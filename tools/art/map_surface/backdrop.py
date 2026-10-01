"""ENV-MAPS P5 track C (concept review gap 8): the procedural night backdrop of the map-image boards, world-free.

The board profile "backdrop" block (unreal/Unmatched/Config/ArtBoards/S08ArtBoardProfiles.json) is parsed and validated
by S08BoardArt.cpp (ParseBackdrop, S08BackdropPlacementProblem) and spawned by S08MapBackdrop.cpp; the two materials are
built out of git by ue_import_map_surface.py from the HLSL strings below. This module is the Python mirror of all of it:

  validate_block(block, map_half)   the parser's rules (tools/art/art_board_fixtures.py check uses it)
  BoardView / moon_card / mist_rect the K1 camera of AS08FlowGameMode::SetupCameraForBoard and the part placement
  MIST_HLSL / MOON_HLSL             Custom-node code of M_MapBackdropMist / M_MapBackdropMoon
  mist_density / moon_glow          numpy mirrors of that HLSL (statistics and the scratch mock, not a UE render)
  mock_far_view(...)                a crude far-zoom mock (tray box + mist + moon over the fog colour) for a sanity look

Status: предложено (numbers are proposals; the look is measured in UE frames by the integrate stage).

  python -B tools/art/map_surface/backdrop.py --check            # validate the shipped blocks + placement report
  python -B tools/art/map_surface/backdrop.py --mock <out dir>   # far-zoom mock PNGs (scratch, out of git)
"""
from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
PROFILES = REPO / "unreal" / "Unmatched" / "Config" / "ArtBoards" / "S08ArtBoardProfiles.json"

# ---- S08BoardArt.h S08MapSurfaceSpec mirrors
MAX_Z = -250.0          # BackdropMaxZ: every part below (the T2b tray bottom is about -216)
MIN_Z = -4000.0         # BackdropMinZ
MIN_LAYER_GAP = 100.0   # BackdropMinLayerGapUU
MAX_MIST = 2            # BackdropMaxMist
FAR_VIEW_RATIO = 0.65   # BackdropFarViewRatio = FS08CameraZoom::OverviewOutRatio
MIST_PATH = "/Game/EnvMaps/M_MapBackdropMist"
MOON_PATH = "/Game/EnvMaps/M_MapBackdropMoon"

MIST_DEFAULTS = {"centerUU": [0.0, 0.0], "halfUU": [1900.0, 1350.0], "colorLinear": [0.3, 0.38, 0.62], "opacity": 0.3,
                 "noiseScaleUU": 700.0, "panUUPerSec": [6.0, -3.0], "edgeFade": 0.3, "coverage": 0.5, "seed": 0.0}
MOON_DEFAULTS = {"screenAnchor": [-0.9, 0.82], "depthUU": 5200.0, "diameterUU": 1800.0, "colorLinear": [0.72, 0.8, 1.0],
                 "intensity": 1.0, "softness": 0.4, "discRadius": 0.06, "discIntensity": 2.0}

# ---- material graph parameters (S08MapSurfaceSpec::ParamBackdrop*) and their defaults in the UE materials
MIST_PARAMS = {"vector": {"Tint": (0.3, 0.38, 0.62, 1.0), "SizeUU": (3800.0, 2700.0, 0.0, 0.0), "PanUU": (6.0, -3.0, 0.0, 0.0)},
               "scalar": {"Opacity": 0.3, "NoiseScaleUU": 700.0, "EdgeFade": 0.3, "Coverage": 0.5, "Seed": 0.0}}
MOON_PARAMS = {"vector": {"Tint": (0.72, 0.8, 1.0, 1.0)},
               "scalar": {"Intensity": 1.0, "Softness": 0.4, "DiscRadius": 0.06, "DiscIntensity": 2.0}}

