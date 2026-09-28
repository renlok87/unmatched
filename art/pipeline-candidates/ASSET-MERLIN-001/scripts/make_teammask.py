#!/usr/bin/env python3
"""Optional TeamColor mask for the Merlin candidate atlas (proposal, AD-CNF-58 open).

    python art/pipeline-candidates/ASSET-MERLIN-001/scripts/make_teammask.py \
        --run-dir art/pipeline-candidates/ASSET-MERLIN-001/20260928-blender-um-fbx-v1

Reads the build profile (team_color) and reports/atlas-report.json of the run, checks that the BC atlas still
matches the atlas stage hash, and writes textures/<mask_texture> (8-bit grayscale, linear, same size as the
atlas) plus reports/teammask-report.json. Rule (profile team_color.mask_rule): inside the inner rect of the
cells listed in mask_parts_expected only, BC texels with hue in [hue_min, hue_max] deg and saturation/value
above their thresholds (1/20 smoothstep ramps), then a 3x3 box blur for a soft 1-px edge. Deterministic.
Nothing else is written; the BC atlas is only read.
"""
import argparse
import hashlib
import json
import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageFilter

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
HUE = (18.0, 55.0)
S_MIN, V_MIN = 0.30, 0.22
RAMP = 0.05


def sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def hsv(a):
    r, g, b = a[..., 0], a[..., 1], a[..., 2]
    mx, mn = a.max(-1), a.min(-1)
    d = mx - mn
    h = np.zeros_like(mx)
    m = d > 1e-6
    rr = (mx == r) & m
    gg = (mx == g) & m & ~rr
    bb = m & ~rr & ~gg
    h[rr] = ((g - b)[rr] / d[rr]) % 6
    h[gg] = ((b - r)[gg] / d[gg]) + 2
    h[bb] = ((r - g)[bb] / d[bb]) + 4
    return h * 60.0, np.where(mx > 0, d / np.maximum(mx, 1e-6), 0.0), mx


def smooth(x):
    x = np.clip(x, 0.0, 1.0)
    return x * x * (3 - 2 * x)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--run-dir", required=True)
    args = ap.parse_args()
    run = Path(args.run_dir) if Path(args.run_dir).is_absolute() else (REPO / args.run_dir)
    manifest = json.loads((run / "manifest.json").read_text(encoding="utf-8"))
    profile = json.loads((REPO / manifest["config"]["build_profile"]).read_text(encoding="utf-8"))
    tc = profile["team_color"]
    atlas = json.loads((run / "reports/atlas-report.json").read_text(encoding="utf-8"))
    bc_path = run / "textures" / atlas["files"]["BC"]["file"]
    bc_hash = sha256(bc_path)
    stage_hash = manifest["stages"]["atlas"]["outputs"]["textures/%s" % bc_path.name]["sha256"]
    if bc_hash != stage_hash:
        sys.exit("BC atlas changed since the atlas stage")
    bc = np.asarray(Image.open(bc_path).convert("RGB")).astype(np.float32) / 255.0
    h, s, v = hsv(bc)
    hue_w = smooth((h - HUE[0]) / 4.0) * smooth((HUE[1] - h) / 4.0)
    raw = hue_w * smooth((s - S_MIN) / RAMP + 0.5) * smooth((v - V_MIN) / RAMP + 0.5)
    inside = np.zeros(raw.shape, dtype=bool)
    cells = atlas["cells"]
    for part in tc["mask_parts_expected"]:
        c = cells[part]
        inside[c["y_top"] + c["inset"]:c["y_top"] + c["cell"] - c["inset"],
               c["x"] + c["inset"]:c["x"] + c["cell"] - c["inset"]] = True
    mask = np.where(inside, raw, 0.0)
    img = Image.fromarray(np.round(mask * 255).astype(np.uint8), "L").filter(ImageFilter.BoxBlur(1))
    out = run / "textures" / tc["mask_texture"]
    img.save(out, optimize=True)
    arr = np.asarray(img).astype(np.float32) / 255.0
    per_cell = {}
    for part, c in sorted(cells.items()):
        sub = arr[c["y_top"]:c["y_top"] + c["cell"], c["x"]:c["x"] + c["cell"]]
        per_cell[part] = round(float((sub > 0.5).mean()), 5)
    report = {
        "stage": "teammask (optional, after build)",
        "script": "art/pipeline-candidates/ASSET-MERLIN-001/scripts/make_teammask.py",
        "script_sha256": sha256(Path(__file__)),
        "status": "предложено",
        "applicability": tc["applicability"],
        "rule": {"cells": tc["mask_parts_expected"], "hue_deg": list(HUE), "saturation_min": S_MIN, "value_min": V_MIN,
                 "ramp": RAMP, "edge": "3x3 box blur"},
        "input": {"file": bc_path.name, "sha256": bc_hash},
        "output": {"file": out.name, "sha256": sha256(out), "bytes": out.stat().st_size, "pixels": list(img.size),
                   "mode": "L", "colorspace": "linear (UE: sRGB off, TC_Grayscale / TC_Masks)"},
        "coverage_over_0_5_by_cell": per_cell,
        "coverage_over_0_5_atlas": round(float((arr > 0.5).mean()), 5),
        "checks": {"only_listed_cells": all(v == 0.0 for p, v in per_cell.items() if p not in tc["mask_parts_expected"]),
                   "bc_unchanged": sha256(bc_path) == bc_hash},
    }
    report["passed"] = all(report["checks"].values())
    (run / "reports/teammask-report.json").write_text(json.dumps(report, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
                                                      encoding="utf-8")
    print("TEAMMASK passed=%s coverage=%s sha=%s" % (report["passed"], per_cell[tc["mask_parts_expected"][0]],
                                                     report["output"]["sha256"][:12]))
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    sys.exit(main())
