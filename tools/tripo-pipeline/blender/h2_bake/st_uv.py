"""Stage uv: one atlas for the whole figure + base.

Per part: seam-based charts (charts.py: surface Voronoi charts, MINIMUM_STRETCH unwrap, split of folded /
overlapping / stretched charts). Every UV island is then scaled so that its UV area is proportional to its 3D area
(equal texel density everywhere) times priority^2 (face, hands, weapon denser; the plain stone base sparser). All
parts are packed together (rotation allowed, concave shapes) with a fractional margin; the gap between islands is
then MEASURED on a 4K raster (discrete Voronoi of island pixels: gap of a pair of adjacent pixels with different
nearest islands = distance_a + distance_b) and must be >= uv.min_gap_px; overlapping UV pixels must be 0.
Caps (faces with the int attribute h2_cap, close stage: contact caps and the base-top caps) get their own texel
priority (closure.texel_priority) and are texture-filled by the textures stage from their rim, not by the bake: for
every cap vertex the uv stage writes a linear combination of rim samples (boundary vertex -> the rim faces of the
coincident / nearest rim vertex, sampled a little inside each face; interior vertex -> harmonic weights of the cap's
boundary vertices), work/uv/caps.npz, and the cap raster work/uv/cap_ids.npy (part index * 1000 + cap id, 0 = none).
Contact footprints (closure.contact_caps[].repaint_footprint): faces of a part hidden at rest under the covering part
near the capped loop get the same rim transfer for BC/RM/AO (their normal map stays baked), work/uv/footprints.npz.
Reads work/lp_closed.blend. Writes work/lp_uv.blend, work/uv/{island_ids,part_ids,base_band,cap_ids}.npy,
work/uv/{caps,footprints}.npz, reports/uv-report.json, preview/uv-layout-1024.png."""

import json
import math
from pathlib import Path

import bmesh
import bpy
import numpy as np

from mathutils.kdtree import KDTree

from . import bl_util as U
from . import charts

CAP_ATTR = "h2_cap"


def uv_islands(bm, uv_layer):
    """Face islands connected through edges whose two loops share UVs on both ends (no seam)."""
    bm.faces.ensure_lookup_table()
    parent = list(range(len(bm.faces)))

    def find(i):
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    for e in bm.edges:
        lf = e.link_loops
        if len(lf) != 2:
            continue
        l1, l2 = lf
        m1 = {l1.vert.index: l1[uv_layer].uv, l1.link_loop_next.vert.index: l1.link_loop_next[uv_layer].uv}
        m2 = {l2.vert.index: l2[uv_layer].uv, l2.link_loop_next.vert.index: l2.link_loop_next[uv_layer].uv}
        if m1.keys() == m2.keys() and all((m1[k] - m2[k]).length < 1e-6 for k in m1):
            ra, rb = find(l1.face.index), find(l2.face.index)
            if ra != rb:
                parent[ra] = rb
    groups = {}
    for f in bm.faces:
        groups.setdefault(find(f.index), []).append(f)
    return [groups[k] for k in sorted(groups)]


def box_contains(box, p):
    return all(box[0][k] <= p[k] <= box[1][k] for k in range(3))


def normalise_islands(obj, factor_default, regions, cap_factor=None):
    me = obj.data
    bm = bmesh.new()
    bm.from_mesh(me)
    uv_layer = bm.loops.layers.uv.active
    cap_layer = bm.faces.layers.int.get(CAP_ATTR)
    islands = uv_islands(bm, uv_layer)
    info = []
    for faces in islands:
        a3 = sum(f.calc_area() for f in faces)
        auv = 0.0
        cen = np.zeros(2)
        c3 = np.zeros(3)
        for f in faces:
            uvs = [l[uv_layer].uv for l in f.loops]
            s = 0.0
            for k in range(1, len(uvs) - 1):
                s += 0.5 * ((uvs[k].x - uvs[0].x) * (uvs[k + 1].y - uvs[0].y) - (uvs[k + 1].x - uvs[0].x) * (uvs[k].y - uvs[0].y))
            auv += abs(s)
            c3 += np.array(f.calc_center_median()) * f.calc_area()
        c3 /= max(a3, 1e-20)
        loops = [l for f in faces for l in f.loops]
        uvarr = np.array([[l[uv_layer].uv.x, l[uv_layer].uv.y] for l in loops])
        cen = uvarr.mean(0)
        factor = factor_default
        region = None
        for reg in regions:
            if box_contains(reg["box_m"], c3):
                factor, region = reg["factor"], reg["name"]
        if cap_factor is not None and cap_layer is not None and all(f[cap_layer] > 0 for f in faces):
            factor, region = min(cap_factor, factor_default), "cap"
        k = math.sqrt(a3 / auv) * factor if auv > 1e-20 else 0.0
        for l in loops:
            uv = l[uv_layer].uv
            l[uv_layer].uv = ((uv.x - cen[0]) * k + cen[0], (uv.y - cen[1]) * k + cen[1])
        info.append({"faces": len(faces), "area_m2": a3, "factor": factor, "region": region})
    bm.to_mesh(me)
    bm.free()
    me.update()
    return info


