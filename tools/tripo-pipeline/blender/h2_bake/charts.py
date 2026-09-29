"""Seam-based UV charts for decimated game meshes. Smart UV Project cuts a decimated triangle soup into thousands of
tiny islands (Medusa H2: 5 402 islands, 41 % of the 4K atlas at an 8 px gap — measured) and its planar projection
overlapped folded cloth when tried as a fallback.

Charts: per connected component (and per profile region, e.g. the face), k = ceil(area / chart_area) seeds by
farthest-point sampling of face centroids (first seed = lowest face index: deterministic); regions grow by
multi-source Dijkstra on the face graph with the cost |c_u - c_v| * (1 + lambda * (1 - n_v . n_seed)), so that
charts avoid crossing sharp folds; a majority filter removes one-triangle spikes. Seams = chart borders + boundary
+ non-manifold edges; Blender unwraps every chart (MINIMUM_STRETCH). A chart that folds (flipped UV triangles),
overlaps itself on a 512 px raster, or stretches (|log area ratio| p95 above the limit; judged only for charts with
>= stretch_min_faces faces, decimation slivers dominate a tiny chart's p95) is split in two and unwrapped again, up
to max_rounds; every face of a chart that still fails becomes its own island (a triangle cannot fold or overlap)."""

import heapq
import math

import bmesh
import bpy
import numpy as np


def face_data(bm):
    bm.faces.ensure_lookup_table()
    bm.edges.ensure_lookup_table()
    cen = np.array([tuple(f.calc_center_median()) for f in bm.faces], np.float64)
    nrm = np.array([tuple(f.normal) for f in bm.faces], np.float64)
    area = np.array([f.calc_area() for f in bm.faces], np.float64)
    adj = [[] for _ in range(len(bm.faces))]
    for e in bm.edges:
        lf = e.link_faces
        if len(lf) == 2:
            a, b = lf[0].index, lf[1].index
            adj[a].append((b, e.index))
            adj[b].append((a, e.index))
    return cen, nrm, area, adj


def components(faces, adj, allowed):
    seen, out = set(), []
    for f in sorted(faces):
        if f in seen:
            continue
        comp, stack = [], [f]
        seen.add(f)
        while stack:
            x = stack.pop()
            comp.append(x)
            for y, _e in adj[x]:
                if y in allowed and y not in seen:
                    seen.add(y)
                    stack.append(y)
        out.append(sorted(comp))
    return out


def grow(faces, k, cen, nrm, adj, lam):
    """Label `faces` (a connected set) into k regions: FPS seeds + multi-source Dijkstra. Returns {face: local id}."""
    faces = sorted(faces)
    allowed = set(faces)
    pts = cen[faces]
    seeds = [0]
    d = np.linalg.norm(pts - pts[0], axis=1)
    for _ in range(1, min(k, len(faces))):
        nxt = int(np.argmax(d))
        if d[nxt] <= 0:
            break
        seeds.append(nxt)
        d = np.minimum(d, np.linalg.norm(pts - pts[nxt], axis=1))
    label, dist, heap = {}, {}, []
    for sid, s in enumerate(seeds):
        f = faces[s]
        dist[f] = 0.0
        heapq.heappush(heap, (0.0, f, sid))
    seed_n = [nrm[faces[s]] for s in seeds]
    while heap:
        dd, f, sid = heapq.heappop(heap)
        if f in label:
            continue
        label[f] = sid
        for g, _e in adj[f]:
            if g not in allowed or g in label:
                continue
            step = float(np.linalg.norm(cen[g] - cen[f])) * (1.0 + lam * (1.0 - float(np.dot(nrm[g], seed_n[sid]))))
            nd = dd + step
            if nd < dist.get(g, math.inf):
                dist[g] = nd
                heapq.heappush(heap, (nd, g, sid))
    return label


def smooth_labels(chart, adj, domain, iterations):
    """Majority filter on the face graph: a face whose >= 2 edge neighbours (same domain) share another chart joins
    it (removes one-triangle spikes along ragged Dijkstra borders; ragged charts pack badly). Deterministic: faces
    in index order, labels from the previous iteration."""
    chart = chart.copy()
    for _ in range(iterations):
        prev = chart.copy()
        changed = 0
        for f in range(len(prev)):
            votes = {}
            for g, _e in adj[f]:
                if domain[g] == domain[f] and prev[g] != prev[f]:
                    votes[int(prev[g])] = votes.get(int(prev[g]), 0) + 1
            if votes:
                best = max(sorted(votes), key=lambda k: votes[k])
                own = sum(1 for g, _e in adj[f] if prev[g] == prev[f])
                if votes[best] >= 2 and votes[best] > own:
                    chart[f] = best
                    changed += 1
        if not changed:
            break
    return chart


