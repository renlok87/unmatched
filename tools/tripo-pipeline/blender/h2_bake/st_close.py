"""Stage close: contact caps — the Tripo "по частям" segmentation cuts every part open along its contact line with
the neighbour (dress under the fist, armholes, collar, slits, greave tops, soles...). At rest the neighbour covers the
opening; in a pose the neighbour moves away and the opening shows a see-through hole (UE one-sided materials cull the
far inner wall). Measured on the first H2 build (verify 2026-09-29): 12 open loops on the dress, the fist open on the
belt side, shoulders, thighs, neck — seams-report distances 6.6–57 mm in the probe poses.

Per profile closure.contact_caps entry: the boundary loops of LP_<part> whose nearest other part (median distance of
the loop vertices to that part's surface) is `covered_by`, within max_median_mm, perimeter >= min_perimeter_cm
(exactly `expect` loops, default 1). Every such loop gets a separate cap (like the base-top caps of the retopo stage):

  boundary  the loop vertices themselves (duplicated, same positions: the cap meets the rim exactly; positional weights
            give both the same skinning, so the seam cannot open), ordered against the winding of the rim faces
            (candidate_build.closure.ordered_boundary_loops) -> the cap is wound like its part (normal out of the part)
  plane     Newell normal n of the ordered loop; the loop must project onto the plane as a simple polygon
  interior  triangular lattice (spacing_m) inside the projected polygon, >= 0.5 spacing from the rim; constrained
            Delaunay (mathutils.geometry.delaunay_2d_cdt)
  height    along n: harmonic (discrete Laplace, rim heights fixed) — or `fit`: quadratic height field fitted to the
            part's own surface around the loop (ring_m) plus the harmonic correction to the rim ("по форме пояса");
            then bulge_m * bubble (bubble = normalised solution of -Laplace = 1, 0 on the rim): negative = into the part
  tag       int face attribute h2_cap = 1-based cap index (uv/bake/textures stages; dropped before the FBX export)

Checks: every selected loop found; projected polygon simple; no flipped / degenerate cap triangles; caps hidden at rest
(ray test: area-weighted samples on the cap faces x Fibonacci directions on the front side, a ray that escapes the
whole figure (all LP parts incl. caps, bow and base) = visible; share <= rest_visibility.max_visible_share).
Reads work/lp.blend (retopo), writes work/lp_closed.blend and reports/close-report.json (+ the loop inventory of all
parts before and after)."""

import math
from pathlib import Path

import bmesh
import bpy
import numpy as np
from mathutils import Vector
from mathutils import geometry as G
from mathutils.bvhtree import BVHTree

from . import bl_util as U

CAP_ATTR = "h2_cap"


def loop_rows(obj, others, min_perimeter_m=0.0):
    """Boundary loops of obj (ordered against the rim winding) with perimeter, centre and nearest other part."""
    from candidate_build.closure import ordered_boundary_loops

    bm = bmesh.new()
    bm.from_mesh(obj.data)
    cap_layer = bm.faces.layers.int.get(CAP_ATTR)

    def not_cap_edge(e):
        return cap_layer is None or all(f[cap_layer] == 0 for f in e.link_faces)

    loops = ordered_boundary_loops(bm, select=not_cap_edge)
    rows = []
    for lp in loops:
        pts = np.array([tuple(v.co) for v in lp["verts"]])
        per = float(np.linalg.norm(np.roll(pts, -1, 0) - pts, axis=1).sum())
        if per < min_perimeter_m:
            continue
        near = []
        for name, bvh in others.items():
            d = np.array([bvh.find_nearest(Vector(p))[3] for p in pts])
            near.append((float(np.median(d)), name, float(np.percentile(d, 90))))
        near.sort()
        rows.append({"verts": [v.index for v in lp["verts"]], "co": pts, "perimeter_m": per, "closed": lp["closed"],
                     "centre_m": pts.mean(0), "nearest": near[:3]})
    bm.free()
    rows.sort(key=lambda r: (-r["perimeter_m"], tuple(np.round(r["centre_m"], 6))))
    return rows


