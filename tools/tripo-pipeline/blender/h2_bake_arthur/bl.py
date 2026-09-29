"""Blender helpers of the H2 bake (headless only; imported by the Blender stages)."""

import math
import sys
from pathlib import Path

import bpy
import numpy as np
from mathutils import Matrix, Vector
from mathutils.bvhtree import BVHTree

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))
BLENDER_TOOLS = HERE.parent
if str(BLENDER_TOOLS) not in sys.path:
    sys.path.insert(0, str(BLENDER_TOOLS))

import pure as P  # noqa: E402


def require_background(name):
    if not bpy.app.background:
        # RuntimeError, not SystemExit: SystemExit would terminate a live Blender session (:9876/:9877).
        raise RuntimeError("%s: headless only (blender -b --factory-startup)" % name)


def script_args():
    argv = sys.argv
    return argv[argv.index("--") + 1:] if "--" in argv else []


def part_key(name):
    """tripo_part_12 -> 12 (sort key); other names sort last."""
    try:
        return int(name.rsplit("_", 1)[1])
    except (IndexError, ValueError):
        return 10 ** 6


def import_glb_parts(path, collection_name):
    """Import a Tripo GLB into a new collection of the current scene; returns {part name: object} (node names).
    The ROOT empty is removed after its children are unparented with their world transform kept."""
    before = set(bpy.data.objects)
    bpy.ops.import_scene.gltf(filepath=str(path))
    new = [o for o in bpy.data.objects if o not in before]
    coll = bpy.data.collections.new(collection_name)
    bpy.context.scene.collection.children.link(coll)
    parts = {}
    for obj in new:
        for c in list(obj.users_collection):
            c.objects.unlink(obj)
        coll.objects.link(obj)
    for obj in new:
        if obj.type == "MESH":
            mw = obj.matrix_world.copy()
            obj.parent = None
            obj.matrix_world = mw
    for obj in new:
        if obj.type != "MESH":
            bpy.data.objects.remove(obj)
    for obj in [o for o in coll.objects if o.type == "MESH"]:
        parts[obj.name.split(".")[0]] = obj
    return dict(sorted(parts.items(), key=lambda kv: part_key(kv[0]))), coll


def mesh_arrays(obj, world=True):
    """(verts Nx3 float64, tris Mx3 int, tri polygon index M) of the evaluated-free mesh data."""
    me = obj.data
    me.calc_loop_triangles()
    n = len(me.vertices)
    co = np.empty(n * 3, dtype=np.float64)
    me.vertices.foreach_get("co", co)
    co = co.reshape(-1, 3)
    if world and not obj.matrix_world == Matrix.Identity(4):
        m = np.array(obj.matrix_world)
        co = co @ m[:3, :3].T + m[:3, 3]
    t = len(me.loop_triangles)
    tris = np.empty(t * 3, dtype=np.int64)
    me.loop_triangles.foreach_get("vertices", tris)
    poly = np.empty(t, dtype=np.int64)
    me.loop_triangles.foreach_get("polygon_index", poly)
    return co, tris.reshape(-1, 3), poly


def tri_geometry(co, tris):
    a, b, c = co[tris[:, 0]], co[tris[:, 1]], co[tris[:, 2]]
    cross = np.cross(b - a, c - a)
    area2 = np.linalg.norm(cross, axis=1)
    normal = cross / np.maximum(area2, 1e-30)[:, None]
    centre = (a + b + c) / 3.0
    return centre, normal, area2 * 0.5


def bvh_from_arrays(co, tris):
    return BVHTree.FromPolygons([tuple(v) for v in co], [tuple(int(i) for i in t) for t in tris], all_triangles=True)


