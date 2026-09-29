"""Stage retopo: game mesh per part from the untextured high-poly (HPG_*, manifold topology; the textured twin
is split along UV seams and would open cracks when decimated).

Per part: collapse decimation (QEM, silhouette-preserving) to retopo.target_tris; a dense region (face) is kept
denser by two steps: (1) the whole part to the region's density, (2) a masked collapse (region protected) down to
the part budget. Then cleanup (merge 1e-6 m, degenerate dissolve, loose geometry, triangulate, tiny islands),
smooth shading, ray-escape orientation of the low-poly, deviation low <-> high in mm. Saves work/lp.blend."""

from pathlib import Path

import bmesh
import bpy
import numpy as np
from mathutils import Vector
from mathutils.bvhtree import BVHTree

from . import bl_util as U


def decimate(obj, ratio, mask_group=None):
    mod = obj.modifiers.new("h2_decimate", "DECIMATE")
    mod.decimate_type = "COLLAPSE"
    mod.ratio = max(min(ratio, 1.0), 1e-5)
    mod.use_collapse_triangulate = True
    mod.use_symmetry = False
    if mask_group:
        mod.vertex_group = mask_group  # weight 0 = protected (measured: the group is a hard mask, not a bias)
    dg = bpy.context.evaluated_depsgraph_get()
    new = bpy.data.meshes.new_from_object(obj.evaluated_get(dg), preserve_all_data_layers=True, depsgraph=dg)
    obj.modifiers.remove(mod)
    old = obj.data
    obj.data = new
    new.name = old.name
    bpy.data.meshes.remove(old)


def in_box(co, box):
    lo, hi = np.array(box[0]), np.array(box[1])
    return np.all((co >= lo) & (co <= hi), axis=1)


def region_triangles(mesh, box):
    co = U.coords(mesh)
    inside = in_box(co, box)
    n = 0
    for p in mesh.polygons:
        if all(inside[v] for v in p.vertices):
            n += len(p.vertices) - 2
    return n


def cleanup(mesh, cfg):
    bm = bmesh.new()
    bm.from_mesh(mesh)
    stats = {}
    before = len(bm.verts)
    bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=cfg["merge_distance_m"])
    stats["merged_vertices"] = before - len(bm.verts)
    res = bmesh.ops.dissolve_degenerate(bm, dist=cfg["degenerate_distance_m"], edges=bm.edges)
    loose_v = [v for v in bm.verts if not v.link_faces]
    loose_e = [e for e in bm.edges if not e.link_faces]
    bmesh.ops.delete(bm, geom=loose_e, context="EDGES")
    bmesh.ops.delete(bm, geom=[v for v in loose_v if v.is_valid], context="VERTS")
    stats["loose_removed"] = len(loose_v) + len(loose_e)
    ngons = [f for f in bm.faces if len(f.verts) > 3]
    bmesh.ops.triangulate(bm, faces=ngons, quad_method="BEAUTY", ngon_method="BEAUTY")
    stats["triangulated_ngons"] = len(ngons)
    # tiny islands (collapsed crumbs): connected face sets below the area threshold
    bm.faces.ensure_lookup_table()
    seen, removed_faces, removed_islands = set(), 0, 0
    doomed = []
    for f in bm.faces:
        if f.index in seen:
            continue
        stack, island = [f], []
        seen.add(f.index)
        while stack:
            g = stack.pop()
            island.append(g)
            for e in g.edges:
                for h in e.link_faces:
                    if h.index not in seen:
                        seen.add(h.index)
                        stack.append(h)
        if sum(g.calc_area() for g in island) < cfg["tiny_island_area_m2"]:
            doomed.extend(island)
            removed_islands += 1
    removed_faces = len(doomed)
    if doomed:
        bmesh.ops.delete(bm, geom=doomed, context="FACES")
    stats["tiny_islands_removed"] = removed_islands
    stats["tiny_island_faces_removed"] = removed_faces
    zero = [f for f in bm.faces if f.calc_area() < cfg["degenerate_area_m2"]]
    stats["near_degenerate_faces_left"] = len(zero)
    bm.to_mesh(mesh)
    bm.free()
    mesh.update()
    return stats


def convex_hull_2d(pts):
    pts = sorted(set(pts))
    if len(pts) < 3:
        return pts

    def cross(o, a, b):
        return (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0])

    lower, upper = [], []
    for p in pts:
        while len(lower) >= 2 and cross(lower[-2], lower[-1], p) <= 0:
            lower.pop()
        lower.append(p)
    for p in reversed(pts):
        while len(upper) >= 2 and cross(upper[-2], upper[-1], p) <= 0:
            upper.pop()
        upper.append(p)
    return lower[:-1] + upper[:-1]  # counter-clockwise seen from +Z


