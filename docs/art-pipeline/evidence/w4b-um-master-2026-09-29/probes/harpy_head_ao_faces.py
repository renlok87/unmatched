"""W4-B review fix, read-only evidence probe: AO of Harpy's head (tripo_part_2) per face class.

    blender -b --factory-startup --python-exit-code 1 --python harpy_head_ao_faces.py -- <args.json>
args.json: {"source": segmented-retopo GLB, "atlas_report": atlas-report.json of a run,
            "orm": {"<label>": ORM atlas PNG, ...}, "out": JSON path}

Face classes = the build's ray-escape test (candidate_build.measure.orientation_scores rule: +normal / -normal ray,
offset 1e-4 x height, reach 2 x height) in the scene the AO bake had BEFORE its per-face fix: the Tripo base
tripo_part_4 removed (occluders_excluded), tripo_part_6 flipped whole (expected_inside_out_parts), the head as in the
GLB. "inward" = only the -normal ray escapes (the faces the per-face fix must turn). Each face is sampled at its UV
centroid in the head's atlas cell (remap of mesh_ops.remap_uvs) in every ORM atlas given; the result is the
area-weighted mean ORM.R (0..1) and the area share below 0.25 per class. Nothing is written except args.out.
"""
import json
import sys
from pathlib import Path

import bpy
import numpy as np
from mathutils.bvhtree import BVHTree

args = json.loads(Path(sys.argv[sys.argv.index("--") + 1]).read_text(encoding="utf-8"))
bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.gltf(filepath=args["source"])
meshes = {o.name: o for o in bpy.context.scene.objects if o.type == "MESH"}
bpy.data.objects.remove(meshes.pop("tripo_part_4"), do_unlink=True)
me6 = meshes["tripo_part_6"].data
for p in me6.polygons:
    p.flip()
me6.update()
verts, polys = [], []
for o in meshes.values():
    base = len(verts)
    verts.extend(o.matrix_world @ v.co for v in o.data.vertices)
    polys.extend([base + i for i in p.vertices] for p in o.data.polygons)
bvh = BVHTree.FromPolygons(verts, polys, all_triangles=False, epsilon=0.0)
zs = [v.z for v in verts]
height = max(zs) - min(zs)
eps, reach = 1e-4 * height, 2.0 * height
head = meshes["tripo_part_2"]
cell = json.loads(Path(args["atlas_report"]).read_text(encoding="utf-8"))["cells"]["tripo_part_2"]
uv = head.data.uv_layers.active.data
faces = []
for p in head.data.polygons:
    c = head.matrix_world @ p.center
    n = (head.matrix_world.to_3x3() @ p.normal).normalized()
    plus = bvh.ray_cast(c + n * eps, n, reach)[0] is not None
    minus = bvh.ray_cast(c - n * eps, -n, reach)[0] is not None
    cls = "outward" if (not plus and minus) else "inward" if (plus and not minus) else "undecided"
    u = sum(uv[li].uv[0] for li in p.loop_indices) / len(p.loop_indices)
    v = sum(uv[li].uv[1] for li in p.loop_indices) / len(p.loop_indices)
    faces.append((p.area, cls, u, v))
inner = cell["cell"] - 2 * cell["inset"]
area = np.array([f[0] for f in faces])
out = {"source": Path(args["source"]).name, "faces": len(faces), "cell": cell,
       "class_area_share": {k: round(float(area[[f[1] == k for f in faces]].sum() / area.sum()), 4)
                            for k in ("inward", "outward", "undecided")}, "orm": {}}
for label, png in sorted(args["orm"].items()):
    img = bpy.data.images.load(png, check_existing=False)
    img.colorspace_settings.name = "Non-Color"
    w, h = img.size
    px = np.empty(w * h * 4, dtype=np.float32)
    img.pixels.foreach_get(px)
    red = px.reshape(h, w, 4)[::-1, :, 0]  # Blender rows are bottom-up; row 0 = top of the PNG after the flip
    vals = np.array([red[min(h - 1, int(cell["y_top"] + cell["inset"] + (1 - f[3]) * inner)),
                         min(w - 1, int(cell["x"] + cell["inset"] + f[2] * inner))] for f in faces])
    res = {}
    for k in ("inward", "outward", "undecided"):
        sel = np.array([f[1] == k for f in faces])
        a = area[sel]
        res[k] = {"mean_ao": round(float((a * vals[sel]).sum() / a.sum()), 3),
                  "area_share_below_0_25": round(float(a[vals[sel] < 0.25].sum() / a.sum()), 3)}
    out["orm"][label] = {"file": Path(png).name, "per_class": res}
    bpy.data.images.remove(img)
Path(args["out"]).write_text(json.dumps(out, indent=1, sort_keys=True) + "\n", encoding="utf-8")
print("PROBE_OK", json.dumps(out["class_area_share"]))
