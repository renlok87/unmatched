"""Bounds of the ART-005 board FBX (all mesh parts) as the table-base footprint reference.

Headless only:
  blender -b --factory-startup --python-exit-code 1 \
      --python art/pipeline-candidates/ASSET-TABLE-BASE-001/scripts/measure_board_fbx.py -- <board.fbx> <out.json>

The FBX is read back in a fresh scene. Numbers are FBX units (UnitScaleFactor 1.0 -> 1 unit = 1 uu):
Blender applies object scale 0.01 on import, so world metres x100 = uu. Axes are the UM_FBX_v1 export
frame as Blender re-imports it; UE shows the same mesh as (x, -y, z) (ART-001, CLI adopt note).
Per part: name, material slots, bounds. Measurement only.
"""
import hashlib
import json
import sys
from pathlib import Path

import bpy
from mathutils import Vector

args = sys.argv[sys.argv.index("--") + 1:]
fbx, out = Path(args[0]), Path(args[1])
bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.fbx(filepath=str(fbx))
objs = sorted((o for o in bpy.context.scene.objects if o.type == "MESH"), key=lambda o: o.name)


def bounds(pts):
    lo = Vector((min(p.x for p in pts), min(p.y for p in pts), min(p.z for p in pts)))
    hi = Vector((max(p.x for p in pts), max(p.y for p in pts), max(p.z for p in pts)))
    return lo, hi


def uu(v):
    return [round(c * 100.0, 3) for c in v]


parts = []
allpts = []
for o in objs:
    pts = [o.matrix_world @ v.co for v in o.data.vertices]
    if not pts:
        continue
    allpts += pts
    lo, hi = bounds(pts)
    parts.append({"name": o.name, "materials": [m.name if m else None for m in o.data.materials],
                  "triangles": sum(len(p.vertices) - 2 for p in o.data.polygons),
                  "bounds_min_uu": uu(lo), "bounds_max_uu": uu(hi), "size_uu": uu(hi - lo)})
lo, hi = bounds(allpts)
top_parts = [p for p in parts if abs(p["bounds_max_uu"][2] - uu(hi)[2]) < 2.0]
# horizontal faces (|n.z| > 0.99) grouped by Z level (0.1 uu): candidates for z-fighting with a flat tray top
levels = {}
for o in objs:
    mw = o.matrix_world
    nm = mw.to_3x3().inverted().transposed()
    for poly in o.data.polygons:
        n = (nm @ poly.normal).normalized()
        if abs(n.z) <= 0.99:
            continue
        z = round((mw @ poly.center).z * 100.0, 1)
        area = poly.area * abs(mw.determinant()) ** (2.0 / 3.0) * 1e4
        key = (z, "up" if n.z > 0 else "down")
        rec = levels.setdefault(key, {"z_uu": z, "facing": key[1], "faces": 0, "area_uu2": 0.0, "parts": set()})
        rec["faces"] += 1
        rec["area_uu2"] += area
        rec["parts"].add(o.name.split(".")[0].split("_")[0])
horizontal = sorted(({**v, "area_uu2": round(v["area_uu2"], 1), "parts": sorted(v["parts"])} for v in levels.values()),
                    key=lambda v: (v["z_uu"], v["facing"]))
res = {
    "fbx": fbx.as_posix(), "fbx_sha256": hashlib.sha256(fbx.read_bytes()).hexdigest(),
    "mesh_objects": len(parts), "triangles": sum(p["triangles"] for p in parts),
    "bounds_min_uu_export_frame": uu(lo), "bounds_max_uu_export_frame": uu(hi), "size_uu_export_frame": uu(hi - lo),
    "centre_xy_uu_export_frame": [round((lo.x + hi.x) * 50.0, 3), round((lo.y + hi.y) * 50.0, 3)],
    "ue_bounds_uu_predicted": {"min": [uu(lo)[0], -uu(hi)[1], uu(lo)[2]], "max": [uu(hi)[0], -uu(lo)[1], uu(hi)[2]]},
    "long_axis_export_frame": "X" if hi.x - lo.x >= hi.y - lo.y else "Y",
    "parts_touching_top_within_2uu": len(top_parts),
    "horizontal_face_levels_uu": horizontal,
    "parts": parts,
    "note": "export frame = FBX read back in Blender; UE axes = (x, -y, z). Measurement only.",
}
out.parent.mkdir(parents=True, exist_ok=True)
out.write_text(json.dumps(res, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
print("BOARD_BOUNDS", json.dumps({k: res[k] for k in ("mesh_objects", "size_uu_export_frame", "bounds_min_uu_export_frame",
                                                      "bounds_max_uu_export_frame", "long_axis_export_frame")}))