def part_bvh(obj):
    return BVHTree.FromPolygons([Vector(c) for c in U.coords(obj.data)], [list(p.vertices) for p in obj.data.polygons])


def newell(pts):
    n = np.zeros(3)
    q = np.roll(pts, -1, 0)
    n[0] = ((pts[:, 1] - q[:, 1]) * (pts[:, 2] + q[:, 2])).sum()
    n[1] = ((pts[:, 2] - q[:, 2]) * (pts[:, 0] + q[:, 0])).sum()
    n[2] = ((pts[:, 0] - q[:, 0]) * (pts[:, 1] + q[:, 1])).sum()
    return n


def frame(n):
    n = n / np.linalg.norm(n)
    a = np.array([1.0, 0.0, 0.0]) if abs(n[0]) < 0.9 else np.array([0.0, 1.0, 0.0])
    e1 = np.cross(n, a)
    e1 /= np.linalg.norm(e1)
    e2 = np.cross(n, e1)
    return n, e1, e2


def segments_intersect(p, q):
    """Any proper intersection between non-adjacent edges of the closed polygon p (n x 2)?"""
    n = len(p)
    a, b = p, np.roll(p, -1, 0)

    def orient(x, y, z):
        return (y[..., 0] - x[..., 0]) * (z[..., 1] - x[..., 1]) - (y[..., 1] - x[..., 1]) * (z[..., 0] - x[..., 0])

    for i in range(n):
        j = np.arange(i + 2, n)
        if i == 0:
            j = j[j != n - 1]
        if len(j) == 0:
            continue
        o1 = orient(a[i], b[i], a[j])
        o2 = orient(a[i], b[i], b[j])
        o3 = orient(a[j], b[j], a[i][None, :])
        o4 = orient(a[j], b[j], b[i][None, :])
        if np.any((o1 * o2 < 0) & (o3 * o4 < 0)):
            return True
    return False


def inside_polygon(pts, poly):
    x, y = pts[:, 0][:, None], pts[:, 1][:, None]
    x1, y1 = poly[:, 0][None, :], poly[:, 1][None, :]
    x2, y2 = np.roll(poly[:, 0], -1)[None, :], np.roll(poly[:, 1], -1)[None, :]
    cond = (y1 > y) != (y2 > y)
    xin = x1 + (y - y1) * (x2 - x1) / np.where(y2 == y1, 1e-30, y2 - y1)
    return (np.sum(cond & (x < xin), axis=1) % 2) == 1


def dist_to_polygon(pts, poly):
    a, b = poly, np.roll(poly, -1, 0)
    ab = b - a
    ap = pts[:, None, :] - a[None, :, :]
    t = np.clip((ap * ab[None]).sum(-1) / np.maximum((ab * ab).sum(-1), 1e-30)[None], 0.0, 1.0)
    d = ap - t[..., None] * ab[None]
    return np.sqrt((d * d).sum(-1)).min(1)


def lattice(poly, spacing):
    lo, hi = poly.min(0), poly.max(0)
    rows = []
    dy = spacing * math.sqrt(3) / 2
    k = 0
    y = lo[1] + dy / 2
    while y < hi[1]:
        x0 = lo[0] + (spacing / 2 if k % 2 else 0.0) + spacing / 4
        xs = np.arange(x0, hi[0], spacing)
        rows.append(np.stack([xs, np.full_like(xs, y)], 1))
        y += dy
        k += 1
    pts = np.concatenate(rows) if rows else np.zeros((0, 2))
    if len(pts) == 0:
        return pts
    keep = inside_polygon(pts, poly)
    pts = pts[keep]
    if len(pts):
        pts = pts[dist_to_polygon(pts, poly) >= 0.5 * spacing]
    return pts


def laplacian(n, faces):
    L = np.zeros((n, n))
    for f in faces:
        for i in range(3):
            a, b = f[i], f[(i + 1) % 3]
            if L[a, b] == 0:
                L[a, b] = L[b, a] = -1.0
    L[np.diag_indices(n)] = -L.sum(1)
    return L


