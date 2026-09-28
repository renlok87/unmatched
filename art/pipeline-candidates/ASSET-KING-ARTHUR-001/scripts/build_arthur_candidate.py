"""Stage `build` for King Arthur (ASSET-KING-ARTHUR-001): segmented Tripo GLB -> skeletal candidate
(body + separate sword) and a separate static base, UM_FBX_v1.

Headless only (`blender -b --factory-startup`), never in a live Blender (read_factory_settings):

    blender -b --factory-startup --python build_arthur_candidate.py -- <params.json>

params.json has the keys of tools/tripo-pipeline/tripo_pipeline.py exec_build:
    {"source", "profile", "atlas_report", "textures_dir", "repo_root", "blend_out",
     "sk_fbx_out", "base_fbx_out", "report_out", "fbx_preset"}

Why not tools/tripo-pipeline/blender/build_candidate.py (0.4.0): it hard-codes Medusa — the weapon is a
whole GLB part bound on the +X side (check axes_bow_on_plus_x), the face part defaults to tripo_part_10
and the neck check reads tripo_part_14. Arthur holds the sword in the right hand (-X) and Tripo fused the
sword with the right gauntlet in tripo_part_12. This script keeps that file's algorithm and report format
(helpers copied, not imported: build_candidate.py runs main() at import) and adds, data-driven by the
build profile:
  * dropped parts (tripo_part_14, degenerate);
  * figure scaled about the source base top and seated on the normalised base (the Medusa build stretched
    the base upward into the feet);
  * weld inside every part with corner normals preserved (captured once, re-applied);
  * sword split off tripo_part_12 (height bands + base-colour saturation + distance to the fitted
    sword axis, then island smoothing);
  * Blender automatic weights (bone heat) per part group restricted to the group's bones, rigid groups,
    caps, cleanup (<0.01, max 4, normalised, nearest-bone fallback);
  * armature object SKEL_UM_Humanoid (rig-contract proposal), weapon bone on the sword axis;
  * closure (verify 2026-09-28): the Tripo footprint holes in the base top are capped flat with UVs moved
    onto clean stone (the dark hole texels and the baked bronze boot fringe are no longer sampled), the
    open boot soles of the foot parts are capped; checks: base without boundary edges, soles closed,
    no see-through with back faces culled (ray test through the base top disc, build and round trip).
The report is deterministic (rounded floats, sorted keys, no timestamps). Nothing outside the params'
output paths is written; the source GLB is only read.
"""

import colorsys
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
from mathutils import Matrix, Vector, geometry
from mathutils.bvhtree import BVHTree
from mathutils.kdtree import KDTree

if not bpy.app.background:
    raise RuntimeError("build_arthur_candidate.py: headless only (blender -b)")

MARKER = "TRIPO_PIPELINE_STAGE_OK build"
BUILDER = "art/pipeline-candidates/ASSET-KING-ARTHUR-001/scripts/build_arthur_candidate.py"
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
    """Min dot between the current corner normals and `expected` (N x 3)."""
    mesh = obj.data
    arr = np.empty(len(mesh.loops) * 3, dtype=np.float32)
    mesh.corner_normals.foreach_get("vector", arr)
    arr = arr.reshape(-1, 3)
    dots = np.einsum("ij,ij->i", arr, expected)
    return float(dots.min()) if len(dots) else 1.0, int((dots < 0.999).sum())


def opposed_corner_fraction(obj):
    """Area share of polygons whose custom corner normals point against the polygon (winding) normal."""
    mesh = obj.data
    cn = np.empty(len(mesh.loops) * 3, dtype=np.float32)
    mesh.corner_normals.foreach_get("vector", cn)
    cn = cn.reshape(-1, 3)
    opposed = total = 0.0
    for p in mesh.polygons:
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
    """Connected components of polygons over shared edges; returns (count, sizes desc)."""
    edge_faces = defaultdict(list)
    allowed = set(range(len(mesh.polygons))) if polys is None else set(polys)
    for p in mesh.polygons:
        if p.index in allowed:
            for ek in p.edge_keys:
                edge_faces[ek].append(p.index)
    seen, sizes, comps = set(), [], []
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


def fit_axis(points):
    pts = np.array(points, dtype=np.float64)
    c = pts.mean(axis=0)
    _u, _s, vt = np.linalg.svd(pts - c)
    d = vt[0]
    if d[2] < 0:
        d = -d
    return Vector(c), Vector(d).normalized()


def dist_to_line(p, c, d):
    v = Vector(p) - c
    return (v - d * v.dot(d)).length


