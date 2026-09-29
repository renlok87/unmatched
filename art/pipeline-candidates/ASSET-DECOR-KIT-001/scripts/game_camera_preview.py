"""Game-camera + ortho previews of an exported static prop FBX (UM_FBX_v1), rendered from the FBX itself.

Headless only (never touches live Blender sessions):
  blender -b --factory-startup --python-exit-code 1 \
      --python art/pipeline-candidates/ASSET-DECOR-KIT-001/scripts/game_camera_preview.py -- \
      <fbx> <texture_prefix_path> <out_dir> [pitch_deg=55] [fov_deg=35] [yaws=0,45]

<texture_prefix_path> = path without suffix, e.g. .../export/T_Decor_Barrel -> _BC/_N/_ORM.png.
The material is rebuilt from the delivered triplet the way UE reads it: BC sRGB, N Linear DirectX
(green flipped back to OpenGL for Blender), ORM Linear (R AO, G roughness, B metallic). A wrong
normal convention therefore shows up as inverted relief in these renders.

Outputs (JPEG, 1200x900): <name>_game-fov35-pitch55-yaw<Y>.jpg (perspective, horizontal FOV like UE)
and <name>_ortho-{front-plusX,side-plusY}.jpg; <name>_preview.json. Axes are UE axes (asset front = +X).
Two material slots (glow_slot of static_prop_candidate.py params): the slot whose name contains "Glow" gets the
same triplet plus a constant emission (preview value, recorded in the JSON; the UE value is an MI parameter).
Measurement only.
"""
import json
import math
import sys
from pathlib import Path

import bpy
from mathutils import Vector

args = sys.argv[sys.argv.index("--") + 1:]
# absolute paths: images.load and render.filepath do not resolve a relative path against the working directory
fbx, tex_prefix, out = Path(args[0]), str(Path(args[1]).resolve()), Path(args[2]).resolve()
pitch = float(args[3]) if len(args) > 3 else 55.0
fov = float(args[4]) if len(args) > 4 else 35.0
yaws = [float(y) for y in (args[5] if len(args) > 5 else "0,45").split(",")]
out.mkdir(parents=True, exist_ok=True)

bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.fbx(filepath=str(fbx))
objs = [o for o in bpy.context.scene.objects if o.type == "MESH"]
name = fbx.stem


def img(suffix, colorspace):
    im = bpy.data.images.load("%s_%s.png" % (tex_prefix, suffix))
    im.colorspace_settings.name = colorspace
    return im


mat = bpy.data.materials.new("PreviewFromTriplet")
mat.use_nodes = True
nt = mat.node_tree
bsdf = nt.nodes["Principled BSDF"]
bc = nt.nodes.new("ShaderNodeTexImage"); bc.image = img("BC", "sRGB")
orm = nt.nodes.new("ShaderNodeTexImage"); orm.image = img("ORM", "Non-Color")
nrm = nt.nodes.new("ShaderNodeTexImage"); nrm.image = img("N", "Non-Color")
sep = nt.nodes.new("ShaderNodeSeparateColor")
mix_ao = nt.nodes.new("ShaderNodeMix"); mix_ao.data_type = "RGBA"; mix_ao.blend_type = "MULTIPLY"
mix_ao.inputs["Factor"].default_value = 1.0
nsep = nt.nodes.new("ShaderNodeSeparateColor")
inv = nt.nodes.new("ShaderNodeMath"); inv.operation = "SUBTRACT"; inv.inputs[0].default_value = 1.0
ncomb = nt.nodes.new("ShaderNodeCombineColor")
nmap = nt.nodes.new("ShaderNodeNormalMap")
L = nt.links.new
L(orm.outputs["Color"], sep.inputs["Color"])
L(bc.outputs["Color"], mix_ao.inputs["A"])
L(sep.outputs["Red"], mix_ao.inputs["B"])
L(mix_ao.outputs["Result"], bsdf.inputs["Base Color"])
L(sep.outputs["Green"], bsdf.inputs["Roughness"])
L(sep.outputs["Blue"], bsdf.inputs["Metallic"])
L(nrm.outputs["Color"], nsep.inputs["Color"])
L(nsep.outputs["Green"], inv.inputs[1])  # DirectX -> OpenGL
L(nsep.outputs["Red"], ncomb.inputs["Red"])
L(inv.outputs["Value"], ncomb.inputs["Green"])
L(nsep.outputs["Blue"], ncomb.inputs["Blue"])
L(ncomb.outputs["Color"], nmap.inputs["Color"])
L(nmap.outputs["Normal"], bsdf.inputs["Normal"])
GLOW_PREVIEW = {"srgb_8bit": [255, 194, 122], "strength": 3.0}  # 03 C-6 warm range; preview only
glow_mat, glow_slots = None, []
for o in objs:
    names = [m.name if m else "" for m in o.data.materials]
    if len(names) <= 1:
        o.data.materials.clear()
        o.data.materials.append(mat)
        continue
    for i, nm in enumerate(names):
        if "Glow" in nm:
            if glow_mat is None:
                glow_mat = mat.copy()
                glow_mat.name = "PreviewGlowFromTriplet"
                gb = glow_mat.node_tree.nodes["Principled BSDF"]
                lin = [c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4
                       for c in (v / 255.0 for v in GLOW_PREVIEW["srgb_8bit"])]
                gb.inputs["Emission Color"].default_value = (lin[0], lin[1], lin[2], 1.0)
                gb.inputs["Emission Strength"].default_value = GLOW_PREVIEW["strength"]
            o.data.materials[i] = glow_mat
            glow_slots.append(nm)
        else:
            o.data.materials[i] = mat

