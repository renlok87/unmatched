"""Register an imagegen concept (Lanczos-resized to the 1920x1080 base frame) to its k1_mock base render.

The base is an exact pinhole render of the original map at the concept camera C0 (render_concept_base.py), so the
map field of a registered concept must land on the projected map. Control points:
  * every space circle (tools/art/map_surface/<map>.vector-layer.json painted_px) projected through C0, located in
    the concept by normalised cross-correlation of gradient-magnitude patches (subpixel parabola peak);
  * a dense grid of map-interior patches (same matcher), so the map illustration itself also constrains the fit.
A robust (Huber IRLS) homography base -> concept is fitted; a thin-plate residual field (scipy RBFInterpolator,
smoothing) is fitted on top and faded out away from the map so that the surround is moved by the homography only.

Usage: python register.py <map> [--out DIR]
Writes DIR/<map>/registration.json (+ the registered concept and a check overlay, both OUT of git).
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
from scipy import ndimage
from scipy.interpolate import RBFInterpolator

import cp_common as C

OUT = Path("C:/tmp/envmaps-research/p7/proto")


def grad_mag(img: np.ndarray, sigma: float = 1.2) -> np.ndarray:
    g = ndimage.gaussian_filter(C.luma(img).astype(np.float64), sigma)
    return np.hypot(ndimage.sobel(g, 1), ndimage.sobel(g, 0))


def ncc_search(a: np.ndarray, b: np.ndarray, cx: float, cy: float, r: int, s: int):
    """Best offset (dx, dy) of the template a[cy-r:cy+r+1, cx-r:cx+r+1] inside b within +-s px, subpixel.
    Returns (dx, dy, peak_ncc, second_peak_ratio) or None near the image border."""
    ix, iy = int(round(cx)), int(round(cy))
    h, w = a.shape
    if ix - r - s < 0 or iy - r - s < 0 or ix + r + s + 1 > w or iy + r + s + 1 > h:
        return None
    t = a[iy - r:iy + r + 1, ix - r:ix + r + 1]
    t = t - t.mean()
    tn = np.sqrt((t * t).sum())
    if tn < 1e-9:
        return None
    win = b[iy - r - s:iy + r + s + 1, ix - r - s:ix + r + s + 1]
    k = 2 * r + 1
    # sliding sums via cumulative sums
    c1 = np.pad(win, ((1, 0), (1, 0))).cumsum(0).cumsum(1)
    c2 = np.pad(win * win, ((1, 0), (1, 0))).cumsum(0).cumsum(1)
    S1 = c1[k:, k:] - c1[:-k, k:] - c1[k:, :-k] + c1[:-k, :-k]
    S2 = c2[k:, k:] - c2[:-k, k:] - c2[k:, :-k] + c2[:-k, :-k]
    from scipy.signal import fftconvolve
    num = fftconvolve(win, t[::-1, ::-1], mode="valid")
    den = np.sqrt(np.maximum(S2 - S1 * S1 / (k * k), 1e-12)) * tn
    ncc = num / den
    j, i = np.unravel_index(np.argmax(ncc), ncc.shape)
    peak = float(ncc[j, i])

    def sub(m1, m0, p1):
        d = m1 - 2 * m0 + p1
        return 0.0 if abs(d) < 1e-12 else 0.5 * (m1 - p1) / d
    dx = i - s + (sub(ncc[j, i - 1], peak, ncc[j, i + 1]) if 0 < i < ncc.shape[1] - 1 else 0.0)
    dy = j - s + (sub(ncc[j - 1, i], peak, ncc[j + 1, i]) if 0 < j < ncc.shape[0] - 1 else 0.0)
    nb = ncc.copy()
    nb[max(0, j - 4):j + 5, max(0, i - 4):i + 5] = -1
    return float(dx), float(dy), peak, float(nb.max() / peak) if peak > 0 else 1.0


def _norm(p):
    m = p.mean(0)
    s = np.sqrt(2) / np.sqrt(((p - m) ** 2).sum(1)).mean()
    T = np.array([[s, 0, -s * m[0]], [0, s, -s * m[1]], [0, 0, 1]])
    return T


def fit_h(src, dst, w=None):
    """Weighted normalised DLT homography src -> dst."""
    w = np.ones(len(src)) if w is None else w
    Ts, Td = _norm(src), _norm(dst)
    s = (np.c_[src, np.ones(len(src))] @ Ts.T)[:, :2]
    d = (np.c_[dst, np.ones(len(dst))] @ Td.T)[:, :2]
    rows = []
    for (x, y), (u, v), wi in zip(s, d, np.sqrt(w)):
        rows.append(wi * np.array([-x, -y, -1, 0, 0, 0, u * x, u * y, u]))
        rows.append(wi * np.array([0, 0, 0, -x, -y, -1, v * x, v * y, v]))
    _, _, vt = np.linalg.svd(np.asarray(rows))
    Hn = vt[-1].reshape(3, 3)
    Hm = np.linalg.inv(Td) @ Hn @ Ts
    return Hm / Hm[2, 2]


def apply_h(Hm, p):
    q = np.c_[p, np.ones(len(p))] @ Hm.T
    return q[:, :2] / q[:, 2:3]


def robust_h(src, dst, iters=20, k=1.5):
    w = np.ones(len(src))
    for _ in range(iters):
        Hm = fit_h(src, dst, w)
        r = np.linalg.norm(apply_h(Hm, src) - dst, axis=1)
        w = np.where(r <= k, 1.0, k / np.maximum(r, 1e-9))
    return Hm, r, w


def map_quad(cam: C.Cam, hx=C.MAP_HX, hy=C.MAP_HY, z=0.0):
    P = np.array([[-hx, -hy, z], [hx, -hy, z], [hx, hy, z], [-hx, hy, z]])
    return cam.project(P)[0]


def load_plate(path: Path, crop=None) -> np.ndarray:
    """A concept-framed image as the 1920x1080 C0 frame: optional crop box (x0, y0, x1, y1) of the concept
    framing inside a larger canvas (outpainted plates), then PIL Lanczos to 1920x1080."""
    from PIL import Image
    im = Image.open(path).convert("RGB")
    if crop:
        im = im.crop(tuple(int(v) for v in crop))
    if im.size != (C.W, C.H):
        im = im.resize((C.W, C.H), Image.LANCZOS)
    return np.asarray(im).astype(np.float32) / 255.0


def register(map_key: str, out: Path, image: Path | None = None, crop=None, tag: str = "") -> dict:
    m = C.MAPS[map_key]
    cam = C.concept_cam()
    base = C.load_rgb(C.CONCEPTS / m["base"])
    img_path = Path(image) if image else C.CONCEPTS / m["concept"]
    concept = load_plate(img_path, crop)
    ga, gb = grad_mag(base), grad_mag(concept)
    vec = json.loads((C.REPO / f"tools/art/map_surface/{map_key}.vector-layer.json").read_text(encoding="utf-8"))
    pts = []
    # 1) circles
    for s in vec["spaces"]:
        Xw = C.src_to_world(np.array(s["painted_px"]))
        p = cam.project(np.array([Xw[0], Xw[1], 0.0]))[0]
        res = ncc_search(ga, gb, p[0], p[1], r=50, s=28)
        if res:
            pts.append({"kind": "circle", "id": s["id"], "base": [float(p[0]), float(p[1])],
                        "dx": res[0], "dy": res[1], "ncc": res[2], "ambig": res[3]})
    # 2) dense map-interior grid (in source px, projected)
    for sy in np.linspace(60, C.SRC_H - 60, 9):
        for sx in np.linspace(60, C.SRC_W - 60, 14):
            Xw = C.src_to_world(np.array([sx, sy]))
            p = cam.project(np.array([Xw[0], Xw[1], 0.0]))[0]
            res = ncc_search(ga, gb, p[0], p[1], r=36, s=28)
            if res:
                pts.append({"kind": "grid", "id": f"g{int(sx)}_{int(sy)}", "base": [float(p[0]), float(p[1])],
                            "dx": res[0], "dy": res[1], "ncc": res[2], "ambig": res[3]})
    good = [p for p in pts if p["ncc"] >= 0.45 and p["ambig"] <= 0.92]
    src = np.array([p["base"] for p in good])
    dst = src + np.array([[p["dx"], p["dy"]] for p in good])
    Hm, r, w = robust_h(src, dst)
    inl = r <= 3.0
    Hm, r, w = robust_h(src[inl], dst[inl])
    r_all = np.linalg.norm(apply_h(Hm, src) - dst, axis=1)
    # thin-plate residual on the inliers, leave-one-out error
    res_vec = dst[inl] - apply_h(Hm, src[inl])
    tps = RBFInterpolator(src[inl], res_vec, kernel="thin_plate_spline", smoothing=2.0)
    loo = []
    idx = np.arange(inl.sum())
    for i in range(len(idx)):
        msk = idx != i
        t_i = RBFInterpolator(src[inl][msk], res_vec[msk], kernel="thin_plate_spline", smoothing=2.0)
        pred = apply_h(Hm, src[inl][i:i + 1]) + t_i(src[inl][i:i + 1])
        loo.append(float(np.linalg.norm(pred - dst[inl][i:i + 1])))
    loo_h = []
    for i in range(len(idx)):
        msk = idx != i
        H_i, _, _ = robust_h(src[inl][msk], dst[inl][msk])
        loo_h.append(float(np.linalg.norm(apply_h(H_i, src[inl][i:i + 1]) - dst[inl][i:i + 1])))
    # identity (no registration) error for reference
    r_id = np.linalg.norm(dst - src, axis=1)
    quad = map_quad(cam)
    fquad = map_quad(cam, C.FRAME_HX, C.FRAME_HY, C.FRAME_TOP_Z)
    quad_c = apply_h(Hm, quad)
    circ = np.array([p["kind"] == "circle" for p in good])

    def st(a):
        a = np.asarray(a)
        return {"n": int(len(a)), "rms": round(float(np.sqrt((a ** 2).mean())), 3), "p50": round(float(np.median(a)), 3),
                "p95": round(float(np.percentile(a, 95)), 3), "max": round(float(a.max()), 3)}
    rep = {
        "schema": "unmatched.concept-paste.registration/1", "map": map_key,
        "concept": {"file": str(img_path.name), "sha256": C.sha256(img_path), "crop": crop,
                    "resize": "PIL Lanczos (crop of the concept framing) -> 1920x1080"},
        "base": {"file": m["base"], "sha256": C.sha256(C.CONCEPTS / m["base"]), "camera": cam.to_json()},
        "matcher": "NCC of gradient magnitude (gauss 1.2), circles r50 / grid r36 px, search +-28 px; kept ncc>=0.45, "
                   "second-peak ratio <= 0.92",
        "points": {"found": len(pts), "kept": len(good), "inliers_3px": int(inl.sum()),
                   "circles_kept": int(circ.sum())},
        "identity_error_px": st(r_id),
        "identity_error_circles_px": st(r_id[circ]),
        "homography_base_to_concept": [[round(float(v), 9) for v in row] for row in Hm],
        "homography_residual_px": st(r_all[inl]),
        "homography_residual_circles_px": st(r_all[circ & inl]),
        "homography_loo_px": st(loo_h),
        "tps_loo_px": st(loo),
        "tps_smoothing": 2.0,
        "map_quad_base_px": quad.round(2).tolist(),
        "map_quad_in_concept_px": quad_c.round(2).tolist(),
        "map_corner_shift_px": np.linalg.norm(quad_c - quad, axis=1).round(2).tolist(),
        "frame_outer_quad_base_px": fquad.round(2).tolist(),
        "mean_shift_px": (dst - src).mean(0).round(3).tolist(),
        "point_list": good,
    }
    # registered concept: sample concept at H(x) (+ TPS residual faded beyond the frame)
    yy, xx = np.mgrid[0:C.H, 0:C.W]
    P = np.c_[xx.ravel() + 0.5, yy.ravel() + 0.5]
    Q = apply_h(Hm, P)
    tq = tps(P)
    # fade: 1 inside the frame quad, 0 at 80 px outside it
    from PIL import Image, ImageDraw
    mk = Image.new("L", (C.W, C.H), 0)
    ImageDraw.Draw(mk).polygon([tuple(v) for v in fquad], fill=255)
    inside = np.asarray(mk) > 0
    fade = np.clip(1 - ndimage.distance_transform_edt(~inside) / 80.0, 0, 1).ravel()
    Q2 = Q + tq * fade[:, None]
    tag_ = f"-{tag}" if tag else ""
    for tag, QQ in (("H", Q), ("HT", Q2)):
        reg = C.bilinear(concept, QQ[:, 0].reshape(C.H, C.W), QQ[:, 1].reshape(C.H, C.W))
        np.save(out / map_key / f"warp{tag_}-{tag}.npy", QQ.reshape(C.H, C.W, 2).astype(np.float32))
        C.save_rgb(out / map_key / f"concept{tag_}-registered-{tag}.png", reg)
    rep["registered"] = {"H": f"concept{tag_}-registered-H.png", "HT": f"concept{tag_}-registered-HT.png",
                         "warp": "warp-<tag>.npy = concept px (1920x1080 frame) per base px"}
    # check overlay: base edges in cyan over registered concept
    reg = C.load_rgb(out / map_key / f"concept{tag_}-registered-HT.png")
    e = grad_mag(base)
    e = np.clip(e / np.percentile(e, 98), 0, 1)[..., None]
    ov = reg * (1 - 0.6 * e) + np.array([0, 1, 1], np.float32) * 0.6 * e
    C.save_rgb(out / map_key / f"check{tag_}-registered-vs-base-edges.jpg", ov)
    eu = np.clip(grad_mag(concept) / np.percentile(grad_mag(concept), 98), 0, 1)[..., None]
    ov0 = concept * (1 - 0.6 * e) + np.array([0, 1, 1], np.float32) * 0.6 * e
    C.save_rgb(out / map_key / f"check{tag_}-unregistered-vs-base-edges.jpg", ov0)
    return rep


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("map", choices=sorted(C.MAPS))
    ap.add_argument("--out", type=Path, default=OUT)
    ap.add_argument("--image", type=Path, help="another concept-framed plate (default: the selected concept)")
    ap.add_argument("--crop", type=float, nargs=4, help="crop box of the concept framing inside the plate")
    ap.add_argument("--tag", default="", help="output name tag for --image")
    a = ap.parse_args()
    (a.out / a.map).mkdir(parents=True, exist_ok=True)
    rep = register(a.map, a.out, a.image, a.crop, a.tag)
    C.dump_json(a.out / a.map / (f"registration-{a.tag}.json" if a.tag else "registration.json"), rep)
    short = {k: rep[k] for k in ("points", "identity_error_px", "identity_error_circles_px", "homography_residual_px",
                                 "homography_residual_circles_px", "homography_loo_px", "tps_loo_px",
                                 "map_corner_shift_px", "mean_shift_px")}
    print(json.dumps(short, indent=1))


if __name__ == "__main__":
    main()
