"""Crack sealing of the per-part game mesh (headless Blender; H2.1). Used by stage_lowpoly.py (non-manifold fix) and
stage_rig.py (contact lips).

M_UM_Figure is one-sided (TwoSided=false). After lowpoly.stitch the shared Tripo cuts are closed vertex for vertex, but
see_through.py still measured isolated 1-3 px pinholes (harpy-h2-bake/2: 50 px over 36 game frames, 0-6 per frame).
The scratch ray diagnosis of 2026-09-29 (every see-through pixel of azimuths 120-240 cast back into the parts) put all
of them next to boundary edges that are NOT shared: three-part corners (head / torso / right-wing coverts), the
wing-root contacts of the torso and the inner/outer wing corners - boundaries that end 0.05-1.5 mm (final scale) away
from the neighbour part, so a ray slips between them and meets only culled back faces behind.

fix_nonmanifold(bm)   edges with more than two faces (decimation pinches and fins; harpy-h2-bake/2: 1 in
                      tripo_part_10, 2 in tripo_part_6) are resolved: at an end vertex whose faces split into separate
                      fans once the edge is ignored, every fan but the largest is moved onto its own copy of the vertex
                      (same position, so nothing opens geometrically); if neither end separates, the smallest face on
                      the edge beyond two is removed (a fin).
add_lips(objs, ...)   a "lip" quad on every boundary edge of a part that lies near another part (0 < distance to the
                      other parts <= contact_m) and is not a stitched (shared) edge: the edge's non-shared vertices are
                      carried to the nearest point of the other parts plus overshoot_m further, tucked tuck_m inward
                      along their own vertex normal, so the lip spans the crack and ends just under the neighbour's
                      surface; winding follows the adjacent face (outward side = the part's outside). Lip corners that
                      coincide with another part's vertex stay where they are (the quad degenerates to a triangle).
                      UVs: the boundary corners keep their UVs; the new corners are extrapolated with the adjacent face's
                      3D->UV map and clamped to max_uv_px texels of the atlas (they stay inside the island's own
                      gutter). The lip is optionally doubled by a detached reversed copy (double_sided).
"""

import bmesh
import numpy as np
from mathutils import Vector
from mathutils.bvhtree import BVHTree
from mathutils.kdtree import KDTree


# ------------------------------------------------------------------------------------------------ non-manifold edges
def _fans(v, skip_edge):
    """Faces around v grouped into fans connected through edges of v other than skip_edge (manifold edges only)."""
    faces = list(v.link_faces)
    idx = {f: k for k, f in enumerate(faces)}
    parent = list(range(len(faces)))

    def find(a):
        while parent[a] != a:
            parent[a] = parent[parent[a]]
            a = parent[a]
        return a

    for e in v.link_edges:
        if e is skip_edge or len(e.link_faces) != 2:
            continue
        a, b = idx.get(e.link_faces[0]), idx.get(e.link_faces[1])
        if a is None or b is None:
            continue
        ra, rb = find(a), find(b)
        if ra != rb:
            parent[max(ra, rb)] = min(ra, rb)
    groups = {}
    for f in faces:
        groups.setdefault(find(idx[f]), []).append(f)
    return sorted(groups.values(), key=lambda g: (-sum(f.calc_area() for f in g), min(f.index for f in g)))


def fix_nonmanifold(bm, max_rounds=50):
    """Resolve edges with > 2 faces in place. Returns {"edges_before", "vertex_splits", "faces_removed", "left"}."""
    out = {"edges_before": sum(1 for e in bm.edges if len(e.link_faces) > 2), "vertex_splits": 0, "faces_removed": 0}
    for _ in range(max_rounds):
        bm.edges.index_update()
        bm.faces.index_update()
        nm = sorted((e for e in bm.edges if len(e.link_faces) > 2), key=lambda e: e.index)
        if not nm:
            break
        e = nm[0]
        done = False
        for v in sorted(e.verts, key=lambda x: x.index):
            fans = _fans(v, e)
            if len(fans) < 2:
                continue
            for fan in fans[1:]:
                new_vs = []
                for f in sorted(fan, key=lambda f: f.index):
                    nv = bmesh.utils.face_vert_separate(f, v)
                    if nv is not v and nv not in new_vs:
                        new_vs.append(nv)
                if len(new_vs) > 1:
                    bmesh.ops.pointmerge(bm, verts=new_vs, merge_co=v.co.copy())
                out["vertex_splits"] += 1
            done = True
            break
        if not done:  # a fin: drop the smallest face beyond two
            fs = sorted(e.link_faces, key=lambda f: (f.calc_area(), f.index))
            bmesh.ops.delete(bm, geom=fs[:len(fs) - 2], context="FACES_ONLY")
            out["faces_removed"] += len(fs) - 2
    for x in [x for x in bm.edges if not x.link_faces]:
        bm.edges.remove(x)
    for x in [x for x in bm.verts if not x.link_faces]:
        bm.verts.remove(x)
    out["left"] = sum(1 for x in bm.edges if len(x.link_faces) > 2)
    return out


