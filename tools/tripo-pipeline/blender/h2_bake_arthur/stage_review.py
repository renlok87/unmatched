"""Stage review (headless): EEVEE frames of the H2 game mesh with its baked PBR atlas (all frames are Blender renders,
labelled "blender" by the sheets stage) + silhouette measurements for the triangle-budget argument.

    blender -b --factory-startup --python stage_review.py -- <profile.json> <run_dir>

Frames (work/frames_png/*.png -> labelled JPEG in preview/frames by stage sheets; 1:1 renders, sRGB "Standard" view transform, neutral studio light, not the game light):
  ortho_{front,left,back}  orthographic, framed like the H2 concepts (9:10, base bottom at 96.2 %, sword tip 4.2 %)
  close_*                  face, right fist + hilt, left hand, blade, base, back of the cloak
  game_K1_*, game_K2_*     FOV 35 (horizontal), pitch -55; K1 = 1 m cell ~ 250 px on 1920 px (04 §3), K2 = K1 x 1.6
                           zoom (03 proposal); the previous candidate (profile review.previous) is rendered alone on the
                           same spot with the same camera (equal scale, *_prev frames)
  game_K2S05_*             FOV 20, 3.0 m, pitch -55 (S05 K-2 measurement: 300 uu)
Silhouettes (work/silhouettes_png/*.png, sheet in preview/): high-poly (repaired, same seat) vs game mesh vs a x0.5 collapse copy (LOD1
proxy) at the game cameras; XOR pixels -> reports/review-report.json.
"""

import math
import sys
import time
from pathlib import Path

import bpy
import numpy as np
from mathutils import Matrix, Vector

sys.path.insert(0, str(Path(__file__).resolve().parent))
import bl  # noqa: E402
import pure as P  # noqa: E402
import repairs  # noqa: E402
from candidate_build import core as CB  # noqa: E402

bl.require_background("stage_review.py")
args = bl.script_args()
PROFILE_PATH, RUN = Path(args[0]).resolve(), Path(args[1]).resolve()
profile = P.load_json(PROFILE_PATH)
paths = P.run_paths(RUN)
rv_cfg = profile["review"]
FR = paths["work"] / "frames_png"      # raw renders; stage sheets writes labelled JPEGs to preview/frames
SI = paths["work"] / "silhouettes_png"
FR.mkdir(parents=True, exist_ok=True)
SI.mkdir(parents=True, exist_ok=True)
t0 = time.time()
rig_rep = P.load_json(paths["reports"] / "rig-report.json")

bpy.ops.wm.open_mainfile(filepath=str(paths["work"] / "h2-rig-authored.blend"))
scene = bpy.context.scene
names = profile["rig"]["objects"]
body, sword, base = (bpy.data.objects[names[k]] for k in ("body", "weapon", "base"))
arm = next(o for o in scene.objects if o.type == "ARMATURE")
arm.hide_render = True
ours = [body, sword, base]

# ------------------------------------------------------------------ previous candidate (next cell, same light)
prev_cfg = rv_cfg["previous"]
prev_objs = []
before = set(bpy.data.objects)
bpy.ops.import_scene.fbx(filepath=str(P.repo_path(prev_cfg["skeletal_fbx"])))
bpy.ops.import_scene.fbx(filepath=str(P.repo_path(prev_cfg["base_fbx"])))
new = [o for o in bpy.data.objects if o not in before]
inv = Matrix.Rotation(math.radians(-90.0), 4, "Z")
offset = Matrix.Translation(Vector(prev_cfg["offset_m"]))
for o in new:
    if o.parent is None:
        o.matrix_world = offset @ inv @ o.matrix_world
bpy.context.view_layer.update()
pmat = bpy.data.materials.new("PREV_ATLAS")
pmat.use_nodes = True


def pbr_material(mat, tex, pre):
    nt = mat.node_tree
    bsdf = next(n for n in nt.nodes if n.bl_idname == "ShaderNodeBsdfPrincipled")

    def node(key, colour):
        img = bpy.data.images.load(str(P.repo_path(tex) / (pre + key + ".png")), check_existing=True)
        img.colorspace_settings.name = "sRGB" if colour else "Non-Color"
        n = nt.nodes.new("ShaderNodeTexImage")
        n.image = img
        return n
    n_bc, n_orm, n_n = node("BC", True), node("ORM", False), node("N_OpenGL", False)
    sep = nt.nodes.new("ShaderNodeSeparateColor")
    nm = nt.nodes.new("ShaderNodeNormalMap")
    nt.links.new(n_bc.outputs[0], bsdf.inputs["Base Color"])
    nt.links.new(n_orm.outputs[0], sep.inputs[0])
    nt.links.new(sep.outputs[1], bsdf.inputs["Roughness"])
    nt.links.new(sep.outputs[2], bsdf.inputs["Metallic"])
    nt.links.new(n_n.outputs[0], nm.inputs["Color"])
    nt.links.new(nm.outputs[0], bsdf.inputs["Normal"])


