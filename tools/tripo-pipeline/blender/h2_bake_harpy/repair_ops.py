"""Geometry repairs of a Tripo high-poly in the authored frame (headless Blender; used by stage_lowpoly.py and by the
repair probes). Every operation is profile driven (section "repair") and deterministic (explicit vertex/face order).

* trim_part(obj, boxes)       deletes the faces of one part whose centroid lies in any of the boxes (authored frame,
                               source scale); used for the Janus-hood remnant of tripo_part_1;
* ellipsoid_mesh(...)          closed UV ellipsoid built explicitly (bmesh.ops.create_uvsphere changed its loop order
                               from run to run, measured 2026-09-29);
* copy_patch(src, boxes, ...)  copies the faces of a part whose centroid lies in the boxes (with the part's UVs and
                               material) into a new object, placed by scale/rotation about a pivot and a translation;
* open_loops(obj, min_z)       open boundary loops of a part (length, bounds) for the report;
* loop_cap(obj, name, near)    closed domed cap over one open boundary loop of a part (the loop nearest a point):
                               walked, resampled by arc length, dome over the best-fit plane, outer ring pushed out
                               and down so it tucks under the jagged Tripo rim, closed underside (an outside ray can
                               never meet one of its back faces first).
"""

import math

import bmesh
import bpy
import numpy as np
from mathutils import Vector


def in_box(co, box):
    lo, hi = np.array(box["min"], dtype=np.float64), np.array(box["max"], dtype=np.float64)
    return np.all((co >= lo) & (co <= hi), axis=1)


def face_centroids(me):
    """Centroid (mean of the corner positions) of every polygon, float64, polygon order."""
    co = np.empty(len(me.vertices) * 3, np.float32)
    me.vertices.foreach_get("co", co)
    co = co.reshape(-1, 3).astype(np.float64)
    lv = np.empty(len(me.loops), np.int32)
    me.loops.foreach_get("vertex_index", lv)
    ls = np.empty(len(me.polygons), np.int32)
    me.polygons.foreach_get("loop_start", ls)
    lt = np.empty(len(me.polygons), np.int32)
    me.polygons.foreach_get("loop_total", lt)
    poly_of_loop = np.repeat(np.arange(len(me.polygons)), lt)
    sums = np.zeros((len(me.polygons), 3))
    np.add.at(sums, poly_of_loop, co[lv])
    return sums / lt[:, None]


def trim_part(obj, boxes):
    """Delete the faces whose centroid lies inside any box; loose vertices/edges left by them are removed too.
    Returns {"faces_removed", "faces_before", "area_removed_m2", "removed_bounds_m"}."""
    me = obj.data
    cen = face_centroids(me)
    kill = np.zeros(len(cen), bool)
    for box in boxes:
        kill |= in_box(cen, box)
    area = np.empty(len(me.polygons), np.float32)
    me.polygons.foreach_get("area", area)
    info = {"faces_before": int(len(cen)), "faces_removed": int(kill.sum()),
            "area_removed_m2": round(float(area[kill].sum()), 7)}
    if kill.any():
        info["removed_bounds_m"] = {"min": [round(float(c), 4) for c in cen[kill].min(0)],
                                    "max": [round(float(c), 4) for c in cen[kill].max(0)]}
    bm = bmesh.new()
    bm.from_mesh(me)
    bm.faces.ensure_lookup_table()
    bmesh.ops.delete(bm, geom=[bm.faces[i] for i in np.nonzero(kill)[0].tolist()], context="FACES_ONLY")
    loose_e = [e for e in bm.edges if not e.link_faces]
    bmesh.ops.delete(bm, geom=loose_e, context="EDGES")
    loose_v = [v for v in bm.verts if not v.link_faces]
    bmesh.ops.delete(bm, geom=loose_v, context="VERTS")
    bm.to_mesh(me)
    bm.free()
    me.update()
    return info


