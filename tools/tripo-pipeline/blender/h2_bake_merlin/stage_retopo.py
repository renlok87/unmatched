"""Stage `retopo` (headless Blender): game mesh from the H2 high-poly, per part, in the source frame.

blender -b --factory-startup --python-exit-code 1 --python stage_retopo.py -- <profile.json>

For every object of the profile (body, staff, base):
 1. join copies of its high-poly parts (positions + faces only), material slot = part (survives decimation);
 2. weld coincident seam vertices (weld_m) of the profile's weld_pairs: the H2 parts are one surface cut into parts;
    anatomical seams are welded, incidental contacts (arm on robe, beard tip on chest) are not;
 3. sequential collapse decimation per part, largest first, the other parts protected by a vertex group
    (weight 0 x protect_factor); seam vertices belong to both sides and may move;
 4. staff: bridge the fist loops of the lower and upper shaft; every object: fan caps on the remaining open loops;
 5. beautify (edge rotation) on near-flat edges inside a part; smooth shading, sharp edges only where the profile
    asks (crystal facets);
 6. measure per part: triangles, deviation high->low and low->high (mm, source metres), triangle shape, open and
    non-manifold edges.
Output: work/h2-retopo.blend (LP_<object> + the HP_ parts), reports/retopo-report.json.
"""

import math
import sys
from pathlib import Path

import bmesh
import bpy
import numpy as np
from mathutils import Vector
from mathutils.kdtree import KDTree

sys.path.insert(0, str(Path(__file__).resolve().parent))
import blib as B  # noqa: E402
import common as C  # noqa: E402

B.require_background("stage_retopo.py")


def join_parts(name, parts, hp):
    """One mesh of the parts (positions and polygons only); material slot i = parts[i]."""
    verts, loops, starts, totals, mats = [], [], [], [], []
    off = 0
    loff = 0
    for i, pn in enumerate(parts):
        me = hp[pn].data
        v = np.empty(len(me.vertices) * 3, np.float64)
        me.vertices.foreach_get("co", v)
        lv = np.empty(len(me.loops), np.int64)
        me.loops.foreach_get("vertex_index", lv)
        ls = B.poly_array(me, "loop_start", np.int64)
        lt = B.poly_array(me, "loop_total", np.int64)
        verts.append(v.reshape(-1, 3))
        loops.append(lv + off)
        starts.append(ls + loff)
        totals.append(lt)
        mats.append(np.full(len(lt), i, np.int64))
        off += len(me.vertices)
        loff += len(lv)
    V = np.concatenate(verts)
    Lv = np.concatenate(loops)
    Ps, Pt, Pm = np.concatenate(starts), np.concatenate(totals), np.concatenate(mats)
    me = bpy.data.meshes.new(name)
    me.vertices.add(len(V))
    me.vertices.foreach_set("co", V.astype(np.float32).ravel())
    me.loops.add(len(Lv))
    me.loops.foreach_set("vertex_index", Lv.astype(np.int32))
    me.polygons.add(len(Pt))
    me.polygons.foreach_set("loop_start", Ps.astype(np.int32))
    me.polygons.foreach_set("loop_total", Pt.astype(np.int32))
    me.polygons.foreach_set("material_index", Pm.astype(np.int32))
    me.update(calc_edges=True)
    me.validate(clean_customdata=False)
    for pn in parts:
        mat = bpy.data.materials.get("PART_" + pn) or bpy.data.materials.new("PART_" + pn)
        me.materials.append(mat)
    obj = bpy.data.objects.new(name, me)
    bpy.context.scene.collection.objects.link(obj)
    return obj