def fit_quadratic(uv, h, reg=1e-9):
    u, v = uv[:, 0], uv[:, 1]
    A = np.stack([np.ones_like(u), u, v, u * u, u * v, v * v], 1)
    coef = np.linalg.solve(A.T @ A + reg * np.eye(6), A.T @ h)
    return lambda q: np.stack([np.ones(len(q)), q[:, 0], q[:, 1], q[:, 0] ** 2, q[:, 0] * q[:, 1], q[:, 1] ** 2], 1) @ coef


def crossing_pairs(p):
    n = len(p)
    a, b = p, np.roll(p, -1, 0)

    def orient(x, y, z):
        return (y[..., 0] - x[..., 0]) * (z[..., 1] - x[..., 1]) - (y[..., 1] - x[..., 1]) * (z[..., 0] - x[..., 0])

    out = []
    for i in range(n):
        j = np.arange(i + 2, n)
        if i == 0:
            j = j[j != n - 1]
        if len(j) == 0:
            continue
        o1 = orient(a[i], b[i], a[j])
        o2 = orient(a[i], b[i], b[j])
        o3 = orient(a[j], b[j], a[i][None, :])
        o4 = orient(a[j], b[j], b[i][None, :])
        out.extend((i, int(k)) for k in j[(o1 * o2 < 0) & (o3 * o4 < 0)])
    return out


def untangle(uv, max_share):
    """2D layout of the rim for the triangulation only (the 3D rim stays exact): a local self-crossing of the
    projected rim (zig-zags of the decimated Tripo loop, a fold where the loop turns over the thigh) is removed by
    laying the vertices of the small sub-loop evenly on the chord that bypasses it. Returns (layout, moved) or
    (None, moved) when a sub-loop longer than max_share of the rim would have to be collapsed."""
    q = uv.copy()
    n = len(q)
    moved = set()
    for _ in range(4 * n):
        pairs = crossing_pairs(q)
        if not pairs:
            return q, moved
        i, k = min(pairs, key=lambda ik: (min(ik[1] - ik[0], n - (ik[1] - ik[0])), ik))
        span = k - i
        if span <= n - span:
            idx = [(i + t) % n for t in range(1, span + 1)]
            a, b = q[i].copy(), q[(k + 1) % n].copy()
        else:
            idx = [(k + t) % n for t in range(1, n - span + 1)]
            a, b = q[k].copy(), q[(i + 1) % n].copy()
        if len(idx) > max_share * n:
            return None, moved
        for t, j in enumerate(idx):
            q[j] = a + (b - a) * ((t + 1) / (len(idx) + 1))
            moved.add(j)
    return None, moved


