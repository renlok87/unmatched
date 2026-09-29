"""Closing Tripo segmentation openings (seated flow).

cap_base_top   (profile closure.base_top, King Arthur): footprint holes in the flat top of a normalised base are
               capped flat, UVs moved onto clean stone (verify 2026-09-28).
cap_soles      (profile closure.soles, King Arthur): open soles of foot parts filled flat.
cap_loops_component (profile open_loop_caps, Harpy): listed open loops of a part fan-filled around their
               centroid (connected components of the boundary-edge graph, angular ordering in the loop plane).
Moved unchanged from build_arthur_candidate.py / build_harpy_candidate.py (2026-09-28)."""

import math
from collections import Counter, defaultdict

import bmesh
import numpy as np
from mathutils import Vector
from mathutils.kdtree import KDTree

from .core import CN_ATTR, PART_ATTR, r, rv, to_final_point


def ordered_boundary_loops(bm, select=None):
    """Boundary cycles of the boundary edges accepted by `select(edge)` (default: all), walked AGAINST the
    winding of the face on each edge, so a face built from a cycle is wound like its neighbours. At every
    vertex the walk turns to the next boundary edge by rotating through the faces around the vertex (a fan
    walk), so pinch vertices (two openings touching at one vertex) are passed correctly; a cycle that visits
    a vertex twice is split there into simple sub-cycles.
    Returns [{"verts": [BMVert] (simple), "cycle_edges": int, "against_winding": int (edges of the cycle
    walked against their face), "closed": bool}]."""
    bm.verts.index_update()
    bm.edges.index_update()
    bm.faces.index_update()
    bnd = sorted((e for e in bm.edges if e.is_boundary and (select is None or select(e))), key=lambda e: e.index)
    chosen = {e.index for e in bnd}
    used, out = set(), []

    def loop_at(face, vert):
        return next(l for l in face.loops if l.vert.index == vert.index)

    for e0 in bnd:
        if e0.index in used:
            continue
        l0 = e0.link_loops[0]                      # its face traverses l0.vert -> l0.next.vert
        start = l0.link_loop_next.vert             # the walk goes the other way
        verts, closed, against = [start], True, 1
        cur_edge, cur_face, a = e0, l0.face, l0.vert
        used.add(e0.index)
        while a.index != start.index:
            verts.append(a)
            face, came, found = cur_face, cur_edge, None
            for _spin in range(1024):
                la = loop_at(face, a)
                other = la.link_loop_prev.edge if la.edge.index == came.index else la.edge
                if other.is_boundary:
                    found = (other, face, la)
                    break
                nxt = [f for f in other.link_faces if f.index != face.index]
                if not nxt:
                    break
                face, came = nxt[0], other
            if found is None or found[0].index not in chosen or found[0].index in used:
                closed = False
                break
            e2, face, la = found
            against += int(la.link_loop_prev.edge.index == e2.index)  # the face traverses q -> a
            used.add(e2.index)
            cur_edge, cur_face, a = e2, face, e2.other_vert(a)
        pieces, stack, pos = [], [], {}
        for v in verts:
            if v.index in pos:
                i = pos[v.index]
                pieces.append(stack[i:])
                for w in stack[i + 1:]:
                    del pos[w.index]
                stack = stack[:i + 1]
            else:
                pos[v.index] = len(stack)
                stack.append(v)
        pieces.append(stack)
        for piece in pieces:
            if len(piece) >= 3:
                out.append({"verts": piece, "cycle_edges": len(verts), "against_winding": against, "closed": closed,
                            "split_from_cycle": len(pieces) > 1})
    return out


def hsv_arrays(rgb):
    mx, mn = rgb.max(axis=2), rgb.min(axis=2)
    d = np.maximum(mx - mn, 1e-6)
    red, green, blue = rgb[..., 0], rgb[..., 1], rgb[..., 2]
    hue = np.where(mx == red, ((green - blue) / d) % 6,
                   np.where(mx == green, (blue - red) / d + 2, (red - green) / d + 4)) * 60.0
    sat = np.where(mx > 0, (mx - mn) / np.maximum(mx, 1e-6), 0.0)
    return hue, sat, mx


def dilate(mask, radius):
    """Square binary dilation (separable, no scipy in Blender's Python)."""
    out = mask.copy()
    for axis in (0, 1):
        src = out.copy()
        for k in range(1, radius + 1):
            if axis == 0:
                out[k:, :] |= src[:-k, :]
                out[:-k, :] |= src[k:, :]
            else:
                out[:, k:] |= src[:, :-k]
                out[:, :-k] |= src[:, k:]
    return out


