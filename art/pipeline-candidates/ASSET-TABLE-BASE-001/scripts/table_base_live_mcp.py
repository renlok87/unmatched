"""ASSET-TABLE-BASE-001, Blender stage in a LIVE Blender GUI through Blender MCP (execute_code), step by step.

Same geometry/texture/export code as table_base_candidate.py (that file is executed without its trailing main()
call, together with the static_prop_candidate.py helpers it loads); what differs is only the session handling:
  * never read_factory_settings: works in its own scene "TableBase" (collection "TableBase"), the other scenes of
    the live session stay untouched; the window is switched to that scene so viewport shots show the work;
  * one MCP call per step, state kept in bpy.app.driver_namespace["table_base_live"];
  * round trip runs in a temporary scene that is removed afterwards;
  * the .blend is written as a copy (save_as_mainfile copy=True) with the glTF source images removed.

Driver (repo root as cwd; BLENDER_MCP_PORT = port of the live addon):
  python C:/Users/ren/.claude/mcp-servers/clients/blender_mcp.py exec-str \
    "STEP='setup'; PARAMS=r'<run>/reports/candidate-params.json'; exec(compile(open(r'<this file>', \
     encoding='utf-8').read(), r'<this file>', 'exec'))"
Steps (2026-09-30 fix run, params with "body" + "lip"): setup, import, cut, lip, liptex, relation, textures, export,
roundtrip, report; boardref / view are for viewport shots (board FBX as context; VIEW = camera dict).
First run of 2026-09-30 (superseded): setup, import, cut, capuv, capbake, relation, ... - the top followed the
irregular rock section (860 x 770) and the cap texels were baked from the light Tripo plate top.
(fit = the flattening of table_base_candidate.py; kept for comparison, it folds the Tripo plate - see the report).
"""

import json
import math
from pathlib import Path

import bpy
import numpy as np
from mathutils import Matrix

LIVE_FILE = Path(globals().get("LIVE_FILE", r"C:/Users/ren/WebstormProjects/unmached/unmached/art/pipeline-candidates/ASSET-TABLE-BASE-001/scripts/table_base_live_mcp.py"))
TBC = LIVE_FILE.parent / "table_base_candidate.py"
SCENE = "TableBase"
STATE_KEY = "table_base_live"


def load_tbc():
    ns_cache = bpy.app.driver_namespace.get(STATE_KEY + "_tbc")
    if ns_cache is not None:
        return ns_cache
    text = TBC.read_text(encoding="utf-8").rstrip()
    if not text.endswith("\nmain()"):
        raise RuntimeError("table_base_candidate.py no longer ends with main()")
    ns = {"__name__": "table_base_candidate_live", "__file__": str(TBC)}
    exec(compile(text[:-len("main()")], str(TBC), "exec"), ns)
    import types
    mod = types.SimpleNamespace(**ns)
    bpy.app.driver_namespace[STATE_KEY + "_tbc"] = mod
    return mod


def state():
    st = bpy.app.driver_namespace.get(STATE_KEY)
    if st is None:
        st = {}
        bpy.app.driver_namespace[STATE_KEY] = st
    return st


def params(path):
    T = load_tbc()
    import sys
    old = sys.argv
    sys.argv = ["blender", "--", str(path)]
    try:
        return T.load_params()
    finally:
        sys.argv = old


def use_scene():
    sc = bpy.data.scenes.get(SCENE)
    if sc is None:
        raise RuntimeError("run STEP='setup' first")
    bpy.context.window.scene = sc
    return sc


def obj_of(P):
    return bpy.data.objects.get(P["asset_name"])


def step_setup(P):
    sc = bpy.data.scenes.get(SCENE)
    if sc is not None:  # idempotent: drop the previous attempt of this scene only
        for o in list(sc.objects):
            data = o.data
            bpy.data.objects.remove(o)
            if data is not None and getattr(data, "users", 1) == 0:
                if isinstance(data, bpy.types.Mesh):
                    bpy.data.meshes.remove(data)
        bpy.data.scenes.remove(sc)
    for cname in [c.name for c in bpy.data.collections if c.name == SCENE or c.name.startswith(SCENE + ".")]:
        col = bpy.data.collections[cname]
        for o in list(col.objects):
            bpy.data.objects.remove(o)
        bpy.data.collections.remove(col)
    # drop what earlier attempts imported from the same GLB (images are looked up by name later)
    T = load_tbc()
    j = T.S.glb_json(P["source_glb"])[0]
    stems = [Path(i.get("name", "")).stem for i in j.get("images", []) if i.get("name")]
    mats = [m.get("name") for m in j.get("materials", []) if m.get("name")]
    for img in list(bpy.data.images):
        if any(img.name.startswith(st_) for st_ in stems) or img.name.startswith(("TB_bake_", "AO_bake")):
            bpy.data.images.remove(img)
    for m in list(bpy.data.materials):
        if any(m.name.startswith(n) for n in mats) or m.name.startswith(("M_TableBase", P["material_name"])):
            bpy.data.materials.remove(m)
    for me_ in list(bpy.data.meshes):
        if me_.users == 0:
            bpy.data.meshes.remove(me_)
    for name in (P["asset_name"], P["asset_name"] + "__src", P["asset_name"] + "_BakeSrc"):
        o = bpy.data.objects.get(name)
        if o is not None:
            bpy.data.objects.remove(o)
    sc = bpy.data.scenes.new(SCENE)
    sc.unit_settings.system = "METRIC"
    sc.unit_settings.scale_length = 1.0
    col = bpy.data.collections.new(SCENE)
    sc.collection.children.link(col)
    bpy.context.window.scene = sc
    bpy.context.view_layer.active_layer_collection = bpy.context.view_layer.layer_collection.children[SCENE]
    st = state()
    st.clear()
    return {"scene": sc.name, "collection": col.name, "scenes_in_file": [s.name for s in bpy.data.scenes]}


def step_import(P):
    T = load_tbc()
    S = T.S
    sc = use_scene()
    bpy.context.view_layer.active_layer_collection = bpy.context.view_layer.layer_collection.children[SCENE]
    before_imgs = {i.name for i in bpy.data.images}
    before_mats = {m.name for m in bpy.data.materials}
    bpy.ops.import_scene.gltf(filepath=str(P["source_glb"]))
    meshes = S.mesh_objects()
    lo, hi = S.world_bounds(meshes)
    rec = {
        "scene": sc.name,
        "mesh_objects": len(meshes), "triangles": sum(S.triangles(o) for o in meshes),
        "materials": sorted({m.name for o in meshes for m in o.data.materials if m}),
        "images": [{"name": i.name, "size": list(i.size), "colorspace": i.colorspace_settings.name}
                   for i in bpy.data.images if i.name not in before_imgs and i.size[0]],
        "bounds_min_m": [S.r(v) for v in lo], "bounds_max_m": [S.r(v) for v in hi],
        "dimensions_m": [S.r(v) for v in (hi - lo)],
        "axis_note": "glTF Y-up read by Blender as Z-up: source X = width (front view), Blender Y = source depth (left view)",
    }
    for o in list(sc.objects):
        if o.type != "MESH":
            bpy.data.objects.remove(o)
    obj = meshes[0]
    if len(meshes) > 1:
        with bpy.context.temp_override(active_object=obj, selected_editable_objects=meshes):
            bpy.ops.object.join()
    obj.parent = None
    obj.data.transform(obj.matrix_world)
    obj.matrix_world = Matrix.Identity(4)
    obj.name = obj.data.name = P["asset_name"]
    st = state()
    st["import"] = rec
    st["gltf_images"] = [i["name"] for i in rec["images"]]
    st["gltf_materials"] = sorted({m.name for m in bpy.data.materials} - before_mats)
    return rec


def step_fit(P):
    T = load_tbc()
    S = T.S
    use_scene()
    obj = obj_of(P)
    st = state()
    geo_before, flipped = S.geometry_stats(obj)
    normals_before = S.corner_normal_stats(obj)
    removed = S.clean_mesh(obj)
    geo_mid, flipped = S.geometry_stats(obj)
    fixed, winding_note = 0, "no inconsistent faces"
    if flipped:
        backup = obj.data.copy()
        fixed = S.fix_winding(obj, flipped)
        geo_try, _ = S.geometry_stats(obj)
        if geo_try["faces_with_inconsistent_winding"] >= geo_mid["faces_with_inconsistent_winding"]:
            old = obj.data
            obj.data = backup
            bpy.data.meshes.remove(old)
            obj.data.name = P["asset_name"]
            winding_note = "%d face(s) flagged; reversing did not reduce the count, kept as delivered" % len(flipped)
            fixed = 0
        else:
            bpy.data.meshes.remove(backup)
            winding_note = "reversed %d face(s)" % fixed
    geo_clean, _ = S.geometry_stats(obj)
    fit = T.fit_and_flatten(obj, P)
    geo_after, flipped_after = S.geometry_stats(obj)
    closed = (geo_after["welded_boundary_edges"] == 0 and geo_after["welded_non_manifold_edges"] == 0
              and geo_after["faces_with_inconsistent_winding"] == 0)
    st["geometry"] = {"before_cleanup": geo_before, "removed": removed, "winding_faces_reversed": fixed,
                      "winding_note": winding_note, "after_cleanup": geo_clean, "after_fit_flatten": geo_after,
                      "flagged_face_centres_uu": [[S.r(c * 100.0, 2) for c in obj.data.polygons[i].center]
                                                  for i in flipped_after[:10]],
                      "corner_normals_before": normals_before, "corner_normals_after": S.corner_normal_stats(obj),
                      "closed_manifold_consistent_after": closed}
    st["fit"] = fit
    top_m = float(P["top_z_uu"]) / 100.0
    lo, hi = S.world_bounds([obj])
    tlo, thi, n_top = T.top_outline(obj, top_m)
    st["tlo"], st["thi"], st["lo"], st["hi"] = list(tlo), list(thi), list(lo), list(hi)
    st["scale_pivot"] = {
        "dimensions_m": [S.r(v) for v in (hi - lo)],
        "bounds_min_m": [S.r(v) for v in lo], "bounds_max_m": [S.r(v) for v in hi],
        "top_plane_z_uu": S.r(top_m * 100.0, 4), "top_plane_vertices": n_top,
        "top_outline_uu_blend": {"min": [S.r(tlo[0] * 100, 3), S.r(tlo[1] * 100, 3)],
                                 "max": [S.r(thi[0] * 100, 3), S.r(thi[1] * 100, 3)],
                                 "size": [S.r((thi[0] - tlo[0]) * 100, 3), S.r((thi[1] - tlo[1]) * 100, 3)]},
        "footprint_target_uu_blend_xy": [float(v) for v in P["footprint_uu_blend_xy"]],
        "depth_below_top_uu": S.r((top_m - lo.z) * 100.0, 3),
        "overhang_beyond_top_outline_uu": [S.r((tlo[0] - lo.x) * 100, 3), S.r((hi.x - thi[0]) * 100, 3),
                                           S.r((tlo[1] - lo.y) * 100, 3), S.r((hi.y - thi[1]) * 100, 3)],
        "pivot": "object origin = board centre (0,0); Z=0 = play plane; tray top at top_z_uu, whole tray below",
        "collision": "none (04 3.6: not interactive; the board keeps its own UBX selection collision)",
    }
    return {"geometry_after": geo_after, "closed": closed, "fit": fit, "scale_pivot": st["scale_pivot"],
            "winding_note": winding_note, "removed": removed}


