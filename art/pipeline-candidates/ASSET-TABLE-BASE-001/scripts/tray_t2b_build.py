"""ASSET-TABLE-BASE-001 T2b: build SM_TableBase_T2b, the chunky version of the ONE shared rocky tray (ENV-U10, gap 3).

Headless only (fresh `blender -b --factory-startup`, CPU, no render), driven by tools/art/env_kit/run_k_assets.py:
  blender -b --factory-startup -t 4 --python-exit-code 1 --python \
      art/pipeline-candidates/ASSET-TABLE-BASE-001/scripts/tray_t2b_build.py -- \
      art/pipeline-candidates/ASSET-TABLE-BASE-001/20261001-tray-t2b/reports/tray-t2b-params.json

Same contract as T2 (tray_t2_build.py), so it is a drop-in mesh for the board actor (S08Diorama T2: component at
(0, tray.offsetY, 0), yaw 0, scale 1):
  top      ONE flat quad at top_z (-3) exactly covering the tray rectangle 2 x 780 by 2 x 470 (the themed ground hides it);
  skirt    convex rock chunks (tray_t2b_layout.py: cap / boulder / block / spike rows), side + corner modules
           instanced around the perimeter with rigid transforms + uniform scale ONLY (anisotropy reported, 1.0);
           a cap whose hull rises above top_z - 0.3 inward of the rim band is moved down (translation only, counted);
  core     an open box (4 walls + bottom) inset core_inset_uu under the top down to core_bottom_z;
  UV0      world box projection, tile_uu per repeat, random offset per chunk (textures tile; the T2 rock set is reused);
  Col      per-corner vertex colour (k_blender.py): R moss mask on the upper lip, G per-chunk random, B depth 0..1, A 1;
  material one slot M_TableBase_T2b (UE: MI_TableBase_T2b - the moss band, Marmoreal moss/petals or Sarpedon damp rock,
           is an MI parameter over Col.R; the textures are T_TableBase_T2_{BC,N,ORM} + T_TableBase_T2b_Moss_{BC,N}).
Checks (the run fails if one is false): triangles <= max_triangles; uniform instances; the flat top is the rectangle at
top_z; nothing above top_z inward of the rim band; lip top <= lip_top_z_max; overhang on the sides / corners <= the max;
depth in [depth_min, depth_max]; no see-through to the void from the game cameras; outward closed chunk hulls; 1 mesh,
1 slot, UV0 + Col, round-trip triangles and bounds equal; UM_FBX_v1 rows conform (pivot row = tray centre).
Outputs: export/SM_TableBase_T2b.fbx, reports/build-report.json, reports/kit-instances.json,
reports/south-profile.json (the rock under the Sarpedon south river mouth, for the waterfall build).
"""

import json
import math
import sys
from pathlib import Path

import bmesh
import bpy
import numpy as np
from mathutils import Vector
from mathutils.bvhtree import BVHTree

HERE = Path(__file__).resolve()
REPO = HERE.parents[4]
sys.path.insert(0, str(HERE.parent))
sys.path.insert(0, str(REPO / "tools" / "art" / "env_kit"))
import k_blender as K  # noqa: E402
import tray_t2b_layout as LAY  # noqa: E402

S, r = K.S, K.r
SCHEMA = "unmatched.table-base-t2b.build-report/1"


def hull(points):
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
    bm = bmesh.new()
    vs = [bm.verts.new(Vector(v)) for v in verts]
    for t in tris:
        try:
            bm.faces.new([vs[i] for i in t])
        except ValueError:
            pass
    for co, no in (((hx_in, 0, 0), (1, 0, 0)), ((-hx_in, 0, 0), (-1, 0, 0)),
                   ((0, hy_in, 0), (0, 1, 0)), ((0, -hy_in, 0), (0, -1, 0))):
        if not bm.verts:
            break
        geom = bm.verts[:] + bm.edges[:] + bm.faces[:]
        bmesh.ops.bisect_plane(bm, geom=geom, plane_co=co, plane_no=no, clear_outer=True, dist=1e-6)
    z = max((v.co.z for v in bm.verts), default=None)
    bm.free()
    return z


