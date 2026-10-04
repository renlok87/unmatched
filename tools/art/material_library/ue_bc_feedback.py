"""UE feedback for a BC edit on the Blender stage (5c-B0, 2026-09-30): predict the UE zone medians of a hero after a
per-channel change of one class's albedo, from the UE look-dev frames already shot (no editor).

    # fit: the per-channel ratio r of the class's EFFECTIVE albedo (after the v2 dielectric clamp) that brings the zone
    # to the concept on the reading exposure (and as close as possible on the board exposure)
    python tools/art/material_library/ue_bc_feedback.py fit --config <review json> --frames <review/iN> --tag iN \
        --zone belt --select class [--weights reading=1,neutral=0.5] --out <json>

    # gain: the BC gain of the class texels (2K BC + MatID of the look-dev run, UE LUT column) for that ratio
    python tools/art/material_library/ue_bc_feedback.py gain --bc <BC_2K.png> --matid <MatID_2K.png> --class-id belt_class         --lut-report <UE LUT report.json> --ratio 0.99,1.32,1.78 [--texel-mask <L png>] --out <json>

    # predict: apply a ratio to the frames (copies in a scratch dir) and run ue_hero_lookdev.cmd_measure on them
    python tools/art/material_library/ue_bc_feedback.py predict --config <review json> --frames <review/iN> --tag iN \
        --zone belt --select class --ratio 0.9,0.95,1.1 --out <dir>

Model (diffuse): a lit pixel of a dielectric = light x effective albedo per channel, so a change of the effective albedo
of the class by r (per channel, linear) multiplies the linear pixel by r. The pixels changed are those of the zone's
MatID class decoded from the debug frame (select "class"), or of the render gate of the zone (select "gate", every
gated pixel: an upper bound when the gate also takes pixels of texels the edit does not touch; "gate_lowsat": the gated
pixels below --sat-max on the gate frame, e.g. Harpy's dark primaries without the shaded rufous coverts), or the class pixels the
team dye changes (select "dye": |P1 - P2| > 40 levels, the TeamAccent texels = e.g. Harpy's dark primary tips, a clean
sample of the edited texels). Specular / sheen are not separated (they dilute the change: the prediction is an upper
bound of the change of saturation). Measurement = ue_hero_lookdev.cmd_measure itself (same masks, gates, medians, k).
This is a PREDICTION from editor frames; the orchestrator re-shoots UE after the reimport.
"""
from __future__ import annotations

import argparse
import json
import math
import shutil
import sys
import tempfile
from pathlib import Path

import numpy as np
from PIL import Image
from scipy.optimize import minimize

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import ue_hero_lookdev as U  # noqa: E402

REPO = U.REPO


def lin(c):
    return U.lin(c)


def srgb(x):
    x = np.clip(x, 0.0, 1.0)
    return np.where(x <= 0.0031308, x * 12.92, 1.055 * np.power(x, 1 / 2.4) - 0.055)


def load_masks(cfg, frames: Path, tag: str):
    presets = json.loads((REPO / "docs/art-pipeline/material-library/um-material-presets-v1.json").read_text(encoding="utf-8"))
    ids = {c["id"]: c["index"] for c in presets["classes"]}
    cls_of = U.zone_classes(cfg, ids)
    classes = sorted({c for cs in cls_of.values() for c in cs} | {ids[c] for c in cfg.get("decode_classes") or []} | {0})
    masks = {}
    for view in U.ORTHO:
        dbg = U.load_frame(frames, cfg["hero"], tag, "%s-debug" % view)
        plate = U.load_frame(frames, cfg["hero"], tag, "%s-plate" % view)
        if dbg is None or plate is None:
            continue
        cls, _ch = U.decode_debug(dbg, plate, classes, cfg.get("debug_calibration"))
        masks[view] = cls
    return masks, cls_of


