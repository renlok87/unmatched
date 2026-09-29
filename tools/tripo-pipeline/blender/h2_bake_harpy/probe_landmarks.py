"""Landmarks of a Tripo high-poly for a new profile (headless only; measurements, no edits).

    blender -b --factory-startup --python probe_landmarks.py -- <run_dir> <landmarks.json> <out.json>

Reads <run>/work/h2-highpoly.blend (stage_import; authored frame = source frame when the profile has no rotation) and a
landmark spec (JSON):
  {"torso": [parts], "head": part, "wings": {"L": [inner, outer], "R": [...]}, "thighs": {"L": p, "R": p},
   "feet": {"L": p, "R": p}, "bands": [parts], "skin": {"v_min": 0.45, "s_max": 0.4}, "contact_m": 0.008}
and reports per part: bounds, sampled base colour statistics (HSV of the Tripo BaseColor at the vertex UVs), the skin
vertices of the head part (bbox, front bbox), contact centroids (shoulders = inner wing within contact_m of the torso,
neck = head within 6 mm of the torso, knees/ankles = thigh/foot contact), wing leading-edge top and tips, talon front
quartiles and gold-coloured vertices of every part. Used to write the H3 profile (placement notes cite this file).
"""

import json
import sys
from pathlib import Path

import bpy
import numpy as np
from mathutils.kdtree import KDTree

sys.path.insert(0, str(Path(__file__).resolve().parent))
import common as C  # noqa: E402

C.require_background("probe_landmarks.py")
a = C.script_args()
RUN, SPEC, OUT = Path(a[0]).resolve(), json.loads(Path(a[1]).read_text(encoding="utf-8")), Path(a[2])
bpy.ops.wm.open_mainfile(filepath=str(RUN / "work" / "h2-highpoly.blend"))
hp = {o.name[3:]: o for o in bpy.context.scene.objects if o.type == "MESH" and o.name.startswith("HP_")}


def verts(p):
    me = hp[p].data
    co = np.empty(len(me.vertices) * 3, np.float32)
    me.vertices.foreach_get("co", co)
    return co.reshape(-1, 3).astype(np.float64)


def vertex_colours(p):
    """sRGB BaseColor at each vertex (first loop's UV, nearest texel)."""
    o = hp[p]
    me = o.data
    img = None
    for s in o.material_slots:
        if s.material and s.material.node_tree:
            for n in s.material.node_tree.nodes:
                if n.type == "TEX_IMAGE" and n.image and any(l.to_socket.name == "Base Color"
                                                            for l in s.material.node_tree.links if l.from_node == n):
                    img = n.image
    if img is None:
        return None
    w, h = img.size
    px = np.empty(w * h * 4, np.float32)
    img.pixels.foreach_get(px)
    px = px.reshape(h, w, 4)
    uv = np.empty(len(me.loops) * 2, np.float32)
    me.uv_layers[0].data.foreach_get("uv", uv)
    uv = uv.reshape(-1, 2)
    lv = np.empty(len(me.loops), np.int32)
    me.loops.foreach_get("vertex_index", lv)
    vuv = np.zeros((len(me.vertices), 2), np.float32)
    vuv[lv] = uv
    x = np.clip((vuv[:, 0] % 1.0) * w, 0, w - 1).astype(int)
    y = np.clip((vuv[:, 1] % 1.0) * h, 0, h - 1).astype(int)
    lin = px[y, x, :3]
    # Blender stores sRGB images as linear floats in .pixels only for float buffers; byte images are the file values
    if not img.is_float:
        return lin
    return np.where(lin <= 0.0031308, lin * 12.92, 1.055 * np.power(np.clip(lin, 0, 1), 1 / 2.4) - 0.055)


def hsv(rgb):
    mx, mn = rgb.max(1), rgb.min(1)
    s = np.where(mx > 1e-6, (mx - mn) / np.maximum(mx, 1e-6), 0)
    r, g, b = rgb[:, 0], rgb[:, 1], rgb[:, 2]
    hue = np.degrees(np.arctan2(np.sqrt(3) * (g - b), 2 * r - g - b)) % 360
    return hue, s, mx


