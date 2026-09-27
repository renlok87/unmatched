"""Import static ART-003 blockouts into a separate UE editor scale-check level.

No gameplay character asset or production level is modified. This is an editor
probe; author approval and packaged visual acceptance remain separate gates.
"""

from __future__ import annotations

import json
from pathlib import Path

import unreal as u


ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / "blender" / "A01"
EXPORT = SOURCE / "export"
BOARD_CONTRACT = ROOT / "docs" / "game-design" / "evidence" / "S04" / "board-contract.json"
DEST = "/Game/ArtTests/ART003"
LEVEL = DEST + "/L_ART003_SilhouetteScale"
REPORT = SOURCE / "ue-import-report.json"


def import_mesh(name: str):
    task = u.AssetImportTask()
    task.filename = str(EXPORT / f"SM_ART003_{name}.fbx")
    task.destination_path = DEST + "/Meshes"
    task.destination_name = f"SM_ART003_{name}"
    task.automated = True
    task.replace_existing = True
    task.save = True
    options = u.FbxImportUI()
    options.import_mesh = True
    options.import_as_skeletal = False
    options.mesh_type_to_import = u.FBXImportType.FBXIT_STATIC_MESH
    options.import_materials = False
    options.import_textures = False
    options.static_mesh_import_data.combine_meshes = True
    options.static_mesh_import_data.import_uniform_scale = 1.0
    task.options = options
    u.AssetToolsHelpers.get_asset_tools().import_asset_tasks([task])
    mesh = u.load_asset(f"{DEST}/Meshes/SM_ART003_{name}")
    if not mesh:
        raise RuntimeError(f"FBX import failed for {name}")
    return mesh


def create_gray_material():
    tools = u.AssetToolsHelpers.get_asset_tools()
    path = DEST + "/Materials/M_ART003_GrayProbe"
    material = u.load_asset(path)
    if not material:
        material = tools.create_asset(
            "M_ART003_GrayProbe", DEST + "/Materials", u.Material, u.MaterialFactoryNew()
        )
    mel = u.MaterialEditingLibrary
    base = mel.create_material_expression(material, u.MaterialExpressionConstant3Vector, -400, 0)
    base.set_editor_property("constant", u.LinearColor(0.10, 0.10, 0.10, 1.0))
    mel.connect_material_property(base, "", u.MaterialProperty.MP_BASE_COLOR)
    rough = mel.create_material_expression(material, u.MaterialExpressionConstant, -400, 180)
    rough.set_editor_property("r", 0.82)
    mel.connect_material_property(rough, "", u.MaterialProperty.MP_ROUGHNESS)
    mel.recompile_material(material)
    u.EditorAssetLibrary.save_loaded_asset(material)
    return material


