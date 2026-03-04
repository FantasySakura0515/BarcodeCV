import logging
import time

import numpy as np

from .decoder import DataMatrixDecoder, DecodeResult

logger = logging.getLogger("barcodecv.decoding")


class PylibdmtxDecoder(DataMatrixDecoder):
    """DataMatrix decoder using pylibdmtx."""

    def __init__(
        self,
        timeout_ms: int = 3000,
        max_count: int = 1,
        shrink: int = 1,
        threshold: int = 50,
        min_edge: int = 10,
        max_edge: int = 100,
    ):
        self._timeout_ms = timeout_ms
        self._max_count = max_count
        self._shrink = shrink
        self._threshold = threshold
        self._min_edge = min_edge
        self._max_edge = max_edge

    def decode(self, image: np.ndarray) -> list[DecodeResult]:
        from PIL import Image
        from pylibdmtx.pylibdmtx import decode as dmtx_decode

        start = time.perf_counter()
        try:
            # pylibdmtx works with PIL images
            if len(image.shape) == 3:
                import cv2
                rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
            else:
                rgb = image
            pil_image = Image.fromarray(rgb)

            decoded = dmtx_decode(
                pil_image,
                timeout=self._timeout_ms,
                max_count=self._max_count,
                shrink=self._shrink,
                threshold=self._threshold,
                min_edge=self._min_edge,
                max_edge=self._max_edge,
            )
            elapsed = (time.perf_counter() - start) * 1000

            results = []
            for item in decoded:
                content = item.data.decode("utf-8")
                results.append(
                    DecodeResult(
                        content=content,
                        decoder_used=self.name(),
                        decode_time_ms=elapsed,
                        success=True,
                    )
                )

            if not results:
                return [
                    DecodeResult(
                        content="",
                        decoder_used=self.name(),
                        decode_time_ms=elapsed,
                        success=False,
                        error_message="No DataMatrix found",
                    )
                ]

            logger.debug(
                "pylibdmtx decoded %d codes in %.1fms", len(results), elapsed
            )
            return results

        except Exception as e:
            elapsed = (time.perf_counter() - start) * 1000
            logger.warning("pylibdmtx decode failed: %s", e)
            return [
                DecodeResult(
                    content="",
                    decoder_used=self.name(),
                    decode_time_ms=elapsed,
                    success=False,
                    error_message=str(e),
                )
            ]

    def name(self) -> str:
        return "pylibdmtx"
