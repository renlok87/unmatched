"""Compare one fixed Cobble art fixture under two reference-inspired light conditions.

These are material/readability stress rigs, not recreations of either game map or
their boardState zones. The original ART005H review level remains untouched.
"""

from __future__ import annotations

import json
from pathlib import Path

import unreal as u


ROOT = Path(__file__).resolve().parents[2]
SOURCE = "/Game/ArtTests/ART005H/L_ART005H_CornerReview"
DEST = "/Game/ArtTests/ART005I"
REPORT = ROOT / "docs/game-design/evidence/ART-005/lighting-stress-ue-report.json"
PROFILES = {
    "forest": {
        "level": DEST + "/L_ART005I_ForestReferenceLight",
        "reference": "Sherwood Forest: foliage-filtered cool green with restrained warm patches; only a color-condition reference",
        "key": {"intensity": 4.0, "color_linear": [0.73, 0.82, 0.74]},
        "ambient": {"intensity": 950.0, "color_linear": [0.88, 0.94, 0.88]},
        "warm": {"intensity": 150.0, "color_linear": [1.0, 0.62, 0.32], "radius_uu": 430.0},
        "secondary": {"position_uu": [-180, 125, 230], "intensity": 110.0,
                      "color_linear": [1.0, 0.67, 0.35], "radius_uu": 330.0},
    },
    "paddock": {
        "level": DEST + "/L_ART005I_PaddockReferenceLight",
        "reference": "T. Rex Paddock: blue-indigo nocturnal color with restrained cyan rim and one warm practical; not map geometry",
        "key": {"intensity": 3.5, "color_linear": [0.62, 0.69, 0.88]},
        "ambient": {"intensity": 1150.0, "color_linear": [0.84, 0.88, 0.96]},
        "warm": {"intensity": 130.0, "color_linear": [1.0, 0.59, 0.30], "radius_uu": 430.0},
        "secondary": {"position_uu": [-210, 110, 250], "intensity": 85.0,
                      "color_linear": [0.55, 0.80, 1.0], "radius_uu": 420.0},
    },
}


def apply_light(component, spec: dict):
    color = spec["color_linear"]
    component.set_light_color(u.LinearColor(*color, 1.0), False)
    component.set_editor_property("intensity", spec["intensity"])
    component.set_editor_property("mobility", u.ComponentMobility.MOVABLE)
    if "radius_uu" in spec:
        component.set_editor_property("attenuation_radius", spec["radius_uu"])
        component.set_editor_property("cast_shadows", False)


def actor_by_label(actors: list, label: str):
    found = [actor for actor in actors if actor.get_actor_label() == label]
    if len(found) != 1:
        raise RuntimeError(f"Expected one light actor {label}, found {len(found)}")
    return found[0]


def run_profile(name: str, spec: dict):
    level = spec["level"]
    if not u.EditorAssetLibrary.does_asset_exist(level):
        if not u.EditorAssetLibrary.duplicate_asset(SOURCE, level):
            raise RuntimeError("Could not duplicate corner scene into " + level)
    levels = u.get_editor_subsystem(u.LevelEditorSubsystem)
    if not levels.load_level(level):
        raise RuntimeError("Could not load " + level)
    subsystem = u.get_editor_subsystem(u.EditorActorSubsystem)
    actors = subsystem.get_all_level_actors()
    for actor in actors:
        if actor.get_actor_label().startswith("ART005I extra light "):
            subsystem.destroy_actor(actor)
    actors = subsystem.get_all_level_actors()
    key = actor_by_label(actors, "ART005 cool scene key - proposed")
    ambient = actor_by_label(actors, "ART005 neutral readability fill - review only")
    warm = actor_by_label(actors, "ART005 warm lantern accent - proposed")
    apply_light(key.light_component, spec["key"])
    apply_light(ambient.light_component, spec["ambient"])
    apply_light(warm.light_component, spec["warm"])
    extra = u.EditorLevelLibrary.spawn_actor_from_class(
        u.PointLight, u.Vector(*spec["secondary"]["position_uu"])
    )
    extra.set_actor_label("ART005I extra light " + name)
    apply_light(extra.light_component, spec["secondary"])
    if not levels.save_current_level() or not levels.load_level(level):
        raise RuntimeError("Could not save/reload " + level)
    reloaded = subsystem.get_all_level_actors()
    labels = [actor.get_actor_label() for actor in reloaded]
    actual_lights = {}
    for role, label in (("key", "ART005 cool scene key - proposed"),
                        ("ambient", "ART005 neutral readability fill - review only"),
                        ("warm", "ART005 warm lantern accent - proposed"),
                        ("secondary", "ART005I extra light " + name)):
        component = actor_by_label(reloaded, label).light_component
        intensity = component.get_editor_property("intensity")
        if abs(intensity - spec[role]["intensity"]) > 0.01:
            raise RuntimeError(f"{name} {role} intensity changed on reload: {intensity}")
        actual_lights[role] = {"intensity": round(intensity, 4)}
    counts = {
        "hit_surfaces": sum(label.startswith("ART005 HIT ") for label in labels),
        "blue_zone_review": sum(label.startswith("ART005 blue section ") for label in labels),
        "red_zone_review": sum(label.startswith("ART005 red section ") for label in labels),
        "gray_figures": sum(label.startswith("ART005 gray ") for label in labels),
        "medusa": sum(label == "ART004 Medusa - animation review" for label in labels),
        "markers": sum(label.startswith("ART005C ") and label.endswith(" review") for label in labels),
        "corners": sum(label.startswith("ART005H Corner ") for label in labels),
        "extra_lights": sum(label.startswith("ART005I extra light ") for label in labels),
    }
    expected = {"hit_surfaces": 30, "blue_zone_review": 15, "red_zone_review": 15,
                "gray_figures": 5, "medusa": 1, "markers": 3, "corners": 4,
                "extra_lights": 1}
    if counts != expected:
        raise RuntimeError(f"Lighting stress scene lost gameplay review actors: {name} {counts}")
    return {"level": level, "reference": spec["reference"], "light_settings_proposed": {
        key: value for key, value in spec.items() if key not in ("level", "reference")
    }, "counts_after_reload": counts, "light_intensities_after_reload": actual_lights}


def main():
    if not u.EditorAssetLibrary.does_asset_exist(SOURCE):
        raise RuntimeError("Missing ART005H source review level")
    results = {name: run_profile(name, spec) for name, spec in PROFILES.items()}
    REPORT.write_text(json.dumps({
        "status": "editor_lighting_stress_fixture_only_not_other_board_reconstruction",
        "source_level": SOURCE,
        "reference_concept": "docs/game-design/evidence/ART-002/lighting-real-map-conditions-concept.png",
        "profiles": results,
        "fixed_factors": "Same S04 Cobble 5x6 board mesh/materials, four modular corners, figures, markers and K1 camera; only lights differ.",
        "limits": "No Sherwood/T. Rex boardState, map surface or accepted lighting coordinates. No live HUD, K2/K3, color-vision review or packaged D-07 FPS.",
    }, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    u.log("ART005I_LIGHTING_STRESS_SCENES_PASS")


main()