# ----------------------------------------------------------------------------- cut & cap (plate removal)
def section_points(bm_src, z):
    import bmesh
    bm = bm_src.copy()
    res = bmesh.ops.bisect_plane(bm, geom=bm.verts[:] + bm.edges[:] + bm.faces[:], dist=1e-9,
                                 plane_co=(0.0, 0.0, z), plane_no=(0.0, 0.0, 1.0))
    pts = np.array([v.co[:] for v in res["geom_cut"] if isinstance(v, bmesh.types.BMVert)])
    bm.free()
    return pts


def step_cut(P):
    """Plane cut instead of flattening: the Tripo top is a thin plate (~0.4 % of the source height) that overhangs
    the rock body; flattening folds its underside into the top plane. Here everything above the cut level
    (cut_below_top_frac of the source height below the source top) is removed, the section is capped flat at
    top_z_uu, and XY is fitted to the bounds of the rock section at the cut (not of the plate)."""
    import bmesh
    T = load_tbc()
    S = T.S
    use_scene()
    obj = obj_of(P)
    me = obj.data
    st = state()
    geo_before, _ = S.geometry_stats(obj)
    normals_before = S.corner_normal_stats(obj)
    co = T.vertex_array(me)
    lo0, hi0 = co.min(0), co.max(0)
    d0 = hi0 - lo0
    turn = bool(d0[0] > d0[1])
    R3 = np.array(Matrix.Rotation(math.radians(90.0 if turn else 0.0), 3, "Z"))
    cr = co @ R3.T
    lo, hi = cr.min(0), cr.max(0)
    Hs = hi[2] - lo[2]
    frac = float(P.get("cut_below_top_frac", 0.025))
    z_cut = hi[2] - frac * Hs
    bm = bmesh.new()
    bm.from_mesh(me)
    bmesh.ops.transform(bm, matrix=Matrix(R3.tolist()).to_4x4(), verts=bm.verts)
    sec = section_points(bm, z_cut)
    bm.free()
    flo, fhi = sec.min(0), sec.max(0)
    body = P.get("body")
    depth_src = z_cut - lo[2]
    if body:
        # rock body recessed under the rectangular lip (step 'lip'): the section at the cut fits inside the lip
        # footprint minus body inset; non-uniform XY limited to body max_nonuniformity (the rest stays recessed)
        bx, by = ((float(v) - 2.0 * float(body["inset_uu"])) / 100.0 for v in P["footprint_uu_blend_xy"])
        kx, ky = bx / (fhi[0] - flo[0]), by / (fhi[1] - flo[1])
        cap_nu = 1.0 + float(body.get("max_nonuniformity", 0.05))
        sx, sy = (kx, min(ky, kx * cap_nu)) if kx <= ky else (min(kx, ky * cap_nu), ky)
        tx, ty = sx * (fhi[0] - flo[0]), sy * (fhi[1] - flo[1])
        top_m = float(body["top_z_uu"]) / 100.0
        sz = ((float(P["depth_uu"]) - (float(P["top_z_uu"]) - float(body["top_z_uu"]))) / 100.0) / depth_src
    else:
        tx, ty = (float(v) / 100.0 for v in P["footprint_uu_blend_xy"])
        sx, sy = tx / (fhi[0] - flo[0]), ty / (fhi[1] - flo[1])
        sz = (float(P["depth_uu"]) / 100.0) / depth_src if P.get("depth_uu") else math.sqrt(sx * sy)
        top_m = float(P["top_z_uu"]) / 100.0
    cx, cy = (flo[0] + fhi[0]) / 2, (flo[1] + fhi[1]) / 2
    L = np.diag([sx, sy, sz]) @ R3
    M = (Matrix.Translation((0.0, 0.0, top_m)) @ Matrix.Diagonal((sx, sy, sz, 1.0))
         @ Matrix.Translation((-cx, -cy, -z_cut)) @ Matrix(R3.tolist()).to_4x4())
    cn = T.corner_normals(me) @ np.linalg.inv(L)
    cn /= np.maximum(np.linalg.norm(cn, axis=1, keepdims=True), 1e-12)
    attr = me.attributes.new("um_orig_normal", "FLOAT_VECTOR", "CORNER")
    attr.data.foreach_set("vector", cn.astype(np.float32).ravel())
    me.transform(M)
    me.update()
    # bake source: the fitted, uncut copy (plate included) - provides the plate-top texels for the cap
    src = bpy.data.objects.get(P["asset_name"] + "_BakeSrc")
    if src is not None:
        bpy.data.objects.remove(src)
    src = obj.copy()
    src.data = me.copy()
    src.name = src.data.name = P["asset_name"] + "_BakeSrc"
    if body:  # cap hidden under the lip: no plate bake, no bake source
        bpy.data.meshes.remove(src.data)
        src = None
    else:
        bpy.data.collections[SCENE].objects.link(src)
    for o_ in ((src,) if src is not None else ()):
        v = np.empty(len(o_.data.loops) * 3, dtype=np.float32)
        o_.data.attributes["um_orig_normal"].data.foreach_get("vector", v)
        o_.data.normals_split_custom_set(v.reshape(-1, 3).tolist())
    # cut + cap
    bm = bmesh.new()
    bm.from_mesh(me)
    cap_layer = bm.faces.layers.int.new("um_cap")
    # glTF splits vertices at UV/normal seams; weld them (loop UVs and corner normals are loop data and stay)
    nv0 = len(bm.verts)
    bmesh.ops.remove_doubles(bm, verts=bm.verts[:], dist=1e-6)
    welded = nv0 - len(bm.verts)
    nf0 = len(bm.faces)
    bmesh.ops.bisect_plane(bm, geom=bm.verts[:] + bm.edges[:] + bm.faces[:], dist=1e-9,
                           plane_co=(0.0, 0.0, top_m), plane_no=(0.0, 0.0, 1.0), clear_outer=True)
    boundary = [e for e in bm.edges if e.is_boundary]
    off_plane = [e for e in boundary if any(abs(v.co.z - top_m) > 1e-6 for v in e.verts)]
    nf_cut = len(bm.faces)
    fill = bmesh.ops.triangle_fill(bm, use_beauty=True, use_dissolve=False, edges=boundary, normal=(0.0, 0.0, 1.0))
    cap = [g for g in fill["geom"] if isinstance(g, bmesh.types.BMFace)]
    flipped_cap = 0
    for f in cap:
        f.normal_update()
        if f.normal.z < 0:
            f.normal_flip()
            flipped_cap += 1
    for f in cap:
        f[cap_layer] = 1
    # sliver clean-up on the cap only (zero-area triangles where two section loops touch)
    tiny = [f for f in cap if f.calc_area() < 1e-10]
    bm.to_mesh(me)
    bm.free()
    me.update()
    # corner normals: rock corners from the transformed Tripo normals, cap corners straight up
    vec = np.empty(len(me.loops) * 3, dtype=np.float32)
    me.attributes["um_orig_normal"].data.foreach_get("vector", vec)
    vec = vec.reshape(-1, 3)
    capf = np.empty(len(me.polygons), dtype=np.int32)
    me.attributes["um_cap"].data.foreach_get("value", capf)
    for p in me.polygons:
        if capf[p.index]:
            vec[p.loop_start:p.loop_start + p.loop_total] = (0.0, 0.0, 1.0)
    vec /= np.maximum(np.linalg.norm(vec, axis=1, keepdims=True), 1e-12)
    me.normals_split_custom_set([tuple(v) for v in vec])
    me.attributes.remove(me.attributes["um_orig_normal"])
    me.update()
    co = T.vertex_array(me)
    folded = sum(1 for p in me.polygons if all(abs(co[i, 2] - top_m) < 1e-7 for i in p.vertices)
                 and p.normal.z < -0.99)
    up = sum(1 for p in me.polygons if capf[p.index] and p.normal.z > 0.99)
    fit = {
        "method": ("plane cut + flat cap of the rock body at body.top_z_uu (plate removed), recessed under the "
                   "rectangular lip of step 'lip'") if body else "plane cut + flat cap (plate removed), not flattening",
        "body": ({"top_z_uu": float(body["top_z_uu"]), "inset_uu": float(body["inset_uu"]),
                  "max_nonuniformity": float(body.get("max_nonuniformity", 0.05)),
                  "section_size_uu_blend": [S.r(tx * 100.0, 3), S.r(ty * 100.0, 3)],
                  "fits_inside_uu_blend": [S.r(bx * 100.0, 3), S.r(by * 100.0, 3)]} if body else None),
        "why": "Tripo top = thin plate over the rock body (plate underside 0.26-0.38 % of the source height below "
               "the top, overhang up to ~170 uu); flattening folded 410 plate-underside faces into the top plane",
        "source_dimensions_m": [S.r(v) for v in d0],
        "turned_90deg_about_z": turn,
        "turn_reason": "source long axis was X; long side must be .blend Y (= UE X)" if turn else "source long axis already Y",
        "cut_below_top_frac": frac, "cut_z_prescale_m": S.r(z_cut), "source_top_z_prescale_m": S.r(hi[2]),
        "footprint_source": "bounds of the rock section at the cut level",
        "footprint_prescale_m": [S.r(fhi[0] - flo[0]), S.r(fhi[1] - flo[1])],
        "footprint_aspect_y_over_x_source": S.r((fhi[1] - flo[1]) / (fhi[0] - flo[0]), 4),
        "footprint_aspect_y_over_x_target": S.r(ty / tx, 4),
        "scale_xyz": [S.r(sx), S.r(sy), S.r(sz)],
        "xy_nonuniformity_pct": S.r(abs(sx / sy - 1.0) * 100.0, 3),
        "z_scale_rule": ("depth_uu %s" % P["depth_uu"]) if P.get("depth_uu") else "source proportions: sqrt(sx*sy)",
        "source_depth_below_cut_m": S.r(depth_src),
        "cut": {"welded_seam_vertices": welded, "faces_before": nf0, "faces_after_cut": nf_cut, "boundary_edges_at_cut": len(boundary),
                "boundary_edges_off_plane": len(off_plane), "cap_faces": len(cap), "cap_faces_flipped_up": flipped_cap,
                "cap_faces_area_lt_1e-10": len(tiny)},
        "flatten": {"vertices_moved": 0, "faces_in_top_plane_facing_up": up,
                    "faces_in_top_plane_facing_down_folded": folded},
    }
    geo_after, flipped_after = S.geometry_stats(obj)
    closed = (geo_after["welded_boundary_edges"] == 0 and geo_after["welded_non_manifold_edges"] == 0
              and geo_after["faces_with_inconsistent_winding"] == 0)
    st["geometry"] = {"before_cleanup": geo_before, "removed": {"note": "no clean-up deletion (it opened a 3-edge "
                                                                "hole at a degenerate face); faces above the cut removed"},
                      "winding_faces_reversed": 0, "winding_note": "cap faces oriented +Z",
                      "after_cleanup": geo_before, "after_fit_flatten": geo_after,
                      "flagged_face_centres_uu": [[S.r(c * 100.0, 2) for c in me.polygons[i].center]
                                                  for i in flipped_after[:10]],
                      "corner_normals_before": normals_before, "corner_normals_after": S.corner_normal_stats(obj),
                      "closed_manifold_consistent_after": closed}
    st["fit"] = fit
    lo, hi = S.world_bounds([obj])
    tlo, thi, n_top = T.top_outline(obj, top_m)
    st["tlo"], st["thi"], st["lo"], st["hi"] = list(tlo), list(thi), list(lo), list(hi)
    st["scale_pivot"] = {
        "dimensions_m": [S.r(v) for v in (hi - lo)],
        "bounds_min_m": [S.r(v) for v in lo], "bounds_max_m": [S.r(v) for v in hi],
        "top_plane_z_uu": S.r(top_m * 100.0, 4), "top_plane_vertices": n_top,
        "top_outline_uu_blend": {"min": [S.r(tlo[0] * 100, 3), S.r(tlo[1] * 100, 3)],
                                 "max": [S.r(thi[0] * 100, 3), S.r(thi[1] * 100, 3)],
                                 "size": [S.r((thi[0] - tlo[0]) * 100, 3), S.r((thi[1] - tlo[1]) * 100, 3)]},
        "footprint_target_uu_blend_xy": [float(v) for v in P["footprint_uu_blend_xy"]],
        "depth_below_top_uu": S.r((top_m - lo.z) * 100.0, 3),
        "overhang_beyond_top_outline_uu": [S.r((tlo[0] - lo.x) * 100, 3), S.r((hi.x - thi[0]) * 100, 3),
                                           S.r((tlo[1] - lo.y) * 100, 3), S.r((hi.y - thi[1]) * 100, 3)],
        "pivot": "object origin = board centre (0,0); Z=0 = play plane; tray top at top_z_uu, whole tray below",
        "collision": "none (04 3.6: not interactive; the board keeps its own UBX selection collision)",
    }
    return {"fit": fit, "geometry_after": geo_after, "closed": closed, "scale_pivot": st["scale_pivot"]}


