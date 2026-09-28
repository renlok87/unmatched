#!/usr/bin/env python3
"""Measure whether the three Harpy instances are distinguishable WITHOUT colour in the K1 / K2-like frames of
review_harpy_candidate.py --instances (plain Python: Pillow + numpy).

    python analyse_instances.py <run_dir>/preview/instances

For every frame instances_<setup>_<k>.png: converts to grayscale (ITU-R BT.601 luma, what "без цвета" means
for a screenshot), and for every pip slot that Blender reported as visible from the camera (ray cast, not hidden
by the figure) measures the mean luma in a disc of 0.6 x the projected pip radius and the luma of the base
top next to it (an annulus 1.6-2.4 projected radii around the pip, minus pixels inside other pip discs). A slot
reads «lit» when pip - top >= 40 of 255. Each instance is then decoded against the three patterns of the build
profile (1: centre pips, 2: outer pips, 3: all): the instance is distinguishable when exactly one index agrees
with every visible slot and it is the true one. Writes instances-analysis.json, grayscale copies
(*_gray.png), 4x crops around each base (*_crop_<i>.png) and one sheet of the three crops per frame
(sheet_<setup>_<k>_gray_crops.png) for reading by eye.
"""

import json
import sys
from pathlib import Path

import numpy as np
from PIL import Image

LIT_DELTA = 40.0
PATTERN = {1: {"centre"}, 2: {"outer_a", "outer_b"}, 3: {"centre", "outer_a", "outer_b"}}


def disc_mean(gray, cx, cy, radius, exclude=None):
    h, w = gray.shape
    x0, x1 = max(int(cx - radius - 1), 0), min(int(cx + radius + 2), w)
    y0, y1 = max(int(cy - radius - 1), 0), min(int(cy + radius + 2), h)
    yy, xx = np.mgrid[y0:y1, x0:x1]
    mask = (xx + 0.5 - cx) ** 2 + (yy + 0.5 - cy) ** 2 <= radius ** 2
    if exclude is not None:
        mask &= ~exclude[y0:y1, x0:x1]
    vals = gray[y0:y1, x0:x1][mask]
    return float(vals.mean()) if vals.size else None, int(vals.size)


def ring_mean(gray, cx, cy, r0, r1, exclude):
    h, w = gray.shape
    x0, x1 = max(int(cx - r1 - 1), 0), min(int(cx + r1 + 2), w)
    y0, y1 = max(int(cy - r1 - 1), 0), min(int(cy + r1 + 2), h)
    yy, xx = np.mgrid[y0:y1, x0:x1]
    d2 = (xx + 0.5 - cx) ** 2 + (yy + 0.5 - cy) ** 2
    mask = (d2 >= r0 ** 2) & (d2 <= r1 ** 2) & ~exclude[y0:y1, x0:x1]
    vals = gray[y0:y1, x0:x1][mask]
    return float(np.median(vals)) if vals.size else None, int(vals.size)


