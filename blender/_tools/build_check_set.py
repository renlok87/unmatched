"""Build the deterministic ART-001 Blender source files.

Run with Blender 5.2.2:
  blender --background --factory-startup --python blender/_tools/build_check_set.py

The source scene stays in metres and faces -Y. Export-space conversion is owned by
batch_export.py so the .blend remains a clean authoring reference.
"""

from __future__ import annotations

import json
import math
from pathlib import Path

import bpy
import bmesh
from mathutils import Vector


ROOT = Path(__file__).resolve().parents[2]
SHARED = ROOT / "blender" / "_shared"
CHECK_DIR = SHARED / "check_set"
CHECK_BLEND = SHARED / "check_set.blend"
RIG_BLEND = SHARED / "rig_template.blend"
FPS = 24


def reset_scene() -> None:
    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.context.preferences.filepaths.save_version = 0
    scene = bpy.context.scene
    scene.unit_settings.system = "METRIC"
    scene.unit_settings.scale_length = 1.0
    scene.render.fps = FPS
    scene.frame_start = 1
    scene.frame_end = 30


def material(name: str, color: tuple[float, float, float], roughness: float = 0.8):
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    mat["TeamColor"] = [0.16, 0.48, 0.95, 1.0]
    bsdf = mat.node_tree.nodes.get("Principled BSDF")
    bsdf.inputs["Base Color"].default_value = (*color, 1.0)
    bsdf.inputs["Roughness"].default_value = roughness
    return mat


def tag(obj, group: str) -> None:
    obj["art001_export_group"] = group


def activate(obj) -> None:
    bpy.ops.object.select_all(action="DESELECT")
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj


def apply_and_bottom_origin(obj) -> None:
    activate(obj)
    bpy.ops.object.transform_apply(location=False, rotation=True, scale=True)
    bpy.context.scene.cursor.location = (0.0, 0.0, 0.0)
    bpy.ops.object.origin_set(type="ORIGIN_CURSOR")


def smart_uv(obj) -> None:
    activate(obj)
    bpy.ops.object.mode_set(mode="EDIT")
    bpy.ops.mesh.select_all(action="SELECT")
    bpy.ops.uv.smart_project(angle_limit=math.radians(66.0), island_margin=0.02)
    bpy.ops.object.mode_set(mode="OBJECT")


def planar_top_uv(obj) -> None:
    """Map the top face across UV0 so the split normal probe is deterministic."""
    uv_layer = obj.data.uv_layers.active or obj.data.uv_layers.new(name="UVMap")
    for polygon in obj.data.polygons:
        for loop_index in polygon.loop_indices:
            if polygon.normal.z > 0.9:
                vertex_index = obj.data.loops[loop_index].vertex_index
                co = obj.data.vertices[vertex_index].co
                uv_layer.data[loop_index].uv = (co.x / 0.4 + 0.5, co.y / 0.4 + 0.5)
            else:
                uv_layer.data[loop_index].uv = (0.5, 0.5)


def cube(name: str, dims, location, mat, group: str):
    bpy.ops.mesh.primitive_cube_add(size=1.0, location=location)
    obj = bpy.context.object
    obj.name = name
    obj.data.name = name
    obj.dimensions = dims
    if mat:
        obj.data.materials.append(mat)
    apply_and_bottom_origin(obj)
    smart_uv(obj)
    tag(obj, group)
    return obj


def cylinder(name: str, radius: float, depth: float, location, mat, group: str, vertices: int = 16):
    bpy.ops.mesh.primitive_cylinder_add(vertices=vertices, radius=radius, depth=depth, location=location)
    obj = bpy.context.object
    obj.name = name
    obj.data.name = name
    if mat:
        obj.data.materials.append(mat)
    apply_and_bottom_origin(obj)
    smart_uv(obj)
    tag(obj, group)
    return obj


def sphere(name: str, radius: float, location, mat, group: str):
    bpy.ops.mesh.primitive_uv_sphere_add(segments=16, ring_count=8, radius=radius, location=location)
    obj = bpy.context.object
    obj.name = name
    obj.data.name = name
    if mat:
        obj.data.materials.append(mat)
    apply_and_bottom_origin(obj)
    smart_uv(obj)
    tag(obj, group)
    return obj


def join(parts, name: str, group: str):
    bpy.ops.object.select_all(action="DESELECT")
    for part in parts:
        part.select_set(True)
    bpy.context.view_layer.objects.active = parts[0]
    bpy.ops.object.join()
    result = bpy.context.object
    result.name = name
    result.data.name = name
    apply_and_bottom_origin(result)
    smart_uv(result)
    tag(result, group)
    return result


