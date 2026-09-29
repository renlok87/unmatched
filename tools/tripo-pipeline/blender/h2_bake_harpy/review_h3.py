"""H3 review frames: the same cameras for the H2.1 baseline (harpy-h2-bake/3) and the H3 candidate (headless only).

    blender -b --factory-startup --python review_h3.py -- <profile.json> <run_dir> <baseline_run_dir> [--only-cobble]

--only-cobble re-renders only the Cobble-light frames (cobble_*, cobwarm_*, cobble_board_*) and the exposure
calibration, and merges them into the existing record (the other frames and their record entries are kept).

Both candidates are rendered from their own work/h2-candidate.blend (rest pose, their own atlas and metal base; the
images are re-pointed to each run's textures/ as review_h21.py does). Back faces culled as in UE. Every frame is a
Blender frame, never an UE frame. The reference of every comparison sheet is the CONCEPT (compose_h3.py puts the
concept panel first), not the previous iteration.

Two lights:
  preview  review.py neutral preview light (EEVEE, sun 3.0 + 1.3, grey world 0.55, Standard): the H2/H2.1 review light
  cobble   approximation of the UE Cobble board light (profile review.h3.cobble = S08ArtBoardProfiles.json
           lightProfiles.cobble-probe): one sun = the directional key (4.5 lux -> sun strength 1:1, UE pitch -55 /
           yaw 30 taken relative to the camera of azimuth 0 as the Arthur H2.2 compare stage), the W4-A ambient dome
           (tools/art/render/make_ambient_dome_hdr.py, same bytes) x sky intensity 11.2 as the world (the camera sees
           it), a flat board plane of the cobblestone mean albedo (8 m, fills the K2 frames), exposure
           log2(1 / (1.2 * 2^EV100)) with EV100 1.3 (render-reference / profile) PLUS a measured offset: the offset is
           bisected (figure hidden, 40 m board, K1 camera FOV 35 at 19.31 m, pitch -55) until the p50 luma of the K1
           board ROI (x 600-1360, y 700-940, t42_sky_calib_editor.BOARD_K1_BOX) is the W4-A anchor 131.2 of the
           cobble-probe sky.calibration (profile review.h3.cobble.exposure_calibration; record
           <run>/reports/cobble-calibration.json). AgX (else Filmic) view transform, EEVEE ray tracing. "cobble" =
           the profile's white key; "cobwarm" = the same with the warm key tint of the H3 brief (assumption, not the
           profile), same calibrated exposure. Not UE, not Lumen.

Frames (<run>/work/h3-frames/<who>_<name>.png, who = h21 | h3; record <run>/preview/h3/review-frames-h3.json):
  concept_{front,side,back}      ortho, framed like the concepts, transparent film
  close_{face_front,face_game,nape_back,nape_game,talons_3q,talons_front,base_band}   ortho close-ups (preview light)
  k2_{5x,1p6x}_az{000,040,140,180}  game camera (FOV 35, pitch -55) at 3.86 / 12.07 m on a 1 m cell (preview light)
  cobble_k2_5x_az{000,040,180}, cobble_k2_1p6x_az040, cobble_close_face_game, cobble_close_nape_game
  cobwarm_k2_5x_az{000,040}      (both runs)
  cobble_board_k2_5x_az{000,040} board only, figure and base hidden (K2 5x board luma check; H3 run only)
  cobble_mask_body_k2_5x_az{000,040}  body only on a transparent film (alpha = body coverage for the colour
                                 measurement of compose_h3.py; both runs)
  cobvt_<vt>_{close_talons_3q,close_face_game,k2_5x_az000}  the Cobble light under the probe view transforms
                                 (profile review.h3.cobble.view_transform_probe), each calibrated to the same anchor
  team_{gold,silver}_k2_5x       H3 only
"""

import json
import math
import sys
from pathlib import Path

import bpy
from mathutils import Vector

sys.path.insert(0, str(Path(__file__).resolve().parent))
import common as C  # noqa: E402
import review as RV  # noqa: E402

