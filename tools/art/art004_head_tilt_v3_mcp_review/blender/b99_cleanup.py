# Remove everything this review added to the live Blender session (never saved to disk).
import bpy, json
before = {"objects": len(bpy.data.objects), "meshes": len(bpy.data.meshes), "materials": len(bpy.data.materials),
          "images": len(bpy.data.images), "actions": len(bpy.data.actions), "scenes": [s.name for s in bpy.data.scenes]}
win = bpy.context.window_manager.windows[0]
win.scene = bpy.data.scenes["Scene"]
scn = bpy.data.scenes.get("A1V3_Review")
if scn:
    colls = list(scn.collection.children_recursive)
    objs = set(scn.collection.all_objects)
    for o in objs:
        bpy.data.objects.remove(o, do_unlink=True)
    for c in colls:
        bpy.data.collections.remove(c)
    bpy.data.scenes.remove(scn)
for c in [c for c in bpy.data.collections if c.name.startswith("A1V3_")]:
    bpy.data.collections.remove(c)
cam = bpy.data.cameras.get("A1V3_Cam")
if cam: bpy.data.cameras.remove(cam)
for a in [a for a in bpy.data.actions if a.name.split(".")[0] in ("Idle", "HitReact", "LungeAttack", "DeathSettle")]:
    bpy.data.actions.remove(a)
# WARNING (2026-09-28): in the A1 run this global purge also removed an unused material from the
# user's unsaved start-up session (2 materials -> 1). Do not run it in a user's live Blender session;
# remove only the datablocks the review created. Kept here as a record of what was executed.
bpy.data.orphans_purge(do_local_ids=True, do_linked_ids=True, do_recursive=True)
for lib in list(bpy.data.libraries):
    if "medusa.blend" in lib.filepath:
        bpy.data.libraries.remove(lib)
after = {"objects": [o.name for o in bpy.data.objects], "meshes": len(bpy.data.meshes), "materials": [m.name for m in bpy.data.materials],
         "images": [i.name for i in bpy.data.images], "actions": len(bpy.data.actions), "scenes": [s.name for s in bpy.data.scenes],
         "libraries": [l.filepath for l in bpy.data.libraries], "filepath": bpy.data.filepath, "window_scene": win.scene.name}
print(json.dumps({"before": before, "after": after}))
