"""Geometry repairs of the Tripo H2 high-poly, applied identically to the untextured and the textured GLB.

drop       parts named "drop" in the profile are removed (phantom duplicates of the side view, see the profile notes)
symmetrize a part (the head) is bisected at a measured plane x = const and its clean half mirrored onto the other
           (Mirror modifier with bisect and merge; UVs are copied, so the texture of the kept half is mirrored too)
grip_bridge an open cylinder on the fitted sword axis between the pommel/grip part and the blade/guard part (the grip
           inside the fist was not modelled by Tripo); only for the game mesh, hidden by the fist
Every repair is geometric, reported and not art-accepted.
"""

import math

import bmesh
import bpy
import numpy as np
from mathutils import Vector

import bl
import pure as P


def _symmetrize(obj, plane_x, keep, merge_m):
    empty = bpy.data.objects.new("h2_mirror_plane", None)
    bpy.context.scene.collection.objects.link(empty)
    empty.location = (plane_x, 0.0, 0.0)
    mod = obj.modifiers.new("h2_symmetrize", "MIRROR")
    mod.use_axis = (True, False, False)
    mod.use_bisect_axis = (True, False, False)
    mod.use_bisect_flip_axis = (keep == "-X", False, False)
    mod.mirror_object = empty
    mod.use_mirror_merge = True
    mod.merge_threshold = merge_m
    mod.use_clip = False
    mod.use_mirror_u = False
    mod.use_mirror_v = False
    dg = bpy.context.evaluated_depsgraph_get()
    me = bpy.data.meshes.new_from_object(obj.evaluated_get(dg), preserve_all_data_layers=True, depsgraph=dg)
    old = obj.data
    obj.modifiers.remove(mod)
    obj.data = me
    me.name = old.name
    bpy.data.meshes.remove(old)
    bpy.data.objects.remove(empty)
    co, _, _ = bl.mesh_arrays(obj)
    rel = co[:, 0] - plane_x
    return {"plane_x_m": plane_x, "kept_side": keep, "merge_m": merge_m,
            "x_extent_after_m": [P.r(rel.min(), 5), P.r(rel.max(), 5)],
            "symmetric_extent": bool(abs(rel.min() + rel.max()) < 1e-5),
            "triangles_after": int(sum(len(p.vertices) - 2 for p in obj.data.polygons)),
            "topology_after": bl.edge_topology(obj)}


PHANTOM_POINTS = {}


def apply_geometry_repairs(high, profile):
    """Drop the phantom parts (their vertices are kept in PHANTOM_POINTS for the hole fill and the texture
    repaint), then symmetrize. Returns the log."""
    log = {"dropped": {}, "symmetrized": {}}
    for name, pc in profile["parts"].items():
        if pc.get("drop") and name in high:
            PHANTOM_POINTS[name] = bl.mesh_arrays(high[name])[0]
            obj = high.pop(name)
            log["dropped"][name] = {"triangles": len(obj.data.polygons), "why": pc["drop"]}
            bpy.data.objects.remove(obj)
    for sym in profile.get("repairs", {}).get("symmetrize", []):
        obj = high[sym["part"]]
        before = co_extent = bl.mesh_arrays(obj)[0][:, 0] - float(sym["plane_x_m"])
        info = _symmetrize(obj, float(sym["plane_x_m"]), sym["keep"], float(sym["merge_m"]))
        info["x_extent_before_m"] = [P.r(before.min(), 5), P.r(before.max(), 5)]
        info["why"] = sym["why"]
        log["symmetrized"][sym["part"]] = info
        del co_extent
    return log


def grip_bridge(high, cfg):
    """Open n-sided cylinder on the sword axis across the gap between the pommel part and the blade part."""
    co_b = bl.mesh_arrays(high[cfg["blade_part"]])[0]
    co_p = bl.mesh_arrays(high[cfg["pommel_part"]])[0]
    tip = co_b[co_b[:, 2] >= co_b[:, 2].max() - float(cfg["tip_band_m"])].mean(axis=0)
    pts = np.concatenate([co_b, co_p])
    z_top_p = co_p[:, 2].max()
    top_band = co_p[co_p[:, 2] >= z_top_p - float(cfg["grip_band_m"])]
    grip_c = top_band.mean(axis=0)
    d = tip - grip_c
    d /= np.linalg.norm(d)
    t_b = (co_b - grip_c) @ d
    t_p = (co_p - grip_c) @ d
    gap_lo, gap_hi = float(t_p.max()), float(t_b.min())
    radial = top_band - grip_c - np.outer((top_band - grip_c) @ d, d)
    radius = float(np.median(np.linalg.norm(radial, axis=1))) * float(cfg.get("radius_factor", 1.0))
    info = {"axis_dir": P.rv(d, 5), "grip_centre_m": P.rv(grip_c, 5), "tip_m": P.rv(tip, 5),
            "gap_m": P.r(gap_hi - gap_lo, 5), "radius_m": P.r(radius, 5)}
    if gap_hi - gap_lo <= float(cfg["min_gap_m"]):
        info["added"] = False
        return info, None
    ov = float(cfg["overlap_m"])
    a = Vector(grip_c + d * (gap_lo - ov))
    b = Vector(grip_c + d * (gap_hi + ov))
    dv = Vector(d)
    ref = Vector((1, 0, 0)) if abs(dv.x) < 0.9 else Vector((0, 1, 0))
    u = dv.cross(ref).normalized()
    v = dv.cross(u).normalized()
    n = int(cfg["sides"])
    bm = bmesh.new()
    ring_a, ring_b = [], []
    for k in range(n):
        ang = 2 * math.pi * k / n
        off = (u * math.cos(ang) + v * math.sin(ang)) * radius
        ring_a.append(bm.verts.new(a + off))
        ring_b.append(bm.verts.new(b + off))
    for k in range(n):
        k2 = (k + 1) % n
        bm.faces.new((ring_a[k], ring_a[k2], ring_b[k2], ring_b[k]))
    bmesh.ops.triangulate(bm, faces=list(bm.faces))
    me = bpy.data.meshes.new(cfg["name"])
    bm.to_mesh(me)
    bm.free()
    obj = bpy.data.objects.new(cfg["name"], me)
    info.update({"added": True, "from_m": P.rv(a, 5), "to_m": P.rv(b, 5), "triangles": len(me.polygons),
                 "why": cfg["why"]})
    return info, obj