def cap_transfer(names, objs, size, frac, rings=None):
    """Rim-sample weights of every cap vertex (see the module docstring) and the cap triangles in atlas pixels.
    rings: {(part, cap index): [d_in, d_out, k]} — the boundary vertices of that cap take their samples from the k
    nearest part vertices lying d_in..d_out (m) from the cap's loop instead of the faces at the loop: the Tripo texture
    right at a contact line carries the neighbour's colour (the belt under the fist is skin-toned, verify frames)."""
    rings = rings or {}
    tri_px, tri_v, tri_cap, samples, rows, cols, vals, meta = [], [], [], [], [], [], [], []
    vbase = 0
    for pi, (n, obj) in enumerate(zip(names, objs)):
        bm = bmesh.new()
        bm.from_mesh(obj.data)
        layer = bm.faces.layers.int.get(CAP_ATTR)
        if layer is None:
            bm.free()
            continue
        uvl = bm.loops.layers.uv.active
        bm.verts.ensure_lookup_table()
        caps = {}
        for f in bm.faces:
            if f[layer] > 0:
                caps.setdefault(f[layer], []).append(f)
        rim = [v for v in bm.verts if v.link_faces and all(f[layer] == 0 for f in v.link_faces)]
        kd = KDTree(len(rim))
        for i, v in enumerate(rim):
            kd.insert(v.co, i)
        kd.balance()
        for cid in sorted(caps):
            faces = caps[cid]
            verts = sorted({v.index for f in faces for v in f.verts})
            local = {vi: k for k, vi in enumerate(verts)}
            ring = rings.get((n, cid))
            ring_kd = None
            if ring:
                loop_kd = KDTree(len(verts))
                for vi in verts:
                    loop_kd.insert(bm.verts[vi].co, vi)
                loop_kd.balance()
                cand = [v for v in rim if ring[0] <= loop_kd.find(v.co)[2] <= ring[1]]
                ring_kd = KDTree(max(len(cand), 1))
                for i, v in enumerate(cand):
                    ring_kd.insert(v.co, i)
                ring_kd.balance()
            bnd = set()
            edges = set()
            for f in faces:
                for e in f.edges:
                    a, b = sorted(v.index for v in e.verts)
                    edges.add((local[a], local[b]))
                    if sum(1 for g in e.link_faces if g[layer] == cid) == 1:
                        bnd.update((a, b))
            B = [local[v] for v in verts if v in bnd]
            I = [local[v] for v in verts if v not in bnd]
            weights = {}
            rim_dist = []
            for b in B:
                co = bm.verts[verts[b]].co
                _c, ri, dist = kd.find(co)
                rim_dist.append(dist)
                sources = [rim[ri]]
                if ring_kd is not None and len(cand):
                    sources = [cand[i] for _c2, i, _d in ring_kd.find_n(co, int(ring[2]))]
                row = []
                for rv in sources:
                    fs = sorted(rv.link_faces, key=lambda f: f.index)
                    for f in fs:
                        lr = next(l for l in f.loops if l.vert.index == rv.index)
                        u0 = np.array(lr[uvl].uv)
                        cen = np.mean([np.array(l[uvl].uv) for l in f.loops], 0)
                        samples.append((u0 + frac * (cen - u0)) * size)
                        row.append((len(samples) - 1, 1.0 / (len(fs) * len(sources))))
                weights[b] = row
            if I:
                L = np.zeros((len(verts), len(verts)))
                for a, b in edges:
                    L[a, b] = L[b, a] = -1.0
                L[np.diag_indices(len(verts))] = -L.sum(1)
                X = np.linalg.solve(L[np.ix_(I, I)], -L[np.ix_(I, B)])
                for r, i in enumerate(I):
                    acc = {}
                    for c, b in enumerate(B):
                        if X[r, c] < 1e-5:
                            continue
                        for sidx, w in weights[b]:
                            acc[sidx] = acc.get(sidx, 0.0) + X[r, c] * w
                    tot = sum(acc.values())
                    weights[i] = [(k, v / tot) for k, v in sorted(acc.items())]
            for k in range(len(verts)):
                for sidx, w in weights[k]:
                    rows.append(vbase + k)
                    cols.append(sidx)
                    vals.append(w)
            for f in faces:
                corners = [(np.array(l[uvl].uv) * size, local[l.vert.index]) for l in f.loops]
                for k in range(1, len(corners) - 1):
                    tri = (corners[0], corners[k], corners[k + 1])
                    tri_px.append([t[0] for t in tri])
                    tri_v.append([vbase + t[1] for t in tri])
                    tri_cap.append(pi * 1000 + cid)
            meta.append({"part": n, "cap": int(cid), "label": pi * 1000 + int(cid), "vertices": len(verts),
                         "rim_ring_m": ring,
                         "boundary_vertices": len(B), "faces": len(faces),
                         "rim_match_max_mm": U.r(max(rim_dist) * 1000, 4) if rim_dist else None})
            vbase += len(verts)
        bm.free()
    return ({"tri_px": np.array(tri_px, np.float64).reshape(-1, 3, 2), "tri_v": np.array(tri_v, np.int64).reshape(-1, 3),
             "tri_cap": np.array(tri_cap, np.int64), "samp_px": np.array(samples, np.float64).reshape(-1, 2),
             "w_rows": np.array(rows, np.int64), "w_cols": np.array(cols, np.int64), "w_vals": np.array(vals, np.float64),
             "n_vertices": np.array(vbase, np.int64)}, meta)


