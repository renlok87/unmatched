"""Stage `maps` (system python: numpy, Pillow, scipy): textures of the H2 atlas from the Cycles bakes.

python maps.py <profile.json>

Inputs: work/uv/<object>.npz (UV triangles, part, cap, island, face normal, corner positions) and
work/bake/<map>.npy (float16 RGBA 4K, row 0 = bottom). Steps:
 1. rasterise the UV triangles at atlas_px (pixel centres, strict inside test): part / island / object maps,
    overlap count, coverage; island gaps (EDT of the island map); texel density per part in the game frame;
 2. per map: texels the bake wrote (alpha) vs the raster (misses per part), gutter + miss fill from the nearest
    baked texel (EDT indices) -> every texel of the atlas is defined (padding >= the island gap);
 3. N (DirectX, green of the OpenGL bake inverted), BC (sRGB), ORM (R AO, G roughness, B metallic, linear),
    TeamMask (L: cloth) and TeamMaskRGBA (R cloth, G base band, B gold embroidery, A 255); no N_OpenGL file: the
    Blender preview inverts the green of N in its shader (a derived copy only added 16.5 MB to git);
    H2.1 material classes (profile maps.materials): per-texel source-frame position (barycentric from the UV raster)
    + part map + BC HSV + team masks -> embroidery (cloth, roughness 0.55-0.65), leather belt, metal buckle
    (metallic 1, BC lifted to an antique-bronze F0), crystal (glossy dielectric, deeper blue), wood; metallic 0
    everywhere else; TeamMaskRGBA.B = embroidery class;
 4. runtime 2K: exact 2x2 box (BC in linear light; normals averaged as vectors and renormalised).
PNG via Pillow (no metadata) -> byte-deterministic. Reports: reports/maps-report.json, reports/textures-report.json
(sha256 of every texture, 4K masters included), preview/h21_material_classes_1K.png (class map of the atlas).
"""

import math
import sys
from pathlib import Path

import numpy as np
from PIL import Image
from scipy import ndimage

sys.path.insert(0, str(Path(__file__).resolve().parent))
import common as C  # noqa: E402
from raster import raster  # noqa: E402

OBJECTS = ("body", "staff", "base")


def srgb_encode(lin):
    lin = np.clip(lin, 0, 1)
    return np.where(lin <= 0.0031308, lin * 12.92, 1.055 * np.power(lin, 1 / 2.4) - 0.055)


def srgb_decode(s):
    return np.where(s <= 0.04045, s / 12.92, np.power((s + 0.055) / 1.055, 2.4))


def to8(a):
    return np.clip(np.floor(np.asarray(a, np.float64) * 255.0 + 0.5), 0, 255).astype(np.uint8)


def save_png(path, arr, mode):
    path.parent.mkdir(parents=True, exist_ok=True)
    img = Image.fromarray(np.flipud(arr), mode)  # row 0 of the arrays = v 0 (bottom); PNG row 0 = top
    img.save(path, format="PNG", optimize=False, compress_level=9)
    return {"path": C.rel(path), "sha256": C.sha256(path), "bytes": path.stat().st_size, "px": list(img.size), "mode": mode}


def box2(a):
    return 0.25 * (a[0::2, 0::2] + a[1::2, 0::2] + a[0::2, 1::2] + a[1::2, 1::2])


def rgb_to_hsv(rgb):
    r, g, b = rgb[..., 0], rgb[..., 1], rgb[..., 2]
    mx, mn = rgb.max(-1), rgb.min(-1)
    d = mx - mn
    h = np.zeros_like(mx)
    m = d > 1e-9
    rr = m & (mx == r)
    gg = m & (mx == g) & ~rr
    bb = m & ~rr & ~gg
    h[rr] = ((g - b)[rr] / d[rr]) % 6
    h[gg] = ((b - r)[gg] / d[gg]) + 2
    h[bb] = ((r - g)[bb] / d[bb]) + 4
    h = h * 60.0
    s = np.where(mx > 1e-9, d / np.maximum(mx, 1e-9), 0)
    return h, s, mx


def ramp(x, a, width):
    return np.clip((x - a) / width, 0, 1)


