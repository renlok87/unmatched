"""ASSET-DECOR-KIT-001.CRATE, step 1 of 2 (Blender 5.2 headless, a fresh process only):

    "C:/Program Files/Blender Foundation/Blender 5.2/blender.exe" -b --factory-startup --python-exit-code 1 \
        --python art/pipeline-candidates/ASSET-DECOR-KIT-001/scripts/crate_build.py -- \
        art/pipeline-candidates/ASSET-DECOR-KIT-001/scripts/crate_params.json

Hand-built (scripted) static prop, no Tripo (registry nextStep: simple manual model, 25 uu):
  - geometry: closed, chamfered shells (posts, iron corner caps, wall planks, front/back rails, X braces, top and
    bottom boards) plus low-poly iron studs; touching parts interpenetrate slightly, so no two shells share a vertex
    position (the 1 um weld of the read-back must not fuse neighbours); front = -Y (04 §1) = X-brace side;
  - pivot (04 §1, decor crate): centre of the base -> origin, min z = 0;
  - the bmesh is rebuilt in a canonical element order (bevel's internal ordering is not stable between runs), so the
    FBX and PNG bytes are reproducible;
  - hidden faces (pressed against another part or facing the closed interior) found by BVH ray casts from a sample
    grid on every face; UV islands made only of hidden faces get a quarter of the density;
  - UV0: exact per-part box projection (stud domes along their axis), islands never mix hidden and visible faces,
    deterministic in-script skyline packing (>= 8 px between islands at 1024); one slot M_Decor_Crate (04 §3.7: <= 2);
  - textures 1K baked in Cycles from a procedural painted-wood/iron shader: BC (sRGB, moderate AO baked in, С-4),
    N (tangent, OpenGL bake -> DirectX green flip), ORM (R = AO, G = roughness, B = metallic; Linear);
  - no collision (04 §3.7: decor is not interactive);
  - export UM_FBX_v1 with the helpers of tools/tripo-pipeline/blender/static_prop_candidate.py (loaded without running
    its main(); that file is not modified), texture paths relative (../textures/...);
  - previews (JPEG <= 1200 px): orthographic front/side/top, 3/4, wireframe, UV layout, game camera (FOV 35 deg
    horizontal, pitch -55 deg, 12 m) over a 6x5 board of 94 uu tiles, with the P1.5 barrel for scale.
Status of everything written here: measured. Not art-accepted, not imported in UE.
"""
import hashlib
import json
import math
import os
import sys
from pathlib import Path

import bmesh
import bpy
import numpy as np
from bpy_extras import bmesh_utils
from bpy_extras.object_utils import world_to_camera_view
from mathutils import Vector
from mathutils.bvhtree import BVHTree

ROOT = Path(__file__).resolve().parents[4]
SPC = ROOT / "tools/tripo-pipeline/blender/static_prop_candidate.py"
M = 0.01  # uu -> Blender metres


def load_helpers():
    src = SPC.read_text(encoding="utf-8")
    body = src.rstrip()
    if not body.endswith("\nmain()"):
        raise SystemExit("static_prop_candidate.py no longer ends with main(); helper import must be revisited")
    ns = {"__file__": str(SPC), "__name__": "static_prop_candidate_helpers"}
    exec(compile(body[: -len("main()")], str(SPC), "exec"), ns)
    return ns, hashlib.sha256(src.encode("utf-8").replace(b"\r\n", b"\n")).hexdigest()


H_, SPC_SHA = load_helpers()
r = H_["r"]
sha256 = H_["sha256"]


def text_sha(path):
    return hashlib.sha256(Path(path).read_bytes().replace(b"\r\n", b"\n")).hexdigest()


def srgb8_to_lin(c):
    return [float(H_["srgb_to_lin"](np.float64(v / 255.0))) for v in c]


# ----------------------------------------------------------------------------- geometry
class Builder:
    """All parts in one bmesh; every part is its own closed shell."""

    def __init__(self):
        self.bm = bmesh.new()
        L = self.bm.faces.layers
        self.l_part = L.int.new("part_id")
        self.l_iron = L.float.new("is_iron")
        self.l_chamf = L.float.new("is_chamfer")
        self.l_stud = L.float.new("is_stud")
        self.l_rand = L.float.new("part_rand")
        self.parts = []
        self.rng = np.random.default_rng(20260928)

    def _finish(self, name, kind, faces, chamfer_faces, frame, iron=False, stud=False):
        pid = len(self.parts)
        rnd = float(self.rng.random())
        cf = set(chamfer_faces)
        for f in faces:
            f[self.l_part] = pid
            f[self.l_iron] = 1.0 if iron else 0.0
            f[self.l_stud] = 1.0 if stud else 0.0
            f[self.l_chamf] = 1.0 if f in cf else 0.0
            f[self.l_rand] = rnd
        o, ax, ay, az = frame
        self.parts.append({"name": name, "kind": kind, "frame": (Vector(o), Vector(ax), Vector(ay), Vector(az)),
                           "rand": r(rnd, 6), "faces_before_triangulation": len(faces)})
        return pid

    def _shell(self, seed_face):
        seen, stack = {seed_face}, [seed_face]
        while stack:
            f = stack.pop()
            for e in f.edges:
                for g in e.link_faces:
                    if g not in seen:
                        seen.add(g)
                        stack.append(g)
        return list(seen)

    def _bevel(self, faces, offset_uu):
        # ordered de-duplication: a set of BMEdge wrappers iterates in memory-address order, which made the bevel
        # (and so vertex order, UV packing and the FBX/PNG bytes) depend on unrelated allocations between runs
        seen, edges = set(), []
        for f in faces:
            for e in f.edges:
                if e not in seen:
                    seen.add(e)
                    edges.append(e)
        res = bmesh.ops.bevel(self.bm, geom=edges, offset=offset_uu * M, offset_type="OFFSET",
                              profile_type="SUPERELLIPSE", segments=1, profile=0.5, affect="EDGES",
                              clamp_overlap=True, loop_slide=True, mark_seam=False, mark_sharp=False,
                              harden_normals=False, face_strength_mode="NONE", miter_outer="SHARP",
                              miter_inner="SHARP", spread=0.1, vmesh_method="ADJ")
        return res["faces"]

    def prism(self, name, kind, poly_uv, origin, U, V, Nn, d0, d1, bevel_uu, grain_dir_uv, iron=False):
        """Convex polygon (uu, in the plane origin + u U + v V) extruded along Nn from d0 to d1 (uu)."""
        U, V, Nn, O = Vector(U), Vector(V), Vector(Nn), Vector(origin)
        bot = [self.bm.verts.new((O + u * U + v * V + d0 * Nn) * M) for u, v in poly_uv]
        top = [self.bm.verts.new((O + u * U + v * V + d1 * Nn) * M) for u, v in poly_uv]
        n = len(poly_uv)
        faces = [self.bm.faces.new(bot[::-1]), self.bm.faces.new(top)]
        for i in range(n):
            j = (i + 1) % n
            faces.append(self.bm.faces.new([bot[i], bot[j], top[j], top[i]]))
        bmesh.ops.recalc_face_normals(self.bm, faces=faces)
        chamf = self._bevel(faces, bevel_uu) if bevel_uu > 0 else []
        shell = self._shell(chamf[0] if chamf else faces[0])
        gu, gv = grain_dir_uv
        gx = (gu * U + gv * V).normalized()
        gy = Nn.cross(gx).normalized()
        return self._finish(name, kind, shell, chamf, (O * M, gx, gy, Nn), iron=iron)

    def box(self, name, kind, lo, hi, bevel_uu, grain_axis, iron=False):
        lo, hi = Vector(lo), Vector(hi)
        poly = [(lo.x, lo.y), (hi.x, lo.y), (hi.x, hi.y), (lo.x, hi.y)]
        axes = {"x": (1, 0), "y": (0, 1)}
        if grain_axis == "z":  # vertical grain: build the prism along X so the frame's X is +Z
            poly = [(lo.z, lo.y), (hi.z, lo.y), (hi.z, hi.y), (lo.z, hi.y)]
            return self.prism(name, kind, poly, (0, 0, 0), (0, 0, 1), (0, 1, 0), (1, 0, 0), lo.x, hi.x,
                              bevel_uu, (1, 0), iron=iron)
        return self.prism(name, kind, poly, (0, 0, 0), (1, 0, 0), (0, 1, 0), (0, 0, 1), lo.z, hi.z,
                          bevel_uu, axes[grain_axis], iron=iron)

    def stud(self, name, centre, normal, U, V, S):
        C, Nn, U, V = Vector(centre), Vector(normal), Vector(U), Vector(V)
        seg = S["segments"]
        rings = [(S["base_r"], -S["sink"])] + [tuple(x) for x in S["profile_r_h"]]
        ring_verts = []
        for rad, h in rings:
            ring_verts.append([self.bm.verts.new((C + Nn * h + (U * math.cos(2 * math.pi * k / seg)
                                                                + V * math.sin(2 * math.pi * k / seg)) * rad) * M)
                               for k in range(seg)])
        apex = self.bm.verts.new((C + Nn * S["apex_h"]) * M)
        faces = [self.bm.faces.new(ring_verts[0][::-1])]
        base = faces[0]
        for a, b in zip(ring_verts[:-1], ring_verts[1:]):
            for k in range(seg):
                j = (k + 1) % seg
                faces.append(self.bm.faces.new([a[k], a[j], b[j], b[k]]))
        last = ring_verts[-1]
        for k in range(seg):
            faces.append(self.bm.faces.new([last[k], last[(k + 1) % seg], apex]))
        bmesh.ops.recalc_face_normals(self.bm, faces=faces)
        pid = self._finish(name, "stud", faces, [], (C * M, U, V, Nn), iron=True, stud=True)
        self.parts[pid]["base_face_smooth"] = False
        return pid, [f for f in faces if f is not base]


def clip(poly, a, b):
    """Sutherland-Hodgman: keep a . p <= b."""
    out = []
    n = len(poly)
    for i in range(n):
        p, q = poly[i], poly[(i + 1) % n]
        dp, dq = a[0] * p[0] + a[1] * p[1] - b, a[0] * q[0] + a[1] * q[1] - b
        if dp <= 0:
            out.append(p)
        if (dp < 0 < dq) or (dq < 0 < dp):
            t = dp / (dp - dq)
            out.append((p[0] + t * (q[0] - p[0]), p[1] + t * (q[1] - p[1])))
    return out


