"""TeamAccent frames of the H2 look-dev (headless Blender; stage ta_render of run_h2_bake.py --mode teamaccent).

The figure is appended from the H2.1 run (work/sk_authored.blend, the rig-stage model in the authored frame; the look-dev
FBX has the same geometry per loop, ld_fbx read-back). Materials: st_lookdev.lut_material (MatID + hero LUT driving a
Principled: roughness / metallic / specular / sheen of the class; the approximation of M_UM_Figure_v2 of the look-dev
run) with the BaseColor of the set:
  ld      the look-dev BC (no dye)
  ld_p1   the look-dev BC with the v2 dye of the TeamAccent, team colour P1 (lookdev_accent.run_maps)
  ld_p2   the same, P2
ID pass: Cycles emission of the ID texture (R MatID, G accent, B 255), Raw view, 1 sample, 0.01 px filter.
Light "cobble" = the UE Cobble board profile approximation used by the King Arthur look-dev (profile cobble: key sun
4.5 lux pitch -55 yaw 30 relative to the camera of azimuth 0, W4-A ambient dome x 11.2, flat board of the cobblestone
mean albedo, EEVEE ray tracing, AgX); exposure CALIBRATED to the W4-A anchor: figure hidden, 40 m board, K1 camera
(FOV 35, 19.31 m, pitch -55), offset bisected until the K1 board ROI p50 luma = 131.2 (h2_bake_arthur/lookdev_render.py,
same numbers). Cameras K2: FOV 35 (horizontal), pitch -55, 3.86 m (5x) / 12.07 m (1.6x), focus z of the H2 profile.
Writes <run>/work/ta/render/{cobble/<set>,id}/<view>.png, render-report.json and reports/ld-team-cobble-calibration.json.
Every frame is Blender, not UE."""

import hashlib
import json
import math
import sys
import time
from pathlib import Path

import bpy
import numpy as np
from mathutils import Vector

from . import bl_util as U
from . import st_lookdev as SL


def game_dir(azimuth_deg, pitch_deg=-55.0):
    """Direction from the target to the camera: azimuth 0 = in front of the figure (-Y), + = the figure's left (+X)."""
    el = math.radians(-pitch_deg)
    az = math.radians(azimuth_deg)
    return (math.sin(az) * math.cos(el), -math.cos(az) * math.cos(el), math.sin(el))


