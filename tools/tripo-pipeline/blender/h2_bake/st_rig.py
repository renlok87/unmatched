"""Stage rig: UM_HUMANOID_17_v2 armature, positional weights, UM_FBX_v1 export and read-back.

Weights are a function of the vertex POSITION (profile rig.weights): every part of one limb uses the same joint
chain (e.g. spine -> arm_upper.L -> arm_lower.L -> hand.L), so coincident points of neighbouring parts (upper arm /
bracer / hand; thigh / greave / sandal) get identical weights and part seams stay closed in poses without welding
the meshes (measured by weight continuity at the junctions and by the probe poses). Rigid: bow -> weapon.L, quiver
-> spine, sandal toes -> foot. Head: z blend spine -> head at the neck, everything farther than r0..r1 from the
neck axis above z0..z1 (snakes, diadem) rigid on head. Dress/cloak: hips, spine above the waist, towards the hem
up to leg_max on the thigh of its side.

Junctions (profile rig.junctions, verify 2026-09-29): where a part meets a neighbour that moves with other bones
(dress collar <-> neck: the collar rim of the dress is spine, the neck rim of the head part is up to ~1.0 head at the
back, where the snake coils are rigid head — the collar opened 6.6–8.9 mm at head_turn 35°), the vertices of `part`
within band_m of its rim loop on `with` blend their weights towards the rule of `with` evaluated at the same position
(smoothstep of 1 - distance / band): the coincident rim points get identical weights and the junction cannot open,
the cloth band follows the neighbour (the collar hugs the neck). Contact caps (h2_cap faces from the close stage) are
weighted like any vertex of their part.

Export: candidate_build.core (read only) — UM_FBX_v1 rotation +90 deg about Z with EditBone.transform(roll=True),
data x100, FBX_SCALE_UNITS, Triangulate, UnitScaleFactor patched to 1.0, determinism pins; path_mode STRIP."""

import math
import re
from pathlib import Path

import bpy
import numpy as np
from mathutils import Matrix, Vector
from mathutils.kdtree import KDTree

from . import bl_util as U


def smoothstep(t):
    t = min(max(t, 0.0), 1.0)
    return t * t * (3.0 - 2.0 * t)


class Chain:
    def __init__(self, arm, bones, bands):
        self.bones = bones
        b = arm.data.bones
        self.pts = [Vector(b[bones[1]].head_local), Vector(b[bones[2]].head_local), Vector(b[bones[3]].head_local),
                    Vector(b[bones[3]].tail_local)]
        self.lens = [(self.pts[k + 1] - self.pts[k]).length for k in range(3)]
        self.S = [0.0, self.lens[0], self.lens[0] + self.lens[1], sum(self.lens)]
        self.bands = bands

    def param(self, p):
        best = None
        for k in range(3):
            a, b = self.pts[k], self.pts[k + 1]
            ab = b - a
            t = (p - a).dot(ab) / ab.length_squared
            lo = -math.inf if k == 0 else 0.0
            hi = math.inf if k == 2 else 1.0
            tc = min(max(t, lo), hi)
            d = (p - (a + ab * tc)).length
            s = self.S[k] + tc * self.lens[k]
            if best is None or d < best[0] - 1e-12:
                best = (d, s)
        return best[1]

    def weights(self, p):
        s = self.param(p)
        f = [smoothstep((s - (self.S[k] - self.bands[k])) / (2 * self.bands[k])) for k in range(3)]
        w = [1.0 - f[0], f[0] - f[1], f[1] - f[2], f[2]]
        return {self.bones[i]: max(w[i], 0.0) for i in range(4)}


