"""ENV-MAPS lane K: shared Blender-side helpers for the Blender-made environment assets (no Tripo).

Imported by the build / preview scripts of
  ASSET-TABLE-BASE-001 T2b (tray_t2b_build.py), ASSET-MAP-FRAME-002, ASSET-ENV-M-BACKWALL-001,
  ASSET-ENV-S-WATERFALL-001
inside a fresh headless `blender -b --factory-startup` (never a running Blender GUI / MCP session; CPU only).

Authoring frame. Geometry is authored in UE numbers (X, Y, Z in uu of the UE local / board-actor frame), treated as a
right-handed math frame: a face is listed counter-clockwise seen from outside (outward normal by the right-hand rule).
UM_FBX_v1 (blender/_tools/presets/UM_FBX_v1.json, +90 deg Z, x100, UnitScaleFactor 1.0) maps UE X = -blend y,
UE Y = -blend x, which is a mirror: MeshBuilder.to_object() converts every vertex (x, y, z) -> blend (-y, -x, z) and
reverses every face (and its per-corner data), so the Blender mesh has outward normals and the FBX lands in UE with the
authored numbers (the read-back frame of check_static_prop_fbx.py = UE with Y negated).

Every FBX helper comes from tools/tripo-pipeline/blender/static_prop_candidate.py (executed without its trailing main(),
as tray_t2_build.py and env_kit_build.py do): export_fbx (deterministic bytes), fbx_kwargs, um_fbx_v1_conformance.

Vertex colours: one FLOAT_COLOR corner attribute 'Col'. The FBX exporter's default colors_type 'SRGB' writes
linear_to_srgb(value), so MeshBuilder stores srgb_to_linear(mask): the FBX (and so the UE FColor / VertexColor node,
which reads the FBX value without a gamma step) carries the mask value itself. The read-back reports the file values.
"""

import json
import math
import sys
import types
from pathlib import Path

import bmesh
import bpy
import numpy as np
from mathutils import Matrix, Vector

HERE = Path(__file__).resolve()
REPO = HERE.parents[3]  # <repo>/tools/art/env_kit/<this file>
SPC_PATH = REPO / "tools" / "tripo-pipeline" / "blender" / "static_prop_candidate.py"
PRESET_PATH = REPO / "blender" / "_tools" / "presets" / "UM_FBX_v1.json"


def load_spc():
    body = SPC_PATH.read_text(encoding="utf-8").rstrip()
    if not body.endswith("\nmain()"):
        raise SystemExit("static_prop_candidate.py no longer ends with a bare main() call: %s" % SPC_PATH)
    ns = {"__name__": "static_prop_candidate_helpers", "__file__": str(SPC_PATH)}
    exec(compile(body[:-len("main()")], str(SPC_PATH), "exec"), ns)
    return types.SimpleNamespace(**ns)


S = load_spc()
r = S.r


def rel(p):
    try:
        return Path(p).resolve().relative_to(REPO).as_posix()
    except ValueError:
        return Path(p).as_posix()


def script_args():
    return sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []


def load_params(path):
    pp = Path(path).resolve()
    P = json.loads(pp.read_text(encoding="utf-8"))
    P["_params_path"] = pp
    P["_run"] = (REPO / P["run_dir"]).resolve()
    P["_scratch"] = Path(P["scratch_dir"]).resolve()
    for sub in ("export", "reports", "preview"):
        (P["_run"] / sub).mkdir(parents=True, exist_ok=True)
    (P["_scratch"] / "work").mkdir(parents=True, exist_ok=True)
    return P


def preset():
    return json.loads(PRESET_PATH.read_text(encoding="utf-8"))


def srgb_to_linear(c):
    c = np.asarray(c, dtype=np.float64)
    return np.where(c <= 0.04045, c / 12.92, ((c + 0.055) / 1.055) ** 2.4)


def linear_to_srgb(c):
    c = np.clip(np.asarray(c, dtype=np.float64), 0.0, None)
    return np.where(c <= 0.0031308, c * 12.92, 1.055 * c ** (1.0 / 2.4) - 0.055)


