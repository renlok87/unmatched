"""Stage rig (headless): seat + scale, UM_HUMANOID_17 armature, proxy heat weights + per-part rules, sockets, seams in
probe poses, UM_FBX_v1 export (SK + base) and FBX readback.

    blender -b --factory-startup --python stage_rig.py -- <profile.json> <run_dir>

Frame: the low parts come in the Tripo frame (stage lowpoly); they are moved so the base axis (circle fit of the base
side wall) is at x = y = 0, the base bottom at z = 0, and scaled uniformly so the head top is rig.figure_height_m.
Weights (why a proxy): the Tripo parts are separate overlapping shells (no shared vertices), so per-part heat gives
each part its own field and the seams between parts open when a bone turns. Bone heat is solved once on a voxel
proxy of the whole body (one watertight shell), transferred to every part by closest-point barycentric
interpolation (the fields are continuous across the part seams), then restricted per part to its allowed bones with
ramps/caps (candidate_build.rig.cleanup_weights: no leg weight in the collar, fist on hand.R, ...). The sword and
the base are rigid / not skinned. Seam opening is measured in the 7 probe poses of rig_deform_probe.py.
Outputs: export/SK_*.fbx, export/SM_*.fbx, work/h2-rig-authored.blend, reports/rig-report.json.
"""

import math
import re
import sys
import time
from collections import Counter
from pathlib import Path

import bmesh
import bpy
import numpy as np
from mathutils import Matrix, Vector
from mathutils.bvhtree import BVHTree

sys.path.insert(0, str(Path(__file__).resolve().parent))
import bl  # noqa: E402
import pure as P  # noqa: E402
from candidate_build import core as CB  # noqa: E402  (read-only use: UM_FBX_v1 export, determinism pins)
from candidate_build import rig as CR  # noqa: E402  (read-only use: armature, cleanup_weights, rigid_weights)
from candidate_build import measure as CM  # noqa: E402

bl.require_background("stage_rig.py")
args = bl.script_args()
PROFILE_PATH, RUN = Path(args[0]).resolve(), Path(args[1]).resolve()
profile = P.load_json(PROFILE_PATH)
paths = P.run_paths(RUN)
for key in ("export", "reports", "work"):
    paths[key].mkdir(parents=True, exist_ok=True)
rc = profile["rig"]
t0 = time.time()
checks = CB.Checks()

bpy.ops.wm.open_mainfile(filepath=str(paths["work"] / "h2-lowpoly.blend"))
scene = bpy.context.scene
scene.name = "h2_rig"
low = {}
for o in scene.objects:
    if o.type == "MESH" and o.name.startswith("LP_"):
        low[o.name[3:] if o.name[3:] in profile["parts"] else o.name] = o

# ------------------------------------------------------------------ 1. seat and scale
base_src = low[rc["base_part"]]
cb, _, _ = bl.mesh_arrays(base_src)
zmin = float(cb[:, 2].min())
hb = float(cb[:, 2].max()) - zmin
wall = cb[(cb[:, 2] > zmin + 0.2 * hb) & (cb[:, 2] < zmin + 0.8 * hb)]
A = np.c_[2 * wall[:, 0], 2 * wall[:, 1], np.ones(len(wall))]
sol, *_ = np.linalg.lstsq(A, (wall[:, :2] ** 2).sum(axis=1), rcond=None)
cx, cy = float(sol[0]), float(sol[1])
radius = math.sqrt(sol[2] + cx * cx + cy * cy)
top_src = float(bl.mesh_arrays(low[rc["top_part"]])[0][:, 2].max())
s = float(rc["figure_height_m"]) / (top_src - zmin)
M = Matrix.Scale(s, 4) @ Matrix.Translation((-cx, -cy, -zmin))
for o in low.values():
    o.data.transform(M)
    o.data.update()


def to_final(axis, value):
    return {"x": (value - cx) * s, "y": (value - cy) * s, "z": (value - zmin) * s}[axis]


def fpt(p):
    return Vector(((p[0] - cx) * s, (p[1] - cy) * s, (p[2] - zmin) * s))


seat = {"scale": P.r(s, 6), "base_axis_tripo_m": [P.r(cx, 5), P.r(cy, 5)], "base_bottom_tripo_m": P.r(zmin, 5),
        "base_radius_tripo_m": P.r(radius, 5), "head_top_tripo_m": P.r(top_src, 5),
        "base_diameter_final_m": P.r(2 * radius * s, 5), "base_height_final_m": P.r(hb * s, 5),
        "method": "uniform scale about the base bottom centre (least-squares circle of the base side wall, 20-80 % of its height)"}

