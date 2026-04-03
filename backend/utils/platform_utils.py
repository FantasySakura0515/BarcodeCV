from __future__ import annotations

import functools
import importlib.util
import sys


def _as_int(value, default: int) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _as_bool(value, default: bool = False) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value)
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in {"1", "true", "yes", "y", "on"}:
            return True
        if normalized in {"0", "false", "no", "n", "off", ""}:
            return False
    return default


@functools.lru_cache(maxsize=1)
def _is_raspberry_pi() -> bool:
    if not sys.platform.startswith("linux"):
        return False

    model_paths = [
        "/proc/device-tree/model",
        "/sys/firmware/devicetree/base/model",
    ]
    for model_path in model_paths:
        try:
            with open(model_path, "r", encoding="utf-8", errors="ignore") as model_file:
                if "raspberry pi" in model_file.read().lower():
                    return True
        except OSError:
            pass

    try:
        with open("/proc/cpuinfo", "r", encoding="utf-8", errors="ignore") as cpuinfo_file:
            cpuinfo = cpuinfo_file.read().lower()
            return "raspberry pi" in cpuinfo or "bcm27" in cpuinfo
    except OSError:
        return False


@functools.lru_cache(maxsize=1)
def _is_picamera2_available() -> bool:
    return importlib.util.find_spec("picamera2") is not None
