#!/usr/bin/env python3
"""ENV-MAPS P2 track GROUND (user decision ENV-U10): splat masks of the themed ground around the original maps.

The ground is one flat layer between the wooden map frame and the tray edge (S08EnvLayout 'ground' section, spawned
by S08EnvGround.cpp as four engine-plane strips at z -1 under M_EnvGround / MI_EnvGround_<Map>). Its look comes from
four CC0 texture sets (ground-params.json 'maps.<key>.layers': L0 base + L1/L2/L3 stacked on top, L3 uppermost) and
one RGBA8 splat texture per map made here from region rules tied to the env layout (prop positions) and the map:

  R = coverage of L1, G = coverage of L2, B = coverage of L3, A = accent density
  Marmoreal  L0 Ground076 dark earth | R Moss002 (cherries, cypresses, tray rim, paving edge) | G Grass005 (outer beds)
             | B Tiles143 marble paving (palace terrace N, walkway round the frame, lamp / plinth / urn pads) | A petals
  Sarpedon   L0 Moss002 forest floor | R Ground055S sand (beach N-centre, river banks, fire clearings, fort dust)
             | G Gravel021 pebbles (both river channels, fort rubble, beach scatter) | B Planks023A deck (E band under the
             hull / cannons, quay N-E and S-E) | A wetness (river channels, sea spray)

A second RGBA8 texture on the same grid, the aux mask (P4, review gaps 1 / 5 / 10), drives what the splat layers cannot:

  R = water coverage (Sarpedon river mouths: N into the sea surf, S to the waterfall), G = foam (shore band, surf
  lines), B = edge band (Marmoreal: the 1-tile curb of the paving; Sarpedon: the deck beam where the planks end),
  A = 1 + water depth * 254 (0 at the shore, 1 at ground-params 'rules.depthUU' into the water; never a zero alpha)

Borders are soft and noisy (deterministic value-noise fBm, seeded per map) and blurred per channel ('rules.blurUU', a
separable Gaussian in uu), the deck keeps straight plank-end edges. Everything is our own procedural art (no original-map
pixels): the only map-derived inputs are coordinates (frame size, the Sarpedon river x-runs measured at the map edges,
ground-params.json 'river'). Every rule number has a code default and may be overridden in ground-params.json
'maps.<key>.rules' (the Tune stage iterates there).

Board-actor space (uu): origin = map centre, +X right on the K1 screen, +Y towards the K1 camera (near side); frame
outer |X| <= 469.667, |Y| <= 312.667; the tray is ground-params.json 'tray' (shared by both maps). The splat covers
splatRect = (params tray U layout tray) + marginUU, rounded outward to roundUU: pixel (i, j) centre =
(minX + (i + 0.5) * w / W, minY + (j + 0.5) * h / H), so row 0 is the far side - the UE texture V = 0 row, matching
M_EnvGround's SplatUV = (P - SplatRect.xy) / SplatRect.zw.

Outputs (art/pipeline-candidates/ASSET-ENV-KIT-001/ground/, our derived art, small, git):
  <map>.splat.png      RGBA8 (the texture ue_import_env_ground.py imports as T_EnvGround_<Map>_Splat)
  <map>.aux.png        RGBA8 aux mask (T_EnvGround_<Map>_Aux): water / foam / edge band / water depth
  <map>.splat.json     meta: rect, size, channels, coverage, sha256 of the PNGs, params, layout props hash, waterfalls
  <map>.preview.png    top: false-colour layers + accent, frame / map / props / tray; bottom: albedo preview with
                       the CC0 textures at their tiling (needs the raw sets, ground-params.json 'cc0Raw')
With --write-layouts the 'ground' section of Config/ArtBoards/EnvLayouts/<map>.layout.json is (re)written:
  {"mode":"runtime", "material":"/Game/EnvKit/Ground/MI_EnvGround_<Map>", "z", "frameOverlapUU", "insetUU",
   "splatRect":[minX, minY, maxX, maxY], "splat":"<repo-relative png>", "splatSha256", "aux", "auxSha256",
   "waterfalls":[{"id", "material":"/Game/EnvKit/Ground/MI_EnvWaterfall_<Map>", "x0", "x1", "y", "topZ", "dropUU",
                  "spillUU"}]  (only maps with ground-params 'water.falls'; S08EnvGround spawns them), "notes"}

Usage (repository root; plain Python: numpy, PIL):
  python -B tools/art/env_kit/ground_splat.py                        # both maps: splat + meta + preview
  python -B tools/art/env_kit/ground_splat.py --write-layouts        # + the layouts' 'ground' sections
  python -B tools/art/env_kit/ground_splat.py --check                # regenerate in memory, compare, validate layouts
Options: --maps marmoreal,sarpedon  --params <json>  --out <dir>  --no-preview  --tray-extents <json>
"""
from __future__ import annotations

import argparse
import hashlib
import io
import json
import math
import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
sys.path.insert(0, str(HERE))
import layout_check as lc  # noqa: E402  (footprint / dims / kit sizes / frame constants)

PARAMS_DEFAULT = REPO / "art/pipeline-candidates/ASSET-ENV-KIT-001/ground/ground-params.json"
LAYOUT_DIR = REPO / "unreal/Unmatched/Config/ArtBoards/EnvLayouts"
TRAY_EXTENTS_SCRATCH = Path("C:/tmp/envmaps-research/p2/tray-extents.json")
SCHEMA_META = "unmatched.env-ground-splat/1"
MAPS = {"marmoreal": "Marmoreal", "sarpedon": "Sarpedon"}
FX, FY = lc.FRAME_HX, lc.FRAME_HY  # 469.667 x 312.667
MX, MY = lc.MAP_HX, lc.MAP_HY      # 445.667 x 288.667
SEEDS = {"marmoreal": 1101, "sarpedon": 2203}
PREVIEW_UU_PER_PX = 2.0


# ------------------------------------------------------------------------------------------------ small helpers
def rel(path: Path) -> str:
    try:
        return Path(path).resolve().relative_to(REPO).as_posix()
    except ValueError:
        return Path(path).as_posix()


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sstep(e0: float, e1: float, x):
    t = np.clip((x - e0) / (e1 - e0), 0.0, 1.0)
    return t * t * (3.0 - 2.0 * t)


def inside(d, soft: float):
    """1 inside (d < -soft), 0 outside (d > soft), smooth in between."""
    return sstep(soft, -soft, d)


def sd_box(X, Y, x0, y0, x1, y1):
    cx, cy, hx, hy = (x0 + x1) / 2, (y0 + y1) / 2, abs(x1 - x0) / 2, abs(y1 - y0) / 2
    qx, qy = np.abs(X - cx) - hx, np.abs(Y - cy) - hy
    return np.hypot(np.maximum(qx, 0), np.maximum(qy, 0)) + np.minimum(np.maximum(qx, qy), 0)


def sd_circle(X, Y, cx, cy, r):
    return np.hypot(X - cx, Y - cy) - r


def sd_poly(X, Y, poly: np.ndarray):
    """Signed distance to a convex polygon (negative inside) - the prop footprints of layout_check.footprint."""
    n = len(poly)
    d = np.full(X.shape, np.inf)
    sign = np.ones(X.shape)
    for k in range(n):
        a, b = poly[k], poly[(k + 1) % n]
        ex, ey = b[0] - a[0], b[1] - a[1]
        wx, wy = X - a[0], Y - a[1]
        t = np.clip((wx * ex + wy * ey) / (ex * ex + ey * ey), 0, 1)
        d = np.minimum(d, np.hypot(wx - ex * t, wy - ey * t))
    # inside test (same side of every edge)
    cross = []
    for k in range(n):
        a, b = poly[k], poly[(k + 1) % n]
        cross.append((b[0] - a[0]) * (Y - a[1]) - (b[1] - a[1]) * (X - a[0]))
    cross = np.stack(cross)
    ins = np.all(cross >= 0, axis=0) | np.all(cross <= 0, axis=0)
    sign[ins] = -1.0
    return d * sign


