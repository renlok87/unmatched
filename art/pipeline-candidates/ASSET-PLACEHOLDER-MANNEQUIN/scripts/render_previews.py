"""Preview frames of the mannequin candidate (EEVEE, neutral preview light, not the game light).

Headless only; opens work/mannequin.blend and never saves it:
  blender -b --factory-startup --python-exit-code 1 --python render_previews.py -- <run_dir> <profile.json>

Writes PNG frames to <run_dir>/work/renders/ (converted to JPEG <= 1200 px by postprocess_previews.py):
  ortho_{front,back,left,right,top}      orthographic, 1000 x 1000, SK figure + base (one-sided materials,
                                          so an inverted face would show as a hole)
  wire_{front,3q}                        wireframe over the flat grey model (04 §5 «wireframe»)
  collision_front                        static mesh + UCP_ capsule as a wire
  game_k1_{front,3q}                     perspective, horizontal FOV 35 deg, pitch -55 deg, 16:9, 1200 x 675,
                                          two static mannequins (gold / silver band) on 1 m cells, camera distance
                                          12.18 m (cell ≈ 250 px at 1920 px, 04 §3 proposal)
  game_close_{front,3q}, game_close_pair same camera angles at 1.4 m
  silhouette_{k1,close}                  black material override on white, board hidden (03 С-1 test)
  pose_<test>                            solid renders of the seven rig_deform_probe rotations (3/4 view)
  fbx_roundtrip_front                    (second run with --fbx) SK + base FBX re-imported in an empty file,
                                          rotation undone, same scene/camera/light as ortho_front
"""

import json
import math
import sys
from pathlib import Path

import bpy
from mathutils import Matrix, Vector

if not bpy.app.background:
    raise RuntimeError("render_previews.py: headless only (blender -b)")

POSES = [  # same bones, world axes and angles as tools/tripo-pipeline/anim/rig_deform_probe.py TESTS
    ("head_turn", "head", "Z", 35), ("spine_bend_fwd", "spine", "X", 25), ("arm_l_raise", "arm_upper.L", "Y", -45),
    ("arm_r_raise", "arm_upper.R", "Y", 45), ("forearm_l_bend", "arm_lower.L", "X", -40),
    ("thigh_l_flex", "leg_upper.L", "X", -35), ("thigh_r_flex", "leg_upper.R", "X", -35),
]


def emission_mat(name, rgb, strength=1.0):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    nt = m.node_tree
    for n in list(nt.nodes):
        nt.nodes.remove(n)
    em = nt.nodes.new("ShaderNodeEmission")
    em.inputs["Color"].default_value = (*rgb, 1)
    em.inputs["Strength"].default_value = strength
    out = nt.nodes.new("ShaderNodeOutputMaterial")
    nt.links.new(em.outputs["Emission"], out.inputs["Surface"])
    return m


def principled(name, rgb, rough=0.8):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    b = next(n for n in m.node_tree.nodes if n.type == "BSDF_PRINCIPLED")
    b.inputs["Base Color"].default_value = (*rgb, 1)
    b.inputs["Roughness"].default_value = rough
    return m


def world(scene, rgb, strength):
    w = bpy.data.worlds.new("W_" + scene.name)
    w.use_nodes = True
    bg = w.node_tree.nodes.get("Background")
    bg.inputs["Color"].default_value = (*rgb, 1)
    bg.inputs["Strength"].default_value = strength
    scene.world = w


def sun(scene, name, rot_deg, energy):
    d = bpy.data.lights.new(name, "SUN")
    d.energy = energy
    o = bpy.data.objects.new(name, d)
    o.rotation_euler = [math.radians(a) for a in rot_deg]
    scene.collection.objects.link(o)
    return o


def look(cam, target, direction, dist):
    d = Vector(direction).normalized()
    cam.location = Vector(target) - d * dist
    cam.rotation_euler = d.to_track_quat("-Z", "Y").to_euler()


