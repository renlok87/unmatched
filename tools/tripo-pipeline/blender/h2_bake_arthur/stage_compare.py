"""Stage compare (headless, H2.1): the same game mesh rendered with several texture sets under the same light and
cameras (H2 | H2.1 before/after frames; all frames are Blender renders, labelled "blender" by sheets_h21.py).

    blender -b --factory-startup --python stage_compare.py -- <profile.json> <run_dir> <out_dir>
        --set LABEL=<textures dir> [--set LABEL=<dir> ...] [--light studio|studio_env] [--views v1,v2,...]
        [--debug-bc <png> [--debug-light FLAT|STUDIO]]   (Workbench texture colour of <png> instead of the PBR
        material: class-map check; STUDIO light shows the geometry)

The mesh is work/h2-rig-authored.blend (stage rig); the images of its atlas material (BC, ORM, N_OpenGL, file names
<prefix>_<key>.png) are reloaded from each set's folder, nothing else changes between the sets.
Lights (profile review_h21.lights):
  studio      the H2 review light: three suns (key 3.2, fill 1.1, rim 2.0), dark grey world 0.045 (a metal reflects
              almost nothing there: only the sun highlights)
  studio_env  the same three suns + an image world for the reflections and the ambient light (Blender's bundled
              studio light file, sha256 in the report), seen by the camera as the same dark grey (Light Path
              "Is Camera Ray"); the UE board has a sky light (render-reference.json "sky": "1"), so a metal there
              reflects an environment - this light is closer to that than the dark world, and still not the game light
  cobble      (H2.2, profile review_h22.lights.cobble) an approximation of the UE Cobble board light
              (Config/ArtBoards/S08ArtBoardProfiles.json lightProfiles.cobble-probe): one sun = the directional key
              (lux -> Blender sun strength 1:1, UE pitch/yaw taken relative to the camera of azimuth 0), the W4-A
              ambient dome (tools/art/render/make_ambient_dome_hdr.py, same bytes) x the sky intensity as the world
              (cd/m2 -> world strength 1:1; the camera sees it), a flat board plane under the base, fixed exposure
              log2(1 / (1.2 * 2^EV100)) + a measured offset (the board of the UE Cobble editor frame) and a filmic
              view transform; EEVEE ray-traced reflections on. Not UE, not Lumen:
              a check that the dark steel does not turn white from the sky reflection
Cameras: ortho views framed like the H2 concepts (as stage review), K2 = FOV 35 (horizontal), pitch -55, distance
review_h21.k2_distance_m (1207 / 386 uu: the 1.6x / 5x K2 frames of Medusa and Merlin), focus +28 uu; close-ups on
parts or Tripo-frame boxes. Writes <out_dir>/<label>/<view>.png and <out_dir>/compare-<label>.json.
"""

import argparse
import json
import math
import sys
import time
from pathlib import Path

import bpy
import numpy as np
from mathutils import Vector

sys.path.insert(0, str(Path(__file__).resolve().parent))
import bl  # noqa: E402
import pure as P  # noqa: E402
from candidate_build import core as CB  # noqa: E402

bl.require_background("stage_compare.py")
ap = argparse.ArgumentParser()
ap.add_argument("profile")
ap.add_argument("run_dir")
ap.add_argument("out_dir")
ap.add_argument("--set", action="append", default=[])
ap.add_argument("--light", default="studio_env")
ap.add_argument("--views", default="")
ap.add_argument("--debug-bc", default="")
ap.add_argument("--debug-light", default="FLAT", help="Workbench light of the --debug-bc frames: FLAT (colour) or STUDIO (shape)")
a = ap.parse_args(bl.script_args())
PROFILE_PATH, RUN, OUT = Path(a.profile).resolve(), Path(a.run_dir).resolve(), Path(a.out_dir).resolve()
profile = P.load_json(PROFILE_PATH)
paths = P.run_paths(RUN)
cfg = profile["review_h21"]
t0 = time.time()

bpy.ops.wm.open_mainfile(filepath=str(paths["work"] / "h2-rig-authored.blend"))
scene = bpy.context.scene
names = profile["rig"]["objects"]
body, sword, base = (bpy.data.objects[names[k]] for k in ("body", "weapon", "base"))
for o in scene.objects:
    if o.type == "ARMATURE":
        o.hide_render = True
ours = [body, sword, base]
mat = body.material_slots[0].material
nt = mat.node_tree
prefix = profile["textures"]["prefix"]
img_nodes = {}
for n in nt.nodes:
    if n.bl_idname == "ShaderNodeTexImage" and n.image:
        key = Path(n.image.filepath).stem[len(prefix) + 1:]
        img_nodes[key] = n


