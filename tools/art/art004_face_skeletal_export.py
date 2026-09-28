"""Export an isolated Medusa skeletal face probe.

This reads the committed .blend and writes only to ignored Artifacts. Existing
production FBXs, .blend, and clips are not changed.

v3.1 mode (stage 3 T1.2, 2026-09-28): ART004_HEAD_TILT_V31=<a|b|c> together with
ART004_FACE_RESTORE_NORMALS=1, ART004_FACE_SLOT=1 and ART004_FACE_NECK_BACK=1. It also flips the
inside-out parts tripo_part_8 (bow arm/bracer) and tripo_part_13 (right hand) like the T4 candidate,
applies the deformation field of art004_head_tilt_v31_field.py (positions + per-vertex J^-T split
normals), exports with Triangulate on and a byte-deterministic FBX writer straight into
blender/ASSET-MEDUSA-001/variants/head-tilt-v31-<x>/ (+ <name>.json report). Axes stay in the
game frame of v2/v3 (face +Y in UE, as S08FighterActor expects); ART004_V31_UM_FBX_V1=1 also
writes a <name>_UM_FBX_v1.fbx twin rotated +90 deg about Z (04 section 1 standard, face +X).
"""

import json
import math
import os
import struct
from pathlib import Path

import bmesh
import bpy
from mathutils import Matrix, Vector


ROOT = Path(__file__).resolve().parents[2]
BLEND = ROOT / "blender/ASSET-MEDUSA-001/medusa.blend"
ATLAS = ROOT / "blender/ASSET-MEDUSA-001/atlas-report.json"
OUTPUT = ROOT / "unreal/Unmatched/Artifacts/ART004Face/SK_Medusa_FaceFix.fbx"
FRONT_ONLY = os.environ.get("ART004_FACE_FRONT_ONLY", "0") == "1"
FACE_SLOT = os.environ.get("ART004_FACE_SLOT", "0") == "1"
RESTORE_NORMALS = os.environ.get("ART004_FACE_RESTORE_NORMALS", "0") == "1"
NECK_BACK = os.environ.get("ART004_FACE_NECK_BACK", "0") == "1"
CROWN_SPREAD = float(os.environ.get("ART004_CROWN_SPREAD", "0"))
HEAD_TILT_DEG = float(os.environ.get("ART004_HEAD_TILT_DEG", "0"))
V31 = os.environ.get("ART004_HEAD_TILT_V31", "")
V31_TWIN = os.environ.get("ART004_V31_UM_FBX_V1", "0") == "1"
if not 0 <= CROWN_SPREAD <= .4:
    raise ValueError("ART004_CROWN_SPREAD must be 0..0.4")
if not -25 <= HEAD_TILT_DEG <= 25 or (CROWN_SPREAD and HEAD_TILT_DEG):
    raise ValueError("Head tilt must be within ±25 degrees and separate from crown spread")
if FRONT_ONLY and FACE_SLOT:
    raise ValueError("Choose either front-only winding or separate face slot")
if RESTORE_NORMALS and FRONT_ONLY:
    raise ValueError("Restored normals require the complete face winding probe")
if NECK_BACK and not (FACE_SLOT and RESTORE_NORMALS):
    raise ValueError("Rear-neck correction requires restored normals and the face slot")
if FRONT_ONLY:
    OUTPUT = OUTPUT.with_name("SK_Medusa_FaceFrontOnly.fbx")
if FACE_SLOT:
    OUTPUT = OUTPUT.with_name("SK_Medusa_FaceSlot.fbx")
if RESTORE_NORMALS:
    OUTPUT = OUTPUT.with_name("SK_Medusa_FaceFixNormalsSlot.fbx" if FACE_SLOT else
                              "SK_Medusa_FaceFixNormals.fbx")
if NECK_BACK:
    OUTPUT = OUTPUT.with_name("SK_Medusa_FaceFixNormalsSlotNeck.fbx")
if CROWN_SPREAD:
    if not NECK_BACK:
        raise ValueError("The crown probe builds on the corrected face-and-neck candidate")
    OUTPUT = OUTPUT.with_name("SK_Medusa_CrownSpreadProbe.fbx")
if HEAD_TILT_DEG:
    if not NECK_BACK:
        raise ValueError("Head tilt probe builds on the corrected face-and-neck candidate")
    OUTPUT = OUTPUT.with_name("SK_Medusa_HeadTiltProbe.fbx")
