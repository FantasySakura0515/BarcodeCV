"""Tests for NNDecoder — the YOLO + CRNN neural network scanner."""

from unittest.mock import MagicMock, patch

import numpy as np
import pytest

from backend.decoding.direct_scanner import ScanResult
from backend.decoding.nn_decoder import NNDecoder, _greedy_ctc_decode, _VOCAB as _FULL_VOCAB


class TestGreedyCtcDecode:
    def test_decode_simple_sequence(self):
        # Build logits: high score on char 'A' (index = vocab.index('A'))
        vocab = _FULL_VOCAB
        a_idx = vocab.index("A")
        T = 8
        logits = np.full((T, len(vocab)), -10.0)
        for t in range(T):
            logits[t, a_idx] = 5.0  # all timesteps predict 'A'
        content, conf = _greedy_ctc_decode(logits)
        # Greedy CTC collapses consecutive duplicates → single 'A'
        assert content == "A"
        assert 0.0 <= conf <= 1.0

    def test_blank_is_ignored(self):
        vocab = _FULL_VOCAB
        # All blank (index 0) → empty string
        T = 5
        logits = np.full((T, len(vocab)), -10.0)
        for t in range(T):
            logits[t, 0] = 5.0  # blank
        content, _ = _greedy_ctc_decode(logits)
        assert content == ""

    def test_multi_char_sequence(self):
        vocab = _FULL_VOCAB
        h_idx = vocab.index("H")
        i_idx = vocab.index("I")
        T = 6
        logits = np.full((T, len(vocab)), -10.0)
        # H H blank I I blank → "HI"
        logits[0, h_idx] = 5.0
        logits[1, h_idx] = 5.0
        logits[2, 0] = 5.0  # blank separator
        logits[3, i_idx] = 5.0
        logits[4, i_idx] = 5.0
        logits[5, 0] = 5.0
        content, _ = _greedy_ctc_decode(logits)
        assert content == "HI"


class TestNNDecoderInterface:
    """Tests that NNDecoder honours its public interface without real models."""

    def _make_decoder(self) -> NNDecoder:
        return NNDecoder(
            yolo_model_path="./models/dummy_yolo.pt",
            crnn_model_path="./models/dummy_crnn.onnx",
        )

    def test_name(self):
        d = self._make_decoder()
        assert "YOLO" in d.name() and "CRNN" in d.name()

    def test_scan_returns_empty_when_models_not_loaded(self):
        d = self._make_decoder()
        image = np.zeros((100, 100, 3), dtype=np.uint8)
        # Models not loaded → should return empty list, not raise
        results = d.scan(image)
        assert results == []

    def test_scan_returns_scan_result_objects(self):
        d = self._make_decoder()

        # Fake YOLO model that detects one region
        fake_box = MagicMock()
        fake_box.xyxy = [MagicMock()]
        fake_box.xyxy[0].cpu.return_value.numpy.return_value = np.array([10, 10, 50, 50])
        fake_box.conf = [MagicMock()]
        fake_box.conf[0].cpu.return_value.numpy.return_value = 0.9

        fake_result = MagicMock()
        fake_result.boxes = [fake_box]

        fake_yolo = MagicMock()
        fake_yolo.return_value = [fake_result]
        d._yolo = fake_yolo

        # Fake CRNN that returns a known string
        fake_crnn = MagicMock()
        fake_crnn.is_loaded = True
        fake_crnn.decode.return_value = ("PART-123", 0.95)
        d._crnn = fake_crnn

        image = np.zeros((100, 100, 3), dtype=np.uint8)
        results = d.scan(image)

        assert len(results) == 1
        r = results[0]
        assert isinstance(r, ScanResult)
        assert r.content == "PART-123"
        assert r.success is True
        assert r.scanner_used == "nn_decoder"

    def test_from_config(self):
        config = {
            "detection": {
                "model_path": "./models/yolo.pt",
                "confidence_threshold": 0.6,
                "iou_threshold": 0.4,
                "device": "cpu",
                "imgsz": 640,
                "max_detections": 30,
            },
            "nn_decoding": {
                "crnn_model_path": "./models/crnn.onnx",
                "pad_ratio": 0.1,
            },
        }
        d = NNDecoder.from_config(config)
        assert d._yolo_path == "./models/yolo.pt"
        assert d._conf_thresh == 0.6
        assert d._pad_ratio == 0.1

    def test_crop_region_clips_to_image_bounds(self):
        d = self._make_decoder()
        image = np.zeros((100, 100, 3), dtype=np.uint8)
        # Bbox that extends outside image
        crop = d._crop_region(image, (-10, -10, 200, 200))
        assert crop is not None
        assert crop.shape[0] <= 100
        assert crop.shape[1] <= 100

    def test_crop_region_invalid_returns_none(self):
        d = self._make_decoder()
        image = np.zeros((100, 100, 3), dtype=np.uint8)
        crop = d._crop_region(image, (50, 50, 40, 60))  # x2 < x1
        assert crop is None


class TestCreateScanner:
    """Integration test for the _create_scanner factory."""

    def test_library_mode_returns_composite_scanner(self):
        from backend.decoding.direct_scanner import CompositeScanner
        from backend.main import _create_scanner

        config = {
            "scanner": {"mode": "library"},
            "decoding": {
                "primary_decoder": "pylibdmtx",
                "fallback_decoder": "zxing",
                "merge_results": True,
                "pylibdmtx": {
                    "timeout_ms": 600,
                    "shrink": 1,
                    "threshold": 50,
                    "min_edge": 6,
                    "max_edge": 400,
                },
            },
        }
        scanner = _create_scanner(config)
        assert isinstance(scanner, CompositeScanner)

    def test_nn_mode_returns_nn_decoder(self):
        from backend.main import _create_scanner

        config = {
            "scanner": {"mode": "nn"},
            "detection": {
                "model_path": "/nonexistent/yolo.pt",
                "confidence_threshold": 0.5,
                "iou_threshold": 0.45,
                "device": "cpu",
                "imgsz": 640,
                "max_detections": 50,
            },
            "nn_decoding": {
                "crnn_model_path": "/nonexistent/crnn.onnx",
                "pad_ratio": 0.05,
            },
        }
        # load_models() would fail without real files — patch it
        with patch.object(NNDecoder, "load_models", return_value=None):
            scanner = _create_scanner(config)
        assert isinstance(scanner, NNDecoder)