def use_set(folder):
    for key, n in img_nodes.items():
        f = Path(folder) / ("%s_%s.png" % (prefix, key))
        img = bpy.data.images.load(str(f), check_existing=False)
        img.colorspace_settings.name = "sRGB" if key == "BC" else "Non-Color"
        n.image = img


# ------------------------------------------------------------------ light
scene.render.engine = "BLENDER_EEVEE"
scene.eevee.taa_render_samples = int(cfg.get("eevee_samples", 32))
scene.view_settings.view_transform = "Standard"
scene.view_settings.look = "None"
scene.render.film_transparent = False
world = bpy.data.worlds.new("h21_world")
scene.world = world
world.use_nodes = True
wnt = world.node_tree
bg = wnt.nodes["Background"]
bg.inputs[0].default_value = (0.045, 0.045, 0.05, 1.0)
bg.inputs[1].default_value = 1.0
light_meta = {"mode": a.light, "suns": "key 3.2 (50, 0, -35), fill 1.1 (65, 0, 140), rim 2.0 (-60, 0, 20)",
              "camera_background_linear": [0.045, 0.045, 0.05]}
if a.light == "studio_env":
    lc = cfg["lights"]["studio_env"]
    env_path = Path(bpy.utils.system_resource("DATAFILES")) / "studiolights" / "world" / lc["world_image"]
    env = wnt.nodes.new("ShaderNodeTexEnvironment")
    env.image = bpy.data.images.load(str(env_path), check_existing=True)
    mapping = wnt.nodes.new("ShaderNodeMapping")
    texco = wnt.nodes.new("ShaderNodeTexCoord")
    mapping.inputs["Rotation"].default_value = (0.0, 0.0, math.radians(float(lc.get("world_rotation_z_deg", 0.0))))
    wnt.links.new(texco.outputs["Generated"], mapping.inputs["Vector"])
    wnt.links.new(mapping.outputs["Vector"], env.inputs["Vector"])
    bg_env = wnt.nodes.new("ShaderNodeBackground")
    bg_env.inputs[1].default_value = float(lc["world_strength"])
    wnt.links.new(env.outputs["Color"], bg_env.inputs[0])
    lp = wnt.nodes.new("ShaderNodeLightPath")
    mix = wnt.nodes.new("ShaderNodeMixShader")
    wnt.links.new(lp.outputs["Is Camera Ray"], mix.inputs["Fac"])
    wnt.links.new(bg_env.outputs[0], mix.inputs[1])
    wnt.links.new(bg.outputs[0], mix.inputs[2])
    out = next(n for n in wnt.nodes if n.bl_idname == "ShaderNodeOutputWorld")
    wnt.links.new(mix.outputs[0], out.inputs["Surface"])
    light_meta |= {"world_image": lc["world_image"], "world_image_sha256": P.sha256(env_path),
                   "world_strength": float(lc["world_strength"]),
                   "world_rotation_z_deg": float(lc.get("world_rotation_z_deg", 0.0)),
                   "camera_sees": "dark grey background (Light Path Is Camera Ray)"}


def add_light(name, energy, rot, colour=(1, 1, 1)):
    ld = bpy.data.lights.new(name, "SUN")
    ld.energy = energy
    ld.color = colour
    lo = bpy.data.objects.new(name, ld)
    lo.rotation_euler = [math.radians(x) for x in rot]
    scene.collection.objects.link(lo)


