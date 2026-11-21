"""Runtime coordinator for app switching, click ripples, dynamic cursors, shake-to-find, and game mode."""

from __future__ import annotations

import ctypes
import logging
import time
from collections import deque
from dataclasses import asdict
from pathlib import Path

from PySide6.QtCore import QObject, QPoint, QTimer, Signal
from PySide6.QtGui import QCursor

from core.builtin_themes import BUILTIN_THEMES
from core.models import AppThemeRule, CursorTheme
from services.windows_foreground import ForegroundWindowInfo, WIN32_AVAILABLE, get_foreground_window_info

VK_LBUTTON = 0x01
VK_RBUTTON = 0x02
VK_MBUTTON = 0x04
USER32 = ctypes.windll.user32 if WIN32_AVAILABLE else None
VALID_RULE_THEME_IDS = {theme.theme_id for theme in BUILTIN_THEMES} | {"system_default"}


def parse_app_theme_rules(text: str) -> list[AppThemeRule]:
    """Parse process-to-theme rules from a textarea-style string."""
    rules: list[AppThemeRule] = []
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if "=" not in stripped:
            raise ValueError(f"规则格式错误：{stripped}")
        process_name, theme_id = [part.strip() for part in stripped.split("=", 1)]
        theme_key = theme_id.lower()
        if not process_name:
            raise ValueError("规则中的进程名不能为空")
        if theme_key not in VALID_RULE_THEME_IDS:
            raise ValueError(f"未知主题标识：{theme_id}")
        rules.append(
            AppThemeRule(
                enabled=True,
                process_name=Path(process_name).name.lower(),
                theme=CursorTheme(
                    theme_id=theme_key,
                    theme_name=_theme_name_for_rule(theme_key),
                    source="system" if theme_key == "system_default" else "builtin",
                ),
            )
        )
    return rules


def serialize_app_theme_rules(rules: list[AppThemeRule]) -> str:
    """Serialize process-to-theme rules into textarea-friendly text."""
    return "\n".join(
        f"{rule.process_name} = {rule.theme.theme_id}"
        for rule in rules
        if rule.enabled and rule.process_name
    )


