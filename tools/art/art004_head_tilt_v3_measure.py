"""Measure the Medusa head-tilt v3 FBX against v2 without editing any source.

Blender 5.2, from the repository root:

  blender --background --factory-startup --python tools/art/art004_head_tilt_v3_measure.py

Reads the committed medusa.blend and the two saved variant FBXs; never saves a
.blend or FBX. Writes only new files into
docs/game-design/evidence/ART-004/head-tilt-v3-probe-2026-09-28/:
blender-measurements.json, blender-id-*.png (flat part-ID renders) and
blender-tex-*.png (Workbench texture close-ups). These are Blender diagnostic
renders, not UE PBR frames and not art acceptance.

v3.1 mode (added 2026-09-28, stage 3 T1.2; the v3 path above is unchanged):

  blender --background --factory-startup --python tools/art/art004_head_tilt_v3_measure.py -- --v31

measures v2, v3 and every variants/head-tilt-v31-*/SK_Medusa_HeadTilt_v31*.fbx with the same
methods plus the A1 junction zones (face / neck_back / crown x collar, numpy port
art004_junction_zones.py), the draft clips per frame, ray-escape orientation of all 15 parts,
UV stretch, normals/tangents and the Head socket; writes
docs/game-design/evidence/ART-004/head-tilt-v31-probe-2026-09-28/ (override: ART004_V31_MEASURE_OUT).
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


# =====================================================================================
# v3.1 mode (stage 3 T1.2, added 2026-09-28). Everything above is the v3 measurement and
# is not changed; without "--v31" the script still writes the v3 probe as before.
# =====================================================================================
import os  # noqa: E402
import sys  # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parent))
import art004_head_tilt_v31_field as field31  # noqa: E402
import art004_junction_zones as zones31  # noqa: E402

V31_OUT = Path(os.environ.get("ART004_V31_MEASURE_OUT") or
               ROOT / "docs/game-design/evidence/ART-004/head-tilt-v31-probe-2026-09-28")
BASE_FBX = ASSET / "export/SM_Medusa_Base.fbx"
FLIPPED_PARTS = {"v2": ("tripo_part_10", "tripo_part_14"), "v3": ("tripo_part_10", "tripo_part_14"),
                 "v31": ("tripo_part_10", "tripo_part_13", "tripo_part_14", "tripo_part_8")}
CHANGED_PARTS = ("tripo_part_1", "tripo_part_10", "tripo_part_14", "tripo_part_3", "tripo_part_7")
HANDS_ARMS = ("tripo_part_8", "tripo_part_9", "tripo_part_11", "tripo_part_12", "tripo_part_13")
FEATURE_Z_UU = 42.0  # facial features = face-part polygons with v2 centre z >= 42 uu (A1 definition)
ID_COLOUR = {"tripo_part_10": (1, 0, 0), "tripo_part_14": (1, 1, 0), "tripo_part_1": (0, 1, 0),
             "tripo_part_3": (0, 1, 1), "tripo_part_7": (1, 1, 1)}
BOW_COLOUR, THROAT_COLOUR = (0, 0, 1), (1, 0, 1)  # pure channels: byte colours are sRGB-encoded
HEAD_SOCKET_BONE_OFFSET_M = (0.0, 0.0, 0.04)  # game import: socket Head = bone head + (0,0,4) uu
V31_LABEL = dict(PART_LABEL, tripo_part_8="bow_arm", tripo_part_13="right_hand", tripo_part_4="bow",
                 tripo_part_2="base")


def _d(deg):
    return math.cos(math.radians(deg)), math.sin(math.radians(deg))


# The camera set of the A1 live review (art004_head_tilt_v3_mcp_review/blender/b4_idrender.py),
# figure at the origin: (type, camera, target, ortho scale | horizontal FOV, resolution).
V31_VIEWS = {
    "neck-front": ("O", (0, -2, .40), (-.02, 0, .40), .16, (1024, 1024)),
    "neck-front34L": ("O", (-1.41, -1.41, .40), (-.02, 0, .40), .16, (1024, 1024)),
    "neck-front34R": ("O", (1.41, -1.41, .40), (-.02, 0, .40), .16, (1024, 1024)),
    "neck-sideL": ("O", (2, 0, .40), (-.02, 0, .40), .16, (1024, 1024)),
    "neck-sideR": ("O", (-2, 0, .40), (-.02, 0, .40), .16, (1024, 1024)),
    "neck-rear": ("O", (0, 2, .40), (-.02, 0, .40), .16, (1024, 1024)),
    "neck-rear34L": ("O", (-1.41, 1.41, .40), (-.02, 0, .40), .16, (1024, 1024)),
    "neck-rear34R": ("O", (1.41, 1.41, .40), (-.02, 0, .40), .16, (1024, 1024)),
    "neck-front-low": ("P", (-.02, -.45, .30), (-.02, 0, .40), 35, (1600, 900)),
    "neck-top55": ("O", (0, -2 * _d(55)[0], .40 + 2 * _d(55)[1]), (-.02, 0, .40), .16, (1024, 1024)),
    "k2-front-d300": ("P", (0, -3 * _d(55)[0], .29 + 3 * _d(55)[1]), (0, 0, .29), 35, (1920, 1080)),
    "k2-rear-d300": ("P", (0, 3 * _d(55)[0], .29 + 3 * _d(55)[1]), (0, 0, .29), 35, (1920, 1080)),
}
# Views of the v3.1 thresholds (A1 act): front, 3/4 right, along the D-10 axis.
GATE_VIEWS = ("neck-front", "neck-front34R", "neck-top55")


def v31_sha_pixels(im):
    return hashlib.sha256(np.ascontiguousarray(im).tobytes()).hexdigest()


def v31_read_png(path):
    image = bpy.data.images.load(str(path))
    w, h = image.size
    buf = np.empty(w * h * 4, dtype=np.float32)
    image.pixels.foreach_get(buf)
    bpy.data.images.remove(image)
    return np.round(buf.reshape(h, w, 4)[::-1] * 255).astype(np.uint8)


def v31_paint(obj, colours, name):
    mesh = obj.data
    attr = mesh.color_attributes.get(name) or mesh.color_attributes.new(name, "BYTE_COLOR", "CORNER")
    data = np.zeros((len(mesh.loops), 4), dtype=np.float32)
    data[:, 3] = 1.0
    for poly, rgb in zip(mesh.polygons, colours):
        data[poly.loop_start:poly.loop_start + poly.loop_total, :3] = rgb
    attr.data.foreach_set("color", data.ravel())
    mesh.color_attributes.active_color = attr
    mesh.color_attributes.render_color_index = mesh.color_attributes.find(name)


def v31_render_setup(scene):
    scene.render.engine = "BLENDER_WORKBENCH"
    scene.render.film_transparent = True
    scene.render.image_settings.file_format = "PNG"
    scene.render.image_settings.color_mode = "RGBA"
    scene.view_settings.view_transform = "Standard"
    scene.view_settings.look = "None"
    scene.display.render_aa = "OFF"
    scene.render.dither_intensity = 0
    for name in dir(scene.render):  # no metadata -> byte-identical PNG on a rerun
        if name.startswith("use_stamp"):
            setattr(scene.render, name, False)
    shading = scene.display.shading
    shading.light = "FLAT"
    shading.color_type = "VERTEX"
    shading.show_backface_culling = True  # UE materials are one-sided
    for flag in ("show_cavity", "show_object_outline", "show_shadows", "show_specular_highlight", "show_xray"):
        if hasattr(shading, flag):
            setattr(shading, flag, False)
    cam = bpy.data.objects.get("V31_Cam")
    if cam is None:
        cam = bpy.data.objects.new("V31_Cam", bpy.data.cameras.new("V31_Cam"))
        scene.collection.objects.link(cam)
    scene.camera = cam
    cam.data.sensor_fit = "HORIZONTAL"
    return cam


def v31_view_metrics(im, band):
    zone = zones31.enclosed_gap(im, band)
    a = im[..., 3] > 127
    rgb = im[..., :3].astype(int)
    classes = {"face": (255, 0, 0), "throat_split": (255, 0, 255), "neck_back": (255, 255, 0),
               "crown": (0, 255, 0), "collar": (0, 255, 255), "quiver": (255, 255, 255),
               "bow": (0, 0, 255), "body": (0, 0, 0)}
    px = {k: int((a & (np.abs(rgb - np.array(c)).sum(axis=2) < 30)).sum()) for k, c in classes.items()}

    def compact(z):
        return {"zone_px": z["zone_px"], "enclosed_gap_px": z["enclosed_gap_px"],
                "junction_only_px": z["junction_only_px"], "components": z["components"],
                "largest_px": [c["px"] for c in z["largest"]],
                "largest_between_parts": [c["between_parts"] for c in z["largest"]]}
    return {"figure_px": int(a.sum()), "class_px": px,
            "face_x_collar": {"enclosed_gap_px": zone["enclosed_gap_px"], "components": zone["components"],
                              "largest_px": zone["largest"], "zone_px": zone["face_x_collar_zone_px"]},
            "neck_back_x_collar": compact(zone["rear_zones"]["neck_back_x_collar"]),
            "crown_x_collar": compact(zone["rear_zones"]["crown_x_collar"]),
            "pixels_sha256": v31_sha_pixels(im)}


def v31_render(tag, body, bow, labels, rest_z, out_dir, views=V31_VIEWS, split=True):
    """Flat part-ID renders with backface culling of `body` + `bow` (all other meshes hidden)."""
    scene = bpy.context.scene
    cam = v31_render_setup(scene)
    for obj in scene.objects:
        if obj.type in {"MESH", "CURVE", "EMPTY", "LIGHT"}:
            obj.hide_render = obj not in (body, bow)
    v31_paint(body, [ID_COLOUR.get(lab, (0, 0, 0)) for lab in labels], "V31_PartID")
    v31_paint(bow, [BOW_COLOUR] * len(bow.data.polygons), "V31_PartID")
    out_dir = Path(out_dir).resolve()  # Blender resolves a relative render path against the drive root
    out_dir.mkdir(parents=True, exist_ok=True)
    metrics = {}

    def shoot(kind, loc, tgt, p, res, path):
        cam.data.type = "ORTHO" if kind == "O" else "PERSP"
        if kind == "O":
            cam.data.ortho_scale = p
        else:
            cam.data.angle = math.radians(p)
        scene.render.resolution_x, scene.render.resolution_y = res
        look_at(cam, loc, tgt)
        scene.render.filepath = str(path)
        bpy.ops.render.render(write_still=True)
        return v31_read_png(path)

    for name, (kind, loc, tgt, p, res) in views.items():
        path = out_dir / f"id-cull-{name}-{tag}.png"
        metrics[name] = v31_view_metrics(shoot(kind, loc, tgt, p, res, path), 3 if name.startswith("k2-") else 40)
    if split:
        face = "tripo_part_10"
        colours = [THROAT_COLOUR if lab == face and rest_z[i] < FEATURE_Z_UU else ID_COLOUR.get(lab, (0, 0, 0))
                   for i, lab in enumerate(labels)]
        v31_paint(body, colours, "V31_PartIDSplit")
        kind, loc, tgt, p, res = V31_VIEWS["k2-front-d300"]
        im = shoot(kind, loc, tgt, p, res, out_dir / f"idsplit-k2-front-d300-{tag}.png")
        a = im[..., 3] > 127
        rgb = im[..., :3].astype(int)

        def count(c):
            return int((a & (np.abs(rgb - np.array(c)).sum(axis=2) < 30)).sum())
        metrics["idsplit-k2-front-d300"] = {
            "facial_features_z_ge_42_px": count((255, 0, 0)), "throat_z_lt_42_px": count((255, 0, 255)),
            "crown_px": count((0, 255, 0)), "quiver_px": count((255, 255, 255)), "bow_px": count((0, 0, 255)),
            "collar_px": count((0, 255, 255)), "pixels_sha256": v31_sha_pixels(im)}
        v31_paint(body, [ID_COLOUR.get(lab, (0, 0, 0)) for lab in labels], "V31_PartID")
    return metrics


# Textured Workbench close-ups (diagnostic look, not UE PBR): atlas BaseColor, studio light,
# one-sided (backface culling), 768 px JPEG q90. A5 asks for the hands and the bow arm from
# the front and from behind; the rest shows the head/neck junction and the quiver lean.
V31_TEX_VIEWS = {
    "tex-head-d10": ((0, -2 * _d(55)[0], .44 + 2 * _d(55)[1]), (-.02, 0, .44), .16),
    "tex-neck-front34R": ((1.41, -1.41, .40), (-.02, 0, .40), .16),
    "tex-neck-rear34R": ((1.41, 1.41, .41), (-.02, .01, .41), .16),
    "tex-quiver-rear34L": ((-1.41, 1.41, .42), (-.05, .04, .42), .22),
    "tex-hands-front": ((0, -2, .31), (0, 0, .31), .24),
    "tex-bowarm-rear": ((0, 2, .32), (.04, 0, .32), .20),
}


def v31_textured(tag, body, bow, out_dir):
    scene = bpy.context.scene
    cam = v31_render_setup(scene)
    mat = bpy.data.materials.get("V31_TexReview")
    if mat is None:
        mat = bpy.data.materials.new("V31_TexReview")
        mat.use_nodes = True
        node = mat.node_tree.nodes.new("ShaderNodeTexImage")
        node.image = bpy.data.images.load(str(ASSET / "textures/T_Medusa_Atlas_BC.png"), check_existing=True)
        mat.node_tree.nodes.active = node
    for obj in (body, bow):
        for i in range(len(obj.data.materials)):
            obj.data.materials[i] = mat
    shading = scene.display.shading
    shading.light, shading.color_type = "STUDIO", "TEXTURE"
    scene.display.render_aa = "8"
    scene.render.image_settings.file_format = "JPEG"
    scene.render.image_settings.color_mode = "RGB"
    scene.render.image_settings.quality = 90
    scene.render.film_transparent = False
    scene.render.resolution_x = scene.render.resolution_y = 768
    cam.data.type = "ORTHO"
    files = {}
    out_dir = Path(out_dir).resolve()
    for name, (loc, tgt, scale) in V31_TEX_VIEWS.items():
        cam.data.ortho_scale = scale
        look_at(cam, loc, tgt)
        path = out_dir / f"{name}-{tag}.jpg"
        scene.render.filepath = str(path)
        bpy.ops.render.render(write_still=True)
        files[name] = path.name
    scene.render.image_settings.file_format = "PNG"
    scene.render.image_settings.color_mode = "RGBA"
    scene.render.film_transparent = True
    scene.display.render_aa = "OFF"
    shading.light, shading.color_type = "FLAT", "VERTEX"
    return files


def v31_orientation(objects):
    """Ray-escape score per part (tools/tripo-pipeline build_candidate.orientation_scores, world space).

    objects: list of (object, labels per polygon). Every polygon casts a ray along +normal and one along
    -normal (offset 1e-4 of the height) against all objects; area where only +normal escapes is outward.
    """
    verts, polys = [], []
    for obj, _labels in objects:
        mw = obj.matrix_world
        base = len(verts)
        verts.extend(mw @ v.co for v in obj.data.vertices)
        polys.extend([base + i for i in p.vertices] for p in obj.data.polygons)
    zs = [v.z for v in verts]
    height = max(zs) - min(zs)
    eps, dist = 1e-4 * height, 2.0 * height
    bvh = BVHTree.FromPolygons(verts, polys, all_triangles=False, epsilon=0.0)
    acc = {}
    for obj, labels in objects:
        mw = obj.matrix_world
        rot = mw.to_3x3()
        for poly, lab in zip(obj.data.polygons, labels):
            centre = mw @ poly.center
            normal = (rot @ poly.normal).normalized()
            area = poly.area
            plus = bvh.ray_cast(centre + normal * eps, normal, dist)[0] is not None
            minus = bvh.ray_cast(centre - normal * eps, -normal, dist)[0] is not None
            slot = acc.setdefault(lab, [0.0, 0.0, 0.0, 0])
            slot[2] += area
            slot[3] += 1
            if not plus and minus:
                slot[0] += area
            elif plus and not minus:
                slot[1] += area
    return {lab: {"polygons": n, "score": r((o - i) / (o + i), 4) if o + i else None,
                  "outward_area_fraction": r(o / t, 4) if t else 0.0}
            for lab, (o, i, t, n) in sorted(acc.items())}


def v31_part_pairs(co, polys, labels, changed, every):
    """Intersecting triangle pairs between a changed part and any other part (each pair once)."""
    ta = BVHTree.FromPolygons(co.tolist(), [polys[i] for i in changed])
    tb = BVHTree.FromPolygons(co.tolist(), [polys[i] for i in every])
    seen, pairs = set(), {}
    for ia, ib in ta.overlap(tb):
        pa, pb = changed[ia], every[ib]
        if labels[pa] == labels[pb] or set(polys[pa]) & set(polys[pb]):
            continue
        key = (min(pa, pb), max(pa, pb))
        if key in seen:
            continue
        seen.add(key)
        name = "|".join(sorted((V31_LABEL.get(labels[pa], labels[pa]), V31_LABEL.get(labels[pb], labels[pb]))))
        pairs[name] = pairs.get(name, 0) + 1
    return len(seen), dict(sorted(pairs.items()))


def v31_clearance(co, from_polys_vertices, to_polys, polys):
    tree = BVHTree.FromPolygons(co.tolist(), [polys[i] for i in to_polys])
    return nearest_clearance(co[from_polys_vertices], tree)


def v31_geometry(tag, co_cm, labels, polys, part_polys, bow_co_cm, bow_polys):
    crown_v = sorted({v for i in part_polys["tripo_part_1"] for v in polys[i]})
    moved_legacy = sorted(i for name in MOVED_PARTS for i in part_polys[name])
    head_parts = set(MOVED_PARTS) | {"tripo_part_3"}
    other = [i for i, lab in enumerate(labels) if lab not in head_parts]
    changed = sorted(i for name in CHANGED_PARTS for i in part_polys[name])
    legacy, legacy_pairs = overlaps(co_cm, polys, moved_legacy, other, labels)
    total, by_pair = v31_part_pairs(co_cm, polys, labels, changed, list(range(len(polys))))
    tb = BVHTree.FromPolygons(bow_co_cm.tolist(), bow_polys)
    tm = BVHTree.FromPolygons(co_cm.tolist(), [polys[i] for i in changed])
    changed_v = sorted({v for i in changed for v in polys[i]})
    return {"body_top_uu": r(co_cm[:, 2].max(), 3),
            "body_bbox_uu": [[r(co_cm[:, a].min()), r(co_cm[:, a].max())] for a in range(3)],
            "crown_to_quiver_min_clearance_uu": r(v31_clearance(co_cm, crown_v, part_polys["tripo_part_7"], polys), 3),
            "changed_parts_to_bow_min_clearance_uu": r(nearest_clearance(co_cm[changed_v], tb), 3),
            "rest_legacy_moved_vs_non_head_intersections": legacy, "rest_legacy_by_part_pair": legacy_pairs,
            "rest_changed_vs_any_other_part_intersections": total, "rest_changed_by_part_pair": by_pair,
            "rest_changed_vs_bow_intersections": len(tm.overlap(tb))}


def v31_posed(variants_m, labels, polys, part_polys):
    """Draft clips only (diagnostic, not animation acceptance): per-frame intersection counts."""
    body = bpy.data.objects["SK_Medusa_Body"]
    bow = bpy.data.objects["SK_Medusa_Bow"]
    arm = bpy.data.objects["SKEL_Medusa"]
    arm.data.pose_position = "POSE"
    head_parts = set(MOVED_PARTS) | {"tripo_part_3"}
    moved_legacy = sorted(i for name in MOVED_PARTS for i in part_polys[name])
    other = [i for i, lab in enumerate(labels) if lab not in head_parts]
    changed = sorted(i for name in CHANGED_PARTS for i in part_polys[name])
    every = list(range(len(polys)))
    crown_v = sorted({v for i in part_polys["tripo_part_1"] for v in polys[i]})
    changed_v = sorted({v for i in changed for v in polys[i]})
    scene = bpy.context.scene
    result = {}
    source = np.empty(len(body.data.vertices) * 3)
    body.data.vertices.foreach_get("co", source)
    for action in sorted(bpy.data.actions, key=lambda a: a.name):
        start, end = (int(x) for x in action.frame_range)
        arm.animation_data.action = action
        per = {"frame_range": [start, end]}
        for tag, co_m in variants_m.items():
            body.data.vertices.foreach_set("co", co_m.reshape(-1))
            body.data.update()
            legacy, changed_any, crown_quiver, clear, bow_hits = [], [], [], [], []
            worst = {}
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
                count, _pairs = overlaps(co, polys, moved_legacy, other, labels)
                legacy.append(int(count))
                total, pairs = v31_part_pairs(co, polys, labels, changed, every)
                changed_any.append(int(total))
                crown_quiver.append(int(pairs.get("crown|quiver", 0)))
                for key, value in pairs.items():
                    worst[key] = max(worst.get(key, 0), value)
                clear.append(v31_clearance(co, crown_v, part_polys["tripo_part_7"], polys))
                tb = BVHTree.FromPolygons((bco.reshape(-1, 3) * UU).tolist(), bpolys)
                tm = BVHTree.FromPolygons(co.tolist(), [polys[i] for i in changed])
                bow_hits.append(len(tm.overlap(tb)))
            per[tag] = {"legacy_moved_vs_non_head_per_frame": legacy,
                        "changed_vs_any_other_part_per_frame": changed_any,
                        "crown_quiver_per_frame": crown_quiver,
                        "crown_to_quiver_min_clearance_uu_per_frame": [r(c, 3) for c in clear],
                        "changed_vs_bow_per_frame": bow_hits,
                        "worst_frame_by_part_pair": dict(sorted(worst.items()))}
        result[action.name] = per
    body.data.vertices.foreach_set("co", source)
    body.data.update()
    arm.animation_data.action = None
    arm.data.pose_position = "REST"
    return result


def v31_corner_table(arrays):
    """Corners sorted by (polygon, vertex): lets two meshes with different winding be compared."""
    poly_of_loop = np.repeat(np.arange(len(arrays["starts"])), arrays["totals"])
    order = np.lexsort((arrays["loops"], poly_of_loop))
    return poly_of_loop[order], arrays["loops"][order], order


def v31_winding(arrays):
    """+1/-1 per triangle: orientation relative to the canonical (min vertex first) rotation."""
    tri = np.array([arrays["loops"][s:s + t] for s, t in zip(arrays["starts"], arrays["totals"])])
    assert tri.shape[1] == 3
    k = np.argmin(tri, axis=1)
    nxt = tri[np.arange(len(tri)), (k + 1) % 3]
    prv = tri[np.arange(len(tri)), (k + 2) % 3]
    return np.where(nxt < prv, 1, -1)


def v31_structure(ref, var, labels):
    out = {}
    for name in sorted(ref):
        a, b = ref[name], var[name]
        pa, va, oa = v31_corner_table(a)
        pb, vb, ob = v31_corner_table(b)
        same_corners = bool(np.array_equal(pa, pb) and np.array_equal(va, vb))
        entry = {"vertices": int(len(a["co"])), "polygons": int(len(a["starts"])),
                 "triangles": int((a["totals"] - 2).sum()), "triangles_var": int((b["totals"] - 2).sum()),
                 "same_corner_sets": same_corners,
                 "material_slots_ref": a["slots"], "material_slots_var": b["slots"],
                 "material_index_equal": bool(np.array_equal(a["mats"], b["mats"]))}
        if same_corners:
            entry["uv_max_abs_diff"] = r(np.abs(a["uv"][oa] - b["uv"][ob]).max(), 7)
            wa, wb = v31_winding(a), v31_winding(b)
            flipped = np.flatnonzero(wa != wb)
            if name == "SK_Medusa_Body":
                counts = {}
                for i in flipped:
                    counts[labels[i]] = counts.get(labels[i], 0) + 1
                entry["winding_flipped_polygons_by_part"] = dict(sorted(counts.items()))
            else:
                entry["winding_flipped_polygons"] = int(len(flipped))
        disp = np.linalg.norm(b["co"] - a["co"], axis=1)
        entry["moved_vertices"] = int((disp > 1e-4).sum())
        entry["max_displacement_uu"] = r(disp.max(), 4)
        out[name] = entry
    return out


def v31_expected_normals(src_arrays, src_labels, flipped_parts, jac_per_vertex):
    """Source corner normals, negated on flipped parts, then n' = normalize(J^-T n) at the vertex."""
    poly_of_loop = np.repeat(np.arange(len(src_arrays["starts"])), src_arrays["totals"])
    normals = src_arrays["normals"].copy()
    flip = np.isin(np.array(src_labels, dtype=object)[poly_of_loop], list(flipped_parts))
    normals[flip] *= -1.0
    if jac_per_vertex is not None:
        normals = field31.transform_normals(jac_per_vertex[src_arrays["loops"]], normals)
    return normals


