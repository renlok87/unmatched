"""Stage seams: do part junctions and contact openings show in the probe poses? (the parts are not welded — positional
weights keep limb junctions together, contact caps close the openings the Tripo segmentation cut along every contact).

Poses: the 7 poses of anim/rig_deform_probe.py (same bones, world axes, angles), plus rest.

1. junctions   (rig.seam_pairs) vertices of part A within rig.seam_radius_m of the surface of part B at rest; opening =
               posed distance to B minus the rest distance (mm, max / p95) — as before.
2. open loops  every rim loop (boundary loop of the real part faces, perimeter >= seams.loop_min_perimeter_cm) of the
               body and the bow: covering part at rest (smallest median distance among the other parts, the bow and the
               base), closed_by_cap (a cap of the close stage shares every rim vertex); per pose the share of the loop
               perimeter whose distance to the posed covering surface grew by more than seams.exposure_threshold_mm
               (verify 2026-09-29: "открытые петли, открывшиеся в позе"). Gate: an open (uncapped) loop may not open on
               more than seams.max_open_share of its perimeter in any pose.
3. see-through ray test (raycam, seams.raycast views/pitch): the posed figure (body + bow + static base) seen from
               17 orthographic views; a pixel whose first hit is a BACK face sees the inside of an open shell — with UE
               one-sided materials that pixel shows what lies behind: a see-through hole. A cap hit from behind is
               passed through (culled, the pixel shows what lies behind the cap). Counted per pose, per part,
               against rest; on the authored .blend and on the exported FBX read back (work/probe-fbx-authored.blend).
               Gate: no 8-connected blob of NEW back-face pixels (pose and not rest, same view and grid) larger
               than seams.max_new_blob_px, on both (a hole is a blob; rim-edge grazing rays leave single pixels, whose
               sum per pose is reported, not gated).
4. frames      Workbench, runtime 2K BaseColor, BACKFACE CULLING, transparent film (composed over magenta: magenta
               inside the silhouette = see-through), orthographic close-ups of each pose's contact (seams.frames) and
               K2 perspective frames (seams.k2_frames), rendered on the FBX read-back -> work/seams_raw/*.png
               (compose.py builds preview/probe-culled-*.jpg). Labelled "blender Workbench" — editor frames.
Reads work/sk_authored.blend, work/probe-fbx-authored.blend, work/rig/body_vertex_{part,cap}.npy,
reports/close-report.json; writes reports/seams-report.json."""

import json
import math
from pathlib import Path

import bmesh
import bpy
import numpy as np
from mathutils import Matrix, Vector
from mathutils.bvhtree import BVHTree
from mathutils.kdtree import KDTree

from . import bl_util as U
from . import raycam

TESTS = [("head_turn", "head", "Z", 35), ("spine_bend_fwd", "spine", "X", 25), ("arm_l_raise", "arm_upper.L", "Y", -45),
         ("arm_r_raise", "arm_upper.R", "Y", 45), ("forearm_l_bend", "arm_lower.L", "X", -40),
         ("thigh_l_flex", "leg_upper.L", "X", -35), ("thigh_r_flex", "leg_upper.R", "X", -35)]
DEFAULTS = {"exposure_threshold_mm": 1.5, "max_open_share": 0.05, "loop_min_perimeter_cm": 1.0,
            "max_new_blob_px": 8, "raycast": {"pitch_m": 0.0015}}


def reset_pose(arm):
    for pb in arm.pose.bones:
        pb.matrix_basis = Matrix.Identity(4)
    bpy.context.view_layer.update()


def rotate_bone(arm, bone, axis, deg):
    pb = arm.pose.bones[bone]
    head = pb.head.copy()
    ax = {"X": Vector((1, 0, 0)), "Y": Vector((0, 1, 0)), "Z": Vector((0, 0, 1))}[axis]
    ax = (arm.matrix_world.to_3x3().inverted() @ ax).normalized()
    pb.matrix = Matrix.Translation(head) @ Matrix.Rotation(math.radians(deg), 4, ax) @ Matrix.Translation(-head) @ pb.matrix
    bpy.context.view_layer.update()


def pose(arm, name):
    reset_pose(arm)
    if name != "rest":
        _n, bone, axis, deg = next(t for t in TESTS if t[0] == name)
        rotate_bone(arm, bone, axis, deg)


