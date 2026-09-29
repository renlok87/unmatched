"""Game-camera and ortho previews of the exported tray FBX, with the ART-005 board FBX as context.

Headless only (never touches live Blender sessions):
  blender -b --factory-startup --python-exit-code 1 \
      --python art/pipeline-candidates/ASSET-TABLE-BASE-001/scripts/table_base_preview.py -- \
      <tray.fbx> <texture_prefix_path> <out_dir> [board.fbx]

<texture_prefix_path> = path without suffix (.../export/T_TableBase -> _BC/_N/_ORM.png). The tray material is
rebuilt from the delivered triplet the way UE reads it: BC sRGB, N Linear DirectX (green flipped back for
Blender), ORM Linear (R AO multiplied into base colour for the preview, G roughness, B metallic). The board
gets flat provisional colours per slot kind (stone / wood / undertray) so the tray reads against it.

Frame: both FBX are read back in the UM_FBX_v1 export frame (UE shows it as x, -y, z); long board side = X.
Game camera (03 section 2, PROPOSED; 04 section 4.4): 16:9 frame, horizontal FOV 35 (sensor_fit HORIZONTAL,
vertical FOV ~20.1, half 10.06), pitch -55. K1 = start camera: 12 m from the board centre, "south" = camera on
export -Y (= UE +Y looking along -Y, yaw -90 of 03) in the MESH frame; the ART-005 actor rotation in the level
is not applied here (UE step deferred). Zoom 0.65x is read as magnification (03: "0.65x = the whole board with
margins and the tray") = 12 / 0.65 = 18.5 m; that frame is the zoom-out limit, not K1. North/east shots use the
same camera from other sides only to inspect the asset (the game yaw is fixed).

Outputs (JPEG, <= 1200 px):
  <name>_k1-south-d12m.jpg                      1200x675 16:9 - K1
  <name>_game-{north,east}-d12m.jpg             1200x675 16:9 - K1 camera from other sides (inspection)
  <name>_game-south-zoom065-d18.5m.jpg          1200x675 16:9 - zoom-out limit 0.65x
  <name>_game-south-zoom{12,16}-follow-nearrow-*  1200x675 16:9 - zoom 1.2x / 1.6x with follow-selection centred on
                                                the near row of cells (03 section 2); only with the board FBX
  <name>_context4x3-notK1-south-d{12,18.5}m.jpg 1200x900 4:3, NOT K1: the rows outside the 16:9 band are
                                                dimmed and the band edges are drawn in yellow (rows 112/787)
  <name>_ortho-*.jpg                            1200x900 orthographic
  <name>_preview.json                           per-shot frame measurement: tray / top outline / board /
                                                board tiles extents in frame, key edge points in degrees from
                                                the optical axis, how deep the near skirt stays inside the
                                                frame, and the visible play-plane span on the centre column.
Measurement only.
"""
import json
import math
import sys
from pathlib import Path

import bpy
import numpy as np
from bpy_extras.object_utils import world_to_camera_view
from mathutils import Vector

args = sys.argv[sys.argv.index("--") + 1:]
fbx, tex_prefix, out = Path(args[0]), args[1], Path(args[2])
board_fbx = Path(args[3]) if len(args) > 3 else None
out.mkdir(parents=True, exist_ok=True)
FOV, PITCH, DIST = 35.0, 55.0, 12.0
GAME_RES = (1200, 675)     # 16:9 game frame (04 section 4.4; D-07 1080p), <= 1200 px
CONTEXT_RES = (1200, 900)  # 4:3 context only (NOT K1), 16:9 band overlaid
ORTHO_RES = (1200, 900)
TOP_TOL_M = 0.005          # 0.5 uu: vertices this close to the tray max Z form the top outline

bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.fbx(filepath=str(fbx))
tray = [o for o in bpy.context.scene.objects if o.type == "MESH"]
name = fbx.stem


def img(suffix, colorspace):
    im = bpy.data.images.load("%s_%s.png" % (tex_prefix, suffix))
    im.colorspace_settings.name = colorspace
    return im


