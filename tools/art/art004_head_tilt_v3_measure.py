"""Measure the Medusa head-tilt v3 FBX against v2 without editing any source.

Blender 5.2, from the repository root:

  blender --background --factory-startup --python tools/art/art004_head_tilt_v3_measure.py

Reads the committed medusa.blend and the two saved variant FBXs; never saves a
.blend or FBX. Writes only new files into
docs/game-design/evidence/ART-004/head-tilt-v3-probe-2026-09-28/:
blender-measurements.json, blender-id-*.png (flat part-ID renders) and
blender-tex-*.png (Workbench texture close-ups). These are Blender diagnostic
renders, not UE PBR frames and not art acceptance.
"""

import hashlib
import json
import math
from pathlib import Path

import bpy
import numpy as np
from mathutils import Matrix, Vector
from mathutils.bvhtree import BVHTree
from mathutils.kdtree import KDTree


ROOT = Path(__file__).resolve().parents[2]
ASSET = ROOT / "blender/ASSET-MEDUSA-001"
BLEND = ASSET / "medusa.blend"
ATLAS = json.loads((ASSET / "atlas-report.json").read_text())
V2 = ASSET / "variants/face-section-neck-v2/SK_Medusa_FaceSectionNeck_v2.fbx"
V3 = ASSET / "variants/head-tilt-v3/SK_Medusa_HeadTilt_v3.fbx"
OUT = ROOT / "docs/game-design/evidence/ART-004/head-tilt-v3-probe-2026-09-28"
EXPECTED_SHA = {
    "medusa.blend": "2a2534f89093e2a296d34e5b4da41290f1549109d6bc2ef4b1ba29ca978ed903",
    "v2": "bd125c6bbeb2559b28f6fc4908a1790e0d05fd572b128bd9188c2daeea046592",
    "v3": "b9cea0fe05071b07732b8d72ecc75b074c366bc665679c378cd4e397e1f822a2",
}
# Parameters of the v3 export (Artifacts/ART004Face/SK_Medusa_HeadTiltProbe.json).
# The reproduction check below proves them against the saved FBX.
TILT_DEG = -15.0
PIVOT_M = Vector((0.0, 0.0, 0.385))
MOVED_PARTS = ("tripo_part_1", "tripo_part_10", "tripo_part_14")
PART_LABEL = {"tripo_part_1": "crown", "tripo_part_10": "face",
              "tripo_part_14": "neck_back", "tripo_part_3": "shoulder_collar",
              "tripo_part_7": "quiver"}
UU = 100.0  # source metres -> UE uu (cm)


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def r(value, digits=3):
    return round(float(value), digits)


def mesh_arrays(mesh):
    n = len(mesh.vertices)
    co = np.empty(n * 3)
    mesh.vertices.foreach_get("co", co)
    loops = np.empty(len(mesh.loops), dtype=np.int64)
    mesh.loops.foreach_get("vertex_index", loops)
    starts = np.empty(len(mesh.polygons), dtype=np.int64)
    totals = np.empty(len(mesh.polygons), dtype=np.int64)
    mesh.polygons.foreach_get("loop_start", starts)
    mesh.polygons.foreach_get("loop_total", totals)
    mats = np.empty(len(mesh.polygons), dtype=np.int64)
    mesh.polygons.foreach_get("material_index", mats)
    uv = np.empty(len(mesh.loops) * 2)
    mesh.uv_layers.active.data.foreach_get("uv", uv)
    normals = np.empty(len(mesh.loops) * 3)
    mesh.corner_normals.foreach_get("vector", normals)
    return {"co": co.reshape(-1, 3), "loops": loops, "starts": starts, "totals": totals,
            "mats": mats, "uv": uv.reshape(-1, 2), "normals": normals.reshape(-1, 3),
            "slots": len(mesh.materials)}