def sd_tube(X, Y, pts: list, radii: list, samples: int = 96):
    """Signed distance to a swept disc along a polyline (radius interpolated along the length)."""
    P = np.array(pts, float)
    R = np.array(radii, float)
    seg = np.hypot(*(P[1:] - P[:-1]).T)
    s = np.concatenate([[0], np.cumsum(seg)])
    t = np.linspace(0, s[-1], samples)
    cx, cy, cr = np.interp(t, s, P[:, 0]), np.interp(t, s, P[:, 1]), np.interp(t, s, R)
    d = np.full(X.shape, np.inf)
    for x, y, r in zip(cx, cy, cr):
        d = np.minimum(d, np.hypot(X - x, Y - y) - r)
    return d


class Noise:
    """Deterministic value-noise fBm on the splat grid (lattice anchored at the rect minimum, in uu)."""

    def __init__(self, X, Y, seed: int):
        self.X, self.Y, self.seed = X, Y, seed
        self.x0, self.y0 = float(X.min()), float(Y.min())

    def value(self, scale: float, key: int):
        rng = np.random.default_rng([self.seed, key, int(scale * 16)])
        gx, gy = (self.X - self.x0) / scale, (self.Y - self.y0) / scale
        nx, ny = int(gx.max()) + 3, int(gy.max()) + 3
        lat = rng.random((ny, nx))
        ix, iy = np.floor(gx).astype(int), np.floor(gy).astype(int)
        fx, fy = gx - ix, gy - iy
        ux, uy = fx * fx * (3 - 2 * fx), fy * fy * (3 - 2 * fy)
        a = lat[iy, ix] * (1 - ux) + lat[iy, ix + 1] * ux
        b = lat[iy + 1, ix] * (1 - ux) + lat[iy + 1, ix + 1] * ux
        return a * (1 - uy) + b * uy

    def fbm(self, scale: float, key: int, octaves: int = 3, gain: float = 0.5):
        total, amp, norm = 0.0, 1.0, 0.0
        for o in range(octaves):
            total = total + amp * self.value(scale / (2 ** o), key * 16 + o)
            norm += amp
            amp *= gain
        v = total / norm
        # stretch the centre-heavy sum back towards [0, 1]
        return np.clip((v - 0.5) * (1.0 + 0.6 * (octaves - 1)) + 0.5, 0.0, 1.0)

    def signed(self, scale: float, key: int, octaves: int = 3):
        return self.fbm(scale, key, octaves) * 2.0 - 1.0


# ------------------------------------------------------------------------------------------------ inputs
def load_params(path: Path) -> dict:
    params = json.loads(Path(path).read_text(encoding="utf-8"))
    if params.get("schema") != "unmatched.env-ground-params/1":
        raise SystemExit(f"{path}: schema {params.get('schema')!r} is not unmatched.env-ground-params/1")
    return params


def tray_rect(t: dict) -> tuple[float, float, float, float]:
    return (-float(t["halfX"]), float(t["offsetY"]) - float(t["halfY"]), float(t["halfX"]),
            float(t["offsetY"]) + float(t["halfY"]))


def tray_notes(params: dict, layout: dict, extents_path: Path | None) -> list[str]:
    """Warnings when the shared tray of the params, the TRAY track's scratch file and the layout disagree."""
    notes = []
    want = tray_rect(params["tray"])
    if extents_path and extents_path.is_file():
        try:
            ext = json.loads(extents_path.read_text(encoding="utf-8"))
            got = tray_rect(ext)
            if max(abs(a - b) for a, b in zip(got, want)) > 0.5:
                notes.append(f"tray-extents {extents_path} = {got} differs from ground-params tray {want}: update "
                             f"ground-params.json 'tray' and re-run")
        except (OSError, ValueError, KeyError) as exc:
            notes.append(f"tray-extents {extents_path} unreadable: {exc}")
    if isinstance(layout.get("tray"), dict):
        got = tray_rect(layout["tray"])
        if max(abs(a - b) for a, b in zip(got, want)) > 0.5:
            notes.append(f"layout tray {tuple(round(v, 2) for v in got)} != shared tray {want} (track TRAY updates the "
                         f"layouts; the splat covers both)")
    return notes


def splat_rect(params: dict, layout: dict) -> tuple[float, float, float, float]:
    rects = [tray_rect(params["tray"])]
    if isinstance(layout.get("tray"), dict):
        rects.append(tray_rect(layout["tray"]))
    m, r = float(params["splat"]["marginUU"]), float(params["splat"]["roundUU"])
    x0 = math.floor((min(q[0] for q in rects) - m) / r) * r
    y0 = math.floor((min(q[1] for q in rects) - m) / r) * r
    x1 = math.ceil((max(q[2] for q in rects) + m) / r) * r
    y1 = math.ceil((max(q[3] for q in rects) + m) / r) * r
    return (x0, y0, x1, y1)


def grid(rect, size):
    x0, y0, x1, y1 = rect
    w, h = size
    xs = x0 + (np.arange(w) + 0.5) * (x1 - x0) / w
    ys = y0 + (np.arange(h) + 0.5) * (y1 - y0) / h
    return np.meshgrid(xs, ys)


def props_of(layout: dict, *names: str) -> list[dict]:
    return [p for p in layout.get("props", []) if lc.mesh_name(p) in names]


def props_hash(layout: dict) -> str:
    return sha256_bytes(json.dumps(layout.get("props", []), sort_keys=True).encode("utf-8"))


# ------------------------------------------------------------------------------------------------ region rules
def _rule(rules: dict, name: str, default: float) -> float:
    """A splat-rule number: ground-params.json 'maps.<key>.rules.<name>', else the code default."""
    v = rules.get(name, default)
    if isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v):
        raise SystemExit(f"ground-params rules.{name} = {v!r} is not a number")
    return float(v)


def gauss_blur(a: np.ndarray, sigma_px: tuple) -> np.ndarray:
    """Separable Gaussian blur (reflect padding, 3 sigma) with sigma in pixels along x (columns) and y (rows)."""
    out = np.asarray(a, float)
    for axis, sig in ((1, float(sigma_px[0])), (0, float(sigma_px[1]))):
        if sig <= 0.05:
            continue
        r = max(1, int(math.ceil(3.0 * sig)))
        k = np.exp(-0.5 * (np.arange(-r, r + 1) / sig) ** 2)
        k /= k.sum()
        pad = [(0, 0), (0, 0)]
        pad[axis] = (r, r)
        ap = np.pad(out, pad, mode="reflect")
        acc = np.zeros_like(out)
        n = out.shape[axis]
        for i, w in enumerate(k):
            sl = [slice(None), slice(None)]
            sl[axis] = slice(i, i + n)
            acc += w * ap[tuple(sl)]
        out = acc
    return out


