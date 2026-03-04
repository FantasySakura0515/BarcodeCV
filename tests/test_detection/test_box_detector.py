"""Unit tests for BoxDetector using synthetic images."""

import numpy as np
import pytest

from src.detection.box_detector import BoxDetector, BoxDetectionResult


def _make_blank(h: int = 480, w: int = 640) -> np.ndarray:
    """Return a black BGR image."""
    return np.zeros((h, w, 3), dtype=np.uint8)


def _draw_rect(img: np.ndarray, x1: int, y1: int, x2: int, y2: int, color=(255, 255, 255), thickness: int = 3) -> None:
    """Draw a filled white rectangle (simulating a box edge)."""
    import cv2
    cv2.rectangle(img, (x1, y1), (x2, y2), color, thickness)


class TestBoxDetector:
    def setup_method(self):
        self.detector = BoxDetector(
            min_area=2000,
            max_area=200000,
            canny_threshold1=30,
            canny_threshold2=100,
            morph_kernel_size=3,
            approx_epsilon=0.04,
            aspect_ratio_min=0.2,
            aspect_ratio_max=5.0,
        )

    def test_detects_single_rectangle(self):
        img = _make_blank()
        _draw_rect(img, 100, 80, 300, 240)
        results = self.detector.detect(img)
        assert len(results) == 1
        r = results[0]
        assert isinstance(r, BoxDetectionResult)
        # Bbox should roughly match the drawn rectangle
        x1, y1, x2, y2 = r.bbox
        assert abs(x1 - 100) < 10
        assert abs(y1 - 80) < 10
        assert abs(x2 - 300) < 10
        assert abs(y2 - 240) < 10

    def test_detects_multiple_rectangles(self):
        img = _make_blank()
        _draw_rect(img, 50, 50, 180, 160)
        _draw_rect(img, 300, 50, 430, 160)
        _draw_rect(img, 50, 280, 180, 390)
        results = self.detector.detect(img)
        assert len(results) == 3

    def test_empty_image_returns_no_results(self):
        img = _make_blank()
        results = self.detector.detect(img)
        assert results == []

    def test_too_small_contour_filtered(self):
        """A tiny rectangle below min_area threshold should be ignored."""
        img = _make_blank()
        _draw_rect(img, 100, 100, 110, 110)  # 10x10 = 100 px² < 2000
        results = self.detector.detect(img)
        assert results == []

    def test_area_stored_in_result(self):
        img = _make_blank()
        _draw_rect(img, 100, 80, 300, 240)
        results = self.detector.detect(img)
        assert len(results) == 1
        assert results[0].area > 0

    def test_from_config_defaults(self):
        detector = BoxDetector.from_config({})
        assert detector._min_area == 5000
        assert detector._max_area == 500000
        assert detector._canny_t1 == 50

    def test_from_config_custom(self):
        cfg = {
            "box_detection": {
                "min_area": 1000,
                "max_area": 100000,
                "canny_threshold1": 20,
                "canny_threshold2": 80,
            }
        }
        detector = BoxDetector.from_config(cfg)
        assert detector._min_area == 1000
        assert detector._canny_t1 == 20

    def test_draw_detections_returns_image(self):
        img = _make_blank()
        _draw_rect(img, 100, 80, 300, 240)
        results = self.detector.detect(img)
        vis = self.detector.draw_detections(img, results)
        assert vis.shape == img.shape
        assert not np.array_equal(vis, _make_blank())  # Something was drawn

    def test_accepts_grayscale_input(self):
        img = np.zeros((480, 640), dtype=np.uint8)
        import cv2
        cv2.rectangle(img, (100, 80), (300, 240), 255, 3)
        results = self.detector.detect(img)
        assert len(results) == 1
