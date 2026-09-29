"""H2 stage 1 — import and verify the two Tripo high-poly GLBs (headless only).

    blender -b --factory-startup --python stage_import.py -- <profile.json> <run_dir>

* imports the geometry GLB (parts, no UV) and the textured GLB (8K texture + PBR, UV0) of the same Tripo task;
* matches parts by node name and compares the geometry of the two files per part (triangle sets, positions);
* measures every part: triangles, bounds (Blender frame: glTF +Z forward -> Blender -Y), welded topology (open and
  non-manifold edges, shells), signed volume, custom-normal vs winding agreement and a sampled ray-escape
  orientation score against the whole figure (the Tripo inside-out lesson of Medusa/Harpy);
* reads the texture set of every textured part (image sizes, colour spaces);
* saves <run>/work/h2-highpoly.blend (textured parts only, images packed) for the later stages and writes
  <run>/reports/h2-import-report.json.
Sources are only read and hashed.
"""

import math
import sys
import time
from pathlib import Path

import bpy
import numpy as np
from mathutils.bvhtree import BVHTree

sys.path.insert(0, str(Path(__file__).resolve().parent))
import common as C  # noqa: E402

C.require_background("stage_import.py")
args = C.script_args()
PROFILE_PATH, RUN = Path(args[0]).resolve(), Path(args[1]).resolve()
P = C.load_profile(PROFILE_PATH)
t0 = time.time()
src = P["sources"]
geo_path = C.REPO / src["geometry_glb"]["path"]
tex_path = C.REPO / src["textured_glb"]["path"]
report = {"schema": "unmatched.h2-bake.import-report/1", "profile": C.rel(PROFILE_PATH),
          "profile_sha256": C.sha256(PROFILE_PATH), "blender": bpy.app.version_string, "sources": {}}
for key, path in (("geometry_glb", geo_path), ("textured_glb", tex_path)):
    digest = C.sha256(path)
    report["sources"][key] = {"path": C.rel(path), "sha256": digest, "bytes": path.stat().st_size,
                              "expected_sha256": src[key]["sha256"], "sha256_matches": digest == src[key]["sha256"]}
    if digest != src[key]["sha256"]:
        raise RuntimeError("%s sha256 mismatch: %s" % (key, digest))

bpy.ops.wm.read_factory_settings(use_empty=True)
scene = bpy.context.scene


def import_prefixed(path, prefix):
    before = set(bpy.data.objects)
    bpy.ops.import_scene.gltf(filepath=str(path))
    new = [o for o in bpy.data.objects if o not in before]
    parts = {}
    for o in new:
        if o.type == "MESH":
            name = o.name.split(".")[0]
            o.name = prefix + name
            o.data.name = prefix + name
            parts[name] = o
    for o in new:  # glTF ROOT empty: keep world transforms, drop the empty
        if o.type == "EMPTY":
            for ch in list(o.children):
                mw = ch.matrix_world.copy()
                ch.parent = None
                ch.matrix_world = mw
            bpy.data.objects.remove(o)
    return parts


geo = import_prefixed(geo_path, "GEO_")
t_geo = time.time() - t0
tex = import_prefixed(tex_path, "HP_")
t_tex = time.time() - t0 - t_geo
report["import_seconds"] = {"geometry": C.r(t_geo, 1), "textured": C.r(t_tex, 1)}
names = sorted(set(geo) | set(tex), key=lambda n: int(n.rsplit("_", 1)[1]))
report["parts_geometry"] = sorted(geo, key=lambda n: int(n.rsplit("_", 1)[1]))
report["parts_textured"] = sorted(tex, key=lambda n: int(n.rsplit("_", 1)[1]))
report["same_part_set"] = set(geo) == set(tex)
for o in list(geo.values()) + list(tex.values()):
    if any(abs(s - 1.0) > 1e-9 for s in o.matrix_world.to_scale()) or o.matrix_world.to_translation().length > 1e-9 or \
            abs(o.matrix_world.to_quaternion().angle) > 1e-9:
        # glTF node transforms are identity for Tripo; apply anyway so mesh data = world
        o.data.transform(o.matrix_world)
        o.matrix_world.identity()