# ----------------------------------------------------------------------------- mesh building (UE numbers)
class MeshBuilder:
    """Vertices in UE numbers; faces CCW from outside (right-handed math on the UE numbers); per-corner UV0 (and an
    optional UV1), per-face material index, per-corner RGBA mask colour (values as they should land in the FBX)."""

    def __init__(self, name, n_uv=1, colors=False):
        self.name = name
        self.V = []
        self.F = []
        self.UV = [[] for _ in range(n_uv)]
        self.MAT = []
        self.COL = [] if colors else None
        self.TAG = []

    def add_verts(self, pts):
        base = len(self.V)
        self.V.extend([tuple(float(c) for c in p) for p in pts])
        return base

    def add_face(self, idx, uvs, mat=0, cols=None, tag=""):
        idx = [int(i) for i in idx]
        if len(set(idx)) < 3:
            return
        self.F.append(idx)
        for k in range(len(self.UV)):
            uv = uvs[k] if len(self.UV) > 1 else uvs
            if len(self.UV) > 1 and uv is None:
                uv = [(0.0, 0.0)] * len(idx)
            self.UV[k].append([tuple(float(c) for c in u) for u in uv])
        self.MAT.append(int(mat))
        if self.COL is not None:
            self.COL.append([tuple(float(c) for c in cc) for cc in (cols or [(1, 1, 1, 1)] * len(idx))])
        self.TAG.append(tag)

    def merge(self, other, mat_map=None):
        base = len(self.V)
        self.V.extend(other.V)
        for i, f in enumerate(other.F):
            self.F.append([base + j for j in f])
            for k in range(len(self.UV)):
                self.UV[k].append(other.UV[k][i] if k < len(other.UV) else [(0.0, 0.0)] * len(f))
            m = other.MAT[i]
            self.MAT.append(mat_map[m] if mat_map else m)
            if self.COL is not None:
                self.COL.append(other.COL[i] if other.COL is not None else [(1, 1, 1, 1)] * len(f))
            self.TAG.append(other.TAG[i])

    def verts(self):
        return np.array(self.V, dtype=np.float64)

    def triangles(self):
        return sum(len(f) - 2 for f in self.F)

    def to_object(self, materials, uv_names=("UVMap", "UV1")):
        """Blender object (metres, .blend axes) with outward normals; see the module doc for the mirror."""
        V = self.verts()
        B = np.c_[-V[:, 1], -V[:, 0], V[:, 2]] / 100.0
        faces = [list(reversed(f)) for f in self.F]
        me = bpy.data.meshes.new(self.name)
        me.from_pydata(B.tolist(), [], faces)
        me.update()
        for p in me.polygons:
            p.use_smooth = False
        for k in range(len(self.UV)):
            uvl = me.uv_layers.new(name=uv_names[k])
            flat = [c for uvs in self.UV[k] for uv in reversed(uvs) for c in uv]
            uvl.data.foreach_set("uv", flat)
        me.polygons.foreach_set("material_index", self.MAT)
        if self.COL is not None:
            attr = me.color_attributes.new("Col", "FLOAT_COLOR", "CORNER")
            lin = []
            for cols in self.COL:
                for c in reversed(cols):
                    rgb = srgb_to_linear(np.array(c[:3]))
                    lin.extend([float(rgb[0]), float(rgb[1]), float(rgb[2]), float(c[3])])
            attr.data.foreach_set("color", lin)
            me.color_attributes.active_color = attr
        me.validate(clean_customdata=False)
        if len(me.polygons) != len(faces):
            raise RuntimeError("%s: validate() dropped faces (%d -> %d)" % (self.name, len(faces), len(me.polygons)))
        obj = bpy.data.objects.new(self.name, me)
        bpy.context.scene.collection.objects.link(obj)
        for m in materials:
            me.materials.append(m)
        return obj


def flat_material(name, rgb=(0.5, 0.5, 0.5), rough=0.8, metal=0.0):
    m = bpy.data.materials.get(name) or bpy.data.materials.new(name)
    m.use_nodes = True
    b = next(n for n in m.node_tree.nodes if n.type == "BSDF_PRINCIPLED")
    b.inputs["Base Color"].default_value = (*rgb, 1.0)
    b.inputs["Roughness"].default_value = rough
    b.inputs["Metallic"].default_value = metal
    return m


# ----------------------------------------------------------------------------- measurements
def bounds(V):
    lo, hi = V.min(0), V.max(0)
    return {"min": [r(v, 3) for v in lo], "max": [r(v, 3) for v in hi], "size": [r(hi[i] - lo[i], 3) for i in range(3)]}


def signed_volume(V, F):
    """Signed volume (uu^3) of a face set authored CCW-outward on the UE numbers (> 0 for a closed outward shell)."""
    vol = 0.0
    for f in F:
        a = V[f[0]]
        for i in range(1, len(f) - 1):
            vol += float(np.dot(a, np.cross(V[f[i]], V[f[i + 1]]))) / 6.0
    return vol


