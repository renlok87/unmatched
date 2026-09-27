"""Render six ART-003 gray blockouts on the separate ART-005 B-atlas probe.

This checks material-vs-silhouette competition only. It is not a UE K1 frame,
does not include gameplay zones/HUD, and never overwrites existing evidence.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import bpy


ROOT = Path(__file__).resolve().parents[2]
BOARD = ROOT / "blender/ASSET-BOARD-COBBLE-001/variants/B-atlas-v1"
ATLAS_BLEND = BOARD / "cobble-city-atlas-B-v1.blend"
ART003_BLEND = ROOT / "blender/A01/silhouette_blockouts.blend"
OUT_BLEND = BOARD / "cobble-city-atlas-B-six-blockouts.blend"
PREVIEW = BOARD / "board-six-figures-k1-atlas-B-v1.png"
REPORT = BOARD / "six-blockouts-report.json"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    bpy.ops.wm.open_mainfile(filepath=str(ATLAS_BLEND))
    bpy.context.preferences.filepaths.save_version = 0
    with bpy.data.libraries.load(str(ART003_BLEND), link=False) as (source, dest):
        if "Game_Fighters_Gray" not in source.collections:
            raise RuntimeError("ART-003 fighter collection missing")
        dest.collections = ["Game_Fighters_Gray"]
    fighters = dest.collections[0]
    if fighters is None or len(fighters.objects) != 101:
        raise RuntimeError("Expected the 101-object ART-003 six-fighter blockout collection")
    bpy.context.scene.collection.children.link(fighters)

    # ART-003 renders with Workbench OBJECT color. Cycles otherwise treats the
    # appended parts and label glyphs as white, hiding the marker digits and
    # overstating contrast against stone. Preserve each object's source color.
    mat = bpy.data.materials.new("M_ART003_Blockout_ObjectColor")
    mat.use_nodes = True
    nodes = mat.node_tree.nodes
    info = nodes.new("ShaderNodeObjectInfo")
    shader = nodes.get("Principled BSDF")
    mat.node_tree.links.new(info.outputs["Color"], shader.inputs["Base Color"])
    shader.inputs["Roughness"].default_value = 0.85
    for obj in fighters.objects:
        obj.data.materials.clear()
        obj.data.materials.append(mat)

    # ART-003's gray board tile top is Z=0.035 m. This board's stone surface
    # stays at/below Z=0, so lower the imported instances by exactly 0.035 m.
    for obj in fighters.objects:
        obj.location.z -= 0.035
    groups = {obj.name.split("__", 1)[0] for obj in fighters.objects if "__" in obj.name}
    expected = {"f-0-hero", "f-0-sk0", "f-0-sk1", "f-0-sk2", "f-1-hero", "f-1-sk0"}
    if groups != expected:
        raise RuntimeError(f"Unexpected fighter groups: {groups}")

    scene = bpy.context.scene
    scene.render.engine = "CYCLES"
    scene.cycles.device = "CPU"
    scene.cycles.samples = 16
    scene.render.threads_mode = "FIXED"
    scene.render.threads = 4
    scene.render.resolution_x = 1280
    scene.render.resolution_y = 720
    scene.render.resolution_percentage = 100
    scene.render.image_settings.file_format = "PNG"
    scene.render.filepath = str(PREVIEW)
    bpy.ops.wm.save_as_mainfile(filepath=str(OUT_BLEND))
    bpy.ops.file.make_paths_relative()
    bpy.ops.wm.save_as_mainfile(filepath=str(OUT_BLEND))
    bpy.ops.render.render(write_still=True)

    report = {
        "status": "Blender material-versus-gray-silhouette preview only",
        "atlas_blend": str(ATLAS_BLEND.relative_to(ROOT)).replace("\\", "/"),
        "atlas_blend_sha256": sha256(ATLAS_BLEND),
        "art003_blend": str(ART003_BLEND.relative_to(ROOT)).replace("\\", "/"),
        "art003_blend_sha256": sha256(ART003_BLEND),
        "source_collection": "Game_Fighters_Gray",
        "imported_objects": len(fighters.objects),
        "fighter_groups": sorted(groups),
        "blockout_colors": "source ART-003 object colors through Object Info in Cycles",
        "vertical_adjustment_m": -0.035,
        "render": "Cycles CPU, 4 threads, 16 samples, 1280x720",
        "limitations": "No gameplay zones, HUD, production Medusa, UE import, packaged timing or GD-058 acceptance",
    }
    REPORT.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("ART005_ATLAS_SIX_BLOCKOUTS_COMPLETE 6")


if __name__ == "__main__":
    main()