# ------------------------------------------------------------------ 2. atlas material (Blender preview; FBX slot name)
mat = bpy.data.materials.new(rc["material"])
mat.use_nodes = True
nt = mat.node_tree
bsdf = next(n for n in nt.nodes if n.bl_idname == "ShaderNodeBsdfPrincipled")
tex_dir = paths["textures"] / "runtime_2k"
prefix = profile["textures"]["prefix"]


def img_node(key, colour, x):
    img = bpy.data.images.load(str(tex_dir / ("%s_%s.png" % (prefix, key))), check_existing=True)
    img.colorspace_settings.name = "sRGB" if colour else "Non-Color"
    n = nt.nodes.new("ShaderNodeTexImage")
    n.image = img
    n.location = (x, 0)
    return n


n_bc = img_node("BC", True, -700)
n_orm = img_node("ORM", False, -700)
n_n = img_node("N_OpenGL", False, -700)
sep = nt.nodes.new("ShaderNodeSeparateColor")
nt.links.new(n_bc.outputs[0], bsdf.inputs["Base Color"])
nt.links.new(n_orm.outputs[0], sep.inputs[0])
nt.links.new(sep.outputs[1], bsdf.inputs["Roughness"])
nt.links.new(sep.outputs[2], bsdf.inputs["Metallic"])
nmap = nt.nodes.new("ShaderNodeNormalMap")
nt.links.new(n_n.outputs[0], nmap.inputs["Color"])
nt.links.new(nmap.outputs[0], bsdf.inputs["Normal"])
for o in low.values():
    o.data.materials.clear()
    o.data.materials.append(mat)

# ------------------------------------------------------------------ 3. part labels (face attribute)
part_index = {name: i for i, name in enumerate(sorted(low, key=bl.part_key))}
for name, o in low.items():
    attr = o.data.attributes.new(CB.PART_ATTR, "INT", "FACE")
    attr.data.foreach_set("value", [part_index[name]] * len(o.data.polygons))

# ------------------------------------------------------------------ 4. armature
xform = (s, cx, cy, 0.0, zmin)
arm, bone_final = CR.make_armature(scene, {"armature": rc["armature"]}, xform)
bone_names = [b[0] for b in rc["armature"]["bones"]]
weapon_fit = None
wf = rc.get("weapon_fit")
if wf:
    # the weapon bone lies on the PCA axis of the blade (part above the guard): head at the grip height, tail at the tip
    co_bl = bl.mesh_arrays(low[wf["blade_part"]])[0]
    pts = co_bl[co_bl[:, 2] > to_final("z", float(wf["blade_min_z_tripo"]))]
    cen = pts.mean(axis=0)
    _u, _s, vt = np.linalg.svd(pts - cen, full_matrices=False)
    dvec = vt[0] if vt[0][2] > 0 else -vt[0]
    t_tip = float(((co_bl - cen) @ dvec).max())
    t_head = (to_final("z", float(wf["grip_z_tripo"])) - cen[2]) / dvec[2]
    w_head, w_tail = cen + dvec * t_head, cen + dvec * t_tip
    bpy.context.view_layer.objects.active = arm
    bpy.ops.object.mode_set(mode="EDIT")
    eb = arm.data.edit_bones[rc["weapon_bone"]]
    eb.head, eb.tail = Vector(w_head.tolist()), Vector(w_tail.tolist())
    bpy.ops.object.mode_set(mode="OBJECT")
    bone_final[rc["weapon_bone"]] = [P.rv(w_head, 5), P.rv(w_tail, 5)]
    weapon_fit = {"blade_vertices": int(len(pts)), "axis": P.rv(dvec, 5), "head_m": P.rv(w_head, 5), "tail_m": P.rv(w_tail, 5),
                  "method": "PCA axis of the blade vertices above blade_min_z_tripo; head where the axis crosses the grip height, tail at the farthest vertex along the axis"}

# ------------------------------------------------------------------ 5. weights
groups = profile["groups"]
body_parts = [p for p in groups["body"] if p in low]
weapon_parts = [p for p in groups["weapon"] if p in low]
wcfg = rc["weights"]
# 5a. proxy: voxel remesh of the joined body copy, decimated, bone heat
proxy_objs = []
for p in body_parts:
    c = low[p].copy()
    c.data = low[p].data.copy()
    scene.collection.objects.link(c)
    proxy_objs.append(c)
for o in bpy.context.view_layer.objects:
    o.select_set(False)
for c in proxy_objs:
    c.select_set(True)
