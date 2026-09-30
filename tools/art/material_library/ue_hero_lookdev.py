"""Hero look-dev on M_UM_Figure_v2 in the LIVE UnrealEditor: hero LUT builds, review frames, zone measurements (LD wave).

    # hero LUT (16 x 16 RGBA16F DDS, build_ue_inputs.py layout) from an overrides JSON, written OUTSIDE the shared
    # art/material-library/v2-ue folder (the hero's UE look-dev run keeps its own iterations)
    python tools/art/material_library/ue_hero_lookdev.py lut --overrides <json> --out <dds>

    # review of an imported hero (skeletal-adopt run with the M_UM_Figure_v2 MIs): frames on the Cobble light (High,
    # screen percentage 100) + MatID zone masks (debug MI) + concept-vs-UE zone statistics + sheets
    python tools/art/material_library/ue_hero_lookdev.py review --config <review json> --out <dir> --tag i1

    # zone statistics again from the frames of an earlier review (no editor)
    python tools/art/material_library/ue_hero_lookdev.py measure --config <review json> --out <dir>

    # concept medians per MatID class from the concept boxes of a look-dev profile (hero without a class-mask concept
    # measurement, e.g. Merlin: lookdev.concept_zones boxes + HSV filters, zones pooled by class) -> cfg concept_zones
    python tools/art/material_library/ue_hero_lookdev.py concept --config <review json> --out <dir>

    # read-back of the H2LD import (skeleton, bones, LOD/triangles/UV, slots, textures, MIs, duplicates, H2Anim clips
    # on the H2LD mesh) under the editor lock
    python tools/art/material_library/ue_hero_lookdev.py verify --config <review json> --out <dir> --tag <tag>

Review config (JSON): {"hero", "run_dir" (skeletal-adopt run), "concept": {"front"|"side"|"back": png},
"concept_zones": <ld measure-report.json> (concept medians per class, pooled over the three concept views),
"variants": {"neutral"|"Blue"|"Red"|"debug": MI package}, "base_mi": {variant: MI package}, "zones": [class ids],
"key_zones": [...] (exposure anchor: geometric mean over these), "tolerance": {"luma_ratio", "hue_deg", "sat"},
"legacy_render_gate": {...}, "previous": [{"label", "frames_dir"}] (older UE frames for the sheets)}.
Look-dev C (2026-09-30) keys, all optional: "zone_class" {zone: preset class id} (zones named apart from their MatID
class, e.g. two feather zones of one class, or horn_claw in the brass column), "decode_classes" [class ids] (every class
of the hero's MatID, for the debug-colour decode), "gate_on_variant" (render_gates evaluated once per view on that
variant's frame and the same pixels used for every variant, e.g. "neutral": a -1 EV or dyed frame then measures the
same pixels), "team_variants" [two variant names] (= "teams"; sheet columns), "sheet_label" (column label prefix,
default "UE H2LD"), tolerance "hue_min_sat" (no hue check below this concept saturation), "shots" (variant -> views).

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
def views(side_camera: str = "+X"):
    """Figure at yaw 90 faces +Y (a UM_FBX_v1 mesh faces +X); a weapon side on local -Y (Medusa's bow) is then world +X,
    one on local +Y (Merlin's staff) world -X. The concept side view looks at the weapon side: Medusa's face to the left
    of the frame -> camera at +X looking -X (side_camera "+X"); Merlin's face to the right -> camera at -X looking +X
    (side_camera "-X", look-dev C)."""
    x, y = CELL[0], CELL[1]
    p = math.radians(-PITCH_K2)
    fz = CELL[2] + FOCUS_Z

    def k2(dist):
        return [x, y + dist * math.cos(p), fz + dist * math.sin(p)], [PITCH_K2, -90.0, 0.0]

    return {
        "front": {"eye": [x, y + DIST, CAM_Z], "rot": [0.0, -90.0, 0.0], "yaw": 90.0, "kind": "front, FOV 35, 200 uu"},
        "side": ({"eye": [x + DIST, y, CAM_Z], "rot": [0.0, 180.0, 0.0], "yaw": 90.0,
                  "kind": "side (weapon side, face to the left as the concept), FOV 35, 200 uu"} if side_camera == "+X" else
                 {"eye": [x - DIST, y, CAM_Z], "rot": [0.0, 0.0, 0.0], "yaw": 90.0,
                  "kind": "side (weapon side, face to the right as the concept), FOV 35, 200 uu"}),
        "back": {"eye": [x, y - DIST, CAM_Z], "rot": [0.0, 90.0, 0.0], "yaw": 90.0, "kind": "back, FOV 35, 200 uu"},
        "k2-5x": dict(zip(("eye", "rot"), k2(K2_5X)), yaw=90.0, kind="game camera K2 5x (386 uu, pitch -55)"),
        "k2-1p6": dict(zip(("eye", "rot"), k2(K2_1P6)), yaw=90.0, kind="game camera K2 1.6x (1207 uu, pitch -55)"),
    }


ORTHO = ("front", "side", "back")


def teams_of(cfg) -> list:
    """Team variant names of a review config (look-dev C: ["P1", "P2"], the active C-11 palette; before: Blue/Red)."""
    return list(cfg.get("teams") or cfg.get("team_variants") or ["Blue", "Red"])


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
    """The whole editor part (level switch, temporary actors, frames, cleanup, previous level restored) runs as ONE step
    under the shared editor lock (ue_lock.py; owner from UE_LOCK_OWNER, look-dev C rule 2026-09-30)."""
    from ue_lock import ue_lock
    with ue_lock("ue_hero_lookdev review %s %s" % (cfg["hero"], a.tag)) as lock:
        rep = _cmd_review(a, cfg)
        rep["editor_lock"] = {k: v for k, v in lock.items() if k != "waits"}
    write_json(Path(a.out).resolve() / ("review-%s.json" % a.tag), rep)
    return rep


def _cmd_review(a, cfg) -> dict:
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
        vs = views(cfg.get("side_camera", "+X"))
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
        plan = cfg.get("shots") or dict({"neutral": list(vs)}, **{t: list(vs) for t in teams_of(cfg)},
                                        debug=list(ORTHO), plate=list(ORTHO))
        bloom_off = False
        for variant, vnames in plan.items():
            if variant == "reading":
                continue
            if variant in ("debug", "plate") and not bloom_off:
                # class colours are emissive: the bloom of bright dyed accents adds a haze in the team hue that the
                # class decoder would read as a leak (LDV-16); debug and plate frames are shot without bloom
                ue.console("ShowFlag.Bloom 0")
                report["console"].append("ShowFlag.Bloom 0")
                bloom_off = True
                time.sleep(1.0)
            elif variant not in ("debug", "plate") and bloom_off:
                ue.console("ShowFlag.Bloom 2")
                report["console"].append("ShowFlag.Bloom 2")
                bloom_off = False
                time.sleep(1.0)
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
        if bloom_off:
            ue.console("ShowFlag.Bloom 2")
            report["console"].append("ShowFlag.Bloom 2")
            time.sleep(1.0)
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
            for flag in SHOW_FLAGS_OFF + ("Bloom",):
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
        if cfg.get("restore_level") and report["restored_level"].split(".")[0] != cfg["restore_level"]:
            report["restore_level_mismatch"] = {"want": cfg["restore_level"], "got": report["restored_level"]}
    return report


# ------------------------------------------------------------------ concept (class medians from look-dev boxes)
def cmd_concept(a, cfg) -> dict:
    """Concept medians per MatID class: the zone boxes + HSV filters of the look-dev profile (lookdev.concept_zones,
    the Blender-stage definition) and extra boxes (ue_measure.extra_concept_boxes) are pooled by the class of the zone
    (cfg concept_boxes.zone_class); statistic = hsv_stats (per-channel sRGB median of the pooled pixels of the three
    views, HSV and linear Y of the median), the same as the UE side of cmd_measure."""
    cb = cfg["concept_boxes"]
    prof = json.loads((REPO / cb["profile"]).read_text(encoding="utf-8"))
    cz = prof["lookdev"]["concept_zones"]
    filters = dict(cz["filters"])
    extra = []
    if cb.get("extra_profile"):
        extra = json.loads((REPO / cb["extra_profile"]).read_text(encoding="utf-8"))["ue_measure"]["extra_concept_boxes"]
    drop = set(cb.get("replace_zones_by_extra") or [])
    pooled, used = {}, {}
    for view in ORTHO:
        img = np.asarray(Image.open(REPO / cfg["concept"][view]).convert("RGB"))
        h, sat, v = rgb_to_hsv(img.astype(np.float32) / 255.0)
        boxes = [z for z in cz.get(view) or [] if z["zone"] not in drop] + [z for z in extra if z["view"] == view]
        vmask = {}
        for z in boxes:
            cls = cb["zone_class"].get(z["zone"])
            if not cls:
                continue
            f = filters[z["filter"]] if isinstance(z["filter"], str) else z["filter"]
            x0, y0, x1, y1 = z["box"]
            m = np.zeros(h.shape, bool)
            m[y0:y1, x0:x1] = True
            if "hue" in f:
                m &= (h >= f["hue"][0]) & (h <= f["hue"][1])
            for key, arr, op in (("s_min", sat, np.greater_equal), ("v_min", v, np.greater_equal),
                                 ("s_max", sat, np.less_equal), ("v_max", v, np.less_equal)):
                if key in f:
                    m &= op(arr, f[key])
            vmask[cls] = vmask.get(cls, np.zeros(h.shape, bool)) | m  # union: overlapping boxes count a pixel once
            used.setdefault(cls, []).append({"view": view, "zone": z["zone"], "box": z["box"], "pixels": int(m.sum())})
        for cls, m in vmask.items():
            pooled.setdefault(cls, []).append(img[m])
    zones = {}
    for cls, arrs in sorted(pooled.items()):
        px = np.concatenate(arrs, 0)
        if len(px) < 30:
            continue
        zones[cls] = {"concept": hsv_stats(px), "pixels_concept": int(len(px)), "boxes": used[cls]}
    res = {"schema": "unmatched.um-v2-hero-concept-classes/1", "hero": cfg["hero"],
           "tool": "tools/art/material_library/ue_hero_lookdev.py concept",
           "sources": {"profile": cb["profile"], "profile_sha256": sha(REPO / cb["profile"]),
                       "extra_profile": cb.get("extra_profile"),
                       "concept": {v: {"path": cfg["concept"][v], "sha256": sha(REPO / cfg["concept"][v])} for v in ORTHO}},
           "zone_class": cb["zone_class"], "replace_zones_by_extra": sorted(drop),
           "method": "boxes + HSV filters of lookdev.concept_zones (+ ue_measure extra boxes), pooled by MatID class over "
                     "front/side/back; per-channel sRGB median, HSV and linear Y of the median (hsv_stats)",
           "zones": zones}
    out = REPO / cfg["concept_zones"]
    out.parent.mkdir(parents=True, exist_ok=True)
    write_json(out, res)
    for cls, z in zones.items():
        print("%-14s px %6d  %s" % (cls, z["pixels_concept"], z["concept"]))
    return res


# ------------------------------------------------------------------ verify (read-back of the import, clips)
def cmd_verify(a, cfg) -> dict:
    """UE read-back under the editor lock: ue/ldc_verify_ue.py (mesh, skeleton, textures, MIs, duplicates, clips)
    and review/ue_py/measure_clips.py with the H2LD mesh (the H2Anim clips evaluated on it)."""
    from ue_live import Ue
    from ue_lock import ue_lock
    v = cfg["verify"]
    run = REPO / cfg["run_dir"]
    ue_rep = json.loads((run / "reports/ue-import-report.json").read_text(encoding="utf-8"))
    names = ue_rep["destination"]["assets"]
    out = Path(a.out).resolve()
    out.mkdir(parents=True, exist_ok=True)
    tex = {k.split(":", 1)[1]: p for k, p in names.items() if k.startswith("texture:")}
    inst = {k: p for k, p in names.items() if k.endswith("instance") or k.startswith(("team:", "extra:"))}
    hero_arg = {"hero": cfg["hero"], "mesh": names["skeletal"], "base": names["base"], "skeleton": v["skeleton"],
                "folder": v["folder"], "hero_root": v["hero_root"], "clips_folder": v["clips_folder"],
                "textures": tex, "instances": inst}
    ue = Ue()
    with ue_lock("ue_hero_lookdev verify %s %s" % (cfg["hero"], a.tag)) as lock:
        rb = ue.run_task(str(HERE / "ue" / "ldc_verify_ue.py"), str(out / "_task.json"), timeout=600, heroes=[hero_arg])
        rec = rb["heroes"][cfg["hero"]]
        clips = [{"anim": c["anim"], "mesh": names["skeletal"], "sample_frames": None} for c in rec["clips"]]
        mc = ue.run_task(str(REVIEW / "ue_py" / "measure_clips.py"), str(out / "_task.json"), timeout=600, clips=clips,
                         height_uu=float(v["height_uu"]), min_pose_change=0.02) if clips else {"clips": []}
        dirty = {p: ue.call("asset", "is_dirty", {"asset_path": p}, record=False)
                 for p in sorted(set(rec["folder_packages"]) | {v["skeleton"]})}
        level = ue.call("scene", "get_current_level", record=False)
    tmp = out / "_task.json"
    if tmp.exists():
        tmp.unlink()
    exp = v["expect"]
    checks = {}

    def check(name, ok, measured, expected=None):
        checks[name] = {"passed": bool(ok), "measured": measured}
        if expected is not None:
            checks[name]["expected"] = expected

    bones = rec["skeleton_bones"]
    check("skeleton_is_canonical", rec["mesh_skeleton"] == v["skeleton"], rec["mesh_skeleton"], v["skeleton"])
    check("bone0_and_v2_bones", rec["bone0"] == "SKEL_UM_Humanoid" and len(bones) == exp["bones"] and
          all(b in bones for b in exp["bone_names"]), {"bone0": rec["bone0"], "count": len(bones), "bones": bones},
          {"bone0": "SKEL_UM_Humanoid", "count": exp["bones"]})
    ci = ue_rep["checks"]
    check("hierarchy_v2_cli", ci["bones_profile_17_present_with_hierarchy"]["passed"],
          ci["bones_profile_17_present_with_hierarchy"]["measured"])
    check("face_plus_x_cli", ci["front_axis_as_fbx_preset"]["passed"] and
          ci["skeletal_bounds_match_build_front_unambiguous"]["passed"],
          {"front": ci["front_axis_as_fbx_preset"]["measured"],
           "bounds": ci["skeletal_bounds_match_build_front_unambiguous"]["measured"]})
    lod0 = rec["lods"][0] if rec["lods"] else {}
    check("lod_triangles_uv", len(rec["lods"]) == 1 and lod0.get("triangles") == exp["triangles"] and
          lod0.get("uv_sets") == 2, rec["lods"], {"lods": 1, "triangles": exp["triangles"], "uv_sets": 2})
    check("base_uv", rec["base"]["uv_channels_lod0"] == exp.get("base_uv_channels", 2), rec["base"],
          {"uv_channels_lod0": exp.get("base_uv_channels", 2)})
    check("material_slots", len(rec["materials"]) == 1 and rec["materials"][0]["mi"] == names[v["default_mi_key"]],
          rec["materials"], names[v["default_mi_key"]])
    t_ok = {}
    for key, want in v["textures"].items():
        got = rec["textures"].get(key) or {}
        t_ok[key] = {"ok": all(str(got.get(k)) == str(w) for k, w in want.items()), "got": got, "want": want}
    check("textures_settings", all(x["ok"] for x in t_ok.values()), t_ok)
    i_ok = {}
    for key, want in v["instances"].items():
        got = rec["instances"].get(key) or {}
        bad = {}
        for sect, vals in want.items():
            if sect == "parent":
                if got.get("parent") != vals:
                    bad["parent"] = got.get("parent")
                continue
            for k, w in vals.items():
                g = (got.get(sect) or {}).get(k)
                if isinstance(w, list):
                    same = isinstance(g, list) and all(abs(x - y) <= 1e-3 for x, y in zip(g, w))
                elif isinstance(w, float):
                    same = isinstance(g, (int, float)) and abs(g - w) <= 1e-3
                else:
                    same = g == w
                if not same:
                    bad["%s.%s" % (sect, k)] = g
        i_ok[key] = {"ok": not bad, "mismatch": bad, "got": got}
    check("instances_values", all(x["ok"] for x in i_ok.values()), i_ok)
    check("no_duplicates", not rec["numbered_copies_in_folder"] and
          not any(v["folder"] in p for ps in rec["same_name_in_two_folders"].values() for p in ps),
          {"numbered": rec["numbered_copies_in_folder"], "same_name": rec["same_name_in_two_folders"]})
    check("no_skeleton_in_run_folder", not [p for p in rec["skeletons_under_hero_root"] if p.startswith(v["folder"])],
          rec["skeletons_under_hero_root"])
    check("folder_packages_as_import", sorted(rec["folder_packages"]) == sorted(set(names.values())),
          {"extra": sorted(set(rec["folder_packages"]) - set(names.values())),
           "missing": sorted(set(names.values()) - set(rec["folder_packages"]))})
    # reference: the H2Anim wave's measurement of the same clips on its preview mesh (same canonical skeleton, so the
    # joint motion must be identical; the idle is a breathing loop below the 2 % "pose change" threshold by design)
    ref = {}
    if v.get("clips_reference"):
        for c in json.loads((REPO / v["clips_reference"]).read_text(encoding="utf-8"))["clips"]:
            ref[c["anim"]] = {"peak_uu": c["peak_bone_displacement"]["uu"], "length_s": c["length_s"], "mesh": c["mesh"]}
    cl = {}
    for c, m in zip(rec["clips"], mc.get("clips") or []):
        samples = m.get("samples") or []
        sock = [s_.get("socket_Weapon") for s_ in samples if s_.get("socket_Weapon")]
        moved = max((math.dist(sock[0], x) for x in sock), default=0.0)
        peak = m["peak_bone_displacement"]["uu"]
        r = ref.get(c["anim"])
        cl[c["anim"].rsplit("/", 1)[1]] = {
            "same_skeleton": c["same_skeleton_as_mesh"], "length_s": c["length_s"], "peak_uu": peak,
            "peak_share_of_height": m["peak_bone_displacement"]["share_of_height"],
            "sockets_available": m.get("sockets_available"), "weapon_socket_moved_uu": round(moved, 3),
            "h2anim_reference": r,
            "ok": c["same_skeleton_as_mesh"] and peak > 0.1 and
            "Weapon" in (m.get("sockets_available") or []) and
            (r is None or (abs(r["peak_uu"] - peak) <= 0.02 and abs(r["length_s"] - c["length_s"]) <= 1e-3))}
    check("h2anim_clips_play_on_mesh", len(cl) == exp["clips"] and all(x["ok"] for x in cl.values()), cl,
          {"clips": exp["clips"]})
    check("nothing_dirty", not any(dirty.values()), dirty)
    res = {"schema": "unmatched.um-v2-hero-verify/1", "hero": cfg["hero"], "tag": a.tag, "at": now(),
           "tool": "tools/art/material_library/ue_hero_lookdev.py verify (ue/ldc_verify_ue.py + review/ue_py/"
                   "measure_clips.py)", "editor_lock": {k: x for k, x in lock.items() if k != "waits"},
           "current_level_after": level, "passed": all(c["passed"] for c in checks.values()), "checks": checks,
           "read_back": rec, "clips_measure": mc}
    write_json(out / ("verify-%s.json" % a.tag), res)
    for k, c in checks.items():
        print("%-28s %s" % (k, "PASS" if c["passed"] else "FAIL"))
    return res


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
    zone_class = cfg.get("zone_class") or {}
    cls_of = {z: ids[zone_class.get(z, z)] for z in zones_cfg}
    classes = sorted(set(cls_of.values()) | {ids[c] for c in cfg.get("decode_classes") or []} | {0})
    gate_on = cfg.get("gate_on_variant")
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
            c = cls_of[zone]
            m = erode(cls == c, 1)
            per_view[view][zone] = {"pixels": int(m.sum())}
            gm = None
            if gate_on and zone in gates:
                ref = load_frame(out, hero, tag, "%s-%s" % (view, gate_on.lower()))
                gm = gate(ref[m], gates[zone]) if ref is not None else None
                per_view[view][zone]["gated_pixels_on_%s" % gate_on] = int(gm.sum()) if gm is not None else None
            for var in variants:
                beauty = load_frame(out, hero, tag, "%s-%s" % (view, var.lower()))
                if beauty is None:
                    continue
                px = beauty[m]
                if gm is not None:
                    px = px[gm]
                elif zone in gates and len(px):
                    px = px[gate(px, gates[zone])]
                if len(px) < int(cfg.get("min_px", 150)):
                    continue
                per_view[view][zone][var] = hsv_stats(px)
                pooled.setdefault((zone, var), []).append(px)
    accent = accent_metrics(out, hero, tag, masks, cfg, ids)
    zones = {}
    for (zone, var), arrs in sorted(pooled.items()):
        px = np.concatenate(arrs, 0)
        zones.setdefault(zone, {"concept": concept.get(zone, {}).get("concept")})[var] = dict(hsv_stats(px), pixels=int(len(px)))
    tol = cfg["tolerance"]
    res = {"schema": "unmatched.um-v2-hero-lookdev-measure/1", "tag": tag, "hero": hero, "zones": zones,
           "per_view": per_view, "tolerance": tol, "team_accent": accent,
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
            # hue of a near-grey median is not defined (look-dev C: hue_min_sat, e.g. 0.1): skipped when the concept
            # zone is below that saturation (reported as hue_defined false)
            hue_defined = c["sat"] >= float(tol.get("hue_min_sat", 0.0))
            ok = {"luma": abs(yr - 1.0) <= tol["luma_ratio"], "hue": (abs(dh) <= tol["hue_deg"]) if hue_defined else True,
                  "sat": abs(ds) <= tol["sat"]}
            ev["deltas"][z] = {"Y_ratio_exposure_normalised": round(yr, 3), "Y_ratio_absolute": round(yr_abs, 3),
                               "Y_ratio_anchor": round(u["luma_Y_linear"] / max(c["luma_Y_linear"] / k_anchor, 1e-6), 3)
                               if k_anchor else None,
                               "dHue_deg": round(dh, 1), "dSat": round(ds, 3), "within": ok, "hue_defined": hue_defined,
                               "all_within": all(ok.values()), "key_zone": z in cfg.get("tolerance_zones", [])}
        res.setdefault("exposure", {})[var] = ev
    # look-dev C verdicts: board exposure (neutral, EV100 1.3) against the reading exposure (bias reading_bias_ev):
    # a zone off on the board exposure and within tolerance on the reading one is "board light" (the board light is not
    # changed by look-dev); off on the reading exposure = material / tone curve
    ex = res.get("exposure") or {}
    if "neutral" in ex and "reading" in ex:
        verdicts = {}
        for z in cfg.get("tolerance_zones") or []:
            a_ = ex["neutral"]["deltas"].get(z)
            b_ = ex["reading"]["deltas"].get(z)
            if not a_ or not b_:
                verdicts[z] = "not measured"
            elif a_["all_within"] and b_["all_within"]:
                verdicts[z] = "within both"
            elif b_["all_within"]:
                verdicts[z] = "board light"
            elif a_["all_within"]:
                verdicts[z] = "off on the reading exposure only"
            else:
                verdicts[z] = "off on both"
        res["verdicts"] = {"zones": verdicts, "board_exposure": "neutral (EV100 1.3)",
                           "reading_exposure": "reading (%+.1f EV)" % float(cfg.get("reading_bias_ev", -1.5))}
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


ACCENT_THRESH = 40


def accent_metrics(out: Path, hero: str, tag: str, masks: dict, cfg, ids: dict) -> dict:
    """Team accent on screen (look-dev C, UseTeamAccent): figure pixels = pixels decoded to a library class (>= 1) in
    the debug frame (class 0 is the dark catch-all that also takes the base top, so it is left out); accent = figure
    pixels whose lit colour differs between the two team frames by more than THRESH sRGB levels (max channel); leak =
    pixels of never-dyed classes that differ between a team frame and the neutral frame by more than THRESH. Lit frames
    of a live Lumen/TSR scene carry per-pixel grain of 10-20 levels on detailed textures (measured c1: the 12-level
    threshold marked the whole figure), so THRESH = 40; Lumen bounce of a bright dyed accent onto a neighbour can still
    pass it, so the leak share is a reference number (the unlit dye test is v2.1 accent hero-*)."""
    teams = teams_of(cfg)
    if len(teams) != 2:
        return {}
    never = [ids[z] for z in cfg.get("never_dye_zones") or [] if z in ids]
    res = {"threshold_levels": ACCENT_THRESH, "teams": teams, "never_dye_zones": cfg.get("never_dye_zones") or [], "views": {}}
    for view, cls in masks.items():
        fr = {v: load_frame(out, hero, tag, "%s-%s" % (view, v.lower())) for v in ["neutral"] + teams}
        if any(f is None for f in fr.values()):
            continue
        fig = cls >= 1
        d_teams = np.abs(fr[teams[0]].astype(np.int16) - fr[teams[1]].astype(np.int16)).max(-1) > ACCENT_THRESH
        acc = fig & d_teams
        item = {"figure_px": int(fig.sum()), "accent_px": int(acc.sum()),
                "accent_share_of_figure": round(float(acc.sum()) / max(int(fig.sum()), 1), 4)}
        if acc.sum():
            for v in ["neutral"] + teams:
                item["accent_median_srgb_" + v] = [round(float(c), 1) for c in np.median(fr[v][acc], 0)]
        if never:
            nv = np.isin(cls, never) & erode(fig, 1)
            item["never_dye_px"] = int(nv.sum())
            for t in teams:
                d = np.abs(fr[t].astype(np.int16) - fr["neutral"].astype(np.int16)).max(-1) > ACCENT_THRESH
                item["never_dye_changed_share_" + t] = round(float((d & nv).sum()) / max(int(nv.sum()), 1), 4)
        res["views"][view] = item
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
    teams = teams_of(cfg)
    label = cfg.get("sheet_label", "UE H2LD")
    cols = [("концепт", None)] + [(p["label"], p) for p in cfg.get("previous") or []] + \
        [("%s %s нейтр." % (label, tag), {"tag": tag, "variant": "neutral"})] + \
        [("%s %s %s" % (label, tag, t), {"tag": tag, "variant": t.lower()}) for t in teams] + \
        [("%s %s нейтр. %+.1f EV" % (label, tag, float(cfg.get("reading_bias_ev", -1.5))),
          {"tag": tag, "variant": "reading"})]
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
    d2.text((10, 12), "%s %s: игровая камера K2 (редактор, Cobble, High) · нейтр. | %s" % (hero, tag, " | ".join(teams)),
            fill=(235, 210, 120), font=font(24))
    for r, (vn, label) in enumerate(k2):
        y = head + r * (lab + ch2)
        for c, var in enumerate(["neutral"] + [t.lower() for t in teams]):
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
    ap.add_argument("command", choices=["lut", "review", "measure", "sheets", "concept", "verify"])
    ap.add_argument("--overrides")
    ap.add_argument("--out", required=True)
    ap.add_argument("--config")
    ap.add_argument("--tag", default="i1")
    a = ap.parse_args()
    if a.command == "lut":
        cmd_lut(a)
        return 0
    cfg = json.loads(Path(a.config).read_text(encoding="utf-8"))
    if a.command == "concept":
        cmd_concept(a, cfg)
    elif a.command == "verify":
        cmd_verify(a, cfg)
    elif a.command == "review":
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