def rules_marmoreal(X, Y, layout: dict, tray, nz: Noise, rules: dict | None = None) -> dict:
    rules = rules or {}
    tx0, ty0, tx1, ty1 = tray
    d_frame = sd_box(X, Y, -FX, -FY, FX, FY)          # > 0 outside the frame
    d_edge = -sd_box(X, Y, tx0, ty0, tx1, ty1)         # > 0 inside the tray (distance to its edge)
    warp = nz.signed(36.0, 1)
    fine = nz.signed(12.0, 2, 2)
    big = nz.signed(110.0, 3)
    mid = nz.signed(20.0, 9, 2)
    # B: marble paving - walkway round the frame, the palace terrace N (under / behind the colonnade), pads
    d_pave = np.minimum(d_frame - 72.0, sd_box(X, Y, -410.0, ty0 - 50.0, 410.0, -300.0))
    for p in props_of(layout, "LanternPlinth"):
        d_pave = np.minimum(d_pave, sd_circle(X, Y, p["loc"][0], p["loc"][1], 48.0 * p["scale"]))
    for p in props_of(layout, "PlinthBall"):
        d_pave = np.minimum(d_pave, sd_circle(X, Y, p["loc"][0], p["loc"][1], 42.0 * p["scale"]))
    for p in props_of(layout, "Urn", "Portal", "ArcadeBay"):
        d_pave = np.minimum(d_pave, sd_poly(X, Y, lc.footprint(p)) - 14.0)
    # noise-broken border (P4 gap 10: three octaves instead of the torn-paper single warp)
    d_pave_n = (d_pave + _rule(rules, "paveWarpUU", 13.0) * warp + _rule(rules, "paveMidUU", 0.0) * mid
                + _rule(rules, "paveFineUU", 5.0) * fine)
    # the paving stops short of the tray rim (moss there): one signed distance for both borders, so the curb follows both
    d_pave_t = np.maximum(d_pave_n, 23.0 - (d_edge + 9.0 * warp))
    pave = inside(d_pave_t, _rule(rules, "paveSoftUU", 3.0))
    # E (aux B): the curb - the outermost paving tile row (curbWidthUU ~ one Tiles143 tile at L3 tileUU 200 / 6)
    cw = _rule(rules, "curbWidthUU", 0.0)
    curb = (inside(np.abs(d_pave_t + cw / 2.0) - cw / 2.0, _rule(rules, "curbSoftUU", 2.0)) if cw > 0
            else np.zeros_like(X))
    # R: moss under the cherries, round the cypresses, along the tray rim, a ring along the paving edge, patches
    d_cherry = np.full(X.shape, np.inf)
    for p in props_of(layout, "Cherry"):
        d_cherry = np.minimum(d_cherry, sd_circle(X, Y, p["loc"][0], p["loc"][1], 110.0 * p["scale"]))
    d_cyp = np.full(X.shape, np.inf)
    for p in props_of(layout, "Cypress"):
        d_cyp = np.minimum(d_cyp, sd_circle(X, Y, p["loc"][0], p["loc"][1], 48.0 * p["scale"]))
    # (the cherry beds stay dark earth under a carpet of petals, as in the concept)
    under_cherry = inside(d_cherry + 24.0 * big + 8.0 * warp, 18.0)
    moss = np.maximum.reduce([
        0.9 * inside(d_cyp + 12.0 * warp, 10.0),
        0.85 * (1.0 - sstep(8.0, 46.0, d_edge + 16.0 * warp)),
        0.6 * sstep(0.6, 0.76, nz.fbm(80.0, 4)) * sstep(0.0, 30.0, d_pave_t) * (1.0 - under_cherry),
        0.65 * inside(np.abs(d_pave_t - 7.0) - 6.0 + 3.0 * fine, 3.0),
    ])
    # G: grass tufts in the outer W / E beds (not under the cherry crowns, not on the rim moss)
    outer = sstep(545.0, 610.0, np.abs(X)) + sstep(-330.0, -380.0, Y) * sstep(430.0, 470.0, np.abs(X))
    grass = np.clip(outer, 0, 1) * sstep(0.56, 0.72, nz.fbm(55.0, 5)) * (1.0 - 0.9 * under_cherry)
    grass *= sstep(18.0, 40.0, d_edge)
    # A: petals (P4 gap 10) - a density mask of Gaussian lobes round every cherry, a drift lobe towards the board and
    # the colonnade flower beds; the even confetti elsewhere is scaled by petalGlobal
    base = _rule(rules, "petalGlobal", 1.0) * (0.05 + 0.06 * (nz.fbm(60.0, 6) - 0.5))
    lobes = np.zeros_like(X)
    tree_r, drift = _rule(rules, "petalTreeRadiusUU", 125.0), _rule(rules, "petalDrift", 0.55)
    for p in props_of(layout, "Cherry"):
        cx, cy = p["loc"][0], p["loc"][1]
        lobes = lobes + np.exp(-((np.hypot(X - cx, Y - cy) / (tree_r * p["scale"])) ** 2))
        dx = -math.copysign(120.0, cx) if cx else 0.0
        lobes = lobes + drift * np.exp(-((np.hypot(X - (cx + dx), Y - (cy + 40.0)) / 150.0) ** 2))
    beds = inside(np.abs(Y + 392.0) - 10.0 + 6.0 * warp, 8.0) * (np.abs(X) < 405.0)
    lobes = lobes + _rule(rules, "petalBeds", 0.3) * beds * sstep(0.4, 0.6, nz.fbm(24.0, 7))
    petals = np.clip(base + lobes, 0.0, 1.0) * (0.8 + 0.2 * nz.fbm(9.0, 8, 2))
    zero = np.zeros_like(X)
    return {"R": moss, "G": grass, "B": pave, "A": petals, "W": zero, "F": zero, "E": curb, "D": zero,
            "debug": {"paveEdge": d_pave_t, "cherry": d_cherry}}


def river_tubes(params: dict, tray) -> tuple[list, list]:
    """Sarpedon: the river continues beyond the frame - N to the far tray edge (widening mouth), S to the near edge
    (waterfall). x-runs at the map edges come from ground-params.json 'river' (measured on the illustration)."""
    riv = params["maps"]["sarpedon"]["river"]
    fa, fb = riv["farEdgeX"]
    na, nb = riv["nearEdgeX"]
    _, ty0, _, ty1 = tray
    fc, fr = (fa + fb) / 2, (fb - fa) / 2
    nc, nr = (na + nb) / 2, (nb - na) / 2
    far = ([(fc, -MY + 12.0), (fc + 12.0, -FY - 90.0), (fc + 40.0, ty0 - 30.0)], [fr, fr * 1.3, fr * 1.9])
    near = ([(nc, MY - 12.0), (nc - 8.0, FY + 50.0), (nc - 14.0, ty1 + 30.0)], [nr, nr * 1.05, nr * 1.12])
    return far, near


