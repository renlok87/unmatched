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

    # RC-10: MI values and the LUT of the import profile onto the EXISTING MIs of the hero's import (no re-import of
    # the mesh, textures or clips), then verify; --profile = a newer rev of the run's profile, --dry-run = diff only
    python tools/art/material_library/ue_hero_lookdev.py apply-mi --config <review json> --out <dir> --tag <tag>
        [--profile <build profile json>] [--dry-run] [--no-verify]

apply-mi vs re-import. A look-dev iteration that changes only MI values (ue.figure_parameters, ue.teams colours,
ue.extra_instances scalars / vectors, ue.base_marker parameters / vectors, figure_static_switches) or the hero LUT
(candidate.library_inputs.LUT: a new DDS) goes through apply-mi: the MI values are planned by the CLI's own
um_master_instances (tripo_pipeline.py, same profile -> same values), only differing values are set, the LUT texture is
re-imported over itself (MIs keep their reference) when its DDS sha differs, only changed packages are saved, values are
read back against the plan and verify runs with the planned values. A new FBX (mesh or base) or any changed texture
other than the LUT (BC, N, ORM, MatID, Edge, TeamAccent: compared by file sha) or a changed asset structure (names,
folder, masters, team / extra MI set, parents) is refused: that still needs the re-import of
references/ue-import-package.md §4.4 (delete the run's assets, new ue-import run, clips, verify).

Settle (F153) and noise band (F155). review turns the editor's bThrottleCPUWhenNotForeground off in memory for the
capture (a background or hidden editor does not converge Lumen + TSR: warm-up 1.7-2.6 instead of 0.3-0.8) and waits
for convergence (3 frame differences in a row <= settle.threshold 1.0, at least the former 39 differences, at most 79);
a warm-up that does not converge aborts the review (exit 3, report settle.status not_settled) unless --allow-unsettled
(WARN). Each shot re-grabs (up to 6 more) until its last difference is under the threshold. measure reads the settle
status of review-<tag>.json (old reports: from their warm-up / settle arrays) into settle and measurement_status;
not_settled -> exit 3 (--allow-unsettled: WARN, exit 0). The luma verdict carries a noise band
(tolerance.luma_noise_band, default 0.04 = the session-to-session spread of settled frames on identical inputs, F155):
a zone whose Y ratio is within +-band of the tolerance edge is "noise_band" (deltas.<zone>.luma_state / state;
verdicts.zones "noise band: ..."), so editor noise cannot flip within <-> off; all_within stays the hard threshold.

Review config (JSON): {"hero", "run_dir" (skeletal-adopt run), "concept": {"front"|"side"|"back": png},
"concept_zones": <ld measure-report.json> (concept medians per class, pooled over the three concept views),
"variants": {"neutral"|"Blue"|"Red"|"debug": MI package}, "base_mi": {variant: MI package}, "zones": [class ids],
"key_zones": [...] (exposure anchor: geometric mean over these), "tolerance": {"luma_ratio", "hue_deg", "sat"},
"legacy_render_gate": {...}, "previous": [{"label", "frames_dir"}] (older UE frames for the sheets),
"anchor_zone": one of "zones" (k_anchor; required for a hero outside the MVP / pilot list ANCHOR_DEFAULT_HEROES, which
keep the old default "linen": review / measure exit 2 before the editor capture otherwise, review gap R-09)}.
Look-dev C (2026-09-30) keys, all optional: "zone_class" {zone: preset class id, or a list of ids = their union (ART-016:
a class split into two columns)} (zones named apart from their MatID class, e.g. two feather zones of one class, or
horn_claw in the brass column), "decode_classes" [class ids] (every class
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
# F153: frame-to-frame mean abs difference (8-bit levels): settled reviews 0.3-0.8 (last shot grab <= 0.73), unsettled
# sessions 1.7-2.6 for the whole warm-up and >= 1.1 on every shot (all 46 reviews 2026-09-29 .. 10-14)
SETTLE = {"threshold": 1.0, "min_diffs": 39, "max_diffs": 79, "shot_extra_grabs": 6}
LUMA_NOISE_BAND = 0.04  # F155: exposure-anchor spread of settled frames between editor sessions on identical inputs
EXIT_NOT_SETTLED = 3
THROTTLE_REF = {"refPath": "/Script/UnrealEd.Default__EditorPerformanceSettings"}
TP_DIR = REPO / "tools" / "tripo-pipeline"


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


def mean_abs_diff(a, b) -> float:
    return round(float(np.abs(np.asarray(a, np.int16) - np.asarray(b, np.int16)).mean()), 4)


def converged(diffs, threshold) -> bool:
    return len(diffs) >= 3 and max(diffs[-3:]) <= threshold


def settle_cfg(cfg) -> dict:
    return dict(SETTLE, **(cfg.get("settle") or {}))


def warm_up(grab_fn, s: dict, pause_s=1.5, sleep=time.sleep):
    """F153: grab until the viewport converged: at least s["min_diffs"] differences (the warm-up length before the rule:
    shader permutations and texture streaming), at most s["max_diffs"]. -> (differences, converged)."""
    prev, diffs = None, []
    while len(diffs) < s["max_diffs"]:
        im = grab_fn()
        if prev is not None:
            diffs.append(mean_abs_diff(im, prev))
            if len(diffs) >= s["min_diffs"] and converged(diffs, s["threshold"]):
                break
        prev = im
        sleep(pause_s)
    return diffs, converged(diffs, s["threshold"])


def settle_status(review: dict | None, threshold: float = SETTLE["threshold"]) -> dict:
    """Settle status of a review report (new: its settle block; older reports: their warm-up and per-shot settle
    arrays). Measured shots = the ortho views (front / side / back) the zone statistics use; an unsettled K2 shot is a
    warning only (K2 sheet)."""
    if not review:
        return {"status": "unknown", "why": "no review report next to the frames"}
    warm = review.get("warmup_mean_abs_diff") or []
    ok = converged(warm, threshold)
    bad = sorted(n for n, f in (review.get("frames") or {}).items()
                 if (f.get("settle_mean_abs_diff") or [0.0])[-1] > threshold)
    measured = [n for n in bad if n.split("-", 1)[0] in ORTHO]
    status = "settled" if ok and not measured else "not_settled"
    res = {"status": status, "threshold": threshold, "warmup_converged": ok, "warmup_last3": warm[-3:],
           "unsettled_measured_shots": measured, "unsettled_other_shots": [n for n in bad if n not in measured]}
    if isinstance(review.get("settle"), dict):
        res["recorded"] = {k: review["settle"].get(k) for k in ("status", "allow_unsettled", "throttle")}
    return res


def throttle(ue, value=None) -> dict:
    """EditorPerformanceSettings.bThrottleCPUWhenNotForeground through the MCP object toolset, in memory only (not
    saved; the class is not exposed to editor Python; same as ue_h5cb1.py, look-dev C C2)."""
    def get():
        r = ue.call("object", "get_properties", {"instance": THROTTLE_REF, "properties": ["bThrottleCPUWhenNotForeground"]},
                    record=False)
        return json.loads(r) if isinstance(r, str) and r[:1] in "[{" else r
    rec = {"before": get()}
    if value is not None:
        ue.call("object", "set_properties", {"instance": THROTTLE_REF,
                                             "values": json.dumps({"bThrottleCPUWhenNotForeground": bool(value)})},
                record=False)
    rec["after"] = get()
    return rec


def throttle_was_on(rec) -> bool:
    return "true" in json.dumps((rec or {}).get("before")).lower()


class Session:
    def __init__(self, ue, out: Path, tag: str, hero: str, settle_threshold: float = SETTLE["threshold"],
                 extra_grabs: int = 0):
        self.ue, self.out, self.tag, self.hero = ue, out, tag, hero
        self.frames = {}
        # F153: a shot whose last grab still differs by more than the threshold re-grabs up to extra_grabs times
        # (0 = the former fixed 4 grabs); info["settled"] records the outcome
        self.settle_threshold, self.extra_grabs = settle_threshold, extra_grabs

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
                settle.append(mean_abs_diff(im, prev))
            prev = im
            if attempt < grabs - 1:
                time.sleep(0.7)
        for _ in range(self.extra_grabs):
            if not settle or settle[-1] <= self.settle_threshold:
                break
            time.sleep(0.7)
            im = self.grab(xform)
            settle.append(mean_abs_diff(im, prev))
            prev = im
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
                "output_px": [1920, 1080], "settle_mean_abs_diff": settle,
                "settled": bool(settle) and settle[-1] <= self.settle_threshold, "fov": FOV, **meta}
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
    profiles = json.loads(PROFILES_JSON.read_text(encoding="utf-8"))["lightProfiles"]
    light_source = "%s lightProfiles.%s" % (rel(PROFILES_JSON), LIGHT_PROFILE)
    if LIGHT_PROFILE in profiles:
        light = profiles[LIGHT_PROFILE]
    elif cfg.get("light_profile_pinned"):
        # 2026-10-04 (real boards only, ND-5): cobble-probe left S08ArtBoardProfiles.json; a look-dev series keeps the
        # exact light of its earlier captures: the data recorded in the pinned review report (same light, same numbers)
        pinned = REPO / cfg["light_profile_pinned"]
        light = json.loads(pinned.read_text(encoding="utf-8"))["light_profile"]["data"]
        light_source = "%s light_profile.data (pinned: %s removed from %s by ND-5, 2026-10-04)" % (
            rel(pinned), LIGHT_PROFILE, rel(PROFILES_JSON))
    else:
        raise SystemExit("light profile %s is not in %s and the config pins none (light_profile_pinned)"
                         % (LIGHT_PROFILE, rel(PROFILES_JSON)))
    out = Path(a.out).resolve()
    out.mkdir(parents=True, exist_ok=True)
    ue = Ue()
    sc = settle_cfg(cfg)
    ss = Session(ue, out, a.tag, cfg["hero"], settle_threshold=sc["threshold"])
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
              "light_profile": {"source": light_source, "data": light},
              "key_rotation_pitch_yaw_roll": KEY_ROTATION, "scalability_before": sg_before, "console": []}
    temp = [L_FIG, L_BASE, L_SKY, L_CAM]
    variants = cfg["variants"]
    allow = bool(getattr(a, "allow_unsettled", False))
    report["settle"] = dict(sc, status="not_started", allow_unsettled=allow)
    thr = None
    try:
        # F153: a background / hidden (-RenderOffScreen) editor throttles its CPU and never converges Lumen + TSR
        thr = throttle(ue, False)
        report["settle"]["throttle"] = thr
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
        warm, ok = warm_up(lambda: ss.grab(xform), sc)
        report["warmup_mean_abs_diff"] = warm
        report["settle"].update(warmup_converged=ok, status="settled" if ok else "not_settled")
        if not ok and not allow:
            print("FAIL not_settled: the warm-up did not converge in %d frame differences (last %s > %.1f); no frames "
                  "taken. Another load on the GPU or a throttled background editor? Re-run, or --allow-unsettled to "
                  "capture anyway (WARN)" % (len(warm), warm[-3:], sc["threshold"]), flush=True)
            raise SystemExit(EXIT_NOT_SETTLED)
        if not ok:
            print("WARN not_settled: warm-up did not converge (last %s); capturing anyway (--allow-unsettled)"
                  % warm[-3:], flush=True)
        else:
            ss.extra_grabs = int(sc["shot_extra_grabs"])
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
                                                    "exposure": "EV100 1.3 fixed + bias %+.2f (reading frame)" % bias})
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
        if thr is not None:
            try:
                report["settle"]["throttle_restored"] = throttle(ue, throttle_was_on(thr))
            except Exception as exc:  # noqa: BLE001
                report["settle"]["throttle_error"] = str(exc)
        ue.call("scene", "load_level", {"level_path": original.split(".")[0]})
        time.sleep(2.0)
        report["restored_level"] = ue.call("scene", "get_current_level", record=False)
        report["restored_level_dirty"] = ue.call("asset", "is_dirty", {"asset_path": report["restored_level"]},
                                                 record=False)
        report["review_level_dirty_after_reload"] = ue.call("asset", "is_dirty", {"asset_path": LEVEL}, record=False)
        report["run_assets_dirty"] = {k: ue.call("asset", "is_dirty", {"asset_path": v}, record=False)
                                      for k, v in sorted(names.items())}
        report["frames"] = ss.frames
        if "warmup_mean_abs_diff" in report:
            st = settle_status(report, sc["threshold"])
            report["settle"].update({k: st[k] for k in ("status", "unsettled_measured_shots", "unsettled_other_shots")})
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
    # every parameter the expectations name is read back (ldc_verify_ue.py reads a fixed default set otherwise: a
    # Saturation / FixGainA of the profile was not verified)
    params = {s: sorted({n for want in (v.get("instances") or {}).values() for n in (want.get(s) or {})})
              for s in ("scalars", "vectors", "textures", "switches")}
    hero_arg = {"hero": cfg["hero"], "mesh": names["skeletal"], "base": names["base"], "skeleton": v["skeleton"],
                "folder": v["folder"], "hero_root": v["hero_root"], "clips_folder": v["clips_folder"],
                "textures": tex, "instances": inst, "params": params}
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


