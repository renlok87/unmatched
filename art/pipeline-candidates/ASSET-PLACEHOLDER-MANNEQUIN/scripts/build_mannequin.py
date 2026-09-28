"""ASSET-PLACEHOLDER-MANNEQUIN: parametric grey fallback figure (D-06, 04 §3.10), built from scratch in Blender.

Headless only (never touches the live Blender sessions :9876/:9877):
  "C:/Program Files/Blender Foundation/Blender 5.2/blender.exe" -b --factory-startup --python-exit-code 1 \
      --python art/pipeline-candidates/ASSET-PLACEHOLDER-MANNEQUIN/scripts/build_mannequin.py -- <profile.json> <run_dir>

What it builds (profile: build-profiles/mannequin-parametric-um-fbx-v1.json, all numbers "предложено"):
  * segmented "artist mannequin" figure: faceted lofts (torso, pelvis, limbs, hands, feet) + oval head; every part
    is a closed shell weighted 100 % to one bone of UM_HUMANOID_17_v1 (armature object SKEL_UM_Humanoid);
  * round base Ø24 x 4 uu with a team band (vertex mask UM_Mask.R = 1), not skinned;
  * static variant SM_PlaceholderMannequin (figure + base, 2 slots) with UCP_ capsule collision (04 §3.10 card);
  * skeletal variant SK_PlaceholderMannequin (armature + figure) + SM_PlaceholderMannequin_Base.
Outputs in run_dir: work/mannequin.blend (scenes Mannequin_Skeletal, Mannequin_Static; metres, face -Y, pivot at the
base bottom centre), export/*.fbx (UM_FBX_v1: +90 deg Z, data x100, FBX_SCALE_UNITS, -Y fwd / Z up, triangulated,
UnitScaleFactor patched to 1.0, byte-deterministic), reports/build-report.json, work/renders/uv_*.png.

UV analysis, FBX determinism and the UnitScaleFactor patch are taken (by AST, unchanged) from
tools/tripo-pipeline/blender/static_prop_candidate.py; its sha256 is recorded. Nothing here is an art decision.
"""

import ast
import datetime
import hashlib
import json
import math
import struct
import sys
from pathlib import Path

import bmesh
import bpy
import numpy as np
from mathutils import Matrix, Vector

if not bpy.app.background:
    raise RuntimeError("build_mannequin.py: headless only (blender -b)")

MARKER = "MANNEQUIN_BUILD_OK"
FIXED_TIME = datetime.datetime(2000, 1, 1, 0, 0, 0)
REPO = Path(__file__).resolve().parents[4]
HELPERS = ("r", "raster_triangles", "island_centre_distances", "uv_raster_metrics", "uv_analysis",
           "PNG_COLOR_CHUNKS", "png_chunks", "strip_png_color_chunks", "save_png", "uv_layout_png",
           "make_fbx_deterministic", "patch_fbx_units")


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def text_sha256_lf(path):
    return hashlib.sha256(Path(path).read_bytes().replace(b"\r\n", b"\n")).hexdigest()


def load_helpers(path):
    """Execute only the named top-level definitions of static_prop_candidate.py (its main() is not run)."""
    tree = ast.parse(Path(path).read_text(encoding="utf-8"))
    keep = []
    for node in tree.body:
        if isinstance(node, ast.FunctionDef) and node.name in HELPERS:
            keep.append(node)
        elif isinstance(node, ast.Assign) and any(getattr(t, "id", None) in HELPERS for t in node.targets):
            keep.append(node)
    ns = {"np": np, "math": math, "bpy": bpy, "Path": Path, "struct": struct, "hashlib": hashlib,
          "datetime": datetime, "FIXED_TIME": FIXED_TIME, "Matrix": Matrix, "Vector": Vector}
    exec(compile(ast.Module(body=keep, type_ignores=[]), str(path), "exec"), ns)
    missing = [h for h in HELPERS if h not in ns]
    if missing:
        raise RuntimeError("helpers missing in %s: %s" % (path, missing))
    return ns


def rel(p):
    try:
        return Path(p).resolve().relative_to(REPO).as_posix()
    except ValueError:
        return Path(p).as_posix()


def rr(v, n=6):
    return round(float(v), n)


def rv(vec, n=6):
    return [rr(c, n) for c in vec]


# ----------------------------------------------------------------------------- geometry
def frame_for(axis):
    w = axis.normalized()
    ref = Vector((1, 0, 0)) if abs(w.x) < 0.9 else Vector((0, 1, 0))
    u = (ref - ref.dot(w) * w).normalized()
    v = w.cross(u).normalized()
    return w, u, v


def add_loft(bm, a, b, rings, sides):
    """Closed tube along a->b; rings [t, ru, rv, (ox, oy, oz)]; radius 0 = pole. Returns the new faces."""
    a, b = Vector(a), Vector(b)
    w, u, v = frame_for(b - a)
    phase = math.pi / sides  # flat faces look along +-u / +-v (front, side, sole)
    loops = []
    for ring in rings:
        t, ru, rvv = ring[0], ring[1], ring[2]
        off = Vector(ring[3:6]) if len(ring) >= 6 else Vector((0, 0, 0))
        c = a + (b - a) * t + off
        if ru == 0 and rvv == 0:
            loops.append([bm.verts.new(c)])
        else:
            loops.append([bm.verts.new(c + u * ru * math.cos(phase + 2 * math.pi * k / sides)
                                       + v * rvv * math.sin(phase + 2 * math.pi * k / sides))
                          for k in range(sides)])
    if len(loops[0]) != 1 or len(loops[-1]) != 1 or any(len(l) == 1 for l in loops[1:-1]):
        raise RuntimeError("loft needs poles exactly at both ends")
    faces = []
    for i in range(len(loops) - 1):
        p, q = loops[i], loops[i + 1]
        for k in range(sides):
            k1 = (k + 1) % sides
            if len(p) == 1:
                faces.append(bm.faces.new((p[0], q[k1], q[k])))
            elif len(q) == 1:
                faces.append(bm.faces.new((p[k], p[k1], q[0])))
            else:
                faces.append(bm.faces.new((p[k], p[k1], q[k1], q[k])))
    return faces