def box_uv(p, n, tile, off):
    ax = int(np.argmax(np.abs(n)))
    if ax == 0:
        u, v = p[1] * math.copysign(1.0, n[0]), p[2]
    elif ax == 1:
        u, v = -p[0] * math.copysign(1.0, n[1]), p[2]
    else:
        u, v = p[0] * math.copysign(1.0, n[2]), p[1]
    return (u / tile + off[0], v / tile + off[1])


def smoothstep(e0, e1, x):
    t = np.clip((np.asarray(x, dtype=np.float64) - e0) / (e1 - e0), 0.0, 1.0)
    return t * t * (3.0 - 2.0 * t)


def value_noise3(p, cell, seed):
    """Deterministic 3D value noise in [0, 1] (trilinear, smooth) at points p (N x 3, uu)."""
    q = np.asarray(p, dtype=np.float64) / cell
    i0 = np.floor(q).astype(np.int64)
    f = q - i0
    f = f * f * (3 - 2 * f)

    def h(ix, iy, iz):
        v = (ix * 73856093) ^ (iy * 19349663) ^ (iz * 83492791) ^ (seed * 2654435761)
        v = (v ^ (v >> 13)) * 1274126177
        return ((v ^ (v >> 16)) & 0xFFFF) / 65535.0
    out = 0.0
    for dx in (0, 1):
        for dy in (0, 1):
            for dz in (0, 1):
                w = ((f[:, 0] if dx else 1 - f[:, 0]) * (f[:, 1] if dy else 1 - f[:, 1]) * (f[:, 2] if dz else 1 - f[:, 2]))
                out = out + w * h(i0[:, 0] + dx, i0[:, 1] + dy, i0[:, 2] + dz)
    return out


def corner_colors(P, pts, n, chunk_rand, top_z):
    """Per-corner (R moss, G chunk random, B depth, A 1) for the corners pts (3 x 3) of a face with normal n."""
    vc = P["vertex_color"]
    up = float(smoothstep(vc["moss_up_min"], vc["moss_up_full"], n[2]))
    z = pts[:, 2]
    height = smoothstep(vc["moss_bottom_z"], vc["moss_top_z"], z)
    noise = value_noise3(pts, float(vc["noise_uu"]), int(P["kit"]["seed"]))
    moss = np.clip(height * (float(vc["moss_side_floor"]) + (1.0 - float(vc["moss_side_floor"])) * up)
                   + float(vc["noise_amount"]) * (noise - 0.5) * 2.0 * height, 0.0, 1.0)
    depth = np.clip((top_z - z) / float(vc["depth_ref_uu"]), 0.0, 1.0)
    return [(float(moss[i]), float(chunk_rand), float(depth[i]), 1.0) for i in range(3)]


