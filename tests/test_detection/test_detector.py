from datetime import datetime
from unittest.mock import MagicMock, patch

import numpy as np
import pytest

from src.camera.base import Frame
from src.detection.detector import DataMatrixDetector


class TestDataMatrixDetector:
    def test_from_config(self):
        config = {
            "detection": {
                "model_path": "test_model.pt",
                "confidence_threshold": 0.6,
                "iou_threshold": 0.5,
                "device": "cpu",
                "imgsz": 640,
                "max_detections": 30,
            }
        }
        detector = DataMatrixDetector.from_config(config)
        assert detector._model_path == "test_model.pt"
        assert detector._conf_thresh == 0.6
        assert detector._max_detections == 30

    def test_detect_raises_without_model(self):
        detector = DataMatrixDetector(model_path="test.pt")
        frame = Frame(
            image=np.zeros((640, 640, 3), dtype=np.uint8),
            timestamp=datetime.now(),
            camera_id="test",
            resolution=(640, 640),
        )
        with pytest.raises(RuntimeError, match="Model not loaded"):
            detector.detect(frame)
