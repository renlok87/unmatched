"""Exemplar-based paint-out (Criminisi et al. 2004, simplified) for the 'UNMATCHED <MAP>' logo.

Works at source resolution on float RGB in [0, 1]. Deterministic: fixed fill order (priority,
first index on ties), exhaustive SSD search in a window, first minimum on ties.
"""
from __future__ import annotations

import numpy as np
from scipy import ndimage
from scipy.signal import fftconvolve

PARAMS = {
    "patch_px": 9,
    "search_px": 110,
    "distance_penalty": 2e-7,  # per px^2, added to the mean squared patch error
    "alpha": 1.0,
    "data_term_floor": 0.02,
    "poisson_seams": True,
}


def _corr(img: np.ndarray, ker: np.ndarray) -> np.ndarray:
    """'valid' cross-correlation via FFT."""
    return fftconvolve(img, ker[::-1, ::-1], mode="valid")


def inpaint(rgb: np.ndarray, hole: np.ndarray, protect: np.ndarray,
            cls: np.ndarray | None = None) -> tuple[np.ndarray, dict]:
    """rgb (H, W, 3) float; hole (H, W) bool = pixels to replace; protect (H, W) bool = pixels
    that must not be used as source (game layer). cls (H, W) int, optional: texture class of
    every pixel (inside the hole: the class the fill should have); a target patch only takes
    source patches whose centre has the class of the target centre. Returns (new rgb, stats)."""
    p = PARAMS["patch_px"]
    hp = p // 2
    S = PARAMS["search_px"]
    ys, xs = np.nonzero(hole)
    y0 = max(0, ys.min() - S - p)
    y1 = min(rgb.shape[0], ys.max() + S + p + 1)
    x0 = max(0, xs.min() - S - p)
    x1 = min(rgb.shape[1], xs.max() + S + p + 1)
    if ys.min() - hp < 0 or xs.min() - hp < 0 or ys.max() + hp >= rgb.shape[0] or xs.max() + hp >= rgb.shape[1]:
        raise ValueError("hole too close to the image border for the patch size")
    img = rgb[y0:y1, x0:x1].copy()
    hol = hole[y0:y1, x0:x1].copy()
    known = ~hol
    src_ok = known & ~protect[y0:y1, x0:x1]
    # candidate centres: whole patch inside the (initial) source region
    src_c = ndimage.binary_erosion(src_ok, structure=np.ones((p, p), bool), border_value=0)
    cl = None if cls is None else cls[y0:y1, x0:x1]
    conf = known.astype(np.float64)
    orig = img.copy()
    hole_c = hol.copy()
    off = np.zeros(hol.shape + (2,), np.int32)  # source offset (dy, dx) of every filled pixel
    img[hol] = 0.0
    H, W = hol.shape
    gy_all, gx_all = np.mgrid[0:H, 0:W]
    lum_w = np.array([0.2126, 0.7152, 0.0722])
    iters = 0
    copied_from = []
    while hol.any():
        iters += 1
        front = hol & ndimage.binary_dilation(known, structure=np.ones((3, 3), bool))
        fy, fx = np.nonzero(front)
        # confidence term
        csum = ndimage.uniform_filter(conf, size=p, mode="constant") * (p * p)
        C = csum[fy, fx] / (p * p)
        # data term: isophote of the known image vs. front normal
        lum = img @ lum_w
        gyy, gxx = np.gradient(lum)
        valid_g = ndimage.binary_erosion(known, structure=np.ones((3, 3), bool)).astype(np.float64)
        # isophote at the front = known-pixel gradient averaged over 5x5, rotated by 90 deg
        wsum = np.maximum(ndimage.uniform_filter(valid_g, 5), 1e-9)
        gxs = ndimage.uniform_filter(gxx * valid_g, 5) / wsum
        gys = ndimage.uniform_filter(gyy * valid_g, 5) / wsum
        ny, nx = np.gradient(ndimage.gaussian_filter(known.astype(np.float64), 1.0))
        nn = np.hypot(nx, ny) + 1e-9
        D = np.abs(-gys[fy, fx] * nx[fy, fx] / nn[fy, fx] + gxs[fy, fx] * ny[fy, fx] / nn[fy, fx])
        D = D / PARAMS["alpha"] + PARAMS["data_term_floor"]
        Pr = C * D
        k = int(np.argmax(Pr))
        py, px = int(fy[k]), int(fx[k])
        # target patch
        ty0, tx0 = py - hp, px - hp
        T = img[ty0:ty0 + p, tx0:tx0 + p]
        M = known[ty0:ty0 + p, tx0:tx0 + p].astype(np.float64)
        # search window
        wy0, wy1 = max(0, py - S - hp), min(H, py + S + hp + 1)
        wx0, wx1 = max(0, px - S - hp), min(W, px + S + hp + 1)
        Wn = img[wy0:wy1, wx0:wx1]
        ssd = np.zeros((wy1 - wy0 - p + 1, wx1 - wx0 - p + 1))
        for c in range(3):
            Tc = T[:, :, c] * M
            ssd += (Tc * T[:, :, c]).sum() - 2 * _corr(Wn[:, :, c], Tc) + _corr(Wn[:, :, c] ** 2, M)
        ssd /= max(M.sum(), 1.0)
        cy = gy_all[wy0 + hp:wy1 - hp, wx0 + hp:wx1 - hp]
        cx = gx_all[wy0 + hp:wy1 - hp, wx0 + hp:wx1 - hp]
        ssd += PARAMS["distance_penalty"] * ((cy - py) ** 2 + (cx - px) ** 2)
        ssd[~src_c[wy0 + hp:wy1 - hp, wx0 + hp:wx1 - hp]] = np.inf
        if cl is not None:
            ssd[cl[wy0 + hp:wy1 - hp, wx0 + hp:wx1 - hp] != cl[py, px]] = np.inf
        q = int(np.argmin(ssd))
        qy, qx = np.unravel_index(q, ssd.shape)
        qy, qx = int(qy + wy0 + hp), int(qx + wx0 + hp)
        if not np.isfinite(ssd.ravel()[q]):
            raise RuntimeError("no source patch available")
        fill = ~known[ty0:ty0 + p, tx0:tx0 + p]
        src = img[qy - hp:qy + hp + 1, qx - hp:qx + hp + 1]
        T[fill] = src[fill]
        off[ty0:ty0 + p, tx0:tx0 + p][fill] = (qy - py, qx - px)
        conf[ty0:ty0 + p, tx0:tx0 + p][fill] = C[k]
        known[ty0:ty0 + p, tx0:tx0 + p][fill] = True
        hol[ty0:ty0 + p, tx0:tx0 + p][fill] = False
        copied_from.append((qx - px, qy - py))
    seams = 0
    if PARAMS["poisson_seams"]:
        img, seams = _poisson_stitch(img, orig, hole_c, off)
    out = rgb.copy()
    out[y0:y1, x0:x1] = img
    cf = np.array(copied_from, float)
    stats = {"iterations": iters, "hole_px": int(hole.sum()),
             "median_copy_offset_px": round(float(np.median(np.hypot(cf[:, 0], cf[:, 1]))), 1),
             "seam_pairs": int(seams), "crop": [int(x0), int(y0), int(x1), int(y1)]}
    return out, stats


