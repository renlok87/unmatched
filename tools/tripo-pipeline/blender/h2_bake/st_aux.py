"""Stage aux (H2.1, 2026-09-29): auxiliary maps for the material pass of the textures stage.

  POSITION  per-texel rest position (final frame, metres) of the low-poly surface (work/lp_uv.blend, caps included),
            rasterised from the UV triangles with barycentrics (pixel centres, inclusive edges; no bake, no GPU)
                                                                     -> work/uv/position.npy (float32 [S, S, 3]),
                                                                        work/uv/position_alpha.npy
  AO_EX     Cycles AO of selected parts with some high-poly occluders hidden (profile bake.ao_exclusions): the
            same cage, samples, distance and seed as the bake stage, only the listed occluders are excluded from
            the scene (hide_render). Use: a part that moves away in the animation (the right fist on the belt)
            must not leave its rest-pose contact shadow in the static AO of its neighbour.
                                                                     -> work/bake/AO_EX.npy (+ _alpha), per-part
  AO_CTRL   (bake.ao_exclusions[*].control) the same part baked again with nothing hidden: the GPU noise floor
            of the AO bake, so the report can separate "the fist's shadow" from bake noise.
Report: reports/aux-report.json (texel counts, AO deltas). Headless only."""

import json
import time
from pathlib import Path

import bpy
import numpy as np

from . import bl_util as U
from .st_bake import RAY_FLAGS, cage_for


def loop_triangles(mesh):
    """(loop index triples [T, 3]) — fan triangulation, the order of bl_util.uv_triangles."""
    tris = []
    for p in mesh.polygons:
        li = list(p.loop_indices)
        for k in range(1, len(li) - 1):
            tris.append((li[0], li[k], li[k + 1]))
    return np.array(tris, np.int64)


def raster_positions(tri_px, tri_pos, size, pos, alpha):
    """Barycentric raster of triangle positions into pos [S, S, 3] (row 0 = v 0); the later triangle wins."""
    for t in range(len(tri_px)):
        a, b, c = tri_px[t]
        x0 = max(int(np.floor(min(a[0], b[0], c[0]))), 0)
        x1 = min(int(np.ceil(max(a[0], b[0], c[0]))), size - 1)
        y0 = max(int(np.floor(min(a[1], b[1], c[1]))), 0)
        y1 = min(int(np.ceil(max(a[1], b[1], c[1]))), size - 1)
        if x1 < x0 or y1 < y0:
            continue
        d = (b[1] - c[1]) * (a[0] - c[0]) + (c[0] - b[0]) * (a[1] - c[1])
        if abs(d) < 1e-12:
            continue
        X, Y = np.meshgrid(np.arange(x0, x1 + 1) + 0.5, np.arange(y0, y1 + 1) + 0.5)
        l1 = ((b[1] - c[1]) * (X - c[0]) + (c[0] - b[0]) * (Y - c[1])) / d
        l2 = ((c[1] - a[1]) * (X - c[0]) + (a[0] - c[0]) * (Y - c[1])) / d
        l3 = 1.0 - l1 - l2
        inside = (l1 >= -1e-9) & (l2 >= -1e-9) & (l3 >= -1e-9)
        if not inside.any():
            continue
        p = tri_pos[t]
        val = l1[inside, None] * p[0] + l2[inside, None] * p[1] + l3[inside, None] * p[2]
        sub = pos[y0:y1 + 1, x0:x1 + 1]
        sub[inside] = val
        alpha[y0:y1 + 1, x0:x1 + 1][inside] = 1


def position_map(run_dir, names, size):
    bpy.ops.wm.open_mainfile(filepath=str(run_dir / "work" / "lp_uv.blend"))
    pos = np.zeros((size, size, 3), np.float32)
    alpha = np.zeros((size, size), np.uint8)
    per_part = {}
    for n in names:
        obj = bpy.data.objects["LP_" + n]
        me = obj.data
        mw = np.array(obj.matrix_world, np.float64)
        co = U.coords(me) @ mw[:3, :3].T + mw[:3, 3]
        lv = np.empty(len(me.loops), np.int64)
        me.loops.foreach_get("vertex_index", lv)
        luv = np.empty(len(me.loops) * 2, np.float64)
        me.uv_layers["UVMap"].data.foreach_get("uv", luv)
        luv = luv.reshape(-1, 2)
        tris = loop_triangles(me)
        before = int(alpha.sum())
        raster_positions(luv[tris] * size, co[lv[tris]], size, pos, alpha)
        per_part[n] = {"triangles": int(len(tris)), "texels_written": int(alpha.sum()) - before}
    return pos, alpha, per_part