bpy.context.view_layer.objects.active = proxy_objs[0]
bpy.ops.object.join()
proxy = proxy_objs[0]
proxy.name = "H2_WEIGHT_PROXY"
proxy.data.remesh_voxel_size = float(wcfg["proxy_voxel_m"])
proxy.data.remesh_voxel_adaptivity = 0.0
bpy.ops.object.voxel_remesh()
dec = proxy.modifiers.new("dec", "DECIMATE")
dec.ratio = min(1.0, float(wcfg["proxy_faces"]) / max(len(proxy.data.polygons), 1))
dec.use_collapse_triangulate = True
bpy.ops.object.modifier_apply(modifier=dec.name)
# drop the voxel crumbs (tiny shells) and near-degenerate faces: the heat solver fails on them
bm = bmesh.new()
bm.from_mesh(proxy.data)
bmesh.ops.dissolve_degenerate(bm, edges=bm.edges, dist=float(wcfg["proxy_voxel_m"]) * 0.05)
seen, crumbs = set(), []
for f in bm.faces:
    if f.index in seen:
        continue
    stack, shell = [f], []
    seen.add(f.index)
    while stack:
        g = stack.pop()
        shell.append(g)
        for e in g.edges:
            for h in e.link_faces:
                if h.index not in seen:
                    seen.add(h.index)
                    stack.append(h)
    if len(shell) < int(wcfg["proxy_min_shell_faces"]):
        crumbs.extend(shell)
bmesh.ops.delete(bm, geom=crumbs, context="FACES")
bmesh.ops.delete(bm, geom=[v for v in bm.verts if not v.link_faces], context="VERTS")
bm.to_mesh(proxy.data)
bm.free()
proxy_stats = {"voxel_m": float(wcfg["proxy_voxel_m"]), "faces": len(proxy.data.polygons),
               "vertices": len(proxy.data.vertices), "crumb_faces_removed": len(crumbs),
               "topology": bl.edge_topology(proxy)}
heat_bones = set(wcfg["proxy_heat_bones"])
# Bone heat fails on small meshes (Laplacian solve at millimetre edge lengths: "failed to find solution"); the solve
# runs on a x heat_scale copy of the proxy and of the armature, the weights (per vertex) are kept, the copies dropped.
k = float(wcfg["heat_scale"])
arm_big = arm.copy()
arm_big.data = arm.data.copy()
scene.collection.objects.link(arm_big)
for o in bpy.context.view_layer.objects:
    o.select_set(False)
bpy.context.view_layer.objects.active = arm_big
arm_big.select_set(True)
bpy.ops.object.mode_set(mode="EDIT")
for eb in arm_big.data.edit_bones:
    eb.transform(Matrix.Scale(k, 4), scale=True, roll=True)
bpy.ops.object.mode_set(mode="OBJECT")
proxy.data.transform(Matrix.Scale(k, 4))
CR.heat_weights(scene, arm_big, [proxy], heat_bones)
proxy.parent = None
proxy.modifiers.clear()
proxy.data.transform(Matrix.Scale(1.0 / k, 4))
bpy.data.objects.remove(arm_big)
proxy_stats["heat_scale"] = k
pw_names = {g.index: g.name for g in proxy.vertex_groups}
nb = len(bone_names)
W = np.zeros((len(proxy.data.vertices), nb), dtype=np.float64)
bidx = {n: i for i, n in enumerate(bone_names)}
unweighted_proxy = 0
for v in proxy.data.vertices:
    tot = 0.0
    for g in v.groups:
        n = pw_names.get(g.group)
        if n in bidx and g.weight > 0:
            W[v.index, bidx[n]] += g.weight
            tot += g.weight
    if tot <= 0:
        unweighted_proxy += 1
proxy_stats["unweighted_vertices_after_heat"] = unweighted_proxy
proxy.data.calc_loop_triangles()
pco = np.array([v.co[:] for v in proxy.data.vertices])
ptris = np.array([t.vertices[:] for t in proxy.data.loop_triangles])
pbvh = BVHTree.FromPolygons([tuple(v) for v in pco], [tuple(int(i) for i in t) for t in ptris], all_triangles=True)


def bary(p, a, b, c):
    v0, v1, v2 = b - a, c - a, p - a
    d00, d01, d11 = v0.dot(v0), v0.dot(v1), v1.dot(v1)
    d20, d21 = v2.dot(v0), v2.dot(v1)
    den = d00 * d11 - d01 * d01
    if abs(den) < 1e-20:
        return (1.0, 0.0, 0.0)
    v = (d11 * d20 - d01 * d21) / den
    w = (d00 * d21 - d01 * d20) / den
    u = 1.0 - v - w
    u, v, w = max(u, 0.0), max(v, 0.0), max(w, 0.0)
    t = u + v + w
    return (u / t, v / t, w / t)