def select_pixels(cfg, frames, tag, masks, cls_of, zone, select, sat_max=0.38):
    """view -> bool mask of the pixels the edit changes."""
    out = {}
    teams = U.teams_of(cfg)
    gates = cfg.get("render_gates") or {}
    for view, cls in masks.items():
        m = U.zone_mask(cls, cls_of[zone])
        reg = U.zone_region(cfg, zone, view, cls)
        if reg is not None:
            m &= reg
        if select in ("gate", "gate_lowsat") and zone in gates:
            ref = U.load_frame(frames, cfg["hero"], tag, "%s-%s" % (view, (cfg.get("gate_on_variant") or "neutral").lower()))
            g = np.zeros(m.shape, bool)
            g[m] = U.gate(ref[m], gates[zone])
            if select == "gate_lowsat":
                # gated pixels whose lit colour is below sat_max (Harpy: the dark primaries, sat 0.1-0.3, apart from
                # the shaded rufous coverts the value gate also takes, sat 0.4-0.7)
                _h, s_, _v = U.rgb_to_hsv(ref.astype(np.float32) / 255.0)
                g &= s_ < float(sat_max)
            m = g
        elif select == "dye":
            a = U.load_frame(frames, cfg["hero"], tag, "%s-%s" % (view, teams[0].lower()))
            b = U.load_frame(frames, cfg["hero"], tag, "%s-%s" % (view, teams[1].lower()))
            m = m & (np.abs(a.astype(np.int16) - b.astype(np.int16)).max(-1) > U.ACCENT_THRESH)
        out[view] = m
    return out


def apply_ratio(img8, sel, r):
    x = img8.astype(np.float64) / 255.0
    y = x.copy()
    y[sel] = srgb(lin(x[sel]) * np.asarray(r)[None, :])
    return np.round(y * 255.0).clip(0, 255).astype(np.uint8)


def predict(cfg, frames: Path, tag: str, sel: dict, r, scratch: Path, variants=("neutral", "reading")):
    """Copies the frames of the tag into scratch/frames, applies r to the selected pixels of the given variants and
    runs ue_hero_lookdev.cmd_measure there; returns its result (measure-<tag>.json in scratch)."""
    fd = scratch / "frames"
    fd.mkdir(parents=True, exist_ok=True)
    for p in (frames / "frames").glob("%s-%s-*.png" % (cfg["hero"].lower(), tag)):
        shutil.copyfile(p, fd / p.name)
    for view, m in sel.items():
        for var in variants:
            p = fd / ("%s-%s-%s-%s.png" % (cfg["hero"].lower(), tag, view, var.lower()))
            if p.is_file():
                Image.fromarray(apply_ratio(np.asarray(Image.open(p).convert("RGB")), m, r)).save(p)
    a = argparse.Namespace(out=str(scratch), tag=tag)
    return U.cmd_measure(a, cfg)