# Custom node 'MapBackdropMist' (CMOT_FLOAT1): inputs UV, Time, Size (.xy), Pan (.xy), NoiseScale, EdgeFade, Coverage, Seed.
# Three octaves of value noise (sin hash) in uu, panned by Pan * Time; coverage threshold; elliptic edge fade.
MIST_INPUTS = ("UV", "Time", "Size", "Pan", "NoiseScale", "EdgeFade", "Coverage", "Seed")
MIST_HLSL = """// ENV-MAPS P5 M_MapBackdropMist (tools/art/map_surface/backdrop.py mirrors it): mist density 0..1.
float2 q = (UV * Size.xy + Pan.xy * Time) / max(NoiseScale, 1.0) + Seed * float2(17.13, 31.71);
float n = 0.0;
float a = 0.5;
float norm = 0.0;
for (int i = 0; i < 3; ++i) {
  float2 ip = floor(q);
  float2 fp = frac(q);
  float2 w = fp * fp * (3.0 - 2.0 * fp);
  float h00 = frac(sin(dot(ip, float2(127.1, 311.7))) * 43758.5453);
  float h10 = frac(sin(dot(ip + float2(1.0, 0.0), float2(127.1, 311.7))) * 43758.5453);
  float h01 = frac(sin(dot(ip + float2(0.0, 1.0), float2(127.1, 311.7))) * 43758.5453);
  float h11 = frac(sin(dot(ip + float2(1.0, 1.0), float2(127.1, 311.7))) * 43758.5453);
  n += a * lerp(lerp(h00, h10, w.x), lerp(h01, h11, w.x), w.y);
  norm += a;
  q = float2(q.x * 1.6 - q.y * 1.2, q.x * 1.2 + q.y * 1.6) + float2(5.2, 1.3);
  a *= 0.5;
}
n /= norm;
float c = saturate(Coverage);
float d = smoothstep(1.0 - c - 0.15, 1.0 - c + 0.15, n);
float r = length((UV - 0.5) * 2.0);
float fade = 1.0 - smoothstep(1.0 - clamp(EdgeFade, 0.01, 1.0), 1.0, r);
return d * fade;
"""
# Custom node 'MapBackdropMoon' (CMOT_FLOAT3): inputs UV, Tint (.rgb), Intensity, Softness, DiscRadius, DiscIntensity.
MOON_INPUTS = ("UV", "Tint", "Intensity", "Softness", "DiscRadius", "DiscIntensity")
MOON_HLSL = """// ENV-MAPS P5 M_MapBackdropMoon (additive, unlit; tools/art/map_surface/backdrop.py mirrors it): soft glow + disc.
float r = length(UV * 2.0 - 1.0);
float s = max(Softness, 0.02);
float glow = exp(-(r * r) / (s * s)) * saturate((1.0 - r) * 5.0);
float disc = step(0.0001, DiscRadius) * (1.0 - smoothstep(DiscRadius * 0.85, DiscRadius + 0.0001, r));
return Tint.rgb * (max(Intensity, 0.0) * glow + max(DiscIntensity, 0.0) * disc);
"""


# ------------------------------------------------------------------------------------------------ camera mirror
def k1_fit_distance(half: tuple[float, float]) -> float:
    """S08K1FitDistanceUU (hfov 35, 16:9, pitch 55, margin 60, x1.12)."""
    half_h = math.tan(math.radians(17.5))
    half_v = half_h / (16.0 / 9.0)
    need_v = (half[1] * math.sin(math.radians(55.0)) + 60.0) / half_v
    need_h = (half[0] + 60.0) / half_h
    return max(need_v, need_h) * 1.12


def far_view_distance(half: tuple[float, float]) -> float:
    return k1_fit_distance(half) / FAR_VIEW_RATIO


class BoardView:
    """FS08BoardView: camera (0, D cos 55, D sin 55), FRotator(-55, -90, 0); NDC x right, y up."""

    def __init__(self, distance: float):
        p, y = math.radians(-55.0), math.radians(-90.0)
        self.loc = (0.0, distance * math.cos(math.radians(55.0)), distance * math.sin(math.radians(55.0)))
        self.f = (math.cos(p) * math.cos(y), math.cos(p) * math.sin(y), math.sin(p))
        self.r = (-math.sin(y), math.cos(y), 0.0)
        self.u = (-math.sin(p) * math.cos(y), -math.sin(p) * math.sin(y), math.cos(p))
        self.tan_h = math.tan(math.radians(17.5))
        self.tan_v = self.tan_h / (16.0 / 9.0)

    def project(self, w) -> tuple[float, float] | None:
        d = [w[i] - self.loc[i] for i in range(3)]
        depth = sum(d[i] * self.f[i] for i in range(3))
        if depth <= 1e-6:
            return None
        return (sum(d[i] * self.r[i] for i in range(3)) / (depth * self.tan_h),
                sum(d[i] * self.u[i] for i in range(3)) / (depth * self.tan_v))

    def ray(self, ndc) -> tuple[float, float, float]:
        v = [self.f[i] + self.r[i] * ndc[0] * self.tan_h + self.u[i] * ndc[1] * self.tan_v for i in range(3)]
        n = math.sqrt(sum(x * x for x in v))
        return tuple(x / n for x in v)


