"""Copy the selected scratch files into the probe directory (run from the scratch dir, _paths.SCRATCH).

Reduced on 2026-09-28 (P0 review fixes): only key frames stay in the repository -
UE MCP K2 Cobble front/rear v2/v3, the Blender part-ID renders, composites
(composites.py) and JSON. The forest/paddock K2 frames and the two Cobble close-ups
stay in the scratch frames_ev13 (composites.py and the metric scripts read them
there); the CLI SceneCapture PNGs stay in the ignored unreal/Unmatched/Artifacts
(only their reports and a head crop of the rear unlit frame are copied). SHA-256 of
every removed file is kept in head-tilt-v3-review-measurements.json.
Optional argv[1] = output directory (default: the probe directory).
Paths come from _paths.py (repository root from this file, ART004_A1_* overrides).
"""
import json, os, sys, shutil, hashlib
from PIL import Image
from _paths import ARTIFACTS as A, PROBE
P = sys.argv[1].rstrip("/") + "/" if len(sys.argv) > 1 else PROBE
def sha(p): return hashlib.sha256(open(p, "rb").read()).hexdigest()
for d in ("ue-mcp-live", "ue-cli-headtiltprobe", "blender-mcp-live"):
    os.makedirs(P + d, exist_ok=True)
manifest = {"ue-mcp-live": {}, "ue-cli-headtiltprobe": {}, "blender-mcp-live": {}}
# 1) UE MCP frames, K2 Cobble only (lossless re-encode with optimize=True; pixels unchanged)
keep = [f"ue-mcp-cobble-{v}-{t}.png" for v in ("d10-k2-d300", "d10-k2-rear-d300") for t in ("v2", "v3")]
for f in keep:
    im = Image.open("frames_ev13/" + f); im.save(P + "ue-mcp-live/" + f, optimize=True)
    manifest["ue-mcp-live"][f] = sha(P + "ue-mcp-live/" + f)
# 2) CLI v3 frames of the art chat: reports byte-identical from the ignored Artifacts,
#    PNGs not copied; the rear unlit frame only as a 1:1 head crop.
cli = ["medusa-skeletal-restorednormals-faceslot-neck-static-frontambient-y100-z500-s100-d10-k2-base-d300-headtiltprobe",
       "medusa-skeletal-restorednormals-faceslot-neck-static-frontambient-y100-z500-s100-d10-k2-base-d300-forest-probe-headtiltprobe",
       "medusa-skeletal-restorednormals-faceslot-neck-static-frontambient-y100-z500-s100-d10-k2-base-d300-paddock-probe-headtiltprobe",
       "medusa-skeletal-restorednormals-faceslot-neck-unlit-all-frontambient-y100-z500-s100-rear-base-headtiltprobe"]
for c in cli:
    rep = "ue-" + c[len("medusa-"):] + "-report.json"
    shutil.copy2(A + rep, P + "ue-cli-headtiltprobe/" + rep)
    manifest["ue-cli-headtiltprobe"][rep] = sha(A + rep)
crop_box = (820, 100, 1260, 580)
Image.open(A + cli[3] + ".png").convert("RGB").crop(crop_box).save(
    P + "ue-cli-headtiltprobe/cli-rear-unlit-head-crop-v3.png", optimize=True)
manifest["ue-cli-headtiltprobe"]["cli-rear-unlit-head-crop-v3.png"] = {
    "sha256": sha(P + "ue-cli-headtiltprobe/cli-rear-unlit-head-crop-v3.png"),
    "source": cli[3] + ".png", "source_sha256": sha(A + cli[3] + ".png"), "crop_box_px": list(crop_box)}
# *.log is git-ignored, so the export log is stored byte-identical as headtilt-export-log.txt.
for extra, name in (("SK_Medusa_HeadTiltProbe.json", "SK_Medusa_HeadTiltProbe.json"),
                    ("headtilt-export.log", "headtilt-export-log.txt")):
    shutil.copy2(A + extra, P + "ue-cli-headtiltprobe/" + name)
    manifest["ue-cli-headtiltprobe"][name] = sha(A + extra)
# 3) Blender MCP part-ID renders (backface culling). Rear/side/front34L added 2026-09-28
#    so the rear-zone metric in junction_enclosed.py can be checked by eye.
R = "blender/renders/"
files = [f"id-cull-{v}-{t}.png" for v in ("neck-front", "neck-top55", "neck-front34R", "neck-front-low",
                                          "k2-front-d300", "k2-rear-d300") for t in ("v2", "v3", "rampprobe")]
files += [f"id-cull-{v}-{t}.png" for v in ("neck-rear", "neck-rear34L", "neck-rear34R", "neck-sideL", "neck-sideR",
                                          "neck-front34L") for t in ("v2", "v3")]
files += ["idsplit-k2-front-d300-v2.png", "idsplit-k2-front-d300-v3.png"]
for f in files:
    shutil.copy2(R + f, P + "blender-mcp-live/" + f); manifest["blender-mcp-live"][f] = sha(R + f)
# The labelled viewport comparisons are written by composites.py.
json.dump(manifest, open("assembled_manifest.json", "w"), indent=1)
print({k: len(v) for k, v in manifest.items()})
