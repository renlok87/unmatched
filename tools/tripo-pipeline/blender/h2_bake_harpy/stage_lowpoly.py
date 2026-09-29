"""H2 stage 2 — game-resolution mesh per part (headless only).

    blender -b --factory-startup --python stage_lowpoly.py -- <profile.json> <run_dir>

Input <run>/work/h2-highpoly.blend (stage_import). Profile keys:
  repair.rotate_z_deg          rigid turn of the whole high-poly about Z (source -> authored frame, face -Y)
  repair.drop_parts            parts removed from the figure (and from every bake)
  repair.occluder_only_parts   parts kept only as AO occluders (not in the game mesh)
  repair.trim                  faces of a part removed by boxes (repair_ops.trim_part), e.g. the Janus-hood remnant
  repair.plugs / caps / patches  added high-poly parts (repair_ops: ellipsoid, closed cap over an open loop with a
                               procedural material, copied feather patch with a backing sheet); each is then a part
                               of lowpoly.parts like the Tripo parts
  lowpoly.parts.<part>         role, target_triangles, side (.L/.R) and priority regions (boxes in the authored frame)
  lowpoly.priority_vertex_group_factor, lowpoly.sharp_angle_deg, lowpoly.weld_distance_m
Per part: copy of the high-poly, welded (the textured GLB splits vertices on its UV seams; the per-corner UVs of
Tripo's texture charts are kept when lowpoly.keep_tripo_uv, so the collapse decimation interpolates them and the game
mesh inherits Tripo's charts), material free,
priority vertex group (face box etc.), Decimate COLLAPSE to the target triangle count with the vertex group
protecting the priority region, cleanup (degenerate dissolve, loose geometry), triangulated, smooth with sharp edges
by angle. lowpoly.stitch (stitch.py): after all parts are decimated, the boundaries of neighbouring parts that share a
Tripo cut on the high-poly are made the same polyline (no cracks with one-sided materials). Measured: triangles,
one-sided surface distances high->low and low->high (area-sampled), flipped faces
against the nearest high-poly normal, inconsistent winding edges, open edges.
Output <run>/work/h2-lowpoly.blend (HP_* in the authored frame + LP_*) and <run>/reports/h2-lowpoly-report.json.
"""

import math
import sys
import time
from pathlib import Path

import bmesh
import bpy
import numpy as np
from mathutils import Matrix, Vector
from mathutils.bvhtree import BVHTree

sys.path.insert(0, str(Path(__file__).resolve().parent))
import common as C  # noqa: E402
import repair_ops as R  # noqa: E402
import stitch as SX  # noqa: E402

C.require_background("stage_lowpoly.py")
args = C.script_args()
PROFILE_PATH, RUN = Path(args[0]).resolve(), Path(args[1]).resolve()
P = C.load_profile(PROFILE_PATH)
REP = P["repair"]
LPC = P["lowpoly"]
t0 = time.time()
bpy.ops.wm.open_mainfile(filepath=str(RUN / "work" / "h2-highpoly.blend"))
scene = bpy.context.scene
report = {"schema": "unmatched.h2-bake.lowpoly-report/1", "profile": C.rel(PROFILE_PATH),
          "profile_sha256": C.sha256(PROFILE_PATH), "blender": bpy.app.version_string,
          "input_blend_sha256": C.sha256(RUN / "work" / "h2-highpoly.blend")}

# ---------------------------------------------------------------- repair: rigid turn + dropped parts
rot = Matrix.Rotation(math.radians(float(REP.get("rotate_z_deg", 0.0))), 4, "Z")
for i in range(4):
    for j in range(4):
        if abs(rot[i][j] - round(rot[i][j])) < 1e-9:
            rot[i][j] = float(round(rot[i][j]))
hp = {o.name[3:]: o for o in scene.objects if o.type == "MESH" and o.name.startswith("HP_")}
dropped = {}
for part, why in sorted(REP.get("drop_parts", {}).items()):
    o = hp.pop(part)
    dropped[part] = {"why": why, "triangles": len(o.data.polygons)}
    bpy.data.objects.remove(o)
cn_check = {}
for part, o in sorted(hp.items()):
    me = o.data
    before = np.empty(len(me.loops) * 3, np.float32)
    me.corner_normals.foreach_get("vector", before)
    me.transform(rot)
    me.update()
    after = np.empty(len(me.loops) * 3, np.float32)
    me.corner_normals.foreach_get("vector", after)
    expect = before.reshape(-1, 3) @ np.array(rot.to_3x3()).T
    cn_check[part] = C.r(float(np.einsum("ij,ij->i", expect, after.reshape(-1, 3)).min()), 6)
    o["h2_role"] = "occluder" if part in REP.get("occluder_only_parts", {}) else "highpoly"
