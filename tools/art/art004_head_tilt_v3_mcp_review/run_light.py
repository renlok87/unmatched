import ue, json, sys, time, capture, os
from setup_scene import xf
light, statefile, outdir = sys.argv[1], sys.argv[2], sys.argv[3]
names = sys.argv[4].split(",")
os.makedirs(outdir, exist_ok=True)
st = json.load(open(statefile))
A = st["actors"]; loc = st["loc"]
V = capture.views(loc)
def activate(tag):
    other = "v3" if tag == "v2" else "v2"
    ue.call(ue.ACTOR, "set_actor_transform", {"actor": A[other], "xform": xf(20000, 20000, 0), "worldspace": True})
    ue.call(ue.ACTOR, "set_actor_transform", {"actor": A[tag], "xform": xf(loc["x"], loc["y"], loc["z"]), "worldspace": True})
    time.sleep(1.0)
meta = {}
for tag in ("v2", "v3"):
    activate(tag)
    for name in names:
        cam = capture.look(*V[name])
        capture.capture(cam, os.path.join(outdir, "_warm.png"))
        time.sleep(0.3)
        path = os.path.join(outdir, f"ue-mcp-{light}-{name}-{tag}.png")
        m = capture.capture(cam, path)
        meta[f"{light}/{name}/{tag}"] = m
        print(path, m["cameraFOV"], m["viewport_px"])
os.remove(os.path.join(outdir, "_warm.png"))
json.dump(meta, open(os.path.join(outdir, f"meta-{light}.json"), "w"), indent=1)
