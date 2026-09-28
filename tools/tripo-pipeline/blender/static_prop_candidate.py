"""P1.5: static prop candidate from a Tripo GLB (clean -> repair -> UV check -> BC/N/ORM -> FBX -> round trip).

Run headless (never touches live Blender sessions):
  blender -b --factory-startup --python-exit-code 1 \
      --python tools/tripo-pipeline/blender/static_prop_candidate.py -- <params.json>

params.json (source_glb, out_dir, fbx_preset: absolute or relative to the repository root):
  repo_root (optional; omit it in committed params): absent -> the checkout that contains this script
      (tools/tripo-pipeline/blender/ -> three levels up); relative -> resolved against the folder of
      params.json; absolute -> used as is,
  source_glb, out_dir, asset_name (SM_*), texture_prefix (T_*), material_name (M_*),
  target_height_m (PROPOSED value from 04/17, not a budget), texture_size (px),
  fbx_preset (blender/_tools/presets/UM_FBX_v1.json), bake_ao (bool), ao_samples, ao_distance_m,
  geometry_repair (optional; null = keep Tripo geometry): {centre_xy_m_prescale, radius_m_prescale,
      z_min_m_prescale, small_island_max_faces} - a disc on the lid top that is deleted and closed again
      with a flat fill (see repair_region), coordinates in the imported glTF space before scaling,
  require_closed_manifold (default true): fail the run if the welded mesh still has open/non-manifold
      edges or inconsistent winding after the repair (set false only for measurement-only runs).

Outputs in out_dir:
  work/<asset>.blend                       editable scene (metres, pivot at base centre)
  export/<asset>.fbx                       UM_FBX_v1 (cm numbers, UnitScaleFactor 1.0, -Y fwd, Z up, +90 Z)
  export/<prefix>_BC.png  (sRGB)           base colour, RGB
  export/<prefix>_N.png   (Linear)         tangent normal, DirectX (green flipped from glTF/OpenGL)
  export/<prefix>_ORM.png (Linear)         R = AO (baked here or 1.0), G = roughness, B = metallic
  reports/candidate-report.json            all measurements (status "measured"; never "accepted")
  preview/*.png                            renders + UV layout

"Linear" for N/ORM is an import setting (UE: TC_Normalmap / TC_Masks, sRGB off). Blender writes
sRGB/gAMA/cHRM chunks into every 8-bit PNG; they are stripped from N and ORM here, but a PNG without
colour chunks is still read as sRGB by most tools, so the import setting is what counts.

Nothing here is an art decision; numbers are measurements of this candidate.
"""

import datetime
import hashlib
import json
import math
import struct
import sys
from pathlib import Path

import bmesh
import bpy
import numpy as np
from mathutils import Matrix, Vector, geometry as mgeo
from mathutils.kdtree import KDTree

FIXED_TIME = datetime.datetime(2000, 1, 1, 0, 0, 0)


# ----------------------------------------------------------------------------- helpers
def r(v, n=6):
    return None if v is None else round(float(v), n)


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def text_sha256_lf(path):
    """sha256 of a text file with CRLF -> LF, i.e. of the git blob: the same value in every checkout,
    whatever core.autocrlf did to the working tree (check: tr -d '\\r' < file | sha256sum)."""
    return hashlib.sha256(Path(path).read_bytes().replace(b"\r\n", b"\n")).hexdigest()


SCRIPT_REPO_ROOT = Path(__file__).resolve().parents[3]  # <repo>/tools/tripo-pipeline/blender/<this file>


def load_params():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    if not argv:
        raise SystemExit("params.json required after --")
    params_path = Path(argv[0]).resolve()
    params = json.loads(params_path.read_text(encoding="utf-8"))
    raw_root = params.get("repo_root")
    if raw_root is None:
        root = SCRIPT_REPO_ROOT
    else:
        root = Path(raw_root)
        root = root if root.is_absolute() else params_path.parent / root
    root = root.resolve()
    params["repo_root"] = root

    def rp(key):
        p = Path(params[key])
        return p if p.is_absolute() else root / p

    for key in ("source_glb", "out_dir", "fbx_preset"):
        params[key] = rp(key)
    missing = [k for k in ("source_glb", "fbx_preset") if not params[k].is_file()]
    if missing:
        raise SystemExit("repo root %s (%s): missing %s - run the script from a repository checkout or set "
                         "repo_root in params.json" % (root, "script location" if raw_root is None else "params",
                                                       ", ".join("%s=%s" % (k, params[k]) for k in missing)))
    return params


def rel(path, P):
    try:
        return Path(path).resolve().relative_to(Path(P["repo_root"]).resolve()).as_posix()
    except ValueError:
        return Path(path).as_posix()


def glb_json(path):
    data = path.read_bytes()
    magic, _ver, total = struct.unpack_from("<4sII", data, 0)
    if magic != b"glTF" or total != len(data):
        raise RuntimeError("not a complete GLB: %s" % path)
    jlen = struct.unpack_from("<I", data, 12)[0]
    return json.loads(data[20:20 + jlen]), data, 20 + jlen + 8


def mesh_objects():
    return sorted((o for o in bpy.context.scene.objects if o.type == "MESH"), key=lambda o: o.name)


def triangles(obj):
    return sum(len(p.vertices) - 2 for p in obj.data.polygons)


def world_bounds(objs):
    # from vertex data (bound_box can be stale right after mesh.transform in background mode)
    pts = [o.matrix_world @ v.co for o in objs for v in o.data.vertices]
    lo = Vector((min(p.x for p in pts), min(p.y for p in pts), min(p.z for p in pts)))
    hi = Vector((max(p.x for p in pts), max(p.y for p in pts), max(p.z for p in pts)))
    return lo, hi


# ----------------------------------------------------------------------------- geometry
def geometry_stats(obj, weld=1e-6):
    """Topology diagnostics on a welded copy (UV/normal seams split vertices in glTF)."""
    bm = bmesh.new()
    bm.from_mesh(obj.data)
    raw_verts = len(bm.verts)
    bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=weld)
    bm.edges.ensure_lookup_table()
    boundary = sum(1 for e in bm.edges if e.is_boundary)
    non_manifold = sum(1 for e in bm.edges if not e.is_manifold and not e.is_boundary)
    wire = sum(1 for e in bm.edges if e.is_wire)
    loose_verts = sum(1 for v in bm.verts if not v.link_edges)
    degenerate = sum(1 for f in bm.faces if f.calc_area() < 1e-12)
    # winding consistency: faces whose normal disagrees with a recalculated outward normal
    before = {f.index: f.normal.copy() for f in bm.faces}
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    flipped = [f.index for f in bm.faces if before[f.index].dot(f.normal) < 0]
    # signed volume (positive = outward winding for a closed mesh)
    vol = bm.calc_volume(signed=True)
    shells = 0
    seen = set()
    for f in bm.faces:
        if f.index in seen:
            continue
        shells += 1
        stack = [f]
        seen.add(f.index)
        while stack:
            cur = stack.pop()
            for e in cur.edges:
                for nf in e.link_faces:
                    if nf.index not in seen:
                        seen.add(nf.index)
                        stack.append(nf)
    stats = {
        "vertices_as_stored": len(obj.data.vertices),
        "vertices_welded_1e-6m": len(bm.verts),
        "faces": len(obj.data.polygons),
        "triangles": triangles(obj),
        "welded_boundary_edges": boundary,
        "welded_non_manifold_edges": non_manifold,
        "wire_edges": wire,
        "loose_vertices": loose_verts,
        "degenerate_faces_area_lt_1e-12": degenerate,
        "faces_with_inconsistent_winding": len(flipped),
        "connected_shells": shells,
        "signed_volume_m3": r(vol, 9),
        "raw_vertex_count_before_weld": raw_verts,
    }
    bm.free()
    return stats, flipped


def clean_mesh(obj):
    """Conservative clean-up that keeps UVs and Tripo's shading normals intact."""
    bm = bmesh.new()
    bm.from_mesh(obj.data)
    removed = {"loose_vertices": 0, "wire_edges": 0, "degenerate_faces": 0}
    loose = [v for v in bm.verts if not v.link_faces]
    removed["loose_vertices"] = len(loose)
    if loose:
        bmesh.ops.delete(bm, geom=loose, context="VERTS")
    wire = [e for e in bm.edges if not e.link_faces]
    removed["wire_edges"] = len(wire)
    if wire:
        bmesh.ops.delete(bm, geom=wire, context="EDGES")
    degenerate = [f for f in bm.faces if f.calc_area() < 1e-12]
    removed["degenerate_faces"] = len(degenerate)
    if degenerate:
        bmesh.ops.delete(bm, geom=degenerate, context="FACES_ONLY")
    bm.to_mesh(obj.data)
    bm.free()
    obj.data.update()
    return removed