pbr_material(pmat, prev_cfg["textures_dir"], prev_cfg["texture_prefix"])
for o in new:
    if o.type == "MESH":
        o.data.materials.clear()
        o.data.materials.append(pmat)
        prev_objs.append(o)
    elif o.type == "ARMATURE":
        o.hide_render = True
prev_top = max((o.matrix_world @ v.co).z for o in prev_objs for v in o.data.vertices)


def set_visible(objs):
    keep = set(objs)
    for o in scene.objects:
        if o.type == "MESH":
            o.hide_render = o not in keep


# ------------------------------------------------------------------ light and render settings
scene.render.engine = "BLENDER_EEVEE"
scene.eevee.taa_render_samples = int(rv_cfg["eevee_samples"])
scene.view_settings.view_transform = "Standard"
scene.view_settings.look = "None"
scene.render.film_transparent = False
world = bpy.data.worlds.new("h2_review_world")
scene.world = world
world.use_nodes = True
bg = world.node_tree.nodes["Background"]
bg.inputs[0].default_value = (0.045, 0.045, 0.05, 1.0)
bg.inputs[1].default_value = 1.0


def add_light(name, kind, energy, rot, size=1.0, colour=(1, 1, 1)):
    ld = bpy.data.lights.new(name, kind)
    ld.energy = energy
    ld.color = colour
    if kind == "AREA":
        ld.size = size
    lo = bpy.data.objects.new(name, ld)
    lo.rotation_euler = [math.radians(a) for a in rot]
    scene.collection.objects.link(lo)
    return lo


add_light("key", "SUN", 3.2, (50, 0, -35), colour=(1.0, 0.97, 0.92))
add_light("fill", "SUN", 1.1, (65, 0, 140), colour=(0.9, 0.93, 1.0))
add_light("rim", "SUN", 2.0, (-60, 0, 20))
cam = bl.new_camera(scene)
frames = {}


def shoot(name, target, direction, ortho=None, fov_h=None, distance=None, res=(1000, 1000), objs=None, folder=FR):
    set_visible(objs if objs is not None else ours)
    cam.data.type = "ORTHO" if ortho else "PERSP"
    if ortho:
        cam.data.ortho_scale = ortho
        bl.look_at(cam, target, direction, 3.0)
    else:
        cam.data.sensor_fit = "HORIZONTAL"
        cam.data.angle = math.radians(fov_h)
        bl.look_at(cam, target, direction, distance)
    scene.render.resolution_x, scene.render.resolution_y = res
    scene.render.filepath = str(folder / (name + ".png"))
    bpy.ops.render.render(write_still=True)
    if folder != FR:
        return
    frames[name] = {"png": P.rel(scene.render.filepath), "engine": scene.render.engine, "camera": cam.data.type,
                    "target_m": P.rv(target, 4), "direction": P.rv(direction, 4), "ortho_scale_m": ortho,
                    "horizontal_fov_deg": fov_h, "distance_m": distance, "resolution": list(res),
                    "label": "blender"}


# ortho, framed like the concepts: portrait 9:10, figure (base bottom -> sword tip) over 92 % of the height
cf = rv_cfg["concept_framing"]
co_sw = np.array([v.co[:] for v in sword.data.vertices])
tip = float(co_sw[:, 2].max())
vext = tip / (cf["base_bottom_frac"] - cf["sword_tip_frac"])
zc = (cf["base_bottom_frac"] - 0.5) * vext
res_c = tuple(rv_cfg["concept_px"])
for view, d in (("front", (0, -1, 0)), ("left", (1, 0, 0)), ("back", (0, 1, 0)), ("right", (-1, 0, 0))):
    shoot("ortho_%s" % view, (0, 0, zc), d, ortho=vext, res=res_c)
print("ortho done", round(time.time() - t0, 1), flush=True)

# close-ups (authored frame; boxes from the body part labels)
vals = np.empty(len(body.data.polygons), dtype=np.int64)
body.data.attributes[CB.PART_ATTR].data.foreach_get("value", vals)
part_order = sorted([p for p in profile["parts"] if not profile["parts"][p].get("drop")] + ["LP_grip_bridge"],
                    key=bl.part_key)


def part_box(parts):
    idx = {part_order.index(p) for p in ([parts] if isinstance(parts, str) else parts)}
    vs = sorted({v for poly in body.data.polygons if vals[poly.index] in idx for v in poly.vertices})
    pts = np.array([body.data.vertices[i].co[:] for i in vs])
    return pts.min(axis=0), pts.max(axis=0)


