"""H2 texture post-process (system Python 3.10+, numpy/scipy/Pillow; no Blender).

    python textures.py <profile.json> <run_dir>

Reads the float bakes <run>/work/bake/{normal,ao,bc,rm}.npy (stage_bake.py) and the UV label rasters
<run>/work/uv-labels.npz (uv_check.py) and writes, for the master size (bake.size) and the runtime size (uv.runtime_px):
  <prefix>_BC.png         sRGB 8-bit RGB (linear bake -> sRGB OETF)
  <prefix>_N.png          tangent normal, DirectX (G = 1 - G of OpenGL), unit length, 8-bit RGB   (UE)
  <prefix>_N_OpenGL.png   the same, OpenGL                                                        (Blender)
  <prefix>_ORM.png        R = baked AO, G = roughness, B = metallic (Tripo PBR), linear 8-bit RGB
  <prefix>_TeamMask.png   linear 8-bit L: TeamColor weight (W4-B format, UE TeamMaskTexture .R)
Gutters: every texel not written by the bake takes the value of the nearest written texel (Euclidean distance
transform; the islands are >= min_padding_px apart, so a gutter texel takes its own island's colour). The runtime size
is a 2x2 box average in linear space (normals renormalised). Checks and statistics go to <run>/reports/textures-report.json.
"""

import json
import sys
from pathlib import Path

import numpy as np
from PIL import Image
from scipy import ndimage

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from textures_common import rasterise, sha256, write_json  # noqa: E402
import base_textures as BT  # noqa: E402

profile_path, run = Path(sys.argv[1]).resolve(), Path(sys.argv[2]).resolve()
P = json.loads(profile_path.read_text(encoding="utf-8"))
T = P["textures"]
N = int(P["bake"]["size"])
parts = sorted(P["lowpoly"]["parts"], key=lambda n: int(n.rsplit("_", 1)[1]))
labels = np.load(run / "work" / "uv-labels.npz")
part_lab, isl_lab = labels["part"], labels["island"]
covered = part_lab >= 0
bake = {k: np.load(run / "work" / "bake" / ("%s.npy" % k)).astype(np.float32) for k in ("normal", "ao", "bc", "rm")}
report = {"schema": "unmatched.h2-bake.textures-report/1", "profile_sha256": sha256(profile_path), "master_px": N,
          "runtime_px": int(P["uv"]["runtime_px"]), "inputs": {}, "checks": {}, "outputs": {}}
for k in bake:
    report["inputs"][k] = sha256(run / "work" / "bake" / ("%s.npy" % k))

# ------------------------------------------------------------------ coverage and gutter fill
written = bake["normal"][..., 3] > 0
for k in ("ao", "bc", "rm"):
    if not np.array_equal(written, bake[k][..., 3] > 0):
        report["checks"]["written_mask_%s_equals_normal" % k] = False
missed = covered & ~written
report["checks"]["texels_covered_by_uv"] = int(covered.sum())
report["checks"]["texels_written_by_bake"] = int(written.sum())
report["checks"]["texels_covered_not_written"] = int(missed.sum())
report["checks"]["texels_covered_not_written_fraction"] = round(float(missed.sum() / covered.sum()), 6)
report["checks"]["missed_by_part"] = {parts[k]: int((missed & (part_lab == k)).sum()) for k in range(len(parts))}
_d, (iy, ix) = ndimage.distance_transform_edt(~written, return_indices=True)


def fill(a):
    return a[iy, ix]


for k in bake:
    bake[k] = fill(bake[k])


# ------------------------------------------------------------------ channels
def srgb(lin):
    lin = np.clip(lin, 0.0, 1.0)
    return np.where(lin <= 0.0031308, lin * 12.92, 1.055 * np.power(lin, 1 / 2.4) - 0.055)


def q8(x):
    return np.clip(np.round(np.clip(x, 0, 1) * 255.0), 0, 255).astype(np.uint8)