# ------------------------------------------------------------------------------------------------ contact lips
def _mesh_bvh(me):
    me.calc_loop_triangles()
    co = np.empty(len(me.vertices) * 3, np.float32)
    me.vertices.foreach_get("co", co)
    tri = np.empty(len(me.loop_triangles) * 3, np.int32)
    me.loop_triangles.foreach_get("vertices", tri)
    co = co.reshape(-1, 3).astype(np.float64)
    return co, BVHTree.FromPolygons(co.tolist(), tri.reshape(-1, 3).tolist(), all_triangles=True)


def _uv_map(face, uv_layer):
    """(p0, J) of the face's 3D->UV affine map (least squares over the face corners)."""
    ps = np.array([tuple(l.vert.co) for l in face.loops], np.float64)
    us = np.array([tuple(l[uv_layer].uv) for l in face.loops], np.float64)
    E = (ps[1:] - ps[0]).T          # 3 x (n-1)
    U = (us[1:] - us[0]).T          # 2 x (n-1)
    return ps[0], us[0], U @ np.linalg.pinv(E)


def add_lips(objs, contact_m=0.0025, overshoot_m=0.0005, tuck_m=0.0002, min_len_m=0.0004, shared_m=1e-7,
             atlas_px=4096, max_uv_px=2.0, double_sided=False, exclude=(), targets_only=(), mode="nearest",
             tangent_factor=1.5, min_area_m2=0.0):
    """Add contact lips to the meshes of objs {part: object} (same frame for all). exclude: parts that get no lips and
    are no contact target; targets_only: parts that are contact targets but get no lips (closed repair caps).
    Returns a report per part."""
    parts = sorted(p for p in objs if p not in exclude)
    geo = {p: _mesh_bvh(objs[p].data) for p in parts}
    # boundary vertex positions of every part (shared-vertex test)
    bnd_pts = {}
    for p in parts:
        bm = bmesh.new()
        bm.from_mesh(objs[p].data)
        pts = sorted({tuple(v.co) for v in bm.verts if v.is_boundary})
        bm.free()
        kd = KDTree(max(1, len(pts)))
        for i, q in enumerate(pts):
            kd.insert(q, i)
        kd.balance()
        bnd_pts[p] = kd
    report = {}
    max_uv = float(max_uv_px) / float(atlas_px)
    for p in parts:
        if p in targets_only:
            continue
        others = [q for q in parts if q != p]
        bm = bmesh.new()
        bm.from_mesh(objs[p].data)
        bm.verts.ensure_lookup_table()
        bm.normal_update()
        uv_layer = bm.loops.layers.uv.active

        def nearest_other(x):
            best = None
            for q in others:
                hit = geo[q][1].find_nearest(x)
                if hit[0] is not None and (best is None or hit[3] < best[1]):
                    best = (hit[0], hit[3], q)
            return best

        def shared(x):
            for q in others:
                if q in targets_only:
                    continue
                _c, _i, d = bnd_pts[q].find(x)
                if d is not None and d <= shared_m:
                    return True
            return False

        edges = sorted((e for e in bm.edges if e.is_boundary), key=lambda e: e.index)
        todo = []
        for e in edges:
            m = (e.verts[0].co + e.verts[1].co) * 0.5
            nb = nearest_other(m)
            if nb is None or nb[1] > contact_m:
                continue
            if nb[1] <= shared_m * 10 and shared(e.verts[0].co) and shared(e.verts[1].co):
                continue  # stitched edge
            todo.append(e)
        # geometric twins (two boundary edges on the same positions, e.g. both sides of a vertex split by
        # fix_nonmanifold): one lip only, else the welded lip corners give edges with three faces
        seen_geo, uniq = set(), []
        for e in todo:
            key = frozenset(tuple(round(c, 9) for c in v.co) for v in e.verts)
            if key in seen_geo:
                continue
            seen_geo.add(key)
            uniq.append(e)
        twins = len(todo) - len(uniq)
        todo = uniq
        lip_co = {}
        for e in todo:
            for v in e.verts:
                if v.index in lip_co:
                    continue
                if shared(v.co):
                    lip_co[v.index] = None
                    continue
                nb = nearest_other(v.co)
                d = (nb[0] - v.co) if nb is not None else Vector((0, 0, 0))
                if mode == "tangent":
                    # continue the part's own surface past the edge (in the adjacent faces' planes, away from them),
                    # long enough to pass the neighbour: closes cracks between parts meeting side by side
                    t_sum = Vector((0, 0, 0))
                    for be in v.link_edges:
                        if not be.is_boundary:
                            continue
                        f = be.link_faces[0]
                        out_ = (be.verts[0].co + be.verts[1].co) * 0.5 - f.calc_center_median()
                        edir = (be.verts[1].co - be.verts[0].co).normalized()
                        out_ = out_ - edir * out_.dot(edir)
                        out_ = out_ - f.normal * out_.dot(f.normal)
                        if out_.length > 1e-12:
                            t_sum += out_.normalized()
                    direction = t_sum.normalized() if t_sum.length > 1e-9 else (d.normalized() if d.length > 1e-7 else Vector((0, 0, 1)))
                    length = min(contact_m, max(min_len_m, tangent_factor * d.length + overshoot_m))
                elif d.length > 1e-7:
                    direction = d.normalized()
                    length = max(d.length + overshoot_m, min_len_m)
                else:  # on the neighbour already: continue the surface outward past the edge
                    f = e.link_faces[0]
                    direction = (v.co - f.calc_center_median())
                    direction = (direction - f.normal * direction.dot(f.normal)).normalized()
                    length = min_len_m
                lip_co[v.index] = v.co + direction * length - v.normal * tuck_m
        new_faces = 0
        tri = 0
        made = {}
        created = []
        for e in todo:
            f = e.link_faces[0]
            # the face traverses the edge a -> b; the lip traverses b -> a (consistent winding)
            loop = next(l for l in f.loops if l.edge is e)
            a, b = loop.vert, loop.link_loop_next.vert
            la, lb = lip_co[a.index], lip_co[b.index]
            if la is None and lb is None:
                continue
            p0, u0, J = _uv_map(f, uv_layer) if uv_layer is not None else (None, None, None)

            def uv_of(vert):
                return next(l[uv_layer].uv.copy() for l in f.loops if l.vert is vert)

            def lip_vert(vert, pos):
                key = (vert.index, f.index)
                nv = bm.verts.new(pos)
                made[key] = nv
                return nv

            corners = [b, a]
            uvs = [uv_of(b), uv_of(a)] if uv_layer is not None else []
            for vert, pos in ((a, la), (b, lb)):
                if pos is None:
                    continue
                corners.append(lip_vert(vert, pos))
                if uv_layer is not None:
                    duv = J @ (np.array(tuple(pos)) - np.array(tuple(vert.co)))
                    n_ = float(np.linalg.norm(duv))
                    if n_ > max_uv:
                        duv = duv * (max_uv / n_)
                    base = uv_of(vert)
                    uvs.append(Vector((base.x + duv[0], base.y + duv[1])))
            if len(corners) < 3:
                continue
            try:
                nf = bm.faces.new(corners)
            except ValueError:
                continue
            nf.material_index = f.material_index
            nf.smooth = True
            created.append(nf)
            if uv_layer is not None:
                for l, uv in zip(nf.loops, uvs):
                    l[uv_layer].uv = uv
            new_faces += 1
            tri += len(corners) - 2
            if double_sided:
                dup = [bm.verts.new(c.co) for c in corners]
                rf = bm.faces.new(list(reversed(dup)))
                rf.material_index = f.material_index
                rf.smooth = True
                created.append(rf)
                if uv_layer is not None:
                    for l, uv in zip(rf.loops, list(reversed(uvs))):
                        l[uv_layer].uv = uv
                new_faces += 1
                tri += len(corners) - 2
        # the lip corners of neighbouring lips of one boundary vertex coincide: weld them (lip vertices only)
        lip_verts = sorted(made.values(), key=lambda v: v.index)
        n_before = len(bm.verts)
        if lip_verts:
            bmesh.ops.remove_doubles(bm, verts=lip_verts, dist=1e-9)
        quads = [x for x in created if x.is_valid and len(x.verts) > 3]
        tri_faces = [x for x in created if x.is_valid and len(x.verts) == 3]
        if quads:
            tri_faces += bmesh.ops.triangulate(bm, faces=quads, quad_method="SHORT_EDGE", ngon_method="EAR_CLIP")["faces"]
        tiny = [x for x in tri_faces if x.is_valid and x.calc_area() < min_area_m2]
        if tiny:
            bmesh.ops.delete(bm, geom=tiny, context="FACES_ONLY")
            bmesh.ops.delete(bm, geom=[x for x in bm.edges if not x.link_faces], context="EDGES")
            bmesh.ops.delete(bm, geom=[x for x in bm.verts if not x.link_faces], context="VERTS")
        tri = len([x for x in tri_faces if x.is_valid])
        bm.to_mesh(objs[p].data)
        objs[p].data.update()
        report[p] = {"boundary_edges": len(edges), "lip_edges": len(todo), "lip_faces": new_faces,
                     "lip_triangles": tri, "lip_vertices_welded": n_before - len(bm.verts) + len(tiny),
                     "tiny_triangles_dropped": len(tiny), "twin_edges_skipped": twins}
        bm.free()
    return report


