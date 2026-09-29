"""Material library v1: detail tiles per material class from the local CC0 raw sets (plus procedural classes).

Input  art/material-library/cc0-raw/<id>/<id>_2K-JPG_{NormalDX,NormalGL,Roughness,Displacement[,AmbientOcclusion]}.jpg
       (ambientCG 2K-JPG sets downloaded by the orchestrator; not committed, see cc0-raw/manifest.json).
Output art/material-library/v1/tiles/<class>/<class>_DetailN.png     DirectX tangent-space normal (G = -dh/drow), 8-bit RGB
       art/material-library/v1/tiles/<class>/<class>_DetailRMH.png   R roughness deviation around 0.5 (0.5 = none,
                                                                      0/1 = -/+ full amplitude of the class preset)
                                                                      G cavity/AO (1 = open, lower = occluded)
                                                                      B height 0..1 (p0.5..p99.5), also the wear mask
       art/material-library/v1/textures-report.json                  sha256 of every tile + measurements
       art/material-library/v1/preview/tiles-sheet.png               contact sheet (review only)

Why the rules:
  - Downsampling is an exact box filter (2x2 / 4x4 means) over the whole 2K image: a box never reads across the wrap,
    so a seamless source stays seamless (PIL resamplers clamp at the border). Normals are averaged as vectors and
    renormalised.
  - The source normal convention is measured, not assumed: NormalDX.G must equal 1 - NormalGL.G, R equal, and the DX
    green must correlate with -dh/drow of the set's own Displacement map (the DirectX convention used by UE).
  - Procedural classes (silk, feathers, skin: no suitable CC0 set) are built on a torus (np.roll gradients, FFT
    filtering, integer thread / feather counts per tile), so they are periodic by construction.
  - Seam check: the wrap pair (last/first column, row) must be an ordinary neighbour pair: its mean difference divided
    by the p99 of all interior pair differences, per axis and map; a tile above SEAM_FIX_RATIO gets a
    variance-preserving half-offset blend and is measured again.
Deterministic: fixed seeds, no time-dependent data in the outputs (the report has no timestamps).

  python tools/art/material_library/build_library.py            # build tiles + report + preview
  python tools/art/material_library/build_library.py --sources  # also rewrite docs/.../sources.json measurements
"""
from __future__ import annotations

import argparse
import glob
import hashlib
import json
import re
import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

REPO = Path(__file__).resolve().parents[3]
RAW = REPO / "art" / "material-library" / "cc0-raw"
OUT = REPO / "art" / "material-library" / "v1"
TILES = OUT / "tiles"
REPORT = OUT / "textures-report.json"
SOURCES_JSON = REPO / "docs" / "art-pipeline" / "material-library" / "sources.json"
GENERATOR = "tools/art/material_library/build_library.py"
GENERATOR_VERSION = "1.0.0"
ROUGH_AMP_FLOOR = 0.04     # a near-constant source roughness (JPEG grain only) must not be stretched to full range
SEAM_FIX_RATIO = 1.25     # on seam_ratio (p99 outlier ratio); the validator gates the same value

# index 0 is reserved: "legacy bake" (the hero's baked ORM/BC is used as is; hair, eyes, anything unmapped)
CLASSES = [
    # index, class id, source, tile size, seed (procedural only)
    (1, "steel_blued", "Metal038", 1024, None),
    (2, "steel_polished", "Metal012", 1024, None),
    (3, "metal_forged", "Metal009", 1024, None),
    (4, "gold_antique", "Metal042A", 1024, None),
    (5, "brass", "Metal048A", 1024, None),
    (6, "bronze", "Metal008", 1024, None),
    (7, "leather_smooth", "Leather026", 1024, None),
    (8, "leather_worn", "Leather030", 1024, None),
    (9, "wool_coarse", "Fabric030", 1024, None),
    (10, "linen", "Fabric061", 512, None),
    (11, "silk", "procedural:satin5", 512, 11),
    (12, "feathers", "procedural:feathers", 1024, 12),
    (13, "skin", "procedural:skin", 512, 13),
    (14, "stone_base", "Marble012", 1024, None),
    (15, "wood", "Wood051", 1024, None),
]


