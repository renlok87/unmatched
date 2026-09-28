"""Import the exported UM_FBX_v1 skeletal FBX and turn it back into the authored frame (face -Y), save a .blend
for tools/tripo-pipeline/anim/rig_deform_probe.py (its tests assume the authored frame: .L = +X, camera -Y).

Headless only: blender -b --factory-startup --python fbx_to_authored_blend.py -- <sk.fbx> <out.blend>

The FBX is imported as written (Blender FBX importer defaults); every root object is multiplied by the
inverse of the preset's +90 deg Z rotation. The source FBX is only read.
"""
import math
import sys
from pathlib import Path

import bpy
from mathutils import Matrix

if not bpy.app.background:
    raise RuntimeError("fbx_to_authored_blend.py: headless only (blender -b)")

src, out = [str(Path(a).resolve()) for a in sys.argv[sys.argv.index("--") + 1:][:2]]
bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.fbx(filepath=src)
inv = Matrix.Rotation(math.radians(-90.0), 4, "Z")
for obj in bpy.context.scene.objects:
    if obj.parent is None:
        obj.matrix_world = inv @ obj.matrix_world
bpy.context.view_layer.update()
bpy.ops.wm.save_as_mainfile(filepath=out, compress=False)
print("FBX_AUTHORED_OK", out, [o.name for o in bpy.context.scene.objects])
