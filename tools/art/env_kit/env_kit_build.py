"""ENV kit: Tripo GLB -> UE-ready static prop (UM_FBX_v1). Headless Blender, CPU only, no renders.

Run from the repository root (never touches a live Blender session):
  blender -b --factory-startup --python-exit-code 1 --python tools/art/env_kit/env_kit_build.py -- \
      <params.json> <ASSET-ID> [--probe]

  --probe  import + join + apply only, then dump per-triangle data (positions, normals, areas, base colour samples)
           to <scratch_dir>/probe/<ASSET-ID>.npz for tools/art/env_kit/orientation_check.py; nothing is exported.
  default  full build: orientation (yaw from reports/orientation-check.json or params), uniform scale to the
           target dimension, pivot at base centre, BC/N/ORM 2K, one material slot, UV analysis, geometry
           diagnostics (reported, never repaired), UM_FBX_v1 export, round trip in an empty scene.

Reuse (not a re-implementation): every mesh/texture/FBX helper comes from
tools/tripo-pipeline/blender/static_prop_candidate.py (the barrel and lantern pipeline). Its source is executed
without the trailing main() call, so the same functions run with the same numbers: glTF base colour factor in
linear light, normal map padding + OpenGL->DirectX green flip, PNG colour chunks stripped from N/ORM,
UM_FBX_v1 export (+90 deg Z, x100 data, FBX_SCALE_UNITS, UnitScaleFactor patched to 1.0, deterministic bytes),
UV raster metrics, conformance rows. What this wrapper does differently and why:
  - no render_previews (Eevee) and no bake_ao (Cycles): no GPU/Cycles work while GPU measurements run; ORM.R = 1.0
    (Tripo delivers no occlusion map). bake_ao can be switched on in params later (still CPU Cycles);
  - no clean_mesh / repair_cracks / fix_winding: geometry is kept exactly as Tripo delivered it; problems are
    measured and reported (shells, gaps, open-edge loops, non-manifold edges, winding, inverted shells);
  - orientation can be turned by a multiple of 90 deg about Z (decided by the silhouette check, see README);
  - the target can be height, length (largest horizontal extent) or diameter (same measure);
  - outputs follow the ENV kit contract: export/SM_Env_<Name>.fbx, export/T_Env_<Name>_{BC,N,ORM}.png,
    reports/assets/SM_Env_<Name>.build.json; the .blend and UV layout go to the scratch folder (not in git).

Axes (UM_FBX_v1, 04 section 1): the asset front (Tripo "front" reference view = glTF +Z = .blend -Y) becomes +X in
UE. On the board the K1 camera looks along -Y (yaw -90), so an actor yaw of +90 turns the front to the camera
(same as the hero figures in tools/tripo-pipeline/review/control_scene.py).
"""

import hashlib
import json
import math
import sys
from pathlib import Path

import bmesh
import bpy
import numpy as np
from mathutils import Matrix, Vector
from mathutils.kdtree import KDTree

HERE = Path(__file__).resolve()
REPO = HERE.parents[3]  # <repo>/tools/art/env_kit/<this file>
SPC_PATH = REPO / "tools" / "tripo-pipeline" / "blender" / "static_prop_candidate.py"


def load_spc():
    """Execute static_prop_candidate.py without its trailing main() call and return its namespace."""
    src = SPC_PATH.read_text(encoding="utf-8")
    body = src.rstrip()
    if not body.endswith("main()"):
        raise RuntimeError("static_prop_candidate.py no longer ends with main(); update load_spc")
    body = body[: body.rfind("main()")]
    ns = {"__file__": str(SPC_PATH), "__name__": "static_prop_candidate"}
    exec(compile(body, str(SPC_PATH), "exec"), ns)
    return ns


SPC = load_spc()
r = SPC["r"]
sha256 = SPC["sha256"]
text_sha256_lf = SPC["text_sha256_lf"]
world_bounds = SPC["world_bounds"]
triangles = SPC["triangles"]
mesh_objects = SPC["mesh_objects"]


def rel(path):
    try:
        return Path(path).resolve().relative_to(REPO).as_posix()
    except ValueError:
        return Path(path).as_posix()


def load_params():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    if len(argv) < 2:
        raise SystemExit("usage: -- <params.json> <ASSET-ID> [--probe]")
    params_path = Path(argv[0]).resolve()
    P = json.loads(params_path.read_text(encoding="utf-8"))
    P["_params_path"] = params_path
    aid = argv[1]
    if aid not in P["assets"]:
        raise SystemExit("unknown asset %s (params has %s)" % (aid, sorted(P["assets"])))
    P["_run_dir"] = (REPO / P["run_dir"]).resolve()
    P["_scratch"] = Path(P["scratch_dir"]).resolve()
    P["_preset"] = (REPO / P["fbx_preset"]).resolve()
    return P, aid, "--probe" in argv[2:]