def evaluated(obj):
    dg = bpy.context.evaluated_depsgraph_get()
    ev = obj.evaluated_get(dg)
    me = ev.to_mesh()
    co = np.array([obj.matrix_world @ v.co for v in me.vertices])
    ev.to_mesh_clear()
    return co


def cap_names(run_dir, names):
    rep = run_dir / "reports" / "close-report.json"
    if not rep.exists():
        return {}
    data = json.loads(rep.read_text(encoding="utf-8"))
    return {(U.part_key(c["part"]), c["cap_index"]): c["name"] for c in data["caps"]}


def junction_metric(arm, body, vpart, ppart, polys, radius, pairs_cfg):
    reset_pose(arm)
    rest = evaluated(body)

    def bvh_for(co, part):
        idx = [i for i, pp in enumerate(ppart) if pp == part]
        return BVHTree.FromPolygons([Vector(c) for c in co], [polys[i] for i in idx])

    pairs = []
    for a_name, b_name in pairs_cfg:
        a, b = U.part_key(a_name), U.part_key(b_name)
        bvh_b = bvh_for(rest, b)
        near, d0 = [], []
        for vi in np.nonzero(vpart == a)[0]:
            hit = bvh_b.find_nearest(Vector(rest[vi]))
            if hit[0] is not None and hit[3] <= radius:
                near.append(int(vi))
                d0.append(hit[3])
        pairs.append((a_name, b_name, b, np.array(near, np.int64), np.array(d0)))
    out = {}
    for name, _bone, _axis, _deg in TESTS:
        pose(arm, name)
        posed = evaluated(body)
        res = {}
        for a_name, b_name, b, near, d0 in pairs:
            if len(near) == 0:
                continue
            bvh_b = bvh_for(posed, b)
            d = np.array([bvh_b.find_nearest(Vector(posed[vi]))[3] for vi in near])
            opening = (d - d0) * 1000.0
            res["%s|%s" % (a_name, b_name)] = {"vertices": int(len(near)), "max_mm": U.r(opening.max(), 3),
                                               "p95_mm": U.r(np.percentile(opening, 95), 3)}
        out[name] = res
    reset_pose(arm)
    worst = {}
    for pname, res in out.items():
        for pair, v in res.items():
            if pair not in worst or v["max_mm"] > worst[pair]["max_mm"]:
                worst[pair] = {"pose": pname, "max_mm": v["max_mm"], "p95_mm": v["p95_mm"]}
    return {"radius_m": radius, "pairs": [list(p[:2]) for p in pairs],
            "junction_vertices": {"%s|%s" % (p[0], p[1]): int(len(p[3])) for p in pairs}, "poses": out,
            "worst_by_pair": worst}