def build_geometry(P, lay):
    tray, kit = P["tray"], P["kit"]
    top_z = float(tray["top_z"])
    hx, hy = lay["half_bx"], lay["half_by"]
    rim = float(tray["rim_uu"])
    tile = float(kit["tile_uu"])
    hulls = {k: [hull(s["points"]) for s in lay["library"][k]] for k in LAY.KINDS}
    V, F, FUV, FKIND, FCOL = [], [], [], [], []
    inst_rows, corrected, vol_bad = [], 0, 0
    rng = np.random.default_rng([kit["seed"], 9])

    def add(verts, tris, kind, off, chunk_rand, tile_k=1.0, colorize=True):
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
            if colorize:
                FCOL.append(corner_colors(P, np.array([a, b, c]), n, chunk_rand, top_z))
            else:
                d = np.clip((top_z - np.array([a[2], b[2], c[2]])) / float(P["vertex_color"]["depth_ref_uu"]), 0, 1)
                FCOL.append([(0.0, 0.5, float(d[i]), 1.0) for i in range(3)])

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
        # outward hull check (signed volume in .blend coordinates)
        vol = sum(float(np.dot(wv[t[0]], np.cross(wv[t[1]], wv[t[2]]))) / 6.0 for t in ht)
        vol_bad += vol <= 0
        off = (float(rng.random()), float(rng.random()))
        add(wv, ht, inst["kind"], off, float(rng.random()))
        sc, an = LAY.uniform_scale(M)
        inst_rows.append({"i": ii, "placement": inst["placement"], "module": inst["module"], "chunk": inst["chunk"],
                          "row": inst["row"], "kind": inst["kind"], "variant": inst["variant"], "scale": round(sc, 6),
                          "anisotropy": an, "yawDeg": round(math.degrees(math.atan2(M[1, 0], M[0, 0])), 3),
                          "posUU": [round(float(v), 3) for v in M[:3, 3]], "rimDropUU": round(dz, 3),
                          "uvOffset": [round(off[0], 4), round(off[1], 4)], "hullTris": len(ht),
                          "volumeUU3": round(vol, 1)})
    ci, zb = float(kit["core_inset_uu"]), float(kit["core_bottom_z"])
    cx, cy = hx - ci, hy - ci
    cv = np.array([[-cx, -cy, top_z], [cx, -cy, top_z], [cx, cy, top_z], [-cx, cy, top_z],
                   [-cx, -cy, zb], [cx, -cy, zb], [cx, cy, zb], [-cx, cy, zb]], dtype=np.float64)
    ct = [(0, 4, 5), (0, 5, 1), (1, 5, 6), (1, 6, 2), (2, 6, 7), (2, 7, 3), (3, 7, 4), (3, 4, 0), (4, 7, 6), (4, 6, 5)]
    add(cv, ct, "core", (0.0, 0.0), 0.5, colorize=False)
    tv = np.array([[-hx, -hy, top_z], [hx, -hy, top_z], [hx, hy, top_z], [-hx, hy, top_z]], dtype=np.float64)
    add(tv, [(0, 1, 2), (0, 2, 3)], "top", (0.0, 0.0), 0.5, tile_k=2.0, colorize=False)
    return np.vstack(V), F, FUV, FKIND, FCOL, inst_rows, corrected, vol_bad


def make_object(P, verts_uu, faces, fuv, fcol):
    me = bpy.data.meshes.new(P["asset_name"])
    me.from_pydata((verts_uu / 100.0).tolist(), [], faces)
    me.update()
    for p in me.polygons:
        p.use_smooth = False
    uvl = me.uv_layers.new(name="UVMap")
    uvl.data.foreach_set("uv", [c for tri in fuv for uv in tri for c in uv])
    attr = me.color_attributes.new("Col", "FLOAT_COLOR", "CORNER")
    lin = []
    for cols in fcol:
        for c in cols:
            rgb = K.srgb_to_linear(np.array(c[:3]))
            lin.extend([float(rgb[0]), float(rgb[1]), float(rgb[2]), float(c[3])])
    attr.data.foreach_set("color", lin)
    me.color_attributes.active_color = attr
    me.validate(clean_customdata=False)
    obj = bpy.data.objects.new(P["asset_name"], me)
    bpy.context.scene.collection.objects.link(obj)
    return obj


def material(P):
    d = REPO / P["rock_textures"]["dir"]
    pre = P["rock_textures"]["prefix"]
    imgs = {}
    for key, cs in (("BC", "sRGB"), ("N", "Non-Color"), ("ORM", "Non-Color")):
        path = d / ("%s_%s.png" % (pre, key))
        if not path.is_file():
            raise SystemExit("missing %s (the T2 rock set)" % path)
        img = bpy.data.images.load(str(path))
        img.colorspace_settings.name = cs
        imgs[key] = img
    return S.build_material(P["material_name"], imgs["BC"], imgs["N"], imgs["ORM"])


