"""ENV-MAPS P9 F4 waterfall cascade (ASSET-ENV-S-PROPS-001 / SM_Env_S_Cascade + SM_Env_S_CascadeFoam).

  python -B tools/art/concept_scene/cascade_build.py   # -> <work>/SM_Env_S_Cascade{,Foam}.pre.npz + reports/cascade-build.json

The concept paints a WIDE MULTI-TIER cascade down the front cliff (C0 x ~640-1001, sarpedon.paste.json overlays
'waterfall' pxRect) from under the near frame beam into the sea: several streams between rock columns, white foam
where they land on the ledges, spray at the bottom. P5c / P8 had one narrow boxy sheet with a hard lip.

Built on the island's own cliff (island_build.py rings, <work>/island_rim.npz: the front rim in the cascade X range
has the deep outlet of island.nearLip): per stream a ribbon of columns across X; each column follows the cliff
profile rings (lip -> ledge 1 -> ... -> ledge 3 -> the sea plane) held clear of the rock (outward offsets past the
rock displacement, lifted over the ledges) and bowed outward on every drop (the water leaves each ledge lip with
momentum), from just under the near beam's bottom edge down to the sea plane. UV0: u across the whole cascade 0..1
(all streams: M_EnvWaterfall's side fades only at its outer edges, the rock gaps are geometry), v along the flow 0..1
per tier (an island per tier: every tier has its lip foam and its landing fade), authored lane K style (Blender v =
s / L top -> bottom, flipped by the FBX import: FallCard.w = 1; FallCard.xy = the cascade width x the mean tier
length). Foam pads (the second mesh) lie on each landing (ledges 1-3) and a wider one on the sea plane at the foot;
UV0 u across the cascade, v from the landing edge 0 to the outer edge 1.

Not baked: track B's translucent water MIs MI_EnvScene_FallsSheet / MI_EnvScene_FallsFoam (children of the P5c
MI_EnvWaterfall_Sarpedon); the manifest's top-level "materials" gives them this build's FallCard. The tier landings (anchors for the mist / spray fx of fx-plan.sarpedon.json) are in the build report.
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

NAME = "SM_Env_S_Cascade"
FOAM = "SM_Env_S_CascadeFoam"
SLOT = "MI_EnvScene_FallsSheet"  # track B's material-route MIs (children of MI_EnvWaterfall_Sarpedon)
FOAM_SLOT = "MI_EnvScene_FallsFoam"


def catmull(P: np.ndarray, n_sub: int) -> np.ndarray:
    """Centripetal-ish (uniform) Catmull-Rom through the points (ends duplicated), n_sub samples per segment."""
    Q = np.vstack([P[:1], P, P[-1:]])
    out = []
    for i in range(1, len(Q) - 2):
        p0, p1, p2, p3 = Q[i - 1], Q[i], Q[i + 1], Q[i + 2]
        for j in range(n_sub):
            t = j / n_sub
            t2, t3 = t * t, t * t * t
            out.append(0.5 * ((2 * p1) + (-p0 + p2) * t + (2 * p0 - 5 * p1 + 4 * p2 - p3) * t2 + (-p0 + 3 * p1 - 3 * p2 + p3) * t3))
    out.append(Q[-2])
    return np.array(out)


def rim_columns(rimd, x_cols: np.ndarray):
    """The cliff rings interpolated at board X positions along the front rim (the near rim is monotonic in X there):
    rings (K, m, 3) and the outward horizontal normals (m, 2)."""
    R, rings = rimd["R"], rimd["rings"]
    sel = np.nonzero((R[:, 1] > CS.C.FRAME_HY) & (np.abs(R[:, 0]) < 600))[0]
    order = sel[np.argsort(R[sel, 0])]
    xs = R[order, 0]
    K = rings.shape[0]
    out = np.zeros((K, len(x_cols), 3))
    for k in range(K):
        for c in range(3):
            out[k, :, c] = np.interp(x_cols, xs, rings[k, order, c])
    nrm = CS.vertex_normals_2d(R)[order]
    n2 = np.c_[np.interp(x_cols, xs, nrm[:, 0]), np.interp(x_cols, xs, nrm[:, 1])]
    n2 /= np.linalg.norm(n2, axis=1, keepdims=True)
    return out, n2


def column_path(ring_pts: np.ndarray, n2: np.ndarray, P: dict, top: np.ndarray, sea_z: float):
    """The water path of one column: the top point under the beam, then each ring point pushed out of the rock
    (offsets per ring kind), drops bowed outward; densified (Catmull-Rom) and cut at the sea plane.
    Returns (points (q, 3), landing indices {tier: index})."""
    off = P["offsetUU"]
    lift = P["ledgeLiftUU"]
    nh = np.array([n2[0], n2[1], 0.0])
    pts = [top]
    kinds = ["top"]
    K = len(ring_pts)
    for k in range(1, K):
        q = ring_pts[k].copy()
        kind = "lip" if k % 2 == 1 else "land"
        if k == K - 1:
            kind = "sea"
        q = q + nh * (off["lip"] if kind == "lip" else off["land"] if kind == "land" else off["sea"])
        if kind == "land":
            q[2] += lift
        pts.append(q)
        kinds.append(kind)
    # bow every drop (lip -> land / sea and top -> first ring) outward by a fraction of its height
    dense, dkinds = [pts[0]], [kinds[0]]
    steep_set = set(P["steepSegments"])  # by segment index: the same sampling in every column (equal ribbon rows)
    for a in range(len(pts) - 1):
        A, B = pts[a], pts[a + 1]
        drop = max(A[2] - B[2], 0.0)
        steep = a in steep_set
        n_sub = P["subDrop"] if steep else P["subLedge"]
        for j in range(1, n_sub + 1):
            t = j / n_sub
            Q = A + (B - A) * t
            if steep:
                # leaves the lip horizontally (z ~ quadratic), bulges outward mid-drop
                Q[2] = A[2] - drop * t ** P["fallPower"]
                Q = Q + nh * (P["bowFrac"] * drop * math.sin(math.pi * t) ** 0.8)
            dense.append(Q)
            dkinds.append(kinds[a + 1] if j == n_sub else "mid")
    D = np.array(dense)
    # cut at the sea plane (+ the foam lift): the last point is the first crossing
    zc = sea_z + P["seaLiftUU"]
    below = np.nonzero(D[:, 2] < zc)[0]
    if len(below):
        i = below[0]
        t = (D[i - 1, 2] - zc) / (D[i - 1, 2] - D[i, 2])
        D = np.vstack([D[:i], D[i - 1] + (D[i] - D[i - 1]) * t])
        dkinds = dkinds[:i] + ["sea"]
    landings = {}
    tier = 0
    for i, kd in enumerate(dkinds):
        if kd in ("land", "sea"):
            tier += 1
            landings[tier] = i
    return D, landings


def ragged_top_dip(P: dict, x: np.ndarray) -> np.ndarray:
    """P10 (RD-3 V-1): how far (uu, >= 0) each column's top sits under the default top (beam bottom - topBelowBeamUU):
    Gaussian notches [x, depth, half-width] (the rock teeth of a torn outlet) + positive value noise, so the water's
    top edge is no straight line under the beam. No "rag" block: 0 (the P9 straight top)."""
    R = P.get("rag")
    x = np.asarray(x, float)
    if not R:
        return np.zeros_like(x)
    d = np.zeros_like(x)
    for cx, depth, hw in R.get("notches", []):
        d = np.maximum(d, float(depth) * np.exp(-0.5 * ((x - float(cx)) / float(hw)) ** 2))
    n = CS.value_noise(x, np.zeros_like(x), float(R.get("noiseScaleUU", 20.0)), int(R.get("seed", 1)))
    return d + float(R.get("noiseUU", 0.0)) * (0.5 * n + 0.5)


def column_phase(P: dict, si: int, x: np.ndarray) -> np.ndarray:
    """P10 (RD-3 V-1): the tier phase of every column (0 .. <1, a fraction of the tier): per stream a base offset +
    value noise; ribbon() maps v -> phase + (1 - phase) v, so the lip foam / streak bands of the tiers are offset per
    stream (and wobble inside it) instead of one straight band across the cascade. No "phase" block: 0."""
    Q = P.get("phase")
    x = np.asarray(x, float)
    if not Q:
        return np.zeros_like(x)
    base = float(Q["streamsV"][si % len(Q["streamsV"])])
    n = CS.value_noise(x, np.zeros_like(x), float(Q.get("noiseScaleUU", 30.0)), int(Q.get("seed", 1)) + si)
    return np.clip(base + float(Q.get("noise", 0.0)) * (0.5 * n + 0.5), 0.0, 0.45)


def ribbon(cols: list[np.ndarray], u: np.ndarray, cuts: list[int], phase: np.ndarray | None = None):
    """Quads between consecutive column paths (truncated to the shortest), one UV island per tier: rows
    cuts[k] .. cuts[k + 1] get v = arc length from the tier's lip / the tier's length (top -> bottom, Blender v), so
    every tier has its own lip foam and its landing fade; the tier boundaries are duplicated vertices. u = the given
    global u across the whole cascade. P10: phase (per column, 0 .. <1) maps v -> phase + (1 - phase) v (the tier's
    lip band starts lower on that column). Returns V, F, UV, the mean tier length."""
    m = len(cols)
    q = min(len(c) for c in cols)
    cols = [c[:q] for c in cols]
    cuts = [c for c in cuts if c < q - 1] + [q - 1]
    ph = np.zeros(m) if phase is None else np.asarray(phase, float)
    Vs, F, UV, lens = [], [], [], []
    base = 0
    for k in range(len(cuts) - 1):
        r0, r1 = cuts[k], cuts[k + 1]
        rows = r1 - r0 + 1
        part = [c[r0:r1 + 1] for c in cols]
        seg = np.array([np.r_[0.0, np.cumsum(np.linalg.norm(np.diff(c, axis=0), axis=1))] for c in part])
        L = seg[:, -1:]
        lens.append(float(L.mean()))
        v = seg / np.maximum(L, 1e-6)
        v = ph[:, None] + (1.0 - ph[:, None]) * v
        Vs.append(np.vstack(part))
        for i in range(m - 1):
            for j in range(rows - 1):
                a, b = base + i * rows + j, base + (i + 1) * rows + j
                c, d = base + (i + 1) * rows + j + 1, base + i * rows + j + 1
                uv = {a: (u[i], v[i, j]), b: (u[i + 1], v[i + 1, j]), c: (u[i + 1], v[i + 1, j + 1]), d: (u[i], v[i, j + 1])}
                for tri in ((a, b, c), (a, c, d)):
                    F.append(tri)
                    UV.append([uv[t] for t in tri])
        base += m * rows
    return np.vstack(Vs), np.array(F, np.int64), np.array(UV, float), lens


def orient(V, F, UV, want):
    """Flip faces whose normal points against `want(face centre)` (unit vectors)."""
    P = V[F]
    n = np.cross(P[:, 1] - P[:, 0], P[:, 2] - P[:, 0])
    c = P.mean(1)
    bad = np.einsum("ij,ij->i", n, want(c)) < 0
    F = F.copy()
    UV = UV.copy()
    F[bad] = F[bad][:, ::-1]
    UV[bad] = UV[bad][:, ::-1]
    return F, UV


def build(P: dict, rimd, sea_z: float, beam: dict):
    streams = P["streams"]
    sheets_V, sheets_F, sheets_UV = [], [], []
    foam_V, foam_F, foam_UV = [], [], []
    base = fbase = 0
    tiers: dict[int, list] = {}
    dims = []
    for si, (x0, x1) in enumerate(streams):
        nc = max(2, int(math.ceil((x1 - x0) / P["columnStepUU"])) + 1)
        xc = np.linspace(x0, x1, nc)
        rp, n2 = rim_columns(rimd, xc)
        dip = ragged_top_dip(P, xc)
        cols, lands = [], []
        for c in range(nc):
            # the top: under the near beam's bottom edge, just in front of its face (P10: torn, dip >= 0)
            top = np.array([xc[c], beam["faceY"] + P["topOutUU"], beam["bottomZ"] - P["topBelowBeamUU"] - dip[c]])
            D, ld = column_path(rp[:, c, :], n2[c], P, top, sea_z)
            cols.append(D)
            lands.append(ld)
        q = min(len(c) for c in cols)
        # u across the whole cascade (side fades only at its outer edges), v per tier (cut at the landings);
        # P9 tune (uvPerStream): u per stream, so M_EnvWaterfall's wobbling side fades soften every stream's sides
        # (the streams overlap a little: no straight rock gaps / rectangular panels)
        if P.get("uvPerStream"):
            X0, X1 = x0, x1
        else:
            X0, X1 = streams[0][0], streams[-1][1]
        u = (xc - X0) / (X1 - X0)
        cuts = [0] + sorted({lands[0][t] for t in lands[0]})
        V, F, UV, tier_len = ribbon(cols, u, cuts, column_phase(P, si, xc))
        L = float(np.mean(tier_len))
        # faces towards the viewer: outward (+Y mostly) and up
        F, UV = orient(V, F, UV, lambda c: np.tile(np.array([0.0, 0.8, 0.6]), (len(c), 1)))
        sheets_V.append(V)
        sheets_F.append(F + base)
        sheets_UV.append(UV)
        base += len(V)
        dims.append({"stream": si, "xUU": [x0, x1], "widthUU": round(float(np.linalg.norm(cols[-1][0] - cols[0][0])), 1),
                     "tierLengthsUU": [round(v, 1) for v in tier_len], "columns": nc, "rows": q})
        # landings: per tier the landing points across the stream -> foam pads + anchors
        n_t = min(len(l) for l in lands)
        for t in range(1, n_t + 1):
            idx = [l[t] for l in lands]
            Lp = np.array([cols[c][min(idx[c], len(cols[c]) - 1)] for c in range(nc)])
            nrm = np.array([n2[c][0] for c in range(nc)]), np.array([n2[c][1] for c in range(nc)])
            nh = np.c_[nrm[0], nrm[1], np.zeros(nc)]
            sea = t == n_t
            depth = P["foamDepthUU"]["sea" if sea else "ledge"]
            widen = P["foamWiden"] if sea else 1.0
            back = P["foamBackUU"]
            cen = Lp.mean(0)
            Lw = cen + (Lp - cen) * widen
            # P10 (RD-3 V-1): a torn foam pad - per column depth x [lo, hi] and the inner edge +- innerUU (value
            # noise along X, a different seed per tier / stream) instead of a straight white strip per ledge
            J = P.get("foamJitter")
            if J:
                xs = Lw[:, 0]
                nd = CS.value_noise(xs, np.full_like(xs, 13.0 * t), float(J.get("scaleUU", 18.0)), int(J.get("seed", 1)) + 7 * si)
                ni = CS.value_noise(xs, np.full_like(xs, 29.0 * t), float(J.get("scaleUU", 18.0)), int(J.get("seed", 1)) + 7 * si + 3)
                lo, hi = (float(v) for v in J.get("depthFrac", (1.0, 1.0)))
                dcol = depth * (lo + (hi - lo) * (0.5 * nd + 0.5))
                icol = back + float(J.get("innerUU", 0.0)) * ni
            else:
                dcol = np.full(nc, float(depth))
                icol = np.full(nc, float(back))
            inner = Lw - nh * icol[:, None] + np.array([0.0, 0.0, P["foamLiftUU"]])
            outer = Lw + nh * dcol[:, None] + np.array([0.0, 0.0, P["foamLiftUU"]])
            if sea:
                inner[:, 2] = outer[:, 2] = sea_z + P["seaLiftUU"] + P["foamLiftUU"]
            else:
                # follow the ledge: the outer edge drops with the ledge slope to its lip (never into the rock)
                outer[:, 2] = np.maximum(outer[:, 2], inner[:, 2] - depth * 0.3)
            Vp = np.vstack([inner, outer])
            Fp, UVp = [], []
            for c in range(nc - 1):
                a, b, d, e = c, c + 1, nc + c + 1, nc + c
                uvs = {a: (u[c], 0.0), b: (u[c + 1], 0.0), d: (u[c + 1], 1.0), e: (u[c], 1.0)}
                for tri in ((a, b, d), (a, d, e)):
                    Fp.append(tri)
                    UVp.append([uvs[x] for x in tri])
            Fp, UVp = orient(Vp, np.array(Fp, np.int64), np.array(UVp, float), lambda c: np.tile(np.array([0.0, 0.0, 1.0]), (len(c), 1)))
            foam_V.append(Vp)
            foam_F.append(Fp + fbase)
            foam_UV.append(UVp)
            fbase += len(Vp)
            tiers.setdefault(t, []).append({"centre": cen, "width": float(np.linalg.norm(Lw[-1] - Lw[0])), "sea": sea})
    pivot = np.array(P["pivot"], float)
    Vs, Fs, UVs = np.vstack(sheets_V), np.vstack(sheets_F), np.vstack(sheets_UV)
    sheet = CS.Mesh(NAME, Vs - pivot, Fs, UVs, np.zeros(len(Fs), int), np.ones(len(Fs), bool), [SLOT], pivot)
    Vf, Ff, UVf = np.vstack(foam_V), np.vstack(foam_F), np.vstack(foam_UV)
    foam = CS.Mesh(FOAM, Vf - pivot, Ff, UVf, np.zeros(len(Ff), int), np.ones(len(Ff), bool), [FOAM_SLOT], pivot)
    anchors = []
    for t in sorted(tiers):
        cs = np.array([e["centre"] for e in tiers[t]])
        anchors.append({"tier": t, "landing": [round(float(v), 2) for v in cs.mean(0)],
                        "widthUU": round(float(cs[:, 0].max() - cs[:, 0].min() + np.mean([e["width"] for e in tiers[t]])), 1),
                        "sea": bool(tiers[t][0]["sea"]),
                        "streams": [[round(float(v), 2) for v in c] for c in cs]})
    # FallCard: the whole cascade width (uvPerStream: the mean stream width) x the mean tier length
    card = [round(float(np.mean([x1 - x0 for x0, x1 in streams]) if P.get("uvPerStream")
                        else streams[-1][1] - streams[0][0]), 1),
            round(float(np.mean([v for d in dims for v in d["tierLengthsUU"]])), 1)]
    info = {"streams": dims, "tiers": anchors, "fallCard": card, "sheetTris": sheet.tris, "foamTris": foam.tris,
            "zRange": [round(float(Vs[:, 2].min()), 1), round(float(Vs[:, 2].max()), 1)]}
    return sheet, foam, info


def c0_coverage(sheet: CS.Mesh, island: CS.Mesh | None, band: CS.Mesh | None, out_png: Path | None = None) -> dict:
    """Painted-width coverage at C0: the painted water region (sarpedon.paste.json overlays 'waterfall' pxRect), the
    share of its columns with a visible water pixel (depth test against the island + frame band), over the C0 frame
    (y <= 1080) and over the whole painted rect (extended canvas); + the visible water pixel share of the rect."""
    from PIL import Image
    spec = CS.spec()
    rect_px = next(o for o in spec["overlays"] if o["id"] == "waterfall")["pxRect"]
    cam = CS.cam0()
    rect = CS.RECT_B
    k = 1.0
    w, h = int((rect[2] - rect[0]) * k), int((rect[3] - rect[1]) * k)
    d_w, _ = CS.raster_tris(cam, sheet.board(), sheet.F, w, h, rect=rect)
    occ = np.full((h, w), np.inf)
    for m in (island, band):
        if m is not None:
            d, _ = CS.raster_tris(cam, m.board(), m.F, w, h, rect=rect, cull_back=True)
            occ = np.minimum(occ, d)
    vis = np.isfinite(d_w) & (d_w <= occ + 0.5)
    x0, y0, x1, y1 = rect_px
    cx0, cx1 = int(x0 - rect[0]), int(x1 - rect[0])
    res = {"paintedRectPx": rect_px}
    for label, ylim in (("c0Frame", 1080.0), ("extended", float(y1))):
        ry0, ry1 = int(y0 - rect[1]), int(min(ylim, y1) - rect[1])
        roi = vis[ry0:ry1, cx0:cx1]
        res[label] = {"widthCoverage": round(float(roi.any(0).mean()), 4), "areaShare": round(float(roi.mean()), 4)}
    if out_png:
        img = CS.plate_c0(rect, w, h, CS.DELIT_EXT)
        o = img.copy()
        o[vis] = o[vis] * 0.4 + np.array([0.2, 0.7, 1.0]) * 0.6
        im = Image.fromarray(np.clip(o * 255, 0, 255).astype(np.uint8))
        im = im.crop((int(400 - rect[0]), int(760 - rect[1]), int(1500 - rect[0]), int(1296 - rect[1])))
        Path(out_png).parent.mkdir(parents=True, exist_ok=True)
        im.save(out_png, quality=88)
    return res


def beam_of(allp: dict) -> dict:
    fb = allp["frameBand"]
    return {"faceY": float(fb["faceYUU"]), "bottomZ": float(fb["faceBottomZ"])}


def main(argv=None) -> int:
    allp = CS.params()
    P = allp["cascade"]
    rimd = np.load(CS.WORK / "island_rim.npz")
    sheet, foam, info = build(P, rimd, float(allp["seaZ"]), beam_of(allp))
    sheet.save(CS.WORK / f"{NAME}.pre.npz")
    foam.save(CS.WORK / f"{FOAM}.pre.npz")
    isl = CS.Mesh.load(CS.WORK / "SM_Env_S_Island.pre.npz")
    fbp = CS.WORK / "SM_Env_S_FrameBand.pre.npz"
    band = CS.Mesh.load(fbp) if fbp.is_file() else None
    cov = c0_coverage(sheet, isl, band, CS.WORK / "overlays" / "cascade-c0.jpg")
    chk = {"maxTris": P["maxTris"], "trianglesOk": sheet.tris + foam.tris <= P["maxTris"],
           "uvInside01": bool((sheet.UV >= -1e-9).all() and (sheet.UV <= 1 + 1e-9).all())}
    rep = {"schema": "unmatched.env-s-cascade.build/1",
           "status": "предложено (geometry, CREATE stage; measured at C0 on the de-lit plate)",
           "meshes": [NAME, FOAM], "pivotBoard": [round(float(v), 3) for v in sheet.pivot], "info": info, "checks": chk,
           "c0Coverage": cov, "overlay": (CS.WORK / "overlays" / "cascade-c0.jpg").as_posix(),
           "meshDigest": {NAME: sheet.digest(), FOAM: foam.digest()}}
    CS.dump_json(CS.RUNS["props"] / "reports" / "cascade-build.json", rep)
    print("CASCADE", sheet.tris, "+", foam.tris, "tris; card", info["fallCard"], "tiers", len(info["tiers"]),
          json.dumps(cov))
    return 0 if chk["trianglesOk"] and chk["uvInside01"] else 1


if __name__ == "__main__":
    sys.exit(main())