def rules_sarpedon(X, Y, layout: dict, tray, nz: Noise, params: dict, rules: dict | None = None) -> dict:
    rules = rules or {}
    tx0, ty0, tx1, ty1 = tray
    d_edge = -sd_box(X, Y, tx0, ty0, tx1, ty1)
    warp = nz.signed(40.0, 1)
    fine = nz.signed(12.0, 2, 2)
    en = _rule(rules, "edgeNoise", 1.0)  # P4 gap 5: scales the border noise of the sand regions
    far, near = river_tubes(params, tray)
    d_rf = sd_tube(X, Y, *far)
    d_rn = sd_tube(X, Y, *near)
    d_river = np.minimum(d_rf, d_rn)
    # B: ship deck - E band (from under the frame), quay N-E east of the river mouth, quay S-E; straight plank ends
    big = 1e4
    d_deck = np.minimum.reduce([
        sd_box(X, Y, FX - 2.0, -big, big, big),
        sd_box(X, Y, 400.0, -big, big, -FY + 10.0),
        sd_box(X, Y, 120.0, FY - 10.0, big, big),
    ])
    deck = inside(d_deck + 1.5 * fine, 1.5)
    # E (aux B): the beam where the planks end - a band just inside the deck border
    bw = _rule(rules, "beamWidthUU", 0.0)
    beam = inside(np.abs(d_deck + bw / 2.0) - bw / 2.0, 0.8) if bw > 0 else np.zeros_like(X)
    # R: sand - beach N-centre, river banks, the S bank round the waterfall, fire clearings, fort dust
    beach = inside(sd_box(X, Y, -300.0, -big, 420.0, -FY + 10.0) + 35.0 * en * warp, 18.0)
    sband = inside(sd_box(X, Y, -345.0, FY - 10.0, 160.0, big) + 25.0 * en * warp, 14.0)
    banks = inside(d_river - 48.0 + 14.0 * en * warp, 12.0)
    fires = np.zeros_like(X)
    f_r, f_w, f_s = _rule(rules, "fireRadiusUU", 58.0), _rule(rules, "fireWarpUU", 14.0), _rule(rules, "fireSoftUU", 10.0)
    f_peak = _rule(rules, "firePeak", 0.85)
    for p in props_of(layout, "Campfire"):
        fires = np.maximum(fires, f_peak * inside(sd_circle(X, Y, p["loc"][0], p["loc"][1], f_r * p["scale"])
                                                  + f_w * warp + 4.0 * fine, f_s))
    fort = np.zeros_like(X)
    for p in props_of(layout, "FortRuin"):
        fort = np.maximum(fort, 0.6 * inside(sd_circle(X, Y, p["loc"][0], p["loc"][1], 115.0) + 30.0 * warp, 20.0))
    sand = np.maximum.reduce([beach, sband, banks, fires, fort])
    # W / D / F (aux R / A / G): water in both river mouths (P4 gap 1), its depth and the foam on the shore + the surf
    d_w = d_river + _rule(rules, "waterWarpUU", 6.0) * warp + 2.0 * fine
    inset = _rule(rules, "waterInsetUU", 3.0)
    water = inside(d_w + inset, 2.0)
    depth = np.clip(-(d_w + inset) / max(_rule(rules, "depthUU", 30.0), 1.0), 0.0, 1.0)
    fw = _rule(rules, "foamWidthUU", 6.0)
    foam = (inside(np.abs(d_w + inset + fw / 2.0) - fw / 2.0, 1.2) * _rule(rules, "foamShore", 1.0)
            * sstep(0.4, 0.75, nz.fbm(14.0, 10)))
    sea = sstep(-FY - 20.0, -FY - 80.0, Y)  # the far mouth opens into the sea at the far tray edge
    for row in rules.get("surf", []):
        dist, width, amp = (float(v) for v in row)
        line = inside(np.abs(Y - ty0 - dist + 9.0 * warp + 3.0 * fine) - width / 2.0, 1.0) * amp
        foam = np.maximum(foam, line * water * sea * sstep(0.2, 0.5, nz.fbm(18.0, 11)))
    # G: pebbles - a thin rim round the water (the bed under it), pebbly banks, fort rubble, a scatter on the beach
    rim = inside(d_w - _rule(rules, "pebbleRimUU", 9.0), 3.0)
    bank_peb = inside(d_river - 22.0 + 10.0 * warp, 8.0) * sstep(0.42, 0.6, nz.fbm(30.0, 3))
    rubble = np.zeros_like(X)
    for p in props_of(layout, "FortRuin"):
        rubble = np.maximum(rubble, inside(sd_circle(X, Y, p["loc"][0], p["loc"][1], 95.0) + 25.0 * warp, 15.0)
                            * sstep(0.5, 0.7, nz.fbm(26.0, 4)) * 0.8)
    scatter = beach * sstep(0.72, 0.86, nz.fbm(28.0, 5)) * _rule(rules, "beachScatter", 0.6)
    gravel = np.maximum.reduce([rim, _rule(rules, "bankPebbles", 0.85) * bank_peb, 0.9 * rubble, scatter])
    # A: wetness - the channels, a falloff over the banks, sea spray along the far edge on the beach
    wet = np.where(d_river <= 0, 1.0, np.exp(-np.maximum(d_river, 0.0) / 38.0))
    spray = 0.35 * np.exp(-np.maximum(d_edge, 0.0) / 55.0) * beach * (Y < 0)
    wet = np.clip(np.maximum(wet, spray) * (0.82 + 0.18 * nz.fbm(10.0, 6, 2)), 0.0, 1.0)
    return {"R": sand, "G": gravel, "B": deck, "A": wet, "W": water, "F": foam, "E": beam, "D": depth,
            "debug": {"river": d_river, "deck": d_deck, "farTube": far, "nearTube": near}}


# ------------------------------------------------------------------------------------------------ generation
def ensure_kit_sizes() -> list[str]:
    """The prop footprints (layout_check.footprint) use the processed sizes of the env kit build reports when they are
    present - load them once, so generate() gives the same bytes from every entry point."""
    if not lc.PROCESSED:
        return lc.kit_crosscheck(lc.BUILD_REPORTS if lc.BUILD_REPORTS.exists() else None)
    return []


def _png(arr: np.ndarray) -> bytes:
    buf = io.BytesIO()
    Image.fromarray(arr, "RGBA").save(buf, format="PNG", compress_level=9)
    return buf.getvalue()


def waterfalls(key: str, params: dict, res: dict) -> list[dict]:
    """The layout 'ground.waterfalls' of a map (ground-params 'water.falls'): x-run = the water of the aux mask on the
    row just inside the near tray edge (the longest run >= 0.5, so the fall lines up with the painted river through the
    river tube), shrunk by insetUU; y = the near tray edge + offsetUU (in front of the T2 overhang, <= 30 uu)."""
    falls = (params["maps"][key].get("water") or {}).get("falls") or []
    out = []
    tx0, ty0, tx1, ty1 = res["tray"]
    W = res["channels"]["W"]
    X, Y = res["X"], res["Y"]
    root = params["ground"]["materialRoot"]
    for f in falls:
        if f.get("river", "near") != "near":
            raise SystemExit(f"{key}: waterfall {f.get('id')!r}: only river 'near' (the near tray edge) is supported")
        j = int(np.argmin(np.abs(Y[:, 0] - (ty1 - 3.0))))
        row = W[j] >= 0.5
        best, start = (0, -1, -1), None
        for i, v in enumerate(list(row) + [False]):
            if v and start is None:
                start = i
            elif not v and start is not None:
                if i - start > best[0]:
                    best = (i - start, start, i - 1)
                start = None
        if best[0] == 0:
            raise SystemExit(f"{key}: waterfall {f.get('id')!r}: no water at the near tray edge (y {ty1 - 3.0})")
        half_px = (X[0, 1] - X[0, 0]) / 2.0
        inset = float(f.get("insetUU", 0.0))
        x0, x1 = X[j, best[1]] - half_px + inset, X[j, best[2]] + half_px - inset
        out.append({"id": str(f["id"]), "material": f"{root}/MI_EnvWaterfall_{MAPS[key]}",
                    "x0": round(float(x0), 1), "x1": round(float(x1), 1),
                    "y": round(float(ty1 + float(f.get("offsetUU", 30.0))), 1),
                    "topZ": float(f.get("topZ", 2.5)), "dropUU": float(f.get("dropUU", 200.0)),
                    "spillUU": float(f.get("spillUU", 0.0))})
    return out


