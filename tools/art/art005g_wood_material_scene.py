"""Compare a dark painted wood BaseColor on the wood-UV board candidate."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import unreal as u


ROOT = Path(__file__).resolve().parents[2]
WOOD = ROOT / "blender/ASSET-BOARD-COBBLE-001/textures/T_ART005_WoodFrame_B_v1_candidate.png"
REPORT = ROOT / "docs/game-design/evidence/ART-005/wood-painted-ue-report.json"
SOURCE_LEVEL = "/Game/ArtTests/ART005F/L_ART005F_WoodUVReview"
MESH_PATH = "/Game/ArtTests/ART005F/Meshes/SM_ART005_BoardStoneV4_WoodUV"
DEST = "/Game/ArtTests/ART005G"
LEVEL = DEST + "/L_ART005G_WoodPaintReview"
TEXTURE_PATH = DEST + "/Textures/T_ART005_WoodFrame_B_v1"
MATERIAL_PATH = DEST + "/Materials/M_ART005G_Wood_DiffuseOnly"


def import_texture():
    task = u.AssetImportTask()
    task.filename = str(WOOD)
    task.destination_path = DEST + "/Textures"
    task.destination_name = "T_ART005_WoodFrame_B_v1"
    task.automated = True
    task.replace_existing = True
    task.save = True
    u.AssetToolsHelpers.get_asset_tools().import_asset_tasks([task])
    texture = u.load_asset(TEXTURE_PATH)
    if texture is None or not texture.get_editor_property("srgb"):
        raise RuntimeError("Wood BaseColor import failed or sRGB is disabled")
    return texture


def make_material(texture):
    material = u.load_asset(MATERIAL_PATH)
    if material is None:
        material = u.AssetToolsHelpers.get_asset_tools().create_asset(
            "M_ART005G_Wood_DiffuseOnly", DEST + "/Materials", u.Material, u.MaterialFactoryNew()
        )
    if material is None:
        raise RuntimeError("Wood material creation failed")
    mel = u.MaterialEditingLibrary
    mel.delete_all_material_expressions(material)
    sample = mel.create_material_expression(material, u.MaterialExpressionTextureSampleParameter2D, -500, 0)
    sample.set_editor_property("parameter_name", "WoodFrameDiffuse")
    sample.set_editor_property("texture", texture)
    value = mel.create_material_expression(material, u.MaterialExpressionScalarParameter, -500, 250)
    value.set_editor_property("parameter_name", "WoodValueScale_Provisional")
    value.set_editor_property("default_value", 0.70)
    multiply = mel.create_material_expression(material, u.MaterialExpressionMultiply, -200, 0)
    mel.connect_material_expressions(sample, "RGB", multiply, "A")
    mel.connect_material_expressions(value, "", multiply, "B")
    mel.connect_material_property(multiply, "", u.MaterialProperty.MP_BASE_COLOR)
    rough = mel.create_material_expression(material, u.MaterialExpressionConstant, -500, 450)
    rough.set_editor_property("r", 0.85)
    mel.connect_material_property(rough, "", u.MaterialProperty.MP_ROUGHNESS)
    mel.recompile_material(material)
    if not u.EditorAssetLibrary.save_loaded_asset(material):
        raise RuntimeError("Could not save wood material")
    return material


def main():
    if not WOOD.is_file() or not u.EditorAssetLibrary.does_asset_exist(SOURCE_LEVEL):
        raise RuntimeError("Missing wood PNG or wood-UV source scene")
    mesh = u.load_asset(MESH_PATH)
    if mesh is None:
        raise RuntimeError("Missing wood-UV mesh")
    texture = import_texture()
    material = make_material(texture)
    if not u.EditorAssetLibrary.does_asset_exist(LEVEL):
        if not u.EditorAssetLibrary.duplicate_asset(SOURCE_LEVEL, LEVEL):
            raise RuntimeError(f"Could not duplicate {SOURCE_LEVEL}")
    levels = u.get_editor_subsystem(u.LevelEditorSubsystem)
    if not levels.load_level(LEVEL):
        raise RuntimeError(f"Could not load {LEVEL}")
    actors = u.get_editor_subsystem(u.EditorActorSubsystem).get_all_level_actors()
    boards = [actor for actor in actors if actor.get_actor_label() == "ART005 Decorative Board - NoCollision"]
    if len(boards) != 1:
        raise RuntimeError(f"Expected one board, got {len(boards)}")
    component = boards[0].static_mesh_component
    if component.get_editor_property("static_mesh") != mesh:
        raise RuntimeError("Source board mesh changed")
    slots = [str(slot.get_editor_property("material_slot_name"))
             for slot in mesh.get_editor_property("static_materials")]
    wood_slots = [index for index, slot in enumerate(slots) if "Wood" in slot]
    if len(slots) != 3 or len(wood_slots) != 1:
        raise RuntimeError(f"Unexpected material slots: {slots}")
    component.set_material(wood_slots[0], material)
    if not levels.save_current_level() or not levels.load_level(LEVEL):
        raise RuntimeError("Could not save/reload wood-painted scene")
    actors = u.get_editor_subsystem(u.EditorActorSubsystem).get_all_level_actors()
    boards = [actor for actor in actors if actor.get_actor_label() == "ART005 Decorative Board - NoCollision"]
    if len(boards) != 1:
        raise RuntimeError("Board missing after reload")
    component = boards[0].static_mesh_component
    if component.get_editor_property("static_mesh") != mesh or component.get_material(wood_slots[0]) != material:
        raise RuntimeError("Wood material or board mesh changed after reload")
    if component.get_collision_profile_name() != "NoCollision":
        raise RuntimeError("Decorative board gained collision")
    for index in range(len(slots)):
        if index != wood_slots[0] and component.get_material(index) != mesh.get_material(index):
            raise RuntimeError(f"Non-wood material changed in slot {index}")
    labels = [actor.get_actor_label() for actor in actors]
    counts = {
        "hit_surfaces": sum(label.startswith("ART005 HIT ") for label in labels),
        "blue_zone_review": sum(label.startswith("ART005 blue section ") for label in labels),
        "red_zone_review": sum(label.startswith("ART005 red section ") for label in labels),
        "gray_figures": sum(label.startswith("ART005 gray ") for label in labels),
        "medusa": sum(label == "ART004 Medusa - animation review" for label in labels),
        "markers": sum(label.startswith("ART005C ") and label.endswith(" review") for label in labels),
    }
    expected = {"hit_surfaces": 30, "blue_zone_review": 15, "red_zone_review": 15,
                "gray_figures": 5, "medusa": 1, "markers": 3}
    if counts != expected:
        raise RuntimeError(f"Wood material scene changed beyond wood: {counts}")
    REPORT.write_text(json.dumps({
        "status": "editor_wood_material_comparison_only_not_art_acceptance",
        "source_level": SOURCE_LEVEL,
        "level": LEVEL,
        "board_mesh": MESH_PATH,
        "wood_source": str(WOOD),
        "wood_sha256": hashlib.sha256(WOOD.read_bytes()).hexdigest(),
        "texture": TEXTURE_PATH,
        "material": MATERIAL_PATH,
        "wood_material_slot": wood_slots[0],
        "provisional_value_scale": 0.70,
        "provisional_roughness": 0.85,
        "counts_after_reload": counts,
        "limits": "Only wood BaseColor and scalar material differ from ART005F. No matching normal/ORM or approved corner join; no live gameplay/HUD or packaged FPS.",
    }, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("ART005G_WOOD_PAINT_SCENE_PASS")


main()
