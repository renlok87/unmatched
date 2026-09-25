"""S05 deterministic asset build. Run: blender --background --factory-startup --python build_medusa.py

Builds ART-001 check items (direction arrow, skeletal mannequin with 1 m root-motion clip)
and the S05 early visual reference set: SK_Medusa + 4 clips, cobble tile, table base,
lantern, facade, team bases, selection ring, target reticle. All geometry is generated from
code with a fixed seed; no manual .blend editing is involved.
Conventions per 04-blender-production.md: metric 1 unit = 1 m, cell = 1 m, forward -Y,
Z up, pivot bottom-center, transforms applied, triangulated FBX.
"""
import bpy
import bmesh
import math
import random
from mathutils import Vector, Matrix
from pathlib import Path

BLEND_DIR = Path(__file__).resolve().parent
OUT = BLEND_DIR / 'export'
OUT.mkdir(parents=True, exist_ok=True)

random.seed(20260925)
FPS = 24
EXPORT_COMMON = dict(
    object_types={'MESH', 'ARMATURE'},
    apply_unit_scale=True,
    # Unit truth (measured 2026-09-25): with these options the exporter writes RAW Blender
    # numbers (an arrow authored at 0.33m leaves the file as 0.33) and declares
    # UnitScaleFactor=100. UE multiplies every FBX number by the file UnitScaleFactor on
    # import, both for geometry and bones - and puts that x100 factor on skeleton bone 0,
    # which root-motion consumption applies a SECOND time (a 100uu clip moved the probe
    # 10000uu). Fix: bake x100 into the data before export (scale_rig_units +
    # scale_objects_units) and patch UnitScaleFactor to 1.0 in every file
    # (patch_fbx_unit_scale): all numbers are cm and land 1:1 as uu, bone-0 scale is 1,
    # root motion is exactly 100uu. The saved .blend stays in meters (the scale is undone).
    apply_scale_options='FBX_SCALE_UNITS',
    axis_forward='-Y',
    axis_up='Z',
    bake_anim=False,
    add_leaf_bones=False,
    mesh_smooth_type='FACE',
)

# ---------------------------------------------------------------- helpers

def wipe_scene():
    bpy.ops.object.select_all(action='SELECT')
    bpy.ops.object.delete(use_global=False)
    for block in (bpy.data.meshes, bpy.data.materials, bpy.data.armatures, bpy.data.actions):
        for item in list(block):
            if item.users == 0:
                block.remove(item)
    scene = bpy.context.scene
    scene.unit_settings.system = 'METRIC'
    scene.unit_settings.scale_length = 1.0
    scene.render.fps = FPS

def make_mat(name, rgb, roughness=0.9, metallic=0.0):
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    bsdf = mat.node_tree.nodes['Principled BSDF']
    bsdf.inputs['Base Color'].default_value = (*rgb, 1.0)
    bsdf.inputs['Roughness'].default_value = roughness
    bsdf.inputs['Metallic'].default_value = metallic
    return mat

def make_emit_mat(name, rgb, strength):
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    emit = mat.node_tree.nodes.new('ShaderNodeEmission')
    emit.inputs['Color'].default_value = (*rgb, 1.0)
    emit.inputs['Strength'].default_value = strength
    out = mat.node_tree.nodes['Material Output']
    mat.node_tree.links.new(emit.outputs['Emission'], out.inputs['Surface'])
    return mat

def place(name, mat, loc):
    mesh = bpy.data.meshes.new(name)
    obj = bpy.data.objects.new(name, mesh)
    obj.location = loc
    bpy.context.collection.objects.link(obj)
    if mat:
        obj.data.materials.append(mat)
    return obj

def finish_obj(obj):
    """Apply rot/scale, keep geometry positions, origin at world (0,0,0)."""
    bpy.context.scene.cursor.location = (0, 0, 0)
    bpy.ops.object.select_all(action='DESELECT')
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj
    bpy.ops.object.origin_set(type='ORIGIN_CURSOR')
    bpy.ops.object.transform_apply(location=False, rotation=True, scale=True)

def smart_uv(obj):
    bpy.ops.object.select_all(action='DESELECT')
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj
    bpy.ops.object.mode_set(mode='EDIT')
    bpy.ops.mesh.select_all(action='SELECT')
    bpy.ops.uv.smart_project(angle_limit=math.radians(66.0), island_margin=0.02)
    bpy.ops.object.mode_set(mode='OBJECT')

def join(parts, name):
    bpy.context.scene.cursor.location = (0, 0, 0)
    for obj in bpy.data.objects:
        obj.select_set(obj in parts)
    bpy.context.view_layer.objects.active = parts[0]
    bpy.ops.object.join()
    result = bpy.context.active_object
    result.name = name
    result.data.name = name
    bpy.ops.object.select_all(action='DESELECT')
    result.select_set(True)
    bpy.context.view_layer.objects.active = result
    bpy.ops.object.origin_set(type='ORIGIN_CURSOR')
    return result

def export_fbx(path, objects):
    for obj in bpy.data.objects:
        obj.select_set(obj in objects)
    bpy.ops.export_scene.fbx(filepath=str(path), use_selection=True, **EXPORT_COMMON)

def export_anim_fbx(path, objects):
    # meshes must stay in clip FBX files: the UE legacy importer matches the target
    # skeleton via the FBX mesh node ("Нет сеток FBX" with armature-only exports);
    # the throwaway SkeletalMesh it spawns alongside is deleted by the import script
    for obj in bpy.data.objects:
        obj.select_set(obj in objects)
    bpy.ops.export_scene.fbx(filepath=str(path), use_selection=True,
                             object_types={'ARMATURE', 'MESH'},
                             apply_unit_scale=True, apply_scale_options='FBX_SCALE_UNITS',
                             axis_forward='-Y', axis_up='Z', bake_anim=True,
                             bake_anim_use_nla_strips=False, bake_anim_use_all_actions=False,
                             bake_anim_force_startend_keying=True,
                             add_leaf_bones=False, mesh_smooth_type='FACE')

