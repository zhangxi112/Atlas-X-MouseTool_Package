"""Encode a sequence of CUR images as a Windows RIFF animated cursor."""

from __future__ import annotations

import struct
from collections.abc import Sequence


def interval_jiffies(interval_ms: int) -> int:
    """Windows stores ANI frame times in sixtieths of a second."""
    return max(1, round(interval_ms * 60 / 1000))


def _chunk(kind: bytes, data: bytes) -> bytes:
    return kind + struct.pack("<I", len(data)) + data + b"\0" * (len(data) % 2)


def encode_animation(frames: Sequence[bytes], jiffies: int) -> bytes:
    if not frames or jiffies < 1:
        raise ValueError("An animation needs cursor frames and a positive frame interval")
    header = struct.pack("<9I", 36, len(frames), len(frames), 0, 0, 0, 0, jiffies, 1)
    icons = b"".join(_chunk(b"icon", frame) for frame in frames)
    return _chunk(b"RIFF", b"ACON" + _chunk(b"anih", header) + _chunk(b"LIST", b"fram" + icons))