class EnhancementManager(QObject):
    """Coordinates advanced runtime enhancements without leaking logic into the UI."""

    runtime_state_changed = Signal()

    def __init__(self, cursor_manager, overlay_manager, config_provider) -> None:
        super().__init__()
        self.logger = logging.getLogger(__name__)
        self.cursor_manager = cursor_manager
        self.overlay_manager = overlay_manager
        self.config_provider = config_provider
        self.app_poll_timer = QTimer(self)
        self.app_poll_timer.timeout.connect(self._poll_foreground)
        self.input_timer = QTimer(self)
        self.input_timer.timeout.connect(self._poll_input)
        self._button_state = {"left": False, "right": False, "middle": False}
        self._click_enabled = False
        self._foreground = ForegroundWindowInfo()
        self._game_mode_active = False
        self._active_rule: AppThemeRule | None = None
        self._target_theme = CursorTheme()
        self._applied_key: tuple | None = None
        self.playback_mode = "static"
        self._recent_positions: deque[tuple[float, int, int]] = deque(maxlen=18)
        self._last_shake_trigger_at = 0.0
        self._shake_live_until = 0.0

    @property
    def foreground_process_name(self) -> str:
        return self._foreground.process_name

    @property
    def game_mode_active(self) -> bool:
        return self._game_mode_active

    @property
    def effective_theme(self) -> CursorTheme:
        return self._clone_theme(self._target_theme)

    @property
    def active_rule(self) -> AppThemeRule | None:
        if self._active_rule is None:
            return None
        return AppThemeRule(enabled=self._active_rule.enabled, process_name=self._active_rule.process_name, theme=self._clone_theme(self._active_rule.theme))

    def start(self) -> None:
        config = self.config_provider()
        if config.app_switch.enabled or config.game_mode.auto_disable_enhancements:
            self._foreground = get_foreground_window_info()
        self.refresh_from_config(force_apply=True)

    def stop(self) -> None:
        self.app_poll_timer.stop()
        self.input_timer.stop()
        self._click_enabled = False
        if self.playback_mode == "native":
            self._apply_static_theme(self._target_theme)
        self.playback_mode = "static"
        self._applied_key = None

    def refresh_from_config(self, force_apply: bool = False) -> None:
        config = self.config_provider()
        if config.app_switch.enabled or config.game_mode.auto_disable_enhancements:
            self.app_poll_timer.setInterval(max(300, config.app_switch.poll_interval_ms))
            if not self.app_poll_timer.isActive():
                self.app_poll_timer.start()
        else:
            self.app_poll_timer.stop()
            self._foreground = ForegroundWindowInfo()

        self._sync_runtime_state(force_apply=force_apply)

    def notify_base_theme_changed(self) -> None:
        self._sync_runtime_state(force_apply=False)

    def set_base_theme(self, theme: CursorTheme) -> bool:
        config = self.config_provider()
        previous = config.app_state.current_theme
        config.app_state.current_theme = theme
        if self._sync_runtime_state(force_apply=True):
            return True
        config.app_state.current_theme = previous
        self._sync_runtime_state(force_apply=True)
        return False

    def _poll_foreground(self) -> None:
        info = get_foreground_window_info()
        if (info.process_name, info.is_fullscreen) == (self._foreground.process_name, self._foreground.is_fullscreen):
            return
        self._foreground = info
        self._sync_runtime_state(force_apply=False)

    def _sync_input(self) -> None:
        config = self.config_provider()
        click_enabled = config.click_ripple.enabled and WIN32_AVAILABLE and not self._game_mode_active
        motion_enabled = config.pointer.shake_to_find_enabled and not self._game_mode_active
        if not motion_enabled:
            self._recent_positions.clear()
            self._shake_live_until = 0.0
        if click_enabled and not self._click_enabled:
            # A button held when resuming is not a new click.
            self._poll_mouse_buttons(None)
        self._click_enabled = click_enabled
        if click_enabled or motion_enabled:
            interval = 24 if click_enabled else 30
            if not self.input_timer.isActive() or self.input_timer.interval() != interval:
                self.input_timer.start(interval)
        else:
            self.input_timer.stop()

    def _poll_input(self) -> None:
        position = QCursor.pos()
        if self._click_enabled:
            self._poll_mouse_buttons(position)
        if self.config_provider().pointer.shake_to_find_enabled:
            self._poll_motion(position)

    def _poll_mouse_buttons(self, position: QPoint | None) -> None:
        if USER32 is None:
            return
        for button_name, vk_code in (("left", VK_LBUTTON), ("right", VK_RBUTTON), ("middle", VK_MBUTTON)):
            pressed = bool(USER32.GetAsyncKeyState(vk_code) & 0x8000)
            if position is not None and pressed and not self._button_state[button_name]:
                self.overlay_manager.trigger_click_ripple(position, button_name)
            self._button_state[button_name] = pressed

    def _poll_motion(self, pos: QPoint) -> None:
        config = self.config_provider()
        if self._game_mode_active or not config.pointer.shake_to_find_enabled:
            self._recent_positions.clear()
            self._shake_live_until = 0.0
            return

        now = time.perf_counter()
        self._recent_positions.append((now, pos.x(), pos.y()))
        while self._recent_positions and (now - self._recent_positions[0][0]) > 0.4:
            self._recent_positions.popleft()

        if len(self._recent_positions) < 4:
            return

        if self._is_shake_motion(config.pointer.shake_distance_threshold):
            session_active = now <= self._shake_live_until
            if session_active or (now - self._last_shake_trigger_at) * 1000 >= config.pointer.shake_cooldown_ms:
                if not session_active:
                    self._last_shake_trigger_at = now
                self._shake_live_until = now + 0.35

        if now <= self._shake_live_until:
            self.overlay_manager.trigger_motion_trail(self._build_motion_trail_points(), replace=True)

    def _build_motion_trail_points(self) -> list[QPoint]:
        sampled: list[QPoint] = []
        last_point: QPoint | None = None
        for _, x_pos, y_pos in self._recent_positions:
            point = QPoint(x_pos, y_pos)
            if last_point is None or abs(point.x() - last_point.x()) + abs(point.y() - last_point.y()) >= 14:
                sampled.append(point)
                last_point = point
        if sampled:
            _, x_pos, y_pos = self._recent_positions[-1]
            if sampled[-1] != QPoint(x_pos, y_pos):
                sampled.append(QPoint(x_pos, y_pos))
        return sampled[-8:]

    def _is_shake_motion(self, threshold: int) -> bool:
        total_distance = 0.0
        min_x = max_x = self._recent_positions[0][1]
        min_y = max_y = self._recent_positions[0][2]
        x_changes = y_changes = 0
        previous_dx_sign = 0
        previous_dy_sign = 0

        for previous, current in zip(self._recent_positions, list(self._recent_positions)[1:]):
            dx = current[1] - previous[1]
            dy = current[2] - previous[2]
            total_distance += abs(dx) + abs(dy)
            min_x = min(min_x, current[1])
            max_x = max(max_x, current[1])
            min_y = min(min_y, current[2])
            max_y = max(max_y, current[2])
            dx_sign = 1 if dx > 0 else -1 if dx < 0 else 0
            if previous_dx_sign and dx_sign and dx_sign != previous_dx_sign:
                x_changes += 1
            if dx_sign:
                previous_dx_sign = dx_sign
            dy_sign = 1 if dy > 0 else -1 if dy < 0 else 0
            if previous_dy_sign and dy_sign and dy_sign != previous_dy_sign:
                y_changes += 1
            if dy_sign:
                previous_dy_sign = dy_sign

        span_x = max_x - min_x
        span_y = max_y - min_y
        compact_enough = max(span_x, span_y) <= max(260, int(threshold * 0.85))
        reverses = (x_changes >= 2 and span_x >= 45) or (y_changes >= 2 and span_y >= 45)
        return total_distance >= threshold and reverses and compact_enough

    def _sync_runtime_state(self, force_apply: bool) -> bool:
        config = self.config_provider()
        new_game_mode_active = bool(config.game_mode.auto_disable_enhancements and self._foreground.is_fullscreen)
        if new_game_mode_active != self._game_mode_active:
            self._game_mode_active = new_game_mode_active
            self.overlay_manager.set_effects_suspended(new_game_mode_active)

        new_rule = None
        if config.app_switch.enabled and not self._game_mode_active:
            new_rule = self._match_rule(config.app_switch.rules, self._foreground.process_name)

        target_theme = self._clone_theme(new_rule.theme if new_rule is not None else config.app_state.current_theme)
        self._active_rule = new_rule
        self._target_theme = target_theme
        self._sync_input()
        applied = self._apply_effective_theme(target_theme, force_apply)
        self.overlay_manager.set_follow_pointer_mode(
            enabled=(not self._game_mode_active and config.pointer.cursor_size_percent > 500),
            size_percent=config.pointer.cursor_size_percent,
        )
        self.runtime_state_changed.emit()
        return applied

    def _apply_effective_theme(self, theme: CursorTheme, force: bool) -> bool:
        config = self.config_provider()
        builtin = theme.source == "builtin"
        size = config.pointer.cursor_size_percent if builtin else 100
        palette = self._palette_override_for_theme(theme) or {}
        interval = config.dynamic_cursor.frame_interval_ms if builtin and config.dynamic_cursor.enabled and not self._game_mode_active else 0
        key = (theme.source, theme.theme_id, theme.cursor_path if not builtin else None, size, tuple(sorted(palette.items())), interval)
        if key == self._applied_key and not force:
            return True
        if interval:
            try:
                path = self.cursor_manager.get_animated_cursor_path(theme.theme_id, size, palette, interval)
                if path and self.cursor_manager.apply_cursor_file(path):
                    self._applied_key = key
                    self.playback_mode = "native"
                    self.logger.info("Native cursor playback: %s (%d ms)", theme.theme_id, interval)
                    return True
            except OSError:
                self.logger.exception("Could not build animated cursor")
            self.logger.warning("Using static fallback for %s", theme.theme_id)
        success = self._apply_static_theme(theme)
        self._applied_key = key if success else None
        self.playback_mode = ("fallback" if interval else "static") if success else "error"
        return success

    def _apply_static_theme(self, theme: CursorTheme) -> bool:
        try:
            return self.cursor_manager.apply_theme(theme, size_percent=self.config_provider().pointer.cursor_size_percent,
                                                   palette_override=self._palette_override_for_theme(theme))
        except OSError:
            self.logger.exception("Could not prepare cursor for %s", theme.theme_id)
            return False

    def _palette_override_for_theme(self, theme: CursorTheme) -> dict[str, str] | None:
        if theme.source != "builtin" or not theme.theme_id:
            return None
        palette = self.config_provider().app_state.builtin_theme_palettes.get(theme.theme_id, {})
        return palette or None

    def _match_rule(self, rules: list[AppThemeRule], process_name: str) -> AppThemeRule | None:
        normalized = Path(process_name).name.lower()
        for rule in rules:
            if rule.enabled and Path(rule.process_name).name.lower() == normalized and normalized:
                return rule
        return None

    def _clone_theme(self, theme: CursorTheme) -> CursorTheme:
        return CursorTheme(**asdict(theme))

def _theme_name_for_rule(theme_id: str) -> str:
    if theme_id == "system_default":
        return "系统默认"
    for theme in BUILTIN_THEMES:
        if theme.theme_id == theme_id:
            return theme.name
    return theme_id


