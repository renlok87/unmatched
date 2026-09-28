#!/usr/bin/env python3
"""Optional TeamColor mask of the Arthur candidate atlas (status: предложено; applicability open, AD-CNF-58).

    python art/pipeline-candidates/ASSET-KING-ARTHUR-001/scripts/team_mask_arthur.py \
        --run-dir art/pipeline-candidates/ASSET-KING-ARTHUR-001/20260928-blender-um-fbx-v1

Reads textures/<prefix>_BC.png and reports/atlas-report.json of the run (only read), writes
textures/<prefix>_TeamMask.png (8-bit grey, linear) and reports/team-mask-report.json. Rule from the build
profile `team_color`: red cloth = HSV hue >= hue_min_deg or <= hue_max_deg, s >= s_min, v in [v_min, v_max],
inside part cells only, softened by a Gaussian blur (sigma px) and re-limited to the cells. Deterministic.
"""
import argparse
import hashlib
import json
from pathlib import Path

import numpy as np
from PIL import Image, ImageFilter

REPO = Path(__file__).resolve().parents[4]


def sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--run-dir", required=True)
    run = (REPO / ap.parse_args().run_dir).resolve()
    manifest = json.loads((run / "manifest.json").read_text(encoding="utf-8"))
    profile = json.loads((REPO / manifest["config"]["build_profile"]).read_text(encoding="utf-8"))
    rule = profile["team_color"]["mask_params"]
    atlas = json.loads((run / "reports/atlas-report.json").read_text(encoding="utf-8"))
    prefix = profile["atlas"]["texture_prefix"]
    bc_path = run / "textures" / ("%s_BC.png" % prefix)
    bc_hash = sha256(bc_path)
    im = np.asarray(Image.open(bc_path).convert("RGB")).astype(np.float32) / 255.0
    mx, mn = im.max(axis=2), im.min(axis=2)
    d = np.maximum(mx - mn, 1e-6)
    r, g, b = im[..., 0], im[..., 1], im[..., 2]
    hue = np.where(mx == r, ((g - b) / d) % 6, np.where(mx == g, (b - r) / d + 2, (r - g) / d + 4)) * 60.0
    sat = np.where(mx > 0, (mx - mn) / np.maximum(mx, 1e-6), 0.0)
    val = mx
    size = atlas["size"]
    cells = np.zeros((size, size), dtype=bool)
    for c in atlas["cells"].values():
        cells[c["y_top"]:c["y_top"] + c["cell"], c["x"]:c["x"] + c["cell"]] = True
    hard = (((hue >= rule["hue_min_deg"]) | (hue <= rule["hue_max_deg"])) & (sat >= rule["s_min"]) &
            (val >= rule["v_min"]) & (val <= rule["v_max"]) & cells)
    soft = Image.fromarray((hard * 255).astype(np.uint8), "L").filter(ImageFilter.GaussianBlur(rule["blur_sigma_px"]))
    mask = np.where(cells, np.asarray(soft), 0).astype(np.uint8)
    out = run / "textures" / profile["team_color"]["mask_texture"]
    Image.fromarray(mask, "L").save(out, optimize=True)
    per_cell = {}
    for name, c in sorted(atlas["cells"].items(), key=lambda kv: int(kv[0].split("_")[-1])):
        inner = mask[c["y_top"] + c["inset"]:c["y_top"] + c["cell"] - c["inset"],
                     c["x"] + c["inset"]:c["x"] + c["cell"] - c["inset"]]
        per_cell[name] = round(float((inner >= 128).mean()), 4)
    report = {"stage": "team-mask (optional, not a CLI stage)", "status": "предложено",
              "applicability": profile["team_color"]["applicability"],
              "source_bc": {"file": bc_path.name, "sha256": bc_hash},
              "rule": rule, "output": {"file": out.name, "sha256": sha256(out), "bytes": out.stat().st_size,
                                       "pixels": [size, size], "mode": "L", "colour_space": "linear (sRGB off in UE)"},
              "coverage_by_cell_mask_ge_0_5": per_cell,
              "cells_with_coverage_over_1pct": sorted(k for k, v in per_cell.items() if v > 0.01),
              "note": "texture-space mask; UE material: BaseColor = lerp(BC, luminance(BC) x TeamColor x k, mask) "
                      "is a proposal for the UE stage, not built here"}
    (run / "reports/team-mask-report.json").write_text(json.dumps(report, indent=2, sort_keys=True,
                                                                  ensure_ascii=False) + "\n", encoding="utf-8")
    print("TEAM_MASK_OK", out.name, report["output"]["sha256"][:12], report["cells_with_coverage_over_1pct"])


if __name__ == "__main__":
    main()
