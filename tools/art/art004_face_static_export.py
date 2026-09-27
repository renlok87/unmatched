"""Export a frozen Medusa body/bow for a Blender-versus-UE face diagnostic.

Run with Blender in the background. This reads the committed .blend, evaluates
the existing Idle pose at frame 29, and writes only to ignored UE Artifacts.
It does not alter the rig, animations, source blend, or production FBXs.
"""

import json
import os
import struct
from pathlib import Path

import bpy
import bmesh
from mathutils import Matrix


ROOT = Path(__file__).resolve().parents[2]
BLEND = ROOT / "blender/ASSET-MEDUSA-001/medusa.blend"
FLIP_HEAD = os.environ.get("ART004_FACE_FLIP_HEAD", "0") == "1"
CLEAR_NORMALS = FLIP_HEAD and os.environ.get("ART004_FACE_CLEAR_NORMALS", "0") == "1"
OUTPUT = ROOT / "unreal/Unmatched/Artifacts/ART004Face" / (
    "SM_Medusa_FlippedHeadRecalc.fbx" if CLEAR_NORMALS else (
        "SM_Medusa_FlippedHead.fbx" if FLIP_HEAD else "SM_Medusa_FrozenIdle.fbx"))
REPORT = OUTPUT.with_suffix(".json")


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
    scene = bpy.context.scene
    armature = bpy.data.objects["SKEL_Medusa"]
    action = bpy.data.actions["Idle"]
    armature.animation_data.action = action
    scene.frame_set(29)
    depsgraph = bpy.context.evaluated_depsgraph_get()
    bpy.ops.object.select_all(action="DESELECT")

    meshes = []
    flipped_faces = 0
    atlas = json.loads((ROOT / "blender/ASSET-MEDUSA-001/atlas-report.json").read_text())
    cell = atlas["cells"]["tripo_part_10"]
    u_min = (cell["x"] + cell["inset"]) / 2048
    u_max = (cell["x"] + cell["cell"] - cell["inset"]) / 2048
    v_min = 1 - (cell["y_top"] + cell["cell"] - cell["inset"]) / 2048
    v_max = 1 - (cell["y_top"] + cell["inset"]) / 2048
    for name in ("SK_Medusa_Body", "SK_Medusa_Bow"):
        source = bpy.data.objects[name]
        evaluated = source.evaluated_get(depsgraph)
        mesh = bpy.data.meshes.new_from_object(evaluated, preserve_all_data_layers=True,
                                                depsgraph=depsgraph)
        assert mesh.uv_layers, name + " has no UV layer"
        if FLIP_HEAD and name == "SK_Medusa_Body":
            uv = mesh.uv_layers.active.data
            selected = {face.index for face in mesh.polygons
                        if all(u_min <= uv[loop].uv.x <= u_max and
                               v_min <= uv[loop].uv.y <= v_max
                               for loop in face.loop_indices)}
            editable = bmesh.new()
            editable.from_mesh(mesh)
            editable.faces.index_update()
            for face in editable.faces:
                if face.index in selected:
                    face.normal_flip()
                    flipped_faces += 1
            editable.to_mesh(mesh)
            editable.free()
            if CLEAR_NORMALS:
                custom = mesh.attributes.get("custom_normal")
                if custom:
                    mesh.attributes.remove(custom)
            mesh.update()
            assert flipped_faces == 587, flipped_faces
        mesh.transform(source.matrix_world @ Matrix.Scale(100, 4))
        frozen = bpy.data.objects.new("SM_Frozen_" + name, mesh)
        scene.collection.objects.link(frozen)
        frozen.select_set(True)
        meshes.append(frozen)

    bpy.context.view_layer.objects.active = meshes[0]
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    bpy.ops.export_scene.fbx(
        filepath=str(OUTPUT), use_selection=True, object_types={"MESH"},
        apply_unit_scale=True, apply_scale_options="FBX_SCALE_UNITS",
        axis_forward="-Y", axis_up="Z", bake_anim=False,
        mesh_smooth_type="FACE", path_mode="AUTO", embed_textures=False,
    )
    patch_fbx_units(OUTPUT)
    vertices = [vertex.co for obj in meshes for vertex in obj.data.vertices]
    report = {
        "source": str(BLEND), "output": str(OUTPUT), "frame": 29,
        "action": action.name, "flip_head_group": FLIP_HEAD,
        "clear_custom_normals": CLEAR_NORMALS,
        "flipped_faces": flipped_faces,
        "parts": [{"name": obj.name, "tris": sum(len(poly.vertices) - 2
                                                 for poly in obj.data.polygons),
                   "uv_layers": len(obj.data.uv_layers)} for obj in meshes],
        "bounds_uu": {axis: [round(min(v[i] for v in vertices), 4),
                             round(max(v[i] for v in vertices), 4)]
                      for i, axis in enumerate("xyz")},
    }
    REPORT.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print("ART004_FACE_STATIC_EXPORT_COMPLETE", json.dumps(report))


main()