# ----------------------------------------------------------------------------- import
def import_joined(src):
    """Fresh empty scene, glTF import, single mesh object with transforms applied (as static_prop_candidate)."""
    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.ops.import_scene.gltf(filepath=str(src))
    meshes = mesh_objects()
    lo, hi = world_bounds(meshes)
    imp = {
        "mesh_objects": len(meshes),
        "faces": sum(len(o.data.polygons) for o in meshes),
        "triangles": sum(triangles(o) for o in meshes),
        "materials": sorted({m.name for o in meshes for m in o.data.materials if m}),
        "images": [{"name": i.name, "size": list(i.size), "colorspace": i.colorspace_settings.name}
                   for i in bpy.data.images if i.size[0]],
        "bounds_min_m": [r(v) for v in lo], "bounds_max_m": [r(v) for v in hi],
        "dimensions_m": [r(v) for v in (hi - lo)],
    }
    for o in list(bpy.context.scene.objects):
        if o.type != "MESH":
            bpy.data.objects.remove(o)
    obj = meshes[0]
    if len(meshes) > 1:
        with bpy.context.temp_override(active_object=obj, selected_editable_objects=meshes):
            bpy.ops.object.join()
    obj.parent = None
    obj.data.transform(obj.matrix_world)
    obj.matrix_world = Matrix.Identity(4)
    return obj, imp


def bc_source_pixels(glb):
    names = SPC["gltf_images"](glb)
    img = SPC["find_image"](names["basecolor"])
    return SPC["image_array"](img)[..., :3], names


# ----------------------------------------------------------------------------- probe
def probe(P, aid, src):
    obj, imp = import_joined(src)
    glb = SPC["glb_json"](src)
    bc, _names = bc_source_pixels(glb)
    h, w = bc.shape[:2]
    me = obj.data
    me.calc_loop_triangles()
    tris = me.loop_triangles
    n = len(tris)
    pos = np.empty((n, 3, 3), dtype=np.float64)
    uv = np.empty((n, 3, 2), dtype=np.float64)
    nrm = np.empty((n, 3), dtype=np.float64)
    area = np.empty(n, dtype=np.float64)
    uvl = me.uv_layers[0].data
    for i, t in enumerate(tris):
        pos[i] = [me.vertices[v].co[:] for v in t.vertices]
        uv[i] = [uvl[l].uv[:] for l in t.loops]
        nrm[i] = t.normal[:]
        area[i] = t.area
    bary = np.array([[1 / 3, 1 / 3, 1 / 3], [0.6, 0.2, 0.2], [0.2, 0.6, 0.2], [0.2, 0.2, 0.6]])
    samples = np.einsum("sk,tkc->tsc", bary, uv)  # (n, 4, 2)
    xs = np.clip((samples[..., 0] % 1.0 * w).astype(int), 0, w - 1)
    ys = np.clip((samples[..., 1] % 1.0 * h).astype(int), 0, h - 1)
    colour = bc[ys, xs].mean(1)  # encoded sRGB 0..1, factor not applied (relative comparison only)
    out = P["_scratch"] / "probe"
    out.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(out / ("%s.npz" % aid), pos=pos, nrm=nrm, area=area, colour=colour)
    (out / ("%s.json" % aid)).write_text(json.dumps({"asset": aid, "source_sha256": sha256(src), "import": imp,
                                                     "triangles": n}, indent=2) + "\n", encoding="utf-8")
    print("PROBE_OK", aid, n)