def rule_weights(rule, p, arm, cache):
    kind = rule["kind"]
    if kind == "rigid":
        return {rule["bone"]: 1.0}
    if kind == "chain":
        key = tuple(rule["chain"]) + tuple(rule["bands_m"])
        if key not in cache:
            cache[key] = Chain(arm, rule["chain"], rule["bands_m"])
        return cache[key].weights(p)
    if kind == "zblend":
        (b0, z0), (b1, z1) = rule["stops"]
        t = smoothstep((p.z - z0) / (z1 - z0))
        ro = rule.get("rigid_outside")
        if ro:
            rad = math.hypot(p.x - ro["axis_xy"][0], p.y - ro["axis_xy"][1])
            fr = smoothstep((rad - ro["r0"]) / (ro["r1"] - ro["r0"])) * smoothstep((p.z - ro["z0"]) / (ro["z1"] - ro["z0"]))
            if ro["bone"] == b1:
                t = t + (1.0 - t) * fr
        return {b0: 1.0 - t, b1: t}
    if kind == "cloth":
        z0, z1 = rule["top_blend_z"]
        top = smoothstep((p.z - z0) / (z1 - z0))
        legs = rule["leg_max"] * smoothstep((rule["leg_start_z"] - p.z) / (rule["leg_start_z"] - rule["leg_full_z"]))
        side_l = smoothstep((p.x + rule["side_band_m"]) / (2 * rule["side_band_m"]))
        rest = 1.0 - legs
        return {rule["top_bone"]: rest * top, rule["base_bone"]: rest * (1.0 - top),
                rule["legs"]["L"]: legs * side_l, rule["legs"]["R"]: legs * (1.0 - side_l)}
    raise ValueError(kind)


def clean(ws, max_inf, clean_below):
    kept = {n: w for n, w in ws.items() if w >= clean_below}
    if not kept:
        kept = {max(ws, key=ws.get): 1.0}
    if len(kept) > max_inf:
        kept = dict(sorted(kept.items(), key=lambda kv: (-kv[1], kv[0]))[:max_inf])
    tot = sum(kept.values())
    return {n: w / tot for n, w in sorted(kept.items())}


def make_armature(scene, rig):
    data = bpy.data.armatures.new(rig["armature_object"])
    arm = bpy.data.objects.new(rig["armature_object"], data)
    scene.collection.objects.link(arm)
    bpy.ops.object.select_all(action="DESELECT")
    bpy.context.view_layer.objects.active = arm
    arm.select_set(True)
    bpy.ops.object.mode_set(mode="EDIT")
    for name, parent, head, tail in rig["bones"]:
        eb = data.edit_bones.new(name)
        eb.head, eb.tail = Vector(head), Vector(tail)
        if parent:
            eb.parent = data.edit_bones[parent]
        eb.use_connect = False
    bpy.ops.object.mode_set(mode="OBJECT")
    for pb in arm.pose.bones:
        pb.rotation_mode = "XYZ"
    return arm


def junction_points(lp, spec, cap_attr="h2_cap"):
    """Rim-loop vertices of spec.part (boundary edges of non-cap faces) within max_median_mm of spec.with's surface."""
    import bmesh
    from mathutils.bvhtree import BVHTree

    a, b = lp[spec["part"]], lp[spec["with"]]
    bm_b = bmesh.new()
    bm_b.from_mesh(b.data)
    layer_b = bm_b.faces.layers.int.get(cap_attr)
    polys = [[v.index for v in f.verts] for f in bm_b.faces if layer_b is None or f[layer_b] == 0]
    bvh = BVHTree.FromPolygons([b.matrix_world @ v.co for v in bm_b.verts], polys)
    bm_b.free()
    bm = bmesh.new()
    bm.from_mesh(a.data)
    layer = bm.faces.layers.int.get(cap_attr)
    tol = float(spec.get("max_distance_mm", 1.0)) / 1000.0
    pts = []
    for e in bm.edges:
        if not e.is_boundary or (layer is not None and e.link_faces[0][layer] != 0):
            continue
        for v in e.verts:
            co = a.matrix_world @ v.co
            hit = bvh.find_nearest(co)
            if hit[0] is not None and hit[3] <= tol:
                pts.append(tuple(co))
    bm.free()
    return sorted(set(pts))


def weight_part(obj, rule, arm, rig, cache, junctions=()):
    """junctions: [(KDTree of rim points, band_m, rule of the neighbour)]."""
    mw = obj.matrix_world
    groups = {}
    per_vertex = []
    for v in obj.data.vertices:
        p = mw @ v.co
        raw = rule_weights(rule, p, arm, cache)
        for kd, band, other in junctions:
            _co, _i, dist = kd.find(p)
            s = smoothstep(1.0 - dist / band)
            if s > 0.0:
                ow = rule_weights(other, p, arm, cache)
                raw = {k: (1.0 - s) * raw.get(k, 0.0) + s * ow.get(k, 0.0) for k in sorted(set(raw) | set(ow))}
        ws = clean(raw, int(rig["max_influences"]), float(rig["clean_below"]))
        per_vertex.append(ws)
        for n, w in ws.items():
            g = groups.get(n) or obj.vertex_groups.get(n) or obj.vertex_groups.new(name=n)
            groups[n] = g
            g.add([v.index], w, "REPLACE")
    return per_vertex


