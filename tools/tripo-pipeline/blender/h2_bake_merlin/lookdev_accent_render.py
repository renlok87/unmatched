"""TeamAccent frames of Merlin (headless Blender, EEVEE / Workbench): Cobble-lit K2 frames and ID frames.

blender -b --factory-startup --python-exit-code 1 --python lookdev_accent_render.py -- <lookdev profile.json> <job.json>

job.json (written by lookdev_accent.py):
  {"out": dir, "sets": {label: {"BC": png, "ORM": png, "N": png}}, "views": [view], "id_sets": {label: png},
   "id_views": [view], "calibrate": true|false}
Mesh: the look-dev FBX pair (export/SK_Merlin_H2LD.fbx + SM_Merlin_H2LD_Base.fbx) imported and turned back to the
authored frame (face -Y), as ld_render_*; geometry, rig and UV are read, never written (nothing is saved).
Material of a set: Principled BSDF with BC (sRGB), ORM (G roughness, B metallic) and N (DirectX, G inverted in the
shader) - stage_preview.pbr_material; the M_UM_Figure_v2 core is not evaluated here (see lookdev_accent.py: the
dye of the accent is applied to the BC in numpy with the v2 formula).
Light "cobble" (profile lookdev.team_accent.frames.cobble, the numbers of the Arthur / Harpy look-dev frames):
  S08ArtBoardProfiles cobble-probe approximation - key sun 4.5 lux, pitch -55, yaw 30 relative to the camera
  (the key turns with the camera azimuth: a back view is the figure turned round on the board, the camera and the
  light stay), W4-A ambient dome (tools/art/render/make_ambient_dome_hdr.py) x 11.2, flat board of the cobblestone
  mean albedo, AgX, EEVEE ray tracing; exposure CALIBRATED to the W4-A anchor: figure hidden, 40 m board, K1 camera
  (FOV 35, 19.31 m, pitch -55), offset bisected until the K1 board ROI p50 luma = 131.2 (+-0.75).
ID frames: Workbench, flat texture colour, Closest, no anti-aliasing, Standard view (the pixel = the ID colour).
Writes <out>/cobble/<label>/<view>.png, <out>/id/<label>/<view>.png, <out>/render-report.json and
reports/ld-accent-cobble-calibration.json. Every frame is a Blender render, not UE.
"""

import math
import sys
import time
from pathlib import Path

import bpy
import numpy as np
from mathutils import Vector

sys.path.insert(0, str(Path(__file__).resolve().parent))
import blib as B  # noqa: E402
import common as C  # noqa: E402
import stage_preview as SP  # noqa: E402  (helpers only)

B.require_background("lookdev_accent_render.py")


