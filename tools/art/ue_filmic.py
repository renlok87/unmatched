#!/usr/bin/env python3
"""UE 5.8 "Filmic" tone curve (the default TonemappingMethod) as a numpy model, its numerical inverse and the exposure
shift of a display-referred 8-bit frame.

Source of truth: Engine/Shaders/Private/PostProcessCombineLUTs.usf (CombineLUTsCommon: ExpandGamut -> ColorCorrectAll ->
ApplyToneCurve -> ComputeFilmColorNoGamma: BlueCorrection -> FilmToneMap -> inverse BlueCorrection -> working sRGB)
and TonemapCommon.ush FilmToneMap (ACES glow + red modifier in AP0, per-channel filmic S-curve in AP1 with pre / post
desaturation), UE_5.8 install of this machine. Defaults (Scene.cpp FPostProcessSettings): Slope 0.88, Toe 0.55,
Shoulder 0.26, BlackClip 0, WhiteClip 0.04, BlueCorrection 0.6, ExpandGamut 1.0, ToneCurveAmount 1, neutral
ColorGrading, sRGB output device, TonemapperGamma default (InverseGamma.y = 1), working colour space sRGB/Rec.709.

Not modelled (all exposure-proportional or spatial, so they do not move a per-zone median by an exposure shift):
bloom (additive, scales with the scene), vignette (multiplies the scene before the LUT), film grain, the 32^3 LUT
quantisation, TSR. Local exposure is neutral by default (highlight / shadow contrast 1.0).

Use:
    display = scene_to_display(linear_rgb)        # scene-referred linear sRGB (after exposure) -> sRGB [0, 1]
    linear  = display_to_scene(display)           # numerical inverse (clipped channels stay at the curve maximum)
    shifted = shift_display_u8(frame_u8, -1.0)    # the same frame at -1 EV of exposure (3D LUT, trilinear)

Status: model of the engine code; checked against the game-layer calibration bytes of W5b-R and against the look-dev C
neutral / reading (-1 EV) frame pairs (tools/art/t5cb1_exposure_sim.py validate). Not an engine capture.
"""
from __future__ import annotations

import math
from functools import lru_cache

import numpy as np

# ------------------------------------------------------------------ matrices (ACESCommon.ush, row-major, mul(M, v))
AP0_2_XYZ = np.array([[0.9525523959, 0.0, 0.0000936786],
                      [0.3439664498, 0.7281660966, -0.0721325464],
                      [0.0, 0.0, 1.0088251844]])
XYZ_2_AP0 = np.array([[1.0498110175, 0.0, -0.0000974845],
                      [-0.4959030231, 1.3733130458, 0.0982400361],
                      [0.0, 0.0, 0.9912520182]])
AP1_2_XYZ = np.array([[0.6624541811, 0.1340042065, 0.1561876870],
                      [0.2722287168, 0.6740817658, 0.0536895174],
                      [-0.0055746495, 0.0040607335, 1.0103391003]])
XYZ_2_AP1 = np.array([[1.6410233797, -0.3248032942, -0.2364246952],
                      [-0.6636628587, 1.6153315917, 0.0167563477],
                      [0.0117218943, -0.0082844420, 0.9883948585]])
AP0_2_AP1 = np.array([[1.4514393161, -0.2365107469, -0.2149285693],
                      [-0.0765537734, 1.1762296998, -0.0996759264],
                      [0.0083161484, -0.0060324498, 0.9977163014]])
AP1_2_AP0 = np.array([[0.6954522414, 0.1406786965, 0.1638690622],
                      [0.0447945634, 0.8596711185, 0.0955343182],
                      [-0.0055258826, 0.0040252103, 1.0015006723]])
XYZ_2_sRGB = np.array([[3.2409699419, -1.5373831776, -0.4986107603],
                       [-0.9692436363, 1.8759675015, 0.0415550574],
                       [0.0556300797, -0.2039769589, 1.0569715142]])