def continuity(parts_obj, weights, names, radius):
    """For vertices of part A within `radius` of a vertex of part B: L1 distance of their weight vectors."""
    kds = {}
    for n in names:
        co = [parts_obj[n].matrix_world @ v.co for v in parts_obj[n].data.vertices]
        kd = KDTree(len(co))
        for i, c in enumerate(co):
            kd.insert(c, i)
        kd.balance()
        kds[n] = (kd, co)
    out = {}
    for a in names:
        for b in names:
            if a >= b:
                continue
            kd_b, _ = kds[b]
            _kd_a, co_a = kds[a]
            diffs = []
            for i, c in enumerate(co_a):
                _co, j, d = kd_b.find(c)
                if d <= radius:
                    wa, wb = weights[a][i], weights[b][j]
                    keys = set(wa) | set(wb)
                    diffs.append(sum(abs(wa.get(k, 0.0) - wb.get(k, 0.0)) for k in keys))
            if diffs:
                out["%s|%s" % (a, b)] = {"pairs": len(diffs), "max_l1": U.r(max(diffs), 4),
                                         "p95_l1": U.r(float(np.percentile(diffs, 95)), 4)}
    return out


def atlas_material(profile, run_dir):
    mat = bpy.data.materials.new(profile["materials"]["atlas"])
    mat.use_nodes = True
    nt = mat.node_tree
    bsdf = next(n for n in nt.nodes if n.type == "BSDF_PRINCIPLED")
    prefix = profile["textures"]["prefix"]
    img = bpy.data.images.load(str(run_dir / "textures" / ("%s_BC.png" % prefix)), check_existing=False)
    img.name = "%s_BC.png" % prefix
    tex = nt.nodes.new("ShaderNodeTexImage")
    tex.image = img
    nt.links.new(tex.outputs["Color"], bsdf.inputs["Base Color"])
    return mat