def ao_exclusion_bakes(run_dir, profile, names, size):
    bcfg = profile["bake"]
    retopo = json.loads((run_dir / "reports" / "retopo-report.json").read_text(encoding="utf-8"))
    bpy.ops.wm.open_mainfile(filepath=str(run_dir / "work" / "hp.blend"))
    scene = bpy.context.scene
    for obj in [o for o in bpy.data.objects if o.name.startswith("HPG_")]:
        bpy.data.objects.remove(obj)
    with bpy.data.libraries.load(str(run_dir / "work" / "lp_uv.blend"), link=False) as (src, dst):
        dst.objects = [n for n in src.objects if n.startswith("LP_")]
    lp_col = bpy.data.collections.new("LP")
    scene.collection.children.link(lp_col)
    for obj in dst.objects:
        lp_col.objects.link(obj)
        for flag in RAY_FLAGS:
            setattr(obj, flag, False)
    device = U.setup_cycles(scene, bcfg.get("device", "GPU"), samples=int(bcfg["ao"]["samples"]),
                            seed=int(bcfg["ao"].get("seed", 0)))
    world = bpy.data.worlds.new("h2_aux_world")
    scene.world = world
    world.light_settings.distance = float(bcfg["ao"]["distance_m"])
    target = bpy.data.images.new("H2_AUX_TARGET", size, size, alpha=True, float_buffer=True)
    target.colorspace_settings.name = "Non-Color"
    lp_mat = bpy.data.materials.new("H2_AUX_LP")
    lp_mat.use_nodes = True
    tex = lp_mat.node_tree.nodes.new("ShaderNodeTexImage")
    tex.image = target
    lp_mat.node_tree.nodes.active = tex
    for obj in dst.objects:
        obj.data.materials.clear()
        obj.data.materials.append(lp_mat)
    part_ids = np.load(run_dir / "work" / "uv" / "part_ids.npy")
    zeros = np.zeros(size * size * 4, np.float32)

    def bake_part(n, hidden):
        hp = bpy.data.objects["HPT_" + n]
        lp = bpy.data.objects["LP_" + n]
        for h in hidden:
            bpy.data.objects["HPT_" + h].hide_render = True
        e, dmax = cage_for(retopo["parts"][n], bcfg["cage"])
        target.pixels.foreach_set(zeros)
        bpy.ops.object.select_all(action="DESELECT")
        hp.select_set(True)
        lp.select_set(True)
        bpy.context.view_layer.objects.active = lp
        bpy.ops.object.bake(type="AO", use_selected_to_active=True, cage_extrusion=e, max_ray_distance=dmax, margin=0,
                            use_clear=False, target="IMAGE_TEXTURES", save_mode="INTERNAL")
        for h in hidden:
            bpy.data.objects["HPT_" + h].hide_render = False
        px = U.image_to_array(target)
        take = (px[..., 3] > 0.5) & (part_ids == names.index(n))
        return px[..., :3], take

    ao_ex = np.zeros((size, size, 3), np.float32)
    ao_ex_a = np.zeros((size, size), np.uint8)
    ao_ctrl = np.zeros((size, size, 3), np.float32)
    ao_ctrl_a = np.zeros((size, size), np.uint8)
    rows = []
    seen = set()
    for ex in bcfg.get("ao_exclusions", []):
        n = ex["part"]
        if n in seen:
            raise RuntimeError("bake.ao_exclusions: part %s listed twice" % n)
        seen.add(n)
        for h in ex["hide_occluders"]:
            if h not in names or h == n:
                raise RuntimeError("bake.ao_exclusions %s: bad occluder %s" % (ex["name"], h))
        t0 = time.time()
        px, take = bake_part(n, ex["hide_occluders"])
        ao_ex[take] = px[take]
        ao_ex_a[take] = 1
        row = {"name": ex["name"], "part": n, "hidden_occluders": list(ex["hide_occluders"]), "baked_texels": int(take.sum()),
               "cage_extrusion_m": U.r(cage_for(retopo["parts"][n], bcfg["cage"])[0], 6)}
        if ex.get("control"):
            pc, tc = bake_part(n, [])
            ao_ctrl[tc] = pc[tc]
            ao_ctrl_a[tc] = 1
            row["control_baked_texels"] = int(tc.sum())
        rows.append(row)
        print("H2_AUX_AO", ex["name"], round(time.time() - t0, 1), flush=True)
    return {"AO_EX": (ao_ex, ao_ex_a), "AO_CTRL": (ao_ctrl, ao_ctrl_a)}, rows, device


