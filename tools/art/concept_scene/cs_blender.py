"""ENV-MAPS P8 concept scene, track A: Blender-side helpers (run inside a fresh headless `blender -b --factory-startup`).

Never a running Blender GUI / MCP session; CPU only (Cycles CPU for the AO bake). numpy only (no scipy / PIL here).

  blender -b --factory-startup --python-exit-code 1 --python tools/art/concept_scene/cs_blender.py -- export <job.json>
  blender -b --factory-startup --python-exit-code 1 --python tools/art/concept_scene/cs_blender.py -- ao <job.json>

Mesh data travel as NPZ (cs_common.Mesh: UE numbers local to the pivot, faces CCW outward in the UE numbers' math frame,
per-corner UV0 in the Blender convention). 'export' builds the object with tools/art/env_kit/k_blender.MeshBuilder
(the UM_FBX_v1 mirror + face reversal), optionally replaces UV0 by a Smart-UV-Project atlas (imported Poly Haven
meshes: their own UVs overlap / tile), sets smooth shading with sharp edges by angle, exports the FBX with
k_blender.export (UM_FBX_v1, deterministic bytes), reads it back in an empty scene (k_blender.roundtrip) and writes the
final NPZ (with the UVs actually exported) for the albedo bake. 'ao' places every final mesh at its pivot and bakes
Cycles CPU ambient occlusion into each mesh's UV0 atlas (all scene meshes occlude each other).
"""
import json
import math
import sys
from pathlib import Path

import bpy
import numpy as np

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
sys.path.insert(0, str(REPO / "tools" / "art" / "env_kit"))
import k_blender as K  # noqa: E402

S, r = K.S, K.r


# ------------------------------------------------------------------ NPZ <-> MeshBuilder
def load_npz(path):
    d = np.load(path, allow_pickle=False)
    return {k: d[k] for k in d.files}


def save_npz(path, d):
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(path, **d)


def builder_from(d):
    mb = K.MeshBuilder(str(d["name"]), n_uv=1)
    mb.add_verts(d["V"].tolist())
    UV = d["UV"]
    for i, f in enumerate(d["F"].tolist()):
        mb.add_face(f, [tuple(u) for u in UV[i].tolist()], int(d["MAT"][i]))
    return mb


def blender_to_ue(co):
    """Blender metres (x, y, z) -> UE numbers of MeshBuilder (X = -by, Y = -bx, Z = bz) x 100 (k_blender module doc)."""
    co = np.asarray(co, np.float64)
    return np.c_[-co[:, 1], -co[:, 0], co[:, 2]] * 100.0


def object_arrays(obj, world=True):
    """Triangulated arrays of a Blender mesh object in UE numbers: V, F (CCW outward in the UE numbers' frame, i.e. the
    reversed Blender loops - MeshBuilder reverses them back), UV (T, 3, 2) of the active UV layer, MAT."""
    import bmesh
    bm = bmesh.new()
    bm.from_mesh(obj.data)
    bmesh.ops.triangulate(bm, faces=bm.faces[:])
    if world:
        bm.transform(obj.matrix_world)
    bm.verts.index_update()
    uvl = bm.loops.layers.uv.active
    V = np.array([v.co[:] for v in bm.verts], np.float64)
    F, UV, MAT = [], [], []
    for f in bm.faces:
        loops = list(f.loops)[::-1]  # the UE-numbers mirror flips the orientation
        F.append([l.vert.index for l in loops])
        UV.append([l[uvl].uv[:] if uvl else (0.0, 0.0) for l in loops])
        MAT.append(f.material_index)
    bm.free()
    return blender_to_ue(V), np.array(F, np.int64), np.array(UV, np.float64), np.array(MAT, np.int64)


def smart_unwrap(obj, angle_deg=60.0, margin=0.004):
    bpy.ops.object.select_all(action="DESELECT")
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj
    bpy.ops.object.mode_set(mode="EDIT")
    bpy.ops.mesh.select_all(action="SELECT")
    # no margin in the projection itself (thousands of small islands would shrink to nothing); the packer adds a
    # fixed fraction of the atlas (4 texels at the atlas size) around each concave island shape
    bpy.ops.uv.smart_project(angle_limit=math.radians(angle_deg), island_margin=0.0, area_weight=0.0,
                             correct_aspect=True, scale_to_bounds=False)
    bpy.ops.uv.pack_islands(rotate=True, margin_method="FRACTION", margin=margin, shape_method="CONCAVE")
    bpy.ops.object.mode_set(mode="OBJECT")


def set_smooth(obj, sharp_deg):
    me = obj.data
    for p in me.polygons:
        p.use_smooth = True
    if sharp_deg is not None:
        try:
            me.set_sharp_from_angle(angle=math.radians(sharp_deg))
        except AttributeError:  # older API
            me.use_auto_smooth = True
            me.auto_smooth_angle = math.radians(sharp_deg)


