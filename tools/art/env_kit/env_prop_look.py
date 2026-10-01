"""ENV-MAPS P4 track B: material 'look' of the environment kit props (recolour + emissive accents, no new textures).

Concept review 2026-10-01 (docs/game-design/evidence/ENV-MAPS/p2-frames-2026-10-01/concept-review.json) asks for
albedo changes on props whose committed BC textures should stay as they are (gap 2 cherry blossom, gap 7 forest trees,
gap 15 cypress baubles) and for emissive-only warm accents (gap 13 lantern glass, gap 14 more small warm sources, no
new lights). M_UM_Figure, the parent of the kit MIs so far, has neither a selective recolour nor a texture emissive.
This module defines a small master for the kit, M_EnvProp, whose parameters do both from the existing BC:

  sRGB  s   = linear_to_srgb(BC)                      (the windows are measured on the PNG values, so they work in sRGB)
  HSV   h,S,V of s
  region w  = hue window x saturation window x value window   (RegionWindow = hueDeg, halfWidthDeg, satMin, valMin;
              soft edges: WindowSoft.x deg of hue, WindowSoft.y of S / V; halfWidthDeg < 0 = no region)
  base      = lerp( hsv2rgb(h, S x RestAdjust.x, V x RestAdjust.y),
                    hsv2rgb(h + RegionAdjust.x, S x RegionAdjust.y, V x RegionAdjust.z), w )   -> back to linear
  emissive  = BC x w_e x EmissiveColor x EmissiveIntensity       (w_e = the same window with EmissiveWindow)
  normal / roughness / metallic / AO as M_UM_Figure at its neutral defaults: N, lerp(RoughnessMin, RoughnessMax,
  ORM.G), ORM.B, ORM.R.

The same HLSL strings (HLSL_ALBEDO / HLSL_EMISSIVE) are built into the UE material by ue_import_env_kit.py and mirrored
here in numpy (apply_look), so the look is checked on the committed textures without UE: --check prints the measured
region statistics before / after against the targets in the look file and exits 1 when a target is missed.

Look file: art/pipeline-candidates/ASSET-ENV-KIT-001/20260930-tripo-h31/scripts/env-prop-look.json
(schema unmatched.env-prop-look/1). Only props listed there move to M_EnvProp; the others keep M_UM_Figure unchanged.

  python -B tools/art/env_kit/env_prop_look.py --check                 # targets on the committed BC textures
  python -B tools/art/env_kit/env_prop_look.py --previews <dir>        # before / after BC + emissive PNGs (scratch)

Status: the values are 'предложено' (proposed) - measured on textures here, in UE frames by the integrate stage.
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
RUN_DEFAULT = REPO / "art" / "pipeline-candidates" / "ASSET-ENV-KIT-001" / "20260930-tripo-h31"
LOOK_DEFAULT = RUN_DEFAULT / "scripts" / "env-prop-look.json"
SCHEMA = "unmatched.env-prop-look/1"
MASTER_PATH = "/Game/EnvKit/Shared/M_EnvProp"
# MI parameter names of M_EnvProp (the texture names are those of M_UM_Figure, so the kit binds the same way)
TEX_PARAMS = {"BC": "BaseColorTexture", "N": "NormalTexture", "ORM": "ORMTexture"}
VECTOR_DEFAULTS = {  # neutral: no region, no recolour, no emissive
    "RegionWindow": (0.0, -1.0, 0.0, 0.0),
    "RegionAdjust": (0.0, 1.0, 1.0, 0.0),
    "RestAdjust": (1.0, 1.0, 0.0, 0.0),
    "WindowSoft": (8.0, 0.06, 0.0, 0.0),
    "EmissiveWindow": (0.0, -1.0, 0.0, 0.0),
    "EmissiveColor": (1.0, 0.62, 0.32, 1.0),
}
SCALAR_DEFAULTS = {"EmissiveIntensity": 0.0, "RoughnessMin": 0.0, "RoughnessMax": 1.0, "NormalStrength": 1.0}

# ------------------------------------------------------------------------------------------------ HLSL (Custom nodes)
# Inputs: C (float3, the BC sample: linear), Win (float4), Adj (float4), Rest (float4), Soft (float4).
# Plain expressions only (no vector ?: - deprecated in HLSL 2021 / dxc), every smoothstep edge pair kept apart.
_HLSL_COMMON = """float3 lc = saturate(C);
float3 s = lerp(lc * 12.92, 1.055 * pow(max(lc, 1e-6), 1.0 / 2.4) - 0.055, step(0.0031308, lc));
float4 K = float4(0.0, -1.0 / 3.0, 2.0 / 3.0, -1.0);
float4 p = lerp(float4(s.bg, K.wz), float4(s.gb, K.xy), step(s.b, s.g));
float4 q = lerp(float4(p.xyw, s.r), float4(s.r, p.yzx), step(p.x, s.r));
float d = q.x - min(q.w, q.y);
float3 hsv = float3(abs(q.z + (q.w - q.y) / (6.0 * d + 1e-10)), d / (q.x + 1e-10), q.x);
float sh = max(Soft.x, 0.01);
float ss = max(Soft.y, 0.001);
float hd = abs(frac(hsv.x - Win.x / 360.0 + 0.5) - 0.5) * 360.0;
float w = (1.0 - smoothstep(Win.y, Win.y + sh, hd)) * smoothstep(Win.z - ss, Win.z + ss, hsv.y)
        * smoothstep(Win.w - ss, Win.w + ss, hsv.z) * step(0.0, Win.y);
