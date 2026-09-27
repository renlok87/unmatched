"""Export ART-005 decorative board probe with the verified UM_FBX_v1 preset."""

from __future__ import annotations

import hashlib
import json
import math
import sys
from pathlib import Path

import bpy
from mathutils import Matrix


ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / "blender/ASSET-BOARD-COBBLE-001"
BLEND = SOURCE / "cobble-city-probe.blend"
OUT = SOURCE / "export"
PRESET = ROOT / "blender/_tools/presets/UM_FBX_v1.json"
sys.path.insert(0, str(ROOT / "blender/_tools"))
from batch_export import export_fbx, patch_fbx_unit_scale  # noqa: E402


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    bpy.ops.wm.open_mainfile(filepath=str(BLEND))
    preset = json.loads(PRESET.read_text(encoding="utf-8"))
    OUT.mkdir(parents=True, exist_ok=True)
    source_collections = (
        "L2_Decorative_Stone_NoCollision",
        "L2_Wood_Frame_NoCollision",
        "L3_Undertray_NoCollision",
    )
    sources = [obj for name in source_collections for obj in bpy.data.collections[name].objects if obj.type == "MESH"]
    if len(sources) != 35:
        raise RuntimeError(f"Expected 30 tiles + 4 frame rails + 1 undertray, got {len(sources)}")
    temp = bpy.data.collections.new("ART005_ExportOnly")
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
        if not clone.data.uv_layers:
            raise RuntimeError(f"Missing UV0: {source.name}")
        clones.append(clone)
    path = OUT / "SM_ART005_BoardCobbleProbe.fbx"
    export_fbx(path, clones, preset, animation=False)
    old_scale = patch_fbx_unit_scale(path, float(preset["patch_fbx_unit_scale_to"]))
    report = {
        "status": "decorative static probe only; no baked zones or gameplay collision",
        "source_blend": str(BLEND.relative_to(ROOT)).replace("\\", "/"),
        "source_blend_sha256": sha(BLEND),
        "fbx": str(path.relative_to(ROOT)).replace("\\", "/"),
        "fbx_sha256": sha(path),
        "fbx_bytes": path.stat().st_size,
        "mesh_parts": len(clones),
        "unit_scale_factor_before_patch": old_scale,
        "unit_scale_factor_after_patch": float(preset["patch_fbx_unit_scale_to"]),
        "preset": str(PRESET.relative_to(ROOT)).replace("\\", "/"),
    }
    (OUT / "export-manifest.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print("ART005_BOARD_EXPORT_COMPLETE 35")


if __name__ == "__main__":
    main()