def ellipsoid_mesh(name, centre, radii, nu, nv):
    """UV ellipsoid built explicitly (vertex, face and loop order fixed). Poles are triangle fans,
    UV = (column / nu, 1 - ring / nv)."""
    cx, cy, cz = centre
    rx, ry, rz = radii
    verts = [(cx, cy, cz + rz)]
    for i in range(1, nv):
        th = math.pi * i / nv
        for j in range(nu):
            ph = 2 * math.pi * j / nu
            verts.append((cx + rx * math.sin(th) * math.cos(ph), cy + ry * math.sin(th) * math.sin(ph), cz + rz * math.cos(th)))
    verts.append((cx, cy, cz - rz))
    bottom = len(verts) - 1

    def ring(i, j):
        return 1 + (i - 1) * nu + (j % nu)

    faces, uvs = [], []
    for j in range(nu):
        faces.append((0, ring(1, j), ring(1, j + 1)))
        uvs.append((((j + 0.5) / nu, 1.0), (j / nu, 1 - 1 / nv), ((j + 1) / nu, 1 - 1 / nv)))
    for i in range(1, nv - 1):
        for j in range(nu):
            faces.append((ring(i, j), ring(i + 1, j), ring(i + 1, j + 1), ring(i, j + 1)))
            uvs.append(((j / nu, 1 - i / nv), (j / nu, 1 - (i + 1) / nv), ((j + 1) / nu, 1 - (i + 1) / nv),
                        ((j + 1) / nu, 1 - i / nv)))
    for j in range(nu):
        faces.append((bottom, ring(nv - 1, j + 1), ring(nv - 1, j)))
        uvs.append((((j + 0.5) / nu, 0.0), ((j + 1) / nu, 1 / nv), (j / nu, 1 / nv)))
    me = bpy.data.meshes.new(name)
    me.from_pydata(verts, [], faces)
    layer = me.uv_layers.new(name="UVMap")
    flat = [c for f in uvs for c in f]
    for li, uv in enumerate(flat):
        layer.data[li].uv = uv
    me.update()
    centre_v = Vector(centre)
    flip = [p.index for p in me.polygons if (Vector(p.center) - centre_v).dot(p.normal) < 0]
    if flip:
        raise RuntimeError("ellipsoid winding: %d inward faces" % len(flip))
    return me


def open_loops(obj, min_z=None, weld=1e-6, top=None):
    """Open boundary loops of a mesh (after welding by distance): length, edge count, bounds, mean; sorted by length."""
    bm = bmesh.new()
    bm.from_mesh(obj.data)
    bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=weld)
    parent = {}

    def find(a):
        while parent.setdefault(a, a) != a:
            parent[a] = parent[parent[a]]
            a = parent[a]
        return a

    open_e = [e for e in bm.edges if len(e.link_faces) == 1]
    for e in open_e:
        parent[find(e.verts[0].index)] = find(e.verts[1].index)
    groups = {}
    for e in open_e:
        groups.setdefault(find(e.verts[0].index), []).append(e)
    loops = []
    for es in groups.values():
        pts = np.array([tuple(v.co) for e in es for v in e.verts])
        if min_z is not None and pts[:, 2].max() < min_z:
            continue
        loops.append({"length_m": round(float(sum(e.calc_length() for e in es)), 4), "edges": len(es),
                      "min_m": [round(float(c), 4) for c in pts.min(0)],
                      "max_m": [round(float(c), 4) for c in pts.max(0)],
                      "mean_m": [round(float(c), 4) for c in pts.mean(0)]})
    bm.free()
    loops.sort(key=lambda l: (-l["length_m"], l["mean_m"]))
    return loops[:top] if top else loops


def drop_custom_normals(me):
    """Remove the custom corner normals (Blender 5: attribute "custom_normal") -> smooth/sharp-edge normals."""
    for a in list(me.attributes):
        if a.name == "custom_normal":
            me.attributes.remove(a)
    me.update()


