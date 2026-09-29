"""Stage lowpoly (headless): per-part retopology of the H2 high-poly, cleanup, UV unwrap and one 4K atlas pack.

    blender -b --factory-startup --python stage_lowpoly.py -- <profile.json> <run_dir>

Input: the untextured "parts" GLB (welded, no UV seams: the best decimation input; stage inspect proved it is the same
geometry as the textured GLB). Output: work/h2-lowpoly.blend (LP_* objects in the Tripo frame, the frame the bake
uses), work/h2-highpoly-repaired.blend is NOT written (the bake stage re-applies the same repairs to the textured
GLB), reports/lowpoly-report.json and work/uv-triangles.npz (for stage uvcheck).

Retopology = quadric collapse decimation (Blender Decimate COLLAPSE, triangulated) per part to the profile's triangle
target: on a uniform 2M marching-cubes surface it keeps the silhouette and creases better than voxel remesh (which
would weld the thin cloak shell and round the blade edges). It is an automatic retopology, not a hand-made quad mesh.
"""

import math
import sys
import time
from pathlib import Path

import bmesh
import bpy
import numpy as np
from bpy_extras import bmesh_utils
from mathutils import Matrix, Vector
from mathutils.bvhtree import BVHTree

sys.path.insert(0, str(Path(__file__).resolve().parent))
import bl  # noqa: E402
import pure as P  # noqa: E402
import charts  # noqa: E402
import repairs  # noqa: E402

bl.require_background("stage_lowpoly.py")
args = bl.script_args()
PROFILE_PATH, RUN = Path(args[0]).resolve(), Path(args[1]).resolve()
profile = P.load_json(PROFILE_PATH)
paths = P.run_paths(RUN)
for key in ("reports", "work"):
    paths[key].mkdir(parents=True, exist_ok=True)
t0 = time.time()
cfg = profile["lowpoly"]
parts_cfg = profile["parts"]

bpy.ops.wm.read_factory_settings(use_empty=True)
scene = bpy.context.scene
src = P.repo_path(profile["sources"]["parts_glb"]["path"])
if P.sha256(src) != profile["sources"]["parts_glb"]["sha256"]:
    raise RuntimeError("parts GLB sha256 mismatch")
high, coll_high = bl.import_glb_parts(src, "H2_HIGH")
repair_log = repairs.apply_geometry_repairs(high, profile)
kept = [n for n in high if n in parts_cfg and not parts_cfg[n].get("drop")]
missing = sorted(set(n for n, c in parts_cfg.items() if not c.get("drop")) - set(high))
if missing:
    raise RuntimeError("profile parts missing in GLB: %s" % missing)


def ctx(obj):
    return bpy.context.temp_override(object=obj, active_object=obj, selected_objects=[obj],
                                     selected_editable_objects=[obj])


def clear_custom_normals(obj):
    for o in bpy.context.view_layer.objects:
        o.select_set(False)
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj
    if obj.data.has_custom_normals:
        bpy.ops.mesh.customdata_custom_splitnormals_clear()
    if obj.data.has_custom_normals:
        raise RuntimeError("custom normals of %s were not cleared" % obj.name)


def decimate_copy(obj, target, name):
    """New object = collapse-decimated copy of obj with about `target` triangles."""
    tris = sum(len(p.vertices) - 2 for p in obj.data.polygons)
    mesh_src = obj.data.copy()
    tmp = bpy.data.objects.new(name + "_tmp", mesh_src)
    scene.collection.objects.link(tmp)
    bpy.context.view_layer.update()
    clear_custom_normals(tmp)
    mod = tmp.modifiers.new("h2_decimate", "DECIMATE")
    mod.decimate_type = "COLLAPSE"
    mod.ratio = min(1.0, float(target) / tris)
    mod.use_collapse_triangulate = True
    mod.use_symmetry = False
    dg = bpy.context.evaluated_depsgraph_get()
    me = bpy.data.meshes.new_from_object(tmp.evaluated_get(dg), preserve_all_data_layers=False)
    me.name = name
    bpy.data.objects.remove(tmp)
    bpy.data.meshes.remove(mesh_src)
    out = bpy.data.objects.new(name, me)
    return out, tris


