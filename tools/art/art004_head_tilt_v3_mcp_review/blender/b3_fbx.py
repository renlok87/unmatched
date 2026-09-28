# Live-Blender MCP step 3: import the saved v2/v3 FBX (read-only) into their own collections,
# give them the appended atlas material, record structure. Offsets: v2 at x=-0.4 m, v3 at x=+0.8 m.
import bpy, json
ROOT = r"C:/Users/ren/.codex/worktrees/art-foundation/unmached/blender/ASSET-MEDUSA-001/"
scn = bpy.data.scenes["A1V3_Review"]
mat = bpy.data.materials["M_Medusa_Atlas"]
out = {}
for tag, path, dx in (("v2", "variants/face-section-neck-v2/SK_Medusa_FaceSectionNeck_v2.fbx", -0.4),
                      ("v3", "variants/head-tilt-v3/SK_Medusa_HeadTilt_v3.fbx", 0.8)):
    cname = "A1V3_fbx_" + tag
    col = bpy.data.collections.new(cname); scn.collection.children.link(col)
    bpy.context.view_layer.active_layer_collection = bpy.context.view_layer.layer_collection.children[cname]
    before = set(bpy.data.objects)
    bpy.ops.import_scene.fbx(filepath=ROOT + path, use_custom_normals=True)
    new = [o for o in bpy.data.objects if o not in before]
    info = {}
    for o in new:
        o.name = o.name.split(".")[0] + "_fbx" + tag
        if o.type == "MESH":
            info[o.name] = {"slots": [m.name if m else None for m in o.data.materials],
                            "tris": sum(len(p.vertices) - 2 for p in o.data.polygons),
                            "matrix_scale": [round(v, 4) for v in o.matrix_world.to_scale()]}
            for i in range(len(o.data.materials)):
                o.data.materials[i] = mat
        if o.type == "ARMATURE":
            o.location.x += dx / o.matrix_world.to_scale()[0] * o.matrix_world.to_scale()[0]
            info[o.name] = {"bones": len(o.data.bones), "loc": list(o.location), "scale": list(o.scale)}
    out[tag] = info
print(json.dumps(out))
