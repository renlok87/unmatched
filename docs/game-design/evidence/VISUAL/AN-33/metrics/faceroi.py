"""faceroi.py <run>... : Medusa face/throat ROI luma (render_bench.face_boxes + the SK_Medusa_H2LD calibration) per K2 view."""
import sys, re, json
sys.path.insert(0, "C:/tmp/wt-visual/tools/art/render")
import render_bench as rb
rb.FACE_ROI_MIN_HEAD_PX = 10.0  # K2x1.6 / K2x2.5 heads are 14.6 / 23.2 px; the tool floor (40) is for K2 5x
import numpy as np
from PIL import Image
def heads(run):
    out = []
    for l in open(f"{run}/bench.trace.log", encoding="utf-8", errors="replace"):
        if "SHOT head fighter=f-0-hero" in l:
            out.append(dict(re.findall(r"(\w+)=(\([^)]*\)|\S+)", l.split("SHOT head ", 1)[1])))
    return out[-3:]
res = {}
for run in sys.argv[1:]:
    hs = heads(run); r = {}
    for view, h in zip(("K1", "K2x1p6", "K2x2p5"), hs):
        if view == "K1": continue
        boxes, why = rb.face_boxes(h)
        a = np.asarray(Image.open(f"{run}/bench-{view}-1920x1080.png").convert("RGB")).astype(float)
        L = 0.2126 * a[..., 0] + 0.7152 * a[..., 1] + 0.0722 * a[..., 2]
        r[view] = {k: rb.roi_stats(L, b) for k, (b, _) in boxes.items()} if boxes else why
    res[run.split("/")[-1]] = r
print(json.dumps(res, indent=1))