def add_ellipsoid(bm, centre, radii, segments, rings):
    """UV ellipsoid as a loft between the poles (bmesh.ops.create_uvsphere orders faces differently from run to run,
    measured 2026-09-28, so the FBX was not byte-stable)."""
    cx, cy, cz = centre
    rx, ry, rz = radii
    lat = []
    for i in range(rings + 1):
        th = math.pi * i / rings
        lat.append([(1 - math.cos(th)) / 2, rx * math.sin(th) if 0 < i < rings else 0,
                    ry * math.sin(th) if 0 < i < rings else 0])
    return add_loft(bm, (cx, cy, cz - rz), (cx, cy, cz + rz), lat, segments)


def mirror_part(part):
    m = dict(part)
    m["a"] = [-part["a"][0]] + part["a"][1:]
    m["b"] = [-part["b"][0]] + part["b"][1:]
    m["rings"] = [ring[:3] + ([-ring[3]] + ring[4:6] if len(ring) >= 6 else []) for ring in part["rings"]]
    return m


def expand_parts(profile):
    out = []
    for part in profile["parts"]:
        if part.get("mirror"):
            left = dict(part, name=part["name"] + "_L", bone=part["bone"] + ".L")
            right = dict(mirror_part(part), name=part["name"] + "_R", bone=part["bone"] + ".R")
            out += [left, right]
        else:
            out.append(part)
    return out


def orient_outward(bm, faces):
    bmesh.ops.recalc_face_normals(bm, faces=faces)


def build_figure(profile):
    parts = expand_parts(profile)
    bm = bmesh.new()
    part_layer = bm.faces.layers.int.new("um_part")
    info = []
    for index, part in enumerate(parts):
        if part["kind"] == "ellipsoid":
            faces = add_ellipsoid(bm, part["centre"], part["radii"], part["segments"], part["rings"])
        else:
            faces = add_loft(bm, part["a"], part["b"], part["rings"], part["sides"])
        orient_outward(bm, faces)
        for f in faces:
            f[part_layer] = index
            f.smooth = part["shading"] == "smooth"
        info.append({"name": part["name"], "bone": part["bone"], "kind": part["kind"], "shading": part["shading"],
                     "faces": len(faces), "triangles": sum(len(f.verts) - 2 for f in faces)})
    triangulate(bm)  # face data (um_part, smooth) is copied to the split faces
    for e in bm.edges:  # flat parts: sharp everywhere; smooth parts: smooth
        e.smooth = all(f.smooth for f in e.link_faces)
    me = bpy.data.meshes.new("PlaceholderMannequin_Figure")
    bm.to_mesh(me)
    bm.free()
    return me, parts, info


ROLE_IDS = {"bottom": 0, "top": 1, "bevel": 2, "side": 3, "team_band": 4, "team_chamfer": 5}
ROLE_NAMES = {v: k for k, v in ROLE_IDS.items()}
SURFACE = {"bottom": "bottom", "top": "top", "bevel": "bevel", "side": "cylinder", "team_band": "cylinder",
           "team_chamfer": "chamfer"}


def triangulate(bm):
    """Triangulate in the authored mesh (BEAUTY), so the .blend shades exactly like the triangulated FBX
    (UM_FBX_v1 «Triangulate Faces»: non-planar flat quads would otherwise split differently at export)."""
    bmesh.ops.triangulate(bm, faces=list(bm.faces), quad_method="BEAUTY", ngon_method="BEAUTY")


def build_base(profile):
    cfg = profile["base"]
    n = cfg["segments"]
    prof = cfg["profile_rz"]
    team = [tuple(z) for z in cfg["team_between_z"]]
    bm = bmesh.new()
    role_layer = bm.faces.layers.int.new("um_base_role")
    rings = []
    for z, rad in prof:
        rings.append([bm.verts.new((rad * math.cos(2 * math.pi * k / n), rad * math.sin(2 * math.pi * k / n), z))
                      for k in range(n)])
    cb = bm.verts.new((0, 0, prof[0][0]))
    ct = bm.verts.new((0, 0, prof[-1][0]))
    for k in range(n):
        k1 = (k + 1) % n
        bm.faces.new((rings[0][k1], rings[0][k], cb))[role_layer] = ROLE_IDS["bottom"]
        bm.faces.new((rings[-1][k], rings[-1][k1], ct))[role_layer] = ROLE_IDS["top"]
        for i in range(len(rings) - 1):
            z0, z1 = prof[i][0], prof[i + 1][0]
            vertical = abs(prof[i][1] - prof[i + 1][1]) < 1e-9
            is_team = any(abs(z0 - a) < 1e-9 and abs(z1 - c) < 1e-9 for a, c in team)
            kind = ("team_band" if vertical else "team_chamfer") if is_team else ("side" if vertical else "bevel")
            f = bm.faces.new((rings[i][k], rings[i][k1], rings[i + 1][k1], rings[i + 1][k]))
            f[role_layer] = ROLE_IDS[kind]
    orient_outward(bm, list(bm.faces))
    for f in bm.faces:
        f.smooth = ROLE_NAMES[f[role_layer]] in ("side", "team_band", "team_chamfer") and cfg.get("smooth_side", True)
    triangulate(bm)
    for e in bm.edges:  # smooth only inside one surface of revolution (cylinder / chamfer cone)
        fs = e.link_faces
        e.smooth = all(f.smooth for f in fs) and len({SURFACE[ROLE_NAMES[f[role_layer]]] for f in fs}) == 1
    me = bpy.data.meshes.new("PlaceholderMannequin_Base")
    bm.to_mesh(me)
    roles = {}
    for f in bm.faces:
        name = ROLE_NAMES[f[role_layer]]
        roles[name] = roles.get(name, 0) + 1
    band_faces = [f.index for f in bm.faces if ROLE_NAMES[f[role_layer]].startswith("team_")]
    bm.free()
    return me, roles, band_faces