def render(scene, path, w, h):
    scene.render.resolution_x, scene.render.resolution_y = w, h
    scene.render.resolution_percentage = 100
    scene.render.filepath = str(path)
    scene.render.image_settings.file_format = "PNG"
    with bpy.context.temp_override(scene=scene):
        bpy.ops.render.render(write_still=True, scene=scene.name)


def new_scene(name, world_rgb=(0.22, 0.22, 0.24), world_strength=0.6):
    sc = bpy.data.scenes.new(name)
    sc.render.engine = "BLENDER_EEVEE"
    if hasattr(sc.eevee, "taa_render_samples"):
        sc.eevee.taa_render_samples = 32
    sc.view_settings.view_transform = "Standard"
    sc.render.film_transparent = False
    world(sc, world_rgb, world_strength)
    sun(sc, name + "_Key", (50, 0, 35), 3.5)
    sun(sc, name + "_Fill", (60, 0, -140), 1.0)
    cam_data = bpy.data.cameras.new(name + "_Cam")
    cam = bpy.data.objects.new(name + "_Cam", cam_data)
    sc.collection.objects.link(cam)
    sc.camera = cam
    return sc, cam


def game_dir(yaw_deg, pitch_deg=-55.0):
    """Camera view direction: pitch below the horizon, yaw 0 = looking along +Y (at the figures' front)."""
    p, y = math.radians(-pitch_deg), math.radians(yaw_deg)
    return Vector((math.sin(y) * math.cos(p), math.cos(y) * math.cos(p), -math.sin(p)))


def board(scene, half_x=7, y_range=(-6, 9)):
    import bmesh
    bm = bmesh.new()
    for i in range(-half_x, half_x + 1):
        for j in range(y_range[0], y_range[1] + 1):
            vs = [bm.verts.new((i + dx * 0.49, j + dy * 0.49, 0.0)) for dx, dy in ((-1, -1), (1, -1), (1, 1), (-1, 1))]
            f = bm.faces.new(vs)
            f.material_index = (i + j) % 2
    under = [bm.verts.new((x, y, -0.002)) for x, y in ((-half_x - 1, y_range[0] - 1), (half_x + 1, y_range[0] - 1),
                                                           (half_x + 1, y_range[1] + 1), (-half_x - 1, y_range[1] + 1))]
    bm.faces.new(under).material_index = 2
    me = bpy.data.meshes.new("PV_Board")
    bm.to_mesh(me)
    bm.free()
    for rgb in ((0.13, 0.13, 0.13), (0.10, 0.10, 0.10), (0.03, 0.03, 0.03)):  # linear greys, cell gap darker
        me.materials.append(principled("PV_Board_%d" % len(me.materials), rgb, 0.9))
    o = bpy.data.objects.new("PV_Board", me)
    scene.collection.objects.link(o)
    return o


def fbx_mode(run_dir, profile):
    """Second process: FBX round trip in a factory-empty file (the importer fails to build the pose when the
    authored armature is already loaded, measured 2026-09-28). Preview materials are appended from the .blend;
    scene, light and camera are the ones of ortho_front."""
    v = profile["variants"]
    out = run_dir / "work" / "renders"
    bpy.ops.wm.read_factory_settings(use_empty=True)
    for f in (v["skeletal"]["fbx"], v["skeletal"]["base_fbx"]):
        bpy.ops.import_scene.fbx(filepath=str(run_dir / "export" / f))
    imported = list(bpy.context.scene.objects)
    inv = Matrix.Rotation(math.radians(-90.0), 4, "Z")
    for o in imported:
        if o.parent is None:
            o.matrix_world = inv @ o.matrix_world
    names = [profile["materials"]["figure"]["name"], profile["materials"]["base"]["name"]]
    for m in list(bpy.data.materials):
        if m.name in names:
            m.name = m.name + "_fbx"
    with bpy.data.libraries.load(str(run_dir / "work" / "mannequin.blend"), link=False) as (src, dst):
        dst.materials = list(names)  # the loader replaces the list items by IDs in place
    mats = {m.name: m for m in dst.materials}
    sc, cam = new_scene("PV_Ortho")
    for o in imported:
        sc.collection.objects.link(o)
        if o.type == "MESH":
            is_base = o.name == v["skeletal"]["base_object"]
            for s in o.material_slots:
                s.material = mats[names[1] if is_base else names[0]]
            if is_base:
                o["um_team_color"] = profile["materials"]["base"]["team_colors_linear"]["gold"]
    sc.view_layers[0].update()
    cam.data.type = "ORTHO"
    cam.data.ortho_scale = 0.6
    look(cam, Vector((0, 0, 0.25)), (0, 1, 0), 3.0)
    render(sc, out / "fbx_roundtrip_front.png", 1000, 1000)
    print("MANNEQUIN_PREVIEWS_FBX", [o.name for o in imported])


