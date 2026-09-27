"""Import the ART-005 board surface into an isolated editor scene.

The S04 contract owns gameplay cells and zones. The Blender/FBX mesh is only
decorative; exact hit surfaces and review zone marks are separate actors.
"""

from __future__ import annotations

import json
from pathlib import Path

import unreal as u


ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / "blender/ASSET-BOARD-COBBLE-001"
CONTRACT = ROOT / "docs/game-design/evidence/S04/board-contract.json"
TEXTURES = ROOT / "art/imagegen/mvp-v1/materials/export"
DEST = "/Game/ArtTests/ART005"
LEVEL = DEST + "/L_ART005_CobbleSurfaceProbe"
REPORT = SOURCE / "ue-import-report.json"


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
        raise RuntimeError("Import failed: " + str(path))
    return asset


def make_surface_material(kind: str):
    family = "cobblestone" if kind == "Stone" else "old_wood"
    paths = {}
    for suffix in ("D", "N", "ORM"):
        name = f"T_{family}_{suffix}_1024"
        texture = import_asset(TEXTURES / (name + ".png"), DEST + "/Textures", name)
        if suffix == "N":
            texture.set_editor_property("compression_settings", u.TextureCompressionSettings.TC_NORMALMAP)
            texture.set_editor_property("flip_green_channel", False)
            texture.set_editor_property("srgb", False)
            u.EditorAssetLibrary.save_loaded_asset(texture)
        elif suffix == "ORM":
            texture.set_editor_property("compression_settings", u.TextureCompressionSettings.TC_MASKS)
            texture.set_editor_property("srgb", False)
            u.EditorAssetLibrary.save_loaded_asset(texture)
        paths[suffix] = texture
    name = f"M_ART005_{kind}_Probe"
    material = u.load_asset(DEST + "/Materials/" + name)
    if not material:
        material = u.AssetToolsHelpers.get_asset_tools().create_asset(
            name, DEST + "/Materials", u.Material, u.MaterialFactoryNew()
        )
    mel = u.MaterialEditingLibrary
    mel.delete_all_material_expressions(material)
    for suffix, y in (("D", 0), ("N", 220), ("ORM", 440)):
        sample = mel.create_material_expression(material, u.MaterialExpressionTextureSampleParameter2D, -600, y)
        sample.set_editor_property("parameter_name", f"{suffix}Texture")
        sample.set_editor_property("texture", paths[suffix])
        if suffix == "N":
            sample.set_editor_property("sampler_type", u.MaterialSamplerType.SAMPLERTYPE_NORMAL)
        elif suffix == "ORM":
            sample.set_editor_property("sampler_type", u.MaterialSamplerType.SAMPLERTYPE_MASKS)
        if suffix == "D":
            mel.connect_material_property(sample, "RGB", u.MaterialProperty.MP_BASE_COLOR)
        elif suffix == "N":
            mel.connect_material_property(sample, "RGB", u.MaterialProperty.MP_NORMAL)
        else:
            mel.connect_material_property(sample, "R", u.MaterialProperty.MP_AMBIENT_OCCLUSION)
            mel.connect_material_property(sample, "G", u.MaterialProperty.MP_ROUGHNESS)
            mel.connect_material_property(sample, "B", u.MaterialProperty.MP_METALLIC)
    mel.recompile_material(material)
    u.EditorAssetLibrary.save_loaded_asset(material)
    return material


