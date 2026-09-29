"""Blender helpers of the H2 bake (headless only; imported by the Blender stages)."""

import sys
from pathlib import Path

import bmesh
import bpy
import numpy as np
from mathutils.bvhtree import BVHTree

HERE = Path(__file__).resolve().parent
for p in (HERE, HERE.parent):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

import common as C  # noqa: E402


def require_background(name):
    if not bpy.app.background:
        # RuntimeError, not SystemExit: SystemExit would terminate a live Blender session (:9876/:9877).
        raise RuntimeError("%s: headless only (blender -b --factory-startup)" % name)


def script_args():
    argv = sys.argv
    return argv[argv.index("--") + 1:] if "--" in argv else []


def ctx(objs, active=None):
    objs = list(objs) if isinstance(objs, (list, tuple)) else [objs]
    active = active or objs[0]
    return bpy.context.temp_override(object=active, active_object=active, selected_objects=objs,
                                     selected_editable_objects=objs)


def select_only(objs, active=None):
    objs = list(objs) if isinstance(objs, (list, tuple)) else [objs]
    for o in bpy.context.view_layer.objects:
        o.select_set(False)
    for o in objs:
        o.select_set(True)
    bpy.context.view_layer.objects.active = active or objs[0]


def empty_file():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    scene = bpy.context.scene
    scene.unit_settings.system = "METRIC"
    scene.unit_settings.scale_length = 1.0
    return scene


def import_glb(path, prefix):
    """Import a glTF; mesh objects renamed <prefix><node name>, parents cleared keeping the world transform."""
    before = set(bpy.data.objects)
    bpy.ops.import_scene.gltf(filepath=str(path))
    new = [o for o in bpy.data.objects if o not in before]
    meshes = {}
    for o in new:
        if o.type == "MESH":
            name = o.name.split(".")[0]
            mw = o.matrix_world.copy()
            o.parent = None
            o.matrix_world = mw
            o.name = prefix + name
            o.data.name = prefix + name
            meshes[name] = o
    for o in new:
        if o.type != "MESH":
            bpy.data.objects.remove(o)
    return meshes


def apply_transform(o):
    """Bake the object transform into the mesh (identity object matrix afterwards)."""
    o.data.transform(o.matrix_world)
    o.matrix_world.identity()


def verts_np(o):
    me = o.data
    a = np.empty(len(me.vertices) * 3, np.float64)
    me.vertices.foreach_get("co", a)
    a = a.reshape(-1, 3)
    m = np.array(o.matrix_world)
    return a @ m[:3, :3].T + m[:3, 3]


def poly_array(me, name, dtype, width=1):
    a = np.empty(len(me.polygons) * width, dtype)
    me.polygons.foreach_get(name, a)
    return a.reshape(-1, width) if width > 1 else a


def int_face_attr(me, name):
    a = np.empty(len(me.polygons), np.int32)
    me.attributes[name].data.foreach_get("value", a)
    return a


def set_int_face_attr(me, name, values):
    if name not in me.attributes:
        me.attributes.new(name, "INT", "FACE")
    me.attributes[name].data.foreach_set("value", np.asarray(values, np.int32))


def bvh_of(objs):
    bm = bmesh.new()
    for o in objs:
        tmp = o.data.copy()
        tmp.transform(o.matrix_world)
        bm.from_mesh(tmp)
        bpy.data.meshes.remove(tmp)
    tree = BVHTree.FromBMesh(bm)
    bm.free()
    return tree


def area_sample_points(o, n, face_mask=None):
    """Deterministic surface samples: face centres of an area-weighted, evenly strided face selection."""
    me = o.data
    areas = poly_array(me, "area", np.float64)
    centers = poly_array(me, "center", np.float64, 3)
    idx = np.arange(len(areas))
    if face_mask is not None:
        idx = idx[face_mask]
    if len(idx) == 0:
        return np.zeros((0, 3))
    cum = np.cumsum(areas[idx])
    targets = (np.arange(n) + 0.5) / n * cum[-1]
    pick = idx[np.searchsorted(cum, targets)]
    m = np.array(o.matrix_world)
    return centers[pick] @ m[:3, :3].T + m[:3, 3]


def deviation(points, tree):
    """Distances (m) from points to the surface in tree: p50/p95/p99/p99.9/max in mm."""
    if len(points) == 0:
        return None
    d = np.array([tree.find_nearest(p)[3] for p in points], np.float64) * 1000.0
    return {"n": int(len(d)), "p50_mm": C.r(np.percentile(d, 50), 4), "p95_mm": C.r(np.percentile(d, 95), 4),
            "p99_mm": C.r(np.percentile(d, 99), 4), "p999_mm": C.r(np.percentile(d, 99.9), 4),
            "max_mm": C.r(d.max(), 4)}


def setup_cycles(scene, samples, seed=0, prefer="OPTIX", device_mode="GPU"):
    """Cycles on the GPU (OptiX, then CUDA) when available and device_mode == "GPU", else CPU (all threads).
    Returns a description of the device."""
    scene.render.engine = "CYCLES"
    cyc = scene.cycles
    cyc.samples = int(samples)
    cyc.seed = int(seed)
    cyc.use_animated_seed = False
    cyc.use_denoising = False
    cyc.use_adaptive_sampling = False
    device = {"device": "CPU", "compute_device_type": "NONE", "devices": []}
    if device_mode == "CPU":
        cyc.device = "CPU"
        scene.render.threads_mode = "AUTO"
        return device
    try:
        prefs = bpy.context.preferences.addons["cycles"].preferences
        for kind in (prefer, "CUDA"):
            prefs.compute_device_type = kind
            prefs.refresh_devices()
            gpus = [d for d in prefs.devices if d.type == kind]
            if gpus:
                for d in prefs.devices:
                    d.use = d.type == kind
                cyc.device = "GPU"
                device = {"device": "GPU", "compute_device_type": kind, "devices": sorted({d.name for d in gpus})}
                break
    except Exception as exc:  # pragma: no cover - reported, CPU fallback
        device["error"] = str(exc)
    if device["device"] == "CPU":
        cyc.device = "CPU"
    return device


def save_blend(path):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    bpy.ops.wm.save_as_mainfile(filepath=str(path), compress=False)


def open_blend(path):
    bpy.ops.wm.open_mainfile(filepath=str(path))


def save_blend_copy(path):
    """Save a copy: bpy.data.filepath stays as it was (empty in a factory session), so a later FBX export writes an
    empty Original|ApplicationNativeFile instead of the host path of the .blend."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    bpy.ops.wm.save_as_mainfile(filepath=str(path), compress=False, copy=True)


def append_objects(path, prefix):
    """Append the objects named <prefix>* of a .blend into the current (factory) scene; returns them by name.
    Unlike open_blend, bpy.data.filepath stays empty."""
    with bpy.data.libraries.load(str(path), link=False) as (src, dst):
        dst.objects = sorted(n for n in src.objects if n.startswith(prefix))
    scene = bpy.context.scene
    out = {}
    for o in dst.objects:
        scene.collection.objects.link(o)
        out[o.name] = o
    return out
