"""Stage `build` for Harpy (ASSET-HARPY-001): segmented Tripo GLB -> skeletal candidate (body with wings) and a
separate parametric static base with instance marks, UM_FBX_v1.

Headless only (`blender -b --factory-startup`), never in a live Blender (read_factory_settings):

    blender -b --factory-startup --python build_harpy_candidate.py -- <params.json>

params.json has the keys of tools/tripo-pipeline/tripo_pipeline.py exec_build plus "reference_glb":
    {"source", "profile", "atlas_report", "textures_dir", "repo_root", "blend_out",
     "sk_fbx_out", "base_fbx_out", "report_out", "fbx_preset", "reference_glb"}

Why not tools/tripo-pipeline/blender/build_candidate.py (0.4.0): it hard-codes Medusa (bow = one GLB part on
+X, face part tripo_part_10, neck check on tripo_part_14). This script is the Merlin builder
(art/pipeline-candidates/ASSET-MERLIN-001/scripts/build_merlin_candidate.py, 2026-09-28) adapted to Harpy;
helpers are copied, not imported (both run main() at import). Harpy differences, data-driven by the profile:
  * no weapon mesh; the 17-bone set keeps an unweighted `weapon` leaf (rig-contract: Harpy = null);
  * the Tripo base part is dropped and a parametric Ø22 x 5 uu base is built, with a UM_Mask vertex-colour
    attribute: R team band, G centre pips, B outer pips (three instances = material parameter);
  * tripo_part_2 (head) has MIXED winding in the retopology: each face is voted against the nearest triangle
    of the correctly oriented Tripo high-poly (segmented-9 GLB, read with numpy); tripo_part_6 is flipped whole
    (ray-escape, as for Medusa/Merlin);
  * wings (arm_upper/arm_lower/hand, rig-contract harpy_wings) are weighted by a span rule, not bone heat;
  * ramps may run along x or y (the tail feathers inside the right-leg part follow hips).
The report is deterministic (rounded floats, sorted keys, no timestamps). Nothing outside the params'
output paths is written; the source and reference GLBs are only read.
"""

import datetime
import faulthandler
import hashlib
import json
import math
import os
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
    raise RuntimeError("build_harpy_candidate.py: headless only (blender -b)")
# faulthandler is a diagnostic switch only (run_harpy_build.py --faulthandler). On Windows it installs a vectored
# exception handler that also prints first-chance exceptions Blender handles itself: Blender 5.2.2 with an empty
# script and faulthandler on prints 0-20 "Windows fatal exception: access violation" on the main thread during
# its own exit (after the script, before Python finalisation) and still exits 0. Off by default so that the
# build log only shows real failures (a real crash still gives a non-zero exit code and no stage marker).
if os.environ.get("HARPY_BUILD_FAULTHANDLER") == "1":
    faulthandler.enable()

MARKER = "TRIPO_PIPELINE_STAGE_OK build"
BUILDER = "art/pipeline-candidates/ASSET-HARPY-001/scripts/build_harpy_candidate.py"
FIXED_TIME = datetime.datetime(2000, 1, 1, 0, 0, 0)
WORK_SCENE = "tripo_pipeline_candidate"
ROUNDTRIP_SCENE = "tripo_pipeline_candidate_roundtrip"
CN_ATTR = "um_corner_normal"
PART_ATTR = "um_part"
REF_FLIP_ATTR = "um_ref_flip"
DEGENERATE_AREA_CM2 = 1e-4
PRESET_KEYS = ("name", "axis_forward", "axis_up", "export_space_rotation_z_degrees", "temporary_data_scale",
               "patch_fbx_unit_scale_to", "apply_unit_scale", "apply_scale_options", "use_triangles",
               "mesh_smooth_type", "add_leaf_bones", "primary_bone_axis", "secondary_bone_axis", "path_mode")
PATH_MODE = "STRIP"
COLORS_TYPE = "SRGB"


def step(label):
    print("HARPY_BUILD_STEP", label, flush=True)


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
            "color_attributes": sorted(a.name for a in mesh.color_attributes),
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
    """Min dot between the current corner normals and `expected` (N x 3); zero captured normals excluded."""
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


def label_faces(obj, part_name):
    attr = obj.data.attributes.get(PART_ATTR) or obj.data.attributes.new(PART_ATTR, "INT", "FACE")
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


def cap_open_loops(obj, part_index, cfg, xform):
    """Fan-fill open boundary loops of one part. Loops are connected components of the boundary-edge graph
    (robust to non-manifold boundary vertices, where a chain walk stops early) whose centroid lies within
    cfg["tolerance_m"] (source frame, scaled) of a listed source point. The loop vertices are ordered by angle
    around the centroid in the loop's best-fit plane and fanned to a new centre vertex. Every cap corner gets the
    UV of the loop corner nearest to the loop's mean UV (one texel of the part's own island next to the opening:
    a flat colour, zero UV area, so the cap overlaps no other island); corner normals (captured attribute) = the plane normal pointing away
    from the part centroid. Reports planarity and the largest angular gap (a star-shaped ring has < 90 deg)."""
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


def bind_to_armature(arm, obj):
    obj.parent = arm
    if not any(m.type == "ARMATURE" for m in obj.modifiers):
        obj.modifiers.new("Armature", "ARMATURE").object = arm


def rigid_weights(arm, obj, bone):
    group = obj.vertex_groups.get(bone) or obj.vertex_groups.new(name=bone)
    group.add(list(range(len(obj.data.vertices))), 1.0, "REPLACE")
    bind_to_armature(arm, obj)


def smoothstep(t):
    t = max(0.0, min(1.0, t))
    return t * t * (3 - 2 * t)


def wing_span_weights(arm, obj, cfg, s_scale):
    """Span rule for a wing sheet: see profile weights.wing_span_rule. Returns measured joint spans."""
    upper, lower, hand = cfg["chain"]
    bones = arm.data.bones
    S = bones[upper].head_local.copy()
    E = bones[lower].head_local.copy()
    W = bones[hand].head_local.copy()
    T = bones[hand].tail_local.copy()
    d = Vector((T.x - S.x, T.y - S.y, 0.0)).normalized()

    def span(p):
        return (p.x - S.x) * d.x + (p.y - S.y) * d.y

    sE, sW, sT = span(E), span(W), span(T)
    band = cfg["joint_band_m"] * s_scale
    root = cfg["root_band_m"] * s_scale
    groups = {}
    for name in (cfg["root_to"], upper, lower, hand):
        groups[name] = obj.vertex_groups.get(name) or obj.vertex_groups.new(name=name)
    counts = Counter()
    for v in obj.data.vertices:
        sv = span(obj.matrix_world @ v.co)
        f1 = smoothstep((sv - (sE - band)) / (2 * band))
        f2 = smoothstep((sv - (sW - band)) / (2 * band))
        w = {hand: f2, lower: max(0.0, f1 - f2), upper: 1.0 - f1}
        if cfg.get("root_mode", "span") == "distance":
            fr = smoothstep(((obj.matrix_world @ v.co) - S).length / root) if root > 0 else 1.0
        else:
            fr = smoothstep(sv / root) if root > 0 else 1.0
        w[cfg["root_to"]] = w[upper] * (1.0 - fr)
        w[upper] *= fr
        for name, value in w.items():
            if value > 0:
                groups[name].add([v.index], value, "REPLACE")
        counts[max(w, key=w.get)] += 1
    bind_to_armature(arm, obj)
    return {"direction_xy": rv(d, 4), "span_elbow_m": r(sE, 5), "span_wrist_m": r(sW, 5), "span_tip_m": r(sT, 5),
            "joint_band_m": r(band, 5), "root_band_m": r(root, 5), "root_mode": cfg.get("root_mode", "span"),
            "dominant_bone_vertices": dict(sorted(counts.items()))}