def v31_normal_error(src_arrays, expected, fbx_arrays):
    ps, vs, os_ = v31_corner_table(src_arrays)
    pf, vf, of = v31_corner_table(fbx_arrays)
    assert np.array_equal(ps, pf) and np.array_equal(vs, vf)
    e = expected[os_]
    f = fbx_arrays["normals"][of]
    cos = np.clip((e * f).sum(axis=1) / np.maximum(1e-12, np.linalg.norm(e, axis=1) * np.linalg.norm(f, axis=1)), -1, 1)
    ang = np.degrees(np.arccos(cos))
    return {"max_deg": r(ang.max(), 4), "p99_9_deg": r(np.percentile(ang, 99.9), 4),
            "corners_over_1deg": int((ang > 1.0).sum())}


def v31_uv_stretch(ref, var, labels, part_polys):
    """Per changed part: 3D triangle area ratio var/v2, edge length ratio, texel density (px per uu)."""
    out = {}
    assert (ref["totals"] == 3).all() and (ref["starts"] == 3 * np.arange(len(ref["starts"]))).all()
    tri = np.array([ref["loops"][s:s + t] for s, t in zip(ref["starts"], ref["totals"])])
    uv = ref["uv"].reshape(-1, 3, 2) * 2048.0  # ref loops are consecutive triangles
    uv_area = 0.5 * np.abs((uv[:, 1, 0] - uv[:, 0, 0]) * (uv[:, 2, 1] - uv[:, 0, 1]) -
                           (uv[:, 2, 0] - uv[:, 0, 0]) * (uv[:, 1, 1] - uv[:, 0, 1]))

    def areas(co):
        p = co[tri]
        return 0.5 * np.linalg.norm(np.cross(p[:, 1] - p[:, 0], p[:, 2] - p[:, 0]), axis=1)

    def edges(co):
        p = co[tri]
        return np.stack([np.linalg.norm(p[:, (k + 1) % 3] - p[:, k], axis=1) for k in range(3)], axis=1)
    a0, a1 = areas(ref["co"]), areas(var["co"])
    e0, e1 = edges(ref["co"]), edges(var["co"])
    for name in CHANGED_PARTS:
        idx = np.array(part_polys[name])
        ok = a0[idx] > 1e-8
        ratio = a1[idx][ok] / a0[idx][ok]
        er = (e1[idx] / np.maximum(1e-9, e0[idx])).ravel()
        out[V31_LABEL[name]] = {
            "triangles": int(len(idx)),
            "area_ratio_min": r(ratio.min(), 4), "area_ratio_p1": r(np.percentile(ratio, 1), 4),
            "area_ratio_p99": r(np.percentile(ratio, 99), 4), "area_ratio_max": r(ratio.max(), 4),
            "edge_ratio_min": r(er.min(), 4), "edge_ratio_max": r(er.max(), 4),
            "texel_density_px_per_uu_v2": r(math.sqrt(uv_area[idx].sum() / a0[idx].sum()), 4),
            "texel_density_px_per_uu_var": r(math.sqrt(uv_area[idx].sum() / a1[idx].sum()), 4)}
    return out


