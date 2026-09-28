"""Base closure review of the Arthur candidate (verify 2026-09-28: footprint holes in the base top).

Headless only:  blender -b --factory-startup --python base_closure_review_arthur.py -- <run_dir> <out_dir>
                [--export-dir <dir with SK_*.fbx and SM_*.fbx>]   (default <run_dir>/export)

Imports the exported FBX pair as written (UM_FBX_v1), turns it back by the inverse +90 deg Z rotation
(authored frame, face -Y) and renders with BACKFACE CULLING, as a one-sided UE material draws it:
  * Workbench, flat colours (base grey, figure gold, magenta background), orthographic 0.34 m:
    rest pose from the top and from pitch 55 deg at yaw 0/90/180/270 (the verify frames), and the base
    alone from the top and from the front at pitch 55;
    for each frame the magenta (background) pixels inside the projected base-top disc (r = 0.12 m, the
    flat part of the top) are counted: a see-through opening in the top shows up as background there;
  * EEVEE with the atlas material (backface culling on), step pose (leg_upper.R -30 deg X, leg_upper.L
    +20 deg X, as the verify frame) at the game camera (horizontal FOV 35, pitch -55) and orthographic
    close-ups of the base under the lifted feet; the probe pose thigh_r_flex (-35 deg X) from the right as
    preview/poses/pose-thigh_r_flex-right; the base alone from the top (cap texture against the stone).
Writes <out_dir>/*.png and <out_dir>/base-closure-review.json. Nothing is saved to any .blend.
"""
import json
import math
import sys
from pathlib import Path

import bpy
import numpy as np
from bpy_extras.object_utils import world_to_camera_view
from mathutils import Matrix, Vector

if not bpy.app.background:
    raise RuntimeError("base_closure_review_arthur.py: headless only (blender -b)")

argv = sys.argv[sys.argv.index("--") + 1:]
RUN, OUT = Path(argv[0]).resolve(), Path(argv[1]).resolve()
EXPORT = Path(argv[argv.index("--export-dir") + 1]).resolve() if "--export-dir" in argv else RUN / "export"
OUT.mkdir(parents=True, exist_ok=True)
TOP_Z, DISC_R = 0.06, 0.12
MAGENTA = (1.0, 0.0, 1.0)

bpy.ops.wm.read_factory_settings(use_empty=True)
fbx = sorted(EXPORT.glob("*.fbx"))
for f in fbx:
    bpy.ops.import_scene.fbx(filepath=str(f))
sc = bpy.context.scene
inv = Matrix.Rotation(math.radians(-90.0), 4, "Z")
for o in sc.objects:
    if o.parent is None:
        o.matrix_world = inv @ o.matrix_world
bpy.context.view_layer.update()
arm = next(o for o in sc.objects if o.type == "ARMATURE")
meshes = [o for o in sc.objects if o.type == "MESH"]
base = next(o for o in meshes if o.name.startswith("SM_"))
figure = [o for o in meshes if o is not base]

tex = RUN / "textures"
mat = bpy.data.materials.new("M_Review_Atlas_Culled")
mat.use_nodes = True
mat.use_backface_culling = True
nt = mat.node_tree
bsdf = next(n for n in nt.nodes if n.type == "BSDF_PRINCIPLED")
imgs = {}
for key in ("BC", "N_OpenGL", "ORM"):
    img = bpy.data.images.load(str(next(tex.glob("*_Atlas_%s.png" % key))))
    img.colorspace_settings.name = "sRGB" if key == "BC" else "Non-Color"
    node = nt.nodes.new("ShaderNodeTexImage")
    node.image = img
    imgs[key] = node
nt.links.new(imgs["BC"].outputs["Color"], bsdf.inputs["Base Color"])
nm = nt.nodes.new("ShaderNodeNormalMap")
nt.links.new(imgs["N_OpenGL"].outputs["Color"], nm.inputs["Color"])
nt.links.new(nm.outputs["Normal"], bsdf.inputs["Normal"])
sep = nt.nodes.new("ShaderNodeSeparateColor")
nt.links.new(imgs["ORM"].outputs["Color"], sep.inputs["Color"])
nt.links.new(sep.outputs["Green"], bsdf.inputs["Roughness"])
nt.links.new(sep.outputs["Blue"], bsdf.inputs["Metallic"])
for o in meshes:
    o.data.materials.clear()
    o.data.materials.append(mat)

cam = bpy.data.objects.new("closure_cam", bpy.data.cameras.new("closure_cam"))
sc.collection.objects.link(cam)
sc.camera = cam
frames = {}