def generate(key: str, params: dict, layout: dict) -> dict:
    ensure_kit_sizes()
    rect = splat_rect(params, layout)
    size = tuple(int(v) for v in params["splat"]["size"])
    X, Y = grid(rect, size)
    nz = Noise(X, Y, SEEDS[key])
    tray = tray_rect(params["tray"])
    rules = params["maps"][key].get("rules") or {}
    ch = (rules_marmoreal(X, Y, layout, tray, nz, rules) if key == "marmoreal"
          else rules_sarpedon(X, Y, layout, tray, nz, params, rules))
    # P4: blur per channel (uu -> px on each axis); the depth follows the water
    blur = rules.get("blurUU") or {}
    upx = ((rect[2] - rect[0]) / size[0], (rect[3] - rect[1]) / size[1])
    for c in ("R", "G", "B", "A", "W", "F", "E", "D"):
        b = float(blur.get("W" if c == "D" else c, 0.0))
        if b > 0:
            ch[c] = np.clip(gauss_blur(ch[c], (b / upx[0], b / upx[1])), 0.0, 1.0)
    rgb = np.clip(np.rint(np.stack([ch["R"], ch["G"], ch["B"]], axis=-1) * 255.0), 0, 255)
    # A is stored as 1 + a * 254 (never 0): UE's PNG import may infill the RGB of zero-alpha pixels
    # (TextureImporter FillPNGZeroAlpha); M_EnvGround decodes a = saturate((A * 255 - 1) / 254).
    alpha = 1.0 + np.rint(np.clip(ch["A"], 0.0, 1.0) * 254.0)
    arr = np.concatenate([rgb, alpha[..., None]], axis=-1).astype(np.uint8)
    png = _png(arr)
    # the aux mask: R water, G foam, B edge band, A = 1 + depth * 254 (the same never-zero alpha rule)
    aux_rgb = np.clip(np.rint(np.stack([ch["W"], ch["F"], ch["E"]], axis=-1) * 255.0), 0, 255)
    aux_a = 1.0 + np.rint(np.clip(ch["D"], 0.0, 1.0) * 254.0)
    aux = np.concatenate([aux_rgb, aux_a[..., None]], axis=-1).astype(np.uint8)
    aux_png = _png(aux)
    res = {"key": key, "rect": rect, "size": size, "X": X, "Y": Y, "channels": ch, "array": arr, "png": png,
           "sha256": sha256_bytes(png), "tray": tray, "aux": aux, "auxPng": aux_png, "auxSha256": sha256_bytes(aux_png)}
    res["falls"] = waterfalls(key, params, res)
    return res


def stacked_weights(r, g, b, h=(0.5, 0.5, 0.5), contrast: float = 0.25, blend=(1.0, 1.0, 1.0)):
    """The M_EnvGround 'GroundWeights' node: height-lerp coverage of L1..L3 stacked over L0 (L3 on top); blend =
    L1..L3_HeightBlend (0: a plain soft lerp, 1: the layer's high points come first)."""
    c = max(contrast, 0.02)
    hh = [0.5 + (h[k] - 0.5) * blend[k] for k in range(3)]
    a1 = np.clip((hh[0] - 1.0 + r * (1.0 + c)) / c, 0, 1)
    a2 = np.clip((hh[1] - 1.0 + g * (1.0 + c)) / c, 0, 1)
    a3 = np.clip((hh[2] - 1.0 + b * (1.0 + c)) / c, 0, 1)
    w3 = a3
    w2 = a2 * (1 - a3)
    w1 = a1 * (1 - a2) * (1 - a3)
    w0 = (1 - a1) * (1 - a2) * (1 - a3)
    return w0, w1, w2, w3


def decode(arr: np.ndarray) -> np.ndarray:
    """RGBA8 splat / aux -> float (R, G, B, and A with the 1 + a * 254 encoding undone)."""
    a = arr.astype(float) / 255.0
    a[..., 3] = np.clip((arr[..., 3].astype(float) - 1.0) / 254.0, 0.0, 1.0)
    return a


def coverage(res: dict, params: dict) -> dict:
    X, Y = res["X"], res["Y"]
    tx0, ty0, tx1, ty1 = res["tray"]
    ground = (X >= tx0) & (X <= tx1) & (Y >= ty0) & (Y <= ty1) & ((np.abs(X) > FX) | (np.abs(Y) > FY))
    a = decode(res["array"])
    w = stacked_weights(a[..., 0], a[..., 1], a[..., 2], contrast=params["material"]["heightContrast"])
    out = {f"L{i}": round(float(w[i][ground].mean()), 4) for i in range(4)}
    out["accentMean"] = round(float(a[..., 3][ground].mean()), 4)
    aux = decode(res["aux"])
    out["water"] = round(float(aux[..., 0][ground].mean()), 4)
    out["foam"] = round(float(aux[..., 1][ground].mean()), 4)
    out["edge"] = round(float(aux[..., 2][ground].mean()), 4)
    out["groundPixels"] = int(ground.sum())
    return out


# ------------------------------------------------------------------------------------------------ preview
FALSE = {
    "marmoreal": [(58, 40, 30), (70, 110, 60), (120, 160, 80), (205, 205, 210)],
    "sarpedon": [(60, 75, 45), (215, 190, 130), (120, 125, 130), (130, 85, 50)],
}
ACCENT_FALSE = {"marmoreal": (245, 150, 190), "sarpedon": (60, 110, 200)}


def _font(size: int):
    for name in ("arial.ttf", "DejaVuSans.ttf"):
        try:
            return ImageFont.truetype(name, size)
        except OSError:
            continue
    return ImageFont.load_default()


def srgb_to_lin(c):
    c = np.asarray(c, float)
    return np.where(c <= 0.04045, c / 12.92, ((c + 0.055) / 1.055) ** 2.4)


def lin_to_srgb(c):
    c = np.clip(c, 0, 1)
    return np.where(c <= 0.0031308, c * 12.92, 1.055 * np.power(c, 1 / 2.4) - 0.055)


def _set_tex(raw_root: Path, set_id: str, rot90: bool, px: int = 512):
    """Colour (linear) and normalised height of a raw CC0 set, downsampled (preview only)."""
    col = Image.open(raw_root / set_id / f"{set_id}_2K-JPG_Color.jpg").convert("RGB").resize((px, px), Image.BILINEAR)
    dsp = Image.open(raw_root / set_id / f"{set_id}_2K-JPG_Displacement.jpg").convert("L").resize((px, px),
                                                                                                   Image.BILINEAR)
    c = srgb_to_lin(np.asarray(col, float) / 255.0)
    h = np.asarray(dsp, float) / 255.0
    lo, hi = np.percentile(h, 1), np.percentile(h, 99)
    h = np.clip((h - lo) / max(hi - lo, 1e-3), 0, 1)
    if rot90:
        c, h = np.rot90(c, 1), np.rot90(h, 1)
    return c, h


def _draw_overlay(img: Image.Image, res: dict, layout: dict, to_px, font, light: bool) -> None:
    d = ImageDraw.Draw(img, "RGBA")
    ink = (255, 255, 255, 230) if light else (20, 20, 20, 230)
    # frame + map placeholder (no original-map pixels: ENV-U3 / ENV-U7)
    d.rectangle([*to_px(-FX, -FY), *to_px(FX, FY)], fill=(72, 48, 30, 255))
    d.rectangle([*to_px(-MX, -MY), *to_px(MX, MY)], fill=(46, 46, 50, 255))
    cx, cy = to_px(0, 0)
    d.text((cx - 40, cy - 10), "MAP (not drawn)", fill=(200, 200, 200, 255), font=font)
    tx0, ty0, tx1, ty1 = res["tray"]
    d.rectangle([*to_px(tx0, ty0), *to_px(tx1, ty1)], outline=(255, 210, 90, 255), width=2)
    for p in layout.get("props", []):
        if not lc.mesh_name(p):
            continue
        poly = [to_px(*q) for q in lc.footprint(p)]
        d.polygon(poly, outline=ink)
        x, y = to_px(*p["loc"][:2])
        d.text((x + 3, y - 6), p["id"], fill=ink, font=font)
    for lt in layout.get("lights", []):
        x, y = to_px(*lt["loc"][:2])
        d.ellipse([x - 3, y - 3, x + 3, y + 3], outline=(255, 190, 90, 255), width=2)
    for f in res.get("falls", []):  # waterfall cards: the spill (dashed box) and the fall line at y
        d.rectangle([*to_px(f["x0"], f["y"] - f["spillUU"]), *to_px(f["x1"], f["y"])], outline=(120, 220, 255, 255))
        d.line([to_px(f["x0"], f["y"]), to_px(f["x1"], f["y"])], fill=(120, 220, 255, 255), width=3)
        x, y = to_px(f["x1"], f["y"])
        d.text((x + 4, y - 12), f"{f['id']} drop {f['dropUU']:g}", fill=(120, 220, 255, 255), font=font)


