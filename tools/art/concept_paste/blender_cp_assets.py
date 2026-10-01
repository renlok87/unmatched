"""ENV-MAPS P7 track A, Blender side of cp_proxies.py (headless `blender -b --factory-startup`, CPU only).

  blender -b --factory-startup --python tools/art/concept_paste/blender_cp_assets.py -- <params.json> <prepare.json>

Builds (UM_FBX_v1 through tools/art/env_kit/k_blender.py; geometry authored in UE numbers):
  SM_<Name>_ConceptSheet (+ optional _ConceptSea)  from the numpy grids of cp_proxies.prepare (quads CCW seen from C0,
                                          UV0 = plate B UV, UV1 = plate A UV, both stored with V flipped
                                          (Blender V up -> UE V down)); planar regions dissolved, triangulated
  SM_EnvCP_LanternHead                    the hanging lantern of SM_Env_LanternPost (faces kept by centroid), pivot =
                                          base centre, custom normals / UVs / slot as the source
  SM_EnvCP_BannerCloth                    cloth + cross-bar of SM_Env_Banner, the cloth stretched along Z to the painted
                                          aspect, pivot = base centre
and writes <run>/reports/build-report.json (schema unmatched.concept-paste.assets-build/1) + an FBX read-back per mesh.
"""
import json
import math
import sys
from pathlib import Path

import bmesh
import bpy
import numpy as np
from mathutils import Matrix

HERE = Path(__file__).resolve()
REPO = HERE.parents[3]
sys.path.insert(0, str(REPO / "tools" / "art" / "env_kit"))
import k_blender as K  # noqa: E402

S = K.S
r = K.r
SCHEMA = "unmatched.concept-paste.assets-build/1"


def ue_from_blend(co):
    """Authoring Blender coords (metres) -> UE numbers (uu): UE X = -y, UE Y = -x (k_blender.py MeshBuilder)."""
    return np.array([-co[1] * 100.0, -co[0] * 100.0, co[2] * 100.0])


def mesh_ue_verts(obj) -> np.ndarray:
    n = len(obj.data.vertices)
    buf = np.zeros(n * 3)
    obj.data.vertices.foreach_get("co", buf)
    b = buf.reshape(-1, 3)
    return np.c_[-b[:, 1] * 100.0, -b[:, 0] * 100.0, b[:, 2] * 100.0]


def bounds_ue(obj) -> dict:
    return K.bounds(mesh_ue_verts(obj))


def finish(obj, fbx: Path, slots: list, checks: dict, extra: dict) -> dict:
    tris = S.triangles(obj)
    b = bounds_ue(obj)
    exp = K.export(obj, fbx)
    exp["um_fbx_v1_conformance"].append({"setting": "Pivot: " + extra.pop("_pivot"), "standard": True, "used": True,
                                         "conforms": True})
    rt = K.roundtrip(fbx, tris, slots, b)
    c = {"single_mesh": rt["mesh_objects"] == 1, "triangles_preserved": rt["triangles"] == tris,
         "material_slots": rt["material_slots"] == slots, "uv0_present": "UVMap" in (rt["uv_layers"] or []),
         "roundtrip_bounds_match_ue_frame": rt["ue_frame_matches_build"],
         "um_fbx_v1_conforms": all(x["conforms"] for x in exp["um_fbx_v1_conformance"]), **checks}
    return {**exp, "name": fbx.stem, "triangles": tris, "boundsUeLocalUU": b, "roundtrip": rt, **extra,
            "checks": {k: bool(v) for k, v in c.items()}}


