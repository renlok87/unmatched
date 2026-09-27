"""Save a Blender source for the painted-wood material on the corrected-UV board."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import bpy


ROOT = Path(__file__).resolve().parents[2]
BOARD = ROOT / "blender/ASSET-BOARD-COBBLE-001"
SOURCE = BOARD / "variants/B-atlas-v4-woodUV/cobble-city-stone-v4-wood-uv.blend"
SOURCE_REPORT = BOARD / "variants/B-atlas-v4-woodUV/build-report.json"
WOOD = BOARD / "textures/T_ART005_WoodFrame_B_v1_candidate.png"
OUT = BOARD / "variants/B-atlas-v4-woodPaint"
BLEND = OUT / "cobble-city-stone-v4-wood-paint.blend"
REPORT = OUT / "build-report.json"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    source_report = json.loads(SOURCE_REPORT.read_text(encoding="utf-8"))
    if sha256(SOURCE) != source_report["blend_sha256"] or not WOOD.is_file():
        raise RuntimeError("Wood-UV blend changed or new wood BaseColor is missing")
    OUT.mkdir(parents=True, exist_ok=True)
    bpy.ops.wm.open_mainfile(filepath=str(SOURCE))
    bpy.context.preferences.filepaths.save_version = 0
    material = bpy.data.materials["M_ART005_Wood_Provisional"]
    nodes = [node for node in material.node_tree.nodes if node.type == "TEX_IMAGE"]
    if len(nodes) != 1:
        raise RuntimeError(f"Expected one wood texture node, got {len(nodes)}")
    image = bpy.data.images.load(str(WOOD), check_existing=False)
    image.colorspace_settings.name = "sRGB"
    nodes[0].image = image
    frame = bpy.data.collections["L2_Wood_Frame_NoCollision"]
    if len(frame.objects) != 4:
        raise RuntimeError(f"Expected four rails, got {len(frame.objects)}")
    bpy.ops.wm.save_as_mainfile(filepath=str(BLEND))
    bpy.ops.file.make_paths_relative()
    bpy.ops.wm.save_as_mainfile(filepath=str(BLEND))
    REPORT.write_text(json.dumps({
        "status": "blender_painted_wood_candidate_not_art_acceptance",
        "source_blend": str(SOURCE.relative_to(ROOT)).replace("\\", "/"),
        "source_blend_sha256": source_report["blend_sha256"],
        "blend": str(BLEND.relative_to(ROOT)).replace("\\", "/"),
        "blend_sha256": sha256(BLEND),
        "wood_basecolor": str(WOOD.relative_to(ROOT)).replace("\\", "/"),
        "wood_sha256": sha256(WOOD),
        "fbx": source_report["fbx"],
        "fbx_sha256": source_report["fbx_sha256"],
        "note": "Geometry and UV are the woodUV variant; Unreal ART005G uses that FBX with this wood BaseColor and a provisional value scale of 0.70.",
    }, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("ART005_WOOD_PAINT_BLEND_PASS")


if __name__ == "__main__":
    main()
