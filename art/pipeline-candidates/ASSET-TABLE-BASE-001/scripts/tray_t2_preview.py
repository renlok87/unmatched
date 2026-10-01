"""ASSET-TABLE-BASE-001 T2: review renders of the EXPORTED SM_TableBase_T2.fbx (headless Blender, Cycles on the CPU).

  "C:/Program Files/Blender Foundation/Blender 5.2/blender.exe" -b --factory-startup --python-exit-code 1 \
      --python art/pipeline-candidates/ASSET-TABLE-BASE-001/scripts/tray_t2_preview.py -- <tray-t2-params.json>

The FBX is read back (frame = UE with Y negated: every UE position below goes through ue()), placed like the board
actor places it (tray centre at UE (0, offsetY)), with a neutral map proxy (flat plate 891.333 x 577.333 at Z -0.5 +
the 24 uu wooden frame; NOT the map illustration: ENV-U3, map-derived images stay out of git) and, in the "ground"
variants, a flat earth-coloured proxy of the themed ground (track GROUND) on the tray rectangle up to Z -1 (its
layout 'ground'.z).
Cameras = the game camera model (HFOV 35, 16:9, pitch -55, yaw -90: looking along UE -Y), K1 x1.25 (ENV-U9) and the
0.65x zoom-out on the map centre, the 1.6x follow view on a near space; plus two NON-game diagnostics (low three-quarter
of the near-east corner, orthographic front elevation of the near side). Lighting is a neutral review rig (cool key
along the art profiles' key direction (-55, 30, 0), weak warm fill from the camera side, dim blue sky), not the night
profiles (the lighting track calibrates those in UE). Output: <run>/preview/tray-t2-*.jpg + preview.json.
"""

import json
import math
import sys
from pathlib import Path

import bpy
from mathutils import Vector

HERE = Path(__file__).resolve()
REPO = HERE.parents[4]


def load_params():
    argv = sys.argv[sys.argv.index("--") + 1:]
    pp = Path(argv[0]).resolve()
    P = json.loads(pp.read_text(encoding="utf-8"))
    P["_run"] = (REPO / P["run_dir"]).resolve()
    return P


def ue(x, y, z):
    """UE board-actor space -> the FBX read-back frame (Y negated)."""
    return Vector((x, -y, z)) / 100.0


def mat_flat(name, rgb, rough=0.9):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    b = next(n for n in m.node_tree.nodes if n.type == "BSDF_PRINCIPLED")
    b.inputs["Base Color"].default_value = (*rgb, 1.0)
    b.inputs["Roughness"].default_value = rough
    return m


def tray_material(P):
    exp = P["_run"] / "export"
    m = bpy.data.materials.new("M_TableBase_T2_preview")
    m.use_nodes = True
    nt = m.node_tree
    b = next(n for n in nt.nodes if n.type == "BSDF_PRINCIPLED")
    imgs = {}
    for key, cs in (("BC", "sRGB"), ("N", "Non-Color"), ("ORM", "Non-Color")):
        img = bpy.data.images.load(str(exp / ("%s_%s.png" % (P["texture_prefix"], key))))
        img.colorspace_settings.name = cs
        t = nt.nodes.new("ShaderNodeTexImage")
        t.image = img
        t.extension = "REPEAT"
        imgs[key] = t
    nt.links.new(imgs["BC"].outputs["Color"], b.inputs["Base Color"])
    sep = nt.nodes.new("ShaderNodeSeparateColor")
    nt.links.new(imgs["ORM"].outputs["Color"], sep.inputs["Color"])
    nt.links.new(sep.outputs["Green"], b.inputs["Roughness"])
    # DirectX normal -> OpenGL for Blender: flip green
    sn = nt.nodes.new("ShaderNodeSeparateColor")
    inv = nt.nodes.new("ShaderNodeMath")
    inv.operation = "SUBTRACT"
    inv.inputs[0].default_value = 1.0
    cm = nt.nodes.new("ShaderNodeCombineColor")
    nm = nt.nodes.new("ShaderNodeNormalMap")
    nt.links.new(imgs["N"].outputs["Color"], sn.inputs["Color"])
    nt.links.new(sn.outputs["Red"], cm.inputs["Red"])
    nt.links.new(sn.outputs["Green"], inv.inputs[1])
    nt.links.new(inv.outputs[0], cm.inputs["Green"])
    nt.links.new(sn.outputs["Blue"], cm.inputs["Blue"])
    nt.links.new(cm.outputs["Color"], nm.inputs["Color"])
    nt.links.new(nm.outputs["Normal"], b.inputs["Normal"])
    return m