# ------------------------------------------------------------------------------------------------ sliver fill
def fill_slivers(objs, shared_m=1e-7, gap_m=1e-6, max_steps=12, max_ratio=3.0, exclude=(), min_area_m2=0.0):
    """Close the slivers the stitch leaves where a boundary edge (a, b) of part A has both ends on boundary vertices of
    part B but B's boundary runs from a to b through other vertices (stitch.py skips the insertion when B's arc is longer
    than max_edge_factor x the edge, to avoid folding A's face). A gets a polygon [b, a, p1 .. pk] (pi = B's path
    vertices, new vertices of A at the same positions), triangulated, winding of A; the pi take UVs interpolated along
    a -> b (the sliver samples A's boundary texels). B's path: shortest walk along B's boundary edges from a to b with
    <= max_steps edges and length <= max_ratio x |ab|. Returns a report per part."""
    parts = sorted(p for p in objs if p not in exclude)
    bnd = {}
    for p in parts:
        bm = bmesh.new()
        bm.from_mesh(objs[p].data)
        bm.verts.ensure_lookup_table()
        co = [tuple(v.co) for v in bm.verts]
        adj = {}
        for e in bm.edges:
            if e.is_boundary:
                a, b = e.verts[0].index, e.verts[1].index
                adj.setdefault(a, []).append(b)
                adj.setdefault(b, []).append(a)
        kd = KDTree(max(1, len(adj)))
        for i in sorted(adj):
            kd.insert(co[i], i)
        kd.balance()
        bnd[p] = (co, adj, kd)
        bm.free()
    report = {}
    for p in parts:
        others = [q for q in parts if q != p]
        bm = bmesh.new()
        bm.from_mesh(objs[p].data)
        bm.verts.ensure_lookup_table()
        uv_layer = bm.loops.layers.uv.active
        added, tris, dropped = 0, 0, 0
        for e in sorted((e for e in bm.edges if e.is_boundary), key=lambda e: e.index):
            f = e.link_faces[0]
            loop = next(l for l in f.loops if l.edge is e)
            a, b = loop.vert, loop.link_loop_next.vert
            best = None
            for q in others:
                co, adj, kd = bnd[q]
                ca, ia, da = kd.find(a.co)
                cb, ib, db = kd.find(b.co)
                if da is None or db is None or da > shared_m or db > shared_m or ia == ib:
                    continue
                if ib in adj.get(ia, ()):  # the same edge in q: shared, nothing to fill
                    best = None
                    break
                # shortest boundary walk ia -> ib (BFS by edges, then length)
                prev = {ia: None}
                frontier = [ia]
                for _ in range(max_steps):
                    nxt = []
                    for u in frontier:
                        for w in sorted(adj.get(u, ())):
                            if w not in prev:
                                prev[w] = u
                                nxt.append(w)
                    frontier = nxt
                    if ib in prev or not frontier:
                        break
                if ib not in prev:
                    continue
                path = [ib]
                while prev[path[-1]] is not None:
                    path.append(prev[path[-1]])
                path = path[::-1]  # ia .. ib
                pts = [Vector(co[i]) for i in path]
                length = sum((pts[k + 1] - pts[k]).length for k in range(len(pts) - 1))
                if length > max_ratio * (b.co - a.co).length + 1e-9:
                    continue
                mid = pts[1:-1]
                if not mid or max((x - a.co).cross(b.co - a.co).length / max((b.co - a.co).length, 1e-12)
                                  for x in mid) < gap_m:
                    continue
                if best is None or length < best[0]:
                    best = (length, mid, q)
            if best is None:
                continue
            _l, mid, q = best
            ab = b.co - a.co
            L2 = max(ab.length_squared, 1e-18)
            uva = next(l[uv_layer].uv.copy() for l in f.loops if l.vert is a) if uv_layer else None
            uvb = next(l[uv_layer].uv.copy() for l in f.loops if l.vert is b) if uv_layer else None
            new_vs = [bm.verts.new(x) for x in mid]
            try:
                nf = bm.faces.new([b, a] + new_vs)
            except ValueError:
                continue
            nf.material_index = f.material_index
            nf.smooth = True
            if uv_layer is not None:
                for l in nf.loops:
                    t = min(max((l.vert.co - a.co).dot(ab) / L2, 0.0), 1.0)
                    l[uv_layer].uv = uva.lerp(uvb, t)
            res = bmesh.ops.triangulate(bm, faces=[nf], quad_method="SHORT_EDGE", ngon_method="EAR_CLIP")
            new_tris = [x for x in res["faces"] if x.is_valid]
            tiny = [x for x in new_tris if x.calc_area() < min_area_m2]
            if tiny:
                bmesh.ops.delete(bm, geom=tiny, context="FACES_ONLY")
                bmesh.ops.delete(bm, geom=[x for x in new_vs if x.is_valid and not x.link_faces], context="VERTS")
                dropped += len(tiny)
            added += 1
            tris += len(new_tris) - len(tiny)
        for x in [x for x in bm.edges if not x.link_faces]:
            bm.edges.remove(x)
        bm.to_mesh(objs[p].data)
        objs[p].data.update()
        bm.free()
        report[p] = {"slivers": added, "triangles": tris, "tiny_triangles_dropped": dropped}
    return report


