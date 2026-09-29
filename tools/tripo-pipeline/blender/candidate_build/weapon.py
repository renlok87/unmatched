"""Weapon assembly of the seated flow.

mode "split-from-part" (King Arthur): the weapon is fused with a fist in one GLB part; polygons are classified
  by height bands, base-colour saturation and distance to the fitted weapon axis, then island smoothing; the
  gap Tripo left inside the fist is closed by an open cylinder on the fitted axis (grip_bridge_fitted).
mode "parts" (Merlin): the weapon is several whole GLB parts joined into one mesh; the shaft inside the fist is
  closed by an open cylinder on the axis through two vertex bands (staff_axis + grip_bridge_axis) and open
  loops of one part below a height are fan-filled (cap_loops_chain).
Moved unchanged from build_arthur_candidate.py / build_merlin_candidate.py (2026-09-28)."""

import colorsys
import math
from collections import Counter, defaultdict

import bmesh
from mathutils import Vector

from .core import CN_ATTR, PART_ATTR, r, rv
from .mesh_ops import dist_to_line, islands


def split_weapon(scene, obj, cfg, bc_pixels, bc_size):
    """Classify polygons of the fused weapon+fist part; returns (hand_obj, weapon_obj, info, (axis_c, axis_d))."""
    mesh = obj.data
    uv = mesh.uv_layers[0].data
    W = H = bc_size
    blade = [p.center.copy() for p in mesh.polygons if p.center.z >= cfg["axis_fit"]["blade_z_min"]]
    pommel = [p.center.copy() for p in mesh.polygons if p.center.z <= cfg["axis_fit"]["pommel_z_max"]]
    top_c = sum(blade, Vector()) / len(blade)
    pom_c = sum(pommel, Vector()) / len(pommel)
    axis_d = (top_c - pom_c).normalized()
    cls, reason = {}, Counter()
    for p in mesh.polygons:
        z = p.center.z
        if z >= cfg["sword_if_z_at_least"]:
            k, why = "sword", "above_guard_line"
        elif z < cfg["sword_if_z_below"]:
            k, why = "sword", "below_fist_line"
        else:
            u = sum(uv[l].uv.x for l in p.loop_indices) / p.loop_total
            v = sum(uv[l].uv.y for l in p.loop_indices) / p.loop_total
            # atlas UV -> texel of the atlas BC (bottom-up rows in Blender pixel order)
            px = min(W - 1, max(0, int(u * W)))
            py = min(H - 1, max(0, int(v * H)))
            rgb = bc_pixels[py, px, :3]
            _h, s, val = colorsys.rgb_to_hsv(*[float(c) for c in rgb])
            if s > cfg["saturation_min"] and val > cfg["value_min"]:
                k, why = "sword", "saturated_texel"
            elif dist_to_line(p.center, pom_c, axis_d) <= cfg["grip_radius_m"]:
                k, why = "sword", "on_grip_axis"
            else:
                k, why = "hand", "grey_off_axis"
        cls[p.index] = k
        reason[why] += 1
    flips = 0
    for _round in range(6):
        changed = 0
        for kind, other in (("sword", "hand"), ("hand", "sword")):
            _n, _sizes, comps = islands(mesh, [i for i, k in cls.items() if k == kind])
            for comp in comps:
                if len(comp) < cfg["min_island_polygons"]:
                    for f in comp:
                        cls[f] = other
                    changed += len(comp)
        flips += changed
        if not changed:
            break
    sword = obj.copy()
    sword.data = obj.data.copy()
    scene.collection.objects.link(sword)
    for target, keep in ((obj, "hand"), (sword, "sword")):
        bm = bmesh.new()
        bm.from_mesh(target.data)
        bm.faces.ensure_lookup_table()
        doomed = [f for f in bm.faces if cls[f.index] != keep]
        bmesh.ops.delete(bm, geom=doomed, context="FACES")
        bm.to_mesh(target.data)
        bm.free()
        target.data.update()
    counts = Counter(cls.values())
    info = {"polygons": dict(sorted(counts.items())), "reasons_before_smoothing": dict(sorted(reason.items())),
            "smoothing_reassigned_polygons": flips,
            "axis_fit": {"blade_centroid_m": rv(top_c, 5), "pommel_centroid_m": rv(pom_c, 5),
                         "direction": rv(axis_d, 5)},
            "islands_after_split": {"hand": islands(obj.data)[1], "sword": islands(sword.data)[1]}}
    return obj, sword, info, (pom_c, axis_d)