def fix_winding(obj, flipped_face_indices):
    if not flipped_face_indices:
        return 0
    bm = bmesh.new()
    bm.from_mesh(obj.data)
    bm.faces.ensure_lookup_table()
    faces = [bm.faces[i] for i in flipped_face_indices if i < len(bm.faces)]
    bmesh.ops.reverse_faces(bm, faces=faces)
    bm.to_mesh(obj.data)
    bm.free()
    return len(faces)


# ----------------------------------------------------------------------------- geometry repair
def bm_uv_islands(bm, uvl):
    """Island id per face: faces sharing a vertex with the same UV are connected (as uv_analysis)."""
    parent = list(range(len(bm.faces)))

    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    owner = {}
    for f in bm.faces:
        for l in f.loops:
            k = (l.vert.index, round(l[uvl].uv[0], 6), round(l[uvl].uv[1], 6))
            if k in owner:
                a, b = find(f.index), find(owner[k])
                if a != b:
                    parent[a] = b
            else:
                owner[k] = f.index
    return [find(i) for i in range(len(bm.faces))]


def uv_signed_area(f, uvl):
    a, b, c = (l[uvl].uv for l in f.loops[:3])
    return 0.5 * ((b.x - a.x) * (c.y - a.y) - (c.x - a.x) * (b.y - a.y))


def detect_fold_faces(bm, uvl, z_min, small_island_max_faces):
    """Faces that make up the lid fold, found by measurement, not by index:
    tiny UV islands (Tripo packs the fold into slivers), UV triangles flipped against their island,
    and faces on the lid top whose normal points down."""
    bm.verts.index_update()
    bm.faces.index_update()
    island = bm_uv_islands(bm, uvl)
    size, signs = {}, {}
    for f in bm.faces:
        size[island[f.index]] = size.get(island[f.index], 0) + 1
        signs.setdefault(island[f.index], []).append(uv_signed_area(f, uvl))
    majority = {k: (1 if sum(1 for s in v if s >= 0) >= sum(1 for s in v if s < 0) else -1) for k, v in signs.items()}
    reasons = {}
    for f in bm.faces:
        k = island[f.index]
        why = []
        if size[k] <= small_island_max_faces:
            why.append("uv_island_le_%d_faces" % small_island_max_faces)
        if uv_signed_area(f, uvl) * majority[k] < 0:
            why.append("uv_flipped_vs_island")
        if f.calc_center_median().z >= z_min and f.normal.z < 0:
            why.append("faces_down_on_lid_top")
        if why:
            reasons[f.index] = why
    return reasons


def repair_region(obj, cfg):
    """Delete a disc of the lid top that contains every detected fold face, then close the hole flat.

    - region = faces with centroid z >= z_min and XY distance to centre <= radius (glTF space, pre-scale);
      every detected fold face must lie in it, otherwise the run fails (params cannot silently miss it);
    - the hole rim is welded (glTF splits vertices at UV/normal seams) so it becomes one edge loop;
    - the fill is a constrained Delaunay triangulation of the rim in XY: no new vertices, every new corner
      takes the rim vertex's UV from the surrounding lid island and its original corner normal;
    - Tripo's corner normals are captured as plain vectors before any topology change and written back
      with normals_split_custom_set (the stored custom normals are encoded per lnor space and would be
      re-decoded differently around the edited rim).
    """
    me = obj.data
    n_loops_before = len(me.loops)
    orig = np.empty(n_loops_before * 3, dtype=np.float32)
    me.corner_normals.foreach_get("vector", orig)
    attr = me.attributes.new("um_orig_normal", "FLOAT_VECTOR", "CORNER")
    attr.data.foreach_set("vector", orig)

    bm = bmesh.new()
    bm.from_mesh(me)
    uvl = bm.loops.layers.uv.active
    nl = bm.loops.layers.float_vector["um_orig_normal"]
    z_min = float(cfg["z_min_m_prescale"])
    cx, cy = (float(c) for c in cfg["centre_xy_m_prescale"])
    radius = float(cfg["radius_m_prescale"])
    fold = detect_fold_faces(bm, uvl, z_min, int(cfg.get("small_island_max_faces", 16)))
    bm.faces.ensure_lookup_table()
    island = bm_uv_islands(bm, uvl)

    def in_disc(f):
        c = f.calc_center_median()
        return c.z >= z_min and math.hypot(c.x - cx, c.y - cy) <= radius

    region = [f for f in bm.faces if in_disc(f)]
    region_idx = {f.index for f in region}
    missing = sorted(set(fold) - region_idx)
    if missing:
        raise RuntimeError("geometry_repair disc misses detected fold faces %s" % missing)
    fold_centres = [bm.faces[i].calc_center_median() for i in sorted(fold)]
    lid_islands = {}
    for f in region:
        if f.index not in fold:
            lid_islands[island[f.index]] = lid_islands.get(island[f.index], 0) + 1
    rec = {
        "method": "delete lid-top disc containing the fold, weld rim, flat constrained-Delaunay fill (no new vertices)",
        "disc": {"centre_xy_m_prescale": [cx, cy], "radius_m_prescale": radius, "z_min_m_prescale": z_min},
        "fold_faces_detected": len(fold),
        "fold_reasons": {k: sum(1 for v in fold.values() if k in v) for k in sorted({w for v in fold.values() for w in v})},
        "fold_bbox_m_prescale": [[r(min(c[i] for c in fold_centres), 4) for i in range(3)],
                                 [r(max(c[i] for c in fold_centres), 4) for i in range(3)]],
        "faces_deleted": len(region),
        "faces_deleted_fold": len(fold),
        "faces_deleted_intact_lid": len(region) - len(fold),
        "lid_island_faces_in_disc": sorted(lid_islands.values()),
    }
    if len(lid_islands) != 1:
        raise RuntimeError("disc spans %d UV islands of the lid; expected exactly one" % len(lid_islands))

    positions = [v.co.copy() for f in region for v in f.verts]
    kd = KDTree(len(positions))
    for i, p in enumerate(positions):
        kd.insert(p, i)
    kd.balance()
    bmesh.ops.delete(bm, geom=region, context="FACES")

    def at_region(v):
        return kd.find(v.co)[2] < 1e-7

    near = [v for v in bm.verts if at_region(v)]
    n_before_weld = len(bm.verts)
    bmesh.ops.remove_doubles(bm, verts=near, dist=1e-6)
    rec["rim_vertices_merged"] = n_before_weld - len(bm.verts)
    bm.edges.ensure_lookup_table()
    hole = [e for e in bm.edges if e.is_boundary and at_region(e.verts[0]) and at_region(e.verts[1])]
    degree = {}
    for e in hole:
        for v in e.verts:
            degree.setdefault(v, []).append(e)
    if not hole or any(len(es) != 2 for es in degree.values()):
        raise RuntimeError("hole rim is not a simple edge loop (%d edges)" % len(hole))
    start = min(degree, key=lambda v: (round(v.co.x, 7), round(v.co.y, 7), round(v.co.z, 7)))
    rim, prev, cur = [start], None, start
    while True:
        e = degree[cur][0] if degree[cur][0] is not prev else degree[cur][1]
        nxt = e.other_vert(cur)
        prev = e
        if nxt is start:
            break
        rim.append(nxt)
        cur = nxt
    if len(rim) != len(degree):
        raise RuntimeError("hole rim has %d loops, expected one" % (len(degree) - len(rim) + 1))
    pts = [v.co.to_2d() for v in rim]
    n = len(pts)
    for i in range(n):
        for j in range(i + 2, n):
            if (i == 0 and j == n - 1):
                continue
            if mgeo.intersect_line_line_2d(pts[i], pts[(i + 1) % n], pts[j], pts[(j + 1) % n]):
                raise RuntimeError("hole rim self-intersects in XY (edges %d, %d)" % (i, j))
    out_v, _out_e, out_f, orig_v, _oe, _of = mgeo.delaunay_2d_cdt(pts, [], [list(range(n))], 1, 1e-9)
    if len(out_v) != n:
        raise RuntimeError("fill would add vertices (%d != %d)" % (len(out_v), n))
    to_in = [ov[0] for ov in orig_v]

    # per rim vertex: UV and corner normal taken from the surviving lid faces around it
    uv_at, n_at = {}, {}
    for v in rim:
        uvs = {(round(l[uvl].uv[0], 6), round(l[uvl].uv[1], 6)) for l in v.link_loops}
        if len(uvs) != 1:
            raise RuntimeError("rim vertex %s sits on a UV seam (%d UVs)" % (tuple(v.co), len(uvs)))
        uv_at[v] = Vector(next(iter(uvs)))
        acc = Vector((0.0, 0.0, 0.0))
        for l in v.link_loops:
            acc += Vector(l[nl])
        n_at[v] = acc.normalized()
    new_faces = []
    for tri in out_f:
        vs = [rim[to_in[i]] for i in tri]
        a, b, c = (v.co.to_2d() for v in vs)
        if (b - a).cross(c - a) < 0:
            vs.reverse()
        f = bm.faces.new(vs)
        f.smooth = True
        f.material_index = 0
        for l in f.loops:
            l[uvl].uv = uv_at[l.vert]
            l[nl] = n_at[l.vert]
        f.normal_update()
        new_faces.append(f)
    # UV orientation of the fill must match the lid island
    ring = {f for v in rim for f in v.link_faces if f not in new_faces}
    lid_sign = 1 if sum(1 for f in ring if uv_signed_area(f, uvl) >= 0) >= len(ring) / 2 else -1
    uv_flipped_fill = sum(1 for f in new_faces if uv_signed_area(f, uvl) * lid_sign <= 0)
    zs = [v.co.z for v in rim]
    rec.update({
        "rim_vertices": n,
        "fill_triangles": len(new_faces),
        "fill_triangles_facing_up": sum(1 for f in new_faces if f.normal.z > 0.9),
        "fill_uv_flipped_vs_lid_island": uv_flipped_fill,
        "fill_area_m2_prescale": r(sum(f.calc_area() for f in new_faces), 7),
        "fill_uv_area_fraction": r(sum(abs(uv_signed_area(f, uvl)) for f in new_faces), 7),
        "rim_z_range_mm_prescale": r((max(zs) - min(zs)) * 1000, 3),
    })
    if uv_flipped_fill:
        raise RuntimeError("fill has %d UV triangles flipped against the lid island" % uv_flipped_fill)
    bm.to_mesh(me)
    bm.free()
    me.update()
    # corner normals: surviving corners keep Tripo's vectors, fill corners use the rim vertex normal
    vec = np.empty(len(me.loops) * 3, dtype=np.float32)
    me.attributes["um_orig_normal"].data.foreach_get("vector", vec)
    vec = vec.reshape(-1, 3)
    vec /= np.maximum(np.linalg.norm(vec, axis=1, keepdims=True), 1e-12)
    me.normals_split_custom_set([tuple(v) for v in vec])
    me.attributes.remove(me.attributes["um_orig_normal"])
    me.update()
    got = np.empty(len(me.loops) * 3, dtype=np.float32)
    me.corner_normals.foreach_get("vector", got)
    got = got.reshape(-1, 3)
    dev = np.degrees(np.arccos(np.clip((got * vec).sum(1), -1, 1)))
    rec["corner_normals_max_deviation_deg_after_rewrite"] = r(dev.max(), 3)
    rec["triangles_after"] = triangles(obj)
    return rec