def run(params, profile):
    t0 = time.time()
    run_dir, repo = Path(params["run_dir"]), Path(params["repo_root"])
    ta = json.loads(Path(params["teamaccent"]).read_text(encoding="utf-8"))
    ld = json.loads((repo / ta["lookdev_profile"]["path"]).read_text(encoding="utf-8"))
    ld_run = repo / ta["lookdev_run"]["path"]
    src_run = repo / ld["source"]["run"]
    work = run_dir / "work" / "ta"
    out = work / "render"
    maps = json.loads((run_dir / "reports" / "ld-team-accent-report.json").read_text(encoding="utf-8"))
    rcfg, cc, cal_cfg = ta["render"], ta["cobble"]["light"], ta["cobble"]["exposure_calibration"]
    scene = U.reset()
    names = (profile["rig"]["armature_object"], profile["meshes"]["body"], profile["meshes"]["weapon"], profile["meshes"]["base"])
    objs = SL.append_figure(src_run / ld["source"]["files"]["sk_authored"], names)
    for o in objs:
        scene.collection.objects.link(o)
        if o.type == "ARMATURE":
            o.hide_render = True
    figure = [o for o in objs if o.type == "MESH"]
    cull = bool(profile["preview"].get("backface_culling", False))
    lf = ta["lookdev_run"]["files"]
    base_tex = {"N_OpenGL": ld_run / lf["N_OpenGL"], "ORM": ld_run / lf["ORM"], "MatID": ld_run / lf["MatID"],
                "LUT": work / ("%s.exr" % ld["lut_name"]), "LUT_ROWS": 16}
    sets = {"ld": ld_run / lf["BC"]}
    for k in ("ld_p1", "ld_p2"):
        sets[k] = run_dir / maps["render_sets"][k]["file"]
    mats = {}
    for k, bc in sets.items():
        m = SL.lut_material("TA_" + k, dict(base_tex, BC=bc), cull)
        m.use_backface_culling = cull
        mats[k] = m
    mats["id"] = SL.class_material("TA_ID", run_dir / maps["render_sets"]["id"]["file"], cull)
    mats["id"].use_backface_culling = cull

    def use(key):
        for o in figure:
            o.data.materials.clear()
            o.data.materials.append(mats[key])

    cam_data = bpy.data.cameras.new("ta_cam")
    cam_data.clip_start, cam_data.clip_end = 0.01, 200.0
    cam = bpy.data.objects.new("ta_cam", cam_data)
    scene.collection.objects.link(cam)
    scene.camera = cam
    k2 = profile["preview"]["k2"]
    views = {}
    for tag, dist in rcfg["k2_distance_m"].items():
        for az in rcfg["azimuths"]:
            views["k2_%s_az%d" % (tag, az)] = {"target": (0.0, 0.0, float(k2["focus_z_m"])), "dir": game_dir(az),
                                               "fov": float(k2["fov_deg_horizontal"]), "dist": float(dist),
                                               "res": tuple(k2["resolution"])}
    views = {k: v for k, v in views.items() if k in rcfg["views"]}

    def shoot(path, v, hide=()):
        for o in scene.objects:
            if o.type == "MESH":
                o.hide_render = o in hide
        cam_data.type = "PERSP"
        cam_data.sensor_fit = "HORIZONTAL"
        cam_data.angle = math.radians(v["fov"])
        d = Vector(v["dir"]).normalized()
        cam.location = Vector(v["target"]) + d * v["dist"]
        cam.rotation_euler = (-d).to_track_quat("-Z", "Y").to_euler()
        scene.render.resolution_x, scene.render.resolution_y = v["res"]
        scene.render.resolution_percentage = 100
        scene.render.filepath = str(path)
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        bpy.ops.render.render(write_still=True)

    # ---------------------------------------------------------------- Cobble
    sys.path.insert(0, str(repo / "tools" / "art" / "render"))
    import make_ambient_dome_hdr as dome  # noqa: E402
    dome_path = work / "cobble-ambient-dome.hdr"
    data = dome.build()
    if not dome_path.exists() or dome_path.read_bytes() != data:
        dome_path.parent.mkdir(parents=True, exist_ok=True)
        dome_path.write_bytes(data)
    scene.render.engine = "BLENDER_EEVEE"
    scene.eevee.taa_render_samples = int(rcfg["eevee_samples"])
    scene.eevee.use_raytracing = True
    scene.render.film_transparent = False
    scene.render.image_settings.file_format = "PNG"
    scene.render.image_settings.color_mode = "RGB"
    scene.render.image_settings.color_depth = "8"
    world = bpy.data.worlds.new("ta_cobble")
    scene.world = world
    world.use_nodes = True
    wnt = world.node_tree
    for n in list(wnt.nodes):
        if n.bl_idname != "ShaderNodeOutputWorld":
            wnt.nodes.remove(n)
    env = wnt.nodes.new("ShaderNodeTexEnvironment")
    env.image = bpy.data.images.load(str(dome_path), check_existing=True)
    env.image.colorspace_settings.name = "Linear Rec.709"
    bg = wnt.nodes.new("ShaderNodeBackground")
    bg.inputs[1].default_value = float(cc["sky_intensity"])
    tint = wnt.nodes.new("ShaderNodeVectorMath")
    tint.operation = "MULTIPLY"
    wnt.links.new(env.outputs["Color"], tint.inputs[0])
    tint.inputs[1].default_value = tuple(float(x) for x in cc["sky_colour_linear"])
    wnt.links.new(tint.outputs["Vector"], bg.inputs[0])
    wout = next(n for n in wnt.nodes if n.bl_idname == "ShaderNodeOutputWorld")
    wnt.links.new(bg.outputs[0], wout.inputs["Surface"])
    pitch, yaw = math.radians(cc["key_pitch_deg"]), math.radians(cc["key_yaw_deg"])
    travel = (math.cos(pitch) * math.sin(yaw), math.cos(pitch) * math.cos(yaw), math.sin(pitch))
    sun = bpy.data.lights.new("cobble_key", "SUN")
    sun.energy = float(cc["key_lux"])
    sun.color = tuple(cc["key_colour_linear"])
    sun.angle = math.radians(float(cc["key_source_angle_deg"]))
    so = bpy.data.objects.new("cobble_key", sun)
    so.rotation_euler = Vector(travel).to_track_quat("-Z", "Y").to_euler()
    scene.collection.objects.link(so)
    bpy.ops.mesh.primitive_plane_add(size=1.0, location=(0.0, 0.0, -0.0005))
    board = bpy.context.active_object
    board.name = "ta_board"
    bm = bpy.data.materials.new("ta_board")
    bm.use_nodes = True
    bsdf = next(n for n in bm.node_tree.nodes if n.bl_idname == "ShaderNodeBsdfPrincipled")
    bsdf.inputs["Base Color"].default_value = (*cc["board_albedo_linear"], 1.0)
    bsdf.inputs["Roughness"].default_value = float(cc["board_roughness"])
    board.data.materials.append(bm)
    scene.view_settings.view_transform = cc["view_transform"]
    scene.view_settings.look = "None"
    base_exp = math.log2(1.0 / (1.2 * 2.0 ** float(cc["ev100"])))

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

    # calibration (figure hidden, 40 m board, K1 camera)
    cal_dir = work / "cobble-calibration"
    board.scale = (float(cal_cfg["calibration_board_size_m"]),) * 3
    cm = cal_cfg["camera"]
    vk1 = {"target": (0.0, 0.0, 0.0), "dir": game_dir(cm["azimuth_deg"], cm["pitch_deg"]), "fov": cm["fov_h_deg"],
           "dist": float(cm["distance_m"]), "res": tuple(cal_cfg["res"])}
    tgt, tol = float(cal_cfg["target_board_p50_luma"]), float(cal_cfg["tolerance_luma"])
    lo, hi = (float(x) for x in cal_cfg["search_stops"])
    steps = []

    def measure(off, tag):
        scene.view_settings.exposure = base_exp + off
        path = cal_dir / ("k1_board_%s.png" % tag)
        shoot(path, vk1, hide=figure)
        p50 = board_p50(path, cal_cfg["roi_px"])
        steps.append({"offset_stops": round(off, 5), "k1_board_p50": p50})
        return p50

    v_lo, v_hi = measure(lo, "lo"), measure(hi, "hi")
    if not (v_lo < tgt < v_hi):
        raise RuntimeError("calibration target %.1f outside [%.1f, %.1f]" % (tgt, v_lo, v_hi))
    best = None
    for i in range(int(cal_cfg["max_iterations"])):
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
    board.scale = (float(ta["cobble"]["board_size_m"]),) * 3
    cal = {"method": cal_cfg["method"], "target_board_p50_luma": tgt, "tolerance_luma": tol, "roi_px": cal_cfg["roi_px"],
           "camera": cm, "base_exposure": round(base_exp, 4), "exposure_offset_stops": off,
           "blender_exposure": round(base_exp + off, 4), "k1_board_p50_final": final, "steps": steps,
           "label": "blender EEVEE, фигура скрыта; якорь W4-A"}
    U.write_json(run_dir / "reports" / "ld-team-cobble-calibration.json", cal)
    scene.view_settings.exposure = base_exp + off
    report = {"schema": "unmatched.h2-lookdev-teamaccent.render/1", "frames": {},
              "lights": {"cobble": {"source": cc["source"], "key_lux": cc["key_lux"], "key_travel_dir": [round(x, 4) for x in travel],
                                    "sky_intensity": cc["sky_intensity"], "dome_sha256": hashlib.sha256(dome_path.read_bytes()).hexdigest(),
                                    "board": {"albedo_linear": cc["board_albedo_linear"], "roughness": cc["board_roughness"],
                                              "size_m": ta["cobble"]["board_size_m"]},
                                    "ev100": cc["ev100"], "exposure_offset_stops": off, "blender_exposure": cal["blender_exposure"],
                                    "k1_board_p50": final, "view_transform": cc["view_transform"], "eevee_raytracing": True,
                                    "eevee_samples": int(rcfg["eevee_samples"]), "backface_culling": cull,
                                    "not_included": cc.get("not_included", "")}}}
    for key in ("ld", "ld_p1", "ld_p2"):
        use(key)
        for vname, v in views.items():
            path = out / "cobble" / key / (vname + ".png")
            shoot(path, v)
            report["frames"]["cobble/%s/%s" % (key, vname)] = str(path.relative_to(run_dir).as_posix())
        print("ta_render set", key, round(time.time() - t0, 1), flush=True)
    # ---------------------------------------------------------------- ID pass (Cycles emission, exact per pixel)
    device = U.setup_cycles(scene, "GPU", samples=1, seed=0)
    scene.cycles.filter_width = 0.01
    scene.view_settings.exposure = 0.0
    try:
        scene.view_settings.view_transform = "Raw"
    except TypeError:
        scene.view_settings.view_transform = "Standard"
    scene.render.film_transparent = True
    scene.render.image_settings.color_mode = "RGBA"
    use("id")
    for vname, v in views.items():
        path = out / "id" / (vname + ".png")
        shoot(path, v, hide=[board])
        report["frames"]["id/%s" % vname] = str(path.relative_to(run_dir).as_posix())
    report["id_pass"] = {"engine": "CYCLES", "device": device, "samples": 1, "filter_width_px": 0.01,
                         "view_transform": scene.view_settings.view_transform}
    report["views"] = {k: {kk: (list(x) if isinstance(x, tuple) else x) for kk, x in v.items()} for k, v in views.items()}
    report["seconds"] = round(time.time() - t0, 1)
    U.write_json(out / "render-report.json", report)
