"""Export an isolated Medusa skeletal candidate with corrected face winding.

This reads the committed .blend and writes only to ignored Artifacts. Existing
production FBXs, .blend, and clips are not changed.
"""

import json
import struct
from pathlib import Path

import bmesh
import bpy
from mathutils import Matrix


ROOT = Path(__file__).resolve().parents[2]
BLEND = ROOT / "blender/ASSET-MEDUSA-001/medusa.blend"
ATLAS = ROOT / "blender/ASSET-MEDUSA-001/atlas-report.json"
OUTPUT = ROOT / "unreal/Unmatched/Artifacts/ART004Face/SK_Medusa_FaceFix.fbx"


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
    selected = face_indices(mesh)
    assert len(selected) == 587, len(selected)
    editable = bmesh.new()
    editable.from_mesh(mesh)
    editable.faces.index_update()
    for face in editable.faces:
        if face.index in selected:
            face.normal_flip()
    editable.to_mesh(mesh)
    editable.free()
    custom = mesh.attributes.get("custom_normal")
    if custom:
        mesh.attributes.remove(custom)
    mesh.update()
    return len(selected)


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
    flipped = flip_face(body.data)
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
              "face_part": "tripo_part_10", "flipped_faces": flipped,
              "body_triangles": sum(len(p.vertices) - 2 for p in body.data.polygons),
              "bow_triangles": sum(len(p.vertices) - 2 for p in bow.data.polygons),
              "bones": len(arm.data.bones), "material_slots": len(body.data.materials)}
    OUTPUT.with_suffix(".json").write_text(json.dumps(report, indent=2) + "\n")
    print("ART004_FACE_SKELETAL_EXPORT_COMPLETE", json.dumps(report))


main()