C.require_background("review_h3.py")
a = C.script_args()
PROFILE_PATH, RUN, BASE_RUN = Path(a[0]).resolve(), Path(a[1]).resolve(), Path(a[2]).resolve()
ONLY_COBBLE = "--only-cobble" in a[3:]
P = C.load_profile(PROFILE_PATH)
H3 = P["review"]["h3"]
CC = H3["cobble"]
OUT = RUN / "work" / "h3-frames"
OUT.mkdir(parents=True, exist_ok=True)
REC = RUN / "preview" / "h3"
REC.mkdir(parents=True, exist_ok=True)
team_lin = {"Gold": (0.807, 0.527, 0.144), "Silver": (0.347, 0.539, 0.686)}
K2 = P["review"].get("k2_live", {}).get("distances_m", {"5x": 3.86, "1.6x": 12.07})
GC = P["review"]["game_camera"]
sys.path.insert(0, str(C.REPO / "tools" / "art" / "render"))
import make_ambient_dome_hdr as dome  # noqa: E402

DOME = RUN / "work" / "cobble-ambient-dome.hdr"
_data = dome.build()
if not DOME.exists() or DOME.read_bytes() != _data:
    DOME.write_bytes(_data)
frames = {"_light": {}}
CAL = {"offset_stops": None}


def load(run_dir):
    bpy.ops.wm.open_mainfile(filepath=str(run_dir / "work" / "h2-candidate.blend"))
    scene = bpy.context.scene
    N_ = P["names"]
    body = bpy.data.objects[N_["body_object"]]
    base = bpy.data.objects[N_["base_object"]]
    arm = next(o for o in scene.objects if o.type == "ARMATURE")
    for o in (body, base):
        mw = o.matrix_world.copy()
        o.parent = None
        o.matrix_world = mw
        for m in list(o.modifiers):
            o.modifiers.remove(m)
    arm.hide_render = True
    for o in list(scene.objects):
        if o.type in ("CAMERA", "LIGHT"):
            bpy.data.objects.remove(o)
    for m in bpy.data.materials:
        m.use_backface_culling = True
    rebased = []
    for img in bpy.data.images:
        parts = Path(bpy.path.abspath(img.filepath)).parts if img.filepath else ()
        if "textures" in parts:
            new = run_dir.joinpath(*parts[parts.index("textures"):])
            if new.exists():
                img.filepath = str(new)
                img.reload()
                rebased.append("/".join(new.parts[-3:]))
    frames.setdefault("_images", {})[run_dir.name] = rebased
    cam = RV.setup_scene(scene, samples=64)
    base["um_instance_index"] = 3.0
    base["um_team_color"] = team_lin["Gold"] + (1.0,)
    rig = json.loads((run_dir / "reports" / "h2-rig-report.json").read_text(encoding="utf-8"))
    return scene, cam, body, base, rig


