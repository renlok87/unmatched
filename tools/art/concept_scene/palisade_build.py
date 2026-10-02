"""ENV-MAPS P8.1 palisade (ASSET-ENV-S-PROPS-001 / SM_Env_S_Palisade): the painted log palisades and posts W / NW.

  python -B tools/art/concept_scene/palisade_build.py      # -> <work>/SM_Env_S_Palisade.pre.npz + reports/palisade-build.json

Every painted log is rebuilt from C0 pixels (cs_geom: foot = the C0 ray hit on the island, vertical, top on the
painted top row, radius = half the painted width at that depth), sharpened or flat-topped, with rope bands around
each group and rope spans between posts (bevelled curves as tubes). Groups / logs / ropes = params palisade.groups
(read on the de-lit plate with a C0 grid). The same builder makes the bay / front piles (piles_build.py).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))
import cs_common as CS  # noqa: E402
import cs_geom as G  # noqa: E402


def build_posts(P: dict, ground: G.Ground, name: str, slot: str):
    cam = CS.cam0()
    rng = np.random.default_rng(P["seed"])
    parts = G.Parts()
    posts = {}
    info = []
    for g in P["groups"]:
        feet, radii, tops = [], [], []
        for i, lg in enumerate(g["logs"]):
            hit = ground.hit_px(*lg["footPx"])
            foot = hit - np.array([0.0, 0.0, P["sinkUU"]])
            h = G.vertical_top(hit, lg["topPx"][1], cam)
            r = G.px_radius(hit, lg["widthPx"], cam)
            top = hit + np.array([0.0, 0.0, h])
            tilt = np.array([rng.uniform(-1, 1), rng.uniform(-1, 1), 0.0]) * P["tiltUU"]
            V, F = G.log(foot, top + tilt, r, P["sides"], P["rings"], lg.get("point", g.get("point", 0.0)), rng)
            parts.add(V, F, "log")
            posts[f"{g['id']}/{i}"] = (foot, top + tilt, r)
            feet.append(hit)
            radii.append(r)
            tops.append(h)
        feet = np.array(feet)
        c = feet[:, :2].mean(0)
        for b in g.get("bands", []):
            rad = float(np.max(np.linalg.norm(feet[:, :2] - c, axis=1) + np.array(radii))) + P["ropeUU"] * 0.6
            z = float(feet[:, 2].mean() + b["frac"] * min(tops))
            V, F = G.band(c, rad, z, P["ropeUU"])
            parts.add(V, F, "band")
        info.append({"id": g["id"], "logs": len(g["logs"]),
                     "feet": [[round(float(v), 1) for v in f] for f in feet],
                     "heightsUU": [round(float(t), 1) for t in tops], "radiiUU": [round(float(r), 1) for r in radii]})
    for rp in P.get("ropes", []):
        fa, ta, _ = posts[rp["from"]]
        fb, tb, _ = posts[rp["to"]]
        a = fa + (ta - fa) * rp["fracA"]
        b = fb + (tb - fb) * rp["fracB"]
        V, F = G.rope(a, b, rp["sagUU"], P["ropeUU"])
        parts.add(V, F, "rope")
    first = info[0]["feet"][0]
    pivot = np.array([first[0], first[1], 0.0])
    mesh = parts.mesh(name, slot, pivot)
    return mesh, {"groups": info, "ropes": len(P.get("ropes", [])), "triangles": mesh.tris}


def run(key: str, name: str, slot: str, report: str) -> int:
    allp = CS.params()
    P = allp[key]
    island = CS.Mesh.load(CS.WORK / "SM_Env_S_Island.pre.npz")
    mesh, info = build_posts(P, G.Ground([island]), name, slot)
    mesh.save(CS.WORK / f"{name}.pre.npz")
    chk = {"maxTris": P["maxTris"], "trianglesOk": mesh.tris <= P["maxTris"]}
    CS.dump_json(CS.RUNS["props"] / "reports" / report,
                 {"schema": f"unmatched.env-s-{key}.build/1", "status": "предложено (geometry, CREATE stage)",
                  "mesh": name, "pivotBoard": [round(float(v), 3) for v in mesh.pivot], "info": info, "checks": chk,
                  "meshDigest": mesh.digest()})
    print(key.upper(), mesh.tris, "tris", len(info["groups"]), "groups")
    return 0 if chk["trianglesOk"] else 1


if __name__ == "__main__":
    sys.exit(run("palisade", "SM_Env_S_Palisade", "MI_Env_S_Palisade", "palisade-build.json"))
