import logging
import time

import numpy as np

from .decoder import DataMatrixDecoder, DecodeResult

logger = logging.getLogger("barcodecv.decoding")


class ZxingDecoder(DataMatrixDecoder):
    """DataMatrix decoder using zxing-cpp."""

    def decode(self, image: np.ndarray) -> list[DecodeResult]:
        import zxingcpp

        start = time.perf_counter()
        try:
            barcodes = zxingcpp.read_barcodes(
                image, formats=zxingcpp.BarcodeFormat.DataMatrix
            )
            elapsed = (time.perf_counter() - start) * 1000

            results = []
            for barcode in barcodes:
                results.append(
                    DecodeResult(
                        content=barcode.text,
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
                "zxing decoded %d codes in %.1fms", len(results), elapsed
            )
            return results

        except Exception as e:
            elapsed = (time.perf_counter() - start) * 1000
            logger.warning("zxing decode failed: %s", e)
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
        return "zxing-cpp"
