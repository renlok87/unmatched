"""Review frames of the Harpy candidate (headless only: blender -b --factory-startup). Harpy version of
art/pipeline-candidates/ASSET-MERLIN-001/scripts/review_merlin_candidate.py (same lights and game camera).

    blender -b --factory-startup --python review_harpy_candidate.py -- <run_dir> <out_dir> [--fbx | --instances]

Default: opens <run_dir>/work/*-candidate.blend (authored frame, face -Y) and renders
  * orthographic front / back / left / right / top (whole figure with base);
  * two 3/4 game-camera frames (horizontal FOV 35 deg, pitch -55 deg, azimuth +-40 deg from the front) filling
    the frame, and front / 3/4 frames at game scale (1 m cell ~250 px across 1920 px, 04 §3);
  * close-ups: head front and 3/4, talons with the bracelet, wing root, wing tip, tail, base with the pips;
  * split view (Workbench flat colours: body red, base blue) and silhouettes.
--fbx: imports export/SK_*.fbx and SM_*.fbx, turns them back by the inverse UM_FBX_v1 rotation, assigns the atlas
material from textures/ and a flat base material, renders the ortho front frame (compare with the .blend frame).
--instances: three copies of the figure (mesh data shared, rest pose) on three adjacent 1 m cells, instance marks
1/2/3 (object property um_instance_index read by the base material), at K1 (12 m) and two K2-like distances
(7.5 m = 12 / 1.6 by the zoom factor of 03 §2; 4.8 m = «2-3 cells across» of the same row), facing the camera
and with mixed yaw; writes the projected pixel centre, projected radius
and camera visibility of every pip slot to instances-pips.json for analyse_instances.py.
All materials are single-sided (use_backface_culling) as in UE, so an inside-out face would render as a hole.
Lighting is a neutral preview (2 suns + grey world, Standard view transform), not the game lighting.
Nothing is saved to any .blend. Writes <out_dir>/review-frames[-fbx|-instances].json with every camera.
"""
import json
import math
import sys
from pathlib import Path

import bpy
from bpy_extras.object_utils import world_to_camera_view
from mathutils import Matrix, Vector

if not bpy.app.background:
    raise RuntimeError("review_harpy_candidate.py: headless only (blender -b)")

argv = sys.argv[sys.argv.index("--") + 1:]
RUN, OUT = Path(argv[0]).resolve(), Path(argv[1]).resolve()
FBX = "--fbx" in argv
INST = "--instances" in argv
OUT.mkdir(parents=True, exist_ok=True)
REPO = Path(__file__).resolve().parents[4]
frames = {}


def load_blend():
    blend = next((RUN / "work").glob("*-candidate.blend"))
    bpy.ops.wm.open_mainfile(filepath=str(blend))
    return blend.name