# ------------------------------------------------------------------ apply-mi (RC-10)
# ue keys whose change is a different asset set or structure (-> re-import, references/ue-import-package.md §4.4)
STRUCT_UE_KEYS = ("skeletal_asset", "base_asset", "target_skeleton", "material_route", "masters", "figure_instance",
                  "base_instance", "team_instances", "team_color_mode", "base_material_mode", "textures")
# profile texture properties (C++ names, as the CLI sets them through the MCP object toolset) -> editor-Python names
TEX_PROPS = {"SRGB": "srgb", "CompressionSettings": "compression_settings", "Filter": "filter",
             "MipGenSettings": "mip_gen_settings", "NeverStream": "never_stream", "LODGroup": "lod_group",
             "bFlipGreenChannel": "flip_green_channel"}
APPLY_TOL = 1e-4


class _PlanRecorder:
    """Stands in for the editor in tripo_pipeline.um_master_instances: records the plan, touches nothing."""

    def call(self, toolset, tool, args=None, record=True):  # noqa: ARG002 - the Ue.call signature
        if (toolset, tool) == ("asset", "exists"):
            return True
        if (toolset, tool) == ("instance", "create"):
            return "%s/%s" % (args["folder_path"], args["asset_name"])
        return None


def _tripo_pipeline():
    if str(TP_DIR) not in sys.path:
        sys.path.insert(0, str(TP_DIR))
    import tripo_pipeline
    return tripo_pipeline


