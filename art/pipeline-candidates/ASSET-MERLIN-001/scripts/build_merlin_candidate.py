"""Stage `build` for Merlin (ASSET-MERLIN-001): segmented Tripo GLB -> skeletal candidate (body + separate
staff) and a separate static base, UM_FBX_v1.

Headless only (`blender -b --factory-startup`), never in a live Blender (read_factory_settings):

    blender -b --factory-startup --python build_merlin_candidate.py -- <params.json>

params.json has the keys of tools/tripo-pipeline/tripo_pipeline.py exec_build:
    {"source", "profile", "atlas_report", "textures_dir", "repo_root", "blend_out",
     "sk_fbx_out", "base_fbx_out", "report_out", "fbx_preset"}

Why not tools/tripo-pipeline/blender/build_candidate.py (0.4.0): it hard-codes Medusa (bow = one GLB part on
+X, face part tripo_part_10, neck check on tripo_part_14). This script is the King Arthur builder
(art/pipeline-candidates/ASSET-KING-ARTHUR-001/scripts/build_arthur_candidate.py) adapted to Merlin. The
copy was taken on 2026-09-28 before 15:53 +05:00, when that file had sha256 db6adc66... The Arthur file
was rewritten later the same day (16:14 and 16:33 +05:00; 704b2360... is the revision in Arthur's own
build-report). The db6adc66 revision is not kept in git or anywhere else, so the provenance hash cannot be
checked against the working tree. Nothing here depends on it: helpers are copied, not imported (both
builders run main() at import). Merlin differences, data-driven by the build profile:
  * the staff is three whole GLB parts (lower shaft, upper shaft, crystal) joined into one weapon mesh;
    no split. An open cylinder closes the shaft inside the fist (Tripo modelled none) and the open shaft
    bottom is capped with a fan;
  * the shoes tripo_part_6 / tripo_part_7 are inside out in the GLB and are flipped (ray-escape);
  * bone joints and weight ramps are given in the SOURCE frame and mapped with the figure transform;
  * ramps may also fade a bone in from below (zero_below_z / full_above_z); caps may send the excess to
    a per-bone target.
The report is deterministic (rounded floats, sorted keys, no timestamps). Nothing outside the params'
output paths is written; the source GLB is only read.
"""

import datetime
import hashlib
import json
import math
import re
import struct
import sys
from collections import Counter, defaultdict
from contextlib import contextmanager
from pathlib import Path

import bmesh
import bpy
import numpy as np
from mathutils import Matrix, Vector
from mathutils.bvhtree import BVHTree

if not bpy.app.background:
    raise RuntimeError("build_merlin_candidate.py: headless only (blender -b)")

MARKER = "TRIPO_PIPELINE_STAGE_OK build"
BUILDER = "art/pipeline-candidates/ASSET-MERLIN-001/scripts/build_merlin_candidate.py"
FIXED_TIME = datetime.datetime(2000, 1, 1, 0, 0, 0)
WORK_SCENE = "tripo_pipeline_candidate"
ROUNDTRIP_SCENE = "tripo_pipeline_candidate_roundtrip"
CN_ATTR = "um_corner_normal"
PART_ATTR = "um_part"
DEGENERATE_AREA_CM2 = 1e-4
PRESET_KEYS = ("name", "axis_forward", "axis_up", "export_space_rotation_z_degrees", "temporary_data_scale",
               "patch_fbx_unit_scale_to", "apply_unit_scale", "apply_scale_options", "use_triangles",
               "mesh_smooth_type", "add_leaf_bones", "primary_bone_axis", "secondary_bone_axis", "path_mode")
PATH_MODE = "STRIP"


def r(value, nd=6):
    return round(float(value), nd)


def rv(vec, nd=6):
    return [r(c, nd) for c in vec]


def sha256(path):
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_params():
    return json.loads(Path(sys.argv[sys.argv.index("--") + 1]).read_text(encoding="utf-8"))


def load_preset(path):
    preset = json.loads(Path(path).read_text(encoding="utf-8"))
    missing = [k for k in PRESET_KEYS if k not in preset]
    if missing:
        raise RuntimeError("FBX preset %s lacks %s" % (path, missing))
    return preset


def export_rotation(preset):
    rot = Matrix.Rotation(math.radians(float(preset["export_space_rotation_z_degrees"])), 4, "Z")
    for i in range(4):
        for j in range(4):
            if abs(rot[i][j] - round(rot[i][j])) < 1e-9:
                rot[i][j] = float(round(rot[i][j]))
    return rot


@contextmanager
def scene_context(scene):
    wm = bpy.context.window_manager
    window = bpy.context.window or (wm.windows[0] if wm.windows else None)
    view_layer = scene.view_layers[0]
    if window is None:
        with bpy.context.temp_override(scene=scene, view_layer=view_layer):
            yield
        return
    previous_scene, previous_layer = window.scene, window.view_layer
    try:
        window.scene = scene
        with bpy.context.temp_override(window=window, scene=scene, view_layer=view_layer):
            yield
    finally:
        window.scene = previous_scene
        window.view_layer = previous_layer


def stable_hash(key):
    digest = hashlib.sha256(repr(key).encode("utf-8")).digest()
    return int.from_bytes(digest[:8], "little") & ((1 << 63) - 1)


_MISSING = object()


def make_fbx_deterministic():
    from io_scene_fbx import export_fbx_bin, fbx_utils

    saved = {"vid": export_fbx_bin._gen_vid_path, "datetime": export_fbx_bin.datetime,
             "hash": fbx_utils.__dict__.get("hash", _MISSING)}
    original_vid_path = saved["vid"]

    def relative_vid_path(img, scene_data):
        _abs, rel = original_vid_path(img, scene_data)
        return rel, rel

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
        export_fbx_bin._gen_vid_path = saved["vid"]
        export_fbx_bin.datetime = saved["datetime"]
        if saved["hash"] is _MISSING:
            fbx_utils.__dict__.pop("hash", None)
        else:
            fbx_utils.hash = saved["hash"]
        fbx_utils._keys_to_uuids.clear()
        fbx_utils._uuids_to_keys.clear()

    return restore


def patch_fbx_units(path, value=1.0):
    buffer = bytearray(path.read_bytes())
    start = buffer.find(b"UnitScaleFactor")
    if start < 0:
        raise RuntimeError("UnitScaleFactor not found in FBX")
    token = buffer.find(b"Number", buffer.find(b"double", start))
    length = struct.unpack_from("<I", buffer, token - 4)[0]
    offset = token + length
    if buffer[offset:offset + 1] != b"S":
        raise RuntimeError("unexpected FBX property layout")
    string_length = struct.unpack_from("<I", buffer, offset + 1)[0]
    offset += 1 + 4 + string_length
    if buffer[offset:offset + 1] != b"D":
        raise RuntimeError("unexpected FBX property layout")
    struct.pack_into("<d", buffer, offset + 1, value)
    path.write_bytes(buffer)


# ------------------------------------------------------------------ measurements (as build_candidate.py)

def cell_rects(cells, size):
    rects = {}
    for name, cell in cells.items():
        rects[name] = ((cell["x"] + cell["inset"]) / size, (cell["x"] + cell["cell"] - cell["inset"]) / size,
                       1 - (cell["y_top"] + cell["cell"] - cell["inset"]) / size, 1 - (cell["y_top"] + cell["inset"]) / size)
    return rects


def polygons_by_part(mesh, rects):
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
    scale2 = (obj.matrix_world.to_3x3().determinant() ** (2.0 / 3.0)) * 1e4
    degenerate = sum(1 for t in mesh.loop_triangles if t.area * scale2 < DEGENERATE_AREA_CM2)
    uv_ok = True
    if mesh.uv_layers:
        arr = np.empty(len(mesh.loops) * 2, dtype=np.float32)
        mesh.uv_layers[0].data.foreach_get("uv", arr)
        uv_ok = bool(arr.size == 0 or (arr.min() >= -1e-6 and arr.max() <= 1 + 1e-6))
    return {"vertices": len(mesh.vertices), "polygons": len(mesh.polygons), "triangles": len(mesh.loop_triangles),
            "near_degenerate_triangles": degenerate, "near_degenerate_area_cm2_below": DEGENERATE_AREA_CM2,
            "uv_layers": [u.name for u in mesh.uv_layers], "uv0_in_unit_square": uv_ok,
            "material_slots": [re.sub(r"\.\d{3}$", "", s.material.name) if s.material else None
                               for s in obj.material_slots],
            "has_custom_normals": bool(mesh.has_custom_normals)}