def preview(res: dict, params: dict, layout: dict, out_png: Path) -> dict:
    key = res["key"]
    x0, y0, x1, y1 = res["rect"]
    W = int(round((x1 - x0) / PREVIEW_UU_PER_PX))
    H = int(round((y1 - y0) / PREVIEW_UU_PER_PX))
    Xp, Yp = grid(res["rect"], (W, H))
    # per channel (an RGBA resize in PIL premultiplies by alpha and would erase the layers where A is low)
    a = decode(np.stack([np.asarray(Image.fromarray(res["array"][..., k], "L").resize((W, H), Image.BILINEAR))
                         for k in range(4)], axis=-1))
    r, g, b, acc = a[..., 0], a[..., 1], a[..., 2], a[..., 3]
    x_aux = decode(np.stack([np.asarray(Image.fromarray(res["aux"][..., k], "L").resize((W, H), Image.BILINEAR))
                             for k in range(4)], axis=-1))
    wat, foam, edge, depth = x_aux[..., 0], x_aux[..., 1], x_aux[..., 2], x_aux[..., 3]
    contrast = params["material"]["heightContrast"]
    mp = params["maps"][key]
    font = _font(11)

    def to_px(x, y):
        return (int(round((x - x0) / PREVIEW_UU_PER_PX)), int(round((y - y0) / PREVIEW_UU_PER_PX)))

    # panel 1: false colour
    w = stacked_weights(r, g, b, contrast=contrast)
    fc = sum(w[i][..., None] * np.array(FALSE[key][i], float) for i in range(4))
    fc = fc * (1 - 0.6 * acc[..., None]) + 0.6 * acc[..., None] * np.array(ACCENT_FALSE[key], float)
    fc = fc * (1 - 0.55 * edge[..., None])  # curb / beam band darker
    fc = fc * (1 - wat[..., None]) + wat[..., None] * (np.array([60, 110, 210], float) * (1 - 0.5 * depth[..., None]))
    fc = fc * (1 - foam[..., None]) + foam[..., None] * 255.0
    top = Image.fromarray(np.clip(fc, 0, 255).astype(np.uint8), "RGB")
    _draw_overlay(top, res, layout, to_px, font, light=True)
    ImageDraw.Draw(top).text((6, 4), f"{MAPS[key]} splat: " + " | ".join(
        f"{lay.get('channel', 'base')} {lay['set']}" for lay in params["maps"][key]["layers"])
        + f" | A {params['maps'][key]['accent']['mode']} | aux: water blue, foam white, edge dark",
        fill=(255, 255, 255), font=_font(13))
    # panel 2: albedo preview with the raw CC0 textures
    raw_root = Path(params["cc0Raw"])
    note = ("albedo preview (CC0 textures at their tiling, tint / saturation / layer macro / accent / edge / water + "
            "foam; no lighting, no night grade, no ripples)")
    try:
        cols, hts = [], []
        for lay in params["maps"][key]["layers"]:
            c, h = _set_tex(raw_root, lay["set"], bool(params["sets"][lay["set"]].get("rotate90")))
            tile = float(lay["tileUU"])
            n = c.shape[0]
            ui = (np.floor((Xp / tile) % 1.0 * n).astype(int)) % n
            vi = (np.floor((Yp / tile) % 1.0 * n).astype(int)) % n
            col = c[vi, ui]
            luma = (col * np.array([0.2126, 0.7152, 0.0722])).sum(-1, keepdims=True)
            col = (luma + (col - luma) * float(lay["saturation"])) * np.array(lay["tint"], float)
            if float(lay.get("macro", 0.0)) > 0:  # LayerMacro (M_EnvGround graph 2): +-macro at layerMacroScaleUU
                lm = Noise(Xp, Yp, 78).signed(float(params["material"].get("layerMacroScaleUU", 33.0)), 2, 2)
                col = col * (1.0 + float(lay["macro"]) * lm[..., None])
            cols.append(col)
            hts.append(h[vi, ui])
        blend = tuple(float(lay.get("heightBlend", 1.0)) for lay in params["maps"][key]["layers"][1:])
        w = stacked_weights(r, g, b, (hts[1], hts[2], hts[3]), contrast, blend)
        alb = sum(w[i][..., None] * cols[i] for i in range(4))
        m = params["material"]
        macro = Noise(Xp, Yp, 77).signed(float(m["macroScaleUU"]), 1, 2)
        alb = alb * (1.0 + float(m["macroStrength"]) * macro[..., None])
        ac = params["maps"][key]["accent"]
        acol = np.array(ac["color"], float)
        if float(ac.get("petalSizeUU", 0)) > 0:
            # the M_EnvGround petal model: a darkened pink carpet under dense petals + one jittered petal per cell
            carpet = (np.clip(acc * 1.5 - 0.3, 0, 1) * float(ac.get("carpet", 0.0)))[..., None]
            alb = alb * (1 - carpet) + carpet * acol * 0.5
            specks = petal_specks(Xp, Yp, acc * float(ac["opacity"]), float(ac["petalSizeUU"]))
            alb = alb * (1 - specks[..., None]) + specks[..., None] * acol
        else:
            k = (acc * float(ac["opacity"]))[..., None]
            alb = alb * (1 - k) + alb * acol * k
        if mp.get("edge"):
            e = (edge * float(mp["edge"].get("strength", 1.0)))[..., None]
            alb = alb * (1 - e + e * np.array(mp["edge"]["color"], float))
        if mp.get("water"):
            wp = mp["water"]
            wc = srgb_to_lin(np.array(wp["colorSrgb"], float) / 255.0)
            shallow = alb * (1 - float(wp["shallowMix"])) + wc * float(wp["shallowMix"])
            wcol = shallow * (1 - depth[..., None]) + wc * depth[..., None]
            alb = alb * (1 - wat[..., None]) + wcol * wat[..., None]
            fo = np.clip(foam * float(wp["foamOpacity"]), 0, 1)[..., None]
            alb = alb * (1 - fo) + fo * np.array(wp["foamColor"], float)
        bot = Image.fromarray((lin_to_srgb(alb) * 255).astype(np.uint8), "RGB")
    except (OSError, KeyError) as exc:
        bot = Image.new("RGB", (W, H), (30, 30, 30))
        note = f"albedo preview unavailable ({type(exc).__name__}: {exc})"
    _draw_overlay(bot, res, layout, to_px, font, light=True)
    ImageDraw.Draw(bot).text((6, 4), note, fill=(255, 255, 255), font=_font(13))
    sheet = Image.new("RGB", (W, 2 * H + 4), (0, 0, 0))
    sheet.paste(top, (0, 0))
    sheet.paste(bot, (0, H + 4))
    buf = io.BytesIO()
    sheet.save(buf, format="PNG", compress_level=9)
    out_png.write_bytes(buf.getvalue())
    return {"path": rel(out_png), "sha256": sha256_bytes(buf.getvalue()), "size": [W, 2 * H + 4],
            "uuPerPx": PREVIEW_UU_PER_PX}


