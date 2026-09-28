"""Stage `build`: segmented Tripo GLB -> skeletal game candidate (body + bow) and a separate base.

Run only through tripo_pipeline.py, in the isolation modes of import_source.py:
``process`` (headless ``blender -b``, factory-empty scene) or ``live`` (running
Blender GUI via blender_mcp.py ``execute_code``: work happens in temporary scenes,
the user's file is never reset, opened or saved, every datablock created here is
removed again and the FBX exporter patches are reverted).

params.json: {"source": abs GLB, "profile": abs build profile, "atlas_report": abs,
              "textures_dir": abs, "repo_root": abs, "blend_out": abs, "fbx_preset": abs JSON,
              "sk_fbx_out": abs, "base_fbx_out": abs, "report_out": abs}

What it does (data-driven by the build profile; the algorithm follows
blender/ASSET-MEDUSA-001/build_segmented_medusa.py and the face/neck fix of
tools/art/art004_face_skeletal_export.py, without writing into either place):
  1. import the GLB, bake part transforms, remap part UVs into the atlas cells,
     scale the whole figure to the profile height with the base bottom at z = 0;
  2. join all parts except bow and base into the body, normalise the base footprint;
  3. measure polygon orientation per part (ray-escape test) and flip the parts that
     are inside-out (winding flip + negated custom corner normals);
  4. build the armature from the profile, weight the body by part rules, bind the
     bow 100 % to its bone; add the face material slot;
  5. write work .blend, export the skeletal FBX and the base FBX byte-deterministically with
     the verified preset UM_FBX_v1 (blender/_tools/presets/UM_FBX_v1.json, ART-001 PASS,
     04-blender-production.md §1/§1.1): the in-memory figure is rotated +90 deg about Z
     (authored front -Y -> +X, which UE keeps as +X) and scaled to centimetre numbers,
     FBX_SCALE_UNITS, -Y forward, Z up, Triangulate on, UnitScaleFactor patched to 1.0.
     Bones are rotated with EditBone.transform(roll=True): the rest pose turns rigidly
     with the mesh, so parent-relative bone frames and socket offsets stay the same;
  6. re-import both FBX in an empty scene; measure the export frame (face must point along
     the preset's rotated front), then turn the round trip back into the authored frame and
     measure every import contract there;
  7. optionally compare with a reference FBX (read only; references are unrotated, the
     comparison runs in the authored frame).
The report is deterministic (rounded floats, sorted keys, no timestamps).
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

MARKER = "TRIPO_PIPELINE_STAGE_OK build"
FIXED_TIME = datetime.datetime(2000, 1, 1, 0, 0, 0)
WORK_SCENE = "tripo_pipeline_candidate"
ROUNDTRIP_SCENE = "tripo_pipeline_candidate_roundtrip"
REFERENCE_SCENE = "tripo_pipeline_candidate_reference"
ID_COLLECTIONS = ("objects", "meshes", "materials", "images", "textures", "node_groups", "collections",
                  "cameras", "lights", "armatures", "actions", "worlds", "scenes", "libraries")


def r(value, nd=6):
    return round(float(value), nd)


def sha256(path):
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_params():
    injected = globals().get("TRIPO_PIPELINE_PARAMS")
    path = injected if injected else sys.argv[sys.argv.index("--") + 1]
    return json.loads(Path(path).read_text(encoding="utf-8"))


PRESET_KEYS = ("name", "axis_forward", "axis_up", "export_space_rotation_z_degrees", "temporary_data_scale",
               "patch_fbx_unit_scale_to", "apply_unit_scale", "apply_scale_options", "use_triangles",
               "mesh_smooth_type", "add_leaf_bones", "primary_bone_axis", "secondary_bone_axis", "path_mode")
# Deliberate, reported deviation from the preset: FBX keeps bare texture file names. The preset's "AUTO"
# would write a path relative to the staging directory (wrong after promotion, host specific); the
# candidate's textures are imported into UE separately from the atlas stage, never through the FBX.
PATH_MODE = "STRIP"


def load_preset(path):
    preset = json.loads(Path(path).read_text(encoding="utf-8"))
    missing = [k for k in PRESET_KEYS if k not in preset]
    if missing:
        raise RuntimeError("FBX preset %s lacks %s" % (path, missing))
    return preset


def export_rotation(preset):
    """Rotation about Z; multiples of 90 deg are snapped to an exact axis permutation (cos 90 = 6e-17
    otherwise perturbs float32 coordinates and flips the normals of sliver triangles)."""
    rot = Matrix.Rotation(math.radians(float(preset["export_space_rotation_z_degrees"])), 4, "Z")
    for i in range(4):
        for j in range(4):
            value = rot[i][j]
            if abs(value - round(value)) < 1e-9:
                rot[i][j] = float(round(value))
    return rot


def id_snapshot():
    return {name: set(getattr(bpy.data, name)) for name in ID_COLLECTIONS}


def remove_new_ids(before):
    doomed = []
    for name in ID_COLLECTIONS:
        doomed.extend(i for i in getattr(bpy.data, name) if i not in before[name])
    if doomed:
        bpy.data.batch_remove(doomed)
    return len(doomed)


@contextmanager
def scene_context(scene):
    """Operators run in `scene`: switch the window's scene (restored afterwards)."""
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
    """Same pinning as export_fbx.py: header time, UUID hash, texture paths. Returns restore()."""
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


