import bpy, json
from collections import defaultdict
from mathutils.bvhtree import BVHTree
ID = ("objects","meshes","materials","images","textures","node_groups","collections","cameras","lights","armatures","actions","worlds","scenes","libraries")
ATLAS = json.load(open(r"C:/Users/ren/WebstormProjects/unmached/unmached/blender/ASSET-MEDUSA-001/atlas-report.json"))
FILES = {
 "production_SK_Medusa": r"C:/Users/ren/WebstormProjects/unmached/unmached/blender/ASSET-MEDUSA-001/export/SK_Medusa.fbx",
 "v2_face_section_neck": r"C:/Users/ren/WebstormProjects/unmached/unmached/blender/ASSET-MEDUSA-001/variants/face-section-neck-v2/SK_Medusa_FaceSectionNeck_v2.fbx",
 "v3_head_tilt_artworktree": r"C:/Users/ren/.codex/worktrees/art-foundation/unmached/blender/ASSET-MEDUSA-001/variants/head-tilt-v3/SK_Medusa_HeadTilt_v3.fbx",
 "t4_candidate": r"C:/Users/ren/WebstormProjects/unmached/unmached/art/pipeline-candidates/ASSET-MEDUSA-001/20260928-t4-local-pass/export/SK_Medusa_Candidate.fbx",
}
rects = {}
for n, c in ATLAS["cells"].items():
    rects[n] = ((c["x"]+c["inset"])/2048, (c["x"]+c["cell"]-c["inset"])/2048, 1-(c["y_top"]+c["cell"]-c["inset"])/2048, 1-(c["y_top"]+c["inset"])/2048)
before = {n: set(getattr(bpy.data, n)) for n in ID}
out = {}
win = bpy.context.window or bpy.context.window_manager.windows[0]
prev = win.scene
try:
    for key, path in FILES.items():
        sc = bpy.data.scenes.new("t4_probe_" + key)
        try:
            win.scene = sc
            with bpy.context.temp_override(window=win, scene=sc, view_layer=sc.view_layers[0]):
                bpy.ops.import_scene.fbx(filepath=path)
        finally:
            win.scene = prev
        objs = [o for o in sc.objects if o.type == "MESH"]
        verts, polys = [], []
        for o in objs:
            base = len(verts); mw = o.matrix_world
            verts.extend(mw @ v.co for v in o.data.vertices)
            polys.extend([base + i for i in p.vertices] for p in o.data.polygons)
        h = max(v.z for v in verts) - min(v.z for v in verts)
        bvh = BVHTree.FromPolygons(verts, polys, all_triangles=False, epsilon=0.0)
        acc = defaultdict(lambda: [0.0, 0.0])
        for o in objs:
            if not o.name.startswith("SK_Medusa_Body"): continue
            uv = o.data.uv_layers[0].data; mw = o.matrix_world; rot = mw.to_3x3()
            for p in o.data.polygons:
                cs = [uv[li].uv for li in p.loop_indices]
                part = next((n for n, (u0,u1,v0,v1) in rects.items() if all(u0-1e-6<=c.x<=u1+1e-6 and v0-1e-6<=c.y<=v1+1e-6 for c in cs)), None)
                if part not in ("tripo_part_8","tripo_part_13","tripo_part_10","tripo_part_14"): continue
                c = mw @ p.center; n = (rot @ p.normal).normalized(); a = p.area
                hp = bvh.ray_cast(c + n*1e-4*h, n, 2*h)[0] is not None
                hm = bvh.ray_cast(c - n*1e-4*h, -n, 2*h)[0] is not None
                if not hp and hm: acc[part][0] += a
                elif hp and not hm: acc[part][1] += a
        out[key] = {p: round((o_ - i_)/(o_ + i_), 3) if o_ + i_ else None for p, (o_, i_) in sorted(acc.items())}
finally:
    doomed = []
    for n in ID:
        doomed.extend(i for i in getattr(bpy.data, n) if i not in before[n])
    bpy.data.batch_remove(doomed)
print("T4PROBE", json.dumps(out))