for c in rv_cfg["closeups"]:
    if c.get("part") or c.get("parts"):
        lo, hi = part_box(c.get("parts") or c["part"])
    else:
        pts = np.array([v.co[:] for v in (sword if c["object"] == "weapon" else base).data.vertices])
        lo, hi = pts.min(axis=0), pts.max(axis=0)
    centre = (lo + hi) / 2 + np.array(c.get("shift_m", [0, 0, 0]))
    size = float(max(hi - lo)) * float(c.get("margin", 1.25))
    for az in c["azimuths"]:
        a = math.radians(az)
        el = math.radians(c.get("elevation_deg", 0))
        d = (math.sin(a) * math.cos(el), -math.cos(a) * math.cos(el), math.sin(el))
        shoot("close_%s_az%d" % (c["name"], az), tuple(centre), d, ortho=size, res=(900, 900))
print("closeups done", round(time.time() - t0, 1), flush=True)

# game cameras
k1_dist = 1920.0 / (float(rv_cfg["k1_px_per_m"]) * 2 * math.tan(math.radians(17.5)))
cams = {"K1": (35.0, k1_dist), "K2": (35.0, k1_dist / float(rv_cfg["k2_zoom"])), "K2S05": (20.0, float(rv_cfg["k2_s05_distance_m"]))}
# the previous candidate stands on the same spot (offset_m) and is rendered alone with the same camera: equal scale
for cname, (fov, dist) in cams.items():
    tz = 0.28 if cname == "K2S05" else 0.25
    for az in rv_cfg["game_azimuths"]:
        shoot("game_%s_az%d" % (cname, az), (0, 0, tz), bl.game_dir(az), fov_h=fov, distance=dist, res=(1920, 1080),
              objs=ours)
        shoot("game_%s_az%d_prev" % (cname, az), (0, 0, tz), bl.game_dir(az), fov_h=fov, distance=dist,
              res=(1920, 1080), objs=prev_objs)
# back and side views of the figure at the game cameras (own figures are seen from behind on the board)
for cname, az in rv_cfg.get("game_back", []):
    fov, dist = cams[cname]
    shoot("game_%s_az%d" % (cname, az), (0, 0, 0.28 if cname == "K2S05" else 0.25), bl.game_dir(az), fov_h=fov,
          distance=dist, res=(1920, 1080), objs=ours)
print("game done", round(time.time() - t0, 1), flush=True)

# ------------------------------------------------------------------ TeamDye preview (M_UM_Figure path)
# base colour = lerp(BC, dye, TeamMask.R) on the runtime 2K textures (EEVEE samples the mips): checks that the
# TeamColor-on-clothing mask covers the cloth up to the island seams (no hairlines of the source red) at the
# S05 K-2 close-up and at K2
td = rv_cfg.get("teamdye")
if td:
    tmat = body.material_slots[0].material
    tnt = tmat.node_tree
    tbsdf = next(n for n in tnt.nodes if n.bl_idname == "ShaderNodeBsdfPrincipled")
    bc_link = tbsdf.inputs["Base Color"].links[0]
    bc_socket = bc_link.from_socket
    tm_img = bpy.data.images.load(str(paths["textures"] / "runtime_2k" / ("%s_TeamMask.png" % profile["textures"]["prefix"])),
                                  check_existing=True)
    tm_img.colorspace_settings.name = "Non-Color"
    n_tm = tnt.nodes.new("ShaderNodeTexImage")
    n_tm.image = tm_img
    n_sep = tnt.nodes.new("ShaderNodeSeparateColor")
    n_mix = tnt.nodes.new("ShaderNodeMix")
    n_mix.data_type = "RGBA"
    n_mix.inputs["B"].default_value = (*td["dye_linear"], 1.0)
    tnt.links.new(n_tm.outputs[0], n_sep.inputs[0])
    tnt.links.new(n_sep.outputs[0], n_mix.inputs["Factor"])
    tnt.links.new(bc_socket, n_mix.inputs["A"])
    tnt.links.new(n_mix.outputs["Result"], tbsdf.inputs["Base Color"])
    lo_c, hi_c = part_box(td["close_part"])
    centre_c = (lo_c + hi_c) / 2
    size_c = float(max(hi_c - lo_c)) * 1.05
    for az in td["close_azimuths"]:
        a = math.radians(az)
        shoot("teamdye_close_%s_az%d" % (td["close_name"], az), tuple(centre_c), (math.sin(a), -math.cos(a), 0.0),
              ortho=size_c, res=(900, 900))
    for cname, az in td["game"]:
        fov, dist = cams[cname]
        shoot("teamdye_game_%s_az%d" % (cname, az), (0, 0, 0.28 if cname == "K2S05" else 0.25), bl.game_dir(az),
              fov_h=fov, distance=dist, res=(1920, 1080), objs=ours)
    tnt.links.new(bc_socket, tbsdf.inputs["Base Color"])
    for nd in (n_tm, n_sep, n_mix):
        tnt.nodes.remove(nd)
    print("teamdye done", round(time.time() - t0, 1), flush=True)

