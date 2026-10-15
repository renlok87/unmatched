"""Read only the own HP GLB; measured provisional bone anchors, no rig authored."""
import sys
from pathlib import Path
import json
import numpy as np
import bpy

sys.dont_write_bytecode = True
OUT = Path(__file__).resolve().parent
REPO = OUT.parents[3]
sys.path.insert(0, str(REPO / "tools/tripo-pipeline/blender"))
from h2_bake import bl_util as U, profile as P

U.require_background()
U.reset()
source = REPO / "art/pipeline-candidates/ASSET-PATROCLUS-001/20261015-h2-tripo/source/patroclus-h2-tripo-e0b4d474-parts24.glb"
before = P.sha256(source)
parts = U.import_glb_parts(source, "MEASURE_")
raw = {n: U.coords(o.data) for n, o in parts.items()}
scale = {"figure_top_m": .43, "base_diameter_m": .24, "base_height_m": .05, "figure_top_part": "tripo_part_4"}
b = raw["tripo_part_1"]
f = P.frame_map((b.min(0), b.max(0)), float(raw["tripo_part_4"][:, 2].max()), scale)
points = {}
for n, c in raw.items():
    cx, cy = f["centre_xy_src"]
    if n == "tripo_part_1":
        sx, sy, sz = f["base_scale"]
        c = np.column_stack(((c[:, 0]-cx)*sx, (c[:, 1]-cy)*sy, (c[:, 2]-f["base_bottom_src"])*sz))
    else:
        s = f["figure_scale"]
        c = np.column_stack(((c[:, 0]-cx)*s, (c[:, 1]-cy)*s, .05+(c[:, 2]-f["base_top_src"])*s))
    points[n] = np.unique(np.round(c, 8), axis=0)

sections = {}
def section(label, ids, z, half=.0015):
    c = np.concatenate([points["tripo_part_%d" % i] for i in ids])
    band = c[np.abs(c[:, 2]-z) <= half]
    if len(band) < 3:
        raise RuntimeError("insufficient section " + label)
    low, high = band.min(0), band.max(0)
    anchor = (low+high)/2
    anchor[2] = z
    sections[label] = {"parts": ids, "z_m": z, "half_band_m": half,
                       "unique_sample_vertices": len(band), "bounds_m": [low.tolist(), high.tolist()],
                       "anchor_m": anchor.tolist(), "method": "midpoint of own unique-position band bounds; provisional HP anatomical anchor"}
    return anchor.tolist()

lm = {}
for side, ids in {"R": (15,9,16,14,7,23), "L": (17,11,18,10,12,22)}.items():
    upper, fore, hand, thigh, shin, toes = ids
    lm["shoulder."+side] = section("shoulder."+side, [upper], .303 if side == "R" else .292)
    lm["elbow."+side] = section("elbow."+side, [upper,fore], .258)
    lm["wrist."+side] = section("wrist."+side, [fore,hand], .226 if side == "R" else .230)
    lm["hand_tip."+side] = section("hand_tip."+side, [hand], .207 if side == "R" else .210)
    lm["hip."+side] = section("hip."+side, [thigh], .190)
    lm["knee."+side] = section("knee."+side, [thigh,shin], .133)
    lm["ankle."+side] = section("ankle."+side, [shin], .073)
    lm["toe."+side] = section("toe."+side, [toes], .0555, .002)
lm["neck"] = section("neck", [5], .328)
lm["head_top"] = section("head_top", [5], .368)
lm["waist"] = section("waist", [3], .248)
lm["chest"] = section("chest", [3], .305)
fist = points["tripo_part_16"]
grip = (fist.min(0)+fist.max(0))/2
blade = points["tripo_part_8"]
_, _, vt = np.linalg.svd(blade-blade.mean(0), full_matrices=False)
axis = vt[0]
if axis[2] > 0:
    axis = -axis
lm["weapon_grip"] = grip.tolist()
lm["weapon_axis_tail"] = (grip + axis*.04).tolist()
sections["weapon_grip"] = {"part": 16, "method": "own fist AABB midpoint; weapon axis from own blade unique-position PCA, distal sign -Z", "anchor_m": grip.tolist(), "axis_unit": axis.tolist(), "limitation": "provisional HP grip anchor, not proof of hidden handle continuity or deformation-safe grip"}
bones = [["root", None, [0,0,0], [0,0,.045]],
         ["hips","root",[0,0,.195],[0,0,.248]],
         ["spine","hips",[0,0,.248],[0,0,.323]],
         ["head","spine",lm["neck"],lm["head_top"]]]
for s in ["L", "R"]:
    bones += [["arm_upper."+s,"spine",lm["shoulder."+s],lm["elbow."+s]],
              ["arm_lower."+s,"arm_upper."+s,lm["elbow."+s],lm["wrist."+s]],
              ["hand."+s,"arm_lower."+s,lm["wrist."+s],lm["hand_tip."+s]]]
for s in ["L", "R"]:
    bones += [["leg_upper."+s,"hips",lm["hip."+s],lm["knee."+s]],
              ["leg_lower."+s,"leg_upper."+s,lm["knee."+s],lm["ankle."+s]],
              ["foot."+s,"leg_lower."+s,lm["ankle."+s],lm["toe."+s]]]
bones.append(["weapon.R","hand.R",lm["weapon_grip"],lm["weapon_axis_tail"]])
report = {"schema":"unmatched.patroclus-hp-landmarks/1", "source": str(source.relative_to(REPO)).replace("\\","/"),
          "sha256_before": before, "sha256_after": P.sha256(source), "scale": scale, "frame_map": f,
          "parts": {n:{"bounds_m":[c.min(0).tolist(),c.max(0).tolist()],"triangles":U.triangles(parts[n].data)} for n,c in points.items()},
          "landmarks_m":lm,"sections":sections,"proposed_bones":bones,
          "limitations":["Measured HP, not LP; remeasure LP after a separately authorized retopo.",
                          "Hips/spine centreline X=Y=0 are explicit anatomical proposals inside own torso bounds.",
                          "No closure, weights, rig, animation or art acceptance executed."]}
U.write_json(OUT / "measurements-own-hp.json", report)
print("OWN_MEASUREMENT_OK", len(parts), sum(x["triangles"] for x in report["parts"].values()), len(bones), flush=True)