def cobble(scene, warm=False):
    """Replace the preview light by the Cobble approximation (see module doc)."""
    for o in list(scene.objects):
        if o.type == "LIGHT":
            bpy.data.objects.remove(o)
    w = bpy.data.worlds.new("h3_cobble_world")
    scene.world = w
    try:
        w.use_nodes = True
    except AttributeError:
        pass
    nt = w.node_tree
    for n in list(nt.nodes):
        if n.bl_idname != "ShaderNodeOutputWorld":
            nt.nodes.remove(n)
    env = nt.nodes.new("ShaderNodeTexEnvironment")
    env.image = bpy.data.images.load(str(DOME), check_existing=True)
    env.image.colorspace_settings.name = "Linear Rec.709"
    bg = nt.nodes.new("ShaderNodeBackground")
    bg.inputs[1].default_value = float(CC["sky_intensity"])
    tint = nt.nodes.new("ShaderNodeVectorMath")
    tint.operation = "MULTIPLY"
    nt.links.new(env.outputs["Color"], tint.inputs[0])
    tint.inputs[1].default_value = tuple(float(x) for x in CC["sky_colour_linear"])
    nt.links.new(tint.outputs["Vector"], bg.inputs[0])
    out = next(n for n in nt.nodes if n.bl_idname == "ShaderNodeOutputWorld")
    nt.links.new(bg.outputs[0], out.inputs["Surface"])
    pitch, yaw = math.radians(CC["key_pitch_deg"]), math.radians(CC["key_yaw_deg"])
    travel = Vector((math.cos(pitch) * math.sin(yaw), math.cos(pitch) * math.cos(yaw), math.sin(pitch)))
    ld = bpy.data.lights.new("cobble_key", "SUN")
    ld.energy = float(CC["key_lux"])
    col = CC["warm_variant_key_colour_linear"] if warm else CC["key_colour_linear"]
    ld.color = tuple(float(x) for x in col)
    ld.angle = math.radians(0.5357)
    lo = bpy.data.objects.new("cobble_key", ld)
    lo.rotation_euler = travel.to_track_quat("-Z", "Y").to_euler()
    scene.collection.objects.link(lo)
    bpy.ops.mesh.primitive_plane_add(size=float(CC["board_size_m"]), location=(0.0, 0.0, -0.0005))
    board = bpy.context.active_object
    board.name = "cobble_board"
    bm = bpy.data.materials.new("cobble_board")
    try:
        bm.use_nodes = True
    except AttributeError:
        pass
    bsdf = next(n for n in bm.node_tree.nodes if n.bl_idname == "ShaderNodeBsdfPrincipled")
    bsdf.inputs["Base Color"].default_value = (*CC["board_albedo_linear"], 1.0)
    bsdf.inputs["Roughness"].default_value = float(CC["board_roughness"])
    board.data.materials.append(bm)
    try:
        scene.eevee.use_raytracing = True
    except AttributeError:
        pass
    vt = None
    for cand in CC.get("view_transform_preference", ["AgX", "Filmic", "Standard"]):
        try:
            scene.view_settings.view_transform = cand
            vt = cand
            break
        except TypeError:
            continue
    scene.view_settings.look = "None"
    scene.view_settings.exposure = base_exposure() + (CAL["offset_stops"] or 0.0)
    frames["_light"]["cobwarm" if warm else "cobble"] = {
        "source": CC["source"], "key_lux": CC["key_lux"], "key_colour_linear": list(col),
        "key_travel_dir": [round(x, 4) for x in travel], "sky": "ambient dome x %s (%s, sha256 %s)" % (
            CC["sky_intensity"], C.rel(DOME), C.sha256(DOME)), "ev100": CC["ev100"],
        "blender_exposure": round(scene.view_settings.exposure, 4), "view_transform": vt,
        "exposure_offset_stops": CAL["offset_stops"], "exposure_calibration": "reports/cobble-calibration.json",
        "board": {"albedo_linear": CC["board_albedo_linear"], "roughness": CC["board_roughness"],
                  "size_m": CC["board_size_m"]},
        "not_included": CC.get("not_included"), "warm_point_note": CC.get("warm_point_note")}
    return board


def base_exposure():
    return math.log2(1.0 / (1.2 * 2.0 ** float(CC["ev100"])))


def board_p50(path, roi):
    """p50 of Rec.709 luma (0-255) of the 8-bit sRGB PNG in roi = (x0, y0, x1, y1), top-left origin."""
    import numpy as np
    img = bpy.data.images.load(str(path), check_existing=False)
    img.colorspace_settings.name = "Non-Color"  # raw stored 8-bit values, no display transform
    w, h = img.size
    px = np.empty(w * h * 4, dtype=np.float32)
    img.pixels.foreach_get(px)
    bpy.data.images.remove(img)
    px = px.reshape(h, w, 4)[::-1]  # Blender rows are bottom-up
    rgb = np.round(px[..., :3] * 255.0)
    L = 0.2126 * rgb[..., 0] + 0.7152 * rgb[..., 1] + 0.0722 * rgb[..., 2]
    x0, y0, x1, y1 = roi
    return round(float(np.percentile(L[y0:y1, x0:x1], 50)), 3)


