#!/usr/bin/env python3
"""EN-05 (docs/game-design/visual/06-tasks/env.csv): the environment gates G1/G2/G4-G7, the P10 criteria and the
acceptance sheet in git, so a measurement repeats on any checkout (ВР-EN.7 by delegation: the gates move into git
before any P3 / P7 measurement; C:/tmp is history only).

The logic is moved WITHOUT changes (thresholds, ROIs, formulas, rounding) from the scratch scripts below. What changed
is plumbing only: concept pixels come as arguments (--concept; concept frames are never in git, ENV-U3), the trace is
bench.trace.log or bench.trace.txt (the git evidence keeps .txt because *.log is ignored), the map key of G5 is an
argument (default: from the trace, as measure.py frames did), G7 writes its diff images only with --g7-diff-out, and G6
takes an optional exclusion polygon per lantern (ВР-EN.10: lantern-deck-se - the crate face under it).

Sources (sha256 of the files as moved, 2026-10-06; the p10/tools/mtools copies differ from the originals only in
sys.path / REPO / DERIVED lines):
  C:/tmp/envmaps-research/p9/tune/gates.py           0c110de93c9634fe5d8997a8a9554bc32abd4325acf1e2b76068f2efb56791d4
  C:/tmp/envmaps-research/p9/tune/g7.py              4aa3a0f9229d492a7f161758514aaf6ea453e274c46a03e9211d80a10ed1f5e8
  C:/tmp/envmaps-research/p9/tune/fixes.py           fb089ad21ca7f998613c73632b7636fc8e51891b061eb025b3ce734598eea3ee (F1)
  C:/tmp/envmaps-research/p5c/tune/measure.py        cfdfb5b63cd1901a6dadd0e074bb2ed5db5a67aee6c86d8ad73c09536a107107
  C:/tmp/envmaps-research/p7/tune/cmp_concept.py     93e5d644f73c705833f1a718d9db42de94010ad0d44ec714b774c2a704281b4a
  C:/tmp/envmaps-research/p5c/tune/zone_precise.py   086affe4c31b02c5e6360cfae7b5fddec91ee310500d65e8bed0fbafdc6a1922
  C:/tmp/envmaps-research/p10/tools/crit.py          b1d3001abd6428c21c840db981f4773b0ea2fe75a260119fd8fbe2baac082419
  C:/tmp/envmaps-research/p10/tools/edgerun.py       ccab29c2eeb151a789369667fab1051b4f95bb5739b3bbe30cce7df74cb2ce41
  C:/tmp/envmaps-research/p10/tools/ssimship.py      b8a60c1a29c378b710acc18ee9d7189926af9adecd3d9476ba7f90a1e966859f
  C:/tmp/envmaps-research/p10/tools/cannons.py       d1b7a1fdf9d45c1b7a89d268e870b5bf45b2f003c92eb40a33ef936faee36d40
  C:/tmp/envmaps-research/p10/tools/patch.py         69df5349c88ab3ddd936c8f7cef367ecc0b21b810c06a841039ea79917556e04
  concept used by P10: C:/tmp/envmaps-research/p7/proto/sarpedon/concept-registered-H.png
                                                     ddf38968117f7e03dbdae8621576f69640f675308dcd158331c3c20c2308834f
A run directory holds bench-<view>-1920x1080.png frames and the bench trace (lines 'SHOT ctx ... cam=(x,y,z)
rot=(p,y,r)' + 'SHOT captured file=<png>'). Views: K1, K1x1p6, K2x1p6, Fitx1p45 (= C0, the concept pose), live pairs
Fitx1p450 / K1x1p0 (G7).

Subcommands
  gates <run> [--concept PNG] [--off <run>] [--map KEY] [--g6-exclude NAME=x,y;x,y;...] [--g7-diff-out DIR]
      G1 (with --off) lights off / on surround luma < 0.12; G2 frame-foot and Medusa shadow profiles; G4 C0 vs the
      registered concept: SSIM of luma at 1/4 in the surround >= 0.55, median dE76 of 7 patches <= 6; G5 per view map Y,
      surround Y, warm share, circle-edge dL* (measure.py) + K1 minimum adjacent-zone dE76 (zone_separation, unrounded);
      G6 lantern glow area game / painted (>= 0.8) and banner rows; G7 live pairs (pixels changed > 8 levels per ROI,
      brazier light std over the K1 series).
  crit <run> --concept PNG [--gates]   the P10 criteria (crit.py): K1 straight edge <= 100 px, C0 falls body dE76 <= 6
      and dL* <= 4, fort dE76 <= 7, F1 SSIM of the ship polygon >= 0.45, hull-red dE76 <= 6, cannons dL*, hull wall
      pixels >= 245; --gates adds G4 / G5 (K1) / G6.
  edge <png> [--roi x0,y0,x1,y1] [--d 1] [--thr 35] [--resize]    longest straight horizontal edge (edgerun.py).
  ssim-ship <png_a> <png_b> --concept PNG    F1 SSIM of the ship polygon per 100x100 px cell, a vs b (ssimship.py).
  cannons <png>...                           barrel L* vs the hull 40 px below (cannons.py).
  streams <png> [--roi x0,y0,x1,y1] [--hi 1.4] [--lo 0.8] [--min-width 10]   NEW: light vertical streams (default ROI:
                                             the Sarpedon C0 cascade 640,885,1000,1040; N_concept = 3).
  fire <png> [--roi x0,y0,x1,y1 ...]         NEW: flame shape (height, h/w, tongues, red share); default ROIs: the
                                             g7.py fire-fort / fire-brazier world boxes projected with the frame's camera.
  sheet <png>... --out <png> [--crop x0,y0,x1,y1] [--label TEXT]   NEW: colour / grey Rec.709 / deuteranopia montage.
  --check                                    self-test on synthetic frames (< 10 s, no frames, no UE, no GPU).
Every subcommand prints JSON; --json <file> writes it too.

New measurements (EN-05 "do" 3, defined here):
  streams  Y = Rec.709 luma of the sRGB values. col[x] = mean Y of column x over the ROI rows; m = median Y of all ROI
           pixels. A bright run = consecutive columns with col >= hi*m (1.4). Two bright runs are one stream unless a
           column between them has col <= lo*m (0.8: a real dark gap between streams). A stream counts when its span
           (first to last bright column) is >= min-width px (10). Output: N, per stream x0 / x1 / width / peak col / m.
  fire     HSV of the sRGB values. Flame mask F = V >= 0.85 and hue 10..45 deg in the ROI; the largest 8-connected
           component is the flame. height = its row span, width = its column span, h/w; tongues = local maxima of its
           top edge (per column the topmost flame row, as a height profile median-filtered over 3 px) whose prominence
           over the lower neighbouring minimum on each side is >= max(2 px, 0.1 x height); red share = of the bright warm
           pixels in the flame's bounding box (V >= 0.85, hue < 45 or >= 345) the share with hue < 15 or >= 345.
  sheet    per input: colour | grey (Y' = 0.2126 R' + 0.7152 G' + 0.0722 B' on the sRGB values) | deuteranopia
           (Machado, Oliveira, Fernandes 2009, severity 1.0, linear RGB) - the transforms of tools/art/visual/sheet.py.
Concept-derived results (crit, G4, G6, streams on the concept) and sheets of the concept stay OUT of git (ENV-U3).

  python tools/art/render/env_gates.py gates <run> --concept C:/tmp/.../concept-registered-H.png --json out.json
  python tools/art/render/env_gates.py --check
Status: «измерено» numbers only; acceptance is decided elsewhere.
"""
from __future__ import annotations

import argparse
import contextlib
import json
import math
import re
import sys
import time
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont
from scipy import ndimage

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
MAP_SURFACE = REPO / "tools" / "art" / "map_surface"
SCENE_PARAMS = REPO / "tools" / "art" / "concept_scene" / "scene-params.sarpedon.json"
W709 = np.array([0.2126, 0.7152, 0.0722])

# ============================================================================ measure.py (P5c, unchanged logic)
MAP_HALF = (445.6667, 288.6667)
FRAME_HALF = (469.67, 312.67)
TRAY_TOP = (-780.0, -515.0, 780.0, 425.0)
TRAY_BOX = (-802.0, -530.4, -179.5, 802.0, 440.4, 260.0)  # z up to the tallest props (~250) for the bg exclusion
SRC = (1337, 866)
UU_PER_PX = 2.0 / 3.0
HUD_RECTS = [(1880, 0, 1920, 30), (940, 1055, 980, 1080)]  # the two small dark HUD squares (top-right, bottom-centre)


def srgb_to_lin(c):
    c = np.asarray(c, np.float64) / 255.0
    return np.where(c <= 0.04045, c / 12.92, ((c + 0.055) / 1.055) ** 2.4)


def lab(rgb8: np.ndarray) -> np.ndarray:
    lin = srgb_to_lin(rgb8)
    m = np.array([[0.4124, 0.3576, 0.1805], [0.2126, 0.7152, 0.0722], [0.0193, 0.1192, 0.9505]])
    xyz = lin @ m.T
    xyz /= np.array([0.95047, 1.0, 1.08883])
    f = np.where(xyz > 216 / 24389, np.cbrt(xyz), (24389 / 27 * xyz + 16) / 116)
    L = 116 * f[..., 1] - 16
    a = 500 * (f[..., 0] - f[..., 1])
    b = 200 * (f[..., 1] - f[..., 2])
    return np.stack([L, a, b], -1)


