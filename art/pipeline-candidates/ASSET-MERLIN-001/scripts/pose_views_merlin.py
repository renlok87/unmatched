"""Extra views of rig_deform_probe-style poses (headless only: blender -b --factory-startup):

    blender -b --factory-startup --python pose_views_merlin.py -- <candidate.blend> <out_dir> <name:bone:axis:deg:view,...>

Each item rotates one pose bone about a world axis through its head (as rig_deform_probe.py) and renders one
view: front, back, 3qr, 3ql, top, gamer / gamel (game camera direction, pitch -55, azimuth -+40), backr, backl.
Same EEVEE preview lights as review_merlin_candidate.py; orthographic, 800x900. Nothing is saved to the .blend.
"""
import bpy, sys, math
if not bpy.app.background:
    raise RuntimeError("pose_views_merlin.py: headless only (blender -b)")
from mathutils import Matrix, Vector
argv = sys.argv[sys.argv.index("--") + 1:]
import os
bpy.ops.wm.open_mainfile(filepath=os.path.abspath(argv[0])); out = os.path.abspath(argv[1])  # absolute: Blender resolves relative paths from the drive root
sc = bpy.context.scene
arm = next(o for o in sc.objects if o.type == "ARMATURE")
sc.render.engine = "BLENDER_EEVEE"; sc.view_settings.view_transform = "Standard"
sc.world = bpy.data.worlds.new("w"); sc.world.use_nodes = True
sc.world.node_tree.nodes["Background"].inputs[0].default_value = (0.5, 0.5, 0.5, 1)
sc.world.node_tree.nodes["Background"].inputs[1].default_value = 0.55
for name, rot, e in (("key", (50, 0, -30), 3.0), ("fill", (60, 0, 150), 1.3)):
    l = bpy.data.lights.new(name, "SUN"); l.energy = e; lo = bpy.data.objects.new(name, l); lo.rotation_euler = [math.radians(a) for a in rot]; sc.collection.objects.link(lo)
cam = bpy.data.objects.new("c", bpy.data.cameras.new("c")); sc.collection.objects.link(cam); sc.camera = cam
cam.data.type = "ORTHO"; cam.data.ortho_scale = 0.62; sc.render.resolution_x, sc.render.resolution_y = 800, 900
def reset():
    for pb in arm.pose.bones: pb.matrix_basis = Matrix.Identity(4)
    bpy.context.view_layer.update()
def rotate(bone, axis, deg):
    pb = arm.pose.bones[bone]; head = pb.head.copy()
    ax = {"X": Vector((1,0,0)), "Y": Vector((0,1,0)), "Z": Vector((0,0,1))}[axis]
    pb.matrix = Matrix.Translation(head) @ Matrix.Rotation(math.radians(deg), 4, ax) @ Matrix.Translation(-head) @ pb.matrix
    bpy.context.view_layer.update()
def shoot(name, d, tgt=(0,0,0.25), scale=0.62):
    d = Vector(d).normalized(); cam.data.ortho_scale = scale
    cam.location = Vector(tgt) + d * 3; cam.rotation_euler = (-d).to_track_quat("-Z", "Y").to_euler()
    sc.render.filepath = out + "/" + name + ".png"; bpy.ops.render.render(write_still=True)
tests = [(a.split(":")) for a in argv[2].split(",")]
for name, bone, axis, deg, view in tests:
    reset(); rotate(bone, axis, float(deg))
    views = {"front": (0,-1,0.1), "back": (0,1,0.1), "3qr": (-0.6,-0.75,0.3), "3ql": (0.6,-0.75,0.3), "top": (0.0,-0.3,1), "gamer": (-0.368,-0.439,0.819), "gamel": (0.368,-0.439,0.819), "backr": (-0.6,0.75,0.3), "backl": (0.6,0.75,0.3)}
    shoot(name + "-" + view, views[view])
reset()
print("POSE_FRONT_OK")
