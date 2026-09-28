"""ASSET-DECOR-KIT-001.FACADES, step 2 of 3 (Blender 5.2 headless, a fresh process only):

    "C:/Program Files/Blender Foundation/Blender 5.2/blender.exe" -b --factory-startup --python-exit-code 1 \
        --python art/pipeline-candidates/ASSET-DECOR-KIT-001/scripts/facades_build.py -- \
        art/pipeline-candidates/ASSET-DECOR-KIT-001/scripts/facades_params.json

Reads reports/trace.json (step 1) and builds one static mesh per facade:
  - front: constrained Delaunay triangulation of the silhouette polygon, glow slits as constraint rectangles
    (their triangles get material slot 1), plane y = 0, normal -Y (04 §1: front = -Y in Blender -> +X in UE);
  - back: same polygon at y = thickness, reversed; sides: one quad per polygon edge; closed, flat shaded;
  - pivot (04 §1, decor facade): bottom edge of the outer (front) face, centred -> origin (0, 0, 0);
  - UV0: front = planar projection into its atlas strip; back = mirrored planar projection and sides = one
    unrolled band per facade, both at back_side_density_scale into uniform-colour atlas rects; no overlaps;
  - materials: M_Decor_Facades (BC/N/ORM atlas) and, when the facade has glow slits, M_Decor_FacadeGlow
    (same atlas, emissive; the UE Emissive parameter is deferred) -> <= 2 slots (04 §3.7);
  - no collision (04 §3.7: decor is not interactive);
  - export UM_FBX_v1 with the helpers of tools/tripo-pipeline/blender/static_prop_candidate.py (loaded without
    running its main(); that file is not modified), texture references relative (../textures/...);
  - previews: orthographic front and the K-1 game camera (FOV 35 deg horizontal, pitch -55 deg, 12 m) over a
    5x6 board of 94 uu tiles, JPEG <= 1200 px.
Status of everything written here: measured. Not art-accepted, not imported in UE.
"""
import hashlib
import json
import math
import os
import sys
from pathlib import Path

import bmesh
import bpy
import numpy as np
from mathutils import Matrix, Vector, geometry as mgeo

ROOT = Path(__file__).resolve().parents[4]
SPC = ROOT / "tools/tripo-pipeline/blender/static_prop_candidate.py"


def load_helpers():
    src = SPC.read_text(encoding="utf-8")
    body = src.rstrip()
    if not body.endswith("\nmain()"):
        raise SystemExit("static_prop_candidate.py no longer ends with main(); helper import must be revisited")
    ns = {"__file__": str(SPC), "__name__": "static_prop_candidate_helpers"}
    exec(compile(body[: -len("main()")], str(SPC), "exec"), ns)
    return ns, hashlib.sha256(src.encode("utf-8").replace(b"\r\n", b"\n")).hexdigest()


H_, SPC_SHA = load_helpers()
r = H_["r"]
sha256 = H_["sha256"]


def text_sha(path):
    return hashlib.sha256(Path(path).read_bytes().replace(b"\r\n", b"\n")).hexdigest()


# ----------------------------------------------------------------------------- mesh
def cdt(points, faces_in):
    out_v, _e, out_f, orig_v, _oe, orig_f = mgeo.delaunay_2d_cdt([Vector(p) for p in points], [], faces_in, 1, 1e-9)
    if len(out_v) != len(points):
        raise RuntimeError("CDT added/removed vertices (%d -> %d)" % (len(points), len(out_v)))
    to_in = [ov[0] for ov in orig_v]
    return [[to_in[i] for i in f] for f in out_f], orig_f