def footprint_transfer(names, objs, size, frac, close_report, specs):
    """Contact footprints (verify 2026-09-29: a pale smear on the belt where the fist was): faces of `part` near the
    capped loop that are hidden at rest under `covered_by` — rays from the face centre over the normal hemisphere
    (64-direction Fibonacci set, d . n > 0.2) against the whole figure: at most max_escape_share escape and at least
    min_cover_share end on the covering part — keep their bake (normal map) but get BC / RM / AO from the visible
    surface around them: the Tripo texture there was never seen by the generator (skin tone under the fist).
    Same transfer as the caps: boundary vertex -> samples of the adjacent visible faces, interior -> harmonic."""
    from mathutils import Vector
    from mathutils.bvhtree import BVHTree

    tri_px, tri_v, tri_lab, samples, rows, cols, vals, meta = [], [], [], [], [], [], [], []
    vbase = 0
    k = np.arange(64) + 0.5
    phi = np.arccos(1 - 2 * k / 64)
    th = math.pi * (1 + 5 ** 0.5) * k
    sphere = np.stack([np.cos(th) * np.sin(phi), np.sin(th) * np.sin(phi), np.cos(phi)], 1)
    by_name = {n: o for n, o in zip(names, objs)}
    all_v, all_p, owner = [], [], []
    for n, o in zip(names, objs):
        off = len(all_v)
        all_v.extend(v.co.copy() for v in o.data.vertices)
        for p in o.data.polygons:
            all_p.append([off + i for i in p.vertices])
            owner.append(n)
    fig_bvh = BVHTree.FromPolygons(all_v, all_p)
    for spec in specs:
        fp = spec.get("repaint_footprint")
        if not fp:
            continue
        rec = next((c for c in close_report["caps"] if c["name"] == spec["name"]), None)
        if rec is None or "error" in rec:
            continue
        pi = names.index(spec["part"])
        obj = by_name[spec["part"]]
        bm = bmesh.new()
        bm.from_mesh(obj.data)
        layer = bm.faces.layers.int.get(CAP_ATTR)
        uvl = bm.loops.layers.uv.active
        bm.verts.ensure_lookup_table()
        bm.faces.ensure_lookup_table()
        loop_pts = sorted({tuple(v.co) for f in bm.faces if f[layer] == rec["cap_index"] for v in f.verts})
        kd = KDTree(len(loop_pts))
        for i, c in enumerate(loop_pts):
            kd.insert(c, i)
        kd.balance()
        near = float(fp.get("max_distance_m", 0.02))
        max_ray = float(fp.get("max_ray_m", 0.1))
        esc_max = float(fp.get("max_escape_share", 0.1))
        cov_min = float(fp.get("min_cover_share", 0.4))
        hidden = set()
        for f in bm.faces:
            if f[layer] != 0:
                continue
            c = f.calc_center_median()
            if kd.find(c)[2] > near:
                continue
            n = np.array(f.normal)
            dirs = sphere[sphere @ n > 0.2]
            esc = cov_hits = 0
            for d in dirs:
                hit = fig_bvh.ray_cast(c + f.normal * 1e-5, Vector(d), max_ray)
                if hit[0] is None:
                    esc += 1
                elif owner[hit[2]] == spec["covered_by"]:
                    cov_hits += 1
            if esc <= esc_max * len(dirs) and cov_hits >= cov_min * len(dirs):
                hidden.add(f.index)
        faces = [bm.faces[i] for i in sorted(hidden)]
        if not faces:
            bm.free()
            meta.append({"name": spec["name"], "part": spec["part"], "faces": 0})
            continue
        verts = sorted({v.index for f in faces for v in f.verts})
        local = {vi: j for j, vi in enumerate(verts)}
        bnd = sorted(vi for vi in verts if any(g.index not in hidden and g[layer] == 0 for g in bm.verts[vi].link_faces))
        bset = set(bnd)
        B = [local[v] for v in bnd]
        I = [local[v] for v in verts if v not in bset]
        weights = {}
        for b in bnd:
            fs = sorted((g for g in bm.verts[b].link_faces if g.index not in hidden and g[layer] == 0), key=lambda g: g.index)
            row = []
            for g in fs:
                lr = next(l for l in g.loops if l.vert.index == b)
                u0 = np.array(lr[uvl].uv)
                cen = np.mean([np.array(l[uvl].uv) for l in g.loops], 0)
                samples.append((u0 + frac * (cen - u0)) * size)
                row.append((len(samples) - 1, 1.0 / len(fs)))
            weights[local[b]] = row
        dropped = 0
        if I:
            edges = set()
            for f in faces:
                for e in f.edges:
                    a, b2 = sorted(v.index for v in e.verts)
                    edges.add((local[a], local[b2]))
            L = np.zeros((len(verts), len(verts)))
            for a, b2 in edges:
                L[a, b2] = L[b2, a] = -1.0
            L[np.diag_indices(len(verts))] = -L.sum(1)
            LII = L[np.ix_(I, I)]
            reach = np.abs(L[np.ix_(I, B)]).sum(1) > 0
            # interior vertices of a patch without any boundary vertex cannot be interpolated: keep their bake
            ok = np.zeros(len(I), bool)
            ok[reach] = True
            for _ in range(len(I)):
                grow = ok | (np.abs(LII[:, ok]).sum(1) > 0)
                if (grow == ok).all():
                    break
                ok = grow
            dropped = int((~ok).sum())
            Iok = [i for i, o in zip(I, ok) if o]
            if Iok:
                X = np.linalg.solve(L[np.ix_(Iok, Iok)], -L[np.ix_(Iok, B)])
                for r, i in enumerate(Iok):
                    acc = {}
                    for cidx, b in enumerate(B):
                        if X[r, cidx] < 1e-5:
                            continue
                        for sidx, w in weights[b]:
                            acc[sidx] = acc.get(sidx, 0.0) + X[r, cidx] * w
                    tot = sum(acc.values())
                    weights[i] = [(kk, vv / tot) for kk, vv in sorted(acc.items())]
        for j in range(len(verts)):
            for sidx, w in weights.get(j, []):
                rows.append(vbase + j)
                cols.append(sidx)
                vals.append(w)
        painted_faces = 0
        for f in faces:
            corners = [(np.array(l[uvl].uv) * size, local[l.vert.index]) for l in f.loops]
            if any(c[1] not in weights for c in corners):
                continue
            painted_faces += 1
            for kk in range(1, len(corners) - 1):
                tri = (corners[0], corners[kk], corners[kk + 1])
                tri_px.append([t[0] for t in tri])
                tri_v.append([vbase + t[1] for t in tri])
                tri_lab.append(pi * 1000 + rec["cap_index"])
        meta.append({"name": spec["name"], "part": spec["part"], "covered_by": spec["covered_by"], "faces": len(faces),
                     "painted_faces": painted_faces, "vertices": len(verts), "boundary_vertices": len(B),
                     "area_cm2": U.r(sum(f.calc_area() for f in faces) * 1e4, 3), "dropped_vertices": dropped,
                     "params": {"max_distance_m": near, "max_ray_m": max_ray, "max_escape_share": esc_max,
                                "min_cover_share": cov_min}})
        vbase += len(verts)
        bm.free()
    return ({"tri_px": np.array(tri_px, np.float64).reshape(-1, 3, 2), "tri_v": np.array(tri_v, np.int64).reshape(-1, 3),
             "tri_cap": np.array(tri_lab, np.int64), "samp_px": np.array(samples, np.float64).reshape(-1, 2),
             "w_rows": np.array(rows, np.int64), "w_cols": np.array(cols, np.int64), "w_vals": np.array(vals, np.float64),
             "n_vertices": np.array(vbase, np.int64)}, meta)