def _poisson_stitch(img: np.ndarray, orig: np.ndarray, hole: np.ndarray, off: np.ndarray):
    """Gradient-domain stitching of the exemplar fill: inside the hole solve a Poisson equation
    whose guidance gradients are the copied ones, and across a seam between two different
    source offsets the mean of the two sources' own gradients (Dirichlet = known pixels)."""
    from scipy.sparse import coo_matrix
    from scipy.sparse.linalg import spsolve
    H, W = hole.shape
    idx = -np.ones((H, W), np.int64)
    ys, xs = np.nonzero(hole)
    n = len(ys)
    idx[ys, xs] = np.arange(n)
    rows, cols, vals = [], [], []
    rhs = np.zeros((n, 3))
    seams = 0
    diag = np.zeros(n)
    for dy, dx in ((0, 1), (0, -1), (1, 0), (-1, 0)):
        qy, qx = ys + dy, xs + dx
        inb = (qy >= 0) & (qy < H) & (qx >= 0) & (qx < W)
        py_, px_ = ys[inb], xs[inb]
        qy, qx = qy[inb], qx[inb]
        ip = idx[py_, px_]
        diag[ip] += 1
        # guidance g = I(p) - I(q)
        g = img[py_, px_] - img[qy, qx]
        op, oq = off[py_, px_], off[qy, qx]
        diff = (op != oq).any(axis=1)
        if diff.any():
            seams += int(diff.sum())
            d = np.nonzero(diff)[0]
            spy, spx = py_[d] + op[d, 0], px_[d] + op[d, 1]      # p in its source
            sqy, sqx = qy[d] + oq[d, 0], qx[d] + oq[d, 1]        # q in its source
            a_y, a_x = spy + dy, spx + dx                         # neighbour of p's source
            b_y, b_x = sqy - dy, sqx - dx                         # neighbour of q's source
            ok = ((a_y >= 0) & (a_y < H) & (a_x >= 0) & (a_x < W) & (b_y >= 0) & (b_y < H) & (b_x >= 0) & (b_x < W))
            ok[ok] &= ~hole[a_y[ok], a_x[ok]] & ~hole[b_y[ok], b_x[ok]]
            gp = orig[spy[ok], spx[ok]] - orig[a_y[ok], a_x[ok]]
            gq = orig[b_y[ok], b_x[ok]] - orig[sqy[ok], sqx[ok]]
            g[d[ok]] = 0.5 * (gp + gq)
        rhs[ip] += g
        qin = hole[qy, qx]
        rows.append(ip[qin])
        cols.append(idx[qy[qin], qx[qin]])
        vals.append(-np.ones(int(qin.sum())))
        # Dirichlet neighbours
        np.add.at(rhs, ip[~qin], img[qy[~qin], qx[~qin]])
    rows.append(np.arange(n))
    cols.append(np.arange(n))
    vals.append(diag)
    A = coo_matrix((np.concatenate(vals), (np.concatenate(rows), np.concatenate(cols))), shape=(n, n)).tocsr()
    sol = np.column_stack([spsolve(A, rhs[:, c]) for c in range(3)])
    out = img.copy()
    out[ys, xs] = np.clip(sol, 0.0, 1.0)
    return out, seams


