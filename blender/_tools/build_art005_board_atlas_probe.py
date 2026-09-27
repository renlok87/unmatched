"""Build a separate, CPU-rendered whole-board UV atlas probe for ART-005.

The original cobble-city-probe.blend and its UE evidence are never overwritten.
This candidate changes only the stone diffuse image and UV0 on the 30 decorative
tiles. Gameplay hit surfaces and zones remain outside the decorative mesh.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import bpy


ROOT = Path(__file__).resolve().parents[2]
BOARD = ROOT / "blender/ASSET-BOARD-COBBLE-001"
SOURCE = BOARD / "cobble-city-probe.blend"
ATLAS = BOARD / "textures/T_ART005_CobbleBoardAtlas_B_v1.png"
OUT = BOARD / "variants/B-atlas-v1"
BLEND = OUT / "cobble-city-atlas-B-v1.blend"
PREVIEW = OUT / "board-surface-k1-atlas-B-v1.png"
REPORT = OUT / "build-report.json"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    if not SOURCE.is_file() or not ATLAS.is_file():
        raise FileNotFoundError("Missing original board probe or generated atlas")
    OUT.mkdir(parents=True, exist_ok=True)
    bpy.ops.wm.open_mainfile(filepath=str(SOURCE))
    bpy.context.preferences.filepaths.save_version = 0

    collection = bpy.data.collections["L2_Decorative_Stone_NoCollision"]
    tiles = sorted(collection.objects, key=lambda obj: obj.name)
    if len(tiles) != 30:
        raise RuntimeError(f"Expected 30 decorative tiles, got {len(tiles)}")

    # World board bounds are X=-2.5..2.5 m and Y=-3..3 m. Every cell maps
    # to its own rectangle of the SAME image: no 1/4-image quadrant reuse.
    uv_bounds = {}
    for obj in tiles:
        if obj.type != "MESH" or obj.get("art_layer") != "board_surface":
            raise RuntimeError(f"Unexpected tile: {obj.name}")
        uv = obj.data.uv_layers.get("UV0")
        if uv is None:
            raise RuntimeError(f"Missing UV0: {obj.name}")
        pairs = []
        for loop in obj.data.loops:
            world = obj.matrix_world @ obj.data.vertices[loop.vertex_index].co
            pair = ((world.x + 2.5) / 5.0, (world.y + 3.0) / 6.0)
            if not (0.0 <= pair[0] <= 1.0 and 0.0 <= pair[1] <= 1.0):
                raise RuntimeError(f"Atlas UV outside 0..1: {obj.name}, {pair}")
            uv.data[loop.index].uv = pair
            pairs.append(pair)
        uv_bounds[obj.name] = [
            round(min(p[0] for p in pairs), 6),
            round(min(p[1] for p in pairs), 6),
            round(max(p[0] for p in pairs), 6),
            round(max(p[1] for p in pairs), 6),
        ]
    if len({tuple(bounds) for bounds in uv_bounds.values()}) != 30:
        raise RuntimeError("UV rectangles are not unique per cell")

    mat = bpy.data.materials["M_ART005_Stone_Provisional"]
    tex_nodes = [node for node in mat.node_tree.nodes if node.type == "TEX_IMAGE"]
    if len(tex_nodes) != 1:
        raise RuntimeError(f"Expected one stone diffuse node, got {len(tex_nodes)}")
    image = bpy.data.images.load(str(ATLAS), check_existing=False)
    image.colorspace_settings.name = "sRGB"
    tex_nodes[0].image = image
    mat.name = "M_ART005_Stone_AtlasB_Provisional"

    scene = bpy.context.scene
    scene.render.engine = "CYCLES"
    scene.cycles.device = "CPU"
    scene.cycles.samples = 12
    scene.render.threads_mode = "FIXED"
    scene.render.threads = 4
    scene.render.resolution_x = 960
    scene.render.resolution_y = 540
    scene.render.resolution_percentage = 100
    scene.render.image_settings.file_format = "PNG"
    scene.render.filepath = str(PREVIEW)
    bpy.ops.wm.save_as_mainfile(filepath=str(BLEND))
    bpy.ops.file.make_paths_relative()
    bpy.ops.wm.save_as_mainfile(filepath=str(BLEND))
    bpy.ops.render.render(write_still=True)

    report = {
        "status": "art005_atlas_B_visual_probe_only",
        "source_blend": str(SOURCE.relative_to(ROOT)).replace("\\", "/"),
        "source_sha256": sha256(SOURCE),
        "atlas": str(ATLAS.relative_to(ROOT)).replace("\\", "/"),
        "atlas_sha256": sha256(ATLAS),
        "atlas_size_px": list(image.size),
        "tile_count": len(tiles),
        "unique_uv_rectangles": len({tuple(bounds) for bounds in uv_bounds.values()}),
        "uv_bounds": uv_bounds,
        "renderer": "Cycles CPU, 4 threads, 12 samples, 960x540; not an UE FPS test",
        "approval": "candidate only; no matching N/ORM, no UE import or GD-058 acceptance",
    }
    REPORT.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("ART005_ATLAS_B_PROBE_COMPLETE 30")


if __name__ == "__main__":
    main()