def luma8(rgb8: np.ndarray) -> np.ndarray:
    return rgb8[..., 0] * 0.2126 + rgb8[..., 1] * 0.7152 + rgb8[..., 2] * 0.0722


def stats(rgb8: np.ndarray, mask: np.ndarray) -> dict:
    px = rgb8[mask].astype(np.float64)
    if px.size == 0:
        return {"n": 0}
    y = luma8(px)
    lb = lab(px)
    hue = (np.degrees(np.arctan2(lb[:, 2], lb[:, 1])) + 360) % 360
    chroma = np.hypot(lb[:, 1], lb[:, 2])
    warm = (hue > 20) & (hue < 100) & (chroma > 18) & (lb[:, 0] > 30)
    cool = lb[:, 2] < -6
    return {"n": int(px.shape[0]), "lumaMean": round(float(y.mean()), 1), "lumaP50": round(float(np.median(y)), 1),
            "lumaP10": round(float(np.percentile(y, 10)), 1), "lumaP90": round(float(np.percentile(y, 90)), 1),
            "L": round(float(lb[:, 0].mean()), 1), "a": round(float(lb[:, 1].mean()), 1),
            "b": round(float(lb[:, 2].mean()), 1), "rgbMean": [round(float(v), 1) for v in px.mean(0)],
            "warmFrac": round(float(warm.mean()), 3), "coolFrac": round(float(cool.mean()), 3),
            "chromaMean": round(float(chroma.mean()), 1)}


class Cam:
    """S08 pinhole: position / rotation of the 'SHOT ctx' line, horizontal FOV 35 deg, 16:9 (measure.py and
    cmp_concept.py carry the same class)."""

    def __init__(self, pos, pitch, yaw, w=1920, h=1080, hfov=35.0):
        p, y = math.radians(pitch), math.radians(yaw)
        self.pos = np.array(pos, float)
        self.fwd = np.array([math.cos(p) * math.cos(y), math.cos(p) * math.sin(y), math.sin(p)])
        self.right = np.array([-math.sin(y), math.cos(y), 0.0])
        self.up = np.array([-math.sin(p) * math.cos(y), -math.sin(p) * math.sin(y), math.cos(p)])
        self.tan_h = math.tan(math.radians(hfov / 2))
        self.tan_v = self.tan_h / (w / h)
        self.w, self.h = w, h

    def project(self, P):
        v = np.asarray(P, float) - self.pos
        z = v @ self.fwd
        sx = (v @ self.right) / z / self.tan_h
        sy = (v @ self.up) / z / self.tan_v
        return np.c_[(sx + 1) / 2 * self.w, (1 - sy) / 2 * self.h]


def rect_poly(cam, x0, y0, x1, y1, z=0.0):
    return [tuple(p) for p in cam.project([[x0, y0, z], [x1, y0, z], [x1, y1, z], [x0, y1, z]])]


def ms_poly_mask(size, poly):
    """measure.py poly_mask(size, poly)."""
    im = Image.new("L", size, 0)
    ImageDraw.Draw(im).polygon(poly, fill=255)
    return np.asarray(im) > 0


def hull(points):
    pts = sorted(map(tuple, points))
    if len(pts) <= 2:
        return pts

    def cross(o, a, b):
        return (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0])
    lower, upper = [], []
    for p in pts:
        while len(lower) >= 2 and cross(lower[-2], lower[-1], p) <= 0:
            lower.pop()
        lower.append(p)
    for p in reversed(pts):
        while len(upper) >= 2 and cross(upper[-2], upper[-1], p) <= 0:
            upper.pop()
        upper.append(p)
    return lower[:-1] + upper[:-1]


def parse_shots(trace: Path):
    shots_, ctx = {}, None
    for line in trace.read_text(encoding="utf-8", errors="replace").splitlines():
        m = re.search(r"SHOT ctx .*cam=\(([-\d.]+),([-\d.]+),([-\d.]+)\) rot=\(([-\d.]+),([-\d.]+),([-\d.]+)\)", line)
        if m:
            v = [float(x) for x in m.groups()]
            ctx = (v[:3], v[3], v[4])
            continue
        m = re.search(r"SHOT captured file=(\S+)", line)
        if m and ctx:
            shots_[m.group(1)] = ctx
            ctx = None
    return shots_


def load_spaces(map_key):
    topo = json.loads((REPO / f"backend/prisma/fixtures/boards/{map_key}.topology.json").read_text(encoding="utf-8"))
    r_uu = topo["spaceRadiusPx"] * topo["uuPerPx"]
    out = []
    for s in topo["spaces"]:
        x = (s["layout"]["x"] / SRC[0] - 0.5) * MAP_HALF[0] * 2
        y = (s["layout"]["y"] / SRC[1] - 0.5) * MAP_HALF[1] * 2
        out.append((s["id"], x, y))
    return out, r_uu


def bilinear(img, xy):
    h, w = img.shape[:2]
    x = np.clip(xy[:, 0] - 0.5, 0, w - 1.001)
    y = np.clip(xy[:, 1] - 0.5, 0, h - 1.001)
    x0, y0 = np.floor(x).astype(int), np.floor(y).astype(int)
    fx, fy = (x - x0)[:, None], (y - y0)[:, None]
    a, b = img[y0, x0], img[y0, x0 + 1]
    c, d = img[y0 + 1, x0], img[y0 + 1, x0 + 1]
    return (a * (1 - fx) + b * fx) * (1 - fy) + (c * (1 - fx) + d * fx) * fy


def circle_metrics(img, cam, spaces, r_uu, n_ang=48):
    ang = np.linspace(0, 2 * np.pi, n_ang, endpoint=False)
    rows = []
    for sid, cx, cy in spaces:
        c = cam.project([[cx, cy, 0.0]])[0]
        if not (20 < c[0] < img.shape[1] - 20 and 20 < c[1] < img.shape[0] - 20):
            continue

        def ring(fracs):
            pts = np.array([[cx + f * r_uu * math.cos(a), cy + f * r_uu * math.sin(a), 0.0] for f in fracs for a in ang])
            xy = cam.project(pts)
            inside = (xy[:, 0] > 1) & (xy[:, 0] < img.shape[1] - 2) & (xy[:, 1] > 1) & (xy[:, 1] < img.shape[0] - 2)
            vals = lab(bilinear(img, xy))
            vals[~inside] = np.nan
            return vals.reshape(len(fracs), n_ang, 3)
        fill = ring([0.45, 0.55, 0.65, 0.75])
        line = ring([0.94, 0.97, 1.0, 1.03, 1.06])
        out = ring([1.2, 1.3, 1.4])
        with np.errstate(all="ignore"), _quiet_nan():
            fill_L = np.nanmedian(fill[..., 0])
            line_L = np.nanmedian(np.nanmin(line[..., 0], axis=0))
            out_L = np.nanmedian(out[..., 0])
            fill_C = np.nanmedian(np.hypot(fill[..., 1], fill[..., 2]))
        rows.append((sid, fill_L, line_L, out_L, fill_C))
    if not rows:
        return {"n": 0}
    a = np.array([r[1:] for r in rows], float)
    edge = a[:, 0] - a[:, 1]
    surr = np.abs(a[:, 0] - a[:, 2])
    return {"n": len(rows), "fillL50": round(float(np.median(a[:, 0])), 1),
            "lineL50": round(float(np.median(a[:, 1])), 1), "outsideL50": round(float(np.median(a[:, 2])), 1),
            "edgeDeltaL50": round(float(np.median(edge)), 1), "edgeDeltaLp10": round(float(np.percentile(edge, 10)), 1),
            "fillVsOutsideDeltaL50": round(float(np.median(surr)), 1),
            "fillVsOutsideDeltaLp10": round(float(np.percentile(surr, 10)), 1),
            "fillChroma50": round(float(np.median(a[:, 3])), 1),
            "worstEdge": sorted(((round(float(e), 1), r[0]) for e, r in zip(edge, rows)))[:3]}


@contextlib.contextmanager
def _quiet_nan():
    import warnings
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", category=RuntimeWarning)
        yield


def measure_frame(png: Path, ctx, map_key: str) -> dict:
    img = np.asarray(Image.open(png).convert("RGB")).astype(np.float64)
    H, W = img.shape[:2]
    cam = Cam(ctx[0], ctx[1], ctx[2], W, H)
    size = (W, H)
    hx, hy = MAP_HALF
    m_map = ms_poly_mask(size, rect_poly(cam, -hx + 8, -hy + 8, hx - 8, hy - 8))
    m_frame = ms_poly_mask(size, rect_poly(cam, -FRAME_HALF[0], -FRAME_HALF[1], FRAME_HALF[0], FRAME_HALF[1], 0.5))
    m_tray = ms_poly_mask(size, rect_poly(cam, *TRAY_TOP, z=-1.0))
    x0, y0, z0, x1, y1, z1 = TRAY_BOX
    corners = [[x, y, z] for x in (x0, x1) for y in (y0, y1) for z in (z0, z1)]
    m_obj = ms_poly_mask(size, hull(cam.project(corners)))
    hud = np.zeros((H, W), bool)
    for r in HUD_RECTS:
        hud[r[1]:r[3], r[0]:r[2]] = True
    m_sur = m_tray & ~m_frame
    m_bg = ~m_obj & ~hud
    spaces, r_uu = load_spaces(map_key)
    res = {"map": stats(img, m_map), "surround": stats(img, m_sur), "background": stats(img, m_bg),
           "frame": stats(img, m_frame & ~m_map), "whole": stats(img, ~hud),
           "circles": circle_metrics(img, cam, spaces, r_uu)}
    mp, su, bg = res["map"], res["surround"], res["background"]
    res["ratios"] = {
        "surround/map": round(su["lumaMean"] / mp["lumaMean"], 3) if su.get("n") else None,
        "bg/map": round(bg["lumaMean"] / mp["lumaMean"], 3) if bg.get("n") else None,
        "surround_minus_map_b": round(su["b"] - mp["b"], 1) if su.get("n") else None}
    return res


