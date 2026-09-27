"""Reopen the Medusa .blend and FBXs in clean Blender sessions and assert the game contract."""

from __future__ import annotations

import json
from pathlib import Path

import bpy
from mathutils import Vector


ROOT = Path(__file__).resolve().parent
REPORT = {}


def triangles(obj):
    return sum(len(poly.vertices) - 2 for poly in obj.data.polygons)


def world_bounds(objects):
    corners = [obj.matrix_world @ Vector(corner) for obj in objects for corner in obj.bound_box]
    return [[round(min(v[i] for v in corners), 5), round(max(v[i] for v in corners), 5)] for i in range(3)]


bpy.ops.wm.open_mainfile(filepath=str(ROOT / "medusa.blend"))
meshes = {obj.name: obj for obj in bpy.data.objects if obj.type == "MESH"}
armatures = [obj for obj in bpy.data.objects if obj.type == "ARMATURE"]
assert set(meshes) == {"SK_Medusa_Body", "SK_Medusa_Bow", "SM_Medusa_Base"}, meshes.keys()
assert len(armatures) == 1
assert len(armatures[0].data.bones) == 17
assert len(bpy.data.actions) >= 4
assert sum(triangles(obj) for obj in meshes.values()) <= 25000
assert all(len(obj.data.materials) == 1 and len(obj.data.uv_layers) == 1 for obj in meshes.values())
assert all(bpy.data.images[f"T_Medusa_Atlas_{suffix}.png"].size[:] == (2048, 2048)
           for suffix in ("BC", "N_OpenGL", "ORM"))
for obj in (meshes["SK_Medusa_Body"], meshes["SK_Medusa_Bow"]):
    assert obj.parent == armatures[0]
    assert any(mod.type == "ARMATURE" for mod in obj.modifiers)
    for vert in obj.data.vertices:
        weights = [g.weight for g in vert.groups]
        assert 1 <= len(weights) <= 4
        assert abs(sum(weights) - 1) < .001

REPORT["blend"] = {
    "height_m": world_bounds(meshes.values())[2][1] - world_bounds(meshes.values())[2][0],
    "triangles": {name: triangles(obj) for name, obj in meshes.items()},
    "bones": len(armatures[0].data.bones),
    "actions": sorted(action.name for action in bpy.data.actions),
    "materials_per_mesh": {name: len(obj.data.materials) for name, obj in meshes.items()},
}
assert abs(REPORT["blend"]["height_m"] - .55) < .002

bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.fbx(filepath=str(ROOT / "export/SK_Medusa.fbx"))
fbx_meshes = [obj for obj in bpy.data.objects if obj.type == "MESH"]
fbx_arms = [obj for obj in bpy.data.objects if obj.type == "ARMATURE"]
assert len(fbx_meshes) == 2
assert len(fbx_arms) == 1 and len(fbx_arms[0].data.bones) == 17
REPORT["skeletal_fbx"] = {
    "meshes": [(obj.name, triangles(obj), len(obj.data.materials)) for obj in fbx_meshes],
    "world_bounds": world_bounds(fbx_meshes),
    "bones": len(fbx_arms[0].data.bones),
}
assert abs(REPORT["skeletal_fbx"]["world_bounds"][2][1] - .55) < .002

bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.fbx(filepath=str(ROOT / "export/SM_Medusa_Base.fbx"))
base_meshes = [obj for obj in bpy.data.objects if obj.type == "MESH"]
assert len(base_meshes) == 1
REPORT["base_fbx"] = {"triangles": triangles(base_meshes[0]), "world_bounds": world_bounds(base_meshes)}
assert REPORT["base_fbx"]["triangles"] == 1780
assert abs(REPORT["base_fbx"]["world_bounds"][2][0]) < .001
# Blender converts the FBX centimetre coordinates back to metres on import.
# Unreal's independent import check below validates the 4 uu game-space height.
assert abs(REPORT["base_fbx"]["world_bounds"][2][1] - .06) < .0005
assert abs(REPORT["base_fbx"]["world_bounds"][0][0] + .15) < .0005
assert abs(REPORT["base_fbx"]["world_bounds"][0][1] - .15) < .0005
assert abs(REPORT["base_fbx"]["world_bounds"][1][0] + .15) < .0005
assert abs(REPORT["base_fbx"]["world_bounds"][1][1] - .15) < .0005

for clip in ("Idle", "LungeAttack", "HitReact", "DeathSettle"):
    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.ops.import_scene.fbx(filepath=str(ROOT / f"export/AM_Medusa_{clip}.fbx"))
    arms = [obj for obj in bpy.data.objects if obj.type == "ARMATURE"]
    assert len(arms) == 1
    assert sum(obj.type == "MESH" for obj in bpy.data.objects) == 2
    action = arms[0].animation_data.action
    assert action is not None
    scene = bpy.context.scene
    scene.frame_set(round(action.frame_range[0]))
    start_root = arms[0].pose.bones["root"].location.copy()
    scene.frame_set(round(action.frame_range[1]))
    end_root = arms[0].pose.bones["root"].location.copy()
    root_delta = (end_root - start_root).length
    assert root_delta < .001, (clip, root_delta)
    REPORT.setdefault("clip_fbx", {})[clip] = {
        "frame_range": [round(v, 3) for v in action.frame_range],
        "bones": len(arms[0].data.bones),
        "mesh_count": sum(obj.type == "MESH" for obj in bpy.data.objects),
        "root_delta": round(root_delta, 6),
    }

(ROOT / "verify-report.json").write_text(json.dumps(REPORT, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
print("MEDUSA_VERIFY", json.dumps(REPORT, ensure_ascii=False))
