"""ENV-MAPS P7 track A, Blender side of cp_proxies.py (headless `blender -b --factory-startup`, CPU only).

  blender -b --factory-startup --python tools/art/concept_paste/blender_cp_assets.py -- <params.json> <prepare.json>
  blender -b --factory-startup --python tools/art/concept_paste/blender_cp_assets.py -- <params.json> - --only banner
      (P7c: rebuild only these details and patch their entries into the existing build report)

Builds (UM_FBX_v1 through tools/art/env_kit/k_blender.py; geometry authored in UE numbers):
  SM_<Name>_ConceptSheet (+ optional _ConceptSea)  from the numpy grids of cp_proxies.prepare (quads CCW seen from C0,
                                          UV0 = plate B UV, UV1 = plate A UV, both stored with V flipped
                                          (Blender V up -> UE V down)); planar regions dissolved, triangulated
  SM_EnvCP_LanternHead                    the hanging lantern of SM_Env_LanternPost (faces kept by centroid), pivot =
                                          base centre, custom normals / UVs / slot as the source
  SM_EnvCP_BannerCloth                    P7c: a procedural cloth grid (aspect 4.0 of the painted banner, folds, toothed
                                          hem, UV0 for the sigil / wind of M_EnvCP_Banner) + a rod, pivot = base centre
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
    """P7c: a procedural hanging banner (the painted one: a long crimson cloth on a rail with a pale hexagram).

    Why not the kit SM_Env_Banner any more (P7b): the painted cloth is 81 x 325 uu (aspect 4.0, design.json 5_elements),
    the kit cloth 2.46 - a 1.6x Z stretch smears its Tripo texture; the Tripo atlas UVs cannot carry the painted sigil;
    the WPO wind needs the hang height. Here: a cloth grid (UV0 u across, v 0 at the rail .. 1 at the hem, UE V down),
    gentle folds growing to the hem, gathered top, a toothed hem, and a thin rod (UV v < 0: the material paints it as
    the rod and keeps it still). UE mesh frame: front +X, width Y, up Z; pivot = base centre (XY bounds centre, min Z).
    """
    Bp = P["bannerCloth"]
    bpy.ops.wm.read_factory_settings(use_empty=True)
    W, L = float(Bp["widthUU"]), float(Bp["lengthUU"])
    nu, nv = int(Bp["gridU"]), int(Bp["gridV"])
    fold_a, folds, curl = float(Bp["foldAmpUU"]), float(Bp["folds"]), float(Bp["curlUU"])
    gather = float(Bp["gatherTop"])
    # the hang direction of the cloth in the mesh frame (unit; default straight down). P7c: the C0 screen-down
    # direction in the yaw frame of the overlay (cp_layout.banner_hang_local), so the cloth hangs straight down in the
    # concept view as painted, its top edge along the rail (a sheared panel); cp_layout --check verifies the numbers
    hang = np.array(Bp.get("hangLocal", [0.0, 0.0, -1.0]), float)
    hang /= np.linalg.norm(hang)
    nrm = np.cross(np.array([0.0, 1.0, 0.0]), hang)  # the cloth normal (folds), towards +X for a downward hang
    nrm /= np.linalg.norm(nrm)
    tat, teeth = float(Bp["tatterUU"]), int(Bp["tatterTeeth"])
    rod_r, rod_over, rod_clear = float(Bp["rodRadiusUU"]), float(Bp["rodOverhangUU"]), float(Bp["rodClearUU"])
    top = L  # the cloth top (before the pivot shift), the hem near Z 0
    rng = np.random.default_rng(int(Bp.get("seed", 7)))
    jit = rng.uniform(0.35, 1.0, size=nu + 1)

    def hem_lift(u: float, i: int) -> float:
        # toothed hem: a triangle wave of `teeth` teeth x a fixed per-column jitter (deterministic seed)
        t = abs(((u * teeth) % 1.0) - 0.5) * 2.0
        return tat * t * jit[i]

    mb = K.MeshBuilder(Bp["asset"], n_uv=1)
    grid = np.zeros((nv + 1, nu + 1), dtype=int)
    uvs = {}
    for j in range(nv + 1):
        v = j / nv
        width_k = gather + (1.0 - gather) * min(1.0, v / 0.12)
        for i in range(nu + 1):
            u = i / nu
            y = (u - 0.5) * W * width_k
            dl = v * L  # distance down the cloth from the rail
            if j == nv:
                dl -= hem_lift(u, i)
            elif j == nv - 1:
                dl -= 0.35 * hem_lift(u, i)
            vv = dl / L
            off = fold_a * (0.35 + 0.65 * vv) * math.sin(2.0 * math.pi * folds * u + 0.7) + curl * vv * vv
            pos = np.array([0.0, y, top]) + dl * hang + off * nrm
            grid[j, i] = mb.add_verts([tuple(float(c) for c in pos)])
            uvs[int(grid[j, i])] = (u, 1.0 - vv)  # Blender V up (UE V down after the FBX)
    for j in range(nv):
        for i in range(nu):
            q = [int(grid[j + 1, i]), int(grid[j + 1, i + 1]), int(grid[j, i + 1]), int(grid[j, i])]  # CCW seen from +X
            mb.add_face(q, [uvs[k] for k in q], 0)
    # the rod: an 8-sided cylinder along Y above the cloth (UV v < 0 -> the material's rod colour, no wind)
    sides = 8
    zc = top + rod_clear + rod_r
    y0, y1 = -W / 2 - rod_over, W / 2 + rod_over
    ring0, ring1 = [], []
    for k in range(sides):
        a = 2.0 * math.pi * k / sides
        x, z = rod_r * math.cos(a), zc + rod_r * math.sin(a)
        ring0.append(mb.add_verts([(x, y0, z)]))
        ring1.append(mb.add_verts([(x, y1, z)]))
    for k in range(sides):
        k2 = (k + 1) % sides
        q = [ring0[k], ring0[k2], ring1[k2], ring1[k]]
        mb.add_face(q, [(0.0, 1.06), (0.0, 1.04), (1.0, 1.04), (1.0, 1.06)], 0)
    mb.add_face(list(reversed(ring0)), [(0.5, 1.05)] * sides, 0)
    mb.add_face(ring1, [(0.5, 1.05)] * sides, 0)
    # pivot: base centre
    V = mb.verts()
    lo, hi = V.min(0), V.max(0)
    piv = np.array([(lo[0] + hi[0]) / 2.0, (lo[1] + hi[1]) / 2.0, lo[2]])
    mb.V = [tuple(float(c) for c in (np.array(v) - piv)) for v in mb.V]
    obj = mb.to_object([K.flat_material(Bp["slot"], (0.35, 0.03, 0.025), 0.85)])
    for poly in obj.data.polygons:
        poly.use_smooth = True
    obj.data.update()
    slots = [m.name if m else None for m in obj.data.materials]
    tris = S.triangles(obj)
    cloth_len = float(top - piv[2])  # rail to the lowest hem point (Z)
    bar_top = round(float(zc + rod_r - piv[2]), 3)
    aspect = L / W
    return finish(obj, run / "export" / f"{Bp['asset']}.fbx", slots,
                  {"triangles_within_budget": tris <= int(Bp["maxTriangles"]),
                   "aspect_reached": abs(aspect - float(Bp["clothAspect"])) < 0.01},
                  {"_pivot": "base centre (XY bounds centre, min Z = the lowest hem tooth)",
                   "source": {"procedural": True, "params": "bannerCloth (cp-assets-params.json)"},
                   "clothWidthUU": round(W, 3), "clothLengthUU": round(L, 3), "clothLengthToHemUU": round(cloth_len, 3),
                   "hangLocal": [round(float(c), 4) for c in hang],
                   "crossbarTopUU": bar_top, "crossbarBottomUU": round(float(zc - rod_r - piv[2]), 3),
                   "crossbarXUU": round(float(-piv[0]), 3), "crossbarYUU": round(float(-piv[1]), 3),
                   "clothTopUU": round(float(top - piv[2]), 3), "pivotShiftUU": [round(float(v), 3) for v in piv],
                   "uv": {"UVMap": "u across the cloth, v 0 at the rail .. 1 at the hem (UE V down); the rod v 1.04..1.06 "
                                   "in Blender = -0.06..-0.04 in UE"},
                   "hangNote": "attach point = (crossbarXUU, crossbarYUU, crossbarTopUU) x scale from the pivot (the "
                               "sheared hang moves the bounds centre off the rail)"})


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


def main_only(P: dict, only: list) -> None:
    """P7c: rebuild only the named detail builders (lantern / banner) and patch their entries into the existing
    build-report.json (the depth sheets, their FBX bytes and the numpy prepare are left as they are)."""
    run = P["_run"]
    path = run / "reports" / "build-report.json"
    report = json.loads(path.read_text(encoding="utf-8"))
    builders = {"lantern": build_lantern, "banner": build_banner}
    for key in only:
        e = builders[key](P, run)
        report["exports"] = [x for x in report["exports"] if x["name"] != e["name"]] + [e]
        print("CP-ASSETS %s tris=%d checks=%s" % (e["name"], e["triangles"], all(e["checks"].values())))
    checks = {e["name"]: all(e["checks"].values()) for e in report["exports"]}
    checks.update({f"measure:{k}": v["sha256Ok"] for k, v in report.get("kitMeasurements", {}).items()})
    report["checks"] = checks
    report["checks_passed"] = all(checks.values())
    report["script_sha256_lf"][K.rel(HERE)] = S.text_sha256_lf(HERE)
    report["params"] = {"path": K.rel(P["_params_path"]), "sha256": S.sha256(P["_params_path"])}
    report["partialRebuilds"] = sorted(set(report.get("partialRebuilds", [])) | {f"{k} (P7c --only)" for k in only})
    K.write_json(path, report)
    print("CP-ASSETS-BUILD", json.dumps(checks))


def main():
    args = K.script_args()
    P = K.load_params(args[0])
    if "--only" in args:
        main_only(P, [x.strip() for x in args[args.index("--only") + 1].split(",") if x.strip()])
        return
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
