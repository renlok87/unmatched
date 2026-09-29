"""Stage ld_fbx of the Harpy look-dev v2 (headless Blender): UV1 in metres on the H3 game model + UM_FBX_v1 export.

    blender -b --factory-startup --python lookdev_export.py -- <harpy-h3-lookdev.json>

1. The armature, the body and the base are appended (not opened: bpy.data.filepath stays empty, the FBX carries no
   host path) from <H3 run>/work/h2-candidate.blend - the rigged H3 model in the authored frame that stage_rig saved
   just before its export. Nothing is re-rigged, re-weighted or re-meshed.
2. UV1 "UV1_m" on the body and the base: per UV0 island (polygons connected through a shared vertex with the same
   UV0) UV1 = (UV0 - centre of the island's UV0 bbox) x s, s = sqrt(area3D / areaUV0) in metres of the final frame:
   a uniform scale of the island (no rotation, no mirror), so the UV1 tangent frame equals UV0 (the Medusa look-dev
   method); centred so |UV1| stays small for UE half-float UVs. UV0 is untouched.
3. The atlas image of the body material is re-pointed to the look-dev BC (the FBX stores the file name only).
4. UM_FBX_v1 export (candidate_build.core, the transform and determinism pins of stage_rig) to <run>/export/.
5. Read-back of the new FBX and of the H3 FBX in the same process: bones / parents / heads-tails, triangles, positions
   and UV0 of every loop, UV layers [UVMap, UV1_m], UV1 density (area UV1 / area 3D per island), face +X in the export
   frame. Report reports/ld-fbx-report.json.
"""

import json
import sys
from pathlib import Path

import bpy
import numpy as np
from mathutils import Matrix, Vector

sys.path.insert(0, str(Path(__file__).resolve().parent))
import common as C  # noqa: E402
from candidate_build import core as CORE  # noqa: E402
from candidate_build import measure as MEAS  # noqa: E402

C.require_background("lookdev_export.py")


def append_objects(src_blend, names):
    with bpy.data.libraries.load(str(src_blend), link=False) as (src, dst):
        missing = sorted(set(names) - set(src.objects))
        if missing:
            raise RuntimeError("%s: objects missing %s" % (src_blend, missing))
        dst.objects = sorted(names)
    scene = bpy.context.scene
    for o in dst.objects:
        scene.collection.objects.link(o)
    return {o.name: o for o in dst.objects}


def islands(mesh):
    """Island index per polygon (UV0 connectivity through a shared vertex with an identical UV)."""
    nl, npoly = len(mesh.loops), len(mesh.polygons)
    lv = np.empty(nl, np.int64)
    mesh.loops.foreach_get("vertex_index", lv)
    uv = np.empty(nl * 2, np.float64)
    mesh.uv_layers[0].data.foreach_get("uv", uv)
    uv = uv.reshape(-1, 2)
    q = np.round(uv * (1 << 22)).astype(np.int64)
    _u, corner = np.unique(np.stack([lv, q[:, 0], q[:, 1]], 1), axis=0, return_inverse=True)
    corner = corner.ravel()
    ls = np.empty(npoly, np.int64)
    lt = np.empty(npoly, np.int64)
    mesh.polygons.foreach_get("loop_start", ls)
    mesh.polygons.foreach_get("loop_total", lt)
    parent = list(range(int(corner.max()) + 1))

    def find(a):
        while parent[a] != a:
            parent[a] = parent[parent[a]]
            a = parent[a]
        return a

    for p in range(npoly):
        base = find(int(corner[ls[p]]))
        for k in range(1, int(lt[p])):
            b = find(int(corner[ls[p] + k]))
            if b != base:
                if b < base:
                    parent[base] = b
                    base = b
                else:
                    parent[b] = base
    root = np.array([find(int(corner[ls[p]])) for p in range(npoly)], np.int64)
    _r, isl = np.unique(root, return_inverse=True)
    return isl.ravel(), uv, ls, lt


def poly_uv_area(uv, ls, lt):
    area = np.zeros(len(ls))
    for n in np.unique(lt):
        sel = np.nonzero(lt == n)[0]
        idx = ls[sel][:, None] + np.arange(n)[None, :]
        u, v = uv[idx, 0], uv[idx, 1]
        area[sel] = 0.5 * np.abs((u * np.roll(v, -1, 1) - np.roll(u, -1, 1) * v).sum(1))
    return area


def poly_areas(obj):
    a = np.empty(len(obj.data.polygons))
    obj.data.polygons.foreach_get("area", a)
    return a * obj.matrix_world.to_3x3().determinant() ** (2.0 / 3.0)