def hsv_to_rgb(h, s, v):
    """Inverse of rgb_to_hsv (h in degrees)."""
    h6 = (h % 360.0) / 60.0
    i = np.floor(h6).astype(np.int64) % 6
    f = h6 - np.floor(h6)
    p = v * (1 - s)
    q = v * (1 - s * f)
    t = v * (1 - s * (1 - f))
    r = np.choose(i, [v, q, p, p, t, v])
    g = np.choose(i, [t, v, v, q, p, p])
    b = np.choose(i, [p, p, t, v, v, q])
    return np.stack([r, g, b], -1)


def sbox(val, lo, hi, soft):
    """Soft 1-D box: 1 inside [lo, hi], 0 outside, linear edge of width soft centred on the bounds."""
    return np.clip((val - lo) / soft + 0.5, 0, 1) * np.clip((hi - val) / soft + 0.5, 0, 1)


def texel_positions(uv_all, pos_all, tri_map):
    """Source-frame position of every covered texel centre: barycentric interpolation of the triangle corners."""
    size = tri_map.shape[0]
    ys, xs = np.nonzero(tri_map >= 0)
    t = tri_map[ys, xs]
    px = (xs + 0.5) / size
    py = (ys + 0.5) / size
    a = uv_all[t, 0]
    v0 = uv_all[t, 1] - a
    v1 = uv_all[t, 2] - a
    v2x, v2y = px - a[:, 0], py - a[:, 1]
    d00 = (v0 * v0).sum(1)
    d01 = (v0 * v1).sum(1)
    d11 = (v1 * v1).sum(1)
    d20 = v2x * v0[:, 0] + v2y * v0[:, 1]
    d21 = v2x * v1[:, 0] + v2y * v1[:, 1]
    den = d00 * d11 - d01 * d01
    b1 = (d11 * d20 - d01 * d21) / den
    b2 = (d00 * d21 - d01 * d20) / den
    b0 = 1.0 - b1 - b2
    pos = np.zeros(tri_map.shape + (3,), np.float32)
    pos[ys, xs] = b0[:, None] * pos_all[t, 0] + b1[:, None] * pos_all[t, 1] + b2[:, None] * pos_all[t, 2]
    return pos


def class_stats(mask, rough, metal, bc_srgb, h, s, v):
    m = mask >= 0.5
    n = int(m.sum())
    if not n:
        return {"texels": 0}
    return {"texels": n, "roughness_p5_p50_p95": C.rv(np.percentile(rough[m], [5, 50, 95]), 3),
            "metallic_p50_max": [C.r(np.median(metal[m]), 3), C.r(metal[m].max(), 3)],
            "bc_srgb_mean": C.rv(bc_srgb[m].mean(0), 3), "hsv_s_p50": C.r(np.median(s[m]), 3), "hsv_v_p50": C.r(np.median(v[m]), 3)}


