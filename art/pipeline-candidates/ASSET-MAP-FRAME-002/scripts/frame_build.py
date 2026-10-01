"""ASSET-MAP-FRAME-002: build the heavy modular map frame (headless Blender, CPU, no render).

  blender -b --factory-startup -t 4 --python-exit-code 1 --python \
      art/pipeline-candidates/ASSET-MAP-FRAME-002/scripts/frame_build.py -- \
      art/pipeline-candidates/ASSET-MAP-FRAME-002/20261001-frame-v1/reports/frame-params.json

Four static meshes (UM_FBX_v1, uniform scale 1.0, two material slots: 0 wood, 1 iron):
  SM_MapFrame002_SegA / _SegB   a straight 157 uu bar of the frame profile (frame_layout.py), two weathering variants
                                (seeded jitter of the bevel points, faded to 0 at the ends so every joint matches);
  SM_MapFrame002_SegMid         SegA's profile + an iron strap with rivets across the middle (the mid-edge bracket);
  SM_MapFrame002_Corner         the mitred corner (legs 53.167 uu from the inner map corner) + an iron L-bracket over
                                the rail and down the outer face (40 uu legs) with rivets.
Profile: 24 uu wide (the current frame width, so FrameHalfUU is unchanged), 22.4 uu tall (z -10 .. +12.4; the current
bars are 14 uu, z -10 .. +4): a raised bevelled outer rail (top 12.4), a cove, a stepped inner lip (4.8) and a chamfered
inner face (2.0) that stays at the map edge. Wood UV0: u = profile perimeter / wood_tile_uu, v = along the bar /
wood_tile_uu (+ variant offset): grain along V for T_old_wood (M_MapFrameWood, Wrap). Iron UV0: box projection /
iron_tile_uu. Faceted (UM_FBX_v1 smoothing FACE).
Checks: triangles <= max per module; outward closed parts; nothing over the map opening (module and assembled); wood
inside FrameHalfUU; profile height 1.6x the current bar; the placements fill both shipped maps exactly (stretch 1.0); the
assembled frame is watertight along every side (abutting modules, no gap / overlap > 1e-3 uu); map occlusion from the
game cameras <= the current frame's; 1 mesh, 2 slots, UV0, round-trip triangles and bounds equal; UM_FBX_v1 rows conform.
Outputs: export/SM_MapFrame002_*.fbx, reports/build-report.json, reports/frame-layout.json (the placements for UE).
"""

import json
import math
import sys
from pathlib import Path

import bpy
import numpy as np

HERE = Path(__file__).resolve()
REPO = HERE.parents[4]
sys.path.insert(0, str(HERE.parent))
sys.path.insert(0, str(REPO / "tools" / "art" / "env_kit"))
import frame_layout as FL  # noqa: E402
import k_blender as K  # noqa: E402

S, r = K.S, K.r
SCHEMA = "unmatched.map-frame-002.build-report/1"


def smoothstep(e0, e1, x):
    t = min(max((x - e0) / (e1 - e0), 0.0), 1.0)
    return t * t * (3 - 2 * t)


def perimeter_coords(prof):
    s = [0.0]
    for i in range(1, len(prof)):
        s.append(s[-1] + math.dist(prof[i - 1], prof[i]))
    return s, s[-1] + math.dist(prof[-1], prof[0])