def corner_normal_stats(obj):
    """Corner normals that point into the surface (dot with the face normal < 0)."""
    me = obj.data
    cn = np.empty(len(me.loops) * 3, dtype=np.float32)
    me.corner_normals.foreach_get("vector", cn)
    cn = cn.reshape(-1, 3)
    fn = np.empty(len(me.polygons) * 3, dtype=np.float32)
    me.polygons.foreach_get("normal", fn)
    fn = fn.reshape(-1, 3)
    loop_face = np.empty(len(me.loops), dtype=np.int64)
    for p in me.polygons:
        loop_face[p.loop_start:p.loop_start + p.loop_total] = p.index
    dots = (cn * fn[loop_face]).sum(1)
    return {"has_custom_normals": bool(me.has_custom_normals),
            "corners_pointing_into_surface": int((dots < 0).sum()),
            "corner_vs_face_normal_angle_deg_p50_p99_max": [r(np.degrees(np.arccos(np.clip(np.percentile(dots, q), -1, 1))), 2)
                                                            for q in (50, 1, 0)]}


# ----------------------------------------------------------------------------- UV analysis
def raster_triangles(tris_uv, size, strict=False):
    """Coverage count per pixel centre (float UV, v up, Blender convention).
    strict=True counts only pixel centres strictly inside a triangle (shared edges are not overlaps)."""
    cov = np.zeros((size, size), dtype=np.int32)
    for t in tris_uv:
        p = t * size
        x0, y0 = np.floor(p.min(0)).astype(int)
        x1, y1 = np.ceil(p.max(0)).astype(int)
        x0, y0 = max(x0, 0), max(y0, 0)
        x1, y1 = min(x1, size), min(y1, size)
        if x1 <= x0 or y1 <= y0:
            continue
        xs, ys = np.meshgrid(np.arange(x0, x1) + 0.5, np.arange(y0, y1) + 0.5)
        (ax, ay), (bx, by), (cx, cy) = p
        d = (by - cy) * (ax - cx) + (cx - bx) * (ay - cy)
        if abs(d) < 1e-12:
            continue
        l1 = ((by - cy) * (xs - cx) + (cx - bx) * (ys - cy)) / d
        l2 = ((cy - ay) * (xs - cx) + (ax - cx) * (ys - cy)) / d
        l3 = 1 - l1 - l2
        if strict:
            eps = 1e-9
            inside = (l1 > eps) & (l2 > eps) & (l3 > eps)
        else:
            inside = (l1 >= 0) & (l2 >= 0) & (l3 >= 0)
        cov[y0:y1, x0:x1] += inside
    return cov


def island_centre_distances(label, rmax):
    """Minimal Euclidean distance between pixel centres of different islands, per island pair (<= rmax).
    Empty texels between two islands along that line ~= distance - 1."""
    h, w = label.shape
    pad = np.full((h + 2 * rmax, w + 2 * rmax), -1, dtype=np.int32)
    pad[rmax:rmax + h, rmax:rmax + w] = label
    offsets = sorted((dy * dy + dx * dx, dy, dx) for dy in range(-rmax, rmax + 1) for dx in range(0, rmax + 1)
                     if (dx > 0 or dy > 0) and dy * dy + dx * dx <= rmax * rmax)
    best = {}
    own = label >= 0
    for d2, dy, dx in offsets:
        sh = pad[rmax + dy:rmax + dy + h, rmax + dx:rmax + dx + w]
        m = own & (sh >= 0) & (sh != label)
        if not m.any():
            continue
        a, b = label[m], sh[m]
        for p in {(int(x), int(y)) for x, y in zip(np.minimum(a, b), np.maximum(a, b))}:
            best.setdefault(p, math.sqrt(d2))
    return best


def uv_raster_metrics(tuv, island, n_islands, size, rmax=8):
    """Overlaps (between and inside islands) and island spacing on a size x size raster."""
    label = np.full((size, size), -1, dtype=np.int32)
    count = np.zeros((size, size), dtype=np.int32)
    inside_overlap = 0
    for k in range(n_islands):
        t = tuv[island == k]
        m = raster_triangles(t, size) > 0
        count += m
        label[m] = k
        inside_overlap += int((raster_triangles(t, size, strict=True) >= 2).sum())
    covered = int((count >= 1).sum())
    dist = island_centre_distances(label, rmax)
    dmin = min(dist.values()) if dist else None
    return {
        "raster_size_px": size,
        "overlap_pixels_between_islands": int((count >= 2).sum()),
        "overlap_pixels_inside_islands_strict": inside_overlap,
        "raster_coverage_fraction": r(covered / size / size, 4),
        "min_island_centre_distance_px": r(dmin, 3) if dmin is not None else ">%d" % rmax,
        "island_pairs_centre_distance_lt_4px": sum(1 for d in dist.values() if d < 4),
        "island_pairs_centre_distance_lt_8px": sum(1 for d in dist.values() if d < 8),
        "mip_where_min_distance_drops_below_1_texel": (int(math.floor(math.log2(dmin))) + 1) if dmin else None,
    }