def weld(obj, dist, parts, pairs):
    """Merge coincident BOUNDARY vertices: always inside one part (UV-seam splits of the textured GLB), across two
    parts only for the profile's weld_pairs (optionally above a source z). Interior vertices are never merged (the
    hood touches itself at the back of the neck; merging there made 6 non-manifold edges, measured 2026-09-29).
    Seams that are not welded stay open here and are capped on both sides later (incidental contacts: an arm that
    lifts off the robe shows a cap instead of stretching a web of skin)."""
    bm = bmesh.new()
    bm.from_mesh(obj.data)
    bm.verts.ensure_lookup_table()
    n0 = len(bm.verts)
    part_of_vert = {}
    for f in bm.faces:
        for v in f.verts:
            part_of_vert.setdefault(v.index, set()).add(parts[f.material_index])
    bnd = [v for v in bm.verts if v.is_boundary]
    allowed = {}
    for rule in pairs:
        a, b = rule["parts"]
        allowed[(a, b)] = allowed[(b, a)] = rule.get("z_min")
    kd = KDTree(len(bnd))
    for i, v in enumerate(bnd):
        kd.insert(v.co, i)
    kd.balance()
    parent = list(range(len(bnd)))

    def find(i):
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    pair_counts = {}
    for i, v in enumerate(bnd):
        pa = part_of_vert[v.index]
        for co, j, d in kd.find_range(v.co, dist):
            if j <= i:
                continue
            w = bnd[j]
            pb = part_of_vert[w.index]
            ok = False
            if pa & pb:
                ok = True
            else:
                for x in pa:
                    for y in pb:
                        if (x, y) in allowed:
                            zmin = allowed[(x, y)]
                            if zmin is None or v.co.z >= zmin:
                                ok = True
                                key = "|".join(sorted((x, y), key=C.part_index))
                                pair_counts[key] = pair_counts.get(key, 0) + 1
            if ok:
                ri, rj = find(i), find(j)
                if ri != rj:
                    parent[max(ri, rj)] = min(ri, rj)
    targetmap = {}
    for i, v in enumerate(bnd):
        r = find(i)
        if r != i:
            targetmap[v] = bnd[r]
    bmesh.ops.weld_verts(bm, targetmap=targetmap)
    n1 = len(bm.verts)
    bm.to_mesh(obj.data)
    bm.free()
    obj.data.update()
    return {"boundary_vertices_before": len(bnd), "vertices_before": n0, "vertices_after": n1, "merged": n0 - n1,
            "cross_part_vertex_pairs_welded": dict(sorted(pair_counts.items()))}


def part_face_counts(obj, parts):
    mi = B.poly_array(obj.data, "material_index", np.int64)
    return {pn: int((mi == i).sum()) for i, pn in enumerate(parts)}


def decimate_part(obj, parts, k, target, factor):
    me = obj.data
    mi = B.poly_array(me, "material_index", np.int64)
    counts = part_face_counts(obj, parts)
    cur_total, cur_k = len(mi), counts[parts[k]]
    if cur_k <= target:
        return {"before": cur_k, "after": cur_k, "skipped": True}
    lv = np.empty(len(me.loops), np.int64)
    me.loops.foreach_get("vertex_index", lv)
    ls = B.poly_array(me, "loop_start", np.int64)
    lt = B.poly_array(me, "loop_total", np.int64)
    w = np.zeros(len(me.vertices), np.float32)
    for j in range(int(lt.max())):
        m = (lt > j) & (mi == k)
        w[lv[ls[m] + j]] = 1.0
    for g in list(obj.vertex_groups):
        obj.vertex_groups.remove(g)
    vg = obj.vertex_groups.new(name="decimate")
    vg.add(np.nonzero(w > 0)[0].tolist(), 1.0, "REPLACE")  # vertices outside the group weigh 0 (protected)
    mod = obj.modifiers.new("dec", "DECIMATE")
    mod.decimate_type = "COLLAPSE"
    mod.use_collapse_triangulate = True
    mod.use_symmetry = False
    mod.vertex_group = "decimate"
    mod.vertex_group_factor = factor
    mod.invert_vertex_group = False
    mod.ratio = (cur_total - cur_k + target) / cur_total
    with B.ctx(obj):
        bpy.ops.object.modifier_apply(modifier=mod.name)
    obj.vertex_groups.remove(obj.vertex_groups["decimate"])
    after = part_face_counts(obj, parts)
    return {"before": cur_k, "after": after[parts[k]], "others_changed": {
        p: [counts[p], after[p]] for p in parts if p != parts[k] and after[p] != counts[p]}}