def moon_card(moon: dict, half: tuple[float, float]) -> dict:
    """S08BackdropMoonTransform: centre, the card axes (local X = screen right, local Y = Z x X), corners, top Z."""
    m = {**MOON_DEFAULTS, **moon}
    view = BoardView(far_view_distance(half))
    ray = view.ray(m["screenAnchor"])
    centre = tuple(view.loc[i] + ray[i] * m["depthUU"] for i in range(3))
    z = tuple(-x for x in view.f)
    x = view.r
    yax = (z[1] * x[2] - z[2] * x[1], z[2] * x[0] - z[0] * x[2], z[0] * x[1] - z[1] * x[0])
    h = m["diameterUU"] / 2.0
    corners = [tuple(centre[i] + sx * h * x[i] + sy * h * yax[i] for i in range(3)) for sx in (-1, 1) for sy in (-1, 1)]
    return {"centre": centre, "normal": z, "corners": corners, "topZ": max(c[2] for c in corners),
            "farViewUU": far_view_distance(half), "radiusNdcX": h / (sum((centre[i] - view.loc[i]) * view.f[i]
                                                                           for i in range(3)) * view.tan_h)}


def mist_rect(mist: dict) -> dict:
    m = {**MIST_DEFAULTS, **mist}
    cx, cy = m["centerUU"]
    hx, hy = m["halfUU"]
    return {"z": m["zUU"], "min": (cx - hx, cy - hy), "max": (cx + hx, cy + hy)}


# ------------------------------------------------------------------------------------------------ parser mirror
def _num(v) -> bool:
    return isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v)


def _vec(v, n, lo, hi) -> bool:
    return isinstance(v, list) and len(v) == n and all(_num(x) and lo <= x <= hi for x in v)


def validate_block(block, half: tuple[float, float], bid: str = "?") -> list[str]:
    """ParseBackdrop + S08BackdropPlacementProblem (same messages' gist)."""
    errs = []
    if not isinstance(block, dict):
        return [f"board {bid}: backdrop must be an object"]
    mist = block.get("mist", [])
    if "mist" in block and (not isinstance(mist, list) or len(mist) > MAX_MIST):
        return [f"board {bid}: backdrop.mist must be an array of at most {MAX_MIST} planes"]
    rng = {"zUU": (MIN_Z, MAX_Z), "opacity": (0.0, 0.8), "noiseScaleUU": (50.0, 5000.0), "edgeFade": (0.05, 0.5),
           "coverage": (0.0, 1.0), "seed": (0.0, 1000.0)}
    for i, m in enumerate(mist):
        ok = isinstance(m, dict) and "zUU" in m
        if ok:
            for k, (lo, hi) in rng.items():
                if k in m and not (_num(m[k]) and lo <= m[k] <= hi):
                    ok = False
            ok = ok and ("opacity" not in m or m["opacity"] > 0)
            ok = ok and ("centerUU" not in m or _vec(m["centerUU"], 2, -4000, 4000))
            ok = ok and ("halfUU" not in m or _vec(m["halfUU"], 2, 500, 8000))
            ok = ok and ("colorLinear" not in m or _vec(m["colorLinear"], 3, 0, 4))
            ok = ok and ("panUUPerSec" not in m or _vec(m["panUUPerSec"], 2, -100, 100))
        if not ok:
            errs.append(f"board {bid}: backdrop.mist[{i}] out of range / zUU missing")
    moon = block.get("moon")
    if moon is not None:
        ok = isinstance(moon, dict)
        if ok:
            for k, (lo, hi) in {"depthUU": (500, 20000), "diameterUU": (50, 5000), "intensity": (0, 50),
                                "softness": (0.05, 1), "discRadius": (0, 0.5), "discIntensity": (0, 50)}.items():
                if k in moon and not (_num(moon[k]) and lo <= moon[k] <= hi):
                    ok = False
            ok = ok and ("intensity" not in moon or moon["intensity"] > 0)
            ok = ok and ("screenAnchor" not in moon or _vec(moon["screenAnchor"], 2, -1, 1))
            ok = ok and ("colorLinear" not in moon or _vec(moon["colorLinear"], 3, 0, 4))
        if not ok:
            errs.append(f"board {bid}: backdrop.moon out of range")
    if errs:
        return errs
    if not mist and moon is None:
        return [f"board {bid}: backdrop needs at least one mist plane or the moon"]
    zs = [m["zUU"] for m in mist]
    for i in range(len(zs)):
        for j in range(i):
            if abs(zs[i] - zs[j]) < MIN_LAYER_GAP:
                errs.append(f"board {bid}: backdrop mist[{j}] and mist[{i}] closer than {MIN_LAYER_GAP:.0f} uu in Z")
    if moon is not None and moon_card(moon, half)["topZ"] > MAX_Z:
        errs.append(f"board {bid}: backdrop moon card reaches above Z {MAX_Z:.0f}")
    return errs


