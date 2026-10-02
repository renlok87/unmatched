"""ENV-MAPS P8.1 ship (ASSET-ENV-S-SHIP-001): Poly Haven CC0 dutch_ship_large_01 fitted to the painted ship by C0 pixels.

Two stages (one file, two interpreters):

  1. prep (Blender headless):
       blender -b --factory-startup --python-exit-code 1 --python tools/art/concept_scene/ship_build.py -- prep
     imports C:/tmp/envmaps-research/p8/polyhaven/dutch_ship_large_01/*.gltf (CC0, sha256 in that folder's manifest),
     keeps the hull and the thick spars of the rigging (masts / yards: loose parts whose 2nd principal std >=
     sparMinStdM and length >= sparMinLenM; ropes, blocks and sails are dropped - the painting shows them, a decimated
     rope reads as noise), decimates (collapse) to the params' budgets and writes the model-frame arrays (UE numbers,
     uu) to <work>/ship_raw.npz.
  2. fit (system Python):
       python -B tools/art/concept_scene/ship_build.py fit
     fits yaw / position / scale / waterline of the model to the painted hull region (params ship.targetPx, C0 px:
     the hull + deck between the island dock line and the far rail, read on the de-lit plate) by maximising the C0
     silhouette IoU (Nelder-Mead from two bow directions, coarse then fine raster), cuts the far hull below the deck
     (invisible from every game camera: faces of the far side under deckCutZ), puts the pivot at the waterline below
     the hull centre and writes <work>/SM_Env_S_Ship.pre.npz (UE numbers local to the pivot, yaw 0, scale 1) +
     the silhouette overlay on the de-lit plate (out of git, C0 frame) and reports/ship-fit.json (git).

The FBX export (UM_FBX_v1, Smart UV atlas for the bake) is cs_blender.py 'export' (run_scene.py drives everything).
"""
from __future__ import annotations

import json
import math
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
try:
    import bpy  # noqa: F401
    IN_BLENDER = True
except ImportError:
    IN_BLENDER = False

if IN_BLENDER:
    import numpy as np
    sys.path.insert(0, str(HERE))
    import cs_blender as CBL  # noqa: E402

    def prep():
        P = json.loads((HERE / "scene-params.sarpedon.json").read_text(encoding="utf-8"))["ship"]
        work = Path(P["work"])
        bpy.ops.wm.read_factory_settings(use_empty=True)
        bpy.ops.import_scene.gltf(filepath=P["source"])
        objs = {o.name: o for o in bpy.context.scene.objects if o.type == "MESH"}
        out = {}
        hull = next(o for n, o in objs.items() if n.endswith("_hull"))
        rig = next(o for n, o in objs.items() if n.endswith("_rigging"))
        # spars: loose parts of the rigging by principal-axis thickness
        import bmesh
        bm = bmesh.new()
        bm.from_mesh(rig.data)
        bm.transform(rig.matrix_world)
        bm.verts.ensure_lookup_table()
        comp = [-1] * len(bm.verts)
        parts = []
        for v in bm.verts:
            if comp[v.index] >= 0:
                continue
            stack, cur = [v], []
            comp[v.index] = len(parts)
            while stack:
                u = stack.pop()
                cur.append(u.index)
                for e in u.link_edges:
                    w = e.other_vert(u)
                    if comp[w.index] < 0:
                        comp[w.index] = len(parts)
                        stack.append(w)
            parts.append(cur)
        keep = set()
        for i, idx in enumerate(parts):
            co = np.array([bm.verts[j].co[:] for j in idx])
            if len(co) < 8:
                continue
            c = co - co.mean(0)
            sv = np.linalg.svd(c, compute_uv=False) / math.sqrt(len(co))
            length = float(np.ptp(c @ np.linalg.svd(c, full_matrices=False)[2][0]))
            if sv[1] >= P["sparMinStdM"] and length >= P["sparMinLenM"]:
                keep.add(i)
        drop = [f for f in bm.faces if comp[f.verts[0].index] not in keep]
        bmesh.ops.delete(bm, geom=drop, context="FACES")
        loose = [v for v in bm.verts if not v.link_faces]
        bmesh.ops.delete(bm, geom=loose, context="VERTS")
        me = bpy.data.meshes.new("spars")
        bm.to_mesh(me)
        bm.free()
        spars = bpy.data.objects.new("spars", me)
        bpy.context.scene.collection.objects.link(spars)
        stats = {"sparParts": len(keep), "rigParts": len(parts)}
        for key, o, budget in (("hull", hull, P["hullPrepTris"]), ("spars", spars, P["sparTris"])):
            tris = sum(len(p.vertices) - 2 for p in o.data.polygons)
            if tris > budget:
                mod = o.modifiers.new("dec", "DECIMATE")
                mod.decimate_type = "COLLAPSE"
                mod.ratio = budget / tris
                mod.use_collapse_triangulate = True
                bpy.context.view_layer.objects.active = o
                o.select_set(True)
                bpy.ops.object.modifier_apply(modifier=mod.name)
            V, F, UV, MAT = CBL.object_arrays(o, world=True)
            out[key + "_V"], out[key + "_F"] = V, F
            stats[key + "Tris"] = int(len(F))
            stats[key + "SourceTris"] = int(tris)
        CBL.save_npz(work / "ship_raw.npz", out)
        (work / "ship_raw.json").write_text(json.dumps(stats, indent=1), encoding="utf-8")
        print("SHIP-PREP", stats)

    if __name__ == "__main__":
        import k_blender as K  # noqa: E402  (path set by cs_blender)
        a = K.script_args()
        if a and a[0] == "prep":
            prep()
        else:
            raise SystemExit("usage: ship_build.py -- prep")

