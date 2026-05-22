import pytest

from backend.camera import camarray_guard


def _config(
    *,
    source_type: str = "arducam",
    camera_num: int | str = 0,
    strict: bool = True,
) -> dict:
    return {
        "cameras": {
            "main": {
                "type": source_type,
                "camera_num": camera_num,
            }
        },
        "camarray": {
            "mode": "dual",
            "active_channels": [0, 1],
        },
        "system": {
            "camarray_startup_strict": strict,
        },
    }


def test_evaluate_camarray_startup_skips_when_main_is_not_arducam():
    report = camarray_guard.evaluate_camarray_startup(_config(source_type="opencv"))

    assert report["enabled"] is False
    assert report["checked"] is False
    assert report["ready"] is True
    assert any("startup check skipped" in message for message in report["warnings"])


def test_evaluate_camarray_startup_skips_hardware_checks_off_rpi():
    report = camarray_guard.evaluate_camarray_startup(_config(), is_rpi=False)

    assert report["enabled"] is True
    assert report["checked"] is False
    assert report["ready"] is True
    assert any("Not running on Raspberry Pi" in message for message in report["warnings"])


def test_evaluate_camarray_startup_reports_missing_picamera2(monkeypatch):
    monkeypatch.setattr(camarray_guard, "_is_picamera2_available", lambda: False)

    report = camarray_guard.evaluate_camarray_startup(_config(), is_rpi=True)

    assert report["checked"] is True
    assert report["ready"] is False
    assert any("picamera2" in message for message in report["errors"])


def test_evaluate_camarray_startup_warns_when_multiple_devices(monkeypatch):
    monkeypatch.setattr(camarray_guard, "_is_picamera2_available", lambda: True)

    report = camarray_guard.evaluate_camarray_startup(
        _config(),
        is_rpi=True,
        available_cams=[{"Num": 0}, {"Num": 2}],
    )

    assert report["checked"] is True
    assert report["ready"] is True
    assert report["available_nums"] == [0, 2]
    assert any("multiple camera devices detected" in message for message in report["warnings"])


def test_evaluate_camarray_startup_handles_invalid_camera_num(monkeypatch):
    monkeypatch.setattr(camarray_guard, "_is_picamera2_available", lambda: True)

    report = camarray_guard.evaluate_camarray_startup(
        _config(camera_num="bad"),
        is_rpi=True,
        available_cams=[{"Num": 0}],
    )

    assert report["configured_camera_num"] == 0
    assert report["ready"] is True


def test_run_camarray_startup_check_raises_when_strict_and_not_ready(monkeypatch):
    monkeypatch.setattr(camarray_guard, "_is_raspberry_pi", lambda: True)
    monkeypatch.setattr(camarray_guard, "_is_picamera2_available", lambda: False)

    with pytest.raises(RuntimeError, match="CamArray startup check failed"):
        camarray_guard.run_camarray_startup_check(_config(strict=True))


def test_run_camarray_startup_check_allows_not_ready_when_not_strict(monkeypatch):
    monkeypatch.setattr(camarray_guard, "_is_raspberry_pi", lambda: True)
    monkeypatch.setattr(camarray_guard, "_is_picamera2_available", lambda: False)

    report = camarray_guard.run_camarray_startup_check(_config(strict=False))
    assert report["strict"] is False
    assert report["ready"] is False


def test_run_camarray_startup_check_parses_string_false_strict(monkeypatch):
    monkeypatch.setattr(camarray_guard, "_is_raspberry_pi", lambda: True)
    monkeypatch.setattr(camarray_guard, "_is_picamera2_available", lambda: False)

    cfg = _config(strict=True)
    cfg["system"]["camarray_startup_strict"] = "false"

    report = camarray_guard.run_camarray_startup_check(cfg)
    assert report["strict"] is False
    assert report["ready"] is False
