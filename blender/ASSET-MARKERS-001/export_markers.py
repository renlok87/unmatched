"""Export the seven marker meshes with the verified UM_FBX_v1 transform."""

from __future__ import annotations

import hashlib
import json
import math
import sys
from pathlib import Path

import bpy
from mathutils import Matrix


ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / "blender/ASSET-MARKERS-001"
BLEND = SOURCE / "markers.blend"
OUT = SOURCE / "export"
PRESET = ROOT / "blender/_tools/presets/UM_FBX_v1.json"
sys.path.insert(0, str(ROOT / "blender/_tools"))
from batch_export import export_fbx, patch_fbx_unit_scale  # noqa: E402


NAMES = (
    "SM_Base_Hero_P1", "SM_Base_Hero_P2",
    "SM_Base_Sidekick_P1", "SM_Base_Sidekick_P2",
    "SM_Marker_SelectionRing", "SM_Marker_TargetRing", "SM_Marker_Status",
)


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    bpy.ops.wm.open_mainfile(filepath=str(BLEND))
    preset = json.loads(PRESET.read_text(encoding="utf-8"))
    OUT.mkdir(parents=True, exist_ok=True)
    temp = bpy.data.collections.new("MARKERS_FBX_EXPORT_ONLY")
    bpy.context.scene.collection.children.link(temp)
    transform = Matrix.Scale(float(preset["temporary_data_scale"]), 4) @ Matrix.Rotation(
        math.radians(float(preset["export_space_rotation_z_degrees"])), 4, "Z"
    )
    report = {
        "status": "candidate_export_no_ue_import",
        "source_blend": str(BLEND.relative_to(ROOT)).replace("\\", "/"),
        "source_sha256": sha256(BLEND),
        "preset": str(PRESET.relative_to(ROOT)).replace("\\", "/"),
        "files": [],
    }
    for name in NAMES:
        source = bpy.data.objects[name]
        original_name = source.name
        source.name = name + "_AUTHORING"
        source_objects = [source]
        if name == "SM_Marker_TargetRing":
            for quadrant in range(4):
                collider = bpy.data.objects[f"UCX_SM_Marker_TargetRing_{quadrant:02d}"]
                collider.name += "_AUTHORING"
                source_objects.append(collider)
        clones = []
        try:
            for obj in source_objects:
                clone = obj.copy()
                clone.data = obj.data.copy()
                clone.name = obj.name.removesuffix("_AUTHORING")
                temp.objects.link(clone)
                clone.hide_render = False
                clone.hide_viewport = False
                clone.matrix_world = obj.matrix_world.copy()
                if clone.location.length > 1e-6 or any(abs(a) > 1e-6 for a in clone.rotation_euler) or any(abs(s - 1) > 1e-6 for s in clone.scale):
                    raise RuntimeError(f"Non-identity source transform: {obj.name}")
                clone.data.transform(transform)
                clones.append(clone)
            path = OUT / (name + ".fbx")
            export_fbx(path, clones, preset, animation=False)
            old_scale = patch_fbx_unit_scale(path, float(preset["patch_fbx_unit_scale_to"]))
            report["files"].append({
                "file": path.name,
                "bytes": path.stat().st_size,
                "sha256": sha256(path),
                "objects": [obj.name for obj in clones],
                "unit_scale_factor_before_patch": old_scale,
                "unit_scale_factor_after_patch": float(preset["patch_fbx_unit_scale_to"]),
            })
        finally:
            for obj in clones:
                bpy.data.objects.remove(obj, do_unlink=True)
            source.name = original_name
            for obj in source_objects[1:]:
                obj.name = obj.name.removesuffix("_AUTHORING")
    (OUT / "export-manifest.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("ART_MARKERS_EXPORT_COMPLETE 7")


if __name__ == "__main__":
    main()