def strip_poly(rect, p0, p1, half_w, cut=None):
    """Band of half width half_w around p0-p1 clipped to rect; cut = (normal, offset, sign) keeps one side."""
    x0, z0, x1, z1 = rect
    poly = [(x0, z0), (x1, z0), (x1, z1), (x0, z1)]
    d = Vector((p1[0] - p0[0], p1[1] - p0[1])).normalized()
    n = (-d.y, d.x)
    c = n[0] * p0[0] + n[1] * p0[1]
    poly = clip(poly, n, c + half_w)
    poly = clip(poly, (-n[0], -n[1]), -(c - half_w))
    if cut:
        (cn, cc, sign) = cut
        poly = clip(poly, (-sign * cn[0], -sign * cn[1]), -sign * cc)
    return poly, (d.x, d.y)


def build_crate(P, B):
    G = P["geometry_uu"]
    po, ca, pl, ra, br, tp, st = (G[k] for k in ("post", "cap", "plank", "rail", "brace", "top_plank", "stud"))
    ov = 0.04  # uu interpenetration of stacked/side-by-side boards (no shared vertex positions)
    studs_smooth = []
    # corner posts (vertical grain) and iron caps
    for sx in (-1, 1):
        for sy in (-1, 1):
            xs = sorted((sx * po["inner"], sx * po["outer"]))
            ys = sorted((sy * po["inner"], sy * po["outer"]))
            B.box("post_%+d%+d" % (sx, sy), "post", (xs[0], ys[0], po["z"][0]), (xs[1], ys[1], po["z"][1]),
                  po["bevel"], "z")
            cxs = sorted((sx * (po["inner"] - ca["inner_overlap"]), sx * ca["outer"]))
            cys = sorted((sy * (po["inner"] - ca["inner_overlap"]), sy * ca["outer"]))
            for tag, z0, z1 in (("bottom", 0.0, ca["height"]), ("top", 25.0 - ca["height"], 25.0)):
                B.box("cap_%s_%+d%+d" % (tag, sx, sy), "cap", (cxs[0], cys[0], z0), (cxs[1], cys[1], z1),
                      ca["bevel"], "z", iron=True)
                zc = (z0 + z1) / 2
                mid = (po["inner"] - ca["inner_overlap"] + ca["outer"]) / 2
                _pid, sm = B.stud("stud_%s_%+d%+d_x" % (tag, sx, sy), (sx * ca["outer"], sy * mid, zc),
                                  (sx, 0, 0), (0, 1, 0), (0, 0, 1), st)
                studs_smooth += sm
                _pid, sm = B.stud("stud_%s_%+d%+d_y" % (tag, sx, sy), (sx * mid, sy * ca["outer"], zc),
                                  (0, sy, 0), (1, 0, 0), (0, 0, 1), st)
                studs_smooth += sm
    # wall planks: front/back (normal -+Y) along X, sides (normal -+X) along Y
    h = (pl["z"][1] - pl["z"][0]) / pl["count"]
    for i in range(pl["count"]):
        z0 = pl["z"][0] + i * h - (ov / 2 if i else 0)
        z1 = pl["z"][0] + (i + 1) * h + (ov / 2 if i < pl["count"] - 1 else 0)
        for s in (-1, 1):
            ys = sorted((s * pl["inner"], s * pl["outer"]))
            B.box("plank_%s_%d" % ("front" if s < 0 else "back", i), "plank",
                  (-pl["span"], ys[0], z0), (pl["span"], ys[1], z1), pl["bevel"], "x")
            xs = sorted((s * pl["inner"], s * pl["outer"]))
            B.box("plank_%s_%d" % ("left" if s < 0 else "right", i), "plank",
                  (xs[0], -pl["span"], z0), (xs[1], pl["span"], z1), pl["bevel"], "y")
    # front/back rails
    for s in (-1, 1):
        ys = sorted((s * ra["inner"], s * ra["outer"]))
        for tag in ("bottom_z", "top_z"):
            z0, z1 = ra[tag]
            B.box("rail_%s_%s" % ("front" if s < 0 else "back", tag[:-2]), "rail",
                  (-ra["span"], ys[0], z0), (ra["span"], ys[1], z1), ra["bevel"], "x")
    # X braces on front (-Y) and back (+Y); plane coordinates (u along U, v = z)
    xi = po["inner"]
    zb, zt = ra["bottom_z"][1], ra["top_z"][0]
    rect = (-xi - br["tuck"], zb - br["tuck"], xi + br["tuck"], zt + br["tuck"])
    p0, p1 = (-xi, zb), (xi, zt)          # "/" continuous
    q0, q1 = (-xi, zt), (xi, zb)          # "\" split in two
    hw = br["width"] / 2
    d1 = Vector((p1[0] - p0[0], p1[1] - p0[1])).normalized()
    n1 = (-d1.y, d1.x)
    c1 = n1[0] * p0[0] + n1[1] * p0[1]
    cross_v = (0.0, zb + (zt - zb) / 2)
    for s, U in ((-1, (1, 0, 0)), (1, (-1, 0, 0))):
        Nn = (0, s, 0)
        side = "front" if s < 0 else "back"
        poly, g = strip_poly(rect, p0, p1, hw)
        B.prism("brace_%s_main" % side, "brace", poly, (0, 0, 0), U, (0, 0, 1), Nn, br["inner"], br["outer_main"],
                br["bevel"], g)
        for k, sign in ((0, 1), (1, -1)):
            off = hw - br["split_under"]
            poly2, g2 = strip_poly(rect, q0, q1, hw, cut=(n1, c1 + sign * off, sign))
            B.prism("brace_%s_split%d" % (side, k), "brace", poly2, (0, 0, 0), U, (0, 0, 1), Nn, br["inner"] - 0.05,
                    br["outer_split"], br["bevel"], g2)
        _pid, sm = B.stud("stud_brace_%s" % side, (Vector(U) * cross_v[0] + Vector((0, 0, cross_v[1]))
                                                   + Vector(Nn) * br["outer_main"]),
                          Nn, U, (0, 0, 1), st)
        studs_smooth += sm
    # top boards along Y (4 across X), bottom board
    w = 2 * tp["extent"] / tp["count"]
    for i in range(tp["count"]):
        x0 = -tp["extent"] + i * w - (ov / 2 if i else 0.05)          # outer boards reach 0.05 uu into the walls
        x1 = -tp["extent"] + (i + 1) * w + (ov / 2 if i < tp["count"] - 1 else 0.05)
        B.box("top_%d" % i, "top_plank", (x0, -tp["extent"] - 0.05, tp["z"][0]), (x1, tp["extent"] + 0.05, tp["z"][1]),
              tp["bevel"], "y")
    B.box("bottom_board", "bottom", (-tp["extent"] - 0.05, -tp["extent"] - 0.05, 0.45),
          (tp["extent"] + 0.05, tp["extent"] + 0.05, 1.45), 0.2, "x")
    return studs_smooth


def canonical_bmesh(src):
    """Rebuild the mesh in a canonical order: bmesh.ops.bevel orders its new elements by internal hash tables, so
    face/vertex order (and with it triangulation ties, island order, UV layout, FBX/PNG bytes) changed between runs.
    Faces sorted by (part, rounded vertex coordinates), each face's loop starting at its smallest vertex (winding
    kept), vertices created in that order and shared per part by rounded position; all face layers and smooth
    flags copied."""
    fl = src.faces.layers
    names_i = [l.name for l in fl.int.values()]
    names_f = [l.name for l in fl.float.values()]
    lp = fl.int.get("part_id")
    recs = []
    for f in src.faces:
        cos = [v.co.copy() for v in f.verts]
        keys = [tuple(round(c, 7) for c in co) for co in cos]
        k = keys.index(min(keys))
        cos, keys = cos[k:] + cos[:k], keys[k:] + keys[:k]
        recs.append(((f[lp], keys), cos, [f[fl.int.get(n)] for n in names_i], [f[fl.float.get(n)] for n in names_f],
                     f.smooth))
    recs.sort(key=lambda t: t[0])
    bm = bmesh.new()
    li = [bm.faces.layers.int.new(n) for n in names_i]
    lf = [bm.faces.layers.float.new(n) for n in names_f]
    vmap = {}
    for (pid, keys), cos, iv, fv, sm in recs:
        vs = []
        for key, co in zip(keys, cos):
            v = vmap.get((pid, key))
            if v is None:
                v = vmap[(pid, key)] = bm.verts.new(co)
            vs.append(v)
        f = bm.faces.new(vs)
        for l_, val in zip(li, iv):
            f[l_] = val
        for l_, val in zip(lf, fv):
            f[l_] = val
        f.smooth = sm
    if len(bm.verts) != len(src.verts) or len(bm.faces) != len(src.faces):
        raise RuntimeError("canonical rebuild changed the element count")
    return bm


def fib_dirs(n):
    out = []
    ga = math.pi * (3 - math.sqrt(5))
    for i in range(n):
        z = 1 - 2 * (i + 0.5) / n
        rr = math.sqrt(max(0.0, 1 - z * z))
        out.append(Vector((rr * math.cos(ga * i), rr * math.sin(ga * i), z)))
    return out


def face_samples(f, spacing_m, pull_m):
    """Barycentric grid over the fan triangles of a face, spacing <= spacing_m, every point moved pull_m toward its
    triangle's centre (a sample on the rim of a part sunk 0.1 uu into another must stay inside that part)."""
    vs = [v.co for v in f.verts]
    pts = []
    for i in range(1, len(vs) - 1):
        a, b, c = vs[0], vs[i], vs[i + 1]
        n = max(1, int(math.ceil(max((b - a).length, (c - b).length, (a - c).length) / spacing_m)))
        ctr = (a + b + c) / 3
        for p in range(n + 1):
            for q in range(n + 1 - p):
                w0, w1 = p / n, q / n
                x = a * (1 - w0 - w1) + b * w0 + c * w1
                d = (ctr - x).length
                pts.append(x + (ctr - x) * min(1.0, pull_m / d) if d > 1e-12 else x)
    return pts