sRGB_2_XYZ = np.array([[0.4123907993, 0.3575843394, 0.1804807884],
                       [0.2126390059, 0.7151686788, 0.0721923154],
                       [0.0193308187, 0.1191947798, 0.9505321522]])
D65_2_D60 = np.array([[1.0130349146, 0.0061052578, -0.0149709436],
                      [0.0076982301, 0.9981633521, -0.0050320385],
                      [-0.0028413174, 0.0046851567, 0.9245061375]])
D60_2_D65 = np.array([[0.9872240087, -0.0061132286, 0.0159532883],
                      [-0.0075983718, 1.0018614847, 0.0053300358],
                      [0.0030725771, -0.0050959615, 1.0816806031]])
AP1_RGB2Y = np.array([0.2722287168, 0.6740817658, 0.0536895174])

sRGB_2_AP1 = XYZ_2_AP1 @ D65_2_D60 @ sRGB_2_XYZ
AP1_2_sRGB = XYZ_2_sRGB @ D60_2_D65 @ AP1_2_XYZ

BLUE_CORRECT = np.array([[0.9404372683, -0.0183068787, 0.0778696104],
                         [0.0083786969, 0.8286599939, 0.1629613092],
                         [0.0005471261, -0.0008833746, 1.0003362486]])
BLUE_CORRECT_INV = np.array([[1.06318, 0.0233956, -0.0865726],
                             [-0.0106337, 1.20632, -0.19569],
                             [-0.000590887, 0.00105248, 0.999538]])
BLUE_CORRECT_AP1 = AP0_2_AP1 @ BLUE_CORRECT @ AP1_2_AP0
BLUE_CORRECT_INV_AP1 = AP0_2_AP1 @ BLUE_CORRECT_INV @ AP1_2_AP0

WIDE_2_XYZ = np.array([[0.5441691, 0.2395926, 0.1666943],
                       [0.2394656, 0.7021530, 0.0583814],
                       [-0.0023439, 0.0361834, 1.0552183]])
EXPAND_MAT = (XYZ_2_AP1 @ WIDE_2_XYZ) @ AP1_2_sRGB

DEFAULTS = {"slope": 0.88, "toe": 0.55, "shoulder": 0.26, "black_clip": 0.0, "white_clip": 0.04,
            "blue_correction": 0.6, "expand_gamut": 1.0}


def _mv(m: np.ndarray, v: np.ndarray) -> np.ndarray:
    """mul(M, v) over (..., 3)."""
    return v @ m.T


# ------------------------------------------------------------------ FilmToneMap (TonemapCommon.ush)
def _rgb_2_saturation(rgb):
    mn = rgb.min(-1)
    mx = rgb.max(-1)
    return (np.maximum(mx, 1e-10) - np.maximum(mn, 1e-10)) / np.maximum(mx, 1e-2)


def _rgb_2_yc(rgb, w=1.75):
    r, g, b = rgb[..., 0], rgb[..., 1], rgb[..., 2]
    chroma = np.sqrt(np.maximum(b * (b - g) + g * (g - r) + r * (r - b), 0.0))
    return (b + g + r + w * chroma) / 3.0


def _sigmoid_shaper(x):
    t = np.maximum(1.0 - np.abs(0.5 * x), 0.0)
    y = 1.0 + np.sign(x) * (1.0 - t * t)
    return 0.5 * y


def _glow_fwd(yc, gain, mid):
    out = np.where(yc <= 2.0 / 3.0 * mid, gain, np.where(yc >= 2.0 * mid, 0.0, gain * (mid / np.maximum(yc, 1e-10) - 0.5)))
    return out


def _rgb_2_hue(rgb):
    r, g, b = rgb[..., 0], rgb[..., 1], rgb[..., 2]
    hue = np.degrees(np.arctan2(math.sqrt(3.0) * (g - b), 2.0 * r - g - b))
    hue = np.where((r == g) & (g == b), 0.0, hue)
    hue = np.where(hue < 0.0, hue + 360.0, hue)
    return np.clip(hue, 0.0, 360.0)


