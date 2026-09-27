"""Build the Medusa production candidate from Tripo's 15-part Quad retopology.

Run with Blender 5.2: blender --background --factory-startup --python build_segmented_medusa.py
The source remains untouched. Authoring coordinates are metres; FBX coordinates are cm.
"""

import json
import math
import struct
from pathlib import Path

import bpy
from mathutils import Matrix, Vector


ROOT = Path(__file__).resolve().parent
SOURCE = ROOT / "tripo-source/b6253e58/medusa-segmented-retopo.glb"
ATLAS = json.loads((ROOT / "atlas-report.json").read_text(encoding="utf-8"))
EXPORT = ROOT / "export"
TEXTURES = ROOT / "textures"
PREVIEW = ROOT / "preview"
for folder in (EXPORT, TEXTURES, PREVIEW):
    folder.mkdir(parents=True, exist_ok=True)


def make_armature():
    # Left denotes the bow side (viewer right, Blender +X). All dimensions are metres.
    p = lambda x, y, z: Vector((x, y, z))
    bones = [
        ("root", None, p(0, 0, 0), p(0, 0, .045)),
        ("hips", "root", p(0, 0, .18), p(0, 0, .245)),
        ("spine", "hips", p(0, 0, .245), p(0, 0, .35)),
        ("head", "spine", p(0, 0, .385), p(0, 0, .49)),
        ("arm_upper.L", "spine", p(.045, 0, .355), p(.068, -.013, .305)),
        ("arm_lower.L", "arm_upper.L", p(.068, -.013, .305), p(.10, -.045, .29)),
        ("hand.L", "arm_lower.L", p(.10, -.045, .29), p(.112, -.06, .275)),
        ("arm_upper.R", "spine", p(-.045, 0, .355), p(-.068, -.018, .305)),
        ("arm_lower.R", "arm_upper.R", p(-.068, -.018, .305), p(-.05, -.045, .305)),
        ("hand.R", "arm_lower.R", p(-.05, -.045, .305), p(-.038, -.055, .29)),
        ("leg_upper.L", "hips", p(.03, 0, .19), p(.038, -.012, .12)),
        ("leg_lower.L", "leg_upper.L", p(.038, -.012, .12), p(.04, -.015, .065)),
        ("foot.L", "leg_lower.L", p(.04, -.015, .065), p(.04, -.045, .045)),
        ("leg_upper.R", "hips", p(-.03, 0, .19), p(-.038, -.012, .12)),
        ("leg_lower.R", "leg_upper.R", p(-.038, -.012, .12), p(-.04, -.015, .065)),
        ("foot.R", "leg_lower.R", p(-.04, -.015, .065), p(-.04, -.045, .045)),
        ("weapon", "hand.L", p(.112, -.06, .275), p(.14, -.06, .275)),
    ]
    data = bpy.data.armatures.new("SKEL_Medusa")
    arm = bpy.data.objects.new("SKEL_Medusa", data)
    bpy.context.collection.objects.link(arm)
    bpy.context.view_layer.objects.active = arm
    bpy.ops.object.mode_set(mode="EDIT")
    for name, parent, head, tail in bones:
        bone = data.edit_bones.new(name)
        bone.head, bone.tail = head, tail
        if parent:
            bone.parent = data.edit_bones[parent]
        bone.use_connect = False
    bpy.ops.object.mode_set(mode="OBJECT")
    for bone in arm.pose.bones:
        bone.rotation_mode = "XYZ"
    return arm


def source_part_indices(mesh, name):
    group = mesh.vertex_groups.get("SRC_" + name)
    assert group is not None, name
    return [v.index for v in mesh.data.vertices if any(g.group == group.index for g in v.groups)]