def add_uv1(obj, name):
    mesh = obj.data
    isl, uv, ls, lt = islands(mesh)
    a3 = poly_areas(obj)
    auv = poly_uv_area(uv, ls, lt)
    n = int(isl.max()) + 1
    A3, AUV = np.bincount(isl, a3, n), np.bincount(isl, auv, n)
    # degenerate UV0 islands (zero UV area: they cover no texel of the atlas) take the median scale of the others
    degen = AUV < 1e-10
    s = np.sqrt(A3 / np.maximum(AUV, 1e-18))
    s[degen] = float(np.median(s[~degen]))
    loop_isl = np.empty(len(uv), np.int64)
    for p in range(len(ls)):
        loop_isl[ls[p]:ls[p] + lt[p]] = isl[p]
    lo = np.full((n, 2), np.inf)
    hi = np.full((n, 2), -np.inf)
    np.minimum.at(lo, loop_isl, uv)
    np.maximum.at(hi, loop_isl, uv)
    uv1 = (uv - ((lo + hi) * 0.5)[loop_isl]) * s[loop_isl][:, None]
    layer = mesh.uv_layers.new(name=name)
    layer.data.foreach_set("uv", uv1.astype(np.float32).ravel())
    mesh.uv_layers.active_index = 0
    mesh.uv_layers[0].active_render = True
    ratio = ((AUV * s * s) / np.maximum(A3, 1e-18))[~degen]
    umax = float(np.abs(uv1).max())
    return {"islands": n, "metres_per_uv_unit_p5_p50_p95": C.rv(np.percentile(s, [5, 50, 95]), 5),
            "uv1_abs_max_m": C.r(umax, 4),
            "half_float_step_at_abs_max_mm": C.r(2.0 ** (np.floor(np.log2(max(umax, 1e-6))) - 10) * 1000.0, 4),
            "density_ratio_min_max": [C.r(ratio.min(), 6), C.r(ratio.max(), 6)], "degenerate_uv0_islands": int(degen.sum()),
            "degenerate_islands_3d_area_share": C.r(A3[degen].sum() / A3.sum(), 7)}


def uv1_density_readback(obj, layer_name):
    mesh = obj.data
    isl, _uv0, ls, lt = islands(mesh)
    uv1 = np.empty(len(mesh.loops) * 2, np.float64)
    mesh.uv_layers[layer_name].data.foreach_get("uv", uv1)
    a1 = poly_uv_area(uv1.reshape(-1, 2), ls, lt)
    a3 = poly_areas(obj)
    n = int(isl.max()) + 1
    keep = (np.bincount(isl, a3, n) > 1e-12) & (np.bincount(isl, poly_uv_area(_uv0, ls, lt), n) >= 1e-10)
    return (np.bincount(isl, a1, n) / np.maximum(np.bincount(isl, a3, n), 1e-18))[keep]


def loops_signature(obj):
    mesh = obj.data
    co = np.empty(len(mesh.vertices) * 3)
    mesh.vertices.foreach_get("co", co)
    lv = np.empty(len(mesh.loops), np.int64)
    mesh.loops.foreach_get("vertex_index", lv)
    uv = np.empty(len(mesh.loops) * 2)
    mesh.uv_layers[0].data.foreach_get("uv", uv)
    mw = np.array(obj.matrix_world)
    p = co.reshape(-1, 3) @ mw[:3, :3].T + mw[:3, 3]
    return p[lv], uv.reshape(-1, 2)


