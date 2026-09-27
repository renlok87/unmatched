"""Check that Medusa's face-section candidate only changes polygon material IDs.

Run in Blender 5.2 after exporting the one-slot restored-normal probe. The
candidate defaults to the tracked FBX; override either path with environment
variables ART004_FACE_SINGLE_FBX and ART004_FACE_SLOT_FBX if needed.
"""

import json
import os
from pathlib import Path

import bpy


ROOT = Path(__file__).resolve().parents[2]
SINGLE = Path(os.environ.get(
    "ART004_FACE_SINGLE_FBX",
    ROOT / "unreal/Unmatched/Artifacts/ART004Face/SK_Medusa_FaceFixNormals.fbx",
))
SLOT = Path(os.environ.get(
    "ART004_FACE_SLOT_FBX",
    ROOT / "blender/ASSET-MEDUSA-001/variants/face-section-v1/SK_Medusa_FaceSection_v1.fbx",
))


def inspect(path):
    if not path.is_file():
        raise FileNotFoundError(path)
    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.ops.import_scene.fbx(filepath=str(path), use_custom_normals=True)
    result = {}
    for obj in bpy.data.objects:
        if obj.type != "MESH":
            continue
        mesh = obj.data
        if not mesh.uv_layers.active:
            raise RuntimeError(f"Missing UV layer: {obj.name}")
        result[obj.name] = {
            "positions": sorted(tuple(round(value, 5) for value in obj.matrix_world @ vertex.co)
                                for vertex in mesh.vertices),
            "normals": [tuple(round(value, 4) for value in normal.vector)
                        for normal in mesh.corner_normals],
            "uv": [tuple(round(value, 5) for value in loop.uv)
                   for loop in mesh.uv_layers.active.data],
            "poly_vertices": [tuple(poly.vertices) for poly in mesh.polygons],
            "materials": [poly.material_index for poly in mesh.polygons],
        }
    return result


def main():
    original = inspect(SINGLE)
    candidate = inspect(SLOT)
    if original.keys() != candidate.keys():
        raise AssertionError(f"Mesh names differ: {sorted(original)} / {sorted(candidate)}")
    summary = {}
    for name in sorted(original):
        before, after = original[name], candidate[name]
        for field in ("positions", "normals", "uv", "poly_vertices"):
            if before[field] != after[field]:
                raise AssertionError(f"Unexpected {field} change in {name}")
        changes = sum(a != b for a, b in zip(before["materials"], after["materials"]))
        if len(before["materials"]) != len(after["materials"]):
            raise AssertionError(f"Polygon count changed in {name}")
        expected = 587 if "Body" in name else 0
        if changes != expected:
            raise AssertionError(f"{name}: material changes {changes}, expected {expected}")
        summary[name] = {
            "vertices": len(before["positions"]),
            "triangles": len(before["poly_vertices"]),
            "material_changes": changes,
        }
    if not any("Body" in name for name in summary) or not any("Bow" in name for name in summary):
        raise AssertionError("Expected body and bow meshes")
    print("ART004_FACE_FBX_COMPARE_OK", json.dumps(summary, sort_keys=True))


main()
