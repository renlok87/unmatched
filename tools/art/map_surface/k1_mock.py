"""K1 perspective mock of a map board: pure numpy pinhole ray caster (no GPU / UE / Blender).

World = UE convention of the S08 board (INT-019): X to the right on screen (east), Y towards the
camera (south, image-down), Z up; the board centre is the origin and the map plane is Z = 0.
Camera = AS08FlowGameMode::SetupCameraForBoard: horizontal FOV 35 deg at 16:9, pitch -55,
yaw -90 (looks along -Y), located at (0, D cos55, D sin55), optical axis through the origin.
The illustration is laid flat and upright: source pixel (x, y) -> X = (x/1337 - 0.5) * 891.33,
Y = (y/866 - 0.5) * 577.33 (2/3 uu per source px), i.e. image top = far edge.
D: s08_fit_distance is the board FIT (1872.156 uu for the map canvas; the mocks of build_map_textures.py and
manifest.<key>.json k1.camera stay at this fit). Since ENV-U9 the game's K1 overview is the fit x the board
profile's "k1DistanceMul" (s08_overview_distance, k1_distance_mul: 1.25 on both map-image boards -> 2340.195 uu).
"""
from __future__ import annotations

import json
import math
from pathlib import Path

import numpy as np
from scipy import ndimage

CAM = {"hfov_deg": 35.0, "aspect": 16.0 / 9.0, "pitch_deg": 55.0, "yaw_deg": -90.0,
       "fit_margin_uu": 60.0, "fit_mul": 1.12}
KEY_LIGHT_ROT = (-55.0, 30.0, 0.0)  # S08 key (pitch, yaw, roll), pinned by S08BoardArtTests
# The board profiles the game reads (FS08BoardArtProfile::K1DistanceMul): the single source of k1DistanceMul.
PROFILES = Path(__file__).resolve().parents[3] / "unreal/Unmatched/Config/ArtBoards/S08ArtBoardProfiles.json"
K1_MUL_RANGE = (1.0, 2.0)  # FS08BoardArtProfile::MinK1DistanceMul / MaxK1DistanceMul (the parser rejects the rest)


def s08_fit_distance(extent_x: float, extent_y: float) -> float:
    """SetupCameraForBoard fit formula (S08K1FitDistanceUU) with board half extents (uu)."""
    half_h = math.tan(math.radians(CAM["hfov_deg"] / 2))
    half_v = half_h / CAM["aspect"]
    sp, m = math.sin(math.radians(CAM["pitch_deg"])), CAM["fit_margin_uu"]
    need_v = (extent_y * sp + m) / half_v
    need_h = (extent_x + m) / half_h
    return max(need_v, need_h) * CAM["fit_mul"]


def k1_distance_mul(board_id: str, profiles: Path | None = None) -> float:
    """ENV-U9: "k1DistanceMul" of the board profile whose match.boardIds holds board_id (1.0 when the profile has
    none, as FS08BoardArtProfile). AS08FlowGameMode::SetupCameraForBoard applies it while that profile is active.
    ValueError when no profile matches or the value is outside K1_MUL_RANGE (the UE parser rejects the document)."""
    doc = json.loads((profiles or PROFILES).read_text(encoding="utf-8"))
    for board in doc.get("boards", []):
        if board_id in ((board.get("match") or {}).get("boardIds") or []):
            mul = board.get("k1DistanceMul", 1.0)
            if isinstance(mul, bool) or not isinstance(mul, (int, float)) or \
                    not K1_MUL_RANGE[0] <= float(mul) <= K1_MUL_RANGE[1]:
                raise ValueError(f"board {board.get('id')}: k1DistanceMul {mul!r} is not a number in {K1_MUL_RANGE}")
            return float(mul)
    raise ValueError(f"no board profile matches board id {board_id!r} in {profiles or PROFILES}")


MAP_GRADE_SCHEMA = {"ev": "nightEV", "saturation": "nightSaturation", "lift": "lift",
                    "mask_saturation": "maskSaturation", "lift_saturation": "liftSaturation"}


