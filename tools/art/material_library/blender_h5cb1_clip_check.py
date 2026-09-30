"""Blender (live GUI via MCP :9876, blender_mcp.py exec) cross-check of wave 5c-B1 group H: an H2Anim clip on the
look-dev H2LD/H3LD mesh in Blender, frames 0 / 50 / 100 %, lowest evaluated vertex against the pedestal top.

Works in its OWN scene (H5CB1_CHECK_SCENE) of the open Blender file and removes it (with its objects, meshes, armatures
and actions) at the end; the user's scene and objects are not touched. Parameters come from the JSON file named in
the environment variable / global H5CB1_ARGS: {"mesh_fbx", "base_fbx", "clip_fbx", "out_dir", "tag", "keep": false}.
Result: <out_dir>/<tag>-blender.json and viewport PNGs <tag>-blender-<pct>.png (OpenGL render of the scene camera).
"""
import json
import math
import os

import bpy
from mathutils import Vector

ARGS = json.load(open(globals().get("H5CB1_ARGS") or os.environ["H5CB1_ARGS"], encoding="utf-8"))
SCN = "H5CB1_CHECK_SCENE"
prev_scene = bpy.context.window.scene
if SCN in bpy.data.scenes:
    bpy.data.scenes.remove(bpy.data.scenes[SCN])
scene = bpy.data.scenes.new(SCN)
bpy.context.window.scene = scene
before_objs = set(bpy.data.objects)
before_actions = set(bpy.data.actions)
before_other = {c: set(getattr(bpy.data, c)) for c in ("materials", "images", "armatures", "meshes", "cameras", "lights")}


def import_fbx(path):
    have = set(bpy.data.objects)
    bpy.ops.import_scene.fbx(filepath=path, automatic_bone_orientation=False)
    return [o for o in bpy.data.objects if o not in have]


mesh_objs = import_fbx(ARGS["mesh_fbx"])
base_objs = import_fbx(ARGS["base_fbx"])
clip_objs = import_fbx(ARGS["clip_fbx"])
arm = next(o for o in mesh_objs if o.type == "ARMATURE")
body = [o for o in mesh_objs if o.type == "MESH"]
base = [o for o in base_objs if o.type == "MESH"]
clip_arm = next(o for o in clip_objs if o.type == "ARMATURE")
action = clip_arm.animation_data.action if clip_arm.animation_data else None
if action is None:
    raise RuntimeError("clip FBX without an action")
for o in clip_objs:
    o.hide_render = True
    o.hide_set(True)
arm.animation_data_create()
arm.animation_data.action = action
try:  # Blender 4.4+: slotted actions
    if getattr(action, "slots", None) and len(action.slots):
        arm.animation_data.action_slot = action.slots[0]
except Exception:  # noqa: BLE001
    pass
f0, f1 = [int(round(x)) for x in action.frame_range]
bone_names = [b.name for b in arm.data.bones]
clip_bones = {g.data_path.split('"')[1] for g in action.fcurves if g.data_path.startswith("pose.bones")} \
    if hasattr(action, "fcurves") else set()


def lowest_z(objs):
    dg = bpy.context.evaluated_depsgraph_get()
    zmin = None
    for o in objs:
        ev = o.evaluated_get(dg)
        me = ev.to_mesh()
        mw = ev.matrix_world
        for v in me.vertices:
            z = (mw @ v.co).z
            zmin = z if zmin is None or z < zmin else zmin
        ev.to_mesh_clear()
    return zmin


def top_z(objs):
    return max((o.matrix_world @ Vector(c)).z for o in objs for c in o.bound_box)


def height(objs):
    dg = bpy.context.evaluated_depsgraph_get()
    zs = []
    for o in objs:
        ev = o.evaluated_get(dg)
        me = ev.to_mesh()
        zs += [(ev.matrix_world @ v.co).z for v in me.vertices]
        ev.to_mesh_clear()
    return min(zs), max(zs)


