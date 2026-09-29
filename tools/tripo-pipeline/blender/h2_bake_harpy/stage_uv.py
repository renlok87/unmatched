"""H2 stage 3 — UV0 of the game mesh and one packed atlas (headless only).

    blender -b --factory-startup --python stage_uv.py -- <profile.json> <run_dir>

Input <run>/work/h2-lowpoly.blend. Charts per LP part:
  1. seed charts = Smart UV Project islands (uv.seed_angle_limit_deg; the decimated feather surface alone gives
     ~3.7k islands for 25.7k triangles at 66 deg, measured 2026-09-29);
  2. greedy merge, smallest chart first, into the neighbour with the longest shared edge, while the merged chart stays
     a topological disk (V - E + F = 1) and every face normal stays within uv.max_chart_normal_angle_deg of the chart's
     mean normal, until a chart reaches uv.min_chart_area_fraction of its part;
  3. seams on chart borders, Unwrap MINIMUM_STRETCH (SLIM, no_flip); charts that still fold go back to their seed
     islands and are unwrapped again;
then over all parts: Average Islands Scale (uniform texel density), islands of the priority regions
(lowpoly.parts.*.priority_regions[].uv_density_factor; an island counts when >= uv.region_island_share of its 3D area
lies in the region box) scaled by the factor about their centre, Pack Islands (rotate, scale to fit, concave shapes,
margin as a fraction = uv.margin_px / uv.atlas_px). Writes <run>/work/h2-uv.blend and <run>/work/uv-tris.npz (UV of
every triangle corner, 3D corners, part, region density factor, island) for uv_check.py / textures.py.
"""

import heapq
import math
import sys
import time
from pathlib import Path

import bmesh
import bpy
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import common as C  # noqa: E402
from textures_common import rasterise  # noqa: E402

C.require_background("stage_uv.py")
args = C.script_args()
PROFILE_PATH, RUN = Path(args[0]).resolve(), Path(args[1]).resolve()
P = C.load_profile(PROFILE_PATH)
U = P["uv"]
t0 = time.time()
bpy.ops.wm.open_mainfile(filepath=str(RUN / "work" / "h2-lowpoly.blend"))
scene = bpy.context.scene
parts_cfg = P["lowpoly"]["parts"]
order = sorted(parts_cfg, key=lambda n: int(n.rsplit("_", 1)[1]))
lp = [bpy.data.objects["LP_" + p] for p in order]
for o in scene.objects:
    o.select_set(False)
for o in lp:
    o.select_set(True)
    if U.get("charts", "tripo") != "tripo" or not o.data.uv_layers:
        for layer in list(o.data.uv_layers):
            o.data.uv_layers.remove(layer)
        o.data.uv_layers.new(name="UVMap")
bpy.context.view_layer.objects.active = lp[0]


def edit_all(*ops):
    bpy.ops.object.mode_set(mode="EDIT")
    bpy.ops.mesh.select_all(action="SELECT")
    for op in ops:
        op()
    bpy.ops.object.mode_set(mode="OBJECT")


def uv_islands(me):
    """Face islands: faces joined across edges whose two loops carry the same UVs on both ends."""
    uv = me.uv_layers[0].data
    parent = list(range(len(me.polygons)))

    def find(a):
        while parent[a] != a:
            parent[a] = parent[parent[a]]
            a = parent[a]
        return a

    edge_loops = {}
    for p in me.polygons:
        for li in p.loop_indices:
            lp_ = me.loops[li]
            nxt = me.loops[p.loop_start + (li - p.loop_start + 1) % p.loop_total]
            a, b = lp_.vertex_index, nxt.vertex_index
            key = (min(a, b), max(a, b))
            uva, uvb = tuple(round(c, 7) for c in uv[li].uv), tuple(round(c, 7) for c in uv[nxt.index].uv)
            ends = {a: uva, b: uvb}
            if key in edge_loops:
                q, other = edge_loops[key]
                if other == ends:
                    ra, rb = find(p.index), find(q)
                    if ra != rb:
                        parent[max(ra, rb)] = min(ra, rb)
            else:
                edge_loops[key] = (p.index, ends)
    return [find(i) for i in range(len(me.polygons))]


def topology(me):
    fverts = [tuple(p.vertices) for p in me.polygons]
    fedges = [tuple(me.loops[li].edge_index for li in p.loop_indices) for p in me.polygons]
    efaces = {}
    for f, es in enumerate(fedges):
        for e in es:
            efaces.setdefault(e, []).append(f)
    return fverts, fedges, efaces


