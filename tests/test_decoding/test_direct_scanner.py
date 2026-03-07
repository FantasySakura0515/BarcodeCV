import sys
from types import ModuleType, SimpleNamespace
from unittest.mock import MagicMock

import numpy as np

from backend.decoding.direct_scanner import (
    CompositeScanner,
    PylibdmtxScanner,
    ScanResult,
    ZxingScanner,
)


class TestCompositeScanner:
    def _make_result(self, content: str, scanner: str = "test") -> ScanResult:
        return ScanResult(
            content=content,
            bbox=(10, 10, 100, 100),
            scanner_used=scanner,
            scan_time_ms=50.0,
            success=True,
        )

    def test_primary_only(self):
        primary = MagicMock()
        primary.name.return_value = "primary"
        primary.scan.return_value = [self._make_result("CODE1", "primary")]

        scanner = CompositeScanner(primary=primary, fallback=None)
        results = scanner.scan(np.zeros((100, 100, 3), dtype=np.uint8))

        assert len(results) == 1
        assert results[0].content == "CODE1"

    def test_merge_deduplicates(self):
        primary = MagicMock()
        primary.name.return_value = "primary"
        primary.scan.return_value = [
            self._make_result("CODE1", "primary"),
            self._make_result("CODE2", "primary"),
        ]

        fallback = MagicMock()
        fallback.name.return_value = "fallback"
        fallback.scan.return_value = [
            self._make_result("CODE2", "fallback"),  # duplicate
            self._make_result("CODE3", "fallback"),  # unique
        ]

        scanner = CompositeScanner(primary=primary, fallback=fallback, merge_results=True)
        results = scanner.scan(np.zeros((100, 100, 3), dtype=np.uint8))

        contents = {r.content for r in results}
        assert contents == {"CODE1", "CODE2", "CODE3"}
        assert len(results) == 3

    def test_fallback_when_primary_fails(self):
        primary = MagicMock()
        primary.name.return_value = "primary"
        primary.scan.return_value = [
            ScanResult(
                content="", bbox=(0, 0, 0, 0), scanner_used="primary",
                scan_time_ms=10.0, success=False, error_message="nothing found",
            )
        ]

        fallback = MagicMock()
        fallback.name.return_value = "fallback"
        fallback.scan.return_value = [self._make_result("CODE1", "fallback")]

        scanner = CompositeScanner(primary=primary, fallback=fallback, merge_results=False)
        results = scanner.scan(np.zeros((100, 100, 3), dtype=np.uint8))

        assert len(results) == 1
        assert results[0].content == "CODE1"

    def test_from_config(self):
        config = {
            "decoding": {
                "primary_decoder": "pylibdmtx",
                "fallback_decoder": "zxing",
                "merge_results": True,
                "pylibdmtx": {
                    "timeout_ms": 3000,
                    "shrink": 1,
                    "threshold": 50,
                    "min_edge": 10,
                    "max_edge": 100,
                },
            }
        }
        scanner = CompositeScanner.from_config(config)
        assert "pylibdmtx" in scanner.name()
        assert "zxing" in scanner.name()


class TestPylibdmtxScanner:
    def test_converts_bottom_origin_bbox_to_top_origin(self):
        scanner = PylibdmtxScanner()
        image = np.zeros((100, 120, 3), dtype=np.uint8)

        pil_module = ModuleType("PIL")
        pil_module.Image = SimpleNamespace(fromarray=lambda array: array)

        pylibdmtx_package = ModuleType("pylibdmtx")
        pylibdmtx_module = ModuleType("pylibdmtx.pylibdmtx")
        pylibdmtx_module.decode = lambda *_args, **_kwargs: [
            SimpleNamespace(
                data=b"DM-001",
                rect=SimpleNamespace(left=10, top=30, width=20, height=15),
            )
        ]

        previous_modules = {
            name: sys.modules.get(name)
            for name in ("PIL", "pylibdmtx", "pylibdmtx.pylibdmtx")
        }

        sys.modules["PIL"] = pil_module
        sys.modules["pylibdmtx"] = pylibdmtx_package
        sys.modules["pylibdmtx.pylibdmtx"] = pylibdmtx_module

        try:
            results = scanner.scan(image)
        finally:
            for name, module in previous_modules.items():
                if module is None:
                    sys.modules.pop(name, None)
                else:
                    sys.modules[name] = module

        assert len(results) == 1
        assert results[0].bbox == (10, 55, 30, 70)
