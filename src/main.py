"""BarcodeCV - Dual-camera DataMatrix scanner for Raspberry Pi 5.

Usage:
    python -m src.main --mode single                    # One-shot scan
    python -m src.main --mode continuous                # Continuous scanning
    python -m src.main --mode preview                   # Live dual-camera display
    python -m src.main --mode tuning                    # Tune BoxDetector params with sliders
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
from .detection.detector import YOLODetector
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
        choices=["single", "continuous", "preview", "tuning", "calibration"],
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
    elif mode == "preview":
        _run_preview(config)
    elif mode == "tuning":
        _run_tuning(config)
    elif mode in ("single", "continuous"):
        _run_scanning(config, mode)
    else:
        logger.error("Unknown mode: %s", mode)
        sys.exit(1)


def _run_preview(config: dict):
    """Live dual-camera preview with box/DataMatrix overlay. Press 'q' to quit."""
    import logging

    import cv2

    logger = logging.getLogger("barcodecv")

    camera_manager = CameraManager.from_config(config)

    # Load YOLO if available
    det_cfg = config.get("detection", {})
    yolo_enabled = det_cfg.get("enabled", False)
    yolo = None
    if yolo_enabled:
        yolo = YOLODetector.from_config(config)
        yolo.load_model()
        logger.info("YOLO loaded for preview")

    # OpenCV box detection fallback
    box_cfg = config.get("box_detection", {})
    box_detector = None
    if not yolo_enabled and box_cfg.get("enabled", True):
        box_detector = BoxDetector.from_config(config)
        logger.info("OpenCV box detection loaded for preview")

    with camera_manager:
        logger.info("Preview started — press 'q' to quit, 's' to scan")

        while True:
            global_frame = camera_manager.capture_global()
            local_frame = camera_manager.capture_local()

            global_img = global_frame.image.copy()
            local_img = local_frame.image.copy()

            # YOLO overlay on global image
            if yolo is not None:
                detections = yolo.detect(global_frame.image)
                for det in detections:
                    x1, y1, x2, y2 = det.bbox
                    if det.class_name == "box":
                        color = (0, 255, 0)  # green
                        label = f"Box {det.confidence:.0%}"
                    else:
                        color = (255, 0, 0)  # blue
                        label = f"DM {det.confidence:.0%}"
                    cv2.rectangle(global_img, (x1, y1), (x2, y2), color, 2)
                    cv2.putText(global_img, label, (x1, y1 - 8),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 2)
            # OpenCV box detection overlay
            elif box_detector is not None:
                boxes = box_detector.detect(global_frame.image)
                for i, box in enumerate(boxes):
                    x1, y1, x2, y2 = box.bbox
                    cv2.rectangle(global_img, (x1, y1), (x2, y2), (0, 255, 0), 2)
                    cv2.putText(global_img, f"Box {i+1}", (x1, y1 - 8),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 2)

            # Labels
            cv2.putText(global_img, "Global (CAM0)", (10, 30),
                        cv2.FONT_HERSHEY_SIMPLEX, 1.0, (0, 255, 255), 2)
            cv2.putText(local_img, "Local (CAM1)", (10, 30),
                        cv2.FONT_HERSHEY_SIMPLEX, 1.0, (0, 255, 255), 2)

            # Resize both to same height for side-by-side display
            h = min(global_img.shape[0], local_img.shape[0], 540)
            g_w = int(global_img.shape[1] * h / global_img.shape[0])
            l_w = int(local_img.shape[1] * h / local_img.shape[0])
            global_resized = cv2.resize(global_img, (g_w, h))
            local_resized = cv2.resize(local_img, (l_w, h))

            combined = cv2.hconcat([global_resized, local_resized])
            cv2.imshow("BarcodeCV Preview", combined)

            key = cv2.waitKey(1) & 0xFF
            if key == ord("q"):
                break
            elif key == ord("s"):
                # One-shot scan
                logger.info("Scanning current frame...")
                scanner = CompositeScanner.from_config(config)
                results = scanner.scan(global_frame.image)
                successful = [r for r in results if r.success]

                for r in successful:
                    logger.info("  Found: %s (%s)", r.content, r.scanner_used)

                # Match with boxes if available
                if successful and box_detector:
                    boxes = box_detector.detect(global_frame.image)
                    if boxes:
                        matcher = SpatialMatcher.from_config(config)
                        matches = matcher.match(boxes, successful)
                        matched = [m for m in matches if m.status == "matched"]
                        missing = [m for m in matches if m.status != "matched"]
                        logger.info("  %d boxes matched, %d missing DataMatrix", len(matched), len(missing))
                        for m in missing:
                            logger.warning("  [!!] Box at %s has no DataMatrix", m.box.bbox)

                if not successful:
                    logger.info("  No DataMatrix found")

        cv2.destroyAllWindows()
        logger.info("Preview stopped")


def _run_tuning(config: dict):
    """Live parameter tuning for BoxDetector with trackbar sliders.

    Trackbars:
        Canny1, Canny2    — edge detection thresholds
        MinArea (x100)    — minimum contour area (displayed value * 100)
        MaxArea (x1000)   — maximum contour area (displayed value * 1000)
        BlurK             — Gaussian blur kernel size (forced odd)
        MorphK            — morphological dilation kernel size (forced odd)
        Epsilon (x0.001)  — contour approximation precision

    Keys:
        p — print current parameters (copy to config/default.yaml)
        s — one-shot DataMatrix scan with current parameters
        q — quit
    """
    import logging

    import cv2

    logger = logging.getLogger("barcodecv")
    camera_manager = CameraManager.from_config(config)

    box_cfg = config.get("box_detection", {})

    # Mutable state read by trackbar callbacks
    params = {
        "canny1": box_cfg.get("canny_threshold1", 50),
        "canny2": box_cfg.get("canny_threshold2", 150),
        "min_area": box_cfg.get("min_area", 5000),
        "max_area": box_cfg.get("max_area", 500000),
        "blur_k": box_cfg.get("blur_kernel_size", 5),
        "morph_k": box_cfg.get("morph_kernel_size", 5),
        "epsilon": box_cfg.get("approx_epsilon", 0.02),
        "ar_min": box_cfg.get("aspect_ratio_min", 0.3),
        "ar_max": box_cfg.get("aspect_ratio_max", 3.0),
    }

    win = "BarcodeCV Tuning"
    cv2.namedWindow(win, cv2.WINDOW_NORMAL)

    # Trackbar callbacks
    def _noop(_):
        pass

    cv2.createTrackbar("Canny1", win, params["canny1"], 300, _noop)
    cv2.createTrackbar("Canny2", win, params["canny2"], 300, _noop)
    cv2.createTrackbar("MinArea x100", win, params["min_area"] // 100, 500, _noop)
    cv2.createTrackbar("MaxArea x1000", win, params["max_area"] // 1000, 1000, _noop)
    cv2.createTrackbar("BlurK", win, params["blur_k"], 15, _noop)
    cv2.createTrackbar("MorphK", win, params["morph_k"], 15, _noop)
    cv2.createTrackbar("Epsilon x1000", win, int(params["epsilon"] * 1000), 100, _noop)

    def _read_params():
        blur_k = cv2.getTrackbarPos("BlurK", win)
        morph_k = cv2.getTrackbarPos("MorphK", win)
        # Force odd kernel sizes (minimum 1)
        blur_k = max(1, blur_k if blur_k % 2 == 1 else blur_k + 1)
        morph_k = max(1, morph_k if morph_k % 2 == 1 else morph_k + 1)
        eps_raw = cv2.getTrackbarPos("Epsilon x1000", win)
        return {
            "canny1": cv2.getTrackbarPos("Canny1", win),
            "canny2": cv2.getTrackbarPos("Canny2", win),
            "min_area": cv2.getTrackbarPos("MinArea x100", win) * 100,
            "max_area": cv2.getTrackbarPos("MaxArea x1000", win) * 1000,
            "blur_k": blur_k,
            "morph_k": morph_k,
            "epsilon": max(0.001, eps_raw / 1000.0),
        }

    with camera_manager:
        logger.info("Tuning mode — adjust sliders, press 'p' to print, 'q' to quit")

        while True:
            global_frame = camera_manager.capture_global()
            img = global_frame.image.copy()

            p = _read_params()
            detector = BoxDetector(
                min_area=p["min_area"],
                max_area=p["max_area"],
                canny_threshold1=p["canny1"],
                canny_threshold2=p["canny2"],
                morph_kernel_size=p["morph_k"],
                approx_epsilon=p["epsilon"],
                aspect_ratio_min=params["ar_min"],
                aspect_ratio_max=params["ar_max"],
                blur_kernel_size=p["blur_k"],
            )

            boxes = detector.detect(global_frame.image)

            # Draw detections
            for i, box in enumerate(boxes):
                x1, y1, x2, y2 = box.bbox
                cv2.rectangle(img, (x1, y1), (x2, y2), (0, 255, 0), 2)
                cv2.putText(img, f"Box {i+1} ({int(box.area)}px)",
                            (x1, y1 - 8), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 2)

            # Show info overlay
            info = (f"Boxes: {len(boxes)} | Canny: {p['canny1']}/{p['canny2']} | "
                    f"Area: {p['min_area']}-{p['max_area']} | "
                    f"Blur: {p['blur_k']} | Morph: {p['morph_k']} | Eps: {p['epsilon']:.3f}")
            cv2.putText(img, info, (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 255), 1)

            # Resize for display
            h = min(img.shape[0], 720)
            w = int(img.shape[1] * h / img.shape[0])
            img_resized = cv2.resize(img, (w, h))
            cv2.imshow(win, img_resized)

            key = cv2.waitKey(1) & 0xFF
            if key == ord("q"):
                break
            elif key == ord("p"):
                print("\n=== Current BoxDetector Parameters ===")
                print("box_detection:")
                print(f"  enabled: true")
                print(f"  min_area: {p['min_area']}")
                print(f"  max_area: {p['max_area']}")
                print(f"  canny_threshold1: {p['canny1']}")
                print(f"  canny_threshold2: {p['canny2']}")
                print(f"  morph_kernel_size: {p['morph_k']}")
                print(f"  approx_epsilon: {p['epsilon']:.3f}")
                print(f"  aspect_ratio_min: {params['ar_min']}")
                print(f"  aspect_ratio_max: {params['ar_max']}")
                print(f"  blur_kernel_size: {p['blur_k']}")
                print("======================================\n")
            elif key == ord("s"):
                logger.info("Scanning current frame...")
                scanner = CompositeScanner.from_config(config)
                results = scanner.scan(global_frame.image)
                successful = [r for r in results if r.success]
                for r in successful:
                    logger.info("  Found: %s (%s)", r.content, r.scanner_used)
                if successful and boxes:
                    matcher = SpatialMatcher.from_config(config)
                    matches = matcher.match(boxes, successful)
                    for m in matches:
                        if m.status == "matched":
                            logger.info("  [OK] Box -> %s", m.scan_result.content)
                        else:
                            logger.warning("  [!!] Box at %s has no DataMatrix", m.box.bbox)
                if not successful:
                    logger.info("  No DataMatrix found")

        cv2.destroyAllWindows()
        logger.info("Tuning stopped")


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

    # YOLO detection (optional — requires trained model)
    det_cfg = config.get("detection", {})
    yolo_enabled = det_cfg.get("enabled", False)
    yolo_detector = None
    if yolo_enabled:
        yolo_detector = YOLODetector.from_config(config)
        yolo_detector.load_model()
        logger.info("YOLO detection: enabled (%s)", det_cfg.get("model_path"))

    # OpenCV box detection (used when YOLO is disabled)
    box_cfg = config.get("box_detection", {})
    box_enabled = box_cfg.get("enabled", True)
    box_detector = None
    if not yolo_enabled and box_enabled:
        box_detector = BoxDetector.from_config(config)
        logger.info("OpenCV box detection: enabled")

    # Spatial matcher needed when either YOLO or box detection is active
    use_matching = yolo_enabled or (box_detector is not None)
    spatial_matcher = SpatialMatcher.from_config(config) if use_matching else None

    logger.info("Using scanner: %s", scanner.name())

    with camera_manager, db_manager:
        repo = ScanRepository(db_manager.get_connection())
        box_repo = BoxRepository(db_manager.get_connection()) if use_matching else None

        pipeline = ScanPipeline(
            camera_manager=camera_manager,
            scanner=scanner,
            repository=repo,
            config=config,
            yolo_detector=yolo_detector,
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