# ----------------------------------------------------------------------------------------------------- helpers
def dump_json(obj) -> str:
    """indent=1 JSON with lists of numbers (and nulls) kept on one line."""
    txt = json.dumps(obj, ensure_ascii=False, indent=1)
    return re.sub(r"\[\s+((?:-?[\d.eE+-]+|null)(?:,\s+(?:-?[\d.eE+-]+|null))*)\s+\]",
                  lambda m: "[" + ", ".join(x.strip() for x in m.group(1).split(",")) + "]", txt) + "\n"


def sha256_file(p: Path) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def load01(p: Path) -> np.ndarray:
    a = np.asarray(Image.open(p)).astype(np.float64) / 255.0
    return a


def gray(a: np.ndarray) -> np.ndarray:
    return a if a.ndim == 2 else a[..., 0]


def box_down(a: np.ndarray, size: int) -> np.ndarray:
    f = a.shape[0] // size
    assert a.shape[0] == a.shape[1] == size * f, (a.shape, size)
    if a.ndim == 2:
        return a.reshape(size, f, size, f).mean(axis=(1, 3))
    return a.reshape(size, f, size, f, a.shape[2]).mean(axis=(1, 3))


def normalize(n: np.ndarray) -> np.ndarray:
    return n / np.maximum(np.linalg.norm(n, axis=-1, keepdims=True), 1e-8)


def lin_from_srgb(c: np.ndarray) -> np.ndarray:
    return np.where(c <= 0.04045, c / 12.92, ((c + 0.055) / 1.055) ** 2.4)


def _seam_parts(a: np.ndarray):
    if a.ndim == 2:
        a = a[..., None]
    a = a.astype(np.float64)
    cx = np.abs(a[:, 1:] - a[:, :-1]).mean(axis=(0, 2))     # mean |difference| of every interior column pair
    cy = np.abs(a[1:] - a[:-1]).mean(axis=(1, 2))
    ex = np.abs(a[:, 0] - a[:, -1]).mean()                   # the wrap pair
    ey = np.abs(a[0] - a[-1]).mean()
    return cx, cy, ex, ey


def _ratio(e, ref):
    if ref > 1e-9:
        return round(float(e / ref), 3)
    return 0.0 if e < 1e-9 else float("inf")


def seam_ratio(a: np.ndarray) -> tuple[float, float]:
    """(x, y) seam outlier ratio: wrap-pair difference / p99 of the interior column (row) pair differences.
    <= 1: the wrap is an ordinary neighbour; a cut tile gives 1.3-2+. Robust for periodic patterns (weave, satin),
    where the wrap can coincide with a thread edge and a mean-based ratio reads ~2 on a perfectly periodic tile."""
    cx, cy, ex, ey = _seam_parts(a)
    return _ratio(ex, np.percentile(cx, 99)), _ratio(ey, np.percentile(cy, 99))


def seam_ratio_mean(a: np.ndarray) -> tuple[float, float]:
    """Informational: wrap-pair difference / mean interior pair difference (~1 for noise-like tiles)."""
    cx, cy, ex, ey = _seam_parts(a)
    return _ratio(ex, cx.mean()), _ratio(ey, cy.mean())


def periodic_gauss(a: np.ndarray, sigma: float) -> np.ndarray:
    """Gaussian blur on the torus (FFT)."""
    n = a.shape[0]
    f = np.fft.fftfreq(n)
    g = np.exp(-2.0 * (np.pi * sigma) ** 2 * (f[:, None] ** 2 + f[None, :] ** 2))
    return np.real(np.fft.ifft2(np.fft.fft2(a) * g))