def bisect_offset(scene, cam, hide, board, prefix="k1_board"):
    """Bisect the exposure offset until the K1 board ROI p50 is the W4-A anchor (see module doc) for the current
    view transform; returns (offset, final p50, steps)."""
    ec = CC["exposure_calibration"]
    cal_dir = RUN / "work" / "cobble-calibration"
    cal_dir.mkdir(parents=True, exist_ok=True)
    for o in hide:
        o.hide_render = True
    size0 = float(CC["board_size_m"])
    board.scale = (float(ec["calibration_board_size_m"]) / size0,) * 3
    cm = ec["camera"]
    tgt, tol = float(ec["target_board_p50_luma"]), float(ec["tolerance_luma"])
    lo, hi = (float(x) for x in ec["search_stops"])
    steps = []

    def measure(off, tag):
        scene.view_settings.exposure = base_exposure() + off
        path = cal_dir / ("%s_%s.png" % (prefix, tag))
        RV.shoot(scene, cam, path, RV.game_dir(cm["azimuth_deg"], cm["pitch_deg"]), (0.0, 0.0, 0.0),
                 fov_h=cm["fov_h_deg"], distance=float(cm["distance_m"]), res=tuple(ec["res"]))
        v = board_p50(path, ec["roi_px"])
        steps.append({"offset_stops": round(off, 5), "k1_board_p50": v, "frame": C.rel(path)})
        return v

    v_lo, v_hi = measure(lo, "lo"), measure(hi, "hi")
    if not (v_lo < tgt < v_hi):
        raise SystemExit("calibration target %.1f outside [%.1f, %.1f] for offsets [%g, %g]" % (tgt, v_lo, v_hi, lo, hi))
    best = None
    for i in range(int(ec["max_iterations"])):
        mid = 0.5 * (lo + hi)
        v = measure(mid, "i%02d" % i)
        if best is None or abs(v - tgt) < abs(best[1] - tgt):
            best = (mid, v)
        if abs(v - tgt) <= tol:
            break
        if v < tgt:
            lo = mid
        else:
            hi = mid
    off = round(best[0], 4)
    final = measure(off, "final")
    for o in hide:
        o.hide_render = False
    board.scale = (1.0, 1.0, 1.0)
    return off, final, steps


def calibrate(scene, cam, hide, board):
    ec = CC["exposure_calibration"]
    cm = ec["camera"]
    tgt, tol = float(ec["target_board_p50_luma"]), float(ec["tolerance_luma"])
    off, final, steps = bisect_offset(scene, cam, hide, board)
    CAL["offset_stops"] = off
    rec = {"schema": "unmatched.h3-cobble-calibration/1",
           "label": "blender frames (EEVEE, AgX), figure hidden; approximation of the UE Cobble light, not an UE frame",
           "anchor": "S08ArtBoardProfiles.json lightProfiles.cobble-probe sky.calibration: K1 board ROI p50 131.2",
           "method": ec["method"], "roi_px": ec["roi_px"], "roi_source": ec["roi_source"], "camera": cm,
           "calibration_board_size_m": ec["calibration_board_size_m"], "board_albedo_linear": CC["board_albedo_linear"],
           "board_roughness": CC["board_roughness"], "target_board_p50_luma": tgt, "tolerance_luma": tol,
           "ev100": CC["ev100"], "base_exposure": round(base_exposure(), 4), "exposure_offset_stops": off,
           "blender_exposure": round(base_exposure() + off, 4), "k1_board_p50_final": final, "steps": steps,
           "view_transform": scene.view_settings.view_transform}
    C.write_json(RUN / "reports" / "cobble-calibration.json", rec)
    frames["_calibration"] = {k: rec[k] for k in ("exposure_offset_stops", "blender_exposure", "k1_board_p50_final",
                                                   "target_board_p50_luma")}
    CAL["record"] = rec
    print("COBBLE_CALIBRATION offset %+.4f stops -> K1 board p50 %.2f (target %.1f)" % (off, final, tgt), flush=True)


