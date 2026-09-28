# Live-Blender MCP step 10 (diagnostic only, in memory, NOT exported, NOT a candidate):
# same -15 deg tilt, but the face (part 10) and rear neck (part 14) blend the angle
# from 0 at z=38.5 cm to full at z=42 cm (smoothstep). Crown (part 1) rotates fully.
import bpy, json, math, os
import numpy as np
from mathutils import Matrix, Vector
from mathutils.bvhtree import BVHTree
scn = bpy.data.scenes["A1V3_Review"]
src = bpy.data.objects["SK_Medusa_Body_fbxv2"]
old = bpy.data.objects.get("SK_Medusa_Body_rampprobe")
if old: bpy.data.objects.remove(old, do_unlink=True)
o = src.copy(); o.data = src.data.copy(); o.name = "SK_Medusa_Body_rampprobe"
col = bpy.data.collections.get("A1V3_rampprobe") or bpy.data.collections.new("A1V3_rampprobe")
if col.name not in scn.collection.children: scn.collection.children.link(col)
col.objects.link(o)
me = o.data
cols = np.empty(len(me.loops) * 4, dtype=np.float32); me.color_attributes["A1V3_ID"].data.foreach_get("color", cols); cols = cols.reshape(-1, 4)
def pid(p):
    c = cols[p.loop_start]
    if c[0] > .9 and c[1] < .1 and c[2] < .1: return 10
    if c[0] > .9 and c[1] > .9 and c[2] < .1: return 14
    if c[0] < .1 and c[1] > .9 and c[2] < .1: return 1
    return 0
part = [pid(p) for p in me.polygons]
vpart = {}
for p, k in zip(me.polygons, part):
    if k:
        for v in p.vertices: vpart[v] = k
piv = Vector((0, 0, 38.5)); z0, z1 = 38.5, 42.0
def ang(v, k):
    if k == 1: return -15.0
    t = min(1.0, max(0.0, (me.vertices[v].co.z - z0) / (z1 - z0)))
    return -15.0 * t * t * (3 - 2 * t)
A = {v: ang(v, k) for v, k in vpart.items()}
split = [l.vector.copy() for l in me.corner_normals]
for v, a in A.items():
    R = Matrix.Rotation(math.radians(a), 3, "X"); co = me.vertices[v].co
    co[:] = piv + R @ (co - piv)
for p in me.polygons:
    for l in p.loop_indices:
        v = me.loops[l].vertex_index
        if v in A: split[l] = Matrix.Rotation(math.radians(A[v]), 3, "X") @ split[l]
me.update(); me.normals_split_custom_set(split); me.update()
# render ID views like step 4 for the probe only
cam = bpy.data.objects["A1V3_Cam"]
for ob in scn.objects:
    if ob.type == "MESH": ob.hide_render = ob.name not in ("SK_Medusa_Body_rampprobe", "SK_Medusa_Bow_fbxv2")
ox = bpy.data.objects["SKEL_Medusa_fbxv2"].location.x
d = lambda deg: (math.cos(math.radians(deg)), math.sin(math.radians(deg)))
V = {"neck-front": ("O", (0, -2, .40), (-.02, 0, .40), .16, (1024, 1024)),
     "neck-top55": ("O", (0, -2 * d(55)[0], .40 + 2 * d(55)[1]), (-.02, 0, .40), .16, (1024, 1024)),
     "neck-front34R": ("O", (1.41, -1.41, .40), (-.02, 0, .40), .16, (1024, 1024)),
     "neck-front-low": ("P", (-.02, -.45, .30), (-.02, 0, .40), 35, (1600, 900)),
     "k2-front-d300": ("P", (0, -3 * d(55)[0], .29 + 3 * d(55)[1]), (0, 0, .29), 35, (1920, 1080)),
     "k2-rear-d300": ("P", (0, 3 * d(55)[0], .29 + 3 * d(55)[1]), (0, 0, .29), 35, (1920, 1080))}
me.color_attributes.active_color = me.color_attributes["A1V3_ID"]
me.color_attributes.render_color_index = me.color_attributes.find("A1V3_ID")
for name, (kind, loc, tgt, pp, (rx, ry)) in V.items():
    cam.data.type = "ORTHO" if kind == "O" else "PERSP"
    if kind == "O": cam.data.ortho_scale = pp
    else: cam.data.angle = math.radians(pp)
    scn.render.resolution_x, scn.render.resolution_y = rx, ry
    L = Vector((loc[0] + ox, loc[1], loc[2])); T = Vector((tgt[0] + ox, tgt[1], tgt[2]))
    cam.location = L; cam.rotation_euler = (T - L).to_track_quat("-Z", "Y").to_euler()
    scn.render.filepath = f"C:/tmp/a1v3/blender/renders/id-cull-{name}-rampprobe.png"
    bpy.ops.render.render(write_still=True)
# clearances (cm, mesh data)
co = [v.co.copy() for v in me.vertices]
polys = [list(p.vertices) for p in me.polygons]
q = [i for i, p in enumerate(me.polygons) if cols[p.loop_start][0] > .9 and cols[p.loop_start][1] > .9 and cols[p.loop_start][2] > .9]
tq = BVHTree.FromPolygons(co, [polys[i] for i in q])
crown_v = [v for v, k in vpart.items() if k == 1]
clear = min(tq.find_nearest(co[v])[3] for v in crown_v)
face_v = [v for v, k in vpart.items() if k == 10]
fz = [co[v].z for v in face_v]
print(json.dumps({"moved_vertices": len(A), "crown_to_quiver_min_cm": round(clear, 3),
                  "face_part_z_range_cm": [round(min(fz), 3), round(max(fz), 3)]}))
