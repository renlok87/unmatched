"""Base see-through check (stage 3, T3.1 review fix): holes in the top of a figure base through which the board
shows. Headless Blender on exported FBX files; no editor, no live Blender, nothing written but --out.

    python tools/tripo-pipeline/review/base_seethrough.py --out <json> <label>=<base fbx>[,<figure fbx>] [...]
        [--blender <blender.exe>] [--step-uu 0.1] [--aim surface|plane]

The same file runs twice: on the host it starts `blender -b --factory-startup --python <this file> -- <params.json>`;
inside Blender (bpy importable) it measures and writes the JSON.

Per base FBX (all mesh objects merged, world space; UM_FBX_v1 imports 1 uu = 1 cm = 0.01 Blender m, so uu = m x 100):
  triangles, open (boundary) edges and their connected loops (bounds in uu; the loops in the top 20 % of the height
  are listed separately -- the footprint holes of the T4 Medusa base lie there);
  see-through area: sample points on a step x step uu grid over the top disc of the base (93 % of the radius, so the
  rim bevel is not sampled); one ray per sample point and direction -- top-down and along the board camera (pitch
  -55) from +X (the front of a UM_FBX_v1 mesh), -X, +Y and -Y. A ray is covered when it meets a front face
  (dot(normal, dir) < 0) anywhere along its length; UE materials of the candidates are one-sided, so a ray that meets
  only back faces, or nothing, reaches the board in the frame.
  area = uncovered rays x step^2, projected on the horizontal plane (uu^2).
  base_only     -- the base mesh alone (holes in the mesh; the figure hidden);
  with_figure   -- base + figure mesh in the rest pose (what the scene shows: holes the figure does not cover).
Aim point of a sample (x, y) -- the rule (--aim surface, the default since 2026-10-14):
  the ray is aimed at the ACTUAL top surface of the base, (x, y, h(x, y)). h comes from a top-down probe of the base
  mesh alone: its first hit is a front face -> h = the z of that hit; a back face or no hit -> (x, y) is a hole and h
  is filled from the surrounding top (mean of the 4-neighbours, grown layer by layer from the probed points). The
  probe never sees the figure, so the aim points are the same for base_only and with_figure.
  Why: the old aim (--aim plane) put every sample on ONE plane, z = the highest vertex of the base. On a domed or
  sloped top (Achilles r3: the top falls 0.17-0.24 uu below that plane at r 13.8-13.9 of the 13.935 sampled radius) a
  -55 ray aimed at a point in the air above the far rim crossed the real top level beyond its edge, missed the base
  completely (no front face, no back face) and was counted as a hole -- the board around the base, not through it
  (F149, Achilles 0.98 uu^2, Leshen 2.81 uu^2). On the surface every solid sample is hit at its aim point (covered);
  a ray is uncovered only where the top itself lets the board through (a hole, a missing or flipped face) or along a
  shared edge. On a flat top h = the plane everywhere, so both aims give identical rays and numbers.
  --aim plane keeps the old rule (schema /1; to reproduce evidence written before 2026-10-14).
  Holes are aimed at the height of the top around them, i.e. measured in the plane of their opening.
The disc sampling assumes a round base footprint (a sample outside the footprint would read as a hole); props
without a base (decor) are not measured.
Threshold (proposed, not a budget): with_figure see-through <= 0.1 uu^2 in every direction (10 samples of
0.1 x 0.1 uu; single rays can slip through shared edges). base_only above it is a mesh defect the figure hides.
"""

import json
import math
import os
import subprocess
import sys
import tempfile

SCHEMA = "unmatched.base-seethrough/2"  # /2: aim on the actual top surface (--aim surface); /1 = --aim plane
DEFAULT_BLENDER = "C:/Program Files/Blender Foundation/Blender 5.2/blender.exe"
UU_PER_M = 100.0
PITCH_DEG = 55.0
# camera azimuth around the mesh (Blender frame of the FBX import; a UM_FBX_v1 mesh faces +X)
DIRECTIONS = {"top_down": None, "cam55_from_+X": 0.0, "cam55_from_-X": 180.0, "cam55_from_+Y": 90.0, "cam55_from_-Y": -90.0}
THRESHOLD_UU2 = 0.1
DISC_SHARE = 0.93
AIMS = ("surface", "plane")
DEFAULT_AIM = "surface"


