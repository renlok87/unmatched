"""Measurements of the build stage (read only: nothing here changes a mesh).

Moved from blender/build_candidate.py (0.4.0) and the per-hero builders of 2026-09-28; where the copies
differed the superset is kept (the extra keys only add report fields)."""

import math
import re
from collections import Counter, defaultdict

import bmesh
import numpy as np
from mathutils import Vector, geometry
from mathutils.bvhtree import BVHTree

from .core import DEGENERATE_AREA_CM2, r, rv


def cell_rects(cells, size):
    rects = {}
    for name, cell in cells.items():
        rects[name] = ((cell["x"] + cell["inset"]) / size, (cell["x"] + cell["cell"] - cell["inset"]) / size,
                       1 - (cell["y_top"] + cell["cell"] - cell["inset"]) / size, 1 - (cell["y_top"] + cell["inset"]) / size)
    return rects


def polygons_by_part(mesh, rects):
    """Part of every polygon = the atlas cell that contains all its UVs (art004 method)."""
    uv = mesh.uv_layers[0].data
    out = defaultdict(list)
    unassigned = 0
    for poly in mesh.polygons:
        coords = [uv[li].uv for li in poly.loop_indices]
        hit = None
        for name, (u0, u1, v0, v1) in sorted(rects.items()):
            if all(u0 - 1e-6 <= c.x <= u1 + 1e-6 and v0 - 1e-6 <= c.y <= v1 + 1e-6 for c in coords):
                hit = name
                break
        if hit is None:
            unassigned += 1
        else:
            out[hit].append(poly.index)
    return dict(out), unassigned


def world_bounds(objects):
    pts = []
    for obj in objects:
        mw = obj.matrix_world
        pts.extend(mw @ v.co for v in obj.data.vertices)
    lo = [min(p[i] for p in pts) for i in range(3)]
    hi = [max(p[i] for p in pts) for i in range(3)]
    return lo, hi


def orientation_scores(labelled):
    """labelled: list of (object, {part: [poly indices]}). Ray-escape score per part."""
    verts, polys = [], []
    for obj, _parts in labelled:
        mw = obj.matrix_world
        base = len(verts)
        verts.extend(mw @ v.co for v in obj.data.vertices)
        polys.extend([base + i for i in p.vertices] for p in obj.data.polygons)
    lo = [min(v[i] for v in verts) for i in range(3)]
    hi = [max(v[i] for v in verts) for i in range(3)]
    height = hi[2] - lo[2]
    eps, dist = 1e-4 * height, 2.0 * height
    bvh = BVHTree.FromPolygons(verts, polys, all_triangles=False, epsilon=0.0)
    scores = {}
    for obj, parts in labelled:
        mw = obj.matrix_world
        rot = mw.to_3x3()
        for part, indices in parts.items():
            out = inw = total = 0.0
            for index in indices:
                poly = obj.data.polygons[index]
                centre = mw @ poly.center
                normal = (rot @ poly.normal).normalized()
                area = poly.area
                total += area
                plus = bvh.ray_cast(centre + normal * eps, normal, dist)[0] is not None
                minus = bvh.ray_cast(centre - normal * eps, -normal, dist)[0] is not None
                if not plus and minus:
                    out += area
                elif plus and not minus:
                    inw += area
            scores[part] = {"polygons": len(indices), "outward_area_fraction": r(out / total, 4) if total else 0.0,
                            "inward_area_fraction": r(inw / total, 4) if total else 0.0,
                            "score": r((out - inw) / (out + inw), 4) if out + inw else None}
    return scores