def view_dir(yaw_deg, pitch_deg):
    """Direction from target to camera; yaw 0 = in front of the figure (-Y), 90 = figure's left (+X)."""
    p, y = math.radians(pitch_deg), math.radians(yaw_deg)
    return Vector((math.sin(y) * math.cos(p), -math.cos(y) * math.cos(p), math.sin(p)))


def place(direction, target, ortho=None, fov_h=None, distance=None, res=(1400, 1000)):
    d = direction.normalized()
    cam.data.type = "ORTHO" if ortho else "PERSP"
    if ortho:
        cam.data.ortho_scale = ortho
        cam.location = Vector(target) + d * 2.0
    else:
        cam.data.sensor_fit = "HORIZONTAL"
        cam.data.angle = math.radians(fov_h)
        cam.location = Vector(target) + d * distance
    cam.data.clip_start, cam.data.clip_end = 0.005, 50
    cam.rotation_euler = (-d).to_track_quat("-Z", "Y").to_euler()
    sc.render.resolution_x, sc.render.resolution_y = res
    sc.render.resolution_percentage = 100
    bpy.context.view_layer.update()


def disc_background_pixels(path, res):
    """Magenta pixels inside the projected base-top disc (r = DISC_R at z = TOP_Z)."""
    ring = [Vector((DISC_R * math.cos(t), DISC_R * math.sin(t), TOP_Z))
            for t in np.linspace(0, 2 * math.pi, 180, endpoint=False)]
    poly = []
    for p in ring:
        c = world_to_camera_view(sc, cam, p)
        poly.append((c.x * res[0], (1.0 - c.y) * res[1]))
    img = bpy.data.images.load(str(path), check_existing=False)
    px = np.array(img.pixels[:], dtype=np.float32).reshape(res[1], res[0], img.channels)[::-1, :, :3]
    bpy.data.images.remove(img)
    gy, gx = np.mgrid[0:res[1], 0:res[0]] + 0.5
    inside = np.zeros(gx.shape, dtype=bool)
    n = len(poly)
    for i in range(n):
        x1, y1 = poly[i]
        x2, y2 = poly[(i + 1) % n]
        cross = ((y1 > gy) != (y2 > gy)) & (gx < (x2 - x1) * (gy - y1) / ((y2 - y1) if y2 != y1 else 1e-12) + x1)
        inside ^= cross
    magenta = (px[..., 0] > 0.9) & (px[..., 1] < 0.1) & (px[..., 2] > 0.9)
    return int((magenta & inside).sum()), int(inside.sum())


def shoot(name, direction, target, count_disc=False, hide=(), **kw):
    place(direction, target, **kw)
    for o in hide:
        o.hide_render = True
    path = OUT / ("%s.png" % name)
    sc.render.filepath = str(path)
    bpy.ops.render.render(write_still=True)
    for o in hide:
        o.hide_render = False
    res = (sc.render.resolution_x, sc.render.resolution_y)
    entry = {"engine": sc.render.engine, "direction_from_target": [round(c, 4) for c in direction.normalized()],
             "target_m": [round(c, 4) for c in target], "ortho_scale_m": kw.get("ortho"),
             "horizontal_fov_deg": kw.get("fov_h"), "distance_m": kw.get("distance"), "resolution": list(res),
             "hidden": sorted(o.name for o in hide), "pose": POSE}
    if count_disc:
        bg, disc = disc_background_pixels(path, res)
        entry["background_px_inside_top_disc"] = bg
        entry["top_disc_px"] = disc
    frames[name] = entry


def set_pose(rotations):
    """Rotate bones about AUTHORED world axes through the bone head (as rig_deform_probe / pose_review on
    the authored .blend); the imported armature lives in the export frame, so the axis is taken into
    armature space."""
    for pb in arm.pose.bones:
        pb.matrix_basis = Matrix.Identity(4)
    bpy.context.view_layer.update()
    to_arm = arm.matrix_world.to_3x3().inverted()
    for bone, axis, deg in rotations:
        pb = arm.pose.bones[bone]
        head = pb.head.copy()
        ax = (to_arm @ {"X": Vector((1, 0, 0)), "Y": Vector((0, 1, 0)), "Z": Vector((0, 0, 1))}[axis]).normalized()
        pb.matrix = Matrix.Translation(head) @ Matrix.Rotation(math.radians(deg), 4, ax) @ \
            Matrix.Translation(-head) @ pb.matrix
        bpy.context.view_layer.update()


