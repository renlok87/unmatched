"""W5c-A: editor review frames of an imported H2 hero (skeletal-adopt run) on the Cobble light of the render reference.

    python tools/tripo-pipeline/review/h2_ue_review.py --run-dir <skeletal-adopt run> --out <evidence dir>
        [--blender-frames <bake>/preview/frames] [--tag r1]

LIVE UnrealEditor (MCP 127.0.0.1:8123 + the editor console, review/ue_live.py). Nothing is saved:
  1. refuses when the open level has unsaved changes or is the review level itself; records the editor scalability;
  2. loads the P1.7 Cobble control level (/Game/ArtTests/P17ControlScene/L_P17ControlScene: the Cobble board of
     L_ART005H_CornerReview, the key/warm lights of the Cobble probe, the fixed-exposure volume EV100 1.3), hides its
     review figures and applies the Cobble light profile of the packaged client in memory
     (unreal/Unmatched/Config/ArtBoards/S08ArtBoardProfiles.json lightProfiles.cobble-probe, W4-A): the pre-W4 point
     fill off, a Movable SkyLight from the profile cubemap (intensity 11.2), the key CSM of the profile (3000 uu, 2
     cascades); the key keeps the editor-probe rotation (pitch -55, yaw 30), see KEY_ROTATION_NOTE;
  3. sets the editor scalability to High (sg.* = 2, the acceptance reference) through console variables, hides the
     editor overlays (grid, sprites, volume wireframes), spawns the H2 figure + base of the run on the Arthur cell of
     the control level and measures it (ref-pose bones/sockets, facing, materials, textures);
  4. captures EDITOR frames (EditorAppToolset.CaptureViewport, piloted CameraActor): front / left / back (FOV 35 at
     200 uu; the viewport ignores a narrower camera FOV, see NARROW), a torso close-up, and the game camera K2 (FOV 35, pitch -55, 5x = 386 uu and 1.6x = 1207 uu)
     facing the camera and from behind; each with the default team MI (Blue) and the Red team MI;
  5. restores the scalability and overlays, destroys the temporary actors and re-opens the previous level (the
     in-memory light changes of the control level are discarded).
Frames are EDITOR frames (class editor-mcp-viewport): diagnostics, not K1/K2 acceptance and not packaged frames (no
RENDER fingerprint). Sheets put the Blender H2.1 frames of the bake (same model, EEVEE, three suns) next to them.
"""

import argparse
import base64
import datetime as dt
import hashlib
import io
import json
import math
import sys
import time
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
sys.path.insert(0, str(HERE))
from ue_live import Ue  # noqa: E402

SCHEMA = "unmatched.h2-ue-review/1"
SIDECAR_SCHEMA = "unmatched.evidence-frame/1"
LEVEL = "/Game/ArtTests/P17ControlScene/L_P17ControlScene"
PROFILES_JSON = REPO / "unreal/Unmatched/Config/ArtBoards/S08ArtBoardProfiles.json"
LIGHT_PROFILE = "cobble-probe"
KEY_LABEL = "ART005 cool scene key - proposed"
FILL_LABEL = "ART005 neutral readability fill - review only"
WARM_LABEL = "ART005 warm lantern accent - proposed"
EXPOSURE_LABEL = "P17 exposure EV100 1.3 - fixed"
KEY_ROTATION = [-55.0, 30.0, 0.0]  # pitch, yaw, roll of the editor probe (L_ART005H_CornerReview, P1.7 control level)
KEY_ROTATION_NOTE = ("S08ArtBoardProfiles.json writes the key as \"rotation\": [0, -55, 30] and S08BoardArt.cpp builds "
                     "FRotator(N[0], N[1], N[2]) = (Pitch 0, Yaw -55, Roll 30): a horizontal key in the packaged client, "
                     "while the editor probe the profile reproduces has Pitch -55, Yaw 30 (control level). These frames "
                     "use the editor-probe rotation; the packaged interpretation is reported, not fixed here")