def welded(v, t, tol=1e-7):
    key = np.round(v / tol).astype(np.int64)
    _, inv = np.unique(key, axis=0, return_inverse=True)
    return inv.reshape(-1)[t], int(inv.max()) + 1


def topology(v, t):
    wt, nvw = welded(v, t)
    e = np.concatenate([wt[:, [0, 1]], wt[:, [1, 2]], wt[:, [2, 0]]])
    e.sort(axis=1)
    _, counts = np.unique(e, axis=0, return_counts=True)
    # shells: union-find by label propagation on welded vertices
    lab = np.arange(nvw)
    a, b = e[:, 0], e[:, 1]
    for _ in range(10000):
        m = np.minimum(lab[a], lab[b])
        new = lab.copy()
        np.minimum.at(new, a, m)
        np.minimum.at(new, b, m)
        new = new[new]
        if np.array_equal(new, lab):
            break
        lab = new
    used = np.unique(wt)
    shells = np.unique(lab[used])
    shell_sizes = np.bincount(np.searchsorted(shells, lab[wt[:, 0]]))
    degenerate = 0
    return {"welded_vertices": int(nvw), "edges": int(len(counts)), "open_edges": int((counts == 1).sum()),
            "non_manifold_edges": int((counts > 2).sum()), "shells": int(len(shells)),
            "largest_shells_triangles": sorted(shell_sizes.tolist(), reverse=True)[:5]}, degenerate


def signed_volume(v, t):
    a, b, c = v[t[:, 0]], v[t[:, 1]], v[t[:, 2]]
    return float(np.einsum("ij,ij->i", a, np.cross(b, c)).sum() / 6.0)


# whole-figure BVH of the textured high-poly (orientation by ray escape)
all_v, all_t, off = [], [], 0
per = {}
for n in names:
    o = tex[n]
    v, t = C.mesh_arrays(o.data)
    per[n] = (v, t)
    all_v.append(v)
    all_t.append(t + off)
    off += len(v)
V = np.concatenate(all_v)
T = np.concatenate(all_t)
lo, hi = V.min(0), V.max(0)
height = float(hi[2] - lo[2])
t_b = time.time()
bvh = BVHTree.FromPolygons(V.tolist(), T.tolist(), all_triangles=True, epsilon=0.0)
report["bvh_seconds"] = C.r(time.time() - t_b, 1)
report["figure_bounds_blender_m"] = {"min": C.rv(lo, 5), "max": C.rv(hi, 5), "height_m": C.r(height, 5)}
eps, dist = 1e-4 * height, 2.0 * height
samples = int(P["import"].get("orientation_samples_per_part", 4000))

