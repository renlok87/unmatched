"""Import a wood-grain UV board variant into a copy of the v4 combined scene."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import unreal as u


ROOT = Path(__file__).resolve().parents[2]
VARIANT = ROOT / "blender/ASSET-BOARD-COBBLE-001/variants/B-atlas-v4-woodUV"
FBX = VARIANT / "export/SM_ART005_BoardStoneV4_WoodUV.fbx"
REPORT = ROOT / "docs/game-design/evidence/ART-005/wood-uv-ue-report.json"
SOURCE_LEVEL = "/Game/ArtTests/ART005E/L_ART005E_StoneV4Review"
SOURCE_MESH = "/Game/ArtTests/ART005B/Meshes/SM_ART005_BoardCobbleAtlasB_v1"
DEST = "/Game/ArtTests/ART005F"
LEVEL = DEST + "/L_ART005F_WoodUVReview"
MESH_PATH = DEST + "/Meshes/SM_ART005_BoardStoneV4_WoodUV"


def import_mesh():
    options = u.FbxImportUI()
    options.import_mesh = True
    options.import_as_skeletal = False
    options.mesh_type_to_import = u.FBXImportType.FBXIT_STATIC_MESH
    options.import_materials = False
    options.import_textures = False
    options.static_mesh_import_data.combine_meshes = True
    options.static_mesh_import_data.auto_generate_collision = False
    task = u.AssetImportTask()
    task.filename = str(FBX)
    task.destination_path = DEST + "/Meshes"
    task.destination_name = "SM_ART005_BoardStoneV4_WoodUV"
    task.automated = True
    task.replace_existing = True
    task.save = True
    task.options = options
    u.AssetToolsHelpers.get_asset_tools().import_asset_tasks([task])
    mesh = u.load_asset(MESH_PATH)
    if mesh is None:
        raise RuntimeError("ART005F board FBX import failed")
    return mesh


def main():
    build = json.loads((VARIANT / "build-report.json").read_text(encoding="utf-8"))
    if hashlib.sha256(FBX.read_bytes()).hexdigest() != build["fbx_sha256"]:
        raise RuntimeError("ART005F FBX source hash changed")
    if build["mesh_parts"] != 35 or build["unit_scale_factor_after_patch"] != 1:
        raise RuntimeError("ART005F FBX contract changed")
    if not u.EditorAssetLibrary.does_asset_exist(SOURCE_LEVEL):
        raise RuntimeError("Missing v4 source scene")
    source_mesh = u.load_asset(SOURCE_MESH)
    if source_mesh is None:
        raise RuntimeError("Missing original B-atlas mesh")
    mesh = import_mesh()
    bounds = mesh.get_bounding_box()
    dimensions = [bounds.max.x - bounds.min.x, bounds.max.y - bounds.min.y, bounds.max.z - bounds.min.z]
    if any(abs(value - expected) > 0.5 for value, expected in zip(dimensions, (656, 556, 36))):
        raise RuntimeError(f"Board dimensions changed: {dimensions}")
    if mesh.get_num_sections(0) != 3:
        raise RuntimeError(f"Expected three LOD0 sections, got {mesh.get_num_sections(0)}")
    source_slots = [str(slot.get_editor_property("material_slot_name"))
                    for slot in source_mesh.get_editor_property("static_materials")]
    slots = [str(slot.get_editor_property("material_slot_name"))
             for slot in mesh.get_editor_property("static_materials")]
    if slots != source_slots or len(slots) != 3:
        raise RuntimeError(f"Material slots changed: {source_slots} -> {slots}")
    materials = {
        "Stone": u.load_asset("/Game/ArtTests/ART005E/Materials/M_ART005E_Stone_DiffuseOnly_v4"),
        "Wood": u.load_asset("/Game/ArtTests/ART005/Materials/M_ART005_Wood_Probe"),
        "Undertray": u.load_asset("/Game/ArtTests/ART005/Materials/M_ART005_Undertray_Probe"),
    }
    if any(material is None for material in materials.values()):
        raise RuntimeError("Missing source board material")
    slot_info = []
    for index, slot in enumerate(slots):
        kind = next((kind for kind in materials if kind in slot), None)
        if kind is None:
            raise RuntimeError(f"Unknown board slot: {slot}")
        mesh.set_material(index, materials[kind])
        slot_info.append({"index": index, "slot": slot, "kind": kind})
    u.EditorAssetLibrary.save_loaded_asset(mesh)
    if not u.EditorAssetLibrary.does_asset_exist(LEVEL):
        if not u.EditorAssetLibrary.duplicate_asset(SOURCE_LEVEL, LEVEL):
            raise RuntimeError(f"Could not duplicate {SOURCE_LEVEL}")
    levels = u.get_editor_subsystem(u.LevelEditorSubsystem)
    if not levels.load_level(LEVEL):
        raise RuntimeError(f"Could not load {LEVEL}")
    actors = u.get_editor_subsystem(u.EditorActorSubsystem).get_all_level_actors()
    boards = [actor for actor in actors if actor.get_actor_label() == "ART005 Decorative Board - NoCollision"]
    if len(boards) != 1:
        raise RuntimeError(f"Expected one decorative board, got {len(boards)}")
    component = boards[0].static_mesh_component
    component.set_static_mesh(mesh)
    for item in slot_info:
        component.set_material(item["index"], materials[item["kind"]])
    if component.get_collision_profile_name() != "NoCollision":
        raise RuntimeError("Decorative board gained gameplay collision")
    if not levels.save_current_level() or not levels.load_level(LEVEL):
        raise RuntimeError("Could not save/reload ART005F scene")
    actors = u.get_editor_subsystem(u.EditorActorSubsystem).get_all_level_actors()
    boards = [actor for actor in actors if actor.get_actor_label() == "ART005 Decorative Board - NoCollision"]
    if len(boards) != 1 or boards[0].static_mesh_component.get_editor_property("static_mesh") != mesh:
        raise RuntimeError("ART005F board mesh did not survive reload")
    component = boards[0].static_mesh_component
    if component.get_collision_profile_name() != "NoCollision":
        raise RuntimeError("Decorative board collision changed after reload")
    for item in slot_info:
        if component.get_material(item["index"]) != materials[item["kind"]]:
            raise RuntimeError(f"Material slot {item['index']} changed after reload")
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
        raise RuntimeError(f"ART005F scene composition changed: {counts}")
    REPORT.write_text(json.dumps({
        "status": "editor_wood_uv_comparison_only_not_art_acceptance",
        "source_level": SOURCE_LEVEL,
        "level": LEVEL,
        "source_fbx": str(FBX),
        "fbx_sha256": build["fbx_sha256"],
        "mesh": MESH_PATH,
        "bounds_uu": [round(value, 4) for value in dimensions],
        "sections_lod0": mesh.get_num_sections(0),
        "material_slots": slot_info,
        "counts_after_reload": counts,
        "limits": "Only the decorative board mesh/wood UV changed from ART005E. The old wood texture and all other materials, actors, camera and gameplay review layers persist. Editor probe only; inspect corner joins visually.",
    }, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("ART005F_WOOD_UV_SCENE_PASS")


main()
