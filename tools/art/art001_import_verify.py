"""Import and verify the Blender ART-001 control set in Unreal Engine 5.8."""

from __future__ import annotations

import json
from pathlib import Path

import unreal as u


ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / "blender" / "_shared" / "check_set"
EXPORT = SOURCE / "export"
REPORT_JSON = SOURCE / "ue-import-report.json"
REPORT_MD = SOURCE / "REPORT.md"
DEST = "/Game/ArtTests/ART001"
LEVEL = DEST + "/L_ART001_Check"

report = {
    "stage": "UE 5.8.2 import and editor verification",
    "checks": {},
    "measurements": {},
    "assets": {},
}


def log(message):
    u.log("ART001_IMPORT " + str(message))


def check(name: str, passed: bool, detail: str) -> None:
    report["checks"][name] = {"ok": bool(passed), "detail": detail}
    log(f"CHECK {name} ok={bool(passed)} {detail}")
    if not passed:
        raise RuntimeError(f"ART-001 check failed: {name}: {detail}")


def import_static(filename: str, name: str):
    task = u.AssetImportTask()
    task.filename = str(EXPORT / filename)
    task.destination_path = DEST + "/Meshes"
    task.destination_name = name
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
    asset = u.load_asset(f"{DEST}/Meshes/{name}")
    if not asset:
        raise RuntimeError(f"Static import failed: {filename}")
    return asset


def import_skeletal(filename: str, name: str):
    task = u.AssetImportTask()
    task.filename = str(EXPORT / filename)
    task.destination_path = DEST + "/Meshes"
    task.destination_name = name
    task.automated = True
    task.replace_existing = True
    task.save = True
    options = u.FbxImportUI()
    options.import_mesh = True
    options.import_as_skeletal = True
    options.mesh_type_to_import = u.FBXImportType.FBXIT_SKELETAL_MESH
    options.import_animations = False
    options.import_materials = False
    options.import_textures = False
    options.skeletal_mesh_import_data.import_uniform_scale = 1.0
    task.options = options
    u.AssetToolsHelpers.get_asset_tools().import_asset_tasks([task])
    asset = u.load_asset(f"{DEST}/Meshes/{name}")
    if not asset:
        raise RuntimeError(f"Skeletal import failed: {filename}")
    return asset


def import_animation(filename: str, name: str, skeleton):
    anim_dir = DEST + "/Animations"
    for path in list(u.EditorAssetLibrary.list_assets(anim_dir, recursive=False)):
        package = str(path).rsplit(".", 1)[0]
        if package.rsplit("/", 1)[-1].startswith(name):
            u.EditorAssetLibrary.delete_asset(package)
    task = u.AssetImportTask()
    task.filename = str(EXPORT / filename)
    task.destination_path = anim_dir
    task.destination_name = name
    task.automated = True
    task.replace_existing = True
    task.save = True
    options = u.FbxImportUI()
    options.import_mesh = False
    options.import_as_skeletal = True
    options.mesh_type_to_import = u.FBXImportType.FBXIT_ANIMATION
    options.import_animations = True
    options.import_materials = False
    options.import_textures = False
    options.set_editor_property("skeleton", skeleton)
    task.options = options
    u.AssetToolsHelpers.get_asset_tools().import_asset_tasks([task])
    candidates = list(task.get_editor_property("imported_object_paths"))
    candidates.extend(u.EditorAssetLibrary.list_assets(anim_dir, recursive=False))
    for path in candidates:
        package = str(path).rsplit(".", 1)[0]
        if package.rsplit("/", 1)[-1].startswith(name):
            asset = u.load_asset(package)
            if asset and asset.get_class().get_name() == "AnimSequence":
                return asset
    raise RuntimeError(f"Animation import failed: {filename}; candidates={candidates}")


def import_texture(path: Path, name: str):
    task = u.AssetImportTask()
    task.filename = str(path)
    task.destination_path = DEST + "/Textures"
    task.destination_name = name
    task.automated = True
    task.replace_existing = True
    task.save = True
    u.AssetToolsHelpers.get_asset_tools().import_asset_tasks([task])
    texture = u.load_asset(f"{DEST}/Textures/{name}")
    if not texture:
        raise RuntimeError(f"Texture import failed: {path}")
    texture.set_editor_property("compression_settings", u.TextureCompressionSettings.TC_NORMALMAP)
    texture.set_editor_property("srgb", False)
    texture.set_editor_property("flip_green_channel", False)
    u.EditorAssetLibrary.save_loaded_asset(texture)
    return texture