def merge_charts(me, chart, min_area, max_angle_deg):
    """Greedy merge (see module doc). Returns (chart per face, merges)."""
    cosmax = math.cos(math.radians(max_angle_deg))
    fa = np.array([p.area for p in me.polygons])
    fn = np.array([tuple(p.normal) for p in me.polygons])
    fverts, fedges, efaces = topology(me)
    elen = np.array([(me.vertices[e.vertices[0]].co - me.vertices[e.vertices[1]].co).length for e in me.edges])
    members = {}
    for f, c in enumerate(chart):
        members.setdefault(c, set()).add(f)
    area = {c: float(fa[sorted(m)].sum()) for c, m in members.items()}
    nsum = {c: (fn[sorted(m)] * fa[sorted(m)][:, None]).sum(0) for c, m in members.items()}
    owner = list(chart)

    def neighbours(c):
        shared = {}
        for f in members[c]:
            for e in fedges[f]:
                fs = efaces[e]
                if len(fs) != 2:
                    continue
                g = fs[0] if fs[1] == f else fs[1]
                oc = owner[g]
                if oc != c:
                    shared[oc] = shared.get(oc, 0.0) + elen[e]
        return sorted(shared.items(), key=lambda kv: (-kv[1], kv[0]))

    def euler(fs):
        vs, es = set(), set()
        for f in fs:
            vs.update(fverts[f])
            es.update(fedges[f])
        return len(vs) - len(es) + len(fs)

    heap = [(area[c], c) for c in sorted(members)]
    heapq.heapify(heap)
    merges = 0
    while heap:
        a, c = heapq.heappop(heap)
        if c not in members or a != area[c] or area[c] >= min_area:
            continue
        for n, _len in neighbours(c):
            fs = members[c] | members[n]
            m = nsum[c] + nsum[n]
            ln = float(np.linalg.norm(m))
            if ln < 1e-12:
                continue
            if (fn[sorted(fs)] @ (m / ln)).min() < cosmax:
                continue
            if euler(fs) != 1:
                continue
            keep, gone = (c, n) if c < n else (n, c)
            for f in members[gone]:
                owner[f] = keep
            members[keep] = fs
            nsum[keep] = m
            area[keep] = area[c] + area[n]
            del members[gone], nsum[gone], area[gone]
            merges += 1
            if area[keep] < min_area:
                heapq.heappush(heap, (area[keep], keep))
            break
    return owner, merges


def set_seams(me, chart):
    _fverts, _fedges, efaces = topology(me)
    seams = np.zeros(len(me.edges), bool)
    for e, fs in efaces.items():
        if len(fs) != 2 or chart[fs[0]] != chart[fs[1]]:
            seams[e] = True
    me.edges.foreach_set("use_seam", seams)
    return int(seams.sum())


def uv_flips(me):
    """Faces whose UV winding disagrees with the majority (area-weighted) of their island, or with ~zero UV area."""
    uvd = me.uv_layers[0].data
    isl = uv_islands(me)
    signed = {}
    for p in me.polygons:
        u = [uvd[li].uv for li in p.loop_indices]
        a = 0.0
        for k in range(1, len(u) - 1):
            a += ((u[k].x - u[0].x) * (u[k + 1].y - u[0].y) - (u[k + 1].x - u[0].x) * (u[k].y - u[0].y)) / 2
        signed.setdefault(isl[p.index], []).append((p.index, a))
    bad = set()
    for _root, fa in signed.items():
        tot = sum(a for _f, a in fa)
        for f, a in fa:
            if a * tot <= 0:
                bad.add(f)
    return bad


def unwrap():
    edit_all(lambda: bpy.ops.uv.unwrap(method=U.get("unwrap_method", "MINIMUM_STRETCH"), fill_holes=True,
                                       correct_aspect=True, margin=0.0, no_flip=True,
                                       iterations=int(U.get("unwrap_iterations", 30))))


def self_overlapping_faces(me, res=int(U.get("overlap_check_px", 512))):
    """Faces involved in UV self-overlap: each island rasterised in its own bbox (res px), triangles shrunk by 1e-5
    so shared edges do not count; the first and the last triangle written to a twice-covered texel are returned."""
    me.calc_loop_triangles()
    uvd = me.uv_layers[0].data
    isl = uv_islands(me)
    by = {}
    for lt in me.loop_triangles:
        by.setdefault(isl[lt.polygon_index], []).append((lt.polygon_index, [tuple(uvd[li].uv) for li in lt.loops]))
    bad = set()
    for _root, tris in by.items():
        if len(tris) < 2:
            continue
        uv = np.array([t for _f, t in tris], np.float64)
        lo_, hi_ = uv.reshape(-1, 2).min(0), uv.reshape(-1, 2).max(0)
        span = max(float((hi_ - lo_).max()), 1e-12)
        q = (uv - lo_) / span * 0.98 + 0.01
        c = q.mean(1, keepdims=True)
        q = c + (q - c) * (1 - 1e-5)
        first = np.full((res, res), -1, np.int32)
        lab, cover = rasterise(q, np.arange(len(q)), res, first)
        m = cover > 1
        if m.any():
            polys = np.array([f for f, _t in tris])
            bad.update(polys[np.unique(np.concatenate([lab[m], first[m]]))].tolist())
    return bad


