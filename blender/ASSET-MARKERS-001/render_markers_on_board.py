"""Preview the neutral selection, target and status meshes on a Cobble K1.

This is a Blender readability probe. Runtime zone/HUD bindings remain open.
"""

from __future__ import annotations

import json
from pathlib import Path

import bpy


ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "blender/ASSET-MARKERS-001"
SOURCE = ROOT / "blender/ASSET-BOARD-COBBLE-001/variants/B-atlas-v1/marker-placement-v2/cobble-city-atlas-B-six-blockouts-markers-v2.blend"
KIT = OUT / "markers.blend"
CONTRACT = ROOT / "docs/game-design/evidence/S04/board-contract.json"
BLEND = OUT / "preview/markers-on-board-k1-v1.blend"
PREVIEW = OUT / "preview/markers-on-board-k1-v1.png"
REPORT = OUT / "preview/markers-on-board-report.json"


def main():
    bpy.ops.wm.open_mainfile(filepath=str(SOURCE))
    bpy.context.preferences.filepaths.save_version = 0
    with bpy.data.libraries.load(str(KIT), link=False) as (source, dest):
        if "ASSET_MARKERS_001_Meshes" not in source.collections:
            raise RuntimeError("Marker kit collection missing")
        dest.collections = ["ASSET_MARKERS_001_Meshes"]
    kit = dest.collections[0]
    bpy.context.scene.collection.children.link(kit)
    contract = json.loads(CONTRACT.read_text(encoding="utf-8"))
    start = next(s for s in contract["starts"] if s["id"] == "medusa-first")
    positions = {f["id"]: f["position"] for f in start["fighters"]}
    cases = [
        ("SM_Marker_SelectionRing", "f-0-hero", (0, 0, 0)),
        ("SM_Marker_TargetRing", "f-1-hero", (0, 0, 0)),
        # The mesh pivot remains cell-centred at Z=0; the game will set an
        # instance height from the fighter silhouette. This probe uses 45 uu.
        ("SM_Marker_Status", "f-1-sk0", (0.24, 0, 0.45)),
    ]
    entries = []
    for name, fighter_id, (dx, dy, dz) in cases:
        source = kit.objects.get(name)
        if source is None:
            raise RuntimeError(f"Missing marker mesh {name}")
        obj = source.copy()
        obj.data = source.data
        obj.name = name + "__" + fighter_id + "__K1_PROBE"
        bpy.context.scene.collection.objects.link(obj)
        obj.hide_render = False
        pos = positions[fighter_id]
        obj.location = (pos["x"] - 2 + dx, pos["y"] - 2.5 + dy, dz)
        entries.append({"mesh": name, "fighter_id": fighter_id, "location_m": [round(v, 4) for v in obj.location]})
    scene = bpy.context.scene
    scene.render.engine = "CYCLES"
    scene.cycles.device = "CPU"
    scene.cycles.samples = 20
    scene.render.threads_mode = "FIXED"
    scene.render.threads = 4
    scene.render.resolution_x = 1280
    scene.render.resolution_y = 720
    scene.render.resolution_percentage = 100
    scene.render.filepath = str(PREVIEW)
    scene.render.image_settings.file_format = "PNG"
    bpy.ops.wm.save_as_mainfile(filepath=str(BLEND))
    bpy.ops.file.make_paths_relative()
    bpy.ops.wm.save_as_mainfile(filepath=str(BLEND))
    bpy.ops.render.render(write_still=True)
    REPORT.write_text(json.dumps({
        "status": "Blender K1 marker placement probe only",
        "source": str(SOURCE.relative_to(ROOT)).replace("\\", "/"),
        "kit": str(KIT.relative_to(ROOT)).replace("\\", "/"),
        "contract": str(CONTRACT.relative_to(ROOT)).replace("\\", "/"),
        "instances": entries,
        "limits": "No UE import, zones, HUD, material parameter binding, clickable ring verification or GD-058 acceptance",
    }, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("ART_MARKERS_K1_PROBE_COMPLETE 3")


if __name__ == "__main__":
    main()