# ------------------------------------------------------------------------------------------------ exposed back faces
def game_directions(azimuth_step_deg=10.0, elevations_deg=(45.0, 55.0, 65.0)):
    """Unit directions from the figure toward a game camera (azimuth 0 = in front, -Y; elevation above the ground)."""
    out = []
    for el in elevations_deg:
        e = np.radians(el)
        for az in np.arange(0.0, 360.0, azimuth_step_deg):
            a = np.radians(az)
            out.append((float(np.sin(a) * np.cos(e)), float(-np.cos(a) * np.cos(e)), float(np.sin(e))))
    return np.array(out)


def exposed_backfaces(objs, directions, bary_steps=3, eps_m=2e-5, far_m=10.0, exclude=()):
    """Triangles whose BACK side is seen from outside along one of the directions: a ray from a sample point of the
    triangle (barycentric grid with bary_steps subdivisions, nudged eps_m to the back side) toward the direction escapes
    every part (all objs, both face sides). With TwoSided=false such a triangle is culled and the background shows
    through (a flap seen from behind, or the far wall behind a crack): see_through.py counts exactly these pixels.
    Returns {part: sorted polygon indices} (loop-triangle polygons of the triangulated game mesh)."""
    from mathutils.bvhtree import BVHTree as _B
    allv, allt, owner, off = [], [], [], 0
    per = {}
    for p in sorted(objs):
        me = objs[p].data
        me.calc_loop_triangles()
        co = np.empty(len(me.vertices) * 3, np.float32)
        me.vertices.foreach_get("co", co)
        co = co.reshape(-1, 3).astype(np.float64)
        tri = np.empty(len(me.loop_triangles) * 3, np.int32)
        me.loop_triangles.foreach_get("vertices", tri)
        tri = tri.reshape(-1, 3)
        poly = np.empty(len(me.loop_triangles), np.int32)
        me.loop_triangles.foreach_get("polygon_index", poly)
        per[p] = (co, tri, poly)
        allv.append(co)
        allt.append(tri + off)
        off += len(co)
    bvh = _B.FromPolygons(np.concatenate(allv).tolist(), np.concatenate(allt).tolist(), all_triangles=True)
    # barycentric sample grid (interior + edges, corners pulled 10 % inward)
    bs = []
    n = int(bary_steps)
    for i in range(n + 1):
        for j in range(n + 1 - i):
            w = np.array([i, j, n - i - j], np.float64) / n
            bs.append(0.8 * w + 0.2 / 3.0)
    bs = np.array(bs)
    D = np.asarray(directions, np.float64)
    out = {}
    for p in sorted(objs):
        if p in exclude:
            continue
        co, tri, poly = per[p]
        a, b, c = co[tri[:, 0]], co[tri[:, 1]], co[tri[:, 2]]
        nrm = np.cross(b - a, c - a)
        ln = np.linalg.norm(nrm, axis=1)
        nrm = nrm / np.maximum(ln, 1e-30)[:, None]
        dots = nrm @ D.T  # (T, dirs): < 0 = back side faces that camera
        hit_polys = set()
        for t in np.nonzero((dots < -0.02).any(1) & (ln > 1e-14))[0].tolist():
            pts = bs @ np.stack([a[t], b[t], c[t]])
            found = False
            for k in np.nonzero(dots[t] < -0.02)[0].tolist():
                d = Vector(D[k])
                for q in pts:
                    o = Vector(q - nrm[t] * eps_m) + d * eps_m
                    if bvh.ray_cast(o, d, far_m)[0] is None:
                        found = True
                        break
                if found:
                    break
            if found:
                hit_polys.add(int(poly[t]))
        out[p] = sorted(hit_polys)
    return out