def discrete_gap(labels, max_steps):
    """Minimum number of empty pixels between two different islands (Chebyshev BFS up to max_steps)."""
    h, w = labels.shape
    lab = labels.copy()
    dist = np.where(lab >= 0, 0, -1).astype(np.int32)
    shifts = [(-1, 0), (1, 0), (0, -1), (0, 1), (-1, -1), (-1, 1), (1, -1), (1, 1)]

    def shifted(a, dy, dx, fill):
        out = np.full_like(a, fill)
        ys = slice(max(dy, 0), h + min(dy, 0))
        yd = slice(max(-dy, 0), h + min(-dy, 0))
        xs = slice(max(dx, 0), w + min(dx, 0))
        xd = slice(max(-dx, 0), w + min(-dx, 0))
        out[yd, xd] = a[ys, xs]
        return out

    for step in range(1, max_steps + 1):
        empty = lab < 0
        if not empty.any():
            break
        new = np.full_like(lab, -1)
        for dy, dx in shifts:
            nb = shifted(lab, dy, dx, -1)
            take = empty & (new < 0) & (nb >= 0)
            new[take] = nb[take]
        grow = empty & (new >= 0)
        lab[grow] = new[grow]
        dist[grow] = step
    best = None
    for dy, dx in ((0, 1), (1, 0)):
        nb_l = shifted(lab, dy, dx, -1)
        nb_d = shifted(dist, dy, dx, -1)
        pair = (lab >= 0) & (nb_l >= 0) & (lab != nb_l)
        if pair.any():
            g = int((dist[pair] + nb_d[pair]).min())
            best = g if best is None else min(best, g)
    return best  # None: no two islands within 2*max_steps