def cap_holes(mesh, cfg):
    """Close the openings of a flat top (the Tripo base top is cut open under the feet and the hem: dark holes in
    the K2 frame, measured). Each boundary loop in the z band gets a separate flat convex-hull cap (fan, normal +Z)
    `sink_m` below the lowest loop vertex: the cap covers the hole, the surrounding top hides its overlap, and the
    mesh topology is not touched (sewing caps into Tripo's ragged loops produced chord edges and duplicate faces —
    measured: 33 duplicate triangles dropped by the FBX round trip). The caps are baked like any face; the
    high-poly has no surface in the holes, so those texels are cage misses filled by the textures stage."""
    from candidate_build.closure import ordered_boundary_loops

    bm = bmesh.new()
    bm.from_mesh(mesh)
    z0, z1 = cfg["z_band_m"]
    sink = float(cfg.get("sink_m", 0.0003))
    in_band = lambda e: all(z0 <= v.co.z <= z1 for v in e.verts)
    loops = ordered_boundary_loops(bm, select=in_band)
    before = len(bm.faces)
    area, capped = 0.0, 0
    for lp in loops:
        hull = convex_hull_2d([(round(v.co.x, 7), round(v.co.y, 7)) for v in lp["verts"]])
        if len(hull) < 3:
            continue
        z = min(v.co.z for v in lp["verts"]) - sink
        cx = sum(p[0] for p in hull) / len(hull)
        cy = sum(p[1] for p in hull) / len(hull)
        centre = bm.verts.new((cx, cy, z))
        ring = [bm.verts.new((p[0], p[1], z)) for p in hull]
        for k in range(len(ring)):
            f = bm.faces.new((centre, ring[k], ring[(k + 1) % len(ring)]))
            f.smooth = True
            area += f.calc_area()
        capped += 1
    after = len(bm.faces)
    bm.to_mesh(mesh)
    bm.free()
    mesh.update()
    return {"loops_in_band": len(loops), "loops_capped": capped, "cap_area_cm2": round(area * 1e4, 3),
            "faces_added": after - before, "sink_m": sink, "z_band_m": [z0, z1],
            "method": "separate convex-hull fan per loop, below the rim (topology of the top untouched)"}


def topology(mesh):
    bm = bmesh.new()
    bm.from_mesh(mesh)
    nonman = sum(1 for e in bm.edges if not e.is_manifold)
    boundary = sum(1 for e in bm.edges if e.is_boundary)
    bm.verts.ensure_lookup_table()
    seen, isl = set(), 0
    for v in bm.verts:
        if v.index in seen:
            continue
        isl += 1
        stack = [v]
        seen.add(v.index)
        while stack:
            x = stack.pop()
            for e in x.link_edges:
                w = e.other_vert(x)
                if w.index not in seen:
                    seen.add(w.index)
                    stack.append(w)
    bm.free()
    return {"non_manifold_edges": nonman, "boundary_edges": boundary, "islands": isl}


def deviation(hi_obj, lo_obj, samples, rng):
    """hi -> lo (silhouette / detail loss) and lo -> hi (low surface off the high one), millimetres."""
    hc = U.coords(hi_obj.data)
    lc = U.coords(lo_obj.data)
    pick = rng.choice(len(hc), min(samples, len(hc)), replace=False)
    lo_bvh = BVHTree.FromPolygons([Vector(c) for c in lc], [list(p.vertices) for p in lo_obj.data.polygons])
    hi_bvh = BVHTree.FromPolygons([Vector(c) for c in hc], [list(p.vertices) for p in hi_obj.data.polygons])
    d1 = np.array([lo_bvh.find_nearest(Vector(hc[i]))[3] for i in sorted(pick)]) * 1000.0
    lp = np.array([p.center for p in lo_obj.data.polygons]) if len(lo_obj.data.polygons) else np.zeros((0, 3))
    pts = np.vstack([lc, lp])
    d2 = np.array([hi_bvh.find_nearest(Vector(c))[3] for c in pts]) * 1000.0
    f = lambda d: {"p50": U.r(np.percentile(d, 50), 4), "p95": U.r(np.percentile(d, 95), 4),
                   "p99": U.r(np.percentile(d, 99), 4), "max": U.r(d.max(), 4)}
    return {"hi_to_lo_mm": f(d1), "lo_to_hi_mm": f(d2), "hi_samples": int(len(d1)), "lo_samples": int(len(d2))}