"""
HLSL_ALBEDO = _HLSL_COMMON + """float3 hr = float3(frac(hsv.x + Adj.x / 360.0), saturate(hsv.y * Adj.y), saturate(hsv.z * Adj.z));
float3 hb = float3(hsv.x, saturate(hsv.y * Rest.x), saturate(hsv.z * Rest.y));
float3 one = float3(1.0, 1.0, 1.0);
float3 kk = float3(1.0, 2.0 / 3.0, 1.0 / 3.0);
float3 rr = hr.z * lerp(one, saturate(abs(frac(hr.x + kk) * 6.0 - 3.0) - 1.0), hr.y);
float3 rb = hb.z * lerp(one, saturate(abs(frac(hb.x + kk) * 6.0 - 3.0) - 1.0), hb.y);
float3 o = saturate(lerp(rb, rr, w));
return lerp(o / 12.92, pow((o + 0.055) / 1.055, 2.4), step(0.04045, o));
"""
# Inputs: C, Win (= EmissiveWindow), Soft, Col (float3), Intensity (float)
HLSL_EMISSIVE = _HLSL_COMMON + """return C * w * Col * max(Intensity, 0.0);
"""
HLSL_INPUTS = {
    "albedo": (("C", "float3"), ("Win", "float4"), ("Adj", "float4"), ("Rest", "float4"), ("Soft", "float4")),
    "emissive": (("C", "float3"), ("Win", "float4"), ("Soft", "float4"), ("Col", "float3"), ("Intensity", "float")),
}


# ------------------------------------------------------------------------------------------------ look file
def load_look(path: Path = LOOK_DEFAULT) -> dict:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    errors = validate_look(data)
    if errors:
        raise ValueError(f"{path}: " + "; ".join(errors))
    return data


def _nums(v, n: int) -> bool:
    return (isinstance(v, (list, tuple)) and len(v) == n
            and all(isinstance(x, (int, float)) and not isinstance(x, bool) and math.isfinite(x) for x in v))


def _window(w) -> tuple:
    return (float(w["hueDeg"]), float(w["halfWidthDeg"]), float(w["satMin"]), float(w["valMin"]))


def validate_look(data: dict) -> list[str]:
    err = []
    if data.get("schema") != SCHEMA:
        err.append(f"schema {data.get('schema')!r} != {SCHEMA}")
    if data.get("master") != MASTER_PATH:
        err.append(f"master {data.get('master')!r} != {MASTER_PATH}")
    props = data.get("props")
    if not isinstance(props, dict) or not props:
        return err + ["props missing / empty"]
    for name, e in props.items():
        if not isinstance(e, dict):
            err.append(f"{name}: not an object")
            continue
        for key in ("region", "emissive"):
            sub = e.get(key)
            if sub is None:
                continue
            win = sub.get("window")
            try:
                h, half, smin, vmin = _window(win)
            except (TypeError, KeyError, ValueError):
                err.append(f"{name}.{key}.window needs hueDeg / halfWidthDeg / satMin / valMin")
                continue
            if not (0 <= h < 360 and 0 < half <= 180 and 0 <= smin <= 1 and 0 <= vmin <= 1):
                err.append(f"{name}.{key}.window out of range ({h}, {half}, {smin}, {vmin})")
        reg = e.get("region")
        if reg is not None:
            a = reg.get("adjust", {})
            if not (-180 <= float(a.get("hueShiftDeg", 0)) <= 180 and 0 <= float(a.get("satMul", 1)) <= 2
                    and 0 <= float(a.get("valMul", 1)) <= 2):
                err.append(f"{name}.region.adjust out of range")
        rest = e.get("rest", {})
        if not (0 <= float(rest.get("satMul", 1)) <= 2 and 0 <= float(rest.get("valMul", 1)) <= 2):
            err.append(f"{name}.rest out of range")
        em = e.get("emissive")
        if em is not None:
            if not _nums(em.get("colorLinear"), 3) or min(em["colorLinear"]) < 0:
                err.append(f"{name}.emissive.colorLinear must be 3 numbers >= 0")
            if not (isinstance(em.get("intensity"), (int, float)) and 0 < em["intensity"] <= 50):
                err.append(f"{name}.emissive.intensity must be in (0, 50]")
        if reg is None and em is None and not e.get("rest"):
            err.append(f"{name}: no region, rest or emissive - leave it on M_UM_Figure instead")
        soft = e.get("soft", data.get("soft", {}))
        if not (0 < float(soft.get("hueDeg", 8)) <= 60 and 0 < float(soft.get("sv", 0.06)) <= 0.3):
            err.append(f"{name}: soft out of range")
    return err


def mi_params(data: dict, name: str) -> dict:
    """The M_EnvProp MI parameters of one prop: {'scalar': {...}, 'vector': {name: rgba}} (all parameters, so the MI
    is complete and comparable)."""
    e = data["props"][name]
    soft = e.get("soft", data.get("soft", {}))
    vec = dict(VECTOR_DEFAULTS)
    scal = dict(SCALAR_DEFAULTS)
    vec["WindowSoft"] = (float(soft.get("hueDeg", 8.0)), float(soft.get("sv", 0.06)), 0.0, 0.0)
    reg = e.get("region")
    if reg is not None:
        vec["RegionWindow"] = _window(reg["window"])
        a = reg.get("adjust", {})
        vec["RegionAdjust"] = (float(a.get("hueShiftDeg", 0.0)), float(a.get("satMul", 1.0)),
                               float(a.get("valMul", 1.0)), 0.0)
    rest = e.get("rest", {})
    vec["RestAdjust"] = (float(rest.get("satMul", 1.0)), float(rest.get("valMul", 1.0)), 0.0, 0.0)
    em = e.get("emissive")
    if em is not None:
        vec["EmissiveWindow"] = _window(em["window"])
        vec["EmissiveColor"] = tuple(float(v) for v in em["colorLinear"]) + (1.0,)
        scal["EmissiveIntensity"] = float(em["intensity"])
    for k in ("RoughnessMin", "RoughnessMax", "NormalStrength"):
        if k in e.get("surface", {}):
            scal[k] = float(e["surface"][k])
    return {"scalar": scal, "vector": {k: tuple(float(x) for x in v) for k, v in vec.items()}}


# ------------------------------------------------------------------------------------------------ numpy mirror
def _np():
    import numpy as np  # lazy: the UE side imports this module without numpy
    return np


def srgb_to_linear(s):
    np = _np()
    s = np.clip(s, 0.0, 1.0)
    return np.where(s >= 0.04045, ((s + 0.055) / 1.055) ** 2.4, s / 12.92)


def linear_to_srgb(c):
    np = _np()
    c = np.clip(c, 0.0, 1.0)
    return np.where(c >= 0.0031308, 1.055 * np.maximum(c, 1e-6) ** (1.0 / 2.4) - 0.055, c * 12.92)


def rgb_to_hsv(s):
    """Same formula as the HLSL (Hocevar): h in 0..1."""
    np = _np()
    r, g, b = s[..., 0], s[..., 1], s[..., 2]
    gb = (g >= b)[..., None]
    p = np.where(gb, np.stack([g, b, np.zeros_like(g), np.full_like(g, -1.0 / 3.0)], -1),
                 np.stack([b, g, np.full_like(g, -1.0), np.full_like(g, 2.0 / 3.0)], -1))
    rp = (r >= p[..., 0])[..., None]
    q = np.where(rp, np.stack([r, p[..., 1], p[..., 2], p[..., 0]], -1),
                 np.stack([p[..., 0], p[..., 1], p[..., 3], r], -1))
    d = q[..., 0] - np.minimum(q[..., 3], q[..., 1])
    h = np.abs(q[..., 2] + (q[..., 3] - q[..., 1]) / (6.0 * d + 1e-10))
    return np.stack([h, d / (q[..., 0] + 1e-10), q[..., 0]], -1)


def hsv_to_rgb(hsv):
    np = _np()
    h, s, v = hsv[..., 0:1], hsv[..., 1:2], hsv[..., 2:3]
    k = np.array([1.0, 2.0 / 3.0, 1.0 / 3.0])
    return v * (1.0 + (np.clip(np.abs(np.mod(h + k, 1.0) * 6.0 - 3.0) - 1.0, 0, 1) - 1.0) * s)


def _smoothstep(a, b, x):
    np = _np()
    t = np.clip((x - a) / (b - a), 0.0, 1.0)
    return t * t * (3.0 - 2.0 * t)


def window_weight(hsv, win: tuple, soft: tuple):
    np = _np()
    h0, half, smin, vmin = win
    if half < 0:
        return np.zeros(hsv.shape[:-1])
    sh, ss = max(soft[0], 0.01), max(soft[1], 0.001)
    hd = np.abs(np.mod(hsv[..., 0] - h0 / 360.0 + 0.5, 1.0) - 0.5) * 360.0
    return ((1.0 - _smoothstep(half, half + sh, hd)) * _smoothstep(smin - ss, smin + ss, hsv[..., 1])
            * _smoothstep(vmin - ss, vmin + ss, hsv[..., 2]))


def apply_look(bc_srgb, params: dict) -> dict:
    """bc_srgb: float array (..., 3) in 0..1 (the PNG values). Returns {'srgb': base colour (sRGB 0..1), 'linear',
    'emissive' (linear, pre-exposure), 'w' (region weight), 'we' (emissive weight), 'hsv' (before)} - the HLSL in
    numpy (the texture sampler hands the shader linear values; srgb -> linear -> srgb is the identity here)."""
    np = _np()
    v = params["vector"]
    lin = srgb_to_linear(bc_srgb)
    s = linear_to_srgb(lin)
    hsv = rgb_to_hsv(s)
    soft = v["WindowSoft"]
    w = window_weight(hsv, v["RegionWindow"], soft)
    adj, rest = v["RegionAdjust"], v["RestAdjust"]
    hr = np.stack([np.mod(hsv[..., 0] + adj[0] / 360.0, 1.0), np.clip(hsv[..., 1] * adj[1], 0, 1),
                   np.clip(hsv[..., 2] * adj[2], 0, 1)], -1)
    hb = np.stack([hsv[..., 0], np.clip(hsv[..., 1] * rest[0], 0, 1), np.clip(hsv[..., 2] * rest[1], 0, 1)], -1)
    o = np.clip(hsv_to_rgb(hb) * (1.0 - w[..., None]) + hsv_to_rgb(hr) * w[..., None], 0, 1)
    we = window_weight(hsv, v["EmissiveWindow"], soft)
    col = np.asarray(v["EmissiveColor"][:3])
    emissive = lin * we[..., None] * col * max(params["scalar"]["EmissiveIntensity"], 0.0)
    return {"srgb": o, "linear": srgb_to_linear(o), "emissive": emissive, "w": w, "we": we, "hsv": hsv}


def circular_mean_deg(h01, weights) -> float:
    np = _np()
    a = h01 * 2 * math.pi
    sw = float(weights.sum())
    if sw <= 0:
        return float("nan")
    return float(np.degrees(np.arctan2((np.sin(a) * weights).sum() / sw, (np.cos(a) * weights).sum() / sw)) % 360)


def load_bc(name: str, run: Path = RUN_DEFAULT, size: int = 512):
    """The committed BC of SM_Env_<name> as sRGB float (size x size, box-filtered: statistics only)."""
    np = _np()
    from PIL import Image
    img = Image.open(run / "export" / f"T_Env_{name}_BC.png").convert("RGB")
    if size and img.size[0] != size:
        img = img.resize((size, size), Image.BOX)
    return np.asarray(img, np.float32) / 255.0


def measure(name: str, data: dict, run: Path = RUN_DEFAULT, size: int = 512) -> dict:
    """Region / rest / emissive statistics of one prop's look on its committed BC (texture space, not a render)."""
    np = _np()
    bc = load_bc(name, run, size)
    params = mi_params(data, name)
    out = apply_look(bc, params)
    hsv0 = out["hsv"]
    hsv1 = rgb_to_hsv(out["srgb"])
    w, we = out["w"], out["we"]
    rest = 1.0 - w
    res = {"name": name, "regionFraction": round(float((w > 0.5).mean()), 4),
           "emissiveFraction": round(float((we > 0.5).mean()), 4)}

    def stats(hsv, wt):
        sw = float(wt.sum())
        if sw <= 1e-6:
            return None
        return {"hueDeg": round(circular_mean_deg(hsv[..., 0], wt), 1),
                "sat": round(float((hsv[..., 1] * wt).sum() / sw), 4),
                "val": round(float((hsv[..., 2] * wt).sum() / sw), 4)}
    if (w > 0.5).any():
        m = (w > 0.5).astype(np.float64)
        res["region"] = {"before": stats(hsv0, m), "after": stats(hsv1, m)}
        res["region"]["valRatio"] = round(res["region"]["after"]["val"] / max(res["region"]["before"]["val"], 1e-6), 4)
        res["region"]["satRatio"] = round(res["region"]["after"]["sat"] / max(res["region"]["before"]["sat"], 1e-6), 4)
    m = (rest > 0.5).astype(np.float64)
    res["rest"] = {"before": stats(hsv0, m), "after": stats(hsv1, m)}
    if res["rest"]["before"] and res["rest"]["after"]:
        res["rest"]["valRatio"] = round(res["rest"]["after"]["val"] / max(res["rest"]["before"]["val"], 1e-6), 4)
        res["rest"]["satRatio"] = round(res["rest"]["after"]["sat"] / max(res["rest"]["before"]["sat"], 1e-6), 4)
    if (we > 0.5).any():
        m = we > 0.5
        lum = out["emissive"] @ np.array([0.2126, 0.7152, 0.0722])
        res["emissive"] = {"meanLuminance": round(float(lum[m].mean()), 4),
                           "p90Luminance": round(float(np.percentile(lum[m], 90)), 4),
                           "intensity": params["scalar"]["EmissiveIntensity"]}
    lum0 = srgb_to_linear(bc) @ np.array([0.2126, 0.7152, 0.0722])
    lum1 = out["linear"] @ np.array([0.2126, 0.7152, 0.0722])
    res["albedoLuminance"] = {"before": round(float(lum0.mean()), 4), "after": round(float(lum1.mean()), 4)}
    return res