def centroid(obj, indices=None):
    mw = obj.matrix_world
    if indices is None:
        pts = [mw @ v.co for v in obj.data.vertices]
    else:
        vids = sorted({v for i in indices for v in obj.data.polygons[i].vertices})
        pts = [mw @ obj.data.vertices[v].co for v in vids]
    return [r(sum(p[a] for p in pts) / len(pts), 5) for a in range(3)]


def along(vector, axis_vector):
    v = Vector(vector)
    a = Vector(axis_vector)
    side = Vector((-a.y, a.x, 0.0))
    return r(v.dot(a), 4), r(abs(v.dot(side)), 4)


def ue_predicted(bounds_cm):
    lo, hi = bounds_cm["min"], bounds_cm["max"]
    return {"min": [lo[0], r(-hi[1], 3), lo[2]], "max": [hi[0], r(-lo[1], 3), hi[2]]}


def ue_from_blender_m(p):
    """Authored Blender metres -> UE component uu under UM_FBX_v1 (measured on the Medusa candidate:
    ue(x, y) = (-y, -x) of the authored frame, z kept)."""
    return [r(-p[1] * 100, 3), r(-p[0] * 100, 3), r(p[2] * 100, 3)]


def axis_name(vector):
    x, y = round(vector[0]), round(vector[1])
    return {(1, 0): "+X", (-1, 0): "-X", (0, 1): "+Y", (0, -1): "-Y"}.get((x, y), "?")


# ------------------------------------------------------------------------- build steps

def bake_parts(scene):
    parts = {}
    for obj in list(scene.objects):
        if obj.type == "MESH":
            parts[obj.name] = obj
    for obj in parts.values():
        world = obj.matrix_world.copy()
        obj.parent = None
        obj.data.transform(world)
        obj.matrix_world.identity()
    for obj in [o for o in scene.objects if o.type != "MESH"]:
        bpy.data.objects.remove(obj)
    return parts


def capture_corner_normals(obj):
    """Store the imported corner normals as a float corner attribute (survives bmesh edits)."""
    mesh = obj.data
    arr = np.empty(len(mesh.loops) * 3, dtype=np.float32)
    mesh.corner_normals.foreach_get("vector", arr)
    attr = mesh.attributes.new(CN_ATTR, "FLOAT_VECTOR", "CORNER")
    attr.data.foreach_set("vector", arr)
    return arr.reshape(-1, 3)


def apply_corner_normals(obj, linear=None):
    """Re-apply the captured corner normals (optionally transformed by a 3x3 linear map, inverse-transpose)."""
    mesh = obj.data
    attr = mesh.attributes[CN_ATTR]
    arr = np.empty(len(mesh.loops) * 3, dtype=np.float32)
    attr.data.foreach_get("vector", arr)
    arr = arr.reshape(-1, 3).astype(np.float64)
    if linear is not None:
        m = np.array(linear, dtype=np.float64)
        arr = arr @ np.linalg.inv(m)  # (M^-T n) as row vectors
    lengths = np.linalg.norm(arr, axis=1)
    lengths[lengths == 0] = 1.0
    arr = arr / lengths[:, None]
    mesh.normals_split_custom_set([tuple(v) for v in arr])
    mesh.update()
    return arr


def corner_normal_agreement(obj, expected):
    """Min dot between the current corner normals and `expected` (N x 3). Corners whose captured normal
    is the zero vector (Tripo writes one on a zero-area collinear triangle of tripo_part_7) carry no
    direction to preserve: they are excluded and counted."""
    mesh = obj.data
    arr = np.empty(len(mesh.loops) * 3, dtype=np.float32)
    mesh.corner_normals.foreach_get("vector", arr)
    arr = arr.reshape(-1, 3)
    valid = np.linalg.norm(expected, axis=1) > 0.5
    dots = np.einsum("ij,ij->i", arr[valid], expected[valid])
    return (float(dots.min()) if len(dots) else 1.0, int((dots < 0.999).sum()), int((~valid).sum()))


def opposed_corner_fraction(obj, polys=None):
    """Area share of polygons whose custom corner normals point against the polygon (winding) normal."""
    mesh = obj.data
    cn = np.empty(len(mesh.loops) * 3, dtype=np.float32)
    mesh.corner_normals.foreach_get("vector", cn)
    cn = cn.reshape(-1, 3)
    allowed = None if polys is None else set(polys)
    opposed = total = 0.0
    for p in mesh.polygons:
        if allowed is not None and p.index not in allowed:
            continue
        n = np.array(p.normal)
        mean = cn[p.loop_start:p.loop_start + p.loop_total].mean(axis=0)
        total += p.area
        if float(np.dot(mean, n)) < 0:
            opposed += p.area
    return r(opposed / total, 5) if total else 0.0


def weld_part(obj, distance):
    mesh = obj.data
    before_v, before_f = len(mesh.vertices), len(mesh.polygons)
    bm = bmesh.new()
    bm.from_mesh(mesh)
    bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=distance)
    bm.to_mesh(mesh)
    bm.free()
    mesh.update()
    return {"vertices_before": before_v, "vertices_after": len(mesh.vertices), "polygons_before": before_f,
            "polygons_after": len(mesh.polygons), "islands_after": islands(mesh)[0]}


def islands(mesh, polys=None):
    """Connected components of polygons over shared edges; returns (count, sizes desc, comps)."""
    edge_faces = defaultdict(list)
    allowed = set(range(len(mesh.polygons))) if polys is None else set(polys)
    for p in mesh.polygons:
        if p.index in allowed:
            for ek in p.edge_keys:
                edge_faces[ek].append(p.index)
    seen, comps = set(), []
    for start in sorted(allowed):
        if start in seen:
            continue
        stack, comp = [start], []
        seen.add(start)
        while stack:
            f = stack.pop()
            comp.append(f)
            for ek in mesh.polygons[f].edge_keys:
                for g in edge_faces[ek]:
                    if g not in seen:
                        seen.add(g)
                        stack.append(g)
        comps.append(comp)
    comps.sort(key=len, reverse=True)
    return len(comps), [len(c) for c in comps], comps


def atlas_material(textures_dir, texture_files, name):
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    nodes, links = mat.node_tree.nodes, mat.node_tree.links
    bsdf = next(n for n in nodes if n.type == "BSDF_PRINCIPLED")
    images = {}
    for key in ("BC", "N_OpenGL", "ORM"):
        image = bpy.data.images.load(str(Path(textures_dir) / texture_files[key]), check_existing=False)
        image.colorspace_settings.name = "sRGB" if key == "BC" else "Non-Color"
        node = nodes.new("ShaderNodeTexImage")
        node.image = image
        node.label = key
        images[key] = node
    links.new(images["BC"].outputs["Color"], bsdf.inputs["Base Color"])
    normal = nodes.new("ShaderNodeNormalMap")
    links.new(images["N_OpenGL"].outputs["Color"], normal.inputs["Color"])
    links.new(normal.outputs["Normal"], bsdf.inputs["Normal"])
    channels = nodes.new("ShaderNodeSeparateColor")
    links.new(images["ORM"].outputs["Color"], channels.inputs["Color"])
    links.new(channels.outputs["Green"], bsdf.inputs["Roughness"])
    links.new(channels.outputs["Blue"], bsdf.inputs["Metallic"])
    return mat, {k: {"image": v.image.name, "colorspace": v.image.colorspace_settings.name,
                     "file": Path(v.image.filepath).name} for k, v in images.items()}


def remap_uvs(obj, cell, size):
    x, y, width, inset = cell["x"], cell["y_top"], cell["cell"], cell["inset"]
    inner = width - 2 * inset
    for uv_data in obj.data.uv_layers.active.data:
        uv = uv_data.uv.copy()
        uv_data.uv = ((x + inset + uv.x * inner) / size, 1 - (y + inset + (1 - uv.y) * inner) / size)


def dist_to_line(p, c, d):
    v = Vector(p) - c
    return (v - d * v.dot(d)).length


def label_faces(obj, part_name):
    attr = obj.data.attributes.new(PART_ATTR, "INT", "FACE")
    attr.data.foreach_set("value", [int(part_name.split("_")[-1])] * len(obj.data.polygons))


def read_face_labels(obj):
    vals = [0] * len(obj.data.polygons)
    obj.data.attributes[PART_ATTR].data.foreach_get("value", vals)
    out = defaultdict(list)
    for i, v in enumerate(vals):
        out["tripo_part_%d" % v].append(i)
    return dict(out)