def grow(me, faces, rings):
    faces = set(faces)
    for _ in range(rings):
        vs = set()
        for f in faces:
            vs.update(me.polygons[f].vertices)
        faces |= {p.index for p in me.polygons if not vs.isdisjoint(p.vertices)}
    return faces


charts_report, seed, charts = {}, {}, {}
if U.get("charts", "tripo") == "tripo":
    # Tripo's texture charts survive the collapse decimation (stage_lowpoly keep_tripo_uv); only the triangles the
    # decimation folded or overlapped are cut out and projected again below
    for part, o in zip(order, lp):
        charts_report[part] = {"tripo_islands_after_decimation": len(set(uv_islands(o.data)))}
else:
    # 1) seed charts
    edit_all(lambda: bpy.ops.uv.smart_project(angle_limit=math.radians(float(U.get("seed_angle_limit_deg", 89.0))),
                                              island_margin=0.0, area_weight=0.0, correct_aspect=True,
                                              scale_to_bounds=False))
    for part, o in zip(order, lp):
        me = o.data
        isl = uv_islands(me)
        seed[part] = isl
        part_area = sum(p.area for p in me.polygons)
        min_area = float(U.get("min_chart_area_fraction", 0.02)) * part_area
        merged, n = merge_charts(me, isl, min_area, float(U.get("max_chart_normal_angle_deg", 70.0)))
        charts[part] = merged
        charts_report[part] = {"seed_islands": len(set(isl)), "merges": n, "charts": len(set(merged)),
                               "seam_edges": set_seams(me, merged), "min_chart_area_m2": C.r(min_area, 8)}
    unwrap()
# repair of the charts the decimation damaged:
#   round 0 — every island with a folded (flipped UV winding) or self-overlapping triangle is unwrapped again as a
#             whole with SLIM (MINIMUM_STRETCH, no_flip) inside its own seams (its Tripo chart border);
#   rounds 1.. — faces still folding/overlapping, grown by uv.repair_rings, get a Smart UV Project of their own
#             (uv.fallback_angle_limit_deg, 10 deg less each round)
fallback = {}


def select_faces(per_part):
    """Edit mode, face select mode: exactly the listed faces selected (flushed down to their edges/vertices), so the
    UV operators touch only them (face flags set in object mode are re-flushed from all-selected vertices)."""
    if bpy.context.object.mode != "EDIT":
        bpy.ops.object.mode_set(mode="EDIT")
    bpy.context.tool_settings.mesh_select_mode = (False, False, True)
    for part, o in zip(order, lp):
        bm = bmesh.from_edit_mesh(o.data)
        bm.faces.ensure_lookup_table()
        for v in bm.verts:
            v.select = False
        for e in bm.edges:
            e.select = False
        sel = set(per_part.get(part, ()))
        for f in bm.faces:
            f.select = f.index in sel
        bm.select_mode = {"FACE"}
        bm.select_flush_mode()
        bmesh.update_edit_mesh(o.data)


for rnd in range(int(U.get("fallback_rounds", 3))):
    todo = {}
    for part, o in zip(order, lp):
        bad = uv_flips(o.data) | self_overlapping_faces(o.data)
        if not bad:
            continue
        if rnd == 0:
            isl = uv_islands(o.data)
            roots = {isl[f] for f in bad}
            todo[part] = {f for f in range(len(o.data.polygons)) if isl[f] in roots}
            set_seams(o.data, isl)
        else:
            todo[part] = grow(o.data, bad, int(U.get("repair_rings", 1)))
    if not todo:
        break
    for part in order:
        fallback.setdefault(part, []).append(len(todo.get(part, ())))
    select_faces(todo)
    if rnd == 0:
        bpy.ops.uv.unwrap(method="MINIMUM_STRETCH", fill_holes=True, correct_aspect=True, margin=0.0, no_flip=True,
                          iterations=int(U.get("unwrap_iterations", 30)))
    else:
        bpy.ops.uv.smart_project(angle_limit=math.radians(float(U.get("fallback_angle_limit_deg", 66.0)) - 10.0 * (rnd - 1)),
                                 island_margin=0.0, area_weight=0.0, correct_aspect=True, scale_to_bounds=False)
    bpy.ops.object.mode_set(mode="OBJECT")
select_faces({part: range(len(o.data.polygons)) for part, o in zip(order, lp)})
bpy.ops.object.mode_set(mode="OBJECT")
flips_after = {part: len(uv_flips(o.data)) for part, o in zip(order, lp)}
overlap_after = {part: len(self_overlapping_faces(o.data)) for part, o in zip(order, lp)}
edit_all(lambda: bpy.ops.uv.select_all(action="SELECT"),
         lambda: bpy.ops.uv.average_islands_scale(scale_uv=False, shear=False))

