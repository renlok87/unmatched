"""Comparison images for the probe directory (run from the scratch dir, _paths.SCRATCH).

Since 2026-09-28 the full UE frames and ID renders are read from the scratch
directories (frames_ev13/, blender/renders/, blender/, followup/): the probe
directory keeps only key frames. The scratch UE frames are pixel-identical to the
copies that were in ue-mcp-live (checked before pruning).
"""
import json
from PIL import Image, ImageDraw
from _paths import PROBE as P
def load(p, alpha_bg=None):
    im = Image.open(p)
    if alpha_bg is not None:
        im = im.convert("RGBA"); bg = Image.new("RGBA", im.size, alpha_bg + (255,)); bg.alpha_composite(im); return bg.convert("RGB")
    return im.convert("RGB")
def grid(rows, box, scale, out, title):
    # rows: list of (row_label, [(panel_label, image_path, alpha_bg)])
    w, h = box[2] - box[0], box[3] - box[1]; W, H = int(w * scale), int(h * scale)
    ncol = max(len(r[1]) for r in rows)
    im = Image.new("RGB", (ncol * (W + 8) - 8, 22 + len(rows) * (H + 36)), (28, 28, 28))
    d = ImageDraw.Draw(im); d.text((4, 4), title, fill=(255, 255, 255))
    for i, (rl, panels) in enumerate(rows):
        y = 22 + i * (H + 36)
        d.text((4, y + 2), rl, fill=(255, 220, 0))
        for j, (pl, path, bg, *smooth) in enumerate(panels):
            x = j * (W + 8)
            resample = Image.LANCZOS if bg is None or smooth else Image.NEAREST  # ID renders stay crisp
            im.paste(load(path, bg).crop(box).resize((W, H), resample), (x, y + 18))
            d.text((x + 4, y + 20), pl, fill=(255, 255, 0))
    im.save(out, optimize=True)
def label_pair(src, out, title, left, right, gap=10):
    # Adds a caption strip above an existing side-by-side viewport shot; panel pixels unchanged.
    im = Image.open(src).convert("RGB"); w, h = im.size; half = (w - gap) // 2
    res = Image.new("RGB", (w, h + 40), (28, 28, 28)); res.paste(im, (0, 40))
    d = ImageDraw.Draw(res); d.text((4, 4), title, fill=(255, 255, 255))
    d.text((4, 22), left, fill=(255, 255, 0)); d.text((half + gap + 4, 22), right, fill=(255, 255, 0))
    res.save(out, optimize=True)
U = "frames_ev13/ue-mcp-"
rows = []
for l in ("cobble", "forest-probe", "paddock-probe"):
    rows.append((l + " (UE editor viewport, FOV 35, EV100 1.3, D-10 K2 300 uu)", [("v2 front", U + l + "-d10-k2-d300-v2.png", None), ("v3 front", U + l + "-d10-k2-d300-v3.png", None)]))
