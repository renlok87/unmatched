"""Stage `rig` (headless Blender): final frame, UM_HUMANOID_17_v2 rig, weights, sockets, UM_FBX_v1 export, readback.

blender -b --factory-startup --python-exit-code 1 --python stage_rig.py -- <profile.json>

1. figure (body + staff): uniform scale s about the source base-top centre, seated on the normalised base top;
   base: normalised to base_footprint_m, pivot at the centre of its bottom (candidate metres, face -Y, Z up);
2. armature SKEL_UM_Humanoid from the profile bones (candidate_build.rig.make_armature, frame "source" mapped by
   the same transform); weapon.R under hand.R;
3. body weights per profile group on a temporary object of the group's parts (rigid, or bone heat restricted to
   the group's bones + candidate_build.rig.cleanup_weights: ramps, caps, max influences); vertices shared by
   several groups (welded seams) take the mean; seam sync: vertices of a part within radius of a seam vertex of
   the same part blend toward the seam weights (smoothstep); final cleanup (< clean_below, <= 4, normalised);
   staff 100 % weapon.R; the base is not skinned;
4. sockets (Weapon = weapon.R head; Head = bbox centre of the face part in head-bone space; crystal centre as a
   proposal) with the predicted UE bone-space offset (x, -y, z) (RIG-CONTRACT §7);
5. work/h2-rig.blend (authored frame, for rig_deform_probe.py; saved as a copy), UM_FBX_v1 export of SK (armature +
   body + staff) and SM (base) with the determinism pins of candidate_build.core, FBX readback checks.
The stage works in a factory session with the low-poly objects appended from work/h2-uv.blend, so no .blend is open
while exporting: the FBX carries an empty Original|ApplicationNativeFile and no host path (check export_no_host_path).
Report: reports/build-report.json.
"""

import math
import re
import sys
from collections import Counter
from pathlib import Path

import bmesh
import bpy
import numpy as np
from mathutils import Matrix, Vector
from mathutils.kdtree import KDTree

sys.path.insert(0, str(Path(__file__).resolve().parent))
import blib as B  # noqa: E402
import common as C  # noqa: E402
from candidate_build import core as CORE  # noqa: E402
from candidate_build import measure as MEAS  # noqa: E402
from candidate_build import rig as RIG  # noqa: E402

B.require_background("stage_rig.py")


def smoothstep(t):
    t = min(1.0, max(0.0, t))
    return t * t * (3 - 2 * t)


def transform_mesh(obj, fn):
    me = obj.data
    v = np.empty(len(me.vertices) * 3, np.float64)
    me.vertices.foreach_get("co", v)
    v = fn(v.reshape(-1, 3))
    me.vertices.foreach_set("co", v.astype(np.float32).ravel())
    me.update()


def group_object(body, parts_idx):
    tmp = body.copy()
    tmp.data = body.data.copy()
    tmp.name = "WGT_" + "_".join(str(p) for p in parts_idx)
    for m in list(tmp.modifiers):
        tmp.modifiers.remove(m)
    for g in list(tmp.vertex_groups):
        tmp.vertex_groups.remove(g)
    bpy.context.scene.collection.objects.link(tmp)
    me = tmp.data
    if "um_orig_vert" in me.attributes:
        me.attributes.remove(me.attributes["um_orig_vert"])
    me.attributes.new("um_orig_vert", "INT", "POINT")
    me.attributes["um_orig_vert"].data.foreach_set("value", np.arange(len(me.vertices), dtype=np.int32))
    part_of = B.int_face_attr(me, "um_part")
    bm = bmesh.new()
    bm.from_mesh(me)
    bm.faces.ensure_lookup_table()
    keep = set(np.nonzero(np.isin(part_of, parts_idx))[0].tolist())
    bmesh.ops.delete(bm, geom=[f for f in bm.faces if f.index not in keep], context="FACES")
    bmesh.ops.delete(bm, geom=[v for v in bm.verts if not v.link_faces], context="VERTS")
    bm.to_mesh(me)
    bm.free()
    return tmp


