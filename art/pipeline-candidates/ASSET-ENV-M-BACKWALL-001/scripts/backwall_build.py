"""ASSET-ENV-M-BACKWALL-001: build the Marmoreal palace back wall modules (headless Blender, Cycles bakes on the CPU).

  blender -b --factory-startup -t 4 --python-exit-code 1 --python \
      art/pipeline-candidates/ASSET-ENV-M-BACKWALL-001/scripts/backwall_build.py -- \
      art/pipeline-candidates/ASSET-ENV-M-BACKWALL-001/20261001-backwall-v1/reports/backwall-params.json

Three modules (params 'modules'), all numbers proposed:
  SM_Env_BackWall_BayDoor     one ArcadeBay wide: an arched door recess + two small upper windows
  SM_Env_BackWall_BayWindows  one ArcadeBay wide: two tall arched windows + an oculus
  SM_Env_BackWall_Centre      the Portal width, taller: a big arched door + two small upper windows, no hedge
Each: a 16 uu marble slab (front face at local x 0, front = +X), plinth, half pilasters at both ends (adjacent modules
complete each other), capitals, a string course, a cornice; arched openings cut as RECESSES (exact booleans) whose back
faces glow (no lights: emissive via the texture), archivolt frames, sills, dark mullions; a lumpy dark hedge strip at the
foot (bays) and a rose garland swag under the cornice (leaf + rose blobs) + roses on the hedge.
Texturing: all modules share ONE atlas (smart UV project over the three meshes, uniform texel density). A G-buffer is
baked with Cycles on the CPU (EMIT: object position, normal, part id; AO), the colours are shaded in numpy from it
(Marble012 triplanar + ashlar joints on the slab, lighter trim, warm glow, dark frames, Moss002 hedge, leaves, roses),
the height (joints, marble / moss relief) is turned into a tangent-space normal map by a Cycles NORMAL bake through a
Bump node (MikkTSpace, as UE), green flipped to DirectX. Outputs: T_Env_BackWall_BC (sRGB 2K), _N (DirectX 2K), _ORM
(2K: R AO, G roughness, B 0), _E (1K emissive mask: 1 on the glow faces). The glow BC sits in a narrow HSV window, so
M_EnvProp's EmissiveWindow can light exactly those texels without a new material (checked here).
Checks: triangles per module; front at x 0 / width / height; the glow texels inside the emissive window and nothing else;
1 mesh, 1 slot, UV0 in 0..1, round trip; UM_FBX_v1 rows conform; layout clearances (hedge vs arcade back, centre vs
portal, the west end vs the cypress, the key-light shadow vs the map frame).
Outputs: export/SM_Env_BackWall_*.fbx + T_Env_BackWall_*.png, reports/build-report.json, reports/backwall-layout.json.
"""

import json
import math
import sys
from pathlib import Path

import bmesh
import bpy
import numpy as np

HERE = Path(__file__).resolve()
REPO = HERE.parents[4]
sys.path.insert(0, str(REPO / "tools" / "art" / "env_kit"))
import k_blender as K  # noqa: E402

S, r = K.S, K.r
SCHEMA = "unmatched.env-m-backwall.build-report/1"
SLOTS = ("marble", "trim", "glow", "frame", "hedge", "leaf", "rose")
M_MARBLE, M_TRIM, M_GLOW, M_FRAME, M_HEDGE, M_LEAF, M_ROSE = range(7)
ASSET_NAMES = {"Bay_Door": "SM_Env_BackWall_BayDoor", "Bay_Windows": "SM_Env_BackWall_BayWindows",
               "Centre": "SM_Env_BackWall_Centre"}


# ----------------------------------------------------------------------------- primitives (UE numbers)
def box(mb, lo, hi, mat, tag):
    x0, y0, z0 = lo
    x1, y1, z1 = hi
    b = mb.add_verts([(x0, y0, z0), (x1, y0, z0), (x1, y1, z0), (x0, y1, z0),
                      (x0, y0, z1), (x1, y0, z1), (x1, y1, z1), (x0, y1, z1)])
    for f in ((0, 3, 2, 1), (4, 5, 6, 7), (0, 1, 5, 4), (1, 2, 6, 5), (2, 3, 7, 6), (3, 0, 4, 7)):
        mb.add_face([b + i for i in f], [(0.0, 0.0)] * 4, mat, tag=tag)


def prism(mb, poly, x0, x1, mat_side, mat_back, mat_front, tag):
    """Polygon poly (list of (y, z), CCW seen from +X) extruded along X from x0 (back cap) to x1 (front cap)."""
    n = len(poly)
    a = mb.add_verts([(x0, y, z) for y, z in poly])
    b = mb.add_verts([(x1, y, z) for y, z in poly])
    mb.add_face([b + i for i in range(n)], [(0.0, 0.0)] * n, mat_front, tag=tag)
    mb.add_face([a + i for i in range(n)][::-1], [(0.0, 0.0)] * n, mat_back, tag=tag)
    for i in range(n):
        j = (i + 1) % n
        mb.add_face([a + i, a + j, b + j, b + i], [(0.0, 0.0)] * 4, mat_side, tag=tag)


def arch_poly(yc, width, z0, spring, grow=0.0, seg=14):
    """Rectangle + semicircle (CCW seen from +X: +Y is to the left when looking along -X... we list it CCW in (y, z))."""
    hw = width / 2 + grow
    pts = [(yc - hw, z0 - grow), (yc + hw, z0 - grow)]
    for i in range(seg + 1):
        t = math.pi * i / seg
        pts.append((yc + hw * math.cos(t), spring + hw * math.sin(t)))
    pts.append((yc - hw, z0 - grow))
    return dedupe(pts)


def circle_poly(yc, zc, rad, seg=20):
    return [(yc + rad * math.cos(2 * math.pi * i / seg), zc + rad * math.sin(2 * math.pi * i / seg)) for i in range(seg)]


def dedupe(pts):
    out = []
    for p in pts:
        if not out or math.dist(p, out[-1]) > 1e-6:
            out.append(p)
    if math.dist(out[0], out[-1]) < 1e-6:
        out.pop()
    return out


def poly_ccw(poly):
    a = sum(poly[i][0] * poly[(i + 1) % len(poly)][1] - poly[(i + 1) % len(poly)][0] * poly[i][1] for i in range(len(poly)))
    return poly if a > 0 else poly[::-1]