def quantize_weights(obj, levels):
    """Weights on a 1/levels grid summing to exactly `levels` per vertex (largest remainder; ties by bone name).
    UE stores skin weights as 8-bit by default, so 255 levels lose nothing the engine keeps; it also removes the
    run-to-run float noise of the heat solve (<= 3e-6, measured 2026-09-29) from the FBX bytes."""
    names = {g.index: g.name for g in obj.vertex_groups}
    groups = {g.name: g for g in obj.vertex_groups}
    changed = 0
    for v in obj.data.vertices:
        ws = sorted(((names[g.group], g.weight) for g in v.groups if g.weight > 0), key=lambda kv: kv[0])
        if not ws:
            continue
        tot = sum(w for _n, w in ws)
        raw = [(n, w / tot * levels) for n, w in ws]
        q = {n: int(x) for n, x in raw}
        rest = levels - sum(q.values())
        for n, x in sorted(raw, key=lambda kv: (-(kv[1] - int(kv[1])), kv[0]))[:rest]:
            q[n] += 1
        for gi in [g.group for g in v.groups]:
            obj.vertex_groups[gi].remove([v.index])
        for n, k in q.items():
            if k > 0:
                groups[n].add([v.index], k / float(levels), "REPLACE")
        changed += 1
    return {"levels": levels, "vertices": changed}


transfer_dist = []
weight_log = {}
rules = {}
for g in wcfg["groups"]:
    for p in g["parts"]:
        rules[p] = g
for p in body_parts:
    o = low[p]
    rule = rules[p]
    allowed = CR.group_allowed_bones(rule)
    vg = {n: o.vertex_groups.new(name=n) for n in bone_names}
    if "rigid" in rule:
        CR.rigid_weights(arm, o, rule["rigid"])
    else:
        for v in o.data.vertices:
            loc, _n, fi, dist = pbvh.find_nearest(v.co)
            transfer_dist.append(dist)
            t = ptris[fi]
            a, b, c = (Vector(pco[t[0]]), Vector(pco[t[1]]), Vector(pco[t[2]]))
            u, vv, w = bary(loc, a, b, c)
            row = W[t[0]] * u + W[t[1]] * vv + W[t[2]] * w
            for k in np.nonzero(row > 1e-4)[0]:
                vg[bone_names[k]].add([v.index], float(row[k]), "REPLACE")
        CR.bind_to_armature(arm, o)
    stats = CR.cleanup_weights(arm, o, allowed, rule, int(rc["armature"]["max_influences"]),
                               float(wcfg["clean_below"]), to_final)
    if wcfg.get("quantize_levels"):
        stats["quantized"] = quantize_weights(o, int(wcfg["quantize_levels"]))
    weight_log[p] = {"allowed": sorted(allowed), "cleanup": stats, "rule": rule.get("why", "")}
bpy.data.objects.remove(proxy)
td = np.array(transfer_dist)
proxy_stats["transfer_distance_mm"] = {"mean": P.r(td.mean() * 1000, 3), "p95": P.r(np.percentile(td, 95) * 1000, 3),
                                       "max": P.r(td.max() * 1000, 3)}
for p in weapon_parts:
    o = low[p]
    for n in bone_names:
        o.vertex_groups.new(name=n)
    CR.rigid_weights(arm, o, rc["weapon_bone"])
print("weights done", round(time.time() - t0, 1), flush=True)

# ------------------------------------------------------------------ 6. seams between parts in the probe poses
PROBES = [("head_turn", "head", "Z", 35), ("spine_bend_fwd", "spine", "X", 25), ("arm_l_raise", "arm_upper.L", "Y", -45),
          ("arm_r_raise", "arm_upper.R", "Y", 45), ("forearm_l_bend", "arm_lower.L", "X", -40),
          ("thigh_l_flex", "leg_upper.L", "X", -35), ("thigh_r_flex", "leg_upper.R", "X", -35)]
scfg = rc["seams"]
tol = float(scfg["contact_m"])
bvhs = {}
rest_co = {}
for p in body_parts:
    co, tris, _ = bl.mesh_arrays(low[p])
    rest_co[p] = (co, tris)
    bvhs[p] = BVHTree.FromPolygons([tuple(v) for v in co], [tuple(int(i) for i in t) for t in tris], all_triangles=True)
pairs = []
zranges = {}
for j in scfg["joints"]:
    if j.get("z_range_source"):
        zranges["%s|%s" % tuple(sorted(j["pair"], key=bl.part_key))] = [to_final("z", z) for z in j["z_range_source"]]
for i, pa in enumerate(body_parts):
    co_a = rest_co[pa][0]
    for pb in body_parts[i + 1:]:
        tris_b = rest_co[pb][1]
        co_b = rest_co[pb][0]
        found = []
        zr = zranges.get("%s|%s" % tuple(sorted((pa, pb), key=bl.part_key)))
        for vi, p in enumerate(co_a):
            if zr and not (zr[0] <= p[2] <= zr[1]):
                continue
            hit = bvhs[pb].find_nearest(Vector(p), tol)
            if hit[0] is not None:
                t = tris_b[hit[2]]
                bc = bary(hit[0], Vector(co_b[t[0]]), Vector(co_b[t[1]]), Vector(co_b[t[2]]))
                found.append((vi, t, bc, hit[3]))
        if len(found) >= int(scfg["min_contacts"]):
            pairs.append((pa, pb, found))


