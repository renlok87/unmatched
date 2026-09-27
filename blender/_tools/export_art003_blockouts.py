"""Export the four ART-003 gray probes as static FBX for an Unreal scale check.

These are disposable blockouts, not skinned production character exports.
Uses the verified ART-001 UM_FBX_v1 preset without mutating the source .blend.
"""

from __future__ import annotations

import hashlib
import json
import math
import sys
from pathlib import Path

import bpy
from mathutils import Matrix


ROOT = Path(__file__).resolve().parents[2]
BLEND = ROOT / "blender" / "A01" / "silhouette_blockouts.blend"
OUT = ROOT / "blender" / "A01" / "export"
PRESET = ROOT / "blender" / "_tools" / "presets" / "UM_FBX_v1.json"
sys.path.insert(0, str(ROOT / "blender" / "_tools"))
from batch_export import export_fbx, patch_fbx_unit_scale  # noqa: E402


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def add_probe_uv(mesh) -> None:
    """Give custom prism faces non-degenerate planar UVs without UI context."""
    uv = mesh.uv_layers.new(name="UV_Probe")
    for face in mesh.polygons:
        normal = face.normal
        dominant = max(range(3), key=lambda axis: abs(normal[axis]))
        axes = ((1, 2), (0, 2), (0, 1))[dominant]
        for loop_index in face.loop_indices:
            point = mesh.vertices[mesh.loops[loop_index].vertex_index].co
            uv.data[loop_index].uv = (point[axes[0]] / 100.0, point[axes[1]] / 100.0)
    mesh.update()


def main() -> None:
    bpy.ops.wm.open_mainfile(filepath=str(BLEND))
    preset = json.loads(PRESET.read_text(encoding="utf-8"))
    OUT.mkdir(parents=True, exist_ok=True)
    material = bpy.data.materials.new("M_ART003_GrayProbe")
    material.diffuse_color = (0.38, 0.38, 0.38, 1.0)
    temp = bpy.data.collections.new("ART003_Export_Only")
    bpy.context.scene.collection.children.link(temp)
    transform = Matrix.Scale(float(preset["temporary_data_scale"]), 4) @ Matrix.Rotation(
        math.radians(float(preset["export_space_rotation_z_degrees"])), 4, "Z"
    )
    manifest = {
        "status": "static gray UE probe, not production meshes",
        "source_blend": str(BLEND.relative_to(ROOT)).replace("\\", "/"),
        "source_sha256": digest(BLEND),
        "preset": str(PRESET.relative_to(ROOT)).replace("\\", "/"),
        "files": [],
    }
    for kind in ("medusa", "harpy", "arthur", "merlin"):
        collection = bpy.data.collections[f"Studio_{kind}"]
        clones = []
        for source in collection.objects:
            if source.type != "MESH":
                continue
            clone = source.copy()
            clone.data = source.data.copy()
            clone.name = f"ART003_{kind}_{source.name}"
            temp.objects.link(clone)
            clone.matrix_world = source.matrix_world.copy()
            clone.hide_render = False
            clone.hide_viewport = False
            clone.data.materials.clear()
            clone.data.materials.append(material)
            bpy.ops.object.select_all(action="DESELECT")
            clone.select_set(True)
            bpy.context.view_layer.objects.active = clone
            bpy.ops.object.transform_apply(location=False, rotation=True, scale=True)
            clone.location = transform @ clone.location
            clone.data.transform(transform)
            # Custom prism capes/wings have no UVs; give probe-only unwraps so
            # Unreal's MikkTSpace importer can build valid tangent bases.
            if not clone.data.uv_layers:
                add_probe_uv(clone.data)
            clones.append(clone)
        if not clones:
            raise RuntimeError(f"Empty ART-003 collection: {kind}")
        name = f"SM_ART003_{kind.title()}"
        path = OUT / f"{name}.fbx"
        export_fbx(path, clones, preset, animation=False)
        old_unit_scale = patch_fbx_unit_scale(path, float(preset["patch_fbx_unit_scale_to"]))
        manifest["files"].append(
            {
                "kind": kind,
                "name": path.name,
                "bytes": path.stat().st_size,
                "sha256": digest(path),
                "source_parts": len(clones),
                "unit_scale_factor_before_patch": old_unit_scale,
                "unit_scale_factor_after_patch": float(preset["patch_fbx_unit_scale_to"]),
            }
        )
        for clone in clones:
            mesh = clone.data
            bpy.data.objects.remove(clone, do_unlink=True)
            bpy.data.meshes.remove(mesh)
    (OUT / "export-manifest.json").write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    print("ART003_EXPORT_COMPLETE", len(manifest["files"]))


if __name__ == "__main__":
    main()
