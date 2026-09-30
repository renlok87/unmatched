"""M_UM_Figure_v2.1 dye test (host side of ue_v2.py `accent`): static switch UseTeamAccent on the Cobble control scene.

The editor is shared, so the test runs in SHORT self-contained parts. Each part runs under the exclusive editor lock
(ue_lock.py, taken by ue_v2.py). It opens the P1.7 control level, first deletes leftover "LDv2 *" actors, applies the
Cobble light and High, spawns only what it needs, captures, cleans up and reopens the previous level. Before every
scene op it checks that the review level is still the open one: if another flow switched levels, the part stops
without touching that level. Nothing is saved. Unsaved probe MIs live in /Game/UM/Materials/v2/_probe and are deleted
at the end of each part.

  --phase baseline     BEFORE the master rebuild (v2.0 graph): class wall neutral (a/b = noise) and with the _Red MIs
                       (TeamMask white x teamDyeAllowed), lit and G-buffer overview; lossless frames -> --frames.
  --phase wall         AFTER `ue_v2.py master` (v2.1): (1) legacy regression, the _Red wall with UseTeamAccent = false
                       against the baseline frames (lit and G-buffer) + the v2.0 dye check; (2) the _Accent wall
                       (TeamAccent = 1 on v < 0.5), lit and albedo (DebugView 7): on every class exactly the masked
                       half changes; (3) DebugView 1 calibration of the class colours (for the hero parts).
  --phase gain         checker spheres (dye weight DebugView 10: accent vs v2.0 path) and the gain rule
                       min(TeamDyeGain, TeamDyeCeiling / maxc(team)) on ONE albedo sphere (MI swapped, emissive).
  --phase hero-merlin  / hero-medusa: H2LD figure with unsaved probe MIs (real TeamAccent texture, C-11 P1 / P2,
                       team-accent.md gains as TeamDyeGain + TeamDyeCeiling), albedo + dye weight + class mask, front and
                       back: albedo must not change where the weight is 0 (any class: gold, bronze, skin, wood, stone),
                       must change where the weight is > 0.5.
  --phase summary      no editor: merges the part reports into <report>/um-v2-accent-report.json, wall sheet.
Frames are EDITOR frames (editor-mcp-viewport): diagnostics, not K1/K2 acceptance, no RENDER fingerprint.
"""
from __future__ import annotations

import json
import time
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

from ue_v2_scene import (CHECKERS, EXPOSURE_LABEL, F_PX, FILL_LABEL, FOV, KEY_LABEL, KEY_ROTATION, LEVEL,
                         PREFIX, PROFILES_JSON, REPO, REVIEW_PY, SG, SHOW_FLAGS_OFF, STEP, TESTS, WALL_TOP, WALL_Y,
                         Shots, annotate, cvar_value, font, project, wall_pos)
from ue_hero_lookdev import decode_debug, erode

HERE = Path(__file__).resolve().parent
PHASES = ["baseline", "wall", "gain", "hero-merlin", "hero-medusa", "summary"]
DYE_CLASSES_V20 = {7, 8, 9, 10, 11, 12}
L_CAM, L_SKY, L_FIG = PREFIX + "camera - temporary", PREFIX + "sky - temporary", PREFIX + "hero - temporary"
PROBE = "/Game/UM/Materials/v2/_probe/"
ALB_COLS = {"left": -85.0, "right": 85.0}
ALB_LAYOUT = {  # name -> (column, row): rows as the wall (0 top)
    "Neutral": ("left", 0), "AccentDefault_Red": ("left", 1), "GainE": ("left", 2), "GainD": ("left", 3),
    "GainA": ("right", 0), "GainB": ("right", 1), "GainC": ("right", 2),
}
ALB_SWAP = list(ALB_LAYOUT) + ["MerlinP1", "MerlinP1Ref", "MerlinP2", "MerlinP2Ref"]
CHECK_MIS = {"checker": TESTS + "/MI_UM_v2_Test_Checker_Accent", "checker-debug": TESTS + "/MI_UM_v2_Test_Checker_AccentW",
             "checker-uv1": TESTS + "/MI_UM_v2_Test_Checker_LegacyW"}
CHECK_NAMES = {"checker": "accent lit (red)", "checker-debug": "accent weight (DebugView 10)",
               "checker-uv1": "v2.0 weight (TeamMask white x teamDyeAllowed)"}
PALETTE = {"P1": [0.807, 0.5271, 0.1441, 1.0], "P2": [0.1022, 0.2122, 0.3467, 1.0]}  # C-11 active, linear
HEROES = {
    "Merlin": {"mesh": "/Game/PipelineCandidates/Merlin/H2LD/Meshes/SK_Merlin_H2LD",
               "neutral": "/Game/PipelineCandidates/Merlin/H2LD/Materials/MI_Merlin_H2LD_Neutral",
               "debug": "/Game/PipelineCandidates/Merlin/H2LD/Materials/MI_Merlin_H2LD_DebugClasses",
               "accent": "art/pipeline-candidates/ASSET-MERLIN-001/20260929-h2-lookdev/textures/T_Merlin_H2LD_TeamAccent_2K.png",
               "y_p50_p95": [0.0295, 0.0998],
               "source": "ld-team-accent-ue.json (Merlin): P1 11.0 / P2 26.0 by the team-accent.md rule"},
    "Medusa": {"mesh": "/Game/PipelineCandidates/Medusa/H2LD/Meshes/SK_Medusa_H2LD",
               "neutral": "/Game/PipelineCandidates/Medusa/H2LD/Materials/MI_Medusa_H2LD_Neutral",
               "debug": "/Game/PipelineCandidates/Medusa/H2LD/Materials/MI_Medusa_H2LD_DebugClass",
               "accent": "art/pipeline-candidates/ASSET-MEDUSA-001/20260929-h2-lookdev/textures/T_Medusa_H2LD_TeamAccent_2K.png",
               "y_p50_p95": [0.03489, 0.05792],
               "source": "ld-team-accent-report.json (Medusa): gain 19 for P1 by the team-accent.md rule"},
}
WALL_VIEW = {"eye": [0.0, WALL_Y + 330.0, WALL_TOP - 1.5 * STEP], "rot": [0.0, -90.0, 0.0]}
CHECK_VIEW = {"eye": [0.0, CHECKERS["checker"][0][1] + 160.0, CHECKERS["checker"][0][2]], "rot": [0.0, -90.0, 0.0]}
FIG_VIEW = {"eye": [0.0, WALL_Y + 200.0, 31.0], "rot": [0.0, -90.0, 0.0]}


