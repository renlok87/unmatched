# Live-Blender MCP step 5: draft-clip deformation check on the appended source rig.
# Counts intersecting triangle pairs between moved head parts (1/10/14) and non-head
# parts (all except 1/10/14/3) per frame, for the in-memory v2 and v3 copies.
import bpy, json
import numpy as np
from mathutils.bvhtree import BVHTree
scn = bpy.data.scenes["A1V3_Review"]
res = {}
rigs = {"v2": (bpy.data.objects["SKEL_Medusa_A1V3v2"], bpy.data.objects["SK_Medusa_Body_A1V3v2"]),
        "v3": (bpy.data.objects["SKEL_Medusa_A1V3v3"], bpy.data.objects["SK_Medusa_Body_A1V3v3"])}
for tag, (arm, body) in rigs.items():
    arm.data.pose_position = "POSE"
    part = np.empty(len(body.data.polygons), dtype=np.int64)
    body.data.attributes["a1v3_part"].data.foreach_get("value", part)
    polys = [list(p.vertices) for p in body.data.polygons]
    moved = [i for i, p in enumerate(part) if p in (1, 10, 14)]
    other = [i for i, p in enumerate(part) if p not in (1, 10, 14, 3)]
    quiver = [i for i, p in enumerate(part) if p == 7]
    for action in sorted(bpy.data.actions, key=lambda a: a.name):
        if not action.name.split(".")[0] in ("Idle", "HitReact", "LungeAttack", "DeathSettle"):
            continue
        arm.animation_data_create(); arm.animation_data.action = action
        s, e = (int(x) for x in action.frame_range)
        counts, crown_quiver = [], []
        for f in range(s, e + 1):
            scn.frame_set(f)
            dg = bpy.context.evaluated_depsgraph_get()
            ev = body.evaluated_get(dg); me = ev.to_mesh()
            co = [v.co.copy() for v in me.vertices]; ev.to_mesh_clear()
            ta = BVHTree.FromPolygons(co, [polys[i] for i in moved]); tb = BVHTree.FromPolygons(co, [polys[i] for i in other])
            pairs = [(moved[a], other[b]) for a, b in ta.overlap(tb) if not set(polys[moved[a]]) & set(polys[other[b]])]
            counts.append(len(pairs))
            crown_quiver.append(sum(1 for a, b in pairs if part[a] == 1 and part[b] == 7))
        worst = int(np.argmax(counts)) + s
        res.setdefault(action.name.split(".")[0], {})[tag] = {"frames": e - s + 1, "max": max(counts), "mean": round(sum(counts) / len(counts), 2),
                                                             "crown_quiver_max": max(crown_quiver), "worst_frame": worst}
    arm.animation_data.action = None
print(json.dumps(res))