def vt_probe(scene, cam, shoot, who, body, base, board, fc):
    """Diagnostic: the same Cobble light under other view transforms, each re-calibrated to the same K1 board anchor,
    so the band / face colour can be split into material and display-transform effects (profile
    review.h3.cobble.view_transform_probe). Frames cobvt_<slug>_{close_talons_3q,close_face_game,k2_5x_az000}."""
    vt0, exp0 = scene.view_settings.view_transform, scene.view_settings.exposure
    probe = CAL["record"].setdefault("view_transform_probe", {})
    for vt in CC.get("view_transform_probe", []):
        slug = vt.lower().replace(" ", "_")
        try:
            scene.view_settings.view_transform = vt
        except TypeError:
            probe[vt] = {"available": False}
            continue
        scene.view_settings.look = "None"
        if vt not in probe:
            off, final, steps = bisect_offset(scene, cam, (body, base), board, prefix="k1_board_" + slug)
            probe[vt] = {"available": True, "exposure_offset_stops": off, "k1_board_p50_final": final,
                         "blender_exposure": round(base_exposure() + off, 4), "steps": steps}
        scene.view_settings.exposure = base_exposure() + probe[vt]["exposure_offset_stops"]
        shoot("cobvt_%s_close_talons_3q" % slug, (0.7, -0.7, 0.3), (0.035, -0.03, 0.085), ortho=0.14, res=(1000, 1000))
        shoot("cobvt_%s_close_face_game" % slug, RV.game_dir(0), (fc.x, fc.y, fc.z + 0.005), ortho=0.09,
              res=(1000, 1000))
        shoot("cobvt_%s_k2_5x_az000" % slug, RV.game_dir(0, GC["pitch_deg"]), (0, 0, 0.12),
              fov_h=GC["horizontal_fov_deg"], distance=float(K2["5x"]), res=(1920, 1080))
    scene.view_settings.view_transform = vt0
    scene.view_settings.look = "None"
    scene.view_settings.exposure = exp0
    C.write_json(RUN / "reports" / "cobble-calibration.json", CAL["record"])


def render_set(who, run_dir):
    scene, cam, body, base, rig = load(run_dir)

    def shoot(name, d, t, **kw):
        rec = RV.shoot(scene, cam, OUT / ("%s_%s.png" % (who, name)), d, t, **kw)
        rec["label"] = "blender"
        frames["%s_%s" % (who, name)] = rec

    span = rig["measure"]["bounds_body_m"]["max"][0] - rig["measure"]["bounds_body_m"]["min"][0]
    ortho = span / 0.89
    zc = 0.42 - (0.5 - 0.10) * 1070 * ortho / 1470
    fc = Vector(rig["measure"]["face_centroid_m"])
    head = Vector(next(s for s in rig["sockets"] if s["name"] == "Head")["target_blender_m"])
    nape = Vector((head.x, head.y + 0.02, head.z - 0.01))
    if not ONLY_COBBLE:
        preview_frames(scene, shoot, who, base, zc, ortho, fc, nape)
    # game-light approximation
    for warm in (False, True):
        board = cobble(scene, warm)
        if CAL["offset_stops"] is None:
            calibrate(scene, cam, (body, base), board)
            scene.view_settings.exposure = base_exposure() + CAL["offset_stops"]
            frames["_light"]["cobble"]["exposure_offset_stops"] = CAL["offset_stops"]
            frames["_light"]["cobble"]["blender_exposure"] = round(scene.view_settings.exposure, 4)
        tag = "cobwarm" if warm else "cobble"
        views = [("k2_5x_az000", 0, "5x"), ("k2_5x_az040", 40, "5x")]
        if not warm:
            views += [("k2_5x_az180", 180, "5x"), ("k2_1p6x_az040", 40, "1.6x")]
        for name, az, zoom in views:
            shoot("%s_%s" % (tag, name), RV.game_dir(az, GC["pitch_deg"]), (0, 0, 0.12),
                  fov_h=GC["horizontal_fov_deg"], distance=float(K2[zoom]), res=(1920, 1080))
        if not warm:
            shoot("cobble_close_face_game", RV.game_dir(0), (fc.x, fc.y, fc.z + 0.005), ortho=0.09, res=(1000, 1000))
            shoot("cobble_close_nape_game", RV.game_dir(180), tuple(nape), ortho=0.2, res=(1000, 1000))
            shoot("cobble_close_talons_3q", (0.7, -0.7, 0.3), (0.035, -0.03, 0.085), ortho=0.14, res=(1000, 1000))
            if who == "h3":
                body.hide_render = base.hide_render = True
                for name, az in (("k2_5x_az000", 0), ("k2_5x_az040", 40)):
                    shoot("cobble_board_" + name, RV.game_dir(az, GC["pitch_deg"]), (0, 0, 0.12),
                          fov_h=GC["horizontal_fov_deg"], distance=float(K2["5x"]), res=(1920, 1080))
                body.hide_render = base.hide_render = False
            # body-only coverage (alpha) for the colour measurement of compose_h3.py: board and base hidden
            base.hide_render = board.hide_render = True
            scene.render.film_transparent = True
            for name, az in (("k2_5x_az000", 0), ("k2_5x_az040", 40)):
                shoot("cobble_mask_body_" + name, RV.game_dir(az, GC["pitch_deg"]), (0, 0, 0.12),
                      fov_h=GC["horizontal_fov_deg"], distance=float(K2["5x"]), res=(1920, 1080))
            scene.render.film_transparent = False
            base.hide_render = board.hide_render = False
            vt_probe(scene, cam, shoot, who, body, base, board, fc)
        bpy.data.objects.remove(board)