def join_objects(scene, objects, active):
    with scene_context(scene):
        bpy.ops.object.select_all(action="DESELECT")
        for obj in objects:
            obj.select_set(True)
        bpy.context.view_layer.objects.active = active
        bpy.ops.object.join()
    return active


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


def grip_bridge(staff, labels, bcfg, axis_c, axis_d, radius, to_final_z):
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


def cap_open_loops(staff, labels, ccfg, to_final_z):
    """Fan-fill open boundary loops of one staff part below a height (the shaft bottom)."""
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


def to_final_point(p, frame, xform):
    if frame == "final":
        return Vector(p)
    s, cx, cy, fz, base_top_src = xform
    return Vector(((p[0] - cx) * s, (p[1] - cy) * s, fz + (p[2] - base_top_src) * s))


def make_armature(scene, profile, xform):
    cfg = profile["armature"]
    data = bpy.data.armatures.new(cfg["object"])
    arm = bpy.data.objects.new(cfg["object"], data)
    scene.collection.objects.link(arm)
    final = {}
    with scene_context(scene):
        bpy.ops.object.select_all(action="DESELECT")
        bpy.context.view_layer.objects.active = arm
        bpy.ops.object.mode_set(mode="EDIT")
        for name, parent, head, tail, frame in cfg["bones"]:
            bone = data.edit_bones.new(name)
            bone.head, bone.tail = to_final_point(head, frame, xform), to_final_point(tail, frame, xform)
            final[name] = [rv(bone.head, 5), rv(bone.tail, 5)]
            if parent:
                bone.parent = data.edit_bones[parent]
            bone.use_connect = False
        bpy.ops.object.mode_set(mode="OBJECT")
    for bone in arm.pose.bones:
        bone.rotation_mode = "XYZ"
    return arm, final


def point_segment_distance(p, a, b):
    ab = b - a
    t = max(0.0, min(1.0, (p - a).dot(ab) / ab.length_squared)) if ab.length_squared else 0.0
    return (p - (a + ab * t)).length


def heat_weights(scene, arm, objects, allowed):
    """Blender automatic weights restricted to `allowed` bones (others temporarily non-deforming)."""
    saved = {b.name: b.use_deform for b in arm.data.bones}
    for b in arm.data.bones:
        b.use_deform = b.name in allowed
    try:
        with scene_context(scene):
            bpy.ops.object.select_all(action="DESELECT")
            for obj in objects:
                obj.select_set(True)
            arm.select_set(True)
            bpy.context.view_layer.objects.active = arm
            bpy.ops.object.parent_set(type="ARMATURE_AUTO")
    finally:
        for b in arm.data.bones:
            b.use_deform = saved[b.name]


def rigid_weights(arm, obj, bone):
    group = obj.vertex_groups.get(bone) or obj.vertex_groups.new(name=bone)
    group.add(list(range(len(obj.data.vertices))), 1.0, "REPLACE")
    obj.parent = arm
    if not any(m.type == "ARMATURE" for m in obj.modifiers):
        obj.modifiers.new("Armature", "ARMATURE").object = arm


def ramp_factor(ramp, z, to_final_z):
    """Fraction of the ramped bones' weight that is KEPT at height z (smoothstep)."""
    if "zero_above_z" in ramp:
        a, b = to_final_z(ramp["zero_above_z"]), to_final_z(ramp["full_below_z"])
        f = (a - z) / (a - b)
    else:
        a, b = to_final_z(ramp["zero_below_z"]), to_final_z(ramp["full_above_z"])
        f = (z - a) / (b - a)
    f = max(0.0, min(1.0, f))
    return f * f * (3 - 2 * f)


def cleanup_weights(arm, obj, allowed, rule, max_influences, clean_below, to_final_z):
    """Weight cleanup of one part: (1) keep only the group's bones, normalise, nearest-bone fallback for
    vertices the heat solve left empty; (2) height ramps, caps, drop < clean_below, keep the strongest
    max_influences, normalise. No edge smoothing (Arthur 2026-09-28: it raised the probe-pose stretch)."""
    bones = {b.name: (arm.matrix_world @ b.head_local, arm.matrix_world @ b.tail_local) for b in arm.data.bones}
    names = {g.index: g.name for g in obj.vertex_groups}
    groups = {g.name: g for g in obj.vertex_groups}
    for name in allowed:
        if name not in groups:
            groups[name] = obj.vertex_groups.new(name=name)
    caps = rule.get("caps") or {}
    excess_by_bone = rule.get("cap_excess_to_by_bone") or {}
    excess_to = rule.get("cap_excess_to")
    stats = Counter()
    mw = obj.matrix_world
    mesh = obj.data
    weights = []
    for v in mesh.vertices:
        ws = {}
        for g in v.groups:
            n = names.get(g.group)
            if n in allowed and g.weight > 0:
                ws[n] = ws.get(n, 0.0) + g.weight
            elif g.weight > 0:
                stats["foreign_weights_removed"] += 1
        total = sum(ws.values())
        if total <= 0:
            p = mw @ v.co
            best = min(sorted(allowed), key=lambda n: point_segment_distance(p, *bones[n]))
            ws = {best: 1.0}
            stats["fallback_nearest_bone"] += 1
        else:
            ws = {n: w / total for n, w in ws.items()}
        weights.append(ws)
    for v, ws in zip(mesh.vertices, weights):
        z = (mw @ v.co).z
        for ramp in rule.get("height_ramps") or []:
            f = ramp_factor(ramp, z, to_final_z)
            for bone in ramp["bones"]:
                w = ws.get(bone, 0.0)
                if w > 0 and f < 1.0:
                    ws[bone] = w * f
                    ws[ramp["to"]] = ws.get(ramp["to"], 0.0) + w * (1.0 - f)
                    stats["height_ramped"] += 1
        for bone, cap in sorted(caps.items()):
            if ws.get(bone, 0.0) > cap:
                extra = ws[bone] - cap
                ws[bone] = cap
                target = excess_by_bone.get(bone, excess_to)
                ws[target] = ws.get(target, 0.0) + extra
                stats["capped"] += 1
        kept = {n: w for n, w in ws.items() if w >= clean_below}
        if not kept:
            kept = {max(ws, key=ws.get): 1.0}
        if len(kept) > max_influences:
            kept = dict(sorted(kept.items(), key=lambda kv: (-kv[1], kv[0]))[:max_influences])
            stats["limited_to_max_influences"] += 1
        total = sum(kept.values())
        kept = {n: w / total for n, w in kept.items()}
        for g in list(v.groups):
            obj.vertex_groups[g.group].remove([v.index])
        for n, w in sorted(kept.items()):
            groups[n].add([v.index], w, "REPLACE")
    for g in list(obj.vertex_groups):
        if g.name not in allowed:
            obj.vertex_groups.remove(g)
    return dict(sorted(stats.items()))


def flip_polygons(mesh, selected):
    source_vertices = {p.index: frozenset(p.vertices) for p in mesh.polygons}
    source_normals = {(p.index, mesh.loops[li].vertex_index): mesh.corner_normals[li].vector.copy()
                      for p in mesh.polygons for li in p.loop_indices}
    editable = bmesh.new()
    editable.from_mesh(mesh)
    editable.faces.index_update()
    for face in editable.faces:
        if face.index in selected:
            face.normal_flip()
    editable.to_mesh(mesh)
    editable.free()
    if not all(frozenset(p.vertices) == source_vertices[p.index] for p in mesh.polygons):
        raise RuntimeError("BMesh reordered polygons")
    normals = [None] * len(mesh.loops)
    for p in mesh.polygons:
        for li in p.loop_indices:
            n = source_normals[(p.index, mesh.loops[li].vertex_index)].copy()
            if p.index in selected:
                n.negate()
            normals[li] = n
    mesh.normals_split_custom_set(normals)
    mesh.update()


def transform_for_fbx(scene, arm, meshes, matrix):
    with scene_context(scene):
        bpy.ops.object.select_all(action="DESELECT")
        bpy.context.view_layer.objects.active = arm
        bpy.ops.object.mode_set(mode="EDIT")
        for bone in arm.data.edit_bones:
            bone.transform(matrix, scale=False, roll=True)
        bpy.ops.object.mode_set(mode="OBJECT")
    for obj in (arm,) + tuple(meshes):
        obj.location = matrix @ obj.location
    for mesh in meshes:
        mesh.data.transform(matrix)


