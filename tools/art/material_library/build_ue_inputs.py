"""M_UM_Figure v2 inputs for UE: detail Texture2DArrays, the class LUT (global + per hero), default/test textures.

    python tools/art/material_library/build_ue_inputs.py                       # global LUT, arrays, test textures
    python tools/art/material_library/build_ue_inputs.py --hero Merlin --overrides <overrides.json>   # + hero LUT

Input   docs/art-pipeline/material-library/um-material-presets-v1.json   (classes, numbers)
        art/material-library/v1/tiles/<class>/<class>_Detail{N,RMH}.png (library v1 tiles, source of truth)
Output  art/material-library/v2-ue/arrays/T_UM_DetailN_Array.dds     16 x 1024^2 RGBA8 (DX10 2D array, mip 0 only;
        art/material-library/v2-ue/arrays/T_UM_DetailRMH_Array.dds   not committed: rebuilt byte-exact from the tiles)
        art/material-library/v2-ue/lut/T_UM_MatLUT_<Name>.dds        16 x 16 RGBA16F (committed, 2 KB)
        art/material-library/v2-ue/textures/*.png                    MatID default + test textures (committed)
        art/material-library/v2-ue/ue-inputs-report.json             layout, fixes, sha256 of every output

Array slice = class index (slice 0 = flat: N (0,0,1), RMH (0.5, 1, 0.5)). 512 px tiles are repeated 2 x 2 to 1024 and
their tilesPerMeter is halved in the LUT (same texel density, README section 5). The UE import (DDS 2D array ->
Texture2DArray, compression/sRGB/mips) is tools/art/material_library/ue/um_v2_import.py.

Fixes of the v1 tiles applied here (the v1 PNGs stay the source of truth; the report lists every fix and its numbers):
  - normal tilt: the mean xy of every DetailN slice is removed (up to 0.009 in v1: a constant 0.5 deg tilt);
  - near-flat DetailN (xy RMS < 0.01: gold_antique, stone_base; the 8-bit quantisation floor) is replaced by a normal
    derived from the tile's own height (B) with periodic central differences, scaled to an art RMS (FLAT_FIX);
    brass has no height (B constant) and stays flat (residual, its LUT normalStrength is kept);
  - roughness variation R of the procedural tiles (skin, silk, feathers) is re-centred to mean 0.5 (v1: 0.588, 0.538,
    0.468 -> the class roughness mean drifted by up to +0.02 from the preset typical).
Deterministic: no timestamps, fixed order; the same inputs give the same bytes.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import struct
import sys
from pathlib import Path

import numpy as np
from PIL import Image

REPO = Path(__file__).resolve().parents[3]
PRESETS = REPO / "docs" / "art-pipeline" / "material-library" / "um-material-presets-v1.json"
TILES = REPO / "art" / "material-library" / "v1" / "tiles"
OUT = REPO / "art" / "material-library" / "v2-ue"
GENERATOR = "tools/art/material_library/build_ue_inputs.py"
GENERATOR_VERSION = "2.0.0"
SLICE = 1024
N_CLASSES = 16
LUT_W, LUT_H = 16, 16
LUMA = np.array([0.2126, 0.7152, 0.0722])
PROCEDURAL = ("silk", "feathers", "skin")
FLAT_RMS = 0.01
# class -> (target xy RMS of the height-derived normal, periodic gaussian sigma in px before the gradient)
FLAT_FIX = {"gold_antique": (0.045, 1.0), "stone_base": (0.035, 1.5)}

# LUT rows (column = class index). README section 4 has rows 0-7; rows 8-9 are added in v2 (hero statistics, skin
# cavity tint), rows 10-15 are reserved (0). Every value is linear, read with Load (no filtering).
LUT_ROWS = {
    0: ("bcR", "bcG", "bcB", "metallic"),
    1: ("roughTypical", "roughLo", "roughHi", "roughVariation"),
    2: ("specular", "clothAmount", "bakeLuminanceModulation", "bcMode"),
    3: ("sheenIntensity", "sheenTint", "sheenRoughness", "shadingModel"),
    4: ("tilesPerMeter", "normalStrength", "slice", "cavityDarken"),
    5: ("wearStrength", "wornRoughness", "wornRoughnessDelta", "wornBCScale"),
    6: ("wornBCR", "wornBCG", "wornBCB", "wornBCMode"),
    7: ("luminanceMin", "luminanceMax", "maxChannel", "teamDyeAllowed"),
    8: ("ymedClassHero", "reserved", "reserved", "reserved"),
    9: ("cavityTintR", "cavityTintG", "cavityTintB", "cavityTintStrength"),
}
LUT_ROW_NOTES = {
    "bcMode": "0 bake-clamped (dielectric: hero bake clamped to the class luminance band), 1 preset-f0 (metal: preset "
              "F0 x clamp(Y(bake)/ymedClassHero, 1 - m, 1 + m))",
    "shadingModel": "0 DefaultLit, 1 Cloth (From Material Expression, per pixel)",
    "slice": "Texture2DArray slice of DetailN/DetailRMH (= class index; 0 = flat)",
    "tilesPerMeter": "detail tiles per metre of object space; halved for 512 px tiles repeated 2 x 2 in the 1024 slice",
    "wornRoughness": "absolute roughness of worn edges; -1 = use roughness + wornRoughnessDelta",
    "wornBCMode": "1 = worn base colour is absolute (wornBC, metals: bare metal), 0 = base colour x wornBCScale",
    "teamDyeAllowed": "1 = TeamColor dye allowed on this class (TeamMask x this flag); class 0 (legacy bake) keeps the v1 "
                      "behaviour (TeamMask only)",
    "ymedClassHero": "median luminance of the hero bake inside the class (hero LUT, written by the MatID generator); "
                     "0 = unknown -> no bake luminance modulation (metal = flat preset F0)",
    "cavityTint": "skin: AO colour = lerp(cavityTint, 1, AO); BC x lerp(1, AO colour, strength) (subsurfaceApprox)",
}


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def rel(path: Path) -> str:
    return path.resolve().relative_to(REPO).as_posix()


# ------------------------------------------------------------------ DDS (DX10 header, 2D texture array, mip 0)

DXGI = {"R8G8B8A8_UNORM": (28, 4), "R16G16B16A16_FLOAT": (10, 8)}


def write_dds(path: Path, slices, fmt: str) -> None:
    code, bpp = DXGI[fmt]
    h, w = slices[0].shape[:2]
    flags = 0x1 | 0x2 | 0x4 | 0x1000 | 0x8          # CAPS HEIGHT WIDTH PIXELFORMAT PITCH
    pixel_format = struct.pack("<II4sIIIII", 32, 0x4, b"DX10", 0, 0, 0, 0, 0)
    header = (struct.pack("<IIIIIII11I", 124, flags, h, w, w * bpp, 0, 1, *([0] * 11)) + pixel_format
              + struct.pack("<IIIII", 0x1000, 0, 0, 0, 0))
    dx10 = struct.pack("<IIIII", code, 3, 0, len(slices), 0)  # DIMENSION_TEXTURE2D, array size
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "wb") as handle:
        handle.write(b"DDS " + header + dx10)
        for s in slices:
            assert s.shape[:2] == (h, w)
            handle.write(np.ascontiguousarray(s).tobytes())


# ------------------------------------------------------------------ presets -> LUT

def load_presets() -> dict:
    return json.loads(PRESETS.read_text(encoding="utf-8"))


def class_columns(presets: dict) -> dict:
    """Class index -> {field: value} of the LUT (README section 4 + v2 rows 8-9)."""
    cols = {}
    for c in presets["classes"]:
        i = c["index"]
        f = {k: 0.0 for row in LUT_ROWS.values() for k in row if k != "reserved"}
        f["classId"] = c["id"]
        if i == 0:  # legacy bake: the shader takes the v1 path, only the dye flag is read
            f.update(teamDyeAllowed=1.0, roughLo=0.0, roughHi=1.0, maxChannel=1.0, luminanceMax=1.0)
            cols[i] = f
            continue
        bc = c["baseColor"]
        f["bcR"], f["bcG"], f["bcB"] = bc["typicalLinear"]
        f["metallic"] = float(c["metallic"])
        r = c["roughness"]
        f["roughTypical"], (f["roughLo"], f["roughHi"]), f["roughVariation"] = r["typical"], r["range"], r["variation"]
        f["specular"] = 0.5 if c.get("specular") is None else c["specular"]["value"]
        f["bcMode"] = 1.0 if bc["mode"] == "preset-f0" else 0.0
        f["bakeLuminanceModulation"] = bc.get("bakeLuminanceModulation", 0.0)
        lum = bc.get("luminanceRange", [0.0, 1.0])
        f["luminanceMin"], f["luminanceMax"] = lum
        f["maxChannel"] = bc.get("maxChannel", 1.0)
        cloth = c.get("cloth")
        if cloth:
            f["clothAmount"] = cloth["clothAmount"]
            f["sheenIntensity"] = cloth["sheenColor"]["intensity"]
            f["sheenTint"] = cloth["sheenColor"]["tint"]
            f["sheenRoughness"] = cloth["sheenRoughness"]
            f["shadingModel"] = 1.0
        d = c["detail"]
        f["tilesPerMeter"] = d["tilesPerMeter"] * (SLICE / d["tileSizePx"]) ** -1 if d["tileSizePx"] < SLICE \
            else d["tilesPerMeter"]
        f["normalStrength"] = d["normalStrength"]
        f["slice"] = float(i)
        f["cavityDarken"] = c.get("ageing", {}).get("cavityDarken", 0.0)
        w = c.get("edgeWear", {})
        f["wornRoughness"] = -1.0
        f["wornBCScale"] = 1.0
        if w.get("enabled"):
            f["wearStrength"] = w["strength"]
            if "wornRoughness" in w:
                f["wornRoughness"] = w["wornRoughness"]
            f["wornRoughnessDelta"] = w.get("wornRoughnessDelta", 0.0)
            if "wornBaseColorLinear" in w:
                f["wornBCR"], f["wornBCG"], f["wornBCB"] = w["wornBaseColorLinear"]
                f["wornBCMode"] = 1.0
            f["wornBCScale"] = w.get("wornBaseColorScale", 1.0)
        f["teamDyeAllowed"] = 1.0 if c.get("teamDyeAllowed") else 0.0
        ss = c.get("subsurfaceApprox")
        if ss:
            f["cavityTintR"], f["cavityTintG"], f["cavityTintB"] = ss["cavityTintLinear"]
            f["cavityTintStrength"] = ss["strength"]
        cols[i] = f
    return cols


def apply_overrides(cols: dict, overrides: dict, presets: dict) -> list:
    """overrides = {"classes": {"<class id>": {"<LUT field>": value, "bc": [r, g, b], "wornBC": [...], ...}}}."""
    by_id = {c["id"]: c["index"] for c in presets["classes"]}
    applied = []
    for cid, fields in sorted((overrides.get("classes") or {}).items()):
        if cid not in by_id:
            raise SystemExit("override for unknown class %s" % cid)
        col = cols[by_id[cid]]
        for key, value in sorted(fields.items()):
            if key in ("bc", "wornBC", "cavityTint"):
                for ch, v in zip("RGB", value):
                    col[key + ch] = float(v)
            elif key in col:
                col[key] = float(value)
            else:
                raise SystemExit("override %s.%s: unknown LUT field" % (cid, key))
            applied.append({"class": cid, "field": key, "value": value})
    return applied


def lut_array(cols: dict) -> np.ndarray:
    lut = np.zeros((LUT_H, LUT_W, 4), np.float32)
    for i, f in cols.items():
        for row, names in LUT_ROWS.items():
            lut[row, i] = [0.0 if n == "reserved" else f[n] for n in names]
    return lut


# ------------------------------------------------------------------ tiles -> slices

def periodic_blur(img: np.ndarray, sigma: float) -> np.ndarray:
    h, w = img.shape
    fy, fx = np.fft.fftfreq(h)[:, None], np.fft.fftfreq(w)[None, :]
    k = np.exp(-2.0 * (np.pi * sigma) ** 2 * (fx ** 2 + fy ** 2))
    return np.real(np.fft.ifft2(np.fft.fft2(img) * k))


def normal_stats(n: np.ndarray) -> dict:
    xy = n[..., :2]
    return {"rms_xy": round(float(np.sqrt((xy ** 2).sum(-1).mean())), 5),
            "mean_xy": [round(float(v), 5) for v in xy.reshape(-1, 2).mean(0)]}


def encode_unorm8(v: np.ndarray) -> np.ndarray:
    return np.clip(np.floor(v * 255.0 + 0.5), 0, 255).astype(np.uint8)


def build_slices(presets: dict) -> tuple:
    n_slices, rmh_slices, info = [], [], {}
    flat_n = np.zeros((SLICE, SLICE, 4), np.uint8)
    flat_n[...] = (128, 128, 255, 255)
    flat_rmh = np.zeros((SLICE, SLICE, 4), np.uint8)
    flat_rmh[...] = (128, 255, 128, 255)
    n_slices.append(flat_n)
    rmh_slices.append(flat_rmh)
    info[0] = {"class": "legacy_bake", "slice": "flat (N 128,128,255; RMH 128,255,128)"}
    for c in presets["classes"][1:]:
        cid, i = c["id"], c["index"]
        pn = TILES / cid / ("%s_DetailN.png" % cid)
        pr = TILES / cid / ("%s_DetailRMH.png" % cid)
        n8 = np.asarray(Image.open(pn).convert("RGB"), np.float64) / 255.0
        r8 = np.asarray(Image.open(pr).convert("RGB"), np.float64) / 255.0
        n = n8 * 2.0 - 1.0
        entry = {"class": cid, "tileN": rel(pn), "tileRMH": rel(pr), "tileN_sha256": sha(pn), "tileRMH_sha256": sha(pr),
                 "tile_px": n8.shape[0], "fixes": []}
        entry["normal_v1"] = normal_stats(n)
        if entry["normal_v1"]["rms_xy"] < FLAT_RMS and cid in FLAT_FIX:
            target, sigma = FLAT_FIX[cid]
            hgt = periodic_blur(r8[..., 2], sigma)
            gx = (np.roll(hgt, -1, 1) - np.roll(hgt, 1, 1)) * 0.5   # dh/dcol
            gy = (np.roll(hgt, -1, 0) - np.roll(hgt, 1, 0)) * 0.5   # dh/drow
            rms = float(np.sqrt((gx ** 2 + gy ** 2).mean()))
            k = target / max(rms, 1e-9)
            for _ in range(4):  # rms of normalised xy is slightly below k * rms
                v = np.stack([-k * gx, -k * gy, np.ones_like(gx)], -1)
                v /= np.linalg.norm(v, axis=-1, keepdims=True)
                got = float(np.sqrt((v[..., :2] ** 2).sum(-1).mean()))
                k *= target / got
            n = v
            entry["fixes"].append({"fix": "normal from height", "reason": "v1 DetailN xy RMS %.4f < %.2f (flat)" % (
                entry["normal_v1"]["rms_xy"], FLAT_RMS), "height_blur_sigma_px": sigma, "target_rms_xy": target,
                "convention": "DirectX: x = -dh/dcol, y = -dh/drow (same as the v1 tiles)"})
        elif entry["normal_v1"]["rms_xy"] < FLAT_RMS:
            entry["fixes"].append({"fix": "none (residual)", "reason": "flat DetailN and constant height (B): nothing "
                                                                          "to derive a relief from"})
        mean_xy = n[..., :2].reshape(-1, 2).mean(0)
        if np.abs(mean_xy).max() > 1e-4:
            n[..., :2] -= mean_xy
            entry["fixes"].append({"fix": "tilt removed", "mean_xy_before": [round(float(x), 5) for x in mean_xy]})
        n[..., 2] = np.maximum(n[..., 2], 1e-3)
        n /= np.linalg.norm(n, axis=-1, keepdims=True)
        r = r8.copy()
        if cid in PROCEDURAL:
            shift = float(r[..., 0].mean()) - 0.5
            r[..., 0] = np.clip(r[..., 0] - shift, 0.0, 1.0)
            entry["fixes"].append({"fix": "roughness variation re-centred", "R_mean_before": round(shift + 0.5, 5),
                                   "R_mean_after": round(float(r[..., 0].mean()), 5)})
        reps = SLICE // n.shape[0]
        if reps > 1:
            n = np.tile(n, (reps, reps, 1))
            r = np.tile(r, (reps, reps, 1))
            entry["fixes"].append({"fix": "tiled %dx%d to %d px" % (reps, reps, SLICE),
                                   "lut_tilesPerMeter": "preset / %d" % reps})
        entry["normal_slice"] = normal_stats(n)
        entry["R_mean_slice"] = round(float(r[..., 0].mean()), 5)
        nq = np.concatenate([encode_unorm8(n * 0.5 + 0.5), np.full(n.shape[:2] + (1,), 255, np.uint8)], -1)
        rq = np.concatenate([encode_unorm8(r), np.full(r.shape[:2] + (1,), 255, np.uint8)], -1)
        n_slices.append(nq)
        rmh_slices.append(rq)
        info[i] = entry
    return n_slices, rmh_slices, info


# ------------------------------------------------------------------ small textures

def class_colour(i: int) -> tuple:
    """Debug colour per class (golden-angle hues), sRGB 8-bit."""
    import colorsys
    if i == 0:
        return (40, 40, 40)
    h = (i * 0.618034) % 1.0
    r, g, b = colorsys.hsv_to_rgb(h, 0.75, 0.95)
    return tuple(int(round(v * 255)) for v in (r, g, b))


def linear_to_srgb8(v: np.ndarray) -> np.ndarray:
    v = np.clip(v, 0.0, 1.0)
    s = np.where(v <= 0.0031308, v * 12.92, 1.055 * np.power(v, 1.0 / 2.4) - 0.055)
    return encode_unorm8(s)


def small_textures(cols: dict) -> dict:
    """MatID default (all legacy) and the test textures of the class-checker sphere.

    Checker on the engine sphere UV: 8 columns in U (4 classes repeated twice around) x 4 rows in V -> classes
    row * 4 + col % 4 (0..15); every half of the sphere shows all 16 classes."""
    out = {}
    out["T_UM_MatID_Legacy"] = (np.full((4, 4), 8, np.uint8), "L", "MatID default: every pixel class 0 (legacy bake)")
    mid = np.zeros((256, 256), np.uint8)
    bc = np.zeros((512, 512, 3), np.float64)
    ys, xs = np.mgrid[0:512, 0:512]
    fine = (((xs // 8) + (ys // 8)) % 2).astype(np.float64)  # 8 px checker inside metal cells (bake modulation)
    for row in range(4):
        for col in range(8):
            cls = row * 4 + (col % 4)
            mid[row * 64:(row + 1) * 64, col * 32:(col + 1) * 32] = cls * 16 + 8
            f = cols[cls]
            y0, y1, x0, x1 = row * 128, (row + 1) * 128, col * 64, (col + 1) * 64
            if cls == 0:
                bc[y0:y1, x0:x1] = (0.18, 0.18, 0.18)
            elif f["bcMode"] > 0.5:   # metal: a mid-grey bake with a fine pattern (the shader uses preset F0)
                bc[y0:y1, x0:x1] = (0.20 + 0.10 * fine[y0:y1, x0:x1])[..., None]
            else:
                bc[y0:y1, x0:x1] = (f["bcR"], f["bcG"], f["bcB"])
    out["T_UM_Test_MatIDChecker"] = (mid, "L", "test: class checker (8 x 4 cells on UV0, classes row*4 + col%4)")
    out["T_UM_Test_BCChecker"] = (linear_to_srgb8(bc), "RGB",
                                  "test: bake albedo of the checker (class typical colour; metals 0.2/0.3 grey 8 px "
                                  "pattern)")
    ramp = np.tile(np.clip((np.arange(256) / 255.0 - 0.25) * 2.0, 0, 1)[None, :], (256, 1))
    out["T_UM_Test_EdgeRamp"] = (encode_unorm8(ramp), "L", "test: edge mask ramp along U (0 for u < 0.25, 1 for u > 0.75)")
    return out


# ------------------------------------------------------------------ main

def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--hero", help="also write T_UM_MatLUT_<hero>.dds from --overrides")
    ap.add_argument("--overrides", help="hero overrides JSON ({\"classes\": {class id: {LUT field: value}}})")
    ap.add_argument("--skip-arrays", action="store_true", help="LUT and small textures only")
    a = ap.parse_args()
    presets = load_presets()
    if [c["index"] for c in presets["classes"]] != list(range(N_CLASSES)):
        raise SystemExit("presets must list classes 0..15 in order")
    report_path = OUT / "ue-inputs-report.json"
    old = json.loads(report_path.read_text(encoding="utf-8")) if report_path.is_file() else {}
    report = {"schema": "unmatched.um-v2-ue-inputs/1", "generator": GENERATOR, "generator_version": GENERATOR_VERSION,
              "presets": rel(PRESETS), "presets_sha256": sha(PRESETS),
              "lut": {"size": [LUT_W, LUT_H], "format": "RGBA16F (DDS R16G16B16A16_FLOAT)", "column": "class index",
                      "rows": {str(k): list(v) for k, v in LUT_ROWS.items()}, "rows_reserved": "10-15 (0)",
                      "notes": LUT_ROW_NOTES, "files": dict(old.get("lut", {}).get("files", {}))},
              "arrays": old.get("arrays", {}), "textures": {}}
    cols = class_columns(presets)
    lut_dir = OUT / "lut"
    lut = lut_array(cols)
    p = lut_dir / "T_UM_MatLUT_Global.dds"
    write_dds(p, [lut.astype(np.float16)], "R16G16B16A16_FLOAT")
    report["lut"]["files"]["Global"] = {"file": rel(p), "sha256": sha(p), "overrides": []}
    report["lut"]["columns_global"] = {str(i): {k: (round(v, 6) if isinstance(v, float) else v)
                                                for k, v in sorted(f.items())} for i, f in cols.items()}
    q = lut.astype(np.float16).astype(np.float32)
    report["lut"]["half_max_abs_error"] = round(float(np.abs(q - lut).max()), 6)
    if a.hero:
        if not a.overrides:
            raise SystemExit("--hero needs --overrides")
        hero_cols = json.loads(json.dumps(cols))
        hero_cols = {int(k): v for k, v in hero_cols.items()}
        ov_path = Path(a.overrides).resolve()
        applied = apply_overrides(hero_cols, json.loads(ov_path.read_text(encoding="utf-8")), presets)
        hp = lut_dir / ("T_UM_MatLUT_%s.dds" % a.hero)
        write_dds(hp, [lut_array(hero_cols).astype(np.float16)], "R16G16B16A16_FLOAT")
        report["lut"]["files"][a.hero] = {"file": rel(hp), "sha256": sha(hp), "overrides_file": rel(ov_path),
                                          "overrides_sha256": sha(ov_path), "overrides": applied}
    tex_dir = OUT / "textures"
    tex_dir.mkdir(parents=True, exist_ok=True)
    for name, (arr, mode, note) in small_textures(cols).items():
        tp = tex_dir / (name + ".png")
        Image.fromarray(arr, mode).save(tp, optimize=False, compress_level=9)
        report["textures"][name] = {"file": rel(tp), "sha256": sha(tp), "size": [arr.shape[1], arr.shape[0]],
                                    "mode": mode, "note": note}
    if not a.skip_arrays:
        n_slices, rmh_slices, info = build_slices(presets)
        arr_dir = OUT / "arrays"
        pn, pr = arr_dir / "T_UM_DetailN_Array.dds", arr_dir / "T_UM_DetailRMH_Array.dds"
        write_dds(pn, n_slices, "R8G8B8A8_UNORM")
        write_dds(pr, rmh_slices, "R8G8B8A8_UNORM")
        report["arrays"] = {
            "slice_px": SLICE, "slices": N_CLASSES, "format_source": "DDS R8G8B8A8_UNORM 2D array, mip 0",
            "DetailN": {"file": rel(pn), "sha256": sha(pn), "ue": "TC_Normalmap (BC5), sRGB off, mips from source"},
            "DetailRMH": {"file": rel(pr), "sha256": sha(pr), "ue": "TC_BC7, sRGB off, mips from source"},
            "per_slice": {str(k): v for k, v in sorted(info.items())}}
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, indent=1, sort_keys=True, ensure_ascii=False) + "\n", encoding="utf-8",
                           newline="\n")
    print("LUT", report["lut"]["files"]["Global"]["sha256"][:12], "half err", report["lut"]["half_max_abs_error"])
    if not a.skip_arrays:
        print("DetailN", report["arrays"]["DetailN"]["sha256"][:12], "DetailRMH", report["arrays"]["DetailRMH"]["sha256"][:12])
        for k, v in report["arrays"]["per_slice"].items():
            if v.get("fixes"):
                print(" ", k, v["class"], [f["fix"] for f in v["fixes"]], v.get("normal_slice"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
