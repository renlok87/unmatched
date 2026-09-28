import ue, json, sys, capture, numpy as np
from PIL import Image
A = "C:/Users/ren/.codex/worktrees/art-foundation/unmached/unreal/Unmatched/Artifacts/ART004Face/"
ref = {"cobble": A + "medusa-skeletal-restorednormals-faceslot-neck-static-frontambient-y100-z500-s100-d10-k2-base-d300-headtiltprobe.png",
       "forest-probe": A + "medusa-skeletal-restorednormals-faceslot-neck-static-frontambient-y100-z500-s100-d10-k2-base-d300-forest-probe-headtiltprobe.png",
       "paddock-probe": A + "medusa-skeletal-restorednormals-faceslot-neck-static-frontambient-y100-z500-s100-d10-k2-base-d300-paddock-probe-headtiltprobe.png"}
def stats(f):
    im = np.array(Image.open(f).convert("RGB")).astype(float)
    return [im[b[1]:b[3], b[0]:b[2]].mean(axis=(0, 1)).round(1).tolist() for b in ((100, 700, 500, 1000), (1400, 700, 1800, 1000), (850, 380, 1100, 700))]
light, out = sys.argv[1], sys.argv[2]
st = json.load(open(f"C:/tmp/a1v3/state_{light.split('-')[0]}.json"))
cam = capture.look(*capture.views(st["loc"])["d10-k2-d300"])
capture.capture(cam, out); capture.capture(cam, out)
print("ref", stats(ref[light])); print("mcp", stats(out))
