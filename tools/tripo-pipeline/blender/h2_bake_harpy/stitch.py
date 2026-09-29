"""Seam stitching of the per-part game mesh (headless Blender; used by stage_lowpoly.py).

Tripo's "by parts" high-poly is one surface cut into parts: two neighbouring parts share their cut exactly (the
boundary vertices of both coincide, e.g. inner/outer wing 1 125 edges each, head bottom / torso top). The per-part
collapse decimation moves each part's boundary on its own, so the cut opens into sub-millimetre cracks; with
one-sided materials (M_UM_Figure TwoSided=false) every crack that leads into a part's interior shows the background
(see_through.py measured 1-15 px per game frame at 4.8 m on harpy-h2-bake/2 before stitching) and the cracks open
further when the parts deform differently.

Stitching makes the two game-mesh boundaries of every shared cut the same polyline:
  1. shared_chains(): on the high-poly (authored frame) the boundary vertices of part A that coincide (<= tol_hp) with
     boundary vertices of part B; the boundary edges of A between such vertices form ordered chains (polylines);
  2. stitch_parts(): every game-mesh boundary vertex of A or B within snap_m of a chain is projected onto it
     (arc-length parameter t); parameters of A and B closer than merge_m are clustered into one shared vertex, the
     clusters one part lacks are inserted into its boundary (edge split, UVs interpolated along the edge), and every
     such vertex is moved to chain(t) - so both parts carry the same vertices along the cut, at the high-poly cut
     positions;
  3. faces that received a vertex are triangulated again.
Weights stay per part; stage_rig's harmonise pass gives coincident vertices the mean of both parts' weights (distance
0 -> full blend), so the cut stays closed in deformation too.
"""

import bmesh
import numpy as np
from mathutils import Vector
from mathutils.kdtree import KDTree


def _welded_boundary(me, weld):
    bm = bmesh.new()
    bm.from_mesh(me)
    bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=weld)
    bm.verts.ensure_lookup_table()
    edges = [(e.verts[0].index, e.verts[1].index) for e in bm.edges if len(e.link_faces) == 1]
    co = np.array([tuple(v.co) for v in bm.verts], dtype=np.float64)
    bm.free()
    return co, edges


def _chains(edge_list):
    """Ordered vertex chains of an edge set (paths and cycles); branch points end a chain."""
    adj = {}
    for a, b in edge_list:
        adj.setdefault(a, []).append(b)
        adj.setdefault(b, []).append(a)
    used = set()
    out = []
    starts = sorted([v for v, n in adj.items() if len(n) != 2]) + sorted(adj)
    for s in starts:
        for n0 in sorted(adj[s]):
            if (min(s, n0), max(s, n0)) in used:
                continue
            chain = [s]
            prev, cur = s, n0
            used.add((min(s, n0), max(s, n0)))
            while True:
                chain.append(cur)
                if cur == s:
                    break
                nxt = [n for n in sorted(adj[cur]) if n != prev and (min(cur, n), max(cur, n)) not in used]
                if len(adj[cur]) != 2 or not nxt:
                    break
                prev, cur = cur, nxt[0]
                used.add((min(prev, cur), max(prev, cur)))
            if len(chain) >= 2:
                out.append(chain)
    return out


