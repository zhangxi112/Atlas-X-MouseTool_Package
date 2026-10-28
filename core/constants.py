"""Application-level constants."""

from __future__ import annotations

from pathlib import Path

APP_NAME = "Atlas-X Cursor Studio"
APP_ID = "atlas_x_cursor_studio"
APP_VERSION = "1.0.1"
ROOT_DIR = Path(__file__).resolve().parent.parent
DEFAULT_CONFIG_PATH = ROOT_DIR / "configs" / "default_config.json"