if a.light == "cobble":
    cc = profile["review_h22"]["lights"]["cobble"]
    sys.path.insert(0, str(P.REPO / "tools" / "art" / "render"))
    import make_ambient_dome_hdr as dome  # noqa: E402
    dome_path = paths["work"] / "cobble-ambient-dome.hdr"
    data = dome.build()
    if not dome_path.exists() or dome_path.read_bytes() != data:
        dome_path.write_bytes(data)
    for n in list(wnt.nodes):
        if n.bl_idname != "ShaderNodeOutputWorld":
            wnt.nodes.remove(n)
    env = wnt.nodes.new("ShaderNodeTexEnvironment")
    env.image = bpy.data.images.load(str(dome_path), check_existing=True)
    env.image.colorspace_settings.name = "Linear Rec.709"
    bg_sky = wnt.nodes.new("ShaderNodeBackground")
    bg_sky.inputs[1].default_value = float(cc["sky_intensity"])
    tint = wnt.nodes.new("ShaderNodeVectorMath")      # colour x sky colour (linear)
    tint.operation = "MULTIPLY"
    wnt.links.new(env.outputs["Color"], tint.inputs[0])
    tint.inputs[1].default_value = tuple(float(x) for x in cc["sky_colour_linear"])
    wnt.links.new(tint.outputs["Vector"], bg_sky.inputs[0])
    out = next(n for n in wnt.nodes if n.bl_idname == "ShaderNodeOutputWorld")
    wnt.links.new(bg_sky.outputs[0], out.inputs["Surface"])
    # key: UE rotation (pitch, yaw) relative to the camera of azimuth 0 (looks along +Y; UE yaw + turns toward the
    # camera's right = +X); the sun shines along its local -Z
    pitch, yaw = math.radians(cc["key_pitch_deg"]), math.radians(cc["key_yaw_deg"])
    travel = Vector((math.cos(pitch) * math.sin(yaw), math.cos(pitch) * math.cos(yaw), math.sin(pitch)))
    ld = bpy.data.lights.new("cobble_key", "SUN")
    ld.energy = float(cc["key_lux"])
    ld.color = cc.get("key_colour_linear", (1.0, 1.0, 1.0))
    ld.angle = math.radians(float(cc.get("key_source_angle_deg", 0.5357)))
    lo = bpy.data.objects.new("cobble_key", ld)
    lo.rotation_euler = travel.to_track_quat("-Z", "Y").to_euler()
    scene.collection.objects.link(lo)
    # the board: a flat plane under the base
    bpy.ops.mesh.primitive_plane_add(size=float(cc["board_size_m"]), location=(0.0, 0.0, -0.0005))
    board = bpy.context.active_object
    board.name = "cobble_board"
    bm = bpy.data.materials.new("cobble_board")
    bm.use_nodes = True
    bsdf = next(n for n in bm.node_tree.nodes if n.bl_idname == "ShaderNodeBsdfPrincipled")
    bsdf.inputs["Base Color"].default_value = (*cc["board_albedo_linear"], 1.0)
    bsdf.inputs["Roughness"].default_value = float(cc["board_roughness"])
    board.data.materials.append(bm)
    ours.append(board)
    scene.eevee.use_raytracing = True
    scene.view_settings.view_transform = cc["view_transform"]
    scene.view_settings.exposure = (math.log2(1.0 / (1.2 * 2.0 ** float(cc["ev100"])))
                                    + float(cc.get("exposure_offset_stops", 0.0)))
    light_meta = {"mode": "cobble", "profile_source": cc["source"], "key_lux": float(cc["key_lux"]),
                  "key_pitch_yaw_deg": [cc["key_pitch_deg"], cc["key_yaw_deg"]],
                  "key_travel_dir": [round(x, 4) for x in travel],
                  "sky": "ambient dome x %s (%s, sha256 %s)" % (cc["sky_intensity"], P.rel(dome_path), P.sha256(dome_path)),
                  "board": {"albedo_linear": cc["board_albedo_linear"], "roughness": cc["board_roughness"]},
                  "ev100": float(cc["ev100"]), "exposure_offset_stops": float(cc.get("exposure_offset_stops", 0.0)),
                  "blender_exposure": round(scene.view_settings.exposure, 4),
                  "view_transform": cc["view_transform"], "eevee_raytracing": True,
                  "not_included": cc.get("not_included", "")}
else:
    add_light("key", 3.2, (50, 0, -35), (1.0, 0.97, 0.92))
    add_light("fill", 1.1, (65, 0, 140), (0.9, 0.93, 1.0))
    add_light("rim", 2.0, (-60, 0, 20))
cam = bl.new_camera(scene)

if a.debug_bc:
    scene.render.engine = "BLENDER_WORKBENCH"
    scene.display.shading.light = a.debug_light
    scene.display.shading.color_type = "TEXTURE"
    scene.display.render_aa = "8"
    dimg = bpy.data.images.load(str(Path(a.debug_bc).resolve()))
    dimg.colorspace_settings.name = "sRGB"
    img_nodes["BC"].image = dimg
    nt.nodes.active = img_nodes["BC"]
    light_meta = {"mode": "workbench %s, texture colour of the debug image (no PBR, no lights)" % a.debug_light}

# ------------------------------------------------------------------ views
vals = np.empty(len(body.data.polygons), dtype=np.int64)
body.data.attributes[CB.PART_ATTR].data.foreach_get("value", vals)
part_order = sorted([p for p in profile["parts"] if not profile["parts"][p].get("drop")] + ["LP_grip_bridge"],
                    key=bl.part_key)
seat = P.load_json(paths["reports"] / "rig-report.json")["seat"]
s_ = float(seat["scale"])
cx, cy = seat["base_axis_tripo_m"]
zmin = float(seat["base_bottom_tripo_m"])