def main() -> None:
    source = json.loads((SOURCE / "build-report.json").read_text(encoding="utf-8"))
    contract = json.loads(BOARD_CONTRACT.read_text(encoding="utf-8"))
    if (contract["width"], contract["height"], len(contract["cells"])) != (5, 6, 30):
        raise RuntimeError("ART003 requires pinned S04 5x6 board contract")
    material = create_gray_material()
    names = {"medusa": "Medusa", "harpy": "Harpy", "arthur": "Arthur", "merlin": "Merlin"}
    meshes = {kind: import_mesh(name) for kind, name in names.items()}
    measurements = {}
    for kind, mesh in meshes.items():
        box = mesh.get_bounding_box()
        dimensions = [box.max.x - box.min.x, box.max.y - box.min.y, box.max.z - box.min.z]
        expected = source["character_bounds"][kind]
        expected_height = 100.0 * (expected["max_m"][2] - expected["min_m"][2])
        if abs(dimensions[2] - expected_height) > 0.5:
            raise RuntimeError(f"{kind} UE height {dimensions[2]:.3f} != Blender {expected_height:.3f}")
        if abs(box.min.z) > 0.5:
            raise RuntimeError(f"{kind} UE base pivot min Z {box.min.z:.3f} != 0")
        if max(dimensions[0], dimensions[1]) >= 100.0:
            raise RuntimeError(f"{kind} footprint exceeds one 100 uu cell: {dimensions}")
        if mesh.get_num_sections(0) < 1:
            raise RuntimeError(f"{kind} has no render sections")
        mesh.set_material(0, material)
        u.EditorAssetLibrary.save_loaded_asset(mesh)
        measurements[kind] = {
            "dimensions_uu": [round(v, 3) for v in dimensions],
            "min_uu": [round(box.min.x, 3), round(box.min.y, 3), round(box.min.z, 3)],
            "max_uu": [round(box.max.x, 3), round(box.max.y, 3), round(box.max.z, 3)],
            "expected_height_uu": round(expected_height, 3),
            "sections_lod0": mesh.get_num_sections(0),
        }
        u.log(f"ART003_IMPORT {kind} dims={dimensions} expected_z={expected_height:.3f}")

    levels = u.get_editor_subsystem(u.LevelEditorSubsystem)
    if u.EditorAssetLibrary.does_asset_exist(LEVEL):
        if not levels.load_level(LEVEL):
            raise RuntimeError(f"Cannot load {LEVEL}")
        actors = u.get_editor_subsystem(u.EditorActorSubsystem).get_all_level_actors()
        for actor in actors:
            u.get_editor_subsystem(u.EditorActorSubsystem).destroy_actor(actor)
    elif not levels.new_level(LEVEL):
        raise RuntimeError(f"Cannot create {LEVEL}")

    cube = u.load_asset("/Engine/BasicShapes/Cube.Cube")
    if not cube:
        raise RuntimeError("Missing engine cube")

    def spawn_cube(label: str, position, scale):
        actor = u.EditorLevelLibrary.spawn_actor_from_class(u.StaticMeshActor, u.Vector(*position))
        actor.set_actor_label(label)
        actor.static_mesh_component.set_static_mesh(cube)
        actor.set_actor_scale3d(u.Vector(*scale))
        return actor

    spawn_cube("ART003 Gray Tray", (0, 0, -12), (5.2, 6.2, 0.18))
    for cell in contract["cells"]:
        x, y = cell["x"], cell["y"]
        spawn_cube(
            f"ART003 Cell {x}:{y}", ((x - 2) * 100, (y - 2.5) * 100, -1.5), (0.97, 0.97, 0.03)
        )

    mapping = {
        "f-0-hero": "medusa",
        "f-0-sk0": "harpy",
        "f-0-sk1": "harpy",
        "f-0-sk2": "harpy",
        "f-1-hero": "arthur",
        "f-1-sk0": "merlin",
    }
    start = next(item for item in contract["starts"] if item["id"] == "medusa-first")
    if {f["id"] for f in start["fighters"]} != set(mapping):
        raise RuntimeError("Unexpected S04 fighter set")
    for fighter in start["fighters"]:
        kind = mapping[fighter["id"]]
        x = (fighter["position"]["x"] - 2) * 100
        y = (fighter["position"]["y"] - 2.5) * 100
        # UM_FBX_v1 exports each figure's front along +X. The near team faces
        # +Y and the far team -Y so opponents face one another on the board.
        yaw = 90 if fighter["id"].startswith("f-0-") else -90
        actor = u.EditorLevelLibrary.spawn_actor_from_class(
            u.StaticMeshActor, u.Vector(x, y, 0), u.Rotator(0, 0, yaw)
        )
        actor.set_actor_label(f"ART003 {fighter['id']} {kind}")
        actor.static_mesh_component.set_static_mesh(meshes[kind])
        actor.static_mesh_component.set_material(0, material)
        if kind == "harpy":
            digit = int(fighter["id"][-1]) + 1
            for index in range(digit):
                dx = (index - (digit - 1) / 2.0) * 4.7
                spawn_cube(f"ART003 {fighter['id']} tally {index+1}", (x + dx, y - 14.5, 10.8), (0.033, 0.03, 0.11))
            label = u.EditorLevelLibrary.spawn_actor_from_class(
                u.TextRenderActor, u.Vector(x, y - 2, 55), u.Rotator(0, 0, -90)
            )
            label.set_actor_label(f"ART003 Harpy {digit} REVIEW LABEL")
            text = label.get_components_by_class(u.TextRenderComponent)[0]
            text.set_editor_property("text", str(digit))
            text.set_editor_property("world_size", 20.0)
            text.set_editor_property("text_render_color", u.Color(12, 12, 12))
            text.set_editor_property("horizontal_alignment", u.HorizTextAligment.EHTA_CENTER)
    key = u.EditorLevelLibrary.spawn_actor_from_class(
        u.DirectionalLight, u.Vector(0, 0, 500), u.Rotator(0, -55, 30)
    )
    key.set_actor_label("ART003 Neutral Key")
    key.light_component.set_editor_property("intensity", 5.0)
    key.light_component.set_editor_property("mobility", u.ComponentMobility.MOVABLE)
    fill = u.EditorLevelLibrary.spawn_actor_from_class(
        u.DirectionalLight, u.Vector(0, 0, 450), u.Rotator(0, -30, 210)
    )
    fill.set_actor_label("ART003 Neutral Fill")
    fill.light_component.set_editor_property("intensity", 1.5)
    fill.light_component.set_editor_property("cast_shadows", False)
    fill.light_component.set_editor_property("mobility", u.ComponentMobility.MOVABLE)
    point = u.EditorLevelLibrary.spawn_actor_from_class(u.PointLight, u.Vector(0, -100, 550))
    point.set_actor_label("ART003 Neutral Capture Fill")
    point.light_component.set_editor_property("intensity", 6000.0)
    point.light_component.set_editor_property("attenuation_radius", 1800.0)
    point.light_component.set_editor_property("cast_shadows", False)
    point.light_component.set_editor_property("mobility", u.ComponentMobility.MOVABLE)
    camera_location = u.Vector(0, -1032.4, 1474.4)
    camera = u.EditorLevelLibrary.spawn_actor_from_class(
        u.CameraActor, camera_location,
        u.MathLibrary.find_look_at_rotation(camera_location, u.Vector(0, 0, 0)),
    )
    camera.set_actor_label("ART003 K1 Probe Camera")
    camera.camera_component.set_editor_property("field_of_view", 35.0)
    levels.save_current_level()
    u.EditorLoadingAndSavingUtils.save_dirty_packages(True, True)
    report = {
        "status": "editor_import_pass",
        "level": LEVEL,
        "source_contract": str(BOARD_CONTRACT.relative_to(ROOT)).replace("\\", "/"),
        "source_blockout": str((SOURCE / "silhouette_blockouts.blend").relative_to(ROOT)).replace("\\", "/"),
        "board": {"width": 5, "height": 6, "cell_uu": 100, "cells": len(contract["cells"])},
        "fighter_instances": [f["id"] for f in start["fighters"]],
        "measurements": measurements,
        "note": "static gray editor probe; no rig, authored material, gameplay integration, packaged QA, or GD-058 acceptance",
    }
    REPORT.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    u.log("ART003_IMPORT_COMPLETE " + str(REPORT))


if __name__ == "__main__":
    main()