class Namer:
    """Canonical (headless) names when the live session already owns a name (.NNN suffix)."""

    def __init__(self, before_ids):
        self.existing = {kind: {i.name for i in ids} for kind, ids in before_ids.items()}
        self.collisions = defaultdict(set)

    def __call__(self, idb, kind):
        match = re.match(r"^(.*)\.(\d{3})$", idb.name)
        if match and match.group(1) in self.existing[kind]:
            self.collisions[kind].add(idb.name)
            return match.group(1)
        return idb.name

    def note_new(self, kind, before_ids):
        for idb in getattr(bpy.data, kind):
            if idb not in before_ids[kind]:
                self(idb, kind)

    def report(self):
        return {kind: sorted(names) for kind, names in sorted(self.collisions.items()) if names}


# ------------------------------------------------------------------ measurements

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
        for name, (u0, u1, v0, v1) in rects.items():
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
    """Per part: UV0 containment in the cell, texel density, raster overlap at atlas resolution."""
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
            cell = cells[part]
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
                         "overlap_ratio": r(overlapped / covered, 5) if covered else 0.0,
                         "cell_px": width}
    return out


def weight_summary(obj, bone_names):
    groups = {g.index: g.name for g in obj.vertex_groups}
    bone_idx = {i for i, n in groups.items() if n in bone_names}
    max_inf, unweighted, used = 0, 0, Counter()
    for v in obj.data.vertices:
        ws = [(groups[g.group], g.weight) for g in v.groups if g.group in bone_idx and g.weight > 0]
        max_inf = max(max_inf, len(ws))
        if not ws:
            unweighted += 1
        for name, _w in ws:
            used[name] += 1
    return {"vertices": len(obj.data.vertices), "max_influences": max_inf, "unweighted_vertices": unweighted,
            "bones_used": dict(sorted(used.items()))}


DEGENERATE_AREA_CM2 = 1e-4  # UE's mesh build drops such slivers (measured: 2 base triangles at 1e-7..1e-6 cm2)


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
            "material_slots": [re.sub(r"\.\d{3}$", "", s.material.name) if s.material else None
                               for s in obj.material_slots],
            "has_custom_normals": bool(mesh.has_custom_normals)}


def facing(obj, indices):
    mw = obj.matrix_world
    rot = mw.to_3x3()
    acc = Vector((0, 0, 0))
    for i in indices:
        p = obj.data.polygons[i]
        acc += (rot @ p.normal).normalized() * p.area
    total = sum(obj.data.polygons[i].area for i in indices)
    return [r(c / total, 4) for c in acc] if total else None


# ------------------------------------------------------------------------- build

def import_glb(scene, source):
    with scene_context(scene):
        bpy.ops.import_scene.gltf(filepath=str(source))


def atlas_material(profile, textures_dir, texture_files, name):
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


def prepare_parts(scene, profile, atlas, textures_dir, namer, before_ids):
    parts = {}
    for obj in list(scene.objects):
        if obj.type == "MESH":
            parts[namer(obj, "objects")] = obj
    if len(parts) != profile["expected_part_count"]:
        raise RuntimeError("expected %d mesh parts, found %d" % (profile["expected_part_count"], len(parts)))
    for obj in parts.values():
        world = obj.matrix_world.copy()
        obj.parent = None
        obj.data.transform(world)
        obj.matrix_world.identity()
    for obj in [o for o in scene.objects if o.type != "MESH"]:
        bpy.data.objects.remove(obj)  # glTF helper empties; parts are already baked to world
    top = max(v.co.z for o in parts.values() for v in o.data.vertices)
    bottom = min(v.co.z for o in parts.values() for v in o.data.vertices)
    scale = profile["scale"]["figure_height_m"] / (top - bottom)
    files = {k: v["file"] for k, v in atlas["files"].items()}
    mat, mat_images = atlas_material(profile, textures_dir, files, profile["materials"]["atlas"])
    size = atlas["size"]
    for name, obj in parts.items():
        cell = atlas["cells"][name]
        x, y, width, inset = cell["x"], cell["y_top"], cell["cell"], cell["inset"]
        inner = width - 2 * inset
        for uv_data in obj.data.uv_layers.active.data:
            uv = uv_data.uv.copy()
            uv_data.uv = ((x + inset + uv.x * inner) / size, 1 - (y + inset + (1 - uv.y) * inner) / size)
        for vert in obj.data.vertices:
            vert.co = (vert.co - Vector((0, 0, bottom))) * scale
        obj.data.materials.clear()
        obj.data.materials.append(mat)
        obj.data.update()
    return parts, mat, mat_images, {"source_top": r(top), "source_bottom": r(bottom), "scale": r(scale, 8)}


def join_body(scene, parts, profile):
    meshes = profile["meshes"]
    excluded = {meshes["bow"]["part"], meshes["base"]["part"]}
    body_parts = [obj for name, obj in sorted(parts.items()) if name not in excluded]
    for name, obj in parts.items():
        if name in excluded:
            continue
        group = obj.vertex_groups.new(name="SRC_" + name)
        group.add(list(range(len(obj.data.vertices))), 1.0, "REPLACE")
    with scene_context(scene):
        bpy.ops.object.select_all(action="DESELECT")
        for obj in body_parts:
            obj.select_set(True)
        body = parts[meshes["body"]["active_part"]]
        bpy.context.view_layer.objects.active = body
        bpy.ops.object.join()
    body.name = meshes["body"]["object"]
    body.data.name = meshes["body"]["mesh"]
    bow = parts[meshes["bow"]["part"]]
    bow.name = meshes["bow"]["object"]
    base = parts[meshes["base"]["part"]]
    base.name = meshes["base"]["object"]
    fx, fy, fz = meshes["base"]["footprint_m"]
    coords = [v.co for v in base.data.vertices]
    lo = [min(c[a] for c in coords) for a in range(3)]
    hi = [max(c[a] for c in coords) for a in range(3)]
    for v in base.data.vertices:
        v.co.x = (v.co.x - (lo[0] + hi[0]) / 2) * (fx / (hi[0] - lo[0]))
        v.co.y = (v.co.y - (lo[1] + hi[1]) / 2) * (fy / (hi[1] - lo[1]))
        v.co.z = (v.co.z - lo[2]) * (fz / (hi[2] - lo[2]))
    base.data.update()
    return body, bow, base, sorted(p for p in parts if p not in excluded)


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