def build_cap(obj, row, spec, cfg, cap_index):
    """Adds the cap faces to obj.data (bmesh), returns the cap record.

    Rim = the loop vertices (exact 3D positions). Newell plane frame (n, e1, e2); the rim is laid out in the plane
    (local self-crossings of the projection untangled for the triangulation only); interior = triangular lattice
    (>= 0.5 spacing from the rim) + constrained Delaunay. Heights along n: harmonic extension of the rim heights (or
    the `fit` quadric of the part's surface around the loop + harmonic correction to the rim), plus bulge * bubble."""
    P = row["co"]
    nb = len(P)
    N = newell(P)
    n, e1, e2 = frame(N)
    c = P.mean(0)
    uv_b = np.stack([(P - c) @ e1, (P - c) @ e2], 1)
    h_b = (P - c) @ n
    rec = {"name": spec["name"], "part": spec["part"], "covered_by": spec["covered_by"], "cap_index": cap_index,
           "loop_vertices": nb, "perimeter_cm": U.r(row["perimeter_m"] * 100, 3), "centre_cm": U.rv(row["centre_m"] * 100, 3),
           "loop_median_to_cover_mm": U.r(next(d for d, nm, _p in row["nearest"] if nm == spec["covered_by"]) * 1000, 3)
           if spec.get("covered_by") else None,
           "projected_area_cm2": U.r(0.5 * np.linalg.norm(N) * 1e4, 3), "normal": U.rv(n, 4),
           "rim_height_range_mm": U.r((h_b.max() - h_b.min()) * 1000, 3)}
    layout, moved = untangle(uv_b, float(cfg.get("untangle_max_share", 0.2)))
    rec["rim_layout_untangled_vertices"] = len(moved)
    if layout is None:
        rec["error"] = "projected rim crosses itself beyond a local fold (untangle_max_share)"
        return rec
    spacing = float(spec.get("spacing_m", cfg.get("spacing_m", 0.004)))
    inner = lattice(layout, spacing)
    cdt_in = [Vector((float(p[0]), float(p[1]))) for p in np.vstack([layout, inner])]
    out_v, _e, out_f, orig_v, _oe, _of = G.delaunay_2d_cdt(cdt_in, [], [list(range(nb))], 1, 1e-12, True)
    if len(out_v) != len(cdt_in) or any(len(o) != 1 for o in orig_v):
        rec["error"] = "CDT merged or added vertices (%d -> %d)" % (len(cdt_in), len(out_v))
        return rec
    remap = np.array([o[0] for o in orig_v])
    uv_all = np.vstack([layout, inner])
    faces = []
    for f in out_f:
        if len(f) != 3:
            raise RuntimeError("CDT returned a non-triangle")
        tri = [int(remap[i]) for i in f]
        p0, p1, p2 = uv_all[tri]
        cr = (p1[0] - p0[0]) * (p2[1] - p0[1]) - (p1[1] - p0[1]) * (p2[0] - p0[0])
        faces.append(tri if cr > 0 else [tri[0], tri[2], tri[1]])
    nv = len(uv_all)
    L = laplacian(nv, faces)
    I = np.arange(nb, nv)
    B = np.arange(nb)
    LII, LIB = L[np.ix_(I, I)], L[np.ix_(I, B)]
    shape = spec.get("shape", "harmonic")
    h = np.zeros(nv)
    h[:nb] = h_b
    fit_info = None
    if len(I) == 0:
        pass
    elif shape == "fit":
        from mathutils.kdtree import KDTree
        ring_m = float(spec.get("ring_m", cfg.get("ring_m", 0.008)))
        co = U.coords(obj.data)
        kd = KDTree(nb)
        for i, p in enumerate(P):
            kd.insert(Vector(p), i)
        kd.balance()
        near = np.array([kd.find(Vector(p))[2] <= ring_m for p in co])
        sel = co[near]
        q_uv = np.stack([(sel - c) @ e1, (sel - c) @ e2], 1)
        q_h = (sel - c) @ n
        Q = fit_quadratic(q_uv, q_h)
        base = Q(uv_all)
        corr = np.zeros(nv)
        corr[:nb] = h_b - base[:nb]
        corr[I] = np.linalg.solve(LII, -LIB @ corr[:nb])
        h = base + corr
        fit_info = {"ring_m": ring_m, "ring_vertices": int(near.sum()),
                    "residual_rms_mm": U.r(np.sqrt(((q_h - Q(q_uv)) ** 2).mean()) * 1000, 4)}
    elif shape == "harmonic":
        h[I] = np.linalg.solve(LII, -LIB @ h_b)
    else:
        raise ValueError("closure cap %s: unknown shape %r" % (spec["name"], shape))
    bulge = float(spec.get("bulge_m", cfg.get("bulge_m", 0.0)))
    if bulge and len(I):
        phi = np.zeros(nv)
        phi[I] = np.linalg.solve(LII, np.ones(len(I)))
        phi /= max(phi.max(), 1e-12)
        h = h + bulge * phi
    h[:nb] = h_b
    X = c[None, :] + uv_all[:, :1] * e1[None, :] + uv_all[:, 1:2] * e2[None, :] + h[:, None] * n[None, :]
    X[:nb] = P
    bm = bmesh.new()
    bm.from_mesh(obj.data)
    layer = bm.faces.layers.int.get(CAP_ATTR) or bm.faces.layers.int.new(CAP_ATTR)
    new_v = [bm.verts.new(tuple(x)) for x in X]
    tri_area, away_area, rim_tris = [], 0.0, 0
    for tri in faces:
        f = bm.faces.new([new_v[i] for i in tri])
        f.smooth = True
        f[layer] = cap_index
        f.normal_update()
        a = f.calc_area()
        tri_area.append(a)
        if f.normal.dot(Vector(n)) <= 0.0:
            away_area += a
        rim_tris += int(all(i < nb for i in tri))
    bm.to_mesh(obj.data)
    bm.free()
    obj.data.update()
    tri_area = np.array(tri_area)
    rec.update({"shape": shape, "fit": fit_info, "bulge_m": bulge, "spacing_m": spacing,
                "interior_vertices": int(len(I)), "triangles": len(faces), "rim_only_triangles": rim_tris,
                "cap_area_cm2": U.r(tri_area.sum() * 1e4, 3),
                "facing_away_area_share": U.r(away_area / max(tri_area.sum(), 1e-20), 5),
                "degenerate_triangles": int((tri_area < float(cfg.get("degenerate_area_m2", 1e-10))).sum()),
                "interior_height_mm": {"min": U.r(h[I].min() * 1000, 3) if len(I) else None,
                                       "max": U.r(h[I].max() * 1000, 3) if len(I) else None,
                                       "rim_min": U.r(h_b.min() * 1000, 3), "rim_max": U.r(h_b.max() * 1000, 3),
                                       "note": "along the cap normal from the rim centroid"}})
    return rec