def v31_import(path):
    """Factory-empty scene with the FBX (+ the production base for the orientation test)."""
    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.ops.import_scene.fbx(filepath=str(path), use_custom_normals=True)
    objs = {o.name: o for o in bpy.data.objects}
    before = set(bpy.data.objects)
    bpy.ops.import_scene.fbx(filepath=str(BASE_FBX), use_custom_normals=True)
    base = [o for o in bpy.data.objects if o not in before and o.type == "MESH"]
    assert len(base) == 1
    return objs["SK_Medusa_Body"], objs["SK_Medusa_Bow"], base[0]


def v31_normals_health(obj, labels):
    mesh = obj.data
    n = np.empty(len(mesh.loops) * 3)
    mesh.corner_normals.foreach_get("vector", n)
    n = n.reshape(-1, 3)
    nl = np.linalg.norm(n, axis=1)
    mesh.calc_tangents(uvmap=mesh.uv_layers.active.name)
    t = np.empty(len(mesh.loops) * 3)
    mesh.loops.foreach_get("tangent", t)
    t = t.reshape(-1, 3)
    tl = np.linalg.norm(t, axis=1)
    mesh.free_tangents()
    bad = np.flatnonzero((tl < 1e-6) | ~np.isfinite(tl))
    poly_of_loop = np.repeat(np.arange(len(mesh.polygons)), [p.loop_total for p in mesh.polygons])
    where = {}
    for loop in bad:
        poly = mesh.polygons[int(poly_of_loop[loop])]
        key = V31_LABEL.get(labels[poly.index], labels[poly.index])
        where.setdefault(key, []).append({"polygon": poly.index, "area_uu2": r(poly.area, 6)})
    return {"corners": int(len(nl)), "zero_or_nan_normals": int(((nl < 1e-6) | ~np.isfinite(nl)).sum()),
            "zero_or_nan_tangents": int(len(bad)), "zero_tangent_corners_by_part": where,
            "normal_length_min": r(np.nanmin(nl), 5)}