mat = bpy.data.materials.new("PreviewFromTriplet")
mat.use_nodes = True
nt = mat.node_tree
bsdf = nt.nodes["Principled BSDF"]
bc = nt.nodes.new("ShaderNodeTexImage"); bc.image = img("BC", "sRGB")
orm = nt.nodes.new("ShaderNodeTexImage"); orm.image = img("ORM", "Non-Color")
nrm = nt.nodes.new("ShaderNodeTexImage"); nrm.image = img("N", "Non-Color")
sep = nt.nodes.new("ShaderNodeSeparateColor")
mix_ao = nt.nodes.new("ShaderNodeMix"); mix_ao.data_type = "RGBA"; mix_ao.blend_type = "MULTIPLY"
mix_ao.inputs["Factor"].default_value = 1.0
nsep = nt.nodes.new("ShaderNodeSeparateColor")
inv = nt.nodes.new("ShaderNodeMath"); inv.operation = "SUBTRACT"; inv.inputs[0].default_value = 1.0
ncomb = nt.nodes.new("ShaderNodeCombineColor")
nmap = nt.nodes.new("ShaderNodeNormalMap")
L = nt.links.new
L(orm.outputs["Color"], sep.inputs["Color"])
L(bc.outputs["Color"], mix_ao.inputs["A"])
L(sep.outputs["Red"], mix_ao.inputs["B"])
L(mix_ao.outputs["Result"], bsdf.inputs["Base Color"])
L(sep.outputs["Green"], bsdf.inputs["Roughness"])
L(sep.outputs["Blue"], bsdf.inputs["Metallic"])
L(nrm.outputs["Color"], nsep.inputs["Color"])
L(nsep.outputs["Green"], inv.inputs[1])  # DirectX -> OpenGL
L(nsep.outputs["Red"], ncomb.inputs["Red"])
L(inv.outputs["Value"], ncomb.inputs["Green"])
L(nsep.outputs["Blue"], ncomb.inputs["Blue"])
L(ncomb.outputs["Color"], nmap.inputs["Color"])
L(nmap.outputs["Normal"], bsdf.inputs["Normal"])
for o in tray:
    o.data.materials.clear()
    o.data.materials.append(mat)

board = []
if board_fbx:
    before = set(bpy.context.scene.objects)
    bpy.ops.import_scene.fbx(filepath=str(board_fbx))
    board = [o for o in bpy.context.scene.objects if o not in before and o.type == "MESH"]
    flat = {}
    for kind, rgb in (("Stone", (0.30, 0.32, 0.35)), ("Wood", (0.26, 0.18, 0.11)), ("Undertray", (0.10, 0.10, 0.11))):
        m = bpy.data.materials.new("Board_%s_flat" % kind)
        m.use_nodes = True
        m.node_tree.nodes["Principled BSDF"].inputs["Base Color"].default_value = rgb + (1.0,)
        m.node_tree.nodes["Principled BSDF"].inputs["Roughness"].default_value = 0.8
        flat[kind] = m
    for o in board:
        for i, slot in enumerate(o.material_slots):
            kind = next((k for k in flat if slot.material and k in slot.material.name), "Stone")
            o.material_slots[i].material = flat[kind]

scene = bpy.context.scene
try:
    scene.render.engine = "BLENDER_EEVEE_NEXT"
except TypeError:
    scene.render.engine = "BLENDER_EEVEE"
scene.render.image_settings.file_format = "JPEG"
scene.render.image_settings.quality = 90
scene.view_settings.view_transform = "Standard"
world = bpy.data.worlds.new("World"); scene.world = world
world.use_nodes = True
bg = world.node_tree.nodes["Background"]
bg.inputs["Color"].default_value = (0.05, 0.05, 0.06, 1)  # 03 C-10: darkness beyond the tray
bg.inputs["Strength"].default_value = 1.0
for nm, energy, rot in (("Key", 3.5, (50, 0, 35)), ("Fill", 1.0, (60, 0, -140))):
    ld = bpy.data.lights.new(nm, "SUN"); ld.energy = energy
    lo_ = bpy.data.objects.new(nm, ld); scene.collection.objects.link(lo_)
    lo_.rotation_euler = tuple(math.radians(v) for v in rot)


def world_pts(objs):
    return [o.matrix_world @ v.co for o in objs for v in o.data.vertices]