def read_fbx(path):
    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.ops.import_scene.fbx(filepath=str(path), use_custom_normals=True)
    meshes = {obj.name: mesh_arrays(obj.data) for obj in bpy.data.objects if obj.type == "MESH"}
    arms = [obj for obj in bpy.data.objects if obj.type == "ARMATURE"]
    assert len(arms) == 1
    bones = {bone.name: {"head_uu": [r(v, 4) for v in bone.head_local],
                         "tail_uu": [r(v, 4) for v in bone.tail_local],
                         "parent": bone.parent.name if bone.parent else None}
             for bone in arms[0].data.bones}
    return meshes, bones


def part_polygons(mesh):
    uv = mesh.uv_layers.active.data
    label = np.full(len(mesh.polygons), "unassigned", dtype=object)
    for name, cell in ATLAS["cells"].items():
        u_min = (cell["x"] + cell["inset"]) / 2048
        u_max = (cell["x"] + cell["cell"] - cell["inset"]) / 2048
        v_min = 1 - (cell["y_top"] + cell["cell"] - cell["inset"]) / 2048
        v_max = 1 - (cell["y_top"] + cell["inset"]) / 2048
        for poly in mesh.polygons:
            if all(u_min <= uv[loop].uv.x <= u_max and v_min <= uv[loop].uv.y <= v_max
                   for loop in poly.loop_indices):
                label[poly.index] = name
    return label


def rotation():
    return Matrix.Rotation(math.radians(TILT_DEG), 3, "X")


def tilt(co_m, moved_vertices):
    rot = np.array(rotation())
    pivot = np.array(PIVOT_M)
    out = co_m.copy()
    idx = np.array(sorted(moved_vertices))
    out[idx] = (out[idx] - pivot) @ rot.T + pivot
    return out


def poly_vertex_lists(arrays):
    return [arrays["loops"][s:s + t].tolist() for s, t in zip(arrays["starts"], arrays["totals"])]


def compare_fbx(v2, v3):
    """Structural diff of the two saved FBX files, in FBX data units (uu)."""
    out = {}
    rot = np.array(rotation())
    for name in sorted(v2):
        a, b = v2[name], v3[name]
        same_topology = (np.array_equal(a["loops"], b["loops"]) and
                         np.array_equal(a["starts"], b["starts"]))
        disp = np.linalg.norm(b["co"] - a["co"], axis=1)
        moved = disp > 1e-4
        polys = poly_vertex_lists(a)
        moved_poly = np.array([moved[p].all() for p in polys])
        partial_poly = np.array([moved[p].any() and not moved[p].all() for p in polys])
        loop_poly = np.repeat(np.arange(len(polys)), a["totals"])
        moved_loops = moved_poly[loop_poly]
        static_normal_err = (np.abs(b["normals"][~moved_loops] - a["normals"][~moved_loops]).max()
                             if (~moved_loops).any() else 0.0)
        rotated = a["normals"][moved_loops] @ rot.T
        rotated_normal_err = (np.abs(b["normals"][moved_loops] - rotated).max()
                              if moved_loops.any() else 0.0)
        out[name] = {
            "vertices": int(len(a["co"])), "polygons": int(len(polys)),
            "triangles": int(sum(len(p) - 2 for p in polys)),
            "material_slots_v2": a["slots"], "material_slots_v3": b["slots"],
            "same_winding_and_topology": bool(same_topology),
            "uv_max_abs_diff": r(np.abs(a["uv"] - b["uv"]).max(), 7),
            "material_index_equal": bool(np.array_equal(a["mats"], b["mats"])),
            "moved_vertices": int(moved.sum()),
            "max_displacement_uu": r(disp.max(), 4),
            "moved_polygons": int(moved_poly.sum()),
            "partially_moved_polygons": int(partial_poly.sum()),
            "static_corner_normal_max_abs_diff": r(static_normal_err, 5),
            "moved_corner_normal_vs_rotated_v2_max_abs_diff": r(rotated_normal_err, 5),
            "bbox_v2_uu": [[r(a["co"][:, i].min()), r(a["co"][:, i].max())] for i in range(3)],
            "bbox_v3_uu": [[r(b["co"][:, i].min()), r(b["co"][:, i].max())] for i in range(3)],
        }
    return out