def copy_patch(src, name, boxes, pivot=(0.0, 0.0, 0.0), scale=(1.0, 1.0, 1.0), rotate_deg=(0.0, 0.0, 0.0),
               translate=(0.0, 0.0, 0.0), exclude_boxes=(), solidify_m=0.0):
    """New object <name>: the faces of src with centroid in any box (and in no exclude box), same UVs/material,
    transformed p' = R (S (p - pivot)) + pivot + translate (R = XYZ Euler, degrees). solidify_m > 0: the sheet is
    given a reversed backing sheet that far behind it (along -vertex normal), so from behind the patch shows the
    backing's front faces instead of culled ones (backing keeps the UVs; separate UV islands). Returns (obj, info)."""
    from mathutils import Euler, Matrix
    me = src.data.copy()
    me.name = name
    cen = face_centroids(me)
    keep = np.zeros(len(cen), bool)
    for box in boxes:
        keep |= in_box(cen, box)
    for box in exclude_boxes:
        keep &= ~in_box(cen, box)
    bm = bmesh.new()
    bm.from_mesh(me)
    bm.faces.ensure_lookup_table()
    bmesh.ops.delete(bm, geom=[bm.faces[i] for i in np.nonzero(~keep)[0].tolist()], context="FACES_ONLY")
    bmesh.ops.delete(bm, geom=[e for e in bm.edges if not e.link_faces], context="EDGES")
    bmesh.ops.delete(bm, geom=[v for v in bm.verts if not v.link_faces], context="VERTS")
    bm.to_mesh(me)
    bm.free()
    piv = Vector(pivot)
    m = (Matrix.Translation(piv + Vector(translate)) @ Euler([math.radians(a) for a in rotate_deg], "XYZ").to_matrix().to_4x4()
         @ Matrix.Diagonal(tuple(scale) + (1.0,)) @ Matrix.Translation(-piv))
    me.transform(m)
    if tuple(scale) != (1.0, 1.0, 1.0) and scale[0] * scale[1] * scale[2] < 0:
        me.flip_normals()
    me.update()
    faces_sheet = len(me.polygons)
    if solidify_m > 0:
        # backing sheet: welded copy of the sheet moved solidify_m along -vertex normal, faces reversed; no rim
        # faces, so the backing's UV islands stay separate islands (same UVs, packed apart by stage_uv) and every
        # face keeps a Tripo texel; custom normals are dropped (smooth vertex normals of the welded sheet)
        drop_custom_normals(me)
        bm = bmesh.new()
        bm.from_mesh(me)
        bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=1e-7)
        bm.normal_update()
        # explicit element order (sets of BMesh elements iterate by memory address = run-dependent); vert_map of
        # bmesh.ops.duplicate maps both ways (old -> new and new -> old), so only the original vertices are read
        orig_faces = list(bm.faces)
        orig_verts = list(bm.verts)
        normals = [v.normal.copy() for v in orig_verts]
        dup = bmesh.ops.duplicate(bm, geom=orig_faces + list(bm.edges) + orig_verts)
        vmap = dup["vert_map"]
        for v_old, n_old in zip(orig_verts, normals):
            v_new = vmap[v_old]
            v_new.co = v_old.co - n_old * float(solidify_m)
        new_faces = [f for f in dup["geom"] if isinstance(f, bmesh.types.BMFace)]
        bmesh.ops.reverse_faces(bm, faces=new_faces, flip_multires=False)
        bm.to_mesh(me)
        bm.free()
        for poly in me.polygons:
            poly.use_smooth = True
        me.update()
    obj = bpy.data.objects.new(name, me)
    area = np.empty(len(me.polygons), np.float32)
    me.polygons.foreach_get("area", area)
    info = {"source": src.name, "faces": len(me.polygons), "faces_sheet": faces_sheet, "solidify_m": solidify_m,
            "area_m2": round(float(area.sum()), 7),
            "matrix": [[round(float(c), 7) for c in row] for row in m]}
    return obj, info


def _frame(n, flow):
    """Orthonormal (d, e, n): d = flow projected onto the plane of n (fallback -Z, then +Y), e = n x d."""
    n = np.asarray(n, np.float64)
    n = n / np.linalg.norm(n)
    for f in (flow, (0.0, 0.0, -1.0), (0.0, 1.0, 0.0)):
        d = np.asarray(f, np.float64) - np.dot(f, n) * n
        if np.linalg.norm(d) > 1e-6:
            d = d / np.linalg.norm(d)
            return d, np.cross(n, d), n
    raise RuntimeError("_frame: degenerate flow")


