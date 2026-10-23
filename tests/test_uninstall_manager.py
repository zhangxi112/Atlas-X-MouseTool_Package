from pathlib import Path
from unittest.mock import patch

from services.uninstall_manager import UninstallManager


def test_uninstall_manager_detects_sibling_uninstaller(tmp_path) -> None:
    app_exe = tmp_path / "AtlasXCursorStudio.exe"
    app_exe.write_text("stub", encoding="utf-8")
    uninstaller = tmp_path / "unins000.exe"
    uninstaller.write_text("stub", encoding="utf-8")
    manager = UninstallManager()
    with patch('services.uninstall_manager.sys', frozen=True, executable=str(app_exe)):
        assert manager.get_uninstaller_path() == uninstaller


def test_uninstall_manager_returns_none_when_unavailable(tmp_path) -> None:
    app_exe = tmp_path / "AtlasXCursorStudio.exe"
    app_exe.write_text("stub", encoding="utf-8")
    manager = UninstallManager()
    with patch('services.uninstall_manager.sys', frozen=True, executable=str(app_exe)):
        assert manager.get_uninstaller_path() is None
