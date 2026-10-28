"""Application entry point for Atlas-X Cursor Studio."""

from __future__ import annotations

import argparse
import logging
import sys
import traceback

from core.constants import APP_NAME


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument('--startup', action='store_true')
    parser.add_argument('--minimized', action='store_true')
    parser.add_argument('--self-test', metavar='REPORT_PATH')
    return parser.parse_known_args(sys.argv[1:])[0]


def install_exception_hook(context) -> None:
    from ui.dialog_utils import show_critical

    logger = logging.getLogger(__name__)
    default_hook = sys.excepthook

    def handle_exception(exc_type, exc_value, exc_traceback) -> None:
        if issubclass(exc_type, KeyboardInterrupt):
            default_hook(exc_type, exc_value, exc_traceback)
            return
        formatted = "".join(traceback.format_exception(exc_type, exc_value, exc_traceback))
        logger.error("Unhandled exception:\n%s", formatted)
        try:
            context.cursor_manager.restore_system_default()
        except Exception:
            logger.exception("Failed to restore cursor after unhandled exception")
        show_critical(None, context.config.appearance.theme_mode, APP_NAME, "程序发生未处理异常，已尝试恢复系统默认光标。")

    sys.excepthook = handle_exception


def main() -> int:
    args = _parse_args()
    if args.self_test:
        from app.self_test import run_self_test

        return run_self_test(args.self_test)
    from PySide6.QtWidgets import QApplication

    from app.bootstrap import bootstrap_app
    from services.tray_hotkey_manager import TrayHotkeyManager
    from ui.app_styles import apply_app_theme
    from ui.main_window import MainWindow

    context = bootstrap_app()
    app = QApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    app.setOrganizationName("张希")
    app.setQuitOnLastWindowClosed(False)
    apply_app_theme(app, context.config.appearance.theme_mode)

    install_exception_hook(context)
    context.overlay_manager.attach_application(app, lambda: context.config)
    context.enhancement_manager.start()

    window = MainWindow(context=context)
    app.aboutToQuit.connect(window.wait_for_background_task)
    tray_manager = TrayHotkeyManager(app=app, window=window, hotkey_sequence=context.config.highlight.hotkey, on_find_mouse=context.overlay_manager.trigger_find_mouse)
    tray_manager.start()
    app.aboutToQuit.connect(tray_manager.stop)
    app.aboutToQuit.connect(context.enhancement_manager.stop)
    app.aboutToQuit.connect(context.overlay_manager.shutdown)
    window.set_tray_manager(tray_manager)
    if not (args.startup or args.minimized):
        window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
