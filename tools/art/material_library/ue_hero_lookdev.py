"""Hero look-dev on M_UM_Figure_v2 in the LIVE UnrealEditor: hero LUT builds, review frames, zone measurements (LD wave).

    # hero LUT (16 x 16 RGBA16F DDS, build_ue_inputs.py layout) from an overrides JSON, written OUTSIDE the shared
    # art/material-library/v2-ue folder (the hero's UE look-dev run keeps its own iterations)
    python tools/art/material_library/ue_hero_lookdev.py lut --overrides <json> --out <dds>

    # review of an imported hero (skeletal-adopt run with the M_UM_Figure_v2 MIs): frames on the Cobble light (High,
    # screen percentage 100) + MatID zone masks (debug MI) + concept-vs-UE zone statistics + sheets
    python tools/art/material_library/ue_hero_lookdev.py review --config <review json> --out <dir> --tag i1

    # zone statistics again from the frames of an earlier review (no editor)
    python tools/art/material_library/ue_hero_lookdev.py measure --config <review json> --out <dir>

Review config (JSON): {"hero", "run_dir" (skeletal-adopt run), "concept": {"front"|"side"|"back": png},
"concept_zones": <ld measure-report.json> (concept medians per class, pooled over the three concept views),
"variants": {"neutral"|"Blue"|"Red"|"debug": MI package}, "base_mi": {variant: MI package}, "zones": [class ids],
"key_zones": [...] (exposure anchor: geometric mean over these), "tolerance": {"luma_ratio", "hue_deg", "sat"},
"legacy_render_gate": {...}, "previous": [{"label", "frames_dir"}] (older UE frames for the sheets)}.

The editor flow is the one of tools/tripo-pipeline/review/h2_ue_review.py (P1.7 Cobble control level, light profile
cobble-probe applied in memory, sg.* = 2, overlays off, temporary actors, previous level restored, nothing saved).
Frames are EDITOR frames (editor-mcp-viewport): diagnostics, not K1/K2 acceptance, no RENDER fingerprint.
"""
from __future__ import annotations

import argparse
import base64
import colorsys
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
REVIEW = REPO / "tools" / "tripo-pipeline" / "review"
sys.path.insert(0, str(REVIEW))
sys.path.insert(0, str(HERE))

SCHEMA = "unmatched.um-v2-hero-lookdev/1"
LEVEL = "/Game/ArtTests/P17ControlScene/L_P17ControlScene"
PROFILES_JSON = REPO / "unreal/Unmatched/Config/ArtBoards/S08ArtBoardProfiles.json"
LIGHT_PROFILE = "cobble-probe"
KEY_LABEL = "ART005 cool scene key - proposed"
FILL_LABEL = "ART005 neutral readability fill - review only"
EXPOSURE_LABEL = "P17 exposure EV100 1.3 - fixed"
KEY_ROTATION = [-55.0, 30.0, 0.0]  # editor-probe rotation (h2_ue_review.py KEY_ROTATION_NOTE)
PREFIX = "LDue "
L_FIG, L_BASE, L_SKY, L_CAM = (PREFIX + "figure - temporary", PREFIX + "base - temporary", PREFIX + "sky - temporary",
                               PREFIX + "camera - temporary")
CELL = [0.0, 50.0, 0.0]
SG = ("sg.ViewDistanceQuality", "sg.AntiAliasingQuality", "sg.ShadowQuality", "sg.GlobalIlluminationQuality",
      "sg.ReflectionQuality", "sg.PostProcessQuality", "sg.TextureQuality", "sg.EffectsQuality", "sg.FoliageQuality",
      "sg.ShadingQuality")
SHOW_FLAGS_OFF = ("Grid", "BillboardSprites", "Volumes")
NOANN = {"gridSpacing": 0, "gridExtent": 0, "gridHeight": 0, "maxLabelDistance": 0, "classFilter": None, "maxLabels": 0}
FOV = 35.0  # the level viewport renders ~35 deg horizontal whatever the camera FOV (h2_ue_review.py NARROW note)
DIST, CAM_Z = 200.0, 29.0
PITCH_K2, K2_5X, K2_1P6, FOCUS_Z = -55.0, 386.0, 1207.0, 28.0
LUMA = np.array([0.2126, 0.7152, 0.0722])


def now() -> str:
    return dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat()


