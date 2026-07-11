import os

os.environ["QT_QPA_PLATFORM"] = "offscreen"

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication

from app.bootstrap import bootstrap_app
from ui.main_window import MainWindow


def test_main_window_smoke() -> None:
    app = QApplication.instance() or QApplication([])
    context = bootstrap_app()
    context.overlay_manager.attach_application(app, lambda: context.config)
    context.enhancement_manager.start()
    window = MainWindow(context)
    assert window.theme_list is not None
    assert window.theme_list.count() >= 10
    assert window.hotkey_edit is not None
    assert window.hotkey_edit.keySequence().toString()
    assert window.quick_hotkey_edit is not None
    assert window.pointer_size_spin is not None
    assert window.pointer_size_input_spin is not None
    assert window.shake_to_find_checkbox is not None
    assert window.shake_distance_input_spin is not None
    assert window.app_rules_edit is not None
    assert window.dynamic_cursor_checkbox is not None
    window._update_responsive_layout(900)
    assert all(splitter.orientation() == Qt.Orientation.Vertical for splitter in window._responsive_splitters)
    window._update_responsive_layout(1200)
    assert all(splitter.orientation() == Qt.Orientation.Horizontal for splitter in window._responsive_splitters)
    window.prepare_for_exit()
    context.enhancement_manager.stop()
    app.processEvents()