def export_job(job):
    """job: {"meshes": [{"npz", "fbx", "final", "slots", "unwrap": bool, "sharpDeg": float|None,
    "smoothFaces": "npz" | "all", "readback"}]}"""
    res = []
    for m in job["meshes"]:
        bpy.ops.wm.read_factory_settings(use_empty=True)
        d = load_npz(m["npz"])
        mb = builder_from(d)
        mats = [K.flat_material(s) for s in m["slots"]]
        obj = mb.to_object(mats)
        if m.get("unwrap"):
            smart_unwrap(obj, m.get("unwrapAngleDeg", 60.0), m.get("unwrapMargin", 0.004))
        set_smooth(obj, m.get("sharpDeg"))
        if m.get("smoothFaces") == "npz":
            sm = d["SMOOTH"].astype(bool).tolist()
            for p, s in zip(obj.data.polygons, sm):
                p.use_smooth = bool(s)
        bounds_ue = K.bounds(d["V"])
        exp = K.export(obj, Path(m["fbx"]))
        # final arrays (UVs as exported) for the bake: the loops of the Blender object, back to UE numbers
        V, F, UV, MAT = object_arrays(obj, world=False)
        if len(F) != len(d["F"]):
            raise RuntimeError("%s: triangle count changed in Blender (%d -> %d)" % (m["fbx"], len(d["F"]), len(F)))
        out = dict(d)
        out.update(V=V, F=F, UV=UV, MAT=MAT)
        save_npz(m["final"], out)
        uvs = UV.reshape(-1, 2)
        rb = K.roundtrip(Path(m["fbx"]), int(len(F)), list(m["slots"]), bounds_ue)
        rep = {"name": str(d["name"]), "fbx": exp["fbx"], "sha256": exp["sha256"], "bytes": exp["bytes"],
               "triangles": int(len(F)), "slots": list(m["slots"]), "boundsLocalUU": bounds_ue,
               "pivotBoard": [r(v, 3) for v in d["pivot"].tolist()],
               "uv0": {"min": [r(float(uvs[:, 0].min()), 4), r(float(uvs[:, 1].min()), 4)],
                       "max": [r(float(uvs[:, 0].max()), 4), r(float(uvs[:, 1].max()), 4)],
                       "unwrap": "smart_project + pack_islands" if m.get("unwrap") else "authored"},
               "shading": {"sharpDeg": m.get("sharpDeg"), "faces": m.get("smoothFaces", "all")},
               "um_fbx_v1_conformance": exp["um_fbx_v1_conformance"], "readback": rb}
        K.write_json(Path(m["readback"]), rb)
        res.append(rep)
    K.write_json(Path(job["report"]), {"exports": res})


# ------------------------------------------------------------------ AO bake (Cycles CPU)
def ao_job(job):
    """job: {"meshes": [{"final": npz, "ao": png, "size": [w, h]}], "samples", "distanceUU", "threads"}: all meshes in
    one scene at their pivots (metres, Blender frame via MeshBuilder), AO baked per mesh into its UV0 (8-bit PNG,
    linear values, margin dilation by Cycles)."""
    bpy.ops.wm.read_factory_settings(use_empty=True)
    sc = bpy.context.scene
    sc.render.engine = "CYCLES"
    sc.cycles.device = "CPU"
    sc.cycles.samples = int(job.get("samples", 32))
    sc.render.threads_mode = "FIXED"
    sc.render.threads = int(job.get("threads", 6))
    sc.render.bake.margin = int(job.get("marginPx", 8))
    world = bpy.data.worlds.new("W")
    sc.world = world
    world.light_settings.distance = float(job.get("distanceUU", 120.0)) / 100.0
    objs = []
    for m in job["meshes"]:
        d = load_npz(m["final"])
        mb = builder_from(d)
        mat = bpy.data.materials.new("AO_" + str(d["name"]))
        mat.use_nodes = True
        obj = mb.to_object([mat])
        piv = d["pivot"]
        obj.location = (-piv[1] / 100.0, -piv[0] / 100.0, piv[2] / 100.0)
        objs.append((obj, mat, m))
    bpy.context.view_layer.update()
    for obj, mat, m in objs:
        w, h = m["size"]
        img = bpy.data.images.new("AO_" + obj.name, width=int(w), height=int(h), alpha=False, float_buffer=False)
        img.colorspace_settings.name = "Non-Color"
        nt = mat.node_tree
        tex = nt.nodes.new("ShaderNodeTexImage")
        tex.image = img
        nt.nodes.active = tex
        bpy.ops.object.select_all(action="DESELECT")
        obj.select_set(True)
        bpy.context.view_layer.objects.active = obj
        bpy.ops.object.bake(type="AO", margin=int(job.get("marginPx", 8)), use_clear=True)
        img.filepath_raw = str(m["ao"])
        img.file_format = "PNG"
        Path(m["ao"]).parent.mkdir(parents=True, exist_ok=True)
        img.save()
        nt.nodes.remove(tex)
    K.write_json(Path(job["report"]), {"ao": [{"name": o.name, "png": m["ao"], "size": m["size"]} for o, _, m in objs],
                                       "samples": sc.cycles.samples, "distanceUU": job.get("distanceUU", 120.0)})


def main():
    args = K.script_args()
    if len(args) < 2:
        raise SystemExit("usage: cs_blender.py -- export|ao <job.json>")
    job = json.loads(Path(args[1]).read_text(encoding="utf-8"))
    if args[0] == "export":
        export_job(job)
    elif args[0] == "ao":
        ao_job(job)
    else:
        raise SystemExit("unknown command %s" % args[0])


if __name__ == "__main__":
    main()
