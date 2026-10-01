"""ASSET-TABLE-BASE-001 T2: build SM_TableBase_T2, the ONE shared rocky tray of the map boards (ENV-U10).

Headless only (never touches a live Blender session; CPU only, no render):
  "C:/Program Files/Blender Foundation/Blender 5.2/blender.exe" -b --factory-startup --python-exit-code 1 \
      --python art/pipeline-candidates/ASSET-TABLE-BASE-001/scripts/tray_t2_build.py -- \
      art/pipeline-candidates/ASSET-TABLE-BASE-001/20261001-tray-t2/reports/tray-t2-params.json
(tray_t2_run.py runs textures -> build -> readback -> preview in order.)

What it builds (every number PROPOSED in the params file, not an art decision):
  top      ONE flat quad at Z top_z (-3) exactly covering the tray rectangle 2 x half_x_ue by 2 x half_y_ue (UE X x Y;
           the themed ground of track GROUND lies on it and hides it).
  skirt    the rocky cliff around the whole perimeter, built modularly by tray_t2_layout.py: a library of convex rock
           chunks (cap / block / spike, bmesh convex hulls of seeded point clouds), side modules (6 lengths) and
           corner modules (2), instanced around the perimeter with rigid transforms + uniform scale ONLY (the
           anisotropy of every instance matrix is reported, 1.0). Caps form the top lip (overhang 4..15 uu, their
           tilted tops may rise to lip_top_z_max only within rim_uu of the edge: a cap whose hull reaches above
           top_z - 0.3 inside the inner rectangle is moved down - translation only, reported), blocks the cliff,
           spikes the hanging jagged bottom (depth 120..180 uu below the top).
  core     an open box (4 walls + bottom, no top face) inset core_inset_uu under the top down to core_bottom_z: gaps
           between chunks show rock, never the void.
  UV0      world-scale box projection per face (tile_uu per texture repeat; +-X/+-Y/+-Z facing, unmirrored, image up
           = world up on the walls) + a random offset per chunk instance (the flat top: 2 x tile_uu, no offset): the
           textures TILE (UE Wrap addressing, M_UM_Figure samples TexCoord0). Flat shading (faceted rock; UM_FBX_v1
           smoothing FACE).
  material one slot M_TableBase_T2 (T_TableBase_T2_BC/N/ORM from tray_t2_textures.py; in UE MI_TableBase_T2).
  pivot    XY = the centre of the flat top (= tray centre), Z = 0 = the board play plane (top at -3). The board actor
           places it at (0, tray offsetY, 0), yaw 0, scale 1: the tray offset is applied by code, not baked.
  axes     .blend: the long side (UE X) along .blend Y; UM_FBX_v1 (+90 deg Z, x100, UnitScaleFactor 1.0): UE X =
           -blend y, UE Y = -blend x (the FBX read back in Blender is UE with Y negated).
  export   the helpers of tools/tripo-pipeline/blender/static_prop_candidate.py (executed without its trailing main();
           its LF sha256 is recorded): export_fbx (deterministic bytes), fbx_kwargs, um_fbx_v1_conformance,
           build_material. Round trip in an empty scene.
Checks (the run fails if one is false): triangles <= max_triangles; every instance uniform (anisotropy 1 +- 1e-9);
the flat top is exactly the rectangle at top_z; nothing above top_z inward of the rim band (bisected); lip top <=
lip_top_z_max; overhang <= overhang_max_uu on the sides (>= 60 uu from a corner) and <= overhang_corner_max_uu at the
corners; depth in [depth_min_uu, depth_max_uu]; no see-through to the void: rays from the game cameras (K1, zoom-out
0.65x, follow 1.2x / 1.6x on near spaces) to every perimeter point at depths -6 .. -55 uu hit the tray; 1 mesh, 1 slot,
UV0, round-trip triangles equal; UM_FBX_v1 rows conform (pivot row replaced by the tray pivot row).
Outputs: <run>/export/SM_TableBase_T2.fbx, <run>/reports/build-report.json, <run>/reports/kit-instances.json;
<scratch>/work/SM_TableBase_T2.blend (out of git, rebuilt by this script).
"""

import json
import math
import sys
import types
from pathlib import Path

import bmesh
import bpy
import numpy as np
from mathutils import Matrix, Vector
from mathutils.bvhtree import BVHTree