def max_empty_rect(free):
    """Largest axis-aligned all-True rectangle in a boolean grid (histogram stack). Returns (area, y0, x0, h, w)."""
    h, w = free.shape
    heights = np.zeros(w, dtype=np.int32)
    best = (0, 0, 0, 0, 0)
    for y in range(h):
        heights = np.where(free[y], heights + 1, 0)
        stack = []
        for x in range(w + 1):
            cur = heights[x] if x < w else 0
            start = x
            while stack and stack[-1][1] >= cur:
                sx_, sh = stack.pop()
                area = sh * (x - sx_)
                if area > best[0]:
                    best = (int(area), y - sh + 1, sx_, int(sh), x - sx_)
                start = sx_
            stack.append((start, cur))
    return best


def step_capuv(P):
    """Cap UV: planar projection placed in the largest free rectangle of the existing atlas (the removed plate
    freed ~0.34 of UV space); rock UVs are not touched, so rock texels are not resampled."""
    T = load_tbc()
    S = T.S
    use_scene()
    obj = obj_of(P)
    me = obj.data
    st = state()
    grid = 512
    margin_px = 4  # at 512 -> 16 texels at 2K
    uvl = me.uv_layers[0].data
    capf = np.empty(len(me.polygons), dtype=np.int32)
    me.attributes["um_cap"].data.foreach_get("value", capf)
    me.calc_loop_triangles()
    rock_tris = np.array([[uvl[i].uv[:] for i in t.loops] for t in me.loop_triangles if not capf[t.polygon_index]])
    occ = S.raster_triangles(rock_tris, grid) > 0
    occ_d = occ.copy()
    for _ in range(margin_px):
        occ_d = occ_d | np.roll(occ_d, 1, 0) | np.roll(occ_d, -1, 0) | np.roll(occ_d, 1, 1) | np.roll(occ_d, -1, 1)
    free = ~occ_d
    free[:margin_px, :] = free[-margin_px:, :] = False
    free[:, :margin_px] = free[:, -margin_px:] = False
    area, y0, x0, hh, ww = max_empty_rect(free)
    cap_polys = [p for p in me.polygons if capf[p.index]]
    xy = np.array([me.vertices[i].co[:2] for p in cap_polys for i in p.vertices])
    clo, chi = xy.min(0), xy.max(0)
    ext = chi - clo
    # fit (optionally rotated 90 deg) into the rectangle, uniform scale
    s_n = min(ww / grid / ext[0], hh / grid / ext[1])
    s_r = min(ww / grid / ext[1], hh / grid / ext[0])
    rot = s_r > s_n
    s = max(s_n, s_r)
    u0, v0 = x0 / grid, y0 / grid
    for p in cap_polys:
        for li in p.loop_indices:
            x, y = me.vertices[me.loops[li].vertex_index].co[:2]
            if rot:
                u, v = u0 + (y - clo[1]) * s, v0 + (chi[0] - x) * s
            else:
                u, v = u0 + (x - clo[0]) * s, v0 + (y - clo[1]) * s
            uvl[li].uv = (u, v)
    rock_area_uv = float(np.sum([abs(np.cross(t[1] - t[0], t[2] - t[0])) / 2 for t in rock_tris]))
    rock_area_3d = sum(p.area for p in me.polygons if not capf[p.index])
    rock_density = math.sqrt(rock_area_uv * 2048 ** 2 / (rock_area_3d * 1e4))  # px per uu
    cap_density = s * 2048 / 100.0
    rec = {"atlas_grid": grid, "margin_texels_at_2k": margin_px * 2048 // grid,
           "free_rect_uv": [S.r(u0, 4), S.r(v0, 4), S.r(ww / grid, 4), S.r(hh / grid, 4)],
           "free_rect_fraction": S.r(area / grid / grid, 4), "rotated_90": rot,
           "cap_extent_uu": [S.r(ext[0] * 100, 2), S.r(ext[1] * 100, 2)],
           "texel_density_px_per_uu": {"cap": S.r(cap_density, 3), "rock_mean": S.r(rock_density, 3)},
           "rock_uv_unchanged": True}
    st["cap_uv"] = rec
    return rec