def run(params, profile):
    run_dir = Path(params["run_dir"])
    bpy.ops.wm.open_mainfile(filepath=str(run_dir / "work" / "hp.blend"))
    scene = bpy.context.scene
    names = sorted(profile["parts"], key=U.part_key)
    rcfg = profile["retopo"]
    cfg_clean = rcfg["cleanup"]
    # drop the textured twin from this file (only HPG is the decimation source)
    for obj in [o for o in bpy.data.objects if o.name.startswith("HPT_")]:
        bpy.data.objects.remove(obj)
    col = bpy.data.collections.new("LP")
    scene.collection.children.link(col)
    rng = np.random.default_rng(rcfg.get("seed", 0))
    parts = {}
    for n in names:
        hi = bpy.data.objects["HPG_" + n]
        target = int(rcfg["target_tris"][n])
        me = hi.data.copy()
        me.name = "LP_" + n
        lo = bpy.data.objects.new("LP_" + n, me)
        col.objects.link(lo)
        hi_tris = U.triangles(hi.data)
        info = {"hi_triangles": hi_tris, "target_triangles": target}
        region = next((d for d in rcfg.get("dense_regions", []) if d["part"] == n), None)
        if region:
            region_hi = region_triangles(hi.data, region["box_m"])
            ratio_a = min(1.0, region["target_tris"] / max(region_hi, 1))
            decimate(lo, ratio_a)
            region_mid = region_triangles(lo.data, region["box_m"])
            co = U.coords(lo.data)
            inside = in_box(co, region["box_m"])
            grp = lo.vertex_groups.new(name="h2_decimate_mask")
            grp.add([int(i) for i in np.nonzero(~inside)[0]], 1.0, "REPLACE")
            now = U.triangles(lo.data)
            decimate(lo, target / max(now, 1), mask_group=grp.name)
            lo.vertex_groups.remove(lo.vertex_groups["h2_decimate_mask"])
            info["dense_region"] = {"name": region["name"], "box_m": region["box_m"], "hi_triangles": region_hi,
                                    "after_step1_triangles": region_mid,
                                    "final_triangles": region_triangles(lo.data, region["box_m"]),
                                    "target_triangles": region["target_tris"]}
        elif target < hi_tris:
            decimate(lo, target / hi_tris)
        info["cleanup"] = cleanup(lo.data, cfg_clean)
        cap = next((c for c in rcfg.get("caps", []) if c["part"] == n), None)
        if cap:
            info["caps"] = cap_holes(lo.data, cap)
        for p in lo.data.polygons:
            p.use_smooth = True
        lo.data.update()
        info["triangles"] = U.triangles(lo.data)
        info["vertices"] = len(lo.data.vertices)
        info["topology"] = topology(lo.data)
        info["topology_hi"] = topology(hi.data) if rcfg.get("measure_hi_topology", True) else None
        info["deviation"] = deviation(hi, lo, rcfg["deviation_samples"], rng)
        info["area_cm2"] = U.r(U.mesh_area(lo.data) * 1e4, 3)
        parts[n] = info
        print("H2_RETOPO", n, info["triangles"], info["deviation"]["hi_to_lo_mm"]["p95"], flush=True)
    lo_objs = [(n, bpy.data.objects["LP_" + n]) for n in names]
    lo_lo, lo_hi = U.bounds([o for _n, o in lo_objs])
    ocfg = profile["orientation"]
    scores = U.orientation_scores(lo_objs, ocfg["samples_per_part"], seed=ocfg.get("seed", 0), height=float(lo_hi[2] - lo_lo[2]))
    flipped = []
    for n, s in scores.items():
        if s["score"] is not None and s["score"] < ocfg["flip_below_score"]:
            U.flip_mesh(bpy.data.objects["LP_" + n].data)
            flipped.append(n)
    after = U.orientation_scores(lo_objs, ocfg["samples_per_part"], seed=ocfg.get("seed", 0), height=float(lo_hi[2] - lo_lo[2])) if flipped else scores
    for n in names:
        parts[n]["orientation"] = {"before": scores[n], "after": after[n]}
    for obj in [o for o in bpy.data.objects if o.name.startswith("HPG_")]:
        bpy.data.objects.remove(obj)
    for m in [m for m in bpy.data.meshes if m.users == 0]:
        bpy.data.meshes.remove(m)
    bpy.ops.wm.save_as_mainfile(filepath=str(run_dir / "work" / "lp.blend"), compress=False)
    groups = {}
    for n in names:
        groups.setdefault(profile["parts"][n]["mesh"], 0)
        groups[profile["parts"][n]["mesh"]] += parts[n]["triangles"]
    checks = {
        "all_parts_outward_low_poly": {"passed": all((after[n]["score"] or 0) >= ocfg["min_score_after_fix"] for n in names),
                                       "measured": {n: after[n]["score"] for n in names},
                                       "expected": ">= %s" % ocfg["min_score_after_fix"]},
        "flipped_low_poly_parts": {"passed": flipped == [], "measured": flipped, "expected": [],
                                   "note": "decimation keeps the high-poly winding; a flip here would mean a collapse error"},
        "near_degenerate_faces": {"passed": all(parts[n]["cleanup"]["near_degenerate_faces_left"] == 0 for n in names),
                                  "measured": {n: parts[n]["cleanup"]["near_degenerate_faces_left"] for n in names},
                                  "expected": 0},
    }
    report = {"stage": "retopo", "method": rcfg["method"], "parts": parts, "triangles_by_mesh": groups,
              "triangles_figure": groups.get("body", 0) + groups.get("weapon", 0),
              "triangles_total": sum(groups.values()), "checks": checks,
              "passed": all(c["passed"] for c in checks.values()), "status": "измерено"}
    U.write_json(run_dir / "reports" / "retopo-report.json", report)
    if not report["passed"]:
        raise RuntimeError("retopo checks failed: %s" % [k for k, c in checks.items() if not c["passed"]])
