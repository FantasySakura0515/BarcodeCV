from __future__ import annotations

from dataclasses import dataclass
import logging
import time

import cv2
import numpy as np

from ..decoding.direct_scanner import CompositeScanner
from ..utils.image_utils import crop_region

logger = logging.getLogger("barcodecv.opencv_datamatrix")


def _build_fast_scanner_with_dynamsoft(config: dict, detector_cfg: dict):
	"""Try to build a Dynamsoft-based scanner for fast mode. Returns None if unavailable."""
	dynamo_cfg = config.get("dynamsoft", {})
	if dynamo_cfg.get("enabled", True) is False:
		return None
	try:
		from ..decoding.direct_scanner import DynamsoftScanner, CompositeScanner, ZxingScanner
		license_key = dynamo_cfg.get("license_key", "DLS2eyJvcmdhbml6YXRpb25JRCI6IjIwMDAwMSJ9")
		template = dynamo_cfg.get("fast_template", "speed_first")
		dynamsoft = DynamsoftScanner(license_key=license_key, template=template)
		# Use zxing as fallback in case Dynamsoft misses something
		zxing = ZxingScanner(try_harder=False)
		scanner = CompositeScanner(primary=dynamsoft, fallback=zxing, merge_results=True)
		logger.info("Fast detector using Dynamsoft + zxing fallback")
		return scanner
	except Exception as exc:
		logger.info("Dynamsoft unavailable for fast mode, falling back to zxing+pylibdmtx: %s", exc)
		return None


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

		# Time budget: fast mode gets 5s, batch mode gets 30s.
		time_budget_s = 5.0 if self._max_roi_scan_variants <= 4 else 30.0

		for bbox in candidates:
			if (time.perf_counter() - start) > time_budget_s:
				logger.info("ROI scan time budget exceeded after %.0fms, stopping early", (time.perf_counter() - start) * 1000)
				break
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

	def decode_bboxes(
		self,
		image: np.ndarray,
		bboxes: list[tuple[int, int, int, int]],
	) -> list[OpenCVDataMatrixResult]:
		"""Decode only inside provided candidate boxes.

		Used by the live pipeline to avoid expensive full-frame scanning.
		Each input bbox is expanded by detector padding before ROI decode.
		"""
		results: list[OpenCVDataMatrixResult] = []
		for bbox in bboxes:
			x1, y1, x2, y2 = self._expand_bbox(bbox, image.shape)
			roi = crop_region(image, (x1, y1, x2, y2))
			if roi.size == 0:
				continue
			decoded = self._scan_roi_variants(roi)
			for item in decoded:
				if not item.success or not item.content:
					continue
				results.append(
					OpenCVDataMatrixResult(
						content=item.content,
						bbox=(
							x1 + int(item.bbox[0]),
							y1 + int(item.bbox[1]),
							x1 + int(item.bbox[2]),
							y1 + int(item.bbox[3]),
						),
						confidence=0.95,
						decoder_used=item.scanner_used,
						detection_source="provided-roi",
						scan_time_ms=item.scan_time_ms,
					)
				)
		return self._deduplicate(results)

	def _scan_roi_variants(self, roi: np.ndarray) -> list:
		"""Try progressively more aggressive preprocessing until a code is found.

		Variants are ordered by effectiveness. For small ROIs (distant codes),
		upscaled variants are prioritized since they are most impactful.
		`max_roi_scan_variants` caps how many variants are attempted.
		"""
		is_small = min(roi.shape[:2]) < 200

		if is_small:
			# Small ROI (distant code): upscale first — most impactful
			variants: list = [
				lambda: self._resize_variant(roi, scale=2.0),
				lambda: self._resize_variant(self._unsharp_mask(roi), scale=2.0),
				lambda: self._resize_variant(self._enhance_for_decode(roi), scale=2.0),
				lambda: roi,
				lambda: self._enhance_for_decode(roi),
				lambda: self._unsharp_mask(roi),
				lambda: self._invert_variant(roi),
				lambda: self._bilateral_variant(roi),
				lambda: self._morphological_sharpen(roi),
			]
		else:
			variants = [
				lambda: roi,
				lambda: self._enhance_for_decode(roi),
				lambda: self._unsharp_mask(roi),
				lambda: self._invert_variant(roi),
				lambda: self._bilateral_variant(roi),
				lambda: self._invert_variant(self._enhance_for_decode(roi)),
				lambda: self._morphological_sharpen(roi),
			]

		for variant_fn in variants[: self._max_roi_scan_variants]:
			decoded = self._scanner.scan(variant_fn())
			successful = [item for item in decoded if item.success and item.content]
			if successful:
				return successful
		return []

	def _scan_full_frame_variants(self, image: np.ndarray) -> list:
		"""Try multiple preprocessing variants on the full frame.

		Includes blur-resistant variants for distant/out-of-focus shots.
		"""
		all_variants = [
			lambda: image,
			lambda: self._enhance_for_decode(image),
			lambda: self._unsharp_mask(image),
			lambda: self._bilateral_variant(image),
			lambda: self._invert_variant(image),
			lambda: self._binary_variant(image),
			lambda: self._denoise_variant(image),
			lambda: self._morphological_sharpen(image),
			lambda: self._invert_variant(self._enhance_for_decode(image)),
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

	@staticmethod
	def _unsharp_mask(image: np.ndarray, sigma: float = 1.0, strength: float = 1.5) -> np.ndarray:
		"""Unsharp masking — effective against mild motion/focus blur."""
		gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY) if len(image.shape) == 3 else image.copy()
		blurred = cv2.GaussianBlur(gray, (0, 0), sigma)
		sharpened = cv2.addWeighted(gray, 1.0 + strength, blurred, -strength, 0)
		return cv2.cvtColor(sharpened, cv2.COLOR_GRAY2BGR)

	@staticmethod
	def _bilateral_variant(image: np.ndarray) -> np.ndarray:
		"""Bilateral filter — edge-preserving smoothing followed by CLAHE contrast."""
		filtered = cv2.bilateralFilter(image, d=9, sigmaColor=75, sigmaSpace=75)
		gray = cv2.cvtColor(filtered, cv2.COLOR_BGR2GRAY) if len(filtered.shape) == 3 else filtered.copy()
		clahe = cv2.createCLAHE(clipLimit=3.0, tileGridSize=(8, 8))
		enhanced = clahe.apply(gray)
		return cv2.cvtColor(enhanced, cv2.COLOR_GRAY2BGR)

	@staticmethod
	def _morphological_sharpen(image: np.ndarray) -> np.ndarray:
		"""Morphological sharpening — extracts edge detail from blurry images."""
		gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY) if len(image.shape) == 3 else image.copy()
		kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (3, 3))
		dilated = cv2.dilate(gray, kernel)
		eroded = cv2.erode(gray, kernel)
		edges = dilated - eroded
		sharpened = cv2.addWeighted(gray, 1.0, edges, 0.5, 0)
		clahe = cv2.createCLAHE(clipLimit=3.0, tileGridSize=(8, 8))
		sharpened = clahe.apply(sharpened)
		return cv2.cvtColor(sharpened, cv2.COLOR_GRAY2BGR)

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
		blurred = cv2.GaussianBlur(gray, (self._blur_kernel_size, self._blur_kernel_size), 0)
		clahe = cv2.createCLAHE(clipLimit=self._clahe_clip_limit, tileGridSize=(8, 8))
		enhanced = clahe.apply(blurred)

		# Run adaptive thresholding at multiple block sizes to catch
		# both fine-grained and coarser patterns (important for blurry images)
		block_sizes = [self._adaptive_block_size]
		for alt in [15, 51, 71]:
			if alt != self._adaptive_block_size:
				block_sizes.append(alt)

		kernel = cv2.getStructuringElement(
			cv2.MORPH_RECT,
			(self._morph_kernel_size, self._morph_kernel_size),
		)

		all_candidates: list[tuple[int, int, int, int]] = []

		# --- Path 1: adaptive threshold (works well on sharp images) ---
		for block_size in block_sizes:
			binary = cv2.adaptiveThreshold(
				enhanced,
				255,
				cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
				cv2.THRESH_BINARY,
				block_size,
				self._adaptive_c,
			)
			binary = cv2.bitwise_not(binary)
			morphed = cv2.morphologyEx(binary, cv2.MORPH_CLOSE, kernel, iterations=1)
			self._extract_contour_candidates(morphed, max_area, all_candidates)

		# --- Path 2: Canny edge detection (better for blurry/distant images) ---
		for low_t, high_t in [(30, 100), (50, 150)]:
			edges = cv2.Canny(enhanced, low_t, high_t)
			dilated = cv2.dilate(edges, kernel, iterations=2)
			self._extract_contour_candidates(dilated, max_area, all_candidates)

		# --- Path 3: Otsu on unsharp-masked image (handles uniform blur) ---
		unsharp = cv2.addWeighted(gray, 1.5, blurred, -0.5, 0)
		_, otsu_binary = cv2.threshold(unsharp, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
		otsu_binary = cv2.bitwise_not(otsu_binary)
		morphed_otsu = cv2.morphologyEx(otsu_binary, cv2.MORPH_CLOSE, kernel, iterations=1)
		self._extract_contour_candidates(morphed_otsu, max_area, all_candidates)

		all_candidates.sort(key=lambda item: (item[2] - item[0]) * (item[3] - item[1]), reverse=True)
		unique: list[tuple[int, int, int, int]] = []
		for bbox in all_candidates:
			if not any(self._iou(bbox, existing) > 0.5 for existing in unique):
				unique.append(bbox)
			if len(unique) >= self._max_candidates:
				break
		return unique

	def _extract_contour_candidates(
		self,
		binary: np.ndarray,
		max_area: int,
		output: list[tuple[int, int, int, int]],
	) -> None:
		"""Extract square-like contour bounding boxes from a binary image."""
		contours, _ = cv2.findContours(binary, cv2.RETR_LIST, cv2.CHAIN_APPROX_SIMPLE)
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

			fill_ratio = area / float(w * h)
			if fill_ratio < 0.15:
				continue

			output.append((x, y, x + w, y + h))

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
			# Try Dynamsoft first — it handles detection+decoding in a single
			# optimized pass and is far more accurate at distance/blur.
			scanner = _build_fast_scanner_with_dynamsoft(config, detector_cfg)
			if scanner is not None:
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
					padding=detector_cfg.get("padding", 30),
					max_candidates=0,
					clahe_clip_limit=detector_cfg.get("clahe_clip_limit", 3.0),
					fallback_full_image=True,
					max_roi_scan_variants=1,
					max_full_frame_scan_variants=1,
				)

			# Fallback: zxing + pylibdmtx when Dynamsoft is unavailable
			dec_cfg = config.get("decoding", {})
			dmtx_cfg = dec_cfg.get("pylibdmtx", {})
			fast_timeout = min(dmtx_cfg.get("fast_timeout_ms", 1200), 1500)
			pylibdmtx = PylibdmtxScanner(
				timeout_ms=fast_timeout,
				max_count=5,
				shrink=max(dmtx_cfg.get("shrink", 1), 1),
				threshold=dmtx_cfg.get("threshold", 50),
				min_edge=dmtx_cfg.get("min_edge", 8),
				max_edge=dmtx_cfg.get("max_edge", 200),
			)
			zxing = ZxingScanner(try_harder=True)
			scanner = CompositeScanner(primary=zxing, fallback=pylibdmtx, merge_results=False)
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
				padding=detector_cfg.get("padding", 30),
				max_candidates=60,
				clahe_clip_limit=detector_cfg.get("clahe_clip_limit", 3.0),
				fallback_full_image=True,
				max_roi_scan_variants=4,
				max_full_frame_scan_variants=3,
			)

		# Full-quality scanner for batch/capture mode
		# Try Dynamsoft (read_rate_first for max accuracy) with pylibdmtx+zxing merge
		dynamo_cfg = config.get("dynamsoft", {})
		dec_cfg = config.get("decoding", {})
		dmtx_cfg = dec_cfg.get("pylibdmtx", {})
		merge = dec_cfg.get("merge_results", True)

		try:
			if dynamo_cfg.get("enabled", True) is not False:
				from ..decoding.direct_scanner import DynamsoftScanner
				license_key = dynamo_cfg.get("license_key", "DLS2eyJvcmdhbml6YXRpb25JRCI6IjIwMDAwMSJ9")
				batch_template = dynamo_cfg.get("batch_template", "read_rate_first")
				dynamsoft = DynamsoftScanner(license_key=license_key, template=batch_template)
				zxing = ZxingScanner(try_harder=True)
				scanner = CompositeScanner(primary=dynamsoft, fallback=zxing, merge_results=True)
				logger.info("Batch detector using Dynamsoft (read_rate_first) + zxing merge")
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
					max_roi_scan_variants=2,
					max_full_frame_scan_variants=2,
				)
		except Exception as exc:
			logger.info("Dynamsoft unavailable for batch mode: %s", exc)

		# Fallback: pylibdmtx + zxing
		pylibdmtx = PylibdmtxScanner(
			timeout_ms=dmtx_cfg.get("timeout_ms", 5000),
			max_count=dmtx_cfg.get("max_count"),
			shrink=dmtx_cfg.get("shrink", 1),
			threshold=dmtx_cfg.get("threshold", 50),
			min_edge=dmtx_cfg.get("min_edge", 8),
			max_edge=dmtx_cfg.get("max_edge", 200),
		)
		zxing = ZxingScanner(try_harder=True)
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
			max_roi_scan_variants=6,
			max_full_frame_scan_variants=6,
		)
