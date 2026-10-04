"""Look-dev round 2 (2026-09-30, after 5c-B1): joint BC-ratio fit and forecast on the CONVERGED UE frames b1 of a hero,
several zones at once (no editor, no Blender, no render).

    # measure the b1 frames with a review config (scratch copy of the frames: cmd_measure writes class maps there)
    python tools/art/material_library/lookdev_r2.py measure --config <review json> --frames <review/b1> --tag b1 \
        --scratch C:/tmp/lr2/<hero> [--out <json>]

    # joint fit of the effective-albedo ratios of several zones (each zone: its MatID class pixels, render region and
    # gate of the config), weights reading=1 / neutral=0.5, every other zone kept within tolerance when it was
    python tools/art/material_library/lookdev_r2.py fit --config <review json> --frames <review/b1> --tag b1 \
        --zones skin,leather_smooth [--keep-luma skin] [--weights reading=1,neutral=0.5] --out <json>

    # forecast: the frames with the linear pixels of each zone x its ratio, measured by ue_hero_lookdev.cmd_measure
    python tools/art/material_library/lookdev_r2.py forecast --config <review json> --frames <review/b1> --tag b1 \
        --ratio skin=0.93,1.0,1.12 --ratio leather_smooth=1.2,1.3,1.4 --scratch C:/tmp/lr2/<hero> [--edit-config <json: its zone definitions pick the edited pixels>] --out <json>

Model = ue_bc_feedback.py (diffuse: a lit dielectric pixel = light x effective albedo per channel, so a ratio r of the
class's effective albedo multiplies the linear pixel by r; specular / sheen / Lumen bounce are not separated: the
forecast is an upper bound of the change). Frames: the b1 capture of 5c-B1 (warm-up 0.48-0.64, converged): neutral =
EV100 1.3 (board exposure of look-dev C), reading = reading_bias_ev of the config (-0.75 EV = EV100 2.05, rev 5).
PREDICTION, not a capture: the UE re-shoot after 5c-B2 measures.
"""
from __future__ import annotations

import argparse
import contextlib
import io
import json
import math
import shutil
import sys
from pathlib import Path

import numpy as np
from PIL import Image
from scipy.optimize import minimize

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import ue_bc_feedback as F  # noqa: E402
import ue_hero_lookdev as U  # noqa: E402

REPO = U.REPO