def main():
    out = Path(sys.argv[1]).resolve()
    pips = json.loads((out / "instances-pips.json").read_text(encoding="utf-8"))
    report = {"method": __doc__.strip().splitlines()[0], "lit_delta_luma": LIT_DELTA, "frames": {}}
    for name, recs in sorted(pips.items()):
        rgb = np.asarray(Image.open(out / ("%s.png" % name)).convert("RGB")).astype(np.float64)
        gray = 0.299 * rgb[:, :, 0] + 0.587 * rgb[:, :, 1] + 0.114 * rgb[:, :, 2]
        Image.fromarray(np.clip(np.round(gray), 0, 255).astype(np.uint8)).save(out / ("%s_gray.png" % name))
        slots = [r for r in recs if "slot" in r]
        centres = {r["instance"]: r["base_centre_px"] for r in recs if "base_centre_px" in r}
        h, w = gray.shape
        excl = np.zeros_like(gray, dtype=bool)
        yy, xx = np.mgrid[0:h, 0:w]
        for r in slots:  # every pip disc (1.2 x radius) is excluded from the top-surface samples
            cx, cy, pr = r["px"][0], r["px"][1], max(r["radius_px"], 0.8)
            y0, y1 = max(int(cy - 2 * pr), 0), min(int(cy + 2 * pr) + 2, h)
            x0, x1 = max(int(cx - 2 * pr), 0), min(int(cx + 2 * pr) + 2, w)
            sub = (xx[y0:y1, x0:x1] + 0.5 - cx) ** 2 + (yy[y0:y1, x0:x1] + 0.5 - cy) ** 2 <= (1.2 * pr) ** 2
            excl[y0:y1, x0:x1] |= sub
        frame = {"instances": {}}
        for inst in (1, 2, 3):
            mine = [r for r in slots if r["instance"] == inst]
            obs = []
            for r in mine:
                entry = {"sector_deg": r["sector_deg"], "slot": r["slot"], "visible": r["visible"],
                         "radius_px": r["radius_px"]}
                if r["visible"]:
                    pr = max(r["radius_px"], 0.8)
                    pip_l, n_pip = disc_mean(gray, r["px"][0], r["px"][1], 0.6 * pr)
                    top_l, n_top = ring_mean(gray, r["px"][0], r["px"][1], 1.6 * pr, 2.4 * pr, excl)
                    entry.update({"pip_luma": round(pip_l, 1) if pip_l is not None else None, "pip_px": n_pip,
                                  "top_luma": round(top_l, 1) if top_l is not None else None, "top_px": n_top})
                    if pip_l is not None and top_l is not None:
                        entry["delta"] = round(pip_l - top_l, 1)
                        entry["lit"] = bool(pip_l - top_l >= LIT_DELTA)
                obs.append(entry)
            seen = [o for o in obs if "lit" in o]
            consistent = [k for k, pat in PATTERN.items() if all(o["lit"] == (o["slot"] in pat) for o in seen)]
            expected_ok = all(o["lit"] == (o["slot"] in PATTERN[inst]) for o in seen)
            frame["instances"][str(inst)] = {
                "yaw_deg": mine[0]["yaw_deg"] if mine else None, "visible_slots": len(seen),
                "lit_slots": sum(1 for o in seen if o["lit"]), "matches_own_pattern": expected_ok,
                "consistent_indices": consistent, "distinguishable": consistent == [inst],
                "min_lit_delta": min((o["delta"] for o in seen if o["lit"]), default=None),
                "max_unlit_delta": max((o["delta"] for o in seen if not o["lit"]), default=None),
                "pip_radius_px": round(float(np.median([o["radius_px"] for o in obs])), 2) if obs else None,
                "slots": obs}
            c = centres.get(inst)
            if c:
                half = int(max(40, 12 * (frame["instances"][str(inst)]["pip_radius_px"] or 3)))
                box = (int(c[0] - half), int(c[1] - half), int(c[0] + half), int(c[1] + half))
                Image.fromarray(np.clip(np.round(gray), 0, 255).astype(np.uint8)).crop(box).resize(
                    (4 * 2 * half, 4 * 2 * half), Image.NEAREST).save(out / ("%s_crop_%d.png" % (name, inst)))
        frame["all_distinguishable"] = all(v["distinguishable"] for v in frame["instances"].values())
        report["frames"][name] = frame
        print(name, {k: (v["visible_slots"], v["lit_slots"], v["consistent_indices"], v["pip_radius_px"])
                     for k, v in frame["instances"].items()}, "ALL" if frame["all_distinguishable"] else "NOT ALL")
    for name in sorted(pips):  # one sheet per frame: the three 4x grayscale crops side by side
        crops = [Image.open(out / ("%s_crop_%d.png" % (name, i))) for i in (1, 2, 3)]
        sheet = Image.new("L", (sum(c.size[0] for c in crops), max(c.size[1] for c in crops)), 255)
        x = 0
        for c in crops:
            sheet.paste(c, (x, 0))
            x += c.size[0]
        sheet.thumbnail((1800, 700))
        sheet.save(out / ("sheet_%s_gray_crops.png" % name[len("instances_"):]))
    (out / "instances-analysis.json").write_text(json.dumps(report, indent=1, sort_keys=True) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
