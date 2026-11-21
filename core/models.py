"""Shared dataclasses for application state."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(slots=True)
class HighlightSettings:
    enabled: bool = True
    duration_ms: int = 1500
    ring_size: int = 220
    multi_monitor: bool = True
    hotkey: str = "F8"
    style: str = "focus"


@dataclass(slots=True)
class PointerSettings:
    cursor_size_percent: int = 120
    shake_to_find_enabled: bool = True
    shake_distance_threshold: int = 360
    shake_cooldown_ms: int = 1200
    trail_style: str = "glow"
    trail_color: str = "#22C55E"


@dataclass(slots=True)
class AppearanceSettings:
    theme_mode: str = "dark"


@dataclass(slots=True)
class ClickRippleSettings:
    enabled: bool = True
    duration_ms: int = 650
    size: int = 120


@dataclass(slots=True)
class DynamicCursorSettings:
    enabled: bool = False
    frame_interval_ms: int = 180


@dataclass(slots=True)
class GameModeSettings:
    auto_disable_enhancements: bool = True


@dataclass(slots=True)
class StartupSettings:
    launch_at_startup: bool = False


@dataclass(slots=True)
class CursorTheme:
    theme_id: str = "system_default"
    theme_name: str = "系统默认"
    source: str = "system"
    cursor_path: str | None = None
    hotspot_x: int = 0
    hotspot_y: int = 0


@dataclass(slots=True)
class AppThemeRule:
    enabled: bool = True
    process_name: str = ""
    theme: CursorTheme = field(default_factory=CursorTheme)


@dataclass(slots=True)
class AppSwitchSettings:
    enabled: bool = False
    poll_interval_ms: int = 1200
    rules: list[AppThemeRule] = field(default_factory=list)


@dataclass(slots=True)
class AppState:
    current_theme: CursorTheme = field(default_factory=CursorTheme)
    recent_custom_cursors: list[str] = field(default_factory=list)
    builtin_theme_palettes: dict[str, dict[str, str]] = field(default_factory=dict)