def sha(path: Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def rel(path: Path) -> str:
    p = Path(path).resolve()
    try:
        return p.relative_to(REPO).as_posix()
    except ValueError:  # outputs outside the checkout (e.g. a scratch LUT rebuild) are reported by absolute path
        return p.as_posix()


def write_json(path: Path, data) -> None:
    Path(path).write_text(json.dumps(data, indent=1, sort_keys=True, ensure_ascii=False) + "\n", encoding="utf-8",
                          newline="\n")


# ------------------------------------------------------------------ LUT
def cmd_lut(a) -> dict:
    import build_ue_inputs as b
    presets = b.load_presets()
    cols = b.class_columns(presets)
    ov_path = Path(a.overrides).resolve()
    overrides = json.loads(ov_path.read_text(encoding="utf-8"))
    applied = b.apply_overrides(cols, overrides, presets)
    out = Path(a.out).resolve()
    b.write_dds(out, [b.lut_array(cols).astype(np.float16)], "R16G16B16A16_FLOAT")
    rep = {"schema": "unmatched.um-v2-hero-lut/1", "tool": "tools/art/material_library/ue_hero_lookdev.py lut",
           "builder": "tools/art/material_library/build_ue_inputs.py %s (load_presets, class_columns, apply_overrides, "
                      "lut_array, write_dds)" % b.GENERATOR_VERSION,
           "presets_sha256": b.sha(b.PRESETS), "overrides": rel(ov_path), "overrides_sha256": sha(ov_path),
           "dds": rel(out), "dds_sha256": sha(out), "applied": applied,
           "columns": {str(i): {k: (round(v, 6) if isinstance(v, float) else v) for k, v in sorted(cols[i].items())}
                       for i in sorted(cols) if any(o["class"] == cols[i]["classId"] for o in applied)}}
    write_json(out.with_suffix(".report.json"), rep)
    print(rep["dds"], rep["dds_sha256"])
    return rep


# ------------------------------------------------------------------ colour helpers
def lin(c):
    c = np.clip(c, 0.0, 1.0)
    return np.where(c <= 0.04045, c / 12.92, ((c + 0.055) / 1.055) ** 2.4)


def rgb_to_hsv(rgb):
    """rgb in [0, 1] (..., 3) -> h deg, s, v (vectorised)."""
    r, g, b = rgb[..., 0], rgb[..., 1], rgb[..., 2]
    mx, mn = rgb.max(-1), rgb.min(-1)
    d = mx - mn
    h = np.zeros_like(mx)
    nz = d > 1e-9
    rm = nz & (mx == r)
    gm = nz & (mx == g) & ~rm
    bm = nz & ~rm & ~gm
    h[rm] = ((g - b)[rm] / d[rm]) % 6.0
    h[gm] = (b - r)[gm] / d[gm] + 2.0
    h[bm] = (r - g)[bm] / d[bm] + 4.0
    h = h * 60.0
    s = np.where(mx > 1e-9, d / np.maximum(mx, 1e-9), 0.0)
    return h, s, mx


def hsv_stats(rgb8):
    """Same definition as the Blender ld_measure (lookdev.hsv_stats): per-channel median of sRGB, then HSV and Y of
    the median."""
    x = rgb8.astype(np.float32) / 255.0
    med = np.median(x, 0)
    h, s, v = rgb_to_hsv(med[None, :])
    y = float((lin(med) * LUMA).sum())
    return {"median_srgb": [round(float(c) * 255, 1) for c in med], "luma_Y_linear": round(y, 4),
            "hue_deg": round(float(h[0]), 1), "sat": round(float(s[0]), 3), "value": round(float(v[0]), 3)}


def gate(rgb8, g):
    if not g:
        return np.ones(len(rgb8), bool)
    h, s, v = rgb_to_hsv(rgb8.astype(np.float32) / 255.0)
    ok = np.ones(len(rgb8), bool)
    if "hue_deg" in g:
        hm = np.zeros(len(rgb8), bool)
        for lo, hi in g["hue_deg"]:
            hm |= (h >= lo) & (h <= hi)
        ok &= hm
    for key, arr, op in (("s_min", s, np.greater_equal), ("s_max", s, np.less_equal),
                         ("v_min", v, np.greater_equal), ("v_max", v, np.less_equal)):
        if key in g:
            ok &= op(arr, g[key])
    return ok


def debug_class_colour(i: int):
    """Linear emissive of DebugView 1 (um_v2_core.hlsl): lerp(1, hue(frac(i * 0.618034)), 0.75) * 0.95; class 0 grey."""
    if i == 0:
        return np.array([0.02, 0.02, 0.02])
    h = (i * 0.618034) % 1.0
    hue = np.clip(np.abs(((h + np.array([0.0, 2.0 / 3.0, 1.0 / 3.0])) % 1.0) * 6.0 - 3.0) - 1.0, 0.0, 1.0)
    return (1.0 + (hue - 1.0) * 0.75) * 0.95


def decode_debug(debug8, plate8, classes, calib=None):
    """Class per pixel from a DebugView-1 frame and the plate (same view, figure hidden): figure = pixels that changed
    against the plate; class = nearest calibrated colour (calib: class -> sRGB8 measured on the frame; default: the hue
    of the debug colour). Class 0 (legacy, dark grey emissive, black surface) = dark changed pixels."""
    d = debug8.astype(np.float32)
    changed = np.abs(d - plate8.astype(np.float32)).max(-1) > 18.0
    h, s, v = rgb_to_hsv(d / 255.0)
    cls = np.full(d.shape[:2], -1, np.int16)
    lib = [c for c in classes if c != 0]
    if calib:
        ref = np.array([calib[str(c)] for c in lib], np.float32)
        dist = np.linalg.norm(d[..., None, :] - ref[None, None], axis=-1)
        k = dist.argmin(-1)
        ok = dist.min(-1) < 40.0
        cls[changed & ok] = np.array(lib, np.int16)[k[changed & ok]]
    else:
        hues = []
        for c in lib:
            col = debug_class_colour(c)
            hh, _, _ = rgb_to_hsv(col[None, :])
            hues.append(float(hh[0]))
        hues = np.array(hues)
        dh = np.abs(((h[..., None] - hues[None, None]) + 180.0) % 360.0 - 180.0)
        k = dh.argmin(-1)
        ok = (s > 0.12) & (v > 0.25) & (dh.min(-1) < 14.0)
        cls[changed & ok] = np.array(lib, np.int16)[k[changed & ok]]
    if 0 in classes:
        cls[changed & (v < 0.10) & (cls < 0)] = 0
    return cls, changed


def erode(mask, it=1):
    m = mask.copy()
    for _ in range(it):
        mm = m.copy()
        mm[1:, :] &= m[:-1, :]
        mm[:-1, :] &= m[1:, :]
        mm[:, 1:] &= m[:, :-1]
        mm[:, :-1] &= m[:, 1:]
        m = mm
    return m


def font(size):
    for f in ("C:/Windows/Fonts/segoeui.ttf", "C:/Windows/Fonts/arial.ttf"):
        try:
            return ImageFont.truetype(f, size)
        except OSError:
            continue
    return ImageFont.load_default()


# ------------------------------------------------------------------ views
def views():
    """Figure at yaw 90 faces +Y (a UM_FBX_v1 mesh faces +X); its weapon side (local -Y) is then world +X. The concept
    side view looks at the bow side with the face to the left of the frame -> the camera at +X looking -X."""
    x, y = CELL[0], CELL[1]
    p = math.radians(-PITCH_K2)
    fz = CELL[2] + FOCUS_Z

    def k2(dist):
        return [x, y + dist * math.cos(p), fz + dist * math.sin(p)], [PITCH_K2, -90.0, 0.0]

    return {
        "front": {"eye": [x, y + DIST, CAM_Z], "rot": [0.0, -90.0, 0.0], "yaw": 90.0, "kind": "front, FOV 35, 200 uu"},
        "side": {"eye": [x + DIST, y, CAM_Z], "rot": [0.0, 180.0, 0.0], "yaw": 90.0,
                 "kind": "side (bow side, face to the left as the concept), FOV 35, 200 uu"},
        "back": {"eye": [x, y - DIST, CAM_Z], "rot": [0.0, 90.0, 0.0], "yaw": 90.0, "kind": "back, FOV 35, 200 uu"},
        "k2-5x": dict(zip(("eye", "rot"), k2(K2_5X)), yaw=90.0, kind="game camera K2 5x (386 uu, pitch -55)"),
        "k2-1p6": dict(zip(("eye", "rot"), k2(K2_1P6)), yaw=90.0, kind="game camera K2 1.6x (1207 uu, pitch -55)"),
    }


ORTHO = ("front", "side", "back")


class Session:
    def __init__(self, ue, out: Path, tag: str, hero: str):
        self.ue, self.out, self.tag, self.hero = ue, out, tag, hero
        self.frames = {}

    def task(self, script, op, timeout=600, **kw):
        path = Path(script) if Path(script).is_absolute() else REVIEW / "ue_py" / script
        return self.ue.run_task(str(path), str(self.out / "_task.json"), timeout=timeout, op=op, **kw)

    def grab(self, xform):
        res = self.ue.call("app", "CaptureViewport", {"captureTransform": xform, "annotations": NOANN, "bShowUI": False},
                           record=False)
        v = res["value"] if isinstance(res, dict) and "value" in res else res
        img = v["image"] if isinstance(v, dict) and "image" in v else res["images"][0]
        return Image.open(io.BytesIO(base64.b64decode(img["data"]))).convert("RGB")

    def shot(self, name, view, meta, grabs=4):
        self.task("control_scene_ue.py", "camera", label=L_CAM, location=view["eye"], rotation=view["rot"], fov=FOV)
        xform = {"location": dict(zip("xyz", view["eye"])), "rotation": dict(zip(("pitch", "yaw", "roll"), view["rot"])),
                 "scale": {"x": 1, "y": 1, "z": 1}}
        time.sleep(0.5)
        prev, settle = None, []
        for attempt in range(grabs):
            im = self.grab(xform)
            if prev is not None:
                settle.append(round(float(np.abs(np.asarray(im, np.int16) - np.asarray(prev, np.int16)).mean()), 4))
            prev = im
            if attempt < grabs - 1:
                time.sleep(0.7)
        w, h = im.size
        ch = round(w * 9 / 16)
        box = (0, (h - ch) // 2, w, (h - ch) // 2 + ch) if ch <= h else ((w - round(h * 16 / 9)) // 2, 0,
                                                                          (w + round(h * 16 / 9)) // 2, h)
        frame = im.crop(box).resize((1920, 1080), Image.LANCZOS)
        fname = "%s-%s-%s.png" % (self.hero.lower(), self.tag, name)
        path = self.out / "frames" / fname
        path.parent.mkdir(parents=True, exist_ok=True)
        frame.save(path, optimize=False, compress_level=6)
        digest = sha(path)
        info = {"view": {k: view[k] for k in ("eye", "rot", "yaw", "kind")}, "viewport_px": [w, h], "crop_px": list(box),
                "output_px": [1920, 1080], "settle_mean_abs_diff": settle, "fov": FOV, **meta}
        side = {"schema": "unmatched.evidence-frame/1", "class": "editor-mcp-viewport", "frameSha256": digest,
                "frame": fname, "label": "EDITOR frame (LD %s look-dev on M_UM_Figure_v2, Cobble light, High, SP 100), "
                                         "diagnostic; not K1/K2 acceptance, no RENDER fingerprint" % self.hero,
                "run_tag": self.tag, **info}
        write_json(path.with_name(path.stem + ".evidence.json"), side)
        self.frames[name] = dict(info, file=fname, sha256=digest)
        print(" ", fname, digest[:12], "settle", settle, flush=True)
        return frame


def cvar_value(ue, name):
    raw = ue.call("app", "SearchCVars", {"name": name}, record=False)
    data = json.loads(raw) if isinstance(raw, str) else raw
    return (data.get(name) or {}).get("value")


def cmd_review(a, cfg) -> dict:
    from ue_live import Ue
    run = REPO / cfg["run_dir"]
    ue_rep = json.loads((run / "reports/ue-import-report.json").read_text(encoding="utf-8"))
    if not ue_rep.get("passed"):
        raise SystemExit("the run's ue-import did not pass")
    names = ue_rep["destination"]["assets"]
    light = json.loads(PROFILES_JSON.read_text(encoding="utf-8"))["lightProfiles"][LIGHT_PROFILE]
    out = Path(a.out).resolve()
    out.mkdir(parents=True, exist_ok=True)
    ue = Ue()
    ss = Session(ue, out, a.tag, cfg["hero"])
    original = ue.call("scene", "get_current_level", record=False)
    if ue.call("asset", "is_dirty", {"asset_path": original}, record=False):
        raise SystemExit("open level %s has unsaved changes; refusing to switch levels" % original)
    if original.split(".")[0] == LEVEL:
        raise SystemExit("the review level is open (another review running?); refusing")
    if ue.call("asset", "is_dirty", {"asset_path": LEVEL}, record=False):
        raise SystemExit("the review level has unsaved changes in memory (someone else is using it)")
    sg_before = {n: cvar_value(ue, n) for n in SG}
    report = {"schema": SCHEMA, "tag": a.tag, "started_at": now(), "tool": "tools/art/material_library/ue_hero_lookdev.py",
              "kind": "EDITOR review frames (live UnrealEditor via MCP): not packaged, no HUD, no RENDER fingerprint, "
                      "not K1/K2 acceptance", "config": cfg, "assets": names, "original_level": original,
              "review_level": LEVEL, "cell": CELL,
              "light_profile": {"source": "%s lightProfiles.%s" % (rel(PROFILES_JSON), LIGHT_PROFILE), "data": light},
              "key_rotation_pitch_yaw_roll": KEY_ROTATION, "scalability_before": sg_before, "console": []}
    temp = [L_FIG, L_BASE, L_SKY, L_CAM]
    variants = cfg["variants"]
    try:
        ue.call("scene", "load_level", {"level_path": LEVEL})
        time.sleep(3.0)
        report["setup"] = ss.task("h2_review_ue.py", "setup", level=LEVEL, hide_label_prefixes=["P17 "],
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
                                          "location": CELL, "yaw": 90.0},
                                  base={"label": L_BASE, "kind": "static", "asset": names["base"], "location": CELL,
                                        "yaw": 90.0})
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
        time.sleep(6.0)
        vs = views()
        # warm-up (shader compile of the v2 permutations, texture streaming)
        ss.task("control_scene_ue.py", "set", changes=[{"label": L_FIG, "materials": {"0": variants["neutral"]}}])
        v0 = vs["front"]
        ss.task("control_scene_ue.py", "camera", label=L_CAM, location=v0["eye"], rotation=v0["rot"], fov=FOV)
        xform = {"location": dict(zip("xyz", v0["eye"])), "rotation": dict(zip(("pitch", "yaw", "roll"), v0["rot"])),
                 "scale": {"x": 1, "y": 1, "z": 1}}
        prev, warm = None, []
        for _ in range(40):
            im = ss.grab(xform)
            if prev is not None:
                warm.append(round(float(np.abs(np.asarray(im, np.int16) - np.asarray(prev, np.int16)).mean()), 4))
                if warm[-1] < 0.05 and len(warm) >= 3:
                    break
            prev = im
            time.sleep(1.5)
        report["warmup_mean_abs_diff"] = warm
        plan = cfg.get("shots") or {"neutral": list(vs), "Blue": list(vs), "Red": list(vs), "debug": list(ORTHO),
                                    "plate": list(ORTHO)}
        for variant, vnames in plan.items():
            if variant == "reading":
                continue
            if variant == "plate":
                ss.task("control_scene_ue.py", "set", changes=[{"label": L_FIG, "visible": False},
                                                              {"label": L_BASE, "visible": False}])
            else:
                changes = [{"label": L_FIG, "visible": True, "materials": {"0": variants[variant]}},
                           {"label": L_BASE, "visible": True}]
                if cfg.get("base_mi", {}).get(variant):
                    changes[1]["materials"] = {"0": cfg["base_mi"][variant]}
                ss.task("control_scene_ue.py", "set", changes=changes)
            time.sleep(2.5)
            for vn in vnames:
                ss.shot("%s-%s" % (vn, variant.lower()), vs[vn],
                        {"subject": "%s (%s)" % (cfg["hero"], names["skeletal"]), "view_name": vn, "variant": variant,
                         "material": variants.get(variant)})
        ss.task("control_scene_ue.py", "set", changes=[{"label": L_FIG, "visible": True}, {"label": L_BASE, "visible": True}])
        # reading frames (LDV-11): the same light and cameras, exposure bias of the fixed-exposure volume lowered so the
        # figure sits where the concept sits on the tone curve (the Cobble exposure pushes skin into the shoulder)
        bias = float(cfg.get("reading_bias_ev", -1.5))
        if plan.get("reading", list(ORTHO) + ["k2-5x"]):
            report["exposure_reading"] = ss.task(str(HERE / "ue" / "um_v2_scene_ue.py"), "exposure", label=EXPOSURE_LABEL,
                                                 bias=bias)
            ss.task("control_scene_ue.py", "set", changes=[{"label": L_FIG, "materials": {"0": variants["neutral"]}},
                                                          {"label": L_BASE, "materials": {"0": cfg["base_mi"]["neutral"]}}])
            time.sleep(3.0)
            for vn in plan.get("reading", list(ORTHO) + ["k2-5x"]):
                ss.shot("%s-reading" % vn, vs[vn], {"subject": "%s (%s)" % (cfg["hero"], names["skeletal"]),
                                                    "view_name": vn, "variant": "reading", "material": variants["neutral"],
                                                    "exposure": "EV100 1.3 fixed + bias %+.1f (reading frame)" % bias})
            report["exposure_restored"] = ss.task(str(HERE / "ue" / "um_v2_scene_ue.py"), "exposure",
                                                  label=EXPOSURE_LABEL, bias=0.0)
    finally:
        try:
            report["cleanup"] = ss.task("control_scene_ue.py", "cleanup", labels=temp)
        except Exception as exc:  # noqa: BLE001
            report["cleanup_error"] = str(exc)
        try:
            for n, v in sg_before.items():
                if v is not None:
                    ue.console("%s %s" % (n, v))
                    report["console"].append("%s %s" % (n, v))
            for flag in SHOW_FLAGS_OFF:
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
        report["frames"] = ss.frames
        report["finished_at"] = now()
        tmp = out / "_task.json"
        if tmp.exists():
            tmp.unlink()
        write_json(out / ("review-%s.json" % a.tag), report)
        print("restored:", report["restored_level"], "dirty:", report["restored_level_dirty"])
    return report


# ------------------------------------------------------------------ measure
def load_frame(out: Path, hero: str, tag: str, name: str):
    p = out / "frames" / ("%s-%s-%s.png" % (hero.lower(), tag, name))
    return np.asarray(Image.open(p).convert("RGB")) if p.is_file() else None


def cmd_measure(a, cfg) -> dict:
    out = Path(a.out).resolve()
    hero, tag = cfg["hero"], a.tag
    presets = json.loads((REPO / "docs/art-pipeline/material-library/um-material-presets-v1.json").read_text(encoding="utf-8"))
    names = {c["index"]: c["id"] for c in presets["classes"]}
    ids = {v: k for k, v in names.items()}
    zones_cfg = cfg["zones"]
    classes = sorted({ids[z] for z in zones_cfg} | {0})
    concept = json.loads((REPO / cfg["concept_zones"]).read_text(encoding="utf-8"))["zones"]
    gates = cfg.get("render_gates") or {}
    calib = cfg.get("debug_calibration")
    masks, pooled, per_view = {}, {}, {}
    variants = [v for v in cfg["variants"] if v not in ("debug",)] + ["reading"]
    for view in ORTHO:
        dbg, plate = load_frame(out, hero, tag, "%s-debug" % view), load_frame(out, hero, tag, "%s-plate" % view)
        if dbg is None or plate is None:
            continue
        cls, changed = decode_debug(dbg, plate, classes, calib)
        masks[view] = cls
        # class map image (evidence)
        vis = np.zeros(dbg.shape, np.uint8)
        for c in classes:
            col = (np.clip(debug_class_colour(c), 0, 1) ** (1 / 2.2) * 255).astype(np.uint8) if c else np.array([90, 90, 90], np.uint8)
            vis[cls == c] = col
        Image.fromarray(vis).save(out / "frames" / ("%s-%s-%s-classmap.png" % (hero.lower(), tag, view)))
        per_view[view] = {}
        for zone in zones_cfg:
            c = ids[zone]
            m = erode(cls == c, 1)
            per_view[view][zone] = {"pixels": int(m.sum())}
            for var in variants:
                beauty = load_frame(out, hero, tag, "%s-%s" % (view, var.lower()))
                if beauty is None:
                    continue
                px = beauty[m]
                if zone in gates and len(px):
                    px = px[gate(px, gates[zone])]
                if len(px) < int(cfg.get("min_px", 150)):
                    continue
                per_view[view][zone][var] = hsv_stats(px)
                pooled.setdefault((zone, var), []).append(px)
    zones = {}
    for (zone, var), arrs in sorted(pooled.items()):
        px = np.concatenate(arrs, 0)
        zones.setdefault(zone, {"concept": concept.get(zone, {}).get("concept")})[var] = dict(hsv_stats(px), pixels=int(len(px)))
    tol = cfg["tolerance"]
    res = {"schema": "unmatched.um-v2-hero-lookdev-measure/1", "tag": tag, "hero": hero, "zones": zones,
           "per_view": per_view, "tolerance": tol,
           "method": "UE zones = MatID classes of the debug MI (DebugView 1) decoded on the same camera against a plate "
                     "frame (figure hidden), eroded 1 px; legacy_bake gated by hue on the beauty frame (snakes); "
                     "median sRGB per channel over the pixels of the three concept views (front/side/back) pooled, "
                     "HSV and Y of the median (as ld_measure); concept = ld measure-report zones.*.concept "
                     "(class mask + colour gates on the concept, same definition)"}
    for var in variants:
        key = [z for z in cfg["key_zones"] if var in zones.get(z, {}) and zones[z].get("concept")]
        if not key:
            continue
        lr = [math.log(zones[z]["concept"]["luma_Y_linear"] / max(zones[z][var]["luma_Y_linear"], 1e-5)) for z in key]
        k = math.exp(sum(lr) / len(lr))
        anchor = cfg.get("anchor_zone", "linen")
        k_anchor = (zones[anchor]["concept"]["luma_Y_linear"] / max(zones[anchor][var]["luma_Y_linear"], 1e-5)
                    if anchor in zones and var in zones[anchor] else None)
        ev = {"k_concept_over_ue_geomean_key_zones": round(k, 4), "key_zones": key,
              "k_anchor_%s" % anchor: round(k_anchor, 4) if k_anchor else None, "deltas": {}}
        for z, zz in zones.items():
            if var not in zz or not zz.get("concept"):
                continue
            c, u = zz["concept"], zz[var]
            yr = u["luma_Y_linear"] / max(c["luma_Y_linear"] / k, 1e-6)
            yr_abs = u["luma_Y_linear"] / max(c["luma_Y_linear"], 1e-6)
            dh = ((u["hue_deg"] - c["hue_deg"] + 180.0) % 360.0) - 180.0
            ds = u["sat"] - c["sat"]
            ok = {"luma": abs(yr - 1.0) <= tol["luma_ratio"], "hue": abs(dh) <= tol["hue_deg"], "sat": abs(ds) <= tol["sat"]}
            ev["deltas"][z] = {"Y_ratio_exposure_normalised": round(yr, 3), "Y_ratio_absolute": round(yr_abs, 3),
                               "Y_ratio_anchor": round(u["luma_Y_linear"] / max(c["luma_Y_linear"] / k_anchor, 1e-6), 3)
                               if k_anchor else None,
                               "dHue_deg": round(dh, 1), "dSat": round(ds, 3), "within": ok,
                               "all_within": all(ok.values()), "key_zone": z in cfg.get("tolerance_zones", [])}
        res.setdefault("exposure", {})[var] = ev
    write_json(out / ("measure-%s.json" % tag), res)
    # table to stdout
    for var, ev in (res.get("exposure") or {}).items():
        print("==", var, "k", ev["k_concept_over_ue_geomean_key_zones"])
        for z, d in ev["deltas"].items():
            u = zones[z][var]
            print("  %-15s Y %.4f ratio %.3f (abs %.3f) hue %5.1f d %5.1f sat %.3f d %+.3f %s" % (
                z, u["luma_Y_linear"], d["Y_ratio_exposure_normalised"], d["Y_ratio_absolute"], u["hue_deg"],
                d["dHue_deg"], u["sat"], d["dSat"], "OK" if d["all_within"] else "--"))
    return res


# ------------------------------------------------------------------ sheets
def crop_portrait(img: Image.Image, aspect: float, zoom: float = 1.0) -> Image.Image:
    w, h = img.size
    ch = h / zoom
    cw = ch * aspect
    return img.crop((int((w - cw) / 2), int((h - ch) / 2), int((w + cw) / 2), int((h + ch) / 2)))


def cmd_sheets(a, cfg) -> dict:
    out = Path(a.out).resolve()
    hero, tag = cfg["hero"], a.tag
    res = {}
    cw, chh, head, lab = 520, 784, 60, 34
    concept = {v: Image.open(REPO / p).convert("RGB") for v, p in cfg["concept"].items()}
    aspect = concept["front"].width / concept["front"].height
    zoom = float(cfg.get("sheet_zoom", 1.0))
    cols = [("концепт", None)] + [(p["label"], p) for p in cfg.get("previous") or []] + \
        [("UE H2LD %s нейтр." % tag, {"tag": tag, "variant": "neutral"}),
         ("UE H2LD %s нейтр. %+.1f EV" % (tag, float(cfg.get("reading_bias_ev", -1.5))), {"tag": tag, "variant": "reading"}),
         ("UE H2LD %s Blue" % tag, {"tag": tag, "variant": "blue"}),
         ("UE H2LD %s Red" % tag, {"tag": tag, "variant": "red"})]
    W, H = cw * len(cols), head + (lab + chh) * 3
    sheet = Image.new("RGB", (W, H), (14, 14, 14))
    d = ImageDraw.Draw(sheet)
    d.text((10, 12), "%s: концепт | UE (живой редактор, DX12/SM6 + Lumen, High, SP 100, свет Cobble) · кадры диагностики, "
                     "не приёмка" % hero, fill=(235, 210, 120), font=font(26))
    for r, view in enumerate(ORTHO):
        y = head + r * (lab + chh)
        for c, (name, spec) in enumerate(cols):
            d.text((c * cw + 8, y + 4), "%s · %s" % (name, view), fill=(220, 220, 220), font=font(20))
            if spec is None:
                im = concept[view]
            else:
                p = Path(spec.get("frames_dir") or (out / "frames"))
                p = (REPO / p) if not p.is_absolute() else p
                f = p / ("%s-%s-%s-%s.png" % (hero.lower(), spec["tag"], view, spec["variant"]))
                if not f.is_file():
                    d.text((c * cw + 20, y + lab + 20), "нет кадра", fill=(200, 80, 80), font=font(20))
                    continue
                im = crop_portrait(Image.open(f).convert("RGB"), aspect, zoom)
            im = im.copy()
            im.thumbnail((cw, chh), Image.LANCZOS)
            sheet.paste(im, (c * cw + (cw - im.width) // 2, y + lab + (chh - im.height) // 2))
    path = out / ("%s-lookdev-sheet-%s.jpg" % (hero.lower(), tag))
    sheet.save(path, quality=88, optimize=True)
    res[path.name] = sha(path)
    # K2 sheet
    k2 = [("k2-5x", "K2 5x"), ("k2-1p6", "K2 1.6x")]
    cw2, ch2 = 640, 360
    sheet2 = Image.new("RGB", (cw2 * 3, head + (lab + ch2) * 2), (14, 14, 14))
    d2 = ImageDraw.Draw(sheet2)
    d2.text((10, 12), "%s %s: игровая камера K2 (редактор, Cobble, High) · нейтр. | Blue | Red" % (hero, tag),
            fill=(235, 210, 120), font=font(24))
    for r, (vn, label) in enumerate(k2):
        y = head + r * (lab + ch2)
        for c, var in enumerate(("neutral", "blue", "red")):
            f = out / "frames" / ("%s-%s-%s-%s.png" % (hero.lower(), tag, vn, var))
            d2.text((c * cw2 + 8, y + 4), "%s · %s" % (label, var), fill=(220, 220, 220), font=font(20))
            if f.is_file():
                im = Image.open(f).convert("RGB")
                if vn == "k2-1p6":  # the figure is small: centre crop 2x
                    w, h = im.size
                    im = im.crop((w // 4, h // 4, 3 * w // 4, 3 * h // 4))
                im.thumbnail((cw2, ch2), Image.LANCZOS)
                sheet2.paste(im, (c * cw2, y + lab))
    p2 = out / ("%s-lookdev-k2-%s.jpg" % (hero.lower(), tag))
    sheet2.save(p2, quality=88, optimize=True)
    res[p2.name] = sha(p2)
    print(res)
    return res


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("command", choices=["lut", "review", "measure", "sheets"])
    ap.add_argument("--overrides")
    ap.add_argument("--out", required=True)
    ap.add_argument("--config")
    ap.add_argument("--tag", default="i1")
    a = ap.parse_args()
    if a.command == "lut":
        cmd_lut(a)
        return 0
    cfg = json.loads(Path(a.config).read_text(encoding="utf-8"))
    if a.command == "review":
        cmd_review(a, cfg)
        cmd_measure(a, cfg)
        cmd_sheets(a, cfg)
    elif a.command == "measure":
        cmd_measure(a, cfg)
    else:
        cmd_sheets(a, cfg)
    return 0


if __name__ == "__main__":
    sys.exit(main())