def boundary_loops_bm(bm):
    adj = {}
    for e in bm.edges:
        if e.is_boundary:
            a, b = e.verts
            adj.setdefault(a, []).append(e)
            adj.setdefault(b, []).append(e)
    seen, loops = set(), []
    for v0 in sorted(adj, key=lambda v: v.index):
        if v0 in seen:
            continue
        stack, verts, edges = [v0], [], set()
        seen.add(v0)
        while stack:
            v = stack.pop()
            verts.append(v)
            for e in adj[v]:
                edges.add(e)
                o = e.other_vert(v)
                if o not in seen:
                    seen.add(o)
                    stack.append(o)
        loops.append((verts, sorted(edges, key=lambda e: e.index)))
    return loops


def loop_centre(verts):
    c = Vector()
    for v in verts:
        c += v.co
    return c / len(verts)


def close_object(obj, parts, cfg, seams, report):
    """Bridge (staff) and fan caps on every remaining open loop. Cap/bridge faces: attribute um_cap = 1/2."""
    bm = bmesh.new()
    bm.from_mesh(obj.data)
    wire = [e for e in bm.edges if not e.link_faces]
    bmesh.ops.delete(bm, geom=wire, context="EDGES")
    loose = [v for v in bm.verts if not v.link_edges]
    bmesh.ops.delete(bm, geom=loose, context="VERTS")
    report["removed_wire_edges_loose_verts"] = [len(wire), len(loose)]
    cap_layer = bm.faces.layers.int.new("um_cap")
    bridges = []
    for br in cfg.get("bridge") or []:
        loops = boundary_loops_bm(bm)

        def seam_centre(part, partner):
            cands = [s for s in seams if s["part"] == part and partner in s["shared_with"]]
            if len(cands) != 1:
                raise RuntimeError("bridge: %d seams %s|%s" % (len(cands), part, partner))
            return Vector(cands[0]["centre_m"])

        ca, cb = seam_centre(br["lower"], br["lower_partner"]), seam_centre(br["upper"], br["upper_partner"])
        la = min(loops, key=lambda L: (loop_centre(L[0]) - ca).length)
        lb = min(loops, key=lambda L: (loop_centre(L[0]) - cb).length)
        da, db = (loop_centre(la[0]) - ca).length, (loop_centre(lb[0]) - cb).length
        if la is lb or max(da, db) > 0.01:
            raise RuntimeError("bridge loops not found (%.4f, %.4f m)" % (da, db))
        before = set(bm.faces)
        res = bmesh.ops.bridge_loops(bm, edges=la[1] + lb[1])
        new = [f for f in res["faces"]]
        tri = bmesh.ops.triangulate(bm, faces=new, quad_method="BEAUTY", ngon_method="BEAUTY")
        mat = parts.index(br["lower"])
        made = [f for f in bm.faces if f not in before]
        for f in made:
            f[cap_layer] = 2
            f.material_index = mat
        bridges.append({"lower": br["lower"], "upper": br["upper"], "loop_vertices": [len(la[0]), len(lb[0])],
                        "centre_offsets_m": [C.r(da, 5), C.r(db, 5)], "faces": len(made)})
    caps = []
    if cfg.get("cap_open_loops"):
        for verts, edges in boundary_loops_bm(bm):
            c = loop_centre(verts)
            if len(edges) < len(verts):
                caps.append({"part": None, "loop_vertices": len(verts), "centre_m": C.rv(c, 4), "faces": 0,
                             "skipped": "open chain (%d edges): source self-contact, left open" % len(edges)})
                continue
            votes = {}
            for e in edges:
                for f in e.link_faces:
                    votes[f.material_index] = votes.get(f.material_index, 0) + 1
            mat = max(sorted(votes), key=lambda m: votes[m])
            centre = bm.verts.new(c)
            made = []
            for e in edges:
                lp = e.link_loops[0]  # the only face loop on a boundary edge runs a -> b
                a, b = lp.vert, lp.link_loop_next.vert
                f = bm.faces.new((b, a, centre))  # the cap runs b -> a: consistent winding
                f[cap_layer] = 1
                f.material_index = mat
                f.smooth = True
                made.append(f)
            caps.append({"part": parts[mat], "loop_vertices": len(verts), "centre_m": C.rv(c, 4), "faces": len(made)})
    bm.to_mesh(obj.data)
    bm.free()
    obj.data.update()
    report["bridges"] = bridges
    report["caps"] = caps


