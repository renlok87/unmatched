"""Stage `uv` (headless Blender): one 4K atlas for body, staff and base.

blender -b --factory-startup --python-exit-code 1 --python stage_uv.py -- <profile.json>

1. seams: Smart UV Project per part on a smoothed proxy copy (Smooth modifier, seam_proxy_smooth x iterations; the
   decimated cloth/relief has noisy normals and gave ~4000 mostly single-triangle islands when projected directly,
   measured 2026-09-29), proxy islands smaller than merge_islands_max_faces merged into the neighbour island of the
   same part; seams = proxy island borders + part borders + sharp edges;
2. ABF unwrap (unwrap_method) of the real mesh with these seams; triangles that come out folded (negative UV area)
   and triangles of an island that overlap another triangle of the same island (raster check) get seams on all
   their edges, and the object is unwrapped again (fix_passes);
3. average island scale over all three objects (one world texel density);
4. island scale x td_priority of its part (x cap_td_factor for cap/bridge islands);
5. one pack of all islands (concave shapes, rotation) into 0..1 with pack_margin_px of atlas_px;
6. export per-triangle data for the pixel checks and the maps stage: work/uv/<object>.npz
   (uv[T,3,2], part[T], cap[T], island[T], area3d_m2[T], normal[T,3], pos[T,3,3] = corner positions in the source
   frame, H2.1: the maps stage interpolates them per texel for the 3D material regions).
Output: work/h2-uv.blend, reports/uv-report.json.
"""

import math
import sys
from pathlib import Path

import bmesh
import bpy
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import blib as B  # noqa: E402
import common as C  # noqa: E402
import raster as RS  # noqa: E402

B.require_background("stage_uv.py")


def islands_of(bm, uv):
    """UV islands: faces connected through edges whose two face corners share UV coordinates."""
    bm.faces.ensure_lookup_table()
    island = [-1] * len(bm.faces)
    n = 0
    for f0 in bm.faces:
        if island[f0.index] >= 0:
            continue
        island[f0.index] = n
        stack = [f0]
        while stack:
            f = stack.pop()
            for lp in f.loops:
                e = lp.edge
                for l2 in e.link_loops:
                    g = l2.face
                    if g is f or island[g.index] >= 0:
                        continue
                    # same edge, same UVs at both ends -> connected in UV space
                    a1, b1 = lp[uv].uv, lp.link_loop_next[uv].uv
                    if l2.vert is lp.vert:
                        a2, b2 = l2[uv].uv, l2.link_loop_next[uv].uv
                    else:
                        a2, b2 = l2.link_loop_next[uv].uv, l2[uv].uv
                    if (a1 - a2).length < 1e-6 and (b1 - b2).length < 1e-6:
                        island[g.index] = n
                        stack.append(g)
        n += 1
    return island, n