def class_names():
    presets = json.loads((REPO / "docs/art-pipeline/material-library/um-material-presets-v1.json")
                         .read_text(encoding="utf-8"))
    return [c["id"] for c in presets["classes"]]


CLASS_NAMES = class_names()
WALL_LABELS = [PREFIX + "class %02d %s" % (i, CLASS_NAMES[i]) for i in range(16)]
ALB_LABELS = {n: PREFIX + "alb " + n for n in ALB_LAYOUT}
CHECK_LABELS = {k: PREFIX + k for k in CHECKERS}
ALL_LABELS = WALL_LABELS + list(ALB_LABELS.values()) + list(CHECK_LABELS.values()) + [L_FIG, L_SKY, L_CAM]


def hero_gains(y50, y95):
    """team-accent.md rule as MI values: TeamDyeGain = 0.8 / Y_p50, TeamDyeCeiling = 0.9 / Y_p95."""
    return round(0.8 / y50, 4), round(0.9 / y95, 4)


def pos_alb(name):
    col, row = ALB_LAYOUT[name]
    return [ALB_COLS[col], WALL_Y, WALL_TOP - row * STEP]


def bands(frame, eye, centre, radius_uu=10.0):
    """Mean sRGB of the upper band (-0.8 R < dy < -0.3 R) and the lower band (0.3 R < dy < 0.8 R) of a sphere disc
    (|dx| < 0.6 R): the hard accent edge (v = 0.5, the equator) stays outside both bands."""
    a = np.asarray(frame, np.float64)
    cx, cy = project(eye, centre)
    r = radius_uu / (eye[1] - centre[1]) * F_PX
    ys, xs = np.mgrid[0:a.shape[0], 0:a.shape[1]]
    dx, dy = (xs - cx) / r, (ys - cy) / r
    inside = (dx ** 2 + dy ** 2 < 0.64) & (np.abs(dx) < 0.6)
    res = {}
    for key, m in (("top", inside & (dy < -0.3)), ("bottom", inside & (dy > 0.3)), ("disc", inside)):
        res[key] = [round(float(v), 2) for v in a[m].mean(0)]
    return res


def maxdiff(x, y):
    return round(float(np.abs(np.array(x) - np.array(y)).max()), 2)


def u8(arr):
    return Image.fromarray(np.asarray(arr).astype(np.uint8))


def xform(v):
    return {"location": dict(zip("xyz", v["eye"])), "rotation": dict(zip(("pitch", "yaw", "roll"), v["rot"])),
            "scale": {"x": 1, "y": 1, "z": 1}}