def blobs(mask):
    """Sizes of the 8-connected components of a boolean image (few pixels: plain BFS)."""
    ys, xs = np.nonzero(mask)
    seen = set()
    sizes = []
    pix = set(zip(ys.tolist(), xs.tolist()))
    for start in zip(ys.tolist(), xs.tolist()):
        if start in seen:
            continue
        stack, n = [start], 0
        seen.add(start)
        while stack:
            y, x = stack.pop()
            n += 1
            for dy in (-1, 0, 1):
                for dx in (-1, 0, 1):
                    q = (y + dy, x + dx)
                    if q in pix and q not in seen:
                        seen.add(q)
                        stack.append(q)
        sizes.append(n)
    return sorted(sizes, reverse=True)


def rest_visibility(objs, names, cap_names, vcfg):
    """Ray-cast views of the rest figure (all LP parts) with and without the caps. A cap pixel whose ray, without the
    caps, would meet a FRONT face of a real part = the cap hides surface that is visible at rest (a regression); a cap
    pixel that would otherwise meet nothing or a BACK face = the cap fills a see-through gap (an improvement)."""
    from . import raycam

    polys, labels, polys_nc, labels_nc, pts = [], [], [], [], []
    for pi, name in enumerate(names):
        obj = objs[name]
        co = U.coords(obj.data)
        pts.append(co)
        attr = obj.data.attributes.get(CAP_ATTR)
        ids = np.zeros(len(obj.data.polygons), np.int64)
        if attr is not None:
            attr.data.foreach_get("value", ids)
        for p, cid in zip(obj.data.polygons, ids):
            poly = [co[i] for i in p.vertices]
            lab = pi * 1000 + int(cid)
            polys.append(poly)
            labels.append(lab)
            if cid == 0:
                polys_nc.append(poly)
                labels_nc.append(lab)
    bvh, lab = raycam.build(polys, labels)
    bvh_nc, lab_nc = raycam.build(polys_nc, labels_nc)
    pts = np.vstack(pts)
    pitch = float(vcfg.get("pitch_m", 0.001))
    views = vcfg.get("views") or raycam.DEFAULT_VIEWS
    per = {}
    totals = {"figure_px": 0, "cap_px": 0, "covers_front_px": 0, "fills_gap_px": 0, "cap_backside_px": 0,
              "largest_covers_front_blob_px": 0, "backface_px_without_caps": 0, "backface_px_with_caps": 0}
    per_view = {}
    for vname, az, el in views:
        d = raycam.view_dir(az, el)
        k1, l1 = raycam.render(bvh, lab, d, pts, pitch)
        k0, _l0 = raycam.render(bvh_nc, lab_nc, d, pts, pitch)
        capm = (k1 > 0) & (l1 % 1000 > 0)
        cover = capm & (k1 == 1) & (k0 == 1)
        totals["figure_px"] += int((k1 > 0).sum())
        totals["cap_px"] += int(capm.sum())
        totals["covers_front_px"] += int(cover.sum())
        totals["fills_gap_px"] += int((capm & (k1 == 1) & (k0 != 1)).sum())
        totals["cap_backside_px"] += int((capm & (k1 == 2)).sum())
        totals["backface_px_without_caps"] += int((k0 == 2).sum())
        totals["backface_px_with_caps"] += int((k1 == 2).sum())
        view_blobs = blobs(cover)
        totals["largest_covers_front_blob_px"] = max(totals["largest_covers_front_blob_px"], view_blobs[0] if view_blobs else 0)
        per_view[vname] = {"cap_px": int(capm.sum()), "covers_front_px": int(cover.sum()),
                           "covers_front_blobs_top3": view_blobs[:3], "cap_backside_px": int((capm & (k1 == 2)).sum()),
                           "backface_px_without_with_caps": [int((k0 == 2).sum()), int((k1 == 2).sum())]}
        for key in np.unique(l1[capm]):
            name = cap_names.get(int(key), str(int(key)))
            r = per.setdefault(name, {"cap_px": 0, "covers_front_px": 0, "fills_gap_px": 0, "cap_backside_px": 0,
                                      "largest_covers_front_blob_px": 0, "worst_view": None})
            mk = capm & (l1 == key)
            cvm = mk & (k1 == 1) & (k0 == 1)
            cv = int(cvm.sum())
            r["cap_px"] += int(mk.sum())
            r["covers_front_px"] += cv
            r["fills_gap_px"] += int((mk & (k1 == 1) & (k0 != 1)).sum())
            r["cap_backside_px"] += int((mk & (k1 == 2)).sum())
            b = blobs(cvm)
            if b and b[0] > r["largest_covers_front_blob_px"]:
                r["largest_covers_front_blob_px"], r["worst_view"] = b[0], vname
    return {"pitch_m": pitch, "views": [v[0] for v in views], "totals": totals, "per_cap": per, "per_view": per_view}


