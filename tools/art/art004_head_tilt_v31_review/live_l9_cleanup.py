# Remove only what l1/l2 created (by pointer diff); no orphans_purge. Restore the viewport.
import bpy, json
from mathutils import Matrix, Vector, Quaternion
ns = bpy.app.driver_namespace
before = ns["T12_V31_BEFORE"]
view = ns["T12_V31_VIEW"]
win = bpy.context.window_manager.windows[0]
win.scene = bpy.data.scenes[view["scene"]]
area = next(a for a in win.screen.areas if a.type == "VIEW_3D")
sp = area.spaces.active
sp.shading.type = view["shading"]; sp.shading.light = view["light"]; sp.shading.color_type = view["color_type"]
sp.shading.show_backface_culling = view["cull"]
if "T12_V31_OVERLAY" in ns:
    sp.overlay.show_overlays = ns["T12_V31_OVERLAY"]
r3 = sp.region_3d
r3.view_perspective = view["persp"]
r3.view_distance = view["view_distance"]; r3.view_location = Vector(view["view_location"])
r3.view_rotation = Quaternion(view["view_rotation"])
doomed = []
for kind, ptrs in before.items():
    doomed.extend(i for i in getattr(bpy.data, kind) if i.as_pointer() not in ptrs)
names = sorted(f"{type(i).__name__}:{i.name}" for i in doomed)
bpy.data.batch_remove(doomed)
for key in ("T12_V31_BEFORE", "T12_V31_VIEW", "T12_V31_SHOT", "T12_V31_OVERLAY", "T12_V31_ROOT"):
    ns.pop(key, None)
after = {k: len(getattr(bpy.data, k)) for k in ("objects","meshes","materials","images","cameras","collections","scenes","armatures","actions","libraries","textures","node_groups","worlds","lights")}
print(json.dumps({"removed": len(names), "removed_names": names, "after": after, "scene": win.scene.name,
                  "shading": [sp.shading.type, sp.shading.light, sp.shading.color_type, sp.shading.show_backface_culling, r3.view_perspective, sp.overlay.show_overlays],
                  "objects": [o.name for o in bpy.data.objects], "materials": [m.name for m in bpy.data.materials]}))