def raster_counts(tris_px, x0, y0, width):
    counts = np.zeros((width, width), dtype=np.uint16)
    for a, b, c in tris_px:
        d = (b[1] - c[1]) * (a[0] - c[0]) + (c[0] - b[0]) * (a[1] - c[1])
        if abs(d) < 1e-12:
            continue
        minx = max(int(math.floor(min(a[0], b[0], c[0]))), x0)
        maxx = min(int(math.ceil(max(a[0], b[0], c[0]))), x0 + width - 1)
        miny = max(int(math.floor(min(a[1], b[1], c[1]))), y0)
        maxy = min(int(math.ceil(max(a[1], b[1], c[1]))), y0 + width - 1)
        if maxx < minx or maxy < miny:
            continue
        gx, gy = np.meshgrid(np.arange(minx, maxx + 1) + 0.5, np.arange(miny, maxy + 1) + 0.5)
        l1 = ((b[1] - c[1]) * (gx - c[0]) + (c[0] - b[0]) * (gy - c[1])) / d
        l2 = ((c[1] - a[1]) * (gx - c[0]) + (a[0] - c[0]) * (gy - c[1])) / d
        l3 = 1.0 - l1 - l2
        inside = (l1 > 1e-7) & (l2 > 1e-7) & (l3 > 1e-7)
        counts[miny - y0:maxy - y0 + 1, minx - x0:maxx - x0 + 1] += inside.astype(np.uint16)
    return counts


def uv_statistics(labelled, cells, size, world_scale_cm):
    """Per part: UV0 containment in the cell, texel density, raster overlap at atlas resolution.
    A label "weapon:<part>" uses the cell of <part>."""
    out = {}
    for obj, parts in labelled:
        mesh = obj.data
        mesh.calc_loop_triangles()
        uv = mesh.uv_layers[0].data
        mw = obj.matrix_world
        tris_by_poly = defaultdict(list)
        for tri in mesh.loop_triangles:
            tris_by_poly[tri.polygon_index].append(tri.loops)
        for part, indices in parts.items():
            cell = cells[part.split(":")[-1]]
            x0, y0, width = cell["x"], cell["y_top"], cell["cell"]
            inner = (x0 + cell["inset"], y0 + cell["inset"], x0 + width - cell["inset"], y0 + width - cell["inset"])
            tris_px, uv_area, world_area, outside = [], 0.0, 0.0, 0
            for index in indices:
                poly = mesh.polygons[index]
                world_area += poly.area * (mw.to_3x3().determinant() ** (2.0 / 3.0)) * world_scale_cm ** 2
                for loops in tris_by_poly[index]:
                    pts = []
                    for li in loops:
                        u, v = uv[li].uv
                        px, py = u * size, (1.0 - v) * size
                        if not (inner[0] - 1e-3 <= px <= inner[2] + 1e-3 and inner[1] - 1e-3 <= py <= inner[3] + 1e-3):
                            outside += 1
                        pts.append((px, py))
                    tris_px.append(pts)
                    (ax, ay), (bx, by), (cx, cy) = pts
                    uv_area += abs((bx - ax) * (cy - ay) - (cx - ax) * (by - ay)) / 2.0
            counts = raster_counts(tris_px, x0, y0, width)
            covered = int((counts >= 1).sum())
            overlapped = int((counts >= 2).sum())
            out[part] = {"triangles": len(tris_px), "loops_outside_cell_inner_rect": outside,
                         "uv_area_px2": r(uv_area, 1), "world_area_cm2": r(world_area, 3),
                         "texel_density_px_per_cm": r(math.sqrt(uv_area / world_area), 3) if world_area else None,
                         "raster_covered_px": covered, "raster_overlap_px": overlapped,
                         "overlap_ratio": r(overlapped / covered, 5) if covered else 0.0, "cell_px": width}
    return out


def weight_summary(obj, bone_names):
    groups = {g.index: g.name for g in obj.vertex_groups}
    bone_idx = {i for i, n in groups.items() if n in bone_names}
    max_inf, unweighted, used, not_normalised = 0, 0, Counter(), 0
    share = defaultdict(float)
    for v in obj.data.vertices:
        ws = [(groups[g.group], g.weight) for g in v.groups if g.group in bone_idx and g.weight > 0]
        max_inf = max(max_inf, len(ws))
        if not ws:
            unweighted += 1
            continue
        total = sum(w for _n, w in ws)
        if abs(total - 1.0) > 1e-3:
            not_normalised += 1
        for name, w in ws:
            used[name] += 1
            share[name] += w / total
    n = max(len(obj.data.vertices), 1)
    return {"vertices": len(obj.data.vertices), "max_influences": max_inf, "unweighted_vertices": unweighted,
            "not_normalised_vertices": not_normalised, "bones_used": dict(sorted(used.items())),
            "weight_share": {k: r(v / n, 4) for k, v in sorted(share.items())}}


