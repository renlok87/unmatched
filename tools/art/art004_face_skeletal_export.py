"""Export an isolated Medusa skeletal face probe.

This reads the committed .blend and writes only to ignored Artifacts. Existing
production FBXs, .blend, and clips are not changed.
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
    bpy.ops.export_scene.fbx(
        filepath=str(OUTPUT), use_selection=True,
        object_types={"ARMATURE", "MESH"},
        apply_unit_scale=True, apply_scale_options="FBX_SCALE_UNITS",
        axis_forward="-Y", axis_up="Z", add_leaf_bones=False,
        bake_anim=False, bake_anim_use_nla_strips=False,
        bake_anim_use_all_actions=False, mesh_smooth_type="FACE",
        path_mode="AUTO", embed_textures=False,
    )
    patch_fbx_units(OUTPUT)
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
    OUTPUT.with_suffix(".json").write_text(json.dumps(report, indent=2) + "\n")
    print("ART004_FACE_SKELETAL_EXPORT_COMPLETE", json.dumps(report))


main()
