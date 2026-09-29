"""Flow "whole-figure" (profile build.flow; the default when a profile names no flow): the T4 Medusa candidate.

The algorithm of blender/ASSET-MEDUSA-001/build_segmented_medusa.py and the face/neck fix of
tools/art/art004_face_skeletal_export.py, as built by tools/tripo-pipeline 0.4.0 (moved here unchanged; the
part names that 0.4.0 hard-coded — face tripo_part_10, neck tripo_part_14, bow on +X — now come from the profile):
  1. import the GLB, bake part transforms, remap part UVs into the atlas cells, scale the whole figure to the
     profile height with the base bottom at z = 0;
  2. join all parts except bow and base into the body, normalise the base footprint;
  3. measure polygon orientation per part (ray-escape test) and flip the parts that are inside-out;
  4. build the armature from the profile, weight the body by part rules, bind the bow 100 % to its bone;
     add the face material slot;
  5. write work .blend, export the skeletal FBX and the base FBX byte-deterministically (UM_FBX_v1);
  6. re-import both FBX, measure the export frame, turn the round trip back into the authored frame and
     measure every import contract there;
  7. optionally compare with a reference FBX (read only).
"""

import re
from pathlib import Path

import bpy
from mathutils import Matrix, Vector

from . import anatomy as anatomy_mod
from .core import (REFERENCE_SCENE, ROUNDTRIP_SCENE, WORK_SCENE, DEGENERATE_AREA_CM2,
                   export_pair, export_settings_report, flip_polygons, import_fbx_into, import_glb, r,
                   scene_context, sha256, to_authored_frame, transform_for_fbx)
from .measure import (AXIS_VECTORS, along, axis_name, cell_rects, centroid, compare_meshes, facing, mesh_summary,
                      orientation_scores, part_points, polygons_by_part, roundtrip_measure, ue_predicted,
                      uv_statistics, weight_summary, world_bounds)
from .mesh_ops import atlas_material, remap_uvs
from .rig import bind_rigid, bind_rules, make_armature


def prepare_parts(scene, profile, atlas, textures_dir, namer):
    parts = {}
    for obj in list(scene.objects):
        if obj.type == "MESH":
            parts[namer(obj, "objects")] = obj
    if len(parts) != profile["expected_part_count"]:
        raise RuntimeError("expected %d mesh parts, found %d" % (profile["expected_part_count"], len(parts)))
    for obj in parts.values():
        world = obj.matrix_world.copy()
        obj.parent = None
        obj.data.transform(world)
        obj.matrix_world.identity()
    for obj in [o for o in scene.objects if o.type != "MESH"]:
        bpy.data.objects.remove(obj)  # glTF helper empties; parts are already baked to world
    top = max(v.co.z for o in parts.values() for v in o.data.vertices)
    bottom = min(v.co.z for o in parts.values() for v in o.data.vertices)
    scale = profile["scale"]["figure_height_m"] / (top - bottom)
    files = {k: v["file"] for k, v in atlas["files"].items()}
    mat, mat_images = atlas_material(textures_dir, files, profile["materials"]["atlas"])
    size = atlas["size"]
    for name, obj in parts.items():
        remap_uvs(obj, atlas["cells"][name], size)
        for vert in obj.data.vertices:
            vert.co = (vert.co - Vector((0, 0, bottom))) * scale
        obj.data.materials.clear()
        obj.data.materials.append(mat)
        obj.data.update()
    return parts, mat, mat_images, {"source_top": r(top), "source_bottom": r(bottom), "scale": r(scale, 8)}


