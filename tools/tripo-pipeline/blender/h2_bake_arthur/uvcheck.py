"""Stage uvcheck (system python: numpy, Pillow, scipy): rasterised checks of the packed atlas.

    python uvcheck.py <profile.json> <run_dir>

Reads work/uv-triangles.npz (stage lowpoly) and reports/lowpoly-report.json, writes reports/uv-report.json,
textures-independent rasters work/uv-island-id-4k.png (island id, for inspection) and work/uv-part-id.npy
(part index per texel at the atlas size, used by stage textures for the TeamMask and the coverage mask).

Measured:
  coverage       share of the atlas covered by triangles
  overlap        texels covered by more than one island
  min gap        minimum distance between two different islands (Voronoi boundary of the nearest-island map:
                 gap = d(p) + d(q) + 1 over neighbouring texels p, q with different nearest islands)
  texel density  px/cm per part at 4K and 2K, in the Tripo frame and in the final 55 uu frame
"""

import json
import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw
from scipy import ndimage

sys.path.insert(0, str(Path(__file__).resolve().parent))
import pure as P  # noqa: E402


def rasterise(uv, ids, size):
    """Label image (int32, 0 = empty, id+1) of triangles in UV space (v up -> image row down)."""
    img = Image.new("I", (size, size), 0)
    draw = ImageDraw.Draw(img)
    for tri, i in zip(uv, ids):
        pts = [(float(u * size - 0.5), float((1.0 - v) * size - 0.5)) for u, v in tri]
        draw.polygon(pts, fill=int(i) + 1)
    return np.array(img, dtype=np.int32)


def count_overlaps(uv, isl, size):
    """Texels covered by two different islands: the raster in island order and in reverse order differ exactly
    there (the later island wins a texel in each pass)."""
    order = np.argsort(isl, kind="stable")
    fwd = rasterise(uv[order], isl[order], size)
    rev = rasterise(uv[order[::-1]], isl[order[::-1]], size)
    return int((fwd != rev).sum())


def main():
    profile = P.load_json(sys.argv[1])
    paths = P.run_paths(sys.argv[2])
    data = np.load(paths["work"] / "uv-triangles.npz")
    uv, obj, a3, isl, names = data["uv"], data["obj"], data["area3d"], data["island"], list(data["names"])
    size = int(profile["uv"]["atlas_px"])
    lab = rasterise(uv, isl, size)
    covered = lab > 0
    rep = {"schema": "unmatched.h2-bake.uvcheck/1", "atlas_px": size, "triangles": int(len(uv)),
           "islands": int(isl.max() + 1), "coverage_share": P.r(covered.mean(), 4)}
    # out of 0..1
    rep["uv_out_of_unit_square"] = int(((uv < 0) | (uv > 1)).any(axis=2).any(axis=1).sum())
    # overlap between islands
    rep["overlap_texels_between_islands"] = count_overlaps(uv, isl, size)
    # min gap between islands via nearest-island map
    dist, (iy, ix) = ndimage.distance_transform_edt(~covered, return_indices=True)
    near = lab[iy, ix]
    gaps = []
    for axis in (0, 1):
        a = near if axis == 0 else near.T
        d = dist if axis == 0 else dist.T
        diff = a[:, 1:] != a[:, :-1]
        g = d[:, 1:][diff] + d[:, :-1][diff] + 1.0
        gaps.append(g)
    g = np.concatenate(gaps)
    rep["min_gap_px_4k"] = P.r(g.min(), 2) if len(g) else None
    rep["gap_px_4k_p01"] = P.r(np.percentile(g, 1), 2) if len(g) else None
    rep["min_gap_px_2k"] = P.r(g.min() / 2, 2) if len(g) else None
    need = float(profile["uv"]["min_gap_px_4k"])
    rep["gap_check"] = {"passed": bool(len(g) and g.min() >= need), "required_px_4k": need,
                        "note": "gap = distance between the nearest texel centres of two islands, measured on the 4K raster (a triangle edge touching a texel centre counts as covered)"}
    # texel density per object (px per cm): sqrt(uv area * size^2 / 3D area)
    a2 = np.abs((uv[:, 1, 0] - uv[:, 0, 0]) * (uv[:, 2, 1] - uv[:, 0, 1]) -
                (uv[:, 2, 0] - uv[:, 0, 0]) * (uv[:, 1, 1] - uv[:, 0, 1])) * 0.5
    seat = profile.get("rig", {}).get("scale_note_factor")
    scale = float(seat) if seat else None
    dens = {}
    for oi, name in enumerate(names):
        m = obj == oi
        uv_a, a3_a = a2[m].sum(), a3[m].sum()
        px_per_m = np.sqrt(uv_a * size * size / max(a3_a, 1e-30))
        entry = {"triangles": int(m.sum()), "uv_area_share": P.r(uv_a, 5),
                 "px_per_cm_4k_tripo_frame": P.r(px_per_m / 100, 2)}
        if scale:
            entry["px_per_cm_4k_final"] = P.r(px_per_m / 100 / scale, 2)
            entry["px_per_cm_2k_final"] = P.r(px_per_m / 200 / scale, 2)
        dens[str(name)] = entry
    rep["texel_density"] = dens
    signed = ((uv[:, 1, 0] - uv[:, 0, 0]) * (uv[:, 2, 1] - uv[:, 0, 1]) -
              (uv[:, 2, 0] - uv[:, 0, 0]) * (uv[:, 1, 1] - uv[:, 0, 1]))
    flipped = 0
    for i in np.unique(isl):
        s_i = signed[isl == i]
        major = 1.0 if (s_i > 0).sum() >= (s_i < 0).sum() else -1.0
        flipped += int((s_i * major < 0).sum())
    rep["flipped_uv_triangles_within_islands"] = flipped
    # part-id raster for the textures stage
    part_lab = rasterise(uv, obj, size)
    np.save(paths["work"] / "uv-part-id.npy", part_lab.astype(np.int16))
    rep["part_index"] = {str(n): i + 1 for i, n in enumerate(names)}
    vis = ((lab.astype(np.int64) * 2654435761) % 16777216).astype(np.uint32)
    rgb = np.stack([(vis >> 16) & 255, (vis >> 8) & 255, vis & 255], axis=-1).astype(np.uint8)
    rgb[~covered] = 0
    Image.fromarray(rgb).resize((1024, 1024), Image.NEAREST).save(paths["work"] / "uv-islands-1k.png")
    P.write_json(paths["reports"] / "uv-report.json", rep)
    print(P.STAGE_MARKER, "uvcheck", json.dumps({k: rep[k] for k in ("coverage_share", "islands", "min_gap_px_4k",
                                                                      "overlap_texels_between_islands")}))


if __name__ == "__main__":
    main()