def materials_h21(mat, pos, part_full, covered, bc_lin, rough, metal, trim, cloth):
    """H2.1 material classes (profile maps.materials). Returns new (bc_lin, rough, metal, embroidery) and the report."""
    bc_srgb = srgb_encode(bc_lin)
    h, s, v = rgb_to_hsv(bc_srgb)
    x, y, z = pos[..., 0], pos[..., 1], pos[..., 2]
    # leather belt: tilted band round the waist + the hanging end, brown texels only, stoles excluded
    lb = mat["leather_belt"]
    on_part = (part_full == C.part_index(lb["part"])).astype(np.float64)
    bd = lb["band"]
    zc = bd["z_center_m"] + bd["z_tilt_m"] * y / np.maximum(np.hypot(x, y), 1e-6)
    band = sbox(z - zc, -bd["half_height_m"], bd["half_height_m"], bd["soft_m"])
    sm = lb["soft_m"]
    for ex in lb["exclude_boxes"]:
        band = band * (1.0 - sbox(x, ex["x"][0], ex["x"][1], sm) * sbox(y, ex["y"][0], ex["y"][1], sm))
    sb = lb["strap_box"]
    strap = sbox(x, sb["x"][0], sb["x"][1], sm) * sbox(y, sb["y"][0], sb["y"][1], sm) * sbox(z, sb["z"][0], sb["z"][1], sm)
    br = lb["brown"]
    brown = (ramp(h, br["hue_deg"][0] - br["hue_soft"], br["hue_soft"]) * ramp(-h, -br["hue_deg"][1] - br["hue_soft"], br["hue_soft"])
             * ramp(s, br["s_min"] - br["s_soft"], br["s_soft"]) * ramp(-v, -br["v_max"] - br["v_soft"], br["v_soft"]))
    leather = np.maximum(band, strap) * brown * on_part
    # metal buckle: frame bars + prong (xz boxes, front only), minus the blue robe behind the rounded corners
    mb = mat["metal_buckle"]
    ring = np.zeros_like(leather)
    for bx in mb["boxes_xz"]:
        ring = np.maximum(ring, sbox(x, bx["x"][0], bx["x"][1], mb["soft_m"]) * sbox(z, bx["z"][0], bx["z"][1], mb["soft_m"]))
    metal_m = ring * sbox(y, -1.0, mb["y_max"], lb["soft_m"]) * (part_full == C.part_index(mb["part"]))
    if mb.get("exclude_cloth_mask"):
        metal_m = metal_m * (1.0 - cloth)
    leather = leather * (1.0 - metal_m)
    emb = trim * (1.0 - leather) * (1.0 - metal_m)
    crystal = (part_full == C.part_index(mat["crystal"]["part"])).astype(np.float64)
    wood = np.isin(part_full, [C.part_index(q) for q in mat["wood"]["parts"]]).astype(np.float64)
    before = {"embroidery": class_stats(emb * covered, rough, metal, bc_srgb, h, s, v),
              "leather_belt": class_stats(leather * covered, rough, metal, bc_srgb, h, s, v),
              "metal_buckle": class_stats(metal_m * covered, rough, metal, bc_srgb, h, s, v),
              "crystal": class_stats(crystal * covered, rough, metal, bc_srgb, h, s, v),
              "wood": class_stats(wood * covered, rough, metal, bc_srgb, h, s, v)}
    # roughness
    r_new = rough.copy()
    cr = mat["crystal"]
    r_c = cr["roughness"][0] + (cr["roughness"][1] - cr["roughness"][0]) * ramp(rough, cr["roughness_from_tripo_ramp"][0],
                                                                                   cr["roughness_from_tripo_ramp"][1] - cr["roughness_from_tripo_ramp"][0])
    r_new = np.where(crystal > 0, r_c, r_new)
    for key, w in (("embroidery", emb), ("leather_belt", leather), ("metal_buckle", metal_m)):
        c = mat[key]
        lo, hi = c["roughness"]
        target = hi - (hi - lo) * ramp(v, c["value_ramp"][0], c["value_ramp"][1])
        r_new = r_new * (1.0 - w) + target * w
    # metallic: 0 everywhere, the metal class only
    m_new = np.clip(metal_m * float(mb["metallic"]), 0, 1) + float(mat["metallic_default"]) * (1.0 - metal_m)
    # base colour: metal F0 (hue/saturation kept), deeper crystal blue
    lum = bc_lin @ np.array([0.2126, 0.7152, 0.0722])
    core = (metal_m >= 0.5) & covered
    lum_p50 = float(np.median(lum[core])) if core.any() else 1.0
    gain = float(mb["bc_linear_luminance_p50"]) / max(lum_p50, 1e-6)
    bc_metal = np.clip(bc_lin * gain, 0, float(mb["bc_linear_max"]))
    bc_new = bc_lin * (1.0 - metal_m[..., None]) + bc_metal * metal_m[..., None]
    ci = crystal > 0
    s_c = np.minimum(s[ci] * cr["bc_saturation_gain"], np.maximum(s[ci], cr["bc_saturation_max"]))
    v_c = np.clip(v[ci] * cr["bc_value_gain"], 0, 1)
    bc_new[ci] = srgb_decode(hsv_to_rgb(h[ci], s_c, v_c))
    bc_new_srgb = srgb_encode(bc_new)
    h2, s2, v2 = rgb_to_hsv(bc_new_srgb)
    after = {"embroidery": class_stats(emb * covered, r_new, m_new, bc_new_srgb, h2, s2, v2),
             "leather_belt": class_stats(leather * covered, r_new, m_new, bc_new_srgb, h2, s2, v2),
             "metal_buckle": class_stats(metal_m * covered, r_new, m_new, bc_new_srgb, h2, s2, v2),
             "crystal": class_stats(crystal * covered, r_new, m_new, bc_new_srgb, h2, s2, v2),
             "wood": class_stats(wood * covered, r_new, m_new, bc_new_srgb, h2, s2, v2)}
    rep = {"before_tripo_bake": before, "after": after, "metal_bc_gain": C.r(gain, 4), "metal_bc_luminance_p50_before": C.r(lum_p50, 5),
           "texels_ge_0_5": {k: int(((w >= 0.5) & covered).sum()) for k, w in
                             (("embroidery", emb), ("leather_belt", leather), ("metal_buckle", metal_m), ("crystal", crystal), ("wood", wood))}}
    masks = {"embroidery": emb, "leather_belt": leather, "metal_buckle": metal_m, "crystal": crystal, "wood": wood}
    return np.clip(bc_new, 0, 1), np.clip(r_new, 0, 1), m_new, emb, masks, rep