if V31:
    import sys
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    import art004_head_tilt_v31_field as field31
    if V31 not in field31.PRESETS:
        raise ValueError("ART004_HEAD_TILT_V31 must be one of %s" % sorted(field31.PRESETS))
    if not (NECK_BACK and FACE_SLOT and RESTORE_NORMALS) or HEAD_TILT_DEG or CROWN_SPREAD:
        raise ValueError("v3.1 builds on the face/neck v2 candidate without the v3 tilt or crown probe")
    OUTPUT = (ROOT / "blender/ASSET-MEDUSA-001/variants" / ("head-tilt-v31-" + V31) /
              ("SK_Medusa_HeadTilt_v31" + V31 + ".fbx"))
elif V31_TWIN:
    raise ValueError("ART004_V31_UM_FBX_V1 needs ART004_HEAD_TILT_V31")
V31_EXTRA_FLIPS = {"tripo_part_8": 575, "tripo_part_13": 607}  # inside-out in the Tripo source (T4)


def part_indices(mesh, part_name):
    cell = json.loads(ATLAS.read_text())["cells"][part_name]
    u_min = (cell["x"] + cell["inset"]) / 2048
    u_max = (cell["x"] + cell["cell"] - cell["inset"]) / 2048
    v_min = 1 - (cell["y_top"] + cell["cell"] - cell["inset"]) / 2048
    v_max = 1 - (cell["y_top"] + cell["inset"]) / 2048
    uv = mesh.uv_layers.active.data
    return {face.index for face in mesh.polygons
            if all(u_min <= uv[loop].uv.x <= u_max and
                   v_min <= uv[loop].uv.y <= v_max
                   for loop in face.loop_indices)}


def flip_face(mesh):
    part = part_indices(mesh, "tripo_part_10")
    assert len(part) == 587, len(part)
    neck = part_indices(mesh, "tripo_part_14") if NECK_BACK else set()
    if NECK_BACK:
        assert len(neck) == 480, len(neck)
        assert not (part & neck), "Atlas parts overlap"
    if FACE_SLOT and not RESTORE_NORMALS:
        face_material = mesh.materials[0].copy()
        face_material.name = "M_Medusa_Face_TwoSidedProbe"
        mesh.materials.append(face_material)
        for index in part:
            mesh.polygons[index].material_index = 1
        mesh.update()
        return 0, None, 0
    y_values = [mesh.polygons[index].center.y for index in part]
    mid_y = (min(y_values) + max(y_values)) / 2
    selected = ({index for index in part
                 if mesh.polygons[index].center.y < mid_y and
                    mesh.polygons[index].normal.y > .1}
                if FRONT_ONLY else set(part))
    selected |= neck
    if V31:
        for name, count in V31_EXTRA_FLIPS.items():
            extra = part_indices(mesh, name)
            assert len(extra) == count, (name, len(extra))
            assert not (extra & selected), "Atlas parts overlap"
            selected |= extra
    assert selected, "No front-facing polygons selected"
    source_vertices = {poly.index: frozenset(poly.vertices) for poly in mesh.polygons}
    source_normals = {(poly.index, mesh.loops[loop].vertex_index):
                      mesh.corner_normals[loop].vector.copy()
                      for poly in mesh.polygons for loop in poly.loop_indices}
    editable = bmesh.new()
    editable.from_mesh(mesh)
    editable.faces.index_update()
    for face in editable.faces:
        if face.index in selected:
            face.normal_flip()
    editable.to_mesh(mesh)
    editable.free()
    assert all(frozenset(poly.vertices) == source_vertices[poly.index]
               for poly in mesh.polygons), "BMesh reordered polygons"
    custom = mesh.attributes.get("custom_normal")
    if custom and not RESTORE_NORMALS:
        mesh.attributes.remove(custom)
    mesh.update()
    if RESTORE_NORMALS:
        normals = [None] * len(mesh.loops)
        for poly in mesh.polygons:
            for loop in poly.loop_indices:
                normal = source_normals[(poly.index, mesh.loops[loop].vertex_index)].copy()
                if poly.index in selected:
                    normal.negate()
                normals[loop] = normal
        mesh.normals_split_custom_set(normals)
        mesh.update()
    if FACE_SLOT:
        face_material = mesh.materials[0].copy()
        face_material.name = "M_Medusa_Face_CorrectedProbe"
        mesh.materials.append(face_material)
        for index in part:
            mesh.polygons[index].material_index = 1
        mesh.update()
    return len(selected), mid_y, len(neck)


