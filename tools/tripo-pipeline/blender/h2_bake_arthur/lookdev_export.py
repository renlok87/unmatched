"""Stage `ld_export` (headless Blender): UV1 in metres on the H2 game model of King Arthur + UM_FBX_v1 re-export.

    blender -b --factory-startup --python lookdev_export.py -- <lookdev profile.json> <lookdev run dir>

1. The armature and the three meshes are appended (not opened: bpy.data.filepath stays empty, so the FBX carries no
   host path) from <source run>/work/h2-rig-authored.blend - the rigged H2 model in the authored frame that stage_rig
   saved just before its export. Nothing is re-rigged, re-weighted or re-meshed.
2. UV1 "UV1_m" per mesh (as Merlin's lookdev_export): UV0 islands (edge-connected triangles with equal UV0 on both
   sides of the edge); per island scale = sqrt(3D area / UV0 area) in metres of the final frame -> 1 UV1 unit = 1 m on
   the object; the island's bounding-box centre goes to (0, 0). No island is rotated (profile uv1.rotate_zones is
   empty for Arthur): UV1 is a similarity of UV0 per island. UV0 is untouched.
3. UM_FBX_v1 export (candidate_build.core: the preset, rotation and determinism pins of stage_rig) to <run>/export/.
4. Read-back: both new FBX and the H2 FBX of the source run are imported; checks: triangles, polygon signatures
   (positions 1e-4 m + UV0 1e-5), bone names / parents / heads, weights (per vertex, max |dw|), UV layers
   [UVMap, UV1_m] with UV1 = the authored values, face +X / sword on the right (UE +Y) in the export frame, no host path.
Writes reports/ld-export-report.json and work/lookdev/uv1-triangles.npz (per object: UV0 and UV1 of every triangle
corner; ld_maps rasterises the per-texel UV1 of the atlas from it for the detail-tile emulation).
"""

import math
import re
import sys
from pathlib import Path

import bpy
import numpy as np
from mathutils import Matrix

sys.path.insert(0, str(Path(__file__).resolve().parent))
import bl  # noqa: E402
import pure as P  # noqa: E402
from candidate_build import core as CORE  # noqa: E402
from candidate_build import measure as MEAS  # noqa: E402

bl.require_background("lookdev_export.py")


def check(checks, name, passed, measured, expected, note=""):
    checks[name] = {"passed": bool(passed), "measured": measured, "expected": expected, "note": note}


def host_path_hits(path):
    data = Path(path).read_bytes()
    needles = set()
    for root in (P.REPO.resolve(), Path.home()):
        s = str(root)
        needles.update({s, s.replace("\\", "/"), s.replace("/", "\\")})
    hits = sorted(n for n in needles if n.encode("utf-8") in data)
    for m in re.finditer(rb"[A-Za-z]:[\\/]+Users[\\/]", data):
        hits.append("offset %d" % m.start())
    return hits


def verts_np(obj):
    me = obj.data
    co = np.empty(len(me.vertices) * 3, np.float64)
    me.vertices.foreach_get("co", co)
    co = co.reshape(-1, 3)
    m = np.array(obj.matrix_world)
    return co @ m[:3, :3].T + m[:3, 3]


def int_face_attr(me, name):
    a = np.empty(len(me.polygons), np.int64)
    me.attributes[name].data.foreach_get("value", a)
    return a


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