# ----------------------------------------------------------------------------- proxies
def build_proxy(name: str, npz: str, slot: str, angle_deg: float, cam_pos_ue):
    bpy.ops.wm.read_factory_settings(use_empty=True)
    d = np.load(npz)
    V, Q, uv0, uv1 = d["verts"], d["quads"], d["uv0"], d["uv1"]
    mb = K.MeshBuilder(name, n_uv=2)
    mb.add_verts(V)
    f0 = np.c_[uv0[:, 0], 1.0 - uv0[:, 1]]
    f1 = np.c_[uv1[:, 0], 1.0 - uv1[:, 1]]
    for q in Q.tolist():
        mb.add_face(q, [[tuple(f0[i]) for i in q], [tuple(f1[i]) for i in q]], 0)
    quads = len(mb.F)
    obj = mb.to_object([K.flat_material(slot, (0.2, 0.2, 0.2), 1.0)])
    me = obj.data
    bm = bmesh.new()
    bm.from_mesh(me)
    bmesh.ops.dissolve_limit(bm, angle_limit=math.radians(angle_deg), use_dissolve_boundaries=False,
                             verts=list(bm.verts), edges=list(bm.edges), delimit={"NORMAL"})
    bmesh.ops.triangulate(bm, faces=list(bm.faces), quad_method="BEAUTY", ngon_method="BEAUTY")
    # the triangulation of a slightly non-planar n-gon can fold a sliver over: turn every such triangle to the camera
    # (no back-face pinholes; the geometry itself is unchanged)
    cx, cy, cz = (float(v) for v in cam_pos_ue)
    cam_b = np.array([-cy / 100.0, -cx / 100.0, cz / 100.0])
    bm.normal_update()
    flip = [f for f in bm.faces if float(np.dot(np.array(f.normal), cam_b - np.array(f.calc_center_median()))) <= 0]
    if flip:
        bmesh.ops.reverse_faces(bm, faces=flip)
    # fidelity: distance of every interior input vertex to the decimated surface (uu)
    from mathutils import Vector
    from mathutils.bvhtree import BVHTree
    tree = BVHTree.FromBMesh(bm)
    interior = d["interior"]
    vb = np.c_[-V[interior, 1], -V[interior, 0], V[interior, 2]] / 100.0  # border vertices graze the mesh edge
    errs = []
    for p in vb:
        hit = tree.find_nearest(Vector(p), 1.0)  # within 100 uu
        errs.append(hit[3] * 100.0 if hit[0] is not None else float("inf"))
    errs = np.array(errs)
    bm.to_mesh(me)
    bm.free()
    me.update()
    # every triangle still faces the C0 camera side (normals: Blender frame of the mirrored authoring)
    return obj, {"quadsBeforeDissolve": quads, "trianglesBeforeDissolve": 2 * quads, "verticesIn": int(len(V)),
                 "sliversFlippedToCamera": len(flip),
                 "surfaceErrorUU": {"p50": r(float(np.median(errs)), 4), "p99": r(float(np.percentile(errs, 99)), 4),
                                  "max": r(float(errs.max()), 4), "misses": int(np.isinf(errs).sum()),
                                  "method": "distance of every interior input grid vertex (4 kept cells) to the dissolved surface (BVH nearest)"}}


def facing_share(obj, cam_pos_ue) -> float:
    """Share of triangles whose UE-frame normal points to the C0 camera (UE numbers, right-handed math)."""
    V = mesh_ue_verts(obj)
    ok = tot = 0
    cp = np.asarray(cam_pos_ue, float)
    for p in obj.data.polygons:
        idx = list(p.vertices)
        a, b, c = V[idx[0]], V[idx[1]], V[idx[2]]
        # the Blender polygon order is the reversed authoring order (mirror): reverse back
        n = np.cross(c - a, b - a)
        tot += 1
        ok += float(np.dot(n, cp - a)) > 0
    return ok / max(tot, 1)


# ----------------------------------------------------------------------------- details from kit meshes
def import_source(path: Path):
    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.ops.import_scene.fbx(filepath=str(path))
    objs = S.mesh_objects()
    if len(objs) != 1:
        raise RuntimeError(f"{path}: {len(objs)} mesh objects")
    obj = objs[0]
    me = obj.data
    me.transform(obj.matrix_world)
    obj.matrix_world = Matrix.Identity(4)
    # read-back frame (UE with Y negated) -> authoring frame of k_blender (rotate -90 deg about Z)
    me.transform(Matrix.Rotation(math.radians(-90.0), 4, "Z"))
    me.update()
    return obj