def spread_crown(mesh):
    if not CROWN_SPREAD:
        return {"moved_vertices": 0}
    # Keep the roots in place and fan the upper crown in both horizontal
    # directions. This changes silhouette only; UVs, weights and bones stay put.
    part = part_indices(mesh, "tripo_part_1")
    assert len(part) == 2633, len(part)
    indices = {index for poly in mesh.polygons if poly.index in part
               for index in poly.vertices}
    center_x, center_y = -.020, .005
    root_z, full_z = .405, .475
    moved = 0
    for index in indices:
        co = mesh.vertices[index].co
        t = max(0.0, min(1.0, (co.z - root_z) / (full_z - root_z)))
        t = t * t * (3.0 - 2.0 * t)
        if t:
            co.x = center_x + (co.x - center_x) * (1.0 + CROWN_SPREAD * t)
            co.y = center_y + (co.y - center_y) * (1.0 + CROWN_SPREAD * t)
            moved += 1
    mesh.update()
    return {"part": "tripo_part_1", "polygons": len(part),
            "moved_vertices": moved, "spread_factor": CROWN_SPREAD,
            "root_z_m": root_z, "full_z_m": full_z}


def tilt_head(mesh):
    if not HEAD_TILT_DEG:
        return {"moved_vertices": 0}
    # Face, crown and short neck are separate atlas sections. The long
    # shoulder/quiver section (part_3) is deliberately excluded.
    parts = {name: part_indices(mesh, name)
             for name in ("tripo_part_1", "tripo_part_10", "tripo_part_14")}
    assert {name: len(indices) for name, indices in parts.items()} == {
        "tripo_part_1": 2633, "tripo_part_10": 587, "tripo_part_14": 480}
    selected = set().union(*parts.values())
    vertices = {index for poly in mesh.polygons if poly.index in selected
                for index in poly.vertices}
    axis = Matrix.Rotation(math.radians(HEAD_TILT_DEG), 3, "X")
    pivot = Vector((0, 0, .385))
    split_normals = [loop.vector.copy() for loop in mesh.corner_normals]
    for index in vertices:
        co = mesh.vertices[index].co
        co[:] = pivot + axis @ (co - pivot)
    for poly in mesh.polygons:
        if poly.index in selected:
            for loop in poly.loop_indices:
                split_normals[loop] = axis @ split_normals[loop]
    mesh.update()
    mesh.normals_split_custom_set(split_normals)
    mesh.update()
    return {"parts": {name: len(indices) for name, indices in parts.items()},
            "moved_vertices": len(vertices), "degrees": HEAD_TILT_DEG,
            "pivot_m": list(pivot)}


def labels_by_vertex(mesh):
    """Atlas part of every vertex (parts are separate shells: no vertex belongs to two parts)."""
    cells = json.loads(ATLAS.read_text())["cells"]
    label = [None] * len(mesh.vertices)
    for name in cells:
        for index in part_indices(mesh, name):
            for vertex in mesh.polygons[index].vertices:
                assert label[vertex] in (None, name), "vertex shared by two parts"
                label[vertex] = name
    return label


def tilt_head_v31(mesh):
    """v3.1 field (art004_head_tilt_v31_field.py): positions and per-vertex J^-T split normals."""
    import numpy as np
    params = field31.PRESETS[V31]
    labels = np.array(labels_by_vertex(mesh), dtype=object)
    co = np.empty(len(mesh.vertices) * 3)
    mesh.vertices.foreach_get("co", co)
    co = co.reshape(-1, 3)
    corner_vertex = np.empty(len(mesh.loops), dtype=np.int64)
    mesh.loops.foreach_get("vertex_index", corner_vertex)
    normals = np.empty(len(mesh.loops) * 3)
    mesh.corner_normals.foreach_get("vector", normals)
    normals = normals.reshape(-1, 3)
    new, jac, moved = field31.apply(params, co, labels)
    new_normals = field31.transform_normals(jac[corner_vertex], normals)
    jac_err, jac_samples = field31.jacobian_check(params, co, labels)
    mesh.vertices.foreach_set("co", new.reshape(-1))
    mesh.update()
    mesh.normals_split_custom_set([tuple(n) for n in new_normals])
    mesh.update()
    check = np.empty(len(mesh.loops) * 3)
    mesh.corner_normals.foreach_get("vector", check)
    check = check.reshape(-1, 3)
    cos = np.clip((check * new_normals).sum(axis=1), -1, 1)
    disp = np.linalg.norm(new - co, axis=1)
    per_part = {}
    for name in sorted(set(labels.tolist())):
        sel = labels == name
        if (disp[sel] > 1e-9).any():
            per_part[name] = {"vertices": int(sel.sum()), "moved_vertices": int((disp[sel] > 1e-9).sum()),
                              "max_displacement_cm": round(float(disp[sel].max() * 100), 4)}
    return {"preset": V31, "params": params, "moved_vertices": int(moved.sum()), "per_part": per_part,
            "jacobian_vs_central_differences_max_abs": float("%.3g" % jac_err),
            "jacobian_check_samples": jac_samples,
            "split_normals_set_vs_requested_max_deg": round(float(np.degrees(np.arccos(cos.min()))), 4)}