def v31_socket(src_bones_head, head_matrix3, params, co_m_by_tag, feature_v):
    """Head socket (bone `head` + (0,0,4) uu) against the facial features, per variant."""
    base_socket = np.array(src_bones_head) + np.array(head_matrix3) @ np.array(HEAD_SOCKET_BONE_OFFSET_M)
    inv = np.linalg.inv(np.array(head_matrix3))
    out = {"socket_source_m": [r(x, 5) for x in base_socket]}
    for tag, co_m in co_m_by_tag.items():
        centroid = co_m[feature_v].mean(axis=0)
        entry = {"feature_centroid_uu": [r(x * UU) for x in centroid],
                 "socket_to_feature_centroid_uu": r(np.linalg.norm(centroid - base_socket) * UU)}
        p = params.get(tag)
        if p is not None:
            rot = field31.rot_x(np.array([math.radians(p["face_deg"])]))[0]
            pivot = np.array(p["pivot_m"])
            follow = pivot + rot @ (base_socket - pivot)
            local = inv @ (follow - np.array(src_bones_head))
            entry.update({
                "socket_following_head_full_angle_m": [r(x, 5) for x in follow],
                "socket_following_head_ue_component_uu": [r(follow[0] * UU), r(-follow[1] * UU), r(follow[2] * UU)],
                "socket_following_head_to_feature_centroid_uu": r(np.linalg.norm(centroid - follow) * UU),
                "shift_uu": r(np.linalg.norm(follow - base_socket) * UU),
                "blender_bone_local_offset_uu": [r(x * UU) for x in local]})
        out[tag] = entry
    return out


