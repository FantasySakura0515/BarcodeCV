"""BarcodeCV - Dual-camera DataMatrix scanner for Raspberry Pi 5.

Usage:
    python -m src.main --mode single                    # One-shot scan
    python -m src.main --mode continuous                # Continuous scanning
    python -m src.main --mode calibration               # Camera distance calibration
    python -m src.main --config config/pi5_deploy.yaml  # Use Pi 5 config
"""

import argparse
import signal
import sys

from .calibration.distance_calibrator import DistanceCalibrator
from .calibration.focus_scorer import FocusScorer
from .camera.camera_manager import CameraManager
from .database.db_manager import DatabaseManager
from .database.repository import BoxRepository, ScanRepository
from .decoding.decoder import DataMatrixDecoder, DecodeResult
from .decoding.direct_scanner import CompositeScanner
from .detection.box_detector import BoxDetector
from .detection.spatial_matcher import ScanSummary, SpatialMatcher
from .pipeline import ScanPipeline
from .utils.config_loader import load_config
from .utils.logger import setup_logger


def main():
    parser = argparse.ArgumentParser(description="BarcodeCV - DataMatrix Scanner")
    parser.add_argument(
        "--config",
        type=str,
        default=None,
        help="Path to YAML config file (overrides default.yaml)",
    )
    parser.add_argument(
        "--mode",
        type=str,
        choices=["single", "continuous", "calibration"],
        default=None,
        help="Run mode (overrides config)",
    )
    args = parser.parse_args()

    config = load_config(args.config)
    if args.mode:
        config["system"]["mode"] = args.mode

    logger = setup_logger(
        log_level=config["system"]["log_level"],
        log_file=config["system"].get("log_file"),
    )
    logger.info("BarcodeCV starting in '%s' mode", config["system"]["mode"])

    mode = config["system"]["mode"]

    if mode == "calibration":
        _run_calibration(config)
    elif mode in ("single", "continuous"):
        _run_scanning(config, mode)
    else:
        logger.error("Unknown mode: %s", mode)
        sys.exit(1)


def _run_scanning(config: dict, mode: str):
    """Run single or continuous scanning mode using library-based detection."""
    import logging

    logger = logging.getLogger("barcodecv")

    camera_manager = CameraManager.from_config(config)
    scanner = CompositeScanner.from_config(config)
    db_manager = DatabaseManager(
        db_path=config["database"]["path"],
        wal_mode=config["database"].get("wal_mode", True),
    )

    # Box detection (optional — enabled by config)
    box_cfg = config.get("box_detection", {})
    box_detection_enabled = box_cfg.get("enabled", False)
    box_detector = BoxDetector.from_config(config) if box_detection_enabled else None
    spatial_matcher = SpatialMatcher.from_config(config) if box_detection_enabled else None

    logger.info("Using scanner: %s", scanner.name())
    if box_detection_enabled:
        logger.info("Box detection: enabled")

    with camera_manager, db_manager:
        repo = ScanRepository(db_manager.get_connection())
        box_repo = BoxRepository(db_manager.get_connection()) if box_detection_enabled else None

        pipeline = ScanPipeline(
            camera_manager=camera_manager,
            scanner=scanner,
            repository=repo,
            config=config,
            box_detector=box_detector,
            spatial_matcher=spatial_matcher,
            box_repo=box_repo,
        )

        if mode == "single":
            summary = pipeline.run_single_scan()
            _print_summary(summary)
        else:
            def signal_handler(sig, frame):
                logger.info("Shutdown signal received")
                pipeline.stop()

            signal.signal(signal.SIGINT, signal_handler)
            signal.signal(signal.SIGTERM, signal_handler)

            interval = config["system"].get("scan_interval_seconds", 2.0)
            pipeline.run_continuous(interval_seconds=interval)

        stats = repo.get_statistics()
        logger.info(
            "Session stats: %d total, %d successful (%.1f%%)",
            stats["total_scans"],
            stats["successful_decodes"] or 0,
            stats["success_rate"] * 100,
        )


def _run_calibration(config: dict):
    """Run distance calibration mode."""
    import logging

    logger = logging.getLogger("barcodecv")

    camera_manager = CameraManager.from_config(config)
    scanner = CompositeScanner.from_config(config)
    scorer = FocusScorer()

    cal_cfg = config.get("calibration", {})
    distances = cal_cfg.get("sweep_distances_mm", [50, 100, 150, 200, 250, 300])
    metric = cal_cfg.get("focus_metric", "laplacian")

    # Adapt CompositeScanner to the DataMatrixDecoder interface for the calibrator
    class _ScannerAdapter(DataMatrixDecoder):
        def __init__(self, composite: CompositeScanner):
            self._scanner = composite

        def decode(self, image):
            results = self._scanner.scan(image)
            return [
                DecodeResult(
                    content=r.content,
                    decoder_used=r.scanner_used,
                    decode_time_ms=r.scan_time_ms,
                    success=r.success,
                    error_message=r.error_message,
                )
                for r in results
            ]

        def name(self):
            return self._scanner.name()

    with camera_manager:
        calibrator = DistanceCalibrator(
            camera=camera_manager.local_camera,
            decoder=_ScannerAdapter(scanner),
            focus_scorer=scorer,
            metric=metric,
        )

        logger.info("Starting calibration sweep with distances: %s", distances)
        results = calibrator.run_sweep(distances)
        optimal = calibrator.find_optimal_distance(results)
        calibrator.print_report(results, optimal)


def _print_summary(summary: ScanSummary) -> None:
    """Print scan summary with box pairing results and warnings."""
    if summary.total_boxes == 0:
        # Box detection not enabled — fall back to simple DataMatrix list
        if summary.total_datamatrix == 0:
            print("\nNo DataMatrix codes found.")
        else:
            print(f"\n=== Scan Results: {summary.total_datamatrix} codes decoded ===")
        return

    total = summary.total_boxes
    print(f"\n=== Scan Summary: {total} box{'es' if total != 1 else ''} found ===")

    for i, m in enumerate(summary.matched, 1):
        content = m.scan_result.content
        scanner = m.scan_result.scanner_used
        print(f"  [OK] Box #{i:02d} -> {content}  ({scanner})")

    offset = len(summary.matched)
    for i, m in enumerate(summary.missing, offset + 1):
        bbox = m.box.bbox
        print(f"  [!!] Box #{i:02d} -> NO DATAMATRIX  (bbox={bbox}) - Please reposition the box!")

    missing_count = len(summary.missing)
    if missing_count:
        print(f"\n  {missing_count} box{'es' if missing_count != 1 else ''} need repositioning.")
    else:
        print(f"\n  All {total} boxes have DataMatrix codes.")


if __name__ == "__main__":
    main()