def overlaps(co, polys, group_a, group_b, labels, seam_a=frozenset(), seam_b=frozenset()):
    """Intersecting polygon pairs between two polygon groups.

    Pairs that share a vertex, or that touch only through a v2 seam (a moved
    vertex coincident with a static vertex), are skipped for both variants so
    that opening a seam is not counted as "fewer intersections".
    """
    ta = BVHTree.FromPolygons(co.tolist(), [polys[i] for i in group_a])
    tb = BVHTree.FromPolygons(co.tolist(), [polys[i] for i in group_b])
    pairs = {}
    count = 0
    for ia, ib in ta.overlap(tb):
        pa, pb = group_a[ia], group_b[ib]
        if set(polys[pa]) & set(polys[pb]):
            continue
        if seam_a.intersection(polys[pa]) and seam_b.intersection(polys[pb]):
            continue
        count += 1
        key = PART_LABEL.get(labels[pa], labels[pa]) + "|" + PART_LABEL.get(labels[pb], labels[pb])
        pairs[key] = pairs.get(key, 0) + 1
    return count, dict(sorted(pairs.items(), key=lambda item: -item[1]))


def nearest_clearance(co_moved, tree):
    best = math.inf
    for p in co_moved:
        hit = tree.find_nearest(Vector(p))
        if hit[0] is not None:
            best = min(best, hit[3])
    return best