# ------------------------------------------------------------------ silhouettes: high-poly vs LOD0 vs x0.5
seat = rig_rep["seat"]
s, (cx, cy), zmin = seat["scale"], seat["base_axis_tripo_m"], seat["base_bottom_tripo_m"]
high, coll = bl.import_glb_parts(P.repo_path(profile["sources"]["parts_glb"]["path"]), "H2_HIGH_SIL")
repairs.apply_geometry_repairs(high, profile)
Mseat = Matrix.Scale(s, 4) @ Matrix.Translation((-cx, -cy, -zmin))
for o in high.values():
    o.data.transform(Mseat)
lod1 = []
for o in ours:
    c = o.copy()
    c.data = o.data.copy()
    c.modifiers.clear()
    scene.collection.objects.link(c)
    m = c.modifiers.new("half", "DECIMATE")
    m.ratio = 0.5
    m.use_collapse_triangulate = True
    lod1.append(c)
scene.render.engine = "BLENDER_WORKBENCH"
scene.display.shading.light = "FLAT"
scene.display.shading.color_type = "SINGLE"
scene.display.shading.single_color = (1, 1, 1)
scene.display.render_aa = "OFF"
bg.inputs[0].default_value = (0, 0, 0, 1)
world.color = (0, 0, 0)
sil = {}
sil_high_tris = int(sum(len(o.data.polygons) for o in high.values()))
lod1_tris = 0
dg = bpy.context.evaluated_depsgraph_get()
for c in lod1:
    ev = c.evaluated_get(dg)
    me = ev.to_mesh()
    lod1_tris += len(me.polygons)
    ev.to_mesh_clear()
for cname, (fov, dist) in cams.items():
    for az in (0, -40):
        masks = {}
        for label, objs in (("high", list(high.values())), ("lod0", ours), ("lod1_half", lod1)):
            n = "sil_%s_az%d_%s" % (cname, az, label)
            shoot(n, (0, 0, 0.28 if cname == "K2S05" else 0.25), bl.game_dir(az), fov_h=fov, distance=dist,
                  res=(1920, 1080), objs=objs, folder=SI)
            img = bpy.data.images.load(str(SI / (n + ".png")))
            px = np.empty(img.size[0] * img.size[1] * 4, dtype=np.float32)
            img.pixels.foreach_get(px)
            masks[label] = px.reshape(-1, 4)[:, 0] > 0.5
            bpy.data.images.remove(img)
        area = int(masks["high"].sum())
        rows = np.nonzero(masks["high"].reshape(1080, 1920).any(axis=1))[0]
        cols = np.nonzero(masks["high"].reshape(1080, 1920).any(axis=0))[0]
        entry = {"figure_px_area": area, "figure_px_height_incl_base_and_sword": int(rows.max() - rows.min() + 1) if len(rows) else 0,
                 "figure_px_width": int(cols.max() - cols.min() + 1) if len(cols) else 0,
                 "high_triangles_per_px": P.r(sil_high_tris / max(area, 1), 2)}
        for label in ("lod0", "lod1_half"):
            x = int((masks[label] ^ masks["high"]).sum())
            entry[label + "_xor_px"] = x
            entry[label + "_xor_share"] = P.r(x / max(area, 1), 4)
        entry["lod0_triangles_per_figure_px"] = P.r(rig_rep["geometry"]["triangles_total"] / max(area, 1), 2)
        sil["%s_az%d" % (cname, az)] = entry
sil_meta = {"lod0_triangles": rig_rep["geometry"]["triangles_total"], "lod1_half_triangles": lod1_tris,
            "high_triangles": sil_high_tris,
            "cameras": {k: {"horizontal_fov_deg": v[0], "distance_m": P.r(v[1], 3)} for k, v in cams.items()}}

report = {"schema": "unmatched.h2-bake.review/1", "frames": frames, "silhouettes": sil, "silhouette_meta": sil_meta,
          "previous_candidate": prev_cfg | {"top_m_measured": P.r(prev_top, 4)},
          "light": "EEVEE, three suns (key 3.2, fill 1.1, rim 2.0), dark grey world; Standard view transform; ORM.R (AO) is not used by the Blender preview material",
          "textures_used": "runtime_2k", "seconds": round(time.time() - t0, 1)}
P.write_json(paths["reports"] / "review-report.json", report)
print(P.STAGE_MARKER, "review", round(time.time() - t0, 1))