def unit(nrm):
    ln = np.linalg.norm(nrm, axis=-1, keepdims=True)
    flat = ln[..., 0] < 1e-6
    out = nrm / np.maximum(ln, 1e-6)
    out[flat] = (0.0, 0.0, 1.0)
    return out


bc_lin = bake["bc"][..., :3]
n_gl = unit(bake["normal"][..., :3] * 2.0 - 1.0)
ao = bake["ao"][..., 0]
rough = bake["rm"][..., 1]
metal = bake["rm"][..., 2]

# normal statistics inside the islands (artifact indicators)
nz = n_gl[..., 2][covered]
report["checks"]["normal_inward_fraction"] = round(float((nz < 0).mean()), 6)
report["checks"]["normal_tilt_over_60deg_fraction"] = round(float((nz < 0.5).mean()), 6)
report["checks"]["normal_tilt_over_60deg_by_part"] = {parts[k]: round(float((n_gl[..., 2][part_lab == k] < 0.5).mean()), 5)
                                                     for k in range(len(parts))}
aoc = ao[covered]
g = T.get("ao_gate", {"min_range_p1_p99": 32, "occluded_below": 250, "min_occluded_fraction": 0.02})
ao8 = np.round(aoc * 255)
report["checks"]["ao_gate"] = {"p1": float(np.percentile(ao8, 1)), "p99": float(np.percentile(ao8, 99)),
                               "occluded_fraction": round(float((ao8 < g["occluded_below"]).mean()), 4),
                               "gate": g,
                               "passed": bool(np.percentile(ao8, 99) - np.percentile(ao8, 1) >= g["min_range_p1_p99"]
                                              and (ao8 < g["occluded_below"]).mean() >= g["min_occluded_fraction"])}
report["checks"]["tripo_roughness_mean_covered"] = round(float(rough[covered].mean()), 4)
report["checks"]["tripo_metallic_mean_covered"] = round(float(metal[covered].mean()), 4)
report["checks"]["tripo_metallic_fraction_over_0_5"] = round(float((metal[covered] > 0.5).mean()), 4)
report["checks"]["bc_linear_mean_covered"] = [round(float(c), 4) for c in bc_lin[covered].mean(0)]