def scale_rig_units(arms, factor):
    """Scale edit-bone rest positions and every keyed location channel by factor.
    Called with 100 before ALL exports and 0.01 after, so the .blend keeps meter authoring."""
    for arm in arms:
        bpy.context.view_layer.objects.active = arm
        bpy.ops.object.mode_set(mode='EDIT')
        for eb in arm.data.edit_bones:
            eb.head = eb.head * factor
            eb.tail = eb.tail * factor
        bpy.ops.object.mode_set(mode='OBJECT')
    for action in bpy.data.actions:
        fcurves = []
        if hasattr(action, 'fcurves'):          # pre-4.4 legacy actions
            fcurves = list(action.fcurves)
        else:                                   # slotted actions (Blender 4.4+)
            for layer in action.layers:
                for strip in layer.strips:
                    for bag in strip.channelbags:
                        fcurves.extend(bag.fcurves)
        for fc in fcurves:
            if fc.data_path == 'location' or fc.data_path.endswith('.location'):
                for kp in fc.keyframe_points:
                    kp.co[1] *= factor
                    kp.handle_left[1] *= factor
                    kp.handle_right[1] *= factor

def scale_objects_units(objects, factor):
    """Bake factor into vertex data and object locations of every exported object.
    The FBX exporter writes RAW Blender numbers (no unit bake: the arrow authored at
    0.33m leaves as 0.33 with UnitScaleFactor=100), and UE multiplies every number by
    the file UnitScaleFactor on import. Scaling the data x100 and patching USF to 1.0
    makes every FBX number land 1:1 as uu in UE while the saved .blend stays in meters."""
    mat = Matrix.Scale(factor, 4)
    for obj in objects:
        obj.location = obj.location * factor
        if obj.type == 'MESH':
            obj.data.transform(mat)

def patch_fbx_unit_scale(path):
    """Set the binary FBX UnitScaleFactor to 1.0 in place. UE Interchange derives the
    skeleton bone-0 unit factor from it, so a file carrying cm-numbered bones and
    geometry must declare plain cm units instead of the Blender default x100."""
    import struct
    buf = bytearray(path.read_bytes())
    i = buf.find(b'UnitScaleFactor')
    assert i >= 0, 'no UnitScaleFactor in %s' % path.name
    j = buf.find(b'double', i)
    k = buf.find(b'Number', j)
    ln = struct.unpack_from('<I', buf, k - 4)[0]
    q = k - 4 + 4 + ln
    assert buf[q:q + 1] == b'S', 'unexpected prop layout in %s' % path.name
    qln = struct.unpack_from('<I', buf, q + 1)[0]
    q += 1 + 4 + qln
    assert buf[q:q + 1] == b'D', 'unexpected prop layout in %s' % path.name
    old = struct.unpack_from('<d', buf, q + 1)[0]
    struct.pack_into('<d', buf, q + 1, 1.0)
    path.write_bytes(buf)
    print('S05_USF_PATCH %s %g -> 1.0' % (path.name, old))

def tri_count(obj):
    return sum(len(p.vertices) - 2 for p in obj.data.polygons)

def capsule(name, mat, p_from, p_to, radius, segments=12):
    """Capsule: cylinder + two sphere caps, stretched between two points."""
    center = (p_from + p_to) * 0.5
    length = (p_to - p_from).length
    obj = place(name, mat, center)
    bm = bmesh.new()
    bmesh.ops.create_cone(bm, cap_ends=True, cap_tris=False, segments=segments,
                          radius1=radius, radius2=radius, depth=length)
    bm.to_mesh(obj.data)
    bm.free()
    obj.rotation_euler = (p_to - p_from).to_track_quat('Z', 'Y').to_euler()
    cap_a = sphere(name + '_capA', mat, p_from, radius, segments)
    cap_b = sphere(name + '_capB', mat, p_to, radius, segments)
    return [obj, cap_a, cap_b]

def cone(name, mat, base_center, tip, radius, segments=12):
    direction = tip - base_center
    obj = place(name, mat, base_center + direction / 2)
    bm = bmesh.new()
    bmesh.ops.create_cone(bm, cap_ends=True, cap_tris=False, segments=segments,
                          radius1=radius, radius2=0.0, depth=direction.length)
    bm.to_mesh(obj.data)
    bm.free()
    obj.rotation_euler = direction.to_track_quat('Z', 'Y').to_euler()
    return obj