def textures_report(prof, out, cls_png, mat_rep):
    """reports/textures-report.json: every texture of the run (4K masters are git-ignored, local only; 2K runtime is
    committed) with sha256/bytes/px/mode, plus the conventions and the H2.1 material summary."""
    files = {}
    for key, info in sorted(out.items()):
        tier = "master_4k" if key.endswith("_4K") else "runtime_2k"
        files[Path(info["path"]).name] = dict(info, tier=tier,
                                              git=("ignored by ASSET-MERLIN-001/.gitignore (20260929-h2-bake/textures/*_4K.png), local only"
                                                   if tier == "master_4k" else "committed"))
    mcfg = prof["maps"]
    C.write_json(prof.reports / "textures-report.json", {
        "stage": "maps", "profile": C.rel(prof.path), "profile_id": prof["profile_id"], "iteration": mcfg["materials"]["iteration"],
        "textures": files, "count": len(files),
        "conventions": {"BC": "sRGB 8-bit (UE TC_Default, sRGB)", "N": mcfg["normal_convention_ue"] + " (UE TC_Normalmap, flip_green false)",
                        "ORM": mcfg["orm"] + " (UE TC_Masks, sRGB off)", "TeamMask": mcfg["team_mask"]["format"],
                        "TeamMaskRGBA": mcfg["team_mask"]["rgba_format"] + "; " + mcfg["team_mask"]["rgba_b_h21"],
                        "downscale": mcfg["downscale"]},
        "material_classes": {"rules": "profile maps.materials", "texels_ge_0_5": mat_rep["texels_ge_0_5"], "after": mat_rep["after"],
                             "class_map": cls_png},
        "note": "sha256 of the 4K masters pins the local build; they are reproducible with run.py (stages uv..maps, CPU bake)"})