POSE = "rest"
set_pose([])

# ---------------- Workbench, flat colours, backface culling (verify frames)
sc.render.engine = "BLENDER_WORKBENCH"
sh = sc.display.shading
sh.light = "STUDIO"
sh.color_type = "OBJECT"
sh.show_backface_culling = True
sc.world = bpy.data.worlds.new("closure_world")
sc.world.color = MAGENTA
sc.view_settings.view_transform = "Standard"
for o in meshes:
    o.color = (0.35, 0.35, 0.35, 1) if o is base else (0.9, 0.75, 0.3, 1)
t_base = (0.0, 0.0, TOP_Z)
shoot("culled_rest_top", view_dir(0, 89.9), t_base, count_disc=True, ortho=0.34)
for yaw, tag in ((0, "front55"), (90, "left55"), (180, "back55"), (270, "right55")):
    shoot("culled_rest_%s" % tag, view_dir(yaw, 55), t_base, count_disc=True, ortho=0.34)
shoot("culled_base_only_top", view_dir(0, 89.9), t_base, count_disc=True, ortho=0.34, hide=figure)
shoot("culled_base_only_front55", view_dir(0, 55), t_base, count_disc=True, ortho=0.34, hide=figure)

# ---------------- EEVEE, atlas material with backface culling
sc.render.engine = "BLENDER_EEVEE"
sc.world = bpy.data.worlds.new("closure_world_eevee")
sc.world.use_nodes = True
sc.world.node_tree.nodes["Background"].inputs[0].default_value = (0.5, 0.5, 0.5, 1)
sc.world.node_tree.nodes["Background"].inputs[1].default_value = 0.55
for name, rot, energy in (("key", (50, 0, -30), 3.0), ("fill", (60, 0, 150), 1.3)):
    light = bpy.data.lights.new(name, "SUN")
    light.energy = energy
    lo = bpy.data.objects.new(name, light)
    lo.rotation_euler = [math.radians(a) for a in rot]
    sc.collection.objects.link(lo)
vfov = 2 * math.atan(math.tan(math.radians(17.5)) * 9 / 16)
fill_dist = 0.62 / (2 * math.tan(vfov / 2))
shoot("tex_base_only_top", view_dir(0, 89.9), t_base, ortho=0.32, res=(1000, 1000), hide=figure)
shoot("tex_rest_base_55", view_dir(0, 55), t_base, ortho=0.34)
POSE = "step: leg_upper.R -30 deg X, leg_upper.L +20 deg X (verify frame)"
set_pose([("leg_upper.R", "X", -30), ("leg_upper.L", "X", 20)])
shoot("tex_step_game_front", view_dir(0, 55), (0, 0, 0.22), fov_h=35, distance=fill_dist, res=(1920, 1080))
shoot("tex_step_base_front55", view_dir(0, 55), t_base, ortho=0.34)
shoot("tex_step_base_right35", view_dir(-60, 35), t_base, ortho=0.34)
POSE = "thigh_r_flex: leg_upper.R -35 deg X (rig_deform_probe)"
set_pose([("leg_upper.R", "X", -35)])
shoot("tex_thigh_r_flex_right", Vector((-1, -0.15, 0.1)), (0, 0, 0.3), ortho=0.7, res=(800, 900))
shoot("tex_thigh_r_flex_base_right35", view_dir(-70, 35), t_base, ortho=0.34)
POSE = "thigh_l_flex: leg_upper.L -35 deg X (rig_deform_probe)"
set_pose([("leg_upper.L", "X", -35)])
shoot("tex_thigh_l_flex_base_left35", view_dir(70, 35), t_base, ortho=0.34)
set_pose([])

report = {"source": [f.name for f in fbx], "export_dir": str(EXPORT.relative_to(RUN)) if EXPORT.is_relative_to(RUN) else EXPORT.name,
          "culling": "Workbench show_backface_culling / material use_backface_culling (one-sided UE material)",
          "disc_rule": "background (magenta) pixels inside the projected disc r = %s m at z = %s m" % (DISC_R, TOP_Z),
          "frames": frames,
          "background_px_inside_top_disc_total": sum(f.get("background_px_inside_top_disc", 0) for f in frames.values())}
(OUT / "base-closure-review.json").write_text(json.dumps(report, indent=1, sort_keys=True) + "\n", encoding="utf-8")
print("BASE_CLOSURE_REVIEW_OK", report["background_px_inside_top_disc_total"], len(frames))