def icosphere(subdiv=1):
    t = (1 + 5 ** 0.5) / 2
    V = [(-1, t, 0), (1, t, 0), (-1, -t, 0), (1, -t, 0), (0, -1, t), (0, 1, t), (0, -1, -t), (0, 1, -t),
         (t, 0, -1), (t, 0, 1), (-t, 0, -1), (-t, 0, 1)]
    V = [np.array(v, float) / np.linalg.norm(v) for v in V]
    F = [(0, 11, 5), (0, 5, 1), (0, 1, 7), (0, 7, 10), (0, 10, 11), (1, 5, 9), (5, 11, 4), (11, 10, 2), (10, 7, 6),
         (7, 1, 8), (3, 9, 4), (3, 4, 2), (3, 2, 6), (3, 6, 8), (3, 8, 9), (4, 9, 5), (2, 4, 11), (6, 2, 10), (8, 6, 7),
         (9, 8, 1)]
    for _ in range(subdiv):
        cache, F2 = {}, []

        def mid(a, b):
            k = (min(a, b), max(a, b))
            if k not in cache:
                m = V[a] + V[b]
                V.append(m / np.linalg.norm(m))
                cache[k] = len(V) - 1
            return cache[k]
        for a, b, c in F:
            ab, bc, ca = mid(a, b), mid(b, c), mid(c, a)
            F2 += [(a, ab, ca), (b, bc, ab), (c, ca, bc), (ab, bc, ca)]
        F = F2
    return np.array(V), F


ICO = icosphere(1)


def blob(mb, c, rad, squash, mat, tag, rng):
    V, F = ICO
    P = V * rad * np.array([squash[0], squash[1], squash[2]]) * (1 + rng.uniform(-0.12, 0.12, size=(len(V), 1)))
    b = mb.add_verts(P + np.asarray(c))
    for f in F:
        mb.add_face([b + i for i in f], [(0.0, 0.0)] * 3, mat, tag=tag)


def value_noise3(p, cell, seed):
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
                w = ((f[..., 0] if dx else 1 - f[..., 0]) * (f[..., 1] if dy else 1 - f[..., 1])
                     * (f[..., 2] if dz else 1 - f[..., 2]))
                out = out + w * h(i0[..., 0] + dx, i0[..., 1] + dy, i0[..., 2] + dz)
    return out


