from unittest.mock import MagicMock

import numpy as np

from backend.decoding.decoder import DecodeResult
from backend.decoding.fallback_decoder import FallbackDecoder


class TestFallbackDecoder:
    def test_returns_first_successful_decoder(self):
        decoder1 = MagicMock()
        decoder1.name.return_value = "decoder1"
        decoder1.decode.return_value = [
            DecodeResult(content="HELLO", decoder_used="decoder1",
                        decode_time_ms=10.0, success=True)
        ]

        decoder2 = MagicMock()
        decoder2.name.return_value = "decoder2"

        fallback = FallbackDecoder([decoder1, decoder2])
        results = fallback.decode(np.zeros((100, 100, 3), dtype=np.uint8))

        assert len(results) == 1
        assert results[0].success
        assert results[0].content == "HELLO"
        decoder2.decode.assert_not_called()

    def test_falls_back_on_failure(self):
        decoder1 = MagicMock()
        decoder1.name.return_value = "decoder1"
        decoder1.decode.return_value = [
            DecodeResult(content="", decoder_used="decoder1",
                        decode_time_ms=10.0, success=False, error_message="fail")
        ]

        decoder2 = MagicMock()
        decoder2.name.return_value = "decoder2"
        decoder2.decode.return_value = [
            DecodeResult(content="WORLD", decoder_used="decoder2",
                        decode_time_ms=20.0, success=True)
        ]

        fallback = FallbackDecoder([decoder1, decoder2])
        results = fallback.decode(np.zeros((100, 100, 3), dtype=np.uint8))

        assert len(results) == 1
        assert results[0].success
        assert results[0].content == "WORLD"

    def test_all_decoders_fail(self):
        decoder1 = MagicMock()
        decoder1.name.return_value = "decoder1"
        decoder1.decode.return_value = [
            DecodeResult(content="", decoder_used="decoder1",
                        decode_time_ms=10.0, success=False)
        ]

        fallback = FallbackDecoder([decoder1])
        results = fallback.decode(np.zeros((100, 100, 3), dtype=np.uint8))

        assert len(results) == 1
        assert not results[0].success
