"""Look-dev v2 frames of King Arthur (headless Blender; stages ld_render_tone / ld_render_final).

    blender -b --factory-startup --python lookdev_render.py -- <lookdev profile.json> <lookdev run dir> <job.json>

job.json (written by the python stage that asks for the frames):
  {"out": dir, "sets": {label: folder with BC.png / ORM.png / N_OpenGL.png},
   "lights": {"studio_env": [views], "cobble": [views]}, "id_sets": {label: zone-colour png}, "id_views": [views],
   "calibrate": true|false}
The mesh is <source run>/work/h2-rig-authored.blend (opened read-only, never saved): the H2 game model in the authored
frame (the look-dev FBX has the same geometry, ld_export read-back). The atlas images of its material are replaced by
the set's images (BC sRGB, ORM and N_OpenGL non-colour), nothing else changes between the sets.
Lights:
  studio_env  the H2.1/H2.2 comparison light of the H2 bake (stage_compare.py): three suns + Blender's studio.exr world
              for reflections, dark grey for camera rays; the steel relative check of H2.2 is measured in it
  cobble      the UE Cobble board light approximation (source profile review_h22.lights.cobble: sun 4.5 lux pitch -55
              yaw 30 relative to the camera of azimuth 0, W4-A ambient dome x 11.2, flat board of the cobblestone mean
              albedo, AgX), exposure CALIBRATED to the W4-A anchor as review_h3.py rev. 2: figure hidden, 40 m board,
              K1 camera (FOV 35, 1931 uu, pitch -55), offset bisected until the K1 board ROI p50 luma = 131.2
  id          Workbench, flat texture colour of the zone texture with Closest filtering (masks of the measurements)
Cameras (as stage_compare): ortho views framed like the concepts, K2 5x / 1.6x (FOV 35, pitch -55, 386 / 1207 uu,
focus +28 uu), close-ups on parts. Writes <out>/<light>/<label>/<view>.png, <out>/id/<label>/<view>.png and
<out>/render-report.json. Every frame is a Blender EEVEE/Workbench render, not UE.
"""

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

bl.require_background("lookdev_render.py")
args = bl.script_args()
PROFILE_PATH, RUN, JOB = Path(args[0]).resolve(), Path(args[1]).resolve(), Path(args[2]).resolve()
prof = P.load_json(PROFILE_PATH)
ld = prof["lookdev"]
src = P.load_json(P.repo_path(ld["source_profile"]))
SRC_RUN = P.repo_path(ld["source_run"])
job = P.load_json(JOB)
OUT = Path(job["out"])
t0 = time.time()

bpy.ops.wm.open_mainfile(filepath=str(SRC_RUN / "work" / "h2-rig-authored.blend"))
scene = bpy.context.scene
names = src["rig"]["objects"]
body, sword, base = (bpy.data.objects[names[k]] for k in ("body", "weapon", "base"))
for o in scene.objects:
    if o.type == "ARMATURE":
        o.hide_render = True
figure = [body, sword, base]
mat = body.material_slots[0].material
nt = mat.node_tree
prefix = src["textures"]["prefix"]
img_nodes = {}
for n in nt.nodes:
    if n.bl_idname == "ShaderNodeTexImage" and n.image:
        img_nodes[Path(n.image.filepath).stem[len(prefix) + 1:]] = n
if sorted(img_nodes) != ["BC", "N_OpenGL", "ORM"]:
    raise RuntimeError("unexpected atlas images %s" % sorted(img_nodes))


def use_set(folder, closest=False):
    for key, n in img_nodes.items():
        img = bpy.data.images.load(str(Path(folder) / (key + ".png")), check_existing=False)
        img.colorspace_settings.name = "sRGB" if key == "BC" else "Non-Color"
        n.image = img
        n.interpolation = "Closest" if closest else "Linear"


cam = bl.new_camera(scene)
report = {"schema": "unmatched.h2-lookdev.render/1", "job": P.rel(JOB), "lights": {}, "frames": {}}