PREFIX = "W5cA H2 "
L_FIG, L_BASE, L_SKY = PREFIX + "figure - temporary", PREFIX + "base - temporary", PREFIX + "sky - temporary"
# ONE piloted camera for every view: a second CameraActor stays in the level where it was left and its editor mesh
# shows up in the other views (r2: the torso camera at 85 uu filled the red front frame and framed the red back frame)
L_CAM_NARROW = L_CAM_K2 = PREFIX + "camera FOV35 - temporary"
CELL = [0.0, 50.0, 0.0]  # Arthur's cell 2:3 of the control level (P1.7 scene spec)
FOV_K2, PITCH_K2, YAW_K2 = 35.0, -55.0, -90.0
K2_5X, K2_1P6, FOCUS_Z = 386.0, 1207.0, 28.0
# Every view uses FOV 35: the level viewport renders at a horizontal FOV of about 35 deg whatever FOV the piloted
# CameraActor has (measured 2026-09-29 on the control level, top-down from 1500 uu: cameras of FOV 8 and 35 gave the
# same frame, 100 uu cells = 214 px of 2033 -> 35.1 deg; CaptureViewport only reports the camera's FOV). So the
# "near-orthographic" views are perspective FOV 35 at 200 uu (figure ~62 uu tall fills ~88 % of the 16:9 height).
NARROW = {"fov": 35.0, "distance": 200.0, "z": 31.0}
TORSO = {"fov": 35.0, "distance": 85.0, "z": 42.0}
SG = ("sg.ViewDistanceQuality", "sg.AntiAliasingQuality", "sg.ShadowQuality", "sg.GlobalIlluminationQuality",
      "sg.ReflectionQuality", "sg.PostProcessQuality", "sg.TextureQuality", "sg.EffectsQuality", "sg.FoliageQuality",
      "sg.ShadingQuality")
SHOW_FLAGS_OFF = ("Grid", "BillboardSprites", "Volumes")
# the level viewport ignores r.BufferVisualizationTarget: ShowFlag.VisualizeBuffer 1 draws the buffer OVERVIEW (base colour,
# specular, world normal, AO, roughness, metallic, shading model tiles) whatever the target (measured W5c-A r3: three
# targets gave the same frame up to TSR/Lumen noise), so one overview frame per view is taken
BUFFERS = ("overview",)
NOANN = {"gridSpacing": 0, "gridExtent": 0, "gridHeight": 0, "maxLabelDistance": 0, "classFilter": None, "maxLabels": 0}
BONES = ["root", "hips", "spine", "head", "arm_upper_L", "arm_upper_R", "leg_upper_L", "leg_upper_R", "hand_R",
         "weapon_R", "foot_L", "foot_R"]
SOCKETS = ["Weapon", "Head"]
# Blender H2.1 frames of the bake for the sheets (preview/frames, regenerated on the H2.1 textures)
BLENDER_PAIRS = {"front": "ortho_front.jpg", "left": "ortho_left.jpg", "back": "ortho_back.jpg",
                 "torso": "close_torso_az0.jpg", "k2-5x-az0": "game_K2S05_az0.jpg",
                 "k2-5x-az180": "game_K2S05_az180.jpg", "k2-1p6-az0": "game_K2_az0.jpg"}


def views():
    """name -> camera (location, rotation [pitch, yaw, roll]), camera label, FOV, figure yaw. The figure faces +Y (the
    board camera) at yaw 90 (a UM_FBX_v1 mesh faces +X); its left side is then +X."""
    x, y = CELL[0], CELL[1]
    n, t = NARROW, TORSO
    p = math.radians(-PITCH_K2)
    fz = CELL[2] + FOCUS_Z

    def k2(dist):
        return [x, y + dist * math.cos(p), fz + dist * math.sin(p)], [PITCH_K2, YAW_K2, 0.0]

    return {
        "front": {"eye": [x, y + n["distance"], n["z"]], "rot": [0.0, -90.0, 0.0], "cam": L_CAM_NARROW, "fov": n["fov"],
                  "yaw": 90.0, "kind": "front, FOV 35, 200 uu"},
        "left": {"eye": [x + n["distance"], y, n["z"]], "rot": [0.0, 180.0, 0.0], "cam": L_CAM_NARROW, "fov": n["fov"],
                 "yaw": 90.0, "kind": "left side, FOV 35, 200 uu"},
        "back": {"eye": [x, y - n["distance"], n["z"]], "rot": [0.0, 90.0, 0.0], "cam": L_CAM_NARROW, "fov": n["fov"],
                 "yaw": 90.0, "kind": "back, FOV 35, 200 uu"},
        "torso": {"eye": [x, y + t["distance"], t["z"]], "rot": [0.0, -90.0, 0.0], "cam": L_CAM_NARROW,
                  "fov": t["fov"], "yaw": 90.0, "kind": "torso close-up, FOV 35, 85 uu"},
        "k2-5x-az0": dict(zip(("eye", "rot"), k2(K2_5X)), cam=L_CAM_K2, fov=FOV_K2, yaw=90.0, kind="game K2 5x"),
        "k2-5x-az180": dict(zip(("eye", "rot"), k2(K2_5X)), cam=L_CAM_K2, fov=FOV_K2, yaw=-90.0, kind="game K2 5x"),
        "k2-1p6-az0": dict(zip(("eye", "rot"), k2(K2_1P6)), cam=L_CAM_K2, fov=FOV_K2, yaw=90.0, kind="game K2 1.6x"),
    }