def tri_pixels(pts, width):
    """Pixel indices (rows, cols) of a cell-local top-down triangle (pixel centres inside or on the edge)."""
    (ax, ay), (bx, by), (cx, cy) = pts
    d = (by - cy) * (ax - cx) + (cx - bx) * (ay - cy)
    empty = (np.zeros(0, dtype=np.int64), np.zeros(0, dtype=np.int64))
    if abs(d) < 1e-12:
        return empty
    minx, maxx = max(int(math.floor(min(ax, bx, cx))), 0), min(int(math.ceil(max(ax, bx, cx))), width - 1)
    miny, maxy = max(int(math.floor(min(ay, by, cy))), 0), min(int(math.ceil(max(ay, by, cy))), width - 1)
    if maxx < minx or maxy < miny:
        return empty
    gx, gy = np.meshgrid(np.arange(minx, maxx + 1) + 0.5, np.arange(miny, maxy + 1) + 0.5)
    l1 = ((by - cy) * (gx - cx) + (cx - bx) * (gy - cy)) / d
    l2 = ((cy - ay) * (gx - cx) + (ax - cx) * (gy - cy)) / d
    inside = (l1 >= -1e-7) & (l2 >= -1e-7) & (1.0 - l1 - l2 >= -1e-7)
    return (gy[inside] - 0.5).astype(np.int64), (gx[inside] - 0.5).astype(np.int64)


def face_cell_pixels(face, uv_layer, cell, size):
    x0, y0, width = cell["x"], cell["y_top"], cell["cell"]
    pts = [(l[uv_layer].uv.x * size - x0, (1.0 - l[uv_layer].uv.y) * size - y0) for l in face.loops]
    rows, cols = [], []
    for i in range(1, len(pts) - 1):
        rr, cc = tri_pixels((pts[0], pts[i], pts[i + 1]), width)
        rows.append(rr)
        cols.append(cc)
    return np.concatenate(rows), np.concatenate(cols)


def donor_shift(footprint, clean, feats=None, target=None, tone_tol=None):
    """Integer pixel shift (dr, dc) that puts every footprint pixel on a clean pixel (FFT correlation of
    the footprint with the unclean mask; the pick is re-verified exactly). Without a tone target: the
    smallest shift. With `feats` (H x W x C texel features of the cell: BC luminance, normal-map R/G) and
    `target` (C values): among the valid shifts, the smallest one whose mean footprint features are all
    within `tone_tol` (C tolerances) of the target, else the one with the smallest max(|diff| / tol).
    Returns (dr, dc, mean features at the pick or None) or None."""
    rows, cols = np.nonzero(footprint)
    r0, r1, c0, c1 = rows.min(), rows.max(), cols.min(), cols.max()
    kernel = footprint[r0:r1 + 1, c0:c1 + 1].astype(np.float64)
    kh, kw = kernel.shape
    width = clean.shape[0]
    shape = (width + kh, width + kw)
    fk = np.fft.rfft2(kernel[::-1, ::-1], s=shape)

    def correlate(img):
        return np.fft.irfft2(np.fft.rfft2(img, s=shape) * fk, s=shape)[kh - 1:width, kw - 1:width]

    score = correlate((~clean).astype(np.float64))
    ys, xs = np.nonzero(score < 0.5)
    if not len(ys):
        return None
    dr, dc = ys - r0, xs - c0
    dist2 = dr * dr + dc * dc
    if feats is not None and target is not None:
        mean = np.stack([correlate(feats[..., c].astype(np.float64))[ys, xs] / kernel.sum()
                         for c in range(feats.shape[2])], axis=1)
        cost = (np.abs(mean - np.array(target)) / np.array(tone_tol)).max(axis=1)
        ok = cost <= 1.0
        order = np.lexsort((dc, dr, dist2, ~ok)) if ok.any() else np.lexsort((dc, dr, dist2, cost))
    else:
        mean = None
        order = np.lexsort((dc, dr, dist2))
    for k in order:
        if clean[rows + dr[k], cols + dc[k]].all():
            return int(dr[k]), int(dc[k]), ([float(c) for c in mean[k]] if mean is not None else None)
    return None


def raster_faces(faces, uv_layer, cell, size):
    mask = np.zeros((cell["cell"], cell["cell"]), dtype=bool)
    for f in faces:
        rr, cc = face_cell_pixels(f, uv_layer, cell, size)
        mask[rr, cc] = True
    return mask


def ring_tone(mask, clean, feats, inner, outer):
    ring = dilate(mask, outer) & ~dilate(mask, inner) & clean
    return [float(np.median(feats[..., c][ring])) for c in range(feats.shape[2])] if ring.any() else None


def place_uvs(faces, uv_layer, cell, size, clean, feats, cfg, scales):
    """Shift (and if needed scale about their centre) the UVs of `faces` onto clean texels whose tone
    matches the clean stone around the faces' own footprint. Returns the placement record."""
    uv0 = {(f.index, k): tuple(loop[uv_layer].uv) for f in faces for k, loop in enumerate(f.loops)}
    centre_uv = np.mean(np.array(list(uv0.values())), axis=0)
    target = ring_tone(raster_faces(faces, uv_layer, cell, size), clean, feats, cfg["tone_ring_px"][0],
                       cfg["tone_ring_px"][1])
    pick, uv_scale, foot = None, None, None
    for uv_scale in scales:
        for f in faces:
            for k, loop in enumerate(f.loops):
                loop[uv_layer].uv = tuple(centre_uv + (np.array(uv0[(f.index, k)]) - centre_uv) * uv_scale)
        foot = dilate(raster_faces(faces, uv_layer, cell, size), cfg["mip_bleed_px"])
        pick = donor_shift(foot, clean, feats, target, cfg["tone_tolerance"])
        if pick is not None:
            break
    if pick is None:
        return None
    dr, dcol, mean = pick
    for f in faces:
        for loop in f.loops:
            u, v = loop[uv_layer].uv
            loop[uv_layer].uv = (u + dcol / size, v - dr / size)
    return {"uv_scale": uv_scale, "footprint_px": int(foot.sum()), "donor_shift_px": [dcol, dr],
            "tone_target": rv(target, 4) if target is not None else None,
            "tone_donor": rv(mean, 4) if mean is not None else None}


