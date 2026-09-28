# Live-Blender MCP step 6: position the live 3D viewport for a screenshot.
import bpy, json, sys, math
from mathutils import Vector, Euler, Quaternion
P = json.loads(PARAMS)
scn = bpy.data.scenes["A1V3_Review"]
for c in ("A1V3_fbx_v2", "A1V3_fbx_v3", "A1V3_v2", "A1V3_v3"):
    lc = bpy.context.view_layer.layer_collection.children.get(c)
    if lc:
        lc.hide_viewport = c not in P["show"]
act = P.get("action")
for tag in ("v2", "v3"):
    arm = bpy.data.objects["SKEL_Medusa_A1V3" + tag]
    arm.animation_data_create()
    arm.animation_data.action = bpy.data.actions[act] if act else None
    arm.data.pose_position = "POSE" if act else "REST"
scn.frame_set(P.get("frame", 1))
area = next(a for a in bpy.context.window_manager.windows[0].screen.areas if a.type == "VIEW_3D")
sp = area.spaces.active
sp.shading.type = "SOLID"
sp.shading.light = "STUDIO"
sp.shading.color_type = P.get("color", "TEXTURE")
sp.shading.show_backface_culling = P.get("cull", True)
sp.overlay.show_overlays = False
r3 = sp.region_3d
r3.view_perspective = "PERSP"
sp.lens = P.get("lens", 50)
tgt = Vector(P["target"]); loc = Vector(P["eye"])
if P.get("bone"):
    arm = bpy.data.objects[P["bone"][0]]
    pb = arm.pose.bones[P["bone"][1]]
    bpy.context.view_layer.update()
    hw = arm.matrix_world @ pb.head
    tw = arm.matrix_world @ pb.tail
    c = hw.lerp(tw, P["bone"][2])
    loc = c + (loc - tgt)
    tgt = c
d = loc - tgt
r3.view_location = tgt
r3.view_rotation = (-d).to_track_quat("-Z", "Y")
r3.view_distance = d.length
print(json.dumps({"area": [area.width, area.height], "frame": scn.frame_current, "action": act}))