def build_mesh(fc, rects, S, d_front, q, T_uu, name, has_glow):
    L, Hh = fc["length_uu"], fc["height_uu"]
    poly = [tuple(p) for p in fc["polygon_uu"]]
    n = len(poly)
    glow = [g["rect_uu_x0_z0_x1_z1"] for g in fc["glow"]]
    pts = list(poly)
    faces_in = [list(range(n))]
    for x0, z0, x1, z1 in glow:
        b = len(pts)
        pts += [(x0, z0), (x1, z0), (x1, z1), (x0, z1)]
        faces_in.append([b, b + 1, b + 2, b + 3])
    front_tris, orig_f = cdt(pts, faces_in)
    back_tris, _ = cdt(poly, [list(range(n))])

    fx, fy, fw, fh = rects["front_" + fc["key"]]
    bx, by, bw, bh = rects["back_" + fc["key"]]
    sx, sy, sw, sh = rects["side_" + fc["key"]]
    su, sz = fw / L, fh / Hh  # strip px per uu (== density up to rounding of the strip size)

    def uv_front(x, z):
        return ((fx + (x + L / 2) * su) / S, 1 - (fy + (Hh - z) * sz) / S)

    def uv_back(x, z):
        return ((bx + 1 + (L / 2 - x) * q) / S, 1 - (by + 1 + (Hh - z) * q) / S)

    cum = [0.0]
    for i in range(n):
        cum.append(cum[-1] + math.dist(poly[i], poly[(i + 1) % n]))

    bm = bmesh.new()
    uvl = bm.loops.layers.uv.new("UVMap")
    T = T_uu / 100.0
    fv = [bm.verts.new((x / 100.0, 0.0, z / 100.0)) for x, z in pts]
    bv = [bm.verts.new((x / 100.0, T, z / 100.0)) for x, z in poly]
    kind = {}
    for k, tri in enumerate(front_tris):
        f = bm.faces.new([fv[i] for i in tri])
        f.material_index = 1 if (has_glow and any(o >= 1 for o in orig_f[k])) else 0
        kind[f] = ("front", None)
    for tri in back_tris:
        f = bm.faces.new([bv[i] for i in tri[::-1]])
        kind[f] = ("back", None)
    for i in range(n):
        j = (i + 1) % n
        f = bm.faces.new([fv[i], fv[j], bv[j], bv[i]])
        kind[f] = ("side", i)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    front_faces = [f for f in bm.faces if kind[f][0] == "front"]
    if sum(1 for f in front_faces if f.normal.y < 0) < len(front_faces):
        raise RuntimeError("front faces do not all face -Y after outward normal recalculation")

    side_flip_v = None
    for f in bm.faces:
        kd, ei = kind[f]
        for lp in f.loops:
            x, y, z = lp.vert.co.x * 100, lp.vert.co.y * 100, lp.vert.co.z * 100
            if kd == "front":
                lp[uvl].uv = uv_front(x, z)
            elif kd == "back":
                lp[uvl].uv = uv_back(x, z)
            else:
                i, j = ei, (ei + 1) % n
                vi = lp.vert
                t = cum[ei] if vi in (fv[i], bv[i]) else cum[ei + 1]
                lp[uvl].uv = (t, y)  # provisional, finalised below
    # side band orientation: try v along +thickness; if that mirrors the map w.r.t. the outward normal, flip v
    def assign_side(flip):
        for f in bm.faces:
            if kind[f][0] != "side":
                continue
            for lp in f.loops:
                t, y = side_ty[lp]
                yy = (T_uu - y) if flip else y
                lp[uvl].uv = ((sx + 1 + t * q) / S, 1 - (sy + 1 + yy * q) / S)

    def mirrored_sides():
        bad = 0
        for f in bm.faces:
            if kind[f][0] != "side":
                continue
            a, b, c = f.loops[0], f.loops[1], f.loops[2]
            e1, e2 = b.vert.co - a.vert.co, c.vert.co - a.vert.co
            du1, dv1 = b[uvl].uv.x - a[uvl].uv.x, b[uvl].uv.y - a[uvl].uv.y
            du2, dv2 = c[uvl].uv.x - a[uvl].uv.x, c[uvl].uv.y - a[uvl].uv.y
            det = du1 * dv2 - du2 * dv1
            dpdu = (e1 * dv2 - e2 * dv1) / det
            dpdv = (e2 * du1 - e1 * du2) / det
            bad += dpdu.cross(dpdv).dot(f.normal) < 0
        return bad

    side_ty = {lp: tuple(lp[uvl].uv) for f in bm.faces if kind[f][0] == "side" for lp in f.loops}
    side_flip_v = False
    assign_side(False)
    if mirrored_sides():
        side_flip_v = True
        assign_side(True)
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    for p in me.polygons:
        p.use_smooth = False
    obj = bpy.data.objects.new(name, me)
    bpy.context.scene.collection.objects.link(obj)
    return obj, {"front_triangles": len(front_tris), "back_triangles": len(back_tris), "side_quads": n,
                 "side_band_v_flipped": bool(side_flip_v), "perimeter_uu": r(cum[-1], 3),
                 "front_strip_px_per_uu": [r(su, 4), r(sz, 4)], "back_side_px_per_uu": q}