# ----------------------------------------------------------------------------- diagnostics (measure, never repair)
def shell_hole_stats(obj, uu_per_unit, gap_tol_uu):
    """Connected shells (welded 1e-6 m), gaps between shells, open-edge loops (holes), inverted shells."""
    bm = bmesh.new()
    bm.from_mesh(obj.data)
    bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=1e-6)
    bm.verts.ensure_lookup_table()
    bm.faces.ensure_lookup_table()
    bm.verts.index_update()
    bm.faces.index_update()
    parent = list(range(len(bm.faces)))

    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    for e in bm.edges:
        fs = e.link_faces
        for f in fs[1:]:
            a, b = find(fs[0].index), find(f.index)
            if a != b:
                parent[a] = b
    shell_of_face = [find(i) for i in range(len(bm.faces))]
    ids = {s: k for k, s in enumerate(sorted(set(shell_of_face), key=lambda s: -shell_of_face.count(s)))}
    shell_of_face = [ids[s] for s in shell_of_face]
    n_sh = len(ids)
    shell_of_vert = [-1] * len(bm.verts)
    for f in bm.faces:
        for v in f.verts:
            shell_of_vert[v.index] = shell_of_face[f.index]
    shells = []
    for k in range(n_sh):
        shells.append({"faces": 0, "triangles": 0, "area_uu2": 0.0, "signed_volume_uu3": 0.0,
                       "lo": [1e30] * 3, "hi": [-1e30] * 3, "open_edges": 0})
    for f in bm.faces:
        s = shells[shell_of_face[f.index]]
        s["faces"] += 1
        s["triangles"] += len(f.verts) - 2
        s["area_uu2"] += f.calc_area() * uu_per_unit ** 2
        vs = [v.co for v in f.verts]
        for i in range(1, len(vs) - 1):
            s["signed_volume_uu3"] += vs[0].dot(vs[i].cross(vs[i + 1])) / 6.0 * uu_per_unit ** 3
        for v in vs:
            for a in range(3):
                s["lo"][a] = min(s["lo"][a], v[a] * uu_per_unit)
                s["hi"][a] = max(s["hi"][a], v[a] * uu_per_unit)
    for e in bm.edges:
        if e.is_boundary:
            shells[shell_of_face[e.link_faces[0].index]]["open_edges"] += 1
    # nearest vertex of another shell
    gaps = [None] * n_sh
    if n_sh > 1:
        kd = KDTree(len(bm.verts))
        for v in bm.verts:
            kd.insert(v.co, v.index)
        kd.balance()
        best = [math.inf] * n_sh
        for v in bm.verts:
            s = shell_of_vert[v.index]
            if s < 0:
                continue
            hit = None
            for _co, idx, dist in kd.find_n(v.co, 12):
                if shell_of_vert[idx] not in (s, -1):
                    hit = dist
                    break
            if hit is None:
                _co, idx, dist = kd.find(v.co, filter=lambda i, s=s: shell_of_vert[i] not in (s, -1))
                hit = dist if idx is not None else math.inf
            if hit < best[s]:
                best[s] = hit
        gaps = [b * uu_per_unit for b in best]
    zmin_all = min(s["lo"][2] for s in shells)
    out = []
    for k, s in enumerate(shells):
        rec = {"shell": k, "faces": s["faces"], "triangles": s["triangles"], "area_uu2": r(s["area_uu2"], 2),
               "signed_volume_uu3": r(s["signed_volume_uu3"], 2), "open_edges": s["open_edges"],
               "bounds_min_uu_prescale_frame": [r(v, 2) for v in s["lo"]],
               "bounds_max_uu_prescale_frame": [r(v, 2) for v in s["hi"]],
               "gap_to_nearest_other_shell_uu": r(gaps[k], 3) if gaps[k] is not None else None}
        rec["isolated"] = gaps[k] is not None and gaps[k] > gap_tol_uu
        rec["off_ground_uu"] = r(s["lo"][2] - zmin_all, 2)
        rec["inverted_if_closed"] = s["open_edges"] == 0 and s["signed_volume_uu3"] < 0
        out.append(rec)
    # open-edge loops (holes)
    bedges = [e for e in bm.edges if e.is_boundary]
    vparent = {}

    def vfind(x):
        while vparent[x] != x:
            vparent[x] = vparent[vparent[x]]
            x = vparent[x]
        return x

    for e in bedges:
        for v in e.verts:
            vparent.setdefault(v.index, v.index)
        a, b = vfind(e.verts[0].index), vfind(e.verts[1].index)
        if a != b:
            vparent[a] = b
    loops = {}
    for e in bedges:
        k = vfind(e.verts[0].index)
        L = loops.setdefault(k, {"edges": 0, "length_uu": 0.0, "centre": Vector((0, 0, 0)), "shell": None,
                                 "elist": []})
        L["edges"] += 1
        L["length_uu"] += e.calc_length() * uu_per_unit
        L["centre"] += (e.verts[0].co + e.verts[1].co) / 2
        L["shell"] = shell_of_face[e.link_faces[0].index]
        L["elist"].append(e)

    def loop_area(elist, centre):
        """Spanned area of an open-edge loop (uu2): Newell vector over the boundary edges, each directed opposite
        to its face's winding (the hole is walked with the surface on the right). Valid for any set of closed
        directed cycles, simple or not; the two sides of a zero-width crack run in opposite directions and
        cancel. Coordinates are taken relative to the loop centre to keep the sum origin-independent."""
        acc = Vector((0.0, 0.0, 0.0))
        for e in elist:
            f = e.link_faces[0]
            for l in f.loops:
                if l.edge is e:
                    a, b = l.link_loop_next.vert.co - centre, l.vert.co - centre
                    acc += a.cross(b)
                    break
        return acc.length / 2 * uu_per_unit ** 2

    crack_width_uu = 0.1  # mean width 2A/P at or below 1 mm: invisible at board distance
    hole_list = []
    for L in loops.values():
        centre = L["centre"] / L["edges"]
        area = loop_area(L["elist"], centre)
        per = L["length_uu"]
        mean_w = 2 * area / per if per > 0 else 0.0
        hole_list.append({"edges": L["edges"], "length_uu": r(per, 2), "shell": L["shell"],
                          "area_uu2": r(area, 3), "mean_width_2A_over_P_uu": r(mean_w, 4),
                          "compactness_4piA_over_P2": r(4 * math.pi * area / per ** 2, 4) if per > 0 else None,
                          "kind": ("crack (zero-width T-junction/sliver)" if mean_w <= crack_width_uu else "hole"),
                          "centre_uu_prescale_frame": [r(c * uu_per_unit, 2) for c in centre]})
    hole_list.sort(key=lambda x: -x["length_uu"])
    holes_true = sorted((h for h in hole_list if h["kind"] == "hole"), key=lambda x: -x["area_uu2"])
    non_manifold = sum(1 for e in bm.edges if not e.is_manifold and not e.is_boundary)
    bm.free()
    return {
        "weld_m_prescale": 1e-6,
        "shells": len(out),
        "shells_isolated_gap_gt_uu": gap_tol_uu,
        "shells_isolated": sum(1 for s in out if s["isolated"]),
        "shells_isolated_off_ground": sum(1 for s in out if s["isolated"] and s["off_ground_uu"] > gap_tol_uu),
        "shells_inverted_closed": sum(1 for s in out if s["inverted_if_closed"]),
        "shell_list_top20_by_faces": out[:20],
        "open_edge_loops": len(hole_list),
        "open_edges": len(bedges),
        "open_edge_loops_by_kind": {k: sum(1 for h in hole_list if h["kind"] == k)
                                    for k in ("crack (zero-width T-junction/sliver)", "hole")},
        "crack_rule": "mean width 2A/P <= %.2f uu (A = Newell area of the directed loop, P = rim length)" % crack_width_uu,
        "open_edge_loops_top10_by_length": hole_list[:10],
        "holes_top10_by_area": holes_true[:10],
        "hole_area_uu2_total": r(sum(h["area_uu2"] for h in holes_true), 3),
        "non_manifold_edges": non_manifold,
    }


