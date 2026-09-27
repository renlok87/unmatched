"""Place four modular no-collision corner straps in an isolated Cobble review level."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import unreal as u


ROOT = Path(__file__).resolve().parents[2]
VARIANT = ROOT / "blender/ASSET-BOARD-COBBLE-001/variants/corner-bracket-v1"
FBX = VARIANT / "export/SM_ART005_CornerBracket_v1.fbx"
CONTRACT = ROOT / "docs/game-design/evidence/S04/board-contract.json"
REPORT = ROOT / "docs/game-design/evidence/ART-005/corner-bracket-ue-report.json"
SOURCE_LEVEL = "/Game/ArtTests/ART005G/L_ART005G_WoodPaintReview"
DEST = "/Game/ArtTests/ART005H"
LEVEL = DEST + "/L_ART005H_CornerReview"
MESH_PATH = DEST + "/Meshes/SM_ART005_CornerBracket_v1"
MATERIAL_PATH = DEST + "/Materials/M_ART005H_IronCorner_Review"


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
    task.destination_name = "SM_ART005_CornerBracket_v1"
    task.automated = True
    task.replace_existing = True
    task.save = True
    task.options = options
    u.AssetToolsHelpers.get_asset_tools().import_asset_tasks([task])
    mesh = u.load_asset(MESH_PATH)
    if mesh is None:
        raise RuntimeError("Corner FBX import failed")
    return mesh


def make_material():
    material = u.load_asset(MATERIAL_PATH)
    if material is None:
        material = u.AssetToolsHelpers.get_asset_tools().create_asset(
            "M_ART005H_IronCorner_Review", DEST + "/Materials", u.Material, u.MaterialFactoryNew()
        )
    if material is None:
        raise RuntimeError("Corner material creation failed")
    mel = u.MaterialEditingLibrary
    mel.delete_all_material_expressions(material)
    base = mel.create_material_expression(material, u.MaterialExpressionConstant3Vector, -350, 0)
    base.set_editor_property("constant", u.LinearColor(0.032, 0.038, 0.045, 1.0))
    mel.connect_material_property(base, "", u.MaterialProperty.MP_BASE_COLOR)
    metallic = mel.create_material_expression(material, u.MaterialExpressionConstant, -350, 180)
    metallic.set_editor_property("r", 0.25)
    mel.connect_material_property(metallic, "", u.MaterialProperty.MP_METALLIC)
    rough = mel.create_material_expression(material, u.MaterialExpressionConstant, -350, 360)
    rough.set_editor_property("r", 0.86)
    mel.connect_material_property(rough, "", u.MaterialProperty.MP_ROUGHNESS)
    mel.recompile_material(material)
    if not u.EditorAssetLibrary.save_loaded_asset(material):
        raise RuntimeError("Could not save corner material")
    return material


def main():
    build = json.loads((VARIANT / "build-report.json").read_text(encoding="utf-8"))
    contract = json.loads(CONTRACT.read_text(encoding="utf-8"))
    if hashlib.sha256(FBX.read_bytes()).hexdigest() != build["fbx_sha256"]:
        raise RuntimeError("Corner FBX hash changed")
    if (build["parts"], build["material_slots"], build["triangles"], build["rivet_count"]) != (1, 1, 76, 2):
        raise RuntimeError("Corner build contract changed")
    if not all(max(x, y) >= build["minimum_playable_clearance_m"] - 1e-6
               for x, y in build["outline_m_local"]):
        raise RuntimeError("Corner plate intrudes into playable quadrant")
    if (contract["width"], contract["height"], contract["cellSizeUu"]) != (5, 6, 100):
        raise RuntimeError("S04 fixture changed: review board corner placement")
    if not u.EditorAssetLibrary.does_asset_exist(SOURCE_LEVEL):
        raise RuntimeError("Missing painted-wood review level")
    mesh = import_mesh()
    bounds = mesh.get_bounding_box()
    dimensions = [bounds.max.x - bounds.min.x, bounds.max.y - bounds.min.y, bounds.max.z - bounds.min.z]
    if any(abs(value - expected) > 0.5 for value, expected in zip(dimensions, (55, 55, 3.6))):
        raise RuntimeError(f"Corner imported at wrong size: {dimensions}")
    if mesh.get_num_sections(0) != 1 or len(mesh.get_editor_property("static_materials")) != 1:
        raise RuntimeError("Corner import gained sections or material slots")
    material = make_material()
    mesh.set_material(0, material)
    if not u.EditorAssetLibrary.save_loaded_asset(mesh):
        raise RuntimeError("Could not save corner mesh")

    if not u.EditorAssetLibrary.does_asset_exist(LEVEL):
        if not u.EditorAssetLibrary.duplicate_asset(SOURCE_LEVEL, LEVEL):
            raise RuntimeError(f"Could not duplicate {SOURCE_LEVEL}")
    levels = u.get_editor_subsystem(u.LevelEditorSubsystem)
    if not levels.load_level(LEVEL):
        raise RuntimeError(f"Could not load {LEVEL}")
    subsystem = u.get_editor_subsystem(u.EditorActorSubsystem)
    for actor in subsystem.get_all_level_actors():
        if actor.get_actor_label().startswith("ART005H Corner "):
            subsystem.destroy_actor(actor)
    actors = subsystem.get_all_level_actors()
    boards = [actor for actor in actors if actor.get_actor_label() == "ART005 Decorative Board - NoCollision"]
    if len(boards) != 1:
        raise RuntimeError("Expected one decorative board")
    board_yaw = boards[0].get_actor_rotation().yaw
    half_x = contract["width"] * contract["cellSizeUu"] / 2
    half_y = contract["height"] * contract["cellSizeUu"] / 2
    # The FBX preset bakes a +90 degree export-space turn into the mesh.
    # Align the two positive local arms with each corner's outward frame sides;
    # the earlier 0/90/180/270 mapping put a whole arm over a corner cell.
    placements = (
        ("NE", half_x, half_y, 270),
        ("NW", -half_x, half_y, 0),
        ("SW", -half_x, -half_y, 90),
        ("SE", half_x, -half_y, 180),
    )
    placed = []
    for corner, x, y, turn in placements:
        yaw = board_yaw + turn
        actor = u.EditorLevelLibrary.spawn_actor_from_class(
            u.StaticMeshActor, u.Vector(x, y, 0), u.Rotator(0, 0, yaw)
        )
        actor.set_actor_label(f"ART005H Corner {corner} review")
        component = actor.static_mesh_component
        component.set_static_mesh(mesh)
        component.set_material(0, material)
        component.set_collision_profile_name("NoCollision")
        actor.tags.append("review-only-modular-corner")
        placed.append({"corner": corner, "xyz_uu": [x, y, 0], "yaw_degrees": yaw})
    if not levels.save_current_level() or not levels.load_level(LEVEL):
        raise RuntimeError("Could not save/reload corner review level")
    actors = subsystem.get_all_level_actors()
    labels = [actor.get_actor_label() for actor in actors]
    corners = [actor for actor in actors if actor.get_actor_label().startswith("ART005H Corner ")]
    if len(corners) != 4:
        raise RuntimeError(f"Expected four corners after reload, got {len(corners)}")
    expected_actors = {f"ART005H Corner {item['corner']} review": item for item in placed}
    for actor in corners:
        expected_actor = expected_actors.get(actor.get_actor_label())
        if expected_actor is None:
            raise RuntimeError("Unexpected corner actor after reload")
        actual = actor.get_actor_location()
        if any(abs(value - expected) > 0.01 for value, expected in zip(
            (actual.x, actual.y, actual.z), expected_actor["xyz_uu"]
        )):
            raise RuntimeError("Corner actor moved after reload")
        yaw_delta = (actor.get_actor_rotation().yaw - expected_actor["yaw_degrees"] + 180) % 360 - 180
        if abs(yaw_delta) > 0.01:
            raise RuntimeError("Corner actor rotated after reload")
        component = actor.static_mesh_component
        if component.get_editor_property("static_mesh") != mesh or component.get_material(0) != material:
            raise RuntimeError("Corner mesh or material changed after reload")
        if component.get_collision_profile_name() != "NoCollision":
            raise RuntimeError("Corner gained gameplay collision")
    counts = {
        "hit_surfaces": sum(label.startswith("ART005 HIT ") for label in labels),
        "blue_zone_review": sum(label.startswith("ART005 blue section ") for label in labels),
        "red_zone_review": sum(label.startswith("ART005 red section ") for label in labels),
        "gray_figures": sum(label.startswith("ART005 gray ") for label in labels),
        "medusa": sum(label == "ART004 Medusa - animation review" for label in labels),
        "markers": sum(label.startswith("ART005C ") and label.endswith(" review") for label in labels),
        "corners": len(corners),
    }
    expected = {"hit_surfaces": 30, "blue_zone_review": 15, "red_zone_review": 15,
                "gray_figures": 5, "medusa": 1, "markers": 3, "corners": 4}
    if counts != expected:
        raise RuntimeError(f"Corner scene changed gameplay review layers: {counts}")
    REPORT.write_text(json.dumps({
        "status": "editor_corner_composition_only_not_board_acceptance",
        "source_level": SOURCE_LEVEL,
        "level": LEVEL,
        "mesh": MESH_PATH,
        "material": MATERIAL_PATH,
        "fbx_sha256": build["fbx_sha256"],
        "bounds_uu": [round(value, 4) for value in dimensions],
        "board_yaw_degrees": board_yaw,
        "placements": placed,
        "counts_after_reload": counts,
        "limits": "The four no-collision corner straps cover the review board's wood butt joints; no final dimensions, live boardState, HUD, other map lights or packaged performance are accepted.",
    }, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    u.log("ART005H_CORNER_SCENE_PASS")


main()