def source_analysis():
    bpy.ops.wm.open_mainfile(filepath=str(BLEND))
    body = bpy.data.objects["SK_Medusa_Body"]
    bow = bpy.data.objects["SK_Medusa_Bow"]
    arm = bpy.data.objects["SKEL_Medusa"]
    mesh = body.data
    labels = part_polygons(mesh)
    polys = [list(p.vertices) for p in mesh.polygons]
    part_polys = {name: [i for i, lab in enumerate(labels) if lab == name]
                  for name in sorted(set(labels))}
    counts = {name: len(v) for name, v in part_polys.items()}
    assert counts["tripo_part_1"] == 2633 and counts["tripo_part_10"] == 587
    assert counts["tripo_part_14"] == 480
    moved_polys = sorted(i for name in MOVED_PARTS for i in part_polys[name])
    moved_set = set(moved_polys)
    static_polys = [i for i in range(len(polys)) if i not in moved_set]
    moved_v = {v for i in moved_polys for v in polys[i]}
    static_v = {v for i in static_polys for v in polys[i]}
    shared_v = moved_v & static_v
    co_m = np.array([v.co[:] for v in mesh.vertices])
    co2 = co_m * UU
    co3 = tilt(co_m, moved_v) * UU

    # Weights: all moved vertices must follow `head` only, otherwise the static
    # tilt would fight the skin.
    assert mesh.shape_keys is None, "Shape keys would bypass the vertex edit"
    head_index = body.vertex_groups["head"].index
    weight_report = {}
    for name in MOVED_PARTS + ("tripo_part_3", "tripo_part_7", "tripo_part_0"):
        verts = {v for i in part_polys[name] for v in polys[i]}
        head_only = 0
        groups = {}
        for v in verts:
            active = [g for g in mesh.vertices[v].groups if g.weight > 1e-6]
            if len(active) == 1 and active[0].group == head_index and active[0].weight > .999:
                head_only += 1
            for g in active:
                key = body.vertex_groups[g.group].name
                groups[key] = groups.get(key, 0) + 1
        weight_report[PART_LABEL.get(name, name)] = {
            "vertices": len(verts), "head_only_vertices": head_only, "bone_groups": groups}

    # Seams: static vertices that coincide (<=0.02 uu) with moved vertices in v2.
    vertex_label = {}
    for i in static_polys:
        for v in polys[i]:
            vertex_label.setdefault(v, labels[i])
    static_list = sorted(static_v - shared_v)
    tree = KDTree(len(static_list))
    for k, v in enumerate(static_list):
        tree.insert(Vector(co2[v]), k)
    tree.balance()
    seam, near = {}, {}
    seam_moved, seam_static = set(), set()
    for v in sorted(moved_v - shared_v):
        for _co, k, dist in tree.find_range(Vector(co2[v]), 0.5):
            s_v = static_list[k]
            gap3 = float(np.linalg.norm(co3[v] - co3[s_v]))
            key = PART_LABEL.get(vertex_label[s_v], vertex_label[s_v])
            if dist <= 0.02:
                seam.setdefault(key, []).append((float(dist), gap3))
                seam_moved.add(v)
                seam_static.add(s_v)
            else:
                near.setdefault(key, []).append((float(dist), gap3))
    seam_report = {key: {"pairs": len(vals), "v2_max_uu": r(max(a for a, _ in vals), 4),
                         "v3_gap_max_uu": r(max(b for _, b in vals)),
                         "v3_gap_mean_uu": r(sum(b for _, b in vals) / len(vals))}
                   for key, vals in seam.items()}
    near_report = {key: {"pairs": len(vals),
                         "v2_mean_uu": r(sum(a for a, _ in vals) / len(vals)),
                         "v3_mean_uu": r(sum(b for _, b in vals) / len(vals)),
                         "v3_max_uu": r(max(b for _, b in vals))}
                   for key, vals in near.items()}
    # Static polygons that share a vertex with a moved polygon get stretched.
    stretched = []
    for i in static_polys:
        if shared_v.intersection(polys[i]):
            ring = polys[i] + polys[i][:1]
            ratio = max(np.linalg.norm(co3[a] - co3[b]) / max(1e-9, np.linalg.norm(co2[a] - co2[b]))
                        for a, b in zip(ring, ring[1:]))
            stretched.append(ratio)
    stretch_report = {"static_polygons_with_moved_vertex": len(stretched),
                      "max_edge_length_ratio": r(max(stretched), 3) if stretched else None}

    # Rigid displacement of moved vertices.
    disp = np.linalg.norm(co3 - co2, axis=1)
    by_part = {}
    for name in MOVED_PARTS:
        verts = sorted({v for i in part_polys[name] for v in polys[i]})
        by_part[PART_LABEL[name]] = {
            "vertices": len(verts), "max_displacement_uu": r(disp[verts].max()),
            "mean_displacement_uu": r(disp[verts].mean()),
            "centroid_v2_uu": [r(x) for x in co2[verts].mean(axis=0)],
            "centroid_v3_uu": [r(x) for x in co3[verts].mean(axis=0)],
            "bbox_v2_uu": [[r(co2[verts][:, a].min()), r(co2[verts][:, a].max())] for a in range(3)],
            "bbox_v3_uu": [[r(co3[verts][:, a].min()), r(co3[verts][:, a].max())] for a in range(3)],
        }

    # Rest-pose interpenetration (moved parts vs everything else, plus bow).
    bow_co = np.array([v.co[:] for v in bow.data.vertices]) * UU
    bow_polys = [list(p.vertices) for p in bow.data.polygons]
    rest = {}
    for tag, co in (("v2", co2), ("v3", co3)):
        count, pairs = overlaps(co, polys, moved_polys, static_polys, labels,
                                frozenset(seam_moved), frozenset(seam_static))
        tb = BVHTree.FromPolygons(bow_co.tolist(), bow_polys)
        tm = BVHTree.FromPolygons(co.tolist(), [polys[i] for i in moved_polys])
        quiver = [i for i in part_polys["tripo_part_7"]]
        tq = BVHTree.FromPolygons(co.tolist(), [polys[i] for i in quiver])
        moved_co = co[sorted(moved_v)]
        rest[tag] = {"moved_vs_static_intersections": count, "by_part_pair": pairs,
                     "moved_vs_bow_intersections": len(tm.overlap(tb)),
                     "min_clearance_moved_to_bow_uu": r(nearest_clearance(moved_co, tb)),
                     "min_clearance_crown_to_quiver_uu": r(nearest_clearance(
                         co[sorted({v for i in part_polys["tripo_part_1"] for v in polys[i]})], tq))}

    report = {
        "source_blend_sha256": sha(BLEND),
        "part_polygon_counts": counts,
        "moved_parts": list(MOVED_PARTS),
        "moved_vertices": len(moved_v),
        "vertices_shared_between_moved_and_static_polygons": len(shared_v),
        "tilt_deg_about_x": TILT_DEG, "pivot_uu": [r(x * UU) for x in PIVOT_M],
        "head_bone_head_uu": [r(x * UU) for x in arm.data.bones["head"].head_local],
        "head_bone_tail_uu": [r(x * UU) for x in arm.data.bones["head"].tail_local],
        "weights": weight_report,
        "seam_coincident_pairs_v2_le_0p02uu": seam_report,
        "seam_near_pairs_v2_0p02_to_0p5uu": near_report,
        "stretched_static_polygons": stretch_report,
        "moved_part_displacement": by_part,
        "rest_pose_interpenetration": rest,
        "body_bbox_v2_uu": [[r(co2[:, a].min()), r(co2[:, a].max())] for a in range(3)],
        "body_bbox_v3_uu": [[r(co3[:, a].min()), r(co3[:, a].max())] for a in range(3)],
        "bow_bbox_uu": [[r(bow_co[:, a].min()), r(bow_co[:, a].max())] for a in range(3)],
    }
    return (report, co_m, moved_v, labels, polys, part_polys, moved_polys,
            frozenset(seam_moved), frozenset(seam_static))


