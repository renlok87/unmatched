"""Look-dev v2 of King Arthur: the hero LUT file of the Blender stage (16 x 8 RGBA16F OpenEXR, README section 4).

Rows 0-7 = README section 4 = rows 0-7 of build_ue_inputs.LUT_ROWS (the v2 master adds rows 8-9: ymedClassHero, skin
cavity tint). As Merlin's look-dev (LDM-7), ymedClassHero of the metal columns is ALSO written into row 7.R (the
luminance clamp of a metal is unused there); the UE import rebuilds the 16 x 16 LUT from reports/ld-lut.json with
lookdev_ue_inputs.py, so the EXR is the Blender-stage record, not the UE input. Column 0 (legacy_bake) is zero.

write_exr() / read_exr(): the minimal byte-deterministic OpenEXR 2.0 writer/reader of h2_bake_merlin/lookdev_lut.py
(scanline, uncompressed, HALF RGBA), copied so the two hero modules stay independent.
"""

import struct

import numpy as np

ROWS = 8
COLS = 16


def exr_rows(lut16, ymed_by_index):
    """lut16: build_ue_inputs.lut_array (16 x 16 x 4) -> the 8 x 16 x 4 EXR payload (row 7.R of metals = Ymed)."""
    out = np.array(lut16[:ROWS], np.float64)
    for i, y in ymed_by_index.items():
        out[7, i, 0] = y
    out[:, 0, :] = 0.0
    return out


def _attr(name, kind, payload):
    return name.encode() + b"\0" + kind.encode() + b"\0" + struct.pack("<i", len(payload)) + payload


def write_exr(path, rgba):
    """rgba [H, W, 4] (row 0 = top = EXR y 0) -> uncompressed HALF RGBA scanline EXR."""
    rgba = np.asarray(rgba, np.float16)
    h, w, _ = rgba.shape
    chans = ("A", "B", "G", "R")  # EXR stores channels sorted by name
    chlist = b"".join(n.encode() + b"\0" + struct.pack("<iB3xii", 1, 0, 1, 1) for n in chans) + b"\0"
    box = struct.pack("<iiii", 0, 0, w - 1, h - 1)
    header = (b"\x76\x2f\x31\x01" + struct.pack("<i", 2)
              + _attr("channels", "chlist", chlist) + _attr("compression", "compression", b"\0")
              + _attr("dataWindow", "box2i", box) + _attr("displayWindow", "box2i", box)
              + _attr("lineOrder", "lineOrder", b"\0") + _attr("pixelAspectRatio", "float", struct.pack("<f", 1.0))
              + _attr("screenWindowCenter", "v2f", struct.pack("<ff", 0.0, 0.0))
              + _attr("screenWindowWidth", "float", struct.pack("<f", 1.0)) + b"\0")
    idx = {"R": 0, "G": 1, "B": 2, "A": 3}
    line_bytes = w * 2 * 4
    first = len(header) + 8 * h
    offsets = b"".join(struct.pack("<Q", first + y * (8 + line_bytes)) for y in range(h))
    blocks = []
    for y in range(h):
        data = b"".join(rgba[y, :, idx[n]].astype("<f2").tobytes() for n in chans)
        blocks.append(struct.pack("<ii", y, len(data)) + data)
    with open(path, "wb") as f:
        f.write(header + offsets + b"".join(blocks))


def read_exr(path):
    """Reader for the subset write_exr produces (uncompressed HALF scanline). Returns [H, W, 4] float16 RGBA."""
    b = open(path, "rb").read()
    if b[:4] != b"\x76\x2f\x31\x01":
        raise ValueError("not an EXR")
    i = 8
    attrs = {}
    while b[i] != 0:
        j = b.index(b"\0", i)
        name = b[i:j].decode()
        k = b.index(b"\0", j + 1)
        kind = b[j + 1:k].decode()
        n = struct.unpack_from("<i", b, k + 1)[0]
        attrs[name] = (kind, b[k + 5:k + 5 + n])
        i = k + 5 + n
    i += 1
    if attrs["compression"][1] != b"\0":
        raise ValueError("compressed EXR not supported")
    x0, y0, x1, y1 = struct.unpack("<iiii", attrs["dataWindow"][1])
    w, h = x1 - x0 + 1, y1 - y0 + 1
    cl = attrs["channels"][1]
    chans, p = [], 0
    while cl[p] != 0:
        q = cl.index(b"\0", p)
        chans.append(cl[p:q].decode())
        if struct.unpack_from("<i", cl, q + 1)[0] != 1:
            raise ValueError("only HALF channels")
        p = q + 1 + 16
    offsets = struct.unpack_from("<%dQ" % h, b, i)
    out = np.zeros((h, w, 4), np.float16)
    idx = {"R": 0, "G": 1, "B": 2, "A": 3}
    for off in offsets:
        y, n = struct.unpack_from("<ii", b, off)
        data = np.frombuffer(b, "<f2", count=w * len(chans), offset=off + 8)
        for ci, name in enumerate(chans):
            out[y - y0, :, idx[name]] = data[ci * w:(ci + 1) * w]
    return out
