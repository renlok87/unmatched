"""Stage `ld_export` (headless Blender): UV1 in metres on the H2.1 game model of Merlin + UM_FBX_v1 re-export.

blender -b --factory-startup --python-exit-code 1 --python lookdev_export.py -- <lookdev profile.json>

1. The armature and the three meshes are appended (not opened: bpy.data.filepath stays empty, so the FBX carries no
   host path) from <source run>/work/h2-rig.blend - the rigged H2.1 model in the authored frame that stage_rig saved
   just before its export. Nothing is re-rigged, re-weighted or re-meshed.
2. UV1 "UV1_m" per mesh: UV0 islands (edge-connected triangles with equal UV0 on both sides of the edge); for each
   island scale = sqrt(3D area / UV0 area) (final frame, metres) -> 1 UV1 unit = 1 m on the object; the island's
   bounding-box centre goes to (0, 0) (smallest |UV1|: UE keeps UVs as 16-bit floats by default). Islands of the rotate_classes parts (wood: staff shaft and claw) are also rotated so the
   3D main axis of the island (PCA) runs along +U (the grain of the wood tile). UV0 is untouched.
3. UM_FBX_v1 export (candidate_build.core: same preset, rotation, determinism pins as stage_rig) to <run>/export/.
4. Read-back: both new FBX and the H2.1 FBX of the source run are imported; checks: triangles, polygon signatures
   (positions 1e-4 m + UV0 1e-5), bone names / parents / heads, weights (per-vertex, max |dw|), UV layers
   [UVMap, UV1_m] with UV1 = the authored values, face +X / weapon side (UE +Y) in the export frame, no host path.
Report: reports/ld-export-report.json.
"""

import math
import re
import sys
from pathlib import Path

import bpy
import numpy as np
from mathutils import Matrix

sys.path.insert(0, str(Path(__file__).resolve().parent))
import blib as B  # noqa: E402
import common as C  # noqa: E402
from candidate_build import core as CORE  # noqa: E402
from candidate_build import measure as MEAS  # noqa: E402

B.require_background("lookdev_export.py")


def append_named(path, names):
    with bpy.data.libraries.load(str(path), link=False) as (src, dst):
        missing = sorted(set(names) - set(src.objects))
        if missing:
            raise RuntimeError("%s: objects missing %s" % (path.name, missing))
        dst.objects = sorted(names)
    scene = bpy.context.scene
    out = {}
    for o in dst.objects:
        scene.collection.objects.link(o)
        out[o.name] = o
    return out


def loops_np(me):
    v = np.empty(len(me.loops), np.int64)
    me.loops.foreach_get("vertex_index", v)
    uv = np.empty(len(me.loops) * 2, np.float64)
    me.uv_layers[0].data.foreach_get("uv", uv)
    ls = np.empty(len(me.polygons), np.int64)
    me.polygons.foreach_get("loop_start", ls)
    lt = np.empty(len(me.polygons), np.int64)
    me.polygons.foreach_get("loop_total", lt)
    return v, uv.reshape(-1, 2), ls, lt


def islands(me):
    """Polygon -> island id (union-find over edges whose two corners carry the same UV0 on both polygons)."""
    v, uv, ls, lt = loops_np(me)
    n = len(ls)
    parent = list(range(n))

    def find(a):
        while parent[a] != a:
            parent[a] = parent[parent[a]]
            a = parent[a]
        return a

    q = np.round(uv * 1e6).astype(np.int64)
    edges = {}
    for p in range(n):
        s, t = int(ls[p]), int(lt[p])
        for k in range(t):
            la, lb = s + k, s + (k + 1) % t
            va, vb = int(v[la]), int(v[lb])
            if va > vb:
                va, vb, la, lb = vb, va, lb, la
            key = (va, vb, int(q[la, 0]), int(q[la, 1]), int(q[lb, 0]), int(q[lb, 1]))
            other = edges.get(key)
            if other is None:
                edges[key] = p
            else:
                ra, rb = find(p), find(other)
                if ra != rb:
                    parent[max(ra, rb)] = min(ra, rb)
    roots = [find(p) for p in range(n)]
    uniq = {r: i for i, r in enumerate(sorted(set(roots)))}
    return np.array([uniq[r] for r in roots], np.int64)