def uv_stats(mb):
    out = {}
    names = ("UVMap", "UV1")
    for k in range(len(mb.UV)):
        uvs = np.array([uv for f in mb.UV[k] for uv in f])
        out[names[k]] = {"min": [r(uvs[:, 0].min(), 4), r(uvs[:, 1].min(), 4)],
                         "max": [r(uvs[:, 0].max(), 4), r(uvs[:, 1].max(), 4)]}
    # degenerate UV triangles (area < 1e-10) on UV0
    deg = 0
    for f, uvs in zip(mb.F, mb.UV[0]):
        a = np.array(uvs[0])
        for i in range(1, len(f) - 1):
            b, c = np.array(uvs[i]), np.array(uvs[i + 1])
            if abs((b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0])) < 1e-10:
                deg += 1
    out["degenerateUv0Triangles"] = deg
    return out


def export(obj, fbx_path, P=None):
    pr = preset()
    kwargs = S.fbx_kwargs(pr)
    conformance = [c for c in S.um_fbx_v1_conformance(pr, kwargs, obj, bpy.context.scene)
                   if not c["setting"].startswith("Pivot:")]
    S.export_fbx(obj, Path(fbx_path), pr)
    return {"fbx": rel(fbx_path), "sha256": S.sha256(fbx_path), "bytes": Path(fbx_path).stat().st_size,
            "preset": PRESET_PATH.name,
            "exporter_kwargs": {k: (sorted(v) if isinstance(v, set) else v) for k, v in sorted(kwargs.items())},
            "colors_type": "SRGB (exporter default; mask values pre-linearised, see k_blender.py)",
            "um_fbx_v1_conformance": conformance}


def roundtrip(fbx_path, expected_tris, expected_slots, build_bounds_ue):
    """Fresh empty scene, FBX import, compare (read-back frame = UE with Y negated, metres x100 = uu)."""
    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.ops.import_scene.fbx(filepath=str(fbx_path))
    objs = S.mesh_objects()
    o = objs[0] if objs else None
    lo, hi = S.world_bounds(objs)
    rb_lo = [v * 100 for v in lo]
    rb_hi = [v * 100 for v in hi]
    as_ue = {"min": [r(rb_lo[0], 3), r(-rb_hi[1], 3), r(rb_lo[2], 3)],
             "max": [r(rb_hi[0], 3), r(-rb_lo[1], 3), r(rb_hi[2], 3)]}
    res = {"mesh_objects": len(objs), "triangles": sum(S.triangles(x) for x in objs), "expected_triangles": expected_tris,
           "material_slots": [m.name if m else None for m in o.data.materials] if o else None,
           "expected_slots": expected_slots,
           "uv_layers": [l.name for l in o.data.uv_layers] if o else None,
           "color_attributes": [a.name for a in o.data.color_attributes] if o else [],
           "bounds_as_ue_uu": as_ue,
           "note": "read-back frame: UE = (x, -y, z)"}
    if o is not None and o.data.color_attributes:
        a = o.data.color_attributes[0]
        n = len(a.data)
        buf = np.zeros(n * 4, dtype=np.float32)
        a.data.foreach_get("color", buf)
        c = buf.reshape(-1, 4)
        fv = linear_to_srgb(c[:, :3]) if a.data_type == "FLOAT_COLOR" else c[:, :3]
        res["color_file_values"] = {"domain": a.domain, "type": a.data_type,
                                    "min": [r(v, 4) for v in fv.min(0)], "max": [r(v, 4) for v in fv.max(0)],
                                    "mean": [r(v, 4) for v in fv.mean(0)]}
    res["ue_frame_matches_build"] = all(abs(a - b) < 0.05 for a, b in zip(as_ue["min"] + as_ue["max"],
                                                                           build_bounds_ue["min"] + build_bounds_ue["max"]))
    return res


def write_json(path, data):
    def conv(o):
        if hasattr(o, "item"):
            return o.item()
        if hasattr(o, "tolist"):
            return o.tolist()
        raise TypeError("not JSON serializable: %r" % type(o))
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text(json.dumps(data, indent=2, ensure_ascii=False, default=conv) + "\n", encoding="utf-8")


def save_scratch_blend(P, name):
    bpy.context.preferences.filepaths.save_version = 0
    path = P["_scratch"] / "work" / ("%s.blend" % name)
    bpy.ops.wm.save_as_mainfile(filepath=str(path), compress=False, copy=True)
    return str(path)