def bind_mesh(arm, mesh):
    groups = {bone.name: mesh.vertex_groups.new(name=bone.name) for bone in arm.data.bones}

    def blend(z, center, span, low, high):
        t = max(0.0, min(1.0, (z - center) / span + .5))
        return [(low, 1 - t), (high, t)]

    def weights(part, z):
        if part in {1, 3, 10, 14}:
            return [("head", 1)]
        if part == 7:
            return [("spine", 1)]
        if part == 0:
            return blend(z, .29, .07, "hips", "spine")
        if part in {5, 6}:
            side = ".L" if part == 5 else ".R"
            if z < .105:
                return blend(z, .075, .03, "foot" + side, "leg_lower" + side)
            return blend(z, .16, .04, "leg_lower" + side, "leg_upper" + side)
        if part in {8, 9}:
            side = ".L" if part == 8 else ".R"
            return blend(z, .335, .035, "arm_lower" + side, "arm_upper" + side)
        if part == 11:
            return [("arm_lower.R", 1)]
        if part == 12:
            return [("hand.L", 1)]
        if part == 13:
            return [("hand.R", 1)]
        raise RuntimeError(f"Unmapped part {part}")

    counts = {}
    for part in range(15):
        if part in (2, 4):
            continue
        indices = source_part_indices(mesh, f"tripo_part_{part}")
        counts[f"part_{part}"] = len(indices)
        for index in indices:
            for bone, weight in weights(part, mesh.data.vertices[index].co.z):
                if weight > 1e-5:
                    groups[bone].add([index], weight, "REPLACE")
    for group in list(mesh.vertex_groups):
        if group.name.startswith("SRC_"):
            mesh.vertex_groups.remove(group)
    bone_group_indices = {group.index for group in groups.values()}
    missing = [v.index for v in mesh.data.vertices if not any(g.group in bone_group_indices for g in v.groups)]
    assert not missing, f"Missing weights on {len(missing)} vertices"
    mesh.parent = arm
    modifier = mesh.modifiers.new("Armature", "ARMATURE")
    modifier.object = arm
    return {"weighted_vertices": len(mesh.data.vertices), "part_vertices": counts,
            "max_influences": max(sum(g.group in bone_group_indices for g in v.groups) for v in mesh.data.vertices)}


def make_action(arm, name, frames):
    reset_pose(arm)
    action = bpy.data.actions.new(name)
    action.use_fake_user = True
    if arm.animation_data is None:
        arm.animation_data_create()
    arm.animation_data.action = action
    for frame, keys in sorted(frames.items()):
        bpy.context.scene.frame_set(frame)
        for bone_name, channels in keys.items():
            bone = arm.pose.bones[bone_name]
            for channel, value in channels.items():
                setattr(bone, channel, value)
                bone.keyframe_insert(data_path=channel, frame=frame)
    return action


def reset_pose(arm):
    for bone in arm.pose.bones:
        bone.location = (0, 0, 0)
        bone.rotation_euler = (0, 0, 0)
        bone.scale = (1, 1, 1)


def actions_for(arm):
    deg = math.radians
    return {
        "AM_Medusa_Idle": make_action(arm, "Idle", {
            1: {"spine": {"rotation_euler": (0, 0, 0)}, "head": {"rotation_euler": (0, 0, 0)}},
            29: {"spine": {"rotation_euler": (deg(2.5), 0, 0)},
                 "head": {"rotation_euler": (deg(-3), 0, 0)}},
            57: {"spine": {"rotation_euler": (0, 0, 0)}, "head": {"rotation_euler": (0, 0, 0)}},
        }),
        "AM_Medusa_LungeAttack": make_action(arm, "LungeAttack", {
            1: {"spine": {"rotation_euler": (0, 0, 0)},
                "arm_upper.L": {"rotation_euler": (0, 0, 0)},
                "arm_upper.R": {"rotation_euler": (0, 0, 0)}},
            7: {"spine": {"rotation_euler": (deg(12), 0, 0)},
                "arm_upper.L": {"rotation_euler": (deg(8), deg(15), 0)},
                "arm_upper.R": {"rotation_euler": (0, deg(-25), 0)}},
            11: {"spine": {"rotation_euler": (deg(12), 0, 0)},
                 "arm_upper.L": {"rotation_euler": (deg(8), deg(15), 0)},
                 "arm_upper.R": {"rotation_euler": (0, deg(-35), 0)}},
            15: {"spine": {"rotation_euler": (0, 0, 0)},
                 "arm_upper.L": {"rotation_euler": (0, 0, 0)},
                 "arm_upper.R": {"rotation_euler": (0, 0, 0)}},
        }),
        "AM_Medusa_HitReact": make_action(arm, "HitReact", {
            1: {"spine": {"rotation_euler": (0, 0, 0)}, "head": {"rotation_euler": (0, 0, 0)}},
            4: {"spine": {"rotation_euler": (deg(-10), 0, 0)},
                "head": {"rotation_euler": (deg(-10), 0, 0)}},
            10: {"spine": {"rotation_euler": (0, 0, 0)}, "head": {"rotation_euler": (0, 0, 0)}},
        }),
        "AM_Medusa_DeathSettle": make_action(arm, "DeathSettle", {
            1: {"hips": {"location": (0, 0, 0)},
                "spine": {"rotation_euler": (0, 0, 0)},
                "head": {"rotation_euler": (0, 0, 0)}},
            12: {"hips": {"location": (0, 0, -.06)},
                 "spine": {"rotation_euler": (deg(25), 0, 0)},
                 "head": {"rotation_euler": (deg(20), 0, 0)}},
            22: {"hips": {"location": (0, 0, -.10)},
                 "spine": {"rotation_euler": (deg(48), 0, 0)},
                 "head": {"rotation_euler": (deg(25), 0, 0)}},
        }),
    }