# ------------------------------------------------------------------ optional metal rule (textures.metal_rule)
_d2, (jy, jx) = ndimage.distance_transform_edt(~covered, return_indices=True)
part_full = part_lab[jy, jx]
mr = T.get("metal_rule")
if mr:
    bs = srgb(bc_lin)
    mxx, mnn = bs.max(-1), bs.min(-1)
    sat = np.where(mxx > 1e-6, (mxx - mnn) / np.maximum(mxx, 1e-6), 0.0)
    rr, gg, bb = bs[..., 0], bs[..., 1], bs[..., 2]
    hue = np.degrees(np.arctan2(np.sqrt(3) * (gg - bb), 2 * rr - gg - bb)) % 360

    def ramp_up(x, lo_, w):
        return np.clip((x - lo_) / w + 0.5, 0, 1)

    hw = mr.get("ramp_deg", 5.0)
    m_hue = np.clip(np.minimum((hue - mr["hue_deg"][0]) / hw + 0.5, (mr["hue_deg"][1] - hue) / hw + 0.5), 0, 1)
    metal_mask = m_hue * ramp_up(sat, mr["s_min"], mr.get("ramp", 0.1)) * ramp_up(mxx, mr["v_min"], mr.get("ramp", 0.1))
    metal_mask *= np.isin(part_full, [parts.index(q) for q in mr["parts"]])
    metal_mask = ndimage.uniform_filter(metal_mask, size=3, mode="nearest")
    metal = metal * (1 - metal_mask) + float(mr["metallic"]) * metal_mask
    rough = rough * (1 - metal_mask) + float(mr["roughness"]) * metal_mask
    if mr.get("base_colour_linear"):
        # H3 (material library preset, mode preset-f0): the metal texels take the preset F0 colour, modulated by the
        # baked luminance relative to its mean inside the mask (amplitude bake_luminance_modulation)
        f0 = np.array(mr["base_colour_linear"], np.float32)
        lum_ = bc_lin @ np.array([0.2126, 0.7152, 0.0722], np.float32)
        sel_ = metal_mask > 0.5
        lmean = float(lum_[sel_].mean()) if sel_.any() else 1.0
        mod = 1.0 + float(mr.get("bake_luminance_modulation", 0.0)) * (lum_ / max(lmean, 1e-6) - 1.0)
        # preset ageing.cavityDarken: darken toward the baked AO (1 - k * (1 - AO)); keeps the relief of the band
        cav_k = float(mr.get("cavity_darken", 0.0))
        mod = mod * (1.0 - cav_k * (1.0 - np.clip(ao, 0.0, 1.0)))
        f0_px = np.clip(f0[None, None, :] * np.clip(mod, 0.0, None)[..., None], 0.0, 1.0)
        bc_before = bc_lin[sel_].mean(0) if sel_.any() else None
        bc_lin = bc_lin * (1 - metal_mask[..., None]) + f0_px * metal_mask[..., None]
        report["checks"].setdefault("metal_rule_colour", {
            "base_colour_linear": f0.tolist(), "bake_luminance_modulation": mr.get("bake_luminance_modulation", 0.0),
            "mask_luminance_mean_before": round(lmean, 4),
            "bc_linear_mean_before_after": [[round(float(c), 4) for c in bc_before] if bc_before is not None else None,
                                            [round(float(c), 4) for c in bc_lin[sel_].mean(0)] if sel_.any() else None]})
    report["checks"]["metal_rule"] = {"rule": mr, "texels_over_0_5": int((metal_mask > 0.5).sum()),
                                      "coverage_by_part": {q: round(float(metal_mask[part_lab == parts.index(q)].mean()), 4)
                                                           for q in mr["parts"]}}