def mesh_summary(obj):
    mesh = obj.data
    mesh.calc_loop_triangles()
    scale2 = (obj.matrix_world.to_3x3().determinant() ** (2.0 / 3.0)) * 1e4  # m2 -> cm2
    degenerate = sum(1 for t in mesh.loop_triangles if t.area * scale2 < DEGENERATE_AREA_CM2)
    uv_ok = True
    if mesh.uv_layers:
        arr = np.empty(len(mesh.loops) * 2, dtype=np.float32)
        mesh.uv_layers[0].data.foreach_get("uv", arr)
        uv_ok = bool(arr.size == 0 or (arr.min() >= -1e-6 and arr.max() <= 1 + 1e-6))
    return {"vertices": len(mesh.vertices), "polygons": len(mesh.polygons), "triangles": len(mesh.loop_triangles),
            "near_degenerate_triangles": degenerate, "near_degenerate_area_cm2_below": DEGENERATE_AREA_CM2,
            "uv_layers": [u.name for u in mesh.uv_layers], "uv0_in_unit_square": uv_ok,
            "color_attributes": sorted(a.name for a in mesh.color_attributes),
            "material_slots": [re.sub(r"\.\d{3}$", "", s.material.name) if s.material else None
                               for s in obj.material_slots],
            "has_custom_normals": bool(mesh.has_custom_normals)}


def facing(obj, indices):
    """Area-weighted mean normal of the polygons `indices` (world)."""
    mw = obj.matrix_world
    rot = mw.to_3x3()
    acc = Vector((0, 0, 0))
    for i in indices:
        p = obj.data.polygons[i]
        acc += (rot @ p.normal).normalized() * p.area
    total = sum(obj.data.polygons[i].area for i in indices)
    return [r(c / total, 4) for c in acc] if total else None


def centroid(obj, indices=None):
    """Mean of the world vertices of `obj` (or of the vertices of the polygons `indices`)."""
    mw = obj.matrix_world
    if indices is None:
        pts = [mw @ v.co for v in obj.data.vertices]
    else:
        vids = sorted({v for i in indices for v in obj.data.polygons[i].vertices})
        pts = [mw @ obj.data.vertices[v].co for v in vids]
    return [r(sum(p[a] for p in pts) / len(pts), 5) for a in range(3)]


def part_points(obj, indices):
    """Vertex positions (object space) of the polygons `indices`, each vertex once, index order."""
    return [obj.data.vertices[v].co for v in sorted({v for i in indices for v in obj.data.polygons[i].vertices})]


def along(vector, axis_vector):
    """Signed component of `vector` along a unit axis, and the largest horizontal cross component."""
    v = Vector(vector)
    a = Vector(axis_vector)
    side = Vector((-a.y, a.x, 0.0))
    return r(v.dot(a), 4), r(abs(v.dot(side)), 4)


def ue_predicted(bounds_cm):
    """Export-frame bounds mapped onto UE as measured by ART-001 (UE y = -Blender y)."""
    lo, hi = bounds_cm["min"], bounds_cm["max"]
    return {"min": [lo[0], r(-hi[1], 3), lo[2]], "max": [hi[0], r(-lo[1], 3), hi[2]]}


def ue_from_blender_m(p):
    """Authored Blender metres -> UE component uu under UM_FBX_v1 (measured on the Medusa candidate:
    ue(x, y) = (-y, -x) of the authored frame, z kept)."""
    return [r(-p[1] * 100, 3), r(-p[0] * 100, 3), r(p[2] * 100, 3)]


