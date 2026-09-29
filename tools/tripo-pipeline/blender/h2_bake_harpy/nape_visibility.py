"""Visible neck-cap pixels in the game camera (H2.1 nape gate; headless Blender only).

    blender -b --factory-startup --python nape_visibility.py -- <profile.json> <run_dir> [--out <json>] [--frames <dir>]
            [--parts cap_100[,...]] [--mark fill_102,patch_101] [--tag <name>]

The repair cap cap_100 closes the torso's neck opening under the nape. It must not read as a smooth "bald hood": this
stage counts, per game-camera frame, the pixels where the FIRST visible surface (back faces culled as in UE) is the
cap. Faces of the candidate body (<run>/work/h2-candidate.blend, rest pose, final frame) are labelled by matching
their corners to the seated LP_* parts of <run>/work/h2-uv.blend (exact vertex positions; the seal geometry of
stage_rig that is not in h2-uv.blend stays unlabelled = "other"). Workbench, flat attribute colour, no AA, 1920x1080,
horizontal FOV 35, pitch -55, target (0, 0, 0.12), azimuths every 20 deg, distances of profile
review.see_through.distances_m. Frames: red = cap, green = --mark parts (the nape fill), grey = rest.
Output <run>/reports/nape-visibility.json. Works on older runs too (e.g. the harpy-h2-bake/2 baseline).
"""

import json
import math
import sys
from pathlib import Path

import bpy
import numpy as np
from mathutils import Matrix, Vector
from mathutils.kdtree import KDTree

sys.path.insert(0, str(Path(__file__).resolve().parent))
import common as C  # noqa: E402
import see_through as ST  # noqa: E402

C.require_background("nape_visibility.py")
a = C.script_args()
P = C.load_profile(Path(a[0]).resolve())
RUN = Path(a[1]).resolve()
out = Path(a[a.index("--out") + 1]).resolve() if "--out" in a else RUN / "reports" / "nape-visibility.json"
frames_dir = Path(a[a.index("--frames") + 1]).resolve() if "--frames" in a else None
cap_parts = a[a.index("--parts") + 1].split(",") if "--parts" in a else ["cap_100"]
mark_parts = a[a.index("--mark") + 1].split(",") if "--mark" in a else ["fill_102", "patch_101"]
tag = a[a.index("--tag") + 1] if "--tag" in a else RUN.name
rig_rep = json.loads((RUN / "reports" / "h2-rig-report.json").read_text(encoding="utf-8"))
# seat exactly as stage_rig.py (the report rounds it): Tripo base part bounds, top of the LP parts
bpy.ops.wm.open_mainfile(filepath=str(RUN / "work" / "h2-uv.blend"))
S_ = P["seat"]
ref = bpy.data.objects["HP_" + S_["base_reference_part"]]
rco = np.array([tuple(v.co) for v in ref.data.vertices])
cx, cy = (rco[:, 0].min() + rco[:, 0].max()) / 2, (rco[:, 1].min() + rco[:, 1].max()) / 2
base_top_src = float(rco[:, 2].max())
top_src = max(max(v.co.z for v in o.data.vertices) for o in bpy.data.objects if o.type == "MESH" and o.name.startswith("LP_"))
fz = float(S_["base_height_m"])
s_ = (float(S_["figure_height_m"]) - fz) / (top_src - base_top_src)
seat = Matrix.Translation((0, 0, fz)) @ Matrix.Diagonal((s_, s_, s_, 1.0)) @ Matrix.Translation((-cx, -cy, -base_top_src))
M = np.array(seat)

# seated vertex sets of the labelled parts
sets = {}
for label, names in (("cap", cap_parts), ("mark", mark_parts)):
    pts = []
    for n in names:
        o = bpy.data.objects.get("LP_" + n)
        if o is None:
            continue
        co = np.empty(len(o.data.vertices) * 3, np.float32)
        o.data.vertices.foreach_get("co", co)
        co = co.reshape(-1, 3).astype(np.float64)
        pts.append(co @ M[:3, :3].T + M[:3, 3])
    if pts:
        pts = np.concatenate(pts)
        kd = KDTree(len(pts))
        for i, q in enumerate(pts):
            kd.insert(q, i)
        kd.balance()
        sets[label] = kd

bpy.ops.wm.open_mainfile(filepath=str(RUN / "work" / "h2-candidate.blend"))
scene = bpy.context.scene
N_ = P["names"]
body = bpy.data.objects[N_["body_object"]]
base = bpy.data.objects[N_["base_object"]]
for o in list(scene.objects):
    if o.type in ("CAMERA", "LIGHT"):
        bpy.data.objects.remove(o)
    elif o.type == "ARMATURE":
        o.hide_render = True
    elif o.type == "MESH" and o not in (body, base):
        o.hide_render = True
for o in (body, base):
    for m in list(o.modifiers):
        o.modifiers.remove(m)
me = body.data
co = np.empty(len(me.vertices) * 3, np.float32)
me.vertices.foreach_get("co", co)
co = co.reshape(-1, 3).astype(np.float64)
mw = np.array(body.matrix_world)
co = co @ mw[:3, :3].T + mw[:3, 3]
vlabel = np.zeros(len(co), np.int8)
for code, label in ((1, "cap"), (2, "mark")):
    if label in sets:
        for i, q in enumerate(co):
            _c, _j, d = sets[label].find(q)
            if d is not None and d < 2e-6:
                vlabel[i] = code
flab = np.zeros(len(me.polygons), np.int8)
for p in me.polygons:
    vs = [vlabel[v] for v in p.vertices]
    if all(x == vs[0] for x in vs):
        flab[p.index] = vs[0]