def check_targets(name: str, data: dict, res: dict) -> list[str]:
    """The 'target' block of a prop: hueDeg [lo, hi], sat [lo, hi], valRatio [lo, hi] (region), restValRatio /
    restSatRatio [lo, hi], regionFraction / emissiveFraction [lo, hi], emissiveMeanLuminance [lo, hi]."""
    t = data["props"][name].get("target", {})
    bad = []

    def rng(key, got):
        lo, hi = t[key]
        if got is None or not (lo <= got <= hi):
            bad.append(f"{name}: {key} {got} not in [{lo}, {hi}]")
    reg = res.get("region") or {}
    after = reg.get("after") or {}
    for key, got in (("hueDeg", after.get("hueDeg")), ("sat", after.get("sat")), ("valRatio", reg.get("valRatio")),
                     ("satRatio", reg.get("satRatio")),
                     ("restValRatio", (res.get("rest") or {}).get("valRatio")),
                     ("restSatRatio", (res.get("rest") or {}).get("satRatio")),
                     ("regionFraction", res.get("regionFraction")),
                     ("emissiveFraction", res.get("emissiveFraction")),
                     ("emissiveMeanLuminance", (res.get("emissive") or {}).get("meanLuminance"))):
        if key in t:
            rng(key, got)
    return bad