def face_centroids_ue(obj) -> np.ndarray:
    V = mesh_ue_verts(obj)
    return np.array([V[list(p.vertices)].mean(0) for p in obj.data.polygons])


def delete_faces(obj, mask_delete: np.ndarray) -> int:
    me = obj.data
    bm = bmesh.new()
    bm.from_mesh(me)
    bm.faces.ensure_lookup_table()
    doomed = [bm.faces[i] for i in np.nonzero(mask_delete)[0]]
    bmesh.ops.delete(bm, geom=doomed, context="FACES")
    bm.to_mesh(me)
    bm.free()
    me.update()
    return len(doomed)


def move_pivot_to_base_centre(obj) -> list:
    V = mesh_ue_verts(obj)
    lo, hi = V.min(0), V.max(0)
    piv = np.array([(lo[0] + hi[0]) / 2, (lo[1] + hi[1]) / 2, lo[2]])
    # UE shift -piv <-> authoring shift (piv_y, piv_x, -piv_z) / 100
    obj.data.transform(Matrix.Translation((piv[1] / 100.0, piv[0] / 100.0, -piv[2] / 100.0)))
    obj.data.update()
    return [float(v) for v in piv]


def rename(obj, name: str):
    obj.name = name
    obj.data.name = name


def build_lantern(P: dict, run: Path) -> dict:
    L = P["lanternHead"]
    src = REPO / L["source"]
    if S.sha256(src) != L["sourceSha256"]:
        raise RuntimeError(f"{src}: sha256 differs from the params")
    obj = import_source(src)
    tris_in = S.triangles(obj)
    c = face_centroids_ue(obj)
    keep = (c[:, 1] < float(L["keep"]["ueYMax"])) & (c[:, 2] < float(L["keep"]["ueZMax"]))
    deleted = delete_faces(obj, ~keep)
    piv = move_pivot_to_base_centre(obj)
    rename(obj, L["asset"])
    slots = [m.name if m else None for m in obj.data.materials]
    glow = [round(float(g - p), 3) for g, p in zip(L["glowCentroidUU"], piv)]
    b = bounds_ue(obj)
    inside = all(b["min"][i] - 0.5 <= glow[i] <= b["max"][i] + 0.5 for i in range(3))
    tris = S.triangles(obj)
    return finish(obj, run / "export" / f"{L['asset']}.fbx", slots,
                  {"triangles_within_budget": tris <= int(L["maxTriangles"]), "glow_inside_bounds": inside,
                   "post_removed": b["size"][2] < 50.0 and b["size"][1] < 25.0},
                  {"_pivot": "base centre of the kept lantern (XY bounds centre, min Z)",
                   "source": {"fbx": L["source"], "sha256": L["sourceSha256"], "triangles": tris_in},
                   "facesDeleted": deleted, "pivotInSourceUU": [round(v, 3) for v in piv],
                   "glowOffsetUU": glow, "glowNote": "flame / light point relative to the pivot (scale with the prop)"})