def cvar_value(ue, name):
    raw = ue.call("app", "SearchCVars", {"name": name}, record=False)
    data = json.loads(raw) if isinstance(raw, str) else raw
    return (data.get(name) or {}).get("value")


class Review:
    def __init__(self, ue, out: Path, tag: str):
        self.ue, self.out, self.tag = ue, out, tag
        self.frames = {}

    def task(self, script, op, timeout=600, **kw):
        return self.ue.run_task(str(HERE / "ue_py" / script), str(self.out / "_task.json"), timeout=timeout, op=op, **kw)

    def grab(self, xform):
        res = self.ue.call("app", "CaptureViewport", {"captureTransform": xform, "annotations": NOANN, "bShowUI": False},
                           record=False)
        v = res["value"] if isinstance(res, dict) and "value" in res else res
        img = v["image"] if isinstance(v, dict) and "image" in v else res["images"][0]
        return Image.open(io.BytesIO(base64.b64decode(img["data"]))).convert("RGB")

    def shot(self, name, view, meta):
        cam = self.task("control_scene_ue.py", "camera", label=view["cam"], location=view["eye"], rotation=view["rot"],
                        fov=view["fov"])["camera"]
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
        fname = "arthur-h2-%s-ue-editor.jpg" % name
        path = self.out / fname
        frame.save(path, quality=90, optimize=True)
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        info = {"camera": cam, "view": {k: view[k] for k in ("eye", "rot", "fov", "yaw", "kind")},
                "viewport_px": [w, h], "crop_px": list(box), "output_px": [1920, 1080],
                "settle_mean_abs_diff": settle, "jpeg_quality": 90,
                "capture": "EditorAppToolset.CaptureViewport via MCP 127.0.0.1:8123 (piloted CameraActor, horizontal "
                           "FOV %.1f, centred 16:9 crop resized to 1920x1080)" % view["fov"], **meta}
        side = {"schema": SIDECAR_SCHEMA, "class": "editor-mcp-viewport", "frameSha256": digest, "frame": fname,
                "label": "EDITOR frame (W5c-A H2 review, Cobble light), diagnostic; not K1/K2 acceptance, no RENDER "
                         "fingerprint", "run_tag": self.tag, **info}
        path.with_name(path.stem + ".evidence.json").write_text(json.dumps(side, indent=1, sort_keys=True) + "\n",
                                                              encoding="utf-8", newline="\n")
        self.frames[fname] = dict(info, sha256=digest, image=frame)
        print(" ", fname, digest[:12], "settle", settle, flush=True)
        return fname


def font(size):
    for f in ("C:/Windows/Fonts/segoeui.ttf", "C:/Windows/Fonts/arial.ttf"):
        try:
            return ImageFont.truetype(f, size)
        except OSError:
            continue
    return ImageFont.load_default()


