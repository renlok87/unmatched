"""M_UM_Figure_v2 control frames (host side of ue_v2.py `scene`): class spheres on the Cobble light of the P1.7 level.

LIVE editor (the same flow as tools/tripo-pipeline/review/h2_ue_review.py): refuses when the open level is dirty,
loads /Game/ArtTests/P17ControlScene/L_P17ControlScene, applies the Cobble light profile in memory (fill off, key CSM,
Movable SkyLight from the profile cubemap), High scalability through console variables, spawns
  - a 4 x 4 wall of spheres (engine sphere x 0.2 = 20 uu), class i at column i % 4, row i // 4 (class 0 top left),
    MI_UM_v2_Test_ClassNN (DebugMatIDOverride = i, bake = class typical colour, edge ramp along U);
  - the MatID checker spheres (real MatID Load + test bake; debug class colours; the UV1 static-switch variant);
  - a scratch frame-probe sphere (ue/um_v2_scene_ue.py, unsaved material): derivative tangent frame vs the engine
    Transform(Local -> Tangent);
captures editor frames (EditorAppToolset.CaptureViewport; diagnostics, not K1/K2 acceptance, no RENDER fingerprint),
swaps the wall to the _Red MIs (TeamColor red, TeamDye 1) for the dye test, takes a G-buffer overview, measures every
sphere in the frames (projection of the known centres), restores everything and reloads the previous level.
"""
from __future__ import annotations

import base64
import hashlib
import io
import json
import math
import time
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
REVIEW_PY = REPO / "tools" / "tripo-pipeline" / "review" / "ue_py"
LEVEL = "/Game/ArtTests/P17ControlScene/L_P17ControlScene"
PROFILES_JSON = REPO / "unreal/Unmatched/Config/ArtBoards/S08ArtBoardProfiles.json"
KEY_LABEL = "ART005 cool scene key - proposed"
FILL_LABEL = "ART005 neutral readability fill - review only"
EXPOSURE_LABEL = "P17 exposure EV100 1.3 - fixed"
KEY_ROTATION = [-55.0, 30.0, 0.0]  # editor-probe rotation, as h2_ue_review.py (KEY_ROTATION_NOTE there)
PREFIX = "LDv2 "
L_SKY, L_CAM, L_PROBE = PREFIX + "sky - temporary", PREFIX + "camera - temporary", PREFIX + "frame probe"
L_FIG = PREFIX + "Merlin H2 - temporary"
SG = ("sg.ViewDistanceQuality", "sg.AntiAliasingQuality", "sg.ShadowQuality", "sg.GlobalIlluminationQuality",
      "sg.ReflectionQuality", "sg.PostProcessQuality", "sg.TextureQuality", "sg.EffectsQuality", "sg.FoliageQuality",
      "sg.ShadingQuality")
SHOW_FLAGS_OFF = ("Grid", "BillboardSprites", "Volumes")
NOANN = {"gridSpacing": 0, "gridExtent": 0, "gridHeight": 0, "maxLabelDistance": 0, "classFilter": None, "maxLabels": 0}
TESTS = "/Game/UM/Materials/v2/Test"
WALL_Y, WALL_TOP, STEP, SCALE = 50.0, 90.0, 26.0, 0.2
CHECK_Y, CHECK_Z = -100.0, 20.0
FOV = 35.0
F_PX = 960.0 / math.tan(math.radians(FOV / 2))  # focal length in px of the 1920-wide output frame
DYE_CLASSES = {7, 8, 9, 10, 11, 12}          # teamDyeAllowed in the presets (+ class 0 legacy: TeamMask as v1)