# ============================================================================ cmp_concept.py (P7, unchanged logic)
def surround_mask(cam: Cam, margin=6.0, ztop=14.0) -> np.ndarray:
    hx, hy = FRAME_HALF[0] + margin, FRAME_HALF[1] + margin
    pts = []
    for z in (-2.0, ztop):
        pts += [(-hx, -hy, z), (hx, -hy, z), (hx, hy, z), (-hx, hy, z)]
    xy = cam.project(pts)
    from scipy.spatial import ConvexHull
    hull_ = xy[ConvexHull(xy).vertices]
    im = Image.new("L", (cam.w, cam.h), 0)
    ImageDraw.Draw(im).polygon([tuple(p) for p in hull_], fill=255)
    m = np.asarray(im) == 0
    for x0, y0, x1, y1 in HUD_RECTS:
        m[y0:y1, x0:x1] = False
    return m


def luma(rgb):
    return rgb @ W709


def ssim(a, b, mask, sigma=1.5):
    a, b = a.astype(np.float64), b.astype(np.float64)
    C1, C2 = (0.01 * 255) ** 2, (0.03 * 255) ** 2
    mu_a, mu_b = ndimage.gaussian_filter(a, sigma), ndimage.gaussian_filter(b, sigma)
    saa = ndimage.gaussian_filter(a * a, sigma) - mu_a ** 2
    sbb = ndimage.gaussian_filter(b * b, sigma) - mu_b ** 2
    sab = ndimage.gaussian_filter(a * b, sigma) - mu_a * mu_b
    s = ((2 * mu_a * mu_b + C1) * (2 * sab + C2)) / ((mu_a ** 2 + mu_b ** 2 + C1) * (saa + sbb + C2))
    m = ndimage.binary_erosion(mask, iterations=4)
    return float(s[m].mean())


# ============================================================================ gates.py (P9, unchanged logic)
KEY_DIR = np.array([math.cos(math.radians(30)), math.sin(math.radians(30))])  # key light (-55, 30, 0), horizontal
MEDUSA_FOOT = np.array([-218.0, -13.0])  # cp_common.K2_HERO_FOCUS sarpedon (the K2x1.6 bench focus)
# big patches of the concept at C0 (1920 x 1080 px rects): water, sand, forest, hull, cliffs, deck, fort
PATCHES = {"sea-right": (1800, 840, 1905, 930), "sand-beach": (840, 150, 1130, 220), "forest-w": (30, 240, 170, 440),
           "hull-red": (1640, 330, 1700, 470), "cliffs-front": (1060, 920, 1340, 1040), "deck-e": (1550, 430, 1615, 740),
           "fort": (345, 40, 420, 150)}
BAND = (500, 840, 1420, 868)  # the painted frame band in front of the map (reported, not in the median)
LANTERNS = {"lantern-bay": (818, 60), "lantern-left": (301, 393), "lantern-stern": (1408, 76), "lantern-rail": (1783, 247),
            "lantern-deck-n": (1541, 344), "lantern-deck-se": (1719, 695)}


def load(p):
    return np.asarray(Image.open(p).convert("RGB")).astype(np.float64)


def trace_path(run: Path) -> Path:
    """bench.trace.log (a fresh run) or bench.trace.txt (the git evidence: *.log is gitignored)."""
    for name in ("bench.trace.log", "bench.trace.txt"):
        if (run / name).is_file():
            return run / name
    raise FileNotFoundError(f"{run}: no bench.trace.log / bench.trace.txt")


def shots(run: Path) -> dict:
    out = {}
    for name, ctx in parse_shots(trace_path(run)).items():
        view = name[len("bench-"):-len("-1920x1080.png")]
        out[view] = (run / name, Cam(ctx[0], ctx[1], ctx[2]))
    return out


def sample(img, cam, P):
    xy = cam.project(np.asarray(P, float))
    ok = (xy[:, 0] > 1) & (xy[:, 0] < img.shape[1] - 2) & (xy[:, 1] > 1) & (xy[:, 1] < img.shape[0] - 2)
    v = bilinear(img, np.clip(xy, 2, [img.shape[1] - 3, img.shape[0] - 3]))
    return v, ok, xy


def g1(on: Path, off: Path) -> dict:
    a, b = shots(on), shots(off)
    res = {}
    for view in a:
        if view not in b:
            continue
        ion, cam = load(a[view][0]), a[view][1]
        ioff = load(b[view][0])
        m = surround_mask(cam)
        lon, loff = float(luma(ion)[m].mean()), float(luma(ioff)[m].mean())
        # linear-light ratio too (display luma is gamma-encoded)
        lin_on = float((srgb_to_lin(ion) @ W709)[m].mean())
        lin_off = float((srgb_to_lin(ioff) @ W709)[m].mean())
        res[view] = {"surroundLumaOn": round(lon, 2), "surroundLumaOff": round(loff, 2), "ratio": round(loff / lon, 4),
                     "ratioLinear": round(lin_off / lin_on, 4), "maskShare": round(float(m.mean()), 3),
                     "pass": loff / lon < 0.12}
    return res


def g2(run: Path) -> dict:
    s = shots(run)
    res = {}
    for view in ("K1", "K1x1p6", "K2x1p6", "Fitx1p45"):
        if view not in s:
            continue
        img, cam = load(s[view][0]), s[view][1]
        L = luma(img)
        for side in ("south", "east", "west", "north"):
            def pts(d):
                if side in ("south", "north"):
                    xs = np.arange(-400.0, 400.1, 2.0)
                    y = (FRAME_HALF[1] + d) * (1 if side == "south" else -1)
                    return np.c_[xs, np.full_like(xs, y), np.full_like(xs, -3.0)]
                ys = np.arange(-260.0, 260.1, 2.0)
                x = (FRAME_HALF[0] + d) * (1 if side == "east" else -1)
                return np.c_[np.full_like(ys, x), ys, np.full_like(ys, -3.0)]
            prof = {}
            for d in np.arange(0.0, 24.1, 0.5):
                v, ok, _ = sample(L[..., None], cam, pts(d))
                prof[float(d)] = float(v[ok, 0].mean()) if ok.sum() > 40 else float("nan")
            with _quiet_nan():
                sh = np.nanmean([prof[d] for d in prof if 0.5 <= d <= 3.0])
                lit = np.nanmean([prof[d] for d in prof if 10.0 <= d <= 20.0])
            if not np.isfinite(sh) or not np.isfinite(lit):
                continue
            # dark gap: per sample line, the longest run of luma < 8 in 0..8 uu out of the foot (px)
            gaps = []
            P0, P1 = pts(-1.0), pts(8.0)
            for p0, p1 in zip(P0, P1):
                seg = np.linspace(p0, p1, 60)
                xy = cam.project(seg)
                okk = (xy[:, 0] >= 0) & (xy[:, 0] < img.shape[1]) & (xy[:, 1] >= 0) & (xy[:, 1] < img.shape[0])
                if okk.sum() < 10:
                    continue
                pix = np.unique(np.round(xy[okk]).astype(int), axis=0)
                dark = L[np.clip(pix[:, 1], 0, img.shape[0] - 1), np.clip(pix[:, 0], 0, img.shape[1] - 1)] < 8
                run_, best = 0, 0
                for k in dark:
                    run_ = run_ + 1 if k else 0
                    best = max(best, run_)
                gaps.append(best)
            gaps = np.array(gaps) if gaps else np.zeros(1)
            res[f"frame-{side}-{view}"] = {"footLuma_d0.5-3": round(float(sh), 2), "bandLuma_d10-20": round(float(lit), 2),
                                           "ratio": round(float(sh / lit), 3),
                                           "profile": {f"{d:g}": round(v, 1) for d, v in prof.items()
                                                       if d in (0, 1, 2, 3, 4, 6, 8, 12, 16, 20, 24)},
                                           "gapLines(run>2px luma<8)": int((gaps > 2).sum()), "lines": int(len(gaps))}
    if "K2x1p6" in s:
        img, cam = load(s["K2x1p6"][0]), s["K2x1p6"][1]
        L = luma(img)
        ang0 = math.atan2(KEY_DIR[1], KEY_DIR[0])
        sh, ref = [], []
        for r in np.arange(14.0, 30.1, 1.0):
            for a in np.radians(np.arange(-180, 180, 3.0)):
                d = (a + math.pi) % (2 * math.pi) - math.pi
                P = [[MEDUSA_FOOT[0] + r * math.cos(ang0 + d), MEDUSA_FOOT[1] + r * math.sin(ang0 + d), 0.5]]
                v, ok, _ = sample(L[..., None], cam, P)
                if not ok[0]:
                    continue
                world_a = ang0 + d
                north = math.sin(world_a) < -0.3  # behind the figure from the camera (occluded by the body)
                if abs(d) <= math.radians(12) and r <= 26:
                    sh.append(v[0, 0])
                elif abs(d) >= math.radians(60) and not north:
                    ref.append(v[0, 0])
        if sh and ref:
            res["medusaK2x1p6"] = {"shadowLuma": round(float(np.mean(sh)), 2),
                                   "refLumaMedian": round(float(np.median(ref)), 2),
                                   "ratio": round(float(np.mean(sh) / np.median(ref)), 3),
                                   "pass": bool(np.mean(sh) / np.median(ref) <= 0.75), "nShadow": len(sh),
                                   "nRef": len(ref)}
    return res