def classify_hidden(bm, ndirs, spacing_uu):
    """Hidden = no ray from any sample escapes within 1 m; downward rays are blocked by the ground z = 0.
    Samples: barycentric grid at <= spacing_uu over the face; directions: Fibonacci sphere, upper half, in the face's
    hemisphere (normal direction first)."""
    bvh = BVHTree.FromBMesh(bm)
    dirs = [d for d in fib_dirs(ndirs) if d.z >= 0.0]
    lay = bm.faces.layers.int.new("hidden")
    casts = samples_total = hidden = 0
    for f in bm.faces:
        n = f.normal
        cand = sorted((d for d in dirs if d.dot(n) > 0.02), key=lambda d: -d.dot(n))
        if n.z >= 0:
            cand = [n.copy()] + cand
        pts = face_samples(f, spacing_uu * M, 0.05 * M)
        samples_total += len(pts)
        visible = False
        for s in pts:
            o = s + n * 1e-5
            for d in cand:
                casts += 1
                if bvh.ray_cast(o, d, 1.0)[0] is None:
                    visible = True
                    break
            if visible:
                break
        f[lay] = 0 if visible else 1
        hidden += 0 if visible else 1
    return {"faces": len(bm.faces), "hidden_faces": hidden, "ray_casts": casts, "samples": samples_total,
            "directions_upper_hemisphere": len(dirs), "sample_spacing_uu": spacing_uu,
            "sample_pull_to_triangle_centre_uu": 0.05, "ray_origin_offset_along_normal_uu": 0.001}


def uv_mirrored_faces(obj):
    me = obj.data
    uv = me.uv_layers[0].data
    bad = 0
    for p in me.polygons:
        li = list(p.loop_indices)[:3]
        a, b, c = (me.vertices[me.loops[i].vertex_index].co for i in li)
        ua, ub, uc = (Vector(uv[i].uv) for i in li)
        e1, e2 = b - a, c - a
        du1, dv1 = (ub - ua)
        du2, dv2 = (uc - ua)
        det = du1 * dv2 - du2 * dv1
        if abs(det) < 1e-14:
            bad += 1
            continue
        dpdu = (e1 * dv2 - e2 * dv1) / det
        dpdv = (e2 * du1 - e1 * du2) / det
        bad += dpdu.cross(dpdv).dot(p.normal) < 0
    return int(bad)


def shell_topology(obj):
    """Per-shell topology without welding (shells never share vertices by construction)."""
    bm = bmesh.new()
    bm.from_mesh(obj.data)
    boundary = sum(1 for e in bm.edges if e.is_boundary)
    nonman = sum(1 for e in bm.edges if not e.is_manifold and not e.is_boundary)
    before = {f.index: f.normal.copy() for f in bm.faces}
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    flipped = sum(1 for f in bm.faces if before[f.index].dot(f.normal) < 0)
    bm.free()
    return {"open_edges": boundary, "non_manifold_edges": nonman, "faces_with_inconsistent_winding": flipped}


def class_density(obj, size):
    """px per uu at `size` for visible / hidden triangles, plus visible-only stretch (same method as uv_analysis)."""
    me = obj.data
    me.calc_loop_triangles()
    uv = me.uv_layers[0].data
    hid = np.zeros(len(me.polygons), dtype=np.int32)
    me.attributes["hidden"].data.foreach_get("value", hid)
    rows = []
    for t in me.loop_triangles:
        rows.append(([uv[i].uv[:] for i in t.loops], [me.vertices[i].co[:] for i in t.vertices], hid[t.polygon_index]))
    tuv = np.array([x[0] for x in rows])
    tpos = np.array([x[1] for x in rows])
    th = np.array([x[2] for x in rows])
    a_uv = 0.5 * np.abs((tuv[:, 1, 0] - tuv[:, 0, 0]) * (tuv[:, 2, 1] - tuv[:, 0, 1])
                        - (tuv[:, 2, 0] - tuv[:, 0, 0]) * (tuv[:, 1, 1] - tuv[:, 0, 1]))
    e1, e2 = tpos[:, 1] - tpos[:, 0], tpos[:, 2] - tpos[:, 0]
    a3 = 0.5 * np.linalg.norm(np.cross(e1, e2), axis=1)
    out = {}
    for lab, m in (("visible", th == 0), ("hidden", th == 1)):
        out[lab] = {"triangles": int(m.sum()), "area_uu2": r(a3[m].sum() * 1e4, 2),
                    "uv_area_fraction": r(a_uv[m].sum(), 4),
                    "px_per_uu": r(math.sqrt(a_uv[m].sum() / max(a3[m].sum(), 1e-12)) * size / 100.0, 3)}
    m = th == 0
    u1 = e1 / np.maximum(np.linalg.norm(e1, axis=1, keepdims=True), 1e-12)
    nrm = np.cross(e1, e2)
    nrm /= np.maximum(np.linalg.norm(nrm, axis=1, keepdims=True), 1e-12)
    v1 = np.cross(nrm, u1)
    Pm = np.stack([np.stack([(e1 * u1).sum(1), (e1 * v1).sum(1)], 1), np.stack([(e2 * u1).sum(1), (e2 * v1).sum(1)], 1)], 1)
    Q = np.stack([tuv[:, 1] - tuv[:, 0], tuv[:, 2] - tuv[:, 0]], 1)
    ok = m & (a3 > 1e-14) & (a_uv > 1e-14)
    J = np.linalg.solve(Pm[ok], Q[ok])
    sv = np.linalg.svd(J, compute_uv=False)
    dens = math.sqrt(a_uv[ok].sum() / a3[ok].sum())
    w = a3[ok] / a3[ok].sum()
    aniso = sv[:, 0] / np.maximum(sv[:, 1], 1e-12)
    area_ratio = (sv[:, 0] * sv[:, 1]) / dens ** 2

    def wp(x, q):
        o = np.argsort(x)
        c = np.cumsum(w[o])
        return float(x[o][min(np.searchsorted(c, q), len(x) - 1)])
    out["visible"]["stretch_area_ratio_p05_p50_p95"] = [r(wp(area_ratio, q), 3) for q in (0.05, 0.5, 0.95)]
    out["visible"]["stretch_anisotropy_p50_p95_max"] = [r(wp(aniso, 0.5), 3), r(wp(aniso, 0.95), 3), r(aniso.max(), 3)]
    return out, tuv, th


# ----------------------------------------------------------------------------- UV
def skyline_place(rects, W, H):
    """Deterministic skyline (bottom-left) packing of integer rectangles [(w, h)] in order; each may be turned 90 deg.
    Returns [(x, y, turned)] or None if they do not fit."""
    sky = [[0, 0, W]]  # segments [x, y, width], left to right, covering [0, W)
    out = []
    for w, h in rects:
        best = None
        for turned in (False, True):
            rw, rh = (h, w) if turned else (w, h)
            if rw > W or rh > H:
                continue
            for i in range(len(sky)):
                x = sky[i][0]
                if x + rw > W:
                    break
                y, j = 0, i
                while j < len(sky) and sky[j][0] < x + rw:
                    y = max(y, sky[j][1])
                    j += 1
                if y + rh > H:
                    continue
                score = (y + rh, x, turned)
                if best is None or score < best[0]:
                    best = (score, x, y, rw, rh, turned)
        if best is None:
            return None
        _sc, x, y, rw, rh, turned = best
        out.append((x, y, turned))
        new = []
        for sx, sy, sw in sky:
            ex = sx + sw
            if ex <= x or sx >= x + rw:
                new.append([sx, sy, sw])
                continue
            if sx < x:
                new.append([sx, sy, x - sx])
            if ex > x + rw:
                new.append([x + rw, sy, ex - (x + rw)])
        new.append([x, y + rh, rw])
        new.sort(key=lambda t: t[0])
        merged = []
        for seg in new:
            if merged and merged[-1][1] == seg[1] and merged[-1][0] + merged[-1][2] == seg[0]:
                merged[-1][2] += seg[2]
            else:
                merged.append(seg)
        sky = merged
    return out


def skyline_pack_islands(bm, uvl, islands, size, margin_px):
    """Replaces bpy.ops.uv.pack_islands (its result jittered at ~1e-6 between runs, so FBX/PNG bytes were not
    reproducible). Islands keep their relative scale; every island's box gets margin_px/2 padding on each side
    (>= margin_px between islands, >= margin_px/2 to the texture edge); the scale is the largest that fits
    (bisection, 24 steps); order: tallest first after turning each box wide side down, ties by first face index."""
    pad = margin_px // 2
    boxes = []
    for isl in islands:
        us = [l[uvl].uv.x for f in isl for l in f.loops]
        vs = [l[uvl].uv.y for f in isl for l in f.loops]
        w, h = max(us) - min(us), max(vs) - min(vs)
        first = min(f.index for f in isl)
        wide = w >= h
        boxes.append({"isl": isl, "u0": min(us), "v0": min(vs), "w": w, "h": h, "pre_turn": not wide, "first": first})
    boxes.sort(key=lambda b: (-min(b["w"], b["h"]), -max(b["w"], b["h"]), b["first"]))

    def rects(sc):
        return [(int(math.ceil(max(b["w"], b["h"]) * sc)) + 2 * pad, int(math.ceil(min(b["w"], b["h"]) * sc)) + 2 * pad)
                for b in boxes]
    area = sum(b["w"] * b["h"] for b in boxes)
    hi = math.sqrt(size * size / area)
    lo = hi / 4
    while skyline_place(rects(lo), size, size) is None:
        lo /= 2
    for _ in range(24):
        mid = (lo + hi) / 2
        if skyline_place(rects(mid), size, size) is None:
            hi = mid
        else:
            lo = mid
    sc = lo
    place = skyline_place(rects(sc), size, size)
    for b, (x, y, turned) in zip(boxes, place):
        rot = b["pre_turn"] != turned  # final 90 deg turn relative to the projection
        for f in b["isl"]:
            for l in f.loops:
                u, v = l[uvl].uv.x - b["u0"], l[uvl].uv.y - b["v0"]
                if rot:  # 90 deg counter-clockwise: (u, v) -> (h - v, u); keeps orientation (no mirror)
                    u, v = b["h"] - v, u
                l[uvl].uv = ((x + pad + u * sc) / size, (y + pad + v * sc) / size)
    return {"packer": "in-script skyline (deterministic)", "scale_px_per_projection_metre": r(sc, 4),
            "margin_px_between_islands_min": margin_px, "edge_padding_px_min": pad, "boxes": len(boxes)}


