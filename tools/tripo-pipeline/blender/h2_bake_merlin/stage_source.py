"""Stage `source` (headless Blender): check and import both H2 GLBs.

blender -b --factory-startup --python-exit-code 1 --python stage_source.py -- <profile.json>

Checks sha256/bytes against the profile, glTF counts, part name matching between the geometry-only GLB and the
textured GLB, geometry identity (every vertex of one file within 1e-7 m of the other, both directions), winding
against the imported corner normals, ray-escape orientation per part (sampled), open boundary loops and the part
that shares each loop (the H2 parts are one surface cut into parts). Keeps only the textured high-poly (HP_<part>,
world transform applied) in work/h2-source.blend. Report: reports/source-report.json (no host paths, no times).
"""

import math
import sys
from pathlib import Path

import bmesh
import bpy
import numpy as np
from mathutils.kdtree import KDTree

sys.path.insert(0, str(Path(__file__).resolve().parent))
import blib as B  # noqa: E402
import common as C  # noqa: E402

B.require_background("stage_source.py")


def kdtree(points):
    kd = KDTree(len(points))
    for i, p in enumerate(points):
        kd.insert(p, i)
    kd.balance()
    return kd


def identity(a, b):
    """Max nearest-vertex distance a->b and b->a (m) on unique positions."""
    ua = np.unique(np.round(a, 7), axis=0)
    ub = np.unique(np.round(b, 7), axis=0)
    ka, kb = kdtree(ub), kdtree(ua)
    dab = max(kb.find(p)[2] for p in ub) if len(ub) else 0.0
    dba = max(ka.find(p)[2] for p in ua) if len(ua) else 0.0
    return {"unique_positions": [int(len(ua)), int(len(ub))], "max_nearest_m": [C.r(dba, 9), C.r(dab, 9)]}


def winding_vs_corner_normals(me):
    n = len(me.polygons)
    pn = B.poly_array(me, "normal", np.float64, 3)
    cn = np.empty(len(me.loops) * 3, np.float64)
    me.corner_normals.foreach_get("vector", cn)
    cn = cn.reshape(-1, 3)
    ls = B.poly_array(me, "loop_start", np.int64)
    lt = B.poly_array(me, "loop_total", np.int64)
    acc = np.zeros((n, 3))
    for k in range(int(lt.max())):
        m = lt > k
        acc[m] += cn[ls[m] + k]
    dots = (acc * pn).sum(1)
    return C.r(float((dots < 0).mean()), 7)


def ray_escape(obj, tree, samples=3000):
    me = obj.data
    n = len(me.polygons)
    step = max(1, n // samples)
    out_a = in_a = 0.0
    eps = 1e-5
    for i in range(0, n, step):
        p = me.polygons[i]
        c, nn = p.center, p.normal
        up = tree.ray_cast(c + nn * eps, nn)[0] is None
        um = tree.ray_cast(c - nn * eps, -nn)[0] is None
        if up and not um:
            out_a += p.area
        elif um and not up:
            in_a += p.area
    return C.r((out_a - in_a) / (out_a + in_a), 4) if out_a + in_a > 0 else None


def boundary_loops(obj):
    bm = bmesh.new()
    bm.from_mesh(obj.data)
    bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=1e-6)
    bm.verts.ensure_lookup_table()
    adj = {}
    for e in bm.edges:
        if e.is_boundary:
            a, b = e.verts
            adj.setdefault(a.index, []).append(b.index)
            adj.setdefault(b.index, []).append(a.index)
    seen, loops = set(), []
    for s in sorted(adj):
        if s in seen:
            continue
        stack, comp = [s], []
        seen.add(s)
        while stack:
            x = stack.pop()
            comp.append(x)
            for y in adj[x]:
                if y not in seen:
                    seen.add(y)
                    stack.append(y)
        loops.append(np.array([bm.verts[i].co[:] for i in sorted(comp)]))
    bm.free()
    return loops