# trims: faces of a part removed by boxes (authored frame), before any plug/cap/patch is built
trims = {}
for tr in REP.get("trim", []):
    info = R.trim_part(hp[tr["part"]], tr["boxes"])
    info.update({"boxes": tr["boxes"], "why": tr.get("why")})
    info["open_loops_after_m"] = R.open_loops(hp[tr["part"]], min_z=tr.get("report_loops_min_z"), top=4)
    trims.setdefault(tr["part"], []).append(info)


def add_highpoly(name, me):
    o = bpy.data.objects.new("HP_" + name, me)
    scene.collection.objects.link(o)
    o["h2_role"] = "highpoly"
    hp[name] = o
    return o


# plugs: closed ellipsoids (both high-poly and game mesh) where a dropped part leaves a see-through gap
plugs = {}
for plug in REP.get("plugs", []):
    me = R.ellipsoid_mesh("HP_" + plug["name"], plug["centre_m"], plug["radii_m"], int(plug["u_segments"]),
                          int(plug["v_segments"]))
    for poly in me.polygons:
        poly.use_smooth = True
    me.materials.append(R.feather_material("M_H2_" + plug["name"], {"kind": "flat", "colour_linear": plug["base_color_linear"],
                                                                    "roughness": plug["roughness"]}))
    add_highpoly(plug["name"], me)
    plugs[plug["name"]] = {"triangles": sum(len(q.vertices) - 2 for q in me.polygons), "why": plug.get("why"),
                           "centre_m": plug["centre_m"], "radii_m": plug["radii_m"]}
# caps: closed domed caps over an open loop of a (trimmed) part; high-poly = game-mesh shape, procedural material baked
caps = {}
for cap in REP.get("caps", []):
    kw = {k: cap[k] for k in ("samples", "outward", "skirt_m", "lip_m", "dome_m", "depth_m", "rings", "smooth",
                              "bottom_scale") if k in cap}
    me, info = R.loop_cap(hp[cap["part"]], "HP_" + cap["name"], cap["near_m"], **kw)
    for poly in me.polygons:
        poly.use_smooth = True
    mcfg = dict(cap["material"])
    mcfg.setdefault("uv_span_m", info["uv_span_m"])
    me.materials.append(R.feather_material("M_H2_" + cap["name"], mcfg))
    add_highpoly(cap["name"], me)
    info.update({"why": cap.get("why"), "material": mcfg})
    caps[cap["name"]] = info
# patches: faces of a part copied (with its Tripo UVs and material), moved, optionally backed
patches = {}
for pa in REP.get("patches", []):
    o, info = R.copy_patch(hp[pa["source"]], "HP_" + pa["name"], pa["boxes"], pa.get("pivot", (0.0, 0.0, 0.0)),
                           pa.get("scale", (1.0, 1.0, 1.0)), pa.get("rotate_deg", (0.0, 0.0, 0.0)),
                           pa.get("translate", (0.0, 0.0, 0.0)), pa.get("exclude_boxes", ()),
                           float(pa.get("solidify_m", 0.0)))
    o.name = "HP_" + pa["name"]
    scene.collection.objects.link(o)
    o["h2_role"] = "highpoly"
    hp[pa["name"]] = o
    info.update({"why": pa.get("why"), "boxes": pa["boxes"], "translate": pa.get("translate")})
    patches[pa["name"]] = info
report["repair"] = {"rotate_z_deg": float(REP.get("rotate_z_deg", 0.0)), "dropped_parts": dropped,
                    "occluder_only_parts": REP.get("occluder_only_parts", {}), "trims": trims, "plugs": plugs,
                    "caps": caps, "patches": patches,
                    "corner_normals_min_dot_after_turn": cn_check, "why": REP.get("why")}


# ---------------------------------------------------------------- helpers
def in_box(co, box):
    lo, hi = np.array(box["min"]), np.array(box["max"])
    return np.all((co >= lo) & (co <= hi), axis=1)


def vertex_co(me):
    co = np.empty(len(me.vertices) * 3, np.float32)
    me.vertices.foreach_get("co", co)
    return co.reshape(-1, 3).astype(np.float64)


