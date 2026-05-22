import copy
from pathlib import Path

import yaml

from .platform_utils import _as_bool, _as_int


def deep_merge(base: dict, override: dict) -> dict:
    """Deep merge override into base, returning a new dict."""
    result = copy.deepcopy(base)
    for key, value in override.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = deep_merge(result[key], value)
        else:
            result[key] = copy.deepcopy(value)
    return result


def normalize_runtime_config(config: dict) -> dict:
    """Normalize camera/camarray fields to the single-main-camera runtime shape."""
    normalized = copy.deepcopy(config or {})

    cameras_cfg = normalized.get("cameras", {})
    if not isinstance(cameras_cfg, dict):
        cameras_cfg = {}

    main_cfg: dict = {}
    if isinstance(cameras_cfg.get("main"), dict):
        main_cfg = copy.deepcopy(cameras_cfg["main"])
    elif isinstance(cameras_cfg.get("global"), dict):
        # Backward compatibility for older dual-camera config files.
        main_cfg = copy.deepcopy(cameras_cfg["global"])
    else:
        for value in cameras_cfg.values():
            if isinstance(value, dict):
                main_cfg = copy.deepcopy(value)
                break

    main_cfg.setdefault("type", "arducam")
    main_cfg["camera_num"] = _as_int(main_cfg.get("camera_num", 0), 0)
    main_cfg["width"] = _as_int(main_cfg.get("width", 1920), 1920)
    main_cfg["height"] = _as_int(main_cfg.get("height", 1080), 1080)
    main_cfg["allow_opencv_fallback"] = _as_bool(main_cfg.get("allow_opencv_fallback", False))
    main_cfg.setdefault("role", "aggregated")
    normalized["cameras"] = {"main": main_cfg}

    camarray_cfg = normalized.get("camarray", {})
    if not isinstance(camarray_cfg, dict):
        camarray_cfg = {}

    mode = str(camarray_cfg.get("mode", "dual")).lower()
    if mode not in {"single", "dual", "quad"}:
        mode = "dual"
    camarray_cfg["mode"] = mode

    layout = str(camarray_cfg.get("layout", "horizontal")).lower()
    if layout not in {"horizontal", "vertical", "grid"}:
        layout = "horizontal"
    camarray_cfg["layout"] = layout

    channels = camarray_cfg.get("active_channels", [0, 1])
    parsed_channels: list[int] = []
    if isinstance(channels, list):
        for value in channels:
            try:
                parsed = int(value)
                if parsed >= 0:
                    parsed_channels.append(parsed)
            except (TypeError, ValueError):
                continue
    camarray_cfg["active_channels"] = parsed_channels or [0, 1]
    normalized["camarray"] = camarray_cfg

    system_cfg = normalized.get("system", {})
    if not isinstance(system_cfg, dict):
        system_cfg = {}
    system_cfg["camarray_startup_strict"] = _as_bool(system_cfg.get("camarray_startup_strict", True), True)
    normalized["system"] = system_cfg

    return normalized


def load_config(config_path: str | None = None) -> dict:
    """Load YAML config, merging user config over defaults."""
    default_path = Path(__file__).parent.parent.parent / "config" / "default.yaml"

    with open(default_path, encoding="utf-8") as f:
        config = yaml.safe_load(f)

    if config_path and Path(config_path).exists():
        with open(config_path, encoding="utf-8") as f:
            user_config = yaml.safe_load(f)
        if user_config:
            config = deep_merge(config, user_config)

    return normalize_runtime_config(config)
