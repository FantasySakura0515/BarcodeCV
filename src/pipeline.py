import logging
import time
import uuid
from datetime import datetime
from pathlib import Path
from threading import Event

import cv2

from .camera.camera_manager import CameraManager
from .database.repository import BoxRecord, BoxRepository, ScanRecord, ScanRepository
from .decoding.direct_scanner import CompositeScanner, ScanResult
from .detection.box_detector import BoxDetectionResult, BoxDetector
from .detection.detector import YOLODetector
from .detection.spatial_matcher import ScanSummary, SpatialMatcher
from .utils.image_utils import enhance_contrast, sharpen

logger = logging.getLogger("barcodecv.pipeline")


class ScanPipeline:
    """Orchestrates the scan cycle.

    When a YOLO model is provided:
      1. YOLO detects boxes + DataMatrix regions on the global frame
      2. Each DataMatrix region is cropped and decoded with pylibdmtx/zxing-cpp
      3. SpatialMatcher pairs each box with its DataMatrix
      4. Boxes without a matching DataMatrix are flagged

    Without YOLO (fallback):
      Scans the entire image with pylibdmtx/zxing-cpp directly.
    """

    def __init__(
        self,
        camera_manager: CameraManager,
        scanner: CompositeScanner,
        repository: ScanRepository,
        config: dict,
        yolo_detector: YOLODetector | None = None,
        box_detector: BoxDetector | None = None,
        spatial_matcher: SpatialMatcher | None = None,
        box_repo: BoxRepository | None = None,
    ):
        self._cameras = camera_manager
        self._scanner = scanner
        self._repo = repository
        self._config = config
        self._stop_event = Event()
        self._session_id: str | None = None

        self._yolo = yolo_detector
        self._box_detector = box_detector
        self._spatial_matcher = spatial_matcher
        self._box_repo = box_repo

        self._save_images = config.get("system", {}).get("save_images", False)
        self._image_dir = config.get("system", {}).get("image_output_dir", "./output/images")
        self._preprocess_cfg = config.get("decoding", {}).get("preprocessing", {})
        self._crop_padding = config.get("detection", {}).get("crop_padding", 10)

    def run_single_scan(self) -> ScanSummary:
        """Execute one full scan cycle."""
        session_id = self._session_id or str(uuid.uuid4())[:8]
        timestamp = datetime.now().isoformat()

        # --- Capture ---
        logger.info("=== Capturing global frame ===")
        global_frame = self._cameras.capture_global()
        global_image = global_frame.image

        global_image_path = None
        if self._save_images:
            global_image_path = self._save_frame(global_image, session_id, "global")

        # --- YOLO or library fallback ---
        if self._yolo is None:
            return self._run_library_only(global_image, session_id, timestamp, global_image_path)

        logger.info("=== YOLO Detection ===")
        all_detections = self._yolo.detect(global_image)
        box_detections = [d for d in all_detections if d.class_name == "box"]
        dm_detections = [d for d in all_detections if d.class_name == "datamatrix"]

        # --- Crop + Decode each DataMatrix region ---
        logger.info("=== Decoding %d DataMatrix regions ===", len(dm_detections))
        decoded_results: list[ScanResult] = []
        for det in dm_detections:
            crop = self._crop_region(global_image, det.bbox)
            crop = self._preprocess_image(crop)

            scan_results = self._scanner.scan(crop)
            successful = [r for r in scan_results if r.success]

            if successful:
                best = successful[0]
                decoded_results.append(ScanResult(
                    content=best.content,
                    bbox=det.bbox,
                    scanner_used=best.scanner_used,
                    scan_time_ms=best.scan_time_ms,
                    success=True,
                ))
            else:
                decoded_results.append(ScanResult(
                    content=None,
                    bbox=det.bbox,
                    scanner_used="none",
                    scan_time_ms=0,
                    success=False,
                ))

        successful_decodes = [r for r in decoded_results if r.success]
        logger.info("Decoded %d / %d DataMatrix regions", len(successful_decodes), len(dm_detections))

        # --- Persist scan_records ---
        scan_record_map: dict[str, int] = {}
        for result in successful_decodes:
            record = ScanRecord(
                session_id=session_id,
                timestamp=timestamp,
                detection_confidence=None,
                bbox_x1=result.bbox[0],
                bbox_y1=result.bbox[1],
                bbox_x2=result.bbox[2],
                bbox_y2=result.bbox[3],
                decoded_content=result.content,
                decode_success=True,
                decoder_used=result.scanner_used,
                decode_time_ms=result.scan_time_ms,
                image_source="global",
                wide_image_path=global_image_path,
                closeup_image_path=None,
            )
            row_id = self._repo.insert_scan(record)
            scan_record_map[result.content] = row_id

        # --- Spatial Matching ---
        if self._spatial_matcher and box_detections:
            boxes = [
                BoxDetectionResult(
                    bbox=d.bbox,
                    area=float((d.bbox[2] - d.bbox[0]) * (d.bbox[3] - d.bbox[1])),
                    contour=None,
                )
                for d in box_detections
            ]
            match_results = self._spatial_matcher.match(boxes, successful_decodes)

            if self._box_repo:
                for match in match_results:
                    content = match.scan_result.content if match.scan_result else None
                    scan_id = scan_record_map.get(content) if content else None
                    box_record = BoxRecord(
                        session_id=session_id,
                        timestamp=timestamp,
                        status=match.status,
                        box_bbox_x1=match.box.bbox[0],
                        box_bbox_y1=match.box.bbox[1],
                        box_bbox_x2=match.box.bbox[2],
                        box_bbox_y2=match.box.bbox[3],
                        box_area=match.box.area,
                        scan_record_id=scan_id,
                        decoded_content=content,
                        overlap_ratio=match.overlap_ratio,
                        wide_image_path=global_image_path,
                    )
                    self._box_repo.insert_box(box_record)

            summary = self._spatial_matcher.summarize(match_results, len(successful_decodes))
        else:
            summary = ScanSummary(
                matched=[], missing=[],
                total_boxes=len(box_detections),
                total_datamatrix=len(successful_decodes),
            )

        logger.info(
            "Scan complete: %d codes, %d matched, %d missing",
            len(successful_decodes), len(summary.matched), len(summary.missing),
        )
        return summary

    def _run_library_only(self, image, session_id, timestamp, image_path) -> ScanSummary:
        """Scan with library scanners + optional OpenCV box detection."""
        logger.info("=== Library scan (pylibdmtx/zxing-cpp) ===")
        results = self._scanner.scan(image)
        successful = [r for r in results if r.success]
        logger.info("Found %d DataMatrix codes", len(successful))

        # Persist scan records
        scan_record_map: dict[str, int] = {}
        for r in successful:
            record = ScanRecord(
                session_id=session_id,
                timestamp=timestamp,
                detection_confidence=None,
                bbox_x1=r.bbox[0], bbox_y1=r.bbox[1],
                bbox_x2=r.bbox[2], bbox_y2=r.bbox[3],
                decoded_content=r.content,
                decode_success=True,
                decoder_used=r.scanner_used,
                decode_time_ms=r.scan_time_ms,
                image_source="global",
                wide_image_path=image_path,
                closeup_image_path=None,
            )
            row_id = self._repo.insert_scan(record)
            scan_record_map[r.content] = row_id

        # OpenCV box detection + spatial matching
        if self._box_detector and self._spatial_matcher:
            logger.info("=== OpenCV Box Detection ===")
            boxes = self._box_detector.detect(image)
            match_results = self._spatial_matcher.match(boxes, successful)

            if self._box_repo:
                for match in match_results:
                    content = match.scan_result.content if match.scan_result else None
                    scan_id = scan_record_map.get(content) if content else None
                    box_record = BoxRecord(
                        session_id=session_id,
                        timestamp=timestamp,
                        status=match.status,
                        box_bbox_x1=match.box.bbox[0],
                        box_bbox_y1=match.box.bbox[1],
                        box_bbox_x2=match.box.bbox[2],
                        box_bbox_y2=match.box.bbox[3],
                        box_area=match.box.area,
                        scan_record_id=scan_id,
                        decoded_content=content,
                        overlap_ratio=match.overlap_ratio,
                        wide_image_path=image_path,
                    )
                    self._box_repo.insert_box(box_record)

            return self._spatial_matcher.summarize(match_results, len(successful))

        return ScanSummary(
            matched=[], missing=[],
            total_boxes=0, total_datamatrix=len(successful),
        )

    def _crop_region(self, image, bbox: tuple[int, int, int, int]):
        h, w = image.shape[:2]
        pad = self._crop_padding
        x1 = max(0, bbox[0] - pad)
        y1 = max(0, bbox[1] - pad)
        x2 = min(w, bbox[2] + pad)
        y2 = min(h, bbox[3] + pad)
        return image[y1:y2, x1:x2].copy()

    def _preprocess_image(self, image):
        cfg = self._preprocess_cfg
        if cfg.get("clahe", False):
            image = enhance_contrast(image, cfg.get("clahe_clip_limit", 2.0))
            if len(image.shape) == 2:
                image = cv2.cvtColor(image, cv2.COLOR_GRAY2BGR)
        if cfg.get("sharpen", False):
            image = sharpen(image)
        return image

    def run_continuous(self, interval_seconds: float = 2.0) -> None:
        self._stop_event.clear()
        self._session_id = str(uuid.uuid4())[:8]
        self._repo.insert_session(self._session_id, config=self._config)

        logger.info(
            "Starting continuous scan (session=%s, interval=%.1fs)",
            self._session_id, interval_seconds,
        )

        cycle = 0
        try:
            while not self._stop_event.is_set():
                cycle += 1
                logger.info("--- Scan cycle %d ---", cycle)
                start = time.perf_counter()

                try:
                    summary = self.run_single_scan()
                    for m in summary.matched:
                        logger.info("  [OK] %s (via %s)", m.scan_result.content, m.scan_result.scanner_used)
                    for m in summary.missing:
                        logger.warning("  [!!] Box at bbox=%s has no DataMatrix", m.box.bbox)
                except Exception as e:
                    logger.error("Scan cycle %d failed: %s", cycle, e)

                elapsed = time.perf_counter() - start
                sleep_time = max(0, interval_seconds - elapsed)
                if sleep_time > 0:
                    self._stop_event.wait(sleep_time)
        finally:
            self._repo.end_session(self._session_id)
            logger.info("Continuous scan stopped after %d cycles", cycle)

    def stop(self) -> None:
        self._stop_event.set()

    def _save_frame(self, image, session_id: str, label: str) -> str:
        Path(self._image_dir).mkdir(parents=True, exist_ok=True)
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{session_id}_{label}_{ts}.jpg"
        path = str(Path(self._image_dir) / filename)
        cv2.imwrite(path, image, [cv2.IMWRITE_JPEG_QUALITY, 85])
        return path