def uv1_for(obj):
    """UV1 per loop + island statistics (mesh in the authored final frame, metres)."""
    me = obj.data
    v, uv, ls, lt = loops_np(me)
    if not np.all(lt == 3):
        raise RuntimeError("%s: non-triangle polygons" % obj.name)
    co = verts_np(obj)
    isl = islands(me)
    tri_l = ls[:, None] + np.arange(3)[None, :]
    Pt = co[v[tri_l]]
    U = uv[tri_l]
    e1, e2 = Pt[:, 1] - Pt[:, 0], Pt[:, 2] - Pt[:, 0]
    a3 = 0.5 * np.linalg.norm(np.cross(e1, e2), axis=1)
    f1, f2 = U[:, 1] - U[:, 0], U[:, 2] - U[:, 0]
    auv_signed = 0.5 * (f1[:, 0] * f2[:, 1] - f1[:, 1] * f2[:, 0])
    out = np.zeros_like(uv)
    scales = []
    for i in range(int(isl.max()) + 1):
        t = np.nonzero(isl == i)[0]
        A3, Auv = float(a3[t].sum()), float(np.abs(auv_signed[t]).sum())
        sc = math.sqrt(A3 / Auv) if Auv > 0 else 0.0
        scales.append(sc)
        lp = tri_l[t].ravel()
        w = uv[lp] * sc
        w = w - 0.5 * (w.min(0) + w.max(0))
        out[lp] = w
    f1b, f2b = out[tri_l[:, 1]] - out[tri_l[:, 0]], out[tri_l[:, 2]] - out[tri_l[:, 0]]
    a1 = 0.5 * np.abs(f1b[:, 0] * f2b[:, 1] - f1b[:, 1] * f2b[:, 0])
    ratio = np.array([a1[isl == i].sum() / a3[isl == i].sum() for i in range(int(isl.max()) + 1)
                      if a3[isl == i].sum() > 0])
    per_tri = a1 / np.maximum(a3, 1e-18)
    stats = {"islands": int(isl.max()) + 1, "rotated_islands": 0, "mirrored_uv0_triangles": int((auv_signed < 0).sum()),
             "island_area_ratio_uv1_over_3d_min_max": P.rv([ratio.min(), ratio.max()], 6),
             "triangle_area_ratio_p5_p50_p95": P.rv(np.percentile(per_tri[a3 > 1e-12], [5, 50, 95]), 4),
             "uv1_abs_max_m": P.r(np.abs(out).max(), 5), "island_scale_min_max": P.rv([min(scales), max(scales)], 4)}
    return out, stats, U, out[tri_l]


def set_uv1(obj, uv1, name):
    me = obj.data
    layer = me.uv_layers.new(name=name, do_init=False)
    layer.data.foreach_set("uv", uv1.astype(np.float32).ravel())
    me.uv_layers.active_index = 0
    for i, lay in enumerate(me.uv_layers):
        lay.active_render = i == 0
    me.update()


def mesh_arrays(obj):
    me = obj.data
    uvs = {}
    for lay in me.uv_layers:
        a = np.empty(len(me.loops) * 2, np.float64)
        lay.data.foreach_get("uv", a)
        uvs[lay.name] = a.reshape(-1, 2)
    groups = {g.index: g.name for g in obj.vertex_groups}
    w = [{groups[g.group]: g.weight for g in vx.groups if g.weight > 0} for vx in me.vertices]
    return {"uv": uvs, "weights": w}


