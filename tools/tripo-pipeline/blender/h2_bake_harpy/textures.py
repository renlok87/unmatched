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
from textures_common import sha256, write_json  # noqa: E402

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
    report["checks"]["metal_rule"] = {"rule": mr, "texels_over_0_5": int((metal_mask > 0.5).sum()),
                                      "coverage_by_part": {q: round(float(metal_mask[part_lab == parts.index(q)].mean()), 4)
                                                           for q in mr["parts"]}}

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

# small preview of the four maps (for the report; 1K JPEG)
prev = run / "preview"
prev.mkdir(exist_ok=True)
for k in ("BC", "N", "ORM", "TeamMask"):
    im = Image.open(run / report["outputs"]["master"][k]["path"])
    im = im.convert("RGB").resize((1024, 1024), Image.LANCZOS)
    im.save(prev / ("atlas_%s_1k.jpg" % k), quality=90)
write_json(run / "reports" / "textures-report.json", report)
print("TEXTURES_OK", json.dumps(report["checks"])[:1500])