# ------------------------------------------------------------------ H2.1 material rules (textures.materials, proposal)
MAT = T.get("materials")
mat_report = {}
if MAT:
    bs_ = srgb(bc_lin)
    vv = bs_.max(-1)
    ss = np.where(vv > 1e-6, (vv - bs_.min(-1)) / np.maximum(vv, 1e-6), 0.0)

    def ramp_below(x, hi, w):
        return np.clip((hi - x) / w + 0.5, 0, 1)

    def ramp_above(x, lo_, w):
        return np.clip((x - lo_) / w + 0.5, 0, 1)

    def in_parts(names):
        return np.isin(part_full, [parts.index(q) for q in names if q in parts])

    mm = metal_mask if mr else np.zeros((N, N))
    # talons: dark, desaturated keratin of the feet parts
    tl = MAT.get("talons")
    talon = np.zeros((N, N))
    if tl:
        talon = (ramp_below(ss, tl["s_max"], tl.get("ramp", 0.06)) * ramp_below(vv, tl["v_max"], tl.get("ramp", 0.06))
                 * in_parts(tl["parts"]))
        talon = ndimage.grey_opening(talon, size=(int(tl.get("open_px", 3)),) * 2)
        talon = ndimage.uniform_filter(talon, size=3, mode="nearest")
        vn = np.clip((vv - tl["v_max"] * 0.25) / max(tl["v_max"] * 0.75, 1e-6), 0, 1)
        r_t = tl["roughness"][0] + (tl["roughness"][1] - tl["roughness"][0]) * (1.0 - vn)
        rough = rough * (1 - talon) + r_t * talon
        metal = metal * (1 - talon)
        bc_lin = bc_lin * (1 - talon[..., None]) + bc_lin * float(tl.get("bc_scale", 1.0)) * talon[..., None]
        mat_report["talons"] = {"rule": tl, "texels_over_0_5": int((talon > 0.5).sum()),
                                "coverage_by_part": {q: round(float(talon[part_lab == parts.index(q)].mean()), 4)
                                                     for q in tl["parts"] if q in parts},
                                "roughness_mean": round(float(rough[talon > 0.5].mean()), 4) if (talon > 0.5).any() else None}
    # feathers: metallic 0, roughness remapped into [lo, hi]: half the part's own Tripo roughness rank, half the
    # baked AO (exposed vanes smoother, occluded roots rougher) - a specular breakup instead of one flat value
    fr = MAT.get("feathers")
    if fr:
        skin = np.zeros((N, N))
        if fr.get("skin"):
            sk = fr["skin"]
            skin = (ramp_above(vv, sk["v_min"], 0.05) * ramp_below(ss, sk["s_max"], 0.05) * in_parts(sk["parts"]))
            skin = ndimage.uniform_filter(skin, size=3, mode="nearest")
        feather = in_parts(fr["parts"]) * (1 - skin) * (1 - mm) * (1 - talon)
        lo_r, hi_r = fr["roughness"]
        t_r = np.zeros((N, N))
        for q in fr["parts"]:
            if q not in parts:
                continue
            m_ = part_full == parts.index(q)
            if not m_.any():
                continue
            p5, p95 = np.percentile(rough[m_], [5, 95])
            t_r[m_] = np.clip((rough[m_] - p5) / max(p95 - p5, 1e-4), 0, 1)
        a5, a95 = np.percentile(ao[covered], [5, 95])
        t_ao = 1.0 - np.clip((ao - a5) / max(a95 - a5, 1e-4), 0, 1)
        w_ao = float(fr.get("ao_weight", 0.5))
        r_f = lo_r + (hi_r - lo_r) * np.clip((1 - w_ao) * t_r + w_ao * t_ao, 0, 1)
        rough_tripo = rough.copy()
        rough = rough * (1 - feather) + r_f * feather
        metal = metal * (1 - feather)
        fm = feather > 0.5
        sk_r = (fr.get("skin") or {}).get("roughness")
        if sk_r:
            # H3 (material library preset "skin"): skin texels of the head part remapped into the preset range by the
            # same rank (half the Tripo roughness rank inside the skin mask, half the baked AO), metallic 0
            skin_w = skin * (1 - mm) * (1 - talon)
            sm_ = skin_w > 0.5
            if sm_.any():
                p5s, p95s = np.percentile(rough_tripo[sm_], [5, 95])
                t_s = np.clip((rough_tripo - p5s) / max(p95s - p5s, 1e-4), 0, 1)
                r_s = sk_r[0] + (sk_r[1] - sk_r[0]) * np.clip((1 - w_ao) * t_s + w_ao * t_ao, 0, 1)
                rough = rough * (1 - skin_w) + r_s * skin_w
                metal = metal * (1 - skin_w)
                mat_report["skin"] = {"roughness_rule": sk_r, "texels_over_0_5": int(sm_.sum()),
                                      "roughness_p1_p50_p99": [round(float(x), 4) for x in np.percentile(rough[sm_], [1, 50, 99])]}
        mat_report["feathers"] = {"rule": fr, "texels_over_0_5": int(fm.sum()),
                                  "roughness_p1_p50_p99": [round(float(x), 4) for x in np.percentile(rough[fm], [1, 50, 99])],
                                  "metallic_max": round(float(metal[fm].max()), 4),
                                  "metallic_max_feather_ge_0_99": round(float(metal[feather >= 0.99].max()), 4),
                                  "texels_feather_over_0_5_metallic_over_0_05": int((fm & (metal > 0.05)).sum()),
                                  "metallic_note": "texels with metallic > 0 inside the feather mask are the 3x3 soft edge "
                                                   "of the gold bands (textures.metal_rule)",
                                  "skin_texels_over_0_5": int((skin > 0.5).sum())}
    # face readability: cavity from the baked AO and a darkening-only local contrast of the painted features
    fc = MAT.get("face_cavity")
    if fc:
        tris = np.load(run / "work" / "uv-tris.npz")
        sel = (tris["density_factor"] >= float(fc.get("density_factor_min", 2.0))) &               np.isin(tris["part"], [parts.index(q) for q in fc["parts"]])
        flab, _fcov = rasterise(tris["uv"][sel], np.ones(int(sel.sum()), np.int32), N)
        face = (flab >= 0).astype(np.float64)
        face = ndimage.uniform_filter(ndimage.binary_dilation(face > 0, iterations=2).astype(np.float64), size=5)
        lum = bc_lin @ np.array([0.2126, 0.7152, 0.0722])
        cav = np.clip((ndimage.gaussian_filter(ao, float(fc.get("cavity_sigma_px", 6))) - ao) *
                      float(fc.get("cavity_gain", 4.0)), 0, 1)
        det = lum - ndimage.gaussian_filter(lum, float(fc.get("detail_sigma_px", 3)))
        dark = np.clip(-det / np.maximum(lum, 1e-3), 0, 1)
        k = 1.0 - face * (float(fc.get("cavity_strength", 0.5)) * cav + float(fc.get("contrast_strength", 0.6)) * dark)
        k = np.clip(k, float(fc.get("min_factor", 0.45)), 1.0)
        lum_before = lum[face > 0.5]
        bc_lin = bc_lin * k[..., None]
        lum_after = (bc_lin @ np.array([0.2126, 0.7152, 0.0722]))[face > 0.5]
        mat_report["face_cavity"] = {"rule": fc, "face_texels": int((face > 0.5).sum()),
                                     "factor_p1_p50": [round(float(x), 4) for x in np.percentile(k[face > 0.5], [1, 50])],
                                     "luminance_std_before_after": [round(float(lum_before.std()), 4),
                                                                    round(float(lum_after.std()), 4)],
                                     "luminance_p5_before_after": [round(float(np.percentile(lum_before, 5)), 4),
                                                                   round(float(np.percentile(lum_after, 5)), 4)]}
    report["checks"]["materials"] = mat_report
    report["checks"]["roughness_mean_covered_after"] = round(float(rough[covered].mean()), 4)