def plan_instances(profile: dict, names: dict) -> dict:
    """MI values of an um-master import profile, planned by the CLI's own um_master_instances (the same code as
    ue-import, so the same profile gives the same values): {key: {asset, parent, textures, scalars, vectors,
    switches}}; names = destination.assets of the run's ue-import-report.json."""
    tp = _tripo_pipeline()
    u = profile["ue"]
    if tp.material_route(u) != "um-master":
        raise SystemExit("apply-mi: ue.material_route %r is not um-master" % u.get("material_route"))
    textures = {k: t for k, t in u["textures"].items() if "texture:" + k in names}
    plan = tp.um_master_instances(_PlanRecorder(), u, names, textures, {}, u.get("team_color_mode", "multiply"),
                                  u.get("base_material_mode", "atlas-instance"), lambda _r: None)
    return plan["instances"]


def profile_inputs(profile: dict) -> dict:
    """{adopt key: repo-relative path} of a skeletal-adopt profile, as the CLI's adopt stage keys them (fbx:<k>,
    texture:<k> for candidate.textures and candidate.library_inputs)."""
    c = profile["candidate"]
    d = Path(c["dir"])
    keys = {"fbx:%s" % k: (d / v).as_posix() for k, v in (c.get("fbx") or {}).items()}
    keys.update({"texture:%s" % k: (d / v).as_posix() for k, v in (c.get("textures") or {}).items()})
    keys.update({"texture:%s" % k: v["path"] for k, v in (c.get("library_inputs") or {}).items()})
    return keys