def export_fbx(scene, path, objects, active, object_types, preset):
    with scene_context(scene):
        bpy.ops.object.select_all(action="DESELECT")
        for obj in objects:
            obj.select_set(True)
        bpy.context.view_layer.objects.active = active
        bpy.ops.export_scene.fbx(
            filepath=str(path), use_selection=True, object_types=object_types,
            apply_unit_scale=bool(preset["apply_unit_scale"]), apply_scale_options=preset["apply_scale_options"],
            axis_forward=preset["axis_forward"], axis_up=preset["axis_up"],
            use_triangles=bool(preset["use_triangles"]), mesh_smooth_type=preset["mesh_smooth_type"],
            add_leaf_bones=bool(preset["add_leaf_bones"]), primary_bone_axis=preset["primary_bone_axis"],
            secondary_bone_axis=preset["secondary_bone_axis"], bake_anim=False, use_custom_props=False,
            path_mode=PATH_MODE, embed_textures=False,
        )
    patch_fbx_units(path, float(preset["patch_fbx_unit_scale_to"]))


def to_authored_frame(scene, inverse):
    for obj in scene.objects:
        if obj.parent is None:
            obj.matrix_world = inverse @ obj.matrix_world
    scene.view_layers[0].update()


def import_fbx_into(scene, path):
    with scene_context(scene):
        bpy.ops.import_scene.fbx(filepath=str(path))


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


def labelled_objects(labelled):
    for obj, parts in labelled:
        for name in parts:
            yield name, obj, parts[name]


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


# ------------------------------------------------------------------------- main