def constant_material(name: str, color, opacity=None, emissive=False):
    material = u.load_asset(DEST + "/Materials/" + name)
    if not material:
        material = u.AssetToolsHelpers.get_asset_tools().create_asset(
            name, DEST + "/Materials", u.Material, u.MaterialFactoryNew()
        )
    mel = u.MaterialEditingLibrary
    mel.delete_all_material_expressions(material)
    material.set_editor_property("blend_mode", u.BlendMode.BLEND_TRANSLUCENT if opacity is not None else u.BlendMode.BLEND_OPAQUE)
    if emissive:
        material.set_editor_property("shading_model", u.MaterialShadingModel.MSM_UNLIT)
    if opacity is not None:
        material.set_editor_property("blend_mode", u.BlendMode.BLEND_TRANSLUCENT)
        alpha = mel.create_material_expression(material, u.MaterialExpressionConstant, -300, 200)
        alpha.set_editor_property("r", opacity)
        mel.connect_material_property(alpha, "", u.MaterialProperty.MP_OPACITY)
    base = mel.create_material_expression(material, u.MaterialExpressionConstant3Vector, -300, 0)
    base.set_editor_property("constant", u.LinearColor(*color, 1.0))
    mel.connect_material_property(base, "", u.MaterialProperty.MP_EMISSIVE_COLOR if emissive else u.MaterialProperty.MP_BASE_COLOR)
    rough = mel.create_material_expression(material, u.MaterialExpressionConstant, -300, 380)
    rough.set_editor_property("r", 0.86)
    mel.connect_material_property(rough, "", u.MaterialProperty.MP_ROUGHNESS)
    mel.recompile_material(material)
    u.EditorAssetLibrary.save_loaded_asset(material)
    return material


def spawn_mesh(mesh, name: str, position, scale=(1, 1, 1), material=None, yaw=0, collision=None):
    actor = u.EditorLevelLibrary.spawn_actor_from_class(
        u.StaticMeshActor, u.Vector(*position), u.Rotator(0, 0, yaw)
    )
    actor.set_actor_label(name)
    component = actor.static_mesh_component
    component.set_static_mesh(mesh)
    actor.set_actor_scale3d(u.Vector(*scale))
    if material is not None:
        component.set_material(0, material)
    if collision:
        component.set_collision_profile_name(collision)
    return actor