def load_fbx():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    for f in sorted((RUN / "export").glob("*.fbx")):
        bpy.ops.import_scene.fbx(filepath=str(f))
    inv = Matrix.Rotation(math.radians(-90.0), 4, "Z")
    for o in bpy.context.scene.objects:
        if o.parent is None:
            o.matrix_world = inv @ o.matrix_world
    tex = RUN / "textures"
    mat = bpy.data.materials.new("M_Review_Atlas")
    mat.use_nodes = True
    nt = mat.node_tree
    bsdf = next(n for n in nt.nodes if n.type == "BSDF_PRINCIPLED")
    imgs = {}
    for key in ("BC", "N_OpenGL", "ORM"):
        img = bpy.data.images.load(str(next(tex.glob("*_Atlas_%s.png" % key))))
        img.colorspace_settings.name = "sRGB" if key == "BC" else "Non-Color"
        node = nt.nodes.new("ShaderNodeTexImage")
        node.image = img
        imgs[key] = node
    nt.links.new(imgs["BC"].outputs["Color"], bsdf.inputs["Base Color"])
    nm = nt.nodes.new("ShaderNodeNormalMap")
    nt.links.new(imgs["N_OpenGL"].outputs["Color"], nm.inputs["Color"])
    nt.links.new(nm.outputs["Normal"], bsdf.inputs["Normal"])
    sep = nt.nodes.new("ShaderNodeSeparateColor")
    nt.links.new(imgs["ORM"].outputs["Color"], sep.inputs["Color"])
    nt.links.new(sep.outputs["Green"], bsdf.inputs["Roughness"])
    nt.links.new(sep.outputs["Blue"], bsdf.inputs["Metallic"])
    bmat = bpy.data.materials.new("M_Review_Base")
    bmat.use_nodes = True
    bb = next(n for n in bmat.node_tree.nodes if n.type == "BSDF_PRINCIPLED")
    vc = bmat.node_tree.nodes.new("ShaderNodeVertexColor")
    vc.layer_name = "UM_Mask"
    mix = bmat.node_tree.nodes.new("ShaderNodeMix")
    mix.data_type = "RGBA"
    a = next(s for s in mix.inputs if s.name == "A" and s.type == "RGBA")
    b = next(s for s in mix.inputs if s.name == "B" and s.type == "RGBA")
    fac = next(s for s in mix.inputs if s.name == "Factor" and s.type == "VALUE")
    a.default_value = (0.03, 0.026, 0.023, 1)
    b.default_value = (0.9, 0.9, 0.9, 1)
    gray = bmat.node_tree.nodes.new("ShaderNodeRGBToBW")
    bmat.node_tree.links.new(vc.outputs["Color"], gray.inputs["Color"])
    bmat.node_tree.links.new(gray.outputs["Val"], fac)
    bmat.node_tree.links.new(next(s for s in mix.outputs if s.name == "Result" and s.type == "RGBA"), bb.inputs["Base Color"])
    for o in bpy.context.scene.objects:
        if o.type == "MESH":
            o.data.materials.clear()
            o.data.materials.append(bmat if o.name.startswith("SM_") else mat)
    return "export/*.fbx (round trip, rotated back); base shown with a grey UM_Mask preview (not the instance material)"


source = load_fbx() if FBX else load_blend()
sc = bpy.context.scene
for o in list(sc.objects):
    if o.type in ("CAMERA", "LIGHT"):
        bpy.data.objects.remove(o)
for mat in bpy.data.materials:
    mat.use_backface_culling = True
meshes = {o.name: o for o in sc.objects if o.type == "MESH"}
body = next(o for n, o in meshes.items() if n.startswith("SK_Harpy_Body"))
base = next(o for n, o in meshes.items() if n.startswith("SM_Harpy_Base"))
arm = next((o for o in sc.objects if o.type == "ARMATURE"), None)

sc.render.engine = "BLENDER_EEVEE"
sc.view_settings.view_transform = "Standard"
sc.world = bpy.data.worlds.new("review_world")
sc.world.use_nodes = True
sc.world.node_tree.nodes["Background"].inputs[0].default_value = (0.5, 0.5, 0.5, 1)
sc.world.node_tree.nodes["Background"].inputs[1].default_value = 0.55
for name, rot, energy in (("key", (50, 0, -30), 3.0), ("fill", (60, 0, 150), 1.3)):
    light = bpy.data.lights.new(name, "SUN")
    light.energy = energy
    lo = bpy.data.objects.new(name, light)
    lo.rotation_euler = [math.radians(a) for a in rot]
    sc.collection.objects.link(lo)
cam = bpy.data.objects.new("review_cam", bpy.data.cameras.new("review_cam"))
sc.collection.objects.link(cam)
sc.camera = cam


def aim(direction, target, ortho=None, fov_h=None, distance=None, res=(1000, 1000)):
    d = Vector(direction).normalized()
    t = Vector(target)
    cam.data.type = "ORTHO" if ortho else "PERSP"
    if ortho:
        cam.data.ortho_scale = ortho
        cam.location = t + d * 3.0
    else:
        cam.data.sensor_fit = "HORIZONTAL"
        cam.data.angle = math.radians(fov_h)
        cam.location = t + d * distance
    cam.data.clip_start, cam.data.clip_end = 0.005, 60
    cam.rotation_euler = (-d).to_track_quat("-Z", "Y").to_euler()
    sc.render.resolution_x, sc.render.resolution_y = res
    bpy.context.view_layer.update()
    return d, t


