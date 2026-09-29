"""UV atlas checks of the H2 bake (system Python 3.10+ with numpy, scipy, Pillow; no Blender).

    python uv_check.py <profile.json> <run_dir>

Reads <run>/work/uv-tris.npz (stage_uv.py) and measures at the master atlas size (uv.atlas_px):
  * texel coverage by pixel centres (triangle rasteriser), texels covered twice, of those the texels strictly
    inside two triangles (overlap; a shared edge through a texel centre is only a tie), texels outside 0..1;
  * padding: the smallest distance between texels of two different UV islands (boundary texels, all offsets up to
    uv.gap_search_px) and the smallest distance between texels of two different PARTS;
  * texel density px/cm at the final figure scale (seat.expected_scale) per part and per priority region
    (area-weighted median), and at the runtime size (uv.runtime_px);
Writes <run>/reports/uv-report.json, <run>/work/uv-labels.npz (island and part label rasters, -1 empty) and
<run>/preview/uv_layout_parts.png (2K, islands coloured by part).
"""

import json
import math
import sys
from pathlib import Path

import numpy as np
from PIL import Image

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from textures_common import PART_RGB, rasterise, sha256, write_json  # noqa: E402

profile_path, run = Path(sys.argv[1]).resolve(), Path(sys.argv[2]).resolve()
P = json.loads(profile_path.read_text(encoding="utf-8"))
U = P["uv"]
N = int(U["atlas_px"])
d = np.load(run / "work" / "uv-tris.npz")
uv, co, part, dens, island = d["uv"], d["co"], d["part"], d["density_factor"], d["island"]
parts = [str(p) for p in d["parts"]]
scale = float(P["seat"]["expected_scale"])

outside = int(((uv < -1e-6) | (uv > 1 + 1e-6)).any(axis=(1, 2)).sum())
first = np.full((N, N), -1, np.int32)
isl_lab, cover = rasterise(uv, island, N, first)
inter_overlap = int(((cover > 1) & (first != isl_lab)).sum())


def strictly_covering(tx, ty, rel_eps=1e-6):
    """Triangles whose interior (not an edge) holds the centre of texel (tx, ty). The rasteriser counts a texel twice
    when a shared edge of two adjacent triangles passes exactly through its centre (inclusive edge test); such a tie
    is not an overlap."""
    cx, cy = tx + 0.5, ty + 0.5
    pts = uv * N
    lo_, hi_ = pts.min(1), pts.max(1)
    cand = np.nonzero((lo_[:, 0] <= cx) & (hi_[:, 0] >= cx) & (lo_[:, 1] <= cy) & (hi_[:, 1] >= cy))[0]
    out = []
    for t in cand:
        (x0, y0), (x1, y1), (x2, y2) = pts[t]
        area = (x1 - x0) * (y2 - y0) - (x2 - x0) * (y1 - y0)
        if abs(area) < 1e-12:
            continue
        w = [(x1 - cx) * (y2 - cy) - (x2 - cx) * (y1 - cy), (x2 - cx) * (y0 - cy) - (x0 - cx) * (y2 - cy),
             (x0 - cx) * (y1 - cy) - (x1 - cx) * (y0 - cy)]
        if area < 0:
            w = [-x for x in w]
        if min(w) > rel_eps * abs(area):
            out.append(int(t))
    return out


twice = np.argwhere(cover > 1)
twice_detail = []
for ty, tx in twice[:200]:
    strict = strictly_covering(int(tx), int(ty))
    twice_detail.append({"texel": [int(tx), int(ty)], "strictly_inside_triangles": strict,
                         "edge_tie": len(strict) < 2})
overlap_strict = int(sum(1 for t in twice_detail if not t["edge_tie"])) + max(0, len(twice) - 200)
# part label per island
isl_part = np.full(island.max() + 1, -1, np.int32)
isl_part[island] = part
part_lab = np.where(isl_lab >= 0, isl_part[np.clip(isl_lab, 0, None)], -1).astype(np.int32)

# padding between islands / parts: boundary texels, offsets up to R
R = int(U.get("gap_search_px", 16))
occ = isl_lab >= 0
bnd = occ.copy()
inner = occ.copy()
for dy, dx in ((0, 1), (0, -1), (1, 0), (-1, 0)):
    sh = np.full_like(isl_lab, -2)
    ys = slice(max(dy, 0), N + min(dy, 0))
    yd = slice(max(-dy, 0), N + min(-dy, 0))
    xs = slice(max(dx, 0), N + min(dx, 0))
    xd = slice(max(-dx, 0), N + min(-dx, 0))
    sh[yd, xd] = isl_lab[ys, xs]
    inner &= sh == isl_lab