def scale_islands(obj, factors_by_face):
    bm = bmesh.new()
    bm.from_mesh(obj.data)
    uv = bm.loops.layers.uv.active
    island, n = islands_of(bm, uv)
    faces_of = [[] for _ in range(n)]
    for f in bm.faces:
        faces_of[island[f.index]].append(f)
    for i, faces in enumerate(faces_of):
        fac = sorted(factors_by_face[f.index] for f in faces)[len(faces) // 2]
        if abs(fac - 1.0) < 1e-9:
            continue
        cx = sum(l[uv].uv.x for f in faces for l in f.loops) / sum(len(f.loops) for f in faces)
        cy = sum(l[uv].uv.y for f in faces for l in f.loops) / sum(len(f.loops) for f in faces)
        for f in faces:
            for l in f.loops:
                l[uv].uv.x = cx + (l[uv].uv.x - cx) * fac
                l[uv].uv.y = cy + (l[uv].uv.y - cy) * fac
    bm.to_mesh(obj.data)
    bm.free()
    return n


def uv_signed_areas(me):
    me.calc_loop_triangles()
    T = len(me.loop_triangles)
    loops = np.empty(T * 3, np.int64)
    me.loop_triangles.foreach_get("loops", loops)
    polys = np.empty(T, np.int64)
    me.loop_triangles.foreach_get("polygon_index", polys)
    uvd = np.empty(len(me.loops) * 2, np.float64)
    me.uv_layers[0].data.foreach_get("uv", uvd)
    uv = uvd.reshape(-1, 2)[loops].reshape(T, 3, 2)
    a = 0.5 * ((uv[:, 1, 0] - uv[:, 0, 0]) * (uv[:, 2, 1] - uv[:, 0, 1])
               - (uv[:, 1, 1] - uv[:, 0, 1]) * (uv[:, 2, 0] - uv[:, 0, 0]))
    return a, polys


def seams_and_unwrap(o, prof, ucfg):
    me = o.data
    part_of = B.int_face_attr(me, "um_part")
    parts = sorted(set(part_of.tolist()))
    # smoothed proxy: only for choosing the seams
    proxy = o.copy()
    proxy.data = me.copy()
    bpy.context.scene.collection.objects.link(proxy)
    sm = proxy.modifiers.new("smooth", "SMOOTH")
    sm.factor = float(ucfg["seam_proxy_smooth_factor"])
    sm.iterations = int(ucfg["seam_proxy_smooth_iterations"])
    with B.ctx(proxy):
        bpy.ops.object.modifier_apply(modifier=sm.name)
    B.select_only(proxy)
    for pk in parts:
        name = "tripo_part_%d" % pk
        ang = ucfg["smart_project_angle_deg"].get(name, ucfg["smart_project_angle_deg"]["default"])
        proxy.data.polygons.foreach_set("select", part_of == pk)
        with B.ctx(proxy):
            bpy.ops.object.mode_set(mode="EDIT")
            bpy.ops.uv.smart_project(angle_limit=math.radians(ang), island_margin=0.0, area_weight=0.0,
                                     correct_aspect=True, scale_to_bounds=False)
            bpy.ops.object.mode_set(mode="OBJECT")
    bmp = bmesh.new()
    bmp.from_mesh(proxy.data)
    lab, n_proxy = islands_of(bmp, bmp.loops.layers.uv.active)
    bmp.free()
    bpy.data.objects.remove(proxy)
    bm = bmesh.new()
    bm.from_mesh(me)
    bm.faces.ensure_lookup_table()
    pl = bm.faces.layers.int.get("um_part")
    # merge tiny proxy islands into the neighbour island (same part) sharing most edges
    small = int(ucfg["merge_islands_max_faces"])
    merged = 0
    for _ in range(4):
        faces_of = {}
        for f in bm.faces:
            faces_of.setdefault(lab[f.index], []).append(f)
        changed = 0
        for i in sorted(faces_of, key=lambda k: (len(faces_of[k]), k)):
            faces = faces_of.get(i) or []
            if not faces or len(faces) > small:
                continue
            cnt = {}
            for f in faces:
                for e in f.edges:
                    for g in e.link_faces:
                        if lab[g.index] != i and g[pl] == f[pl]:
                            cnt[lab[g.index]] = cnt.get(lab[g.index], 0) + 1
            if not cnt:
                continue
            tgt = max(sorted(cnt), key=lambda k: cnt[k])
            for f in faces:
                lab[f.index] = tgt
            faces_of[tgt] = faces_of.get(tgt, []) + faces
            faces_of[i] = []
            changed += 1
        merged += changed
        if not changed:
            break
    sharp = me.attributes.get("sharp_edge")
    sharp_vals = np.zeros(len(me.edges), bool)
    if sharp is not None:
        sharp.data.foreach_get("value", sharp_vals)
    bm.edges.ensure_lookup_table()
    cl = bm.faces.layers.int.get("um_cap")
    for e in bm.edges:
        fs = e.link_faces
        e.seam = bool(len(fs) != 2 or lab[fs[0].index] != lab[fs[1].index] or fs[0][pl] != fs[1][pl]
                      or (fs[0][cl] > 0) != (fs[1][cl] > 0) or sharp_vals[e.index])
    bm.to_mesh(me)
    bm.free()
    history = []
    B.select_only(o)
    passes = int(ucfg["fix_passes"])
    for p in range(passes + 1):
        me.polygons.foreach_set("select", np.ones(len(me.polygons), bool))
        with B.ctx(o):
            bpy.ops.object.mode_set(mode="EDIT")
            bpy.ops.uv.unwrap(method=ucfg["unwrap_method"], fill_holes=True, correct_aspect=True, margin=0.0)
            bpy.ops.object.mode_set(mode="OBJECT")
        area, polys = uv_signed_areas(me)
        seam_arr = np.empty(len(me.edges), bool)
        me.edges.foreach_get("use_seam", seam_arr)
        loop_edge = np.empty(len(me.loops), np.int64)
        me.loops.foreach_get("edge_index", loop_edge)
        isolated = {p.index for p in me.polygons
                    if all(seam_arr[loop_edge[li]] for li in p.loop_indices)}  # single-face island: a mirror is no fold
        folded_all = sorted(set(polys[area <= 0].tolist()))
        folded = [f for f in folded_all if f not in isolated]
        bad_faces, bad_isl = self_overlap_faces(me, int(ucfg["overlap_check_px"]))
        history.append({"folded_triangles": len(folded), "self_overlapping_islands": len(bad_isl),
                        "self_overlapping_faces": len(bad_faces),
                        "mirrored_single_triangle_islands": len(folded_all) - len(folded)})
        if (not folded and not bad_faces) or p == passes:
            break
        bm = bmesh.new()
        bm.from_mesh(me)
        bm.faces.ensure_lookup_table()
        for fi in sorted(set(folded) | set(bad_faces)):
            for e in bm.faces[fi].edges:
                e.seam = True
        bm.to_mesh(me)
        bm.free()
    return {"proxy_islands": n_proxy, "tiny_islands_merged": merged, "passes": history}


def self_overlap_faces(me, size):
    """Faces of triangles that cover a texel already covered by another triangle of the same island (raster at
    size px over 0..1, strict inside test: triangles sharing an edge never both cover a texel)."""
    bm = bmesh.new()
    bm.from_mesh(me)
    island, _n = islands_of(bm, bm.loops.layers.uv.active)
    bm.free()
    island = np.asarray(island, np.int64)
    me.calc_loop_triangles()
    T = len(me.loop_triangles)
    loops = np.empty(T * 3, np.int64)
    me.loop_triangles.foreach_get("loops", loops)
    polys = np.empty(T, np.int64)
    me.loop_triangles.foreach_get("polygon_index", polys)
    uvd = np.empty(len(me.loops) * 2, np.float64)
    me.uv_layers[0].data.foreach_get("uv", uvd)
    uv = uvd.reshape(-1, 2)[loops].reshape(T, 3, 2)
    isl_t = island[polys]
    tri_map = np.full((size, size), -1, np.int64)
    bad = set()

    def on_overlap(t, prev):
        same = prev[isl_t[prev] == isl_t[t]] if len(prev) else prev
        if len(same):
            bad.add(int(polys[t]))
            bad.update(int(polys[q]) for q in np.unique(same))

    RS.raster(uv, size, [(np.arange(T), tri_map)], on_overlap)
    islands = sorted({int(island[f]) for f in bad})
    return sorted(bad), islands


def export_triangles(obj, path):
    me = obj.data
    me.calc_loop_triangles()
    tris = me.loop_triangles
    T = len(tris)
    loops = np.empty(T * 3, np.int64)
    tris.foreach_get("loops", loops)
    polys = np.empty(T, np.int64)
    tris.foreach_get("polygon_index", polys)
    uvd = np.empty(len(me.loops) * 2, np.float64)
    me.uv_layers[0].data.foreach_get("uv", uvd)
    uvd = uvd.reshape(-1, 2)
    uv = uvd[loops].reshape(T, 3, 2)
    lv = np.empty(len(me.loops), np.int64)
    me.loops.foreach_get("vertex_index", lv)
    V = B.verts_np(obj)
    P = V[lv[loops]].reshape(T, 3, 3)
    area3d = 0.5 * np.linalg.norm(np.cross(P[:, 1] - P[:, 0], P[:, 2] - P[:, 0]), axis=1)
    normal = np.cross(P[:, 1] - P[:, 0], P[:, 2] - P[:, 0])
    normal /= np.maximum(np.linalg.norm(normal, axis=1, keepdims=True), 1e-30)
    part = B.int_face_attr(me, "um_part")[polys]
    cap = B.int_face_attr(me, "um_cap")[polys]
    bm = bmesh.new()
    bm.from_mesh(me)
    island, _n = islands_of(bm, bm.loops.layers.uv.active)
    bm.free()
    isl = np.asarray(island, np.int64)[polys]
    path.parent.mkdir(parents=True, exist_ok=True)
    np.savez(path, uv=uv, part=part, cap=cap, island=isl, area3d_m2=area3d, normal=normal, pos=P)
    return {"triangles": int(T), "islands": int(isl.max() + 1) if T else 0}


def main():
    prof = C.Profile(B.script_args()[0])
    if not C.load_json(prof.reports / "retopo-report.json")["passed"]:
        raise RuntimeError("retopo stage did not pass")
    B.open_blend(prof.work / "h2-retopo.blend")
    ucfg = prof["uv"]
    objs = [bpy.data.objects["LP_" + k] for k in ("body", "staff", "base")]
    scene = bpy.context.scene
    scene.tool_settings.use_uv_select_sync = True
    for o in objs:
        me = o.data
        while me.uv_layers:
            me.uv_layers.remove(me.uv_layers[0])
        me.uv_layers.new(name="UVMap")
    # 1-2. seams from a smoothed proxy, ABF unwrap, fold fix
    seam_stats = {}
    for o in objs:
        seam_stats[o.name[3:]] = seams_and_unwrap(o, prof, ucfg)
    # 2. uniform density over all objects
    B.select_only(objs)
    for o in objs:
        o.data.polygons.foreach_set("select", np.ones(len(o.data.polygons), bool))
    with B.ctx(objs):
        bpy.ops.object.mode_set(mode="EDIT")
        bpy.ops.uv.average_islands_scale()
        bpy.ops.object.mode_set(mode="OBJECT")
    # 3. priorities
    islands = {}
    for o in objs:
        part_of = B.int_face_attr(o.data, "um_part")
        cap_of = B.int_face_attr(o.data, "um_cap")
        fac = [prof["parts"]["tripo_part_%d" % p]["td_priority"] * (ucfg["cap_td_factor"] if c else 1.0)
               for p, c in zip(part_of, cap_of)]
        islands[o.name] = scale_islands(o, fac)
    # 4. pack
    margin = float(ucfg["pack_margin_px"]) / float(ucfg["atlas_px"])
    with B.ctx(objs):
        bpy.ops.object.mode_set(mode="EDIT")
        bpy.ops.uv.pack_islands(udim_source="CLOSEST_UDIM", rotate=True, rotate_method="ANY", scale=True,
                                merge_overlap=False, margin_method="FRACTION", margin=margin, pin=False,
                                shape_method=ucfg["pack_shape_method"])
        bpy.ops.object.mode_set(mode="OBJECT")
    # 5. data for checks
    out = {}
    uv_all = []
    for o in objs:
        out[o.name[3:]] = export_triangles(o, prof.work / "uv" / (o.name[3:] + ".npz"))
        d = np.empty(len(o.data.loops) * 2)
        o.data.uv_layers[0].data.foreach_get("uv", d)
        uv_all.append(d.reshape(-1, 2))
    uv_all = np.concatenate(uv_all)
    # after the final pack: no texel of the atlas covered twice (any island, any object)
    tris = []
    for o in objs:
        z = np.load(prof.work / "uv" / (o.name[3:] + ".npz"))
        tris.append(z["uv"])
    cnt = RS.raster(np.concatenate(tris), int(ucfg["atlas_px"]))
    overlap_texels = int((cnt > 1).sum())
    lo, hi = uv_all.min(0), uv_all.max(0)
    checks = {}
    C.check(checks, "uv0_in_unit_square", bool((lo >= 0).all() and (hi <= 1).all()), {"min": C.rv(lo, 6), "max": C.rv(hi, 6)}, "[0, 1]")
    folded = {k: v["passes"][-1] for k, v in seam_stats.items()}
    C.check(checks, "no_folded_or_self_overlapping_uv", not any(v["folded_triangles"] or v["self_overlapping_islands"] for v in folded.values()),
            folded, 0, "after the last unwrap pass: UV triangles with negative/zero area; islands overlapping themselves "
            "(raster at overlap_check_px)")
    C.check(checks, "no_overlap_texels_after_pack", overlap_texels == 0, overlap_texels, 0,
            "texel centres covered by more than one UV triangle at atlas_px after the final pack")
    C.check(checks, "one_uv_layer", all(len(o.data.uv_layers) == 1 for o in objs), [len(o.data.uv_layers) for o in objs], 1)
    B.save_blend(prof.work / "h2-uv.blend")
    report = {"stage": "uv", "profile": C.rel(prof.path), "profile_id": prof["profile_id"],
              "method": ucfg["note"], "seams": seam_stats, "pack_margin_fraction": C.r(margin, 8), "islands_after_priority": islands,
              "objects": out, "checks": checks, "passed": all(c["passed"] for c in checks.values()),
              "note": "pixel gaps, overlaps and texel density are measured by the maps stage on the rasterised atlas"}
    C.write_json(prof.reports / "uv-report.json", report)
    print("H2_STAGE_OK uv passed=%s" % report["passed"])
    if not report["passed"]:
        raise RuntimeError("uv checks failed")


main()
