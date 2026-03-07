from __future__ import annotations

from dataclasses import dataclass
import logging
import time

import cv2
import numpy as np

from ..decoding.direct_scanner import CompositeScanner
from ..utils.image_utils import crop_region

logger = logging.getLogger("barcodecv.opencv_datamatrix")


@dataclass
class OpenCVDataMatrixResult:
	content: str
	bbox: tuple[int, int, int, int]
	confidence: float
	decoder_used: str
	detection_source: str
	scan_time_ms: float


class OpenCVDataMatrixDetector:
	"""OpenCV-based DataMatrix candidate detector with decoder fallback.

	Strategy:
	1. Use OpenCV to find square-like, high-contrast candidates.
	2. Decode each candidate ROI using the composite scanner.
	3. Fallback to full-frame scanning to catch missed codes.
	4. Merge and deduplicate all successful detections.
	"""

	def __init__(
		self,
		scanner: CompositeScanner,
		min_area: int = 80,
		max_area_ratio: float = 0.2,
		adaptive_block_size: int = 31,
		adaptive_c: int = 8,
		morph_kernel_size: int = 3,
		blur_kernel_size: int = 5,
		aspect_ratio_min: float = 0.6,
		aspect_ratio_max: float = 1.4,
		padding: int = 12,
		max_candidates: int = 120,
		clahe_clip_limit: float = 2.0,
		fallback_full_image: bool = True,
		max_roi_scan_variants: int = 6,
		max_full_frame_scan_variants: int = 6,
	):
		self._scanner = scanner
		self._min_area = min_area
		self._max_area_ratio = max_area_ratio
		self._adaptive_block_size = adaptive_block_size if adaptive_block_size % 2 == 1 else adaptive_block_size + 1
		self._adaptive_c = adaptive_c
		self._morph_kernel_size = morph_kernel_size
		self._blur_kernel_size = blur_kernel_size if blur_kernel_size % 2 == 1 else blur_kernel_size + 1
		self._aspect_ratio_min = aspect_ratio_min
		self._aspect_ratio_max = aspect_ratio_max
		self._padding = padding
		self._max_candidates = max_candidates
		self._clahe_clip_limit = clahe_clip_limit
		self._fallback_full_image = fallback_full_image
		self._max_roi_scan_variants = max_roi_scan_variants
		self._max_full_frame_scan_variants = max_full_frame_scan_variants

	def detect_and_decode(self, image: np.ndarray) -> list[OpenCVDataMatrixResult]:
		start = time.perf_counter()
		h, w = image.shape[:2]
		max_area = max(int(h * w * self._max_area_ratio), self._min_area)

		candidates = self._detect_candidates(image, max_area=max_area)
		results: list[OpenCVDataMatrixResult] = []

		for bbox in candidates:
			x1, y1, x2, y2 = self._expand_bbox(bbox, image.shape)
			roi = crop_region(image, (x1, y1, x2, y2))
			decoded = self._scan_roi_variants(roi)
			for item in decoded:
				if not item.success or not item.content:
					continue
				global_bbox = (
					x1 + int(item.bbox[0]),
					y1 + int(item.bbox[1]),
					x1 + int(item.bbox[2]),
					y1 + int(item.bbox[3]),
				)
				results.append(
					OpenCVDataMatrixResult(
						content=item.content,
						bbox=global_bbox,
						confidence=0.95,
						decoder_used=item.scanner_used,
						detection_source="opencv-roi",
						scan_time_ms=item.scan_time_ms,
					)
				)

		if self._fallback_full_image and not results:
			decoded_full = self._scan_full_frame_variants(image)
			for item in decoded_full:
				if not item.success or not item.content:
					continue
				results.append(
					OpenCVDataMatrixResult(
						content=item.content,
						bbox=tuple(int(v) for v in item.bbox),
						confidence=0.88,
						decoder_used=item.scanner_used,
						detection_source="full-frame",
						scan_time_ms=item.scan_time_ms,
					)
				)

		merged = self._deduplicate(results)
		elapsed = (time.perf_counter() - start) * 1000
		logger.info(
			"OpenCV DataMatrix detector found %d codes from %d candidates in %.1fms",
			len(merged),
			len(candidates),
			elapsed,
		)
		return merged

	def _scan_roi_variants(self, roi: np.ndarray) -> list:
		"""Try progressively more aggressive preprocessing until a code is found.

		Variants are ordered cheapest-first. `max_roi_scan_variants` caps how
		many variants are attempted (use 1-2 for live/fast mode, 6 for batch).
		"""
		variants: list = [
			lambda: roi,
			lambda: self._enhance_for_decode(roi),
			lambda: self._invert_variant(roi),
			lambda: self._invert_variant(self._enhance_for_decode(roi)),
		]
		# Upscale variants — only useful if ROI is small
		if min(roi.shape[:2]) < 120:
			variants += [
				lambda: self._resize_variant(roi, scale=2.0),
				lambda: self._resize_variant(self._enhance_for_decode(roi), scale=2.0),
			]

		for variant_fn in variants[: self._max_roi_scan_variants]:
			decoded = self._scanner.scan(variant_fn())
			successful = [item for item in decoded if item.success and item.content]
			if successful:
				return successful
		return []

	def _scan_full_frame_variants(self, image: np.ndarray) -> list:
		"""Try multiple preprocessing variants on the full frame."""
		all_variants = [
			lambda: image,
			lambda: self._enhance_for_decode(image),
			lambda: self._invert_variant(image),
			lambda: self._binary_variant(image),
			lambda: self._invert_variant(self._enhance_for_decode(image)),
			lambda: self._denoise_variant(image),
		]
		for variant_fn in all_variants[: self._max_full_frame_scan_variants]:
			results = self._scanner.scan(variant_fn())
			successful = [item for item in results if item.success and item.content]
			if successful:
				return successful
		return []

	def _enhance_for_decode(self, image: np.ndarray) -> np.ndarray:
		gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY) if len(image.shape) == 3 else image.copy()
		clahe = cv2.createCLAHE(clipLimit=max(self._clahe_clip_limit, 3.0), tileGridSize=(8, 8))
		gray = clahe.apply(gray)
		sharpen_kernel = np.array([[0, -1, 0], [-1, 5, -1], [0, -1, 0]], dtype=np.float32)
		gray = cv2.filter2D(gray, -1, sharpen_kernel)
		return cv2.cvtColor(gray, cv2.COLOR_GRAY2BGR)

	@staticmethod
	def _invert_variant(image: np.ndarray) -> np.ndarray:
		"""Invert image — helps for light-on-dark DataMatrix codes."""
		return cv2.bitwise_not(image)

	@staticmethod
	def _denoise_variant(image: np.ndarray) -> np.ndarray:
		"""Apply non-local means denoising — helps for blurry/noisy images."""
		gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY) if len(image.shape) == 3 else image.copy()
		denoised = cv2.fastNlMeansDenoising(gray, h=10, templateWindowSize=7, searchWindowSize=21)
		return cv2.cvtColor(denoised, cv2.COLOR_GRAY2BGR)

	def _binary_variant(self, image: np.ndarray) -> np.ndarray:
		gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY) if len(image.shape) == 3 else image.copy()
		gray = cv2.GaussianBlur(gray, (3, 3), 0)
		binary = cv2.adaptiveThreshold(
			gray,
			255,
			cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
			cv2.THRESH_BINARY,
			31,
			5,
		)
		return cv2.cvtColor(binary, cv2.COLOR_GRAY2BGR)

	@staticmethod
	def _resize_variant(image: np.ndarray, scale: float) -> np.ndarray:
		height, width = image.shape[:2]
		new_width = max(1, int(width * scale))
		new_height = max(1, int(height * scale))
		return cv2.resize(image, (new_width, new_height), interpolation=cv2.INTER_CUBIC)

	def draw_detections(
		self, image: np.ndarray, results: list[OpenCVDataMatrixResult]
	) -> np.ndarray:
		output = image.copy()
		for index, result in enumerate(results, start=1):
			x1, y1, x2, y2 = result.bbox
			cv2.rectangle(output, (x1, y1), (x2, y2), (34, 197, 94), 2)
			label = f"DM#{index}: {result.content}"
			text_y = y1 - 10 if y1 > 24 else y1 + 22
			cv2.putText(
				output,
				label,
				(x1, text_y),
				cv2.FONT_HERSHEY_SIMPLEX,
				0.55,
				(34, 197, 94),
				2,
				cv2.LINE_AA,
			)
		return output

	def _detect_candidates(self, image: np.ndarray, max_area: int) -> list[tuple[int, int, int, int]]:
		gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY) if len(image.shape) == 3 else image.copy()
		gray = cv2.GaussianBlur(gray, (self._blur_kernel_size, self._blur_kernel_size), 0)
		clahe = cv2.createCLAHE(clipLimit=self._clahe_clip_limit, tileGridSize=(8, 8))
		gray = clahe.apply(gray)

		# Run adaptive thresholding at two different block sizes to catch
		# both fine-grained and coarser patterns
		block_sizes = [self._adaptive_block_size]
		alternative = 15 if self._adaptive_block_size > 15 else 51
		if alternative != self._adaptive_block_size:
			block_sizes.append(alternative)

		kernel = cv2.getStructuringElement(
			cv2.MORPH_RECT,
			(self._morph_kernel_size, self._morph_kernel_size),
		)

		all_candidates: list[tuple[int, int, int, int]] = []
		for block_size in block_sizes:
			binary = cv2.adaptiveThreshold(
				gray,
				255,
				cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
				cv2.THRESH_BINARY,
				block_size,
				self._adaptive_c,
			)
			binary = cv2.bitwise_not(binary)
			morphed = cv2.morphologyEx(binary, cv2.MORPH_CLOSE, kernel, iterations=1)

			contours, _ = cv2.findContours(morphed, cv2.RETR_LIST, cv2.CHAIN_APPROX_SIMPLE)
			for contour in contours:
				area = cv2.contourArea(contour)
				if area < self._min_area or area > max_area:
					continue

				rect = cv2.minAreaRect(contour)
				width, height = rect[1]
				if width <= 0 or height <= 0:
					continue

				ratio = width / height
				if ratio < self._aspect_ratio_min or ratio > self._aspect_ratio_max:
					continue

				box = cv2.boxPoints(rect)
				box = np.int32(box)
				x, y, w, h = cv2.boundingRect(box)
				if w <= 0 or h <= 0:
					continue

				# Relaxed fill_ratio (was 0.25) to avoid missing valid candidates
				fill_ratio = area / float(w * h)
				if fill_ratio < 0.15:
					continue

				all_candidates.append((x, y, x + w, y + h))

		all_candidates.sort(key=lambda item: (item[2] - item[0]) * (item[3] - item[1]), reverse=True)
		unique: list[tuple[int, int, int, int]] = []
		for bbox in all_candidates:
			if not any(self._iou(bbox, existing) > 0.5 for existing in unique):
				unique.append(bbox)
			if len(unique) >= self._max_candidates:
				break
		return unique

	def _expand_bbox(
		self,
		bbox: tuple[int, int, int, int],
		shape: tuple[int, ...],
	) -> tuple[int, int, int, int]:
		h, w = shape[:2]
		x1, y1, x2, y2 = bbox
		return (
			max(0, x1 - self._padding),
			max(0, y1 - self._padding),
			min(w, x2 + self._padding),
			min(h, y2 + self._padding),
		)

	def _deduplicate(
		self, results: list[OpenCVDataMatrixResult]
	) -> list[OpenCVDataMatrixResult]:
		deduped: list[OpenCVDataMatrixResult] = []
		for result in sorted(results, key=lambda item: item.confidence, reverse=True):
			exists = False
			for existing in deduped:
				same_content = existing.content == result.content
				overlap = self._iou(existing.bbox, result.bbox) > 0.35
				if same_content or overlap:
					exists = True
					break
			if not exists:
				deduped.append(result)
		return deduped

	@staticmethod
	def _iou(a: tuple[int, int, int, int], b: tuple[int, int, int, int]) -> float:
		ax1, ay1, ax2, ay2 = a
		bx1, by1, bx2, by2 = b
		inter_x1 = max(ax1, bx1)
		inter_y1 = max(ay1, by1)
		inter_x2 = min(ax2, bx2)
		inter_y2 = min(ay2, by2)
		inter_w = max(0, inter_x2 - inter_x1)
		inter_h = max(0, inter_y2 - inter_y1)
		inter_area = inter_w * inter_h
		area_a = max(0, ax2 - ax1) * max(0, ay2 - ay1)
		area_b = max(0, bx2 - bx1) * max(0, by2 - by1)
		union = area_a + area_b - inter_area
		return inter_area / union if union else 0.0

	@staticmethod
	def from_config(config: dict, fast: bool = False) -> "OpenCVDataMatrixDetector":
		from ..decoding.direct_scanner import CompositeScanner, PylibdmtxScanner, ZxingScanner

		detector_cfg = config.get("opencv_datamatrix", {})

		if fast:
			# Build a fast scanner for live preview — balanced between speed and accuracy.
			dec_cfg = config.get("decoding", {})
			dmtx_cfg = dec_cfg.get("pylibdmtx", {})
			# Use config timeout or a generous default; 100ms was too tight on Pi.
			fast_timeout = dmtx_cfg.get("fast_timeout_ms", dmtx_cfg.get("timeout_ms", 2000))
			pylibdmtx = PylibdmtxScanner(
				timeout_ms=fast_timeout,
				max_count=dmtx_cfg.get("max_count"),
				shrink=max(dmtx_cfg.get("shrink", 1), 1),
				threshold=dmtx_cfg.get("threshold", 50),
				min_edge=dmtx_cfg.get("min_edge", 8),
				max_edge=dmtx_cfg.get("max_edge", 200),
			)
			zxing = ZxingScanner(try_harder=False)  # speed priority in live mode
			# merge_results=False: only run zxing if pylibdmtx found nothing
			scanner = CompositeScanner(primary=pylibdmtx, fallback=zxing, merge_results=False)
			return OpenCVDataMatrixDetector(
				scanner=scanner,
				min_area=detector_cfg.get("min_area", 60),
				max_area_ratio=detector_cfg.get("max_area_ratio", 0.3),
				adaptive_block_size=detector_cfg.get("adaptive_block_size", 31),
				adaptive_c=detector_cfg.get("adaptive_c", 8),
				morph_kernel_size=detector_cfg.get("morph_kernel_size", 3),
				blur_kernel_size=detector_cfg.get("blur_kernel_size", 5),
				aspect_ratio_min=detector_cfg.get("aspect_ratio_min", 0.5),
				aspect_ratio_max=detector_cfg.get("aspect_ratio_max", 2.0),
				padding=detector_cfg.get("padding", 20),
				max_candidates=detector_cfg.get("max_candidates", 120),
				clahe_clip_limit=detector_cfg.get("clahe_clip_limit", 3.0),
				fallback_full_image=True,
				max_roi_scan_variants=3,        # original + enhanced + inverted
				max_full_frame_scan_variants=4, # original + enhanced + inverted + binary
			)

		# Full-quality scanner for batch/capture mode
		dec_cfg = config.get("decoding", {})
		dmtx_cfg = dec_cfg.get("pylibdmtx", {})
		pylibdmtx = PylibdmtxScanner(
			timeout_ms=dmtx_cfg.get("timeout_ms", 5000),
			max_count=dmtx_cfg.get("max_count"),
			shrink=dmtx_cfg.get("shrink", 1),
			threshold=dmtx_cfg.get("threshold", 50),
			min_edge=dmtx_cfg.get("min_edge", 8),
			max_edge=dmtx_cfg.get("max_edge", 200),
		)
		zxing = ZxingScanner(try_harder=True)
		merge = dec_cfg.get("merge_results", True)
		scanner = CompositeScanner(primary=pylibdmtx, fallback=zxing, merge_results=merge)
		return OpenCVDataMatrixDetector(
			scanner=scanner,
			min_area=detector_cfg.get("min_area", 60),
			max_area_ratio=detector_cfg.get("max_area_ratio", 0.3),
			adaptive_block_size=detector_cfg.get("adaptive_block_size", 31),
			adaptive_c=detector_cfg.get("adaptive_c", 8),
			morph_kernel_size=detector_cfg.get("morph_kernel_size", 3),
			blur_kernel_size=detector_cfg.get("blur_kernel_size", 5),
			aspect_ratio_min=detector_cfg.get("aspect_ratio_min", 0.5),
			aspect_ratio_max=detector_cfg.get("aspect_ratio_max", 2.0),
			padding=detector_cfg.get("padding", 20),
			max_candidates=detector_cfg.get("max_candidates", 120),
			clahe_clip_limit=detector_cfg.get("clahe_clip_limit", 3.0),
			fallback_full_image=detector_cfg.get("fallback_full_image", True),
			max_roi_scan_variants=6,          # try all preprocessing variants
			max_full_frame_scan_variants=6,   # try all full-frame fallback variants
		)
