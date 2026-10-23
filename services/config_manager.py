"""JSON-backed configuration management."""

from __future__ import annotations

import json
import logging
import os
import re
import shutil
import tempfile
from dataclasses import asdict, dataclass, field, fields
from pathlib import Path
from uuid import uuid4

from core.constants import DEFAULT_CONFIG_PATH
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
from services.runtime_paths import user_data_dir


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
    def __init__(self) -> None:
        self.logger = logging.getLogger(__name__)
        self.default_config_path = DEFAULT_CONFIG_PATH
        self.user_data_dir, self.user_log_dir = self._resolve_runtime_dirs()
        self.user_config_path = self.user_data_dir / "config.json"

    def load(self) -> AppConfig:
        default_payload = self._read_json(self.default_config_path)
        user_payload = self._read_json(self.user_config_path) if self.user_config_path.exists() else {}
        merged = self._deep_merge(default_payload, user_payload)
        return self._sanitize_config(self._from_dict(merged))


    def _sanitize_config(self, config: AppConfig) -> AppConfig:
        ranges = (
            (config.highlight, "duration_ms", 300, 5000),
            (config.highlight, "ring_size", 80, 600),
            (config.pointer, "cursor_size_percent", 10, 1000),
            (config.pointer, "shake_distance_threshold", 80, 1600),
            (config.pointer, "shake_cooldown_ms", 100, 10000),
            (config.dynamic_cursor, "frame_interval_ms", 90, 1000),
            (config.click_ripple, "duration_ms", 200, 2000),
            (config.click_ripple, "size", 40, 260),
            (config.app_switch, "poll_interval_ms", 300, 10000),
        )
        for settings, name, minimum, maximum in ranges:
            value = self._integer(getattr(settings, name), getattr(type(settings)(), name))
            setattr(settings, name, max(minimum, min(maximum, value)))
        if config.appearance.theme_mode not in {"dark", "light"}:
            config.appearance.theme_mode = "dark"
        if config.pointer.trail_style not in {"glow", "dash", "comet", "spark", "ring"}:
            config.pointer.trail_style = "glow"
        if not self._valid_color(config.pointer.trail_color):
            config.pointer.trail_color = PointerSettings().trail_color
        if not config.highlight.hotkey.strip():
            config.highlight.hotkey = HighlightSettings().hotkey
        return config

    def save(self, config: AppConfig) -> None:
        payload = asdict(config)
        temporary_path = None
        try:
            with tempfile.NamedTemporaryFile(
                mode="w", encoding="utf-8-sig", dir=self.user_config_path.parent,
                prefix=".config-", suffix=".tmp", delete=False,
            ) as handle:
                temporary_path = Path(handle.name)
                json.dump(payload, handle, ensure_ascii=False, indent=2, allow_nan=False)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temporary_path, self.user_config_path)
        finally:
            if temporary_path is not None:
                temporary_path.unlink(missing_ok=True)

    def _resolve_runtime_dirs(self) -> tuple[Path, Path]:
        candidate = user_data_dir()
        log_dir = candidate / "logs"
        log_dir.mkdir(parents=True, exist_ok=True)
        return candidate, log_dir

    def _read_json(self, path: Path) -> dict:
        if not path.exists():
            return {}
        try:
            payload = json.loads(path.read_text(encoding="utf-8-sig"))
            if not isinstance(payload, dict):
                raise ValueError("Configuration root must be an object")
            return payload
        except (ValueError, UnicodeError) as exc:
            backup_path = path.with_name(f"{path.name}.corrupt-{uuid4().hex}.bak")
            try:
                shutil.copy2(path, backup_path)
            except OSError:
                self.logger.exception("Could not back up unreadable configuration: %s", path)
                # Do not allow a later save to destroy the only recoverable copy.
                raise
            self.logger.warning("Invalid configuration preserved at %s: %s", backup_path, exc)
            return {}

    def _deep_merge(self, base: dict, override: dict) -> dict:
        result = dict(base)
        for key, value in override.items():
            if isinstance(value, dict) and isinstance(result.get(key), dict):
                result[key] = self._deep_merge(result[key], value)
            else:
                result[key] = value
        return result

    def _from_dict(self, payload: dict) -> AppConfig:
        app_state_payload = self._mapping(payload.get("app_state"))
        theme_payload = app_state_payload.get("current_theme", {})
        app_switch_payload = self._mapping(payload.get("app_switch"))
        rules: list[AppThemeRule] = []
        for rule_payload in self._list(app_switch_payload.get("rules")):
            if not isinstance(rule_payload, dict):
                continue
            rule_theme_payload = rule_payload.get("theme", {})
            if not isinstance(rule_theme_payload, dict):
                rule_theme_payload = {}
            rules.append(
                AppThemeRule(
                    enabled=rule_payload.get("enabled") if isinstance(rule_payload.get("enabled"), bool) else True,
                    process_name=rule_payload.get("process_name", "").strip() if isinstance(rule_payload.get("process_name", ""), str) else "",
                    theme=self._settings(CursorTheme, rule_theme_payload),
                )
            )
        return AppConfig(
            version=payload.get("version") if isinstance(payload.get("version"), str) else "1.0",
            app_state=AppState(
                current_theme=self._settings(CursorTheme, theme_payload),
                recent_custom_cursors=[item for item in self._list(app_state_payload.get("recent_custom_cursors")) if isinstance(item, str) and item][:10],
                builtin_theme_palettes={
                    theme_id: {key: value for key, value in palette.items() if key in {"primary", "secondary", "accent", "glow"} and self._valid_color(value)}
                    for theme_id, palette in self._mapping(app_state_payload.get("builtin_theme_palettes")).items()
                    if isinstance(palette, dict)
                },
            ),
            appearance=self._settings(AppearanceSettings, payload.get("appearance")),
            highlight=self._settings(HighlightSettings, payload.get("highlight")),
            pointer=self._settings(PointerSettings, payload.get("pointer")),
            click_ripple=self._settings(ClickRippleSettings, payload.get("click_ripple")),
            dynamic_cursor=self._settings(DynamicCursorSettings, payload.get("dynamic_cursor")),
            app_switch=AppSwitchSettings(
                enabled=app_switch_payload.get("enabled") is True,
                poll_interval_ms=self._integer(app_switch_payload.get("poll_interval_ms"), 1200),
                rules=rules,
            ),
            game_mode=self._settings(GameModeSettings, payload.get("game_mode")),
            startup=self._settings(StartupSettings, payload.get("startup")),
        )

    @staticmethod
    def _mapping(value) -> dict:
        return value if isinstance(value, dict) else {}

    @staticmethod
    def _list(value) -> list:
        return value if isinstance(value, list) else []

    @staticmethod
    def _valid_color(value) -> bool:
        return isinstance(value, str) and re.fullmatch(r"#[0-9a-fA-F]{6}", value) is not None

    @staticmethod
    def _integer(value, default: int) -> int:
        if isinstance(value, bool):
            return default
        try:
            return int(value)
        except (TypeError, ValueError, OverflowError):
            return default

    def _settings(self, settings_type, payload):
        """Accept known fields only and keep corrupt types out of runtime state."""
        settings = settings_type()
        payload = self._mapping(payload)
        for item in fields(settings):
            default = getattr(settings, item.name)
            value = payload.get(item.name, default)
            if isinstance(default, bool):
                value = value if isinstance(value, bool) else default
            elif isinstance(default, int):
                value = self._integer(value, default)
            elif isinstance(default, str):
                value = value if isinstance(value, str) else default
            elif default is None:
                value = value if isinstance(value, str) else None
            setattr(settings, item.name, value)
        return settings
