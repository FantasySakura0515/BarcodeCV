from __future__ import annotations

from .picamera_source import PiCameraSource
from ..utils.platform_utils import _as_bool, _as_int, _is_picamera2_available, _is_raspberry_pi


def _extract_available_nums(available_cams: list[dict]) -> list[int]:
    nums: list[int] = []
    for i, info in enumerate(available_cams):
        raw_num = info.get("Num", i)
        try:
            nums.append(int(raw_num))
        except (TypeError, ValueError):
            nums.append(i)
    return nums


def evaluate_camarray_startup(
    config: dict,
    *,
    available_cams: list[dict] | None = None,
    is_rpi: bool | None = None,
) -> dict:
    cameras_cfg = config.get("cameras", {})
    main_cfg = cameras_cfg.get("main", {}) if isinstance(cameras_cfg, dict) else {}
    source_type = str(main_cfg.get("type", "")).lower()

    camarray_cfg = config.get("camarray", {})
    mode = str(camarray_cfg.get("mode", "dual")).lower()
    raw_channels = camarray_cfg.get("active_channels", [0, 1])
    channels: list[int] = []
    if isinstance(raw_channels, list):
        for value in raw_channels:
            channels.append(_as_int(value, -1))
        channels = [value for value in channels if value >= 0]

    configured_num = _as_int(main_cfg.get("camera_num", 0), 0)
    report = {
        "enabled": source_type == "arducam",
        "checked": False,
        "ready": True,
        "is_raspberry_pi": False,
        "configured_camera_num": configured_num,
        "available_nums": [],
        "mode": mode,
        "active_channels": channels or [0, 1],
        "warnings": [],
        "errors": [],
    }

    if not report["enabled"]:
        report["warnings"].append("cameras.main.type is not 'arducam'; CamArray startup check skipped.")
        return report

    if is_rpi is None:
        is_rpi = _is_raspberry_pi()
    report["is_raspberry_pi"] = bool(is_rpi)

    if not is_rpi:
        report["warnings"].append("Not running on Raspberry Pi; hardware startup check skipped.")
        return report

    report["checked"] = True

    if not _is_picamera2_available():
        report["errors"].append("picamera2 is not importable.")
        report["ready"] = False
        return report

    if available_cams is None:
        try:
            available_cams = PiCameraSource.available_cameras()
        except Exception as exc:  # noqa: BLE001
            report["errors"].append(f"failed to enumerate cameras: {exc}")
            report["ready"] = False
            return report

    available_nums = _extract_available_nums(available_cams)
    report["available_nums"] = available_nums

    if not available_nums:
        report["errors"].append("no CSI camera detected by picamera2/libcamera.")
    elif configured_num not in available_nums:
        report["errors"].append(
            f"configured camera_num={configured_num} not found (available={available_nums})."
        )

    if len(available_nums) > 1:
        report["warnings"].append(
            f"multiple camera devices detected ({available_nums}); CamArray flow expects one aggregated device."
        )

    if mode != "dual":
        report["warnings"].append(
            f"camarray.mode is '{mode}'. Recommended mode is 'dual' for current runtime."
        )

    if mode == "dual" and report["active_channels"] not in ([0, 1], [2, 3]):
        report["warnings"].append(
            f"camarray.active_channels={report['active_channels']} is uncommon for dual mode."
        )

    report["ready"] = len(report["errors"]) == 0
    return report


def run_camarray_startup_check(config: dict, *, strict: bool | None = None) -> dict:
    report = evaluate_camarray_startup(config)
    if strict is None:
        strict = _as_bool(config.get("system", {}).get("camarray_startup_strict", True), True)
    report["strict"] = _as_bool(strict, True)

    if report["strict"] and report["checked"] and report["errors"]:
        issues = "; ".join(report["errors"])
        raise RuntimeError(f"CamArray startup check failed: {issues}")

    return report