def fit(im, w, h, portrait_crop=False):
    if portrait_crop:  # centre crop to the aspect of the target cell
        iw, ih = im.size
        cw = round(ih * w / h)
        if cw < iw:
            im = im.crop(((iw - cw) // 2, 0, (iw - cw) // 2 + cw, ih))
    im = im.copy()
    im.thumbnail((w, h), Image.LANCZOS)
    cell = Image.new("RGB", (w, h), (24, 24, 24))
    cell.paste(im, ((w - im.width) // 2, (h - im.height) // 2))
    return cell


def sheet(rows, cell_w, cell_h, title, path):
    head, lab = 56, 34
    W, H = cell_w * max(len(cells) for _, cells in rows), head + (lab + cell_h) * len(rows)
    out = Image.new("RGB", (W, H), (12, 12, 12))
    d = ImageDraw.Draw(out)
    d.text((10, 10), title, fill=(235, 210, 120), font=font(28))
    for r, (row_name, cells) in enumerate(rows):
        y = head + r * (lab + cell_h)
        for c, (col_name, im, portrait) in enumerate(cells):
            d.text((c * cell_w + 8, y + 4), "%s · %s" % (col_name, row_name), fill=(220, 220, 220), font=font(22))
            if im is not None:
                out.paste(fit(im, cell_w, cell_h, portrait), (c * cell_w, y + lab))
            else:
                d.text((c * cell_w + 20, y + lab + 20), "нет кадра", fill=(200, 80, 80), font=font(22))
    out.save(path, quality=88, optimize=True)
    return hashlib.sha256(path.read_bytes()).hexdigest()


def team_difference(blue, red):
    """Where Blue and Red frames differ (the team colour on the cloth and the base band): pixel fraction with a mean
    channel difference > 24 levels, and the mean colour of those pixels in each frame."""
    a, b = np.asarray(blue, np.int16), np.asarray(red, np.int16)
    diff = np.abs(a - b).mean(axis=2)
    m = diff > 24
    res = {"changed_fraction": round(float(m.mean()), 5), "changed_px": int(m.sum()),
           "mean_abs_diff_all": round(float(diff.mean()), 4)}
    if m.any():
        res["blue_frame_mean_rgb_where_changed"] = [round(float(v), 1) for v in a[m].mean(axis=0)]
        res["red_frame_mean_rgb_where_changed"] = [round(float(v), 1) for v in b[m].mean(axis=0)]
    return res


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--run-dir", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--tag", default="r1")
    ap.add_argument("--blender-frames", default=None)
    a = ap.parse_args()
    run = Path(a.run_dir).resolve()
    manifest = json.loads((run / "manifest.json").read_text(encoding="utf-8"))
    ue_rep = json.loads((run / "reports/ue-import-report.json").read_text(encoding="utf-8"))
    if not ue_rep.get("passed"):
        raise SystemExit("the run's ue-import did not pass; nothing to review")
    profile = json.loads((REPO / manifest["config"]["build_profile"]).read_text(encoding="utf-8"))
    names = ue_rep["destination"]["assets"]
    u = profile["ue"]
    teams = sorted(u["teams"])
    default = u["default_team"]
    other = [t for t in teams if t != default]
    light = json.loads(PROFILES_JSON.read_text(encoding="utf-8"))["lightProfiles"][LIGHT_PROFILE]
    out = Path(a.out).resolve()
    out.mkdir(parents=True, exist_ok=True)
    ue = Ue()
    rv = Review(ue, out, a.tag)
    started = dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat()
    original = ue.call("scene", "get_current_level", record=False)
    if ue.call("asset", "is_dirty", {"asset_path": original}, record=False):
        raise SystemExit("open level %s has unsaved changes; refusing to switch levels" % original)
    if original.split(".")[0] == LEVEL:
        raise SystemExit("the review level itself is open; open another level first")
    if ue.call("asset", "is_dirty", {"asset_path": LEVEL}, record=False):
        raise SystemExit("the review level has unsaved changes in memory (someone else is using it)")
    sg_before = {n: cvar_value(ue, n) for n in SG}
    bv_before = cvar_value(ue, "r.BufferVisualizationTarget")
    report = {"schema": SCHEMA, "tag": a.tag, "started_at": started, "tool": "tools/tripo-pipeline/review/h2_ue_review.py",
              "kind": "EDITOR review frames (live UnrealEditor via MCP); not packaged, no HUD, no boardState, no RENDER "
                      "fingerprint, not K1/K2 acceptance",
              "run": str(run.relative_to(REPO)).replace("\\", "/"), "profile": profile["profile_id"],
              "assets": names, "original_level": original, "review_level": LEVEL, "cell": CELL,
              "light_profile": {"source": "%s lightProfiles.%s" % (PROFILES_JSON.relative_to(REPO).as_posix(),
                                                                   LIGHT_PROFILE), "data": light},
              "key_rotation_pitch_yaw_roll": KEY_ROTATION, "key_rotation_note": KEY_ROTATION_NOTE,
              "scalability_before": sg_before, "buffer_visualization_target_before": bv_before, "console": [], "teams": {t: u["teams"][t] for t in teams}}
    temp = [L_FIG, L_BASE, L_SKY, L_CAM_NARROW]
    try:
        ue.call("scene", "load_level", {"level_path": LEVEL})
        time.sleep(3.0)
        report["setup"] = rv.task("h2_review_ue.py", "setup", timeout=600, level=LEVEL, hide_label_prefixes=["P17 "],
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
                                  figure={"label": L_FIG, "kind": "skeletal", "asset": names["skeletal"],
                                          "location": CELL, "yaw": 0.0},
                                  base={"label": L_BASE, "kind": "static", "asset": names["base"], "location": CELL,
                                        "yaw": 0.0})
        report["measure_yaw0"] = rv.task("h2_review_ue.py", "measure", label=L_FIG, base_label=L_BASE, bones=BONES,
                                         sockets=SOCKETS)
        for n in SG:
            ue.console("%s 2" % n)
            report["console"].append("%s 2" % n)
        for flag in SHOW_FLAGS_OFF:
            ue.console("ShowFlag.%s 0" % flag)
            report["console"].append("ShowFlag.%s 0" % flag)
        report["scalability_during"] = {n: cvar_value(ue, n) for n in SG}
        report["screen_percentage"] = {n: cvar_value(ue, n) for n in ("r.ScreenPercentage",
                                                                       "r.Editor.Viewport.ScreenPercentage")}
        report["anti_aliasing_method"] = cvar_value(ue, "r.AntiAliasingMethod")
        report["gi_reflections"] = {n: cvar_value(ue, n) for n in ("r.DynamicGlobalIlluminationMethod",
                                                                     "r.ReflectionMethod")}
        time.sleep(8.0)  # shader compile / texture streaming of the new level and the High settings
        vs = views()
        # warm-up on the first view until two consecutive captures agree (streaming), not kept
        rv.task("control_scene_ue.py", "set", changes=[{"label": L_FIG, "yaw": 90.0}, {"label": L_BASE, "yaw": 90.0}])
        v0 = vs["k2-5x-az0"]
        rv.task("control_scene_ue.py", "camera", label=v0["cam"], location=v0["eye"], rotation=v0["rot"], fov=v0["fov"])
        xform = {"location": dict(zip("xyz", v0["eye"])), "rotation": dict(zip(("pitch", "yaw", "roll"), v0["rot"])),
                 "scale": {"x": 1, "y": 1, "z": 1}}
        prev, warm = None, []
        for _ in range(25):
            im = rv.grab(xform)
            if prev is not None:
                warm.append(round(float(np.abs(np.asarray(im, np.int16) - np.asarray(prev, np.int16)).mean()), 4))
                if warm[-1] < 0.05 and len(warm) >= 3:
                    break
            prev = im
            time.sleep(1.5)
        report["warmup_mean_abs_diff"] = warm
        shots = {}
        for team in [default] + other:
            if team != default:
                rv.task("control_scene_ue.py", "set", changes=[
                    {"label": L_FIG, "materials": {"0": names["team:figure:%s" % team]}},
                    {"label": L_BASE, "materials": {"0": names["team:base:%s" % team]}}])
                time.sleep(2.0)
            for name, view in vs.items():
                rv.task("control_scene_ue.py", "set", changes=[{"label": L_FIG, "yaw": view["yaw"]},
                                                               {"label": L_BASE, "yaw": view["yaw"]}])
                shots[(name, team)] = rv.shot("%s-%s" % (name, team.lower()), view,
                                              {"subject": "King Arthur H2.1 (%s)" % names["skeletal"], "view_name": name,
                                               "team": team, "team_hex": u["teams"][team],
                                               "materials": {"figure": names["team:figure:%s" % team],
                                                             "base": names["team:base:%s" % team]}})
        # G-buffer overview of the default team (front, torso): base colour / metallic / roughness as the renderer reads
        # them from the MI (sRGB of BC, ORM.B metallic, ORM.G roughness after the M_UM_Figure knobs)
        report["buffers"] = {}
        for target in BUFFERS:
            ue.console("ShowFlag.VisualizeBuffer 1")
            report["console"].append("ShowFlag.VisualizeBuffer 1")
            time.sleep(1.5)
            rv.task("control_scene_ue.py", "set", changes=[
                {"label": L_FIG, "materials": {"0": names["team:figure:%s" % default]}},
                {"label": L_BASE, "materials": {"0": names["team:base:%s" % default]}}])
            for name in ("front", "torso"):
                view = vs[name]
                rv.task("control_scene_ue.py", "set", changes=[{"label": L_FIG, "yaw": view["yaw"]},
                                                               {"label": L_BASE, "yaw": view["yaw"]}])
                report["buffers"]["%s-%s" % (name, target)] = rv.shot(
                    "%s-buffer-%s" % (name, target.lower()), view,
                    {"subject": "King Arthur H2.1 (%s)" % names["skeletal"], "view_name": name, "team": default,
                     "buffer_visualization": "overview (ShowFlag.VisualizeBuffer 1)"})
        ue.console("ShowFlag.VisualizeBuffer 2")
        report["console"].append("ShowFlag.VisualizeBuffer 2")
        report["measure_after"] = rv.task("h2_review_ue.py", "measure", label=L_FIG, base_label=L_BASE, bones=BONES,
                                          sockets=SOCKETS)
        # team colour: Blue vs Red frames of the same view
        report["team_difference"] = {}
        for name in vs:
            if len(teams) == 2:
                fa = rv.frames[shots[(name, "Blue")]]["image"] if ("Blue" in teams) else None
                fb = rv.frames[shots[(name, "Red")]]["image"] if ("Red" in teams) else None
                if fa is not None and fb is not None:
                    report["team_difference"][name] = team_difference(fa, fb)
        # sheets: Blender H2.1 | UE Blue | UE Red
        bf = Path(a.blender_frames).resolve() if a.blender_frames else None
        report["sheets"] = {}
        for sheet_name, rows_names, cw, chh, portrait in (
                ("views", ["front", "left", "back", "torso"], 620, 700, True),
                ("k2", ["k2-5x-az0", "k2-5x-az180", "k2-1p6-az0"], 960, 540, False)):
            rows = []
            for rn in rows_names:
                cells = []
                bpath = (bf / BLENDER_PAIRS[rn]) if bf else None
                cells.append(("Blender H2.1 (EEVEE, 3 солнца)", Image.open(bpath).convert("RGB") if bpath and bpath.is_file()
                              else None, portrait))
                for team in teams:
                    cells.append(("UE %s (Cobble, High)" % team, rv.frames[shots[(rn, team)]]["image"], portrait))
                rows.append((rn, cells))
            path = out / ("arthur-h2-sheet-%s.jpg" % sheet_name)
            digest = sheet(rows, cw, chh,
                           "King Arthur H2.1 · Blender (бейк) | UE редактор (живой, DX12/SM6 + Lumen, High, свет Cobble) · "
                           "кадры диагностики, не приёмка", path)
            report["sheets"][path.name] = {"sha256": digest, "rows": rows_names,
                                           "blender_frames": {rn: BLENDER_PAIRS[rn] for rn in rows_names}}
    finally:
        try:
            report["cleanup"] = rv.task("control_scene_ue.py", "cleanup", labels=temp)
        except Exception as exc:  # noqa: BLE001 - keep restoring
            report["cleanup_error"] = str(exc)
        try:
            for n, v in sg_before.items():
                if v is not None:
                    ue.console("%s %s" % (n, v))
                    report["console"].append("%s %s" % (n, v))
            if bv_before:
                ue.console("r.BufferVisualizationTarget %s" % bv_before)
                report["console"].append("r.BufferVisualizationTarget %s" % bv_before)
            for flag in SHOW_FLAGS_OFF + ("VisualizeBuffer",):
                ue.console("ShowFlag.%s 2" % flag)
                report["console"].append("ShowFlag.%s 2" % flag)
            report["scalability_after"] = {n: cvar_value(ue, n) for n in SG}
        except Exception as exc:  # noqa: BLE001
            report["console_error"] = str(exc)
        ue.call("scene", "load_level", {"level_path": original.split(".")[0]})
        time.sleep(2.0)
        report["restored_level"] = ue.call("scene", "get_current_level", record=False)
        report["restored_level_dirty"] = ue.call("asset", "is_dirty", {"asset_path": report["restored_level"]},
                                                 record=False)
        report["review_level_dirty_after_reload"] = ue.call("asset", "is_dirty", {"asset_path": LEVEL}, record=False)
        report["run_assets_dirty"] = {k: ue.call("asset", "is_dirty", {"asset_path": v}, record=False)
                                      for k, v in sorted(names.items())}
        report["frames"] = {k: {kk: vv for kk, vv in v.items() if kk != "image"} for k, v in rv.frames.items()}
        report["finished_at"] = dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat()
        tmp = out / "_task.json"
        if tmp.exists():
            tmp.unlink()
        (out / "h2-ue-review-report.json").write_text(json.dumps(report, indent=1, sort_keys=True, ensure_ascii=False)
                                                      + "\n", encoding="utf-8", newline="\n")
        print("restored:", report["restored_level"], "dirty:", report["restored_level_dirty"])


if __name__ == "__main__":
    main()
