"""Resolve writable runtime storage independently of the install directory."""

from __future__ import annotations

import os
import tempfile
from pathlib import Path

from core.constants import APP_ID


def user_data_dir() -> Path:
    candidates = [
        Path(root) / APP_ID
        for key in ("APPDATA", "LOCALAPPDATA")
        if (root := os.environ.get(key))
    ]
    candidates.append(Path.home() / f".{APP_ID}")
    last_error = None
    for candidate in candidates:
        try:
            candidate.mkdir(parents=True, exist_ok=True)
            with tempfile.TemporaryFile(dir=candidate):
                pass
            return candidate
        except OSError as exc:
            last_error = exc
    raise OSError("No writable user data directory is available") from last_error
