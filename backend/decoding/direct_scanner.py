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
            image_height = image.shape[0]
            for item in decoded:
                content = item.data.decode("utf-8")
                # pylibdmtx returns Rect(left, top, width, height)
                # `top` is measured from the image bottom, so convert it back
                # to OpenCV's top-left origin before exposing the bbox.
                rect = item.rect
                x1 = rect.left
                x2 = rect.left + rect.width
                y2 = image_height - rect.top
                y1 = y2 - rect.height

                # If shrink was used, scale coordinates back
                if self._shrink > 1:
                    x1 *= self._shrink
                    y1 *= self._shrink
                    x2 *= self._shrink
                    y2 *= self._shrink

                x1 = max(0, int(x1))
                y1 = max(0, int(y1))
                x2 = max(x1, int(x2))
                y2 = max(y1, int(y2))

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
    """Scan entire image for multiple DataMatrix codes using zxing-cpp.

    Supports trying multiple binarizers to increase recognition rate.
    """

    def __init__(self, try_harder: bool = True):
        """
        Args:
            try_harder: When True, also tries GlobalHistogram and FixedThreshold
                        binarizers in addition to the default LocalAverage.
                        Increases recognition rate at the cost of extra CPU time.
        """
        self._try_harder = try_harder

    def scan(self, image: np.ndarray) -> list[ScanResult]:
        """Scan image for all DataMatrix codes. Returns list of ScanResult."""
        import zxingcpp

        start = time.perf_counter()

        try:
            binarizers = [zxingcpp.Binarizer.LocalAverage]
            if self._try_harder:
                binarizers += [
                    zxingcpp.Binarizer.GlobalHistogram,
                    zxingcpp.Binarizer.FixedThreshold,
                ]

            all_contents: set[str] = set()
            results: list[ScanResult] = []

            for binarizer in binarizers:
                barcodes = zxingcpp.read_barcodes(
                    image,
                    formats=zxingcpp.BarcodeFormat.DataMatrix,
                    binarizer=binarizer,
                )
                for barcode in barcodes:
                    text = barcode.text
                    if not text or text in all_contents:
                        continue
                    all_contents.add(text)
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
                        content=text,
                        bbox=(x1, y1, x2, y2),
                        scanner_used="zxing-cpp",
                        scan_time_ms=0,
                        success=True,
                    ))

            elapsed = (time.perf_counter() - start) * 1000
            for r in results:
                r.scan_time_ms = elapsed

            logger.info("zxing-cpp found %d codes in %.1fms", len(results), elapsed)
            return results if results else [ScanResult(
                content="",
                bbox=(0, 0, 0, 0),
                scanner_used="zxing-cpp",
                scan_time_ms=elapsed,
                success=False,
            )]

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


