"""Mean abs RGB differences: MCP viewport vs CLI SceneCapture, and v2 vs v3 inside the MCP set.

Run from the scratch dir (_paths.SCRATCH). The v3 CLI frames are read from _paths.ARTIFACTS
(from the main checkout set ART004_A1_ARTIFACTS to the art worktree's Artifacts/ART004Face).
"""
import json
import numpy as np
from PIL import Image
from _paths import ARTIFACTS as A, EVIDENCE as E
cli = {"v2": E + "medusa-frozen-skeletal-restorednormals-faceslot-neck-static-frontambient-y100-z500-s100-d10-k2-base-d300-ue-editor-2026-09-28.png",
       "v3": A + "medusa-skeletal-restorednormals-faceslot-neck-static-frontambient-y100-z500-s100-d10-k2-base-d300-headtiltprobe.png"}
box = (800, 340, 1140, 700)
load = lambda p: np.array(Image.open(p).convert("RGB")).astype(float)
crop = lambda im: im[box[1]:box[3], box[0]:box[2]]
out = {}
for t in ("v2", "v3"):
    m, c = load(f"frames_ev13/ue-mcp-cobble-d10-k2-d300-{t}.png"), load(cli[t])
    out[f"mcp_vs_cli_{t}_head_mad"] = round(float(np.abs(crop(m) - crop(c)).mean()), 2)
    out[f"mcp_vs_cli_{t}_full_mad"] = round(float(np.abs(m - c).mean()), 2)
out["cli_v2_vs_v3_head_mad"] = round(float(np.abs(crop(load(cli["v2"])) - crop(load(cli["v3"]))).mean()), 2)
for light in ("cobble", "forest-probe", "paddock-probe"):
    a, b = load(f"frames_ev13/ue-mcp-{light}-d10-k2-d300-v2.png"), load(f"frames_ev13/ue-mcp-{light}-d10-k2-d300-v3.png")
    d = np.abs(a - b).sum(axis=2); ys, xs = np.nonzero(d > 30)
    out[f"mcp_{light}_v2_vs_v3"] = {"head_mad": round(float(np.abs(crop(a) - crop(b)).mean()), 2), "changed_px_gt30": int((d > 30).sum()),
                                   "changed_bbox": [int(xs.min()), int(ys.min()), int(xs.max()), int(ys.max())] if len(xs) else None}
# Exposure check of the EV100 1.3 choice (added 2026-09-28 after vc): CLI v3 SceneCapture vs
# MCP v3 viewport, mean RGB ratio per window. Floor windows are the calib.py ones; the top
# corners show the SceneCapture vignette.
cli_v3 = {"cobble": cli["v3"],
          "forest-probe": A + "medusa-skeletal-restorednormals-faceslot-neck-static-frontambient-y100-z500-s100-d10-k2-base-d300-forest-probe-headtiltprobe.png",
          "paddock-probe": A + "medusa-skeletal-restorednormals-faceslot-neck-static-frontambient-y100-z500-s100-d10-k2-base-d300-paddock-probe-headtiltprobe.png"}
windows = {"floor_lower_left_400x300": (100, 700, 500, 1000), "floor_lower_right_400x300": (1400, 700, 1800, 1000),
           "corner_top_left_300x200": (0, 0, 300, 200), "corner_top_right_300x200": (1620, 0, 1920, 200),
           "corner_top_left_150x100": (0, 0, 150, 100), "corner_top_right_150x100": (1770, 0, 1920, 100)}
ev = {}
for light, path in cli_v3.items():
    c, m = load(path), load(f"frames_ev13/ue-mcp-{light}-d10-k2-d300-v3.png")
    ev[light] = {n: round(100 * (float(c[y0:y1, x0:x1].mean()) / float(m[y0:y1, x0:x1].mean()) - 1), 1)
                 for n, (x0, y0, x1, y1) in windows.items()}
out["exposure_cli_vs_mcp_v3_percent"] = ev
json.dump(out, open("ue_frame_diffs.json", "w"), indent=1)