def duplicate_reversed(obj, polys):
    """Detached reversed copies of the given polygons of obj (own vertices at the same positions, same UVs, material,
    smooth flag): the back side of a thin flap gets a front face. Returns {new vertex index: source vertex index}."""
    me = obj.data
    bm = bmesh.new()
    bm.from_mesh(me)
    bm.faces.ensure_lookup_table()
    bm.verts.ensure_lookup_table()
    uv_layer = bm.loops.layers.uv.active
    nv0 = len(bm.verts)
    vmap = {}
    src_faces = [bm.faces[pi] for pi in polys]
    for f in src_faces:
        loops = list(f.loops)[::-1]
        vs = []
        for l in loops:
            nv = bm.verts.new(l.vert.co)
            vs.append(nv)
        nf = bm.faces.new(vs)
        nf.material_index = f.material_index
        nf.smooth = f.smooth
        if uv_layer is not None:
            for nl, l in zip(nf.loops, loops):
                nl[uv_layer].uv = l[uv_layer].uv
        for nv, l in zip(vs, loops):
            vmap[nv] = l.vert.index
    bm.verts.index_update()
    out = {nv.index: src for nv, src in vmap.items()}
    bm.to_mesh(me)
    me.update()
    bm.free()
    return out


# ------------------------------------------------------------------------------------------------ inner occluder core
def _fib_dirs(n):
    k = np.arange(n) + 0.5
    phi = np.arccos(1 - 2 * k / n)
    th = np.pi * (1 + 5 ** 0.5) * k
    return np.stack([np.cos(th) * np.sin(phi), np.sin(th) * np.sin(phi), np.cos(phi)], 1)