def step_capbake(P):
    """Bake the cap island from the plate top of the uncut copy (Cycles, selected to active) and write it into the
    glTF source images only inside the cap island (+ margin); every rock texel stays as delivered."""
    T = load_tbc()
    S = T.S
    sc = use_scene()
    obj = obj_of(P)
    src = bpy.data.objects[P["asset_name"] + "_BakeSrc"]
    src.hide_set(False)
    src.hide_render = False
    me = obj.data
    st = state()
    glb = S.glb_json(P["source_glb"])
    names = S.gltf_images(glb)
    bc_img, mr_img, n_img = (S.find_image(names[k]) for k in ("basecolor", "metallic_roughness", "normal"))
    size = bc_img.size[0]
    gl_mat = src.data.materials[0]
    # target gets its own material copy with the bake node; source switches between emission and the glTF material
    tgt_mat = gl_mat.copy()
    tgt_mat.name = "M_TableBase_bake_tmp"
    me.materials[0] = tgt_mat
    emit = bpy.data.materials.new("M_TableBase_emit_tmp")
    emit.use_nodes = True
    nt = emit.node_tree
    for n in list(nt.nodes):
        nt.nodes.remove(n)
    out_n = nt.nodes.new("ShaderNodeOutputMaterial")
    em = nt.nodes.new("ShaderNodeEmission")
    tex = nt.nodes.new("ShaderNodeTexImage")
    nt.links.new(tex.outputs["Color"], em.inputs["Color"])
    nt.links.new(em.outputs["Emission"], out_n.inputs["Surface"])
    sc.render.engine = "CYCLES"
    sc.cycles.device = "CPU"
    sc.cycles.samples = 4
    bk = sc.render.bake
    bk.use_selected_to_active = True
    bk.cage_extrusion = float(P.get("cap_bake_extrusion_m", 0.035))
    bk.max_ray_distance = 0.08
    bk.margin = 8
    bk.margin_type = "EXTEND"
    tnode = tgt_mat.node_tree.nodes.new("ShaderNodeTexImage")
    tgt_mat.node_tree.nodes.active = tnode
    for o in sc.objects:
        o.select_set(False)
    src.select_set(True)
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj
    results = {}

    def bake(kind, image_src=None):
        img = bpy.data.images.new("TB_bake_" + kind, size, size, alpha=False, float_buffer=True)
        img.colorspace_settings.name = "Non-Color"
        tnode.image = img
        if kind == "normal":
            src.data.materials[0] = gl_mat
            bk.normal_space = "TANGENT"
            bk.normal_r, bk.normal_g, bk.normal_b = "POS_X", "POS_Y", "POS_Z"
            bpy.ops.object.bake(type="NORMAL", use_selected_to_active=True, cage_extrusion=bk.cage_extrusion,
                                max_ray_distance=bk.max_ray_distance, margin=8, use_clear=True)
        else:
            tex.image = image_src
            src.data.materials[0] = emit
            bpy.ops.object.bake(type="EMIT", use_selected_to_active=True, cage_extrusion=bk.cage_extrusion,
                                max_ray_distance=bk.max_ray_distance, margin=8, use_clear=True)
        arr = S.image_array(img)[..., :3].copy()
        bpy.data.images.remove(img)
        return arr

    results["bc_lin"] = bake("bc", bc_img)
    results["rm"] = bake("rm", mr_img)
    results["normal"] = bake("normal")
    src.data.materials[0] = gl_mat
    bk.use_selected_to_active = False  # scene setting; the AO bake later bakes the tray alone
    # cap mask at full size, grown by the bake margin
    uvl = me.uv_layers[0].data
    capf = np.empty(len(me.polygons), dtype=np.int32)
    me.attributes["um_cap"].data.foreach_get("value", capf)
    me.calc_loop_triangles()
    cap_tris = np.array([[uvl[i].uv[:] for i in t.loops] for t in me.loop_triangles if capf[t.polygon_index]])
    mask = S.raster_triangles(cap_tris, size) > 0
    cover = mask.sum()
    for _ in range(6):
        mask = mask | np.roll(mask, 1, 0) | np.roll(mask, -1, 0) | np.roll(mask, 1, 1) | np.roll(mask, -1, 1)
    # write into the in-memory glTF images (the GLB file is not touched)
    def write(img, rgb):
        a = S.image_array(img).copy()
        a[mask, :3] = rgb[mask]
        img.pixels.foreach_set(a.ravel())
        img.update()
    write(bc_img, S.lin_to_srgb(results["bc_lin"]))
    write(mr_img, results["rm"])
    write(n_img, results["normal"])
    # quality numbers of the baked cap region
    nb = results["normal"][mask] * 2 - 1
    rec = {"method": "Cycles selected-to-active from the uncut fitted copy (plate top above the cap)",
           "cage_extrusion_m": bk.cage_extrusion, "max_ray_distance_m": bk.max_ray_distance, "samples": 4,
           "passes": {"BC": "EMIT of the glTF base colour (linear) -> sRGB", "RM": "EMIT of the glTF metallicRoughness",
                      "N": "NORMAL tangent OpenGL (flipped to DirectX later with the rest)"},
           "cap_texels": int(cover), "written_texels_with_margin": int(mask.sum()),
           "bc_mean_srgb": [S.r(v, 3) for v in S.lin_to_srgb(results["bc_lin"][mask]).mean(0)],
           "bc_black_texels_lt_0.02": int((results["bc_lin"][mask].max(1) < 0.0004).sum()),
           "normal_mean": [S.r(v, 3) for v in nb.mean(0)],
           "rock_texels_changed": 0}
    # restore: target back to the glTF material (build_textures replaces it), drop temporaries and the source
    me.materials[0] = gl_mat
    bpy.data.materials.remove(tgt_mat)
    bpy.data.materials.remove(emit)
    sdata = src.data
    bpy.data.objects.remove(src)
    bpy.data.meshes.remove(sdata)
    st["cap_bake"] = rec
    return rec


# ----------------------------------------------------------------------------- rectangular lip (2026-09-30 fix)
LIP_SIDES = (  # corner i -> i+1 (CCW from above); outward normal n, along-side axis a (a, n, +Z right-handed UV)
    ("+Y", (0.0, 1.0), (1.0, 0.0)), ("-X", (-1.0, 0.0), (0.0, 1.0)),
    ("-Y", (0.0, -1.0), (-1.0, 0.0)), ("+X", (1.0, 0.0), (0.0, -1.0)))
LIP_CORNERS = ((1, 1), (-1, 1), (-1, -1), (1, -1))


def lip_profile(P):
    """Closed profile (inset from the outer edge, z) in metres: P0 inner-bottom, P1 inner-top, P2 bevel start,
    P3 bevel end, P4 outer-bottom. Unfolded arc length v starts at P1 (top ring first, then bevel, outer side,
    bottom ring, inner side)."""
    L = P["lip"]
    th, b, w = (float(L[k]) / 100.0 for k in ("thickness_uu", "bevel_uu", "ring_width_uu"))
    zt = float(P["top_z_uu"]) / 100.0
    zb = zt - th
    prof = [(w, zb), (w, zt), (b, zt), (0.0, zt - b), (0.0, zb)]
    seg = {1: w - b, 2: b * math.sqrt(2.0), 3: th - b, 4: w, 0: th}  # segment k: P_k -> P_(k+1)
    v_at = {1: 0.0}
    v_at[2] = seg[1]
    v_at[3] = v_at[2] + seg[2]
    v_at[4] = v_at[3] + seg[3]
    v_at[0] = v_at[4] + seg[4]
    total = v_at[0] + seg[0]
    return prof, v_at, total, (th, b, w, zt, zb)