def run(params, profile):
    run_dir = Path(params["run_dir"])
    bpy.ops.wm.open_mainfile(filepath=str(run_dir / "work" / "lp_closed.blend"))
    cfg = profile["uv"]
    size = int(cfg["atlas_px"])
    names = sorted(profile["parts"], key=U.part_key)
    objs = [bpy.data.objects["LP_" + n] for n in names]
    pri = cfg["texel_priority"]
    ccfg = cfg["charts"]
    chart_stats = {}
    for n, obj in zip(names, objs):
        me = obj.data
        for uv in list(me.uv_layers):
            me.uv_layers.remove(uv)
        me.uv_layers.new(name="UVMap")
        bpy.ops.object.select_all(action="DESELECT")
        obj.select_set(True)
        bpy.context.view_layer.objects.active = obj
        pcfg = {"normal_penalty": ccfg["normal_penalty"], "max_rounds": ccfg["max_rounds"],
                "max_overlap_share": ccfg["max_overlap_share"], "max_stretch_log_p95": ccfg["max_stretch_log_p95"],
                "stretch_min_faces": ccfg.get("stretch_min_faces", 12), "smooth_iterations": ccfg.get("smooth_iterations", 0),
                "chart_area_m2": float(ccfg["chart_area_cm2"].get(n, ccfg["chart_area_cm2"]["default"])) * 1e-4}
        regions = [{"box_m": r["box_m"], "chart_area_m2": float(r["chart_area_cm2"]) * 1e-4, "name": r["name"]}
                   for r in ccfg.get("regions", []) if r["part"] == n]
        chart_stats[n] = charts.chart_part(obj, pcfg, regions, ccfg["unwrap_method"])
        if obj.mode != "OBJECT":
            bpy.ops.object.mode_set(mode="OBJECT")
    island_info = {}
    for n, obj in zip(names, objs):
        default = pri["parts"].get(n, pri["default"])
        regions = [r for r in pri.get("regions", []) if r["part"] == n]
        island_info[n] = normalise_islands(obj, default, regions, profile.get("closure", {}).get("texel_priority"))
    # ---- pack all parts together
    bpy.ops.object.select_all(action="DESELECT")
    for obj in objs:
        obj.select_set(True)
    bpy.context.view_layer.objects.active = objs[0]
    ts = bpy.context.scene.tool_settings
    ts.use_uv_select_sync = True
    bpy.ops.object.mode_set(mode="EDIT")
    bpy.ops.mesh.select_all(action="SELECT")
    bpy.ops.uv.pack_islands(udim_source="CLOSEST_UDIM", rotate=True, rotate_method="ANY", scale=True,
                            merge_overlap=False, margin_method="FRACTION", margin=float(cfg["pack_margin_fraction"]),
                            pin=False, shape_method="CONCAVE")
    bpy.ops.object.mode_set(mode="OBJECT")

    # ---- measure: raster of islands and parts, bounds, texel density, gaps
    island_ids = np.full((size, size), -1, np.int32)
    part_ids = np.full((size, size), -1, np.int32)
    base_band = np.zeros((size, size), np.int32)
    overlap = np.zeros((size, size), np.int32)
    gid = 0
    per_part = {}
    uv_min, uv_max = np.array([9.0, 9.0]), np.array([-9.0, -9.0])
    band_cfg = profile["textures"]["team_mask"]["base_band"]
    for pi, (n, obj) in enumerate(zip(names, objs)):
        me = obj.data
        bm = bmesh.new()
        bm.from_mesh(me)
        uv_layer = bm.loops.layers.uv.active
        islands = uv_islands(bm, uv_layer)
        cap_layer = bm.faces.layers.int.get(CAP_ATTR)
        tris_px, vals, band_tris = [], [], []
        uv_area = cap_uv_area = cap_area = 0.0
        for faces in islands:
            for f in faces:
                is_cap = cap_layer is not None and f[cap_layer] > 0
                if is_cap:
                    cap_area += f.calc_area()
                uvs = [(l[uv_layer].uv.x * size, l[uv_layer].uv.y * size) for l in f.loops]
                for k in range(1, len(uvs) - 1):
                    t = (uvs[0], uvs[k], uvs[k + 1])
                    tris_px.append(t)
                    vals.append(gid)
                    a_uv = 0.5 * abs((t[1][0] - t[0][0]) * (t[2][1] - t[0][1]) - (t[2][0] - t[0][0]) * (t[1][1] - t[0][1]))
                    if is_cap:
                        cap_uv_area += a_uv
                    else:
                        uv_area += a_uv
                    if n == band_cfg["part"] and abs(f.normal.z) <= band_cfg["normal_z_abs_max"]:
                        band_tris.append(t)
                for l in f.loops:
                    uv = l[uv_layer].uv
                    uv_min = np.minimum(uv_min, (uv.x, uv.y))
                    uv_max = np.maximum(uv_max, (uv.x, uv.y))
            gid += 1
        tris_px = np.array(tris_px, np.float64)
        vals = np.array(vals, np.int32)
        layer = U.raster_triangles(tris_px, vals, size, fill=-1)
        U.raster_count(tris_px, size, out=overlap)
        island_ids = np.where(layer >= 0, layer, island_ids)
        part_ids[layer >= 0] = pi
        if band_tris:
            U.raster_triangles(np.array(band_tris, np.float64), np.ones(len(band_tris), np.int32), size, out=base_band)
        area_cm2 = U.mesh_area(me) * 1e4 - cap_area * 1e4
        covered = int((layer >= 0).sum())
        per_part[n] = {"islands": len(islands), "uv_area_px": U.r(uv_area, 1), "raster_px": covered,
                       "area_cm2": U.r(area_cm2, 3),
                       "caps": {"area_cm2": U.r(cap_area * 1e4, 3), "uv_area_px": U.r(cap_uv_area, 1),
                                "texel_density_px_per_cm_4k": U.r(math.sqrt(cap_uv_area / (cap_area * 1e4)), 3)}
                       if cap_area > 0 else None,
                       "texel_density_px_per_cm_4k": U.r(math.sqrt(uv_area / area_cm2), 3) if area_cm2 > 0 else None,
                       "texel_density_px_per_cm_2k": U.r(math.sqrt(uv_area / area_cm2) / 2, 3) if area_cm2 > 0 else None,
                       "priority_factor_default": pri["parts"].get(n, pri["default"]),
                       "regions": sorted({i["region"] for i in island_info[n] if i["region"]})}
        bm.free()
    region_density = {}
    for reg in pri.get("regions", []):
        obj = bpy.data.objects["LP_" + reg["part"]]
        me = obj.data
        bm = bmesh.new()
        bm.from_mesh(me)
        uv_layer = bm.loops.layers.uv.active
        a3 = auv = 0.0
        for faces in uv_islands(bm, uv_layer):
            c3 = sum((np.array(f.calc_center_median()) * f.calc_area() for f in faces), np.zeros(3)) / max(
                sum(f.calc_area() for f in faces), 1e-20)
            if not box_contains(reg["box_m"], c3):
                continue
            for f in faces:
                a3 += f.calc_area()
                uvs = [l[uv_layer].uv for l in f.loops]
                for k in range(1, len(uvs) - 1):
                    auv += 0.5 * abs((uvs[k].x - uvs[0].x) * (uvs[k + 1].y - uvs[0].y) - (uvs[k + 1].x - uvs[0].x) * (uvs[k].y - uvs[0].y))
        bm.free()
        region_density[reg["name"]] = U.r(math.sqrt(auv * size * size / (a3 * 1e4)), 3) if a3 > 0 else None
    gap = discrete_gap(island_ids, int(cfg["min_gap_px"]) // 2 + 2)
    coverage = float((island_ids >= 0).mean())
    out_dir = run_dir / "work" / "uv"
    out_dir.mkdir(parents=True, exist_ok=True)
    np.save(out_dir / "island_ids.npy", island_ids)
    np.save(out_dir / "part_ids.npy", part_ids)
    np.save(out_dir / "base_band.npy", base_band.astype(np.uint8))
    close_rep = json.loads((run_dir / "reports" / "close-report.json").read_text(encoding="utf-8"))
    ring_of = {c["name"]: c["rim_ring_m"] for c in profile.get("closure", {}).get("contact_caps", []) if c.get("rim_ring_m")}
    rings = {(c["part"], c["cap_index"]): ring_of[c["name"]] for c in close_rep["caps"] if c["name"] in ring_of}
    transfer, cap_meta = cap_transfer(names, objs, size, float(profile.get("closure", {}).get("rim_sample_fraction", 0.35)),
                                      rings)
    cap_ids = np.zeros((size, size), np.int32)
    if len(transfer["tri_cap"]):
        U.raster_triangles(transfer["tri_px"], transfer["tri_cap"].astype(np.int32), size, out=cap_ids)
    np.save(out_dir / "cap_ids.npy", cap_ids)
    np.savez(out_dir / "caps.npz", **transfer)
    fp_transfer, fp_meta = footprint_transfer(names, objs, size, float(profile.get("closure", {}).get("rim_sample_fraction", 0.35)),
                                              close_rep, profile.get("closure", {}).get("contact_caps", []))
    np.savez(out_dir / "footprints.npz", **fp_transfer)
    fp_ids = np.zeros((size, size), np.int32)
    if len(fp_transfer["tri_cap"]):
        U.raster_triangles(fp_transfer["tri_px"], fp_transfer["tri_cap"].astype(np.int32), size, out=fp_ids)
    # ---- layout preview (parts coloured, v up)
    rng = np.random.default_rng(7)
    pal = (rng.random((len(names), 3)) * 180 + 60).astype(np.uint8)
    img = np.zeros((size, size, 3), np.uint8)
    img[part_ids >= 0] = pal[part_ids[part_ids >= 0]]
    small = img[::4, ::4]  # row 0 = v 0, the pixel order of Blender images
    prev = bpy.data.images.new("uv_layout", 1024, 1024, alpha=False)
    rgba = np.concatenate([small.astype(np.float32) / 255.0, np.ones((1024, 1024, 1), np.float32)], axis=2)
    U.array_to_image(prev, rgba)
    prev.filepath_raw = str(run_dir / "preview" / "uv-layout-1024.png")
    (run_dir / "preview").mkdir(parents=True, exist_ok=True)
    prev.file_format = "PNG"
    prev.save()
    bpy.data.images.remove(prev)
    bpy.ops.wm.save_as_mainfile(filepath=str(run_dir / "work" / "lp_uv.blend"), compress=False)
    min_gap = int(cfg["min_gap_px"])
    checks = {
        "uv_inside_0_1": {"passed": bool(uv_min.min() >= 0.0 and uv_max.max() <= 1.0),
                          "measured": [U.rv(uv_min, 6), U.rv(uv_max, 6)], "expected": "[0, 1]"},
        "island_gap_px_at_4k": {"passed": gap is None or gap >= min_gap, "measured": gap, "expected": ">= %d" % min_gap,
                                "note": "raster at pixel centres; None = no two islands closer than the BFS horizon"},
        "raster_overlap_px": {"passed": int((overlap > 1).sum()) <= int(cfg["max_overlap_px"]),
                              "measured": int((overlap > 1).sum()), "expected": "<= %d" % int(cfg["max_overlap_px"]),
                              "note": "pixel centres strictly inside two or more UV triangles (any islands, any parts)"},
        "no_folded_uv_triangles": {"passed": all(c["folded_triangles"] == 0 for c in chart_stats.values()),
                                   "measured": {n: c["folded_triangles"] for n, c in chart_stats.items()}, "expected": 0},
        "priority_face_denser_than_body": {
            "passed": (region_density.get("face") or 0) >= 1.5 * (per_part["tripo_part_0"]["texel_density_px_per_cm_4k"] or 1e9),
            "measured": {"face": region_density.get("face"), "dress": per_part["tripo_part_0"]["texel_density_px_per_cm_4k"]},
            "expected": "face >= 1.5 x dress"},
    }
    report = {"stage": "uv", "atlas_px": size, "pack": {"margin_method": "FRACTION", "margin": cfg["pack_margin_fraction"],
                                                        "rotate": "ANY", "shape_method": "CONCAVE"},
              "unwrap": {"method": "voronoi charts + %s (fallback: one island per face)" % ccfg["unwrap_method"],
                         "charts": chart_stats}, "coverage_share": U.r(coverage, 4),
              "islands_total": gid, "min_gap_px": gap, "parts": per_part, "region_density_px_per_cm_4k": region_density,
              "caps": {"count": len(cap_meta), "texels_4k": int((cap_ids > 0).sum()),
                       "texel_priority": profile.get("closure", {}).get("texel_priority"),
                       "rim_samples": int(len(transfer["samp_px"])), "per_cap": cap_meta,
                       "note": "cap texels are filled by the textures stage from their rim (caps.npz), not baked"},
              "footprints": {"texels_4k": int((fp_ids > 0).sum()), "per_contact": fp_meta,
                             "note": "BC/RM/AO of faces hidden at rest under the covering part, from the visible surface around "
                                     "them (footprints.npz); their normal map stays baked"},
              "checks": checks, "passed": all(c["passed"] for c in checks.values()), "status": "измерено"}
    U.write_json(run_dir / "reports" / "uv-report.json", report)
    if not report["passed"]:
        raise RuntimeError("uv checks failed: %s" % [k for k, c in checks.items() if not c["passed"]])
