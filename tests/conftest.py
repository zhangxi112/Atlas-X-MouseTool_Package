"""Keep automated checks away from the user's desktop and saved settings."""

import os
from unittest.mock import Mock

import pytest

os.environ["QT_QPA_PLATFORM"] = "offscreen"


@pytest.fixture(autouse=True)
def isolated_runtime(tmp_path, monkeypatch):
    from services import cursor_manager, enhancement_manager, startup_manager
    from services import tray_hotkey_manager, windows_foreground
    from services.logger import LoggerService

    monkeypatch.setenv("APPDATA", str(tmp_path / "appdata"))
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path / "localappdata"))
    # No test may change real system cursors, hotkeys, or startup registration.
    monkeypatch.setattr(cursor_manager, "USER32", Mock())
    monkeypatch.setattr(enhancement_manager, "USER32", None)
    monkeypatch.setattr(enhancement_manager, "WIN32_AVAILABLE", False)
    monkeypatch.setattr(windows_foreground, "WIN32_AVAILABLE", False)
    monkeypatch.setattr(startup_manager, "WINREG_AVAILABLE", False)
    monkeypatch.setattr(tray_hotkey_manager, "ctypes", Mock(windll=Mock()))
    monkeypatch.setattr(LoggerService, "configure", Mock())


@pytest.fixture(scope="session")
def qapp():
    from PySide6.QtWidgets import QApplication

    app = QApplication.instance() or QApplication([])
    yield app
