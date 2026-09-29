"""bpy helpers shared by the H2 bake stages (headless only)."""

import json
import math
import random
import re
from pathlib import Path

import bmesh
import bpy
import numpy as np
from mathutils import Matrix, Vector
from mathutils.bvhtree import BVHTree


def require_background():
    if not bpy.app.background:
        # RuntimeError, not SystemExit: SystemExit would kill a live Blender (MCP add-on catches Exception only)
        raise RuntimeError("h2_bake: headless only (blender -b --factory-startup)")


def reset():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    scene = bpy.context.scene
    scene.unit_settings.system = "METRIC"
    scene.unit_settings.scale_length = 1.0
    return scene


def r(v, nd=6):
    return round(float(v), nd)


def rv(vec, nd=6):
    return [r(c, nd) for c in vec]


def write_json(path, data):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, sort_keys=True, ensure_ascii=False) + "\n", encoding="utf-8")


def part_key(name):
    m = re.search(r"tripo_part_(\d+)", name)
    return int(m.group(1)) if m else 10 ** 6


def import_glb_parts(path, prefix):
    """Import a Tripo GLB into the current scene, bake node transforms into the meshes, drop helper empties,
    rename objects/meshes to <prefix><tripo_part_N>. Returns {part: object} sorted by part number."""
    before = set(bpy.data.objects)
    bpy.ops.import_scene.gltf(filepath=str(path))
    new = [o for o in bpy.data.objects if o not in before]
    parts = {}
    for obj in new:
        if obj.type != "MESH":
            continue
        m = re.match(r"^(tripo_part_\d+)", obj.name)
        if not m:
            raise RuntimeError("unexpected mesh node %s in %s" % (obj.name, path))
        parts[m.group(1)] = obj
    for obj in parts.values():
        world = obj.matrix_world.copy()
        obj.parent = None
        obj.data.transform(world)
        obj.matrix_world = Matrix.Identity(4)
    for obj in new:
        if obj.type != "MESH":
            bpy.data.objects.remove(obj)
    out = {}
    for name in sorted(parts, key=part_key):
        obj = parts[name]
        obj.name = prefix + name
        obj.data.name = prefix + name
        out[name] = obj
    return out


def coords(mesh):
    a = np.empty(len(mesh.vertices) * 3, np.float64)
    mesh.vertices.foreach_get("co", a)
    return a.reshape(-1, 3)


def set_coords(mesh, arr):
    mesh.vertices.foreach_set("co", np.ascontiguousarray(arr, dtype=np.float32).ravel())
    mesh.update()


def triangles(mesh):
    return sum(len(p.vertices) - 2 for p in mesh.polygons)


def mesh_area(mesh):
    a = np.empty(len(mesh.polygons), np.float64)
    mesh.polygons.foreach_get("area", a)
    return float(a.sum())


def bounds(objs):
    pts = np.vstack([coords(o.data) for o in objs])
    return pts.min(0), pts.max(0)


def bvh_of(objects):
    verts, polys, owner = [], [], []
    for name, obj in objects:
        off = len(verts)
        verts.extend(Vector(c) for c in coords(obj.data))
        for p in obj.data.polygons:
            polys.append([off + i for i in p.vertices])
            owner.append(name)
    return BVHTree.FromPolygons(verts, polys, all_triangles=False), owner


def orientation_scores(objects, samples, seed=0, eps_rel=1e-4, height=1.0):
    """Ray-escape per polygon (profile orientation.method): a ray along +normal and one along -normal against the
    whole figure; area where only the +normal ray escapes counts outward, only the -normal ray escapes counts
    inward; score = (out - in) / (out + in). Sampled polygons (seeded) per part."""
    bvh, _owner = bvh_of(objects)
    rng = random.Random(seed)
    eps = eps_rel * height
    out = {}
    for name, obj in objects:
        polys = obj.data.polygons
        idx = list(range(len(polys)))
        if len(idx) > samples:
            idx = sorted(rng.sample(idx, samples))
        o_area = i_area = 0.0
        for i in idx:
            p = polys[i]
            c = p.center
            n = p.normal
            if n.length < 0.5:
                continue
            hit_out = bvh.ray_cast(c + n * eps, n)[0] is not None
            hit_in = bvh.ray_cast(c - n * eps, -n)[0] is not None
            if not hit_out and hit_in:
                o_area += p.area
            elif hit_out and not hit_in:
                i_area += p.area
        tot = o_area + i_area
        out[name] = {"score": r((o_area - i_area) / tot, 4) if tot > 0 else None,
                     "out_area_m2": r(o_area, 9), "in_area_m2": r(i_area, 9), "sampled_polygons": len(idx)}
    return out


def flip_mesh(mesh):
    bm = bmesh.new()
    bm.from_mesh(mesh)
    for f in bm.faces:
        f.normal_flip()
    bm.to_mesh(mesh)
    bm.free()
    mesh.update()


