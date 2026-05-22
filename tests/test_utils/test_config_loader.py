from backend.utils.config_loader import normalize_runtime_config


def test_normalize_runtime_config_supports_legacy_global_camera_section():
    normalized = normalize_runtime_config(
        {
            "cameras": {
                "global": {
                    "type": "arducam",
                    "camera_num": "1",
                    "width": "1600",
                    "height": "900",
                    "allow_opencv_fallback": "true",
                }
            },
            "camarray": {
                "mode": "DUAL",
                "layout": "Horizontal",
                "active_channels": ["0", "1"],
            },
            "system": {},
        }
    )

    assert normalized["cameras"] == {
        "main": {
            "type": "arducam",
            "camera_num": 1,
            "width": 1600,
            "height": 900,
            "allow_opencv_fallback": True,
            "role": "aggregated",
        }
    }
    assert normalized["camarray"]["mode"] == "dual"
    assert normalized["camarray"]["layout"] == "horizontal"
    assert normalized["camarray"]["active_channels"] == [0, 1]
    assert normalized["system"]["camarray_startup_strict"] is True


def test_normalize_runtime_config_falls_back_to_safe_defaults_on_bad_values():
    normalized = normalize_runtime_config(
        {
            "cameras": {
                "main": {
                    "camera_num": "bad-value",
                    "width": None,
                    "height": "bad-value",
                    "allow_opencv_fallback": "no",
                }
            },
            "camarray": {
                "mode": "unexpected",
                "layout": "unexpected",
                "active_channels": ["x", -1, 2],
            },
            "system": {
                "camarray_startup_strict": "0",
            },
        }
    )

    main = normalized["cameras"]["main"]
    assert main["camera_num"] == 0
    assert main["width"] == 1920
    assert main["height"] == 1080
    assert main["allow_opencv_fallback"] is False
    assert main["type"] == "arducam"
    assert main["role"] == "aggregated"

    assert normalized["camarray"]["mode"] == "dual"
    assert normalized["camarray"]["layout"] == "horizontal"
    assert normalized["camarray"]["active_channels"] == [2]
    assert normalized["system"]["camarray_startup_strict"] is False
