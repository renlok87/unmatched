"""ENV-MAPS P8.1 banner cloth (ASSET-ENV-S-PROPS-001 / SM_Env_S_Banner): the red banner hanging VERTICALLY from the
ship rail (task §3: P7c hung SM_EnvCP_BannerCloth along the C0 screen-down = a sheared panel, diagnosis §0.2 #5).

  python -B tools/art/concept_scene/banner_build.py        # -> <work>/SM_Env_S_Banner.pre.npz + reports/banner-build.json

Same cloth construction and UV contract as tools/art/concept_paste/blender_cp_assets.py build_banner (so the P7c
material M_EnvCP_Banner / MI_EnvCP_Banner - sigil pattern + WPO wind from UV0 - applies unchanged): a cloth grid with
UV0 u across, v 0 at the rail .. 1 at the hem (Blender V up = 1 - v), folds growing to the hem, gathered top, a toothed
hem, and an 8-sided rod above it at Blender V 1.04..1.06 (the material paints it as the rod, no wind); but the hang
direction is straight down (0, 0, -1). Pivot = the rod top centre (the layout puts it on the rail point). Not baked:
its slot keeps MI_EnvCP_Banner (manifest "materialExisting").
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

NAME = "SM_Env_S_Banner"


def build(B: dict):
    W, L = float(B["widthUU"]), float(B["lengthUU"])
    nu, nv = int(B["gridU"]), int(B["gridV"])
    fold_a, folds, curl, gather = float(B["foldAmpUU"]), float(B["folds"]), float(B["curlUU"]), float(B["gatherTop"])
    tat, teeth = float(B["tatterUU"]), int(B["tatterTeeth"])
    rod_r, rod_over, rod_clear = float(B["rodRadiusUU"]), float(B["rodOverhangUU"]), float(B["rodClearUU"])
    rng = np.random.default_rng(int(B["seed"]))
    jit = rng.uniform(0.35, 1.0, size=nu + 1)
    hang = np.array([0.0, 0.0, -1.0])
    nrm = np.array([1.0, 0.0, 0.0])  # cloth faces +X (yaw 90 in the layout turns it to the K1 camera)
    V, UVv = [], []
    grid = np.zeros((nv + 1, nu + 1), int)
    for j in range(nv + 1):
        v = j / nv
        wk = gather + (1.0 - gather) * min(1.0, v / 0.12)
        for i in range(nu + 1):
            u = i / nu
            y = (u - 0.5) * W * wk
            dl = v * L
            t = abs(((u * teeth) % 1.0) - 0.5) * 2.0
            if j == nv:
                dl -= tat * t * jit[i]
            elif j == nv - 1:
                dl -= 0.35 * tat * t * jit[i]
            vv = dl / L
            off = fold_a * (0.35 + 0.65 * vv) * math.sin(2.0 * math.pi * folds * u + 0.7) + curl * vv * vv
            grid[j, i] = len(V)
            V.append(np.array([0.0, y, 0.0]) + dl * hang + off * nrm)
            UVv.append((u, 1.0 - vv))
    F, UV = [], []
    for j in range(nv):
        for i in range(nu):
            a, b, c, d = grid[j + 1, i], grid[j + 1, i + 1], grid[j, i + 1], grid[j, i]  # CCW seen from +X
            for tri in ((a, b, c), (a, c, d)):
                F.append(list(tri))
                UV.append([UVv[k] for k in tri])
    sides = 8
    zc = rod_clear + rod_r
    y0, y1 = -W / 2 - rod_over, W / 2 + rod_over
    r0, r1 = [], []
    for k in range(sides):
        ang = 2.0 * math.pi * k / sides
        r0.append(len(V))
        V.append(np.array([rod_r * math.cos(ang), y0, zc + rod_r * math.sin(ang)]))
        r1.append(len(V))
        V.append(np.array([rod_r * math.cos(ang), y1, zc + rod_r * math.sin(ang)]))
    for k in range(sides):
        k2 = (k + 1) % sides
        q = [r0[k], r0[k2], r1[k2], r1[k]]
        quv = [(0.0, 1.06), (0.0, 1.04), (1.0, 1.04), (1.0, 1.06)]
        for tri in ((0, 1, 2), (0, 2, 3)):
            F.append([q[t] for t in tri])
            UV.append([quv[t] for t in tri])
    for k in range(1, sides - 1):
        F.append([r0[0], r0[k + 1], r0[k]])
        UV.append([(0.5, 1.05)] * 3)
        F.append([r1[0], r1[k], r1[k + 1]])
        UV.append([(0.5, 1.05)] * 3)
    V = np.array(V)
    F = np.array(F, np.int64)
    # rod caps / sides: orient outward from the rod axis (cloth faces keep +X)
    P = V[F]
    n = np.cross(P[:, 1] - P[:, 0], P[:, 2] - P[:, 0])
    cen = P.mean(1)
    rod = cen[:, 2] > 0.5 * zc
    axis_pt = np.c_[np.zeros(len(cen)), np.clip(cen[:, 1], y0 + 1e-3, y1 - 1e-3), np.full(len(cen), zc)]
    caps = rod & ((np.abs(cen[:, 1] - y0) < 1e-6) | (np.abs(cen[:, 1] - y1) < 1e-6))
    out = cen - axis_pt
    out[caps] = np.c_[np.zeros(caps.sum()), np.sign(cen[caps, 1]), np.zeros(caps.sum())]
    flip = rod & (np.einsum("ij,ij->i", n, out) < 0)
    F[flip] = F[flip][:, ::-1]
    UV = np.array(UV, float)
    UV[flip] = UV[flip][:, ::-1]
    top = zc + rod_r
    V = V - np.array([0.0, 0.0, top])  # pivot = rod top centre
    mesh = CS.Mesh(NAME, V, F, UV, np.zeros(len(F), int), np.ones(len(F), bool), ["MI_EnvCP_Banner"], (0.0, 0.0, 0.0))
    info = {"clothWidthUU": W, "clothLengthUU": L, "rodTopToHemUU": round(float(-V[:, 2].min()), 3), "triangles": int(len(F)), "hang": [0.0, 0.0, -1.0],
            "uv": "u across, v 0 at the rail .. 1 at the hem (UE V down); rod at Blender V 1.04..1.06 (M_EnvCP_Banner contract)"}
    return mesh, info


def main() -> int:
    B = CS.params()["banner"]
    mesh, info = build(B)
    mesh.save(CS.WORK / f"{NAME}.pre.npz")
    CS.dump_json(CS.RUNS["props"] / "reports" / "banner-build.json",
                 {"schema": "unmatched.env-s-banner.build/1", "status": "предложено (geometry, CREATE stage)",
                  "mesh": NAME, "info": info, "meshDigest": mesh.digest()})
    print("BANNER", json.dumps(info))
    return 0


if __name__ == "__main__":
    sys.exit(main())