def sweep(mb, prof, n_st, pos, mat, uv_side, uv_cap, jitter=None, part=""):
    """Closed prism: profile polygon prof (list of (w, z)) at n_st stations; pos(k, t, w, z) -> 3D point at station k
    (t = k / (n_st - 1)); jitter(k, i) -> (dw, dz). Faces are fixed to outward winding by the part's signed volume."""
    n = len(prof)
    s, s_tot = perimeter_coords(prof)
    rings = []
    for k in range(n_st):
        t = k / (n_st - 1)
        ring = []
        for i, (w, z) in enumerate(prof):
            dw, dz = jitter(k, i) if jitter else (0.0, 0.0)
            ring.append(pos(k, t, w + dw, z + dz))
        rings.append(mb.add_verts(ring))
    faces = []
    for k in range(n_st - 1):
        for i in range(n):
            j = (i + 1) % n
            sj = s_tot if j == 0 else s[j]
            idx = [rings[k] + i, rings[k] + j, rings[k + 1] + j, rings[k + 1] + i]
            uvs = [uv_side(k, s[i]), uv_side(k, sj), uv_side(k + 1, sj), uv_side(k + 1, s[i])]
            faces.append((idx, uvs))
    for k, rev in ((0, False), (n_st - 1, True)):
        idx = [rings[k] + i for i in range(n)]
        uvs = [uv_cap(w, z) for (w, z) in prof]
        if rev:
            idx, uvs = idx[::-1], uvs[::-1]
        faces.append((idx, uvs))
    V = np.array(mb.V)
    vol = K.signed_volume(V, [f for f, _ in faces])
    for idx, uvs in faces:
        if vol < 0:
            idx, uvs = idx[::-1], uvs[::-1]
        mb.add_face(idx, uvs, mat=mat, tag=part)
    return abs(vol)


def dome(mb, c, nrm, radius, height, seg, mat, tile, part="rivet"):
    c = np.asarray(c, dtype=np.float64)
    nrm = np.asarray(nrm, dtype=np.float64)
    nrm = nrm / np.linalg.norm(nrm)
    a = np.array([1.0, 0.0, 0.0]) if abs(nrm[0]) < 0.9 else np.array([0.0, 1.0, 0.0])
    t1 = np.cross(nrm, a)
    t1 /= np.linalg.norm(t1)
    t2 = np.cross(nrm, t1)
    pts = []
    for rr, hh in ((radius, -0.15), (radius * 0.72, height * 0.62)):
        for i in range(seg):
            ang = 2 * math.pi * i / seg
            pts.append(c + nrm * hh + rr * (math.cos(ang) * t1 + math.sin(ang) * t2))
    pts.append(c + nrm * height)
    base = mb.add_verts(pts)

    def uv(p):
        return (float(np.dot(p, t1)) / tile, float(np.dot(p, t2)) / tile)
    faces = [[base + i for i in range(seg)][::-1]]
    for i in range(seg):
        j = (i + 1) % seg
        faces.append([base + i, base + j, base + seg + j, base + seg + i])
        faces.append([base + seg + i, base + seg + j, base + 2 * seg])
    V = np.array(mb.V)
    vol = K.signed_volume(V, faces)
    for f in faces:
        f2 = f if vol > 0 else f[::-1]
        mb.add_face(f2, [uv(V[i]) for i in f2], mat=mat, tag=part)


def stations(length, step):
    return max(2, int(math.ceil(length / step)) + 1)