def join_body(scene, parts, profile):
    meshes = profile["meshes"]
    excluded = {meshes["bow"]["part"], meshes["base"]["part"]}
    body_parts = [obj for name, obj in sorted(parts.items()) if name not in excluded]
    for name, obj in parts.items():
        if name in excluded:
            continue
        group = obj.vertex_groups.new(name="SRC_" + name)
        group.add(list(range(len(obj.data.vertices))), 1.0, "REPLACE")
    with scene_context(scene):
        bpy.ops.object.select_all(action="DESELECT")
        for obj in body_parts:
            obj.select_set(True)
        body = parts[meshes["body"]["active_part"]]
        bpy.context.view_layer.objects.active = body
        bpy.ops.object.join()
    body.name = meshes["body"]["object"]
    body.data.name = meshes["body"]["mesh"]
    bow = parts[meshes["bow"]["part"]]
    bow.name = meshes["bow"]["object"]
    base = parts[meshes["base"]["part"]]
    base.name = meshes["base"]["object"]
    fx, fy, fz = meshes["base"]["footprint_m"]
    coords = [v.co for v in base.data.vertices]
    lo = [min(c[a] for c in coords) for a in range(3)]
    hi = [max(c[a] for c in coords) for a in range(3)]
    for v in base.data.vertices:
        v.co.x = (v.co.x - (lo[0] + hi[0]) / 2) * (fx / (hi[0] - lo[0]))
        v.co.y = (v.co.y - (lo[1] + hi[1]) / 2) * (fy / (hi[1] - lo[1]))
        v.co.z = (v.co.z - lo[2]) * (fz / (hi[2] - lo[2]))
    base.data.update()
    return body, bow, base, sorted(p for p in parts if p not in excluded)


def part_summaries(obj, labels):
    out = {}
    for part, ix in labels.items():
        pts = part_points(obj, ix)
        if not pts:
            continue
        out[part] = {"min": [min(p[a] for p in pts) for a in range(3)], "max": [max(p[a] for p in pts) for a in range(3)],
                     "centroid": [sum(p[a] for p in pts) / len(pts) for a in range(3)], "polygons": len(ix)}
    return out