def run(params, profile):
    run_dir = Path(params["run_dir"])
    names = sorted(profile["parts"], key=U.part_key)
    size = int(profile["bake"]["resolution"])
    t0 = time.time()
    pos, pos_a, per_part = position_map(run_dir, names, size)
    uv_dir = run_dir / "work" / "uv"
    np.save(uv_dir / "position.npy", pos)
    np.save(uv_dir / "position_alpha.npy", pos_a)
    part_ids = np.load(uv_dir / "part_ids.npy")
    cover = part_ids >= 0
    t_pos = time.time() - t0
    maps, rows, device = ao_exclusion_bakes(run_dir, profile, names, size)
    bake_dir = run_dir / "work" / "bake"
    for key, (arr, a) in maps.items():
        np.save(bake_dir / ("%s.npy" % key), arr)
        np.save(bake_dir / ("%s_alpha.npy" % key), a)
    ao = np.load(bake_dir / "AO.npy")[..., 0]
    for row in rows:
        pi = names.index(row["part"])
        m = (part_ids == pi) & (maps["AO_EX"][1] > 0)
        d = maps["AO_EX"][0][..., 0][m] - ao[m]
        row["ao_delta_vs_bake"] = {"mean": U.r(d.mean(), 5), "p99": U.r(np.percentile(d, 99), 4), "max": U.r(d.max(), 4),
                                   "min": U.r(d.min(), 4), "texels_gt_1_255": int((np.abs(d) > 1.0 / 255).sum()),
                                   "texels_gt_16_255": int((d > 16.0 / 255).sum())}
        if "control_baked_texels" in row:
            mc = m & (maps["AO_CTRL"][1] > 0)
            dc = maps["AO_CTRL"][0][..., 0][mc] - ao[mc]
            row["control_delta_vs_bake"] = {"max_abs": U.r(np.abs(dc).max(), 4),
                                            "texels_gt_1_255": int((np.abs(dc) > 1.0 / 255).sum()),
                                            "note": "the same bake with nothing hidden: GPU noise floor of the AO bake"}
    checks = {"position_covers_uv_raster": {
        "passed": bool(((pos_a > 0) | ~cover).all() and ((pos_a > 0) & ~cover).sum() <= 0.001 * cover.sum()),
        "measured": {"uv_texels": int(cover.sum()), "uv_texels_without_position": int((cover & (pos_a == 0)).sum()),
                     "position_outside_uv_raster": int(((pos_a > 0) & ~cover).sum())},
        "expected": "every UV-raster texel has a position (the same triangles and pixel-centre rule as the uv stage)"}}
    report = {"stage": "aux", "device": device, "resolution": size,
              "position": {"per_part": per_part, "frame": "final (authored) frame, metres, rest pose"},
              "ao_exclusions": rows, "checks": checks, "passed": all(c["passed"] for c in checks.values()),
              "status": "измерено"}
    U.write_json(run_dir / "reports" / "aux-report.json", report)
    U.write_json(run_dir / "work" / "bake" / "aux-timing.json", {"position_s": U.r(t_pos, 1)})  # wall time: not a report
    if not report["passed"]:
        raise RuntimeError("aux checks failed: %s" % report["checks"])
