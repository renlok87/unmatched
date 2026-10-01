"""ENV-MAPS P7: mock re-renders of the concept paste from the game cameras + metrics (offline prototype).

  python proto_views.py <map> [--proxies relief,terrain,plane] [--out DIR]

Views: concept pose C0 (2714.6 uu), K1 (2340.2), K1x0.65 = far wheel limit (2880.2), K2x1.6 centred (1462.6) and,
on Sarpedon, K2x1.6 on Medusa's start (focus (-218, -13, 28), the P5c bench framing).
Metrics per view and proxy (metrics.json):
  * grade: map / surround luma with the ROIs of the P2-P5c measure.py (map inset 8 uu; surround = tray top
    (-780..780, -515..425) at Z -1 minus the frame), surround / map, warm fraction;
  * coverage: share of the frame whose painted source lies outside the outpainted canvas;
  * anchors: screen distance between each 3D detail (placed on its host flat = the relief proxy) and its painted host
    as the proxy shows it (relief = 0 by construction; +-25 uu flat depth error reported as sensitivity);
  * landmarks: the same for tall painted masses (fort top, post tops, ship rail / rigging, canopy, cliff foot):
    how far a proxy that ignores their height shears them;
  * stretch: per sheet cell, singular values of the C0 -> view Jacobian (relative to C0): share of the visible
    painted area with anisotropy > 2 or area scale > 2.5x the view median (rubber-sheet smear);
  * texel density: screen px per C0 px (median / p95 of sqrt(det J)) -> upscale target.
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont

import cp_common as C
import k1_mock
import paste_proto as pp

sys.path.insert(0, "C:/tmp/envmaps-research/p5c/tune")
import measure as MS  # noqa: E402  (scratch measure.py of P2-P5c: stats / lab / ROI helpers)

TARGET_MAP_Y = {"sarpedon": 106.6, "marmoreal": 117.6}  # P5c measured K1 map luma (game)
LANDMARKS = {  # C0 px of tall painted masses and their reference host (the relief proxy)
    "sarpedon": {"fort-top": (480, 10), "fort-arch": (530, 120), "post-bay-top": (812, 0),
                 "post-left-top": (290, 330), "ship-rail": (1700, 200), "ship-rigging": (1800, 40),
                 "ship-hull-low": (2000, 800), "canopy-edge": (250, 300), "canopy-far": (100, 150),
                 "cliff-foot": (700, 1150), "palisade-top": (330, 300)},
}


def roi_masks(cam: C.Cam):
    hx, hy = MS.MAP_HALF
    size = (cam.w, cam.h)

    def rect(x0, y0, x1, y1, z):
        return [tuple(p) for p in cam.project(np.array([[x0, y0, z], [x1, y0, z], [x1, y1, z], [x0, y1, z]],
                                                       float))[0]]
    m_map = MS.poly_mask(size, rect(-hx + 8, -hy + 8, hx - 8, hy - 8, 0.0))
    m_frame = MS.poly_mask(size, rect(-MS.FRAME_HALF[0], -MS.FRAME_HALF[1], MS.FRAME_HALF[0], MS.FRAME_HALF[1], 0.5))
    m_tray = MS.poly_mask(size, rect(*MS.TRAY_TOP, -1.0))
    return m_map, m_tray & ~m_frame, ~m_tray


def grade_stats(img8: np.ndarray, cam: C.Cam) -> dict:
    m_map, m_sur, m_out = roi_masks(cam)
    res = {"map": MS.stats(img8, m_map), "surround": MS.stats(img8, m_sur), "outsideTray": MS.stats(img8, m_out)}
    res["surround/map"] = round(res["surround"]["lumaMean"] / res["map"]["lumaMean"], 3)
    return res


def jac_stats(cam: C.Cam, P: np.ndarray, grid, has_sheet: np.ndarray, sheet_attr: np.ndarray) -> dict:
    """C0 -> view Jacobian per sheet cell; visible cells = cells whose centre maps to a sheet pixel that shows this
    cell (the rasterised C0 px of the pixel lies inside the cell)."""
    gx, gy = grid
    step = gx[1] - gx[0]
    q, z = cam.project(P.reshape(-1, 3))
    q = q.reshape(P.shape[0], P.shape[1], 2)
    dx = (q[:-1, 1:] - q[:-1, :-1] + q[1:, 1:] - q[1:, :-1]) / (2 * step)
    dy = (q[1:, :-1] - q[:-1, :-1] + q[1:, 1:] - q[:-1, 1:]) / (2 * step)
    J = np.stack([dx, dy], -1)  # (..., 2 view, 2 c0)
    s = np.linalg.svd(J, compute_uv=False)
    aniso = s[..., 0] / np.maximum(s[..., 1], 1e-9)
    scale = np.sqrt(np.abs(s[..., 0] * s[..., 1]))
    # visibility: which cell does each sheet pixel show
    cx = np.floor((sheet_attr[..., 2] - gx[0]) / step).astype(np.int64)
    cy = np.floor((sheet_attr[..., 3] - gy[0]) / step).astype(np.int64)
    ok = has_sheet & (cx >= 0) & (cy >= 0) & (cx < aniso.shape[1]) & (cy < aniso.shape[0])
    a = aniso[cy[ok], cx[ok]]
    sc = scale[cy[ok], cx[ok]]
    if not len(a):
        return {}
    med = float(np.median(sc))
    return {"visibleSheetPx": int(ok.sum()), "texelScaleMedian": round(med, 3),
            "texelScaleP95": round(float(np.percentile(sc, 95)), 3),
            "anisoP50": round(float(np.median(a)), 3), "anisoP99": round(float(np.percentile(a, 99)), 3),
            "smearShare_aniso>2": round(float((a > 2).mean()), 4),
            "smearShare_scale>2.5xMedian": round(float((sc > 2.5 * med).mean()), 4)}


def anchor_errors(cam: C.Cam, spec: dict, ctx: dict, proxy: str) -> dict:
    """Detail (relief host) vs its painted host shown through `proxy`, and the +-25 uu flat-depth sensitivity."""
    c0 = ctx["c0"]
    out = {}
    g = spec["geometry"]
    zones = {z["id"]: z for z in g["planeZones"]}
    for d in ctx["details"]:
        T = np.array(d["world"])
        fx, fy = np.array(float(d["px"][0])), np.array(float(d["px"][1]))
        Pp = pp.sheet_points(spec, c0, np.array([fx - 0.5, fx + 0.5]), np.array([fy - 0.5, fy + 0.5]), proxy)
        Pp = Pp.mean(axis=(0, 1))
        a = cam.project(T)[0]
        b = cam.project(Pp)[0]
        rec = {"err": round(float(np.linalg.norm(a - b)), 2), "screen": [round(float(v), 1) for v in a],
               "onScreen": bool(0 <= a[0] < cam.w and 0 <= a[1] < cam.h)}
        if proxy == "relief" and d["on"] in zones:
            P0, n = pp.zone_plane(c0, zones[d["on"]], g["groundZ"])
            errs = []
            for dlt in (-25.0, 25.0):
                Q = pp.ray_plane(c0, fx, fy, P0 + n * dlt, n)[0]
                errs.append(float(np.linalg.norm(cam.project(Q)[0] - a)))
            rec["errFlat25uu"] = round(max(errs), 2)
        out[d["id"]] = rec
    return out


def landmark_errors(cam: C.Cam, spec: dict, ctx: dict, proxy: str, map_key: str) -> dict:
    c0 = ctx["c0"]
    out = {}
    for name, (x, y) in LANDMARKS.get(map_key, {}).items():
        xs, ys = np.array([x - 0.5, x + 0.5], float), np.array([y - 0.5, y + 0.5], float)
        T = pp.sheet_points(spec, c0, xs, ys, "relief").mean(axis=(0, 1))
        Pp = pp.sheet_points(spec, c0, xs, ys, proxy).mean(axis=(0, 1))
        a = cam.project(T)[0]
        out[name] = {"err": round(float(np.linalg.norm(a - cam.project(Pp)[0])), 2),
                     "onScreen": bool(0 <= a[0] < cam.w and 0 <= a[1] < cam.h),
                     "hostWorld": [round(float(v), 1) for v in T]}
    return out


def label(img: Image.Image, text: str) -> Image.Image:
    d = ImageDraw.Draw(img)
    try:
        f = ImageFont.truetype("arial.ttf", 22)
    except OSError:
        f = ImageFont.load_default()
    d.rectangle([0, 0, 12 + 12 * len(text), 32], fill=(0, 0, 0))
    d.text((6, 4), text, fill=(255, 255, 255), font=f)
    return img


def montage(tiles: list[tuple[str, Path]], cols: int, out: Path, tile_w: int = 960):
    ims = []
    for name, p in tiles:
        im = Image.open(p).convert("RGB")
        im = im.resize((tile_w, round(im.size[1] * tile_w / im.size[0])), Image.LANCZOS)
        ims.append(label(im, name))
    th = max(i.size[1] for i in ims)
    rows = (len(ims) + cols - 1) // cols
    M = Image.new("RGB", (cols * tile_w, rows * th), (20, 20, 20))
    for i, im in enumerate(ims):
        M.paste(im, ((i % cols) * tile_w, (i // cols) * th))
    M.save(out, quality=88)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("map", choices=sorted(C.MAPS))
    ap.add_argument("--proxies", default="relief,terrain,plane")
    ap.add_argument("--out", type=Path, default=pp.OUT)
    ap.add_argument("--views", default="")
    a = ap.parse_args()
    t0 = time.time()
    proxies = a.proxies.split(",")
    od = a.out / a.map
    ctx = pp.concept_c0_ctx(a.map, a.out, proxies)
    spec = ctx["spec"]
    views = C.game_views(a.map)
    if a.views:
        views = {k: v for k, v in views.items() if k in a.views.split(",")}
    # 1) calibrate the real map gain so the mock K1 map luma = the measured game K1 luma
    k1 = C.Cam(C.D_K1)
    col, _ = ctx["real"].render(k1)
    m_map, _, _ = roi_masks(k1)
    for _ in range(4):
        y = MS.luma8(np.round(k1_mock.lin_to_srgb(col * ctx["real"].gain) * 255))[m_map].mean()
        ctx["real"].gain *= (TARGET_MAP_Y[a.map] / y) ** 2.2
    # 2) painted gain: the concept's own map luma -> the game map luma (keeps the concept's surround / map ratio)
    concept = C.load_rgb(C.CONCEPTS / C.MAPS[a.map]["concept"], (C.W, C.H))
    c0 = ctx["c0"]
    cst = grade_stats(np.round(concept * 255), c0)
    paint_gain_disp = TARGET_MAP_Y[a.map] / cst["map"]["lumaMean"]
    ctx["paintGain"] = float(paint_gain_disp ** 2.2)
    res = {"schema": "unmatched.concept-paste.proto-metrics/1", "map": a.map,
           "calibration": {"realMapGainLinear": round(float(ctx["real"].gain), 4),
                           "targetMapY_K1": TARGET_MAP_Y[a.map],
                           "conceptStatsAtC0": cst,
                           "paintGainDisplay": round(paint_gain_disp, 4), "paintGainLinear": round(ctx["paintGain"], 4)},
           "details": ctx["details"], "views": {}}
    frames = {}
    for vn, cam in views.items():
        res["views"][vn] = {"camera": cam.to_json()}
        for proxy in proxies:
            img, layers, sattr, has = pp.render_view(a.map, cam, spec, ctx, proxy)
            p = od / f"mock-{proxy}-{vn}.png"
            C.save_rgb(p, img)
            frames[(proxy, vn)] = p
            img8 = np.round(img * 255)
            r = {"layers": {k: round(float(v.mean()), 4) for k, v in layers.items()},
                 "grade": grade_stats(img8, cam),
                 "stretch": jac_stats(cam, ctx["sheets"][proxy], ctx["grid"], has & layers["sheet"], sattr),
                 "anchors": anchor_errors(cam, spec, ctx, proxy),
                 "landmarks": landmark_errors(cam, spec, ctx, proxy, a.map)}
            res["views"][vn][proxy] = r
            print(vn, proxy, "mapY", r["grade"]["map"]["lumaMean"], "sur/map", r["grade"]["surround/map"],
                  "outsideExt", r["layers"]["outsideExtended"], "smear", r["stretch"].get("smearShare_aniso>2"),
                  round(time.time() - t0), "s", flush=True)
    C.dump_json(od / "metrics.json", res)
    # montages
    rel = "relief" if "relief" in proxies else proxies[0]
    cpath = od / "concept-1920.png"
    C.save_rgb(cpath, concept)
    tiles = [(f"concept {C.MAPS[a.map]['concept']} (C0 2714.6 uu)", cpath)] + [(f"mock {rel} {vn}", frames[(rel, vn)])
                                                                for vn in views]
    montage(tiles, 2, od / f"montage-concept-vs-mock-{rel}.jpg")
    if len(proxies) > 1:
        for vn in [v for v in ("K2x1.6hero", "K2x1.6c", "K1") if v in views]:
            montage([(f"{p} {vn}", frames[(p, vn)]) for p in proxies], len(proxies),
                    od / f"montage-proxies-{vn}.jpg", 960)
    print("done", round(time.time() - t0), "s")


if __name__ == "__main__":
    main()
