"""Exercise a packaged build without changing the user's desktop settings."""

from __future__ import annotations

import json
import os
from pathlib import Path
import sys
from tempfile import TemporaryDirectory


def run_self_test(report_path: str | Path) -> int:
    report_path = Path(report_path).resolve()
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report = {"status": "failed", "frozen": bool(getattr(sys, "frozen", False))}
    previous_env = {key: os.environ.get(key) for key in ("APPDATA", "LOCALAPPDATA", "QT_QPA_PLATFORM")}
    window = None
    app = None
    try:
        os.environ["QT_QPA_PLATFORM"] = "offscreen"
        from PIL import Image
        import onnxruntime
        from PySide6.QtWidgets import QApplication

        from app.bootstrap import AppContext
        from core.constants import APP_VERSION, DEFAULT_CONFIG_PATH
        from services.config_manager import ConfigManager
        from services.cursor_manager import CursorManager
        from services.enhancement_manager import EnhancementManager
        from services.image_pipeline import ImagePipeline
        from services.logger import LoggerService
        from services.overlay_manager import OverlayManager
        from services.startup_manager import StartupManager
        from services.uninstall_manager import UninstallManager
        from ui.main_window import MainWindow

        report["version"] = APP_VERSION
        if not DEFAULT_CONFIG_PATH.is_file():
            raise RuntimeError("Bundled default configuration is missing")
        app = QApplication.instance() or QApplication([])

        def disallow_system_change(*args, **kwargs):
            raise RuntimeError("System changes are disabled during package self-test")

        with TemporaryDirectory(prefix="atlasx-self-test-", dir=report_path.parent) as directory:
            os.environ["APPDATA"] = directory
            os.environ["LOCALAPPDATA"] = directory
            config_manager = ConfigManager()
            config = config_manager.load()
            config_manager.save(config)
            if config_manager.load() != config:
                raise RuntimeError("Configuration round-trip failed")
            cursor_manager = CursorManager(config_manager.user_data_dir / "builtin_cursors")
            cursor_manager.apply_cursor_file = disallow_system_change
            cursor_manager.restore_system_default = disallow_system_change
            assets = cursor_manager.list_builtin_themes()
            if len(assets) != 10 or not all(asset.cursor_path.is_relative_to(cursor_manager.bundled_dir) for asset in assets):
                raise RuntimeError("Bundled cursor assets are incomplete")
            pipeline = ImagePipeline(config_manager.user_data_dir / "custom_cursors", cursor_manager)
            source = Path(directory) / "sample.png"
            Image.new("RGBA", (32, 32), (255, 0, 0, 255)).save(source)
            project = pipeline.import_image(source)
            pipeline.generate_preview(project, 100, 32, 32)
            cursor = pipeline.generate_cursor(project, 100, 32, 32)
            if cursor.stat().st_size <= 22:
                raise RuntimeError("Generated cursor is empty")
            overlay = OverlayManager()
            overlay.attach_application(app, lambda: config)
            enhancement = EnhancementManager(cursor_manager, overlay, lambda: config)
            startup = StartupManager()
            startup.get_registered_command = lambda: None
            startup.set_enabled = disallow_system_change
            startup.repair_if_needed = disallow_system_change
            uninstall = UninstallManager()
            uninstall.launch = disallow_system_change
            context = AppContext(config_manager, LoggerService(config_manager.user_log_dir), config,
                                 cursor_manager, overlay, enhancement, pipeline, startup, uninstall)
            window = MainWindow(context)
            if window.theme_list.count() != 10 or window.hotkey_edit.keySequence().isEmpty():
                raise RuntimeError("Main window initialization failed")
            app.processEvents()
            window.prepare_for_exit()
            window = None
            enhancement.stop()
            overlay.shutdown()
            report.update(status="passed", builtin_themes=len(assets),
                          onnx_providers=onnxruntime.get_available_providers(),
                          checks=["bundled_resources", "configuration", "cursor_generation", "main_window", "onnx_import"])
    except Exception as exc:
        report["error"] = f"{type(exc).__name__}: {exc}"
    finally:
        if window is not None:
            window.prepare_for_exit()
        for key, value in previous_env.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value
        report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return 0 if report["status"] == "passed" else 1