def profile_map_grade(map_key: str, profiles: Path | None = None) -> dict:
    """ENV-MAPS P4: the night grade the ENGINE renders a map with - the "mapGrade" of the light profile of the
    map-image board whose mapImage.manifest is tools/art/map_surface/manifest.<map_key>.json (S08ArtBoardProfiles.json,
    AS08BoardActor::ApplyMapGrade sets it on the M_MapBoard MID). Returned in the k1_mock grade format:
    {ev, saturation, lift, tint_lin, mask_saturation, lift_saturation, mask_inverse_tint_lin, source}; the optional
    graph-v2 terms default to identity, a missing nightTintLinear to (1, 1, 1). ValueError without a board / grade."""
    path = profiles or PROFILES
    doc = json.loads(path.read_text(encoding="utf-8"))
    manifest = f"tools/art/map_surface/manifest.{map_key}.json"
    board = next((b for b in doc.get("boards", []) if (b.get("mapImage") or {}).get("manifest") == manifest), None)
    if board is None:
        raise ValueError(f"no map-image board profile with mapImage.manifest {manifest} in {path}")
    light = (doc.get("lightProfiles") or {}).get(board.get("light"))
    grade = (light or {}).get("mapGrade")
    if not isinstance(grade, dict):
        raise ValueError(f"board {board.get('id')}: light profile {board.get('light')!r} has no mapGrade")
    out = {k: float(grade.get(src, 1.0 if k in ("mask_saturation", "lift_saturation") else 0.0))
           for k, src in MAP_GRADE_SCHEMA.items()}
    for k in ("ev", "saturation", "lift"):
        if MAP_GRADE_SCHEMA[k] not in grade:
            raise ValueError(f"light {board.get('light')}: mapGrade.{MAP_GRADE_SCHEMA[k]} missing")
    out["tint_lin"] = [float(x) for x in grade.get("nightTintLinear", [1.0, 1.0, 1.0])]
    out["mask_inverse_tint_lin"] = [float(x) for x in grade.get("maskInverseTintLinear", [1.0, 1.0, 1.0])]
    out["source"] = (f"unreal/Unmatched/Config/ArtBoards/S08ArtBoardProfiles.json rev {doc.get('revision')} board "
                     f"{board.get('id')} light {board.get('light')} mapGrade")
    return out


def s08_overview_distance(extent_x: float, extent_y: float, k1_mul: float = 1.0) -> float:
    """ENV-U9: the K1 overview (S08K1OverviewDistanceUU) = s08_fit_distance x k1DistanceMul; 1.0 = the fit itself.
    The camera rig keeps its zoom ratios relative to this overview, its near limit at 300 uu and its far limit at
    fit / 0.65 (FS08CameraZoom; tools/art/env_kit/layout_check.py camera_set mirrors it)."""
    fit = s08_fit_distance(extent_x, extent_y)
    return fit if k1_mul == 1.0 else fit * k1_mul


class Camera:
    def __init__(self, distance: float, width: int, height: int):
        p = math.radians(CAM["pitch_deg"])
        self.pos = np.array([0.0, distance * math.cos(p), distance * math.sin(p)])
        self.fwd = np.array([0.0, -math.cos(p), -math.sin(p)])
        self.right = np.array([1.0, 0.0, 0.0])  # UE yaw -90: camera +Y axis = world +X
        self.up = np.array([0.0, -math.sin(p), math.cos(p)])
        self.tan_h = math.tan(math.radians(CAM["hfov_deg"] / 2))
        self.tan_v = self.tan_h / CAM["aspect"]
        self.w, self.h = width, height

    def rays(self, r0: int, r1: int):
        """Unnormalised ray directions for render rows [r0, r1): arrays (rows, W, 3)."""
        cols = (np.arange(self.w) + 0.5) / self.w * 2 - 1
        rows = 1 - (np.arange(r0, r1) + 0.5) / self.h * 2
        sx = cols[None, :] * self.tan_h
        sy = rows[:, None] * self.tan_v
        return (self.fwd[None, None, :] + sx[..., None] * self.right[None, None, :]
                + sy[..., None] * self.up[None, None, :])

    def project(self, P) -> np.ndarray:
        """World points (n, 3) -> screen pixel coordinates (n, 2) (x right, y down, pixel
        centres at i + 0.5) of this camera's image size."""
        v = np.asarray(P, float) - self.pos
        z = v @ self.fwd
        sx = (v @ self.right) / z / self.tan_h
        sy = (v @ self.up) / z / self.tan_v
        return np.c_[(sx + 1) / 2 * self.w, (1 - sy) / 2 * self.h]