def grad_rows_cols(h: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Central differences on the torus: (dh/drow, dh/dcol)."""
    return ((np.roll(h, -1, 0) - np.roll(h, 1, 0)) * 0.5, (np.roll(h, -1, 1) - np.roll(h, 1, 1)) * 0.5)


def normal_dx_from_height(h_px: np.ndarray) -> np.ndarray:
    """h_px: height in pixel units. DirectX tangent-space normal: x = -dh/dcol, y = -dh/drow (green points down the
    image = +V in UE's texture space), z = 1."""
    dr, dc = grad_rows_cols(h_px)
    return normalize(np.stack([-dc, -dr, np.ones_like(h_px)], axis=-1))


def corr(a: np.ndarray, b: np.ndarray) -> float:
    a = a.ravel() - a.mean()
    b = b.ravel() - b.mean()
    d = np.sqrt((a * a).sum() * (b * b).sum())
    return float((a * b).sum() / d) if d > 1e-12 else 0.0


def offset_blend(a: np.ndarray, is_normal: bool) -> np.ndarray:
    """Variance-preserving half-offset blend (the seam of the shifted copy lands where its weight is 0)."""
    n = a.shape[0]
    t = np.abs(np.arange(n) - (n - 1) / 2.0) / ((n - 1) / 2.0)          # 0 centre .. 1 edge
    w1 = np.clip((np.maximum(t[:, None], t[None, :]) - 0.6) / 0.4, 0, 1)  # weight of the shifted copy
    w1 = w1 * w1 * (3 - 2 * w1)
    w0 = 1.0 - w1
    b = np.roll(np.roll(a, n // 2, 0), n // 2, 1)
    if a.ndim == 3:
        w0, w1 = w0[..., None], w1[..., None]
    mean = a.mean(axis=(0, 1))
    out = (a - mean) * w0 + (b - mean) * w1
    out = out / np.sqrt(w0 ** 2 + w1 ** 2) + mean
    if is_normal:
        out[..., 2] = np.abs(out[..., 2])
        out = normalize(out)
    return out


def encode_normal(n: np.ndarray) -> np.ndarray:
    return np.clip(np.round((n * 0.5 + 0.5) * 255.0), 0, 255).astype(np.uint8)


def encode01(a: np.ndarray) -> np.ndarray:
    return np.clip(np.round(a * 255.0), 0, 255).astype(np.uint8)


def pct(a, qs, nd=4):
    return [round(float(x), nd) for x in np.percentile(a, qs)]


# ------------------------------------------------------------------------------------------ packing (shared)
def pack_rmh(rough_dev: np.ndarray, cavity: np.ndarray, height: np.ndarray) -> np.ndarray:
    return np.stack([encode01(rough_dev), encode01(cavity), encode01(height)], axis=-1)


def normalise_height(h: np.ndarray) -> tuple[np.ndarray, bool]:
    lo, hi = np.percentile(h, [0.5, 99.5])
    if hi - lo < 1e-3:
        return np.full_like(h, 0.5), True
    return np.clip((h - lo) / (hi - lo), 0.0, 1.0), False


def cavity_from_height(h01: np.ndarray, sigma: float, flat: bool) -> np.ndarray:
    if flat:
        return np.ones_like(h01)
    cav = np.maximum(periodic_gauss(h01, sigma) - h01, 0.0)
    ref = np.percentile(cav, 99.5)
    if ref < 1e-6:
        return np.ones_like(h01)
    return 1.0 - 0.6 * np.clip(cav / ref, 0.0, 1.0)


def rough_deviation(r: np.ndarray, floor: float = ROUGH_AMP_FLOOR) -> tuple[np.ndarray, float, float]:
    med = float(np.median(r))
    lo, hi = np.percentile(r, [0.5, 99.5])
    amp = max(float(hi - med), float(med - lo), floor)
    return np.clip(0.5 + 0.5 * (r - med) / amp, 0.0, 1.0), med, amp


# ------------------------------------------------------------------------------------------- CC0 source tiles
def raw_map(src: str, key: str) -> Path | None:
    hits = sorted(glob.glob(str(RAW / src / f"{src}_2K-JPG_{key}.jpg")))
    return Path(hits[0]) if hits else None


def build_from_source(cls: str, src: str, size: int) -> tuple[np.ndarray, np.ndarray, dict]:
    p_dx, p_gl = raw_map(src, "NormalDX"), raw_map(src, "NormalGL")
    p_r, p_h, p_ao = raw_map(src, "Roughness"), raw_map(src, "Displacement"), raw_map(src, "AmbientOcclusion")
    if not (p_dx and p_gl and p_r and p_h):
        raise FileNotFoundError(f"{src}: NormalDX/NormalGL/Roughness/Displacement missing under {RAW / src}")
    ndx = load01(p_dx)[..., :3]
    ngl = load01(p_gl)[..., :3]
    rough = gray(load01(p_r))
    disp = gray(load01(p_h))
    # --- convention of the source, measured at 2K
    dr, dc = grad_rows_cols(disp)
    conv = {
        "sourceMaps": {"normal": p_dx.name, "normalGL": p_gl.name, "roughness": p_r.name, "height": p_h.name,
                       "ao": p_ao.name if p_ao else None},
        "meanAbs_DX_G_minus_inverted_GL_G": round(float(np.abs(ndx[..., 1] - (1.0 - ngl[..., 1])).mean()), 5),
        "meanAbs_DX_G_minus_GL_G": round(float(np.abs(ndx[..., 1] - ngl[..., 1]).mean()), 5),
        "meanAbs_DX_R_minus_GL_R": round(float(np.abs(ndx[..., 0] - ngl[..., 0]).mean()), 5),
        "corr_DX_G_vs_minus_dHeight_drow": round(corr(ndx[..., 1] - 0.5, -dr), 4),
        "corr_DX_R_vs_minus_dHeight_dcol": round(corr(ndx[..., 0] - 0.5, -dc), 4),
    }
    conv["sourceIsDirectX"] = bool(conv["meanAbs_DX_G_minus_inverted_GL_G"] < 0.01
                                   and conv["meanAbs_DX_R_minus_GL_R"] < 0.01)
    if not conv["sourceIsDirectX"]:
        raise RuntimeError(f"{src}: NormalDX is not the G-inverted NormalGL: {conv}")
    # --- downsample
    n = normalize(box_down(ndx * 2.0 - 1.0, size))
    r = box_down(rough, size)
    h = box_down(disp, size)
    ao = box_down(gray(load01(p_ao)), size) if p_ao else None
    info = {"source": src, "convention": conv,
            "sourceRoughness_p5_p50_p95": pct(rough, [5, 50, 95]),
            "sourceHeightStd": round(float(disp.std()), 4)}
    return pack_source(n, r, h, ao, info, size)


def pack_source(n, r, h, ao, info, size):
    fixes = {}
    before = {"N": seam_ratio(n[..., :2]), "R": seam_ratio(r), "H": seam_ratio(h)}
    if max(max(before["N"]), max(before["R"]), max(before["H"])) > SEAM_FIX_RATIO:
        n = offset_blend(n, True)
        r = offset_blend(r, False)
        h = offset_blend(h, False)
        if ao is not None:
            ao = offset_blend(ao, False)
        fixes = {"offsetBlend": True, "seamBefore": before}
    h01, flat = normalise_height(h)
    rdev, rmed, ramp = rough_deviation(r)
    if ao is not None:
        cavity = np.clip(ao, 0.0, 1.0)
        cav_method = "source AmbientOcclusion map (box-downsampled)"
    else:
        cavity = cavity_from_height(h01, sigma=size / 128.0, flat=flat)
        cav_method = f"height cavity: max(blur(h, sigma={size / 128.0:g}px) - h, 0), 1 - 0.6 * norm(p99.5)"
    info.update({
        "roughnessMedian": round(rmed, 4), "roughnessAmplitude": round(ramp, 4),
        "roughnessEncoding": "R = 0.5 + 0.5 * (r - median) / amplitude (clipped); amplitude = max(p99.5 - med, med - p0.5, 0.04)",
        "heightFlat": flat, "cavityMethod": cav_method,
        "seamFix": fixes or {"offsetBlend": False},
    })
    return n, pack_rmh(rdev, cavity, h01), info


# ------------------------------------------------------------------------------------------ procedural tiles
def proc_satin(size: int, seed: int):
    """5-end warp satin (move 2): 80 warp x 160 weft per tile (both multiples of the repeat 5) -> periodic."""
    rng = np.random.default_rng(seed)
    yy, xx = np.meshgrid(np.arange(size) + 0.5, np.arange(size) + 0.5, indexing="ij")
    n_warp, n_weft = 80, 160
    xw = xx * n_warp / size
    yw = yy * n_weft / size
    i = np.floor(xw).astype(int) % n_warp
    xf = xw - np.floor(xw)
    across = np.sqrt(np.clip(1.0 - (2.0 * xf - 1.0) ** 2, 0.0, 1.0))           # round warp yarn
    bind = (i * 2) % 5
    d = (yw - (bind + 0.5)) % 5.0
    d = np.where(d > 2.5, d - 5.0, d)
    dip = np.exp(-(d / 0.55) ** 2)                                               # warp goes under a weft
    # fibre streaks along the warp (y): noise filtered anisotropically on the torus
    f = np.fft.fftfreq(size)
    fy, fx = f[:, None], f[None, :]
    noise = rng.standard_normal((size, size))
    filt = np.exp(-((fx * size / 60.0) ** 2 + (fy * size / 6.0) ** 2))
    streak = np.real(np.fft.ifft2(np.fft.fft2(noise) * filt))
    streak /= max(streak.std(), 1e-9)
    h = 0.65 * across * (1.0 - 0.8 * dip) + 0.05 * streak
    n = normal_dx_from_height(h * 3.0)
    h01, _ = normalise_height(h)
    cavity = cavity_from_height(h01, sigma=2.0, flat=False)
    rdev = np.clip(0.5 + 0.45 * (dip - 0.5 * (1 - across)) + 0.04 * streak, 0.0, 1.0)  # floats smoother
    info = {"source": "procedural:satin5", "seed": seed,
            "recipe": "5-end satin, move 2, 80 warp x 160 weft per tile; warp floats smooth, binding points rough",
            "heightFlat": False, "cavityMethod": "height cavity (sigma 2 px)",
            "roughnessEncoding": "procedural deviation, amplitude = preset roughness.variation",
            "seamFix": {"offsetBlend": False, "reason": "periodic by construction"}}
    return n, pack_rmh(rdev, cavity, h01), info


def proc_feathers(size: int, seed: int):
    """Contour feathers in offset rows (4 columns x 8 rows per tile), pointing down the image (+V).
    Topmost feather at a texel = the one with the largest t (farthest from its base): shingle order without a global
    ordering, so the torus wrap is consistent. Height rises toward the tip (a feather's tip rests on the next one)."""
    rng = np.random.default_rng(seed)
    cols, rows = 4, 8
    cw, rh = size / cols, size / rows
    length, half_w = 3.0 * rh, 0.52 * cw
    yy, xx = np.meshgrid(np.arange(size) + 0.5, np.arange(size) + 0.5, indexing="ij")
    best_t = np.full((size, size), -1.0)
    height = np.zeros((size, size))
    rach = np.zeros((size, size))
    edge = np.zeros((size, size))
    tan_b = np.tan(np.radians(38.0))
    for r in range(rows):
        for c in range(cols):
            ax = (c + 0.5 * (r % 2)) * cw + rng.uniform(-0.06, 0.06) * cw
            ay = (r + 0.5) * rh + rng.uniform(-0.05, 0.05) * rh   # tips at (r + 3.5) rows: no tip step on the wrap row
            ang = np.radians(rng.uniform(-7.0, 7.0))
            dx = (xx - ax + size / 2) % size - size / 2
            dy = (yy - ay + size / 2) % size - size / 2
            v = dy * np.cos(ang) + dx * np.sin(ang)                 # along the feather (down)
            u = dx * np.cos(ang) - dy * np.sin(ang)                 # across
            t = v / length
            wt = half_w * np.sqrt(np.clip(1.0 - ((t - 0.55) / 0.55) ** 2, 0.0, 1.0)) * (1.0 - 0.35 * np.clip((t - 0.7) / 0.3, 0, 1))
            inside = (t > 0.0) & (t < 1.0) & (np.abs(u) < wt)
            take = inside & (t > best_t)
            if not take.any():
                continue
            un = np.abs(u) / np.maximum(wt, 1e-6)                   # 0 rachis .. 1 vane edge
            barbs = 0.5 + 0.5 * np.cos(2 * np.pi * (v - np.abs(u) * tan_b) / 5.0)
            rachis = np.exp(-(u / 2.4) ** 2) * np.clip((0.95 - t) / 0.1, 0, 1)
            h = 0.9 * t + 0.35 * (1.0 - un ** 2) + 0.25 * rachis + 0.10 * barbs * (1.0 - rachis) * (0.4 + 0.6 * un)
            h = h * (1.0 - 0.35 * np.clip((un - 0.85) / 0.15, 0, 1))  # thin, slightly curled vane edge
            best_t = np.where(take, t, best_t)
            height = np.where(take, h, height)
            rach = np.where(take, rachis, rach)
            edge = np.where(take, un, edge)
    assert (best_t >= 0).all(), "feather lattice leaves holes"
    h_px = height * 6.0
    n = normal_dx_from_height(h_px)
    h01, _ = normalise_height(height)
    cavity = cavity_from_height(h01, sigma=size / 96.0, flat=False)
    rdev = np.clip(0.5 + 0.35 * (edge - 0.5) - 0.35 * rach, 0.0, 1.0)  # rachis glossier, vane edges rougher
    info = {"source": "procedural:feathers", "seed": seed,
            "recipe": "4 x 8 contour feathers per tile, length 3.0 row pitch, ovate tapered tip, barbs 38 deg / 5 px, shingle by max t",
            "heightFlat": False, "cavityMethod": f"height cavity (sigma {size / 96.0:g} px)",
            "roughnessEncoding": "procedural deviation, amplitude = preset roughness.variation",
            "seamFix": {"offsetBlend": False, "reason": "periodic by construction"}}
    return n, pack_rmh(rdev, cavity, h01), info


def proc_skin(size: int, seed: int):
    """Pores (gaussian dimples at random points, FFT convolution on the torus) + fine crossing creases
    (ridged band-pass noise at +-35 deg) + soft undulation."""
    rng = np.random.default_rng(seed)
    f = np.fft.fftfreq(size)
    fy, fx = f[:, None], f[None, :]
    fr = np.sqrt(fx ** 2 + fy ** 2)
    imp = np.zeros((size, size))
    k = 1100
    ys, xs = rng.integers(0, size, k), rng.integers(0, size, k)
    np.add.at(imp, (ys, xs), rng.uniform(0.5, 1.0, k))
    pores = np.real(np.fft.ifft2(np.fft.fft2(imp) * np.exp(-2 * (np.pi * 1.3) ** 2 * fr ** 2)))
    pores /= max(pores.max(), 1e-9)

    def band(theta_deg, f0, bw, aniso):
        th = np.radians(theta_deg)
        a = fx * np.cos(th) + fy * np.sin(th)
        b = -fx * np.sin(th) + fy * np.cos(th)
        filt = np.exp(-((np.abs(a) - f0) / bw) ** 2) * np.exp(-(b / (bw * aniso)) ** 2)
        x = np.real(np.fft.ifft2(np.fft.fft2(rng.standard_normal((size, size))) * filt))
        return x / max(x.std(), 1e-9)

    creases = -np.abs(band(35, 0.035, 0.015, 0.8)) - np.abs(band(-35, 0.035, 0.015, 0.8))
    soft = band(0, 0.0, 0.01, 1.0)
    h = -1.0 * pores + 0.10 * creases + 0.25 * soft
    n = normal_dx_from_height(h * 1.2)
    h01, _ = normalise_height(h)
    cavity = cavity_from_height(h01, sigma=3.0, flat=False)
    rdev = np.clip(0.5 + 0.4 * pores - 0.05 * creases, 0.0, 1.0)     # pores rougher, plateaus slightly oilier
    info = {"source": "procedural:skin", "seed": seed,
            "recipe": "1100 pores (gauss 1.3 px) + weak ridged band-pass creases +-35 deg (f0 0.035 cyc/px) + undulation",
            "heightFlat": False, "cavityMethod": "height cavity (sigma 3 px)",
            "roughnessEncoding": "procedural deviation, amplitude = preset roughness.variation",
            "seamFix": {"offsetBlend": False, "reason": "periodic by construction"}}
    return n, pack_rmh(rdev, cavity, h01), info


PROCEDURAL = {"procedural:satin5": proc_satin, "procedural:feathers": proc_feathers, "procedural:skin": proc_skin}


# --------------------------------------------------------------------------------------------- measurements
def tile_measurements(n_png: np.ndarray, rmh_png: np.ndarray) -> dict:
    n = n_png.astype(np.float64) / 255.0 * 2.0 - 1.0
    rmh = rmh_png.astype(np.float64) / 255.0
    ln = np.linalg.norm(n, axis=-1)
    h = rmh[..., 2]
    dr, dc = grad_rows_cols(periodic_gauss(h, 1.0))
    flat = float(h.std()) < 1e-3
    return {
        "seamRatio": {"N_xy": seam_ratio(n[..., :2]), "R": seam_ratio(rmh[..., 0]), "G": seam_ratio(rmh[..., 1]),
                      "B": seam_ratio(rmh[..., 2])},
        "seamRatioMeanInfo": {"N_xy": seam_ratio_mean(n[..., :2]), "B": seam_ratio_mean(rmh[..., 2])},
        "normalLength_p1_p99": pct(ln, [1, 99]),
        "normalMeanXY": [round(float(n[..., 0].mean()), 4), round(float(n[..., 1].mean()), 4)],
        "normalMinZ": round(float(n[..., 2].min()), 4),
        "heightFlat": flat,
        "corr_N_G_vs_minus_dB_drow": None if flat else round(corr(n[..., 1], -dr), 4),
        "corr_N_R_vs_minus_dB_dcol": None if flat else round(corr(n[..., 0], -dc), 4),
        "R_mean_std": [round(float(rmh[..., 0].mean()), 4), round(float(rmh[..., 0].std()), 4)],
        "G_p1_mean": [round(float(np.percentile(rmh[..., 1], 1)), 4), round(float(rmh[..., 1].mean()), 4)],
        "B_mean_std": [round(float(h.mean()), 4), round(float(h.std()), 4)],
    }


# ---------------------------------------------------------------------------------------------- sources.json
def measure_raw_set(src: str) -> dict:
    out = {}
    p_c, p_r, p_m = raw_map(src, "Color"), raw_map(src, "Roughness"), raw_map(src, "Metalness")
    if p_c:
        c = load01(p_c)
        c = np.repeat(c[..., None], 3, axis=-1) if c.ndim == 2 else c[..., :3]
        cl = lin_from_srgb(c).reshape(-1, 3)
        out["baseColorLinear_p5_p50_p95"] = [[round(float(x), 3) for x in row]
                                              for row in np.percentile(cl, [5, 50, 95], axis=0)]
    if p_r:
        out["roughness_p5_p50_p95"] = pct(gray(load01(p_r)), [5, 50, 95], 3)
    if p_m:
        out["metalnessMean"] = round(float(gray(load01(p_m)).mean()), 3)
    p_dx, p_gl = raw_map(src, "NormalDX"), raw_map(src, "NormalGL")
    if p_dx and p_gl:
        a, b = load01(p_dx)[..., 1], load01(p_gl)[..., 1]
        out["normalDX_G_eq_1_minus_GL_G_meanAbs"] = round(float(np.abs(a - (1.0 - b)).mean()), 5)
        out["normalDetail_meanAbs_xy"] = round(float(np.abs(load01(p_dx)[..., :2] * 2 - 1).mean()), 4)
    return out


def update_sources_measurements():
    data = json.loads(SOURCES_JSON.read_text(encoding="utf-8"))
    for s in data["sets"]:
        if (RAW / s["id"]).is_dir():
            s["measured"] = measure_raw_set(s["id"])
    SOURCES_JSON.write_text(json.dumps(data, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(f"updated measurements in {SOURCES_JSON.relative_to(REPO)}")


# ---------------------------------------------------------------------------------------------------- main
def build() -> dict:
    TILES.mkdir(parents=True, exist_ok=True)
    manifest = json.loads((RAW / "manifest.json").read_text(encoding="utf-8"))
    by_id = {a["id"]: a for a in manifest["assets"]}
    report = {"generator": GENERATOR, "generatorVersion": GENERATOR_VERSION,
              "normalConvention": "DirectX (UE): tangent-space, G = -dh/drow (+V down the image), 8-bit, z stored",
              "rmhLayout": {"R": "roughness deviation, 0.5 = none, 0/1 = -/+ preset roughness.variation",
                            "G": "cavity/AO, 1 = open", "B": "height 0..1 (p0.5..p99.5), wear mask source"},
              "seamFixThreshold": SEAM_FIX_RATIO,
              "seamMetric": "wrap-pair mean |diff| / p99 of interior pair mean |diff|, per axis (x, y)", "classes": []}
    sheet_items = []
    for index, cls, src, size, seed in CLASSES:
        if src.startswith("procedural:"):
            n, rmh, info = PROCEDURAL[src](size, seed)
            src_files = []
        else:
            n, rmh, info = build_from_source(cls, src, size)
            src_files = []
            for key in ("NormalDX", "NormalGL", "Roughness", "Displacement", "AmbientOcclusion"):
                p = raw_map(src, key)
                if p:
                    src_files.append({"file": p.relative_to(REPO).as_posix(), "sha256": sha256_file(p)})
            info["sourceZipSha256"] = by_id[src]["sha256"]
            info["license"] = by_id[src]["license"]
        d = TILES / cls
        d.mkdir(parents=True, exist_ok=True)
        n_png = encode_normal(n)
        pn, pr = d / f"{cls}_DetailN.png", d / f"{cls}_DetailRMH.png"
        Image.fromarray(n_png, "RGB").save(pn, optimize=True)
        Image.fromarray(rmh, "RGB").save(pr, optimize=True)
        meas = tile_measurements(np.asarray(Image.open(pn)), np.asarray(Image.open(pr)))
        report["classes"].append({
            "index": index, "class": cls, "size": size,
            "outputs": [{"map": "DetailN", "path": pn.relative_to(REPO).as_posix(), "sha256": sha256_file(pn),
                         "bytes": pn.stat().st_size},
                        {"map": "DetailRMH", "path": pr.relative_to(REPO).as_posix(), "sha256": sha256_file(pr),
                         "bytes": pr.stat().st_size}],
            "sourceFiles": src_files, "build": info, "measured": meas})
        sheet_items.append((cls, n_png, rmh))
        print(f"{index:2d} {cls:15s} {size:5d} seam N{meas['seamRatio']['N_xy']} B{meas['seamRatio']['B']} "
              f"corrG {meas['corr_N_G_vs_minus_dB_drow']}")
    REPORT.write_text(json.dumps(report, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    write_sheet(sheet_items)
    return report


def write_sheet(items):
    s = 192
    sheet = Image.new("RGB", (s * 4, (s + 16) * len(items) // 2 + 16), (32, 32, 32))
    d = ImageDraw.Draw(sheet)
    for k, (cls, n, rmh) in enumerate(items):
        x0 = (k % 2) * 2 * s
        y0 = (k // 2) * (s + 16)
        for j, img in enumerate((n, rmh)):
            h = img.shape[0] // 2      # half-roll: the wrap seam (if any) shows as a cross in the centre
            im = Image.fromarray(np.roll(np.roll(img, h, 0), h, 1), "RGB")
            sheet.paste(im.resize((s, s), Image.BOX), (x0 + j * s, y0 + 16))
        d.text((x0 + 4, y0 + 2), f"{cls}  N | RMH (half-roll)", fill=(255, 230, 0))
    (OUT / "preview").mkdir(parents=True, exist_ok=True)
    sheet.save(OUT / "preview" / "tiles-sheet.png", optimize=True)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--sources", action="store_true", help="refresh measured stats in sources.json")
    a = ap.parse_args(argv)
    if not RAW.is_dir():
        print(f"raw CC0 sets missing: {RAW}", file=sys.stderr)
        return 2
    build()
    if a.sources:
        update_sources_measurements()
    return 0


if __name__ == "__main__":
    sys.exit(main())