def evaluated(obj):
    dg = bpy.context.evaluated_depsgraph_get()
    ev = obj.evaluated_get(dg)
    me = ev.to_mesh()
    arr = np.empty(len(me.vertices) * 3)
    me.vertices.foreach_get("co", arr)
    ev.to_mesh_clear()
    return arr.reshape(-1, 3)


def rotate_bone(bone, axis, deg):
    pb = arm.pose.bones[bone]
    head = pb.head.copy()
    ax = {"X": Vector((1, 0, 0)), "Y": Vector((0, 1, 0)), "Z": Vector((0, 0, 1))}[axis]
    R = Matrix.Translation(head) @ Matrix.Rotation(math.radians(deg), 4, ax) @ Matrix.Translation(-head)
    pb.matrix = R @ pb.matrix
    bpy.context.view_layer.update()


seam_report = {"contact_m": tol, "contacts_per_pair": {"%s|%s" % (a, b): len(f) for a, b, f in pairs},
               "joints": scfg["joints"], "poses": {},
               "note": "joints = pairs of parts that continue one body surface (neck, shoulders, elbows, wrist, hips, collar); other contacts are layered garments (cloak over armour) that may slide apart"}
for name, bone, axis, deg in PROBES:
    for pb in arm.pose.bones:
        pb.matrix_basis = Matrix.Identity(4)
    bpy.context.view_layer.update()
    rotate_bone(bone, axis, deg)
    posed = {p: evaluated(low[p]) for p in body_parts}
    openings = []
    worst = {}
    for pa, pb_, found in pairs:
        A_, B_ = posed[pa], posed[pb_]
        for vi, t, bc, d0 in found:
            q = B_[t[0]] * bc[0] + B_[t[1]] * bc[1] + B_[t[2]] * bc[2]
            op = float(np.linalg.norm(A_[vi] - q)) - d0
            openings.append(op)
            key = "%s|%s" % (pa, pb_)
            worst[key] = max(worst.get(key, 0.0), op)
    op = np.array(openings)
    top = sorted(worst.items(), key=lambda kv: -kv[1])[:4]
    joint_keys = {"%s|%s" % tuple(sorted(j["pair"], key=bl.part_key)) for j in scfg["joints"]}
    jw = {k: v for k, v in worst.items() if k in joint_keys}
    seam_report["poses"][name] = {"bone": bone, "deg": deg,
                                  "joints_max_opening_mm": {k: P.r(v * 1000, 3) for k, v in sorted(jw.items())},
                                  "all_contacts_max_opening_mm": P.r(op.max() * 1000, 3),
                                  "all_contacts_p99_opening_mm": P.r(np.percentile(op, 99) * 1000, 3),
                                  "all_contacts_worst_pairs_mm": {k: P.r(v * 1000, 3) for k, v in top}}
for pb in arm.pose.bones:
    pb.matrix_basis = Matrix.Identity(4)
bpy.context.view_layer.update()
print("seams done", round(time.time() - t0, 1), flush=True)

# ------------------------------------------------------------------ 7. join
names_cfg = rc["objects"]


def join(parts, name, mesh_name):
    objs = [low[p] for p in parts]
    for o in bpy.context.view_layer.objects:
        o.select_set(False)
    for o in objs:
        o.select_set(True)
    bpy.context.view_layer.objects.active = objs[0]
    if len(objs) > 1:
        bpy.ops.object.join()
    ob = objs[0]
    ob.name = name
    ob.data.name = mesh_name
    mods = [m for m in ob.modifiers if m.type == "ARMATURE"]
    for m in mods[1:]:
        ob.modifiers.remove(m)
    return ob


body = join(body_parts, names_cfg["body"], names_cfg["body_mesh"])
sword = join(weapon_parts, names_cfg["weapon"], names_cfg["weapon_mesh"])
base = low[rc["base_part"]]
base.name = names_cfg["base"]
base.data.name = names_cfg["base_mesh"]
for o in (body, sword, base):
    o.data.update()

# ------------------------------------------------------------------ 8. measurements and checks
tris = {o.name: len(o.data.polygons) for o in (body, sword, base)}
total = sum(tris.values())
figure_parts = {part_index[p] for p in body_parts}


def face_points(obj, part_names):
    idx = {part_index[p] for p in part_names}
    vals = np.empty(len(obj.data.polygons), dtype=np.int64)
    obj.data.attributes[CB.PART_ATTR].data.foreach_get("value", vals)
    vs = set()
    for poly in obj.data.polygons:
        if vals[poly.index] in idx:
            vs.update(poly.vertices)
    return np.array([obj.data.vertices[i].co[:] for i in sorted(vs)])


