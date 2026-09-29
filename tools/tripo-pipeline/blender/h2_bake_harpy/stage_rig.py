"""H2 stage 5 — seat, parametric base, UM_HUMANOID_17 rig, weights, sockets, UM_FBX_v1 export and read-back
(headless only).

    blender -b --factory-startup --python stage_rig.py -- <profile.json> <run_dir>

Input <run>/work/h2-uv.blend (LP_* parts with UV0 in the authored frame at source scale; HP_tripo_part_7 = Tripo base,
reference of the seat) and the textures of textures.py. Steps (profile keys in brackets):
  1. seat [seat]: uniform scale about the Tripo base top centre so that base bottom -> figure top = figure_height_m,
     figure on the parametric base top (height base_height_m);
  2. parametric base [base_parametric] (candidate_build.base: chamfered cylinder, team band and instance pips in a
     vertex mask); the pip ring is turned to the azimuth offset with the largest clearance from the talons
     [base_parametric.pips.search_offsets_deg];
  3. armature [armature] (candidate_build.rig.make_armature, bones in the authored source frame, mapped by the seat);
  4. weights per part group [weights.groups]: rigid, bone heat, wing span, axis blend (candidate_build.rig), cleanup
     with ramps; then [weights.harmonise] cross-part blending: a vertex closer than distance_m to a vertex of a
     listed neighbour part moves its weights toward the mean of both (smoothstep of the distance), so touching parts
     deform together (the Tripo parts are separate shells; this is the "weld" where deformation needs it);
  5. join into the body mesh [names], one material slot, sockets [sockets] with the UE bone-space prediction;
  6. seam-gap probe: pairs of vertices of different parts closer than 3 mm at rest, their largest separation in the
     seven rig_deform_probe poses, with and without the harmonisation;
  7. <run>/work/h2-candidate.blend (authored frame), UM_FBX_v1 export of SK + base (candidate_build.core), read-back
     in a fresh scene (bones, hierarchy, triangles, slots, UV0, influences, bounds, face direction +X in the export
     frame) -> <run>/reports/h2-rig-report.json.
"""

import json
import math
import sys
import time
from pathlib import Path

import bmesh
import bpy
import numpy as np
from mathutils import Matrix, Vector
from mathutils.kdtree import KDTree

sys.path.insert(0, str(Path(__file__).resolve().parent))
import base_gold as BG  # noqa: E402
import common as C  # noqa: E402
import seal as SL  # noqa: E402
from candidate_build import core as CORE  # noqa: E402
from candidate_build.base import base_material, build_parametric_base  # noqa: E402
from candidate_build.mesh_ops import join_objects  # noqa: E402
from candidate_build.measure import ue_bone_local_from_blender_uu, ue_from_blender_m, ue_predicted  # noqa: E402
from candidate_build.rig import (axis_blend_weights, cleanup_weights, group_allowed_bones, heat_weights,  # noqa: E402
                                 make_armature, rigid_weights, smoothstep, wing_span_weights)

C.require_background("stage_rig.py")
args = C.script_args()
PROFILE_PATH, RUN = Path(args[0]).resolve(), Path(args[1]).resolve()
P = C.load_profile(PROFILE_PATH)
t0 = time.time()
checks = CORE.Checks()
src_blend = RUN / "work" / "h2-uv.blend"
bpy.ops.wm.open_mainfile(filepath=str(src_blend))
scene = bpy.context.scene
order = sorted(P["lowpoly"]["parts"], key=lambda n: int(n.rsplit("_", 1)[1]))
parts = {p: bpy.data.objects["LP_" + p] for p in order}
S = P["seat"]
ref = bpy.data.objects["HP_" + S["base_reference_part"]]
for o in list(scene.objects):
    if o.name.startswith("HP_") and o is not ref:
        bpy.data.objects.remove(o)
for m in [m for m in bpy.data.meshes if m.users == 0]:
    bpy.data.meshes.remove(m)
for im in [i for i in bpy.data.images if i.users == 0]:
    bpy.data.images.remove(im)