def preview_frames(scene, shoot, who, base, zc, ortho, fc, nape):
    """Preview-light frames (concept framing, close-ups, K2, team colour)."""
    scene.render.film_transparent = True
    for tag, d in (("front", (0, -1, 0)), ("side", (1, 0, 0)), ("back", (0, 1, 0))):
        shoot("concept_%s" % tag, d, (0, 0, zc), ortho=ortho, res=(1470, 1070))
    scene.render.film_transparent = False
    close = [("face_front", (0, -1, 0.05), (fc.x, fc.y, fc.z + 0.005), 0.12),
             ("face_game", RV.game_dir(0), (fc.x, fc.y, fc.z + 0.005), 0.09),
             ("nape_back", (0, 1, 0.15), tuple(nape), 0.16),
             ("nape_game", RV.game_dir(180), tuple(nape), 0.2),
             ("talons_3q", (0.7, -0.7, 0.3), (0.035, -0.03, 0.085), 0.14),
             ("talons_front", (0, -1, 0.35), (0, -0.03, 0.085), 0.2),
             ("base_band", (0.35, -1, 0.35), (0.0, -0.06, 0.04), 0.2)]
    for name, d, t, o_ in close:
        shoot("close_" + name, d, t, ortho=o_, res=(1000, 1000))
    cells = RV.ground(scene, [(0.0, 0.0)])
    for zoom, dist in sorted(K2.items()):
        tagz = zoom.replace(".", "p")
        for az in (0, 40, 140, 180):
            shoot("k2_%s_az%03d" % (tagz, az), RV.game_dir(az, GC["pitch_deg"]), (0, 0, 0.12),
                  fov_h=GC["horizontal_fov_deg"], distance=float(dist), res=(1920, 1080))
    if who == "h3":
        for team in ("Gold", "Silver"):
            base["um_team_color"] = team_lin[team] + (1.0,)
            shoot("team_%s_k2_5x" % team.lower(), RV.game_dir(40, GC["pitch_deg"]), (0, 0, 0.12),
                  fov_h=GC["horizontal_fov_deg"], distance=float(K2["5x"]), res=(1920, 1080))
        base["um_team_color"] = team_lin["Gold"] + (1.0,)
    for o in cells:
        bpy.data.objects.remove(o)


render_set("h3", RUN)
render_set("h21", BASE_RUN)
if ONLY_COBBLE and (REC / "review-frames-h3.json").exists():
    old = json.loads((REC / "review-frames-h3.json").read_text(encoding="utf-8"))["frames"]
    keep = {k: v for k, v in old.items()
            if not (k.startswith("_") or k.split("_", 1)[1].startswith(("cobble_", "cobwarm_", "cobvt_")))}
    keep.update(frames)
    frames = keep
C.write_json(REC / "review-frames-h3.json", {
    "label": "blender frames (EEVEE); preview light or the Cobble approximation; back faces culled; not an UE frame",
    "baseline_run": C.rel(BASE_RUN), "baseline_label": H3.get("baseline_label"), "k2_distances_m": K2, "frames": frames})
print(C.STAGE_MARKER, "review_h3", len(frames), flush=True)
