# T1.2 live review (Blender 9876): isolated scene, FBX imports only (medusa.blend is not opened).
import bpy, json
ROOT = bpy.app.driver_namespace["T12_V31_ROOT"]  # set by run_live_review.py
KINDS = ("objects", "meshes", "materials", "images", "cameras", "collections", "scenes", "armatures",
         "actions", "libraries", "textures", "node_groups", "worlds", "lights")
ns = bpy.app.driver_namespace
if "T12_V31_BEFORE" in ns or "T12_V31_Review" in bpy.data.scenes:
    raise RuntimeError("review already set up; run cleanup first")
ns["T12_V31_BEFORE"] = {k: {i.as_pointer() for i in getattr(bpy.data, k)} for k in KINDS}
win = bpy.context.window_manager.windows[0]
area = next(a for a in win.screen.areas if a.type == "VIEW_3D")
sp = area.spaces.active
r3 = sp.region_3d
ns["T12_V31_VIEW"] = {"scene": win.scene.name, "shading": sp.shading.type, "light": sp.shading.light,
                      "color_type": sp.shading.color_type, "cull": sp.shading.show_backface_culling,
                      "persp": r3.view_perspective, "view_matrix": [list(r) for r in r3.view_matrix],
                      "view_distance": r3.view_distance, "view_location": list(r3.view_location),
                      "view_rotation": list(r3.view_rotation)}
scn = bpy.data.scenes.new("T12_V31_Review")
win.scene = scn
img = bpy.data.images.load(ROOT + "textures/T_Medusa_Atlas_BC.png", check_existing=False)
img.name = "T12_V31_BC"
mat = bpy.data.materials.new("T12_V31_Tex")
mat.use_nodes = True
node = mat.node_tree.nodes.new("ShaderNodeTexImage"); node.image = img
mat.node_tree.links.new(node.outputs["Color"], mat.node_tree.nodes["Principled BSDF"].inputs["Base Color"])
mat.node_tree.nodes.active = node
FILES = {"v2": "variants/face-section-neck-v2/SK_Medusa_FaceSectionNeck_v2.fbx",
         "v31a": "variants/head-tilt-v31-a/SK_Medusa_HeadTilt_v31a.fbx",
         "v31b": "variants/head-tilt-v31-b/SK_Medusa_HeadTilt_v31b.fbx",
         "v31c": "variants/head-tilt-v31-c/SK_Medusa_HeadTilt_v31c.fbx"}
OFFSET = {"v2": -0.25, "v31a": 0.0, "v31b": 0.25, "v31c": 0.5}
out = {}
for tag, rel in FILES.items():
    col = bpy.data.collections.new("T12_V31_" + tag); scn.collection.children.link(col)
    bpy.context.view_layer.active_layer_collection = bpy.context.view_layer.layer_collection.children[col.name]
    before = set(bpy.data.objects)
    bpy.ops.import_scene.fbx(filepath=ROOT + rel, use_custom_normals=True)
    new = [o for o in bpy.data.objects if o not in before]
    for o in new:
        o.name = "T12_" + tag + "_" + o.name.split(".")[0]
        if o.type == "MESH":
            for i in range(len(o.data.materials)):
                o.data.materials[i] = mat
        if o.parent is None:
            o.location.x += OFFSET[tag]
    out[tag] = sorted(o.name for o in new)
cam = bpy.data.objects.new("T12_V31_Cam", bpy.data.cameras.new("T12_V31_Cam"))
scn.collection.objects.link(cam); scn.camera = cam
cam.data.sensor_fit = "HORIZONTAL"
scn.render.resolution_x, scn.render.resolution_y = 1600, 1000
print(json.dumps(out))