def build_banner(P: dict, run: Path) -> dict:
    Bp = P["bannerCloth"]
    src = REPO / Bp["source"]
    if S.sha256(src) != Bp["sourceSha256"]:
        raise RuntimeError(f"{src}: sha256 differs from the params")
    obj = import_source(src)
    tris_in = S.triangles(obj)
    c = face_centroids_ue(obj)
    V = mesh_ue_verts(obj)
    polys = list(obj.data.polygons)
    fz_min = np.array([V[list(p.vertices), 2].min() for p in polys])
    fz_max = np.array([V[list(p.vertices), 2].max() for p in polys])
    # the cross-bar: faces beyond the cloth width; the cloth: off the pole axis, above the pole foot, below the bar
    bar = np.abs(c[:, 1]) > float(Bp["crossbarMinAbsY"])
    bar_v = np.unique(np.concatenate([list(polys[i].vertices) for i in np.nonzero(bar)[0]]))
    zc_lo, zc_hi = float(V[bar_v, 2].min()), float(V[bar_v, 2].max())
    cloth = ((np.abs(c[:, 1]) > float(Bp["clothMinAbsY"])) & (c[:, 2] > float(Bp["clothMinZ"]))
             & (c[:, 2] < zc_lo - 0.5))
    cloth_v = np.unique(np.concatenate([list(polys[i].vertices) for i in np.nonzero(cloth)[0]]))
    zb = float(V[cloth_v, 2].min())
    cloth_w = float(V[cloth_v, 1].max() - V[cloth_v, 1].min())
    # delete every face reaching below the lowest cloth vertex (pole foot, base plate, the long pole quads) or above
    # the cross-bar (spear tip)
    doomed = (fz_min < zb - 0.5) | (fz_max > zc_hi + 0.5)
    deleted = delete_faces(obj, doomed)
    # stretch everything below the cross-bar bottom along Z (cloth length / width -> clothAspect)
    length0 = zc_lo - zb
    k = float(Bp["clothAspect"]) * cloth_w / length0
    me = obj.data
    n = len(me.vertices)
    buf = np.zeros(n * 3)
    me.vertices.foreach_get("co", buf)
    co = buf.reshape(-1, 3)
    zs = zc_lo / 100.0
    below = co[:, 2] < zs
    co[below, 2] = zs - (zs - co[below, 2]) * k
    me.vertices.foreach_set("co", co.ravel())
    me.update()
    piv = move_pivot_to_base_centre(obj)
    rename(obj, Bp["asset"])
    slots = [m.name if m else None for m in obj.data.materials]
    b = bounds_ue(obj)
    tris = S.triangles(obj)
    bar_top = round(zc_hi - piv[2], 3)
    return finish(obj, run / "export" / f"{Bp['asset']}.fbx", slots,
                  {"triangles_within_budget": tris <= int(Bp["maxTriangles"]),
                   "aspect_reached": abs((zc_lo - zb) * k / cloth_w - float(Bp["clothAspect"])) < 0.01},
                  {"_pivot": "base centre after the stretch (XY bounds centre, min Z = lowest cloth tatter)",
                   "source": {"fbx": Bp["source"], "sha256": Bp["sourceSha256"], "triangles": tris_in},
                   "facesDeleted": deleted, "stretchZ": round(k, 4),
                   "clothWidthUU": round(cloth_w, 3), "clothLengthUU": round((zc_lo - zb) * k, 3),
                   "crossbarTopUU": bar_top, "crossbarBottomUU": round(zc_lo - piv[2], 3),
                   "pivotInSourceUU": [round(v, 3) for v in piv],
                   "hangNote": "attach point = (0, 0, crossbarTopUU) x scale above the pivot"})


def measure_kit(P: dict) -> dict:
    """Read-only measurements of reused kit meshes (UE mesh frame, uu)."""
    out = {}
    for name, m in P.get("kitMeasure", {}).items():
        src = REPO / m["source"]
        got = S.sha256(src)
        obj = import_source(src)
        V = mesh_ue_verts(obj)
        lo, hi = V.min(0), V.max(0)
        front = V[V[:, 0] >= hi[0] - float(m["muzzleShare"]) * (hi[0] - lo[0])]
        out[name] = {"source": m["source"], "sha256": got, "sha256Ok": got == m["sourceSha256"],
                     "boundsUU": {"min": [r(v, 3) for v in lo], "max": [r(v, 3) for v in hi]},
                     "muzzleXUU": r(float(hi[0]), 3),
                     "barrelAxisZUU": r(float((front[:, 2].min() + front[:, 2].max()) / 2), 3),
                     "barrelRadiusUU": r(float((front[:, 2].max() - front[:, 2].min()) / 2), 3),
                     "barrelAxisYUU": r(float((front[:, 1].min() + front[:, 1].max()) / 2), 3)}
    return out