def loop_metric(arm, objs, labels, cfg, names_by_label, cap_name_of):
    """objs: {"body": obj, "bow": obj, "base": obj}; labels: {"body": (vpart, vcap, fcap), "bow": part, "base": part}."""
    body, bow, base = objs["body"], objs["bow"], objs["base"]
    vpart, vcap, fcap = labels["body"]
    bm = bmesh.new()
    bm.from_mesh(body.data)
    from candidate_build.closure import ordered_boundary_loops

    def real_edge(e):
        return all(fcap[f.index] == 0 for f in e.link_faces)

    raw_loops = [[v.index for v in lp["verts"]] for lp in ordered_boundary_loops(bm, select=real_edge)]
    bm.free()
    reset_pose(arm)
    rest = evaluated(body)
    rest_bow = evaluated(bow)
    base_co = U.coords(base.data)
    body_polys = [list(p.vertices) for p in body.data.polygons]
    ppart = np.array([vpart[p[0]] for p in body_polys])
    real = np.array([fcap[i] == 0 for i in range(len(body_polys))])
    bow_polys = [list(p.vertices) for p in bow.data.polygons]
    base_polys = [list(p.vertices) for p in base.data.polygons]
    part_ids = sorted(set(ppart.tolist()))

    def surfaces(co, co_bow):
        s = {}
        for p in part_ids:
            idx = np.nonzero((ppart == p) & real)[0]
            s[p] = BVHTree.FromPolygons([Vector(c) for c in co], [body_polys[i] for i in idx])
        s[labels["bow"]] = BVHTree.FromPolygons([Vector(c) for c in co_bow], bow_polys)
        s[labels["base"]] = BVHTree.FromPolygons([Vector(c) for c in base_co], base_polys)
        return s

    cap_kd = {}
    for p in part_ids:
        ids = np.nonzero((vpart == p) & (vcap > 0))[0]
        kd = KDTree(max(len(ids), 1))
        for i in ids:
            kd.insert(Vector(rest[i]), int(i))
        kd.balance()
        cap_kd[p] = (kd, len(ids))
    s0 = surfaces(rest, rest_bow)
    thr = float(cfg["exposure_threshold_mm"]) / 1000.0
    rows = []
    for lp in raw_loops:
        vi = np.array(lp)
        parts = sorted(set(int(vpart[i]) for i in vi))
        pts = rest[vi]
        seg = np.linalg.norm(np.roll(pts, -1, 0) - pts, axis=1)
        if seg.sum() < float(cfg["loop_min_perimeter_cm"]) / 100.0 or len(parts) != 1:
            continue
        part = parts[0]
        kd, n_cap = cap_kd[part]
        cap_hits = [kd.find(Vector(p)) for p in pts] if n_cap else []
        closed = None
        if n_cap and all(h[2] is not None and h[2] <= 1e-6 for h in cap_hits):
            cid = int(vcap[cap_hits[0][1]])
            closed = cap_name_of.get((part, cid), "cap %d" % cid)
        best = None
        for q, bvh in s0.items():
            if q == part:
                continue
            d = np.array([bvh.find_nearest(Vector(p))[3] for p in pts])
            if best is None or np.median(d) < np.median(best[1]):
                best = (q, d)
        wv = (seg + np.roll(seg, 1)) / 2
        rows.append({"part": names_by_label[part], "covered_by": names_by_label[best[0]], "cover_label": best[0],
                     "perimeter_cm": U.r(seg.sum() * 100, 2), "centre_cm": U.rv(pts.mean(0) * 100, 2),
                     "median_to_cover_mm": U.r(np.median(best[1]) * 1000, 3), "closed_by_cap": closed,
                     "_vi": vi, "_d0": best[1], "_w": wv / wv.sum(), "poses": {}})
    for name, _b, _a, _d in TESTS:
        pose(arm, name)
        co, co_bow = evaluated(body), evaluated(bow)
        s = surfaces(co, co_bow)
        for r in rows:
            d = np.array([s[r["cover_label"]].find_nearest(Vector(p))[3] for p in co[r["_vi"]]])
            op = d - r["_d0"]
            r["poses"][name] = {"open_share": U.r((r["_w"] * (op > thr)).sum(), 4), "max_mm": U.r(op.max() * 1000, 2)}
    reset_pose(arm)
    for r in rows:
        worst = max(r["poses"].items(), key=lambda kv: (kv[1]["open_share"], kv[1]["max_mm"]))
        r["worst"] = {"pose": worst[0], **worst[1]}
        for k in ("_vi", "_d0", "_w", "cover_label"):
            r.pop(k)
    rows.sort(key=lambda r: (r["part"], -r["perimeter_cm"]))
    return rows


def ray_scene(objs, labels, co_body, co_bow):
    body, bow, base = objs["body"], objs["bow"], objs["base"]
    vpart, vcap, fcap = labels["body"]
    polys, labs = [], []
    for i, p in enumerate(body.data.polygons):
        polys.append([co_body[v] for v in p.vertices])
        labs.append(int(vpart[p.vertices[0]]) * 1000 + int(fcap[i]))
    for p in bow.data.polygons:
        polys.append([co_bow[v] for v in p.vertices])
        labs.append(labels["bow"] * 1000)
    bco = U.coords(base.data)
    for p in base.data.polygons:
        polys.append([bco[v] for v in p.vertices])
        labs.append(labels["base"] * 1000)
    pts = np.vstack([co_body, co_bow, bco])
    return raycam.build(polys, labs), pts