def conform_fill(src, name, boxes, surface, targets, exclude_boxes=(), source_flow=(0.0, 0.0, -1.0),
                 lift_m=0.001, height_scale=1.0, probe_m=0.05, drop_outside=False):
    """Feather clusters laid on a repair surface (H2.1 nape fill). The faces of `src` whose centroid lies in `boxes`
    (and in no exclude box) are one source cluster with its Tripo UVs and material; its frame is the area-weighted
    centroid c_s, mean normal n_s and the flow d_s = source_flow in the cluster plane. Each target
    {"at": point, "flow": direction, "scale": s, "turn_deg": a} is projected onto the nearest point of `surface`
    (closed repair cap: its outside), and the cluster is laid there: a vertex with cluster coordinates (a, b, h) goes
    to S(t + s*(a d_t + b e_t) rotated by turn_deg about n_t) + N * (lift_m + height_scale * s * (h - h_min)), where S
    is the surface point hit by a ray along -n_t (the plane point where the ray misses) and N the surface normal
    there, so the lowest point of every copy sits lift_m above the surface and the feathers keep their relief and their
    own flow direction (down the nape). drop_outside: faces of a copy whose corners all miss the surface (beyond its
    rim, where the tangent plane would carry them away from the surface) are removed. All copies are one new object
    `name`. Deterministic (explicit orders). Returns (obj, info)."""
    from mathutils.bvhtree import BVHTree
    me_src = src.data.copy()
    cen = face_centroids(me_src)
    keep = np.zeros(len(cen), bool)
    for box in boxes:
        keep |= in_box(cen, box)
    for box in exclude_boxes:
        keep &= ~in_box(cen, box)
    bm = bmesh.new()
    bm.from_mesh(me_src)
    bm.faces.ensure_lookup_table()
    bmesh.ops.delete(bm, geom=[bm.faces[i] for i in np.nonzero(~keep)[0].tolist()], context="FACES_ONLY")
    bmesh.ops.delete(bm, geom=[e for e in bm.edges if not e.link_faces], context="EDGES")
    bmesh.ops.delete(bm, geom=[v for v in bm.verts if not v.link_faces], context="VERTS")
    bm.to_mesh(me_src)
    bm.free()
    drop_custom_normals(me_src)
    me_src.update()
    co = np.empty(len(me_src.vertices) * 3, np.float32)
    me_src.vertices.foreach_get("co", co)
    co = co.reshape(-1, 3).astype(np.float64)
    fc = face_centroids(me_src)
    fa = np.empty(len(me_src.polygons), np.float32)
    me_src.polygons.foreach_get("area", fa)
    fn = np.empty(len(me_src.polygons) * 3, np.float32)
    me_src.polygons.foreach_get("normal", fn)
    fn = fn.reshape(-1, 3).astype(np.float64)
    fa = fa.astype(np.float64)
    c_s = (fc * fa[:, None]).sum(0) / fa.sum()
    n_s = (fn * fa[:, None]).sum(0)
    d_s, e_s, n_s = _frame(n_s, source_flow)
    rel_ = co - c_s
    la, lb, lh = rel_ @ d_s, rel_ @ e_s, rel_ @ n_s
    h_min = float(lh.min())
    sv, st = [], []
    sme = surface.data
    sco = np.empty(len(sme.vertices) * 3, np.float32)
    sme.vertices.foreach_get("co", sco)
    sco = sco.reshape(-1, 3).astype(np.float64)
    sme.calc_loop_triangles()
    stri = np.empty(len(sme.loop_triangles) * 3, np.int32)
    sme.loop_triangles.foreach_get("vertices", stri)
    bvh = BVHTree.FromPolygons(sco.tolist(), stri.reshape(-1, 3).tolist(), all_triangles=True)
    parts_me = []
    info_t = []
    misses = 0
    for k, tg in enumerate(targets):
        hit = bvh.find_nearest(Vector(tg["at"]))
        t_c, n_t = np.array(hit[0]), np.array(hit[1])
        d_t, e_t, n_t = _frame(n_t, tg.get("flow", (0.0, 0.0, -1.0)))
        ang = math.radians(float(tg.get("turn_deg", 0.0)))
        d_r = d_t * math.cos(ang) + e_t * math.sin(ang)
        e_r = np.cross(n_t, d_r)
        s = float(tg.get("scale", 1.0))
        new = np.empty_like(co)
        missed = np.zeros(len(co), bool)
        for i in range(len(co)):
            q = t_c + s * (la[i] * d_r + lb[i] * e_r)
            loc, nrm, _idx, _d = bvh.ray_cast(Vector(q + n_t * probe_m), Vector(-n_t), 2 * probe_m)
            if loc is None:
                misses += 1
                missed[i] = True
                base, nn = q, n_t
            else:
                base, nn = np.array(loc), np.array(nrm)
                if nn @ n_t < 0:
                    nn = -nn
            new[i] = base + nn * (lift_m + float(tg.get("height_scale", height_scale)) * s * (lh[i] - h_min))
        m = me_src.copy()
        m.vertices.foreach_set("co", new.astype(np.float32).reshape(-1))
        m.update()
        dropped = 0
        if drop_outside and missed.any():
            bmd = bmesh.new()
            bmd.from_mesh(m)
            bmd.faces.ensure_lookup_table()
            gone = [f for f in bmd.faces if all(missed[v.index] for v in f.verts)]
            dropped = len(gone)
            bmesh.ops.delete(bmd, geom=gone, context="FACES_ONLY")
            bmesh.ops.delete(bmd, geom=[e for e in bmd.edges if not e.link_faces], context="EDGES")
            bmesh.ops.delete(bmd, geom=[v for v in bmd.verts if not v.link_faces], context="VERTS")
            bmd.to_mesh(m)
            bmd.free()
            m.update()
        parts_me.append(m)
        info_t.append({"at": [round(float(x), 4) for x in tg["at"]], "on_surface": [round(float(x), 4) for x in t_c],
                       "normal": [round(float(x), 4) for x in n_t], "scale": s, "turn_deg": float(tg.get("turn_deg", 0.0)),
                       "faces_dropped_outside": dropped})
    # join the copies (explicit order) into one mesh
    bm = bmesh.new()
    for m in parts_me:
        bm.from_mesh(m)
    out = bpy.data.meshes.new(name)
    bm.to_mesh(out)
    bm.free()
    for m in parts_me:
        bpy.data.meshes.remove(m)
    for mat in me_src.materials:
        # own copy of the source material (same images): stage_bake rewires the emission of each HP part's material, and a
        # recolour rule of the source part (bake.recolor) must not be undone by, or leak into, the fill
        mc = mat.copy()
        mc.name = "M_H2_%s" % name.replace("HP_", "")
        out.materials.append(mc)
    for poly in out.polygons:
        poly.use_smooth = True
    out.update()
    bpy.data.meshes.remove(me_src)
    obj = bpy.data.objects.new(name, out)
    area = np.empty(len(out.polygons), np.float32)
    out.polygons.foreach_get("area", area)
    info = {"source": src.name, "boxes": boxes, "faces_per_copy": int(keep.sum()), "faces": len(out.polygons),
            "copies": len(targets), "source_centre_m": [round(float(x), 4) for x in c_s],
            "source_normal": [round(float(x), 4) for x in n_s], "source_height_range_m": round(float(lh.max() - h_min), 4),
            "ray_misses": int(misses), "lift_m": lift_m, "height_scale": height_scale,
            "area_m2": round(float(area.sum()), 7), "targets": info_t}
    return obj, info


