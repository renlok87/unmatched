"""Stage ld_review of the Harpy look-dev v2 (headless Blender, EEVEE): control frames before the UE stage.

    blender -b --factory-startup --python lookdev_review.py -- <harpy-h3-lookdev.json> [--only NAME_PREFIX ...]

The H3 model (<H3 run>/work/h2-candidate.blend, rest pose, back faces culled as in UE) with the look-dev material:
M_UM_Figure_v2 is approximated per texel by ld_maps (work/lookdev/preview/LD_BC_{none,P1,P2}.png: LUT class values,
metal = hero F0 x clamp(Y(bake) / Ymed, 1 -+ m), dielectric luminance clamp, TeamAccent dye TeamDye 1 x hero gain;
LD_RMS.png: roughness = LUT typical, metallic, specular) - no detail tiles, no wear, no AO in the BSDF (as the H3
frames). Principled: Base Color, Roughness, Metallic, Specular IOR Level, Normal (H3 normal map). The base keeps its
M_Harpy_Base graph with the look-dev base textures; its team band shows the frame's team colour (P1 for "none").

Cameras and lights = review_h3.py (H3 rev 2), so every LD frame pairs with the H3 frame of the same name in
<H3 run>/work/h3-frames/h3_<name>.png:
  concept_{front,side,back}   ortho, concept framing (1470 x 1070 = concept pixels), transparent film, preview light
                              (Standard view: sRGB OETF, invertible for the colour measurement)
  id_concept_{front,side,back} class-ID pass of the same cameras (emission of the class colours, Closest, Standard)
  k2_5x_az{000,040,180}       game camera (FOV 35, pitch -55, 3.86 m), preview light
  close_talons_3q             ortho close-up of the band and the talons, preview light
  cobble_k2_5x_az{000,040}_{none,P1,P2}, cobble_k2_5x_az180_{none,P1}, cobble_close_talons_3q_{none,P1,P2}
                              the Cobble approximation of review_h3.py (dome x 11.2, 4.5 lux key, 8 m board, AgX),
                              exposure bisected to the W4-A anchor (K1 board ROI p50 131.2) in this run
  h3orm_{concept_front,cobble_k2_5x_az000,cobble_close_talons_3q}  control: the H3 textures (BC, ORM, N) in the
                              material of this script; must equal the H3 frames of review_h3.py (checks that the
                              LD / H3 difference comes from the maps, not from the preview material or the light)
Frames: <run>/work/ld-frames/<name>.png (local); record <run>/preview/ld-frames.json.
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

C.require_background("lookdev_review.py")
a = C.script_args()
PROF_PATH = Path(a[0]).resolve()
ONLY = a[a.index("--only") + 1:] if "--only" in a else None
PROF = C.load_profile(PROF_PATH)
LD = PROF["lookdev"]
RUN = C.REPO / PROF["run_dir"]
SRC_RUN = C.REPO / LD["source"]["run"]
SRC = C.load_profile(C.REPO / LD["source"]["profile"])
CC = SRC["review"]["h3"]["cobble"]
GC = SRC["review"]["game_camera"]
K2 = float(PROF["lookdev"]["review"]["k2_distance_m"])
OUT = RUN / "work" / "ld-frames"
OUT.mkdir(parents=True, exist_ok=True)
PV = RUN / "work" / "lookdev" / "preview"
PX = LD["prefix"]
TEAM_HEX = {"P1": "#E8C06A", "P2": "#5A7F9F"}
sys.path.insert(0, str(C.REPO / "tools" / "art" / "render"))
import make_ambient_dome_hdr as dome  # noqa: E402

DOME = RUN / "work" / "cobble-ambient-dome.hdr"
_data = dome.build()
if not DOME.exists() or DOME.read_bytes() != _data:
    DOME.write_bytes(_data)
frames = {}
CAL = {}


def hex_lin(h):
    out = []
    for i in (1, 3, 5):
        c = int(h[i:i + 2], 16) / 255.0
        out.append(c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4)
    return tuple(out)


def want(name):
    return ONLY is None or any(name.startswith(p) for p in ONLY)


def img(path, colour):
    im = bpy.data.images.load(str(path), check_existing=True)
    im.colorspace_settings.name = "sRGB" if colour else "Non-Color"
    return im


def ld_material(name, bc_path, rms_path, n_path, cull=True, orm_mode=False):
    """Principled with BC / roughness / metallic / specular / normal textures (UV0). orm_mode: RMS is an ORM texture
    (G roughness, B metallic, specular stays 0.5) - the H3 control."""
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    nt = m.node_tree
    N, L = nt.nodes, nt.links
    bsdf = next(n for n in N if n.type == "BSDF_PRINCIPLED")
    t_bc, t_r, t_n = N.new("ShaderNodeTexImage"), N.new("ShaderNodeTexImage"), N.new("ShaderNodeTexImage")
    t_bc.image, t_r.image, t_n.image = img(bc_path, True), img(rms_path, False), img(n_path, False)
    sep = N.new("ShaderNodeSeparateColor")
    L.new(t_bc.outputs["Color"], bsdf.inputs["Base Color"])
    L.new(t_r.outputs["Color"], sep.inputs["Color"])
    if orm_mode:
        L.new(sep.outputs["Green"], bsdf.inputs["Roughness"])
        L.new(sep.outputs["Blue"], bsdf.inputs["Metallic"])
    else:
        L.new(sep.outputs["Red"], bsdf.inputs["Roughness"])
        L.new(sep.outputs["Green"], bsdf.inputs["Metallic"])
        L.new(sep.outputs["Blue"], bsdf.inputs["Specular IOR Level"])
    nm = N.new("ShaderNodeNormalMap")
    L.new(t_n.outputs["Color"], nm.inputs["Color"])
    L.new(nm.outputs["Normal"], bsdf.inputs["Normal"])
    m.use_backface_culling = cull
    return m, t_bc


def id_material(path):
    m = bpy.data.materials.new("LD_ID")
    m.use_nodes = True
    nt = m.node_tree
    for n in list(nt.nodes):
        nt.nodes.remove(n)
    out = nt.nodes.new("ShaderNodeOutputMaterial")
    em = nt.nodes.new("ShaderNodeEmission")
    t = nt.nodes.new("ShaderNodeTexImage")
    t.image = img(path, True)   # sRGB in, Standard view out: the stored class colours come back unchanged
    t.interpolation = "Closest"
    nt.links.new(t.outputs["Color"], em.inputs["Color"])
    nt.links.new(em.outputs["Emission"], out.inputs["Surface"])
    m.use_backface_culling = True
    return m


def load():
    bpy.ops.wm.open_mainfile(filepath=str(SRC_RUN / "work" / "h2-candidate.blend"))
    scene = bpy.context.scene
    N_ = SRC["names"]
    body, base = bpy.data.objects[N_["body_object"]], bpy.data.objects[N_["base_object"]]
    arm = next(o for o in scene.objects if o.type == "ARMATURE")
    for o in (body, base):
        mw = o.matrix_world.copy()
        o.parent = None
        o.matrix_world = mw
        for mo in list(o.modifiers):
            o.modifiers.remove(mo)
    arm.hide_render = True
    for o in list(scene.objects):
        if o.type in ("CAMERA", "LIGHT"):
            bpy.data.objects.remove(o)
    atlas = body.data.materials[0]
    ln = {(l.from_node.type, l.to_socket.name) for l in atlas.node_tree.links}
    frames["_h3_atlas_links"] = sorted("%s->%s" % x for x in ln)
    for im in bpy.data.images:   # the base: look-dev base textures
        p = Path(bpy.path.abspath(im.filepath)) if im.filepath else None
        if p and "_Base_" in p.name:
            new = RUN / "textures" / "base_1k" / p.name.replace(LD["source"]["prefix"], PX)
            im.filepath = str(new)
            im.reload()
    for mt in bpy.data.materials:
        mt.use_backface_culling = True
    cam = RV.setup_scene(scene, samples=64)
    base["um_instance_index"] = 3.0
    rig = json.loads((SRC_RUN / "reports" / "h2-rig-report.json").read_text(encoding="utf-8"))
    return scene, cam, body, base, rig


def set_team(base, tag):
    base["um_team_color"] = hex_lin(TEAM_HEX["P1" if tag == "none" else tag]) + (1.0,)
    base.update_tag()


def cobble(scene):
    for o in list(scene.objects):
        if o.type == "LIGHT":
            bpy.data.objects.remove(o)
    w = bpy.data.worlds.new("ld_cobble_world")
    scene.world = w
    w.use_nodes = True
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
    ld.color = tuple(float(x) for x in CC["key_colour_linear"])
    ld.angle = math.radians(0.5357)
    lo = bpy.data.objects.new("cobble_key", ld)
    lo.rotation_euler = travel.to_track_quat("-Z", "Y").to_euler()
    scene.collection.objects.link(lo)
    bpy.ops.mesh.primitive_plane_add(size=float(CC["board_size_m"]), location=(0.0, 0.0, -0.0005))
    board = bpy.context.active_object
    board.name = "cobble_board"
    bm = bpy.data.materials.new("cobble_board")
    bm.use_nodes = True
    bsdf = next(n for n in bm.node_tree.nodes if n.bl_idname == "ShaderNodeBsdfPrincipled")
    bsdf.inputs["Base Color"].default_value = (*CC["board_albedo_linear"], 1.0)
    bsdf.inputs["Roughness"].default_value = float(CC["board_roughness"])
    board.data.materials.append(bm)
    try:
        scene.eevee.use_raytracing = True
    except AttributeError:
        pass
    for cand in CC.get("view_transform_preference", ["AgX", "Filmic", "Standard"]):
        try:
            scene.view_settings.view_transform = cand
            break
        except TypeError:
            continue
    scene.view_settings.look = "None"
    return board


def base_exposure():
    return math.log2(1.0 / (1.2 * 2.0 ** float(CC["ev100"])))


def board_p50(path, roi):
    import numpy as np
    im = bpy.data.images.load(str(path), check_existing=False)
    im.colorspace_settings.name = "Non-Color"
    w, h = im.size
    px = np.empty(w * h * 4, dtype=np.float32)
    im.pixels.foreach_get(px)
    bpy.data.images.remove(im)
    px = px.reshape(h, w, 4)[::-1]
    rgb = np.round(px[..., :3] * 255.0)
    lum = 0.2126 * rgb[..., 0] + 0.7152 * rgb[..., 1] + 0.0722 * rgb[..., 2]
    x0, y0, x1, y1 = roi
    return round(float(np.percentile(lum[y0:y1, x0:x1], 50)), 3)


def calibrate(scene, cam, hide, board):
    ec = CC["exposure_calibration"]
    cal_dir = RUN / "work" / "cobble-calibration"
    cal_dir.mkdir(parents=True, exist_ok=True)
    for o in hide:
        o.hide_render = True
    board.scale = (float(ec["calibration_board_size_m"]) / float(CC["board_size_m"]),) * 3
    cm = ec["camera"]
    tgt, tol = float(ec["target_board_p50_luma"]), float(ec["tolerance_luma"])
    lo, hi = (float(x) for x in ec["search_stops"])
    steps = []

    def measure(off, tag):
        scene.view_settings.exposure = base_exposure() + off
        path = cal_dir / ("k1_board_%s.png" % tag)
        RV.shoot(scene, cam, path, RV.game_dir(cm["azimuth_deg"], cm["pitch_deg"]), (0.0, 0.0, 0.0),
                 fov_h=cm["fov_h_deg"], distance=float(cm["distance_m"]), res=tuple(ec["res"]))
        v = board_p50(path, ec["roi_px"])
        steps.append({"offset_stops": round(off, 5), "k1_board_p50": v})
        return v

    v_lo, v_hi = measure(lo, "lo"), measure(hi, "hi")
    if not (v_lo < tgt < v_hi):
        raise RuntimeError("calibration target outside the search range: %s %s" % (v_lo, v_hi))
    best = None
    for i in range(int(ec["max_iterations"])):
        mid = 0.5 * (lo + hi)
        v = measure(mid, "i%02d" % i)
        if best is None or abs(v - tgt) < abs(best[1] - tgt):
            best = (mid, v)
        if abs(v - tgt) <= tol:
            break
        lo, hi = (mid, hi) if v < tgt else (lo, mid)
    off = round(best[0], 4)
    final = measure(off, "final")
    for o in hide:
        o.hide_render = False
    board.scale = (1.0, 1.0, 1.0)
    scene.view_settings.exposure = base_exposure() + off
    CAL.update({"schema": "unmatched.h3-cobble-calibration/1", "label": "blender (EEVEE, %s), figure hidden; approximation of "
                "the UE Cobble light, not an UE frame" % scene.view_settings.view_transform,
                "anchor": "S08ArtBoardProfiles.json lightProfiles.cobble-probe sky.calibration: K1 board ROI p50 131.2 (W4-A)",
                "method": ec["method"], "roi_px": ec["roi_px"], "camera": cm, "target_board_p50_luma": tgt, "tolerance_luma": tol,
                "ev100": CC["ev100"], "base_exposure": round(base_exposure(), 4), "exposure_offset_stops": off,
                "blender_exposure": round(base_exposure() + off, 4), "k1_board_p50_final": final, "steps": steps,
                "view_transform": scene.view_settings.view_transform})
    C.write_json(RUN / "reports" / "cobble-calibration.json", CAL)
    print("LD_COBBLE_CALIBRATION offset %+.4f -> p50 %.2f" % (off, final), flush=True)


def main():
    scene, cam, body, base, rig = load()
    n_path = RUN / "textures" / "2k" / ("%s_N_OpenGL.png" % PX)
    mat, t_bc = ld_material("LD_V2_PREVIEW", PV / "LD_BC_none.png", PV / "LD_RMS.png", n_path)
    sp = LD["source"]["prefix"]
    h3dir = SRC_RUN / "textures" / "4k"
    mat_h3, _ = ld_material("H3_ORM_CONTROL", h3dir / ("%s_BC.png" % sp), h3dir / ("%s_ORM.png" % sp),
                            h3dir / ("%s_N_OpenGL.png" % sp), orm_mode=True)
    mat_id = id_material(PV / "LD_CLASS.png")
    bc_imgs = {t: img(PV / ("LD_BC_%s.png" % t), True) for t in ("none", "P1", "P2")}

    def use(m, tag="none"):
        body.data.materials.clear()
        body.data.materials.append(m)
        if m is mat:
            t_bc.image = bc_imgs[tag]
        set_team(base, tag)

    def shoot(name, d, t, **kw):
        if not want(name):
            return
        rec = RV.shoot(scene, cam, OUT / (name + ".png"), d, t, **kw)
        rec.update(label="blender", view_transform=scene.view_settings.view_transform,
                   exposure=round(scene.view_settings.exposure, 4), material=body.data.materials[0].name)
        frames[name] = rec

    span = rig["measure"]["bounds_body_m"]["max"][0] - rig["measure"]["bounds_body_m"]["min"][0]
    ortho = span / 0.89
    zc = 0.42 - (0.5 - 0.10) * 1070 * ortho / 1470
    talons = dict(d=(0.7, -0.7, 0.3), t=(0.035, -0.03, 0.085), ortho=0.14)
    # ---------------------------------------------------------------- preview light
    scene.render.film_transparent = True
    for tag, d in (("front", (0, -1, 0)), ("side", (1, 0, 0)), ("back", (0, 1, 0))):
        use(mat)
        shoot("concept_%s" % tag, d, (0, 0, zc), ortho=ortho, res=(1470, 1070))
        use(mat_id)
        vt = scene.view_settings.view_transform
        scene.view_settings.view_transform = "Standard"
        eevee_samples, fs = scene.eevee.taa_render_samples, scene.render.filter_size
        scene.eevee.taa_render_samples, scene.render.filter_size = 1, 0.0
        shoot("id_concept_%s" % tag, d, (0, 0, zc), ortho=ortho, res=(1470, 1070))
        scene.eevee.taa_render_samples, scene.render.filter_size = eevee_samples, fs
        scene.view_settings.view_transform = vt
    use(mat_h3)
    shoot("h3orm_concept_front", (0, -1, 0), (0, 0, zc), ortho=ortho, res=(1470, 1070))
    scene.render.film_transparent = False
    use(mat)
    shoot("close_talons_3q", talons["d"], talons["t"], ortho=talons["ortho"], res=(1000, 1000))
    cells = RV.ground(scene, [(0.0, 0.0)])
    for az in (0, 40, 180):
        shoot("k2_5x_az%03d" % az, RV.game_dir(az, GC["pitch_deg"]), (0, 0, 0.12), fov_h=GC["horizontal_fov_deg"],
              distance=K2, res=(1920, 1080))
    for o in cells:
        bpy.data.objects.remove(o)
    # ---------------------------------------------------------------- Cobble
    board = cobble(scene)
    calibrate(scene, cam, (body, base), board)
    for tag in ("none", "P1", "P2"):
        use(mat, tag)
        for az in (0, 40) + ((180,) if tag != "P2" else ()):
            shoot("cobble_k2_5x_az%03d_%s" % (az, tag), RV.game_dir(az, GC["pitch_deg"]), (0, 0, 0.12),
                  fov_h=GC["horizontal_fov_deg"], distance=K2, res=(1920, 1080))
        shoot("cobble_close_talons_3q_%s" % tag, talons["d"], talons["t"], ortho=talons["ortho"], res=(1000, 1000))
    use(mat_h3)
    shoot("h3orm_cobble_k2_5x_az000", RV.game_dir(0, GC["pitch_deg"]), (0, 0, 0.12), fov_h=GC["horizontal_fov_deg"],
          distance=K2, res=(1920, 1080))
    shoot("h3orm_cobble_close_talons_3q", talons["d"], talons["t"], ortho=talons["ortho"], res=(1000, 1000))
    # body-only alpha (figure pixels for the colour measurement): board and base hidden
    use(mat, "none")
    base.hide_render = board.hide_render = True
    scene.render.film_transparent = True
    shoot("cobble_mask_body_k2_5x_az000", RV.game_dir(0, GC["pitch_deg"]), (0, 0, 0.12), fov_h=GC["horizontal_fov_deg"],
          distance=K2, res=(1920, 1080))
    rec_path = RUN / "preview" / "ld-frames.json"
    old = json.loads(rec_path.read_text(encoding="utf-8"))["frames"] if (ONLY and rec_path.exists()) else {}
    old.update(frames)
    C.write_json(rec_path, {"label": LD["review"]["label"], "baseline_frames": LD["review"]["baseline_frames"],
                            "calibration": {k: CAL.get(k) for k in ("exposure_offset_stops", "blender_exposure", "k1_board_p50_final")},
                            "team_palette": TEAM_HEX, "frames": old})
    print(C.STAGE_MARKER, "ld_review", len(frames), flush=True)


main()