def tripo_to_final(p):
    return np.array([(p[0] - cx) * s_, (p[1] - cy) * s_, (p[2] - zmin) * s_])


def part_box(parts):
    idx = {part_order.index(p) for p in ([parts] if isinstance(parts, str) else parts)}
    vs = sorted({v for poly in body.data.polygons if vals[poly.index] in idx for v in poly.vertices})
    pts = np.array([body.data.vertices[i].co[:] for i in vs])
    return pts.min(axis=0), pts.max(axis=0)


co_sw = np.array([v.co[:] for v in sword.data.vertices])
tip = float(co_sw[:, 2].max())
cf = profile["review"]["concept_framing"]
vext = tip / (cf["base_bottom_frac"] - cf["sword_tip_frac"])
zc = (cf["base_bottom_frac"] - 0.5) * vext
views = {}
for view, d in (("front", (0, -1, 0)), ("left", (1, 0, 0)), ("back", (0, 1, 0))):
    views["ortho_" + view] = {"target": (0, 0, zc), "dir": d, "ortho": vext, "res": tuple(profile["review"]["concept_px"])}
for tag, dist in cfg["k2_distance_m"].items():
    for az in cfg["k2_azimuths"]:
        views["k2_%s_az%d" % (tag, az)] = {"target": (0, 0, float(cfg["k2_focus_z_m"])), "dir": bl.game_dir(az),
                                           "fov": 35.0, "dist": float(dist), "res": (1920, 1080)}
for c in cfg["closeups"]:
    if c.get("part"):
        lo, hi = part_box(c["part"])
    elif c.get("object"):
        pts = np.array([v.co[:] for v in (sword if c["object"] == "weapon" else base).data.vertices])
        lo, hi = pts.min(axis=0), pts.max(axis=0)
    else:
        lo, hi = tripo_to_final(c["box_tripo_m"][0]), tripo_to_final(c["box_tripo_m"][1])
    centre = (lo + hi) / 2
    size = float(max(hi - lo)) * float(c.get("margin", 1.1))
    for az in c["azimuths"]:
        el = math.radians(c.get("elevation_deg", 0))
        ar = math.radians(az)
        views["close_%s_az%d" % (c["name"], az)] = {
            "target": tuple(centre), "dir": (math.sin(ar) * math.cos(el), -math.cos(ar) * math.cos(el), math.sin(el)),
            "ortho": size, "res": (900, 900), "hide": c.get("hide", [])}
want = [v for v in a.views.split(",") if v] or list(views)


def shoot(path, v):
    hidden = {bpy.data.objects[names[k]] for k in v.get("hide", [])}
    for o in scene.objects:
        if o.type == "MESH":
            o.hide_render = o not in ours or o in hidden
    if v.get("ortho"):
        cam.data.type = "ORTHO"
        cam.data.sensor_fit = "AUTO"      # as stage review (its ortho frames come before any perspective view)
        cam.data.ortho_scale = v["ortho"]
        bl.look_at(cam, v["target"], v["dir"], 3.0)
    else:
        cam.data.type = "PERSP"
        cam.data.sensor_fit = "HORIZONTAL"
        cam.data.angle = math.radians(v["fov"])
        bl.look_at(cam, v["target"], v["dir"], v["dist"])
    scene.render.resolution_x, scene.render.resolution_y = v["res"]
    scene.render.filepath = str(path)
    bpy.ops.render.render(write_still=True)


sets = [s.split("=", 1) for s in a.set] or [["current", str(paths["textures"] / "runtime_2k")]]
report = {"schema": "unmatched.h2-bake.compare/1", "light": light_meta, "engine": scene.render.engine,
          "sets": {}, "views": {}}
for label, folder in sets:
    if not a.debug_bc:
        use_set(folder)
    report["sets"][label] = ({"debug_bc": P.rel(a.debug_bc), "sha256": P.sha256(a.debug_bc)} if a.debug_bc else
                             {"textures": P.rel(folder),
                              "sha256": {k: P.sha256(Path(folder) / ("%s_%s.png" % (prefix, k))) for k in img_nodes}})
    for name in want:
        v = views[name]
        shoot(OUT / label / (name + ".png"), v)
        report["views"][name] = {k: (list(x) if isinstance(x, tuple) else x) for k, x in v.items()}
    print("set", label, "done", round(time.time() - t0, 1), flush=True)
report["seconds"] = round(time.time() - t0, 1)
OUT.mkdir(parents=True, exist_ok=True)
(OUT / ("compare-%s.json" % "_".join(s[0] for s in sets))).write_text(json.dumps(report, indent=1, ensure_ascii=False),
                                                                     encoding="utf-8")
print(P.STAGE_MARKER, "compare", report["seconds"])
