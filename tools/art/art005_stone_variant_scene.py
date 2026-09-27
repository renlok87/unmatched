"""Compare candidate Cobble City stone atlases in the existing combined UE scene."""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path

import unreal as u


ROOT = Path(__file__).resolve().parents[2]
VARIANT = os.environ.get("ART005_STONE_VARIANT", "v3")
if VARIANT not in ("v3", "v4"):
    raise RuntimeError(f"Unsupported ART005_STONE_VARIANT: {VARIANT}")
SUFFIX = {"v3": "D", "v4": "E"}[VARIANT]
ATLAS = ROOT / f"blender/ASSET-BOARD-COBBLE-001/textures/T_ART005_CobbleBoardAtlas_B_{VARIANT}_candidate.png"
REPORT = ROOT / f"docs/game-design/evidence/ART-005/stone-{VARIANT}-ue-report.json"
SOURCE_LEVEL = "/Game/ArtTests/ART005C/L_ART005C_CombinedReview"
DEST = f"/Game/ArtTests/ART005{SUFFIX}"
LEVEL = DEST + f"/L_ART005{SUFFIX}_Stone{VARIANT.upper()}Review"
TEXTURE_NAME = f"T_ART005_CobbleBoardAtlas_B_{VARIANT}"
MATERIAL_NAME = f"M_ART005{SUFFIX}_Stone_DiffuseOnly_{VARIANT}"
TEXTURE_PATH = DEST + "/Textures/" + TEXTURE_NAME
MATERIAL_PATH = DEST + "/Materials/" + MATERIAL_NAME
BOARD_PATH = "/Game/ArtTests/ART005B/Meshes/SM_ART005_BoardCobbleAtlasB_v1"


def import_texture():
    task = u.AssetImportTask()
    task.filename = str(ATLAS)
    task.destination_path = DEST + "/Textures"
    task.destination_name = TEXTURE_NAME
    task.automated = True
    task.replace_existing = True
    task.save = True
    u.AssetToolsHelpers.get_asset_tools().import_asset_tasks([task])
    texture = u.load_asset(TEXTURE_PATH)
    if texture is None or not texture.get_editor_property("srgb"):
        raise RuntimeError(f"Stone {VARIANT} texture import failed or sRGB is disabled")
    return texture


def make_material(texture):
    material = u.load_asset(MATERIAL_PATH)
    if material is None:
        material = u.AssetToolsHelpers.get_asset_tools().create_asset(
            MATERIAL_NAME, DEST + "/Materials", u.Material, u.MaterialFactoryNew()
        )
    if material is None:
        raise RuntimeError(f"Stone {VARIANT} material creation failed")
    mel = u.MaterialEditingLibrary
    mel.delete_all_material_expressions(material)
    sample = mel.create_material_expression(material, u.MaterialExpressionTextureSampleParameter2D, -500, 0)
    sample.set_editor_property("parameter_name", "BoardAtlasDiffuse")
    sample.set_editor_property("texture", texture)
    value = mel.create_material_expression(material, u.MaterialExpressionScalarParameter, -500, 250)
    value.set_editor_property("parameter_name", "BoardValueScale_Provisional")
    value.set_editor_property("default_value", 0.70)
    multiply = mel.create_material_expression(material, u.MaterialExpressionMultiply, -200, 0)
    mel.connect_material_expressions(sample, "RGB", multiply, "A")
    mel.connect_material_expressions(value, "", multiply, "B")
    mel.connect_material_property(multiply, "", u.MaterialProperty.MP_BASE_COLOR)
    rough = mel.create_material_expression(material, u.MaterialExpressionConstant, -500, 450)
    rough.set_editor_property("r", 0.86)
    mel.connect_material_property(rough, "", u.MaterialProperty.MP_ROUGHNESS)
    mel.recompile_material(material)
    if not u.EditorAssetLibrary.save_loaded_asset(material):
        raise RuntimeError(f"Could not save stone {VARIANT} material")
    return material


