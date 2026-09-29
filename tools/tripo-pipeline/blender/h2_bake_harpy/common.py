"""Shared helpers of the H2 bake stages (headless Blender only).

The H2 bake takes a Tripo high-poly "by parts" GLB (geometry, no UV) and the same high-poly after Tripo's 8K texture +
PBR pass (UV0 + BaseColor/MetallicRoughness/Normal per part), builds a game-resolution mesh per part, packs one UV
atlas, bakes BC/N/ORM/TeamMask from the high-poly and rigs the result to UM_HUMANOID_17 (profile driven).

Nothing here touches the live Blender sessions (:9876/:9877): every stage calls read_factory_settings and refuses to
run without -b. The candidate_build library of the CLI (tools/tripo-pipeline/blender/candidate_build) is imported
read-only for the FBX preset, determinism pins, armature and weight rules.
"""

import hashlib
import json
import sys
from pathlib import Path

import bpy
import numpy as np

HERE = Path(__file__).resolve().parent
BLENDER_TOOLS = HERE.parent
REPO = HERE.parents[3]
if str(BLENDER_TOOLS) not in sys.path:
    sys.path.insert(0, str(BLENDER_TOOLS))

STAGE_MARKER = "H2_BAKE_STAGE_OK"


def require_background(name):
    if not bpy.app.background:
        # RuntimeError, not SystemExit: SystemExit would terminate a live Blender session.
        raise RuntimeError("%s: headless only (blender -b --factory-startup)" % name)


def script_args():
    argv = sys.argv
    return argv[argv.index("--") + 1:] if "--" in argv else []


def sha256(path):
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def rel(path):
    p = Path(path).resolve()
    try:
        return p.relative_to(REPO.resolve()).as_posix()
    except ValueError:
        return p.as_posix()


def load_profile(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def write_json(path, data):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=1, sort_keys=True, ensure_ascii=False) + "\n", encoding="utf-8")


def r(v, nd=6):
    return round(float(v), nd)


def rv(vec, nd=6):
    return [r(c, nd) for c in vec]


def mesh_arrays(mesh):
    """(verts Nx3 float64, tris Mx3 int, loop_tri_polys M) of a mesh via loop triangles (object space)."""
    mesh.calc_loop_triangles()
    nv = len(mesh.vertices)
    co = np.empty(nv * 3, dtype=np.float32)
    mesh.vertices.foreach_get("co", co)
    nt = len(mesh.loop_triangles)
    tv = np.empty(nt * 3, dtype=np.int32)
    mesh.loop_triangles.foreach_get("vertices", tv)
    return co.reshape(-1, 3).astype(np.float64), tv.reshape(-1, 3)


def world_verts(obj):
    co, _ = mesh_arrays(obj.data)
    m = np.array(obj.matrix_world)
    return co @ m[:3, :3].T + m[:3, 3]


def tri_normals_areas(v, t):
    a, b, c = v[t[:, 0]], v[t[:, 1]], v[t[:, 2]]
    n = np.cross(b - a, c - a)
    area2 = np.linalg.norm(n, axis=1)
    nn = n / np.maximum(area2, 1e-30)[:, None]
    return nn, area2 * 0.5, (a + b + c) / 3.0


def set_cycles_device(scene, prefer_gpu=True):
    """GPU (OPTIX > CUDA) if the preference exposes one, else CPU. Returns a report dict."""
    scene.render.engine = "CYCLES"
    info = {"requested_gpu": prefer_gpu, "device": "CPU", "backend": None, "devices": []}
    if not prefer_gpu:
        scene.cycles.device = "CPU"
        return info
    try:
        prefs = bpy.context.preferences.addons["cycles"].preferences
    except KeyError:
        scene.cycles.device = "CPU"
        return info
    for backend in ("OPTIX", "CUDA"):
        try:
            prefs.compute_device_type = backend
        except TypeError:
            continue
        prefs.get_devices()
        gpus = [d for d in prefs.devices if d.type == backend]
        if gpus:
            for d in prefs.devices:
                d.use = d.type == backend
            scene.cycles.device = "GPU"
            info.update(device="GPU", backend=backend, devices=[d.name for d in gpus])
            return info
    scene.cycles.device = "CPU"
    return info
