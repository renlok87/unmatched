"""Review frames of the Merlin candidate (headless only: blender -b --factory-startup). Merlin copy of
art/pipeline-candidates/ASSET-KING-ARTHUR-001/scripts/review_arthur_candidate.py (same lights, cameras, modes).

    blender -b --factory-startup --python review_merlin_candidate.py -- <run_dir> <out_dir> [--fbx | --team]

Default: opens <run_dir>/work/*-candidate.blend (authored frame, face -Y) and renders
  * orthographic front / back / left / right / top (whole figure with base);
  * two 3/4 game-camera frames (horizontal FOV 35 deg, pitch -55 deg, azimuth +-40 deg from the front),
    one filling the frame and one at game scale (figure ~125 px tall in 1920x1080, 03 §2 / 04 §3);
  * close-ups: head front and 3/4, right fist on the staff, the fist with the staff hidden (grip bridge
    and the fist's open ring), the staff alone, the staff bottom on the right shoe, the crystal, the left fist,
    the base;
  * split view: staff green, body red, base blue (Workbench flat colours); silhouettes.
--team: TeamColor preview of the .blend (optional mask textures/*_TeamMask.png, proposal), ortho front/back.
--fbx: imports export/SK_*.fbx and SM_*.fbx instead, turns them back by the inverse UM_FBX_v1 rotation,
assigns the atlas material from textures/ (FBX keeps bare names, path_mode STRIP) and renders the ortho
front frame only (compare with the .blend frame). Lighting is a neutral preview (2 suns + grey world,
Standard view transform), not the game lighting. Nothing is saved to any .blend.
Writes <out_dir>/review-frames.json with every camera.
"""
import json
import math
import sys
from pathlib import Path

import bpy
from mathutils import Matrix, Vector

if not bpy.app.background:
    raise RuntimeError("review_merlin_candidate.py: headless only (blender -b)")

argv = sys.argv[sys.argv.index("--") + 1:]
RUN, OUT = Path(argv[0]).resolve(), Path(argv[1]).resolve()  # absolute: Blender resolves relative paths from the drive root
FBX = "--fbx" in argv
OUT.mkdir(parents=True, exist_ok=True)
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
    for o in bpy.context.scene.objects:
        if o.type == "MESH":
            o.data.materials.clear()
            o.data.materials.append(mat)
    return "export/*.fbx (round trip, rotated back)"


source = load_fbx() if FBX else load_blend()
sc = bpy.context.scene
for o in list(sc.objects):
    if o.type in ("CAMERA", "LIGHT"):
        bpy.data.objects.remove(o)
meshes = {o.name: o for o in sc.objects if o.type == "MESH"}
body = next(o for n, o in meshes.items() if n.startswith("SK_Merlin_Body"))
staff = next(o for n, o in meshes.items() if n.startswith("SK_Merlin_Staff"))
base = next(o for n, o in meshes.items() if n.startswith("SM_Merlin_Base"))

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


def shoot(name, direction, target, ortho=None, fov_h=None, distance=None, res=(1000, 1000), hide=()):
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
    cam.data.clip_start, cam.data.clip_end = 0.005, 50
    cam.rotation_euler = (-d).to_track_quat("-Z", "Y").to_euler()
    sc.render.resolution_x, sc.render.resolution_y = res
    for o in hide:
        o.hide_render = True
    sc.render.filepath = str(OUT / ("%s.png" % name))
    bpy.ops.render.render(write_still=True)
    for o in hide:
        o.hide_render = False
    frames[name] = {"camera": "ortho" if ortho else "perspective", "direction_from_target": [round(c, 4) for c in d],
                    "target_m": [round(c, 4) for c in t], "ortho_scale_m": ortho, "horizontal_fov_deg": fov_h,
                    "distance_m": distance, "resolution": list(res),
                    "hidden": [o.name for o in hide]}


def game_dir(azimuth_deg, pitch_deg=-55.0):
    """Direction from target to camera: azimuth 0 = in front of the figure (-Y), + = figure's left (+X)."""
    el = math.radians(-pitch_deg)
    az = math.radians(azimuth_deg)
    return (math.sin(az) * math.cos(el), -math.cos(az) * math.cos(el), math.sin(el))