def inspect_level(material, board_mesh):
    actors = u.get_editor_subsystem(u.EditorActorSubsystem).get_all_level_actors()
    labels = [actor.get_actor_label() for actor in actors]
    boards = [actor for actor in actors if actor.get_actor_label() == "ART005 Decorative Board - NoCollision"]
    if len(boards) != 1:
        raise RuntimeError(f"Expected one decorative board, got {len(boards)}")
    board = boards[0]
    component = board.static_mesh_component
    if component.get_editor_property("static_mesh") != board_mesh:
        raise RuntimeError("Board mesh differs from the ART005C reference")
    if component.get_collision_profile_name() != "NoCollision":
        raise RuntimeError("Decorative board gained gameplay collision")
    slots = [str(slot.get_editor_property("material_slot_name"))
             for slot in board_mesh.get_editor_property("static_materials")]
    stone_slots = [index for index, slot in enumerate(slots) if "Stone" in slot]
    if len(slots) != 3 or len(stone_slots) != 1:
        raise RuntimeError(f"Unexpected board material slots: {slots}")
    if component.get_material(stone_slots[0]) != material:
        raise RuntimeError(f"Stone {VARIANT} material override was not saved")
    for index in range(len(slots)):
        if index != stone_slots[0] and component.get_material(index) != board_mesh.get_material(index):
            raise RuntimeError(f"Non-stone board material changed in slot {index}")
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
        raise RuntimeError(f"ART005{SUFFIX} scene changed beyond stone texture: {counts}")
    return stone_slots[0], counts


def main():
    if not ATLAS.is_file() or not u.EditorAssetLibrary.does_asset_exist(SOURCE_LEVEL):
        raise RuntimeError(f"Missing stone {VARIANT} PNG or source level")
    board_mesh = u.load_asset(BOARD_PATH)
    if board_mesh is None:
        raise RuntimeError("Missing reference B-atlas board mesh")
    atlas_sha256 = hashlib.sha256(ATLAS.read_bytes()).hexdigest()
    texture = import_texture()
    material = make_material(texture)
    if not u.EditorAssetLibrary.does_asset_exist(LEVEL):
        if not u.EditorAssetLibrary.duplicate_asset(SOURCE_LEVEL, LEVEL):
            raise RuntimeError(f"Could not duplicate {SOURCE_LEVEL}")
    levels = u.get_editor_subsystem(u.LevelEditorSubsystem)
    if not levels.load_level(LEVEL):
        raise RuntimeError(f"Could not load {LEVEL}")
    board = next((actor for actor in u.get_editor_subsystem(u.EditorActorSubsystem).get_all_level_actors()
                  if actor.get_actor_label() == "ART005 Decorative Board - NoCollision"), None)
    if board is None:
        raise RuntimeError("Decorative board absent from duplicate")
    slots = board_mesh.get_editor_property("static_materials")
    stone_slots = [index for index, slot in enumerate(slots)
                   if "Stone" in str(slot.get_editor_property("material_slot_name"))]
    if len(stone_slots) != 1:
        raise RuntimeError(f"Expected one stone slot, got {stone_slots}")
    board.static_mesh_component.set_material(stone_slots[0], material)
    if not levels.save_current_level() or not levels.load_level(LEVEL):
        raise RuntimeError(f"Could not save and reload stone {VARIANT} review level")
    stone_index, counts = inspect_level(material, board_mesh)
    REPORT.write_text(json.dumps({
        "status": "editor_texture_comparison_only_not_art_acceptance",
        "variant": VARIANT,
        "source_level": SOURCE_LEVEL,
        "level": LEVEL,
        "board_mesh": BOARD_PATH,
        "atlas_source": str(ATLAS),
        "atlas_sha256": atlas_sha256,
        "texture": TEXTURE_PATH,
        "material": MATERIAL_PATH,
        "stone_material_slot": stone_index,
        "provisional_value_scale": 0.70,
        "provisional_roughness": 0.86,
        "counts_after_reload": counts,
        "limits": "Only the stone diffuse changed from ART005C. No matching normal/ORM; old wood and undertray persist. Zone review marks are boardState data, not lighting. Editor comparison only; no HUD, live state, other map lighting or packaged FPS.",
    }, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"ART005_STONE_VARIANT_SCENE_PASS {VARIANT}")


main()