def sample_surface(v, t, n, seed):
    """Area-weighted deterministic sample of n surface points (and their triangle normals)."""
    nn, area, _c = C.tri_normals_areas(v, t)
    rng = np.random.default_rng(seed)
    p = area / area.sum()
    idx = rng.choice(len(t), size=n, p=p)
    r1, r2 = rng.random(n), rng.random(n)
    s1 = np.sqrt(r1)
    a, b, c = v[t[idx, 0]], v[t[idx, 1]], v[t[idx, 2]]
    pts = (1 - s1)[:, None] * a + (s1 * (1 - r2))[:, None] * b + (s1 * r2)[:, None] * c
    return pts, nn[idx]


def distances(points, bvh):
    d = np.empty(len(points))
    for i, p in enumerate(points):
        hit = bvh.find_nearest(Vector(p))
        d[i] = hit[3] if hit[0] is not None else np.inf
    return d


def stats_mm(d):
    return {"p50_mm": C.r(np.percentile(d, 50) * 1000, 3), "p95_mm": C.r(np.percentile(d, 95) * 1000, 3),
            "p99_mm": C.r(np.percentile(d, 99) * 1000, 3), "max_mm": C.r(d.max() * 1000, 3)}


def inconsistent_edges(me):
    """Edges whose two faces traverse them in the same direction (inconsistent winding)."""
    seen = {}
    bad = 0
    for p in me.polygons:
        vs = list(p.vertices)
        for k in range(len(vs)):
            a, b = vs[k], vs[(k + 1) % len(vs)]
            key = (min(a, b), max(a, b))
            direction = a < b
            if key in seen:
                if seen[key] == direction:
                    bad += 1
            else:
                seen[key] = direction
    return bad


def open_and_nonmanifold(me):
    bm = bmesh.new()
    bm.from_mesh(me)
    open_e = sum(1 for e in bm.edges if len(e.link_faces) == 1)
    nm = sum(1 for e in bm.edges if len(e.link_faces) > 2)
    loose = sum(1 for v in bm.verts if not v.link_faces)
    bm.free()
    return open_e, nm, loose