# ------------------------------------------------------------------ views (as stage_compare.py of the H2 bake)
cfg21 = src["review_h21"]
vals = np.empty(len(body.data.polygons), dtype=np.int64)
body.data.attributes[CB.PART_ATTR].data.foreach_get("value", vals)
part_order = sorted([p for p in src["parts"] if not src["parts"][p].get("drop")] + ["LP_grip_bridge"], key=bl.part_key)
seat = P.load_json(SRC_RUN / "reports" / "rig-report.json")["seat"]
s_ = float(seat["scale"])
cx, cy = seat["base_axis_tripo_m"]
zmin = float(seat["base_bottom_tripo_m"])


def part_box(parts):
    idx = {part_order.index(p) for p in ([parts] if isinstance(parts, str) else parts)}
    vs = sorted({v for poly in body.data.polygons if vals[poly.index] in idx for v in poly.vertices})
    pts = np.array([body.data.vertices[i].co[:] for i in vs])
    return pts.min(axis=0), pts.max(axis=0)


co_sw = np.array([v.co[:] for v in sword.data.vertices])
tip = float(co_sw[:, 2].max())
cf = src["review"]["concept_framing"]
vext = tip / (cf["base_bottom_frac"] - cf["sword_tip_frac"])
zc = (cf["base_bottom_frac"] - 0.5) * vext
views = {}
for view, d in (("front", (0, -1, 0)), ("left", (1, 0, 0)), ("back", (0, 1, 0))):
    views["ortho_" + view] = {"target": (0, 0, zc), "dir": d, "ortho": vext, "res": tuple(src["review"]["concept_px"])}
for tag, dist in cfg21["k2_distance_m"].items():
    for az in (0, -40, 40, 180):
        views["k2_%s_az%d" % (tag, az)] = {"target": (0, 0, float(cfg21["k2_focus_z_m"])), "dir": bl.game_dir(az),
                                           "fov": 35.0, "dist": float(dist), "res": (1920, 1080)}
closeups = list(cfg21["closeups"])
for c in closeups:
    if c.get("part"):
        lo, hi = part_box(c["part"])
    elif c.get("object"):
        pts = np.array([v.co[:] for v in (sword if c["object"] == "weapon" else base).data.vertices])
        lo, hi = pts.min(axis=0), pts.max(axis=0)
    else:
        continue
    centre = (lo + hi) / 2
    size = float(max(hi - lo)) * float(c.get("margin", 1.1))
    for az in c["azimuths"]:
        el = math.radians(c.get("elevation_deg", 0))
        ar = math.radians(az)
        views["close_%s_az%d" % (c["name"], az)] = {
            "target": tuple(centre), "dir": (math.sin(ar) * math.cos(el), -math.cos(ar) * math.cos(el), math.sin(el)),
            "ortho": size, "res": (900, 900)}


def shoot(path, v, hide=()):
    for o in scene.objects:
        if o.type == "MESH":
            o.hide_render = o in hide or o.name.startswith("ld_calib")
    if v.get("ortho"):
        cam.data.type = "ORTHO"
        cam.data.sensor_fit = "AUTO"
        cam.data.ortho_scale = v["ortho"]
        bl.look_at(cam, v["target"], v["dir"], 3.0)
    else:
        cam.data.type = "PERSP"
        cam.data.sensor_fit = "HORIZONTAL"
        cam.data.angle = math.radians(v["fov"])
        bl.look_at(cam, v["target"], v["dir"], v["dist"])
    scene.render.resolution_x, scene.render.resolution_y = v["res"]
    scene.render.resolution_percentage = 100
    scene.render.filepath = str(path)
    bpy.ops.render.render(write_still=True)


# ------------------------------------------------------------------ lights
def clear_lights():
    for o in list(scene.objects):
        if o.type == "LIGHT" or o.name.startswith("ld_board"):
            bpy.data.objects.remove(o)


