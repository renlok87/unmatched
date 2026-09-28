# NOTE (2026-09-28, after the verifier vc): this file was corrected AFTER the live run.
# The copy executed in live Blender (~10:32) rotated the socket by +15 deg (z would be 37.465);
# this -15 deg version was edited at 10:42, after b99_cleanup removed the scene, and was never run.
# The published numbers (7.639 / 8.511 / 1.122 cm, rotated socket (0; 3.864; 39.535), offset 1.044)
# are confirmed by the headless recomputation tools/art/art004_head_tilt_v3_followup.py
# (head_socket in followup-measurements.json); build_json.py now reads them from there.
# Live-Blender MCP step 9: Head socket (UE component (0,4,38.5) cm = FBX data (0,-4,38.5))
# against the facial-feature centroid and the nearest body surface, v2 vs v3.
import bpy, json, math
import numpy as np
from mathutils import Vector
from mathutils.bvhtree import BVHTree
sock = Vector((0.0, -4.0, 38.5))
b2 = bpy.data.objects["SK_Medusa_Body_fbxv2"]
rest_z = np.array([p.center.z for p in b2.data.polygons])
out = {}
for tag in ("v2", "v3"):
    me = bpy.data.objects["SK_Medusa_Body_fbx" + tag].data
    cols = np.empty(len(me.loops) * 4, dtype=np.float32); me.color_attributes["A1V3_ID"].data.foreach_get("color", cols)
    cols = cols.reshape(-1, 4)
    face = [p.index for p in me.polygons if cols[p.loop_start][0] > .9 and cols[p.loop_start][1] < .1 and cols[p.loop_start][2] < .1]
    feat = [i for i in face if rest_z[i] >= 42.0]
    fv = sorted({v for i in feat for v in me.polygons[i].vertices})
    co = np.array([me.vertices[v].co[:] for v in fv])
    cen = Vector(co.mean(axis=0))
    bvh = BVHTree.FromPolygons([v.co for v in me.vertices], [list(p.vertices) for p in me.polygons])
    loc, nrm, idx, dist = bvh.find_nearest(sock)
    # ray along -Y (forward in FBX data = front of figure) to test inside/outside
    hits = 0; o = sock.copy()
    while True:
        h = bvh.ray_cast(o, Vector((0, -1, 0)))
        if h[0] is None: break
        hits += 1; o = h[0] + Vector((0, -1e-3, 0))
    out[tag] = {"face_feature_polys": len(feat), "feature_centroid_fbx_cm": [round(x, 3) for x in cen],
                "socket_to_feature_centroid_cm": round((cen - sock).length, 3),
                "socket_nearest_surface_cm": round(dist, 3), "ray_forward_hits": hits}
# where a head-bone-following socket would be for v3: FBX data axes == source axes
# (UE mirrors Y on import), so apply the same Rotation(-15 deg, X) as tilt_head.
th = math.radians(-15.0)
rel = np.array([0, -4.0, 0.0])
r = np.array([[1, 0, 0], [0, math.cos(th), -math.sin(th)], [0, math.sin(th), math.cos(th)]]) @ rel
out["v3_socket_if_rotated_with_head_fbx_cm"] = [round(float(r[0]), 3), round(float(r[1]), 3), round(38.5 + float(r[2]), 3)]
out["v3_socket_offset_vs_rotated_cm"] = round(float(np.linalg.norm(r - rel)), 3)
print(json.dumps(out))
