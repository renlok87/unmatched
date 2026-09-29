"""Stage curve (optional, not part of `--stages all`): the exploratory "triangles -> deviation" curve used to pick the
per-part retopo budgets (profile retopo.target_tris) and to argue the proposed hero budget.

For every high-poly part HPG_<part> of work/hp.blend (untextured Tripo parts, already in the final frame, metres):
collapse decimation (st_retopo.decimate, no mask, no cleanup) to each level of profile curve.levels (skipped when
level * 1.5 > the part's high-poly triangles); deviation high -> low over `samples` high-poly vertices (seed) to the
nearest low-poly point, and low -> high over at most `lo_samples` low-poly vertices (every k-th). Millimetres in the
final frame. Writes reports/decimation-curve.json (status "измерено", exploratory: the shipped low-poly is made by the
retopo stage, not by this curve)."""

from pathlib import Path

import bpy
import numpy as np
from mathutils import Vector
from mathutils.bvhtree import BVHTree

from . import bl_util as U
from .st_retopo import decimate

DEFAULT = {"levels": [250, 500, 1000, 2000, 4000, 8000, 16000], "samples": 30000, "lo_samples": 5000, "seed": 0}


def run(params, profile):
    run_dir = Path(params["run_dir"])
    cfg = dict(DEFAULT, **profile.get("curve", {}))
    bpy.ops.wm.open_mainfile(filepath=str(run_dir / "work" / "hp.blend"))
    for obj in [o for o in bpy.data.objects if o.name.startswith("HPT_")]:
        bpy.data.objects.remove(obj)
    names = sorted(profile["parts"], key=U.part_key)
    rng = np.random.default_rng(int(cfg["seed"]))
    out = {}
    for n in names:
        hi = bpy.data.objects["HPG_" + n]
        hc = U.coords(hi.data)
        hi_tris = U.triangles(hi.data)
        pick = np.sort(rng.choice(len(hc), min(int(cfg["samples"]), len(hc)), replace=False))
        hi_bvh = BVHTree.FromPolygons([Vector(c) for c in hc], [list(p.vertices) for p in hi.data.polygons])
        levels = {}
        for level in cfg["levels"]:
            if level * 1.5 > hi_tris:
                continue
            me = hi.data.copy()
            lo = bpy.data.objects.new("CURVE_" + n, me)
            bpy.context.scene.collection.objects.link(lo)
            decimate(lo, level / hi_tris)
            lc = U.coords(lo.data)
            lo_bvh = BVHTree.FromPolygons([Vector(c) for c in lc], [list(p.vertices) for p in lo.data.polygons])
            d1 = np.array([lo_bvh.find_nearest(Vector(hc[i]))[3] for i in pick]) * 1000.0
            step = max(1, len(lc) // int(cfg["lo_samples"]))
            d2 = np.array([hi_bvh.find_nearest(Vector(c))[3] for c in lc[::step]]) * 1000.0
            levels[str(level)] = {"triangles": U.triangles(lo.data), "hi_to_lo_p95_mm": U.r(np.percentile(d1, 95), 4),
                                  "hi_to_lo_max_mm": U.r(d1.max(), 4), "lo_to_hi_p95_mm": U.r(np.percentile(d2, 95), 4)}
            mesh = lo.data
            bpy.data.objects.remove(lo)
            bpy.data.meshes.remove(mesh)
        out[n] = {"hi_triangles": hi_tris, "area_cm2": U.r(U.mesh_area(hi.data) * 1e4, 3), "levels": levels,
                  "retopo_target_triangles": int(profile["retopo"]["target_tris"][n])}
        print("H2_CURVE", n, {k: (v["triangles"], v["hi_to_lo_p95_mm"]) for k, v in levels.items()}, flush=True)
    report = {"stage": "curve", "status": "измерено", "kind": "exploratory (budget choice), not the shipped low-poly",
              "method": "st_retopo.decimate (collapse, no mask, no cleanup) of each HPG part of work/hp.blend (final frame)",
              "levels": cfg["levels"], "samples": cfg["samples"], "lo_samples": cfg["lo_samples"], "seed": cfg["seed"],
              "parts": out}
    U.write_json(run_dir / "reports" / "decimation-curve.json", report)