def normals_tangents_health(mesh):
    import numpy as np
    n = np.empty(len(mesh.loops) * 3)
    mesh.corner_normals.foreach_get("vector", n)
    nl = np.linalg.norm(n.reshape(-1, 3), axis=1)
    mesh.calc_tangents(uvmap=mesh.uv_layers.active.name)
    t = np.empty(len(mesh.loops) * 3)
    mesh.loops.foreach_get("tangent", t)
    tl = np.linalg.norm(t.reshape(-1, 3), axis=1)
    mesh.free_tangents()
    return {"corners": len(mesh.loops),
            "zero_or_nan_corner_normals": int(((nl < 1e-6) | ~np.isfinite(nl)).sum()),
            "zero_or_nan_tangents": int(((tl < 1e-6) | ~np.isfinite(tl)).sum()),
            "polygons": len(mesh.polygons),
            "triangles": sum(len(p.vertices) - 2 for p in mesh.polygons)}


def make_fbx_deterministic():
    """Pin the FBX header time, UUID hashing and texture paths (relative in both fields).

    Same technique as tools/tripo-pipeline/blender/build_candidate.py make_fbx_deterministic():
    the exporter otherwise writes the current time and an absolute, host-specific texture path.
    Returns restore().
    """
    import datetime
    import hashlib
    from io_scene_fbx import export_fbx_bin, fbx_utils
    missing = object()
    saved = {"vid": export_fbx_bin._gen_vid_path, "datetime": export_fbx_bin.datetime,
             "hash": fbx_utils.__dict__.get("hash", missing)}
    original_vid_path = saved["vid"]

    def relative_vid_path(img, scene_data):
        _abs, rel = original_vid_path(img, scene_data)
        return rel, rel

    def stable_hash(key):
        digest = hashlib.sha256(repr(key).encode("utf-8")).digest()
        return int.from_bytes(digest[:8], "little") & ((1 << 63) - 1)

    class FixedDateTime(datetime.datetime):
        @classmethod
        def now(cls, tz=None):
            return datetime.datetime(2000, 1, 1, 0, 0, 0)

    class FixedModule:
        datetime = FixedDateTime

    original_header = export_fbx_bin.fbx_header_elements
    native = BLEND.relative_to(ROOT).as_posix().encode("utf-8")

    def header_with_relative_native_file(root, scene_data, time=None):
        # The header stores bpy.data.filepath (absolute, checkout-specific) as
        # Original|ApplicationNativeFile; write the repository-relative path instead.
        original_header(root, scene_data, time)
        pending = [root]
        while pending:
            elem = pending.pop()
            if elem.id == b"P" and elem.props and elem.props[0].endswith(b"Original|ApplicationNativeFile"):
                elem.props[-1] = struct.pack("<I", len(native)) + native
            pending.extend(elem.elems)

    export_fbx_bin._gen_vid_path = relative_vid_path
    export_fbx_bin.fbx_header_elements = header_with_relative_native_file
    fbx_utils.hash = stable_hash
    fbx_utils._keys_to_uuids.clear()
    fbx_utils._uuids_to_keys.clear()
    export_fbx_bin.datetime = FixedModule

    def restore():
        export_fbx_bin.fbx_header_elements = original_header
        export_fbx_bin._gen_vid_path = saved["vid"]
        export_fbx_bin.datetime = saved["datetime"]
        if saved["hash"] is missing:
            fbx_utils.__dict__.pop("hash", None)
        else:
            fbx_utils.hash = saved["hash"]
        fbx_utils._keys_to_uuids.clear()
        fbx_utils._uuids_to_keys.clear()
    return restore