def map_half(board: dict) -> tuple[float, float]:
    mi = board.get("mapImage") or {}
    w, h = (mi.get("srcSize") or [1337, 866])[:2]
    s = float(mi.get("uuPerPx", 0.6666667))
    return w * s * 0.5, h * s * 0.5


# ------------------------------------------------------------------------------------------------ HLSL mirrors
def _np():
    import numpy as np  # lazy: the plain checks need no numpy
    return np


def _hash(ip):
    np = _np()
    return np.mod(np.sin(ip[..., 0] * 127.1 + ip[..., 1] * 311.7) * 43758.5453, 1.0)


def _smoothstep(a, b, x):
    np = _np()
    t = np.clip((x - a) / (b - a), 0.0, 1.0)
    return t * t * (3.0 - 2.0 * t)


def mist_noise(uv, t: float, p: dict):
    np = _np()
    size = np.asarray(p["SizeUU"][:2], dtype=np.float64)
    pan = np.asarray(p["PanUU"][:2], dtype=np.float64)
    q = (uv * size + pan * t) / max(p["NoiseScaleUU"], 1.0) + p["Seed"] * np.array([17.13, 31.71])
    n = np.zeros(uv.shape[:-1])
    a, norm = 0.5, 0.0
    for _ in range(3):
        ip = np.floor(q)
        fp = q - ip
        w = fp * fp * (3.0 - 2.0 * fp)
        h00, h10 = _hash(ip), _hash(ip + [1.0, 0.0])
        h01, h11 = _hash(ip + [0.0, 1.0]), _hash(ip + [1.0, 1.0])
        n += a * ((h00 * (1 - w[..., 0]) + h10 * w[..., 0]) * (1 - w[..., 1]) + (h01 * (1 - w[..., 0]) + h11 * w[..., 0]) * w[..., 1])
        norm += a
        q = np.stack([q[..., 0] * 1.6 - q[..., 1] * 1.2, q[..., 0] * 1.2 + q[..., 1] * 1.6], -1) + [5.2, 1.3]
        a *= 0.5
    return n / norm


def mist_density(uv, t: float, p: dict):
    """MIST_HLSL in numpy: uv (..., 2) in 0..1, p = MIST_PARAMS-like flat dict (SizeUU, PanUU, NoiseScaleUU, EdgeFade,
    Coverage, Seed)."""
    np = _np()
    n = mist_noise(uv, t, p)
    c = min(max(p["Coverage"], 0.0), 1.0)
    d = _smoothstep(1.0 - c - 0.15, 1.0 - c + 0.15, n)
    r = np.linalg.norm((uv - 0.5) * 2.0, axis=-1)
    fade = 1.0 - _smoothstep(1.0 - min(max(p["EdgeFade"], 0.01), 1.0), 1.0, r)
    return d * fade


def moon_glow(uv, p: dict):
    """MOON_HLSL in numpy: emissive (..., 3)."""
    np = _np()
    r = np.linalg.norm(uv * 2.0 - 1.0, axis=-1)
    s = max(p["Softness"], 0.02)
    glow = np.exp(-(r * r) / (s * s)) * np.clip((1.0 - r) * 5.0, 0.0, 1.0)
    disc = (1.0 if p["DiscRadius"] >= 0.0001 else 0.0) * (1.0 - _smoothstep(p["DiscRadius"] * 0.85, p["DiscRadius"] + 0.0001, r))
    k = max(p["Intensity"], 0.0) * glow + max(p["DiscIntensity"], 0.0) * disc
    return k[..., None] * np.asarray(p["Tint"][:3])