def fill_phantom_holes(obj, phantom_pts, max_dist, max_edges):
    """Fill the boundary loops of `obj` that a phantom part passed through (a loop vertex within max_dist of a
    phantom vertex) and that have at most max_edges edges: the hole the generator cut where the phantom crossed the
    garment. holes_fill (winding from the neighbours) + beauty triangulation. Returns [{edges, centre, dist}]."""
    from mathutils.kdtree import KDTree
    kd = KDTree(len(phantom_pts))
    for i, p in enumerate(phantom_pts):
        kd.insert(p, i)
    kd.balance()
    bm = bmesh.new()
    bm.from_mesh(obj.data)
    bm.edges.index_update()
    seen, loops = set(), []
    for e in sorted((e for e in bm.edges if len(e.link_faces) == 1), key=lambda e: e.index):
        if e in seen:
            continue
        loop, stack = [], [e]
        seen.add(e)
        while stack:
            x = stack.pop()
            loop.append(x)
            for v in x.verts:
                for y in v.link_edges:
                    if len(y.link_faces) == 1 and y not in seen:
                        seen.add(y)
                        stack.append(y)
        loops.append(loop)
    filled = []
    for loop in loops:
        verts = list({v for e in loop for v in e.verts})
        d = min(kd.find(v.co)[2] for v in verts)
        if d > max_dist or len(loop) > max_edges:
            continue
        centre = sum((v.co for v in verts[1:]), verts[0].co.copy()) / len(verts)
        before = set(bm.faces)
        bmesh.ops.holes_fill(bm, edges=loop, sides=0)
        method = "holes_fill"
        new = [f for f in bm.faces if f not in before]
        if not new:
            # holes_fill refuses loops that are not a simple ring; triangle_fill projects the loop on its best plane
            bmesh.ops.triangle_fill(bm, use_beauty=True, use_dissolve=False, edges=loop)
            method = "triangle_fill"
            new = [f for f in bm.faces if f not in before]
        if new:
            bmesh.ops.triangulate(bm, faces=new, quad_method="BEAUTY", ngon_method="BEAUTY")
            new = [f for f in bm.faces if f not in before]
            # winding: a filled face must run every edge it shares with an old face opposite to that face
            bad = good = 0
            for f in new:
                for lp in f.loops:
                    for other in lp.edge.link_loops:
                        if other.face in before:
                            if other.vert == lp.vert:
                                bad += 1
                            else:
                                good += 1
            flipped = bad > good
            if flipped:
                bmesh.ops.reverse_faces(bm, faces=new)
        else:
            flipped = False
        filled.append({"edges": len(loop), "centre_m": P.rv(centre, 4), "phantom_dist_mm": P.r(d * 1000, 2),
                       "faces_added": len(new), "method": method, "winding_flipped": flipped})
    bm.to_mesh(obj.data)
    bm.free()
    obj.data.update()
    return filled


def smooth_box(obj, cfg):
    """Laplacian smoothing of the vertices of `obj` inside an axis-aligned box (Tripo frame), boundary vertices
    pinned: flattens raised phantom imprints (the strip and tabs on the cloak back) into the cloth surface."""
    lo, hi = Vector(cfg["min_m"]), Vector(cfg["max_m"])
    bm = bmesh.new()
    bm.from_mesh(obj.data)
    inside = [v for v in bm.verts if all(lo[i] <= v.co[i] <= hi[i] for i in range(3)) and not v.is_boundary]
    before = {v: v.co.copy() for v in inside}
    for _ in range(int(cfg["iterations"])):
        bmesh.ops.smooth_vert(bm, verts=inside, factor=float(cfg["factor"]), use_axis_x=True, use_axis_y=True,
                              use_axis_z=True)
    moved = [(v.co - before[v]).length for v in inside]
    bm.to_mesh(obj.data)
    bm.free()
    obj.data.update()
    return {"box_min_m": cfg["min_m"], "box_max_m": cfg["max_m"], "vertices": len(inside),
            "max_move_mm": P.r(max(moved) * 1000, 2) if moved else 0.0, "why": cfg["why"]}
