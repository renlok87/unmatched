"""Vector game layer of an original Unmatched map, measured on the map illustration.

Coordinates: continuous source pixels of the 1337x866 illustration (SVG / topology convention:
pixel (i, j) covers [j, j+1] x [i, i+1], its centre is (j + 0.5, i + 0.5)). y grows downwards,
angles are atan2(dy, dx) in degrees (0 = +x, 90 = +y = down on the image).

What is measured here (numbers only, no pixels leave this module):
  * ring: centre-line radius and stroke width of the painted circle outlines (global per map);
  * dividers: rays of the half / wedge zone splits, from the zone SVG pieces of maps.json, plus
    their measured offset against the painted divider stroke;
  * connections: one polyline per topology edge, traced on the thick dark-line mask of the image
    (geodesic path in a corridor, then a straight-line or circular-arc fit extended to both rings);
  * start diamonds: centre and half-diagonal of the numbered diamond on each start space.
"""
from __future__ import annotations

import math
import re

import numpy as np
from scipy import ndimage
from scipy.sparse import coo_matrix
from scipy.sparse.csgraph import dijkstra

# ------------------------------------------------------------------ parameters (recorded in JSON)
PARAMS = {
    "dark_maxc_hi": 0.30,      # max(R,G,B) at/above this is "not a line" (0 darkness)
    "dark_maxc_lo": 0.18,      # max(R,G,B) at/below this is fully dark
    "dark_blur_sigma_px": 1.2,
    "path_cost_offline": 30.0,  # cost multiplier off the dark stroke
    "block_disc_r_px": 65.0,   # discs (incl. their ring) are not traversable for the tracer
    "seed_band_px": [65.0, 69.0],
    "corridor_w": [0.33, 14.0],  # corridor half-width = a * chord + b (px)
    "arc_min_samples": 25,     # arc model needs this many centre-line samples
    "arc_max_rms_px": 0.5,     # ... fits a circle this well
    "arc_min_rms_ratio": 2.0,  # ... and beats the straight fit by this factor
    "arc_min_sagitta_px": 0.75,  # ... and bows at least this much between the rings
    "centreline_min_r_px": 65.0,
    "fit_min_darkness": 0.55,  # only path samples on the stroke are used for the fit
    "short_gap_min_samples": 4,  # fewer path centre-line samples: sample the stroke along the chord
    "short_gap_step_px": 0.5,
    "short_gap_recentre": 3,   # mean-shift steps of the +-6 px profile window (chord samples, check)
    "polyline_step_px": 3.0,
    "fallback_coverage": 0.9,  # below this the straight ring-to-ring search is tried as well
    "offset_check_at": [0.2, 0.35, 0.5, 0.65, 0.8],  # fractions of the polyline length
    "max_stroke_offset_px": 0.5,  # |median painted-stroke centre - polyline| above this fails the build
}

_TOKEN = re.compile(r"[MCLZmclz]|-?\d+(?:\.\d+)?(?:e-?\d+)?")
_PATH = re.compile(r'<path\b[^>]*\bd="([^"]+)"')


# ------------------------------------------------------------------ image helpers
def darkness(rgb: np.ndarray) -> np.ndarray:
    """Soft 'black stroke' likelihood from max channel (neutral black lines; brown soil stays low)."""
    mx = rgb.max(axis=2)
    lo, hi = PARAMS["dark_maxc_lo"], PARAMS["dark_maxc_hi"]
    return np.clip((hi - mx) / (hi - lo), 0.0, 1.0)


def luma(rgb: np.ndarray) -> np.ndarray:
    return rgb @ np.array([0.2126, 0.7152, 0.0722])


def sample(img: np.ndarray, xs, ys, order: int = 1) -> np.ndarray:
    """Sample a (H, W) array at continuous source coordinates."""
    return ndimage.map_coordinates(img, [np.asarray(ys) - 0.5, np.asarray(xs) - 0.5], order=order, mode="nearest")