def main():
    contract = json.loads(CONTRACT.read_text(encoding="utf-8"))
    cells = contract["cells"]
    if (contract["width"], contract["height"], len(cells)) != (5, 6, 30):
        raise RuntimeError("S04 runtime contract changed; stop and review board art")
    if {z: sum(z in c["zones"] for c in cells) for z in ("blue", "red")} != {"blue": 15, "red": 15}:
        raise RuntimeError("Unexpected zone counts")
    options = u.FbxImportUI()
    options.import_mesh = True
    options.import_as_skeletal = False
    options.mesh_type_to_import = u.FBXImportType.FBXIT_STATIC_MESH
    options.import_materials = False
    options.import_textures = False
    options.static_mesh_import_data.combine_meshes = True
    options.static_mesh_import_data.import_uniform_scale = 1.0
    board = import_asset(SOURCE / "export/SM_ART005_BoardCobbleProbe.fbx", DEST + "/Meshes", "SM_ART005_BoardCobbleProbe", options)
    bbox = board.get_bounding_box()
    dimensions = [bbox.max.x - bbox.min.x, bbox.max.y - bbox.min.y, bbox.max.z - bbox.min.z]
    if sorted(round(v) for v in dimensions[:2]) != [556, 656]:
        raise RuntimeError(f"Board size differs from Blender 5.56×6.56 m: {dimensions}")
    material_map = {
        "Stone": make_surface_material("Stone"),
        "Wood": make_surface_material("Wood"),
        "Undertray": constant_material("M_ART005_Undertray_Probe", (0.14, 0.16, 0.18)),
    }
    texture_checks = {}
    for family in ("cobblestone", "old_wood"):
        normal = u.load_asset(f"{DEST}/Textures/T_{family}_N_1024")
        orm = u.load_asset(f"{DEST}/Textures/T_{family}_ORM_1024")
        normal_settings = {
            "compression": str(normal.get_editor_property("compression_settings")),
            "srgb": bool(normal.get_editor_property("srgb")),
            "flip_green": bool(normal.get_editor_property("flip_green_channel")),
        }
        orm_settings = {
            "compression": str(orm.get_editor_property("compression_settings")),
            "srgb": bool(orm.get_editor_property("srgb")),
        }
        if "NORMALMAP" not in normal_settings["compression"].upper() or normal_settings["srgb"] or normal_settings["flip_green"]:
            raise RuntimeError(f"Bad {family} DirectX normal import: {normal_settings}")
        if "MASKS" not in orm_settings["compression"].upper() or orm_settings["srgb"]:
            raise RuntimeError(f"Bad {family} ORM import: {orm_settings}")
        texture_checks[family] = {"normal": normal_settings, "orm": orm_settings}
    slots = []
    for index, static_material in enumerate(board.get_editor_property("static_materials")):
        slot = str(static_material.get_editor_property("material_slot_name"))
        if "Stone" in slot:
            kind = "Stone"
        elif "Wood" in slot:
            kind = "Wood"
        elif "Undertray" in slot:
            kind = "Undertray"
        else:
            raise RuntimeError(f"Unknown board material slot: {index} {slot}")
        board.set_material(index, material_map[kind])
        slots.append({"index": index, "slot": slot, "kind": kind})
    if {s["kind"] for s in slots} != set(material_map):
        raise RuntimeError(f"Board slots incomplete: {slots}")
    u.EditorAssetLibrary.save_loaded_asset(board)
    levels = u.get_editor_subsystem(u.LevelEditorSubsystem)
    if u.EditorAssetLibrary.does_asset_exist(LEVEL):
        if not levels.load_level(LEVEL):
            raise RuntimeError("Could not load ART005 test level")
        actors = u.get_editor_subsystem(u.EditorActorSubsystem).get_all_level_actors()
        for actor in actors:
            u.get_editor_subsystem(u.EditorActorSubsystem).destroy_actor(actor)
    elif not levels.new_level(LEVEL):
        raise RuntimeError("Could not create ART005 test level")
    # If importer rotates the extents, yaw is only an export correction, not
    # a new design decision. The three sampled cell centres are checked below.
    board_yaw = 0 if dimensions[0] < dimensions[1] else -90
    board_actor = spawn_mesh(board, "ART005 Decorative Board - NoCollision", (0, 0, 0), yaw=board_yaw, collision="NoCollision")
    if board_actor.static_mesh_component.get_collision_profile_name() != "NoCollision":
        raise RuntimeError("Decorative board retained gameplay collision")
    cube = u.load_asset("/Engine/BasicShapes/Cube.Cube")
    if not cube:
        raise RuntimeError("Engine basic shapes missing")
    blue = constant_material("M_ART005_BlueSection_Review", (0.025, 0.16, 0.70), emissive=True)
    red = constant_material("M_ART005_RedSection_Review", (0.70, 0.06, 0.035), emissive=True)
    glyph = constant_material("M_ART005_ZoneGlyph_Review", (0.72, 0.74, 0.72))
    hit_centers = {}
    for cell in cells:
        x, y = int(cell["x"]), int(cell["y"])
        center = ((x - 2) * 100, (y - 2.5) * 100)
        zone = cell["zones"][0]
        # Hidden exact 100×100 uu click proxies are separate from decorative
        # 98.5×98.5 uu tiles. They are a scene proof, not hooked to gameplay.
        hit = spawn_mesh(cube, f"ART005 HIT {x}:{y}", (center[0], center[1], -0.07), (1, 1, 0.001), collision="BlockAll")
        hit.set_actor_hidden_in_game(True)
        hit.static_mesh_component.set_visibility(False, True)
        hit_centers[f"{x}:{y}"] = [center[0], center[1]]
        marker = spawn_mesh(cube, f"ART005 {zone} section {x}:{y}", (center[0], center[1] + 46.0, 0.28), (0.96, 0.035, 0.004), blue if zone == "blue" else red, collision="NoCollision")
        marker.tags.append("review-only-zone-from-boardState")
        cx, cy = center[0] - 36, center[1] + 36
        if zone == "blue":
            spawn_mesh(cube, f"ART005 blue diamond {x}:{y}", (cx, cy, 0.28), (0.105, 0.105, 0.004), glyph, yaw=45, collision="NoCollision")
        else:
            for offset in (-4, 4):
                spawn_mesh(cube, f"ART005 red double-bar {x}:{y}:{offset}", (cx + offset, cy, 0.28), (0.025, 0.13, 0.004), glyph, collision="NoCollision")
    for key in ("0:0", "4:5", "1:0"):
        x, y = (int(n) for n in key.split(":"))
        expected = [(x - 2) * 100, (y - 2.5) * 100]
        if hit_centers[key] != expected:
            raise RuntimeError(f"Cell origin mismatch {key}")
    figure_map = {
        "f-0-hero": "Medusa", "f-0-sk0": "Harpy", "f-0-sk1": "Harpy",
        "f-0-sk2": "Harpy", "f-1-hero": "Arthur", "f-1-sk0": "Merlin",
    }
    start = next(s for s in contract["starts"] if s["id"] == "medusa-first")
    for fighter in start["fighters"]:
        name = figure_map[fighter["id"]]
        mesh = u.load_asset(f"/Game/ArtTests/ART003/Meshes/SM_ART003_{name}")
        if not mesh:
            raise RuntimeError("ART003 gray figure probe unavailable: " + name)
        pos = fighter["position"]
        yaw = 90 if fighter["id"].startswith("f-0-") else -90
        spawn_mesh(mesh, f"ART005 gray {fighter['id']}", ((pos["x"] - 2) * 100, (pos["y"] - 2.5) * 100, 0), yaw=yaw, collision="NoCollision")
    key = u.EditorLevelLibrary.spawn_actor_from_class(u.DirectionalLight, u.Vector(-350, -150, 600), u.Rotator(0, -55, 30))
    key.set_actor_label("ART005 cool scene key - proposed")
    key.light_component.set_editor_property("intensity", 4.5)
    key.light_component.set_editor_property("mobility", u.ComponentMobility.MOVABLE)
    ambient = u.EditorLevelLibrary.spawn_actor_from_class(u.PointLight, u.Vector(0, -100, 550))
    ambient.set_actor_label("ART005 neutral readability fill - review only")
    ambient.light_component.set_editor_property("intensity", 700.0)
    ambient.light_component.set_editor_property("attenuation_radius", 1800.0)
    ambient.light_component.set_editor_property("cast_shadows", False)
    ambient.light_component.set_editor_property("mobility", u.ComponentMobility.MOVABLE)
    fill = u.EditorLevelLibrary.spawn_actor_from_class(u.PointLight, u.Vector(260, -300, 250))
    fill.set_actor_label("ART005 warm lantern accent - proposed")
    fill.light_component.set_editor_property("intensity", 85.0)
    fill.light_component.set_editor_property("attenuation_radius", 450.0)
    fill.light_component.set_editor_property("cast_shadows", False)
    fill.light_component.set_editor_property("mobility", u.ComponentMobility.MOVABLE)
    camera_location = u.Vector(0, -1032.4, 1474.4)
    camera = u.EditorLevelLibrary.spawn_actor_from_class(
        u.CameraActor, camera_location,
        u.MathLibrary.find_look_at_rotation(camera_location, u.Vector(0, 0, 0)),
    )
    camera.set_actor_label("ART005 K1 review camera - unapproved")
    camera.camera_component.set_editor_property("field_of_view", 35.0)
    levels.save_current_level()
    u.EditorLoadingAndSavingUtils.save_dirty_packages(True, True)
    REPORT.write_text(json.dumps({
        "status": "editor_probe_only",
        "level": LEVEL,
        "board_dimensions_uu": [round(v, 3) for v in dimensions],
        "board_bounds_min_uu": [round(bbox.min.x, 3), round(bbox.min.y, 3), round(bbox.min.z, 3)],
        "board_bounds_max_uu": [round(bbox.max.x, 3), round(bbox.max.y, 3), round(bbox.max.z, 3)],
        "board_yaw_correction_deg": board_yaw,
        "material_slots": slots,
        "texture_import": texture_checks,
        "cell_centers_checked": {k: hit_centers[k] for k in ("0:0", "4:5", "1:0")},
        "hit_proxies": len(hit_centers),
        "zones": {"blue": 15, "red": 15, "source": str(CONTRACT.relative_to(ROOT)).replace("\\", "/")},
        "figures": len(start["fighters"]),
        "note": "Review overlays are scene actors from S04 cells[].zones; no gameplay binding, final art approval, packaged QA or GD-058 pass",
    }, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    u.log("ART005_IMPORT_COMPLETE " + str(REPORT))


if __name__ == "__main__":
    main()
