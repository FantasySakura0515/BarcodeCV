"""Neural network-based DataMatrix decoder.

Two-stage pipeline that replaces pylibdmtx / zxing-cpp:

  Stage 1 – Detection:   YOLO model finds DataMatrix bounding boxes.
  Stage 2 – Recognition: CRNN/ONNX model reads the encoded content from
                         each cropped region.

Both models are trained with the scripts in ``training/``.
The CRNN is exported to ONNX (``training/export_recognizer.py``) for
efficient inference via onnxruntime on Raspberry Pi 5.

Usage (from config)::

    detection:
      model_path: "./models/datamatrix_yolo.pt"
      confidence_threshold: 0.5
      iou_threshold: 0.45
      imgsz: 640
      device: "cpu"
      max_detections: 50
    nn_decoding:
      crnn_model_path: "./models/datamatrix_crnn.onnx"
      pad_ratio: 0.05

Usage (programmatic)::

    decoder = NNDecoder.from_config(config)
    decoder.load_models()
    results = decoder.scan(image)          # list[ScanResult]
"""

import logging
import time

import cv2
import numpy as np

from .direct_scanner import ScanResult

logger = logging.getLogger("barcodecv.nn_decoder")

# ──────────────────────────────────────────────────────────────────────────────
# Vocabulary (must match training/models/crnn.py)
# ──────────────────────────────────────────────────────────────────────────────

_BLANK_IDX = 0
_VOCAB: list[str] = ["<blank>"] + [chr(i) for i in range(32, 127)]  # 96 tokens

# CRNN input resolution (must match training)
_IMG_H: int = 32
_IMG_W: int = 256


# ──────────────────────────────────────────────────────────────────────────────
# Preprocessing helpers
# ──────────────────────────────────────────────────────────────────────────────


def _preprocess_crop(crop: np.ndarray) -> np.ndarray:
    """Resize and normalise a cropped DataMatrix region for CRNN inference.

    Returns:
        float32 array of shape (1, 1, IMG_H, IMG_W) in [0, 1].
    """
    if len(crop.shape) == 3:
        gray = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)
    else:
        gray = crop.copy()

    resized = cv2.resize(gray, (_IMG_W, _IMG_H), interpolation=cv2.INTER_AREA)
    normalised = resized.astype(np.float32) / 255.0
    return normalised[np.newaxis, np.newaxis, :, :]  # (1, 1, H, W)


def _greedy_ctc_decode(logits: np.ndarray) -> tuple[str, float]:
    """Greedy CTC decoding of CRNN output.

    Args:
        logits: (T, vocab_size) raw scores (before or after softmax).

    Returns:
        ``(decoded_string, mean_confidence)`` where confidence is the
        mean max-softmax probability across all time steps.
    """
    # Softmax to obtain probabilities
    shifted = logits - logits.max(axis=-1, keepdims=True)
    exp = np.exp(shifted)
    probs = exp / exp.sum(axis=-1, keepdims=True)  # (T, vocab)

    preds = probs.argmax(axis=-1)  # (T,)
    confidence = float(probs.max(axis=-1).mean())

    chars: list[str] = []
    prev = -1
    for p in preds:
        if p != prev:
            if p != _BLANK_IDX:
                chars.append(_VOCAB[p])
            prev = p

    return "".join(chars), confidence


# ──────────────────────────────────────────────────────────────────────────────
# CRNN inference wrapper (ONNX Runtime)
# ──────────────────────────────────────────────────────────────────────────────


class _CRNNInference:
    """Thin wrapper around an ONNX-exported CRNN model."""

    def __init__(self, model_path: str) -> None:
        self._model_path = model_path
        self._session = None

    def load(self) -> None:
        import onnxruntime as ort  # type: ignore[import]

        providers = ["CPUExecutionProvider"]
        if "CUDAExecutionProvider" in ort.get_available_providers():
            providers = ["CUDAExecutionProvider", "CPUExecutionProvider"]

        self._session = ort.InferenceSession(self._model_path, providers=providers)
        logger.info("Loaded CRNN ONNX model from %s", self._model_path)

    @property
    def is_loaded(self) -> bool:
        return self._session is not None

    def decode(self, crop: np.ndarray) -> tuple[str, float]:
        """Run recognition on a single cropped DataMatrix image.

        Args:
            crop: BGR or grayscale image of the DataMatrix region.

        Returns:
            ``(content, confidence)`` tuple.
        """
        if not self.is_loaded:
            raise RuntimeError("CRNN model not loaded. Call load() first.")

        inp = _preprocess_crop(crop)  # (1, 1, H, W)
        input_name = self._session.get_inputs()[0].name
        logits = self._session.run(None, {input_name: inp})[0]  # (T, 1, vocab)

        # Squeeze batch dimension
        logits = logits[:, 0, :]  # (T, vocab_size)
        return _greedy_ctc_decode(logits)


# ──────────────────────────────────────────────────────────────────────────────
# Public NNDecoder class
# ──────────────────────────────────────────────────────────────────────────────


