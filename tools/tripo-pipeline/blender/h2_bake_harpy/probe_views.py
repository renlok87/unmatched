"""Diagnostic views of a .blend (headless only): perspective frames around a target at given azimuths/elevations.

    blender -b --factory-startup --python probe_views.py -- <blend> <out_dir> <prefix> <tx,ty,tz> <distance> <fov> \
        <az:el>[ <az:el> ...]

Azimuth 0 = camera in -Y (the authored front), 90 = camera at +X (figure's left), 180 = +Y (back), -90 = -X.
A red cone marks -Y (authored front) 5 cm in front of the target. Label: blender preview, not game light.
"""

import math
import sys
from pathlib import Path

import bpy

sys.path.insert(0, str(Path(__file__).resolve().parent))
import common as C  # noqa: E402
import review as RV  # noqa: E402

C.require_background("probe_views.py")
a = C.script_args()
blend, out, prefix = Path(a[0]), Path(a[1]), a[2]
target = tuple(float(x) for x in a[3].split(","))
dist, fov = float(a[4]), float(a[5])
views = [tuple(float(x) for x in s.split(":")) for s in a[6:]]
out.mkdir(parents=True, exist_ok=True)
bpy.ops.wm.open_mainfile(filepath=str(blend))
scene = bpy.context.scene
for o in list(scene.objects):
    if o.type in ("CAMERA", "LIGHT"):
        bpy.data.objects.remove(o)
for m in bpy.data.materials:
    m.use_backface_culling = True
cam = RV.setup_scene(scene, samples=16)
bpy.ops.mesh.primitive_cone_add(radius1=0.006, depth=0.03, location=(target[0], target[1] - 0.12, target[2] + 0.1),
                                rotation=(math.radians(90), 0, 0))
cone = bpy.context.active_object
cone.data.materials.append(RV.flat_material("probe_red", (0.9, 0.05, 0.05)))
for az, el in views:
    d = (math.sin(math.radians(az)) * math.cos(math.radians(el)), -math.cos(math.radians(az)) * math.cos(math.radians(el)),
         math.sin(math.radians(el)))
    RV.shoot(scene, cam, out / ("%s_az%+04d_el%+03d.png" % (prefix, int(az), int(el))), d, target, fov_h=fov,
             distance=dist, res=(900, 900))
print(C.STAGE_MARKER, "probe_views", flush=True)