# ------------------------------------------------------------------ 0. seal (H2.1, profile "seal"; authored frame, source m)
SE = P.get("seal") or {}
seal_report = None
if SE:
    t_seal = time.time()
    seal_report = {}
    min_area = 1.2e-8 / float(S["expected_scale"]) ** 2  # 1.2 x the export check (1e-4 cm2 final) in source m2
    ex_all = tuple(SE.get("exclude_parts", []))
    if (SE.get("slivers") or {}).get("enabled"):
        seal_report["slivers"] = SL.fill_slivers(parts, exclude=ex_all + tuple(SE["slivers"].get("exclude_parts", [])),
                                                 min_area_m2=min_area)
    if (SE.get("lips") or {}).get("enabled"):
        Lc = SE["lips"]
        seal_report["lips"] = SL.add_lips(parts, contact_m=float(Lc["contact_m"]), overshoot_m=float(Lc["overshoot_m"]),
                                          tuck_m=float(Lc["tuck_m"]), min_len_m=float(Lc.get("min_len_m", 0.0004)),
                                          atlas_px=int(P["uv"]["atlas_px"]), max_uv_px=float(Lc.get("max_uv_px", 2.0)),
                                          exclude=ex_all + tuple(Lc.get("exclude_parts", [])),
                                          targets_only=tuple(Lc.get("targets_only", [])), mode=Lc.get("mode", "nearest"),
                                          min_area_m2=min_area)
    if (SE.get("core") or {}).get("enabled"):
        K = SE["core"]
        cme, cinfo = SL.inner_core(parts, K["box_parts"], voxel_m=float(K["voxel_m"]), margin_m=float(K["margin_m"]),
                                   rays=int(K.get("rays", 14)), min_inside_votes=int(K.get("min_inside_votes", 12)))
        if cme is None:
            raise RuntimeError("seal.core: no inside voxels")
        cme, finfo = SL.finish_core(scene, cme, int(K["target_triangles"]), list(parts.values()), float(K["margin_m"]),
                                    float(K.get("remesh_voxel_m", 0.003)))
        # one texel of a dark island for the whole core (only ever seen through sub-millimetre cracks)
        src_me = parts[K["uv_from_part"]].data
        sco = np.array([tuple(v.co) for v in src_me.vertices])
        vi = int(np.argmin(np.linalg.norm(sco - sco.mean(0), axis=1)))
        li = min(l.index for l in src_me.loops if l.vertex_index == vi)
        uv0 = tuple(src_me.uv_layers[0].data[li].uv)
        layer = cme.uv_layers.new(name="UVMap")
        for d in layer.data:
            d.uv = uv0
        for poly in cme.polygons:
            poly.use_smooth = True
        cme.name = "LP_" + K["name"]
        cobj = bpy.data.objects.new("LP_" + K["name"], cme)
        scene.collection.objects.link(cobj)
        parts[K["name"]] = cobj
        order.append(K["name"])
        tri_area = np.array([pl.area for pl in cme.polygons])
        seal_report["core"] = {**cinfo, **finfo, "uv": [round(c, 6) for c in uv0], "uv_from_part": K["uv_from_part"],
                               "min_triangle_area_m2": float(tri_area.min())}
    if (SE.get("exposed") or {}).get("enabled"):
        X = SE["exposed"]
        dirs = SL.game_directions(float(X.get("azimuth_step_deg", 10.0)), tuple(X.get("elevations_deg", (45.0, 55.0, 65.0))))
        only = set(X["parts"])
        exp = SL.exposed_backfaces(parts, dirs, bary_steps=int(X.get("bary_steps", 3)),
                                   exclude=tuple(p for p in parts if p not in only))
        seal_report["exposed"] = {}
        for p in sorted(only):
            if exp.get(p):
                SL.duplicate_reversed(parts[p], exp[p])
            seal_report["exposed"][p] = len(exp.get(p, []))
    seal_report["triangles_after"] = {p: sum(len(q.vertices) - 2 for q in parts[p].data.polygons) for p in order}
    seal_report["seconds"] = C.r(time.time() - t_seal, 1)
    seal_report["settings"] = SE

# ------------------------------------------------------------------ 1. seat
rco = np.array([tuple(v.co) for v in ref.data.vertices])
cx, cy = (rco[:, 0].min() + rco[:, 0].max()) / 2, (rco[:, 1].min() + rco[:, 1].max()) / 2
base_top_src = float(rco[:, 2].max())
top_src = max(max(v.co.z for v in o.data.vertices) for o in parts.values())
fz = float(S["base_height_m"])
s = (float(S["figure_height_m"]) - fz) / (top_src - base_top_src)
xform = (s, cx, cy, fz, base_top_src)
seat = Matrix.Translation((0, 0, fz)) @ Matrix.Diagonal((s, s, s, 1.0)) @ Matrix.Translation((-cx, -cy, -base_top_src))
bpy.data.objects.remove(ref)
for o in parts.values():
    o.data.transform(seat)
    o.data.update()


def to_final(axis, value):
    if axis == "x":
        return (value - cx) * s
    if axis == "y":
        return (value - cy) * s
    return fz + (value - base_top_src) * s


