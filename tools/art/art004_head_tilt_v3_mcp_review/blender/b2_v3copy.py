# Live-Blender MCP step 2: v3 copy = source body with the recorded head tilt
# (-15 deg about X, pivot z=0.385 m, parts 1/10/14), then verify against the saved v3 FBX.
import bpy, math, json
import numpy as np
from mathutils import Matrix, Vector
ROOT = r"C:/Users/ren/.codex/worktrees/art-foundation/unmached/"
ATLAS = json.load(open(ROOT + "blender/ASSET-MEDUSA-001/atlas-report.json"))
scn = bpy.data.scenes["A1V3_Review"]
col2 = bpy.data.collections["A1V3_v2"]
col3 = bpy.data.collections.new("A1V3_v3"); scn.collection.children.link(col3)
src = {o.name.split(".")[0]: o for o in col2.objects}
arm2 = src["SKEL_Medusa"]
copies = {}
for key, o in src.items():
    c = o.copy()
    if o.data is not None:
        c.data = o.data.copy()
    c.name = key + "_A1V3v3"
    col3.objects.link(c)
    copies[key] = c
for key, c in copies.items():
    if src[key].parent is arm2:
        c.parent = copies["SKEL_Medusa"]
        for m in c.modifiers:
            if m.type == "ARMATURE":
                m.object = copies["SKEL_Medusa"]
for key, o in src.items():
    o.name = key + "_A1V3v2"
mesh = copies["SK_Medusa_Body"].data
uv = mesh.uv_layers.active.data
def label(poly):
    for name, cell in ATLAS["cells"].items():
        u0 = (cell["x"] + cell["inset"]) / 2048; u1 = (cell["x"] + cell["cell"] - cell["inset"]) / 2048
        v0 = 1 - (cell["y_top"] + cell["cell"] - cell["inset"]) / 2048; v1 = 1 - (cell["y_top"] + cell["inset"]) / 2048
        if all(u0 <= uv[l].uv.x <= u1 and v0 <= uv[l].uv.y <= v1 for l in poly.loop_indices):
            return name
    return "unassigned"
labels = [label(p) for p in mesh.polygons]
moved = {i for i, l in enumerate(labels) if l in ("tripo_part_1", "tripo_part_10", "tripo_part_14")}
counts = {n: labels.count(n) for n in ("tripo_part_1", "tripo_part_10", "tripo_part_14")}
verts = {v for p in mesh.polygons if p.index in moved for v in p.vertices}
rot = Matrix.Rotation(math.radians(-15.0), 3, "X"); pivot = Vector((0, 0, .385))
split = [l.vector.copy() for l in mesh.corner_normals]
for i in verts:
    co = mesh.vertices[i].co
    co[:] = pivot + rot @ (co - pivot)
for p in mesh.polygons:
    if p.index in moved:
        for l in p.loop_indices:
            split[l] = rot @ split[l]
mesh.update(); mesh.normals_split_custom_set(split); mesh.update()
# store part labels as an int attribute for later tests (both copies)
for m in (src["SK_Medusa_Body"].data, mesh):
    a = m.attributes.get("a1v3_part") or m.attributes.new("a1v3_part", "INT", "FACE")
    a.data.foreach_set("value", [int(l.split("_")[-1]) if l.startswith("tripo_part_") else -1 for l in labels])
# Verify against the saved v3 FBX (imported into a temporary collection, then removed)
before = set(bpy.data.objects)
tmp = bpy.data.collections.new("A1V3_tmp_fbx"); scn.collection.children.link(tmp)
lc = bpy.context.view_layer.layer_collection.children["A1V3_tmp_fbx"]
bpy.context.view_layer.active_layer_collection = lc
bpy.ops.import_scene.fbx(filepath=ROOT + "blender/ASSET-MEDUSA-001/variants/head-tilt-v3/SK_Medusa_HeadTilt_v3.fbx", use_custom_normals=True)
new = [o for o in bpy.data.objects if o not in before]
fb = next(o for o in new if o.type == "MESH" and "Body" in o.name)
n = len(fb.data.vertices)
a = np.empty(n * 3); fb.data.vertices.foreach_get("co", a)
b = np.empty(len(mesh.vertices) * 3); mesh.vertices.foreach_get("co", b)
diff = float(np.abs(a.reshape(-1, 3) - b.reshape(-1, 3) * 100).max())
res = {"part_counts": counts, "moved_vertices": len(verts), "fbx_body_vertices": n,
       "max_abs_diff_fbx_vs_live_copy_cm": round(diff, 6),
       "fbx_objects": [o.name for o in new]}
for o in new:
    bpy.data.objects.remove(o, do_unlink=True)
bpy.data.collections.remove(tmp)
copies["SKEL_Medusa"].location.x += 0.40
print(json.dumps(res))