def atlas_material():
    mat = bpy.data.materials.new("M_Medusa_Atlas")
    mat.use_nodes = True
    nodes = mat.node_tree.nodes
    bsdf = nodes.get("Principled BSDF")
    links = mat.node_tree.links
    images = {}
    for suffix in ("BC", "N_OpenGL", "ORM"):
        image = bpy.data.images.load(str(TEXTURES / f"T_Medusa_Atlas_{suffix}.png"), check_existing=True)
        if suffix != "BC":
            image.colorspace_settings.name = "Non-Color"
        node = nodes.new("ShaderNodeTexImage")
        node.image = image
        node.label = suffix
        images[suffix] = node
    links.new(images["BC"].outputs["Color"], bsdf.inputs["Base Color"])
    normal = nodes.new("ShaderNodeNormalMap")
    links.new(images["N_OpenGL"].outputs["Color"], normal.inputs["Color"])
    links.new(normal.outputs["Normal"], bsdf.inputs["Normal"])
    channels = nodes.new("ShaderNodeSeparateColor")
    links.new(images["ORM"].outputs["Color"], channels.inputs["Color"])
    links.new(channels.outputs["Green"], bsdf.inputs["Roughness"])
    links.new(channels.outputs["Blue"], bsdf.inputs["Metallic"])
    return mat


def prepare_parts():
    bpy.ops.import_scene.gltf(filepath=str(SOURCE))
    parts = {obj.name: obj for obj in bpy.data.objects if obj.type == "MESH"}
    assert len(parts) == 15, list(parts)
    for obj in parts.values():
        world = obj.matrix_world.copy()
        obj.parent = None
        obj.data.transform(world)
        obj.matrix_world.identity()
    top = max(vert.co.z for obj in parts.values() for vert in obj.data.vertices)
    bottom = min(vert.co.z for obj in parts.values() for vert in obj.data.vertices)
    scale = .55 / (top - bottom)
    mat = atlas_material()
    for name, obj in parts.items():
        cell = ATLAS["cells"][name]
        x, y, width, inset = cell["x"], cell["y_top"], cell["cell"], cell["inset"]
        inner = width - 2 * inset
        for uv_data in obj.data.uv_layers.active.data:
            uv = uv_data.uv.copy()
            uv_data.uv = ((x + inset + uv.x * inner) / 2048,
                          1 - (y + inset + (1 - uv.y) * inner) / 2048)
        for vert in obj.data.vertices:
            vert.co = (vert.co - Vector((0, 0, bottom))) * scale
        obj.data.materials.clear()
        obj.data.materials.append(mat)
        obj.data.update()
    return parts