def ssim_quarter(game, ref, mask):
    lg, lr = luma(game), luma(ref)
    g4_ = ndimage.zoom(lg, 0.25, order=1)
    r4 = ndimage.zoom(lr, 0.25, order=1)
    m4 = ndimage.zoom(mask.astype(float), 0.25, order=1) > 0.99
    m4 = m4[: g4_.shape[0], : g4_.shape[1]]
    return ssim(g4_, r4, m4)


def g4(run: Path, concept: Path) -> dict:
    s = shots(run)
    if "Fitx1p45" not in s:
        return {}
    game, cam = load(s["Fitx1p45"][0]), s["Fitx1p45"][1]
    ref = load(concept)
    m = surround_mask(cam)
    res = {"ssimQuarter": round(ssim_quarter(game, ref, m), 4), "ssimFull": round(ssim(luma(game), luma(ref), m), 4),
           "meanAbsDiff": round(float(np.abs(game - ref).mean(-1)[m].mean()), 2),
           "lumaGame": round(float(luma(game)[m].mean()), 2), "lumaConcept": round(float(luma(ref)[m].mean()), 2)}
    pd = {}
    for k, (x0, y0, x1, y1) in list(PATCHES.items()) + [("frame-band (info)", BAND)]:
        a = game[y0:y1, x0:x1].reshape(-1, 3).mean(0)
        b = ref[y0:y1, x0:x1].reshape(-1, 3).mean(0)
        la, lb = lab(a[None])[0], lab(b[None])[0]
        pd[k] = {"dE76": round(float(np.linalg.norm(la - lb)), 2), "gameSrgb": [round(v) for v in a],
                 "conceptSrgb": [round(v) for v in b], "dL": round(float(la[0] - lb[0]), 1)}
    vals = [v["dE76"] for k, v in pd.items() if "info" not in k]
    res["patches"] = pd
    res["patchDeltaE76Median"] = round(float(np.median(vals)), 2)
    res["pass"] = bool(res["ssimQuarter"] >= 0.55 and res["patchDeltaE76Median"] <= 6)
    return res


def glow(a, exclude: dict | None = None):
    """Lantern glow area (px) per lantern. exclude: lantern -> list of polygons [[x, y], ...] in frame px removed from
    the glow mask (ВР-EN.10; applied to the game and the painted frame alike)."""
    out = {}
    for k, (x, y) in LANTERNS.items():
        y0, x0 = max(0, y - 50), x - 40
        reg = a[y0:y + 50, x0:x + 40]
        l = 0.299 * reg[..., 0] + 0.587 * reg[..., 1] + 0.114 * reg[..., 2]
        m = (l > 140) & (reg[..., 0] > reg[..., 2] + 40)
        if exclude and k in exclude:
            ex = np.zeros(a.shape[:2], bool)
            for poly in exclude[k]:
                ex |= poly_mask_pts(poly, a.shape)
            m &= ~ex[y0:y + 50, x0:x + 40]
        out[k] = int(m.sum())
    return out


def banner(a):
    reg = a[340:820, 1780:1920]
    red = (reg[..., 0] > reg[..., 1] * 1.6) & (reg[..., 0] > 35)
    rows = np.nonzero(red.sum(1) >= 12)[0]
    return {"rowsWithCloth": int(len(rows)), "top": int(rows.min() + 340) if len(rows) else None,
            "bottom": int(rows.max() + 340) if len(rows) else None,
            "medianSrgb": np.median(reg[red], 0).round(1).tolist() if red.any() else None}


def g6(run: Path, concept: Path, exclude: dict | None = None) -> dict:
    s = shots(run)
    if "Fitx1p45" not in s:
        return {}
    game, ref = load(s["Fitx1p45"][0]), load(concept)
    gg, gr = glow(game, exclude), glow(ref, exclude)
    per = {k: {"game": gg[k], "painted": gr[k], "ratio": round(gg[k] / max(1, gr[k]), 3)} for k in gg}
    tot = sum(gg.values()) / max(1, sum(gr.values()))
    bg, br = banner(game), banner(ref)
    out = {"lanterns": per, "glowAreaRatioTotal": round(tot, 3),
           "lanternsAt80pct": sum(v["ratio"] >= 0.8 for v in per.values()),
           "bannerGame": bg, "bannerConcept": br,
           "bannerRowsRatio": round(bg["rowsWithCloth"] / max(1, br["rowsWithCloth"]), 3)}
    if exclude:
        out["excluded"] = {k: v for k, v in exclude.items()}
    return out


def map_key_of(run: Path) -> str:
    """measure.py frames: Marmoreal when the trace says so, else Sarpedon."""
    return "marmoreal" if "map=Marmoreal" in trace_path(run).read_text(encoding="utf-8", errors="replace") else "sarpedon"


def g5(run: Path, map_key: str | None = None) -> dict:
    map_key = map_key or map_key_of(run)
    out = {}
    for name, ctx in parse_shots(trace_path(run)).items():
        view = name[len("bench-"):-len("-1920x1080.png")]
        try:
            r = measure_frame(run / name, ctx, map_key)
        except Exception as exc:  # noqa: BLE001
            out[view] = {"error": str(exc)}
            continue
        out[view] = {"mapY": r.get("map", {}).get("lumaMean"), "surroundY": r.get("surround", {}).get("lumaMean"),
                     "surround/map": r["ratios"]["surround/map"], "warm": r.get("surround", {}).get("warmFrac"),
                     "ringDL50": (r.get("circles") or {}).get("edgeDeltaL50")}
    return out


# ============================================================================ zone_precise.py (P5c, unchanged logic)
def zone_min_de(run: Path, map_key: str | None = None, view: str = "K1") -> dict:
    """Minimum adjacent-zone dE76 of the frame without the 0.1 rounding of zone_separation.pair_table (the P10 G5
    number 25.33). Needs the derived map textures (zone_separation.MapData; out of git, main checkout fallback)."""
    map_key = map_key or map_key_of(run)
    sys.path.insert(0, str(MAP_SURFACE))
    try:
        import zone_separation as Z  # noqa: E402
    finally:
        sys.path.remove(str(MAP_SURFACE))
    orig = Z.pair_table
    last = {}

    def pt(zones, adjacent):
        adj = {f"{a}-{b}": float(np.linalg.norm(zones[a] - zones[b])) for a, b in adjacent if a in zones and b in zones}
        k = min(adj, key=adj.get)
        last["pair"], last["dE76"] = k, round(adj[k], 3)
        return orig(zones, adjacent)

    Z.pair_table = pt
    try:
        md = Z.MapData(map_key)
        Z.measure(md, run / f"bench-{view}-1920x1080.png", trace_path(run))
    finally:
        Z.pair_table = orig
    return {"view": view, "map": map_key, **last}


# ============================================================================ g7.py (P9, unchanged logic)
BRAZIER = np.array([-577.3, 139.9, 27.75])  # P9: the brazier bowl fx point (scene overlay fxAnchors / fire-brazier-core)
FORT = np.array([-492.3, -427.3, -3.0])
ROIS_WORLD = {  # name -> (lo, hi) world box
    "foliage": ((-1050.0, -650.0, 0.0), (-640.0, 40.0, 260.0)),
    "sea-W": ((-1500.0, -200.0, -300.0), (-1150.0, 300.0, -300.0)),
    "sea-NE": ((900.0, -1100.0, -300.0), (1500.0, -700.0, -300.0)),
    "waterfall": ((-270.0, 380.0, -300.0), (40.0, 600.0, -40.0)),  # P9 F4: the cascade (cascade-build.json)
    "fire-fort": ((-530.0, -465.0, -3.0), (-455.0, -390.0, 90.0)),
    "fire-brazier": ((-610.0, 110.0, 20.0), (-545.0, 170.0, 110.0)),  # P9: the brazier bowl
}
BANNER_PX_FITX = (1740, 380, 1940, 800)


def box_px(cam, lo, hi, img_shape):
    pts = np.array([[x, y, z] for x in (lo[0], hi[0]) for y in (lo[1], hi[1]) for z in (lo[2], hi[2])], float)
    xy = cam.project(pts)
    x0, y0 = np.clip(xy.min(0), 0, [img_shape[1] - 1, img_shape[0] - 1]).astype(int)
    x1, y1 = np.clip(xy.max(0), 0, [img_shape[1] - 1, img_shape[0] - 1]).astype(int)
    return int(x0), int(y0), int(x1), int(y1)


def changed(a, b, rect):
    x0, y0, x1, y1 = rect
    d = np.abs(a[y0:y1, x0:x1] - b[y0:y1, x0:x1]).max(-1)
    return round(float((d > 8).mean() * 100), 2), (x1 - x0) * (y1 - y0)