# ------------------------------------------------------------------ rings
def measure_ring(dark: np.ndarray, spaces: list[dict]) -> dict:
    """Median radial darkness profile over all spaces -> centre-line radius and FWHM width."""
    rr = np.arange(55.0, 70.0, 0.1)
    angs = np.deg2rad(np.arange(0.0, 360.0, 1.0))
    profiles = []
    for s in spaces:
        cx, cy = s["px"]
        X = cx + np.cos(angs)[:, None] * rr[None, :]
        Y = cy + np.sin(angs)[:, None] * rr[None, :]
        P = sample(dark, X, Y)
        # keep angles where the ring is a thin isolated stroke (no line / dark fill touching)
        ok = (P[:, rr < 58.0].max(1) < 0.2) & (P[:, rr > 67.0].max(1) < 0.2)
        profiles.append(P[ok])
    P = np.concatenate(profiles)
    prof = np.median(P, axis=0)
    k = int(np.argmax(prof))
    peak = prof[k]
    half = peak / 2.0
    # sub-sample crossings of the half maximum
    i0 = k
    while i0 > 0 and prof[i0] > half:
        i0 -= 1
    i1 = k
    while i1 < len(prof) - 1 and prof[i1] > half:
        i1 += 1
    r_in = rr[i0] + (half - prof[i0]) / (prof[i0 + 1] - prof[i0]) * 0.1
    r_out = rr[i1 - 1] + (prof[i1 - 1] - half) / (prof[i1 - 1] - prof[i1]) * 0.1
    return {
        "r_center_px": round(float((r_in + r_out) / 2.0), 3),
        "width_fwhm_px": round(float(r_out - r_in), 3),
        "r_inner_px": round(float(r_in), 3),
        "r_outer_px": round(float(r_out), 3),
        "samples": int(P.shape[0]),
        "peak_darkness": round(float(peak), 3),
    }


def fit_ring_centres(dark: np.ndarray, spaces: list[dict], r_ring: float) -> list[dict]:
    """Per-space centre of the painted ring (ring-template contrast, grid search +-2.5 px at
    0.125 px, radius fixed to the map's median ring radius), plus that space's own best radius.
    The topology centres stay authoritative for the game; the render layers (SDF / ID / mask)
    use these painted centres so the vector strokes sit on the painted ones."""
    out = []
    angs = np.deg2rad(np.arange(0.0, 360.0, 1.0))
    ca, sa = np.cos(angs), np.sin(angs)

    def score(cx, cy, r):
        on = sample(dark, cx + ca * r, cy + sa * r)
        inn = sample(dark, cx + ca * (r - 3.5), cy + sa * (r - 3.5))
        out_ = sample(dark, cx + ca * (r + 3.5), cy + sa * (r + 3.5))
        return float(np.mean(np.clip(on - 0.5 * (inn + out_), -0.25, 1.0)))

    for s in spaces:
        cx, cy = s["px"]
        base = score(cx, cy, r_ring)
        best = (base, 0.0, 0.0)
        for step, span, c0 in ((0.5, 2.5, (0.0, 0.0)), (0.125, 0.5, None)):
            if c0 is None:
                c0 = (best[1], best[2])
            g = np.arange(-span, span + 1e-9, step)
            for dx in g:
                for dy in g:
                    sc = score(cx + c0[0] + dx, cy + c0[1] + dy, r_ring)
                    if sc > best[0] + 1e-12:
                        best = (sc, c0[0] + dx, c0[1] + dy)
        rs = np.arange(r_ring - 1.5, r_ring + 1.5001, 0.1)
        rsc = [score(cx + best[1], cy + best[2], r) for r in rs]
        out.append({"id": s["id"], "dx": round(float(best[1]), 3), "dy": round(float(best[2]), 3),
                    "contrast_topology": round(base, 4), "contrast_fitted": round(best[0], 4),
                    "own_best_r_px": round(float(rs[int(np.argmax(rsc))]), 2)})
    return out


# ------------------------------------------------------------------ dividers
def _path_lines(d: str) -> list[tuple[tuple[float, float], tuple[float, float]]]:
    toks = _TOKEN.findall(d)
    i, cmd, pos, lines = 0, None, None, []
    arity = {"M": 2, "C": 6, "L": 2}
    while i < len(toks):
        t = toks[i]
        if t in "MCLZmclz":
            if t.islower():
                raise ValueError("relative path command not supported")
            cmd = t
            i += 1
            continue
        n = arity[cmd]
        nums = [float(x) for x in toks[i:i + n]]
        i += n
        end = (nums[-2], nums[-1])
        if cmd == "L":
            lines.append((pos, end))
        pos = end
    return lines