# ------------------------------------------------------------------ colour helpers
def srgb_to_lin(c):
    c = np.asarray(c, np.float32)
    return np.where(c <= 0.04045, c / 12.92, ((c + 0.055) / 1.055) ** 2.4).astype(np.float32)


def lin_to_srgb(c):
    c = np.clip(c, 0.0, 1.0)
    return np.where(c <= 0.0031308, c * 12.92, 1.055 * np.power(c, 1 / 2.4) - 0.055)


LUMA = np.array([0.2126, 0.7152, 0.0722], np.float32)


def build_mips(lin: np.ndarray) -> list[np.ndarray]:
    mips = [lin]
    while mips[-1].shape[0] > 1:
        a = mips[-1]
        mips.append(0.25 * (a[0::2, 0::2] + a[1::2, 0::2] + a[0::2, 1::2] + a[1::2, 1::2]))
    return mips


def _bilinear(tex: np.ndarray, u: np.ndarray, v: np.ndarray) -> np.ndarray:
    h, w = tex.shape[:2]
    fx = u * w - 0.5
    fy = v * h - 0.5
    x0 = np.floor(fx).astype(np.int64)
    y0 = np.floor(fy).astype(np.int64)
    ax = (fx - x0).astype(np.float32)
    ay = (fy - y0).astype(np.float32)
    x0c, x1c = np.clip(x0, 0, w - 1), np.clip(x0 + 1, 0, w - 1)
    y0c, y1c = np.clip(y0, 0, h - 1), np.clip(y0 + 1, 0, h - 1)
    if tex.ndim == 3:
        ax, ay = ax[..., None], ay[..., None]
    top = tex[y0c, x0c] * (1 - ax) + tex[y0c, x1c] * ax
    bot = tex[y1c, x0c] * (1 - ax) + tex[y1c, x1c] * ax
    return top * (1 - ay) + bot * ay


def trilinear(mips: list[np.ndarray], u, v, lod):
    lod = np.clip(lod, 0, len(mips) - 1)
    l0 = np.floor(lod).astype(np.int64)
    out = None
    for L in np.unique(l0):
        sel = l0 == L
        a = _bilinear(mips[L], u[sel], v[sel])
        if L + 1 < len(mips):
            b = _bilinear(mips[L + 1], u[sel], v[sel])
            t = (lod[sel] - L).astype(np.float32)
            a = a * (1 - t[:, None]) + b * t[:, None] if a.ndim == 2 else a * (1 - t) + b * t
        if out is None:
            out = np.zeros(u.shape + a.shape[1:], np.float32)
        out[sel] = a
    return out


# ------------------------------------------------------------------ scene pieces
def _rock_noise(shape=(1024, 1024), seed=7) -> np.ndarray:
    rng = np.random.default_rng(seed)
    n = np.zeros(shape, np.float32)
    for sigma, amp in ((24, 0.55), (8, 0.3), (2.5, 0.15)):
        f = ndimage.gaussian_filter(rng.standard_normal(shape).astype(np.float32), sigma, mode="wrap")
        n += amp * f / max(float(f.std()), 1e-6)
    return n


