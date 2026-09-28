"""Independent read-back of the three mannequin FBX files (only reads them and the authored .blend).

Headless only:
  blender -b --factory-startup --python-exit-code 1 --python readback_fbx.py -- <run_dir> <profile.json> <out.json>

Per FBX, in a fresh factory-empty scene with the Blender FBX importer defaults:
  objects and types, triangles, material slots, UV layers, the UM_Mask colour layer (binary, R corners),
  world bounds as written (export frame, uu) and the UE bounds predicted by the ART-001 map ue = (x, -y, z);
  then every root object is turned back by the inverse of the preset rotation and the evaluated vertices are
  compared with the authored .blend (nearest-vertex distance both ways, KDTree); for the skeletal FBX also the
  armature object name, 17 bones and parents vs rig-contract.json, bone heads vs the profile, influences per
  vertex and the bone of every vertex vs its nearest authored vertex; facing: the feet lie at +X and the left
  hand at +Y of the export frame (UE: front +X, left -Y).
"""

import json
import math
import sys
from pathlib import Path

import bpy
from mathutils import Matrix, Vector
from mathutils.kdtree import KDTree

if not bpy.app.background:
    raise RuntimeError("readback_fbx.py: headless only (blender -b)")

REPO = Path(__file__).resolve().parents[4]


def rr(v, n=6):
    return round(float(v), n)


def rv(vec, n=6):
    return [rr(c, n) for c in vec]


def rel(p):
    try:
        return Path(p).resolve().relative_to(REPO).as_posix()
    except ValueError:
        return Path(p).as_posix()


def world_points(obj, evaluated=True):
    if evaluated:
        dg = bpy.context.evaluated_depsgraph_get()
        ev = obj.evaluated_get(dg)
        me = ev.to_mesh()
        pts = [obj.matrix_world @ v.co for v in me.vertices]
        ev.to_mesh_clear()
        return pts
    return [obj.matrix_world @ v.co for v in obj.data.vertices]


def bounds(pts):
    lo = Vector((min(p.x for p in pts), min(p.y for p in pts), min(p.z for p in pts)))
    hi = Vector((max(p.x for p in pts), max(p.y for p in pts), max(p.z for p in pts)))
    return lo, hi


def kd(points):
    t = KDTree(len(points))
    for i, p in enumerate(points):
        t.insert(p, i)
    t.balance()
    return t


def authored_data(blend):
    bpy.ops.wm.open_mainfile(filepath=str(blend))
    out = {}
    for obj in bpy.data.objects:
        if obj.type == "MESH":
            groups = {g.index: g.name for g in obj.vertex_groups}
            vb = [groups[v.groups[0].group] if len(v.groups) else None for v in obj.data.vertices]
            out[obj.name] = {"points": [Vector(p) for p in world_points(obj, evaluated=False)], "vertex_bone": vb,
                             "tris": sum(len(p.vertices) - 2 for p in obj.data.polygons)}
        elif obj.type == "ARMATURE":
            out[obj.name] = {"heads": {b.name: obj.matrix_world @ b.head_local for b in obj.data.bones}}
    return out


def mask_info(me):
    if "UM_Mask" not in me.color_attributes:
        return {"present": False, "layers": [a.name for a in me.color_attributes]}
    a = me.color_attributes["UM_Mask"]
    vals = [tuple(d.color) for d in a.data]
    binary = all(abs(c) < 2e-3 or abs(c - 1) < 2e-3 for col in vals for c in col)
    return {"present": True, "layers": [x.name for x in me.color_attributes], "domain": a.domain, "type": a.data_type,
            "binary": binary, "corners_R1": sum(1 for c in vals if c[0] > 0.5), "corners_G1": sum(1 for c in vals if c[1] > 0.5),
            "corners_B1": sum(1 for c in vals if c[2] > 0.5), "corners": len(vals)}


