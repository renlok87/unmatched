"""ENV-MAPS P8.1 fort ruin (ASSET-ENV-S-FORT-001): the painted stone ruin NW of the map as real blocks.

  python -B tools/art/concept_scene/fort_build.py          # -> <work>/SM_Env_S_Fort.pre.npz + reports/fort-build.json

The painted ruin (sarpedon.paste.json planeZones.fort, C0 (330, 172)-(645, 172)) is a wall of big ashlar blocks with a
tall left end, a low middle, a right part with a small arch and fallen blocks at its foot. It is rebuilt along its
painted base line (C0 ray hits on the island mesh) as courses of chamfered blocks (bevel ~2 uu: soft highlights under
the key light) whose ragged top follows the painted top silhouette (params fort.profilePx, cast onto the wall's
vertical front plane), with the arch opening left free and rubble blocks in front. Deterministic (seeded).

Deviation from the task text ("modular_fort_01 walls/arch"): the Poly Haven modular_fort_01 modules are clean 8.5 m
walls (2.6-4.2 m thick); scaled to the painted ruin (up to ~280 uu at C0) they would be 80-130 uu thick and need
boolean ruin cuts that do not follow the painted outline. The block generator fits the painted outline and block
pattern by construction; modular_fort_01 stays listed as the reference (CREDITS) and is not exported.
"""
from __future__ import annotations

import json
import math
import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))
import cs_common as CS  # noqa: E402
import cs_geom as G  # noqa: E402

NAME = "SM_Env_S_Fort"