def dividers_from_svg(map_rec: dict, spaces: list[dict], r_ring: float) -> dict:
    """Rays (angle, from the space centre to the ring) of every half / wedge split."""
    segs = []
    for zone in map_rec.get("zones") or []:
        for d in _PATH.findall(zone.get("svgGroup") or ""):
            segs.extend(_path_lines(d))
    out: dict[str, list[float]] = {}
    for s in spaces:
        if len(s["zones"]) < 2:
            continue
        cx, cy = s["px"]
        angs: list[float] = []
        for a, b in segs:
            for p in (a, b):
                dist = math.hypot(p[0] - cx, p[1] - cy)
                if 40.0 < dist < 75.0:  # rim end of a divider belonging to this space
                    ang = math.degrees(math.atan2(p[1] - cy, p[0] - cx)) % 360.0
                    if all(min(abs(ang - q), 360 - abs(ang - q)) > 3.0 for q in angs):
                        angs.append(ang)
        angs.sort()
        want = 2 if len(s["zones"]) == 2 else 3
        if len(angs) != want:
            raise ValueError(f"{s['id']}: {len(angs)} divider rays from SVG, expected {want}")
        out[s["id"]] = [round(a, 3) for a in angs]
    return out


def measure_dividers(rgb: np.ndarray, spaces: list[dict], rays: dict, r_ring: float) -> dict:
    """Offset (px, +90 deg side) and width of the painted divider stroke along each SVG ray."""
    L = luma(rgb)
    byid = {s["id"]: s for s in spaces}
    offs = np.arange(-6.0, 6.01, 0.25)
    t = np.linspace(0.2, 0.85, 27) * r_ring
    res = {}
    all_off = []
    for sid, angs in rays.items():
        cx, cy = byid[sid]["px"]
        per = []
        for a in angs:
            u = np.array([math.cos(math.radians(a)), math.sin(math.radians(a))])
            n = np.array([-u[1], u[0]])
            X = cx + u[0] * t[:, None] + n[0] * offs[None, :]
            Y = cy + u[1] * t[:, None] + n[1] * offs[None, :]
            prof = np.median(sample(L, X, Y), axis=0)
            base = np.median(np.r_[prof[:4], prof[-4:]])
            dev = np.abs(prof - base)
            k = int(np.argmax(dev))
            w = dev / max(dev[k], 1e-6)
            sel = w > 0.5
            off = float(np.sum(offs[sel] * w[sel]) / np.sum(w[sel]))
            per.append({"ang": a, "offset_px": round(off, 2), "fwhm_px": round(float(sel.sum() * 0.25), 2),
                        "contrast": round(float(prof[k] - base), 3)})
            all_off.append(off)
        res[sid] = per
    return {"per_space": res, "abs_offset_px_median": round(float(np.median(np.abs(all_off))), 3),
            "abs_offset_px_max": round(float(np.max(np.abs(all_off))), 3)}


# ------------------------------------------------------------------ connections
def _circle_fit(pts: np.ndarray) -> tuple[float, float, float]:
    A = np.c_[2 * pts[:, 0], 2 * pts[:, 1], np.ones(len(pts))]
    b = (pts ** 2).sum(1)
    sol = np.linalg.lstsq(A, b, rcond=None)[0]
    cx, cy = sol[0], sol[1]
    r = math.sqrt(sol[2] + cx * cx + cy * cy)
    # Gauss-Newton refinement of the geometric distance
    for _ in range(20):
        dx, dy = pts[:, 0] - cx, pts[:, 1] - cy
        d = np.hypot(dx, dy)
        res = d - r
        J = np.c_[-dx / d, -dy / d, -np.ones(len(pts))]
        step = np.linalg.lstsq(J, -res, rcond=None)[0]
        cx, cy, r = cx + step[0], cy + step[1], r + step[2]
        if np.abs(step).max() < 1e-6:
            break
    return float(cx), float(cy), float(r)


def _line_circle(p0, u, c, r):
    """Intersections p0 + t u with circle (c, r); returns sorted t values."""
    d = p0 - c
    b = 2 * np.dot(u, d)
    cc = np.dot(d, d) - r * r
    disc = b * b - 4 * cc
    if disc < 0:
        return []
    s = math.sqrt(disc)
    return sorted([(-b - s) / 2, (-b + s) / 2])