def facing_stats(obj, uu_per_unit):
    """Which way does each face really point? Ray escape test (BVH ray casts on the CPU, no renderer):
    from the face centre, 7 rays in a 50 deg cone around +normal and 7 around -normal; a ray 'escapes' when it
    hits nothing. outward = the +normal side escapes at least as often as the -normal side (and >= 2/7);
    inward (flipped: a one-sided material culls it from outside) = the -normal side escapes >= 2/7 more rays than
    the +normal side; sheet = both sides escape >= 4/7 (thin open card, seen from both sides); enclosed = both
    sides escape < 2/7 (inside other geometry). Robust on open and non-manifold meshes, unlike recalc_face_normals."""
    from mathutils.bvhtree import BVHTree
    me = obj.data
    verts = [v.co.copy() for v in me.vertices]
    polys = [tuple(p.vertices) for p in me.polygons]
    bvh = BVHTree.FromPolygons(verts, polys, all_triangles=False, epsilon=0.0)
    lo, hi = world_bounds([obj])
    eps = max((hi - lo).length, 1e-6) * 1e-5
    ca, sa = math.cos(math.radians(50)), math.sin(math.radians(50))
    ring = [(math.cos(k * math.pi / 3), math.sin(k * math.pi / 3)) for k in range(6)]
    cls = {"outward": [0, 0.0], "inward": [0, 0.0], "sheet": [0, 0.0], "enclosed": [0, 0.0]}
    inward_centres = []
    for p in me.polygons:
        n = p.normal
        if n.length < 0.5:
            continue
        t = n.orthogonal().normalized()
        b = n.cross(t)
        c = p.center
        esc = []
        for sgn in (1.0, -1.0):
            m = n * sgn
            dirs = [m] + [(m * ca + (t * x + b * y) * sa).normalized() for x, y in ring]
            e = 0
            for d in dirs:
                hit = bvh.ray_cast(c + d * eps, d)
                if hit[0] is None:
                    e += 1
            esc.append(e)
        ep, em = esc
        if ep >= 4 and em >= 4:
            k = "sheet"
        elif em - ep >= 2 and em >= 2:
            k = "inward"
        elif ep >= 2 and ep >= em:
            k = "outward"
        elif ep < 2 and em < 2:
            k = "enclosed"
        else:
            k = "outward" if ep >= em else "inward"
        cls[k][0] += 1
        cls[k][1] += p.area
        if k == "inward" and len(inward_centres) < 12:
            inward_centres.append([r(v * uu_per_unit, 2) for v in c])
    total = sum(v[1] for v in cls.values()) or 1.0
    return {
        "method": "7+7 ray escape per face (50 deg cone), BVH ray cast, CPU; see facing_stats docstring",
        "faces": {k: v[0] for k, v in cls.items()},
        "area_fraction": {k: r(v[1] / total, 4) for k, v in cls.items()},
        "inward_face_centres_uu_prescale_frame_first12": inward_centres,
    }


