"""Stage prepare: import the untextured high-poly by parts (HPG_*) and the textured 8K/PBR high-poly (HPT_*),
match the parts by node name, prove identical geometry, map both into the final frame (card 04), measure the
orientation of every high-poly part (ray escape) and save work/hp.blend.

Figure height: the source top mapped to scale.figure_top_m is the highest vertex of any non-base part (weapon included),
or, with the optional scale.figure_top_part, the top of that part (the head under a raised sword or antlers: the budget
top of Specs()); profile.figure_top_source_z. The report then names the part and the figure bounds top.

Part offsets (optional prepare.part_offsets_m = {tripo_part_N: [dx, dy, dz]}, profile.part_offsets; Ancient Leshen
stage 5 r3, 2026-10-14): a rigid detail that Tripo generated off its perch (the crow tripo_part_8 hung 2.9 cm in front
of the right forearm) is translated by that vector in the FINAL frame (metres, -Y front, +X the figure's left, +Z up —
the frame of retopo.dense_regions, rig.bones and seams targets), on both twins, right after the frame map: the map
(scale, base footprint, figure top) and every other part keep their coordinates to the bit. The final frame, not the
source one, because every number an author measures (rider gap, contact point) is in it and the offset does not feed
back into the figure scale. The report gets a part_offsets_m block only when the key is present (Medusa bytes).

Base underside (optional base.flatten_bottom, profile.base_flatten, base_ops.flatten_z; W2-c, pilot F83): after the
offsets, the base part of both twins is flattened in the final frame: floor = area-weighted quantile of the centroid z of
the downward faces (n_z < down_normal_z) of HPG; every vertex of a downward face at most band_m above it goes down to it
(lifted rim) and the vertices above follow with a linear falloff over falloff_m (no stretched strip at the rim); every base
vertex still below the floor goes up to it (hanging bumps); then z is rescaled so that the floor is z = 0 and the base
top keeps its height (base_ops.flatten_z). The decision is made per unique position (both twins share the position set,
checked), so the bake rays and the retopo source agree. Report block base_flatten (absent without the key)."""

from pathlib import Path

import bpy
import numpy as np

from . import base_ops as B
from . import bl_util as U
from . import profile as P


def mesh_faces(me):
    """(centre z, normal z, area, corner vertices in polygon order, loop totals) of the polygons of a mesh."""
    n = len(me.polygons)
    cen = np.empty(n * 3, np.float64)
    me.polygons.foreach_get("center", cen)
    nrm = np.empty(n * 3, np.float64)
    me.polygons.foreach_get("normal", nrm)
    area = np.empty(n, np.float64)
    me.polygons.foreach_get("area", area)
    lv = np.empty(len(me.loops), np.int64)
    me.loops.foreach_get("vertex_index", lv)
    lt = np.empty(n, np.int64)
    me.polygons.foreach_get("loop_total", lt)
    ls = np.empty(n, np.int64)
    me.polygons.foreach_get("loop_start", ls)
    loop_idx = np.repeat(ls, lt) + (np.arange(int(lt.sum())) - np.repeat(np.cumsum(lt) - lt, lt))
    return cen.reshape(-1, 3)[:, 2], nrm.reshape(-1, 3)[:, 2], area, lv[loop_idx], lt


def mesh_tris(me):
    me.calc_loop_triangles()
    tri = np.empty(len(me.loop_triangles) * 3, np.int64)
    me.loop_triangles.foreach_get("vertices", tri)
    return tri.reshape(-1, 3)


def bottom_profiles(me):
    co, tris = U.coords(me), mesh_tris(me)
    return {"front_x": B.bottom_profile(co, tris, 0), "side_y": B.bottom_profile(co, tris, 1)}


def kd_nearest(src_xy, query_xy, k):
    """base_ops.flatten_z neighbour search: mathutils KDTree in the xy plane (Blender has no scipy)."""
    from mathutils.kdtree import KDTree

    kd = KDTree(len(src_xy))
    for i, (x, y) in enumerate(src_xy):
        kd.insert((float(x), float(y), 0.0), i)
    kd.balance()
    k = min(k, len(src_xy))
    d = np.empty((len(query_xy), k), np.float64)
    idx = np.empty((len(query_xy), k), np.int64)
    for j, (x, y) in enumerate(query_xy):
        for m, (_co, i, dist) in enumerate(kd.find_n((float(x), float(y), 0.0), k)):
            idx[j, m], d[j, m] = i, dist
    return d, idx