def collapse_slivers(bm, min_area, passes=12):
    """Collapse the shortest edge of every triangle below min_area (UE's mesh build drops such triangles and
    leaves holes: measured 80 on the first sword build); repeated until none is left or `passes` is reached."""
    collapsed = 0
    for _ in range(passes):
        small = [f for f in bm.faces if f.calc_area() < min_area]
        if not small:
            break
        edges, seen, used = [], set(), set()
        for f in sorted(small, key=lambda f: f.index):
            e = min(f.edges, key=lambda e: (e.calc_length(), e.index))
            if e in seen or e.verts[0] in used or e.verts[1] in used:
                continue
            seen.add(e)
            used.update(e.verts)
            edges.append(e)
        bmesh.ops.collapse(bm, edges=edges, uvs=False)
        collapsed += len(edges)
        bmesh.ops.dissolve_degenerate(bm, edges=bm.edges, dist=1e-9)
        bm.faces.index_update()
        bm.edges.index_update()
    left = sum(1 for f in bm.faces if f.calc_area() < min_area)
    return collapsed, left


def cleanup(obj, weld_m, min_area=0.0):
    bm = bmesh.new()
    bm.from_mesh(obj.data)
    before_v, before_f = len(bm.verts), len(bm.faces)
    bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=weld_m)
    bmesh.ops.dissolve_degenerate(bm, edges=bm.edges, dist=weld_m)
    bmesh.ops.triangulate(bm, faces=[f for f in bm.faces if len(f.verts) > 3])
    sliver_edges, sliver_left = collapse_slivers(bm, min_area) if min_area > 0 else (0, 0)
    # duplicate faces (same vertex set) are dropped by the FBX round trip: keep the first
    keys, dup = set(), []
    for f in bm.faces:
        k = tuple(sorted(v.index for v in f.verts))
        if k in keys or len(set(k)) < 3:
            dup.append(f)
        keys.add(k)
    bmesh.ops.delete(bm, geom=dup, context="FACES_ONLY")
    loose_e = [e for e in bm.edges if not e.link_faces]
    bmesh.ops.delete(bm, geom=loose_e, context="EDGES")
    loose_v = [v for v in bm.verts if not v.link_edges]
    bmesh.ops.delete(bm, geom=loose_v, context="VERTS")
    tiny = [f for f in bm.faces if f.calc_area() < 1e-12]
    bmesh.ops.delete(bm, geom=tiny, context="FACES_ONLY")
    bmesh.ops.triangulate(bm, faces=[f for f in bm.faces if len(f.verts) > 3])
    stats = {"welded_vertices": before_v - len(bm.verts), "faces_removed": before_f - len(bm.faces),
             "zero_area_faces_removed": len(tiny), "sliver_edges_collapsed": sliver_edges,
             "slivers_left_below_min_area": sliver_left, "duplicate_faces_removed": len(dup)}
    bm.to_mesh(obj.data)
    bm.free()
    obj.data.shade_smooth()
    return stats


