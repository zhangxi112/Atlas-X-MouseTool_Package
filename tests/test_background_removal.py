from dataclasses import asdict
from threading import Event, get_ident
import time
from unittest.mock import Mock

import pytest
from PIL import Image
from PySide6.QtCore import QTimer
from PySide6.QtTest import QTest

from app.bootstrap import bootstrap_app
from ui.main_window import MainWindow


@pytest.fixture
def window(qapp, tmp_path):
    context = bootstrap_app()
    context.overlay_manager.attach_application(qapp, lambda: context.config)
    main_window = MainWindow(context)
    source = tmp_path / "source.png"
    Image.new("RGBA", (32, 32), "red").save(source)
    main_window.current_custom_project = context.image_pipeline.import_image(source)
    yield main_window
    main_window.wait_for_background_task()
    qapp.processEvents()
    main_window.prepare_for_exit()
    context.enhancement_manager.stop()
    context.overlay_manager.shutdown()
    main_window.deleteLater()
    qapp.processEvents()


def wait_until(predicate):
    deadline = time.monotonic() + 5
    while not predicate() and time.monotonic() < deadline:
        QTest.qWait(10)
    assert predicate(), "Qt task did not complete before the test deadline"


def test_background_removal_keeps_gui_responsive_and_prevents_duplicate_work(window, monkeypatch):
    release = Event()
    entered = Event()
    worker_threads = []

    def remove(project):
        worker_threads.append(get_ident())
        entered.set()
        assert release.wait(5)
        project.bg_removed_path = project.original_path

    monkeypatch.setattr(window.context.image_pipeline, "remove_background", remove)
    gui_thread = get_ident()
    heartbeat = []
    try:
        window._remove_custom_background()
        task = window._background_task
        window._remove_custom_background()
        assert window._background_task is task
        wait_until(entered.is_set)
        QTimer.singleShot(0, lambda: heartbeat.append(True))
        wait_until(lambda: bool(heartbeat))
        assert len(worker_threads) == 1
        assert worker_threads[0] != gui_thread
        assert all(not control.isEnabled() for control in window._custom_controls)
    finally:
        release.set()
        wait_until(lambda: window._background_task is None)
    assert all(control.isEnabled() for control in window._custom_controls)
    assert window.current_custom_project.bg_removed_path is not None


def test_background_failure_reenables_controls_and_can_retry(window, monkeypatch):
    warning = Mock()
    monkeypatch.setattr(window, "_show_warning", warning)
    remove = Mock(side_effect=RuntimeError("model unavailable"))
    monkeypatch.setattr(window.context.image_pipeline, "remove_background", remove)
    window._remove_custom_background()
    wait_until(lambda: window._background_task is None)
    assert all(control.isEnabled() for control in window._custom_controls)
    warning.assert_called_once()
    assert "model unavailable" in warning.call_args.args[0]
    remove.side_effect = None
    window._remove_custom_background()
    wait_until(lambda: window._background_task is None)
    assert remove.call_count == 2


def test_exit_is_deferred_until_background_work_finishes(window, monkeypatch):
    release = Event()
    monkeypatch.setattr(window.context.image_pipeline, "remove_background", lambda project: release.wait(5))
    try:
        window._remove_custom_background()
        assert window.prepare_for_exit() is False
        assert window._exit_after_background is True
        assert window._allow_close is False
    finally:
        release.set()
        wait_until(lambda: window._background_task is None)
    assert window._allow_close is True


def test_failed_hotkey_change_does_not_save_other_settings(window, monkeypatch):
    original = asdict(window.context.config)
    window.tray_manager = Mock()
    window.tray_manager.update_hotkey.return_value = False
    monkeypatch.setattr(window, "_show_warning", Mock())
    save = Mock()
    monkeypatch.setattr(window.context.config_manager, "save", save)
    window._set_hotkey_widgets("F9")
    window.duration_spin.setValue(3000)
    window._save_settings()
    assert asdict(window.context.config) == original
    save.assert_not_called()