def uv_mirrored_faces(obj):
    """Faces whose UV map is mirrored relative to the outward normal (tangent-space handedness flip)."""
    me = obj.data
    uv = me.uv_layers[0].data
    bad = 0
    for p in me.polygons:
        li = list(p.loop_indices)[:3]
        a, b, c = (me.vertices[me.loops[i].vertex_index].co for i in li)
        ua, ub, uc = (Vector(uv[i].uv) for i in li)
        e1, e2 = b - a, c - a
        du1, dv1 = (ub - ua)
        du2, dv2 = (uc - ua)
        det = du1 * dv2 - du2 * dv1
        if abs(det) < 1e-14:
            bad += 1
            continue
        dpdu = (e1 * dv2 - e2 * dv1) / det
        dpdv = (e2 * du1 - e1 * du2) / det
        bad += dpdu.cross(dpdv).dot(p.normal) < 0
    return int(bad)


# ----------------------------------------------------------------------------- materials
def load_image(path, colorspace):
    img = bpy.data.images.load(str(path), check_existing=True)
    img.colorspace_settings.name = colorspace
    return img


def glow_material(name, bc, n_dx, orm, strength):
    mat = H_["build_material"](name, bc, n_dx, orm)
    nt = mat.node_tree
    bsdf = next(nd for nd in nt.nodes if nd.type == "BSDF_PRINCIPLED")
    tex = next(nd for nd in nt.nodes if nd.type == "TEX_IMAGE" and nd.image == bc)
    nt.links.new(tex.outputs["Color"], bsdf.inputs["Emission Color"])
    bsdf.inputs["Emission Strength"].default_value = strength
    return mat


# ----------------------------------------------------------------------------- export
def export_with_relative_textures(obj, fbx_path, preset):
    """helpers' export_fbx (UM_FBX_v1: +90 Z, x100, UnitScaleFactor 1.0, deterministic) with texture paths written
    relative to the FBX folder: path_mode AUTO would write an absolute path for ../textures (not a subfolder)."""
    from io_scene_fbx import export_fbx_bin
    orig_make = H_["make_fbx_deterministic"]
    fbx_dir = Path(fbx_path).parent

    def make():
        restore = orig_make()
        prev = export_fbx_bin._gen_vid_path

        def rel_path(img, scene_data):
            rel = os.path.relpath(bpy.path.abspath(img.filepath), fbx_dir).replace("\\", "/")
            return rel, rel
        export_fbx_bin._gen_vid_path = rel_path

        def restore_all():
            export_fbx_bin._gen_vid_path = prev
            restore()
        return restore_all

    H_["make_fbx_deterministic"] = make
    try:
        H_["export_fbx"](obj, fbx_path, preset)
    finally:
        H_["make_fbx_deterministic"] = orig_make


def fbx_absolute_path_leaks(path):
    data = Path(path).read_bytes()
    needles = [str(ROOT).encode(), str(ROOT).replace("\\", "/").encode(), b"C:\\", b"C:/", b"Users\\ren", b"Users/ren"]
    return sorted({n.decode() for n in needles if n in data})


# ----------------------------------------------------------------------------- previews
def setup_render(scene, w, h):
    try:
        scene.render.engine = "BLENDER_EEVEE_NEXT"
    except TypeError:
        scene.render.engine = "BLENDER_EEVEE"
    scene.render.resolution_x, scene.render.resolution_y = w, h
    scene.render.resolution_percentage = 100
    scene.render.film_transparent = False
    scene.view_settings.view_transform = "Standard"
    scene.render.image_settings.file_format = "JPEG"
    scene.render.image_settings.quality = 88
    world = scene.world or bpy.data.worlds.new("World")
    scene.world = world
    world.use_nodes = True
    bg = world.node_tree.nodes.get("Background")
    bg.inputs["Color"].default_value = (0.05, 0.06, 0.08, 1)
    bg.inputs["Strength"].default_value = 1.0


def add_lights(scene):
    objs = []
    for nm, energy, rot in (("Key", 3.0, (50, 0, 20)), ("Fill", 0.8, (65, 0, -150))):
        ld = bpy.data.lights.new("PV_" + nm, "SUN")
        ld.energy = energy
        ld.use_shadow = nm == "Key"
        o = bpy.data.objects.new("PV_" + nm, ld)
        o.rotation_euler = tuple(math.radians(a) for a in rot)
        scene.collection.objects.link(o)
        objs.append(o)
    return objs