def rotate_for_um_fbx_v1(arm, meshes):
    """UM_FBX_v1 export space: +90 deg about Z as an exact axis permutation; bones rotate rigidly."""
    rot = Matrix(((0.0, -1.0, 0.0, 0.0), (1.0, 0.0, 0.0, 0.0), (0.0, 0.0, 1.0, 0.0), (0.0, 0.0, 0.0, 1.0)))
    bpy.ops.object.select_all(action="DESELECT")
    bpy.context.view_layer.objects.active = arm
    bpy.ops.object.mode_set(mode="EDIT")
    for bone in arm.data.edit_bones:
        bone.transform(rot, scale=False, roll=True)
    bpy.ops.object.mode_set(mode="OBJECT")
    for obj in meshes:
        obj.data.transform(rot)
    return rot


def patch_fbx_units(path):
    buffer = bytearray(path.read_bytes())
    start = buffer.find(b"UnitScaleFactor")
    assert start >= 0
    token = buffer.find(b"Number", buffer.find(b"double", start))
    length = struct.unpack_from("<I", buffer, token - 4)[0]
    offset = token + length
    assert buffer[offset:offset + 1] == b"S"
    string_length = struct.unpack_from("<I", buffer, offset + 1)[0]
    offset += 1 + 4 + string_length
    assert buffer[offset:offset + 1] == b"D"
    struct.pack_into("<d", buffer, offset + 1, 1.0)
    path.write_bytes(buffer)