def build(P: dict, ground: G.Ground):
    cam = CS.cam0()
    rng = np.random.default_rng(P["seed"])
    A = ground.hit_px(*P["basePx"][0])
    B = ground.hit_px(*P["basePx"][1])
    u = np.r_[(B - A)[:2], 0.0]
    L = np.linalg.norm(u)
    u /= L
    n = np.array([-u[1], u[0], 0.0])
    if n[1] < 0:
        n = -n  # front = towards the K1 camera (+Y)
    base_z = min(A[2], B[2]) - P["sinkUU"]
    # profile: rays of the painted top silhouette on the vertical front plane through A (normal n)
    prof = []
    for x, y in P["profilePx"]:
        d = cam.rays(np.array(float(x)), np.array(float(y)))
        t = ((A - cam.pos) @ n) / (d @ n)
        Q = cam.pos + t * d
        prof.append(((Q - A) @ u, Q[2]))
    prof = np.array(sorted(prof))
    s0, s1 = prof[0, 0], prof[-1, 0]

    def H(s):
        return np.interp(s, prof[:, 0], prof[:, 1])

    # arch (painted opening) on the front plane
    ac = P["archPx"]
    arch = []
    for x, y in ((ac["cx"] - ac["halfWidthPx"], ac["springY"]), (ac["cx"] + ac["halfWidthPx"], ac["springY"]),
                 (ac["cx"], ac["topY"])):
        d = cam.rays(np.array(float(x)), np.array(float(y)))
        t = ((A - cam.pos) @ n) / (d @ n)
        Q = cam.pos + t * d
        arch.append(((Q - A) @ u, Q[2]))
    a_s0, a_s1 = arch[0][0], arch[1][0]
    a_c, a_w = (a_s0 + a_s1) / 2, (a_s1 - a_s0) / 2
    a_spring, a_top = (arch[0][1] + arch[1][1]) / 2, arch[2][1]

    def in_arch(s, z):
        if abs(s - a_c) > a_w or z < base_z:
            return False
        if z <= a_spring:
            return True
        ry = max(a_top - a_spring, 1.0)
        return ((s - a_c) / a_w) ** 2 + ((z - a_spring) / ry) ** 2 <= 1.0

    parts = G.Parts()
    th = P["thicknessUU"]
    yaw = math.degrees(math.atan2(u[1], u[0]))
    z = base_z
    course = 0
    blocks = 0
    while z < prof[:, 1].max():
        ch = rng.uniform(*P["courseUU"])
        s = s0 - rng.uniform(0, P["blockUU"][0])
        while s < s1:
            bl = rng.uniform(*P["blockUU"])
            sa, sb = max(s, s0), min(s + bl, s1)
            s += bl
            if sb - sa < P["blockUU"][0] * 0.4:
                continue
            sc = (sa + sb) / 2
            top = H(sc)
            if z + ch * P["keepFrac"] > top:
                continue
            if in_arch(sc, z + ch / 2) or in_arch(sa + 2, z + ch / 2) or in_arch(sb - 2, z + ch / 2):
                continue
            hh = ch * rng.uniform(0.92, 0.98)
            if z + hh > top + ch * 0.25:
                hh = max(top - z + ch * 0.25, ch * 0.4)
            depth = th * rng.uniform(0.86, 1.0)
            ctr = A + u * sc - n * (th / 2 - rng.uniform(-P["protrudeUU"], P["protrudeUU"])) + \
                np.array([0.0, 0.0, z + hh / 2 - A[2]])
            ctr[2] = z + hh / 2
            loose = top - (z + hh) < ch * 1.2
            tilt = (rng.uniform(-3, 3), rng.uniform(-3, 3)) if loose else (0.0, 0.0)
            V, F = G.chamfer_box(ctr, (sb - sa - P["jointUU"], depth, hh), yaw + rng.uniform(-2, 2), P["bevelUU"], tilt)
            parts.add(V, F, "block")
            blocks += 1
        z += ch
        course += 1
    # rubble in front of the wall
    for i in range(P["rubble"]["n"]):
        sc = rng.uniform(s0 + 20, s1 - 20)
        off = rng.uniform(*P["rubble"]["frontUU"])
        xy = A[:2] + u[:2] * sc + n[:2] * off
        gz = ground.height_at(*xy)
        sz = rng.uniform(*P["rubble"]["sizeUU"])
        dims = (sz * rng.uniform(1.0, 1.6), sz * rng.uniform(0.8, 1.1), sz * rng.uniform(0.6, 0.9))
        V, F = G.chamfer_box([xy[0], xy[1], gz + dims[2] * 0.35], dims, rng.uniform(0, 180), P["bevelUU"],
                             (rng.uniform(-12, 12), rng.uniform(-12, 12)))
        parts.add(V, F, "rubble")
    pivot = np.array([*(A[:2] + u[:2] * (s0 + s1) / 2), base_z])
    mesh = parts.mesh(NAME, "MI_Env_S_Fort", pivot)
    info = {"blocks": blocks, "courses": course, "rubble": P["rubble"]["n"], "triangles": mesh.tris,
            "lengthUU": round(float(s1 - s0), 1), "heightMaxUU": round(float(prof[:, 1].max() - base_z), 1),
            "baseZ": round(float(base_z), 1), "yawDeg": round(yaw, 2),
            "baseBoard": [[round(float(v), 1) for v in A], [round(float(v), 1) for v in B]],
            "arch": {"centreS": round(a_c, 1), "halfWidthUU": round(a_w, 1), "springZ": round(a_spring, 1),
                     "topZ": round(a_top, 1)}}
    return mesh, info


def main() -> int:
    allp = CS.params()
    P = allp["fort"]
    island = CS.Mesh.load(CS.WORK / "SM_Env_S_Island.pre.npz")
    mesh, info = build(P, G.Ground([island]))
    mesh.save(CS.WORK / f"{NAME}.pre.npz")
    chk = {"maxTris": P["maxTris"], "trianglesOk": mesh.tris <= P["maxTris"]}
    CS.dump_json(CS.RUNS["fort"] / "reports" / "fort-build.json",
                 {"schema": "unmatched.env-s-fort.build/1", "status": "предложено (geometry, CREATE stage)",
                  "mesh": NAME, "pivotBoard": [round(float(v), 3) for v in mesh.pivot], "info": info, "checks": chk,
                  "meshDigest": mesh.digest()})
    print("FORT", json.dumps(info))
    return 0 if chk["trianglesOk"] else 1


if __name__ == "__main__":
    sys.exit(main())
