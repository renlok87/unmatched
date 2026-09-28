"""ASSET-DECOR-KIT-001.FACADES, step 3 of 3: facade-specific FBX read-back in a fresh Blender process
(independent of facades_build.py; complements tools/tripo-pipeline/blender/check_static_prop_fbx.py, whose
"protrusion" direction is a barrel measure and does not apply to a flat wall).

    blender -b --factory-startup --python-exit-code 1 --python facades_readback.py -- <fbx> <out.json>

Measures after Blender's FBX import (axes converted back to Z-up; the UM_FBX_v1 +90 deg Z export rotation is not
undone, so the authoring front -Y reads back as +X, as the barrel bung did in P1.5 and as UE shows it, ART-001):
area-weighted normal of the largest planar face group (the outer face), which side of the pivot it is on,
dimensions (length along Y, thickness along X), triangles, material slots, UV0 bounds, smoothing, image paths.
"""
import json
import os
import sys
from pathlib import Path

import bpy
from mathutils import Vector

args = sys.argv[sys.argv.index("--") + 1:]
fbx, out = args[0], args[1]
bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.fbx(filepath=fbx)
objs = [o for o in bpy.context.scene.objects if o.type == "MESH"]
o = objs[0]
me = o.data
sc = o.scale
pts = [Vector((v.co.x * sc.x, v.co.y * sc.y, v.co.z * sc.z)) * 100 for v in me.vertices]  # FBX numbers (uu)
lo = Vector((min(p.x for p in pts), min(p.y for p in pts), min(p.z for p in pts)))
hi = Vector((max(p.x for p in pts), max(p.y for p in pts), max(p.z for p in pts)))
uvd = me.uv_layers[0].data if me.uv_layers else None


def uv_area(p):
    a = [uvd[i].uv for i in p.loop_indices]
    return abs(sum(a[i].x * a[(i + 1) % len(a)].y - a[(i + 1) % len(a)].x * a[i].y for i in range(len(a)))) / 2


groups = {}
for p in me.polygons:
    n = p.normal
    key = (round(n.x, 3), round(n.y, 3), round(n.z, 3))
    g = groups.setdefault(key, [0.0, 0.0])
    g[0] += p.area
    g[1] += uv_area(p) if uvd else 0.0
# the two largest planar groups are the outer face and the back (same polygon, same area); the outer face is the
# textured one: largest UV area per 3D area (front strip 2.5 px/uu vs back 0.625 px/uu in the atlas)
big = sorted(groups.items(), key=lambda kv: -kv[1][0])[:2]
(front_key, (front_area, front_uv)) = max(big, key=lambda kv: kv[1][1] / max(kv[1][0], 1e-12))
other = [kv for kv in big if kv[0] != front_key][0]
front_faces = [p for p in me.polygons if (round(p.normal.x, 3), round(p.normal.y, 3), round(p.normal.z, 3)) == front_key]
front_x = sorted({round(me.vertices[i].co.x * sc.x * 100, 4) for p in front_faces for i in p.vertices})
uv = me.uv_layers[0].data if me.uv_layers else []
us = [d.uv.x for d in uv]
vs = [d.uv.y for d in uv]
# image paths as resolved by the importer, reported relative to the FBX folder (no checkout path in the report)
imgs = [{"name": i.name,
         "path_rel_to_fbx": os.path.relpath(bpy.path.abspath(i.filepath), Path(fbx).resolve().parent).replace("\\", "/"),
         "exists": Path(bpy.path.abspath(i.filepath)).is_file()}
        for i in bpy.data.images]
res = {
    "fbx": fbx,
    "mesh_objects": [x.name for x in objs],
    "armatures": sum(1 for x in bpy.context.scene.objects if x.type == "ARMATURE"),
    "triangles": sum(len(p.vertices) - 2 for p in me.polygons),
    "material_slots": [m.name if m else None for m in me.materials],
    "faces_per_slot": {str(i): sum(1 for p in me.polygons if p.material_index == i) for i in range(len(me.materials))},
    "uv_layers": [l.name for l in me.uv_layers],
    "uv0_bounds": [round(min(us), 6), round(min(vs), 6), round(max(us), 6), round(max(vs), 6)] if us else None,
    "smooth_faces": sum(1 for p in me.polygons if p.use_smooth),
    "bounds_min_uu": [round(v, 3) for v in lo], "bounds_max_uu": [round(v, 3) for v in hi],
    "dimensions_uu_x_thickness_y_length_z_height": [round(hi[i] - lo[i], 3) for i in range(3)],
    "outer_face_normal_readback": list(front_key),
    "outer_face_area_uu2": round(front_area * (sc.x * 100) ** 2, 2),
    "texel_density_px_per_uu_outer_vs_back_at_1024": [round((front_uv / front_area) ** 0.5 * 1024, 4),
                                                       round((other[1][1] / other[1][0]) ** 0.5 * 1024, 4)],
    "back_face_normal_readback": list(other[0]),
    "outer_face_x_values_uu": front_x[:4],
    "outer_face_axis": ("+X" if front_key[0] > 0.999 else "-X" if front_key[0] < -0.999 else
                        "+Y" if front_key[1] > 0.999 else "-Y" if front_key[1] < -0.999 else "other"),
    "pivot_checks": {"base_z0": abs(lo.z) < 1e-3, "centred_along_length_y": abs(lo.y + hi.y) < 1e-3,
                     "outer_face_on_pivot_plane_x0": front_x == [0.0]},
    "images": imgs,
    "note": "UE reads the same FBX with -Y forward / Z up (UM_FBX_v1, ART-001): outer face +X in both.",
}
json.dump(res, open(out, "w", encoding="utf-8"), indent=2, ensure_ascii=False)
print("FACADE_READBACK", json.dumps({k: res[k] for k in ("triangles", "outer_face_axis", "dimensions_uu_x_thickness_y_length_z_height", "pivot_checks")}))