head_pts = face_points(body, [rc["top_part"]])
head_top = float(head_pts[:, 2].max())
co_sw = np.array([v.co[:] for v in sword.data.vertices])
co_base = np.array([v.co[:] for v in base.data.vertices])
co_body = np.array([v.co[:] for v in body.data.vertices])
feet = face_points(body, rc["feet_parts"])
base_top = float(np.percentile(co_base[:, 2], 99.5))
geometry = {"triangles": tris, "triangles_total": total, "figure_height_m": P.r(head_top, 5),
            "sword_tip_m": P.r(co_sw[:, 2].max(), 5), "base_top_m_p99_5": P.r(base_top, 5),
            "feet_lowest_m": P.r(feet[:, 2].min(), 5),
            "radius_from_axis_m": P.r(max(np.hypot(co_body[:, 0], co_body[:, 1]).max(), np.hypot(co_sw[:, 0], co_sw[:, 1]).max()), 5),
            "bounds_body_m": {"min": P.rv(co_body.min(axis=0), 5), "max": P.rv(co_body.max(axis=0), 5)}}
lim = rc["proposed_limits_for_comparison_only"]
checks("triangles_in_proposed_h2_range", lim["hero_triangles"][0] <= total <= lim["hero_triangles"][1], total,
       lim["hero_triangles"], "proposed H2 guide, not a budget (GD-058 open)")
checks("height_52_56_uu", 0.52 <= head_top <= 0.56, P.r(head_top * 100, 3), [52, 56])
checks("base_30x6_uu", abs(seat["base_diameter_final_m"] - 0.30) < 0.01 and abs(seat["base_height_final_m"] - 0.06) < 0.005,
       [P.r(seat["base_diameter_final_m"] * 100, 2), P.r(seat["base_height_final_m"] * 100, 2)], [30, 6])
cap = lim["capsule_uu"]
checks("inside_capsule_36x62_uu", geometry["radius_from_axis_m"] * 100 <= cap["diameter"] / 2 and co_sw[:, 2].max() * 100 <= cap["height"],
       [P.r(geometry["radius_from_axis_m"] * 100, 2), P.r(co_sw[:, 2].max() * 100, 2)], cap)
checks("feet_on_base_top", -0.004 <= feet[:, 2].min() - base_top <= 0.003, P.r((feet[:, 2].min() - base_top) * 1000, 2),
       "[-4, +3] mm")
wsum = {o.name: CM.weight_summary(o, bone_names) for o in (body, sword)}
checks("weights_max_4_normalised_no_unweighted",
       all(w["max_influences"] <= 4 and w["unweighted_vertices"] == 0 and w["not_normalised_vertices"] == 0 for w in wsum.values()),
       {k: [v["max_influences"], v["unweighted_vertices"], v["not_normalised_vertices"]] for k, v in wsum.items()})
checks("sword_rigid_on_weapon_bone", wsum[sword.name]["bones_used"] == {rc["weapon_bone"]: len(sword.data.vertices)},
       wsum[sword.name]["bones_used"])
checks("bones_17_names", sorted(b.name for b in arm.data.bones) == sorted(bone_names) and len(bone_names) == 17,
       len(arm.data.bones))
checks("single_material_slot", all(len(o.material_slots) == 1 for o in (body, sword, base)),
       {o.name: len(o.material_slots) for o in (body, sword, base)})

# weapon bone vs the sword axis
wb = arm.data.bones[rc["weapon_bone"]]
axis_d = (wb.tail_local - wb.head_local).normalized()
rel_sw = co_sw - np.array(wb.head_local[:])
along = rel_sw @ np.array(axis_d[:])
radial = np.linalg.norm(rel_sw - np.outer(along, axis_d[:]), axis=1)
blade = along > 0.05 * (wb.tail_local - wb.head_local).length
radial_vec = rel_sw - np.outer(along, axis_d[:])
geometry["weapon_bone"] = {"head_m": P.rv(wb.head_local, 5), "tail_m": P.rv(wb.tail_local, 5),
                           "tip_error_m": P.r((Vector(co_sw[np.argmax(co_sw[:, 2])]) - wb.tail_local).length, 5),
                           "blade_centroid_off_axis_m": P.r(np.linalg.norm(radial_vec[blade].mean(axis=0)), 5),
                           "blade_median_radial_m": P.r(np.median(radial[blade]), 5)}
checks("weapon_bone_on_sword_axis", geometry["weapon_bone"]["tip_error_m"] < 0.004 and geometry["weapon_bone"]["blade_centroid_off_axis_m"] < 0.004,
       [geometry["weapon_bone"]["tip_error_m"], geometry["weapon_bone"]["blade_centroid_off_axis_m"]],
       "< 4 mm (tip; centroid of the blade vertices off the bone axis)")