seat_report = {"scale": C.r(s, 6), "source_base_centre_xy_m": C.rv((cx, cy), 5), "source_base_top_z_m": C.r(base_top_src, 5),
               "source_figure_top_z_m": C.r(top_src, 5), "figure_height_m": S["figure_height_m"],
               "base_height_m": fz, "expected_scale_in_profile": S.get("expected_scale")}

# ------------------------------------------------------------------ 2. parametric base (pip ring offset search)
bcfg = json.loads(json.dumps(P["base_parametric"]))
pc = bcfg["pips"]
band = pc.get("clearance", {}).get("band_m", 0.015)
low_xy = np.array([(v.co.x, v.co.y) for o in parts.values() for v in o.data.vertices if v.co.z < fz + band])


def pip_centres(sectors, ring):
    out = []
    dphi = pc["arc_spacing_m"] / ring
    for sector in sectors:
        for k in (-1, 0, 1):
            a = math.radians(sector) + k * dphi
            out.append((ring * math.cos(a), ring * math.sin(a)))
    return np.array(out)


def clearance(sectors, ring):
    c = pip_centres(sectors, ring)
    d = np.sqrt(((c[:, None, :] - low_xy[None, :, :]) ** 2).sum(-1)).min(1) - pc["pip_radius_m"]
    return d


search = []
best = None
base_sectors = pc["sector_azimuths_deg"]
for ring in pc.get("search_ring_radii_m", [pc["ring_radius_m"]]):
    for off in range(*pc.get("search_offsets_deg", [0, 1, 1])):
        secs = [a + off for a in base_sectors]
        dmin = float(clearance(secs, ring).min())
        search.append((dmin, -abs(off if off <= 60 else off - 120), -ring, off, ring))
        if dmin >= pc["clearance"]["min_m"] and (best is None or (-abs(off if off <= 60 else off - 120), ring) >
                                                    (-abs(best[0] if best[0] <= 60 else best[0] - 120), best[1])):
            best = (off, ring, dmin)
    if best is not None:
        break
if best is None:
    top = max(search)
    best = (top[3], top[4], top[0])