def deviation(high_obj, low_obj, samples):
    """Surface distance both ways (mm, source frame): high vertices -> low surface and low vertices -> high."""
    co_h, tris_h, _ = bl.mesh_arrays(high_obj)
    co_l, tris_l, _ = bl.mesh_arrays(low_obj)
    bvh_l = BVHTree.FromPolygons([tuple(v) for v in co_l], [tuple(int(i) for i in t) for t in tris_l],
                                 all_triangles=True)
    bvh_h = BVHTree.FromPolygons([tuple(v) for v in co_h], [tuple(int(i) for i in t) for t in tris_h],
                                 all_triangles=True)
    step = max(1, len(co_h) // samples)
    d_hl = np.array([bvh_l.find_nearest(Vector(p))[3] for p in co_h[::step]])
    d_lh = np.array([bvh_h.find_nearest(Vector(p))[3] for p in co_l])

    def stats(d):
        return {"mean_mm": P.r(d.mean() * 1000, 3), "p95_mm": P.r(np.percentile(d, 95) * 1000, 3),
                "max_mm": P.r(d.max() * 1000, 3)}
    return {"high_to_low": stats(d_hl), "low_to_high": stats(d_lh), "high_samples": int(len(d_hl))}


coll_low = bpy.data.collections.new("H2_LOW")
scene.collection.children.link(coll_low)
low = {}
report = {"schema": "unmatched.h2-bake.lowpoly/1", "profile": P.rel(PROFILE_PATH), "repairs": repair_log,
          "parts": {}, "method": cfg["method_note"]}
for name in kept:
    pc = parts_cfg[name]
    obj, src_tris = decimate_copy(high[name], pc["target_tris"], "LP_" + name)
    coll_low.objects.link(obj)
    hf = profile["repairs"].get("fill_phantom_holes", {})
    holes = None
    if name in hf.get("parts", []) and repairs.PHANTOM_POINTS:
        pts = np.concatenate([v for _k, v in sorted(repairs.PHANTOM_POINTS.items())])
        holes = repairs.fill_phantom_holes(obj, pts, float(hf["max_dist_m"]), int(hf["max_edges"]))
    clean = cleanup(obj, float(cfg["weld_m"]), float(cfg["min_triangle_area_m2_tripo_frame"]))
    if holes is not None:
        clean["phantom_holes_filled"] = holes
    for sb in profile["repairs"].get("smooth_boxes", []):
        if sb["part"] == name:
            clean.setdefault("smoothed_boxes", []).append(repairs.smooth_box(obj, sb))
    low[name] = obj
    tris = len(obj.data.polygons)
    if obj.data.has_custom_normals:
        raise RuntimeError("low mesh %s kept custom normals" % name)
    report["parts"][name] = {"role": pc["role"], "source_triangles": src_tris, "target_triangles": pc["target_tris"],
                             "triangles": tris, "vertices": len(obj.data.vertices), "cleanup": clean,
                             "topology": bl.edge_topology(obj)}
    print("decimated", name, src_tris, "->", tris, round(time.time() - t0, 1), flush=True)

# ---------------------------------------------------------------- weapon grip bridge (hidden inside the fist)
bridge_cfg = cfg.get("grip_bridge")
if bridge_cfg:
    info, bridge = repairs.grip_bridge(high, bridge_cfg)
    report["grip_bridge"] = info
    if bridge is not None:
        coll_low.objects.link(bridge)
        bridge.data.shade_smooth()
        low[bridge_cfg["name"]] = bridge

# ---------------------------------------------------------------- deviation (before UV: geometry only)
for name in kept:
    report["parts"][name]["deviation"] = deviation(high[name], low[name], int(cfg["deviation_samples"]))
print("deviation done", round(time.time() - t0, 1), flush=True)

# ---------------------------------------------------------------- UV: charts per part (charts.py)
uv_cfg = profile["uv"]
scene.tool_settings.use_uv_select_sync = True


def activate(objs):
    for o in bpy.context.view_layer.objects:
        o.select_set(False)
    for o in objs:
        o.select_set(True)
    bpy.context.view_layer.objects.active = objs[0]


chart_log = {}
for name, obj in low.items():
    obj.data.uv_layers.new(name="UVMap")
    chart_log[name] = charts.chart_unwrap(obj, uv_cfg["charts"])
print("charted", round(time.time() - t0, 1), flush=True)


def island_list(obj):
    bm = bmesh.new()
    bm.from_mesh(obj.data)
    uv = bm.loops.layers.uv.active
    bm.faces.ensure_lookup_table()
    islands = bmesh_utils.bmesh_linked_uv_islands(bm, uv)
    out = []
    for isl in islands:
        a3 = sum(f.calc_area() for f in isl)
        auv = 0.0
        for f in isl:
            pts = [l[uv].uv for l in f.loops]
            for k in range(1, len(pts) - 1):
                auv += abs((pts[k].x - pts[0].x) * (pts[k + 1].y - pts[0].y) -
                           (pts[k + 1].x - pts[0].x) * (pts[k].y - pts[0].y)) * 0.5
        nz = sum(f.normal.z * f.calc_area() for f in isl) / max(a3, 1e-30)
        out.append({"faces": sorted(f.index for f in isl), "a3": a3, "auv": auv, "nz": nz})
    bm.free()
    return out


density_log = {}
for name, obj in low.items():
    pc = parts_cfg.get(name, {})
    prio = float(pc.get("texel_priority", 1.0)) if name in parts_cfg else float(bridge_cfg.get("texel_priority", 0.3))
    islands = island_list(obj)
    uvl = obj.data.uv_layers["UVMap"].data
    loops_of = {p.index: list(p.loop_indices) for p in obj.data.polygons}
    n_bottom = 0
    for isl in islands:
        k = prio
        rule = pc.get("bottom_faces_priority") if pc else None
        if rule is not None and isl["nz"] < -0.9:
            k = float(rule)
            n_bottom += 1
        if isl["auv"] <= 0 or isl["a3"] <= 0:
            continue
        s = k * math.sqrt(isl["a3"] / isl["auv"])
        loops = [li for fi in isl["faces"] for li in loops_of[fi]]
        cu = sum(uvl[li].uv.x for li in loops) / len(loops)
        cv = sum(uvl[li].uv.y for li in loops) / len(loops)
        for li in loops:
            u, v = uvl[li].uv
            uvl[li].uv = (cu + (u - cu) * s, cv + (v - cv) * s)
    density_log[name] = {"islands": len(islands), "priority": prio, "bottom_islands_scaled": n_bottom,
                         "charts": chart_log[name]}

# ---------------------------------------------------------------- one atlas pack (all LP objects together)
objs = list(low.values())
activate(objs)
bpy.ops.object.mode_set(mode="EDIT")
bpy.ops.mesh.select_all(action="SELECT")
bpy.ops.uv.select_all(action="SELECT")
bpy.ops.uv.pack_islands(udim_source="CLOSEST_UDIM", rotate=True, rotate_method="ANY", scale=True,
                        merge_overlap=False, margin_method="FRACTION", margin=float(uv_cfg["pack_margin_fraction"]),
                        pin=False, shape_method=uv_cfg.get("pack_shape", "CONCAVE"))
bpy.ops.uv.seams_from_islands(mark_seams=True, mark_sharp=False)
bpy.ops.object.mode_set(mode="OBJECT")
print("packed", round(time.time() - t0, 1), flush=True)

# sharp edges only where the UVs are split (a hard normal needs a UV seam for a clean bake)
sharp_cos = math.cos(math.radians(float(uv_cfg["sharp_angle_deg"])))
for name, obj in low.items():
    bm = bmesh.new()
    bm.from_mesh(obj.data)
    n = 0
    for e in bm.edges:
        e.smooth = True
        if e.seam and len(e.link_faces) == 2:
            if e.link_faces[0].normal.dot(e.link_faces[1].normal) < sharp_cos:
                e.smooth = False
                n += 1
    bm.to_mesh(obj.data)
    bm.free()
    density_log[name]["sharp_edges"] = n

# ---------------------------------------------------------------- UV triangles for stage uvcheck
names = list(low)
rows_uv, rows_obj, rows_a3, rows_nz, rows_isl = [], [], [], [], []
isl_offset = 0
for oi, name in enumerate(names):
    obj = low[name]
    me = obj.data
    me.calc_loop_triangles()
    uvl = me.uv_layers["UVMap"].data
    islands = island_list(obj)
    face_isl = np.zeros(len(me.polygons), dtype=np.int64)
    for ii, isl in enumerate(islands):
        face_isl[isl["faces"]] = isl_offset + ii
    isl_offset += len(islands)
    for lt in me.loop_triangles:
        rows_uv.append([tuple(uvl[li].uv) for li in lt.loops])
        rows_obj.append(oi)
        rows_a3.append(lt.area)
        rows_nz.append(lt.normal.z)
        rows_isl.append(face_isl[lt.polygon_index])
np.save(paths["work"] / "phantom-points.npy",
        np.concatenate([v[::int(profile["repairs"]["phantom_points_stride"])] for _k, v in sorted(repairs.PHANTOM_POINTS.items())]))
np.savez_compressed(paths["work"] / "uv-triangles.npz", uv=np.array(rows_uv, dtype=np.float64),
                    obj=np.array(rows_obj), area3d=np.array(rows_a3), nz=np.array(rows_nz),
                    island=np.array(rows_isl), names=np.array(names))
report["uv"] = {"method": uv_cfg["method_note"], "per_object": density_log, "objects": names}
report["totals"] = {"triangles_all": int(sum(len(o.data.polygons) for o in low.values())),
                    "triangles_by_group": {}}
for gname, members in profile["groups"].items():
    report["totals"]["triangles_by_group"][gname] = int(sum(len(low[m].data.polygons) for m in members if m in low))

# keep only the low collection in the work file
for obj in list(coll_high.objects):
    bpy.data.objects.remove(obj)
bpy.data.collections.remove(coll_high)
bpy.data.orphans_purge(do_recursive=True)
out = paths["work"] / "h2-lowpoly.blend"
bpy.ops.wm.save_as_mainfile(filepath=str(out), compress=False)
report["work_blend"] = P.rel(out)
report["seconds"] = round(time.time() - t0, 1)
P.write_json(paths["reports"] / "lowpoly-report.json", report)
print(P.STAGE_MARKER, "lowpoly", report["totals"], round(time.time() - t0, 1))