def uv_analysis(obj, size):
    me = obj.data
    uv_layers = [l.name for l in me.uv_layers]
    if not uv_layers:
        return {"uv_layers": [], "error": "no UV0"}
    uv = me.uv_layers[0].data
    me.calc_loop_triangles()
    tris = me.loop_triangles
    tuv = np.array([[uv[i].uv[:] for i in t.loops] for t in tris], dtype=np.float64)
    tpos = np.array([[me.vertices[i].co[:] for i in t.vertices] for t in tris], dtype=np.float64)
    # islands: loops sharing a vertex AND the same UV belong together
    parent = list(range(len(tris)))

    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    key_owner = {}
    for ti, t in enumerate(tris):
        for li, vi in zip(t.loops, t.vertices):
            k = (vi, round(uv[li].uv[0], 6), round(uv[li].uv[1], 6))
            if k in key_owner:
                a, b = find(ti), find(key_owner[k])
                if a != b:
                    parent[a] = b
            else:
                key_owner[k] = ti
    island = np.array([find(i) for i in range(len(tris))])
    ids = {v: n for n, v in enumerate(sorted(set(island)))}
    island = np.array([ids[v] for v in island])
    n_islands = len(ids)

    area_uv = 0.5 * ((tuv[:, 1, 0] - tuv[:, 0, 0]) * (tuv[:, 2, 1] - tuv[:, 0, 1])
                     - (tuv[:, 2, 0] - tuv[:, 0, 0]) * (tuv[:, 1, 1] - tuv[:, 0, 1]))
    e1, e2 = tpos[:, 1] - tpos[:, 0], tpos[:, 2] - tpos[:, 0]
    area_3d = 0.5 * np.linalg.norm(np.cross(e1, e2), axis=1)
    # per-island orientation: flipped triangle = sign opposite to its island's majority
    flipped = 0
    for k in range(n_islands):
        s = np.sign(area_uv[island == k])
        maj = 1 if (s >= 0).sum() >= (s < 0).sum() else -1
        flipped += int((s == -maj).sum())
    # stretch: singular values of the 3D->UV map per triangle, area-weighted
    u1 = e1 / np.maximum(np.linalg.norm(e1, axis=1, keepdims=True), 1e-12)
    nrm = np.cross(e1, e2)
    nrm /= np.maximum(np.linalg.norm(nrm, axis=1, keepdims=True), 1e-12)
    v1 = np.cross(nrm, u1)
    P = np.stack([np.stack([(e1 * u1).sum(1), (e1 * v1).sum(1)], 1),
                  np.stack([(e2 * u1).sum(1), (e2 * v1).sum(1)], 1)], 1)  # rows: edges in local 2D
    Q = np.stack([tuv[:, 1] - tuv[:, 0], tuv[:, 2] - tuv[:, 0]], 1)
    valid = (area_3d > 1e-14) & (np.abs(area_uv) > 1e-14)
    J = np.zeros((len(tris), 2, 2))
    J[valid] = np.linalg.solve(P[valid], Q[valid])  # local2D -> UV
    sv = np.linalg.svd(J, compute_uv=False)
    tex_density = np.sqrt(np.abs(area_uv).sum() / max(area_3d.sum(), 1e-12))  # UV units per metre
    smax = sv[:, 0] / tex_density
    smin = np.maximum(sv[:, 1], 1e-12) / tex_density
    aniso = sv[:, 0] / np.maximum(sv[:, 1], 1e-12)
    w = area_3d / area_3d.sum()

    def wpct(x, q):
        o = np.argsort(x)
        c = np.cumsum(w[o])
        return float(x[o][min(np.searchsorted(c, q), len(x) - 1)])

    area_ratio = (np.abs(area_uv) / area_uv.__abs__().sum()) / np.maximum(w, 1e-18)
    # rasterise per island for overlap and gutter
    label = np.full((size, size), -1, dtype=np.int32)
    count = np.zeros((size, size), dtype=np.int32)
    for k in range(n_islands):
        m = raster_triangles(tuv[island == k], size) > 0
        count += m
        label[m] = k
    overlap_px = int((count >= 2).sum())
    covered_px = int((count >= 1).sum())
    # gutter: multi-source growth; first contact of different islands after s steps => gap ~ 2s-1 px
    lab = label.copy()
    lab[count >= 2] = -2
    min_gap = None
    close_pairs = set()
    for step in range(1, 17):
        grown = lab.copy()
        cand = []
        for dy, dx in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            cand.append(np.roll(np.roll(lab, dy, 0), dx, 1))
        empty = lab == -1
        stack = np.stack(cand)
        valid_n = stack >= 0
        big = np.where(valid_n, stack, -1).max(0)
        small = np.where(valid_n, stack, 1 << 30).min(0)
        collide = empty & (big >= 0) & (small != big) & (small < (1 << 30))
        # also contact between an existing labelled pixel and a neighbour of another island
        touch = (lab >= 0) & (((big >= 0) & (big != lab)) | ((small < (1 << 30)) & (small != lab)))
        if collide.any() or touch.any():
            gap = 2 * step - 1 if collide.any() else 2 * (step - 1)
            if min_gap is None:
                min_gap = gap
            ys, xs = np.nonzero(collide | touch)
            for y, x in zip(ys[:2000], xs[:2000]):
                a, b = int(small[y, x]), int(big[y, x])
                if lab[y, x] >= 0:
                    a, b = int(lab[y, x]), (b if b != lab[y, x] else a)
                close_pairs.add((min(a, b), max(a, b), 2 * step - 1))
            if step >= 2:
                break
        grow = empty & (big >= 0)
        grown[grow] = big[grow]
        lab = grown
    pairs_lt4 = sorted({(a, b) for a, b, g in close_pairs if g < 4})
    out_of_bounds = int(((tuv < 0) | (tuv > 1)).any(axis=(1, 2)).sum())
    rasters = [uv_raster_metrics(tuv, island, n_islands, s) for s in (size, 2 * size)]
    return {
        "uv_layers": uv_layers,
        "raster_size_px": size,
        "islands": n_islands,
        "triangles_out_of_0_1": out_of_bounds,
        "uv_bounds": [r(tuv[..., 0].min()), r(tuv[..., 1].min()), r(tuv[..., 0].max()), r(tuv[..., 1].max())],
        "uv_area_used_fraction": r(np.abs(area_uv).sum(), 4),
        "raster_coverage_fraction": r(covered_px / size / size, 4),
        "overlap_pixels_between_islands": overlap_px,
        "overlap_fraction_of_covered": r(overlap_px / max(covered_px, 1), 5),
        "overlap_pixels_inside_islands_strict": rasters[0]["overlap_pixels_inside_islands_strict"],
        "flipped_uv_triangles_vs_island_majority": flipped,
        "zero_area_uv_triangles": int((np.abs(area_uv) <= 1e-14).sum()),
        "texel_density_px_per_m_at_raster": r(tex_density * size, 1),
        "stretch_area_ratio_p05_p50_p95": [r(wpct(area_ratio, q), 3) for q in (0.05, 0.5, 0.95)],
        "stretch_anisotropy_sigma_max_over_min_p50_p95_max": [r(wpct(aniso, 0.5), 3), r(wpct(aniso, 0.95), 3),
                                                               r(aniso[valid].max(), 3)],
        "stretch_sigma_max_norm_p95": r(wpct(smax, 0.95), 3),
        "stretch_sigma_min_norm_p05": r(wpct(smin, 0.05), 3),
        "min_gutter_px_estimate": min_gap,
        "island_pairs_closer_than_4px": len(pairs_lt4),
        "note": ("min_gutter_px_estimate / island_pairs_closer_than_4px: 4-neighbour growth at raster_size_px "
                 "(odd/even estimate +-1 px). raster_metrics: Euclidean distance between centres of pixels of "
                 "different islands (another metric, counts differ), plus strict in-island overlap from flipped UV "
                 "triangles; at raster_size_px and 2x."),
        "raster_metrics": rasters,
    }, tuv


def uv_layout_png(tuv, bc_pixels, size, path):
    img = bc_pixels.copy() * 0.6
    for t in tuv:
        p = t * size
        for a, b in ((0, 1), (1, 2), (2, 0)):
            n = int(max(abs(p[b] - p[a]).max(), 1)) * 2
            xs = np.clip(np.linspace(p[a][0], p[b][0], n).astype(int), 0, size - 1)
            ys = np.clip(np.linspace(p[a][1], p[b][1], n).astype(int), 0, size - 1)
            img[ys, xs, :3] = (1.0, 0.9, 0.1)
    save_png(img, size, path, "sRGB")


# ----------------------------------------------------------------------------- textures
def image_array(img):
    w, h = img.size
    a = np.empty(w * h * 4, dtype=np.float32)
    img.pixels.foreach_get(a)
    return a.reshape(h, w, 4)  # row 0 = bottom (Blender)


