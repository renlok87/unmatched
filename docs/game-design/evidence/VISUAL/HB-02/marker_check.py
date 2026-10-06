"""HB-02 evidence helper: is a gate marker block (the -S09Markers debug layer) drawn in a frame?

  python docs/game-design/evidence/VISUAL/HB-02/marker_check.py --expect absent  <png/jpg ...>  [--json out.json]
  python docs/game-design/evidence/VISUAL/HB-02/marker_check.py --expect present <png/jpg ...>  (positive control)

Every gate marker of the debug layer is a solid SColorBlock: the 14 AddMarker panels (220x14 su), the lobby panel and the
match-interrupted panels (220x14 su) and the four result-stripe blocks (120x12 su) - colours from S08FlowGameMode.cpp
(GS09*/GS10* constants) and S08FlowGameModeResult.cpp (GResult*Marker). At 720p the HUD scale is 0.75 (HB-09), so the
smallest block is 90x9 px. A block is detected when at least MIN_ROWS rows hold a run of >= MIN_RUN consecutive pixels
within +/-TOL of one marker colour; painted scene pixels do not form such runs. The #7CFC00 reveal block is left out:
the revealed attack/defense value text keeps that colour in the player's view.
--expect absent fails (exit 1) on any detected block; --expect present fails when a frame has none.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np
from PIL import Image

MARKERS = {
    "maneuver #FF00FF": (255, 0, 255), "discard #00FFFF": (0, 255, 255), "attack #FF8000": (255, 128, 0),
    "defense #FF4040": (255, 64, 64), "resolve #40FF40": (64, 255, 64), "boost #FFFF40": (255, 255, 64),
    "result #40FF80": (64, 255, 128), "pending #4080FF": (64, 128, 255), "lobby #40C8FF": (64, 200, 255),
    "reveal-line #8040FF": (128, 64, 255), "resolve-blocked #FF40B0": (255, 64, 176), "scheme #A020FF": (160, 32, 255),
    "interrupt #FF6414": (255, 100, 20), "result-screen #FFD700": (255, 215, 0), "result-outcome #FF0064": (255, 0, 100),
    "result-support #00FFA0": (0, 255, 160), "result-button #8000FF": (128, 0, 255),
}
TOL = 16
MIN_RUN = 48
MIN_ROWS = 5


def max_runs(mask: np.ndarray) -> np.ndarray:
    """Longest run of True per row."""
    h, w = mask.shape
    padded = np.zeros((h, w + 2), dtype=np.int8)
    padded[:, 1:-1] = mask
    d = np.diff(padded, axis=1)
    out = np.zeros(h, dtype=np.int32)
    for y in np.nonzero(mask.any(axis=1))[0]:
        starts = np.nonzero(d[y] == 1)[0]
        ends = np.nonzero(d[y] == -1)[0]
        out[y] = int((ends - starts).max())
    return out


def check(path: Path) -> dict:
    rgb = np.asarray(Image.open(path).convert("RGB")).astype(np.int16)
    found = {}
    for name, (r, g, b) in MARKERS.items():
        mask = (np.abs(rgb[..., 0] - r) <= TOL) & (np.abs(rgb[..., 1] - g) <= TOL) & (np.abs(rgb[..., 2] - b) <= TOL)
        if not mask.any():
            continue
        runs = max_runs(mask)
        rows = int((runs >= MIN_RUN).sum())
        if rows >= MIN_ROWS:
            found[name] = {"rows": rows, "longestRun": int(runs.max())}
    return {"file": path.as_posix(), "size": list(Image.open(path).size), "blocks": found}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--expect", choices=("absent", "present"), required=True)
    ap.add_argument("--json", type=Path)
    ap.add_argument("frames", nargs="+", type=Path)
    a = ap.parse_args(argv)
    results, bad = [], 0
    for f in a.frames:
        res = check(f)
        ok = (not res["blocks"]) if a.expect == "absent" else bool(res["blocks"])
        res["ok"] = ok
        bad += 0 if ok else 1
        results.append(res)
        print(("OK  " if ok else "BAD ") + f.name + " " + (", ".join(f"{k} rows={v['rows']} run={v['longestRun']}"
                                                           for k, v in res["blocks"].items()) or "no marker block"))
    summary = {"expect": a.expect, "tol": TOL, "minRun": MIN_RUN, "minRows": MIN_ROWS, "frames": len(results),
               "bad": bad, "results": results}
    if a.json:
        a.json.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"MARKER_CHECK {'PASS' if bad == 0 else 'FAIL'} expect={a.expect} frames={len(results)} bad={bad}")
    return 0 if bad == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