def run(params, profile):
    from candidate_build import core
    from candidate_build import measure

    run_dir = Path(params["run_dir"])
    repo = Path(params["repo_root"])
    rig = profile["rig"]
    names = sorted(profile["parts"], key=U.part_key)
    # objects are appended into a factory scene (bpy.data.filepath stays ""): the FBX writer stores the path of the
    # open .blend (ApplicationNativeFile), which made the FBX bytes depend on the run directory (measured)
    scene = U.reset()
    with bpy.data.libraries.load(str(run_dir / "work" / "lp_uv.blend"), link=False) as (src, dst):
        dst.objects = [n for n in src.objects if n.startswith("LP_")]
    for obj in dst.objects:
        scene.collection.objects.link(obj)
    lp = {n: bpy.data.objects["LP_" + n] for n in names}
    arm = make_armature(scene, rig)
    bone_names = [b[0] for b in rig["bones"]]
    cache = {}
    weights = {}
    junction_report = []
    junctions = {}
    for spec in rig.get("junctions", []):
        pts = junction_points(lp, spec)
        kd = KDTree(len(pts))
        for i, c in enumerate(pts):
            kd.insert(c, i)
        kd.balance()
        junctions.setdefault(spec["part"], []).append((kd, float(spec["band_m"]), rig["weights"][spec["with"]]))
        junction_report.append({"part": spec["part"], "with": spec["with"], "band_m": spec["band_m"],
                                "rim_points": len(pts), "note": spec.get("note")})
        if not pts:
            raise RuntimeError("junction %s|%s: no rim points" % (spec["part"], spec["with"]))
    for n in names:
        if profile["parts"][n]["mesh"] == "base":
            continue
        weights[n] = weight_part(lp[n], rig["weights"][n], arm, rig, cache, junctions.get(n, ()))
    cont = continuity(lp, weights, sorted(weights, key=U.part_key), float(rig.get("continuity_radius_m", 0.0015)))
    mat = atlas_material(profile, run_dir)
    for n in names:
        lp[n].data.materials.clear()
        lp[n].data.materials.append(mat)
        attr = lp[n].data.attributes.new("h2_part", "INT", "FACE")
        attr.data.foreach_set("value", [U.part_key(n)] * len(lp[n].data.polygons))
    meshes = profile["meshes"]
    body_parts = [lp[n] for n in names if profile["parts"][n]["mesh"] == "body"]
    weapon_part = [lp[n] for n in names if profile["parts"][n]["mesh"] == "weapon"][0]
    base_part = [lp[n] for n in names if profile["parts"][n]["mesh"] == "base"][0]
    bpy.ops.object.select_all(action="DESELECT")
    for o in body_parts:
        o.select_set(True)
    active = lp[names[0]] if profile["parts"][names[0]]["mesh"] == "body" else body_parts[0]
    bpy.context.view_layer.objects.active = active
    bpy.ops.object.join()
    body = active
    body.name = meshes["body"]
    body.data.name = meshes["body"]
    weapon_part.name = meshes["weapon"]
    weapon_part.data.name = meshes["weapon"]
    base_part.name = meshes["base"]
    base_part.data.name = meshes["base"]
    for obj in (body, weapon_part):
        obj.parent = arm
        obj.modifiers.new("Armature", "ARMATURE").object = arm
    # part labels -> report, then drop (keeps the FBX free of custom data)
    labels = np.empty(len(body.data.polygons), np.int64)
    body.data.attributes["h2_part"].data.foreach_get("value", labels)
    caps = np.zeros(len(body.data.polygons), np.int64)
    if body.data.attributes.get("h2_cap") is not None:
        body.data.attributes["h2_cap"].data.foreach_get("value", caps)
    vert_part = np.full(len(body.data.vertices), -1, np.int64)
    vert_cap = np.zeros(len(body.data.vertices), np.int64)
    for poly in body.data.polygons:
        for vi in poly.vertices:
            vert_part[vi] = labels[poly.index]
            if caps[poly.index]:
                vert_cap[vi] = caps[poly.index]
    (run_dir / "work" / "rig").mkdir(parents=True, exist_ok=True)
    np.save(run_dir / "work" / "rig" / "body_vertex_part.npy", vert_part)
    np.save(run_dir / "work" / "rig" / "body_vertex_cap.npy", vert_cap)
    np.save(run_dir / "work" / "rig" / "body_face_cap.npy", caps)
    for obj in (body, weapon_part, base_part):
        obj.data.attributes.remove(obj.data.attributes["h2_part"])
        if obj.data.attributes.get("h2_cap") is not None:
            obj.data.attributes.remove(obj.data.attributes["h2_cap"])  # keeps the FBX free of custom data
    face_box = next((d["box_m"] for d in profile["retopo"].get("dense_regions", []) if d["name"] == "face"), None)
    face_polys = [p.index for p in body.data.polygons
                  if labels[p.index] == 1 and caps[p.index] == 0 and face_box and all(face_box[0][k] <= p.center[k] <= face_box[1][k] for k in range(3))
                  and p.normal.y < -0.3]
    pre = {o.name: measure.mesh_summary(o) for o in (body, weapon_part, base_part)}
    wsum = {"body": measure.weight_summary(body, bone_names), "weapon": measure.weight_summary(weapon_part, bone_names)}
    lo_sk, hi_sk = measure.world_bounds([body, weapon_part])
    lo_b, hi_b = measure.world_bounds([base_part])
    face_normal = measure.facing(body, face_polys)
    bow_c = measure.centroid(weapon_part)
    # sockets (Blender bone space, UE bone-space prediction)
    sockets = []
    for s in profile["sockets"]:
        bone = arm.data.bones[s["bone"]]
        if s.get("target") == "bone_head":
            target = Vector(bone.head_local)
        else:
            target = Vector(s["target_m"])
        local = bone.matrix_local.inverted() @ target
        local_uu = [c * 100.0 for c in local]
        pred = measure.ue_bone_local_from_blender_uu(local_uu)
        sockets.append({"name": s["name"], "bone": s["bone"], "ue_bone": s["bone"].replace(".", "_"),
                        "target_blender_m": U.rv(target, 5), "target_ue_component_uu": measure.ue_from_blender_m(target),
                        "offset_blender_bone_uu": U.rv(local_uu, 3),
                        "location_uu_for_ue": s["location_uu"] if s.get("location_uu") is not None else pred,
                        "source": "profile" if s.get("location_uu") is not None else "build prediction (x, -y, z)"})
    blend = run_dir / "work" / "sk_authored.blend"
    bpy.ops.wm.save_as_mainfile(filepath=str(blend), compress=False, copy=True)  # copy: bpy.data.filepath stays ""
    if bpy.data.filepath:
        raise RuntimeError("bpy.data.filepath must stay empty before the FBX export (deterministic bytes)")
    # ---- export (UM_FBX_v1)
    preset_path = repo / profile["exports"]["fbx_preset"]
    preset = core.load_preset(preset_path)
    rot = core.export_rotation(preset)
    data_scale = float(preset["temporary_data_scale"])
    core.transform_for_fbx(scene, arm, (body, weapon_part, base_part), Matrix.Scale(data_scale, 4) @ rot)
    sk_fbx = run_dir / "export" / profile["exports"]["skeletal_fbx"]
    base_fbx = run_dir / "export" / profile["exports"]["base_fbx"]
    core.export_pair(scene, arm, (body, weapon_part), base_part, preset, sk_fbx, base_fbx)
    # ---- read back: export frame, then the authored frame
    rt = bpy.data.scenes.new("h2_rt")
    core.import_fbx_into(rt, sk_fbx)
    rtb = bpy.data.scenes.new("h2_rt_base")
    core.import_fbx_into(rtb, base_fbx)
    rt_meas, rt_meshes = measure.roundtrip_measure(rt, bone_names)
    rtb_meas, _ = measure.roundtrip_measure(rtb, bone_names)
    arms_rt = [o for o in rt.objects if o.type == "ARMATURE"]
    rt_body = rt_meshes.get(meshes["body"])
    front_export = rot.to_3x3() @ Vector((0.0, -1.0, 0.0))
    bow_export = rot.to_3x3() @ Vector((1.0, 0.0, 0.0))
    face_rt = measure.facing(rt_body, face_polys) if rt_body and len(rt_body.data.polygons) == len(body.data.polygons) else None
    lo_rt, hi_rt = measure.world_bounds([o for o in rt.objects if o.type == "MESH"])
    lo_rtb, hi_rtb = measure.world_bounds([o for o in rtb.objects if o.type == "MESH"])
    bow_rt = measure.centroid(rt_meshes[meshes["weapon"]]) if meshes["weapon"] in rt_meshes else None
    inv = rot.inverted()
    core.to_authored_frame(rt, inv)
    core.to_authored_frame(rtb, inv)
    back_lo, back_hi = measure.world_bounds([o for o in rt.objects if o.type == "MESH"])
    exp_tris = {o.name: pre[o.name]["triangles"] for o in (body, weapon_part, base_part)}
    rt_tris = {n: e["triangles"] for n, e in list(rt_meas["meshes"].items()) + list(rtb_meas["meshes"].items())}
    exp_bones = {b[0]: b[1] for b in rig["bones"]}
    rt_bones = {n: v["parent"] for n, v in rt_meas["bones"].items()}
    wrt = rt_meas["meshes"].get(meshes["body"], {}).get("weights") or {}
    cm = lambda v: [U.r(c * 100.0, 3) for c in v]  # the FBX importer returns metres (scale ratio 1.0)
    bounds_export_cm = {"min": cm(lo_rt), "max": cm(hi_rt)}
    checks = core.Checks()
    checks("armature_object_is_bone0_name", [re.sub(r"\.\d{3}$", "", a.name) for a in arms_rt] == [rig["armature_object"]],
           [a.name for a in arms_rt], [rig["armature_object"]])
    checks("bones_and_parents_as_profile", rt_bones == exp_bones, len(rt_bones), len(exp_bones))
    checks("weapon_bone_by_side_v2", "weapon.L" in rt_bones and "weapon" not in rt_bones and rt_bones.get("weapon.L") == "hand.L",
           rt_bones.get("weapon.L"), "hand.L")
    checks("triangles_round_trip", rt_tris == exp_tris, rt_tris, exp_tris)
    checks("material_slots", all(len(e["material_slots"]) == 1 for e in list(rt_meas["meshes"].values()) + list(rtb_meas["meshes"].values())),
           {n: e["material_slots"] for n, e in list(rt_meas["meshes"].items()) + list(rtb_meas["meshes"].items())}, "1 per mesh (<= 2 total)")
    checks("uv0_present_in_unit_square", all(e["uv_layers"] and e["uv0_in_unit_square"] for e in list(rt_meas["meshes"].values()) + list(rtb_meas["meshes"].values())),
           {n: e["uv_layers"] for n, e in list(rt_meas["meshes"].items()) + list(rtb_meas["meshes"].items())}, "UV0 in [0,1]")
    checks("max_influences", (wrt.get("max_influences") or 99) <= int(rig["max_influences"]), wrt.get("max_influences"), "<= %d" % rig["max_influences"])
    checks("no_unweighted_vertices", wrt.get("unweighted_vertices") == 0 and (rt_meas["meshes"].get(meshes["weapon"], {}).get("weights") or {}).get("unweighted_vertices") == 0,
           wrt.get("unweighted_vertices"), 0)
    checks("export_frame_face_points_along_rotated_front", face_rt is not None and Vector(face_rt).dot(front_export) > 0.5,
           {"face_normal": face_rt, "rotated_front": U.rv(front_export, 3)}, "dot > 0.5 (UE +X)")
    checks("export_frame_bow_on_rotated_left", bow_rt is not None and Vector(bow_rt).dot(bow_export) > 0,
           {"bow_centroid_cm": bow_rt, "rotated_bow_side": U.rv(bow_export, 3)}, "bow on +Y of the export frame (UE -Y)")
    checks("authored_bounds_after_inverse_rotation",
           all(abs(a - b) < 5e-4 for a, b in zip(list(back_lo) + list(back_hi), list(lo_sk) + list(hi_sk))),
           {"min_cm": cm(back_lo), "max_cm": cm(back_hi)}, {"min_cm": cm(lo_sk), "max_cm": cm(hi_sk)})
    checks("unit_scale_1_and_height", abs(hi_rt[2] - hi_sk[2]) < 5e-4 and abs(hi_rtb[2] - hi_b[2]) < 5e-4,
           {"skeletal_top_cm": U.r(hi_rt[2] * 100, 3), "base_top_cm": U.r(hi_rtb[2] * 100, 3)},
           {"skeletal_top_cm": U.r(hi_sk[2] * 100, 3), "base_top_cm": U.r(hi_b[2] * 100, 3)})
    report = {"stage": "rig", "skeleton": rig["skeleton"], "armature_object": rig["armature_object"],
              "bones": {b[0]: {"parent": b[1], "head_m": b[2], "tail_m": b[3]} for b in rig["bones"]},
              "meshes_pre_export": pre, "weights": wsum, "weight_continuity_at_part_junctions": cont,
              "junctions": junction_report,
              "face_polygons": len(face_polys), "face_mean_normal_authored": face_normal, "bow_centroid_authored_m": bow_c,
              "bounds_authored_m": {"skeletal": [U.rv(lo_sk, 5), U.rv(hi_sk, 5)], "base": [U.rv(lo_b, 5), U.rv(hi_b, 5)]},
              "expected_ue_bounds_uu_at_import_scale_1": {"skeletal": measure.ue_predicted(bounds_export_cm),
                                                          "base": measure.ue_predicted({"min": cm(lo_rtb), "max": cm(hi_rtb)})},
              "sockets": sockets, "exports": {"skeletal_fbx": {"path": P_rel(sk_fbx, repo), "sha256": core.sha256(sk_fbx), "bytes": sk_fbx.stat().st_size},
                                              "base_fbx": {"path": P_rel(base_fbx, repo), "sha256": core.sha256(base_fbx), "bytes": base_fbx.stat().st_size},
                                              "settings": core.export_settings_report(preset, profile["exports"]["fbx_preset"], preset_path, data_scale)},
              "roundtrip": {"skeletal": rt_meas, "base": rtb_meas, "bounds_export_frame_cm": bounds_export_cm},
              "checks": dict(checks), "failed": checks.failed(), "passed": not checks.failed(), "status": "измерено",
              "claims": {"art_accepted": False, "game_ready": False, "budgets_declared": False}}
    U.write_json(run_dir / "reports" / "rig-report.json", report)
    if checks.failed():
        raise RuntimeError("rig checks failed: %s" % checks.failed())


def P_rel(path, repo):
    try:
        return Path(path).resolve().relative_to(Path(repo).resolve()).as_posix()
    except ValueError:
        return Path(path).as_posix()