# priority scaling of islands
scaled = {}
share_min = float(U.get("region_island_share", 0.5))
for part, o in zip(order, lp):
    regions = [r for r in parts_cfg[part].get("priority_regions", []) if float(r.get("uv_density_factor", 1.0)) != 1.0]
    if not regions:
        continue
    me = o.data
    isl = uv_islands(me)
    uvd = me.uv_layers[0].data
    groups = {}
    for p, root in zip(me.polygons, isl):
        groups.setdefault(root, []).append(p.index)
    n_scaled = 0
    for root, faces in sorted(groups.items()):
        area = sum(me.polygons[f].area for f in faces)
        best = 1.0
        for reg in regions:
            lo_, hi_ = np.array(reg["box"]["min"]), np.array(reg["box"]["max"])
            inside = sum(me.polygons[f].area for f in faces
                         if np.all((np.array(me.polygons[f].center) >= lo_) & (np.array(me.polygons[f].center) <= hi_)))
            if area > 0 and inside / area >= share_min:
                best = max(best, float(reg["uv_density_factor"]))
        if best != 1.0:
            loops = [li for f in faces for li in me.polygons[f].loop_indices]
            pts = np.array([tuple(uvd[li].uv) for li in loops])
            c = (pts.min(0) + pts.max(0)) / 2
            for li, q in zip(loops, pts):
                uvd[li].uv = tuple(c + (q - c) * best)
            n_scaled += 1
    scaled[part] = {"islands": len(groups), "islands_scaled": n_scaled}

prepack_digest = {}
for part, o in zip(order, lp):
    uvp = np.empty(len(o.data.loops) * 2, np.float64)
    o.data.uv_layers[0].data.foreach_get("uv", uvp)
    prepack_digest[part] = C.hashlib.sha256(np.round(uvp, 9).tobytes()).hexdigest()[:16]
margin = float(U["margin_px"]) / float(U["atlas_px"])
edit_all(lambda: bpy.ops.uv.select_all(action="SELECT"),
         lambda: bpy.ops.uv.pack_islands(udim_source="CLOSEST_UDIM", rotate=True, rotate_method="ANY", scale=True,
                                         merge_overlap=False, margin_method="FRACTION", margin=margin, pin=False,
                                         shape_method=U.get("shape_method", "CONCAVE")))

# export triangles for the checks and the texture post-process
uvs, cos, part_idx, dens, isl_id = [], [], [], [], []
island_offset = 0
islands_report = {}
for k, (part, o) in enumerate(zip(order, lp)):
    me = o.data
    me.calc_loop_triangles()
    isl = uv_islands(me)
    roots = {r: i for i, r in enumerate(sorted(set(isl)))}
    uvd = me.uv_layers[0].data
    regions = parts_cfg[part].get("priority_regions", [])
    for lt in me.loop_triangles:
        uvs.append([tuple(uvd[li].uv) for li in lt.loops])
        cos.append([tuple(me.vertices[v].co) for v in lt.vertices])
        part_idx.append(k)
        c = np.array(lt.center)
        f = 1.0
        for reg in regions:
            if np.all((c >= np.array(reg["box"]["min"])) & (c <= np.array(reg["box"]["max"]))):
                f = max(f, float(reg.get("uv_density_factor", 1.0)))
        dens.append(f)
        isl_id.append(island_offset + roots[isl[lt.polygon_index]])
    islands_report[part] = len(roots)
    island_offset += len(roots)
np.savez_compressed(RUN / "work" / "uv-tris.npz", uv=np.array(uvs, np.float64), co=np.array(cos, np.float64),
                    part=np.array(part_idx, np.int32), density_factor=np.array(dens, np.float32),
                    island=np.array(isl_id, np.int32), parts=np.array(order))
blend = RUN / "work" / "h2-uv.blend"
bpy.ops.wm.save_as_mainfile(filepath=str(blend), compress=False)
C.write_json(RUN / "reports" / "h2-uv-stage.json", {
    "schema": "unmatched.h2-bake.uv-stage/1", "profile": C.rel(PROFILE_PATH), "profile_sha256": C.sha256(PROFILE_PATH),
    "blender": bpy.app.version_string, "settings": U, "charts": charts_report, "fallback_smart_project_faces_per_round": fallback,
    "uv_flipped_faces_after": flips_after, "prepack_uv_digest": prepack_digest, "uv_self_overlap_faces_after": overlap_after, "priority_scaled": scaled, "islands": islands_report,
    "islands_total": island_offset, "triangles": len(uvs), "output_blend": C.rel(blend),
    "seconds": C.r(time.time() - t0, 1)})
print(C.STAGE_MARKER, "uv", len(uvs), island_offset, flush=True)