def ue_bone_local_from_blender_uu(p):
    """Blender bone-local offset (uu) -> UE bone space. UM_FBX_v1 keeps the bone axes (primary Y, secondary X:
    no bone correction), the export rotation turns the rest pose rigidly, and the UE FBX importer mirrors Y
    (right- to left-handed) for every node, i.e. conjugates each local transform by diag(1, -1, 1): a bone-local
    offset p becomes (p.x, -p.y, p.z). Consistent with the live Medusa measurement (UE (0, 0, 4) on the vertical
    head bone lands 4 uu in front, RIG-CONTRACT §7); the Y sign along a bone is a prediction until measured."""
    return [r(p[0], 3) + 0.0, r(-p[1], 3) + 0.0, r(p[2], 3) + 0.0]  # + 0.0: no "-0.0" in reports


def axis_name(vector):
    x, y = round(vector[0]), round(vector[1])
    return {(1, 0): "+X", (-1, 0): "-X", (0, 1): "+Y", (0, -1): "-Y"}.get((x, y), "?")


AXIS_VECTORS = {"+X": (1.0, 0.0, 0.0), "-X": (-1.0, 0.0, 0.0), "+Y": (0.0, 1.0, 0.0), "-Y": (0.0, -1.0, 0.0)}


def inconsistent_winding_edges(mesh, polys=None):
    """Manifold edges whose two faces traverse them in the same direction (inconsistent winding)."""
    allowed = None if polys is None else set(polys)
    seen = defaultdict(list)
    for p in mesh.polygons:
        if allowed is not None and p.index not in allowed:
            continue
        vs = list(p.vertices)
        for i in range(len(vs)):
            a, b = vs[i], vs[(i + 1) % len(vs)]
            seen[tuple(sorted((a, b)))].append((a, b))
    bad = total = 0
    for key, dirs in seen.items():
        if len(dirs) == 2:
            total += 1
            if dirs[0] == dirs[1]:
                bad += 1
    return {"manifold_edges": total, "inconsistent": bad}


def cross_part_coincident(body, part_of_poly, tol=1e-5):
    """Informational: vertex positions shared (within tol) by two different parts of the joined body."""
    part_of_vert = defaultdict(set)
    for p in body.data.polygons:
        for v in p.vertices:
            part_of_vert[v].add(part_of_poly[p.index])
    buckets = defaultdict(list)
    for v in body.data.vertices:
        key = tuple(int(math.floor(c / tol)) for c in v.co)
        buckets[key].append(v.index)
    pairs = Counter()
    for vids in buckets.values():
        owners = set()
        for v in vids:
            owners |= part_of_vert[v]
        if len(owners) > 1:
            pairs[" / ".join(sorted(owners))] += 1
    return {"tolerance_m": tol, "shared_positions": dict(sorted(pairs.items())),
            "note": "parts are not welded to each other; listed only to show where seams can open under deformation"}


def boundary_edge_count(obj, weld, z_max=None):
    """Boundary edges of a mesh object in world space after a diagnostic weld (optionally only below z_max)."""
    bm = bmesh.new()
    bm.from_mesh(obj.data)
    bm.transform(obj.matrix_world)
    bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=weld)
    edges = [e for e in bm.edges if e.is_boundary and (z_max is None or max(v.co.z for v in e.verts) < z_max)]
    non_manifold = sum(1 for e in bm.edges if not e.is_manifold and not e.is_boundary)
    bm.free()
    return len(edges), non_manifold