# ---------------------------------------------------------------- per part decimation
parts_cfg = LPC["parts"]
factor = float(LPC.get("priority_vertex_group_factor", 1.0))
weld = float(LPC.get("weld_distance_m", 1e-6))
sharp = math.radians(float(LPC.get("sharp_angle_deg", 60.0)))
samples = int(LPC.get("distance_samples_per_part", 20000))
parts_report = {}
pending = {}
for part in sorted(parts_cfg, key=lambda n: int(n.rsplit("_", 1)[1])):
    cfg = parts_cfg[part]
    src = hp[part]
    me = src.data.copy()
    me.name = "LP_" + part
    keep_uv = bool(LPC.get("keep_tripo_uv", True))
    for layer in list(me.uv_layers)[1 if keep_uv else 0:]:
        me.uv_layers.remove(layer)
    if keep_uv and me.uv_layers:
        me.uv_layers[0].name = "UVMap"
    me.materials.clear()
    lo = bpy.data.objects.new("LP_" + part, me)
    scene.collection.objects.link(lo)
    bm = bmesh.new()
    bm.from_mesh(me)
    v_before = len(bm.verts)
    bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=weld)
    welded_verts = len(bm.verts)
    bm.to_mesh(me)
    bm.free()
    if me.has_custom_normals:
        with bpy.context.temp_override(object=lo, active_object=lo):
            bpy.ops.mesh.customdata_custom_splitnormals_clear()
    if me.has_custom_normals:
        raise RuntimeError("custom normals survived on " + part)
    tris_in = len(me.polygons)
    # priority vertex group: weight = 1 - protect (Decimate COLLAPSE adds (2 - w1 - w2) * factor * edge length
    # to an edge's cost, so weight 1 decimates freely and weight 0 is protected in proportion to the factor)
    co = vertex_co(me)
    w = np.ones(len(co))
    region_report = {}
    regions = cfg.get("priority_regions", [])
    for reg in regions:
        m = in_box(co, reg["box"])
        w[m] = np.minimum(w[m], 1.0 - float(reg.get("protect", 0.0)))
        region_report[reg["name"]] = {"vertices_highpoly": int(m.sum()), "protect": float(reg.get("protect", 0.0))}
    target = int(cfg["target_triangles"])
    ratio = min(1.0, target / max(1, tris_in))
    protected = bool((w < 1.0).any())
    base_me = me.copy() if protected else None

    def decimate(obj, fac):
        if protected:
            vg = obj.vertex_groups.get("h2_priority") or obj.vertex_groups.new(name="h2_priority")
            for val in sorted(set(w.tolist())):
                vg.add(np.nonzero(w == val)[0].tolist(), float(val), "REPLACE")
        mod = obj.modifiers.new("h2_decimate", "DECIMATE")
        mod.decimate_type = "COLLAPSE"
        mod.use_collapse_triangulate = True
        mod.ratio = ratio
        if protected:
            mod.vertex_group = "h2_priority"
            mod.vertex_group_factor = fac
        with bpy.context.temp_override(object=obj, active_object=obj):
            bpy.ops.object.modifier_apply(modifier=mod.name)

    def region_tris(mesh, reg):
        v, t = C.mesh_arrays(mesh)
        return int(np.all(in_box(v, reg["box"])[t], axis=1).sum())

    search = []
    fac_used = None
    if protected:
        goal = [r_ for r_ in regions if r_.get("min_triangles")]
        lo_f, hi_f = float(LPC.get("factor_search_min", 1e-7)), float(LPC.get("factor_search_max", 1e-2))
        best = hi_f
        for _it in range(int(LPC.get("factor_search_iterations", 10))):
            mid = math.sqrt(lo_f * hi_f)
            tmp_me = base_me.copy()
            tmp = bpy.data.objects.new("h2_tmp", tmp_me)
            scene.collection.objects.link(tmp)
            decimate(tmp, mid)
            counts = {r_["name"]: region_tris(tmp_me, r_) for r_ in goal}
            ok = all(counts[r_["name"]] >= int(r_["min_triangles"]) for r_ in goal)
            search.append({"factor": mid, "triangles": len(tmp_me.polygons), "region_triangles": counts, "meets_min": ok})
            bpy.data.objects.remove(tmp)
            bpy.data.meshes.remove(tmp_me)
            if ok:
                best, hi_f = mid, mid
            else:
                lo_f = mid
        fac_used = best
    decimate(lo, fac_used if protected else 0.0)
    if base_me is not None:
        bpy.data.meshes.remove(base_me)
    # cleanup
    bm = bmesh.new()
    bm.from_mesh(me)
    bmesh.ops.dissolve_degenerate(bm, dist=float(LPC.get("degenerate_dist_m", 1e-6)), edges=bm.edges)
    loose_v = [v for v in bm.verts if not v.link_faces]
    loose_e = [e for e in bm.edges if not e.link_faces]
    bmesh.ops.delete(bm, geom=loose_e, context="EDGES")
    bmesh.ops.delete(bm, geom=[v for v in loose_v if v.is_valid], context="VERTS")
    bmesh.ops.triangulate(bm, faces=[f for f in bm.faces if len(f.verts) > 3], quad_method="BEAUTY",
                          ngon_method="BEAUTY")
    bm.to_mesh(me)
    bm.free()
    pending[part] = dict(cfg=cfg, src=src, me=me, lo=lo, region_report=region_report, target=target, tris_in=tris_in,
                         v_before=v_before, welded_verts=welded_verts, ratio=ratio, fac_used=fac_used, search=search)

# ---------------------------------------------------------------- seam stitching across parts (stitch.py)
ST_CFG = LPC.get("stitch") or {}
stitch_report = None
if ST_CFG.get("enabled"):
    t_s = time.time()
    exclude = set(ST_CFG.get("exclude_parts", []))
    hp_cut = {p: hp[p] for p in pending if p not in exclude}
    chains = SX.shared_chains(hp_cut, tol_hp=float(ST_CFG.get("tol_hp_m", 1e-5)),
                              min_vertices=int(ST_CFG.get("min_chain_vertices", 8)))
    stitch_report = SX.stitch_parts({p: pending[p]["me"] for p in hp_cut}, chains,
                                    snap_m=float(ST_CFG.get("snap_m", 0.002)),
                                    merge_m=float(ST_CFG.get("merge_m", 0.0005)),
                                    max_edge_factor=float(ST_CFG.get("max_edge_factor", 1.5)),
                                    junctions=bool(ST_CFG.get("junctions", True)),
                                    # slivers: 1.2 x the export check (1e-4 cm2 at the final scale) in source m2
                                    min_area_m2=1.2e-8 / float(P["seat"]["expected_scale"]) ** 2)
    stitch_report["chains"] = {"%s|%s" % k: [int(len(c)) for c in v] for k, v in sorted(chains.items())}
    stitch_report["settings"] = ST_CFG
    stitch_report["seconds"] = C.r(time.time() - t_s, 1)