# ----------------------------------------------------------------------------- previews (Cycles on the CPU only)
def setup_cycles_cpu(samples=16, res=(960, 540), threads=4):
    sc = bpy.context.scene
    try:
        sc.render.engine = "CYCLES"
    except TypeError as e:
        raise SystemExit("Cycles unavailable: %s" % e)
    sc.cycles.device = "CPU"
    sc.cycles.samples = int(samples)
    sc.cycles.use_denoising = True
    sc.render.threads_mode = "FIXED"
    sc.render.threads = int(threads)
    sc.render.resolution_x, sc.render.resolution_y = res
    sc.render.resolution_percentage = 100
    fmts = [i.identifier for i in sc.render.image_settings.bl_rna.properties["file_format"].enum_items]
    sc.render.image_settings.file_format = "JPEG" if "JPEG" in fmts else "PNG"
    if sc.render.image_settings.file_format == "JPEG":
        sc.render.image_settings.quality = 88
    vts = [i.identifier for i in sc.view_settings.bl_rna.properties["view_transform"].enum_items]
    sc.view_settings.view_transform = "AgX" if "AgX" in vts else "Standard"
    return sc


def ue(x, y, z):
    """UE numbers -> the FBX read-back frame in Blender (Y negated, metres)."""
    return Vector((x, -y, z)) / 100.0


def review_rig(sc, key_energy=2.2, fill_energy=0.45, world_rgb=(0.012, 0.016, 0.03)):
    """Neutral review rig of tray_t2_preview.py: cool key along the art profiles' key (-55, 30, 0), warm fill from the
    camera side, dim blue world. Not the night profiles."""
    world = bpy.data.worlds.new("W")
    sc.world = world
    world.use_nodes = True
    bg = next(n for n in world.node_tree.nodes if n.type == "BACKGROUND")
    bg.inputs["Color"].default_value = (*world_rgb, 1.0)
    bg.inputs["Strength"].default_value = 1.0
    p, yw = math.radians(-55.0), math.radians(30.0)
    travel = Vector((math.cos(p) * math.cos(yw), -math.cos(p) * math.sin(yw), math.sin(p)))
    key = bpy.data.objects.new("Key", bpy.data.lights.new("Key", "SUN"))
    key.data.energy = key_energy
    key.data.color = (0.75, 0.82, 1.0)
    key.data.angle = math.radians(2.0)
    key.rotation_euler = travel.to_track_quat("-Z", "Y").to_euler()
    sc.collection.objects.link(key)
    fill = bpy.data.objects.new("Fill", bpy.data.lights.new("Fill", "SUN"))
    fill.data.energy = fill_energy
    fill.data.color = (1.0, 0.8, 0.6)
    fill.rotation_euler = Vector((0.15, 0.75, -0.55)).normalized().to_track_quat("-Z", "Y").to_euler()
    sc.collection.objects.link(fill)
    return key, fill


def camera(sc, hfov_deg=35.0):
    cam = bpy.data.objects.new("Cam", bpy.data.cameras.new("Cam"))
    sc.collection.objects.link(cam)
    sc.camera = cam
    cam.data.sensor_fit = "HORIZONTAL"
    cam.data.angle = math.radians(hfov_deg)
    cam.data.clip_start, cam.data.clip_end = 0.05, 300.0
    return cam


def aim(obj, target):
    obj.rotation_euler = (target - obj.location).to_track_quat("-Z", "Y").to_euler()


def game_view(focus_ue, dist, pitch_deg=-55.0):
    """The board camera model (yaw -90: looking along UE -Y from +Y) -> (location, target) in the read-back frame."""
    p = math.radians(-pitch_deg)
    fx, fy, fz = focus_ue
    return ue(fx, fy + dist * math.cos(p), fz + dist * math.sin(p)), ue(fx, fy, fz)


def render(sc, cam, path, loc, target, ortho=None):
    cam.location = loc
    aim(cam, target)
    if ortho:
        cam.data.type = "ORTHO"
        cam.data.ortho_scale = ortho
    else:
        cam.data.type = "PERSP"
    sc.render.filepath = str(path)
    bpy.ops.render.render(write_still=True)


