"""Minimal deterministic PNG writer/reader for 16-bit gray / RGBA (PIL cannot write RGBA16).

Only what the map-surface pipeline needs: colour types 0 (gray) and 6 (RGBA), bit depth 8 or 16,
filter type 2 ("Up") on every row, zlib level fixed. The reader only accepts files written here
(used by the self-check, not as a general decoder).
"""
from __future__ import annotations

import struct
import zlib

import numpy as np

_SIG = b"\x89PNG\r\n\x1a\n"


def _chunk(tag: bytes, data: bytes) -> bytes:
    return struct.pack(">I", len(data)) + tag + data + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)


def encode_png(arr: np.ndarray, level: int = 6) -> bytes:
    """arr: (H, W) or (H, W, 4); dtype uint16 or uint8."""
    if arr.ndim == 2:
        ctype, ch = 0, 1
    elif arr.ndim == 3 and arr.shape[2] == 4:
        ctype, ch = 6, 4
    else:
        raise ValueError(f"unsupported shape {arr.shape}")
    if arr.dtype == np.uint16:
        depth = 16
        raw = arr.astype(">u2").reshape(arr.shape[0], -1).view(np.uint8)
    elif arr.dtype == np.uint8:
        depth = 8
        raw = np.ascontiguousarray(arr).reshape(arr.shape[0], -1)
    else:
        raise ValueError(f"unsupported dtype {arr.dtype}")
    h, w = arr.shape[:2]
    raw = raw.reshape(h, w * ch * depth // 8)
    up = raw.copy()
    up[1:] = (raw[1:].astype(np.int16) - raw[:-1].astype(np.int16)).astype(np.uint8)
    rows = np.empty((h, up.shape[1] + 1), np.uint8)
    rows[:, 0] = 2  # filter Up (row 0: Up against an all-zero previous row == raw)
    rows[:, 1:] = up
    ihdr = struct.pack(">IIBBBBB", w, h, depth, ctype, 0, 0, 0)
    return _SIG + _chunk(b"IHDR", ihdr) + _chunk(b"IDAT", zlib.compress(rows.tobytes(), level)) + _chunk(b"IEND", b"")


def decode_png(data: bytes) -> np.ndarray:
    """Inverse of encode_png (filter Up only)."""
    if data[:8] != _SIG:
        raise ValueError("not a PNG")
    pos = 8
    idat = b""
    w = h = depth = ctype = None
    while pos < len(data):
        (n,) = struct.unpack(">I", data[pos:pos + 4])
        tag = data[pos + 4:pos + 8]
        body = data[pos + 8:pos + 8 + n]
        pos += 12 + n
        if tag == b"IHDR":
            w, h, depth, ctype = struct.unpack(">IIBB", body[:10])
        elif tag == b"IDAT":
            idat += body
    ch = {0: 1, 6: 4}[ctype]
    rows = np.frombuffer(zlib.decompress(idat), np.uint8).reshape(h, -1)
    if not (rows[:, 0] == 2).all():
        raise ValueError("decode_png: only filter Up is supported")
    raw = _unup(rows[:, 1:])
    if depth == 16:
        out = raw.reshape(h, -1).view(">u2").astype(np.uint16)
    else:
        out = raw
    return out.reshape(h, w, ch) if ch > 1 else out.reshape(h, w)


def _unup(f: np.ndarray) -> np.ndarray:
    # Up filter is a per-column running sum mod 256.
    return (np.cumsum(f.astype(np.uint32), axis=0) & 0xFF).astype(np.uint8)
