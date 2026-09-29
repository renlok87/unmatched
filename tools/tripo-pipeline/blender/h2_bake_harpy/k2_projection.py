"""Projected size of the H2 figure in the game-camera frames (headless only; no rendering).

    blender -b --factory-startup --python k2_projection.py -- <profile.json> <run_dir>

Places the authored candidate at the cell used by the K2 review frames (x = +0.5 m), sets the game camera (horizontal
FOV 35, pitch -55, azimuth 0 = from the front) at K1 12 m, K2 7.5 m and 4.8 m, 1920x1080, and projects every body
vertex: bounding box in pixels, the face region (lowpoly face box mapped by the seat) and the base top diameter.
Writes <run>/reports/k2-projection.json.
"""

import json
import math
import sys
from pathlib import Path

import bpy
import numpy as np
from bpy_extras.object_utils import world_to_camera_view
from mathutils import Matrix, Vector

sys.path.insert(0, str(Path(__file__).resolve().parent))
import common as C  # noqa: E402
import review as RV  # noqa: E402

C.require_background("k2_projection.py")
a = C.script_args()
P = C.load_profile(a[0])
RUN = Path(a[1]).resolve()
RIG = json.loads((RUN / "reports" / "h2-rig-report.json").read_text(encoding="utf-8"))
bpy.ops.wm.open_mainfile(filepath=str(RUN / "work" / "h2-candidate.blend"))
scene = bpy.context.scene
body = bpy.data.objects[P["names"]["body_object"]]
cam = RV.setup_scene(scene)
offset = Vector((0.5, 0.0, 0.0))
vco = [body.matrix_world @ v.co + offset for v in body.data.vertices]
s = RIG["seat"]
cx, cy = s["source_base_centre_xy_m"]
box = P["lowpoly"]["parts"][P["anatomy"]["head_part"]]["priority_regions"][0]["box"]


def to_final(p):
    return Vector(((p[0] - cx) * s["scale"], (p[1] - cy) * s["scale"], s["base_height_m"] + (p[2] - s["source_base_top_z_m"]) * s["scale"]))


flo, fhi = to_final(box["min"]), to_final(box["max"])
lo = Vector([min(flo[i], fhi[i]) for i in range(3)])
hi = Vector([max(flo[i], fhi[i]) for i in range(3)])
face = [p for p in vco if all(lo[i] <= (p - offset)[i] <= hi[i] for i in range(3))]
out = {"label": "projection of the authored game mesh, no rendering", "camera": {"horizontal_fov_deg": 35, "pitch_deg": -55,
       "resolution": [1920, 1080], "figure_offset_m": list(offset)}, "frames": {}}
for name, dist in (("K1_12m", 12.0), ("K2_7.5m", 7.5), ("K2close_4.8m", 4.8)):
    RV.aim(scene, cam, RV.game_dir(0), (0, 0, 0.12), fov_h=35, distance=dist, res=(1920, 1080))
    bpy.context.view_layer.update()

    def bbox(pts):
        q = np.array([[c.x * 1920, (1 - c.y) * 1080] for c in (world_to_camera_view(scene, cam, p) for p in pts)])
        return [round(float(q[:, 0].max() - q[:, 0].min()), 1), round(float(q[:, 1].max() - q[:, 1].min()), 1)]

    base_pts = [offset + Vector((0.11 * math.cos(t), 0.11 * math.sin(t), 0.05)) for t in np.linspace(0, 2 * math.pi, 73)]
    out["frames"][name] = {"figure_bbox_px": bbox(vco), "face_region_bbox_px": bbox(face), "base_top_bbox_px": bbox(base_pts),
                           "mm_per_px_at_target": round(2 * dist * math.tan(math.radians(17.5)) / 1920 * 1000, 3)}
C.write_json(RUN / "reports" / "k2-projection.json", out)
print(C.STAGE_MARKER, "k2_projection", out["frames"], flush=True)