# ------------------------------------------------------------------ TeamMask (W4-B hsv-band-cells on the sRGB BC)
tm = T["team_mask"]
bc_s = srgb(bc_lin)
mx, mn = bc_s.max(-1), bc_s.min(-1)
v = mx
s = np.where(mx > 1e-6, (mx - mn) / np.maximum(mx, 1e-6), 0.0)


def band_upper(x, hi, ramp):
    return np.clip((hi + ramp - x) / (2 * ramp) if ramp > 0 else (x <= hi).astype(np.float32), 0, 1)


mask = np.ones((N, N), np.float32)
if "v_max" in tm:
    mask *= band_upper(v, tm["v_max"], tm.get("ramp", 0.0))
if "s_max" in tm:
    mask *= band_upper(s, tm["s_max"], tm.get("ramp", 0.0))
cell_idx = [parts.index(p) for p in tm["parts"]]
in_cells = np.isin(part_lab, cell_idx)
# gutter texels belong to the nearest island's part (part_full)
mask *= np.isin(part_full, cell_idx)
if tm.get("blur", "3x3") == "3x3":
    mask = ndimage.uniform_filter(mask, size=3, mode="nearest")
report["checks"]["team_mask"] = {
    "rule": tm, "coverage_of_cells": round(float(mask[in_cells].mean()), 4),
    "coverage_of_figure": round(float(mask[covered].mean()), 4),
    "coverage_by_part": {p: round(float(mask[part_lab == parts.index(p)].mean()), 4) for p in parts}}

# ------------------------------------------------------------------ outputs
prefix = T["prefix"]