def step_lip(P):
    """Straight, slightly bevelled rectangular rock lip at the footprint (UE 756 x 656): a closed ring solid
    (outer = footprint, inner opening ring_width_uu in from it, under the board frame), top at top_z_uu, joined into
    the tray. UV: one unfolded strip per side (top -> bevel -> outer side -> bottom -> inner side, uniform texel
    density, right-handed like the faces) packed into the largest atlas rectangle not used by rock islands (the one
    freed by the Tripo plate); the rock-body cap (hidden under the board) gets a small island beside the short
    strips. Rock UVs are not touched."""
    import bmesh
    T = load_tbc()
    S = T.S
    use_scene()
    obj = obj_of(P)
    me = obj.data
    st = state()
    size = int(P["texture_size"])
    hx, hy = (float(v) / 200.0 for v in P["footprint_uu_blend_xy"])
    prof, v_at, vtot, (th, b, w, zt, zb) = lip_profile(P)
    # --- free atlas area (rock islands only), 512 grid, 16 texel margin at 2K
    grid, margin_px = 512, 4
    uvl = me.uv_layers[0].data
    capf = np.empty(len(me.polygons), dtype=np.int32)
    me.attributes["um_cap"].data.foreach_get("value", capf)
    me.calc_loop_triangles()
    rock_tris = np.array([[uvl[i].uv[:] for i in t.loops] for t in me.loop_triangles if not capf[t.polygon_index]])
    occ = S.raster_triangles(rock_tris, grid) > 0
    for _ in range(margin_px):
        occ = occ | np.roll(occ, 1, 0) | np.roll(occ, -1, 0) | np.roll(occ, 1, 1) | np.roll(occ, -1, 1)
    free = ~occ
    free[:margin_px, :] = free[-margin_px:, :] = False
    free[:, :margin_px] = free[:, -margin_px:] = False
    area, gy0, gx0, gh, gw = max_empty_rect(free)
    k = size // grid
    X0, Y0, W, H = gx0 * k, gy0 * k, gw * k, gh * k  # px at texture size, row 0 = bottom (v up)
    gap = 16
    len_x, len_y = 2 * hx * 100.0, 2 * hy * 100.0  # strip lengths (uu): +-Y sides run along x, +-X sides along y
    Lmax, Lmin = max(len_x, len_y), min(len_x, len_y)
    vt_uu = vtot * 100.0
    d = min(W / Lmax, (H - 3 * gap) / (4 * vt_uu))
    cap_room_min = 64
    if W - Lmin * d - gap < cap_room_min:
        d = min(d, (W - gap - cap_room_min) / Lmin)
    strip_h = vt_uu * d
    lens = {"+Y": len_x, "-Y": len_x, "+X": len_y, "-X": len_y}
    order = sorted([n for n, _, _ in LIP_SIDES], key=lambda n: -lens[n])  # long strips at the bottom
    place = {}
    y = Y0
    for n in order:
        place[n] = {"x0": float(X0), "y0": float(y), "len_uu": lens[n], "w_px": lens[n] * d, "h_px": strip_h}
        y += strip_h + gap
    short = [n for n in order if lens[n] == Lmin]
    cap_box = {"x0": X0 + Lmin * d + gap, "y0": place[short[0]]["y0"],
               "w_px": W - Lmin * d - gap, "h_px": 2 * strip_h + gap}
    # --- lip mesh
    lip_me = bpy.data.meshes.new(P["asset_name"] + "_Lip")
    bm = bmesh.new()
    ring = [[bm.verts.new((cx_ * (hx - t), cy_ * (hy - t), z)) for (cx_, cy_) in LIP_CORNERS] for t, z in prof]
    vring = {v: kk for kk in range(5) for v in ring[kk]}
    uv_layer = bm.loops.layers.uv.new(me.uv_layers[0].name)
    cap_layer = bm.faces.layers.int.new("um_cap")
    side_of = {}
    for kseg in range(5):
        k2 = (kseg + 1) % 5
        for i in range(4):
            i2 = (i + 1) % 4
            f = bm.faces.new((ring[kseg][i], ring[kseg][i2], ring[k2][i2], ring[k2][i]))
            f[cap_layer] = 2
            side_of[f] = (i, kseg)
    bm.normal_update()
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
    bm.normal_update()
    top_up = all(f.normal.z > 0.99 for f, (i, kseg) in side_of.items() if kseg == 1)
    for f, (i, kseg) in side_of.items():
        name, nrm, ax = LIP_SIDES[i]
        half = hx if name in ("+Y", "-Y") else hy
        pl = place[name]
        for loop in f.loops:
            co = loop.vert.co
            u_uu = (co.x * ax[0] + co.y * ax[1] + half) * 100.0
            kv = vring[loop.vert]
            v_m = vtot if (kseg == 0 and kv == 1) else v_at[kv]  # the inner side closes the strip at P1
            loop[uv_layer].uv = ((pl["x0"] + u_uu * d) / size, (pl["y0"] + v_m * 100.0 * d) / size)
    bm.to_mesh(lip_me)
    bm.free()
    lip_me.materials.append(me.materials[0])
    lip_me.update()
    cn = [None] * len(lip_me.loops)
    for p in lip_me.polygons:  # flat corner normals: every lip edge is hard (the bevel is one flat chamfer)
        for li in p.loop_indices:
            cn[li] = tuple(p.normal)
    lip_me.normals_split_custom_set(cn)
    n_lip_faces = len(lip_me.polygons)
    # rock-body cap: small planar island in cap_box (hidden under the board; texels filled in liptex)
    cap_polys = [p for p in me.polygons if capf[p.index] == 1]
    xy = np.array([me.vertices[i].co[:2] for p in cap_polys for i in p.vertices])
    clo, chi = xy.min(0), xy.max(0)
    ext = (chi - clo) * 100.0
    m8 = 8
    dc = min((cap_box["w_px"] - 2 * m8) / ext[0], (cap_box["h_px"] - 2 * m8) / ext[1])
    for p in cap_polys:
        for li in p.loop_indices:
            x, y_ = me.vertices[me.loops[li].vertex_index].co[:2]
            uvl[li].uv = ((cap_box["x0"] + m8 + (x - clo[0]) * 100.0 * dc) / size,
                          (cap_box["y0"] + m8 + (y_ - clo[1]) * 100.0 * dc) / size)
    # join (same UV layer name, same material, um_cap attribute on both)
    lip = bpy.data.objects.new(P["asset_name"] + "_Lip", lip_me)
    bpy.data.collections[SCENE].objects.link(lip)
    nl_rock = len(me.loops)
    rock_cn = T.corner_normals(me)
    with bpy.context.temp_override(active_object=obj, selected_editable_objects=[obj, lip]):
        bpy.ops.object.join()
    me = obj.data
    me.name = P["asset_name"]
    orphan = bpy.data.meshes.get(P["asset_name"] + "_Lip")
    if orphan is not None and orphan.users == 0:  # else it keeps the glTF material (+ packed images) alive
        bpy.data.meshes.remove(orphan)
    allcn = T.corner_normals(me)
    drift = float(np.abs(allcn[:nl_rock] - rock_cn).max())
    lip_flat = allcn[nl_rock:]
    if drift > 1e-4:  # join lost the rock custom normals -> set both again
        me.normals_split_custom_set([tuple(v) for v in np.vstack([rock_cn, lip_flat])])
        drift = float(np.abs(T.corner_normals(me)[:nl_rock] - rock_cn).max())
    top_m = zt
    co = T.vertex_array(me)
    capf = np.empty(len(me.polygons), dtype=np.int32)
    me.attributes["um_cap"].data.foreach_get("value", capf)
    in_top = [p for p in me.polygons if all(abs(co[i, 2] - top_m) < 1e-7 for i in p.vertices)]
    folded = sum(1 for p in in_top if p.normal.z < -0.99)
    up = sum(1 for p in in_top if p.normal.z > 0.99)
    above = int((co[:, 2] > top_m + 1e-7).sum())
    geo_after, flipped_after = S.geometry_stats(obj)
    closed = (geo_after["welded_boundary_edges"] == 0 and geo_after["welded_non_manifold_edges"] == 0
              and geo_after["faces_with_inconsistent_winding"] == 0)
    lo, hi = S.world_bounds([obj])
    tlo, thi, n_top = T.top_outline(obj, top_m)
    st["tlo"], st["thi"], st["lo"], st["hi"] = list(tlo), list(thi), list(lo), list(hi)
    rec = {
        "method": "rectangular ring solid: 5-point profile swept along the footprint rectangle (mitred corners), "
                  "flat faces, joined into the tray as its own closed shell over the recessed rock body",
        "footprint_uu_blend": [S.r(2 * hx * 100, 3), S.r(2 * hy * 100, 3)],
        "thickness_uu": S.r(th * 100, 3), "bevel_uu": S.r(b * 100, 3), "ring_width_uu": S.r(w * 100, 3),
        "inner_opening_uu_blend": [S.r(2 * (hx - w) * 100, 3), S.r(2 * (hy - w) * 100, 3)],
        "top_z_uu": S.r(zt * 100, 3), "bottom_z_uu": S.r(zb * 100, 3), "faces": n_lip_faces,
        "top_faces_up": top_up,
        "uv": {"free_rect_px": [X0, Y0, W, H], "free_rect_fraction": S.r(area / grid / grid, 4),
               "texel_density_px_per_uu": S.r(d, 4), "strip_height_px": S.r(strip_h, 2), "gap_px": gap,
               "strips": {n: {kk: S.r(vv, 2) for kk, vv in place[n].items()} for n in order},
               "unfold_v_m": {"P1_top_inner": 0.0, "P2_bevel": S.r(v_at[2], 4), "P3_outer_side": S.r(v_at[3], 4),
                              "P4_outer_bottom": S.r(v_at[4], 4), "P0_inner_bottom": S.r(v_at[0], 4),
                              "end": S.r(vtot, 4)},
               "rock_cap_island": {"box_px": [S.r(v, 2) for v in (cap_box["x0"], cap_box["y0"], cap_box["w_px"],
                                                                 cap_box["h_px"])],
                                   "texel_density_px_per_uu": S.r(dc, 4), "extent_uu": [S.r(v, 2) for v in ext]},
               "rock_uv_unchanged": True},
        "rock_custom_normals_max_drift_after_join": S.r(drift, 6),
        "vertices_above_top_plane": above,
        "top_plane_faces_up": up, "top_plane_faces_down_folded": folded,
    }
    st["lip"] = rec
    st["lip_place"] = {"d": d, "place": place, "cap_box": cap_box, "dc": dc, "vtot": vtot}
    st["fit"]["flatten"] = {"vertices_moved": 0, "faces_in_top_plane_facing_up": up,
                            "faces_in_top_plane_facing_down_folded": folded,
                            "note": "top plane = lip top (Z top_z_uu); the rock-body cap lies below it"}
    st["geometry"]["after_fit_flatten"] = geo_after
    st["geometry"]["closed_manifold_consistent_after"] = closed
    st["geometry"]["flagged_face_centres_uu"] = [[S.r(c * 100.0, 2) for c in me.polygons[i].center]
                                                 for i in flipped_after[:10]]
    st["geometry"]["corner_normals_after"] = S.corner_normal_stats(obj)
    st["scale_pivot"] = {
        "dimensions_m": [S.r(v) for v in (hi - lo)],
        "bounds_min_m": [S.r(v) for v in lo], "bounds_max_m": [S.r(v) for v in hi],
        "top_plane_z_uu": S.r(top_m * 100.0, 4), "top_plane_vertices": n_top,
        "top_outline_uu_blend": {"min": [S.r(tlo[0] * 100, 3), S.r(tlo[1] * 100, 3)],
                                 "max": [S.r(thi[0] * 100, 3), S.r(thi[1] * 100, 3)],
                                 "size": [S.r((thi[0] - tlo[0]) * 100, 3), S.r((thi[1] - tlo[1]) * 100, 3)],
                                 "note": "flat top = footprint minus the bevel on each side"},
        "footprint_target_uu_blend_xy": [float(v) for v in P["footprint_uu_blend_xy"]],
        "depth_below_top_uu": S.r((top_m - lo.z) * 100.0, 3),
        "overhang_beyond_footprint_uu": [S.r((-hx - lo.x) * 100, 3), S.r((hi.x - hx) * 100, 3),
                                         S.r((-hy - lo.y) * 100, 3), S.r((hi.y - hy) * 100, 3)],
        "pivot": "object origin = board centre (0,0); Z=0 = play plane; tray top at top_z_uu, whole tray below",
        "collision": "none (04 3.6: not interactive; the board keeps its own UBX selection collision)",
    }
    return {"lip": rec, "geometry_after": geo_after, "closed": closed, "scale_pivot": st["scale_pivot"]}