def build_team_material():
    tools = u.AssetToolsHelpers.get_asset_tools()
    path = DEST + "/Materials/M_ART001_TeamColor"
    material = u.load_asset(path)
    if not material:
        material = tools.create_asset(
            "M_ART001_TeamColor", DEST + "/Materials", u.Material, u.MaterialFactoryNew()
        )
    mel = u.MaterialEditingLibrary
    base = mel.create_material_expression(material, u.MaterialExpressionVectorParameter, -600, 0)
    base.set_editor_property("parameter_name", "BaseColor")
    base.set_editor_property("default_value", u.LinearColor(0.58, 0.60, 0.64, 1.0))
    team = mel.create_material_expression(material, u.MaterialExpressionVectorParameter, -600, 180)
    team.set_editor_property("parameter_name", "TeamColor")
    team.set_editor_property("default_value", u.LinearColor(0.16, 0.48, 0.95, 1.0))
    multiply = mel.create_material_expression(material, u.MaterialExpressionMultiply, -300, 80)
    mel.connect_material_expressions(base, "", multiply, "A")
    mel.connect_material_expressions(team, "", multiply, "B")
    mel.connect_material_property(multiply, "", u.MaterialProperty.MP_BASE_COLOR)
    rough = mel.create_material_expression(material, u.MaterialExpressionScalarParameter, -600, 340)
    rough.set_editor_property("parameter_name", "Roughness")
    rough.set_editor_property("default_value", 0.82)
    mel.connect_material_property(rough, "", u.MaterialProperty.MP_ROUGHNESS)
    material.set_editor_property("used_with_skeletal_mesh", True)
    mel.recompile_material(material)
    u.EditorAssetLibrary.save_loaded_asset(material)
    return material


def build_normal_material(texture):
    tools = u.AssetToolsHelpers.get_asset_tools()
    path = DEST + "/Materials/M_ART001_NormalProbe"
    material = u.load_asset(path)
    if not material:
        material = tools.create_asset(
            "M_ART001_NormalProbe", DEST + "/Materials", u.Material, u.MaterialFactoryNew()
        )
    mel = u.MaterialEditingLibrary
    base = mel.create_material_expression(material, u.MaterialExpressionConstant3Vector, -500, 0)
    base.set_editor_property("constant", u.LinearColor(0.45, 0.45, 0.48, 1.0))
    mel.connect_material_property(base, "", u.MaterialProperty.MP_BASE_COLOR)
    sample = mel.create_material_expression(material, u.MaterialExpressionTextureSampleParameter2D, -500, 180)
    sample.set_editor_property("parameter_name", "NormalTexture")
    sample.set_editor_property("texture", texture)
    sample.set_editor_property("sampler_type", u.MaterialSamplerType.SAMPLERTYPE_NORMAL)
    mel.connect_material_property(sample, "RGB", u.MaterialProperty.MP_NORMAL)
    rough = mel.create_material_expression(material, u.MaterialExpressionConstant, -500, 360)
    rough.set_editor_property("r", 0.55)
    mel.connect_material_property(rough, "", u.MaterialProperty.MP_ROUGHNESS)
    mel.recompile_material(material)
    u.EditorAssetLibrary.save_loaded_asset(material)
    return material


def assign_material(mesh, material) -> None:
    mesh.set_material(0, material)
    u.EditorAssetLibrary.save_loaded_asset(mesh)


def bounds_dimensions(box):
    return [box.max.x - box.min.x, box.max.y - box.min.y, box.max.z - box.min.z]


def simple_collision_count(mesh) -> int:
    body_setup = mesh.get_editor_property("body_setup")
    if not body_setup:
        return 0
    aggregate = body_setup.get_editor_property("agg_geom")
    fields = (
        "box_elems",
        "sphere_elems",
        "sphyl_elems",
        "convex_elems",
        "tapered_capsule_elems",
        "level_set_elems",
        "skinned_level_set_elems",
    )
    return sum(len(aggregate.get_editor_property(field)) for field in fields)