def build_segment(P, name, variant, with_strap):
    prof = [tuple(p) for p in P["profile"]["points"]]
    seg = float(P["modules"]["segment_uu"])
    pr = P["profile"]
    wt, it = float(P["uv"]["wood_tile_uu"]), float(P["uv"]["iron_tile_uu"])
    vo = float(P["variants"][variant]["v_offset"])
    rng = np.random.default_rng([20261001, int(P["variants"][variant]["seed"])])
    n_st = stations(seg, float(pr["station_step_uu"]))
    jit = rng.uniform(-1.0, 1.0, size=(n_st, len(prof), 2)) * float(pr["jitter_uu"])
    jset = set(pr["jitter"])
    xs = np.linspace(0.0, seg, n_st)

    def jitter(k, i):
        if i not in jset:
            return (0.0, 0.0)
        f = smoothstep(0.0, float(pr["jitter_fade_uu"]), min(xs[k], seg - xs[k]))
        return (jit[k, i, 0] * f, jit[k, i, 1] * f)
    mb = K.MeshBuilder(name, n_uv=1)
    sweep(mb, prof, n_st, lambda k, t, w, z: (xs[k], w, z), 0,
          lambda k, s: (s / wt, xs[k] / wt + vo), lambda w, z: (w / wt, z / wt), jitter, "wood")
    if with_strap:
        ir = P["iron"]
        poly = FL.thicken_polyline(ir["mid_polyline"], prof, float(ir["thickness_uu"]))
        half = float(ir["mid_strap_width_uu"]) / 2
        x0, x1 = seg / 2 - half, seg / 2 + half
        sweep(mb, poly, 2, lambda k, t, w, z: (x0 + t * (x1 - x0), w, z), 1,
              lambda k, s: (s / it, (x0 if k == 0 else x1) / it), lambda w, z: (w / it, z / it), None, "strap")
        top = 12.4 + float(ir["thickness_uu"])
        th = float(ir["thickness_uu"])
        q = half * 0.55
        for c, n in (((seg / 2 - q, 16.5, top), (0, 0, 1)), ((seg / 2 + q, 16.5, top), (0, 0, 1)),
                     ((seg / 2, 5.4, 4.8 + th), (0, 0, 1)),
                     ((seg / 2 - q, 24.0 + th, 3.0), (0, 1, 0)), ((seg / 2 + q, 24.0 + th, 3.0), (0, 1, 0))):
            dome(mb, c, n, float(ir["rivet_radius_uu"]), float(ir["rivet_height_uu"]), int(ir["rivet_segments"]), 1, it)
    return mb


def build_corner(P, name):
    prof = [tuple(p) for p in P["profile"]["points"]]
    lc = float(P["modules"]["corner_leg_uu"])
    pr = P["profile"]
    wt, it = float(P["uv"]["wood_tile_uu"]), float(P["uv"]["iron_tile_uu"])
    vo = float(P["variants"]["Corner"]["v_offset"])
    rng = np.random.default_rng([20261001, int(P["variants"]["Corner"]["seed"])])
    n_st = stations(lc + 12.0, float(pr["station_step_uu"]))
    jset = set(pr["jitter"])
    mb = K.MeshBuilder(name, n_uv=1)
    for leg in ("A", "B"):
        jit = rng.uniform(-1.0, 1.0, size=(n_st, len(prof), 2)) * float(pr["jitter_uu"])

        def jitter(k, i, jit=jit):
            if i not in jset:
                return (0.0, 0.0)
            t = k / (n_st - 1)
            f = smoothstep(0.0, float(pr["jitter_fade_uu"]), min(t, 1 - t) * (lc + 12.0))
            return (jit[k, i, 0] * f, jit[k, i, 1] * f)
        if leg == "A":   # along x from -lc to the mitre x = w, outward +y
            pos = lambda k, t, w, z: (-lc + t * (w + lc), w, z)  # noqa: E731
            uvs = lambda k, s: (s / wt, (k / (n_st - 1)) * (lc + 12.0) / wt + vo)  # noqa: E731
        else:            # along y from the mitre y = w down to -lc, outward +x
            pos = lambda k, t, w, z: (w, w + t * (-lc - w), z)  # noqa: E731
            uvs = lambda k, s: (s / wt, (k / (n_st - 1)) * (lc + 12.0) / wt + vo + 0.37)  # noqa: E731
        sweep(mb, prof, n_st, pos, 0, uvs, lambda w, z: (w / wt, z / wt), jitter, "wood")
    ir = P["iron"]
    th = float(ir["thickness_uu"])
    poly = FL.thicken_polyline(ir["corner_polyline"], prof, th)
    a = 24.0 - float(ir["corner_strap_uu"])
    sweep(mb, poly, 2, lambda k, t, w, z: (a + t * (w - a), w, z), 1,
          lambda k, s: (s / it, k * 0.5), lambda w, z: (w / it, z / it), None, "strap")
    sweep(mb, poly, 2, lambda k, t, w, z: (w, w + t * (a - w), z), 1,
          lambda k, s: (s / it, k * 0.5 + 0.25), lambda w, z: (w / it, z / it), None, "strap")
    top = 12.4 + th
    rv = (float(ir["rivet_radius_uu"]), float(ir["rivet_height_uu"]), int(ir["rivet_segments"]))
    for c, n in (((16.5, 16.5, top), (0, 0, 1)),
                 ((-22.0, 16.5, top), (0, 0, 1)), ((-8.0, 16.5, top), (0, 0, 1)), ((4.0, 16.5, top), (0, 0, 1)),
                 ((16.5, -22.0, top), (0, 0, 1)), ((16.5, -8.0, top), (0, 0, 1)), ((16.5, 4.0, top), (0, 0, 1)),
                 ((-20.0, 24.0 + th, 3.0), (0, 1, 0)), ((-4.0, 24.0 + th, 3.0), (0, 1, 0)), ((10.0, 24.0 + th, 3.0), (0, 1, 0)),
                 ((24.0 + th, -20.0, 3.0), (1, 0, 0)), ((24.0 + th, -4.0, 3.0), (1, 0, 0)), ((24.0 + th, 10.0, 3.0), (1, 0, 0))):
        dome(mb, c, n, rv[0], rv[1], rv[2], 1, it)
    return mb