def cap_base_top(obj, top_z, linear, cfg, bc_px, n_px, cell, size):
    """Close the Tripo footprint holes in the flat top of the base (verify 2026-09-28: 4 boundary loops,
    74 edges; after the non-uniform base normalisation they no longer match the feet and show as
    see-through crescents / dark openings when a foot lifts).

    1. The flat top (z = top, normal +Z) is one planar UV chart: an affine XY -> UV map is fitted on it.
    2. Texels of the hole regions are black and the bake left a bronze boot fringe around them: flat top
       faces near a hole with dark/bronze texels (dilated by the mip bleed margin) are removed together
       with the hole (the top is flat, so the shape does not change). Short vertical hole walls left
       standing as free ribbons are removed too.
    3. Every resulting boundary loop is capped flat at z = top. Loop vertices below the top (ends of the
       cracks that run into the holes) get a raised copy at the top and a small vertical wall to it, so
       the cracks end in a closed wall instead of an opening.
    4. The Tripo top has a few overlapping slivers (folds). A cap loop running along one would need a
       flipped triangle to close; the flat faces next to such a triangle are removed as well and the caps
       rebuilt from scratch (repeated until no cap triangle faces down).
    5. Cap and wall UVs use the same affine map, shifted by the smallest pixel offset that puts the whole
       footprint (+ bleed margin) on clean flat-top texels (uv_scale_steps if nothing fits): stone texture,
       no BC edit.
    Corner normals (float corner attribute CN_ATTR, still in the source frame of the base): +Z for caps,
    the wall normal for walls, stored as M^T n so that apply_corner_normals(M^-T) gives the final value."""
    mesh = obj.data
    mt = np.array(linear, dtype=np.float64).T
    tol, low_tol = cfg["top_tolerance_m"], cfg["below_top_m"]

    def src_normal(n):
        v = mt @ np.array(tuple(n), dtype=np.float64)
        return tuple(v / np.linalg.norm(v))

    def is_flat(f):
        return f.normal.z > cfg["flat_normal_z_min"] and all(abs(v.co.z - top_z) < tol for v in f.verts)

    def xy_area_of(verts):
        xy = [(v.co.x, v.co.y) for v in verts]
        return sum(xy[i][0] * xy[(i + 1) % len(xy)][1] - xy[(i + 1) % len(xy)][0] * xy[i][1]
                   for i in range(len(xy))) / 2.0

    # ---------------- analysis on the untouched mesh (face indices = mesh polygon indices)
    bm = bmesh.new()
    bm.from_mesh(mesh)
    uv_layer = bm.loops.layers.uv.active
    holes = ordered_boundary_loops(bm)
    hole_info = []
    for lp in holes:
        pts = [v.co for v in lp["verts"]]
        hole_info.append({"edges": len(lp["verts"]), "closed": lp["closed"],
                          "centre_m": rv(sum(pts, Vector()) / len(pts), 4),
                          "size_xy_m": [r(max(p[i] for p in pts) - min(p[i] for p in pts), 4) for i in range(2)],
                          "z_range_m": [r(min(p.z for p in pts), 5), r(max(p.z for p in pts), 5)]})
    hole_verts = {v.index for lp in holes for v in lp["verts"]}
    flat = [f for f in bm.faces if is_flat(f)]
    smooth_default = Counter(f.smooth for f in flat).most_common(1)[0][0]
    rows, uvs = [], []
    for f in flat:
        if not any(v.index in hole_verts for v in f.verts):
            for loop in f.loops:
                rows.append((loop.vert.co.x, loop.vert.co.y, 1.0))
                uvs.append(tuple(loop[uv_layer].uv))
    design, target = np.array(rows), np.array(uvs)
    affine = np.linalg.lstsq(design, target, rcond=None)[0]
    resid_px = float(np.sqrt(((design @ affine - target) ** 2).sum(axis=1).max())) * size
    if resid_px > cfg["affine_max_residual_px"]:
        raise RuntimeError("base top is not one planar UV chart (residual %.3f px)" % resid_px)

    width = cell["cell"]
    height = bc_px.shape[0]
    tile = bc_px[height - cell["y_top"] - width:height - cell["y_top"], cell["x"]:cell["x"] + width, :3][::-1]
    hue, sat, val = hsv_arrays(tile.astype(np.float64))
    dc_cfg = cfg["dirty_texels"]
    dark = val < dc_cfg["dark_value_max"]
    bronze = ((hue >= dc_cfg["bronze_hue_deg"][0]) & (hue <= dc_cfg["bronze_hue_deg"][1]) &
              (sat > dc_cfg["bronze_s_min"]) & (val > dc_cfg["bronze_v_min"]))
    covered = np.zeros((width, width), dtype=bool)
    for f in bm.faces:
        rr, cc = face_cell_pixels(f, uv_layer, cell, size)
        covered[rr, cc] = True
    dark &= ~covered  # dark texels no face uses: the hole regions of the chart (and the chart background)
    dirty = dilate(dark | bronze, cfg["mip_bleed_px"])
    ntile = n_px[height - cell["y_top"] - width:height - cell["y_top"], cell["x"]:cell["x"] + width, :3][::-1]
    feats = np.dstack([tile[..., 0] * 0.2126 + tile[..., 1] * 0.7152 + tile[..., 2] * 0.0722,
                       ntile[..., 0], ntile[..., 1]])  # BC luminance, tangent normal R, G
    dirty_count = {}
    for f in flat:
        rr, cc = face_cell_pixels(f, uv_layer, cell, size)
        dirty_count[f.index] = (int(dirty[rr, cc].sum()), int(len(rr)))

    hole_xy = KDTree(len(hole_verts))
    for v in bm.verts:
        if v.index in hole_verts:
            hole_xy.insert((v.co.x, v.co.y, 0.0), v.index)
    hole_xy.balance()
    reach = cfg["region_max_distance_from_hole_m"]

    def near_hole(f):
        return max(hole_xy.find((v.co.x, v.co.y, 0.0))[2] for v in f.verts) <= reach

    def is_dirty(f):
        n, total = dirty_count[f.index]
        if not near_hole(f):
            # compact caps: long flat faces reaching further from a hole stay (and so does the dark crack
            # line that runs between the toe holes: a crack of the slab, not a footprint)
            return False
        return n >= dc_cfg["face_min_texels"] or (total and n / total >= dc_cfg["face_min_fraction"])

    region, visited = set(), set(hole_verts)
    frontier = set(hole_verts)
    flat_set = {f.index for f in flat}
    bm.verts.ensure_lookup_table()
    while frontier:
        added = set()
        for vi in sorted(frontier):
            for f in bm.verts[vi].link_faces:
                if f.index in flat_set and f.index not in region and is_dirty(f):
                    region.add(f.index)
                    added.add(f.index)
        bm.faces.ensure_lookup_table()
        frontier = {v.index for fi in added for v in bm.faces[fi].verts} - visited
        visited |= frontier
    bm.faces.ensure_lookup_table()
    removed_dirty = sum(dirty_count[i][0] for i in region)
    remaining_dirty = sum(n for i, (n, _t) in dirty_count.items() if i not in region and near_hole(bm.faces[i]))
    face_area = {f.index: f.calc_area() for f in bm.faces}
    bm.free()

    def uv_of(co, normal):
        """The top's planar map; faces that are not horizontal are unfolded outward along their horizontal
        normal by their depth below the top (non-degenerate UVs for crack-end walls)."""
        x, y = co[0], co[1]
        horiz = math.hypot(normal[0], normal[1])
        if normal[2] <= 0.5 and horiz > 1e-9:
            depth = top_z - co[2]
            x, y = x + normal[0] / horiz * depth, y + normal[1] / horiz * depth
        u, v = np.array((x, y, 1.0)) @ affine
        return float(u), float(v)

    # ---------------- build the caps; rebuild from scratch while a cap needs a flipped triangle (fold)
    forced, fold_fixes = set(), []
    for _attempt in range(cfg["fold_fix_max_attempts"]):
        bm = bmesh.new()
        bm.from_mesh(mesh)
        uv_layer = bm.loops.layers.uv.active
        cn_layer = bm.loops.layers.float_vector.get(CN_ATTR)
        orig_layer = bm.faces.layers.int.new("um_orig_face")
        tag_layer = bm.faces.layers.int.new("um_cap_tag")
        bm.faces.ensure_lookup_table()
        for f in bm.faces:
            f[orig_layer] = f.index + 1
        doomed_ix = sorted(region | forced)
        bmesh.ops.delete(bm, geom=[bm.faces[i] for i in doomed_ix], context="FACES")

        # Hole walls: parts of the Tripo holes had a short vertical wall (to z ~0.057) along their rim. With
        # the flat faces around them removed they stand as free vertical ribbons whose openings have no area
        # in XY; they would end up under the cap, so they are removed too (only below the top, near a hole).
        ribbons = []
        for _round in range(16):
            vertical = [lp for lp in ordered_boundary_loops(bm)
                        if abs(xy_area_of(lp["verts"])) < cfg["horizontal_cap_min_area_m2"]]
            if not vertical:
                break
            doomed = {}
            for lp in vertical:
                vs = lp["verts"]
                for i, v in enumerate(vs):
                    edge = bm.edges.get((v, vs[(i + 1) % len(vs)]))
                    for f in (edge.link_faces if edge is not None else []):
                        doomed[f.index] = f
            for f in doomed.values():
                if is_flat(f) or any(v.co.z > top_z + tol for v in f.verts) or not near_hole(f):
                    raise RuntimeError("vertical opening next to a face that is not a hole wall: %s" %
                                       rv(f.calc_center_median(), 4))
            ribbons.append({"openings": len(vertical), "faces": len(doomed),
                            "area_cm2": r(sum(f.calc_area() for f in doomed.values()) * 1e4, 3),
                            "z_min_m": r(min(v.co.z for f in doomed.values() for v in f.verts), 5)})
            bmesh.ops.delete(bm, geom=list(doomed.values()), context="FACES")
        else:
            raise RuntimeError("hole-wall removal did not converge")

        # clean donor texels: flat top faces that stay, minus dirty (dilated) texels
        clean = np.zeros((width, width), dtype=bool)
        for f in bm.faces:
            if is_flat(f):
                rr, cc = face_cell_pixels(f, uv_layer, cell, size)
                clean[rr, cc] = True
        clean &= ~dirty

        caps, folds = [], []
        cap_zone = np.zeros((width, width), dtype=bool)
        for lp in ordered_boundary_loops(bm):
            if not lp["closed"]:
                raise RuntimeError("base cap loop is not closed (%d edges)" % lp["cycle_edges"])
            loop_verts = lp["verts"]
            xy_area = xy_area_of(loop_verts)
            if xy_area < cfg["horizontal_cap_min_area_m2"]:
                raise RuntimeError("cap loop is not a horizontal opening wound +Z (area %.3g m2)" % xy_area)
            raised, walls = {}, []
            for v in loop_verts:
                if v.co.z < top_z - low_tol:
                    raised[v.index] = bm.verts.new((v.co.x, v.co.y, top_z))
            top_ring = [raised.get(v.index, v) for v in loop_verts]
            for i, v in enumerate(loop_verts):
                w = loop_verts[(i + 1) % len(loop_verts)]
                if v.index in raised or w.index in raised:
                    ring = [v, w] + ([raised[w.index]] if w.index in raised else []) + \
                           ([raised[v.index]] if v.index in raised else [])
                    walls.append(bm.faces.new(ring))
            cap = bm.faces.new(top_ring)
            new_faces = [cap] + walls
            cap_no = len(caps) + 1
            for face in new_faces:
                face.material_index = 0
                face.smooth = smooth_default
                face[tag_layer] = cap_no
                face.normal_update()
                for loop in face.loops:
                    loop[uv_layer].uv = uv_of(loop.vert.co, face.normal)
            cap_up = cap.normal.z
            bmesh.ops.triangulate(bm, faces=new_faces, quad_method="BEAUTY", ngon_method="BEAUTY")
            tri = [f for f in bm.faces if f[tag_layer] == cap_no]
            for f in tri:
                f.normal_update()
                for loop in f.loops:
                    loop[cn_layer] = src_normal((0.0, 0.0, 1.0) if f.normal.z > 0.5 else f.normal)
            folds.extend(f for f in tri if f.normal.z < -0.5)
            cap_zone |= raster_faces(tri, uv_layer, cell, size)
            # UV scale 1 keeps the stone's texel density; if no clean area fits the footprint (+ bleed
            # margin), the cap UVs are scaled down about their centre (the flat-top stone is nearly uniform);
            # among the fitting areas the one closest in tone to the stone around the cap is taken
            placed = place_uvs(tri, uv_layer, cell, size, clean, feats, cfg, cfg["uv_scale_steps"])
            if placed is None:
                raise RuntimeError("no clean donor area on the base top for a cap of %d edges" % len(loop_verts))
            dcol, dr = placed["donor_shift_px"]
            shift_m = np.linalg.solve(affine[:2, :].T, np.array((dcol / size, -dr / size)))
            pts = [v.co for v in top_ring]
            horiz = [f for f in tri if f.normal.z > 0.5]
            wall_tris = [f for f in tri if -0.5 <= f.normal.z <= 0.5]
            caps.append({"loop_xy_area_cm2": r(xy_area * 1e4, 3),
                         "loop_edges": len(loop_verts), "cycle_edges": lp["cycle_edges"],
                         "cycle_against_winding_edges": lp["against_winding"],
                         "split_from_cycle": lp["split_from_cycle"],
                         "vertices_below_top": len(raised), "walls": len(walls),
                         "cap_normal_z_before_triangulate": r(cap_up, 4),
                         "triangles": len(tri), "fold_triangles": sum(1 for f in tri if f.normal.z < -0.5),
                         "cap_triangles_normal_z_min": r(min(f.normal.z for f in horiz), 4),
                         "cap_triangles_z_range_m": [r(min(v.co.z for f in horiz for v in f.verts), 6),
                                                     r(max(v.co.z for f in horiz for v in f.verts), 6)],
                         "wall_triangles": len(wall_tris),
                         "wall_triangles_normal_z_abs_max": r(max((abs(f.normal.z) for f in wall_tris), default=0.0), 4),
                         "centre_m": rv(sum(pts, Vector()) / len(pts), 4),
                         "size_xy_m": [r(max(p[i] for p in pts) - min(p[i] for p in pts), 4) for i in range(2)],
                         "cap_area_cm2": r(sum(f.calc_area() for f in horiz) * 1e4, 2),
                         "wall_area_cm2": r(sum(f.calc_area() for f in wall_tris) * 1e4, 3),
                         "uv_scale": placed["uv_scale"], "footprint_px": placed["footprint_px"],
                         "tone_target": placed["tone_target"], "tone_donor": placed["tone_donor"],
                         "donor_shift_px": [dcol, dr], "donor_shift_m_on_top": [r(c, 4) for c in shift_m]})
        if not folds:
            break
        add = set()
        for f in folds:
            for e in f.edges:
                for g in e.link_faces:
                    if g[tag_layer] == 0:
                        if not is_flat(g):
                            raise RuntimeError("cap fold next to a face that is not flat top: %s" %
                                               rv(g.calc_center_median(), 4))
                        add.add(g[orig_layer] - 1)
        fold_fixes.append({"fold_triangles": len(folds), "flat_faces_added": sorted(add),
                           "at_m": [rv(f.calc_center_median(), 4) for f in folds]})
        if not add - forced:
            raise RuntimeError("cap folds persist after removing their flat neighbours")
        forced |= add
        bm.free()
    else:
        raise RuntimeError("cap fold repair did not converge")

    # Kept flat faces near a hole that still sample the boot fringe (bronze texels) or the black hole
    # texels (long fan triangles reaching further than the region rule allows) get their UVs moved onto
    # clean stone as well, per edge-connected group; the geometry stays. UV seams appear at the group
    # borders (stone against stone).
    fcfg = cfg["fringe_reuv"]
    fringe = dilate(bronze, fcfg["bronze_dilate_px"]) | dilate(dark & cap_zone, cfg["mip_bleed_px"])
    picked = {}
    bm.faces.index_update()

    def in_top_chart(f):
        return all(np.hypot(*(np.array((l.vert.co.x, l.vert.co.y, 1.0)) @ affine - np.array(tuple(l[uv_layer].uv))))
                   * size <= cfg["affine_max_residual_px"] for l in f.loops)

    for f in bm.faces:
        if f[tag_layer] or not in_top_chart(f):
            continue
        if min(hole_xy.find((v.co.x, v.co.y, 0.0))[2] for v in f.verts) > reach:
            continue
        rr, cc = face_cell_pixels(f, uv_layer, cell, size)
        n = int(fringe[rr, cc].sum())
        if n >= fcfg["face_min_texels"]:
            picked[f.index] = n
    bm.faces.ensure_lookup_table()
    groups, seen = [], set()
    for start in sorted(picked):
        if start in seen:
            continue
        comp, stack = [], [start]
        seen.add(start)
        while stack:
            fi = stack.pop()
            comp.append(fi)
            for e in bm.faces[fi].edges:
                for g in e.link_faces:
                    if g.index in picked and g.index not in seen:
                        seen.add(g.index)
                        stack.append(g.index)
        groups.append(sorted(comp))
    fringe_groups = []
    for comp in groups:
        faces = [bm.faces[i] for i in comp]
        placed = place_uvs(faces, uv_layer, cell, size, clean, feats, cfg, fcfg["uv_scale_steps"])
        if placed is None:
            raise RuntimeError("no clean donor area for %d fringe faces" % len(faces))
        placed.update({"faces": len(faces), "fringe_texels_before": sum(picked[i] for i in comp),
                       "area_cm2": r(sum(f.calc_area() for f in faces) * 1e4, 3),
                       "centre_m": rv(sum((f.calc_center_median() for f in faces), Vector()) / len(faces), 4)})
        fringe_groups.append(placed)
    left = 0
    for f in bm.faces:
        if not f[tag_layer] and in_top_chart(f) and min(hole_xy.find((v.co.x, v.co.y, 0.0))[2] for v in f.verts) <= reach:
            rr, cc = face_cell_pixels(f, uv_layer, cell, size)
            left += int(fringe[rr, cc].sum())

    boundary_after = sum(1 for e in bm.edges if e.is_boundary)
    bm.faces.layers.int.remove(tag_layer)
    bm.faces.layers.int.remove(orig_layer)
    bm.to_mesh(mesh)
    bm.free()
    mesh.update()
    stone = tile[clean]
    removed_all = region | forced
    return {"holes_before": hole_info, "hole_boundary_edges_before": sum(len(h["verts"]) for h in holes),
            "affine_xy_to_uv": [rv(row, 6) for row in affine], "affine_max_residual_px": r(resid_px, 4),
            "texel_density_px_per_cm": r(math.sqrt(abs(np.linalg.det(affine[:2, :]))) * size / 100.0, 3),
            "dirty_rule": dc_cfg, "mip_bleed_px": cfg["mip_bleed_px"],
            "dark_unused_texels": int(dark.sum()), "bronze_texels": int(bronze.sum()),
            "region_max_distance_from_hole_m": reach, "smooth_faces": bool(smooth_default),
            "removed_flat_faces": len(removed_all), "removed_flat_faces_dirty_region": len(region),
            "removed_flat_faces_fold_repair": len(forced - region), "fold_repairs": fold_fixes,
            "removed_area_cm2": r(sum(face_area[i] for i in removed_all) * 1e4, 2),
            "removed_hole_walls": ribbons,
            "removed_dirty_texels": removed_dirty, "dirty_texels_left_on_kept_flat_faces_near_holes": remaining_dirty,
            "caps": caps, "boundary_edges_after": boundary_after,
            "fringe_reuv": {"rule": fcfg, "groups": fringe_groups, "faces": sum(g["faces"] for g in fringe_groups),
                            "fringe_texels_left_on_kept_top_chart_faces_touching_the_zone": left},
            "clean_donor_texels": int(clean.sum()),
            "clean_stone_median_rgb": [r(c, 4) for c in np.median(stone, axis=0)] if len(stone) else None}


