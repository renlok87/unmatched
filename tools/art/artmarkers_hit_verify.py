"""Verify the target ring's simple collision on an isolated UE editor actor."""

from __future__ import annotations

import json
import math
from pathlib import Path

import unreal as u


ROOT = Path(__file__).resolve().parents[2]
REPORT = ROOT / "blender/ASSET-MARKERS-001/ue-hit-report.json"
MESH_PATH = "/Game/ArtTests/ARTMarkers/Meshes/SM_Marker_TargetRing"
LEVEL_PATH = "/Game/ArtTests/ARTMarkers/L_ARTMarkers_HitTest"


def make_level():
    levels = u.get_editor_subsystem(u.LevelEditorSubsystem)
    if u.EditorAssetLibrary.does_asset_exist(LEVEL_PATH):
        if not levels.load_level(LEVEL_PATH):
            raise RuntimeError(f"Could not load {LEVEL_PATH}")
        actors = u.get_editor_subsystem(u.EditorActorSubsystem)
        for actor in actors.get_all_level_actors():
            actors.destroy_actor(actor)
    elif not levels.new_level(LEVEL_PATH):
        raise RuntimeError(f"Could not create {LEVEL_PATH}")
    return levels


def trace(world, x: float, y: float):
    result = u.SystemLibrary.line_trace_single(
        world,
        u.Vector(x, y, 50),
        u.Vector(x, y, -20),
        u.TraceTypeQuery.TRACE_TYPE_QUERY1,
        False,
        [],
        u.DrawDebugTrace.NONE,
        True,
    )
    if isinstance(result, tuple):
        return any(value is True for value in result)
    return result is not None


def main():
    mesh = u.load_asset(MESH_PATH)
    if not mesh:
        raise RuntimeError(f"Missing imported mesh {MESH_PATH}")
    convex = mesh.get_editor_property("body_setup").get_editor_property("agg_geom").get_editor_property("convex_elems")
    if len(convex) != 4:
        raise RuntimeError(f"Target ring has {len(convex)} convex hulls, expected 4")
    levels = make_level()
    actor = u.EditorLevelLibrary.spawn_actor_from_class(u.StaticMeshActor, u.Vector(0, 0, 0))
    actor.set_actor_label("ARTMarkers target ring collision test")
    component = actor.static_mesh_component
    component.set_static_mesh(mesh)
    component.set_collision_profile_name("BlockAll")
    component.set_collision_enabled(u.CollisionEnabled.QUERY_AND_PHYSICS)
    if not levels.save_current_level() or not levels.load_level(LEVEL_PATH):
        raise RuntimeError(f"Could not save/reload {LEVEL_PATH}")
    actors = u.get_editor_subsystem(u.EditorActorSubsystem).get_all_level_actors()
    mesh_actors = [a for a in actors if isinstance(a, u.StaticMeshActor)]
    if len(mesh_actors) != 1:
        raise RuntimeError(f"Expected exactly one mesh actor, got {len(mesh_actors)}")
    actor = mesh_actors[0]
    if actor.get_actor_label() != "ARTMarkers target ring collision test":
        raise RuntimeError("Unexpected mesh actor in isolated test level")
    component = actor.static_mesh_component
    u.log(f"ART_MARKERS_COMPONENT collision={component.get_collision_enabled()} profile={component.get_collision_profile_name()}")

    world = u.EditorLevelLibrary.get_editor_world()
    points = []
    for quadrant in range(4):
        angle = math.radians(45 + 90 * quadrant)
        points.append((f"arc_{quadrant}", 22 * math.cos(angle), 22 * math.sin(angle), True))
    for quadrant in range(4):
        angle = math.radians(90 * quadrant)
        points.append((f"gap_{quadrant}", 22 * math.cos(angle), 22 * math.sin(angle), False))
    points.append(("center", 0.0, 0.0, False))

    cases = {}
    for name, x, y, expected in points:
        actual = trace(world, x, y)
        cases[name] = {
            "xy_uu": [round(x, 4), round(y, 4)],
            "expected_hit": expected,
            "actual_hit": actual,
            "pass": actual == expected,
        }
        u.log(f"ART_MARKERS_TRACE {name} expected={expected} actual={actual}")

    status = "pass" if all(case["pass"] for case in cases.values()) else "fail"
    REPORT.write_text(json.dumps({
        "status": status,
        "engine": "Unreal Engine 5.8.2",
        "mesh": MESH_PATH,
        "level": LEVEL_PATH,
        "method": "Editor-world vertical line_trace_single, visibility channel, trace_complex=False, isolated StaticMeshActor",
        "convex_hulls": len(convex),
        "cases": cases,
        "limits": "Editor collision probe only; not in-game mouse picking, HUD, board zones or packaged build",
    }, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    if status != "pass":
        raise RuntimeError("ART_MARKERS_UE_HIT_FAIL: see ue-hit-report.json")
    print("ART_MARKERS_UE_HIT_PASS 9")


main()
