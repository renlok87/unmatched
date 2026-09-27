"""Build an isolated Medusa animation review scene from the Cobble City probe."""

import json
from pathlib import Path

import unreal as u


ROOT = Path(__file__).resolve().parents[2]
SOURCE_LEVEL = "/Game/ArtTests/ART005/L_ART005_CobbleSurfaceProbe"
LEVEL = "/Game/ArtTests/ART004/L_ART004_MedusaAnimationReview"
ASSET = "/Game/ART004/Medusa"
REPORT = ROOT / "blender/ASSET-MEDUSA-001/ue-scene-report.json"


def asset(path):
    value = u.load_asset(path)
    if not value:
        raise RuntimeError("Missing required asset " + path)
    return value


def main():
    if not u.EditorAssetLibrary.does_asset_exist(SOURCE_LEVEL):
        raise RuntimeError("Build ART005 Cobble City probe first: " + SOURCE_LEVEL)
    mesh = asset(ASSET + "/Meshes/SK_Medusa_Atlas")
    base = asset(ASSET + "/Meshes/SM_Medusa_Base")
    blue = asset(ASSET + "/Materials/MI_Medusa_Blue")
    clips = {name: asset(ASSET + "/Animation/AM_Medusa_" + name + "_Anim")
             for name in ("Idle", "LungeAttack", "HitReact", "DeathSettle")}
    skeleton = mesh.get_editor_property("skeleton")
    for name, clip in clips.items():
        if clip.get_editor_property("skeleton") != skeleton:
            raise RuntimeError("Clip is on a different skeleton: " + name)

    if not u.EditorAssetLibrary.does_asset_exist(LEVEL):
        copy = u.EditorAssetLibrary.duplicate_asset(SOURCE_LEVEL, LEVEL)
        if not copy:
            raise RuntimeError("Could not duplicate ART005 into isolated ART004 level")
    levels = u.get_editor_subsystem(u.LevelEditorSubsystem)
    if not levels.load_level(LEVEL):
        raise RuntimeError("Could not load " + LEVEL)
    subsystem = u.get_editor_subsystem(u.EditorActorSubsystem)
    old_hero = None
    for actor in subsystem.get_all_level_actors():
        label = actor.get_actor_label()
        if label == "ART005 gray f-0-hero":
            old_hero = actor
        elif label.startswith("ART004 Medusa"):
            subsystem.destroy_actor(actor)
    if old_hero:
        location = old_hero.get_actor_location()
        subsystem.destroy_actor(old_hero)
    else:
        contract = json.loads((ROOT / "docs/game-design/evidence/S04/board-contract.json").read_text())
        start = next(item for item in contract["starts"] if item["id"] == "medusa-first")
        hero = next(item for item in start["fighters"] if item["id"] == "f-0-hero")
        position = hero["position"]
        location = u.Vector((position["x"] - 2) * 100, (position["y"] - 2.5) * 100, 0)
    # ART005 gray static probe faces +X; this skeletal FBX faces +Y in UE.
    # The south-side Medusa must face north toward the opposing team.
    rotation = u.Rotator(0, 0, 0)

    figure = u.EditorLevelLibrary.spawn_actor_from_class(u.SkeletalMeshActor, location, rotation)
    figure.set_actor_label("ART004 Medusa - animation review")
    component = figure.skeletal_mesh_component
    component.set_editor_property("skeletal_mesh", mesh)
    component.set_material(0, blue)
    component.set_editor_property("animation_mode", u.AnimationMode.ANIMATION_SINGLE_NODE)
    component.play_animation(clips["Idle"], True)
    figure.set_editor_property("tags", ["art004_medusa_review", "f-0-hero"])

    pedestal = u.EditorLevelLibrary.spawn_actor_from_class(u.StaticMeshActor, location, rotation)
    pedestal.set_actor_label("ART004 Medusa - static base")
    pedestal.static_mesh_component.set_static_mesh(base)
    pedestal.static_mesh_component.set_material(0, blue)
    pedestal.static_mesh_component.set_collision_profile_name("BlockAll")

    levels.save_current_level()
    u.EditorLoadingAndSavingUtils.save_dirty_packages(True, True)
    REPORT.write_text(json.dumps({
        "source_level": SOURCE_LEVEL,
        "level": LEVEL,
        "figure": figure.get_actor_label(),
        "location_uu": [round(location.x, 3), round(location.y, 3), round(location.z, 3)],
        "yaw_deg": round(rotation.yaw, 3),
        "skeletal_mesh": mesh.get_path_name(),
        "static_base": base.get_path_name(),
        "material": blue.get_path_name(),
        "clips": {name: clip.get_path_name() for name, clip in clips.items()},
        "note": "Isolated editor review copy of ART005; not gameplay replacement or accepted K1/K2/K3",
    }, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    u.log("ART004_SCENE_COMPLETE " + str(REPORT))


main()
