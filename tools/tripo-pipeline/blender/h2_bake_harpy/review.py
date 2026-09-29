"""Review helpers of the H2 bake (render frames in headless Blender). Every frame is a Blender render (label
"blender"), neutral preview light, not the game lighting; materials single-sided as in UE."""

import math

import bpy
from mathutils import Vector

PART_COLOURS = [(0.90, 0.30, 0.25), (0.25, 0.60, 0.90), (0.95, 0.80, 0.20), (0.40, 0.80, 0.40), (0.80, 0.40, 0.90),
                (0.95, 0.55, 0.15), (0.30, 0.90, 0.85), (0.60, 0.60, 0.60), (0.90, 0.45, 0.65), (0.50, 0.35, 0.20),
                (0.20, 0.35, 0.75), (0.75, 0.90, 0.30), (0.95, 0.95, 0.95), (0.35, 0.20, 0.50)]


def setup_scene(scene, engine="BLENDER_EEVEE", world=0.55, key=3.0, fill=1.3, view="Standard", samples=64):
    scene.render.engine = engine
    if engine == "CYCLES":
        scene.cycles.samples = samples
        scene.cycles.use_denoising = False
        scene.cycles.seed = 0
    elif engine == "BLENDER_EEVEE":
        try:
            scene.eevee.taa_render_samples = samples
        except AttributeError:
            pass
    scene.view_settings.view_transform = view
    scene.render.film_transparent = False
    w = bpy.data.worlds.new("h2_review_world")
    scene.world = w
    try:
        w.use_nodes = True
    except AttributeError:
        pass
    bg = w.node_tree.nodes.get("Background")
    bg.inputs[0].default_value = (0.5, 0.5, 0.5, 1)
    bg.inputs[1].default_value = world
    for name, rot, energy in (("h2_key", (50, 0, -30), key), ("h2_fill", (60, 0, 150), fill)):
        light = bpy.data.lights.new(name, "SUN")
        light.energy = energy
        lo = bpy.data.objects.new(name, light)
        lo.rotation_euler = [math.radians(a) for a in rot]
        scene.collection.objects.link(lo)
    cam = bpy.data.objects.new("h2_cam", bpy.data.cameras.new("h2_cam"))
    scene.collection.objects.link(cam)
    scene.camera = cam
    return cam


def aim(scene, cam, direction, target, ortho=None, fov_h=None, distance=None, res=(1000, 1000)):
    d = Vector(direction).normalized()
    t = Vector(target)
    if ortho is not None:
        cam.data.type = "ORTHO"
        cam.data.ortho_scale = ortho
        cam.location = t + d * 5.0
    else:
        cam.data.type = "PERSP"
        cam.data.sensor_fit = "HORIZONTAL"
        cam.data.angle = math.radians(fov_h)
        cam.location = t + d * distance
    cam.data.clip_start = 0.01
    cam.data.clip_end = 100.0
    cam.rotation_euler = (-d).to_track_quat("-Z", "Y").to_euler()
    scene.render.resolution_x, scene.render.resolution_y = res
    scene.render.resolution_percentage = 100
    return d, t


def shoot(scene, cam, path, direction, target, **kw):
    aim(scene, cam, direction, target, **kw)
    scene.render.filepath = str(path)
    scene.render.image_settings.file_format = "PNG"
    bpy.ops.render.render(write_still=True)
    return {"direction": [round(c, 4) for c in Vector(direction).normalized()], "target_m": list(target),
            **{k: (list(v) if isinstance(v, tuple) else v) for k, v in kw.items()}}


def game_dir(azimuth_deg, pitch_deg=-55.0):
    """Direction from target to camera: azimuth 0 = in front of the figure (-Y), + = figure's left (+X)."""
    el = math.radians(-pitch_deg)
    az = math.radians(azimuth_deg)
    return (math.sin(az) * math.cos(el), -math.cos(az) * math.cos(el), math.sin(el))


def flat_material(name, rgb, roughness=0.6):
    m = bpy.data.materials.new(name)
    try:
        m.use_nodes = True
    except AttributeError:
        pass
    bsdf = next(n for n in m.node_tree.nodes if n.type == "BSDF_PRINCIPLED")
    bsdf.inputs["Base Color"].default_value = (*rgb, 1)
    bsdf.inputs["Roughness"].default_value = roughness
    m.use_backface_culling = True
    return m


def ground(scene, cells, name="h2_cells"):
    """1 m cells on the ground plane with a 2 cm dark border (board-like), z just below 0 (same as the T3.3 review)."""
    import bmesh
    mats = [flat_material("h2_cell", (0.085, 0.095, 0.11), 0.9), flat_material("h2_border", (0.02, 0.02, 0.025), 0.9)]
    made = []
    for (cx, cy) in cells:
        for size, z, mat in ((1.0, -0.0006, mats[1]), (0.96, -0.0003, mats[0])):
            me = bpy.data.meshes.new(name)
            bm = bmesh.new()
            h = size / 2
            vs = [bm.verts.new((cx + x, cy + y, z)) for x, y in ((-h, -h), (h, -h), (h, h), (-h, h))]
            bm.faces.new(vs)
            bm.to_mesh(me)
            bm.free()
            me.materials.append(mat)
            o = bpy.data.objects.new(name, me)
            scene.collection.objects.link(o)
            made.append(o)
    return made
