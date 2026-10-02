"""ENV-MAPS P9 F2 frame band (ASSET-ENV-S-PROPS-001 / SM_Env_S_FrameBand): the heavy dark wooden frame of the painting
around frame-002, as real geometry.

  python -B tools/art/concept_scene/frame_band_build.py   # -> <work>/SM_Env_S_FrameBand.pre.npz + reports/frameband-build.json

The concept paints the board in a frame about 2-3.6x wider than frame-002 (sarpedon.paste.json cut.paintedFrameOuterUU:
far 51, east 63, west 61, near 87 uu from the map edge, measured where the wood ends on the ground plane Z -3). P8 left
that band as the island top baked with planks (a pale plinth). P9 builds it: bevelled plank beams on the island top
around frame-002 (inner edge = frame-002's outer edge + gapUU, top below frame-002's top), each side's outer top edge
on the C0 ray of the painted outer edge (so the band covers the painted frame at C0), the near side a tall beam whose
front face drops to faceBottomZ over the tucked cliff lip (island_build nearLip: no grazing lip strip in front of the
frame, F3), iron corner brackets (a square plate on the corner block + two arms) and mid-edge straps (over the top
and, on the near beam, down the front face) with rivets. Nothing lies over frame-002 or the map field, the top stays
below frame-002's top (FRAME_TOP_Z 12.4), so no cell is covered (layout_check rule 12 checks it on the proxies).

Not baked: two slots for track B's material-route MIs - MI_EnvScene_FrameWood (Planks023A tinted to the concept's
dark frame colour) and MI_EnvScene_FrameIron (the frame-002 iron textures: the same iron as the inner frame) - with
box-mapped tiling UV0 (1 UV = uvTileUU.wood / .iron; the grain runs along each beam's long axis). It stays an occluder
of the island bake (the island top under it is hidden at C0).
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

NAME = "SM_Env_S_FrameBand"
SLOTS = ["MI_EnvScene_FrameWood", "MI_EnvScene_FrameIron"]  # track B's material-route MIs (ue_scene_material.py)
C = CS.C


def outer_extents(P: dict) -> dict:
    """Outer top edges of the band per side (board uu): the C0 ray of the painted outer edge (ground plane Z -3) taken
    up to the band's top Z, so the band's outer top edge covers the painted frame's outer edge at C0. The near side
    has its own front face plane (faceYUU)."""
    spec = CS.spec()
    pw = spec["cut"]["paintedFrameOuterUU"]
    cam = CS.cam0()
    z_top, z_g = float(P["topZ"]), float(spec["geometry"]["groundZ"])

    def up(pt):  # ground point -> the point of the same C0 ray at z_top
        q, _ = cam.project(np.array([pt], float))
        return CS.ray_z(q[0, 0], q[0, 1], z_top)

    far = up((0.0, -(C.MAP_HY + pw["far"]), z_g))
    east = up((C.MAP_HX + pw["east"], 0.0, z_g))
    west = up((-(C.MAP_HX + pw["west"]), 0.0, z_g))
    return {"farY": float(far[1]), "eastX": float(east[0]), "westX": float(west[0]), "nearY": float(P["faceYUU"]),
            "paintedOuterUU": pw}


def segments(a: float, b: float, n: int, rng, jitter: float) -> list[tuple[float, float]]:
    """n butt-jointed segments of [a, b] with jittered joints."""
    cuts = [a] + [a + (b - a) * (i + rng.uniform(-jitter, jitter)) / n for i in range(1, n)] + [b]
    return list(zip(cuts[:-1], cuts[1:]))


def box(parts, lo, hi, bevel, tag, rng=None, jz=0.0):
    lo, hi = np.asarray(lo, float), np.asarray(hi, float)
    if rng is not None and jz:
        hi = hi.copy()
        hi[2] += rng.uniform(-jz, jz)
    V, F = G.chamfer_box((lo + hi) / 2, hi - lo, 0.0, bevel)
    parts.add(V, F, tag)
    return [((lo + hi) / 2).tolist(), (hi - lo).tolist()]


def box_uv(V: np.ndarray, F: np.ndarray, tile: float, rng) -> np.ndarray:
    """Box mapping per triangle (dominant normal axis), u along the part's long horizontal axis (the grain), a random
    offset per part (no repeated pattern between neighbouring planks). Blender UV convention (v up)."""
    P = V[F]
    n = np.cross(P[:, 1] - P[:, 0], P[:, 2] - P[:, 0])
    ax = np.argmax(np.abs(n), axis=1)
    ext = V.max(0) - V.min(0)
    long_x = ext[0] >= ext[1]
    off = rng.uniform(0.0, 1.0, size=2)
    UV = np.zeros((len(F), 3, 2))
    for i in range(len(F)):
        q = P[i]
        if ax[i] == 2:      # top / bottom: (along, across)
            uv = np.c_[q[:, 0], q[:, 1]] if long_x else np.c_[q[:, 1], q[:, 0]]
        elif ax[i] == 1:    # faces looking along Y: (x, z)
            uv = np.c_[q[:, 0], q[:, 2]]
        else:               # faces looking along X: (y, z)
            uv = np.c_[q[:, 1], q[:, 2]]
        UV[i] = uv / tile + off
    return UV


def build(P: dict):
    rng = np.random.default_rng(P["seed"])
    ext = outer_extents(P)
    g = float(P["gapUU"])
    hx_in, hy_in = C.FRAME_HX + g, C.FRAME_HY + g
    z_top, z_bot = float(P["topZ"]), float(P["sinkZ"])
    gap, bev, jz = float(P["plankGapUU"]), float(P["bevelUU"]), float(P["plankJitterZUU"])
    W, E, Fy, Ny = ext["westX"], ext["eastX"], ext["farY"], ext["nearY"]
    ft = float(P["frontBoardUU"])
    parts = G.Parts()
    iron = []

    def planks_x(x0, x1, y0, y1, n_across, n_len, zb=z_bot):
        """Planks running along X between y0 and y1 (n_across planks, n_len butt-jointed segments each)."""
        ys = np.linspace(y0, y1, n_across + 1)
        for i in range(n_across):
            for a, b in segments(x0, x1, n_len, rng, 0.18):
                box(parts, (a + gap / 2, ys[i] + gap / 2, zb), (b - gap / 2, ys[i + 1] - gap / 2, z_top), bev, "wood",
                    rng, jz)

    def planks_y(x0, x1, y0, y1, n_across, n_len):
        xs = np.linspace(x0, x1, n_across + 1)
        for i in range(n_across):
            for a, b in segments(y0, y1, n_len, rng, 0.18):
                box(parts, (xs[i] + gap / 2, a + gap / 2, z_bot), (xs[i + 1] - gap / 2, b - gap / 2, z_top), bev, "wood",
                    rng, jz)

    n_len = int(P["segmentsLong"])
    planks_x(W, E, Fy, -hy_in, int(P["planksAcross"]["far"]), n_len)               # far beam (full length)
    planks_x(W, E, hy_in, Ny - ft, int(P["planksAcross"]["near"]), n_len)          # near beam top planks
    planks_y(W, -hx_in, -hy_in, hy_in, int(P["planksAcross"]["west"]), int(P["segmentsShort"]))
    planks_y(hx_in, E, -hy_in, hy_in, int(P["planksAcross"]["east"]), int(P["segmentsShort"]))
    # the near beam's front boards (the tall face of the painted frame over the tucked lip)
    zf = np.linspace(float(P["faceBottomZ"]), z_top, int(P["frontBoards"]) + 1)
    for k in range(len(zf) - 1):
        for a, b in segments(W, E, n_len, rng, 0.18):
            box(parts, (a + gap / 2, Ny - ft, zf[k] + gap / 2), (b - gap / 2, Ny, zf[k + 1] - gap / 2 if k < len(zf) - 2
                                                                     else z_top), bev, "wood", rng, jz if k == len(zf) - 2 else 0.0)
    # ---- iron: corner brackets (square plate on the corner block + two arms), mid straps, rivets
    T = float(P["ironThickUU"])
    zi0, zi1 = z_top + float(P["plankJitterZUU"]), z_top + float(P["plankJitterZUU"]) + T
    rv = float(P["rivetUU"])
    rvh = float(P["rivetHUU"])
    ib = float(P["ironBevelUU"])
    arm, armw = float(P["cornerArmUU"]), float(P["cornerArmWidthFrac"])

    def rivet(x, y, z, normal="z"):
        if normal == "z":
            lo, hi = (x - rv / 2, y - rv / 2, z), (x + rv / 2, y + rv / 2, z + rvh)
        else:  # on the near front face (+Y)
            lo, hi = (x - rv / 2, y, z - rv / 2), (x + rv / 2, y + rvh, z + rv / 2)
        iron.append(box(parts, lo, hi, min(ib, rv * 0.3), "iron"))

    for sx in (-1, 1):
        for sy in (-1, 1):
            xo = E if sx > 0 else W
            yo = Ny if sy > 0 else Fy
            xi, yi = sx * hx_in, sy * hy_in
            m = float(P["ironMarginUU"])
            # the square on the corner block
            x0, x1 = sorted((xi + sx * m, xo - sx * m))
            y0, y1 = sorted((yi + sy * m, yo - sy * m))
            iron.append(box(parts, (x0, y0, zi0), (x1, y1, zi1), ib, "iron"))
            for fx in (0.25, 0.75):
                for fy in (0.25, 0.75):
                    rivet(x0 + (x1 - x0) * fx, y0 + (y1 - y0) * fy, zi1)
            # the arm along X (on the far / near beam) and along Y (on the west / east beam), at the outer side
            bw_y = abs(yo - yi)
            ay0, ay1 = sorted((yo - sy * m, yo - sy * (m + armw * bw_y)))
            ax0, ax1 = sorted((xi, xi - sx * arm))
            iron.append(box(parts, (ax0, ay0, zi0), (ax1, ay1, zi1), ib, "iron"))
            rivet((ax0 + ax1) / 2 - sx * arm * 0.25, (ay0 + ay1) / 2, zi1)
            bw_x = abs(xo - xi)
            bx0, bx1 = sorted((xo - sx * m, xo - sx * (m + armw * bw_x)))
            by0, by1 = sorted((yi, yi - sy * arm))
            iron.append(box(parts, (bx0, by0, zi0), (bx1, by1, zi1), ib, "iron"))
            rivet((bx0 + bx1) / 2, (by0 + by1) / 2 - sy * arm * 0.25, zi1)
            if sy > 0:  # near corners: the bracket bends down the front face
                fw = float(P["frontPlateWidthUU"])
                fx0, fx1 = sorted((xo - sx * m, xo - sx * (m + fw)))
                iron.append(box(parts, (fx0, Ny, float(P["faceBottomZ"]) + 4.0), (fx1, Ny + T, zi1), ib, "iron"))
                for zz in (z_top - 6.0, float(P["faceBottomZ"]) + 10.0):
                    rivet((fx0 + fx1) / 2, Ny + T, zz, "y")
    sw = float(P["strapWidthUU"])
    for side in ("far", "near", "west", "east"):
        if side in ("far", "near"):
            y0, y1 = (Fy + 1.5, -hy_in - 1.0) if side == "far" else (hy_in + 1.0, Ny)
            iron.append(box(parts, (-sw / 2, y0, zi0), (sw / 2, y1, zi1), ib, "iron"))
            for yy in (y0 + (y1 - y0) * 0.25, y0 + (y1 - y0) * 0.75):
                rivet(0.0, yy, zi1)
            if side == "near":
                iron.append(box(parts, (-sw / 2, Ny, float(P["faceBottomZ"]) + 4.0), (sw / 2, Ny + T, zi1), ib, "iron"))
                for zz in (z_top - 6.0, float(P["faceBottomZ"]) + 10.0):
                    rivet(0.0, Ny + T, zz, "y")
        else:
            x0, x1 = (W + 1.5, -hx_in - 1.0) if side == "west" else (hx_in + 1.0, E - 1.5)
            iron.append(box(parts, (x0, -sw / 2, zi0), (x1, sw / 2, zi1), ib, "iron"))
            for xx in (x0 + (x1 - x0) * 0.25, x0 + (x1 - x0) * 0.75):
                rivet(xx, 0.0, zi1)
    pivot = np.array(P["pivot"], float)
    # assemble: per part its slot (0 wood, 1 iron) and box-mapped tiling UV0
    Vs, Fs, UVs, MAT = [], [], [], []
    base = 0
    tags = np.array(parts.tags)
    t0 = 0
    for V, F in zip(parts.V, parts.F):
        Fl = F - base
        tag = tags[t0]
        t0 += len(F)
        tile = float(P["uvTileUU"]["iron" if tag == "iron" else "wood"])
        Vs.append(V)
        Fs.append(F)
        UVs.append(box_uv(V, Fl, tile, rng))
        MAT.append(np.full(len(F), 1 if tag == "iron" else 0))
        base += len(V)
    Vall = np.vstack(Vs)
    mesh = CS.Mesh(NAME, Vall - pivot, np.vstack(Fs), np.vstack(UVs), np.concatenate(MAT), np.ones(t0, bool), SLOTS, pivot)
    B = mesh.board()
    info = {"extents": {k: round(v, 2) if isinstance(v, float) else v for k, v in ext.items()},
            "innerHalf": [round(hx_in, 3), round(hy_in, 3)],
            "widthUU": {"far": round(-hy_in - Fy, 1), "near": round(Ny - hy_in, 1), "west": round(-hx_in - W, 1),
                        "east": round(E - hx_in, 1)},
            "topZ": z_top, "maxZ": round(float(B[:, 2].max()), 3), "minZ": round(float(B[:, 2].min()), 3),
            "ironBoxes": [[[round(v, 3) for v in c], [round(v, 3) for v in s]] for c, s in iron],
            "ironParts": len(iron), "triangles": mesh.tris, "slots": SLOTS,
            "trianglesPerSlot": [int((mesh.MAT == k).sum()) for k in range(len(SLOTS))]}
    return mesh, info


def checks(mesh: CS.Mesh, P: dict) -> dict:
    B = mesh.board()
    over = (np.abs(B[:, 0]) < C.FRAME_HX) & (np.abs(B[:, 1]) < C.FRAME_HY)
    return {"verticesOverFrame002OrMap": int(over.sum()), "maxZ": round(float(B[:, 2].max()), 3),
            "belowFrameTop": bool(B[:, 2].max() <= C.FRAME_TOP_Z + 1e-6), "maxTris": P["maxTris"],
            "trianglesOk": mesh.tris <= P["maxTris"]}


def c0_coverage(mesh: CS.Mesh, out_png: Path | None = None, scale: float = 1.0) -> dict:
    """C0 self-check: the painted frame band = the ground-plane ring between frame-002's outer top edge silhouette
    and the painted outer edge (paintedFrameOuterUU at Z -3), rasterised at C0; share covered by the band mesh and the
    band pixels outside it (spill), over the C0 frame."""
    from PIL import Image, ImageDraw
    spec = CS.spec()
    pw = spec["cut"]["paintedFrameOuterUU"]
    cam = CS.cam0()
    rect = (0.0, 0.0, 1920.0, 1080.0)
    w, h = int(1920 * scale), int(1080 * scale)
    zg = float(spec["geometry"]["groundZ"])
    outer = np.array([[-(C.MAP_HX + pw["west"]), -(C.MAP_HY + pw["far"]), zg], [C.MAP_HX + pw["east"], -(C.MAP_HY + pw["far"]), zg],
                      [C.MAP_HX + pw["east"], C.MAP_HY + pw["near"], zg], [-(C.MAP_HX + pw["west"]), C.MAP_HY + pw["near"], zg]])
    inner = np.array([[-C.FRAME_HX, -C.FRAME_HY, C.FRAME_TOP_Z], [C.FRAME_HX, -C.FRAME_HY, C.FRAME_TOP_Z],
                      [C.FRAME_HX, C.FRAME_HY, C.FRAME_TOP_Z], [-C.FRAME_HX, C.FRAME_HY, C.FRAME_TOP_Z]])
    po = cam.project(outer)[0]
    pi = cam.project(inner)[0]
    painted = CS.poly_mask(po.tolist(), w, h, rect) & ~CS.poly_mask(pi.tolist(), w, h, rect)
    d, _ = CS.raster_tris(cam, mesh.board(), mesh.F, w, h, rect=rect, cull_back=True)
    band = np.isfinite(d)
    res = {"paintedBandPx": int(painted.sum()), "covered": round(float((band & painted).sum() / max(painted.sum(), 1)), 4),
           "spillShareOfPainted": round(float((band & ~painted).sum() / max(painted.sum(), 1)), 4)}
    if out_png:
        img = CS.plate_c0(rect, w, h, CS.DELIT_EXT)
        o = img.copy()
        o[band] = o[band] * 0.45 + np.array([1.0, 0.55, 0.1]) * 0.55
        im = Image.fromarray(np.clip(o * 255, 0, 255).astype(np.uint8))
        dr = ImageDraw.Draw(im)
        for poly, col in ((po, (255, 0, 255)), (pi, (0, 255, 255))):
            pts = [(x * scale, y * scale) for x, y in poly]
            dr.line(pts + pts[:1], fill=col, width=2)
        Path(out_png).parent.mkdir(parents=True, exist_ok=True)
        im.save(out_png, quality=88)
    return res


def main(argv=None) -> int:
    allp = CS.params()
    P = allp["frameBand"]
    mesh, info = build(P)
    mesh.save(CS.WORK / f"{NAME}.pre.npz")
    chk = checks(mesh, P)
    cov = c0_coverage(mesh, CS.WORK / "overlays" / "frameband-c0.jpg")
    rep = {"schema": "unmatched.env-s-frameband.build/1",
           "status": "предложено (geometry, CREATE stage; measured at C0 on the de-lit plate)",
           "mesh": NAME, "pivotBoard": [round(float(v), 3) for v in mesh.pivot], "info": info, "checks": chk,
           "c0Coverage": cov, "overlay": (CS.WORK / "overlays" / "frameband-c0.jpg").as_posix(),
           "meshDigest": mesh.digest()}
    CS.dump_json(CS.RUNS["props"] / "reports" / "frameband-build.json", rep)
    print("FRAMEBAND", mesh.tris, "tris", json.dumps(info["widthUU"]), json.dumps(chk), json.dumps(cov))
    bad = chk["verticesOverFrame002OrMap"] or not chk["belowFrameTop"] or not chk["trianglesOk"]
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
