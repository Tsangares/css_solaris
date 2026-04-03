"""
Server configuration persistence for CSS Solaris.
Stores server-level settings like forum channel IDs.
"""

import json
import os
from typing import Dict, Any, Optional

CONFIG_PATH = "data/config.json"

DEFAULT_CONFIG = {
    "lobby_forum_id": None,
    "discussions_forum_id": None,
    "voting_forum_id": None,
}


def load_config() -> Dict[str, Any]:
    """Load server config, merging with defaults for any missing keys."""
    config = dict(DEFAULT_CONFIG)
    if os.path.exists(CONFIG_PATH):
        try:
            with open(CONFIG_PATH, 'r') as f:
                saved = json.load(f)
                config.update(saved)
        except (json.JSONDecodeError, FileNotFoundError):
            pass
    return config


def save_config(config: Dict[str, Any]):
    """Save server config to disk."""
    os.makedirs(os.path.dirname(CONFIG_PATH), exist_ok=True)
    with open(CONFIG_PATH, 'w') as f:
        json.dump(config, f, indent=2)


def get(key: str) -> Optional[Any]:
    """Get a single config value."""
    return load_config().get(key)


def set(key: str, value: Any):
    """Set a single config value and save."""
    config = load_config()
    config[key] = value
    save_config(config)