def write_previews(name: str, data: dict, out_dir: Path, run: Path = RUN_DEFAULT, size: int = 1024) -> list[Path]:
    """Scratch previews: <name>-before.png / -after.png (BC), -emissive.png (tonemapped x exposure 0.2), -mask.png."""
    np = _np()
    from PIL import Image
    out_dir.mkdir(parents=True, exist_ok=True)
    bc = load_bc(name, run, size)
    out = apply_look(bc, mi_params(data, name))
    em = out["emissive"] * 0.2  # ~ the night profiles' fixed exposure (EV100 2.05)
    em = em / (1.0 + em)
    paths = []
    for tag, img in (("before", bc), ("after", out["srgb"]), ("emissive", linear_to_srgb(em)),
                     ("mask", np.stack([out["w"], out["we"], np.zeros_like(out["w"])], -1))):
        p = out_dir / f"T_Env_{name}-{tag}.png"
        Image.fromarray((np.clip(img, 0, 1) * 255 + 0.5).astype(np.uint8)).save(p)
        paths.append(p)
    return paths


def main(argv: list | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n", 1)[0])
    ap.add_argument("--look", default=str(LOOK_DEFAULT))
    ap.add_argument("--run", default=str(RUN_DEFAULT))
    ap.add_argument("--check", action="store_true", help="measure every prop's look on its BC against its targets")
    ap.add_argument("--previews", default=None, help="write before / after / emissive / mask PNGs here (scratch)")
    ap.add_argument("--json", default=None, help="write the measurements here")
    args = ap.parse_args(argv)
    data = load_look(Path(args.look))
    run = Path(args.run)
    report, bad = {"schema": "unmatched.env-prop-look-check/1", "look": str(args.look), "props": {}}, []
    for name in data["props"]:
        res = measure(name, data, run)
        report["props"][name] = res
        miss = check_targets(name, data, res)
        bad += miss
        reg = res.get("region")
        line = f"{name:<14} region {res['regionFraction']:.3f}"
        if reg:
            b, a = reg["before"], reg["after"]
            line += (f" H {b['hueDeg']:.0f}->{a['hueDeg']:.0f} S {b['sat']:.2f}->{a['sat']:.2f} "
                     f"V {b['val']:.2f}->{a['val']:.2f} (x{reg['valRatio']:.2f})")
        rs = res.get("rest") or {}
        if rs.get("valRatio") is not None and (abs(rs["valRatio"] - 1) > 0.005 or abs(rs["satRatio"] - 1) > 0.005):
            line += f" | rest S x{rs['satRatio']:.2f} V x{rs['valRatio']:.2f}"
        if res.get("emissive"):
            line += (f" | emissive {res['emissiveFraction']:.3f} of texels, mean lum {res['emissive']['meanLuminance']:.2f}"
                     f" (x{res['emissive']['intensity']:g})")
        print(("MISS " if miss else "ok   ") + line)
        if args.previews:
            write_previews(name, data, Path(args.previews), run)
    for b in bad:
        print("  TARGET " + b)
    report["ok"] = not bad
    if args.json:
        Path(args.json).write_text(json.dumps(report, indent=1, ensure_ascii=False), encoding="utf-8")
    print(f"ENVPROP-LOOK {'ok' if not bad else 'failed'} props={len(data['props'])}")
    return 0 if not bad else 1


if __name__ == "__main__":
    sys.exit(main())
