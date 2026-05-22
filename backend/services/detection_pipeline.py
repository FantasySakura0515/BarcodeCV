from __future__ import annotations

import logging

import cv2
import numpy as np

from ..decoding.direct_scanner import ScanResult, sanitize_decoded_text
from ..detection.box_detector import BoxDetectionResult
from ..detection.opencv_datamatrix_detector import OpenCVDataMatrixResult

logger = logging.getLogger("barcodecv.detection_pipeline")


class DetectionPipeline:
    def __init__(
        self,
        *,
        detector,
        fast_detector,
        box_detection_enabled: bool,
        box_detector,
        spatial_matcher,
        min_result_confidence: float,
        square_ratio_max: float,
        square_candidate_limit: int,
        supplement_when_mismatch: bool,
    ) -> None:
        self._detector = detector
        self._fast_detector = fast_detector
        self._box_detection_enabled = box_detection_enabled
        self._box_detector = box_detector
        self._spatial_matcher = spatial_matcher
        self._min_result_confidence = min_result_confidence
        self._square_ratio_max = square_ratio_max
        self._square_candidate_limit = square_candidate_limit
        self._supplement_when_mismatch = supplement_when_mismatch
        self._live_known: dict[str, list[tuple[str, tuple[int, int, int, int]]]] = {}

    def detect_objects(
        self,
        image: np.ndarray,
        *,
        fast: bool,
        camera_id: str | None = None,
    ) -> list[OpenCVDataMatrixResult]:
        detector = self._fast_detector if fast else self._detector

        skip_bboxes: list[tuple[int, int, int, int]] | None = None
        if fast and camera_id and camera_id in self._live_known:
            skip_bboxes = [bbox for _, bbox in self._live_known[camera_id]] or None

        if self._box_detection_enabled and self._box_detector is not None and self._spatial_matcher is not None:
            boxes = self._detect_boxes_fast(image) if fast else self._select_square_boxes(self._box_detector.detect(image))
            if boxes:
                box_bboxes = [box.bbox for box in boxes]
                roi_detections = detector.decode_bboxes(image, box_bboxes)
                combined_dm = list(roi_detections)

                decoded_contents = {item.content for item in roi_detections if item.content}
                decoded_bboxes = [
                    tuple(int(v) for v in item.bbox)
                    for item in roi_detections
                    if sanitize_decoded_text(item.content)
                ]
                missing_count = max(0, len(boxes) - len(decoded_contents))
                needs_supplement = self._supplement_when_mismatch and len(decoded_contents) < len(boxes)

                if needs_supplement:
                    if fast:
                        # For dense clean images (e.g. 100+ boxes), fast-mode
                        # ROI decode can leave a small tail of misses.
                        # Escalate to full-quality supplement only when miss
                        # count is meaningful, otherwise keep fast path.
                        accuracy_boost = (
                            len(boxes) >= 40
                            and missing_count >= max(3, int(round(len(boxes) * 0.04)))
                        )
                        if accuracy_boost:
                            supplement_dm = self._detector.detect_and_decode(
                                image,
                                skip_bboxes=decoded_bboxes or None,
                            )
                        else:
                            downscaled, scale = self._resize_for_fast_scan(image, target_width=1280)
                            supplement_dm = detector.detect_two_stage_on(
                                detection_image=downscaled,
                                original_image=image,
                                detection_scale=scale,
                                # Skip only already-decoded regions; skipping
                                # all box bboxes prevents recovery of misses.
                                skip_bboxes=decoded_bboxes or None,
                            )
                    else:
                        supplement_dm = detector.detect_and_decode(
                            image,
                            # Skip only already-decoded regions; this lets
                            # supplement pass focus on boxes that failed ROI decode.
                            skip_bboxes=decoded_bboxes or None,
                        )
                    combined_dm.extend(supplement_dm)

                dm_detections = self._deduplicate_dm_detections(combined_dm)
                results = self._merge_box_and_dm(boxes, dm_detections)

                if fast:
                    self._update_live_known(camera_id, results)

                logger.debug(
                    "square-first pipeline: boxes=%d, roi_dm=%d, merged=%d, missing=%d, supplement=%s",
                    len(boxes),
                    len(roi_detections),
                    len(results),
                    missing_count,
                    "yes" if needs_supplement else "no",
                )
                return results

        if fast:
            downscaled, scale = self._resize_for_fast_scan(image, target_width=1280)
            results = detector.detect_two_stage_on(
                detection_image=downscaled,
                original_image=image,
                detection_scale=scale,
                skip_bboxes=skip_bboxes,
            )
            self._update_live_known(camera_id, results)
            return results

        return detector.detect_and_decode(image, skip_bboxes=skip_bboxes)

    def apply_confidence_filter(
        self,
        detections: list[OpenCVDataMatrixResult],
    ) -> list[OpenCVDataMatrixResult]:
        filtered: list[OpenCVDataMatrixResult] = []
        for item in detections:
            normalized_content = sanitize_decoded_text(item.content)
            if not normalized_content:
                # Keep box-only placeholders so UI can show objects that were
                # detected but failed to decode.
                if item.detection_source == "box-only":
                    filtered.append(item)
                continue

            if float(item.confidence or 0.0) >= self._min_result_confidence:
                filtered.append(item)

        return filtered

    def clear_live_known(self, camera_id: str) -> None:
        self._live_known.pop(camera_id, None)

    @staticmethod
    def draw_object_overlays(image: np.ndarray, detections: list[OpenCVDataMatrixResult]) -> np.ndarray:
        output = image.copy()
        for index, detection in enumerate(detections, start=1):
            x1, y1, x2, y2 = detection.bbox
            decoded = bool(detection.content)
            color = (34, 197, 94) if decoded else (0, 191, 255)
            label = detection.content if decoded else f"Box {index}"
            cv2.rectangle(output, (x1, y1), (x2, y2), color, 2)
            text_y = y1 - 10 if y1 > 24 else y1 + 22
            cv2.putText(
                output,
                label,
                (x1, text_y),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.55,
                color,
                2,
                cv2.LINE_AA,
            )
        return output

    def _update_live_known(
        self,
        camera_id: str | None,
        results: list[OpenCVDataMatrixResult],
    ) -> None:
        if not camera_id:
            return
        existing = {content: bbox for content, bbox in self._live_known.get(camera_id, [])}
        for result in results:
            if result.content:
                existing[result.content] = tuple(int(v) for v in result.bbox)
        self._live_known[camera_id] = [(content, bbox) for content, bbox in existing.items()]

    def _merge_box_and_dm(
        self,
        boxes: list[BoxDetectionResult],
        dm_detections: list[OpenCVDataMatrixResult],
    ) -> list[OpenCVDataMatrixResult]:
        if self._spatial_matcher is None:
            return self._deduplicate_final_detections(dm_detections)

        scan_results = [
            ScanResult(
                content=sanitize_decoded_text(item.content),
                bbox=item.bbox,
                scanner_used=item.decoder_used,
                scan_time_ms=item.scan_time_ms,
                success=bool(sanitize_decoded_text(item.content)),
            )
            for item in dm_detections
            if sanitize_decoded_text(item.content)
        ]
        match_results = self._spatial_matcher.match(boxes, scan_results)

        merged: list[OpenCVDataMatrixResult] = []
        matched_keys: set[tuple[str, tuple[int, int, int, int]]] = set()

        for match in match_results:
            if match.scan_result is not None:
                normalized_content = sanitize_decoded_text(match.scan_result.content)
                if not normalized_content:
                    continue
                matched_keys.add((normalized_content, tuple(int(v) for v in match.scan_result.bbox)))
                merged.append(
                    OpenCVDataMatrixResult(
                        content=normalized_content,
                        bbox=match.box.bbox,
                        confidence=max(0.9, match.overlap_ratio),
                        decoder_used=match.scan_result.scanner_used,
                        detection_source="box-matched",
                        scan_time_ms=match.scan_result.scan_time_ms,
                    )
                )
            else:
                merged.append(
                    OpenCVDataMatrixResult(
                        content="",
                        bbox=match.box.bbox,
                        confidence=0.35,
                        decoder_used="box-detector",
                        detection_source="box-only",
                        scan_time_ms=0.0,
                    )
                )

        for item in dm_detections:
            normalized_content = sanitize_decoded_text(item.content)
            if not normalized_content:
                continue
            key = (normalized_content, tuple(int(v) for v in item.bbox))
            if key in matched_keys:
                continue

            duplicate = False
            for existing in merged:
                if not existing.content:
                    continue
                iou = self._bbox_iou(existing.bbox, item.bbox)
                if iou >= 0.65:
                    duplicate = True
                    break
                if existing.content == normalized_content and iou >= 0.25:
                    duplicate = True
                    break

            if duplicate:
                continue

            merged.append(
                OpenCVDataMatrixResult(
                    content=normalized_content,
                    bbox=item.bbox,
                    confidence=item.confidence,
                    decoder_used=item.decoder_used,
                    detection_source=item.detection_source,
                    scan_time_ms=item.scan_time_ms,
                )
            )

        return self._deduplicate_final_detections(merged)

    def _detect_boxes_fast(self, image: np.ndarray) -> list[BoxDetectionResult]:
        if self._box_detector is None:
            return []
        downscaled, scale = self._resize_for_fast_scan(image, target_width=960)
        boxes_small = self._box_detector.detect(downscaled)
        if scale == 1.0:
            return boxes_small

        scaled_boxes: list[BoxDetectionResult] = []
        for box in boxes_small:
            x1, y1, x2, y2 = box.bbox
            scaled_boxes.append(
                type(box)(
                    bbox=(
                        int(round(x1 / scale)),
                        int(round(y1 / scale)),
                        int(round(x2 / scale)),
                        int(round(y2 / scale)),
                    ),
                    area=float(box.area / max(scale * scale, 1e-6)),
                    contour=box.contour,
                )
            )
        return self._select_square_boxes(scaled_boxes)

    def _select_square_boxes(self, boxes: list[BoxDetectionResult]) -> list[BoxDetectionResult]:
        if not boxes:
            return []

        square_like: list[BoxDetectionResult] = []
        for box in boxes:
            x1, y1, x2, y2 = box.bbox
            width = max(1, int(x2) - int(x1))
            height = max(1, int(y2) - int(y1))
            ratio = max(width, height) / max(1.0, min(width, height))
            if ratio <= self._square_ratio_max:
                square_like.append(box)

        target = square_like if square_like else boxes
        target.sort(
            key=lambda box: (
                abs(1.0 - self._bbox_aspect_ratio(box.bbox)),
                -float(getattr(box, "area", 0.0)),
            )
        )
        return target[: self._square_candidate_limit]

    @staticmethod
    def _bbox_aspect_ratio(bbox: tuple[int, int, int, int]) -> float:
        x1, y1, x2, y2 = bbox
        width = max(1, int(x2) - int(x1))
        height = max(1, int(y2) - int(y1))
        return max(width, height) / max(1.0, min(width, height))

    @staticmethod
    def _deduplicate_dm_detections(
        detections: list[OpenCVDataMatrixResult],
    ) -> list[OpenCVDataMatrixResult]:
        sanitized: list[OpenCVDataMatrixResult] = []
        for item in detections:
            normalized_content = sanitize_decoded_text(item.content)
            if not normalized_content:
                continue
            sanitized.append(
                OpenCVDataMatrixResult(
                    content=normalized_content,
                    bbox=tuple(int(v) for v in item.bbox),
                    confidence=float(item.confidence or 0.0),
                    decoder_used=item.decoder_used,
                    detection_source=item.detection_source,
                    scan_time_ms=float(item.scan_time_ms or 0.0),
                )
            )

        deduped: list[OpenCVDataMatrixResult] = []
        for item in sorted(sanitized, key=lambda entry: entry.confidence, reverse=True):
            is_duplicate = False
            for existing in deduped:
                iou = DetectionPipeline._bbox_iou(existing.bbox, item.bbox)
                if iou >= 0.65:
                    is_duplicate = True
                    break
                if existing.content == item.content and iou >= 0.25:
                    is_duplicate = True
                    break

            if not is_duplicate:
                deduped.append(item)

        return deduped

    @staticmethod
    def _deduplicate_final_detections(
        detections: list[OpenCVDataMatrixResult],
    ) -> list[OpenCVDataMatrixResult]:
        deduped: list[OpenCVDataMatrixResult] = []
        for item in sorted(detections, key=lambda entry: float(entry.confidence or 0.0), reverse=True):
            duplicate = False
            for existing in deduped:
                iou = DetectionPipeline._bbox_iou(existing.bbox, item.bbox)
                if iou >= 0.65:
                    duplicate = True
                    break
                if existing.content and item.content and existing.content == item.content and iou >= 0.2:
                    duplicate = True
                    break
            if not duplicate:
                deduped.append(item)
        return deduped

    @staticmethod
    def _bbox_iou(a: tuple[int, int, int, int], b: tuple[int, int, int, int]) -> float:
        ax1, ay1, ax2, ay2 = a
        bx1, by1, bx2, by2 = b
        inter_x1 = max(ax1, bx1)
        inter_y1 = max(ay1, by1)
        inter_x2 = min(ax2, bx2)
        inter_y2 = min(ay2, by2)
        inter_w = max(0, inter_x2 - inter_x1)
        inter_h = max(0, inter_y2 - inter_y1)
        inter_area = inter_w * inter_h
        area_a = max(0, ax2 - ax1) * max(0, ay2 - ay1)
        area_b = max(0, bx2 - bx1) * max(0, by2 - by1)
        union = area_a + area_b - inter_area
        return inter_area / union if union else 0.0

    @staticmethod
    def _resize_for_fast_scan(image: np.ndarray, target_width: int = 1280) -> tuple[np.ndarray, float]:
        height, width = image.shape[:2]
        if width <= target_width:
            return image, 1.0
        scale = target_width / float(width)
        resized_height = max(1, int(round(height * scale)))
        resized = cv2.resize(image, (target_width, resized_height), interpolation=cv2.INTER_AREA)
        return resized, scale
