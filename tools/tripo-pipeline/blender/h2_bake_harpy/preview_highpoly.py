"""Preview frames of the H2 high-poly (headless only): textured and part-coloured orthographic views.

    blender -b --factory-startup --python preview_highpoly.py -- <run_dir> <out_dir>
"""

import sys
from pathlib import Path

import bpy

sys.path.insert(0, str(Path(__file__).resolve().parent))
import common as C  # noqa: E402
import review as RV  # noqa: E402

C.require_background("preview_highpoly.py")
args = C.script_args()
RUN, OUT = Path(args[0]).resolve(), Path(args[1]).resolve()
OUT.mkdir(parents=True, exist_ok=True)
bpy.ops.wm.open_mainfile(filepath=str(RUN / "work" / "h2-highpoly.blend"))
scene = bpy.context.scene
for m in bpy.data.materials:
    m.use_backface_culling = True
cam = RV.setup_scene(scene, samples=32)
parts = sorted([o for o in scene.objects if o.type == "MESH"], key=lambda o: int(o.name.rsplit("_", 1)[1]))
full = (0, 0, 0.317)
views = {"front": (0, -1, 0), "back": (0, 1, 0), "left": (1, 0, 0), "right": (-1, 0, 0), "top": (0, 0, 1)}
frames = {}
for tag, d in views.items():
    res = (1470, 1070) if tag in ("front", "back", "top") else (1070, 1070)
    scale = 1.08 if tag in ("front", "back", "top") else 0.78
    frames["hp_tex_" + tag] = RV.shoot(scene, cam, OUT / ("hp_tex_%s.png" % tag), d, full, ortho=scale, res=res)
# part colours (Workbench object colour)
scene.render.engine = "BLENDER_WORKBENCH"
scene.display.shading.light = "STUDIO"
scene.display.shading.color_type = "OBJECT"
for i, o in enumerate(parts):
    o.color = (*RV.PART_COLOURS[i % len(RV.PART_COLOURS)], 1)
for tag in ("front", "back", "left", "top"):
    d = views[tag]
    res = (1470, 1070) if tag in ("front", "back", "top") else (1070, 1070)
    scale = 1.08 if tag in ("front", "back", "top") else 0.78
    frames["hp_parts_" + tag] = RV.shoot(scene, cam, OUT / ("hp_parts_%s.png" % tag), d, full, ortho=scale, res=res)
C.write_json(OUT / "preview-highpoly.json", {"label": "blender", "frames": frames,
                                             "part_colours": {o.name: RV.PART_COLOURS[i % len(RV.PART_COLOURS)]
                                                              for i, o in enumerate(parts)}})
print(C.STAGE_MARKER, "preview_highpoly", flush=True)