def main():
    params = load_params()
    profile = json.loads(Path(params["profile"]).read_text(encoding="utf-8"))
    atlas = json.loads(Path(params["atlas_report"]).read_text(encoding="utf-8"))
    source = Path(params["source"])
    repo = Path(params["repo_root"])
    source_hash = sha256(source)
    preset_path = Path(params["fbx_preset"])
    preset = load_preset(preset_path)
    try:
        preset_rel = preset_path.resolve().relative_to(repo.resolve()).as_posix()
    except ValueError:
        preset_rel = preset_path.name
    rot = export_rotation(preset)
    rot3 = rot.to_3x3()
    data_scale = float(preset["temporary_data_scale"])
    front_export = rot3 @ Vector((0.0, -1.0, 0.0))
    weapon_side_export = rot3 @ Vector((-1.0, 0.0, 0.0))
    bpy.ops.wm.read_factory_settings(use_empty=True)
    checks = {}

    def check(name, passed, measured=None, expected=None, note=None):
        item = {"passed": bool(passed), "measured": measured}
        if expected is not None:
            item["expected"] = expected
        if note:
            item["note"] = note
        checks[name] = item

    m = profile["meshes"]
    size = atlas["size"]
    cells = atlas["cells"]
    rects = cell_rects(cells, size)
    scene = bpy.data.scenes.new(WORK_SCENE)
    scene.unit_settings.system = "METRIC"
    scene.unit_settings.scale_length = 1.0
    with scene_context(scene):
        bpy.ops.import_scene.gltf(filepath=str(source))
    parts = bake_parts(scene)
    if len(parts) != profile["expected_part_count"]:
        raise RuntimeError("expected %d mesh parts, found %d" % (profile["expected_part_count"], len(parts)))
    source_polys = {n: len(o.data.polygons) for n, o in sorted(parts.items())}
    captured = {n: capture_corner_normals(o) for n, o in sorted(parts.items())}

    # ---- drop degenerate parts (none expected for Merlin; kept data-driven)
    dropped = {}
    for name, why in sorted((m.get("drop_parts") or {}).items()):
        obj = parts.pop(name)
        lo, hi = world_bounds([obj])
        dropped[name] = {"reason": why, "polygons": len(obj.data.polygons), "vertices": len(obj.data.vertices),
                         "source_size": rv([hi[i] - lo[i] for i in range(3)], 6)}
        bpy.data.objects.remove(obj)
        captured.pop(name)

    # ---- scale and seat: figure uniform about the source base top, base to its footprint
    base = parts[m["base"]["part"]]
    blo, bhi = world_bounds([base])
    cx, cy = (blo[0] + bhi[0]) / 2, (blo[1] + bhi[1]) / 2
    base_top_src, base_bottom_src = bhi[2], blo[2]
    fx, fy, fz = m["base"]["footprint_m"]
    top_src = max(v.co.z for v in parts[profile["scale"]["top_part"]].data.vertices)
    s = (profile["scale"]["figure_height_m"] - fz) / (top_src - base_top_src)
    xform = (s, cx, cy, fz, base_top_src)

    def to_final_z(z_src):
        return fz + (z_src - base_top_src) * s

    base_linear = [[fx / (bhi[0] - blo[0]), 0, 0], [0, fy / (bhi[1] - blo[1]), 0], [0, 0, fz / (bhi[2] - blo[2])]]
    for name, obj in parts.items():
        if obj is base:
            for v in obj.data.vertices:
                v.co = Vector(((v.co.x - cx) * base_linear[0][0], (v.co.y - cy) * base_linear[1][1],
                               (v.co.z - base_bottom_src) * base_linear[2][2]))
        else:
            for v in obj.data.vertices:
                v.co = Vector(((v.co.x - cx) * s, (v.co.y - cy) * s, fz + (v.co.z - base_top_src) * s))
        obj.data.update()
    scale_info = {"source_base_top": r(base_top_src), "source_base_bottom": r(base_bottom_src),
                  "source_base_centre_xy": [r(cx), r(cy)], "source_top_of_top_part": r(top_src),
                  "figure_scale": r(s, 8), "base_scale_xyz": [r(base_linear[i][i], 8) for i in range(3)],
                  "figure_height_m": profile["scale"]["figure_height_m"], "base_height_m": fz,
                  "base_diameter_m": fx,
                  "tripo_base_diameter_at_figure_scale_m": r((bhi[0] - blo[0]) * s, 6)}

    # ---- atlas UVs + material
    files = {k: v["file"] for k, v in atlas["files"].items()}
    mat, mat_images = atlas_material(params["textures_dir"], files, "M_Merlin_Atlas")
    for name, obj in parts.items():
        remap_uvs(obj, cells[name], size)
        obj.data.materials.clear()
        obj.data.materials.append(mat)
        obj.data.update()

    # ---- weld inside every part; label faces with their part
    weld = {n: weld_part(o, profile["weld"]["distance_m"]) for n, o in sorted(parts.items())}
    for name, obj in parts.items():
        label_faces(obj, name)

    # ---- staff: join the staff parts, bridge the shaft inside the fist, cap the open bottom
    wparts = m["weapon"]["parts"]
    staff_objs = [parts.pop(n) for n in wparts]
    staff = join_objects(scene, staff_objs, staff_objs[0])
    staff.name = m["weapon"]["object"]
    staff.data.name = m["weapon"]["mesh"]
    srep = profile["staff_repair"]
    labels = read_face_labels(staff)
    axis_c, axis_d, shaft_r, axis_info = staff_axis(staff, labels, srep["grip_bridge"]["axis_rings_source_z"], to_final_z)
    bridge = grip_bridge(staff, labels, srep["grip_bridge"], axis_c, axis_d, shaft_r, to_final_z)
    labels = read_face_labels(staff)
    caps = cap_open_loops(staff, labels, srep["caps"], to_final_z)
    labels = read_face_labels(staff)
    staff_info = {"parts": wparts, "axis": axis_info, "grip_bridge": bridge, "caps": caps,
                  "islands_final": islands(staff.data)[1],
                  "part_polygons": {p: len(v) for p, v in sorted(labels.items())}}

    # corner normals back (figure: uniform scale = rotation-free, base: inverse-transpose of its scale)
    normals_after, normals_preserved = {}, {}
    for name, obj in sorted(parts.items()) + [("weapon", staff)]:
        normals_after[name] = apply_corner_normals(obj, base_linear if obj is base else None)
    for name, obj in sorted(parts.items()) + [("weapon", staff)]:
        mn, bad, zero = corner_normal_agreement(obj, normals_after[name])
        normals_preserved[name] = {"min_dot": r(mn, 5), "corners_below_0_999": bad,
                                   "zero_captured_corners_excluded": zero}
    for obj in list(parts.values()) + [staff]:
        obj.data.attributes.remove(obj.data.attributes[CN_ATTR])

    # ---- orientation (ray-escape) per part (staff parts separately); flip inside-out parts
    ocfg = profile["orientation"]
    labelled = [(o, {n: [p.index for p in o.data.polygons]}) for n, o in sorted(parts.items())]
    labelled.append((staff, {"weapon:" + p: list(ix) for p, ix in sorted(labels.items())}))
    orient_before = orientation_scores(labelled)
    inside_out = sorted(p for p, sc in orient_before.items()
                        if sc["score"] is not None and sc["score"] < ocfg["flip_below_score"])
    check("orientation_inside_out_parts_as_profile", inside_out == sorted(ocfg["expected_inside_out_parts"]),
          inside_out, sorted(ocfg["expected_inside_out_parts"]),
          "ray-escape score < %s on the Tripo geometry" % ocfg["flip_below_score"])
    for name in inside_out:
        if name.startswith("weapon:"):
            flip_polygons(staff.data, set(labels[name.split(":", 1)[1]]))
        else:
            flip_polygons(parts[name].data, {p.index for p in parts[name].data.polygons})
    orient_after = orientation_scores(labelled)
    bad_after = sorted(p for p, sc in orient_after.items() if sc["score"] is None or sc["score"] < ocfg["min_score_after_fix"])
    check("orientation_all_parts_outward_after_fix", not bad_after,
          {p: sc["score"] for p, sc in sorted(orient_after.items())}, ">= %s" % ocfg["min_score_after_fix"])
    opposed = {n: opposed_corner_fraction(o, ix) for n, o, ix in labelled_objects(labelled)}
    check("corner_normals_agree_with_winding", all(v <= ocfg["corner_normal_opposed_max_fraction"] for v in opposed.values()),
          opposed, "<= %s area share per part" % ocfg["corner_normal_opposed_max_fraction"],
          "area share of polygons whose mean custom corner normal points against the polygon normal")
    check("corner_normals_preserved_by_weld_seat_staff", all(v["min_dot"] > 0.999 for v in normals_preserved.values()),
          normals_preserved, "min dot > 0.999 against the captured import normals (base: inverse-transpose of its scale)")

    # ---- armature and weights
    arm, bones_final = make_armature(scene, profile, xform)
    bone_names = [b[0] for b in profile["armature"]["bones"]]
    wcfg_all = profile["weights"]
    rules = {}
    for rule in wcfg_all["groups"]:
        for part in rule["parts"]:
            rules[part] = rule
    body_part_names = sorted(n for n in parts if n != m["base"]["part"])
    missing_rules = sorted(set(body_part_names) - set(rules))
    if missing_rules:
        raise RuntimeError("no weight rule for parts %s" % missing_rules)
    for rule in wcfg_all["groups"]:
        objs = [parts[p] for p in rule["parts"] if p in parts]
        if "rigid" in rule:
            for obj in objs:
                rigid_weights(arm, obj, rule["rigid"])
        else:
            heat_weights(scene, arm, objs, set(rule["heat"]))
    rigid_weights(arm, staff, m["weapon"]["bone"])
    heat_stats = {}
    for name in body_part_names:
        rule = rules[name]
        allowed = {rule["rigid"]} if "rigid" in rule else set(rule["heat"])
        heat_stats[name] = cleanup_weights(arm, parts[name], allowed, rule, profile["armature"]["max_influences"],
                                           wcfg_all["clean_below"], to_final_z)
    per_part_weights = {n: weight_summary(parts[n], bone_names) for n in body_part_names}

    # ---- join body
    body = join_objects(scene, [parts[n] for n in body_part_names], parts[m["body"]["active_part"]])
    body.name = m["body"]["object"]
    body.data.name = m["body"]["mesh"]
    base.name = m["base"]["object"]
    base.data.name = m["base"]["mesh"]
    for mod in [md for md in body.modifiers if md.type == "ARMATURE"][1:]:
        body.modifiers.remove(mod)
    body_parts = read_face_labels(body)
    part_of_poly = {i: p for p, ix in body_parts.items() for i in ix}
    staff_parts = read_face_labels(staff)
    for obj in (body, staff, base):
        if PART_ATTR in obj.data.attributes:
            obj.data.attributes.remove(obj.data.attributes[PART_ATTR])
    uv_parts, unassigned = polygons_by_part(body.data, rects)
    uv_matches_parts = all(sorted(uv_parts.get(p, [])) == sorted(ix) for p, ix in body_parts.items())
    uv_staff, unassigned_staff = polygons_by_part(staff.data, rects)
    uv_staff_matches = all(sorted(uv_staff.get(p, [])) == sorted(ix) for p, ix in staff_parts.items())

    # ---- measurements (authored frame, metres)
    pre = {m["body"]["object"]: mesh_summary(body), m["weapon"]["object"]: mesh_summary(staff),
           m["base"]["object"]: mesh_summary(base)}
    weights = {"body": weight_summary(body, bone_names), "weapon": weight_summary(staff, bone_names)}
    labelled_final = [(body, body_parts), (staff, {"weapon:" + p: ix for p, ix in sorted(staff_parts.items())}),
                      (base, {m["base"]["part"]: [p.index for p in base.data.polygons]})]
    uv_stats = uv_statistics(labelled_final, cells, size, 100.0)
    lo_sk, hi_sk = world_bounds([body, staff])
    lo_body, hi_body = world_bounds([body])
    lo_base, hi_base = world_bounds([base])
    lo_all, hi_all = world_bounds([body, staff, base])

    def part_points(obj, ix):
        return [obj.data.vertices[v].co for v in sorted({v for i in ix for v in obj.data.polygons[i].vertices})]

    head_ix = body_parts[profile["scale"]["top_part"]]
    head_pts = part_points(body, head_ix)
    head_top = max(p.z for p in head_pts)
    feet_parts = {"L": "tripo_part_7", "R": "tripo_part_6"}
    feet_low = min(p.z for side in feet_parts.values() for p in part_points(body, body_parts[side]))
    staff_c = centroid(staff)
    staff_top = max((staff.matrix_world @ v.co for v in staff.data.vertices), key=lambda p: p.z)
    toe_ankle = {}
    for side, part in sorted(feet_parts.items()):
        low = [p for p in part_points(body, body_parts[part]) if p.z < fz + 0.006]
        toe_y = min(p.y for p in low)
        heel_y = max(p.y for p in low)
        ankle = arm.data.bones["foot.%s" % side].head_local
        toe_ankle[side] = {"toe_y": r(toe_y, 5), "heel_y": r(heel_y, 5), "ankle_y": r(ankle.y, 5),
                           "toe_minus_ankle": r(toe_y - ankle.y, 5), "heel_minus_ankle": r(heel_y - ankle.y, 5)}
    body_c = centroid(body)
    face_c = centroid(body, head_ix)
    lfist_c = centroid(body, body_parts["tripo_part_9"])
    radial = max(math.hypot(v.co.x, v.co.y) for o in (body, staff) for v in o.data.vertices)
    radial_body = max(math.hypot(v.co.x, v.co.y) for v in body.data.vertices)
    # weapon bone against the staff geometry
    wb = arm.data.bones[m["weapon"]["bone"]]
    tip_err = (wb.tail_local - staff_top).length
    head_axis_err = dist_to_line(wb.head_local, axis_c, axis_d)
    fist_pts = part_points(body, body_parts["tripo_part_8"])
    fist_lo = [min(p[i] for p in fist_pts) for i in range(3)]
    fist_hi = [max(p[i] for p in fist_pts) for i in range(3)]
    head_in_fist = all(fist_lo[i] <= wb.head_local[i] <= fist_hi[i] for i in range(3))
    bone_heads = {b.name: rv(b.head_local, 5) for b in arm.data.bones}
    # sockets
    head_centre = Vector([(min(p[a] for p in head_pts) + max(p[a] for p in head_pts)) / 2 for a in range(3)])
    crystal_pts = part_points(staff, staff_parts["tripo_part_10"])
    crystal_centre = Vector([(min(p[a] for p in crystal_pts) + max(p[a] for p in crystal_pts)) / 2 for a in range(3)])
    sockets = []
    for sock in profile["sockets"]:
        bone = arm.data.bones[sock["bone"]]
        target = head_centre if sock["name"] == "Head" else bone.head_local.copy()
        local = bone.matrix_local.inverted() @ target
        entry = {"name": sock["name"], "bone": sock["bone"], "target_blender_m": rv(target, 5),
                 "target_ue_component_uu": ue_from_blender_m(target),
                 "offset_blender_bone_local_uu": [r(c * 100, 3) for c in local],
                 "bone_head_ue_component_uu": ue_from_blender_m(bone.head_local)}
        if sock["name"] == "Weapon":
            tip_local = bone.matrix_local.inverted() @ crystal_centre
            entry["staff_tip_proposal"] = {"crystal_centre_blender_m": rv(crystal_centre, 5),
                                           "offset_blender_bone_local_uu": [r(c * 100, 3) for c in tip_local],
                                           "status": "предложено (AD-CNF-59 open)"}
        sockets.append(entry)
    root = arm.data.bones["root"]
    pivot = {"root_bone": root.name, "root_head_m": [r(c, 6) for c in root.head_local],
             "armature_object_location": [r(c, 6) for c in arm.location]}
    cross_part = cross_part_coincident(body, part_of_poly)

    blend_out = Path(params["blend_out"])
    blend_out.parent.mkdir(parents=True, exist_ok=True)
    bpy.data.libraries.write(str(blend_out), {scene}, compress=False)

    # ---- export (UM_FBX_v1) on the in-memory copy; the work .blend stays authored
    transform_for_fbx(scene, arm, (body, staff, base), Matrix.Scale(data_scale, 4) @ rot)
    sk_fbx, base_fbx = Path(params["sk_fbx_out"]), Path(params["base_fbx_out"])
    sk_fbx.parent.mkdir(parents=True, exist_ok=True)
    restore = make_fbx_deterministic()
    try:
        export_fbx(scene, sk_fbx, (arm, body, staff), arm, {"ARMATURE", "MESH"}, preset)
    finally:
        restore()
    restore = make_fbx_deterministic()
    try:
        export_fbx(scene, base_fbx, (base,), base, {"MESH"}, preset)
    finally:
        restore()

    # ---- round trip
    rt = bpy.data.scenes.new(ROUNDTRIP_SCENE)
    import_fbx_into(rt, sk_fbx)
    rtb = bpy.data.scenes.new(ROUNDTRIP_SCENE + "_base")
    import_fbx_into(rtb, base_fbx)
    raw = {re.sub(r"\.\d{3}$", "", o.name): o for sc in (rt, rtb) for o in sc.objects if o.type == "MESH"}
    for key in ("body", "weapon", "base"):
        if m[key]["object"] not in raw:
            raise RuntimeError("round trip lost meshes: %s" % sorted(raw))
    rb_export = raw[m["body"]["object"]]
    rb_parts_export, _ = polygons_by_part(rb_export.data, rects)
    lo_x, hi_x = world_bounds([raw[m["body"]["object"]], raw[m["weapon"]["object"]]])
    lo_xb, hi_xb = world_bounds([raw[m["base"]["object"]]])
    export_frame = {"weapon_centroid_m": centroid(raw[m["weapon"]["object"]]),
                    "body_centroid_m": centroid(rb_export),
                    "face_centroid_m": centroid(rb_export, rb_parts_export[profile["scale"]["top_part"]]),
                    "left_fist_centroid_m": centroid(rb_export, rb_parts_export["tripo_part_9"]),
                    "skeletal_bounds_cm": {"min": [r(c * 100, 3) for c in lo_x], "max": [r(c * 100, 3) for c in hi_x]},
                    "base_bounds_cm": {"min": [r(c * 100, 3) for c in lo_xb], "max": [r(c * 100, 3) for c in hi_xb]}}
    inverse = rot.inverted()
    to_authored_frame(rt, inverse)
    to_authored_frame(rtb, inverse)
    rt_sk, rt_sk_meshes = roundtrip_measure(rt, bone_names)
    rt_base, rt_base_meshes = roundtrip_measure(rtb, bone_names)
    rt_body, rt_staff, rt_base_obj = (rt_sk_meshes[m["body"]["object"]], rt_sk_meshes[m["weapon"]["object"]],
                                      rt_base_meshes[m["base"]["object"]])
    rt_parts, rt_unassigned = polygons_by_part(rt_body.data, rects)
    rt_staff_parts, rt_unassigned_staff = polygons_by_part(rt_staff.data, rects)
    rt_labelled = [(rt_body, rt_parts), (rt_staff, {"weapon:" + p: ix for p, ix in sorted(rt_staff_parts.items())}),
                   (rt_base_obj, {m["base"]["part"]: [p.index for p in rt_base_obj.data.polygons]})]
    orient_rt = orientation_scores(rt_labelled)
    rt_lo_sk, rt_hi_sk = world_bounds([rt_body, rt_staff])

    # ---------------------------------------------------------------- checks
    exp = profile["expectations"]
    tris = {n: pre[n]["triangles"] for n in pre}
    if all(v is not None for v in exp["triangles"].values()):
        check("triangles_as_profile", tris == exp["triangles"], tris, exp["triangles"])
    else:
        check("triangles_as_profile", True, tris, exp["triangles"], "profile expectations not fixed yet: measured only")
    check("dropped_parts_as_profile", sorted(dropped) == sorted(m.get("drop_parts") or {}), dropped)
    check("weld_inside_parts_measured", True, weld,
          note="bmesh remove_doubles at %s m inside each part; islands_after per part" % profile["weld"]["distance_m"])
    check("weapon_parts_as_profile", sorted(staff_parts) == sorted(wparts) and
          all(len(ix) > 0 for ix in staff_parts.values()), {p: len(ix) for p, ix in sorted(staff_parts.items())},
          sorted(wparts))
    gb = staff_info["grip_bridge"]
    check("weapon_grip_bridge_closes_gap", gb.get("added") is True and gb["to_t_m"] > gb["from_t_m"]
          and gb["triangles"] == 2 * srep["grip_bridge"]["sides"],
          gb, "an open %d-sided cylinder on the fitted shaft axis from source z %s to %s"
          % (srep["grip_bridge"]["sides"], srep["grip_bridge"]["from_source_z"], srep["grip_bridge"]["to_source_z"]),
          "Tripo modelled no shaft inside the fist; the staff was two shaft islands with a gap hidden by the fist")
    check("weapon_bottom_capped", len(caps) == srep["caps"]["expected_loops"] and all(c["triangles"] == c["loop_vertices"]
                                                                                   for c in caps),
          caps, "%d closed fan(s)" % srep["caps"]["expected_loops"])
    check("weapon_bone_on_staff", tip_err <= profile["armature"]["weapon_axis_tolerance_m"] and
          head_axis_err <= profile["armature"]["weapon_axis_tolerance_m"] and head_in_fist,
          {"tail_to_staff_top_m": r(tip_err, 5), "head_to_fitted_axis_m": r(head_axis_err, 5),
           "head_inside_fist_bounds": head_in_fist, "staff_top_m": rv(staff_top, 5),
           "fist_bounds_m": {"min": rv(fist_lo, 5), "max": rv(fist_hi, 5)}},
          "<= %s m" % profile["armature"]["weapon_axis_tolerance_m"])
    check("every_polygon_in_its_atlas_cell", unassigned == 0 and rt_unassigned == 0 and uv_matches_parts
          and unassigned_staff == 0 and rt_unassigned_staff == 0 and uv_staff_matches,
          {"body_build": unassigned, "body_roundtrip": rt_unassigned, "body_uv_cells_equal_part_labels": uv_matches_parts,
           "staff_build": unassigned_staff, "staff_roundtrip": rt_unassigned_staff,
           "staff_uv_cells_equal_part_labels": uv_staff_matches})
    uv_outside = sum(sv["loops_outside_cell_inner_rect"] for sv in uv_stats.values())
    check("uv0_single_layer_on_every_mesh", all(pre[n]["uv_layers"] == ["UVMap"] for n in pre),
          {n: pre[n]["uv_layers"] for n in pre})
    check("uv0_inside_unit_square", all(pre[n]["uv0_in_unit_square"] for n in pre),
          {n: pre[n]["uv0_in_unit_square"] for n in pre})
    check("uv0_inside_own_atlas_cell", uv_outside == 0, uv_outside,
          note="every UV corner lies in its part's inner cell rect (gutter kept)")
    check("uv0_raster_overlap_measured", True, {p: sv["overlap_ratio"] for p, sv in sorted(uv_stats.items())},
          note="informational: texels covered by >= 2 triangles / covered texels, per part at atlas resolution")
    check("weights_every_vertex_weighted", weights["body"]["unweighted_vertices"] == 0 and
          weights["weapon"]["unweighted_vertices"] == 0,
          {"body": weights["body"]["unweighted_vertices"], "weapon": weights["weapon"]["unweighted_vertices"]})
    check("weights_normalised", weights["body"]["not_normalised_vertices"] == 0 and
          weights["weapon"]["not_normalised_vertices"] == 0,
          {"body": weights["body"]["not_normalised_vertices"], "weapon": weights["weapon"]["not_normalised_vertices"]})
    check("weights_max_influences", max(weights["body"]["max_influences"], weights["weapon"]["max_influences"])
          <= profile["armature"]["max_influences"],
          max(weights["body"]["max_influences"], weights["weapon"]["max_influences"]), profile["armature"]["max_influences"])
    allowed_ok = {}
    for name in body_part_names:
        rule = rules[name]
        allowed = {rule["rigid"]} if "rigid" in rule else set(rule["heat"])
        allowed_ok[name] = sorted(set(per_part_weights[name]["bones_used"]) - allowed)
    check("weights_only_group_bones", not any(allowed_ok.values()), allowed_ok,
          note="per part: bones outside the group's list (must be empty)")
    fallback = {n: st.get("fallback_nearest_bone", 0) for n, st in heat_stats.items()}
    check("weights_heat_fallback_measured", True, fallback,
          note="vertices the heat solve left unweighted, given 1.0 on the nearest allowed bone (informational)")
    check("weapon_bound_only_to_weapon", list(weights["weapon"]["bones_used"]) == [m["weapon"]["bone"]],
          weights["weapon"]["bones_used"])
    height = hi_all[2] - lo_all[2]
    check("height_m", abs(head_top - profile["scale"]["figure_height_m"]) < 1e-5 and abs(lo_all[2]) < 1e-6,
          {"head_top": r(head_top, 6), "skeletal_top_staff_crystal": r(hi_sk[2], 6), "lowest": r(lo_all[2], 6),
           "figure_with_base_and_staff": r(height, 6)}, profile["scale"]["figure_height_m"])
    check("feet_on_base_top", abs(feet_low - fz) <= 0.003,
          {"lowest_foot_vertex_z": r(feet_low, 5), "base_top_z": fz}, "within 3 mm of the base top (source: shoes sink ~4 mm into the Tripo base)")
    base_dims = [r(hi_base[i] - lo_base[i], 6) for i in range(3)]
    check("base_footprint_and_pivot", all(abs(a - b) < 1e-6 for a, b in zip(base_dims, (fx, fy, fz)))
          and all(abs(lo_base[i] + hi_base[i]) < 1e-6 for i in range(2)) and abs(lo_base[2]) < 1e-6,
          {"dimensions_m": base_dims, "centre_xy_m": [r((lo_base[i] + hi_base[i]) / 2, 6) for i in range(2)],
           "bottom_z_m": r(lo_base[2], 6)}, {"dimensions_m": [fx, fy, fz], "centre_xy_m": [0, 0], "bottom_z_m": 0})
    check("pivot_root_at_origin", pivot["root_head_m"] == [0.0, 0.0, 0.0] and
          pivot["armature_object_location"] == [0.0, 0.0, 0.0], pivot)
    check("armature_object_name_contract", arm.name == profile["armature"]["object"], arm.name,
          profile["armature"]["object"])
    front_ok = (all(t["toe_minus_ankle"] < -0.02 and t["heel_minus_ankle"] < 0.03 + 1e-9 for t in toe_ankle.values())
                and face_c[1] - body_c[1] < -0.005 and lfist_c[1] - body_c[1] < -0.02)
    check("axes_front_minus_y", front_ok, {"feet": toe_ankle, "body_centroid_m": body_c, "face_part_centroid_m": face_c,
                                           "left_fist_centroid_m": lfist_c},
          "toes ahead of the ankles (-Y), face part ahead of the body centroid by > 5 mm, left fist by > 2 cm")
    check("axes_weapon_on_minus_x", staff_c[0] < -0.02, staff_c, "-X (Blender, character's right hand)")
    front_name, side_name = axis_name(front_export), axis_name(weapon_side_export)
    ef = export_frame
    rel_face = [ef["face_centroid_m"][i] - ef["body_centroid_m"][i] for i in range(3)]
    rel_fist = [ef["left_fist_centroid_m"][i] - ef["body_centroid_m"][i] for i in range(3)]
    rel_staff = [ef["weapon_centroid_m"][i] - ef["body_centroid_m"][i] for i in range(3)]
    face_along, _ = along(rel_face, front_export)
    fist_along, _ = along(rel_fist, front_export)
    staff_side, _ = along(rel_staff, weapon_side_export)
    check("export_frame_face_front_staff_on_rotated_right", face_along > 0.005 and fist_along > 0.02 and staff_side > 0.02,
          {"face_minus_body_along_front": face_along, "left_fist_minus_body_along_front": fist_along,
           "staff_minus_body_along_weapon_side": staff_side},
          "front %s, weapon side %s (authored -Y / -X rotated by %s deg about Z)"
          % (front_name, side_name, preset["export_space_rotation_z_degrees"]))
    all_tris = {n: [pre[n]["polygons"], pre[n]["triangles"]] for n in pre}
    rt_all = dict(rt_sk["meshes"], **rt_base["meshes"])
    check("triangulate_changes_no_geometry", all(p == t for p, t in all_tris.values()) and
          all(e["polygons"] == e["triangles"] for e in rt_all.values()),
          {"pre_export_polygons_triangles": all_tris,
           "roundtrip_polygons_triangles": {n: [e["polygons"], e["triangles"]] for n, e in sorted(rt_all.items())}},
          note="preset use_triangles=%s; the meshes are already all triangles" % preset["use_triangles"])
    check("roundtrip_one_armature", rt_sk["armatures"] == 1 and rt_base["armatures"] == 0 and
          rt_sk["armature_objects"] == [profile["armature"]["object"]],
          {"skeletal_fbx": rt_sk["armature_objects"], "base_fbx": rt_base["armatures"]})
    rt_bones = rt_sk["bones"]
    check("roundtrip_bones", sorted(rt_bones) == sorted(bone_names) and len(rt_bones) == exp["bones"],
          len(rt_bones), exp["bones"])
    parents_ok = all(rt_bones.get(n, {}).get("parent") == p for n, p, _h, _t, _f in profile["armature"]["bones"])
    heads_ok = all(rt_bones.get(n) and all(abs(a - b) < 1e-4 for a, b in zip(rt_bones[n]["head_m"], bones_final[n][0]))
                   for n in bone_names)
    check("roundtrip_bone_hierarchy_and_rest_positions", parents_ok and heads_ok,
          {"parents_ok": parents_ok, "heads_within_1e-4_m": heads_ok})
    rt_tris = {n: e["triangles"] for n, e in rt_all.items()}
    check("roundtrip_triangles_preserved", rt_tris == tris, rt_tris, tris)
    rt_slots = {n: e["material_slots"] for n, e in rt_all.items()}
    sk_unique = sorted({sl for n in (m["body"]["object"], m["weapon"]["object"]) for sl in rt_slots.get(n, []) if sl})
    check("roundtrip_material_slots", len(sk_unique) == exp["skeletal_material_slots"] and
          len(rt_slots.get(m["base"]["object"], [])) == exp["base_material_slots"],
          {"per_mesh": rt_slots, "skeletal_unique": sk_unique},
          {"skeletal_unique": exp["skeletal_material_slots"], "base": exp["base_material_slots"]})
    check("roundtrip_uv0", all(e["uv_layers"] == ["UVMap"] and e["uv0_in_unit_square"] for e in rt_all.values()),
          {n: e["uv_layers"] for n, e in rt_all.items()})
    rt_w = {n: e["weights"] for n, e in rt_sk["meshes"].items()}
    check("roundtrip_weights", rt_w[m["body"]["object"]]["unweighted_vertices"] == 0 and
          list(rt_w[m["weapon"]["object"]]["bones_used"]) == [m["weapon"]["bone"]] and
          max(w["max_influences"] for w in rt_w.values()) <= profile["armature"]["max_influences"],
          {n: {k: w[k] for k in ("max_influences", "unweighted_vertices", "not_normalised_vertices")}
           for n, w in rt_w.items()})
    rt_bad = sorted(p for p, sc in orient_rt.items() if sc["score"] is None or sc["score"] < ocfg["min_score_after_fix"])
    check("roundtrip_orientation_all_parts_outward", not rt_bad,
          {p: sc["score"] for p, sc in sorted(orient_rt.items())}, ">= %s" % ocfg["min_score_after_fix"])
    ratio = [r((rt_hi_sk[i] - rt_lo_sk[i]) / (hi_sk[i] - lo_sk[i]), 6) for i in range(3)]
    check("roundtrip_scale_ratio_1", all(abs(v - 1) < 1e-4 for v in ratio), ratio,
          note="Blender re-reads the cm FBX (UnitScaleFactor 1.0) as metres")
    check("roundtrip_part_polygon_counts", {p: len(v) for p, v in sorted(rt_parts.items())} ==
          {p: len(v) for p, v in sorted(body_parts.items())} and
          {p: len(v) for p, v in sorted(rt_staff_parts.items())} == {p: len(v) for p, v in sorted(staff_parts.items())},
          {"body": {p: len(v) for p, v in sorted(rt_parts.items())},
           "staff": {p: len(v) for p, v in sorted(rt_staff_parts.items())}})
    lim = profile["proposed_limits_for_comparison_only"]
    comparison = {
        "hero_triangles": {"measured": sum(tris[n] for n in (m["body"]["object"], m["weapon"]["object"])),
                           "with_base": sum(tris.values()), "proposed": lim["hero_triangles"]},
        "texture_px": {"measured": size, "proposed": lim["texture_px"],
                       "note": "2K atlas at native part-texture size; the 1K proposal can be met on import (MaxTextureSize 1024)"},
        "material_slots": {"measured_skeletal_unique": len(sk_unique), "base": len(rt_slots.get(m["base"]["object"], [])),
                           "proposed_max": lim["material_slots_max"]},
        "height_uu": {"measured_head_top": r(head_top * 100, 3), "staff_top": r(hi_sk[2] * 100, 3),
                      "proposed": lim["height_uu"]},
        "base_uu": {"measured": [r(c * 100, 3) for c in base_dims], "proposed_diameter": lim["base_diameter_uu"],
                    "proposed_height": lim["base_height_uu"]},
        "capsule_uu": {"max_radius_from_pivot_axis": r(radial * 100, 3), "body_max_radius": r(radial_body * 100, 3),
                       "top": r(hi_sk[2] * 100, 3), "proposed": lim["capsule_uu"],
                       "fits": bool(radial * 100 <= lim["capsule_uu"]["diameter"] / 2 + 1e-6
                                    and hi_sk[2] * 100 <= lim["capsule_uu"]["height"])},
        "footprint_vs_base": {"body_max_radius_uu": r(radial_body * 100, 3), "base_radius_uu": r(fx * 50, 3),
                              "note": "the robe hem reaches past the base rim by this margin (informational)"},
        "note": "comparison with proposals only, not budgets (GD-058 open)"}

    report = {
        "stage": "build",
        "builder": BUILDER,
        "builder_sha256": sha256(Path(__file__)) if "__file__" in globals() else None,
        "blender": bpy.app.version_string,
        "profile": {"id": profile["profile_id"], "status": profile["status"]},
        "source": {"file": source.name, "sha256": source_hash},
        "isolation_note": "process",
        "scale": scale_info,
        "source_part_polygons": source_polys,
        "dropped_parts": dropped,
        "weld": weld,
        "weapon_assembly": staff_info,
        "body_parts": sorted(body_parts),
        "body_part_polygons": {p: len(v) for p, v in sorted(body_parts.items())},
        "cross_part_coincident_vertices": cross_part,
        "orientation": {"method": ocfg["method"], "before_fix": orient_before, "flipped_parts": inside_out,
                        "after_fix": orient_after, "roundtrip": orient_rt, "corner_normals_opposed_area_share": opposed,
                        "corner_normals_preserved": normals_preserved},
        "materials": {"atlas": "M_Merlin_Atlas", "blender_images": mat_images},
        "meshes_pre_export_m": pre,
        "weights": weights,
        "weights_per_part": per_part_weights,
        "weights_cleanup": heat_stats,
        "uv": uv_stats,
        "bones_final_m": bones_final,
        "bones_head_m": bone_heads,
        "sockets": sockets,
        "bounds_m": {"skeletal": {"min": [r(c) for c in lo_sk], "max": [r(c) for c in hi_sk]},
                     "body": {"min": [r(c) for c in lo_body], "max": [r(c) for c in hi_body]},
                     "base": {"min": [r(c) for c in lo_base], "max": [r(c) for c in hi_base]},
                     "figure_with_base_height": r(height), "head_top": r(head_top)},
        "expected_ue_bounds_uu_at_import_scale_1": {
            "skeletal_blender_axes": {"min": [r(c * 100, 3) for c in lo_sk], "max": [r(c * 100, 3) for c in hi_sk]},
            "base_blender_axes": {"min": [r(c * 100, 3) for c in lo_base], "max": [r(c * 100, 3) for c in hi_base]},
            "export_rotation_z_degrees": float(preset["export_space_rotation_z_degrees"]),
            "skeletal_export_frame": export_frame["skeletal_bounds_cm"],
            "base_export_frame": export_frame["base_bounds_cm"],
            "skeletal_ue_predicted": ue_predicted(export_frame["skeletal_bounds_cm"]),
            "base_ue_predicted": ue_predicted(export_frame["base_bounds_cm"]),
            "note": "*_blender_axes: authored frame (front -Y), centimetres; *_export_frame: as written into the FBX "
                    "(re-imported); *_ue_predicted: export frame mapped as UE (x, -y, z) per ART-001"},
        "axes": {"staff_centroid_m": staff_c, "feet": toe_ankle, "body_centroid_m": body_c,
                 "face_part_centroid_m": face_c, "left_fist_centroid_m": lfist_c,
                 "export_frame": {k: export_frame[k] for k in ("weapon_centroid_m", "body_centroid_m",
                                                               "face_centroid_m", "left_fist_centroid_m")},
                 "export_front_axis": front_name, "export_weapon_side_axis": side_name},
        "pivot": pivot,
        "exports": {"skeletal": {"file": sk_fbx.name, "sha256": sha256(sk_fbx), "bytes": sk_fbx.stat().st_size},
                    "base": {"file": base_fbx.name, "sha256": sha256(base_fbx), "bytes": base_fbx.stat().st_size},
                    "settings": {"preset": {"name": preset["name"], "version": preset.get("version"),
                                            "path": preset_rel, "sha256": sha256(preset_path)},
                                 "apply_unit_scale": bool(preset["apply_unit_scale"]),
                                 "apply_scale_options": preset["apply_scale_options"],
                                 "axis_forward": preset["axis_forward"], "axis_up": preset["axis_up"],
                                 "export_space_rotation_z_degrees": float(preset["export_space_rotation_z_degrees"]),
                                 "bone_rotation": "EditBone.transform(roll=True): rest pose rotated rigidly",
                                 "data_scale": data_scale,
                                 "unit_scale_factor_after_patch": float(preset["patch_fbx_unit_scale_to"]),
                                 "use_triangles": bool(preset["use_triangles"]),
                                 "add_leaf_bones": bool(preset["add_leaf_bones"]),
                                 "primary_bone_axis": preset["primary_bone_axis"],
                                 "secondary_bone_axis": preset["secondary_bone_axis"],
                                 "mesh_smooth_type": preset["mesh_smooth_type"], "bake_anim": False,
                                 "path_mode": PATH_MODE, "embed_textures": False,
                                 "deviations_from_preset": {
                                     "path_mode": "%s instead of %s: bare texture names; textures reach UE from the "
                                                  "atlas stage, not through the FBX" % (PATH_MODE, preset["path_mode"]),
                                     "bake_anim": "off: the candidate FBX carries no clips"},
                                 "creation_time_pinned": FIXED_TIME.isoformat()}},
        "roundtrip": {"skeletal": rt_sk, "base": rt_base, "scale_ratio": ratio},
        "reference_comparison": None,
        "proposed_limits_comparison": comparison,
        "checks": checks,
        "passed": all(c["passed"] for c in checks.values()),
        "status": "technically_exported_not_art_accepted",
        "not_checked": [
            "art acceptance, silhouette, lighting, K1/K2/K3 (art track)",
            "deformation quality in animation; clips are not built by this stage (rig_deform_probe runs separately)",
            "budgets: numbers are measured only (proposals until GD-058)",
            "UV intra-part island padding (Tripo's own layout inside each cell)",
            "selection collision (04 §3.4 UCP_ 28x54 uu proposal; skeletal meshes use a physics asset in UE)",
            "UE-side facing and sockets: ue-import stage (deferred)",
        ],
    }
    out = Path(params["report_out"])
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=2, sort_keys=True, ensure_ascii=False) + "\n", encoding="utf-8")
    if sha256(source) != source_hash:
        raise RuntimeError("source GLB changed during build")
    if not report["passed"]:
        raise RuntimeError("build checks failed: %s" % sorted(k for k, c in checks.items() if not c["passed"]))
    print(MARKER, "isolation=process", "sk=%s" % report["exports"]["skeletal"]["sha256"][:12],
          "base=%s" % report["exports"]["base"]["sha256"][:12])


main()
