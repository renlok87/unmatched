"""Part preparation of the seated flow (and shared bits of the whole-figure flow): bake the glTF parts, keep
the imported corner normals through topology edits, weld inside a part, islands, atlas material and UVs,
part labels, join. Moved unchanged from the per-hero builders of 2026-09-28 (Arthur, Merlin, Harpy)."""

from collections import defaultdict
from pathlib import Path

import bmesh
import bpy
import numpy as np
from mathutils import Vector

from .core import CN_ATTR, PART_ATTR, r, scene_context


def bake_parts(scene, namer=None):
    """Mesh parts of the imported glTF by (canonical) name; part transforms baked into the mesh data,
    helper empties removed."""
    parts = {}
    for obj in list(scene.objects):
        if obj.type == "MESH":
            parts[namer(obj, "objects") if namer else obj.name] = obj
    for obj in parts.values():
        world = obj.matrix_world.copy()
        obj.parent = None
        obj.data.transform(world)
        obj.matrix_world.identity()
    for obj in [o for o in scene.objects if o.type != "MESH"]:
        bpy.data.objects.remove(obj)  # glTF helper empties; parts are already baked to world
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
    is the zero vector (Tripo writes one on zero-area collinear triangles) carry no direction to preserve:
    they are excluded and counted."""
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


def material_pixels(mat, label):
    """RGBA float pixels (rows bottom-up, Blender order) of the image node `label` of an atlas material."""
    image = next(n.image for n in mat.node_tree.nodes if n.type == "TEX_IMAGE" and n.label == label)
    return np.array(image.pixels[:], dtype=np.float32).reshape(image.size[1], image.size[0], 4), image.size[0]


def remap_uvs(obj, cell, size):
    x, y, width, inset = cell["x"], cell["y_top"], cell["cell"], cell["inset"]
    inner = width - 2 * inset
    for uv_data in obj.data.uv_layers.active.data:
        uv = uv_data.uv.copy()
        uv_data.uv = ((x + inset + uv.x * inner) / size, 1 - (y + inset + (1 - uv.y) * inner) / size)


def part_number(part_name):
    return int(part_name.split("_")[-1])


def label_faces(obj, part_name):
    attr = obj.data.attributes.get(PART_ATTR) or obj.data.attributes.new(PART_ATTR, "INT", "FACE")
    attr.data.foreach_set("value", [part_number(part_name)] * len(obj.data.polygons))


def read_face_labels(obj):
    vals = [0] * len(obj.data.polygons)
    obj.data.attributes[PART_ATTR].data.foreach_get("value", vals)
    out = defaultdict(list)
    for i, v in enumerate(vals):
        out["tripo_part_%d" % v].append(i)
    return dict(out)


def remove_attribute(obj, name):
    if name in obj.data.attributes:
        obj.data.attributes.remove(obj.data.attributes[name])


def join_objects(scene, objects, active):
    with scene_context(scene):
        bpy.ops.object.select_all(action="DESELECT")
        for obj in objects:
            obj.select_set(True)
        bpy.context.view_layer.objects.active = active
        bpy.ops.object.join()
    return active


def dist_to_line(p, c, d):
    v = Vector(p) - c
    return (v - d * v.dot(d)).length


def fit_axis(points):
    pts = np.array(points, dtype=np.float64)
    c = pts.mean(axis=0)
    _u, _s, vt = np.linalg.svd(pts - c)
    d = vt[0]
    if d[2] < 0:
        d = -d
    return Vector(c), Vector(d).normalized()