def posed_analysis(co_m, moved_v, labels, polys, part_polys, moved_polys, seam_moved, seam_static):
    """Draft clips only: diagnostic interpenetration, not animation acceptance."""
    body = bpy.data.objects["SK_Medusa_Body"]
    bow = bpy.data.objects["SK_Medusa_Bow"]
    arm = bpy.data.objects["SKEL_Medusa"]
    arm.data.pose_position = "POSE"
    head_parts = set(MOVED_PARTS) | {"tripo_part_3"}
    other_polys = [i for i, lab in enumerate(labels) if lab not in head_parts]
    scene = bpy.context.scene
    result = {}
    original = co_m.reshape(-1).copy()
    variants = {"v2": original, "v3": tilt(co_m, moved_v).reshape(-1)}
    for action in sorted(bpy.data.actions, key=lambda a: a.name):
        start, end = (int(x) for x in action.frame_range)
        arm.animation_data.action = action
        per = {}
        for tag, flat in variants.items():
            body.data.vertices.foreach_set("co", flat)
            body.data.update()
            counts, bow_hits, worst = [], [], {}
            for frame in range(start, end + 1):
                scene.frame_set(frame)
                graph = bpy.context.evaluated_depsgraph_get()
                ev = body.evaluated_get(graph)
                em = ev.to_mesh()
                co = np.empty(len(em.vertices) * 3)
                em.vertices.foreach_get("co", co)
                ev.to_mesh_clear()
                co = co.reshape(-1, 3) * UU
                bev = bow.evaluated_get(graph)
                bm = bev.to_mesh()
                bco = np.empty(len(bm.vertices) * 3)
                bm.vertices.foreach_get("co", bco)
                bpolys = [list(p.vertices) for p in bm.polygons]
                bev.to_mesh_clear()
                count, pairs = overlaps(co, polys, moved_polys, other_polys, labels,
                                        seam_moved, seam_static)
                counts.append(count)
                for key, value in pairs.items():
                    worst[key] = max(worst.get(key, 0), value)
                tb = BVHTree.FromPolygons((bco.reshape(-1, 3) * UU).tolist(), bpolys)
                tm = BVHTree.FromPolygons(co.tolist(), [polys[i] for i in moved_polys])
                bow_hits.append(len(tm.overlap(tb)))
            per[tag] = {"frames": end - start + 1,
                        "moved_vs_non_head_intersections_max": int(max(counts)),
                        "moved_vs_non_head_intersections_mean": r(sum(counts) / len(counts), 1),
                        "worst_frame_by_part_pair": worst,
                        "moved_vs_bow_intersections_max": int(max(bow_hits))}
        result[action.name] = per
    body.data.vertices.foreach_set("co", original)
    body.data.update()
    arm.animation_data.action = None
    return result