def shoot(name, direction, target, ortho=None, fov_h=None, distance=None, res=(1000, 1000), hide=()):
    d, t = aim(direction, target, ortho, fov_h, distance, res)
    for o in hide:
        o.hide_render = True
    sc.render.filepath = str(OUT / ("%s.png" % name))
    bpy.ops.render.render(write_still=True)
    for o in hide:
        o.hide_render = False
    frames[name] = {"camera": "ortho" if ortho else "perspective", "direction_from_target": [round(c, 4) for c in d],
                    "target_m": [round(c, 4) for c in t], "ortho_scale_m": ortho, "horizontal_fov_deg": fov_h,
                    "distance_m": distance, "resolution": list(res), "hidden": [o.name for o in hide]}


def game_dir(azimuth_deg, pitch_deg=-55.0):
    """Direction from target to camera: azimuth 0 = in front of the figure (-Y), + = figure's left (+X)."""
    el = math.radians(-pitch_deg)
    az = math.radians(azimuth_deg)
    return (math.sin(az) * math.cos(el), -math.cos(az) * math.cos(el), math.sin(el))


def ground(cells, name="review_cells"):
    """1 m cells on the ground plane with a 2 cm dark border (board-like), z just below 0."""
    mats = []
    for tag, rgb in (("cell", (0.085, 0.095, 0.11)), ("border", (0.02, 0.02, 0.025))):
        m = bpy.data.materials.new("review_%s" % tag)
        m.use_nodes = True
        m.node_tree.nodes["Principled BSDF"].inputs["Base Color"].default_value = (*rgb, 1)
        m.node_tree.nodes["Principled BSDF"].inputs["Roughness"].default_value = 0.9
        mats.append(m)
    made = []
    for (cx, cy) in cells:
        bpy.ops.mesh.primitive_plane_add(size=1.0, location=(cx, cy, -0.0006))
        border = bpy.context.active_object
        border.data.materials.append(mats[1])
        bpy.ops.mesh.primitive_plane_add(size=0.96, location=(cx, cy, -0.0003))
        cell = bpy.context.active_object
        cell.data.materials.append(mats[0])
        made += [border, cell]
    return made


base_index_default = base.get("um_instance_index", 3.0)
if FBX:
    shoot("fbx_roundtrip_ortho_front", (0, -1, 0), (0, 0, 0.21), ortho=0.72, res=(1100, 800))