grid(rows, (800, 330, 1140, 700), 1.0, P + "compare-ue-k2-front-three-lights.png", "ART-004 head-tilt v3 vs v2 - EDITOR frames, not packaged K2")
rows = [(l + " rear K2 300 uu", [("v2 rear", U + l + "-d10-k2-rear-d300-v2.png", None), ("v3 rear", U + l + "-d10-k2-rear-d300-v3.png", None)]) for l in ("cobble", "forest-probe", "paddock-probe")]
grid(rows, (780, 330, 1120, 700), 1.0, P + "compare-ue-k2-rear-three-lights.png", "ART-004 head-tilt v3 vs v2 - EDITOR frames, rear D-10")
grid([("cobble K2 300 uu, x5 zoom of face", [("v2", U + "cobble-d10-k2-d300-v2.png", None), ("v3", U + "cobble-d10-k2-d300-v3.png", None)])], (890, 400, 1030, 510), 5, P + "compare-ue-k2-face-zoom.png", "Face at K2 (EDITOR frame, upscaled)")
grid([("cobble eye-level close-up, neck base (x2)", [("v2", U + "cobble-close-head-front-v2.png", None), ("v3: see-through wedge under throat plate", U + "cobble-close-head-front-v3.png", None)])], (800, 640, 1200, 900), 2, P + "compare-ue-neck-front-closeup.png", "Neck base, EDITOR close-up 55 cm")
grid([("cobble rear 3/4 close-up", [("v2", U + "cobble-close-neck-rear34-v2.png", None), ("v3", U + "cobble-close-neck-rear34-v3.png", None)])], (300, 0, 1620, 1080), 0.6, P + "compare-ue-neck-rear34-closeup.png", "Rear neck / crown / quiver, EDITOR close-up")
B = "blender/renders/id-cull-"
MAG = (255, 0, 255)
grid([("ortho front 16 cm, backface culling (magenta = see-through)", [("v2", B + "neck-front-v2.png", MAG), ("v3", B + "neck-front-v3.png", MAG), ("ramp probe (diagnostic)", B + "neck-front-rampprobe.png", MAG)]),
      ("ortho along D-10 pitch -55 (K2 direction)", [("v2", B + "neck-top55-v2.png", MAG), ("v3", B + "neck-top55-v3.png", MAG), ("ramp probe (diagnostic)", B + "neck-top55-rampprobe.png", MAG)])],
     (250, 250, 780, 700), 0.8, P + "compare-blender-id-neck-junction.png", "Blender MCP part-ID: red face/throat, cyan collar, green crown, yellow rear neck, white quiver")
# Added 2026-09-28 (vc): rear and side junction views for the rear-zone metric.
grid([(v + ", ortho 16 cm, backface culling (magenta = see-through)", [("v2", B + v + "-v2.png", MAG), ("v3", B + v + "-v3.png", MAG)])
      for v in ("neck-rear", "neck-rear34R", "neck-rear34L", "neck-sideR")],
     (160, 120, 864, 760), 0.55, P + "compare-blender-id-neck-rear.png",
     "Blender MCP part-ID, rear/side: yellow rear neck, green crown, cyan collar, white quiver, magenta = background")
# Labelled live-viewport comparisons (left = v2, right = v3: matched pixel-exactly to the single shots).
for v in ("front", "rear"):
    label_pair(f"blender/cmp-fbx-d10-{v}.png", P + f"blender-mcp-live/viewport-cmp-fbx-d10-{v}.png",
               f"Live Blender viewport, saved FBX, D-10 {v}, rest pose (same camera relative to each figure)",
               "v2 face-section-neck", "v3 head-tilt")
# HitReact worst frame from the headless follow-up (one camera for both, only body and bow).
F = "followup/"
fu = json.load(open(F + "followup-measurements.json", encoding="utf-8"))
hr = fu["hitreact_render"]; fr = hr["frame"]; cnt = fu["draft_clip_per_frame"]["HitReact"]
k = fr - cnt["frame_range"][0]  # index of the rendered frame in the per-frame lists
BG = (60, 60, 60)
grid([("Workbench texture, backface culling", [(f"v2  frame {fr}: {cnt['v2']['per_frame'][k]} intersecting pairs", F + hr["files"]["tex-v2"], BG, "smooth"),
                                              (f"v3  frame {fr}: {cnt['v3']['per_frame'][k]} pairs (crown x quiver {cnt['v3']['crown_quiver_per_frame'][k]})", F + hr["files"]["tex-v3"], BG, "smooth")]),
      ("part ID: green crown, red face, white quiver, cyan collar, blue bow", [("v2", F + hr["files"]["id-v2"], BG), ("v3", F + hr["files"]["id-v3"], BG)])],
     (0, 0, 1024, 1024), 0.5, P + "compare-blender-hitreact-f4.png",
     "Draft HitReact frame %d (diagnostic, not an accepted clip), headless Blender, same camera" % fr)
print("ok")