def apply_mi_refusals(run_profile: dict, profile: dict, adopt: dict, names: dict, sha_of=sha) -> list:
    """Why a profile cannot go through apply-mi onto the run's import (empty = it can): a changed asset structure or
    any changed mesh / texture input other than the LUT (by content: sha of the new profile's file against the sha the
    run's adopt stage pinned)."""
    why = []
    ru, u = run_profile["ue"], profile["ue"]
    for k in STRUCT_UE_KEYS:
        if ru.get(k) != u.get(k):
            why.append("ue.%s changed" % k)
    if sorted(ru.get("teams") or {}) != sorted(u.get("teams") or {}):
        why.append("ue.teams: other team names")

    def extras(p):
        return sorted((e["asset"], e.get("parent", "figure_instance")) for e in p["ue"].get("extra_instances") or [])
    if extras(run_profile) != extras(profile):
        why.append("ue.extra_instances: other MIs or parents")
    pinned = {k: adopt["inputs"].get(p) for k, p in (adopt.get("keys") or {}).items()}
    for key, path in sorted(profile_inputs(profile).items()):
        if key == "texture:LUT":
            continue
        if key.startswith("texture:") and key not in names:
            continue  # pinned but not imported (e.g. TeamMask with team_color_mode none)
        f = REPO / path
        if not f.is_file():
            why.append("%s: %s is missing" % (key, path))
        elif key not in pinned:
            why.append("%s: not an input of the run's import" % key)
        elif sha_of(f) != pinned[key]:
            why.append("%s: %s differs from the imported file (sha %s)" % (key, path, str(pinned[key])[:12]))
    return why


def lut_settings(tcfg: dict) -> dict:
    """Profile ue.textures.<LUT> -> editor-Python texture properties (enum values by name)."""
    s = {"srgb": bool(tcfg["srgb"]), "compression_settings": tcfg["compression"]}
    if "flip_green" in tcfg:
        s["flip_green_channel"] = bool(tcfg["flip_green"])
    for k, v in (tcfg.get("properties") or {}).items():
        if k not in TEX_PROPS:
            raise SystemExit("apply-mi: texture property %s has no editor-Python mapping (TEX_PROPS)" % k)
        s[TEX_PROPS[k]] = v
    return s


def lut_decision(info: dict, want_sha: str, sha_of=sha) -> dict:
    """Is the LUT texture in the editor the profile's DDS? sha stamp (written by apply-mi) first, else the sha of the
    file its import data names (the ue-import of the run records the DDS it read)."""
    if info.get("sha_stamp"):
        cur, how = info["sha_stamp"] == want_sha, "sha stamp"
    else:
        found = [s for s in info.get("source_files") or [] if Path(s).is_file()]
        cur = bool(found) and any(sha_of(Path(s)) == want_sha for s in found)
        how = ("source file %s" % found[0]) if found else "source file gone (%s)" % (info.get("source_files") or "-")
    return {"current": cur, "how": how, "want_sha256": want_sha, "reimport": not cur}


def instance_diff(plan: dict, got: dict, tol: float = APPLY_TOL) -> tuple:
    """(changes {package: {section: {name: value}}}, parent mismatches) of the planned MI values against a read-back."""
    changes, parents = {}, {}
    for key, want in sorted(plan.items()):
        pkg_ = want["asset"]
        g = got[pkg_]
        if g["parent"] != want["parent"]:
            parents[key] = {"want": want["parent"], "got": g["parent"]}
        ch = {}
        for n, v in want["scalars"].items():
            if g["scalars"].get(n) is None or abs(g["scalars"][n] - v) > tol:
                ch.setdefault("scalars", {})[n] = float(v)
        for n, v in want["vectors"].items():
            gv = g["vectors"].get(n)
            if gv is None or max(abs(a - b) for a, b in zip(gv, v)) > tol:
                ch.setdefault("vectors", {})[n] = [float(x) for x in v]
        for n, v in want["textures"].items():
            if g["textures"].get(n) != v.split(".")[0]:
                ch.setdefault("textures", {})[n] = v.split(".")[0]
        for n, v in (want.get("switches") or {}).items():
            if g["switches"].get(n) is not bool(v):
                ch.setdefault("switches", {})[n] = bool(v)
        if ch:
            changes[pkg_] = ch
    return changes, parents


def param_names(plan: dict) -> dict:
    return {w["asset"]: {s: sorted(w.get(s) or {}) for s in ("scalars", "vectors", "textures", "switches")}
            for w in plan.values()}


