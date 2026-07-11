from pathlib import Path

from services.config_manager import AppConfig, ConfigManager


def test_config_manager_loads_defaults(tmp_path: Path) -> None:
    manager = ConfigManager(runtime_dir=tmp_path / "runtime")
    config = manager.load()
    assert config.highlight.duration_ms > 0
    assert config.highlight.hotkey
    assert config.click_ripple.enabled is True
    assert config.dynamic_cursor.frame_interval_ms >= 90
    assert config.game_mode.auto_disable_enhancements is True


def test_config_manager_sanitizes_ranges(tmp_path: Path) -> None:
    manager = ConfigManager(runtime_dir=tmp_path / "runtime")
    config = AppConfig()
    config.pointer.cursor_size_percent = 5000
    config.pointer.shake_distance_threshold = 10
    sanitized = manager._sanitize_config(config)
    assert sanitized.pointer.cursor_size_percent == 1000
    assert sanitized.pointer.shake_distance_threshold == 80
