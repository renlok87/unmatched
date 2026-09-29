"""LD-<hero>-ue: UE look-dev frames and concept-vs-UE zone metrics of a hero on M_UM_Figure_v2 (Cobble light, High).

    python tools/tripo-pipeline/review/h2ld_ue_lookdev.py --run-dir <H2LD skeletal-adopt run> --out <evidence dir>
        --lookdev-profile <hero>-h2-lookdev.json --tag r1 [--h2-run <H2 skeletal-adopt run>] [--raw-dir C:/tmp/...]

LIVE UnrealEditor (MCP 127.0.0.1:8123 + editor console, review/ue_live.py). Same scene as review/h2_ue_review.py
(W5c-A): the P1.7 Cobble control level, the cobble-probe light profile of the packaged client applied in memory
(SkyLight cubemap x 11.2, key CSM), fixed exposure EV100 1.3, editor scalability High (sg.* = 2), screen percentage
as the editor has it (recorded). Nothing is saved; the previous level is re-opened at the end.

Frames (EditorAppToolset.CaptureViewport, piloted CameraActor, FOV 35):
  front / side / back  horizontal camera at 200 uu under the concept's view: front, the figure's RIGHT side (the concept
                       side view shows the staff hand), back; torso close-up; game camera K2 5x (az 0 / 180) and 1.6x;
  materials            H2LD Neutral (TeamColor white, TeamDye 0 = the concept-toned bake), Blue, Red (team MIs);
                       H2 (v1, W5c-A) neutral through a transient MID (TeamDye 0) and its Blue MI, on the same actor
                       (mesh swapped: H2 and H2LD share rig, UV0 and geometry);
  masks                DebugZones MI (look-dev zone id in the MatID slot, DebugView 1 = emissive zone colour) on figure
                       and base; a plate without the figure; 12 calibration frames (DebugMatIDOverride = zone id) give
                       each zone's reference colour; DebugClasses MI (class colours of the MatID).
Metrics per zone and view (front/side/back): median colour in linear light of the Neutral frame inside the eroded zone
mask (and of H2) vs the concept median measured with the boxes + HSV filters of the look-dev profile
(lookdev.concept_zones, the same as the Blender stage) plus --extra-concept-boxes; luma ratio after one exposure factor
k = median over zones and views of concept Y / UE Y (the concept's light and exposure are unknown, LDM-6); hue and
saturation of the medians in sRGB HSV. Frames are EDITOR frames (class editor-mcp-viewport): diagnostics, not K1/K2
acceptance, no RENDER fingerprint.
"""

import argparse
import datetime as dt
import hashlib
import json
import math
import sys
import time
from pathlib import Path

import numpy as np
from PIL import Image
from scipy import ndimage

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
sys.path.insert(0, str(HERE))
import h2_ue_review as R  # noqa: E402
from ue_live import Ue  # noqa: E402

SCHEMA = "unmatched.h2ld-ue-lookdev/1"
PREFIX = "LDM "
L_FIG, L_BASE, L_SKY, L_CAM = (PREFIX + "figure - temporary", PREFIX + "base - temporary", PREFIX + "sky - temporary",
                               PREFIX + "camera FOV35 - temporary")
LUM = np.array([0.2126, 0.7152, 0.0722])
TOLERANCE = {"luma_ratio": 0.15, "hue_deg": 12.0, "sat": 0.10}
TOLERANCE_ZONES = ("wool", "embroidery", "buckle", "face_skin", "hands_skin")  # metals, cloth, skin of the character
MIN_PX = 60
MVIEWS = ["front", "side", "back", "torso", "buckle", "buckle-q"]  # measured views (torso and close-ups: front concept)
K_VIEWS = ("front", "side", "back", "torso")  # views of the exposure factor k (the close-ups would over-weight the belt)
AVG_LAST = 3  # measured frames: mean of the last 3 grabs (Lumen reflection noise on small metal parts)
# buckle close-ups (LD-merlin-ue fix pass): the buckle is 1494 texels, 26 px in the 200 uu front view - measured in two
# views of its own besides the torso: straight on and from 35 deg to the figure's right, 40 uu, at the buckle height
BUCKLE = {"distance": 40.0, "z": 28.0, "azimuth_q": 35.0}
# views of a zone's summary (median over views): the close-ups exist for the buckle only; every other zone keeps the
# four views of r1-r3 (a close-up full of wool or hands would change their medians and break the r3 comparison)
ZONE_VIEWS = {"buckle": ("torso", "buckle", "buckle-q")}
# the base keeps M_UM_BaseMarker v1: its side is the team band (white in the neutral MI), not the concept's stone -
# measured and reported, but not part of the exposure factor k
K_EXCLUDE = ("base",)
ERODE_PX = 2