def axis_blend_weights(arm, obj, cfg, to_final):
    """Geometric two-bone blend along one axis (no heat): weight of `to` = smoothstep between the two source
    coordinates, the rest on `from`."""
    axis = cfg.get("axis", "z")
    k = {"x": 0, "y": 1, "z": 2}[axis]
    a, b = to_final(axis, cfg["zero_below"]), to_final(axis, cfg["full_above"])
    g_from = obj.vertex_groups.get(cfg["from"]) or obj.vertex_groups.new(name=cfg["from"])
    g_to = obj.vertex_groups.get(cfg["to"]) or obj.vertex_groups.new(name=cfg["to"])
    for v in obj.data.vertices:
        f = smoothstep(((obj.matrix_world @ v.co)[k] - a) / (b - a))
        if f < 1.0:
            g_from.add([v.index], 1.0 - f, "REPLACE")
        if f > 0.0:
            g_to.add([v.index], f, "REPLACE")
    bind_to_armature(arm, obj)


def ramp_factor(ramp, value, to_final):
    """Fraction of the ramped bones' weight that is KEPT at `value` (smoothstep) on the ramp axis."""
    axis = ramp.get("axis", "z")
    suffix = "" if "axis" in ramp else "_z"
    if ("zero_above" + suffix) in ramp:
        a, b = to_final(axis, ramp["zero_above" + suffix]), to_final(axis, ramp["full_below" + suffix])
        f = (a - value) / (a - b)
    else:
        a, b = to_final(axis, ramp["zero_below" + suffix]), to_final(axis, ramp["full_above" + suffix])
        f = (value - a) / (b - a)
    return smoothstep(f)


def cleanup_weights(arm, obj, allowed, rule, max_influences, clean_below, to_final):
    """Weight cleanup of one part: (1) keep only the group's bones, normalise, nearest-bone fallback for
    vertices the heat solve left empty; (2) ramps, caps, drop < clean_below, keep the strongest
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
    axis_index = {"x": 0, "y": 1, "z": 2}
    for v, ws in zip(mesh.vertices, weights):
        p = mw @ v.co
        for ramp in rule.get("height_ramps") or []:
            f = ramp_factor(ramp, p[axis_index[ramp.get("axis", "z")]], to_final)
            for bone in ramp["bones"]:
                w = ws.get(bone, 0.0)
                if w > 0 and f < 1.0:
                    ws[bone] = w * f
                    ws[ramp["to"]] = ws.get(ramp["to"], 0.0) + w * (1.0 - f)
                    stats["ramped_%s" % ramp.get("axis", "z")] += 1
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
        # read the group indices first: removing an entry reallocates v.groups, so VertexGroupElement references
        # taken before the removal point to freed memory (a crash of the first Harpy build, 2026-09-28)
        for gi in [g.group for g in v.groups]:
            obj.vertex_groups[gi].remove([v.index])
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


def read_glb_node_triangles(path, node_names):
    """Positions (Blender frame: (x, -z, y) of glTF) and triangle indices of the named mesh nodes, numpy only."""
    data = Path(path).read_bytes()
    if data[:4] != b"glTF" or struct.unpack_from("<I", data, 8)[0] != len(data):
        raise RuntimeError("not a complete binary glTF: %s" % path)
    json_len = struct.unpack_from("<I", data, 12)[0]
    model = json.loads(data[20:20 + json_len])
    binary = 20 + json_len + 8
    comp = {5126: np.float32, 5125: np.uint32, 5123: np.uint16, 5121: np.uint8}
    ncomp = {"SCALAR": 1, "VEC3": 3}

    def accessor(index):
        acc = model["accessors"][index]
        view = model["bufferViews"][acc["bufferView"]]
        dtype = np.dtype(comp[acc["componentType"]])
        n = ncomp[acc["type"]]
        start = binary + view.get("byteOffset", 0) + acc.get("byteOffset", 0)
        stride = view.get("byteStride") or dtype.itemsize * n
        if stride == dtype.itemsize * n:
            arr = np.frombuffer(data, dtype=dtype, count=acc["count"] * n, offset=start).reshape(acc["count"], n)
        else:
            raw = np.frombuffer(data, dtype=np.uint8, count=stride * acc["count"], offset=start).reshape(acc["count"], stride)
            arr = raw[:, :dtype.itemsize * n].copy().view(dtype).reshape(acc["count"], n)
        return arr

    out = {}
    for node in model["nodes"]:
        if node.get("name") not in node_names or "mesh" not in node:
            continue
        if any(k in node for k in ("translation", "rotation", "scale", "matrix")):
            raise RuntimeError("reference node %s has a transform" % node["name"])
        prim = model["meshes"][node["mesh"]]["primitives"][0]
        if prim.get("mode", 4) != 4:
            raise RuntimeError("reference node %s is not triangles" % node["name"])
        pos = accessor(prim["attributes"]["POSITION"]).astype(np.float64)
        idx = accessor(prim["indices"]).reshape(-1, 3).astype(np.int64)
        out[node["name"]] = (np.stack([pos[:, 0], -pos[:, 2], pos[:, 1]], axis=1), idx)
    missing = sorted(set(node_names) - set(out))
    if missing:
        raise RuntimeError("reference nodes missing: %s" % missing)
    return out


def reference_votes(obj, ref_pos, ref_idx, max_dist):
    """Per face of `obj` (source frame): mean of sign(dot(face normal, nearest reference triangle normal)) over
    the face centre and its corners pulled 10 % toward the centre, in [-1, 1] (0 when nothing is in reach)."""
    bvh = BVHTree.FromPolygons([tuple(p) for p in ref_pos], [tuple(t) for t in ref_idx], all_triangles=True, epsilon=0.0)
    votes, unmatched = [], 0
    mesh = obj.data
    for p in mesh.polygons:
        c = p.center
        samples = [c] + [c + (mesh.vertices[v].co - c) * 0.9 for v in p.vertices]
        vote = matched = 0
        for s in samples:
            loc, nrm, _i, dist = bvh.find_nearest(s, max_dist)
            if loc is None:
                continue
            matched += 1
            vote += 1 if p.normal.dot(nrm) >= 0 else -1
        if not matched:
            unmatched += 1
        votes.append(vote / matched if matched else 0.0)
    conf = [abs(v) for v in votes]
    return votes, {"faces": len(mesh.polygons), "raw_vote_to_flip": sum(1 for v in votes if v < 0),
                   "unmatched_faces": unmatched,
                   "unanimous_share": r(sum(1 for c in conf if c == 1.0) / max(len(conf), 1), 4),
                   "reference_triangles": int(len(ref_idx))}


def smooth_orientation(mesh, votes, lam, iterations):
    """ICM over faces: o_f in {+1 keep, -1 flip} minimising sum_f |vote_f| [o_f disagrees with the vote] +
    lam * #inconsistent manifold edges; starts from the raw vote. Returns (faces to flip, stats)."""
    edge = defaultdict(list)
    for p in mesh.polygons:
        vs = list(p.vertices)
        for i in range(len(vs)):
            a, b = vs[i], vs[(i + 1) % len(vs)]
            edge[tuple(sorted((a, b)))].append((p.index, (a, b)))
    pairs = [(v[0][0], v[1][0], v[0][1] == v[1][1]) for v in edge.values() if len(v) == 2]
    nbr = defaultdict(list)
    for fa, fb, same in pairs:
        nbr[fa].append((fb, same))
        nbr[fb].append((fa, same))

    def inconsistent(o):
        return sum(1 for fa, fb, same in pairs if same != (o[fa] != o[fb]))

    raw = [-1 if v < 0 else 1 for v in votes]
    o = list(raw)
    sweeps = 0
    for sweeps in range(1, iterations + 1):
        changed = 0
        for f in range(len(o)):
            best = None
            for cand in (1, -1):
                data = abs(votes[f]) * (1 if (cand == -1) != (votes[f] < 0) else 0)
                smooth = sum(lam for g, same in nbr[f] if same != (cand != o[g]))
                energy = data + smooth
                if best is None or energy < best[0] - 1e-12:
                    best = (energy, cand)
            if best[1] != o[f]:
                o[f] = best[1]
                changed += 1
        if not changed:
            break
    return {i for i, v in enumerate(o) if v == -1}, {
        "lambda": lam, "sweeps": sweeps, "manifold_edges": len(pairs),
        "inconsistent_as_imported": inconsistent([1] * len(o)), "inconsistent_raw_vote": inconsistent(raw),
        "inconsistent_after_smoothing": inconsistent(o), "changed_vs_raw_vote": sum(1 for a, b in zip(o, raw) if a != b),
        "flipped": sum(1 for v in o if v == -1)}