# ----------------------------------------------------------------------------- textures (as static_prop_candidate.main)
def make_textures(P, glb, tex_dir, prefix, size):
    names = SPC["gltf_images"](glb)
    bc_img = SPC["find_image"](names["basecolor"])
    mr_img = SPC["find_image"](names["metallic_roughness"])
    n_img = SPC["find_image"](names["normal"])
    src_size = bc_img.size[0]
    factor = src_size // size
    if src_size % size or any(i.size[0] != src_size for i in (mr_img, n_img)):
        raise RuntimeError("texture sizes not an integer multiple of target: %s" % src_size)
    image_array, srgb_to_lin, lin_to_srgb = SPC["image_array"], SPC["srgb_to_lin"], SPC["lin_to_srgb"]
    box_down, dilate_into, save_png = SPC["box_down"], SPC["dilate_into"], SPC["save_png"]
    bc = image_array(bc_img)[..., :3]
    bc_lin = srgb_to_lin(bc) if bc_img.colorspace_settings.name == "sRGB" else bc
    bc_factor = [float(v) for v in names["factors"]["basecolor"][:3]]
    bc_factor_applied = any(f != 1.0 for f in bc_factor)
    if bc_factor_applied:
        bc_lin = bc_lin * np.array(bc_factor, dtype=bc_lin.dtype)
    bc_out = lin_to_srgb(box_down(bc_lin, factor))
    n_raw = image_array(n_img)[..., :3]
    n_len = np.linalg.norm(n_raw * 2 - 1, axis=2)
    n_bg = (n_raw[..., 2] < 0.5) | (n_len < 0.7) | (n_len > 1.3)
    nrm = n_raw * 2 - 1
    pad_px = int(P.get("normal_padding_px_source", 32))
    nrm, filled = dilate_into(nrm, n_bg, pad_px)
    nrm[~filled] = (0.0, 0.0, 1.0)
    nrm = box_down(nrm, factor)
    nrm /= np.maximum(np.linalg.norm(nrm, axis=2, keepdims=True), 1e-6)
    n_dx = nrm.copy()
    n_dx[..., 1] *= -1  # OpenGL (glTF) -> DirectX (UE)
    n_out = n_dx * 0.5 + 0.5
    mr = box_down(image_array(mr_img)[..., :3], factor)
    bc_path, n_path, orm_path = (tex_dir / ("%s_%s.png" % (prefix, s)) for s in ("BC", "N", "ORM"))
    t_bc = save_png(bc_out, size, bc_path, "sRGB")
    t_n = save_png(n_out, size, n_path, "Non-Color")
    orm = np.ones((size, size, 3), dtype=np.float32)
    orm[..., 1] = mr[..., 1]
    orm[..., 2] = mr[..., 2]
    t_orm = save_png(orm, size, orm_path, "Non-Color")
    rec = {
        "source_images": names, "source_size_px": src_size, "target_size_px": size,
        "downscale": "none (source already %d px)" % size if factor == 1 else "box %dx%d" % (factor, factor),
        "normal_padding": {"background_fraction_source": r(n_bg.mean(), 4), "dilated_px_at_source": pad_px,
                           "flat_filled_fraction_source": r((~filled).mean(), 4)},
        "channel_stats": {"roughness_mean": r(orm[..., 1].mean(), 3), "metallic_mean": r(orm[..., 2].mean(), 3),
                          "metallic_fraction_gt_0.5": r((orm[..., 2] > 0.5).mean(), 4),
                          "normal_mean_rgb_dx": [r(v, 3) for v in n_out.reshape(-1, 3).mean(0)],
                          "bc_mean_srgb": [r(v, 3) for v in bc_out.reshape(-1, 3).mean(0)]},
    }
    if bc_factor_applied:
        rec["base_color_factor_applied"] = {"factor_rgb": bc_factor, "space": "linear (glTF semantics)",
                                            "note": "same rule as the lantern candidate (Tripo Studio export 0.8)"}
    return (t_bc, t_n, t_orm), (bc_path, n_path, orm_path), bc_out, rec


def uncovered_texels(obj, bc_out, raster):
    """Fraction of BC texels outside every UV island (at a coarse raster) and their mean colour: dark gutters
    bleed into islands at far mips."""
    me = obj.data
    me.calc_loop_triangles()
    uvl = me.uv_layers[0].data
    tuv = np.array([[uvl[i].uv[:] for i in t.loops] for t in me.loop_triangles])
    cov = SPC["raster_triangles"](tuv, raster) > 0
    size = bc_out.shape[0]
    f = size // raster
    bc_small = bc_out.reshape(raster, f, raster, f, 3).mean((1, 3))
    un = ~cov
    return {"raster_px": raster, "uncovered_fraction": r(un.mean(), 4),
            "uncovered_mean_bc_srgb": [r(v, 3) for v in (bc_small[un].mean(0) if un.any() else [0, 0, 0])],
            "note": "Tripo BC gutters; the lantern/barrel pipeline pads only N, BC/ORM are written as delivered"}