def boundary_loops_ordered(me, weld=1e-6):
    """Open boundary loops of a mesh as ordered position arrays (welded copy). At a branch point (more than two
    boundary edges) the walk takes the unvisited edge that continues straightest."""
    bm = bmesh.new()
    bm.from_mesh(me)
    bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=weld)
    bm.verts.ensure_lookup_table()
    adj = {}
    for e in bm.edges:
        if len(e.link_faces) == 1:
            a, b = e.verts[0].index, e.verts[1].index
            adj.setdefault(a, []).append(b)
            adj.setdefault(b, []).append(a)
    co = {i: np.array(tuple(bm.verts[i].co)) for i in adj}
    bm.free()
    used = set()
    loops = []
    for start in sorted(adj):
        if all(tuple(sorted((start, n))) in used for n in adj[start]):
            continue
        chain = [start]
        prev, cur = None, start
        while True:
            cand = sorted(n for n in adj[cur] if tuple(sorted((cur, n))) not in used)
            if not cand:
                break
            if prev is not None and len(cand) > 1:
                d0 = co[cur] - co[prev]
                cand.sort(key=lambda n: -np.dot(d0, co[n] - co[cur]) /
                          (np.linalg.norm(d0) * np.linalg.norm(co[n] - co[cur]) + 1e-12))
            nxt = cand[0]
            used.add(tuple(sorted((cur, nxt))))
            prev, cur = cur, nxt
            if cur == start:
                break
            chain.append(cur)
        if len(chain) > 2:
            loops.append(np.array([co[i] for i in chain]))
    return loops


