# Live-Blender MCP step 8: K2 front ID render with the face part split at the jaw
# (rest-pose z >= 42 cm = facial features, orange = neck/throat of the same part).
import bpy, json, math, os
import numpy as np
from mathutils import Vector
scn = bpy.data.scenes["A1V3_Review"]
b2 = bpy.data.objects["SK_Medusa_Body_fbxv2"]
rest_z = np.array([p.center.z for p in b2.data.polygons])  # cm, v2 = rest
res = {}
for tag in ("v2", "v3"):
    body = bpy.data.objects["SK_Medusa_Body_fbx" + tag]
    attr = body.data.color_attributes["A1V3_ID"]
    cols = np.empty(len(body.data.loops) * 4, dtype=np.float32); attr.data.foreach_get("color", cols)
    cols = cols.reshape(-1, 4)
    n = 0
    for p in body.data.polygons:
        c = cols[p.loop_start]
        if c[0] > .9 and c[1] < .1 and c[2] < .1 and rest_z[p.index] < 42.0:
            cols[p.loop_start:p.loop_start + p.loop_total] = (1, .5, 0, 1); n += 1
    a2 = body.data.color_attributes.get("A1V3_ID2") or body.data.color_attributes.new("A1V3_ID2", "BYTE_COLOR", "CORNER")
    a2.data.foreach_set("color", cols.reshape(-1))
    body.data.color_attributes.active_color = a2
    body.data.color_attributes.render_color_index = body.data.color_attributes.find("A1V3_ID2")
    res[tag] = n
cam = bpy.data.objects["A1V3_Cam"]
OUT = r"C:/tmp/a1v3/blender/renders"
for tag in ("v2", "v3"):
    ox = bpy.data.objects["SKEL_Medusa_fbx" + tag].location.x
    for o in scn.objects:
        if o.type == "MESH":
            o.hide_render = not o.name.endswith("_fbx" + tag)
    for view, sy in (("k2-front-d300", -1),):
        c, s = math.cos(math.radians(55)), math.sin(math.radians(55))
        loc = Vector((ox, sy * 3 * c, .29 + 3 * s)); tgt = Vector((ox, 0, .29))
        cam.data.type = "PERSP"; cam.data.angle = math.radians(35)
        scn.render.resolution_x, scn.render.resolution_y = 1920, 1080
        cam.location = loc; cam.rotation_euler = (tgt - loc).to_track_quat("-Z", "Y").to_euler()
        scn.render.filepath = os.path.join(OUT, f"idsplit-{view}-{tag}.png")
        bpy.ops.render.render(write_still=True)
print(json.dumps({"neck_polys_recoloured": res}))