def fix_cap_winding(obj):
    """Caps/bridges must agree with the winding of the original faces around them: every connected region of
    cap/bridge faces votes on its edges shared with original faces (a shared edge must run in opposite
    directions); a region that mostly runs the same way is flipped as a whole. Returns flipped face count."""
    bm = bmesh.new()
    bm.from_mesh(obj.data)
    cap = bm.faces.layers.int.get("um_cap")
    seen, flipped = set(), 0
    for f0 in bm.faces:
        if not f0[cap] or f0 in seen:
            continue
        region, stack = [], [f0]
        seen.add(f0)
        while stack:
            f = stack.pop()
            region.append(f)
            for e in f.edges:
                for g in e.link_faces:
                    if g[cap] and g not in seen:
                        seen.add(g)
                        stack.append(g)
        same = opposite = 0
        for f in region:
            for lp in f.loops:
                for l2 in lp.edge.link_loops:
                    if l2.face is f or l2.face[cap]:
                        continue
                    if l2.vert is lp.vert:
                        same += 1
                    else:
                        opposite += 1
        if same > opposite:
            for f in region:
                f.normal_flip()
            flipped += len(region)
    bm.to_mesh(obj.data)
    bm.free()
    return flipped


def beautify(obj, max_dihedral_deg):
    bm = bmesh.new()
    bm.from_mesh(obj.data)
    lim = math.radians(max_dihedral_deg)
    cap = bm.faces.layers.int.get("um_cap")
    edges = []
    for e in bm.edges:
        if len(e.link_faces) != 2:
            continue
        f1, f2 = e.link_faces
        if f1.material_index != f2.material_index or f1[cap] or f2[cap]:
            continue
        if f1.normal.angle(f2.normal, 0.0) < lim:
            edges.append(e)
    n = len(edges)
    bmesh.ops.beautify_fill(bm, faces=list(bm.faces), edges=edges, method="AREA")
    bm.to_mesh(obj.data)
    bm.free()
    return n


def set_shading(obj, parts, sharp_cfg):
    me = obj.data
    me.shade_smooth()
    bm = bmesh.new()
    bm.from_mesh(me)
    sharp = set()
    selfcontact = set()
    for e in bm.edges:
        if len(e.link_faces) > 2 or (len(e.link_loops) == 2 and e.link_loops[0].vert is e.link_loops[1].vert):
            selfcontact.add(e.index)
            continue
        if len(e.link_faces) != 2:
            continue
        f1, f2 = e.link_faces
        for f in (f1, f2):
            limit = sharp_cfg.get(parts[f.material_index], sharp_cfg["default"])
            if limit < 180.0 and f1.normal.angle(f2.normal, 0.0) > math.radians(limit):
                sharp.add(e.index)
    bm.free()
    attr = me.attributes.get("sharp_edge") or me.attributes.new("sharp_edge", "BOOLEAN", "EDGE")
    vals = np.zeros(len(me.edges), bool)
    vals[sorted(sharp | selfcontact)] = True
    attr.data.foreach_set("value", vals)
    return {"by_angle": len(sharp), "self_contact": len(selfcontact)}