PALETTE = {  # pure colours survive the Standard view transform exactly
    "face": (1, 0, 0), "crown": (0, 1, 0), "neck_back": (1, 1, 0),
    "shoulder_collar": (0, 1, 1), "quiver": (1, 1, 1), "body": (0, 0, 0),
    "bow": (0, 0, 1), "base": (1, 0, 1),
}


def paint(obj, colors_per_poly):
    mesh = obj.data
    attr = mesh.color_attributes.new("A1_PartID", "BYTE_COLOR", "CORNER")
    data = []
    for poly in mesh.polygons:
        rgb = colors_per_poly(poly.index)
        for _ in poly.loop_indices:
            data.extend((*rgb, 1.0))
    attr.data.foreach_set("color", data)
    mesh.color_attributes.active_color = attr
    mesh.color_attributes.render_color_index = mesh.color_attributes.find("A1_PartID")


def look_at(cam, location, target):
    cam.location = location
    direction = Vector(target) - Vector(location)
    cam.rotation_euler = direction.to_track_quat("-Z", "Y").to_euler()


def d10(distance_uu, rear=False):
    d = distance_uu / UU
    y = -d * math.cos(math.radians(55))
    if rear:
        y = -y
    return (0.0, y, .29 + d * math.sin(math.radians(55))), (0.0, 0.0, .29)


def k1_distance_uu():
    # Same fit expression as art004_face_static_ue_capture.py d10-k1.
    half_h = math.tan(math.radians(35 / 2))
    half_v = half_h / (16 / 9)
    need_v = (300 * math.sin(math.radians(55)) + 60) / half_v
    need_h = (250 + 60) / half_h
    return max(need_v, need_h) * 1.12


def classify(path):
    image = bpy.data.images.load(str(path))
    w, h = image.size
    px = np.array(image.pixels[:]).reshape(h, w, 4)[::-1]
    bpy.data.images.remove(image)
    alpha = px[..., 3] > .5
    rgb = np.round(px[..., :3]).astype(int)
    classes = {}
    for name, color in PALETTE.items():
        classes[name] = alpha & np.all(rgb == np.array(color), axis=2)
    return classes, alpha


def components(mask):
    """4-connected component sizes of a small boolean mask (pure Python)."""
    h, w = mask.shape
    seen = np.zeros_like(mask)
    sizes = []
    for y0, x0 in zip(*np.nonzero(mask)):
        if seen[y0, x0]:
            continue
        stack = [(y0, x0)]
        seen[y0, x0] = True
        size = 0
        while stack:
            y, x = stack.pop()
            size += 1
            for ny, nx in ((y + 1, x), (y - 1, x), (y, x + 1), (y, x - 1)):
                if 0 <= ny < h and 0 <= nx < w and mask[ny, nx] and not seen[ny, nx]:
                    seen[ny, nx] = True
                    stack.append((ny, nx))
        sizes.append(size)
    return sorted(sizes, reverse=True)


def crown_metrics(classes, alpha):
    crown = classes["crown"]
    ys, xs = np.nonzero(crown)
    if not len(ys):
        return {"crown_px": 0}
    top, bottom = ys.min(), ys.max()
    band_end = top + max(1, int(.4 * (bottom - top + 1)))
    runs, bg_gaps, other_gaps = [], 0, 0
    for y in range(top, band_end):
        row = crown[y]
        cols = np.nonzero(row)[0]
        if not len(cols):
            continue
        # A run break needs at least 2 non-crown pixels, so 1-px aliasing is ignored.
        runs.append(1 + int(((np.diff(cols) - 1) >= 2).sum()))
        span = slice(cols.min(), cols.max() + 1)
        bg_gaps += int((~alpha[y, span]).sum())
        other_gaps += int((alpha[y, span] & ~row[span]).sum())
    band = crown[top:band_end]
    comps = [s for s in components(band) if s >= 6]
    return {"crown_px": int(crown.sum()), "crown_bbox_px": [int(xs.min()), int(top), int(xs.max()), int(bottom)],
            "top_band_rows": int(band_end - top),
            "top_band_runs_mean": r(sum(runs) / max(1, len(runs)), 2),
            "top_band_runs_max": int(max(runs) if runs else 0),
            "top_band_rows_with_3plus_runs": int(sum(1 for v in runs if v >= 3)),
            "top_band_background_gap_px": bg_gaps,
            "top_band_other_geometry_gap_px": other_gaps,
            "top_band_components_ge6px": len(comps),
            "top_band_component_sizes": comps[:12]}