def build_capsule(cfg, name):
    R, (z0, z1), n, k = cfg["radius_m"], cfg["axis_z_m"], cfg["segments"], cfg["hemisphere_rings"]
    bm = bmesh.new()
    loops = [[bm.verts.new((0, 0, z0 - R))]]
    for i in range(1, k + 1):  # lower hemisphere, pole excluded
        phi = -math.pi / 2 + math.pi / 2 * i / k
        loops.append([bm.verts.new((R * math.cos(phi) * math.cos(2 * math.pi * j / n),
                                    R * math.cos(phi) * math.sin(2 * math.pi * j / n), z0 + R * math.sin(phi)))
                      for j in range(n)])
    for i in range(0, k):  # upper hemisphere from the equator
        phi = math.pi / 2 * i / k
        loops.append([bm.verts.new((R * math.cos(phi) * math.cos(2 * math.pi * j / n),
                                    R * math.cos(phi) * math.sin(2 * math.pi * j / n), z1 + R * math.sin(phi)))
                      for j in range(n)])
    loops.append([bm.verts.new((0, 0, z1 + R))])
    for i in range(len(loops) - 1):
        p, q = loops[i], loops[i + 1]
        for j in range(n):
            j1 = (j + 1) % n
            if len(p) == 1:
                bm.faces.new((p[0], q[j1], q[j]))
            elif len(q) == 1:
                bm.faces.new((p[j], p[j1], q[0]))
            else:
                bm.faces.new((p[j], p[j1], q[j1], q[j]))
    orient_outward(bm, list(bm.faces))
    triangulate(bm)
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    return me


def set_mask(me, values_per_face):
    attr = me.color_attributes.new(name="UM_Mask", type="BYTE_COLOR", domain="CORNER")
    cols = np.zeros((len(me.loops), 4), dtype=np.float32)
    for p in me.polygons:
        c = values_per_face(p.index)
        for li in p.loop_indices:
            cols[li] = c
    attr.data.foreach_set("color", cols.ravel())
    me.color_attributes.active_color = attr
    me.color_attributes.render_color_index = me.color_attributes.find("UM_Mask")
    return attr


# ----------------------------------------------------------------------------- materials (Blender preview)
def srgb_hex_to_linear(hexstr):
    out = []
    for i in (1, 3, 5):
        c = int(hexstr[i:i + 2], 16) / 255.0
        out.append(c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4)
    return out


def figure_material(cfg):
    mat = bpy.data.materials.new(cfg["name"])
    mat.use_nodes = True
    bsdf = next(n for n in mat.node_tree.nodes if n.type == "BSDF_PRINCIPLED")
    lin = srgb_hex_to_linear(cfg["base_color_srgb_hex"])
    bsdf.inputs["Base Color"].default_value = (*lin, 1.0)
    bsdf.inputs["Roughness"].default_value = cfg["roughness"]
    bsdf.inputs["Metallic"].default_value = cfg["metallic"]
    mat.diffuse_color = (*lin, 1.0)
    mat.use_backface_culling = True
    return mat, lin


def base_material(cfg):
    """Preview of the UE rule BaseColor = lerp(base_color, TeamColor, UM_Mask.R); TeamColor = object prop um_team_color."""
    mat = bpy.data.materials.new(cfg["name"])
    mat.use_nodes = True
    nt = mat.node_tree
    bsdf = next(n for n in nt.nodes if n.type == "BSDF_PRINCIPLED")
    bsdf.inputs["Roughness"].default_value = cfg["roughness"]
    bsdf.inputs["Metallic"].default_value = cfg["metallic"]
    vc = nt.nodes.new("ShaderNodeVertexColor")
    vc.layer_name = "UM_Mask"
    sep = nt.nodes.new("ShaderNodeSeparateColor")
    nt.links.new(vc.outputs["Color"], sep.inputs["Color"])
    team = nt.nodes.new("ShaderNodeAttribute")
    team.attribute_type = "OBJECT"
    team.attribute_name = "um_team_color"
    mix = nt.nodes.new("ShaderNodeMix")
    mix.data_type = "RGBA"
    ins = [s for s in mix.inputs if s.type == "RGBA"]
    ins[0].default_value = (*cfg["base_color_linear"], 1.0)
    nt.links.new(team.outputs["Color"], ins[1])
    fac = next(s for s in mix.inputs if s.type == "VALUE")
    nt.links.new(sep.outputs["Red"], fac)
    out = next(s for s in mix.outputs if s.type == "RGBA")
    nt.links.new(out, bsdf.inputs["Base Color"])
    mat.diffuse_color = (*cfg["base_color_linear"], 1.0)
    mat.use_backface_culling = True
    return mat


# ----------------------------------------------------------------------------- scene helpers
def link(scene, obj):
    scene.collection.objects.link(obj)
    return obj


def smart_uv(obj, angle_deg, margin):
    bpy.ops.object.select_all(action="DESELECT")
    bpy.context.view_layer.objects.active = obj
    obj.select_set(True)
    bpy.ops.object.mode_set(mode="EDIT")
    bpy.ops.mesh.select_all(action="SELECT")
    bpy.ops.uv.smart_project(angle_limit=math.radians(angle_deg), island_margin=margin)
    bpy.ops.object.mode_set(mode="OBJECT")
    obj.select_set(False)


def build_armature(scene, profile):
    arm_cfg = profile["armature"]
    data = bpy.data.armatures.new(arm_cfg["object"])
    arm = link(scene, bpy.data.objects.new(arm_cfg["object"], data))
    bpy.ops.object.select_all(action="DESELECT")
    bpy.context.view_layer.objects.active = arm
    arm.select_set(True)
    bpy.ops.object.mode_set(mode="EDIT")
    for name, parent, head, tail in arm_cfg["bones"]:
        eb = data.edit_bones.new(name)
        eb.head, eb.tail, eb.roll = head, tail, arm_cfg["roll"]
        eb.use_connect = arm_cfg["use_connect"]
        if parent:
            eb.parent = data.edit_bones[parent]
    bpy.ops.object.mode_set(mode="OBJECT")
    arm.select_set(False)
    for pb in arm.pose.bones:
        pb.rotation_mode = "XYZ"
    return arm


