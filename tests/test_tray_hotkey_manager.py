from types import SimpleNamespace
from unittest.mock import Mock

from services import tray_hotkey_manager as module


def make_manager(monkeypatch):
    # Test the registration transaction without creating a real tray or hotkey.
    manager = module.TrayHotkeyManager.__new__(module.TrayHotkeyManager)
    module.QObject.__init__(manager)
    manager.app = Mock()
    manager.window = SimpleNamespace(context=SimpleNamespace(config=SimpleNamespace(appearance=SimpleNamespace(theme_mode="dark"))))
    manager.logger = Mock()
    manager.on_find_mouse = Mock()
    manager.hotkey_sequence = "F8"
    manager.hotkey_filter = object()
    manager._registered_hotkey_id = manager.HOTKEY_ID
    native = Mock()
    monkeypatch.setattr(module, "ctypes", SimpleNamespace(windll=SimpleNamespace(user32=native), WinError=lambda *args: OSError("hotkey occupied"), get_last_error=lambda: 1409))
    monkeypatch.setattr(module, "show_warning", Mock())
    return manager, native


def test_failed_update_preserves_old_registration(monkeypatch):
    manager, native = make_manager(monkeypatch)
    old_filter = manager.hotkey_filter
    native.RegisterHotKey.return_value = False
    assert manager.update_hotkey("F9") is False
    assert manager.hotkey_sequence == "F8"
    assert manager.hotkey_filter is old_filter
    native.UnregisterHotKey.assert_not_called()
    manager.app.removeNativeEventFilter.assert_not_called()


def test_successful_update_registers_new_key_before_releasing_old(monkeypatch):
    manager, native = make_manager(monkeypatch)
    native.RegisterHotKey.return_value = True
    assert manager.update_hotkey("Ctrl+F9") is True
    assert manager.hotkey_sequence == "Ctrl+F9"
    assert manager._registered_hotkey_id == manager.HOTKEY_ID + 1
    assert [call[0] for call in native.method_calls] == ["RegisterHotKey", "UnregisterHotKey"]
    native.UnregisterHotKey.assert_called_once_with(None, manager.HOTKEY_ID)


def test_unchanged_or_invalid_hotkey_does_not_touch_registration(monkeypatch):
    manager, native = make_manager(monkeypatch)
    assert manager.update_hotkey("f8") is True
    assert manager.update_hotkey("Ctrl+A+B") is False
    assert not native.method_calls