parts_report = {}
for n in names:
    item = {}
    og, ot = geo.get(n), tex.get(n)
    vg, tg = C.mesh_arrays(og.data) if og else (None, None)
    vt, tt = per[n]
    item["triangles_geometry"] = int(len(tg)) if tg is not None else None
    item["triangles_textured"] = int(len(tt))
    item["vertices_geometry"] = int(len(vg)) if vg is not None else None
    item["vertices_textured"] = int(len(vt))
    item["polygons_textured"] = len(ot.data.polygons)
    item["bounds_min_m"], item["bounds_max_m"] = C.rv(vt.min(0), 5), C.rv(vt.max(0), 5)
    item["centroid_m"] = C.rv(vt.mean(0), 5)
    # geometry match: canonical triangle sets (corners sorted lexicographically, rows sorted)
    if tg is not None:
        def canon(v, t):
            tri = np.round(v[t] / 1e-7).astype(np.int64)  # (M,3,3)
            order = np.lexsort((tri[:, :, 2], tri[:, :, 1], tri[:, :, 0]), axis=1)
            tri = np.take_along_axis(tri, order[:, :, None], axis=1).reshape(len(t), 9)
            return tri[np.lexsort(tri.T[::-1])]
        same_count = len(tg) == len(tt)
        match = {"same_triangle_count": same_count}
        if same_count:
            cg, ct = canon(vg, tg), canon(vt, tt)
            diff = np.abs(cg - ct).max() * 1e-7
            match["canonical_triangle_sets_equal"] = bool(np.array_equal(cg, ct))
            match["max_abs_position_difference_m"] = float(diff)
            match["same_order_max_difference_m"] = float(np.abs(vg[tg] - vt[tt]).max())
        item["geometry_vs_textured"] = match
    topo, _ = topology(vt, tt)
    item["topology_textured_welded"] = topo
    item["signed_volume_m3"] = signed_volume(vt, tt)
    nn, area, cen = C.tri_normals_areas(vt, tt)
    item["area_m2"] = C.r(area.sum(), 7)
    item["degenerate_triangles"] = int((area < 1e-12).sum())
    # custom corner normals vs winding (normals from the GLB NORMAL attribute)
    me = ot.data
    cn = np.empty(len(me.loops) * 3, dtype=np.float32)
    me.corner_normals.foreach_get("vector", cn) if hasattr(me.corner_normals, "foreach_get") else None
    cn = cn.reshape(-1, 3)
    pn = np.empty(len(me.polygons) * 3, dtype=np.float32)
    me.polygons.foreach_get("normal", pn)
    pn = pn.reshape(-1, 3)
    loop_poly = np.repeat(np.arange(len(me.polygons)), [p.loop_total for p in me.polygons])
    dots = np.einsum("ij,ij->i", cn, pn[loop_poly])
    item["corner_normals_against_winding_fraction"] = C.r((dots < 0).mean(), 5)
    # sampled ray escape (deterministic stride over triangles)
    idx = np.linspace(0, len(tt) - 1, min(samples, len(tt))).astype(np.int64)
    out = inw = 0.0
    for i in idx:
        c = cen[i]
        nrm = nn[i]
        a = area[i]
        if a <= 0:
            continue
        from mathutils import Vector
        cv, nv = Vector(c), Vector(nrm)
        plus = bvh.ray_cast(cv + nv * eps, nv, dist)[0] is not None
        minus = bvh.ray_cast(cv - nv * eps, -nv, dist)[0] is not None
        if not plus and minus:
            out += a
        elif plus and not minus:
            inw += a
    item["ray_escape"] = {"samples": int(len(idx)), "score": C.r((out - inw) / (out + inw), 4) if out + inw else None,
                          "outward_area": C.r(out, 8), "inward_area": C.r(inw, 8)}
    # textures
    mats = [s.material for s in ot.material_slots if s.material]
    texinfo = {}
    for m in mats:
        if not m.use_nodes:
            continue
        for node in m.node_tree.nodes:
            if node.type == "TEX_IMAGE" and node.image:
                im = node.image
                links = [l.to_socket.name + "@" + l.to_node.bl_idname for l in m.node_tree.links if l.from_node == node]
                texinfo[im.name] = {"size": list(im.size), "colorspace": im.colorspace_settings.name,
                                    "feeds": sorted(links), "packed": im.packed_file is not None,
                                    "file_format": im.file_format}
        texinfo["_material"] = m.name
    item["textures"] = texinfo
    item["uv_layers"] = [l.name for l in me.uv_layers]
    parts_report[n] = item
    print("part", n, item["triangles_textured"], item["ray_escape"]["score"], flush=True)

report["parts"] = parts_report
report["totals"] = {"triangles_textured": int(sum(p["triangles_textured"] for p in parts_report.values())),
                    "triangles_geometry": int(sum(p["triangles_geometry"] or 0 for p in parts_report.values()))}
report["geometry_files_match"] = all(p.get("geometry_vs_textured", {}).get("canonical_triangle_sets_equal")
                                     for p in parts_report.values())

# keep the textured high-poly only
for o in geo.values():
    bpy.data.objects.remove(o)
for me in [m for m in bpy.data.meshes if m.users == 0]:
    bpy.data.meshes.remove(me)
for im in bpy.data.images:
    if im.packed_file is None and im.source == "FILE":
        im.pack()
work = RUN / "work"
work.mkdir(parents=True, exist_ok=True)
blend = work / "h2-highpoly.blend"
bpy.ops.wm.save_as_mainfile(filepath=str(blend), compress=False)
report["highpoly_blend"] = C.rel(blend)
report["seconds_total"] = C.r(time.time() - t0, 1)
C.write_json(RUN / "reports" / "h2-import-report.json", report)
print(C.STAGE_MARKER, "import", flush=True)