def rule_weights(rule, z):
    if "bone" in rule:
        return [(rule["bone"], 1.0)]
    if "split_z" in rule:
        return rule_weights(rule["below"] if z < rule["split_z"] else rule["above"], z)
    b = rule["blend"]
    t = max(0.0, min(1.0, (z - b["center"]) / b["span"] + 0.5))
    return [(b["low"], 1 - t), (b["high"], t)]


def bind_body(arm, body, profile, body_part_names):
    groups = {bone.name: body.vertex_groups.new(name=bone.name) for bone in arm.data.bones}
    rules = {}
    for rule in profile["weights"]:
        for part in rule["parts"]:
            rules[part] = rule
    missing_rules = sorted(set(body_part_names) - set(rules))
    if missing_rules:
        raise RuntimeError("no weight rule for parts %s" % missing_rules)
    counts = {}
    for part in body_part_names:
        group = body.vertex_groups["SRC_" + part]
        indices = [v.index for v in body.data.vertices if any(g.group == group.index for g in v.groups)]
        counts[part] = len(indices)
        for index in indices:
            for bone, weight in rule_weights(rules[part], body.data.vertices[index].co.z):
                if weight > 1e-5:
                    groups[bone].add([index], weight, "REPLACE")
    for group in list(body.vertex_groups):
        if group.name.startswith("SRC_"):
            body.vertex_groups.remove(group)
    body.parent = arm
    body.modifiers.new("Armature", "ARMATURE").object = arm
    return counts


def bind_bow(arm, bow, bone):
    group = bow.vertex_groups.new(name=bone)
    group.add(list(range(len(bow.data.vertices))), 1.0, "REPLACE")
    bow.parent = arm
    bow.modifiers.new("Armature", "ARMATURE").object = arm


def flip_polygons(mesh, selected):
    """Flip winding of `selected` polygons and negate their custom corner normals (RESTORE_NORMALS)."""
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
    """UM_FBX_v1 export space on the in-memory figure: rotation about Z and metres -> centimetre numbers.

    Bones use EditBone.transform(roll=True), i.e. the whole rest pose turns rigidly with the mesh
    (batch_export.py of ART-001 moves only head/tail; for vertical bones that leaves the local X/Z
    axes unrotated). Object transforms are identity here; locations are rotated for completeness.
    """
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
    """Undo the export rotation on a re-imported scene so it can be compared with the authored data."""
    for obj in scene.objects:
        if obj.parent is None:
            obj.matrix_world = inverse @ obj.matrix_world
    scene.view_layers[0].update()


def centroid(obj):
    mw = obj.matrix_world
    n = len(obj.data.vertices)
    return [r(sum((mw @ v.co)[a] for v in obj.data.vertices) / n, 5) for a in range(3)]


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


def axis_name(vector):
    x, y = round(vector[0]), round(vector[1])
    return {(1, 0): "+X", (-1, 0): "-X", (0, 1): "+Y", (0, -1): "-Y"}.get((x, y), "?")


# ---------------------------------------------------------------- round trip / reference

def import_fbx_into(scene, path):
    with scene_context(scene):
        bpy.ops.import_scene.fbx(filepath=str(path))


def roundtrip_measure(scene, profile, atlas, rects, bone_names):
    arms = [o for o in scene.objects if o.type == "ARMATURE"]
    meshes = {re.sub(r"\.\d{3}$", "", o.name): o for o in scene.objects if o.type == "MESH"}
    out = {"armatures": len(arms), "meshes": {}, "bones": {}}
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


# ------------------------------------------------------------------------- main