class Scene:
    """One part on the control level: guarded scene ops, lossless frames, cleanup and restore in `close`."""

    def __init__(self, ue, out: Path, frames: Path, phase: str, report: dict):
        self.ue, self.out, self.phase, self.report = ue, out, phase, report
        self.frames_dir = frames / phase
        self.frames_dir.mkdir(parents=True, exist_ok=True)
        self.in_level = False
        self.shots = Shots(ue, out, self.run)
        self.sg_before = {}
        self.original = None
        report.update({"phase": phase, "level": LEVEL, "light_profile": "cobble-probe",
                       "key_rotation_pitch_yaw_roll": KEY_ROTATION, "console": [],
                       "frames_lossless_dir": str(self.frames_dir).replace("\\", "/"), "classes": CLASS_NAMES})

    def current(self):
        return (self.ue.call("scene", "get_current_level", record=False) or "").split(".")[0]

    def run(self, script, op, timeout=600, **kw):
        # the editor is shared: another flow may load its own level at any time (2026-09-30: anim-v2 restored
        # S08Arena in the middle of this test and the camera op spawned a camera there). Every scene op first checks
        # that the review level is still the open one; otherwise the part stops without touching the other level.
        if self.in_level and op != "drop_probe":
            cur = self.current()
            if cur != LEVEL:
                self.in_level = False
                raise RuntimeError("review level lost: %s is open now (another flow loaded it); stopped" % cur)
        path = REVIEW_PY / script if script == "control_scene_ue.py" else HERE / "ue" / script
        return self.ue.run_task(str(path), str(self.out / "_task.json"), timeout=timeout, op=op, **kw)

    def console(self, cmd):
        self.ue.console(cmd)
        self.report["console"].append(cmd)

    def open(self, spheres):
        ue = self.ue
        original = ue.call("scene", "get_current_level", record=False)
        if ue.call("asset", "is_dirty", {"asset_path": original}, record=False):
            raise SystemExit("open level %s has unsaved changes; refusing to switch levels" % original)
        if original.split(".")[0] == LEVEL:
            raise SystemExit("the review level itself is open; open another level first")
        if ue.call("asset", "is_dirty", {"asset_path": LEVEL}, record=False):
            raise SystemExit("the review level has unsaved changes in memory (someone else is using it)")
        self.original = original
        self.report["original_level"] = original
        self.sg_before = {n: cvar_value(ue, n) for n in SG}
        self.report["scalability_before"] = self.sg_before
        light = json.loads(PROFILES_JSON.read_text(encoding="utf-8"))["lightProfiles"]["cobble-probe"]
        ue.call("scene", "load_level", {"level_path": LEVEL})
        time.sleep(3.0)
        if self.current() != LEVEL:
            raise RuntimeError("could not open the review level")
        self.in_level = True
        # the level package can stay in memory between loads: remove leftovers of an earlier interrupted part
        self.report["preclean"] = self.run("control_scene_ue.py", "cleanup", labels=ALL_LABELS)
        self.report["setup"] = self.run(
            "um_v2_scene_ue.py", "setup", level=LEVEL, hide_label_prefixes=["P17 "], keep_labels=[EXPOSURE_LABEL],
            lights={"off": [FILL_LABEL],
                    "key": {"label": KEY_LABEL, "intensity_lux": light["directional"]["intensity"],
                            "shadow_distance_uu": light["directional"]["shadow"]["distanceUU"],
                            "cascades": light["directional"]["shadow"]["cascades"],
                            "contact_shadow_length": light["directional"]["shadow"]["contactShadowLength"],
                            "rotation_pitch_yaw_roll": KEY_ROTATION}},
            sky={"label": L_SKY, "cubemap": light["sky"]["cubemap"], "intensity": light["sky"]["intensity"],
                 "lower_hemisphere_is_black": light["sky"]["lowerHemisphereIsBlack"],
                 "color_linear": light["sky"]["colorLinear"]},
            spheres=spheres, probe=None)
        for n in SG:
            self.console("%s 2" % n)
        for flag in SHOW_FLAGS_OFF:
            self.console("ShowFlag.%s 0" % flag)
        self.report["scalability_during"] = {n: cvar_value(ue, n) for n in SG}
        self.report["render_cvars"] = {n: cvar_value(ue, n) for n in ("r.ScreenPercentage", "r.AntiAliasingMethod",
                                                                         "r.DynamicGlobalIlluminationMethod",
                                                                         "r.ReflectionMethod", "r.Substrate")}
        time.sleep(8.0)

    def close(self):
        ue, report = self.ue, self.report
        lost = not self.in_level or self.current() != LEVEL
        report["review_level_lost"] = lost
        try:
            if not lost:
                report["cleanup"] = self.run("control_scene_ue.py", "cleanup", labels=ALL_LABELS)
        except Exception as exc:  # noqa: BLE001
            report["cleanup_error"] = str(exc)
        try:
            for n, v in self.sg_before.items():
                if v is not None:
                    self.console("%s %s" % (n, v))
            for flag in SHOW_FLAGS_OFF + ("VisualizeBuffer", "Bloom"):
                self.console("ShowFlag.%s 2" % flag)
            report["scalability_after"] = {n: cvar_value(ue, n) for n in SG}
        except Exception as exc:  # noqa: BLE001
            report["console_error"] = str(exc)
        if not lost and self.original:
            try:
                ue.call("scene", "load_level", {"level_path": self.original.split(".")[0]})
                time.sleep(2.0)
            except Exception as exc:  # noqa: BLE001
                report["restore_error"] = str(exc)
        self.in_level = False
        try:
            report["drop_probe"] = self.run("um_v2_scene_ue.py", "drop_probe")
        except Exception as exc:  # noqa: BLE001
            report["drop_probe_error"] = str(exc)
        report["restored_level"] = ue.call("scene", "get_current_level", record=False)
        report["restored_level_dirty"] = ue.call("asset", "is_dirty", {"asset_path": report["restored_level"]},
                                                 record=False)
        report["review_level_dirty_after_reload"] = ue.call("asset", "is_dirty", {"asset_path": LEVEL}, record=False)
        report["frames"] = {k: {kk: vv for kk, vv in v.items() if kk != "image"} for k, v in self.shots.frames.items()}

    # ---- capture helpers
    def settle(self, view, n=20):
        prev = None
        for _ in range(n):
            im = self.shots.grab(xform(view))
            # the shared editor viewport can be resized between grabs (2026-09-30: 2033 -> 1350 px wide): restart
            if prev is not None and im.size != prev.size:
                self.report.setdefault("viewport_resized", []).append([list(prev.size), list(im.size)])
                prev = im
                continue
            if prev is not None and float(np.abs(np.asarray(im, np.int16) - np.asarray(prev, np.int16)).mean()) < 0.05:
                return
            prev = im
            time.sleep(2.0)

    def camera(self, view):
        self.run("control_scene_ue.py", "camera", label=L_CAM, location=view["eye"], rotation=view["rot"], fov=FOV)

    def shot(self, name, view, meta):
        img = self.shots.shot(name, view, dict(meta, phase=self.phase))
        img.save(self.frames_dir / (name + ".png"), optimize=False, compress_level=1)
        return np.asarray(img, np.int16)

    def set(self, changes):
        self.run("control_scene_ue.py", "set", changes=changes)

    def vis(self, labels, on):
        if labels:
            self.set([{"label": lab, "visible": on} for lab in labels])

    def mats(self, labels_to_mi):
        self.set([{"label": lab, "materials": {"0": mi}} for lab, mi in labels_to_mi.items()])

    def probe(self, textures, instances):
        pr = self.run("um_v2_scene_ue.py", "accent_probe", textures=textures, instances=instances)
        return {"textures": pr.get("textures"), "instances": len(pr.get("instances") or {})}


def wall_mis(suffix):
    return {WALL_LABELS[i]: "%s/MI_UM_v2_Test_Class%02d%s" % (TESTS, i, suffix) for i in range(16)}


def wall_bands(frame):
    return {CLASS_NAMES[i]: bands(u8(frame), WALL_VIEW["eye"], wall_pos(i)) for i in range(16)}


# ------------------------------------------------------------------ parts

