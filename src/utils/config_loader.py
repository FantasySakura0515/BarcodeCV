import copy
from pathlib import Path

import yaml


def deep_merge(base: dict, override: dict) -> dict:
    """Deep merge override into base, returning a new dict."""
    result = copy.deepcopy(base)
    for key, value in override.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = deep_merge(result[key], value)
        else:
            result[key] = copy.deepcopy(value)
    return result


def load_config(config_path: str | None = None) -> dict:
    """Load YAML config, merging user config over defaults."""
    default_path = Path(__file__).parent.parent.parent / "config" / "default.yaml"

    with open(default_path) as f:
        config = yaml.safe_load(f)

    if config_path and Path(config_path).exists():
        with open(config_path) as f:
            user_config = yaml.safe_load(f)
        if user_config:
            config = deep_merge(config, user_config)

    return config