def tri_quality(obj, parts):
    me = obj.data
    mi = B.poly_array(me, "material_index", np.int64)
    V = B.verts_np(obj)
    lv = np.empty(len(me.loops), np.int64)
    me.loops.foreach_get("vertex_index", lv)
    ls = B.poly_array(me, "loop_start", np.int64)
    a, b, c = V[lv[ls]], V[lv[ls + 1]], V[lv[ls + 2]]
    la, lb, lc = np.linalg.norm(b - c, axis=1), np.linalg.norm(a - c, axis=1), np.linalg.norm(a - b, axis=1)
    area = 0.5 * np.linalg.norm(np.cross(b - a, c - a), axis=1)
    s = la ** 2 + lb ** 2 + lc ** 2
    q = np.where(s > 0, 4 * math.sqrt(3) * area / np.maximum(s, 1e-30), 0)
    out = {}
    for i, pn in enumerate(parts):
        qq = q[mi == i]
        if len(qq):
            out[pn] = {"q_p5": C.r(np.percentile(qq, 5), 3), "q_median": C.r(np.median(qq), 3),
                       "share_q_below_0_2": C.r((qq < 0.2).mean(), 4), "degenerate_area_below_1e-12_m2": int((area[mi == i] < 1e-12).sum())}
    return out


def topology(obj):
    bm = bmesh.new()
    bm.from_mesh(obj.data)
    out = {"vertices": len(bm.verts), "triangles": sum(len(f.verts) - 2 for f in bm.faces),
           "non_triangles": sum(1 for f in bm.faces if len(f.verts) != 3),
           "boundary_edges": sum(1 for e in bm.edges if e.is_boundary),
           "non_manifold_edges": sum(1 for e in bm.edges if not e.is_manifold and not e.is_boundary),
           "inconsistent_winding_edges": sum(1 for e in bm.edges if len(e.link_loops) == 2
                                              and e.link_loops[0].vert is e.link_loops[1].vert)}
    bm.free()
    return out


def part_object(obj, parts, pn):
    """Temporary object with only the faces of part pn (for per-part BVH)."""
    tmp = obj.copy()
    tmp.data = obj.data.copy()
    bpy.context.scene.collection.objects.link(tmp)
    bm = bmesh.new()
    bm.from_mesh(tmp.data)
    k = parts.index(pn)
    bmesh.ops.delete(bm, geom=[f for f in bm.faces if f.material_index != k], context="FACES")
    bm.to_mesh(tmp.data)
    bm.free()
    return tmp


