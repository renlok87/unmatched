"""Export an isolated Medusa skeletal face probe.

This reads the committed .blend and writes only to ignored Artifacts. Existing
production FBXs, .blend, and clips are not changed.
"""

import json
import os
import struct
from pathlib import Path

import bmesh
import bpy
from mathutils import Matrix


ROOT = Path(__file__).resolve().parents[2]
BLEND = ROOT / "blender/ASSET-MEDUSA-001/medusa.blend"
ATLAS = ROOT / "blender/ASSET-MEDUSA-001/atlas-report.json"
OUTPUT = ROOT / "unreal/Unmatched/Artifacts/ART004Face/SK_Medusa_FaceFix.fbx"
FRONT_ONLY = os.environ.get("ART004_FACE_FRONT_ONLY", "0") == "1"
FACE_SLOT = os.environ.get("ART004_FACE_SLOT", "0") == "1"
RESTORE_NORMALS = os.environ.get("ART004_FACE_RESTORE_NORMALS", "0") == "1"
if FRONT_ONLY and FACE_SLOT:
    raise ValueError("Choose either front-only winding or separate face slot")
if RESTORE_NORMALS and (FRONT_ONLY or FACE_SLOT):
    raise ValueError("Restored normals require the complete face winding probe")
if FRONT_ONLY:
    OUTPUT = OUTPUT.with_name("SK_Medusa_FaceFrontOnly.fbx")
if FACE_SLOT:
    OUTPUT = OUTPUT.with_name("SK_Medusa_FaceSlot.fbx")
if RESTORE_NORMALS:
    OUTPUT = OUTPUT.with_name("SK_Medusa_FaceFixNormals.fbx")


def face_indices(mesh):
    cell = json.loads(ATLAS.read_text())["cells"]["tripo_part_10"]
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
    part = face_indices(mesh)
    assert len(part) == 587, len(part)
    if FACE_SLOT:
        face_material = mesh.materials[0].copy()
        face_material.name = "M_Medusa_Face_TwoSidedProbe"
        mesh.materials.append(face_material)
        for index in part:
            mesh.polygons[index].material_index = 1
        mesh.update()
        return 0, None
    y_values = [mesh.polygons[index].center.y for index in part]
    mid_y = (min(y_values) + max(y_values)) / 2
    selected = ({index for index in part
                 if mesh.polygons[index].center.y < mid_y and
                    mesh.polygons[index].normal.y > .1}
                if FRONT_ONLY else part)
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
    return len(selected), mid_y


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
    flipped, mid_y = flip_face(body.data)
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
              "front_mid_y_m": mid_y, "flipped_faces": flipped,
              "body_triangles": sum(len(p.vertices) - 2 for p in body.data.polygons),
              "bow_triangles": sum(len(p.vertices) - 2 for p in bow.data.polygons),
              "bones": len(arm.data.bones), "material_slots": len(body.data.materials)}
    OUTPUT.with_suffix(".json").write_text(json.dumps(report, indent=2) + "\n")
    print("ART004_FACE_SKELETAL_EXPORT_COMPLETE", json.dumps(report))


main()
