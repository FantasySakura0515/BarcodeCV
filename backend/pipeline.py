import logging
import time
import uuid
from datetime import datetime
from pathlib import Path
from threading import Event
from typing import Protocol, runtime_checkable

import cv2
import numpy as np

from .camera.camera_manager import CameraManager
from .database.repository import BoxRecord, BoxRepository, ScanRecord, ScanRepository
from .decoding.direct_scanner import CompositeScanner, ScanResult
from .detection.box_detector import BoxDetector
from .detection.preprocessor import preprocess_for_detection
from .detection.spatial_matcher import ScanSummary, SpatialMatcher
from .utils.image_utils import enhance_contrast, sharpen

logger = logging.getLogger("barcodecv.pipeline")


@runtime_checkable
class _ScannerProtocol(Protocol):
    """Structural interface shared by CompositeScanner and NNDecoder."""

    def scan(self, image: np.ndarray) -> list[ScanResult]:
        ...

    def name(self) -> str:
        ...


class ScanPipeline:
    """Orchestrates a single-camera DataMatrix scan cycle.

    Supports two scanner backends (set via ``config.scanner.mode``):
      - ``"nn"`` (default): YOLO detection + CRNN recognition — fully neural
        network pipeline; no third-party barcode libraries required at runtime.
      - ``"library"``: Legacy pylibdmtx/zxing-cpp composite scanner.

    When box_detector is provided, each scan also detects boxes on the surface
    and flags any box without a matching DataMatrix as "missing_datamatrix".
    """

    def __init__(
        self,
        camera_manager: CameraManager,
        scanner: _ScannerProtocol,
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

        if self._save_images:
            Path(self._image_dir).mkdir(parents=True, exist_ok=True)

    def run_single_scan(self) -> ScanSummary:
        """Execute one full single-camera scan cycle."""
        session_id = self._session_id or str(uuid.uuid4())[:8]
        timestamp = datetime.now().isoformat()

        logger.info("=== Main Phase: Scanning aggregated frame ===")
        frame = self._cameras.capture()
        detection_image = preprocess_for_detection(frame.image)
        scan_image = self._preprocess_image(detection_image)

        boxes = []
        if self._box_detection_enabled:
            boxes = self._box_detector.detect(detection_image)
            logger.info("Main camera detected %d boxes", len(boxes))

        scan_results = self._scanner.scan(scan_image)
        successful_results = self._deduplicate_results(
            [result for result in scan_results if result.success]
        )
        logger.info("Main camera found %d unique DataMatrix codes", len(successful_results))

        frame_image_path = None
        if self._save_images:
            frame_image_path = self._save_frame(scan_image, session_id, "main")

        scan_record_map: dict[str, tuple[int, ScanResult]] = {}
        for result in successful_results:
            content = result.content
            if not content:
                continue
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
                image_source="main",
                frame_image_path=frame_image_path,
            )
            row_id = self._repo.insert_scan(record)
            scan_record_map[content] = (row_id, result)

        merged_scan_results = [result for _, result in scan_record_map.values()]
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
                    frame_image_path=frame_image_path,
                )
                self._box_repo.insert_box(box_record)

            summary = self._spatial_matcher.summarize(match_results, len(successful_results))
        else:
            summary = ScanSummary(
                matched=[],
                missing=[],
                total_boxes=0,
                total_datamatrix=len(successful_results),
            )

        logger.info(
            "Scan complete: %d codes decoded, %d boxes matched, %d missing DataMatrix",
            len(successful_results),
            len(summary.matched),
            len(summary.missing),
        )
        return summary

    @staticmethod
    def _deduplicate_results(results: list[ScanResult]) -> list[ScanResult]:
        unique: dict[str, ScanResult] = {}
        for result in results:
            if result.content and result.content not in unique:
                unique[result.content] = result
        return list(unique.values())

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
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{session_id}_{label}_{ts}.jpg"
        path = str(Path(self._image_dir) / filename)
        cv2.imwrite(path, image, [cv2.IMWRITE_JPEG_QUALITY, 85])
        return path