def box2(a):
    h, w = a.shape[:2]
    return a.reshape(h // 2, 2, w // 2, 2, *a.shape[2:]).mean(axis=(1, 3))


def save(arr, path, mode):
    path.parent.mkdir(parents=True, exist_ok=True)
    Image.fromarray(np.flipud(arr), mode).save(path, optimize=False, compress_level=9)
    return {"path": str(path.relative_to(run)).replace("\\", "/"), "sha256": sha256(path),
            "bytes": path.stat().st_size, "size": [int(arr.shape[1]), int(arr.shape[0])], "mode": mode}


levels = {"master": 1}
rt = int(P["uv"]["runtime_px"])
f = N // rt
if f > 1:
    levels["runtime"] = f
for level, fac in levels.items():
    bcl, ngl, a_, r_, m_, tmk = bc_lin, n_gl, ao, rough, metal, mask
    for _ in range(int(np.log2(fac))):
        bcl, ngl, a_, r_, m_, tmk = box2(bcl), unit(box2(ngl)), box2(a_), box2(r_), box2(m_), box2(tmk)
    size = bcl.shape[0]
    d = run / "textures" / ("%dk" % (size // 1024))
    outs = {}
    outs["BC"] = save(q8(srgb(bcl)), d / ("%s_BC.png" % prefix), "RGB")
    n8 = q8(ngl * 0.5 + 0.5)
    outs["N_OpenGL"] = save(n8, d / ("%s_N_OpenGL.png" % prefix), "RGB")
    dx = n8.copy()
    dx[..., 1] = 255 - dx[..., 1]
    outs["N"] = save(dx, d / ("%s_N.png" % prefix), "RGB")
    outs["ORM"] = save(np.stack([q8(a_), q8(r_), q8(m_)], -1), d / ("%s_ORM.png" % prefix), "RGB")
    outs["TeamMask"] = save(q8(tmk), d / ("%s_TeamMask.png" % prefix), "L")
    # format checks on the written files
    back = {k: np.array(Image.open(run / o["path"])) for k, o in outs.items()}
    ndx = back["N"].astype(np.int32)
    ngl8 = back["N_OpenGL"].astype(np.int32)
    vec = back["N_OpenGL"].astype(np.float32) / 255 * 2 - 1
    ln = np.linalg.norm(vec, axis=-1)
    outs["_checks"] = {
        "directx_equals_opengl_with_inverted_g": bool(np.array_equal(ndx[..., 0], ngl8[..., 0]) and
                                                      np.array_equal(ndx[..., 2], ngl8[..., 2]) and
                                                      np.array_equal(ndx[..., 1], 255 - ngl8[..., 1])),
        "normal_length_within_0_02_fraction": round(float((np.abs(ln - 1) < 0.02).mean()), 5),
        "orm_r_is_baked_ao_not_constant": bool(back["ORM"][..., 0].std() > 1.0)}
    report["outputs"][level] = outs

# ------------------------------------------------------------------ H2.1 metal base textures (base_material)
BM = P.get("base_material")
if BM:
    bt = BT.make(BM, int(BM["texture_px"]))
    d = run / "textures" / ("base_%dk" % max(1, int(BM["texture_px"]) // 1024))
    outs = {}
    bprefix = BM["texture_prefix"]
    outs["BC"] = save(bt["BC"][::-1], d / ("%s_BC.png" % bprefix), "RGB")
    outs["N_OpenGL"] = save(bt["N_OpenGL"][::-1], d / ("%s_N_OpenGL.png" % bprefix), "RGB")
    outs["N"] = save(bt["N"][::-1], d / ("%s_N.png" % bprefix), "RGB")
    outs["ORM"] = save(bt["ORM"][::-1], d / ("%s_ORM.png" % bprefix), "RGB")
    outs["_stats"] = bt["stats"]
    report["outputs"]["base"] = outs

# small preview of the four maps (for the report; 1K JPEG)
prev = run / "preview"
prev.mkdir(exist_ok=True)
for k in ("BC", "N", "ORM", "TeamMask"):
    im = Image.open(run / report["outputs"]["master"][k]["path"])
    im = im.convert("RGB").resize((1024, 1024), Image.LANCZOS)
    im.save(prev / ("atlas_%s_1k.jpg" % k), quality=90)
write_json(run / "reports" / "textures-report.json", report)
print("TEXTURES_OK", json.dumps(report["checks"])[:1500])