def mesh_topology(obj):
    """Per-shell diagnostics (faces grouped by um_part if present, else by connectivity)."""
    bm = bmesh.new()
    bm.from_mesh(obj.data)
    bm.faces.ensure_lookup_table()
    before = {f.index: f.normal.copy() for f in bm.faces}
    shells, seen = [], set()
    for f in bm.faces:
        if f.index in seen:
            continue
        stack, shell = [f], []
        seen.add(f.index)
        while stack:
            cur = stack.pop()
            shell.append(cur)
            for e in cur.edges:
                for nf in e.link_faces:
                    if nf.index not in seen:
                        seen.add(nf.index)
                        stack.append(nf)
        shells.append(shell)
    boundary = sum(1 for e in bm.edges if e.is_boundary)
    non_manifold = sum(1 for e in bm.edges if not e.is_manifold and not e.is_boundary)
    degenerate = sum(1 for f in bm.faces if f.calc_area() < 1e-10)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    inconsistent = sum(1 for f in bm.faces if before[f.index].dot(f.normal) < 0)
    vols = []
    for shell in shells:
        v = 0.0
        for f in shell:
            vs = [x.co for x in f.verts]
            for i in range(1, len(vs) - 1):
                v += vs[0].dot(vs[i].cross(vs[i + 1])) / 6.0
        vols.append(v)
    bm.free()
    return {"shells": len(shells), "boundary_edges": boundary, "non_manifold_edges": non_manifold,
            "degenerate_faces_area_lt_1e-10_m2": degenerate, "faces_with_inconsistent_winding": inconsistent,
            "shell_signed_volumes_m3_min": rr(min(vols), 9), "shells_with_non_positive_volume": sum(1 for v in vols if v <= 0),
            "total_volume_m3": rr(sum(vols), 9)}


def tris(obj):
    return sum(len(p.vertices) - 2 for p in obj.data.polygons)


def bounds(objs):
    pts = [o.matrix_world @ v.co for o in objs for v in o.data.vertices]
    lo = Vector((min(p.x for p in pts), min(p.y for p in pts), min(p.z for p in pts)))
    hi = Vector((max(p.x for p in pts), max(p.y for p in pts), max(p.z for p in pts)))
    return lo, hi


def seg_distance(p, a, b):
    ab = b - a
    t = max(0.0, min(1.0, (p - a).dot(ab) / max(ab.length_squared, 1e-12)))
    return (p - (a + ab * t)).length


class Checks(dict):
    def __call__(self, name, passed, measured=None, expected=None, note=None):
        item = {"passed": bool(passed), "measured": measured}
        if expected is not None:
            item["expected"] = expected
        if note:
            item["note"] = note
        self[name] = item

    def failed(self):
        return sorted(k for k, v in self.items() if not v["passed"])


# ----------------------------------------------------------------------------- export
def fbx_kwargs(preset, object_types):
    return dict(use_selection=True, object_types=object_types,
                apply_unit_scale=bool(preset["apply_unit_scale"]), apply_scale_options=preset["apply_scale_options"],
                bake_space_transform=False, axis_forward=preset["axis_forward"], axis_up=preset["axis_up"],
                use_triangles=bool(preset["use_triangles"]), mesh_smooth_type=preset["mesh_smooth_type"],
                use_mesh_edges=False, use_custom_props=False, add_leaf_bones=bool(preset["add_leaf_bones"]),
                primary_bone_axis=preset["primary_bone_axis"], secondary_bone_axis=preset["secondary_bone_axis"],
                bake_anim=False, path_mode=preset["path_mode"], embed_textures=False, colors_type="SRGB")


def set_window_scene(scene):
    """Background Blender may still have a window; its scene drives selection lookups (see core.scene_context)."""
    wm = bpy.context.window_manager
    window = bpy.context.window or (wm.windows[0] if wm.windows else None)
    if window is not None:
        window.scene = scene


def export_one(H, scene, path, objects, active, object_types, preset):
    set_window_scene(scene)
    with bpy.context.temp_override(scene=scene, view_layer=scene.view_layers[0]):
        for o in scene.objects:
            o.select_set(False)
        for o in objects:
            o.select_set(True)
        scene.view_layers[0].objects.active = active
        restore = H["make_fbx_deterministic"]()
        try:
            bpy.ops.export_scene.fbx(filepath=str(path), **fbx_kwargs(preset, object_types))
        finally:
            restore()
    H["patch_fbx_units"](path, float(preset["patch_fbx_unit_scale_to"]))


def to_export_space(scene, arm, meshes, matrix):
    """UM_FBX_v1 export space on the in-memory scene (not saved): rigid rest-pose rotation + x100 (see core.py)."""
    if arm is not None:
        with bpy.context.temp_override(scene=scene, view_layer=scene.view_layers[0]):
            for o in scene.objects:
                o.select_set(False)
            scene.view_layers[0].objects.active = arm
            arm.select_set(True)
            bpy.ops.object.mode_set(mode="EDIT")
            for eb in arm.data.edit_bones:
                eb.transform(matrix, scale=False, roll=True)
            bpy.ops.object.mode_set(mode="OBJECT")
            arm.select_set(False)
    for m in meshes:
        m.data.transform(matrix)
        m.data.update()