def new_world(name):
    w = bpy.data.worlds.new(name)
    scene.world = w
    w.use_nodes = True
    return w.node_tree


def add_sun(name, energy, rot=None, colour=(1, 1, 1), travel=None, angle_deg=None):
    ld_ = bpy.data.lights.new(name, "SUN")
    ld_.energy = energy
    ld_.color = colour
    if angle_deg is not None:
        ld_.angle = math.radians(angle_deg)
    lo = bpy.data.objects.new(name, ld_)
    if travel is not None:
        lo.rotation_euler = Vector(travel).to_track_quat("-Z", "Y").to_euler()
    else:
        lo.rotation_euler = [math.radians(x) for x in rot]
    scene.collection.objects.link(lo)


def setup_studio_env():
    clear_lights()
    scene.render.engine = "BLENDER_EEVEE"
    scene.eevee.taa_render_samples = int(prof["lookdev"]["render"]["eevee_samples"])
    scene.eevee.use_raytracing = False
    scene.view_settings.view_transform = "Standard"
    scene.view_settings.look = "None"
    scene.view_settings.exposure = 0.0
    scene.render.film_transparent = False
    wnt = new_world("ld_studio_env")
    bg = wnt.nodes["Background"]
    bg.inputs[0].default_value = (0.045, 0.045, 0.05, 1.0)
    lc = cfg21["lights"]["studio_env"]
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
    add_sun("key", 3.2, (50, 0, -35), (1.0, 0.97, 0.92))
    add_sun("fill", 1.1, (65, 0, 140), (0.9, 0.93, 1.0))
    add_sun("rim", 2.0, (-60, 0, 20))
    return {"mode": "studio_env", "suns": "key 3.2 (50, 0, -35), fill 1.1 (65, 0, 140), rim 2.0 (-60, 0, 20)",
            "world_image": lc["world_image"], "world_image_sha256": P.sha256(env_path),
            "camera_background_linear": [0.045, 0.045, 0.05], "view_transform": "Standard",
            "source": "stage_compare.py studio_env of the H2 bake (the H2.1 / H2.2 comparison light)"}


CC = src["review_h22"]["lights"]["cobble"]
CAL = prof["lookdev"]["cobble"]["exposure_calibration"]


def base_exposure():
    return math.log2(1.0 / (1.2 * 2.0 ** float(CC["ev100"])))


def setup_cobble():
    clear_lights()
    sys.path.insert(0, str(P.REPO / "tools" / "art" / "render"))
    import make_ambient_dome_hdr as dome  # noqa: E402
    dome_path = RUN / "work" / "cobble-ambient-dome.hdr"
    data = dome.build()
    if not dome_path.exists() or dome_path.read_bytes() != data:
        dome_path.parent.mkdir(parents=True, exist_ok=True)
        dome_path.write_bytes(data)
    scene.render.engine = "BLENDER_EEVEE"
    scene.eevee.taa_render_samples = int(prof["lookdev"]["render"]["eevee_samples"])
    scene.eevee.use_raytracing = True
    wnt = new_world("ld_cobble")
    for n in list(wnt.nodes):
        if n.bl_idname != "ShaderNodeOutputWorld":
            wnt.nodes.remove(n)
    env = wnt.nodes.new("ShaderNodeTexEnvironment")
    env.image = bpy.data.images.load(str(dome_path), check_existing=True)
    env.image.colorspace_settings.name = "Linear Rec.709"
    bg = wnt.nodes.new("ShaderNodeBackground")
    bg.inputs[1].default_value = float(CC["sky_intensity"])
    tint = wnt.nodes.new("ShaderNodeVectorMath")
    tint.operation = "MULTIPLY"
    wnt.links.new(env.outputs["Color"], tint.inputs[0])
    tint.inputs[1].default_value = tuple(float(x) for x in CC["sky_colour_linear"])
    wnt.links.new(tint.outputs["Vector"], bg.inputs[0])
    out = next(n for n in wnt.nodes if n.bl_idname == "ShaderNodeOutputWorld")
    wnt.links.new(bg.outputs[0], out.inputs["Surface"])
    pitch, yaw = math.radians(CC["key_pitch_deg"]), math.radians(CC["key_yaw_deg"])
    travel = (math.cos(pitch) * math.sin(yaw), math.cos(pitch) * math.cos(yaw), math.sin(pitch))
    add_sun("cobble_key", float(CC["key_lux"]), colour=tuple(CC["key_colour_linear"]), travel=travel,
            angle_deg=float(CC.get("key_source_angle_deg", 0.5357)))
    bpy.ops.mesh.primitive_plane_add(size=1.0, location=(0.0, 0.0, -0.0005))
    board = bpy.context.active_object
    board.name = "ld_board"
    bm = bpy.data.materials.new("ld_board")
    bm.use_nodes = True
    bsdf = next(n for n in bm.node_tree.nodes if n.bl_idname == "ShaderNodeBsdfPrincipled")
    bsdf.inputs["Base Color"].default_value = (*CC["board_albedo_linear"], 1.0)
    bsdf.inputs["Roughness"].default_value = float(CC["board_roughness"])
    board.data.materials.append(bm)
    board.scale = (float(prof["lookdev"]["cobble"]["board_size_m"]),) * 3
    scene.view_settings.view_transform = CC["view_transform"]
    scene.view_settings.look = "None"
    return board, dome_path, travel