def shared_chains(hp_objects, pairs=None, tol_hp=1e-5, weld=1e-6, min_vertices=8):
    """{(A, B): [polyline (N x 3), ...]} for part pairs whose high-poly boundaries share vertices."""
    data = {p: _welded_boundary(o.data, weld) for p, o in hp_objects.items()}
    names = sorted(data)
    trees = {}
    for p in names:
        co, edges = data[p]
        bverts = sorted({v for e in edges for v in e})
        kd = KDTree(max(1, len(bverts)))
        for i in bverts:
            kd.insert(Vector(co[i]), i)
        kd.balance()
        trees[p] = (kd, bverts)
    out = {}
    for ia, a in enumerate(names):
        for b in names[ia + 1:]:
            if pairs is not None and (a, b) not in pairs and (b, a) not in pairs:
                continue
            co_a, edges_a = data[a]
            kd_b = trees[b][0]
            shared = set()
            for i in trees[a][1]:
                _c, _j, d = kd_b.find(Vector(co_a[i]))
                if d is not None and d <= tol_hp:
                    shared.add(i)
            if len(shared) < min_vertices:
                continue
            sedges = [(u, v) for u, v in edges_a if u in shared and v in shared]
            polys = [co_a[c] for c in _chains(sedges) if len(c) >= min_vertices]
            if polys:
                out[(a, b)] = polys
    return out


class Chain:
    """Polyline with arc-length parametrisation and nearest-point projection."""

    def __init__(self, pts):
        self.p = np.asarray(pts, dtype=np.float64)
        self.closed = bool(np.linalg.norm(self.p[0] - self.p[-1]) < 1e-9)
        seg = np.linalg.norm(np.diff(self.p, axis=0), axis=1)
        self.s = np.concatenate([[0.0], np.cumsum(seg)])
        self.length = float(self.s[-1])

    def project(self, q):
        a, b = self.p[:-1], self.p[1:]
        ab = b - a
        L2 = np.maximum((ab * ab).sum(1), 1e-30)
        t = np.clip(((q - a) * ab).sum(1) / L2, 0.0, 1.0)
        pts = a + ab * t[:, None]
        d = np.linalg.norm(pts - q, axis=1)
        k = int(np.argmin(d))
        return float(d[k]), float(self.s[k] + t[k] * np.sqrt(L2[k]))

    def at(self, s):
        if self.closed:
            s = s % self.length
        s = min(max(s, 0.0), self.length)
        k = int(np.clip(np.searchsorted(self.s, s, side="right") - 1, 0, len(self.p) - 2))
        seg = self.s[k + 1] - self.s[k]
        f = 0.0 if seg <= 0 else (s - self.s[k]) / seg
        return self.p[k] + (self.p[k + 1] - self.p[k]) * f

    def between(self, s0, s1):
        """Arc from s0 to s1 (shorter way round on a closed chain): (start, signed length)."""
        d = s1 - s0
        if self.closed and abs(d) > self.length / 2:
            d = d - np.sign(d) * self.length
        return s0, d


def fix_slivers(bm, min_area_m2, short_m=1e-5, rounds=4):
    """Triangles left below min_area_m2 by the snapping: an edge shorter than short_m is collapsed (its two vertices
    coincide for practical purposes, the neighbour part keeps one vertex there), otherwise the longest edge of the
    sliver is rotated when it is an inner edge (Delaunay flip). Returns {"collapsed", "rotated", "left"}."""
    out = {"collapsed": 0, "rotated": 0, "left": 0}
    for _ in range(rounds):
        tiny = [f for f in bm.faces if f.is_valid and f.calc_area() < min_area_m2]
        if not tiny:
            break
        changed = False
        for f in tiny:
            if not f.is_valid or f.calc_area() >= min_area_m2:
                continue
            edges = sorted(f.edges, key=lambda e: e.calc_length())
            if edges[0].calc_length() < short_m:
                e = edges[0]
                bmesh.ops.pointmerge(bm, verts=list(e.verts), merge_co=e.verts[0].co.copy())
                out["collapsed"] += 1
                changed = True
            elif not edges[-1].is_boundary and len(edges[-1].link_faces) == 2:
                res = bmesh.ops.rotate_edges(bm, edges=[edges[-1]], use_ccw=False)
                if res.get("edges"):
                    out["rotated"] += 1
                    changed = True
        if not changed:
            break
    out["left"] = sum(1 for f in bm.faces if f.calc_area() < min_area_m2)
    return out