def cap_soles(obj, cfg):
    """Close the open soles of a foot part (boundary loops entirely below z_max): flat fill, normal
    down, UVs a small non-degenerate rectangle inside the UV triangle of the loop's largest neighbour
    (sole-rim texels), corner normal = cap face normal (source frame = final frame: uniform figure scale)."""
    mesh = obj.data
    bm = bmesh.new()
    bm.from_mesh(mesh)
    uv_layer = bm.loops.layers.uv.active
    cn_layer = bm.loops.layers.float_vector.get(CN_ATTR)
    tag_layer = bm.faces.layers.int.new("um_cap_tag")
    smooth_default = Counter(f.smooth for f in bm.faces).most_common(1)[0][0]
    z_max = cfg["z_max_m"]
    loops = ordered_boundary_loops(bm, lambda e: max(v.co.z for v in e.verts) < z_max)
    out = []
    for lp in loops:
        if not lp["closed"] or lp["split_from_cycle"]:
            raise RuntimeError("sole loop is not a closed simple loop (%d edges) in %s" % (lp["cycle_edges"], obj.name))
        verts = lp["verts"]
        neighbours = []
        for i, v in enumerate(verts):
            edge = bm.edges.get((v, verts[(i + 1) % len(verts)]))
            neighbours.extend(edge.link_faces)

        def uv_area(f):
            p = [l[uv_layer].uv for l in f.loops][:3]
            return abs((p[1] - p[0]).cross(p[2] - p[0])) / 2.0

        src = max(sorted(neighbours, key=lambda f: f.index), key=uv_area)  # first max in index order
        tri = [l[uv_layer].uv.copy() for l in src.loops][:3]
        cen = (tri[0] + tri[1] + tri[2]) / 3
        inr = min(abs((tri[(i + 1) % 3] - tri[i]).orthogonal().normalized().dot(cen - tri[i])) for i in range(3))
        half = cfg["uv_rect_fraction_of_inradius"] * inr
        xs, ys = [v.co.x for v in verts], [v.co.y for v in verts]
        cx, cy = (min(xs) + max(xs)) / 2, (min(ys) + max(ys)) / 2
        ext = max(max(xs) - min(xs), max(ys) - min(ys)) / 2 or 1.0
        cap = bm.faces.new(verts)
        cap.material_index = 0
        cap.smooth = smooth_default
        cap.normal_update()
        cap[tag_layer] = len(out) + 1
        down = cap.normal.z
        for loop in cap.loops:
            loop[uv_layer].uv = (cen.x + (loop.vert.co.x - cx) / ext * half, cen.y + (loop.vert.co.y - cy) / ext * half)
        bmesh.ops.triangulate(bm, faces=[cap], quad_method="BEAUTY", ngon_method="BEAUTY")
        tris = [f for f in bm.faces if f[tag_layer] == len(out) + 1]
        for f in tris:
            f.normal_update()
            for loop in f.loops:
                loop[cn_layer] = tuple(f.normal)
        pts = [v.co for v in verts]
        out.append({"loop_edges": len(verts), "against_winding_edges": lp["against_winding"],
                    "normal_z_before_triangulate": r(down, 4), "triangles": len(tris),
                    "triangles_normal_z_max": r(max(f.normal.z for f in tris), 4),
                    "centre_m": rv(sum(pts, Vector()) / len(pts), 4),
                    "size_xy_m": [r(max(xs) - min(xs), 4), r(max(ys) - min(ys), 4)],
                    "z_range_m": [r(min(p.z for p in pts), 5), r(max(p.z for p in pts), 5)],
                    "uv_rect_centre": rv(cen, 6), "uv_rect_half_extent": r(half, 6)})
    low_after = sum(1 for e in bm.edges if e.is_boundary and max(v.co.z for v in e.verts) < z_max)
    bm.faces.layers.int.remove(tag_layer)
    bm.to_mesh(mesh)
    bm.free()
    mesh.update()
    return {"caps": out, "low_boundary_edges_after": low_after}