def grip_bridge_fitted(weapon, bcfg, axis_c, axis_d):
    """Close the grip Tripo never modelled inside the fist: an open triangle-strip cylinder on the fitted
    weapon axis from the top of the lowest island (grip stub + pommel) to the bottom of the highest island
    (guard + blade), both overlapped by `overlap_m`. Radius = median distance to the axis of the stub
    vertices within `near_top_m` of its top. UVs: a small rectangle inside the largest grip polygon's UV
    triangle (leather texels, non-degenerate for tangents). Corner normals: radial."""
    mesh = weapon.data
    n, sizes, comps = islands(mesh)
    if n < 2:
        return {"added": False, "reason": "weapon is a single island"}

    def t_of(p):
        return (Vector(p) - axis_c).dot(axis_d)

    info = []
    for comp in comps:
        vids = sorted({v for f in comp for v in mesh.polygons[f].vertices})
        ts = [t_of(mesh.vertices[v].co) for v in vids]
        info.append({"mean": sum(ts) / len(ts), "min": min(ts), "max": max(ts), "faces": comp, "verts": vids})
    info.sort(key=lambda c: c["mean"])
    lower, upper = info[0], info[-1]
    t0, t1 = lower["max"] - bcfg["overlap_m"], upper["min"] + bcfg["overlap_m"]
    gap = upper["min"] - lower["max"]
    if gap <= 0:
        return {"added": False, "reason": "islands overlap along the axis", "gap_m": r(gap, 5)}
    near = sorted(dist_to_line(mesh.vertices[v].co, axis_c, axis_d) for v in lower["verts"]
                  if t_of(mesh.vertices[v].co) >= lower["max"] - bcfg["near_top_m"])
    radius = near[len(near) // 2] * bcfg["radius_factor"]
    uv = mesh.uv_layers[0].data
    grip_faces = [f for f in lower["faces"] if t_of(mesh.polygons[f].center) > lower["mean"]
                  and dist_to_line(mesh.polygons[f].center, axis_c, axis_d) <= 1.6 * radius]
    src = max(grip_faces, key=lambda f: mesh.polygons[f].area)
    tri = [uv[li].uv.copy() for li in mesh.polygons[src].loop_indices][:3]
    cen = (tri[0] + tri[1] + tri[2]) / 3
    inr = min(abs((tri[(i + 1) % 3] - tri[i]).orthogonal().normalized().dot(cen - tri[i])) for i in range(3))
    half = 0.4 * inr
    bm = bmesh.new()
    bm.from_mesh(mesh)
    uv_layer = bm.loops.layers.uv.active
    cn_layer = bm.loops.layers.float_vector.get(CN_ATTR)
    a = axis_d
    ref = Vector((1, 0, 0)) if abs(a.x) < 0.9 else Vector((0, 1, 0))
    e1 = a.cross(ref).normalized()
    e2 = a.cross(e1).normalized()
    sides = bcfg["sides"]
    angles = [2 * math.pi * i / sides for i in range(sides)]
    radial = [(e1 * math.cos(t) + e2 * math.sin(t)).normalized() for t in angles]
    rings = [[bm.verts.new(axis_c + a * t + radial[i] * radius) for i in range(sides)] for t in (t0, t1)]
    added = 0
    for i in range(sides):
        j = (i + 1) % sides
        uj = 1.0 if j == 0 else j / sides
        corners = {(0, i): (i / sides, 0.0), (0, j): (uj, 0.0), (1, i): (i / sides, 1.0), (1, j): (uj, 1.0)}
        for keys in (((0, i), (0, j), (1, j)), ((0, i), (1, j), (1, i))):
            face = bm.faces.new([rings[k][s] for k, s in keys])
            face.material_index = 0
            face.normal_update()
            mid = (radial[i] + radial[j]).normalized()
            if face.normal.dot(mid) < 0:
                face.normal_flip()
            for loop in face.loops:
                k, s = next(key for key in keys if rings[key[0]][key[1]] is loop.vert)
                u, v = corners[(k, s)]
                loop[uv_layer].uv = (cen.x + (2 * u - 1) * half, cen.y + (2 * v - 1) * half)
                loop[cn_layer] = radial[s]
            added += 1
    bm.to_mesh(mesh)
    bm.free()
    mesh.update()
    return {"added": True, "triangles": added, "sides": sides, "radius_m": r(radius, 5), "gap_m": r(gap, 5),
            "from_t_m": r(t0, 5), "to_t_m": r(t1, 5), "overlap_m": bcfg["overlap_m"],
            "islands_bridged": [len(lower["faces"]), len(upper["faces"])],
            "uv_source_polygon_area_m2": r(mesh.polygons[src].area, 9), "uv_rect_half_extent": r(half, 6),
            "uv_rect_centre": rv(cen, 6)}


def staff_axis(obj, labels, rings, to_final_z):
    """Axis through the centroids of two vertex bands: (part, (z0, z1) source) below and above the fist."""
    mesh = obj.data
    cents = []
    for part, (z0, z1) in sorted(rings.items(), key=lambda kv: kv[1][0]):
        lo, hi = to_final_z(z0), to_final_z(z1)
        vids = sorted({v for f in labels[part] for v in mesh.polygons[f].vertices if lo <= mesh.vertices[v].co.z <= hi})
        pts = [mesh.vertices[v].co for v in vids]
        cents.append((part, sum(pts, Vector()) / len(pts), vids))
    (_pa, ca, va), (_pb, cb, vb) = cents
    d = (cb - ca).normalized()
    radii = sorted(dist_to_line(mesh.vertices[v].co, ca, d) for v in va + vb)
    return ca, d, radii[len(radii) // 2], {"below_centroid_m": rv(ca, 5), "above_centroid_m": rv(cb, 5),
                                            "direction": rv(d, 5), "median_radius_m": r(radii[len(radii) // 2], 5),
                                            "band_vertices": [len(va), len(vb)]}


def grip_bridge_axis(staff, labels, bcfg, axis_c, axis_d, radius, to_final_z):
    """Open triangle-strip cylinder on the fitted shaft axis between two heights (inside the fist).
    UVs: a small rectangle inside the largest lower-shaft polygon near the fist; corner normals radial."""
    mesh = staff.data
    a = axis_d
    z_from, z_to = to_final_z(bcfg["from_source_z"]), to_final_z(bcfg["to_source_z"])
    # axis parameter at the given heights
    t0 = (z_from - axis_c.z) / a.z
    t1 = (z_to - axis_c.z) / a.z
    rad = radius * bcfg["radius_factor"]
    uv = mesh.uv_layers[0].data
    band_lo, band_hi = to_final_z(bcfg["uv_source_band_z"][0]), to_final_z(bcfg["uv_source_band_z"][1])
    cand = [f for f in labels[bcfg["lower_part"]] if band_lo <= mesh.polygons[f].center.z <= band_hi]
    src = max(cand, key=lambda f: mesh.polygons[f].area)
    tri = [uv[li].uv.copy() for li in mesh.polygons[src].loop_indices][:3]
    cen = (tri[0] + tri[1] + tri[2]) / 3
    inr = min(abs((tri[(i + 1) % 3] - tri[i]).orthogonal().normalized().dot(cen - tri[i])) for i in range(3))
    half = 0.4 * inr
    bm = bmesh.new()
    bm.from_mesh(mesh)
    uv_layer = bm.loops.layers.uv.active
    cn_layer = bm.loops.layers.float_vector.get(CN_ATTR)
    part_layer = bm.faces.layers.int.get(PART_ATTR)
    ref = Vector((1, 0, 0)) if abs(a.x) < 0.9 else Vector((0, 1, 0))
    e1 = a.cross(ref).normalized()
    e2 = a.cross(e1).normalized()
    sides = bcfg["sides"]
    angles = [2 * math.pi * i / sides for i in range(sides)]
    radial = [(e1 * math.cos(t) + e2 * math.sin(t)).normalized() for t in angles]
    rings = [[bm.verts.new(axis_c + a * t + radial[i] * rad) for i in range(sides)] for t in (t0, t1)]
    added = 0
    lower_index = int(bcfg["lower_part"].split("_")[-1])
    for i in range(sides):
        j = (i + 1) % sides
        uj = 1.0 if j == 0 else j / sides
        corners = {(0, i): (i / sides, 0.0), (0, j): (uj, 0.0), (1, i): (i / sides, 1.0), (1, j): (uj, 1.0)}
        for keys in (((0, i), (0, j), (1, j)), ((0, i), (1, j), (1, i))):
            face = bm.faces.new([rings[k][s] for k, s in keys])
            face.material_index = 0
            face[part_layer] = lower_index
            face.normal_update()
            mid = (radial[i] + radial[j]).normalized()
            if face.normal.dot(mid) < 0:
                face.normal_flip()
            for loop in face.loops:
                k, s = next(key for key in keys if rings[key[0]][key[1]] is loop.vert)
                u, v = corners[(k, s)]
                loop[uv_layer].uv = (cen.x + (2 * u - 1) * half, cen.y + (2 * v - 1) * half)
                loop[cn_layer] = radial[s]
            added += 1
    bm.to_mesh(mesh)
    bm.free()
    mesh.update()
    return {"added": True, "triangles": added, "sides": sides, "radius_m": r(rad, 5),
            "shaft_median_radius_m": r(radius, 5), "from_t_m": r(t0, 5), "to_t_m": r(t1, 5),
            "from_z_m": r(z_from, 5), "to_z_m": r(z_to, 5),
            "uv_source_polygon_area_m2": r(mesh.polygons[src].area, 9), "uv_rect_half_extent": r(half, 6),
            "uv_rect_centre": rv(cen, 6)}


def cap_loops_chain(staff, labels, ccfg, to_final_z):
    """Fan-fill open boundary loops of one weapon part below a height (the shaft bottom). Loops are walked as
    chains of boundary edges; the fan UV of each loop vertex comes from its boundary face, the centre UV is
    their mean, corner normals point from the part centroid to the loop centre."""
    mesh = staff.data
    part = ccfg["part"]
    zmax = to_final_z(ccfg["below_source_z"])
    part_index = int(part.split("_")[-1])
    part_faces = set(labels[part])
    bm = bmesh.new()
    bm.from_mesh(mesh)
    bm.faces.ensure_lookup_table()
    uv_layer = bm.loops.layers.uv.active
    cn_layer = bm.loops.layers.float_vector.get(CN_ATTR)
    part_layer = bm.faces.layers.int.get(PART_ATTR)
    part_centre = sum((bm.faces[f].calc_center_median() for f in part_faces), Vector()) / len(part_faces)
    bedges = [e for e in bm.edges if e.is_boundary and e.link_faces[0].index in part_faces]
    adj = defaultdict(list)
    for e in bedges:
        a, b = e.verts
        adj[a].append((b, e))
        adj[b].append((a, e))
    seen, loops_found = set(), []
    for start in list(adj):
        if start in seen:
            continue
        chain, prev, cur = [start], None, start
        seen.add(start)
        while True:
            nxt = [v for v, _e in adj[cur] if v is not prev and v not in seen]
            if not nxt:
                break
            prev, cur = cur, nxt[0]
            seen.add(cur)
            chain.append(cur)
        loops_found.append(chain)
    caps = []
    for chain in loops_found:
        if len(chain) < ccfg["min_vertices"]:
            continue
        centre = sum((v.co for v in chain), Vector()) / len(chain)
        if centre.z > zmax:
            continue
        # UV of each boundary vertex from its boundary face
        vuv = {}
        for v in chain:
            for loop in v.link_loops:
                if loop.face.index in part_faces:
                    vuv[v] = loop[uv_layer].uv.copy()
                    break
        cuv = sum(vuv.values(), Vector((0.0, 0.0))) / len(vuv)
        outward = (centre - part_centre).normalized()
        cv = bm.verts.new(centre)
        new = 0
        for i in range(len(chain)):
            a, b = chain[i], chain[(i + 1) % len(chain)]
            if bm.edges.get((a, b)) is None:
                continue  # open chain end
            face = bm.faces.new((a, b, cv))
            face.material_index = 0
            face[part_layer] = part_index
            face.normal_update()
            if face.normal.dot(outward) < 0:
                face.normal_flip()
            for loop in face.loops:
                loop[uv_layer].uv = cuv if loop.vert is cv else vuv[loop.vert]
                loop[cn_layer] = outward
            new += 1
        caps.append({"loop_vertices": len(chain), "triangles": new, "centre_m": rv(centre, 5),
                     "outward": rv(outward, 4)})
    bm.to_mesh(mesh)
    bm.free()
    mesh.update()
    return caps