def verify_overlay(cfg: dict, plan: dict) -> dict:
    """The review config with verify.instances updated by the planned MI values (the hand-copied expectations of the
    config would otherwise fail on values apply-mi just changed)."""
    out = json.loads(json.dumps(cfg))
    vi = out["verify"].setdefault("instances", {})
    for key, want in plan.items():
        e = vi.setdefault(key, {})
        e["parent"] = want["parent"]
        for s in ("textures", "scalars", "vectors", "switches"):
            if want.get(s):
                e.setdefault(s, {}).update({n: (v.split(".")[0] if s == "textures" else
                                                [round(x, 4) for x in v] if s == "vectors" else
                                                float(v) if s == "scalars" else bool(v))
                                            for n, v in want[s].items()})
    return out


def cmd_apply_mi(a, cfg) -> dict:
    """RC-10: MI values and the LUT of the import profile onto the EXISTING MIs of the hero's import (see the module
    docstring), then verify. Exit codes through main(): refusal = SystemExit with the reason."""
    from ue_live import Ue
    from ue_lock import ue_lock
    t0 = time.time()
    run = REPO / cfg["run_dir"]
    ue_rep = json.loads((run / "reports/ue-import-report.json").read_text(encoding="utf-8"))
    adopt = json.loads((run / "reports/adopt-report.json").read_text(encoding="utf-8"))
    names = ue_rep["destination"]["assets"]
    run_profile_path = REPO / json.loads((run / "manifest.json").read_text(encoding="utf-8"))["config"]["build_profile"]
    profile_path = Path(a.profile).resolve() if getattr(a, "profile", None) else run_profile_path
    run_profile = json.loads(run_profile_path.read_text(encoding="utf-8"))
    profile = json.loads(profile_path.read_text(encoding="utf-8"))
    out = Path(a.out).resolve()
    out.mkdir(parents=True, exist_ok=True)
    rep = {"schema": "unmatched.um-v2-hero-apply-mi/1", "hero": cfg["hero"], "tag": a.tag, "started_at": now(),
           "tool": "tools/art/material_library/ue_hero_lookdev.py apply-mi (ue/hero_mi_apply_ue.py)",
           "run_dir": cfg["run_dir"], "run_profile": rel(run_profile_path), "profile": rel(profile_path),
           "profile_sha256": sha(profile_path), "dry_run": bool(getattr(a, "dry_run", False))}
    why = apply_mi_refusals(run_profile, profile, adopt, names)
    if why:
        rep["refused"] = why
        write_json(out / ("apply-mi-%s.json" % a.tag), rep)
        raise SystemExit("apply-mi refused (needs the re-import of references/ue-import-package.md §4.4): %s" % "; ".join(why))
    plan = plan_instances(profile, names)
    rep["plan"] = plan
    lut_pkg = names.get("texture:LUT")
    lib_lut = (profile["candidate"].get("library_inputs") or {}).get("LUT")
    want_lut = None
    if lut_pkg and lib_lut:
        f = REPO / lib_lut["path"]
        digest = sha(f)
        if lib_lut.get("sha256") and lib_lut["sha256"] != digest:
            raise SystemExit("apply-mi: LUT %s has sha %s, the profile pins %s" % (lib_lut["path"], digest[:12],
                                                                                   lib_lut["sha256"][:12]))
        want_lut = {"asset": lut_pkg, "source_file": f.as_posix(), "sha256": digest,
                    "settings": lut_settings(profile["ue"]["textures"]["LUT"])}
    task = HERE / "ue" / "hero_mi_apply_ue.py"
    tmp = out / "_task.json"
    ue = Ue()
    with ue_lock("ue_hero_lookdev apply-mi %s %s" % (cfg["hero"], a.tag)) as lock:
        read_args = {"instances": param_names(plan), "textures": [lut_pkg] if lut_pkg else []}
        before = ue.run_task(str(task), str(tmp), timeout=600, op="read", **read_args)
        changes, parents = instance_diff(plan, before["instances"])
        rep["before"] = before
        if parents:
            rep["refused"] = ["MI parent differs: %s" % parents]
            write_json(out / ("apply-mi-%s.json" % a.tag), rep)
            raise SystemExit("apply-mi refused: MI parents differ from the plan %s (re-import)" % parents)
        lut = None
        if want_lut:
            rep["lut"] = dict(lut_decision(before["textures"][lut_pkg], want_lut["sha256"]), source_file=rel(Path(want_lut["source_file"])))
            lut = want_lut if rep["lut"]["reimport"] else None
        rep["changes"] = changes
        rep["applied"] = None
        if (changes or lut) and not rep["dry_run"]:
            rep["applied"] = ue.run_task(str(task), str(tmp), timeout=900, op="apply", changes=changes, lut=lut)
        after = ue.run_task(str(task), str(tmp), timeout=600, op="read", **read_args)
        rest, _ = instance_diff(plan, after["instances"])
        level = ue.call("scene", "get_current_level", record=False)
        rep["editor_lock"] = {k: x for k, x in lock.items() if k != "waits"}
    if tmp.exists():
        tmp.unlink()
    rep["after"] = after
    rep["current_level"] = level
    lut_after = lut_decision(after["textures"][lut_pkg], want_lut["sha256"]) if want_lut else None
    rep["checks"] = {
        "mi_values_as_profile": {"passed": not rest or rep["dry_run"], "remaining_differences": rest},
        "lut_is_profile_dds": {"passed": lut_after is None or lut_after["current"] or rep["dry_run"], "measured": lut_after},
        "only_changed_packages_saved": {"passed": rep["applied"] is None or
                                        sorted((rep["applied"].get("saved") or {})) ==
                                        sorted(set(changes) | ({lut_pkg} if lut else set())),
                                        "saved": (rep["applied"] or {}).get("saved")},
        "hero_packages_not_dirty": {"passed": not [p for p in after["dirty_after"] if p in set(names.values())],
                                    "dirty": after["dirty_after"]}}
    rep["passed"] = all(c["passed"] for c in rep["checks"].values())
    rep["apply_s"] = round(time.time() - t0, 1)
    if not getattr(a, "no_verify", False) and cfg.get("verify") and not rep["dry_run"]:
        vres = cmd_verify(a, verify_overlay(cfg, plan))
        rep["verify"] = {"passed": vres["passed"], "report": rel(out / ("verify-%s.json" % a.tag)),
                         "failed": [k for k, c in vres["checks"].items() if not c["passed"]]}
        rep["passed"] = rep["passed"] and vres["passed"]
    rep["elapsed_s"] = round(time.time() - t0, 1)
    rep["finished_at"] = now()
    write_json(out / ("apply-mi-%s.json" % a.tag), rep)
    print("apply-mi %s: %d MI(s) with changes %s, LUT %s, %s in %.1f s" % (
        cfg["hero"], len(changes), sorted(p.rsplit("/", 1)[1] for p in changes),
        "n/a" if not want_lut else ("re-imported" if lut and rep["applied"] else
                                    "to re-import (dry run)" if lut else "current (%s)" % rep["lut"]["how"]),
        "PASS" if rep["passed"] else "FAIL", rep["elapsed_s"]))
    for k, c in rep["checks"].items():
        print("%-28s %s" % (k, "PASS" if c["passed"] else "FAIL"))
    return rep