def class_map(rgb: np.ndarray, hole: np.ndarray, rule: str, noise_amp: float = 0.12,
              noise_sigma: float = 6.0, seed: int = 0) -> np.ndarray:
    """Texture class per pixel for the guided fill. Outside the hole: the rule on a 5x5 mean
    colour. Inside: harmonic extension of the boundary classes (Laplace, Jacobi) plus a fixed
    low-frequency noise so the class border is irregular, thresholded at 0.5."""
    m = ndimage.uniform_filter(rgb, size=(5, 5, 1))
    if rule == "b_gt_r":
        c = (m[..., 2] > m[..., 0]).astype(np.float64)
    else:
        raise ValueError(f"unknown class rule {rule}")
    ys, xs = np.nonzero(hole)
    y0, y1, x0, x1 = ys.min() - 2, ys.max() + 3, xs.min() - 2, xs.max() + 3
    sub = c[y0:y1, x0:x1].copy()
    hs = hole[y0:y1, x0:x1]
    sub[hs] = 0.5
    for _ in range(4000):
        avg = 0.25 * (np.roll(sub, 1, 0) + np.roll(sub, -1, 0) + np.roll(sub, 1, 1) + np.roll(sub, -1, 1))
        sub[hs] = avg[hs]
    rng = np.random.default_rng(seed)
    noise = ndimage.gaussian_filter(rng.standard_normal(sub.shape), noise_sigma)
    noise *= noise_amp / max(noise.std(), 1e-9)
    out = c.copy()
    out[y0:y1, x0:x1][hs] = (sub + noise)[hs] > 0.5
    return out.astype(np.int8)