def run(ctx):
    profile, params, atlas, preset = ctx.profile, ctx.params, ctx.atlas, ctx.preset
    check = ctx.checks
    rot, rot3 = ctx.rot, ctx.rot3
    axes_cfg = profile.get("axes") or {}
    bow_side = axes_cfg.get("blender_bow_side", "+X")
    front_export = rot3 @ Vector((0.0, -1.0, 0.0))  # authored front -Y in the export frame
    bow_export = rot3 @ Vector(AXIS_VECTORS[bow_side])  # authored bow side in the export frame
    face_cfg = profile["materials"].get("face_slot")
    anat_cfg = profile.get("anatomy") or {}
    face_part = anat_cfg.get("face") or (face_cfg["part"] if face_cfg else None)
    neck_part = anat_cfg.get("neck")
    if not face_part:
        raise RuntimeError("whole-figure flow: name the face part (profile anatomy.face or materials.face_slot.part)")
    try:
        scene = ctx.new_scene(WORK_SCENE)
        import_glb(scene, ctx.source)
        parts, atlas_mat, mat_images, scale_info = prepare_parts(scene, profile, atlas, params["textures_dir"], ctx.namer)
        source_polys = {name: len(obj.data.polygons) for name, obj in sorted(parts.items())}
        body, bow, base, body_part_names = join_body(scene, parts, profile)
        size = atlas["size"]
        rects = cell_rects(atlas["cells"], size)
        body_parts, unassigned = polygons_by_part(body.data, rects)
        labelled = [(body, body_parts), (bow, {profile["meshes"]["bow"]["part"]: [p.index for p in bow.data.polygons]}),
                    (base, {profile["meshes"]["base"]["part"]: [p.index for p in base.data.polygons]})]
        orient_before = orientation_scores(labelled)
        ocfg = profile["orientation"]
        inside_out = sorted(p for p, s in orient_before.items()
                            if s["score"] is not None and s["score"] < ocfg["flip_below_score"])
        check("orientation_inside_out_parts_as_profile", inside_out == sorted(ocfg["expected_inside_out_parts"]),
              inside_out, sorted(ocfg["expected_inside_out_parts"]),
              "ray-escape score < %s on the Tripo geometry" % ocfg["flip_below_score"])
        not_in_body = [p for p in inside_out if p not in body_parts]
        if not_in_body:
            raise RuntimeError("inside-out parts outside the body are not supported: %s" % not_in_body)
        arm, _bones_final = make_armature(scene, profile)
        part_vertex_counts = bind_rules(arm, body, profile["weights"], body_part_names)
        bind_rigid(arm, bow, profile["meshes"]["bow"]["bone"])
        selected = {i for p in inside_out for i in body_parts[p]}
        flip_polygons(body.data, selected)
        if face_cfg:
            face_mat = atlas_mat.copy()
            face_mat.name = face_cfg["material"]
            body.data.materials.append(face_mat)
            for index in body_parts[face_cfg["part"]]:
                body.data.polygons[index].material_index = 1
            body.data.update()
        orient_after = orientation_scores(labelled)
        bad_after = sorted(p for p, s in orient_after.items()
                           if s["score"] is None or s["score"] < ocfg["min_score_after_fix"])
        check("orientation_all_parts_outward_after_fix", not bad_after,
              {p: s["score"] for p, s in sorted(orient_after.items())}, ">= %s" % ocfg["min_score_after_fix"])

        # ---- pre-export measurements (metres)
        bone_names = [b[0] for b in profile["armature"]["bones"]]
        m0 = profile["meshes"]
        pre = {m0["body"]["object"]: mesh_summary(body), m0["bow"]["object"]: mesh_summary(bow),
               m0["base"]["object"]: mesh_summary(base)}
        weights = {"body": weight_summary(body, bone_names), "bow": weight_summary(bow, bone_names)}
        uv_stats = uv_statistics(labelled, atlas["cells"], size, 100.0)
        lo_sk, hi_sk = world_bounds([body, bow])
        lo_base, hi_base = world_bounds([base])
        lo_all, hi_all = world_bounds([body, bow, base])
        axes = {"face_mean_normal": facing(body, body_parts[face_part]),
                "bow_centroid_m": [r(sum((bow.matrix_world @ v.co)[a] for v in bow.data.vertices) / len(bow.data.vertices), 5)
                                   for a in range(3)]}
        root = arm.data.bones[profile["armature"]["bones"][0][0]]
        pivot = {"root_bone": root.name, "root_head_m": [r(c, 6) for c in root.head_local],
                 "armature_object_location": [r(c, 6) for c in arm.location]}
        anat = anatomy_mod.resolve({"head": anat_cfg.get("head"), "face": face_part, "neck": neck_part,
                                    "feet": anat_cfg.get("feet"), "weapon_hand": anat_cfg.get("weapon_hand")},
                                   part_summaries(body, body_parts),
                                   weapon_bone_head=list(arm.data.bones[m0["bow"]["bone"]].head_local))

        blend_out = Path(params["blend_out"])
        blend_out.parent.mkdir(parents=True, exist_ok=True)
        bpy.data.libraries.write(str(blend_out), {scene}, compress=False)

        # ---- export (UM_FBX_v1: rotate + scale the in-memory copy; the work .blend above stays authored)
        transform_for_fbx(scene, arm, (body, bow, base), Matrix.Scale(ctx.data_scale, 4) @ rot)
        sk_fbx, base_fbx = Path(params["sk_fbx_out"]), Path(params["base_fbx_out"])
        ctx.note_export_names()
        export_pair(scene, arm, (body, bow), base, preset, sk_fbx, base_fbx)

        # ---- round trip: first the export frame as written, then back into the authored frame
        m = profile["meshes"]
        rt = bpy.data.scenes.new(ROUNDTRIP_SCENE)
        import_fbx_into(rt, sk_fbx)
        rt_base_scene = bpy.data.scenes.new(ROUNDTRIP_SCENE + "_base")
        import_fbx_into(rt_base_scene, base_fbx)
        raw = {re.sub(r"\.\d{3}$", "", o.name): o for s in (rt, rt_base_scene) for o in s.objects if o.type == "MESH"}
        if not all(raw.get(m[k]["object"]) for k in ("body", "bow", "base")):
            raise RuntimeError("round trip lost meshes: %s" % sorted(raw))
        raw_parts, _ = polygons_by_part(raw[m["body"]["object"]].data, rects)
        lo_x, hi_x = world_bounds([raw[m["body"]["object"]], raw[m["bow"]["object"]]])
        lo_xb, hi_xb = world_bounds([raw[m["base"]["object"]]])
        export_frame = {"face_mean_normal": facing(raw[m["body"]["object"]], raw_parts.get(face_part, [])),
                        "bow_centroid_m": centroid(raw[m["bow"]["object"]]),
                        "skeletal_bounds_cm": {"min": [r(c * 100, 3) for c in lo_x], "max": [r(c * 100, 3) for c in hi_x]},
                        "base_bounds_cm": {"min": [r(c * 100, 3) for c in lo_xb], "max": [r(c * 100, 3) for c in hi_xb]}}
        inverse = rot.inverted()
        to_authored_frame(rt, inverse)
        to_authored_frame(rt_base_scene, inverse)
        rt_sk, rt_sk_meshes = roundtrip_measure(rt, bone_names)
        rt_base, rt_base_meshes = roundtrip_measure(rt_base_scene, bone_names)
        rt_body = rt_sk_meshes.get(m["body"]["object"])
        rt_bow = rt_sk_meshes.get(m["bow"]["object"])
        rt_base_obj = rt_base_meshes.get(m["base"]["object"])
        if not (rt_body and rt_bow and rt_base_obj):
            raise RuntimeError("round trip lost meshes: %s / %s" % (sorted(rt_sk_meshes), sorted(rt_base_meshes)))
        rt_parts, rt_unassigned = polygons_by_part(rt_body.data, rects)
        rt_labelled = [(rt_body, rt_parts), (rt_bow, {m["bow"]["part"]: [p.index for p in rt_bow.data.polygons]}),
                       (rt_base_obj, {m["base"]["part"]: [p.index for p in rt_base_obj.data.polygons]})]
        orient_rt = orientation_scores(rt_labelled)
        rt_lo_sk, rt_hi_sk = world_bounds([rt_body, rt_bow])

        # ---- reference (read only)
        reference = None
        ref_cfg = profile.get("reference") or {}
        ref_path = ctx.repo / ref_cfg["skeletal_fbx"] if ref_cfg.get("skeletal_fbx") else None
        if ref_path and ref_path.is_file():
            ref_hash = sha256(ref_path)
            ref_scene = bpy.data.scenes.new(REFERENCE_SCENE)
            import_fbx_into(ref_scene, ref_path)
            ref_meshes = {re.sub(r"\.\d{3}$", "", o.name): o for o in ref_scene.objects if o.type == "MESH"}
            ref_arm = next((o for o in ref_scene.objects if o.type == "ARMATURE"), None)
            part_of_poly = {i: p for p, idx in rt_parts.items() for i in idx}
            reference = {"skeletal_fbx": ref_cfg["skeletal_fbx"], "sha256": ref_hash,
                         "sha256_matches_profile": ref_hash == ref_cfg.get("skeletal_fbx_sha256"),
                         "body": compare_meshes(rt_body, ref_meshes[m["body"]["object"]], part_of_poly),
                         "bow": compare_meshes(rt_bow, ref_meshes[m["bow"]["object"]],
                                               {p.index: m["bow"]["part"] for p in rt_bow.data.polygons})}
            if ref_arm:
                arm_rt = next(o for o in rt.objects if o.type == "ARMATURE")
                diffs = []
                for b in arm_rt.data.bones:
                    rb = ref_arm.data.bones.get(b.name)
                    if rb is None:
                        diffs.append(b.name + ": missing in reference")
                        continue
                    for tag, va, vb in (("head", arm_rt.matrix_world @ b.head_local, ref_arm.matrix_world @ rb.head_local),
                                        ("tail", arm_rt.matrix_world @ b.tail_local, ref_arm.matrix_world @ rb.tail_local)):
                        if (va - vb).length > 1e-5:
                            diffs.append("%s %s differs by %.6f m" % (b.name, tag, (va - vb).length))
                reference["bones_identical"] = not diffs and len(arm_rt.data.bones) == len(ref_arm.data.bones)
                reference["bone_differences"] = diffs
            base_ref = ctx.repo / ref_cfg["base_fbx"] if ref_cfg.get("base_fbx") else None
            if base_ref and base_ref.is_file():
                bref_scene = bpy.data.scenes.new(REFERENCE_SCENE + "_base")
                import_fbx_into(bref_scene, base_ref)
                bref = next(o for o in bref_scene.objects if o.type == "MESH")
                reference["base_fbx"] = ref_cfg["base_fbx"]
                reference["base_sha256"] = sha256(base_ref)
                reference["base"] = compare_meshes(rt_base_obj, bref, {p.index: m["base"]["part"]
                                                                      for p in rt_base_obj.data.polygons})
    finally:
        ctx.end()  # live isolation: the session is cleaned before the checks (they use plain values only)

    # ---------------------------------------------------------------- checks
    exp = profile["expectations"]
    tris = {n: pre[n]["triangles"] for n in pre}
    check("triangles_as_profile", tris == exp["triangles"], tris, exp["triangles"])
    check("face_slot_polygons", len(body_parts.get(face_part, [])) == exp["face_slot_polygons"],
          len(body_parts.get(face_part, [])), exp["face_slot_polygons"])
    if neck_part:
        check("neck_polygons", len(body_parts.get(neck_part, [])) == exp["neck_polygons"],
              len(body_parts.get(neck_part, [])), exp["neck_polygons"])
    check("every_body_polygon_in_one_atlas_cell", unassigned == 0 and rt_unassigned == 0,
          {"build": unassigned, "roundtrip": rt_unassigned})
    uv_outside = sum(s["loops_outside_cell_inner_rect"] for s in uv_stats.values())
    check("uv0_single_layer_on_every_mesh", all(pre[n]["uv_layers"] == ["UVMap"] for n in pre),
          {n: pre[n]["uv_layers"] for n in pre})
    check("uv0_inside_unit_square", all(pre[n]["uv0_in_unit_square"] for n in pre),
          {n: pre[n]["uv0_in_unit_square"] for n in pre})
    check("uv0_inside_own_atlas_cell", uv_outside == 0, uv_outside,
          note="every UV corner lies in its part's inner cell rect (gutter kept)")
    overlap = {p: s["overlap_ratio"] for p, s in sorted(uv_stats.items())}
    check("uv0_raster_overlap_measured", True, overlap,
          note="informational: texels covered by >= 2 triangles / covered texels, per part at atlas resolution")
    check("weights_every_vertex_weighted", weights["body"]["unweighted_vertices"] == 0 and
          weights["bow"]["unweighted_vertices"] == 0,
          {"body": weights["body"]["unweighted_vertices"], "bow": weights["bow"]["unweighted_vertices"]})
    check("weights_max_influences", max(weights["body"]["max_influences"], weights["bow"]["max_influences"])
          <= profile["armature"]["max_influences"],
          max(weights["body"]["max_influences"], weights["bow"]["max_influences"]), profile["armature"]["max_influences"])
    check("bow_bound_only_to_weapon", list(weights["bow"]["bones_used"]) == [m["bow"]["bone"]],
          weights["bow"]["bones_used"])
    height = hi_all[2] - lo_all[2]
    check("height_m", abs(height - profile["scale"]["figure_height_m"]) < 1e-5 and abs(lo_all[2]) < 1e-6
          and abs(hi_sk[2] - profile["scale"]["figure_height_m"]) < 1e-5,
          {"figure_with_base": r(height, 6), "skeletal_top": r(hi_sk[2], 6), "lowest": r(lo_all[2], 6)},
          profile["scale"]["figure_height_m"])
    fx, fy, fz = m["base"]["footprint_m"]
    base_dims = [r(hi_base[i] - lo_base[i], 6) for i in range(3)]
    check("base_footprint_and_pivot", all(abs(a - b) < 1e-6 for a, b in zip(base_dims, (fx, fy, fz)))
          and all(abs(lo_base[i] + hi_base[i]) < 1e-6 for i in range(2)) and abs(lo_base[2]) < 1e-6,
          {"dimensions_m": base_dims, "centre_xy_m": [r((lo_base[i] + hi_base[i]) / 2, 6) for i in range(2)],
           "bottom_z_m": r(lo_base[2], 6)}, {"dimensions_m": [fx, fy, fz], "centre_xy_m": [0, 0], "bottom_z_m": 0})
    check("pivot_root_at_origin", pivot["root_head_m"] == [0.0, 0.0, 0.0] and
          pivot["armature_object_location"] == [0.0, 0.0, 0.0], pivot)
    check("axes_face_points_minus_y", axes["face_mean_normal"] is not None and axes["face_mean_normal"][1] < -0.3,
          axes["face_mean_normal"], "-Y (Blender front)")
    side_index = 0 if bow_side in ("+X", "-X") else 1
    side_sign = 1 if bow_side.startswith("+") else -1
    check("axes_bow_on_%s_%s" % ("plus" if side_sign > 0 else "minus", bow_side[1].lower()),
          side_sign * axes["bow_centroid_m"][side_index] > 0, axes["bow_centroid_m"],
          "%s (Blender, bow side; profile axes.blender_bow_side)" % bow_side)
    # export frame as written into the FBX (UM_FBX_v1 rotation); ART-001 maps it onto UE as (x, -y, z)
    front_name, bow_name = axis_name(front_export), axis_name(bow_export)
    face_along, face_cross = along(export_frame["face_mean_normal"] or (0, 0, 0), front_export)
    check("export_frame_face_points_along_rotated_front", face_along > 0.3 and face_cross < face_along,
          {"face_mean_normal": export_frame["face_mean_normal"], "along_front": face_along,
           "largest_horizontal_cross": face_cross}, "%s (authored -Y rotated by %s deg about Z)"
          % (front_name, preset["export_space_rotation_z_degrees"]),
          "area-weighted mean normal of the face part in the re-imported FBX, before undoing the rotation")
    bow_along, _ = along(export_frame["bow_centroid_m"], bow_export)
    check("export_frame_bow_on_rotated_side", bow_along > 0, export_frame["bow_centroid_m"],
          "%s (authored %s rotated)" % (bow_name, bow_side))
    all_tris = {n: [pre[n]["polygons"], pre[n]["triangles"]] for n in pre}
    rt_all = dict(rt_sk["meshes"], **rt_base["meshes"])
    check("triangulate_changes_no_geometry", all(p == t for p, t in all_tris.values()) and
          all(e["polygons"] == e["triangles"] for e in rt_all.values()),
          {"pre_export_polygons_triangles": all_tris,
           "roundtrip_polygons_triangles": {n: [e["polygons"], e["triangles"]] for n, e in sorted(rt_all.items())}},
          note="preset use_triangles=%s; the meshes are already all triangles, so Triangulate is a no-op"
               % preset["use_triangles"])
    # round trip
    check("roundtrip_one_armature", rt_sk["armatures"] == 1 and rt_base["armatures"] == 0,
          {"skeletal_fbx": rt_sk["armatures"], "base_fbx": rt_base["armatures"]})
    rt_bones = rt_sk["bones"]
    check("roundtrip_bones", sorted(rt_bones) == sorted(bone_names) and len(rt_bones) == exp["bones"],
          len(rt_bones), exp["bones"])
    parents_ok = all(rt_bones.get(n, {}).get("parent") == p for n, p, _h, _t in profile["armature"]["bones"])
    heads_ok = all(rt_bones.get(n) and all(abs(a - b) < 1e-4 for a, b in zip(rt_bones[n]["head_m"], h))
                   for n, _p, h, _t in profile["armature"]["bones"])
    check("roundtrip_bone_hierarchy_and_rest_positions", parents_ok and heads_ok,
          {"parents_ok": parents_ok, "heads_within_1e-4_m": heads_ok})
    rt_tris = {n: e["triangles"] for n, e in rt_sk["meshes"].items()}
    rt_tris.update({n: e["triangles"] for n, e in rt_base["meshes"].items()})
    check("roundtrip_triangles_preserved", rt_tris == tris, rt_tris, tris)
    rt_slots = {n: e["material_slots"] for n, e in rt_sk["meshes"].items()}
    rt_slots.update({n: e["material_slots"] for n, e in rt_base["meshes"].items()})
    sk_unique = sorted({s for n in (m["body"]["object"], m["bow"]["object"]) for s in rt_slots.get(n, []) if s})
    check("roundtrip_material_slots", len(sk_unique) == exp["skeletal_material_slots"] and
          len(rt_slots.get(m["base"]["object"], [])) == exp["base_material_slots"],
          {"per_mesh": rt_slots, "skeletal_unique": sk_unique},
          {"skeletal_unique": exp["skeletal_material_slots"], "base": exp["base_material_slots"]})
    check("roundtrip_uv0", all(e["uv_layers"] == ["UVMap"] and e["uv0_in_unit_square"]
                               for e in list(rt_sk["meshes"].values()) + list(rt_base["meshes"].values())),
          {n: e["uv_layers"] for n, e in list(rt_sk["meshes"].items()) + list(rt_base["meshes"].items())})
    rt_w = {n: e["weights"] for n, e in rt_sk["meshes"].items()}
    check("roundtrip_weights", rt_w[m["body"]["object"]]["unweighted_vertices"] == 0 and
          list(rt_w[m["bow"]["object"]]["bones_used"]) == [m["bow"]["bone"]] and
          max(w["max_influences"] for w in rt_w.values()) <= profile["armature"]["max_influences"],
          {n: {k: w[k] for k in ("max_influences", "unweighted_vertices")} for n, w in rt_w.items()})
    rt_bad = sorted(p for p, s in orient_rt.items() if s["score"] is None or s["score"] < ocfg["min_score_after_fix"])
    check("roundtrip_orientation_all_parts_outward", not rt_bad,
          {p: s["score"] for p, s in sorted(orient_rt.items())}, ">= %s" % ocfg["min_score_after_fix"])
    ratio = [r((rt_hi_sk[i] - rt_lo_sk[i]) / (hi_sk[i] - lo_sk[i]), 6) for i in range(3)]
    check("roundtrip_scale_ratio_1", all(abs(v - 1) < 1e-4 for v in ratio), ratio,
          note="Blender re-reads the cm FBX (UnitScaleFactor 1.0) as metres")
    part_counts_ok = len(rt_parts.get(face_part, [])) == exp["face_slot_polygons"]
    if neck_part:
        part_counts_ok = part_counts_ok and len(rt_parts.get(neck_part, [])) == exp["neck_polygons"]
    check("roundtrip_part_polygon_counts", part_counts_ok, {p: len(v) for p, v in sorted(rt_parts.items())})
    if reference:
        body_cmp = reference["body"]
        flipped_parts = sorted(p for p, n in body_cmp["flipped_winding_by_part"].items() if n)
        fixed_in_reference = set(ref_cfg.get("parts_fixed_in_reference") or [face_part] + ([neck_part] if neck_part else []))
        expected_flip = sorted(set(inside_out) - fixed_in_reference)
        full_flip = all(body_cmp["flipped_winding_by_part"].get(p, 0) == len(rt_parts.get(p, []))
                        for p in expected_flip)
        check("reference_v2_same_geometry_uv_material",
              body_cmp["unmatched_candidate_polygons"] == 0 and body_cmp["unmatched_reference_polygons"] == 0 and
              reference["bow"]["unmatched_candidate_polygons"] == 0 and reference["bones_identical"],
              {"body_unmatched": [body_cmp["unmatched_candidate_polygons"], body_cmp["unmatched_reference_polygons"]],
               "bow_unmatched": [reference["bow"]["unmatched_candidate_polygons"],
                                 reference["bow"]["unmatched_reference_polygons"]],
               "bones_identical": reference.get("bones_identical")},
              note="read-only comparison with %s" % reference["skeletal_fbx"])
        check("reference_v2_winding_differs_only_in_new_fixes", flipped_parts == expected_flip and full_flip,
              {"flipped_vs_reference": flipped_parts,
               "counts": {p: body_cmp["flipped_winding_by_part"].get(p, 0) for p in flipped_parts}},
              expected_flip, "the reference fixed %s only; any other inside-out part is expected to differ fully"
              % sorted(fixed_in_reference))
        if "base" in reference:
            check("reference_base_same_geometry", reference["base"]["unmatched_candidate_polygons"] == 0 and
                  reference["base"]["unmatched_reference_polygons"] == 0,
                  [reference["base"]["unmatched_candidate_polygons"], reference["base"]["unmatched_reference_polygons"]])
        corner_other = {k: reference[k]["corner_normals_other_by_part"] for k in ("body", "bow", "base") if k in reference}
        other_detail = {k: reference[k]["corner_normals_other_detail"] for k in corner_other}
        other_total = sum(v for d in corner_other.values() for v in d.values())
        slivers_only = all(e["touches_near_degenerate"] for d in other_detail.values() for e in d) and \
            other_total == sum(len(d) for d in other_detail.values())
        negated = sorted(p for p, n in body_cmp["corner_normals_negated_by_part"].items() if n)
        check("reference_corner_normals_rotated_consistently", slivers_only and negated == expected_flip,
              {"other_by_mesh": corner_other, "other_detail": other_detail, "negated_parts": negated},
              {"other": "only at vertices of near-degenerate triangles (< %s cm2)" % DEGENERATE_AREA_CM2,
               "negated_parts": expected_flip},
              "corner normals equal the unrotated reference (|dot| > 0.999) after undoing the export rotation, "
              "negated only on the parts whose winding this candidate fixes. Exception, reported per corner: the face "
              "normal of a sliver triangle is numerically undefined: the export rotation (even an exact axis permutation "
              "changes the float summation order) changes it and shifts the exported normals of the corners that "
              "share its vertices (measured: not caused by Triangulate)")

    report = {
        "stage": "build",
        "flow": "whole-figure",
        "blender": bpy.app.version_string,
        "profile": {"id": profile["profile_id"], "status": profile["status"]},
        "source": {"file": ctx.source.name, "sha256": ctx.source_hash},
        "isolation_note": "live: temporary scenes, all created datablocks removed" if ctx.isolation == "live" else "process",
        "scale": scale_info,
        "source_part_polygons": source_polys,
        "body_parts": body_part_names,
        "body_part_vertex_counts": part_vertex_counts,
        "anatomy": anat,
        "orientation": {"method": ocfg["method"], "before_fix": orient_before, "flipped_parts": inside_out,
                        "flipped_polygons": len(selected), "after_fix": orient_after, "roundtrip": orient_rt},
        "materials": {"atlas": profile["materials"]["atlas"], "face_slot": face_cfg, "blender_images": mat_images},
        "meshes_pre_export_m": pre,
        "weights": weights,
        "uv": uv_stats,
        "figure": {"figure_height_m": profile["scale"]["figure_height_m"], "top_part": None,
                   "figure_top_m": r(hi_all[2]), "skeletal_top_m": r(hi_sk[2]), "skeletal_top_is_figure_top": True,
                   "note": "whole-figure flow: the figure (with base) is scaled to the profile height; the skeletal top "
                           "is the figure top"},
        "bounds_m": {"skeletal": {"min": [r(c) for c in lo_sk], "max": [r(c) for c in hi_sk]},
                     "base": {"min": [r(c) for c in lo_base], "max": [r(c) for c in hi_base]},
                     "figure_with_base_height": r(height)},
        "expected_ue_bounds_uu_at_import_scale_1": {
            "skeletal_blender_axes": {"min": [r(c * 100, 3) for c in lo_sk], "max": [r(c * 100, 3) for c in hi_sk]},
            "base_blender_axes": {"min": [r(c * 100, 3) for c in lo_base], "max": [r(c * 100, 3) for c in hi_base]},
            "export_rotation_z_degrees": float(preset["export_space_rotation_z_degrees"]),
            "skeletal_export_frame": export_frame["skeletal_bounds_cm"],
            "base_export_frame": export_frame["base_bounds_cm"],
            "skeletal_ue_predicted": ue_predicted(export_frame["skeletal_bounds_cm"]),
            "base_ue_predicted": ue_predicted(export_frame["base_bounds_cm"]),
            "note": "*_blender_axes: authored Blender frame (front -Y), centimetres; *_export_frame: as written "
                    "into the FBX (re-imported); *_ue_predicted: export frame mapped as UE (x, -y, z) per ART-001. "
                    "ue-import measures the real mapping"},
        "axes": dict(axes, export_frame={"face_mean_normal": export_frame["face_mean_normal"],
                                         "bow_centroid_m": export_frame["bow_centroid_m"],
                                         "front_axis": front_name, "bow_side_axis": bow_name}),
        "pivot": pivot,
        "exports": {"skeletal": {"file": sk_fbx.name, "sha256": sha256(sk_fbx), "bytes": sk_fbx.stat().st_size},
                    "base": {"file": base_fbx.name, "sha256": sha256(base_fbx), "bytes": base_fbx.stat().st_size},
                    "settings": export_settings_report(preset, ctx.preset_rel, ctx.preset_path, ctx.data_scale)},
        "roundtrip": {"skeletal": rt_sk, "base": rt_base, "scale_ratio": ratio},
        "reference_comparison": reference,
        "checks": dict(check),
        "passed": not check.failed(),
        "status": "technically_exported_not_art_accepted",
        "not_checked": [
            "art acceptance, silhouette, lighting, K1/K2/K3 (art track)",
            "deformation quality in animation; clips are not built by this stage",
            "budgets: numbers are measured only (proposals until GD-058)",
            "UV intra-part island padding (Tripo's own layout inside each cell)",
            "collision capsule (04 §3.1 UCP_ proposal)",
            "UE-side facing: measured by ue-import (bounds axis map) and editor frames, not here",
        ],
    }
    return report