def view_metrics(path):
    classes, alpha = classify(path)
    ys, xs = np.nonzero(alpha)
    out = {"figure_px": int(alpha.sum()),
           "figure_bbox_px": [int(xs.min()), int(ys.min()), int(xs.max()), int(ys.max())],
           "class_px": {name: int(mask.sum()) for name, mask in classes.items()}}
    out.update(crown_metrics(classes, alpha))
    return out


def render_views(co_m, moved_v, labels, polys):
    body = bpy.data.objects["SK_Medusa_Body"]
    bow = bpy.data.objects["SK_Medusa_Bow"]
    base = bpy.data.objects["SM_Medusa_Base"]
    arm = bpy.data.objects["SKEL_Medusa"]
    arm.animation_data.action = None
    arm.data.pose_position = "REST"
    for obj in bpy.data.objects:
        if obj.type in {"LIGHT", "CAMERA"}:
            obj.hide_render = True
    scene = bpy.context.scene
    scene.render.engine = "BLENDER_WORKBENCH"
    scene.render.film_transparent = True
    scene.render.image_settings.file_format = "PNG"
    scene.render.image_settings.color_mode = "RGBA"
    scene.view_settings.view_transform = "Standard"
    scene.view_settings.look = "None"
    scene.display.render_aa = "OFF"
    scene.render.dither_intensity = 0
    shading = scene.display.shading
    for flag in ("show_cavity", "show_object_outline", "show_shadows",
                 "show_specular_highlight", "show_xray"):
        if hasattr(shading, flag):
            setattr(shading, flag, False)
    cam_data = bpy.data.cameras.new("A1_Camera")
    cam = bpy.data.objects.new("A1_Camera", cam_data)
    scene.collection.objects.link(cam)
    scene.camera = cam
    cam_data.sensor_fit = "HORIZONTAL"

    label_color = {"tripo_part_1": "crown", "tripo_part_10": "face", "tripo_part_14": "neck_back",
                   "tripo_part_3": "shoulder_collar", "tripo_part_7": "quiver"}
    paint(body, lambda i: PALETTE[label_color.get(labels[i], "body")])
    paint(bow, lambda i: PALETTE["bow"])
    paint(base, lambda i: PALETTE["base"])

    k1 = k1_distance_uu()
    views = {
        "d10-k2-front-d300": ("persp", *d10(300)),
        "d10-k2-rear-d300": ("persp", *d10(300, rear=True)),
        "d10-k1scale-front": ("persp", *d10(k1)),
        "ortho-front": ("ortho", (0, -2, .3), (0, 0, .3)),
        "ortho-back": ("ortho", (0, 2, .3), (0, 0, .3)),
        "ortho-side-left": ("ortho", (2, 0, .3), (0, 0, .3)),
        "ortho-side-right": ("ortho", (-2, 0, .3), (0, 0, .3)),
    }
    original = co_m.reshape(-1).copy()
    variants = {"v2": original, "v3": tilt(co_m, moved_v).reshape(-1)}
    metrics = {}
    OUT.mkdir(parents=True, exist_ok=True)
    for tag, flat in variants.items():
        body.data.vertices.foreach_set("co", flat)
        body.data.update()
        shading.light = "FLAT"
        shading.color_type = "VERTEX"
        for view, (kind, loc, target) in views.items():
            if kind == "ortho":
                cam_data.type = "ORTHO"
                cam_data.ortho_scale = .62
                scene.render.resolution_x = scene.render.resolution_y = 1080
            else:
                cam_data.type = "PERSP"
                cam_data.angle = math.radians(35)
                scene.render.resolution_x, scene.render.resolution_y = 1920, 1080
            look_at(cam, loc, target)
            path = OUT / f"blender-id-{view}-{tag}.png"
            scene.render.filepath = str(path)
            bpy.ops.render.render(write_still=True)
            metrics.setdefault(view, {})[tag] = view_metrics(path)
            metrics[view]["camera"] = {"type": kind, "location_m": list(loc), "target_m": list(target),
                                       "horizontal_fov_deg": 35 if kind == "persp" else None}
        # Textured Workbench close-ups of the head/neck junction.
        shading.light = "STUDIO"
        shading.color_type = "TEXTURE"
        mat = body.data.materials[0]
        mat.node_tree.nodes.active = mat.node_tree.nodes["Image Texture"]
        cam_data.type = "ORTHO"
        cam_data.ortho_scale = .2
        scene.render.resolution_x = scene.render.resolution_y = 1024
        closeups = {"neck-rear34": ((.9, 1.2, .75), (-.02, .02, .41)),
                    "neck-side-right": ((-2, 0, .41), (-.02, 0, .41)),
                    "head-front": ((0, -2, .44), (-.02, 0, .44)),
                    "head-d10-front": (d10(300)[0], (-.02, 0, .44))}
        for view, (loc, target) in closeups.items():
            look_at(cam, loc, target)
            scene.render.filepath = str(OUT / f"blender-tex-{view}-{tag}.png")
            bpy.ops.render.render(write_still=True)
    body.data.vertices.foreach_set("co", original)
    body.data.update()
    return metrics, {"k1_distance_uu": r(k1, 1), "k2_distance_uu": 300,
                     "pitch_deg": -55, "horizontal_fov_deg": 35,
                     "target_z_uu": 29, "note": "Blender Workbench, flat part-ID colours, AA off; "
                     "UE uses the same D-10 geometry but different renderer, lights and materials."}