def inventory(objs, bvhs, min_perimeter_m, closed=None):
    """Rim loops of every part (perimeter >= min); closed = {(part, frozenset(vertex indices)): cap name}."""
    out = {}
    for name, obj in objs.items():
        others = {k: b for k, b in bvhs.items() if k != name}
        rows = loop_rows(obj, others, min_perimeter_m)
        out[name] = [{"perimeter_cm": U.r(r["perimeter_m"] * 100, 2), "centre_cm": U.rv(r["centre_m"] * 100, 2),
                      "nearest": [[nm, U.r(d * 1000, 2)] for d, nm, _p in r["nearest"][:2]],
                      "closed_by_cap": (closed or {}).get((name, frozenset(r["verts"])))} for r in rows]
    return out


def run(params, profile):
    run_dir = Path(params["run_dir"])
    cfg = profile.get("closure", {})
    bpy.ops.wm.open_mainfile(filepath=str(run_dir / "work" / "lp.blend"))
    names = sorted(profile["parts"], key=U.part_key)
    objs = {n: bpy.data.objects["LP_" + n] for n in names}
    bvhs = {n: part_bvh(o) for n, o in objs.items()}
    min_inv = float(cfg.get("inventory_min_perimeter_cm", 1.0)) / 100.0
    before = inventory(objs, bvhs, min_inv)
    caps, problems = [], []
    cap_index_of = {}
    counters = {}
    closed = {}
    for spec in cfg.get("contact_caps", []):
        obj = objs[spec["part"]]
        others = {k: b for k, b in bvhs.items() if k != spec["part"]}
        rows = loop_rows(obj, others, float(spec.get("min_perimeter_cm", cfg.get("min_perimeter_cm", 3.0))) / 100.0)
        tol = float(spec.get("max_median_mm", cfg.get("max_median_mm", 1.0))) / 1000.0
        chosen = [r for r in rows if r["nearest"][0][1] == spec["covered_by"] and r["nearest"][0][0] <= tol]
        if len(chosen) != int(spec.get("expect", 1)):
            problems.append("%s: %d loops match (expected %s)" % (spec["name"], len(chosen), spec.get("expect", 1)))
            continue
        for k, row in enumerate(chosen):
            counters[spec["part"]] = counters.get(spec["part"], 0) + 1
            idx = counters[spec["part"]]
            rec = build_cap(obj, row, spec, cfg, idx)
            if len(chosen) > 1:
                rec["name"] = "%s_%d" % (spec["name"], k + 1)
            if "error" in rec:
                problems.append("%s: %s" % (rec["name"], rec["error"]))
            cap_index_of[(obj.name, idx)] = rec["name"]
            if "error" not in rec:
                closed[(spec["part"], frozenset(row["verts"]))] = rec["name"]
            caps.append(rec)
    for spec in cfg.get("rebuild_retopo_caps", []):
        # the base-top holes: the retopo stage closed them with convex-hull fans 0.3 mm below the rim; from above at a
        # grazing angle the ring between rim and fan showed the underside of the top (see-through arcs where a foot
        # lifts, seams ray test 2026-09-29). The fans are removed and every hole loop in the z band gets a cap on the
        # exact rim, like the contact caps (visible by design: stone from the rim).
        part = spec["part"]
        obj = objs[part]
        bm = bmesh.new()
        bm.from_mesh(obj.data)
        bm.faces.ensure_lookup_table()
        # vertex-connected components (Tripo bow-tie triangles touch the main mesh by a vertex only); the retopo
        # fans are the flat components that share no vertex with the main mesh
        parent = {}

        def find(x):
            while parent.setdefault(x, x) != x:
                parent[x] = parent[parent[x]]
                x = parent[x]
            return x

        for f in bm.faces:
            vs = [v.index for v in f.verts]
            for v in vs[1:]:
                ra, rb = find(vs[0]), find(v)
                if ra != rb:
                    parent[max(ra, rb)] = min(ra, rb)
        groups = {}
        for f in bm.faces:
            groups.setdefault(find(f.verts[0].index), []).append(f)
        comps = sorted(groups.values(), key=lambda c: (-len(c), min(f.index for f in c)))
        comps = [comps[0]] + [c for c in comps[1:]
                              if max(v.co.z for f in c for v in f.verts) - min(v.co.z for f in c for v in f.verts) < 1e-6]
        removed = [len(c) for c in comps[1:]]
        doomed = [f for c in comps[1:] for f in c]
        bmesh.ops.delete(bm, geom=doomed, context="FACES")
        bm.to_mesh(obj.data)
        bm.free()
        obj.data.update()
        z0, z1 = spec["z_band_m"]
        others = {k: bv for k, bv in bvhs.items() if k != part}
        rows = [r for r in loop_rows(obj, others, float(spec.get("min_perimeter_cm", 0.0)) / 100.0)
                if z0 <= r["co"][:, 2].min() and r["co"][:, 2].max() <= z1]
        if "expect" in spec and len(rows) != int(spec["expect"]):
            problems.append("%s: %d hole loops in the z band (expected %s)" % (spec["name"], len(rows), spec["expect"]))
        for k, row in enumerate(rows, 1):
            counters[part] = counters.get(part, 0) + 1
            idx = counters[part]
            cspec = dict(spec, covered_by=None, name="%s_%d" % (spec["name"], k))
            rec = build_cap(obj, row, cspec, cfg, idx)
            rec["visible_by_design"] = True
            rec["replaces"] = "retopo convex-hull fan caps (%d components, %d faces removed)" % (len(removed), sum(removed))
            if "error" in rec:
                problems.append("%s: %s" % (rec["name"], rec["error"]))
            else:
                closed[(part, frozenset(row["verts"]))] = rec["name"]
            cap_index_of[(obj.name, idx)] = rec["name"]
            caps.append(rec)
    cap_names = {names.index(obj_name[3:]) * 1000 + cid: nm for (obj_name, cid), nm in cap_index_of.items()}
    vis = rest_visibility(objs, names, cap_names, cfg.get("rest_visibility", {}))
    for rec in caps:
        rec["rest_visibility"] = vis["per_cap"].get(rec["name"], {"cap_px": 0, "covers_front_px": 0, "fills_gap_px": 0})
    bvhs_after = {n: part_bvh(o) for n, o in objs.items()}
    after = inventory(objs, bvhs_after, min_inv, closed)
    open_after = {n: [r for r in rows if not r["closed_by_cap"]] for n, rows in after.items()}
    bpy.ops.wm.save_as_mainfile(filepath=str(run_dir / "work" / "lp_closed.blend"), compress=False)
    tris = {n: U.triangles(o.data) for n, o in objs.items()}
    groups = {}
    for n in names:
        groups[profile["parts"][n]["mesh"]] = groups.get(profile["parts"][n]["mesh"], 0) + tris[n]
    vcfg = cfg.get("rest_visibility", {})
    max_cover = float(vcfg.get("max_covers_front_share", 1e-4))
    max_blob = int(vcfg.get("max_covers_front_blob_px", 9))
    fig_px = max(vis["totals"]["figure_px"], 1)
    contact = [r for r in caps if not r.get("visible_by_design")]
    checks = {
        "all_cap_loops_found_and_built": {"passed": not problems, "measured": problems or "all", "expected": "no problems"},
        "no_degenerate_or_inverted_cap_triangles": {
            "passed": all(r.get("degenerate_triangles", 1) == 0
                          and r.get("facing_away_area_share", 1) <= float(cfg.get("max_facing_away_share", 0.02)) for r in caps),
            "measured": {r["name"]: [r.get("degenerate_triangles"), r.get("facing_away_area_share")] for r in caps},
            "expected": "[0 degenerate, area share of cap triangles facing away from the cap normal <= %s]"
                        % cfg.get("max_facing_away_share", 0.02),
            "note": "triangles along rim zig-zags / local folds of the decimated Tripo loop (1-3 mm) may face away"},
        "caps_hidden_at_rest": {
            "passed": sum(r["rest_visibility"]["covers_front_px"] for r in contact) <= max_cover * fig_px
                      and max([r["rest_visibility"].get("largest_covers_front_blob_px", 0) for r in contact] + [0]) <= max_blob,
            "measured": {"covers_front_px": sum(r["rest_visibility"]["covers_front_px"] for r in contact),
                         "figure_px": vis["totals"]["figure_px"],
                         "largest_blob_px": max([r["rest_visibility"].get("largest_covers_front_blob_px", 0) for r in contact] + [0]),
                         "per_cap": {r["name"]: [r["rest_visibility"]["covers_front_px"],
                                                 r["rest_visibility"].get("largest_covers_front_blob_px", 0)] for r in contact}},
            "expected": "front-facing cap pixels that hide a real front face at rest: <= %s of the figure pixels and no "
                        "8-connected blob > %d px (%d views, %.1f mm pitch; a back-facing cap pixel is culled in UE)"
                        % (max_cover, max_blob, len(vis["views"]), vis["pitch_m"] * 1000)},
    }
    report = {"stage": "close", "caps": caps, "cap_triangles": sum(r.get("triangles", 0) for r in contact),
              "cap_area_cm2": U.r(sum(r.get("cap_area_cm2", 0) for r in contact), 3),
              "contact_caps": len(contact), "tagged_retopo_caps": len(caps) - len(contact),
              "triangles_by_part": tris, "triangles_by_mesh": groups,
              "triangles_figure": groups.get("body", 0) + groups.get("weapon", 0),
              "rest_visibility": vis, "loops_before": before, "loops_after": after,
              "open_loops_after": {"count": sum(len(v) for v in open_after.values()),
                                   "count_before": sum(len(v) for v in before.values()),
                                   "closed_by_caps": len(closed)}, "checks": checks,
              "passed": all(c["passed"] for c in checks.values()), "status": "измерено",
              "note": "loops_* = rim loops (perimeter >= inventory_min_perimeter_cm) of every part, nearest other part by "
                      "median distance; closed_by_cap = the cap that closes the loop (cap boundaries are not rim loops); "
                      "open loops left are judged in poses by the seams stage"}
    U.write_json(run_dir / "reports" / "close-report.json", report)
    if not report["passed"]:
        raise RuntimeError("close checks failed: %s" % [k for k, c in checks.items() if not c["passed"]])
