"""Build one reusable dark-iron corner strap for the provisional board frame."""

from __future__ import annotations

import hashlib
import json
import math
import sys
from pathlib import Path

import bpy
from mathutils import Matrix


ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "blender/ASSET-BOARD-COBBLE-001/variants/corner-bracket-v1"
BLEND = OUT / "corner-bracket-v1.blend"
FBX = OUT / "export/SM_ART005_CornerBracket_v1.fbx"
REPORT = OUT / "build-report.json"
PRESET_PATH = ROOT / "blender/_tools/presets/UM_FBX_v1.json"

sys.path.insert(0, str(ROOT / "blender/_tools"))
from batch_export import export_fbx, patch_fbx_unit_scale  # noqa: E402


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def add_prism(vertices: list, faces: list, outline: list, bottom: float, top: float):
    first = len(vertices)
    vertices.extend((x, y, bottom) for x, y in outline)
    vertices.extend((x, y, top) for x, y in outline)
    n = len(outline)
    faces.append(tuple(first + i for i in reversed(range(n))))
    faces.append(tuple(first + n + i for i in range(n)))
    for i in range(n):
        j = (i + 1) % n
        faces.append((first + i, first + j, first + n + j, first + n + i))


def main():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.context.preferences.filepaths.save_version = 0
    OUT.mkdir(parents=True, exist_ok=True)
    FBX.parent.mkdir(parents=True, exist_ok=True)
    scene = bpy.context.scene
    scene.unit_settings.system = "METRIC"
    frame = bpy.data.collections.new("L3_Corner_Bracket_NoCollision")
    scene.collection.children.link(frame)

    # Local origin is the inside corner of the board. Positive X/Y are
    # outward; the two arms remain outside the playable X/Y rectangle.
    outline = [
        (0.01, -0.32), (0.23, -0.32), (0.23, 0.23),
        (-0.32, 0.23), (-0.32, 0.01), (0.01, 0.01),
    ]
    vertices: list[tuple[float, float, float]] = []
    faces: list[tuple[int, ...]] = []
    add_prism(vertices, faces, outline, 0.052, 0.075)
    for cx, cy in ((0.12, -0.22), (-0.22, 0.12)):
        ring = [(cx + 0.024 * math.cos(2 * math.pi * i / 8),
                 cy + 0.024 * math.sin(2 * math.pi * i / 8)) for i in range(8)]
        add_prism(vertices, faces, ring, 0.075, 0.088)
    mesh = bpy.data.meshes.new("CornerBracketMesh")
    mesh.from_pydata(vertices, [], faces)
    mesh.update()
    obj = bpy.data.objects.new("CornerBracket", mesh)
    frame.objects.link(obj)
    obj["art_layer"] = "decor"
    obj["gameplay_collision"] = False
    uv = mesh.uv_layers.new(name="UV0")
    for face in mesh.polygons:
        normal = face.normal
        dominant = max(range(3), key=lambda axis: abs(normal[axis]))
        axes = ((1, 2), (0, 2), (0, 1))[dominant]
        for index in face.loop_indices:
            point = mesh.vertices[mesh.loops[index].vertex_index].co
            uv.data[index].uv = ((point[axes[0]] + 0.32) / 0.55,
                                 (point[axes[1]] + 0.32) / 0.55)
    material = bpy.data.materials.new("M_ART005_IronCorner_Provisional")
    material.use_nodes = True
    shader = material.node_tree.nodes.get("Principled BSDF")
    shader.inputs["Base Color"].default_value = (0.032, 0.038, 0.045, 1.0)
    shader.inputs["Metallic"].default_value = 0.25
    shader.inputs["Roughness"].default_value = 0.86
    mesh.materials.append(material)
    bpy.ops.wm.save_as_mainfile(filepath=str(BLEND))

    preset = json.loads(PRESET_PATH.read_text(encoding="utf-8"))
    clone = obj.copy()
    clone.data = obj.data.copy()
    temp = bpy.data.collections.new("ART005_Corner_ExportOnly")
    scene.collection.children.link(temp)
    temp.objects.link(clone)
    transform = Matrix.Scale(float(preset["temporary_data_scale"]), 4) @ Matrix.Rotation(
        math.radians(float(preset["export_space_rotation_z_degrees"])), 4, "Z"
    )
    clone.data.transform(transform)
    export_fbx(FBX, [clone], preset, animation=False)
    old_scale = patch_fbx_unit_scale(FBX, float(preset["patch_fbx_unit_scale_to"]))
    tris = sum(len(face.vertices) - 2 for face in mesh.polygons)
    bounds = [[min(vertex.co[axis] for vertex in mesh.vertices),
               max(vertex.co[axis] for vertex in mesh.vertices)] for axis in range(3)]
    REPORT.write_text(json.dumps({
        "status": "modular_corner_candidate_not_board_acceptance",
        "blend": str(BLEND.relative_to(ROOT)).replace("\\", "/"),
        "blend_sha256": sha256(BLEND),
        "fbx": str(FBX.relative_to(ROOT)).replace("\\", "/"),
        "fbx_sha256": sha256(FBX),
        "preset": str(PRESET_PATH.relative_to(ROOT)).replace("\\", "/"),
        "unit_scale_factor_before_patch": old_scale,
        "unit_scale_factor_after_patch": float(preset["patch_fbx_unit_scale_to"]),
        "parts": 1,
        "material_slots": 1,
        "vertices": len(vertices),
        "triangles": tris,
        "rivet_count": 2,
        "outline_m_local": outline,
        "minimum_playable_clearance_m": 0.01,
        "bounds_m_local": [[round(value, 4) for value in pair] for pair in bounds],
        "local_origin": "inner board corner; +X/+Y point outward, +Z is board height",
        "gameplay_collision": False,
        "material_candidate": {"base_color_linear": [0.032, 0.038, 0.045], "metallic": 0.25, "roughness": 0.86},
        "limits": "Provisional ornamental joint for the S04 5x6 editor board. Final board dimensions, palette and D-07 performance remain open.",
    }, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("ART005_CORNER_BRACKET_BUILD_PASS")


if __name__ == "__main__":
    main()