def chart_quality(me, faces_by_chart, uv_name, raster=512):
    """Per chart: folded UV triangles, raster self-overlap share, |log(area ratio)| p95 (ratio normalised by the
    chart's total UV/3D area)."""
    uv = me.uv_layers[uv_name]
    luv = np.empty(len(me.loops) * 2, np.float64)
    uv.data.foreach_get("uv", luv)
    luv = luv.reshape(-1, 2)
    co = np.empty(len(me.vertices) * 3, np.float64)
    me.vertices.foreach_get("co", co)
    co = co.reshape(-1, 3)
    out = {}
    for cid, faces in faces_by_chart.items():
        tris_uv, tris_3d = [], []
        for fi in faces:
            p = me.polygons[fi]
            li = list(p.loop_indices)
            vi = list(p.vertices)
            for k in range(1, len(li) - 1):
                tris_uv.append((luv[li[0]], luv[li[k]], luv[li[k + 1]]))
                tris_3d.append((co[vi[0]], co[vi[k]], co[vi[k + 1]]))
        tu = np.array(tris_uv)
        t3 = np.array(tris_3d)
        signed = 0.5 * ((tu[:, 1, 0] - tu[:, 0, 0]) * (tu[:, 2, 1] - tu[:, 0, 1]) - (tu[:, 2, 0] - tu[:, 0, 0]) * (tu[:, 1, 1] - tu[:, 0, 1]))
        a3 = 0.5 * np.linalg.norm(np.cross(t3[:, 1] - t3[:, 0], t3[:, 2] - t3[:, 0]), axis=1)
        major = 1.0 if signed.sum() >= 0 else -1.0
        folded = int(((signed * major) < -1e-14).sum())
        auv = np.abs(signed)
        ok = (a3 > 1e-14) & (auv > 1e-20)
        if ok.sum() == 0 or auv.sum() <= 0:
            out[cid] = {"folded": folded, "overlap": 1.0, "stretch_p95": 99.0}
            continue
        ratio = np.log(auv[ok] / a3[ok]) - math.log(auv.sum() / a3.sum())
        stretch = float(np.percentile(np.abs(ratio), 95))
        lo = tu.reshape(-1, 2).min(0)
        span = max(float((tu.reshape(-1, 2).max(0) - lo).max()), 1e-12)
        px = (tu - lo) / span * (raster - 1)
        cnt = np.zeros((raster, raster), np.int32)
        for t in px:
            x0, y0 = np.floor(t.min(0)).astype(int)
            x1, y1 = np.ceil(t.max(0)).astype(int)
            x0, y0 = max(x0, 0), max(y0, 0)
            x1, y1 = min(x1, raster - 1), min(y1, raster - 1)
            if x1 < x0 or y1 < y0:
                continue
            X, Y = np.meshgrid(np.arange(x0, x1 + 1) + 0.5, np.arange(y0, y1 + 1) + 0.5)
            a, b, c = t
            dd = (b[1] - c[1]) * (a[0] - c[0]) + (c[0] - b[0]) * (a[1] - c[1])
            if abs(dd) < 1e-12:
                continue
            l1 = ((b[1] - c[1]) * (X - c[0]) + (c[0] - b[0]) * (Y - c[1])) / dd
            l2 = ((c[1] - a[1]) * (X - c[0]) + (a[0] - c[0]) * (Y - c[1])) / dd
            inside = (l1 > 1e-6) & (l2 > 1e-6) & (1 - l1 - l2 > 1e-6)
            cnt[y0:y1 + 1, x0:x1 + 1] += inside
        covered = (cnt > 0).sum()
        overlap = float((cnt > 1).sum() / covered) if covered else 1.0
        out[cid] = {"folded": folded, "overlap": overlap, "stretch_p95": stretch}
    return out


def select_faces_edit(obj, face_ids):
    """Edit mode, face select mode, exactly `face_ids` selected (vertex select mode would re-derive faces from
    stale vertex flags: measured — a fallback Smart UV Project then re-projected the whole part)."""
    if obj.mode != "EDIT":
        bpy.ops.object.mode_set(mode="EDIT")
    ts = bpy.context.scene.tool_settings
    ts.mesh_select_mode = (False, False, True)
    ts.use_uv_select_sync = True
    bm = bmesh.from_edit_mesh(obj.data)
    bm.faces.ensure_lookup_table()
    for v in bm.verts:
        v.select = False
    for e in bm.edges:
        e.select = False
    for f in bm.faces:
        f.select = False
    for i in face_ids:
        bm.faces[i].select = True
    bm.select_mode = {"FACE"}
    bm.select_flush_mode()
    bmesh.update_edit_mesh(obj.data, loop_triangles=False, destructive=False)
    n = sum(1 for f in bm.faces if f.select)
    if n != len(set(face_ids)):
        raise RuntimeError("face selection mismatch on %s: %d != %d" % (obj.name, n, len(set(face_ids))))