def board_p50(path, roi):
    img = bpy.data.images.load(str(path), check_existing=False)
    img.colorspace_settings.name = "Non-Color"
    w, h = img.size
    px = np.empty(w * h * 4, dtype=np.float32)
    img.pixels.foreach_get(px)
    bpy.data.images.remove(img)
    px = px.reshape(h, w, 4)[::-1]
    rgb = np.round(px[..., :3] * 255.0)
    L = 0.2126 * rgb[..., 0] + 0.7152 * rgb[..., 1] + 0.0722 * rgb[..., 2]
    x0, y0, x1, y1 = roi
    return round(float(np.percentile(L[y0:y1, x0:x1], 50)), 3)


def calibrate(board):
    """Bisect the exposure offset until the K1 board ROI p50 is the W4-A anchor (figure hidden, 40 m board)."""
    cal_dir = RUN / "work" / "cobble-calibration"
    cal_dir.mkdir(parents=True, exist_ok=True)
    board.scale = (float(CAL["calibration_board_size_m"]),) * 3
    cm = CAL["camera"]
    v = {"target": (0.0, 0.0, 0.0), "dir": bl.game_dir(cm["azimuth_deg"], cm["pitch_deg"]), "fov": cm["fov_h_deg"],
         "dist": float(cm["distance_m"]), "res": tuple(CAL["res"])}
    tgt, tol = float(CAL["target_board_p50_luma"]), float(CAL["tolerance_luma"])
    lo, hi = (float(x) for x in CAL["search_stops"])
    steps = []

    def measure(off, tag):
        scene.view_settings.exposure = base_exposure() + off
        path = cal_dir / ("k1_board_%s.png" % tag)
        shoot(path, v, hide=figure)
        p50 = board_p50(path, CAL["roi_px"])
        steps.append({"offset_stops": round(off, 5), "k1_board_p50": p50, "frame": P.rel(path)})
        return p50

    v_lo, v_hi = measure(lo, "lo"), measure(hi, "hi")
    if not (v_lo < tgt < v_hi):
        raise RuntimeError("calibration target %.1f outside [%.1f, %.1f]" % (tgt, v_lo, v_hi))
    best = None
    for i in range(int(CAL["max_iterations"])):
        mid = 0.5 * (lo + hi)
        val = measure(mid, "i%02d" % i)
        if best is None or abs(val - tgt) < abs(best[1] - tgt):
            best = (mid, val)
        if abs(val - tgt) <= tol:
            break
        if val < tgt:
            lo = mid
        else:
            hi = mid
    off = round(best[0], 4)
    final = measure(off, "final")
    board.scale = (float(prof["lookdev"]["cobble"]["board_size_m"]),) * 3
    return {"method": CAL["method"], "target_board_p50_luma": tgt, "tolerance_luma": tol, "roi_px": CAL["roi_px"],
            "camera": cm, "base_exposure": round(base_exposure(), 4), "exposure_offset_stops": off,
            "blender_exposure": round(base_exposure() + off, 4), "k1_board_p50_final": final, "steps": steps}


