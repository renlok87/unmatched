# Live-Blender MCP step 1: isolated scene, append (read-only) Medusa source objects,
# build v2/v3 copies in memory. Never saves medusa.blend.
import bpy, math, json
from mathutils import Matrix, Vector
SRC = r"C:/Users/ren/.codex/worktrees/art-foundation/unmached/blender/ASSET-MEDUSA-001/medusa.blend"
SCN = "A1V3_Review"
if SCN in bpy.data.scenes:
    raise RuntimeError("scene exists; run cleanup first")
scn = bpy.data.scenes.new(SCN)
bpy.context.window_manager.windows[0].scene = scn
names = ["SK_Medusa_Body", "SK_Medusa_Bow", "SKEL_Medusa", "SM_Medusa_Base"]
with bpy.data.libraries.load(SRC, link=False) as (src, dst):
    dst.objects = [n for n in src.objects if n in names]
    dst.actions = list(src.actions)
col2 = bpy.data.collections.new("A1V3_v2"); scn.collection.children.link(col2)
for o in dst.objects:
    col2.objects.link(o)
body = next(o for o in dst.objects if o.name.startswith("SK_Medusa_Body"))
arm = next(o for o in dst.objects if o.name.startswith("SKEL_Medusa"))
bow = next(o for o in dst.objects if o.name.startswith("SK_Medusa_Bow"))
base = next(o for o in dst.objects if o.name.startswith("SM_Medusa_Base"))
res = {"appended": [o.name for o in dst.objects], "actions": [a.name for a in dst.actions],
       "body_parent": body.parent.name if body.parent else None,
       "bow_parent": bow.parent.name if bow.parent else None,
       "mods": [(m.type, getattr(m, 'object', None) and m.object.name) for m in body.modifiers],
       "materials": [m.name for m in body.data.materials], "scene": scn.name,
       "lib_filepath": [l.filepath for l in bpy.data.libraries]}
print(json.dumps(res))