def setup_cycles(scene, device="GPU", samples=1, seed=0):
    scene.render.engine = "CYCLES"
    used = "CPU"
    if device == "GPU":
        prefs = bpy.context.preferences.addons["cycles"].preferences
        for kind in ("OPTIX", "CUDA"):
            try:
                prefs.compute_device_type = kind
                prefs.get_devices()
            except Exception:  # noqa: BLE001 - backend not compiled in / no driver
                continue
            devs = [d for d in prefs.devices if d.type == kind]
            if devs:
                for d in prefs.devices:
                    d.use = d.type == kind
                used = "GPU:%s:%s" % (kind, ",".join(sorted(d.name for d in devs)))
                break
    scene.cycles.device = "GPU" if used.startswith("GPU") else "CPU"
    scene.cycles.samples = samples
    scene.cycles.seed = seed
    scene.cycles.use_animated_seed = False
    scene.cycles.use_denoising = False
    scene.cycles.use_adaptive_sampling = False
    return used


def image_to_array(img):
    w, h = img.size
    a = np.empty(w * h * 4, np.float32)
    img.pixels.foreach_get(a)
    return a.reshape(h, w, 4)


def array_to_image(img, arr):
    img.pixels.foreach_set(np.ascontiguousarray(arr, dtype=np.float32).ravel())


def uv_triangles(mesh, uv_name=None):
    """(tris_uv [T,3,2], tris_poly [T]) of a triangulated mesh (fan triangulation of n-gons)."""
    uv = mesh.uv_layers[uv_name] if uv_name else mesh.uv_layers.active
    loops_uv = np.empty(len(mesh.loops) * 2, np.float64)
    uv.data.foreach_get("uv", loops_uv)
    loops_uv = loops_uv.reshape(-1, 2)
    tris, owner = [], []
    for p in mesh.polygons:
        li = list(p.loop_indices)
        for k in range(1, len(li) - 1):
            tris.append((li[0], li[k], li[k + 1]))
            owner.append(p.index)
    tris = np.array(tris, np.int64)
    return loops_uv[tris], np.array(owner, np.int64)


def raster_count(tris_px, size, out=None):
    """Coverage count of pixel centres strictly inside each triangle (shared edges are not double counted
    except for centres exactly on an edge): pixels with count > 1 are overlapping UVs."""
    if out is None:
        out = np.zeros((size, size), np.int32)
    for t in range(len(tris_px)):
        a, b, c = tris_px[t]
        x0 = max(int(math.floor(min(a[0], b[0], c[0]))), 0)
        x1 = min(int(math.ceil(max(a[0], b[0], c[0]))), size - 1)
        y0 = max(int(math.floor(min(a[1], b[1], c[1]))), 0)
        y1 = min(int(math.ceil(max(a[1], b[1], c[1]))), size - 1)
        if x1 < x0 or y1 < y0:
            continue
        X, Y = np.meshgrid(np.arange(x0, x1 + 1) + 0.5, np.arange(y0, y1 + 1) + 0.5)
        d = (b[1] - c[1]) * (a[0] - c[0]) + (c[0] - b[0]) * (a[1] - c[1])
        if abs(d) < 1e-12:
            continue
        l1 = ((b[1] - c[1]) * (X - c[0]) + (c[0] - b[0]) * (Y - c[1])) / d
        l2 = ((c[1] - a[1]) * (X - c[0]) + (a[0] - c[0]) * (Y - c[1])) / d
        l3 = 1.0 - l1 - l2
        eps = 1e-7
        out[y0:y1 + 1, x0:x1 + 1] += ((l1 > eps) & (l2 > eps) & (l3 > eps)).astype(np.int32)
    return out


def raster_triangles(tris_px, values, size, out=None, fill=0):
    """Rasterise pixel-space triangles (pixel centres, inclusive edges) writing values[t] (int) into an
    int32 image [size, size] (row 0 = v 0, i.e. bottom-up like Blender images)."""
    if out is None:
        out = np.full((size, size), fill, np.int32)
    for t in range(len(tris_px)):
        a, b, c = tris_px[t]
        x0 = max(int(math.floor(min(a[0], b[0], c[0]))), 0)
        x1 = min(int(math.ceil(max(a[0], b[0], c[0]))), size - 1)
        y0 = max(int(math.floor(min(a[1], b[1], c[1]))), 0)
        y1 = min(int(math.ceil(max(a[1], b[1], c[1]))), size - 1)
        if x1 < x0 or y1 < y0:
            continue
        xs = np.arange(x0, x1 + 1) + 0.5
        ys = np.arange(y0, y1 + 1) + 0.5
        X, Y = np.meshgrid(xs, ys)
        d = (b[1] - c[1]) * (a[0] - c[0]) + (c[0] - b[0]) * (a[1] - c[1])
        if abs(d) < 1e-12:
            continue
        l1 = ((b[1] - c[1]) * (X - c[0]) + (c[0] - b[0]) * (Y - c[1])) / d
        l2 = ((c[1] - a[1]) * (X - c[0]) + (a[0] - c[0]) * (Y - c[1])) / d
        l3 = 1.0 - l1 - l2
        tol = -1e-9
        inside = (l1 >= tol) & (l2 >= tol) & (l3 >= tol)
        sub = out[y0:y1 + 1, x0:x1 + 1]
        sub[inside] = values[t]
    return out