def main():
    prof_path = Path(C.script_args()[0]).resolve()
    prof = C.load_profile(prof_path)
    ld = prof["lookdev"]
    run = C.REPO / prof["run_dir"]
    src_run = C.REPO / ld["source"]["run"]
    src = C.load_profile(C.REPO / ld["source"]["profile"])
    N_ = src["names"]
    checks = CORE.Checks()
    src_fbx = {k: src_run / "export" / src["exports"][k] for k in ("skeletal_fbx", "base_fbx")}
    shas = {p.name: C.sha256(p) for p in src_fbx.values()}
    checks("source_fbx_sha256", shas == ld["source"]["fbx_sha256"], shas, ld["source"]["fbx_sha256"])
    bpy.ops.wm.read_factory_settings(use_empty=True)
    scene = bpy.context.scene
    blend = src_run / "work" / "h2-candidate.blend"
    objs = append_objects(blend, [src["armature"]["object"], N_["body_object"], N_["base_object"]])
    arm, body, base = objs[src["armature"]["object"]], objs[N_["body_object"]], objs[N_["base_object"]]
    checks("session_blend_path_empty", bpy.data.filepath == "", bpy.data.filepath, "")
    mods = {o.name: [(m.type, m.object.name if getattr(m, "object", None) else None) for m in o.modifiers] for o in (body, base)}
    checks("appended_skinning_intact", mods[body.name] == [("ARMATURE", arm.name)] and mods[base.name] == [], mods)
    px = ld["prefix"]
    for img in bpy.data.images:
        if img.filepath and "_BC" in Path(img.filepath).name and "_Base_" not in Path(img.filepath).name:
            img.filepath = str(run / "textures" / "2k" / ("%s_BC.png" % px))
            img.name = "%s_BC.png" % px
        elif img.filepath and "_Base_" in Path(img.filepath).name:
            nm = Path(img.filepath).name.replace(ld["source"]["prefix"], px)
            img.filepath = str(run / "textures" / "base_1k" / nm)
            img.name = nm
    # face polygons (authored frame, -Y front) for the export-frame check
    rig = json.loads((src_run / "reports" / "h2-rig-report.json").read_text(encoding="utf-8"))
    fc = Vector(rig["measure"]["face_centroid_m"])
    face_polys = [p.index for p in body.data.polygons if (body.matrix_world @ p.center - fc).length < 0.03 and p.normal.y < -0.3]
    layer = ld["uv1"]["layer_name"]
    uv1 = {o.name: add_uv1(o, layer) for o in (body, base)}
    checks("uv1_density_authored", all(abs(v["density_ratio_min_max"][0] - 1) < 1e-4 and abs(v["density_ratio_min_max"][1] - 1) < 1e-4
                                       for v in uv1.values()), uv1, "area UV1 / area 3D = 1 per island")
    checks("uv1_half_precision", max(v["half_float_step_at_abs_max_mm"] for v in uv1.values()) <= 0.25,
           {k: v["half_float_step_at_abs_max_mm"] for k, v in uv1.items()}, "<= 0.25 mm")
    pre = {o.name: MEAS.mesh_summary(o) for o in (body, base)}
    preset_path = C.REPO / src["fbx_preset"]
    preset = CORE.load_preset(preset_path)
    rot = CORE.export_rotation(preset)
    data_scale = float(preset["temporary_data_scale"])
    CORE.transform_for_fbx(scene, arm, (body, base), Matrix.Diagonal((data_scale, data_scale, data_scale, 1.0)) @ rot)
    sk_fbx = run / "export" / ld["exports"]["skeletal_fbx"]
    base_fbx = run / "export" / ld["exports"]["base_fbx"]
    CORE.export_pair(scene, arm, (body,), base, preset, sk_fbx, base_fbx)
    raw_hits = {}
    for p in (sk_fbx, base_fbx):
        b = p.read_bytes()
        raw_hits[p.name] = int(b.count(b"C:\\Users") + b.count(b"C:/Users") + b.count(b"WebstormProjects"))
    checks("export_no_host_path", not any(raw_hits.values()), raw_hits, 0)
    bone_names = [b[0] for b in src["armature"]["bones"]]
    sets = {}
    for tag, sk, bs in (("ld", sk_fbx, base_fbx), ("h3", src_fbx["skeletal_fbx"], src_fbx["base_fbx"])):
        s1 = bpy.data.scenes.new("rt_" + tag)
        CORE.import_fbx_into(s1, sk)
        s2 = bpy.data.scenes.new("rtb_" + tag)
        CORE.import_fbx_into(s2, bs)
        m1, o1 = MEAS.roundtrip_measure(s1, bone_names)
        m2, o2 = MEAS.roundtrip_measure(s2, bone_names)
        sets[tag] = {"meas": (m1, m2), "objs": dict(o1, **o2)}
    ld_m, h_m = sets["ld"]["meas"], sets["h3"]["meas"]
    checks("bones_and_parents_as_h3", {n: v["parent"] for n, v in ld_m[0]["bones"].items()} ==
           {n: v["parent"] for n, v in h_m[0]["bones"].items()}, len(ld_m[0]["bones"]), len(h_m[0]["bones"]))
    checks("bone_heads_tails_as_h3", ld_m[0]["bones"] == h_m[0]["bones"], "equal", "equal (5 decimals, export frame)")
    tri = lambda m: {n: e["triangles"] for n, e in list(m[0]["meshes"].items()) + list(m[1]["meshes"].items())}
    checks("triangles_as_h3", tri(ld_m) == tri(h_m), tri(ld_m), tri(h_m))
    geo, same = {}, True
    for name, obj in sets["ld"]["objs"].items():
        ref = sets["h3"]["objs"].get(name)
        if ref is None or len(obj.data.loops) != len(ref.data.loops):
            same = False
            geo[name] = "missing or different loop count"
            continue
        p1, uv_a = loops_signature(obj)
        p2, uv_b = loops_signature(ref)
        dp, du = float(np.abs(p1 - p2).max()), float(np.abs(uv_a - uv_b).max())
        geo[name] = {"max_abs_position_diff": dp, "max_abs_uv0_diff": du}
        same &= dp <= 1e-6 and du <= 1e-7
    checks("positions_and_uv0_per_loop_as_h3", same, geo, "<= 1e-6 / 1e-7")
    wts = {}
    for name, obj in sets["ld"]["objs"].items():
        ref = sets["h3"]["objs"].get(name)
        if not obj.vertex_groups or ref is None:
            continue
        ga = {g.index: g.name for g in obj.vertex_groups}
        gb = {g.index: g.name for g in ref.vertex_groups}
        dmax, keys_same = 0.0, True
        for va, vb in zip(obj.data.vertices, ref.data.vertices):
            wa = {ga[x.group]: x.weight for x in va.groups if x.weight > 0}
            wb = {gb[x.group]: x.weight for x in vb.groups if x.weight > 0}
            if set(wa) != set(wb):
                keys_same = False
                break
            dmax = max([dmax] + [abs(wa[k] - wb[k]) for k in wa])
        wts[name] = {"same_bones_per_vertex": keys_same, "max_abs_weight_delta": C.r(dmax, 8)}
    checks("weights_as_h3", bool(wts) and all(v["same_bones_per_vertex"] and v["max_abs_weight_delta"] <= 1e-6 for v in wts.values()), wts)
    layers = {n: [u.name for u in o.data.uv_layers] for n, o in sets["ld"]["objs"].items()}
    checks("uv_layers_order", all(v == ["UVMap", layer] for v in layers.values()), layers, ["UVMap", layer])
    dens, ok = {}, True
    tol = float(ld["uv1"]["density_tolerance"])
    for n, o in sets["ld"]["objs"].items():
        r_ = uv1_density_readback(o, layer)
        # read back in the export frame (centimetre numbers x unit patch): the ratio is scale-free only if the
        # importer returns metres; report the raw median and check the spread around it
        med = float(np.median(r_))
        dens[n] = {"islands": int(len(r_)), "ratio_p1_p50_p99": C.rv(np.percentile(r_, [1, 50, 99]), 5)}
        ok &= abs(med - 1.0) <= tol and bool(np.all(np.abs(np.percentile(r_, [1, 99]) - 1.0) <= tol))
    checks("uv1_metres_density_readback", ok, dens, "area(UV1) / area3D = 1 +- %s (p1..p99 of islands)" % tol)
    rt_body = next(o for n, o in sets["ld"]["objs"].items() if n.startswith(N_["body_object"]))
    front_export = rot.to_3x3() @ Vector((0.0, -1.0, 0.0))
    face_rt = MEAS.facing(rt_body, face_polys) if face_polys else None
    checks("export_frame_face_along_plus_x", face_rt is not None and Vector(face_rt).dot(front_export) > 0.5 and abs(front_export.x - 1.0) < 1e-6,
           {"face_normal": face_rt, "rotated_front": C.rv(front_export, 3), "face_polygons": len(face_polys)}, "dot > 0.5, front = +X")
    slots = {n: e["material_slots"] for n, e in list(ld_m[0]["meshes"].items()) + list(ld_m[1]["meshes"].items())}
    rep = {"stage": "ld_fbx", "profile": C.rel(prof_path), "blender": bpy.app.version_string, "status": "измерено",
           "source": {"blend": C.rel(blend), "blend_sha256": C.sha256(blend), "h3_fbx": shas},
           "uv1": dict(ld["uv1"], per_mesh=uv1), "meshes_pre_export": pre, "material_slots": slots,
           "exports": {"skeletal_fbx": {"path": C.rel(sk_fbx), "sha256": C.sha256(sk_fbx), "bytes": sk_fbx.stat().st_size},
                       "base_fbx": {"path": C.rel(base_fbx), "sha256": C.sha256(base_fbx), "bytes": base_fbx.stat().st_size},
                       "settings": CORE.export_settings_report(preset, src["fbx_preset"], preset_path, data_scale)},
           "readback": {"geometry_vs_h3": geo, "weights_vs_h3": wts, "uv_layers": layers, "uv1_density": dens},
           "ue_import_notes": ["UV1_m — второй UV-канал (индекс 1): при импорте SM подставки выключить Generate Lightmap UVs "
                               "(или DstLightmapIndex >= 2), иначе UE перезапишет UV1 картой освещения",
                               "материальный слот тот же (M_Harpy_H3_Atlas): назначается MI v2 героя",
                               "у подставки UV1 есть, но она остаётся на M_UM_BaseMarker (метки, полоса команды)"],
           "checks": dict(checks), "failed": checks.failed(), "passed": not checks.failed(),
           "claims": {"art_accepted": False, "game_ready": False}}
    C.write_json(run / "reports" / "ld-fbx-report.json", rep)
    print(C.STAGE_MARKER, "ld_fbx failed:", checks.failed(), flush=True)
    if checks.failed():
        raise RuntimeError("ld_fbx checks failed: %s" % checks.failed())


main()