def _hero_sdf(p: np.ndarray) -> np.ndarray:
    """Grey placeholder hero, base centre at origin, ~50 uu tall (base 40 uu, as S08 art figure)."""
    x, y, z = p[..., 0], p[..., 1], p[..., 2]
    r = np.hypot(x, y)
    # base: capped cylinder r 20, z 0..4
    dx, dz = r - 20.0, np.abs(z - 2.0) - 2.0
    base = np.minimum(np.maximum(dx, dz), 0) + np.hypot(np.maximum(dx, 0), np.maximum(dz, 0))
    # body: round cone r 11.5 @ z 6 -> r 7 @ z 34
    t = np.clip((z - 6.0) / 28.0, 0, 1)
    rad = 11.5 + (7.0 - 11.5) * t
    body = np.maximum(r - rad, np.maximum(6.0 - z, z - 36.0))
    # head: sphere r 7 @ z 43
    head = np.sqrt(r * r + (z - 43.0) ** 2) - 7.0
    return np.minimum(np.minimum(base, body), head)


def render(cam: Camera, maps: dict, layout: dict, variant: str, ss: int = 3, strip: int = 60) -> np.ndarray:
    """maps: {'mips': linear BC mips, 'mask_mips': mask mips (float 0..1) or None};
    layout: board/tray sizes and props (heroes/rings in world uu). Returns sRGB uint8 (H, W, 3)."""
    W, H = cam.w, cam.h
    rc = Camera(float(np.linalg.norm(cam.pos)), W * ss, H * ss)
    MX, MY = layout["map_half_uu"]
    TX, TY = MX + layout["tray_rim_uu"], MY + layout["tray_rim_uu"]
    TZ = layout["tray_height_uu"]
    grade = layout["grade"]
    L = _light_dir(KEY_LIGHT_ROT)
    noise = _rock_noise()
    rock = srgb_to_lin(layout["rock_srgb"])
    bg_top, bg_bot = srgb_to_lin(layout["bg_top_srgb"]), srgb_to_lin(layout["bg_bottom_srgb"])
    heroes = layout.get("heroes", []) if variant == "c" else []
    rings = layout.get("rings", []) if variant == "c" else []
    out = np.zeros((H, W, 3), np.uint8)
    for fr0 in range(0, H, strip):
        fr1 = min(H, fr0 + strip)
        r0, r1 = fr0 * ss, fr1 * ss
        d = rc.rays(r0, r1)
        rows = np.arange(r0, r1)
        col = np.empty(d.shape, np.float32)
        # background: vertical gradient by screen row
        tb = ((rows + 0.5) / rc.h)[:, None, None].astype(np.float32)
        col[:] = bg_top * (1 - tb) + bg_bot * tb
        # plane z = 0
        t0 = -rc.pos[2] / d[..., 2]
        X = rc.pos[0] + t0 * d[..., 0]
        Y = rc.pos[1] + t0 * d[..., 1]
        on_map = (np.abs(X) <= MX) & (np.abs(Y) <= MY)
        on_rim = ~on_map & (np.abs(X) <= TX) & (np.abs(Y) <= TY)
        # near wall (Y = +TY, facing the camera)
        tw = (TY - rc.pos[1]) / d[..., 1]
        Zw = rc.pos[2] + tw * d[..., 2]
        Xw = rc.pos[0] + tw * d[..., 0]
        on_wall = ~on_map & ~on_rim & (Zw <= 0) & (Zw >= -TZ) & (np.abs(Xw) <= TX) & (Y > TY)
        # --- map
        if on_map.any():
            u = (X + MX) / (2 * MX)
            v = (Y + MY) / (2 * MY)
            n0 = maps["mips"][0].shape[0]
            du_dx = np.gradient(u * n0, axis=1)
            dv_dx = np.gradient(v * n0, axis=1)
            du_dy = np.gradient(u * n0, axis=0)
            dv_dy = np.gradient(v * n0, axis=0)
            lx = np.hypot(du_dx, dv_dx)
            ly = np.hypot(du_dy, dv_dy)
            lod = np.log2(np.maximum(np.sqrt(lx * ly), 1e-6))
            um, vm, lm = u[on_map], v[on_map], lod[on_map]
            alb = trilinear(maps["mips"], um, vm, lm)
            if variant == "a":
                c = alb
            else:
                m = trilinear(maps["mask_mips"], um, vm, lm)
                c = _night(alb, m, grade)
            # blob shadows + team rings (variant c)
            Xm, Ym = X[on_map], Y[on_map]
            for hr in heroes:
                dd = np.hypot(Xm - hr["x"] - 4.0, Ym - hr["y"] - 3.0)
                c = c * (1 - 0.45 * np.exp(-(dd / 20.0) ** 2))[:, None]
            for rg in rings:
                dd = np.hypot(Xm - rg["x"], Ym - rg["y"])
                band = _aa_band(dd, rg["r_in"], rg["r_out"], 0.6)
                rim = _aa_band(dd, rg["r_out"] - rg["rim"], rg["r_out"], 0.6)
                rcol = srgb_to_lin(rg["srgb"]) * rg["intensity"]
                rimc = rcol * 0.45
                c = c * (1 - band)[:, None] + rcol * (band - rim)[:, None] + rimc * rim[:, None]
            col[on_map] = c
        # --- tray top (rim) and near wall
        if on_rim.any():
            nx = ((X[on_rim] + TX) / (2 * TX) * 1023).astype(np.int64) % 1024
            ny = ((Y[on_rim] + TY) / (2 * TY) * 1023).astype(np.int64) % 1024
            tone = 1.0 + 0.22 * noise[ny, nx]
            # inner groove: darker band next to the map edge (fake AO)
            edge = np.hypot(np.maximum(np.abs(X[on_rim]) - MX, 0), np.maximum(np.abs(Y[on_rim]) - MY, 0))
            ao = 1 - 0.55 * np.exp(-(edge / 3.0) ** 2)
            ndl = max(0.0, float(np.dot([0, 0, 1], -L)))
            shade = (0.35 + 0.65 * ndl) * tone * ao
            c = rock[None, :] * shade[:, None]
            col[on_rim] = c if variant == "a" else _night(c, None, grade)
        if on_wall.any():
            nx = ((Xw[on_wall] + TX) / (2 * TX) * 1023).astype(np.int64) % 1024
            nz = ((-Zw[on_wall]) / TZ * 300).astype(np.int64) % 1024
            tone = 1.0 + 0.3 * noise[nz, nx]
            ndl = max(0.0, float(np.dot([0, 1, 0], -L)))
            fall = 1 - 0.5 * (-Zw[on_wall] / TZ)
            shade = (0.28 + 0.65 * ndl) * tone * fall
            c = rock[None, :] * 0.85 * shade[:, None]
            col[on_wall] = c if variant == "a" else _night(c, None, grade)
        # --- heroes (sphere-traced SDF)
        for hr in heroes:
            _trace_hero(col, rc, d, t0, hr, L, grade, variant)
        # downsample the strip (box ss x ss) in linear light
        hh, ww = (r1 - r0) // ss, W
        col = col.reshape(hh, ss, ww, ss, 3).mean(axis=(1, 3))
        out[fr0:fr1] = np.round(lin_to_srgb(col) * 255).astype(np.uint8)
    return out