def main():
    isolation = globals().get("TRIPO_PIPELINE_ISOLATION", "process")
    params = load_params()
    profile = json.loads(Path(params["profile"]).read_text(encoding="utf-8"))
    atlas = json.loads(Path(params["atlas_report"]).read_text(encoding="utf-8"))
    source = Path(params["source"])
    repo = Path(params["repo_root"])
    source_hash = sha256(source)
    if not params.get("fbx_preset"):
        raise RuntimeError("params.fbx_preset is required (UM_FBX_v1, 04-blender-production.md §1.1)")
    preset_path = Path(params["fbx_preset"])
    preset = load_preset(preset_path)
    try:
        preset_rel = preset_path.resolve().relative_to(repo.resolve()).as_posix()
    except ValueError:
        preset_rel = preset_path.name
    rot = export_rotation(preset)
    rot3 = rot.to_3x3()
    data_scale = float(preset["temporary_data_scale"])
    front_export = rot3 @ Vector((0.0, -1.0, 0.0))  # authored front -Y in the export frame
    bow_export = rot3 @ Vector((1.0, 0.0, 0.0))     # authored bow side +X in the export frame
    if isolation == "process":
        bpy.ops.wm.read_factory_settings(use_empty=True)
    elif isolation != "live":
        raise RuntimeError("unknown isolation mode %r" % isolation)
    for name in (WORK_SCENE, ROUNDTRIP_SCENE, REFERENCE_SCENE):
        if name in bpy.data.scenes:
            raise RuntimeError("scene %r already exists (leftover of an interrupted pipeline stage?); "
                               "remove it by hand before re-running" % name)
    before_ids = id_snapshot()
    namer = Namer(before_ids)
    restore = None
    removed = 0
    checks = {}

    def check(name, passed, measured=None, expected=None, note=None):
        item = {"passed": bool(passed), "measured": measured}
        if expected is not None:
            item["expected"] = expected
        if note:
            item["note"] = note
        checks[name] = item

    try:
        scene = bpy.data.scenes.new(WORK_SCENE)
        scene.unit_settings.system = "METRIC"
        scene.unit_settings.scale_length = 1.0
        import_glb(scene, source)
        parts, atlas_mat, mat_images, scale_info = prepare_parts(scene, profile, atlas, params["textures_dir"],
                                                                 namer, before_ids)
        source_polys = {name: len(obj.data.polygons) for name, obj in sorted(parts.items())}
        body, bow, base, body_part_names = join_body(scene, parts, profile)
        size = atlas["size"]
        rects = cell_rects(atlas["cells"], size)
        body_parts, unassigned = polygons_by_part(body.data, rects)
        labelled = [(body, body_parts), (bow, {profile["meshes"]["bow"]["part"]: [p.index for p in bow.data.polygons]}),
                    (base, {profile["meshes"]["base"]["part"]: [p.index for p in base.data.polygons]})]
        orient_before = orientation_scores(labelled)
        ocfg = profile["orientation"]
        inside_out = sorted(p for p, s in orient_before.items()
                            if s["score"] is not None and s["score"] < ocfg["flip_below_score"])
        check("orientation_inside_out_parts_as_profile", inside_out == sorted(ocfg["expected_inside_out_parts"]),
              inside_out, sorted(ocfg["expected_inside_out_parts"]),
              "ray-escape score < %s on the Tripo geometry" % ocfg["flip_below_score"])
        not_in_body = [p for p in inside_out if p not in body_parts]
        if not_in_body:
            raise RuntimeError("inside-out parts outside the body are not supported: %s" % not_in_body)
        arm = make_armature(scene, profile)
        part_vertex_counts = bind_body(arm, body, profile, body_part_names)
        bind_bow(arm, bow, profile["meshes"]["bow"]["bone"])
        selected = {i for p in inside_out for i in body_parts[p]}
        flip_polygons(body.data, selected)
        face_cfg = profile["materials"].get("face_slot")
        if face_cfg:
            face_mat = atlas_mat.copy()
            face_mat.name = face_cfg["material"]
            body.data.materials.append(face_mat)
            for index in body_parts[face_cfg["part"]]:
                body.data.polygons[index].material_index = 1
            body.data.update()
        orient_after = orientation_scores(labelled)
        bad_after = sorted(p for p, s in orient_after.items()
                           if s["score"] is None or s["score"] < ocfg["min_score_after_fix"])
        check("orientation_all_parts_outward_after_fix", not bad_after,
              {p: s["score"] for p, s in sorted(orient_after.items())}, ">= %s" % ocfg["min_score_after_fix"])

        # ---- pre-export measurements (metres)
        bone_names = [b[0] for b in profile["armature"]["bones"]]
        m0 = profile["meshes"]
        pre = {m0["body"]["object"]: mesh_summary(body), m0["bow"]["object"]: mesh_summary(bow),
               m0["base"]["object"]: mesh_summary(base)}
        weights = {"body": weight_summary(body, bone_names), "bow": weight_summary(bow, bone_names)}
        uv_stats = uv_statistics(labelled, atlas["cells"], size, 100.0)
        lo_sk, hi_sk = world_bounds([body, bow])
        lo_base, hi_base = world_bounds([base])
        lo_all, hi_all = world_bounds([body, bow, base])
        face_part = face_cfg["part"] if face_cfg else "tripo_part_10"
        axes = {"face_mean_normal": facing(body, body_parts[face_part]),
                "bow_centroid_m": [r(sum((bow.matrix_world @ v.co)[a] for v in bow.data.vertices) / len(bow.data.vertices), 5)
                                   for a in range(3)]}
        root = arm.data.bones[profile["armature"]["bones"][0][0]]
        pivot = {"root_bone": root.name, "root_head_m": [r(c, 6) for c in root.head_local],
                 "armature_object_location": [r(c, 6) for c in arm.location]}

        blend_out = Path(params["blend_out"])
        blend_out.parent.mkdir(parents=True, exist_ok=True)
        bpy.data.libraries.write(str(blend_out), {scene}, compress=False)

        # ---- export (UM_FBX_v1: rotate + scale the in-memory copy; the work .blend above stays authored)
        transform_for_fbx(scene, arm, (body, bow, base), Matrix.Scale(data_scale, 4) @ rot)
        sk_fbx, base_fbx = Path(params["sk_fbx_out"]), Path(params["base_fbx_out"])
        sk_fbx.parent.mkdir(parents=True, exist_ok=True)
        namer.note_new("objects", before_ids)
        namer.note_new("materials", before_ids)
        namer.note_new("meshes", before_ids)
        namer.note_new("armatures", before_ids)
        restore = make_fbx_deterministic()
        export_fbx(scene, sk_fbx, (arm, body, bow), arm, {"ARMATURE", "MESH"}, preset)
        restore()
        restore = make_fbx_deterministic()
        export_fbx(scene, base_fbx, (base,), base, {"MESH"}, preset)
        restore()
        restore = None

        # ---- round trip: first the export frame as written, then back into the authored frame
        m = profile["meshes"]
        rt = bpy.data.scenes.new(ROUNDTRIP_SCENE)
        import_fbx_into(rt, sk_fbx)
        rt_base_scene = bpy.data.scenes.new(ROUNDTRIP_SCENE + "_base")
        import_fbx_into(rt_base_scene, base_fbx)
        raw = {re.sub(r"\.\d{3}$", "", o.name): o for s in (rt, rt_base_scene) for o in s.objects if o.type == "MESH"}
        if not all(raw.get(m[k]["object"]) for k in ("body", "bow", "base")):
            raise RuntimeError("round trip lost meshes: %s" % sorted(raw))
        raw_parts, _ = polygons_by_part(raw[m["body"]["object"]].data, rects)
        lo_x, hi_x = world_bounds([raw[m["body"]["object"]], raw[m["bow"]["object"]]])
        lo_xb, hi_xb = world_bounds([raw[m["base"]["object"]]])
        export_frame = {"face_mean_normal": facing(raw[m["body"]["object"]], raw_parts.get(face_part, [])),
                        "bow_centroid_m": centroid(raw[m["bow"]["object"]]),
                        "skeletal_bounds_cm": {"min": [r(c * 100, 3) for c in lo_x], "max": [r(c * 100, 3) for c in hi_x]},
                        "base_bounds_cm": {"min": [r(c * 100, 3) for c in lo_xb], "max": [r(c * 100, 3) for c in hi_xb]}}
        inverse = rot.inverted()
        to_authored_frame(rt, inverse)
        to_authored_frame(rt_base_scene, inverse)
        rt_sk, rt_sk_meshes = roundtrip_measure(rt, profile, atlas, rects, bone_names)
        rt_base, rt_base_meshes = roundtrip_measure(rt_base_scene, profile, atlas, rects, bone_names)
        rt_body = rt_sk_meshes.get(m["body"]["object"])
        rt_bow = rt_sk_meshes.get(m["bow"]["object"])
        rt_base_obj = rt_base_meshes.get(m["base"]["object"])
        if not (rt_body and rt_bow and rt_base_obj):
            raise RuntimeError("round trip lost meshes: %s / %s" % (sorted(rt_sk_meshes), sorted(rt_base_meshes)))
        rt_parts, rt_unassigned = polygons_by_part(rt_body.data, rects)
        rt_labelled = [(rt_body, rt_parts), (rt_bow, {m["bow"]["part"]: [p.index for p in rt_bow.data.polygons]}),
                       (rt_base_obj, {m["base"]["part"]: [p.index for p in rt_base_obj.data.polygons]})]
        orient_rt = orientation_scores(rt_labelled)
        rt_lo_sk, rt_hi_sk = world_bounds([rt_body, rt_bow])
        rt_lo_base, rt_hi_base = world_bounds([rt_base_obj])

        # ---- reference (read only)
        reference = None
        ref_cfg = profile.get("reference") or {}
        ref_path = repo / ref_cfg["skeletal_fbx"] if ref_cfg.get("skeletal_fbx") else None
        if ref_path and ref_path.is_file():
            ref_hash = sha256(ref_path)
            ref_scene = bpy.data.scenes.new(REFERENCE_SCENE)
            import_fbx_into(ref_scene, ref_path)
            ref_meshes = {re.sub(r"\.\d{3}$", "", o.name): o for o in ref_scene.objects if o.type == "MESH"}
            ref_arm = next((o for o in ref_scene.objects if o.type == "ARMATURE"), None)
            part_of_poly = {i: p for p, idx in rt_parts.items() for i in idx}
            reference = {"skeletal_fbx": ref_cfg["skeletal_fbx"], "sha256": ref_hash,
                         "sha256_matches_profile": ref_hash == ref_cfg.get("skeletal_fbx_sha256"),
                         "body": compare_meshes(rt_body, ref_meshes[m["body"]["object"]], part_of_poly),
                         "bow": compare_meshes(rt_bow, ref_meshes[m["bow"]["object"]],
                                               {p.index: m["bow"]["part"] for p in rt_bow.data.polygons})}
            if ref_arm:
                arm_rt = next(o for o in rt.objects if o.type == "ARMATURE")
                diffs = []
                for b in arm_rt.data.bones:
                    rb = ref_arm.data.bones.get(b.name)
                    if rb is None:
                        diffs.append(b.name + ": missing in reference")
                        continue
                    for tag, va, vb in (("head", arm_rt.matrix_world @ b.head_local, ref_arm.matrix_world @ rb.head_local),
                                        ("tail", arm_rt.matrix_world @ b.tail_local, ref_arm.matrix_world @ rb.tail_local)):
                        if (va - vb).length > 1e-5:
                            diffs.append("%s %s differs by %.6f m" % (b.name, tag, (va - vb).length))
                reference["bones_identical"] = not diffs and len(arm_rt.data.bones) == len(ref_arm.data.bones)
                reference["bone_differences"] = diffs
            base_ref = repo / ref_cfg["base_fbx"] if ref_cfg.get("base_fbx") else None
            if base_ref and base_ref.is_file():
                bref_scene = bpy.data.scenes.new(REFERENCE_SCENE + "_base")
                import_fbx_into(bref_scene, base_ref)
                bref = next(o for o in bref_scene.objects if o.type == "MESH")
                reference["base_fbx"] = ref_cfg["base_fbx"]
                reference["base_sha256"] = sha256(base_ref)
                reference["base"] = compare_meshes(rt_base_obj, bref, {p.index: m["base"]["part"]
                                                                      for p in rt_base_obj.data.polygons})
    finally:
        if restore is not None:
            restore()
        if isolation == "live":
            removed = remove_new_ids(before_ids)

    # ---------------------------------------------------------------- checks
    exp = profile["expectations"]
    tris = {n: pre[n]["triangles"] for n in pre}
    check("triangles_as_profile", tris == exp["triangles"], tris, exp["triangles"])
    check("face_slot_polygons", len(body_parts.get(face_part, [])) == exp["face_slot_polygons"],
          len(body_parts.get(face_part, [])), exp["face_slot_polygons"])
    check("neck_polygons", len(body_parts.get("tripo_part_14", [])) == exp["neck_polygons"],
          len(body_parts.get("tripo_part_14", [])), exp["neck_polygons"])
    check("every_body_polygon_in_one_atlas_cell", unassigned == 0 and rt_unassigned == 0,
          {"build": unassigned, "roundtrip": rt_unassigned})
    uv_outside = sum(s["loops_outside_cell_inner_rect"] for s in uv_stats.values())
    check("uv0_single_layer_on_every_mesh", all(pre[n]["uv_layers"] == ["UVMap"] for n in pre),
          {n: pre[n]["uv_layers"] for n in pre})
    check("uv0_inside_unit_square", all(pre[n]["uv0_in_unit_square"] for n in pre),
          {n: pre[n]["uv0_in_unit_square"] for n in pre})
    check("uv0_inside_own_atlas_cell", uv_outside == 0, uv_outside,
          note="every UV corner lies in its part's inner cell rect (gutter kept)")
    overlap = {p: s["overlap_ratio"] for p, s in sorted(uv_stats.items())}
    check("uv0_raster_overlap_measured", True, overlap,
          note="informational: texels covered by >= 2 triangles / covered texels, per part at atlas resolution")
    check("weights_every_vertex_weighted", weights["body"]["unweighted_vertices"] == 0 and
          weights["bow"]["unweighted_vertices"] == 0,
          {"body": weights["body"]["unweighted_vertices"], "bow": weights["bow"]["unweighted_vertices"]})
    check("weights_max_influences", max(weights["body"]["max_influences"], weights["bow"]["max_influences"])
          <= profile["armature"]["max_influences"],
          max(weights["body"]["max_influences"], weights["bow"]["max_influences"]), profile["armature"]["max_influences"])
    check("bow_bound_only_to_weapon", list(weights["bow"]["bones_used"]) == [m["bow"]["bone"]],
          weights["bow"]["bones_used"])
    height = hi_all[2] - lo_all[2]
    check("height_m", abs(height - profile["scale"]["figure_height_m"]) < 1e-5 and abs(lo_all[2]) < 1e-6
          and abs(hi_sk[2] - profile["scale"]["figure_height_m"]) < 1e-5,
          {"figure_with_base": r(height, 6), "skeletal_top": r(hi_sk[2], 6), "lowest": r(lo_all[2], 6)},
          profile["scale"]["figure_height_m"])
    fx, fy, fz = m["base"]["footprint_m"]
    base_dims = [r(hi_base[i] - lo_base[i], 6) for i in range(3)]
    check("base_footprint_and_pivot", all(abs(a - b) < 1e-6 for a, b in zip(base_dims, (fx, fy, fz)))
          and all(abs(lo_base[i] + hi_base[i]) < 1e-6 for i in range(2)) and abs(lo_base[2]) < 1e-6,
          {"dimensions_m": base_dims, "centre_xy_m": [r((lo_base[i] + hi_base[i]) / 2, 6) for i in range(2)],
           "bottom_z_m": r(lo_base[2], 6)}, {"dimensions_m": [fx, fy, fz], "centre_xy_m": [0, 0], "bottom_z_m": 0})
    check("pivot_root_at_origin", pivot["root_head_m"] == [0.0, 0.0, 0.0] and
          pivot["armature_object_location"] == [0.0, 0.0, 0.0], pivot)
    check("axes_face_points_minus_y", axes["face_mean_normal"] is not None and axes["face_mean_normal"][1] < -0.3,
          axes["face_mean_normal"], "-Y (Blender front)")
    check("axes_bow_on_plus_x", axes["bow_centroid_m"][0] > 0, axes["bow_centroid_m"], "+X (Blender, bow side)")
    # export frame as written into the FBX (UM_FBX_v1 rotation); ART-001 maps it onto UE as (x, -y, z)
    front_name, bow_name = axis_name(front_export), axis_name(bow_export)
    face_along, face_cross = along(export_frame["face_mean_normal"] or (0, 0, 0), front_export)
    check("export_frame_face_points_along_rotated_front", face_along > 0.3 and face_cross < face_along,
          {"face_mean_normal": export_frame["face_mean_normal"], "along_front": face_along,
           "largest_horizontal_cross": face_cross}, "%s (authored -Y rotated by %s deg about Z)"
          % (front_name, preset["export_space_rotation_z_degrees"]),
          "area-weighted mean normal of the face part in the re-imported FBX, before undoing the rotation")
    bow_along, _ = along(export_frame["bow_centroid_m"], bow_export)
    check("export_frame_bow_on_rotated_side", bow_along > 0, export_frame["bow_centroid_m"],
          "%s (authored +X rotated)" % bow_name)
    all_tris = {n: [pre[n]["polygons"], pre[n]["triangles"]] for n in pre}
    rt_all = dict(rt_sk["meshes"], **rt_base["meshes"])
    check("triangulate_changes_no_geometry", all(p == t for p, t in all_tris.values()) and
          all(e["polygons"] == e["triangles"] for e in rt_all.values()),
          {"pre_export_polygons_triangles": all_tris,
           "roundtrip_polygons_triangles": {n: [e["polygons"], e["triangles"]] for n, e in sorted(rt_all.items())}},
          note="preset use_triangles=%s; the meshes are already all triangles, so Triangulate is a no-op"
               % preset["use_triangles"])
    # round trip
    check("roundtrip_one_armature", rt_sk["armatures"] == 1 and rt_base["armatures"] == 0,
          {"skeletal_fbx": rt_sk["armatures"], "base_fbx": rt_base["armatures"]})
    rt_bones = rt_sk["bones"]
    check("roundtrip_bones", sorted(rt_bones) == sorted(bone_names) and len(rt_bones) == exp["bones"],
          len(rt_bones), exp["bones"])
    parents_ok = all(rt_bones.get(n, {}).get("parent") == p for n, p, _h, _t in profile["armature"]["bones"])
    heads_ok = all(rt_bones.get(n) and all(abs(a - b) < 1e-4 for a, b in zip(rt_bones[n]["head_m"], h))
                   for n, _p, h, _t in profile["armature"]["bones"])
    check("roundtrip_bone_hierarchy_and_rest_positions", parents_ok and heads_ok,
          {"parents_ok": parents_ok, "heads_within_1e-4_m": heads_ok})
    rt_tris = {n: e["triangles"] for n, e in rt_sk["meshes"].items()}
    rt_tris.update({n: e["triangles"] for n, e in rt_base["meshes"].items()})
    check("roundtrip_triangles_preserved", rt_tris == tris, rt_tris, tris)
    rt_slots = {n: e["material_slots"] for n, e in rt_sk["meshes"].items()}
    rt_slots.update({n: e["material_slots"] for n, e in rt_base["meshes"].items()})
    sk_unique = sorted({s for n in (m["body"]["object"], m["bow"]["object"]) for s in rt_slots.get(n, []) if s})
    check("roundtrip_material_slots", len(sk_unique) == exp["skeletal_material_slots"] and
          len(rt_slots.get(m["base"]["object"], [])) == exp["base_material_slots"],
          {"per_mesh": rt_slots, "skeletal_unique": sk_unique},
          {"skeletal_unique": exp["skeletal_material_slots"], "base": exp["base_material_slots"]})
    check("roundtrip_uv0", all(e["uv_layers"] == ["UVMap"] and e["uv0_in_unit_square"]
                               for e in list(rt_sk["meshes"].values()) + list(rt_base["meshes"].values())),
          {n: e["uv_layers"] for n, e in list(rt_sk["meshes"].items()) + list(rt_base["meshes"].items())})
    rt_w = {n: e["weights"] for n, e in rt_sk["meshes"].items()}
    check("roundtrip_weights", rt_w[m["body"]["object"]]["unweighted_vertices"] == 0 and
          list(rt_w[m["bow"]["object"]]["bones_used"]) == [m["bow"]["bone"]] and
          max(w["max_influences"] for w in rt_w.values()) <= profile["armature"]["max_influences"],
          {n: {k: w[k] for k in ("max_influences", "unweighted_vertices")} for n, w in rt_w.items()})
    rt_bad = sorted(p for p, s in orient_rt.items() if s["score"] is None or s["score"] < ocfg["min_score_after_fix"])
    check("roundtrip_orientation_all_parts_outward", not rt_bad,
          {p: s["score"] for p, s in sorted(orient_rt.items())}, ">= %s" % ocfg["min_score_after_fix"])
    ratio = [r((rt_hi_sk[i] - rt_lo_sk[i]) / (hi_sk[i] - lo_sk[i]), 6) for i in range(3)]
    check("roundtrip_scale_ratio_1", all(abs(v - 1) < 1e-4 for v in ratio), ratio,
          note="Blender re-reads the cm FBX (UnitScaleFactor 1.0) as metres")
    check("roundtrip_part_polygon_counts", len(rt_parts.get(face_part, [])) == exp["face_slot_polygons"] and
          len(rt_parts.get("tripo_part_14", [])) == exp["neck_polygons"],
          {p: len(v) for p, v in sorted(rt_parts.items())})
    if reference:
        body_cmp = reference["body"]
        flipped_parts = sorted(p for p, n in body_cmp["flipped_winding_by_part"].items() if n)
        expected_flip = sorted(set(inside_out) - {"tripo_part_10", "tripo_part_14"})
        full_flip = all(body_cmp["flipped_winding_by_part"].get(p, 0) == len(rt_parts.get(p, []))
                        for p in expected_flip)
        check("reference_v2_same_geometry_uv_material",
              body_cmp["unmatched_candidate_polygons"] == 0 and body_cmp["unmatched_reference_polygons"] == 0 and
              reference["bow"]["unmatched_candidate_polygons"] == 0 and reference["bones_identical"],
              {"body_unmatched": [body_cmp["unmatched_candidate_polygons"], body_cmp["unmatched_reference_polygons"]],
               "bow_unmatched": [reference["bow"]["unmatched_candidate_polygons"],
                                 reference["bow"]["unmatched_reference_polygons"]],
               "bones_identical": reference.get("bones_identical")},
              note="read-only comparison with %s" % reference["skeletal_fbx"])
        check("reference_v2_winding_differs_only_in_new_fixes", flipped_parts == expected_flip and full_flip,
              {"flipped_vs_reference": flipped_parts,
               "counts": {p: body_cmp["flipped_winding_by_part"].get(p, 0) for p in flipped_parts}},
              expected_flip, "v2 fixed part_10/part_14 only; any other inside-out part is expected to differ fully")
        if "base" in reference:
            check("reference_base_same_geometry", reference["base"]["unmatched_candidate_polygons"] == 0 and
                  reference["base"]["unmatched_reference_polygons"] == 0,
                  [reference["base"]["unmatched_candidate_polygons"], reference["base"]["unmatched_reference_polygons"]])
        corner_other = {k: reference[k]["corner_normals_other_by_part"] for k in ("body", "bow", "base") if k in reference}
        other_detail = {k: reference[k]["corner_normals_other_detail"] for k in corner_other}
        other_total = sum(v for d in corner_other.values() for v in d.values())
        slivers_only = all(e["touches_near_degenerate"] for d in other_detail.values() for e in d) and \
            other_total == sum(len(d) for d in other_detail.values())
        negated = sorted(p for p, n in body_cmp["corner_normals_negated_by_part"].items() if n)
        check("reference_corner_normals_rotated_consistently", slivers_only and negated == expected_flip,
              {"other_by_mesh": corner_other, "other_detail": other_detail, "negated_parts": negated},
              {"other": "only at vertices of near-degenerate triangles (< %s cm2)" % DEGENERATE_AREA_CM2,
               "negated_parts": expected_flip},
              "corner normals equal the unrotated reference (|dot| > 0.999) after undoing the export rotation, "
              "negated only on the parts whose winding this candidate fixes. Exception, reported per corner: the face "
              "normal of a sliver triangle is numerically undefined: the export rotation (even an exact axis permutation "
              "changes the float summation order) changes it and shifts the exported normals of the corners that "
              "share its vertices (measured: not caused by Triangulate)")

    report = {
        "stage": "build",
        "blender": bpy.app.version_string,
        "profile": {"id": profile["profile_id"], "status": profile["status"]},
        "source": {"file": source.name, "sha256": source_hash},
        "isolation_note": "live: temporary scenes, all created datablocks removed" if isolation == "live" else "process",
        "scale": scale_info,
        "source_part_polygons": source_polys,
        "body_parts": body_part_names,
        "body_part_vertex_counts": part_vertex_counts,
        "orientation": {"method": ocfg["method"], "before_fix": orient_before, "flipped_parts": inside_out,
                        "flipped_polygons": len(selected), "after_fix": orient_after, "roundtrip": orient_rt},
        "materials": {"atlas": profile["materials"]["atlas"], "face_slot": face_cfg, "blender_images": mat_images},
        "meshes_pre_export_m": pre,
        "weights": weights,
        "uv": uv_stats,
        "bounds_m": {"skeletal": {"min": [r(c) for c in lo_sk], "max": [r(c) for c in hi_sk]},
                     "base": {"min": [r(c) for c in lo_base], "max": [r(c) for c in hi_base]},
                     "figure_with_base_height": r(height)},
        "expected_ue_bounds_uu_at_import_scale_1": {
            "skeletal_blender_axes": {"min": [r(c * 100, 3) for c in lo_sk], "max": [r(c * 100, 3) for c in hi_sk]},
            "base_blender_axes": {"min": [r(c * 100, 3) for c in lo_base], "max": [r(c * 100, 3) for c in hi_base]},
            "export_rotation_z_degrees": float(preset["export_space_rotation_z_degrees"]),
            "skeletal_export_frame": export_frame["skeletal_bounds_cm"],
            "base_export_frame": export_frame["base_bounds_cm"],
            "skeletal_ue_predicted": ue_predicted(export_frame["skeletal_bounds_cm"]),
            "base_ue_predicted": ue_predicted(export_frame["base_bounds_cm"]),
            "note": "*_blender_axes: authored Blender frame (front -Y), centimetres; *_export_frame: as written "
                    "into the FBX (re-imported); *_ue_predicted: export frame mapped as UE (x, -y, z) per ART-001. "
                    "ue-import measures the real mapping"},
        "axes": dict(axes, export_frame={"face_mean_normal": export_frame["face_mean_normal"],
                                         "bow_centroid_m": export_frame["bow_centroid_m"],
                                         "front_axis": front_name, "bow_side_axis": bow_name}),
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
        "reference_comparison": reference,
        "checks": checks,
        "passed": all(c["passed"] for c in checks.values()),
        "status": "technically_exported_not_art_accepted",
        "not_checked": [
            "art acceptance, silhouette, lighting, K1/K2/K3 (art track)",
            "deformation quality in animation; clips are not built by this stage",
            "budgets: numbers are measured only (proposals until GD-058)",
            "UV intra-part island padding (Tripo's own layout inside each cell)",
            "collision capsule (04 §3.1 UCP_ proposal)",
            "UE-side facing: measured by ue-import (bounds axis map) and editor frames, not here",
        ],
    }
    collisions = namer.report()
    if collisions:
        report["live_name_collisions"] = collisions
    out = Path(params["report_out"])
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    if sha256(source) != source_hash:
        raise RuntimeError("source GLB changed during build")
    if not report["passed"]:
        raise RuntimeError("build checks failed: %s" % sorted(k for k, c in checks.items() if not c["passed"]))
    print(MARKER, "isolation=%s" % isolation, "temp_ids_removed=%d" % removed,
          "sk=%s" % report["exports"]["skeletal"]["sha256"][:12], "base=%s" % report["exports"]["base"]["sha256"][:12])


main()
