import bpy, math, json
from mathutils import Vector
ns = bpy.app.driver_namespace
kind, loc, tgt, p = ns["T12_V31_SHOT"]
scn = bpy.data.scenes["T12_V31_Review"]
cam = bpy.data.objects["T12_V31_Cam"]
cam.data.type = "ORTHO" if kind == "O" else "PERSP"
if kind == "O":
    cam.data.ortho_scale = p
else:
    cam.data.angle = math.radians(p)
cam.location = loc
cam.rotation_euler = (Vector(tgt) - Vector(loc)).to_track_quat("-Z", "Y").to_euler()
cam.data.clip_start, cam.data.clip_end = 0.01, 100
win = bpy.context.window_manager.windows[0]
area = next(a for a in win.screen.areas if a.type == "VIEW_3D")
sp = area.spaces.active
if "T12_V31_OVERLAY" not in ns:
    ns["T12_V31_OVERLAY"] = sp.overlay.show_overlays
sp.overlay.show_overlays = False
sp.shading.type = "SOLID"; sp.shading.light = "STUDIO"; sp.shading.color_type = "TEXTURE"
sp.shading.show_backface_culling = True
sp.region_3d.view_perspective = "CAMERA"
sp.region_3d.view_camera_zoom = 29
sp.region_3d.view_camera_offset = (0, 0)
area.tag_redraw()
print(json.dumps({"cam": list(cam.location), "kind": kind}))