class Fast:
    """In-memory copy of cmd_measure for the fit (same pooling, medians, k, deltas; accent metrics left out)."""

    def __init__(self, cfg, frames, tag, masks, cls_of, sel, variants=("neutral", "reading"), restrict_zone=None):
        """restrict_zone: measure that zone on the selected (changed) pixels only (e.g. the dye-identified texels);
        the exposure k is then fixed to the one of the unrestricted measurement (the key zones unchanged)."""
        self.cfg, self.variants, self.restrict = cfg, variants, restrict_zone
        self.k_fixed = None
        concept = json.loads((REPO / cfg["concept_zones"]).read_text(encoding="utf-8"))["zones"]
        gates = cfg.get("render_gates") or {}
        gate_on = cfg.get("gate_on_variant")
        self.concept = {z: concept.get(z, {}).get("concept") for z in cfg["zones"]}
        self.px = {}      # (zone, var) -> (pixels uint8 [N,3], changed bool [N])
        for view, cls in masks.items():
            for zone in cfg["zones"]:
                m = U.erode(U.zone_mask(cls, cls_of[zone]), 1)
                reg = U.zone_region(cfg, zone, view, cls)
                if reg is not None:
                    m &= reg
                gm = None
                if gate_on and zone in gates:
                    ref = U.load_frame(frames, cfg["hero"], tag, "%s-%s" % (view, gate_on.lower()))
                    gm = U.gate(ref[m], gates[zone])
                for var in variants:
                    beauty = U.load_frame(frames, cfg["hero"], tag, "%s-%s" % (view, var.lower()))
                    px, ch = beauty[m], sel.get(view, np.zeros(m.shape, bool))[m]
                    if gm is not None:
                        px, ch = px[gm], ch[gm]
                    elif zone in gates and len(px):
                        g = U.gate(px, gates[zone])
                        px, ch = px[g], ch[g]
                    if zone == restrict_zone:
                        px, ch = px[ch], ch[ch]
                    if len(px) < int(cfg.get("min_px", 150)):
                        continue
                    a, b = self.px.get((zone, var), (np.zeros((0, 3), np.uint8), np.zeros(0, bool)))
                    self.px[(zone, var)] = (np.concatenate([a, px]), np.concatenate([b, ch]))

    def measure(self, r):
        zones = {}
        for (zone, var), (px, ch) in self.px.items():
            p = px
            if ch.any() and r is not None:
                p = px.copy()
                p[ch] = apply_ratio(px[ch][:, None, :], np.ones((int(ch.sum()), 1), bool), r)[:, 0, :]
            zones.setdefault(zone, {})[var] = U.hsv_stats(p)
        tol = self.cfg["tolerance"]
        res = {}
        for var in self.variants:
            key = [z for z in self.cfg["key_zones"] if var in zones.get(z, {}) and self.concept.get(z)]
            lr = [math.log(self.concept[z]["luma_Y_linear"] / max(zones[z][var]["luma_Y_linear"], 1e-5)) for z in key]
            k = math.exp(sum(lr) / len(lr)) if not self.k_fixed else self.k_fixed[var]
            d = {}
            for z, zz in zones.items():
                c = self.concept.get(z)
                if var not in zz or not c:
                    continue
                u = zz[var]
                yr = u["luma_Y_linear"] / max(c["luma_Y_linear"] / k, 1e-6)
                dh = ((u["hue_deg"] - c["hue_deg"] + 180.0) % 360.0) - 180.0
                ds = u["sat"] - c["sat"]
                hd = c["sat"] >= float(tol.get("hue_min_sat", 0.0))
                ok = abs(yr - 1) <= tol["luma_ratio"] and (abs(dh) <= tol["hue_deg"] or not hd) and abs(ds) <= tol["sat"]
                d[z] = {"Y_ratio": round(yr, 3), "dHue_deg": round(dh, 1), "dSat": round(ds, 3), "hue_defined": hd,
                        "all_within": bool(ok), "median_srgb": u["median_srgb"]}
            res[var] = {"k": round(k, 4), "deltas": d}
        return res


def cost(res, zone, weights, tol, sat_target=0.0, y_target=None):
    """y_target: {variant: Y ratio to keep} (--keep-luma: only the chroma moves), default 1.0 (the concept)."""
    c = 0.0
    for var, w in weights.items():
        d = res[var]["deltas"][zone]
        yt = 1.0 if not y_target else y_target[var]
        c += w * (((d["Y_ratio"] - yt) / tol["luma_ratio"]) ** 2 + ((d["dSat"] - sat_target) / tol["sat"]) ** 2
                  + ((d["dHue_deg"] / tol["hue_deg"]) ** 2 if d["hue_defined"] else 0.0))
    return c