def part_wall(sc: Scene, a, meas: dict, report: dict) -> None:
    """baseline (v2.0) or wall (v2.1): the class wall only."""
    after = sc.phase == "wall"
    vw = WALL_VIEW
    sc.camera(vw)
    sc.settle(vw, 40)
    f = {"neutral_a": sc.shot("acc-wall-neutral-a", vw, {"subject": "class wall, TeamColor white"})}
    time.sleep(2.0)
    f["neutral_b"] = sc.shot("acc-wall-neutral-b", vw, {"subject": "class wall, TeamColor white (noise pair)"})
    sc.mats(wall_mis("_Red"))
    time.sleep(3.0)
    sc.settle(vw)
    f["red"] = sc.shot("acc-wall-red-legacy", vw, {"subject": "class wall _Red: v2.0 path (TeamMask white x "
                                                              "teamDyeAllowed)%s" % (", UseTeamAccent false" if after else "")})
    sc.console("ShowFlag.VisualizeBuffer 1")
    time.sleep(3.0)
    f["red_buf"] = sc.shot("acc-wall-red-legacy-buffers", vw, {"subject": "G-buffer overview, _Red wall"})
    sc.console("ShowFlag.VisualizeBuffer 0")
    meas["noise_neutral_pair_mean_abs"] = round(float(np.abs(f["neutral_a"] - f["neutral_b"]).mean()), 4)
    meas["wall_neutral"] = wall_bands(f["neutral_a"])
    meas["wall_neutral_b"] = wall_bands(f["neutral_b"])
    meas["wall_red"] = wall_bands(f["red"])
    dye20 = {}
    for i in range(16):
        c = CLASS_NAMES[i]
        d = maxdiff(meas["wall_neutral"][c]["disc"], meas["wall_red"][c]["disc"])
        exp = i in DYE_CLASSES_V20 or i == 0
        dye20[c] = {"max_channel_diff": d, "changed": d > 6.0, "expected_changed": exp, "ok": (d > 6.0) == exp}
    meas["dye_check_v20"] = dye20
    report["dye_v20_ok"] = all(v["ok"] for v in dye20.values())
    if not after:
        return
    base = Path(a.frames).resolve() / "baseline"
    base_jpg = sc.out.parent / "baseline"
    reg = {}
    modes = set()
    for key, name in (("red", "acc-wall-red-legacy"), ("red_buf", "acc-wall-red-legacy-buffers"),
                      ("neutral_a", "acc-wall-neutral-a")):
        bf = base / (name + ".png")
        if bf.is_file():
            # lossless baseline against the lossless frame of this run
            b, cur, mode = np.asarray(Image.open(bf).convert("RGB"), np.int16), f[key], "png"
        else:
            # the lossless baseline frames of the red wall were lost with the interrupted run (2026-09-30): compare the
            # baseline evidence JPEG with the JPEG of this run (same encoder, quality 92; identical frames give
            # identical JPEG bytes, JPEG ringing spreads a real difference only inside its 8x8 block)
            bj, cj = base_jpg / ("um-v2-%s.jpg" % name), sc.out / ("um-v2-%s.jpg" % name)
            if not (bj.is_file() and cj.is_file()):
                reg[key] = "baseline frame missing: %s and %s" % (bf, bj)
                continue
            b = np.asarray(Image.open(bj).convert("RGB"), np.int16)
            cur, mode = np.asarray(Image.open(cj).convert("RGB"), np.int16), "jpeg-q92"
        modes.add(mode)
        reg[key] = {"compare": mode, "mean_abs_full_frame": round(float(np.abs(b - cur).mean()), 4)}
        if key == "red":
            per = {CLASS_NAMES[i]: maxdiff(bands(u8(b), vw["eye"], wall_pos(i))["disc"],
                                           bands(u8(cur), vw["eye"], wall_pos(i))["disc"]) for i in range(16)}
            reg[key]["per_class_disc_max_channel_diff"] = per
            reg[key]["worst"] = max(per.values())
        if key == "red_buf":
            tiles = {}
            for (r_, c_), tname in {(0, 0): "base_colour", (0, 1): "specular", (0, 3): "world_normal",
                                    (3, 1): "roughness", (3, 2): "metallic", (3, 3): "shading_model"}.items():
                sl = (slice(r_ * 270 + 30, r_ * 270 + 240), slice(c_ * 480 + 10, c_ * 480 + 470))
                tiles[tname] = {"mean_abs": round(float(np.abs(b[sl] - cur[sl]).mean()), 4),
                                "max_abs": int(np.abs(b[sl] - cur[sl]).max())}
            reg[key]["tiles"] = tiles
    reg["rule"] = ("v2.0 path (UseTeamAccent false) against the v2.0 master: G-buffer tiles equal (base colour, "
                   "metallic, roughness, normal, shading model: lossless max 0; JPEG-vs-JPEG mean <= 0.05 level), lit "
                   "class discs within the frame-to-frame noise of the neutral pair")
    meas["legacy_regression_vs_v20"] = reg
    tiles = reg.get("red_buf", {}).get("tiles", {}) if isinstance(reg.get("red_buf"), dict) else {}
    gtiles = ("base_colour", "metallic", "roughness", "world_normal", "shading_model")
    if modes == {"png"}:
        ok = bool(tiles) and all(tiles[t]["max_abs"] == 0 for t in gtiles)
    else:
        ok = bool(tiles) and all(tiles[t]["mean_abs"] <= 0.05 for t in gtiles)
    report["legacy_regression_ok"] = ok
    report["legacy_regression_compare"] = sorted(modes)
    # accent wall, lit
    sc.mats(wall_mis("_Accent"))
    time.sleep(3.0)
    sc.settle(vw)
    f["accent"] = sc.shot("acc-wall-accent", vw, {"subject": "class wall _Accent: UseTeamAccent, TeamAccent 1 on v < 0.5, "
                                                             "TeamColor red, TeamDye 1, gain 1"})
    meas["wall_accent"] = wall_bands(f["accent"])
    # albedo (DebugView 7) and class colours (DebugView 1) through unsaved probe MIs
    inst = []
    for i in range(16):
        inst += [{"name": "MI_Probe_WallN_%02d" % i, "parent": "%s/MI_UM_v2_Test_Class%02d" % (TESTS, i),
                  "scalars": {"DebugView": 7.0}},
                 {"name": "MI_Probe_WallA_%02d" % i, "parent": "%s/MI_UM_v2_Test_Class%02d_Accent" % (TESTS, i),
                  "scalars": {"DebugView": 7.0}},
                 {"name": "MI_Probe_Cal_%02d" % i, "parent": "%s/MI_UM_v2_Test_Class%02d" % (TESTS, i),
                  "scalars": {"DebugView": 1.0}}]
    report["accent_probe"] = sc.probe({}, inst)
    alb = {}
    for key, prefix, fname, subj in (("alb_n", "WallN", "acc-wall-albedo-neutral", "class wall albedo (DebugView 7), no dye"),
                                     ("alb_a", "WallA", "acc-wall-albedo-accent", "_Accent wall albedo (DebugView 7)"),
                                     ("cal", "Cal", "acc-wall-debugclass", "class wall DebugView 1 (class colours)")):
        sc.mats({WALL_LABELS[i]: PROBE + "MI_Probe_%s_%02d" % (prefix, i) for i in range(16)})
        time.sleep(3.0)
        sc.settle(vw)
        f[key] = sc.shot(fname, vw, {"subject": subj})
        alb[key] = wall_bands(f[key])
    meas["debug_class_calibration_srgb"] = {str(i): alb["cal"][CLASS_NAMES[i]]["disc"] for i in range(16)}
    nb = {}
    for c in CLASS_NAMES:
        n0, n1, ac = meas["wall_neutral"][c], meas["wall_neutral_b"][c], meas["wall_accent"][c]
        an, aa = alb["alb_n"][c], alb["alb_a"][c]
        nb[c] = {"albedo_top": maxdiff(an["top"], aa["top"]), "albedo_bottom": maxdiff(an["bottom"], aa["bottom"]),
                 "lit_top": maxdiff(n0["top"], ac["top"]), "lit_bottom": maxdiff(n0["bottom"], ac["bottom"]),
                 "lit_noise_top": maxdiff(n0["top"], n1["top"]), "lit_noise_bottom": maxdiff(n0["bottom"], n1["bottom"])}
    tops = sum(1 for v in nb.values() if v["albedo_top"] > 6.0)
    masked = "top" if tops >= 8 else "bottom"
    free = "bottom" if masked == "top" else "top"
    for v in nb.values():
        v["masked_half"] = masked
        v["albedo_masked_changed"] = v["albedo_" + masked] > 6.0
        v["albedo_free_unchanged"] = v["albedo_" + free] <= 1.5
        v["ok"] = v["albedo_masked_changed"] and v["albedo_free_unchanged"]
        v["lit_free_within_noise"] = v["lit_" + free] <= max(3.0, 2.0 * v["lit_noise_" + free])
    meas["dye_check_accent"] = nb
    meas["dye_check_accent_rule"] = ("albedo (DebugView 7) of the masked half changes by > 6 sRGB levels and of the free "
                                     "half by <= 1.5 on every class; lit_* = the same in the lit frame (informational: "
                                     "mirror classes also reflect their dyed neighbours)")
    report["dye_accent_ok"] = all(v["ok"] for v in nb.values())
    names = ["%d %s" % (i, CLASS_NAMES[i]) for i in range(16)]
    pos = [wall_pos(i) for i in range(16)]
    sheet = Image.new("RGB", (1920 * 3, 1080 + 60), (12, 12, 12))
    d = ImageDraw.Draw(sheet)
    d.text((12, 12), "M_UM_Figure_v2.1 · 16 классов · слева без красителя · в центре UseTeamAccent=false (путь v2.0: "
                     "TeamMask белый × teamDyeAllowed) · справа UseTeamAccent=true, TeamAccent = 1 на v < 0.5 (красится "
                     "любой класс, только по маске) · TeamColor красный · редактор, DX12/SM6 + Lumen, High, Cobble · "
                     "диагностика", fill=(235, 210, 120), font=font(26))
    for k, key in enumerate(("neutral_a", "red", "accent")):
        sheet.paste(annotate(u8(f[key]), vw["eye"], names, pos), (1920 * k, 60))
    sp = sc.out / "acc-sheet-wall.jpg"
    sheet.save(sp, quality=88, optimize=True)
    report["sheet"] = sp.name