def _center_hue(hue, c):
    h = hue - c
    h = np.where(h < -180.0, h + 360.0, h)
    return np.where(h > 180.0, h - 360.0, h)


def _smoothstep(e0, e1, x):
    t = np.clip((x - e0) / (e1 - e0), 0.0, 1.0)
    return t * t * (3.0 - 2.0 * t)


def film_tone_map(ap1: np.ndarray, p: dict | None = None) -> np.ndarray:
    """FilmToneMap(ColorAP1) of TonemapCommon.ush, (..., 3) linear AP1 -> tone-mapped AP1."""
    p = dict(DEFAULTS, **(p or {}))
    slope, toe, shoulder, bclip, wclip = p["slope"], p["toe"], p["shoulder"], p["black_clip"], p["white_clip"]
    ap0 = _mv(AP1_2_AP0, ap1)
    sat = _rgb_2_saturation(ap0)
    yc = _rgb_2_yc(ap0)
    s = _sigmoid_shaper((sat - 0.4) / 0.2)
    glow = 1.0 + _glow_fwd(yc, 0.05 * s, 0.08)
    ap0 = ap0 * glow[..., None]
    hue = _rgb_2_hue(ap0)
    ch = _center_hue(hue, 0.0)
    hw = _smoothstep(0.0, 1.0, 1.0 - np.abs(2.0 * ch / 135.0)) ** 2
    ap0 = ap0.copy()
    ap0[..., 0] = ap0[..., 0] + hw * sat * (0.03 - ap0[..., 0]) * (1.0 - 0.82)
    w = np.maximum(_mv(AP0_2_AP1, ap0), 0.0)
    y = (w * AP1_RGB2Y).sum(-1, keepdims=True)
    w = y + (w - y) * 0.96
    toe_scale = 1.0 + bclip - toe
    sh_scale = 1.0 + wclip - shoulder
    in_m, out_m = 0.18, 0.18
    if toe > 0.8:
        toe_match = (1.0 - toe - out_m) / slope + math.log10(in_m)
    else:
        bt = (out_m + bclip) / toe_scale - 1.0
        toe_match = math.log10(in_m) - 0.5 * math.log((1.0 + bt) / (1.0 - bt)) * (toe_scale / slope)
    straight_match = (1.0 - toe) / slope - toe_match
    shoulder_match = shoulder / slope - straight_match
    lc = np.log10(np.maximum(w, 1e-10))
    straight = slope * (lc + straight_match)
    with np.errstate(over="ignore"):
        toe_c = -bclip + (2.0 * toe_scale) / (1.0 + np.exp((-2.0 * slope / toe_scale) * (lc - toe_match)))
        sh_c = (1.0 + wclip) - (2.0 * sh_scale) / (1.0 + np.exp((2.0 * slope / sh_scale) * (lc - shoulder_match)))
    toe_c = np.where(lc < toe_match, toe_c, straight)
    sh_c = np.where(lc > shoulder_match, sh_c, straight)
    t = np.clip((lc - toe_match) / (shoulder_match - toe_match), 0.0, 1.0)
    if shoulder_match < toe_match:
        t = 1.0 - t
    t = (3.0 - 2.0 * t) * t * t
    tone = toe_c + (sh_c - toe_c) * t
    y = (tone * AP1_RGB2Y).sum(-1, keepdims=True)
    tone = y + (tone - y) * 0.93
    return np.maximum(tone, 0.0)


# ------------------------------------------------------------------ CombineLUTs chain
def linear_to_srgb(x):
    x = np.clip(x, 0.0, 1.0)
    return np.where(x <= 0.0031308, x * 12.92, 1.055 * np.power(x, 1.0 / 2.4) - 0.055)


def srgb_to_linear(c):
    c = np.clip(c, 0.0, 1.0)
    return np.where(c <= 0.04045, c / 12.92, np.power((c + 0.055) / 1.055, 2.4))