def _hash12(px, py):
    """Dave Hoskins 'hash without sine' (the same as the M_EnvGround Custom HLSL)."""
    p3x, p3y, p3z = (px * 0.1031) % 1.0, (py * 0.1031) % 1.0, (px * 0.1031) % 1.0
    dd = p3x * (p3y + 33.33) + p3y * (p3z + 33.33) + p3z * (p3x + 33.33)
    p3x, p3y, p3z = p3x + dd, p3y + dd, p3z + dd
    return ((p3x + p3y) * p3z) % 1.0


def petal_specks(X, Y, density, size_uu: float):
    """CPU mirror of the petal specks of M_EnvGround (one jittered ellipse per cell, 3 x 3 neighbourhood)."""
    qx, qy = X / size_uu, Y / size_uu
    bx, by = np.floor(qx), np.floor(qy)
    out = np.zeros_like(X)
    for dy in (-1, 0, 1):
        for dx in (-1, 0, 1):
            cx, cy = bx + dx, by + dy
            jx, jy = _hash12(cx, cy), _hash12(cx + 19.19, cy + 7.7)
            pick = _hash12(cx + 47.3, cy + 11.1)
            ang = _hash12(cx + 3.1, cy + 91.7) * 6.2831853
            ox, oy = qx - (cx + 0.15 + 0.7 * jx), qy - (cy + 0.15 + 0.7 * jy)
            lx = ox * np.cos(ang) + oy * np.sin(ang)
            ly = -ox * np.sin(ang) + oy * np.cos(ang)
            e = (lx / 0.36) ** 2 + (ly / 0.2) ** 2
            out = np.maximum(out, sstep(1.0, 0.55, e) * (pick < density))
    return out


# ------------------------------------------------------------------------------------------------ layout section
def ground_section(key: str, params: dict, res: dict, png_path: Path) -> dict:
    g = params["ground"]
    x0, y0, x1, y1 = res["rect"]
    aux_path = Path(png_path).with_name(f"{key}.aux.png")
    sec = {
        "mode": g["mode"],
        "material": f"{g['materialRoot']}/MI_EnvGround_{MAPS[key]}",
        "z": float(g["z"]),
        "frameOverlapUU": float(g["frameOverlapUU"]),
        "insetUU": float(g["insetUU"]),
        "splatRect": [float(x0), float(y0), float(x1), float(y1)],
        "splat": rel(png_path),
        "splatSha256": res["sha256"],
        "aux": rel(aux_path),
        "auxSha256": res["auxSha256"],
    }
    if res.get("falls"):
        sec["waterfalls"] = [dict(f) for f in res["falls"]]
    sec["notes"] = ("ENV-U10 themed ground (tools/art/env_kit/ground_splat.py, ground-params.json): runtime = four "
                    "/Engine/BasicShapes/Plane strips = tray top minus the frame (hole = frame outer - frameOverlapUU, "
                    "outer = tray top - insetUU) at z, NoCollision, no shadow casting; material MI_EnvGround_<Map> "
                    "(tools/art/env_kit/ue_import_env_ground.py) gets GroundStrip / SplatRect per strip (MID); the aux "
                    "mask (water / foam / edge band / depth) is bound in the MI. P4 waterfalls (S08EnvGround): per "
                    "entry a vertical engine-plane card x0..x1 at y from topZ down dropUU plus a flat spill (y - "
                    "spillUU .. y at topZ) over the T2 lip, MI_EnvWaterfall_<Map>, no collision, no shadow.")
    return sec


# S08EnvGroundSpec waterfall limits (S08EnvGround.h): the C++ parser rejects the whole layout outside them
FALL_MAX = 4
FALL_TOP_Z = (-3.0, 20.0)      # inclusive
FALL_MAX_DROP_UU = 1000.0      # (0, max]
FALL_MAX_SPILL_UU = 200.0      # [0, max]
FALL_MAX_WIDTH_UU = 2000.0


def validate_waterfalls(key: str, falls, tray) -> list[str]:
    """The layout 'ground.waterfalls' against the S08EnvGround parse rules and the tray (the card stands in front of
    the near tray edge, within the T2 overhang + 40 uu)."""
    if falls is None:
        return []
    if not isinstance(falls, list):
        return [f"{key}: ground.waterfalls is not an array"]
    errs, ids = [], set()
    if len(falls) > FALL_MAX:
        errs.append(f"{key}: {len(falls)} waterfalls > {FALL_MAX}")
    for f in falls:
        if not isinstance(f, dict):
            errs.append(f"{key}: a waterfall is not an object")
            continue
        fid = f.get("id")
        if not isinstance(fid, str) or not fid or fid in ids:
            errs.append(f"{key}: waterfall id {fid!r} empty or duplicate")
        ids.add(fid)
        num = {k: f.get(k) for k in ("x0", "x1", "y", "topZ", "dropUU", "spillUU")}
        if not all(isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v) for v in num.values()):
            errs.append(f"{key}: waterfall {fid}: x0 / x1 / y / topZ / dropUU / spillUU must be numbers")
            continue
        if not 0.0 < num["x1"] - num["x0"] <= FALL_MAX_WIDTH_UU:
            errs.append(f"{key}: waterfall {fid}: width x1 - x0 not in (0, {FALL_MAX_WIDTH_UU:g}]")
        if not FALL_TOP_Z[0] <= num["topZ"] <= FALL_TOP_Z[1]:
            errs.append(f"{key}: waterfall {fid}: topZ not in [{FALL_TOP_Z[0]:g}, {FALL_TOP_Z[1]:g}]")
        if not 0.0 < num["dropUU"] <= FALL_MAX_DROP_UU:
            errs.append(f"{key}: waterfall {fid}: dropUU not in (0, {FALL_MAX_DROP_UU:g}]")
        if not 0.0 <= num["spillUU"] <= FALL_MAX_SPILL_UU:
            errs.append(f"{key}: waterfall {fid}: spillUU not in [0, {FALL_MAX_SPILL_UU:g}]")
        tx0, ty0, tx1, ty1 = tray
        if not (ty1 <= num["y"] <= ty1 + 40.0) or num["x0"] < tx0 or num["x1"] > tx1:
            errs.append(f"{key}: waterfall {fid}: not at the near tray edge (y {num['y']} vs {ty1}, x {num['x0']}..{num['x1']})")
        if num["y"] - num["spillUU"] > ty1 or num["y"] - num["spillUU"] < ty1 - 120.0:
            errs.append(f"{key}: waterfall {fid}: the spill {num['y'] - num['spillUU']}..{num['y']} does not start on the tray top near its edge")
        if not isinstance(f.get("material"), str) or not f["material"].startswith("/Game/EnvKit/Ground/MI_EnvWaterfall_"):
            errs.append(f"{key}: waterfall {fid}: material {f.get('material')!r} is not /Game/EnvKit/Ground/MI_EnvWaterfall_<Map>")
    return errs


def write_layout_ground(layout_path: Path, section: dict) -> bool:
    """Read-modify-write of one key (keeps key order and the 2-space format of the layouts). True if changed."""
    raw = layout_path.read_bytes()
    doc = json.loads(raw.decode("utf-8"))
    if doc.get("ground") == section:
        return False
    out = {}
    for k, v in doc.items():
        if k == "ground":
            continue
        if k == "notes":
            out["ground"] = section
        out[k] = v
    if "ground" not in out:
        out["ground"] = section
    text = json.dumps(out, indent=2, ensure_ascii=False) + "\n"
    if layout_path.read_bytes() != raw:  # changed under us (another track): refuse, the caller re-runs
        raise RuntimeError(f"{layout_path} changed while it was being updated - re-run")
    layout_path.write_bytes(text.encode("utf-8"))
    return True


