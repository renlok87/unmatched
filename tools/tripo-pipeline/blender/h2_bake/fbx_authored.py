"""Import the exported UM_FBX_v1 skeletal FBX and turn it back into the authored frame (face -Y), save a .blend for
tools/tripo-pipeline/anim/rig_deform_probe.py (its tests assume the authored frame: .L = +X, camera at -Y).

Headless only: blender -b --factory-startup --python fbx_authored.py -- <sk.fbx> <out.blend> [<rotation_deg>=90]
(same procedure as the heroes' fbx_to_authored_blend.py; the source FBX is only read)."""

import math
import sys
from pathlib import Path

import bpy
from mathutils import Matrix

if not bpy.app.background:
    raise RuntimeError("fbx_authored.py: headless only (blender -b)")

args = sys.argv[sys.argv.index("--") + 1:]
src, out = str(Path(args[0]).resolve()), str(Path(args[1]).resolve())
deg = float(args[2]) if len(args) > 2 else 90.0
bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.fbx(filepath=src)
inv = Matrix.Rotation(math.radians(-deg), 4, "Z")
for obj in bpy.context.scene.objects:
    if obj.parent is None:
        obj.matrix_world = inv @ obj.matrix_world
bpy.context.view_layer.update()
bpy.ops.wm.save_as_mainfile(filepath=out, compress=False)
print("FBX_AUTHORED_OK", out, sorted(o.name for o in bpy.context.scene.objects))