def g7(run: Path, diff_out: Path | None = None) -> dict:
    s = shots(run)
    res = {"pairs": {}}
    for a, b in (("Fitx1p45", "Fitx1p450"), ("K1", "K1x1p0")):
        if a not in s or b not in s:
            continue
        ia, ib = load(s[a][0]), load(s[b][0])
        cam = s[a][1]
        d = np.abs(ia - ib).max(-1)
        pair = {"meanAbsDiff": round(float(np.abs(ia - ib).mean()), 3), "pxOver8Pct": round(float((d > 8).mean() * 100), 3),
                "rois": {}}
        for name, (lo, hi) in ROIS_WORLD.items():
            r = box_px(cam, lo, hi, ia.shape)
            if (r[2] - r[0]) * (r[3] - r[1]) < 200:
                continue
            pct, n = changed(ia, ib, r)
            pair["rois"][name] = {"rectPx": r, "changedPct": pct, "px": n}
        if a.startswith("Fitx"):
            pct, n = changed(ia, ib, BANNER_PX_FITX)
            pair["rois"]["banner-rect"] = {"rectPx": BANNER_PX_FITX, "changedPct": pct, "px": n}
            # the cloth itself: red pixels (R > 1.6 G, R > 30) of either frame in the rect, dilated 2 px
            x0, y0, x1, y1 = BANNER_PX_FITX[0], BANNER_PX_FITX[1], min(BANNER_PX_FITX[2], ia.shape[1]), BANNER_PX_FITX[3]
            ra, rb = ia[y0:y1, x0:x1], ib[y0:y1, x0:x1]
            cl = ((ra[..., 0] > ra[..., 1] * 1.6) & (ra[..., 0] > 30)) | ((rb[..., 0] > rb[..., 1] * 1.6) & (rb[..., 0] > 30))
            cl = ndimage.binary_dilation(cl, iterations=2)
            dd = np.abs(ra - rb).max(-1)
            pair["rois"]["banner-cloth"] = {"changedPct": round(float((dd[cl] > 8).mean() * 100), 2), "px": int(cl.sum())}
        # the foliage crowns: green pixels of the W forest box
        fr = ROIS_WORLD["foliage"]
        x0, y0, x1, y1 = box_px(cam, fr[0], fr[1], ia.shape)
        ra, rb = ia[y0:y1, x0:x1], ib[y0:y1, x0:x1]
        gm = (ra[..., 1] > ra[..., 0]) & (ra[..., 1] > ra[..., 2] * 0.9) & (ra[..., 1] > 15)
        dd = np.abs(ra - rb).max(-1)
        pair["rois"]["foliage-crowns"] = {"changedPct": round(float((dd[gm] > 8).mean() * 100), 2), "px": int(gm.sum())}
        res["pairs"][f"{a}-vs-{b}"] = pair
        if diff_out is not None:
            diff_out.mkdir(parents=True, exist_ok=True)
            Image.fromarray(np.clip(np.abs(ia - ib) * 4, 0, 255).astype(np.uint8)).save(diff_out / f"diff-live-{a}.png")
    # brazier light over time (K1 series)
    series = [v for v in ("K1", "K1x1p0", "K1x1p00", "K1x1p000", "K1x1p0000", "K1x1p00000") if v in s]
    vals = []
    for v in series:
        img, cam = load(s[v][0]), s[v][1]
        L = luma(img)
        pts = []
        for r in np.arange(40.0, 141.0, 4.0):
            for a in np.radians(np.arange(0, 360, 6.0)):
                pts.append([BRAZIER[0] + r * np.cos(a), BRAZIER[1] + r * np.sin(a), 0.0])
        xy = cam.project(np.array(pts))
        fl = cam.project(np.array([[BRAZIER[0], BRAZIER[1], z] for z in np.arange(20, 120, 10)]))
        ok = (xy[:, 0] > 2) & (xy[:, 0] < 1917) & (xy[:, 1] > 2) & (xy[:, 1] < 1077)
        # mask the flame sprite: within 45 px of the flame column
        dflame = np.min(np.linalg.norm(xy[:, None, :] - fl[None, :, :], axis=-1), axis=1)
        ok &= dflame > 45
        xi, yi = xy[ok, 0].astype(int), xy[ok, 1].astype(int)
        vals.append(float(L[yi, xi].mean()))
    res["brazierLight"] = {"frames": series, "meanLuma": [round(v, 3) for v in vals],
                           "stdOverTime": round(float(np.std(vals)), 3) if vals else None}
    return res


# ============================================================================ fixes.py F1 + patch.py (P9 / P10)
def srgb2lab(c):
    c = np.asarray(c, float) / 255.0
    lin = np.where(c <= 0.04045, c / 12.92, ((c + 0.055) / 1.055) ** 2.4)
    M = np.array([[0.4124, 0.3576, 0.1805], [0.2126, 0.7152, 0.0722], [0.0193, 0.1192, 0.9505]])
    xyz = M @ lin / np.array([0.95047, 1.0, 1.08883])
    f = np.where(xyz > 216 / 24389, np.cbrt(xyz), (24389 / 27 * xyz + 16) / 116)
    return np.array([116 * f[1] - 16, 500 * (f[0] - f[1]), 200 * (f[1] - f[2])])


def de(a, b):
    """patch.py de / fixes.py de76: (dE76, dL*) of two mean sRGB colours."""
    la, lb = srgb2lab(a), srgb2lab(b)
    return float(np.linalg.norm(la - lb)), float(la[0] - lb[0])


def ssim_map(a, b):
    a4 = ndimage.zoom(a, 0.25, order=1)
    b4 = ndimage.zoom(b, 0.25, order=1)
    sigma = 1.5
    C1, C2 = (0.01 * 255) ** 2, (0.03 * 255) ** 2
    mu_a, mu_b = ndimage.gaussian_filter(a4, sigma), ndimage.gaussian_filter(b4, sigma)
    saa = ndimage.gaussian_filter(a4 * a4, sigma) - mu_a ** 2
    sbb = ndimage.gaussian_filter(b4 * b4, sigma) - mu_b ** 2
    sab = ndimage.gaussian_filter(a4 * b4, sigma) - mu_a * mu_b
    return ((2 * mu_a * mu_b + C1) / (mu_a ** 2 + mu_b ** 2 + C1)) * ((2 * sab + C2) / (saa + sbb + C2))


def poly_mask_pts(pts, shape):
    """fixes.py poly_mask(pts, shape)."""
    im = Image.new("L", (shape[1], shape[0]), 0)
    ImageDraw.Draw(im).polygon([tuple(map(float, p)) for p in pts], fill=1)
    return np.asarray(im).astype(bool)


def ship_poly() -> list:
    sp = json.loads(SCENE_PARAMS.read_text(encoding="utf-8"))
    return sp["ship"]["targetC0Px"]


def f1(fitx_png, concept):
    poly = ship_poly()
    g = load(fitx_png)
    m = poly_mask_pts(poly, g.shape)
    S = ssim_map(g @ W709, concept @ W709)
    m4 = ndimage.zoom(m.astype(float), 0.25, order=1)[:S.shape[0], :S.shape[1]] > 0.99
    m4 = ndimage.binary_erosion(m4, iterations=2)
    # the hull wall only: the lower half of the polygon below the rail (rows 250..640 at C0, x >= 1560)
    hull_ = m.copy()
    hull_[:250] = False
    hull_[:, :1560] = False
    h4 = ndimage.zoom(hull_.astype(float), 0.25, order=1)[:S.shape[0], :S.shape[1]] > 0.99
    h4 = ndimage.binary_erosion(h4, iterations=2)
    mg, mc = g[m].mean(0), concept[m].mean(0)
    d_poly, dl_poly = de(mg, mc)
    x0, y0, x1, y1 = PATCHES["hull-red"]
    pg, pc = g[y0:y1, x0:x1].reshape(-1, 3).mean(0), concept[y0:y1, x0:x1].reshape(-1, 3).mean(0)
    d_patch, dl_patch = de(pg, pc)
    return {"ssimShipPoly": round(float(S[m4].mean()), 4), "ssimHullWall": round(float(S[h4].mean()), 4),
            "polyDE76": round(d_poly, 2), "polyDL": round(dl_poly, 2), "polyGameSrgb": [round(v) for v in mg],
            "polyConceptSrgb": [round(v) for v in mc], "hullPatchDE76": round(d_patch, 2), "hullPatchDL": round(dl_patch, 2)}


# ============================================================================ edgerun.py (P10, unchanged logic)
def longest(b):
    best = 0
    run_ = 0
    for v in b:
        run_ = run_ + 1 if v else 0
        best = max(best, run_)
    return best


def edge(p, roi, d=1, thr=35, signed=False, resize=False):
    im = Image.open(p).convert("RGB")
    if resize:
        im = im.resize((1920, 1080), Image.LANCZOS)
    l = np.asarray(im).astype(np.float64) @ W709
    x0, y0, x1, y1 = roi
    best = (0, None)
    for y in range(y0, y1 - d):
        diff = l[y + d, x0:x1] - l[y, x0:x1]
        b = np.abs(diff) > thr
        r = longest(b)
        if r > best[0]:
            best = (r, y)
    return best


# ============================================================================ cannons.py (P10, unchanged logic)
MUZ = {"cannon-1": (1542, 247), "cannon-2": (1630, 337), "cannon-3": (1737, 502)}
DET = {"cannon-1": (1579, 241), "cannon-2": (1654, 339), "cannon-3": (1768, 496)}
HULL_DY = 40
LANT = [(1783, 247), (1541, 344), (1719, 695)]