# ----------------------------------------------------------------------------- build
def build(P, aid, src):
    cfg = P["assets"][aid]
    name = cfg["name"]
    sm, prefix, mat_name = "SM_Env_" + name, "T_Env_" + name, "M_Env_" + name
    run = P["_run_dir"]
    export_dir = run / "export"
    rep_dir = run / "reports" / "assets"
    work = P["_scratch"] / "work"
    for d in (export_dir, rep_dir, work):
        d.mkdir(parents=True, exist_ok=True)
    preset = json.loads(P["_preset"].read_text(encoding="utf-8"))
    tripo = json.loads((run / "reports" / "tripo-run.json").read_text(encoding="utf-8"))
    src_sha = sha256(src)
    expected_sha = tripo["assets"][aid]["sha256"]
    glb = SPC["glb_json"](src)
    report = {
        "schema": "unmatched.env-kit.asset-build/1",
        "status": "measured",
        "claims": {"art_accepted": False, "game_ready": False, "budgets_declared": False},
        "asset_id": aid, "ue_mesh": sm, "board": cfg["board"],
        "blender_version": bpy.app.version_string,
        "scripts_sha256_lf": {rel(HERE): text_sha256_lf(HERE), rel(SPC_PATH): text_sha256_lf(SPC_PATH)},
        "source": {"path": rel(src), "sha256": src_sha, "bytes": src.stat().st_size,
                   "sha256_matches_tripo_run": src_sha == expected_sha,
                   "tripo_task": tripo["assets"][aid].get("tripoTask"),
                   "gltf_generator": glb[0].get("asset", {}).get("generator"),
                   "gltf_extensions_used": glb[0].get("extensionsUsed")},
        "no_render_policy": "no Eevee/Cycles/Workbench render, no bake, no viewport: GPU measurements in progress",
    }
    if src_sha != expected_sha:
        raise RuntimeError("source sha256 %s differs from tripo-run.json %s" % (src_sha, expected_sha))

    obj, imp = import_joined(src)
    obj.name = sm
    obj.data.name = sm
    report["import"] = imp

    # --- orientation: yaw about +Z in multiples of 90 deg (params override > orientation-check.json)
    yaw, yaw_src = cfg.get("yaw_deg"), "params"
    ocheck = None
    ocheck_path = run / "reports" / "orientation-check.json"
    if ocheck_path.is_file():
        ocheck = json.loads(ocheck_path.read_text(encoding="utf-8"))["assets"].get(aid)
    if yaw is None:
        if ocheck is None:
            raise RuntimeError("no yaw: run orientation_check.py first or set assets.%s.yaw_deg" % aid)
        yaw, yaw_src = ocheck["decision"]["yaw_deg"], "reports/orientation-check.json"
    yaw = float(yaw)
    if yaw % 90:
        raise RuntimeError("yaw must be a multiple of 90 deg, got %s" % yaw)
    if yaw:
        obj.data.transform(Matrix.Rotation(math.radians(yaw), 4, "Z"))
        obj.data.update()

    # --- target scale (rotation by 90 deg multiples keeps height and max horizontal extent)
    lo, hi = world_bounds([obj])
    dims = hi - lo
    tgt = cfg["target"]
    target_m = float(tgt["uu"]) / 100.0
    measure = {"height": dims.z, "length": max(dims.x, dims.y), "diameter": max(dims.x, dims.y)}[tgt["dimension"]]
    scale = target_m / measure
    uu_per_unit = scale * 100.0

    # --- geometry diagnostics before any transform of the data beyond yaw (Tripo geometry kept as is)
    geo, flipped = SPC["geometry_stats"](obj)
    report["geometry"] = {
        "policy": "measured only; no clean-up, repair or winding change (task rule: fix orientation/scale/pivot only)",
        "stats_welded_1e-6m_prescale": geo,
        "corner_normals": SPC["corner_normal_stats"](obj),
        "inconsistent_winding_face_centres_uu_prescale_frame": [
            [r(c * uu_per_unit, 2) for c in obj.data.polygons[i].center] for i in flipped[:10]],
        "shells_and_holes": shell_hole_stats(obj, uu_per_unit, float(P.get("isolated_gap_uu", 0.5))),
        "ray_escape_facing": facing_stats(obj, uu_per_unit),
        "winding_note": ("faces_with_inconsistent_winding comes from bmesh recalc_face_normals on the welded mesh; on "
                         "open/non-manifold meshes (foliage, overlapping Tripo shells) it splits regions arbitrarily, "
                         "so ray_escape_facing.inward is the flipped-face measure"),
    }
    geo_g = report["geometry"]
    geo_g["closed_manifold_consistent"] = (geo["welded_boundary_edges"] == 0 and geo["welded_non_manifold_edges"] == 0
                                           and geo["faces_with_inconsistent_winding"] == 0)

    centre = Vector(((lo.x + hi.x) / 2, (lo.y + hi.y) / 2, lo.z))
    obj.data.transform(Matrix.Scale(scale, 4) @ Matrix.Translation(-centre))
    obj.data.update()
    lo, hi = world_bounds([obj])
    d = hi - lo
    report["orientation"] = {
        "yaw_deg_about_plus_z_applied": yaw, "yaw_source": yaw_src,
        "orientation_check": ocheck,
        "front_convention": ("Tripo 'front' reference view = glTF +Z = .blend -Y = UE +X (UM_FBX_v1). Tripo 'left' view "
                             "= seen from .blend +X, 'right' = from -X, 'back' = from +Y. K1 camera looks along -Y: "
                             "actor yaw +90 turns the front to the camera"),
    }
    report["scale_pivot"] = {
        "target": tgt, "measured_source_m": r(measure), "uniform_scale_applied": r(scale),
        "uu_per_source_metre": r(uu_per_unit, 4),
        "dimensions_m_blend": [r(v) for v in d], "bounds_min_m": [r(v) for v in lo], "bounds_max_m": [r(v) for v in hi],
        "dimensions_uu_ue_xyz": [r(d.y * 100, 3), r(d.x * 100, 3), r(d.z * 100, 3)],
        "ue_axes_note": "UE X = depth (front-back, .blend Y), UE Y = width (.blend X), UE Z = height",
        "pivot": "object origin = (0,0,0) = centre of the XY bounds at min Z",
    }

    # --- textures + one material slot
    size = int(P["texture_size"])
    (t_bc, t_n, t_orm), paths, bc_out, tex = make_textures(P, glb, export_dir, prefix, size)
    obj.data.materials.clear()
    obj.data.materials.append(SPC["build_material"](mat_name, t_bc, t_n, t_orm))
    ao_stats = None
    if P.get("bake_ao"):
        raise RuntimeError("bake_ao is a Cycles bake: not allowed in this run (GPU measurement window)")
    for img in (t_bc, t_n, t_orm):
        img.reload()
    png_chunks, PNG_COLOR_CHUNKS = SPC["png_chunks"], SPC["PNG_COLOR_CHUNKS"]

    def png_tags(path):
        return sorted(t.decode() for t, _s, _e in png_chunks(path)[1] if t in PNG_COLOR_CHUNKS)

    note = "Linear is an import setting (UE: sRGB off); no sRGB/gAMA/cHRM/iCCP chunk in the file"
    bc_path, n_path, orm_path = paths
    tex["outputs"] = {
        "BC": {"path": rel(bc_path), "colorspace": "sRGB", "png_color_chunks": png_tags(bc_path),
               "sha256": sha256(bc_path), "bytes": bc_path.stat().st_size},
        "N": {"path": rel(n_path), "colorspace": "Linear (Non-Color)",
              "convention": "DirectX (G flipped from glTF OpenGL); UE: TC_Normalmap, flip_green false",
              "png_color_chunks": png_tags(n_path), "note": note, "sha256": sha256(n_path),
              "bytes": n_path.stat().st_size},
        "ORM": {"path": rel(orm_path), "colorspace": "Linear (Non-Color)",
                "channels": {"R": "1.0 (no AO: Tripo has no occlusion map; Cycles bake not run)",
                             "G": "roughness from glTF metallicRoughness.G", "B": "metallic from glTF metallicRoughness.B"},
                "png_color_chunks": png_tags(orm_path), "note": note, "sha256": sha256(orm_path),
                "bytes": orm_path.stat().st_size},
    }
    tex["ao_bake"] = ao_stats
    tex["bc_gutters"] = uncovered_texels(obj, bc_out, 512)
    report["textures"] = tex

    uv, tuv = SPC["uv_analysis"](obj, int(P.get("uv_raster_size", 1024)))
    report["uv0"] = uv
    SPC["uv_layout_png"](tuv, np.ascontiguousarray(bc_out[::4, ::4]), size // 4,
                         work / ("%s_uv0_layout.png" % sm))
    report["material_slots"] = len(obj.data.materials)
    report["material_names"] = [m.name for m in obj.data.materials]

    blend = work / ("%s.blend" % sm)
    bpy.context.preferences.filepaths.save_version = 0
    bpy.ops.wm.save_as_mainfile(filepath=str(blend), compress=False, copy=True)

    fbx = export_dir / ("%s.fbx" % sm)
    kwargs = SPC["fbx_kwargs"](preset)
    conformance = SPC["um_fbx_v1_conformance"](preset, kwargs, obj, bpy.context.scene)
    oc_ok = bool(ocheck and ocheck["decision"]["consistent"]) if yaw_src != "params" else True
    conformance.append({"setting": "Front (Tripo front view) along -Y in .blend (04 1: face -Y -> +X in UE)",
                        "standard": "-Y", "used": "-Y after yaw %+d deg" % yaw, "conforms": oc_ok,
                        "measured": "silhouette/colour check vs the four Tripo reference views, see orientation"})
    SPC["export_fbx"](obj, fbx, preset)
    report["export"] = {
        "fbx": rel(fbx), "sha256": sha256(fbx), "bytes": fbx.stat().st_size, "preset": P["_preset"].name,
        "settings": {k: preset[k] for k in ("axis_forward", "axis_up", "export_space_rotation_z_degrees",
                                            "temporary_data_scale", "patch_fbx_unit_scale_to", "apply_scale_options",
                                            "use_triangles", "mesh_smooth_type", "path_mode")},
        "exporter_kwargs": {k: (sorted(v) if isinstance(v, set) else v) for k, v in sorted(kwargs.items())},
        "textures_embedded": False, "texture_paths": "relative to the FBX (absolute checkout path is never written)",
        "um_fbx_v1_conformance": conformance,
        "um_fbx_v1_conforms": all(c["conforms"] for c in conformance),
        "ue_import": "legacy FBX, import_uniform_scale 1.0 (UM_FBX_v1 patches UnitScaleFactor to 1.0; the S05 "
                     "'FBX_SCALE_UNITS + import 100' note is another profile without the patch, see RIG-CONTRACT.md)",
    }
    report["work_blend_scratch"] = str(blend)

    expected_tris = triangles(obj)
    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.ops.import_scene.fbx(filepath=str(fbx))
    rt = mesh_objects()
    lo2, hi2 = world_bounds(rt)
    arm = [o for o in bpy.context.scene.objects if o.type == "ARMATURE"]
    rt_dims = hi2 - lo2
    rt_obj = rt[0] if rt else None
    rt_tris = sum(triangles(o) for o in rt)
    report["roundtrip"] = {
        "mesh_objects": len(rt), "object_names": [o.name for o in rt], "triangles": rt_tris,
        "expected_triangles_blend_faces": expected_tris,
        "material_slots": len(rt_obj.data.materials) if rt_obj else None,
        "uv_layers": len(rt_obj.data.uv_layers) if rt_obj else None, "armatures": len(arm),
        "dimensions_uu": [r(v * 100, 3) for v in rt_dims], "bounds_min_uu": [r(v * 100, 3) for v in lo2],
        "bounds_max_uu": [r(v * 100, 3) for v in hi2],
        "object_scale": [r(v) for v in rt_obj.scale] if rt_obj else None,
        "note": "Blender reads UnitScaleFactor 1.0 as cm and scales x0.01; readback frame: .blend -Y -> +X",
    }
    got_target = {"height": rt_dims.z, "length": max(rt_dims.x, rt_dims.y),
                  "diameter": max(rt_dims.x, rt_dims.y)}[tgt["dimension"]] * 100
    checks = {
        "source_sha256_matches_tripo_run": src_sha == expected_sha,
        "single_mesh": len(rt) == 1,
        "triangles_preserved": rt_tris == expected_tris,
        "triangles_le_budget": rt_tris <= int(P.get("max_triangles", 12000)),
        "one_material_slot": report["roundtrip"]["material_slots"] == 1,
        "uv0_present": (report["roundtrip"]["uv_layers"] or 0) >= 1,
        "uv0_inside_0_1": uv.get("triangles_out_of_0_1") == 0,
        "no_armature": not arm,
        "target_dimension_1pct": abs(got_target - float(tgt["uu"])) / float(tgt["uu"]) < 0.01,
        "base_at_zero": abs(lo2.z) < 1e-4,
        "centred_xy": abs((lo2.x + hi2.x) / 2) < 1e-4 and abs((lo2.y + hi2.y) / 2) < 1e-4,
        "source_unchanged": sha256(src) == src_sha,
        "um_fbx_v1_conforms": report["export"]["um_fbx_v1_conforms"],
    }
    report["checks"] = checks
    report["checks_passed"] = all(checks.values())
    out = rep_dir / ("%s.build.json" % sm)
    out.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print("ENV_KIT_BUILD", aid, json.dumps(checks))
    if not report["checks_passed"]:
        raise SystemExit(1)


def main():
    P, aid, probe_only = load_params()
    src = P["_run_dir"] / "source" / ("%s.glb" % aid)
    if not src.is_file():
        raise SystemExit("missing source %s" % src)
    if probe_only:
        probe(P, aid, src)
    else:
        build(P, aid, src)


main()