# ------------------------------------------------------------------ measure
def zone_region(cfg, zone: str, view: str, cls):
    """Screen region of a zone (look-dev round 2, 2026-09-30): None = the whole frame (default, every zone without
    cfg["render_regions"][zone]). A region mirrors the concept boxes of the zone on the UE frame in figure-relative
    coordinates: the figure extents = the pixels decoded to a library class (>= 1; class 0 also takes the base top);
    x_outer = |x - centre| / half-width (the outer wing = [0.59, 0.985]), x = (x - left) / width, y = (y - top) /
    (bottom - top); "views" limits the zone to the views the concept measures (views not listed -> empty mask)."""
    reg = (cfg.get("render_regions") or {}).get(zone)
    if not reg:
        return None
    if reg.get("views") and view not in reg["views"]:
        return np.zeros(cls.shape, bool)
    ys, xs = np.nonzero(cls >= 1)
    if not len(xs):
        return np.zeros(cls.shape, bool)
    x0, x1, y0, y1 = xs.min(), xs.max(), ys.min(), ys.max()
    yy, xx = np.mgrid[0:cls.shape[0], 0:cls.shape[1]].astype(np.float32)
    m = np.ones(cls.shape, bool)
    if "x_outer" in reg:
        cx, hw = 0.5 * (x0 + x1), max(0.5 * (x1 - x0), 1.0)
        t = np.abs(xx - cx) / hw
        m &= (t >= reg["x_outer"][0]) & (t <= reg["x_outer"][1])
    if "x" in reg:
        t = (xx - x0) / max(x1 - x0, 1)
        m &= (t >= reg["x"][0]) & (t <= reg["x"][1])
    if "y" in reg:
        t = (yy - y0) / max(y1 - y0, 1)
        m &= (t >= reg["y"][0]) & (t <= reg["y"][1])
    return m


def zone_classes(cfg, ids: dict) -> dict:
    """zone -> tuple of MatID columns of the zone: cfg["zone_class"][zone] is a preset class id or a LIST of ids (the
    union: a class split into two columns keeps the zone definition, e.g. ART-016 feathers + metal_forged = the slot of
    feathers_flight); default = the zone name itself."""
    zc = cfg.get("zone_class") or {}
    out = {}
    for z in cfg["zones"]:
        v = zc.get(z, z)
        out[z] = tuple(ids[c] for c in (v if isinstance(v, list) else [v]))
    return out


def zone_mask(cls, cids) -> np.ndarray:
    return np.isin(cls, list(cids))


# R-09 (review 2026-10-14): a config without anchor_zone silently took Medusa's "linen" as the exposure anchor. The MVP
# and pilot heroes keep that default (their configs all name the zone); any other hero must name a zone of its own.
ANCHOR_DEFAULT = "linen"
ANCHOR_DEFAULT_HEROES = frozenset({"Medusa", "KingArthur", "Merlin", "Harpy", "Achilles", "Angel", "AncientLeshen"})


class ConfigError(ValueError):
    pass


