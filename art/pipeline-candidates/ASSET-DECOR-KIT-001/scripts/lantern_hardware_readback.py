"""ASSET-DECOR-KIT-001.LANTERN: door-hardware read-back of the exported FBX (independent of the build script).

Headless only (never touches live Blender sessions):
  blender -b --factory-startup --python-exit-code 1 \
      --python art/pipeline-candidates/ASSET-DECOR-KIT-001/scripts/lantern_hardware_readback.py -- \
      <fbx> <out.json> [band_lo=0.62] [band_hi=0.76] [cluster_gap_frac=0.03]

Frame: the FBX read back in Blender = UM_FBX_v1 export frame (asset front = +X; looking at the front, frame-left =
-Y, frame-right = +Y; UE shows it as (x, -y, z), ART-001). In the lantern head the pane panels are large quads, so
vertices in the height band [band_lo, band_hi] (fractions of the height) come from the door hardware and frame
corners only. Measured:
  - vertices per horizontal sector (front +X, frame-left -Y, back -X, frame-right +Y; 90 deg sectors around the
    footprint centre) and how many lie behind half of the largest forward extent: hardware duplicated on the side
    panels or on the back would put vertices there;
  - on the front, vertices split by lateral side (-Y / +Y) and clustered by height (gap > cluster_gap_frac of the
    height; 0.03: the knuckle rows of one hinge are 1.4-2 % apart, the two hinges ~6 %, measured on this FBX):
    tripo-stage-plan.json (hingeSideDecision) expects two hinges at frame-left (-Y) and the latch at frame-right
    (+Y) between them in height.
Measurement only; not an art acceptance.
"""
import json
import math
import sys

import bpy

args = sys.argv[sys.argv.index("--") + 1:]
fbx, out = args[0], args[1]
band = (float(args[2]) if len(args) > 2 else 0.62, float(args[3]) if len(args) > 3 else 0.76)
gap = float(args[4]) if len(args) > 4 else 0.03

bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.fbx(filepath=fbx)
objs = [o for o in bpy.context.scene.objects if o.type == "MESH"]
UU = 100.0  # Blender metres back to FBX centimetre numbers (= UE uu)
pts = [tuple(c * UU for c in (o.matrix_world @ v.co)) for o in objs for v in o.data.vertices]
lo = [min(p[i] for p in pts) for i in range(3)]
hi = [max(p[i] for p in pts) for i in range(3)]
H = hi[2] - lo[2]
cx, cy = (lo[0] + hi[0]) / 2, (lo[1] + hi[1]) / 2
z0, z1 = lo[2] + H * band[0], lo[2] + H * band[1]
sel = [(p[0] - cx, p[1] - cy, p[2]) for p in pts if z0 <= p[2] <= z1]
if not sel:
    raise SystemExit("no vertex in the band %s" % (band,))


def sector(x, y):
    a = math.degrees(math.atan2(y, x))
    if -45 <= a < 45:
        return "front_+X"
    if 45 <= a < 135:
        return "frame_right_+Y"
    if -135 <= a < -45:
        return "frame_left_-Y"
    return "back_-X"


sectors = {"front_+X": 0, "frame_left_-Y": 0, "frame_right_+Y": 0, "back_-X": 0}
for x, y, _z in sel:
    sectors[sector(x, y)] += 1
fmax = max(x for x, _y, _z in sel)
behind_half = sum(1 for x, _y, _z in sel if x < 0.5 * fmax)


def clusters(points):
    points = sorted(points, key=lambda p: p[2])
    groups, cur = [], [points[0]]
    for p in points[1:]:
        if p[2] - cur[-1][2] > gap * H:
            groups.append(cur)
            cur = []
        cur.append(p)
    groups.append(cur)
    res = []
    for g in groups:
        ys = [p[1] for p in g]
        res.append({"vertices": len(g),
                    "z_frac": [round((g[0][2] - lo[2]) / H, 4), round((g[-1][2] - lo[2]) / H, 4)],
                    "lateral_y_uu_min_mean_max": [round(min(ys), 3), round(sum(ys) / len(ys), 3), round(max(ys), 3)],
                    "forward_x_uu_max": round(max(p[0] for p in g), 3)})
    return res


front = [p for p in sel if p[0] >= 0.5 * fmax]  # front zone: at least half of the largest forward extent
left = clusters([p for p in front if p[1] < 0]) if any(p[1] < 0 for p in front) else []
right = clusters([p for p in front if p[1] > 0]) if any(p[1] > 0 for p in front) else []
latch_between = (len(left) == 2 and len(right) == 1 and left[0]["z_frac"][1] <= right[0]["z_frac"][0] + 0.01
                 and right[0]["z_frac"][1] <= left[1]["z_frac"][0] + 0.01)
res = {
    "fbx": fbx,
    "frame": "FBX read back in Blender = UM_FBX_v1 export frame: front +X, frame-left -Y, frame-right +Y (UE: x, -y, z)",
    "height_uu": round(H, 3),
    "band_frac": list(band),
    "cluster_gap_frac": gap,
    "band_z_uu": [round(z0, 3), round(z1, 3)],
    "vertices_in_band": len(sel),
    "vertices_by_sector": sectors,
    "forward_x_uu_max_in_band": round(fmax, 3),
    "forward_x_uu_min_in_band": round(min(x for x, _y, _z in sel), 3),
    "vertices_behind_half_of_max_forward": behind_half,
    "front_clusters_frame_left_minus_y": left,
    "front_clusters_frame_right_plus_y": right,
    "expected_by_tripo_stage_plan": "hinges x2 at frame-left (-Y), latch x1 at frame-right (+Y), latch height between the hinges",
    "hinge_latch_pattern_matches_plan": latch_between,
    "no_vertices_on_sides_or_back_in_band": behind_half == 0,
    "note": "Measurement only. Sector = 90 deg around the footprint centre; clusters split at height gaps > cluster_gap_frac of H.",
}
json.dump(res, open(out, "w", encoding="utf-8"), indent=2, ensure_ascii=False)
print("LANTERN_HARDWARE", json.dumps({k: res[k] for k in ("vertices_by_sector", "vertices_behind_half_of_max_forward",
                                                           "hinge_latch_pattern_matches_plan")}))
