"""Solid (non X-ray) renders of the rig_deform_probe poses, to look for tearing and gaps
(headless only: blender -b --factory-startup --python pose_review_arthur.py -- <blend> <out_dir>).

Poses are the seven TESTS of tools/tripo-pipeline/anim/rig_deform_probe.py (same bone, world axis, angle,
rotation about the bone head in armature space). Each pose is rendered from the front-right 3/4 and from
the character's side that the pose affects. Also writes <out_dir>/pose-review.json with the per-pose
maximum vertex displacement of body and sword and the largest stretch of any body edge (ratio of posed to
rest length) as a numeric tearing/stretch indicator. Nothing is saved to the .blend.
"""
import json
import math
import sys
from pathlib import Path

import bpy
import numpy as np
from mathutils import Matrix, Vector

if not bpy.app.background:
    raise RuntimeError("pose_review_arthur.py: headless only (blender -b)")

blend, out = [Path(a).resolve() for a in sys.argv[sys.argv.index("--") + 1:][:2]]
out.mkdir(parents=True, exist_ok=True)
bpy.ops.wm.open_mainfile(filepath=str(blend))
sc = bpy.context.scene
arm = next(o for o in sc.objects if o.type == "ARMATURE")
body = next(o for o in sc.objects if o.name.startswith("SK_KingArthur_Body"))
sword = next(o for o in sc.objects if o.name.startswith("SK_KingArthur_Sword"))
TESTS = [("head_turn", "head", "Z", 35), ("spine_bend_fwd", "spine", "X", 25), ("arm_l_raise", "arm_upper.L", "Y", -45),
         ("arm_r_raise", "arm_upper.R", "Y", 45), ("forearm_l_bend", "arm_lower.L", "X", -40),
         ("thigh_l_flex", "leg_upper.L", "X", -35), ("thigh_r_flex", "leg_upper.R", "X", -35)]
VIEWS = {"3q": (-0.6, -0.75, 0.3), "left": (1, -0.15, 0.1), "right": (-1, -0.15, 0.1)}
SIDE = {"head_turn": "3q", "spine_bend_fwd": "right", "arm_l_raise": "left", "arm_r_raise": "right",
        "forearm_l_bend": "left", "thigh_l_flex": "left", "thigh_r_flex": "right"}

sc.render.engine = "BLENDER_EEVEE"
sc.view_settings.view_transform = "Standard"
sc.world = bpy.data.worlds.new("pose_world")
sc.world.use_nodes = True
sc.world.node_tree.nodes["Background"].inputs[0].default_value = (0.5, 0.5, 0.5, 1)
sc.world.node_tree.nodes["Background"].inputs[1].default_value = 0.55
for name, rot, energy in (("key", (50, 0, -30), 3.0), ("fill", (60, 0, 150), 1.3)):
    light = bpy.data.lights.new(name, "SUN")
    light.energy = energy
    lo = bpy.data.objects.new(name, light)
    lo.rotation_euler = [math.radians(a) for a in rot]
    sc.collection.objects.link(lo)
cam = bpy.data.objects.new("pose_cam", bpy.data.cameras.new("pose_cam"))
sc.collection.objects.link(cam)
sc.camera = cam
cam.data.type = "ORTHO"
cam.data.ortho_scale = 0.7
sc.render.resolution_x, sc.render.resolution_y = 800, 900


def evaluated(obj):
    dg = bpy.context.evaluated_depsgraph_get()
    ev = obj.evaluated_get(dg)
    me = ev.to_mesh()
    co = np.array([tuple(obj.matrix_world @ v.co) for v in me.vertices])
    ev.to_mesh_clear()
    return co


def reset():
    for pb in arm.pose.bones:
        pb.matrix_basis = Matrix.Identity(4)
    bpy.context.view_layer.update()


def rotate(bone, axis, deg):
    pb = arm.pose.bones[bone]
    head = pb.head.copy()
    ax = {"X": Vector((1, 0, 0)), "Y": Vector((0, 1, 0)), "Z": Vector((0, 0, 1))}[axis]
    rot = Matrix.Translation(head) @ Matrix.Rotation(math.radians(deg), 4, ax) @ Matrix.Translation(-head)
    pb.matrix = rot @ pb.matrix
    bpy.context.view_layer.update()


def shoot(name, view):
    d = Vector(VIEWS[view]).normalized()
    cam.location = Vector((0, 0, 0.3)) + d * 3
    cam.rotation_euler = (-d).to_track_quat("-Z", "Y").to_euler()
    sc.render.filepath = str(out / ("%s.png" % name))
    bpy.ops.render.render(write_still=True)


edges = np.array([tuple(e.vertices) for e in body.data.edges])
reset()
rest_b, rest_s = evaluated(body), evaluated(sword)
rest_len = np.linalg.norm(rest_b[edges[:, 0]] - rest_b[edges[:, 1]], axis=1)
report = {"source": blend.name, "poses": {}}
shoot("pose-rest-3q", "3q")
for name, bone, axis, deg in TESTS:
    reset()
    rotate(bone, axis, deg)
    pb, ps = evaluated(body), evaluated(sword)
    ln = np.linalg.norm(pb[edges[:, 0]] - pb[edges[:, 1]], axis=1)
    ratio = ln / np.maximum(rest_len, 1e-9)
    report["poses"][name] = {"bone": bone, "axis": axis, "deg": deg,
                             "body_max_displacement_m": round(float(np.linalg.norm(pb - rest_b, axis=1).max()), 5),
                             "sword_max_displacement_m": round(float(np.linalg.norm(ps - rest_s, axis=1).max()), 5),
                             "edge_stretch_max": round(float(ratio.max()), 4),
                             "edge_stretch_p99": round(float(np.percentile(ratio, 99)), 4),
                             "edges_stretched_over_1_5x": int((ratio > 1.5).sum()),
                             "edge_compress_min": round(float(ratio.min()), 4)}
    shoot("pose-%s-%s" % (name, SIDE[name]), SIDE[name])
reset()
(out / "pose-review.json").write_text(json.dumps(report, indent=1, sort_keys=True) + "\n", encoding="utf-8")
print("POSE_REVIEW_OK", json.dumps({k: (v["edge_stretch_max"], v["edges_stretched_over_1_5x"]) for k, v in report["poses"].items()}))
