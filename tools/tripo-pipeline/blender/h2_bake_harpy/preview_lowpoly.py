"""High-poly vs game mesh shape frames (headless only, Workbench studio light, label "blender").

    blender -b --factory-startup --python preview_lowpoly.py -- <run_dir> <out_dir> [blend_name]

Renders the same camera twice (HP_* only, then LP_* only) and writes <name>_hp.png / <name>_lp.png, plus a silhouette
IoU per view (object masks by flat black shading) into preview-lowpoly.json.
"""

import sys
from pathlib import Path

import bpy
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import common as C  # noqa: E402
import review as RV  # noqa: E402

C.require_background("preview_lowpoly.py")
args = C.script_args()
RUN, OUT = Path(args[0]).resolve(), Path(args[1]).resolve()
blend_name = args[2] if len(args) > 2 else "h2-lowpoly.blend"
OUT.mkdir(parents=True, exist_ok=True)
bpy.ops.wm.open_mainfile(filepath=str(RUN / "work" / blend_name))
scene = bpy.context.scene
hp = [o for o in scene.objects if o.type == "MESH" and o.name.startswith("HP_") and o.get("h2_role") != "occluder"]
occ = [o for o in scene.objects if o.type == "MESH" and o.get("h2_role") == "occluder"]
lp = [o for o in scene.objects if o.type == "MESH" and o.name.startswith("LP_")]
for o in occ:
    o.hide_render = True
cam = RV.setup_scene(scene)
scene.render.engine = "BLENDER_WORKBENCH"
scene.display.shading.light = "STUDIO"
scene.display.shading.color_type = "SINGLE"
scene.display.shading.single_color = (0.7, 0.7, 0.7)
scene.display.shading.show_backface_culling = True
views = {
    "front": ((0, -1, 0), (0, 0, 0.35), dict(ortho=0.92, res=(1200, 900))),
    "side_left": ((1, 0, 0), (0, 0, 0.35), dict(ortho=0.62, res=(900, 900))),
    "back": ((0, 1, 0), (0, 0, 0.35), dict(ortho=0.92, res=(1200, 900))),
    "top": ((0, 0, 1), (0, 0, 0.35), dict(ortho=1.0, res=(1100, 900))),
    "head_front": ((0, -1, 0.05), (0, -0.17, 0.48), dict(ortho=0.17, res=(900, 900))),
    "head_3q": ((-0.7, -0.7, 0.1), (0, -0.17, 0.48), dict(ortho=0.2, res=(900, 900))),
    "feet_front": ((0, -1, 0.3), (0, -0.05, 0.1), dict(ortho=0.28, res=(1000, 700))),
    "wing_tip_back": ((0.3, 1, 0.3), (0.35, 0.05, 0.4), dict(ortho=0.35, res=(900, 900))),
}
frames = {}
iou = {}
for tag, (d, t, kw) in views.items():
    masks = {}
    for label, show in (("hp", hp), ("lp", lp)):
        for o in hp + lp:
            o.hide_render = o not in show
        path = OUT / ("%s_%s.png" % (tag, label))
        frames["%s_%s" % (tag, label)] = RV.shoot(scene, cam, path, d, t, **kw)
        img = bpy.data.images.load(str(path))
        px = np.empty(img.size[0] * img.size[1] * 4, np.float32)
        img.pixels.foreach_get(px)
        px = px.reshape(-1, 4)
        bg = px[0, :3]
        masks[label] = np.abs(px[:, :3] - bg).sum(1) > 0.02
        bpy.data.images.remove(img)
    inter = (masks["hp"] & masks["lp"]).sum()
    union = (masks["hp"] | masks["lp"]).sum()
    iou[tag] = {"iou": C.r(inter / union, 5), "hp_px": int(masks["hp"].sum()), "lp_px": int(masks["lp"].sum()),
                "xor_px": int((masks["hp"] ^ masks["lp"]).sum())}
C.write_json(OUT / "preview-lowpoly.json", {"label": "blender (Workbench studio, not game light)",
                                            "frames": frames, "silhouette_iou": iou})
print(C.STAGE_MARKER, "preview_lowpoly", iou, flush=True)
