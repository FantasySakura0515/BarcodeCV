from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import sqlite3
from pathlib import Path
import uuid

import cv2
import numpy as np

from ..database.repository import ScanRecord, ScanRepository
from ..decoding.direct_scanner import ScanResult
from ..detection.box_detector import BoxDetector
from ..detection.opencv_datamatrix_detector import OpenCVDataMatrixDetector, OpenCVDataMatrixResult
from ..detection.spatial_matcher import SpatialMatcher
from ..services.model_service import ModelService


@dataclass
class DetectionRunResult:
    rid: str
    image_path: str
    objects: list[dict]
    source_image: dict[str, int]


@dataclass
class DetectionPreviewResult:
    rid: str
    image_path: str | None
    objects: list[dict]
    source_image: dict[str, int]


class DetectionService:
    def __init__(self, conn: sqlite3.Connection, config: dict):
        self._conn = conn
        self._config = config
        self._repo = ScanRepository(conn)
        self._model_service = ModelService(conn)
        self._detector = OpenCVDataMatrixDetector.from_config(config)
        self._fast_detector = OpenCVDataMatrixDetector.from_config(config, fast=True)
        self._box_detection_enabled = config.get("box_detection", {}).get("enabled", True)
        self._box_detector = BoxDetector.from_config(config) if self._box_detection_enabled else None
        self._spatial_matcher = SpatialMatcher.from_config(config) if self._box_detection_enabled else None
        self._min_result_confidence = float(
            config.get("opencv_datamatrix", {}).get("min_output_confidence", 0.6)
        )
        self._output_dir = Path(config.get("system", {}).get("image_output_dir", "./output/images"))
        self._output_dir.mkdir(parents=True, exist_ok=True)
        # Per-camera cache of already-decoded barcodes for live detection.
        # Key: camera_id → list of (barcode_content, (x1, y1, x2, y2)) in original image space.
        # Regions already confirmed do not need re-scanning; effort is redirected
        # to undiscovered barcodes visible in the frame.
        self._live_known: dict[str, list[tuple[str, tuple[int, int, int, int]]]] = {}

    def run_detection(self, file_bytes: bytes, filename: str, model_type: str = "opencv") -> DetectionRunResult:
        image = self._decode_image(file_bytes)
        return self.run_detection_on_image(
            image=image,
            filename=filename,
            model_type=model_type,
            image_source="upload",
        )

    def run_detection_on_image(
        self,
        image: np.ndarray,
        filename: str,
        model_type: str = "opencv",
        image_source: str = "upload",
        camera_id: str | None = None,
    ) -> DetectionRunResult:
        if model_type != "opencv":
            raise ValueError("目前僅支援 opencv 檢測模型")

        rid = uuid.uuid4().hex[:8].upper()
        now = datetime.now().isoformat()
        model = self._model_service.get_active_model(model_type)

        input_path = self._save_image(image, f"{rid}_input.png")
        detections = self._apply_confidence_filter(self._detect_objects(image, fast=False))
        annotated = self._draw_object_overlays(image, detections)
        annotated_path = self._save_image(annotated, f"{rid}_annotated.png")

        self._repo.insert_session(
            rid,
            config={
                "source": image_source,
                "filename": filename,
                "modelType": model_type,
                "cameraId": camera_id,
                "inputImage": input_path,
                "annotatedImage": annotated_path,
            },
        )

        objects = self._build_detection_objects(
            rid=rid,
            now=now,
            detections=detections,
            model=model,
            input_path=input_path,
            annotated_path=annotated_path,
            image_source=image_source,
            camera_id=camera_id,
            persist=True,
        )

        return DetectionRunResult(
            rid=rid,
            image_path=annotated_path,
            objects=objects,
            source_image={"width": int(image.shape[1]), "height": int(image.shape[0])},
        )

    def preview_detection_on_image(
        self,
        image: np.ndarray,
        filename: str,
        model_type: str = "opencv",
        image_source: str = "preview",
        camera_id: str | None = None,
        save_preview_image: bool = False,
    ) -> DetectionPreviewResult:
        if model_type != "opencv":
            raise ValueError("目前僅支援 opencv 檢測模型")

        rid = f"LIVE-{uuid.uuid4().hex[:8].upper()}"
        now = datetime.now().isoformat()
        model = self._model_service.get_active_model(model_type)

        input_path = self._save_image(image, f"{rid}_{Path(filename).stem}_preview.png") if save_preview_image else None
        detections = self._apply_confidence_filter(self._detect_objects(image, fast=True, camera_id=camera_id))
        objects = self._build_detection_objects(
            rid=rid,
            now=now,
            detections=detections,
            model=model,
            input_path=input_path,
            annotated_path=input_path,
            image_source=image_source,
            camera_id=camera_id,
            persist=False,
        )

        return DetectionPreviewResult(
            rid=rid,
            image_path=input_path,
            objects=objects,
            source_image={"width": int(image.shape[1]), "height": int(image.shape[0])},
        )

    def _detect_objects(
        self,
        image: np.ndarray,
        fast: bool,
        camera_id: str | None = None,
    ) -> list[OpenCVDataMatrixResult]:
        detector = self._fast_detector if fast else self._detector

        # Build skip_bboxes from previous-frame known barcodes for live mode.
        skip_bboxes: list[tuple[int, int, int, int]] | None = None
        if fast and camera_id and camera_id in self._live_known:
            skip_bboxes = [bbox for _, bbox in self._live_known[camera_id]] or None

        if fast and self._box_detection_enabled and self._box_detector is not None and self._spatial_matcher is not None:
            boxes = self._detect_boxes_fast(image)
            if boxes:
                # Decode only inside known box regions.  This is fast because
                # only ~N ROIs are scanned instead of up to 150 candidates.
                # Full-frame supplemental pass is intentionally skipped in the
                # fast path — the OpenCVDataMatrixDetector already does a
                # full-frame fallback when a box ROI fails to decode.
                dm_detections = detector.decode_bboxes(image, [box.bbox for box in boxes])
                results = self._merge_box_and_dm(boxes, dm_detections)
                self._update_live_known(camera_id, results)
                return results

            downscaled, scale = self._resize_for_fast_scan(image, target_width=1280)
            # Two-stage: detect on downscaled thumbnail (fast contour detection),
            # then scan each candidate at ORIGINAL resolution (high quality).
            # This is the critical fix for small DataMatrix codes: detection runs
            # on the cheap downscaled image, but the actual zxing scan gets crisp
            # full-resolution pixels, so upscale variants work on real detail.
            results = detector.detect_two_stage_on(
                detection_image=downscaled,
                original_image=image,
                detection_scale=scale,
                skip_bboxes=skip_bboxes,  # already in original-image coords
            )
            self._update_live_known(camera_id, results)
            return results

        dm_detections = detector.detect_and_decode(image, skip_bboxes=skip_bboxes)

        if not self._box_detection_enabled or self._box_detector is None or self._spatial_matcher is None:
            return dm_detections

        boxes = self._box_detector.detect(image)
        if not boxes:
            return dm_detections

        return self._merge_box_and_dm(boxes, dm_detections)

    def _update_live_known(
        self,
        camera_id: str | None,
        results: list[OpenCVDataMatrixResult],
    ) -> None:
        """Merge newly decoded barcodes into the per-camera known-bbox cache.

        Only barcodes with decoded content are stored.  The latest bbox always
        wins (assumes camera/objects may have moved slightly between frames).
        """
        if not camera_id:
            return
        existing = {content: bbox for content, bbox in self._live_known.get(camera_id, [])}
        for r in results:
            if r.content:
                existing[r.content] = tuple(int(v) for v in r.bbox)  # type: ignore[assignment]
        self._live_known[camera_id] = [(c, b) for c, b in existing.items()]

    def clear_live_known(self, camera_id: str) -> None:
        """Reset the tracking cache for a camera (call on stop / camera switch)."""
        self._live_known.pop(camera_id, None)

    def _merge_box_and_dm(self, boxes, dm_detections: list[OpenCVDataMatrixResult]) -> list[OpenCVDataMatrixResult]:
        if self._spatial_matcher is None:
            return dm_detections

        scan_results = [
            ScanResult(
                content=item.content,
                bbox=item.bbox,
                scanner_used=item.decoder_used,
                scan_time_ms=item.scan_time_ms,
                success=bool(item.content),
            )
            for item in dm_detections
            if item.content
        ]
        match_results = self._spatial_matcher.match(boxes, scan_results)

        merged: list[OpenCVDataMatrixResult] = []
        matched_keys: set[tuple[str, tuple[int, int, int, int]]] = set()

        for match in match_results:
            if match.scan_result is not None:
                matched_keys.add((match.scan_result.content, tuple(int(v) for v in match.scan_result.bbox)))
                merged.append(
                    OpenCVDataMatrixResult(
                        content=match.scan_result.content,
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
            key = (item.content, tuple(int(v) for v in item.bbox))
            if item.content and key in matched_keys:
                continue
            merged.append(item)

        return merged

    def _apply_confidence_filter(
        self,
        detections: list[OpenCVDataMatrixResult],
    ) -> list[OpenCVDataMatrixResult]:
        return [
            item for item in detections
            if float(item.confidence or 0.0) >= self._min_result_confidence
        ]

    def _detect_boxes_fast(self, image: np.ndarray):
        if self._box_detector is None:
            return []
        downscaled, scale = self._resize_for_fast_scan(image, target_width=960)
        boxes_small = self._box_detector.detect(downscaled)
        if scale == 1.0:
            return boxes_small

        scaled_boxes = []
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
        return scaled_boxes

    @staticmethod
    def _resize_for_fast_scan(image: np.ndarray, target_width: int = 1280) -> tuple[np.ndarray, float]:
        height, width = image.shape[:2]
        if width <= target_width:
            return image, 1.0
        scale = target_width / float(width)
        resized_height = max(1, int(round(height * scale)))
        resized = cv2.resize(image, (target_width, resized_height), interpolation=cv2.INTER_AREA)
        return resized, scale

    @staticmethod
    def _scale_dm_results(results: list[OpenCVDataMatrixResult], scale: float) -> list[OpenCVDataMatrixResult]:
        if scale == 1.0:
            return results
        scaled: list[OpenCVDataMatrixResult] = []
        for item in results:
            x1, y1, x2, y2 = item.bbox
            scaled.append(
                OpenCVDataMatrixResult(
                    content=item.content,
                    bbox=(
                        int(round(x1 / scale)),
                        int(round(y1 / scale)),
                        int(round(x2 / scale)),
                        int(round(y2 / scale)),
                    ),
                    confidence=item.confidence,
                    decoder_used=item.decoder_used,
                    detection_source=item.detection_source,
                    scan_time_ms=item.scan_time_ms,
                )
            )
        return scaled

    @staticmethod
    def _draw_object_overlays(image: np.ndarray, detections: list[OpenCVDataMatrixResult]) -> np.ndarray:
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

    def _build_detection_objects(
        self,
        rid: str,
        now: str,
        detections: list,
        model: dict,
        input_path: str | None,
        annotated_path: str | None,
        image_source: str,
        camera_id: str | None,
        persist: bool,
    ) -> list[dict]:
        objects: list[dict] = []
        for index, detection in enumerate(detections, start=1):
            row_id: int | None = None
            bid = f"LIVE-{index:03d}"

            if persist:
                record = ScanRecord(
                    session_id=rid,
                    timestamp=now,
                    detection_confidence=detection.confidence,
                    bbox_x1=detection.bbox[0],
                    bbox_y1=detection.bbox[1],
                    bbox_x2=detection.bbox[2],
                    bbox_y2=detection.bbox[3],
                    decoded_content=detection.content,
                    decode_success=bool(detection.content),
                    decoder_used=detection.decoder_used,
                    decode_time_ms=detection.scan_time_ms,
                    image_source=camera_id or detection.detection_source or image_source,
                    wide_image_path=annotated_path,
                    closeup_image_path=input_path,
                )
                row_id = self._repo.insert_scan(record)
                bid = f"BID-{row_id:06d}"

            objects.append(
                {
                    "id": str(row_id or index),
                    "rid": rid,
                    "bid": bid,
                    "bbox": {
                        "x1": int(detection.bbox[0]),
                        "y1": int(detection.bbox[1]),
                        "x2": int(detection.bbox[2]),
                        "y2": int(detection.bbox[3]),
                    },
                    "barcodeValue": detection.content or None,
                    "barcodeType": "DataMatrix" if detection.content else None,
                    "ocrText": None,
                    "confidenceScore": float(detection.confidence or 0.0),
                    "modelId": model["id"],
                    "model": model,
                    "imagePath": annotated_path,
                    "remark": None,
                    "createdAt": now,
                    "updatedAt": now,
                }
            )

        return objects

    def list_batches(self, limit: int = 50, offset: int = 0) -> list[dict]:
        model = self._model_service.get_active_model("opencv")
        rows = self._conn.execute(
            """
            SELECT
                s.id AS rid,
                s.started_at AS created_at,
                COUNT(r.id) AS object_count,
                SUM(CASE WHEN r.decode_success = 1 THEN 1 ELSE 0 END) AS barcode_success_count
            FROM scan_sessions s
            LEFT JOIN scan_records r ON r.session_id = s.id
            GROUP BY s.id, s.started_at
            ORDER BY s.started_at DESC
            LIMIT ? OFFSET ?
            """,
            (limit, offset),
        ).fetchall()

        batches: list[dict] = []
        for row in rows:
            batches.append(
                {
                    "rid": row["rid"],
                    "objectCount": row["object_count"] or 0,
                    "barcodeSuccessCount": row["barcode_success_count"] or 0,
                    "ocrSuccessCount": 0,
                    "model": model,
                    "createdAt": row["created_at"],
                    "objects": self.list_objects_by_rid(row["rid"], model=model),
                }
            )
        return batches

    def get_batch(self, rid: str) -> dict | None:
        model = self._model_service.get_active_model("opencv")
        session = self._conn.execute(
            "SELECT id, started_at FROM scan_sessions WHERE id = ?",
            (rid,),
        ).fetchone()
        if session is None:
            return None

        objects = self.list_objects_by_rid(rid, model=model)
        barcode_success_count = sum(1 for item in objects if item["barcodeValue"])
        return {
            "rid": rid,
            "objectCount": len(objects),
            "barcodeSuccessCount": barcode_success_count,
            "ocrSuccessCount": 0,
            "model": model,
            "createdAt": session["started_at"],
            "objects": objects,
        }

    def get_object(self, bid: str) -> dict | None:
        row_id = self._parse_bid(bid)
        if row_id is None:
            return None
        row = self._conn.execute(
            "SELECT * FROM scan_records WHERE id = ?",
            (row_id,),
        ).fetchone()
        if row is None:
            return None
        if not self._passes_row_confidence(row):
            return None
        model = self._model_service.get_active_model("opencv")
        return self._build_object_dict(row_id=row_id, rid=row["session_id"], row=row, model=model)

    def update_object_remark(self, bid: str, remark: str) -> dict | None:
        row_id = self._parse_bid(bid)
        if row_id is None:
            return None
        self._conn.execute(
            "UPDATE scan_records SET remark = ? WHERE id = ?",
            (remark, row_id),
        )
        self._conn.commit()
        return self.get_object(bid)

    def list_objects_by_rid(self, rid: str, model: dict | None = None) -> list[dict]:
        model = model or self._model_service.get_active_model("opencv")
        rows = self._conn.execute(
            "SELECT * FROM scan_records WHERE session_id = ? ORDER BY id ASC",
            (rid,),
        ).fetchall()
        return [
            self._build_object_dict(row_id=row["id"], rid=rid, row=row, model=model)
            for row in rows
            if self._passes_row_confidence(row)
        ]

    @staticmethod
    def _parse_bid(bid: str) -> int | None:
        if not bid.startswith("BID-"):
            return None
        try:
            return int(bid.split("-", 1)[1])
        except ValueError:
            return None

    def _decode_image(self, file_bytes: bytes) -> np.ndarray:
        array = np.frombuffer(file_bytes, dtype=np.uint8)
        image = cv2.imdecode(array, cv2.IMREAD_COLOR)
        if image is None:
            raise ValueError("無法解析上傳影像")
        return image

    def _save_image(self, image: np.ndarray, file_name: str) -> str:
        path = self._output_dir / file_name
        cv2.imwrite(str(path), image)
        return f"/api/images/{file_name}"

    def _passes_row_confidence(self, row: sqlite3.Row | dict) -> bool:
        return float(row["detection_confidence"] or 0.0) >= self._min_result_confidence

    @staticmethod
    def _build_object_dict(row_id: int, rid: str, row: sqlite3.Row | dict, model: dict) -> dict:
        created_at = row["created_at"] if "created_at" in row.keys() else row["timestamp"]
        return {
            "id": str(row_id),
            "rid": rid,
            "bid": f"BID-{row_id:06d}",
            "bbox": {
                "x1": int(row["bbox_x1"] or 0),
                "y1": int(row["bbox_y1"] or 0),
                "x2": int(row["bbox_x2"] or 0),
                "y2": int(row["bbox_y2"] or 0),
            },
            "barcodeValue": row["decoded_content"] or None,
            "barcodeType": "DataMatrix" if row["decoded_content"] else None,
            "ocrText": None,
            "confidenceScore": float(row["detection_confidence"] or 0.0),
            "modelId": model["id"],
            "model": model,
            "imagePath": row["wide_image_path"] or None,
            "remark": row["remark"] if "remark" in row.keys() else None,
            "createdAt": created_at,
            "updatedAt": created_at,
        }