def main():
    argv = sys.argv[sys.argv.index("--") + 1:]
    run_dir, profile_path = Path(argv[0]).resolve(), Path(argv[1]).resolve()
    profile = json.loads(profile_path.read_text(encoding="utf-8"))
    if "--fbx" in argv:
        fbx_mode(run_dir, profile)
        return
    out = run_dir / "work" / "renders"
    out.mkdir(parents=True, exist_ok=True)
    bpy.ops.wm.open_mainfile(filepath=str(run_dir / "work" / "mannequin.blend"))
    v = profile["variants"]
    body = bpy.data.objects[v["skeletal"]["object"]]
    base = bpy.data.objects[v["skeletal"]["base_object"]]
    arm = bpy.data.objects[profile["armature"]["object"]]
    static = bpy.data.objects[v["static"]["object"]]
    ucp = bpy.data.objects[v["static"]["collision_object"]]
    gold = profile["materials"]["base"]["team_colors_linear"]["gold"]
    silver = profile["materials"]["base"]["team_colors_linear"]["silver"]
    cam_cfg = profile["previews"]["game_camera"]
    done = []

    # ---------------------------------------------------------------- ortho
    sc, cam = new_scene("PV_Ortho")
    for o in (arm, body, base):
        sc.collection.objects.link(o)
    cam.data.type = "ORTHO"
    cam.data.ortho_scale = 0.6
    target = Vector((0, 0, 0.25))
    for key, d in (("front", (0, 1, 0)), ("back", (0, -1, 0)), ("left", (-1, 0, 0)), ("right", (1, 0, 0)),
                   ("top", (0, 0.0001, -1))):
        look(cam, target, d, 3.0)
        render(sc, out / ("ortho_%s.png" % key), 1000, 1000)
        done.append("ortho_%s" % key)
    # wireframe overlay: linked copies with a wireframe modifier and a black material
    black = emission_mat("PV_Black", (0, 0, 0), 1.0)
    wires = []
    for o in (body, base):
        c = o.copy()
        c.name = o.name + "_PVWire"
        c.parent = None
        c.matrix_world = o.matrix_world
        for s in c.material_slots:
            s.link = "OBJECT"
            s.material = black
        c.modifiers.clear()
        wm = c.modifiers.new("Wire", "WIREFRAME")
        wm.thickness = 0.0005
        wm.use_replace = True
        sc.collection.objects.link(c)
        wires.append(c)
    look(cam, target, (0, 1, 0), 3.0)
    render(sc, out / "wire_front.png", 1000, 1000)
    look(cam, target, game_dir(35, -20), 3.0)
    render(sc, out / "wire_3q.png", 1000, 1000)
    done += ["wire_front", "wire_3q"]
    for c in wires:
        sc.collection.objects.unlink(c)
    # poses (solid; probe rotations about world axes through the bone head)
    look(cam, target, game_dir(30, -15), 3.0)
    for name, bone, axis, deg in POSES:
        for pb in arm.pose.bones:
            pb.matrix_basis = Matrix.Identity(4)
        bpy.context.view_layer.update()
        sc.view_layers[0].update()
        pb = arm.pose.bones[bone]
        head = pb.head.copy()
        ax = {"X": Vector((1, 0, 0)), "Y": Vector((0, 1, 0)), "Z": Vector((0, 0, 1))}[axis]
        R = Matrix.Translation(head) @ Matrix.Rotation(math.radians(deg), 4, ax) @ Matrix.Translation(-head)
        pb.matrix = R @ pb.matrix
        sc.view_layers[0].update()
        render(sc, out / ("pose_%s.png" % name), 700, 700)
        done.append("pose_" + name)
    for pb in arm.pose.bones:
        pb.matrix_basis = Matrix.Identity(4)
    sc.view_layers[0].update()

    # ---------------------------------------------------------------- collision overlay (static scene objects)
    sc2, cam2 = new_scene("PV_Collision")
    sc2.collection.objects.link(static)
    uc = ucp.copy()
    uc.name = "UCP_PVWire"
    uc.hide_render = False
    uc.display_type = "TEXTURED"
    orange = emission_mat("PV_Orange", (1.0, 0.35, 0.02), 1.0)
    uc.data = ucp.data.copy()
    uc.data.materials.clear()
    uc.data.materials.append(orange)
    wm = uc.modifiers.new("Wire", "WIREFRAME")
    wm.thickness = 0.0012
    wm.use_replace = True
    sc2.collection.objects.link(uc)
    cam2.data.type = "ORTHO"
    cam2.data.ortho_scale = 0.75
    look(cam2, (0, 0, 0.205), (0, 1, 0), 3.0)
    render(sc2, out / "collision_front.png", 1000, 1000)
    done.append("collision_front")

    # ---------------------------------------------------------------- game camera
    sc3, cam3 = new_scene("PV_Game", (0.01, 0.01, 0.012), 1.0)
    brd = board(sc3)
    figs = []
    for x, col in ((0.0, gold), (1.0, silver)):
        c = static.copy()
        c.name = "PV_Fig_%s" % ("gold" if col is gold else "silver")
        c.location = (x, 0, 0)
        c["um_team_color"] = col
        sc3.collection.objects.link(c)
        figs.append(c)
    cam3.data.type = "PERSP"
    cam3.data.sensor_fit = "HORIZONTAL"
    cam3.data.angle_x = math.radians(cam_cfg["horizontal_fov_deg"])
    cam3.data.clip_start = 0.05
    cam3.data.clip_end = 100
    tgt = Vector((0.5, 0, 0.2))
    for key, yaw in (("front", 0.0), ("3q", 35.0)):
        look(cam3, tgt, game_dir(yaw, cam_cfg["pitch_deg"]), cam_cfg["k1_distance_m"])
        render(sc3, out / ("game_k1_%s.png" % key), 1200, 675)
        done.append("game_k1_" + key)
    look(cam3, tgt, game_dir(0.0, cam_cfg["pitch_deg"]), cam_cfg["closeup_distance_m"] * 1.6)
    render(sc3, out / "game_close_pair.png", 1200, 675)
    done.append("game_close_pair")
    figs[1].hide_render = True
    for key, yaw in (("front", 0.0), ("3q", 35.0)):
        look(cam3, Vector((0, 0, 0.24)), game_dir(yaw, cam_cfg["pitch_deg"]), cam_cfg["closeup_distance_m"])
        render(sc3, out / ("game_close_%s.png" % key), 1200, 675)
        done.append("game_close_" + key)
    # silhouettes: black override, white world, no board
    brd.hide_render = True
    sc3.view_layers[0].material_override = black
    sc3.world.node_tree.nodes["Background"].inputs["Color"].default_value = (1, 1, 1, 1)
    figs[1].hide_render = True
    look(cam3, Vector((0, 0, 0.2)), game_dir(0.0, cam_cfg["pitch_deg"]), cam_cfg["k1_distance_m"])
    render(sc3, out / "silhouette_k1.png", 1200, 675)
    look(cam3, Vector((0, 0, 0.24)), game_dir(0.0, cam_cfg["pitch_deg"]), cam_cfg["closeup_distance_m"])
    render(sc3, out / "silhouette_close.png", 1200, 675)
    done += ["silhouette_k1", "silhouette_close"]

    print("MANNEQUIN_PREVIEWS", len(done), done)


main()
