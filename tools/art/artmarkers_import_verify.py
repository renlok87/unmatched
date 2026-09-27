"""Import the ART marker candidate into isolated UE ArtTests assets (no level)."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import unreal as u


ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / "blender/ASSET-MARKERS-001"
EXPORT = SOURCE / "export"
DEST = "/Game/ArtTests/ARTMarkers/Meshes"
REPORT = SOURCE / "ue-import-report.json"


def import_static(path: Path, name: str):
    task = u.AssetImportTask()
    task.filename = str(path)
    task.destination_path = DEST
    task.destination_name = name
    task.automated = True
    task.replace_existing = True
    task.save = True
    options = u.FbxImportUI()
    options.import_mesh = True
    options.import_as_skeletal = False
    options.mesh_type_to_import = u.FBXImportType.FBXIT_STATIC_MESH
    options.import_materials = False
    options.import_textures = False
    options.static_mesh_import_data.combine_meshes = True
    options.static_mesh_import_data.import_uniform_scale = 1.0
    options.static_mesh_import_data.auto_generate_collision = False
    task.options = options
    u.AssetToolsHelpers.get_asset_tools().import_asset_tasks([task])
    asset = u.load_asset(DEST + "/" + name)
    if not asset:
        raise RuntimeError(f"UE import failed: {name}")
    return asset


def simple_collision(mesh):
    body = mesh.get_editor_property("body_setup")
    if not body:
        return {"convex": 0, "other": 0}
    aggregate = body.get_editor_property("agg_geom")
    convex = len(aggregate.get_editor_property("convex_elems"))
    other = sum(len(aggregate.get_editor_property(key)) for key in (
        "box_elems", "sphere_elems", "sphyl_elems", "tapered_capsule_elems",
    ))
    return {"convex": convex, "other": other}


def main():
    build = json.loads((SOURCE / "build-report.json").read_text(encoding="utf-8"))
    manifest = json.loads((EXPORT / "export-manifest.json").read_text(encoding="utf-8"))
    if len(manifest["files"]) != 7 or len(build["meshes"]) != 7:
        raise RuntimeError("Expected exactly seven authored marker meshes")
    results = {}
    for entry in manifest["files"]:
        path = EXPORT / entry["file"]
        actual_sha = hashlib.sha256(path.read_bytes()).hexdigest()
        if actual_sha != entry["sha256"]:
            raise RuntimeError(f"FBX hash changed: {path}")
        name = path.stem
        mesh = import_static(path, name)
        bounds = mesh.get_bounding_box()
        imported = [[getattr(bounds.min, axis), getattr(bounds.max, axis)] for axis in ("x", "y", "z")]
        source = build["meshes"][name]["bounds_m"]
        src_xy = sorted(100 * (hi - lo) for lo, hi in source[:2])
        ue_xy = sorted(hi - lo for lo, hi in imported[:2])
        if any(abs(a - b) > 0.5 for a, b in zip(src_xy, ue_xy)):
            raise RuntimeError(f"UE XY size mismatch for {name}: expected {src_xy}, got {ue_xy}")
        if any(abs(imported[2][i] - 100 * source[2][i]) > 0.5 for i in range(2)):
            raise RuntimeError(f"UE Z/pivot mismatch for {name}: expected {source[2]}, got {imported[2]}")
        sections = mesh.get_num_sections(0)
        materials = len(mesh.get_editor_property("static_materials"))
        collision = simple_collision(mesh)
        if sections != 1 or materials != 1:
            raise RuntimeError(f"Bad UE section/material count for {name}: {sections}/{materials}")
        if name == "SM_Marker_TargetRing":
            if collision != {"convex": 4, "other": 0}:
                raise RuntimeError(f"Target ring UCX import failed: {collision}")
        elif collision != {"convex": 0, "other": 0}:
            raise RuntimeError(f"Unexpected gameplay collision on {name}: {collision}")
        results[name] = {
            "asset": DEST + "/" + name,
            "bounds_uu": [[round(v, 4) for v in axis] for axis in imported],
            "sections_lod0": sections,
            "material_slots": materials,
            "simple_collision": collision,
            "fbx_sha256": actual_sha,
        }
        u.log(f"ART_MARKERS_UE_IMPORT {name} dims={ue_xy} collision={collision}")
    REPORT.write_text(json.dumps({
        "status": "editor_import_pass_no_level_capture",
        "engine": "Unreal Engine 5.8.2",
        "destination": DEST,
        "meshes": results,
        "limits": "No level, gameplay click, team/state material parameter binding, HUD/zones, K1/K2/K3 or packaged FPS validation",
    }, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("ART_MARKERS_UE_IMPORT_PASS 7")


main()