def box(name, lo, hi, mat):
    bpy.ops.mesh.primitive_cube_add(size=1.0)
    o = bpy.context.active_object
    o.name = name
    a, b = Vector(lo), Vector(hi)
    o.location = (a + b) / 2
    o.scale = Vector((abs(b.x - a.x), abs(b.y - a.y), abs(b.z - a.z)))
    o.data.materials.append(mat)
    return o


def aim(obj, target):
    d = target - obj.location
    obj.rotation_euler = d.to_track_quat("-Z", "Y").to_euler()


def main():
    P = load_params()
    pv, tray = P["preview"], P["tray"]
    out = P["_run"] / "preview"
    out.mkdir(parents=True, exist_ok=True)
    bpy.ops.wm.read_factory_settings(use_empty=True)
    sc = bpy.context.scene
    try:
        sc.render.engine = "CYCLES"
    except TypeError as e:
        raise SystemExit("Cycles unavailable: %s" % e)
    sc.cycles.device = "CPU"
    sc.cycles.samples = int(pv["samples"])
    sc.cycles.use_denoising = True
    sc.render.resolution_x, sc.render.resolution_y = pv["resolution"]
    sc.render.resolution_percentage = 100
    fmts = [i.identifier for i in sc.render.image_settings.bl_rna.properties["file_format"].enum_items]
    sc.render.image_settings.file_format = "JPEG" if "JPEG" in fmts else "PNG"
    if sc.render.image_settings.file_format == "JPEG":
        sc.render.image_settings.quality = 90
    sc.view_settings.view_transform = "AgX" if "AgX" in [i.identifier for i in sc.view_settings.bl_rna.properties[
        "view_transform"].enum_items] else "Standard"

    bpy.ops.import_scene.fbx(filepath=str(P["_run"] / "export" / ("%s.fbx" % P["asset_name"])))
    tray_obj = next(o for o in sc.objects if o.type == "MESH")
    tray_obj.data.materials.clear()
    tray_obj.data.materials.append(tray_material(P))
    oy = float(tray["offset_y_ue"])
    tray_obj.location = ue(0.0, oy, 0.0)

    # map proxy + wooden frame (board-actor space, map centre at the origin)
    mhx, mhy, fr = 445.667, 288.667, 24.0
    plate = mat_flat("map_proxy", (0.10, 0.11, 0.09), 0.8)
    wood = mat_flat("frame_wood", (0.10, 0.055, 0.03), 0.7)
    box("MapProxy", ue(-mhx, mhy, -1.0), ue(mhx, -mhy, -0.5), plate)
    for n, lo, hi in (("FrameN", (-mhx - fr, -mhy - fr), (mhx + fr, -mhy)), ("FrameS", (-mhx - fr, mhy), (mhx + fr, mhy + fr)),
                      ("FrameW", (-mhx - fr, -mhy), (-mhx, mhy)), ("FrameE", (mhx, -mhy), (mhx + fr, mhy))):
        box(n, ue(lo[0], hi[1], -10.0), ue(hi[0], lo[1], 4.0), wood)
    hx, hy = float(tray["half_x_ue"]), float(tray["half_y_ue"])
    # the GROUND track's runtime ground: tray top minus the frame at z -1 (layout "ground".z) - a proxy slab up to -1
    ground = box("GroundProxy", ue(-hx, oy + hy, -3.0), ue(hx, oy - hy, -1.0), mat_flat("ground_proxy", (0.075, 0.06, 0.045)))

    # review light rig
    world = bpy.data.worlds.new("W")
    sc.world = world
    world.use_nodes = True
    bg = next(n for n in world.node_tree.nodes if n.type == "BACKGROUND")
    bg.inputs["Color"].default_value = (0.012, 0.016, 0.03, 1.0)
    bg.inputs["Strength"].default_value = 1.0
    p, yw = math.radians(-55.0), math.radians(30.0)
    travel = Vector((math.cos(p) * math.cos(yw), -math.cos(p) * math.sin(yw), math.sin(p)))  # UE (-55, 30) -> read-back
    key = bpy.data.objects.new("Key", bpy.data.lights.new("Key", "SUN"))
    key.data.energy = 2.2
    key.data.color = (0.75, 0.82, 1.0)
    key.data.angle = math.radians(2.0)
    key.rotation_euler = travel.to_track_quat("-Z", "Y").to_euler()
    sc.collection.objects.link(key)
    fill = bpy.data.objects.new("Fill", bpy.data.lights.new("Fill", "SUN"))
    fill.data.energy = 0.45
    fill.data.color = (1.0, 0.8, 0.6)
    fdir = Vector((0.15, 0.75, -0.55)).normalized()  # from the camera side (UE +Y), towards the tray
    fill.rotation_euler = fdir.to_track_quat("-Z", "Y").to_euler()
    sc.collection.objects.link(fill)

    cam = bpy.data.objects.new("Cam", bpy.data.cameras.new("Cam"))
    sc.collection.objects.link(cam)
    sc.camera = cam
    cam.data.sensor_fit = "HORIZONTAL"
    cam.data.angle = math.radians(float(pv["hfov_deg"]))
    cam.data.clip_start, cam.data.clip_end = 0.1, 200.0
    pitch = math.radians(-float(pv["pitch_deg"]))

    def game(focus, dist):
        f = ue(*focus)
        c = ue(focus[0], focus[1] + dist * math.cos(pitch), focus[2] + dist * math.sin(pitch))
        return c, f

    shots = [
        ("zoomout065-ground", "game: zoom-out 0.65x (D %.0f) on the map centre, ground proxy" % pv["zoom_out_distance_uu"],
         game((0, 0, 0), pv["zoom_out_distance_uu"]), True, None),
        ("zoomout065-bare", "game: zoom-out 0.65x, bare T2 (flat top visible)", game((0, 0, 0), pv["zoom_out_distance_uu"]),
         False, None),
        ("k1-ground", "game: K1 x1.25 (D %.0f), ground proxy" % pv["k1_distance_uu"], game((0, 0, 0), pv["k1_distance_uu"]),
         True, None),
        ("follow16-nearE-ground", "game: 1.6x follow on a near-east space (UE 300, 250), ground proxy",
         game((300, 250, 28), pv["follow_distance_uu"]), True, None),
        ("diag-corner-NE-low", "NOT a game view: low three-quarter of the near-east corner",
         (ue(1350, 1250, 180), ue(700, 380, -70)), True, None),
        ("diag-front-ortho", "NOT a game view: orthographic front elevation of the near side (UE +Y)",
         (ue(0, 2500, -60), ue(0, 0, -60)), True, 17.5),
    ]
    info = {"schema": "unmatched.table-base-t2.preview/1", "renderer": "Cycles CPU", "samples": sc.cycles.samples,
            "resolution": pv["resolution"], "shots": []}
    for name, title, (c, f), with_ground, ortho in shots:
        ground.hide_render = not with_ground
        cam.location = c
        aim(cam, f)
        if ortho:
            cam.data.type = "ORTHO"
            cam.data.ortho_scale = ortho
        else:
            cam.data.type = "PERSP"
        path = out / ("tray-t2-%s.%s" % (name, "jpg" if sc.render.image_settings.file_format == "JPEG" else "png"))
        sc.render.filepath = str(path)
        bpy.ops.render.render(write_still=True)
        info["shots"].append({"file": path.name, "title": title, "cameraUE": [round(c.x * 100, 1), round(-c.y * 100, 1),
                                                                               round(c.z * 100, 1)],
                              "targetUE": [round(f.x * 100, 1), round(-f.y * 100, 1), round(f.z * 100, 1)],
                              "groundProxy": with_ground})
        print("T2-PREVIEW", path.name)
    (out / "preview.json").write_text(json.dumps(info, indent=2) + "\n", encoding="utf-8")


main()