def views():
    x, y = R.CELL[0], R.CELL[1]
    n, t = R.NARROW, R.TORSO
    p = math.radians(-R.PITCH_K2)
    fz = R.CELL[2] + R.FOCUS_Z

    def k2(dist):
        return [x, y + dist * math.cos(p), fz + dist * math.sin(p)], [R.PITCH_K2, R.YAW_K2, 0.0]

    # the figure faces +Y at yaw 90; its right side (staff hand, UE +Y at yaw 0) is then -X
    bd, bz, qa = BUCKLE["distance"], BUCKLE["z"], math.radians(BUCKLE["azimuth_q"])
    return {
        "buckle": {"eye": [x, y + bd, bz], "rot": [0.0, -90.0, 0.0], "fov": n["fov"], "yaw": 90.0,
                   "kind": "buckle close-up, front, FOV 35, 40 uu", "concept": "front"},
        # the figure's right is -X (see above): the camera swings to -X by the azimuth and looks back at the buckle
        "buckle-q": {"eye": [x - bd * math.sin(qa), y + bd * math.cos(qa), bz],
                     "rot": [0.0, math.degrees(math.atan2(-math.cos(qa), math.sin(qa))), 0.0], "fov": n["fov"],
                     "yaw": 90.0, "kind": "buckle close-up, 35 deg to the figure's right, FOV 35, 40 uu",
                     "concept": "front"},
        "front": {"eye": [x, y + n["distance"], n["z"]], "rot": [0.0, -90.0, 0.0], "fov": n["fov"], "yaw": 90.0,
                  "kind": "front, FOV 35, 200 uu", "concept": "front"},
        "side": {"eye": [x - n["distance"], y, n["z"]], "rot": [0.0, 0.0, 0.0], "fov": n["fov"], "yaw": 90.0,
                 "kind": "right side (concept side view), FOV 35, 200 uu", "concept": "side"},
        "back": {"eye": [x, y - n["distance"], n["z"]], "rot": [0.0, 90.0, 0.0], "fov": n["fov"], "yaw": 90.0,
                 "kind": "back, FOV 35, 200 uu", "concept": "back"},
        "torso": {"eye": [x, y + t["distance"], t["z"]], "rot": [0.0, -90.0, 0.0], "fov": t["fov"], "yaw": 90.0,
                  "kind": "torso close-up, FOV 35, 85 uu (measured against the front concept: buckle, face, hands)",
                  "concept": "front"},
        "k2-5x-az0": dict(zip(("eye", "rot"), k2(R.K2_5X)), fov=R.FOV_K2, yaw=90.0, kind="game K2 5x, facing the camera"),
        "k2-5x-az180": dict(zip(("eye", "rot"), k2(R.K2_5X)), fov=R.FOV_K2, yaw=-90.0, kind="game K2 5x, from behind"),
        "k2-1p6-az0": dict(zip(("eye", "rot"), k2(R.K2_1P6)), fov=R.FOV_K2, yaw=90.0, kind="game K2 1.6x"),
    }


def srgb_to_linear(a):
    a = np.asarray(a, np.float64)
    return np.where(a <= 0.04045, a / 12.92, ((a + 0.055) / 1.055) ** 2.4)


def linear_to_srgb(a):
    a = np.clip(np.asarray(a, np.float64), 0, 1)
    return np.where(a <= 0.0031308, a * 12.92, 1.055 * a ** (1 / 2.4) - 0.055)


def rgb_to_hsv(rgb):
    r, g, b = rgb[..., 0], rgb[..., 1], rgb[..., 2]
    mx, mn = rgb.max(-1), rgb.min(-1)
    d = mx - mn
    h = np.zeros_like(mx)
    m = d > 1e-9
    rr = m & (mx == r)
    gg = m & (mx == g) & ~rr
    bb = m & ~rr & ~gg
    h[rr] = ((g - b)[rr] / d[rr]) % 6
    h[gg] = ((b - r)[gg] / d[gg]) + 2
    h[bb] = ((r - g)[bb] / d[bb]) + 4
    h = h * 60.0
    s = np.where(mx > 1e-9, d / np.maximum(mx, 1e-9), 0.0)
    return h, s, mx


def describe(lin):
    lin = np.asarray(lin, np.float64)
    h, s, v = rgb_to_hsv(linear_to_srgb(lin)[None, :])
    return {"linear": [round(float(x), 5) for x in lin], "luma_Y": round(float(lin @ LUM), 5),
            "hue_deg": round(float(h[0]), 1), "sat": round(float(s[0]), 4), "value": round(float(v[0]), 4)}


def hue_delta(a, b):
    return (a - b + 180.0) % 360.0 - 180.0


def concept_medians(profile, concept_dir, hero, extra_boxes):
    cz = profile["lookdev"]["concept_zones"]
    filters = dict(cz["filters"])
    out = {}
    for view in ("front", "side", "back"):
        img = np.asarray(Image.open(concept_dir / ("%s-%s.png" % (hero, view))).convert("RGB"), np.float64) / 255.0
        h, s, v = rgb_to_hsv(img)
        lin = srgb_to_linear(img)
        masks = {}
        for z in list(cz.get(view) or []) + [b for b in extra_boxes if b["view"] == view]:
            f = filters[z["filter"]] if isinstance(z["filter"], str) else z["filter"]
            x0, y0, x1, y1 = z["box"]
            m = np.zeros(h.shape, bool)
            m[y0:y1, x0:x1] = True
            if "hue" in f:
                m &= (h >= f["hue"][0]) & (h <= f["hue"][1])
            for key, arr, op in (("s_min", s, np.greater_equal), ("v_min", v, np.greater_equal),
                                 ("s_max", s, np.less_equal), ("v_max", v, np.less_equal)):
                if key in f:
                    m &= op(arr, f[key])
            masks[z["zone"]] = masks.get(z["zone"], np.zeros(h.shape, bool)) | m
        out[view] = {k: {"pixels": int(m.sum()), **(describe(np.median(lin[m], 0)) if m.sum() >= 30 else {})}
                     for k, m in masks.items()}
    return out


