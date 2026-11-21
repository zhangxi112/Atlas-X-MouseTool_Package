from unittest.mock import Mock

from PySide6.QtCore import QPoint, QRect
from PySide6.QtGui import QColor
from PySide6.QtTest import QTest

from app.instance import StudioInstance
from core.models import CursorTheme
from services.config_manager import AppConfig
from services.enhancement_manager import EnhancementManager
from services.overlay_manager import EffectOverlay
from services.windows_foreground import ForegroundWindowInfo


def test_native_playback_changes_only_with_effective_settings(qapp, monkeypatch):
    cfg = AppConfig()
    cfg.app_state.current_theme = CursorTheme("crosshair", "十字", "builtin")
    cfg.dynamic_cursor.enabled = True
    cfg.dynamic_cursor.frame_interval_ms = 90
    cursor = Mock()
    engine = EnhancementManager(cursor, Mock(), lambda: cfg)
    engine.start()
    try:
        assert engine.playback_mode == "native"
        assert engine.input_timer.isActive()
        engine.refresh_from_config()
        QTest.qWait(300)
        cursor.apply_cursor_file.assert_called_once()
        cursor.apply_theme.assert_not_called()
        info = ForegroundWindowInfo(process_name="game.exe", is_fullscreen=True)
        monkeypatch.setattr("services.enhancement_manager.get_foreground_window_info", lambda: info)
        engine._poll_foreground()
        assert engine.game_mode_active and not engine.input_timer.isActive()
        assert engine.playback_mode == "static"
        cursor.apply_theme.assert_called_once()
        info = ForegroundWindowInfo()
        engine._poll_foreground()
        assert engine.input_timer.isActive() and cursor.apply_cursor_file.call_count == 2
        cfg.dynamic_cursor.frame_interval_ms = 250
        engine.refresh_from_config()
        assert cursor.get_animated_cursor_path.call_args.args[-1] == 250
    finally:
        engine.stop()


def test_native_failure_falls_back_and_failed_theme_choice_rolls_back(qapp):
    cfg = AppConfig()
    cfg.dynamic_cursor.enabled = True
    cursor = Mock()
    cursor.apply_cursor_file.return_value = False
    engine = EnhancementManager(cursor, Mock(), lambda: cfg)
    original = CursorTheme("orbit", "轨道", "builtin")
    try:
        assert engine.set_base_theme(original)
        assert engine.playback_mode == "fallback"
        engine.refresh_from_config()
        cursor.apply_cursor_file.assert_called_once()
        cursor.apply_theme.side_effect = [False, True]
        assert not engine.set_base_theme(CursorTheme("prism", "棱镜", "builtin"))
        assert cfg.app_state.current_theme == engine.effective_theme == original
    finally:
        engine.stop()


def test_vertical_shake_and_non_reversing_motion(qapp):
    engine = EnhancementManager(Mock(), Mock(), AppConfig)
    for index, y in enumerate((0, 100, 10, 115, 0)):
        engine._recent_positions.append((index * 0.03, 50, y))
    assert engine._is_shake_motion(300)
    engine._recent_positions.clear()
    for index, y in enumerate((0, 90, 180, 270, 360)):
        engine._recent_positions.append((index * 0.03, 50, y))
    assert not engine._is_shake_motion(300)


def test_overlay_bounds_origin_cleanup_and_stationary_follow(qapp):
    geometry = QRect(-1600, 0, 1600, 900)
    surface = EffectOverlay(geometry)
    origin = geometry.topLeft() + QPoint(550, 300)
    try:
        surface.add_click_ripple(origin, 600, 80, QColor("#44ACAB"))
        expected = surface.mapFromGlobal(origin)
        assert surface._effect_region().contains(expected)
        assert surface._effect_region().boundingRect().width() < 180
        surface.add_motion_trail([origin, origin + QPoint(45, 20)], 600, 90, QColor("white"), "comet")
        surface.start_find_effect(origin, 800, 120, "focus", QColor("cyan"))
        assert not surface.grab().isNull()
        surface.reset()
        assert not surface._timer.isActive() and not surface.isVisible()
        surface.set_follow_pointer(origin, 160, QColor("cyan"))
        assert not surface._timer.isActive()
        surface.clear_follow_pointer()
        assert not surface.isVisible()
    finally:
        surface.reset()
        surface.close()


def test_second_launch_activates_existing_instance_without_a_second_controller(qapp, tmp_path):
    first, second = StudioInstance(tmp_path), StudioInstance(tmp_path)
    seen = []
    first.activate_requested.connect(lambda: seen.append(True))
    try:
        assert first.acquire(show_existing=True)
        assert not second.acquire(show_existing=False)
        assert not second.acquire(show_existing=True)
        for _ in range(25):
            QTest.qWait(10)
            if seen:
                break
        assert seen == [True]
    finally:
        first.close()
    assert second.acquire(show_existing=False)
    second.close()
