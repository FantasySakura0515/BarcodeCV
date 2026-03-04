"""Direct DataMatrix scanning - detect AND decode in one pass using library APIs.

This eliminates the need for a YOLO model. Both pylibdmtx and zxing-cpp
can scan an entire image and find multiple DataMatrix codes directly.
"""

import logging
import time
from dataclasses import dataclass

import numpy as np

logger = logging.getLogger("barcodecv.scanner")


@dataclass
class ScanResult:
    """Result of a direct scan (detection + decoding combined)."""

    content: str
    bbox: tuple[int, int, int, int]  # (x1, y1, x2, y2)
    scanner_used: str
    scan_time_ms: float
    success: bool
    error_message: str | None = None


class PylibdmtxScanner:
    """Scan entire image for multiple DataMatrix codes using pylibdmtx."""

    def __init__(
        self,
        timeout_ms: int = 5000,
        max_count: int | None = None,
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

    def scan(self, image: np.ndarray) -> list[ScanResult]:
        """Scan image for all DataMatrix codes. Returns list of ScanResult."""
        from PIL import Image
        from pylibdmtx.pylibdmtx import decode as dmtx_decode

        import cv2

        start = time.perf_counter()

        # Convert to PIL Image
        if len(image.shape) == 3:
            rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
        else:
            rgb = image
        pil_image = Image.fromarray(rgb)

        # Build decode kwargs
        kwargs = {
            "timeout": self._timeout_ms,
            "shrink": self._shrink,
            "threshold": self._threshold,
            "min_edge": self._min_edge,
            "max_edge": self._max_edge,
        }
        if self._max_count is not None:
            kwargs["max_count"] = self._max_count

        try:
            decoded = dmtx_decode(pil_image, **kwargs)
            elapsed = (time.perf_counter() - start) * 1000

            results = []
            for item in decoded:
                content = item.data.decode("utf-8")
                # pylibdmtx returns Rect(left, top, width, height)
                rect = item.rect
                x1 = rect.left
                y1 = rect.top
                x2 = rect.left + rect.width
                y2 = rect.top + rect.height

                # If shrink was used, scale coordinates back
                if self._shrink > 1:
                    x1 *= self._shrink
                    y1 *= self._shrink
                    x2 *= self._shrink
                    y2 *= self._shrink

                results.append(ScanResult(
                    content=content,
                    bbox=(x1, y1, x2, y2),
                    scanner_used="pylibdmtx",
                    scan_time_ms=elapsed,
                    success=True,
                ))

            logger.info("pylibdmtx found %d codes in %.1fms", len(results), elapsed)
            return results

        except Exception as e:
            elapsed = (time.perf_counter() - start) * 1000
            logger.warning("pylibdmtx scan failed: %s", e)
            return [ScanResult(
                content="",
                bbox=(0, 0, 0, 0),
                scanner_used="pylibdmtx",
                scan_time_ms=elapsed,
                success=False,
                error_message=str(e),
            )]

    def name(self) -> str:
        return "pylibdmtx"


class ZxingScanner:
    """Scan entire image for multiple DataMatrix codes using zxing-cpp."""

    def scan(self, image: np.ndarray) -> list[ScanResult]:
        """Scan image for all DataMatrix codes. Returns list of ScanResult."""
        import zxingcpp

        start = time.perf_counter()

        try:
            barcodes = zxingcpp.read_barcodes(
                image, formats=zxingcpp.BarcodeFormat.DataMatrix
            )
            elapsed = (time.perf_counter() - start) * 1000

            results = []
            for barcode in barcodes:
                # Extract bounding box from position
                pos = barcode.position
                points = [
                    (pos.top_left.x, pos.top_left.y),
                    (pos.top_right.x, pos.top_right.y),
                    (pos.bottom_right.x, pos.bottom_right.y),
                    (pos.bottom_left.x, pos.bottom_left.y),
                ]
                xs = [p[0] for p in points]
                ys = [p[1] for p in points]
                x1, y1, x2, y2 = min(xs), min(ys), max(xs), max(ys)

                results.append(ScanResult(
                    content=barcode.text,
                    bbox=(x1, y1, x2, y2),
                    scanner_used="zxing-cpp",
                    scan_time_ms=elapsed,
                    success=True,
                ))

            logger.info("zxing-cpp found %d codes in %.1fms", len(results), elapsed)
            return results

        except Exception as e:
            elapsed = (time.perf_counter() - start) * 1000
            logger.warning("zxing-cpp scan failed: %s", e)
            return [ScanResult(
                content="",
                bbox=(0, 0, 0, 0),
                scanner_used="zxing-cpp",
                scan_time_ms=elapsed,
                success=False,
                error_message=str(e),
            )]

    def name(self) -> str:
        return "zxing-cpp"


class CompositeScanner:
    """Try multiple scanners and merge unique results.

    Strategy: Run primary scanner first. If it finds codes, use those.
    Then optionally run fallback scanner to catch any codes the primary missed.
    Deduplicates by comparing decoded content.
    """

    def __init__(
        self,
        primary: PylibdmtxScanner | ZxingScanner,
        fallback: PylibdmtxScanner | ZxingScanner | None = None,
        merge_results: bool = True,
    ):
        self._primary = primary
        self._fallback = fallback
        self._merge = merge_results

    def scan(self, image: np.ndarray) -> list[ScanResult]:
        """Scan with primary, optionally merge with fallback results."""
        results = self._primary.scan(image)
        successful = [r for r in results if r.success]

        if self._fallback and self._merge:
            fallback_results = self._fallback.scan(image)
            # Merge: add fallback results whose content isn't already found
            existing_contents = {r.content for r in successful}
            for r in fallback_results:
                if r.success and r.content not in existing_contents:
                    successful.append(r)
                    existing_contents.add(r.content)

        elif self._fallback and not successful:
            # Only use fallback if primary found nothing
            successful = [r for r in self._fallback.scan(image) if r.success]

        return successful if successful else results  # return failures if nothing worked

    def name(self) -> str:
        names = [self._primary.name()]
        if self._fallback:
            names.append(self._fallback.name())
        return f"CompositeScanner({' + '.join(names)})"

    @staticmethod
    def from_config(config: dict) -> "CompositeScanner":
        """Create CompositeScanner from config."""
        dec_cfg = config.get("decoding", {})
        dmtx_cfg = dec_cfg.get("pylibdmtx", {})

        primary_name = dec_cfg.get("primary_decoder", "pylibdmtx")
        fallback_name = dec_cfg.get("fallback_decoder", "zxing")
        merge = dec_cfg.get("merge_results", True)

        pylibdmtx = PylibdmtxScanner(
            timeout_ms=dmtx_cfg.get("timeout_ms", 5000),
            max_count=dmtx_cfg.get("max_count"),
            shrink=dmtx_cfg.get("shrink", 1),
            threshold=dmtx_cfg.get("threshold", 50),
            min_edge=dmtx_cfg.get("min_edge", 10),
            max_edge=dmtx_cfg.get("max_edge", 100),
        )
        zxing = ZxingScanner()

        scanner_map = {"pylibdmtx": pylibdmtx, "zxing": zxing}

        primary = scanner_map.get(primary_name, pylibdmtx)
        fallback = scanner_map.get(fallback_name) if fallback_name else None

        return CompositeScanner(primary=primary, fallback=fallback, merge_results=merge)
