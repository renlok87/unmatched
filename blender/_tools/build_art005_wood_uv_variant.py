"""Correct frame-rail grain direction in a separate Cobble City board candidate."""

from __future__ import annotations

import hashlib
import json
import math
import sys
from pathlib import Path

import bpy
from mathutils import Matrix


ROOT = Path(__file__).resolve().parents[2]
BOARD = ROOT / "blender/ASSET-BOARD-COBBLE-001"
SOURCE = BOARD / "variants/B-atlas-v1/cobble-city-atlas-B-v1.blend"
SOURCE_MANIFEST = BOARD / "variants/B-atlas-v1/export/export-manifest.json"
STONE = BOARD / "textures/T_ART005_CobbleBoardAtlas_B_v4_candidate.png"
OUT = BOARD / "variants/B-atlas-v4-woodUV"
BLEND = OUT / "cobble-city-stone-v4-wood-uv.blend"
EXPORT = OUT / "export/SM_ART005_BoardStoneV4_WoodUV.fbx"
REPORT = OUT / "build-report.json"
PRESET = ROOT / "blender/_tools/presets/UM_FBX_v1.json"

sys.path.insert(0, str(ROOT / "blender/_tools"))
from batch_export import export_fbx, patch_fbx_unit_scale  # noqa: E402


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def remap_rail(obj) -> dict:
    if obj.type != "MESH" or obj.data.uv_layers.active is None:
        raise RuntimeError(f"Frame rail or UV missing: {obj.name}")
    uv = obj.data.uv_layers.active
    long_axis = 1 if obj.name in ("Frame_West", "Frame_East") else 0
    cross_axis = 1 - long_axis
    length = obj.dimensions[long_axis]
    width = obj.dimensions[cross_axis]
    height = obj.dimensions.z
    visible_faces = 0
    for face in obj.data.polygons:
        is_end = abs(face.normal[long_axis]) > 0.9
        is_top_or_bottom = abs(face.normal.z) > 0.9
        for index in face.loop_indices:
            point = obj.data.vertices[obj.data.loops[index].vertex_index].co
            cross = point[cross_axis] / width + 0.5
            along = point[long_axis] / length + 0.5
            vertical = point.z / height + 0.5
            if is_end:
                pair = (cross, vertical)
            elif is_top_or_bottom:
                pair = (cross, along)
            else:
                pair = (vertical, along)
            uv.data[index].uv = pair
        if not is_end:
            visible_faces += 1
            pairs = [uv.data[index].uv for index in face.loop_indices]
            u_span = max(pair.x for pair in pairs) - min(pair.x for pair in pairs)
            v_span = max(pair.y for pair in pairs) - min(pair.y for pair in pairs)
            if abs(u_span - 1.0) > 1e-5 or abs(v_span - 1.0) > 1e-5:
                raise RuntimeError(f"Incorrect wood grain UV span on {obj.name}: {u_span}, {v_span}")
    if visible_faces != 4:
        raise RuntimeError(f"Expected four visible faces on {obj.name}, got {visible_faces}")
    return {
        "name": obj.name,
        "uv_layer": uv.name,
        "length_axis": "Y" if long_axis == 1 else "X",
        "length_m": round(length, 4),
        "visible_faces_along_texture_v": visible_faces,
    }


def main() -> None:
    source_manifest = json.loads(SOURCE_MANIFEST.read_text(encoding="utf-8"))
    if sha256(SOURCE) != source_manifest["source_blend_sha256"]:
        raise RuntimeError("The B-atlas-v1 source blend changed")
    if not STONE.is_file():
        raise FileNotFoundError(STONE)
    OUT.mkdir(parents=True, exist_ok=True)
    EXPORT.parent.mkdir(parents=True, exist_ok=True)
    bpy.ops.wm.open_mainfile(filepath=str(SOURCE))
    bpy.context.preferences.filepaths.save_version = 0
    rails = [remap_rail(bpy.data.objects[name]) for name in
             ("Frame_West", "Frame_East", "Frame_North", "Frame_South")]
    material = bpy.data.materials["M_ART005_Stone_AtlasB_Provisional"]
    image_nodes = [node for node in material.node_tree.nodes if node.type == "TEX_IMAGE"]
    if len(image_nodes) != 1:
        raise RuntimeError("Expected one stone image node")
    image = bpy.data.images.load(str(STONE), check_existing=False)
    image.colorspace_settings.name = "sRGB"
    image_nodes[0].image = image

    bpy.ops.wm.save_as_mainfile(filepath=str(BLEND))
    bpy.ops.file.make_paths_relative()
    bpy.ops.wm.save_as_mainfile(filepath=str(BLEND))

    source_collections = (
        "L2_Decorative_Stone_NoCollision",
        "L2_Wood_Frame_NoCollision",
        "L3_Undertray_NoCollision",
    )
    sources = [obj for name in source_collections
               for obj in bpy.data.collections[name].objects if obj.type == "MESH"]
    if len(sources) != 35:
        raise RuntimeError(f"Expected 35 board parts, got {len(sources)}")
    polygons = sum(len(obj.data.polygons) for obj in sources)
    preset = json.loads(PRESET.read_text(encoding="utf-8"))
    temp = bpy.data.collections.new("ART005_WoodUV_ExportOnly")
    bpy.context.scene.collection.children.link(temp)
    transform = Matrix.Scale(float(preset["temporary_data_scale"]), 4) @ Matrix.Rotation(
        math.radians(float(preset["export_space_rotation_z_degrees"])), 4, "Z"
    )
    clones = []
    for source in sources:
        clone = source.copy()
        clone.data = source.data.copy()
        temp.objects.link(clone)
        clone.matrix_world = source.matrix_world.copy()
        bpy.ops.object.select_all(action="DESELECT")
        clone.select_set(True)
        bpy.context.view_layer.objects.active = clone
        bpy.ops.object.transform_apply(location=False, rotation=True, scale=True)
        clone.location = transform @ clone.location
        clone.data.transform(transform)
        clones.append(clone)
    export_fbx(EXPORT, clones, preset, animation=False)
    old_scale = patch_fbx_unit_scale(EXPORT, float(preset["patch_fbx_unit_scale_to"]))
    if len(clones) != source_manifest["mesh_parts"]:
        raise RuntimeError("Mesh part count changed during export")
    REPORT.write_text(json.dumps({
        "status": "editor_wood_uv_candidate_not_art_acceptance",
        "source_blend": str(SOURCE.relative_to(ROOT)).replace("\\", "/"),
        "source_sha256": source_manifest["source_blend_sha256"],
        "blend": str(BLEND.relative_to(ROOT)).replace("\\", "/"),
        "blend_sha256": sha256(BLEND),
        "fbx": str(EXPORT.relative_to(ROOT)).replace("\\", "/"),
        "fbx_sha256": sha256(EXPORT),
        "source_stone": str(STONE.relative_to(ROOT)).replace("\\", "/"),
        "source_stone_sha256": sha256(STONE),
        "mesh_parts": len(clones),
        "source_polygons": polygons,
        "rails": rails,
        "unit_scale_factor_before_patch": old_scale,
        "unit_scale_factor_after_patch": float(preset["patch_fbx_unit_scale_to"]),
        "changes": "Only four frame-rail UV maps and the referenced stone BaseColor image changed; source geometry and old wood texture were retained.",
        "limits": "UV direction fixes cross-grain mapping but does not prove that every corner join is visually acceptable; inspect in Unreal K1 and close view.",
    }, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("ART005_WOOD_UV_VARIANT_PASS 35")


if __name__ == "__main__":
    main()
