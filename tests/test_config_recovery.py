import json

import pytest

from services.config_manager import AppConfig, ConfigManager


@pytest.mark.parametrize("contents", [b'{"pointer":', b"[]", b"null", b"\xff\xfe\x00"])
def test_corrupt_configuration_is_preserved_and_defaults_load(contents):
    manager = ConfigManager()
    manager.user_config_path.write_bytes(contents)
    assert manager.load().highlight.hotkey == "F8"
    backups = list(manager.user_data_dir.glob("config.json.corrupt-*.bak"))
    assert len(backups) == 1
    assert backups[0].read_bytes() == contents
    assert manager.user_config_path.read_bytes() == contents


@pytest.mark.parametrize("section", ["app_state", "appearance", "highlight", "pointer", "click_ripple", "dynamic_cursor", "app_switch", "game_mode", "startup"])
@pytest.mark.parametrize("value", [None, [], "invalid"])
def test_wrong_section_types_fall_back_to_defaults(section, value):
    manager = ConfigManager()
    manager.user_config_path.write_text(json.dumps({section: value}), encoding="utf-8")
    assert manager.load() == AppConfig()


def test_unknown_fields_and_invalid_nested_values_are_tolerated():
    manager = ConfigManager()
    payload = {
        "pointer": {"future_option": 1, "cursor_size_percent": "180", "shake_distance_threshold": None, "trail_color": "#ZZZZZZ"},
        "appearance": {"theme_mode": "unknown"},
        "dynamic_cursor": {"enabled": "false", "frame_interval_ms": float("inf")},
        "app_switch": {"poll_interval_ms": "broken", "rules": [None, {"theme": {"future_option": 1}, "process_name": None}]},
        "app_state": {
            "current_theme": {"future_option": 1, "source": None},
            "recent_custom_cursors": [None, 3, "cursor.cur"],
            "builtin_theme_palettes": {"classic_arrow": {"primary": "#123abc", "glow": "bad", "unknown": "#FFFFFF"}, "crosshair": None},
        },
    }
    manager.user_config_path.write_text(json.dumps(payload), encoding="utf-8")
    config = manager.load()
    assert config.pointer.cursor_size_percent == 180
    assert config.pointer.shake_distance_threshold == 360
    assert config.pointer.trail_color == "#22C55E"
    assert config.appearance.theme_mode == "dark"
    assert config.dynamic_cursor.enabled is False
    assert config.dynamic_cursor.frame_interval_ms == 180
    assert config.app_switch.poll_interval_ms == 1200
    assert config.app_switch.rules[0].process_name == ""
    assert config.app_state.current_theme.source == "system"
    assert config.app_state.recent_custom_cursors == ["cursor.cur"]
    assert config.app_state.builtin_theme_palettes == {"classic_arrow": {"primary": "#123abc"}}


def test_save_round_trips_unicode_and_preserves_original_on_replace_failure(monkeypatch):
    manager = ConfigManager()
    config = AppConfig()
    config.app_state.current_theme.theme_name = "自定义光标"
    manager.save(config)
    assert manager.load() == config
    original = manager.user_config_path.read_bytes()

    def fail_replace(*args):
        raise OSError("disk unavailable")

    monkeypatch.setattr("services.config_manager.os.replace", fail_replace)
    config.highlight.hotkey = "F9"
    with pytest.raises(OSError, match="disk unavailable"):
        manager.save(config)
    assert manager.user_config_path.read_bytes() == original
    assert not list(manager.user_data_dir.glob(".config-*.tmp"))
