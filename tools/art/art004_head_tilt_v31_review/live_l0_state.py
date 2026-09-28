import bpy, json
wm = bpy.context.window_manager
out = {"windows": [], "ids": {k: len(getattr(bpy.data, k)) for k in ("objects","meshes","materials","images","cameras","collections","scenes","armatures","actions","libraries","textures","node_groups","worlds","lights")},
       "file": bpy.data.filepath, "is_dirty": bpy.data.is_dirty}
for w in wm.windows:
    wi = {"scene": w.scene.name, "areas": []}
    for a in w.screen.areas:
        ai = {"type": a.type, "w": a.width, "h": a.height}
        if a.type == "VIEW_3D":
            sp = a.spaces.active; sh = sp.shading
            ai.update({"shading": sh.type, "light": sh.light, "color_type": sh.color_type, "cull": sh.show_backface_culling,
                       "persp": sp.region_3d.view_perspective, "camera": sp.camera.name if sp.camera else None})
        wi["areas"].append(ai)
    out["windows"].append(wi)
print(json.dumps(out))