if "--team" in argv:
    # TeamColor preview (proposal): BaseColor = lerp(BC, luminance(BC) * TeamColor * k, TeamMask)
    mat = body.data.materials[0]
    nt = mat.node_tree
    bsdf = next(n for n in nt.nodes if n.type == "BSDF_PRINCIPLED")
    bc = next(n for n in nt.nodes if n.type == "TEX_IMAGE" and n.label == "BC")
    mimg = bpy.data.images.load(str(next((RUN / "textures").glob("*_TeamMask.png"))))
    mimg.colorspace_settings.name = "Non-Color"
    mnode = nt.nodes.new("ShaderNodeTexImage")
    mnode.image = mimg
    bw = nt.nodes.new("ShaderNodeRGBToBW")
    nt.links.new(bc.outputs["Color"], bw.inputs["Color"])
    team = nt.nodes.new("ShaderNodeRGB")
    tint = nt.nodes.new("ShaderNodeMix")
    tint.data_type = "RGBA"
    tint.blend_type = "MULTIPLY"
    tint.inputs["Factor"].default_value = 1.0
    nt.links.new(team.outputs["Color"], tint.inputs["A"])
    scale = nt.nodes.new("ShaderNodeMath")
    scale.operation = "MULTIPLY"
    scale.inputs[1].default_value = 4.5
    nt.links.new(bw.outputs["Val"], scale.inputs[0])
    comb = nt.nodes.new("ShaderNodeCombineColor")
    for ch in ("Red", "Green", "Blue"):
        nt.links.new(scale.outputs["Value"], comb.inputs[ch])
    nt.links.new(comb.outputs["Color"], tint.inputs["B"])
    mix = nt.nodes.new("ShaderNodeMix")
    mix.data_type = "RGBA"
    nt.links.new(mnode.outputs["Color"], mix.inputs["Factor"])
    nt.links.new(bc.outputs["Color"], mix.inputs["A"])
    nt.links.new(tint.outputs["Result"], mix.inputs["B"])
    nt.links.new(mix.outputs["Result"], bsdf.inputs["Base Color"])
    for tag, rgb in (("silver", (0.62, 0.76, 0.85)), ("gold", (0.91, 0.76, 0.42))):
        team.outputs["Color"].default_value = (*rgb, 1.0)
        shoot("teamcolor_%s_ortho_front" % tag, (0, -1, 0), (0, 0, 0.25), ortho=0.56, res=(900, 1000))
        shoot("teamcolor_%s_ortho_back" % tag, (0, 1, 0), (0, 0, 0.25), ortho=0.56, res=(900, 1000))
    source += " + TeamColor preview (k 4.5, С-11 silver (0.62,0.76,0.85) / gold (0.91,0.76,0.42))"
elif FBX:
    shoot("fbx_roundtrip_ortho_front", (0, -1, 0), (0, 0, 0.25), ortho=0.56, res=(900, 1000))