def dilate_into(arr, empty, iterations):
    """Edge padding: grow valid texels into empty ones (8-neighbour mean), like a bake margin."""
    arr = arr.copy()
    valid = ~empty
    for _ in range(iterations):
        acc = np.zeros_like(arr)
        cnt = np.zeros(valid.shape, dtype=np.float32)
        for dy in (-1, 0, 1):
            for dx in (-1, 0, 1):
                if dy == 0 and dx == 0:
                    continue
                v = np.roll(np.roll(valid, dy, 0), dx, 1)
                acc += np.roll(np.roll(arr, dy, 0), dx, 1) * v[..., None]
                cnt += v
        grow = (~valid) & (cnt > 0)
        if not grow.any():
            break
        arr[grow] = acc[grow] / cnt[grow][:, None]
        valid = valid | grow
    return arr, valid


def box_down(a, factor):
    if factor == 1:
        return a
    h, w, c = a.shape
    return a.reshape(h // factor, factor, w // factor, factor, c).mean((1, 3))


def srgb_to_lin(x):
    return np.where(x <= 0.04045, x / 12.92, ((x + 0.055) / 1.055) ** 2.4)


def lin_to_srgb(x):
    x = np.clip(x, 0, 1)
    return np.where(x <= 0.0031308, x * 12.92, 1.055 * x ** (1 / 2.4) - 0.055)


PNG_COLOR_CHUNKS = (b"sRGB", b"gAMA", b"cHRM", b"iCCP")


def png_chunks(path):
    data = Path(path).read_bytes()
    if data[:8] != b"\x89PNG\r\n\x1a\n":
        raise RuntimeError("not a PNG: %s" % path)
    pos, out = 8, []
    while pos < len(data):
        length = struct.unpack(">I", data[pos:pos + 4])[0]
        out.append((data[pos + 4:pos + 8], pos, pos + 12 + length))
        pos += 12 + length
    return data, out


def strip_png_color_chunks(path):
    """Drop sRGB/gAMA/cHRM/iCCP: Blender tags every 8-bit PNG as sRGB even for Non-Color data."""
    data, chunks = png_chunks(path)
    kept = [data[s:e] for t, s, e in chunks if t not in PNG_COLOR_CHUNKS]
    Path(path).write_bytes(data[:8] + b"".join(kept))
    return sorted(t.decode() for t, _s, _e in chunks if t in PNG_COLOR_CHUNKS)


def save_png(arr, size, path, colorspace):
    name = Path(path).stem
    img = bpy.data.images.new(name, size, size, alpha=False, float_buffer=False)
    img.colorspace_settings.name = colorspace
    a = np.ones((size, size, 4), dtype=np.float32)
    a[..., :arr.shape[2]] = arr[..., :min(arr.shape[2], 4)]
    a[..., 3] = 1.0
    img.pixels.foreach_set(np.clip(a, 0, 1).ravel())
    img.filepath_raw = str(path)
    img.file_format = "PNG"
    img.save()
    if colorspace != "sRGB":
        strip_png_color_chunks(path)
    return img


def gltf_images(glb):
    """Map glTF material slots -> Blender images loaded by the importer (by image name)."""
    j, _data, _bin = glb
    mat = j["materials"][0]
    tex = j["textures"]
    imgs = j["images"]

    def name(ref):
        return imgs[tex[ref["index"]]["source"]]["name"] if ref else None

    pbr = mat.get("pbrMetallicRoughness", {})
    return {
        "basecolor": name(pbr.get("baseColorTexture")),
        "metallic_roughness": name(pbr.get("metallicRoughnessTexture")),
        "normal": name(mat.get("normalTexture")),
        "occlusion": name(mat.get("occlusionTexture")),
        "factors": {"metallic": pbr.get("metallicFactor", 1.0), "roughness": pbr.get("roughnessFactor", 1.0),
                    "basecolor": pbr.get("baseColorFactor", [1, 1, 1, 1])},
    }


def find_image(gname):
    if gname is None:
        return None
    stem = Path(gname).stem
    for img in bpy.data.images:
        if img.name in (gname, stem) or Path(img.name).stem == stem:
            return img
    raise RuntimeError("image %r not found after glTF import (%s)" % (gname, [i.name for i in bpy.data.images]))


def bake_ao(obj, size, samples, distance):
    scene = bpy.context.scene
    scene.render.engine = "CYCLES"
    scene.cycles.device = "CPU"
    scene.cycles.samples = samples
    scene.world = scene.world or bpy.data.worlds.new("World")
    scene.world.light_settings.distance = distance
    img = bpy.data.images.new("AO_bake", size, size, alpha=False, float_buffer=True)
    img.colorspace_settings.name = "Non-Color"
    mat = obj.data.materials[0]
    nt = mat.node_tree
    node = nt.nodes.new("ShaderNodeTexImage")
    node.image = img
    nt.nodes.active = node
    for o in bpy.context.scene.objects:
        o.select_set(False)
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj
    scene.render.bake.margin = 8
    scene.render.bake.margin_type = "EXTEND"
    bpy.ops.object.bake(type="AO", margin=8, use_clear=True)
    arr = image_array(img)[..., 0]
    nt.nodes.remove(node)
    return arr


# ----------------------------------------------------------------------------- material / export
def build_material(name, bc, n_dx, orm):
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    nt = mat.node_tree
    nodes, links = nt.nodes, nt.links
    bsdf = next(n for n in nodes if n.type == "BSDF_PRINCIPLED")
    t_bc = nodes.new("ShaderNodeTexImage"); t_bc.image = bc
    t_orm = nodes.new("ShaderNodeTexImage"); t_orm.image = orm
    t_n = nodes.new("ShaderNodeTexImage"); t_n.image = n_dx
    sep = nodes.new("ShaderNodeSeparateColor")
    links.new(t_bc.outputs["Color"], bsdf.inputs["Base Color"])
    links.new(t_orm.outputs["Color"], sep.inputs["Color"])
    links.new(sep.outputs["Green"], bsdf.inputs["Roughness"])
    links.new(sep.outputs["Blue"], bsdf.inputs["Metallic"])
    # DirectX normal -> flip green back for Blender's OpenGL tangent space
    sepn = nodes.new("ShaderNodeSeparateColor")
    inv = nodes.new("ShaderNodeMath"); inv.operation = "SUBTRACT"; inv.inputs[0].default_value = 1.0
    comb = nodes.new("ShaderNodeCombineColor")
    nmap = nodes.new("ShaderNodeNormalMap")
    links.new(t_n.outputs["Color"], sepn.inputs["Color"])
    links.new(sepn.outputs["Red"], comb.inputs["Red"])
    links.new(sepn.outputs["Green"], inv.inputs[1])
    links.new(inv.outputs[0], comb.inputs["Green"])
    links.new(sepn.outputs["Blue"], comb.inputs["Blue"])
    links.new(comb.outputs["Color"], nmap.inputs["Color"])
    links.new(nmap.outputs["Normal"], bsdf.inputs["Normal"])
    return mat


def make_fbx_deterministic():
    from io_scene_fbx import export_fbx_bin, fbx_utils

    def stable_hash(key):
        d = hashlib.sha256(repr(key).encode("utf-8")).digest()
        return int.from_bytes(d[:8], "little") & ((1 << 63) - 1)

    saved = (export_fbx_bin.datetime, fbx_utils.__dict__.get("hash"), export_fbx_bin._gen_vid_path)
    original_vid_path = saved[2]

    def relative_vid_path(img, scene_data):
        _abs, rel = original_vid_path(img, scene_data)
        return rel, rel  # never write the absolute checkout path into the FBX

    export_fbx_bin._gen_vid_path = relative_vid_path
    fbx_utils.hash = stable_hash
    fbx_utils._keys_to_uuids.clear()
    fbx_utils._uuids_to_keys.clear()

    class FixedDateTime(datetime.datetime):
        @classmethod
        def now(cls, tz=None):
            return FIXED_TIME

    class FixedModule:
        datetime = FixedDateTime

    export_fbx_bin.datetime = FixedModule

    def restore():
        export_fbx_bin.datetime = saved[0]
        export_fbx_bin._gen_vid_path = saved[2]
        if saved[1] is None:
            fbx_utils.__dict__.pop("hash", None)
        else:
            fbx_utils.hash = saved[1]

    return restore


def patch_fbx_units(path, value):
    buf = bytearray(Path(path).read_bytes())
    start = buf.find(b"UnitScaleFactor")
    token = buf.find(b"Number", buf.find(b"double", start))
    length = struct.unpack_from("<I", buf, token - 4)[0]
    off = token + length
    assert buf[off:off + 1] == b"S"
    off += 1 + 4 + struct.unpack_from("<I", buf, off + 1)[0]
    assert buf[off:off + 1] == b"D"
    struct.pack_into("<d", buf, off + 1, value)
    Path(path).write_bytes(buf)


def fbx_kwargs(preset):
    """Blender FBX exporter arguments for UM_FBX_v1 (04 section 1.1), same set as blender/_tools/batch_export.py.
    Static prop: bake_anim off (baking is for skeletal clips only); no tangent export (UE rebuilds MikkTSpace)."""
    return dict(
        use_selection=True, object_types={"ARMATURE", "MESH"},
        apply_unit_scale=bool(preset["apply_unit_scale"]), apply_scale_options=preset["apply_scale_options"],
        bake_space_transform=False,
        axis_forward=preset["axis_forward"], axis_up=preset["axis_up"],
        use_triangles=bool(preset["use_triangles"]), mesh_smooth_type=preset["mesh_smooth_type"],
        use_mesh_edges=False, use_custom_props=False,
        add_leaf_bones=bool(preset["add_leaf_bones"]),
        primary_bone_axis=preset["primary_bone_axis"], secondary_bone_axis=preset["secondary_bone_axis"],
        bake_anim=False, path_mode=preset["path_mode"], embed_textures=False,
    )


def um_fbx_v1_conformance(preset, kwargs, obj, scene):
    """Row-by-row comparison with 04 section 1 / 1.1 (UM_FBX_v1) for this static prop."""
    rows = []

    def row(setting, standard, used):
        rows.append({"setting": setting, "standard": standard, "used": used, "conforms": standard == used})

    row("Forward / Up (04 1.1)", ["-Y", "Z"], [kwargs["axis_forward"], kwargs["axis_up"]])
    row("Apply Scalings (04 1.1)", "FBX_SCALE_UNITS", kwargs["apply_scale_options"])
    row("Apply Unit (04 1.1)", True, kwargs["apply_unit_scale"])
    row("Apply Transform (04 1.1)", False, kwargs["bake_space_transform"])
    row("Triangulate Faces (04 1.1)", True, kwargs["use_triangles"])
    row("Smoothing (04 1.1)", "FACE", kwargs["mesh_smooth_type"])
    row("Object Types (04 1.1)", ["ARMATURE", "MESH"], sorted(kwargs["object_types"]))
    row("Loose Edges / Custom Properties (04 1.1)", [False, False], [kwargs["use_mesh_edges"], kwargs["use_custom_props"]])
    row("Leaf bones / bone axes (04 1.1, preset)", [False, "Y", "X"],
        [kwargs["add_leaf_bones"], kwargs["primary_bone_axis"], kwargs["secondary_bone_axis"]])
    row("Bake Animation (04 1.1: skeletal clips only)", False, kwargs["bake_anim"])
    row("Path Mode, textures not embedded (04 1.1)", ["AUTO", False], [kwargs["path_mode"], kwargs["embed_textures"]])
    row("Export space: +Z rotation deg / data scale / UnitScaleFactor patch (preset)", [90.0, 100.0, 1.0],
        [float(preset["export_space_rotation_z_degrees"]), float(preset["temporary_data_scale"]),
         float(preset["patch_fbx_unit_scale_to"])])
    row("Scene units: metric, unit scale 1.0 (04 1)", ["METRIC", 1.0],
        [scene.unit_settings.system, r(scene.unit_settings.scale_length)])
    row("Transforms applied: object matrix identity (04 1)", True,
        all(abs(a - b) < 1e-9 for ra, rb in zip(obj.matrix_world, Matrix.Identity(4)) for a, b in zip(ra, rb)))
    lo, hi = world_bounds([obj])
    row("Pivot: base centre, min Z = 0 (04 1, decor: centre of base)", True,
        abs(lo.z) < 1e-6 and abs(lo.x + hi.x) < 1e-6 and abs(lo.y + hi.y) < 1e-6)
    return rows


def front_direction(obj, z_frac=0.5):
    """Horizontal direction of the most protruding vertex in a band at z_frac of the height
    (barrel: the bung = asset front). Same method as check_static_prop_fbx.py."""
    pts = [obj.matrix_world @ v.co for v in obj.data.vertices]
    lo, hi = world_bounds([obj])
    cx, cy = (lo.x + hi.x) / 2, (lo.y + hi.y) / 2
    z0 = lo.z + (hi.z - lo.z) * z_frac
    band = [p for p in pts if abs(p.z - z0) < (hi.z - lo.z) * 0.08]
    far = max(band, key=lambda p: math.hypot(p.x - cx, p.y - cy))
    return r(math.degrees(math.atan2(far.y - cy, far.x - cx)), 1)


def export_fbx(obj, path, preset):
    """UM_FBX_v1 on a temporary copy: rotate +Z, x100, export, patch UnitScaleFactor."""
    final_name = obj.name
    obj.name = final_name + "__src"
    tmp = obj.copy()
    tmp.data = obj.data.copy()
    tmp.name = final_name
    if tmp.name != final_name:
        raise RuntimeError("export object name collision: %s" % tmp.name)
    bpy.context.scene.collection.objects.link(tmp)
    rot = Matrix.Rotation(math.radians(float(preset["export_space_rotation_z_degrees"])), 4, "Z")
    scale = float(preset["temporary_data_scale"])
    tmp.data.transform(Matrix.Scale(scale, 4) @ rot)
    tmp.location = (rot @ tmp.location) * scale
    for o in bpy.context.scene.objects:
        o.select_set(False)
    tmp.select_set(True)
    bpy.context.view_layer.objects.active = tmp
    restore = make_fbx_deterministic()
    try:
        bpy.ops.export_scene.fbx(filepath=str(path), **fbx_kwargs(preset))
    finally:
        restore()
    patch_fbx_units(path, float(preset["patch_fbx_unit_scale_to"]))
    data = tmp.data
    bpy.data.objects.remove(tmp)
    bpy.data.meshes.remove(data)
    obj.name = final_name


# ----------------------------------------------------------------------------- previews
def render_previews(obj, out, prefix):
    scene = bpy.context.scene
    try:
        scene.render.engine = "BLENDER_EEVEE_NEXT"
    except TypeError:
        scene.render.engine = "BLENDER_EEVEE"
    scene.render.resolution_x = 900
    scene.render.resolution_y = 900
    scene.render.film_transparent = False
    scene.view_settings.view_transform = "Standard"
    world = scene.world or bpy.data.worlds.new("World")
    scene.world = world
    world.use_nodes = True
    bg = world.node_tree.nodes.get("Background")
    bg.inputs["Color"].default_value = (0.22, 0.22, 0.24, 1)
    bg.inputs["Strength"].default_value = 0.6
    sun_data = bpy.data.lights.new("Key", "SUN"); sun_data.energy = 3.5
    sun = bpy.data.objects.new("Key", sun_data); scene.collection.objects.link(sun)
    sun.rotation_euler = (math.radians(50), 0, math.radians(35))
    fill_data = bpy.data.lights.new("Fill", "SUN"); fill_data.energy = 1.0
    fill = bpy.data.objects.new("Fill", fill_data); scene.collection.objects.link(fill)
    fill.rotation_euler = (math.radians(60), 0, math.radians(-140))
    cam_data = bpy.data.cameras.new("Cam"); cam_data.type = "ORTHO"
    cam = bpy.data.objects.new("Cam", cam_data); scene.collection.objects.link(cam)
    scene.camera = cam
    lo, hi = world_bounds([obj])
    centre = (lo + hi) / 2
    size = max(hi - lo)
    cam_data.ortho_scale = size * 1.35
    shots = {
        "front": (0.0, 90.0),        # camera on -Y looking +Y (bung side)
        "side": (90.0, 90.0),        # camera on +X
        "game-3q-55deg": (35.0, 35.0),  # elevation 55 deg from vertical axis ~ board camera
        "top": (0.0, 0.1),
    }
    files = {}
    for key, (yaw, polar) in shots.items():
        th, ph = math.radians(polar), math.radians(yaw)
        d = Vector((math.sin(th) * math.sin(ph), -math.sin(th) * math.cos(ph), math.cos(th)))
        cam.location = centre + d * size * 4
        cam.rotation_euler = (-d).to_track_quat("-Z", "Y").to_euler()
        path = out / ("%s_%s.png" % (prefix, key))
        scene.render.filepath = str(path)
        bpy.ops.render.render(write_still=True)
        files[key] = path
    return files


# ----------------------------------------------------------------------------- main
def main():
    P = load_params()
    out = P["out_dir"]
    for sub in ("work", "export", "reports", "preview"):
        (out / sub).mkdir(parents=True, exist_ok=True)
    preset = json.loads(P["fbx_preset"].read_text(encoding="utf-8"))
    src_sha_before = sha256(P["source_glb"])
    glb = glb_json(P["source_glb"])
    report = {
        "schema": "unmatched.tripo-pipeline.static-prop-candidate/1",
        "status": "measured",
        "claims": {"art_accepted": False, "game_ready": False, "budgets_declared": False},
        "blender_version": bpy.app.version_string,
        "script_sha256_lf": text_sha256_lf(Path(__file__)),
        "params": {k: (rel(v, P) if isinstance(v, Path) else v) for k, v in P.items() if k != "repo_root"},
        "source": {"path": rel(P["source_glb"], P), "sha256": src_sha_before, "bytes": P["source_glb"].stat().st_size,
                   "gltf_generator": glb[0].get("asset", {}).get("generator")},
    }

    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.ops.import_scene.gltf(filepath=str(P["source_glb"]))
    meshes = mesh_objects()
    lo, hi = world_bounds(meshes)
    report["import"] = {
        "mesh_objects": len(meshes),
        "triangles": sum(triangles(o) for o in meshes),
        "materials": sorted({m.name for o in meshes for m in o.data.materials if m}),
        "images": [{"name": i.name, "size": list(i.size), "colorspace": i.colorspace_settings.name}
                   for i in bpy.data.images if i.size[0]],
        "bounds_min_m": [r(v) for v in lo], "bounds_max_m": [r(v) for v in hi],
        "dimensions_m": [r(v) for v in (hi - lo)],
    }
    # single object, transforms applied, no parents/empties
    for o in list(bpy.context.scene.objects):
        if o.type != "MESH":
            bpy.data.objects.remove(o)
    obj = meshes[0]
    if len(meshes) > 1:
        with bpy.context.temp_override(active_object=obj, selected_editable_objects=meshes):
            bpy.ops.object.join()
    obj.parent = None
    obj.data.transform(obj.matrix_world)
    obj.matrix_world = Matrix.Identity(4)
    obj.name = P["asset_name"]
    obj.data.name = P["asset_name"]

    geo_before, flipped = geometry_stats(obj)
    normals_before = corner_normal_stats(obj)
    removed = clean_mesh(obj)
    repair = None
    if P.get("geometry_repair"):
        repair = repair_region(obj, P["geometry_repair"])
    geo_mid, flipped = geometry_stats(obj)
    # reverse faces flagged by the outward recalculation only if that really reduces inconsistency
    fixed = 0
    winding_note = "no inconsistent faces"
    if flipped:
        backup = obj.data.copy()
        fixed = fix_winding(obj, flipped)
        geo_try, _ = geometry_stats(obj)
        if geo_try["faces_with_inconsistent_winding"] >= geo_mid["faces_with_inconsistent_winding"]:
            old_mesh = obj.data
            obj.data = backup
            bpy.data.meshes.remove(old_mesh)
            obj.data.name = P["asset_name"]
            winding_note = ("%d face(s) flagged next to non-manifold edges; reversing did not reduce the count, "
                            "kept as delivered by Tripo" % len(flipped))
            fixed = 0
        else:
            bpy.data.meshes.remove(backup)
            winding_note = "reversed %d face(s)" % fixed
    geo_after, flipped_after = geometry_stats(obj)
    me = obj.data
    flagged = [[r(c, 4) for c in me.polygons[i].center] for i in flipped_after[:10]]
    bm = bmesh.new(); bm.from_mesh(me)
    bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=1e-6)
    open_edges = [[r(c, 4) for c in (e.verts[0].co + e.verts[1].co) / 2] for e in bm.edges
                  if e.is_boundary or (not e.is_manifold)][:10]
    bm.free()
    report["geometry"] = {"before_cleanup": geo_before, "removed": removed, "repair": repair,
                          "winding_faces_reversed": fixed,
                          "winding_note": winding_note, "after_cleanup": geo_after,
                          "flagged_face_centres_m_prescale": flagged,
                          "open_or_non_manifold_edge_midpoints_m_prescale": open_edges,
                          "corner_normals_before": normals_before,
                          "corner_normals_after": corner_normal_stats(obj)}
    closed = (geo_after["welded_boundary_edges"] == 0 and geo_after["welded_non_manifold_edges"] == 0
              and geo_after["faces_with_inconsistent_winding"] == 0)
    report["geometry"]["closed_manifold_consistent_after"] = closed

    # orientation: glTF +Y up already mapped to Blender +Z by the importer; verify tallest axis is Z
    lo, hi = world_bounds([obj])
    dims = hi - lo
    report["orientation"] = {"dimensions_before_scale_m": [r(v) for v in dims],
                             "z_is_tallest_axis": bool(dims.z >= max(dims.x, dims.y))}
    scale = float(P["target_height_m"]) / dims.z
    centre = Vector(((lo.x + hi.x) / 2, (lo.y + hi.y) / 2, lo.z))
    obj.data.transform(Matrix.Scale(scale, 4) @ Matrix.Translation(-centre))
    obj.data.update()
    lo, hi = world_bounds([obj])
    report["scale_pivot"] = {
        "uniform_scale_applied": r(scale),
        "target_height_m_proposed": P["target_height_m"],
        "dimensions_m": [r(v) for v in (hi - lo)],
        "bounds_min_m": [r(v) for v in lo], "bounds_max_m": [r(v) for v in hi],
        "pivot": "object origin = (0,0,0) = centre of bounding box footprint at base (min Z)",
        "diameter_to_height_ratio": r(max(hi.x - lo.x, hi.y - lo.y) / (hi.z - lo.z), 4),
    }

    # textures
    names = gltf_images(glb)
    size = int(P["texture_size"])
    bc_img = find_image(names["basecolor"])
    mr_img = find_image(names["metallic_roughness"])
    n_img = find_image(names["normal"])
    src_size = bc_img.size[0]
    factor = src_size // size
    if src_size % size or any(i.size[0] != src_size for i in (mr_img, n_img)):
        raise RuntimeError("texture sizes not an integer multiple of target: %s" % src_size)
    # pixels come as stored (byte images: encoded values), row 0 = bottom
    bc = image_array(bc_img)[..., :3]
    bc_lin = srgb_to_lin(bc) if bc_img.colorspace_settings.name == "sRGB" else bc
    bc_out = lin_to_srgb(box_down(bc_lin, factor))
    n_raw = image_array(n_img)[..., :3]
    # Tripo leaves the normal map background near-black with no edge padding; black decodes to
    # (-1,-1,-1) and would bleed into island borders through downscaling/mips. Pad islands outward
    # at source resolution, then fill the rest with a flat normal.
    # invalid = not a unit tangent-space normal pointing out of the surface (encoded blue < 0.5 or length off)
    n_len = np.linalg.norm(n_raw * 2 - 1, axis=2)
    n_bg = (n_raw[..., 2] < 0.5) | (n_len < 0.7) | (n_len > 1.3)
    nrm = n_raw * 2 - 1
    pad_px = int(P.get("normal_padding_px_source", 32))
    nrm, filled = dilate_into(nrm, n_bg, pad_px)
    nrm[~filled] = (0.0, 0.0, 1.0)
    nrm = box_down(nrm, factor)
    normal_padding = {"background_fraction_source": r(n_bg.mean(), 4), "dilated_px_at_source": pad_px,
                      "flat_filled_fraction_source": r((~filled).mean(), 4)}
    nrm /= np.maximum(np.linalg.norm(nrm, axis=2, keepdims=True), 1e-6)
    n_dx = nrm.copy()
    n_dx[..., 1] *= -1  # OpenGL (glTF) -> DirectX (UE)
    n_out = n_dx * 0.5 + 0.5
    mr = box_down(image_array(mr_img)[..., :3], factor)
    tex_dir = out / "export"
    pre = P["texture_prefix"]
    bc_path, n_path, orm_path = (tex_dir / ("%s_%s.png" % (pre, s)) for s in ("BC", "N", "ORM"))
    t_bc = save_png(bc_out, size, bc_path, "sRGB")
    t_n = save_png(n_out, size, n_path, "Non-Color")
    orm = np.ones((size, size, 3), dtype=np.float32)
    orm[..., 1] = mr[..., 1]
    orm[..., 2] = mr[..., 2]
    t_orm = save_png(orm, size, orm_path, "Non-Color")
    # material: exactly one slot
    obj.data.materials.clear()
    mat = build_material(P["material_name"], t_bc, t_n, t_orm)
    obj.data.materials.append(mat)
    ao_stats = None
    if P.get("bake_ao"):
        ao = bake_ao(obj, size, int(P.get("ao_samples", 64)), float(P.get("ao_distance_m", 0.05)))
        me = obj.data
        me.calc_loop_triangles()
        uvl = me.uv_layers[0].data
        cover = raster_triangles(np.array([[uvl[i].uv[:] for i in t.loops] for t in me.loop_triangles]), size) > 0
        # texels outside every island (and beyond the 8 px bake margin) stay neutral 1.0
        ao_full = ao.copy()
        orm[..., 0] = np.where(cover | (ao_full > 0), ao_full, 1.0)
        t_orm = save_png(orm, size, orm_path, "Non-Color")
        a = ao[cover]
        ao_stats = {"measured_on": "texels covered by UV islands", "min": r(a.min(), 3), "p05": r(np.percentile(a, 5), 3),
                    "p50": r(np.percentile(a, 50), 3), "mean": r(a.mean(), 3),
                    "texels_lt_0.05": int((a < 0.05).sum()), "texels_lt_0.2": int((a < 0.2).sum()),
                    "samples": int(P.get("ao_samples", 64)), "distance_m": float(P.get("ao_distance_m", 0.05))}
    for img in (t_bc, t_n, t_orm):
        img.reload()

    def png_tags(path):
        return sorted(t.decode() for t, _s, _e in png_chunks(path)[1] if t in PNG_COLOR_CHUNKS)

    import_note = "Linear is an import setting (UE: sRGB off); no sRGB/gAMA/cHRM/iCCP chunk in the file"
    report["textures"] = {
        "source_images": names,
        "source_size_px": src_size, "target_size_px": size, "downscale": "box %dx%d (BC in linear light)" % (factor, factor),
        "outputs": {
            "BC": {"path": bc_path.name, "colorspace": "sRGB", "png_color_chunks": png_tags(bc_path),
                   "sha256": sha256(bc_path)},
            "N": {"path": n_path.name, "colorspace": "Linear (Non-Color)", "convention": "DirectX (G flipped from glTF OpenGL)",
                  "png_color_chunks": png_tags(n_path), "note": import_note, "sha256": sha256(n_path)},
            "ORM": {"path": orm_path.name, "colorspace": "Linear (Non-Color)",
                    "channels": {"R": "AO baked in Blender Cycles" if ao_stats else "1.0 (no AO)",
                                 "G": "roughness from glTF metallicRoughness.G", "B": "metallic from glTF metallicRoughness.B"},
                    "png_color_chunks": png_tags(orm_path), "note": import_note, "sha256": sha256(orm_path)},
        },
        "ao_bake": ao_stats,
        "normal_padding": normal_padding,
        "channel_stats": {
            "roughness_mean": r(orm[..., 1].mean(), 3), "metallic_mean": r(orm[..., 2].mean(), 3),
            "metallic_fraction_gt_0.5": r((orm[..., 2] > 0.5).mean(), 4),
            "normal_mean_rgb_dx": [r(v, 3) for v in n_out.reshape(-1, 3).mean(0)],
        },
        "teamcolor": "not applicable: decor L3 is not team-owned (04 3.7); M_DioramaMaster TeamColor left at neutral in UE",
    }

    uv, tuv = uv_analysis(obj, size)
    report["uv0"] = uv
    uv_layout_png(tuv, bc_out, size, out / "preview" / ("%s_uv0_layout.png" % P["asset_name"]))
    report["material_slots"] = len(obj.data.materials)
    report["material_names"] = [m.name for m in obj.data.materials]

    # smooth shading from Tripo's stored normals: keep as imported (custom normals preserved)
    blend = out / "work" / ("%s.blend" % P["asset_name"])
    bpy.context.preferences.filepaths.save_version = 0
    bpy.ops.wm.save_as_mainfile(filepath=str(blend), compress=False, copy=True)

    fbx = out / "export" / ("%s.fbx" % P["asset_name"])
    kwargs = fbx_kwargs(preset)
    conformance = um_fbx_v1_conformance(preset, kwargs, obj, bpy.context.scene)
    front_deg = front_direction(obj)
    conformance.append({"setting": "Front (bung) along -Y in .blend (04 1: face -Y -> +X in UE)", "standard": -90.0,
                        "used": front_deg, "conforms": abs(front_deg + 90.0) <= 15.0})
    export_fbx(obj, fbx, preset)
    report["export"] = {
        "fbx": fbx.name, "sha256": sha256(fbx), "bytes": fbx.stat().st_size,
        "preset": P["fbx_preset"].name,
        "settings": {k: preset[k] for k in ("axis_forward", "axis_up", "export_space_rotation_z_degrees",
                                            "temporary_data_scale", "patch_fbx_unit_scale_to", "apply_scale_options",
                                            "use_triangles", "mesh_smooth_type", "path_mode")},
        "exporter_kwargs": {k: (sorted(v) if isinstance(v, set) else v) for k, v in sorted(kwargs.items())},
        "textures_embedded": False,
        "texture_paths": "relative to the FBX (absolute checkout path is never written)",
        "um_fbx_v1_conformance": conformance,
        "um_fbx_v1_conforms": all(c["conforms"] for c in conformance),
        "front_direction_deg_in_blend_ccw_from_plus_x": front_deg,
    }

    previews = render_previews(obj, out / "preview", P["asset_name"])
    report["previews"] = {k: v.name for k, v in previews.items()}

    # round trip in an empty scene
    expected_tris = triangles(obj)
    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.ops.import_scene.fbx(filepath=str(fbx))
    rt = mesh_objects()
    lo2, hi2 = world_bounds(rt)
    arm = [o for o in bpy.context.scene.objects if o.type == "ARMATURE"]
    rt_dims = hi2 - lo2
    rt_obj = rt[0] if rt else None
    report["roundtrip"] = {
        "mesh_objects": len(rt), "object_names": [o.name for o in rt],
        "triangles": sum(triangles(o) for o in rt), "expected_triangles": expected_tris,
        "material_slots": len(rt_obj.data.materials) if rt_obj else None,
        "uv_layers": len(rt_obj.data.uv_layers) if rt_obj else None,
        "armatures": len(arm),
        "dimensions_blender_m": [r(v) for v in rt_dims],
        "bounds_min_blender_m": [r(v) for v in lo2],
        "object_scale": [r(v) for v in rt_obj.scale] if rt_obj else None,
        "note": "Blender reads UnitScaleFactor 1.0 as cm and scales x0.01, so metres here = UE uu/100",
    }
    rt_uu = [r(v * 100, 3) for v in rt_dims]
    exp_m = report["scale_pivot"]["dimensions_m"]
    report["roundtrip"]["expected_ue_dimensions_uu_at_import_scale_1"] = [r(exp_m[1] * 100, 3), r(exp_m[0] * 100, 3),
                                                                          r(exp_m[2] * 100, 3)]
    report["roundtrip"]["dimensions_uu"] = rt_uu
    checks = {
        "single_mesh": len(rt) == 1,
        "triangles_preserved": report["roundtrip"]["triangles"] == expected_tris,
        "one_material_slot": report["roundtrip"]["material_slots"] == 1,
        "uv0_present": (report["roundtrip"]["uv_layers"] or 0) >= 1,
        "no_armature": not arm,
        "height_matches_target_1pct": abs(rt_dims.z - P["target_height_m"]) / P["target_height_m"] < 0.01,
        "base_at_zero": abs(lo2.z) < 1e-4,
        "centred_xy": abs((lo2.x + hi2.x) / 2) < 1e-4 and abs((lo2.y + hi2.y) / 2) < 1e-4,
        "source_unchanged": sha256(P["source_glb"]) == src_sha_before,
        "um_fbx_v1_conforms": report["export"]["um_fbx_v1_conforms"],
    }
    if P.get("require_closed_manifold", True):
        checks["closed_manifold_consistent_winding"] = report["geometry"]["closed_manifold_consistent_after"]
    report["checks"] = checks
    report["checks_passed"] = all(checks.values())
    (out / "reports" / "candidate-report.json").write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n",
                                                           encoding="utf-8")
    print("CANDIDATE_REPORT", json.dumps(checks))
    if not report["checks_passed"]:
        raise SystemExit(1)


main()