def bounds(pts):
    lo = Vector((min(p.x for p in pts), min(p.y for p in pts), min(p.z for p in pts)))
    hi = Vector((max(p.x for p in pts), max(p.y for p in pts), max(p.z for p in pts)))
    return lo, hi


tray_pts = world_pts(tray)
lo, hi = bounds(tray_pts)
top_pts = [p for p in tray_pts if p.z >= hi.z - TOP_TOL_M]
board_pts = world_pts(board) if board else []
tile_pts = world_pts([o for o in board if "Tile" in o.name])  # ART-005 StoneTile_* = the play cells
board_lo, board_hi = bounds(board_pts) if board_pts else (None, None)
cd = bpy.data.cameras.new("Cam")
cam = bpy.data.objects.new("Cam", cd); scene.collection.objects.link(cam); scene.camera = cam
half_v_16x9 = math.degrees(math.atan(math.tan(math.radians(FOV / 2)) * GAME_RES[1] / GAME_RES[0]))
report = {"fbx": fbx.name, "board_fbx": board_fbx.name if board_fbx else None,
          "tray_bounds_uu": {"min": [round(v * 100, 3) for v in lo], "max": [round(v * 100, 3) for v in hi]},
          "tray_top_outline_vertices": len(top_pts),
          "material": "rebuilt from %s_{BC,N,ORM}.png (N DirectX->OpenGL, AO multiplied)" % Path(tex_prefix).name,
          "frame": "UM_FBX_v1 export frame (UE: x, -y, z); board actor rotation not applied",
          "game_frame": {"resolution": list(GAME_RES), "aspect": "16:9", "fov_h_deg": FOV, "sensor_fit": "HORIZONTAL",
                         "fov_v_deg": round(2 * half_v_16x9, 3), "half_fov_v_deg": round(half_v_16x9, 3),
                         "source": "03 section 2 (PROPOSED), 04 section 4.4 (vertical FOV ~20 at 16:9)"},
          "angle_convention": "up_deg > 0 = above the frame centre (far side for a camera looking down), "
                              "right_deg > 0 = right of centre; in_frame = inside the rendered frame",
          "shots": {}}


def set_resolution(res):
    scene.render.resolution_x, scene.render.resolution_y = res
    scene.render.resolution_percentage = 100


def place(loc, target):
    cam.location = loc
    cam.rotation_euler = (target - loc).to_track_quat("-Z", "Y").to_euler()
    bpy.context.view_layer.update()


def render(key):
    path = out / ("%s_%s.jpg" % (name, key))
    scene.render.filepath = str(path)
    bpy.ops.render.render(write_still=True)
    return path


def frame_angles(p):
    """Normalised frame coords -> degrees from the optical axis (tangent-plane, exact on the centre column)."""
    v = world_to_camera_view(scene, cam, p)
    rx, ry = scene.render.resolution_x, scene.render.resolution_y
    th = math.tan(math.radians(FOV / 2))
    tv = th * ry / rx
    return v, math.degrees(math.atan((v.y - 0.5) * 2 * tv)), math.degrees(math.atan((v.x - 0.5) * 2 * th))


def in_frame(v):
    return v.z > 0 and 0.0 <= v.x <= 1.0 and 0.0 <= v.y <= 1.0


def extents(pts):
    vs = [frame_angles(p) for p in pts]
    inside = sum(1 for v, _, _ in vs if in_frame(v))
    ups = [u for _, u, _ in vs]
    rights = [r for _, _, r in vs]
    xs = [v.x for v, _, _ in vs]
    ys = [v.y for v, _, _ in vs]
    return {"vertices": len(pts), "in_frame_frac": round(inside / len(pts), 4),
            "up_deg": [round(min(ups), 2), round(max(ups), 2)], "right_deg": [round(min(rights), 2), round(max(rights), 2)],
            "cut": {"bottom_near": min(ys) < 0, "top_far": max(ys) > 1, "left": min(xs) < 0, "right": max(xs) > 1}}


def key_point(p):
    v, up, right = frame_angles(p)
    return {"world_uu": [round(c * 100, 1) for c in p], "up_deg": round(up, 2), "right_deg": round(right, 2),
            "in_frame": in_frame(v)}