# ------------------------------------------------------------------ run the job
for light, vlist in job.get("lights", {}).items():
    if not vlist:
        continue
    if light == "studio_env":
        meta = setup_studio_env()
    elif light == "cobble":
        board, dome_path, travel = setup_cobble()
        cal_file = RUN / "reports" / "ld-cobble-calibration.json"
        if job.get("calibrate") or not cal_file.exists():
            cal = calibrate(board)
            P.write_json(cal_file, cal)
        cal = P.load_json(cal_file)
        scene.view_settings.exposure = cal["blender_exposure"]
        meta = {"mode": "cobble", "profile_source": CC["source"], "key_lux": CC["key_lux"],
                "key_travel_dir": [round(x, 4) for x in travel],
                "sky": "ambient dome x %s (%s, sha256 %s)" % (CC["sky_intensity"], P.rel(dome_path), P.sha256(dome_path)),
                "board": {"albedo_linear": CC["board_albedo_linear"], "roughness": CC["board_roughness"],
                          "size_m": prof["lookdev"]["cobble"]["board_size_m"]},
                "ev100": CC["ev100"], "exposure_offset_stops": cal["exposure_offset_stops"],
                "blender_exposure": cal["blender_exposure"], "k1_board_p50": cal["k1_board_p50_final"],
                "calibration": P.rel(cal_file), "view_transform": CC["view_transform"], "eevee_raytracing": True,
                "not_included": CC.get("not_included", "")}
    else:
        raise RuntimeError("unknown light %s" % light)
    report["lights"][light] = meta
    for label, folder in job["sets"].items():
        use_set(folder)
        for vname in vlist:
            path = OUT / light / label / (vname + ".png")
            shoot(path, views[vname])
            report["frames"]["%s/%s/%s" % (light, label, vname)] = {"file": P.rel(path), "sha256": P.sha256(path)}
        print("light", light, "set", label, "done", round(time.time() - t0, 1), flush=True)
    clear_lights()

if job.get("id_sets"):
    scene.render.engine = "BLENDER_WORKBENCH"
    scene.display.shading.light = "FLAT"
    scene.display.shading.color_type = "TEXTURE"
    scene.display.render_aa = "OFF"
    scene.view_settings.view_transform = "Standard"
    scene.view_settings.exposure = 0.0
    nt.nodes.active = img_nodes["BC"]
    for label, png in job["id_sets"].items():
        img = bpy.data.images.load(str(png), check_existing=False)
        img.colorspace_settings.name = "sRGB"
        img_nodes["BC"].image = img
        img_nodes["BC"].interpolation = "Closest"
        for vname in job["id_views"]:
            path = OUT / "id" / label / (vname + ".png")
            shoot(path, views[vname], hide=[o for o in scene.objects if o.name.startswith("ld_board")])
            report["frames"]["id/%s/%s" % (label, vname)] = {"file": P.rel(path), "sha256": P.sha256(path)}
    report["lights"]["id"] = {"mode": "Workbench FLAT, texture colour, Closest, no anti-aliasing"}
report["views"] = {k: {kk: (list(x) if isinstance(x, tuple) else x) for kk, x in v.items()} for k, v in views.items()}
report["seconds"] = round(time.time() - t0, 1)
OUT.mkdir(parents=True, exist_ok=True)
P.write_json(OUT / "render-report.json", report)
print(P.STAGE_MARKER, "ld_render", report["seconds"])