class DynamsoftScanner:
    """Scan entire image for DataMatrix codes using Dynamsoft Barcode Reader.

    Dynamsoft handles both detection and decoding in a single optimized pass,
    making it significantly faster and more accurate than the pylibdmtx/zxing
    pipeline — especially for distant or blurry codes.
    """

    _license_initialized = False
    _cvr_instance: "CaptureVisionRouter | None" = None

    def __init__(
        self,
        license_key: str = "DLS2eyJvcmdhbml6YXRpb25JRCI6IjIwMDAwMSJ9",
        template: str = "speed_first",
    ):
        self._license_key = license_key
        self._template_name = template
        self._ensure_initialized()

    def _ensure_initialized(self) -> None:
        if DynamsoftScanner._cvr_instance is not None:
            return
        try:
            from dynamsoft_barcode_reader_bundle import (
                CaptureVisionRouter,
                EnumBarcodeFormat,
                EnumErrorCode,
                EnumPresetTemplate,
                LicenseManager,
            )

            if not DynamsoftScanner._license_initialized:
                err, msg = LicenseManager.init_license(self._license_key)
                if err != EnumErrorCode.EC_OK and err != EnumErrorCode.EC_LICENSE_WARNING:
                    logger.warning("Dynamsoft license init failed: %s (code %d)", msg, err)
                else:
                    logger.info("Dynamsoft license initialized OK")
                DynamsoftScanner._license_initialized = True

            cvr = CaptureVisionRouter()

            # Configure for DataMatrix-only scanning
            template = self._resolve_template()
            err, msg, settings = cvr.get_simplified_settings(template)
            if err == EnumErrorCode.EC_OK:
                settings.barcode_settings.barcode_format_ids = EnumBarcodeFormat.BF_DATAMATRIX
                settings.barcode_settings.expected_barcodes_count = 0  # find all
                cvr.update_settings(template, settings)

            DynamsoftScanner._cvr_instance = cvr
            logger.info("Dynamsoft CaptureVisionRouter initialized (template: %s)", self._template_name)
        except ImportError:
            logger.warning("dynamsoft_barcode_reader_bundle not installed, DynamsoftScanner unavailable")
            raise
        except Exception as exc:
            logger.warning("Dynamsoft initialization failed: %s", exc)
            raise

    def _resolve_template(self) -> str:
        from dynamsoft_barcode_reader_bundle import EnumPresetTemplate

        templates = {
            "speed_first": EnumPresetTemplate.PT_READ_BARCODES_SPEED_FIRST,
            "read_rate_first": EnumPresetTemplate.PT_READ_BARCODES_READ_RATE_FIRST,
            "default": EnumPresetTemplate.PT_READ_BARCODES,
        }
        return templates.get(self._template_name, EnumPresetTemplate.PT_READ_BARCODES_SPEED_FIRST)

    def scan(self, image: np.ndarray) -> list[ScanResult]:
        from dynamsoft_barcode_reader_bundle import (
            EnumErrorCode,
            EnumImagePixelFormat,
            ImageData,
        )

        start = time.perf_counter()
        cvr = DynamsoftScanner._cvr_instance
        if cvr is None:
            return [ScanResult(
                content="", bbox=(0, 0, 0, 0), scanner_used="dynamsoft",
                scan_time_ms=0, success=False, error_message="not initialized",
            )]

        try:
            # Convert numpy BGR image to Dynamsoft ImageData
            if len(image.shape) == 3:
                pixel_fmt = EnumImagePixelFormat.IPF_BGR_888
                img_bytes = image.tobytes()
                stride = image.strides[0]
            else:
                pixel_fmt = EnumImagePixelFormat.IPF_GRAYSCALED
                img_bytes = image.tobytes()
                stride = image.strides[0]

            image_data = ImageData(
                img_bytes, image.shape[1], image.shape[0],
                stride, pixel_fmt,
            )

            template = self._resolve_template()
            result = cvr.capture(image_data, template)

            elapsed = (time.perf_counter() - start) * 1000

            if result.get_error_code() != EnumErrorCode.EC_OK:
                err_msg = result.get_error_string()
                if result.get_error_code() != EnumErrorCode.EC_UNSUPPORTED_JSON_KEY_WARNING:
                    logger.warning("Dynamsoft capture error: %s", err_msg)

            barcode_result = result.get_decoded_barcodes_result()
            if barcode_result is None:
                logger.info("dynamsoft found 0 codes in %.1fms", elapsed)
                return [ScanResult(
                    content="", bbox=(0, 0, 0, 0), scanner_used="dynamsoft",
                    scan_time_ms=elapsed, success=False,
                )]

            items = barcode_result.get_items()
            if not items:
                logger.info("dynamsoft found 0 codes in %.1fms", elapsed)
                return [ScanResult(
                    content="", bbox=(0, 0, 0, 0), scanner_used="dynamsoft",
                    scan_time_ms=elapsed, success=False,
                )]

            results: list[ScanResult] = []
            seen: set[str] = set()
            for item in items:
                text = item.get_text()
                if not text or text in seen:
                    continue
                seen.add(text)

                location = item.get_location()
                points = location.points
                xs = [p.x for p in points]
                ys = [p.y for p in points]
                x1, y1 = min(xs), min(ys)
                x2, y2 = max(xs), max(ys)

                results.append(ScanResult(
                    content=text,
                    bbox=(max(0, x1), max(0, y1), max(0, x2), max(0, y2)),
                    scanner_used="dynamsoft",
                    scan_time_ms=elapsed,
                    success=True,
                ))

            logger.info("dynamsoft found %d codes in %.1fms", len(results), elapsed)
            return results if results else [ScanResult(
                content="", bbox=(0, 0, 0, 0), scanner_used="dynamsoft",
                scan_time_ms=elapsed, success=False,
            )]

        except Exception as exc:
            elapsed = (time.perf_counter() - start) * 1000
            logger.warning("dynamsoft scan failed: %s", exc)
            return [ScanResult(
                content="", bbox=(0, 0, 0, 0), scanner_used="dynamsoft",
                scan_time_ms=elapsed, success=False, error_message=str(exc),
            )]

    def name(self) -> str:
        return "dynamsoft"


class CompositeScanner:
    """Try multiple scanners and merge unique results.

    Strategy: Run primary scanner first. If it finds codes, use those.
    Then optionally run fallback scanner to catch any codes the primary missed.
    Deduplicates by comparing decoded content.
    """

    def __init__(
        self,
        primary: "PylibdmtxScanner | ZxingScanner | DynamsoftScanner",
        fallback: "PylibdmtxScanner | ZxingScanner | DynamsoftScanner | None" = None,
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

        merge = dec_cfg.get("merge_results", True)

        pylibdmtx = PylibdmtxScanner(
            timeout_ms=dmtx_cfg.get("timeout_ms", 5000),
            max_count=dmtx_cfg.get("max_count"),
            shrink=dmtx_cfg.get("shrink", 1),
            threshold=dmtx_cfg.get("threshold", 50),
            min_edge=dmtx_cfg.get("min_edge", 8),
            max_edge=dmtx_cfg.get("max_edge", 200),
        )
        zxing = ZxingScanner(try_harder=True)

        return CompositeScanner(primary=pylibdmtx, fallback=zxing, merge_results=merge)