scene = bpy.context.scene
try:
    scene.render.engine = "BLENDER_EEVEE_NEXT"
except TypeError:
    scene.render.engine = "BLENDER_EEVEE"
scene.render.resolution_x, scene.render.resolution_y = 1200, 900
scene.render.image_settings.file_format = "JPEG"
scene.render.image_settings.quality = 90
scene.view_settings.view_transform = "Standard"
world = bpy.data.worlds.new("World"); scene.world = world
world.use_nodes = True
bg = world.node_tree.nodes["Background"]
bg.inputs["Color"].default_value = (0.22, 0.22, 0.24, 1)
bg.inputs["Strength"].default_value = 0.6
for nm, energy, rot in (("Key", 3.5, (50, 0, 35)), ("Fill", 1.0, (60, 0, -140))):
    ld = bpy.data.lights.new(nm, "SUN"); ld.energy = energy
    lo_ = bpy.data.objects.new(nm, ld); scene.collection.objects.link(lo_)
    lo_.rotation_euler = tuple(math.radians(v) for v in rot)

pts = [o.matrix_world @ v.co for o in objs for v in o.data.vertices]
lo = Vector((min(p.x for p in pts), min(p.y for p in pts), min(p.z for p in pts)))
hi = Vector((max(p.x for p in pts), max(p.y for p in pts), max(p.z for p in pts)))
centre, radius = (lo + hi) / 2, (hi - lo).length / 2

cd = bpy.data.cameras.new("Cam")
cam = bpy.data.objects.new("Cam", cd); scene.collection.objects.link(cam); scene.camera = cam
report = {"fbx": fbx.name, "bounds_blender_m": {"min": [round(v, 5) for v in lo], "max": [round(v, 5) for v in hi]},
          "material": "rebuilt from %s_{BC,N,ORM}.png (N DirectX->OpenGL)" % Path(tex_prefix).name, "shots": {}}
if glow_slots:
    report["glow_preview"] = dict(GLOW_PREVIEW, slots=glow_slots,
                                  note="constant emission on the glow slot, Blender preview only")


def shoot(key, d):
    cam.location = centre + d
    cam.rotation_euler = (-d).to_track_quat("-Z", "Y").to_euler()
    path = out / ("%s_%s.jpg" % (name, key))
    scene.render.filepath = str(path)
    bpy.ops.render.render(write_still=True)
    return path.name


# perspective game camera: horizontal FOV (UE convention), pitch below horizon.
# yaw 0 = camera on +X = asset front: the FBX is read back in UE axes (UM_FBX_v1 turns .blend -Y into +X;
# barrel readback: bung at +5.8 deg). Looking at the front, frame-left = -Y, frame-right = +Y.
cd.type = "PERSP"; cd.sensor_fit = "HORIZONTAL"; cd.angle = math.radians(fov)
vfov = 2 * math.atan(math.tan(math.radians(fov) / 2) * scene.render.resolution_y / scene.render.resolution_x)
dist = radius * 1.15 / math.sin(min(math.radians(fov), vfov) / 2)
for yaw in yaws:
    p, y = math.radians(pitch), math.radians(yaw)
    d = Vector((math.cos(p) * math.cos(y), math.cos(p) * math.sin(y), math.sin(p))) * dist
    key = "game-fov%g-pitch%g-yaw%g" % (fov, pitch, yaw)
    report["shots"][key] = {"file": shoot(key, d), "fov_h_deg": fov, "pitch_deg": -pitch, "yaw_deg": yaw,
                            "distance_m": round(dist, 4)}
cd.type = "ORTHO"; cd.ortho_scale = max(hi - lo) * 1.35
for key, d in (("ortho-front-plusX", Vector((1, 0, 0))), ("ortho-side-plusY", Vector((0, 1, 0)))):
    report["shots"][key] = {"file": shoot(key, d * radius * 4), "ortho_scale_m": round(cd.ortho_scale, 4)}
(out / ("%s_preview.json" % name)).write_text(json.dumps(report, indent=2), encoding="utf-8")
print("PREVIEW_REPORT", json.dumps(report))