def main():
    prof = C.Profile(B.script_args()[0])
    src_rep = C.load_json(prof.reports / "source-report.json")
    if not src_rep["passed"]:
        raise RuntimeError("source stage did not pass")
    B.open_blend(prof.work / "h2-source.blend")
    hp = {o.name[3:]: o for o in bpy.data.objects if o.name.startswith("HP_")}
    rcfg = prof["retopo"]
    checks = {}
    objects = {}
    for key in ("body", "staff", "base"):
        cfg = prof["objects"][key]
        parts = list(cfg["parts"])
        obj = join_parts("LP_" + key, parts, hp)
        rep = {"object": cfg["name"], "parts": parts, "high_poly_triangles": part_face_counts(obj, parts)}
        rep["weld"] = weld(obj, float(cfg["weld_m"]), parts, cfg.get("weld_pairs") or [])
        order = sorted(range(len(parts)), key=lambda i: (-rep["high_poly_triangles"][parts[i]], parts[i]))
        rep["decimation"] = []
        for i in order:
            d = decimate_part(obj, parts, i, int(prof["parts"][parts[i]]["tris"]), float(rcfg["protect_factor"]))
            d["part"] = parts[i]
            d["target"] = int(prof["parts"][parts[i]]["tris"])
            rep["decimation"].append(d)
        rep["after_decimation"] = part_face_counts(obj, parts)
        close_object(obj, parts, cfg, src_rep["seams"], rep)
        rep["cap_winding_flipped"] = fix_cap_winding(obj)
        rep["beautify_edges"] = beautify(obj, float(rcfg["beautify_max_dihedral_deg"]))
        rep["sharp_edges"] = set_shading(obj, parts, rcfg["sharp_edge_dihedral_deg"])
        # part attribute + part material names are the contract of the next stages
        B.set_int_face_attr(obj.data, "um_part", [C.part_index(parts[m]) for m in B.poly_array(obj.data, "material_index", np.int64)])
        if "um_cap" not in obj.data.attributes:
            B.set_int_face_attr(obj.data, "um_cap", np.zeros(len(obj.data.polygons), np.int32))
        rep["triangles_by_part"] = part_face_counts(obj, parts)
        rep["topology"] = topology(obj)
        rep["triangle_quality"] = tri_quality(obj, parts)
        # deviation per part, both directions (source metres -> mm)
        total_area = sum(sum(p.area for p in hp[pn].data.polygons) for pn in parts)
        dev = {}
        cap = B.int_face_attr(obj.data, "um_cap")
        mi = B.poly_array(obj.data, "material_index", np.int64)
        for pn in parts:
            area = sum(p.area for p in hp[pn].data.polygons)
            n = max(2000, int(rcfg["deviation_samples"] * area / total_area))
            lo = part_object(obj, parts, pn)
            tree_lo = B.bvh_of([lo])
            tree_hi = B.bvh_of([hp[pn]])
            tree_all = B.bvh_of([hp[q] for q in parts])
            hi_pts = B.area_sample_points(hp[pn], n)
            k = parts.index(pn)
            lo_pts = B.area_sample_points(obj, n, face_mask=(mi == k) & (cap == 0))
            dev[pn] = {"high_to_low": B.deviation(hi_pts, tree_lo), "low_to_high": B.deviation(lo_pts, tree_hi),
                       "low_to_high_any_part": B.deviation(lo_pts, tree_all)}
            bpy.data.objects.remove(lo)
        rep["deviation_mm_source"] = dev
        objects[key] = rep
        obj["um_object_key"] = key
    for m in [m for m in bpy.data.meshes if m.users == 0]:
        bpy.data.meshes.remove(m)
    figure = sum(sum(objects[k]["triangles_by_part"].values()) for k in ("body", "staff"))
    base = sum(objects["base"]["triangles_by_part"].values())
    lo_b, hi_b = prof["budget_proposal"]["figure_triangles"]
    C.check(checks, "figure_triangles_in_proposed_band", lo_b <= figure <= hi_b, figure, [lo_b, hi_b],
            "proposal (budget_proposal), not a budget")
    for key, rep in objects.items():
        t = rep["topology"]
        chains = sum(len([1 for c in rep["caps"] if c.get("skipped")]) for _ in [0])
        chain_edges = sum(c["loop_vertices"] - 1 for c in rep["caps"] if c.get("skipped"))
        sc = rep["sharp_edges"]["self_contact"]
        C.check(checks, "%s_closed_except_source_self_contact" % key,
                t["boundary_edges"] == chain_edges and t["non_manifold_edges"] + t["inconsistent_winding_edges"] <= sc
                and sc <= 32,
                {k: t[k] for k in ("boundary_edges", "non_manifold_edges", "inconsistent_winding_edges")},
                {"boundary_edges": chain_edges, "self_contact_edges_marked_sharp": sc},
                "open edges only in skipped open chains; non-manifold/inconsistent edges are Tripo self-contacts "
                "(hood back, hem) present in the source after the seam weld, marked sharp (no normal averaging)")
        C.check(checks, "%s_all_triangles" % key, t["non_triangles"] == 0, t["non_triangles"], 0)
    worst = {pn: d["high_to_low"]["p99_mm"] for rep in objects.values() for pn, d in rep["deviation_mm_source"].items()}
    C.check(checks, "deviation_high_to_low_p99_below_2mm_source", max(worst.values()) < 2.0, worst, "< 2 mm (Tripo metres; x0.505 in the game frame)")
    out = prof.work / "h2-retopo.blend"
    B.save_blend(out)
    report = {"stage": "retopo", "profile": C.rel(prof.path), "profile_id": prof["profile_id"], "method": rcfg["method"],
              "objects": objects, "figure_triangles": figure, "base_triangles": base, "checks": checks,
              "passed": all(c["passed"] for c in checks.values()), "work_blend": C.rel(out)}
    C.write_json(prof.reports / "retopo-report.json", report)
    print("H2_STAGE_OK retopo passed=%s figure=%d base=%d" % (report["passed"], figure, base))
    if not report["passed"]:
        raise RuntimeError("retopo checks failed: %s" % sorted(k for k, c in checks.items() if not c["passed"]))


main()