def cap_loops_component(obj, part_index, cfg, xform):
    """Fan-fill open boundary loops of one part. Loops are connected components of the boundary-edge graph
    (robust to non-manifold boundary vertices, where a chain walk stops early) whose centroid lies within
    cfg["tolerance_m"] (source frame, scaled) of a listed source point. The loop vertices are ordered by angle
    around the centroid in the loop's best-fit plane and fanned to a new centre vertex. Every cap corner gets the
    UV of the loop corner nearest to the loop's mean UV (one texel of the part's own island next to the opening:
    a flat colour, zero UV area, so the cap overlaps no other island); corner normals (captured attribute) = the
    plane normal pointing away from the part centroid. Reports planarity and the largest angular gap (a
    star-shaped ring has < 90 deg)."""
    mesh = obj.data
    s = xform[0]
    bm = bmesh.new()
    bm.from_mesh(mesh)
    bm.faces.ensure_lookup_table()
    uv_layer = bm.loops.layers.uv.active
    cn_layer = bm.loops.layers.float_vector.get(CN_ATTR)
    part_layer = bm.faces.layers.int.get(PART_ATTR)
    part_centre = sum((f.calc_center_median() for f in bm.faces), Vector()) / len(bm.faces)
    parent = {}

    def find(v):
        while parent[v] is not v:
            parent[v] = parent[parent[v]]
            v = parent[v]
        return v

    for e in bm.edges:
        if e.is_boundary:
            a, b = e.verts
            parent.setdefault(a, a)
            parent.setdefault(b, b)
            ra, rb = find(a), find(b)
            if ra is not rb:
                parent[ra] = rb
    comps = defaultdict(list)
    for v in parent:
        comps[find(v)].append(v)
    targets = [to_final_point(pt, "source", xform) for pt in cfg["loops_source_centres"]]
    tol = cfg["tolerance_m"] * s
    caps, used = [], set()
    for comp in sorted(comps.values(), key=lambda c: -len(c)):
        if len(comp) < cfg["min_vertices"]:
            continue
        centre = sum((v.co for v in comp), Vector()) / len(comp)
        hit = next((k for k, t in enumerate(targets) if (centre - t).length <= tol and k not in used), None)
        if hit is None:
            continue
        radius_sel = (cfg.get("select_radius_m") or [None] * len(targets))[hit]
        dropped_branch = 0
        if radius_sel:
            keep = [v for v in comp if (v.co - targets[hit]).length <= radius_sel * s]
            dropped_branch = len(comp) - len(keep)
            comp = keep
            centre = sum((v.co for v in comp), Vector()) / len(comp)
        pts = np.array([tuple(v.co) for v in comp])
        c0 = pts.mean(axis=0)
        _u, _s, vt = np.linalg.svd(pts - c0)
        e1, e2, normal = Vector(vt[0]), Vector(vt[1]), Vector(vt[2])
        if normal.dot(centre - part_centre) < 0:
            normal.negate()
        ring = sorted(comp, key=lambda v: math.atan2((v.co - centre).dot(e2), (v.co - centre).dot(e1)))
        angles = sorted(math.atan2((v.co - centre).dot(e2), (v.co - centre).dot(e1)) for v in comp)
        gaps = [angles[i + 1] - angles[i] for i in range(len(angles) - 1)] + [2 * math.pi - (angles[-1] - angles[0])]
        radius = float(np.linalg.norm(pts - c0, axis=1).mean())
        planar = float(np.abs((pts - c0) @ np.array(normal)).max())
        vuv = {}
        for v in comp:
            for loop in v.link_loops:
                vuv[v] = loop[uv_layer].uv.copy()
                break
        mean_uv = sum(vuv.values(), Vector((0.0, 0.0))) / len(vuv)
        cuv = min(vuv.values(), key=lambda q: ((q - mean_uv).length, q.x, q.y)).copy()
        cv = bm.verts.new(centre)
        new = 0
        n = len(ring)
        for i in range(n):
            a, b = ring[i], ring[(i + 1) % n]
            if bm.faces.get((a, b, cv)) is not None:
                continue
            face = bm.faces.new((a, b, cv))
            face.material_index = 0
            face[part_layer] = part_index
            face.normal_update()
            if face.normal.dot(normal) < 0:
                face.normal_flip()
            for loop in face.loops:
                loop[uv_layer].uv = cuv  # one texel for the whole cap: no UV area, no overlap with other islands
                loop[cn_layer] = normal
            new += 1
        used.add(hit)
        caps.append({"target_source": cfg["loops_source_centres"][hit], "loop_vertices": n, "triangles": new,
                     "centre_m": rv(centre, 5), "normal": rv(normal, 4), "mean_radius_m": r(radius, 5),
                     "max_off_plane_m": r(planar, 5), "max_angular_gap_deg": r(math.degrees(max(gaps)), 2),
                     "branch_vertices_left_open": dropped_branch})
    bm.to_mesh(mesh)
    bm.free()
    mesh.update()
    return caps