def check_layout_ground(key: str, layout: dict, res: dict, params: dict) -> list[str]:
    errs = []
    g = layout.get("ground")
    if not isinstance(g, dict):
        return [f"{key}: layout has no 'ground' section (run with --write-layouts)"]
    want = ground_section(key, params, res, Path(REPO / g.get("splat", "")))
    for k in ("mode", "material", "z", "frameOverlapUU", "insetUU", "splatRect", "splatSha256", "aux", "auxSha256"):
        if g.get(k) != want[k]:
            errs.append(f"{key}: layout ground.{k} = {g.get(k)!r}, generator gives {want[k]!r}")
    if g.get("waterfalls") != want.get("waterfalls"):
        errs.append(f"{key}: layout ground.waterfalls = {g.get('waterfalls')!r}, generator gives {want.get('waterfalls')!r}")
    errs += validate_waterfalls(key, g.get("waterfalls"), res["tray"])
    return errs


# ------------------------------------------------------------------------------------------------ entry
AUX_CHANNELS = {"R": "water coverage (river mouths)", "G": "foam (shore band, surf)",
                "B": "edge band (Marmoreal curb / Sarpedon deck beam)", "A": "1 + water depth * 254"}


def compare_png(key: str, path: Path, sha: str, arr: np.ndarray) -> list[str]:
    """--check: the committed PNG against the regenerated array (<= 1 LSB of float drift is accepted)."""
    if not path.is_file():
        return [f"{key}: {rel(path)} missing"]
    have = path.read_bytes()
    if sha256_bytes(have) == sha:
        return []
    old = np.asarray(Image.open(io.BytesIO(have)).convert("RGBA"), int)
    diff = int(np.abs(old - arr.astype(int)).max()) if old.shape == arr.shape else 999
    if diff > 1:
        return [f"{key}: {rel(path)} differs from the rules (max |diff| {diff}); re-run"]
    print(f"  {key}: {path.name} bytes differ by <= 1 LSB (float drift) - accepted")
    return []


def run(args) -> int:
    params = load_params(Path(args.params))
    out_dir = Path(args.out) if args.out else Path(args.params).resolve().parent
    out_dir.mkdir(parents=True, exist_ok=True)
    kit_msgs = ensure_kit_sizes()
    keys = [k.strip() for k in args.maps.split(",") if k.strip()]
    ok = True
    extents = Path(args.tray_extents) if args.tray_extents else TRAY_EXTENTS_SCRATCH
    for key in keys:
        if key not in MAPS:
            print(f"unknown map {key!r}")
            return 2
        layout_path = LAYOUT_DIR / f"{key}.layout.json"
        layout = json.loads(layout_path.read_text(encoding="utf-8"))
        res = generate(key, params, layout)
        png_path = out_dir / f"{key}.splat.png"
        aux_path = out_dir / f"{key}.aux.png"
        meta_path = out_dir / f"{key}.splat.json"
        notes = tray_notes(params, layout, extents)
        cov = coverage(res, params)
        x0, y0, x1, y1 = res["rect"]
        meta = {
            "schema": SCHEMA_META, "map": key, "tool": "tools/art/env_kit/ground_splat.py",
            "params": {"path": rel(Path(args.params)), "sha256": sha256_bytes(Path(args.params).read_bytes())},
            "layout": {"path": rel(layout_path), "propsSha256": props_hash(layout), "props": len(layout["props"])},
            "tray": dict(zip(("minX", "minY", "maxX", "maxY"), res["tray"])),
            "splatRect": [x0, y0, x1, y1], "size": list(res["size"]),
            "uuPerPx": [round((x1 - x0) / res["size"][0], 4), round((y1 - y0) / res["size"][1], 4)],
            "orientation": "row 0 = far side (-Y, UE texture V = 0), column 0 = -X; SplatUV = (P - rect.min) / rect.size",
            "channels": {lay.get("channel", "base"): f"{lay['slot']} {lay['set']} - {lay['role']}"
                         for lay in params["maps"][key]["layers"]},
            "accent": params["maps"][key]["accent"], "coverage": cov, "seed": SEEDS[key],
            "png": {"path": rel(png_path), "sha256": res["sha256"], "bytes": len(res["png"]), "format": "PNG RGBA8"},
            "aux": {"path": rel(aux_path), "sha256": res["auxSha256"], "bytes": len(res["auxPng"]),
                    "format": "PNG RGBA8", "channels": AUX_CHANNELS},
            "rules": params["maps"][key].get("rules") or {},
            "waterfalls": res["falls"],
            "kit": kit_msgs[:3], "notes": notes,
        }
        if args.check:
            errs = compare_png(key, png_path, res["sha256"], res["array"])
            errs += compare_png(key, aux_path, res["auxSha256"], res["aux"])
            if meta_path.is_file():
                m_old = json.loads(meta_path.read_text(encoding="utf-8"))
                for field, path in (("png", png_path), ("aux", aux_path)):
                    if (m_old.get(field) or {}).get("sha256") != (sha256_bytes(path.read_bytes()) if path.is_file() else None):
                        errs.append(f"{key}: {rel(meta_path)} {field}.sha256 does not match {rel(path)}")
                if m_old.get("waterfalls", []) != res["falls"]:
                    errs.append(f"{key}: {rel(meta_path)} waterfalls differ from the rules; re-run")
            else:
                errs.append(f"{key}: {rel(meta_path)} missing")
            if png_path.is_file() and aux_path.is_file():
                res_file = dict(res, sha256=sha256_bytes(png_path.read_bytes()),
                                auxSha256=sha256_bytes(aux_path.read_bytes()))
                errs += check_layout_ground(key, layout, res_file, params)
            for e in errs:
                print("  ERROR " + e)
            for n in notes:
                print("  note  " + n)
            print(f"== {key}: check {'OK' if not errs else 'FAILED'} (rect {res['rect']}, coverage {cov})")
            ok = ok and not errs
            continue
        png_path.write_bytes(res["png"])
        aux_path.write_bytes(res["auxPng"])
        if not args.no_preview:
            meta["preview"] = preview(res, params, layout, out_dir / f"{key}.preview.png")
        meta_path.write_bytes((json.dumps(meta, indent=1, ensure_ascii=False) + "\n").encode("utf-8"))  # LF
        changed = None
        if args.write_layouts:
            changed = write_layout_ground(layout_path, ground_section(key, params, res, png_path))
        print(f"== {key}: {rel(png_path)} {res['size'][0]}x{res['size'][1]} sha256 {res['sha256'][:16]} aux "
              f"{res['auxSha256'][:16]} rect {res['rect']} coverage {cov} waterfalls {res['falls']}"
              + ("" if changed is None else f" layout ground {'updated' if changed else 'unchanged'}"))
        for n in notes:
            print("  note  " + n)
    return 0 if ok else 1


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n", 1)[0])
    ap.add_argument("--maps", default="marmoreal,sarpedon")
    ap.add_argument("--params", default=str(PARAMS_DEFAULT))
    ap.add_argument("--out", default=None, help="output folder (default: the params folder)")
    ap.add_argument("--tray-extents", default=None, help="TRAY track extents JSON to compare with (warning only)")
    ap.add_argument("--no-preview", action="store_true")
    ap.add_argument("--write-layouts", action="store_true", help="(re)write the layouts' 'ground' sections")
    ap.add_argument("--check", action="store_true", help="regenerate in memory and compare; validate the layouts")
    return run(ap.parse_args(argv))


if __name__ == "__main__":
    sys.exit(main())
