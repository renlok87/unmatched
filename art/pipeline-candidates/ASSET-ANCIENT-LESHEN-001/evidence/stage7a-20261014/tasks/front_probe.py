# UE task (ue_live.Ue().run_task): independent front-axis probe of an imported skeletal mesh, read only.
# ARGS = {"out", "mesh", "z_band": [z0, z1]} ; vertices of LOD0 through GeometryScript (transient DynamicMesh),
# centroid / extremes of the vertices inside the z band (the deer skull 46-55 uu) -> the snout points +X if the front
# is +X. Nothing is created or saved.
import json
u = unreal  # noqa: F821
a = ARGS  # noqa: F821
mesh = u.load_asset(a["mesh"])
if mesh is None:
    raise RuntimeError("asset not found: " + a["mesh"])
dm = u.DynamicMesh()
read = u.GeometryScriptMeshReadLOD()
read.set_editor_property("lod_index", 0)
_dm, outcome = u.GeometryScript_AssetUtils.copy_mesh_from_skeletal_mesh(mesh, dm, u.GeometryScriptCopyMeshFromAssetOptions(), read)
Q = u.GeometryScript_MeshQueries
pts = []
for vid in range(int(Q.get_vertex_i_d_range(dm)) if hasattr(Q, "get_vertex_i_d_range") else int(Q.get_vertex_count(dm))):
    r = Q.get_vertex_position(dm, vid)
    pos, ok = (r[0], r[1]) if isinstance(r, tuple) else (r, True)
    if ok:
        pts.append((pos.x, pos.y, pos.z))

z0, z1 = a["z_band"]
band = [p for p in pts if z0 <= p[2] <= z1]
res = {"mesh": a["mesh"], "outcome": str(outcome), "vertices": len(pts), "band_uu": [z0, z1], "band_vertices": len(band)}
if band:
    n = float(len(band))
    res["band_centroid_uu"] = [round(sum(p[i] for p in band) / n, 4) for i in range(3)]
    res["band_x_min_max_uu"] = [round(min(p[0] for p in band), 4), round(max(p[0] for p in band), 4)]
    res["band_y_min_max_uu"] = [round(min(p[1] for p in band), 4), round(max(p[1] for p in band), 4)]
xs = [p[0] for p in pts]
res["all_x_min_max_uu"] = [round(min(xs), 4), round(max(xs), 4)]
with open(a["out"], "w", encoding="utf-8") as h:
    json.dump(res, h, indent=1)