def opening_violation(V, kind):
    """Max penetration (uu) into the map opening in the module's local frame (segment: y < 0; corner: x < 0 and
    y < 0 - the map quadrant of the inner corner)."""
    if kind == "corner":
        return float(max(0.0, (-np.maximum(V[:, 0], V[:, 1])).max()))
    return float(max(0.0, (-V[:, 1]).max()))


def assemble(P, meshes, lay):
    """All placements in board-actor space: union bounds, opening clearance, side coverage."""
    pts, wood = [], []
    for inst in lay["instances"]:
        mb = meshes[inst["module"]]
        V = mb.verts().copy()
        V[:, 0] *= inst["scaleX"]
        W = V @ FL.yaw_matrix(inst["yawDeg"]).T + np.array(inst["loc"])
        pts.append(W)
        wood.append(W[sorted({v for f, t in zip(mb.F, mb.TAG) if t == "wood" for v in f})])
    A = np.vstack(pts)
    Wd = np.vstack(wood)
    hx, hy = lay["mapHalfUU"]
    inside = (np.abs(A[:, 0]) < hx - 1e-3) & (np.abs(A[:, 1]) < hy - 1e-3)
    # coverage: along each side, the union of module intervals on the inner edge must be [-h, h] with no gap
    cover = {}
    seg = float(P["modules"]["segment_uu"])
    lc = float(P["modules"]["corner_leg_uu"])
    for side, h in (("near", hx), ("far", hx), ("east", hy), ("west", hy)):
        iv = [(-h, -h + lc), (h - lc, h)]
        for inst in lay["instances"]:
            if inst["id"].startswith(side + "-"):
                c = inst["loc"][0] if side in ("near", "far") else inst["loc"][1]
                L = seg * inst["scaleX"]
                d = {"near": 1, "far": -1, "east": -1, "west": 1}[side]
                iv.append(tuple(sorted((c, c + d * L))))
        iv.sort()
        gaps = [round(iv[i + 1][0] - iv[i][1], 6) for i in range(len(iv) - 1)]
        cover[side] = {"intervals": len(iv), "maxGapUU": max(gaps), "minGapUU": min(gaps),
                       "span": [round(iv[0][0], 4), round(iv[-1][1], 4)]}
    return A, {"boundsUU": {"min": [r(v, 3) for v in A.min(0)], "max": [r(v, 3) for v in A.max(0)]},
               "woodBoundsUU": {"min": [r(v, 4) for v in Wd.min(0)], "max": [r(v, 4) for v in Wd.max(0)]},
               "verticesInsideMapOpening": int(inside.sum()), "sideCoverage": cover}