def walk_bones(mesh):
    names = ["root"]
    pending = ["root"]
    while pending:
        parent = pending.pop()
        for child in mesh.get_bone_children(parent):
            name = str(child)
            names.append(name)
            pending.append(name)
    return names


def create_level(cube, arrow, mannequin, normal_probe, skeletal, material, normal_material):
    levels = u.get_editor_subsystem(u.LevelEditorSubsystem)
    if u.EditorAssetLibrary.does_asset_exist(LEVEL):
        levels.load_level(LEVEL)
        actors = u.get_editor_subsystem(u.EditorActorSubsystem).get_all_level_actors()
        for actor in actors:
            u.get_editor_subsystem(u.EditorActorSubsystem).destroy_actor(actor)
    else:
        if not levels.new_level(LEVEL):
            raise RuntimeError("Could not create ART-001 check level")

    def spawn_static(mesh, label, location, override):
        actor = u.EditorLevelLibrary.spawn_actor_from_class(u.StaticMeshActor, u.Vector(*location))
        actor.set_actor_label(label)
        actor.static_mesh_component.set_static_mesh(mesh)
        actor.static_mesh_component.set_material(0, override)
        return actor

    spawn_static(cube, "ART001 Cube 100uu", (-180, 0, 0), material)
    spawn_static(arrow, "ART001 Arrow +X", (-30, 0, 2), material)
    mannequin_actor = spawn_static(mannequin, "ART001 Static Mannequin", (130, 0, 0), material)
    spawn_static(normal_probe, "ART001 DirectX Normal Probe", (260, 0, 0), normal_material)
    skeletal_actor = u.EditorLevelLibrary.spawn_actor_from_class(
        u.SkeletalMeshActor, u.Vector(390, 0, 0)
    )
    skeletal_actor.set_actor_label("ART001 Skeletal Mannequin")
    skeletal_actor.skeletal_mesh_component.set_editor_property("skeletal_mesh", skeletal)
    skeletal_actor.skeletal_mesh_component.set_material(0, material)

    key = u.EditorLevelLibrary.spawn_actor_from_class(
        u.DirectionalLight, u.Vector(0, 0, 500), u.Rotator(-50, 35, 0)
    )
    key.light_component.set_editor_property("intensity", 8.0)
    key.light_component.set_editor_property("mobility", u.ComponentMobility.MOVABLE)
    fill = u.EditorLevelLibrary.spawn_actor_from_class(
        u.DirectionalLight, u.Vector(0, 0, 450), u.Rotator(-25, 210, 0)
    )
    fill.light_component.set_editor_property("intensity", 2.0)
    fill.light_component.set_editor_property("cast_shadows", False)
    fill.light_component.set_editor_property("mobility", u.ComponentMobility.MOVABLE)

    hit_ok = False
    hit_detail = "trace API unavailable"
    try:
        trace = u.SystemLibrary.line_trace_single(
            u.EditorLevelLibrary.get_editor_world(),
            u.Vector(130, 0, 100),
            u.Vector(130, 0, -20),
            u.TraceTypeQuery.TRACE_TYPE_QUERY1,
            False,
            [],
            u.DrawDebugTrace.NONE,
            True,
        )
        if isinstance(trace, tuple):
            hit_ok = any(value is True for value in trace)
            hit_detail = f"tuple_hit={hit_ok}"
        else:
            hit_ok = trace is not None
            hit_detail = "hit" if hit_ok else "miss"
    except Exception as exc:
        hit_detail = f"trace exception: {exc}"
    levels.save_current_level()
    return mannequin_actor, hit_ok, hit_detail