def main():
    hashes = {"medusa.blend": sha(BLEND), "v2": sha(V2), "v3": sha(V3)}
    assert hashes == EXPECTED_SHA, hashes
    v2_meshes, v2_bones = read_fbx(V2)
    v3_meshes, v3_bones = read_fbx(V3)
    fbx = compare_fbx(v2_meshes, v3_meshes)
    bones_equal = v2_bones == v3_bones
    (src, co_m, moved_v, labels, polys, part_polys, moved_polys,
     seam_moved, seam_static) = source_analysis()
    # Reproduction: v3 FBX positions == tilt(source) and v2 FBX == source.
    body2 = v2_meshes["SK_Medusa_Body"]["co"]
    body3 = v3_meshes["SK_Medusa_Body"]["co"]
    repro = {"v2_fbx_vs_source_max_uu": r(np.abs(body2 - co_m * UU).max(), 5),
             "v3_fbx_vs_tilted_source_max_uu": r(np.abs(body3 - tilt(co_m, moved_v) * UU).max(), 5)}
    assert repro["v3_fbx_vs_tilted_source_max_uu"] < .01, repro
    posed = posed_analysis(co_m, moved_v, labels, polys, part_polys, moved_polys,
                           seam_moved, seam_static)
    views, camera = render_views(co_m, moved_v, labels, polys)
    report = {
        "status": "measured_diagnostic_not_art_acceptance",
        "inputs_sha256": hashes,
        "fbx_structural_diff": fbx,
        "bones": {"count_v2": len(v2_bones), "count_v3": len(v3_bones),
                  "rest_pose_identical": bones_equal, "head": v3_bones.get("head"),
                  "weapon": v3_bones.get("weapon")},
        "reproduction_check": repro,
        "source_geometry": src,
        "draft_clip_interpenetration": posed,
        "blender_views": views,
        "blender_camera": camera,
    }
    OUT.mkdir(parents=True, exist_ok=True)
    path = OUT / "blender-measurements.json"
    path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("ART004_HEAD_TILT_V3_MEASURE_OK", path)


# Guarded so art004_head_tilt_v3_followup.py can import the helpers (added 2026-09-28,
# after the verified runs; `blender --python` still runs main() because __name__ == "__main__").
if __name__ == "__main__":
    main()
