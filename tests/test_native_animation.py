import ctypes
import struct
import sys

import pytest

from core.animated_cursor import encode_animation, interval_jiffies
from services.cursor_manager import CursorManager


def test_animation_chunk_sizes_padding_and_clock():
    data = encode_animation([b"odd", b"even"], interval_jiffies(180))
    assert data[:4] == b"RIFF" and struct.unpack_from("<I", data, 4)[0] == len(data) - 8
    assert data[8:16] == b"ACONanih"
    assert struct.unpack_from("<9I", data, 20) == (36, 2, 2, 0, 0, 0, 0, 11, 1)
    assert data[64:] == b"framicon\x03\0\0\0odd\0icon\x04\0\0\0even"


@pytest.mark.skipif(sys.platform != "win32", reason="Windows cursor decoder")
def test_windows_draws_different_frames_from_packaged_cursor(tmp_path):
    import win32con
    import win32gui
    import win32ui

    manager = CursorManager(cache_dir=tmp_path)
    path = manager.get_animated_cursor_path("crosshair", 70, None, 180)
    # Use private handles and a memory bitmap. Never install a cursor on the desktop.
    user32 = ctypes.WinDLL("user32", use_last_error=True)
    user32.LoadImageW.argtypes = [ctypes.c_void_p, ctypes.c_wchar_p, ctypes.c_uint, ctypes.c_int, ctypes.c_int, ctypes.c_uint]
    user32.LoadImageW.restype = ctypes.c_void_p
    user32.DestroyCursor.argtypes = [ctypes.c_void_p]
    cursor = user32.LoadImageW(None, str(path), win32con.IMAGE_CURSOR, 0, 0, win32con.LR_LOADFROMFILE)
    assert cursor, ctypes.WinError(ctypes.get_last_error())
    screen = win32gui.GetDC(0)
    reference = win32ui.CreateDCFromHandle(screen)
    memory = reference.CreateCompatibleDC()
    bitmap = win32ui.CreateBitmap()
    bitmap.CreateCompatibleBitmap(reference, 64, 64)
    old_bitmap = memory.SelectObject(bitmap)
    try:
        frames = []
        for index in range(6):
            memory.FillSolidRect((0, 0, 64, 64), 0)
            win32gui.DrawIconEx(memory.GetSafeHdc(), 0, 0, cursor, 64, 64, index, 0, win32con.DI_NORMAL)
            frames.append(bitmap.GetBitmapBits(True))
        assert len(set(frames)) == 6
        assert manager.get_animated_cursor_path("crosshair", 70, None, 90) != path
    finally:
        memory.SelectObject(old_bitmap)
        memory.DeleteDC()
        win32gui.DeleteObject(bitmap.GetHandle())
        win32gui.ReleaseDC(0, screen)
        user32.DestroyCursor(cursor)