def hedge(mb, P, W):
    H = P["hedge"]
    x0, x1, hz = float(H["back_x"]), float(H["front_x"]), float(H["height"])
    hy = W / 2 - float(H["end_inset"])
    n = int(H["cuts"])
    cx, cz = (x0 + x1) / 2, hz / 2
    ex, ey, ez = (x1 - x0) / 2, hy, hz / 2

    def disp(p):
        d = np.array([(p[0] - cx) / ex ** 2, p[1] / ey ** 2, (p[2] - cz) / ez ** 2])
        d = d / max(np.linalg.norm(d), 1e-9)
        amt = float(H["lump_uu"]) * (value_noise3(np.array([p]), float(H["noise_uu"]), int(H["seed"]))[0] - 0.25)
        q = np.array(p, float) + d * amt
        if p[2] <= 1e-6:
            q[2] = 0.0
        # round the top edges a little
        return q
    faces = []
    # each box face as an n x m grid; long faces get more columns
    ny = max(n, int(2 * hy / 6.0))
    for axis, sign in (("x", 1), ("x", -1), ("z", 1), ("y", 1), ("y", -1)):
        if axis == "x":
            us, vs = np.linspace(-hy, hy, ny + 1), np.linspace(0, hz, n // 2 + 2)
            grid = [[(x1 if sign > 0 else x0, u, v) for u in us] for v in vs]
        elif axis == "z":
            us, vs = np.linspace(-hy, hy, ny + 1), np.linspace(x0, x1, n // 2 + 2)
            grid = [[(v, u, hz) for u in us] for v in vs]
        else:
            us, vs = np.linspace(x0, x1, n // 2 + 2), np.linspace(0, hz, n // 2 + 2)
            grid = [[(u, sign * hy, v) for u in us] for v in vs]
        rows = [mb.add_verts([disp(p) for p in row]) for row in grid]
        for j in range(len(grid) - 1):
            for i in range(len(grid[0]) - 1):
                idx = [rows[j] + i, rows[j] + i + 1, rows[j + 1] + i + 1, rows[j + 1] + i]
                V = np.array([mb.V[k] for k in idx])
                nn = np.cross(V[1] - V[0], V[3] - V[0])
                c = V.mean(0) - np.array([cx, 0.0, 0.0 if axis != "z" else -100.0])
                want = {"x": np.array([sign, 0, 0]), "z": np.array([0, 0, 1]), "y": np.array([0, sign, 0])}[axis]
                if np.dot(nn, want) < 0:
                    idx = idx[::-1]
                faces.append(idx)
                mb.add_face(idx, [(0.0, 0.0)] * 4, M_HEDGE, tag="hedge")
    return faces


def garland(mb, P, W, H, rng, with_hedge, over):
    G = P["garland"]
    hw = W / 2 - float(G["end_inset"])
    top = H - float(over.get("garland_drop", G["drop_below_top"]))
    sag = float(over.get("garland_sag", G["sag"]))
    x = float(G["x"])

    def zf(y):
        return top - sag * (1 - (y / hw) ** 2)
    ys = np.linspace(-hw, hw, 400)
    pts = np.c_[np.full_like(ys, x), ys, [zf(y) for y in ys]]
    arc = np.r_[0, np.cumsum(np.linalg.norm(np.diff(pts, axis=0), axis=1))]
    s = 0.0
    k = 0
    while s <= arc[-1]:
        p = pts[np.searchsorted(arc, s).clip(0, len(pts) - 1)]
        for dz in (-1.6, 1.6):
            blob(mb, p + np.array([rng.uniform(0, 1.6), rng.uniform(-1, 1), dz + rng.uniform(-0.8, 0.8)]),
                 rng.uniform(*G["leaf_r"]), (0.75, 1.0, 0.8), M_LEAF, "leaf", rng)
        s += float(G["leaf_step"])
        k += 1
    s = float(G["rose_step"]) / 2
    while s <= arc[-1]:
        p = pts[np.searchsorted(arc, s).clip(0, len(pts) - 1)]
        blob(mb, p + np.array([3.0, rng.uniform(-1.5, 1.5), rng.uniform(-1.2, 1.2)]), rng.uniform(*G["rose_r"]),
             (0.9, 1.0, 0.9), M_ROSE, "rose", rng)
        s += float(G["rose_step"])
    for end in (-1, 1):
        for i in range(int(G["tail"])):
            blob(mb, (x + 0.8, end * hw + rng.uniform(-1, 1), top - 6.0 * (i + 1)), rng.uniform(*G["leaf_r"]) * 0.85,
                 (0.75, 1.0, 0.85), M_LEAF, "leaf", rng)
        blob(mb, (x + 2.5, end * hw, top - 6.0 * int(G["tail"]) - 4.0), G["rose_r"][1], (0.9, 1.0, 0.9), M_ROSE, "rose", rng)
    if with_hedge:
        Hh = P["hedge"]
        for i in range(int(G["hedge_roses"])):
            y = rng.uniform(-(W / 2 - float(Hh["end_inset"]) - 6), W / 2 - float(Hh["end_inset"]) - 6)
            blob(mb, (float(Hh["front_x"]) - 3.0, y, float(Hh["height"]) + 0.5), rng.uniform(*G["rose_r"]),
                 (0.9, 1.0, 0.9), M_ROSE, "rose", rng)


# ----------------------------------------------------------------------------- Blender helpers
def materials():
    out = []
    for i, n in enumerate(SLOTS):
        m = bpy.data.materials.new("BW_" + n)
        m.use_nodes = True
        out.append(m)
    return out


def obj_from(mb, mats):
    o = mb.to_object(mats)
    return o


def apply_modifiers(o):
    dg = bpy.context.evaluated_depsgraph_get()
    ev = o.evaluated_get(dg)
    me = bpy.data.meshes.new_from_object(ev)
    o.modifiers.clear()
    old = o.data
    o.data = me
    bpy.data.meshes.remove(old)


def boolean(target, cutter, op="DIFFERENCE"):
    m = target.modifiers.new("b", "BOOLEAN")
    m.operation = op
    m.object = cutter
    solvers = [i.identifier for i in m.bl_rna.properties["solver"].enum_items]
    m.solver = "EXACT" if "EXACT" in solvers else solvers[-1]
    if hasattr(m, "use_self"):
        m.use_self = True
    apply_modifiers(target)


def join(objs, name):
    with bpy.context.temp_override(active_object=objs[0], object=objs[0], selected_objects=objs,
                                   selected_editable_objects=objs):
        bpy.ops.object.join()
    o = objs[0]
    o.name = name
    o.data.name = name
    return o


def build_module(P, key, mats):
    M = P["modules"][key]
    Wl = P["wall"]
    W, H = float(M["width"]), float(M["height"])
    hw = W / 2
    T = float(Wl["thickness"])
    rng = np.random.default_rng([20261001, list(P["modules"]).index(key)])
    # 1. marble body: slab + plinth + pilasters + capitals + string course + cornice + top band (overlapping closed shells)
    body = K.MeshBuilder("body", n_uv=1)
    box(body, (-T, -hw, 0.0), (0.0, hw, H), M_MARBLE, "slab")
    pd, ph = Wl["plinth"]
    box(body, (-T, -hw, 0.0), (pd, hw, ph), M_TRIM, "plinth")
    phw, pdp = float(Wl["pilaster_half"]), float(Wl["pilaster_depth"])
    cd, ch = Wl["capital"]
    cod, coh = Wl["cornice"]
    tbd, tbh = Wl["top_band"]
    for s in (-1, 1):
        y0, y1 = sorted((s * hw, s * (hw - phw)))
        box(body, (-T, y0, ph), (pdp, y1, H - coh - tbh - ch), M_TRIM, "pilaster")
        y0c, y1c = sorted((s * hw, s * (hw - phw - 1.5)))
        box(body, (-T, y0c, H - coh - tbh - ch), (cd, y1c, H - coh - tbh), M_TRIM, "capital")
    scd, scz, sch = Wl["string_course"]
    box(body, (-T, -hw, scz), (scd, hw, scz + sch), M_TRIM, "string")
    box(body, (-T, -hw, H - coh - tbh), (cod, hw, H - tbh), M_TRIM, "cornice")
    box(body, (-T, -hw, H - tbh), (tbd, hw, H), M_TRIM, "topband")
    o_body = obj_from(body, mats)
    # 2. cut the recesses (back cap = glow, sides = trim)
    extras = K.MeshBuilder("extras", n_uv=1)
    for op in M["openings"]:
        rec = float(op["recess"])
        fr = float(op["frame"])
        if op["kind"] == "oculus":
            poly = poly_ccw(circle_poly(float(op["y"]), float(op["z"]), float(op["radius"])))
            outer = poly_ccw(circle_poly(float(op["y"]), float(op["z"]), float(op["radius"]) + fr))
            sill = None
        else:
            poly = poly_ccw(arch_poly(float(op["y"]), float(op["width"]), float(op["z0"]), float(op["spring"])))
            outer = poly_ccw(arch_poly(float(op["y"]), float(op["width"]), float(op["z0"]), float(op["spring"]), fr))
            sill = op["kind"] == "window"
        cut = K.MeshBuilder("cut", n_uv=1)
        prism(cut, poly, -rec, 12.0, M_TRIM, M_GLOW, M_TRIM, "cut")
        o_cut = obj_from(cut, mats)
        boolean(o_body, o_cut)
        bpy.data.objects.remove(o_cut)
        # archivolt ring: outer prism minus a slightly longer inner prism (the opening), on the face x 0 .. 1.5
        ring = K.MeshBuilder("ring", n_uv=1)
        prism(ring, outer, -0.5, 1.5, M_TRIM, M_TRIM, M_TRIM, "frame")
        o_ring = obj_from(ring, mats)
        hole = K.MeshBuilder("hole", n_uv=1)
        prism(hole, poly, -2.0, 3.0, M_TRIM, M_TRIM, M_TRIM, "cut")
        o_hole = obj_from(hole, mats)
        boolean(o_ring, o_hole)
        bpy.data.objects.remove(o_hole)
        boolean(o_body, o_ring, "UNION")
        bpy.data.objects.remove(o_ring)
        # sill + mullions (dark) on the glow back
        yc = float(op["y"])
        if sill:
            w = float(op["width"])
            box(extras, (0.0, yc - w / 2 - 3.0, float(op["z0"]) - 3.0), (3.0, yc + w / 2 + 3.0, float(op["z0"])), M_TRIM, "sill")
        xb = -rec
        if op["kind"] == "oculus":
            z = float(op["z"])
            rr = float(op["radius"])
            box(extras, (xb, yc - 0.7, z - rr), (xb + 1.0, yc + 0.7, z + rr), M_FRAME, "mullion")
            box(extras, (xb, yc - rr, z - 0.7), (xb + 1.0, yc + rr, z + 0.7), M_FRAME, "mullion")
        elif op["kind"] == "window":
            w = float(op["width"])
            z0, sp = float(op["z0"]), float(op["spring"])
            box(extras, (xb, yc - 0.8, z0), (xb + 1.0, yc + 0.8, sp + w / 2), M_FRAME, "mullion")
            zt = z0 + (sp - z0) * 0.6
            box(extras, (xb, yc - w / 2, zt - 0.8), (xb + 1.0, yc + w / 2, zt + 0.8), M_FRAME, "mullion")
        else:  # door: two door leaves standing open (dark), a transom bar at the spring
            w = float(op["width"])
            z0, sp = float(op["z0"]), float(op["spring"])
            for s in (-1, 1):
                box(extras, (xb, yc + s * (w / 2 - 6.0) - 3.0, z0), (xb + 5.0, yc + s * (w / 2 - 6.0) + 3.0, sp - 1.0),
                    M_FRAME, "door")
            box(extras, (xb, yc - w / 2, sp - 1.2), (xb + 1.2, yc + w / 2, sp + 1.2), M_FRAME, "mullion")
    if M.get("hedge"):
        hedge(extras, P, W)
    if M.get("garland"):
        garland(extras, P, W, H, rng, bool(M.get("hedge")), M)
    o_extras = obj_from(extras, mats)
    o = join([o_body, o_extras], ASSET_NAMES[key])
    o.pass_index = list(P["modules"]).index(key) + 1
    me = o.data
    bm = bmesh.new()
    bm.from_mesh(me)
    bmesh.ops.dissolve_degenerate(bm, dist=1e-5, edges=bm.edges[:])
    bm.to_mesh(me)
    bm.free()
    for p in me.polygons:
        p.use_smooth = False
    return o


# ----------------------------------------------------------------------------- UV + bakes
def smart_uv(objs):
    for o in bpy.context.scene.objects:
        o.select_set(o in objs)
    bpy.context.view_layer.objects.active = objs[0]
    for o in objs:
        if not o.data.uv_layers:
            o.data.uv_layers.new(name="UVMap")
    bpy.ops.object.mode_set(mode="EDIT")
    bpy.ops.mesh.select_all(action="SELECT")
    bpy.ops.uv.smart_project(angle_limit=math.radians(60.0), island_margin=0.004, area_weight=0.0,
                             correct_aspect=True, scale_to_bounds=False)
    bpy.ops.object.mode_set(mode="OBJECT")


def emission_tree(m, color_socket_fn, image):
    nt = m.node_tree
    for n in list(nt.nodes):
        nt.nodes.remove(n)
    out = nt.nodes.new("ShaderNodeOutputMaterial")
    em = nt.nodes.new("ShaderNodeEmission")
    em.inputs["Strength"].default_value = 1.0
    nt.links.new(em.outputs["Emission"], out.inputs["Surface"])
    color_socket_fn(nt, em.inputs["Color"])
    tex = nt.nodes.new("ShaderNodeTexImage")
    tex.image = image
    nt.nodes.active = tex
    return nt


def bake(objs, type_, image, mats, color_fn=None, margin=8, extra=None):
    for i, m in enumerate(mats):
        if color_fn is not None:
            emission_tree(m, lambda nt, sock, i=i: color_fn(nt, sock, i), image)
        else:
            nt = m.node_tree
            tex = next((n for n in nt.nodes if n.type == "TEX_IMAGE" and n.image == image), None)
            if tex is None:
                tex = nt.nodes.new("ShaderNodeTexImage")
                tex.image = image
            nt.nodes.active = tex
    for o in bpy.context.scene.objects:
        o.select_set(o in objs)
    bpy.context.view_layer.objects.active = objs[0]
    sc = bpy.context.scene
    sc.render.bake.margin = margin
    if hasattr(sc.render.bake, "margin_type"):
        sc.render.bake.margin_type = "EXTEND"
    kw = {"type": type_, "margin": margin, "use_clear": extra is None or extra.get("clear", True)}
    if extra and "normal_space" in extra:
        kw["normal_space"] = extra["normal_space"]
    bpy.ops.object.bake(**kw)


def new_image(name, size, float_buffer=True, color=(0, 0, 0, 0)):
    img = bpy.data.images.new(name, size, size, alpha=True, float_buffer=float_buffer)
    img.colorspace_settings.name = "Non-Color"
    img.generated_color = color
    return img


def load_rgb(path):
    img = bpy.data.images.load(str(path))
    img.colorspace_settings.name = "Non-Color"
    a = S.image_array(img)[..., :3].astype(np.float64)
    return a  # raw stored values (sRGB-encoded for colour maps), row 0 = bottom


def sample(tex, u, v):
    h, w = tex.shape[:2]
    x = (np.mod(u, 1.0) * w).astype(np.int64) % w
    y = (np.mod(v, 1.0) * h).astype(np.int64) % h
    return tex[y, x]


def triplanar(tex, pos, nrm, tile):
    ax = np.argmax(np.abs(nrm), axis=-1)
    u = np.where(ax == 0, pos[..., 1], np.where(ax == 1, pos[..., 0], pos[..., 0])) / tile
    v = np.where(ax == 2, pos[..., 1], pos[..., 2]) / tile
    return sample(tex, u, v)


def hsv(rgb):
    mx, mn = rgb.max(-1), rgb.min(-1)
    d = mx - mn
    h = np.zeros_like(mx)
    m = d > 1e-9
    r_, g_, b_ = rgb[..., 0], rgb[..., 1], rgb[..., 2]
    hr = np.where(mx == r_, ((g_ - b_) / np.where(m, d, 1)) % 6, 0)
    hg = np.where(mx == g_, (b_ - r_) / np.where(m, d, 1) + 2, 0)
    hb = np.where(mx == b_, (r_ - g_) / np.where(m, d, 1) + 4, 0)
    h = np.where(mx == r_, hr, np.where(mx == g_, hg, hb)) * 60.0
    h = np.where(m, h, 0.0)
    s = np.where(mx > 1e-9, d / np.where(mx > 1e-9, mx, 1), 0.0)
    return h % 360.0, s, mx


def shade(P, gb, cc0):
    """numpy shading from the G-buffer -> BC (sRGB), height (uu), roughness, emissive mask, per texel."""
    L = P["look"]
    pos_b = gb["pos"] * 8.0 - 4.0          # .blend metres
    nrm_b = gb["nrm"] * 2.0 - 1.0
    pos = np.stack([-pos_b[..., 1], -pos_b[..., 0], pos_b[..., 2]], -1) * 100.0   # UE numbers (uu)
    nrm = np.stack([-nrm_b[..., 1], -nrm_b[..., 0], nrm_b[..., 2]], -1)
    slot = np.clip(np.floor(gb["id"][..., 0] * 8.0), 0, 7).astype(int)
    covered = gb["id"][..., 1] > 0.05
    H, W = slot.shape
    bc = np.zeros((H, W, 3))
    height = np.zeros((H, W))
    rough = np.zeros((H, W))
    emis = np.zeros((H, W))
    marble = triplanar(cc0["marble"], pos, nrm, float(L["marble_tile_uu"]))
    marble_h = triplanar(cc0["marble_h"], pos, nrm, float(L["marble_tile_uu"]))[..., 0]
    tint = np.array(L["marble_tint_srgb"])
    # ashlar joints on the slab (wall-plane coordinates: (y, z) on X-facing faces, (x, z) on Y-facing faces)
    ax = np.argmax(np.abs(nrm), axis=-1)
    bu = np.where(ax == 0, pos[..., 1], pos[..., 0])
    bv = pos[..., 2]
    bw, bh = L["block"]
    row = np.floor(bv / bh)
    uu = bu / bw + 0.5 * (row % 2)
    dj = np.minimum(np.abs(uu - np.round(uu)) * bw, np.abs(bv / bh - np.round(bv / bh)) * bh)
    jw = float(L["joint_uu"])
    joint = np.clip(1.0 - dj / jw, 0.0, 1.0) * (ax != 2)
    rr = L["roughness"]
    m = slot == M_MARBLE
    bc[m] = (marble[m] * float(L["marble_value"]) * tint) * (1 - joint[m, None] * (1 - float(L["joint_dark"])))
    height[m] = marble_h[m] * 0.25 - joint[m] * 0.6
    rough[m] = rr["marble"] + joint[m] * 0.3
    m = slot == M_TRIM
    bc[m] = np.clip(marble[m] * float(L["trim_value"]) * tint, 0, 1)
    height[m] = marble_h[m] * 0.2
    rough[m] = rr["trim"]
    m = slot == M_GLOW
    zt = np.clip((pos[..., 2] - 0.0) / 200.0, 0, 1)
    gt, gbm = np.array(L["glow_srgb_top"]), np.array(L["glow_srgb_bottom"])
    bc[m] = gbm[None] * (1 - zt[m, None]) + gt[None] * zt[m, None]
    rough[m] = rr["glow"]
    emis[m] = 1.0
    m = slot == M_FRAME
    bc[m] = np.array(L["frame_srgb"])
    rough[m] = rr["frame"]
    m = slot == M_HEDGE
    moss = triplanar(cc0["moss"], pos, nrm, float(L["hedge_tile_uu"]))
    moss_h = triplanar(cc0["moss_h"], pos, nrm, float(L["hedge_tile_uu"]))[..., 0]
    bc[m] = moss[m] * float(L["hedge_value"])
    height[m] = moss_h[m] * 1.5
    rough[m] = rr["hedge"]
    nz = value_noise3(pos, 3.0, 5)
    m = slot == M_LEAF
    bc[m] = np.array(L["leaf_srgb"]) * (0.75 + 0.5 * nz[m, None])
    height[m] = nz[m] * 0.6
    rough[m] = rr["leaf"]
    m = slot == M_ROSE
    bc[m] = np.array(L["rose_srgb"]) * (0.8 + 0.35 * nz[m, None])
    height[m] = nz[m] * 0.8
    rough[m] = rr["rose"]
    bc[~covered] = 0.5
    return {"bc": np.clip(bc, 0, 1), "height": height, "rough": np.clip(rough, 0, 1), "emis": emis, "slot": slot,
            "covered": covered}


def emissive_window_check(P, sh):
    w = P["look"]["emissive_window"]
    h, s, v = hsv(sh["bc"])
    hd = np.abs((h - float(w["hue_deg"]) + 180.0) % 360.0 - 180.0)
    inside = (hd <= float(w["hue_half_deg"])) & (s >= float(w["sat_min"])) & (v >= float(w["val_min"]))
    cov = sh["covered"]
    glow = (sh["slot"] == M_GLOW) & cov
    other = (~(sh["slot"] == M_GLOW)) & cov
    return {"window": w, "glowTexels": int(glow.sum()), "glowInsideFraction": r(float(inside[glow].mean()) if glow.any() else 0, 5),
            "otherTexels": int(other.sum()), "otherInsideFraction": r(float(inside[other].mean()) if other.any() else 0, 6)}


def main():
    P = K.load_params(K.script_args()[0])
    run = P["_run"]
    bpy.ops.wm.read_factory_settings(use_empty=True)
    sc = K.setup_cycles_cpu(1, (64, 64))
    mats = materials()
    objs = [build_module(P, key, mats) for key in P["modules"]]
    smart_uv(objs)
    size = int(P["atlas_size"])
    imgs = {k: new_image("gb_" + k, size) for k in ("pos", "nrm", "id")}
    bk = P["bake"]

    def col_pos(nt, sock, i):
        g = nt.nodes.new("ShaderNodeNewGeometry")
        a = nt.nodes.new("ShaderNodeVectorMath")
        a.operation = "MULTIPLY_ADD"
        a.inputs[1].default_value = (0.125, 0.125, 0.125)
        a.inputs[2].default_value = (0.5, 0.5, 0.5)
        nt.links.new(g.outputs["Position"], a.inputs[0])
        nt.links.new(a.outputs[0], sock)

    def col_nrm(nt, sock, i):
        g = nt.nodes.new("ShaderNodeNewGeometry")
        a = nt.nodes.new("ShaderNodeVectorMath")
        a.operation = "MULTIPLY_ADD"
        a.inputs[1].default_value = (0.5, 0.5, 0.5)
        a.inputs[2].default_value = (0.5, 0.5, 0.5)
        nt.links.new(g.outputs["True Normal"], a.inputs[0])
        nt.links.new(a.outputs[0], sock)

    def col_id(nt, sock, i):
        oi = nt.nodes.new("ShaderNodeObjectInfo")
        mth = nt.nodes.new("ShaderNodeMath")
        mth.operation = "MULTIPLY_ADD"
        mth.inputs[1].default_value = 0.25
        mth.inputs[2].default_value = 0.0
        nt.links.new(oi.outputs["Object Index"], mth.inputs[0])
        cmb = nt.nodes.new("ShaderNodeCombineColor")
        cmb.inputs["Red"].default_value = i / 8.0 + 1 / 16.0
        cmb.inputs["Blue"].default_value = 1.0
        nt.links.new(mth.outputs[0], cmb.inputs["Green"])
        nt.links.new(cmb.outputs["Color"], sock)
    for key, fn in (("pos", col_pos), ("nrm", col_nrm), ("id", col_id)):
        bake(objs, "EMIT", imgs[key], mats, fn, int(bk["margin_px"]))
    gb = {k: S.image_array(v)[..., :3].astype(np.float64) for k, v in imgs.items()}
    # AO per module alone (the modules overlap in space at the origin)
    sc.cycles.samples = int(bk["samples_ao"])
    sc.world = bpy.data.worlds.new("W")
    ao_img = new_image("gb_ao", size, True, (1, 1, 1, 1))
    for i, m in enumerate(mats):
        emission_tree(m, lambda nt, sock: None, ao_img)
    sc.render.bake.use_clear = False
    for o in objs:
        for x in objs:
            x.hide_render = x is not o
        with bpy.context.temp_override():
            pass
        for x in bpy.context.scene.objects:
            x.select_set(x is o)
        bpy.context.view_layer.objects.active = o
        sc.render.bake.margin = int(bk["margin_px"])
        sc.world.light_settings.distance = float(bk["ao_distance_m"])
        bpy.ops.object.bake(type="AO", margin=int(bk["margin_px"]), use_clear=False)
    for x in objs:
        x.hide_render = False
    ao = S.image_array(ao_img)[..., 0].astype(np.float64)
    lib = Path(P["cc0"]["lib"])
    mid, hid = P["cc0"]["marble"], P["cc0"]["hedge"]
    cc0 = {"marble": load_rgb(lib / mid / f"{mid}_2K-JPG_Color.jpg"),
           "marble_h": load_rgb(lib / mid / f"{mid}_2K-JPG_Displacement.jpg"),
           "moss": load_rgb(lib / hid / f"{hid}_2K-JPG_Color.jpg"),
           "moss_h": load_rgb(lib / hid / f"{hid}_2K-JPG_Displacement.jpg")}
    sh = shade(P, gb, cc0)
    ew = emissive_window_check(P, sh)
    # height -> tangent normal map: Cycles NORMAL bake through a Bump node (MikkTSpace), then green flip (DirectX)
    h_img = new_image("height", size, True)
    hp = np.zeros((size, size, 4), dtype=np.float32)
    hp[..., 0] = hp[..., 1] = hp[..., 2] = sh["height"]
    hp[..., 3] = 1.0
    h_img.pixels.foreach_set(hp.ravel())
    n_img = new_image("normal", size, True, (0.5, 0.5, 1.0, 1.0))
    for m in mats:
        nt = m.node_tree
        for n in list(nt.nodes):
            nt.nodes.remove(n)
        out = nt.nodes.new("ShaderNodeOutputMaterial")
        bs = nt.nodes.new("ShaderNodeBsdfDiffuse")
        nt.links.new(bs.outputs[0], out.inputs["Surface"])
        uvn = nt.nodes.new("ShaderNodeUVMap")
        uvn.uv_map = "UVMap"
        ht = nt.nodes.new("ShaderNodeTexImage")
        ht.image = h_img
        ht.interpolation = "Cubic"
        nt.links.new(uvn.outputs["UV"], ht.inputs["Vector"])
        bump = nt.nodes.new("ShaderNodeBump")
        bump.inputs["Strength"].default_value = 1.0
        bump.inputs["Distance"].default_value = 0.01
        nt.links.new(ht.outputs["Color"], bump.inputs["Height"])
        nt.links.new(bump.outputs["Normal"], bs.inputs["Normal"])
        tgt = nt.nodes.new("ShaderNodeTexImage")
        tgt.image = n_img
        nt.nodes.active = tgt
    sc.cycles.samples = 1
    for x in bpy.context.scene.objects:
        x.select_set(x in objs)
    bpy.context.view_layer.objects.active = objs[0]
    bpy.ops.object.bake(type="NORMAL", normal_space="TANGENT", margin=int(bk["margin_px"]), use_clear=True)
    nrm_t = S.image_array(n_img)[..., :3].astype(np.float64)
    nrm_dx = nrm_t.copy()
    nrm_dx[..., 1] = 1.0 - nrm_dx[..., 1]
    cov = sh["covered"]
    nxy = np.abs(nrm_t[..., :2] - 0.5).sum(-1)
    # outputs
    pre = P["texture_prefix"]
    exp = run / "export"
    orm = np.stack([np.clip(ao, 0, 1), sh["rough"], np.zeros_like(ao)], -1)
    paths = {"BC": exp / f"{pre}_BC.png", "N": exp / f"{pre}_N.png", "ORM": exp / f"{pre}_ORM.png", "E": exp / f"{pre}_E.png"}
    S.save_png(sh["bc"], size, paths["BC"], "sRGB")
    S.save_png(nrm_dx, size, paths["N"], "Non-Color")
    S.save_png(orm, size, paths["ORM"], "Non-Color")
    es = int(P["emissive_size"])
    e = S.box_down(np.repeat(sh["emis"][..., None], 3, -1), size // es)
    S.save_png(e, es, paths["E"], "Non-Color")
    tex_rep = {k: {"path": K.rel(v), "sha256": S.sha256(v), "bytes": v.stat().st_size} for k, v in paths.items()}
    # per-slot texel statistics and atlas usage
    area_uu = {}
    for o in objs:
        me = o.data
        area_uu[o.name] = r(sum(p.area for p in me.polygons) * 1e4, 1)
    tot_area = sum(area_uu.values())
    covered_frac = float(cov.mean())
    texel = {"atlasCoveredFraction": r(covered_frac, 4),
             "texelsPerUU": r(math.sqrt(covered_frac * size * size / tot_area), 3), "surfaceAreaUU2": area_uu,
             "slotTexelFractions": {n: r(float(((sh["slot"] == i) & cov).mean()), 4) for i, n in enumerate(SLOTS)},
             "normalDeviationMeanMarble": r(float(nxy[(sh["slot"] == M_MARBLE) & cov].mean()), 4),
             "normalDeviationMeanHedge": r(float(nxy[(sh["slot"] == M_HEDGE) & cov].mean()), 4) if
             ((sh["slot"] == M_HEDGE) & cov).any() else None,
             "aoMean": r(float(ao[cov].mean()), 4), "aoMinP5": r(float(np.percentile(ao[cov], 5)), 4)}
    # final: one slot, export each module
    exports = []
    final_mat = bpy.data.materials.new(P["material"])
    module_V = {}
    for key, o in zip(P["modules"], objs):
        me = o.data
        tag_slots = [p.material_index for p in me.polygons]
        slot_tris = {}
        for p in me.polygons:
            n = SLOTS[p.material_index]
            slot_tris[n] = slot_tris.get(n, 0) + len(p.vertices) - 2
        me.materials.clear()
        me.materials.append(final_mat)
        for p in me.polygons:
            p.material_index = 0
        Vb = np.array([v.co[:] for v in me.vertices]) * 100.0
        V = np.c_[-Vb[:, 1], -Vb[:, 0], Vb[:, 2]]
        module_V[key] = V
        b = K.bounds(V)
        uvs = np.zeros(len(me.uv_layers[0].data) * 2)
        me.uv_layers[0].data.foreach_get("uv", uvs)
        uvs = uvs.reshape(-1, 2)
        tris = S.triangles(o)
        exports.append({"key": key, "obj": o, "bounds": b, "tris": tris, "slotTris": slot_tris,
                        "uv": [r(uvs.min(), 4), r(uvs.max(), 4)], "nGlowFaces": sum(1 for t in tag_slots if t == M_GLOW)})
    blend = K.save_scratch_blend(P, "SM_Env_BackWall_all")
    rows = []
    for ex in exports:
        key, o = ex["key"], ex["obj"]
        M = P["modules"][key]
        for x in bpy.context.scene.objects:
            x.select_set(False)
        fbx = run / "export" / ("%s.fbx" % o.name)
        exp_r = K.export(o, fbx)
        V = module_V[key]
        piv_ok = abs(V[:, 2].min()) < 1e-4 and abs(V[:, 1].min() + float(M["width"]) / 2) < 1e-3 and abs(
            V[:, 1].max() - float(M["width"]) / 2) < 1e-3
        exp_r["um_fbx_v1_conformance"].append({"setting": "Pivot: wall front face (x 0) at the module centre, base z 0; "
                                                          "width = the module width", "standard": True, "used": piv_ok,
                                               "conforms": piv_ok})
        rows.append((ex, fbx, exp_r))
    out_exports = []
    for ex, fbx, exp_r in rows:
        key = ex["key"]
        M = P["modules"][key]
        rt = K.roundtrip(fbx, ex["tris"], [P["material"]], ex["bounds"])
        c = {"triangles_within_budget": ex["tris"] <= int(P["max_triangles_per_module"]),
             "width_equals_module": abs(ex["bounds"]["size"][1] - float(M["width"])) < 1e-3,
             "height_equals_module": abs(ex["bounds"]["max"][2] - float(M["height"])) < 1e-3 and abs(ex["bounds"]["min"][2]) < 1e-3,
             "back_at_minus_thickness": abs(ex["bounds"]["min"][0] + float(P["wall"]["thickness"])) < 1e-3,
             "has_glow_faces": ex["nGlowFaces"] > 0,
             "uv0_in_unit_square": ex["uv"][0] >= -1e-6 and ex["uv"][1] <= 1 + 1e-6,
             "single_mesh": rt["mesh_objects"] == 1, "triangles_preserved": rt["triangles"] == ex["tris"],
             "one_material_slot": rt["material_slots"] == [P["material"]], "uv0_present": bool(rt["uv_layers"]),
             "roundtrip_bounds_match_ue_frame": rt["ue_frame_matches_build"],
             "um_fbx_v1_conforms": all(x["conforms"] for x in exp_r["um_fbx_v1_conformance"])}
        out_exports.append({**exp_r, "name": ASSET_NAMES[key], "module": key, "triangles": ex["tris"],
                            "trianglesBySlot": ex["slotTris"], "boundsUeLocalUU": ex["bounds"], "uvRange": ex["uv"],
                            "glowFaces": ex["nGlowFaces"], "roundtrip": rt, "checks": {k: bool(v) for k, v in c.items()}})
    lay = layout(P, module_V)
    checks = {e2["name"]: all(e2["checks"].values()) for e2 in out_exports}
    checks["emissive_window_isolates_glow"] = ew["glowInsideFraction"] >= 0.99 and ew["otherInsideFraction"] <= 0.001
    checks["normal_map_has_relief"] = texel["normalDeviationMeanMarble"] > 0.004
    checks.update({k: v for k, v in lay["checks"].items()})
    report = {
        "schema": SCHEMA, "status": "measured", "asset": "ASSET-ENV-M-BACKWALL-001",
        "claims": {"art_accepted": False, "game_ready": False, "technically_imported": False},
        "blender_version": bpy.app.version_string, "script_sha256_lf": S.text_sha256_lf(HERE),
        "helpers": {"k_blender": S.text_sha256_lf(K.HERE), "static_prop_candidate": S.text_sha256_lf(K.SPC_PATH)},
        "params": {"path": K.rel(P["_params_path"]), "sha256": S.sha256(P["_params_path"])},
        "textures": tex_rep, "texel": texel, "emissiveWindow": ew,
        "cc0": {"marble": P["cc0"]["marble"], "hedge": P["cc0"]["hedge"], "license": "CC0 1.0 (ambientCG), local library"},
        "layout": {"file": "reports/backwall-layout.json", **{k: v for k, v in lay.items() if k != "entries"}},
        "contract": {"ue": {"folder": "/Game/EnvKit/Marmoreal (flat, env-kit contract)",
                            "meshes": list(ASSET_NAMES.values()),
                            "material": "MI_Env_BackWall: child of /Game/EnvKit/Shared/M_EnvProp, BaseColor/Normal/ORM = "
                                        "T_Env_BackWall_{BC,N,ORM}, EmissiveWindow = (hue %.0f, half %.0f, S %.2f, V %.2f), "
                                        "EmissiveColor warm, EmissiveIntensity ~ the lantern glass (P4: x6); T_Env_BackWall_E "
                                        "is the same mask as a texture for a future dedicated master" % (
                                            P["look"]["emissive_window"]["hue_deg"], P["look"]["emissive_window"]["hue_half_deg"],
                                            P["look"]["emissive_window"]["sat_min"], P["look"]["emissive_window"]["val_min"]),
                            "import": "extend tools/art/env_kit/ue_import_env_kit.py (legacy FbxFactory, uniform scale 1.0, "
                                      "normals imported, no collision, Nanite off; BC sRGB, N TC_Normalmap DirectX, "
                                      "ORM / E TC_Masks)"}},
        "exports": out_exports, "blend_scratch": blend,
    }
    report["checks"] = {k: bool(v) for k, v in checks.items()}
    report["checks_passed"] = all(report["checks"].values())
    K.write_json(run / "reports" / "build-report.json", report)
    K.write_json(run / "reports" / "backwall-layout.json", {"schema": "unmatched.env-m-backwall.layout/1",
                                                            "status": "proposed", "map": "marmoreal",
                                                            "props": lay["entries"], "note": P["placement"]["note"]})
    print("BACKWALL-BUILD", json.dumps(report["checks"]))
    print("BACKWALL-SUMMARY tris=%s texel=%.2f px/uu ew=%s" % ([e2["triangles"] for e2 in out_exports],
                                                               texel["texelsPerUU"], json.dumps(ew)))
    if not report["checks_passed"]:
        raise SystemExit(1)


def layout(P, module_V):
    """Layout entries (env-layout props) + clearance checks in board space."""
    pl = P["placement"]
    src = P["layout_source"]
    yaw = float(pl["yaw"])
    c, s = math.cos(math.radians(yaw)), math.sin(math.radians(yaw))
    R = np.array([[c, -s, 0], [s, c, 0], [0, 0, 1]])
    entries, pts = [], {}
    arc_back = float(src["arcade_y"]) - float(src["arcade_native_depth_uu"]) * float(src["arcade_scale"]) / 2
    portal_back = float(src["portal_y"]) - float(src["portal_native_depth_uu"]) * float(src["arcade_scale"]) / 2
    portal_top = float(src["portal_native_height_uu"]) * float(src["arcade_scale"]) - 3.0
    gap = float(pl["gap_uu"])
    bay_front = max(float(module_V[k][:, 0].max()) for k in module_V if k != "Centre")
    cv = module_V["Centre"]
    cen_front = float(cv[cv[:, 2] + float(pl["z"]) < portal_top + gap, 0].max())
    y_front = min(arc_back - gap - bay_front, portal_back - gap - cen_front)
    for row in pl["rows"]:
        loc = [float(row["x"]), round(y_front, 3), float(pl["z"])]
        entries.append({"id": row["id"], "mesh": "/Game/EnvKit/Marmoreal/%s" % ASSET_NAMES[row["module"]],
                        "loc": loc, "yawDeg": yaw, "scale": 1.0, "castShadow": True})
        pts[row["id"]] = module_V[row["module"]] @ R.T + np.array(loc)
    bays = [k for k in pts if k != "backwall-c"]
    hedge_front = max(float(pts[k][:, 1].max()) for k in bays)
    cen = pts["backwall-c"]
    portal_hits = int(((cen[:, 1] > portal_back) & (cen[:, 2] < portal_top) & (np.abs(cen[:, 0]) < 93.0)).sum())
    allp = np.vstack(list(pts.values()))
    west_end = float(allp[:, 0].min())
    cypress_east = -427.7 + 35.088 / 2 * 1.3
    # key light (-55, 30, 0): travel direction in UE = (cos p cos y, cos p sin y, sin p)
    p, yw = math.radians(-55.0), math.radians(30.0)
    tr = np.array([math.cos(p) * math.cos(yw), math.cos(p) * math.sin(yw), math.sin(p)])
    top = allp[:, 2].max()
    tip = allp[allp[:, 2] > top - 1.0]
    sh_y = float((tip[:, 1] + tr[1] / -tr[2] * (tip[:, 2] + 3.0)).max())
    frame_far = -(866 * 0.6666667 / 2 + 24.0)
    rows_x = sorted(float(r_["x"]) for r_ in pl["rows"])
    out = {"entries": entries, "yFrontFace": r(y_front, 3), "gapUU": gap,
           "arcadeBackY": r(arc_back, 3), "portalBackY": r(portal_back, 3), "portalTopZ": r(portal_top, 3),
           "bayHedgeFrontY": r(hedge_front, 3), "rowXExtent": [r(west_end, 3), r(float(allp[:, 0].max()), 3)],
           "cypressNwEastEdgeX": r(cypress_east, 3), "keyShadowTipY": r(sh_y, 3), "mapFrameFarEdgeY": r(frame_far, 3),
           "bayPitchUU": [r(b - a, 3) for a, b in zip(rows_x, rows_x[1:])]}
    out["checks"] = {
        "layout_hedge_behind_arcade": hedge_front <= arc_back - gap + 1e-6,
        "layout_centre_clear_of_portal": portal_hits == 0,
        "layout_clear_of_cypress": west_end > cypress_east + 2.0 and -float(allp[:, 0].max()) > cypress_east + 2.0,
        "layout_shadow_short_of_map_frame": sh_y < frame_far,
    }
    return out


main()