def ray_escape_scores(parts_arrays, sample_per_part=6000, height=None):
    """Ray-escape orientation per part: for sampled triangles a ray along +normal and one along -normal against the
    whole figure. Area where only +normal escapes counts outward, only -normal escapes inward.
    score = (out - in) / (out + in). parts_arrays: {part: (co, tris)} in world metres."""
    all_co, all_tris, offset = [], [], 0
    for co, tris in parts_arrays.values():
        all_co.append(co)
        all_tris.append(tris + offset)
        offset += len(co)
    co_all = np.concatenate(all_co)
    tris_all = np.concatenate(all_tris)
    if height is None:
        height = float(co_all[:, 2].max() - co_all[:, 2].min())
    bvh = bvh_from_arrays(co_all, tris_all)
    eps, dist = 1e-4 * height, 2.0 * height
    out = {}
    for part, (co, tris) in parts_arrays.items():
        centre, normal, area = tri_geometry(co, tris)
        step = max(1, len(tris) // sample_per_part)
        idx = np.arange(0, len(tris), step)
        o = i = amb = 0.0
        for k in idx:
            c = Vector(centre[k])
            n = Vector(normal[k])
            plus = bvh.ray_cast(c + n * eps, n, dist)[0] is None
            minus = bvh.ray_cast(c - n * eps, -n, dist)[0] is None
            a = float(area[k])
            if plus and not minus:
                o += a
            elif minus and not plus:
                i += a
            else:
                amb += a
        tot = o + i
        out[part] = {"score": round((o - i) / tot, 4) if tot > 0 else None,
                     "sampled_triangles": int(len(idx)),
                     "escape_out_area_share": round(o / max(o + i + amb, 1e-30), 4),
                     "escape_in_area_share": round(i / max(o + i + amb, 1e-30), 4),
                     "ambiguous_area_share": round(amb / max(o + i + amb, 1e-30), 4)}
    return out


def opposed_corner_normal_share(obj):
    """Area share of polygons whose mean imported corner normal points against the winding normal."""
    me = obj.data
    npoly = len(me.polygons)
    if npoly == 0:
        return None
    pn = np.empty(npoly * 3)
    me.polygons.foreach_get("normal", pn)
    pn = pn.reshape(-1, 3)
    area = np.empty(npoly)
    me.polygons.foreach_get("area", area)
    nl = len(me.loops)
    cn = np.empty(nl * 3)
    me.corner_normals.foreach_get("vector", cn)
    cn = cn.reshape(-1, 3)
    start = np.empty(npoly, dtype=np.int64)
    me.polygons.foreach_get("loop_start", start)
    total = np.empty(npoly, dtype=np.int64)
    me.polygons.foreach_get("loop_total", total)
    loop_poly = np.repeat(np.arange(npoly), total)
    mean = np.zeros((npoly, 3))
    np.add.at(mean, loop_poly, cn)
    dots = np.einsum("ij,ij->i", mean, pn)
    return round(float(area[dots < 0].sum() / max(area.sum(), 1e-30)), 6)


def edge_topology(obj):
    """Boundary and non-manifold edge counts after an in-memory 1e-7 weld (bmesh copy; the object is unchanged)."""
    import bmesh
    bm = bmesh.new()
    bm.from_mesh(obj.data)
    bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=1e-7)
    boundary = sum(1 for e in bm.edges if len(e.link_faces) == 1)
    nonman = sum(1 for e in bm.edges if len(e.link_faces) > 2)
    wire = sum(1 for e in bm.edges if len(e.link_faces) == 0)
    # shells
    seen = set()
    shells = []
    faces = list(bm.faces)
    for f in faces:
        if f.index in seen:
            continue
        stack = [f]
        seen.add(f.index)
        count = 0
        while stack:
            g = stack.pop()
            count += 1
            for e in g.edges:
                for h in e.link_faces:
                    if h.index not in seen:
                        seen.add(h.index)
                        stack.append(h)
        shells.append(count)
    welded_verts = len(bm.verts)
    bm.free()
    shells.sort(reverse=True)
    return {"welded_vertices": welded_verts, "boundary_edges": boundary, "non_manifold_edges": nonman,
            "wire_edges": wire, "shells": len(shells), "largest_shells_faces": shells[:5]}


# ----------------------------------------------------------------------------------------------- rendering helpers

def look_at(cam, target, direction, distance):
    d = Vector(direction).normalized()
    cam.location = Vector(target) + d * distance
    cam.rotation_euler = (-d).to_track_quat("-Z", "Y").to_euler()


def new_camera(scene, name="h2_cam"):
    cam = bpy.data.objects.new(name, bpy.data.cameras.new(name))
    scene.collection.objects.link(cam)
    scene.camera = cam
    cam.data.clip_start, cam.data.clip_end = 0.002, 100.0
    return cam


def game_dir(azimuth_deg, pitch_deg=-55.0):
    """Direction from target to camera: azimuth 0 = in front of the figure (-Y), + = figure's left (+X)."""
    el = math.radians(-pitch_deg)
    az = math.radians(azimuth_deg)
    return (math.sin(az) * math.cos(el), -math.cos(az) * math.cos(el), math.sin(el))


# ----------------------------------------------------------------------------------------------- FBX header pin

class fbx_native_file:
    """Context manager: the Blender FBX exporter writes bpy.data.filepath (the absolute path of the open .blend,
    i.e. the user's profile path) into FBXHeaderExtension/SceneInfo "Original|ApplicationNativeFile". Inside the
    block that one property gets `value` instead (a run-dir-relative path), so the FBX bytes do not depend on the
    checkout location and carry no local path. Wraps export_fbx_bin.elem_props_compound; restored on exit."""

    def __init__(self, value):
        self.value = value
        self.hits = 0

    def __enter__(self):
        from io_scene_fbx import export_fbx_bin as efb
        self._efb, self._orig = efb, efb.elem_props_compound
        outer = self

        def compound(elem, cmpd_name, custom=False):
            setter = outer._orig(elem, cmpd_name, custom=custom)

            def _setter(ptype, name, value, *args, **kwargs):
                if name == b"ApplicationNativeFile":
                    outer.hits += 1
                    value = outer.value
                return setter(ptype, name, value, *args, **kwargs)
            return _setter
        efb.elem_props_compound = compound
        return self

    def __exit__(self, *exc):
        self._efb.elem_props_compound = self._orig
        return False
