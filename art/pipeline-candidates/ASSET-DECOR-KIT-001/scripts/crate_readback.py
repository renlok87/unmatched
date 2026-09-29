"""ASSET-DECOR-KIT-001.CRATE, step 2 of 2: crate-specific FBX read-back in a fresh Blender process (independent of
crate_build.py; complements tools/tripo-pipeline/blender/check_static_prop_fbx.py, whose "protrusion" direction is a
barrel measure: on this crate the corner caps/studs protrude most, so it reports a diagonal, not the front).

    blender -b --factory-startup --python-exit-code 1 --python crate_readback.py -- <fbx> <build-report.json> <out.json>

Measures after Blender's FBX import (axes converted back to Z-up; the UM_FBX_v1 +90 deg Z export rotation is not
undone, so the authoring front -Y reads back as +X, as the barrel bung did in P1.5 and as UE shows it, ART-001):
objects, triangles vs the build report, material slots, UV layers and bounds, colour attributes, dimensions in uu,
pivot, welded (1 um) topology, which sides carry the X braces (faces whose normals lie in the side's plane and are
diagonal = the long edges of the diagonal boards), smoothing, texture paths relative to the FBX and their sha256
against the build report, PNG colour chunks of N/ORM.
"""
import hashlib
import json
import os
import struct
import sys
from pathlib import Path

import bmesh
import bpy
from mathutils import Vector

args = sys.argv[sys.argv.index("--") + 1:]
fbx, build_report, out = Path(args[0]).resolve(), Path(args[1]).resolve(), Path(args[2])
BR = json.loads(build_report.read_text(encoding="utf-8"))
bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.fbx(filepath=str(fbx))
objs = [o for o in bpy.context.scene.objects if o.type == "MESH"]
o = objs[0]
me = o.data
sc = o.scale
U = 100.0 * sc.x  # mesh units -> uu (object scale 0.01 for UnitScaleFactor 1.0)
pts = [Vector((v.co.x * sc.x, v.co.y * sc.y, v.co.z * sc.z)) * 100 for v in me.vertices]
lo = Vector((min(p.x for p in pts), min(p.y for p in pts), min(p.z for p in pts)))
hi = Vector((max(p.x for p in pts), max(p.y for p in pts), max(p.z for p in pts)))

# X-brace long edges: normal perpendicular to the side axis, diagonal in the side plane, centroid near that side and
# at least 0.5 uu inside the posts (inner face 9.0 uu): board-end chamfers tucked into the posts are not counted
sides = {"+X": 0.0, "-X": 0.0, "+Y": 0.0, "-Y": 0.0}
for p in me.polygons:
    n = p.normal
    c = p.center * U
    if c.z < 3.0 or c.z > 22.0:
        continue
    if abs(n.x) < 0.1 and abs(n.y) > 0.3 and abs(n.z) > 0.3 and abs(c.x) > 10.0 and abs(c.y) < 8.5:
        sides["+X" if c.x > 0 else "-X"] += p.area * U * U
    if abs(n.y) < 0.1 and abs(n.x) > 0.3 and abs(n.z) > 0.3 and abs(c.y) > 10.0 and abs(c.x) < 8.5:
        sides["+Y" if c.y > 0 else "-Y"] += p.area * U * U
brace_axes = sorted(k for k, v in sides.items() if v > 1.0)

bm = bmesh.new()
bm.from_mesh(me)
bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=1e-6 / max(sc.x, 1e-12))  # 1 um in FBX units
before = {f.index: f.normal.copy() for f in bm.faces}
bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
topo = {"open_edges": sum(1 for e in bm.edges if e.is_boundary),
        "non_manifold_edges": sum(1 for e in bm.edges if not e.is_manifold and not e.is_boundary),
        "faces_with_inconsistent_winding": sum(1 for f in bm.faces if before[f.index].dot(f.normal) < 0)}
shells = 0
seen = set()
for f in bm.faces:
    if f.index in seen:
        continue
    shells += 1
    stack = [f]
    seen.add(f.index)
    while stack:
        cur = stack.pop()
        for e in cur.edges:
            for g in e.link_faces:
                if g.index not in seen:
                    seen.add(g.index)
                    stack.append(g)
bm.free()


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def png_color_chunks(p):
    data = Path(p).read_bytes()
    pos, found = 8, []
    while pos < len(data):
        ln = struct.unpack(">I", data[pos:pos + 4])[0]
        t = data[pos + 4:pos + 8]
        if t in (b"sRGB", b"gAMA", b"cHRM", b"iCCP"):
            found.append(t.decode())
        pos += 12 + ln
    return sorted(found)


imgs = []
for i in bpy.data.images:
    ap = Path(bpy.path.abspath(i.filepath))
    imgs.append({"name": i.name, "path_rel_to_fbx": os.path.relpath(ap, fbx.parent).replace("\\", "/"),
                 "exists": ap.is_file(), "sha256": sha(ap) if ap.is_file() else None})