def scene_to_film_linear(lin_srgb: np.ndarray, p: dict | None = None, clip: bool = True) -> np.ndarray:
    """Scene linear sRGB/Rec.709 (after exposure) -> display linear sRGB (before the sRGB OETF). clip=False keeps the
    negative out-of-gamut values of the last matrix (the engine clips them: max(0, FromAP1 * c)) - used by the
    inverse so that a channel pushed below 0 still has a gradient."""
    p = dict(DEFAULTS, **(p or {}))
    c = _mv(sRGB_2_AP1, np.asarray(lin_srgb, dtype=np.float64))
    luma = (c * AP1_RGB2Y).sum(-1, keepdims=True)
    chroma = c / np.maximum(luma, 1e-10)
    cds = ((chroma - 1.0) ** 2).sum(-1, keepdims=True)
    amount = (1.0 - np.exp2(-4.0 * cds)) * (1.0 - np.exp2(-4.0 * p["expand_gamut"] * luma * luma))
    c = c + (_mv(EXPAND_MAT, c) - c) * amount
    bc = p["blue_correction"]
    c = c + (_mv(BLUE_CORRECT_AP1, c) - c) * bc
    c = film_tone_map(c, p)
    c = c + (_mv(BLUE_CORRECT_INV_AP1, c) - c) * bc
    out = _mv(AP1_2_sRGB, c)
    return np.maximum(out, 0.0) if clip else out


def scene_to_display(lin_srgb: np.ndarray, p: dict | None = None) -> np.ndarray:
    """Scene linear (after exposure) -> display sRGB-encoded [0, 1]."""
    return linear_to_srgb(scene_to_film_linear(lin_srgb, p))


LOG_LO, LOG_HI = math.log(1e-6), math.log(60.0)
BLACK = 0.5 / 255.0  # display code below half a level = black: one-sided target


def display_to_scene(display: np.ndarray, p: dict | None = None, iters: int = 40) -> np.ndarray:
    """Numerical inverse of scene_to_display on (..., 3) sRGB-encoded [0, 1]: damped Gauss-Newton (Levenberg) on the
    input log, residual in display-linear relative units (1 / (target + 0.004)), numerical 3x3 Jacobian of the UNCLIPPED
    curve (so an out-of-gamut channel keeps a gradient), started from the grey-curve inverse per channel. A channel at
    display 0 is one-sided (anything at or below 0 is exact); a channel at 255 is held at the curve top. Every pixel of
    a real frame is reachable; a target outside the curve's gamut converges to the nearest reachable value."""
    d = np.clip(np.asarray(display, dtype=np.float64), 0.0, 1.0)
    shape = d.shape
    d = d.reshape(-1, 3)
    tgt = srgb_to_linear(d)
    black = d <= BLACK
    top = float(scene_to_film_linear(np.array([[60.0, 60.0, 60.0]]), p)[0, 0])
    tgt = np.minimum(tgt, top * 0.9995)
    wgt = 1.0 / (tgt + 0.004)
    u = np.log(np.maximum(_grey_inverse(np.maximum(tgt, 1e-5), p), 1e-6))
    u = np.clip(u, LOG_LO, LOG_HI)
    h = 1e-4
    for _ in range(iters):
        f = scene_to_film_linear(np.exp(u), p, clip=False)
        r = tgt - f
        r = np.where(black & (r >= 0.0), 0.0, r) * wgt
        if np.abs(r).max() < 1e-7:
            break
        J = np.empty((len(u), 3, 3))
        for k in range(3):
            du = np.zeros(3)
            du[k] = h
            J[:, :, k] = (scene_to_film_linear(np.exp(u + du), p, clip=False) - f) / h
        J = J * wgt[..., None]
        JT = np.transpose(J, (0, 2, 1))
        A = JT @ J + 1e-6 * np.eye(3)[None]
        step = np.linalg.solve(A, (JT @ r[..., None]))[..., 0]
        n = np.abs(step).max(-1, keepdims=True)
        step = np.where(n > 0.7, step * (0.7 / np.maximum(n, 1e-12)), step)
        u = np.clip(u + step, LOG_LO, LOG_HI)
    return np.exp(u).reshape(shape)