elif INST:
    fig_objs = [body, base]
    if arm is not None:
        arm.hide_render = True
    for mod in list(body.modifiers):
        if mod.type == "ARMATURE":
            body.modifiers.remove(mod)  # rest pose: the modifier is identity; copies must not follow one armature
    body.hide_render = base.hide_render = True
    for o in (body, base):  # also out of the ray casts that decide pip visibility
        o.matrix_world = Matrix.Translation((0.0, 0.0, -100.0)) @ o.matrix_world
    setups = {"facing": [0.0, 0.0, 0.0], "mixed_yaw": [35.0, -120.0, 150.0]}
    cells = [(-1.0, 0.0), (0.0, 0.0), (1.0, 0.0)]
    ground_objs = ground([(x, y) for x in (-1.0, 0.0, 1.0) for y in (-1.0, 0.0, 1.0)])
    pip_rec = {}
    bpy.context.view_layer.update()
    base_pips = []
    pc = None
    prof = json.loads((REPO / json.loads((RUN / "manifest.json").read_text(encoding="utf-8"))["config"]["build_profile"]).read_text(encoding="utf-8"))
    pc = prof["base_parametric"]["pips"]
    for sector in pc["sector_azimuths_deg"]:
        dphi = pc["arc_spacing_m"] / pc["ring_radius_m"]
        for slot, k in zip(pc["slots_per_sector"], (-1, 0, 1)):
            a = math.radians(sector) + k * dphi
            base_pips.append({"sector_deg": sector, "slot": slot,
                              "local": Vector((pc["ring_radius_m"] * math.cos(a), pc["ring_radius_m"] * math.sin(a),
                                               prof["base_parametric"]["height_m"] + pc["raise_m"]))})
    team = tuple(prof["base_parametric"]["preview_colours_linear"]["team_gold"]) + (1.0,)
    for setup, yaws in setups.items():
        copies = []
        for i, ((cx, cy), yaw) in enumerate(zip(cells, yaws)):
            for src in fig_objs:
                c = src.copy()
                c.data = src.data
                c.hide_render = False
                c.matrix_world = Matrix.Translation((cx, cy, 0.0)) @ Matrix.Rotation(math.radians(yaw), 4, "Z")
                c["um_instance_index"] = float(i + 1)
                c["um_team_color"] = team
                sc.collection.objects.link(c)
                copies.append((i + 1, src, c))
        bpy.context.view_layer.update()
        for kname, dist in (("k1", 12.0), ("k2", 7.5), ("k2close", 4.8)):
            name = "instances_%s_%s" % (setup, kname)
            shoot(name, game_dir(0), (0.0, 0.0, 0.12), fov_h=35, distance=dist, res=(1920, 1080))
            frames[name]["yaws_deg"] = yaws
            depsgraph = bpy.context.evaluated_depsgraph_get()
            recs = []
            for idx, src, c in copies:
                if not src.name.startswith("SM_Harpy_Base"):
                    continue
                mw = c.matrix_world
                for pip in base_pips:
                    wp = mw @ pip["local"]
                    ndc = world_to_camera_view(sc, cam, wp)
                    edge = mw @ (pip["local"] + Vector((pc["pip_radius_m"], 0, 0)))
                    ndc_e = world_to_camera_view(sc, cam, edge)
                    px = (ndc.x * 1920, (1 - ndc.y) * 1080)
                    pr = math.hypot((ndc_e.x - ndc.x) * 1920, (ndc_e.y - ndc.y) * 1080)
                    direction = (wp - cam.location).normalized()
                    hit, loc, _n, _i, hobj, _m = sc.ray_cast(depsgraph, cam.location, direction,
                                                           distance=(wp - cam.location).length + 0.01)
                    visible = bool(hit and hobj is not None and hobj.name == c.name and (loc - wp).length < pc["pip_radius_m"])
                    recs.append({"instance": idx, "yaw_deg": yaws[idx - 1], "sector_deg": pip["sector_deg"],
                                 "slot": pip["slot"], "px": [round(px[0], 2), round(px[1], 2)],
                                 "radius_px": round(pr, 2), "visible": visible,
                                 "occluder": None if visible else (hobj.name if hit and hobj else "none")})
                    # a sample of the unlit top just inside the pip (towards the base centre) for the contrast
                inner = mw @ Vector((0, 0, prof["base_parametric"]["height_m"]))
                ndc_c = world_to_camera_view(sc, cam, inner)
                recs.append({"instance": idx, "base_centre_px": [round(ndc_c.x * 1920, 2), round((1 - ndc_c.y) * 1080, 2)]})
            pip_rec[name] = recs
        for _idx, _src, c in copies:
            bpy.data.objects.remove(c)
    for o in ground_objs:
        bpy.data.objects.remove(o)
    (OUT / "instances-pips.json").write_text(json.dumps(pip_rec, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    source += " + three instances (rest pose copies, instance index 1/2/3, team gold)"
else:
    full = (0, 0, 0.21)
    shoot("ortho_front", (0, -1, 0), full, ortho=0.72, res=(1100, 800))
    shoot("ortho_back", (0, 1, 0), full, ortho=0.72, res=(1100, 800))
    shoot("ortho_left", (1, 0, 0), full, ortho=0.5, res=(900, 900))
    shoot("ortho_right", (-1, 0, 0), full, ortho=0.5, res=(900, 900))
    shoot("ortho_top", (0, 0, 1), (0, 0.03, 0.2), ortho=0.72, res=(1100, 800))
    vfov = 2 * math.atan(math.tan(math.radians(17.5)) * 9 / 16)
    fill_dist = 0.8 / (2 * math.tan(vfov / 2))
    game_dist = 1920 / (250 * 2 * math.tan(math.radians(17.5)))
    for az in (-40, 40):
        tag = "right" if az < 0 else "left"
        shoot("game_3q_%s_fill" % tag, game_dir(az), (0, 0.06, 0.22), fov_h=35, distance=fill_dist, res=(1920, 1080))
    cell_objs = ground([(0.0, 0.0)])
    shoot("game_3q_right_gamescale", game_dir(-40), (0, 0, 0.1), fov_h=35, distance=game_dist, res=(1920, 1080))
    shoot("game_front_gamescale", game_dir(0), (0, 0, 0.1), fov_h=35, distance=game_dist, res=(1920, 1080))
    for o in cell_objs:
        bpy.data.objects.remove(o)
    # close-ups
    shoot("closeup_head_front", (0, -1, 0), (0, -0.05, 0.335), ortho=0.15)
    shoot("closeup_head_3q", (-0.6, -0.8, 0.15), (0, -0.05, 0.335), ortho=0.15)
    shoot("closeup_talons_front", (0, -1, 0.35), (0, -0.03, 0.075), ortho=0.14, res=(1000, 800))
    shoot("closeup_talons_3q_left", (0.7, -0.7, 0.3), (0.035, -0.03, 0.075), ortho=0.1)
    shoot("closeup_wing_root_back", (0.35, 1, 0.45), (0.06, 0.02, 0.27), ortho=0.16)
    shoot("closeup_wing_tip_left", (0.2, -1, 0.1), (0.27, 0.12, 0.3), ortho=0.2)
    shoot("closeup_tail_back", (0.0, 1, 0.2), (0, 0.04, 0.15), ortho=0.18)
    for idx in (1, 2, 3):
        base["um_instance_index"] = float(idx)
        shoot("closeup_base_instance_%d" % idx, game_dir(0), (0, -0.02, 0.05), ortho=0.26, res=(1000, 700))
    base["um_instance_index"] = base_index_default
    # split view and silhouettes (Workbench flat colours)
    sc.render.engine = "BLENDER_WORKBENCH"
    sc.display.shading.light = "STUDIO"
    sc.display.shading.color_type = "OBJECT"
    body.color, base.color = (0.85, 0.25, 0.2, 1), (0.3, 0.45, 0.9, 1)
    shoot("split_meshes_front", (0, -1, 0), full, ortho=0.72, res=(1100, 800))
    sc.display.shading.light = "FLAT"
    sc.display.shading.color_type = "SINGLE"
    sc.display.shading.single_color = (0.0, 0.0, 0.0)
    sc.world.color = (1.0, 1.0, 1.0)
    shoot("silhouette_front", (0, -1, 0), full, ortho=0.72, res=(1100, 800))
    shoot("silhouette_game_3q_right", game_dir(-40), (0, 0.06, 0.22), fov_h=35, distance=fill_dist, res=(1920, 1080))
    shoot("silhouette_gamescale_front", game_dir(0), (0, 0, 0.1), fov_h=35, distance=game_dist, res=(1920, 1080))
    shoot("silhouette_gamescale_3q_right", game_dir(-40), (0, 0, 0.1), fov_h=35, distance=game_dist, res=(1920, 1080))
    shoot("silhouette_gamescale_front_no_base", game_dir(0), (0, 0, 0.1), fov_h=35, distance=game_dist,
          res=(1920, 1080), hide=(base,))

suffix = "-fbx" if FBX else "-instances" if INST else ""
(OUT / ("review-frames%s.json" % suffix)).write_text(
    json.dumps({"source": source, "lighting": "EEVEE preview: sun 3.0 (50,0,-30), sun 1.3 (60,0,150), world grey 0.55; "
                "Standard view transform; single-sided materials; not game lighting", "frames": frames},
               indent=1, sort_keys=True) + "\n", encoding="utf-8")
print("REVIEW_OK", len(frames))