def occlusion(P, A, lay):
    """Map strip hidden behind the frame from the game cameras: for every frame vertex, the camera ray through it hits
    the map plane (z -0.5); the deepest hit inside the opening (uu from the map edge) is the occlusion. The same for the
    current frame (cube bars 24 x 14, z -10 .. +4)."""
    pv = P["preview"]
    hx, hy = lay["mapHalfUU"]
    p = math.radians(-float(pv["pitch_deg"]))
    cams = {"K1": ((0.0, 0.0, 0.0), pv["k1_distance_uu"]), "zoomout065": ((0.0, 0.0, 0.0), pv["zoom_out_distance_uu"]),
            "follow16-nearE": ((300.0, 250.0, 28.0), pv["follow_distance_uu"]),
            "follow16-farW": ((-300.0, -200.0, 28.0), pv["follow_distance_uu"])}
    F = float(P["map"]["frame_uu"])
    old = []
    for xs in (-hx - F, -hx, hx, hx + F):
        for ys in (-hy - F, -hy, hy, hy + F):
            if (abs(xs) >= hx - 1e-6 or abs(ys) >= hy - 1e-6) and not (abs(xs) < hx and abs(ys) < hy):
                old.append((xs, ys, 4.0))
    # the current bars' top inner edges (dense along the edges)
    for t in np.linspace(-1, 1, 81):
        old += [(t * hx, hy, 4.0), (t * hx, -hy, 4.0), (hx, t * hy, 4.0), (-hx, t * hy, 4.0)]
    old = np.array(old)
    out = {}
    for name, (f, d) in cams.items():
        c = np.array([f[0], f[1] + d * math.cos(p), f[2] + d * math.sin(p)])

        def depth(pts):
            q = pts[pts[:, 2] > -0.5]
            t = (c[2] + 0.5) / (c[2] - q[:, 2])
            hit = c[None, :] + (q - c[None, :]) * t[:, None]
            ins = (np.abs(hit[:, 0]) < hx) & (np.abs(hit[:, 1]) < hy)
            if not ins.any():
                return 0.0
            h = hit[ins]
            return float(np.minimum(hx - np.abs(h[:, 0]), hy - np.abs(h[:, 1])).max())
        out[name] = {"newFrameUU": r(depth(A), 3), "currentFrameUU": r(depth(old), 3)}
    return out