else:
    import numpy as np
    from PIL import Image, ImageDraw
    from scipy.optimize import minimize

    sys.path.insert(0, str(HERE))
    import cs_common as CS  # noqa: E402

    def rot(yaw_deg):
        a = math.radians(yaw_deg)
        return np.array([[math.cos(a), -math.sin(a), 0.0], [math.sin(a), math.cos(a), 0.0], [0.0, 0.0, 1.0]])

    def transform(V, x):
        """model (UE numbers, uu, waterline Z 0) -> board: scale s, yaw, translate (tx, ty, zw)."""
        tx, ty, yaw, s, zw = x
        return (V * s) @ rot(yaw).T + np.array([tx, ty, zw])

    def load_raw(P):
        d = np.load(Path(P["work"]) / "ship_raw.npz")
        V = np.vstack([d["hull_V"], d["spars_V"]])
        F = np.vstack([d["hull_F"], d["spars_F"] + len(d["hull_V"])])
        part = np.r_[np.zeros(len(d["hull_F"]), int), np.ones(len(d["spars_F"]), int)]
        return V, F, part

    class Fitter:
        def __init__(self, P, V, F, scale_px):
            self.P, self.V, self.F = P, V, F
            self.cam = CS.cam0()
            self.rect = CS.RECT_B
            self.w = int((self.rect[2] - self.rect[0]) * scale_px)
            self.h = int((self.rect[3] - self.rect[1]) * scale_px)
            self.target = CS.poly_mask(P["targetPx"], self.w, self.h, self.rect)
            self.island = CS.poly_mask(CS.spec()["geometry"]["islandMatte"]["poly"], self.w, self.h, self.rect)
            self.hullF = F

        def mask(self, x):
            Pw = transform(self.V, x)
            depth, _ = CS.raster_tris(self.cam, Pw, self.F, self.w, self.h, rect=self.rect)
            return np.isfinite(depth)

        def score(self, x):
            m = self.mask(x)
            inter = (m & self.target).sum()
            union = (m | self.target).sum()
            # the ship must not cover the island dock / frame side of the target line
            spill = (m & ~self.target & self.island).sum() / max(self.target.sum(), 1)
            return float(inter / max(union, 1)) - self.P["spillWeight"] * float(spill)

    def fit(P):
        V, F, part = load_raw(P)
        hullF = F[part == 0]
        best = None
        log = []
        zw = float(P["waterlineZ"])
        for yaw0 in P["yawStartsDeg"]:
            x0 = np.array([*P["start"]["xy"], yaw0, P["start"]["scale"]], float)
            for stage, (spx, it) in enumerate(((0.25, P["iterCoarse"]), (0.5, P["iterFine"]))):
                fz = Fitter(P, V, hullF, spx)
                steps = np.array(P["simplexSteps"], float) / (1 + stage)
                sim = [x0] + [x0 + np.eye(4)[k] * steps[k] for k in range(4)]
                res = minimize(lambda x: -fz.score(np.r_[x, zw]), x0, method="Nelder-Mead",
                               options={"initial_simplex": np.array(sim), "maxiter": it, "xatol": 0.5, "fatol": 1e-4})
                x0 = res.x
                log.append({"yawStart": yaw0, "stage": stage, "iou": round(-float(res.fun), 4),
                            "x": [round(float(v), 3) for v in res.x], "evals": int(res.nfev)})
            if best is None or -res.fun > best[0]:
                best = (-float(res.fun), np.r_[x0, zw])
        return best, log, (V, F, part)

    def ray_mesh(o, d, Pw, F):
        """Nearest hit distance of the ray o + t d with triangles (Moller-Trumbore, vectorised); inf if none."""
        a, b, c = Pw[F[:, 0]], Pw[F[:, 1]], Pw[F[:, 2]]
        e1, e2 = b - a, c - a
        pv = np.cross(d, e2)
        det = np.einsum("ij,ij->i", e1, pv)
        ok = np.abs(det) > 1e-12
        inv = np.where(ok, 1.0 / np.where(ok, det, 1.0), 0.0)
        tv = o - a
        u = np.einsum("ij,ij->i", tv, pv) * inv
        qv = np.cross(tv, e1)
        v = (qv @ d) * inv
        t = np.einsum("ij,ij->i", e2, qv) * inv
        hit = ok & (u >= 0) & (v >= 0) & (u + v <= 1) & (t > 1)
        return float(t[hit].min()) if hit.any() else math.inf

    def cylinder(foot, top, radius, seg=12):
        """Closed tapered cylinder (top radius 0.7) from foot to top; UVs filled later by the Smart UV atlas."""
        ax = top - foot
        L = np.linalg.norm(ax)
        ax = ax / L
        ref = np.array([1.0, 0.0, 0.0]) if abs(ax[0]) < 0.9 else np.array([0.0, 1.0, 0.0])
        u = np.cross(ax, ref)
        u /= np.linalg.norm(u)
        v = np.cross(ax, u)
        ang = np.arange(seg) * 2 * math.pi / seg
        ring0 = foot + radius * (np.cos(ang)[:, None] * u + np.sin(ang)[:, None] * v)
        ring1 = top + 0.7 * radius * (np.cos(ang)[:, None] * u + np.sin(ang)[:, None] * v)
        V = np.vstack([ring0, ring1, top[None]])
        F = []
        for i in range(seg):
            j = (i + 1) % seg
            F += [[i, j, seg + j], [i, seg + j, seg + i], [seg + i, seg + j, 2 * seg]]
        F = np.array(F)
        # outward check (right-handed math on the UE numbers): the side normal must point away from the axis
        n = np.cross(V[F[0, 1]] - V[F[0, 0]], V[F[0, 2]] - V[F[0, 0]])
        if n @ (V[F[0]].mean(0) - foot - ax * ((V[F[0]].mean(0) - foot) @ ax)) < 0:
            F = F[:, ::-1]
        return V, F

    def painted_masts(P, Pw, F):
        """Masts at the painted mast pixels (the model's spars sit elsewhere): foot = C0 ray hit on the fitted hull,
        top = the top pixel's ray on the plane Y = foot Y (the C0 yaw looks along -Y); radius from the painted width."""
        cam = CS.cam0()
        out, info = [], []
        for m in P["masts"]:
            d = cam.rays(np.array(float(m["footPx"][0])), np.array(float(m["footPx"][1])))
            d = d / np.linalg.norm(d)
            t = ray_mesh(cam.pos, d, Pw, F)
            on = "hull"
            if not math.isfinite(t):  # off the fitted hull (the painted stern lies on the island dock): the plateau
                t = (P["dockZ"] - cam.pos[2]) / d[2]
                on = "plateau"
            foot = cam.pos + t * d - np.array([0.0, 0.0, m.get("sinkUU", 10.0)])
            # vertical mast: the height whose top projects onto the painted top row (bisection)
            lo_h, hi_h = 10.0, 3000.0
            for _ in range(60):
                mid = (lo_h + hi_h) / 2
                if cam.project(foot + np.array([0.0, 0.0, mid]))[0][1] > m["topPx"][1]:
                    lo_h = mid
                else:
                    hi_h = mid
            top = foot + np.array([0.0, 0.0, lo_h])
            depth = float((foot - cam.pos) @ cam.fwd)
            radius = m["widthPx"] / 2 * depth / cam.f_px
            V, Fm = cylinder(foot, top, radius)
            out.append((V, Fm))
            info.append({"id": m["id"], "on": on, "foot": [round(float(v), 1) for v in foot], "top": [round(float(v), 1) for v in top],
                         "radiusUU": round(radius, 1)})
        return out, info

    def hull_section(Pw, F, z, nrm, centre):
        """Near-side points of the hull section at height z (board XY): the triangle edges crossing z on the side
        facing the board (nrm)."""
        a = Pw[F]
        pts = []
        for i, j in ((0, 1), (1, 2), (2, 0)):
            za, zb = a[:, i, 2], a[:, j, 2]
            m = (za - z) * (zb - z) < 0
            t = (z - za[m]) / (zb[m] - za[m])
            pts.append(a[m, i, :2] + t[:, None] * (a[m, j, :2] - a[m, i, :2]))
        pts = np.vstack(pts)
        side = (pts - centre) @ nrm
        return pts[side > 0]

    def cut_and_pivot(P, V, F, part, x):
        """Board-space mesh: the model spars dropped, the far hull below the deck removed, the painted masts added,
        pivot at the waterline below the hull centre."""
        Pw = transform(V, x)
        tx, ty, yaw, s, zw = x
        axis = rot(yaw) @ np.array([0.0, 1.0, 0.0])  # model length axis (UE Y) in board space
        nrm = np.array([-axis[1], axis[0], 0.0])
        if nrm @ (np.array([0.0, 0.0, 0.0]) - np.array([tx, ty, 0.0])) < 0:
            nrm = -nrm  # towards the board
        cen = Pw[F].mean(1)
        side = (cen[:, :2] - np.array([tx, ty])) @ nrm[:2]
        deck_z = zw + P["deckModelZ"] * 100.0 * s
        drop = (part == 1) | ((side < -P["cutKeepUU"]) & (cen[:, 2] < deck_z - P["cutBelowDeckUU"]))
        keepF = F[~drop]
        masts, minfo = painted_masts(P, Pw, F[part == 0])
        Vall, Fall = [Pw], [keepF]
        base = len(Pw)
        for Vm, Fm in masts:
            Vall.append(Vm)
            Fall.append(Fm + base)
            base += len(Vm)
        Pw2 = np.vstack(Vall)
        F2 = np.vstack(Fall)
        part2 = np.r_[np.zeros(len(keepF), int), np.full(len(F2) - len(keepF), 2)]
        used = np.unique(F2)
        remap = -np.ones(len(Pw2), np.int64)
        remap[used] = np.arange(len(used))
        Vb = Pw2[used]
        F2 = remap[F2]
        pivot = np.array([tx, ty, zw])
        dock = hull_section(Vb, F2[part2 == 0], P["dockZ"], nrm[:2], np.array([tx, ty]))
        info = {"droppedTris": int(drop.sum()), "deckZ": round(float(deck_z), 1),
                "nearNormal": [round(float(v), 4) for v in nrm[:2]], "axis": [round(float(v), 4) for v in axis[:2]],
                "masts": minfo}
        return Vb - pivot, F2, part2, pivot, info, dock

    def overlay(P, mesh_board, F, out_png, fz_scale=0.5):
        cam = CS.cam0()
        rect = CS.RECT_B
        w, h = int((rect[2] - rect[0]) * fz_scale), int((rect[3] - rect[1]) * fz_scale)
        img = CS.plate_c0(rect, w, h, CS.DELIT_EXT)
        depth, _ = CS.raster_tris(cam, mesh_board, F, w, h, rect=rect)
        m = np.isfinite(depth)
        out = img.copy()
        out[m] = out[m] * 0.45 + np.array([0.1, 0.9, 1.0]) * 0.55
        im = Image.fromarray(np.clip(out * 255, 0, 255).astype(np.uint8))
        d = ImageDraw.Draw(im)
        k = w / (rect[2] - rect[0])
        tp = [((x - rect[0]) * k, (y - rect[1]) * k) for x, y in P["targetPx"]]
        d.line(tp + tp[:1], fill=(255, 0, 255), width=2)
        fr = [((x - rect[0]) * k, (y - rect[1]) * k) for x, y in ((0, 0), (1920, 0), (1920, 1080), (0, 1080), (0, 0))]
        d.line(fr, fill=(255, 255, 0), width=1)
        Path(out_png).parent.mkdir(parents=True, exist_ok=True)
        im.save(out_png)
        t = CS.poly_mask(P["targetPx"], w, h, rect)
        return {"iou": round(float((m & t).sum() / max((m | t).sum(), 1)), 4),
                "targetCovered": round(float((m & t).sum() / max(t.sum(), 1)), 4),
                "outsideTarget": round(float((m & ~t).sum() / max(t.sum(), 1)), 4)}

    def run_fit():
        allp = CS.params()
        P = allp["ship"]
        cache = Path(P["work"]) / "ship_fit_cache.json"
        key = {"params": {k: P[k] for k in ("targetPx", "spillWeight", "yawStartsDeg", "start", "simplexSteps",
                                            "iterCoarse", "iterFine", "waterlineZ")},
               "raw": CS.sha256(Path(P["work"]) / "ship_raw.npz")}
        V, F, part = load_raw(P)
        old = json.loads(cache.read_text(encoding="utf-8")) if cache.is_file() else {}
        if old.get("key") == key and "--refit" not in sys.argv:
            best, log = (old["iou"], np.array(old["x"])), old["log"]
            print("SHIP-FIT cached", old["x"])
        else:
            best, log, _ = fit(P)
            cache.write_text(json.dumps({"key": key, "iou": best[0], "x": best[1].tolist(), "log": log}), encoding="utf-8")
        x = best[1]
        Vl, F2, part2, pivot, info, dock = cut_and_pivot(P, V, F, part, x)
        # the dock line: the outermost near-side hull section points at the plateau per 60 uu bin along the hull axis
        # (= the outer face of the near bulwark at dockZ), the island's east rim follows it tucked under the hull
        ax, nr = np.array(info["axis"]), np.array(info["nearNormal"])
        c2 = pivot[:2]
        ta, tn = (dock - c2) @ ax, (dock - c2) @ nr
        dock_line = []
        for b in np.arange(np.floor(ta.min() / 60) * 60, ta.max() + 60, 60):
            m = (ta >= b) & (ta < b + 60)
            if m.sum() >= 2:
                i = np.argmax(np.where(m, tn, -np.inf))
                dock_line.append([round(float(v), 1) for v in dock[i]])
        tris = len(F2)
        if tris > P["maxTris"]:
            raise SystemExit(f"ship: {tris} triangles > {P['maxTris']} after the cut (lower hullPrepTris)")
        UV = np.zeros((len(F2), 3, 2))
        mesh = CS.Mesh("SM_Env_S_Ship", Vl, F2, UV, np.zeros(len(F2), int), np.ones(len(F2), bool),
                       ["MI_Env_S_Ship"], pivot)
        mesh.save(Path(P["work"]) / "SM_Env_S_Ship.pre.npz")
        ov = overlay(P, mesh.board(), F2, CS.WORK / "overlays" / "ship-silhouette-c0.png")
        hullsel = part2 == 0
        Pb = mesh.board()
        hb = Pb[np.unique(F2[hullsel])]
        rep = {"schema": "unmatched.env-s-ship.fit/1",
               "status": "измерено (C0 silhouette fit on the de-lit plate; proposed geometry)",
               "source": P["source"], "fit": {"tx": round(float(x[0]), 2), "ty": round(float(x[1]), 2),
                                             "yawDeg": round(float(x[2]), 3), "scale": round(float(x[3]), 5),
                                             "waterlineZ": round(float(x[4]), 2), "iou": round(best[0], 4)},
               "log": log, "cut": info, "triangles": int(tris),
               "hullTopZ": round(float(hb[:, 2].max()), 1),
               "dockLine": dock_line, "dockZ": P["dockZ"],
               "overlay": (CS.WORK / "overlays" / "ship-silhouette-c0.png").as_posix(), "overlayStats": ov,
               "pivotBoard": [round(float(v), 3) for v in pivot],
               "boundsBoard": {"min": [round(float(v), 1) for v in Pb.min(0)],
                               "max": [round(float(v), 1) for v in Pb.max(0)]}}
        CS.dump_json(CS.RUNS["ship"] / "reports" / "ship-fit.json", rep)
        print("SHIP-FIT", json.dumps(rep["fit"]), "tris", tris, "overlay", ov)
        return rep

    if __name__ == "__main__":
        if len(sys.argv) > 1 and sys.argv[1] == "fit":
            run_fit()
        else:
            raise SystemExit("usage: ship_build.py fit   (prep runs under Blender: -- prep)")
