"""OpenCV contour-based box detection.

Detects uniformly-shaped boxes on a flat surface using edge detection
and contour approximation. No ML model required — works by finding
rectangular contours that match expected box dimensions.
"""

import logging
from dataclasses import dataclass, field

import cv2
import numpy as np

logger = logging.getLogger("barcodecv.box_detector")


@dataclass
class BoxDetectionResult:
    """A single detected box on the surface."""

    bbox: tuple[int, int, int, int]  # (x1, y1, x2, y2)
    area: float
    contour: np.ndarray = field(repr=False)


class BoxDetector:
    """Detect boxes on a flat surface using OpenCV contour analysis.

    Tuning guide (adjust via config):
    - If too many false positives: increase min_area, tighten aspect_ratio range
    - If boxes are missed: lower canny_threshold1, increase morph_kernel_size
    - If edges are noisy: increase blur_kernel_size
    """

    def __init__(
        self,
        min_area: float = 5000,
        max_area: float = 500000,
        canny_threshold1: float = 50,
        canny_threshold2: float = 150,
        morph_kernel_size: int = 5,
        approx_epsilon: float = 0.02,
        aspect_ratio_min: float = 0.3,
        aspect_ratio_max: float = 3.0,
        blur_kernel_size: int = 5,
    ):
        self._min_area = min_area
        self._max_area = max_area
        self._canny_t1 = canny_threshold1
        self._canny_t2 = canny_threshold2
        self._morph_ksize = morph_kernel_size
        self._approx_eps = approx_epsilon
        self._ar_min = aspect_ratio_min
        self._ar_max = aspect_ratio_max
        self._blur_ksize = blur_kernel_size

    def detect(self, image: np.ndarray) -> list[BoxDetectionResult]:
        """Detect boxes in the image. Returns list of BoxDetectionResult."""
        # 1. Greyscale + blur
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY) if len(image.shape) == 3 else image
        blurred = cv2.GaussianBlur(gray, (self._blur_ksize, self._blur_ksize), 0)

        # 2. Canny edge detection
        edges = cv2.Canny(blurred, self._canny_t1, self._canny_t2)

        # 3. Morphological dilation to connect broken edges
        kernel = cv2.getStructuringElement(
            cv2.MORPH_RECT, (self._morph_ksize, self._morph_ksize)
        )
        dilated = cv2.dilate(edges, kernel, iterations=1)

        # 4. Find external contours
        contours, _ = cv2.findContours(
            dilated, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE
        )

        results = []
        for contour in contours:
            area = cv2.contourArea(contour)

            # Filter by area
            if area < self._min_area or area > self._max_area:
                continue

            # Approximate contour to polygon
            peri = cv2.arcLength(contour, True)
            approx = cv2.approxPolyDP(contour, self._approx_eps * peri, True)

            # Keep only roughly rectangular shapes (4 corners)
            if len(approx) != 4:
                continue

            # Bounding box
            x, y, w, h = cv2.boundingRect(approx)

            # Filter by aspect ratio
            if h == 0:
                continue
            ar = w / h
            if ar < self._ar_min or ar > self._ar_max:
                continue

            results.append(
                BoxDetectionResult(
                    bbox=(x, y, x + w, y + h),
                    area=area,
                    contour=contour,
                )
            )

        logger.info("Detected %d boxes", len(results))
        return results

    def draw_detections(
        self, image: np.ndarray, results: list[BoxDetectionResult]
    ) -> np.ndarray:
        """Draw detected box bounding boxes on the image for debugging."""
        vis = image.copy()
        for i, r in enumerate(results):
            x1, y1, x2, y2 = r.bbox
            cv2.rectangle(vis, (x1, y1), (x2, y2), (0, 255, 0), 2)
            cv2.putText(
                vis,
                f"Box {i + 1}",
                (x1, y1 - 8),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.6,
                (0, 255, 0),
                2,
            )
        return vis

    @staticmethod
    def from_config(config: dict) -> "BoxDetector":
        """Create BoxDetector from YAML config dict."""
        cfg = config.get("box_detection", {})
        return BoxDetector(
            min_area=cfg.get("min_area", 5000),
            max_area=cfg.get("max_area", 500000),
            canny_threshold1=cfg.get("canny_threshold1", 50),
            canny_threshold2=cfg.get("canny_threshold2", 150),
            morph_kernel_size=cfg.get("morph_kernel_size", 5),
            blur_kernel_size=cfg.get("blur_kernel_size", 5),
            approx_epsilon=cfg.get("approx_epsilon", 0.02),
            aspect_ratio_min=cfg.get("aspect_ratio_min", 0.3),
            aspect_ratio_max=cfg.get("aspect_ratio_max", 3.0),
        )