HERE = Path(__file__).resolve()
REPO = HERE.parents[4]  # <repo>/art/pipeline-candidates/<asset>/scripts/<this file>
SPC_PATH = REPO / "tools" / "tripo-pipeline" / "blender" / "static_prop_candidate.py"
SCHEMA = "unmatched.table-base-t2.build-report/1"
sys.path.insert(0, str(HERE.parent))
import tray_t2_layout as LAY  # noqa: E402


def load_helpers():
    body = SPC_PATH.read_text(encoding="utf-8").rstrip()
    if not body.endswith("\nmain()"):
        raise SystemExit("static_prop_candidate.py no longer ends with a bare main() call: %s" % SPC_PATH)
    ns = {"__name__": "static_prop_candidate_helpers", "__file__": str(SPC_PATH)}
    exec(compile(body[:-len("main()")], str(SPC_PATH), "exec"), ns)
    return types.SimpleNamespace(**ns)


S = load_helpers()
r = S.r


def rel(p):
    try:
        return Path(p).resolve().relative_to(REPO).as_posix()
    except ValueError:
        return Path(p).as_posix()


def load_params():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    if not argv:
        raise SystemExit("params.json required after --")
    pp = Path(argv[0]).resolve()
    P = json.loads(pp.read_text(encoding="utf-8"))
    P["_params_path"] = pp
    P["_run"] = (REPO / P["run_dir"]).resolve()
    P["_scratch"] = Path(P["scratch_dir"]).resolve()
    P["_preset"] = (REPO / P["fbx_preset"]).resolve()
    return P


# ----------------------------------------------------------------------------- geometry
def hull(points):
    """Convex hull of a point cloud (uu): (verts N x 3, triangles list), outward normals."""
    bm = bmesh.new()
    for p in points:
        bm.verts.new(Vector(p))
    res = bmesh.ops.convex_hull(bm, input=bm.verts[:], use_existing_faces=False)
    drop = list({g for g in res["geom_interior"] + res["geom_unused"] if isinstance(g, bmesh.types.BMVert)})
    if drop:
        bmesh.ops.delete(bm, geom=drop, context="VERTS")
    bmesh.ops.triangulate(bm, faces=bm.faces[:])
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
    bm.verts.index_update()
    verts = np.array([v.co[:] for v in bm.verts], dtype=np.float64)
    tris = [tuple(v.index for v in f.verts) for f in bm.faces]
    bm.free()
    return verts, tris


def max_z_inside(verts, tris, hx_in, hy_in):
    """Highest point of a closed mesh inside the prism |x| < hx_in, |y| < hy_in (bisected exactly), or None."""
    bm = bmesh.new()
    vs = [bm.verts.new(Vector(v)) for v in verts]
    for t in tris:
        bm.faces.new([vs[i] for i in t])
    for co, no in (((hx_in, 0, 0), (1, 0, 0)), ((-hx_in, 0, 0), (-1, 0, 0)),
                   ((0, hy_in, 0), (0, 1, 0)), ((0, -hy_in, 0), (0, -1, 0))):
        geom = bm.verts[:] + bm.edges[:] + bm.faces[:]
        if not bm.verts:
            break
        bmesh.ops.bisect_plane(bm, geom=geom, plane_co=co, plane_no=no, clear_outer=True, dist=1e-6)
    z = max((v.co.z for v in bm.verts), default=None)
    bm.free()
    return z


def box_uv(p, n, tile, off):
    """World box projection (uu -> UV), unmirrored, image up = +Z on walls."""
    ax = int(np.argmax(np.abs(n)))
    if ax == 0:
        u, v = p[1] * math.copysign(1.0, n[0]), p[2]
    elif ax == 1:
        u, v = -p[0] * math.copysign(1.0, n[1]), p[2]
    else:
        u, v = p[0] * math.copysign(1.0, n[2]), p[1]
    return (u / tile + off[0], v / tile + off[1])