def see_through_rays(objects, top_z, cfg):
    """Backface-culled ray test (one-sided UE material): per view, a BVH of only the triangles facing the
    camera (orthographic view direction d: normal . d < 0, normal from the winding); orthographic rays
    through a grid of points on the base top disc must hit one of them. Views: the top and pitch/yaw
    views. A grid point exactly on a shared edge can slip through the BVH test although the surface is
    closed there; a miss is re-tested with 4 rays offset by `jitter_m` and counted only if at least 2 of
    them also miss (an opening narrower than ~2 x jitter would go unnoticed: 0.04 mm = 0.004 uu)."""
    verts, tris = [], []
    for obj in objects:
        mw = obj.matrix_world
        base = len(verts)
        verts.extend(mw @ v.co for v in obj.data.vertices)
        obj.data.calc_loop_triangles()
        tris.extend([base + i for i in t.vertices] for t in obj.data.loop_triangles)
    normals = [geometry.normal(verts[a], verts[b], verts[c]) for a, b, c in tris]
    step, radius, jit = cfg["grid_step_m"], cfg["disc_radius_m"], cfg["jitter_m"]
    n = int(radius / step)
    samples = [Vector((i * step, j * step, top_z)) for i in range(-n, n + 1) for j in range(-n, n + 1)
               if math.hypot(i * step, j * step) <= radius]
    offsets = [Vector((jit, 0.3 * jit, 0.0)), Vector((-0.3 * jit, jit, 0.0)), Vector((-jit, -0.3 * jit, 0.0)),
               Vector((0.3 * jit, -jit, 0.0))]
    raw, confirmed, where = {}, {}, []
    for pitch in cfg["pitches_deg"]:
        yaws = [0] if pitch >= 89.999 else list(range(0, 360, cfg["yaw_step_deg"]))
        for yaw in yaws:
            p, y = math.radians(pitch), math.radians(yaw)
            cam = Vector((math.sin(y) * math.cos(p), -math.cos(y) * math.cos(p), math.sin(p)))
            d = -cam
            front = [t for t, nrm in zip(tris, normals) if nrm.dot(d) < 0]
            bvh = BVHTree.FromPolygons(verts, front, all_triangles=True, epsilon=0.0)
            key = "pitch%02d_yaw%03d" % (int(round(pitch)), yaw)
            raw[key] = confirmed[key] = 0
            for q in samples:
                if bvh.ray_cast(q + cam, d, 3.0)[0] is None:
                    raw[key] += 1
                    if sum(bvh.ray_cast(q + o + cam, d, 3.0)[0] is None for o in offsets) >= 2:
                        confirmed[key] += 1
                        where.append([key] + rv(q, 4))
    return {"samples_per_view": len(samples), "grid_step_m": step, "disc_radius_m": radius, "jitter_m": jit,
            "raw_missed_by_view": raw, "raw_missed_total": sum(raw.values()),
            "missed_by_view": confirmed, "missed_total": sum(confirmed.values()), "missed_samples": where[:50]}


def mask_census(obj, name):
    """Count corners per vertex-colour mask value (rounded to 0/1 per channel) and flag non-binary values."""
    attr = obj.data.color_attributes.get(name)
    if attr is None:
        return None
    arr = np.empty(len(attr.data) * 4, dtype=np.float32)
    attr.data.foreach_get("color", arr)
    arr = arr.reshape(-1, 4)
    binary = bool(np.all((arr < 0.02) | (arr > 0.98)))
    keys = Counter(tuple(int(round(float(c))) for c in row[:3]) for row in arr)
    return {"domain": attr.domain, "type": attr.data_type, "corners": int(len(arr)), "binary": binary,
            "rgb_counts": {"%d%d%d" % k: v for k, v in sorted(keys.items())}}


def roundtrip_measure(scene, bone_names):
    arms = [o for o in scene.objects if o.type == "ARMATURE"]
    meshes = {re.sub(r"\.\d{3}$", "", o.name): o for o in scene.objects if o.type == "MESH"}
    out = {"armatures": len(arms), "armature_objects": sorted(re.sub(r"\.\d{3}$", "", a.name) for a in arms),
           "meshes": {}, "bones": {}}
    if arms:
        arm = arms[0]
        mw = arm.matrix_world
        out["bones"] = {b.name: {"parent": b.parent.name if b.parent else None,
                                 "head_m": [r(c, 5) for c in (mw @ b.head_local)],
                                 "tail_m": [r(c, 5) for c in (mw @ b.tail_local)]} for b in arm.data.bones}
    for name, obj in sorted(meshes.items()):
        entry = mesh_summary(obj)
        entry["weights"] = weight_summary(obj, bone_names) if obj.vertex_groups else None
        lo, hi = world_bounds([obj])
        entry["bounds_m"] = {"min": [r(c, 5) for c in lo], "max": [r(c, 5) for c in hi]}
        out["meshes"][name] = entry
    return out, meshes