def flatten_base(hpg, hpt, cfg):
    """base.flatten_bottom on the base part of both twins (module docstring); -> report block."""
    c = B.flatten_cfg(cfg)
    before = bottom_profiles(hpg.data)
    fz, fnz, area, lv, lt = mesh_faces(hpg.data)
    floor = B.floor_level(fz, fnz, area, c)
    down_face = fnz < c["down_normal_z"]
    ca = U.coords(hpg.data).astype(np.float32)
    bottom = np.zeros(len(ca), bool)
    bottom[lv[np.repeat(down_face, lt)]] = True
    ua, inv_a = np.unique(ca, axis=0, return_inverse=True)
    cb = U.coords(hpt.data).astype(np.float32)
    ub, inv_b = np.unique(cb, axis=0, return_inverse=True)
    if not np.array_equal(ua, ub):
        raise RuntimeError("base.flatten_bottom: the base twins have different position sets")
    inv_a, inv_b = inv_a.ravel(), inv_b.ravel()
    bottom_u = np.zeros(len(ua), bool)
    np.logical_or.at(bottom_u, inv_a, bottom)
    z_u, stats = B.flatten_z(ua.astype(np.float64), bottom_u, floor, float(c["band_m"]), float(c["falloff_m"]),
                             nearest=kd_nearest)
    for obj, c32, inv in ((hpg, ca, inv_a), (hpt, cb, inv_b)):
        new = c32.astype(np.float64)
        new[:, 2] = z_u[inv]
        U.set_coords(obj.data, new)
    down_area = {}
    for tag, me in (("before", None), ("after", hpg.data)):
        if me is None:
            zz, nz_, aa = fz, fnz, area
        else:
            zz, nz_, aa, _lv, _lt = mesh_faces(me)
        d = nz_ < c["down_normal_z"]
        down_area[tag] = {k: U.r(aa[d & (zz >= lo) & (zz < hi)].sum() * 1e4, 3)
                          for k, lo, hi in (("0-1mm", -1.0, 0.001), ("1-2mm", 0.001, 0.002), ("2-4mm", 0.002, 0.004),
                                            ("4-8mm", 0.004, 0.008), ("8mm+", 0.008, 1.0))}
    return {"config": dict(c, note=cfg.get("note")) if cfg.get("note") else c, "floor_from": "area-weighted quantile %s of "
            "the centroid z of the HPG base faces with n_z < %s" % (c["floor_quantile"], c["down_normal_z"]),
            "unique_positions": int(len(ua)), "stats": stats, "downward_face_area_cm2_by_z": down_area,
            "bottom_profile_hpg": {"before": before, "after": bottom_profiles(hpg.data),
                                   "metric": "lowest z per 1 mm column (lower envelope of the edges), |u| <= 0.9 of the "
                                             "half-width; share of columns above 1 / 2 mm"},
            "note": "frame_map describes the map before the flattening; parts.<base>.final_bounds_m are after it"}


