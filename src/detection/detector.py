import logging
import time
from dataclasses import dataclass

import numpy as np

logger = logging.getLogger("barcodecv.detection")


@dataclass
class DetectionResult:
    """A single detected object bounding box."""

    bbox: tuple[int, int, int, int]  # (x1, y1, x2, y2) in pixels
    confidence: float
    class_name: str  # "box" or "datamatrix"


class YOLODetector:
    """YOLO-based detector for boxes and DataMatrix codes.

    Classes:
        0: box        — rectangular package on the surface
        1: datamatrix — DataMatrix code on top of a box
    """

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
        from ultralytics import YOLO
        self._model = YOLO(self._model_path)
        logger.info("Loaded YOLO model from %s", self._model_path)

    def detect(self, image: np.ndarray) -> list[DetectionResult]:
        """Run detection on an image, returning all detected objects."""
        if self._model is None:
            raise RuntimeError("Model not loaded. Call load_model() first.")

        start = time.perf_counter()
        results = self._model(
            image,
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
                cls_name = result.names.get(cls_id, "unknown")

                detections.append(
                    DetectionResult(
                        bbox=(int(xyxy[0]), int(xyxy[1]), int(xyxy[2]), int(xyxy[3])),
                        confidence=conf,
                        class_name=cls_name,
                    )
                )

        n_boxes = sum(1 for d in detections if d.class_name == "box")
        n_dm = sum(1 for d in detections if d.class_name == "datamatrix")
        logger.info("YOLO: %d boxes + %d datamatrix in %.1fms", n_boxes, n_dm, elapsed_ms)
        return detections

    def detect_boxes(self, image: np.ndarray) -> list[DetectionResult]:
        return [d for d in self.detect(image) if d.class_name == "box"]

    def detect_datamatrix(self, image: np.ndarray) -> list[DetectionResult]:
        return [d for d in self.detect(image) if d.class_name == "datamatrix"]

    @staticmethod
    def from_config(config: dict) -> "YOLODetector":
        det_cfg = config.get("detection", {})
        detector = YOLODetector(
            model_path=det_cfg.get("model_path", "models/best.pt"),
            confidence_threshold=det_cfg.get("confidence_threshold", 0.5),
            iou_threshold=det_cfg.get("iou_threshold", 0.45),
            device=det_cfg.get("device", "cpu"),
            imgsz=det_cfg.get("imgsz", 640),
            max_detections=det_cfg.get("max_detections", 50),
        )
        return detector
