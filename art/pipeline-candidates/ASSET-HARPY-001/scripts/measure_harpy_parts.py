"""Measure the parts of the Harpy segmented retopology GLB (ASSET-HARPY-001) for the build profile.

Headless only, read-only on the source:
    blender -b --factory-startup --python measure_harpy_parts.py -- <segmented-retopo.glb> <out.json>

Writes, per part (Tripo source frame: metres, Z up, face -Y, own left +X): triangles, bounds, centroid,
ray-escape orientation score (as build_candidate.py), custom-corner-normal vs winding agreement, open
boundary loops (centre, mean radius, plane normal), horizontal slices (centroid and extent per z band)
and a few landmarks (wing leading-edge top, wing tip, talon tips). These numbers are where the bone
joints of the build profile come from; nothing is written next to the source.
"""

import json
import math
import sys
from collections import defaultdict

import bmesh
import bpy
import numpy as np
from mathutils import Vector
from mathutils.bvhtree import BVHTree

if not bpy.app.background:
    raise RuntimeError("measure_harpy_parts.py: headless only (blender -b)")


def r(v, nd=4):
    return round(float(v), nd)


def rv(v, nd=4):
    return [r(c, nd) for c in v]


def main():
    argv = sys.argv[sys.argv.index("--") + 1:]
    src, out_path = argv[0], argv[1]
    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.ops.import_scene.gltf(filepath=src)
    parts = {}
    for obj in list(bpy.context.scene.objects):
        if obj.type == "MESH":
            world = obj.matrix_world.copy()
            obj.parent = None
            obj.data.transform(world)
            obj.matrix_world.identity()
            parts[obj.name] = obj
    # orientation (ray escape against the whole model)
    verts, polys, owner = [], [], []
    for name, obj in sorted(parts.items()):
        base = len(verts)
        verts.extend(v.co.copy() for v in obj.data.vertices)
        for p in obj.data.polygons:
            polys.append([base + i for i in p.vertices])
            owner.append(name)
    lo = [min(v[i] for v in verts) for i in range(3)]
    hi = [max(v[i] for v in verts) for i in range(3)]
    height = hi[2] - lo[2]
    bvh = BVHTree.FromPolygons(verts, polys, all_triangles=False, epsilon=0.0)
    eps, dist = 1e-4 * height, 2.0 * height
    out = {"source": src.replace("\\", "/").split("/")[-1], "bounds": {"min": rv(lo), "max": rv(hi)}, "parts": {}}
    for name, obj in sorted(parts.items()):
        mesh = obj.data
        mesh.calc_loop_triangles()
        cn = np.empty(len(mesh.loops) * 3, dtype=np.float32)
        mesh.corner_normals.foreach_get("vector", cn)
        cn = cn.reshape(-1, 3)
        o_area = i_area = tot = opp = 0.0
        for p in mesh.polygons:
            n = p.normal
            c = p.center
            a = p.area
            tot += a
            plus = bvh.ray_cast(c + n * eps, n, dist)[0] is not None
            minus = bvh.ray_cast(c - n * eps, -n, dist)[0] is not None
            if not plus and minus:
                o_area += a
            elif plus and not minus:
                i_area += a
            if float(np.dot(cn[p.loop_start:p.loop_start + p.loop_total].mean(axis=0), np.array(n))) < 0:
                opp += a
        pts = np.array([v.co for v in mesh.vertices])
        entry = {"triangles": len(mesh.loop_triangles), "vertices": len(mesh.vertices),
                 "min": rv(pts.min(axis=0)), "max": rv(pts.max(axis=0)), "centroid": rv(pts.mean(axis=0)),
                 "orientation_score": r((o_area - i_area) / (o_area + i_area), 4) if o_area + i_area else None,
                 "corner_normals_opposed_area_share": r(opp / tot, 4)}
        # open boundary loops (after a 1e-6 weld, as the builder does)
        bm = bmesh.new()
        bm.from_mesh(mesh)
        bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=1e-6)
        bedges = [e for e in bm.edges if e.is_boundary]
        adj = defaultdict(list)
        for e in bedges:
            a, b = e.verts
            adj[a].append(b)
            adj[b].append(a)
        seen, loops = set(), []
        for start in list(adj):
            if start in seen:
                continue
            chain, prev, cur = [start], None, start
            seen.add(start)
            while True:
                nxt = [v for v in adj[cur] if v is not prev and v not in seen]
                if not nxt:
                    break
                prev, cur = cur, nxt[0]
                seen.add(cur)
                chain.append(cur)
            if len(chain) >= 5:
                P = np.array([v.co for v in chain])
                c = P.mean(axis=0)
                u, s, vt = np.linalg.svd(P - c)
                normal = vt[2]
                rad = np.linalg.norm(P - c, axis=1).mean()
                loops.append({"vertices": len(chain), "centre": rv(c), "mean_radius": r(rad),
                              "plane_normal": rv(normal, 3), "z_range": [r(P[:, 2].min()), r(P[:, 2].max())]})
        loops.sort(key=lambda d: -d["vertices"])
        entry["open_loops_ge5"] = loops[:12]
        entry["open_loop_count_ge5"] = len(loops)
        entry["boundary_edges"] = len(bedges)
        bm.free()
        # horizontal slices
        zs = pts[:, 2]
        slices = []
        z0, z1 = zs.min(), zs.max()
        n = max(4, int(round((z1 - z0) / 0.02)))
        for k in range(n):
            a = z0 + (z1 - z0) * k / n
            b = z0 + (z1 - z0) * (k + 1) / n
            sel = pts[(zs >= a) & (zs <= b)]
            if len(sel) < 3:
                continue
            slices.append({"z": [r(a), r(b)], "n": int(len(sel)), "centroid": rv(sel.mean(axis=0)),
                           "min": rv(sel.min(axis=0)), "max": rv(sel.max(axis=0))})
        entry["slices_2cm"] = slices
        # landmarks
        top = pts[np.argmax(zs)]
        entry["top_vertex"] = rv(top)
        entry["lowest_vertex"] = rv(pts[np.argmin(zs)])
        ax = np.abs(pts[:, 0])
        entry["max_abs_x_vertex"] = rv(pts[np.argmax(ax)])
        entry["min_abs_x_vertex"] = rv(pts[np.argmin(ax)])
        entry["min_y_vertex"] = rv(pts[np.argmin(pts[:, 1])])
        entry["max_y_vertex"] = rv(pts[np.argmax(pts[:, 1])])
        # top 2 % of the part by z: centroid (wing leading-edge bend, crest top)
        k = max(3, len(pts) // 50)
        idx = np.argsort(-zs)[:k]
        entry["top2pct_centroid"] = rv(pts[idx].mean(axis=0))
        idx = np.argsort(-ax)[:k]
        entry["outer2pct_abs_x_centroid"] = rv(pts[idx].mean(axis=0))
        idx = np.argsort(zs)[:k]
        entry["low2pct_centroid"] = rv(pts[idx].mean(axis=0))
        out["parts"][name] = entry
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(out, f, indent=1, sort_keys=True)
    print("MEASURE_OK", out_path, len(parts))


main()