def build_geometry(P, lay):
    tray, kit = P["tray"], P["kit"]
    top_z = float(tray["top_z"])
    hx, hy = lay["half_bx"], lay["half_by"]
    rim = float(tray["rim_uu"])
    tile = float(kit["tile_uu"])
    hulls = {k: [hull(s["points"]) for s in lay["library"][k]] for k in LAY.KINDS}
    V, F, FUV, FKIND = [], [], [], []
    inst_rows, corrected = [], 0
    rng = np.random.default_rng([kit["seed"], 9])

    def add(verts, tris, kind, off, tile_k=1.0):
        base = sum(len(v) for v in V)
        V.append(verts)
        for t in tris:
            a, b, c = (verts[i] for i in t)
            n = np.cross(b - a, c - a)
            ln = np.linalg.norm(n)
            n = n / ln if ln > 0 else np.array([0.0, 0.0, 1.0])
            F.append(tuple(base + i for i in t))
            FUV.append([box_uv(verts[i], n, tile * tile_k, off) for i in t])
            FKIND.append(kind)

    for ii, inst in enumerate(lay["instances"]):
        hv, ht = hulls[inst["kind"]][inst["variant"]]
        M = inst["matrix"]
        wv = hv @ M[:3, :3].T + M[:3, 3]
        dz = 0.0
        zin = max_z_inside(wv, ht, hx - rim, hy - rim)
        if zin is not None and zin > top_z - 0.3:
            dz = zin - (top_z - 0.3)
            wv = wv - np.array([0.0, 0.0, dz])
            corrected += 1
        off = (float(rng.random()), float(rng.random()))
        add(wv, ht, inst["kind"], off)
        sc, an = LAY.uniform_scale(M)
        inst_rows.append({"i": ii, "placement": inst["placement"], "module": inst["module"], "chunk": inst["chunk"],
                          "kind": inst["kind"], "variant": inst["variant"], "scale": round(sc, 6),
                          "anisotropy": an, "yawDeg": round(math.degrees(math.atan2(M[1, 0], M[0, 0])), 3),
                          "posUU": [round(float(v), 3) for v in M[:3, 3]], "rimDropUU": round(dz, 3),
                          "uvOffset": [round(off[0], 4), round(off[1], 4)], "hullTris": len(ht)})
    # core: open box (walls + bottom) inset under the top
    ci, zb = float(kit["core_inset_uu"]), float(kit["core_bottom_z"])
    cx, cy = hx - ci, hy - ci
    cv = np.array([[-cx, -cy, top_z], [cx, -cy, top_z], [cx, cy, top_z], [-cx, cy, top_z],
                   [-cx, -cy, zb], [cx, -cy, zb], [cx, cy, zb], [-cx, cy, zb]], dtype=np.float64)
    # outward-facing walls (CCW seen from outside) + bottom facing -Z
    ct = [(0, 4, 5), (0, 5, 1), (1, 5, 6), (1, 6, 2), (2, 6, 7), (2, 7, 3), (3, 7, 4), (3, 4, 0),
          (4, 7, 6), (4, 6, 5)]
    add(cv, ct, "core", (0.0, 0.0))
    # the flat top: one quad (2 triangles) = the tray rectangle at top_z, facing +Z
    tv = np.array([[-hx, -hy, top_z], [hx, -hy, top_z], [hx, hy, top_z], [-hx, hy, top_z]], dtype=np.float64)
    # (texture repeat x2 on the flat top: one 1560 x 940 plane shows its repeats more than the broken rock faces do)
    add(tv, [(0, 1, 2), (0, 2, 3)], "top", (0.0, 0.0), tile_k=2.0)
    return np.vstack(V), F, FUV, FKIND, inst_rows, corrected


def make_object(P, verts_uu, faces, fuv):
    me = bpy.data.meshes.new(P["asset_name"])
    me.from_pydata((verts_uu / 100.0).tolist(), [], faces)
    me.update()
    for p in me.polygons:
        p.use_smooth = False
    uvl = me.uv_layers.new(name="UVMap")
    flat = [c for tri in fuv for uv in tri for c in uv]
    uvl.data.foreach_set("uv", flat)
    me.validate(clean_customdata=False)
    obj = bpy.data.objects.new(P["asset_name"], me)
    bpy.context.scene.collection.objects.link(obj)
    return obj


def material(P):
    exp = P["_run"] / "export"
    pre = P["texture_prefix"]
    imgs = {}
    for key, cs in (("BC", "sRGB"), ("N", "Non-Color"), ("ORM", "Non-Color")):
        path = exp / ("%s_%s.png" % (pre, key))
        if not path.is_file():
            raise SystemExit("missing %s (run tray_t2_textures.py first)" % path)
        img = bpy.data.images.load(str(path))
        img.colorspace_settings.name = cs
        imgs[key] = img
    return S.build_material(P["material_name"], imgs["BC"], imgs["N"], imgs["ORM"])


