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
from .detection.box_detector import BoxDetector
from .detection.preprocessor import preprocess_for_detection
from .detection.spatial_matcher import ScanSummary, SpatialMatcher
from .utils.image_utils import enhance_contrast, sharpen

logger = logging.getLogger("barcodecv.pipeline")


class ScanPipeline:
    """Orchestrates the Global-to-Local DataMatrix scan cycle.

    Supports two detection strategies:
      - "library" (default): Use pylibdmtx/zxing-cpp to directly scan entire images.
        No YOLO model needed. Simpler and works out of the box.
      - "yolo": Use a trained YOLO model for detection, then crop and decode.
        Better for small/distant codes. Requires a trained model.

    When box_detector is provided, each scan also detects boxes on the surface
    and flags any box without a matching DataMatrix as "missing_datamatrix".
    """

    def __init__(
        self,
        camera_manager: CameraManager,
        scanner: CompositeScanner,
        repository: ScanRepository,
        config: dict,
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

        self._box_detector = box_detector
        self._spatial_matcher = spatial_matcher
        self._box_repo = box_repo
        self._box_detection_enabled = (
            box_detector is not None
            and config.get("box_detection", {}).get("enabled", True)
        )

        self._save_images = config.get("system", {}).get("save_images", False)
        self._image_dir = config.get("system", {}).get("image_output_dir", "./output/images")
        self._preprocess_cfg = config.get("decoding", {}).get("preprocessing", {})

    def run_single_scan(self) -> ScanSummary:
        """Execute one full Global-to-Local scan cycle.

        1. Global camera captures wide view → BoxDetector + CompositeScanner
        2. Local camera captures close-up → CompositeScanner (higher resolution)
        3. Merge DataMatrix results (deduplicate by content, prefer local)
        4. SpatialMatcher pairs each box with its DataMatrix (if any)
        5. Persist scan_records (DataMatrix) and box_records (all boxes)
        6. Return ScanSummary with matched/missing breakdown
        """
        session_id = self._session_id or str(uuid.uuid4())[:8]
        timestamp = datetime.now().isoformat()

        # --- Global Phase ---
        logger.info("=== Global Phase: Scanning wide-angle frame ===")
        global_frame = self._cameras.capture_global()
        global_image = preprocess_for_detection(global_frame.image)

        # Box detection on global frame
        boxes = []
        if self._box_detection_enabled:
            boxes = self._box_detector.detect(global_image)
            logger.info("Global camera detected %d boxes", len(boxes))

        global_results = self._scanner.scan(global_image)
        global_successful = [r for r in global_results if r.success]
        logger.info("Global camera found %d DataMatrix codes", len(global_successful))

        global_image_path = None
        if self._save_images:
            global_image_path = self._save_frame(global_image, session_id, "global")

        # --- Local Phase ---
        logger.info("=== Local Phase: Scanning close-up frame ===")
        local_frame = self._cameras.capture_local()
        local_image = self._preprocess_image(local_frame.image)

        local_results = self._scanner.scan(local_image)
        local_successful = [r for r in local_results if r.success]
        logger.info("Local camera found %d DataMatrix codes", len(local_successful))

        local_image_path = None
        if self._save_images:
            local_image_path = self._save_frame(local_image, session_id, "local")

        # --- Merge DataMatrix Results ---
        merged = self._merge_results(global_successful, local_successful)
        logger.info("Total unique codes after merge: %d", len(merged))

        # --- Persist scan_records ---
        scan_record_map: dict[str, tuple[int, ScanResult, str]] = {}
        for content, result, source in merged:
            record = ScanRecord(
                session_id=session_id,
                timestamp=timestamp,
                detection_confidence=None,
                bbox_x1=result.bbox[0],
                bbox_y1=result.bbox[1],
                bbox_x2=result.bbox[2],
                bbox_y2=result.bbox[3],
                decoded_content=content,
                decode_success=True,
                decoder_used=result.scanner_used,
                decode_time_ms=result.scan_time_ms,
                image_source=source,
                wide_image_path=global_image_path,
                closeup_image_path=local_image_path,
            )
            row_id = self._repo.insert_scan(record)
            scan_record_map[content] = (row_id, result, source)

        # --- Spatial Matching + box_records ---
        merged_scan_results = [result for _, result, _ in merged]
        if self._box_detection_enabled and self._spatial_matcher and self._box_repo:
            match_results = self._spatial_matcher.match(boxes, merged_scan_results)

            for match in match_results:
                box = match.box
                content = match.scan_result.content if match.scan_result else None
                scan_id = scan_record_map[content][0] if content and content in scan_record_map else None

                box_record = BoxRecord(
                    session_id=session_id,
                    timestamp=timestamp,
                    status=match.status,
                    box_bbox_x1=box.bbox[0],
                    box_bbox_y1=box.bbox[1],
                    box_bbox_x2=box.bbox[2],
                    box_bbox_y2=box.bbox[3],
                    box_area=box.area,
                    scan_record_id=scan_id,
                    decoded_content=content,
                    overlap_ratio=match.overlap_ratio,
                    wide_image_path=global_image_path,
                )
                self._box_repo.insert_box(box_record)

            summary = self._spatial_matcher.summarize(match_results, len(merged))
        else:
            # No box detection: build a minimal summary from scan results only
            summary = ScanSummary(
                matched=[],
                missing=[],
                total_boxes=0,
                total_datamatrix=len(merged),
            )

        logger.info(
            "Scan complete: %d codes decoded, %d boxes matched, %d missing DataMatrix",
            len(merged),
            len(summary.matched),
            len(summary.missing),
        )
        return summary

    def _merge_results(
        self,
        global_results: list[ScanResult],
        local_results: list[ScanResult],
    ) -> list[tuple[str, ScanResult, str]]:
        """Merge and deduplicate results from both cameras.

        Prefers Local camera results (higher resolution).
        Returns list of (content, ScanResult, source_label).
        """
        merged: dict[str, tuple[ScanResult, str]] = {}

        for r in local_results:
            if r.content and r.content not in merged:
                merged[r.content] = (r, "local")

        for r in global_results:
            if r.content and r.content not in merged:
                merged[r.content] = (r, "global")

        return [(content, result, source) for content, (result, source) in merged.items()]

    def _preprocess_image(self, image):
        """Apply preprocessing to improve decoding quality."""
        cfg = self._preprocess_cfg
        if cfg.get("clahe", False):
            image = enhance_contrast(image, cfg.get("clahe_clip_limit", 2.0))
            if len(image.shape) == 2:
                image = cv2.cvtColor(image, cv2.COLOR_GRAY2BGR)
        if cfg.get("sharpen", False):
            image = sharpen(image)
        return image

    def run_continuous(self, interval_seconds: float = 2.0) -> None:
        """Run continuous scanning loop."""
        self._stop_event.clear()
        self._session_id = str(uuid.uuid4())[:8]
        self._repo.insert_session(self._session_id, config=self._config)

        logger.info(
            "Starting continuous scan (session=%s, interval=%.1fs)",
            self._session_id,
            interval_seconds,
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
                        logger.info(
                            "  [OK] %s (via %s)",
                            m.scan_result.content,
                            m.scan_result.scanner_used,
                        )
                    for m in summary.missing:
                        logger.warning(
                            "  [!!] Box at bbox=%s has no DataMatrix — reposition needed",
                            m.box.bbox,
                        )
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
        """Signal the continuous loop to stop."""
        self._stop_event.set()

    def _save_frame(self, image, session_id: str, label: str) -> str:
        """Save a frame to disk and return the path."""
        Path(self._image_dir).mkdir(parents=True, exist_ok=True)
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{session_id}_{label}_{ts}.jpg"
        path = str(Path(self._image_dir) / filename)
        cv2.imwrite(path, image, [cv2.IMWRITE_JPEG_QUALITY, 85])
        return path