def main():
    P = K.load_params(K.script_args()[0])
    run = P["_run"]
    lay = FL.placements(P)
    mods = {"A": build_segment(P, "SM_MapFrame002_SegA", "A", False),
            "B": build_segment(P, "SM_MapFrame002_SegB", "B", False),
            "Mid": build_segment(P, "SM_MapFrame002_SegMid", "Mid", True),
            "Corner": build_corner(P, "SM_MapFrame002_Corner")}
    A, asm = assemble(P, mods, lay)
    occ = occlusion(P, A, lay)
    pb = FL.all_points_bounds(P)
    cur = P["current_frame"]
    height_ratio = (pb["woodZ"][1] - pb["woodZ"][0]) / float(cur["bar_section_uu"][1])
    exports, checks_mod = [], {}
    for key, mb in mods.items():
        bpy.ops.wm.read_factory_settings(use_empty=True)
        mats = [K.flat_material(P["materials"]["wood"], (0.06, 0.035, 0.02), 0.75),
                K.flat_material(P["materials"]["iron"], (0.032, 0.038, 0.045), 0.8, 0.6)]
        V = mb.verts()
        b_ue = K.bounds(V)
        kind = "corner" if key == "Corner" else "segment"
        obj = mb.to_object(mats)
        tris = S.triangles(obj)
        blend = K.save_scratch_blend(P, mb.name)
        fbx = run / "export" / ("%s.fbx" % mb.name)
        exp = K.export(obj, fbx)
        pivot_ok = (abs(V[:, 2].min() + 10.0) < 1e-6 and (kind == "corner" or abs(V[:, 0].min()) < 1e-6))
        exp["um_fbx_v1_conformance"].append({
            "setting": "Pivot: %s (frame_layout.py frames; z 0 = the play plane, wood bottom at -10)" % (
                "the inner map corner" if kind == "corner" else "start of the inner edge"),
            "standard": True, "used": pivot_ok, "conforms": pivot_ok})
        rt = K.roundtrip(fbx, tris, [P["materials"]["wood"], P["materials"]["iron"]], b_ue)
        wood_ids = [i for i, t in enumerate(mb.TAG) if t == "wood"]
        wv = V[sorted({v for i in wood_ids for v in mb.F[i]})]
        wood_out = float(wv[:, 1].max()) if kind == "segment" else float(np.maximum(wv[:, 0], wv[:, 1]).max())
        c = {"triangles_within_budget": tris <= int(P["max_triangles_per_module"]),
             "nothing_over_the_map_opening": opening_violation(V, kind) < 1e-6,
             "wood_inside_frame_half": wood_out <= float(P["map"]["frame_uu"]) + 1e-6,
             "single_mesh": rt["mesh_objects"] == 1, "triangles_preserved": rt["triangles"] == tris,
             "two_material_slots": rt["material_slots"] == [P["materials"]["wood"], P["materials"]["iron"]],
             "uv0_present": bool(rt["uv_layers"]), "roundtrip_bounds_match_ue_frame": rt["ue_frame_matches_build"],
             "um_fbx_v1_conforms": all(x["conforms"] for x in exp["um_fbx_v1_conformance"])}
        checks_mod[mb.name] = c
        parts = {}
        for t in set(mb.TAG):
            parts[t] = sum(len(f) - 2 for f, tt in zip(mb.F, mb.TAG) if tt == t)
        exports.append({**exp, "name": mb.name, "module": key, "triangles": tris, "trianglesByPart": parts,
                        "boundsUeLocalUU": b_ue, "woodOuterWUU": r(wood_out, 4),
                        "openingPenetrationUU": r(opening_violation(V, kind), 6), "uv": K.uv_stats(mb),
                        "roundtrip": rt, "blend_scratch": blend, "checks": c})
    checks = {
        "modules_pass": all(all(c.values()) for c in checks_mod.values()),
        "exact_fit_both_maps": lay["exactFit"],
        "assembled_nothing_inside_opening": asm["verticesInsideMapOpening"] == 0,
        "assembled_sides_watertight": all(abs(c["maxGapUU"]) < 1e-3 and abs(c["minGapUU"]) < 1e-3
                                          for c in asm["sideCoverage"].values()),
        "assembled_wood_bounds_equal_frame_half": all(
            abs(abs(asm["woodBoundsUU"][m][i]) - lay["frameHalfUU"][i]) < 1e-3 for m in ("min", "max") for i in (0, 1)),
        "profile_height_about_1p6x": abs(height_ratio - 1.6) < 0.01,
        "map_occlusion_not_worse_than_current": all(o["newFrameUU"] <= o["currentFrameUU"] + 1e-6 for o in occ.values()),
    }
    fh = lay["frameHalfUU"]
    iron_out = max(abs(asm["boundsUU"]["max"][0]) - fh[0], abs(asm["boundsUU"]["max"][1]) - fh[1])
    report = {
        "schema": SCHEMA, "status": "measured", "asset": "ASSET-MAP-FRAME-002 / SM_MapFrame002_*",
        "claims": {"art_accepted": False, "game_ready": False, "technically_imported": False},
        "blender_version": bpy.app.version_string,
        "script_sha256_lf": S.text_sha256_lf(HERE), "layout_sha256_lf": S.text_sha256_lf(HERE.parent / "frame_layout.py"),
        "helpers": {"k_blender": S.text_sha256_lf(K.HERE), "static_prop_candidate": S.text_sha256_lf(K.SPC_PATH)},
        "params": {"path": K.rel(P["_params_path"]), "sha256": S.sha256(P["_params_path"])},
        "profile": {"woodW": pb["woodW"], "woodZ": pb["woodZ"], "ironW": [r(v, 4) for v in pb["ironW"]],
                    "ironZ": [r(v, 4) for v in pb["ironZ"]], "areaUU2": r(abs(FL.profile_area(P["profile"]["points"])), 3),
                    "currentBarAreaUU2": cur["bar_section_uu"][0] * cur["bar_section_uu"][1],
                    "heightRatioToCurrent": r(height_ratio, 4),
                    "visibleHeightAboveGroundUU": {"new": r(pb["woodZ"][1] + 1.0, 3), "current": 5.0}},
        "layout": {"file": "reports/frame-layout.json", "exactFit": lay["exactFit"], "sides": lay["sides"],
                   "frameHalfUU": [r(v, 4) for v in fh], "mapHalfUU": [r(v, 4) for v in lay["mapHalfUU"]]},
        "assembled": {**asm, "ironBeyondFrameHalfUU": r(iron_out, 4),
                      "note": "the wood ends exactly at FrameHalfUU; only the iron straps / rivets on the outer face "
                              "stand %.2f uu proud of it (onto the ground strip, which overlaps the frame by 2 uu)" % iron_out},
        "mapOcclusionUU": occ,
        "contract": {
            "ue": {"folder": "/Game/EnvMaps/Frame", "meshes": [m.name for m in mods.values()],
                   "slots": {"0 M_MapFrame002_Wood": "MID of /Game/EnvMaps/M_MapFrameWood (the P4 frameWood profile values "
                                                     "keep working; UV0 tiles T_old_wood, Wrap)",
                             "1 M_MapFrame002_Iron": "MI of /Game/EnvKit/Shared/M_EnvProp (or M_UM_Figure) with "
                                                     "T_MapFrame002_Iron_{BC,N,ORM} (Wrap)"},
                   "import": "new tools/art/env_kit/ue_import_map_frame.py modelled on ue_import_tray_t2.py (legacy "
                             "FbxFactory, import_uniform_scale 1.0, normals imported, no collision, Nanite off)"},
            "placement": "reports/frame-layout.json: per instance module, loc (board-actor space, z 0), yawDeg, "
                         "scaleX (1.0 for both maps); replaces the 4 cube bars AND the ART-005 ArtCorners instances "
                         "on map-image boards (the corner module carries its own bracket)",
            "axes": "UE numbers authored directly (k_blender.py); read-back frame = UE with Y negated"},
        "exports": exports,
    }
    report["checks"] = {k: bool(v) for k, v in checks.items()}
    report["checks_passed"] = all(report["checks"].values())
    K.write_json(run / "reports" / "build-report.json", report)
    K.write_json(run / "reports" / "frame-layout.json", {
        "schema": "unmatched.map-frame-002.layout/1", "status": "proposed",
        "frame": "board-actor space (map centre at the origin), z relative to the play plane; yaw = UE yaw",
        "meshes": {"A": "SM_MapFrame002_SegA", "B": "SM_MapFrame002_SegB", "Mid": "SM_MapFrame002_SegMid",
                   "Corner": "SM_MapFrame002_Corner"},
        **lay})
    print("FRAME-BUILD", json.dumps(report["checks"]))
    for e in exports:
        print("FRAME-MODULE %s tris=%d bounds=%s checks=%s" % (e["name"], e["triangles"], e["boundsUeLocalUU"]["size"],
                                                              all(e["checks"].values())))
    print("FRAME-OCCLUSION", json.dumps(occ))
    if not report["checks_passed"]:
        raise SystemExit(1)


main()