def join_body(parts):
    body_parts = [obj for name, obj in parts.items() if name not in {"tripo_part_2", "tripo_part_4"}]
    for obj in body_parts:
        group = obj.vertex_groups.new(name="SRC_" + obj.name)
        group.add(list(range(len(obj.data.vertices))), 1.0, "REPLACE")
    bpy.ops.object.select_all(action="DESELECT")
    for obj in body_parts:
        obj.select_set(True)
    body = parts["tripo_part_0"]
    bpy.context.view_layer.objects.active = body
    bpy.ops.object.join()
    body.name = "SK_Medusa_Body"
    body.data.name = "Medusa_Body_Quad"
    bow = parts["tripo_part_4"]
    bow.name = "SK_Medusa_Bow"
    base = parts["tripo_part_2"]
    base.name = "SM_Medusa_Base"
    # Keep Tripo's base silhouette while meeting the proposed 30 x 6 uu
    # miniature footprint and centring its game-space pivot at the tile centre.
    coords = [vert.co for vert in base.data.vertices]
    lo = [min(co[axis] for co in coords) for axis in range(3)]
    hi = [max(co[axis] for co in coords) for axis in range(3)]
    for vert in base.data.vertices:
        vert.co.x = (vert.co.x - (lo[0] + hi[0]) / 2) * (.30 / (hi[0] - lo[0]))
        vert.co.y = (vert.co.y - (lo[1] + hi[1]) / 2) * (.30 / (hi[1] - lo[1]))
        vert.co.z = (vert.co.z - lo[2]) * (.06 / (hi[2] - lo[2]))
    base.data.update()
    return body, bow, base


def bind_bow(arm, bow):
    group = bow.vertex_groups.new(name="weapon")
    group.add(list(range(len(bow.data.vertices))), 1.0, "REPLACE")
    bow.parent = arm
    modifier = bow.modifiers.new("Armature", "ARMATURE")
    modifier.object = arm


def setup_preview():
    world = bpy.data.worlds.new("Medusa_Preview_World")
    bpy.context.scene.world = world
    world.use_nodes = True
    world.node_tree.nodes["Background"].inputs["Color"].default_value = (.11, .12, .14, 1)
    world.node_tree.nodes["Background"].inputs["Strength"].default_value = .6
    camera_data = bpy.data.cameras.new("Medusa_Preview_Camera")
    camera = bpy.data.objects.new("Medusa_Preview_Camera", camera_data)
    bpy.context.collection.objects.link(camera)
    camera.location = (0, -1.5, .34)
    target = Vector((0, 0, .31))
    camera.rotation_euler = (target - camera.location).to_track_quat("-Z", "Y").to_euler()
    camera_data.type = "ORTHO"
    camera_data.ortho_scale = .72
    bpy.context.scene.camera = camera
    for name, location, energy in (("Key", (-.65, -.5, .9), 220), ("Fill", (.65, -.2, .7), 130)):
        data = bpy.data.lights.new(name, "AREA")
        data.energy = energy
        data.shape = "DISK"
        data.size = .7
        light = bpy.data.objects.new(name, data)
        bpy.context.collection.objects.link(light)
        light.location = location
        light.rotation_euler = (target - light.location).to_track_quat("-Z", "Y").to_euler()
    scene = bpy.context.scene
    scene.render.engine = "BLENDER_EEVEE"
    scene.render.resolution_x = scene.render.resolution_y = 1024
    scene.render.resolution_percentage = 100
    scene.render.image_settings.file_format = "PNG"
    scene.render.film_transparent = False
    scene.render.image_settings.color_mode = "RGBA"
    scene.view_settings.view_transform = "AgX"


def render_previews(arm, clips):
    frames = {"Idle": 29, "LungeAttack": 10, "HitReact": 4, "DeathSettle": 22}
    for name, frame in frames.items():
        reset_pose(arm)
        arm.animation_data.action = clips["AM_Medusa_" + name]
        bpy.context.scene.frame_set(frame)
        bpy.context.scene.render.filepath = str(PREVIEW / f"segmented-{name}.png")
        bpy.ops.render.render(write_still=True)
    reset_pose(arm)
    arm.animation_data.action = clips["AM_Medusa_Idle"]
    bpy.context.scene.frame_set(1)


def scale_action_locations(factor):
    for action in bpy.data.actions:
        for layer in action.layers:
            for strip in layer.strips:
                for bag in strip.channelbags:
                    for curve in bag.fcurves:
                        if not curve.data_path.endswith(".location"):
                            continue
                        for point in curve.keyframe_points:
                            point.co[1] *= factor
                            point.handle_left[1] *= factor
                            point.handle_right[1] *= factor


def scale_for_fbx(arm, meshes, factor):
    bpy.context.view_layer.objects.active = arm
    bpy.ops.object.mode_set(mode="EDIT")
    for bone in arm.data.edit_bones:
        bone.head *= factor
        bone.tail *= factor
    bpy.ops.object.mode_set(mode="OBJECT")
    for mesh in meshes:
        mesh.data.transform(Matrix.Scale(factor, 4))
    scale_action_locations(factor)