def bombing_fill(src_list, valid_tl, win, rng, qx, qy, means):
    """Texture bombing with Hann windows (partition of unity, stride = win/2) and variance-preserving blending
    (out = mean + sum w (x - mean) / sqrt(sum w^2)). qx, qy: source-texel coordinates (column, row) of the target
    texels. src_list: source arrays (H, W, C) sampled bilinearly; valid_tl: (N, 2) top-left (row, col) of windows
    that lie fully inside usable rock texels. Returns one array per source (qx.shape + (C,))."""
    stride = win / 2.0
    acc = [np.zeros(qx.shape + (a.shape[2],), dtype=np.float64) for a in src_list]
    wsum2 = np.zeros(qx.shape, dtype=np.float64)
    i0, i1 = int(math.floor(qx.min() / stride)) - 1, int(math.ceil(qx.max() / stride)) + 1
    j0, j1 = int(math.floor(qy.min() / stride)) - 1, int(math.ceil(qy.max() / stride)) + 1
    for j in range(j0, j1 + 1):
        for i in range(i0, i1 + 1):
            dx, dy = qx - i * stride, qy - j * stride
            m = (np.abs(dx) < stride) & (np.abs(dy) < stride)
            if not m.any():
                continue
            wgt = (np.cos(math.pi * dx[m] / win) ** 2) * (np.cos(math.pi * dy[m] / win) ** 2)
            r0, c0 = valid_tl[rng.integers(len(valid_tl))]
            sr, sc_ = r0 + win / 2.0 + dy[m] - 0.5, c0 + win / 2.0 + dx[m] - 0.5
            rf, cf = np.floor(sr).astype(int), np.floor(sc_).astype(int)
            fr, fc = (sr - rf)[:, None], (sc_ - cf)[:, None]
            for kk, arr_ in enumerate(src_list):
                v = (arr_[rf, cf] * (1 - fr) * (1 - fc) + arr_[rf, cf + 1] * (1 - fr) * fc
                     + arr_[rf + 1, cf] * fr * (1 - fc) + arr_[rf + 1, cf + 1] * fr * fc)
                acc[kk][m] += wgt[:, None] * (v - means[kk])
            wsum2[m] += wgt ** 2
    norm = 1.0 / np.sqrt(np.maximum(wsum2, 1e-12))
    return [means[kk] + acc[kk] * norm[..., None] for kk in range(len(acc))]


def box_blur(a, rad, passes=2):
    """Separable box blur (edge-clamped) of an (H, W, C) array; passes=2 ~ Gaussian sigma ~ rad * 0.8."""
    out = a
    for _ in range(passes):
        for ax in (0, 1):
            pad = [(0, 0)] * out.ndim
            pad[ax] = (rad + 1, rad)
            c = np.cumsum(np.pad(out, pad, mode="edge"), axis=ax)
            hi_ = np.take(c, np.arange(2 * rad + 1, c.shape[ax]), axis=ax)
            lo_ = np.take(c, np.arange(0, c.shape[ax] - 2 * rad - 1), axis=ax)
            out = (hi_ - lo_) / (2 * rad + 1)
    return out


def step_liptex(P):
    """Lip + rock-cap texels from the painted-rock texels of the Tripo skirt itself (no new source): texture bombing
    of rock windows at the rock texel density (no mirroring, variance kept), written into the in-memory glTF images
    only inside the lip strip rectangles (+8 px margin) and the cap box; rock texels stay as delivered. Normal
    texels are copied in the strip's own UV frame (strip UV = unfolded lip, same orientation as the source window),
    so tangent-space values stay valid. BC of the lip is multiplied by lip.bc_value_scale (linear)."""
    T = load_tbc()
    S = T.S
    use_scene()
    obj = obj_of(P)
    me = obj.data
    st = state()
    L = P["lip"]
    glb = S.glb_json(P["source_glb"])
    names = S.gltf_images(glb)
    bc_img, mr_img, n_img = (S.find_image(names[k]) for k in ("basecolor", "metallic_roughness", "normal"))
    size = bc_img.size[0]
    lp = st["lip_place"]
    d, place, cap_box, dc = lp["d"], lp["place"], lp["cap_box"], lp["dc"]
    srgb = bc_img.colorspace_settings.name == "sRGB"
    bc = S.image_array(bc_img)[..., :3].astype(np.float64)
    bc_lin = S.srgb_to_lin(bc) if srgb else bc
    rm = S.image_array(mr_img)[..., :3].astype(np.float64)
    nrm = S.image_array(n_img)[..., :3].astype(np.float64) * 2 - 1
    uvl = me.uv_layers[0].data
    capf = np.empty(len(me.polygons), dtype=np.int32)
    me.attributes["um_cap"].data.foreach_get("value", capf)
    me.calc_loop_triangles()
    rock_tris = np.array([[uvl[i].uv[:] for i in t.loops] for t in me.loop_triangles if capf[t.polygon_index] == 0])
    cov = S.raster_triangles(rock_tris, size) > 0
    erode = int(L.get("source_erode_px", 6))
    ok = cov.copy()
    for _ in range(erode):
        ok = ok & np.roll(ok, 1, 0) & np.roll(ok, -1, 0) & np.roll(ok, 1, 1) & np.roll(ok, -1, 1)
    nl = np.linalg.norm(nrm, axis=2)
    ok &= (nrm[..., 2] > 0.3) & (nl > 0.7) & (nl < 1.3)
    win = int(L.get("bomb_window_px", 160))
    ii = np.pad(np.cumsum(np.cumsum((~ok).astype(np.int64), 0), 1), ((1, 0), (1, 0)))
    n_ = win + 2  # window + 1 texel for the bilinear neighbour
    bad = ii[n_:, n_:] - ii[:-n_, n_:] - ii[n_:, :-n_] + ii[:-n_, :-n_]
    valid_tl = np.argwhere(bad == 0)
    if len(valid_tl) < 50:
        raise RuntimeError("too few rock windows of %d px: %d" % (win, len(valid_tl)))
    means = [bc_lin[ok].mean(0), rm[ok].mean(0), np.array([0.0, 0.0, 1.0])]
    src_list = [bc_lin, rm, nrm]
    sd = float(L.get("source_px_per_uu", 1.337))  # rock mean texel density of the Tripo atlas at 2K
    rng = np.random.default_rng(int(L.get("seed", 20260930)))
    scale = float(L.get("bc_value_scale", 1.0))
    out_bc = S.image_array(bc_img).copy()
    out_rm = S.image_array(mr_img).copy()
    out_n = S.image_array(n_img).copy()
    written = 0
    stats = {}
    m8 = 8
    regions = [(n, pl["x0"], pl["y0"], pl["w_px"], pl["h_px"], d, scale, m8) for n, pl in place.items()]
    regions.append(("rock_cap", cap_box["x0"], cap_box["y0"], cap_box["w_px"], cap_box["h_px"], dc, 1.0, 0))
    for name, x0, y0, wpx, hpx, dens, vs, mg in regions:
        c0, c1 = max(int(math.floor(x0)) - mg, 0), min(int(math.ceil(x0 + wpx)) + mg, size)
        r0, r1 = max(int(math.floor(y0)) - mg, 0), min(int(math.ceil(y0 + hpx)) + mg, size)
        cols, rows = np.meshgrid(np.arange(c0, c1) + 0.5, np.arange(r0, r1) + 0.5)
        qx = (cols - x0) / dens * sd + rng.uniform(0, 4096)
        qy = (rows - y0) / dens * sd + rng.uniform(0, 4096)
        f_bc, f_rm, f_n = bombing_fill(src_list, valid_tl, win, rng, qx, qy, means)
        if name != "rock_cap" and L.get("bc_lowpass_px"):
            # flat top: the painted crevice shading of the cliff texels reads as cloudy blotches on a flat lip ->
            # keep the crack-scale detail (gain), damp the low frequencies (keep), then darken (value scale)
            lowp = box_blur(f_bc, int(L["bc_lowpass_px"]))
            mean_ = f_bc.reshape(-1, 3).mean(0)
            f_bc = (mean_ + (f_bc - lowp) * float(L.get("bc_detail_gain", 1.0))
                    + (lowp - mean_) * float(L.get("bc_lowfreq_keep", 1.0)))
        if name != "rock_cap" and L.get("n_lowpass_px"):
            # the cliff normals carry the broad curvature of the Tripo rock faces: on the flat lip it shades as large
            # dark blotches under the Cobble key light -> damp the low frequencies of the tangent XY the same way
            lown = box_blur(f_n[..., :2], int(L["n_lowpass_px"]))
            f_n[..., :2] = ((f_n[..., :2] - lown) * float(L.get("n_detail_gain", 1.0))
                            + lown * float(L.get("n_lowfreq_keep", 1.0)))
        f_bc = np.clip(f_bc * vs, 0.0, 1.0)
        f_rm = np.clip(f_rm, 0.0, 1.0)
        f_n[..., :2] = np.clip(f_n[..., :2], -0.95, 0.95)
        f_n[..., 2] = np.sqrt(np.maximum(1.0 - f_n[..., 0] ** 2 - f_n[..., 1] ** 2, 0.0))
        out_bc[r0:r1, c0:c1, :3] = S.lin_to_srgb(f_bc) if srgb else f_bc
        out_rm[r0:r1, c0:c1, :3] = f_rm
        out_n[r0:r1, c0:c1, :3] = f_n * 0.5 + 0.5
        written += (r1 - r0) * (c1 - c0)
        stats[name] = {"rect_px": [c0, r0, c1 - c0, r1 - r0], "density_px_per_uu": S.r(dens, 4),
                       "bc_mean_srgb": [S.r(v, 3) for v in S.lin_to_srgb(f_bc).reshape(-1, 3).mean(0)],
                       "bc_value_scale": vs,
                       "bc_lowpass_px": (L.get("bc_lowpass_px") if name != "rock_cap" else None),
                       "bc_detail_gain": (L.get("bc_detail_gain") if name != "rock_cap" else None),
                       "bc_lowfreq_keep": (L.get("bc_lowfreq_keep") if name != "rock_cap" else None),
                       "n_lowpass_px": (L.get("n_lowpass_px") if name != "rock_cap" else None),
                       "n_lowfreq_keep": (L.get("n_lowfreq_keep") if name != "rock_cap" else None),
                       "normal_xy_rms": S.r(float(np.sqrt((f_n[..., :2] ** 2).sum(-1).mean())), 4)}
    rock_srgb = S.lin_to_srgb(bc_lin[ok])
    for img, arr in ((bc_img, out_bc), (mr_img, out_rm), (n_img, out_n)):
        img.pixels.foreach_set(arr.astype(np.float32).ravel())
        img.update()
    after = S.image_array(bc_img)[..., :3]
    changed = int((np.abs(after[cov] - bc[cov]) > 1e-6).any(1).sum())
    rec = {"method": "texture bombing of Tripo rock windows (Hann, stride win/2, variance-preserving), no mirroring; "
                     "no new texture source",
           "window_px": win, "source_erode_px": erode, "valid_windows": int(len(valid_tl)),
           "source_px_per_uu": sd, "seed": int(L.get("seed", 20260930)),
           "rock_bc_mean_srgb_source": [S.r(v, 3) for v in rock_srgb.mean(0)],
           "rock_bc_p50_value_srgb": S.r(float(np.percentile(rock_srgb.max(1), 50)), 3),
           "regions": stats, "texels_written": int(written), "rock_texels_changed": changed,
           "normal_convention_written": "OpenGL (as the glTF source; flipped to DirectX with the rest in textures)"}
    st["lip_tex"] = rec
    return rec