def cannon_centres():
    return {k: ((MUZ[k][0] + DET[k][0]) / 2, (MUZ[k][1] + DET[k][1]) / 2) for k in MUZ}


def Lstar(a):
    return srgb2lab(a.reshape(-1, 3).mean(0))[0]


def cannons(p) -> dict:
    a = np.asarray(Image.open(p).convert("RGB")).astype(float)
    out = {}
    for k, (cx, cy) in cannon_centres().items():
        cx, cy = int(round(cx)), int(round(cy))
        b = a[cy - 10:cy + 10, cx - 10:cx + 10]
        h = a[cy + HULL_DY - 10:cy + HULL_DY + 10, cx - 10:cx + 10]
        lb, lh = Lstar(b), Lstar(h)
        out[k] = {"barrelL": round(lb, 1), "hullL": round(lh, 1), "dL": round(abs(lb - lh), 1)}
    return out


# ============================================================================ ssimship.py (P10, unchanged logic)
def ssim_ship_grid(p, con):
    g = load(p)
    m = poly_mask_pts(ship_poly(), g.shape)
    S = ssim_map(g @ W709, con @ W709)
    m4 = ndimage.zoom(m.astype(float), 0.25, order=1)[:S.shape[0], :S.shape[1]] > 0.99
    m4 = ndimage.binary_erosion(m4, iterations=2)
    # cells of 25x25 quarter-px (100x100 C0 px)
    out = {}
    for y in range(0, S.shape[0], 25):
        for x in range(385, S.shape[1], 25):
            mm = m4[y:y + 25, x:x + 25]
            if mm.sum() > 100:
                out[(x * 4, y * 4)] = round(float(S[y:y + 25, x:x + 25][mm].mean()), 3)
    return out, float(S[m4].mean())


def ssim_ship(a: Path, b: Path, concept: Path) -> dict:
    con = load(concept)
    ga, sa = ssim_ship_grid(a, con)
    gb, sb = ssim_ship_grid(b, con)
    cells = [{"cellPx": list(k), "a": ga[k], "b": gb.get(k), "delta": round(gb.get(k, 0) - ga[k], 3)} for k in ga]
    return {"meanA": round(sa, 4), "meanB": round(sb, 4), "cells": cells}


# ============================================================================ crit.py (P10, unchanged logic)
def patch_mean(a, box):
    x0, y0, x1, y1 = box
    return a[y0:y1, x0:x1].reshape(-1, 3).mean(0)


