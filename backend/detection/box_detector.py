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
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY) if len(image.shape) == 3 else image
        gray = self._ensure_odd_blur(gray)

        clahe = cv2.createCLAHE(clipLimit=2.5, tileGridSize=(8, 8))
        enhanced = clahe.apply(gray)
        bilateral = cv2.bilateralFilter(enhanced, d=9, sigmaColor=75, sigmaSpace=75)

        kernel = cv2.getStructuringElement(
            cv2.MORPH_RECT, (self._morph_ksize, self._morph_ksize)
        )

        masks: list[np.ndarray] = []

        # Path 1: classic Canny on CLAHE-enhanced image
        edges = cv2.Canny(enhanced, self._canny_t1, self._canny_t2)
        masks.append(cv2.dilate(edges, kernel, iterations=2))

        # Path 2: lower-threshold Canny on bilateral-filtered image for blurry edges
        edges_soft = cv2.Canny(bilateral, max(10, int(self._canny_t1 * 0.6)), max(30, int(self._canny_t2 * 0.75)))
        masks.append(cv2.dilate(edges_soft, kernel, iterations=2))

        # Path 3: adaptive threshold for low-contrast / uneven lighting scenes
        adaptive = cv2.adaptiveThreshold(
            bilateral,
            255,
            cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
            cv2.THRESH_BINARY,
            31,
            5,
        )
        adaptive = cv2.bitwise_not(adaptive)
        masks.append(cv2.morphologyEx(adaptive, cv2.MORPH_CLOSE, kernel, iterations=2))

        # Path 4: Otsu threshold on sharpened image
        sharpened = cv2.addWeighted(enhanced, 1.4, cv2.GaussianBlur(enhanced, (0, 0), 1.0), -0.4, 0)
        _, otsu = cv2.threshold(sharpened, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        otsu = cv2.bitwise_not(otsu)
        masks.append(cv2.morphologyEx(otsu, cv2.MORPH_CLOSE, kernel, iterations=2))

        results: list[BoxDetectionResult] = []
        for mask in masks:
            contours, _ = cv2.findContours(mask, cv2.RETR_LIST, cv2.CHAIN_APPROX_SIMPLE)
            for contour in contours:
                result = self._contour_to_result(contour)
                if result is not None:
                    results.append(result)

        deduped = self._deduplicate(results)
        logger.info("Detected %d boxes (%d raw candidates)", len(deduped), len(results))
        return deduped

    def _contour_to_result(self, contour: np.ndarray) -> BoxDetectionResult | None:
        area = cv2.contourArea(contour)
        if area < self._min_area or area > self._max_area:
            return None

        peri = cv2.arcLength(contour, True)
        if peri <= 0:
            return None

        approx = cv2.approxPolyDP(contour, self._approx_eps * peri, True)
        if len(approx) < 4 or len(approx) > 10:
            return None

        rect = cv2.minAreaRect(contour)
        rw, rh = rect[1]
        if rw <= 0 or rh <= 0:
            return None

        ratio = max(rw, rh) / max(1.0, min(rw, rh))
        if ratio < self._ar_min or ratio > self._ar_max:
            return None

        box = cv2.boxPoints(rect)
        box = np.int32(box)
        x, y, w, h = cv2.boundingRect(box)
        if w <= 0 or h <= 0:
            return None

        rect_area = float(w * h)
        fill_ratio = area / rect_area if rect_area > 0 else 0.0
        if fill_ratio < 0.45:
            return None

        hull = cv2.convexHull(contour)
        hull_area = cv2.contourArea(hull)
        solidity = area / hull_area if hull_area > 0 else 0.0
        if solidity < 0.75:
            return None

        return BoxDetectionResult(
            bbox=(x, y, x + w, y + h),
            area=area,
            contour=contour,
        )

    def _deduplicate(self, results: list[BoxDetectionResult]) -> list[BoxDetectionResult]:
        deduped: list[BoxDetectionResult] = []
        for item in sorted(results, key=lambda r: r.area, reverse=True):
            if any(self._iou(item.bbox, existing.bbox) > 0.5 for existing in deduped):
                continue
            deduped.append(item)
        return deduped

    def _ensure_odd_blur(self, gray: np.ndarray) -> np.ndarray:
        k = self._blur_ksize if self._blur_ksize % 2 == 1 else self._blur_ksize + 1
        return cv2.GaussianBlur(gray, (k, k), 0)

    @staticmethod
    def _iou(a: tuple[int, int, int, int], b: tuple[int, int, int, int]) -> float:
        ax1, ay1, ax2, ay2 = a
        bx1, by1, bx2, by2 = b
        ix1 = max(ax1, bx1)
        iy1 = max(ay1, by1)
        ix2 = min(ax2, bx2)
        iy2 = min(ay2, by2)
        iw = max(0, ix2 - ix1)
        ih = max(0, iy2 - iy1)
        inter = iw * ih
        area_a = max(0, ax2 - ax1) * max(0, ay2 - ay1)
        area_b = max(0, bx2 - bx1) * max(0, by2 - by1)
        union = area_a + area_b - inter
        return inter / union if union > 0 else 0.0

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
            approx_epsilon=cfg.get("approx_epsilon", 0.02),
            aspect_ratio_min=cfg.get("aspect_ratio_min", 0.3),
            aspect_ratio_max=cfg.get("aspect_ratio_max", 3.0),
            blur_kernel_size=cfg.get("blur_kernel_size", 5),
        )