def screen_uv(cam: Camera, layout: dict, tex: int):
    """Nearest texel (u_idx, v_idx) seen by every pixel of the camera image, and the map mask."""
    mx, my = layout["map_half_uu"]
    d = cam.rays(0, cam.h)
    t0 = -cam.pos[2] / d[..., 2]
    X = cam.pos[0] + t0 * d[..., 0]
    Y = cam.pos[1] + t0 * d[..., 1]
    on = (np.abs(X) <= mx) & (np.abs(Y) <= my)
    u = np.clip(((X + mx) / (2 * mx) * tex).astype(np.int64), 0, tex - 1)
    v = np.clip(((Y + my) / (2 * my) * tex).astype(np.int64), 0, tex - 1)
    return on, u, v


def _aa_band(d, r_in, r_out, soft):
    return np.clip((d - r_in) / soft + 0.5, 0, 1) * np.clip((r_out - d) / soft + 0.5, 0, 1)


def _light_dir(rot):
    p, y = math.radians(rot[0]), math.radians(rot[1])
    return np.array([math.cos(p) * math.cos(y), math.cos(p) * math.sin(y), math.sin(p)])


def _saturate(c: np.ndarray, s: float) -> np.ndarray:
    """Luma-preserving saturation in linear light (M_MapBoard: max(lerp(luma, c, s), 0))."""
    if s == 1.0:
        return c
    y = (c @ LUMA)[:, None]
    return np.maximum(y + (c - y) * np.float32(s), 0.0)