def mist_params(mist: dict) -> dict:
    m = {**MIST_DEFAULTS, **mist}
    return {"Tint": tuple(m["colorLinear"]) + (1.0,), "SizeUU": (m["halfUU"][0] * 2, m["halfUU"][1] * 2, 0.0, 0.0),
            "PanUU": (m["panUUPerSec"][0], m["panUUPerSec"][1], 0.0, 0.0), "Opacity": m["opacity"],
            "NoiseScaleUU": m["noiseScaleUU"], "EdgeFade": m["edgeFade"], "Coverage": m["coverage"], "Seed": m["seed"]}


def moon_params(moon: dict) -> dict:
    m = {**MOON_DEFAULTS, **moon}
    return {"Tint": tuple(m["colorLinear"]) + (1.0,), "Intensity": m["intensity"], "Softness": m["softness"],
            "DiscRadius": m["discRadius"], "DiscIntensity": m["discIntensity"]}


# ------------------------------------------------------------------------------------------------ scratch mock
TRAY_T2 = {"half": (780.0, 470.0), "offsetY": -45.0, "topZ": -3.0, "bottomZ": -216.0}  # S08Diorama T2 / T2b depth


def mock_far_view(block: dict, half: tuple[float, float], fog_rgb=(0.2, 0.255, 0.46), size=(480, 270), t: float = 0.0,
                  distance: float | None = None):
    """Linear RGB mock of a view (default: the far zoom): background = the fog colour, the tray as a dark box (its top
    and sides only), mist planes composited back to front (the box hides what is under it), additive moon card. A
    sanity look only: no lighting, no fog on the parts (as the materials), no props."""
    np = _np()
    W, H = size
    view = BoardView(distance or far_view_distance(half))
    xs = (np.arange(W) + 0.5) / W * 2.0 - 1.0
    ys = 1.0 - (np.arange(H) + 0.5) / H * 2.0
    nx, ny = np.meshgrid(xs, ys)
    f, r, u = (np.asarray(v) for v in (view.f, view.r, view.u))
    d = f + nx[..., None] * view.tan_h * r + ny[..., None] * view.tan_v * u
    d /= np.linalg.norm(d, axis=-1, keepdims=True)
    o = np.asarray(view.loc)
    img = np.ones((H, W, 3)) * np.asarray(fog_rgb)
    # tray box: hit distance of the slab (axis aligned) -> occluder depth
    lo = np.array([-TRAY_T2["half"][0], TRAY_T2["offsetY"] - TRAY_T2["half"][1], TRAY_T2["bottomZ"]])
    hi = np.array([TRAY_T2["half"][0], TRAY_T2["offsetY"] + TRAY_T2["half"][1], TRAY_T2["topZ"]])
    with np.errstate(divide="ignore", invalid="ignore"):
        t1, t2 = (lo - o) / d, (hi - o) / d
    tmin = np.nanmax(np.minimum(t1, t2), axis=-1)
    tmax = np.nanmin(np.maximum(t1, t2), axis=-1)
    tray_t = np.where((tmax >= tmin) & (tmax > 0), tmin, np.inf)
    layers = []
    for m in block.get("mist", []):
        p = mist_params(m)
        tz = (m["zUU"] - o[2]) / d[..., 2]
        hit = o + tz[..., None] * d
        rect = mist_rect(m)
        uv = np.stack([(hit[..., 0] - rect["min"][0]) / (rect["max"][0] - rect["min"][0]),
                       (hit[..., 1] - rect["min"][1]) / (rect["max"][1] - rect["min"][1])], -1)
        inside = (uv[..., 0] >= 0) & (uv[..., 0] <= 1) & (uv[..., 1] >= 0) & (uv[..., 1] <= 1) & (tz > 0) & (tz < tray_t)
        a = np.where(inside, mist_density(np.clip(uv, 0, 1), t, p) * p["Opacity"], 0.0)
        layers.append((tz, a, np.asarray(p["Tint"][:3])))
    moon = block.get("moon")
    if moon is not None:
        card = moon_card(moon, half)
        c = np.asarray(card["centre"])
        nrm = np.asarray(card["normal"])
        tz = ((c - o) @ nrm) / (d @ nrm)
        hit = o + tz[..., None] * d - c
        hd = (moon.get("diameterUU", MOON_DEFAULTS["diameterUU"])) / 2.0
        yax = np.cross(nrm, r)
        uv = np.stack([(hit @ r) / (2 * hd) + 0.5, (hit @ yax) / (2 * hd) + 0.5], -1)
        inside = (uv[..., 0] >= 0) & (uv[..., 0] <= 1) & (uv[..., 1] >= 0) & (uv[..., 1] <= 1) & (tz > 0) & (tz < tray_t)
        glow = np.where(inside[..., None], moon_glow(np.clip(uv, 0, 1), moon_params(moon)), 0.0)
        layers.append((tz, None, glow))
    # back to front by the per-pixel depth (both kinds are flat per pixel)
    order = sorted(range(len(layers)), key=lambda i: -float(np.nanmedian(np.where(np.isfinite(layers[i][0]), layers[i][0], np.nan))))
    for i in order:
        _, a, col = layers[i]
        if a is None:
            img = img + col
        else:
            img = img * (1 - a[..., None]) + col * a[..., None]
    img = np.where(np.isfinite(tray_t)[..., None], np.asarray([0.035, 0.03, 0.028]), img)
    return img


