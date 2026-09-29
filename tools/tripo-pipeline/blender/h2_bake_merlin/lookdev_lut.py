"""Look-dev v2: the material LUT of a hero (16 x 8 RGBA16F) from the UM library presets v1 + hero overrides.

Layout = docs/art-pipeline/material-library/README.md §4 (column = class index, row = parameter group):
  row 0  BC typical r g b | metallic
  row 1  roughness typical | range lo | range hi | variation
  row 2  specular | clothAmount | bakeLuminanceModulation | bcMode (0 bake-clamped, 1 preset-f0)
  row 3  sheen intensity | sheen tint | sheenRoughness | shadingModel (0 DefaultLit, 1 Cloth)
  row 4  tilesPerMeter (512 tiles / 2: they are repeated 2 x 2 in the 1K array slice) | normalStrength | array slice | cavityDarken
  row 5  wear strength | wornRoughness (absolute, -1 = none) | wornRoughnessDelta | wornBCScale
  row 6  worn BC r g b | wornBCMode (0 scale, 1 absolute)
  row 7  luminance min | luminance max | maxChannel | teamDyeAllowed
Metals (bcMode 1) have no luminance clamp; README §4 names Ymed_class_hero (median luminance of the baked albedo inside
the class) as LUT data but gives it no cell: here it is row 7.R of the metal columns (proposal, recorded in the look-dev
decisions). Column 0 (legacy_bake) is all zero: the shader does not read it.

write_exr(): minimal OpenEXR 2.0 writer (scanline, uncompressed, HALF RGBA, no metadata besides the required
attributes) -> byte-deterministic; read_exr() parses the same subset for the round-trip check.
"""

import copy
import struct

import numpy as np

ROWS = 8
COLS = 16
# review colours of the MatID classes present on the heroes (index -> linear RGB); 0 = legacy_bake black
CLASS_COLOURS = {0: (0.0, 0.0, 0.0), 6: (0.9, 0.45, 0.1), 8: (0.1, 0.8, 0.2), 9: (0.15, 0.2, 0.8), 11: (1.0, 0.85, 0.1),
                 13: (1.0, 0.6, 0.45), 14: (0.4, 0.4, 0.45), 15: (0.45, 0.28, 0.12)}


def _get(d, path, default):
    for k in path:
        if not isinstance(d, dict) or k not in d or d[k] is None:
            return default
        d = d[k]
    return d


def deep_merge(base, over):
    out = copy.deepcopy(base)
    for k, v in over.items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = deep_merge(out[k], v)
        else:
            out[k] = copy.deepcopy(v)
    return out


def column(c):
    """8 x 4 float values of one class preset (already merged with the hero override)."""
    col = np.zeros((ROWS, 4), np.float64)
    if c["id"] == "legacy_bake":
        return col
    metal = int(c["metallic"]) == 1
    bc = c["baseColor"]
    col[0, :3] = bc["typicalLinear"]
    col[0, 3] = c["metallic"]
    r = c["roughness"]
    col[1] = [r["typical"], r["range"][0], r["range"][1], r["variation"]]
    spec = c.get("specular")
    col[2, 0] = 0.5 if (metal or spec is None) else spec["value"]
    cloth = c.get("cloth")
    col[2, 1] = cloth["clothAmount"] if cloth else 0.0
    col[2, 2] = bc.get("bakeLuminanceModulation", 0.0) if metal else 0.0
    col[2, 3] = 1.0 if bc["mode"] == "preset-f0" else 0.0
    if cloth:
        col[3] = [cloth["sheenColor"]["intensity"], cloth["sheenColor"]["tint"], cloth["sheenRoughness"], 1.0]
    det = c["detail"]
    tpm = float(det["tilesPerMeter"])
    if int(det["tileSizePx"]) == 512:
        tpm /= 2.0
    col[4] = [tpm, det.get("normalStrength", 1.0), c["index"], _get(c, ("ageing", "cavityDarken"), 0.0)]
    w = c.get("edgeWear", {})
    if w.get("enabled"):
        col[5] = [w["strength"], w.get("wornRoughness", -1.0), w.get("wornRoughnessDelta", 0.0), w.get("wornBaseColorScale", 1.0)]
        if "wornBaseColorLinear" in w:
            col[6] = list(w["wornBaseColorLinear"]) + [1.0]
    else:
        col[5] = [0.0, -1.0, 0.0, 1.0]
    if metal:
        col[7] = [c.get("heroYmed", 0.0), 0.0, 1.0, 1.0 if c.get("teamDyeAllowed") else 0.0]
    else:
        col[7] = [bc["luminanceRange"][0], bc["luminanceRange"][1], bc.get("maxChannel", 1.0), 1.0 if c.get("teamDyeAllowed") else 0.0]
    return col


def build(presets, overrides=None):
    """presets: um-material-presets-v1.json; overrides: {class id: partial preset}. Returns (lut [8,16,4] float64,
    merged classes by id)."""
    overrides = overrides or {}
    classes = {}
    lut = np.zeros((ROWS, COLS, 4), np.float64)
    for c in presets["classes"]:
        m = deep_merge(c, overrides.get(c["id"], {}))
        classes[c["id"]] = m
        lut[:, int(c["index"]), :] = column(m)
    unknown = sorted(set(overrides) - set(classes))
    if unknown:
        raise ValueError("overrides for unknown classes: %s" % unknown)
    return lut, classes


def to_half(lut):
    return lut.astype(np.float16)


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