def wall_pos(i):
    return [(i % 4 - 1.5) * STEP, WALL_Y, WALL_TOP - (i // 4) * STEP]


CHECKERS = {"checker": ([-30.0, CHECK_Y, CHECK_Z], TESTS + "/MI_UM_v2_Test_Checker"),
            "checker-debug": ([0.0, CHECK_Y, CHECK_Z], TESTS + "/MI_UM_v2_Test_Checker_Debug"),
            "checker-uv1": ([30.0, CHECK_Y, CHECK_Z], TESTS + "/MI_UM_v2_Test_Checker_UV1")}
PROBE_POS = [70.0, CHECK_Y, CHECK_Z]


def views():
    wall_c = [0.0, WALL_Y, WALL_TOP - 1.5 * STEP]
    p = math.radians(35.0)
    return {
        "wall-front": {"eye": [0.0, WALL_Y + 330.0, wall_c[2]], "rot": [0.0, -90.0, 0.0]},
        "wall-top35": {"eye": [0.0, WALL_Y + 330.0 * math.cos(p), wall_c[2] + 330.0 * math.sin(p)],
                       "rot": [-35.0, -90.0, 0.0]},
        "wall-rows01": {"eye": [0.0, WALL_Y + 175.0, WALL_TOP - 0.5 * STEP], "rot": [0.0, -90.0, 0.0]},
        "wall-rows23": {"eye": [0.0, WALL_Y + 175.0, WALL_TOP - 2.5 * STEP], "rot": [0.0, -90.0, 0.0]},
        "checkers": {"eye": [0.0, CHECK_Y + 160.0, CHECK_Z], "rot": [0.0, -90.0, 0.0]},
        "checker-close": {"eye": [-30.0, CHECK_Y + 55.0, CHECK_Z], "rot": [0.0, -90.0, 0.0]},
        "probe": {"eye": [PROBE_POS[0], CHECK_Y + 55.0, CHECK_Z], "rot": [0.0, -90.0, 0.0]},
    }


def project(eye, point):
    """Screen position (1920x1080 output) of a world point for a camera looking along -Y (rot yaw -90, pitch 0)."""
    d = eye[1] - point[1]
    return 960.0 + (point[0] - eye[0]) / d * F_PX, 540.0 - (point[2] - eye[2]) / d * F_PX


def cvar_value(ue, name):
    raw = ue.call("app", "SearchCVars", {"name": name}, record=False)
    data = json.loads(raw) if isinstance(raw, str) else raw
    return (data.get(name) or {}).get("value")


def font(size):
    for f in ("C:/Windows/Fonts/segoeui.ttf", "C:/Windows/Fonts/arial.ttf"):
        try:
            return ImageFont.truetype(f, size)
        except OSError:
            continue
    return ImageFont.load_default()


class Shots:
    def __init__(self, ue, out: Path, run):
        self.ue, self.out, self.run = ue, out, run
        self.frames = {}

    def grab(self, xform):
        res = self.ue.call("app", "CaptureViewport", {"captureTransform": xform, "annotations": NOANN, "bShowUI": False},
                           record=False)
        v = res["value"] if isinstance(res, dict) and "value" in res else res
        img = v["image"] if isinstance(v, dict) and "image" in v else res["images"][0]
        return Image.open(io.BytesIO(base64.b64decode(img["data"]))).convert("RGB")

    def shot(self, name, view, meta):
        self.run("control_scene_ue.py", "camera", label=L_CAM, location=view["eye"], rotation=view["rot"], fov=FOV)
        xform = {"location": dict(zip("xyz", view["eye"])), "rotation": dict(zip(("pitch", "yaw", "roll"), view["rot"])),
                 "scale": {"x": 1, "y": 1, "z": 1}}
        time.sleep(0.5)
        prev, settle = None, []
        for attempt in range(4):
            im = self.grab(xform)
            if prev is not None:
                settle.append(round(float(np.abs(np.asarray(im, np.int16) - np.asarray(prev, np.int16)).mean()), 4))
            prev = im
            if attempt < 3:
                time.sleep(0.7)
        w, h = im.size
        ch = round(w * 9 / 16)
        box = (0, (h - ch) // 2, w, (h - ch) // 2 + ch) if ch <= h else ((w - round(h * 16 / 9)) // 2, 0,
                                                                          (w + round(h * 16 / 9)) // 2, h)
        frame = im.crop(box).resize((1920, 1080), Image.LANCZOS)
        fname = "um-v2-%s.jpg" % name
        path = self.out / fname
        frame.save(path, quality=92, optimize=True)
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        info = {"view": view, "viewport_px": [w, h], "crop_px": list(box), "output_px": [1920, 1080],
                "settle_mean_abs_diff": settle, "fov": FOV, **meta}
        side = {"schema": "unmatched.evidence-frame/1", "class": "editor-mcp-viewport", "frameSha256": digest,
                "frame": fname, "label": "EDITOR frame (LD-master M_UM_Figure_v2 control spheres, Cobble light, High), "
                                         "diagnostic; not K1/K2 acceptance, no RENDER fingerprint", **info}
        path.with_name(path.stem + ".evidence.json").write_text(json.dumps(side, indent=1, sort_keys=True) + "\n",
                                                              encoding="utf-8", newline="\n")
        self.frames[name] = dict(info, file=fname, sha256=digest, image=frame)
        print(" ", fname, digest[:12], "settle", settle, flush=True)
        return frame


def sphere_samples(frame: Image.Image, eye, centre, radius_uu=10.0):
    """Mean sRGB of the sphere disc (r < 0.8 R) and of its lit upper-left quarter, projected from the known centre."""
    a = np.asarray(frame, np.float64)
    cx, cy = project(eye, centre)
    r_px = radius_uu / (eye[1] - centre[1]) * F_PX
    ys, xs = np.mgrid[0:a.shape[0], 0:a.shape[1]]
    d2 = ((xs - cx) ** 2 + (ys - cy) ** 2) / max(r_px, 1.0) ** 2
    disc = d2 < 0.64
    quarter = disc & (xs < cx) & (ys < cy)
    res = {"centre_px": [round(cx, 1), round(cy, 1)], "radius_px": round(r_px, 1), "disc_px": int(disc.sum())}
    for key, m in (("disc", disc), ("upper_left", quarter)):
        if m.any():
            rgb = a[m].mean(0)
            res[key + "_srgb"] = [round(float(v), 1) for v in rgb]
            res[key + "_luma"] = round(float(np.dot(rgb, [0.2126, 0.7152, 0.0722])), 1)
            res[key + "_p98_luma"] = round(float(np.percentile(a[m] @ np.array([0.2126, 0.7152, 0.0722]), 98)), 1)
    return res


def hue_sat(rgb):
    import colorsys
    h, s, v = colorsys.rgb_to_hsv(*[c / 255.0 for c in rgb])
    return round(h * 360.0, 1), round(s, 3), round(v, 3)


def annotate(frame, eye, names, positions):
    im = frame.copy()
    d = ImageDraw.Draw(im)
    for n, p in zip(names, positions):
        x, y = project(eye, p)
        r = 10.0 / (eye[1] - p[1]) * F_PX
        d.text((x - r, y + r * 1.02), n, fill=(255, 235, 150), font=font(max(16, int(r / 4))))
    return im


def cmd_scene(ue, out: Path, a, task) -> dict:
    presets = json.loads((REPO / "docs/art-pipeline/material-library/um-material-presets-v1.json")
                         .read_text(encoding="utf-8"))
    class_ids = [c["id"] for c in presets["classes"]]
    light = json.loads(PROFILES_JSON.read_text(encoding="utf-8"))["lightProfiles"]["cobble-probe"]

    def run(script, op, timeout=600, **kw):
        path = REVIEW_PY / script if script == "control_scene_ue.py" else HERE / "ue" / script
        return ue.run_task(str(path), str(out / "_task.json"), timeout=timeout, op=op, **kw)

    shots = Shots(ue, out, run)
    report = {"level": LEVEL, "light_profile": light, "key_rotation_pitch_yaw_roll": KEY_ROTATION, "console": [],
              "classes": class_ids, "layout": {"wall": "class i at column i %% 4, row i // 4; centres %s" %
                                                       [wall_pos(i) for i in range(16)],
                                               "checkers": {k: v[0] for k, v in CHECKERS.items()},
                                               "probe": PROBE_POS, "sphere_diameter_uu": 100 * SCALE}}
    original = ue.call("scene", "get_current_level", record=False)
    if ue.call("asset", "is_dirty", {"asset_path": original}, record=False):
        raise SystemExit("open level %s has unsaved changes; refusing to switch levels" % original)
    if original.split(".")[0] == LEVEL:
        raise SystemExit("the review level itself is open; open another level first")
    if ue.call("asset", "is_dirty", {"asset_path": LEVEL}, record=False):
        raise SystemExit("the review level has unsaved changes in memory (someone else is using it)")
    report["original_level"] = original
    sg_before = {n: cvar_value(ue, n) for n in SG}
    report["scalability_before"] = sg_before
    wall_labels = [PREFIX + "class %02d %s" % (i, class_ids[i]) for i in range(16)]
    check_labels = [PREFIX + k for k in CHECKERS]
    temp = wall_labels + check_labels + [L_PROBE, L_FIG, L_SKY, L_CAM]
    spheres = [{"label": wall_labels[i], "location": wall_pos(i), "scale": SCALE,
                "material": "%s/MI_UM_v2_Test_Class%02d" % (TESTS, i)} for i in range(16)]
    spheres += [{"label": PREFIX + k, "location": v[0], "scale": SCALE, "material": v[1]} for k, v in CHECKERS.items()]
    try:
        ue.call("scene", "load_level", {"level_path": LEVEL})
        time.sleep(3.0)
        report["setup"] = run("um_v2_scene_ue.py", "setup", level=LEVEL, hide_label_prefixes=["P17 "],
                              keep_labels=[EXPOSURE_LABEL],
                              lights={"off": [FILL_LABEL],
                                      "key": {"label": KEY_LABEL, "intensity_lux": light["directional"]["intensity"],
                                              "shadow_distance_uu": light["directional"]["shadow"]["distanceUU"],
                                              "cascades": light["directional"]["shadow"]["cascades"],
                                              "contact_shadow_length": light["directional"]["shadow"]["contactShadowLength"],
                                              "rotation_pitch_yaw_roll": KEY_ROTATION}},
                              sky={"label": L_SKY, "cubemap": light["sky"]["cubemap"], "intensity": light["sky"]["intensity"],
                                   "lower_hemisphere_is_black": light["sky"]["lowerHemisphereIsBlack"],
                                   "color_linear": light["sky"]["colorLinear"]},
                              spheres=spheres,
                              probe={"label": L_PROBE, "location": PROBE_POS, "scale": SCALE, "local_unit_m": 0.002})
        for n in SG:
            ue.console("%s 2" % n)
            report["console"].append("%s 2" % n)
        for flag in SHOW_FLAGS_OFF:
            ue.console("ShowFlag.%s 0" % flag)
            report["console"].append("ShowFlag.%s 0" % flag)
        report["scalability_during"] = {n: cvar_value(ue, n) for n in SG}
        report["render_cvars"] = {n: cvar_value(ue, n) for n in ("r.ScreenPercentage", "r.AntiAliasingMethod",
                                                                    "r.DynamicGlobalIlluminationMethod",
                                                                    "r.ReflectionMethod", "r.Substrate")}
        time.sleep(8.0)
        vs = views()
        # warm-up (shader compile of the new MIs, streaming): until two consecutive captures agree
        v0 = vs["wall-front"]
        run("control_scene_ue.py", "camera", label=L_CAM, location=v0["eye"], rotation=v0["rot"], fov=FOV)
        xf = {"location": dict(zip("xyz", v0["eye"])), "rotation": dict(zip(("pitch", "yaw", "roll"), v0["rot"])),
              "scale": {"x": 1, "y": 1, "z": 1}}
        prev, warm = None, []
        for _ in range(40):
            im = shots.grab(xf)
            if prev is not None:
                warm.append(round(float(np.abs(np.asarray(im, np.int16) - np.asarray(prev, np.int16)).mean()), 4))
                if warm[-1] < 0.05 and len(warm) >= 3:
                    break
            prev = im
            time.sleep(2.0)
        report["warmup_mean_abs_diff"] = warm
        for name in ("wall-front", "wall-top35", "wall-rows01", "wall-rows23", "checkers", "checker-close", "probe"):
            shots.shot(name, vs[name], {"subject": "M_UM_Figure_v2 control spheres", "team": "none (TeamColor white)"})
        # dye test: the same wall with TeamColor red, TeamDye 1 (TeamMask white = every pixel inside the mask)
        run("control_scene_ue.py", "set", changes=[{"label": wall_labels[i], "materials": {
            "0": "%s/MI_UM_v2_Test_Class%02d_Red" % (TESTS, i)}} for i in range(16)])
        time.sleep(3.0)
        for _ in range(20):
            im = shots.grab(xf)
            if prev is not None and float(np.abs(np.asarray(im, np.int16) - np.asarray(prev, np.int16)).mean()) < 0.05:
                break
            prev = im
            time.sleep(2.0)
        shots.shot("wall-front-red", vs["wall-front"], {"subject": "M_UM_Figure_v2 control spheres",
                                                        "team": "TeamColor linear (0.8, 0.02, 0.02), TeamDye 1"})
        run("control_scene_ue.py", "set", changes=[{"label": wall_labels[i], "materials": {
            "0": "%s/MI_UM_v2_Test_Class%02d" % (TESTS, i)}} for i in range(16)])
        # G-buffer overview (base colour / metallic / roughness / shading model tiles)
        ue.console("ShowFlag.VisualizeBuffer 1")
        report["console"].append("ShowFlag.VisualizeBuffer 1")
        time.sleep(2.0)
        shots.shot("wall-front-buffers", vs["wall-front"], {"subject": "G-buffer overview (ShowFlag.VisualizeBuffer 1)"})
        ue.console("ShowFlag.VisualizeBuffer 0")
        report["console"].append("ShowFlag.VisualizeBuffer 0")
        # exposure -1.5 EV (the Cobble exposure clips albedo > ~0.3 and bright metals): the same views, reading only
        report["exposure_lowered"] = run("um_v2_scene_ue.py", "exposure", label=EXPOSURE_LABEL, bias=-1.5)
        time.sleep(3.0)
        for name in ("wall-front", "wall-rows01", "wall-rows23", "checker-close"):
            shots.shot(name + "-ev-1p5", vs[name], {"subject": "M_UM_Figure_v2 control spheres",
                                                    "exposure": "EV100 1.3 fixed + bias -1.5 (reading frame)"})
        report["exposure_restored"] = run("um_v2_scene_ue.py", "exposure", label=EXPOSURE_LABEL, bias=0.0)
        # regression: Merlin H2 with its v1 red MI vs the same values on the v2 master (MatID legacy = v1 path)
        run("control_scene_ue.py", "set", changes=[{"label": lab, "visible": False}
                                                   for lab in wall_labels + check_labels + [L_PROBE]])
        fig_mis = {"v1": "/Game/PipelineCandidates/Merlin/H2/Materials/MI_Merlin_H2_Red",
                   "v2": TESTS + "/MI_UM_v2_Test_LegacyMerlin_Red"}
        report["figure"] = run("um_v2_scene_ue.py", "figure", label=L_FIG, asset="/Game/PipelineCandidates/Merlin/H2/Meshes/SK_Merlin_H2",
                               location=[0.0, WALL_Y, 0.0], yaw=90.0, material=fig_mis["v1"])
        fview = {"eye": [0.0, WALL_Y + 200.0, 31.0], "rot": [0.0, -90.0, 0.0]}
        time.sleep(15.0)  # Lumen GI / shadows settle after the spheres were hidden (r2: the rail drifted in v1a)
        reg = {}
        for tag in ("v1a", "v2a", "v1b", "v2b"):
            run("control_scene_ue.py", "set", changes=[{"label": L_FIG, "materials": {"0": fig_mis[tag[:2]]}}])
            time.sleep(4.0)
            reg[tag] = np.asarray(shots.shot("merlin-legacy-" + tag, fview, {"subject": "Merlin H2 red, " + fig_mis[tag[:2]]}),
                                  np.int16)
        roi = (slice(80, 1040), slice(660, 1260))

        def mad(x, y):
            return round(float(np.abs(reg[x][roi] - reg[y][roi]).mean()), 4)

        report["regression_legacy"] = {
            "roi_px": "x 660-1260, y 80-1040 (the figure)", "v1a_v1b_noise": mad("v1a", "v1b"),
            "v2a_v2b_noise": mad("v2a", "v2b"), "v1a_v2a": mad("v1a", "v2a"), "v1b_v2b": mad("v1b", "v2b"),
            "v1_mean_v2_mean_abs": round(float(np.abs((reg["v1a"][roi] + reg["v1b"][roi]) / 2.0 -
                                                      (reg["v2a"][roi] + reg["v2b"][roi]) / 2.0).mean()), 4),
            "rule": "v2 with MatID legacy must equal v1 within the frame-to-frame noise"}
        # the same in the G-buffer overview (no lighting noise): tile by tile (4 x 4 tiles of 480 x 270)
        ue.console("ShowFlag.VisualizeBuffer 1")
        report["console"].append("ShowFlag.VisualizeBuffer 1")
        time.sleep(2.0)
        buf = {}
        for tag in ("v1a", "v2a", "v1b", "v2b"):
            run("control_scene_ue.py", "set", changes=[{"label": L_FIG, "materials": {"0": fig_mis[tag[:2]]}}])
            time.sleep(4.0)
            buf[tag] = np.asarray(shots.shot("merlin-legacy-buffers-" + tag, fview,
                                             {"subject": "Merlin H2 red G-buffer overview, " + fig_mis[tag[:2]]}), np.int16)
        ue.console("ShowFlag.VisualizeBuffer 0")
        report["console"].append("ShowFlag.VisualizeBuffer 0")
        tiles = {}
        for (r_, c_), tname in {(0, 0): "base_colour", (0, 1): "specular", (0, 2): "subsurface_colour",
                                (0, 3): "world_normal", (3, 0): "ao_or_custom", (3, 1): "roughness", (3, 2): "metallic",
                                (3, 3): "shading_model"}.items():
            sl = (slice(r_ * 270 + 30, r_ * 270 + 240), slice(c_ * 480 + 10, c_ * 480 + 470))

            def tmad(x, y, sl=sl):
                return round(float(np.abs(buf[x][sl] - buf[y][sl]).mean()), 4)

            tiles[tname] = {"v1a_v1b": tmad("v1a", "v1b"), "v2a_v2b": tmad("v2a", "v2b"), "v1a_v2a": tmad("v1a", "v2a"),
                            "v1b_v2b": tmad("v1b", "v2b"),
                            "max_abs_v1a_v2a": int(np.abs(buf["v1a"][sl] - buf["v2a"][sl]).max())}
        report["regression_legacy_buffers"] = tiles
        # ---- measurements
        meas = {"wall": {}, "wall_red": {}, "dye_check": {}, "probe": None}
        fv, fr = shots.frames["wall-front"], shots.frames["wall-front-red"]
        for i in range(16):
            s0 = sphere_samples(fv["image"], vs["wall-front"]["eye"], wall_pos(i))
            s1 = sphere_samples(fr["image"], vs["wall-front"]["eye"], wall_pos(i))
            meas["wall"][class_ids[i]] = s0
            meas["wall_red"][class_ids[i]] = s1
            h0, sat0, _ = hue_sat(s0["disc_srgb"])
            h1, sat1, _ = hue_sat(s1["disc_srgb"])
            diff = float(np.abs(np.array(s0["disc_srgb"]) - np.array(s1["disc_srgb"])).max())
            changed = diff > 6.0
            expected = i in DYE_CLASSES or i == 0
            meas["dye_check"][class_ids[i]] = {"max_channel_diff": round(diff, 1), "changed": changed,
                                               "expected_changed": expected, "ok": changed == expected,
                                               "hue_sat_before": [h0, sat0], "hue_sat_red": [h1, sat1]}
        pv = shots.frames["probe"]
        arr = np.asarray(pv["image"], np.float64)
        cx, cy = project(vs["probe"]["eye"], PROBE_POS)
        r_px = 10.0 / (vs["probe"]["eye"][1] - PROBE_POS[1]) * F_PX
        ys, xs = np.mgrid[0:arr.shape[0], 0:arr.shape[1]]
        disc = ((xs - cx) ** 2 + (ys - cy) ** 2) < (0.8 * r_px) ** 2
        meas["probe"] = {"mean_srgb_R_error_plus_gradv": round(float(arr[disc][:, 0].mean()), 1),
                         "mean_srgb_G_error_minus_gradv": round(float(arr[disc][:, 1].mean()), 1),
                         "p95_R": round(float(np.percentile(arr[disc][:, 0], 95)), 1),
                         "p95_G": round(float(np.percentile(arr[disc][:, 1], 95)), 1),
                         "meaning": "emissive = 0.5 x |my tangent-space vector - engine Transform(Local->Tangent)|, "
                                    "EyeAdaptationInverse: R with tangent Y = +grad v, G with Y = -grad v; the right "
                                    "convention reads near 0 (sRGB after the tonemapper)"}
        report["measurements"] = meas
        report["dye_ok"] = all(v["ok"] for v in meas["dye_check"].values())
        # annotated wall frames + sheet
        names = ["%d %s" % (i, class_ids[i]) for i in range(16)]
        pos = [wall_pos(i) for i in range(16)]
        sheet = Image.new("RGB", (1920 * 2, 1080 + 60), (12, 12, 12))
        d = ImageDraw.Draw(sheet)
        d.text((12, 12), "M_UM_Figure_v2 · 16 классов (DebugMatIDOverride, бейк = типичный цвет класса) · слева белая команда, "
                         "справа TeamColor красный (краситель только ткань/кожа/перья + legacy) · редактор, DX12/SM6 + "
                         "Lumen, High, свет Cobble · диагностика, не приёмка", fill=(235, 210, 120), font=font(26))
        sheet.paste(annotate(fv["image"], vs["wall-front"]["eye"], names, pos), (0, 60))
        sheet.paste(annotate(fr["image"], vs["wall-front"]["eye"], names, pos), (1920, 60))
        sp = out / "um-v2-sheet-wall.jpg"
        sheet.save(sp, quality=88, optimize=True)
        report["sheet"] = {"file": sp.name, "sha256": hashlib.sha256(sp.read_bytes()).hexdigest()}
    finally:
        try:
            report["cleanup"] = run("control_scene_ue.py", "cleanup", labels=temp)
        except Exception as exc:  # noqa: BLE001
            report["cleanup_error"] = str(exc)
        try:
            for n, v in sg_before.items():
                if v is not None:
                    ue.console("%s %s" % (n, v))
                    report["console"].append("%s %s" % (n, v))
            for flag in SHOW_FLAGS_OFF + ("VisualizeBuffer",):
                ue.console("ShowFlag.%s 2" % flag)
                report["console"].append("ShowFlag.%s 2" % flag)
            report["scalability_after"] = {n: cvar_value(ue, n) for n in SG}
        except Exception as exc:  # noqa: BLE001
            report["console_error"] = str(exc)
        ue.call("scene", "load_level", {"level_path": original.split(".")[0]})
        time.sleep(2.0)
        try:
            report["drop_probe"] = run("um_v2_scene_ue.py", "drop_probe")
        except Exception as exc:  # noqa: BLE001
            report["drop_probe_error"] = str(exc)
        report["restored_level"] = ue.call("scene", "get_current_level", record=False)
        report["restored_level_dirty"] = ue.call("asset", "is_dirty", {"asset_path": report["restored_level"]},
                                                 record=False)
        report["review_level_dirty_after_reload"] = ue.call("asset", "is_dirty", {"asset_path": LEVEL}, record=False)
        report["frames"] = {k: {kk: vv for kk, vv in v.items() if kk != "image"} for k, v in shots.frames.items()}
    return report