def uv1_for(obj, rotate_parts):
    """UV1 per loop + island statistics. Mesh in the authored final frame (metres)."""
    me = obj.data
    v, uv, ls, lt = loops_np(me)
    if not np.all(lt == 3):
        raise RuntimeError("%s: non-triangle polygons" % obj.name)
    co = B.verts_np(obj)
    isl = islands(me)
    part = B.int_face_attr(me, "um_part") if "um_part" in me.attributes else np.full(len(ls), -1)
    tri_l = ls[:, None] + np.arange(3)[None, :]
    P = co[v[tri_l]]                      # [T,3,3]
    U = uv[tri_l]                         # [T,3,2]
    e1, e2 = P[:, 1] - P[:, 0], P[:, 2] - P[:, 0]
    a3 = 0.5 * np.linalg.norm(np.cross(e1, e2), axis=1)
    f1, f2 = U[:, 1] - U[:, 0], U[:, 2] - U[:, 0]
    auv_signed = 0.5 * (f1[:, 0] * f2[:, 1] - f1[:, 1] * f2[:, 0])
    out = np.zeros_like(uv)
    stats = {"islands": int(isl.max()) + 1, "rotated_islands": 0, "mirrored_uv0_triangles": int((auv_signed < 0).sum()),
             "rotation_deg_of_rotated": []}
    scales = []
    for i in range(int(isl.max()) + 1):
        t = np.nonzero(isl == i)[0]
        A3, Auv = float(a3[t].sum()), float(np.abs(auv_signed[t]).sum())
        sc = math.sqrt(A3 / Auv) if Auv > 0 else 0.0
        scales.append(sc)
        lp = tri_l[t].ravel()
        w = uv[lp] * sc
        if len(rotate_parts) and np.all(np.isin(part[t], rotate_parts)):
            # 3D main axis of the island (PCA of its corner positions, area weighted by triangle)
            pts = P[t].reshape(-1, 3)
            wt = np.repeat(a3[t], 3)
            c = (pts * wt[:, None]).sum(0) / wt.sum()
            cov = ((pts - c) * wt[:, None]).T @ (pts - c) / wt.sum()
            axis = np.linalg.eigh(cov)[1][:, -1]
            # its direction in UV0 per triangle: d = pinv(J) axis, J = [dP/du dP/dv]; area-weighted mean of unit d
            # (sign of axis per triangle aligned to the first, the axis has no orientation)
            acc = np.zeros(2)
            for tt in t:
                J = np.linalg.lstsq(np.stack([f1[tt], f2[tt]], 0), np.stack([e1[tt], e2[tt]], 0), rcond=None)[0]  # 2x3: rows dP/du, dP/dv
                d = np.linalg.lstsq(J.T, axis, rcond=None)[0]
                nrm = np.linalg.norm(d)
                if nrm < 1e-12:
                    continue
                d = d / nrm
                if acc @ d < 0:
                    d = -d
                acc += a3[tt] * d
            ang = math.atan2(acc[1], acc[0])
            ca, sa = math.cos(-ang), math.sin(-ang)
            w = w @ np.array([[ca, sa], [-sa, ca]])
            stats["rotated_islands"] += 1
            stats["rotation_deg_of_rotated"].append(round(math.degrees(ang), 2))
        w = w - 0.5 * (w.min(0) + w.max(0))  # island centred on (0, 0): the smallest |UV1| for 16-bit UVs
        out[lp] = w
    # measured density: UV1 area / 3D area per island (1 = metres)
    f1b, f2b = out[tri_l[:, 1]] - out[tri_l[:, 0]], out[tri_l[:, 2]] - out[tri_l[:, 0]]
    a1 = 0.5 * np.abs(f1b[:, 0] * f2b[:, 1] - f1b[:, 1] * f2b[:, 0])
    ratio = np.array([a1[isl == i].sum() / a3[isl == i].sum() for i in range(int(isl.max()) + 1)])
    per_tri = a1 / np.maximum(a3, 1e-18)
    stats.update({"island_area_ratio_uv1_over_3d_min_max": C.rv([ratio.min(), ratio.max()], 6),
                  "triangle_area_ratio_p5_p50_p95": C.rv(np.percentile(per_tri[a3 > 1e-12], [5, 50, 95]), 4),
                  "uv1_abs_max_m": C.r(np.abs(out).max(), 5), "island_scale_min_max": C.rv([min(scales), max(scales)], 4)})
    stats["rotation_deg_of_rotated"] = stats["rotation_deg_of_rotated"][:40]
    return out, stats


def set_uv1(obj, uv1, name):
    me = obj.data
    layer = me.uv_layers.new(name=name, do_init=False)
    layer.data.foreach_set("uv", uv1.astype(np.float32).ravel())
    me.uv_layers.active_index = 0
    for i, l in enumerate(me.uv_layers):
        l.active_render = i == 0
    me.update()