def _circle_circle(c0, r0, c1, r1):
    d = math.hypot(c1[0] - c0[0], c1[1] - c0[1])
    if d > r0 + r1 or d < abs(r0 - r1) or d == 0:
        return []
    a = (r0 * r0 - r1 * r1 + d * d) / (2 * d)
    h = math.sqrt(max(r0 * r0 - a * a, 0.0))
    ex = ((c1[0] - c0[0]) / d, (c1[1] - c0[1]) / d)
    mx, my = c0[0] + a * ex[0], c0[1] + a * ex[1]
    return [(mx - h * ex[1], my + h * ex[0]), (mx + h * ex[1], my - h * ex[0])]


def trace_edges(rgb: np.ndarray, spaces: list[dict], edges: list[list[str]], r_ring: float) -> dict:
    H, W = rgb.shape[:2]
    dkr = darkness(rgb)
    dk = ndimage.gaussian_filter(dkr, PARAMS["dark_blur_sigma_px"])
    dk = np.clip(dk / max(np.percentile(dk, 99.9), 1e-6), 0, 1)
    cost_img = 1.0 + PARAMS["path_cost_offline"] * (1.0 - dk) ** 2
    yy, xx = np.mgrid[0:H, 0:W]
    xc, yc = xx + 0.5, yy + 0.5
    byid = {s["id"]: s for s in spaces}
    blocked = np.zeros((H, W), bool)
    for s in spaces:
        cx, cy = s["px"]
        blocked |= (xc - cx) ** 2 + (yc - cy) ** 2 < PARAMS["block_disc_r_px"] ** 2
    out = {}
    for a_id, b_id in edges:
        A = np.array(byid[a_id]["px"], float)
        B = np.array(byid[b_id]["px"], float)
        chord = float(np.linalg.norm(B - A))
        wcor = PARAMS["corridor_w"][0] * chord + PARAMS["corridor_w"][1]
        x0 = int(max(0, math.floor(min(A[0], B[0]) - wcor - 2)))
        x1 = int(min(W, math.ceil(max(A[0], B[0]) + wcor + 2)))
        y0 = int(max(0, math.floor(min(A[1], B[1]) - wcor - 2)))
        y1 = int(min(H, math.ceil(max(A[1], B[1]) + wcor + 2)))
        sx, sy = xc[y0:y1, x0:x1], yc[y0:y1, x0:x1]
        u = (B - A) / chord
        t = np.clip((sx - A[0]) * u[0] + (sy - A[1]) * u[1], 0, chord)
        dseg = np.hypot(sx - (A[0] + t * u[0]), sy - (A[1] + t * u[1]))
        allowed = (dseg <= wcor) & ~blocked[y0:y1, x0:x1]
        ra = np.hypot(sx - A[0], sy - A[1])
        rb = np.hypot(sx - B[0], sy - B[1])
        lo, hi = PARAMS["seed_band_px"]
        seeds = allowed & (ra >= lo) & (ra <= hi)
        targets = allowed & (rb >= lo) & (rb <= hi)
        h, w = allowed.shape
        idx = -np.ones((h, w), np.int64)
        n = int(allowed.sum())
        idx[allowed] = np.arange(n)
        c = cost_img[y0:y1, x0:x1]
        rows, cols, wts = [], [], []
        for dy, dx in ((0, 1), (1, 0), (1, 1), (1, -1)):
            ya0, ya1 = max(0, -dy), h - max(0, dy)
            xa0, xa1 = max(0, -dx), w - max(0, dx)
            a_ok = allowed[ya0:ya1, xa0:xa1] & allowed[ya0 + dy:ya1 + dy, xa0 + dx:xa1 + dx]
            ia = idx[ya0:ya1, xa0:xa1][a_ok]
            ib = idx[ya0 + dy:ya1 + dy, xa0 + dx:xa1 + dx][a_ok]
            wv = 0.5 * (c[ya0:ya1, xa0:xa1][a_ok] + c[ya0 + dy:ya1 + dy, xa0 + dx:xa1 + dx][a_ok]) * math.hypot(dx, dy)
            rows += [ia, ib]
            cols += [ib, ia]
            wts += [wv, wv]
        src = n  # super source
        sidx = idx[seeds]
        rows.append(np.full(len(sidx), src))
        cols.append(sidx)
        wts.append(np.full(len(sidx), 1e-9))
        G = coo_matrix((np.concatenate(wts), (np.concatenate(rows), np.concatenate(cols))), shape=(n + 1, n + 1)).tocsr()
        dist, pred = dijkstra(G, directed=True, indices=src, return_predecessors=True)
        tidx = idx[targets]
        tbest = int(tidx[np.argmin(dist[tidx])])
        path = []
        k = tbest
        while k != src and k >= 0:
            path.append(k)
            k = pred[k]
        path = path[::-1]
        inv = np.argwhere(allowed)  # row-major order == idx order
        P = np.array([(inv[k][1] + x0 + 0.5, inv[k][0] + y0 + 0.5) for k in path])
        Q, qpeak = _centreline_samples(dkr, P, A, B)
        rec = {"a": a_id, "b": b_id, "chord_px": round(chord, 2), "path_samples": int(len(P)),
               "centreline_samples": int(len(Q))}
        if len(Q) < PARAMS["short_gap_min_samples"]:
            # short rim-to-rim gap (S09-S10: 15.7 px): the traced path is only a few pixels long,
            # and a fit on its raw pixel centres sits ~1.3 px off the stroke -> sub-pixel stroke
            # centres along the chord over the whole gap instead
            Q, qpeak = _chord_centreline_samples(dkr, A, B)
            rec.update({"centreline_source": "chord-profile", "chord_centreline_samples": int(len(Q))})
        if len(Q) < 4:  # degenerate: fall back to raw path pixels
            Q = P
        # straight fit (total least squares) and circle fit on the sub-pixel centre-line samples
        m = Q.mean(0)
        _, _, vt = np.linalg.svd(Q - m)
        ud = vt[0]
        nrm = np.array([-ud[1], ud[0]])
        res_line = (Q - m) @ nrm
        rms_line = float(np.sqrt(np.mean(res_line ** 2)))
        rms_arc = None
        if len(Q) >= PARAMS["arc_min_samples"]:
            ccx, ccy, cr = _circle_fit(Q)
            resid = np.hypot(Q[:, 0] - ccx, Q[:, 1] - ccy) - cr
            rms_arc = float(np.sqrt(np.mean(resid ** 2)))
        arc = None
        if rms_arc is not None:
            arc = _arc_polyline(ccx, ccy, cr, A, B, P, r_ring)
        is_arc = (arc is not None and rms_arc <= PARAMS["arc_max_rms_px"]
                  and rms_line >= PARAMS["arc_min_rms_ratio"] * max(rms_arc, 0.02)
                  and abs(arc[1]) >= PARAMS["arc_min_sagitta_px"])
        rec.update({"straight_fit_rms_px": round(rms_line, 3),
                    "arc_fit_rms_px": None if rms_arc is None else round(rms_arc, 3),
                    "arc_candidate_sagitta_px": None if arc is None else round(arc[1], 2)})
        if not is_arc:
            if np.dot(ud, B - A) < 0:
                ud = -ud
            ta = _line_circle(m, ud, A, r_ring)
            tb = _line_circle(m, ud, B, r_ring)
            if not ta or not tb:
                raise ValueError(f"{a_id}-{b_id}: fitted line misses a ring")
            pa = m + ud * ta[1]  # exit of ring A towards B
            pb = m + ud * tb[0]  # entry of ring B
            pts = np.array([pa, pb])
            rec["kind"] = "straight"
        else:
            pts = arc[0]
            rec.update({"kind": "arc", "arc_center_px": [round(ccx, 3), round(ccy, 3)], "arc_radius_px": round(cr, 3),
                        "arc_start_deg": round(math.degrees(arc[2]), 4), "arc_sweep_deg": round(math.degrees(arc[3]), 4),
                        "sagitta_px": round(arc[1], 2)})
        rec["method"] = "geodesic-fit"
        rec["coverage"], rec["length_px"] = _coverage(dk, pts)
        if rec["coverage"] < PARAMS["fallback_coverage"]:
            # stroke interrupted (e.g. painted under the glass bridge): best straight ring-to-ring
            # segment by mean stroke darkness, which locks onto the visible fragments at both ends
            # (an interrupted stroke cannot support a curvature estimate, so it is always straight)
            spts = _straight_search(dk, A, B, r_ring)
            scov, slen = _coverage(dk, spts)
            rec = {k: v for k, v in rec.items()
                   if k not in ("arc_center_px", "arc_radius_px", "arc_start_deg", "arc_sweep_deg", "sagitta_px")}
            rec.update({"kind": "straight", "method": "ring-to-ring-search", "coverage": scov, "length_px": slen,
                        "geodesic_coverage": rec["coverage"]})
            pts = spts
        rec["polyline_px"] = [[round(float(x), 2), round(float(y), 2)] for x, y in pts]
        if rec["method"] == "geodesic-fit":  # an interrupted stroke has no centre to check against
            rec["stroke_offset_px"] = _stroke_offset(dkr, np.array(rec["polyline_px"]))
        out[f"{a_id}-{b_id}"] = rec
    checked = [(abs(r["stroke_offset_px"]), e) for e, r in out.items() if r.get("stroke_offset_px") is not None]
    worst = max(checked, default=(0.0, None))
    if worst[0] > PARAMS["max_stroke_offset_px"]:
        raise ValueError(f"{worst[1]}: polyline {worst[0]} px off the painted stroke centre "
                         f"(limit {PARAMS['max_stroke_offset_px']} px)")
    return out