# the seal core (stage_rig, not in h2-uv.blend) is found by its single UV point (h2-rig-report seal.core.uv)
core_uv = ((rig_rep.get("seal") or {}).get("core") or {}).get("uv")
if core_uv:
    uvd = np.empty(len(me.loops) * 2, np.float32)
    me.uv_layers[0].data.foreach_get("uv", uvd)
    uvd = uvd.reshape(-1, 2)
    on = np.all(np.abs(uvd - np.array(core_uv, np.float32)) < 2e-6, axis=1)
    for p in me.polygons:
        if on[p.loop_start:p.loop_start + p.loop_total].all():
            flab[p.index] = 3
colours = {0: (0.3, 0.3, 0.3, 1.0), 1: (1.0, 0.0, 0.0, 1.0), 2: (0.0, 1.0, 0.0, 1.0), 3: (0.0, 0.0, 1.0, 1.0)}
attr = me.color_attributes.new("h2_nape", "FLOAT_COLOR", "CORNER")
cols = np.zeros((len(me.loops), 4), np.float32)
for p in me.polygons:
    cols[p.loop_start:p.loop_start + p.loop_total] = colours[int(flab[p.index])]
attr.data.foreach_set("color", cols.reshape(-1))
me.color_attributes.active_color = attr
battr = base.data.color_attributes.new("h2_nape", "FLOAT_COLOR", "CORNER")
battr.data.foreach_set("color", np.tile(np.array(colours[0], np.float32), len(base.data.loops)))
base.data.color_attributes.active_color = battr

cfg = dict(ST.DEFAULTS)
cfg.update({k: v for k, v in P.get("review", {}).get("see_through", {}).items() if k in ST.DEFAULTS})
cam = ST.setup(scene, cfg)
sh = scene.display.shading
sh.color_type = "VERTEX"
sh.show_backface_culling = True
scene.render.film_transparent = False
scene.render.image_settings.color_mode = "RGB"
w = bpy.data.worlds.new("h2_nape_world")
w.color = (0.0, 0.0, 0.0)
scene.world = w
target = Vector(cfg["target_m"])
tmp = RUN / "work" / "nape-tmp.png"
rows = []
for dist in cfg["distances_m"]:
    for az in cfg["azimuths_deg"]:
        d = ST.game_dir(az, cfg["pitch_deg"])
        cam.location = target + d * float(dist)
        cam.rotation_euler = (-d).to_track_quat("-Z", "Y").to_euler()
        scene.render.filepath = str(tmp)
        bpy.ops.render.render(write_still=True)
        im = bpy.data.images.load(str(tmp), check_existing=False)
        W_, H_ = im.size
        px = np.empty(W_ * H_ * 4, np.float32)
        im.pixels.foreach_get(px)
        bpy.data.images.remove(im)
        px = px.reshape(H_, W_, 4)[::-1, :, :3]
        red = (px[..., 0] > 0.8) & (px[..., 1] < 0.2) & (px[..., 2] < 0.2)
        green = (px[..., 1] > 0.8) & (px[..., 0] < 0.2)
        blue = (px[..., 2] > 0.8) & (px[..., 0] < 0.2) & (px[..., 1] < 0.2)
        grey = (np.abs(px[..., 0] - px[..., 1]) < 0.02) & (px[..., 0] > 0.2)
        figure = red | green | grey | blue
        row = {"azimuth_deg": az, "distance_m": dist, "cap_px": int(red.sum()), "mark_px": int(green.sum()),
               "core_px": int(blue.sum()), "figure_px": int(figure.sum())}
        rows.append(row)
        if frames_dir is not None and az % 60 == 0:
            frames_dir.mkdir(parents=True, exist_ok=True)
            ys, xs = np.nonzero(figure)
            if len(ys):
                y0, y1, x0, x1 = ys.min(), ys.max(), xs.min(), xs.max()
                crop = px[max(0, y0 - 10):y1 + 10, max(0, x0 - 10):x1 + 10]
                ST.save_rgb(crop, frames_dir / ("nape_%s_az%03d_d%.2f.png" % (tag, az, dist)))
        print("nape", dist, az, row["cap_px"], row["mark_px"], flush=True)
if tmp.exists():
    tmp.unlink()
run_label = C.rel(RUN)
if ":" in run_label or run_label.startswith("/"):  # outside the repository (e.g. a local copy of the H2 baseline run)
    run_label = "external:" + RUN.name
res = {"schema": "unmatched.h2-bake.nape-visibility/1", "run": run_label, "label": "blender Workbench, flat labels, "
       "back faces culled, no AA; not an UE frame", "cap_parts": cap_parts, "mark_parts": mark_parts,
       "labelled_faces": {"cap": int((flab == 1).sum()), "mark": int((flab == 2).sum()), "core": int((flab == 3).sum()),
                          "other": int((flab == 0).sum())},
       "total_core_px": int(sum(r["core_px"] for r in rows)),
       "worst_frame_core_px": int(max(r["core_px"] for r in rows)),
       "camera": {k: cfg[k] for k in ("resolution", "fov_h_deg", "pitch_deg", "target_m", "distances_m", "azimuths_deg")},
       "frames": rows,
       "total_cap_px": int(sum(r["cap_px"] for r in rows)),
       "by_distance": {str(dd): {"cap_px": int(sum(r["cap_px"] for r in rows if r["distance_m"] == dd)),
                                 "worst_frame_cap_px": int(max(r["cap_px"] for r in rows if r["distance_m"] == dd)),
                                 "figure_px": int(sum(r["figure_px"] for r in rows if r["distance_m"] == dd))}
                       for dd in cfg["distances_m"]}}
C.write_json(out, res)
print(C.STAGE_MARKER, "nape-visibility", res["total_cap_px"], flush=True)