def unwrap_selected(obj, face_ids, method):
    select_faces_edit(obj, face_ids)
    bpy.ops.uv.unwrap(method=method, fill_holes=True, correct_aspect=True, margin=0.0)
    bpy.ops.object.mode_set(mode="OBJECT")


def set_seams(obj, chart_of_face):
    me = obj.data
    bm = bmesh.new()
    bm.from_mesh(me)
    bm.edges.ensure_lookup_table()
    n = 0
    for e in bm.edges:
        lf = e.link_faces
        seam = bool(len(lf) != 2 or chart_of_face[lf[0].index] != chart_of_face[lf[1].index])
        e.seam = seam
        n += int(seam)
    bm.to_mesh(me)
    bm.free()
    me.update()
    return n


def chart_part(obj, cfg, regions, method, uv_name="UVMap"):
    """Charts + unwrap of one part object (must be the only selected, active object). Returns stats."""
    me = obj.data
    bm = bmesh.new()
    bm.from_mesh(me)
    cen, nrm, area, adj = face_data(bm)
    bm.free()
    nf = len(area)
    lam = float(cfg["normal_penalty"])
    # region membership (face centroid in a box) cuts the part into independent chart domains
    domain = np.zeros(nf, np.int64)
    domain_area = {0: float(cfg["chart_area_m2"])}
    for ri, reg in enumerate(regions, start=1):
        lo, hi = np.array(reg["box_m"][0]), np.array(reg["box_m"][1])
        inside = np.all((cen >= lo) & (cen <= hi), axis=1)
        domain[inside] = ri
        domain_area[ri] = float(reg["chart_area_m2"])
    chart = np.full(nf, -1, np.int64)
    next_id = 0
    for dom in sorted(set(domain.tolist())):
        allowed = set(np.nonzero(domain == dom)[0].tolist())
        for comp in components(allowed, adj, allowed):
            k = max(1, int(math.ceil(area[comp].sum() / domain_area[dom])))
            lab = grow(comp, k, cen, nrm, adj, lam)
            for f, sid in lab.items():
                chart[f] = next_id + sid
            next_id += k
    if (chart < 0).any():
        raise RuntimeError("chart growth left faces unlabelled in %s" % obj.name)
    chart = smooth_labels(chart, adj, domain, int(cfg.get("smooth_iterations", 0)))
    # compact ids
    _u, chart = np.unique(chart, return_inverse=True)
    rounds = []
    fallback = []
    todo = sorted(set(chart.tolist()))
    for rnd in range(int(cfg["max_rounds"]) + 1):
        set_seams(obj, chart)
        faces_todo = [f for f in range(nf) if chart[f] in set(todo)]
        unwrap_selected(obj, faces_todo, method)
        by_chart = {}
        for f in faces_todo:
            by_chart.setdefault(int(chart[f]), []).append(f)
        q = chart_quality(me, by_chart, uv_name)
        small = int(cfg.get("stretch_min_faces", 12))
        bad = sorted(c for c, s in q.items() if s["folded"] > 0 or s["overlap"] > cfg["max_overlap_share"]
                     or (len(by_chart[c]) >= small and s["stretch_p95"] > cfg["max_stretch_log_p95"]))
        rounds.append({"round": rnd, "charts_unwrapped": len(by_chart), "bad": len(bad)})
        if not bad:
            break
        if rnd == int(cfg["max_rounds"]):
            fallback = bad
            break
        top = int(chart.max()) + 1
        new_todo = []
        for c in bad:
            faces = [f for f in range(nf) if chart[f] == c]
            if len(faces) < 2:
                new_todo.append(c)
                continue
            lab = grow(faces, 2, cen, nrm, adj, lam)
            for f, sid in lab.items():
                if sid == 1:
                    chart[f] = top
            new_todo.extend([c, top])
            top += 1
        todo = new_todo
    if fallback:
        # last resort: every face of a still-failing chart becomes its own island (a triangle cannot fold or
        # overlap itself; Smart UV Project was measured to overlap projected cloth folds)
        top = int(chart.max()) + 1
        faces = [f for f in range(nf) if chart[f] in set(fallback)]
        for f in faces:
            chart[f] = top
            top += 1
        set_seams(obj, chart)
        unwrap_selected(obj, faces, method)
    by_chart = {}
    for f in range(nf):
        by_chart.setdefault(int(chart[f]), []).append(f)
    q = chart_quality(me, by_chart, uv_name)
    stretch = [s["stretch_p95"] for s in q.values()]
    return {"charts": int(len(by_chart)), "rounds": rounds, "fallback_charts": len(fallback),
            "fallback_faces": int(len(faces)) if fallback else 0,
            "folded_triangles": int(sum(s["folded"] for s in q.values())),
            "max_overlap_share": round(max([s["overlap"] for s in q.values()] or [0.0]), 5),
            "stretch_log_p95_max": round(max(stretch or [0.0]), 4),
            "stretch_log_p95_median": round(float(np.median(stretch)) if stretch else 0.0, 4)}