def read_weights(obj):
    names = {g.index: g.name for g in obj.vertex_groups}
    out = []
    for v in obj.data.vertices:
        out.append({names[g.group]: g.weight for g in v.groups if g.weight > 0})
    return out


def normalise(ws, clean_below, max_inf):
    kept = {n: w for n, w in ws.items() if w >= clean_below}
    if not kept:
        kept = {max(sorted(ws), key=lambda n: ws[n]): 1.0}
    if len(kept) > max_inf:
        kept = dict(sorted(kept.items(), key=lambda kv: (-kv[1], kv[0]))[:max_inf])
    t = sum(kept.values())
    return {n: w / t for n, w in sorted(kept.items())}


def write_weights(arm, obj, weights):
    for g in list(obj.vertex_groups):
        obj.vertex_groups.remove(g)
    groups = {}
    for b in arm.data.bones:
        groups[b.name] = obj.vertex_groups.new(name=b.name)
    by_bone = {}
    for i, ws in enumerate(weights):
        for n, w in ws.items():
            by_bone.setdefault((n, round(w, 6)), []).append(i)
    for (n, w), idx in sorted(by_bone.items()):
        groups[n].add(idx, w, "REPLACE")
    for g in list(obj.vertex_groups):
        if not any(n == g.name for (n, _w) in by_bone):
            obj.vertex_groups.remove(g)
    RIG.bind_to_armature(arm, obj)


def weight_stats(obj, weights, part_of_vert=None):
    share = Counter()
    maxinf = 0
    for ws in weights:
        maxinf = max(maxinf, len(ws))
        for n, w in ws.items():
            share[n] += w
    tot = sum(share.values())
    return {"vertices": len(weights), "max_influences": maxinf, "unweighted": sum(1 for ws in weights if not ws),
            "bone_share": {n: C.r(v / tot, 4) for n, v in sorted(share.items())}}