def _night(c: np.ndarray, mask, grade: dict) -> np.ndarray:
    """Night grade = the M_MapBoard graph (tools/art/map_surface/ue_import_map_surface.py BASE_HLSL / LIFT_HLSL):
    lit = albedo * 2^EV * tint everywhere; outside the game-layer mask desaturated by 'saturation'; inside the mask
    (graph v2, ENV-MAPS P4) lit * mask_inverse_tint_lin with chroma x mask_saturation, plus the unlit lift
    'lift' x albedo with chroma x lift_saturation (UE emissive). The graph-v2 terms default to identity, so a grade
    without them is the graph-v1 formula exactly."""
    light = (2.0 ** grade["ev"]) * np.asarray(grade["tint_lin"], np.float32)
    lit = c * light
    y = (lit @ LUMA)[:, None]
    outside = y + (lit - y) * grade["saturation"]
    if mask is None:
        return outside
    inv = np.asarray(grade.get("mask_inverse_tint_lin", (1.0, 1.0, 1.0)), np.float32)
    lit_in = lit if np.all(inv == 1.0) else lit * inv
    inside = (_saturate(lit_in, float(grade.get("mask_saturation", 1.0)))
              + grade["lift"] * _saturate(c, float(grade.get("lift_saturation", 1.0))))
    m = mask.reshape(-1, 1) if mask.ndim == 1 else mask
    return outside * (1 - m) + inside * m


def _trace_hero(col, rc: Camera, d, t_plane, hr, L, grade, variant):
    hx, hy = hr["x"], hr["y"]
    centre = np.array([hx, hy, 26.0])
    rad = 36.0
    # ray-sphere bound
    dn = d / np.linalg.norm(d, axis=-1, keepdims=True)
    oc = rc.pos - centre
    b = dn @ oc
    cc = float(oc @ oc) - rad * rad
    disc = b * b - cc
    cand = disc > 0
    if not cand.any():
        return
    idx = np.nonzero(cand)
    ray = dn[idx]
    t = -b[idx] - np.sqrt(disc[idx])
    t_far = -b[idx] + np.sqrt(disc[idx])
    hit = np.zeros(len(t), bool)
    for _ in range(120):
        p = rc.pos + ray * t[:, None] - np.array([hx, hy, 0.0])
        s = _hero_sdf(p)
        hit |= s < 0.03
        t = np.where(hit, t, t + np.maximum(s, 0.02))
        if ((t > t_far) | hit).all():
            break
    hit &= t < t_far
    if not hit.any():
        return
    p = rc.pos + ray[hit] * t[hit][:, None] - np.array([hx, hy, 0.0])
    e = 0.05
    n = np.stack([_hero_sdf(p + [e, 0, 0]) - _hero_sdf(p - [e, 0, 0]),
                  _hero_sdf(p + [0, e, 0]) - _hero_sdf(p - [0, e, 0]),
                  _hero_sdf(p + [0, 0, e]) - _hero_sdf(p - [0, 0, e])], axis=-1)
    n /= np.maximum(np.linalg.norm(n, axis=-1, keepdims=True), 1e-9)
    ndl = np.clip(n @ (-L), 0, 1)
    alb = np.float32(hr.get("albedo_lin", 0.30))
    c = alb * (0.30 + 0.85 * ndl)
    c = np.repeat(c[:, None], 3, axis=1).astype(np.float32)
    if variant != "a":
        c = _night(c, None, grade) * 1.35  # figures keep a little more light than the decor
    rows, cols_ = idx[0][hit], idx[1][hit]
    col[rows, cols_] = c