def to_srgb8(img, exposure: float = 1.0):
    np = _np()
    x = np.clip(img * exposure, 0, 1)
    s = np.where(x >= 0.0031308, 1.055 * np.power(np.maximum(x, 1e-9), 1 / 2.4) - 0.055, x * 12.92)
    return (np.clip(s, 0, 1) * 255 + 0.5).astype(np.uint8)


LUMA = (0.2126, 0.7152, 0.0722)
BACKGROUND_SRGB8 = 32.3  # P2 night calibration: background luma at K1x0.65 (S08ArtBoardProfiles sky "calibration")


def fog_color(board: dict, path: Path = PROFILES) -> tuple[float, float, float]:
    data = json.loads(path.read_text(encoding="utf-8"))
    fog = ((data.get("lightProfiles") or {}).get(board.get("light")) or {}).get("fog") or {}
    return tuple(fog.get("colorLinear") or (0.2, 0.255, 0.46))


def mock_exposure(fog_rgb) -> float:
    """Linear scale that puts the bare fog colour at the measured background luma (no tonemapper in the mock)."""
    s = BACKGROUND_SRGB8 / 255.0
    lin = ((s + 0.055) / 1.055) ** 2.4
    return lin / sum(c * w for c, w in zip(fog_rgb, LUMA))


# ------------------------------------------------------------------------------------------------ CLI
def shipped_blocks(path: Path = PROFILES) -> dict:
    data = json.loads(path.read_text(encoding="utf-8"))
    return {b["id"]: b for b in data.get("boards", []) if b.get("surface") == "map-image" and "backdrop" in b}


def report(block: dict, half: tuple[float, float]) -> dict:
    out = {"farViewUU": round(far_view_distance(half), 2), "mist": [], "moon": None}
    for m in block.get("mist", []):
        out["mist"].append({"rect": mist_rect(m), "params": mist_params(m)})
    if "moon" in block:
        card = moon_card(block["moon"], half)
        view_far = BoardView(card["farViewUU"])
        view_k1 = BoardView(k1_fit_distance(half) * 1.25)
        out["moon"] = {"centre": [round(v, 1) for v in card["centre"]], "topZ": round(card["topZ"], 1),
                       "ndcFar": [round(v, 3) for v in view_far.project(card["centre"])],
                       "ndcK1": [round(v, 3) for v in view_k1.project(card["centre"])],
                       "radiusNdcX": round(card["radiusNdcX"], 3)}
    return out


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n", 1)[0])
    ap.add_argument("--check", action="store_true")
    ap.add_argument("--mock", default=None, help="write far-zoom / K1 mock PNGs of the shipped blocks to this directory")
    a = ap.parse_args(argv)
    blocks = shipped_blocks()
    ok = True
    for bid, board in blocks.items():
        half = map_half(board)
        errs = validate_block(board["backdrop"], half, bid)
        ok = ok and not errs
        print(json.dumps({"board": bid, "errors": errs, **report(board["backdrop"], half)}, ensure_ascii=False))
        if a.mock:
            from PIL import Image
            out = Path(a.mock)
            out.mkdir(parents=True, exist_ok=True)
            fog = fog_color(board)
            for tag, dist in (("far065", None), ("k1", k1_fit_distance(half) * 1.25)):
                img = mock_far_view(board["backdrop"], half, fog_rgb=fog, distance=dist, size=(960, 540))
                Image.fromarray(to_srgb8(img, mock_exposure(fog))).save(out / f"backdrop-mock-{bid}-{tag}.png")
    print(f"BACKDROP-CHECK {'ok' if ok else 'failed'} boards={','.join(blocks) or '-'}")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