def part_gain(sc: Scene, a, meas: dict, report: dict) -> None:
    """Checker spheres (dye weight of every class) and the gain rule on one albedo sphere."""
    sc.vis(list(ALB_LABELS.values()), False)
    sc.camera(CHECK_VIEW)
    time.sleep(2.0)
    sc.settle(CHECK_VIEW)
    fr = sc.shot("acc-checkers", CHECK_VIEW, {"subject": "MatID checker: " + "; ".join(
        "%s = %s" % (k, CHECK_NAMES[k]) for k in CHECKERS)})
    meas["checkers"] = {CHECK_NAMES[k]: bands(u8(fr), CHECK_VIEW["eye"], CHECKERS[k][0]) for k in CHECKERS}
    ck = meas["checkers"]
    report["checkers_ok"] = (min(ck[CHECK_NAMES["checker-debug"]]["top"]) > 200
                             and max(ck[CHECK_NAMES["checker-debug"]]["bottom"]) < 3)
    sc.vis(list(CHECK_LABELS.values()), False)
    sc.vis(list(ALB_LABELS.values()), True)
    vw = WALL_VIEW
    sc.camera(vw)
    time.sleep(3.0)
    sc.settle(vw)
    sc.shot("acc-albedo-spheres", vw, {"subject": "albedo spheres (DebugView 7), class 7: " + ", ".join(ALB_LAYOUT)})
    slot, spos = ALB_LABELS["GainA"], pos_alb("GainA")
    alb = {}
    for n in ALB_SWAP:
        sc.mats({slot: "%s/MI_UM_v2_Test_Alb_%s" % (TESTS, n)})
        time.sleep(1.5)
        grabs = []
        for _ in range(2):
            g = sc.shots.grab(xform(vw))
            w, hh = g.size
            chh = round(w * 9 / 16)
            box = (0, (hh - chh) // 2, w, (hh - chh) // 2 + chh)
            grabs.append(bands(g.crop(box).resize((1920, 1080), Image.LANCZOS), vw["eye"], spos)["disc"])
            time.sleep(0.7)
        alb[n] = {"a": grabs[0], "b": grabs[1]}
    gains = {"slot": "sphere %s at %s, MI swapped" % (slot, spos),
             "noise_a_b": {n: maxdiff(v["a"], v["b"]) for n, v in alb.items()}}
    pairs = {"AccentDefault_Red == Neutral (accent black: no dye, old TeamMask white ignored)":
             ("AccentDefault_Red", "Neutral", "equal"),
             "GainB == GainA (ceiling binds: min(100, 16/0.8) = 20)": ("GainB", "GainA", "equal"),
             "GainC == GainA (ceiling not binding)": ("GainC", "GainA", "equal"),
             "GainD == GainA (v2.0 path ignores the ceiling)": ("GainD", "GainA", "equal"),
             "GainE != GainA (gain 10 vs 20: the test is sensitive)": ("GainE", "GainA", "differ"),
             "GainA != Neutral (dyed)": ("GainA", "Neutral", "differ"),
             "MerlinP1 == MerlinP1Ref (min(27.12, 9.018/0.807) = 11.175)": ("MerlinP1", "MerlinP1Ref", "equal"),
             "MerlinP2 == MerlinP2Ref (min(27.12, 9.018/0.3467) = 26.01)": ("MerlinP2", "MerlinP2Ref", "equal")}
    res = {}
    for label, (x, y, kind) in pairs.items():
        d = maxdiff(alb[x]["a"], alb[y]["a"])
        res[label] = {"max_channel_diff": d, "ok": d <= 1.0 if kind == "equal" else d > 6.0}
    gains["pairs"] = res
    gains["rule"] = "equal pairs <= 1.0 sRGB level (disc mean, same sphere), differing pairs > 6"
    gains["spheres_srgb"] = {n: v["a"] for n, v in alb.items()}
    meas["gain_rule"] = gains
    report["gain_rule_ok"] = all(v["ok"] for v in res.values())


HERO_RULE = ("zones on the DECODED figure pixels only (DebugView 1 class found; the figure shadow on the floor, which "
             "differs from the plate, is excluded). Albedo = DebugView 7 of the probe MI P1/P2 against Neutral. Weight 0 "
             "(DebugView 10 luma < 4, 2 px erosion): <= 0.2 %% of pixels change by > 6 sRGB levels and the signed mean "
             "change (bias toward the team colour) is <= 0.1 level in every channel; the mean absolute change and the "
             "Neutral-vs-Neutral albedo noise (alb_N2) are reported (debug views captured with ShowFlag.Bloom 0: the "
             "bloom haze of the dyed accents is an additive bias in the team hue). High weight (DebugView 10 luma > %d; "
             "w = 1 gives 223, 1 px erosion): >= 95 %% change by > 6 against Neutral AND differ by > 6 between P1 and "
             "P2 (the dye follows the team colour). Lit numbers are informational (Lumen bounce and reflections of "
             "the dyed accent reach nearby pixels)")
W_HIGH = 150.0
HERO_RULE = HERO_RULE % int(W_HIGH)


def analyse_hero_view(fr: dict, calib: dict):
    """Zone statistics of one hero view from the frames (int16 arrays): alb_N, alb_N2, alb_P1, alb_P2, w, dbg, plate,
    n_a, n_b, P1, P2. Pure function (offline rescoring of the lossless frames uses it too)."""
    cls, fig_px = decode_debug(fr["dbg"].astype(np.uint8), fr["plate"].astype(np.uint8), list(range(16)), calib=calib)
    figd = cls >= 0
    wl = fr["w"].astype(np.float32) @ np.array([0.2126, 0.7152, 0.0722], np.float32)
    w0 = erode(figd & (wl < 4.0), 2)            # weight 0, 2 px away from any accent pixel
    w1 = erode(figd & (wl > W_HIGH), 1)         # high weight
    lit_noise = np.abs(fr["n_a"] - fr["n_b"]).max(-1)
    alb_noise = np.abs(fr["alb_N2"] - fr["alb_N"]).max(-1) if "alb_N2" in fr else None
    alb_d = {t: np.abs(fr["alb_" + t] - fr["alb_N"]).max(-1) for t in PALETTE}
    alb_12 = np.abs(fr["alb_P1"] - fr["alb_P2"]).max(-1)
    lit_d = {t: np.abs(fr[t] - fr["n_a"]).max(-1) for t in PALETTE}
    per = {}
    for ci in sorted(set(int(x) for x in np.unique(cls)) - {-1}):
        m = cls == ci
        e = {"px": int(m.sum())}
        for zone, zm in (("weight0", m & w0), ("weight_high", m & w1)):
            n = int(zm.sum())
            e[zone + "_px"] = n
            if n < 50:
                continue
            for team in PALETTE:
                e["%s_%s_albedo_mean" % (zone, team)] = round(float(alb_d[team][zm].mean()), 3)
                e["%s_%s_albedo_gt6_share" % (zone, team)] = round(float((alb_d[team][zm] > 6).mean()), 4)
                e["%s_%s_lit_mean" % (zone, team)] = round(float(lit_d[team][zm].mean()), 3)
            e[zone + "_lit_noise_mean"] = round(float(lit_noise[zm].mean()), 3)
            if alb_noise is not None:
                e[zone + "_albedo_noise_mean"] = round(float(alb_noise[zm].mean()), 3)
        per[CLASS_NAMES[ci]] = e
    summ = {"figure_px": int(fig_px.sum()), "decoded_px": int(figd.sum()),
            "undecoded_changed_px": int((fig_px & ~figd).sum()), "weight0_px": int(w0.sum()),
            "weight_high_px": int(w1.sum()), "weight_high_threshold_luma": W_HIGH,
            "lit_noise_weight0_mean": round(float(lit_noise[w0].mean()), 3),
            "weight_high_P1_vs_P2_albedo_gt6_share": round(float((alb_12[w1] > 6).mean()), 4)}
    if alb_noise is not None:
        summ["albedo_noise_weight0_mean"] = round(float(alb_noise[w0].mean()), 4)
        summ["albedo_noise_weight0_gt6_share"] = round(float((alb_noise[w0] > 6).mean()), 5)
    for team in PALETTE:
        summ["weight0_%s_albedo_mean" % team] = round(float(alb_d[team][w0].mean()), 4)
        summ["weight0_%s_albedo_bias_rgb" % team] = [round(float(v), 4) for v in
                                                     (fr["alb_" + team] - fr["alb_N"])[w0].astype(np.float64).mean(0)]
        summ["weight0_%s_albedo_gt6_share" % team] = round(float((alb_d[team][w0] > 6).mean()), 5)
        summ["weight_high_%s_albedo_mean" % team] = round(float(alb_d[team][w1].mean()), 3)
        summ["weight_high_%s_albedo_gt6_share" % team] = round(float((alb_d[team][w1] > 6).mean()), 4)
        summ["weight0_%s_lit_mean" % team] = round(float(lit_d[team][w0].mean()), 3)
        summ["weight_high_%s_lit_mean" % team] = round(float(lit_d[team][w1].mean()), 3)
    checks = {}
    for t in PALETTE:
        c = {"weight0_albedo_gt6_share_le_0_002": summ["weight0_%s_albedo_gt6_share" % t] <= 0.002,
             "weight_high_albedo_gt6_share_ge_0_95": summ["weight_high_%s_albedo_gt6_share" % t] >= 0.95,
             "weight_high_P1_vs_P2_gt6_share_ge_0_95": summ["weight_high_P1_vs_P2_albedo_gt6_share"] >= 0.95}
        c["weight0_albedo_bias_le_0_1"] = max(abs(v) for v in summ["weight0_%s_albedo_bias_rgb" % t]) <= 0.1
        checks[t] = c
    return per, summ, checks


def part_hero(sc: Scene, a, meas: dict, report: dict, hero: str, calib: dict) -> None:
    h = dict(HEROES[hero])
    g, c = hero_gains(*h["y_p50_p95"])
    inst = []
    for team, col in PALETTE.items():
        for suffix, extra in (("", {}), ("_Alb", {"DebugView": 7.0})):
            inst.append({"name": "MI_Probe_%s_%s%s" % (hero, team, suffix), "parent": h["neutral"],
                         "scalars": dict({"TeamDye": 1.0, "TeamDyeGain": g, "TeamDyeCeiling": c}, **extra),
                         "vectors": {"TeamColor": col}, "textures": {"TeamAccentTexture": "probe:" + hero},
                         "switches": {"UseTeamAccent": True}})
    inst.append({"name": "MI_Probe_%s_Neutral_Alb" % hero, "parent": h["neutral"], "scalars": {"DebugView": 7.0},
                 "textures": {"TeamAccentTexture": "probe:" + hero}, "switches": {"UseTeamAccent": True}})
    inst.append({"name": "MI_Probe_%s_W" % hero, "parent": h["neutral"], "scalars": {"DebugView": 10.0},
                 "textures": {"TeamAccentTexture": "probe:" + hero}, "switches": {"UseTeamAccent": True}})
    report["accent_probe"] = sc.probe({hero: str((REPO / h["accent"]).resolve()).replace("\\", "/")}, inst)
    hv = {"TeamDyeGain": g, "TeamDyeCeiling": c, "source": h["source"], "accent_texture": h["accent"],
          "effective_gain": {t: round(min(g, c / max(col[:3])), 3) for t, col in PALETTE.items()}, "views": {}}
    fig = sc.run("um_v2_scene_ue.py", "figure", label=L_FIG, asset=h["mesh"], location=[0.0, WALL_Y, 0.0], yaw=90.0,
                 material=h["neutral"])
    slots = int(fig.get("slots", 1))
    hv["slots"] = slots

    def put(mat):
        sc.set([{"label": L_FIG, "materials": {str(i): mat for i in range(slots)}}])
        time.sleep(4.0)

    fv = FIG_VIEW
    sc.camera(fv)
    for vname, yaw in (("front", 90.0), ("back", 270.0)):
        sc.set([{"label": L_FIG, "yaw": yaw}])
        put(h["neutral"])
        time.sleep(8.0)
        sc.settle(fv)
        fr = {}
        tag = "acc-%s-%s" % (hero.lower(), vname)
        fr["n_a"] = sc.shot(tag + "-neutral-a", fv, {"subject": "%s H2LD Neutral" % hero})
        time.sleep(2.0)
        fr["n_b"] = sc.shot(tag + "-neutral-b", fv, {"subject": "%s H2LD Neutral (noise pair)" % hero})
        for team in PALETTE:
            put(PROBE + "MI_Probe_%s_%s" % (hero, team))
            fr[team] = sc.shot("%s-%s" % (tag, team.lower()), fv,
                               {"subject": "%s H2LD probe MI: UseTeamAccent, TeamAccent, %s" % (hero, team)})
        # emissive debug views without bloom: the bloom haze of the bright dyed accents (additive, in the team hue,
        # decaying over ~60 px) would otherwise show up as an albedo change of the weight-0 pixels (2026-09-30 r3)
        sc.console("ShowFlag.Bloom 0")
        time.sleep(2.0)
        for key, mat in (("alb_N", "MI_Probe_%s_Neutral_Alb" % hero), ("alb_P1", "MI_Probe_%s_P1_Alb" % hero),
                         ("alb_P2", "MI_Probe_%s_P2_Alb" % hero), ("w", "MI_Probe_%s_W" % hero),
                         ("alb_N2", "MI_Probe_%s_Neutral_Alb" % hero)):
            # alb_N2: Neutral albedo again after three material swaps = the noise pair of the albedo comparison
            put(PROBE + mat)
            fr[key] = sc.shot("%s-%s" % (tag, key.replace("_", "-").lower()), fv,
                              {"subject": "%s %s (emissive debug view)" % (hero, mat)})
        put(h["debug"])
        fr["dbg"] = sc.shot(tag + "-debugclass", fv, {"subject": "%s DebugView 1 (class mask)" % hero})
        sc.set([{"label": L_FIG, "visible": False}])
        time.sleep(4.0)
        fr["plate"] = sc.shot(tag + "-plate", fv, {"subject": "plate (figure hidden)"})
        sc.console("ShowFlag.Bloom 2")
        sc.set([{"label": L_FIG, "visible": True}])
        per, summ, checks = analyse_hero_view(fr, calib)
        hv["views"][vname] = {"classes": per, "summary": summ, "checks": checks}
        tiles = [fr["n_a"], fr["P1"], fr["P2"], fr["w"]]
        sheet = Image.new("RGB", (4 * 640, 600 + 50), (12, 12, 12))
        d = ImageDraw.Draw(sheet)
        d.text((10, 10), "%s H2LD %s · Neutral | P1 #E8C06A | P2 #5A7F9F | вес красителя (DebugView 10) · "
                         "M_UM_Figure_v2.1 UseTeamAccent · редактор, Cobble, High · диагностика" % (hero, vname),
               fill=(235, 210, 120), font=font(20))
        for k, t in enumerate(tiles):
            im = u8(t).crop((660, 60, 1260, 1040)).resize((358, 585))
            canvas = Image.new("RGB", (640, 600), (12, 12, 12))
            canvas.paste(im, ((640 - 358) // 2, 0))
            sheet.paste(canvas, (k * 640, 50))
        sp = sc.out / ("acc-sheet-%s-%s.jpg" % (hero.lower(), vname))
        sheet.save(sp, quality=90, optimize=True)
        hv["views"][vname]["sheet"] = sp.name
    meas["hero"] = {hero: hv}
    meas["hero_rule"] = HERO_RULE
    report["hero_ok"] = all(all(ch.values()) for v in hv["views"].values() for ch in v["checks"].values())


def cmd_accent(ue, out: Path, a, task) -> dict:
    phase = a.phase
    report, meas = {}, {}
    if phase == "summary":
        return summary(out, a)
    sc = Scene(ue, out, Path(a.frames).resolve(), phase, report)
    calib = None
    if phase.startswith("hero-"):
        wall_rep = Path(a.calib_from).resolve() if a.calib_from else out.parent / "wall" / "um-v2-accent-report.json"
        calib = json.loads(wall_rep.read_text(encoding="utf-8"))["measurements"]["debug_class_calibration_srgb"]
        report["calibration_from"] = str(wall_rep).replace("\\", "/")
    if phase in ("baseline", "wall"):
        spheres = [{"label": WALL_LABELS[i], "location": wall_pos(i), "scale": 0.2,
                    "material": "%s/MI_UM_v2_Test_Class%02d" % (TESTS, i)} for i in range(16)]
    elif phase == "gain":
        spheres = [{"label": ALB_LABELS[n], "location": pos_alb(n), "scale": 0.2,
                    "material": "%s/MI_UM_v2_Test_Alb_%s" % (TESTS, n)} for n in ALB_LAYOUT]
        spheres += [{"label": CHECK_LABELS[k], "location": CHECKERS[k][0], "scale": 0.2, "material": CHECK_MIS[k]}
                    for k in CHECKERS]
    else:
        spheres = []
    try:
        sc.open(spheres)
        if phase in ("baseline", "wall"):
            part_wall(sc, a, meas, report)
        elif phase == "gain":
            part_gain(sc, a, meas, report)
        else:
            part_hero(sc, a, meas, report, {"hero-merlin": "Merlin", "hero-medusa": "Medusa"}[phase], calib)
        report["measurements"] = meas
    finally:
        sc.close()
    return report


def summary(out: Path, a) -> dict:
    """Merge the part reports (sibling folders of <report>) into one summary."""
    root = out.parent
    parts = {}
    for p in PHASES[:-1]:
        f = root / p / "um-v2-accent-report.json"
        if f.is_file():
            parts[p] = json.loads(f.read_text(encoding="utf-8"))
    res = {"parts": {p: {"report": "../%s/um-v2-accent-report.json" % p, "started_at": r.get("started_at"),
                         "finished_at": r.get("finished_at"), "editor_lock": r.get("editor_lock"),
                         "review_level_lost": r.get("review_level_lost"), "restored_level": r.get("restored_level"),
                         "restored_level_dirty": r.get("restored_level_dirty")} for p, r in parts.items()}}
    ok = {}
    for p, r in parts.items():
        for k, v in r.items():
            if k.endswith("_ok"):
                ok["%s.%s" % (p, k)] = v
    res["checks"] = ok
    res["all_ok"] = bool(ok) and all(ok.values()) and all(p in parts for p in PHASES[:-1])
    res["missing_parts"] = [p for p in PHASES[:-1] if p not in parts]
    w = parts.get("wall", {}).get("measurements", {})
    res["legacy_regression_vs_v20"] = w.get("legacy_regression_vs_v20")
    res["dye_check_accent"] = w.get("dye_check_accent")
    res["gain_rule"] = parts.get("gain", {}).get("measurements", {}).get("gain_rule")
    res["heroes"] = {}
    for p in ("hero-merlin", "hero-medusa"):
        hm = parts.get(p, {}).get("measurements", {}).get("hero", {})
        for hero, hv in hm.items():
            res["heroes"][hero] = {"TeamDyeGain": hv["TeamDyeGain"], "TeamDyeCeiling": hv["TeamDyeCeiling"],
                                   "effective_gain": hv["effective_gain"],
                                   "views": {vn: {"summary": v["summary"], "checks": v["checks"], "sheet": v["sheet"]}
                                             for vn, v in hv["views"].items()}}
    return res
