import logging

import numpy as np

from .decoder import DataMatrixDecoder, DecodeResult
from .pylibdmtx_decoder import PylibdmtxDecoder
from .zxing_decoder import ZxingDecoder

logger = logging.getLogger("barcodecv.decoding")


class FallbackDecoder(DataMatrixDecoder):
    """Composite decoder that tries multiple decoders in sequence.

    Returns the first successful result. Falls back to the next decoder
    only if the previous one fails.
    """

    def __init__(self, decoders: list[DataMatrixDecoder]):
        self._decoders = decoders

    def decode(self, image: np.ndarray) -> list[DecodeResult]:
        for decoder in self._decoders:
            results = decoder.decode(image)
            if any(r.success for r in results):
                return [r for r in results if r.success]

        # All decoders failed - return the last failure
        return [
            DecodeResult(
                content="",
                decoder_used=self.name(),
                decode_time_ms=0,
                success=False,
                error_message="All decoders failed",
            )
        ]

    def name(self) -> str:
        names = [d.name() for d in self._decoders]
        return f"FallbackDecoder({' -> '.join(names)})"

    @staticmethod
    def from_config(config: dict) -> "FallbackDecoder":
        """Create FallbackDecoder from config dict."""
        dec_cfg = config["decoding"]
        decoders: list[DataMatrixDecoder] = []

        decoder_map = {
            "zxing": lambda: ZxingDecoder(),
            "pylibdmtx": lambda: PylibdmtxDecoder(
                timeout_ms=dec_cfg["pylibdmtx"]["timeout_ms"],
                max_count=dec_cfg["pylibdmtx"]["max_count"],
                shrink=dec_cfg["pylibdmtx"]["shrink"],
                threshold=dec_cfg["pylibdmtx"]["threshold"],
                min_edge=dec_cfg["pylibdmtx"]["min_edge"],
                max_edge=dec_cfg["pylibdmtx"]["max_edge"],
            ),
        }

        primary = dec_cfg.get("primary_decoder")
        if primary and primary in decoder_map:
            decoders.append(decoder_map[primary]())

        fallback = dec_cfg.get("fallback_decoder")
        if fallback and fallback in decoder_map:
            decoders.append(decoder_map[fallback]())

        if not decoders:
            decoders.append(ZxingDecoder())

        return FallbackDecoder(decoders)