tex_dir = fbx.parent.parent / "textures"
tex = {}
for k, rec in BR["textures"].items():
    p = tex_dir / Path(rec["path"]).name
    tex[k] = {"file": "../textures/" + p.name, "exists": p.is_file(), "sha256_matches_build_report": sha(p) == rec["sha256"],
              "png_color_chunks": png_color_chunks(p)}
uv = me.uv_layers[0].data if me.uv_layers else []
us = [d.uv.x for d in uv]
vs = [d.uv.y for d in uv]
dims = [round(hi[i] - lo[i], 3) for i in range(3)]
res = {
    "fbx": fbx.name, "fbx_sha256": sha(fbx), "fbx_sha256_matches_build_report": sha(fbx) == BR["export"]["sha256"],
    "mesh_objects": [x.name for x in objs],
    "armatures": sum(1 for x in bpy.context.scene.objects if x.type == "ARMATURE"),
    "object_scale": [round(v, 6) for v in sc], "object_location": [round(v, 6) for v in o.location],
    "object_rotation_deg": [round(v * 57.29577951308232, 4) for v in o.rotation_euler],
    "triangles": sum(len(p.vertices) - 2 for p in me.polygons), "triangles_build_report": BR["triangles"],
    "material_slots": [m.name if m else None for m in me.materials],
    "uv_layers": [l.name for l in me.uv_layers],
    "uv0_bounds": [round(min(us), 6), round(min(vs), 6), round(max(us), 6), round(max(vs), 6)] if us else None,
    "color_attributes": [a.name for a in me.color_attributes],
    "smooth_faces": sum(1 for p in me.polygons if p.use_smooth), "smooth_faces_build_report": BR["smooth_faces"],
    "has_custom_split_normals": bool(getattr(me, "has_custom_normals", False)),
    "bounds_min_uu": [round(v, 3) for v in lo], "bounds_max_uu": [round(v, 3) for v in hi],
    "dimensions_uu_readback_axes": dims,
    "topology_welded_1um": topo, "shells_after_weld": shells, "shells_build_report": BR["parts"]["count"],
    "x_brace_edge_area_uu2_by_side": {k: round(v, 3) for k, v in sides.items()},
    "x_brace_sides_readback": brace_axes,
    "images_referenced": imgs, "textures": tex,
    "note": ("Readback frame: Blender FBX import (Z up); authoring -Y front reads back as +X = UE +X (ART-001). "
             "The crate is symmetric front/back, so the X braces show on +X and -X; plain planks on +-Y."),
}
res["checks"] = {
    "one_mesh_no_armature": len(objs) == 1 and res["armatures"] == 0,
    "fbx_bytes_as_built": res["fbx_sha256_matches_build_report"],
    "triangles_as_built": res["triangles"] == BR["triangles"],
    "one_slot_named": res["material_slots"] == BR["material_slots"],
    "uv0_present_in_0_1": res["uv_layers"] != [] and res["uv0_bounds"][0] >= 0 and res["uv0_bounds"][1] >= 0
                          and res["uv0_bounds"][2] <= 1 and res["uv0_bounds"][3] <= 1,
    "no_colour_attributes": res["color_attributes"] == [],
    "size_25_uu_1pct": all(abs(d - 25.0) <= 0.25 for d in dims),
    "pivot_base_centre": abs(lo.z) < 1e-3 and abs(lo.x + hi.x) < 1e-3 and abs(lo.y + hi.y) < 1e-3,
    "object_scale_0_01_no_rotation": all(abs(v - 0.01) < 1e-9 for v in sc) and all(abs(v) < 1e-6 for v in o.rotation_euler),
    "closed_after_1um_weld": topo["open_edges"] == 0 and topo["non_manifold_edges"] == 0
                             and topo["faces_with_inconsistent_winding"] == 0,
    "shells_as_built": shells == BR["parts"]["count"],
    "x_braces_on_plus_minus_x": brace_axes == ["+X", "-X"],
    "smooth_faces_as_built": res["smooth_faces"] == BR["smooth_faces"],
    "texture_paths_relative_and_present": all(i["exists"] and not i["path_rel_to_fbx"].startswith("/")
                                              and ":" not in i["path_rel_to_fbx"] for i in imgs) and len(imgs) >= 1,
    "textures_as_built": all(t["exists"] and t["sha256_matches_build_report"] for t in tex.values()),
    "n_orm_without_colour_chunks": tex["N"]["png_color_chunks"] == [] and tex["ORM"]["png_color_chunks"] == [],
}
res["checks_passed"] = all(res["checks"].values())
out.write_text(json.dumps(res, indent=1, ensure_ascii=False), encoding="utf-8")
print("CRATE_READBACK", json.dumps(res["checks"]), "ALL", res["checks_passed"])
if not res["checks_passed"]:
    raise SystemExit("readback checks failed: %s" % [k for k, v in res["checks"].items() if not v])