def main():
    prof = C.Profile(B.script_args()[0])
    for st in ("retopo", "uv"):
        if not C.load_json(prof.reports / ("%s-report.json" % st))["passed"]:
            raise RuntimeError("%s stage did not pass" % st)
    src = C.load_json(prof.reports / "source-report.json")
    # the low-poly objects are appended into a factory session instead of opening h2-uv.blend: bpy.data.filepath
    # stays "" and the FBX writer stores it as Original|ApplicationNativeFile (opening/saving a .blend put the host
    # path of work/h2-rig.blend into both FBX files, measured 2026-09-29)
    scene = B.empty_file()
    appended = B.append_objects(prof.work / "h2-uv.blend", "LP_")
    checks = {}
    objs = {k: appended["LP_" + k] for k in ("body", "staff", "base")}
    # ------------------------------------------------------------------ 1. final frame
    bmin = np.array(src["parts"]["tripo_part_1"]["bounds_m"]["min"])
    bmax = np.array(src["parts"]["tripo_part_1"]["bounds_m"]["max"])
    cx, cy = (bmin[0] + bmax[0]) / 2, (bmin[1] + bmax[1]) / 2
    base_top = bmax[2]
    top_src = src["parts"][prof["scale"]["top_part"]]["bounds_m"]["max"][2]
    fx, fy, fz = prof["scale"]["base_footprint_m"]
    s = (prof["scale"]["figure_height_m"] - fz) / (top_src - base_top)
    xform = (s, cx, cy, fz, base_top)

    def fig(v):
        return np.stack([(v[:, 0] - cx) * s, (v[:, 1] - cy) * s, fz + (v[:, 2] - base_top) * s], -1)

    # the base is normalised on its own low-poly bounds (decimation moves the extremes by ~0.1 mm), so the export
    # is exactly the footprint with the pivot at the centre of its bottom
    lb = B.verts_np(objs["base"])
    lbmin, lbmax = lb.min(0), lb.max(0)
    lcx, lcy = (lbmin[0] + lbmax[0]) / 2, (lbmin[1] + lbmax[1]) / 2
    bs = np.array([fx / (lbmax[0] - lbmin[0]), fy / (lbmax[1] - lbmin[1]), fz / (lbmax[2] - lbmin[2])])

    def basefn(v):
        return np.stack([(v[:, 0] - lcx) * bs[0], (v[:, 1] - lcy) * bs[1], (v[:, 2] - lbmin[2]) * bs[2]], -1)

    transform_mesh(objs["body"], fig)
    transform_mesh(objs["staff"], fig)
    transform_mesh(objs["base"], basefn)

    def to_final(axis, value):
        return {"x": (value - cx) * s, "y": (value - cy) * s, "z": fz + (value - base_top) * s}[axis]

    names = prof["objects"]
    mat = bpy.data.materials.new(prof["materials"]["atlas"])
    if mat.node_tree is None:
        mat.use_nodes = True
    for key, o in objs.items():
        o.name = names[key]["name"]
        o.data.name = names[key]["mesh"]
        o.data.materials.clear()
        o.data.materials.append(mat)
        o.data.polygons.foreach_set("material_index", np.zeros(len(o.data.polygons), np.int32))
    # ------------------------------------------------------------------ 2. armature
    arm, bones_final = RIG.make_armature(scene, prof.data, xform)
    arm.data.name = prof["armature"]["object"]
    bone_names = [b[0] for b in prof["armature"]["bones"]]
    # ------------------------------------------------------------------ 3. weights
    wcfg = prof["weights"]
    body = objs["body"]
    me = body.data
    part_of = B.int_face_attr(me, "um_part")
    vparts = [set() for _ in range(len(me.vertices))]
    for p in me.polygons:
        for vi in p.vertices:
            vparts[vi].add(int(part_of[p.index]))
    group_results = [[] for _ in range(len(me.vertices))]
    group_reports = []
    for gi, rule in enumerate(wcfg["groups"]):
        pidx = [C.part_index(p) for p in rule["parts"]]
        tmp = group_object(body, pidx)
        allowed = RIG.group_allowed_bones(rule)
        if "rigid" in rule:
            RIG.rigid_weights(arm, tmp, rule["rigid"])
            stats = {"rigid": rule["rigid"]}
        else:
            RIG.heat_weights(scene, arm, [tmp], allowed)
            stats = RIG.cleanup_weights(arm, tmp, allowed, rule, int(prof["armature"]["max_influences"]),
                                        float(wcfg["clean_below"]), to_final)
        ws = read_weights(tmp)
        orig = np.empty(len(tmp.data.vertices), np.int32)
        tmp.data.attributes["um_orig_vert"].data.foreach_get("value", orig)
        for w, o in zip(ws, orig):
            group_results[o].append(w)
        group_reports.append({"parts": rule["parts"], "allowed": sorted(allowed), "vertices": len(ws), "cleanup": stats})
        bpy.data.objects.remove(tmp)
    missing = [i for i, g in enumerate(group_results) if not g]
    if missing:
        raise RuntimeError("%d body vertices in no weight group" % len(missing))
    base_w = []
    for g in group_results:
        acc = Counter()
        for ws in g:
            for n, w in ws.items():
                acc[n] += w / len(g)
        base_w.append(dict(acc))
    # seam sync
    sync = wcfg["seam_sync"]
    R = float(sync["radius_m"]) * s
    V = B.verts_np(body)
    seam = [i for i, ps in enumerate(vparts) if len(ps) >= 2]
    synced = 0
    final_w = [dict(w) for w in base_w]
    for p in sorted(set(part_of.tolist())):
        sv = [i for i in seam if p in vparts[i]]
        if not sv:
            continue
        kd = KDTree(len(sv))
        for j, i in enumerate(sv):
            kd.insert(V[i], j)
        kd.balance()
        for i, ps in enumerate(vparts):
            if len(ps) != 1 or p not in ps:
                continue
            co, j, d = kd.find(V[i])
            if d >= R:
                continue
            t = smoothstep(d / R)
            ws_seam = base_w[sv[j]]
            mix = Counter()
            for n, w in ws_seam.items():
                mix[n] += (1 - t) * w
            for n, w in base_w[i].items():
                mix[n] += t * w
            final_w[i] = dict(mix)
            synced += 1
    final_w = [normalise(w, float(wcfg["clean_below"]), int(prof["armature"]["max_influences"])) for w in final_w]
    write_weights(arm, body, final_w)
    RIG.rigid_weights(arm, objs["staff"], wcfg["staff"]["rigid"])
    staff_w = read_weights(objs["staff"])
    for o in objs.values():
        o["um_object_key"] = o.get("um_object_key", "")
    weights_report = {"groups": group_reports, "seam_vertices": len(seam), "seam_sync_radius_m_final": C.r(R, 5),
                      "synced_vertices": synced, "body": weight_stats(body, final_w), "staff": weight_stats(objs["staff"], staff_w)}
    # per part dominant bones (measured)
    per_part = {}
    for p in sorted(set(part_of.tolist())):
        acc = Counter()
        vs = [i for i, ps in enumerate(vparts) if p in ps]
        for i in vs:
            for n, w in final_w[i].items():
                acc[n] += w
        tot = sum(acc.values())
        per_part["tripo_part_%d" % p] = {n: C.r(v / tot, 3) for n, v in sorted(acc.items(), key=lambda kv: -kv[1])[:4]}
    weights_report["per_part_top_bones"] = per_part
    # ------------------------------------------------------------------ 4. sockets
    def bbox_centre_part(obj, pk):
        pof = B.int_face_attr(obj.data, "um_part")
        vv = B.verts_np(obj)
        idx = sorted({vi for p in obj.data.polygons if pof[p.index] == pk for vi in p.vertices})
        pts = vv[idx]
        return Vector(((pts.min(0) + pts.max(0)) / 2).tolist())

    sockets = []
    for sock in prof["sockets"]:
        bone = arm.data.bones[sock["bone"]]
        if sock["target"] == "bone_head":
            target = bone.head_local.copy()
        else:
            pk = C.part_index(sock["part"])
            owner = objs["staff"] if prof["parts"][sock["part"]]["object"] == "staff" else body
            target = bbox_centre_part(owner, pk)
        local = bone.matrix_local.inverted() @ target
        local_uu = [c * 100 for c in local]
        ue_local = MEAS.ue_bone_local_from_blender_uu(local_uu)
        explicit = sock.get("location_uu")
        sockets.append({"name": sock["name"], "bone": sock["bone"], "ue_bone": sock["bone"].replace(".", "_"),
                        "target": sock["target"], "part": sock.get("part"), "target_blender_m": C.rv(target, 5),
                        "target_ue_component_uu": MEAS.ue_from_blender_m(target),
                        "offset_blender_bone_local_uu": [C.r(c, 3) + 0.0 for c in local_uu],
                        "offset_ue_bone_local_uu_predicted": ue_local,
                        "location_uu_for_ue": list(explicit) if isinstance(explicit, list) else ue_local,
                        "status": sock.get("status", "предложено")})
    # ------------------------------------------------------------------ measurements before export
    def bounds(obj_list):
        pts = np.concatenate([B.verts_np(o) for o in obj_list])
        return pts.min(0), pts.max(0)

    pof = B.int_face_attr(body.data, "um_part")
    vb = B.verts_np(body)
    hood_idx = sorted({vi for p in body.data.polygons if pof[p.index] == C.part_index(prof["scale"]["top_part"]) for vi in p.vertices})
    hood_top = float(vb[hood_idx][:, 2].max())
    lo_f, hi_f = bounds([body, objs["staff"]])
    lo_b, hi_b = bounds([objs["base"]])
    radial = float(np.max(np.linalg.norm(np.concatenate([B.verts_np(body), B.verts_np(objs["staff"])])[:, :2], axis=1)))
    tris = {o.name: len(o.data.polygons) for o in objs.values()}
    figure_tris = tris[names["body"]["name"]] + tris[names["staff"]["name"]]
    measures = {"scale_source_to_final": C.r(s, 6), "base_scale_xyz": C.rv(bs, 6),
                "hood_top_uu": C.r(hood_top * 100, 3), "figure_top_uu": C.r(hi_f[2] * 100, 3),
                "figure_bounds_uu": {"min": C.rv(lo_f * 100, 3), "max": C.rv(hi_f * 100, 3)},
                "base_bounds_uu": {"min": C.rv(lo_b * 100, 3), "max": C.rv(hi_b * 100, 3)},
                "figure_max_radius_uu": C.r(radial * 100, 3), "triangles": tris, "figure_triangles": figure_tris,
                "bones_final_m": bones_final}
    C.check(checks, "hood_top_45uu", abs(hood_top * 100 - prof["scale"]["figure_height_m"] * 100) < 0.05,
            C.r(hood_top * 100, 3), prof["scale"]["figure_height_m"] * 100)
    C.check(checks, "base_footprint", np.allclose((hi_b - lo_b) * 100, np.array(prof["scale"]["base_footprint_m"]) * 100, atol=0.02)
            and abs(lo_b[2]) < 1e-6, {"size": C.rv((hi_b - lo_b) * 100, 3), "min_z": C.r(lo_b[2] * 100, 4)}, [c * 100 for c in prof["scale"]["base_footprint_m"]])
    lo_t, hi_t = prof["budget_proposal"]["figure_triangles"]
    C.check(checks, "figure_triangles_in_proposed_band", lo_t <= figure_tris <= hi_t, figure_tris, [lo_t, hi_t], "proposal")
    C.check(checks, "bones_17_v2", len(bone_names) == 17 and "weapon.R" in bone_names and "weapon" not in bone_names,
            len(bone_names), 17)
    C.check(checks, "weapon_R_parent_hand_R", arm.data.bones["weapon.R"].parent.name == "hand.R",
            arm.data.bones["weapon.R"].parent.name, "hand.R")
    C.check(checks, "body_weights_valid", weights_report["body"]["unweighted"] == 0 and weights_report["body"]["max_influences"] <= 4,
            {k: weights_report["body"][k] for k in ("unweighted", "max_influences")}, {"unweighted": 0, "max_influences": "<= 4"})
    C.check(checks, "staff_rigid_weapon_R", weights_report["staff"]["bone_share"] == {"weapon.R": 1.0},
            weights_report["staff"]["bone_share"], {"weapon.R": 1.0})
    # weapon bone on the staff axis: grip within the staff hull, tail at the crystal top
    st_v = B.verts_np(objs["staff"])
    tail = np.array(arm.data.bones["weapon.R"].tail_local)
    C.check(checks, "weapon_tail_at_crystal_top", abs(tail[2] - st_v[:, 2].max()) < 0.002,
            C.r((tail[2] - st_v[:, 2].max()) * 100, 3), "|dz| < 0.2 uu")
    # ------------------------------------------------------------------ 5. rig blend + export
    B.save_blend_copy(prof.work / "h2-rig.blend")
    C.check(checks, "session_blend_path_empty", bpy.data.filepath == "", bpy.data.filepath != "", False,
            "measured value = a .blend path is open (the path itself is not written to the report)")
    preset_path = C.REPO / prof["exports"]["fbx_preset"]
    preset = CORE.load_preset(preset_path)
    rot = CORE.export_rotation(preset)
    data_scale = float(preset["temporary_data_scale"])
    skel = (body, objs["staff"])
    CORE.transform_for_fbx(scene, arm, skel + (objs["base"],), Matrix.Scale(data_scale, 4) @ rot)
    sk_fbx = prof.export / prof["exports"]["skeletal_fbx"]
    base_fbx = prof.export / prof["exports"]["base_fbx"]
    CORE.export_pair(scene, arm, skel, objs["base"], preset, sk_fbx, base_fbx)
    hits = {C.rel(p): len(C.host_path_hits(p)) for p in (sk_fbx, base_fbx)}
    C.check(checks, "export_no_host_path", not any(hits.values()), hits, {C.rel(p): 0 for p in (sk_fbx, base_fbx)},
            "number of absolute host paths (repo root, user home, <drive>:/Users/) in the FBX bytes")
    # ------------------------------------------------------------------ readback
    rt = bpy.data.scenes.new("h2_roundtrip")
    CORE.import_fbx_into(rt, sk_fbx)
    rtb = bpy.data.scenes.new("h2_roundtrip_base")
    CORE.import_fbx_into(rtb, base_fbx)
    raw = {re.sub(r"\.\d{3}$", "", o.name): o for sc in (rt, rtb) for o in sc.objects}
    rb = raw[names["body"]["name"]]
    rs = raw[names["staff"]["name"]]
    rbase = raw[names["base"]["name"]]
    rarm = next(o for o in rt.objects if o.type == "ARMATURE")
    # export frame (as read back, before undoing the rotation): face +X, weapon side -Y (UE +Y)
    rv_body = B.verts_np(rb)
    body_c = rv_body.mean(0)
    # face part centroid in the export frame via the authored face-part vertex set (same vertex order)
    face_part = C.part_index(next(sk["part"] for sk in prof["sockets"] if sk["name"] == "Head"))
    face_idx = sorted({vi for p in body.data.polygons if pof[p.index] == face_part for vi in p.vertices})
    face_c = rv_body[face_idx].mean(0) if len(rv_body) == len(body.data.vertices) else None
    staff_c = B.verts_np(rs).mean(0)
    Lh = np.array(rarm.matrix_world @ rarm.data.bones["arm_upper.L"].head_local)
    Rh = np.array(rarm.matrix_world @ rarm.data.bones["arm_upper.R"].head_local)
    lat = Lh - Rh
    yaw = math.degrees(math.atan2(lat[1], lat[0])) - 90.0  # lateral .L-.R = +Y  <=> face +X (yaw 0)
    exp_frame = {"body_centroid_uu": C.rv(body_c * 100, 3), "face_part_centroid_uu": C.rv(face_c * 100, 3) if face_c is not None else None,
                 "staff_centroid_uu": C.rv(staff_c * 100, 3), "lateral_L_minus_R": C.rv(lat, 4), "yaw_deg": C.r(yaw, 2)}
    C.check(checks, "export_face_plus_x", face_c is not None and face_c[0] - body_c[0] > 0.005 and abs(yaw) < 10,
            exp_frame, "face part ahead of the body centroid along +X by > 0.5 uu; lateral yaw 0 +- 10 deg (UE front +X)")
    C.check(checks, "export_staff_side_minus_y_blender_plus_y_ue", staff_c[1] - body_c[1] < -0.02,
            C.r((staff_c[1] - body_c[1]) * 100, 3), "< -2 uu (Blender export frame) = UE +Y")
    inv = rot.inverted()
    CORE.to_authored_frame(rt, inv)
    CORE.to_authored_frame(rtb, inv)
    rt_sk, rt_meshes = MEAS.roundtrip_measure(rt, bone_names)
    rt_base, rt_base_meshes = MEAS.roundtrip_measure(rtb, bone_names)
    rt_tris = {n: e["triangles"] for n, e in list(rt_sk["meshes"].items()) + list(rt_base["meshes"].items())}
    C.check(checks, "roundtrip_triangles", rt_tris == tris, rt_tris, tris)
    C.check(checks, "roundtrip_one_armature_named", rt_sk["armatures"] == 1 and rt_sk["armature_objects"] == [prof["armature"]["object"]],
            rt_sk["armature_objects"], [prof["armature"]["object"]])
    rt_bones = rt_sk["bones"]
    parents_ok = all(rt_bones[b]["parent"] == p for b, p, *_ in prof["armature"]["bones"] if b in rt_bones)
    heads_ok = all(np.allclose(rt_bones[b]["head_m"], bones_final[b][0], atol=2e-4) for b in bone_names if b in rt_bones)
    C.check(checks, "roundtrip_bones_hierarchy_positions", sorted(rt_bones) == sorted(bone_names) and parents_ok and heads_ok,
            {"bones": len(rt_bones), "parents_ok": parents_ok, "heads_within_0_02uu": heads_ok}, {"bones": 17})
    slots = {n: e["material_slots"] for n, e in list(rt_sk["meshes"].items()) + list(rt_base["meshes"].items())}
    C.check(checks, "roundtrip_material_slots", all(len(set(v)) == 1 and v[0] == prof["materials"]["atlas"] for v in slots.values()),
            slots, "1 slot %s on SK meshes and SM" % prof["materials"]["atlas"])
    uvs = {n: [e["uv_layers"], e["uv0_in_unit_square"]] for n, e in list(rt_sk["meshes"].items()) + list(rt_base["meshes"].items())}
    C.check(checks, "roundtrip_uv0", all(v[0] == ["UVMap"] and v[1] for v in uvs.values()), uvs, "one UVMap in [0,1]")
    rtw = {n: e["weights"] for n, e in rt_sk["meshes"].items()}
    C.check(checks, "roundtrip_weights", all(w and w["unweighted_vertices"] == 0 and w["max_influences"] <= 4 for w in rtw.values()),
            {n: {k: w[k] for k in ("unweighted_vertices", "max_influences")} for n, w in rtw.items()}, "0 unweighted, <= 4")
    lo_r, hi_r = MEAS.world_bounds([rt_meshes[names["body"]["name"]], rt_meshes[names["staff"]["name"]]])
    ratio = [C.r((hi_r[i] - lo_r[i]) / (hi_f[i] - lo_f[i]), 6) for i in range(3)]
    C.check(checks, "roundtrip_scale_ratio_1", all(abs(r - 1) < 1e-4 for r in ratio), ratio, [1, 1, 1])
    report = {"stage": "rig", "profile": C.rel(prof.path), "profile_id": prof["profile_id"], "blender": bpy.app.version_string,
              "skeleton": prof["armature"]["skeleton"], "armature_object": prof["armature"]["object"],
              "measures": measures, "weights": weights_report, "sockets": sockets, "export_frame": exp_frame,
              "exports": {"skeletal_fbx": {"path": C.rel(sk_fbx), "sha256": C.sha256(sk_fbx), "bytes": sk_fbx.stat().st_size},
                          "base_fbx": {"path": C.rel(base_fbx), "sha256": C.sha256(base_fbx), "bytes": base_fbx.stat().st_size},
                          "settings": CORE.export_settings_report(preset, prof["exports"]["fbx_preset"], preset_path, data_scale)},
              "roundtrip": {"skeletal": rt_sk, "base": rt_base, "scale_ratio": ratio},
              "checks": checks, "passed": all(c["passed"] for c in checks.values())}
    C.write_json(prof.reports / "build-report.json", report)
    print("H2_STAGE_OK rig passed=%s" % report["passed"])
    if not report["passed"]:
        raise RuntimeError("rig checks failed: %s" % sorted(k for k, c in checks.items() if not c["passed"]))


main()