def sphere(name, mat, center, radius, segments=16):
    obj = place(name, mat, center)
    bm = bmesh.new()
    bmesh.ops.create_uvsphere(bm, u_segments=segments, v_segments=max(6, segments // 2 + 2), radius=radius)
    bm.to_mesh(obj.data)
    bm.free()
    return obj

def cylinder(name, mat, bottom_center, height, radius, segments=16, radius_top=None):
    obj = place(name, mat, bottom_center + Vector((0, 0, height / 2)))
    bm = bmesh.new()
    bmesh.ops.create_cone(bm, cap_ends=True, cap_tris=False, segments=segments,
                          radius1=radius, radius2=radius if radius_top is None else radius_top, depth=height)
    bm.to_mesh(obj.data)
    bm.free()
    return obj

def torus_ring(name, mat, center, major_radius, tube_radius, start_deg, arc_deg):
    """Torus arc in the XY plane (axis Z); tube cross-section spans radial+Z so the ring has real thickness."""
    verts = []
    faces = []
    ring_segments = max(6, int(arc_deg / 6.0))
    tube_segments = 8
    for i in range(ring_segments + 1):
        angle = math.radians(start_deg + arc_deg * i / ring_segments)
        ring_center = Vector((center.x + major_radius * math.cos(angle),
                              center.y + major_radius * math.sin(angle), center.z))
        radial = Vector((math.cos(angle), math.sin(angle), 0))
        for j in range(tube_segments):
            phi = 2 * math.pi * j / tube_segments
            offset = radial * (tube_radius * math.cos(phi)) + Vector((0, 0, tube_radius * math.sin(phi)))
            verts.append(ring_center + offset)
    for i in range(ring_segments):
        for j in range(tube_segments):
            a = i * tube_segments + j
            b = i * tube_segments + (j + 1) % tube_segments
            c = (i + 1) * tube_segments + (j + 1) % tube_segments
            d = (i + 1) * tube_segments + j
            faces.append((a, b, c, d))
    mesh = bpy.data.meshes.new(name)
    mesh.from_pydata(verts, [], faces)
    mesh.validate()
    obj = bpy.data.objects.new(name, mesh)
    obj.location = (0, 0, 0)
    bpy.context.collection.objects.link(obj)
    if mat:
        obj.data.materials.append(mat)
    return obj

def cylinder_between(name, mat, p_from, p_to, radius, segments=12):
    obj = place(name, mat, (p_from + p_to) / 2)
    bm = bmesh.new()
    bmesh.ops.create_cone(bm, cap_ends=True, cap_tris=False, segments=segments,
                          radius1=radius, radius2=radius, depth=(p_to - p_from).length)
    bm.to_mesh(obj.data)
    bm.free()
    obj.rotation_euler = (p_to - p_from).to_track_quat('Z', 'Y').to_euler()
    return obj

# ---------------------------------------------------------------- ART-001 direction arrow

def build_arrow():
    """Asymmetric arrow ~0.72 m long, tip toward -Y, top marker toward +Z.

    Pre-rotated +90 deg around Z before export: the Blender 5.2.2 -> UE 5.8 legacy
    static FBX path maps y_bl -> -y_ue and ignores force_front_x_axis/import_rotation,
    so a -Y tip lands on UE +Y. The pre-rotation moves the tip to +X_bl, which
    survives the importer as +X_ue (ART-001 orientation check; see Q-311).
    """
    mat = make_mat('M_S05_Check', (0.85, 0.55, 0.15), roughness=0.8)
    z = 0.02
    parts = [cylinder_between('ArrowShaft', mat, Vector((0, 0.39, z)), Vector((0, 0.02, z)), 0.024)]
    parts.append(cone('ArrowHead', mat, Vector((0, -0.13, z)), Vector((0, -0.33, z)), 0.08))
    for side in (1, -1):
        parts.append(cylinder_between('Fin%d' % side, mat, Vector((0.02 * side, 0.30, z)),
                                      Vector((0.085 * side, 0.36, z)), 0.018, segments=4))
    marker = place('TopMark', mat, (0.10, 0.30, z + 0.045))
    bm = bmesh.new()
    bmesh.ops.create_cube(bm, size=0.05)
    bm.to_mesh(marker.data)
    bm.free()
    parts.append(marker)
    arrow = join(parts, 'SM_S05_Arrow')
    finish_obj(arrow)
    arrow.rotation_euler = (0.0, 0.0, math.radians(90.0))
    finish_obj(arrow)
    smart_uv(arrow)
    return arrow

# ---------------------------------------------------------------- skeleton

def make_armature(name, bone_defs):
    """bone_defs: list of (name, parent, head Vector, tail Vector)."""
    arm_data = bpy.data.armatures.new(name)
    arm = bpy.data.objects.new(name, arm_data)
    bpy.context.collection.objects.link(arm)
    bpy.context.view_layer.objects.active = arm
    bpy.ops.object.mode_set(mode='EDIT')
    for bone_name, parent, head, tail in bone_defs:
        eb = arm_data.edit_bones.new(bone_name)
        eb.head = head
        eb.tail = tail
        eb.roll = 0.0
        if parent:
            eb.parent = arm_data.edit_bones[parent]
            eb.use_connect = False
    bpy.ops.object.mode_set(mode='OBJECT')
    for pb in arm.pose.bones:
        pb.rotation_mode = 'XYZ'
    return arm

def bind_auto(arm, mesh_obj):
    bpy.ops.object.select_all(action='DESELECT')
    mesh_obj.select_set(True)
    arm.select_set(True)
    bpy.context.view_layer.objects.active = arm
    bpy.ops.object.parent_set(type='ARMATURE_AUTO')

def bind_rigid(arm, mesh_obj, bone_name):
    bpy.ops.object.select_all(action='DESELECT')
    mesh_obj.select_set(True)
    arm.select_set(True)
    bpy.context.view_layer.objects.active = arm
    bpy.ops.object.parent_set(type='ARMATURE')
    vg = mesh_obj.vertex_groups.get(bone_name) or mesh_obj.vertex_groups.new(name=bone_name)
    vg.add([v.index for v in mesh_obj.data.vertices], 1.0, 'REPLACE')
    for group in list(mesh_obj.vertex_groups):
        if group.name != bone_name:
            mesh_obj.vertex_groups.remove(group)

def key(arm, action_name, frames):
    action = bpy.data.actions.new(action_name)
    if arm.animation_data is None:
        arm.animation_data_create()
    arm.animation_data.action = action
    for frame in sorted(frames):
        bpy.context.scene.frame_set(frame)
        for bone, channels in frames[frame].items():
            if bone == '@armature':
                # Object-level keys: the UE legacy importer turns the FBX armature-object node
                # into skeleton bone 0 and UE root-motion extraction reads bone 0 only.
                for channel, value in channels.items():
                    setattr(arm, channel, value)
                    arm.keyframe_insert(data_path=channel, frame=frame)
                continue
            pb = arm.pose.bones.get(bone)
            if pb is None:
                raise RuntimeError('missing bone %s for action %s' % (bone, action_name))
            for channel, value in channels.items():
                setattr(pb, channel, value)
                pb.keyframe_insert(data_path=channel, frame=frame)
    return action

# ---------------------------------------------------------------- ART-001 mannequin + root motion

def build_mannequin():
    mat_body = make_mat('M_S05_Mannequin', (0.62, 0.62, 0.62), roughness=0.85)
    parts = [cylinder('ManqTorso', mat_body, Vector((0, 0, 0.10)), 0.22, 0.07, radius_top=0.06),
             sphere('ManqHead', mat_body, Vector((0, 0, 0.40)), 0.05)]
    parts.extend(capsule('ManqArmL', mat_body, Vector((-0.09, 0, 0.30)), Vector((-0.17, 0, 0.14)), 0.016))
    parts.extend(capsule('ManqArmR', mat_body, Vector((0.09, 0, 0.30)), Vector((0.18, 0, 0.20)), 0.016))
    parts.append(cylinder('ManqLegs', mat_body, Vector((0, 0, 0.0)), 0.10, 0.05))
    parts.append(cylinder('ManqBase', mat_body, Vector((0, 0, 0)), 0.02, 0.12))
    body = join(parts, 'Mannequin_Body')
    finish_obj(body)
    smart_uv(body)
    bones = [
        ('root', None, Vector((0, 0, 0)), Vector((0, 0, 0.08))),
        ('hips', 'root', Vector((0, 0, 0.14)), Vector((0, 0, 0.24))),
        ('spine', 'hips', Vector((0, 0, 0.24)), Vector((0, 0, 0.34))),
        ('head', 'spine', Vector((0, 0, 0.34)), Vector((0, 0, 0.44))),
        ('arm_upper.L', 'spine', Vector((-0.09, 0, 0.30)), Vector((-0.17, 0, 0.14))),
        ('arm_lower.L', 'arm_upper.L', Vector((-0.17, 0, 0.14)), Vector((-0.17, -0.02, 0.05))),
        ('hand.L', 'arm_lower.L', Vector((-0.17, -0.02, 0.05)), Vector((-0.17, -0.02, 0.01))),
        ('arm_upper.R', 'spine', Vector((0.09, 0, 0.30)), Vector((0.18, 0, 0.20))),
        ('arm_lower.R', 'arm_upper.R', Vector((0.18, 0, 0.20)), Vector((0.18, -0.01, 0.28))),
        ('hand.R', 'arm_lower.R', Vector((0.18, -0.01, 0.28)), Vector((0.18, -0.01, 0.33))),
        ('leg_upper.L', 'hips', Vector((-0.03, 0, 0.14)), Vector((-0.035, 0, 0.06))),
        ('leg_lower.L', 'leg_upper.L', Vector((-0.035, 0, 0.06)), Vector((-0.04, 0, 0.02))),
        ('foot.L', 'leg_lower.L', Vector((-0.04, 0, 0.02)), Vector((-0.04, -0.02, 0.01))),
        ('leg_upper.R', 'hips', Vector((0.03, 0, 0.14)), Vector((0.035, 0, 0.06))),
        ('leg_lower.R', 'leg_upper.R', Vector((0.035, 0, 0.06)), Vector((0.04, 0, 0.02))),
        ('foot.R', 'leg_lower.R', Vector((0.04, 0, 0.02)), Vector((0.04, -0.02, 0.01))),
        ('weapon', 'hand.L', Vector((-0.17, -0.02, 0.05)), Vector((-0.17, -0.06, 0.05))),
    ]
    arm = make_armature('SKEL_S05_Mannequin', bones)
    bind_auto(arm, body)
    # The 1 m displacement must live on the armature OBJECT, not the 'root' pose bone: the UE
    # legacy importer maps the FBX armature-object node to skeleton bone 0 ('skel_s05_mannequin')
    # and root-motion extraction reads bone 0 only (animating the 'root' pose bone measured
    # delta=0.00 in the 2026-09-25 packaged run).
    frames = {
        1: {'@armature': {'location': (0, 0, 0)}, 'arm_upper.R': {'rotation_euler': (0, 0, 0)}},
        15: {'@armature': {'location': (0, -0.5, 0)}, 'arm_upper.R': {'rotation_euler': (0, math.radians(-60), 0)}},
        30: {'@armature': {'location': (0, -1.0, 0)}, 'arm_upper.R': {'rotation_euler': (0, math.radians(-100), 0)}},
    }
    rm_test = key(arm, 'RM_Test', frames)
    return arm, body, rm_test

# ---------------------------------------------------------------- Medusa

SNAKE_COUNT = 6

def build_medusa():
    mat_body = make_mat('M_S05_Body', (0.28, 0.33, 0.28), roughness=0.9)
    mat_accent = make_mat('M_S05_Accent', (0.45, 0.32, 0.18), roughness=0.55, metallic=0.25)
    mat_base = make_mat('M_S05_Base', (0.75, 0.72, 0.66), roughness=0.8)
    shoulder_l = Vector((-0.062, -0.02, 0.355))
    elbow_l = Vector((-0.075, -0.09, 0.30))
    hand_l = Vector((-0.05, -0.160, 0.315))
    shoulder_r = Vector((0.062, -0.02, 0.355))
    elbow_r = Vector((0.088, -0.06, 0.30))
    hand_r = Vector((0.055, -0.10, 0.325))
    parts = [
        cylinder('MedGown', mat_body, Vector((0, 0, 0.06)), 0.20, 0.145, radius_top=0.085),
        cylinder('MedTorso', mat_body, Vector((0, 0, 0.26)), 0.11, 0.082, radius_top=0.070),
        sphere('MedChest', mat_body, Vector((0, 0, 0.365)), 0.062),
        sphere('MedHead', mat_body, Vector((0, 0.004, 0.450)), 0.048, segments=20),
        cylinder('MedBelt', mat_accent, Vector((0, 0, 0.255)), 0.014, 0.086),
    ]
    # Snake crown: readable "crown" silhouette, not detailed snakes (04 §3.1) — the 2026-09-25
    # review could not recognize Medusa in K2, so the crown is wider and taller than v1.
    for i in range(SNAKE_COUNT):
        angle = 2 * math.pi * i / SNAKE_COUNT + math.pi / 6
        dir_out = Vector((math.cos(angle), math.sin(angle), 0))
        base = Vector((0, 0.004, 0.450)) + dir_out * 0.033 + Vector((0, 0, 0.024))
        tip = base + dir_out * 0.062 + Vector((0, 0, 0.062))
        parts.append(cone('MedSnake%d' % i, mat_body, base, tip, 0.0125, segments=8))
        parts.append(sphere('MedSnakeHead%d' % i, mat_body, tip, 0.014, segments=10))
    parts.extend(capsule('MedArmL', mat_body, shoulder_l, elbow_l, 0.015))
    parts.extend(capsule('MedForeL', mat_body, elbow_l, hand_l, 0.013))
    parts.extend(capsule('MedArmR', mat_body, shoulder_r, elbow_r, 0.015))
    parts.extend(capsule('MedForeR', mat_body, elbow_r, hand_r, 0.013))
    parts.append(sphere('MedHandL', mat_body, hand_l, 0.02, segments=12))
    parts.append(sphere('MedHandR', mat_body, hand_r, 0.02, segments=12))
    body = join(parts, 'Medusa_Body')
    finish_obj(body)
    smart_uv(body)
    # bow: arc in XZ plane (opens along -Y), string, arrow; weapon oversized per C-1
    # (x1.2-1.4 of "realistic") so the bow reads in the K2 silhouette.
    bow_parts = []
    center_bow = hand_l + Vector((0, -0.01, 0))
    arc = torus_ring('MedBowArc', mat_accent, Vector((0, 0, 0)), 0.19, 0.008, -100, 200)
    arc.rotation_euler = (math.radians(90), 0, 0)
    arc.location = center_bow
    bow_parts.append(arc)
    string_a = center_bow + Vector((0.187, 0, 0))
    string_b = center_bow - Vector((0.187, 0, 0))
    string = place('MedBowString', mat_accent, (string_a + string_b) / 2)
    bm = bmesh.new()
    bmesh.ops.create_cone(bm, cap_ends=True, cap_tris=False, segments=6,
                          radius1=0.0024, radius2=0.0024, depth=(string_b - string_a).length)
    bm.to_mesh(string.data)
    bm.free()
    string.rotation_euler = (string_b - string_a).to_track_quat('Z', 'Y').to_euler()
    bow_parts.append(string)
    shaft = place('MedArrowShaft', mat_accent, center_bow)
    bm = bmesh.new()
    bmesh.ops.create_cone(bm, cap_ends=True, cap_tris=False, segments=6,
                          radius1=0.0045, radius2=0.0045, depth=0.34)
    bm.to_mesh(shaft.data)
    bm.free()
    shaft.rotation_euler = (math.radians(90), 0, 0)
    bow_parts.append(shaft)
    bow_parts.append(cone('MedArrowTip', mat_accent, center_bow + Vector((0, -0.17, 0)),
                          center_bow + Vector((0, -0.215, 0)), 0.010, segments=8))
    bow = join(bow_parts, 'Medusa_Bow')
    finish_obj(bow)
    smart_uv(bow)
    base = cylinder('Medusa_Base', mat_base, Vector((0, 0, 0)), 0.06, 0.15, segments=24)
    finish_obj(base)
    smart_uv(base)
    bones = [
        ('root', None, Vector((0, 0, 0)), Vector((0, 0, 0.08))),
        ('hips', 'root', Vector((0, 0, 0.20)), Vector((0, 0, 0.26))),
        ('spine', 'hips', Vector((0, 0, 0.26)), Vector((0, 0, 0.36))),
        ('head', 'spine', Vector((0, 0.004, 0.42)), Vector((0, 0.004, 0.50))),
        ('arm_upper.L', 'spine', shoulder_l.copy(), elbow_l.copy()),
        ('arm_lower.L', 'arm_upper.L', elbow_l.copy(), hand_l.copy()),
        ('hand.L', 'arm_lower.L', hand_l.copy(), hand_l + Vector((0, -0.03, 0))),
        ('arm_upper.R', 'spine', shoulder_r.copy(), elbow_r.copy()),
        ('arm_lower.R', 'arm_upper.R', elbow_r.copy(), hand_r.copy()),
        ('hand.R', 'arm_lower.R', hand_r.copy(), hand_r + Vector((0, -0.03, 0))),
        ('leg_upper.L', 'hips', Vector((-0.03, 0, 0.20)), Vector((-0.035, 0, 0.10))),
        ('leg_lower.L', 'leg_upper.L', Vector((-0.035, 0, 0.10)), Vector((-0.04, 0, 0.03))),
        ('foot.L', 'leg_lower.L', Vector((-0.04, 0, 0.03)), Vector((-0.04, -0.02, 0.01))),
        ('leg_upper.R', 'hips', Vector((0.03, 0, 0.20)), Vector((0.035, 0, 0.10))),
        ('leg_lower.R', 'leg_upper.R', Vector((0.035, 0, 0.10)), Vector((0.04, 0, 0.03))),
        ('foot.R', 'leg_lower.R', Vector((0.04, 0, 0.03)), Vector((0.04, -0.02, 0.01))),
        ('weapon', 'hand.L', hand_l.copy(), hand_l + Vector((0, -0.08, 0))),
    ]
    arm = make_armature('SKEL_S05_Medusa', bones)
    bind_auto(arm, body)
    bind_rigid(arm, bow, 'hand.L')
    bind_rigid(arm, base, 'root')
    # clips: all start from the modeled rest pose; no root motion on figure clips
    clips = {}
    clips['AM_Medusa_Idle'] = key(arm, 'Idle', {
        1: {'spine': {'rotation_euler': (0, 0, 0)}, 'head': {'rotation_euler': (0, 0, 0)}},
        29: {'spine': {'rotation_euler': (math.radians(2.5), 0, 0)}, 'head': {'rotation_euler': (math.radians(-3), 0, 0)}},
        57: {'spine': {'rotation_euler': (0, 0, 0)}, 'head': {'rotation_euler': (0, 0, 0)}},
    })
    clips['AM_Medusa_LungeAttack'] = key(arm, 'LungeAttack', {
        1: {'spine': {'rotation_euler': (0, 0, 0)}, 'head': {'rotation_euler': (0, 0, 0)},
            'arm_upper.L': {'rotation_euler': (0, 0, 0)}, 'arm_upper.R': {'rotation_euler': (0, 0, 0)}},
        7: {'spine': {'rotation_euler': (math.radians(12), 0, 0)}, 'head': {'rotation_euler': (math.radians(-8), 0, 0)},
            'arm_upper.L': {'rotation_euler': (math.radians(8), math.radians(15), 0)},
            'arm_upper.R': {'rotation_euler': (0, math.radians(-25), 0)}},
        11: {'spine': {'rotation_euler': (math.radians(12), 0, 0)}, 'head': {'rotation_euler': (math.radians(-8), 0, 0)},
             'arm_upper.L': {'rotation_euler': (math.radians(8), math.radians(15), 0)},
             'arm_upper.R': {'rotation_euler': (0, math.radians(-35), 0)}},
        15: {'spine': {'rotation_euler': (0, 0, 0)}, 'head': {'rotation_euler': (0, 0, 0)},
             'arm_upper.L': {'rotation_euler': (0, 0, 0)}, 'arm_upper.R': {'rotation_euler': (0, 0, 0)}},
    })
    clips['AM_Medusa_HitReact'] = key(arm, 'HitReact', {
        1: {'spine': {'rotation_euler': (0, 0, 0)}, 'head': {'rotation_euler': (0, 0, 0)}},
        4: {'spine': {'rotation_euler': (math.radians(-10), 0, 0)}, 'head': {'rotation_euler': (math.radians(-10), 0, 0)}},
        10: {'spine': {'rotation_euler': (0, 0, 0)}, 'head': {'rotation_euler': (0, 0, 0)}},
    })
    clips['AM_Medusa_DeathSettle'] = key(arm, 'DeathSettle', {
        1: {'hips': {'location': (0, 0, 0)}, 'spine': {'rotation_euler': (0, 0, 0)}},
        12: {'hips': {'location': (0, 0, -0.08)}, 'spine': {'rotation_euler': (math.radians(25), 0, 0)},
             'head': {'rotation_euler': (math.radians(20), 0, 0)}},
        22: {'hips': {'location': (0, 0, -0.13)}, 'spine': {'rotation_euler': (math.radians(48), 0, 0)},
             'head': {'rotation_euler': (math.radians(25), 0, 0)}},
    })
    return arm, body, bow, base, clips

# ---------------------------------------------------------------- board set

def build_tile():
    """Playable cell plate 0.94 m: the 6 cm gap between plates reads as a dark seam over the
    tray stone, making cell boundaries legible without zoom (2026-09-25 review: 4x4 cobbles
    per cell hid the 5x6 grid). 3x3 cobbles per cell = 270 on the board."""
    mat = make_mat('M_S05_Cobble', (0.32, 0.35, 0.40), roughness=0.92)
    mesh = bpy.data.meshes.new('SM_S05_CobbleTile')
    bm = bmesh.new()
    plate = bmesh.ops.create_cube(bm, size=1.0)
    bmesh.ops.scale(bm, verts=plate['verts'], vec=(0.94, 0.94, 0.015))
    bmesh.ops.translate(bm, verts=plate['verts'], vec=(0, 0, 0.0075))
    grid = 3
    span = 0.94
    cell = span / grid
    for ix in range(grid):
        for iy in range(grid):
            cx = (ix + 0.5) * cell - span / 2
            cy = (iy + 0.5) * cell - span / 2
            half = cell * 0.42
            jitter = lambda: random.uniform(-0.006, 0.006)
            top = 0.026 + random.uniform(0.0, 0.006)
            bottom_corners = [(cx - half + jitter(), cy - half + jitter(), 0.008),
                              (cx + half + jitter(), cy - half + jitter(), 0.008),
                              (cx + half + jitter(), cy + half + jitter(), 0.008),
                              (cx - half + jitter(), cy + half + jitter(), 0.008)]
            shrink = half * 0.18
            top_corners = [(cx - half + shrink, cy - half + shrink, top),
                           (cx + half - shrink, cy - half + shrink, top),
                           (cx + half - shrink, cy + half - shrink, top),
                           (cx - half + shrink, cy + half - shrink, top)]
            vb = [bm.verts.new(c) for c in bottom_corners]
            vt = [bm.verts.new(c) for c in top_corners]
            bm.faces.new(vt)
            for i in range(4):
                bm.faces.new([vb[i], vb[(i + 1) % 4], vt[(i + 1) % 4], vt[i]])
            bm.faces.new(reversed(vb))
    bm.to_mesh(mesh)
    bm.free()
    obj = bpy.data.objects.new('SM_S05_CobbleTile', mesh)
    obj.location = (0, 0, 0)
    bpy.context.collection.objects.link(obj)
    obj.data.materials.append(mat)
    finish_obj(obj)
    smart_uv(obj)
    return obj

def build_table_base():
    mat = make_mat('M_S05_TrayStone', (0.13, 0.14, 0.17), roughness=0.95)
    mesh = bpy.data.meshes.new('SM_S05_TableBase')
    bm = bmesh.new()
    # 5x6 m board + 0.5 m rim (04-blender-production.md 3.6: rim 0.4-0.6 m, thickness 0.3-0.5 m).
    # The 2026-09-25 build shipped 0.64x0.74x0.04 m — a x10 unit slip that left the board
    # floating in darkness with a stray dark cuboid in the frame.
    half_x, half_y, corner, thick = 2.95, 3.45, 0.45, 0.4
    steps = 64
    pts = []
    for i in range(steps):
        t = 2 * math.pi * i / steps
        rx = half_x - corner * (1 - abs(math.cos(t)))
        ry = half_y - corner * (1 - abs(math.sin(t)))
        r = 1.0 + random.uniform(-0.05, 0.05)
        pts.append(Vector((math.copysign(rx, math.cos(t)) * r, math.copysign(ry, math.sin(t)) * r, 0)))
    top_ring = [bm.verts.new((p.x, p.y, 0.0)) for p in pts]
    bottom_ring = [bm.verts.new((p.x, p.y, -thick)) for p in pts]
    bm.faces.new(top_ring)
    for i in range(steps):
        bm.faces.new([top_ring[i], top_ring[(i + 1) % steps], bottom_ring[(i + 1) % steps], bottom_ring[i]])
    bm.faces.new(list(reversed(bottom_ring)))
    bm.to_mesh(mesh)
    bm.free()
    obj = bpy.data.objects.new('SM_S05_TableBase', mesh)
    obj.location = (0, 0, 0)
    bpy.context.collection.objects.link(obj)
    obj.data.materials.append(mat)
    finish_obj(obj)
    smart_uv(obj)
    return obj

def build_lantern():
    mat_metal = make_mat('M_S05_LanternMetal', (0.20, 0.19, 0.17), roughness=0.6, metallic=0.4)
    mat_glow = make_emit_mat('M_S05_LanternGlow', (1.0, 0.71, 0.36), 3.0)
    parts = [cylinder('LanternPost', mat_metal, Vector((0, 0, 0)), 0.82, 0.016, segments=10),
             cylinder('LanternFoot', mat_metal, Vector((0, 0, 0)), 0.03, 0.05, segments=10),
             cylinder('LanternHead', mat_glow, Vector((0, 0, 0.82)), 0.09, 0.045, segments=8),
             cylinder('LanternCap', mat_metal, Vector((0, 0, 0.91)), 0.03, 0.055, segments=8)]
    lantern = join(parts, 'SM_S05_Lantern')
    finish_obj(lantern)
    smart_uv(lantern)
    return lantern

def build_facade():
    # Far-side backdrop 4.0 m long (04-blender-production.md 3.7: 3-6 m length; the 2026-09-25
    # build shipped 0.5 m — a x10 slip that read as a stray post in the frame).
    mat_wall = make_mat('M_S05_Facade', (0.18, 0.19, 0.23), roughness=0.95)
    mat_window = make_emit_mat('M_S05_Window', (1.0, 0.78, 0.47), 2.5)
    mesh = bpy.data.meshes.new('SM_S05_Facade')
    bm = bmesh.new()
    wall = bmesh.ops.create_cube(bm, size=1.0)
    bmesh.ops.scale(bm, verts=wall['verts'], vec=(4.0, 0.035, 1.10))
    bmesh.ops.translate(bm, verts=wall['verts'], vec=(0, 0, 0.55))
    for wx in (-1.2, 1.2):
        window_verts = [bm.verts.new(v) for v in
                        [(wx - 0.30, -0.037, 0.55), (wx + 0.30, -0.037, 0.55),
                         (wx + 0.30, -0.037, 0.85), (wx - 0.30, -0.037, 0.85)]]
        face = bm.faces.new(window_verts)
        face.material_index = 1
    bm.to_mesh(mesh)
    bm.free()
    obj = bpy.data.objects.new('SM_S05_Facade', mesh)
    obj.location = (0, 0, 0)
    bpy.context.collection.objects.link(obj)
    obj.data.materials.append(mat_wall)
    obj.data.materials.append(mat_window)
    finish_obj(obj)
    smart_uv(obj)
    return obj

def build_zone_edge():
    # Raised two-tone bar on the blue/red zone boundary (world y=0). Shape (raised strip) +
    # luminance difference carry the boundary without color (03-art-direction.md C-7).
    mat_blue = make_mat('M_S05_ZoneEdgeBlue', (0.22, 0.36, 0.64), roughness=0.6)
    mat_red = make_mat('M_S05_ZoneEdgeRed', (0.68, 0.30, 0.26), roughness=0.6)
    mesh = bpy.data.meshes.new('SM_S05_ZoneEdge')
    bm = bmesh.new()
    south = bmesh.ops.create_cube(bm, size=1.0)
    bmesh.ops.scale(bm, verts=south['verts'], vec=(5.0, 0.06, 0.02))
    bmesh.ops.translate(bm, verts=south['verts'], vec=(0, -0.033, 0.01))
    north = bmesh.ops.create_cube(bm, size=1.0)
    bmesh.ops.scale(bm, verts=north['verts'], vec=(5.0, 0.06, 0.02))
    bmesh.ops.translate(bm, verts=north['verts'], vec=(0, 0.033, 0.01))
    bm.to_mesh(mesh)
    bm.free()
    obj = bpy.data.objects.new('SM_S05_ZoneEdge', mesh)
    obj.location = (0, 0, 0)
    bpy.context.collection.objects.link(obj)
    obj.data.materials.append(mat_blue)
    obj.data.materials.append(mat_red)
    for poly in obj.data.polygons:
        center = obj.data.vertices[poly.vertices[0]].co
        poly.material_index = 0 if center.y < 0 else 1
    finish_obj(obj)
    smart_uv(obj)
    return obj

def build_zone_icons():
    # Zone pictograms at the tray edge (03-art-direction.md K-1): diamond = blue zone,
    # triangle = red zone — distinct by shape, not only color (C-7 deuteranopia requirement).
    mat_blue = make_mat('M_S05_IconBlue', (0.25, 0.40, 0.70), roughness=0.55)
    mat_red = make_mat('M_S05_IconRed', (0.72, 0.33, 0.28), roughness=0.55)
    diamond = cylinder('SM_S05_ZoneIcon_Blue', mat_blue, Vector((0, 0, 0)), 0.02, 0.14, segments=4)
    diamond.rotation_euler = (0.0, 0.0, math.pi / 4)
    finish_obj(diamond)
    smart_uv(diamond)
    tri = cylinder('SM_S05_ZoneIcon_Red', mat_red, Vector((0, 0, 0)), 0.02, 0.15, segments=3)
    finish_obj(tri)
    smart_uv(tri)
    return diamond, tri

def build_attack_beam():
    # K3 staged attack vector: shaft + head toward the target cell (north). Built along
    # Blender -Y, which lands on UE +Y (Q-311 axis mapping).
    mat = make_mat('M_S05_Beam', (0.95, 0.45, 0.20), roughness=0.4)
    parts = [cylinder_between('BeamShaft', mat, Vector((0, 0.28, 0.30)), Vector((0, -0.22, 0.30)), 0.011, segments=8),
             cone('BeamHead', mat, Vector((0, -0.22, 0.30)), Vector((0, -0.40, 0.30)), 0.030, segments=8)]
    beam = join(parts, 'SM_S05_AttackBeam')
    finish_obj(beam)
    smart_uv(beam)
    return beam

def build_card_quad():
    # Staged card inspector quad (60x84 uu stand-in; no 2D card art exists yet). The card face
    # sits on the Blender -Y side, which lands on UE +Y — toward the south-side camera.
    mat_frame = make_mat('M_S05_CardFrame', (0.10, 0.10, 0.12), roughness=0.6)
    mat_face = make_mat('M_S05_CardFace', (0.30, 0.28, 0.24), roughness=0.8)
    mesh = bpy.data.meshes.new('SM_S05_CardQuad')
    bm = bmesh.new()
    frame = bmesh.ops.create_cube(bm, size=1.0)
    bmesh.ops.scale(bm, verts=frame['verts'], vec=(0.62, 0.008, 0.86))
    bmesh.ops.translate(bm, verts=frame['verts'], vec=(0, 0, 0.43))
    face = bmesh.ops.create_cube(bm, size=1.0)
    bmesh.ops.scale(bm, verts=face['verts'], vec=(0.56, 0.008, 0.78))
    bmesh.ops.translate(bm, verts=face['verts'], vec=(0, -0.004, 0.43))
    bm.to_mesh(mesh)
    bm.free()
    obj = bpy.data.objects.new('SM_S05_CardQuad', mesh)
    obj.location = (0, 0, 0)
    bpy.context.collection.objects.link(obj)
    obj.data.materials.append(mat_frame)
    obj.data.materials.append(mat_face)
    for poly in obj.data.polygons:
        center = obj.data.vertices[poly.vertices[0]].co
        poly.material_index = 1 if center.y < 0 else 0
    finish_obj(obj)
    smart_uv(obj)
    return obj

def build_selection_capsule():
    # ART-004 selection collision proxy: render cylinder (hidden at runtime) + UCP_ capsule
    # kept as a SEPARATE FBX object (joining would destroy the UCP_ name UE matches for
    # collision import). Skeletal FBX import ignores UCP_ on SK_Medusa, so this ships as a
    # separate static mesh spawned invisibly under each figure for line traces.
    mat = make_mat('M_S05_HitProxy', (0.5, 0.5, 0.5), roughness=0.9)
    render = cylinder('SM_S05_SelectionCapsule', mat, Vector((0, 0, 0)), 0.62, 0.20, segments=12)
    finish_obj(render)
    smart_uv(render)
    ucp = cylinder('UCP_Medusa', mat, Vector((0, 0, 0)), 0.60, 0.18, segments=12)
    finish_obj(ucp)
    smart_uv(ucp)
    return render, ucp

def build_markers():
    mat_sel = make_mat('M_S05_RingSel', (0.95, 0.91, 0.85), roughness=0.5)
    mat_target = make_mat('M_S05_RingTarget', (0.88, 0.35, 0.23), roughness=0.5)
    mat_base_p1 = make_mat('M_S05_BaseP1', (0.91, 0.75, 0.42), roughness=0.7)
    mat_base_p2 = make_mat('M_S05_BaseP2', (0.62, 0.76, 0.85), roughness=0.7)
    ring = torus_ring('SM_S05_Ring_Selection', mat_sel, Vector((0, 0, 0.012)), 0.20, 0.008, 0, 360)
    finish_obj(ring)
    smart_uv(ring)
    target_parts = [torus_ring('TargetArc%d' % k, mat_target, Vector((0, 0, 0.014)), 0.225, 0.010, 45 + 90 * k, 50)
                    for k in range(4)]
    target = join(target_parts, 'SM_S05_Ring_Target')
    finish_obj(target)
    smart_uv(target)
    base_p1 = cylinder('SM_S05_Base_Hero_P1', mat_base_p1, Vector((0, 0, 0)), 0.06, 0.15, segments=28)
    finish_obj(base_p1)
    smart_uv(base_p1)
    base_p2 = cylinder('SM_S05_Base_Team2_Hex', mat_base_p2, Vector((0, 0, 0)), 0.045, 0.175, segments=6)
    finish_obj(base_p2)
    smart_uv(base_p2)
    return ring, target, base_p1, base_p2

# ---------------------------------------------------------------- main

def main():
    wipe_scene()
    report = {}
    arrow = build_arrow()
    manq_arm, manq_body, rm_test = build_mannequin()
    med_arm, med_body, med_bow, med_base, clips = build_medusa()
    tile = build_tile()
    table = build_table_base()
    lantern = build_lantern()
    facade = build_facade()
    zone_edge = build_zone_edge()
    icon_blue, icon_red = build_zone_icons()
    beam = build_attack_beam()
    card = build_card_quad()
    capsule_render, capsule_ucp = build_selection_capsule()
    ring_sel, ring_target, base_p1, base_p2 = build_markers()

    export_objects = [arrow, manq_arm, manq_body, med_arm, med_body, med_bow, med_base,
                      tile, table, lantern, facade, zone_edge, icon_blue, icon_red, beam,
                      card, capsule_render, capsule_ucp, ring_sel, ring_target, base_p1, base_p2]
    scale_rig_units((manq_arm, med_arm), 100.0)
    scale_objects_units(export_objects, 100.0)
    export_fbx(OUT / 'SM_S05_Arrow.fbx', [arrow])
    export_fbx(OUT / 'SM_S05_Mannequin.fbx', [manq_arm, manq_body])
    export_fbx(OUT / 'SK_Medusa.fbx', [med_arm, med_body, med_bow, med_base])
    for clip_name, action in clips.items():
        med_arm.animation_data.action = action
        bpy.context.scene.frame_start = int(action.frame_range[0])
        bpy.context.scene.frame_end = int(action.frame_range[1])
        export_anim_fbx(OUT / (clip_name + '.fbx'), [med_arm, med_body, med_bow, med_base])
    manq_arm.animation_data.action = rm_test
    bpy.context.scene.frame_start, bpy.context.scene.frame_end = 1, 30
    export_anim_fbx(OUT / 'AM_RM_Test.fbx', [manq_arm, manq_body])
    for obj in (tile, table, lantern, facade, zone_edge, icon_blue, icon_red, beam, card,
                ring_sel, ring_target, base_p1, base_p2):
        export_fbx(OUT / (obj.name + '.fbx'), [obj])
    export_fbx(OUT / 'SM_S05_SelectionCapsule.fbx', [capsule_render, capsule_ucp])
    scale_rig_units((manq_arm, med_arm), 0.01)
    scale_objects_units(export_objects, 0.01)
    # USF=1 on EVERY exported file: the data inside is already cm-numbered (scale pass above),
    # and UE multiplies every number by the file UnitScaleFactor - 1.0 lands numbers 1:1 as uu
    for fbx_file in sorted(OUT.glob('*.fbx')):
        patch_fbx_unit_scale(fbx_file)

    bpy.ops.wm.save_as_mainfile(filepath=str(BLEND_DIR / 's05-assets.blend'))

    def dims(obj):
        return [round(v, 4) for v in (obj.dimensions.x, obj.dimensions.y, obj.dimensions.z)]
    report['dims_m'] = {'arrow': dims(arrow), 'mannequin': dims(manq_body), 'medusa_body': dims(med_body),
                        'medusa_bow': dims(med_bow), 'medusa_base': dims(med_base), 'tile': dims(tile),
                        'table': dims(table), 'lantern': dims(lantern), 'facade': dims(facade),
                        'zone_edge': dims(zone_edge), 'icon_blue': dims(icon_blue), 'icon_red': dims(icon_red),
                        'beam': dims(beam), 'card': dims(card), 'selection_capsule': dims(capsule_render)}
    report['tris'] = {'arrow': tri_count(arrow), 'mannequin': tri_count(manq_body),
                      'medusa_body': tri_count(med_body), 'medusa_bow': tri_count(med_bow),
                      'medusa_base': tri_count(med_base), 'tile': tri_count(tile), 'table': tri_count(table),
                      'lantern': tri_count(lantern), 'facade': tri_count(facade), 'ring_sel': tri_count(ring_sel),
                      'ring_target': tri_count(ring_target), 'base_p1': tri_count(base_p1), 'base_p2': tri_count(base_p2),
                      'zone_edge': tri_count(zone_edge), 'icon_blue': tri_count(icon_blue),
                      'icon_red': tri_count(icon_red), 'beam': tri_count(beam), 'card': tri_count(card),
                      'selection_capsule': tri_count(capsule_render)}
    report['medusa_bones'] = len(med_arm.data.bones)
    report['fbx_unit_contract'] = ('rig FBX carry cm-numbered bones/curves + geometry, '
                                   'UnitScaleFactor patched to 1.0: UE bone 0 scale 1, '
                                   'AM_RM_Test root motion exactly 100uu')
    # authoritative bone-name list for the UE import check (the legacy FBX importer renames
    # '.' to '_': arm_upper.L -> arm_upper_L); no hardcode fallback on the UE side anymore
    report['medusa_bone_names'] = [b.name for b in med_arm.data.bones]
    report['clips'] = {name: [int(a.frame_range[0]), int(a.frame_range[1])] for name, a in clips.items()}
    report['rm_test_frames'] = [int(rm_test.frame_range[0]), int(rm_test.frame_range[1])]
    (BLEND_DIR / 'build-report.json').write_text(str(report).replace("'", '"'), encoding='utf-8')
    print('S05_BUILD_REPORT ' + str(report).replace("'", '"'))

main()
