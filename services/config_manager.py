"""JSON-backed configuration management."""

from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass, field
from pathlib import Path

from core.constants import APP_ID, DEFAULT_CONFIG_PATH
from core.models import (
    AppState,
    AppSwitchSettings,
    AppThemeRule,
    AppearanceSettings,
    ClickRippleSettings,
    CursorTheme,
    DynamicCursorSettings,
    GameModeSettings,
    HighlightSettings,
    PointerSettings,
    StartupSettings,
)


@dataclass(slots=True)
class AppConfig:
    version: str = "1.0"
    app_state: AppState = field(default_factory=AppState)
    appearance: AppearanceSettings = field(default_factory=AppearanceSettings)
    highlight: HighlightSettings = field(default_factory=HighlightSettings)
    pointer: PointerSettings = field(default_factory=PointerSettings)
    click_ripple: ClickRippleSettings = field(default_factory=ClickRippleSettings)
    dynamic_cursor: DynamicCursorSettings = field(default_factory=DynamicCursorSettings)
    app_switch: AppSwitchSettings = field(default_factory=AppSwitchSettings)
    game_mode: GameModeSettings = field(default_factory=GameModeSettings)
    startup: StartupSettings = field(default_factory=StartupSettings)


class ConfigManager:
    def __init__(self, runtime_dir: str | Path | None = None) -> None:
        self.default_config_path = DEFAULT_CONFIG_PATH
        if runtime_dir is None:
            self.user_data_dir, self.user_log_dir = self._resolve_runtime_dirs()
        else:
            self.user_data_dir = Path(runtime_dir)
            self.user_log_dir = self.user_data_dir / "logs"
            self.user_data_dir.mkdir(parents=True, exist_ok=True)
            self.user_log_dir.mkdir(parents=True, exist_ok=True)
        self.user_config_path = self.user_data_dir / "config.json"

    def load(self) -> AppConfig:
        default_payload = self._read_json(self.default_config_path)
        user_payload = self._read_json(self.user_config_path) if self.user_config_path.exists() else {}
        merged = self._deep_merge(default_payload, user_payload)
        return self._sanitize_config(self._from_dict(merged))


    def _sanitize_config(self, config: AppConfig) -> AppConfig:
        config.pointer.cursor_size_percent = max(10, min(1000, int(config.pointer.cursor_size_percent)))
        config.pointer.shake_distance_threshold = max(80, min(1600, int(config.pointer.shake_distance_threshold)))
        config.dynamic_cursor.frame_interval_ms = max(90, min(1000, int(config.dynamic_cursor.frame_interval_ms)))
        config.click_ripple.duration_ms = max(200, min(2000, int(config.click_ripple.duration_ms)))
        config.click_ripple.size = max(40, min(260, int(config.click_ripple.size)))
        return config

    def save(self, config: AppConfig) -> None:
        payload = asdict(config)
        self.user_config_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8-sig")

    def _resolve_runtime_dirs(self) -> tuple[Path, Path]:
        appdata_root = os.environ.get("APPDATA")
        if appdata_root:
            candidate = Path(appdata_root) / APP_ID
            log_dir = candidate / "logs"
            try:
                candidate.mkdir(parents=True, exist_ok=True)
                log_dir.mkdir(parents=True, exist_ok=True)
                return candidate, log_dir
            except OSError:
                pass
        fallback = DEFAULT_CONFIG_PATH.parent / "runtime"
        log_dir = fallback / "logs"
        fallback.mkdir(parents=True, exist_ok=True)
        log_dir.mkdir(parents=True, exist_ok=True)
        return fallback, log_dir

    def _read_json(self, path: Path) -> dict:
        if not path.exists():
            return {}
        return json.loads(path.read_text(encoding="utf-8-sig"))

    def _deep_merge(self, base: dict, override: dict) -> dict:
        result = dict(base)
        for key, value in override.items():
            if isinstance(value, dict) and isinstance(result.get(key), dict):
                result[key] = self._deep_merge(result[key], value)
            else:
                result[key] = value
        return result

    def _from_dict(self, payload: dict) -> AppConfig:
        app_state_payload = payload.get("app_state", {})
        theme_payload = app_state_payload.get("current_theme", {})
        app_switch_payload = payload.get("app_switch", {})
        rules: list[AppThemeRule] = []
        for rule_payload in app_switch_payload.get("rules", []):
            if not isinstance(rule_payload, dict):
                continue
            rule_theme_payload = rule_payload.get("theme", {})
            if not isinstance(rule_theme_payload, dict):
                rule_theme_payload = {}
            rules.append(
                AppThemeRule(
                    enabled=rule_payload.get("enabled", True),
                    process_name=str(rule_payload.get("process_name", "")).strip(),
                    theme=CursorTheme(**rule_theme_payload) if rule_theme_payload else CursorTheme(),
                )
            )
        return AppConfig(
            version=payload.get("version", "1.0"),
            app_state=AppState(
                current_theme=CursorTheme(**theme_payload) if isinstance(theme_payload, dict) else CursorTheme(),
                recent_custom_cursors=app_state_payload.get("recent_custom_cursors", []),
                builtin_theme_palettes=app_state_payload.get("builtin_theme_palettes", {}),
            ),
            appearance=AppearanceSettings(**payload.get("appearance", {})),
            highlight=HighlightSettings(**payload.get("highlight", {})),
            pointer=PointerSettings(**payload.get("pointer", {})),
            click_ripple=ClickRippleSettings(**payload.get("click_ripple", {})),
            dynamic_cursor=DynamicCursorSettings(**payload.get("dynamic_cursor", {})),
            app_switch=AppSwitchSettings(
                enabled=app_switch_payload.get("enabled", False),
                poll_interval_ms=app_switch_payload.get("poll_interval_ms", 1200),
                rules=rules,
            ),
            game_mode=GameModeSettings(**payload.get("game_mode", {})),
            startup=StartupSettings(**payload.get("startup", {})),
        )