# ----------------------------------------------------------------------------- main
def main():
    argv = sys.argv[sys.argv.index("--") + 1:]
    profile_path, run_dir = Path(argv[0]).resolve(), Path(argv[1]).resolve()
    profile = json.loads(profile_path.read_text(encoding="utf-8"))
    preset_path = REPO / profile["fbx_preset"]
    preset = json.loads(preset_path.read_text(encoding="utf-8"))
    contract_path = REPO / profile["rig_contract"]
    contract = json.loads(contract_path.read_text(encoding="utf-8"))
    helpers_path = REPO / profile["uv_helpers_from"]
    H = load_helpers(helpers_path)
    for sub in ("work", "work/renders", "export", "reports"):
        (run_dir / sub).mkdir(parents=True, exist_ok=True)

    bpy.ops.wm.read_factory_settings(use_empty=True)
    sk_scene = bpy.context.scene
    sk_scene.name = "Mannequin_Skeletal"
    for sc in (sk_scene,):
        sc.unit_settings.system = "METRIC"
        sc.unit_settings.scale_length = 1.0
    st_scene = bpy.data.scenes.new("Mannequin_Static")
    st_scene.unit_settings.system = "METRIC"
    st_scene.unit_settings.scale_length = 1.0
    checks = Checks()

    # --- materials
    fig_mat, fig_lin = figure_material(profile["materials"]["figure"])
    base_mat = base_material(profile["materials"]["base"])
    gold = profile["materials"]["base"]["team_colors_linear"]["gold"]

    # --- figure (skeletal body)
    fig_me, parts, part_info = build_figure(profile)
    fig_me.name = profile["variants"]["skeletal"]["object"]
    fig_me.materials.append(fig_mat)
    body = link(sk_scene, bpy.data.objects.new(profile["variants"]["skeletal"]["object"], fig_me))
    set_mask(fig_me, lambda i: profile["mask"]["figure_values"])

    # --- base
    base_me, base_roles, band_faces = build_base(profile)
    base_me.name = profile["variants"]["skeletal"]["base_object"]
    base_me.materials.append(base_mat)
    band = set(band_faces)
    set_mask(base_me, lambda i: (1, 0, 0, 1) if i in band else (0, 0, 0, 1))
    base = link(sk_scene, bpy.data.objects.new(profile["variants"]["skeletal"]["base_object"], base_me))
    base["um_team_color"] = gold

    # --- UV0 (Smart UV Project) per mesh, then the static copy inherits both
    ucfg = profile["uv"]
    with bpy.context.temp_override(scene=sk_scene, view_layer=sk_scene.view_layers[0]):
        for o in (body, base):
            smart_uv(o, 66.0, 0.02)

    # --- armature + rigid weights
    arm = build_armature(sk_scene, profile)
    part_layer = fig_me.attributes["um_part"].data
    groups = {}
    for bone in arm.data.bones:
        groups[bone.name] = body.vertex_groups.new(name=bone.name)
    vert_bone = {}
    for poly in fig_me.polygons:
        bone = parts[part_layer[poly.index].value]["bone"]
        for vi in poly.vertices:
            prev = vert_bone.setdefault(vi, bone)
            if prev != bone:
                raise RuntimeError("vertex %d shared by parts of %s and %s" % (vi, prev, bone))
    by_bone = {}
    for vi, bone in vert_bone.items():
        by_bone.setdefault(bone, []).append(vi)
    for bone, idx in by_bone.items():
        groups[bone].add(sorted(idx), 1.0, "REPLACE")
    body.parent = arm
    mod = body.modifiers.new("Armature", "ARMATURE")
    mod.object = arm

    # --- static variant: figure + base joined (2 slots) + UCP capsule, in its own scene
    st_body = bpy.data.objects.new(profile["variants"]["static"]["object"], fig_me.copy())
    st_body.data.name = profile["variants"]["static"]["object"]
    st_base = bpy.data.objects.new("static_base_tmp", base_me.copy())
    link(st_scene, st_body)
    link(st_scene, st_base)
    with bpy.context.temp_override(scene=st_scene, view_layer=st_scene.view_layers[0],
                                   active_object=st_body, selected_editable_objects=[st_body, st_base],
                                   selected_objects=[st_body, st_base]):
        bpy.ops.object.join()
    st_body.vertex_groups.clear()
    if "um_part" in st_body.data.attributes:
        st_body.data.attributes.remove(st_body.data.attributes["um_part"])
    st_body["um_team_color"] = gold
    ucp = link(st_scene, bpy.data.objects.new(profile["variants"]["static"]["collision_object"],
                                              build_capsule(profile["collision"], profile["variants"]["static"]["collision_object"])))
    ucp.display_type = "WIRE"
    ucp.hide_render = True

    bpy.context.view_layer.update()
    for sc in (sk_scene, st_scene):
        sc.view_layers[0].update()

    # ------------------------------------------------------------------ measurements / checks
    rep = {"asset_id": profile["asset_id"], "status": "измерено", "blender": bpy.app.version_string,
           "profile": {"path": rel(profile_path), "sha256_lf": text_sha256_lf(profile_path), "id": profile["profile_id"]},
           "builder": {"path": rel(Path(__file__)), "sha256_lf": text_sha256_lf(Path(__file__))},
           "helpers": {"path": rel(helpers_path), "sha256_lf": text_sha256_lf(helpers_path), "functions": list(HELPERS)},
           "fbx_preset": {"path": rel(preset_path), "sha256": sha256(preset_path), "name": preset["name"],
                          "version": preset.get("version")},
           "rig_contract": {"path": rel(contract_path), "sha256_lf": text_sha256_lf(contract_path)},
           "reference_image": profile["reference_image"]}

    ref = REPO / profile["reference_image"]["path"]
    checks("reference_image_sha256", ref.is_file() and sha256(ref) == profile["reference_image"]["sha256"],
           sha256(ref) if ref.is_file() else "missing", profile["reference_image"]["sha256"],
           "shape reference only (registry sourceImages.recommended); not read by the build")
    # units / transforms
    checks("scene_units_metric_1", all(sc.unit_settings.system == "METRIC" and sc.unit_settings.scale_length == 1.0
                                       for sc in (sk_scene, st_scene)), "METRIC / 1.0")
    ident = all(all(abs(a - b) < 1e-12 for ra, rb in zip(o.matrix_world, Matrix.Identity(4)) for a, b in zip(ra, rb))
                for o in (arm, body, base, st_body, ucp))
    checks("object_transforms_identity", ident, ident, True, "04 §1: transforms applied; armature at the origin")
    # triangles
    t_body, t_base, t_static, t_ucp = tris(body), tris(base), tris(st_body), tris(ucp)
    rep["triangles"] = {"figure": t_body, "base": t_base, "static_total": t_static, "collision_ucp": t_ucp,
                        "parts": part_info, "base_faces_by_role": base_roles}
    checks("triangles_in_proposed_1k_3k", 1000 <= t_static <= 3000, t_static, "1000-3000 (04 §3.10, proposal)")
    checks("static_equals_figure_plus_base", t_static == t_body + t_base, [t_static, t_body + t_base])
    # bounds / pivot / height
    lo, hi = bounds([st_body])
    flo, fhi = bounds([body])
    blo, bhi = bounds([base])
    rep["bounds_m"] = {"static": {"min": rv(lo), "max": rv(hi)}, "figure": {"min": rv(flo), "max": rv(fhi)},
                       "base": {"min": rv(blo), "max": rv(bhi)}}
    rep["dimensions_uu"] = {"static": rv((hi - lo) * 100, 3), "figure": rv((fhi - flo) * 100, 3),
                            "base": rv((bhi - blo) * 100, 3)}
    checks("total_height_50uu", abs(hi.z - profile["scale"]["total_height_m"]) < 1e-4 and abs(lo.z) < 1e-9,
           rr(hi.z * 100, 3), "50 ±0.01 uu, min Z = 0 (QA-009 test figure 50 ±2)")
    checks("pivot_base_bottom_centre", abs(blo.z) < 1e-9 and abs(blo.x + bhi.x) < 1e-6 and abs(blo.y + bhi.y) < 1e-6,
           {"base_min": rv(blo), "base_max": rv(bhi)}, "min Z = 0, XY centred")
    checks("figure_inside_base_footprint_xy", max(abs(flo.x), abs(fhi.x), abs(flo.y), abs(fhi.y)) < bhi.x,
           rr(max(abs(flo.x), abs(fhi.x), abs(flo.y), abs(fhi.y)) * 100, 3), "< base radius %.1f uu" % (bhi.x * 100))
    base_top = profile["base"]["profile_rz"][-1][0]
    sole = flo.z
    checks("feet_touch_base_top", base_top - 0.0015 <= sole < base_top, rr(sole * 100, 3),
           "sole 0-1.5 mm inside the base top %.2f uu (no floating)" % (base_top * 100))
    # head proportion
    head_part = next(p for p in parts if p["name"] == "Head")
    head_h = 2 * head_part["radii"][2]
    rep["proportions"] = {"figure_height_m": rr(fhi.z - flo.z), "head_height_m": rr(head_h),
                          "heads_per_figure": rr((fhi.z - flo.z) / head_h, 2), "03_C1": "5-6 heads (stylised)"}
    checks("heads_5_to_6", 5.0 <= (fhi.z - flo.z) / head_h <= 6.0, rr((fhi.z - flo.z) / head_h, 2), "5-6 (03 С-1)")
    # topology
    topo = {"figure": mesh_topology(body), "base": mesh_topology(base), "static": mesh_topology(st_body),
            "collision": mesh_topology(ucp)}
    rep["topology"] = topo
    for key, t in topo.items():
        ok = (t["boundary_edges"] == 0 and t["non_manifold_edges"] == 0 and t["faces_with_inconsistent_winding"] == 0
              and t["shells_with_non_positive_volume"] == 0 and t["degenerate_faces_area_lt_1e-10_m2"] == 0)
        checks("closed_outward_%s" % key, ok, t, "every shell closed, manifold, outward (volume > 0), no slivers")
    checks("figure_shells_equal_parts", topo["figure"]["shells"] == len(parts), [topo["figure"]["shells"], len(parts)])
    # normals / shading
    flat_faces = sum(1 for p in fig_me.polygons if not p.use_smooth)
    rep["shading"] = {"figure_flat_faces": flat_faces, "figure_smooth_faces": len(fig_me.polygons) - flat_faces,
                      "base_smooth_faces": sum(1 for p in base_me.polygons if p.use_smooth),
                      "rule": "faceted lofts flat (reference look), head and the base side smooth; sharp edges where a "
                              "flat face meets another face; FBX mesh_smooth_type FACE"}
    # materials
    rep["materials"] = {"figure_slots": [m.name for m in fig_me.materials], "base_slots": [m.name for m in base_me.materials],
                        "static_slots": [m.name for m in st_body.data.materials],
                        "figure_base_color_linear": rv(fig_lin, 4), "figure_base_color_srgb": profile["materials"]["figure"]["base_color_srgb_hex"],
                        "base_rule": profile["materials"]["base"]["team_color_rule"], "textures": "none (04 §3.10)"}
    checks("material_slots_le_3", len(st_body.data.materials) <= 3 and len(fig_me.materials) == 1 and len(base_me.materials) == 1,
           rep["materials"]["static_slots"], "static 2, SK 1, base 1 (04 §1: ≤ 3)")
    mi = [p.material_index for p in st_body.data.polygons]
    checks("static_slot_split", mi.count(0) == len(fig_me.polygons) and mi.count(1) == len(base_me.polygons),
           {"slot0": mi.count(0), "slot1": mi.count(1)})
    # mask
    def mask_stats(me):
        a = me.color_attributes["UM_Mask"]
        c = np.zeros(len(a.data) * 4, dtype=np.float32)
        a.data.foreach_get("color", c)
        c = c.reshape(-1, 4)
        binary = bool(np.all((np.abs(c) < 1e-6) | (np.abs(c - 1) < 1e-6)))
        return {"domain": a.domain, "type": a.data_type, "binary": binary,
                "corners_R1": int((c[:, 0] > 0.5).sum()), "corners_G1": int((c[:, 1] > 0.5).sum()),
                "corners_B1": int((c[:, 2] > 0.5).sum()), "corners_A1": int((c[:, 3] > 0.5).sum()), "corners": len(c)}
    ms = {"figure": mask_stats(fig_me), "base": mask_stats(base_me), "static": mask_stats(st_body.data)}
    rep["mask"] = ms
    band_corners = sum(len(base_me.polygons[i].loop_indices) for i in band_faces)
    checks("mask_binary_everywhere", all(v["binary"] for v in ms.values()), [v["binary"] for v in ms.values()])
    checks("mask_R_only_on_base_band", ms["figure"]["corners_R1"] == 0 and ms["base"]["corners_R1"] == band_corners
           and ms["static"]["corners_R1"] == band_corners and all(v["corners_G1"] == 0 and v["corners_B1"] == 0 for v in ms.values()),
           {"figure_R": ms["figure"]["corners_R1"], "base_R": ms["base"]["corners_R1"], "band_corners": band_corners})
    rep["mask"]["team_z_ranges_uu"] = [[rr(a * 100, 3), rr(c * 100, 3)] for a, c in profile["base"]["team_between_z"]]
    rep["mask"]["team_faces"] = len(band_faces)
    # UV
    size = ucfg["raster_px"]
    uv_fig, tuv_fig = H["uv_analysis"](body, size)
    uv_base, tuv_base = H["uv_analysis"](base, size)
    rep["uv"] = {"method": ucfg["method"], "figure": uv_fig, "base": uv_base,
                 "static_note": "SM_PlaceholderMannequin keeps both UV sets unchanged in two material slots (separate texture spaces)"}
    for key, u in (("figure", uv_fig), ("base", uv_base)):
        ok = (u["uv_layers"] == ["UVMap"] and u["triangles_out_of_0_1"] == 0 and u["overlap_pixels_between_islands"] == 0
              and u["overlap_pixels_inside_islands_strict"] == 0 and u["flipped_uv_triangles_vs_island_majority"] == 0
              and u["zero_area_uv_triangles"] == 0)
        checks("uv0_clean_%s" % key, ok, {k: u[k] for k in ("uv_layers", "islands", "triangles_out_of_0_1",
                                                           "overlap_pixels_between_islands", "overlap_pixels_inside_islands_strict",
                                                           "flipped_uv_triangles_vs_island_majority", "min_gutter_px_estimate")},
               "one UV0, inside 0-1, no overlaps/flips at %d px" % size)
        checks("uv_gutter_ge_4px_%s" % key, (u["min_gutter_px_estimate"] or 99) >= 4, u["min_gutter_px_estimate"], ">= 4 px at 1K")
    checks("uv_same_on_static", len(st_body.data.uv_layers) == 1, [l.name for l in st_body.data.uv_layers])
    grey = np.full((size, size, 3), 0.18, dtype=np.float32)
    H["uv_layout_png"](tuv_fig, grey, size, run_dir / "work" / "renders" / "uv0_figure.png")
    H["uv_layout_png"](tuv_base, grey, size, run_dir / "work" / "renders" / "uv0_base.png")
    # armature vs contract
    sk = contract["skeletons"][profile["armature"]["skeleton"]]
    want = {b["name"]: b["parent"] for b in sk["bones"]}
    have = {b.name: (b.parent.name if b.parent else None) for b in arm.data.bones}
    checks("armature_object_name", arm.name == sk["armature_object"]["name"], arm.name, sk["armature_object"]["name"])
    checks("bones_match_contract", have == want, {"count": len(have), "diff": sorted(set(have.items()) ^ set(want.items()))},
           "17 names and parents of %s" % profile["armature"]["skeleton"])
    rep["armature"] = {"object": arm.name, "bones": len(arm.data.bones),
                       "heads_m": {b.name: rv(b.head_local) for b in arm.data.bones},
                       "tails_m": {b.name: rv(b.tail_local) for b in arm.data.bones},
                       "weapon_parent": have.get("weapon"), "weapon_note": profile["armature"]["weapon_note"]}
    # weights
    infl, total = [], []
    for v in fig_me.vertices:
        ws = [g.weight for g in v.groups if g.weight > 0]
        infl.append(len(ws))
        total.append(sum(ws))
    share = {}
    for bone, idx in sorted(by_bone.items()):
        share[bone] = rr(len(idx) / len(fig_me.vertices), 4)
    rep["weights"] = {"method": profile["weights"]["method"], "max_influences": max(infl), "unweighted_vertices": infl.count(0),
                      "vertex_share_by_bone": share, "unweighted_bones": sorted(set(have) - set(by_bone))}
    checks("weights_rigid_normalised", max(infl) == 1 and min(infl) == 1 and all(abs(t - 1) < 1e-6 for t in total),
           {"max_influences": max(infl), "min_influences": min(infl)}, "exactly 1 influence of 1.0 per vertex (≤ 4 contract)")
    checks("weights_only_contract_bones", set(by_bone) <= set(want), sorted(by_bone))
    # every part sits on its bone (sanity: L/R and chain not swapped)
    bone_seg = {b.name: (b.head_local, b.tail_local) for b in arm.data.bones}
    part_dist = {}
    for idx_part, part in enumerate(parts):
        vs = sorted({vi for p in fig_me.polygons if part_layer[p.index].value == idx_part for vi in p.vertices})
        c = sum((fig_me.vertices[i].co for i in vs), Vector()) / len(vs)
        a, b = bone_seg[part["bone"]]
        part_dist[part["name"]] = {"bone": part["bone"], "centroid_m": rv(c, 4), "dist_to_bone_m": rr(seg_distance(c, a, b), 4),
                                   "side_x_sign": 0 if abs(c.x) < 1e-6 else (1 if c.x > 0 else -1)}
    rep["parts_on_bones"] = part_dist
    side_ok = all((d["side_x_sign"] == 1) == d["bone"].endswith(".L") for d in part_dist.values()
                  if d["bone"].endswith((".L", ".R")))
    checks("parts_on_their_bones", all(d["dist_to_bone_m"] < 0.02 for d in part_dist.values()) and side_ok,
           {k: v["dist_to_bone_m"] for k, v in part_dist.items()}, "centroid within 2 cm of its bone; .L parts at +X")
    # collision encloses everything
    R = profile["collision"]["radius_m"]
    z0, z1 = profile["collision"]["axis_z_m"]
    worst = 0.0
    for v in st_body.data.vertices:
        p = v.co
        worst = max(worst, seg_distance(p, Vector((0, 0, z0)), Vector((0, 0, z1))) - R)
    clo, chi = bounds([ucp])
    rep["collision"] = {"object": ucp.name, "kind": profile["collision"]["kind"], "radius_uu": R * 100,
                        "bounds_uu": {"min": rv(clo * 100, 3), "max": rv(chi * 100, 3)},
                        "max_vertex_outside_uu": rr(worst * 100, 4), "note": profile["collision"]["note"],
                        "skeletal_note": "SK variant: selection collision comes from the UE Physics Asset or the actor capsule, "
                                         "not from the FBX (as for the hero candidates)"}
    checks("ucp_encloses_static_mesh", worst <= 1e-6, rr(worst * 100, 4),
           "<= 0.0001 uu outside the analytic capsule (float32 vertex precision); the 16-gon facets lie up to "
           "R(1 - cos 11.25 deg) = %.2f uu inside it, UE fits an analytic capsule to the UCP_ vertices" % (R * 100 * (1 - math.cos(math.pi / 16))))
    checks("ucp_name_convention", ucp.name == "UCP_" + st_body.name + "_00", ucp.name)

    # ------------------------------------------------------------------ save the authored .blend (before export space)
    blend_path = run_dir / "work" / "mannequin.blend"
    set_window_scene(sk_scene)
    bpy.context.preferences.filepaths.save_version = 0  # no mannequin.blend1 backups in the run directory
    bpy.ops.wm.save_as_mainfile(filepath=str(blend_path), compress=False)
    rep["blend"] = {"path": rel(blend_path), "scenes": [s.name for s in bpy.data.scenes],
                    "note": "authored frame: metres, face -Y, .L = +X, pivot at the base bottom centre"}

    # ------------------------------------------------------------------ export (in-memory export space, not saved)
    rot = Matrix.Rotation(math.radians(float(preset["export_space_rotation_z_degrees"])), 4, "Z")
    for i in range(4):
        for j in range(4):
            if abs(rot[i][j] - round(rot[i][j])) < 1e-9:
                rot[i][j] = float(round(rot[i][j]))
    M = Matrix.Scale(float(preset["temporary_data_scale"]), 4) @ rot
    to_export_space(sk_scene, arm, (body, base), M)
    to_export_space(st_scene, None, (st_body, ucp), M)
    names = profile["variants"]
    exports = [
        ("skeletal", run_dir / "export" / names["skeletal"]["fbx"], sk_scene, (arm, body), arm, {"ARMATURE", "MESH"}),
        ("skeletal_base", run_dir / "export" / names["skeletal"]["base_fbx"], sk_scene, (base,), base, {"MESH"}),
        ("static", run_dir / "export" / names["static"]["fbx"], st_scene, (st_body, ucp), st_body, {"MESH"}),
    ]
    rep["exports"] = {"settings": {k: v for k, v in fbx_kwargs(preset, {"MESH"}).items() if k != "object_types"},
                      "export_space_rotation_z_degrees": float(preset["export_space_rotation_z_degrees"]),
                      "data_scale": float(preset["temporary_data_scale"]),
                      "unit_scale_factor_after_patch": float(preset["patch_fbx_unit_scale_to"]),
                      "bone_rotation": "EditBone.transform(roll=True): rest pose rotated rigidly (as candidate_build/core.py)",
                      "deviations_from_preset": {
                          "bake_anim": "False: skeletal mesh only, no clips in this stage (04 §1.1 bakes clips)",
                          "colors_type": "SRGB passed explicitly (Blender default); UM_Mask values are 0/1"},
                      "files": {}}
    rep["exports"]["settings"]["object_types"] = "ARMATURE+MESH for SK, MESH for the base and the static mesh"
    for key, path, scene, objs, active, types in exports:
        export_one(H, scene, path, objs, active, types, preset)
        rep["exports"]["files"][key] = {"file": rel(path), "bytes": path.stat().st_size, "sha256": sha256(path),
                                        "objects": [o.name for o in objs]}
    checks("fbx_written", all(Path(REPO / f["file"]).stat().st_size > 0 for f in rep["exports"]["files"].values()),
           {k: v["bytes"] for k, v in rep["exports"]["files"].items()})
    # USF patched
    usf = {}
    for key, f in rep["exports"]["files"].items():
        data = (REPO / f["file"]).read_bytes()
        s = data.find(b"UnitScaleFactor")
        tok = data.find(b"Number", data.find(b"double", s))
        ln = struct.unpack_from("<I", data, tok - 4)[0]
        off = tok + ln
        off += 1 + 4 + struct.unpack_from("<I", data, off + 1)[0]
        usf[key] = struct.unpack_from("<d", data, off + 1)[0]
    checks("unit_scale_factor_1", all(abs(v - 1.0) < 1e-12 for v in usf.values()), usf)

    rep["checks"] = checks
    rep["checks_failed"] = checks.failed()
    rep["checks_passed_count"] = sum(1 for c in checks.values() if c["passed"])
    rep["checks_total"] = len(checks)
    rep["not_claimed"] = ["art acceptance", "UE import", "clips", "QA-012 in the game (fallback wiring, Warning log)",
                          "final size (Q-312 / GD-058)", "static vs skeletal decision"]
    out = run_dir / "reports" / "build-report.json"
    out.write_text(json.dumps(rep, indent=1, ensure_ascii=False, sort_keys=False) + "\n", encoding="utf-8")
    print(MARKER, "checks %d/%d" % (rep["checks_passed_count"], rep["checks_total"]), "failed", rep["checks_failed"],
          "tris static %d figure %d base %d" % (t_static, t_body, t_base))
    if rep["checks_failed"]:
        raise SystemExit(1)


main()