def build_arrow(mat):
    # A 1 m arrow authored from tail y=0 to tip y=-1. Top marker is offset
    # in X so a mirror/axis error is visible as well as measurable.
    outline = [(-0.05, 0.0), (0.05, 0.0), (0.05, -0.68),
               (0.16, -0.68), (0.0, -1.0), (-0.16, -0.68), (-0.05, -0.68)]
    verts = [(x, y, z) for z in (0.0, 0.04) for x, y in outline]
    n = len(outline)
    faces = [tuple(range(n - 1, -1, -1)), tuple(range(n, 2 * n))]
    for i in range(n):
        j = (i + 1) % n
        faces.append((i, j, n + j, n + i))
    mesh = bpy.data.meshes.new("SM_ART001_Arrow")
    mesh.from_pydata(verts, [], faces)
    mesh.update()
    arrow = bpy.data.objects.new("SM_ART001_Arrow", mesh)
    bpy.context.collection.objects.link(arrow)
    arrow.data.materials.append(mat)
    marker = cube("ART001_ArrowTopMarker", (0.07, 0.07, 0.06), (0.12, -0.15, 0.07), mat, "arrow")
    return join([arrow, marker], "SM_ART001_Arrow", "arrow")


def mannequin_parts(prefix: str, mat, group: str):
    parts = [
        cylinder(prefix + "_Base", 0.12, 0.02, (0, 0, 0.01), mat, group),
        cylinder(prefix + "_Torso", 0.065, 0.21, (0, 0, 0.255), mat, group),
        sphere(prefix + "_Head", 0.05, (0, 0, 0.45), mat, group),
        cylinder(prefix + "_LegL", 0.025, 0.15, (-0.035, 0, 0.095), mat, group, 12),
        cylinder(prefix + "_LegR", 0.025, 0.15, (0.035, 0, 0.095), mat, group, 12),
    ]
    for side, x in (("L", -0.095), ("R", 0.095)):
        arm = cylinder(prefix + "_Arm" + side, 0.018, 0.19, (x, 0, 0.31), mat, group, 12)
        arm.rotation_euler = (0.0, math.radians(18 if side == "L" else -18), 0.0)
        apply_and_bottom_origin(arm)
        parts.append(arm)
    return parts


BONES = [
    ("root", None, (0, 0, 0), (0, 0, 0.06)),
    ("hips", "root", (0, 0, 0.14), (0, 0, 0.22)),
    ("spine", "hips", (0, 0, 0.22), (0, 0, 0.35)),
    ("head", "spine", (0, 0, 0.35), (0, 0, 0.48)),
    ("arm_upper.L", "spine", (-0.06, 0, 0.34), (-0.12, 0, 0.29)),
    ("arm_lower.L", "arm_upper.L", (-0.12, 0, 0.29), (-0.16, 0, 0.22)),
    ("hand.L", "arm_lower.L", (-0.16, 0, 0.22), (-0.17, -0.02, 0.19)),
    ("arm_upper.R", "spine", (0.06, 0, 0.34), (0.12, 0, 0.29)),
    ("arm_lower.R", "arm_upper.R", (0.12, 0, 0.29), (0.16, 0, 0.22)),
    ("hand.R", "arm_lower.R", (0.16, 0, 0.22), (0.17, -0.02, 0.19)),
    ("leg_upper.L", "hips", (-0.035, 0, 0.15), (-0.035, 0, 0.09)),
    ("leg_lower.L", "leg_upper.L", (-0.035, 0, 0.09), (-0.035, 0, 0.03)),
    ("foot.L", "leg_lower.L", (-0.035, 0, 0.03), (-0.035, -0.04, 0.015)),
    ("leg_upper.R", "hips", (0.035, 0, 0.15), (0.035, 0, 0.09)),
    ("leg_lower.R", "leg_upper.R", (0.035, 0, 0.09), (0.035, 0, 0.03)),
    ("foot.R", "leg_lower.R", (0.035, 0, 0.03), (0.035, -0.04, 0.015)),
    ("weapon", "hand.R", (0.17, -0.02, 0.19), (0.17, -0.08, 0.19)),
]


def build_armature(name: str, group: str | None = None):
    data = bpy.data.armatures.new(name)
    arm = bpy.data.objects.new(name, data)
    bpy.context.collection.objects.link(arm)
    if group:
        tag(arm, group)
    bpy.context.view_layer.objects.active = arm
    arm.select_set(True)
    bpy.ops.object.mode_set(mode="EDIT")
    for bone_name, parent_name, head, tail in BONES:
        bone = data.edit_bones.new(bone_name)
        bone.head = head
        bone.tail = tail
        bone.roll = 0.0
        if parent_name:
            bone.parent = data.edit_bones[parent_name]
            bone.use_connect = False
    bpy.ops.object.mode_set(mode="OBJECT")
    for pose_bone in arm.pose.bones:
        pose_bone.rotation_mode = "XYZ"
    return arm


def rigid_bind(arm, obj, bone_name: str) -> None:
    modifier = obj.modifiers.new("ART001_Armature", "ARMATURE")
    modifier.object = arm
    obj.parent = arm
    group = obj.vertex_groups.new(name=bone_name)
    group.add([v.index for v in obj.data.vertices], 1.0, "REPLACE")