def board(scene):
    """Preview-only context: tray 714.5 x 612.6 x 40 uu, 6 x 5 tiles of 94 uu with 6 uu seams (S04/S05 measures);
    long side along X as 03 §2 prescribes for a 5x6 board (camera looks along +Y)."""
    objs = []
    mt = bpy.data.materials.new("PV_Tray")
    mt.use_nodes = True
    mt.node_tree.nodes["Principled BSDF"].inputs["Base Color"].default_value = (0.02, 0.022, 0.028, 1)
    mc = bpy.data.materials.new("PV_Tile")
    mc.use_nodes = True
    mc.node_tree.nodes["Principled BSDF"].inputs["Base Color"].default_value = (0.09, 0.1, 0.12, 1)
    bm = bmesh.new()
    bmesh.ops.create_cube(bm, size=1.0)
    bmesh.ops.scale(bm, vec=(7.145, 6.126, 0.40), verts=bm.verts)
    bmesh.ops.translate(bm, vec=(0, 0, -0.20 - 0.005), verts=bm.verts)
    me = bpy.data.meshes.new("PV_Tray")
    bm.to_mesh(me)
    bm.free()
    me.materials.append(mt)
    o = bpy.data.objects.new("PV_Tray", me)
    scene.collection.objects.link(o)
    objs.append(o)
    bm = bmesh.new()
    for cx in range(6):
        for cy in range(5):
            x0, y0 = (cx - 3.0) + 0.03, (cy - 2.5) + 0.03
            vs = [bm.verts.new((x0, y0, 0)), bm.verts.new((x0 + 0.94, y0, 0)),
                  bm.verts.new((x0 + 0.94, y0 + 0.94, 0)), bm.verts.new((x0, y0 + 0.94, 0))]
            bm.faces.new(vs)
    me = bpy.data.meshes.new("PV_Tiles")
    bm.to_mesh(me)
    bm.free()
    me.materials.append(mc)
    o = bpy.data.objects.new("PV_Tiles", me)
    scene.collection.objects.link(o)
    objs.append(o)
    return objs


def camera(scene, ortho):
    cd = bpy.data.cameras.new("PV_Cam")
    cd.type = "ORTHO" if ortho else "PERSP"
    cd.sensor_fit = "HORIZONTAL"
    cam = bpy.data.objects.new("PV_Cam", cd)
    scene.collection.objects.link(cam)
    scene.camera = cam
    return cam


def look(cam, pos, target):
    cam.location = pos
    cam.rotation_euler = (Vector(target) - Vector(pos)).to_track_quat("-Z", "Y").to_euler()


def render(scene, path):
    scene.render.filepath = str(path)
    bpy.ops.render.render(write_still=True)
    return path