def load_cfg(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def zone_sel(cfg, frames: Path, tag: str, masks, cls_of, zone: str) -> dict:
    """view -> pixels the BC edit of the zone changes: the zone's class (render region applied) and, when the zone has
    a render gate on the gate variant, the gated pixels (the pixels the zone measures)."""
    sel = F.select_pixels(cfg, frames, tag, masks, cls_of, zone, "gate" if zone in (cfg.get("render_gates") or {})
                          else "class")
    return sel


class Multi:
    """In-memory cmd_measure (same masks, regions, gates, pooled medians, k, deltas) with several edited groups."""

    def __init__(self, cfg, frames: Path, tag: str, edits: list[str], variants=("neutral", "reading"), sel_cfg=None):
        """sel_cfg: the config whose zone definitions (regions, gates) pick the EDITED pixels (default cfg): e.g. the
        texels of the outer primaries edited, measured with the old whole-frame zone definition."""
        self.cfg, self.variants, self.edits = cfg, variants, edits
        masks, cls_of = F.load_masks(cfg, frames, tag)
        sels = {z: zone_sel(sel_cfg or cfg, frames, tag, masks, cls_of, z) for z in edits}
        concept = json.loads((REPO / cfg["concept_zones"]).read_text(encoding="utf-8"))["zones"]
        gates = cfg.get("render_gates") or {}
        gate_on = cfg.get("gate_on_variant")
        self.concept = {z: concept.get(z, {}).get("concept") for z in cfg["zones"]}
        self.px = {}
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
                grp = np.full(int(m.sum()), -1, np.int16)
                for gi, z in reversed(list(enumerate(edits))):
                    grp[sels[z][view][m]] = gi
                for var in variants:
                    beauty = U.load_frame(frames, cfg["hero"], tag, "%s-%s" % (view, var.lower()))
                    px, g = beauty[m], grp
                    if gm is not None:
                        px, g = px[gm], g[gm]
                    elif zone in gates and len(px):
                        k = U.gate(px, gates[zone])
                        px, g = px[k], g[k]
                    if len(px) < int(cfg.get("min_px", 150)):
                        continue
                    a, b = self.px.get((zone, var), (np.zeros((0, 3), np.uint8), np.zeros(0, np.int16)))
                    self.px[(zone, var)] = (np.concatenate([a, px]), np.concatenate([b, g]))
        self.changed_px = {z: {v: int(s.sum()) for v, s in sels[z].items()} for z in edits}

    def measure(self, ratios: dict | None):
        zones = {}
        for (zone, var), (px, g) in self.px.items():
            p = px
            if ratios:
                p = px.copy()
                for gi, z in enumerate(self.edits):
                    r = ratios.get(z)
                    sel = g == gi
                    if r is None or not sel.any():
                        continue
                    p[sel] = F.apply_ratio(px[sel][:, None, :], np.ones((int(sel.sum()), 1), bool), r)[:, 0, :]
            zones.setdefault(zone, {})[var] = U.hsv_stats(p)
        tol = self.cfg["tolerance"]
        res = {}
        for var in self.variants:
            key = [z for z in self.cfg["key_zones"] if var in zones.get(z, {}) and self.concept.get(z)]
            lr = [math.log(self.concept[z]["luma_Y_linear"] / max(zones[z][var]["luma_Y_linear"], 1e-5)) for z in key]
            k = math.exp(sum(lr) / len(lr))
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
            res[var] = {"k": round(k, 4), "deltas": d,
                        "within": sum(1 for z in self.cfg["tolerance_zones"] if d.get(z, {}).get("all_within")),
                        "of": len(self.cfg["tolerance_zones"])}
        return res


def margin_cost(d, tol, keep_luma_y=None):
    """0 inside half the tolerance, quadratic outside (normalised by the tolerance)."""
    yt = 1.0 if keep_luma_y is None else keep_luma_y
    c = ((d["Y_ratio"] - yt) / tol["luma_ratio"]) ** 2 + (d["dSat"] / tol["sat"]) ** 2
    if d["hue_defined"]:
        c += (d["dHue_deg"] / tol["hue_deg"]) ** 2
    return c


def cmd_fit(a, cfg):
    frames = Path(a.frames)
    zs = [z for z in a.zones.split(",") if z]
    keep = set((a.keep_luma or "").split(",")) - {""}
    mf = Multi(cfg, frames, a.tag, zs)
    weights = {kv.split("=")[0]: float(kv.split("=")[1]) for kv in a.weights.split(",")}
    tol = cfg["tolerance"]
    before = mf.measure(None)
    y_keep = {z: {v: before[v]["deltas"][z]["Y_ratio"] for v in before} for z in keep}
    others_ok = {v: {z: d["all_within"] for z, d in before[v]["deltas"].items() if z not in zs
                     and z in cfg["tolerance_zones"]} for v in before}

    def f(x):
        rat = {z: np.exp(x[3 * i:3 * i + 3]) for i, z in enumerate(zs)}
        res = mf.measure(rat)
        c = 0.0
        for var, w in weights.items():
            for z in zs:
                c += w * margin_cost(res[var]["deltas"][z], tol, y_keep.get(z, {}).get(var))
            for z, was in others_ok[var].items():
                if was and not res[var]["deltas"][z]["all_within"]:
                    c += 50.0 * w
        # regulariser: small edits preferred
        c += 0.05 * float(np.sum(x ** 2))
        return c

    n = 3 * len(zs)
    simplex = np.vstack([np.zeros(n)] + [np.eye(n)[i] * 0.2 for i in range(n)])
    best = minimize(f, np.zeros(n), method="Nelder-Mead",
                    options={"xatol": 2e-3, "fatol": 1e-4, "maxiter": 400 * n, "initial_simplex": simplex})
    rat = {z: [round(float(v), 4) for v in np.exp(best.x[3 * i:3 * i + 3])] for i, z in enumerate(zs)}
    after = mf.measure({z: np.array(r) for z, r in rat.items()})
    out = {"schema": "unmatched.lookdev-r2-fit/1", "hero": cfg["hero"], "tag": a.tag, "zones": zs,
           "keep_luma": sorted(keep), "weights": weights, "ratio_effective_albedo_linear": rat,
           "changed_pixels_by_view": mf.changed_px, "before": before, "predicted": after,
           "cost": round(float(best.fun), 4), "model": __doc__.split("Model = ")[1].split("\nPREDICTION")[0].replace("\n", " ")}
    if a.out:
        U.write_json(Path(a.out), out)
    table(cfg, before, "before")
    table(cfg, after, "after %s" % json.dumps(rat))
    return out


def table(cfg, res, label):
    for var in ("reading", "neutral"):
        if var not in res:
            continue
        r = res[var]
        cells = ["%s %.2f/%+.1f/%+.3f%s" % (z, d["Y_ratio"], d["dHue_deg"], d["dSat"], "+" if d["all_within"] else "x")
                 for z, d in r["deltas"].items()]
        print("%-40s %-8s k %.3f %d/%d | %s" % (label[:40], var, r["k"], r["within"], r["of"], " | ".join(cells)))


def cmd_forecast(a, cfg):
    frames = Path(a.frames)
    ratios = {}
    for item in a.ratio or []:
        z, r = item.split("=")
        ratios[z] = np.array([float(x) for x in r.split(",")])
    mf = Multi(cfg, frames, a.tag, list(ratios), sel_cfg=load_cfg(a.edit_config) if a.edit_config else None)
    before, after = mf.measure(None), mf.measure(ratios)
    out = {"schema": "unmatched.lookdev-r2-forecast/1", "hero": cfg["hero"], "tag": a.tag,
           "ratio_effective_albedo_linear": {z: [float(x) for x in r] for z, r in ratios.items()},
           "changed_pixels_by_view": mf.changed_px, "before": before, "forecast": after,
           "note": "PREDICTION on the converged b1 editor frames (diffuse model, upper bound), not a capture"}
    if a.out:
        U.write_json(Path(a.out), out)
    table(cfg, before, "before")
    table(cfg, after, "forecast")
    return out


def cmd_measure(a, cfg):
    """cmd_measure on a scratch copy of the frames (the repo review dir is not written)."""
    scratch = Path(a.scratch) / a.tag
    (scratch / "frames").mkdir(parents=True, exist_ok=True)
    for p in (Path(a.frames) / "frames").glob("%s-%s-*.png" % (cfg["hero"].lower(), a.tag)):
        if not (scratch / "frames" / p.name).is_file():
            shutil.copyfile(p, scratch / "frames" / p.name)
    with contextlib.redirect_stdout(io.StringIO()):
        res = U.cmd_measure(argparse.Namespace(out=str(scratch), tag=a.tag), cfg)
    if a.out:
        shutil.copyfile(scratch / ("measure-%s.json" % a.tag), a.out)
    for var in ("reading", "neutral"):
        e = res["exposure"][var]
        n = sum(1 for z in cfg["tolerance_zones"] if e["deltas"].get(z, {}).get("all_within"))
        print(var, "k %.3f" % e["k_concept_over_ue_geomean_key_zones"], "%d/%d" % (n, len(cfg["tolerance_zones"])),
              " | ".join("%s %.2f/%+.1f/%+.3f%s" % (z, d["Y_ratio_exposure_normalised"], d["dHue_deg"], d["dSat"],
                                                   "+" if d["all_within"] else "x") for z, d in e["deltas"].items()))
    return res


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("command", choices=["measure", "fit", "forecast"])
    ap.add_argument("--config", required=True)
    ap.add_argument("--frames", required=True)
    ap.add_argument("--tag", default="b1")
    ap.add_argument("--zones")
    ap.add_argument("--keep-luma")
    ap.add_argument("--weights", default="reading=1,neutral=0.5")
    ap.add_argument("--ratio", action="append")
    ap.add_argument("--scratch", default="C:/tmp/lr2/scratch")
    ap.add_argument("--edit-config", help="forecast: config whose zone definitions pick the edited pixels")
    ap.add_argument("--out")
    a = ap.parse_args()
    cfg = load_cfg(a.config)
    {"measure": cmd_measure, "fit": cmd_fit, "forecast": cmd_forecast}[a.command](a, cfg)
    return 0


if __name__ == "__main__":
    sys.exit(main())