def main():
    prof = C.Profile(sys.argv[1])
    size = int(prof["uv"]["atlas_px"])
    mcfg = prof["maps"]
    checks = {}
    # ---------------------------------------------------------------- 1. raster
    part_map = np.full((size, size), -1, np.int16)
    island_map = np.full((size, size), -1, np.int32)
    obj_map = np.full((size, size), -1, np.int8)
    nz_map = np.zeros((size, size), np.float32)
    cap_map = np.zeros((size, size), np.int8)
    count = np.zeros((size, size), np.uint16)
    td = {}
    s = None
    isl_off = 0
    tri_map = np.full((size, size), -1, np.int32)
    tri_off = 0
    uv_all, pos_all = [], []
    uv_area_px = {}
    area3d = {}
    for oi, key in enumerate(OBJECTS):
        z = np.load(prof.work / "uv" / (key + ".npz"))
        uv, part, isl, nrm, a3 = z["uv"], z["part"], z["island"], z["normal"], z["area3d_m2"]
        c = raster(uv, size, [(part.astype(np.int16), part_map), ((isl + isl_off).astype(np.int32), island_map),
                              (np.full(len(uv), oi, np.int8), obj_map), (np.abs(nrm[:, 2]).astype(np.float32), nz_map),
                              (z["cap"].astype(np.int8), cap_map), ((np.arange(len(uv)) + tri_off).astype(np.int32), tri_map)])
        count += c
        isl_off += int(isl.max()) + 1
        tri_off += len(uv)
        uv_all.append(uv)
        pos_all.append(z["pos"])
        ua = 0.5 * np.abs((uv[:, 1, 0] - uv[:, 0, 0]) * (uv[:, 2, 1] - uv[:, 0, 1]) - (uv[:, 1, 1] - uv[:, 0, 1]) * (uv[:, 2, 0] - uv[:, 0, 0]))
        for p in np.unique(part):
            m = part == p
            name = "tripo_part_%d" % p
            uv_area_px[name] = uv_area_px.get(name, 0.0) + float(ua[m].sum()) * size * size
            area3d[name] = area3d.get(name, 0.0) + float(a3[m].sum())
    covered = count > 0
    overlap = int((count > 1).sum())
    C.check(checks, "no_uv_overlap_texels", overlap == 0, overlap, 0, "texel centres inside more than one UV triangle")
    utilisation = float(covered.mean())
    # island gaps: nearest-island label for every texel, then label changes between 4-neighbours
    lab = island_map
    dist, (iy, ix) = ndimage.distance_transform_edt(lab < 0, return_indices=True)
    near = lab[iy, ix]
    gaps = []
    for axis in (0, 1):
        a = near
        b = np.roll(near, -1, axis=axis)
        da, db = dist, np.roll(dist, -1, axis=axis)
        valid = np.ones_like(a, bool)
        if axis == 0:
            valid[-1, :] = False
        else:
            valid[:, -1] = False
        diff = valid & (a != b)
        if diff.any():
            gaps.append(float((da + db)[diff].min()))
    min_gap = min(gaps) if gaps else None
    pad = int(prof["uv"]["padding_px"])
    C.check(checks, "island_gap_at_least_padding_px", min_gap is not None and min_gap >= pad, C.r(min_gap, 3), ">= %d px at %d" % (pad, size),
            "min over neighbouring texels of different nearest islands of (d1 + d2), d = EDT distance to the island")
    # texel density in the game frame
    rt = C.load_json(prof.reports / "source-report.json")
    zmin = min(p["bounds_m"]["min"][2] for p in rt["parts"].values())
    base_top = rt["parts"]["tripo_part_1"]["bounds_m"]["max"][2]
    top = rt["parts"][prof["scale"]["top_part"]]["bounds_m"]["max"][2]
    fz = prof["scale"]["base_footprint_m"][2]
    s = (prof["scale"]["figure_height_m"] - fz) / (top - base_top)
    for name in sorted(uv_area_px, key=C.part_index):
        cm2 = area3d[name] * (s * 100.0) ** 2
        td[name] = {"px_per_uu_at_4k": C.r(math.sqrt(uv_area_px[name] / cm2), 3), "uv_share": C.r(uv_area_px[name] / size / size, 4),
                    "td_priority": prof["parts"][name]["td_priority"]}
    ref = td["tripo_part_0"]["px_per_uu_at_4k"]
    for name in td:
        td[name]["relative_to_robe"] = C.r(td[name]["px_per_uu_at_4k"] / ref, 3)
    # ---------------------------------------------------------------- 2. bakes + fill
    bake = {}
    misses = {}
    for mp in ("normal", "ao", "basecolor", "roughness", "metallic"):
        a = np.load(prof.work / "bake" / (mp + ".npy")).astype(np.float32)
        written = a[..., 3] > 0.5
        miss = covered & ~written
        surf = covered & (cap_map == 0)
        miss_s = miss & (cap_map == 0)
        misses[mp] = {"texels": int(miss.sum()), "share_of_covered": C.r(miss.sum() / max(1, covered.sum()), 6),
                      "surface_texels": int(miss_s.sum()), "surface_share": C.r(miss_s.sum() / max(1, surf.sum()), 6),
                      "cap_texels": int((miss & (cap_map > 0)).sum()), "cap_texels_total": int((covered & (cap_map > 0)).sum()),
                      "surface_by_part": {("tripo_part_%d" % p): int((miss_s & (part_map == p)).sum()) for p in np.unique(part_map[miss_s]) if p >= 0}}
        _d, (jy, jx) = ndimage.distance_transform_edt(~written, return_indices=True)
        bake[mp] = a[jy, jx, :3]
    worst = max(m["surface_share"] for m in misses.values())
    C.check(checks, "bake_surface_misses_below_0_5_percent", worst < 0.005, {k: v["surface_share"] for k, v in misses.items()}, "< 0.005",
            "texels inside non-cap UV triangles no cage ray matched; filled from the nearest baked texel. Caps and the "
            "staff bridge lie inside the fist / on the base where the high-poly has no surface: their misses are reported, not gated")
    # ---------------------------------------------------------------- 3. textures
    out = {}
    prefix = mcfg["prefix"]
    tex = prof.textures
    n_gl = bake["normal"] * 2.0 - 1.0
    n_gl /= np.maximum(np.linalg.norm(n_gl, axis=-1, keepdims=True), 1e-8)
    n_dx = n_gl.copy()
    n_dx[..., 1] *= -1.0
    bc_lin = np.clip(bake["basecolor"], 0, 1)
    ao = np.clip(bake["ao"][..., 0], 0, 1)
    rough = np.clip(bake["roughness"][..., 0], 0, 1)
    metal = np.clip(bake["metallic"][..., 0], 0, 1)
    bc_srgb = srgb_encode(bc_lin)
    # team masks on the 4K raster (parts) + base colour HSV
    _d, (ky, kx) = ndimage.distance_transform_edt(part_map < 0, return_indices=True)
    part_full = part_map[ky, kx]
    nz_full = nz_map[ky, kx]
    h, sat, val = rgb_to_hsv(bc_srgb)
    tm = mcfg["team_mask"]
    team_of = {C.part_index(n): p.get("team") for n, p in prof["parts"].items()}
    cloth_parts = np.isin(part_full, [k for k, v in team_of.items() if v == "cloth"])
    base_parts = np.isin(part_full, [k for k, v in team_of.items() if v == "base"])
    cc = tm["cloth"]
    hr = 10.0
    cloth = (ramp(h, cc["hue_deg"][0] - hr, hr) * ramp(-h, -cc["hue_deg"][1] - hr, hr)
             * ramp(sat, cc["s_min"] - cc["soft"], cc["soft"]) * ramp(-val, -cc["v_max"] - cc["soft"], cc["soft"]))
    cloth = np.where(cloth_parts, cloth, 0.0)
    trc = tm["trim"]
    trim = (ramp(h, trc["hue_deg"][0] - hr, hr) * ramp(-h, -trc["hue_deg"][1] - hr, hr)
            * ramp(sat, trc["s_min"] - trc["soft"], trc["soft"]) * ramp(val, trc["v_min"] - trc["soft"], trc["soft"]))
    trim = np.where(cloth_parts, trim, 0.0)
    band = (base_parts & (nz_full < tm["base_band"]["normal_z_abs_max"])).astype(np.float64)
    # 1-px soft edge of the masks (3x3 box) so the lerp has no stair steps
    cloth = ndimage.uniform_filter(cloth, 3, mode="nearest")
    trim = ndimage.uniform_filter(trim, 3, mode="nearest")
    # H2.1 material classes: per-texel source-frame positions (gutter texels take the nearest covered texel)
    pos = texel_positions(np.concatenate(uv_all), np.concatenate(pos_all).astype(np.float64), tri_map)
    pos = pos[ky, kx]
    mat = mcfg["materials"]
    rough_before, metal_before = rough, metal
    bc_lin, rough, metal, emb, cls, mat_rep = materials_h21(mat, pos, part_full, covered, bc_lin, rough, metal, trim, cloth)
    bc_srgb = srgb_encode(bc_lin)
    trim_h2 = trim
    trim = emb
    coverage_team = {}
    for p in sorted({k for k in team_of}):
        m = covered & (part_map == p)
        if m.any():
            coverage_team["tripo_part_%d" % p] = {"cloth_mean": C.r(cloth[m].mean(), 4), "trim_mean": C.r(trim[m].mean(), 4),
                                                   "band_mean": C.r(band[m].mean(), 4)}
    non_team = covered & ~cloth_parts
    C.check(checks, "team_cloth_mask_only_on_cloth_parts", float(cloth[non_team].max()) == 0.0 if non_team.any() else True,
            C.r(float(cloth[non_team].max()) if non_team.any() else 0.0, 4), 0.0, "face, hands, staff, shoes and base stay outside the cloth mask")
    maps4 = {
        "BC": (to8(bc_srgb), "RGB"),
        "N": (to8(n_dx * 0.5 + 0.5), "RGB"),
        "ORM": (to8(np.stack([ao, rough, metal], -1)), "RGB"),
        "TeamMask": (to8(cloth), "L"),
        "TeamMaskRGBA": (to8(np.stack([cloth, band, trim, np.ones_like(cloth)], -1)), "RGBA"),
    }
    for k, (arr, mode) in maps4.items():
        out[k + "_4K"] = save_png(tex / ("%s_%s_4K.png" % (prefix, k)), arr, mode)
    # runtime 2K
    bc2 = srgb_encode(box2(bc_lin))
    n2 = box2(n_gl)
    n2 /= np.maximum(np.linalg.norm(n2, axis=-1, keepdims=True), 1e-8)
    n2dx = n2.copy()
    n2dx[..., 1] *= -1
    maps2 = {
        "BC": (to8(bc2), "RGB"),
        "N": (to8(n2dx * 0.5 + 0.5), "RGB"),
        "ORM": (to8(np.stack([box2(ao), box2(rough), box2(metal)], -1)), "RGB"),
        "TeamMask": (to8(box2(cloth)), "L"),
        "TeamMaskRGBA": (to8(np.stack([box2(cloth), box2(band), box2(trim), np.ones_like(box2(cloth))], -1)), "RGBA"),
    }
    for k, (arr, mode) in maps2.items():
        out[k + "_2K"] = save_png(tex / ("%s_%s_2K.png" % (prefix, k)), arr, mode)
    # H2.1 material checks on the written 8-bit ORM (4K)
    orm8 = maps4["ORM"][0]
    r8 = orm8[..., 1].astype(np.float64) / 255.0
    m8 = orm8[..., 2]
    metal_cls = cls["metal_buckle"]
    C.check(checks, "h21_metallic_zero_outside_metal_class", int(m8[metal_cls <= 0].max()) == 0,
            int(m8[metal_cls <= 0].max()), 0, "8-bit metallic of every texel with metal class weight 0 (whole atlas incl. gutters)")
    core_m = covered & (metal_cls >= 0.999)
    C.check(checks, "h21_metal_class_found_and_metallic_1", int(core_m.sum()) >= 1000 and int(m8[core_m].min()) == 255,
            {"texels": int(core_m.sum()), "metallic_min_8bit": int(m8[core_m].min()) if core_m.any() else None}, ">= 1000 texels, 255",
            "belt buckle frame + prong")
    ec = mat["embroidery"]["roughness"]
    core_e = covered & (cls["embroidery"] >= 0.999)
    C.check(checks, "h21_embroidery_roughness_in_range", bool(core_e.any()) and float(r8[core_e].min()) >= ec[0] - 0.5 / 255 and float(r8[core_e].max()) <= ec[1] + 0.5 / 255,
            C.rv([r8[core_e].min(), np.median(r8[core_e]), r8[core_e].max()], 4) if core_e.any() else None, ec,
            "min / p50 / max of the 8-bit roughness on texels fully in the embroidery class")
    crc = mat["crystal"]["roughness"]
    core_c = covered & (cls["crystal"] > 0)
    C.check(checks, "h21_crystal_glossy_dielectric", float(r8[core_c].min()) >= 0.1 - 0.5 / 255 and float(r8[core_c].max()) <= 0.2 + 0.5 / 255 and int(m8[core_c].max()) == 0,
            {"roughness_min_p50_max": C.rv([r8[core_c].min(), np.median(r8[core_c]), r8[core_c].max()], 4), "metallic_max_8bit": int(m8[core_c].max())},
            {"roughness": [0.1, 0.2], "metallic": 0, "profile_roughness": crc})
    core_w = covered & (cls["wood"] > 0)
    C.check(checks, "h21_wood_metallic_zero", int(m8[core_w].max()) == 0, int(m8[core_w].max()), 0)
    tb = maps4["TeamMaskRGBA"][0][..., 2]
    lm = covered & ((cls["leather_belt"] >= 0.999) | (metal_cls >= 0.999))
    C.check(checks, "h21_team_rgba_b_excludes_leather_and_metal", int(tb[lm].max()) == 0 if lm.any() else True,
            int(tb[lm].max()) if lm.any() else 0, 0, "TeamMaskRGBA.B (gold embroidery) on the belt / buckle")
    # class map for review (1K, committed): cloth blue, embroidery yellow, leather green, metal red, crystal cyan,
    # wood brown, other covered texels grey, gutter black
    cm = np.zeros((size, size, 3), np.float64)
    cm[covered] = 0.35
    wc = (cloth * covered)[..., None]
    cm = cm * (1 - wc) + np.array([0.15, 0.2, 0.75]) * wc
    for key, col in (("wood", (0.45, 0.28, 0.12)), ("crystal", (0.1, 0.9, 1.0)), ("embroidery", (1.0, 0.85, 0.1)),
                     ("leather_belt", (0.1, 0.85, 0.2)), ("metal_buckle", (1.0, 0.1, 0.1))):
        w = cls[key][..., None] * covered[..., None]
        cm = cm * (1 - w) + np.array(col) * w
    cls_png = save_png(prof.preview / "h21_material_classes_1K.png", to8(box2(box2(cm))), "RGB")
    # ORM statistics per part (measured, for the report)
    stats = {}
    for p in sorted(np.unique(part_map[covered])):
        m = covered & (part_map == p)
        stats["tripo_part_%d" % p] = {"ao_p5_p50": [C.r(np.percentile(ao[m], 5), 3), C.r(np.median(ao[m]), 3)],
                                      "roughness_p50": C.r(np.median(rough[m]), 3), "metallic_p50_p95": [C.r(np.median(metal[m]), 3), C.r(np.percentile(metal[m], 95), 3)],
                                      "bc_srgb_mean": C.rv(bc_srgb[m].mean(0), 3)}
    C.check(checks, "ao_not_constant", float(np.percentile(ao[covered], 99) - np.percentile(ao[covered], 1)) > 32 / 255,
            C.r(np.percentile(ao[covered], 99) - np.percentile(ao[covered], 1), 4), "> 32/255 (W4-B gate min_range_p1_p99)")
    # debug: part map for review
    rng = np.random.default_rng(0)
    pal = rng.integers(60, 255, (16, 3)).astype(np.uint8)
    dbg = np.zeros((size, size, 3), np.uint8)
    dbg[covered] = pal[np.clip(part_map[covered], 0, 15)]
    save_png(prof.work / "debug" / "part_map_4K.png", dbg, "RGB")
    report = {"stage": "maps", "profile": C.rel(prof.path), "profile_id": prof["profile_id"], "atlas_px": size,
              "runtime_px": int(mcfg["runtime_px"]), "utilisation": C.r(utilisation, 4), "uv_overlap_texels": overlap,
              "min_island_gap_px": C.r(min_gap, 3), "texel_density": td, "game_frame_scale_from_source": C.r(s, 6),
              "misses": misses, "team_mask_coverage": coverage_team, "part_stats": stats, "textures": out,
              "materials_h21": dict(mat_rep, class_map=cls_png, rules={k: v for k, v in mat.items() if k not in ("note",)},
                                    trim_h2_vs_embroidery_texels_ge_0_5={"trim_h2": int(((trim_h2 >= 0.5) & covered).sum()),
                                                                          "embroidery_h21": int(((emb >= 0.5) & covered).sum())},
                                    tripo_bake_metallic_p50_p99=C.rv(np.percentile(metal_before[covered], [50, 99]), 4),
                                    tripo_bake_roughness_p50=C.r(np.median(rough_before[covered]), 4)),
              "conventions": {"N": mcfg["normal_convention_ue"], "ORM": mcfg["orm"], "TeamMask": tm["format"],
                              "TeamMaskRGBA": tm["rgba_format"], "downscale": mcfg["downscale"]},
              "checks": checks, "passed": all(c["passed"] for c in checks.values())}
    C.write_json(prof.reports / "maps-report.json", report)
    textures_report(prof, out, cls_png, mat_rep)
    print("H2_STAGE_OK maps passed=%s" % report["passed"])
    if not report["passed"]:
        print("failed:", sorted(k for k, c in checks.items() if not c["passed"]))
        sys.exit(1)


if __name__ == "__main__":
    main()
