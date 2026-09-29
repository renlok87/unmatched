"""Independent read-back of a static prop FBX (no dependency on the build script).

blender -b --factory-startup --python-exit-code 1 --python check_static_prop_fbx.py -- <fbx> <out.json> [front_z_frac]
blender ... -- <fbx> <out.json> <candidate-params.json>   (front_check of static_prop_candidate.py params)

Measures in a fresh scene: objects, triangles, material slots, UV layers, custom/split normals,
dimensions as UE would see them (FBX numbers, UnitScaleFactor 1.0 -> 1 unit = 1 uu),
pivot (object origin vs bounds), topology after welding coincident vertices (open / non-manifold
edges, faces whose winding disagrees with a consistent outward orientation) and the horizontal
direction of the most protruding vertex band at front_z_frac of the height (barrel: the bung = front).
With a params JSON instead of front_z_frac, its front_check is applied as well: method protrusion sets the band
height; method axis_extent adds "front_check" (largest vertex extent along +-X/+-Y in the height band, measured in
this read-back frame, where the .blend axis maps by the UM_FBX_v1 +90 deg Z turn: -Y -> +X, +X -> +Y, +Y -> -X,
-X -> -Y). Without a params JSON the output is unchanged.
"""
import json
import math
import sys

import bmesh
import bpy
from mathutils import Vector

args = sys.argv[sys.argv.index("--") + 1:]
fbx, out = args[0], args[1]
front_cfg = None
if len(args) > 2 and args[2].lower().endswith(".json"):
    front_cfg = json.load(open(args[2], encoding="utf-8")).get("front_check")
    zfrac = float(front_cfg.get("z_frac", 0.5)) if front_cfg and front_cfg.get("method") == "protrusion" else 0.5
else:
    zfrac = float(args[2]) if len(args) > 2 else 0.5
bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.fbx(filepath=fbx)
objs = [o for o in bpy.context.scene.objects if o.type == "MESH"]
res = {"fbx": fbx, "mesh_objects": [o.name for o in objs],
       "armatures": sum(1 for o in bpy.context.scene.objects if o.type == "ARMATURE")}
o = objs[0]
me = o.data
# FBX numbers = mesh data * object scale; Blender applies 0.01 object scale for UnitScaleFactor 1.0 (cm)
pts = [Vector((v.co.x * o.scale.x, v.co.y * o.scale.y, v.co.z * o.scale.z)) for v in me.vertices]
lo = Vector((min(p.x for p in pts), min(p.y for p in pts), min(p.z for p in pts)))
hi = Vector((max(p.x for p in pts), max(p.y for p in pts), max(p.z for p in pts)))
uu = 100.0  # Blender metres back to FBX centimetre numbers
res.update({
    "object_scale": [round(v, 6) for v in o.scale],
    "object_location": [round(v, 6) for v in o.location],
    "triangles": sum(len(p.vertices) - 2 for p in me.polygons),
    "material_slots": [m.name if m else None for m in me.materials],
    "uv_layers": [l.name for l in me.uv_layers],
    "has_custom_split_normals": bool(getattr(me, "has_custom_normals", False)),
    "dimensions_uu_blender_axes": [round((hi[i] - lo[i]) * uu, 3) for i in range(3)],
    "bounds_min_uu": [round(v * uu, 3) for v in lo], "bounds_max_uu": [round(v * uu, 3) for v in hi],
})
bm = bmesh.new()
bm.from_mesh(me)
bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=1e-6 / max(o.scale.x, 1e-12))  # 1 micrometre in FBX units
before = {f.index: f.normal.copy() for f in bm.faces}
bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
res["topology_welded_1um"] = {
    "open_edges": sum(1 for e in bm.edges if e.is_boundary),
    "non_manifold_edges": sum(1 for e in bm.edges if not e.is_manifold and not e.is_boundary),
    "faces_with_inconsistent_winding": sum(1 for f in bm.faces if before[f.index].dot(f.normal) < 0),
}
bm.free()
cx, cy = (lo.x + hi.x) / 2, (lo.y + hi.y) / 2
z0 = lo.z + (hi.z - lo.z) * zfrac
band = [p for p in pts if abs(p.z - z0) < (hi.z - lo.z) * 0.08]
far = max(band, key=lambda p: math.hypot(p.x - cx, p.y - cy))
ang = math.degrees(math.atan2(far.y - cy, far.x - cx))
res["protrusion_direction_deg_from_plus_x_ccw"] = round(ang, 1)
res["protrusion_axis_blender"] = min((("+X", 0), ("+Y", 90), ("-X", 180), ("-X", -180), ("-Y", -90)),
                                     key=lambda a: abs(ang - a[1]))[0]
if front_cfg and front_cfg.get("method") == "axis_extent":
    band = [float(v) for v in front_cfg["z_band_frac"]]
    z_lo, z_hi = lo.z + (hi.z - lo.z) * band[0], lo.z + (hi.z - lo.z) * band[1]
    sel = [p for p in pts if z_lo <= p.z <= z_hi]
    dirs = (("+X", (1.0, 0.0)), ("-X", (-1.0, 0.0)), ("+Y", (0.0, 1.0)), ("-Y", (0.0, -1.0)))
    ext = {k: max((p.x - cx) * d[0] + (p.y - cy) * d[1] for p in sel) * uu for k, d in dirs}
    order = sorted(ext, key=lambda k: -ext[k])
    blend_to_readback = {"-Y": "+X", "+X": "+Y", "+Y": "-X", "-X": "-Y"}
    expected = blend_to_readback[front_cfg.get("expected_axis", "-Y")]
    margin_uu = ext[order[0]] - ext[order[1]]
    min_margin_uu = float(front_cfg["min_margin_m"]) * uu
    res["front_check"] = {
        "method": "axis_extent", "feature": front_cfg.get("feature"), "z_band_frac": band, "vertices_in_band": len(sel),
        "extents_uu_from_footprint_centre": {k: round(v, 3) for k, v in ext.items()},
        "largest_axis_readback": order[0], "runner_up_axis_readback": order[1], "margin_uu": round(margin_uu, 3),
        "expected_axis_readback": expected, "min_margin_uu": round(min_margin_uu, 3),
        "conforms": order[0] == expected and margin_uu >= min_margin_uu,
    }
res["note"] = ("Blender FBX import converts FBX axes back to Blender Z-up; UE's FBX import with the same "
               "-Y forward/Z up convention was verified for UM_FBX_v1 in ART-001 (root arrow along +X).")
json.dump(res, open(out, "w", encoding="utf-8"), indent=2, ensure_ascii=False)
print("CHECK_FBX", json.dumps(res))