def main():
    if Path(bpy.data.filepath).resolve() != BLEND.resolve():
        raise RuntimeError("Launch Blender with the Medusa .blend before --python")
    arm = bpy.data.objects["SKEL_Medusa"]
    body = bpy.data.objects["SK_Medusa_Body"]
    bow = bpy.data.objects["SK_Medusa_Bow"]
    flipped, mid_y, neck_count = flip_face(body.data)
    crown = spread_crown(body.data)
    tilt = tilt_head(body.data)
    tilt_v31 = tilt_head_v31(body.data) if V31 else None
    arm.animation_data.action = None
    for bone in arm.pose.bones:
        bone.location = (0, 0, 0)
        bone.rotation_euler = (0, 0, 0)
        bone.scale = (1, 1, 1)
    bpy.context.scene.frame_set(1)
    bpy.ops.object.select_all(action="DESELECT")
    bpy.context.view_layer.objects.active = arm
    bpy.ops.object.mode_set(mode="EDIT")
    for bone in arm.data.edit_bones:
        bone.head *= 100
        bone.tail *= 100
    bpy.ops.object.mode_set(mode="OBJECT")
    for obj in (body, bow):
        obj.data.transform(Matrix.Scale(100, 4))
    arm.select_set(True)
    body.select_set(True)
    bow.select_set(True)
    bpy.context.view_layer.objects.active = arm
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    twin = None
    if V31:
        health = {"body": normals_tangents_health(body.data), "bow": normals_tangents_health(bow.data)}
        assert health["body"]["triangles"] == health["body"]["polygons"], "Triangulate would change the body"
        assert health["bow"]["triangles"] == health["bow"]["polygons"], "Triangulate would change the bow"
        restore = make_fbx_deterministic()
    try:
        bpy.ops.export_scene.fbx(
            filepath=str(OUTPUT), use_selection=True,
            object_types={"ARMATURE", "MESH"},
            apply_unit_scale=True, apply_scale_options="FBX_SCALE_UNITS",
            axis_forward="-Y", axis_up="Z", add_leaf_bones=False,
            bake_anim=False, bake_anim_use_nla_strips=False,
            bake_anim_use_all_actions=False, mesh_smooth_type="FACE",
            path_mode="RELATIVE" if V31 else "AUTO", embed_textures=False,
            **({"use_triangles": True, "primary_bone_axis": "Y", "secondary_bone_axis": "X",
                "use_custom_props": False} if V31 else {}),
        )
        patch_fbx_units(OUTPUT)
        if V31 and V31_TWIN:
            twin = OUTPUT.with_name(OUTPUT.stem + "_UM_FBX_v1.fbx")
            restore()
            restore = make_fbx_deterministic()
            rotate_for_um_fbx_v1(arm, (body, bow))
            arm.select_set(True)
            body.select_set(True)
            bow.select_set(True)
            bpy.context.view_layer.objects.active = arm
            bpy.ops.export_scene.fbx(
                filepath=str(twin), use_selection=True, object_types={"ARMATURE", "MESH"},
                apply_unit_scale=True, apply_scale_options="FBX_SCALE_UNITS",
                axis_forward="-Y", axis_up="Z", add_leaf_bones=False, bake_anim=False,
                bake_anim_use_nla_strips=False, bake_anim_use_all_actions=False,
                mesh_smooth_type="FACE", path_mode="RELATIVE", embed_textures=False,
                use_triangles=True, primary_bone_axis="Y", secondary_bone_axis="X", use_custom_props=False)
            patch_fbx_units(twin)
    finally:
        if V31:
            restore()
    report = {"input": str(BLEND), "output": str(OUTPUT),
              "face_part": "tripo_part_10", "front_only": FRONT_ONLY,
              "face_slot": FACE_SLOT, "restore_normals": RESTORE_NORMALS,
              "face_slot_polygons": 587 if FACE_SLOT else 0,
              "neck_back_polygons": neck_count,
              "front_mid_y_m": mid_y, "flipped_faces": flipped,
              "crown_probe": crown,
              "head_tilt_probe": tilt,
              "body_triangles": sum(len(p.vertices) - 2 for p in body.data.polygons),
              "bow_triangles": sum(len(p.vertices) - 2 for p in bow.data.polygons),
              "bones": len(arm.data.bones), "material_slots": len(body.data.materials)}
    if V31:
        import hashlib
        report.update({
            "input": BLEND.relative_to(ROOT).as_posix(), "output": OUTPUT.relative_to(ROOT).as_posix(),
            "input_sha256": hashlib.sha256(BLEND.read_bytes()).hexdigest(),
            "blender": bpy.app.version_string,
            "extra_flipped_parts": V31_EXTRA_FLIPS,
            "head_tilt_v31": tilt_v31,
            "normals_tangents_before_export": health,
            "fbx_sha256": hashlib.sha256(OUTPUT.read_bytes()).hexdigest(),
            "fbx_bytes": OUTPUT.stat().st_size,
            "export_settings": {
                "preset_basis": "UM_FBX_v1 (blender/_tools/presets/UM_FBX_v1.json, 04 section 1.1)",
                "axis_forward": "-Y", "axis_up": "Z", "apply_scale_options": "FBX_SCALE_UNITS",
                "data_scale": 100, "unit_scale_factor_patched": 1.0, "use_triangles": True,
                "mesh_smooth_type": "FACE", "add_leaf_bones": False, "primary_bone_axis": "Y",
                "secondary_bone_axis": "X", "bake_anim": False, "path_mode": "RELATIVE",
                "path_mode_note": "deviation from the preset's AUTO: the atlas lies outside the export folder, "
                "so AUTO writes an absolute, checkout-specific path; RELATIVE (../../textures/...) keeps the "
                "bytes identical in every checkout. The game import does not import textures.",
                "deterministic_writer": "header time 2000-01-01, sha256-based UUIDs, relative texture paths, "
                "repository-relative ApplicationNativeFile",
                "deviation_from_UM_FBX_v1": "export_space_rotation_z_degrees 0 instead of 90: game frame "
                "of v2/v3 and production SK_Medusa (face +Y in UE), because S08FighterActor::ApplyFighter "
                "sets yaw 0/180 for a +Y-facing mesh and art004_import_v2_game_candidate.py imports "
                "without rotation; the +X standard twin is written with ART004_V31_UM_FBX_V1=1"},
            "um_fbx_v1_twin": ({"path": twin.relative_to(ROOT).as_posix(),
                                "sha256": hashlib.sha256(twin.read_bytes()).hexdigest(),
                                "bytes": twin.stat().st_size, "export_space_rotation_z_degrees": 90.0,
                                "bone_rotation": "EditBone.transform(roll=True)"} if twin else None),
        })
        report.pop("front_mid_y_m", None)
        OUTPUT.with_suffix(".json").write_text(json.dumps(report, indent=2, sort_keys=True) + "\n",
                                               encoding="utf-8")
        print("ART004_FACE_SKELETAL_EXPORT_COMPLETE", report["output"], report["fbx_sha256"])
        return
    OUTPUT.with_suffix(".json").write_text(json.dumps(report, indent=2) + "\n")
    print("ART004_FACE_SKELETAL_EXPORT_COMPLETE", json.dumps(report))


main()