def fill_holes(cells, heights, fallback):
    """Heights for the hole cells of the sampled grid: `cells` are (i, j) grid indices, `heights` the probed top z per
    cell or None (hole). Each pass gives every hole cell that touches known cells (4-neighbours) the mean of their
    heights, so a hole gets the height of the top around it. Cells no known cell reaches (or no probed cell at all)
    get `fallback`. Pure Python (unit-tested without Blender)."""
    known = {cell: h for cell, h in zip(cells, heights) if h is not None}
    todo = {cell for cell, h in zip(cells, heights) if h is None}
    while todo and known:
        layer = {}
        for i, j in todo:
            near = [known[c] for c in ((i + 1, j), (i - 1, j), (i, j + 1), (i, j - 1)) if c in known]
            if near:
                layer[(i, j)] = sum(near) / len(near)
        if not layer:
            break
        known.update(layer)
        todo.difference_update(layer)
    return [known.get(cell, fallback) for cell in cells]


def load_bmesh(path):
    """All mesh objects of an FBX (evaluated: a skinned figure in its rest pose), world space, in uu."""
    import bmesh  # noqa: PLC0415 - Blender only
    import bpy  # noqa: PLC0415

    bpy.ops.wm.read_homefile(use_empty=True)
    bpy.ops.import_scene.fbx(filepath=path)
    depsgraph = bpy.context.evaluated_depsgraph_get()
    bm = bmesh.new()
    names = []
    for ob in [o for o in bpy.data.objects if o.type == "MESH"]:
        ev = ob.evaluated_get(depsgraph)
        me = ev.to_mesh()
        tmp = bmesh.new()
        tmp.from_mesh(me)
        tmp.transform(ob.matrix_world)
        ev.to_mesh_clear()
        mesh = bpy.data.meshes.new("_tmp")
        tmp.to_mesh(mesh)
        tmp.free()
        bm.from_mesh(mesh)
        bpy.data.meshes.remove(mesh)
        names.append(ob.name)
    bmesh.ops.scale(bm, vec=(UU_PER_M, UU_PER_M, UU_PER_M), verts=bm.verts)
    bm.normal_update()
    bm.faces.ensure_lookup_table()
    return bm, names


def boundary_loops(bm):
    boundary = [e for e in bm.edges if e.is_boundary]
    seen, loops = set(), []
    for e in boundary:
        if e.index in seen:
            continue
        comp, stack = [], [e]
        seen.add(e.index)
        while stack:
            x = stack.pop()
            comp.append(x)
            for v in x.verts:
                for y in v.link_edges:
                    if y.is_boundary and y.index not in seen:
                        seen.add(y.index)
                        stack.append(y)
        vs = {v for x in comp for v in x.verts}
        lx, ly, lz = ([v.co[i] for v in vs] for i in range(3))
        loops.append({"edges": len(comp), "x_uu": [round(min(lx), 2), round(max(lx), 2)],
                      "y_uu": [round(min(ly), 2), round(max(ly), 2)], "z_uu": [round(min(lz), 2), round(max(lz), 2)]})
    loops.sort(key=lambda item: (-item["edges"], item["x_uu"], item["y_uu"]))
    return len(boundary), loops


def top_surface(bvh, grid, above_z):
    """Top-down probe of the base mesh alone: per grid point the z of the first hit if it is a front face, else None
    (a hole: the first hit is a back face, or there is no hit)."""
    from mathutils import Vector  # noqa: PLC0415

    d = Vector((0.0, 0.0, -1.0))
    heights = []
    for gx, gy in grid:
        loc, nor, _idx, _dist = bvh.ray_cast(Vector((gx, gy, above_z)), d)
        heights.append(loc.z if loc is not None and nor.dot(d) < 0.0 else None)
    return heights