def step_boardref(P):
    """ART-005 board FBX as context (collection TableBase_BoardRef in the TableBase scene; never exported)."""
    use_scene()
    sc = bpy.context.scene
    name = SCENE + "_BoardRef"
    col = bpy.data.collections.get(name)
    if col is not None:
        for o in list(col.objects):
            bpy.data.objects.remove(o)
        bpy.data.collections.remove(col)
    col = bpy.data.collections.new(name)
    sc.collection.children.link(col)
    bpy.context.view_layer.active_layer_collection = bpy.context.view_layer.layer_collection.children[name]
    b = json.loads(Path(P["board_bounds_json"]).read_text(encoding="utf-8"))
    fbx = P["repo_root"] / b["fbx"]
    before = set(bpy.data.objects)
    bpy.ops.import_scene.fbx(filepath=str(fbx))
    new = [o for o in bpy.data.objects if o not in before]
    rot = Matrix.Rotation(math.radians(-90.0), 4, "Z")  # export frame -> .blend frame (inverse of UM_FBX_v1 +90)
    for o in new:
        if o.parent is None:
            o.matrix_world = rot @ o.matrix_world
    bpy.context.view_layer.update()
    S = load_tbc().S
    lo, hi = S.world_bounds([o for o in new if o.type == "MESH"])
    bpy.context.view_layer.active_layer_collection = bpy.context.view_layer.layer_collection.children[SCENE]
    return {"fbx": b["fbx"], "objects": len(new), "bounds_min_uu": [S.r(v * 100, 2) for v in lo],
            "bounds_max_uu": [S.r(v * 100, 2) for v in hi]}


def step_view(P):
    """Viewport for a shot: VIEW = {rot_euler_deg, dist_m, loc_m, shading, wire, board, lens, overlays}."""
    from mathutils import Euler, Vector
    V = globals().get("VIEW") or {}
    sc = use_scene()
    obj = obj_of(P)
    col = bpy.data.collections.get(SCENE + "_BoardRef")
    if col is not None:
        col.hide_viewport = not V.get("board", False)
    for o in sc.objects:
        o.select_set(False)
    if obj is not None:
        obj.show_wire = bool(V.get("wire", False))
        obj.show_all_edges = bool(V.get("wire", False))
    for area in bpy.context.window.screen.areas:
        if area.type != "VIEW_3D":
            continue
        sp = area.spaces.active
        r3 = sp.region_3d
        r3.view_perspective = "PERSP"
        r3.view_rotation = Euler([math.radians(a) for a in V.get("rot_euler_deg", (60, 0, 20))]).to_quaternion()
        r3.view_distance = float(V.get("dist_m", 14.0))
        r3.view_location = Vector(V.get("loc_m", (0.0, 0.0, -0.5)))
        sp.lens = float(V.get("lens", 50.0))
        sp.clip_end = 1000.0
        sp.shading.type = V.get("shading", "MATERIAL")
        sp.overlay.show_overlays = bool(V.get("overlays", True))
        area.tag_redraw()
    return {"view": V}


def step_relation(P):
    T = load_tbc()
    S = T.S
    use_scene()
    obj = obj_of(P)
    st = state()
    board = T.board_reference(P)
    st["board_reference"] = board
    top_m = float(P["top_z_uu"]) / 100.0
    target = [float(v) for v in P["footprint_uu_blend_xy"]]
    bvh = T.bvh_of(obj)
    lo = st["lo"]
    bmin, bmax = board["whole_uu_blend"]["min"], board["whole_uu_blend"]["max"]
    half = [max(abs(bmin[0]), abs(bmax[0])) / 100.0, max(abs(bmin[1]), abs(bmax[1])) / 100.0]
    rim = T.rim_widths(bvh, top_m, half)
    rim["board_half_extent_uu_blend"] = [S.r(half[0] * 100, 3), S.r(half[1] * 100, 3)]
    rim["board_outline_source"] = "board FBX bounds (whole mesh, .blend axes)"
    rim["proposed_uu"] = P["rim_proposed_uu"]
    rim["min_within_proposed"] = P["rim_proposed_uu"][0] <= rim["min_uu"] <= P["rim_proposed_uu"][1]
    rim["p50_within_proposed"] = P["rim_proposed_uu"][0] <= rim["p50_uu"] <= P["rim_proposed_uu"][1]
    rel = {"rim_flat_top": rim}
    levels = board["horizontal_face_levels_uu"]
    gaps = sorted(({"z_uu": h["z_uu"], "facing": h["facing"], "parts": h["parts"],
                    "gap_to_top_plane_uu": S.r(abs(h["z_uu"] - top_m * 100.0), 3)} for h in levels),
                  key=lambda g: g["gap_to_top_plane_uu"])
    st["coplanar_ok"] = gaps[0]["gap_to_top_plane_uu"] >= float(P["coplanar_min_uu"]) if gaps else True
    rel["board_horizontal_faces_nearest_top_plane"] = gaps[:4]
    rel["board_top_above_tray_top_uu"] = S.r(bmax[2] - top_m * 100.0, 3)
    rel["board_bottom_below_tray_top_uu"] = S.r(top_m * 100.0 - bmin[2], 3)
    rel["tray_depth_below_board_bottom_uu"] = S.r(bmin[2] - lo[2] * 100.0, 3)
    if board.get("undertray_uu_blend"):
        u = board["undertray_uu_blend"]
        rel["board_undertray_enclosed"] = T.enclosed(bvh, u["min"], u["max"])
    st["board_relation"] = rel
    _ = target
    return rel


def step_textures(P):
    T = load_tbc()
    S = T.S
    use_scene()
    obj = obj_of(P)
    st = state()
    out = P["out_dir"]
    for sub in ("work", "export", "reports", "preview", "blender"):
        (out / sub).mkdir(parents=True, exist_ok=True)
    glb = S.glb_json(P["source_glb"])
    st["textures"], bc_out = T.build_textures(obj, glb, P, out)
    size = int(P["texture_size"])
    uv, tuv = S.uv_analysis(obj, size)
    st["uv0"] = uv
    uv_png = out / "work" / ("%s_uv0_layout.png" % P["asset_name"])
    S.uv_layout_png(tuv, bc_out, size, uv_png)
    T.save_jpg(uv_png, out / "preview" / ("%s_uv0_layout.jpg" % P["asset_name"]), 1024)
    st["material_slots"] = len(obj.data.materials)
    st["material_names"] = [m.name for m in obj.data.materials]
    return {"textures": st["textures"], "uv0": uv}


def step_export(P):
    T = load_tbc()
    S = T.S
    sc = use_scene()
    obj = obj_of(P)
    st = state()
    out = P["out_dir"]
    # drop the glTF source images/materials and the AO bake buffer (not needed in the .blend; keeps it small)
    removed = []
    for name in st.get("gltf_materials", []):  # materials first: they hold the users of the packed glTF images
        m = bpy.data.materials.get(name)
        if m is not None and m.users == 0:
            bpy.data.materials.remove(m)
            removed.append(name)
    for name in st.get("gltf_images", []) + ["AO_bake"]:
        img = bpy.data.images.get(name)
        if img is not None and img.users == 0:
            bpy.data.images.remove(img)
            removed.append(name)
    st["blend_cleanup_removed"] = removed
    blend = out / "blender" / ("%s.blend" % P["asset_name"])
    bpy.context.preferences.filepaths.save_version = 0
    bpy.ops.wm.save_as_mainfile(filepath=str(blend), compress=True, copy=True, relative_remap=True)
    st["blend"] = {"path": S.rel(blend, P), "bytes": blend.stat().st_size,
                   "note": "copy of the live session (all scenes); tray in scene 'TableBase'; textures external, "
                           "relative paths ../export/T_TableBase_*.png"}
    preset = json.loads(P["fbx_preset"].read_text(encoding="utf-8"))
    fbx = out / "export" / ("%s.fbx" % P["asset_name"])
    kwargs = S.fbx_kwargs(preset)
    conformance = [c for c in S.um_fbx_v1_conformance(preset, kwargs, obj, sc)
                   if not c["setting"].startswith("Pivot:")]
    tlo, thi, hi = st["tlo"], st["thi"], st["hi"]
    top_m = float(P["top_z_uu"]) / 100.0
    centre_uu = [S.r((tlo[0] + thi[0]) * 50.0, 4), S.r((tlo[1] + thi[1]) * 50.0, 4)]
    conformance.append({"setting": "Pivot: board centre (0,0) = centre of the top outline; top plane at top_z_uu "
                                   "and nothing above it (04 3.6)",
                        "standard": [0.0, 0.0, float(P["top_z_uu"])],
                        "used": centre_uu + [S.r(hi[2] * 100.0, 4)],
                        "conforms": abs(centre_uu[0]) < 0.01 and abs(centre_uu[1]) < 0.01
                        and abs(hi[2] - top_m) < 1e-6})
    S.export_fbx(obj, fbx, preset)
    st["export"] = {
        "fbx": fbx.name, "sha256": S.sha256(fbx), "bytes": fbx.stat().st_size, "preset": P["fbx_preset"].name,
        "settings": {k: preset[k] for k in ("axis_forward", "axis_up", "export_space_rotation_z_degrees",
                                            "temporary_data_scale", "patch_fbx_unit_scale_to", "apply_scale_options",
                                            "use_triangles", "mesh_smooth_type", "path_mode")},
        "exporter_kwargs": {k: (sorted(v) if isinstance(v, set) else v) for k, v in sorted(kwargs.items())},
        "textures_embedded": False,
        "texture_paths": "relative to the FBX (absolute checkout path is never written)",
        "um_fbx_v1_conformance": conformance,
        "um_fbx_v1_conforms": all(c["conforms"] for c in conformance),
    }
    st["expected_tris"] = S.triangles(obj)
    return st["export"]