def crit(r: Path, concept: Path, gates: bool = False) -> dict:
    r = Path(r)
    out = {"run": str(r)}
    k1 = r / "bench-K1-1920x1080.png"
    c0 = r / "bench-Fitx1p45-1920x1080.png"
    con = load(concept)
    if k1.exists():
        n, row = edge(str(k1), (560, 900, 1360, 1080), 1)
        out["V1_K1_edgeRunPx"] = {"value": n, "row": row, "pass": n <= 100}
    if c0.exists():
        g = load(c0)
        n, row = edge(str(c0), (560, 800, 1360, 1080), 1)
        out["V1_C0_edgeRunPx(info)"] = {"value": n, "row": row}
        a, b = patch_mean(g, (660, 870, 980, 1000)), patch_mean(con, (660, 870, 980, 1000))
        d, dl = de(a, b)
        out["V1_C0_fallsBody"] = {"dE76": round(d, 2), "dL": round(dl, 2), "game": a.round(1).tolist(),
                                  "concept": b.round(1).tolist(), "pass": d <= 6 and dl <= 4}
        a, b = patch_mean(g, PATCHES["fort"]), patch_mean(con, PATCHES["fort"])
        d, dl = de(a, b)
        out["V2_C0_fort"] = {"dE76": round(d, 2), "dL": round(dl, 2), "game": a.round(1).tolist(),
                             "concept": b.round(1).tolist(), "pass": d <= 7}
        f1_ = f1(c0, con)
        out["F1"] = f1_
        out["V3_F1_ssimShipPoly"] = {"value": f1_["ssimShipPoly"], "pass": f1_["ssimShipPoly"] >= 0.45}
        out["V4_hullRed"] = {"dE76": f1_["hullPatchDE76"], "dL": f1_["hullPatchDL"], "pass": f1_["hullPatchDE76"] <= 6}
        # cannons: barrel patch (20x20 at the painted barrel midpoint) vs the hull-red patch (L*)
        hullL = srgb2lab(patch_mean(g, PATCHES["hull-red"]))[0]
        hullLc = srgb2lab(patch_mean(con, PATCHES["hull-red"]))[0]
        cans = {}
        for k in MUZ:
            cx, cy = (MUZ[k][0] + DET[k][0]) // 2, (MUZ[k][1] + DET[k][1]) // 2

            def cstats(img, hl, cx=cx, cy=cy):
                p = img[cy - 10:cy + 10, cx - 10:cx + 10].reshape(-1, 3)
                Ls = np.array([srgb2lab(px)[0] for px in p])
                return round(float(srgb2lab(p.mean(0))[0] - hl), 1), round(float(np.percentile(Ls, 90) - hl), 1)
            gm, gp = cstats(g, hullL)
            cm, cp = cstats(con, hullLc)
            cans[k] = {"dLmean": gm, "dLp90": gp, "conceptDLmean": cm, "conceptDLp90": cp}
        out["V3_cannons"] = {"hullL": round(float(hullL), 1), "per": cans,
                             "passMean12": all(abs(v["dLmean"]) >= 12 for v in cans.values()),
                             "passP90_12": all(v["dLp90"] >= 12 for v in cans.values())}
        # hull wall max (ship polygon, below the rail, lantern boxes masked)
        m = poly_mask_pts(ship_poly(), g.shape)
        m[:250] = False
        m[:, :1560] = False
        for (x, y) in LANT:
            m[max(0, y - 60):y + 60, max(0, x - 50):x + 50] = False
        m_all = m.copy()
        for k in MUZ:  # the iron barrels (their rim highlights are not the hull side)
            for (x, y) in (MUZ[k], ((MUZ[k][0] + DET[k][0]) // 2, (MUZ[k][1] + DET[k][1]) // 2)):
                m[max(0, y - 16):y + 16, max(0, x - 16):x + 16] = False
        out["V4_hullWallMax_withCannons(info)"] = {"max": float(g[m_all].max()),
                                                   "px>=245": int((g[m_all].max(-1) >= 245).sum())}
        out["V4_hullWallMax"] = {"max": float(g[m].max()), "px>=245": int((g[m].max(-1) >= 245).sum()),
                                 "pass": int((g[m].max(-1) >= 245).sum()) == 0}
    if gates:
        try:
            trace_path(r)
            has_trace = True
        except FileNotFoundError:
            has_trace = False
        if has_trace:
            g4_ = g4(r, concept)
            out["G4"] = {"ssimQuarter": g4_.get("ssimQuarter"), "patchMedian": g4_.get("patchDeltaE76Median"),
                         "patches": {k: v["dE76"] for k, v in g4_.get("patches", {}).items()}}
            g5_ = g5(r)
            out["G5"] = g5_.get("K1")
            g6_ = g6(r, concept)
            out["G6"] = {k: v["ratio"] for k, v in g6_.get("lanterns", {}).items()} if g6_ else None
            if g6_:
                out["G6banner"] = g6_["bannerRowsRatio"]
    return out


# ============================================================================ NEW: streams, fire, sheet (EN-05)
# The cascade of the Sarpedon concept at C0 (= fixes.py F4: columns 640..1000, the rows the painted cascade covers,
# 885..1040). EN-05 measured N_concept = 3 there (concept-registered-H.png; the P10 packaged C0 frame gives 2).
STREAMS_ROI_SARPEDON_C0 = (640, 885, 1000, 1040)
FIRE_ROIS = ("fire-fort", "fire-brazier")  # world boxes of ROIS_WORLD (g7.py), projected with the frame's camera


def streams(p, roi=STREAMS_ROI_SARPEDON_C0, hi=1.4, lo=0.8, min_width=10) -> dict:
    a = load(p)
    x0, y0, x1, y1 = roi
    Y = (a @ W709)[y0:y1, x0:x1]
    m = float(np.median(Y))
    col = Y.mean(0)
    bright = col >= hi * m
    runs, start = [], None
    for x, b in enumerate(bright):
        if b and start is None:
            start = x
        elif not b and start is not None:
            runs.append([start, x - 1])
            start = None
    if start is not None:
        runs.append([start, len(col) - 1])
    merged = []
    for r in runs:  # one stream unless a real dark gap (col <= lo * m) lies between two bright runs
        if merged and not (col[merged[-1][1] + 1:r[0]] <= lo * m).any():
            merged[-1][1] = r[1]
        else:
            merged.append(list(r))
    out = []
    for s0, s1 in merged:
        width = s1 - s0 + 1
        if width >= min_width:
            out.append({"x0": x0 + s0, "x1": x0 + s1, "width": width,
                        "peakCol": round(float(col[s0:s1 + 1].max()), 1)})
    return {"roi": list(roi), "medianY": round(m, 2), "hi": round(hi * m, 2), "lo": round(lo * m, 2),
            "minWidth": min_width, "N": len(out), "streams": out}


def hsv_deg(a):
    """sRGB 0..255 -> (hue deg 0..360, saturation, value 0..1)."""
    rgb = a / 255.0
    mx, mn = rgb.max(-1), rgb.min(-1)
    d = mx - mn
    r, g, b = rgb[..., 0], rgb[..., 1], rgb[..., 2]
    h = np.zeros_like(mx)
    nz = d > 1e-12
    rm = nz & (mx == r)
    gm = nz & (mx == g) & ~rm
    bm = nz & ~rm & ~gm
    h[rm] = ((g[rm] - b[rm]) / d[rm]) % 6
    h[gm] = (b[gm] - r[gm]) / d[gm] + 2
    h[bm] = (r[bm] - g[bm]) / d[bm] + 4
    s = np.where(mx > 0, d / np.maximum(mx, 1e-12), 0.0)
    return h * 60.0, s, mx


def fire_rois(p) -> dict:
    """The fire-fort / fire-brazier world boxes of g7.py projected with the camera of this frame (its run's trace)."""
    p = Path(p)
    view = p.name[len("bench-"):-len("-1920x1080.png")]
    s = shots(p.parent)
    if view not in s:
        raise KeyError(f"{p.name}: no SHOT line in the trace of {p.parent}")
    cam = s[view][1]
    return {k: box_px(cam, ROIS_WORLD[k][0], ROIS_WORLD[k][1], (1080, 1920)) for k in FIRE_ROIS}


def fire(p, roi, min_sat: float = 0.0) -> dict:
    """min_sat 0 = the EN-05 definition; > 0 also needs HSV saturation >= min_sat (the bare definition takes surfaces lit
    by the fire at V >= 0.85 too - the P10 K1 fort wall - so EN-22 may tighten the mask or the ROI)."""
    a = load(p)
    x0, y0, x1, y1 = roi
    reg = a[y0:y1, x0:x1]
    h, s, v = hsv_deg(reg)
    F = (v >= 0.85) & (h >= 10) & (h <= 45) & (s >= min_sat)
    lab_, n = ndimage.label(F, structure=np.ones((3, 3)))
    if n == 0:
        return {"roi": list(roi), "minSat": min_sat, "flamePx": 0, "height": 0, "width": 0, "hOverW": None, "tongues": 0, "redShare": None}
    sizes = ndimage.sum(F, lab_, range(1, n + 1))
    comp = lab_ == (int(np.argmax(sizes)) + 1)
    rows, cols = np.nonzero(comp)
    r0, r1, c0, c1 = rows.min(), rows.max(), cols.min(), cols.max()
    height, width = int(r1 - r0 + 1), int(c1 - c0 + 1)
    # top edge as a height profile over the component's columns
    prof = np.array([float(r1 - np.nonzero(comp[:, c])[0].min() + 1) if comp[:, c].any() else 0.0
                     for c in range(c0, c1 + 1)])
    prof = ndimage.median_filter(prof, size=3, mode="nearest") if len(prof) >= 3 else prof
    prom_min = max(2.0, 0.1 * height)
    tongues = 0
    for i in range(len(prof)):
        if (i > 0 and prof[i] < prof[i - 1]) or (i + 1 < len(prof) and prof[i] < prof[i + 1]):
            continue
        if i > 0 and prof[i] == prof[i - 1]:
            continue  # count a plateau once (at its first column)
        left = prof[:i][::-1]
        right = prof[i + 1:]

        def side_min(seq):
            low = prof[i]
            for vv in seq:
                if vv > prof[i]:
                    break
                low = min(low, vv)
            return low
        lmin = side_min(left) if len(left) else 0.0
        rmin = side_min(right) if len(right) else 0.0
        if prof[i] - max(lmin, rmin) >= prom_min:
            tongues += 1
    box = (slice(r0, r1 + 1), slice(c0, c1 + 1))
    hb, vb = h[box], v[box]
    warm = (vb >= 0.85) & ((hb < 45) | (hb >= 345))
    red = warm & ((hb < 15) | (hb >= 345))
    return {"roi": list(roi), "minSat": min_sat, "flamePx": int(comp.sum()), "bboxPx": [int(x0 + c0), int(y0 + r0), int(x0 + c1), int(y0 + r1)],
            "height": height, "width": width, "hOverW": round(height / max(1, width), 3), "tongues": int(tongues),
            "redShare": round(float(red.sum() / max(1, warm.sum())), 3), "prominenceMinPx": round(prom_min, 1)}


def _sheet_lib():
    sys.path.insert(0, str(REPO / "tools" / "art" / "visual"))
    try:
        import sheet as S  # noqa: E402  (tools/art/visual/sheet.py: gray709 / deuteranopia transforms)
    finally:
        sys.path.remove(str(REPO / "tools" / "art" / "visual"))
    return S


def sheet(pngs: list[Path], out: Path, crop=None, label: str | None = None, max_w: int = 960) -> dict:
    S = _sheet_lib()
    tiles = []
    for p in pngs:
        im = Image.open(p).convert("RGB")
        if crop:
            im = im.crop(tuple(crop))
        if im.width > max_w:
            im = im.resize((max_w, round(im.height * max_w / im.width)), Image.LANCZOS)
        rgb = np.asarray(im)
        tiles.append((Path(p).name, [Image.fromarray(rgb), Image.fromarray(S.gray709(rgb)),
                                     Image.fromarray(S.deuteranopia(rgb))]))
    w = max(t[1][0].width for t in tiles)
    hs = [t[1][0].height for t in tiles]
    head, row_head = 30, 22
    sheet_img = Image.new("RGB", (3 * w, head + sum(h + row_head for h in hs)), (18, 18, 20))
    draw = ImageDraw.Draw(sheet_img)
    try:
        font = ImageFont.truetype("C:/Windows/Fonts/arial.ttf", 16)
    except OSError:
        font = ImageFont.load_default()
    draw.text((8, 6), (label + " | " if label else "") + "colour | grey Rec.709 | deuteranopia (Machado 2009, 1.0)",
              fill=(235, 235, 235), font=font)
    y = head
    for (name, ims), h in zip(tiles, hs):
        draw.text((8, y + 2), name, fill=(200, 200, 200), font=font)
        for i, im in enumerate(ims):
            sheet_img.paste(im, (i * w, y + row_head))
        y += h + row_head
    out.parent.mkdir(parents=True, exist_ok=True)
    sheet_img.save(out)
    return {"out": str(out), "size": list(sheet_img.size), "inputs": [str(p) for p in pngs],
            "modes": ["colour", "grey Rec.709 (sRGB values)", "deuteranopia Machado 2009 severity 1.0 (linear RGB)"]}


# ============================================================================ CLI
def parse_box(s: str) -> tuple[int, int, int, int]:
    v = [int(round(float(x))) for x in s.split(",")]
    if len(v) != 4:
        raise argparse.ArgumentTypeError(f"box needs x0,y0,x1,y1: {s}")
    return tuple(v)


def parse_exclude(items: list[str] | None) -> dict | None:
    """NAME=x,y;x,y;x,y (repeatable; several polygons per lantern allowed)."""
    if not items:
        return None
    out: dict[str, list] = {}
    for it in items:
        name, pts = it.split("=", 1)
        poly = [[float(c) for c in p.split(",")] for p in pts.split(";") if p.strip()]
        if name not in LANTERNS or len(poly) < 3:
            raise argparse.ArgumentTypeError(f"--g6-exclude {it}: known lantern and >= 3 points needed")
        out.setdefault(name, []).append(poly)
    return out


def cmd_gates(a) -> dict:
    run = Path(a.run)
    res = {"run": str(run)}
    if a.off:
        res["G1"] = g1(run, Path(a.off))
    res["G2"] = g2(run)
    if a.concept:
        res["G4"] = g4(run, Path(a.concept))
    res["G5measure"] = g5(run, a.map)
    if (run / "bench-K1-1920x1080.png").is_file():
        try:
            res["G5zones"] = zone_min_de(run, a.map)
        except Exception as exc:  # noqa: BLE001 - derived maps missing etc.
            res["G5zones"] = {"error": str(exc)}
    if a.concept:
        res["G6"] = g6(run, Path(a.concept), parse_exclude(a.g6_exclude))
    live = g7(run, Path(a.g7_diff_out) if a.g7_diff_out else None)
    if live["pairs"] or len(live["brazierLight"]["frames"]) > 1:
        res["G7"] = live
    return res


def main(argv=None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if argv and argv[0] == "--check":
        t0 = time.time()
        errs = self_check()
        dt = time.time() - t0
        for e in errs:
            print("  " + e)
        print(f"env_gates --check: {'ok' if not errs else 'FAILED'} ({dt:.1f} s)")
        return 0 if not errs else 1
    ap = argparse.ArgumentParser(description=__doc__.split("\n", 1)[0])
    ap.add_argument("--json", default=None, help="also write the result here")
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("gates")
    p.add_argument("run")
    p.add_argument("--concept")
    p.add_argument("--off")
    p.add_argument("--map", choices=["marmoreal", "sarpedon"])
    p.add_argument("--g6-exclude", action="append", metavar="NAME=x,y;x,y;...")
    p.add_argument("--g7-diff-out")
    p = sub.add_parser("crit")
    p.add_argument("run")
    p.add_argument("--concept", required=True)
    p.add_argument("--gates", action="store_true")
    p = sub.add_parser("edge")
    p.add_argument("png")
    p.add_argument("--roi", type=parse_box, default=(560, 900, 1360, 1080))
    p.add_argument("--d", type=int, default=1)
    p.add_argument("--thr", type=float, default=35)
    p.add_argument("--resize", action="store_true")
    p = sub.add_parser("ssim-ship")
    p.add_argument("a")
    p.add_argument("b")
    p.add_argument("--concept", required=True)
    p = sub.add_parser("cannons")
    p.add_argument("png", nargs="+")
    p = sub.add_parser("streams")
    p.add_argument("png")
    p.add_argument("--roi", type=parse_box, default=STREAMS_ROI_SARPEDON_C0)
    p.add_argument("--hi", type=float, default=1.4)
    p.add_argument("--lo", type=float, default=0.8)
    p.add_argument("--min-width", type=int, default=10)
    p = sub.add_parser("fire")
    p.add_argument("png")
    p.add_argument("--roi", type=parse_box, action="append", help="default: fire-fort / fire-brazier from the trace")
    p.add_argument("--min-sat", type=float, default=0.0, help="also HSV saturation >= this (default 0: EN-05 mask)")
    p = sub.add_parser("sheet")
    p.add_argument("png", nargs="+")
    p.add_argument("--out", required=True)
    p.add_argument("--crop", type=parse_box)
    p.add_argument("--label")
    a = ap.parse_args(argv)
    if a.cmd == "gates":
        res = cmd_gates(a)
    elif a.cmd == "crit":
        res = crit(Path(a.run), Path(a.concept), a.gates)
    elif a.cmd == "edge":
        n, row = edge(a.png, a.roi, a.d, a.thr, resize=a.resize)
        res = {"png": a.png, "roi": list(a.roi), "d": a.d, "thr": a.thr, "edgeRunPx": n, "row": row}
    elif a.cmd == "ssim-ship":
        res = ssim_ship(Path(a.a), Path(a.b), Path(a.concept))
    elif a.cmd == "cannons":
        res = {p_: cannons(p_) for p_ in a.png}
    elif a.cmd == "streams":
        res = streams(a.png, a.roi, a.hi, a.lo, a.min_width)
    elif a.cmd == "fire":
        rois = {f"roi{i}": r for i, r in enumerate(a.roi)} if a.roi else fire_rois(a.png)
        res = {"png": a.png, "fires": {k: fire(a.png, r, a.min_sat) for k, r in rois.items()}}
    else:
        res = sheet([Path(x) for x in a.png], Path(a.out), a.crop, a.label)
    txt = json.dumps(res, indent=1, default=float, ensure_ascii=False)
    if a.json:
        Path(a.json).write_text(txt + "\n", encoding="utf-8")
    print(txt)
    return 0


# ============================================================================ --check (synthetic, no frames)
def self_check() -> list[str]:
    import tempfile

    errs: list[str] = []

    def ok(cond, msg):
        if not cond:
            errs.append(msg)

    with tempfile.TemporaryDirectory() as td:
        td = Path(td)
        # edge: a 300 px bright bar over dark -> straight horizontal edge of 300 px at its top row
        img = np.zeros((1080, 1920, 3), np.uint8)
        img[950:1080, 700:1000] = 200
        Image.fromarray(img).save(td / "edge.png")
        n, row = edge(td / "edge.png", (560, 900, 1360, 1080))
        ok(n == 300 and row == 949, f"edge: {n} @ {row}, expected 300 @ 949")
        # streams: median 40 (the mid-tone), rocks 20 (<= 0.8 x median: a real gap), stripes 200 (>= 1.4 x median):
        # 4 stripes of 14 px, a 6 px sliver (too narrow), and two stripes split by a 50 column (no dark gap) = one of 28
        img = np.full((300, 400, 3), 40, np.uint8)
        for x in (20, 80, 140, 200):
            img[:, x:x + 14] = 200
        for x0_, x1_ in ((34, 44), (94, 104), (154, 164), (230, 240), (280, 290)):
            img[:, x0_:x1_] = 20
        img[:, 260:266] = 200
        img[:, 300:312] = 200
        img[:, 312:316] = 50
        img[:, 316:328] = 200
        Image.fromarray(img).save(td / "streams.png")
        st = streams(td / "streams.png", (0, 0, 400, 300))
        ok(st["N"] == 5, f"streams: N={st['N']} expected 5 ({[s_['x0'] for s_ in st['streams']]})")
        ok(st["streams"][-1]["width"] == 28, f"streams: merged width {st['streams'][-1]['width']} expected 28")
        # fire: three triangular tongues of yellow-orange flame on black, one red blob beside
        img = np.zeros((200, 200, 3), np.uint8)
        flame = np.zeros((200, 200), bool)
        for cx, top in ((60, 40), (90, 60), (120, 30)):
            for yy in range(top, 170):
                half = int((yy - top) * 0.35) + 1
                flame[yy, max(0, cx - half):cx + half] = True
        flame[150:170, 40:140] = True
        img[flame] = (255, 170, 30)  # hue ~38 deg, V 1.0
        img[160:170, 60:80] = (255, 30, 20)  # red: hue < 15 inside the box
        Image.fromarray(img).save(td / "fire.png")
        fr = fire(td / "fire.png", (0, 0, 200, 200))
        ok(fr["tongues"] == 3, f"fire: tongues {fr['tongues']} expected 3")
        ok(fr["height"] == 140 and fr["hOverW"] is not None and 0.5 < fr["hOverW"] < 2.0,
           f"fire: height {fr['height']} h/w {fr['hOverW']}")
        ok(fr["redShare"] is not None and 0.0 < fr["redShare"] < 0.2, f"fire: redShare {fr['redShare']}")
        # sheet: three panels, grey has equal channels
        sh = sheet([td / "fire.png"], td / "sheet.png", label="check")
        sim = np.asarray(Image.open(td / "sheet.png").convert("RGB"))
        ok(sh["size"][0] == 600, f"sheet: width {sh['size'][0]} expected 600")
        gpanel = sim[52:252, 200:400]
        ok(np.abs(gpanel[..., 0].astype(int) - gpanel[..., 2]).max() == 0, "sheet: grey panel not grey")
        # colour maths
        ok(abs(srgb2lab([255, 255, 255])[0] - 100) < 0.01, "srgb2lab white L != 100")
        ok(de([10, 20, 30], [10, 20, 30]) == (0.0, 0.0), "de of equal colours != 0")
        ok(abs(lab(np.array([[255.0, 255.0, 255.0]]))[0, 0] - 100) < 0.01, "lab white L != 100")
        # a synthetic run: the concept itself as the game frame -> G4 SSIM 1, patch dE 0, G6 ratios 1
        rng = np.random.default_rng(7)
        con = (rng.random((1080, 1920, 3)) * 120).astype(np.uint8)
        for (x, y) in LANTERNS.values():
            con[y - 20:y + 20, x - 15:x + 15] = (250, 190, 90)  # lantern glow: luma > 140, R > B + 40
        run = td / "run"
        run.mkdir()
        Image.fromarray(con).save(td / "concept.png")
        Image.fromarray(con).save(run / "bench-Fitx1p45-1920x1080.png")
        Image.fromarray(con).save(run / "bench-Fitx1p450-1920x1080.png")
        (run / "bench.trace.txt").write_text(
            "SHOT ctx view=Fitx1p45 cam=(-1600.0,0.0,1500.0) rot=(-45.0,0.0,0.0)\n"
            "SHOT captured file=bench-Fitx1p45-1920x1080.png\n"
            "SHOT ctx view=Fitx1p450 cam=(-1600.0,0.0,1500.0) rot=(-45.0,0.0,0.0)\n"
            "SHOT captured file=bench-Fitx1p450-1920x1080.png\n", encoding="utf-8")
        cam = shots(run)["Fitx1p45"][1]
        c = cam.project([[0.0, 0.0, 0.0]])[0]
        ok(abs(c[0] - 960) < 1e-6, f"Cam: board centre x {c[0]:.3f} != 960")
        r4 = g4(run, td / "concept.png")
        ok(abs(r4["ssimQuarter"] - 1.0) < 1e-9 and r4["patchDeltaE76Median"] == 0.0, f"G4 on identical frames: {r4}")
        r6 = g6(run, td / "concept.png")
        ok(all(v["ratio"] == 1.0 for v in r6["lanterns"].values()), "G6 on identical frames: ratio != 1")
        x, y = LANTERNS["lantern-deck-se"]
        ex = {"lantern-deck-se": [[[x - 15, y], [x + 15, y], [x + 15, y + 20], [x - 15, y + 20]]]}
        before = glow(con.astype(float))["lantern-deck-se"]
        after = glow(con.astype(float), ex)["lantern-deck-se"]
        ok(before == 1200 and after == 600, f"G6 exclusion polygon: {before} -> {after}, expected 1200 -> 600")
        r7 = g7(run)
        pair = r7["pairs"].get("Fitx1p45-vs-Fitx1p450", {})
        ok(pair.get("pxOver8Pct") == 0.0, f"G7 on identical frames: {pair.get('pxOver8Pct')}")
        ok(parse_exclude(["lantern-deck-se=1,2;3,4;5,6"]) == {"lantern-deck-se": [[[1.0, 2.0], [3.0, 4.0], [5.0, 6.0]]]},
           "parse_exclude")
    return errs


if __name__ == "__main__":
    sys.exit(main())