report["stitch"] = stitch_report

for part in sorted(pending, key=lambda n: int(n.rsplit("_", 1)[1])):
    st = pending[part]
    cfg, src, me, lo, region_report = st["cfg"], st["src"], st["me"], st["lo"], st["region_report"]
    target, tris_in, v_before, welded_verts = st["target"], st["tris_in"], st["v_before"], st["welded_verts"]
    ratio, fac_used, search = st["ratio"], st["fac_used"], st["search"]
    for p in me.polygons:
        p.use_smooth = True
    me.set_sharp_from_angle(angle=sharp)
    me.update()
    # measurements
    vl, tl = C.mesh_arrays(me)
    vh, th = C.mesh_arrays(src.data)
    bvh_low = BVHTree.FromPolygons(vl.tolist(), tl.tolist(), all_triangles=True)
    bvh_high = BVHTree.FromPolygons(vh.tolist(), th.tolist(), all_triangles=True)
    ph, _nh = sample_surface(vh, th, samples, seed=int(part.rsplit("_", 1)[1]))
    pl, nl = sample_surface(vl, tl, samples // 2, seed=1000 + int(part.rsplit("_", 1)[1]))
    d_hl = distances(ph, bvh_low)
    d_lh = distances(pl, bvh_high)
    flipped = 0
    for p_, n_ in zip(pl, nl):
        hit = bvh_high.find_nearest(Vector(p_))
        if hit[0] is not None and Vector(n_).dot(hit[1]) < -0.2:
            flipped += 1
    nn, area, _ = C.tri_normals_areas(vl, tl)
    open_e, nm, loose = open_and_nonmanifold(me)
    for reg in cfg.get("priority_regions", []):
        m = in_box(vl, reg["box"])
        tri_in = int(np.all(in_box(vl, reg["box"])[tl], axis=1).sum())
        region_report[reg["name"]].update({"vertices_lowpoly": int(m.sum()), "triangles_lowpoly": tri_in,
                                           "min_triangles": reg.get("min_triangles"),
                                           "uv_density_factor": reg.get("uv_density_factor", 1.0)})
    lo["h2_part"] = part
    lo["h2_role"] = cfg.get("role", "")
    parts_report[part] = {
        "role": cfg.get("role"), "side": cfg.get("side"), "target_triangles": target,
        "triangles_highpoly": tris_in, "vertices_highpoly_split": v_before, "vertices_highpoly_welded": welded_verts,
        "triangles": len(tl), "vertices": len(vl), "decimate_ratio": C.r(ratio, 6),
        "priority_regions": region_report, "vertex_group_factor": fac_used, "factor_search": search,
        "distance_high_to_low": stats_mm(d_hl), "distance_low_to_high": stats_mm(d_lh),
        "faces_flipped_vs_highpoly_fraction": C.r(flipped / len(pl), 5),
        "inconsistent_winding_edges": inconsistent_edges(me), "open_edges": open_e, "non_manifold_edges": nm,
        "loose_vertices": loose, "min_triangle_area_mm2": C.r(area.min() * 1e6, 6),
        "triangles_below_1e-4_cm2_at_final_scale": int((area * 1e4 * float(P["seat"]["expected_scale"]) ** 2 < 1e-4).sum()),
    }
    print("lowpoly", part, len(tl), parts_report[part]["distance_high_to_low"], flush=True)

report["parts"] = parts_report
report["triangles_total"] = int(sum(p["triangles"] for p in parts_report.values()))
report["settings"] = {"decimate": "COLLAPSE, use_collapse_triangulate, vertex group h2_priority (factor %g)" % factor,
                      "weld_distance_m": weld, "sharp_angle_deg": float(LPC.get("sharp_angle_deg", 60.0)),
                      "distance_samples_per_part": samples,
                      "why_not_quadriflow": LPC.get("why_not_quadriflow")}
report["seconds"] = C.r(time.time() - t0, 1)
blend = RUN / "work" / "h2-lowpoly.blend"
bpy.ops.wm.save_as_mainfile(filepath=str(blend), compress=False)
report["output_blend"] = C.rel(blend)
C.write_json(RUN / "reports" / "h2-lowpoly-report.json", report)
print(C.STAGE_MARKER, "lowpoly", report["triangles_total"], flush=True)
