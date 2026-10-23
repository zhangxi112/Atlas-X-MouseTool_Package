"""Tray and hotkey manager."""

from __future__ import annotations

import ctypes
import ctypes.wintypes
import logging
from collections.abc import Callable

from PySide6.QtCore import QAbstractNativeEventFilter, QObject
from PySide6.QtGui import QAction, QIcon
from PySide6.QtWidgets import QApplication, QMenu, QSystemTrayIcon

from core.constants import APP_NAME
from ui.dialog_utils import show_warning
from ui.icon_factory import create_app_icon

WM_HOTKEY = 0x0312
MOD_ALT = 0x0001
MOD_CONTROL = 0x0002
MOD_SHIFT = 0x0004
MOD_WIN = 0x0008


def describe_hotkey_sequence(sequence: str) -> str:
    normalized = sequence.strip()
    if not normalized:
        return "点击录制后直接按键，推荐使用 F8 或 Shift+F8。"
    try:
        parse_hotkey_sequence(normalized)
    except ValueError as exc:
        return f"当前格式不可用：{exc}"
    parts = [part.strip().upper() for part in normalized.split("+") if part.strip()]
    modifier_count = sum(part in {"CTRL", "CONTROL", "ALT", "SHIFT", "WIN", "WINDOWS"} for part in parts)
    key_token = next((part for part in reversed(parts) if part not in {"CTRL", "CONTROL", "ALT", "SHIFT", "WIN", "WINDOWS"}), "")
    if modifier_count == 0:
        if key_token.startswith("F"):
            return "单键触发，操作最快，通常冲突风险较低。"
        return "单键触发，但和应用自身快捷键冲突的风险较高。"
    if modifier_count == 1:
        return "双键触发，速度和冲突控制比较平衡。"
    return "多键触发，冲突概率更低，但按起来会更慢。"


def parse_hotkey_sequence(sequence: str) -> tuple[int, int]:
    parts = [part.strip().upper() for part in sequence.split("+")]
    if not all(parts):
        raise ValueError("Hotkey sequence is empty")
    modifier_map = {
        "CTRL": MOD_CONTROL,
        "CONTROL": MOD_CONTROL,
        "ALT": MOD_ALT,
        "SHIFT": MOD_SHIFT,
        "WIN": MOD_WIN,
        "WINDOWS": MOD_WIN,
    }
    modifiers = 0
    key_code = None
    function_keys = {f"F{index}": 0x6F + index for index in range(1, 13)}
    for part in parts:
        if part in modifier_map:
            modifiers |= modifier_map[part]
            continue
        if key_code is not None:
            raise ValueError("Hotkey sequence must contain exactly one non-modifier key")
        if part in function_keys:
            key_code = function_keys[part]
            continue
        if len(part) == 1 and part.isascii() and part.isalnum():
            key_code = ord(part)
            continue
        raise ValueError(f"Unsupported hotkey token: {part}")
    if key_code is None:
        raise ValueError("Hotkey sequence must include a non-modifier key")
    return modifiers, key_code


class GlobalHotkeyFilter(QAbstractNativeEventFilter):
    def __init__(self, hotkey_id: int, callback: Callable[[], None]) -> None:
        super().__init__()
        self.hotkey_id = hotkey_id
        self.callback = callback

    def nativeEventFilter(self, event_type, message):  # noqa: N802
        del event_type
        msg = ctypes.wintypes.MSG.from_address(int(message))
        if msg.message == WM_HOTKEY and msg.wParam == self.hotkey_id:
            self.callback()
            return True, 0
        return False, 0