def import_fbx_placed(path, loc_ue=(0.0, 0.0, 0.0), yaw_deg=0.0, scale=1.0):
    """Import an exported FBX and place it like a UE component at loc (UE numbers), yaw (UE degrees), uniform scale."""
    before = set(bpy.context.scene.objects)
    bpy.ops.import_scene.fbx(filepath=str(path))
    new = [o for o in bpy.context.scene.objects if o not in before and o.type == "MESH"]
    for o in new:
        o.location = ue(*loc_ue)
        # UE yaw (left-handed, about +Z) is -yaw in the Y-negated read-back frame
        o.rotation_euler = (0.0, 0.0, math.radians(-yaw_deg))
        o.scale = Vector(o.scale) * scale
    return new


def textured_material(name, bc=None, n_dx=None, orm=None, rgb=None, rough=0.85, emission=None, vcol_tint=None):
    """Preview material: BC/N(DirectX)/ORM images (REPEAT) or a flat colour; optional emission (image mask x colour)."""
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    nt = m.node_tree
    b = next(n for n in nt.nodes if n.type == "BSDF_PRINCIPLED")
    if bc:
        t = nt.nodes.new("ShaderNodeTexImage")
        t.image = bpy.data.images.load(str(bc))
        t.extension = "REPEAT"
        col = t.outputs["Color"]
        if vcol_tint:
            # mix the BC towards vcol_tint[1] by the vertex-colour channel vcol_tint[0] (preview of a mask MI param)
            attr = nt.nodes.new("ShaderNodeVertexColor")
            attr.layer_name = "Col"
            sep = nt.nodes.new("ShaderNodeSeparateColor")
            nt.links.new(attr.outputs["Color"], sep.inputs["Color"])
            mix = nt.nodes.new("ShaderNodeMix")
            mix.data_type = "RGBA"
            mix.blend_type = "MULTIPLY"
            nt.links.new(sep.outputs[vcol_tint[0]], mix.inputs["Factor"])
            nt.links.new(col, mix.inputs[6])
            mix.inputs[7].default_value = (*vcol_tint[1], 1.0)
            col = mix.outputs[2]
        nt.links.new(col, b.inputs["Base Color"])
    elif rgb:
        b.inputs["Base Color"].default_value = (*rgb, 1.0)
    b.inputs["Roughness"].default_value = rough
    if orm:
        t = nt.nodes.new("ShaderNodeTexImage")
        t.image = bpy.data.images.load(str(orm))
        t.image.colorspace_settings.name = "Non-Color"
        sep = nt.nodes.new("ShaderNodeSeparateColor")
        nt.links.new(t.outputs["Color"], sep.inputs["Color"])
        nt.links.new(sep.outputs["Green"], b.inputs["Roughness"])
        nt.links.new(sep.outputs["Blue"], b.inputs["Metallic"])
    if n_dx:
        t = nt.nodes.new("ShaderNodeTexImage")
        t.image = bpy.data.images.load(str(n_dx))
        t.image.colorspace_settings.name = "Non-Color"
        sn = nt.nodes.new("ShaderNodeSeparateColor")
        inv = nt.nodes.new("ShaderNodeMath")
        inv.operation = "SUBTRACT"
        inv.inputs[0].default_value = 1.0
        cm = nt.nodes.new("ShaderNodeCombineColor")
        nm = nt.nodes.new("ShaderNodeNormalMap")
        nt.links.new(t.outputs["Color"], sn.inputs["Color"])
        nt.links.new(sn.outputs["Red"], cm.inputs["Red"])
        nt.links.new(sn.outputs["Green"], inv.inputs[1])
        nt.links.new(inv.outputs[0], cm.inputs["Green"])
        nt.links.new(sn.outputs["Blue"], cm.inputs["Blue"])
        nt.links.new(cm.outputs["Color"], nm.inputs["Color"])
        nt.links.new(nm.outputs["Normal"], b.inputs["Normal"])
    if emission:
        img_path, rgb_e, strength = emission
        t = nt.nodes.new("ShaderNodeTexImage")
        t.image = bpy.data.images.load(str(img_path))
        t.image.colorspace_settings.name = "Non-Color"
        mul = nt.nodes.new("ShaderNodeMix")
        mul.data_type = "RGBA"
        mul.blend_type = "MULTIPLY"
        mul.inputs["Factor"].default_value = 1.0
        nt.links.new(t.outputs["Color"], mul.inputs[6])
        mul.inputs[7].default_value = (*rgb_e, 1.0)
        nt.links.new(mul.outputs[2], b.inputs["Emission Color"])
        b.inputs["Emission Strength"].default_value = strength
    return m