def uv_stats(P, verts, faces, fuv):
    """Box projection: texel density is exact on the projection plane; a face tilted from it stretches the texture
    by 1 / |n . axis| along its slope (<= sqrt(3)). Area-weighted over the mesh (uu, px of a 2048 texture)."""
    tile = float(P["kit"]["tile_uu"])
    tri = verts[np.array(faces)]
    n = np.cross(tri[:, 1] - tri[:, 0], tri[:, 2] - tri[:, 0])
    area = 0.5 * np.linalg.norm(n, axis=1)
    cosd = np.abs(n).max(1) / np.maximum(np.linalg.norm(n, axis=1), 1e-12)
    stretch = 1.0 / np.maximum(cosd, 1e-6)
    w = area / area.sum()
    uvs = np.array(fuv)
    return {"layers": ["UVMap"], "projection": "world box, per chunk random offset", "tileUU": tile,
            "texelsPerUU_2048": r(2048.0 / tile, 3), "uvRange": [r(uvs.min(), 3), r(uvs.max(), 3)],
            "stretchAreaWeightedMean": r(float((stretch * w).sum()), 4), "stretchMax": r(float(stretch.max()), 4),
            "stretchP95": r(float(np.sort(stretch)[int(0.95 * (len(stretch) - 1))]), 4),
            "surfaceAreaUU2": r(float(area.sum()), 1)}


# ----------------------------------------------------------------------------- measurements
def ue_frame(lo, hi):
    """.blend bounds (uu) -> UE bounds: X = -blend y, Y = -blend x."""
    return [-hi[1], -hi[0], lo[2]], [-lo[1], -lo[0], hi[2]]


def game_cameras(P):
    """(name, origin, target) in the mesh's .blend frame (mesh centred on the tray centre; the map centre lies at UE
    (0, -offsetY) relative to it). UE (X, Y) -> .blend (-Y, -X)."""
    pv, tray = P["preview"], P["tray"]
    oy = -float(tray["offset_y_ue"])  # map centre relative to the tray centre, UE Y
    pitch = math.radians(-float(pv["pitch_deg"]))

    def cam(focus_ue, dist):
        fx, fy, fz = focus_ue
        c = (fx, fy + dist * math.cos(pitch), fz + dist * math.sin(pitch))
        return (-c[1], -c[0], c[2]), (-fy, -fx, fz)
    out = []
    for name, focus, dist in (("K1", (0.0, oy, 0.0), pv["k1_distance_uu"]),
                              ("zoom-out-0.65", (0.0, oy, 0.0), pv["zoom_out_distance_uu"]),
                              ("follow-1.2-near-W", (-300.0, oy + 250.0, 28.0), pv["k1_distance_uu"] / 1.2),
                              ("follow-1.6-near-E", (300.0, oy + 250.0, 28.0), pv["follow_distance_uu"])):
        o, t = cam(focus, float(dist))
        out.append((name, Vector(o), Vector(t)))
    return out


