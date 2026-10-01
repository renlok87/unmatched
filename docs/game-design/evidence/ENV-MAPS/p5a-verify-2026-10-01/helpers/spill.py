#!/usr/bin/env python3
"""ENV-MAPS P5a: warm spill of the Sarpedon hull lanterns on the east circles (S07 / S15 / S27), read-only.

Per circle the fill samples (fractions 0.35-0.75 of the ring radius, all angles) are projected into the frame with
the camera of its 'SHOT ctx' line (tools/art/map_surface/zone_separation.py Cam / MapData); residual = median CIELAB
of the frame samples - median CIELAB of the same samples on the original map (BC). The reference residual is the
median over the UNLIT circles (every warm point light of ALL given layouts - hull lanterns, campfires - farther than 450 uu,
so P3 and P5a share one reference set); the local
tint of a circle = its residual - the reference (dL*, da*, db*, dab = hypot(da, db)). Warm spill = + da / + db on the
east circles S07 / S15 / S27 (the same zones exist only on the ship side, so no same-zone control is possible).
Frames: P3 packaged K1 (lanterns before the P4 move), P4 editor K1, P5a packaged K1 x3, P5a live K1.
Usage: python spill.py --frame F --trace T [--frame F --trace T ...] --json OUT
"""
from __future__ import annotations
import argparse, json, math, sys
from pathlib import Path
import numpy as np
from PIL import Image
WT = Path("C:/tmp/wt-envmaps")
sys.path.insert(0, str(WT / "tools/art/map_surface"))
import zone_separation as Z  # noqa: E402

EAST = ("S07", "S15", "S27")
FRACS = (0.35, 0.45, 0.55, 0.65, 0.75)


def circle_px(cx, cy, r):
    a = np.radians(np.arange(0, 360, 6))
    return np.array([[cx + f * r * math.cos(t), cy + f * r * math.sin(t)] for f in FRACS for t in a])


def lch(l):
    return float(math.hypot(l[1], l[2])), float(math.degrees(math.atan2(l[2], l[1])) % 360)


def warm_lights(layout: dict):
    return [(l["id"], l["loc"]) for l in layout["lights"] if l.get("type") == "point"]


def run(md, frame: Path, trace: Path, lights, ref_lights=None):
    img = np.asarray(Image.open(frame).convert("RGB")).astype(np.float64)
    pos, pitch, yaw = Z.shot_camera(trace, frame.name)
    cam = Z.Cam(pos, pitch, yaw, img.shape[1], img.shape[0])
    r = md.vec["ring"]["r_center_px"]
    painted = {s["id"]: s["painted_px"] for s in md.vec["spaces"]}
    lant = [loc for i, loc in lights if i.startswith("ship-lantern")]
    per = {}
    for s in md.topo["spaces"]:
        px = circle_px(*painted[s["id"]], r)
        xy = cam.project(md.world(px))
        ok = (xy[:, 0] > 2) & (xy[:, 0] < img.shape[1] - 3) & (xy[:, 1] > 2) & (xy[:, 1] < img.shape[0] - 3)
        if ok.sum() < 20:
            continue
        f = np.median(Z.lab(Z.bilinear(img, xy[ok])), axis=0)
        o = np.median(Z.lab(md.bc_at(px)), axis=0)
        w = md.world(np.array([painted[s["id"]]]))[0]
        per[s["id"]] = {"zones": s["zones"], "frameLab": f, "origLab": o, "resid": f - o,
                        "nearestWarmUU": min(math.dist(w, l) for _, l in lights),
                        "nearestRefUU": min(math.dist(w, l) for _, l in (ref_lights or lights)),
                        "nearestLanternUU": min(math.dist(w, l) for l in lant)}
    unlit = [k for k, v in per.items() if v["nearestRefUU"] > 450]
    ref = np.median(np.array([per[k]["resid"] for k in unlit]), axis=0)
    def tint(v):
        d = v["resid"] - ref
        return {"dL": round(float(d[0]), 2), "da": round(float(d[1]), 2), "db": round(float(d[2]), 2),
                "dab": round(float(math.hypot(d[1], d[2])), 2)}
    allc = {k: {"nearestLanternUU": round(v["nearestLanternUU"], 1), "nearestWarmUU": round(v["nearestWarmUU"], 1),
                "zones": v["zones"], **tint(v)} for k, v in per.items()}
    out = {"frame": frame.name, "camera": {"pos": pos, "pitch": pitch, "yaw": yaw}, "circlesMeasured": len(per),
           "unlitReference": {"circles": sorted(unlit), "residualLab": [round(float(x), 2) for x in ref]},
           "east": {sid: allc.get(sid) for sid in EAST}, "allCircles": allc}
    near = [v for v in allc.values() if v["nearestLanternUU"] <= 350]
    out["lanternBand"] = {"circlesWithin350uu": sorted(k for k, v in allc.items() if v["nearestLanternUU"] <= 350),
                          "medianDa": round(float(np.median([v["da"] for v in near])), 2) if near else None,
                          "medianDb": round(float(np.median([v["db"] for v in near])), 2) if near else None}
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--frame", action="append", required=True)
    ap.add_argument("--trace", action="append", required=True)
    ap.add_argument("--label", action="append", required=True)
    ap.add_argument("--layout", action="append", required=True, help="layout json per frame (lantern positions)")
    ap.add_argument("--json")
    a = ap.parse_args()
    md = Z.MapData("sarpedon")
    # one UNLIT reference set for every frame: circles > 450 uu from the warm lights of ALL given layouts
    ref_lights = [x for lay in dict.fromkeys(a.layout) for x in warm_lights(json.loads(Path(lay).read_text(encoding="utf-8")))]
    res = {"schema": "unmatched.env-maps.sarpedon-lantern-spill/1", "method": " ".join(__doc__.strip().splitlines()[2:9]), "runs": []}
    for fr, tr, lb, lay in zip(a.frame, a.trace, a.label, a.layout):
        layout = json.loads(Path(lay).read_text(encoding="utf-8"))
        r = run(md, Path(fr), Path(tr), warm_lights(layout), ref_lights)
        r["label"] = lb
        r["lights"] = [{k: l[k] for k in ("id", "loc", "intensityCd", "radius")} for l in layout["lights"]]
        res["runs"].append(r)
        print(lb, "unlit", len(r["unlitReference"]["circles"]), json.dumps({k: v and {x: v[x] for x in ("nearestLanternUU", "dL", "da", "db", "dab")} for k, v in r["east"].items()}), "band", r["lanternBand"])
    if a.json:
        Path(a.json).write_text(json.dumps(res, ensure_ascii=False, indent=1) + "\n", encoding="utf-8", newline="\n")


if __name__ == "__main__":
    main()