def build_action(arm):
    action = bpy.data.actions.new("AM_ART001_RootMotion")
    arm.animation_data_create()
    arm.animation_data.action = action
    for frame, y, raise_degrees in ((1, 0.0, 0.0), (15, -0.5, -55.0), (30, -1.0, -105.0)):
        bpy.context.scene.frame_set(frame)
        arm.location = (0.0, y, 0.0)
        arm.keyframe_insert(data_path="location", frame=frame)
        upper = arm.pose.bones["arm_upper.R"]
        upper.rotation_euler = (0.0, math.radians(raise_degrees), 0.0)
        upper.keyframe_insert(data_path="rotation_euler", frame=frame)
    bpy.context.scene.frame_set(1)
    return action


def save_normal_probe() -> None:
    CHECK_DIR.mkdir(parents=True, exist_ok=True)
    image = bpy.data.images.new("T_ART001_Normal_DX", width=64, height=64, alpha=False, float_buffer=False)
    pixels = []
    for _y in range(64):
        for x in range(64):
            # DirectX tangent normals: opposing green halves make inversion obvious.
            pixels.extend((0.5, 0.25 if x < 32 else 0.75, 1.0, 1.0))
    image.pixels = pixels
    image.file_format = "PNG"
    image.filepath_raw = str(CHECK_DIR / "T_ART001_Normal_DX.png")
    image.save()


def build_check_set() -> dict:
    reset_scene()
    gray = material("M_ART001_TeamColor", (0.55, 0.58, 0.62))
    orange = material("M_ART001_Axis", (0.9, 0.42, 0.08))
    normal_mat = material("M_ART001_NormalProbe", (0.45, 0.45, 0.48), 0.55)

    check_cube = cube("SM_ART001_Cube", (1, 1, 1), (0, 0, 0.5), gray, "cube")
    arrow = build_arrow(orange)
    static_parts = mannequin_parts("ART001_Static", gray, "static_mannequin")
    static_body = join(static_parts, "SM_ART001_Mannequin", "static_mannequin")
    collision = cylinder("UCX_SM_ART001_Mannequin_00", 0.13, 0.50, (0, 0, 0.25), None,
                         "static_mannequin", vertices=12)
    normal_probe = cube("SM_ART001_NormalProbe", (0.4, 0.4, 0.1), (0, 0, 0.05), normal_mat,
                        "normal_probe")
    planar_top_uv(normal_probe)

    arm = build_armature("SKEL_ART001_Mannequin", "skeletal_mannequin")
    sk_parts = mannequin_parts("SK_ART001", gray, "skeletal_mannequin")
    rigid_map = {
        "SK_ART001_Base": "root", "SK_ART001_Torso": "spine", "SK_ART001_Head": "head",
        "SK_ART001_LegL": "leg_upper.L", "SK_ART001_LegR": "leg_upper.R",
        "SK_ART001_ArmL": "arm_upper.L", "SK_ART001_ArmR": "arm_upper.R",
    }
    for part in sk_parts:
        rigid_bind(arm, part, rigid_map[part.name])
    action = build_action(arm)

    save_normal_probe()
    CHECK_DIR.mkdir(parents=True, exist_ok=True)
    bpy.ops.wm.save_as_mainfile(filepath=str(CHECK_BLEND))

    def dims(obj):
        return [round(float(v), 6) for v in obj.dimensions]

    report = {
        "blender_version": bpy.app.version_string,
        "unit_system": bpy.context.scene.unit_settings.system,
        "unit_scale": bpy.context.scene.unit_settings.scale_length,
        "authored_forward": "-Y",
        "objects": {
            check_cube.name: {"dimensions_m": dims(check_cube), "origin": list(check_cube.location)},
            arrow.name: {"dimensions_m": dims(arrow), "bounds_y_m": [-1.0, 0.0]},
            static_body.name: {"dimensions_m": dims(static_body), "origin": list(static_body.location)},
            collision.name: {"dimensions_m": dims(collision)},
            normal_probe.name: {"dimensions_m": dims(normal_probe)},
        },
        "rig": {"name": arm.name, "bones": [b.name for b in arm.data.bones], "bone_count": len(arm.data.bones)},
        "animation": {"name": action.name, "frames": [1, 30], "fps": FPS,
                      "root_motion_m": [0.0, -1.0, 0.0], "arm_raise_degrees": -105.0},
    }
    (CHECK_DIR / "source-report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    return report


def build_rig_template() -> None:
    reset_scene()
    arm = build_armature("SKEL_UM_Template")
    arm["contract"] = "D-11 light rig; authoring forward -Y; metres"
    arm["max_vertex_influences"] = 4
    bpy.ops.wm.save_as_mainfile(filepath=str(RIG_BLEND))


if __name__ == "__main__":
    built = build_check_set()
    build_rig_template()
    print("ART001_BUILD " + json.dumps(built, ensure_ascii=False))