def main():
    argv = sys.argv[sys.argv.index("--") + 1:]
    run_dir, profile_path, out_path = Path(argv[0]).resolve(), Path(argv[1]).resolve(), Path(argv[2]).resolve()
    profile = json.loads(profile_path.read_text(encoding="utf-8"))
    preset = json.loads((REPO / profile["fbx_preset"]).read_text(encoding="utf-8"))
    contract = json.loads((REPO / profile["rig_contract"]).read_text(encoding="utf-8"))
    sk = contract["skeletons"][profile["armature"]["skeleton"]]
    inv = Matrix.Rotation(math.radians(-float(preset["export_space_rotation_z_degrees"])), 4, "Z")
    authored = authored_data(run_dir / "work" / "mannequin.blend")
    v = profile["variants"]
    files = {"skeletal": v["skeletal"]["fbx"], "skeletal_base": v["skeletal"]["base_fbx"], "static": v["static"]["fbx"]}
    expect_objects = {"skeletal": [v["skeletal"]["object"], profile["armature"]["object"]],
                      "skeletal_base": [v["skeletal"]["base_object"]],
                      "static": [v["static"]["object"], v["static"]["collision_object"]]}
    report = {"method": __doc__.strip().splitlines()[0], "blender": bpy.app.version_string, "files": {}, "checks": {}}
    checks = report["checks"]

    def check(name, ok, measured, expected=None):
        checks[name] = {"passed": bool(ok), "measured": measured}
        if expected is not None:
            checks[name]["expected"] = expected

    for key, fname in files.items():
        path = run_dir / "export" / fname
        bpy.ops.wm.read_factory_settings(use_empty=True)
        bpy.ops.import_scene.fbx(filepath=str(path))
        scene = bpy.context.scene
        objs = sorted(scene.objects, key=lambda o: o.name)
        info = {"file": rel(path), "objects": [{"name": o.name, "type": o.type, "parent": o.parent.name if o.parent else None,
                                                "scale": rv(o.scale), "location": rv(o.location)} for o in objs]}
        meshes = [o for o in objs if o.type == "MESH"]
        arms = [o for o in objs if o.type == "ARMATURE"]
        check("%s_objects" % key, sorted(o.name for o in objs) == sorted(expect_objects[key]),
              sorted(o.name for o in objs), sorted(expect_objects[key]))
        per_mesh = {}
        export_pts = {}
        for m in meshes:
            me = m.data
            pts = world_points(m)
            export_pts[m.name] = pts
            lo, hi = bounds(pts)
            per_mesh[m.name] = {"triangles": sum(len(p.vertices) - 2 for p in me.polygons), "vertices": len(me.vertices),
                                "material_slots": [s.material.name if s.material else None for s in m.material_slots],
                                "uv_layers": [l.name for l in me.uv_layers], "mask": mask_info(me),
                                "export_frame_bounds_uu": {"min": rv(lo * 100, 3), "max": rv(hi * 100, 3)},
                                "export_frame_dimensions_uu": rv((hi - lo) * 100, 3),
                                "predicted_ue_bounds_uu": {"min": [rr(lo.x * 100, 3), rr(-hi.y * 100, 3), rr(lo.z * 100, 3)],
                                                           "max": [rr(hi.x * 100, 3), rr(-lo.y * 100, 3), rr(hi.z * 100, 3)]}}
        # back to the authored frame
        for o in scene.objects:
            if o.parent is None:
                o.matrix_world = inv @ o.matrix_world
        bpy.context.view_layer.update()
        for m in meshes:
            pts = world_points(m)
            src = authored.get(m.name)
            if src is None:
                per_mesh[m.name]["authored_match"] = "no authored object of this name"
                continue
            t_src, t_fbx = kd(src["points"]), kd(pts)
            d1 = max(t_src.find(p)[2] for p in pts)
            d2 = max(t_fbx.find(p)[2] for p in src["points"])
            per_mesh[m.name]["authored_match"] = {"max_nearest_distance_uu": rr(max(d1, d2) * 100, 5),
                                                  "vertex_count": [len(pts), len(src["points"])],
                                                  "triangles": [per_mesh[m.name]["triangles"], src["tris"]]}
            check("%s_%s_matches_authored" % (key, m.name), max(d1, d2) < 1e-5 and len(pts) == len(src["points"])
                  and per_mesh[m.name]["triangles"] == src["tris"], per_mesh[m.name]["authored_match"],
                  "same vertex count and triangles, every vertex within 0.001 uu after undoing the export rotation")
            if src["vertex_bone"][0] is not None and m.vertex_groups:
                groups = {g.index: g.name for g in m.vertex_groups}
                infl = [len([g for g in vv.groups if g.weight > 1e-6]) for vv in m.data.vertices]
                wsum = [sum(g.weight for g in vv.groups) for vv in m.data.vertices]
                mism = 0
                for p, vv in zip(pts, m.data.vertices):
                    _co, idx, _d = t_src.find(p)
                    got = groups[vv.groups[0].group] if len(vv.groups) else None
                    mism += got != src["vertex_bone"][idx]
                per_mesh[m.name]["weights"] = {"max_influences": max(infl), "min_influences": min(infl),
                                               "weight_sum_min_max": [rr(min(wsum), 6), rr(max(wsum), 6)],
                                               "vertices_with_other_bone_than_authored": mism,
                                               "groups": sorted(groups.values())}
                check("%s_weights_roundtrip" % key, max(infl) == 1 and min(infl) == 1 and mism == 0
                      and abs(min(wsum) - 1) < 1e-4 and abs(max(wsum) - 1) < 1e-4, per_mesh[m.name]["weights"])
        info["meshes"] = per_mesh
        for m in meshes:
            if m.name.startswith("UCP_"):
                continue  # collision hull: never rendered, no mask or UV needed
            mk = per_mesh[m.name]["mask"]
            check("%s_%s_mask" % (key, m.name), mk.get("present") and mk.get("binary") and mk.get("corners_G1") == 0
                  and mk.get("corners_B1") == 0, mk)
            check("%s_%s_uv0" % (key, m.name), per_mesh[m.name]["uv_layers"] == ["UVMap"],
                  per_mesh[m.name]["uv_layers"])
        if arms:
            arm = arms[0]
            have = {b.name: (b.parent.name if b.parent else None) for b in arm.data.bones}
            want = {b["name"]: b["parent"] for b in sk["bones"]}
            heads = {b.name: arm.matrix_world @ b.head_local for b in arm.data.bones}
            auth = authored[profile["armature"]["object"]]["heads"]
            dmax = max((heads[n] - auth[n]).length for n in heads if n in auth)
            info["armature"] = {"object": arm.name, "bones": len(have), "parents_match_contract": have == want,
                                "max_head_offset_vs_authored_uu": rr(dmax * 100, 5),
                                "ue_bone_count_expected": len(have) + 1,
                                "ue_bone_0": arm.name}
            check("skeletal_armature_object_name", arm.name == sk["armature_object"]["name"], arm.name,
                  sk["armature_object"]["name"])
            check("skeletal_bones_match_contract", have == want and len(have) == 17, {"count": len(have),
                  "diff": sorted(set(have.items()) ^ set(want.items()))})
            check("skeletal_bone_heads_roundtrip", dmax < 1e-5, rr(dmax * 100, 5), "< 0.001 uu")
        # facing in the export frame (before undoing): feet toward +X, left hand toward +Y
        fig_name = v["skeletal"]["object"] if key == "skeletal" else (v["static"]["object"] if key == "static" else None)
        if fig_name and fig_name in export_pts:
            pts = export_pts[fig_name]
            feet = [p for p in pts if 0.0385 < p.z < 0.066 and abs(p.y) < 0.06 and (abs(p.x) < 0.06) and
                    (key != "static" or math.hypot(p.x, p.y) < 0.075)]
            fx = sum(p.x for p in feet) / len(feet)
            hand = [p for p in pts if 0.16 < p.z < 0.21 and abs(p.y) > 0.07]
            left = [p for p in hand if p.y > 0]
            info["facing_export_frame"] = {"feet_band_vertices": len(feet), "feet_mean_x_uu": rr(fx * 100, 3),
                                           "hand_vertices_at_+Y": len(left), "hand_vertices_total": len(hand),
                                           "ue_prediction": "front +X, left hand -Y (ART-001 map ue = (x, -y, z))"}
            check("%s_facing_front_plus_x" % key, fx > 0.005, rr(fx * 100, 3), "feet centroid ahead (+X) of the pivot")
        report["files"][key] = info
    report["checks_failed"] = sorted(k for k, c in checks.items() if not c["passed"])
    report["checks_passed_count"] = sum(1 for c in checks.values() if c["passed"])
    report["checks_total"] = len(checks)
    out_path.write_text(json.dumps(report, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    print("MANNEQUIN_READBACK", "%d/%d" % (report["checks_passed_count"], report["checks_total"]), report["checks_failed"])
    if report["checks_failed"]:
        raise SystemExit(1)


main()
