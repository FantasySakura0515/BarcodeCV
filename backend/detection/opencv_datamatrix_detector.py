from __future__ import annotations

from dataclasses import dataclass
import logging
import os
import threading
import time
from concurrent.futures import Future, ThreadPoolExecutor, as_completed

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
		# When True (accuracy mode): full-frame scan is ALWAYS run and its results
		# supplement any codes already found by ROI scanning.
		# When False (speed mode): full-frame only runs when ROI found NOTHING.
		full_frame_always_supplement: bool = False,
		# Stop scanning candidates once this many codes are found (0 = no limit).
		# Set to expected barcode count for fast early exit.
		early_exit_count: int = 0,
		# Use fewer candidate-detection passes (fast mode: 1 path vs 7 paths).
		fast_candidate_detection: bool = False,
		# Number of threads for parallel ROI scanning.  0 = sequential.
		# zxing-cpp releases the GIL so threads run in true parallel on multi-core.
		# Recommended: min(4, cpu_count) for live mode; 0 for batch mode.
		parallel_workers: int = 0,
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
		self._full_frame_always_supplement = full_frame_always_supplement
		self._early_exit_count = early_exit_count
		self._fast_candidate_detection = fast_candidate_detection
		self._parallel_workers = parallel_workers

	def detect_and_decode(
		self,
		image: np.ndarray,
		skip_bboxes: list[tuple[int, int, int, int]] | None = None,
	) -> list[OpenCVDataMatrixResult]:
		"""Detect and decode DataMatrix codes in *image*.

		Args:
			image: BGR frame to scan.
			skip_bboxes: Bounding boxes of codes already confirmed in a previous
				frame.  Any candidate ROI whose expanded bbox overlaps a skip_bbox
				by IoU >= 0.35 is dropped, saving scan time and focusing effort
				on regions that have NOT yet been decoded.
		"""
		start = time.perf_counter()
		h, w = image.shape[:2]
		max_area = max(int(h * w * self._max_area_ratio), self._min_area)

		candidates = self._detect_candidates(image, max_area=max_area)

		# Drop candidates whose region is already covered by a known bbox,
		# so we spend all scanning budget on *new* undecoded regions.
		if skip_bboxes:
			filtered: list[tuple[int, int, int, int]] = []
			for cand in candidates:
				exp = self._expand_bbox(cand, image.shape)
				if any(self._iou(exp, kb) >= 0.35 for kb in skip_bboxes):
					continue
				filtered.append(cand)
			skipped = len(candidates) - len(filtered)
			if skipped:
				logger.debug("Skipped %d/%d candidates overlapping known bboxes", skipped, len(candidates))
			candidates = filtered

		# --- Parallel ROI scanning -------------------------------------------
		# Flat task pool: pre-compute all (candidate × variant) images on the
		# main thread (OpenCV, fast), then submit ALL zxing scan tasks at once.
		# Example: 35 candidates × 3 variants = 105 tasks, 8 workers →
		# ceil(105/8) = 14 parallel rounds × ~15ms = ~210ms
		# vs sequential: ceil(35/4) rounds × avg_variants × 15ms ≈ 270–405ms
		if self._parallel_workers > 1 and candidates:
			results = self._scan_candidates_flat_parallel(image, candidates)
		else:
			# Sequential path (batch mode or single-core).
			results = self._scan_candidates_sequential(image, candidates)

		if self._fallback_full_image:
			# Speed mode (full_frame_always_supplement=False):
			#   Full-frame scan only runs when ROI found NOTHING.  Keeps latency
			#   low for live preview.  If ROI found some codes, it's good enough.
			# Accuracy mode (full_frame_always_supplement=True):
			#   Full-frame scan always runs and supplements ROI results with any
			#   codes whose contours were missed (blur, compression artefacts, etc.).
			#   Used in batch/capture mode where latency is less critical.
			run_full_frame = self._full_frame_always_supplement or not results
			if run_full_frame:
				already_found = {r.content for r in results if r.content}
				decoded_full = (
					self._scan_full_frame_variants_parallel(image)
					if self._parallel_workers > 1
					else self._scan_full_frame_variants(image)
				)
				for item in decoded_full:
					if not item.success or not item.content:
						continue
					if item.content in already_found:
						continue
					already_found.add(item.content)
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

	def _scan_candidates_sequential(
		self,
		image: np.ndarray,
		candidates: list[tuple[int, int, int, int]],
	) -> list[OpenCVDataMatrixResult]:
		"""Process ROI candidates one-by-one with early exit support."""
		results: list[OpenCVDataMatrixResult] = []
		found_contents: set[str] = set()

		for bbox in candidates:
			if self._early_exit_count > 0 and len(found_contents) >= self._early_exit_count:
				logger.debug("Early exit after finding %d codes", len(found_contents))
				break

			x1, y1, x2, y2 = self._expand_bbox(bbox, image.shape)
			roi = crop_region(image, (x1, y1, x2, y2))
			gray_roi = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY) if len(roi.shape) == 3 else roi
			decoded = self._scan_roi_variants(roi, gray_roi)
			for item in decoded:
				if not item.success or not item.content:
					continue
				if item.content in found_contents:
					continue
				found_contents.add(item.content)
				results.append(OpenCVDataMatrixResult(
					content=item.content,
					bbox=(x1 + int(item.bbox[0]), y1 + int(item.bbox[1]), x1 + int(item.bbox[2]), y1 + int(item.bbox[3])),
					confidence=0.95,
					decoder_used=item.scanner_used,
					detection_source="opencv-roi",
					scan_time_ms=item.scan_time_ms,
				))
		return results

	def _precompute_roi_variant_images(
		self,
		roi: np.ndarray,
		gray: np.ndarray,
	) -> list[np.ndarray]:
		"""Eagerly compute all preprocessing variants for one ROI.

		Called on the main thread before submitting zxing scans to the pool.
		For small ROIs (≤200×200 px) all variants complete in < 10ms total.
		Returns a list of pre-processed images (up to max_roi_scan_variants).
		"""
		standard_fns: list = [
			lambda: roi,
			lambda: self._enhance_from_gray(gray),
			lambda: self._unsharp_mask_gray(gray),
			lambda: self._invert_variant(roi),
			lambda: self._bilateral_variant_gray(gray),
			lambda: self._invert_variant(self._enhance_from_gray(gray)),
			lambda: self._morphological_sharpen_gray(gray),
			lambda: self._jpeg_artifact_variant_gray(gray),
		]
		# Upscale variants: put FIRST so a small budget (max_roi_scan_variants=5)
		# still reaches them.  Previously they were appended after 8 standard
		# variants and were never reached in fast mode.
		side = min(roi.shape[:2])
		if side < 64:
			# Tiny ROI — zxing needs ≥ 2 px/module; 3× upscale is mandatory.
			upscale_fns = [
				lambda: self._resize_variant(roi, scale=3.0),
				lambda: self._resize_variant(self._enhance_from_gray(gray), scale=3.0),
				lambda: self._resize_variant(self._unsharp_mask_gray(gray), scale=3.0),
				lambda: self._resize_variant(roi, scale=2.0),
				lambda: self._resize_variant(self._enhance_from_gray(gray), scale=2.0),
			]
			variant_fns = upscale_fns + standard_fns
		elif side < 160:
			# Small ROI — 2× upscale first.
			upscale_fns = [
				lambda: self._resize_variant(roi, scale=2.0),
				lambda: self._resize_variant(self._enhance_from_gray(gray), scale=2.0),
				lambda: self._resize_variant(self._unsharp_mask_gray(gray), scale=2.0),
				lambda: self._resize_variant(self._jpeg_artifact_variant_gray(gray), scale=2.0),
			]
			variant_fns = upscale_fns + standard_fns
		elif side < 320:
			# Moderately small — prepend 2× but keep standard variants available.
			upscale_fns = [
				lambda: self._resize_variant(roi, scale=2.0),
				lambda: self._resize_variant(self._enhance_from_gray(gray), scale=2.0),
			]
			variant_fns = upscale_fns + standard_fns
		else:
			variant_fns = standard_fns
		# Evaluate eagerly — only as many as we'll actually scan.
		return [fn() for fn in variant_fns[: self._max_roi_scan_variants]]

	def _scan_candidates_flat_parallel(
		self,
		image: np.ndarray,
		candidates: list[tuple[int, int, int, int]],
	) -> list[OpenCVDataMatrixResult]:
		"""Flat task pool: one zxing scan task per (candidate × variant).

		Phase 1 (main thread): crop ROI, compute gray, evaluate all preprocessing
		  variant images.  OpenCV is fast for small ROIs (≤10 ms total for 3
		  variants of a 150×150 ROI).
		Phase 2 (thread pool): submit every pre-processed image as an independent
		  zxing scan task.  zxing-cpp releases the GIL → true parallelism.

		With 35 candidates × 3 variants = 105 tasks and 8 workers the pool runs
		ceil(105/8) = 14 parallel rounds instead of the old ceil(35/4)×avg_variants
		≈ 27 sequential rounds.
		"""
		# Phase 1: pre-compute all variant images on main thread.
		# Task = (roi_x1, roi_y1, roi_w, roi_h, variant_img)
		# roi_w/roi_h are stored so we can normalise scanner bbox coords from
		# the variant-image space back to ROI space in the worker.
		all_tasks: list[tuple[int, int, int, int, np.ndarray]] = []
		for bbox in candidates:
			x1, y1, x2, y2 = self._expand_bbox(bbox, image.shape)
			roi = crop_region(image, (x1, y1, x2, y2))
			if roi.size == 0:
				continue
			roi_h, roi_w = roi.shape[:2]
			gray_roi = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY) if len(roi.shape) == 3 else roi
			for vi in self._precompute_roi_variant_images(roi, gray_roi):
				all_tasks.append((x1, y1, roi_w, roi_h, vi))

		if not all_tasks:
			return []

		# Phase 2: flat parallel zxing scans.
		results: list[OpenCVDataMatrixResult] = []
		lock = threading.Lock()
		found_contents: set[str] = set()
		abort = threading.Event()

		def _scan_task(task: tuple[int, int, int, int, np.ndarray]) -> None:
			if abort.is_set():
				return
			x1, y1, roi_w, roi_h, variant_img = task
			# Normalise variant-space bbox → ROI space so the final image-absolute
			# bbox is correct even when the variant is an upscaled copy.
			var_h, var_w = variant_img.shape[:2]
			sx = roi_w / max(var_w, 1)
			sy = roi_h / max(var_h, 1)
			decoded = self._scanner.scan(variant_img)
			for item in decoded:
				if not item.success or not item.content:
					continue
				with lock:
					if item.content in found_contents:
						continue
					found_contents.add(item.content)
					if self._early_exit_count > 0 and len(found_contents) >= self._early_exit_count:
						abort.set()
					results.append(OpenCVDataMatrixResult(
						content=item.content,
						bbox=(
							x1 + int(item.bbox[0] * sx),
							y1 + int(item.bbox[1] * sy),
							x1 + int(item.bbox[2] * sx),
							y1 + int(item.bbox[3] * sy),
						),
						confidence=0.95,
						decoder_used=item.scanner_used,
						detection_source="opencv-roi",
						scan_time_ms=item.scan_time_ms,
					))

		with ThreadPoolExecutor(max_workers=self._parallel_workers) as pool:
			list(pool.map(_scan_task, all_tasks))

		return results

	def _scan_full_frame_variants_parallel(self, image: np.ndarray) -> list:
		"""Run all full-frame preprocessing variants in parallel.

		Submits (preprocess_fn + zxing_scan) as one task per variant so that
		both the heavy OpenCV ops (CLAHE, bilateral, etc.) AND zxing scanning
		run concurrently.  OpenCV C++ extensions release the GIL during
		compute-heavy operations, giving true multi-core parallelism.

		With 4 variants and 4+ workers all 4 variants run simultaneously,
		reducing full-frame fallback latency by ~4×.
		"""
		gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY) if len(image.shape) == 3 else image

		# Each fn is evaluated inside the worker — preprocessing is parallel too.
		variant_fns = [
			lambda: image,
			lambda: self._enhance_from_gray(gray),
			lambda: self._unsharp_mask_gray(gray),
			lambda: self._bilateral_variant_gray(gray),
			lambda: self._jpeg_artifact_variant_gray(gray),
			lambda: self._invert_variant(image),
			lambda: self._binary_variant_gray(gray),
			lambda: self._denoise_variant_gray(gray),
			lambda: self._morphological_sharpen_gray(gray),
			lambda: self._invert_variant(self._enhance_from_gray(gray)),
		][: self._max_full_frame_scan_variants]

		all_results: list = []
		lock = threading.Lock()
		found: set[str] = set()

		def _scan_ff(vfn) -> None:
			scanned = self._scanner.scan(vfn())
			for item in scanned:
				if not item.success or not item.content:
					continue
				with lock:
					if item.content not in found:
						found.add(item.content)
						all_results.append(item)

		workers = min(self._parallel_workers, len(variant_fns))
		with ThreadPoolExecutor(max_workers=workers) as pool:
			list(pool.map(_scan_ff, variant_fns))

		return all_results

	def _scan_candidates_parallel(
		self,
		image: np.ndarray,
		candidates: list[tuple[int, int, int, int]],
	) -> list[OpenCVDataMatrixResult]:
		"""Fan out ROI candidates across a thread pool.

		zxing-cpp releases the Python GIL during barcode reading, so multiple
		threads run in true parallel on multi-core hardware (Pi 5 = 4 cores).
		Expected speedup: ~min(workers, candidates) times faster than sequential.

		Early exit: a threading.Event is shared across workers.  Once we have
		enough codes (early_exit_count), the event is set and remaining workers
		skip their scan step immediately.
		"""
		results: list[OpenCVDataMatrixResult] = []
		lock = threading.Lock()
		found_contents: set[str] = set()
		abort = threading.Event()

		def _worker(bbox: tuple[int, int, int, int]) -> list[OpenCVDataMatrixResult]:
			if abort.is_set():
				return []
			x1, y1, x2, y2 = self._expand_bbox(bbox, image.shape)
			roi = crop_region(image, (x1, y1, x2, y2))
			if roi.size == 0:
				return []
			gray_roi = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY) if len(roi.shape) == 3 else roi
			# _scan_roi_variants is stateless (reads only self._* scalars and calls
			# self._scanner.scan which is thread-safe for zxing-cpp).
			decoded = self._scan_roi_variants(roi, gray_roi)
			local_new: list[OpenCVDataMatrixResult] = []
			for item in decoded:
				if not item.success or not item.content:
					continue
				with lock:
					if item.content in found_contents:
						continue
					found_contents.add(item.content)
					if self._early_exit_count > 0 and len(found_contents) >= self._early_exit_count:
						abort.set()
				local_new.append(OpenCVDataMatrixResult(
					content=item.content,
					bbox=(x1 + int(item.bbox[0]), y1 + int(item.bbox[1]), x1 + int(item.bbox[2]), y1 + int(item.bbox[3])),
					confidence=0.95,
					decoder_used=item.scanner_used,
					detection_source="opencv-roi",
					scan_time_ms=item.scan_time_ms,
				))
			return local_new

		with ThreadPoolExecutor(max_workers=self._parallel_workers) as pool:
			futures: list[Future[list[OpenCVDataMatrixResult]]] = [
				pool.submit(_worker, bbox) for bbox in candidates
			]
			for fut in as_completed(futures):
				try:
					results.extend(fut.result())
				except Exception as exc:  # noqa: BLE001
					logger.warning("Parallel ROI worker failed: %s", exc)

		return results

	def detect_two_stage_on(
		self,
		detection_image: np.ndarray,
		original_image: np.ndarray,
		detection_scale: float,
		skip_bboxes: list[tuple[int, int, int, int]] | None = None,
	) -> list["OpenCVDataMatrixResult"]:
		"""Locate on *detection_image*, scan on *original_image*.

		Args:
			detection_image: Downscaled image used for cheap contour detection.
			original_image:  Full-resolution image used for high-quality scanning.
			detection_scale: ``detection_width / original_width``.
			skip_bboxes:     Already-decoded bboxes to skip (original coords).
		"""
		start = time.perf_counter()
		h, w = detection_image.shape[:2]
		max_area = max(int(h * w * self._max_area_ratio), self._min_area)
		candidates_det = self._detect_candidates(detection_image, max_area=max_area)

		if not candidates_det:
			logger.debug("Two-stage: no candidates on detection image")
			return []

		# Project back to original-image coordinate space.
		if detection_scale != 1.0:
			inv = 1.0 / detection_scale
			candidates_orig = [
				(int(x1 * inv), int(y1 * inv), int(x2 * inv), int(y2 * inv))
				for x1, y1, x2, y2 in candidates_det
			]
		else:
			candidates_orig = candidates_det

		# Filter already-known barcodes.
		if skip_bboxes:
			candidates_orig = [
				c for c in candidates_orig
				if not any(
					self._iou(self._expand_bbox(c, original_image.shape), kb) >= 0.35
					for kb in skip_bboxes
				)
			]

		if not candidates_orig:
			return []

		elapsed_det = (time.perf_counter() - start) * 1000
		logger.debug(
			"Two-stage detect: %d candidates in %.1fms, scanning on original",
			len(candidates_orig), elapsed_det,
		)

		# Scan at original resolution — upscale variants in _scan_roi_variants
		# now start from crisp high-res pixels instead of a compressed thumbnail.
		results = (
			self._scan_candidates_flat_parallel(original_image, candidates_orig)
			if self._parallel_workers > 1
			else self._scan_candidates_sequential(original_image, candidates_orig)
		)

		# Full-frame fallback on original image when nothing found by ROI scan.
		if not results and self._fallback_full_image:
			decoded_full = (
				self._scan_full_frame_variants_parallel(original_image)
				if self._parallel_workers > 1
				else self._scan_full_frame_variants(original_image)
			)
			for item in decoded_full:
				if item.success and item.content:
					results.append(OpenCVDataMatrixResult(
						content=item.content,
						bbox=tuple(int(v) for v in item.bbox),
						confidence=0.88,
						decoder_used=item.scanner_used,
						detection_source="full-frame",
						scan_time_ms=item.scan_time_ms,
					))

		elapsed_total = (time.perf_counter() - start) * 1000
		logger.debug("Two-stage total: %d codes in %.1fms", len(results), elapsed_total)
		return self._deduplicate(results)

	def decode_bboxes(
		self,
		image: np.ndarray,
		bboxes: list[tuple[int, int, int, int]],
	) -> list[OpenCVDataMatrixResult]:
		"""Decode only inside provided candidate boxes.

		Used by the live pipeline to avoid expensive full-frame scanning.
		Each input bbox is expanded by detector padding before ROI decode.
		Respects parallel_workers for thread-pool acceleration.
		"""
		if self._parallel_workers > 1 and bboxes:
			return self._scan_candidates_flat_parallel(image, bboxes)

		results: list[OpenCVDataMatrixResult] = []
		for bbox in bboxes:
			x1, y1, x2, y2 = self._expand_bbox(bbox, image.shape)
			roi = crop_region(image, (x1, y1, x2, y2))
			if roi.size == 0:
				continue
			gray_roi = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY) if len(roi.shape) == 3 else roi
			decoded = self._scan_roi_variants(roi, gray_roi)
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

	def _scan_roi_variants(self, roi: np.ndarray, gray: np.ndarray | None = None) -> list:
		"""Try progressively more aggressive preprocessing until a code is found.

		Variants are ordered cheapest-first. `max_roi_scan_variants` caps how
		many variants are attempted (use 1-2 for live/fast mode, 6+ for batch).
		Includes blur-resistant variants (unsharp mask, bilateral, morphological,
		JPEG artifact suppression).

		``gray`` is a pre-computed grayscale of ``roi``.  Pass it in to avoid
		repeating the BGR→GRAY conversion for every variant.
		"""
		if gray is None:
			gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY) if len(roi.shape) == 3 else roi

		standard_variants: list = [
			lambda: roi,
			lambda: self._enhance_from_gray(gray),
			lambda: self._unsharp_mask_gray(gray),
			lambda: self._invert_variant(roi),
			lambda: self._bilateral_variant_gray(gray),
			lambda: self._invert_variant(self._enhance_from_gray(gray)),
			lambda: self._morphological_sharpen_gray(gray),
			lambda: self._jpeg_artifact_variant_gray(gray),
		]
		# Upscale variants — prepended (not appended) so they're tried first on
		# small ROIs even when max_roi_scan_variants is low (e.g. 5 in live mode).
		side = min(roi.shape[:2])
		if side < 64:
			upscale_fns = [
				lambda: self._resize_variant(roi, scale=3.0),
				lambda: self._resize_variant(self._enhance_from_gray(gray), scale=3.0),
				lambda: self._resize_variant(self._unsharp_mask_gray(gray), scale=3.0),
				lambda: self._resize_variant(roi, scale=2.0),
				lambda: self._resize_variant(self._enhance_from_gray(gray), scale=2.0),
			]
			variants = upscale_fns + standard_variants
		elif side < 160:
			upscale_fns = [
				lambda: self._resize_variant(roi, scale=2.0),
				lambda: self._resize_variant(self._enhance_from_gray(gray), scale=2.0),
				lambda: self._resize_variant(self._unsharp_mask_gray(gray), scale=2.0),
				lambda: self._resize_variant(self._jpeg_artifact_variant_gray(gray), scale=2.0),
			]
			variants = upscale_fns + standard_variants
		elif side < 320:
			upscale_fns = [
				lambda: self._resize_variant(roi, scale=2.0),
				lambda: self._resize_variant(self._enhance_from_gray(gray), scale=2.0),
			]
			variants = upscale_fns + standard_variants
		else:
			variants = standard_variants
		roi_h, roi_w = roi.shape[:2]
		for variant_fn in variants[: self._max_roi_scan_variants]:
			var_img = variant_fn()
			decoded = self._scanner.scan(var_img)
			successful = [item for item in decoded if item.success and item.content]
			if successful:
				# If the variant was upscaled, bbox coords are in the upscaled space;
				# normalise them back to ROI space before returning so callers can
				# safely add the ROI origin (x1, y1) to get image-absolute coords.
				var_h, var_w = var_img.shape[:2]
				if var_w != roi_w or var_h != roi_h:
					sx = roi_w / max(var_w, 1)
					sy = roi_h / max(var_h, 1)
					for item in successful:
						bx1, by1, bx2, by2 = item.bbox
						item.bbox = (
							int(bx1 * sx), int(by1 * sy),
							int(bx2 * sx), int(by2 * sy),
						)
				return successful
		return []

	def _scan_full_frame_variants(self, image: np.ndarray) -> list:
		"""Try multiple preprocessing variants on the full frame.

		Includes blur-resistant variants for distant/out-of-focus shots.
		"""
		# Pre-compute gray once for all full-frame variants.
		gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY) if len(image.shape) == 3 else image
		all_variants = [
			lambda: image,
			lambda: self._enhance_from_gray(gray),
			lambda: self._unsharp_mask_gray(gray),
			lambda: self._bilateral_variant_gray(gray),
			lambda: self._jpeg_artifact_variant_gray(gray),
			lambda: self._invert_variant(image),
			lambda: self._binary_variant_gray(gray),
			lambda: self._denoise_variant_gray(gray),
			lambda: self._morphological_sharpen_gray(gray),
			lambda: self._invert_variant(self._enhance_from_gray(gray)),
		]
		for variant_fn in all_variants[: self._max_full_frame_scan_variants]:
			results = self._scanner.scan(variant_fn())
			successful = [item for item in results if item.success and item.content]
			if successful:
				return successful
		return []

	def _enhance_for_decode(self, image: np.ndarray) -> np.ndarray:
		"""BGR or gray image → sharpened+CLAHE BGR.  Kept for external callers."""
		gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY) if len(image.shape) == 3 else image
		return self._enhance_from_gray(gray)

	def _enhance_from_gray(self, gray: np.ndarray) -> np.ndarray:
		"""CLAHE + sharpen kernel on a pre-computed grayscale image."""
		clahe = cv2.createCLAHE(clipLimit=max(self._clahe_clip_limit, 3.0), tileGridSize=(8, 8))
		enhanced = clahe.apply(gray)
		sharpen_kernel = np.array([[0, -1, 0], [-1, 5, -1], [0, -1, 0]], dtype=np.float32)
		enhanced = cv2.filter2D(enhanced, -1, sharpen_kernel)
		return cv2.cvtColor(enhanced, cv2.COLOR_GRAY2BGR)

	@staticmethod
	def _invert_variant(image: np.ndarray) -> np.ndarray:
		"""Invert image — helps for light-on-dark DataMatrix codes."""
		return cv2.bitwise_not(image)

	@staticmethod
	def _denoise_variant(image: np.ndarray) -> np.ndarray:
		"""Kept for external callers; internally use _denoise_variant_gray."""
		gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY) if len(image.shape) == 3 else image
		return OpenCVDataMatrixDetector._denoise_variant_gray(gray)

	@staticmethod
	def _denoise_variant_gray(gray: np.ndarray) -> np.ndarray:
		"""Median blur denoising — 30x faster than NLM for live mode.

		medianBlur(k=5) effectively suppresses JPEG block noise and salt-and-pepper
		artefacts while preserving the sharp edges of the DataMatrix finder
		pattern.  fastNlMeansDenoising was replaced here because NLM is O(n²)
		per pixel (≈500ms per ROI) versus O(k²) for median (≈4ms per ROI).
		"""
		denoised = cv2.medianBlur(gray, 5)
		return cv2.cvtColor(denoised, cv2.COLOR_GRAY2BGR)

	@staticmethod
	def _jpeg_artifact_variant(image: np.ndarray) -> np.ndarray:
		"""Kept for external callers; internally use _jpeg_artifact_variant_gray."""
		gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY) if len(image.shape) == 3 else image
		return OpenCVDataMatrixDetector._jpeg_artifact_variant_gray(gray)

	@staticmethod
	def _jpeg_artifact_variant_gray(gray: np.ndarray) -> np.ndarray:
		"""Suppress JPEG block artifacts then boost contrast.

		medianBlur(k=5) removes 8×8 block artefacts in roughly 4ms (vs 500ms
		for fastNlMeansDenoising).  A fine-tiled CLAHE (4×4) then restores the
		module contrast that JPEG compression degraded, and a mild sharpen kernel
		re-emphasises the quiet-zone/finder boundary.
		"""
		# Step 1: remove block artefacts (cheap median filter)
		denoised = cv2.medianBlur(gray, 5)
		# Step 2: fine-tiled CLAHE for local contrast enhancement
		clahe = cv2.createCLAHE(clipLimit=4.0, tileGridSize=(4, 4))
		enhanced = clahe.apply(denoised)
		# Step 3: mild sharpen to re-emphasise module edges
		sharp_kernel = np.array([[0, -1, 0], [-1, 5, -1], [0, -1, 0]], dtype=np.float32)
		sharpened = cv2.filter2D(enhanced, -1, sharp_kernel)
		return cv2.cvtColor(sharpened, cv2.COLOR_GRAY2BGR)

	@staticmethod
	def _unsharp_mask(image: np.ndarray, sigma: float = 1.0, strength: float = 1.5) -> np.ndarray:
		"""Kept for external callers; internally use _unsharp_mask_gray."""
		gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY) if len(image.shape) == 3 else image
		return OpenCVDataMatrixDetector._unsharp_mask_gray(gray, sigma, strength)

	@staticmethod
	def _unsharp_mask_gray(gray: np.ndarray, sigma: float = 1.0, strength: float = 1.5) -> np.ndarray:
		"""Unsharp masking — effective against mild motion/focus blur."""
		blurred = cv2.GaussianBlur(gray, (0, 0), sigma)
		sharpened = cv2.addWeighted(gray, 1.0 + strength, blurred, -strength, 0)
		return cv2.cvtColor(sharpened, cv2.COLOR_GRAY2BGR)

	@staticmethod
	def _bilateral_variant(image: np.ndarray) -> np.ndarray:
		"""Kept for external callers; internally use _bilateral_variant_gray."""
		gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY) if len(image.shape) == 3 else image
		return OpenCVDataMatrixDetector._bilateral_variant_gray(gray)

	@staticmethod
	def _bilateral_variant_gray(gray: np.ndarray) -> np.ndarray:
		"""Bilateral filter — edge-preserving smoothing followed by CLAHE contrast.

		d=5 instead of d=9: complexity is O(d²) per pixel, so d=5 is ~3x faster
		(25 vs 81 operations per pixel) with minimal quality loss for DataMatrix.
		"""
		filtered = cv2.bilateralFilter(gray, d=5, sigmaColor=50, sigmaSpace=50)
		clahe = cv2.createCLAHE(clipLimit=3.0, tileGridSize=(8, 8))
		enhanced = clahe.apply(filtered)
		return cv2.cvtColor(enhanced, cv2.COLOR_GRAY2BGR)

	@staticmethod
	def _morphological_sharpen(image: np.ndarray) -> np.ndarray:
		"""Kept for external callers; internally use _morphological_sharpen_gray."""
		gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY) if len(image.shape) == 3 else image
		return OpenCVDataMatrixDetector._morphological_sharpen_gray(gray)

	@staticmethod
	def _morphological_sharpen_gray(gray: np.ndarray) -> np.ndarray:
		"""Morphological sharpening — extracts edge detail from blurry images."""
		kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (3, 3))
		dilated = cv2.dilate(gray, kernel)
		eroded = cv2.erode(gray, kernel)
		edges = dilated - eroded
		sharpened = cv2.addWeighted(gray, 1.0, edges, 0.5, 0)
		clahe = cv2.createCLAHE(clipLimit=3.0, tileGridSize=(8, 8))
		sharpened = clahe.apply(sharpened)
		return cv2.cvtColor(sharpened, cv2.COLOR_GRAY2BGR)

	def _binary_variant(self, image: np.ndarray) -> np.ndarray:
		gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY) if len(image.shape) == 3 else image
		return self._binary_variant_gray(gray)

	def _binary_variant_gray(self, gray: np.ndarray) -> np.ndarray:
		blurred = cv2.GaussianBlur(gray, (3, 3), 0)
		binary = cv2.adaptiveThreshold(
			blurred,
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

		kernel = cv2.getStructuringElement(
			cv2.MORPH_RECT,
			(self._morph_kernel_size, self._morph_kernel_size),
		)

		all_candidates: list[tuple[int, int, int, int]] = []

		if self._fast_candidate_detection:
			# Fast mode: single adaptive-threshold pass + one Canny pass.
			# Skips 5 of the 7 processing paths used in accuracy mode, saving
			# roughly 60% of the candidate-detection time.
			binary = cv2.adaptiveThreshold(
				enhanced, 255,
				cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY,
				self._adaptive_block_size, self._adaptive_c,
			)
			binary = cv2.bitwise_not(binary)
			morphed = cv2.morphologyEx(binary, cv2.MORPH_CLOSE, kernel, iterations=1)
			self._extract_contour_candidates(morphed, max_area, all_candidates)

			# Lower Canny thresholds (20/80 vs old 40/120) to catch faint, fine
			# edges of small or distant DataMatrix codes.
			edges = cv2.Canny(enhanced, 20, 80)
			dilated = cv2.dilate(edges, kernel, iterations=2)
			self._extract_contour_candidates(dilated, max_area, all_candidates)
		else:
			# Accuracy mode: run adaptive thresholding at multiple block sizes to
			# catch both fine-grained and coarser patterns (important for blurry images)
			block_sizes = [self._adaptive_block_size]
			for alt in [15, 51, 71]:
				if alt != self._adaptive_block_size:
					block_sizes.append(alt)

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
			# Build a fast scanner for live preview — zxing-only, no pylibdmtx.
			#
			# pylibdmtx has a hard minimum of ~200ms per scan call (timeout floor).
			# 35 candidates × 3 variants × 200ms = up to 21 seconds worst-case.
			# zxing-cpp has no timeout and completes each ROI in 2-30ms, so worst
			# case is 35 × 3 × 30ms = ~3 seconds, typical < 1 second.
			#
			# try_harder=True runs 3 binarizers (LocalAverage / GlobalHistogram /
			# FixedThreshold) — still << 100ms per ROI, but much higher recognition
			# rate than a single binarizer pass.
			zxing = ZxingScanner(try_harder=True)
			# No fallback needed: zxing already tries multiple binarizers.
			scanner = CompositeScanner(primary=zxing, fallback=None, merge_results=False)
			return OpenCVDataMatrixDetector(
				scanner=scanner,
				# Lower min_area to 30 so tiny DataMatrix codes (small physical size
				# or far from camera) are not discarded during candidate detection.
				min_area=detector_cfg.get("min_area", 30),
				max_area_ratio=detector_cfg.get("max_area_ratio", 0.3),
				adaptive_block_size=detector_cfg.get("adaptive_block_size", 31),
				adaptive_c=detector_cfg.get("adaptive_c", 8),
				morph_kernel_size=detector_cfg.get("morph_kernel_size", 3),
				blur_kernel_size=detector_cfg.get("blur_kernel_size", 5),
				aspect_ratio_min=detector_cfg.get("aspect_ratio_min", 0.5),
				aspect_ratio_max=detector_cfg.get("aspect_ratio_max", 2.0),
				padding=detector_cfg.get("padding", 20),
				# Fast mode: cap at 35 candidates — 150 candidates × variants is the
				# main cause of 50+ second latency.  35 well-ranked candidates
				# (sorted by area descending) covers almost all real DataMatrix codes.
				max_candidates=detector_cfg.get("fast_max_candidates", 35),
				clahe_clip_limit=detector_cfg.get("clahe_clip_limit", 3.0),
				fallback_full_image=True,
				# 5 variants: for normal ROIs → original + enhanced + unsharp + invert
				# + bilateral.  For small ROIs (< 160 px side) upscale variants are
				# PREPENDED so the 5-slot budget is spent on 2×/3× upscaled versions
				# first — the most impactful fix for small DataMatrix in live mode.
				max_roi_scan_variants=5,
				max_full_frame_scan_variants=4,
				# Speed mode: full-frame only when ROI found nothing
				full_frame_always_supplement=False,
				# Fast candidate detection: 1 adaptive-threshold + 1 Canny pass
				fast_candidate_detection=True,
				# Flat task pool: 2×cpu_count workers keeps the pool full even when
				# a thread briefly holds the GIL for OpenCV preprocessing.
				# Pi 5 (4 cores) → 8 workers: ceil(35 cand × 5 variants / 8) = 22
				# rounds × ~15ms ≈ 330ms vs old ceil(35/4)×3×15ms ≈ 405ms.
				parallel_workers=min(8, (os.cpu_count() or 4) * 2),
			)

		# Full-quality scanner for batch/capture mode
		dec_cfg = config.get("decoding", {})
		dmtx_cfg = dec_cfg.get("pylibdmtx", {})
		pylibdmtx = PylibdmtxScanner(
			# 600ms budget: adaptive-timeout scales this to ~150ms for typical
			# ROI crops (≤200×200 px) and up to 600ms only for large regions
			# (full res frame).  Pylibdmtx either finds a code fast or it won't;
			# 5000ms was pure waste.  If the user needs a higher ceiling they can
			# Set decoding.pylibdmtx.timeout_ms in default.yaml.
			timeout_ms=dmtx_cfg.get("timeout_ms", 600),
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
			# Batch: 70 candidates is thorough without triggering 7×70=490 sequential calls.
			# Flat parallel pool handles all 490 tasks across workers simultaneously.
			max_candidates=detector_cfg.get("max_candidates", 70),
			clahe_clip_limit=detector_cfg.get("clahe_clip_limit", 3.0),
			fallback_full_image=detector_cfg.get("fallback_full_image", True),
			max_roi_scan_variants=7,           # original+enhanced+unsharp+invert+bilateral+morphological+jpeg_artifact
			max_full_frame_scan_variants=8,    # same set for full-frame
			# Accuracy mode: full-frame supplements ROI to catch any missed codes
			full_frame_always_supplement=True,
			# Batch mode also benefits from parallel scanning: pylibdmtx releases
			# the GIL during its C-level decode, so 8 workers gives near-linear
			# speedup.  70 cand × 7 variants = 490 tasks / 8 workers ≈ 62 rounds
			# × ~150ms ≈ 9s vs old 490 × 150ms sequential = 73s.
			parallel_workers=min(8, (os.cpu_count() or 4) * 2),
		)