def cmd_fit(a, cfg):
    frames = Path(a.frames)
    masks, cls_of = load_masks(cfg, frames, a.tag)
    sel = select_pixels(cfg, frames, a.tag, masks, cls_of, a.zone, a.select, a.sat_max)
    fast = Fast(cfg, frames, a.tag, masks, cls_of, sel)
    if a.restrict:
        full = fast.measure(None)
        fast = Fast(cfg, frames, a.tag, masks, cls_of, sel, restrict_zone=a.zone)
        fast.k_fixed = {v: full[v]["k"] for v in full}
    weights = {kv.split("=")[0]: float(kv.split("=")[1]) for kv in a.weights.split(",")}
    tol = cfg["tolerance"]
    before = fast.measure(None)

    y_t = {v: before[v]["deltas"][a.zone]["Y_ratio"] for v in before} if a.keep_luma else None

    def f(logr):
        return cost(fast.measure(np.exp(logr)), a.zone, weights, tol, a.sat_target, y_t)

    # log-ratio simplex of +-0.2 (the default 0.00025 step of a zero start is below the 8-bit rounding: flat cost)
    simplex = np.array([[0.0, 0.0, 0.0], [0.2, 0.0, 0.0], [0.0, 0.2, 0.0], [0.0, 0.0, 0.2]])
    best = minimize(f, np.zeros(3), method="Nelder-Mead",
                    options={"xatol": 2e-3, "fatol": 1e-4, "maxiter": 600, "initial_simplex": simplex})
    r = np.exp(best.x)
    after = fast.measure(r)
    out = {"schema": "unmatched.ue-bc-feedback-fit/1", "hero": cfg["hero"], "tag": a.tag, "zone": a.zone,
           "select": a.select, "restricted_to_changed_pixels": bool(a.restrict), "changed_pixels_by_view": {v: int(m.sum()) for v, m in sel.items()},
           "weights": weights, "sat_target": a.sat_target, "keep_luma": bool(a.keep_luma), "ratio_effective_albedo_linear": [round(float(x), 4) for x in r],
           "before": {v: before[v]["deltas"][a.zone] | {"k": before[v]["k"]} for v in before},
           "predicted": {v: after[v]["deltas"][a.zone] | {"k": after[v]["k"]} for v in after},
           "other_zones_predicted_all_within_unchanged": {
               v: {z: (before[v]["deltas"][z]["all_within"], after[v]["deltas"][z]["all_within"])
                   for z in before[v]["deltas"] if z != a.zone} for v in before},
           "model": __doc__.split("Model (diffuse): ")[1].split("\nThis is")[0].replace("\n", " ")}
    Path(a.out).parent.mkdir(parents=True, exist_ok=True)
    Path(a.out).write_text(json.dumps(out, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps({k: out[k] for k in ("ratio_effective_albedo_linear", "before", "predicted")}, indent=1))
    return out


def cmd_predict(a, cfg):
    frames = Path(a.frames)
    masks, cls_of = load_masks(cfg, frames, a.tag)
    sel = select_pixels(cfg, frames, a.tag, masks, cls_of, a.zone, a.select, a.sat_max)
    r = [float(x) for x in a.ratio.split(",")]
    out = Path(a.out)
    with tempfile.TemporaryDirectory(dir=str(out.parent) if out.parent.exists() else None) as td:
        res = predict(cfg, frames, a.tag, sel, r, Path(td))
    out.mkdir(parents=True, exist_ok=True)
    res["prediction"] = {"zone": a.zone, "select": a.select, "ratio_effective_albedo_linear": r,
                         "frames": U.rel(frames), "note": "PREDICTION: UE frames of %s with the linear pixels of the "
                                                          "selected zone pixels x ratio (ue_bc_feedback.py)" % a.tag}
    U.write_json(out / ("measure-%s-pred.json" % a.tag), res)
    return res


LUMA = np.array([0.2126, 0.7152, 0.0722])


def effective(bc, lo, hi, maxc):
    """v2 core dielectric path (um_v2_core.hlsl): luminance clamped to [lo, hi] keeping the chroma, channel ceiling."""
    y = np.maximum(bc @ LUMA, 1e-5)
    return np.minimum(bc * (np.clip(y, lo, hi) / y)[:, None], maxc)


def solve_gain(bc, r, lo, hi, maxc, iters=40):
    """Per-channel gain g of the BC texels (linear, N x 3) such that the per-channel median of the effective albedo
    changes by r: median(eff(bc x g)) / median(eff(bc)) = r (the clamp makes g != r where the floor holds)."""
    r = np.asarray(r, np.float64)
    m0 = np.median(effective(bc, lo, hi, maxc), 0)
    g = r.copy()
    for _ in range(iters):
        got = np.median(effective(np.minimum(bc * g, 1.0), lo, hi, maxc), 0) / m0
        g = g * (r / got) ** 0.7
    got = np.median(effective(np.minimum(bc * g, 1.0), lo, hi, maxc), 0) / m0
    return g, got


def lut_column(report: Path, class_id: str):
    presets = json.loads((REPO / "docs/art-pipeline/material-library/um-material-presets-v1.json").read_text(encoding="utf-8"))
    idx = {c["id"]: c["index"] for c in presets["classes"]}
    col = json.loads(Path(report).read_text(encoding="utf-8"))["columns"][str(idx[class_id])]
    return idx[class_id], col


def cmd_gain(a, cfg=None):
    """BC gain of a class (2K BC + MatID of the look-dev run, the UE LUT column of the class) for a fitted ratio."""
    ci, col = lut_column(Path(a.lut_report), a.class_id)
    bc = lin(np.asarray(Image.open(a.bc).convert("RGB"), np.float64) / 255.0)
    mid = np.asarray(Image.open(a.matid)) // 16
    sel = mid == ci
    if a.texel_mask:
        tm = np.asarray(Image.open(a.texel_mask).convert("L")) >= 128
        sel &= tm
    r = [float(x) for x in a.ratio.split(",")]
    g, got = solve_gain(bc[sel], r, col["luminanceMin"], col["luminanceMax"], col["maxChannel"])
    b0, b1 = bc[sel], np.minimum(bc[sel] * g, 1.0)
    e0, e1 = effective(b0, col["luminanceMin"], col["luminanceMax"], col["maxChannel"]),         effective(b1, col["luminanceMin"], col["luminanceMax"], col["maxChannel"])

    def hsv_of(lin_rgb):
        h, s_, v = U.rgb_to_hsv(srgb(np.median(lin_rgb, 0))[None, :])
        return {"median_linear": [round(float(x), 5) for x in np.median(lin_rgb, 0)],
                "Y_median": round(float(np.median(lin_rgb @ LUMA)), 5), "hue_deg": round(float(h[0]), 1),
                "sat": round(float(s_[0]), 3)}

    out = {"class": a.class_id, "texels_2k": int(sel.sum()), "ratio_effective_target": r,
           "gain_bc_linear": [round(float(x), 4) for x in g], "ratio_effective_got": [round(float(x), 4) for x in got],
           "lut_column": {k: col[k] for k in ("luminanceMin", "luminanceMax", "maxChannel", "specular")},
           "floor_clamped_share_before": round(float(((b0 @ LUMA) < col["luminanceMin"]).mean()), 4),
           "floor_clamped_share_after": round(float(((b1 @ LUMA) < col["luminanceMin"]).mean()), 4),
           "bc_before": hsv_of(b0), "bc_after": hsv_of(b1), "effective_before": hsv_of(e0), "effective_after": hsv_of(e1)}
    print(json.dumps(out, indent=1))
    if a.out:
        Path(a.out).write_text(json.dumps(out, indent=1) + "\n", encoding="utf-8")
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("command", choices=["fit", "predict", "gain"])
    ap.add_argument("--config")
    ap.add_argument("--frames")
    ap.add_argument("--tag")
    ap.add_argument("--zone")
    ap.add_argument("--bc")
    ap.add_argument("--matid")
    ap.add_argument("--class-id")
    ap.add_argument("--lut-report")
    ap.add_argument("--texel-mask")
    ap.add_argument("--select", default="class", choices=["class", "gate", "gate_lowsat", "dye"])
    ap.add_argument("--sat-max", type=float, default=0.38)
    ap.add_argument("--weights", default="reading=1,neutral=0.5")
    ap.add_argument("--sat-target", type=float, default=0.0)
    ap.add_argument("--keep-luma", action="store_true", help="keep the zone's Y ratio, move only the chroma")
    ap.add_argument("--restrict", action="store_true", help="measure the zone on the changed pixels only (k of the full zone)")
    ap.add_argument("--ratio")
    ap.add_argument("--out")
    a = ap.parse_args()
    if a.command == "gain":
        cmd_gain(a)
        return 0
    cfg = json.loads(Path(a.config).read_text(encoding="utf-8"))
    {"fit": cmd_fit, "predict": cmd_predict}[a.command](a, cfg)
    return 0


if __name__ == "__main__":
    sys.exit(main())