def build_parametric_base(scene, cfg, mcfg):
    """Ø x h cylinder with a chamfer, fan top/bottom and raised pips; UM_Mask byte colours; planar UV0."""
    R0, zt, R1, h, n = cfg["radius_bottom_m"], cfg["side_top_z_m"], cfg["radius_top_m"], cfg["height_m"], cfg["segments"]
    pc = cfg["pips"]
    bm = bmesh.new()
    ang = [2 * math.pi * i / n for i in range(n)]
    bottom = [bm.verts.new((R0 * math.cos(a), R0 * math.sin(a), 0.0)) for a in ang]
    side_top = [bm.verts.new((R0 * math.cos(a), R0 * math.sin(a), zt)) for a in ang]
    top = [bm.verts.new((R1 * math.cos(a), R1 * math.sin(a), h)) for a in ang]
    cb = bm.verts.new((0.0, 0.0, 0.0))
    ct = bm.verts.new((0.0, 0.0, h))
    role = {}
    for i in range(n):
        j = (i + 1) % n
        role[bm.faces.new((bottom[j], bottom[i], cb))] = "bottom"
        role[bm.faces.new((bottom[i], bottom[j], side_top[j], side_top[i]))] = "band"
        role[bm.faces.new((side_top[i], side_top[j], top[j], top[i]))] = "band"
        role[bm.faces.new((top[i], top[j], ct))] = "top"
    pips = []
    for sector in pc["sector_azimuths_deg"]:
        base_ang = math.radians(sector)
        dphi = pc["arc_spacing_m"] / pc["ring_radius_m"]
        for slot, k in zip(pc["slots_per_sector"], (-1, 0, 1)):
            a = base_ang + k * dphi
            cx, cy = pc["ring_radius_m"] * math.cos(a), pc["ring_radius_m"] * math.sin(a)
            m = pc["pip_sides"]
            up = [bm.verts.new((cx + pc["pip_radius_m"] * math.cos(2 * math.pi * q / m),
                                cy + pc["pip_radius_m"] * math.sin(2 * math.pi * q / m), h + pc["raise_m"])) for q in range(m)]
            dn = [bm.verts.new((v.co.x, v.co.y, h - pc["skirt_m"])) for v in up]
            cen = bm.verts.new((cx, cy, h + pc["raise_m"]))
            kind = "pip_centre" if slot == "centre" else "pip_outer"
            for q in range(m):
                w = (q + 1) % m
                role[bm.faces.new((up[q], up[w], cen))] = kind
                role[bm.faces.new((dn[q], dn[w], up[w], up[q]))] = kind
            pips.append({"sector_deg": sector, "slot": slot, "centre_m": [r(cx, 5), r(cy, 5)],
                         "radius_from_axis_m": r(math.hypot(cx, cy), 5)})
    bm.normal_update()
    for f in bm.faces:  # outward check by construction: every face normal away from the axis/centre
        c = f.calc_center_median()
        kind = role[f]
        want = Vector((0, 0, -1)) if kind == "bottom" else Vector((0, 0, 1)) if kind in ("top",) else None
        if want is None:
            if kind == "band":
                want = Vector((c.x, c.y, 0)).normalized()
            else:  # pip: top faces up, skirt faces radially out of the pip
                pcen = min(pips, key=lambda q: math.hypot(q["centre_m"][0] - c.x, q["centre_m"][1] - c.y))["centre_m"]
                want = Vector((0, 0, 1)) if abs(f.normal.z) > 0.5 else Vector((c.x - pcen[0], c.y - pcen[1], 0)).normalized()
        if f.normal.dot(want) < 0:
            f.normal_flip()
    uv = bm.loops.layers.uv.new("UVMap")
    col = bm.loops.layers.color.new(mcfg["attribute"])
    colour = {"bottom": (0, 0, 0, 1), "top": (0, 0, 0, 1), "band": (1, 0, 0, 1),
              "pip_centre": (0, 1, 0, 1), "pip_outer": (0, 0, 1, 1)}
    side = {f for f in bm.faces if role[f] == "band" and abs(f.normal.z) < 0.2}
    for f in bm.faces:
        for loop in f.loops:
            co = loop.vert.co
            loop[uv].uv = (0.5 + co.x / (2 * R0) * 0.98, 0.5 + co.y / (2 * R0) * 0.98)
            loop[col] = colour[role[f]]
        f.smooth = f in side
    mesh = bpy.data.meshes.new("Harpy_Base")
    bm.to_mesh(mesh)
    roles = Counter(role.values())
    bm.free()
    obj = bpy.data.objects.new("SM_Harpy_Base", mesh)
    scene.collection.objects.link(obj)
    return obj, {"faces_by_role": dict(sorted(roles.items())), "pips": pips}


def sock(sockets, name, kind):
    return next(x for x in sockets if x.name == name and x.type == kind)


def base_material(cfg):
    """Preview material of the base: dark top, team band (object prop um_team_color), pips lit by the object
    prop um_instance_index (1: G, 2: B, 3: G+B) — the UE material rule of profile base_parametric.mask."""
    cols = cfg["preview_colours_linear"]
    mat = bpy.data.materials.new(cfg["material"])
    mat.use_nodes = True
    nt = mat.node_tree
    nodes, links = nt.nodes, nt.links
    bsdf = next(n for n in nodes if n.type == "BSDF_PRINCIPLED")
    bsdf.inputs["Roughness"].default_value = 0.6
    ca = nodes.new("ShaderNodeVertexColor")
    ca.layer_name = cfg["mask"]["attribute"]
    sep = nodes.new("ShaderNodeSeparateColor")
    links.new(ca.outputs["Color"], sep.inputs["Color"])
    idx = nodes.new("ShaderNodeAttribute")
    idx.attribute_type = "OBJECT"
    idx.attribute_name = "um_instance_index"
    team = nodes.new("ShaderNodeAttribute")
    team.attribute_type = "OBJECT"
    team.attribute_name = "um_team_color"

    def math_node(op, a, b=None):
        node = nodes.new("ShaderNodeMath")
        node.operation = op
        for k, v in enumerate((a, b)):
            if v is None:
                continue
            if isinstance(v, (int, float)):
                node.inputs[k].default_value = v
            else:
                links.new(v, node.inputs[k])
        return node.outputs["Value"]

    centre_on = math_node("GREATER_THAN", math_node("ABSOLUTE", math_node("SUBTRACT", idx.outputs["Fac"], 2.0)), 0.5)
    outer_on = math_node("GREATER_THAN", idx.outputs["Fac"], 1.5)
    lit = math_node("MINIMUM", math_node("ADD", math_node("MULTIPLY", sep.outputs["Green"], centre_on),
                                         math_node("MULTIPLY", sep.outputs["Blue"], outer_on)), 1.0)
    mix_team = nodes.new("ShaderNodeMix")
    mix_team.data_type = "RGBA"
    sock(mix_team.inputs, "A", "RGBA").default_value = (*cols["base"], 1.0)
    links.new(team.outputs["Color"], sock(mix_team.inputs, "B", "RGBA"))
    links.new(sep.outputs["Red"], sock(mix_team.inputs, "Factor", "VALUE"))
    mix_pip = nodes.new("ShaderNodeMix")
    mix_pip.data_type = "RGBA"
    links.new(sock(mix_team.outputs, "Result", "RGBA"), sock(mix_pip.inputs, "A", "RGBA"))
    sock(mix_pip.inputs, "B", "RGBA").default_value = (*cols["pip"], 1.0)
    links.new(lit, sock(mix_pip.inputs, "Factor", "VALUE"))
    links.new(sock(mix_pip.outputs, "Result", "RGBA"), bsdf.inputs["Base Color"])
    em = nodes.new("ShaderNodeMix")
    em.data_type = "RGBA"
    sock(em.inputs, "A", "RGBA").default_value = (0, 0, 0, 1)
    sock(em.inputs, "B", "RGBA").default_value = (*cols["pip"], 1.0)
    links.new(lit, sock(em.inputs, "Factor", "VALUE"))
    links.new(sock(em.outputs, "Result", "RGBA"), bsdf.inputs["Emission Color"])
    bsdf.inputs["Emission Strength"].default_value = 0.35
    return mat


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
            path_mode=PATH_MODE, embed_textures=False, colors_type=COLORS_TYPE,
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