def near_skirt_limit(p_top, z_floor):
    """On the vertical line under p_top: the Z (uu) where the line leaves the bottom of the frame."""
    v_top = frame_angles(p_top)[0]
    if v_top.y < 0:
        return {"z_uu": None, "note": "the top edge itself is below the frame bottom (cut)"}
    bottom = Vector((p_top.x, p_top.y, z_floor))
    if frame_angles(bottom)[0].y >= 0:
        return {"z_uu": round(z_floor * 100, 1), "note": "whole line down to the tray min Z is in frame"}
    a, b = p_top.z, z_floor
    for _ in range(40):
        m = (a + b) / 2
        if frame_angles(Vector((p_top.x, p_top.y, m)))[0].y >= 0:
            a = m
        else:
            b = m
    return {"z_uu": round(a * 100, 1), "depth_below_top_uu": round((p_top.z - a) * 100, 1),
            "note": "deeper than this the near skirt under the top-outline edge is outside the frame"}


def play_plane_visible(u, target):
    """Centre column on the play plane Z=0: where it leaves the frame, as signed distance along u (towards the
    camera) from the board centre."""
    t0 = target.dot(u)

    def edge(sign, inside):
        a, b = 0.0, 20.0
        for _ in range(50):
            m = (a + b) / 2
            if inside(frame_angles(target + u * (sign * m))[0]):
                a = m
            else:
                b = m
        return round((t0 + sign * a) * 100, 1)
    return {"near_uu": edge(1.0, lambda v: v.y >= 0), "far_uu": edge(-1.0, lambda v: v.y <= 1),
            "note": "distance from the board centre along the camera direction (near > 0); camera-target column"}


def measure(az_deg, target):
    u = Vector((math.cos(math.radians(az_deg)), math.sin(math.radians(az_deg)), 0.0))  # towards the camera
    top_d = [p.dot(u) for p in top_pts]
    top_z = hi.z
    m = {"tray": extents(tray_pts), "tray_top_outline": extents(top_pts),
         "key_points": {"tray_top_near_edge_mid": key_point(u * max(top_d) + Vector((0, 0, top_z))),
                        "tray_top_far_edge_mid": key_point(u * min(top_d) + Vector((0, 0, top_z)))}}
    m["near_skirt_limit"] = near_skirt_limit(u * max(top_d) + Vector((0, 0, top_z)), lo.z)
    m["play_plane_centre_column_visible"] = play_plane_visible(u, target)
    if board_pts:
        b_d = [p.dot(u) for p in board_pts]
        m["board"] = extents(board_pts)
        if tile_pts:
            m["board_tiles"] = extents(tile_pts)
        m["key_points"]["board_near_edge_mid_bbox_top"] = key_point(u * max(b_d) + Vector((0, 0, board_hi.z)))
        m["key_points"]["board_far_edge_mid_bbox_top"] = key_point(u * min(b_d) + Vector((0, 0, board_hi.z)))
    return m


def overlay_16x9_band(jpg_path):
    """4:3 context JPEG: dim the rows outside the central 16:9 band (same horizontal FOV) and draw its edges."""
    w, h = scene.render.resolution_x, scene.render.resolution_y
    im = bpy.data.images.load(str(jpg_path))
    px = np.empty(w * h * 4, dtype=np.float32)
    im.pixels.foreach_get(px)
    a = px.reshape(h, w, 4)[::-1]  # view with row 0 = top of the picture
    band = round(w * 9 / 16)
    top = (h - band) // 2
    bot = top + band - 1
    a[:top, :, :3] *= 0.4
    a[bot + 1:, :, :3] *= 0.4
    for r in (top - 1, top, bot, bot + 1):
        a[r, :, :3] = (1.0, 0.82, 0.0)
    im.pixels.foreach_set(px)
    im.file_format = "JPEG"
    im.filepath_raw = str(jpg_path)
    im.save(quality=90)
    bpy.data.images.remove(im)
    return {"band_rows_from_top": [top, bot], "band_height_px": band}


def set_hidden(objs, hidden):
    for o in objs:
        o.hide_render = hidden


