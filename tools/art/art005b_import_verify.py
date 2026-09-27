"""Import the B-atlas Cobble City candidate into an isolated copy of ART-005."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import unreal as u


ROOT = Path(__file__).resolve().parents[2]
VARIANT = ROOT / "blender/ASSET-BOARD-COBBLE-001/variants/B-atlas-v1"
EXPORT = VARIANT / "export/SM_ART005_BoardCobbleAtlasB_v1.fbx"
ATLAS = ROOT / "blender/ASSET-BOARD-COBBLE-001/textures/T_ART005_CobbleBoardAtlas_B_v1.png"
REPORT = VARIANT / "ue-import-report.json"
DEST = "/Game/ArtTests/ART005B"
SOURCE_LEVEL = "/Game/ArtTests/ART005/L_ART005_CobbleSurfaceProbe"
LEVEL = DEST + "/L_ART005_BAtlasProbe"


def import_asset(path: Path, folder: str, name: str, options=None):
    task = u.AssetImportTask()
    task.filename = str(path)
    task.destination_path = folder
    task.destination_name = name
    task.automated = True
    task.replace_existing = True
    task.save = True
    if options is not None:
        task.options = options
    u.AssetToolsHelpers.get_asset_tools().import_asset_tasks([task])
    asset = u.load_asset(folder + "/" + name)
    if not asset:
        raise RuntimeError(f"Import failed: {path}")
    return asset


def make_stone_material(texture):
    name = "M_ART005B_Stone_DiffuseOnly"
    path = DEST + "/Materials/" + name
    material = u.load_asset(path)
    if not material:
        material = u.AssetToolsHelpers.get_asset_tools().create_asset(
            name, DEST + "/Materials", u.Material, u.MaterialFactoryNew()
        )
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
    u.EditorAssetLibrary.save_loaded_asset(material)
    return material


def main():
    manifest = json.loads((VARIANT / "export/export-manifest.json").read_text(encoding="utf-8"))
    for path, key in ((EXPORT, "fbx_sha256"), (ATLAS, "atlas_sha256")):
        actual = hashlib.sha256(path.read_bytes()).hexdigest()
        if actual != manifest[key]:
            raise RuntimeError(f"Source hash changed: {path}")
    if manifest["mesh_parts"] != 35 or manifest["unit_scale_factor_after_patch"] != 1:
        raise RuntimeError("B-atlas FBX export contract changed")

    options = u.FbxImportUI()
    options.import_mesh = True
    options.import_as_skeletal = False
    options.mesh_type_to_import = u.FBXImportType.FBXIT_STATIC_MESH
    options.import_materials = False
    options.import_textures = False
    options.static_mesh_import_data.combine_meshes = True
    options.static_mesh_import_data.auto_generate_collision = False
    mesh = import_asset(EXPORT, DEST + "/Meshes", "SM_ART005_BoardCobbleAtlasB_v1", options)
    bounds = mesh.get_bounding_box()
    dimensions = [bounds.max.x - bounds.min.x, bounds.max.y - bounds.min.y, bounds.max.z - bounds.min.z]
    if any(abs(a - b) > 0.5 for a, b in zip(dimensions, (656, 556, 36))):
        raise RuntimeError(f"B-atlas board dimensions changed: {dimensions}")

    texture = import_asset(ATLAS, DEST + "/Textures", "T_ART005_CobbleBoardAtlas_B_v1")
    if not texture.get_editor_property("srgb"):
        raise RuntimeError("Base-color atlas imported with sRGB disabled")
    materials = {
        "Stone": make_stone_material(texture),
        "Wood": u.load_asset("/Game/ArtTests/ART005/Materials/M_ART005_Wood_Probe"),
        "Undertray": u.load_asset("/Game/ArtTests/ART005/Materials/M_ART005_Undertray_Probe"),
    }
    if any(asset is None for asset in materials.values()):
        raise RuntimeError("Missing original ART-005 wood/undertray materials")
    slots = []
    for index, static_material in enumerate(mesh.get_editor_property("static_materials")):
        slot = str(static_material.get_editor_property("material_slot_name"))
        kind = next((name for name in materials if name in slot), None)
        if kind is None:
            raise RuntimeError(f"Unexpected board slot {index}: {slot}")
        mesh.set_material(index, materials[kind])
        slots.append({"index": index, "slot": slot, "kind": kind})
    if len(slots) != 3 or {entry["kind"] for entry in slots} != set(materials):
        raise RuntimeError(f"Incomplete board material slots: {slots}")
    if mesh.get_num_sections(0) != 3:
        raise RuntimeError(f"Expected three LOD0 material sections, got {mesh.get_num_sections(0)}")
    u.EditorAssetLibrary.save_loaded_asset(mesh)

    if not u.EditorAssetLibrary.does_asset_exist(SOURCE_LEVEL):
        raise RuntimeError(f"Missing reference level: {SOURCE_LEVEL}")
    if not u.EditorAssetLibrary.does_asset_exist(LEVEL):
        if not u.EditorAssetLibrary.duplicate_asset(SOURCE_LEVEL, LEVEL):
            raise RuntimeError(f"Could not duplicate {SOURCE_LEVEL} to {LEVEL}")
    levels = u.get_editor_subsystem(u.LevelEditorSubsystem)
    if not levels.load_level(LEVEL):
        raise RuntimeError(f"Could not load {LEVEL}")
    actors = u.get_editor_subsystem(u.EditorActorSubsystem).get_all_level_actors()
    boards = [actor for actor in actors if actor.get_actor_label() == "ART005 Decorative Board - NoCollision"]
    if len(boards) != 1:
        raise RuntimeError(f"Expected one decorative board actor, got {len(boards)}")
    board = boards[0]
    board.static_mesh_component.set_static_mesh(mesh)
    for slot in slots:
        board.static_mesh_component.set_material(slot["index"], materials[slot["kind"]])
        effective = board.static_mesh_component.get_material(slot["index"])
        if effective != materials[slot["kind"]]:
            raise RuntimeError(f"Incorrect effective material in slot {slot['index']}: {effective}")
    if board.static_mesh_component.get_collision_profile_name() != "NoCollision":
        raise RuntimeError("Decorative board acquired gameplay collision")
    labels = [actor.get_actor_label() for actor in actors]
    hit_count = sum(label.startswith("ART005 HIT ") for label in labels)
    blue_count = sum(label.startswith("ART005 blue section ") for label in labels)
    red_count = sum(label.startswith("ART005 red section ") for label in labels)
    figure_count = sum(label.startswith("ART005 gray ") for label in labels)
    if (hit_count, blue_count, red_count, figure_count) != (30, 15, 15, 6):
        raise RuntimeError(f"Duplicated scene changed: {hit_count}, {blue_count}, {red_count}, {figure_count}")
    if not levels.save_current_level():
        raise RuntimeError(f"Could not save {LEVEL}")
    REPORT.write_text(json.dumps({
        "status": "editor_candidate_import_pass_not_art_acceptance",
        "engine": "Unreal Engine 5.8.2",
        "level": LEVEL,
        "source_level": SOURCE_LEVEL,
        "mesh": DEST + "/Meshes/SM_ART005_BoardCobbleAtlasB_v1",
        "atlas": DEST + "/Textures/T_ART005_CobbleBoardAtlas_B_v1",
        "material": DEST + "/Materials/M_ART005B_Stone_DiffuseOnly",
        "stone_value_scale_provisional": 0.70,
        "bounds_uu": [round(v, 4) for v in dimensions],
        "sections_lod0": mesh.get_num_sections(0),
        "material_slots": slots,
        "hit_surfaces": hit_count,
        "zone_review_marks": {"blue": blue_count, "red": red_count},
        "gray_figures": figure_count,
        "fbx_sha256": manifest["fbx_sha256"],
        "atlas_sha256": manifest["atlas_sha256"],
        "limits": "Stone uses new diffuse with a provisional 0.70 value scale and roughness 0.86; no matching normal/ORM. Old wood and undertray retained. Zones are review actors, not lighting or live boardState. No HUD, accessibility or packaged performance proof.",
    }, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("ART005B_IMPORT_PASS")


main()
