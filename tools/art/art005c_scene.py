"""Compose Medusa, the B-atlas board and neutral markers in isolated UE ArtTests."""

from __future__ import annotations

import json
from pathlib import Path

import unreal as u


ROOT = Path(__file__).resolve().parents[2]
CONTRACT = ROOT / "docs/game-design/evidence/S04/board-contract.json"
REPORT = ROOT / "docs/game-design/evidence/ART-005/combined-scene-report.json"
SOURCE_LEVEL = "/Game/ArtTests/ART004/L_ART004_MedusaAnimationReview"
LEVEL = "/Game/ArtTests/ART005C/L_ART005C_CombinedReview"
BOARD_PATH = "/Game/ArtTests/ART005B/Meshes/SM_ART005_BoardCobbleAtlasB_v1"
MARKER_ROOT = "/Game/ArtTests/ARTMarkers/Meshes/"


def require(path):
    result = u.load_asset(path)
    if not result:
        raise RuntimeError(f"Missing required asset {path}")
    return result


def marker_material(name: str, color):
    path = "/Game/ArtTests/ART005C/Materials"
    material = u.load_asset(path + "/" + name)
    if not material:
        material = u.AssetToolsHelpers.get_asset_tools().create_asset(name, path, u.Material, u.MaterialFactoryNew())
    mel = u.MaterialEditingLibrary
    mel.delete_all_material_expressions(material)
    base = mel.create_material_expression(material, u.MaterialExpressionConstant3Vector, -300, 0)
    base.set_editor_property("constant", u.LinearColor(*color, 1.0))
    mel.connect_material_property(base, "", u.MaterialProperty.MP_BASE_COLOR)
    emissive = mel.create_material_expression(material, u.MaterialExpressionConstant3Vector, -300, 180)
    emissive.set_editor_property("constant", u.LinearColor(*(channel * 0.6 for channel in color), 1.0))
    mel.connect_material_property(emissive, "", u.MaterialProperty.MP_EMISSIVE_COLOR)
    rough = mel.create_material_expression(material, u.MaterialExpressionConstant, -300, 360)
    rough.set_editor_property("r", 0.82)
    mel.connect_material_property(rough, "", u.MaterialProperty.MP_ROUGHNESS)
    mel.recompile_material(material)
    u.EditorAssetLibrary.save_loaded_asset(material)
    return material


def main():
    if not u.EditorAssetLibrary.does_asset_exist(SOURCE_LEVEL):
        raise RuntimeError(f"Missing Medusa review level: {SOURCE_LEVEL}")
    board_mesh = require(BOARD_PATH)
    markers = {name: require(MARKER_ROOT + "SM_Marker_" + name)
               for name in ("SelectionRing", "TargetRing", "Status")}
    if not u.EditorAssetLibrary.does_asset_exist(LEVEL):
        if not u.EditorAssetLibrary.duplicate_asset(SOURCE_LEVEL, LEVEL):
            raise RuntimeError(f"Could not duplicate {SOURCE_LEVEL}")
    levels = u.get_editor_subsystem(u.LevelEditorSubsystem)
    if not levels.load_level(LEVEL):
        raise RuntimeError(f"Could not load {LEVEL}")
    subsystem = u.get_editor_subsystem(u.EditorActorSubsystem)
    actors = subsystem.get_all_level_actors()
    for actor in actors:
        if actor.get_actor_label().startswith("ART005C "):
            subsystem.destroy_actor(actor)
    actors = subsystem.get_all_level_actors()
    boards = [actor for actor in actors if actor.get_actor_label() == "ART005 Decorative Board - NoCollision"]
    medusas = [actor for actor in actors if actor.get_actor_label() == "ART004 Medusa - animation review"]
    if len(boards) != 1 or len(medusas) != 1:
        raise RuntimeError(f"Expected one board and Medusa, got {len(boards)} and {len(medusas)}")
    component = boards[0].static_mesh_component
    component.set_static_mesh(board_mesh)
    for index in range(len(board_mesh.get_editor_property("static_materials"))):
        component.set_material(index, board_mesh.get_material(index))
    if component.get_collision_profile_name() != "NoCollision":
        raise RuntimeError("Decorative board gained gameplay collision")

    contract = json.loads(CONTRACT.read_text(encoding="utf-8"))
    start = next(item for item in contract["starts"] if item["id"] == "medusa-first")
    positions = {fighter["id"]: fighter["position"] for fighter in start["fighters"]}
    materials = {
        "SelectionRing": marker_material("M_ART005C_SelectionGold_Review", (0.90, 0.52, 0.08)),
        "TargetRing": marker_material("M_ART005C_TargetCoral_Review", (0.98, 0.25, 0.10)),
        "Status": marker_material("M_ART005C_StatusIvory_Review", (0.85, 0.92, 0.78)),
    }
    placements = {
        "SelectionRing": "f-0-hero",
        "TargetRing": "f-1-hero",
        "Status": "f-1-sk0",
    }
    marker_results = {}
    for kind, fighter_id in placements.items():
        pos = positions[fighter_id]
        world = u.Vector((pos["x"] - 2) * 100, (pos["y"] - 2.5) * 100, 0)
        if kind == "Status":
            world += u.Vector(25, 0, 45)
        actor = u.EditorLevelLibrary.spawn_actor_from_class(u.StaticMeshActor, world)
        actor.set_actor_label(f"ART005C {kind} {fighter_id} review")
        actor.static_mesh_component.set_static_mesh(markers[kind])
        actor.static_mesh_component.set_material(0, materials[kind])
        actor.static_mesh_component.set_collision_profile_name("NoCollision")
        marker_results[kind] = {"fighter_id": fighter_id, "xyz_uu": [world.x, world.y, world.z]}

    labels = [actor.get_actor_label() for actor in subsystem.get_all_level_actors()]
    counts = {
        "hit_surfaces": sum(label.startswith("ART005 HIT ") for label in labels),
        "blue_zone_review": sum(label.startswith("ART005 blue section ") for label in labels),
        "red_zone_review": sum(label.startswith("ART005 red section ") for label in labels),
        "gray_figures": sum(label.startswith("ART005 gray ") for label in labels),
        "medusa": sum(label == "ART004 Medusa - animation review" for label in labels),
    }
    if counts != {"hit_surfaces": 30, "blue_zone_review": 15, "red_zone_review": 15,
                  "gray_figures": 5, "medusa": 1}:
        raise RuntimeError(f"Combined scene count mismatch: {counts}")
    if not levels.save_current_level():
        raise RuntimeError(f"Could not save {LEVEL}")
    REPORT.write_text(json.dumps({
        "status": "editor_composition_probe_not_gameplay_acceptance",
        "level": LEVEL,
        "source_level": SOURCE_LEVEL,
        "board": BOARD_PATH,
        "medusa": medusas[0].get_actor_label(),
        "markers": marker_results,
        "counts": counts,
        "limits": "Marker colors, emission and elevated status placement are review-only. Zone review marks come from S04 boardState; they are not lighting sections. No live HUD, click binding, animation approval, other maps or packaged FPS.",
    }, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("ART005C_SCENE_PASS")


main()