def patch_fbx_units(path):
    buf = bytearray(path.read_bytes())
    i = buf.find(b"UnitScaleFactor")
    assert i >= 0, path
    j = buf.find(b"double", i)
    k = buf.find(b"Number", j)
    length = struct.unpack_from("<I", buf, k - 4)[0]
    p = k + length
    assert buf[p:p + 1] == b"S"
    string_length = struct.unpack_from("<I", buf, p + 1)[0]
    p += 1 + 4 + string_length
    assert buf[p:p + 1] == b"D"
    struct.pack_into("<d", buf, p + 1, 1.0)
    path.write_bytes(buf)


def export_fbx(path, arm, meshes, animation):
    bpy.ops.object.select_all(action="DESELECT")
    arm.select_set(True)
    for mesh in meshes:
        mesh.select_set(True)
    bpy.context.view_layer.objects.active = arm
    bpy.ops.export_scene.fbx(
        filepath=str(path), use_selection=True,
        object_types={"ARMATURE", "MESH"},
        apply_unit_scale=True, apply_scale_options="FBX_SCALE_UNITS",
        axis_forward="-Y", axis_up="Z", add_leaf_bones=False,
        bake_anim=animation, bake_anim_use_nla_strips=False,
        bake_anim_use_all_actions=False, bake_anim_force_startend_keying=True,
        mesh_smooth_type="FACE", path_mode="AUTO", embed_textures=False,
    )
    patch_fbx_units(path)


def export_base(path, base):
    bpy.ops.object.select_all(action="DESELECT")
    base.select_set(True)
    bpy.context.view_layer.objects.active = base
    bpy.ops.export_scene.fbx(filepath=str(path), use_selection=True, object_types={"MESH"},
                             apply_unit_scale=True, apply_scale_options="FBX_SCALE_UNITS",
                             axis_forward="-Y", axis_up="Z", bake_anim=False,
                             add_leaf_bones=False, mesh_smooth_type="FACE",
                             path_mode="AUTO", embed_textures=False)
    patch_fbx_units(path)


def main():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    parts = prepare_parts()
    body, bow, base = join_body(parts)
    arm = make_armature()
    weights = bind_mesh(arm, body)
    bind_bow(arm, bow)
    clips = actions_for(arm)
    reset_pose(arm)
    arm.animation_data.action = clips["AM_Medusa_Idle"]
    bpy.context.scene.frame_set(1)
    bpy.context.scene.render.fps = 24
    bpy.context.scene.unit_settings.system = "METRIC"
    bpy.context.scene.unit_settings.scale_length = 1.0
    setup_preview()
    bpy.data.orphans_purge(do_recursive=True)
    bpy.ops.wm.save_as_mainfile(filepath=str(ROOT / "medusa.blend"))
    render_previews(arm, clips)

    report = {
        "source": str(SOURCE.relative_to(ROOT)),
        "height_m": .55,
        "triangles": {obj.name: sum(len(face.vertices) - 2 for face in obj.data.polygons)
                      for obj in (body, bow, base)},
        "vertices": {obj.name: len(obj.data.vertices) for obj in (body, bow, base)},
        "materials": {obj.name: [material.name for material in obj.data.materials]
                      for obj in (body, bow, base)},
        "uv_layers": list(body.data.uv_layers.keys()),
        "textures": ATLAS["files"],
        "bones": [bone.name for bone in arm.data.bones],
        "weights": weights,
        "clips": {name: [int(action.frame_range[0]), int(action.frame_range[1])]
                  for name, action in clips.items()},
    }
    (ROOT / "build-report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    scale_for_fbx(arm, (body, bow, base), 100)
    arm.animation_data.action = None
    export_fbx(EXPORT / "SK_Medusa.fbx", arm, (body, bow), False)
    export_base(EXPORT / "SM_Medusa_Base.fbx", base)
    for name, action in clips.items():
        reset_pose(arm)
        arm.animation_data.action = action
        bpy.context.scene.frame_start, bpy.context.scene.frame_end = report["clips"][name]
        bpy.context.scene.frame_set(bpy.context.scene.frame_start)
        export_fbx(EXPORT / f"{name}.fbx", arm, (body, bow), True)
    print("MEDUSA_BUILD_REPORT", json.dumps(report, ensure_ascii=False))


main()