def kd(p):
    v = verts(p)
    t = KDTree(len(v))
    for i, c in enumerate(v):
        t.insert(c, i)
    t.balance()
    return t


def near(p, others, d):
    v = verts(p)
    trees = [kd(q) for q in others]
    m = np.zeros(len(v), bool)
    for i, c in enumerate(v):
        for t in trees:
            if t.find(c)[2] < d:
                m[i] = True
                break
    return v[m]


def bb(v):
    return {"min": C.rv(v.min(0), 4), "max": C.rv(v.max(0), 4), "centroid": C.rv(v.mean(0), 4), "n": int(len(v))} \
        if len(v) else None


res = {"run": C.rel(RUN), "spec": SPEC, "parts": {}}
cols = {}
for p in sorted(hp, key=lambda n: int(n.rsplit("_", 1)[1])):
    v = verts(p)
    c = vertex_colours(p)
    cols[p] = c
    item = {"bounds": bb(v)}
    if c is not None:
        hue, s, val = hsv(c)
        gold = (hue > 30) & (hue < 62) & (s > 0.45) & (val > 0.45)
        item["colour"] = {"srgb_median": C.rv(np.median(c, 0), 3), "v_p10_p50_p90": C.rv(np.percentile(val, [10, 50, 90]), 3),
                          "s_p50": C.r(np.median(s), 3), "gold_vertex_fraction": C.r(gold.mean(), 4),
                          "dark_v_le_0_22_fraction": C.r((val <= 0.22).mean(), 4)}
        if gold.any():
            item["gold_bbox"] = bb(v[gold])
    res["parts"][p] = item

sk = SPEC.get("skin", {"v_min": 0.45, "s_max": 0.4})
hv = verts(SPEC["head"])
hue, s, val = hsv(cols[SPEC["head"]])
skin = (val > sk["v_min"]) & (s < sk["s_max"])
res["head_skin"] = bb(hv[skin])
front = skin & (hv[:, 1] < np.percentile(hv[skin][:, 1], 60)) if skin.any() else skin
res["head_skin_front60"] = bb(hv[front])
res["head_skin_central"] = bb(hv[skin & (np.abs(hv[:, 0]) < 0.045)])
res["neck"] = bb(near(SPEC["head"], SPEC["torso"], 0.006))
cm = float(SPEC.get("contact_m", 0.008))
res["shoulders"] = {sd: bb(near(parts[0], SPEC["torso"], cm)) for sd, parts in SPEC["wings"].items()}
res["wings"] = {}
for sd, parts in SPEC["wings"].items():
    v = np.concatenate([verts(q) for q in parts])
    top = v[np.argmax(v[:, 2])]
    ax = np.abs(v[:, 0])
    tip = v[ax >= np.percentile(ax, 98)]
    res["wings"][sd] = {"top_vertex": C.rv(top, 4), "tip_outer2pct_centroid": C.rv(tip.mean(0), 4), "bounds": bb(v)}
res["thigh_foot"] = {}
for sd in ("L", "R"):
    th, ft = SPEC["thighs"][sd], SPEC["feet"][sd]
    res["thigh_foot"][sd] = {"thigh_to_foot_contact": bb(near(th, [ft] + SPEC.get("bands", []), 0.006)),
                             "thigh_to_torso_contact": bb(near(th, SPEC["torso"], 0.006)),
                             "thigh_bounds": bb(verts(th)), "foot_bounds": bb(verts(ft))}
    fv = verts(ft)
    fr = fv[fv[:, 1] <= np.percentile(fv[:, 1], 25)]
    res["thigh_foot"][sd]["foot_front_quartile_centroid"] = C.rv(fr.mean(0), 4)
    fc = cols[ft]
    if fc is not None:
        h_, s_, v_ = hsv(fc)
        claw = (s_ < 0.3) & (v_ < 0.4)
        res["thigh_foot"][sd]["claw_vertices"] = bb(fv[claw])
for bnd in SPEC.get("bands", []):
    res.setdefault("bands", {})[bnd] = bb(verts(bnd))
C.write_json(OUT, res)
print(C.STAGE_MARKER, "probe_landmarks", flush=True)
