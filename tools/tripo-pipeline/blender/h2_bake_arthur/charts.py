"""UV charting of a decimated part: normal-cone region growing + small-chart merge, SLIM unwrap, refinement.

Why not Smart UV Project: on collapse-decimated Tripo surfaces (noisy triangle normals) it breaks every part into
hundreds of fragments (measured 2026-09-29: 6019 islands for 40k triangles, 4.8 % atlas coverage after a 16 px-gap
pack; a larger angle limit or a smoothed projection proxy gave MORE islands). Charts grown over the face adjacency
keep the islands connected and large; SLIM (MINIMUM_STRETCH, no_flip) flattens each chart. Islands that still flip
or compress a face area below `bad_area_ratio` of the island mean are re-segmented with a narrower cone (no forced
merges) and unwrapped again, up to len(refine_cones_deg) times.

Deterministic: seeds in descending face area (ties by index), heap keyed by (angle, face index).
"""

import heapq
import math

import bmesh
import bpy
from bpy_extras import bmesh_utils

FOLD_COS = -0.5  # dihedral fold > 120 deg (thin-shell rims of the cloak/tabard): never inside one chart


def _grow(bm, subset, cone_deg, min_faces, min_area_share, merge_extra_deg, force_max_faces):
    """Chart id per face index of `subset` (faces outside the subset are never joined)."""
    faces = bm.faces
    sub = set(subset)
    normals = {i: faces[i].normal.copy() for i in sub}
    areas = {i: faces[i].calc_area() for i in sub}
    total_area = sum(areas.values()) or 1.0
    adj = {i: [] for i in sub}
    for i in sorted(sub):
        for e in faces[i].edges:
            lf = e.link_faces
            if len(lf) != 2 or not e.is_manifold:
                continue
            j = lf[1].index if lf[0].index == i else lf[0].index
            if j in sub and faces[i].normal.dot(faces[j].normal) >= FOLD_COS:
                adj[i].append((j, e.index))
    cos_cone = math.cos(math.radians(cone_deg))
    chart = {}
    charts = []
    for seed in sorted(sub, key=lambda i: (-areas[i], i)):
        if seed in chart:
            continue
        cid = len(charts)
        acc = normals[seed] * areas[seed]
        members = [seed]
        chart[seed] = cid
        heap = [(-normals[nb].dot(normals[seed]), nb) for nb, _e in adj[seed] if nb not in chart]
        heapq.heapify(heap)
        while heap:
            _key, f = heapq.heappop(heap)
            if f in chart:
                continue
            cn = acc.normalized() if acc.length > 0 else normals[seed]
            if normals[f].dot(cn) < cos_cone:
                continue
            chart[f] = cid
            members.append(f)
            acc += normals[f] * areas[f]
            cn = acc.normalized()
            for nb, _e in adj[f]:
                if nb not in chart:
                    heapq.heappush(heap, (-normals[nb].dot(cn), nb))
        charts.append({"faces": members, "acc": acc})
    cos_merge = math.cos(math.radians(cone_deg + merge_extra_deg))
    edge_len = {}
    changed, passes = True, 0
    while changed and passes < 8:
        changed = False
        passes += 1
        for c in sorted(range(len(charts)), key=lambda c: (len(charts[c]["faces"]), c)):
            fs = charts[c]["faces"]
            if not fs:
                continue
            if len(fs) >= min_faces and sum(areas[f] for f in fs) >= min_area_share * total_area:
                continue
            shared = {}
            for f in fs:
                for nb, e in adj[f]:
                    d = chart[nb]
                    if d != c:
                        if e not in edge_len:
                            edge_len[e] = bm.edges[e].calc_length()
                        shared[d] = shared.get(d, 0.0) + edge_len[e]
            ranked = sorted(shared.items(), key=lambda kv: (-kv[1], kv[0]))
            best = None
            for d, _length in ranked:
                acc = charts[d]["acc"] + charts[c]["acc"]
                if acc.length == 0:
                    continue
                cn = acc.normalized()
                if all(normals[f].dot(cn) >= cos_merge for f in fs + charts[d]["faces"]):
                    best = d
                    break
            if best is None and ranked and len(fs) <= force_max_faces:
                best = ranked[0][0]
            if best is None:
                continue
            for f in fs:
                chart[f] = best
            charts[best]["faces"].extend(fs)
            charts[best]["acc"] = charts[best]["acc"] + charts[c]["acc"]
            charts[c]["faces"] = []
            changed = True
    return chart