def v31_variants():
    found = {}
    for folder in sorted((ASSET / "variants").glob("head-tilt-v31-*")):
        fbx = sorted(p for p in folder.glob("SK_Medusa_HeadTilt_v31*.fbx") if not p.stem.endswith("_UM_FBX_v1"))
        assert len(fbx) == 1, fbx
        report = json.loads(fbx[0].with_suffix(".json").read_text(encoding="utf-8"))
        assert report["fbx_sha256"] == sha(fbx[0]), "saved FBX differs from its export report"
        twin = fbx[0].with_name(fbx[0].stem + "_UM_FBX_v1.fbx")
        found["v31" + folder.name.rsplit("-", 1)[1]] = {"fbx": fbx[0], "report": report,
                                                        "twin": twin if twin.exists() else None}
    return found


def v31_twin_check(game_meshes, game_bones, twin_path):
    """UM_FBX_v1 twin = game-frame FBX rotated +90 deg about Z (authored -Y front -> +X)."""
    meshes, bones = read_fbx(twin_path)
    back = np.array([[0, 1, 0], [-1, 0, 0], [0, 0, 1]], dtype=float)  # -90 deg about Z
    out = {}
    for name in sorted(game_meshes):
        g, t = game_meshes[name], meshes[name]
        pg, vg, og = v31_corner_table(g)
        pt, vt, ot = v31_corner_table(t)
        same = bool(np.array_equal(pg, pt) and np.array_equal(vg, vt))
        entry = {"same_corner_sets": same,
                 "positions_after_minus90z_max_abs_uu": r(np.abs(t["co"] @ back.T - g["co"]).max(), 5)}
        if same:
            a, b = t["normals"][ot] @ back.T, g["normals"][og]
            cos = np.clip((a * b).sum(axis=1) / np.maximum(1e-12, np.linalg.norm(a, axis=1) * np.linalg.norm(b, axis=1)), -1, 1)
            ang = np.degrees(np.arccos(cos))
            entry.update({"normals_after_minus90z_max_deg": r(ang.max(), 3),
                          "normals_after_minus90z_p99_9_deg": r(np.percentile(ang, 99.9), 4),
                          "corners_over_1deg": int((ang > 1.0).sum())})
        out[name] = entry
    face = [i for i, lab in enumerate(part_polygons_arrays(game_meshes["SK_Medusa_Body"])) if lab == "tripo_part_10"]
    out["face_mean_normal_twin"] = [r(x, 4) for x in mean_face_normal(meshes["SK_Medusa_Body"], face)]
    out["face_mean_normal_game"] = [r(x, 4) for x in mean_face_normal(game_meshes["SK_Medusa_Body"], face)]
    err = 0.0
    for name, bone in bones.items():
        for key in ("head_uu", "tail_uu"):
            err = max(err, float(np.abs(back @ np.array(bone[key]) - np.array(game_bones[name][key])).max()))
    out["bones_after_minus90z_max_abs_uu"] = r(err, 4)
    out["bone_names_equal"] = sorted(bones) == sorted(game_bones)
    return out