else:
    full = (0, 0, 0.25)
    shoot("ortho_front", (0, -1, 0), full, ortho=0.56, res=(900, 1000))
    shoot("ortho_back", (0, 1, 0), full, ortho=0.56, res=(900, 1000))
    shoot("ortho_left", (1, 0, 0), full, ortho=0.56, res=(900, 1000))
    shoot("ortho_right", (-1, 0, 0), full, ortho=0.56, res=(900, 1000))
    shoot("ortho_top", (0, 0, 1), (0, 0, 0.25), ortho=0.3, res=(900, 900))
    # 3/4 game camera: FOV 35 (horizontal), pitch -55; fill frame and game scale
    vfov = 2 * math.atan(math.tan(math.radians(17.5)) * 9 / 16)
    fill_dist = 0.46 / (2 * math.tan(vfov / 2))
    # game scale per 04 §3: a 1 m cell spans ~250 px across 1920 px at the target (horizontal FOV 35)
    game_dist = 1920 / (250 * 2 * math.tan(math.radians(17.5)))
    for az in (-40, 40):
        tag = "right" if az < 0 else "left"
        shoot("game_3q_%s_fill" % tag, game_dir(az), (0, 0, 0.23), fov_h=35, distance=fill_dist, res=(1920, 1080))
    # 1 m cell outline on the ground for the game-scale frames only
    bpy.ops.mesh.primitive_plane_add(size=1.0, location=(0, 0, -0.0005))
    cell = bpy.context.active_object
    cell.name = "review_cell_1m"
    cm = bpy.data.materials.new("review_cell")
    cm.diffuse_color = (0.36, 0.36, 0.36, 1)
    cm.use_nodes = True
    cm.node_tree.nodes["Principled BSDF"].inputs["Base Color"].default_value = (0.3, 0.3, 0.3, 1)
    cell.data.materials.append(cm)
    shoot("game_3q_right_gamescale", game_dir(-40), (0, 0, 0.1), fov_h=35, distance=game_dist, res=(1920, 1080))
    shoot("game_front_gamescale", game_dir(0), (0, 0, 0.1), fov_h=35, distance=game_dist, res=(1920, 1080))
    bpy.data.objects.remove(cell)
    # close-ups
    shoot("closeup_head_front", (0, -1, 0), (0, -0.015, 0.375), ortho=0.13)
    shoot("closeup_head_3q", (-0.6, -0.8, 0.15), (0, -0.015, 0.375), ortho=0.13)
    shoot("closeup_right_fist_staff", (-0.5, -0.85, 0.15), (-0.08, 0.0, 0.32), ortho=0.09)
    shoot("closeup_right_fist_no_staff", (-0.5, -0.85, 0.15), (-0.08, 0.0, 0.32), ortho=0.09, hide=(staff,))
    shoot("closeup_right_fist_back", (0.2, 1, 0.15), (-0.08, 0.0, 0.32), ortho=0.09)
    shoot("closeup_staff_grip_no_body", (0.6, -0.8, 0.1), (-0.08, 0.0, 0.32), ortho=0.09, hide=(body, base))
    shoot("closeup_staff_only", (-0.3, -1, 0.0), (-0.08, 0.0, 0.28), ortho=0.5, hide=(body, base))
    shoot("closeup_staff_bottom_on_shoe", (-0.5, -0.85, 0.25), (-0.065, -0.005, 0.065), ortho=0.07)
    shoot("closeup_staff_bottom_cap", (-0.3, -0.5, -0.8), (-0.07, -0.005, 0.07), ortho=0.05, hide=(body, base))
    shoot("closeup_crystal", (-0.4, -0.9, 0.2), (-0.08, 0.0, 0.47), ortho=0.07)
    shoot("closeup_left_fist", (0.4, -0.9, 0.15), (0.03, -0.04, 0.27), ortho=0.08)
    shoot("closeup_feet_front", (0, -1, 0.3), (0.0, -0.02, 0.07), ortho=0.2, res=(1000, 700))
    shoot("closeup_base", game_dir(-20, -35), (0, 0, 0.03), ortho=0.3, res=(1000, 700))
    # split view (Workbench flat colours)
    sc.render.engine = "BLENDER_WORKBENCH"
    sc.display.shading.light = "STUDIO"
    sc.display.shading.color_type = "OBJECT"
    body.color, staff.color, base.color = (0.85, 0.25, 0.2, 1), (0.2, 0.85, 0.35, 1), (0.3, 0.45, 0.9, 1)
    shoot("split_meshes_front", (0, -1, 0), full, ortho=0.56, res=(900, 1000))
    shoot("split_fist_closeup", (-0.5, -0.85, 0.15), (-0.08, 0.0, 0.32), ortho=0.09)
    # silhouette without colour (04 §3.4: «колпак+посох» — vertical with an offset staff diagonal)
    sc.display.shading.light = "FLAT"
    sc.display.shading.color_type = "SINGLE"
    sc.display.shading.single_color = (0.0, 0.0, 0.0)
    sc.world.color = (1.0, 1.0, 1.0)
    shoot("silhouette_front", (0, -1, 0), full, ortho=0.56, res=(600, 660))
    shoot("silhouette_game_3q_right", game_dir(-40), (0, 0, 0.23), fov_h=35, distance=fill_dist, res=(1920, 1080))

(OUT / ("review-frames%s.json" % ("-team" if "--team" in argv else "-fbx" if FBX else ""))).write_text(
    json.dumps({"source": source, "lighting": "EEVEE preview: sun 3.0 (50,0,-30), sun 1.3 (60,0,150), world grey 0.55; "
                "Standard view transform; not game lighting", "frames": frames}, indent=1, sort_keys=True) + "\n",
    encoding="utf-8")
print("REVIEW_OK", len(frames))