def resample_closed(pts, n):
    """n points evenly spaced by arc length along the closed polyline pts; returns (points, length)."""
    closed = np.vstack([pts, pts[:1]])
    seg = np.linalg.norm(np.diff(closed, axis=0), axis=1)
    s = np.concatenate([[0.0], np.cumsum(seg)])
    t = np.linspace(0.0, s[-1], n, endpoint=False)
    out = np.empty((n, 3))
    for k in range(3):
        out[:, k] = np.interp(t, s, closed[:, k])
    return out, float(s[-1])


def loop_cap(obj, name, near, samples=64, outward=0.1, skirt_m=0.004, dome_m=0.01, depth_m=0.02, rings=4,
             smooth=2, min_length_m=0.1, bottom_scale=0.6, lip_m=0.002):
    """Closed domed cap (new mesh `name`) over the open boundary loop of obj whose centroid is nearest to `near`
    (authored frame). Top: skirt ring pushed out by `outward` (fraction of the radius) and down by skirt_m along the
    loop's best-fit normal (tucks under the collar outside the rim), a lip ring on the rim lifted by lip_m (so a ray
    that grazes the rim meets the cap before the inner side of the rim wall), `rings` dome rings up to dome_m, a
    centre vertex; underside:
    a ring at bottom_scale of the radius depth_m below the plane and a bottom vertex, so the cap is closed.
    Returns (mesh, info)."""
    loops = [lp for lp in boundary_loops_ordered(obj.data) if resample_closed(lp, 8)[1] >= min_length_m]
    if not loops:
        raise RuntimeError("loop_cap: no open loop on %s" % obj.name)
    near = np.array(near, dtype=np.float64)
    loop = min(loops, key=lambda lp: float(np.linalg.norm(lp.mean(0) - near)))
    ring, length = resample_closed(loop, samples)
    for _ in range(int(smooth)):  # light smoothing: the Tripo cut zig-zags at the sub-millimetre scale
        ring = (np.roll(ring, 1, 0) + 2 * ring + np.roll(ring, -1, 0)) / 4.0
    c = ring.mean(0)
    _u, _s, vt = np.linalg.svd(ring - c)
    nrm = vt[2] / np.linalg.norm(vt[2])
    if nrm[2] < 0:
        nrm = -nrm
    ex = vt[0] / np.linalg.norm(vt[0])
    ey = np.cross(nrm, ex)
    ang = np.unwrap(np.arctan2((ring - c) @ ey, (ring - c) @ ex))
    if ang[-1] - ang[0] < 0:  # counter-clockwise seen from +nrm
        ring = ring[::-1].copy()
    n = len(ring)
    layers = [c + (ring - c) * (1.0 + outward) - nrm * skirt_m, ring + nrm * lip_m]
    for k in range(rings, 0, -1):
        f = k / float(rings + 1)
        layers.append(c + (ring - c) * f + nrm * dome_m * (1.0 - f * f))
    verts = [tuple(p) for layer in layers for p in layer.tolist()]
    top = len(verts)
    verts.append(tuple((c + nrm * dome_m).tolist()))
    b0 = len(verts)
    verts.extend(tuple(p) for p in (c + (ring - c) * bottom_scale - nrm * depth_m).tolist())
    bottom = len(verts)
    verts.append(tuple((c - nrm * depth_m).tolist()))
    faces = []
    for li in range(len(layers) - 1):
        a0, a1 = li * n, (li + 1) * n
        for j in range(n):
            faces.append((a0 + j, a0 + (j + 1) % n, a1 + (j + 1) % n, a1 + j))
    last = (len(layers) - 1) * n
    for j in range(n):
        faces.append((last + j, last + (j + 1) % n, top))
    for j in range(n):  # underside ring -> outer rim
        faces.append((b0 + j, b0 + (j + 1) % n, (j + 1) % n, j))
    for j in range(n):
        faces.append((b0 + (j + 1) % n, b0 + j, bottom))
    me = bpy.data.meshes.new(name)
    me.from_pydata(verts, [], faces)
    me.update()
    # orientation: top faces must face +nrm (outside); flip the whole mesh if they do not
    up = sum(1 for p in list(me.polygons)[: n * len(layers)] if Vector(p.normal).dot(Vector(nrm.tolist())) > 0)
    if up < n * len(layers) // 2:
        me.flip_normals()
        me.update()
        up = sum(1 for p in list(me.polygons)[: n * len(layers)] if Vector(p.normal).dot(Vector(nrm.tolist())) > 0)
    layer = me.uv_layers.new(name="UVMap")
    span = float(np.abs(np.stack([(layers[0] - c) @ ex, (layers[0] - c) @ ey])).max()) * 1.05
    lv = [me.loops[i].vertex_index for i in range(len(me.loops))]
    for li, vi in enumerate(lv):
        v = np.array(me.vertices[vi].co)
        layer.data[li].uv = (0.5 + float((v - c) @ ex) / (2 * span), 0.5 + float((v - c) @ ey) / (2 * span))
    info = {"loop_length_m": round(length, 4), "loop_points": int(len(loop)),
            "loop_bounds_m": {"min": [round(float(x), 4) for x in loop.min(0)],
                              "max": [round(float(x), 4) for x in loop.max(0)]},
            "centre_m": [round(float(x), 4) for x in c], "normal": [round(float(x), 4) for x in nrm],
            "samples": samples, "outward": outward, "skirt_m": skirt_m, "lip_m": lip_m, "dome_m": dome_m,
            "depth_m": depth_m,
            "rings": rings, "triangles": sum(len(p.vertices) - 2 for p in me.polygons),
            "top_faces_facing_out": up, "top_faces": n * len(layers), "uv_span_m": round(2 * span, 5)}
    return me, info