pc["sector_azimuths_deg"] = [a + best[0] for a in base_sectors]
pc["ring_radius_m"] = best[1]
base, base_info = build_parametric_base(scene, bcfg, bcfg["mask"], P["names"]["base_object"], P["names"]["base_mesh"])
BMAT = P.get("base_material")
base_uv_report = None
if BMAT:  # H2.1 metal base: own UV layout + textures (base_gold / base_textures)
    base_uv_report = BG.uv_layout(base, {**bcfg, **BMAT}, pip_centres(pc["sector_azimuths_deg"], pc["ring_radius_m"]),
                                  pc["pip_radius_m"])
    tdir = RUN / "textures" / ("base_%dk" % max(1, int(BMAT["texture_px"]) // 1024))
    base.data.materials.append(BG.preview_material(
        {**BMAT, "material": bcfg["material"], "mask_attribute": bcfg["mask"]["attribute"]},
        {k: tdir / ("%s_%s.png" % (BMAT["texture_prefix"], k)) for k in ("BC", "N_OpenGL", "ORM")}))
else:
    base.data.materials.append(base_material(bcfg))
pip_clear = clearance(pc["sector_azimuths_deg"], pc["ring_radius_m"])
checks("base_pips_clear_of_feet", bool(pip_clear.min() > pc["clearance"]["min_m"]),
       {"offset_deg": best[0], "ring_radius_m": best[1], "min_xy_clearance_m": C.r(pip_clear.min(), 5),
        "sector_azimuths_deg": pc["sector_azimuths_deg"]}, "> %g m" % pc["clearance"]["min_m"])

# ------------------------------------------------------------------ 3. armature
arm_profile = {"armature": P["armature"]}
arm, bones_final = make_armature(scene, arm_profile, xform)
bone_names = [b[0] for b in P["armature"]["bones"]]

# ------------------------------------------------------------------ 4. weights
W = P["weights"]
rules = {}
for rule in W["groups"]:
    for part in rule["parts"]:
        rules[part] = rule
missing = sorted(set(order) - set(rules))
if missing:
    raise RuntimeError("no weight rule for parts %s" % missing)
wing_info = {}
for rule in W["groups"]:
    objs = [parts[p] for p in rule["parts"]]
    if "rigid" in rule:
        for obj in objs:
            rigid_weights(arm, obj, rule["rigid"])
    elif "wing_span" in rule:
        for p in rule["parts"]:
            wing_info[p] = wing_span_weights(arm, parts[p], rule["wing_span"], s)
    elif "axis_blend" in rule:
        for obj in objs:
            axis_blend_weights(arm, obj, rule["axis_blend"], to_final)
    else:
        heat_weights(scene, arm, objs, set(rule["heat"]))
cleanup = {}
for p in order:
    cleanup[p] = cleanup_weights(arm, parts[p], group_allowed_bones(rules[p]), rules[p], P["armature"]["max_influences"],
                                 W["clean_below"], to_final)


def read_weights(obj):
    names = {g.index: g.name for g in obj.vertex_groups}
    out = []
    for v in obj.data.vertices:
        out.append({names[g.group]: g.weight for g in v.groups if g.weight > 0})
    return out


def write_weights(obj, ws):
    for g in list(obj.vertex_groups):
        obj.vertex_groups.remove(g)
    groups = {}
    for i, w in enumerate(ws):
        for n, val in sorted(w.items()):
            if n not in groups:
                groups[n] = obj.vertex_groups.new(name=n)
            groups[n].add([i], val, "REPLACE")


def pair_list(max_d, connected):
    """(part_a, vi, part_b, vj, rest distance) for vertices of connected parts (weights.harmonise.pairs: parts that
    touch on the figure; left and right feet also touch at rest but are different limbs) closer than max_d."""
    trees = {}
    for p, o in parts.items():
        kd = KDTree(len(o.data.vertices))
        for v in o.data.vertices:
            kd.insert(v.co, v.index)
        kd.balance()
        trees[p] = kd
    pairs = []
    for a in order:
        for b in order:
            if a >= b or not ({(a, b), (b, a)} & connected):
                continue
            for v in parts[a].data.vertices:
                co, j, d = trees[b].find(v.co)
                if d < max_d:
                    pairs.append((a, v.index, b, j, d))
    return pairs


PROBES = [("head_turn", "head", "Z", 35), ("spine_bend_fwd", "spine", "X", 25), ("arm_l_raise", "arm_upper.L", "Y", -45),
          ("arm_r_raise", "arm_upper.R", "Y", 45), ("forearm_l_bend", "arm_lower.L", "X", -40),
          ("thigh_l_flex", "leg_upper.L", "X", -35), ("thigh_r_flex", "leg_upper.R", "X", -35)]


def seam_gaps(objs_by_part, pairs):
    """Largest separation (m, final) of the rest-near vertex pairs in each probe pose (rotation about the world axis
    through the bone head, as tools/tripo-pipeline/anim/rig_deform_probe.py)."""
    out = {}
    for tag, bone, axis, deg in PROBES:
        pb = arm.pose.bones[bone]
        head = arm.data.bones[bone].head_local.copy()
        rotm = Matrix.Translation(head) @ Matrix.Rotation(math.radians(deg), 4, axis) @ Matrix.Translation(-head)
        pb.matrix = rotm @ pb.matrix
        bpy.context.view_layer.update()
        dg = bpy.context.evaluated_depsgraph_get()
        pos = {}
        for p, o in objs_by_part.items():
            ev = o.evaluated_get(dg)
            me = ev.to_mesh()
            pos[p] = np.array([tuple(v.co) for v in me.vertices])
            ev.to_mesh_clear()
        worst = 0.0
        where = None
        for a, i, b, j, d0 in pairs:
            d = float(np.linalg.norm(pos[a][i] - pos[b][j]))
            if d - d0 > worst:
                worst, where = d - d0, (a, b)
        out[tag] = {"max_opening_m": C.r(worst, 5), "between": list(where) if where else None}
        for pbb in arm.pose.bones:
            pbb.matrix_basis = Matrix.Identity(4)
        bpy.context.view_layer.update()
    return out


pairs = pair_list(float(W.get("seam_probe_pair_distance_m", 0.003)),
                  {tuple(x) for x in (W.get("harmonise") or {}).get("pairs", [])})
gaps_before = seam_gaps(parts, pairs)
H = W.get("harmonise")
harmonise_report = None
if H:
    dist = float(H["distance_m"]) * s
    wts = {p: read_weights(o) for p, o in parts.items()}
    new = {p: [dict(w) for w in ws] for p, ws in wts.items()}
    trees = {}
    for p, o in parts.items():
        kd = KDTree(len(o.data.vertices))
        for v in o.data.vertices:
            kd.insert(v.co, v.index)
        kd.balance()
        trees[p] = kd
    moved = {}
    for a, b in H["pairs"]:
        for x, y in ((a, b), (b, a)):
            cnt = 0
            for v in parts[x].data.vertices:
                co, j, d = trees[y].find(v.co)
                if d >= dist:
                    continue
                f = smoothstep(1.0 - d / dist) * float(H.get("strength", 1.0))
                mine, theirs = wts[x][v.index], wts[y][j]
                mean = {n: 0.5 * (mine.get(n, 0.0) + theirs.get(n, 0.0)) for n in set(mine) | set(theirs)}
                blended = {n: (1 - f) * mine.get(n, 0.0) + f * mean[n] for n in mean}
                new[x][v.index] = blended
                cnt += 1
            moved["%s<-%s" % (x, y)] = cnt
    maxinf = int(P["armature"]["max_influences"])
    for p, ws in new.items():
        clean = []
        for w in ws:
            kept = {n: val for n, val in w.items() if val >= W["clean_below"]}
            if not kept:
                kept = {max(w, key=w.get): 1.0}
            kept = dict(sorted(kept.items(), key=lambda kv: (-kv[1], kv[0]))[:maxinf])
            tot = sum(kept.values())
            clean.append({n: val / tot for n, val in kept.items()})
        write_weights(parts[p], clean)
    harmonise_report = {"distance_m_final": C.r(dist, 5), "pairs": H["pairs"], "vertices_blended": moved}
# H2.1: parts that take the weights of the nearest vertex of other parts (the seal core deforms with the body)
copy_report = {}
for tgt, srcs in sorted((W.get("copy_nearest") or {}).items()):
    if tgt not in parts:
        continue
    kd = KDTree(sum(len(parts[q].data.vertices) for q in srcs))
    lut = []
    for q in srcs:
        wq = read_weights(parts[q])
        for v in parts[q].data.vertices:
            kd.insert(v.co, len(lut))
            lut.append(wq[v.index])
    kd.balance()
    ws = []
    for v in parts[tgt].data.vertices:
        _c, j, _d = kd.find(v.co)
        ws.append(dict(lut[j]))
    write_weights(parts[tgt], ws)
    copy_report[tgt] = {"from": srcs, "vertices": len(ws)}
gaps_after = seam_gaps(parts, pairs)

# ------------------------------------------------------------------ 5. join, material, sockets
N_ = P["names"]
for p, o in parts.items():
    attr = o.data.attributes.new("um_part", "INT", "FACE")
    attr.data.foreach_set("value", [order.index(p)] * len(o.data.polygons))
body = join_objects(scene, [parts[p] for p in order], parts[order[0]])
body.name = N_["body_object"]
body.data.name = N_["body_mesh"]
for mod in [m for m in body.modifiers if m.type == "ARMATURE"][1:]:
    body.modifiers.remove(mod)
body.data.materials.clear()
mat = bpy.data.materials.new(N_["material"])
try:
    mat.use_nodes = True
except AttributeError:
    pass
nt = mat.node_tree
bsdf = next(n for n in nt.nodes if n.type == "BSDF_PRINCIPLED")
tex_dir = RUN / "textures" / "4k"
prefix = P["textures"]["prefix"]
nodes = {}
for key, cs in (("BC", "sRGB"), ("N_OpenGL", "Non-Color"), ("ORM", "Non-Color")):
    img = bpy.data.images.load(str(tex_dir / ("%s_%s.png" % (prefix, key))))
    img.colorspace_settings.name = cs
    node = nt.nodes.new("ShaderNodeTexImage")
    node.image = img
    nodes[key] = node
nt.links.new(nodes["BC"].outputs["Color"], bsdf.inputs["Base Color"])
nm = nt.nodes.new("ShaderNodeNormalMap")
nt.links.new(nodes["N_OpenGL"].outputs["Color"], nm.inputs["Color"])
nt.links.new(nm.outputs["Normal"], bsdf.inputs["Normal"])
sep = nt.nodes.new("ShaderNodeSeparateColor")
nt.links.new(nodes["ORM"].outputs["Color"], sep.inputs["Color"])
nt.links.new(sep.outputs["Green"], bsdf.inputs["Roughness"])
nt.links.new(sep.outputs["Blue"], bsdf.inputs["Metallic"])
mat.use_backface_culling = True
body.data.materials.append(mat)
labels = np.empty(len(body.data.polygons), np.int32)
body.data.attributes["um_part"].data.foreach_get("value", labels)
part_polys = {p: np.nonzero(labels == k)[0] for k, p in enumerate(order)}


def part_points(part):
    vs = sorted({v for i in part_polys[part] for v in body.data.polygons[int(i)].vertices})
    return [body.matrix_world @ body.data.vertices[v].co for v in vs]


def bbox_centre(pts):
    return Vector([(min(p[a] for p in pts) + max(p[a] for p in pts)) / 2 for a in range(3)])


sockets = []
for sock in P["sockets"]:
    bone = arm.data.bones[sock["bone"]]
    tcfg = sock["target"]
    if tcfg["kind"] == "part_bbox_centre":
        target = bbox_centre(part_points(tcfg["part"]))
    elif tcfg["kind"] == "part_front_quartile":
        pts = sorted(part_points(tcfg["part"]), key=lambda p: p.y)
        front = pts[:max(1, len(pts) // 4)]
        target = sum(front, Vector()) / len(front)
    elif tcfg["kind"] == "bone_head":
        target = bone.head_local.copy()
    else:
        raise RuntimeError("socket target kind %r" % tcfg["kind"])
    local = bone.matrix_local.inverted() @ target
    local_uu = [c * 100 for c in local]
    ue_local = ue_bone_local_from_blender_uu(local_uu)
    sockets.append({"name": sock["name"], "bone": sock["bone"], "ue_bone": sock["bone"].replace(".", "_"),
                    "target_kind": tcfg["kind"], "target_part": tcfg.get("part"),
                    "target_blender_m": C.rv(target, 5), "target_ue_component_uu": ue_from_blender_m(target),
                    "offset_blender_bone_local_uu": [C.r(c, 3) + 0.0 for c in local_uu],
                    "offset_ue_bone_local_uu_predicted": ue_local, "location_uu_for_ue": ue_local,
                    "location_source": "predicted: UE bone space = (x, -y, z) of the Blender bone-local offset "
                                       "(RIG-CONTRACT §7); verify with a live get_socket_location against "
                                       "target_ue_component_uu", "purpose": sock.get("purpose"),
                    "status": "предложено"})

# measurements (authored final frame)
me = body.data
me.calc_loop_triangles()
vco = np.array([tuple(v.co) for v in me.vertices])
lo_b, hi_b = vco.min(0), vco.max(0)
bco = np.array([tuple(v.co) for v in base.data.vertices])
infl = [len([g for g in v.groups if g.weight > 0]) for v in me.vertices]
tri_area_cm2 = np.array([t.area for t in me.loop_triangles]) * 1e4
face_c = np.array(bbox_centre(part_points(P["anatomy"]["head_part"])))
face_box = P["lowpoly"]["parts"][P["anatomy"]["head_part"]]["priority_regions"][0]["box"]
fb_lo = np.array([to_final("x", face_box["min"][0]), to_final("y", face_box["min"][1]), to_final("z", face_box["min"][2])])
fb_hi = np.array([to_final("x", face_box["max"][0]), to_final("y", face_box["max"][1]), to_final("z", face_box["max"][2])])
fm = np.all((vco >= np.minimum(fb_lo, fb_hi)) & (vco <= np.maximum(fb_lo, fb_hi)), axis=1)
face_centroid = vco[fm].mean(0)
body_centroid = vco.mean(0)
radial = float(np.hypot(vco[:, 0], vco[:, 1]).max())
core_parts = [p for p in order if p not in P["anatomy"]["capsule_exclude_parts"]]
core_v = sorted({v for p in core_parts for i in part_polys[p] for v in me.polygons[int(i)].vertices})
radial_core = float(np.hypot(vco[core_v, 0], vco[core_v, 1]).max())
checks("body_triangles", True, len(me.loop_triangles))
checks("all_triangles", all(len(p.vertices) == 3 for p in me.polygons), sum(1 for p in me.polygons if len(p.vertices) != 3), 0)
checks("figure_top_m", abs(hi_b[2] - S["figure_height_m"]) < 1e-5, C.r(hi_b[2], 6), S["figure_height_m"])
checks("base_bottom_at_zero", abs(bco[:, 2].min()) < 1e-9, C.r(bco[:, 2].min(), 9), 0.0)
checks("face_ahead_of_body_minus_y", face_centroid[1] < body_centroid[1] - 0.02,
       {"face_centroid_y": C.r(face_centroid[1], 5), "body_centroid_y": C.r(body_centroid[1], 5)}, "face y < body y - 0.02")
checks("max_influences", max(infl) <= P["armature"]["max_influences"], max(infl), P["armature"]["max_influences"])
checks("no_unweighted_vertices", min(infl) >= 1, min(infl), ">= 1")
checks("no_triangles_below_1e-4_cm2", int((tri_area_cm2 < CORE.DEGENERATE_AREA_CM2).sum()) == 0,
       int((tri_area_cm2 < CORE.DEGENERATE_AREA_CM2).sum()), 0)
_bm_top = bmesh.new()
_bm_top.from_mesh(me)
topo_body = {"non_manifold_edges": sum(1 for e in _bm_top.edges if len(e.link_faces) > 2),
             "open_edges": sum(1 for e in _bm_top.edges if len(e.link_faces) == 1),
             "loose_vertices": sum(1 for v in _bm_top.verts if not v.link_faces)}
_bm_top.free()
checks("no_non_manifold_edges_body", topo_body["non_manifold_edges"] == 0, topo_body["non_manifold_edges"], 0)
checks("one_material_slot_body", len(body.material_slots) == 1, len(body.material_slots), 1)
checks("one_uv_layer_body", len(me.uv_layers) == 1, [l.name for l in me.uv_layers], ["UVMap"])
checks("bone_count", len(arm.data.bones) == len(P["armature"]["bones"]), len(arm.data.bones), len(P["armature"]["bones"]))
weights_share = {}
tot = 0.0
for v in me.vertices:
    for g in v.groups:
        n = body.vertex_groups[g.group].name
        weights_share[n] = weights_share.get(n, 0.0) + g.weight
        tot += g.weight
weights_share = {n: C.r(w / tot, 4) for n, w in sorted(weights_share.items())}

# ------------------------------------------------------------------ 7. save authored, export, read back
for o in list(scene.objects):
    if o.type in ("CAMERA", "LIGHT"):
        bpy.data.objects.remove(o)
if "um_part" in body.data.attributes:
    body.data.attributes.remove(body.data.attributes["um_part"])
n_tris_body = len(me.loop_triangles)
n_verts_body = len(me.vertices)
n_tris_base = sum(len(p.vertices) - 2 for p in base.data.polygons)
authored_bones = {b.name: (b.head_local.copy(), b.tail_local.copy(), b.parent.name if b.parent else None)
                  for b in arm.data.bones}
blend = RUN / "work" / "h2-candidate.blend"
bpy.ops.wm.save_as_mainfile(filepath=str(blend), compress=False, relative_remap=True)
preset_path = CORE_PRESET = C.REPO / P["fbx_preset"]
preset = CORE.load_preset(preset_path)
rot = CORE.export_rotation(preset)
data_scale = float(preset["temporary_data_scale"])
export_matrix = Matrix.Diagonal((data_scale, data_scale, data_scale, 1.0)) @ rot
CORE.transform_for_fbx(scene, arm, (body, base), export_matrix)
exp_face = (export_matrix.to_3x3() @ Vector(face_centroid)) - (export_matrix.to_3x3() @ Vector(body_centroid))
checks("export_frame_face_points_plus_x", exp_face.x > 0 and abs(exp_face.x) > abs(exp_face.y),
       C.rv(exp_face, 3), "+X (UM_FBX_v1 ref pose: FBX opened in Blender faces +X)")
sk_fbx = RUN / "export" / P["exports"]["skeletal_fbx"]
base_fbx = RUN / "export" / P["exports"]["base_fbx"]
CORE.export_pair(scene, arm, (body,), base, preset, sk_fbx, base_fbx)
lo_e = np.array([tuple(export_matrix @ Vector(p)) for p in (lo_b, hi_b)])
exp_bounds_cm = {"min": C.rv(np.minimum(lo_e[0], lo_e[1]), 3), "max": C.rv(np.maximum(lo_e[0], lo_e[1]), 3)}

bpy.ops.wm.read_factory_settings(use_empty=True)
rt = bpy.context.scene
CORE.import_fbx_into(rt, sk_fbx)
CORE.import_fbx_into(rt, base_fbx)
inv = rot.inverted()
arm_rt = next(o for o in rt.objects if o.type == "ARMATURE")
meshes_rt = [o for o in rt.objects if o.type == "MESH"]
body_rt = next(o for o in meshes_rt if o.name.startswith(N_["body_object"]))
base_rt = next(o for o in meshes_rt if o.name.startswith(N_["base_object"]))
# export frame checks before undoing the rotation
bpy.context.view_layer.update()
rt_bones = {b.name: b for b in arm_rt.data.bones}
checks("roundtrip_armature_object_name", arm_rt.name == P["armature"]["object"], arm_rt.name, P["armature"]["object"])
checks("roundtrip_bone_names", sorted(rt_bones) == sorted(authored_bones), sorted(rt_bones), sorted(authored_bones))
checks("roundtrip_hierarchy", all((rt_bones[n].parent.name if rt_bones[n].parent else None) == authored_bones[n][2]
                                  for n in rt_bones if n in authored_bones), None)
CORE.to_authored_frame(rt, inv)
bpy.context.view_layer.update()
mw = arm_rt.matrix_world
head_err = max(((mw @ rt_bones[n].head_local) - authored_bones[n][0]).length for n in authored_bones if n in rt_bones)
checks("roundtrip_bone_heads_m", head_err < 1e-4, C.r(head_err, 7), "< 1e-4")
rme = body_rt.data
rme.calc_loop_triangles()
rv_ = np.array([tuple(body_rt.matrix_world @ v.co) for v in rme.vertices])
checks("roundtrip_triangles", len(rme.loop_triangles) == n_tris_body, len(rme.loop_triangles), n_tris_body)
checks("roundtrip_bounds_m", float(np.abs(rv_.min(0) - lo_b).max()) < 1e-4 and float(np.abs(rv_.max(0) - hi_b).max()) < 1e-4,
       {"min": C.rv(rv_.min(0), 5), "max": C.rv(rv_.max(0), 5)}, {"min": C.rv(lo_b, 5), "max": C.rv(hi_b, 5)})
checks("roundtrip_material_slots_body", len(body_rt.material_slots) == 1, [s.name for s in body_rt.material_slots])
checks("roundtrip_uv0", len(rme.uv_layers) >= 1, [l.name for l in rme.uv_layers])
rinfl = [len([g for g in v.groups if g.weight > 0]) for v in rme.vertices]
checks("roundtrip_max_influences", max(rinfl) <= P["armature"]["max_influences"] and min(rinfl) >= 1,
       {"max": max(rinfl), "min": min(rinfl)})
rbase = base_rt.data
checks("roundtrip_base_triangles", sum(len(p.vertices) - 2 for p in rbase.polygons) == n_tris_base,
       sum(len(p.vertices) - 2 for p in rbase.polygons), n_tris_base)
checks("roundtrip_base_vertex_colours", len(rbase.color_attributes) >= 1, [a.name for a in rbase.color_attributes])
roundtrip = {"triangles_body": len(rme.loop_triangles), "vertices_body": len(rme.vertices),
             "triangles_base": sum(len(p.vertices) - 2 for p in rbase.polygons), "bones": len(rt_bones)}

report = {
    "schema": "unmatched.h2-bake.rig-report/1", "profile": C.rel(PROFILE_PATH), "profile_sha256": C.sha256(PROFILE_PATH),
    "blender": bpy.app.version_string, "input_blend_sha256": C.sha256(src_blend),
    "status": "измерено (technically exported, not art-accepted)",
    "seat": seat_report, "base": {"pips": base_info, "search_best": {"offset_deg": best[0], "ring_radius_m": best[1]},
                                  "clearance_m": C.r(pip_clear.min(), 5), "triangles": n_tris_base},
    "armature": {"object": P["armature"]["object"], "skeleton": P["armature"]["skeleton"], "bones_final_m": bones_final},
    "weights": {"wing_span": wing_info, "cleanup": cleanup, "harmonise": harmonise_report, "share_by_bone": weights_share,
                "copy_nearest": copy_report},
    "seal": seal_report, "topology_body": topo_body, "base_uv": base_uv_report,
    "seam_gap_probe": {"pairs": len(pairs), "pair_distance_m": W.get("seam_probe_pair_distance_m", 0.003),
                       "per_part_weights_only": gaps_before, "after_harmonise": gaps_after},
    "sockets": sockets,
    "measure": {"bounds_body_m": {"min": C.rv(lo_b, 5), "max": C.rv(hi_b, 5)},
                "span_uu": C.r((hi_b[0] - lo_b[0]) * 100, 2), "height_with_base_uu": C.r(hi_b[2] * 100, 2),
                "radial_max_uu": C.r(radial * 100, 2), "radial_core_uu": C.r(radial_core * 100, 2),
                "face_centroid_m": C.rv(face_centroid, 5), "body_centroid_m": C.rv(body_centroid, 5),
                "triangles_body": n_tris_body, "vertices_body": n_verts_body, "triangles_base": n_tris_base,
                "export_bounds_cm": exp_bounds_cm, "ue_predicted_bounds_uu": ue_predicted(exp_bounds_cm)},
    "exports": {"skeletal_fbx": {"path": C.rel(sk_fbx), "sha256": C.sha256(sk_fbx), "bytes": sk_fbx.stat().st_size},
                "base_fbx": {"path": C.rel(base_fbx), "sha256": C.sha256(base_fbx), "bytes": base_fbx.stat().st_size},
                "settings": CORE.export_settings_report(preset, P["fbx_preset"], preset_path, data_scale)},
    "roundtrip": roundtrip, "authored_blend": C.rel(blend),
    "checks": dict(checks), "checks_failed": checks.failed(), "seconds": C.r(time.time() - t0, 1)}
C.write_json(RUN / "reports" / "h2-rig-report.json", report)
print(C.STAGE_MARKER, "rig", "failed:", checks.failed(), flush=True)