def unwrap(obj, P, parts):
    """Exact per-part box projection (no Smart UV averaging): every face is projected onto the plane of the part-frame
    axis closest to its normal, unmirrored; visible stud domes get one projection along the stud axis. Island key =
    (part, axis, sign, hidden), each key offset apart so different keys never share a UV. Density is then uniform on
    flat faces (chamfers at 45 deg compress by 0.71 across). Hidden-only islands x hidden scale, then pack."""
    U = P["uv"]
    me = obj.data
    bm = bmesh.new()
    bm.from_mesh(me)
    uvl = bm.loops.layers.uv.get("UVMap") or bm.loops.layers.uv.new("UVMap")
    hid, stud, part = (bm.faces.layers.int.get("hidden"), bm.faces.layers.float.get("is_stud"),
                       bm.faces.layers.int.get("part_id"))
    keys = {}
    n_axial = 0
    for f in bm.faces:
        o, ax, ay, az = parts[f[part]]["frame"]
        n = f.normal
        if f[stud] > 0.5 and f[hid] == 0 and n.dot(az) > 0:
            k, sgn, axis = 3, 1, az  # stud dome: along the stud axis (frame z = outward normal of the stud)
            n_axial += 1
        else:
            dots = [n.dot(ax), n.dot(ay), n.dot(az)]
            k = max(range(3), key=lambda i: (abs(dots[i]) - 1e-6 * i))
            sgn = 1 if dots[k] > 0 else -1
            axis = (ax, ay, az)[k]
        e1, e2 = [(ax, ay, az)[i] for i in range(3) if i != (k if k < 3 else 2)]
        if e1.cross(e2).dot(axis * sgn) < 0:
            e1 = -e1
        key = (f[part], k, sgn, f[hid])
        gi = keys.setdefault(key, len(keys))
        off = Vector((gi % 64, gi // 64)) * 2.0
        for l in f.loops:
            d = l.vert.co - o
            l[uvl].uv = (d.dot(e1) + off.x, d.dot(e2) + off.y)
    islands = bmesh_utils.bmesh_linked_uv_islands(bm, uvl)
    s = P["hidden_faces"]["uv_scale_for_hidden_only_islands"]
    scaled = mixed = 0
    for isl in islands:
        flags = {f[hid] for f in isl}
        if flags == {1}:
            loops = [l for f in isl for l in f.loops]
            us = [l[uvl].uv.x for l in loops]
            vs = [l[uvl].uv.y for l in loops]
            cu, cv = (min(us) + max(us)) / 2, (min(vs) + max(vs)) / 2
            for l in loops:
                l[uvl].uv = (cu + (l[uvl].uv.x - cu) * s, cv + (l[uvl].uv.y - cv) * s)
            scaled += 1
        elif len(flags) > 1:
            mixed += 1
    pack = skyline_pack_islands(bm, uvl, islands, P["texture_px"], P["uv"]["pack_margin_px"])
    bm.to_mesh(me)
    bm.free()
    me.update()
    return {"method": "per-part box projection (exact planes) + stud-axis projection for visible stud domes",
            "projection_groups": len(keys), "stud_dome_faces_axis_projected": n_axial, "islands": len(islands),
            "hidden_only_islands_scaled": scaled, "islands_mixing_hidden_and_visible_faces": mixed, "pack": pack}


# ----------------------------------------------------------------------------- bake material
def new(nt, typ, **props):
    n = nt.nodes.new(typ)
    for k, v in props.items():
        setattr(n, k, v)
    return n


def sock(node, name, kind=None, out=False):
    coll = node.outputs if out else node.inputs
    for s in coll:
        if s.name == name and (kind is None or s.type == kind) and s.enabled:
            return s
    for s in coll:
        if s.name == name and (kind is None or s.type == kind):
            return s
    raise KeyError("%s: no %s socket %s/%s" % (node.bl_idname, "output" if out else "input", name, kind))


def feed(nt, target, src):
    if isinstance(src, (int, float)):
        target.default_value = src
    elif isinstance(src, (tuple, list)):
        target.default_value = tuple(src) if len(src) == len(target.default_value) else tuple(src) + (1.0,)
    else:
        nt.links.new(src, target)


def math_(nt, op, a, b=None, clamp=False):
    n = new(nt, "ShaderNodeMath", operation=op, use_clamp=clamp)
    feed(nt, n.inputs[0], a)
    if b is not None:
        feed(nt, n.inputs[1], b)
    return n.outputs[0]


def mix_rgb(nt, fac, a, b):
    n = new(nt, "ShaderNodeMix", data_type="RGBA", blend_type="MIX", clamp_factor=True)
    feed(nt, sock(n, "Factor", "VALUE"), fac)
    feed(nt, sock(n, "A", "RGBA"), a)
    feed(nt, sock(n, "B", "RGBA"), b)
    return sock(n, "Result", "RGBA", out=True)


def mix_f(nt, fac, a, b):
    n = new(nt, "ShaderNodeMix", data_type="FLOAT", clamp_factor=True)
    feed(nt, sock(n, "Factor", "VALUE"), fac)
    feed(nt, sock(n, "A", "VALUE"), a)
    feed(nt, sock(n, "B", "VALUE"), b)
    return sock(n, "Result", "VALUE", out=True)


def scale_rgb(nt, col, k):
    comb = new(nt, "ShaderNodeCombineXYZ")
    for i in range(3):
        feed(nt, comb.inputs[i], k)
    vm = new(nt, "ShaderNodeVectorMath", operation="MULTIPLY")
    feed(nt, vm.inputs[0], col)
    nt.links.new(comb.outputs[0], vm.inputs[1])
    return vm.outputs[0]


def maprange(nt, v, a, b, c, d):
    n = new(nt, "ShaderNodeMapRange", interpolation_type="SMOOTHSTEP", clamp=True)
    feed(nt, sock(n, "Value", "VALUE"), v)
    for nm, val in (("From Min", a), ("From Max", b), ("To Min", c), ("To Max", d)):
        sock(n, nm, "VALUE").default_value = val
    return sock(n, "Result", "VALUE", out=True)


def attr(nt, name, out="Fac"):
    n = new(nt, "ShaderNodeAttribute", attribute_type="GEOMETRY", attribute_name=name)
    return n.outputs[out]


def noise(nt, vec, scale, detail, rough=0.55):
    n = new(nt, "ShaderNodeTexNoise")
    feed(nt, n.inputs["Vector"], vec)
    n.inputs["Scale"].default_value = scale
    n.inputs["Detail"].default_value = detail
    n.inputs["Roughness"].default_value = rough
    return n.outputs["Fac"]


def bake_material(P):
    pal = {k: srgb8_to_lin(v) for k, v in P["palette_srgb"].items() if k != "note"}
    S = P["surface"]
    mat = bpy.data.materials.new("BAKE_Crate")
    mat.use_nodes = True
    nt = mat.node_tree
    for n in list(nt.nodes):
        nt.nodes.remove(n)
    out = new(nt, "ShaderNodeOutputMaterial", target="CYCLES")
    grain = attr(nt, "grain", "Vector")
    rand = attr(nt, "part_rand")
    iron = attr(nt, "is_iron")
    chamf = attr(nt, "is_chamfer")
    stud = attr(nt, "is_stud")
    geo = new(nt, "ShaderNodeNewGeometry")
    pos, nrm = geo.outputs["Position"], geo.outputs["Normal"]
    bev = new(nt, "ShaderNodeBevel", samples=8)
    bev.inputs["Radius"].default_value = 0.003
    dot = new(nt, "ShaderNodeVectorMath", operation="DOT_PRODUCT")
    nt.links.new(bev.outputs["Normal"], dot.inputs[0])
    nt.links.new(nrm, dot.inputs[1])
    edge_soft = math_(nt, "MULTIPLY", math_(nt, "SUBTRACT", 1.0, sock(dot, "Value", out=True)), 30.0, clamp=True)
    sep = new(nt, "ShaderNodeSeparateXYZ")
    nt.links.new(grain, sep.inputs[0])
    s_ = math_(nt, "ADD", sep.outputs["Y"], math_(nt, "MULTIPLY", sep.outputs["Z"], 0.7))
    comb = new(nt, "ShaderNodeCombineXYZ")
    nt.links.new(s_, comb.inputs[0])
    nt.links.new(math_(nt, "MULTIPLY", sep.outputs["X"], 0.04), comb.inputs[1])
    nt.links.new(math_(nt, "MULTIPLY", rand, 5.0), comb.inputs[2])
    wave = new(nt, "ShaderNodeTexWave", wave_type="BANDS", bands_direction="X", wave_profile="SIN")
    nt.links.new(comb.outputs[0], wave.inputs["Vector"])
    wave.inputs["Scale"].default_value = 26.0
    wave.inputs["Distortion"].default_value = 4.0
    wave.inputs["Detail"].default_value = 2.0
    wave.inputs["Detail Scale"].default_value = 1.2
    streak = maprange(nt, wave.outputs["Fac"], 0.0, 0.28, 1.0, 0.0)
    blotch = noise(nt, pos, 35.0, 3.0)
    chip_n = noise(nt, pos, 160.0, 2.0)
    chip = maprange(nt, chip_n, 0.35, 0.65, 0.55, 1.0)
    aon = new(nt, "ShaderNodeAmbientOcclusion", samples=16, only_local=True, inside=False)
    aon.inputs["Distance"].default_value = 0.004
    convex = maprange(nt, aon.outputs["AO"], 0.72, 0.95, 0.0, 1.0)  # worn highlight on outer edges, not in grooves
    edge_f = math_(nt, "MULTIPLY", math_(nt, "MULTIPLY", math_(nt, "MAXIMUM", math_(nt, "MULTIPLY", chamf, 0.85),
                                                             math_(nt, "MULTIPLY", edge_soft, 0.7)), chip),
                   convex, clamp=True)
    sepn = new(nt, "ShaderNodeSeparateXYZ")
    nt.links.new(nrm, sepn.inputs[0])
    up = math_(nt, "MAXIMUM", sepn.outputs["Z"], 0.0)
    down = math_(nt, "MAXIMUM", math_(nt, "MULTIPLY", sepn.outputs["Z"], -1.0), 0.0)
    zen = math_(nt, "SUBTRACT", math_(nt, "ADD", 1.0, math_(nt, "MULTIPLY", up, 0.14)),
                math_(nt, "MULTIPLY", down, 0.12))
    wood = mix_rgb(nt, maprange(nt, blotch, 0.35, 0.65, 0.0, 1.0), pal["wood_mid"], pal["wood_blotch"])
    wood = mix_rgb(nt, math_(nt, "MULTIPLY", streak, 0.55), wood, pal["wood_dark"])
    wood = scale_rgb(nt, wood, math_(nt, "ADD", 0.86, math_(nt, "MULTIPLY", rand, 0.28)))
    wood = mix_rgb(nt, edge_f, wood, pal["wood_light"])
    iron_base = mix_rgb(nt, maprange(nt, blotch, 0.3, 0.7, 0.0, 1.0), pal["iron_dark"], pal["iron_mid"])
    iron_hl = math_(nt, "MULTIPLY",
                    math_(nt, "ADD", math_(nt, "ADD", math_(nt, "MULTIPLY", chamf, 0.7),
                                           math_(nt, "MULTIPLY", edge_soft, 0.6)),
                          math_(nt, "MULTIPLY", stud, math_(nt, "ADD", 0.25, math_(nt, "MULTIPLY", up, 0.5)))),
                    math_(nt, "MULTIPLY", chip, convex), clamp=True)
    iron_col = mix_rgb(nt, iron_hl, iron_base, pal["iron_light"])
    col = scale_rgb(nt, mix_rgb(nt, iron, wood, iron_col), zen)
    rough_w = math_(nt, "SUBTRACT", math_(nt, "ADD", S["roughness_wood"],
                                          math_(nt, "MULTIPLY", streak, S["roughness_wood_streak_add"])),
                    math_(nt, "MULTIPLY", edge_f, S["roughness_worn_edge_sub"]))
    rough_i = math_(nt, "ADD", math_(nt, "SUBTRACT", S["roughness_iron"], math_(nt, "MULTIPLY", iron_hl, 0.06)),
                    math_(nt, "MULTIPLY", math_(nt, "SUBTRACT", blotch, 0.5), 0.12))
    rough = mix_f(nt, iron, rough_w, rough_i)
    metal = math_(nt, "MULTIPLY", iron, S["metallic_iron"])
    hammer = noise(nt, pos, 220.0, 2.0)
    h_wood = math_(nt, "SUBTRACT", math_(nt, "ADD", math_(nt, "MULTIPLY", streak, -0.5),
                                         math_(nt, "MULTIPLY", math_(nt, "SUBTRACT", blotch, 0.5), 0.8)),
                   math_(nt, "MULTIPLY", edge_f, math_(nt, "MULTIPLY", chip_n, 0.6)))
    h_iron = math_(nt, "MULTIPLY", math_(nt, "SUBTRACT", hammer, 0.5), 0.3)
    height = mix_f(nt, iron, h_wood, h_iron)
    bump = new(nt, "ShaderNodeBump")
    bump.inputs["Strength"].default_value = 0.45
    bump.inputs["Distance"].default_value = 0.001
    nt.links.new(height, bump.inputs["Height"])
    emis = {}
    for key, src in (("BC", col), ("R", rough), ("M", metal)):
        e = new(nt, "ShaderNodeEmission")
        nt.links.new(src, e.inputs["Color"])
        e.inputs["Strength"].default_value = 1.0
        emis[key] = e
    bsdf = new(nt, "ShaderNodeBsdfPrincipled")
    nt.links.new(bump.outputs["Normal"], bsdf.inputs["Normal"])
    diff = new(nt, "ShaderNodeBsdfDiffuse")
    tex = new(nt, "ShaderNodeTexImage")
    nt.nodes.active = tex
    return mat, {"out": out, "emis": emis, "bsdf": bsdf, "diff": diff, "tex": tex}


def bake_pass(obj, mat, K, kind, img, samples, P):
    nt = mat.node_tree
    surf = K["out"].inputs["Surface"]
    for l in list(surf.links):
        nt.links.remove(l)
    if kind in ("BC", "R", "M"):
        nt.links.new(K["emis"][kind].outputs[0], surf)
        btype = "EMIT"
    elif kind == "N":
        nt.links.new(K["bsdf"].outputs[0], surf)
        btype = "NORMAL"
    else:
        nt.links.new(K["diff"].outputs[0], surf)
        btype = "AO"
    K["tex"].image = img
    nt.nodes.active = K["tex"]
    K["tex"].select = True
    scene = bpy.context.scene
    scene.cycles.samples = samples
    for o in scene.objects:
        o.select_set(False)
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj
    kw = dict(type=btype, margin=P["bake"]["margin_px"], margin_type="EXTEND", use_clear=True)
    if btype == "NORMAL":
        kw.update(normal_space="TANGENT", normal_r="POS_X", normal_g="POS_Y", normal_b="POS_Z")
    bpy.ops.object.bake(**kw)
    return H_["image_array"](img)


def dilate_mask(mask, it):
    m = mask.copy()
    for _ in range(it):
        g = m.copy()
        for dy in (-1, 0, 1):
            for dx in (-1, 0, 1):
                g |= np.roll(np.roll(m, dy, 0), dx, 1)
        m = g
    return m


# ----------------------------------------------------------------------------- export (as facades_build.py)
def export_with_relative_textures(obj, fbx_path, preset):
    from io_scene_fbx import export_fbx_bin
    orig_make = H_["make_fbx_deterministic"]
    fbx_dir = Path(fbx_path).parent

    def make():
        restore = orig_make()
        prev = export_fbx_bin._gen_vid_path

        def rel_path(img, scene_data):
            rel = os.path.relpath(bpy.path.abspath(img.filepath), fbx_dir).replace("\\", "/")
            return rel, rel
        export_fbx_bin._gen_vid_path = rel_path

        def restore_all():
            export_fbx_bin._gen_vid_path = prev
            restore()
        return restore_all

    H_["make_fbx_deterministic"] = make
    try:
        H_["export_fbx"](obj, fbx_path, preset)
    finally:
        H_["make_fbx_deterministic"] = orig_make


def fbx_absolute_path_leaks(path):
    data = Path(path).read_bytes()
    needles = [str(ROOT).encode(), str(ROOT).replace("\\", "/").encode(), b"C:\\", b"C:/", b"Users\\ren", b"Users/ren"]
    return sorted({n.decode() for n in needles if n in data})


# ----------------------------------------------------------------------------- previews
def setup_render(scene, w, h, bg=(0.05, 0.06, 0.08), strength=1.0):
    try:
        scene.render.engine = "BLENDER_EEVEE_NEXT"
    except TypeError:
        scene.render.engine = "BLENDER_EEVEE"
    scene.render.resolution_x, scene.render.resolution_y = w, h
    scene.render.resolution_percentage = 100
    scene.render.film_transparent = False
    scene.view_settings.view_transform = "Standard"
    scene.render.image_settings.file_format = "JPEG"
    scene.render.image_settings.quality = 90
    world = scene.world or bpy.data.worlds.new("World")
    scene.world = world
    world.use_nodes = True
    b = world.node_tree.nodes.get("Background")
    b.inputs["Color"].default_value = tuple(bg) + (1,)
    b.inputs["Strength"].default_value = strength


def add_lights(scene):
    objs = []
    for nm, energy, rot in (("Key", 3.0, (50, 0, 20)), ("Fill", 0.8, (65, 0, -150))):
        ld = bpy.data.lights.new("PV_" + nm, "SUN")
        ld.energy = energy
        ld.use_shadow = nm == "Key"
        o = bpy.data.objects.new("PV_" + nm, ld)
        o.rotation_euler = tuple(math.radians(a) for a in rot)
        scene.collection.objects.link(o)
        objs.append(o)
    return objs


def board(scene, PV):
    """Preview-only context as in facades_build.py: tray 714.5 x 612.6 x 40 uu, 6 x 5 tiles of 94 uu, 6 uu seams."""
    objs = []
    mt = bpy.data.materials.new("PV_Tray")
    mt.use_nodes = True
    mt.node_tree.nodes["Principled BSDF"].inputs["Base Color"].default_value = (0.02, 0.022, 0.028, 1)
    mc = bpy.data.materials.new("PV_Tile")
    mc.use_nodes = True
    mc.node_tree.nodes["Principled BSDF"].inputs["Base Color"].default_value = (0.09, 0.1, 0.12, 1)
    bm = bmesh.new()
    bmesh.ops.create_cube(bm, size=1.0)
    bmesh.ops.scale(bm, vec=(7.145, 6.126, 0.40), verts=bm.verts)
    bmesh.ops.translate(bm, vec=(0, 0, -0.20 - 0.005), verts=bm.verts)
    me = bpy.data.meshes.new("PV_Tray")
    bm.to_mesh(me)
    bm.free()
    me.materials.append(mt)
    o = bpy.data.objects.new("PV_Tray", me)
    scene.collection.objects.link(o)
    objs.append(o)
    bm = bmesh.new()
    t = PV["board_tile_uu"] / 100.0
    nx, ny = PV["board_tiles_x"], PV["board_tiles_y"]
    for cx in range(nx):
        for cy in range(ny):
            x0, y0 = (cx - nx / 2) + 0.03, (cy - ny / 2) + 0.03
            vs = [bm.verts.new((x0, y0, 0)), bm.verts.new((x0 + t, y0, 0)),
                  bm.verts.new((x0 + t, y0 + t, 0)), bm.verts.new((x0, y0 + t, 0))]
            bm.faces.new(vs)
    me = bpy.data.meshes.new("PV_Tiles")
    bm.to_mesh(me)
    bm.free()
    me.materials.append(mc)
    o = bpy.data.objects.new("PV_Tiles", me)
    scene.collection.objects.link(o)
    objs.append(o)
    return objs


def camera(scene, ortho, name="PV_Cam"):
    cd = bpy.data.cameras.new(name)
    cd.type = "ORTHO" if ortho else "PERSP"
    cd.sensor_fit = "HORIZONTAL"
    cam = bpy.data.objects.new(name, cd)
    scene.collection.objects.link(cam)
    scene.camera = cam
    return cam


def look(cam, pos, target):
    cam.location = pos
    cam.rotation_euler = (Vector(target) - Vector(pos)).to_track_quat("-Z", "Y").to_euler()


def render(scene, path):
    scene.render.filepath = str(path)
    bpy.ops.render.render(write_still=True)
    return path


def save_jpeg(arr, path):
    h, w = arr.shape[:2]
    img = bpy.data.images.new(Path(path).stem, w, h, alpha=False, float_buffer=False)
    a = np.ones((h, w, 4), dtype=np.float32)
    a[..., :3] = np.clip(arr[..., :3], 0, 1)
    img.pixels.foreach_set(a.ravel())
    img.filepath_raw = str(path)
    img.file_format = "JPEG"
    img.save()
    bpy.data.images.remove(img)


def uv_layout_jpeg(tuv, th, bc_srgb, size, path):
    img = bc_srgb[..., :3].copy() * 0.55
    for t, hflag in zip(tuv, th):
        p = t * size
        colr = (0.25, 0.75, 1.0) if hflag else (1.0, 0.9, 0.1)
        for a, b in ((0, 1), (1, 2), (2, 0)):
            n = int(max(abs(p[b] - p[a]).max(), 1)) * 2
            xs = np.clip(np.linspace(p[a][0], p[b][0], n).astype(int), 0, size - 1)
            ys = np.clip(np.linspace(p[a][1], p[b][1], n).astype(int), 0, size - 1)
            img[ys, xs, :3] = colr
    save_jpeg(img, path)


# ----------------------------------------------------------------------------- main
def main():
    params_path = Path(sys.argv[sys.argv.index("--") + 1]).resolve()
    P = json.loads(params_path.read_text(encoding="utf-8"))
    out = ROOT / P["out_dir"]
    preset_path = ROOT / P["fbx_preset"]
    preset = json.loads(preset_path.read_text(encoding="utf-8"))
    for sub in ("work", "export", "reports", "preview", "textures"):
        (out / sub).mkdir(parents=True, exist_ok=True)
    ref = ROOT / P["reference"]["path"]
    ref_sha = sha256(ref)
    if ref_sha != P["reference"]["sha256"]:
        raise SystemExit("reference image sha256 mismatch")
    S = P["texture_px"]

    bpy.ops.wm.read_factory_settings(use_empty=True)  # fresh headless process only
    scene = bpy.context.scene
    scene.unit_settings.system = "METRIC"
    scene.unit_settings.scale_length = 1.0

    # ---------------------------------------------------------------- geometry
    B = Builder()
    studs_smooth = build_crate(P, B)
    bmesh.ops.recalc_face_normals(B.bm, faces=B.bm.faces)
    stud_smooth_set = set(studs_smooth)
    for f in B.bm.faces:
        f.smooth = f in stud_smooth_set
    bm = canonical_bmesh(B.bm)
    B.bm.free()
    bm.normal_update()
    hid_stats = classify_hidden(bm, P["hidden_faces"]["directions"], P["hidden_faces"]["sample_spacing_uu"])
    quads = len(bm.faces)
    bmesh.ops.triangulate(bm, faces=bm.faces[:], quad_method="BEAUTY", ngon_method="BEAUTY")
    me = bpy.data.meshes.new(P["asset_name"])
    bm.to_mesh(me)
    bm.free()
    obj = bpy.data.objects.new(P["asset_name"], me)
    scene.collection.objects.link(obj)
    # grain coordinates (part-local frame, metres) as a point attribute for the bake shader
    pid = np.zeros(len(me.polygons), dtype=np.int32)
    me.attributes["part_id"].data.foreach_get("value", pid)
    vpart = np.full(len(me.vertices), -1, dtype=np.int64)
    for p in me.polygons:
        for vi in p.vertices:
            vpart[vi] = pid[p.index]
    grain = np.zeros((len(me.vertices), 3), dtype=np.float32)
    for v in me.vertices:
        o, ax, ay, az = B.parts[vpart[v.index]]["frame"]
        d = v.co - o
        grain[v.index] = (d.dot(ax), d.dot(ay), d.dot(az))
    ga = me.attributes.new("grain", "FLOAT_VECTOR", "POINT")
    ga.data.foreach_set("vector", grain.ravel())
    me.update()

    # ---------------------------------------------------------------- UV
    uv_meta = unwrap(obj, P, B.parts)
    me.calc_loop_triangles()

    # ---------------------------------------------------------------- bake
    scene.render.engine = "CYCLES"
    scene.cycles.device = P["bake"]["device"]
    scene.cycles.seed = P["bake"]["seed"]
    scene.cycles.use_denoising = False
    scene.render.bake.margin = P["bake"]["margin_px"]
    scene.render.bake.margin_type = "EXTEND"
    scene.world = bpy.data.worlds.new("BakeWorld")
    scene.world.light_settings.distance = P["bake"]["ao_distance_m"]
    mat_bake, K = bake_material(P)
    me.materials.append(mat_bake)
    ground_me = bpy.data.meshes.new("BAKE_Ground")
    gbm = bmesh.new()
    gv = [gbm.verts.new(c) for c in ((-2, -2, 0), (2, -2, 0), (2, 2, 0), (-2, 2, 0))]
    gbm.faces.new(gv)
    gbm.to_mesh(ground_me)
    gbm.free()
    ground = bpy.data.objects.new("BAKE_Ground", ground_me)
    scene.collection.objects.link(ground)
    imgs = {k: bpy.data.images.new("BAKE_" + k, S, S, alpha=True, float_buffer=True) for k in ("BC", "R", "M", "N", "AO")}
    for im in imgs.values():
        im.colorspace_settings.name = "Non-Color"
    samples = {"BC": P["bake"]["emit_samples"], "R": P["bake"]["emit_samples"], "M": P["bake"]["emit_samples"],
               "N": P["bake"]["normal_samples"], "AO": P["bake"]["ao_samples"]}
    arrs = {}
    for k in ("BC", "R", "M", "N"):
        ground.hide_render = True
        arrs[k] = bake_pass(obj, mat_bake, K, k, imgs[k], samples[k], P)
    ground.hide_render = False
    arrs["AO"] = bake_pass(obj, mat_bake, K, "AO", imgs["AO"], samples["AO"], P)
    bpy.data.objects.remove(ground)
    bpy.data.meshes.remove(ground_me)

    # coverage masks (row 0 = bottom, as Blender pixels)
    rows = [(np.array([me.uv_layers[0].data[i].uv[:] for i in t.loops]), t.polygon_index) for t in me.loop_triangles]
    hid_face = np.zeros(len(me.polygons), dtype=np.int32)
    me.attributes["hidden"].data.foreach_get("value", hid_face)
    tuv_all = np.array([x[0] for x in rows])
    t_hidden = np.array([hid_face[x[1]] for x in rows])
    cov = H_["raster_triangles"](tuv_all, S) > 0
    cov_vis = H_["raster_triangles"](tuv_all[t_hidden == 0], S) > 0
    baked_zone = dilate_mask(cov, P["bake"]["margin_px"])
    ao = np.clip(arrs["AO"][..., 0], 0, 1)
    k_ao = P["bake"]["ao_in_basecolor_strength"]
    bc_lin = np.clip(arrs["BC"][..., :3], 0, 1) * (1 - k_ao * (1 - ao))[..., None]
    fill_bc = np.median(bc_lin[cov_vis], axis=0)
    bc_lin[~baked_zone] = fill_bc
    bc_srgb = H_["lin_to_srgb"](bc_lin)
    nmap = np.clip(arrs["N"][..., :3], 0, 1).copy()
    nmap[..., 1] = 1.0 - nmap[..., 1]  # OpenGL (Blender bake) -> DirectX (UE)
    nmap[~baked_zone] = (0.5, 0.5, 1.0)
    rough = np.clip(arrs["R"][..., 0], 0, 1)
    metal = np.clip(arrs["M"][..., 0], 0, 1)
    orm = np.stack([ao, rough, metal], -1)
    orm[~baked_zone] = (1.0, float(np.median(rough[cov_vis])), 0.0)
    tex_paths = {k: out / "textures" / ("%s_%s.png" % (P["texture_prefix"], k)) for k in ("BC", "N", "ORM")}
    H_["save_png"](bc_srgb, S, tex_paths["BC"], "sRGB")
    H_["save_png"](nmap, S, tex_paths["N"], "Non-Color")
    H_["save_png"](orm, S, tex_paths["ORM"], "Non-Color")

    def png_chunk_names(pth):
        _d, ch = H_["png_chunks"](pth)
        return sorted({t.decode() for t, _s, _e in ch if t in H_["PNG_COLOR_CHUNKS"]})

    # texture measurements on texels of visible faces
    bc8 = np.round(bc_srgb * 255)
    nv = nmap[cov] * 2 - 1
    tilt = np.degrees(np.arccos(np.clip(nv[:, 2] / np.maximum(np.linalg.norm(nv, axis=1), 1e-9), -1, 1)))
    iron_px = metal[cov_vis] > 0.3
    tex_meas = {
        "size_px": S,
        "texels_covered_all_faces": int(cov.sum()), "texels_covered_visible_faces": int(cov_vis.sum()),
        "bc_srgb8_median_visible": [int(v) for v in np.median(bc8[cov_vis], 0)],
        "bc_srgb8_median_visible_wood": [int(v) for v in np.median(bc8[cov_vis][~iron_px], 0)],
        "bc_srgb8_median_visible_iron": [int(v) for v in np.median(bc8[cov_vis][iron_px], 0)] if iron_px.any() else None,
        "bc_srgb8_p05_p95_luma_visible": [r(np.percentile((bc8[cov_vis] @ [0.2126, 0.7152, 0.0722]), q), 1) for q in (5, 95)],
        "normal_tilt_deg_p50_p95_max_covered": [r(np.percentile(tilt, 50), 2), r(np.percentile(tilt, 95), 2), r(tilt.max(), 2)],
        "ao_visible_p05_p50_mean": [r(np.percentile(ao[cov_vis], 5), 3), r(np.percentile(ao[cov_vis], 50), 3), r(ao[cov_vis].mean(), 3)],
        "roughness_visible_mean": r(rough[cov_vis].mean(), 3),
        "roughness_ge_0_6_fraction_visible_texels": r((rough[cov_vis] >= 0.6).mean(), 4),
        "metallic_visible_mean": r(metal[cov_vis].mean(), 4),
        "metallic_gt_0_3_fraction_visible_texels": r(iron_px.mean(), 4),
        "note": "Visible texels = UV raster of faces not classified hidden; uniform density on them, so texel fractions ~ area fractions.",
    }
    textures = {
        "BC": {"path": tex_paths["BC"].relative_to(ROOT).as_posix(), "colorspace": "sRGB", "ue": "sRGB, TC_Default",
               "png_color_chunks": png_chunk_names(tex_paths["BC"]), "sha256": sha256(tex_paths["BC"])},
        "N": {"path": tex_paths["N"].relative_to(ROOT).as_posix(), "colorspace": "Linear (Non-Color)",
              "convention": "DirectX (green flipped from Blender's OpenGL tangent bake)", "ue": "TC_Normalmap, flip_green false",
              "png_color_chunks": png_chunk_names(tex_paths["N"]), "sha256": sha256(tex_paths["N"])},
        "ORM": {"path": tex_paths["ORM"].relative_to(ROOT).as_posix(), "colorspace": "Linear (Non-Color)",
                "channels": {"R": "AO baked in Cycles (%d spp, %.0f uu, ground plane z=0)" % (P["bake"]["ao_samples"], P["bake"]["ao_distance_m"] * 100),
                             "G": "roughness (procedural)", "B": "metallic (iron caps/studs %.2f, else 0)" % P["surface"]["metallic_iron"]},
                "ue": "TC_Masks, sRGB off", "png_color_chunks": png_chunk_names(tex_paths["ORM"]), "sha256": sha256(tex_paths["ORM"])},
    }

    # ---------------------------------------------------------------- final material, measurements, export
    me.materials.clear()
    bc_img = bpy.data.images.load(str(tex_paths["BC"]))
    bc_img.colorspace_settings.name = "sRGB"
    n_img = bpy.data.images.load(str(tex_paths["N"]))
    n_img.colorspace_settings.name = "Non-Color"
    orm_img = bpy.data.images.load(str(tex_paths["ORM"]))
    orm_img.colorspace_settings.name = "Non-Color"
    m_final = H_["build_material"](P["material_name"], bc_img, n_img, orm_img)
    me.materials.append(m_final)
    bpy.data.materials.remove(mat_bake)

    dens, tuv_d, th_d = class_density(obj, S)
    uv, tuv = H_["uv_analysis"](obj, S)
    parts_by_kind = {}
    for p in B.parts:
        parts_by_kind[p["kind"]] = parts_by_kind.get(p["kind"], 0) + 1
    # remove build-only attributes (the FBX exporter would ignore them; removed so the export copy is clean)
    for nm in ("grain", "part_rand", "is_iron", "is_chamfer", "is_stud"):
        me.attributes.remove(me.attributes[nm])
    tri_by = {}
    part_arr = np.zeros(len(me.polygons), dtype=np.int32)
    me.attributes["part_id"].data.foreach_get("value", part_arr)
    for pi in part_arr:
        k = B.parts[pi]["kind"]
        tri_by[k] = tri_by.get(k, 0) + 1
    geo, _fl = H_["geometry_stats"](obj)
    topo = shell_topology(obj)
    lo, hi = H_["world_bounds"]([obj])
    dims = [r((hi[i] - lo[i]) * 100, 3) for i in range(3)]
    brace_pts = [v.co for p in me.polygons if B.parts[part_arr[p.index]]["kind"] == "brace" for v in
                 (me.vertices[i] for i in p.vertices)]
    brace_side_y = sorted({("-Y" if c.y < 0 else "+Y") for c in brace_pts})
    kw = H_["fbx_kwargs"](preset)
    rows_um = H_["um_fbx_v1_conformance"](preset, kw, obj, scene)
    area_total = sum(p.area for p in me.polygons) * 1e4
    area_hidden = sum(p.area for p in me.polygons if hid_face[p.index]) * 1e4
    report = {
        "schema": "unmatched.decor-crate.build/1", "status": "measured",
        "claims": {"art_accepted": False, "game_ready": False, "budgets_declared": False, "ue_imported": False},
        "asset_id": P["asset_id"], "run_id": P["run_id"],
        "blender_version": bpy.app.version_string,
        "script": Path(__file__).resolve().relative_to(ROOT).as_posix(), "script_sha256_lf": text_sha(__file__),
        "helpers": {"path": SPC.relative_to(ROOT).as_posix(), "sha256_lf": SPC_SHA,
                    "used": ["export_fbx", "make_fbx_deterministic", "patch_fbx_units", "fbx_kwargs",
                             "um_fbx_v1_conformance", "geometry_stats", "uv_analysis", "raster_triangles",
                             "build_material", "save_png", "png_chunks", "image_array", "srgb_to_lin", "lin_to_srgb"]},
        "params": params_path.relative_to(ROOT).as_posix(), "params_sha256_lf": text_sha(params_path),
        "reference": {"path": P["reference"]["path"], "sha256": ref_sha, "use": P["reference"]["use"]},
        "fbx_preset": {"path": P["fbx_preset"], "sha256_lf": text_sha(preset_path)},
        "units": "Blender metres; uu = cm = FBX numbers (UnitScaleFactor 1.0)",
        "asset_name": P["asset_name"],
        "parts": {"count": len(B.parts), "by_kind": parts_by_kind, "list": [
            {k: v for k, v in p.items() if k != "frame"} for p in B.parts]},
        "faces_before_triangulation": quads,
        "triangles": H_["triangles"](obj), "triangles_by_kind": tri_by, "vertices": len(me.vertices),
        "geometry_welded_1e-6m": geo,
        "topology_per_shell_unwelded": topo,
        "smooth_faces": sum(1 for p in me.polygons if p.use_smooth),
        "smooth_note": "stud domes smooth (base flat); all wood/iron boards flat-shaded (chamfers are real geometry)",
        "hidden_faces": dict(hid_stats, method=P["hidden_faces"]["method"],
                             area_uu2_total=r(area_total, 2), area_uu2_hidden=r(area_hidden, 2),
                             hidden_area_fraction=r(area_hidden / area_total, 4)),
        "bounds_min_uu": [r(v * 100, 3) for v in lo], "bounds_max_uu": [r(v * 100, 3) for v in hi],
        "dimensions_uu_x_y_z": dims,
        "pivot": {"origin": [0.0, 0.0, 0.0], "rule": "04 §1: decor crate = centre of the base",
                  "min_z_uu": r(lo.z * 100, 6), "x_centre_offset_uu": r((lo.x + hi.x) * 50, 6),
                  "y_centre_offset_uu": r((lo.y + hi.y) * 50, 6)},
        "front": {"rule": "04 §1: front = -Y in Blender (-> +X in UE)", "x_brace_sides_blender": brace_side_y,
                  "note": "X braces on the front (-Y) and the back (+Y): the crate reads the same after a 180 deg turn; plain planks on +-X."},
        "material_slots": [m.name for m in me.materials],
        "uv_unwrap": dict(uv_meta,
                          pack_margin_px_at_1024=P["uv"]["pack_margin_px"],
                          hidden_island_scale=P["hidden_faces"]["uv_scale_for_hidden_only_islands"]),
        "uv0": uv, "uv0_by_visibility": dens, "uv_mirrored_faces": uv_mirrored_faces(obj),
        "textures": textures, "texture_measurements": tex_meas,
        "bake": dict({k: v for k, v in P["bake"].items()}, engine="Cycles"),
        "collision": "none (04 §3.7: decor not interactive; clicks go through to L1). UE import: no collision (build profile collision: none).",
        "um_fbx_v1_rows": rows_um, "um_fbx_v1_conforms": all(x["conforms"] for x in rows_um),
    }
    # export copy without the build-only face attributes
    for nm in ("part_id", "hidden"):
        if nm in me.attributes:
            report.setdefault("build_attributes_removed_before_export", []).append(nm)
    keep = {nm: np.zeros(len(me.polygons), dtype=np.int32) for nm in ("part_id", "hidden")}
    for nm in keep:
        me.attributes[nm].data.foreach_get("value", keep[nm])
        me.attributes.remove(me.attributes[nm])
    fbx = out / "export" / (P["asset_name"] + ".fbx")
    export_with_relative_textures(obj, fbx, preset)
    fbx_bytes = fbx.read_bytes()
    report["export"] = {"fbx": fbx.relative_to(ROOT).as_posix(), "sha256": sha256(fbx), "bytes": fbx.stat().st_size,
                        "absolute_path_leaks": fbx_absolute_path_leaks(fbx),
                        "texture_refs": sorted({s for s in ("../textures/%s_%s.png" % (P["texture_prefix"], k)
                                                            for k in ("BC", "N", "ORM")) if s.encode() in fbx_bytes})}
    for nm, arr in keep.items():
        a = me.attributes.new(nm, "INT", "FACE")
        a.data.foreach_set("value", arr)
    tol = 0.01
    report["checks"] = {
        "single_mesh_no_armature": True,
        "closed_shells_consistent_winding_unwelded": topo["open_edges"] == 0 and topo["non_manifold_edges"] == 0
                                                     and topo["faces_with_inconsistent_winding"] == 0,
        "closed_manifold_welded_1e-6m": geo["welded_boundary_edges"] == 0 and geo["welded_non_manifold_edges"] == 0
                                         and geo["faces_with_inconsistent_winding"] == 0 and geo["signed_volume_m3"] > 0,
        "shells_equal_parts": geo["connected_shells"] == len(B.parts),
        "no_degenerate_faces": geo["degenerate_faces_area_lt_1e-12"] == 0,
        "size_25_uu_proposed_all_axes": all(abs(d - P["size_uu"]) <= tol for d in dims),
        "pivot_base_centre": abs(lo.z) < 1e-9 and abs(lo.x + hi.x) < 1e-9 and abs(lo.y + hi.y) < 1e-9,
        "x_brace_on_front_and_back_only": brace_side_y == ["+Y", "-Y"],
        "material_slots_le_2": len(me.materials) <= 2,
        "uv0_in_0_1_no_overlap": uv["triangles_out_of_0_1"] == 0 and uv["overlap_pixels_between_islands"] == 0
                                 and uv["overlap_pixels_inside_islands_strict"] == 0,
        "uv_not_mirrored": report["uv_mirrored_faces"] == 0,
        "min_gutter_ge_4px_at_1024": (uv["min_gutter_px_estimate"] or 99) >= 4,
        "texture_1k": S == 1024,
        "n_orm_no_png_color_chunks": textures["N"]["png_color_chunks"] == [] and textures["ORM"]["png_color_chunks"] == [],
        "roughness_ge_0_6_on_ge_90pct_visible": tex_meas["roughness_ge_0_6_fraction_visible_texels"] >= 0.9,
        "no_absolute_paths_in_fbx": not report["export"]["absolute_path_leaks"],
        "um_fbx_v1_conforms": report["um_fbx_v1_conforms"],
    }
    report["checks_passed"] = all(report["checks"].values())

    # ---------------------------------------------------------------- previews
    PV = P["preview"]
    prev = {}
    uv_layout_jpeg(tuv_d, th_d, bc_srgb, S, out / "preview" / "SM_Decor_Crate_uv0-layout.jpg")
    prev["uv0_layout"] = out / "preview" / "SM_Decor_Crate_uv0-layout.jpg"
    setup_render(scene, 900, 900, bg=(0.21, 0.21, 0.22), strength=0.9)
    scene.eevee.taa_render_samples = 64
    lights = add_lights(scene)
    cam = camera(scene, ortho=True)
    c = (lo + hi) / 2
    cam.data.ortho_scale = 0.25 * 1.3
    for key, pos in (("front-ortho", (0.0, -3.0, c.z)), ("side-ortho", (3.0, 0.0, c.z)), ("top-ortho", (0.0, -1e-4, 3.0))):
        look(cam, Vector(pos), c)
        prev[key] = render(scene, out / "preview" / ("SM_Decor_Crate_%s.jpg" % key))
    pc = camera(scene, ortho=False, name="PV_Persp")
    pc.data.angle = math.radians(20.0)
    yaw, el, dist = math.radians(35.0), math.radians(22.0), 1.25
    look(pc, c + Vector((math.sin(yaw) * math.cos(el), -math.cos(yaw) * math.cos(el), math.sin(el))) * dist, c)
    prev["3q"] = render(scene, out / "preview" / "SM_Decor_Crate_3q-front-right.jpg")
    # wireframe over the shaded model
    wf = obj.copy()
    wf.data = obj.data.copy()
    scene.collection.objects.link(wf)
    mod = wf.modifiers.new("WF", "WIREFRAME")
    mod.thickness = 0.0005
    mod.use_replace = True
    wm = bpy.data.materials.new("PV_Wire")
    wm.use_nodes = True
    bs = wm.node_tree.nodes["Principled BSDF"]
    bs.inputs["Base Color"].default_value = (1.0, 0.85, 0.2, 1)
    bs.inputs["Emission Color"].default_value = (1.0, 0.85, 0.2, 1)
    bs.inputs["Emission Strength"].default_value = 2.0
    wf.data.materials.clear()
    wf.data.materials.append(wm)
    prev["wire"] = render(scene, out / "preview" / "SM_Decor_Crate_3q-wireframe.jpg")
    bpy.data.objects.remove(wf)
    # hidden-face check: faces classified hidden drawn in red; red must not show from outside
    red = bpy.data.materials.new("PV_Hidden")
    red.use_nodes = True
    bs = red.node_tree.nodes["Principled BSDF"]
    bs.inputs["Base Color"].default_value = (1.0, 0.0, 0.0, 1)
    bs.inputs["Emission Color"].default_value = (1.0, 0.0, 0.0, 1)
    bs.inputs["Emission Strength"].default_value = 1.0
    me.materials.append(red)
    red_px = {}
    for p in me.polygons:
        p.material_index = 1 if keep["hidden"][p.index] else 0
    for key, yaw_d, el_d in (("front-right-30", 35.0, 30.0), ("back-left-30", 215.0, 30.0), ("side-low-5", 100.0, 5.0),
                             ("top-down-80", 10.0, 80.0)):
        yw, ev = math.radians(yaw_d), math.radians(el_d)
        look(pc, c + Vector((math.sin(yw) * math.cos(ev), -math.cos(yw) * math.cos(ev), math.sin(ev))) * dist, c)
        prev["hidden_check_" + key] = render(scene, out / "preview" / ("SM_Decor_Crate_hidden-check_%s.jpg" % key))
        chk = bpy.data.images.load(str(prev["hidden_check_" + key]))
        px = H_["image_array"](chk)
        red_px[key] = int(((px[..., 0] > 170 / 255) & (px[..., 1] < 70 / 255) & (px[..., 2] < 70 / 255)).sum())
        bpy.data.images.remove(chk)
    for p in me.polygons:
        p.material_index = 0
    me.materials.pop(index=1)
    report["hidden_face_check"] = {"red_pixels_per_view_900x900": red_px, "threshold_srgb": "R>170, G<70, B<70",
                                   "views": "yaw/elevation 35/30, 215/30, 100/5, 10/80 deg around the crate, persp 20 deg"}
    report["checks"]["hidden_faces_not_visible_in_4_views"] = all(v == 0 for v in red_px.values())
    report["checks_passed"] = all(report["checks"].values())
    # game camera (03 §2): FOV 35 deg horizontal, pitch -55 deg, 12 m; crate + P1.5 barrel on the east tray margin
    setup_render(scene, 1200, 675)
    board_objs = board(scene, PV)
    bpy.ops.import_scene.fbx(filepath=str(ROOT / PV["barrel_fbx"]))
    barrel = [o for o in bpy.context.selected_objects if o.type == "MESH"][0]
    barrel.location = (PV["barrel_xy_m"][0], PV["barrel_xy_m"][1], 0.0)
    obj.location = (PV["crate_xy_m"][0], PV["crate_xy_m"][1], 0.0)
    gc = camera(scene, ortho=False, name="PV_Game")
    gc.data.angle = math.radians(35.0)
    dist, pitch = 12.0, math.radians(55.0)
    cam_pos = Vector((0.0, -dist * math.cos(pitch), dist * math.sin(pitch)))
    look(gc, cam_pos, (0.0, 0.0, 0.0))
    bpy.context.view_layer.update()
    prev["k1_exact"] = render(scene, out / "preview" / "SM_Decor_Crate_game-k1-exact-12m.jpg")
    # on-screen size at 1920x1080 in exact K-1 (projected bounding box of the crate)
    corners = [Vector((obj.location.x + x, obj.location.y + y, z)) for x in (lo.x, hi.x) for y in (lo.y, hi.y) for z in (lo.z, hi.z)]
    ndc = [world_to_camera_view(scene, gc, p) for p in corners]
    wpx = (max(p.x for p in ndc) - min(p.x for p in ndc)) * 1920
    hpx = (max(p.y for p in ndc) - min(p.y for p in ndc)) * 1080
    cx_ = (sum(p.x for p in ndc) / 8, sum(p.y for p in ndc) / 8)
    report["k1_exact_frame_analysis"] = {
        "crate_location_m": [PV["crate_xy_m"][0], PV["crate_xy_m"][1], 0.0],
        "projected_bbox_px_at_1920x1080": [r(wpx, 1), r(hpx, 1)],
        "bbox_centre_ndc": [r(cx_[0], 4), r(cx_[1], 4)],
        "in_frame": all(0 <= p.x <= 1 and 0 <= p.y <= 1 for p in ndc),
        "texel_density_needed_at_k1_px_per_uu": r(wpx / 25.0, 3),
    }
    # same camera, 4x crop around the crate (lens x4 + shift): same projection, more pixels
    k = 4.0
    gc.data.angle = 2 * math.atan(math.tan(math.radians(17.5)) / k)
    gc.data.shift_x = (cx_[0] - 0.5) * k
    gc.data.shift_y = (cx_[1] - 0.5) * k * 675 / 1200
    prev["k1_crop4"] = render(scene, out / "preview" / "SM_Decor_Crate_game-k1-same-camera-crop4x.jpg")
    gc.data.shift_x = gc.data.shift_y = 0.0
    # game angles close-up (pitch -55 deg, FOV 35, close_up_distance_m, aimed at the crate centre): not a game zoom level
    gc.data.angle = math.radians(35.0)
    cd_ = PV["close_up_distance_m"]
    tgt = Vector((PV["crate_xy_m"][0], PV["crate_xy_m"][1], 0.125))
    look(gc, tgt + Vector((0.0, -cd_ * math.cos(pitch), cd_ * math.sin(pitch))), tgt)
    prev["game_close"] = render(scene, out / "preview" / ("SM_Decor_Crate_game-angles-close-%sm-with-barrel.jpg"
                                                          % str(cd_).replace(".", "p")))
    obj.location = (0.0, 0.0, 0.0)
    report["previews"] = {kk: {"path": v.relative_to(ROOT).as_posix()} for kk, v in prev.items()}
    report["preview_note"] = ("EEVEE, neutral sun key (shadowed) + fill, not the P1.7 control scene. Ortho/3q/wire on a grey "
                              "backdrop like the concept. Game shots: FOV 35 deg horizontal, pitch -55 deg, 12 m (03 §2), 16:9, "
                              "board 6x5 tiles of 94 uu, crate and the P1.5 barrel FBX on the east tray margin by the far row "
                              "(layout suggestion only). crop4x = same camera position and projection, lens x4 with shift (more "
                              "pixels, not what K-1 shows). UV layout: yellow = visible-face triangles, blue = hidden-only "
                              "islands (packed at 1/4 density).")
    for o in board_objs + lights + [barrel]:
        o.hide_render = True
    bpy.ops.wm.save_as_mainfile(filepath=str(out / "work" / "decor-crate.blend"), compress=True)
    report["work_blend"] = (out / "work" / "decor-crate.blend").relative_to(ROOT).as_posix() + " (transient, gitignored)"
    (out / "reports" / "build-report.json").write_text(json.dumps(report, indent=1, ensure_ascii=False), encoding="utf-8")
    print("CRATE_BUILD", json.dumps({"tris": report["triangles"], "dims": dims, "checks": report["checks"],
                                     "px_per_uu": {k2: v["px_per_uu"] for k2, v in dens.items()}}))
    if not report["checks_passed"]:
        raise SystemExit("checks failed: %s" % [k2 for k2, v in report["checks"].items() if not v])


main()