def part_polygons_arrays(arrays):
    rects = {name: ((c["x"] + c["inset"]) / 2048, (c["x"] + c["cell"] - c["inset"]) / 2048,
                    1 - (c["y_top"] + c["cell"] - c["inset"]) / 2048, 1 - (c["y_top"] + c["inset"]) / 2048)
             for name, c in ATLAS["cells"].items()}
    labels = []
    for s, t in zip(arrays["starts"], arrays["totals"]):
        uv = arrays["uv"][s:s + t]
        hit = "unassigned"
        for name, (u0, u1, v0, v1) in rects.items():
            if ((uv[:, 0] >= u0) & (uv[:, 0] <= u1) & (uv[:, 1] >= v0) & (uv[:, 1] <= v1)).all():
                hit = name
        labels.append(hit)
    return labels


def mean_face_normal(arrays, polys_idx):
    acc = np.zeros(3)
    for i in polys_idx:
        s, t = arrays["starts"][i], arrays["totals"][i]
        p = arrays["co"][arrays["loops"][s:s + t]]
        n = np.cross(p[1] - p[0], p[2] - p[0])
        acc += n / 2.0
    return acc / np.linalg.norm(acc)


def v31_near_pairs(co_ref, labels_v, parts=CHANGED_PARTS):
    """Vertex pairs of different parts within 0.5 uu in v2 that involve a changed part (A1 method)."""
    tree = KDTree(len(co_ref))
    for i, p in enumerate(co_ref):
        tree.insert(Vector(p), i)
    tree.balance()
    pairs = []
    changed = [i for i, lab in enumerate(labels_v) if lab in parts]
    for i in changed:
        for _c, j, dist in tree.find_range(Vector(co_ref[i]), 0.5):
            if labels_v[j] != labels_v[i] and (labels_v[j] not in parts or j > i):
                pairs.append((i, j))
    return pairs


def v31_near_report(pairs, labels_v, co_ref, co_var):
    groups = {}
    for i, j in pairs:
        key = "|".join(sorted((V31_LABEL.get(labels_v[i], labels_v[i]), V31_LABEL.get(labels_v[j], labels_v[j]))))
        groups.setdefault(key, []).append((float(np.linalg.norm(co_ref[i] - co_ref[j])),
                                           float(np.linalg.norm(co_var[i] - co_var[j]))))
    return {key: {"pairs": len(v), "v2_mean_uu": r(sum(a for a, _ in v) / len(v)),
                  "var_mean_uu": r(sum(b for _, b in v) / len(v)), "var_max_uu": r(max(b for _, b in v))}
            for key, v in sorted(groups.items())}