class NNDecoder:
    """Neural network DataMatrix scanner (YOLO detection + CRNN recognition).

    Implements the same ``scan(image) → list[ScanResult]`` interface as
    ``CompositeScanner``, making it a drop-in replacement in the pipeline.

    Args:
        yolo_model_path:        Path to YOLO model (``.pt`` / ``.onnx`` / ``_ncnn_model/``).
        crnn_model_path:        Path to CRNN ONNX model (``.onnx``).
        confidence_threshold:   YOLO detection confidence threshold.
        iou_threshold:          YOLO NMS IoU threshold.
        device:                 Inference device (``"cpu"`` or ``"0"`` for GPU).
        imgsz:                  YOLO input image size.
        max_detections:         Maximum DataMatrix regions per image.
        pad_ratio:              Fractional padding added around each YOLO crop.
    """

    def __init__(
        self,
        yolo_model_path: str,
        crnn_model_path: str,
        confidence_threshold: float = 0.5,
        iou_threshold: float = 0.45,
        device: str = "cpu",
        imgsz: int = 640,
        max_detections: int = 50,
        pad_ratio: float = 0.05,
    ) -> None:
        self._yolo_path = yolo_model_path
        self._conf_thresh = confidence_threshold
        self._iou_thresh = iou_threshold
        self._device = device
        self._imgsz = imgsz
        self._max_det = max_detections
        self._pad_ratio = pad_ratio

        self._yolo = None
        self._crnn = _CRNNInference(crnn_model_path)

    # ── Lifecycle ──────────────────────────────────────────────────────────────

    def load_models(self) -> None:
        """Load both YOLO (detection) and CRNN (recognition) models."""
        from ultralytics import YOLO  # type: ignore[import]

        self._yolo = YOLO(self._yolo_path)
        logger.info("Loaded YOLO model from %s", self._yolo_path)
        self._crnn.load()

    # ── Public scan interface ─────────────────────────────────────────────────

    def scan(self, image: np.ndarray) -> list[ScanResult]:
        """Detect and decode all DataMatrix codes in *image*.

        Args:
            image: BGR ndarray (as returned by OpenCV / camera).

        Returns:
            List of ``ScanResult`` objects, one per successfully decoded code.
            Returns an empty list if models are not loaded or nothing is found.
        """
        if self._yolo is None or not self._crnn.is_loaded:
            logger.warning("NNDecoder: models not loaded — returning empty results")
            return []

        t0 = time.perf_counter()

        regions = self._detect_regions(image)
        if not regions:
            elapsed = (time.perf_counter() - t0) * 1000
            logger.debug("NNDecoder: no regions detected (%.1f ms)", elapsed)
            return []

        results: list[ScanResult] = []
        for bbox, det_conf in regions:
            crop = self._crop_region(image, bbox)
            if crop is None or crop.size == 0:
                continue
            try:
                content, rec_conf = self._crnn.decode(crop)
                if content:
                    # scan_time_ms represents the cumulative wall-clock time
                    # from the start of scan() — consistent with CompositeScanner.
                    scan_ms = (time.perf_counter() - t0) * 1000
                    results.append(
                        ScanResult(
                            content=content,
                            bbox=bbox,
                            scanner_used="nn_decoder",
                            scan_time_ms=scan_ms,
                            success=True,
                        )
                    )
                    logger.debug(
                        "NNDecoder: '%s' det=%.2f rec=%.2f bbox=%s",
                        content,
                        det_conf,
                        rec_conf,
                        bbox,
                    )
            except Exception as exc:
                logger.warning("CRNN decode failed for bbox %s: %s", bbox, exc)

        total_ms = (time.perf_counter() - t0) * 1000
        logger.info(
            "NNDecoder: %d codes from %d regions in %.1f ms",
            len(results),
            len(regions),
            total_ms,
        )
        return results

    def name(self) -> str:
        return "NNDecoder(YOLO+CRNN)"

    # ── Internal helpers ───────────────────────────────────────────────────────

    def _detect_regions(
        self, image: np.ndarray
    ) -> list[tuple[tuple[int, int, int, int], float]]:
        """Run YOLO and return a list of (bbox, confidence) tuples."""
        yolo_out = self._yolo(
            image,
            conf=self._conf_thresh,
            iou=self._iou_thresh,
            imgsz=self._imgsz,
            device=self._device,
            max_det=self._max_det,
            verbose=False,
        )
        regions: list[tuple[tuple[int, int, int, int], float]] = []
        for result in yolo_out:
            if result.boxes is None:
                continue
            for box in result.boxes:
                xyxy = box.xyxy[0].cpu().numpy().astype(int)
                conf = float(box.conf[0].cpu().numpy())
                bbox = (int(xyxy[0]), int(xyxy[1]), int(xyxy[2]), int(xyxy[3]))
                regions.append((bbox, conf))
        return regions

    def _crop_region(
        self, image: np.ndarray, bbox: tuple[int, int, int, int]
    ) -> np.ndarray | None:
        """Return a padded crop of *bbox* from *image*, or ``None`` if invalid."""
        x1, y1, x2, y2 = bbox
        h, w = image.shape[:2]

        pad_x = max(1, int((x2 - x1) * self._pad_ratio))
        pad_y = max(1, int((y2 - y1) * self._pad_ratio))
        x1 = max(0, x1 - pad_x)
        y1 = max(0, y1 - pad_y)
        x2 = min(w, x2 + pad_x)
        y2 = min(h, y2 + pad_y)

        if x2 <= x1 or y2 <= y1:
            return None
        return image[y1:y2, x1:x2]

    # ── Factory ───────────────────────────────────────────────────────────────

    @staticmethod
    def from_config(config: dict) -> "NNDecoder":
        """Create an ``NNDecoder`` from a BarcodeCV YAML config dict."""
        det_cfg = config.get("detection", {})
        nn_cfg = config.get("nn_decoding", {})
        return NNDecoder(
            yolo_model_path=det_cfg.get("model_path", "./models/datamatrix_yolo.pt"),
            crnn_model_path=nn_cfg.get("crnn_model_path", "./models/datamatrix_crnn.onnx"),
            confidence_threshold=det_cfg.get("confidence_threshold", 0.5),
            iou_threshold=det_cfg.get("iou_threshold", 0.45),
            device=det_cfg.get("device", "cpu"),
            imgsz=det_cfg.get("imgsz", 640),
            max_detections=det_cfg.get("max_detections", 50),
            pad_ratio=nn_cfg.get("pad_ratio", 0.05),
        )