def main():
    args = B.script_args()
    prof = C.Profile(args[0])
    job = C.load_json(args[1])
    ld = prof["lookdev"]
    fcfg = ld["team_accent"]["frames"]
    CC = fcfg["cobble"]
    CAL = CC["exposure_calibration"]
    out = Path(job["out"])
    t0 = time.time()
    B.empty_file()
    scene = bpy.context.scene
    cam, lights = SP.setup_scene(scene)
    for lo in lights:
        bpy.data.objects.remove(lo)
    col = bpy.data.collections.new("LD")
    scene.collection.children.link(col)
    objs = (SP.import_fbx_authored(prof.export / ld["exports"]["skeletal_fbx"], col)
            + SP.import_fbx_authored(prof.export / ld["exports"]["base_fbx"], col))
    meshes = [o for o in objs if o.type == "MESH"]
    for o in objs:
        if o.type == "ARMATURE":
            o.hide_render = True
    arm = next(o for o in objs if o.type == "ARMATURE")

    def bone_mid(name, t=0.5):
        b = arm.data.bones[name]
        return arm.matrix_world @ (b.head_local * (1 - t) + b.tail_local * t)

    # ------------------------------------------------------------------ views
    views = {}
    for tag, dist_uu in fcfg["k2_distance_uu"].items():
        for az in fcfg["k2_azimuths"]:
            views["k2_%s_az%d" % (tag, az)] = {"kind": "game", "dist": dist_uu / 100.0, "az": float(az)}
    for name, c in fcfg["closeups"].items():
        centre = bone_mid(c["bone"], c.get("t", 0.5)) + Vector(c.get("offset_m", (0, 0, 0)))
        views[name] = {"kind": "ortho", "centre": tuple(centre), "scale": float(c["scale_m"]),
                       "direction": c["direction"], "az": {"front": 0.0, "back": 180.0, "left": 90.0, "right": -90.0}[c["direction"]],
                       "res": tuple(c.get("res", (900, 900)))}
    focus = Vector((0.0, 0.0, float(fcfg["k2_focus_above_cell_uu"]) / 100.0))

    def place(v):
        if v["kind"] == "game":
            SP.game_cam(cam, focus, v["dist"], float(fcfg["k2_pitch_deg"]), v["az"], float(fcfg["k2_hfov_deg"]))
            return tuple(fcfg["k2_resolution"])
        if v["kind"] == "k1":
            SP.game_cam(cam, Vector((0, 0, 0)), v["dist"], v["pitch"], 0.0, v["fov"])
            return v["res"]
        SP.ortho(cam, v["direction"], v["centre"], v["scale"])
        return v["res"]

    frames = {}

    def shoot(path, v, hide_figure=False):
        for o in meshes:
            o.hide_render = hide_figure
        res = place(v)
        scene.render.resolution_x, scene.render.resolution_y = res
        scene.render.resolution_percentage = 100
        scene.render.image_settings.file_format = "PNG"
        scene.render.image_settings.color_mode = "RGB"
        scene.render.image_settings.color_depth = "8"
        path.parent.mkdir(parents=True, exist_ok=True)
        scene.render.filepath = str(path)
        bpy.ops.render.render(write_still=True)
        C.strip_png_metadata(path)
        return C.sha256(path)

    # ------------------------------------------------------------------ Cobble light
    sys.path.insert(0, str(C.REPO / "tools" / "art" / "render"))
    import make_ambient_dome_hdr as dome  # noqa: E402
    dome_path = prof.work / "lookdev" / "accent" / "cobble-ambient-dome.hdr"
    data = dome.build()
    if not dome_path.exists() or dome_path.read_bytes() != data:
        dome_path.parent.mkdir(parents=True, exist_ok=True)
        dome_path.write_bytes(data)
    scene.render.engine = "BLENDER_EEVEE"
    scene.eevee.taa_render_samples = int(fcfg["eevee_samples"])
    scene.eevee.use_raytracing = True
    world = bpy.data.worlds.new("ld_cobble")
    world.use_nodes = True
    scene.world = world
    wnt = world.node_tree
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
    wout = next(n for n in wnt.nodes if n.bl_idname == "ShaderNodeOutputWorld")
    wnt.links.new(bg.outputs[0], wout.inputs["Surface"])
    key_d = bpy.data.lights.new("cobble_key", "SUN")
    key_d.energy = float(CC["key_lux"])
    key_d.color = tuple(CC["key_colour_linear"])
    key_d.angle = math.radians(float(CC["key_source_angle_deg"]))
    key = bpy.data.objects.new("cobble_key", key_d)
    scene.collection.objects.link(key)
    pitch, yaw = math.radians(CC["key_pitch_deg"]), math.radians(CC["key_yaw_deg"])
    travel0 = Vector((math.cos(pitch) * math.sin(yaw), math.cos(pitch) * math.cos(yaw), math.sin(pitch)))

    def key_for(az_deg):
        a = math.radians(az_deg)
        tr = Vector((travel0.x * math.cos(a) - travel0.y * math.sin(a), travel0.x * math.sin(a) + travel0.y * math.cos(a),
                     travel0.z))
        key.rotation_euler = tr.to_track_quat("-Z", "Y").to_euler()
        return [round(x, 4) for x in tr]

    bpy.ops.mesh.primitive_plane_add(size=1.0, location=(0.0, 0.0, -0.0005))
    board = bpy.context.active_object
    board.name = "ld_board"
    bm = bpy.data.materials.new("ld_board")
    bm.use_nodes = True
    bsdf = next(n for n in bm.node_tree.nodes if n.bl_idname == "ShaderNodeBsdfPrincipled")
    bsdf.inputs["Base Color"].default_value = (*CC["board_albedo_linear"], 1.0)
    bsdf.inputs["Roughness"].default_value = float(CC["board_roughness"])
    board.data.materials.append(bm)
    board.scale = (float(CC["board_size_m"]),) * 3
    scene.view_settings.view_transform = CC["view_transform"]
    scene.view_settings.look = "None"
    base_exposure = math.log2(1.0 / (1.2 * 2.0 ** float(CC["ev100"])))

    def board_p50(path, roi):
        img = bpy.data.images.load(str(path), check_existing=False)
        img.colorspace_settings.name = "Non-Color"
        w, h = img.size
        px = np.empty(w * h * 4, dtype=np.float32)
        img.pixels.foreach_get(px)
        bpy.data.images.remove(img)
        px = px.reshape(h, w, 4)[::-1]
        rgb = np.round(px[..., :3] * 255.0)
        lum = 0.2126 * rgb[..., 0] + 0.7152 * rgb[..., 1] + 0.0722 * rgb[..., 2]
        x0, y0, x1, y1 = roi
        return round(float(np.percentile(lum[y0:y1, x0:x1], 50)), 3)

    cal_file = prof.reports / "ld-accent-cobble-calibration.json"
    if job.get("calibrate") or not cal_file.exists():
        cal_dir = prof.work / "lookdev" / "accent" / "cobble-calibration"
        board.scale = (float(CAL["calibration_board_size_m"]),) * 3
        cm = CAL["camera"]
        k1 = {"kind": "k1", "dist": float(cm["distance_m"]), "pitch": float(cm["pitch_deg"]), "fov": float(cm["fov_h_deg"]),
              "res": tuple(CAL["res"])}
        key_for(float(cm["azimuth_deg"]))
        tgt, tol = float(CAL["target_board_p50_luma"]), float(CAL["tolerance_luma"])
        lo, hi = (float(x) for x in CAL["search_stops"])
        steps = []

        def measure(off, tag):
            scene.view_settings.exposure = base_exposure + off
            path = cal_dir / ("k1_board_%s.png" % tag)
            shoot(path, k1, hide_figure=True)
            p50 = board_p50(path, CAL["roi_px"])
            steps.append({"offset_stops": round(off, 5), "k1_board_p50": p50})
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
        board.scale = (float(CC["board_size_m"]),) * 3
        C.write_json(cal_file, {"method": CAL["method"], "target_board_p50_luma": tgt, "tolerance_luma": tol,
                                "roi_px": CAL["roi_px"], "camera": cm, "base_exposure": round(base_exposure, 4),
                                "exposure_offset_stops": off, "blender_exposure": round(base_exposure + off, 4),
                                "k1_board_p50_final": final, "steps": steps, "blender": bpy.app.version_string,
                                "passed": abs(final - tgt) <= tol})
    cal = C.load_json(cal_file)
    scene.view_settings.exposure = float(cal["blender_exposure"])
    report = {"schema": "unmatched.merlin-lookdev.accent-render/1", "job": C.rel(args[1]), "blender": bpy.app.version_string,
              "lights": {"cobble": {"key_lux": CC["key_lux"], "key_pitch_deg": CC["key_pitch_deg"],
                                    "key_yaw_deg_relative_to_camera": CC["key_yaw_deg"],
                                    "sky": "W4-A ambient dome x %s (sha256 %s)" % (CC["sky_intensity"], C.sha256(dome_path)),
                                    "board": {"albedo_linear": CC["board_albedo_linear"], "roughness": CC["board_roughness"],
                                              "size_m": CC["board_size_m"]},
                                    "ev100": CC["ev100"], "exposure_offset_stops": cal["exposure_offset_stops"],
                                    "blender_exposure": cal["blender_exposure"], "k1_board_p50": cal["k1_board_p50_final"],
                                    "calibration": C.rel(cal_file), "view_transform": CC["view_transform"],
                                    "eevee_samples": fcfg["eevee_samples"], "eevee_raytracing": True,
                                    "not_included": CC["not_included"]}},
              "frames": {}, "key_travel_by_view": {}}
    mats = {}
    for label, s in job["sets"].items():
        mats[label] = SP.pbr_material("ACC_" + label, s["BC"], s["ORM"], s["N"], True)
    for vname in job["views"]:
        v = views[vname]
        report["key_travel_by_view"][vname] = key_for(v["az"])
        for label in job["sets"]:
            SP.assign(meshes, mats[label])
            path = out / "cobble" / label / (vname + ".png")
            report["frames"]["cobble/%s/%s" % (label, vname)] = {"file": C.rel(path), "sha256": shoot(path, v)}
        print("view", vname, round(time.time() - t0, 1), flush=True)
    # ------------------------------------------------------------------ ID frames (Workbench)
    if job.get("id_sets"):
        board.hide_render = True
        scene.render.engine = "BLENDER_WORKBENCH"
        scene.display.shading.light = "FLAT"
        scene.display.shading.color_type = "TEXTURE"
        scene.display.render_aa = "OFF"
        scene.view_settings.view_transform = "Standard"
        scene.view_settings.exposure = 0.0
        world.use_nodes = False
        for label, png in job["id_sets"].items():
            m = bpy.data.materials.new("ID_" + label)
            m.use_nodes = True
            nt = m.node_tree
            tex = nt.nodes.new("ShaderNodeTexImage")
            tex.image = bpy.data.images.load(str(png), check_existing=False)
            tex.image.colorspace_settings.name = "sRGB"
            tex.interpolation = "Closest"
            bsdf_i = next(n for n in nt.nodes if n.bl_idname == "ShaderNodeBsdfPrincipled")
            nt.links.new(tex.outputs["Color"], bsdf_i.inputs["Base Color"])
            nt.nodes.active = tex
            SP.assign(meshes, m)
            for vname in job["id_views"]:
                path = out / "id" / label / (vname + ".png")
                report["frames"]["id/%s/%s" % (label, vname)] = {"file": C.rel(path), "sha256": shoot(path, views[vname])}
        report["lights"]["id"] = {"mode": "Workbench FLAT, texture colour, Closest, no anti-aliasing, Standard"}
    report["views"] = {k: {kk: (list(x) if isinstance(x, tuple) else x) for kk, x in v.items()} for k, v in views.items()}
    report["seconds"] = round(time.time() - t0, 1)
    C.write_json(out / "render-report.json", report)
    print("H2_STAGE_OK ld_accent_render", report["seconds"])


main()