def mesh_arrays(obj):
    me = obj.data
    co = B.verts_np(obj)
    layers = [l.name for l in me.uv_layers]
    uvs = {}
    for l in me.uv_layers:
        a = np.empty(len(me.loops) * 2, np.float64)
        l.data.foreach_get("uv", a)
        uvs[l.name] = a.reshape(-1, 2)
    v = np.empty(len(me.loops), np.int64)
    me.loops.foreach_get("vertex_index", v)
    groups = {g.index: g.name for g in obj.vertex_groups}
    w = [{groups[g.group]: g.weight for g in vx.groups if g.weight > 0} for vx in me.vertices]
    return {"co": co, "layers": layers, "uv": uvs, "loop_vert": v, "weights": w, "polys": len(me.polygons)}


def main():
    prof = C.Profile(B.script_args()[0])
    ld = prof["lookdev"]
    src = C.Profile(C.repo_path(ld["source_profile"]))
    checks = {}
    names = src["objects"]
    arm_name = src["armature"]["object"]
    rig_blend = src.work / "h2-rig.blend"
    src_fbx = {k: src.export / src["exports"][k] for k in ("skeletal_fbx", "base_fbx")}
    shas = {p.name: C.sha256(p) for p in src_fbx.values()}
    C.check(checks, "source_fbx_sha256", shas == ld["source_fbx_sha256"], shas, ld["source_fbx_sha256"])
    scene = B.empty_file()
    objs_all = append_named(rig_blend, [arm_name, names["body"]["name"], names["staff"]["name"], names["base"]["name"]])
    arm = objs_all[arm_name]
    objs = {k: objs_all[names[k]["name"]] for k in ("body", "staff", "base")}
    C.check(checks, "session_blend_path_empty", bpy.data.filepath == "", bpy.data.filepath != "", False)
    mods = {k: [(m.type, m.object.name if getattr(m, "object", None) else None) for m in o.modifiers] for k, o in objs.items()}
    C.check(checks, "appended_skinning_intact", mods["body"] == [("ARMATURE", arm_name)] and mods["staff"] == [("ARMATURE", arm_name)] and mods["base"] == [],
            mods, {"body": [["ARMATURE", arm_name]], "staff": [["ARMATURE", arm_name]], "base": []})
    # ---------------------------------------------------------------- UV1
    u = ld["uv1"]
    zparts = ld["zones"]["parts"]
    rot_parts = sorted({C.part_index(p) for cls in u["rotate_classes"] for p in zparts[cls]})
    uv1 = {}
    uv1_stats = {}
    for k, o in objs.items():
        uv1[k], uv1_stats[k] = uv1_for(o, rot_parts)
        set_uv1(o, uv1[k], u["layer_name"])
    dens = [v for s in uv1_stats.values() for v in s["island_area_ratio_uv1_over_3d_min_max"]]
    C.check(checks, "uv1_metres_per_island", min(dens) > 0.999 and max(dens) < 1.001, uv1_stats, "UV1 area / 3D area = 1 +- 0.001 per island")
    umax = max(s["uv1_abs_max_m"] for s in uv1_stats.values())
    half_step_mm = 2.0 ** (math.floor(math.log2(umax)) - 10) * 1000.0 if umax > 0 else 0.0
    C.check(checks, "uv1_half_precision", half_step_mm <= 0.25, {"uv1_abs_max_m": umax, "half_float_step_mm_at_max": C.r(half_step_mm, 5)},
            "<= 0.25 mm (UE stores UVs as 16-bit floats unless Use Full Precision UVs)")
    C.check(checks, "wood_islands_rotated", uv1_stats["staff"]["rotated_islands"] > 0, uv1_stats["staff"]["rotated_islands"], "> 0")
    authored = {k: mesh_arrays(o) for k, o in objs.items()}
    # ---------------------------------------------------------------- export (as stage_rig)
    preset_path = C.REPO / src["exports"]["fbx_preset"]
    preset = CORE.load_preset(preset_path)
    rot = CORE.export_rotation(preset)
    data_scale = float(preset["temporary_data_scale"])
    skel = (objs["body"], objs["staff"])
    CORE.transform_for_fbx(scene, arm, skel + (objs["base"],), Matrix.Scale(data_scale, 4) @ rot)
    sk_fbx = prof.export / ld["exports"]["skeletal_fbx"]
    base_fbx = prof.export / ld["exports"]["base_fbx"]
    CORE.export_pair(scene, arm, skel, objs["base"], preset, sk_fbx, base_fbx)
    hits = {C.rel(p): len(C.host_path_hits(p)) for p in (sk_fbx, base_fbx)}
    C.check(checks, "export_no_host_path", not any(hits.values()), hits, 0)
    # ---------------------------------------------------------------- read-back: new and H2.1
    bone_names = [b[0] for b in src["armature"]["bones"]]
    inv = rot.inverted()

    def load(sk, base, tag):
        sc = bpy.data.scenes.new("rt_" + tag)
        CORE.import_fbx_into(sc, sk)
        scb = bpy.data.scenes.new("rtb_" + tag)
        CORE.import_fbx_into(scb, base)
        raw = {re.sub(r"\.\d{3}$", "", o.name): o for s in (sc, scb) for o in s.objects}
        rarm = next(o for o in sc.objects if o.type == "ARMATURE")
        return sc, scb, raw, rarm

    new_sc, new_scb, new_raw, new_arm = load(sk_fbx, base_fbx, "new")
    old_sc, old_scb, old_raw, old_arm = load(src_fbx["skeletal_fbx"], src_fbx["base_fbx"], "h21")
    # export frame (before undoing the rotation): face +X, staff to -Y (UE +Y)
    body_new = new_raw[names["body"]["name"]]
    rv_body = B.verts_np(body_new)
    pof = B.int_face_attr(objs["body"].data, "um_part")
    face_idx = sorted({vi for p in objs["body"].data.polygons if pof[p.index] == C.part_index("tripo_part_9") for vi in p.vertices})
    same_count = len(rv_body) == len(objs["body"].data.vertices)
    body_c = rv_body.mean(0)
    face_c = rv_body[face_idx].mean(0) if same_count else None
    staff_c = B.verts_np(new_raw[names["staff"]["name"]]).mean(0)
    Lh = np.array(new_arm.matrix_world @ new_arm.data.bones["arm_upper.L"].head_local)
    Rh = np.array(new_arm.matrix_world @ new_arm.data.bones["arm_upper.R"].head_local)
    lat = Lh - Rh
    yaw = math.degrees(math.atan2(lat[1], lat[0])) - 90.0
    frame = {"face_minus_body_x_uu": C.r((face_c[0] - body_c[0]) * 100, 3) if face_c is not None else None, "yaw_deg": C.r(yaw, 2),
             "staff_minus_body_y_uu": C.r((staff_c[1] - body_c[1]) * 100, 3)}
    C.check(checks, "export_face_plus_x", face_c is not None and face_c[0] - body_c[0] > 0.005 and abs(yaw) < 10, frame,
            "face ahead of the body centroid along +X (> 0.5 uu), lateral yaw 0 +- 10 deg")
    C.check(checks, "export_staff_side_ue_plus_y", staff_c[1] - body_c[1] < -0.02, frame["staff_minus_body_y_uu"], "< -2 uu (= UE +Y)")
    for sc in (new_sc, new_scb, old_sc, old_scb):
        CORE.to_authored_frame(sc, inv)
    m_new, _ = MEAS.roundtrip_measure(new_sc, bone_names)
    m_old, _ = MEAS.roundtrip_measure(old_sc, bone_names)
    b_new, _ = MEAS.roundtrip_measure(new_scb, bone_names)
    b_old, _ = MEAS.roundtrip_measure(old_scb, bone_names)
    tris_new = {n: e["triangles"] for n, e in list(m_new["meshes"].items()) + list(b_new["meshes"].items())}
    tris_old = {n: e["triangles"] for n, e in list(m_old["meshes"].items()) + list(b_old["meshes"].items())}
    C.check(checks, "triangles_equal_h21", tris_new == tris_old, {"lookdev": tris_new, "h21": tris_old}, "equal")
    bones_eq = m_new["bones"] == m_old["bones"]
    C.check(checks, "bones_equal_h21", bones_eq and sorted(m_new["bones"]) == sorted(bone_names) and m_new["armature_objects"] == [arm_name],
            {"bones": len(m_new["bones"]), "armature_objects": m_new["armature_objects"], "names_parents_heads_tails_equal": bones_eq},
            {"bones": 17, "armature": arm_name})
    geo = {}
    wts = {}
    uvl = {}
    uv1_rb = {}
    for key in ("body", "staff", "base"):
        nm = names[key]["name"]
        a, b = new_raw[nm], old_raw[nm]
        cmp = MEAS.compare_meshes(a, b, {})
        geo[nm] = {k: cmp[k] for k in ("polygons_candidate", "polygons_reference", "unmatched_candidate_polygons", "unmatched_reference_polygons")}
        va, vb = B.verts_np(a), B.verts_np(b)
        geo[nm]["vertices"] = [len(va), len(vb)]
        geo[nm]["max_vertex_delta_m"] = C.r(float(np.abs(va - vb).max()), 9) if va.shape == vb.shape else None
        uvl[nm] = [l.name for l in a.data.uv_layers]
        if a.vertex_groups:
            ma, mb = mesh_arrays(a), mesh_arrays(b)
            d = 0.0
            same_keys = True
            for wa, wb in zip(ma["weights"], mb["weights"]):
                if set(wa) != set(wb):
                    same_keys = False
                    break
                d = max([d] + [abs(wa[n] - wb[n]) for n in wa])
            wts[nm] = {"same_bones_per_vertex": same_keys, "max_abs_weight_delta": C.r(d, 8)}
        # UV1 read back = authored UV1 (the importer keeps the loop order of the exporter)
        if u["layer_name"] in a.data.uv_layers:
            ra = np.empty(len(a.data.loops) * 2, np.float64)
            a.data.uv_layers[u["layer_name"]].data.foreach_get("uv", ra)
            ra = ra.reshape(-1, 2)
            au = authored[key]["uv"][u["layer_name"]]
            uv1_rb[nm] = C.r(float(np.abs(ra - au).max()), 8) if ra.shape == au.shape else "loop count differs"
    C.check(checks, "geometry_equal_h21", all(g["unmatched_candidate_polygons"] == 0 and g["unmatched_reference_polygons"] == 0
                                              and g["max_vertex_delta_m"] is not None and g["max_vertex_delta_m"] <= 1e-6 for g in geo.values()),
            geo, "all polygons matched (positions 1e-4 m + UV0 1e-5), vertex arrays equal (<= 1e-6 m)")
    C.check(checks, "weights_equal_h21", all(w["same_bones_per_vertex"] and w["max_abs_weight_delta"] <= 1e-6 for w in wts.values()) and len(wts) == 2,
            wts, "same bones per vertex, |dw| <= 1e-6")
    C.check(checks, "uv_layers_uvmap_then_uv1", all(v == ["UVMap", u["layer_name"]] for v in uvl.values()), uvl, ["UVMap", u["layer_name"]])
    C.check(checks, "uv1_readback_equals_authored", all(isinstance(v, float) and v <= 1e-5 for v in uv1_rb.values()), uv1_rb, "<= 1e-5")
    slots = {n: e["material_slots"] for n, e in list(m_new["meshes"].items()) + list(b_new["meshes"].items())}
    C.check(checks, "material_slot_single", all(len(set(v)) == 1 and v[0] == src["materials"]["atlas"] for v in slots.values()), slots,
            src["materials"]["atlas"])
    report = {"stage": "ld_export", "profile": C.rel(prof.path), "profile_id": prof["profile_id"], "blender": bpy.app.version_string,
              "source": {"rig_blend": C.rel(rig_blend), "rig_blend_sha256": C.sha256(rig_blend),
                         "h21_fbx": {C.rel(p): C.sha256(p) for p in src_fbx.values()}},
              "uv1": dict(u, stats=uv1_stats, rotate_parts=["tripo_part_%d" % p for p in rot_parts]),
              "export_frame": frame,
              "exports": {"skeletal_fbx": {"path": C.rel(sk_fbx), "sha256": C.sha256(sk_fbx), "bytes": sk_fbx.stat().st_size},
                          "base_fbx": {"path": C.rel(base_fbx), "sha256": C.sha256(base_fbx), "bytes": base_fbx.stat().st_size},
                          "settings": CORE.export_settings_report(preset, src["exports"]["fbx_preset"], preset_path, data_scale)},
              "readback": {"triangles": tris_new, "geometry_vs_h21": geo, "weights_vs_h21": wts, "uv_layers": uvl,
                           "uv1_readback_max_abs": uv1_rb},
              "checks": checks, "passed": all(c["passed"] for c in checks.values())}
    C.write_json(prof.reports / "ld-export-report.json", report)
    print("H2_STAGE_OK ld_export passed=%s" % report["passed"])
    if not report["passed"]:
        raise RuntimeError("ld_export checks failed: %s" % sorted(k for k, c in checks.items() if not c["passed"]))


main()