# camera: 3/4 front (the rig v2 faces +X in UE = author -Y in Blender (UM_FBX_v1): look from -Y/+X)
lo, hi = height(body)
h = hi - lo
cam_data = bpy.data.cameras.new("H5CB1_cam")
cam_data.lens = 50
cam = bpy.data.objects.new("H5CB1_cam", cam_data)
scene.collection.objects.link(cam)
d = h * 3.2
cam.location = (d * math.sin(math.radians(35)), -d * math.cos(math.radians(35)), lo + h * 0.55)
direction = Vector((0, 0, lo + h * 0.45)) - cam.location
cam.rotation_euler = direction.to_track_quat("-Z", "Y").to_euler()
scene.camera = cam
sun_data = bpy.data.lights.new("H5CB1_sun", "SUN")
sun_data.energy = 3.0
sun = bpy.data.objects.new("H5CB1_sun", sun_data)
sun.rotation_euler = (math.radians(50), 0, math.radians(30))
scene.collection.objects.link(sun)
scene.render.resolution_x, scene.render.resolution_y = 960, 960
try:
    scene.render.engine = "BLENDER_WORKBENCH"
    scene.display.shading.color_type = "TEXTURE"
except Exception:  # noqa: BLE001 - engine ids differ between versions; the default engine renders too
    pass
scene.render.image_settings.file_format = "PNG"

res = {"mesh_fbx": ARGS["mesh_fbx"], "base_fbx": ARGS["base_fbx"], "clip_fbx": ARGS["clip_fbx"],
       "action": action.name, "frame_range": [f0, f1], "armature": arm.name, "bones": len(bone_names),
       "clip_bones_missing_on_mesh": sorted(b for b in clip_bones if b not in bone_names),
       "base_top_z": round(top_z(base), 5), "ref_min_z": round(lo, 5), "ref_height": round(h, 5), "frames": {}}
for pct in (0, 50, 100):
    fr = f0 + (f1 - f0) * pct / 100.0
    scene.frame_set(int(math.floor(fr)), subframe=fr - math.floor(fr))
    lz, hz = height(body)
    png = os.path.join(ARGS["out_dir"], "%s-blender-%03d.png" % (ARGS["tag"], pct))
    scene.render.filepath = png
    try:
        bpy.ops.render.opengl(write_still=True, view_context=False)
    except Exception as exc:  # noqa: BLE001
        png = "render failed: %s" % exc
    res["frames"][str(pct)] = {"frame": round(fr, 3), "min_z": round(lz, 5), "max_z": round(hz, 5),
                               "min_below_base_top": round(res["base_top_z"] - lz, 5), "png": png}
json.dump(res, open(os.path.join(ARGS["out_dir"], "%s-blender.json" % ARGS["tag"]), "w", encoding="utf-8"), indent=1)

if not ARGS.get("keep"):
    bpy.context.window.scene = prev_scene
    new_objs = [o for o in bpy.data.objects if o not in before_objs]
    datas = [(type(o.data).__name__, o.data.name) for o in new_objs if o.data is not None]
    for o in new_objs:
        bpy.data.objects.remove(o, do_unlink=True)
    colls = {"Mesh": bpy.data.meshes, "Armature": bpy.data.armatures, "Camera": bpy.data.cameras,
             "SunLight": bpy.data.lights}
    for kind, name in datas:
        coll = colls.get(kind)
        if coll is not None and name in coll and coll[name].users == 0:
            coll.remove(coll[name])
    for a in [a for a in bpy.data.actions if a not in before_actions]:
        bpy.data.actions.remove(a)
    bpy.data.scenes.remove(scene)
    for cname, had in before_other.items():   # imported materials / images / leftover data of this run only
        coll = getattr(bpy.data, cname)
        for dblock in [x for x in coll if x not in had and x.users == 0]:
            coll.remove(dblock)
print("H5CB1", json.dumps({k: v for k, v in res.items() if k != "frames"}), json.dumps(res["frames"]))