def mask_census(obj, name):
    """Count corners per UM_Mask value (rounded to 0/1 per channel) and flag non-binary values."""
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
    reference = Path(params["reference_glb"])
    repo = Path(params["repo_root"])
    source_hash = sha256(source)
    reference_hash = sha256(reference)
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
    left_export = rot3 @ Vector((1.0, 0.0, 0.0))
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

    step('raw orientation')
    # ---- raw orientation of the Tripo geometry (all 9 parts, source frame), winding consistency
    orient_raw = orientation_scores([(o, {n: [p.index for p in o.data.polygons]}) for n, o in sorted(parts.items())])

    step('reference vote')
    # ---- per-face reference vote (source frame) for parts with mixed winding
    ocfg = profile["orientation"]
    rcfg = ocfg["per_face_reference"]
    ref = read_glb_node_triangles(reference, rcfg["parts"])
    ref_votes = {}
    for name in rcfg["parts"]:
        votes, info = reference_votes(parts[name], ref[name][0], ref[name][1], rcfg["max_reference_distance_m"])
        attr = parts[name].data.attributes.new(REF_FLIP_ATTR, "FLOAT", "FACE")
        attr.data.foreach_set("value", votes)
        ref_votes[name] = info
    ref.clear()

    step('drop base')
    # ---- drop the Tripo base (replaced by the parametric base)
    dropped = {}
    tripo_base = parts[m["base"]["source_part"]]
    blo, bhi = world_bounds([tripo_base])
    cx, cy = (blo[0] + bhi[0]) / 2, (blo[1] + bhi[1]) / 2
    base_top_src, base_bottom_src = bhi[2], blo[2]
    for name, why in sorted((m.get("drop_parts") or {}).items()):
        obj = parts.pop(name)
        lo, hi = world_bounds([obj])
        dropped[name] = {"reason": why, "polygons": len(obj.data.polygons), "vertices": len(obj.data.vertices),
                         "source_size": rv([hi[i] - lo[i] for i in range(3)], 6),
                         "source_bounds": {"min": rv(lo, 5), "max": rv(hi, 5)}}
        bpy.data.objects.remove(obj)
        captured.pop(name)

    step('scale')
    # ---- scale and seat: figure uniform about the source base top, on the parametric base top
    fx, fy, fz = m["base"]["footprint_m"]
    top_src = max(v.co.z for v in parts[profile["scale"]["top_part"]].data.vertices)
    s = (profile["scale"]["figure_height_m"] - fz) / (top_src - base_top_src)
    xform = (s, cx, cy, fz, base_top_src)

    def to_final(axis, value):
        if axis == "x":
            return (value - cx) * s
        if axis == "y":
            return (value - cy) * s
        return fz + (value - base_top_src) * s

    for name, obj in parts.items():
        for v in obj.data.vertices:
            v.co = Vector(((v.co.x - cx) * s, (v.co.y - cy) * s, fz + (v.co.z - base_top_src) * s))
        obj.data.update()
    scale_info = {"source_base_top": r(base_top_src), "source_base_bottom": r(base_bottom_src),
                  "source_base_centre_xy": [r(cx), r(cy)], "source_top_of_top_part": r(top_src),
                  "figure_scale": r(s, 8), "figure_height_m": profile["scale"]["figure_height_m"],
                  "base_height_m": fz, "base_diameter_m": fx,
                  "tripo_base_diameter_at_figure_scale_m": r((bhi[0] - blo[0]) * s, 6)}

    step('atlas uv')
    # ---- atlas UVs + material
    files = {k: v["file"] for k, v in atlas["files"].items()}
    mat, mat_images = atlas_material(params["textures_dir"], files, "M_Harpy_Atlas")
    for name, obj in parts.items():
        remap_uvs(obj, cells[name], size)
        obj.data.materials.clear()
        obj.data.materials.append(mat)
        obj.data.update()

    step('weld')
    # ---- weld inside every part; label faces with their part
    weld = {n: weld_part(o, profile["weld"]["distance_m"]) for n, o in sorted(parts.items())}
    for name, obj in parts.items():
        label_faces(obj, name)

    step('normals back')
    # ---- caps on open loops (feet: ankle and sole openings; torso: wing sockets)
    step("caps")
    caps = {}
    for name, ccfg in sorted((profile.get("caps") or {}).items()):
        caps[name] = cap_open_loops(parts[name], int(name.split("_")[-1]), ccfg, xform)

    # corner normals back (uniform scale = rotation-free)
    normals_after, normals_preserved = {}, {}
    for name, obj in sorted(parts.items()):
        normals_after[name] = apply_corner_normals(obj)
    for name, obj in sorted(parts.items()):
        mn, bad, zero = corner_normal_agreement(obj, normals_after[name])
        normals_preserved[name] = {"min_dot": r(mn, 5), "corners_below_0_999": bad,
                                   "zero_captured_corners_excluded": zero}
    for obj in parts.values():
        obj.data.attributes.remove(obj.data.attributes[CN_ATTR])

    step('base')
    # ---- parametric base
    bcfg = profile["base_parametric"]
    base, base_info = build_parametric_base(scene, bcfg, bcfg["mask"])
    base.name, base.data.name = m["base"]["object"], m["base"]["mesh"]
    bmat = base_material(bcfg)
    base.data.materials.append(bmat)
    base["um_instance_index"] = 3.0
    base["um_team_color"] = tuple(bcfg["preview_colours_linear"]["team_gold"]) + (1.0,)

    step('orientation')
    # ---- orientation: (1) per-face reference fix, (2) whole-part ray-escape fix
    labelled = [(o, {n: [p.index for p in o.data.polygons]}) for n, o in sorted(parts.items())]
    labelled.append((base, {"base": [p.index for p in base.data.polygons]}))
    orient_before_ref = orientation_scores(labelled)
    for name in rcfg["parts"]:
        mesh = parts[name].data
        vals = [0.0] * len(mesh.polygons)
        mesh.attributes[REF_FLIP_ATTR].data.foreach_get("value", vals)
        ref_votes[name]["winding_after_weld_before_fix"] = inconsistent_winding_edges(mesh)
        flip, smooth = smooth_orientation(mesh, vals, rcfg["smoothing_lambda"], rcfg["smoothing_max_sweeps"])
        flip_polygons(mesh, flip)
        ref_votes[name]["smoothing"] = smooth
        ref_votes[name]["winding_after_fix"] = inconsistent_winding_edges(mesh)
        mesh.attributes.remove(mesh.attributes[REF_FLIP_ATTR])
    orient_before = orientation_scores(labelled)
    inside_out = sorted(p for p, sc in orient_before.items()
                        if sc["score"] is not None and sc["score"] < ocfg["flip_below_score"])
    check("orientation_inside_out_parts_as_profile", inside_out == sorted(ocfg["expected_inside_out_parts"]),
          inside_out, sorted(ocfg["expected_inside_out_parts"]),
          "ray-escape score < %s after the per-face reference fix" % ocfg["flip_below_score"])
    for name in inside_out:
        flip_polygons(parts[name].data, {p.index for p in parts[name].data.polygons})
    orient_after = orientation_scores(labelled)
    bad_after = sorted(p for p, sc in orient_after.items() if sc["score"] is None or sc["score"] < ocfg["min_score_after_fix"])
    check("orientation_all_parts_outward_after_fix", not bad_after,
          {p: sc["score"] for p, sc in sorted(orient_after.items())}, ">= %s" % ocfg["min_score_after_fix"])
    rv2 = ref_votes[rcfg["parts"][0]]
    check("orientation_reference_vote_fixed_mixed_winding",
          rv2["winding_after_fix"]["inconsistent"] <= rcfg["max_inconsistent_after"]
          and rv2["winding_after_fix"]["inconsistent"] < rv2["winding_after_weld_before_fix"]["inconsistent"]
          and rv2["unmatched_faces"] == 0,
          ref_votes, "inconsistent winding edges <= %s after the fix, every face finds reference triangles" % rcfg["max_inconsistent_after"],
          "faces of the mixed-winding part voted against the Tripo high-poly, then smoothed (ICM) toward consistent winding")
    opposed = {n: opposed_corner_fraction(o, ix) for n, o, ix in labelled_objects(labelled)}
    check("corner_normals_agree_with_winding", all(v <= ocfg["corner_normal_opposed_max_fraction"] for v in opposed.values()),
          opposed, "<= %s area share per part" % ocfg["corner_normal_opposed_max_fraction"],
          "area share of polygons whose mean custom corner normal points against the polygon normal")
    check("corner_normals_preserved_by_weld_and_seat", all(v["min_dot"] > 0.999 for v in normals_preserved.values()),
          normals_preserved, "min dot > 0.999 against the captured import normals")

    step('armature')
    # ---- armature and weights
    arm, bones_final = make_armature(scene, profile, xform)
    bone_names = [b[0] for b in profile["armature"]["bones"]]
    wcfg_all = profile["weights"]
    rules = {}
    for rule in wcfg_all["groups"]:
        for part in rule["parts"]:
            rules[part] = rule
    body_part_names = sorted(parts)
    missing_rules = sorted(set(body_part_names) - set(rules))
    if missing_rules:
        raise RuntimeError("no weight rule for parts %s" % missing_rules)
    wing_info = {}
    for rule in wcfg_all["groups"]:
        objs = [parts[p] for p in rule["parts"] if p in parts]
        if "rigid" in rule:
            for obj in objs:
                rigid_weights(arm, obj, rule["rigid"])
        elif "wing_span" in rule:
            for p in rule["parts"]:
                wing_info[p] = wing_span_weights(arm, parts[p], rule["wing_span"], s)
        elif "axis_blend" in rule:
            for obj in objs:
                axis_blend_weights(arm, obj, rule["axis_blend"], to_final)
        else:
            heat_weights(scene, arm, objs, set(rule["heat"]))

    def allowed_of(rule):
        if "rigid" in rule:
            return {rule["rigid"]}
        if "wing_span" in rule:
            return set(rule["wing_span"]["chain"]) | {rule["wing_span"]["root_to"]}
        if "axis_blend" in rule:
            return {rule["axis_blend"]["from"], rule["axis_blend"]["to"]}
        return set(rule["heat"])

    heat_stats = {}
    for name in body_part_names:
        rule = rules[name]
        heat_stats[name] = cleanup_weights(arm, parts[name], allowed_of(rule), rule, profile["armature"]["max_influences"],
                                           wcfg_all["clean_below"], to_final)
    per_part_weights = {n: weight_summary(parts[n], bone_names) for n in body_part_names}

    step('join')
    # ---- join body
    body = join_objects(scene, [parts[n] for n in body_part_names], parts[m["body"]["active_part"]])
    body.name = m["body"]["object"]
    body.data.name = m["body"]["mesh"]
    for mod in [md for md in body.modifiers if md.type == "ARMATURE"][1:]:
        body.modifiers.remove(mod)
    body_parts = read_face_labels(body)
    part_of_poly = {i: p for p, ix in body_parts.items() for i in ix}
    body.data.attributes.remove(body.data.attributes[PART_ATTR])
    uv_parts, unassigned = polygons_by_part(body.data, rects)
    uv_matches_parts = all(sorted(uv_parts.get(p, [])) == sorted(ix) for p, ix in body_parts.items())

    step('measure')
    # ---- measurements (authored frame, metres)
    pre = {m["body"]["object"]: mesh_summary(body), m["base"]["object"]: mesh_summary(base)}
    weights = {"body": weight_summary(body, bone_names)}
    labelled_final = [(body, body_parts)]
    uv_stats = uv_statistics(labelled_final, cells, size, 100.0)
    lo_body, hi_body = world_bounds([body])
    lo_base, hi_base = world_bounds([base])
    lo_all, hi_all = world_bounds([body, base])

    def part_points(obj, ix):
        return [obj.data.vertices[v].co for v in sorted({v for i in ix for v in obj.data.polygons[i].vertices})]

    head_ix = body_parts[profile["scale"]["top_part"]]
    head_pts = part_points(body, head_ix)
    head_top = max(p.z for p in head_pts)
    feet_parts = {"L": "tripo_part_8", "R": "tripo_part_7"}
    feet_low = min(p.z for side in feet_parts.values() for p in part_points(body, body_parts[side]))
    toe_ankle, talon_tips = {}, {}
    for side, part in sorted(feet_parts.items()):
        pts = part_points(body, body_parts[part])
        ys = sorted(p.y for p in pts)
        cut = ys[max(0, len(ys) // 4 - 1)]
        front = [p for p in pts if p.y <= cut]
        tip = sum(front, Vector()) / len(front)
        talon_tips[side] = tip
        ankle = arm.data.bones["foot.%s" % side].head_local
        toe_ankle[side] = {"talon_tips_centre_m": rv(tip, 5), "ankle_y": r(ankle.y, 5), "tips_minus_ankle_y": r(tip.y - ankle.y, 5)}
    body_c = centroid(body)
    face_c = centroid(body, head_ix)
    wing_c = {"L": centroid(body, body_parts["tripo_part_0"]), "R": centroid(body, body_parts["tripo_part_1"])}
    span = hi_body[0] - lo_body[0]
    radial_body = max(math.hypot(v.co.x, v.co.y) for v in body.data.vertices)
    core = [v.co for p in ("tripo_part_2", "tripo_part_3", "tripo_part_5", "tripo_part_6", "tripo_part_7", "tripo_part_8")
            for v in [body.data.vertices[i] for i in sorted({vv for f in body_parts[p] for vv in body.data.polygons[f].vertices})]]
    radial_core = max(math.hypot(c.x, c.y) for c in core)
    talon_radial = max(math.hypot(c.x, c.y) for p in feet_parts.values() for c in part_points(body, body_parts[p]))
    bone_heads = {b.name: rv(b.head_local, 5) for b in arm.data.bones}
    # sockets
    head_centre = Vector([(min(p[a] for p in head_pts) + max(p[a] for p in head_pts)) / 2 for a in range(3)])
    sockets = []
    for sock in profile["sockets"]:
        bone = arm.data.bones[sock["bone"]]
        target = head_centre if sock["name"] == "Head" else talon_tips["R"]
        local = bone.matrix_local.inverted() @ target
        sockets.append({"name": sock["name"], "bone": sock["bone"], "target_blender_m": rv(target, 5),
                        "target_ue_component_uu": ue_from_blender_m(target),
                        "offset_blender_bone_local_uu": [r(c * 100, 3) for c in local],
                        "bone_head_ue_component_uu": ue_from_blender_m(bone.head_local),
                        "status": sock.get("status", "предложено")})
    root = arm.data.bones["root"]
    pivot = {"root_bone": root.name, "root_head_m": [r(c, 6) for c in root.head_local],
             "armature_object_location": [r(c, 6) for c in arm.location]}
    cross_part = cross_part_coincident(body, part_of_poly)
    base_mask = mask_census(base, bcfg["mask"]["attribute"])
    weapon_parent = arm.data.bones["weapon"].parent.name  # read now: Bone references die at the export's edit mode
    weapon_weighted = "weapon" in weights["body"]["bones_used"]
    tail_y = to_final("y", 0.03)
    tail_vids = sorted({v for i in body_parts["tripo_part_5"] for v in body.data.polygons[i].vertices
                        if body.data.vertices[v].co.y > tail_y})
    leg_groups = {g.index for g in body.vertex_groups if g.name.startswith("leg_")}
    tail_leg = sum(1 for v in tail_vids if any(g.group in leg_groups and g.weight > 0 for g in body.data.vertices[v].groups))
    low_xy = [(v.co.x, v.co.y) for v in body.data.vertices if v.co.z < fz + 0.015]
    pip_clearance = []
    for pip in base_info["pips"]:
        d = min(math.hypot(x - pip["centre_m"][0], y - pip["centre_m"][1]) for x, y in low_xy)
        pip_clearance.append(r(d - bcfg["pips"]["pip_radius_m"], 5))

    blend_out = Path(params["blend_out"])
    blend_out.parent.mkdir(parents=True, exist_ok=True)
    bpy.data.libraries.write(str(blend_out), {scene}, compress=False)

    step('export')
    # ---- export (UM_FBX_v1) on the in-memory copy; the work .blend stays authored
    transform_for_fbx(scene, arm, (body, base), Matrix.Scale(data_scale, 4) @ rot)
    sk_fbx, base_fbx = Path(params["sk_fbx_out"]), Path(params["base_fbx_out"])
    sk_fbx.parent.mkdir(parents=True, exist_ok=True)
    restore = make_fbx_deterministic()
    try:
        export_fbx(scene, sk_fbx, (arm, body), arm, {"ARMATURE", "MESH"}, preset)
    finally:
        restore()
    restore = make_fbx_deterministic()
    try:
        export_fbx(scene, base_fbx, (base,), base, {"MESH"}, preset)
    finally:
        restore()

    step('roundtrip')
    # ---- round trip
    rt = bpy.data.scenes.new(ROUNDTRIP_SCENE)
    import_fbx_into(rt, sk_fbx)
    rtb = bpy.data.scenes.new(ROUNDTRIP_SCENE + "_base")
    import_fbx_into(rtb, base_fbx)
    raw = {re.sub(r"\.\d{3}$", "", o.name): o for sc in (rt, rtb) for o in sc.objects if o.type == "MESH"}
    for key in ("body", "base"):
        if m[key]["object"] not in raw:
            raise RuntimeError("round trip lost meshes: %s" % sorted(raw))
    rb_export = raw[m["body"]["object"]]
    rb_parts_export, _ = polygons_by_part(rb_export.data, rects)
    lo_x, hi_x = world_bounds([rb_export])
    lo_xb, hi_xb = world_bounds([raw[m["base"]["object"]]])
    export_frame = {"body_centroid_m": centroid(rb_export),
                    "face_centroid_m": centroid(rb_export, rb_parts_export[profile["scale"]["top_part"]]),
                    "left_wing_centroid_m": centroid(rb_export, rb_parts_export["tripo_part_0"]),
                    "skeletal_bounds_cm": {"min": [r(c * 100, 3) for c in lo_x], "max": [r(c * 100, 3) for c in hi_x]},
                    "base_bounds_cm": {"min": [r(c * 100, 3) for c in lo_xb], "max": [r(c * 100, 3) for c in hi_xb]}}
    inverse = rot.inverted()
    to_authored_frame(rt, inverse)
    to_authored_frame(rtb, inverse)
    rt_sk, rt_sk_meshes = roundtrip_measure(rt, bone_names)
    rt_base, rt_base_meshes = roundtrip_measure(rtb, bone_names)
    rt_body, rt_base_obj = rt_sk_meshes[m["body"]["object"]], rt_base_meshes[m["base"]["object"]]
    rt_parts, rt_unassigned = polygons_by_part(rt_body.data, rects)
    rt_labelled = [(rt_body, rt_parts), (rt_base_obj, {"base": [p.index for p in rt_base_obj.data.polygons]})]
    orient_rt = orientation_scores(rt_labelled)
    rt_lo, rt_hi = world_bounds([rt_body])
    rt_mask = mask_census(rt_base_obj, bcfg["mask"]["attribute"])

    step('checks')
    # ---------------------------------------------------------------- checks
    exp = profile["expectations"]
    tris = {n: pre[n]["triangles"] for n in pre}
    if all(v is not None for v in exp["triangles"].values()):
        check("triangles_as_profile", tris == exp["triangles"], tris, exp["triangles"])
    else:
        check("triangles_as_profile", True, tris, exp["triangles"], "profile expectations not fixed yet: measured only")
    check("dropped_parts_as_profile", sorted(dropped) == sorted(m.get("drop_parts") or {}), dropped)
    check("caps_as_profile", all(len(caps.get(n, [])) == len(c["loops_source_centres"]) and
                                 all(cp["triangles"] == cp["loop_vertices"] and cp["max_angular_gap_deg"] < 90
                                     for cp in caps.get(n, []))
                                 for n, c in (profile.get("caps") or {}).items()),
          caps, {n: len(c["loops_source_centres"]) for n, c in (profile.get("caps") or {}).items()},
          "every listed open loop found and fan-filled all round (star-shaped ring: largest angular gap < 90 deg)")
    check("weld_inside_parts_measured", True, weld,
          note="bmesh remove_doubles at %s m inside each part; islands_after per part" % profile["weld"]["distance_m"])
    check("every_polygon_in_its_atlas_cell", unassigned == 0 and rt_unassigned == 0 and uv_matches_parts,
          {"body_build": unassigned, "body_roundtrip": rt_unassigned, "body_uv_cells_equal_part_labels": uv_matches_parts})
    uv_outside = sum(sv["loops_outside_cell_inner_rect"] for sv in uv_stats.values())
    check("uv0_single_layer_on_every_mesh", all(pre[n]["uv_layers"] == ["UVMap"] for n in pre),
          {n: pre[n]["uv_layers"] for n in pre})
    check("uv0_inside_unit_square", all(pre[n]["uv0_in_unit_square"] for n in pre),
          {n: pre[n]["uv0_in_unit_square"] for n in pre})
    check("uv0_inside_own_atlas_cell", uv_outside == 0, uv_outside,
          note="every UV corner lies in its part's inner cell rect (gutter kept)")
    check("uv0_raster_overlap_measured", True, {p: sv["overlap_ratio"] for p, sv in sorted(uv_stats.items())},
          note="informational: texels covered by >= 2 triangles / covered texels, per part at atlas resolution")
    check("weights_every_vertex_weighted", weights["body"]["unweighted_vertices"] == 0,
          weights["body"]["unweighted_vertices"])
    check("weights_normalised", weights["body"]["not_normalised_vertices"] == 0, weights["body"]["not_normalised_vertices"])
    check("weights_max_influences", weights["body"]["max_influences"] <= profile["armature"]["max_influences"],
          weights["body"]["max_influences"], profile["armature"]["max_influences"])
    allowed_ok = {n: sorted(set(per_part_weights[n]["bones_used"]) - allowed_of(rules[n])) for n in body_part_names}
    check("weights_only_group_bones", not any(allowed_ok.values()), allowed_ok,
          note="per part: bones outside the group's list (must be empty)")
    fallback = {n: st.get("fallback_nearest_bone", 0) for n, st in heat_stats.items()}
    check("weights_heat_fallback_measured", True, fallback,
          note="vertices the heat solve left unweighted, given 1.0 on the nearest allowed bone (informational)")
    wing_ok = all(set(per_part_weights[p]["bones_used"]) >= set(rules[p]["wing_span"]["chain"]) for p in wing_info)
    check("weights_wings_on_arm_chain", wing_ok, {p: per_part_weights[p]["weight_share"] for p in sorted(wing_info)},
          "each wing uses arm_upper, arm_lower and hand of its side (rig-contract harpy_wings)")
    check("weights_tail_follows_hips", len(tail_vids) > 0 and tail_leg == 0,
          {"tail_vertices_behind_source_y_0_03": len(tail_vids), "with_leg_weight": tail_leg},
          "tail feathers of tripo_part_5 behind source y 0.03 carry no leg weight")
    check("weapon_bone_kept_unweighted", "weapon" in arm.data.bones and not weapon_weighted
          and weapon_parent == "hand.L",
          {"present": "weapon" in arm.data.bones, "weighted": weapon_weighted, "parent": weapon_parent},
          note="17-bone set kept for validate_clip.py; Harpy has no weapon (rig-contract parent_by_character Harpy = null)")
    height = hi_all[2] - lo_all[2]
    check("height_m", abs(head_top - profile["scale"]["figure_height_m"]) < 1e-5 and abs(lo_all[2]) < 1e-6
          and abs(hi_all[2] - head_top) < 1e-9,
          {"head_top": r(head_top, 6), "top_of_all": r(hi_all[2], 6), "lowest": r(lo_all[2], 6)},
          profile["scale"]["figure_height_m"])
    check("feet_on_base_top", -0.006 <= feet_low - fz <= 0.0005,
          {"lowest_talon_vertex_z": r(feet_low, 5), "base_top_z": fz, "sink_m": r(fz - feet_low, 5)},
          "talons at most 6 mm into the base top (source: they sink 7.4 mm into the Tripo base = 4.9 mm at scale)")
    base_dims = [r(hi_base[i] - lo_base[i], 6) for i in range(3)]
    base_body_dims = [r(2 * bcfg["radius_bottom_m"], 6), r(2 * bcfg["radius_bottom_m"], 6),
                      r(bcfg["height_m"] + bcfg["pips"]["raise_m"], 6)]
    check("base_footprint_and_pivot", all(abs(a - b) < 1e-6 for a, b in zip(base_dims[:2], (fx, fy)))
          and abs(base_dims[2] - base_body_dims[2]) < 1e-6
          and all(abs(lo_base[i] + hi_base[i]) < 1e-6 for i in range(2)) and abs(lo_base[2]) < 1e-6,
          {"dimensions_m": base_dims, "centre_xy_m": [r((lo_base[i] + hi_base[i]) / 2, 6) for i in range(2)],
           "bottom_z_m": r(lo_base[2], 6)},
          {"dimensions_m": [fx, fy, "%s + pip raise %s" % (fz, bcfg["pips"]["raise_m"])], "centre_xy_m": [0, 0], "bottom_z_m": 0})
    check("base_pips_clear_of_talons", len(base_info["pips"]) == 9 and min(pip_clearance) > 0.001,
          {"pips": len(base_info["pips"]), "talon_max_radius_m": r(talon_radial, 5),
           "per_pip_xy_clearance_m": pip_clearance, "min_m": min(pip_clearance)},
          "9 pips; every pip edge > 1 mm (XY) from any body vertex lower than 1.5 cm above the base top")
    check("base_mask_binary_and_complete", bool(base_mask) and base_mask["binary"]
          and set(base_mask["rgb_counts"]) == {"000", "100", "010", "001"},
          base_mask, note="UM_Mask corners: 000 top/bottom, 100 team band, 010 centre pips, 001 outer pips")
    check("pivot_root_at_origin", pivot["root_head_m"] == [0.0, 0.0, 0.0] and
          pivot["armature_object_location"] == [0.0, 0.0, 0.0], pivot)
    check("armature_object_name_contract", arm.name == profile["armature"]["object"], arm.name,
          profile["armature"]["object"])
    front_ok = (all(t["tips_minus_ankle_y"] < -0.02 for t in toe_ankle.values()) and face_c[1] - body_c[1] < -0.02)
    check("axes_front_minus_y", front_ok, {"feet": toe_ankle, "body_centroid_m": body_c, "face_part_centroid_m": face_c},
          "talon tips ahead of the ankles (-Y) by > 2 cm, head part ahead of the body centroid by > 2 cm")
    check("axes_left_wing_on_plus_x", wing_c["L"][0] > 0.05 and wing_c["R"][0] < -0.05, wing_c,
          "tripo_part_0 (.L chain) on +X, tripo_part_1 on -X")
    front_name, left_name = axis_name(front_export), axis_name(left_export)
    ef = export_frame
    rel_face = [ef["face_centroid_m"][i] - ef["body_centroid_m"][i] for i in range(3)]
    rel_wing = [ef["left_wing_centroid_m"][i] - ef["body_centroid_m"][i] for i in range(3)]
    face_along, _ = along(rel_face, front_export)
    wing_side, _ = along(rel_wing, left_export)
    check("export_frame_face_front_left_wing_rotated", face_along > 0.02 and wing_side > 0.05,
          {"face_minus_body_along_front": face_along, "left_wing_minus_body_along_left": wing_side},
          "front %s, left wing %s (authored -Y / +X rotated by %s deg about Z)"
          % (front_name, left_name, preset["export_space_rotation_z_degrees"]))
    all_tris = {n: [pre[n]["polygons"], pre[n]["triangles"]] for n in pre}
    rt_all = dict(rt_sk["meshes"], **rt_base["meshes"])
    body_all_tris = pre[m["body"]["object"]]["polygons"] == pre[m["body"]["object"]]["triangles"]
    check("triangulate_changes_no_body_geometry", body_all_tris and
          all(e["polygons"] == e["triangles"] for e in rt_all.values()),
          {"pre_export_polygons_triangles": all_tris,
           "roundtrip_polygons_triangles": {n: [e["polygons"], e["triangles"]] for n, e in sorted(rt_all.items())}},
          note="preset use_triangles=%s; the body is all triangles, the base quads are triangulated by the export" % preset["use_triangles"])
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
    check("roundtrip_triangles_preserved", rt_tris[m["body"]["object"]] == tris[m["body"]["object"]]
          and rt_tris[m["base"]["object"]] >= tris[m["base"]["object"]],
          rt_tris, tris, "body equal; the base quads become 2 triangles each")
    rt_slots = {n: e["material_slots"] for n, e in rt_all.items()}
    sk_unique = sorted({sl for sl in rt_slots.get(m["body"]["object"], []) if sl})
    check("roundtrip_material_slots", len(sk_unique) == exp["skeletal_material_slots"] and
          len(rt_slots.get(m["base"]["object"], [])) == exp["base_material_slots"],
          {"per_mesh": rt_slots, "skeletal_unique": sk_unique},
          {"skeletal_unique": exp["skeletal_material_slots"], "base": exp["base_material_slots"]})
    check("roundtrip_uv0", all(e["uv_layers"] == ["UVMap"] and e["uv0_in_unit_square"] for e in rt_all.values()),
          {n: e["uv_layers"] for n, e in rt_all.items()})
    check("roundtrip_base_mask", bool(rt_mask) and rt_mask["binary"] and set(rt_mask["rgb_counts"]) == set(base_mask["rgb_counts"]),
          {"build": base_mask, "roundtrip": rt_mask},
          note="UM_Mask survives the FBX (colors_type %s) with binary values and the same four classes; corner counts "
               "differ because the export triangulates the base quads" % COLORS_TYPE)
    rt_w = {n: e["weights"] for n, e in rt_sk["meshes"].items()}
    check("roundtrip_weights", rt_w[m["body"]["object"]]["unweighted_vertices"] == 0 and
          max(w["max_influences"] for w in rt_w.values()) <= profile["armature"]["max_influences"],
          {n: {k: w[k] for k in ("max_influences", "unweighted_vertices", "not_normalised_vertices")}
           for n, w in rt_w.items()})
    rt_bad = sorted(p for p, sc in orient_rt.items() if sc["score"] is None or sc["score"] < ocfg["min_score_after_fix"])
    check("roundtrip_orientation_all_parts_outward", not rt_bad,
          {p: sc["score"] for p, sc in sorted(orient_rt.items())}, ">= %s" % ocfg["min_score_after_fix"])
    ratio = [r((rt_hi[i] - rt_lo[i]) / (hi_body[i] - lo_body[i]), 6) for i in range(3)]
    check("roundtrip_scale_ratio_1", all(abs(v - 1) < 1e-4 for v in ratio), ratio,
          note="Blender re-reads the cm FBX (UnitScaleFactor 1.0) as metres")
    check("roundtrip_part_polygon_counts", {p: len(v) for p, v in sorted(rt_parts.items())} ==
          {p: len(v) for p, v in sorted(body_parts.items())}, {p: len(v) for p, v in sorted(rt_parts.items())})
    lim = profile["proposed_limits_for_comparison_only"]
    comparison = {
        "sidekick_triangles": {"measured_body": tris[m["body"]["object"]], "with_base": sum(tris.values()),
                               "proposed": lim["sidekick_triangles"]},
        "base_triangles": {"measured_after_triangulation": rt_tris[m["base"]["object"]], "proposed": lim["base_triangles"]},
        "texture_px": {"measured": size, "proposed": lim["texture_px"],
                       "note": "2K atlas at native part-texture size; the 1K proposal can be met on import (MaxTextureSize 1024)"},
        "material_slots": {"measured_skeletal_unique": len(sk_unique), "base": len(rt_slots.get(m["base"]["object"], [])),
                           "total": len(sk_unique) + len(rt_slots.get(m["base"]["object"], [])),
                           "proposed_max": lim["material_slots_max"]},
        "height_uu": {"measured_head_top": r(head_top * 100, 3), "proposed": lim["height_uu"]},
        "span_uu": {"measured": r(span * 100, 3), "proposed_max": lim["span_max_uu"],
                    "fits": bool(span * 100 <= lim["span_max_uu"])},
        "base_uu": {"measured": [r(c * 100, 3) for c in base_dims], "proposed_diameter": lim["base_diameter_uu"],
                    "proposed_height": lim["base_height_uu"]},
        "capsule_uu": {"body_max_radius_from_pivot_axis": r(radial_body * 100, 3),
                       "core_max_radius_without_wings": r(radial_core * 100, 3),
                       "top": r(hi_body[2] * 100, 3), "proposed": lim["capsule_uu"],
                       "core_fits": bool(radial_core * 100 <= lim["capsule_uu"]["diameter"] / 2 + 1e-6
                                         and hi_body[2] * 100 <= lim["capsule_uu"]["height"]),
                       "note": "the wings (span %.1f uu) are outside a Ø26 capsule by design; the capsule is the selection body, the wings stay within the cell (100 uu)" % (span * 100)},
        "note": "comparison with proposals only, not budgets (GD-058 open)"}

    report = {
        "stage": "build",
        "builder": BUILDER,
        "builder_sha256": sha256(Path(__file__)) if "__file__" in globals() else None,
        "blender": bpy.app.version_string,
        "profile": {"id": profile["profile_id"], "status": profile["status"]},
        "source": {"file": source.name, "sha256": source_hash},
        "reference": {"file": reference.name, "sha256": reference_hash, "role": rcfg["role"], "use": "per-face orientation vote only"},
        "isolation_note": "process",
        "scale": scale_info,
        "source_part_polygons": source_polys,
        "dropped_parts": dropped,
        "weld": weld,
        "caps": caps,
        "body_parts": sorted(body_parts),
        "body_part_polygons": {p: len(v) for p, v in sorted(body_parts.items())},
        "cross_part_coincident_vertices": cross_part,
        "orientation": {"method": ocfg["method"], "raw_tripo": orient_raw, "before_reference_fix": orient_before_ref,
                        "reference_vote": ref_votes, "before_fix": orient_before, "flipped_parts": inside_out,
                        "after_fix": orient_after, "roundtrip": orient_rt, "corner_normals_opposed_area_share": opposed,
                        "corner_normals_preserved": normals_preserved},
        "materials": {"atlas": "M_Harpy_Atlas", "blender_images": mat_images, "base": bcfg["material"]},
        "base": {"parametric": base_info, "mask": base_mask, "roundtrip_mask": rt_mask,
                 "talon_max_radius_m": r(talon_radial, 5)},
        "meshes_pre_export_m": pre,
        "weights": weights,
        "weights_per_part": per_part_weights,
        "weights_cleanup": heat_stats,
        "wings": wing_info,
        "uv": uv_stats,
        "bones_final_m": bones_final,
        "bones_head_m": bone_heads,
        "sockets": sockets,
        "bounds_m": {"body": {"min": [r(c) for c in lo_body], "max": [r(c) for c in hi_body]},
                     "base": {"min": [r(c) for c in lo_base], "max": [r(c) for c in hi_base]},
                     "figure_with_base_height": r(height), "head_top": r(head_top), "span": r(span)},
        "expected_ue_bounds_uu_at_import_scale_1": {
            "skeletal_blender_axes": {"min": [r(c * 100, 3) for c in lo_body], "max": [r(c * 100, 3) for c in hi_body]},
            "base_blender_axes": {"min": [r(c * 100, 3) for c in lo_base], "max": [r(c * 100, 3) for c in hi_base]},
            "export_rotation_z_degrees": float(preset["export_space_rotation_z_degrees"]),
            "skeletal_export_frame": export_frame["skeletal_bounds_cm"],
            "base_export_frame": export_frame["base_bounds_cm"],
            "skeletal_ue_predicted": ue_predicted(export_frame["skeletal_bounds_cm"]),
            "base_ue_predicted": ue_predicted(export_frame["base_bounds_cm"]),
            "note": "*_blender_axes: authored frame (front -Y), centimetres; *_export_frame: as written into the FBX "
                    "(re-imported); *_ue_predicted: export frame mapped as UE (x, -y, z) per ART-001"},
        "axes": {"feet": toe_ankle, "body_centroid_m": body_c, "face_part_centroid_m": face_c, "wing_centroids_m": wing_c,
                 "export_frame": {k: export_frame[k] for k in ("body_centroid_m", "face_centroid_m", "left_wing_centroid_m")},
                 "export_front_axis": front_name, "export_left_wing_axis": left_name},
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
                                 "path_mode": PATH_MODE, "embed_textures": False, "colors_type": COLORS_TYPE,
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
            "selection collision (04 §3.2 UCP_ 26x48 uu proposal; skeletal meshes use a physics asset in UE)",
            "UE-side facing, sockets, vertex-colour import and the base material: ue-import stage (deferred)",
        ],
    }
    out = Path(params["report_out"])
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=2, sort_keys=True, ensure_ascii=False) + "\n", encoding="utf-8")
    if sha256(source) != source_hash or sha256(reference) != reference_hash:
        raise RuntimeError("source or reference GLB changed during build")
    if not report["passed"]:
        raise RuntimeError("build checks failed: %s" % sorted(k for k, c in checks.items() if not c["passed"]))
    print(MARKER, "isolation=process", "sk=%s" % report["exports"]["skeletal"]["sha256"][:12],
          "base=%s" % report["exports"]["base"]["sha256"][:12])


main()