def main():
    args = bl.script_args()
    prof_path, run = Path(args[0]).resolve(), Path(args[1]).resolve()
    prof = P.load_json(prof_path)
    ld = prof["lookdev"]
    src = P.load_json(P.repo_path(ld["source_profile"]))
    src_paths = P.run_paths(P.repo_path(ld["source_run"]))
    paths = P.run_paths(run)
    for k in ("export", "reports", "work"):
        paths[k].mkdir(parents=True, exist_ok=True)
    rc = src["rig"]
    names = rc["objects"]
    checks = {}
    rig_blend = src_paths["work"] / "h2-rig-authored.blend"
    src_fbx = {k: src_paths["export"] / rc["exports"][k] for k in ("skeletal_fbx", "base_fbx")}
    shas = {p.name: P.sha256(p) for p in src_fbx.values()}
    check(checks, "source_fbx_sha256", shas == ld["source_fbx_sha256"], shas, ld["source_fbx_sha256"])
    bpy.ops.wm.read_factory_settings(use_empty=True)
    scene = bpy.context.scene
    arm_name = rc["armature"]["object"]
    objs_all = append_named(rig_blend, [arm_name, names["body"], names["weapon"], names["base"]])
    arm = objs_all[arm_name]
    objs = {"body": objs_all[names["body"]], "weapon": objs_all[names["weapon"]], "base": objs_all[names["base"]]}
    check(checks, "session_blend_path_empty", bpy.data.filepath == "", bpy.data.filepath, "")
    mods = {k: [(m.type, m.object.name if getattr(m, "object", None) else None) for m in o.modifiers] for k, o in objs.items()}
    check(checks, "appended_skinning_intact",
          mods["body"] == [("ARMATURE", arm_name)] and mods["weapon"] == [("ARMATURE", arm_name)] and mods["base"] == [],
          mods, {"body": [["ARMATURE", arm_name]], "weapon": [["ARMATURE", arm_name]], "base": []})
    # ---------------------------------------------------------------- UV1
    u = ld["uv1"]
    uv1, uv1_stats, tri_uv = {}, {}, {}
    for k, o in objs.items():
        uv1[k], uv1_stats[k], u0t, u1t = uv1_for(o)
        tri_uv[k + "_uv0"] = u0t.astype(np.float64)
        tri_uv[k + "_uv1"] = u1t.astype(np.float64)
        set_uv1(o, uv1[k], u["layer_name"])
    dens = [x for s in uv1_stats.values() for x in s["island_area_ratio_uv1_over_3d_min_max"]]
    check(checks, "uv1_metres_per_island", min(dens) > 0.999 and max(dens) < 1.001, uv1_stats,
          "UV1 area / 3D area = 1 +- 0.001 per island")
    umax = max(s["uv1_abs_max_m"] for s in uv1_stats.values())
    half_step_mm = 2.0 ** (math.floor(math.log2(umax)) - 10) * 1000.0 if umax > 0 else 0.0
    check(checks, "uv1_half_precision", half_step_mm <= 0.25,
          {"uv1_abs_max_m": umax, "half_float_step_mm_at_max": P.r(half_step_mm, 5)},
          "<= 0.25 mm (UE stores UVs as 16-bit floats unless Use Full Precision UVs)")
    check(checks, "uv0_not_mirrored", all(s["mirrored_uv0_triangles"] == 0 for s in uv1_stats.values()),
          {k: s["mirrored_uv0_triangles"] for k, s in uv1_stats.items()}, 0,
          "a similarity UV1 keeps the UV0 tangent frame only without mirrored UV0 triangles")
    wk = paths["work"] / "lookdev"
    wk.mkdir(parents=True, exist_ok=True)
    np.savez(wk / "uv1-triangles.npz", **tri_uv)
    authored = {k: mesh_arrays(o) for k, o in objs.items()}
    # ---------------------------------------------------------------- export (as stage_rig)
    preset_path = P.REPO / rc["fbx_preset"]
    preset = CORE.load_preset(preset_path)
    rot = CORE.export_rotation(preset)
    data_scale = float(preset["temporary_data_scale"])
    skel = (objs["body"], objs["weapon"])
    CORE.transform_for_fbx(scene, arm, skel + (objs["base"],), Matrix.Scale(data_scale, 4) @ rot)
    sk_fbx = paths["export"] / ld["exports"]["skeletal_fbx"]
    base_fbx = paths["export"] / ld["exports"]["base_fbx"]
    CORE.export_pair(scene, arm, skel, objs["base"], preset, sk_fbx, base_fbx)
    hits = {P.rel(p): host_path_hits(p) for p in (sk_fbx, base_fbx)}
    check(checks, "export_no_host_path", not any(hits.values()), hits, "no repo / home / Users path in the FBX bytes")
    # ---------------------------------------------------------------- read-back: new and H2
    bone_names = [b[0] for b in rc["armature"]["bones"]] if isinstance(rc["armature"].get("bones"), list) else \
        [b.name for b in arm.data.bones]
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
    old_sc, old_scb, old_raw, old_arm = load(src_fbx["skeletal_fbx"], src_fbx["base_fbx"], "h2")
    # export frame, as the readback of stage_rig: anatomy front from the bones (side = mean(arm_upper, leg_upper
    # heads) .L - .R, front = side turned -90 deg about Z) and the sword centroid ahead / on the right of the body
    mw = new_arm.matrix_world
    bn = new_arm.data.bones
    Ls = (mw @ bn["arm_upper.L"].head_local + mw @ bn["leg_upper.L"].head_local) / 2
    Rs = (mw @ bn["arm_upper.R"].head_local + mw @ bn["leg_upper.R"].head_local) / 2
    side = np.array(Ls - Rs)[:2]
    side = side / np.linalg.norm(side)
    front = np.array([side[1], -side[0]])
    yaw = math.degrees(math.atan2(front[1], front[0]))
    body_c = verts_np(new_raw[names["body"]]).mean(0)
    sword_c = verts_np(new_raw[names["weapon"]]).mean(0)
    wmb = sword_c - body_c
    frame = {"front_yaw_deg_from_plus_x": P.r(yaw, 2), "sword_minus_body_centroid_m": P.rv(wmb, 4),
             "method": "FBX re-imported in Blender (metres); the H2 rig readback uses the same measures"}
    check(checks, "export_front_plus_x", abs(yaw) <= 10, frame["front_yaw_deg_from_plus_x"], "0 +- 10 deg (UE +X)")
    check(checks, "export_sword_front_right", wmb[0] > 0.01 and wmb[1] < -0.01, frame["sword_minus_body_centroid_m"],
          "x > 0.01 (front), y < -0.01 (FBX -Y = UE +Y: right hand)")
    for sc in (new_sc, new_scb, old_sc, old_scb):
        CORE.to_authored_frame(sc, inv)
    m_new, _ = MEAS.roundtrip_measure(new_sc, bone_names)
    m_old, _ = MEAS.roundtrip_measure(old_sc, bone_names)
    b_new, _ = MEAS.roundtrip_measure(new_scb, bone_names)
    b_old, _ = MEAS.roundtrip_measure(old_scb, bone_names)
    tris_new = {n: e["triangles"] for n, e in list(m_new["meshes"].items()) + list(b_new["meshes"].items())}
    tris_old = {n: e["triangles"] for n, e in list(m_old["meshes"].items()) + list(b_old["meshes"].items())}
    check(checks, "triangles_equal_h2", tris_new == tris_old, {"lookdev": tris_new, "h2": tris_old}, "equal")
    bones_eq = m_new["bones"] == m_old["bones"]
    check(checks, "bones_equal_h2", bones_eq and len(m_new["bones"]) == 17 and m_new["armature_objects"] == [arm_name],
          {"bones": len(m_new["bones"]), "armature_objects": m_new["armature_objects"],
           "names_parents_heads_tails_equal": bones_eq}, {"bones": 17, "armature": arm_name})
    geo, wts, uvl, uv1_rb = {}, {}, {}, {}
    for key in ("body", "weapon", "base"):
        nm = names[key]
        a, b = new_raw[nm], old_raw[nm]
        cmp = MEAS.compare_meshes(a, b, {})
        geo[nm] = {k: cmp[k] for k in ("polygons_candidate", "polygons_reference", "unmatched_candidate_polygons",
                                       "unmatched_reference_polygons")}
        va, vb = verts_np(a), verts_np(b)
        geo[nm]["vertices"] = [len(va), len(vb)]
        geo[nm]["max_vertex_delta_m"] = P.r(float(np.abs(va - vb).max()), 9) if va.shape == vb.shape else None
        uvl[nm] = [lay.name for lay in a.data.uv_layers]
        if a.vertex_groups:
            ma, mb = mesh_arrays(a), mesh_arrays(b)
            d = 0.0
            same_keys = True
            for wa, wb in zip(ma["weights"], mb["weights"]):
                if set(wa) != set(wb):
                    same_keys = False
                    break
                d = max([d] + [abs(wa[n] - wb[n]) for n in wa])
            wts[nm] = {"same_bones_per_vertex": same_keys, "max_abs_weight_delta": P.r(d, 8)}
        if u["layer_name"] in a.data.uv_layers:
            ra = np.empty(len(a.data.loops) * 2, np.float64)
            a.data.uv_layers[u["layer_name"]].data.foreach_get("uv", ra)
            ra = ra.reshape(-1, 2)
            au = authored[key]["uv"][u["layer_name"]]
            uv1_rb[nm] = P.r(float(np.abs(ra - au).max()), 8) if ra.shape == au.shape else "loop count differs"
    # vertex positions: the FBX importer stores centimetre numbers scaled back to metres by the object transform
    check(checks, "geometry_equal_h2",
          all(g["unmatched_candidate_polygons"] == 0 and g["unmatched_reference_polygons"] == 0 and
              g["max_vertex_delta_m"] is not None and g["max_vertex_delta_m"] <= 1e-6 for g in geo.values()),
          geo, "all polygons matched (positions 1e-4 m + UV0 1e-5), vertex arrays equal (<= 1e-6)")
    check(checks, "weights_equal_h2", all(w["same_bones_per_vertex"] and w["max_abs_weight_delta"] <= 1e-6
                                          for w in wts.values()) and len(wts) == 2,
          wts, "same bones per vertex, |dw| <= 1e-6")
    check(checks, "uv_layers_uvmap_then_uv1", all(v == ["UVMap", u["layer_name"]] for v in uvl.values()), uvl,
          ["UVMap", u["layer_name"]])
    check(checks, "uv1_readback_equals_authored", all(isinstance(v, float) and v <= 1e-5 for v in uv1_rb.values()),
          uv1_rb, "<= 1e-5")
    slots = {n: e["material_slots"] for n, e in list(m_new["meshes"].items()) + list(b_new["meshes"].items())}
    check(checks, "material_slot_single", all(len(set(v)) == 1 and v[0] == rc["material"] for v in slots.values()),
          slots, rc["material"])
    report = {"stage": "ld_export", "profile": P.rel(prof_path), "profile_id": prof["profile_id"],
              "blender": bpy.app.version_string,
              "source": {"rig_blend": P.rel(rig_blend), "rig_blend_sha256": P.sha256(rig_blend),
                         "h2_fbx": {P.rel(p): P.sha256(p) for p in src_fbx.values()}},
              "uv1": dict(u, stats=uv1_stats), "export_frame": frame,
              "exports": {"skeletal_fbx": {"path": P.rel(sk_fbx), "sha256": P.sha256(sk_fbx), "bytes": sk_fbx.stat().st_size},
                          "base_fbx": {"path": P.rel(base_fbx), "sha256": P.sha256(base_fbx), "bytes": base_fbx.stat().st_size},
                          "settings": CORE.export_settings_report(preset, rc["fbx_preset"], preset_path, data_scale)},
              "readback": {"triangles": tris_new, "geometry_vs_h2": geo, "weights_vs_h2": wts, "uv_layers": uvl,
                           "uv1_readback_max_abs": uv1_rb},
              "uv1_triangles": P.rel(wk / "uv1-triangles.npz"),
              "checks": checks, "passed": all(c["passed"] for c in checks.values())}
    P.write_json(paths["reports"] / "ld-export-report.json", report)
    print(P.STAGE_MARKER, "ld_export passed=%s" % report["passed"],
          sorted(k for k, c in checks.items() if not c["passed"]))


main()