def main_v31():
    variants = v31_variants()
    assert variants, "no variants/head-tilt-v31-* found"
    inputs = {"medusa.blend": sha(BLEND), "v2": sha(V2), "v3": sha(V3), "atlas-report.json": sha(ASSET / "atlas-report.json"),
              "SM_Medusa_Base.fbx": sha(BASE_FBX)}
    assert {k: inputs[k] for k in EXPECTED_SHA} == EXPECTED_SHA, inputs
    for tag, info in variants.items():
        inputs[tag] = sha(info["fbx"])
        if info["twin"]:
            inputs[tag + "_UM_FBX_v1"] = sha(info["twin"])
    files = {"v2": V2, "v3": V3}
    files.update({tag: info["fbx"] for tag, info in variants.items()})
    fbx_arrays, fbx_bones = {}, {}
    for tag, path in files.items():
        fbx_arrays[tag], fbx_bones[tag] = read_fbx(path)
    # ---- source (read only)
    bpy.ops.wm.open_mainfile(filepath=str(BLEND))
    body = bpy.data.objects["SK_Medusa_Body"]
    bow = bpy.data.objects["SK_Medusa_Bow"]
    arm = bpy.data.objects["SKEL_Medusa"]
    mesh = body.data
    labels = list(part_polygons(mesh))
    polys = [list(p.vertices) for p in mesh.polygons]
    part_polys = {name: [i for i, lab in enumerate(labels) if lab == name] for name in sorted(set(labels))}
    src = mesh_arrays(mesh)
    co_m = src["co"]
    label_v = np.empty(len(co_m), dtype=object)
    for i, poly in enumerate(polys):
        label_v[poly] = labels[i]
    head = arm.data.bones["head"]
    head_pos = [float(x) for x in head.head_local]
    head_m3 = [[float(x) for x in row] for row in head.matrix_local.to_3x3()]
    bow_co_cm = np.array([v.co[:] for v in bow.data.vertices]) * UU
    bow_polys = [list(p.vertices) for p in bow.data.polygons]
    # ---- reproduction: every FBX = its recipe applied to the source
    jac = {"v2": None, "v3": np.repeat(np.array(rotation())[None], len(co_m), axis=0)}
    expected_co = {"v2": co_m.copy(), "v3": tilt(co_m, {v for i in part_polys_moved(part_polys) for v in polys[i]})}
    v3_moved = np.zeros(len(co_m), dtype=bool)
    v3_moved[sorted({v for i in part_polys_moved(part_polys) for v in polys[i]})] = True
    jac["v3"][~v3_moved] = np.eye(3)
    params = {"v3": {"face_deg": TILT_DEG, "pivot_m": list(PIVOT_M)}}
    for tag, info in variants.items():
        params[tag] = info["report"]["head_tilt_v31"]["params"]
        new, j, _moved = field31.apply(params[tag], co_m, label_v)
        expected_co[tag], jac[tag] = new, j
    repro = {}
    for tag in files:
        body_fbx = fbx_arrays[tag]["SK_Medusa_Body"]
        flips = FLIPPED_PARTS["v31" if tag.startswith("v31") else tag]
        normals = v31_expected_normals(src, labels, flips, jac[tag])
        repro[tag] = {"positions_fbx_vs_recipe_max_uu": r(np.abs(body_fbx["co"] - expected_co[tag] * UU).max(), 5),
                      "corner_normals_fbx_vs_recipe": v31_normal_error(src, normals, body_fbx),
                      "recipe": ("source + flip parts 10/14" if tag == "v2" else
                                 "source + flip parts 10/14 + rigid -15 deg (v3)" if tag == "v3" else
                                 "source + flip parts 8/10/13/14 + v3.1 field (J^-T normals)")}
        assert repro[tag]["positions_fbx_vs_recipe_max_uu"] < .01, (tag, repro[tag])
    # ---- structure against v2
    structure = {tag: v31_structure(fbx_arrays["v2"], fbx_arrays[tag], labels) for tag in files if tag != "v2"}
    for tag, st in structure.items():
        body_st = st["SK_Medusa_Body"]
        flipped = body_st.get("winding_flipped_polygons_by_part", {})
        if tag.startswith("v31"):
            assert flipped == {"tripo_part_13": 607, "tripo_part_8": 575}, flipped
    bones = {tag: {"count": len(b), "rest_pose_identical_to_v2": b == fbx_bones["v2"]} for tag, b in fbx_bones.items()}
    # ---- geometry, UV stretch, near pairs, socket
    co_cm = {tag: fbx_arrays[tag]["SK_Medusa_Body"]["co"] for tag in files}
    geometry = {tag: v31_geometry(tag, co_cm[tag], labels, polys, part_polys, bow_co_cm, bow_polys) for tag in files}
    parts_moved = {}
    for tag in files:
        disp = np.linalg.norm(co_cm[tag] - co_cm["v2"], axis=1)
        parts_moved[tag] = {V31_LABEL.get(name, name): {"moved_vertices": int((disp[sorted({v for i in idx for v in polys[i]})] > 1e-4).sum()),
                                                        "max_displacement_uu": r(disp[sorted({v for i in idx for v in polys[i]})].max(), 4)}
                            for name, idx in part_polys.items()}
    bow_disp = {tag: r(np.abs(fbx_arrays[tag]["SK_Medusa_Bow"]["co"] - fbx_arrays["v2"]["SK_Medusa_Bow"]["co"]).max(), 6)
                for tag in files}
    stretch = {tag: v31_uv_stretch(fbx_arrays["v2"]["SK_Medusa_Body"], fbx_arrays[tag]["SK_Medusa_Body"], labels, part_polys)
               for tag in files if tag != "v2"}
    near = v31_near_pairs(co_cm["v2"], list(label_v))
    near_report = {tag: v31_near_report(near, list(label_v), co_cm["v2"], co_cm[tag]) for tag in files if tag != "v2"}
    face_polys = part_polys["tripo_part_10"]
    rest_z = np.array([co_cm["v2"][polys[i]].mean(axis=0)[2] for i in range(len(polys))])
    feature_v = sorted({v for i in face_polys if rest_z[i] >= FEATURE_Z_UU for v in polys[i]})
    socket = v31_socket(head_pos, head_m3, params, {tag: co_cm[tag] / UU for tag in files}, feature_v)
    # ---- draft clips (source armature and actions, read only)
    posed = v31_posed({tag: co_cm[tag] / UU for tag in files}, labels, polys, part_polys)
    # ---- per-FBX scenes: normals/tangents, ray-escape orientation, part-ID renders
    rest_z_list = rest_z.tolist()
    renders, orientation, health, textured = {}, {}, {}, {}
    for tag, path in files.items():
        fbody, fbow, fbase = v31_import(path)
        flabels = part_polygons_arrays(fbx_arrays[tag]["SK_Medusa_Body"])
        assert flabels == labels
        health[tag] = v31_normals_health(fbody, flabels)
        orientation[tag] = v31_orientation([(fbody, flabels), (fbow, ["tripo_part_4"] * len(fbow.data.polygons)),
                                            (fbase, ["tripo_part_2"] * len(fbase.data.polygons))])
        renders[tag] = v31_render(tag, fbody, fbow, flabels, rest_z_list, V31_OUT)
        if tag != "v3":  # the v3 textured frames are in the A1 probe
            textured[tag] = v31_textured(tag, fbody, fbow, V31_OUT)
    twins = {tag: v31_twin_check(fbx_arrays[tag], fbx_bones[tag], info["twin"])
             for tag, info in variants.items() if info["twin"]}
    gates = v31_gates(files, renders, geometry, posed, orientation, structure, bones, bow_disp, parts_moved)
    report = {
        "status": "measured_diagnostic_not_art_acceptance",
        "runner": "Blender " + bpy.app.version_string + " --background --factory-startup (Workbench only)",
        "inputs_sha256": inputs,
        "variants": {tag: {"fbx": info["fbx"].relative_to(ROOT).as_posix(), "params": params[tag],
                           "um_fbx_v1_twin": info["twin"].relative_to(ROOT).as_posix() if info["twin"] else None}
                     for tag, info in variants.items()},
        "reproduction_check": repro,
        "fbx_structure_vs_v2": structure,
        "bones": bones,
        "bow_max_abs_diff_vs_v2_uu": bow_disp,
        "parts_moved_vs_v2": parts_moved,
        "geometry_rest": geometry,
        "uv_stretch_vs_v2": stretch,
        "near_pairs_v2_le_0p5uu": near_report,
        "normals_tangents_fbx_import": health,
        "orientation_ray_escape": orientation,
        "head_socket": socket,
        "draft_clip_interpenetration_per_frame": posed,
        "part_id_views": renders,
        "textured_closeups": {"files": textured, "views": {k: {"camera_m": list(v[0]), "target_m": list(v[1]),
                                                               "ortho_scale_m": v[2]} for k, v in V31_TEX_VIEWS.items()},
                              "note": "Workbench studio light, atlas BaseColor only, backface culling, 768 px JPEG q90; "
                                      "diagnostic look, not UE PBR, not art acceptance"},
        "um_fbx_v1_twin": twins,
        "gates": gates,
        "camera_note": "A1 live-review camera set (b4_idrender.py) at the origin; Workbench flat part-ID colours, "
                       "AA off, backface culling on; ortho views 0.16 m wide at 1024 px, k2 = D-10 300 uu 1920x1080.",
    }
    V31_OUT.mkdir(parents=True, exist_ok=True)
    path = V31_OUT / "blender-measurements.json"
    path.write_text(json.dumps(report, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print("ART004_HEAD_TILT_V31_MEASURE_OK", path, hashlib.sha256(path.read_bytes()).hexdigest())


def part_polys_moved(part_polys):
    return sorted(i for name in MOVED_PARTS for i in part_polys[name])


def v31_gates(files, renders, geometry, posed, orientation, structure, bones, bow_disp, parts_moved):
    """Thresholds of the A1 act / stage-3 plan, evaluated for every v3.1 variant (and v3 for reference)."""
    out = {}
    v2 = renders["v2"]
    for tag in files:
        if tag == "v2":
            continue
        g = {}
        for view in GATE_VIEWS:
            g["gap_" + view] = {"value": renders[tag][view]["face_x_collar"]["enclosed_gap_px"],
                                "v2": v2[view]["face_x_collar"]["enclosed_gap_px"]}
            g["gap_" + view]["pass"] = g["gap_" + view]["value"] <= g["gap_" + view]["v2"]
        rear = {}
        for view in ("neck-rear", "neck-rear34R", "neck-rear34L", "neck-sideR", "neck-sideL", "k2-rear-d300"):
            for zone in ("neck_back_x_collar", "crown_x_collar"):
                rear[view + ":" + zone] = [renders[tag][view][zone]["junction_only_px"], v2[view][zone]["junction_only_px"]]
        g["rear_zones_junction_only_le_v2"] = {"value_vs_v2": rear, "pass": all(a <= b for a, b in rear.values())}
        feat = renders[tag]["idsplit-k2-front-d300"]["facial_features_z_ge_42_px"]
        g["k2_facial_features_px"] = {"value": feat, "threshold": 1242, "pass": feat >= 1242}
        clear = geometry[tag]["crown_to_quiver_min_clearance_uu"]
        g["crown_to_quiver_rest_uu"] = {"value": clear, "threshold": 1.0, "pass": clear >= 1.0}
        hit = posed["HitReact"][tag]
        g["hitreact_zero_intersections"] = {
            "legacy_per_frame": hit["legacy_moved_vs_non_head_per_frame"],
            "crown_quiver_per_frame": hit["crown_quiver_per_frame"],
            "pass": max(hit["legacy_moved_vs_non_head_per_frame"]) == 0 and max(hit["crown_quiver_per_frame"]) == 0}
        others = {a: max(posed[a][tag]["legacy_moved_vs_non_head_per_frame"]) for a in ("Idle", "LungeAttack", "DeathSettle")}
        g["other_clips_legacy_max"] = {"value": others, "pass": not any(others.values())}
        scores = {k: v["score"] for k, v in orientation[tag].items()}
        g["ray_escape_all_15_parts_ge_0p978"] = {"value": scores, "min": min(scores.values()), "parts": len(scores),
                                                 "pass": len(scores) == 15 and min(scores.values()) >= 0.978}
        top = geometry[tag]["body_top_uu"]
        g["top_55_pm_0p5_uu"] = {"value": top, "pass": abs(top - 55.0) <= 0.5}
        hands = {V31_LABEL.get(k, k): parts_moved[tag][V31_LABEL.get(k, k)]["moved_vertices"] for k in HANDS_ARMS}
        g["bow_and_hands_unchanged"] = {"bow_max_abs_uu": bow_disp[tag], "hands_arms_moved_vertices": hands,
                                        "pass": bow_disp[tag] == 0 and not any(hands.values())}
        body = structure[tag]["SK_Medusa_Body"]
        bow_st = structure[tag]["SK_Medusa_Bow"]
        g["structure_identical_to_v2"] = {
            "triangles": [body["triangles_var"], bow_st["triangles_var"]], "uv_max_abs_diff": body.get("uv_max_abs_diff"),
            "slots": body["material_slots_var"], "material_index_equal": body["material_index_equal"],
            "bones_identical": bones[tag]["rest_pose_identical_to_v2"],
            "pass": (body["same_corner_sets"] and body["triangles_var"] == 18199 and bow_st["triangles_var"] == 1197
                     and body.get("uv_max_abs_diff", 1) == 0 and body["material_slots_var"] == 2
                     and body["material_index_equal"] and bones[tag]["rest_pose_identical_to_v2"])}
        g["all_pass"] = all(v["pass"] for k, v in g.items() if isinstance(v, dict) and "pass" in v)
        out[tag] = g
    return out


# Guarded so art004_head_tilt_v3_followup.py can import the helpers (added 2026-09-28,
# after the verified runs; `blender --python` still runs main() because __name__ == "__main__").
if __name__ == "__main__":
    SCRIPT_ARGS = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    if "--v31" in SCRIPT_ARGS:
        main_v31()
    else:
        main()