# ------------------------------------------------------------------ multi-scale patch voting
WEXLER = {
    "patch_px": 7,
    "levels": 3,              # 1/4, 1/2, 1
    "iters": [12, 8, 5],      # per level, coarse -> fine
    "source_stride_fine": 2,  # candidate stride at the finest level (1 elsewhere)
    "chunk": 1024,
    "final_pick": "best",     # finest level: take each pixel from its single best covering patch
}


def _patches(img: np.ndarray, ys: np.ndarray, xs: np.ndarray, hp: int) -> np.ndarray:
    """Stack (n, p*p*3) of patches centred at (ys, xs)."""
    o = np.arange(-hp, hp + 1)
    YY = ys[:, None, None] + o[None, :, None]
    XX = xs[:, None, None] + o[None, None, :]
    return img[YY, XX].reshape(len(ys), -1)


def _down(a: np.ndarray, mode: str) -> np.ndarray:
    h, w = a.shape[:2]
    a = a[: h // 2 * 2, : w // 2 * 2]
    b = a.reshape(h // 2, 2, w // 2, 2, *a.shape[2:])
    if mode == "mean":
        return b.mean(axis=(1, 3))
    if mode == "any":
        return b.any(axis=(1, 3))
    return b.all(axis=(1, 3))


def inpaint_multiscale(rgb: np.ndarray, hole: np.ndarray, protect: np.ndarray,
                       init: np.ndarray | None = None) -> tuple[np.ndarray, dict]:
    """Wexler-style completion: at each pyramid level alternate exhaustive nearest-neighbour
    patch search (source = known & not protected) and patch voting over the hole."""
    p = WEXLER["patch_px"]
    hp = p // 2
    S = PARAMS["search_px"]
    L = WEXLER["levels"]
    ys, xs = np.nonzero(hole)
    m = 2 ** (L - 1)
    y0 = max(0, (ys.min() - S) // m * m)
    x0 = max(0, (xs.min() - S) // m * m)
    y1 = min(rgb.shape[0], ys.max() + S + 1)
    x1 = min(rgb.shape[1], xs.max() + S + 1)
    y1 = y0 + (y1 - y0) // m * m
    x1 = x0 + (x1 - x0) // m * m
    img0 = rgb[y0:y1, x0:x1].astype(np.float32)
    hol0 = hole[y0:y1, x0:x1]
    src0 = ~hol0 & ~protect[y0:y1, x0:x1]
    ini0 = None if init is None else init[y0:y1, x0:x1].astype(np.float32)
    pyr = [(img0, hol0, src0, ini0)]
    for _ in range(L - 1):
        a, h_, s_, i_ = pyr[-1]
        pyr.append((_down(a, "mean"), _down(h_, "any"), _down(s_, "all"), None if i_ is None else _down(i_, "mean")))
    pyr = pyr[::-1]  # coarse -> fine
    est = None
    stats = {"levels": []}
    for li, (orig, hol, src, ini) in enumerate(pyr):
        H, W = hol.shape
        img = orig.copy()
        if est is None and ini is not None:
            img[hol] = ini[hol]
        elif est is None:
            # harmonic-ish init: repeated blur of known colours into the hole
            known = (~hol).astype(np.float32)
            fill = img * known[..., None]
            wsum = known.copy()
            for _ in range(200):
                fill = ndimage.uniform_filter(fill, size=(3, 3, 1))
                wsum = ndimage.uniform_filter(wsum, size=3)
                done = img * known[..., None]
                fill = np.where(hol[..., None], fill, done)
                wsum = np.where(hol, wsum, 1.0)
            img[hol] = (fill / np.maximum(wsum, 1e-6)[..., None])[hol]
        else:
            up = ndimage.zoom(est, (H / est.shape[0], W / est.shape[1], 1), order=1)
            img[hol] = up[hol]
        # candidate source centres
        sc = ndimage.binary_erosion(src, structure=np.ones((p, p), bool), border_value=0)
        sc[:hp, :] = sc[-hp:, :] = False
        sc[:, :hp] = sc[:, -hp:] = False
        stride = WEXLER["source_stride_fine"] if li == L - 1 else 1
        if stride > 1:
            grid = np.zeros_like(sc)
            grid[::stride, ::stride] = True
            sc &= grid
        sy, sx = np.nonzero(sc)
        # target patches: every centre whose patch touches the hole
        tmask = ndimage.binary_dilation(hol, structure=np.ones((p, p), bool))
        tmask[:hp, :] = tmask[-hp:, :] = False
        tmask[:, :hp] = tmask[:, -hp:] = False
        ty, tx = np.nonzero(tmask)
        o = np.arange(-hp, hp + 1)
        for it in range(WEXLER["iters"][li]):
            SP = _patches(img, sy, sx, hp)
            s2 = (SP * SP).sum(1)
            TP = _patches(img, ty, tx, hp)
            nn = np.empty(len(ty), np.int64)
            dd = np.empty(len(ty), np.float32)
            for c0 in range(0, len(ty), WEXLER["chunk"]):
                T = TP[c0:c0 + WEXLER["chunk"]]
                D = s2[None, :] - 2.0 * (T @ SP.T) + (T * T).sum(1)[:, None]
                k = np.argmin(D, axis=1)
                nn[c0:c0 + len(T)] = k
                dd[c0:c0 + len(T)] = np.maximum(D[np.arange(len(T)), k], 0)
            final = (li == L - 1 and it == WEXLER["iters"][li] - 1 and WEXLER["final_pick"] == "best")
            sig2 = float(np.percentile(dd, 75)) + 1e-8
            wgt = np.exp(-dd / (2 * sig2)).astype(np.float32)
            acc = np.zeros((H, W, 3), np.float32)
            wac = np.zeros((H, W), np.float32)
            best_w = np.full((H, W), -1.0, np.float32)
            best_c = np.zeros((H, W, 3), np.float32)
            for dy in o:
                for dx in o:
                    yy, xx = ty + dy, tx + dx
                    col = img[sy[nn] + dy, sx[nn] + dx]
                    if final:
                        # tie-break deterministic: strictly greater keeps the first
                        np.maximum.at(best_w, (yy, xx), wgt)
                    else:
                        np.add.at(acc, (yy, xx), col * wgt[:, None])
                        np.add.at(wac, (yy, xx), wgt)
            if final:
                # second pass: assign the colour of the (first) patch achieving the max weight
                taken = np.zeros((H, W), bool)
                for dy in o:
                    for dx in o:
                        yy, xx = ty + dy, tx + dx
                        hit = (wgt >= best_w[yy, xx]) & ~taken[yy, xx]
                        best_c[yy[hit], xx[hit]] = img[sy[nn[hit]] + dy, sx[nn[hit]] + dx]
                        taken[yy[hit], xx[hit]] = True
                img[hol] = best_c[hol]
            else:
                img[hol] = (acc[hol] / np.maximum(wac[hol], 1e-12)[:, None])
        est = img
        stats["levels"].append({"shape": [H, W], "targets": int(len(ty)), "sources": int(len(sy)),
                                "median_nn_ssd": round(float(np.median(dd)), 5)})
    out = rgb.copy()
    out[y0:y1, x0:x1] = np.where(hol0[..., None], est, rgb[y0:y1, x0:x1])
    stats.update({"hole_px": int(hole.sum()), "crop": [int(x0), int(y0), int(x1), int(y1)]})
    return out, stats