def see_through(bvh, grid, aim_z, reach, step_uu):
    """`aim_z`: the z of the aim point of every grid point (the actual top, or the plane with --aim plane)."""
    from mathutils import Vector  # noqa: PLC0415

    results = {}
    for name, az in DIRECTIONS.items():
        if az is None:
            d = Vector((0.0, 0.0, -1.0))
        else:
            p, a = math.radians(PITCH_DEG), math.radians(az)
            # the camera sits at azimuth `az` (pitch -55) and looks at the mesh
            d = Vector((-math.cos(p) * math.cos(a), -math.cos(p) * math.sin(a), -math.sin(p)))
        see = []
        for (gx, gy), gz in zip(grid, aim_z):
            o = Vector((gx, gy, gz)) - d * reach
            covered = False
            for _ in range(64):
                loc, nor, _idx, _dist = bvh.ray_cast(o, d)
                if loc is None:
                    break
                if nor.dot(d) < 0.0:
                    covered = True
                    break
                o = loc + d * 1e-3  # past the back face just met (0.001 uu)
            if not covered:
                see.append((gx, gy))
        area = len(see) * step_uu * step_uu
        item = {"rays": len(grid), "see_through_rays": len(see), "see_through_area_uu2": round(area, 3),
                "within_threshold": area <= THRESHOLD_UU2}
        if see:
            sx, sy = [q[0] for q in see], [q[1] for q in see]
            item["see_through_bounds_uu"] = {"x": [round(min(sx), 2), round(max(sx), 2)],
                                             "y": [round(min(sy), 2), round(max(sy), 2)]}
        results[name] = item
    return {"directions": results, "max_area_uu2": max(r["see_through_area_uu2"] for r in results.values())}