def game_cameras(P):
    pv, tray = P["preview"], P["tray"]
    oy = -float(tray["offset_y_ue"])
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
    """tray_t2_build.see_through: required rays (top-0.5 .. -55) that miss AND then run through the inside of the tray
    are holes (the void would show where rock must be); deep rays (-100 / -160 / -200) measure how open the bottom is."""
    zb = float(P["kit"]["core_bottom_z"])

    def enters_inside(o, d, t0):
        for k in range(1, 81):
            q = o + d * (t0 + 5.0 * k)
            if abs(q.x) < hx - 0.5 and abs(q.y) < hy - 0.5 and zb < q.z < top_z:
                return True
        return False
    req = [top_z - 0.5, top_z - 3.0, -15.0, -30.0, -45.0, -55.0]
    deep = [-100.0, -160.0, -200.0]
    res = {"requiredDepthsZ": req, "deepDepthsZ": deep, "cameras": {}}
    total = 0
    for name, o, _t in game_cameras(P):
        miss, sil, n_req, open_deep, n_deep, where = 0, 0, 0, 0, 0, []
        for (x, y), _n, side in perimeter_points(hx, hy, 4.0):
            for tz, required in [(z, True) for z in req] + [(z, False) for z in deep]:
                d = Vector((x, y, tz)) - o
                hit = bvh.ray_cast(o, d.normalized(), d.length + 600.0)[0]
                if required:
                    n_req += 1
                    if hit is None and enters_inside(o, d.normalized(), d.length):
                        miss += 1
                        if len(where) < 12:
                            where.append([side, round(x, 1), round(y, 1), round(tz, 1)])
                    elif hit is None:
                        sil += 1
                else:
                    n_deep += 1
                    open_deep += hit is None
        total += miss
        res["cameras"][name] = {"origin": [r(v, 2) for v in o], "requiredRays": n_req, "holes": miss, "holesAt": where,
                                "silhouetteMisses": sil, "deepRays": n_deep,
                                "deepOpenFraction": r(open_deep / max(n_deep, 1), 4)}
    res["missedTotal"] = total
    return res


def south_profile(P, verts, faces, fkind):
    """Outward rock extent beyond the near/south tray edge (UE +Y = .blend -x) for UE X in x_ue, per z bin.
    Dense barycentric samples on the rock triangles (not only vertices). UE X = -blend y."""
    cfg = P["south_profile"]
    hx = float(P["tray"]["half_y_ue"])  # blend x half = UE Y half
    x0, x1 = (float(v) for v in cfg["x_ue"])
    step = float(cfg["z_step_uu"])
    T = verts[np.array([f for f, k in zip(faces, fkind) if k in LAY.KINDS])]
    g = []
    n = 6
    for i in range(n + 1):
        for j in range(n + 1 - i):
            g.append((i / n, j / n, 1 - i / n - j / n))
    g = np.array(g)
    pts = np.einsum("sk,tkc->tsc", g, T).reshape(-1, 3)
    ue_x = -pts[:, 1]
    outward = -pts[:, 0] - hx
    sel = (ue_x >= x0) & (ue_x <= x1) & (outward > -80.0)
    pts, outward = pts[sel], outward[sel]
    zmin, zmax = float(pts[:, 2].min()), float(pts[:, 2].max())
    bins = []
    z = math.floor(zmax / step) * step + step
    while z > zmin - step:
        m = (pts[:, 2] <= z) & (pts[:, 2] > z - step)
        if m.any():
            bins.append({"zTop": r(z, 2), "zBottom": r(z - step, 2), "maxOutwardUU": r(float(outward[m].max()), 3)})
        z -= step
    return {"schema": "unmatched.table-base-t2b.south-profile/1",
            "note": "outwardUU = distance beyond the near/south tray edge (board UE Y = offsetY + halfY = %.1f); "
                    "frame: tray mesh, so board UE Y = edge + outward" % (float(P["tray"]["offset_y_ue"]) + hx),
            "edgeBoardUeY": r(float(P["tray"]["offset_y_ue"]) + hx, 3), "xRangeUeUU": [x0, x1], "zStepUU": step,
            "bins": bins, "maxOutwardTopBandUU": r(max(b["maxOutwardUU"] for b in bins if b["zTop"] > -40.0), 3),
            "lowestZUU": r(zmin, 3)}