def step_roundtrip(P):
    T = load_tbc()
    S = T.S
    st = state()
    out = P["out_dir"]
    fbx = out / "export" / ("%s.fbx" % P["asset_name"])
    tmp = bpy.data.scenes.new(SCENE + "_RoundTrip")
    bpy.context.window.scene = tmp
    before_objs = set(bpy.data.objects)
    before_mats = set(bpy.data.materials)
    before_imgs = set(bpy.data.images)
    before_meshes = set(bpy.data.meshes)
    try:
        bpy.ops.import_scene.fbx(filepath=str(fbx))
        rt = S.mesh_objects()
        arm = [o for o in tmp.objects if o.type == "ARMATURE"]
        rt_obj = rt[0] if rt else None
        lo2, hi2 = S.world_bounds(rt)
        pts = np.array([list(rt_obj.matrix_world @ v.co) for v in rt_obj.data.vertices])
        rt_top = pts[np.abs(pts[:, 2] - hi2.z) < 1e-6]
        rt_top_size = rt_top.max(0) - rt_top.min(0)
        rt_top_centre = (rt_top.max(0) + rt_top.min(0)) / 2
        dims = st["scale_pivot"]["dimensions_m"]
        geo_rt, _ = S.geometry_stats(rt_obj)
        st["roundtrip"] = {
            "mesh_objects": len(rt), "object_names": [o.name for o in rt],
            "triangles": sum(S.triangles(o) for o in rt), "expected_triangles": st["expected_tris"],
            "material_slots": len(rt_obj.data.materials), "uv_layers": len(rt_obj.data.uv_layers),
            "armatures": len(arm),
            "dimensions_uu": [S.r(v * 100, 3) for v in (hi2 - lo2)],
            "bounds_min_uu": [S.r(v * 100, 3) for v in lo2], "bounds_max_uu": [S.r(v * 100, 3) for v in hi2],
            "top_outline_size_uu": [S.r(rt_top_size[0] * 100, 3), S.r(rt_top_size[1] * 100, 3)],
            "top_outline_centre_uu": [S.r(rt_top_centre[0] * 100, 3), S.r(rt_top_centre[1] * 100, 3)],
            "expected_ue_dimensions_uu_at_import_scale_1": [S.r(dims[1] * 100, 3), S.r(dims[0] * 100, 3),
                                                            S.r(dims[2] * 100, 3)],
            "object_scale": [S.r(v) for v in rt_obj.scale],
            "geometry_readback": geo_rt,
            "note": "FBX read back in the live Blender (temporary scene, removed) = UM_FBX_v1 export frame "
                    "(UE shows it as x, -y, z); metres x100 = uu",
        }
        top_ok = abs(hi2.z * 100 - float(P["top_z_uu"])) < 0.01
        tlo, thi = st["tlo"], st["thi"]
        exp_top = [thi[1] - tlo[1], thi[0] - tlo[0]]
        target = [float(v) for v in P["footprint_uu_blend_xy"]]
        if P.get("lip"):  # flat top = footprint minus the bevel; the footprint itself = XY bounds of the tray
            bev = 2.0 * float(P["lip"]["bevel_uu"])
            target = [target[0] - bev, target[1] - bev]
            rt_xy = (hi2 - lo2) * 100.0
            st["roundtrip"]["xy_bounds_match_footprint_1uu"] = bool(
                abs(rt_xy[0] - float(P["footprint_uu_blend_xy"][1])) < 1.0
                and abs(rt_xy[1] - float(P["footprint_uu_blend_xy"][0])) < 1.0)
        closed = st["geometry"]["closed_manifold_consistent_after"]
        checks = {
            "single_mesh": len(rt) == 1,
            "triangles_preserved": st["roundtrip"]["triangles"] == st["expected_tris"],
            "one_material_slot": st["roundtrip"]["material_slots"] == 1,
            "uv0_present": st["roundtrip"]["uv_layers"] >= 1,
            "no_armature": not arm,
            "top_at_top_z": top_ok,
            "top_outline_matches_footprint_1uu": (abs(rt_top_size[0] - exp_top[0]) * 100 < 1.0
                                                  and abs(rt_top_size[1] - exp_top[1]) * 100 < 1.0
                                                  and abs(rt_top_size[0] * 100 - target[1]) < 1.0
                                                  and abs(rt_top_size[1] * 100 - target[0]) < 1.0),
            "top_outline_centred": abs(rt_top_centre[0]) * 100 < 0.01 and abs(rt_top_centre[1]) * 100 < 0.01,
            "no_folded_faces_in_top_plane": st["fit"]["flatten"]["faces_in_top_plane_facing_down_folded"] == 0,
            "no_board_horizontal_face_near_top_plane": st["coplanar_ok"],
            "source_unchanged": S.sha256(P["source_glb"]) == st["source"]["sha256"],
            "um_fbx_v1_conforms": st["export"]["um_fbx_v1_conforms"],
            "closed_manifold_consistent_winding": closed,
            "readback_closed_manifold": (geo_rt["welded_boundary_edges"] == 0
                                         and geo_rt["welded_non_manifold_edges"] == 0),
        }
        if P.get("lip"):
            checks["xy_bounds_match_footprint_1uu"] = st["roundtrip"]["xy_bounds_match_footprint_1uu"]
            checks["lip_rock_texels_unchanged"] = st.get("lip_tex", {}).get("rock_texels_changed", 1) == 0
        st["checks"] = {k: bool(v) for k, v in checks.items()}
    finally:
        for o in list(tmp.objects):
            bpy.data.objects.remove(o)
        for m in set(bpy.data.meshes) - before_meshes:
            if m.users == 0:
                bpy.data.meshes.remove(m)
        for m in set(bpy.data.materials) - before_mats:
            if m.users == 0:
                bpy.data.materials.remove(m)
        for i in set(bpy.data.images) - before_imgs:
            if i.users == 0:
                bpy.data.images.remove(i)
        _ = before_objs
        bpy.data.scenes.remove(tmp)
        use_scene()
    return {"roundtrip": st["roundtrip"], "checks": st["checks"]}


def step_report(P):
    T = load_tbc()
    S = T.S
    st = state()
    out = P["out_dir"]
    report = {
        "schema": T.SCHEMA, "status": "measured", "asset": "ASSET-TABLE-BASE-001",
        "claims": {"art_accepted": False, "game_ready": False, "budgets_declared": False},
        "session": "live Blender GUI through Blender MCP (execute_code), scene 'TableBase'; driver "
                   "scripts/table_base_live_mcp.py",
        "blender_version": bpy.app.version_string,
        "script_sha256_lf": S.text_sha256_lf(TBC),
        "live_driver_sha256_lf": S.text_sha256_lf(LIVE_FILE),
        "helpers": {"path": S.rel(T.SPC, P), "sha256_lf": S.text_sha256_lf(T.SPC)},
        "params": {k: (S.rel(v, P) if isinstance(v, Path) else v) for k, v in P.items() if k != "repo_root"},
        "source": st["source"],
        "board_reference": st.get("board_reference"),
        "import": st["import"],
        "geometry": st["geometry"],
        "fit": st["fit"],
        "scale_pivot": st["scale_pivot"],
        "cap_uv": st.get("cap_uv"),
        "cap_bake": st.get("cap_bake"),
        "lip": st.get("lip"),
        "lip_textures": st.get("lip_tex"),
        "board_relation": st["board_relation"],
        "textures": st["textures"],
        "uv0": st["uv0"],
        "material_slots": st["material_slots"],
        "material_names": st["material_names"],
        "blend": st.get("blend"),
        "blend_cleanup_removed": st.get("blend_cleanup_removed"),
        "export": st["export"],
        "roundtrip": st["roundtrip"],
        "checks": st["checks"],
        "checks_passed": all(st["checks"].values()),
        "decisions": st.get("decisions", {}),
    }
    text = json.dumps(report, indent=2, ensure_ascii=False, default=T.json_default) + "\n"
    (out / "reports" / "candidate-report.json").write_text(text, encoding="utf-8")
    return {"checks": st["checks"], "checks_passed": report["checks_passed"]}


def run(step, params_path):
    if step == "setup":  # re-read table_base_candidate.py / helpers on every fresh run
        bpy.app.driver_namespace.pop(STATE_KEY + "_tbc", None)
    P = params(params_path)
    st = state()
    if step == "setup":
        res = step_setup(P)
        st = state()
        T = load_tbc()
        st["source"] = {"path": T.S.rel(P["source_glb"], P), "sha256": T.S.sha256(P["source_glb"]),
                        "bytes": P["source_glb"].stat().st_size,
                        "gltf_generator": T.S.glb_json(P["source_glb"])[0].get("asset", {}).get("generator")}
        return res
    fn = {"import": step_import, "fit": step_fit, "cut": step_cut, "capuv": step_capuv, "capbake": step_capbake,
          "lip": step_lip, "liptex": step_liptex, "boardref": step_boardref, "view": step_view,
          "relation": step_relation, "textures": step_textures,
          "export": step_export, "roundtrip": step_roundtrip, "report": step_report}[step]
    _ = st
    return fn(P)


if "STEP" in globals():
    _res = run(globals()["STEP"], globals()["PARAMS"])
    print("LIVE_STEP", globals()["STEP"], json.dumps(_res, ensure_ascii=False, default=lambda o: o.item() if hasattr(o, "item") else str(o))[:20000])