def run(params, profile):
    repo = Path(params["repo_root"])
    run_dir = Path(params["run_dir"])
    src = profile["sources"]
    parts_glb = repo / src["parts_glb"]["path"]
    tex_glb = repo / src["tex_glb"]["path"]
    hashes = {"parts_glb": P.sha256(parts_glb), "tex_glb": P.sha256(tex_glb)}
    checks = {}
    for key, path in (("parts_glb", parts_glb), ("tex_glb", tex_glb)):
        exp = src[key]
        checks["%s_sha256_as_source_spec" % key] = {
            "passed": hashes[key] == exp["sha256"] and path.stat().st_size == exp["bytes"],
            "measured": {"sha256": hashes[key], "bytes": path.stat().st_size},
            "expected": {"sha256": exp["sha256"], "bytes": exp["bytes"]}}

    scene = U.reset()
    hpt = U.import_glb_parts(tex_glb, "HPT_")
    hpg = U.import_glb_parts(parts_glb, "HPG_")
    names = sorted(profile["parts"], key=U.part_key)
    checks["part_sets_match"] = {"passed": sorted(hpt) == sorted(hpg) == sorted(names),
                                 "measured": {"parts_glb": sorted(hpg, key=U.part_key),
                                              "tex_glb": sorted(hpt, key=U.part_key)},
                                 "expected": names}
    if not checks["part_sets_match"]["passed"]:
        raise RuntimeError("part sets differ: %s" % checks["part_sets_match"])

    # ---- geometry identity (by part): triangles, unique vertex position sets (exact float32), bounds
    per_part = {}
    identical = True
    for n in names:
        a, b = hpg[n].data, hpt[n].data
        ca = np.round(U.coords(a).astype(np.float32), 7)
        cb = np.round(U.coords(b).astype(np.float32), 7)
        ua, ub = np.unique(ca, axis=0), np.unique(cb, axis=0)
        same = ua.shape == ub.shape and bool(np.array_equal(ua, ub))
        tri_a, tri_b = U.triangles(a), U.triangles(b)
        identical &= same and tri_a == tri_b
        per_part[n] = {"triangles": [tri_a, tri_b], "vertices": [len(a.vertices), len(b.vertices)],
                       "unique_positions": [int(len(ua)), int(len(ub))], "unique_position_sets_equal": same,
                       "uv_layers": [[u.name for u in a.uv_layers], [u.name for u in b.uv_layers]],
                       "materials": [len(a.materials), len(b.materials)],
                       "source_bounds_m": [U.rv(ca.min(0), 5), U.rv(ca.max(0), 5)]}
    checks["geometry_identical_parts_vs_textured"] = {
        "passed": identical, "measured": "per part: triangles equal and unique vertex position sets equal (float32)",
        "note": "the textured GLB splits vertices along UV seams (more vertices, same positions)"}

    # ---- final frame map (base normalised to the card-04 footprint, figure uniform)
    base_part = [n for n in names if profile["parts"][n]["mesh"] == "base"][0]
    bc = U.coords(hpg[base_part].data)
    # highest non-base vertex (old rule), or the top of scale.figure_top_part (a raised blade / antlers above the head)
    top = P.figure_top_source_z(profile, {n: float(U.coords(hpg[n].data)[:, 2].max()) for n in names if n != base_part})
    fmap = P.frame_map((bc.min(0), bc.max(0)), top, profile["scale"])
    for n in names:
        is_base = n == base_part
        for obj in (hpg[n], hpt[n]):
            c = U.coords(obj.data)
            cx, cy = fmap["centre_xy_src"]
            if is_base:
                sx, sy, sz = fmap["base_scale"]
                c = np.column_stack(((c[:, 0] - cx) * sx, (c[:, 1] - cy) * sy, (c[:, 2] - fmap["base_bottom_src"]) * sz))
            else:
                s = fmap["figure_scale"]
                c = np.column_stack(((c[:, 0] - cx) * s, (c[:, 1] - cy) * s,
                                     fmap["base_height_m"] + (c[:, 2] - fmap["base_top_src"]) * s))
            U.set_coords(obj.data, c)
            if obj.data.has_custom_normals and is_base:
                pass  # non-uniform base scale: custom normals are re-derived by Blender from the split data
    # optional prepare.part_offsets_m (profile.part_offsets): translate the listed parts in the final frame, after the
    # frame map (the map and every other part keep their bytes); both twins, so the bake rays and the retopo agree
    offsets = P.part_offsets(profile)
    if offsets:
        for n in sorted(offsets, key=U.part_key):
            d = np.asarray(offsets[n], dtype=np.float64)
            for obj in (hpg[n], hpt[n]):
                U.set_coords(obj.data, U.coords(obj.data) + d)
    # optional base.flatten_bottom (profile.base_flatten): flat underside of the base, both twins (module docstring)
    flat_cfg = P.base_flatten(profile)
    flat_rep = flatten_base(hpg[base_part], hpt[base_part], flat_cfg) if flat_cfg is not None else None
    lo, hi = U.bounds(list(hpg.values()))
    fig_lo, fig_hi = U.bounds([hpg[n] for n in names if n != base_part])
    for n in names:
        c = U.coords(hpg[n].data)
        per_part[n]["final_bounds_m"] = [U.rv(c.min(0), 5), U.rv(c.max(0), 5)]
        per_part[n]["final_area_cm2"] = U.r(U.mesh_area(hpg[n].data) * 1e4, 3)

    # ---- orientation of the high-poly parts (the whole figure is the ray target)
    ocfg = profile["orientation"]
    scores = U.orientation_scores([(n, hpg[n]) for n in names], ocfg["samples_per_part"], seed=ocfg.get("seed", 0),
                                  height=float(hi[2] - lo[2]))
    inside_out = sorted((n for n, s in scores.items() if s["score"] is not None and s["score"] < ocfg["flip_below_score"]),
                        key=U.part_key)
    checks["orientation_inside_out_parts_as_profile"] = {
        "passed": inside_out == sorted(ocfg["expected_inside_out_parts"], key=U.part_key),
        "measured": inside_out, "expected": ocfg["expected_inside_out_parts"]}
    for n in inside_out:  # flipped on both twins (bake rays and the retopo source must agree)
        U.flip_mesh(hpg[n].data)
        U.flip_mesh(hpt[n].data)

    for obj in list(hpg.values()) + list(hpt.values()):
        obj.hide_render = False
    hpg_col = bpy.data.collections.new("HPG")
    hpt_col = bpy.data.collections.new("HPT")
    scene.collection.children.link(hpg_col)
    scene.collection.children.link(hpt_col)
    for obj in hpg.values():
        scene.collection.objects.unlink(obj)
        hpg_col.objects.link(obj)
    for obj in hpt.values():
        scene.collection.objects.unlink(obj)
        hpt_col.objects.link(obj)
    blend = run_dir / "work" / "hp.blend"
    blend.parent.mkdir(parents=True, exist_ok=True)
    bpy.ops.file.pack_all()
    bpy.ops.wm.save_as_mainfile(filepath=str(blend), compress=False)

    report = {"stage": "prepare", "sources": {k: {"path": src[k]["path"], "sha256": hashes[k]} for k in hashes},
              "base_part": base_part, "frame_map": {k: (U.rv(v, 8) if isinstance(v, (list, tuple)) else U.r(v, 8))
                                                   for k, v in fmap.items()},
              "frame_note": "Tripo GLB metres (glTF +Z front -> Blender -Y) to final metres: base -> diameter x diameter "
                            "x height of card 04 (non-uniform), other parts uniform x figure_scale about the base centre, "
                            "feet contact with the base top kept from the source",
              "bounds_final_m": [U.rv(lo, 5), U.rv(hi, 5)], "figure_bounds_final_m": [U.rv(fig_lo, 5), U.rv(fig_hi, 5)],
              "orientation": scores, "parts": per_part, "checks": checks,
              "passed": all(c["passed"] for c in checks.values()), "status": "измерено"}
    if P.figure_top_part(profile) is not None:  # profiles without the key keep their report bytes
        report["figure_top_part"] = {"part": P.figure_top_part(profile), "top_m": U.r(fmap["figure_top_m"], 5),
                                     "figure_bounds_top_m": U.r(fig_hi[2], 5),
                                     "note": "scale.figure_top_m is the top of this part; the figure bounds top (weapon, "
                                             "ornaments) frames the concept views (profile.frame_top_m)"}
    if offsets:  # profiles without the key keep their report bytes
        report["part_offsets_m"] = {
            "parts": {n: U.rv(offsets[n], 6) for n in sorted(offsets, key=U.part_key)},
            "frame": "final (metres, -Y front, +X figure left, +Z up), applied after frame_map to HPG_* and HPT_*",
            "note": "parts.<part>.final_bounds_m include the offset; source_bounds_m do not"}
    if flat_rep is not None:  # profiles without base.flatten_bottom keep their report bytes
        report["base_flatten"] = flat_rep
    U.write_json(run_dir / "reports" / "prepare-report.json", report)
    if not report["passed"]:
        raise RuntimeError("prepare checks failed: %s" % [k for k, c in checks.items() if not c["passed"]])