def measure(P, lay, verts, faces, fkind):
    tray = P["tray"]
    top_z = float(tray["top_z"])
    hx, hy = lay["half_bx"], lay["half_by"]
    rim = float(tray["rim_uu"])
    lo, hi = verts.min(0), verts.max(0)
    by_kind = {}
    for f, k in zip(faces, fkind):
        by_kind[k] = by_kind.get(k, 0) + len(f) - 2
    top_ids = [i for i, k in enumerate(fkind) if k == "top"]
    tv = verts[sorted({v for i in top_ids for v in faces[i]})]
    zin = max_z_inside(verts, faces, hx - rim, hy - rim)
    ox, oy = np.abs(verts[:, 0]) - hx, np.abs(verts[:, 1]) - hy
    along_x = np.abs(verts[:, 1]) < hy - 60.0
    along_y = np.abs(verts[:, 0]) < hx - 60.0
    ov_side = max(float(ox[along_x].max()), float(oy[along_y].max()))
    ov_all = float(np.maximum(ox, oy).max())
    ue_lo = [-hi[1], -hi[0], lo[2]]
    ue_hi = [-lo[1], -lo[0], hi[2]]
    rows = {}
    for k in LAY.KINDS:
        ids = [i for i, kk in enumerate(fkind) if kk == k]
        vv = verts[sorted({v for i in ids for v in faces[i]})]
        rows[k] = {"triangles": by_kind.get(k, 0), "zRange": [r(vv[:, 2].min(), 2), r(vv[:, 2].max(), 2)]}
    return {"triangles": sum(len(f) - 2 for f in faces), "trianglesByPart": by_kind, "vertices": int(len(verts)),
            "boundsUeUU": {"min": [r(v, 3) for v in ue_lo], "max": [r(v, 3) for v in ue_hi],
                           "size": [r(ue_hi[i] - ue_lo[i], 3) for i in range(3)]},
            "flatTop": {"zUU": sorted({r(v, 4) for v in tv[:, 2]}),
                        "rectUeUU": {"halfX": r(tv[:, 1].max(), 3), "halfY": r(tv[:, 0].max(), 3)},
                        "rectBlendMin": [r(v, 3) for v in tv.min(0)[:2]]},
            "lip": {"topZMaxUU": r(hi[2], 3), "rimUU": rim,
                    "maxZInsideRimBandInnerRectUU": None if zin is None else r(zin, 4)},
            "overhangUU": {"sidesMax": r(ov_side, 3), "cornersMax": r(ov_all, 3)},
            "depthBelowTopUU": r(top_z - lo[2], 3), "lowestZUU": r(lo[2], 3), "rows": rows}


def module_stats(P, lay):
    """Per-module triangle count (hull triangles of its chunks) and its extent: the modular budget (<= 40k each)."""
    tris = {k: [len(hull(s["points"])[1]) for s in lay["library"][k]] for k in LAY.KINDS}
    out = []
    for m in lay["sides"] + lay["corners"]:
        pts = LAY.module_points(lay["library"], m)
        out.append({"type": m["type"], "variant": m["index"], "chunks": len(m["chunks"]),
                    "triangles": int(sum(tris[c["kind"]][c["variant"]] for c in m["chunks"])),
                    "lengthUU": m.get("length"), "legUU": m.get("legUU"),
                    "zRange": [r(pts[:, 2].min(), 2), r(pts[:, 2].max(), 2)]})
    return out


