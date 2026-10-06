"""SX-01 (EN-02 fallback, T-SYNTX-IMG-BANANA): input canvas, registration, membrane seam field, lit variant,
metrics and sheets. Written by Claude (not Codex) for the SX-01 run of 2026-10-07; rules ВР-VS2-EN.6...10.

Run with python -B from the repository root:
  python -B art/imagegen/env-u16-marmoreal-codex/_tools/sx01.py prepare
  python -B art/imagegen/env-u16-marmoreal-codex/_tools/sx01.py build <raw.png> [--tag r1]
  python -B art/imagegen/env-u16-marmoreal-codex/_tools/sx01.py sheets [--tag r1]
  python -B art/imagegen/env-u16-marmoreal-codex/_tools/sx01.py promote --tag r1

Images (they contain the concept painting) go only to scraped-data/derived/env-u16-marmoreal-codex/sx01/.
Metadata without pixels goes to art/imagegen/env-u16-marmoreal-codex/_tools/sx01-*.json.
No provider, git or Unreal calls here.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw
from scipy import ndimage
from scipy.sparse import coo_matrix
from scipy.sparse.linalg import cg

ROOT = Path(__file__).resolve().parents[4]
PKG = ROOT / "art/imagegen/env-u16-marmoreal-codex"
IMG = ROOT / "scraped-data/derived/env-u16-marmoreal-codex"
OUT = IMG / "sx01"
SIZE = (2340, 1317)
BOX = (334, 188, 2006, 1129)  # x0, y0, x1 (excl), y1 (excl): the original 1672x941
ORIGINAL = IMG / "marmoreal-clean.png"
LANTERN = IMG / "marmoreal-lantern-mask.png"
FIELD = IMG / "marmoreal-field-mask.png"
C0 = ROOT / "scraped-data/derived/concepts/env-v1/marmoreal-v1.png"
GREY = (128, 128, 128)
WORKING = [(1521, 856), (1170, 659)]


def rel(p: Path) -> str:
    return p.resolve().relative_to(ROOT).as_posix() if p.resolve().is_relative_to(ROOT) else p.as_posix()


def sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def write_json(p: Path, value) -> None:
    assert p.resolve().is_relative_to(PKG) or p.resolve().is_relative_to(IMG)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def stamp() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def srgb_to_lin(a):
    a = np.asarray(a, dtype=np.float64) / 255
    return np.where(a <= .04045, a / 12.92, ((a + .055) / 1.055) ** 2.4)


def lin_to_srgb(lin):
    s = np.where(lin <= .0031308, 12.92 * lin, 1.055 * np.clip(lin, 0, None) ** (1 / 2.4) - .055)
    return np.clip(np.rint(s * 255), 0, 255).astype("uint8")


def luma(rgb):
    return srgb_to_lin(rgb) @ np.array([.2126, .7152, .0722])


def gray(img: Image.Image) -> Image.Image:
    y = luma(np.asarray(img.convert("RGB")))
    return Image.fromarray(lin_to_srgb(y)).convert("RGB")


def inside_mask():
    yy, xx = np.indices((SIZE[1], SIZE[0]))
    return (xx >= BOX[0]) & (xx < BOX[2]) & (yy >= BOX[1]) & (yy < BOX[3])


# ------------------------------------------------------------------ prepare

def cmd_prepare(_a):
    OUT.mkdir(parents=True, exist_ok=True)
    original = Image.open(ORIGINAL).convert("RGB")
    assert original.size == (1672, 941)
    canvas = Image.new("RGB", SIZE, GREY)
    canvas.paste(original, BOX[:2])
    dest = OUT / "SX01-input-2340x1317.png"
    canvas.save(dest)
    field = np.asarray(Image.open(FIELD).convert("L")) > 0
    o = np.asarray(original)
    info = {
        "card": "EN-02", "package": "SX-01", "created_utc": stamp(),
        "input": rel(dest), "input_sha256": sha(dest), "size": list(SIZE),
        "original_rect_xywh": [BOX[0], BOX[1], 1672, 941],
        "outpaint_band_fill": "#808080 (empty canvas, ВР-VS2-EN.10)",
        "board_field": "#808080 inside the original (EN-01 field mask)",
        "field_is_808080": bool((o[field] == 128).all()),
        "sources": {rel(p): sha(p) for p in (ORIGINAL, LANTERN, FIELD, C0)},
        "generator_inputs": ["SX01-input-2340x1317.png only (our EN-01 clean plate on the canvas); "
                             "C0, the board illustration and DE frames are never uploaded (ВР-PR08)"],
    }
    write_json(PKG / "_tools/sx01-input.json", info)
    print(json.dumps(info, ensure_ascii=False, indent=1))


# ------------------------------------------------------------------ registration

def _resample(raw: Image.Image, sx: float, sy: float, tx: float, ty: float, disp=None) -> np.ndarray:
    """Canvas pixel (x, y) takes raw pixel ((x + dx - tx) / sx, (y + dy - ty) / sy); bicubic, float RGB.
    disp = (dx, dy) arrays of the local warp (None = global scale + translation only)."""
    a = np.asarray(raw.convert("RGB"), dtype=np.float64)
    yy, xx = np.indices((SIZE[1], SIZE[0]), dtype=np.float64)
    if disp is not None:
        xx = xx + disp[0]
        yy = yy + disp[1]
    u = (xx + .5 - tx) / sx - .5
    v = (yy + .5 - ty) / sy - .5
    out = np.empty((SIZE[1], SIZE[0], 3))
    for c in range(3):
        out[..., c] = ndimage.map_coordinates(a[..., c], [v, u], order=3, mode="mirror")
    return out


def register(raw: Image.Image):
    """Fit scale + translation of the raw output onto the canvas by the original area (structure only)."""
    orig = np.asarray(Image.open(ORIGINAL).convert("RGB"), dtype=np.float64)
    field = np.asarray(Image.open(FIELD).convert("L")) > 0
    valid = ~ndimage.binary_dilation(field, iterations=8)
    valid[:16] = valid[-16:] = False
    valid[:, :16] = valid[:, -16:] = False
    yo = orig @ np.array([.299, .587, .114])
    base_sx, base_sy = SIZE[0] / raw.width, SIZE[1] / raw.height

    def score(params):
        dsx, dsy, tx, ty = params
        g = _resample(raw, base_sx * (1 + dsx), base_sy * (1 + dsy), tx, ty)
        yg = g[BOX[1]:BOX[3], BOX[0]:BOX[2]] @ np.array([.299, .587, .114])
        a = yo[valid] - yo[valid].mean()
        b = yg[valid] - yg[valid].mean()
        return float(a @ b / np.sqrt((a @ a) * (b @ b)))

    best = (0.0, 0.0, 0.0, 0.0)
    best_s = score(best)
    trace = [{"params": list(best), "ncc": best_s}]
    for step_t, step_s in ((4.0, .004), (2.0, .002), (1.0, .001), (.5, .0005), (.25, .00025)):
        improved = True
        while improved:
            improved = False
            for i, d in ((0, step_s), (1, step_s), (2, step_t), (3, step_t)):
                for sgn in (-1, 1):
                    cand = list(best)
                    cand[i] += sgn * d
                    s = score(cand)
                    if s > best_s + 1e-6:
                        best, best_s, improved = tuple(cand), s, True
                        trace.append({"params": list(best), "ncc": s})
    dsx, dsy, tx, ty = best
    return {"base_scale": [base_sx, base_sy], "scale": [base_sx * (1 + dsx), base_sy * (1 + dsy)],
            "translate_px": [tx, ty], "ncc_identity": trace[0]["ncc"], "ncc_fit": best_s,
            "method": "bicubic resample; NCC of luma over the original area without the field (+8 px) and a 16 px rim; "
                      "pattern search on scale and translation",
            "steps": len(trace)}


def local_displacement(gen: np.ndarray):
    """Local warp along the old border (ВР-VS2-EN.10 assembly, geometry only): NCC block matching of the globally
    registered generation against the original in 64x48 windows just inside each side, every 32 px, +-4 px with a
    parabolic sub-pixel peak; windows on the field, flat ones (std < 2) or with NCC < 0.6 are dropped. The ring
    displacement is a Gaussian-weighted mean of the samples (sigma 40 px, by Euclidean distance, so corners mix both
    sides); the field is that value at the nearest ring point, fading to 0 over 128 px away from the ring, then
    smoothed (sigma 8 px). Returns (dx, dy, samples): the original at x matches the generation at x + d(x)."""
    x0, y0, x1, y1 = BOX
    yo = np.zeros(SIZE[::-1])
    yo[y0:y1, x0:x1] = np.asarray(Image.open(ORIGINAL).convert("RGB"), dtype=np.float64) @ np.array([.299, .587, .114])
    yg = gen @ np.array([.299, .587, .114])
    field = np.zeros(SIZE[::-1], bool)
    field[y0:y1, x0:x1] = np.asarray(Image.open(FIELD).convert("L")) > 0
    R = 4
    wins = []
    for x in range(x0, x1 - 64 + 1, 32):
        wins.append(("top", x, y0 + 2, 64, 48))
        wins.append(("bottom", x, y1 - 50, 64, 48))
    for y in range(y0, y1 - 64 + 1, 32):
        wins.append(("left", x0 + 2, y, 48, 64))
        wins.append(("right", x1 - 50, y, 48, 64))
    samples = []

    def sub(m, c, p):
        den = m - 2 * c + p
        return 0.0 if abs(den) < 1e-9 else float(np.clip(.5 * (m - p) / den, -.5, .5))

    for side, cx, cy, w, h in wins:
        o = yo[cy:cy + h, cx:cx + w]
        if field[cy:cy + h, cx:cx + w].mean() > .2 or o.std() < 2:
            continue
        a = o - o.mean()
        res = np.full((2 * R + 1, 2 * R + 1), -1.0)
        for dy in range(-R, R + 1):
            for dx in range(-R, R + 1):
                g = yg[cy + dy:cy + dy + h, cx + dx:cx + dx + w]
                b = g - g.mean()
                res[dy + R, dx + R] = (a * b).sum() / np.sqrt((a * a).sum() * (b * b).sum() + 1e-9)
        j, i = np.unravel_index(res.argmax(), res.shape)
        peak = float(res[j, i])
        if peak < .6 or j in (0, 2 * R) or i in (0, 2 * R):
            continue
        dx = i - R + sub(res[j, i - 1], res[j, i], res[j, i + 1])
        dy = j - R + sub(res[j - 1, i], res[j, i], res[j + 1, i])
        samples.append({"side": side, "x": cx + w / 2, "y": cy + h / 2, "dx": round(dx, 3), "dy": round(dy, 3),
                        "ncc": round(peak, 4)})
    inside = inside_mask()
    ring = inside & ~ndimage.binary_erosion(inside, iterations=1)
    ry, rx = np.nonzero(ring)
    sxs = np.array([q["x"] for q in samples])
    sys_ = np.array([q["y"] for q in samples])
    sdx = np.array([q["dx"] for q in samples])
    sdy = np.array([q["dy"] for q in samples])
    ring_dx = np.zeros(len(ry))
    ring_dy = np.zeros(len(ry))
    for k0 in range(0, len(ry), 2048):
        d2 = (rx[k0:k0 + 2048, None] - sxs[None]) ** 2 + (ry[k0:k0 + 2048, None] - sys_[None]) ** 2
        wgt = np.exp(-d2 / (2 * 40.0 ** 2))
        ws = wgt.sum(1)
        ring_dx[k0:k0 + 2048] = np.where(ws > 1e-6, (wgt * sdx).sum(1) / np.maximum(ws, 1e-12), 0)
        ring_dy[k0:k0 + 2048] = np.where(ws > 1e-6, (wgt * sdy).sum(1) / np.maximum(ws, 1e-12), 0)
    rdx = np.zeros(SIZE[::-1])
    rdy = np.zeros(SIZE[::-1])
    rdx[ry, rx] = ring_dx
    rdy[ry, rx] = ring_dy
    dist, (iy, ix) = ndimage.distance_transform_edt(~ring, return_indices=True)
    fade = np.clip(1 - dist / 128.0, 0, 1)
    dxf = ndimage.gaussian_filter(rdx[iy, ix] * fade, 8)
    dyf = ndimage.gaussian_filter(rdy[iy, ix] * fade, 8)
    return dxf, dyf, samples


# ------------------------------------------------------------------ membrane seam field

def membrane(diff_ring: np.ndarray, ring: np.ndarray, domain: np.ndarray) -> np.ndarray:
    """Harmonic field f on `domain` (outside the original): f = diff on `ring` (original's outermost pixels),
    f = 0 on the canvas border, Laplace inside. One 2D solve for all four sides and corners (ВР-VS2-EN.10)."""
    h, w = domain.shape
    idx = -np.ones((h, w), dtype=np.int64)
    ys, xs = np.nonzero(domain)
    idx[ys, xs] = np.arange(len(ys))
    n = len(ys)
    rows, cols, vals = [], [], []
    rhs = np.zeros((n, diff_ring.shape[-1]))
    diag = np.zeros(n)
    for dy, dx in ((-1, 0), (1, 0), (0, -1), (0, 1)):
        ny, nx = ys + dy, xs + dx
        inb = (ny >= 0) & (ny < h) & (nx >= 0) & (nx < w)
        # Canvas border: Dirichlet 0 just outside the canvas.
        diag += 1
        k = np.nonzero(inb)[0]
        nyk, nxk = ny[k], nx[k]
        nb_dom = domain[nyk, nxk]
        nb_ring = ring[nyk, nxk]
        kk = k[nb_dom]
        rows.append(kk)
        cols.append(idx[nyk[nb_dom], nxk[nb_dom]])
        vals.append(-np.ones(len(kk)))
        kr = k[nb_ring & ~nb_dom]
        rhs[kr] += diff_ring[ny[kr], nx[kr]]
    rows.append(np.arange(n))
    cols.append(np.arange(n))
    vals.append(diag)
    A = coo_matrix((np.concatenate(vals), (np.concatenate(rows), np.concatenate(cols))), shape=(n, n)).tocsr()
    # Initial guess: distance-decayed copy of the nearest ring value (fast convergence).
    dist, (iy, ix) = ndimage.distance_transform_edt(~ring, return_indices=True)
    x0 = diff_ring[iy, ix] * np.clip(1 - dist / 160.0, 0, 1)[..., None]
    out = np.zeros((h, w, diff_ring.shape[-1]))
    info = []
    pre = 1.0 / diag
    from scipy.sparse.linalg import LinearOperator
    M = LinearOperator((n, n), matvec=lambda v: pre * v)
    for c in range(diff_ring.shape[-1]):
        sol, flag = cg(A, rhs[:, c], x0=x0[ys, xs, c], rtol=1e-6, maxiter=20000, M=M)
        res = float(np.linalg.norm(A @ sol - rhs[:, c]) / max(np.linalg.norm(rhs[:, c]), 1e-12))
        info.append({"channel": c, "cg_flag": int(flag), "rel_residual": res})
        out[ys, xs, c] = sol
    return out, info


# ------------------------------------------------------------------ metrics

def seam_profile(img: np.ndarray):
    """ВР-VS2-EN.7: linear Rec.709 Y*255, per-side G(d), d = 0 is the pair original | extension."""
    y = luma(img) * 255
    x0, y0, x1, y1 = BOX
    res = {}
    for side in ("left", "right", "top", "bottom"):
        rows = []
        for d in range(-64, 65):
            if side == "left":
                v = np.abs(y[y0:y1, x0 - d] - y[y0:y1, x0 - 1 - d])
            elif side == "right":
                v = np.abs(y[y0:y1, x1 + d] - y[y0:y1, x1 - 1 + d])
            elif side == "top":
                v = np.abs(y[y0 - d, x0:x1] - y[y0 - 1 - d, x0:x1])
            else:
                v = np.abs(y[y1 + d, x0:x1] - y[y1 - 1 + d, x0:x1])
            rows.append(v)
        rows = np.array(rows)
        g = rows.mean(axis=1)
        med = float(np.median(np.r_[g[:64], g[65:]]))
        segs = []
        for s in range(0, rows.shape[1], 64):
            gg = rows[:, s:s + 64].mean(axis=1)
            m = float(np.median(np.r_[gg[:64], gg[65:]]))
            segs.append({"start_px": s, "end_px": min(s + 64, rows.shape[1]), "G0": float(gg[64]), "median": m,
                         "ratio": float(gg[64] / m) if m else None})
        res[side] = {"G0": float(g[64]), "median": med, "ratio": float(g[64] / med) if med else None,
                     "passed": bool(g[64] <= 1.5 * med), "profile_G": [round(float(v), 4) for v in g],
                     "segments_64px": segs,
                     "segments_above_1_5": [s for s in segs if s["ratio"] is None or s["ratio"] > 1.5]}
    return {"definition": "ВР-VS2-EN.7: linear Rec.709 Y*255; mean |dY| across a line parallel to the old border at "
                          "offset d (d<0 original, d=0 original|extension, d>0 extension); pass G(0) <= 1.5 x median "
                          "G(d), 1<=|d|<=64; 64 px segments for inspection only",
            "offsets": list(range(-64, 65)), "sides": res, "passed": all(v["passed"] for v in res.values())}


def artifact_metrics(img: np.ndarray):
    y = luma(img) * 255
    x0, y0, x1, y1 = BOX
    mirror, streak, dark = {}, {}, {}
    for side, width in (("left", 334), ("right", 334), ("top", 188), ("bottom", 188)):
        vals = []
        for wdt in sorted({32, 64, width}):
            if side == "left":
                ext, org = y[y0:y1, x0 - wdt:x0], y[y0:y1, x0:x0 + wdt][:, ::-1]
            elif side == "right":
                ext, org = y[y0:y1, x1:x1 + wdt], y[y0:y1, x1 - wdt:x1][:, ::-1]
            elif side == "top":
                ext, org = y[y0 - wdt:y0, x0:x1], y[y0:y0 + wdt, x0:x1][::-1]
            else:
                ext, org = y[y1:y1 + wdt, x0:x1], y[y1 - wdt:y1, x0:x1][::-1]
            a = ext.ravel() - ext.mean()
            b = org.ravel() - org.mean()
            den = np.linalg.norm(a) * np.linalg.norm(b)
            vals.append({"width_px": wdt, "ncc": float(a @ b / den) if den else 0.0})
        mirror[side] = {"samples": vals, "max": max(v["ncc"] for v in vals),
                        "flag": any(v["ncc"] > .8 for v in vals)}
        gx = float(np.abs(np.diff(ext, axis=1)).mean())
        gy = float(np.abs(np.diff(ext, axis=0)).mean())
        across, along = (gx, gy) if side in ("left", "right") else (gy, gx)
        streak[side] = {"across": across, "along": along, "across_over_along": across / along if along else None,
                        "flag_stretched": bool(along and across / along < .3)}
        if side == "left":
            edge, inner = y[y0:y1, :32], y[y0:y1, x0:x0 + 32]
        elif side == "right":
            edge, inner = y[y0:y1, -32:], y[y0:y1, x1 - 32:x1]
        elif side == "top":
            edge, inner = y[:32, x0:x1], y[y0:y0 + 32, x0:x1]
        else:
            edge, inner = y[-32:, x0:x1], y[y1 - 32:y1, x0:x1]
        dark[side] = {"outer32_mean_Y": float(edge.mean()), "original32_mean_Y": float(inner.mean()),
                      "edge_darker": bool(edge.mean() < inner.mean())}
    return mirror, streak, dark


def water_like(img: np.ndarray):
    """Rough flag: large flat saturated-blue horizontal areas in the lower band (water is forbidden)."""
    a = img.astype(np.float64)
    lower = a[BOX[3]:, :, :]
    r, g, b = lower[..., 0], lower[..., 1], lower[..., 2]
    blue = (b > r + 25) & (b > g + 10) & (b > 90)
    return {"lower_band_blue_fraction": float(blue.mean()),
            "note": "screening number only; the verdict on water is visual (Read PNG)"}


# ------------------------------------------------------------------ build

def build(raw_path: Path, tag: str, darken: list, ring_sigma: float, warp: bool):
    OUT.mkdir(parents=True, exist_ok=True)
    raw = Image.open(raw_path)
    reg = register(raw)
    sx, sy = reg["scale"]
    tx, ty = reg["translate_px"]
    gen = _resample(raw, sx, sy, tx, ty)
    warp_info = {"applied": False}
    if warp:
        ddx, ddy, samples = local_displacement(gen)
        gen = _resample(raw, sx, sy, tx, ty, (ddx, ddy))
        warp_info = {"applied": True, "samples": len(samples),
                     "max_abs_px": [float(np.abs(ddx).max()), float(np.abs(ddy).max())],
                     "mean_abs_px_on_samples": [float(np.mean([abs(q["dx"]) for q in samples])),
                                                float(np.mean([abs(q["dy"]) for q in samples]))],
                     "rule": local_displacement.__doc__.split("Returns")[0].strip(), "sample_points": samples}
    Image.fromarray(np.clip(np.rint(gen), 0, 255).astype("uint8")).save(OUT / f"SX01-{tag}-registered.png")
    orig = np.asarray(Image.open(ORIGINAL).convert("RGB"), dtype=np.float64)
    inside = inside_mask()
    x0, y0, x1, y1 = BOX
    # Registration error at the border band (before paste-back), for the record.
    band = inside & ~ndimage.binary_erosion(inside, iterations=32)
    canvas_orig = np.zeros_like(gen)
    canvas_orig[y0:y1, x0:x1] = orig
    mae_band = float(np.abs(gen - canvas_orig)[band].mean())
    # Seam field: difference original - generation on the original's outermost ring, in linear light,
    # lightly smoothed along the ring (sigma 1.5 px) so single-pixel noise is not imprinted.
    ring = inside & ~ndimage.binary_erosion(inside, iterations=1)
    lin_o = srgb_to_lin(canvas_orig)
    lin_g = srgb_to_lin(np.clip(gen, 0, 255))
    diff = np.zeros_like(lin_g)
    diff[ring] = (lin_o - lin_g)[ring]
    w = ring.astype(np.float64)
    if ring_sigma > 0:
        sm = np.stack([ndimage.gaussian_filter(diff[..., c], ring_sigma) for c in range(3)], -1)
        ws = ndimage.gaussian_filter(w, ring_sigma)
        diff_s = np.where(ring[..., None], sm / np.maximum(ws, 1e-9)[..., None], 0)
    else:
        diff_s = diff
    domain = ~inside
    field, cg_info = membrane(diff_s, ring, domain)
    lin = lin_g + field
    # Edge darkening outside the original only (card: edges darken toward the frame border), linear light,
    # smoothstep from 1.0 at the old border to `darken` at the canvas edge. Low-frequency, ВР-VS2-EN.7.
    # Per side (left, right, top, bottom): factor = product of 1 - (1 - F_side) * smoothstep(t_side), where t_side
    # depends on one coordinate only, so the field is smooth across the corners and 1 at the old border.
    yy, xx = np.indices((SIZE[1], SIZE[0]))
    ts = {"left": np.clip((x0 - xx) / x0, 0, 1), "right": np.clip((xx - (x1 - 1)) / (SIZE[0] - x1), 0, 1),
          "top": np.clip((y0 - yy) / y0, 0, 1), "bottom": np.clip((yy - (y1 - 1)) / (SIZE[1] - y1), 0, 1)}
    factor = np.ones(SIZE[::-1])
    for (side, t), f_side in zip(ts.items(), darken):
        factor *= 1 - (1 - f_side) * t * t * (3 - 2 * t)
    lin = lin * factor[..., None]
    clean = lin_to_srgb(np.clip(lin, 0, 1))
    clean[y0:y1, x0:x1] = np.asarray(Image.open(ORIGINAL).convert("RGB"))  # byte-exact paste-back
    clean_img = Image.fromarray(clean)
    clean_path = OUT / f"marmoreal-clean-ext-{tag}.png"
    clean_img.save(clean_path)
    # Lit variant (ВР-VS2-EN.8): lit = clean_ext*(1-m) + C0*m inside the original rect; no second feather.
    m = np.asarray(Image.open(LANTERN).convert("L"), dtype=np.float64) / 255
    c0 = np.asarray(Image.open(C0).convert("RGB"), dtype=np.float64)
    lit = clean.copy()
    crop = clean[y0:y1, x0:x1].astype(np.float64)
    lit[y0:y1, x0:x1] = np.clip(np.rint(crop * (1 - m[..., None]) + c0 * m[..., None]), 0, 255).astype("uint8")
    lit_path = OUT / f"marmoreal-lit-ext-{tag}.png"
    Image.fromarray(lit).save(lit_path)
    # Proofs.
    raw_crop = clean[y0:y1, x0:x1]
    en01 = np.asarray(Image.open(ORIGINAL).convert("RGB"))
    field = np.asarray(Image.open(FIELD).convert("L")) > 0
    changed = np.any(lit != clean, axis=-1)
    mask_canvas = np.zeros(SIZE[::-1], bool)
    mask_canvas[y0:y1, x0:x1] = m > 0
    core = np.zeros(SIZE[::-1], bool)
    core[y0:y1, x0:x1] = m >= 1
    c0_canvas = np.zeros_like(clean)
    c0_canvas[y0:y1, x0:x1] = c0.astype("uint8")
    # Uncorrected composite (generation + paste-back only) for the record of what the field fixed.
    plain = np.clip(np.rint(gen), 0, 255).astype("uint8")
    plain[y0:y1, x0:x1] = en01
    seam_plain = seam_profile(plain)
    seam_final = seam_profile(clean)
    mirror, streak, dark = artifact_metrics(clean)
    proof = {
        "tag": tag, "created_utc": stamp(), "raw": raw_path.as_posix(), "raw_sha256": sha(raw_path),
        "raw_size": list(raw.size), "registration": reg, "registration_MAE_RGB_32px_inside_border": mae_band,
        "seam_field": {"rule": "ВР-VS2-EN.10: one smooth 2D field over the whole outside (membrane / Laplace), "
                               "Dirichlet = (original - generation) in linear light on the original's outermost "
                               "ring (gaussian ring_sigma_px along the ring; 0 = exact), 0 at the canvas edge; decay outward "
                               f"{y0} px top/bottom, {x0} px left/right (>= 96)",
                       "cg": cg_info,
                       "max_abs_linear_at_ring": float(np.abs(diff_s[ring]).max()),
                       "mean_abs_linear_at_ring": float(np.abs(diff_s[ring]).mean())},
        "edge_darkening": {"outer_factor_linear_LRTB": darken, "curve": "per side smoothstep of the normalised "
                           "distance from the old border line to the canvas edge, product over sides; outside the "
                           "original only; linear light"},
        "ring_sigma_px": ring_sigma, "local_warp": warp_info,
        "size": list(clean_img.size),
        "original_crop_sha256_rgb": hashlib.sha256(raw_crop.tobytes()).hexdigest(),
        "en01_sha256_rgb": hashlib.sha256(en01.tobytes()).hexdigest(),
        "original_byte_identical": bool((raw_crop == en01).all()),
        "field_808080_clean": bool((raw_crop[field] == 128).all()),
        "field_808080_lit": bool((lit[y0:y1, x0:x1][field] == 128).all()),
        "lit_changes_only_inside_mask": bool(not (changed & ~mask_canvas).any()),
        "lit_changed_px": int(changed.sum()),
        "lit_core_equals_C0": bool((lit[core] == c0_canvas[core]).all()),
        "seam_before_field": {k: {j: v[j] for j in ("G0", "median", "ratio", "passed")}
                              for k, v in seam_plain["sides"].items()},
        "seam": seam_final, "mirror": mirror, "streak": streak, "edge_darkness": dark,
        "water_screen": water_like(clean),
        "outputs": {rel(clean_path): sha(clean_path), rel(lit_path): sha(lit_path)},
    }
    write_json(PKG / f"_tools/sx01-{tag}-proof.json", proof)
    summary = {k: {j: round(v[j], 3) if isinstance(v[j], float) else v[j] for j in ("G0", "median", "ratio", "passed")}
               for k, v in seam_final["sides"].items()}
    print(json.dumps({"tag": tag, "registration": {k: reg[k] for k in ("scale", "translate_px", "ncc_identity", "ncc_fit")},
                      "mae_band": mae_band, "seam_before": proof["seam_before_field"], "seam": summary,
                      "byte_identical": proof["original_byte_identical"],
                      "lit_only_mask": proof["lit_changes_only_inside_mask"], "core_C0": proof["lit_core_equals_C0"],
                      "mirror_max": {k: round(v["max"], 3) for k, v in mirror.items()},
                      "streak": {k: round(v["across_over_along"], 3) for k, v in streak.items()},
                      "dark": {k: v["edge_darker"] for k, v in dark.items()}, "cg": cg_info},
                     ensure_ascii=False, indent=1))


def cmd_build(a):
    build(Path(a.raw), a.tag, [float(v) for v in a.darken.split(',')], a.ring_sigma, not a.no_warp)


# ------------------------------------------------------------------ sheets

def label(img: Image.Image, text: str) -> Image.Image:
    out = Image.new("RGB", (img.width, img.height + 30), "#202020")
    out.paste(img, (0, 30))
    ImageDraw.Draw(out).text((10, 9), text, fill="white")
    return out


def save_pair(name: str, img: Image.Image):
    d = OUT / "comparison"
    d.mkdir(parents=True, exist_ok=True)
    img.save(d / f"{name}-colour.png")
    gray(img).save(d / f"{name}-gray.png")
    return [rel(d / f"{name}-colour.png"), rel(d / f"{name}-gray.png")]


def cmd_sheets(a):
    tag = a.tag
    clean = Image.open(OUT / f"marmoreal-clean-ext-{tag}.png").convert("RGB")
    lit = Image.open(OUT / f"marmoreal-lit-ext-{tag}.png").convert("RGB")
    proof = json.loads((PKG / f"_tools/sx01-{tag}-proof.json").read_text(encoding="utf-8"))
    sheets = {}
    x0, y0, x1, y1 = BOX
    # K1 x0.65 framing = whole rect B (whole canvas) downscaled to 1672x941 (ВР-VS2-EN.6), original outlined.
    for nm, im in (("clean", clean), ("lit", lit)):
        k1 = im.resize((1672, 941), Image.Resampling.LANCZOS)
        k1o = k1.copy()
        s = 1672 / SIZE[0]
        ImageDraw.Draw(k1o).rectangle((x0 * s - 1, y0 * s - 1, x1 * s, y1 * s), outline=(255, 255, 255), width=1)
        sheets[f"K1x065-{nm}"] = save_pair(f"sx01-{tag}-K1x065-{nm}", label(k1, f"SX-01 {tag} {nm}-ext: rect B (2340x1317) -> 1672x941 (K1 x0.65 framing, ВР-VS2-EN.6)"))
        sheets[f"K1x065-{nm}-outlined"] = save_pair(f"sx01-{tag}-K1x065-{nm}-outlined", label(k1o, f"SX-01 {tag} {nm}-ext with the original outlined"))
    for wsz in WORKING:
        sheets[f"working-{wsz[0]}"] = save_pair(f"sx01-{tag}-working-{wsz[0]}x{wsz[1]}",
                                                label(clean.resize(wsz, Image.Resampling.LANCZOS), f"SX-01 {tag} clean-ext at {wsz[0]}x{wsz[1]}"))
    # Edges at 2x nearest: four strips centred on the old border, with corners included.
    strips = {
        "left": (0, 0, x0 + 160, SIZE[1]), "right": (x1 - 160, 0, SIZE[0], SIZE[1]),
        "top": (0, 0, SIZE[0], y0 + 120), "bottom": (0, y1 - 120, SIZE[0], SIZE[1]),
    }
    for side, box in strips.items():
        crop = clean.crop(box)
        # Split long strips into two halves so 2x nearest stays readable.
        if side in ("top", "bottom"):
            parts = [crop.crop((0, 0, crop.width // 2, crop.height)), crop.crop((crop.width // 2, 0, crop.width, crop.height))]
        else:
            parts = [crop.crop((0, 0, crop.width, crop.height // 2)), crop.crop((0, crop.height // 2, crop.width, crop.height))]
        for i, p in enumerate(parts):
            p2 = p.resize((p.width * 2, p.height * 2), Image.Resampling.NEAREST)
            sheets[f"edge-{side}-{i+1}"] = save_pair(f"sx01-{tag}-edge-{side}-{i+1}-2x", label(p2, f"SX-01 {tag} edge {side} part {i+1}/2, 2x nearest, crop {box}"))
    # Gradient magnitude map and G(d) profiles.
    y = luma(np.asarray(clean)) * 255
    gx = ndimage.sobel(y, axis=1)
    gy = ndimage.sobel(y, axis=0)
    mag = np.hypot(gx, gy)
    vis = np.clip(mag / np.percentile(mag, 99) * 255, 0, 255).astype("uint8")
    gimg = Image.fromarray(vis).convert("RGB")
    ImageDraw.Draw(gimg).rectangle((x0 - 1, y0 - 1, x1, y1), outline=(255, 64, 64), width=1)
    gimg = gimg.resize((1672, 941), Image.Resampling.LANCZOS)
    plot = Image.new("RGB", (1672, 360), "#181818")
    dr = ImageDraw.Draw(plot)
    cols = {"left": (120, 200, 255), "right": (255, 200, 120), "top": (160, 255, 160), "bottom": (255, 140, 200)}
    sides = proof["seam"]["sides"]
    gmax = max(max(v["profile_G"]) for v in sides.values())
    for i, (side, v) in enumerate(sides.items()):
        ox = 20 + i * 412
        dr.rectangle((ox, 30, ox + 392, 330), outline=(90, 90, 90))
        pts = [(ox + (j / 128) * 392, 330 - v["profile_G"][j] / gmax * 290) for j in range(129)]
        dr.line(pts, fill=cols[side], width=2)
        dr.line([(ox + 196, 30), (ox + 196, 330)], fill=(200, 60, 60))
        dr.text((ox + 4, 8), f"{side}: G0 {v['G0']:.2f} / med {v['median']:.2f} = {v['ratio']:.2f} ({'PASS' if v['passed'] else 'FAIL'} <=1.5)", fill="white")
    grad = Image.new("RGB", (1672, 941 + 360), "#181818")
    grad.paste(gimg, (0, 0))
    grad.paste(plot, (0, 941))
    sheets["gradient"] = save_pair(f"sx01-{tag}-gradient", label(grad, f"SX-01 {tag}: Sobel |grad Y| (old border red) and G(d), d=-64..64 (red line d=0)"))
    # Lit diff.
    diff = np.any(np.asarray(lit) != np.asarray(clean), axis=-1)
    dimg = Image.fromarray(np.where(diff, 255, 0).astype("uint8")).convert("RGB").resize((1672, 941), Image.Resampling.NEAREST)
    sheets["lit-diff"] = save_pair(f"sx01-{tag}-lit-diff", label(dimg, f"SX-01 {tag}: pixels where lit-ext != clean-ext (white)"))
    # Corners at 2x nearest (where per-side corrections failed before).
    for nm, (cx, cy) in {"tl": (x0, y0), "tr": (x1, y0), "bl": (x0, y1), "br": (x1, y1)}.items():
        box = (max(cx - 200, 0), max(cy - 150, 0), min(cx + 200, SIZE[0]), min(cy + 150, SIZE[1]))
        p = clean.crop(box)
        sheets[f"corner-{nm}"] = save_pair(f"sx01-{tag}-corner-{nm}-2x", label(p.resize((p.width * 2, p.height * 2), Image.Resampling.NEAREST), f"SX-01 {tag} corner {nm}, 2x nearest, crop {box}"))
    write_json(PKG / f"_tools/sx01-{tag}-sheets.json", sheets)
    print(json.dumps(sheets, ensure_ascii=False, indent=1))


def cmd_promote(a):
    """Accepted result -> canonical names; rejected CX-17 candidates are moved (not deleted) to history."""
    hist = IMG / "history/cx17-rejected"
    hist.mkdir(parents=True, exist_ok=True)
    moved = {}
    for nm in ("marmoreal-clean-ext.png", "marmoreal-lit-ext.png"):
        src = IMG / nm
        if src.exists():
            dst = hist / nm
            assert not dst.exists()
            h = sha(src)
            shutil.move(src, dst)
            assert sha(dst) == h
            moved[rel(src)] = {"to": rel(dst), "sha256": h}
    out = {}
    for nm in ("clean", "lit"):
        src = OUT / f"marmoreal-{nm}-ext-{a.tag}.png"
        dst = IMG / f"marmoreal-{nm}-ext.png"
        shutil.copyfile(src, dst)
        assert sha(src) == sha(dst)
        out[rel(dst)] = {"from": rel(src), "sha256": sha(dst)}
    rec = {"created_utc": stamp(), "tag": a.tag, "moved_rejected_cx17": moved, "promoted": out}
    write_json(PKG / "_tools/sx01-promote.json", rec)
    print(json.dumps(rec, ensure_ascii=False, indent=1))


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("prepare")
    b = sub.add_parser("build")
    b.add_argument("raw")
    b.add_argument("--tag", default="r1")
    b.add_argument("--darken", default="1,1,1,1", help="outer linear factor per side: left,right,top,bottom")
    b.add_argument("--ring-sigma", type=float, default=0.0)
    b.add_argument("--no-warp", action="store_true")
    s = sub.add_parser("sheets")
    s.add_argument("--tag", default="r1")
    p = sub.add_parser("promote")
    p.add_argument("--tag", required=True)
    a = ap.parse_args()
    {"prepare": cmd_prepare, "build": cmd_build, "sheets": cmd_sheets, "promote": cmd_promote}[a.cmd](a)


if __name__ == "__main__":
    main()