# ----------------------------------------------------------------------------- main
def main():
    params_path = Path(sys.argv[sys.argv.index("--") + 1]).resolve()
    P = json.loads(params_path.read_text(encoding="utf-8"))
    out = ROOT / P["out_dir"]
    trace_path = out / "reports" / "trace.json"
    TR = json.loads(trace_path.read_text(encoding="utf-8"))
    preset_path = ROOT / P["fbx_preset"]
    preset = json.loads(preset_path.read_text(encoding="utf-8"))
    for sub in ("work", "export", "reports", "preview"):
        (out / sub).mkdir(parents=True, exist_ok=True)
    S = TR["atlas_px"]
    d = TR["density_px_per_uu"]
    q = TR["back_side_density_px_per_uu"]
    T_uu = TR["thickness_uu"]
    rects = TR["atlas_rects_px_x_y_w_h_top_left_origin"]

    bpy.ops.wm.read_factory_settings(use_empty=True)  # fresh headless process only
    scene = bpy.context.scene
    scene.unit_settings.system = "METRIC"
    scene.unit_settings.scale_length = 1.0

    tex = {k: out / v["path"].split(P["out_dir"] + "/", 1)[1] for k, v in TR["textures"].items()}
    tex_sha_before = {k: sha256(p) for k, p in tex.items()}
    if any(tex_sha_before[k] != TR["textures"][k]["sha256"] for k in tex):
        raise RuntimeError("textures changed since trace.json")
    bc = load_image(tex["BC"], "sRGB")
    nn = load_image(tex["N"], "Non-Color")
    orm = load_image(tex["ORM"], "Non-Color")
    m_wall = H_["build_material"](P["material_wall"], bc, nn, orm)
    m_glow = glow_material(P["material_glow"], bc, nn, orm, 4.0)

    report = {
        "schema": "unmatched.decor-facades.build/1", "status": "measured",
        "claims": {"art_accepted": False, "game_ready": False, "budgets_declared": False, "ue_imported": False},
        "blender_version": bpy.app.version_string,
        "script": Path(__file__).resolve().relative_to(ROOT).as_posix(), "script_sha256_lf": text_sha(__file__),
        "helpers": {"path": SPC.relative_to(ROOT).as_posix(), "sha256_lf": SPC_SHA,
                    "used": ["export_fbx", "make_fbx_deterministic", "patch_fbx_units", "fbx_kwargs",
                             "um_fbx_v1_conformance", "geometry_stats", "corner_normal_stats", "uv_analysis",
                             "build_material"]},
        "params": params_path.relative_to(ROOT).as_posix(), "params_sha256_lf": text_sha(params_path),
        "trace": {"path": trace_path.relative_to(ROOT).as_posix(), "sha256": sha256(trace_path)},
        "fbx_preset": {"path": P["fbx_preset"], "sha256_lf": text_sha(preset_path)},
        "textures": TR["textures"],
        "units": "Blender metres; uu = cm = FBX numbers (UnitScaleFactor 1.0)",
        "facades": [],
    }
    built = []
    for fc in TR["facades"]:
        name = fc["asset_name"]
        has_glow = bool(fc["glow"])
        obj, meta = build_mesh(fc, rects, S, d, q, T_uu, name, has_glow)
        obj.data.materials.append(m_wall)
        if has_glow:
            obj.data.materials.append(m_glow)
        geo, flipped = H_["geometry_stats"](obj)
        lo, hi = H_["world_bounds"]([obj])
        me = obj.data
        area_front = Vector((0, 0, 0))
        for p in me.polygons:
            if abs(p.center.y) < 1e-9:
                area_front += p.normal * p.area
        uv, tuv = H_["uv_analysis"](obj, S)
        slots = [m.name for m in me.materials]
        used_slots = sorted({p.material_index for p in me.polygons})
        rec = {
            "key": fc["key"], "asset_name": name, "build": meta,
            "triangles": H_["triangles"](obj), "vertices": len(me.vertices),
            "geometry": geo,
            "corner_normals": H_["corner_normal_stats"](obj),
            "bounds_min_uu": [r(v * 100, 3) for v in lo], "bounds_max_uu": [r(v * 100, 3) for v in hi],
            "dimensions_uu_x_len_y_thick_z_height": [r((hi[i] - lo[i]) * 100, 3) for i in range(3)],
            "pivot": {"origin": [0.0, 0.0, 0.0], "rule": "04 §1: facade = bottom edge of the outer face, centred",
                      "min_z_uu": r(lo.z * 100, 6), "x_centre_offset_uu": r((lo.x + hi.x) * 50, 6),
                      "front_face_y_uu": r(lo.y * 100, 6)},
            "front_area_weighted_normal": [r(v, 6) for v in area_front.normalized()],
            "front_area_m2": r(area_front.length, 6),
            "material_slots": slots, "material_slots_used": used_slots,
            "glow_faces": sum(1 for p in me.polygons if p.material_index == 1),
            "glow_area_uu2": r(sum(p.area for p in me.polygons if p.material_index == 1) * 1e4, 3),
            "uv0": uv, "uv_mirrored_faces": uv_mirrored_faces(obj),
            "collision": "none (04 §3.7: decor not interactive; clicks go through to L1)",
        }
        # UM_FBX_v1 rows (helpers) with the decor-facade pivot rule instead of the base-centre row
        kw = H_["fbx_kwargs"](preset)
        rows = [row for row in H_["um_fbx_v1_conformance"](preset, kw, obj, scene) if not row["setting"].startswith("Pivot")]
        rows.append({"setting": "Pivot: facade = bottom edge of outer face, centred (04 §1)", "standard": True,
                     "used": abs(lo.z) < 1e-6 and abs(lo.x + hi.x) < 1e-6 and abs(lo.y) < 1e-9,
                     "conforms": abs(lo.z) < 1e-6 and abs(lo.x + hi.x) < 1e-6 and abs(lo.y) < 1e-9})
        rec["um_fbx_v1_rows"] = rows
        rec["um_fbx_v1_conforms"] = all(row["conforms"] for row in rows)
        fbx = out / "export" / (name + ".fbx")
        export_with_relative_textures(obj, fbx, preset)
        rec["export"] = {"fbx": fbx.relative_to(ROOT).as_posix(), "sha256": sha256(fbx), "bytes": fbx.stat().st_size,
                         "absolute_path_leaks": fbx_absolute_path_leaks(fbx),
                         "texture_refs": sorted({s for s in ("../textures/%s_%s.png" % (P["texture_prefix"], k)
                                                             for k in ("BC", "N", "ORM"))
                                                 if s.encode() in fbx.read_bytes()})}
        L, Hh = fc["length_uu"], fc["height_uu"]
        dims = rec["dimensions_uu_x_len_y_thick_z_height"]
        rec["checks"] = {
            "single_mesh_no_armature": True,
            "closed_manifold_consistent_winding": geo["welded_boundary_edges"] == 0 and geo["welded_non_manifold_edges"] == 0
                                                  and geo["faces_with_inconsistent_winding"] == 0 and geo["signed_volume_m3"] > 0,
            "front_faces_minus_y": rec["front_area_weighted_normal"][1] < -0.999999,
            "length_300_600_uu_proposed": 300 <= dims[0] <= 600,
            "height_le_120_uu_proposed": dims[2] <= 120 + 1e-6,
            "height_matches_param_0_1pct": abs(dims[2] - Hh) <= Hh * 1e-3,
            "length_matches_trace_0_1pct": abs(dims[0] - L) <= L * 1e-3,
            "thickness_matches_param": abs(dims[1] - T_uu) < 1e-6,
            "material_slots_le_2": len(slots) <= 2 and used_slots == list(range(len(slots))),
            "uv0_in_0_1_no_overlap": uv["triangles_out_of_0_1"] == 0 and uv["overlap_pixels_between_islands"] == 0
                                     and uv["overlap_pixels_inside_islands_strict"] == 0,
            "uv_not_mirrored": rec["uv_mirrored_faces"] == 0,
            "no_absolute_paths_in_fbx": not rec["export"]["absolute_path_leaks"],
            "um_fbx_v1_conforms": rec["um_fbx_v1_conforms"],
        }
        rec["checks_passed"] = all(rec["checks"].values())
        report["facades"].append(rec)
        built.append(obj)

    # ---------------------------------------------------------------- previews
    setup_render(scene, 1200, 400)
    add_lights(scene)
    cam = camera(scene, ortho=True)
    previews = {}
    for obj in built:
        for o in built:
            o.hide_render = o is not obj
        lo, hi = H_["world_bounds"]([obj])
        c = (lo + hi) / 2
        L = hi.x - lo.x
        cam.data.ortho_scale = L * 1.06
        scene.render.resolution_x, scene.render.resolution_y = 1200, int(round(1200 * (hi.z - lo.z) * 1.06 / (L * 1.06) + 40))
        cam.data.ortho_scale = L * 1.06
        look(cam, (c.x, -10.0, c.z), (c.x, 0.0, c.z))
        previews[obj.name + "_front"] = render(scene, out / "preview" / (obj.name + "_front-ortho.jpg"))
    # game camera (03 §2): FOV 35 deg horizontal, pitch -55 deg, 12 m; board centre at origin, long side along X,
    # facade front at y = FACADE_Y (tray margin behind the far row: tiles end at y = 250 uu, tray edge at 306 uu)
    board(scene)
    pc = camera(scene, ortho=False)
    pc.data.angle = math.radians(35.0)
    scene.render.resolution_x, scene.render.resolution_y = 1200, 675
    dist, pitch = 12.0, math.radians(55.0)
    facade_y = 2.70

    def aim(target_y):
        tgt = Vector((0.0, target_y, 0.0))
        look(pc, tgt + Vector((0.0, -dist * math.cos(pitch), dist * math.sin(pitch))), tgt)

    # frame position of the facade base/top at exact K-1 (target = board centre), analytic, 16:9
    vfov_half = math.degrees(math.atan(math.tan(math.radians(17.5)) * 675 / 1200))
    cam_pos = Vector((0.0, -dist * math.cos(pitch), dist * math.sin(pitch)))
    k1_frame = {}
    for fc in TR["facades"]:
        rows = {}
        for lab, z in (("base", 0.0), ("top", fc["height_uu"] / 100.0)):
            v = Vector((0.0, facade_y, z)) - cam_pos
            dep = math.degrees(math.atan2(-v.z, v.y))
            rows[lab + "_deg_above_frame_centre"] = r(55.0 - dep, 3)
            rows[lab + "_in_frame"] = (55.0 - dep) <= vfov_half
        k1_frame[fc["key"]] = rows
    report["k1_exact_frame_analysis"] = {"vertical_half_fov_deg_16x9": r(vfov_half, 3), "facade_front_y_uu": facade_y * 100,
                                         "per_facade": k1_frame}
    offs = {"A": (0.0, facade_y), "B": (-3.1, facade_y + 0.6), "C": (3.1, facade_y + 0.6)}
    for obj, fc in zip(built, TR["facades"]):
        obj.location = (offs[fc["key"]][0], offs[fc["key"]][1], 0.0)
        obj.hide_render = False
    aim(0.0)
    previews["lineup_k1_exact"] = render(scene, out / "preview" / "facades-lineup_k1-exact-12m.jpg")
    aim(1.5)
    previews["lineup_game_far"] = render(scene, out / "preview" / "facades-lineup_game-fov35-pitch55-target-y150.jpg")
    for obj in built:
        obj.location = (0.0, facade_y, 0.0)
    for obj in built:
        for o in built:
            o.hide_render = o is not obj
        previews[obj.name + "_game"] = render(scene, out / "preview" / (obj.name + "_game-fov35-pitch55-target-y150.jpg"))
    # back three-quarter of A (thickness, back/side colour)
    for obj in built:
        obj.location = (0.0, 0.0, 0.0)
        obj.hide_render = obj is not built[0]
    for o in board_objs(scene):
        o.hide_render = True
    look(pc, (4.6, 8.8, 3.4), (0.0, 0.0, 0.55))
    previews["A_back"] = render(scene, out / "preview" / (built[0].name + "_back-3q.jpg"))
    for obj in built:
        obj.hide_render = False
        obj.location = (0.0, 0.0, 0.0)
    report["previews"] = {k: {"path": v.relative_to(ROOT).as_posix()} for k, v in previews.items()}
    report["preview_note"] = ("EEVEE, neutral sun key (shadowed) + fill (no shadow), dark world; not the P1.7 control scene. "
                              "Game shots: FOV 35 deg horizontal, pitch -55 deg, 12 m (03 §2), 16:9, board 6x5 tiles with the "
                              "long side along X; facade front at y=+270 uu on the side far from the camera. *_k1-exact: "
                              "target = board centre (K-1); *_target-y150: same camera shifted 1.5 m toward the far side so the "
                              "facade is in frame. Lineup offsets (B left, C right, 0.6 m further back) are a skyline check, "
                              "not a layout decision. Emission strength 4 is a preview value only.")
    bpy.ops.wm.save_as_mainfile(filepath=str(out / "work" / "decor-facades.blend"), compress=True)
    report["work_blend"] = (out / "work" / "decor-facades.blend").relative_to(ROOT).as_posix() + " (transient, gitignored)"
    report["textures_unchanged"] = all(sha256(p) == tex_sha_before[k] for k, p in tex.items())
    report["checks_passed"] = all(f["checks_passed"] for f in report["facades"]) and report["textures_unchanged"]
    (out / "reports" / "build-report.json").write_text(json.dumps(report, indent=1, ensure_ascii=False), encoding="utf-8")
    print("FACADES_BUILD", json.dumps({f["key"]: [f["triangles"], f["dimensions_uu_x_len_y_thick_z_height"], f["checks_passed"]]
                                       for f in report["facades"]}), "ALL", report["checks_passed"])
    if not report["checks_passed"]:
        failed = {f["key"]: [k for k, v in f["checks"].items() if not v] for f in report["facades"]}
        raise SystemExit("checks failed: %s" % failed)


def board_objs(scene):
    return [o for o in scene.objects if o.name.startswith("PV_Tray") or o.name.startswith("PV_Tiles")]


main()