class Shots:
    def __init__(self, ue, out: Path, raw: Path, tag: str, hero: str):
        self.ue, self.out, self.raw, self.tag, self.hero = ue, out, raw, tag, hero
        self.frames = {}
        self.images = {}

    def task(self, script, op, timeout=600, **kw):
        return self.ue.run_task(str(HERE / "ue_py" / script), str(self.raw / "_task.json"), timeout=timeout, op=op, **kw)

    def grab(self, xform):
        return R.Review.grab(self, xform)

    def shot(self, name, view, meta, keep_jpg=True, settle_n=4, avg_last=1):
        """avg_last > 1: the measured image (self.images, raw PNG) is the mean of the last N grabs in linear light -
        the temporal noise of Lumen reflections on small metal parts (buckle) is averaged out; the JPEG frame stays
        the last grab."""
        self.task("control_scene_ue.py", "camera", label=L_CAM, location=view["eye"], rotation=view["rot"],
                  fov=view["fov"])
        xform = {"location": dict(zip("xyz", view["eye"])), "rotation": dict(zip(("pitch", "yaw", "roll"), view["rot"])),
                 "scale": {"x": 1, "y": 1, "z": 1}}
        time.sleep(0.5)
        settle_n = max(settle_n, avg_last + 1)
        prev, settle, grabs = None, [], []
        for attempt in range(settle_n):
            im = self.grab(xform)
            if prev is not None:
                settle.append(round(float(np.abs(np.asarray(im, np.int16) - np.asarray(prev, np.int16)).mean()), 4))
            prev = im
            grabs.append(np.asarray(im))
            if attempt < settle_n - 1:
                time.sleep(0.7)
        if avg_last > 1:
            lin = np.mean([srgb_to_linear(g.astype(np.float64) / 255.0) for g in grabs[-avg_last:]], 0)
            meas = np.clip(np.round(linear_to_srgb(lin) * 255.0), 0, 255).astype(np.uint8)
        else:
            meas = np.asarray(im)
        raw_path = self.raw / ("%s.png" % name)
        Image.fromarray(meas).save(raw_path)
        self.images[name] = meas
        info = {"view": {k: view[k] for k in ("eye", "rot", "fov", "yaw", "kind")}, "viewport_px": list(im.size),
                "settle_mean_abs_diff": settle, "measured_mean_of_last_grabs": avg_last, **meta}
        if keep_jpg:
            w, h = im.size
            ch = round(w * 9 / 16)
            box = (0, (h - ch) // 2, w, (h - ch) // 2 + ch) if ch <= h else ((w - round(h * 16 / 9)) // 2, 0,
                                                                              (w + round(h * 16 / 9)) // 2, h)
            frame = im.crop(box).resize((1920, 1080), Image.LANCZOS)
            fname = "%s-h2ld-%s-%s.jpg" % (self.hero.lower(), name, self.tag)
            path = self.out / fname
            frame.save(path, quality=90, optimize=True)
            digest = hashlib.sha256(path.read_bytes()).hexdigest()
            side = {"schema": R.SIDECAR_SCHEMA, "class": "editor-mcp-viewport", "frameSha256": digest, "frame": fname,
                    "label": "EDITOR frame (LD-%s-ue look-dev, Cobble light, High), diagnostic; not K1/K2 acceptance, "
                             "no RENDER fingerprint" % self.hero.lower(), "run_tag": self.tag,
                    "crop_px": list(box), "output_px": [1920, 1080], "jpeg_quality": 90, **info}
            path.with_name(path.stem + ".evidence.json").write_text(json.dumps(side, indent=1, sort_keys=True) + "\n",
                                                                  encoding="utf-8", newline="\n")
            info.update(frame=fname, sha256=digest)
        self.frames[name] = info
        print(" ", name, "settle", settle, flush=True)
        return name


def figure_mask(zone_img, plate_img, thr=14.0):
    d = np.abs(zone_img.astype(np.int16) - plate_img.astype(np.int16)).mean(-1)
    return d > thr


def classify(zone_img, fmask, refs, max_dist=38.0):
    """zone id per pixel (0 = none): nearest calibrated reference colour (sRGB 8-bit), inside the figure mask."""
    ids = sorted(refs)
    ref = np.array([refs[i] for i in ids], np.float64)
    px = zone_img.astype(np.float64)
    d = np.sqrt(((px[..., None, :] - ref[None, None, :, :]) ** 2).sum(-1))
    best = d.argmin(-1)
    dist = d.min(-1)
    lab = np.array(ids)[best]
    lab[(dist > max_dist) | ~fmask] = 0
    return lab


def zone_stats(img, lab, legend):
    lin = srgb_to_linear(img.astype(np.float64) / 255.0)
    out = {}
    for zid, rec in legend.items():
        m = lab == int(zid)
        m = ndimage.binary_erosion(m, iterations=ERODE_PX)
        n = int(m.sum())
        out[rec["zone"]] = {"pixels": n, **(describe(np.median(lin[m], 0)) if n >= MIN_PX else {})}
    return out


def compare(ue, concept, k):
    res = {}
    for zone, u in ue.items():
        c = concept.get(zone) or {}
        if "luma_Y" not in u or "luma_Y" not in c:
            res[zone] = {"ue_pixels": u.get("pixels"), "concept_pixels": c.get("pixels"), "measured": False}
            continue
        lr = u["luma_Y"] * k / max(c["luma_Y"], 1e-6)
        dh = hue_delta(u["hue_deg"], c["hue_deg"])
        ds = u["sat"] - c["sat"]
        res[zone] = {"measured": True, "ue": u, "concept": c, "luma_ratio": round(lr, 3), "hue_delta_deg": round(dh, 1),
                     "sat_delta": round(ds, 3),
                     "within": {"luma": abs(lr - 1) <= TOLERANCE["luma_ratio"], "hue": abs(dh) <= TOLERANCE["hue_deg"],
                                "sat": abs(ds) <= TOLERANCE["sat"]}}
    return res


def summarise(per_view):
    zones = sorted({z for v in per_view.values() for z in v})
    out = {}
    for z in zones:
        use = ZONE_VIEWS.get(z, K_VIEWS)
        rows = [per_view[v][z] for v in per_view if v in use and z in per_view[v] and per_view[v][z].get("measured")]
        if not rows:
            out[z] = {"views": 0}
            continue
        lr = float(np.median([r["luma_ratio"] for r in rows]))
        dh = float(np.median([r["hue_delta_deg"] for r in rows]))
        ds = float(np.median([r["sat_delta"] for r in rows]))
        out[z] = {"views": len(rows), "summary_views": [v for v in per_view if v in use and z in per_view[v]
                                                         and per_view[v][z].get("measured")], "luma_ratio": round(lr, 3), "hue_delta_deg": round(dh, 1), "sat_delta": round(ds, 3),
                  "toleranced": z in TOLERANCE_ZONES,
                  "within": {"luma": abs(lr - 1) <= TOLERANCE["luma_ratio"], "hue": abs(dh) <= TOLERANCE["hue_deg"],
                             "sat": abs(ds) <= TOLERANCE["sat"]}}
        out[z]["pass"] = all(out[z]["within"].values())
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--run-dir", required=True)
    ap.add_argument("--h2-run", default=None)
    ap.add_argument("--out", required=True)
    ap.add_argument("--raw-dir", required=True)
    ap.add_argument("--lookdev-profile", required=True)
    ap.add_argument("--hero", default="Merlin")
    ap.add_argument("--concept-dir", default=None)
    ap.add_argument("--extra-concept-boxes", default=None,
                    help="JSON list [{view, zone, box, filter}], or a JSON file with that list (or with "
                         "ue_measure.extra_concept_boxes, e.g. the hero's *-lookdev-ue-lut.json)")
    ap.add_argument("--tag", default="r1")
    ap.add_argument("--quick", action="store_true", help="measurement views only (front/side/back), no K2/team sets")
    ap.add_argument("--exposure-offset", type=float, default=0.0,
                    help="DIAGNOSTIC r.ExposureOffset for the whole pass (0 = the acceptance exposure EV100 1.3)")
    ap.add_argument("--metrics-only", action="store_true",
                    help="no editor: recompute metrics and sheets from the raw PNGs (--raw-dir) and the report of an "
                         "earlier pass with the same --tag (e.g. after a change of the concept boxes or zone views)")
    ap.add_argument("--second-exposure", type=float, default=None,
                    help="also shoot the measured Neutral (and H2) views at r.ExposureOffset = this and measure them "
                         "with their own k (two-exposure check of the look-dev: a LUT tuned on the tone-curve "
                         "shoulder of one exposure must not pass by accident)")
    a = ap.parse_args()
    hero = a.hero
    run = Path(a.run_dir).resolve()
    manifest = json.loads((run / "manifest.json").read_text(encoding="utf-8"))
    ue_rep = json.loads((run / "reports/ue-import-report.json").read_text(encoding="utf-8"))
    if not ue_rep.get("passed"):
        raise SystemExit("the run's ue-import did not pass")
    profile = json.loads((REPO / manifest["config"]["build_profile"]).read_text(encoding="utf-8"))
    names = ue_rep["destination"]["assets"]
    h2 = None
    if a.h2_run:
        h2r = json.loads((Path(a.h2_run).resolve() / "reports/ue-import-report.json").read_text(encoding="utf-8"))
        h2 = h2r["destination"]["assets"]
    ldprof = json.loads(Path(a.lookdev_profile).read_text(encoding="utf-8"))
    concept_dir = Path(a.concept_dir) if a.concept_dir else REPO / "art/imagegen/hero-quality-v1" / hero.lower()
    extra = []
    if a.extra_concept_boxes:
        src = a.extra_concept_boxes
        extra = json.loads(Path(src).read_text(encoding="utf-8")) if Path(src).is_file() else json.loads(src)
        if isinstance(extra, dict):
            extra = extra["ue_measure"]["extra_concept_boxes"]
    ue_inputs = json.loads((REPO / profile["candidate"]["dir"] / profile["candidate"]["extra_reports"]["ue_inputs"])
                           .read_text(encoding="utf-8"))
    legend = ue_inputs["zone_legend"]
    light = json.loads(R.PROFILES_JSON.read_text(encoding="utf-8"))["lightProfiles"][R.LIGHT_PROFILE]
    out = Path(a.out).resolve()
    out.mkdir(parents=True, exist_ok=True)
    raw = Path(a.raw_dir).resolve()
    raw.mkdir(parents=True, exist_ok=True)
    if a.metrics_only:
        sh = Shots(None, out, raw, a.tag, hero)
        report = json.loads((out / ("h2ld-lookdev-report-%s.json" % a.tag)).read_text(encoding="utf-8"))
        report["concept"] = concept_medians(ldprof, concept_dir, hero.lower(), extra)
        report["concept_extra_boxes"] = extra
        report["metrics_recomputed_at"] = dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat()
        (out / ("h2ld-lookdev-report-%s.json" % a.tag)).write_text(
            json.dumps(report, indent=1, sort_keys=True, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n")
        for png in sorted(raw.glob("*.png")):
            if not png.stem.endswith("-labels"):
                sh.images[png.stem] = np.asarray(Image.open(png).convert("RGB"))
        refs = {int(z): v for z, v in report["zone_reference_colours_srgb8"].items()}
        vs = views()
    else:
        ue = Ue()
        sh = Shots(ue, out, raw, a.tag, hero)
        report = {"schema": SCHEMA, "tag": a.tag, "tool": "tools/tripo-pipeline/review/h2ld_ue_lookdev.py",
                  "started_at": dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat(),
                  "kind": "EDITOR look-dev frames + zone metrics (live UnrealEditor via MCP); not packaged, no RENDER "
                          "fingerprint, not K1/K2 acceptance",
                  "run": run.relative_to(REPO).as_posix(), "profile": profile["profile_id"], "assets": names,
                  "h2_assets": h2, "review_level": R.LEVEL, "cell": R.CELL, "tolerance": TOLERANCE,
                  "tolerance_zones": list(TOLERANCE_ZONES), "erode_px": ERODE_PX, "min_px": MIN_PX,
                  "light_profile": {"source": "%s lightProfiles.%s" % (R.PROFILES_JSON.relative_to(REPO).as_posix(),
                                                                       R.LIGHT_PROFILE), "data": light},
                  "key_rotation_pitch_yaw_roll": R.KEY_ROTATION, "console": []}
        report["concept"] = concept_medians(ldprof, concept_dir, hero.lower(), extra)
        report["concept_extra_boxes"] = extra
        original = ue.call("scene", "get_current_level", record=False)
        if ue.call("asset", "is_dirty", {"asset_path": original}, record=False):
            raise SystemExit("open level %s has unsaved changes; refusing to switch levels" % original)
        if original.split(".")[0] == R.LEVEL:
            raise SystemExit("the review level itself is open (another session?); open another level first")
        if ue.call("asset", "is_dirty", {"asset_path": R.LEVEL}, record=False):
            raise SystemExit("the review level has unsaved changes in memory (someone else is using it)")
        report["original_level"] = original
        sg_before = {n: R.cvar_value(ue, n) for n in R.SG}
        report["scalability_before"] = sg_before
        report["verify"] = sh.task("h2ld_lookdev_ue.py", "verify",
                                   textures=[v for k, v in names.items() if k.startswith("texture:")],
                                   skeletal=[names["skeletal"]] + ([h2["skeletal"]] if h2 else []))
        temp = [L_FIG, L_BASE, L_SKY, L_CAM]
        vs = views()
        fig_mi = {"Neutral": names["extra:MI_%s_H2LD_Neutral" % hero], "Blue": names["team:figure:Blue"],
                  "Red": names["team:figure:Red"]}
        base_mi = {"Neutral": names["base_instance"], "Blue": names["team:base:Blue"], "Red": names["team:base:Red"]}
        zones_mi = names["extra:MI_%s_H2LD_DebugZones" % hero]
        classes_mi = names["extra:MI_%s_H2LD_DebugClasses" % hero]
        shots = {}

        def setm(fig, base):
            sh.task("control_scene_ue.py", "set", changes=[{"label": L_FIG, "materials": {"0": fig}},
                                                           {"label": L_BASE, "materials": {"0": base}}])

        def yaw(v):
            sh.task("control_scene_ue.py", "set", changes=[{"label": L_FIG, "yaw": v["yaw"]}, {"label": L_BASE, "yaw": v["yaw"]}])

        def set_exposure(v):
            ue.console("r.ExposureOffset %g" % v)
            report["console"].append("r.ExposureOffset %g" % v)
            time.sleep(1.5)

        def still_ours():
            cur = ue.call("scene", "get_current_level", record=False)
            if cur.split(".")[0] != R.LEVEL:
                raise RuntimeError("the editor level changed under the run (another session?): %s" % cur)

        try:
            ue.call("scene", "load_level", {"level_path": R.LEVEL})
            time.sleep(3.0)
            report["setup"] = sh.task("h2_review_ue.py", "setup", timeout=600, level=R.LEVEL, hide_label_prefixes=["P17 "],
                                      keep_labels=[R.EXPOSURE_LABEL],
                                      lights={"off": [R.FILL_LABEL],
                                              "key": {"label": R.KEY_LABEL, "intensity_lux": light["directional"]["intensity"],
                                                      "shadow_distance_uu": light["directional"]["shadow"]["distanceUU"],
                                                      "cascades": light["directional"]["shadow"]["cascades"],
                                                      "contact_shadow_length": light["directional"]["shadow"]["contactShadowLength"],
                                                      "rotation_pitch_yaw_roll": R.KEY_ROTATION}},
                                      sky={"label": L_SKY, "cubemap": light["sky"]["cubemap"], "intensity": light["sky"]["intensity"],
                                           "lower_hemisphere_is_black": light["sky"]["lowerHemisphereIsBlack"],
                                           "color_linear": light["sky"]["colorLinear"]},
                                      figure={"label": L_FIG, "kind": "skeletal", "asset": names["skeletal"],
                                              "location": R.CELL, "yaw": 0.0},
                                      base={"label": L_BASE, "kind": "static", "asset": names["base"], "location": R.CELL,
                                            "yaw": 0.0})
            for n in R.SG:
                ue.console("%s 2" % n)
                report["console"].append("%s 2" % n)
            for flag in R.SHOW_FLAGS_OFF:
                ue.console("ShowFlag.%s 0" % flag)
                report["console"].append("ShowFlag.%s 0" % flag)
            if a.exposure_offset:
                ue.console("r.ExposureOffset %g" % a.exposure_offset)
                report["console"].append("r.ExposureOffset %g" % a.exposure_offset)
            report["exposure_offset"] = R.cvar_value(ue, "r.ExposureOffset")
            report["scalability_during"] = {n: R.cvar_value(ue, n) for n in R.SG}
            report["screen_percentage"] = {n: R.cvar_value(ue, n) for n in ("r.ScreenPercentage",
                                                                             "r.Editor.Viewport.ScreenPercentage")}
            report["anti_aliasing_method"] = R.cvar_value(ue, "r.AntiAliasingMethod")
            report["gi_reflections"] = {n: R.cvar_value(ue, n) for n in ("r.DynamicGlobalIlluminationMethod",
                                                                           "r.ReflectionMethod")}
            setm(fig_mi["Neutral"], base_mi["Neutral"])
            time.sleep(8.0)
            yaw(vs["front"])
            v0 = vs["front"]
            sh.task("control_scene_ue.py", "camera", label=L_CAM, location=v0["eye"], rotation=v0["rot"], fov=v0["fov"])
            xform = {"location": dict(zip("xyz", v0["eye"])), "rotation": dict(zip(("pitch", "yaw", "roll"), v0["rot"])),
                     "scale": {"x": 1, "y": 1, "z": 1}}
            prev, warm = None, []
            for _ in range(30):
                im = sh.grab(xform)
                if prev is not None:
                    warm.append(round(float(np.abs(np.asarray(im, np.int16) - np.asarray(prev, np.int16)).mean()), 4))
                    if warm[-1] < 0.05 and len(warm) >= 3:
                        break
                prev = im
                time.sleep(1.5)
            report["warmup_mean_abs_diff"] = warm
            mviews = MVIEWS
            allviews = list(vs) if not a.quick else mviews
            # H2LD neutral / Blue / Red
            for team in ("Neutral", "Blue", "Red"):
                if a.quick and team != "Neutral":
                    continue
                setm(fig_mi[team], base_mi[team])
                time.sleep(2.0)
                for name in allviews:
                    yaw(vs[name])
                    shots[(name, "ld", team)] = sh.shot("%s-ld-%s" % (name, team.lower()), vs[name],
                                                        {"subject": "%s H2LD (%s)" % (hero, names["skeletal"]),
                                                         "model": "H2LD", "team": team,
                                                         "materials": {"figure": fig_mi[team], "base": base_mi[team]}},
                                                        avg_last=AVG_LAST if (team == "Neutral" and name in mviews) else 1)
                if team == "Neutral" and a.second_exposure is not None:
                    set_exposure(a.second_exposure)
                    for name in mviews:
                        yaw(vs[name])
                        shots[(name, "ld", "Neutral-ev2")] = sh.shot(
                            "%s-ld-neutral-ev2" % name, vs[name],
                            {"subject": "%s H2LD (%s)" % (hero, names["skeletal"]), "model": "H2LD", "team": "Neutral",
                             "exposure_offset": a.second_exposure,
                             "materials": {"figure": fig_mi[team], "base": base_mi[team]}}, avg_last=AVG_LAST)
                    set_exposure(a.exposure_offset)
            still_ours()
            # masks: zones, plate, calibration, classes
            setm(zones_mi, zones_mi)
            time.sleep(2.0)
            for name in mviews:
                yaw(vs[name])
                shots[(name, "zones")] = sh.shot("%s-zones" % name, vs[name], {"model": "H2LD", "debug": "DebugZones"},
                                                 keep_jpg=(name == "front"))
            setm(classes_mi, classes_mi)
            time.sleep(1.5)
            yaw(vs["front"])
            shots[("front", "classes")] = sh.shot("front-classes", vs["front"], {"model": "H2LD", "debug": "DebugClasses"})
            # calibration: every zone id on the whole figure (front view)
            refs = {}
            sh.task("control_scene_ue.py", "set", changes=[{"label": L_BASE, "visible": False}])
            for zid in sorted(legend, key=int):
                sh.task("h2ld_lookdev_ue.py", "mid", label=L_FIG, slot=0, parent=zones_mi,
                        scalars={"DebugMatIDOverride": float(zid)})
                time.sleep(0.8)
                sh.shot("calib-%02d" % int(zid), vs["front"], {"debug": "DebugMatIDOverride %s" % zid}, keep_jpg=False,
                        settle_n=2)
            sh.task("control_scene_ue.py", "set", changes=[{"label": L_FIG, "visible": False}])
            for name in mviews:
                shots[(name, "plate")] = sh.shot("%s-plate" % name, vs[name], {"debug": "plate: figure and base hidden"},
                                                 keep_jpg=False)
            sh.task("control_scene_ue.py", "set", changes=[{"label": L_FIG, "visible": True}, {"label": L_BASE, "visible": True}])
            still_ours()
            plate_f = sh.images["front-plate"]
            for zid in legend:
                im = sh.images["calib-%02d" % int(zid)]
                fm = figure_mask(im, plate_f)
                fm = ndimage.binary_erosion(fm, iterations=3)
                refs[int(zid)] = [float(x) for x in np.median(im[fm], 0)]
            report["zone_reference_colours_srgb8"] = {str(k): [round(x, 1) for x in v] for k, v in sorted(refs.items())}
            # H2 (v1) neutral via MID + Blue
            if h2:
                sh.task("h2ld_lookdev_ue.py", "swap_mesh", label=L_FIG, mesh=h2["skeletal"])
                sh.task("h2ld_lookdev_ue.py", "mid", label=L_FIG, slot=0, parent=h2["figure_instance"],
                        scalars={"TeamDye": 0.0}, vectors={"TeamColor": [1.0, 1.0, 1.0, 1.0]})
                sh.task("control_scene_ue.py", "set", changes=[{"label": L_BASE, "materials": {"0": h2["base_instance"]}}])
                time.sleep(4.0)
                for name in mviews:
                    yaw(vs[name])
                    shots[(name, "h2", "Neutral")] = sh.shot("%s-h2-neutral" % name, vs[name],
                                                             {"subject": "%s H2 (%s), v1 M_UM_Figure, transient MID TeamDye 0"
                                                                         % (hero, h2["skeletal"]), "model": "H2",
                                                              "team": "Neutral"}, avg_last=AVG_LAST)
                if a.second_exposure is not None:
                    set_exposure(a.second_exposure)
                    for name in mviews:
                        yaw(vs[name])
                        shots[(name, "h2", "Neutral-ev2")] = sh.shot(
                            "%s-h2-neutral-ev2" % name, vs[name],
                            {"subject": "%s H2 (%s), v1, TeamDye 0" % (hero, h2["skeletal"]), "model": "H2",
                             "team": "Neutral", "exposure_offset": a.second_exposure}, avg_last=AVG_LAST)
                    set_exposure(a.exposure_offset)
                if not a.quick:
                    setm(h2["team:figure:Blue"], h2["team:base:Blue"])
                    time.sleep(2.0)
                    for name in ("front", "k2-5x-az0"):
                        yaw(vs[name])
                        shots[(name, "h2", "Blue")] = sh.shot("%s-h2-blue" % name, vs[name],
                                                              {"model": "H2", "team": "Blue",
                                                               "materials": {"figure": h2["team:figure:Blue"]}})
                sh.task("h2ld_lookdev_ue.py", "swap_mesh", label=L_FIG, mesh=names["skeletal"])
            still_ours()
        finally:
            try:
                report["cleanup"] = sh.task("control_scene_ue.py", "cleanup", labels=temp)
            except Exception as exc:  # noqa: BLE001
                report["cleanup_error"] = str(exc)
            try:
                for n, v in sg_before.items():
                    if v is not None:
                        ue.console("%s %s" % (n, v))
                        report["console"].append("%s %s" % (n, v))
                for flag in R.SHOW_FLAGS_OFF:
                    ue.console("ShowFlag.%s 2" % flag)
                    report["console"].append("ShowFlag.%s 2" % flag)
                ue.console("r.ExposureOffset 0")
                report["console"].append("r.ExposureOffset 0")
                report["exposure_offset_after"] = R.cvar_value(ue, "r.ExposureOffset")
                report["scalability_after"] = {n: R.cvar_value(ue, n) for n in R.SG}
            except Exception as exc:  # noqa: BLE001
                report["console_error"] = str(exc)
            ue.call("scene", "load_level", {"level_path": original.split(".")[0]})
            time.sleep(2.0)
            report["restored_level"] = ue.call("scene", "get_current_level", record=False)
            report["restored_level_dirty"] = ue.call("asset", "is_dirty", {"asset_path": report["restored_level"]},
                                                     record=False)
            report["review_level_dirty_after_reload"] = ue.call("asset", "is_dirty", {"asset_path": R.LEVEL}, record=False)
            report["run_assets_dirty"] = {k: ue.call("asset", "is_dirty", {"asset_path": v}, record=False)
                                          for k, v in sorted(names.items())}
            report["frames"] = sh.frames
            (out / ("h2ld-lookdev-report-%s.json" % a.tag)).write_text(
                json.dumps(report, indent=1, sort_keys=True, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n")
    # ---------------------------------------------------------------- metrics
    metrics = {"ld": {}, "h2": {}}
    labels = {}
    for name in MVIEWS:
        zone_img, plate = sh.images["%s-zones" % name], sh.images["%s-plate" % name]
        lab = classify(zone_img, figure_mask(zone_img, plate), refs)
        labels[name] = lab
        np.save(raw / ("%s-labels-ids.npy" % name), lab.astype(np.uint8))
        cov = {legend[str(z)]["zone"]: int((lab == z).sum()) for z in refs}
        metrics.setdefault("zone_pixels", {})[name] = cov
        Image.fromarray((np.array([[0, 0, 0]] + [refs[int(z)] for z in sorted(legend, key=int)], np.uint8))[lab])\
            .save(raw / ("%s-labels.png" % name))

    def measure(suffix):
        """zone stats of the Neutral H2LD (and H2) frames of one exposure; k over K_VIEWS of H2LD, same k for H2"""
        res = {"ld": {}, "h2": {}}
        for name in MVIEWS:
            if ("%s-ld-neutral%s" % (name, suffix)) in sh.images:
                res["ld"][name] = zone_stats(sh.images["%s-ld-neutral%s" % (name, suffix)], labels[name], legend)
            if ("%s-h2-neutral%s" % (name, suffix)) in sh.images:
                res["h2"][name] = zone_stats(sh.images["%s-h2-neutral%s" % (name, suffix)], labels[name], legend)
        ratios = []
        for name in K_VIEWS:
            cv = report["concept"][vs[name]["concept"]]
            for z, s_ in res["ld"].get(name, {}).items():
                if z in K_EXCLUDE:
                    continue
                if "luma_Y" in s_ and "luma_Y" in (cv.get(z) or {}):
                    ratios.append(cv[z]["luma_Y"] / max(s_["luma_Y"], 1e-6))
        k_ = float(np.median(ratios)) if ratios else 1.0
        res["k"] = round(k_, 4)
        res["k_note"] = ("k = median over zones and views %s of concept Y / UE Y of the H2LD Neutral frames (LDM-6 "
                         "method), without %s; the same k scales H2" % (list(K_VIEWS), K_EXCLUDE))
        for model in ("ld", "h2"):
            per_view = {name: compare(res[model][name], report["concept"][vs[name]["concept"]], k_)
                        for name in res[model]}
            res[model + "_compare"] = per_view
            res[model + "_summary"] = summarise(per_view)
        res["tolerance_result"] = {z: res["ld_summary"].get(z) for z in TOLERANCE_ZONES}
        return res

    base_m = measure("")
    metrics.update(base_m)
    k = base_m["k"]
    metrics["exposure_offset"] = a.exposure_offset
    if a.second_exposure is not None:
        ev2 = measure("-ev2")
        ev2["exposure_offset"] = a.second_exposure
        metrics["second_exposure"] = ev2
        both = {}
        for z in TOLERANCE_ZONES:
            s1, s2 = base_m["ld_summary"].get(z) or {}, ev2["ld_summary"].get(z) or {}
            both[z] = {"exposure_%g" % a.exposure_offset: s1.get("pass"),
                       "exposure_%g" % a.second_exposure: s2.get("pass"),
                       "both": bool(s1.get("pass") and s2.get("pass"))}
        metrics["tolerance_both_exposures"] = both
    (out / ("h2ld-lookdev-metrics-%s.json" % a.tag)).write_text(
        json.dumps(metrics, indent=1, sort_keys=True, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n")
    # ---------------------------------------------------------------- sheets
    def img_of(name):
        return Image.fromarray(sh.images[name]) if name in sh.images else None
    rows = []
    for name in ("front", "side", "back"):
        cells = [("концепт", Image.open(concept_dir / ("%s-%s.png" % (hero.lower(), vs[name]["concept"]))).convert("RGB"), False),
                 ("UE H2 (v1, без красителя)", img_of("%s-h2-neutral" % name), True),
                 ("UE H2LD (v2, без красителя)", img_of("%s-ld-neutral" % name), True)]
        rows.append((name, cells))
    p = out / ("%s-h2ld-sheet-concept-%s.jpg" % (hero.lower(), a.tag))
    report_sheets = {p.name: R.sheet(rows, 620, 700, "%s · концепт | UE H2 | UE H2LD · редактор, DX12/SM6 + Lumen, High, "
                                     "свет Cobble, k = %.2f · диагностика, не приёмка" % (hero, k), p)}
    if not a.quick:
        rows = []
        for name in ("front", "side", "back", "torso", "k2-5x-az0", "k2-5x-az180", "k2-1p6-az0"):
            rows.append((name, [("H2LD %s" % t, img_of("%s-ld-%s" % (name, t.lower())), name in ("front", "side", "back", "torso"))
                                for t in ("Neutral", "Blue", "Red")]))
        p = out / ("%s-h2ld-sheet-teams-%s.jpg" % (hero.lower(), a.tag))
        report_sheets[p.name] = R.sheet(rows, 620, 460, "%s H2LD · без красителя | Blue | Red · Cobble, High" % hero, p)
    rows = []
    bid = [int(z) for z, rec in legend.items() if rec["zone"] == "buckle"]

    def buckle_crop(im, name):
        """the buckle region of a frame (bbox of the largest piece of the buckle zone + margin, 2:1), 4x upscale"""
        if im is None or not bid or name not in labels or not (labels[name] == bid[0]).any():
            return im
        comp, n = ndimage.label(labels[name] == bid[0])
        big = 1 + int(np.argmax(ndimage.sum(np.ones_like(comp), comp, range(1, n + 1))))  # largest piece of the zone
        ys, xs = np.nonzero(comp == big)
        cx, cy = (xs.min() + xs.max()) / 2.0, (ys.min() + ys.max()) / 2.0
        half_w = max(xs.max() - xs.min(), 2 * (ys.max() - ys.min())) * 1.1 + 20
        box = (int(cx - half_w), int(cy - half_w / 2), int(cx + half_w), int(cy + half_w / 2))
        c = im.crop(box)
        return c.resize((c.width * 4, c.height * 4), Image.LANCZOS)

    for name in ("torso", "buckle", "buckle-q"):
        rows.append((name, [("UE H2 (v1)", buckle_crop(img_of("%s-h2-neutral" % name), name), False),
                            ("UE H2LD", buckle_crop(img_of("%s-ld-neutral" % name), name), False),
                            ("UE H2LD, EV %+g" % (a.second_exposure or 0),
                             buckle_crop(img_of("%s-ld-neutral-ev2" % name), name), False),
                            ("зоны", buckle_crop(img_of("%s-zones" % name), name), False)]))
    cimg = Image.open(concept_dir / ("%s-front.png" % hero.lower())).convert("RGB").crop((545, 520, 625, 580))
    cimg = cimg.resize((cimg.width * 6, cimg.height * 6), Image.LANCZOS)
    rows.append(("концепт front", [("концепт, пряжка (x6)", cimg, False)]))
    p = out / ("%s-h2ld-sheet-buckle-%s.jpg" % (hero.lower(), a.tag))
    report_sheets[p.name] = R.sheet(rows, 560, 300, "%s · пряжка (вырезка по маске зоны): H2 | H2LD | H2LD при второй "
                                    "экспозиции | маска зон · Cobble, High" % hero, p)
    if a.second_exposure is not None:
        rows = []
        for name in ("front", "side", "back"):
            rows.append((name, [("концепт", Image.open(concept_dir / ("%s-%s.png" % (hero.lower(), vs[name]["concept"])))
                                 .convert("RGB"), False),
                                ("UE H2, EV %+g" % a.second_exposure, img_of("%s-h2-neutral-ev2" % name), True),
                                ("UE H2LD, EV %+g" % a.second_exposure, img_of("%s-ld-neutral-ev2" % name), True)]))
        p = out / ("%s-h2ld-sheet-concept-ev2-%s.jpg" % (hero.lower(), a.tag))
        report_sheets[p.name] = R.sheet(rows, 620, 700, "%s · концепт | UE H2 | UE H2LD · r.ExposureOffset %+g "
                                        "(вторая экспозиция), k = %.2f · диагностика" % (
                                            hero, a.second_exposure, metrics["second_exposure"]["k"]), p)
    rows = [("маски", [("классы MatID", img_of("front-classes"), True), ("зоны front", img_of("front-zones"), True),
                       ("зоны side", img_of("side-zones"), True), ("зоны back", img_of("back-zones"), True)])]
    p = out / ("%s-h2ld-sheet-masks-%s.jpg" % (hero.lower(), a.tag))
    report_sheets[p.name] = R.sheet(rows, 480, 620, "%s H2LD · отладочные MI: классы и зоны замера" % hero, p)
    print(json.dumps({"k": metrics["k"], "sheets": report_sheets}, indent=1))
    for label, mm in [("EV%+g" % a.exposure_offset, metrics)] + (
            [("EV%+g" % a.second_exposure, metrics["second_exposure"])] if a.second_exposure is not None else []):
        print("--", label, "k", mm["k"])
        for z, s in sorted(mm["ld_summary"].items()):
            hs = mm["h2_summary"].get(z) or {}
            print("%-11s LD luma %s hue %s sat %s %s (%s views) | H2 luma %s hue %s sat %s" % (
                z, s.get("luma_ratio"), s.get("hue_delta_deg"), s.get("sat_delta"),
                ("PASS" if s.get("pass") else "FAIL") if s.get("views") else "-", s.get("views"),
                hs.get("luma_ratio"), hs.get("hue_delta_deg"), hs.get("sat_delta")))


if __name__ == "__main__":
    main()