origin = Vector((0.0, 0.0, 0.0))  # board centre on the play plane
cd.type = "PERSP"; cd.sensor_fit = "HORIZONTAL"; cd.angle = math.radians(FOV)


def cam_loc(az, dist):
    p, a = math.radians(PITCH), math.radians(az)
    return Vector((math.cos(p) * math.cos(a), math.cos(p) * math.sin(a), math.sin(p))) * dist


set_resolution(GAME_RES)
game_shots = [("k1-south-d12m", -90.0, DIST, origin, "K1 (start camera, 16:9)"),
              ("game-north-d12m", 90.0, DIST, origin, "K1 camera from the north - asset inspection, not K1"),
              ("game-east-d12m", 0.0, DIST, origin, "K1 camera from the east - asset inspection, not K1"),
              ("game-south-zoom065-d18.5m", -90.0, DIST / 0.65, origin, "zoom-out limit 0.65x (16:9), not K1")]
if tile_pts:
    # 03 section 2: at zoom >= 1.2x the camera centres on the last selected object. Worst case for the near
    # skirt: a figure in the near row of cells (cell 100 uu -> row centre 0.5 m inside the near tile edge).
    south = Vector((0.0, -1.0, 0.0))
    near_row = south * (max(p.dot(south) for p in tile_pts) - 0.5)
    for zoom in (1.2, 1.6):
        game_shots.append(("game-south-zoom%s-follow-nearrow-d%sm" % (str(zoom).replace(".", ""), round(DIST / zoom, 2)),
                           -90.0, DIST / zoom, near_row,
                           "follow-selection at zoom %.1fx (03 section 2), target = near-row cell centre, not K1" % zoom))
for key, az, dist, target, role in game_shots:
    place(target + cam_loc(az, dist), target)
    shot = {"role": role, "k1": key.startswith("k1-"), "resolution": list(GAME_RES), "aspect": "16:9",
            "fov_h_deg": FOV, "fov_v_deg": round(2 * half_v_16x9, 3), "pitch_deg": -PITCH,
            "camera_azimuth_deg_export_frame": az, "distance_m": round(dist, 3),
            "target_uu": [round(c * 100, 1) for c in target], "board": bool(board)}
    shot["measure"] = measure(az, target)
    shot["file"] = render(key).name
    report["shots"][key] = shot

set_resolution(CONTEXT_RES)
for key, dist in (("context4x3-notK1-south-d12m", DIST), ("context4x3-notK1-south-d18.5m", DIST / 0.65)):
    place(cam_loc(-90.0, dist), origin)
    path = render(key)
    report["shots"][key] = {"role": "NOT K1: 4:3 context; rows outside the 16:9 band dimmed, band edges yellow",
                            "k1": False, "resolution": list(CONTEXT_RES), "aspect": "4:3", "fov_h_deg": FOV,
                            "pitch_deg": -PITCH, "camera_azimuth_deg_export_frame": -90.0, "distance_m": round(dist, 3),
                            "board": bool(board), "overlay_16x9": overlay_16x9_band(path), "file": path.name}

set_resolution(ORTHO_RES)
cd.type = "ORTHO"
size = max(hi - lo)
cd.ortho_scale = size * 1.1
centre = (lo + hi) / 2
place(centre + Vector((0, 0.0001, 1)) * size * 4, centre)
report["shots"]["ortho-top-with-board"] = {"file": render("ortho-top-with-board").name, "k1": False,
                                           "resolution": list(ORTHO_RES), "ortho_scale_m": round(cd.ortho_scale, 3)}
set_hidden(board, True)
for key, d in (("ortho-front-minusY", Vector((0, -1, 0))), ("ortho-side-plusX", Vector((1, 0, 0))),
               ("ortho-bottom", Vector((0, 0.0001, -1)))):
    place(centre + d * size * 4, centre)
    report["shots"][key] = {"file": render(key).name, "k1": False, "resolution": list(ORTHO_RES),
                            "ortho_scale_m": round(cd.ortho_scale, 3), "board": False}
(out / ("%s_preview.json" % name)).write_text(json.dumps(report, indent=2), encoding="utf-8")
print("PREVIEW_REPORT", json.dumps(report))