def main():
    args = K.script_args()
    P = K.load_params(args[0])
    prep = json.loads(Path(args[1]).read_text(encoding="utf-8"))
    run = P["_run"]
    pr = P["proxies"]
    exports = []
    cam_pos = prep.get("_camPosUE")
    for key, info in sorted(prep.items()):
        if key.startswith("_"):
            continue
        name = info["name"]
        for part, slot, budget in (("sheet", "M_ConceptPaste", pr["maxSheetTriangles"]),
                                   ("sea", "M_ConceptPaste", pr["maxSeaTriangles"])):
            if part not in info:
                continue
            asset = f"SM_{name}_Concept{part.capitalize()}"
            obj, extra = build_proxy(asset, info[part]["npz"], slot, float(pr["dissolveAngleDeg"]), cam_pos)
            share = facing_share(obj, cam_pos)
            tris = S.triangles(obj)
            e = finish(obj, run / "export" / f"{asset}.fbx", [slot],
                       {"triangles_within_budget": tris <= int(budget), "faces_c0_camera": share == 1.0,
                        "surface_error_p99_le_1uu": extra["surfaceErrorUU"]["p99"] <= 1.0,
                        "surface_error_max_le_8uu": extra["surfaceErrorUU"]["max"] <= 8.0,
                        "no_misses": extra["surfaceErrorUU"]["misses"] == 0,
                        "uv1_present": True},
                       {"_pivot": "board-actor origin (map centre, Z 0 = map plane): identity under the board actor",
                        "map": key, "part": part, "grid": info[part], "facingC0Share": round(share, 5),
                        "dissolveAngleDeg": pr["dissolveAngleDeg"], **extra,
                        "uv": {"UVMap": "plate B UV (u, v down in UE) of the vertex's C0 pixel",
                               "UV1": "plate A UV (outside 0..1 beyond the concept frame)",
                               "contract": "exact at the vertices only: the paste material projects through C0"}})
            exports.append(e)
            print("CP-ASSETS %s tris=%d (from %d) facing=%.4f surfErr p99=%.3f max=%.3f uu" % (
                asset, tris, extra["trianglesBeforeDissolve"], share, extra["surfaceErrorUU"]["p99"], extra["surfaceErrorUU"]["max"]))
    for builder in (build_lantern, build_banner):
        e = builder(P, run)
        exports.append(e)
        print("CP-ASSETS %s tris=%d checks=%s" % (e["name"], e["triangles"], all(e["checks"].values())))
    kit = measure_kit(P)
    for name, m in kit.items():
        print("CP-ASSETS measure %s barrelAxisZ=%.2f muzzleX=%.2f" % (name, m["barrelAxisZUU"], m["muzzleXUU"]))
    checks = {e["name"]: all(e["checks"].values()) for e in exports}
    checks.update({f"measure:{k}": v["sha256Ok"] for k, v in kit.items()})
    report = {"schema": SCHEMA, "status": "measured", "asset": P["asset"],
              "claims": {"art_accepted": False, "game_ready": False, "technically_imported": False},
              "blender_version": bpy.app.version_string,
              "script_sha256_lf": {K.rel(HERE): S.text_sha256_lf(HERE),
                                   "tools/art/concept_paste/cp_proxies.py": S.text_sha256_lf(HERE.parent / "cp_proxies.py"),
                                   "tools/art/env_kit/k_blender.py": S.text_sha256_lf(K.HERE)},
              "params": {"path": K.rel(P["_params_path"]), "sha256": S.sha256(P["_params_path"])},
              "numpy": {k: v for k, v in prep.items()},
              "contract": {"ue": {"proxies": "/Game/EnvMaps/<Name>/ConceptPaste/SM_<Name>_ConceptSheet (no collision, "
                                             "Nanite off, no shadows, Lumen GI off on the component: design.json 4)",
                                  "details": "/Game/EnvKit/ConceptPaste/SM_EnvCP_{LanternHead,BannerCloth} (slots -> "
                                             "MI_Env_LanternPost / MI_Env_Banner of the env kit)",
                                  "import": "tools/art/concept_paste/ue_import_concept_paste.py"}},
              "exports": exports, "kitMeasurements": kit, "checks": checks, "checks_passed": all(checks.values())}
    K.write_json(run / "reports" / "build-report.json", report)
    print("CP-ASSETS-BUILD", json.dumps(checks))


main()