def polygon_signatures(obj):
    mesh = obj.data
    mw = obj.matrix_world
    uv = mesh.uv_layers[0].data
    cn = mesh.corner_normals
    rot = mw.to_3x3()
    sigs = defaultdict(list)
    for p in mesh.polygons:
        corners = []
        normals = {}
        for li in p.loop_indices:
            co = mw @ mesh.vertices[mesh.loops[li].vertex_index].co
            key = (round(co.x, 4), round(co.y, 4), round(co.z, 4), round(uv[li].uv.x, 5), round(uv[li].uv.y, 5))
            corners.append(key)
            normals[key] = (rot @ cn[li].vector).normalized()
        sig = (p.material_index, tuple(sorted(corners)))
        sigs[sig].append(((rot @ p.normal).normalized(), normals, p.index))
    return sigs


def compare_meshes(candidate, reference, part_of_poly):
    a, b = polygon_signatures(candidate), polygon_signatures(reference)
    unmatched_candidate = unmatched_reference = 0
    same = defaultdict(int)
    flipped = defaultdict(int)
    corner_same = defaultdict(int)
    corner_negated = defaultdict(int)
    corner_other = defaultdict(int)
    other_detail = []
    scale2 = (candidate.matrix_world.to_3x3().determinant() ** (2.0 / 3.0)) * 1e4  # m2 -> cm2
    sliver_vertices = {v for p in candidate.data.polygons if p.area * scale2 < DEGENERATE_AREA_CM2 for v in p.vertices}
    for sig, items in a.items():
        refs = b.get(sig, [])
        unmatched_candidate += max(0, len(items) - len(refs))
        for (n_a, cn_a, idx), (n_b, cn_b, _i) in zip(items, refs):
            part = part_of_poly.get(idx, "unassigned")
            if n_a.dot(n_b) >= 0:
                same[part] += 1
            else:
                flipped[part] += 1
            for key, va in cn_a.items():
                d = va.dot(cn_b[key])
                if d > 0.999:
                    corner_same[part] += 1
                elif d < -0.999:
                    corner_negated[part] += 1
                else:
                    corner_other[part] += 1
                    poly = candidate.data.polygons[idx]
                    other_detail.append({"part": part, "polygon": idx, "dot": r(d, 4),
                                         "area_cm2": r(poly.area * scale2, 9),
                                         "touches_near_degenerate": bool(set(poly.vertices) & sliver_vertices)})
    for sig, items in b.items():
        unmatched_reference += max(0, len(items) - len(a.get(sig, [])))
    return {"polygons_candidate": len(candidate.data.polygons), "polygons_reference": len(reference.data.polygons),
            "unmatched_candidate_polygons": unmatched_candidate, "unmatched_reference_polygons": unmatched_reference,
            "same_winding_by_part": dict(sorted(same.items())), "flipped_winding_by_part": dict(sorted(flipped.items())),
            "corner_normals_same_by_part": dict(sorted(corner_same.items())),
            "corner_normals_negated_by_part": dict(sorted(corner_negated.items())),
            "corner_normals_other_by_part": dict(sorted(corner_other.items())),
            "corner_normals_other_detail": sorted(other_detail, key=lambda e: (e["part"], e["polygon"]))[:50],
            "precision": "positions 1e-4 m, UV 1e-5, material index; corner normals |dot| > 0.999"}


def labelled_objects(labelled):
    for obj, parts in labelled:
        for name in parts:
            yield name, obj, parts[name]