def perimeter_points(hx, hy, step):
    """(point on the rectangle boundary (x, y), outward normal, side name) every 'step' uu."""
    pts = []
    for name, (x0, y0), (dx, dy), (nx, ny), L in (("top", (-hx, hy), (1, 0), (0, 1), 2 * hx),
                                                  ("right", (hx, hy), (0, -1), (1, 0), 2 * hy),
                                                  ("bottom", (hx, -hy), (-1, 0), (0, -1), 2 * hx),
                                                  ("left", (-hx, -hy), (0, 1), (-1, 0), 2 * hy)):
        for i in range(int(L // step) + 1):
            u = min(i * step, L)
            pts.append(((x0 + dx * u, y0 + dy * u), (nx, ny), name))
    return pts


def see_through(P, bvh, hx, hy, top_z):
    """Rays from the game cameras to the tray boundary. A required ray (depths top-0.5 .. -55) that hits nothing is a
    HOLE when, past its target, it runs through the inside of the tray (|x| < hx, |y| < hy, core bottom .. top): the
    void would show where rock must be. A miss that leaves the tray outward (at a chamfered corner, under an
    overhang) is silhouette and only counted. Deep rays (-100 / -140) measure how open the hanging bottom is."""
    zb = float(P["kit"]["core_bottom_z"])

    def enters_inside(o, d, t0):
        for k in range(1, 81):
            q = o + d * (t0 + 5.0 * k)
            if abs(q.x) < hx - 0.5 and abs(q.y) < hy - 0.5 and zb < q.z < top_z:
                return True
        return False
    # required: the boundary line of the flat top just under it and down the cliff (a miss = the void shows through
    # the tray); a point OUTSIDE the edge is not required - there the lip rock may lie lower (silhouette, not a hole)
    req = [top_z - 0.5, top_z - 3.0, -15.0, -30.0, -45.0, -55.0]
    deep = [-100.0, -140.0]
    res = {"requiredDepthsZ": req, "deepDepthsZ": deep, "cameras": {}}
    total_miss = 0
    for name, o, _t in game_cameras(P):
        miss, silhouette, n_req, open_deep, n_deep, miss_where = 0, 0, 0, 0, 0, []
        for (x, y), (nx, ny), side in perimeter_points(hx, hy, 4.0):
            targets = [((x, y, z), True) for z in req]
            targets += [((x, y, z), False) for z in deep]
            for (tx, ty, tz), required in targets:
                d = Vector((tx, ty, tz)) - o
                dist = d.length
                hit = bvh.ray_cast(o, d.normalized(), dist + 600.0)[0]
                if required:
                    n_req += 1
                    if hit is None and enters_inside(o, d.normalized(), dist):
                        miss += 1
                        if len(miss_where) < 12:
                            miss_where.append([side, round(x, 1), round(y, 1), round(tz, 1)])
                    elif hit is None:
                        silhouette += 1
                else:
                    n_deep += 1
                    open_deep += hit is None
        total_miss += miss
        res["cameras"][name] = {"origin": [r(v, 2) for v in o], "requiredRays": n_req, "holes": miss,
                                "holesAt": miss_where, "silhouetteMisses": silhouette, "deepRays": n_deep,
                                "deepOpenFraction": r(open_deep / max(n_deep, 1), 4)}
    res["missedTotal"] = total_miss
    return res


def measure(P, lay, verts, faces, fkind):
    tray = P["tray"]
    top_z = float(tray["top_z"])
    hx, hy = lay["half_bx"], lay["half_by"]
    rim = float(tray["rim_uu"])
    lo, hi = verts.min(0), verts.max(0)
    tris = sum(len(f) - 2 for f in faces)
    by_kind = {}
    for f, k in zip(faces, fkind):
        by_kind[k] = by_kind.get(k, 0) + len(f) - 2
    # flat top: the +Z faces at top_z
    top_ids = [i for i, k in enumerate(fkind) if k == "top"]
    tv = verts[sorted({v for i in top_ids for v in faces[i]})]
    # nothing above top_z inward of the rim band (whole mesh bisected; the top quad itself is exactly top_z)
    zin = max_z_inside(verts, faces, hx - rim, hy - rim)
    # overhang (beyond the rectangle) on the sides (>= 60 uu from a corner) and at the corners
    ox, oy = np.abs(verts[:, 0]) - hx, np.abs(verts[:, 1]) - hy
    along_x_side = np.abs(verts[:, 1]) < hy - 60.0  # the long sides x = +-hx
    along_y_side = np.abs(verts[:, 0]) < hx - 60.0  # the short sides y = +-hy
    ov_side = max(float(ox[along_x_side].max()), float(oy[along_y_side].max()))
    ov_all = float(np.maximum(ox, oy).max())
    per_side = {"right(x+)": float(ox[along_x_side & (verts[:, 0] > 0)].max()),
                "left(x-)": float(ox[along_x_side & (verts[:, 0] < 0)].max()),
                "top(y+)": float(oy[along_y_side & (verts[:, 1] > 0)].max()),
                "bottom(y-)": float(oy[along_y_side & (verts[:, 1] < 0)].max())}
    ue_side = {"right(x+)": "far/north (UE -Y)", "left(x-)": "near/south (UE +Y)", "top(y+)": "west (UE -X)",
               "bottom(y-)": "east (UE +X)"}
    kinds = {}
    for k in LAY.KINDS:
        ids = [i for i, kk in enumerate(fkind) if kk == k]
        vv = verts[sorted({v for i in ids for v in faces[i]})]
        kinds[k] = {"triangles": by_kind.get(k, 0), "zRange": [r(vv[:, 2].min(), 2), r(vv[:, 2].max(), 2)]}
    ue_lo, ue_hi = ue_frame(lo, hi)
    return {
        "triangles": tris, "trianglesByPart": by_kind, "vertices": int(len(verts)),
        "boundsBlendUU": {"min": [r(v, 3) for v in lo], "max": [r(v, 3) for v in hi]},
        "boundsUeUU": {"min": [r(v, 3) for v in ue_lo], "max": [r(v, 3) for v in ue_hi],
                       "size": [r(ue_hi[i] - ue_lo[i], 3) for i in range(3)]},
        "flatTop": {"zUU": sorted({r(v, 4) for v in tv[:, 2]}),
                    "rectBlendUU": {"min": [r(v, 3) for v in tv.min(0)[:2]], "max": [r(v, 3) for v in tv.max(0)[:2]]},
                    "rectUeUU": {"halfX": r(tv[:, 1].max(), 3), "halfY": r(tv[:, 0].max(), 3)},
                    "triangles": 2 * 1},
        "lip": {"topZMaxUU": r(hi[2], 3), "rimUU": rim,
                "maxZInsideRimBandInnerRectUU": None if zin is None else r(zin, 4),
                "note": "max Z of the whole mesh inside |x| < half - rim, |y| < half - rim (bisected): the flat top"},
        "overhangUU": {"sidesMax": r(ov_side, 3), "cornersMax": r(ov_all, 3),
                       "perSide": {ue_side[k]: r(v, 3) for k, v in per_side.items()}},
        "depthBelowTopUU": r(top_z - lo[2], 3), "lowestZUU": r(lo[2], 3),
        "rows": kinds,
    }


def main():
    P = load_params()
    run, scratch = P["_run"], P["_scratch"]
    for sub in ("export", "reports"):
        (run / sub).mkdir(parents=True, exist_ok=True)
    (scratch / "work").mkdir(parents=True, exist_ok=True)
    preset = json.loads(P["_preset"].read_text(encoding="utf-8"))
    tray, kit = P["tray"], P["kit"]
    top_z = float(tray["top_z"])

    bpy.ops.wm.read_factory_settings(use_empty=True)
    lay = LAY.build(P)
    verts, faces, fuv, fkind, inst_rows, corrected = build_geometry(P, lay)
    meas = measure(P, lay, verts, faces, fkind)
    bvh = BVHTree.FromPolygons([Vector(v) for v in verts], faces, all_triangles=True)
    holes = see_through(P, bvh, lay["half_bx"], lay["half_by"], top_z)

    obj = make_object(P, verts, faces, fuv)
    mat = material(P)
    obj.data.materials.append(mat)
    bpy.context.view_layer.objects.active = obj
    uv = uv_stats(P, verts, faces, fuv)  # tiling UVs: S.uv_analysis rasterises 0..1 atlases, not this

    blend = scratch / "work" / ("%s.blend" % P["asset_name"])
    bpy.context.preferences.filepaths.save_version = 0
    bpy.ops.wm.save_as_mainfile(filepath=str(blend), compress=False, copy=True)

    fbx = run / "export" / ("%s.fbx" % P["asset_name"])
    kwargs = S.fbx_kwargs(preset)
    conformance = [c for c in S.um_fbx_v1_conformance(preset, kwargs, obj, bpy.context.scene)
                   if not c["setting"].startswith("Pivot:")]
    rect = meas["flatTop"]["rectBlendUU"]
    centre = [r((rect["min"][0] + rect["max"][0]) / 2, 4), r((rect["min"][1] + rect["max"][1]) / 2, 4)]
    conformance.append({"setting": "Pivot: tray centre (0,0) = centre of the flat top; flat top at top_z; above it only "
                                   "the rocky lip within rim_uu of the edge (ENV-U10 T2)",
                        "standard": [0.0, 0.0, top_z], "used": centre + meas["flatTop"]["zUU"][:1],
                        "conforms": abs(centre[0]) < 0.01 and abs(centre[1]) < 0.01
                        and meas["flatTop"]["zUU"] == [r(top_z, 4)]})
    S.export_fbx(obj, fbx, preset)
    expected_tris = S.triangles(obj)

    # round trip in an empty scene (read-back frame = UE with Y negated; metres x100 = uu)
    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.ops.import_scene.fbx(filepath=str(fbx))
    rt = S.mesh_objects()
    rt_obj = rt[0] if rt else None
    lo2, hi2 = S.world_bounds(rt)
    roundtrip = {"mesh_objects": len(rt), "triangles": sum(S.triangles(o) for o in rt),
                 "expected_triangles": expected_tris,
                 "material_slots": [m.name if m else None for m in rt_obj.data.materials] if rt_obj else None,
                 "uv_layers": [l.name for l in rt_obj.data.uv_layers] if rt_obj else None,
                 "bounds_min_uu_readback": [r(v * 100, 3) for v in lo2],
                 "bounds_max_uu_readback": [r(v * 100, 3) for v in hi2],
                 "note": "read-back frame: UE = (x, -y, z)"}
    ue = meas["boundsUeUU"]
    rb_as_ue_min = [roundtrip["bounds_min_uu_readback"][0], -roundtrip["bounds_max_uu_readback"][1],
                    roundtrip["bounds_min_uu_readback"][2]]
    rb_as_ue_max = [roundtrip["bounds_max_uu_readback"][0], -roundtrip["bounds_min_uu_readback"][1],
                    roundtrip["bounds_max_uu_readback"][2]]
    roundtrip["bounds_as_ue_uu"] = {"min": rb_as_ue_min, "max": rb_as_ue_max}
    roundtrip["ue_frame_matches_build"] = all(abs(a - b) < 0.05 for a, b in zip(rb_as_ue_min + rb_as_ue_max,
                                                                                 ue["min"] + ue["max"]))
    hx_ue, hy_ue = float(tray["half_x_ue"]), float(tray["half_y_ue"])
    an = max(row["anisotropy"] for row in inst_rows)
    checks = {
        "triangles_within_budget": meas["triangles"] <= int(tray["max_triangles"]),
        "instances_uniform_scale_only": abs(an - 1.0) < 1e-9,
        "flat_top_is_the_tray_rectangle": (meas["flatTop"]["zUU"] == [r(top_z, 4)]
                                           and abs(meas["flatTop"]["rectUeUU"]["halfX"] - hx_ue) < 0.01
                                           and abs(meas["flatTop"]["rectUeUU"]["halfY"] - hy_ue) < 0.01
                                           and meas["flatTop"]["rectBlendUU"]["min"] == [-hy_ue, -hx_ue]),
        "nothing_above_top_inward_of_rim": (meas["lip"]["maxZInsideRimBandInnerRectUU"] is not None
                                            and meas["lip"]["maxZInsideRimBandInnerRectUU"] <= top_z + 0.01),
        "lip_top_within_max": meas["lip"]["topZMaxUU"] <= float(tray["lip_top_z_max"]) + 1e-6,
        "overhang_sides_within_max": meas["overhangUU"]["sidesMax"] <= float(tray["overhang_max_uu"]),
        "overhang_corners_within_max": meas["overhangUU"]["cornersMax"] <= float(tray["overhang_corner_max_uu"]),
        "depth_in_range": float(tray["depth_min_uu"]) <= meas["depthBelowTopUU"] <= float(tray["depth_max_uu"]),
        "no_see_through_to_void": holes["missedTotal"] == 0,
        "single_mesh": roundtrip["mesh_objects"] == 1,
        "triangles_preserved": roundtrip["triangles"] == expected_tris,
        "one_material_slot": roundtrip["material_slots"] == [P["material_name"]],
        "uv0_present": bool(roundtrip["uv_layers"]),
        "roundtrip_bounds_match_ue_frame": roundtrip["ue_frame_matches_build"],
        "um_fbx_v1_conforms": all(c["conforms"] for c in conformance),
    }
    report = {
        "schema": SCHEMA, "status": "measured", "asset": "ASSET-TABLE-BASE-001 / SM_TableBase_T2",
        "claims": {"art_accepted": False, "game_ready": False, "budgets_declared": False},
        "blender_version": bpy.app.version_string,
        "script_sha256_lf": S.text_sha256_lf(HERE),
        "layout_sha256_lf": S.text_sha256_lf(HERE.parent / "tray_t2_layout.py"),
        "helpers": {"path": rel(SPC_PATH), "sha256_lf": S.text_sha256_lf(SPC_PATH)},
        "params": {"path": rel(P["_params_path"]), "sha256": S.sha256(P["_params_path"]),
                   "tray": tray, "kit": kit},
        "contract": {
            "ue": {"folder": "/Game/PipelineCandidates/TableBase/T2", "mesh": P["asset_name"],
                   "material_instance": "MI_TableBase_T2",
                   "textures": ["%s_%s" % (P["texture_prefix"], k) for k in ("BC", "N", "ORM")],
                   "import": "tools/art/env_kit/ue_import_tray_t2.py (legacy FbxFactory, import_uniform_scale 1.0, "
                             "normals imported, no collision, Nanite off; textures Wrap)"},
            "placement": "board actor: component at (0, tray.offsetY, 0), yaw 0, scale 1 (S08Diorama T2); the mesh is "
                         "XY-centred on its flat top, Z = play plane",
            "axes": "UE X = -blend y (long side), UE Y = -blend x; read-back frame = UE with Y negated",
            "uv": "UV0 world box projection, %.0f uu per repeat, textures tile (Wrap)" % float(kit["tile_uu"]),
        },
        "kit": {
            "library": {k: [{"variant": i, "w": r(s["w"], 2), "t": r(s["t"], 2), "h": r(s["h"], 2),
                             "points": int(len(s["points"])), "extra": s["extra"]}
                            for i, s in enumerate(lay["library"][k])] for k in LAY.KINDS},
            "sideModules": [{"variant": m["index"], "lengthUU": m["length"], "chunks": len(m["chunks"])}
                            for m in lay["sides"]],
            "cornerModules": [{"variant": m["index"], "legUU": m["legUU"], "chunks": len(m["chunks"])}
                              for m in lay["corners"]],
            "perimeter": lay["perimeter"]["sides"],
            "modulePlacements": len(lay["perimeter"]["placements"]),
            "chunkInstances": len(inst_rows),
            "instanceScaleRange": [r(min(x["scale"] for x in inst_rows), 4), r(max(x["scale"] for x in inst_rows), 4)],
            "instanceAnisotropyMax": an,
            "capsMovedDownForRim": corrected,
            "instancesFile": "reports/kit-instances.json",
        },
        "geometry": meas,
        "seeThrough": holes,
        "uv0": uv,
        "material": {"slot": P["material_name"], "textures": {k: rel(P["_run"] / "export" /
                                                                    ("%s_%s.png" % (P["texture_prefix"], k)))
                                                             for k in ("BC", "N", "ORM")}},
        "export": {"fbx": rel(fbx), "sha256": S.sha256(fbx), "bytes": fbx.stat().st_size,
                   "preset": P["_preset"].name, "exporter_kwargs": {k: (sorted(v) if isinstance(v, set) else v)
                                                                   for k, v in sorted(kwargs.items())},
                   "um_fbx_v1_conformance": conformance},
        "roundtrip": roundtrip,
        "blend_scratch": str(blend),
    }
    report["checks"] = {k: bool(v) for k, v in checks.items()}
    report["checks_passed"] = all(report["checks"].values())
    (run / "reports" / "build-report.json").write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n",
                                                        encoding="utf-8")
    (run / "reports" / "kit-instances.json").write_text(
        json.dumps({"schema": "unmatched.table-base-t2.instances/1", "frame": ".blend uu (UE X = -y, UE Y = -x)",
                    "placements": lay["perimeter"]["placements"], "instances": inst_rows}, indent=1) + "\n",
        encoding="utf-8")
    print("T2-BUILD", json.dumps(report["checks"]))
    print("T2-BUILD-SUMMARY tris=%d instances=%d lipTop=%.2f depth=%.1f overhang=%.1f/%.1f miss=%d fbx=%s" % (
        meas["triangles"], len(inst_rows), meas["lip"]["topZMaxUU"], meas["depthBelowTopUU"],
        meas["overhangUU"]["sidesMax"], meas["overhangUU"]["cornersMax"], holes["missedTotal"],
        report["export"]["sha256"][:12]))
    if not report["checks_passed"]:
        raise SystemExit(1)


main()
