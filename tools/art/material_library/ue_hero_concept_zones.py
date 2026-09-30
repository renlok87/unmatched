"""Concept zone medians for the UE look-dev review (ue_hero_lookdev.py measure) of heroes whose look-dev measured the
concept with boxes + HSV filters (King Arthur, Harpy; look-dev C, 2026-09-30).

    python tools/art/material_library/ue_hero_concept_zones.py --spec <spec json> --out <concept-zones json>

Spec (JSON): {"hero", "concept": {"front"|"side"|"back": png}, "sources": [{"profile": <look-dev profile>,
"pointer": "/lookdev/concept_zones", "as_zone": <optional: every region of this source is that zone>, "gate": <optional
HSV filter of regions without one>}, ...] (boxes [x0, y0, x1, y1] or polygons, with a named HSV filter of the same
block), "zones": {<zone>: {"class": <preset class id>, "from": [<zone name in the sources>, ...]}}}.

Per zone: the concept pixels of every box / polygon of the source zones that pass the box's HSV filter, pooled over
the three views; statistics = ue_hero_lookdev.hsv_stats (per-channel median of sRGB, HSV and Y of the median: the
definition the UE side uses). Output {"zones": {<zone>: {"class", "concept": stats, "pixels", "per_view"}}}.
Only the concept is read; no editor, no Blender.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
sys.path.insert(0, str(HERE))
from ue_hero_lookdev import hsv_stats, rgb_to_hsv, write_json  # noqa: E402


def sha(path: Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def pointer(doc, ptr):
    for key in [k for k in ptr.split("/") if k]:
        doc = doc[key]
    return doc


def filter_mask(rgb8, flt):
    h, s, v = rgb_to_hsv(rgb8.astype(np.float32) / 255.0)
    ok = np.ones(h.shape, bool)
    hue = flt.get("hue") or flt.get("hue_deg")
    if hue:
        ranges = hue if isinstance(hue[0], (list, tuple)) else [hue]
        hm = np.zeros(h.shape, bool)
        for lo, hi in ranges:
            hm |= ((h >= lo) & (h <= hi)) if lo <= hi else ((h >= lo) | (h <= hi))
        ok &= hm
    for key, arr, op in (("s_min", s, np.greater_equal), ("s_max", s, np.less_equal),
                         ("v_min", v, np.greater_equal), ("v_max", v, np.less_equal)):
        if key in flt:
            ok &= op(arr, flt[key])
    return ok


def region_mask(shape, item):
    h, w = shape
    m = Image.new("L", (w, h), 0)
    d = ImageDraw.Draw(m)
    if "box" in item or "rect" in item:
        x0, y0, x1, y1 = item.get("box") or item.get("rect")
        d.rectangle([x0, y0, x1 - 1, y1 - 1], fill=255)
    elif "poly" in item:
        d.polygon([tuple(p) for p in item["poly"]], fill=255)
    return np.asarray(m) > 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--spec", required=True)
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    spec_path = Path(a.spec).resolve()
    spec = json.loads(spec_path.read_text(encoding="utf-8"))
    concept = {v: np.asarray(Image.open(REPO / p).convert("RGB")) for v, p in spec["concept"].items()}
    blocks = []
    for src in spec["sources"]:
        doc = json.loads((REPO / src["profile"]).read_text(encoding="utf-8"))
        blk = pointer(doc, src["pointer"])
        blocks.append({"source": src, "block": blk})
    out = {"schema": "unmatched.um-v2-hero-concept-zones/1", "hero": spec["hero"],
           "tool": "tools/art/material_library/ue_hero_concept_zones.py",
           "spec": str(spec_path.relative_to(REPO)).replace("\\", "/"), "spec_sha256": sha(spec_path),
           "concept": {v: {"path": p, "sha256": sha(REPO / p)} for v, p in spec["concept"].items()},
           "sources": [dict(b["source"], sha256=sha(REPO / b["source"]["profile"])) for b in blocks],
           "method": "concept pixels of the look-dev boxes / polygons of each zone that pass the box's HSV filter "
                     "(sRGB HSV), pooled over front/side/back; per-channel median of sRGB, then HSV and Y (linear) of "
                     "the median (ue_hero_lookdev.hsv_stats, the definition of the UE side)",
           "zones": {}}
    for zone, zspec in spec["zones"].items():
        pooled, per_view = [], {}
        for view, img in concept.items():
            vm = np.zeros(img.shape[:2], bool)
            for b in blocks:
                blk = b["block"]
                filters = blk.get("filters") or {}
                for item in blk.get(view) or []:
                    name = b["source"].get("as_zone") or item.get("zone") or item.get("name")
                    if name not in zspec["from"]:
                        continue
                    flt = item.get("filter")
                    flt = filters.get(flt, {}) if isinstance(flt, str) else (flt or b["source"].get("gate") or {})
                    rm = region_mask(img.shape[:2], item)
                    fm = filter_mask(img, flt)
                    vm |= rm & fm
            n = int(vm.sum())
            if n:
                px = img[vm]
                pooled.append(px)
                per_view[view] = dict(hsv_stats(px), pixels=n)
        if not pooled:
            continue
        px = np.concatenate(pooled, 0)
        out["zones"][zone] = {"class": zspec["class"], "from": zspec["from"], "concept": hsv_stats(px),
                              "pixels": int(len(px)), "per_view": per_view}
    write_json(Path(a.out), out)
    for z, r in out["zones"].items():
        c = r["concept"]
        print("%-12s %-15s n %6d  sRGB %s  Y %.4f  hue %.1f  sat %.3f" % (z, r["class"], r["pixels"], c["median_srgb"],
                                                                          c["luma_Y_linear"], c["hue_deg"], c["sat"]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