# sockets
sockets = []
for sock in rc["sockets"]:
    bone = arm.data.bones[sock["bone"]]
    if sock["target"] == "bone_head":
        target = bone.head_local.copy()
    else:
        pts = face_points(body, [sock["target_part"]])
        target = Vector(((pts.min(axis=0) + pts.max(axis=0)) / 2).tolist())
    local = bone.matrix_local.inverted() @ target
    local_uu = [c * 100 for c in local]
    ue_local = CM.ue_bone_local_from_blender_uu(local_uu)
    sockets.append({"name": sock["name"], "bone": sock["bone"], "ue_bone": sock["bone"].replace(".", "_"),
                    "target": sock["target"], "target_blender_m": P.rv(target, 5),
                    "target_ue_component_uu": CM.ue_from_blender_m(target),
                    "offset_blender_bone_local_uu": [P.r(c, 3) + 0.0 for c in local_uu],
                    "offset_ue_bone_local_uu_predicted": ue_local,
                    "location_uu_for_ue": ue_local, "status": "предсказание (UE bone space = (x, -y, z)); проверить get_socket_location на UE-этапе"})

# ------------------------------------------------------------------ 9. save the authored blend
blend_out = paths["work"] / "h2-rig-authored.blend"
for o in list(scene.objects):
    if o.type == "MESH" and o not in (body, sword, base):
        bpy.data.objects.remove(o)
bpy.ops.wm.save_as_mainfile(filepath=str(blend_out), compress=False)

# ------------------------------------------------------------------ 10. export UM_FBX_v1
preset_path = P.REPO / profile["rig"]["fbx_preset"]
preset = CB.load_preset(preset_path)
rot = CB.export_rotation(preset)
CB.transform_for_fbx(scene, arm, (body, sword, base), Matrix.Scale(float(preset["temporary_data_scale"]), 4) @ rot)
sk_fbx = paths["export"] / rc["exports"]["skeletal_fbx"]
base_fbx = paths["export"] / rc["exports"]["base_fbx"]
# the exporter would embed the absolute .blend path (user profile, checkout location): pin it run-dir-relative
native_file = blend_out.relative_to(paths["run"]).as_posix()
with bl.fbx_native_file(native_file) as pin:
    CB.export_pair(scene, arm, (body, sword), base, preset, sk_fbx, base_fbx)
abs_markers = [m.encode("utf-8") for m in {str(P.REPO.resolve()), P.REPO.resolve().as_posix(), str(paths["run"])}]
abs_hits = {f.name: any(mk in f.read_bytes() for mk in abs_markers) for f in (sk_fbx, base_fbx)}
checks("fbx_no_absolute_blend_path", pin.hits == 2 and not any(abs_hits.values()),
       {"ApplicationNativeFile": native_file, "pinned_writes": pin.hits, "absolute_path_found": abs_hits},
       "ApplicationNativeFile = run-dir-relative path in both FBX; no absolute work/ path in the bytes")
export_info = {"skeletal_fbx": {"file": P.rel(sk_fbx), "sha256": P.sha256(sk_fbx), "bytes": sk_fbx.stat().st_size},
               "base_fbx": {"file": P.rel(base_fbx), "sha256": P.sha256(base_fbx), "bytes": base_fbx.stat().st_size},
               "application_native_file": native_file,
               "settings": CB.export_settings_report(preset, P.rel(preset_path), preset_path,
                                                    float(preset["temporary_data_scale"]))}
print("exported", round(time.time() - t0, 1), flush=True)