def stitch_parts(lp_meshes, chains, snap_m=0.002, merge_m=0.0005, max_edge_factor=1.5, junctions=True,
                 min_area_m2=2.5e-8):
    """Stitch the game meshes {part: bpy mesh} along the shared chains {(A, B): [pts]}. Returns a report.
    min_area_m2: slivers below it are fixed afterwards (fix_slivers; 2.5e-8 m2 source = 1.1e-4 cm2 at the Harpy seat
    scale 0.66, above the export check's 1e-4 cm2)."""
    report = {"pairs": {}, "vertices_inserted": {}, "vertices_snapped": {}, "faces_retriangulated": {}}
    bms = {}
    for p, me in lp_meshes.items():
        bm = bmesh.new()
        bm.from_mesh(me)
        bms[p] = bm
    for (a, b), polys in sorted(chains.items()):
        if a not in bms or b not in bms:
            continue
        pair_rep = []
        for pts in polys:
            ch = Chain(pts)
            params = {}
            for p in (a, b):
                bm = bms[p]
                bnd = [v for v in bm.verts if v.is_boundary]
                near = {}
                for v in bnd:
                    d, s = ch.project(np.array(tuple(v.co)))
                    if d <= snap_m:
                        near[v] = s
                # a vertex belongs to the cut only if a boundary neighbour is near the chain too (keeps an unrelated
                # boundary that merely passes within snap_m, e.g. a feather tip, where it is)
                on = {v: s for v, s in near.items()
                      if any(e.is_boundary and e.other_vert(v) in near for e in v.link_edges)}
                params[p] = on
            # clusters of the parameters of both parts closer than merge_m along the chain -> one shared vertex
            # (cluster mean); a part gets a vertex inserted only where the other part has one and it has none
            union = sorted(set(params[a].values()) | set(params[b].values()))
            clusters = []
            for s in union:  # span of a cluster <= merge_m (no chaining of many close vertices into one)
                if clusters and s - clusters[-1][0] <= merge_m:
                    clusters[-1].append(s)
                else:
                    clusters.append([s])
            if ch.closed and len(clusters) > 1 and clusters[0][-1] + ch.length - clusters[-1][0] <= merge_m:
                clusters[0] = [x - ch.length for x in clusters[-1]] + clusters[0]
                clusters.pop()
            centre_of = {}
            merged = []
            for c in clusters:
                m = float(np.mean(c))
                if ch.closed:
                    m %= ch.length
                merged.append(m)
                for x in c:
                    centre_of[x % ch.length if ch.closed else x] = m
            for p in (a, b):
                params[p] = {v: centre_of[s] for v, s in params[p].items()}
            merged.sort()
            ins_count = {a: 0, b: 0}
            for p in (a, b):
                bm = bms[p]
                on = params[p]
                # boundary edges running along the chain (both ends on it, arc not longer than max_edge_factor x
                # the edge; 3.0 let an edge follow a bend of the cut and folded a wing corner, measured 2026-09-29):
                # split at the union parameters that fall strictly inside
                edges = [e for e in bm.edges if e.is_boundary and e.verts[0] in on and e.verts[1] in on]
                for e in edges:
                    v0, v1 = e.verts
                    s0, ds = ch.between(on[v0], on[v1])
                    if abs(ds) < 1e-9 or abs(ds) > max_edge_factor * e.calc_length() + snap_m:
                        continue
                    lo_, hi_ = (s0, s0 + ds) if ds > 0 else (s0 + ds, s0)
                    inner = []
                    for s in merged:
                        for cand in ((s, s - ch.length, s + ch.length) if ch.closed else (s,)):
                            if lo_ + 1e-9 < cand < hi_ - 1e-9:
                                inner.append((cand - s0) / ds)
                    if not inner:
                        continue
                    inner.sort()
                    cur_edge, cur_v0, r_prev = e, v0, 0.0
                    for r in inner:
                        fac = min(max((r - r_prev) / (1.0 - r_prev), 1e-4), 1 - 1e-4)
                        _new_e, new_v = bmesh.utils.edge_split(cur_edge, cur_v0, fac)
                        s_new = s0 + r * ds
                        on[new_v] = s_new % ch.length if ch.closed else s_new
                        cur_edge = next(x for x in new_v.link_edges if v1 in x.verts)
                        cur_v0, r_prev = new_v, r
                        ins_count[p] += 1
                for v, s in on.items():
                    v.co = Vector(ch.at(s))
            pair_rep.append({"chain_length_m": round(ch.length, 5), "chain_points": int(len(ch.p)),
                             "closed": ch.closed, "on_chain": {a: len(params[a]), b: len(params[b])},
                             "union_parameters": len(merged), "inserted": ins_count})
            for p in (a, b):
                report["vertices_inserted"][p] = report["vertices_inserted"].get(p, 0) + ins_count[p]
                report["vertices_snapped"][p] = report["vertices_snapped"].get(p, 0) + len(params[p])
        report["pairs"]["%s|%s" % (a, b)] = pair_rep
    # junctions: the open ends of every chain (where the cut meets another part's cut or ends) get a vertex exactly
    # at the high-poly end point in both parts of the chain (nearest boundary vertex within merge_m moved there,
    # otherwise the nearest boundary edge within snap_m split there), so the three-part corners close too
    n_junctions = 0
    for (a, b), polys in sorted(chains.items()) if junctions else ():
        if a not in bms or b not in bms:
            continue
        for pts in polys:
            ch = Chain(pts)
            if ch.closed:
                continue
            for end in (ch.p[0], ch.p[-1]):
                J = Vector(end)
                for p in (a, b):
                    bm = bms[p]
                    bv = [v for v in bm.verts if v.is_boundary]
                    if not bv:
                        continue
                    v_near = min(bv, key=lambda v: (v.co - J).length)
                    if (v_near.co - J).length <= merge_m:
                        v_near.co = J
                        continue
                    best = None
                    for e in bm.edges:
                        if not e.is_boundary:
                            continue
                        p0, p1 = e.verts[0].co, e.verts[1].co
                        d = p1 - p0
                        L2 = d.length_squared
                        if L2 <= 1e-18:
                            continue
                        t = min(max((J - p0).dot(d) / L2, 0.0), 1.0)
                        dist = (p0 + d * t - J).length
                        if best is None or dist < best[0]:
                            best = (dist, e, t)
                    if best is None or best[0] > snap_m:
                        continue
                    _dist, e, t = best
                    if t <= 1e-3 or t >= 1 - 1e-3:
                        (e.verts[0] if t <= 1e-3 else e.verts[1]).co = J
                    else:
                        _ne, nv = bmesh.utils.edge_split(e, e.verts[0], t)
                        nv.co = J
                        report["vertices_inserted"][p] = report["vertices_inserted"].get(p, 0) + 1
                    n_junctions += 1
    report["junction_vertices"] = n_junctions
    for p, bm in bms.items():
        # two boundary vertices of one part that fell into the same cluster now coincide: merge them
        nv = len(bm.verts)
        bmesh.ops.remove_doubles(bm, verts=[v for v in bm.verts if v.is_boundary], dist=1e-7)
        report.setdefault("vertices_merged_within_part", {})[p] = nv - len(bm.verts)
        bmesh.ops.dissolve_degenerate(bm, dist=1e-7, edges=bm.edges[:])
        ngons = [f for f in bm.faces if len(f.verts) > 3]
        report["faces_retriangulated"][p] = len(ngons)
        if ngons:
            bmesh.ops.triangulate(bm, faces=ngons, quad_method="BEAUTY", ngon_method="EAR_CLIP")
        report.setdefault("slivers_fixed", {})[p] = fix_slivers(bm, min_area_m2)
        bm.to_mesh(lp_meshes[p])
        bm.free()
        lp_meshes[p].update()
    return report
