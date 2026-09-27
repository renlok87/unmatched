"""Deterministic FBX export for ART-001 and later Blender assets.

Example:
  blender --background --factory-startup blender/_shared/check_set.blend \
    --python blender/_tools/batch_export.py -- \
    --preset blender/_tools/presets/UM_FBX_v1.json --all

The editable .blend stays in metres. During export we temporarily convert the
selected data, rig rest pose and location curves to centimetre-numbered values,
then patch FBX UnitScaleFactor to 1.0. UE therefore receives 1 FBX unit = 1 uu
without putting an extra x100 scale on skeleton bone zero.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import struct
import sys
from pathlib import Path

import bpy
from mathutils import Matrix, Vector


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_BLEND = ROOT / "blender" / "_shared" / "check_set.blend"
DEFAULT_PRESET = ROOT / "blender" / "_tools" / "presets" / "UM_FBX_v1.json"
DEFAULT_OUT = ROOT / "blender" / "_shared" / "check_set" / "export"


def script_args() -> argparse.Namespace:
    argv = sys.argv[sys.argv.index("--") + 1 :] if "--" in sys.argv else []
    parser = argparse.ArgumentParser()
    parser.add_argument("--blend", type=Path, default=DEFAULT_BLEND)
    parser.add_argument("--preset", type=Path, default=DEFAULT_PRESET)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--only", action="append", default=[])
    parser.add_argument("--all", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    return parser.parse_args(argv)


def iter_action_fcurves(action):
    if hasattr(action, "fcurves"):
        yield from action.fcurves
        return
    for layer in action.layers:
        for strip in layer.strips:
            for bag in strip.channelbags:
                yield from bag.fcurves


def transform_location_curves(action, matrix: Matrix, scale: float) -> None:
    grouped: dict[str, dict[int, object]] = {}
    for curve in iter_action_fcurves(action):
        if curve.data_path == "location" or curve.data_path.endswith(".location"):
            grouped.setdefault(curve.data_path, {})[curve.array_index] = curve
    for curves in grouped.values():
        frames = sorted({point.co[0] for curve in curves.values() for point in curve.keyframe_points})
        for frame in frames:
            source = Vector(tuple(curves[i].evaluate(frame) if i in curves else 0.0 for i in range(3)))
            target = (matrix @ source) * scale
            for axis, curve in curves.items():
                for point in curve.keyframe_points:
                    if abs(point.co[0] - frame) < 1e-5:
                        ratio = target[axis] / point.co[1] if abs(point.co[1]) > 1e-9 else 1.0
                        point.co[1] = target[axis]
                        if abs(point.handle_left[1]) > 1e-9:
                            point.handle_left[1] *= ratio
                        else:
                            point.handle_left[1] = target[axis]
                        if abs(point.handle_right[1]) > 1e-9:
                            point.handle_right[1] *= ratio
                        else:
                            point.handle_right[1] = target[axis]


def transform_armature(armature, rotation: Matrix, scale: float) -> None:
    bpy.context.view_layer.objects.active = armature
    armature.select_set(True)
    bpy.ops.object.mode_set(mode="EDIT")
    for bone in armature.data.edit_bones:
        bone.head = (rotation @ bone.head) * scale
        bone.tail = (rotation @ bone.tail) * scale
    bpy.ops.object.mode_set(mode="OBJECT")
    if armature.animation_data and armature.animation_data.action:
        transform_location_curves(armature.animation_data.action, rotation, scale)


def transform_objects(objects, rotation: Matrix, scale: float) -> None:
    matrix = Matrix.Scale(scale, 4) @ rotation
    for obj in objects:
        obj.location = (rotation @ obj.location) * scale
        if obj.type == "MESH":
            obj.data.transform(matrix)


def patch_fbx_unit_scale(path: Path, target: float) -> float:
    """Patch the binary FBX GlobalSettings/UnitScaleFactor double in place."""
    data = bytearray(path.read_bytes())
    index = data.find(b"UnitScaleFactor")
    if index < 0:
        raise RuntimeError(f"UnitScaleFactor not found in {path}")
    double_tag = data.find(b"double", index)
    number_tag = data.find(b"Number", double_tag)
    if double_tag < 0 or number_tag < 0:
        raise RuntimeError(f"Unexpected UnitScaleFactor property layout in {path}")
    string_length = struct.unpack_from("<I", data, number_tag - 4)[0]
    cursor = number_tag - 4 + 4 + string_length
    if data[cursor : cursor + 1] != b"S":
        raise RuntimeError(f"Unexpected UnitScaleFactor string property in {path}")
    value_length = struct.unpack_from("<I", data, cursor + 1)[0]
    cursor += 1 + 4 + value_length
    if data[cursor : cursor + 1] != b"D":
        raise RuntimeError(f"Unexpected UnitScaleFactor numeric property in {path}")
    old_value = struct.unpack_from("<d", data, cursor + 1)[0]
    struct.pack_into("<d", data, cursor + 1, target)
    path.write_bytes(data)
    return old_value


def select(objects) -> None:
    bpy.ops.object.select_all(action="DESELECT")
    for obj in objects:
        obj.select_set(True)
    bpy.context.view_layer.objects.active = objects[0]


def export_fbx(path: Path, objects, preset: dict, animation: bool) -> None:
    select(objects)
    bpy.ops.export_scene.fbx(
        filepath=str(path),
        use_selection=True,
        object_types={"MESH", "ARMATURE"},
        apply_unit_scale=bool(preset["apply_unit_scale"]),
        apply_scale_options=preset["apply_scale_options"],
        axis_forward=preset["axis_forward"],
        axis_up=preset["axis_up"],
        use_triangles=bool(preset["use_triangles"]),
        mesh_smooth_type=preset["mesh_smooth_type"],
        add_leaf_bones=bool(preset["add_leaf_bones"]),
        primary_bone_axis=preset["primary_bone_axis"],
        secondary_bone_axis=preset["secondary_bone_axis"],
        bake_anim=animation,
        bake_anim_use_all_bones=bool(preset["bake_anim_use_all_bones"]),
        bake_anim_use_nla_strips=bool(preset["bake_anim_use_nla_strips"]),
        bake_anim_use_all_actions=bool(preset["bake_anim_use_all_actions"]),
        bake_anim_force_startend_keying=bool(preset["bake_anim_force_startend_keying"]),
        path_mode=preset["path_mode"],
        use_custom_props=False,
    )


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def main() -> None:
    args = script_args()
    blend_path = args.blend.resolve()
    preset_path = args.preset.resolve()
    out_dir = args.out.resolve()
    if Path(bpy.data.filepath).resolve() != blend_path:
        bpy.ops.wm.open_mainfile(filepath=str(blend_path))
    preset = json.loads(preset_path.read_text(encoding="utf-8"))
    out_dir.mkdir(parents=True, exist_ok=True)
    for old in out_dir.glob("*.fbx"):
        old.unlink()

    groups: dict[str, dict] = {
        "SM_ART001_Cube": {"objects": ["SM_ART001_Cube"]},
        "SM_ART001_Arrow": {"objects": ["SM_ART001_Arrow"]},
        "SM_ART001_Mannequin": {
            "objects": ["SM_ART001_Mannequin", "UCX_SM_ART001_Mannequin_00"]
        },
        "SM_ART001_NormalProbe": {"objects": ["SM_ART001_NormalProbe"]},
        "SK_ART001_Mannequin": {
            "tag": "skeletal_mannequin",
            "animation": True,
        },
        "AM_ART001_RootMotion": {
            "tag": "skeletal_mannequin",
            "animation": True,
        },
    }
    requested = set(groups) if args.all or not args.only else set(args.only)
    unknown = requested.difference(groups)
    if unknown:
        raise RuntimeError(f"Unknown export group(s): {sorted(unknown)}")
    if args.dry_run:
        print("ART001_EXPORT_PLAN " + json.dumps(sorted(requested)))
        return

    rotation = Matrix.Rotation(math.radians(float(preset["export_space_rotation_z_degrees"])), 4, "Z")
    factor = float(preset["temporary_data_scale"])
    all_exported_objects = [obj for obj in bpy.data.objects if obj.get("art001_export_group")]
    armatures = [obj for obj in all_exported_objects if obj.type == "ARMATURE"]
    for armature in armatures:
        transform_armature(armature, rotation, factor)
    transform_objects(all_exported_objects, rotation, factor)

    try:
        source_blend = blend_path.resolve().relative_to(ROOT.resolve()).as_posix()
    except ValueError:
        source_blend = str(blend_path.resolve())
    manifest = {
        "preset": preset,
        "source_blend": source_blend,
        "source_sha256": sha256(blend_path),
        "files": [],
    }
    for name in sorted(requested):
        definition = groups[name]
        if "objects" in definition:
            objects = [bpy.data.objects[obj_name] for obj_name in definition["objects"]]
        else:
            objects = [obj for obj in bpy.data.objects if obj.get("art001_export_group") == definition["tag"]]
        path = out_dir / f"{name}.fbx"
        export_fbx(path, objects, preset, bool(definition.get("animation")))
        old_unit_scale = patch_fbx_unit_scale(path, float(preset["patch_fbx_unit_scale_to"]))
        manifest["files"].append(
            {
                "name": path.name,
                "bytes": path.stat().st_size,
                "sha256": sha256(path),
                "unit_scale_factor_before_patch": old_unit_scale,
                "unit_scale_factor_after_patch": float(preset["patch_fbx_unit_scale_to"]),
                "objects": [obj.name for obj in objects],
            }
        )
        print(f"ART001_EXPORT {path.name} USF {old_unit_scale:g}->1 sha256={sha256(path)}")
    (out_dir / "export-manifest.json").write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    print("ART001_EXPORT_COMPLETE " + json.dumps({"count": len(manifest["files"]), "out": str(out_dir)}))


if __name__ == "__main__":
    main()