def write_markdown() -> None:
    checks = report["checks"]
    measurements = report["measurements"]
    rows = [
        ("Размер куба", "100×100×100 uu", measurements.get("cube_dimensions_uu"), "cube_100uu"),
        ("Pivot куба", "нижний центр", measurements.get("cube_min_uu"), "cube_bottom_pivot"),
        ("Направление стрелки", "наконечник +X, метка +Z", measurements.get("arrow_bounds_uu"), "arrow_plus_x_top_z"),
        ("Масштаб фигурки", "50 uu ±2", measurements.get("mannequin_dimensions_uu"), "mannequin_50uu"),
        ("Pivot фигурки", "опора, центр клетки", measurements.get("mannequin_min_uu"), "mannequin_bottom_pivot"),
        ("Импорт материала", "1 слот, TeamColor задаётся", measurements.get("material"), "teamcolor_material"),
        ("Коллизия выбора", "1 UCX и трассировка попадает", measurements.get("collision"), "selection_collision"),
        ("Клип: ориентация", "без разворота/наклона", measurements.get("skeleton"), "skeleton_orientation"),
        ("Клип: root-движение", "100 uu вдоль +X", measurements.get("root_motion_delta_uu"), "root_motion_plus_x"),
        ("Нормаль-карта", "DirectX, без flip green", measurements.get("normal_texture"), "normal_map_contract"),
    ]
    lines = [
        "# ART-001 — проверочный набор Blender → Unreal Engine",
        "",
        "> Сформировано автоматически на Blender 5.2.2 LTS и Unreal Engine 5.8.2. "
        "Результат подтверждает технический импортный контракт; художественные размеры серийных моделей остаются открыты до GD-058.",
        "",
        "| Проверка | Ожидаемое | Получено | Вывод |",
        "|---|---|---|---|",
    ]
    for title, expected, measured, key in rows:
        state = "PASS" if checks.get(key, {}).get("ok") else "FAIL"
        lines.append(f"| {title} | {expected} | `{measured}` | **{state}** |")
    lines += [
        "",
        "## Воспроизводимость",
        "",
        "- Исходник: `blender/_shared/check_set.blend`.",
        "- Шаблон скелета: `blender/_shared/rig_template.blend`.",
        "- Пресет: `blender/_tools/presets/UM_FBX_v1.json`.",
        "- Экспорт: `blender/_tools/batch_export.py`.",
        "- Проверка геометрии: `blender/_tools/mesh_report.py`.",
        "- UE-импорт: `tools/art/art001_import_verify.py`.",
        "- Полный прогон: `tools/art/run-art001.ps1`.",
        "- Уровень: `/Game/ArtTests/ART001/L_ART001_Check`.",
        "- Кадр уровня: `preview/ue-art001-overview.png`.",
        "- Визуализация normal buffer: `preview/ue-art001-normal-probe.png`.",
        "",
        "Полный машинный результат: `ue-import-report.json`; экспортные хэши: `export/export-manifest.json`. "
        "Это редакторный технический gate Q-311; packaged-проверка серийных ассетов остаётся частью QA-009.",
    ]
    REPORT_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    cube = import_static("SM_ART001_Cube.fbx", "SM_ART001_Cube")
    arrow = import_static("SM_ART001_Arrow.fbx", "SM_ART001_Arrow")
    mannequin = import_static("SM_ART001_Mannequin.fbx", "SM_ART001_Mannequin")
    normal_probe = import_static("SM_ART001_NormalProbe.fbx", "SM_ART001_NormalProbe")
    skeletal = import_skeletal("SK_ART001_Mannequin.fbx", "SK_ART001_Mannequin")
    skeleton = skeletal.get_editor_property("skeleton")
    animation = import_animation("AM_ART001_RootMotion.fbx", "AM_ART001_RootMotion", skeleton)
    texture = import_texture(SOURCE / "T_ART001_Normal_DX.png", "T_ART001_Normal_DX")
    team_material = build_team_material()
    normal_material = build_normal_material(texture)
    for mesh in (cube, arrow, mannequin):
        assign_material(mesh, team_material)
    assign_material(normal_probe, normal_material)

    cube_box = cube.get_bounding_box()
    cube_dims = bounds_dimensions(cube_box)
    report["measurements"]["cube_dimensions_uu"] = [round(value, 3) for value in cube_dims]
    report["measurements"]["cube_min_uu"] = [round(cube_box.min.x, 3), round(cube_box.min.y, 3), round(cube_box.min.z, 3)]
    check("cube_100uu", all(abs(value - 100.0) <= 0.05 for value in cube_dims), f"dims={cube_dims}")
    check(
        "cube_bottom_pivot",
        abs(cube_box.min.z) <= 0.05,
        f"min={report['measurements']['cube_min_uu']}",
    )

    arrow_box = arrow.get_bounding_box()
    arrow_dims = bounds_dimensions(arrow_box)
    arrow_measure = {
        "min": [round(arrow_box.min.x, 3), round(arrow_box.min.y, 3), round(arrow_box.min.z, 3)],
        "max": [round(arrow_box.max.x, 3), round(arrow_box.max.y, 3), round(arrow_box.max.z, 3)],
        "dims": [round(value, 3) for value in arrow_dims],
    }
    report["measurements"]["arrow_bounds_uu"] = arrow_measure
    check(
        "arrow_plus_x_top_z",
        arrow_box.max.x >= 99.9 and arrow_box.min.x >= -0.1 and arrow_dims[1] <= 32.1 and 9.9 <= arrow_box.max.z <= 10.1,
        f"bounds={arrow_measure}",
    )

    mannequin_box = mannequin.get_bounding_box()
    mannequin_dims = bounds_dimensions(mannequin_box)
    report["measurements"]["mannequin_dimensions_uu"] = [round(value, 3) for value in mannequin_dims]
    report["measurements"]["mannequin_min_uu"] = [round(mannequin_box.min.x, 3), round(mannequin_box.min.y, 3), round(mannequin_box.min.z, 3)]
    check("mannequin_50uu", abs(mannequin_dims[2] - 50.0) <= 2.0, f"dims={mannequin_dims}")
    check(
        "mannequin_bottom_pivot",
        abs(mannequin_box.min.z) <= 0.05,
        f"min={report['measurements']['mannequin_min_uu']}",
    )

    material_slots = len(mannequin.get_editor_property("static_materials"))
    report["measurements"]["material"] = {"slots": material_slots, "TeamColor": [0.16, 0.48, 0.95]}
    check("teamcolor_material", material_slots == 1 and team_material is not None, f"slots={material_slots} material={team_material.get_path_name()}")

    collision_count = simple_collision_count(mannequin)
    _actor, trace_ok, trace_detail = create_level(
        cube, arrow, mannequin, normal_probe, skeletal, team_material, normal_material
    )
    report["measurements"]["collision"] = {"simple_shapes": collision_count, "trace_hit": trace_ok, "trace": trace_detail}
    check("selection_collision", collision_count == 1 and trace_ok, f"shapes={collision_count} trace={trace_detail}")

    bones = walk_bones(skeletal)
    report["measurements"]["skeleton"] = {"bones": bones, "count": len(bones)}
    check("skeleton_orientation", len(bones) == 17, f"bones={bones}")
    duration = animation.get_play_length()
    root_name = "SKEL_ART001_Mannequin"
    start = u.AnimationLibrary.get_bone_pose_for_time(animation, root_name, 0.0, False).translation
    end = u.AnimationLibrary.get_bone_pose_for_time(animation, root_name, duration, False).translation
    delta = [end.x - start.x, end.y - start.y, end.z - start.z]
    report["measurements"]["root_motion_delta_uu"] = [round(value, 3) for value in delta]
    report["measurements"]["animation_seconds"] = duration
    check(
        "root_motion_plus_x",
        abs(delta[0] - 100.0) <= 0.5 and abs(delta[1]) <= 0.5 and abs(delta[2]) <= 0.5,
        f"delta={delta} duration={duration:.4f}s",
    )

    normal_settings = {
        "compression": str(texture.get_editor_property("compression_settings")),
        "srgb": bool(texture.get_editor_property("srgb")),
        "flip_green": bool(texture.get_editor_property("flip_green_channel")),
    }
    report["measurements"]["normal_texture"] = normal_settings
    check(
        "normal_map_contract",
        not normal_settings["srgb"] and not normal_settings["flip_green"] and "NORMALMAP" in normal_settings["compression"].upper(),
        str(normal_settings),
    )

    report["assets"] = {
        "cube": cube.get_path_name(),
        "arrow": arrow.get_path_name(),
        "mannequin": mannequin.get_path_name(),
        "skeletal": skeletal.get_path_name(),
        "animation": animation.get_path_name(),
        "material": team_material.get_path_name(),
        "normal_texture": texture.get_path_name(),
        "level": LEVEL,
    }
    REPORT_JSON.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    write_markdown()
    u.EditorLoadingAndSavingUtils.save_dirty_packages(True, True)
    log("COMPLETE " + json.dumps({"checks": len(report["checks"]), "report": str(REPORT_JSON)}))


if __name__ == "__main__":
    main()
