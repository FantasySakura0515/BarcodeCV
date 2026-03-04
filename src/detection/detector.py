import logging
import time
from dataclasses import dataclass

import numpy as np

from ..camera.base import Frame

logger = logging.getLogger("barcodecv.detection")


@dataclass
class DetectionResult:
    """A single detected DataMatrix bounding box."""

    bbox: tuple[int, int, int, int]  # (x1, y1, x2, y2) in pixels
    confidence: float
    class_name: str


class DataMatrixDetector:
    """YOLO-based DataMatrix detector."""

    def __init__(
        self,
        model_path: str,
        confidence_threshold: float = 0.5,
        iou_threshold: float = 0.45,
        device: str = "cpu",
        imgsz: int = 640,
        max_detections: int = 50,
    ):
        self._model_path = model_path
        self._conf_thresh = confidence_threshold
        self._iou_thresh = iou_threshold
        self._device = device
        self._imgsz = imgsz
        self._max_detections = max_detections
        self._model = None

    def load_model(self) -> None:
        """Load the YOLO model."""
        from ultralytics import YOLO

        self._model = YOLO(self._model_path)
        logger.info("Loaded YOLO model from %s", self._model_path)

    def detect(self, frame: Frame) -> list[DetectionResult]:
        """Run detection on a frame, returning DataMatrix bounding boxes."""
        if self._model is None:
            raise RuntimeError("Model not loaded. Call load_model() first.")

        start = time.perf_counter()
        results = self._model(
            frame.image,
            conf=self._conf_thresh,
            iou=self._iou_thresh,
            imgsz=self._imgsz,
            device=self._device,
            max_det=self._max_detections,
            verbose=False,
        )
        elapsed_ms = (time.perf_counter() - start) * 1000

        detections = []
        for result in results:
            boxes = result.boxes
            if boxes is None:
                continue
            for box in boxes:
                xyxy = box.xyxy[0].cpu().numpy().astype(int)
                conf = float(box.conf[0].cpu().numpy())
                cls_id = int(box.cls[0].cpu().numpy())
                cls_name = result.names.get(cls_id, "datamatrix")

                detections.append(
                    DetectionResult(
                        bbox=(int(xyxy[0]), int(xyxy[1]), int(xyxy[2]), int(xyxy[3])),
                        confidence=conf,
                        class_name=cls_name,
                    )
                )

        logger.info(
            "Detected %d DataMatrix codes in %.1fms", len(detections), elapsed_ms
        )
        return detections

    @staticmethod
    def from_config(config: dict) -> "DataMatrixDetector":
        """Create detector from config dict."""
        det_cfg = config["detection"]
        detector = DataMatrixDetector(
            model_path=det_cfg["model_path"],
            confidence_threshold=det_cfg["confidence_threshold"],
            iou_threshold=det_cfg["iou_threshold"],
            device=det_cfg["device"],
            imgsz=det_cfg["imgsz"],
            max_detections=det_cfg["max_detections"],
        )
        return detector