@lru_cache(maxsize=8)
def _grey_table(key: tuple) -> tuple[np.ndarray, np.ndarray]:
    p = dict(key)
    xs = np.logspace(-6, 2.5, 4000)
    g = np.stack([xs, xs, xs], -1)
    ys = scene_to_film_linear(g, p)[:, 1]
    ys = np.maximum.accumulate(ys)
    return xs, ys


def _grey_inverse(tgt, p):
    xs, ys = _grey_table(tuple(sorted(dict(DEFAULTS, **(p or {})).items())))
    return np.interp(tgt, ys, xs)


# ------------------------------------------------------------------ frames
@lru_cache(maxsize=16)
def shift_lut(ev: float, n: int = 65, key: tuple = ()) -> np.ndarray:
    """(n, n, n, 3) table: display sRGB grid -> display sRGB of the same scene value x 2^ev."""
    p = dict(key) if key else None
    g = np.linspace(0.0, 1.0, n)
    rr, gg, bb = np.meshgrid(g, g, g, indexing="ij")
    disp = np.stack([rr, gg, bb], -1).reshape(-1, 3)
    scene = display_to_scene(disp, p)
    out = scene_to_display(scene * (2.0 ** ev), p)
    return out.reshape(n, n, n, 3)


def apply_lut(img01: np.ndarray, lut: np.ndarray) -> np.ndarray:
    """Trilinear lookup of (..., 3) [0, 1] values in an (n, n, n, 3) table."""
    n = lut.shape[0]
    x = np.clip(img01, 0.0, 1.0) * (n - 1)
    i0 = np.minimum(np.floor(x).astype(np.int64), n - 2)
    f = x - i0
    out = np.zeros(img01.shape, dtype=np.float64)
    for dr in (0, 1):
        wr = f[..., 0] if dr else 1.0 - f[..., 0]
        for dg in (0, 1):
            wg = f[..., 1] if dg else 1.0 - f[..., 1]
            for db in (0, 1):
                wb = f[..., 2] if db else 1.0 - f[..., 2]
                w = (wr * wg * wb)[..., None]
                out += w * lut[i0[..., 0] + dr, i0[..., 1] + dg, i0[..., 2] + db]
    return out


def shift_display_u8(frame_u8: np.ndarray, ev: float, mask: np.ndarray | None = None, n: int = 65) -> np.ndarray:
    """The 8-bit display frame at +ev of exposure (scene value x 2^ev). mask (H, W) bool: only these pixels move
    (e.g. lit pixels; the unlit game layer x EyeAdaptationInverse and UMG do not follow the exposure)."""
    if abs(ev) < 1e-9:
        return frame_u8.copy()
    lut = shift_lut(round(float(ev), 4), n)
    src = frame_u8.astype(np.float64) / 255.0
    out = np.clip(np.rint(apply_lut(src, lut) * 255.0), 0, 255).astype(np.uint8)
    if mask is not None:
        out = np.where(mask[..., None], out, frame_u8)
    return out


def hex_to_linear(hx: str) -> np.ndarray:
    hx = hx.lstrip("#")
    return srgb_to_linear(np.array([int(hx[i:i + 2], 16) for i in (0, 2, 4)], dtype=np.float64) / 255.0)


def game_layer_screen_u8(hx: str) -> list[int]:
    """Screen bytes of an unlit game-layer colour (M_UM_GameLayer: LayerColor = FromSRGBColor(hex), emissive x
    EyeAdaptationInverse -> the scene value is the linear colour at any exposure) through the tone curve."""
    d = scene_to_display(hex_to_linear(hx)[None, :])[0]
    return [int(v) for v in np.clip(np.rint(d * 255.0), 0, 255)]


def ev_to_brightness(ev100: float) -> float:
    """Histogram min = max brightness of the fixed exposure of the board profiles (2^EV100, profile rev 4 note)."""
    return 2.0 ** ev100