def _set_seams(bm, chart, subset):
    sub = set(subset)
    for f in sorted(sub):
        for e in bm.faces[f].edges:
            lf = e.link_faces
            if len(lf) == 2 and e.is_manifold and lf[0].normal.dot(lf[1].normal) >= FOLD_COS:
                a, b = lf[0].index, lf[1].index
                if a in sub and b in sub:
                    e.seam = chart[a] != chart[b]
                else:
                    e.seam = True
            else:
                e.seam = True


def _unwrap_selected(obj, faces, iterations):
    me = obj.data
    sel = set(faces)
    for p in me.polygons:
        p.select = p.index in sel
    for o in bpy.context.view_layer.objects:
        o.select_set(False)
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj
    bpy.ops.object.mode_set(mode="EDIT")
    bpy.ops.uv.unwrap(method="MINIMUM_STRETCH", fill_holes=True, correct_aspect=True, margin=0.0,
                      no_flip=True, iterations=iterations)
    bpy.ops.object.mode_set(mode="OBJECT")


def island_quality(obj):
    """Per UV island: faces, flipped faces (UV winding against the island majority) and the area-weighted p5 of
    ratio = face UV-area share / face 3D-area share inside the island (1 = no area distortion)."""
    bm = bmesh.new()
    bm.from_mesh(obj.data)
    uv = bm.loops.layers.uv.active
    out = []
    for isl in bmesh_utils.bmesh_linked_uv_islands(bm, uv):
        a3, au, sg = [], [], []
        for f in isl:
            p = [l[uv].uv for l in f.loops]
            s = (p[1].x - p[0].x) * (p[2].y - p[0].y) - (p[2].x - p[0].x) * (p[1].y - p[0].y)
            sg.append(s)
            au.append(abs(s) * 0.5)
            a3.append(f.calc_area())
        t3, tu = sum(a3) or 1e-30, sum(au) or 1e-30
        pos = sum(1 for s in sg if s > 0)
        neg = sum(1 for s in sg if s < 0)
        ratios = sorted(((u / tu) / max(a / t3, 1e-30), a) for u, a in zip(au, a3))
        acc, p5 = 0.0, ratios[0][0]
        for rr, a in ratios:
            acc += a
            if acc >= 0.05 * t3:
                p5 = rr
                break
        out.append({"faces": sorted(f.index for f in isl), "flipped": min(pos, neg), "p5_ratio": p5})
    bm.free()
    return out


def chart_unwrap(obj, cfg):
    """Segment, seam, unwrap and refine one part. Returns a report dict."""
    bm = bmesh.new()
    bm.from_mesh(obj.data)
    bm.faces.ensure_lookup_table()
    bm.edges.ensure_lookup_table()
    all_faces = list(range(len(bm.faces)))
    chart = _grow(bm, all_faces, float(cfg["cone_deg"]), int(cfg["min_chart_faces"]), float(cfg["min_chart_area_share"]),
                  float(cfg["merge_extra_deg"]), int(cfg["force_merge_max_faces"]))
    _set_seams(bm, chart, all_faces)
    bm.to_mesh(obj.data)
    bm.free()
    iterations = int(cfg["slim_iterations"])
    _unwrap_selected(obj, all_faces, iterations)
    rep = {"charts_initial": len(set(chart.values())), "refinements": []}
    bad_ratio = float(cfg["bad_area_ratio"])
    for cone in cfg["refine_cones_deg"]:
        q = island_quality(obj)
        bad = [i for i in q if i["flipped"] > 0 or i["p5_ratio"] < bad_ratio]
        if not bad:
            break
        faces = sorted(f for i in bad for f in i["faces"])
        bm = bmesh.new()
        bm.from_mesh(obj.data)
        bm.faces.ensure_lookup_table()
        bm.edges.ensure_lookup_table()
        sub_chart = _grow(bm, faces, float(cone), int(cfg["min_chart_faces"]), float(cfg["min_chart_area_share"]),
                          float(cfg["merge_extra_deg"]) * 0.5, 0)
        _set_seams(bm, sub_chart, faces)
        bm.to_mesh(obj.data)
        bm.free()
        _unwrap_selected(obj, faces, iterations)
        rep["refinements"].append({"cone_deg": cone, "bad_islands": len(bad), "faces": len(faces),
                                   "flipped_before": sum(i["flipped"] for i in bad)})
    q = island_quality(obj)
    rep["islands"] = len(q)
    rep["flipped_faces"] = sum(i["flipped"] for i in q)
    rep["islands_below_bad_ratio"] = sum(1 for i in q if i["p5_ratio"] < bad_ratio)
    rep["worst_island_p5_ratio"] = round(min(i["p5_ratio"] for i in q), 4)
    return rep