def anchor_zone(cfg: dict) -> str:
    """Exposure anchor zone of the review config: cfg["anchor_zone"]; without it — "linen" only for the MVP / pilot
    heroes (old behaviour), otherwise ConfigError. A new hero's anchor must also be one of its zones."""
    hero = cfg.get("hero")
    zones = list(cfg.get("zones") or [])
    z = cfg.get("anchor_zone")
    if not z:
        if hero in ANCHOR_DEFAULT_HEROES:
            return ANCHOR_DEFAULT
        raise ConfigError("review config of %r has no anchor_zone: the old default %r is Medusa's exposure anchor. Name "
                          "a zone of this hero (one of zones %s) — \"anchor_zone\" in the config, or "
                          "write_review_config.py --set anchor_zone=<zone> (references/ue-import-package.md §3.2)"
                          % (hero, ANCHOR_DEFAULT, zones))
    if hero not in ANCHOR_DEFAULT_HEROES and zones and z not in zones:
        raise ConfigError("anchor_zone %r of %r is not one of its zones %s" % (z, hero, zones))
    return z


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
    cls_of = zone_classes(cfg, ids)
    classes = sorted({c for cs in cls_of.values() for c in cs} | {ids[c] for c in cfg.get("decode_classes") or []} | {0})
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
            m = erode(zone_mask(cls, cls_of[zone]), 1)
            reg = zone_region(cfg, zone, view, cls)
            if reg is not None:
                m &= reg
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
    band = float(tol.get("luma_noise_band", LUMA_NOISE_BAND))
    res = {"schema": "unmatched.um-v2-hero-lookdev-measure/1", "tag": tag, "hero": hero, "zones": zones,
           "per_view": per_view, "tolerance": tol, "team_accent": accent,
           "method": "UE zones = MatID classes of the debug MI (DebugView 1) decoded on the same camera against a plate "
                     "frame (figure hidden), eroded 1 px; legacy_bake gated by hue on the beauty frame (snakes); "
                     "median sRGB per channel over the pixels of the three concept views (front/side/back) pooled, "
                     "HSV and Y of the median (as ld_measure); concept = ld measure-report zones.*.concept "
                     "(class mask + colour gates on the concept, same definition)"}
    if cfg.get("render_regions"):
        res["render_regions"] = cfg["render_regions"]
    for var in variants:
        key = [z for z in cfg["key_zones"] if var in zones.get(z, {}) and zones[z].get("concept")]
        if not key:
            continue
        lr = [math.log(zones[z]["concept"]["luma_Y_linear"] / max(zones[z][var]["luma_Y_linear"], 1e-5)) for z in key]
        k = math.exp(sum(lr) / len(lr))
        anchor = anchor_zone(cfg)
        k_anchor =(zones[anchor]["concept"]["luma_Y_linear"] / max(zones[anchor][var]["luma_Y_linear"], 1e-5)
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
            ls = luma_state(yr, tol["luma_ratio"], band)
            ev["deltas"][z] = {"Y_ratio_exposure_normalised": round(yr, 3), "Y_ratio_absolute": round(yr_abs, 3),
                               "Y_ratio_anchor": round(u["luma_Y_linear"] / max(c["luma_Y_linear"] / k_anchor, 1e-6), 3)
                               if k_anchor else None,
                               "dHue_deg": round(dh, 1), "dSat": round(ds, 3), "within": ok, "hue_defined": hue_defined,
                               "all_within": all(ok.values()), "key_zone": z in cfg.get("tolerance_zones", []),
                               "luma_state": ls, "state": zone_state(ls, ok["hue"], ok["sat"])}
        res.setdefault("exposure", {})[var] = ev
    # look-dev C verdicts: board exposure (neutral, EV100 1.3) against the reading exposure (bias reading_bias_ev):
    # a zone off on the board exposure and within tolerance on the reading one is "board light" (the board light is not
    # changed by look-dev); off on the reading exposure = material / tone curve
    ex = res.get("exposure") or {}
    if "neutral" in ex and "reading" in ex:
        verdicts, hard = {}, {}
        for z in cfg.get("tolerance_zones") or []:
            a_ = ex["neutral"]["deltas"].get(z)
            b_ = ex["reading"]["deltas"].get(z)
            if not a_ or not b_:
                verdicts[z] = hard[z] = "not measured"
                continue
            hard[z] = zone_verdict(a_["all_within"], b_["all_within"])
            # F155: a zone in the noise band of either exposure is not decided (editor noise could flip it)
            noisy = [n for n, d in (("neutral", a_), ("reading", b_)) if d["state"] == "noise_band"]
            verdicts[z] = ("noise band: %s" % " + ".join(noisy) if noisy else
                           zone_verdict(a_["state"] == "within", b_["state"] == "within"))
        res["verdicts"] = {"zones": verdicts, "zones_hard": hard, "board_exposure": "neutral (EV100 1.3)",
                           "reading_exposure": "reading (%+.2f EV)" % float(cfg.get("reading_bias_ev", -1.5)),
                           "luma_noise_band": band}
    # F153: the settle status of the review that took these frames
    rev_path = out / ("review-%s.json" % tag)
    rev = json.loads(rev_path.read_text(encoding="utf-8")) if rev_path.is_file() else None
    res["settle"] = settle_status(rev, settle_cfg(cfg)["threshold"])
    res["measurement_status"] = res["settle"]["status"]
    if res["measurement_status"] == "not_settled":
        res["measurement_note"] = ("frames measured before the editor viewport converged (F153): zone values are not "
                                   "comparable with settled frames; do not tune MI values on them")
    write_json(out / ("measure-%s.json" % tag), res)
    # table to stdout
    for var, ev in (res.get("exposure") or {}).items():
        print("==", var, "k", ev["k_concept_over_ue_geomean_key_zones"])
        for z, d in ev["deltas"].items():
            u = zones[z][var]
            print("  %-15s Y %.4f ratio %.3f (abs %.3f) hue %5.1f d %5.1f sat %.3f d %+.3f %s%s" % (
                z, u["luma_Y_linear"], d["Y_ratio_exposure_normalised"], d["Y_ratio_absolute"], u["hue_deg"],
                d["dHue_deg"], u["sat"], d["dSat"], "OK" if d["all_within"] else "--",
                " (noise band)" if d["state"] == "noise_band" else ""))
    st = res["settle"]
    print("%s measurement %s (warm-up converged %s, unsettled measured shots %d)" % (
        "WARN" if st["status"] != "settled" else "OK", st["status"], st.get("warmup_converged"),
        len(st.get("unsettled_measured_shots") or [])))
    return res


def luma_state(yr: float, tol: float, band: float = LUMA_NOISE_BAND) -> str:
    """F155: luma verdict that holds for every Y ratio in [yr (1 - band), yr (1 + band)]: "within" / "off", else
    "noise_band" (the ratio is within the noise of the tolerance edge 1 +- tol)."""
    lo, hi = yr * (1.0 - band), yr * (1.0 + band)
    if lo >= 1.0 - tol and hi <= 1.0 + tol:
        return "within"
    if lo > 1.0 + tol or hi < 1.0 - tol:
        return "off"
    return "noise_band"


def zone_state(luma: str, hue_ok: bool, sat_ok: bool) -> str:
    if luma == "off" or not hue_ok or not sat_ok:
        return "off"
    return luma


def zone_verdict(board_within: bool, reading_within: bool) -> str:
    """Look-dev C verdict of a zone from the board (neutral) and the reading exposure."""
    if board_within and reading_within:
        return "within both"
    if reading_within:
        return "board light"
    if board_within:
        return "off on the reading exposure only"
    return "off on both"


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
        [("%s %s нейтр. %+.2f EV" % (label, tag, float(cfg.get("reading_bias_ev", -1.5))),
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
    for stream in (sys.stdout, sys.stderr):  # RB-11/F47: UTF-8 even in a cp1251 pipe (agents' Bash tool)
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="backslashreplace")
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0],
                                 epilog="apply-mi: MI values / LUT of the import profile onto the existing MIs, no "
                                        "re-import; a new FBX or texture (other than the LUT) still needs the re-import "
                                        "of references/ue-import-package.md §4.4")
    ap.add_argument("command", choices=["lut", "review", "measure", "sheets", "concept", "verify", "apply-mi"])
    ap.add_argument("--overrides")
    ap.add_argument("--out", required=True)
    ap.add_argument("--config")
    ap.add_argument("--tag", default="i1")
    ap.add_argument("--allow-unsettled", action="store_true",
                    help="review / measure: capture and measure frames whose editor viewport did not converge (F153); "
                         "WARN instead of exit 3")
    ap.add_argument("--profile", help="apply-mi: build profile to apply (default: the profile of the config's run_dir)")
    ap.add_argument("--dry-run", action="store_true", help="apply-mi: read and diff only, change nothing")
    ap.add_argument("--no-verify", action="store_true", help="apply-mi: skip the verify read-back after applying")
    a = ap.parse_args()
    if a.command == "lut":
        cmd_lut(a)
        return 0
    cfg = json.loads(Path(a.config).read_text(encoding="utf-8"))
    if a.command in ("review", "measure"):
        try:
            anchor_zone(cfg)  # R-09: before the editor capture, not after it
        except ConfigError as exc:
            print("ERROR %s" % exc, file=sys.stderr)
            return 2
    measured = None
    if a.command == "concept":
        cmd_concept(a, cfg)
    elif a.command == "verify":
        cmd_verify(a, cfg)
    elif a.command == "apply-mi":
        return 0 if cmd_apply_mi(a, cfg)["passed"] else 1
    elif a.command == "review":
        cmd_review(a, cfg)
        measured = cmd_measure(a, cfg)
        cmd_sheets(a, cfg)
    elif a.command == "measure":
        measured = cmd_measure(a, cfg)
    else:
        cmd_sheets(a, cfg)
    if measured and measured.get("measurement_status") == "not_settled":
        if a.allow_unsettled:
            print("WARN not_settled frames measured (--allow-unsettled): diagnostic only, do not tune on them")
        else:
            print("FAIL not_settled: frames of %s were taken before the editor viewport converged (F153); re-run the "
                  "review (or --allow-unsettled for a diagnostic measurement)" % a.tag)
            return EXIT_NOT_SETTLED
    return 0


if __name__ == "__main__":
    sys.exit(main())