def see_through(arm, objs, labels, rcfg, names_by_label):
    views = rcfg.get("views") or raycam.DEFAULT_VIEWS
    pitch = float(rcfg.get("pitch_m", 0.0015))
    from .st_close import blobs

    out = {}
    rest_masks = {}
    reset_pose(arm)
    extent = None
    for name in ["rest"] + [t[0] for t in TESTS]:
        pose(arm, name)
        (bvh, lab), pts = ray_scene(objs, labels, evaluated(objs["body"]), evaluated(objs["bow"]))
        if extent is None:  # one grid (origin, size) for every pose: the rest bounds + margin, so pixel phases match
            lo, hi = pts.min(0) - float(rcfg.get("margin_m", 0.1)), pts.max(0) + float(rcfg.get("margin_m", 0.1))
            extent = np.array([[x, y, z] for x in (lo[0], hi[0]) for y in (lo[1], hi[1]) for z in (lo[2], hi[2])])
        grid = extent
        per_view, per_part, total, new_blob, new_blob_view = {}, {}, 0, 0, None
        for vname, az, el in views:
            k, l = raycam.render(bvh, lab, raycam.view_dir(az, el), grid, pitch, pass_back=(lab % 1000) > 0)
            back = k == 2
            per_view[vname] = int(back.sum())
            total += int(back.sum())
            if name == "rest":
                rest_masks[vname] = back
            else:
                b = blobs(back & ~rest_masks[vname])
                if b and b[0] > new_blob:
                    new_blob, new_blob_view = b[0], vname
            for key in np.unique(l[back] // 1000):
                nm = names_by_label[int(key)]
                per_part[nm] = per_part.get(nm, 0) + int((back & (l // 1000 == key)).sum())
        out[name] = {"backface_px": total, "per_view": per_view, "per_part": dict(sorted(per_part.items()))}
        if name != "rest":
            out[name]["largest_new_blob_px"] = new_blob
            out[name]["largest_new_blob_view"] = new_blob_view
    reset_pose(arm)
    rest = out["rest"]
    for name in out:
        if name == "rest":
            continue
        o = out[name]
        o["new_vs_rest_px"] = o["backface_px"] - rest["backface_px"]
        o["new_vs_rest_by_view"] = {v: o["per_view"][v] - rest["per_view"][v] for v in o["per_view"]}
        o["new_vs_rest_by_part"] = {p: o["per_part"].get(p, 0) - rest["per_part"].get(p, 0)
                                    for p in sorted(set(o["per_part"]) | set(rest["per_part"]))
                                    if o["per_part"].get(p, 0) != rest["per_part"].get(p, 0)}
    return {"pitch_m": pitch, "views": [v[0] for v in views], "poses": out}


def workbench_frames(scene, arm, objs, bc_path, fcfg, k2cfg, raw):
    scene.render.engine = "BLENDER_WORKBENCH"
    sh = scene.display.shading
    sh.light = "STUDIO"
    sh.color_type = "TEXTURE"
    sh.show_backface_culling = True
    sh.show_xray = False
    sh.show_shadows = False
    sh.show_cavity = False
    scene.render.film_transparent = True
    scene.render.image_settings.file_format = "PNG"
    scene.render.image_settings.color_mode = "RGBA"
    img = bpy.data.images.load(str(bc_path), check_existing=True)
    mat = bpy.data.materials.new("SEAMS_BC")
    mat.use_nodes = True
    tex = mat.node_tree.nodes.new("ShaderNodeTexImage")
    tex.image = img
    mat.node_tree.nodes.active = tex
    for o in objs.values():
        o.data.materials.clear()
        o.data.materials.append(mat)
    cam_data = bpy.data.cameras.new("seams_cam")
    cam = bpy.data.objects.new("seams_cam", cam_data)
    scene.collection.objects.link(cam)
    scene.camera = cam
    shots = []

    def shoot(name, res):
        scene.render.resolution_x, scene.render.resolution_y = res
        scene.render.resolution_percentage = 100
        scene.render.filepath = str(raw / (name + ".png"))
        bpy.ops.render.render(write_still=True)
        shots.append(name)

    raw.mkdir(parents=True, exist_ok=True)
    for f in fcfg:
        cam_data.type = "ORTHO"
        cam_data.ortho_scale = float(f["ortho_m"])
        d = Vector(f["dir"]).normalized()
        cam.location = Vector(f["target_m"]) + d * 2.0
        cam.rotation_euler = (-d).to_track_quat("-Z", "Y").to_euler()
        for pname in ("rest", f["pose"]):
            pose(arm, pname)
            shoot("%s-%s-%s" % (f["name"], pname, "view"), (700, 700))
    if k2cfg:
        cam_data.type = "PERSP"
        cam_data.sensor_fit = "HORIZONTAL"
        cam_data.angle = math.radians(float(k2cfg["fov_deg_horizontal"]))
        cam_data.clip_start, cam_data.clip_end = 0.05, 100.0
        pitch = math.radians(-float(k2cfg["pitch_deg"]))
        d = Vector((0.0, -math.cos(pitch), math.sin(pitch)))
        cam.location = Vector((0.0, 0.0, float(k2cfg["focus_z_m"]))) + d * float(k2cfg["distance_uu"]) / 100.0
        cam.rotation_euler = (-d).to_track_quat("-Z", "Y").to_euler()
        for pname in ["rest"] + list(k2cfg["poses"]):
            pose(arm, pname)
            shoot("k2-%s" % pname, tuple(k2cfg["resolution"]))
    reset_pose(arm)
    return shots


def run(params, profile):
    run_dir = Path(params["run_dir"])
    rig = profile["rig"]
    cfg = dict(DEFAULTS, **profile.get("seams", {}))
    names = sorted(profile["parts"], key=U.part_key)
    names_by_label = {U.part_key(n): n for n in names}
    bow_label = U.part_key(next(n for n in names if profile["parts"][n]["mesh"] == "weapon"))
    base_label = U.part_key(next(n for n in names if profile["parts"][n]["mesh"] == "base"))
    cap_name_of = cap_names(run_dir, names)
    meshes = profile["meshes"]
    # ---------------- authored .blend
    bpy.ops.wm.open_mainfile(filepath=str(run_dir / "work" / "sk_authored.blend"))
    arm = bpy.data.objects[rig["armature_object"]]
    objs = {"body": bpy.data.objects[meshes["body"]], "bow": bpy.data.objects[meshes["weapon"]],
            "base": bpy.data.objects[meshes["base"]]}
    vpart = np.load(run_dir / "work" / "rig" / "body_vertex_part.npy")
    vcap_path = run_dir / "work" / "rig" / "body_vertex_cap.npy"
    vcap = np.load(vcap_path) if vcap_path.exists() else np.zeros_like(vpart)
    fcap_path = run_dir / "work" / "rig" / "body_face_cap.npy"
    fcap = np.load(fcap_path) if fcap_path.exists() else np.zeros(len(objs["body"].data.polygons), np.int64)
    polys = [list(p.vertices) for p in objs["body"].data.polygons]
    ppart = np.array([vpart[p[0]] for p in polys])
    labels = {"body": (vpart, vcap, fcap), "bow": bow_label, "base": base_label}
    junctions = junction_metric(arm, objs["body"], vpart, ppart, polys, float(rig.get("seam_radius_m", 0.001)),
                                rig["seam_pairs"])
    loops = loop_metric(arm, objs, labels, cfg, names_by_label, cap_name_of)
    st_blend = see_through(arm, objs, labels, cfg["raycast"], names_by_label)
    # ---------------- FBX read back (what UE imports), turned back into the authored frame by the probes stage
    authored_body = objs["body"]
    authored = {"vpart": vpart, "fcap": fcap}
    fbx_blend = run_dir / "work" / "probe-fbx-authored.blend"
    base_src = run_dir / "work" / "sk_authored.blend"
    authored_centres = [(authored_body.matrix_world @ p.center).copy() for p in authored_body.data.polygons]
    authored_first_vert_part = np.array([vpart[p.vertices[0]] for p in authored_body.data.polygons])
    bpy.ops.wm.open_mainfile(filepath=str(fbx_blend))
    with bpy.data.libraries.load(str(base_src), link=False) as (_src, dst):
        dst.objects = [meshes["base"]]
    for o in dst.objects:
        bpy.context.scene.collection.objects.link(o)
    scene = bpy.context.scene
    arm_f = next(o for o in scene.objects if o.type == "ARMATURE")
    body_f = next(o for o in scene.objects if o.type == "MESH" and o.name.startswith(meshes["body"]))
    bow_f = next(o for o in scene.objects if o.type == "MESH" and o.name.startswith(meshes["weapon"]))
    base_f = dst.objects[0]
    kd = KDTree(len(authored_centres))
    for i, c in enumerate(authored_centres):
        kd.insert(c, i)
    kd.balance()
    reset_pose(arm_f)
    fpart = np.zeros(len(body_f.data.polygons), np.int64)
    ffcap = np.zeros(len(body_f.data.polygons), np.int64)
    match_worst = 0.0
    for i, p in enumerate(body_f.data.polygons):
        _c, j, dist = kd.find(body_f.matrix_world @ p.center)
        match_worst = max(match_worst, dist)
        fpart[i] = authored_first_vert_part[j]
        ffcap[i] = authored["fcap"][j]
    fvpart = np.zeros(len(body_f.data.vertices), np.int64)
    for i, p in enumerate(body_f.data.polygons):
        for v in p.vertices:
            fvpart[v] = fpart[i]
    objs_f = {"body": body_f, "bow": bow_f, "base": base_f}
    labels_f = {"body": (fvpart, np.zeros_like(fvpart), ffcap), "bow": bow_label, "base": base_label}
    st_fbx = see_through(arm_f, objs_f, labels_f, cfg["raycast"], names_by_label)
    # ---------------- culled frames on the FBX read-back with the runtime 2K BaseColor
    prefix = profile["textures"]["prefix"]
    k2cfg = None
    if cfg.get("k2_frames"):
        k2 = profile["preview"]["k2"]
        k2cfg = {"fov_deg_horizontal": k2["fov_deg_horizontal"], "pitch_deg": k2["pitch_deg"], "focus_z_m": k2["focus_z_m"],
                 "distance_uu": k2["distances_uu"]["k2-5x"], "resolution": k2["resolution"], "poses": cfg["k2_frames"]}
    shots = workbench_frames(scene, arm_f, objs_f, run_dir / "textures" / ("%s_2K_BC.png" % prefix), cfg.get("frames", []),
                             k2cfg, run_dir / "work" / "seams_raw")
    # ---------------- gates
    open_loops = [r for r in loops if not r["closed_by_cap"]]
    bad_loops = [r for r in open_loops if r["worst"]["open_share"] > float(cfg["max_open_share"])]
    max_blob = int(cfg.get("max_new_blob_px", 8))
    worst_new = {tag: max((v["new_vs_rest_px"] for k, v in st["poses"].items() if k != "rest"), default=0)
                 for tag, st in (("blend", st_blend), ("fbx", st_fbx))}
    worst_blob = {tag: max((v["largest_new_blob_px"] for k, v in st["poses"].items() if k != "rest"), default=0)
                  for tag, st in (("blend", st_blend), ("fbx", st_fbx))}
    checks = {
        "open_loops_do_not_open_in_probe_poses": {
            "passed": not bad_loops,
            "measured": [{k: r[k] for k in ("part", "covered_by", "perimeter_cm", "centre_cm", "worst")} for r in bad_loops]
                        or "none", "expected": "every rim loop not closed by a cap opens (> %s mm) on <= %s of its perimeter"
                                                % (cfg["exposure_threshold_mm"], cfg["max_open_share"])},
        "no_see_through_holes_in_probe_poses": {
            "passed": all(v <= max_blob for v in worst_blob.values()),
            "measured": {"largest_new_blob_px": worst_blob, "new_backface_px_sum_of_views": worst_new},
            "expected": "no 8-connected blob of new back-face pixels (pose and not rest, same view) larger than %d px "
                        "(%.1f mm pitch, %d views), .blend and FBX; the sum of new back-face pixels is reported (rim-edge "
                        "grazing rays leave scattered single pixels)" % (max_blob, st_blend["pitch_m"] * 1000, len(st_blend["views"]))},
        "fbx_polygons_matched_to_authored": {"passed": match_worst < 1e-4, "measured": U.r(match_worst * 1000, 5),
                                             "expected": "< 0.1 mm (nearest polygon centre)"},
    }
    report = {"stage": "seams", "radius_m": junctions["radius_m"], "pairs": junctions["pairs"],
              "junction_vertices": junctions["junction_vertices"], "poses": junctions["poses"],
              "worst_by_pair": junctions["worst_by_pair"],
              "loops": {"threshold_mm": cfg["exposure_threshold_mm"], "count": len(loops),
                        "closed_by_cap": len(loops) - len(open_loops), "open": len(open_loops), "rows": loops},
              "see_through": {"blend": st_blend, "fbx": st_fbx},
              "frames": {"shots": shots, "raw_dir": "<run>/work/seams_raw", "label": cfg.get("frames_label")},
              "checks": checks, "passed": all(c["passed"] for c in checks.values()), "status": "измерено",
              "note": "junction opening = distance to the posed neighbour surface minus the rest distance; loops: rim "
                      "loops of real (non-cap) faces; see-through = first ray hit on a back face (UE one-sided); "
                      "figure height 0.55 m"}
    U.write_json(run_dir / "reports" / "seams-report.json", report)
    if not report["passed"]:
        raise RuntimeError("seams checks failed: %s" % [k for k, c in checks.items() if not c["passed"]])