class TrayHotkeyManager(QObject):
    HOTKEY_ID = 0xA71A

    def __init__(self, app: QApplication, window, hotkey_sequence: str, on_find_mouse: Callable[[], None]) -> None:
        super().__init__()
        self.app = app
        self.window = window
        self.hotkey_sequence = hotkey_sequence
        self.on_find_mouse = on_find_mouse
        self.logger = logging.getLogger(__name__)
        self.tray_icon = QSystemTrayIcon(self._resolve_icon(), parent=self.app)
        self.menu = QMenu()
        self.hotkey_filter: GlobalHotkeyFilter | None = None
        self._registered_hotkey_id: int | None = None
        self._open_action: QAction | None = None
        self._hide_action: QAction | None = None
        self._find_action: QAction | None = None
        self._quit_action: QAction | None = None

    def start(self) -> None:
        if not QSystemTrayIcon.isSystemTrayAvailable():
            self.logger.warning("System tray is not available on this environment")
            return
        self._build_menu()
        self.tray_icon.setContextMenu(self.menu)
        self.tray_icon.setToolTip(APP_NAME)
        self.tray_icon.activated.connect(self._handle_activation)
        self.tray_icon.show()
        self._register_hotkey()
        self.tray_icon.showMessage(APP_NAME, f"应用已进入托盘常驻。全局快捷键：{self.hotkey_sequence}", QSystemTrayIcon.MessageIcon.Information, 2500)
        self.logger.info("Tray manager started")

    def stop(self) -> None:
        self._unregister_hotkey()
        self.tray_icon.hide()

    def update_hotkey(self, hotkey_sequence: str) -> bool:
        try:
            parsed = parse_hotkey_sequence(hotkey_sequence)
        except ValueError:
            return False
        if self.hotkey_filter is not None and parsed == parse_hotkey_sequence(self.hotkey_sequence):
            return True
        return self._register_hotkey(hotkey_sequence)

    def show_window(self) -> None:
        self.window.showNormal()
        self.window.raise_()
        self.window.activateWindow()
        self._sync_menu_labels()

    def hide_window(self) -> None:
        self.window.hide()
        self._sync_menu_labels()

    def quit_application(self) -> None:
        if not self.window.prepare_for_exit():
            return
        self.stop()
        self.app.quit()

    def _build_menu(self) -> None:
        self.menu.clear()
        self._open_action = self.menu.addAction("打开主窗口")
        self._hide_action = self.menu.addAction("隐藏窗口")
        self._find_action = self.menu.addAction("找回鼠标")
        self.menu.addSeparator()
        self._quit_action = self.menu.addAction("退出")
        self._open_action.triggered.connect(self.show_window)
        self._hide_action.triggered.connect(self.hide_window)
        self._find_action.triggered.connect(self.on_find_mouse)
        self._quit_action.triggered.connect(self.quit_application)
        self._sync_menu_labels()

    def _resolve_icon(self) -> QIcon:
        return create_app_icon()

    def _handle_activation(self, reason: QSystemTrayIcon.ActivationReason) -> None:
        if reason in {QSystemTrayIcon.ActivationReason.DoubleClick, QSystemTrayIcon.ActivationReason.Trigger}:
            if self.window.isVisible():
                self.hide_window()
            else:
                self.show_window()

    def _sync_menu_labels(self) -> None:
        if self._open_action is not None:
            self._open_action.setEnabled(not self.window.isVisible())
        if self._hide_action is not None:
            self._hide_action.setEnabled(self.window.isVisible())

    def _register_hotkey(self, sequence: str | None = None) -> bool:
        if not hasattr(ctypes, "windll"):
            self.logger.warning("Global hotkey registration is only supported on Windows")
            return False
        candidate = sequence if sequence is not None else self.hotkey_sequence
        hotkey_id = self.HOTKEY_ID + 1 if self._registered_hotkey_id == self.HOTKEY_ID else self.HOTKEY_ID
        registered = False
        try:
            modifiers, key_code = parse_hotkey_sequence(candidate)
            if not ctypes.windll.user32.RegisterHotKey(None, hotkey_id, modifiers, key_code):
                raise ctypes.WinError(ctypes.get_last_error())
            registered = True
            new_filter = GlobalHotkeyFilter(hotkey_id, self.on_find_mouse)
            self.app.installNativeEventFilter(new_filter)
            # Acquire the replacement before releasing the working shortcut.
            self._unregister_hotkey()
            self._registered_hotkey_id = hotkey_id
            self.hotkey_filter = new_filter
            self.hotkey_sequence = candidate
            self.logger.info("Registered global hotkey: %s", self.hotkey_sequence)
            return True
        except Exception as exc:
            if registered:
                ctypes.windll.user32.UnregisterHotKey(None, hotkey_id)
            self.logger.exception("Failed to register global hotkey: %s", exc)
            show_warning(self.window, getattr(self.window.context.config.appearance, "theme_mode", "dark"), APP_NAME, f"注册全局快捷键失败：{candidate}\n{exc}")
            return False

    def _unregister_hotkey(self) -> None:
        if self._registered_hotkey_id is not None and hasattr(ctypes, "windll"):
            ctypes.windll.user32.UnregisterHotKey(None, self._registered_hotkey_id)
        self._registered_hotkey_id = None
        if self.hotkey_filter is not None:
            self.app.removeNativeEventFilter(self.hotkey_filter)
            self.hotkey_filter = None