def _arc_polyline(ccx, ccy, cr, A, B, P, r_ring):
    """Arc of the fitted circle between its crossings with ring A and ring B (the crossings
    nearest the traced path ends; sweep through the path middle). Returns (pts, sagitta)."""
    ia = _circle_circle((ccx, ccy), cr, tuple(A), r_ring)
    ib = _circle_circle((ccx, ccy), cr, tuple(B), r_ring)
    if not ia or not ib:
        return None
    pa = min(ia, key=lambda p: math.hypot(p[0] - P[0, 0], p[1] - P[0, 1]))
    pb = min(ib, key=lambda p: math.hypot(p[0] - P[-1, 0], p[1] - P[-1, 1]))
    a0 = math.atan2(pa[1] - ccy, pa[0] - ccx)
    a1 = math.atan2(pb[1] - ccy, pb[0] - ccx)
    mid = P[len(P) // 2]
    am = math.atan2(mid[1] - ccy, mid[0] - ccx)

    def _wrap(x):
        return (x + math.pi) % (2 * math.pi) - math.pi
    sweep = _wrap(a1 - a0)
    if not (sweep != 0 and 0 <= _wrap(am - a0) / sweep <= 1):
        sweep = sweep - math.copysign(2 * math.pi, sweep)
    nseg = max(2, int(math.ceil(abs(sweep) * cr / PARAMS["polyline_step_px"])))
    angs = a0 + sweep * np.linspace(0, 1, nseg + 1)
    pts = np.c_[ccx + cr * np.cos(angs), ccy + cr * np.sin(angs)]
    ch = np.array(pb) - np.array(pa)
    chn = np.array([-ch[1], ch[0]]) / np.linalg.norm(ch)
    sag = (pts - np.array(pa)) @ chn
    return pts, float(sag[np.argmax(np.abs(sag))]), float(a0), float(sweep)


def _centreline_samples(dkr: np.ndarray, P: np.ndarray, A: np.ndarray, B: np.ndarray):
    """Sub-pixel stroke centre across the traced path: darkness-weighted centroid of the
    perpendicular profile (+-6 px) at every path sample outside both rings."""
    if len(P) < 3:
        return np.zeros((0, 2)), np.zeros(0)
    Ps = ndimage.gaussian_filter1d(P, 3.0, axis=0, mode="nearest")
    tg = np.gradient(Ps, axis=0)
    tg /= np.maximum(np.linalg.norm(tg, axis=1, keepdims=True), 1e-9)
    nr = np.c_[-tg[:, 1], tg[:, 0]]
    rmin = PARAMS["centreline_min_r_px"]
    keep = (np.hypot(*(Ps - A).T) >= rmin) & (np.hypot(*(Ps - B).T) >= rmin)
    Ps, nr = Ps[keep], nr[keep]
    c, peak = _profile_centroids(dkr, Ps, nr)
    Q = Ps + nr * c[:, None]
    ok = peak >= PARAMS["fit_min_darkness"]
    return Q[ok], peak[ok]


def _chord_centreline_samples(dkr: np.ndarray, A: np.ndarray, B: np.ndarray):
    """Stroke centre of a short rim-to-rim gap: perpendicular-profile centroid every
    short_gap_step_px along the chord, over the whole gap outside both rings."""
    chord = float(np.linalg.norm(B - A))
    u = (B - A) / chord
    rmin = PARAMS["centreline_min_r_px"]
    ts = np.arange(rmin, chord - rmin + 1e-9, PARAMS["short_gap_step_px"])
    Ps = A[None, :] + ts[:, None] * u[None, :]
    nr = np.tile([-u[1], u[0]], (len(Ps), 1))
    # the stroke need not run along the chord (S09-S10: ~5 px beside it) -> mean-shift the window
    c, peak = _profile_centroids(dkr, Ps, nr, recentre=PARAMS["short_gap_recentre"])
    Q = Ps + nr * c[:, None]
    ok = peak >= PARAMS["fit_min_darkness"]
    return Q[ok], peak[ok]


def _profile_centroids(dkr: np.ndarray, Ps: np.ndarray, nr: np.ndarray, recentre: int = 0):
    """Darkness-weighted centroid (px along nr, from Ps) and peak of the +-6 px profile at every
    Ps; recentre > 0 moves the window onto the centroid that many more times (mean shift), so a
    stroke centred up to ~6 px off Ps is not clipped by the window."""
    offs = np.arange(-6.0, 6.01, 0.25)
    c = np.zeros(len(Ps))
    for _ in range(recentre + 1):
        C = Ps + nr * c[:, None]
        X = C[:, 0:1] + nr[:, 0:1] * offs[None, :]
        Y = C[:, 1:2] + nr[:, 1:2] * offs[None, :]
        V = sample(dkr, X, Y)
        peak = V.max(axis=1)
        wsum = np.maximum(V.sum(axis=1), 1e-9)
        c = c + (V * offs[None, :]).sum(axis=1) / wsum
    return c, peak


def _stroke_offset(dkr: np.ndarray, pts: np.ndarray):
    """Median perpendicular offset (px) of the painted stroke centre from the final polyline at
    offset_check_at of its length (same profile centroid as the fit); None if no stroke there."""
    seg = np.hypot(*np.diff(pts, axis=0).T)
    s = np.r_[0, np.cumsum(seg)]
    ss = np.asarray(PARAMS["offset_check_at"]) * s[-1]
    k = np.clip(np.searchsorted(s, ss, side="right") - 1, 0, len(pts) - 2)
    d = pts[k + 1] - pts[k]
    Ps = pts[k] + ((ss - s[k]) / seg[k])[:, None] * d
    u = d / seg[k][:, None]
    c, peak = _profile_centroids(dkr, Ps, np.c_[-u[:, 1], u[:, 0]], recentre=PARAMS["short_gap_recentre"])
    ok = peak >= PARAMS["fit_min_darkness"]
    return round(float(np.median(c[ok])), 3) if ok.any() else None


def _coverage(dk: np.ndarray, pts: np.ndarray) -> tuple[float, float]:
    """Fraction of the centre-line (1 px steps, 3 px ring AA trimmed) lying on the painted stroke."""
    seg_len = np.hypot(*np.diff(pts, axis=0).T)
    s_cum = np.r_[0, np.cumsum(seg_len)]
    ss = np.arange(0, s_cum[-1], 1.0)
    cov = sample(dk, np.interp(ss, s_cum, pts[:, 0]), np.interp(ss, s_cum, pts[:, 1]))
    core = (ss > 3) & (ss < s_cum[-1] - 3)
    return round(float((cov[core] >= 0.5).mean()), 3), round(float(s_cum[-1]), 2)


def _straight_search(dk: np.ndarray, A: np.ndarray, B: np.ndarray, r_ring: float) -> np.ndarray:
    base = math.atan2(B[1] - A[1], B[0] - A[0])
    t = np.linspace(0.03, 0.97, 160)

    def score(ta: np.ndarray, tb: np.ndarray) -> np.ndarray:
        pa = A[None, :] + r_ring * np.c_[np.cos(ta), np.sin(ta)]
        pb = B[None, :] + r_ring * np.c_[np.cos(tb), np.sin(tb)]
        X = pa[:, 0:1] + (pb[:, 0:1] - pa[:, 0:1]) * t[None, :]
        Y = pa[:, 1:2] + (pb[:, 1:2] - pa[:, 1:2]) * t[None, :]
        return sample(dk, X, Y).mean(axis=1)

    best = (-1.0, base, base + math.pi)
    for span, step, ca, cb in ((math.radians(70), math.radians(1.0), base, base + math.pi), (None, None, None, None)):
        if span is None:
            span, step = math.radians(1.5), math.radians(0.05)
            ca, cb = best[1], best[2]
        g = np.arange(-span, span + 1e-9, step)
        TA, TB = np.meshgrid(ca + g, cb + g, indexing="ij")
        sc = score(TA.ravel(), TB.ravel())
        k = int(np.argmax(sc))
        if sc[k] > best[0]:
            best = (float(sc[k]), float(TA.ravel()[k]), float(TB.ravel()[k]))
    pa = A + r_ring * np.array([math.cos(best[1]), math.sin(best[1])])
    pb = B + r_ring * np.array([math.cos(best[2]), math.sin(best[2])])
    return np.array([pa, pb])


def measure_line_width(rgb: np.ndarray, conns: dict) -> dict:
    """Median perpendicular darkness profile over all straight connection centre-lines."""
    dkr = darkness(rgb)
    L = luma(rgb)
    offs = np.arange(-9.0, 9.01, 0.25)
    profs, lprofs = [], []
    for rec in conns.values():
        if rec["kind"] != "straight" or rec["coverage"] < 0.95:
            continue
        p0, p1 = np.array(rec["polyline_px"][0]), np.array(rec["polyline_px"][-1])
        u = (p1 - p0) / np.linalg.norm(p1 - p0)
        n = np.array([-u[1], u[0]])
        ts = np.linspace(0.3, 0.7, 9) * np.linalg.norm(p1 - p0)
        X = p0[0] + u[0] * ts[:, None] + n[0] * offs[None, :]
        Y = p0[1] + u[1] * ts[:, None] + n[1] * offs[None, :]
        profs.append(sample(dkr, X, Y))
        lprofs.append(sample(L, X, Y))
    P = np.median(np.concatenate(profs), axis=0)
    LP = np.median(np.concatenate(lprofs), axis=0)
    half = P.max() / 2
    sel = P > half
    return {"core_fwhm_px": round(float(sel.sum() * 0.25), 3),
            "profile_offsets_px": [float(o) for o in offs[::4]],
            "median_luma_profile": [round(float(v), 3) for v in LP[::4]]}


# ------------------------------------------------------------------ start diamonds
def find_diamonds(rgb: np.ndarray, spaces: list[dict], r_ring: float) -> list[dict]:
    dkr = darkness(rgb)
    out = []
    for s in spaces:
        if not s.get("start"):
            continue
        cx, cy = s["px"]
        angs = np.deg2rad(np.arange(0.0, 360.0, 1.0))
        inn = sample(ndimage.uniform_filter(dkr, 3), cx + np.cos(angs) * (r_ring - 5), cy + np.sin(angs) * (r_ring - 5))
        out_ = sample(ndimage.uniform_filter(dkr, 3), cx + np.cos(angs) * (r_ring + 5), cy + np.sin(angs) * (r_ring + 5))
        score = np.minimum(inn, out_)
        k = int(np.argmax(score))
        gx, gy = cx + math.cos(angs[k]) * r_ring, cy + math.sin(angs[k]) * r_ring
        # template search on a 0.5 px grid: filled L1-diamond (a light digit inside r < 4 is
        # ignored) against a band just outside it (the ring stroke itself excluded)
        step, win, tmp = 0.5, 20.0, 14.0
        g = np.arange(-win, win + 1e-9, step)
        GX, GY = np.meshgrid(gx + g, gy + g)
        V = sample(dkr, GX, GY)
        RB = np.abs(np.hypot(GX - cx, GY - cy) - r_ring) < 3.0
        o = np.arange(-tmp, tmp + 1e-9, step)
        OX, OY = np.meshgrid(o, o)
        l1 = np.abs(OX) + np.abs(OY)
        nt = len(o)
        shifts = range(0, len(g) - nt + 1)
        best = None
        for h in np.arange(6.0, 11.01, 0.5):
            ins = (l1 <= h - 0.5) & (np.hypot(OX, OY) > 4.0)
            band = (l1 >= h + 1.5) & (l1 <= h + 4.0)
            for iy in shifts:
                for ix in shifts:
                    v = V[iy:iy + nt, ix:ix + nt]
                    outs = band & ~RB[iy:iy + nt, ix:ix + nt]
                    sc = float(v[ins].mean() - v[outs].mean())
                    if best is None or sc > best[0] + 1e-12:
                        best = (sc, float(GX[iy, ix] + tmp), float(GY[iy, ix] + tmp), float(h))
        sc, px, py, h = best
        out.append({"space": s["id"], "start": s["start"], "center_px": [round(px, 2), round(py, 2)],
                    "half_diagonal_px": float(h), "score": round(sc, 3),
                    "angle_deg": round(math.degrees(math.atan2(py - cy, px - cx)) % 360.0, 2),
                    "radial_px": round(math.hypot(px - cx, py - cy), 2)})
    return out