def feather_material(name, cfg):
    """Procedural material of a repair cap (baked like any high-poly part: stage_bake links the Base Color source to
    the emission for the BC pass, the Bump reaches the normal pass through the shading normal).

    cfg (profile repair.caps[].material): kind "feather_scallop" — Voronoi cells on the cap's planar UV (uv_span_m =
    the UV unit in metres, from loop_cap), stretched along V (feather length) by stretch, cell size cell_m; feature
    "F1" (distance from the cell centre: colour_centre -> colour_edge at edge_position, height 1 - distance) or
    "DISTANCE_TO_EDGE" (dark outline of every cell: colour_edge at the edge -> colour_centre at edge_position, height
    = distance to the edge); per-cell brightness jitter cell_jitter; bump_strength / bump_distance_m.
    Roughness constant."""
    m = bpy.data.materials.new(name)
    try:
        m.use_nodes = True
    except AttributeError:
        pass
    nt = m.node_tree
    bsdf = next(n for n in nt.nodes if n.type == "BSDF_PRINCIPLED")
    bsdf.inputs["Roughness"].default_value = float(cfg.get("roughness", 0.8))
    bsdf.inputs["Metallic"].default_value = 0.0
    kind = cfg.get("kind", "flat")
    if kind == "flat":
        bsdf.inputs["Base Color"].default_value = tuple(cfg["colour_linear"]) + (1.0,)
        m.diffuse_color = tuple(cfg["colour_linear"]) + (1.0,)
        return m
    if kind != "feather_scallop":
        raise RuntimeError("feather_material: unknown kind %s" % kind)
    uv = nt.nodes.new("ShaderNodeUVMap")
    uv.uv_map = "UVMap"
    mp = nt.nodes.new("ShaderNodeMapping")
    cells = float(cfg["uv_span_m"]) / float(cfg["cell_m"])
    mp.inputs["Scale"].default_value = (cells, cells / float(cfg.get("stretch", 1.8)), 1.0)
    nt.links.new(uv.outputs["UV"], mp.inputs["Vector"])
    vor = nt.nodes.new("ShaderNodeTexVoronoi")
    feature = cfg.get("feature", "F1")
    vor.feature = feature
    vor.distance = "EUCLIDEAN"
    vor.inputs["Scale"].default_value = 1.0
    vor.inputs["Randomness"].default_value = float(cfg.get("randomness", 0.8))
    nt.links.new(mp.outputs["Vector"], vor.inputs["Vector"])
    edge_first = feature == "DISTANCE_TO_EDGE"
    ramp = nt.nodes.new("ShaderNodeValToRGB")
    ramp.color_ramp.elements[0].position = 0.0
    ramp.color_ramp.elements[0].color = tuple(cfg["colour_edge_linear" if edge_first else "colour_centre_linear"]) + (1.0,)
    ramp.color_ramp.elements[1].position = float(cfg.get("edge_position", 0.6))
    ramp.color_ramp.elements[1].color = tuple(cfg["colour_centre_linear" if edge_first else "colour_edge_linear"]) + (1.0,)
    nt.links.new(vor.outputs["Distance"], ramp.inputs["Fac"])
    # per-cell jitter of the value (Voronoi cell colour -> brightness factor around 1)
    cell = vor
    if edge_first:  # DISTANCE_TO_EDGE has no cell colour: an F1 node on the same cells gives it
        cell = nt.nodes.new("ShaderNodeTexVoronoi")
        cell.feature = "F1"
        cell.distance = "EUCLIDEAN"
        cell.inputs["Scale"].default_value = 1.0
        cell.inputs["Randomness"].default_value = vor.inputs["Randomness"].default_value
        nt.links.new(mp.outputs["Vector"], cell.inputs["Vector"])
    bw = nt.nodes.new("ShaderNodeRGBToBW")
    nt.links.new(cell.outputs["Color"], bw.inputs["Color"])
    jit = nt.nodes.new("ShaderNodeMapRange")
    jit.inputs["To Min"].default_value = 1.0 - float(cfg.get("cell_jitter", 0.25))
    jit.inputs["To Max"].default_value = 1.0 + float(cfg.get("cell_jitter", 0.25))
    nt.links.new(bw.outputs["Val"], jit.inputs["Value"])
    mul = nt.nodes.new("ShaderNodeMix")
    mul.data_type = "RGBA"
    mul.blend_type = "MULTIPLY"
    next(s for s in mul.inputs if s.name == "Factor" and s.type == "VALUE").default_value = 1.0
    nt.links.new(ramp.outputs["Color"], next(s for s in mul.inputs if s.name == "A" and s.type == "RGBA"))
    comb = nt.nodes.new("ShaderNodeCombineColor")
    for ch in ("Red", "Green", "Blue"):
        nt.links.new(jit.outputs["Result"], comb.inputs[ch])
    nt.links.new(comb.outputs["Color"], next(s for s in mul.inputs if s.name == "B" and s.type == "RGBA"))
    nt.links.new(next(s for s in mul.outputs if s.name == "Result" and s.type == "RGBA"), bsdf.inputs["Base Color"])
    inv = nt.nodes.new("ShaderNodeMath")
    if edge_first:  # height rises from the cell outline, saturating at edge_position
        inv.operation = "MINIMUM"
        inv.inputs[1].default_value = float(cfg.get("edge_position", 0.6))
        nt.links.new(vor.outputs["Distance"], inv.inputs[0])
    else:
        inv.operation = "SUBTRACT"
        inv.inputs[0].default_value = 1.0
        nt.links.new(vor.outputs["Distance"], inv.inputs[1])
    bump = nt.nodes.new("ShaderNodeBump")
    bump.inputs["Strength"].default_value = float(cfg.get("bump_strength", 0.5))
    bump.inputs["Distance"].default_value = float(cfg.get("bump_distance_m", 0.001))
    nt.links.new(inv.outputs["Value"], bump.inputs["Height"])
    nt.links.new(bump.outputs["Normal"], bsdf.inputs["Normal"])
    m.diffuse_color = tuple(cfg["colour_centre_linear"]) + (1.0,)
    return m
