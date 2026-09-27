"""Reimport the marker FBX files and check bounds, UV, origin and topology."""

from __future__ import annotations

import json
from pathlib import Path

import bmesh
import bpy
from mathutils import Vector


ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / "blender/ASSET-MARKERS-001"
OUT = SOURCE / "export"
BUILD = SOURCE / "build-report.json"
MANIFEST = OUT / "export-manifest.json"
REPORT = OUT / "roundtrip-report.json"


def bounds(obj):
    points = [obj.matrix_world @ Vector(corner) for corner in obj.bound_box]
    return [[min(point[i] for point in points), max(point[i] for point in points)] for i in range(3)]


def main():
    build = json.loads(BUILD.read_text(encoding="utf-8"))
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    if len(manifest["files"]) != 7 or len(build["meshes"]) != 7:
        raise RuntimeError("Expected seven marker files and meshes")
    report = {"status": "roundtrip_pass", "blender": bpy.app.version_string, "meshes": {}}
    for item in manifest["files"]:
        path = OUT / item["file"]
        name = path.stem
        bpy.ops.object.select_all(action="SELECT")
        bpy.ops.object.delete(use_global=False)
        bpy.ops.import_scene.fbx(filepath=str(path))
        meshes = {obj.name: obj for obj in bpy.data.objects if obj.type == "MESH"}
        expected_names = {name}
        if name == "SM_Marker_TargetRing":
            expected_names.update(f"UCX_SM_Marker_TargetRing_{q:02d}" for q in range(4))
        if set(meshes) != expected_names:
            raise RuntimeError(f"Unexpected FBX objects for {name}: {sorted(meshes)}")
        obj = meshes[name]
        source_bounds = build["meshes"][name]["bounds_m"]
        actual = bounds(obj)
        source_spans = sorted(hi - lo for lo, hi in source_bounds[:2])
        actual_spans = sorted(hi - lo for lo, hi in actual[:2])
        if any(abs(a - b) > .002 for a, b in zip(source_spans, actual_spans)):
            raise RuntimeError(f"XY bounds differ for {name}: {source_spans} vs {actual_spans}")
        if any(abs(actual[2][i] - source_bounds[2][i]) > .002 for i in range(2)):
            raise RuntimeError(f"Z bounds differ for {name}: {source_bounds[2]} vs {actual[2]}")
        if obj.location.length > 1e-5 or len(obj.data.materials) != 1 or len(obj.data.uv_layers) != 1:
            raise RuntimeError(f"Bad pivot/material/UV on {name}")
        obj.data.calc_loop_triangles()
        if len(obj.data.loop_triangles) != build["meshes"][name]["triangles"]:
            raise RuntimeError(f"Triangle count changed on {name}")
        bm = bmesh.new()
        bm.from_mesh(obj.data)
        nonmanifold = sum(not edge.is_manifold for edge in bm.edges)
        volume = bm.calc_volume(signed=True) * obj.matrix_world.to_3x3().determinant()
        bm.free()
        if nonmanifold or volume <= 0:
            raise RuntimeError(f"Topology or winding invalid on {name}: nonmanifold={nonmanifold}, signed_volume={volume}")
        if name == "SM_Marker_TargetRing":
            for q in range(4):
                hit = meshes[f"UCX_SM_Marker_TargetRing_{q:02d}"]
                if hit.location.length > 1e-5:
                    raise RuntimeError("Target hit proxy pivot shifted")
                hit_bm = bmesh.new()
                hit_bm.from_mesh(hit.data)
                bad = sum(not edge.is_manifold for edge in hit_bm.edges)
                vol = hit_bm.calc_volume(signed=True) * hit.matrix_world.to_3x3().determinant()
                hit_bm.free()
                if bad or vol <= 0:
                    raise RuntimeError(f"Target hit proxy {q} invalid: {bad} nonmanifold, {vol} volume")
        report["meshes"][name] = {
            "objects": sorted(meshes), "triangles": len(obj.data.loop_triangles),
            "bounds_m": [[round(v, 5) for v in axis] for axis in actual],
            "signed_volume_m3": round(volume, 8), "nonmanifold_edges": nonmanifold,
            "reimport_scale": [round(v, 6) for v in obj.scale],
            "material_slots": len(obj.data.materials), "uv_layers": len(obj.data.uv_layers),
        }
    REPORT.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("ART_MARKERS_ROUNDTRIP_PASS 7")


if __name__ == "__main__":
    main()