def split_weapon(scene, obj, cfg, bc_pixels, bc_size, atlas_cell, atlas_size):
    """Classify polygons of the fused sword+fist part; returns (hand_obj, sword_obj, info)."""
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


def grip_bridge(sword, bcfg, axis_c, axis_d):
    """Close the grip Tripo never modelled inside the fist: an open triangle-strip cylinder on the fitted
    sword axis from the top of the lowest sword island (grip stub + pommel) to the bottom of the highest
    island (guard + blade), both overlapped by `overlap_m`. Radius = median distance to the axis of the
    stub vertices within `near_top_m` of its top. UVs: a small rectangle inside the largest grip polygon's
    UV triangle (leather texels, non-degenerate for tangents). Corner normals: radial."""
    mesh = sword.data
    n, sizes, comps = islands(mesh)
    if n < 2:
        return {"added": False, "reason": "sword is a single island"}

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


# ------------------------------------------------------------------ hole caps (verify 2026-09-28)

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
    """Close the open boot soles of a foot part (boundary loops entirely below z_max): flat fill, normal
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


def make_armature(scene, profile):
    cfg = profile["armature"]
    data = bpy.data.armatures.new(cfg["object"])
    arm = bpy.data.objects.new(cfg["object"], data)
    scene.collection.objects.link(arm)
    with scene_context(scene):
        bpy.ops.object.select_all(action="DESELECT")
        bpy.context.view_layer.objects.active = arm
        bpy.ops.object.mode_set(mode="EDIT")
        for name, parent, head, tail in cfg["bones"]:
            bone = data.edit_bones.new(name)
            bone.head, bone.tail = Vector(head), Vector(tail)
            if parent:
                bone.parent = data.edit_bones[parent]
            bone.use_connect = False
        bpy.ops.object.mode_set(mode="OBJECT")
    for bone in arm.pose.bones:
        bone.rotation_mode = "XYZ"
    return arm


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


def cleanup_weights(arm, obj, allowed, rule, max_influences, clean_below):
    """Weight cleanup of one part: (1) keep only the group's bones, normalise, nearest-bone fallback for
    vertices the heat solve left empty; (2) height ramps, caps, drop < clean_below, keep the strongest
    max_influences, normalise. No edge smoothing: Tripo's retopology has long edges joining distant regions and
    edge averaging raised the probe-pose stretch (tried 2026-09-28: arm_l_raise 1.46x -> 3.10x)."""
    bones = {b.name: (arm.matrix_world @ b.head_local, arm.matrix_world @ b.tail_local) for b in arm.data.bones}
    names = {g.index: g.name for g in obj.vertex_groups}
    groups = {g.name: g for g in obj.vertex_groups}
    for name in allowed:
        if name not in groups:
            groups[name] = obj.vertex_groups.new(name=name)
    caps = rule.get("caps") or {}
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
            a, b = ramp["zero_above_z"], ramp["full_below_z"]
            f = max(0.0, min(1.0, (a - z) / (a - b)))
            f = f * f * (3 - 2 * f)
            for bone in ramp["bones"]:
                w = ws.get(bone, 0.0)
                if w > 0 and f < 1.0:
                    ws[bone] = w * f
                    ws[ramp["to"]] = ws.get(ramp["to"], 0.0) + w * (1.0 - f)
                    stats["height_ramped"] += 1
        for bone, cap in caps.items():
            if ws.get(bone, 0.0) > cap:
                extra = ws[bone] - cap
                ws[bone] = cap
                ws[excess_to] = ws.get(excess_to, 0.0) + extra
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

    # ---- drop degenerate parts
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
    fig_linear = [[s, 0, 0], [0, s, 0], [0, 0, s]]
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
                  "figure_height_m": profile["scale"]["figure_height_m"], "base_height_m": fz}

    # ---- atlas UVs + material
    files = {k: v["file"] for k, v in atlas["files"].items()}
    mat, mat_images = atlas_material(params["textures_dir"], files, "M_KingArthur_Atlas")
    for name, obj in parts.items():
        remap_uvs(obj, cells[name], size)
        obj.data.materials.clear()
        obj.data.materials.append(mat)
        obj.data.update()

    # ---- weld inside every part, then split the sword off its part
    weld = {n: weld_part(o, profile["weld"]["distance_m"]) for n, o in sorted(parts.items())}
    bc_image = next(n.image for n in mat.node_tree.nodes if n.type == "TEX_IMAGE" and n.label == "BC")
    bc_px = np.array(bc_image.pixels[:], dtype=np.float32).reshape(bc_image.size[1], bc_image.size[0], 4)

    # ---- close the Tripo footprint holes of the base top and the open boot soles (verify 2026-09-28)
    ccfg = profile["caps"]
    n_image = next(n.image for n in mat.node_tree.nodes if n.type == "TEX_IMAGE" and n.label == "N_OpenGL")
    n_px = np.array(n_image.pixels[:], dtype=np.float32).reshape(n_image.size[1], n_image.size[0], 4)
    caps_info = {"base": cap_base_top(base, fz, base_linear, ccfg["base"], bc_px, n_px, cells[m["base"]["part"]], size),
                 "soles": {p: cap_soles(parts[p], ccfg["soles"]) for p in ccfg["soles"]["parts"]}}
    wcfg = profile["weapon_split"]
    hand, sword, split_info, (axis_c, axis_d) = split_weapon(scene, parts[wcfg["part"]], wcfg, bc_px,
                                                             bc_image.size[0], cells[wcfg["part"]], size)
    sword.name = m["weapon"]["object"]
    sword.data.name = m["weapon"]["mesh"]
    bridge = grip_bridge(sword, wcfg["grip_bridge"], axis_c, axis_d) if wcfg.get("grip_bridge") else None
    split_info["grip_bridge"] = bridge
    split_info["islands_final"] = islands(sword.data)[1]
    # corner normals back (figure: uniform scale = rotation-free, base: inverse-transpose of its scale)
    normals_after = {}
    for name, obj in list(parts.items()) + [("weapon:" + wcfg["part"], sword)]:
        normals_after[name] = apply_corner_normals(obj, base_linear if obj is base else None)
    normals_preserved = {}
    for name, obj in list(parts.items()) + [("weapon:" + wcfg["part"], sword)]:
        mn, bad = corner_normal_agreement(obj, normals_after[name])
        normals_preserved[name] = {"min_dot": r(mn, 5), "corners_below_0_999": bad}
    for obj in list(parts.values()) + [sword]:
        obj.data.attributes.remove(obj.data.attributes[CN_ATTR])

    # ---- orientation (ray-escape) per part and weapon; flip inside-out parts
    ocfg = profile["orientation"]
    labelled = [(o, {n: [p.index for p in o.data.polygons]}) for n, o in sorted(parts.items())]
    labelled.append((sword, {"weapon:" + wcfg["part"]: [p.index for p in sword.data.polygons]}))
    orient_before = orientation_scores(labelled)
    inside_out = sorted(p for p, sc in orient_before.items()
                        if sc["score"] is not None and sc["score"] < ocfg["flip_below_score"])
    check("orientation_inside_out_parts_as_profile", inside_out == sorted(ocfg["expected_inside_out_parts"]),
          inside_out, sorted(ocfg["expected_inside_out_parts"]),
          "ray-escape score < %s on the Tripo geometry" % ocfg["flip_below_score"])
    for name in inside_out:
        obj = sword if name.startswith("weapon:") else parts[name]
        flip_polygons(obj.data, {p.index for p in obj.data.polygons})
    orient_after = orientation_scores(labelled)
    bad_after = sorted(p for p, sc in orient_after.items() if sc["score"] is None or sc["score"] < ocfg["min_score_after_fix"])
    check("orientation_all_parts_outward_after_fix", not bad_after,
          {p: sc["score"] for p, sc in sorted(orient_after.items())}, ">= %s" % ocfg["min_score_after_fix"])
    opposed = {n: opposed_corner_fraction(o) for n, o in labelled_objects(labelled)}
    check("corner_normals_agree_with_winding", all(v <= ocfg["corner_normal_opposed_max_fraction"] for v in opposed.values()),
          opposed, "<= %s area share per part" % ocfg["corner_normal_opposed_max_fraction"],
          "area share of polygons whose mean custom corner normal points against the polygon normal")
    check("corner_normals_preserved_by_weld_split_seat", all(v["min_dot"] > 0.999 for v in normals_preserved.values()),
          normals_preserved, "min dot > 0.999 against the captured import normals (base: inverse-transpose of its scale)")

    # ---- armature and weights
    arm = make_armature(scene, profile)
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
    rigid_weights(arm, sword, m["weapon"]["bone"])
    heat_stats = {}
    for name in body_part_names:
        rule = rules[name]
        allowed = {rule["rigid"]} if "rigid" in rule else set(rule["heat"])
        heat_stats[name] = cleanup_weights(arm, parts[name], allowed, rule, profile["armature"]["max_influences"],
                                           wcfg_all["clean_below"])
    per_part_weights = {n: weight_summary(parts[n], bone_names) for n in body_part_names}

    # ---- join body
    for name in body_part_names:
        obj = parts[name]
        attr = obj.data.attributes.new(PART_ATTR, "INT", "FACE")
        attr.data.foreach_set("value", [int(name.split("_")[-1])] * len(obj.data.polygons))
    with scene_context(scene):
        bpy.ops.object.select_all(action="DESELECT")
        for name in body_part_names:
            parts[name].select_set(True)
        body = parts[m["body"]["active_part"]]
        bpy.context.view_layer.objects.active = body
        bpy.ops.object.join()
    body.name = m["body"]["object"]
    body.data.name = m["body"]["mesh"]
    base.name = m["base"]["object"]
    base.data.name = m["base"]["mesh"]
    for mod in [md for md in body.modifiers if md.type == "ARMATURE"][1:]:
        body.modifiers.remove(mod)
    part_of_poly = {}
    vals = [0] * len(body.data.polygons)
    body.data.attributes[PART_ATTR].data.foreach_get("value", vals)
    for i, v in enumerate(vals):
        part_of_poly[i] = "tripo_part_%d" % v
    body.data.attributes.remove(body.data.attributes[PART_ATTR])
    body_parts = defaultdict(list)
    for i, p in part_of_poly.items():
        body_parts[p].append(i)
    body_parts = dict(body_parts)
    uv_parts, unassigned = polygons_by_part(body.data, rects)
    uv_matches_parts = all(sorted(uv_parts.get(p, [])) == sorted(ix) for p, ix in body_parts.items())

    # ---- measurements (authored frame, metres)
    pre = {m["body"]["object"]: mesh_summary(body), m["weapon"]["object"]: mesh_summary(sword),
           m["base"]["object"]: mesh_summary(base)}
    weights = {"body": weight_summary(body, bone_names), "weapon": weight_summary(sword, bone_names)}
    labelled_final = [(body, body_parts), (sword, {"weapon:" + wcfg["part"]: [p.index for p in sword.data.polygons]}),
                      (base, {m["base"]["part"]: [p.index for p in base.data.polygons]})]
    uv_stats = uv_statistics(labelled_final, cells, size, 100.0)
    lo_sk, hi_sk = world_bounds([body, sword])
    lo_body, hi_body = world_bounds([body])
    lo_base, hi_base = world_bounds([base])
    lo_all, hi_all = world_bounds([body, sword, base])
    head_ix = body_parts[profile["scale"]["top_part"]]
    head_top = max(body.data.vertices[v].co.z for i in head_ix for v in body.data.polygons[i].vertices)
    feet_low = min(body.data.vertices[v].co.z for p in ("tripo_part_3", "tripo_part_4")
                   for i in body_parts[p] for v in body.data.polygons[i].vertices)
    sword_c = centroid(sword)
    sword_top = max((sword.matrix_world @ v.co for v in sword.data.vertices), key=lambda p: p.z)
    toe_ankle = {}
    for side, part, ankle_bone in (("L", "tripo_part_3", "foot.L"), ("R", "tripo_part_4", "foot.R")):
        vids = sorted({v for i in body_parts[part] for v in body.data.polygons[i].vertices})
        low = [body.data.vertices[v].co for v in vids if body.data.vertices[v].co.z < fz + 0.012]
        toe_y = min(p.y for p in low)
        heel_y = max(p.y for p in low)
        ankle = arm.data.bones[ankle_bone].head_local
        toe_ankle[side] = {"toe_y": r(toe_y, 5), "heel_y": r(heel_y, 5), "ankle_y": r(ankle.y, 5),
                           "toe_minus_ankle": r(toe_y - ankle.y, 5), "heel_minus_ankle": r(heel_y - ankle.y, 5)}
    radial = max(math.hypot(v.co.x, v.co.y) for o in (body, sword) for v in o.data.vertices)
    # weapon bone against the sword geometry
    wb = arm.data.bones[m["weapon"]["bone"]]
    tip_err = (wb.tail_local - sword_top).length
    head_axis_err = dist_to_line(wb.head_local, axis_c, axis_d)
    hand_vids = sorted({v for i in body_parts[wcfg["part"]] for v in body.data.polygons[i].vertices})
    hand_pts = [body.data.vertices[v].co for v in hand_vids]
    hand_lo = [min(p[i] for p in hand_pts) for i in range(3)]
    hand_hi = [max(p[i] for p in hand_pts) for i in range(3)]
    head_in_fist = all(hand_lo[i] <= wb.head_local[i] <= hand_hi[i] for i in range(3))
    # bone heads inside the skeletal bounds (sanity)
    bone_heads = {b.name: rv(b.head_local, 5) for b in arm.data.bones}
    # sockets
    head_bone = arm.data.bones["head"]
    head_centre = Vector([(min(body.data.vertices[v].co[a] for i in head_ix for v in body.data.polygons[i].vertices) +
                           max(body.data.vertices[v].co[a] for i in head_ix for v in body.data.polygons[i].vertices)) / 2
                          for a in range(3)])
    sockets = []
    for sock in profile["sockets"]:
        bone = arm.data.bones[sock["bone"]]
        if sock["name"] == "Head":
            target = head_centre
        else:
            target = bone.head_local.copy()
        local = bone.matrix_local.inverted() @ target
        sockets.append({"name": sock["name"], "bone": sock["bone"], "target_blender_m": rv(target, 5),
                        "target_ue_component_uu": ue_from_blender_m(target),
                        "offset_blender_bone_local_uu": [r(c * 100, 3) for c in local],
                        "bone_head_ue_component_uu": ue_from_blender_m(bone.head_local)})
    root = arm.data.bones["root"]
    pivot = {"root_bone": root.name, "root_head_m": [r(c, 6) for c in root.head_local],
             "armature_object_location": [r(c, 6) for c in arm.location]}
    cross_part = cross_part_coincident(body, part_of_poly)
    weld_diag = ccfg["diagnostic_weld_m"]
    closure = {"base_boundary_edges": boundary_edge_count(base, weld_diag)[0],
               "base_non_manifold_edges": boundary_edge_count(base, weld_diag)[1],
               "body_boundary_edges_below_z_max": boundary_edge_count(body, weld_diag, ccfg["soles"]["z_max_m"])[0],
               "body_boundary_edges_total_info": boundary_edge_count(body, weld_diag)[0],
               "see_through_base_only": see_through_rays([base], fz, ccfg["see_through"]),
               "see_through_rest_figure": see_through_rays([base, body, sword], fz, ccfg["see_through"])}

    blend_out = Path(params["blend_out"])
    blend_out.parent.mkdir(parents=True, exist_ok=True)
    bpy.data.libraries.write(str(blend_out), {scene}, compress=False)

    # ---- export (UM_FBX_v1) on the in-memory copy; the work .blend stays authored
    transform_for_fbx(scene, arm, (body, sword, base), Matrix.Scale(data_scale, 4) @ rot)
    sk_fbx, base_fbx = Path(params["sk_fbx_out"]), Path(params["base_fbx_out"])
    sk_fbx.parent.mkdir(parents=True, exist_ok=True)
    restore = make_fbx_deterministic()
    try:
        export_fbx(scene, sk_fbx, (arm, body, sword), arm, {"ARMATURE", "MESH"}, preset)
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
    lo_x, hi_x = world_bounds([raw[m["body"]["object"]], raw[m["weapon"]["object"]]])
    lo_xb, hi_xb = world_bounds([raw[m["base"]["object"]]])
    export_frame = {"weapon_centroid_m": centroid(raw[m["weapon"]["object"]]),
                    "body_centroid_m": centroid(raw[m["body"]["object"]]),
                    "skeletal_bounds_cm": {"min": [r(c * 100, 3) for c in lo_x], "max": [r(c * 100, 3) for c in hi_x]},
                    "base_bounds_cm": {"min": [r(c * 100, 3) for c in lo_xb], "max": [r(c * 100, 3) for c in hi_xb]}}
    inverse = rot.inverted()
    to_authored_frame(rt, inverse)
    to_authored_frame(rtb, inverse)
    rt_sk, rt_sk_meshes = roundtrip_measure(rt, bone_names)
    rt_base, rt_base_meshes = roundtrip_measure(rtb, bone_names)
    rt_body, rt_sword, rt_base_obj = (rt_sk_meshes[m["body"]["object"]], rt_sk_meshes[m["weapon"]["object"]],
                                      rt_base_meshes[m["base"]["object"]])
    rt_parts, rt_unassigned = polygons_by_part(rt_body.data, rects)
    rt_labelled = [(rt_body, rt_parts), (rt_sword, {"weapon:" + wcfg["part"]: [p.index for p in rt_sword.data.polygons]}),
                   (rt_base_obj, {m["base"]["part"]: [p.index for p in rt_base_obj.data.polygons]})]
    orient_rt = orientation_scores(rt_labelled)
    rt_lo_sk, rt_hi_sk = world_bounds([rt_body, rt_sword])
    rt_lo_b, rt_hi_b = world_bounds([rt_base_obj])
    closure["roundtrip"] = {
        "base_boundary_edges": boundary_edge_count(rt_base_obj, weld_diag)[0],
        "body_boundary_edges_below_z_max": boundary_edge_count(rt_body, weld_diag, ccfg["soles"]["z_max_m"])[0],
        "see_through_base_only": see_through_rays([rt_base_obj], fz, ccfg["see_through"])["missed_total"]}

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
    split_ok = (split_info["islands_after_split"]["sword"][:1] and
                all(n >= wcfg["min_island_polygons"] for n in split_info["islands_after_split"]["sword"]) and
                all(n >= wcfg["min_island_polygons"] for n in split_info["islands_after_split"]["hand"]))
    check("weapon_split_clean_islands", bool(split_ok), split_info["islands_after_split"],
          ">= %d polygons per island" % wcfg["min_island_polygons"])
    if wcfg.get("grip_bridge"):
        br = split_info["grip_bridge"] or {}
        check("weapon_grip_bridge_closes_gap", br.get("added") is True and br["to_t_m"] > br["from_t_m"]
              and br["triangles"] == 2 * wcfg["grip_bridge"]["sides"],
              br, "an open %d-sided cylinder overlapping both sword islands by %s m"
              % (wcfg["grip_bridge"]["sides"], wcfg["grip_bridge"]["overlap_m"]),
              "Tripo modelled no grip inside the fist; the split sword was two islands with a gap hidden by the fist")
    check("weapon_bone_on_sword", tip_err <= profile["armature"]["weapon_axis_tolerance_m"] and
          head_axis_err <= profile["armature"]["weapon_axis_tolerance_m"] and head_in_fist,
          {"tail_to_blade_tip_m": r(tip_err, 5), "head_to_fitted_axis_m": r(head_axis_err, 5),
           "head_inside_fist_bounds": head_in_fist, "blade_tip_m": rv(sword_top, 5)},
          "<= %s m" % profile["armature"]["weapon_axis_tolerance_m"])
    check("every_body_polygon_in_one_atlas_cell", unassigned == 0 and rt_unassigned == 0 and uv_matches_parts,
          {"build": unassigned, "roundtrip": rt_unassigned, "uv_cells_equal_part_labels": uv_matches_parts})
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
          {"head_top": r(head_top, 6), "skeletal_top_sword_tip": r(hi_sk[2], 6), "lowest": r(lo_all[2], 6),
           "figure_with_base_and_sword": r(height, 6)}, profile["scale"]["figure_height_m"])
    check("feet_on_base_top", abs(feet_low - fz) <= 0.003,
          {"lowest_foot_vertex_z": r(feet_low, 5), "base_top_z": fz}, "within 3 mm of the base top (source: feet sink 1.3 mm)")
    bcap = caps_info["base"]
    check("base_top_closed", bcap["hole_boundary_edges_before"] > 0 and bcap["boundary_edges_after"] == 0
          and closure["base_boundary_edges"] == 0 and closure["roundtrip"]["base_boundary_edges"] == 0
          and all(c["cycle_against_winding_edges"] == c["cycle_edges"] for c in bcap["caps"])
          and all(c["cap_normal_z_before_triangulate"] > 0.9999 for c in bcap["caps"]),
          {"hole_loops_before": len(bcap["holes_before"]), "hole_boundary_edges_before": bcap["hole_boundary_edges_before"],
           "caps": len(bcap["caps"]), "boundary_edges_after_caps": bcap["boundary_edges_after"],
           "boundary_edges_welded_%g_m" % weld_diag: closure["base_boundary_edges"],
           "roundtrip_boundary_edges": closure["roundtrip"]["base_boundary_edges"],
           "non_manifold_edges_info": closure["base_non_manifold_edges"]}, 0,
          "Tripo footprint holes (verify 2026-09-28: 4 loops, 74 edges) capped; caps wound with their neighbours")
    check("base_caps_flat_with_clean_stone_uvs", all(c["cap_triangles_normal_z_min"] >= 0.9999 and
                                                     c["fold_triangles"] == 0 and
                                                     abs(c["cap_triangles_z_range_m"][0] - fz) < 1e-6 and
                                                     abs(c["cap_triangles_z_range_m"][1] - fz) < 1e-6 and
                                                     c["wall_triangles_normal_z_abs_max"] < 0.5
                                                     for c in bcap["caps"])
          and bcap["affine_max_residual_px"] <= ccfg["base"]["affine_max_residual_px"]
          and all(c["donor_shift_px"] is not None for c in bcap["caps"]),
          {"cap_normal_z_min": min(c["cap_triangles_normal_z_min"] for c in bcap["caps"]),
           "fold_triangles": sum(c["fold_triangles"] for c in bcap["caps"]),
           "fold_repairs": len(bcap["fold_repairs"]),
           "cap_triangles": [c["triangles"] for c in bcap["caps"]],
           "crack_end_walls": sum(c["walls"] for c in bcap["caps"]),
           "uv_scale": [c["uv_scale"] for c in bcap["caps"]],
           "affine_residual_px": bcap["affine_max_residual_px"],
           "donor_shift_px": [c["donor_shift_px"] for c in bcap["caps"]],
           "removed_flat_faces": bcap["removed_flat_faces"], "removed_area_cm2": bcap["removed_area_cm2"],
           "removed_hole_wall_faces": sum(w["faces"] for w in bcap["removed_hole_walls"])},
          note="caps flat at the base top; UVs = the top's planar map shifted onto clean stone texels "
               "(dark hole texels and the baked bronze boot fringe are no longer used within %s m of a hole)"
               % ccfg["base"]["region_max_distance_from_hole_m"])
    sole = caps_info["soles"]
    check("body_soles_closed", all(v["low_boundary_edges_after"] == 0 and v["caps"] for v in sole.values())
          and closure["body_boundary_edges_below_z_max"] == 0
          and closure["roundtrip"]["body_boundary_edges_below_z_max"] == 0
          and all(c["triangles_normal_z_max"] < 0 and c["against_winding_edges"] == c["loop_edges"]
                  for v in sole.values() for c in v["caps"]),
          {p: {"caps": len(v["caps"]), "loop_edges": [c["loop_edges"] for c in v["caps"]],
               "normal_z_max": max(c["triangles_normal_z_max"] for c in v["caps"])} for p, v in sorted(sole.items())},
          0, "boundary edges of the body below z %s m (welded %g m), build and round trip"
          % (ccfg["soles"]["z_max_m"], weld_diag))
    st_base, st_fig = closure["see_through_base_only"], closure["see_through_rest_figure"]
    check("base_no_see_through_backface_culled", st_base["missed_total"] == 0 and st_fig["missed_total"] == 0
          and closure["roundtrip"]["see_through_base_only"] == 0,
          {"base_only": st_base["missed_total"], "rest_figure": st_fig["missed_total"],
           "roundtrip_base_only": closure["roundtrip"]["see_through_base_only"],
           "raw_base_only_edge_slips": st_base["raw_missed_total"], "raw_rest_figure_edge_slips": st_fig["raw_missed_total"],
           "rays_per_view": st_base["samples_per_view"], "views": len(st_base["missed_by_view"])}, 0,
          "orthographic rays through the base top disc (r <= %s m, step %s m) from the top and pitch %s deg "
          "every %s deg of yaw; back faces skipped as by a one-sided material; a miss counts if 2 of 4 rays "
          "jittered by %s m also miss (grid points exactly on a shared edge slip through the BVH test)" %
          (ccfg["see_through"]["disc_radius_m"], ccfg["see_through"]["grid_step_m"],
           ccfg["see_through"]["pitches_deg"], ccfg["see_through"]["yaw_step_deg"], ccfg["see_through"]["jitter_m"]))
    base_dims = [r(hi_base[i] - lo_base[i], 6) for i in range(3)]
    check("base_footprint_and_pivot", all(abs(a - b) < 1e-6 for a, b in zip(base_dims, (fx, fy, fz)))
          and all(abs(lo_base[i] + hi_base[i]) < 1e-6 for i in range(2)) and abs(lo_base[2]) < 1e-6,
          {"dimensions_m": base_dims, "centre_xy_m": [r((lo_base[i] + hi_base[i]) / 2, 6) for i in range(2)],
           "bottom_z_m": r(lo_base[2], 6)}, {"dimensions_m": [fx, fy, fz], "centre_xy_m": [0, 0], "bottom_z_m": 0})
    check("pivot_root_at_origin", pivot["root_head_m"] == [0.0, 0.0, 0.0] and
          pivot["armature_object_location"] == [0.0, 0.0, 0.0], pivot)
    check("armature_object_name_contract", arm.name == profile["armature"]["object"], arm.name,
          profile["armature"]["object"])
    front_ok = sword_c[1] < -0.02 and all(t["toe_minus_ankle"] < -0.02 and t["heel_minus_ankle"] < 0.03 + 1e-9
                                         for t in toe_ankle.values())
    check("axes_front_minus_y", front_ok, {"sword_centroid_m": sword_c, "feet": toe_ankle},
          "sword in front (y < -0.02) and toes ahead of the ankles (-Y)")
    check("axes_weapon_on_minus_x", sword_c[0] < -0.02, sword_c, "-X (Blender, character's right hand)")
    # export frame
    front_name, side_name = axis_name(front_export), axis_name(weapon_side_export)
    rel = [export_frame["weapon_centroid_m"][i] - export_frame["body_centroid_m"][i] for i in range(3)]
    f_along, _ = along(rel, front_export)
    s_along, _ = along(rel, weapon_side_export)
    check("export_frame_weapon_in_front_and_on_rotated_right", f_along > 0.02 and s_along > 0.02,
          {"weapon_minus_body_centroid_m": [r(c, 5) for c in rel], "along_front": f_along, "along_weapon_side": s_along},
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
    parents_ok = all(rt_bones.get(n, {}).get("parent") == p for n, p, _h, _t in profile["armature"]["bones"])
    heads_ok = all(rt_bones.get(n) and all(abs(a - b) < 1e-4 for a, b in zip(rt_bones[n]["head_m"], h))
                   for n, _p, h, _t in profile["armature"]["bones"])
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
          {p: len(v) for p, v in sorted(body_parts.items())},
          {p: len(v) for p, v in sorted(rt_parts.items())})
    lim = profile["proposed_limits_for_comparison_only"]
    comparison = {
        "hero_triangles": {"measured": sum(tris[n] for n in (m["body"]["object"], m["weapon"]["object"])),
                           "with_base": sum(tris.values()), "proposed": lim["hero_triangles"]},
        "texture_px": {"measured": size, "proposed": lim["texture_px"]},
        "material_slots": {"measured_skeletal_unique": len(sk_unique), "base": len(rt_slots.get(m["base"]["object"], [])),
                           "proposed_max": lim["material_slots_max"]},
        "height_uu": {"measured_head_top": r(head_top * 100, 3), "sword_tip": r(hi_sk[2] * 100, 3),
                      "proposed": lim["height_uu"]},
        "base_uu": {"measured": [r(c * 100, 3) for c in base_dims], "proposed_diameter": lim["base_diameter_uu"],
                    "proposed_height": lim["base_height_uu"]},
        "capsule_uu": {"max_radius_from_pivot_axis": r(radial * 100, 3), "top": r(hi_sk[2] * 100, 3),
                       "proposed": lim["capsule_uu"],
                       "fits": bool(radial * 100 <= lim["capsule_uu"]["diameter"] / 2 + 1e-6
                                    and hi_sk[2] * 100 <= lim["capsule_uu"]["height"])},
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
        "weapon_split": split_info,
        "caps": caps_info,
        "closure": closure,
        "body_parts": sorted(body_parts),
        "body_part_polygons": {p: len(v) for p, v in sorted(body_parts.items())},
        "cross_part_coincident_vertices": cross_part,
        "orientation": {"method": ocfg["method"], "before_fix": orient_before, "flipped_parts": inside_out,
                        "after_fix": orient_after, "roundtrip": orient_rt, "corner_normals_opposed_area_share": opposed,
                        "corner_normals_preserved": normals_preserved},
        "materials": {"atlas": "M_KingArthur_Atlas", "blender_images": mat_images},
        "meshes_pre_export_m": pre,
        "weights": weights,
        "weights_per_part": per_part_weights,
        "weights_cleanup": heat_stats,
        "uv": uv_stats,
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
        "axes": {"sword_centroid_m": sword_c, "feet": toe_ankle,
                 "export_frame": {"weapon_centroid_m": export_frame["weapon_centroid_m"],
                                  "body_centroid_m": export_frame["body_centroid_m"],
                                  "front_axis": front_name, "weapon_side_axis": side_name}},
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
            "selection collision (04 §3.3 UCP_ 36x62 uu proposal; skeletal meshes use a physics asset in UE)",
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


def labelled_objects(labelled):
    for obj, parts in labelled:
        for name in parts:
            yield name, obj


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


main()