bnd = occ & ~inner
by, bx = np.nonzero(bnd)
bl = isl_lab[by, bx]
bp = isl_part[bl]
min_island = math.inf
min_part = math.inf
closest = None
for dy in range(-R, R + 1):
    for dx in range(-R, R + 1):
        dist = math.hypot(dx, dy)
        if dist == 0 or dist > R or dist >= min_island and dist >= min_part:
            continue
        yy, xx = by + dy, bx + dx
        ok = (yy >= 0) & (yy < N) & (xx >= 0) & (xx < N)
        other = np.full(len(by), -1)
        other[ok] = isl_lab[yy[ok], xx[ok]]
        hit = (other >= 0) & (other != bl)
        if hit.any():
            if dist < min_island:
                min_island = dist
                i = int(np.nonzero(hit)[0][0])
                closest = {"texel": [int(bx[i]), int(by[i])], "islands": [int(bl[i]), int(other[i])]}
            ph = hit & (isl_part[np.clip(other, 0, None)] != bp)
            if ph.any() and dist < min_part:
                min_part = dist

# texel density
a, b, c = co[:, 0], co[:, 1], co[:, 2]
area_cm2 = 0.5 * np.linalg.norm(np.cross(b - a, c - a), axis=1) * 1e4 * scale ** 2
ua, ub, uc = uv[:, 0] * N, uv[:, 1] * N, uv[:, 2] * N
uv_px2 = 0.5 * np.abs((ub[:, 0] - ua[:, 0]) * (uc[:, 1] - ua[:, 1]) - (uc[:, 0] - ua[:, 0]) * (ub[:, 1] - ua[:, 1]))
ok = area_cm2 > 1e-8
dens_px = np.sqrt(uv_px2[ok] / area_cm2[ok])


def wmedian(v, w):
    o = np.argsort(v)
    cw = np.cumsum(w[o])
    return float(v[o][np.searchsorted(cw, cw[-1] / 2)])


per_part = {}
for k, name in enumerate(parts):
    m = (part[ok] == k)
    per_part[name] = {"texel_density_px_per_cm_master": round(wmedian(dens_px[m], area_cm2[ok][m]), 2),
                      "texel_density_px_per_cm_runtime": round(wmedian(dens_px[m], area_cm2[ok][m]) * U["runtime_px"] / N, 2),
                      "area_cm2_final": round(float(area_cm2[part == k].sum()), 2),
                      "triangles": int((part == k).sum()), "islands": int(len(np.unique(island[part == k]))),
                      "texels": int((part_lab == k).sum())}
regions = {}
for f in sorted(set(dens.tolist())):
    m = dens[ok] == f
    regions["density_factor_%g" % f] = {"texel_density_px_per_cm_master": round(wmedian(dens_px[m], area_cm2[ok][m]), 2),
                                        "area_cm2_final": round(float(area_cm2[ok][m].sum()), 2),
                                        "triangles": int(m.sum())}
base = regions.get("density_factor_1", {}).get("texel_density_px_per_cm_master")
for k, v in regions.items():
    v["ratio_to_base"] = round(v["texel_density_px_per_cm_master"] / base, 3) if base else None

np.savez_compressed(run / "work" / "uv-labels.npz", island=isl_lab, part=part_lab)
img = np.zeros((N, N, 3), np.uint8) + 24
for k in range(len(parts)):
    img[part_lab == k] = PART_RGB[k % len(PART_RGB)]
prev = run / "preview" / "uv_layout_parts.png"
prev.parent.mkdir(parents=True, exist_ok=True)
Image.fromarray(img[::-1]).resize((2048, 2048), Image.NEAREST).save(prev, optimize=True)
report = {
    "schema": "unmatched.h2-bake.uv-report/1", "atlas_px": N, "runtime_px": U["runtime_px"],
    "triangles": int(len(uv)), "islands": int(island.max() + 1), "triangles_outside_0_1": outside,
    "texels_covered": int(occ.sum()), "fill_ratio": round(float(occ.mean()), 4),
    "texels_covered_twice": int((cover > 1).sum()),
    "texels_covered_twice_detail": twice_detail[:20],
    "texels_overlapping_strict": overlap_strict,
    "texels_covered_twice_note": ("texels_covered_twice counts every texel centre the inclusive pixel-centre "
                                  "rasteriser gives to two triangles; texels_overlapping_strict counts only those "
                                  "strictly inside two triangles (a shared edge through a texel centre is a tie, "
                                  "not an overlap)"),
    "texels_covered_by_two_islands": inter_overlap,
    "min_texel_distance_between_islands_px": None if min_island == math.inf else round(min_island, 3),
    "min_texel_distance_between_parts_px": None if min_part == math.inf else round(min_part, 3),
    "closest_pair": closest, "gap_search_px": R,
    "padding_requirement": "free texels between islands >= %d at %d px (texel centre distance >= %d)" % (
        U["min_padding_px"], N, U["min_padding_px"] + 1),
    "padding_ok": (min_island == math.inf) or (min_island >= U["min_padding_px"] + 1),
    "parts": per_part, "density_regions": regions,
    "preview": str(prev.relative_to(run)).replace("\\", "/"),
    "uv_tris_sha256": sha256(run / "work" / "uv-tris.npz"),
}
write_json(run / "reports" / "uv-report.json", report)
print("UV_CHECK_OK", report["fill_ratio"], report["min_texel_distance_between_islands_px"],
      report["texels_covered_twice"], inter_overlap, json.dumps(regions))