# ------------------------------------------------------------------ 11. readback
rb = {}
for key, path in (("skeletal", sk_fbx), ("base", base_fbx)):
    sc = bpy.data.scenes.new("h2_readback_" + key)
    CB.import_fbx_into(sc, path)
    arms_rb = [o for o in sc.objects if o.type == "ARMATURE"]
    meshes = [o for o in sc.objects if o.type == "MESH"]
    entry = {"armatures": [a.name for a in arms_rb], "meshes": {}}
    for mo in meshes:
        ms = CM.mesh_summary(mo)
        lo, hi = CM.world_bounds([mo])
        ms["bounds_m_fbx_frame"] = {"min": P.rv(lo, 5), "max": P.rv(hi, 5)}
        entry["meshes"][mo.name] = ms
    if arms_rb:
        a = arms_rb[0]
        mw = a.matrix_world
        entry["bones"] = {b.name: {"parent": b.parent.name if b.parent else None} for b in a.data.bones}
        L = (mw @ a.data.bones["arm_upper.L"].head_local + mw @ a.data.bones["leg_upper.L"].head_local) / 2
        R = (mw @ a.data.bones["arm_upper.R"].head_local + mw @ a.data.bones["leg_upper.R"].head_local) / 2
        side = (L - R)
        side.z = 0
        side.normalize()
        front = Vector((side.y, -side.x, 0.0))  # authored: left +X -> front -Y; the same turn in any frame
        entry["anatomy_fbx_frame"] = {"left_minus_right_xy": P.rv(side, 4), "front_xy": P.rv(front, 4),
                                      "yaw_deg_of_front_from_plus_x": P.r(math.degrees(math.atan2(front.y, front.x)), 2),
                                      "method": "side = mean(arm_upper, leg_upper heads) .L - .R; front = side turned -90 deg about Z"}
        root = a.data.bones["root"]
        entry["root_x_axis_fbx_frame"] = P.rv((mw.to_3x3() @ root.matrix_local.to_3x3()).col[0], 4)
        sw = next(o for o in meshes if o.name.startswith(names_cfg["weapon"]))
        bd = next(o for o in meshes if o.name.startswith(names_cfg["body"]))
        c_sw = CM.centroid(sw)
        c_bd = CM.centroid(bd)
        entry["weapon_minus_body_centroid_fbx_frame_m"] = P.rv(Vector(c_sw) - Vector(c_bd), 4)
        lo, hi = CM.world_bounds([sw, bd])
        entry["ue_predicted_bounds_uu"] = {"min": [P.r(lo[0] * 100, 2), P.r(-hi[1] * 100, 2), P.r(lo[2] * 100, 2)],
                                           "max": [P.r(hi[0] * 100, 2), P.r(-lo[1] * 100, 2), P.r(hi[2] * 100, 2)],
                                           "map": "ue(x, y, z) = fbx-in-Blender(x, -y, z) x 100 (UM_FBX_v1, ART-001/T4 measurements)"}
    rb[key] = entry
sk_rb = rb["skeletal"]
rb_tris = {k.split(".")[0]: v["triangles"] for k, v in sk_rb["meshes"].items()}
rb_tris.update({k.split(".")[0]: v["triangles"] for k, v in rb["base"]["meshes"].items()})
checks("readback_triangles", rb_tris == tris, rb_tris, tris)
checks("readback_one_armature_named",
       [re.sub(r"\.\d{3}$", "", a) for a in sk_rb["armatures"]] == [rc["armature"]["object"]] and rb["base"]["armatures"] == [],
       [sk_rb["armatures"], rb["base"]["armatures"]], note="a .NNN suffix only comes from the authored armature of this session")
checks("readback_17_bones_hierarchy", sorted(sk_rb["bones"]) == sorted(bone_names) and
       all(sk_rb["bones"][b[0]]["parent"] == b[1] for b in rc["armature"]["bones"]), len(sk_rb["bones"]))
allm = list(sk_rb["meshes"].values()) + list(rb["base"]["meshes"].values())
checks("readback_uv0_single_slot", all(m["uv_layers"] == ["UVMap"] and m["uv0_in_unit_square"] and len(m["material_slots"]) == 1
                                      for m in allm), [[m["uv_layers"], m["material_slots"]] for m in allm])
checks("readback_no_near_degenerate_triangles", all(m["near_degenerate_triangles"] == 0 for m in allm),
       [m["near_degenerate_triangles"] for m in allm], note="UE drops triangles below 1e-4 cm2")
an = sk_rb["anatomy_fbx_frame"]
checks("readback_face_plus_x", abs(an["yaw_deg_of_front_from_plus_x"]) <= 10, an["yaw_deg_of_front_from_plus_x"],
       "0 +- 10 deg (FBX in Blender; UE +X)")
wmb = sk_rb["weapon_minus_body_centroid_fbx_frame_m"]
checks("readback_weapon_front_and_right", wmb[0] > 0.01 and wmb[1] < -0.01, wmb,
       "x > 0 (front), y < 0 (right side in the FBX frame -> UE +Y)")

report = {"schema": "unmatched.h2-bake.rig/1", "profile": P.rel(PROFILE_PATH), "seat": seat,
          "armature": {"object": arm.name, "bones_final_m": bone_final, "skeleton": rc["skeleton"], "weapon_fit": weapon_fit},
          "weights": {"proxy": proxy_stats, "parts": weight_log, "summary": wsum}, "seams": seam_report,
          "geometry": geometry, "sockets": sockets, "exports": export_info, "readback": rb,
          "checks": dict(checks), "failed": checks.failed(), "authored_blend": P.rel(blend_out),
          "seconds": round(time.time() - t0, 1)}
P.write_json(paths["reports"] / "rig-report.json", report)
print(P.STAGE_MARKER, "rig", "failed:", checks.failed(), round(time.time() - t0, 1))