def main():
    P = K.load_params(K.script_args()[0])
    run = P["_run"]
    tray, kit = P["tray"], P["kit"]
    top_z = float(tray["top_z"])
    bpy.ops.wm.read_factory_settings(use_empty=True)
    lay = LAY.build(P)
    verts, faces, fuv, fkind, fcol, inst_rows, corrected, vol_bad = build_geometry(P, lay)
    meas = measure(P, lay, verts, faces, fkind)
    bvh = BVHTree.FromPolygons([Vector(v) for v in verts], faces, all_triangles=True)
    holes = see_through(P, bvh, lay["half_bx"], lay["half_by"], top_z)
    sp = south_profile(P, verts, faces, fkind)
    mods = module_stats(P, lay)

    obj = make_object(P, verts, faces, fuv, fcol)
    obj.data.materials.append(material(P))
    blend = K.save_scratch_blend(P, P["asset_name"])
    fbx = run / "export" / ("%s.fbx" % P["asset_name"])
    exp = K.export(obj, fbx)
    rect_ok = (meas["flatTop"]["zUU"] == [r(top_z, 4)]
               and abs(meas["flatTop"]["rectUeUU"]["halfX"] - float(tray["half_x_ue"])) < 0.01
               and abs(meas["flatTop"]["rectUeUU"]["halfY"] - float(tray["half_y_ue"])) < 0.01)
    exp["um_fbx_v1_conformance"].append({"setting": "Pivot: tray centre (0,0) = centre of the flat top at top_z (T2 rule)",
                                         "standard": True, "used": rect_ok, "conforms": rect_ok})
    expected_tris = S.triangles(obj)
    col = np.array([c for cols in fcol for c in cols])
    col_stats = {"R_moss": {"mean": r(col[:, 0].mean(), 4), "fractionAbove0.5": r((col[:, 0] > 0.5).mean(), 4)},
                 "G_chunkRandom": {"min": r(col[:, 1].min(), 4), "max": r(col[:, 1].max(), 4)},
                 "B_depth": {"min": r(col[:, 2].min(), 4), "max": r(col[:, 2].max(), 4)}}
    # moss is on the upper lip: the mean R of corners above -20 vs below -80
    zc = np.array([verts[i][2] for f in faces for i in f])
    col_stats["R_moss"]["meanAboveZ-20"] = r(col[zc > -20, 0].mean(), 4)
    col_stats["R_moss"]["meanBelowZ-80"] = r(col[zc < -80, 0].mean(), 4)
    rt = K.roundtrip(fbx, expected_tris, [P["material_name"]], meas["boundsUeUU"])
    an = max(row["anisotropy"] for row in inst_rows)
    checks = {
        "triangles_within_budget": meas["triangles"] <= int(tray["max_triangles"]),
        "module_triangles_within_budget": all(m["triangles"] <= int(tray["max_triangles"]) for m in mods),
        "instances_uniform_scale_only": abs(an - 1.0) < 1e-9,
        "chunk_hulls_outward": vol_bad == 0,
        "flat_top_is_the_tray_rectangle": rect_ok,
        "nothing_above_top_inward_of_rim": (meas["lip"]["maxZInsideRimBandInnerRectUU"] is not None
                                            and meas["lip"]["maxZInsideRimBandInnerRectUU"] <= top_z + 0.01),
        "lip_top_within_max": meas["lip"]["topZMaxUU"] <= float(tray["lip_top_z_max"]) + 1e-6,
        "overhang_sides_within_max": meas["overhangUU"]["sidesMax"] <= float(tray["overhang_max_uu"]),
        "overhang_corners_within_max": meas["overhangUU"]["cornersMax"] <= float(tray["overhang_corner_max_uu"]),
        "depth_in_range": float(tray["depth_min_uu"]) <= meas["depthBelowTopUU"] <= float(tray["depth_max_uu"]),
        "no_see_through_to_void": holes["missedTotal"] == 0,
        "moss_on_upper_lip": col_stats["R_moss"]["meanAboveZ-20"] > 0.4 and col_stats["R_moss"]["meanBelowZ-80"] < 0.05,
        "single_mesh": rt["mesh_objects"] == 1,
        "triangles_preserved": rt["triangles"] == expected_tris,
        "one_material_slot": rt["material_slots"] == [P["material_name"]],
        "uv0_present": bool(rt["uv_layers"]),
        "vertex_colors_present": rt["color_attributes"] == ["Col"],
        "roundtrip_bounds_match_ue_frame": rt["ue_frame_matches_build"],
        "um_fbx_v1_conforms": all(c["conforms"] for c in exp["um_fbx_v1_conformance"]),
    }
    report = {
        "schema": SCHEMA, "status": "measured", "asset": "ASSET-TABLE-BASE-001 / SM_TableBase_T2b",
        "claims": {"art_accepted": False, "game_ready": False, "technically_imported": False},
        "blender_version": bpy.app.version_string,
        "script_sha256_lf": S.text_sha256_lf(HERE),
        "layout_sha256_lf": S.text_sha256_lf(HERE.parent / "tray_t2b_layout.py"),
        "helpers": {"k_blender": S.text_sha256_lf(K.HERE), "static_prop_candidate": S.text_sha256_lf(K.SPC_PATH)},
        "params": {"path": K.rel(P["_params_path"]), "sha256": S.sha256(P["_params_path"])},
        "contract": {
            "ue": {"folder": "/Game/PipelineCandidates/TableBase/T2b", "mesh": P["asset_name"],
                   "material_instance": "MI_TableBase_T2b (parent: a new M_TableBase_T2b = the T2 rock graph + a moss "
                                        "lerp by VertexColor.R; MI params MossTint/MossAmount per map)",
                   "textures": ["T_TableBase_T2_BC", "T_TableBase_T2_N", "T_TableBase_T2_ORM (reused, already in UE)",
                                "T_TableBase_T2b_Moss_BC", "T_TableBase_T2b_Moss_N"],
                   "import": "extend tools/art/env_kit/ue_import_tray_t2.py (legacy FbxFactory, import_uniform_scale 1.0, "
                             "vertex_color_import_option REPLACE, normals imported, no collision, Nanite off)"},
            "placement": "the same as SM_TableBase_T2: board actor component at (0, tray.offsetY, 0), yaw 0, scale 1",
            "axes": "UE X = -blend y (long side), UE Y = -blend x; read-back frame = UE with Y negated",
            "uv": "UV0 world box projection, %.0f uu per repeat (Wrap)" % float(kit["tile_uu"]),
            "vertexColor": P["vertex_color"]["note"]},
        "kit": {
            "library": {k: [{"variant": i, "w": r(s["w"], 2), "t": r(s["t"], 2), "h": r(s["h"], 2),
                             "points": int(len(s["points"])), "extra": s["extra"]}
                            for i, s in enumerate(lay["library"][k])] for k in LAY.KINDS},
            "modules": mods,
            "perimeter": lay["perimeter"]["sides"],
            "modulePlacements": len(lay["perimeter"]["placements"]),
            "chunkInstances": len(inst_rows),
            "instancesByRow": {k: sum(1 for x in inst_rows if x["row"] == k) for k in [rw["name"] for rw in kit["rows"]]},
            "instanceScaleRange": [r(min(x["scale"] for x in inst_rows), 4), r(max(x["scale"] for x in inst_rows), 4)],
            "instanceAnisotropyMax": an, "capsMovedDownForRim": corrected, "hullsNotOutward": vol_bad,
            "instancesFile": "reports/kit-instances.json"},
        "geometry": meas, "seeThrough": holes, "vertexColorStats": col_stats,
        "southProfile": {"file": "reports/south-profile.json", "maxOutwardTopBandUU": sp["maxOutwardTopBandUU"]},
        "exports": [{**exp, "name": P["asset_name"], "triangles": expected_tris}],
        "roundtrip": rt, "blend_scratch": blend,
    }
    report["checks"] = {k: bool(v) for k, v in checks.items()}
    report["checks_passed"] = all(report["checks"].values())
    K.write_json(run / "reports" / "build-report.json", report)
    K.write_json(run / "reports" / "south-profile.json", sp)
    (run / "reports" / "kit-instances.json").write_text(
        json.dumps({"schema": "unmatched.table-base-t2b.instances/1", "frame": ".blend uu (UE X = -y, UE Y = -x)",
                    "placements": lay["perimeter"]["placements"], "instances": inst_rows}, indent=1) + "\n",
        encoding="utf-8")
    print("T2B-BUILD", json.dumps(report["checks"]))
    print("T2B-BUILD-SUMMARY tris=%d instances=%d lipTop=%.2f depth=%.1f overhang=%.1f/%.1f miss=%d southTop=%.1f fbx=%s" % (
        meas["triangles"], len(inst_rows), meas["lip"]["topZMaxUU"], meas["depthBelowTopUU"],
        meas["overhangUU"]["sidesMax"], meas["overhangUU"]["cornersMax"], holes["missedTotal"],
        sp["maxOutwardTopBandUU"], exp["sha256"][:12]))
    if not report["checks_passed"]:
        raise SystemExit(1)


main()