def inner_core(objs, box_parts, voxel_m=0.004, margin_m=0.003, rays=14, min_inside_votes=12, smooth_iter=3,
               name="core", keep_largest=True):
    """Closed occluder inside the body (H2.1): voxel centres in the bounding box of box_parts that lie >= margin_m from
    every part surface and see the inner (back) side of the surface first along >= min_inside_votes of `rays`
    directions are "inside"; the faces between inside and outside voxels form a closed blocky shell (outward winding),
    smoothed (Laplacian, smooth_iter) and checked to stay >= margin_m / 2 from the surfaces. A camera ray that slips
    through a sub-millimetre crack between parts meets this shell's front face instead of culled back faces.
    Returns (bpy mesh, info)."""
    from mathutils.bvhtree import BVHTree as _B
    allv, allt, off = [], [], 0
    for p in sorted(objs):
        me = objs[p].data
        me.calc_loop_triangles()
        co = np.empty(len(me.vertices) * 3, np.float32)
        me.vertices.foreach_get("co", co)
        tri = np.empty(len(me.loop_triangles) * 3, np.int32)
        me.loop_triangles.foreach_get("vertices", tri)
        allv.append(co.reshape(-1, 3).astype(np.float64))
        allt.append(tri.reshape(-1, 3) + off)
        off += len(allv[-1])
    V = np.concatenate(allv)
    bvh = _B.FromPolygons(V.tolist(), np.concatenate(allt).tolist(), all_triangles=True)
    pts_box = []
    for p in box_parts:
        me = objs[p].data
        co = np.empty(len(me.vertices) * 3, np.float32)
        me.vertices.foreach_get("co", co)
        pts_box.append(co.reshape(-1, 3))
    pb = np.concatenate(pts_box).astype(np.float64)
    lo, hi = pb.min(0), pb.max(0)
    n = np.ceil((hi - lo) / voxel_m).astype(int) + 1
    D = _fib_dirs(rays)
    inside = np.zeros(tuple(n), bool)
    for i in range(n[0]):
        for j in range(n[1]):
            for k in range(n[2]):
                c = Vector(lo + np.array([i, j, k]) * voxel_m)
                hit = bvh.find_nearest(c)
                if hit[0] is None or hit[3] < margin_m:
                    continue
                votes = 0
                for r in range(rays):
                    d = Vector(D[r])
                    loc, nrm, _idx, _dist = bvh.ray_cast(c, d, 10.0)
                    if loc is not None and nrm.dot(d) > 0:
                        votes += 1
                    elif r - votes >= rays - min_inside_votes + 1:
                        break
                inside[i, j, k] = votes >= min_inside_votes
    if keep_largest and inside.any():
        from collections import deque
        lab = np.full(inside.shape, -1, np.int64)
        sizes = []
        for idx in zip(*np.nonzero(inside)):
            if lab[idx] >= 0:
                continue
            q = deque([idx])
            lab[idx] = len(sizes)
            cnt = 0
            while q:
                x = q.popleft()
                cnt += 1
                for dx in ((1, 0, 0), (-1, 0, 0), (0, 1, 0), (0, -1, 0), (0, 0, 1), (0, 0, -1)):
                    y = (x[0] + dx[0], x[1] + dx[1], x[2] + dx[2])
                    if all(0 <= y[a] < n[a] for a in range(3)) and inside[y] and lab[y] < 0:
                        lab[y] = len(sizes)
                        q.append(y)
            sizes.append(cnt)
        inside = lab == int(np.argmax(sizes))
    # boundary faces of the voxel set (outward winding), shared corner vertices
    bm = bmesh.new()
    vid = {}

    def vert(ci):
        v = vid.get(ci)
        if v is None:
            v = bm.verts.new(tuple(lo + (np.array(ci) - 0.5) * voxel_m))
            vid[ci] = v
        return v

    quads = {  # neighbour offset: corner offsets (counter-clockwise seen from outside)
        (1, 0, 0): ((1, 0, 0), (1, 1, 0), (1, 1, 1), (1, 0, 1)),
        (-1, 0, 0): ((0, 0, 0), (0, 0, 1), (0, 1, 1), (0, 1, 0)),
        (0, 1, 0): ((0, 1, 0), (0, 1, 1), (1, 1, 1), (1, 1, 0)),
        (0, -1, 0): ((0, 0, 0), (1, 0, 0), (1, 0, 1), (0, 0, 1)),
        (0, 0, 1): ((0, 0, 1), (1, 0, 1), (1, 1, 1), (0, 1, 1)),
        (0, 0, -1): ((0, 0, 0), (0, 1, 0), (1, 1, 0), (1, 0, 0)),
    }
    for idx in sorted(zip(*np.nonzero(inside))):
        for dn, corners in quads.items():
            y = (idx[0] + dn[0], idx[1] + dn[1], idx[2] + dn[2])
            if all(0 <= y[a] < n[a] for a in range(3)) and inside[y]:
                continue
            bm.faces.new([vert((idx[0] + c[0], idx[1] + c[1], idx[2] + c[2])) for c in corners])
    info = {"voxel_m": voxel_m, "margin_m": margin_m, "grid": [int(x) for x in n], "voxels_inside": int(inside.sum()),
            "rays": rays, "min_inside_votes": min_inside_votes}
    if not bm.faces:
        bm.free()
        return None, info
    # non-manifold corners of the voxel surface (two voxels touching at an edge): separate them by moving on
    for _ in range(int(smooth_iter)):
        new = {}
        for v in bm.verts:
            nb = [e.other_vert(v).co for e in v.link_edges]
            if nb:
                new[v] = v.co * 0.5 + sum(nb, Vector()) / len(nb) * 0.5
        for v, c in new.items():
            v.co = c
    bmesh.ops.triangulate(bm, faces=bm.faces[:], quad_method="SHORT_EDGE", ngon_method="EAR_CLIP")
    me = bpy_mesh_from(bm, name)
    bm.free()
    co = np.empty(len(me.vertices) * 3, np.float32)
    me.vertices.foreach_get("co", co)
    dmin = min(bvh.find_nearest(Vector(c))[3] for c in co.reshape(-1, 3))
    info.update({"triangles": len(me.polygons), "min_distance_to_surface_m": round(float(dmin), 5)})
    return me, info


