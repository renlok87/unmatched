"""Stage prepare: import the untextured high-poly by parts (HPG_*) and the textured 8K/PBR high-poly (HPT_*),
match the parts by node name, prove identical geometry, map both into the final frame (card 04), measure the
orientation of every high-poly part (ray escape) and save work/hp.blend."""

from pathlib import Path

import bpy
import numpy as np

from . import bl_util as U
from . import profile as P


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
    top = max(float(U.coords(hpg[n].data)[:, 2].max()) for n in names if n != base_part)
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
    U.write_json(run_dir / "reports" / "prepare-report.json", report)
    if not report["passed"]:
        raise RuntimeError("prepare checks failed: %s" % [k for k, c in checks.items() if not c["passed"]])