def main():
    prof = C.Profile(B.script_args()[0])
    checks = {}
    src = prof["sources"]
    files = {}
    for key in ("parts", "textured"):
        path = C.repo_path(src[key]["path"])
        digest, size = C.sha256(path), path.stat().st_size
        files[key] = {"path": src[key]["path"], "sha256": digest, "bytes": size}
        C.check(checks, "source_%s_sha256_bytes" % key, digest == src[key]["sha256"] and size == src[key]["bytes"],
                [digest, size], [src[key]["sha256"], src[key]["bytes"]])
    B.empty_file()
    G = B.import_glb(C.repo_path(src["parts"]["path"]), "G_")
    H = B.import_glb(C.repo_path(src["textured"]["path"]), "HP_")
    for o in list(G.values()) + list(H.values()):
        B.apply_transform(o)
    names = sorted(G, key=C.part_index)
    C.check(checks, "part_names_match", sorted(G) == sorted(H) == sorted(prof["parts"]),
            {"parts_glb": sorted(G), "textured_glb": sorted(H)}, sorted(prof["parts"]))
    C.check(checks, "mesh_counts", len(G) == src["parts"]["meshes"] and len(H) == src["textured"]["meshes"],
            [len(G), len(H)], [src["parts"]["meshes"], src["textured"]["meshes"]])
    tris = {"parts": sum(len(G[n].data.polygons) for n in names), "textured": sum(len(H[n].data.polygons) for n in names)}
    C.check(checks, "triangle_counts", tris["parts"] == src["parts"]["triangles"] and tris["textured"] == src["textured"]["triangles"],
            tris, {"parts": src["parts"]["triangles"], "textured": src["textured"]["triangles"]})
    images = sorted({im.name for im in bpy.data.images if im.size[0] > 0})
    mats = sorted({s.material.name for n in names for s in H[n].material_slots if s.material})
    C.check(checks, "textured_materials_images", len(mats) == src["textured"]["materials"] and len(images) == src["textured"]["images"],
            [len(mats), len(images)], [src["textured"]["materials"], src["textured"]["images"]])

    tree = B.bvh_of([G[n] for n in names])
    per_part = {}
    for n in names:
        g, h = G[n], H[n]
        gv, hv = B.verts_np(g), B.verts_np(h)
        ident = identity(gv, hv)
        tex = {}
        for node in h.material_slots[0].material.node_tree.nodes:
            if node.type == "TEX_IMAGE" and node.image:
                kind = node.image.name.rsplit("_", 1)[1].split(".")[0]
                tex[kind] = {"px": list(node.image.size), "colorspace": node.image.colorspace_settings.name}
        per_part[n] = {
            "role": prof["parts"][n]["role"], "object": prof["parts"][n]["object"],
            "triangles": len(g.data.polygons), "vertices": [len(g.data.vertices), len(h.data.vertices)],
            "bounds_m": {"min": C.rv(gv.min(0), 5), "max": C.rv(gv.max(0), 5)},
            "geometry_identity": ident,
            "same_polygon_count": len(g.data.polygons) == len(h.data.polygons),
            "opposed_corner_normal_fraction": winding_vs_corner_normals(g.data),
            "ray_escape_score": ray_escape(g, tree),
            "textures": tex,
            "uv_layers": [u.name for u in h.data.uv_layers],
        }
    C.check(checks, "geometry_identical_parts_vs_textured",
            all(max(p["geometry_identity"]["max_nearest_m"]) <= 1e-7 and p["same_polygon_count"] for p in per_part.values()),
            {n: p["geometry_identity"]["max_nearest_m"] for n, p in per_part.items()}, "<= 1e-7 m both directions",
            "vertex counts differ only by UV-seam splits of the textured file")
    bad = {n: p["ray_escape_score"] for n, p in per_part.items() if p["ray_escape_score"] is None or p["ray_escape_score"] < 0.5}
    C.check(checks, "orientation_all_parts_outward", not bad, {n: p["ray_escape_score"] for n, p in per_part.items()},
            ">= 0.5 (ray escape, 3000 sampled polygons per part)", "no inside-out part in H2 (unlike d9ff4260 shoes)")
    opp = {n: p["opposed_corner_normal_fraction"] for n, p in per_part.items()}
    C.check(checks, "winding_agrees_with_corner_normals", max(opp.values()) < 0.001, opp, "< 0.1 % of polygons")

    # seams: boundary loops and the part that shares them
    loops = {n: boundary_loops(G[n]) for n in names}
    kds = {}
    for n in names:
        pts = np.concatenate(loops[n]) if loops[n] else np.zeros((0, 3))
        kds[n] = kdtree(pts) if len(pts) else None
    tol = float(prof["objects"]["body"]["weld_m"])
    seams = []
    for n in names:
        for pts in sorted(loops[n], key=lambda a: (-len(a), a.mean(0).tolist())):
            c = pts.mean(0)
            partners = {}
            for m in names:
                if m == n or kds[m] is None:
                    continue
                f = float(np.mean([kds[m].find(p)[2] < tol for p in pts]))
                if f > 0.05:
                    partners[m] = C.r(f, 3)
            seams.append({"part": n, "vertices": int(len(pts)), "centre_m": C.rv(c, 4),
                          "radius_m": C.r(np.linalg.norm(pts - c, axis=1).mean(), 4),
                          "z_range_m": [C.r(pts[:, 2].min(), 4), C.r(pts[:, 2].max(), 4)], "shared_with": partners})
    unshared = [s for s in seams if not s["shared_with"] and s["vertices"] > 3]
    C.check(checks, "seam_loops_shared", not unshared, {"loops": len(seams), "unshared_over_3_vertices": unshared},
            note="every open loop of a part (except tiny holes) is shared with another part within weld_m")

    # keep the textured high-poly only
    for o in G.values():
        bpy.data.objects.remove(o)
    for m in [m for m in bpy.data.meshes if m.users == 0]:
        bpy.data.meshes.remove(m)
    for n in names:
        H[n]["um_part"] = C.part_index(n)
    out = prof.work / "h2-source.blend"
    B.save_blend(out)
    report = {"stage": "source", "profile": C.rel(prof.path), "profile_id": prof["profile_id"], "files": files,
              "blender": bpy.app.version_string, "parts": per_part, "seams": seams, "checks": checks,
              "passed": all(c["passed"] for c in checks.values()), "work_blend": C.rel(out)}
    C.write_json(prof.reports / "source-report.json", report)
    print("H2_STAGE_OK source passed=%s" % report["passed"])
    if not report["passed"]:
        raise RuntimeError("source checks failed: %s" % sorted(k for k, c in checks.items() if not c["passed"]))


main()
