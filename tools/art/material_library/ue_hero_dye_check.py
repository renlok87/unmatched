"""Look-dev C: where does the team colour land? (frames of an ue_hero_lookdev.py review, no editor)

    python tools/art/material_library/ue_hero_dye_check.py --config <review json> --out <review dir> --tag <tag>

Per view (front / side / back / K2 5x) and team variant: pixels of the figure (MatID class map of the debug frame for
the ortho views; pixels that changed against the plate at K2) whose colour differs from the neutral frame of the same
camera by more than 24 levels (max channel) = dyed. Per class: share of dyed pixels. The TeamAccent rule (team-accent.md):
metal, skin, horn and stone never change; the accent share of the figure is small (5-12 % of the surface).
Writes <out>/dye-check-<tag>.json.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
sys.path.insert(0, str(HERE))
from ue_hero_lookdev import ORTHO, decode_debug, load_frame, write_json  # noqa: E402

THRESH = 24


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--config", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--tag", required=True)
    a = ap.parse_args()
    cfg = json.loads(Path(a.config).read_text(encoding="utf-8"))
    out, hero, tag = Path(a.out).resolve(), cfg["hero"], a.tag
    presets = json.loads((REPO / "docs/art-pipeline/material-library/um-material-presets-v1.json").read_text(encoding="utf-8"))
    names = {c["index"]: c["id"] for c in presets["classes"]}
    ids = {v: k for k, v in names.items()}
    zc = cfg.get("zone_class") or {}
    classes = sorted({ids[zc.get(z, z)] for z in cfg["zones"]} | {ids[c] for c in cfg.get("decode_classes") or []} | {0})
    teams = cfg.get("team_variants") or ["Blue", "Red"]
    res = {"schema": "unmatched.um-v2-hero-dye-check/1", "hero": hero, "tag": tag, "threshold_levels": THRESH,
           "tool": "tools/art/material_library/ue_hero_dye_check.py", "views": {}}
    for view in list(ORTHO) + ["k2-5x"]:
        neu = load_frame(out, hero, tag, "%s-neutral" % view)
        if neu is None:
            continue
        rv = {}
        if view in ORTHO:
            cls, changed = decode_debug(load_frame(out, hero, tag, "%s-debug" % view),
                                        load_frame(out, hero, tag, "%s-plate" % view), classes, cfg.get("debug_calibration"))
            fig = cls >= 0
        else:
            cls, fig = None, None
        for t in teams:
            fr = load_frame(out, hero, tag, "%s-%s" % (view, t.lower()))
            if fr is None:
                continue
            d = np.abs(fr.astype(np.int16) - neu.astype(np.int16)).max(-1) > THRESH
            if fig is None:  # K2: figure = pixels where any team frame differs from neutral or the figure is dark/busy
                rv[t] = {"dyed_pixels": int(d.sum())}
                continue
            per = {}
            for c in classes:
                m = cls == c
                if m.sum() >= 50:
                    per[names[c]] = {"pixels": int(m.sum()), "dyed_share": round(float((d & m).sum() / m.sum()), 4)}
            rv[t] = {"figure_pixels": int(fig.sum()), "dyed_share_of_figure": round(float((d & fig).sum() / max(fig.sum(), 1)), 4),
                     "per_class": per}
        res["views"][view] = rv
    write_json(out / ("dye-check-%s.json" % tag), res)
    for v, rv in res["views"].items():
        for t, r in rv.items():
            print(v, t, r.get("dyed_share_of_figure", r.get("dyed_pixels")),
                  {k: x["dyed_share"] for k, x in (r.get("per_class") or {}).items()})
    return 0


if __name__ == "__main__":
    sys.exit(main())