def measure(base_path, figure_path, step_uu, aim=DEFAULT_AIM):
    from mathutils import Vector  # noqa: PLC0415
    from mathutils.bvhtree import BVHTree  # noqa: PLC0415

    bm, names = load_bmesh(base_path)
    xs, ys, zs = ([v.co[i] for v in bm.verts] for i in range(3))
    lo, hi = Vector((min(xs), min(ys), min(zs))), Vector((max(xs), max(ys), max(zs)))
    height = hi.z - lo.z
    n_boundary, loops = boundary_loops(bm)
    top_z0 = lo.z + 0.8 * height
    cx, cy = (lo.x + hi.x) / 2.0, (lo.y + hi.y) / 2.0
    radius = min(hi.x - lo.x, hi.y - lo.y) / 2.0
    r_s = DISC_SHARE * radius
    n = int(math.floor(r_s / step_uu))
    cells = [(i, j) for i in range(-n, n + 1) for j in range(-n, n + 1)
             if (i * step_uu) ** 2 + (j * step_uu) ** 2 <= r_s ** 2]
    grid = [(cx + i * step_uu, cy + j * step_uu) for i, j in cells]
    out = {"base": {"file": base_path, "objects": names, "triangles": sum(len(f.verts) - 2 for f in bm.faces),
                    "bounds_uu": {"min": [round(v, 3) for v in lo], "max": [round(v, 3) for v in hi]},
                    "boundary_edges": n_boundary, "boundary_loops": len(loops),
                    "top_region_z_from_uu": round(top_z0, 3),
                    "top_boundary_loops": [lp for lp in loops if lp["z_uu"][0] >= top_z0],
                    "largest_boundary_loops": loops[:10]},
           "disc": {"centre_uu": [round(cx, 3), round(cy, 3)], "radius_uu": round(radius, 3),
                    "sampled_radius_uu": round(r_s, 3), "step_uu": step_uu, "plane_z_uu": round(hi.z, 3),
                    "aim": aim}}
    base_verts = [v.co.copy() for v in bm.verts]
    base_faces = [[v.index for v in f.verts] for f in bm.faces]
    bm.free()
    reach = 200.0
    base_bvh = BVHTree.FromPolygons(base_verts, base_faces)
    probed = top_surface(base_bvh, grid, hi.z + 1.0)
    solid = sorted(h for h in probed if h is not None)
    out["disc"]["top_surface_uu"] = {
        "samples": len(grid), "front_face_from_above": len(solid), "holes": len(grid) - len(solid),
        "hole_area_uu2": round((len(grid) - len(solid)) * step_uu * step_uu, 3),
        "z_min": round(solid[0], 3) if solid else None, "z_median": round(solid[len(solid) // 2], 3) if solid else None,
        "z_max": round(solid[-1], 3) if solid else None,
        "max_drop_below_plane_uu": round(hi.z - solid[0], 3) if solid else None}
    aim_z = fill_holes(cells, probed, hi.z) if aim == "surface" else [hi.z] * len(grid)
    out["base_only"] = see_through(base_bvh, grid, aim_z, reach, step_uu)
    if figure_path:
        fig, fnames = load_bmesh(figure_path)
        fz = [v.co.z for v in fig.verts]
        verts = base_verts + [v.co.copy() for v in fig.verts]
        faces = base_faces + [[v.index + len(base_verts) for v in f.verts] for f in fig.faces]
        out["figure"] = {"file": figure_path, "objects": fnames, "triangles": sum(len(f.verts) - 2 for f in fig.faces),
                         "z_uu": [round(min(fz), 3), round(max(fz), 3)]}
        fig.free()
        out["with_figure"] = see_through(BVHTree.FromPolygons(verts, faces), grid, aim_z, reach, step_uu)
    judged = out.get("with_figure", out["base_only"])
    out["pass"] = judged["max_area_uu2"] <= THRESHOLD_UU2
    out["judged_on"] = "with_figure" if figure_path else "base_only"
    return out


def blender_main():
    params = json.load(open(sys.argv[sys.argv.index("--") + 1], encoding="utf-8"))
    import bpy  # noqa: PLC0415
    res = {"schema": SCHEMA, "blender": bpy.app.version_string, "step_uu": params["step_uu"],
           "threshold_uu2": THRESHOLD_UU2, "pitch_deg": PITCH_DEG, "disc_share": DISC_SHARE, "aim": params["aim"],
           "method": __doc__.split("Per base FBX", 1)[1].strip(), "items": {}}
    for label, base, figure in params["items"]:
        res["items"][label] = measure(base, figure, params["step_uu"], params["aim"])
    with open(params["out"], "w", encoding="utf-8", newline="\n") as handle:
        handle.write(json.dumps(res, indent=1, sort_keys=True, ensure_ascii=False) + "\n")


def host_main():
    import argparse  # noqa: PLC0415
    import hashlib  # noqa: PLC0415
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    ap.add_argument("--blender", default=os.environ.get("TRIPO_PIPELINE_BLENDER") or DEFAULT_BLENDER)
    ap.add_argument("--step-uu", type=float, default=0.1)
    ap.add_argument("--aim", choices=AIMS, default=DEFAULT_AIM,
                    help="surface: aim at the actual top of the base (default); plane: the old rule (schema /1)")
    ap.add_argument("items", nargs="+", help="<label>=<base fbx>[,<figure fbx>]")
    a = ap.parse_args()
    items = []
    for spec in a.items:
        label, paths = spec.split("=", 1)
        base, _sep, figure = paths.partition(",")
        items.append([label, os.path.abspath(base).replace("\\", "/"),
                      os.path.abspath(figure).replace("\\", "/") if figure else None])
    out = os.path.abspath(a.out)
    with tempfile.TemporaryDirectory() as tmp:
        params = os.path.join(tmp, "params.json")
        raw = os.path.join(tmp, "result.json")
        with open(params, "w", encoding="utf-8") as handle:
            json.dump({"items": items, "step_uu": a.step_uu, "aim": a.aim, "out": raw.replace("\\", "/")}, handle)
        proc = subprocess.run([a.blender, "-b", "--factory-startup", "--python", os.path.abspath(__file__), "--",
                               params], capture_output=True, text=True, encoding="utf-8", errors="replace",
                              timeout=3600)
        if proc.returncode != 0 or not os.path.exists(raw):
            sys.stderr.write(proc.stdout[-3000:] + proc.stderr[-3000:])
            raise SystemExit("blender failed (rc %s)" % proc.returncode)
        res = json.load(open(raw, encoding="utf-8"))
    repo = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))

    def rel(path):
        r = os.path.relpath(path, repo).replace("\\", "/")
        return r if not r.startswith("..") else path

    for label, base, figure in items:
        item = res["items"][label]
        for key, path in (("base", base), ("figure", figure)):
            if path:
                with open(path, "rb") as handle:
                    item[key]["sha256"] = hashlib.sha256(handle.read()).hexdigest()
                item[key]["file"] = rel(path)
    res["tool"] = "tools/tripo-pipeline/review/base_seethrough.py"
    with open(out, "w", encoding="utf-8", newline="\n") as handle:
        handle.write(json.dumps(res, indent=1, sort_keys=True, ensure_ascii=False) + "\n")
    for label, item in res["items"].items():
        b = item["base"]
        print("%-22s base tris %5d open edges %4d loops %3d (top %2d) | aim %-7s | see-through base only %6.2f uu2%s"
              " | %s" % (label, b["triangles"], b["boundary_edges"], b["boundary_loops"], len(b["top_boundary_loops"]),
                         res["aim"], item["base_only"]["max_area_uu2"],
                         " | with figure %6.2f uu2" % item["with_figure"]["max_area_uu2"] if "with_figure" in item
                         else "", "PASS" if item["pass"] else "FAIL"))


if __name__ == "__main__":
    try:
        import bpy  # noqa: F401,PLC0415
    except ImportError:
        host_main()
    else:
        blender_main()
