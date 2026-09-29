"""Stage `maps` (system python: numpy, Pillow, scipy): textures of the H2 atlas from the Cycles bakes.

python maps.py <profile.json>

Inputs: work/uv/<object>.npz (UV triangles, part, cap, island, face normal) and work/bake/<map>.npy (float16
RGBA 4K, row 0 = bottom). Steps:
 1. rasterise the UV triangles at atlas_px (pixel centres, strict inside test): part / island / object maps,
    overlap count, coverage; island gaps (EDT of the island map); texel density per part in the game frame;
 2. per map: texels the bake wrote (alpha) vs the raster (misses per part), gutter + miss fill from the nearest
    baked texel (EDT indices) -> every texel of the atlas is defined (padding >= the island gap);
 3. N (DirectX, green of the OpenGL bake inverted), BC (sRGB), ORM (R AO, G roughness, B metallic, linear),
    TeamMask (L: cloth) and TeamMaskRGBA (R cloth, G base band, B gold trim, A 255); no N_OpenGL file: the Blender
    preview inverts the green of N in its shader (a derived copy only added 16.5 MB to git);
 4. runtime 2K: exact 2x2 box (BC in linear light; normals averaged as vectors and renormalised).
PNG via Pillow (no metadata) -> byte-deterministic. Report: reports/maps-report.json.
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
    uv_area_px = {}
    area3d = {}
    for oi, key in enumerate(OBJECTS):
        z = np.load(prof.work / "uv" / (key + ".npz"))
        uv, part, isl, nrm, a3 = z["uv"], z["part"], z["island"], z["normal"], z["area3d_m2"]
        c = raster(uv, size, [(part.astype(np.int16), part_map), ((isl + isl_off).astype(np.int32), island_map),
                              (np.full(len(uv), oi, np.int8), obj_map), (np.abs(nrm[:, 2]).astype(np.float32), nz_map),
                              (z["cap"].astype(np.int8), cap_map)])
        count += c
        isl_off += int(isl.max()) + 1
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
              "conventions": {"N": mcfg["normal_convention_ue"], "ORM": mcfg["orm"], "TeamMask": tm["format"],
                              "TeamMaskRGBA": tm["rgba_format"], "downscale": mcfg["downscale"]},
              "checks": checks, "passed": all(c["passed"] for c in checks.values())}
    C.write_json(prof.reports / "maps-report.json", report)
    print("H2_STAGE_OK maps passed=%s" % report["passed"])
    if not report["passed"]:
        print("failed:", sorted(k for k, c in checks.items() if not c["passed"]))
        sys.exit(1)


if __name__ == "__main__":
    main()