def bpy_mesh_from(bm, name):
    import bpy
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    me.update()
    return me


def finish_core(scene, me, target_triangles, surfaces, margin_m, remesh_voxel_m=0.003):
    """Decimate the core mesh (COLLAPSE) to target_triangles in a temporary object, fix non-manifold edges, pull any
    vertex closer than margin_m / 2 to a surface back along its inward normal. Returns (mesh, info)."""
    import bpy
    from mathutils.bvhtree import BVHTree as _B
    obj = bpy.data.objects.new("h2_core_tmp", me)
    scene.collection.objects.link(obj)
    tris = len(me.polygons)
    # voxel remesh first: the blocky voxel shell has edges shared by 4 faces where two voxels touch along an edge;
    # the remesh rebuilds a closed manifold surface of the same volume
    rm = obj.modifiers.new("remesh", "REMESH")
    rm.mode = "VOXEL"
    rm.voxel_size = float(remesh_voxel_m)
    rm.adaptivity = 0.0
    rm.use_smooth_shade = True
    with bpy.context.temp_override(object=obj, active_object=obj):
        bpy.ops.object.modifier_apply(modifier=rm.name)
    tris_remesh = len(me.polygons)
    if len(me.polygons) > target_triangles:
        mod = obj.modifiers.new("dec", "DECIMATE")
        mod.decimate_type = "COLLAPSE"
        mod.use_collapse_triangulate = True
        mod.ratio = float(target_triangles) / sum(len(q.vertices) - 2 for q in me.polygons)
        with bpy.context.temp_override(object=obj, active_object=obj):
            bpy.ops.object.modifier_apply(modifier=mod.name)
    bm = bmesh.new()
    bm.from_mesh(me)
    # the collapse decimation can leave closed two-triangle pockets (two faces on the same three vertices): drop them
    by_set = {}
    for f in bm.faces:
        by_set.setdefault(tuple(sorted(v.index for v in f.verts)), []).append(f)
    dup = [f for fs in by_set.values() if len(fs) > 1 for f in fs]
    if dup:
        bmesh.ops.delete(bm, geom=dup, context="FACES_ONLY")
        bmesh.ops.delete(bm, geom=[e for e in bm.edges if not e.link_faces], context="EDGES")
        bmesh.ops.delete(bm, geom=[v for v in bm.verts if not v.link_faces], context="VERTS")
    nm = fix_nonmanifold(bm)
    nm["duplicate_faces_removed"] = len(dup)
    allv, allt, off = [], [], 0
    for o in surfaces:
        m2 = o.data
        m2.calc_loop_triangles()
        co = np.empty(len(m2.vertices) * 3, np.float32)
        m2.vertices.foreach_get("co", co)
        tri = np.empty(len(m2.loop_triangles) * 3, np.int32)
        m2.loop_triangles.foreach_get("vertices", tri)
        allv.append(co.reshape(-1, 3).astype(np.float64))
        allt.append(tri.reshape(-1, 3) + off)
        off += len(allv[-1])
    bvh = _B.FromPolygons(np.concatenate(allv).tolist(), np.concatenate(allt).tolist(), all_triangles=True)
    bm.normal_update()
    pulled = 0
    for _ in range(4):
        moved = 0
        for v in bm.verts:
            hit = bvh.find_nearest(v.co)
            if hit[0] is not None and hit[3] < margin_m * 0.5:
                v.co = v.co - v.normal * (margin_m * 0.5 - hit[3] + 1e-4)
                moved += 1
        pulled += moved
        if not moved:
            break
    # the collapse decimation can bridge a concavity (chin / neck): a core triangle that crosses a body surface would
    # show from outside. Vertices of crossing triangles move inward (step_m per round), what still crosses is removed
    step = margin_m * 0.3
    shrunk = 0
    for _ in range(12):
        bm.faces.ensure_lookup_table()
        cb = _B.FromBMesh(bm)
        pairs = cb.overlap(bvh)
        if not pairs:
            break
        bad = sorted({v.index for fi, _j in pairs for v in bm.faces[fi].verts})
        bm.normal_update()
        bm.verts.ensure_lookup_table()
        for vi in bad:
            v = bm.verts[vi]
            v.co = v.co - v.normal * step
        shrunk += len(bad)
    bm.faces.ensure_lookup_table()
    left = sorted({fi for fi, _j in _B.FromBMesh(bm).overlap(bvh)})
    if left:
        bmesh.ops.delete(bm, geom=[bm.faces[i] for i in left], context="FACES_ONLY")
        bmesh.ops.delete(bm, geom=[e for e in bm.edges if not e.link_faces], context="EDGES")
        bmesh.ops.delete(bm, geom=[v for v in bm.verts if not v.link_faces], context="VERTS")
    dmin = min(bvh.find_nearest(v.co)[3] for v in bm.verts)
    bm.to_mesh(me)
    me.update()
    bm.free()
    scene.collection.objects.unlink(obj)
    bpy.data.objects.remove(obj)
    return me, {"triangles_voxel": tris, "triangles_remesh": tris_remesh, "triangles": len(me.polygons),
                "nonmanifold_fix": nm,
                "vertices_pulled_in": pulled, "vertex_moves_against_crossing": shrunk,
                "crossing_faces_removed": len(left), "min_distance_to_surface_m": round(float(dmin), 5)}
