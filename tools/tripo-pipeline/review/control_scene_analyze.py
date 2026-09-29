"""Analysis of the P1.7 control-scene runs (stage 3, T3.1): repeat noise (E2), idempotency of the scene report,
silhouettes, team colour in grey, animation test, scale/sockets/materials, base see-through in the frames, decor
support height and the per-asset model checklist numbers.

    python tools/tripo-pipeline/review/control_scene_analyze.py --runs <dir> --tags r1 r2 r3 --out <evidence dir>
        [--repro-tag repro] [--ue-reports <run dirs of the heroes>]

Reads the PNG frames and control-scene-report.json of every tag written by control_scene.py (offline, no editor).
Writes into --out: noise.json (E2: noise = max pairwise mean |dRGB| over the repeats, threshold = 2 x noise),
idempotency.json, measurements.json (silhouettes, team colour in grey, animation, scale, sockets, materials, lights)
and, with --repro-tag, repro-frames.json (repro barrel frames against the repeats, threshold from noise.json).
Numbers only: nothing here is an art decision; the checklist judgements are written by hand into
model-checklist.json next to these numbers.
"""

import argparse
import itertools
import json
import math
from pathlib import Path

import numpy as np
from PIL import Image

W, H = 1920, 1080
FOV, PITCH, YAW = 35.0, -55.0, -90.0
MASK_T = 12.0      # per-pixel mean |dRGB| (0..255) that counts as "the subject is here" (repeat noise is < 1)
WINDOW_PX = 24     # margin around the projected box of the subject's world bounds
TEAM_T = 6.0       # per-pixel mean |dRGB| between the team and the swapped-team frame
DISC_SHARE = 0.93  # base top disc sampled for see-through (rim bevel excluded; = base_seethrough.py)
DISC_ERODE_PX = 2  # anti-aliased edge of the projected disc
VOID_T = 4         # max channel (0..255) of a pixel that shows the editor void behind the hidden board ((0,0,0))
VOLATILE = ("started_at", "finished_at", "frames", "warmup_mean_abs_diff", "settle_mean_abs_diff", "tag", "console",
            "previous_packages_deleted", "cleanup", "sha256", "main_frames", "diagnostic_frames", "_task")
HERO_TARGETS_FROM = {"arthur": "ASSET-KING-ARTHUR-001", "merlin": "ASSET-MERLIN-001", "harpy1": "ASSET-HARPY-001",
                     "harpy2": "ASSET-HARPY-001", "harpy3": "ASSET-HARPY-001"}


def load(path):
    return np.asarray(Image.open(path).convert("RGB"), dtype=np.float64)


def mad(a, b):
    return float(np.abs(a - b).mean())


def luma(img):
    return img[..., 0] * 0.2126 + img[..., 1] * 0.7152 + img[..., 2] * 0.0722


def project(points, cam_loc, pitch=PITCH, yaw=YAW, fov=FOV):
    """World points -> pixel coordinates of the 1920x1080 frame (horizontal FOV, UE camera axes)."""
    p, y = math.radians(pitch), math.radians(yaw)
    fwd = np.array([math.cos(p) * math.cos(y), math.cos(p) * math.sin(y), math.sin(p)])
    right = np.array([-math.sin(y), math.cos(y), 0.0])
    up = np.cross(fwd, right)
    f = (W / 2) / math.tan(math.radians(fov / 2))
    d = np.asarray(points, dtype=np.float64) - np.asarray(cam_loc, dtype=np.float64)
    z = d @ fwd
    return np.stack([W / 2 + f * (d @ right) / z, H / 2 - f * (d @ up) / z], axis=-1)


def polygon_mask(poly):
    from PIL import ImageDraw
    img = Image.new("L", (W, H), 0)
    ImageDraw.Draw(img).polygon([tuple(map(float, q)) for q in poly], fill=1)
    return np.asarray(img, dtype=bool)


def mask_stats(mask):
    ys, xs = np.nonzero(mask)
    if not len(xs):
        return {"area_px": 0}
    return {"area_px": int(mask.sum()), "bbox_px": [int(xs.min()), int(ys.min()), int(xs.max()), int(ys.max())],
            "width_px": int(xs.max() - xs.min() + 1), "height_px": int(ys.max() - ys.min() + 1)}


def min_gap_px(a, b):
    """Smallest pixel distance between two masks (0 = touching/overlapping)."""
    if (a & b).any():
        return 0.0
    from scipy import ndimage  # noqa: PLC0415 - optional, only for this metric
    dist = ndimage.distance_transform_edt(~a)
    return float(dist[b].min())


def strip(obj):
    if isinstance(obj, dict):
        return {k: strip(v) for k, v in obj.items() if k not in VOLATILE}
    if isinstance(obj, list):
        return [strip(v) for v in obj]
    if isinstance(obj, float):
        return round(obj, 3)
    return obj


def diff_paths(a, b, path=""):
    out = []
    if isinstance(a, dict) and isinstance(b, dict):
        for k in sorted(set(a) | set(b)):
            out += diff_paths(a.get(k), b.get(k), path + "/" + str(k))
    elif isinstance(a, list) and isinstance(b, list) and len(a) == len(b):
        for i, (x, y) in enumerate(zip(a, b)):
            out += diff_paths(x, y, "%s[%d]" % (path, i))
    elif a != b:
        out.append({"path": path, "a": a, "b": b})
    return out


DECOR_SUNK_TOL_UU, DECOR_SPREAD_TOL_UU = 0.05, 0.1


def decor_support(build):
    """Decor actors placed by the build on the surface under them (build["decor_support"], review fix: the barrel
    stood at z 0 inside the 5 uu wooden rim). on_surface: bottom = highest support hit (|sunk| <= DECOR_SUNK_TOL_UU)
    and a flat support (spread <= DECOR_SPREAD_TOL_UU)."""
    dec = {}
    for label, sup in sorted((build.get("decor_support") or {}).items()):
        act = build["actors"][label]
        bottom = act["world_bounds"]["min"][2]
        sunk = round(sup["support_z_max_uu"] - bottom, 4)
        dec[label.split(" ", 1)[1]] = {
            "support_z_max_uu": sup["support_z_max_uu"], "support_z_min_uu": sup["support_z_min_uu"],
            "spread_uu": sup["spread_uu"], "supports": sup["supports"], "samples": sup["samples"],
            "actor_z_uu": act["location"][2], "bottom_z_uu": bottom, "sunk_into_support_uu": sunk,
            "on_surface": abs(sunk) <= DECOR_SUNK_TOL_UU and sup["spread_uu"] <= DECOR_SPREAD_TOL_UU,
            "rule": "bottom = top of the surface under the whole bottom footprint (|sunk| <= %.2f uu, spread <= %.1f uu)"
                    % (DECOR_SUNK_TOL_UU, DECOR_SPREAD_TOL_UU)}
    return dec


def void_holes(disc, disc_uu2, empty, base_only, with_figure):
    """Board-hidden 5x frames of one base (RGB 0..255): void pixels inside the projected top disc. base_only = holes of
    the base mesh; with_figure = the holes that stay void with the figure in place (a black figure pixel exactly over
    a hole still counts: upper bound). void_empty_ok: the disc is all void without the base (the camera sees nothing
    else there)."""
    void = {k: disc & (img.max(axis=2) <= VOID_T) for k, img in (("empty", empty), ("base", base_only),
                                                                 ("figure", with_figure))}
    out = {}
    for key, mask in (("void_empty", void["empty"]), ("base_only", void["base"]),
                      ("with_figure", void["base"] & void["figure"])):
        share = float(mask.sum()) / max(1, int(disc.sum()))
        out[key] = dict(mask_stats(mask), void_px=int(mask.sum()), share_of_disc=round(share, 4),
                        area_uu2_est=round(share * disc_uu2, 2))
    out["void_empty_ok"] = out["void_empty"]["share_of_disc"] >= 0.999
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--runs", required=True)
    ap.add_argument("--tags", nargs="+", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--repro-tag")
    ap.add_argument("--repo", default=str(Path(__file__).resolve().parents[3]))
    a = ap.parse_args()
    runs, out, repo = Path(a.runs), Path(a.out), Path(a.repo)
    out.mkdir(parents=True, exist_ok=True)
    reports = {t: json.loads((runs / t / "control-scene-report.json").read_text(encoding="utf-8")) for t in a.tags}
    base = reports[a.tags[0]]

    # ---------------------------------------------------------------- E2 noise over the repeats
    common = sorted(set.intersection(*[set(r["frames"]) for r in reports.values()]))
    per_frame, roi_c = {}, (slice(270, 810), slice(480, 1440))
    for name in common:
        imgs = {t: load(runs / t / name) for t in a.tags}
        pairs = {}
        for x, y in itertools.combinations(a.tags, 2):
            pairs["%s-%s" % (x, y)] = {"full": round(mad(imgs[x], imgs[y]), 4),
                                       "centre_960x540": round(mad(imgs[x][roi_c], imgs[y][roi_c]), 4),
                                       "max_px": int(np.abs(imgs[x] - imgs[y]).max())}
        per_frame[name] = {"pairs": pairs, "noise_full": max(p["full"] for p in pairs.values()),
                           "noise_centre": max(p["centre_960x540"] for p in pairs.values())}
    main_names = [n for n in common if base["frames"][n].get("set") == "main"]
    noise = {"rule": "E2 (s3-baseline thresholds.json E2_repeat_noise): noise = max over the repeat pairs of the mean "
                     "|dRGB| (0..255) in a fixed ROI; threshold = 2 x noise",
             "repeats": a.tags, "roi": {"full": "1920x1080", "centre_960x540": "rows 270-810, cols 480-1440"},
             "frames": per_frame,
             "main_set": {"frames": main_names,
                          "noise_full": max(per_frame[n]["noise_full"] for n in main_names),
                          "noise_centre": max(per_frame[n]["noise_centre"] for n in main_names)}}
    noise["main_set"]["threshold_full"] = round(2 * noise["main_set"]["noise_full"], 4)
    noise["main_set"]["threshold_centre"] = round(2 * noise["main_set"]["noise_centre"], 4)
    noise["all_frames"] = {"noise_full": max(v["noise_full"] for v in per_frame.values()),
                           "threshold_full": round(2 * max(v["noise_full"] for v in per_frame.values()), 4)}
    (out / "noise.json").write_text(json.dumps(noise, indent=1, sort_keys=True) + "\n", encoding="utf-8", newline="\n")

    # ---------------------------------------------------------------- idempotency of the scene report
    stripped = {t: strip(r) for t, r in reports.items()}
    idem = {"compared": a.tags, "ignored_keys": list(VOLATILE),
            "differences": {"%s-%s" % (x, y): diff_paths(stripped[x], stripped[y])
                            for x, y in itertools.combinations(a.tags, 2)}}
    idem["identical"] = all(not v for v in idem["differences"].values())
    idem["frame_sets_equal"] = all(set(r["frames"]) == set(base["frames"]) for r in reports.values())
    (out / "idempotency.json").write_text(json.dumps(idem, indent=1, sort_keys=True, ensure_ascii=False) + "\n",
                                          encoding="utf-8", newline="\n")

    # ---------------------------------------------------------------- measurements (first repeat)
    t0 = a.tags[0]
    r0 = runs / t0
    fr = base["frames"]
    build = base["build"]
    names =sorted({lab.split(" ")[1] for lab in build["actors"]})
    meas = {"repeat_used": t0, "mask_threshold": MASK_T, "team_threshold": TEAM_T}
    # silhouettes: subject alone with shadows off minus the empty board, restricted to the projected box of the
    # subject's world bounds (+ WINDOW_PX) and reduced to its largest connected component (temporal AA leaves
    # scattered single pixels above the threshold elsewhere on the board)
    sil, masks_k1 = {}, {}

    def subject_box(n, cam):
        labs = [lab for lab in build["actors"] if lab.split(" ")[1] == n]
        lo = np.min([build["actors"][lab]["world_bounds"]["min"] for lab in labs], axis=0)
        hi = np.max([build["actors"][lab]["world_bounds"]["max"] for lab in labs], axis=0)
        corners = [[x, y, z] for x in (lo[0], hi[0]) for y in (lo[1], hi[1]) for z in (lo[2], hi[2])]
        pr = project(corners, cam)
        return [float(pr[:, 0].min()), float(pr[:, 1].min()), float(pr[:, 0].max()), float(pr[:, 1].max())]

    def subject_mask(diff, box):
        from scipy import ndimage  # noqa: PLC0415
        win = np.zeros(diff.shape, dtype=bool)
        x0, y0 = max(0, int(box[0]) - WINDOW_PX), max(0, int(box[1]) - WINDOW_PX)
        x1, y1 = min(W, int(box[2]) + WINDOW_PX + 1), min(H, int(box[3]) + WINDOW_PX + 1)
        win[y0:y1, x0:x1] = True
        m = (diff > MASK_T) & win
        lab, n = ndimage.label(m)
        if n == 0:
            return m, {"window_px": [x0, y0, x1, y1], "components": 0}
        sizes = ndimage.sum(m, lab, range(1, n + 1))
        keep = lab == (int(np.argmax(sizes)) + 1)
        return keep, {"window_px": [x0, y0, x1, y1], "components": int(n),
                      "largest_component_share": round(float(sizes.max() / sizes.sum()), 4)}

    if "p17-mask-k1-empty-ue-editor.png" in fr:
        empty_k1 = load(r0 / "p17-mask-k1-empty-ue-editor.png")
        cam_k1 = fr["p17-k1-overview-ue-editor.png"]["camera"]["location"]
        for n in names:
            item = {}
            f1 = r0 / ("p17-mask-k1-%s-ue-editor.png" % n)
            if f1.exists():
                box = subject_box(n, fr[f1.name]["camera"]["location"])
                m, info = subject_mask(np.abs(load(f1) - empty_k1).mean(axis=2), box)
                masks_k1[n] = m
                item["k1"] = dict(mask_stats(m), projected_box_px=[round(v, 1) for v in box], **info)
            f2, e2 = r0 / ("p17-mask-k2-1p6-%s-ue-editor.png" % n), r0 / ("p17-mask-k2-1p6-empty-%s-ue-editor.png" % n)
            if f2.exists() and e2.exists():
                box = subject_box(n, fr[f2.name]["camera"]["location"])
                m, info = subject_mask(np.abs(load(f2) - load(e2)).mean(axis=2), box)
                item["k2_1p6"] = dict(mask_stats(m), projected_box_px=[round(v, 1) for v in box], **info)
            sil[n] = item
        harp = [n for n in names if n.startswith("harpy")]
        sil["harpy_pairs_k1_min_gap_px"] = {"%s-%s" % (x, y): round(min_gap_px(masks_k1[x], masks_k1[y]), 2)
                                            for x, y in itertools.combinations(harp, 2) if x in masks_k1 and y in masks_k1}
        sil["figure_pairs_k1_min_gap_px"] = {"%s-%s" % (x, y): round(min_gap_px(masks_k1[x], masks_k1[y]), 2)
                                             for x, y in itertools.combinations([n for n in names if n != "barrel"], 2)
                                             if x in masks_k1 and y in masks_k1}
        # decor rule: barrel pixels over the cells (500 x 600 uu at z 0) in K1
        cells = project([[-250, -300, 0], [250, -300, 0], [250, 300, 0], [-250, 300, 0]], cam_k1)
        cell_mask = polygon_mask(cells)
        if "barrel" in masks_k1:
            sil["barrel_over_cells_k1_px"] = int((masks_k1["barrel"] & cell_mask).sum())
            sil["barrel_over_cells_note"] = ("silhouette pixels of the barrel inside the projected 5 x 6 cell area "
                                             "(500 x 600 uu at z 0) of the K1 frame")
    meas["silhouettes"] = sil
    # team colour in grey
    team = {}
    for n in names:
        alt = r0 / ("p17-team-alt-k2-1p6-%s-ue-editor.png" % n)
        main = r0 / ("p17-k2-1p6-%s-ue-editor.png" % n)
        if not alt.exists():
            continue
        A, B = load(main), load(alt)
        m = np.abs(A - B).mean(axis=2) > TEAM_T
        la, lb = luma(A)[m], luma(B)[m]
        team[n] = {"changed_px": int(m.sum()), "materials_swapped": fr[alt.name].get("materials"),
                   "mean_rgb_default": [round(float(v), 2) for v in A[m].mean(0)] if m.any() else None,
                   "mean_rgb_swapped": [round(float(v), 2) for v in B[m].mean(0)] if m.any() else None,
                   "mean_luma_default": round(float(la.mean()), 2) if m.any() else None,
                   "mean_luma_swapped": round(float(lb.mean()), 2) if m.any() else None,
                   "delta_luma": round(float(la.mean() - lb.mean()), 2) if m.any() else None,
                   "mean_abs_luma_diff_per_px": round(float(np.abs(la - lb).mean()), 2) if m.any() else None,
                   "note": "luma = Rec.709 weights on the sRGB frame values; the pixels that change when the team "
                           "material is swapped (per-pixel mean |dRGB| > %.0f)" % TEAM_T}
    meas["team_colour_in_grey"] = team
    # animation test
    anim = base.get("anim_test")
    if anim:
        poses = anim["poses"]
        p0 = poses[0]["points"]["points"]

        def dist(u, v):
            return round(math.dist(u, v), 4)
        rows = []
        for p in poses:
            pts = p["points"]["points"]
            rows.append({"percent": p["percent"], "time_s": p["time_s"],
                         "actor_location": p["points"]["actor_location"],
                         "bone0_delta_uu": dist(pts["SKEL_Medusa"]["world"], p0["SKEL_Medusa"]["world"]),
                         "root_delta_uu": dist(pts["root"]["world"], p0["root"]["world"]),
                         "socket_weapon_to_bone_weapon_uu": dist(pts["Weapon"]["world"], pts["weapon"]["world"]),
                         "socket_weapon_to_hand_L_uu": dist(pts["Weapon"]["world"], pts["hand_L"]["world"]),
                         "socket_head_to_bone_head_uu": dist(pts["Head"]["world"], pts["head"]["world"]),
                         "hand_L_moved_from_pose0_uu": dist(pts["hand_L"]["world"], p0["hand_L"]["world"]),
                         "head_moved_from_pose0_uu": dist(pts["head"]["world"], p0["head"]["world"]),
                         "position_read_back_s": p["points"]["position_read_back"]})
        frames_mad = {}
        for tag in ("k2-1p6", "k2-5x"):
            f0 = load(r0 / ("p17-anim-lunge-p000-%s-ue-editor.png" % tag))
            frames_mad[tag] = {"p%03d" % p["percent"]: round(mad(load(r0 / ("p17-anim-lunge-p%03d-%s-ue-editor.png" % (p["percent"], tag))), f0), 4)
                               for p in poses}
        meas["anim_test"] = {"clip": anim["clip"], "length_s": anim["length_s"], "poses": rows,
                             "frame_mean_abs_diff_vs_pose0": frames_mad,
                             "thresholds": {"bone0_and_root_delta_uu_max": 0.5,
                                            "source": "rig-contract §4 / T2.1 (0.5 uu)"},
                             "bone0_root_within": all(r["bone0_delta_uu"] <= 0.5 and r["root_delta_uu"] <= 0.5 for r in rows),
                             "actor_location_constant": len({tuple(r["actor_location"]) for r in rows}) == 1}
    # scale, sockets, materials, lights
    actors = build["actors"]
    scale = {}
    for n in names:
        fig, bas = actors.get("P17 %s figure" % n), actors.get("P17 %s base" % n)
        if fig:
            scale[n] = {"figure_world_top_uu": fig["world_bounds"]["max"][2], "figure_world_bottom_uu": fig["world_bounds"]["min"][2],
                        "base_top_uu": bas["world_bounds"]["max"][2] if bas else None,
                        "feet_below_base_top_uu": round(bas["world_bounds"]["max"][2] - fig["world_bounds"]["min"][2], 4) if bas else None,
                        "footprint_xy_uu": [round(fig["world_bounds"]["max"][i] - fig["world_bounds"]["min"][i], 3) for i in (0, 1)],
                        "base_xy_uu": [round(bas["world_bounds"]["max"][i] - bas["world_bounds"]["min"][i], 3) for i in (0, 1)] if bas else None,
                        "cell_uu": 100, "triangles_figure_lod0": fig.get("triangles_lod0"),
                        "triangles_base_lod0": bas.get("triangles_lod0") if bas else None,
                        "bones": fig.get("bones"), "bone0": fig.get("bone0"), "skeleton": fig.get("skeleton")}
        else:
            st = actors["P17 %s" % n]
            scale[n] = {"world_bounds": st["world_bounds"], "triangles_lod0": st.get("triangles_lod0"),
                        "size_uu": [round(st["world_bounds"]["max"][i] - st["world_bounds"]["min"][i], 3) for i in range(3)]}
    meas["scale"] = scale
    meas["decor_support"] = decor_support(build)
    # base see-through in the frames (review fix): 5x frames with the board actors hidden (the editor void behind the
    # board renders exactly (0,0,0)): base alone (figure hidden), figure + base, and neither. base_only = void pixels
    # (max channel <= VOID_T) inside the projected top disc of the base (DISC_SHARE of its radius at its top z, eroded
    # DISC_ERODE_PX): holes of the base mesh. with_figure = those hole pixels that stay void with the figure in place
    # (the figure does not cover them). Void alone is not used for with_figure: without the board there is no bounce
    # light and shadowed figure pixels render black too (upper bound: a black figure pixel exactly over a hole still
    # counts). Against the board the test is unreliable (grout lines and grey bases match the board within MASK_T;
    # the board under a base renders darker than the empty board), so the board-background 5x frames
    # (mask-k2-5x-base-*) are visual references only. Area estimate = pixel share x disc area (uu^2, plane of the top).
    see = {}
    for n in names:
        fv = {k: r0 / ("p17-mask-k2-5x-void-%s%s-ue-editor.png" % (k, n)) for k in ("empty-", "base-", "")}
        bas = actors.get("P17 %s base" % n)
        if not bas or not all(f.exists() for f in fv.values()):
            continue
        from scipy import ndimage  # noqa: PLC0415
        lo, hi = bas["world_bounds"]["min"], bas["world_bounds"]["max"]
        cx, cy = bas["location"][0], bas["location"][1]
        r_s = DISC_SHARE * min(hi[0] - lo[0], hi[1] - lo[1]) / 2.0
        ring = [[cx + r_s * math.cos(t), cy + r_s * math.sin(t), hi[2]]
                for t in np.linspace(0.0, 2 * math.pi, 180, endpoint=False)]
        disc = ndimage.binary_erosion(polygon_mask(project(ring, fr[fv["empty-"].name]["camera"]["location"])),
                                      iterations=DISC_ERODE_PX)
        disc_uu2 = math.pi * r_s ** 2
        yaw = bas["yaw"]
        side = {90.0: "+X (front of a UM_FBX_v1 mesh)", -90.0: "-X (back)"}.get(round(yaw, 1), "yaw %.1f" % yaw)
        item = {"frames": {"void_empty": fv["empty-"].name, "base_only": fv["base-"].name, "with_figure": fv[""].name,
                           "visual_board_background": ["p17-mask-k2-5x-base-%s-ue-editor.png" % n,
                                                       "p17-mask-k2-5x-%s-ue-editor.png" % n]},
                "camera_side_in_mesh_space": side, "disc_radius_uu": round(r_s, 3), "disc_plane_z_uu": hi[2],
                "disc_px": int(disc.sum()), "disc_area_uu2": round(disc_uu2, 2), "void_threshold": VOID_T}
        item.update(void_holes(disc, disc_uu2, load(fv["empty-"]), load(fv["base-"]), load(fv[""])))
        see[n] = item
    meas["base_see_through_frames"] = see
    sockets = {}
    for n in names:
        fig = actors.get("P17 %s figure" % n)
        if not fig:
            continue
        item = {"measured_component_uu": {k: v["component"] for k, v in fig["sockets"].items()},
                "bones": {k: v["bone"] for k, v in fig["sockets"].items()}}
        asset = HERO_TARGETS_FROM.get(n)
        if asset:
            rep = json.loads((repo / "art/pipeline-candidates" / asset / "20260928-cli-um-fbx-v1/reports/ue-import-report.json")
                             .read_text(encoding="utf-8"))
            manifest = json.loads((repo / "art/pipeline-candidates" / asset / "20260928-cli-um-fbx-v1/manifest.json")
                                  .read_text(encoding="utf-8"))
            bprof = json.loads((repo / manifest["config"]["build_profile"]).read_text(encoding="utf-8"))
            targets = {}
            for s in rep["measured"]["sockets_plan"]:
                if s.get("target_ue_component_uu"):
                    targets[s["name"]] = {"target": s["target_ue_component_uu"], "source": "build target (ue-import plan)"}
            for s in bprof["sockets"]:
                if s["name"] not in targets and s.get("measured_target_ue_component_uu"):
                    targets[s["name"]] = {"target": s["measured_target_ue_component_uu"], "source": "profile measured target"}
            for name, t in targets.items():
                m = item["measured_component_uu"].get(name)
                if m:
                    d = round(math.dist(m, t["target"]), 4)
                    t.update(distance_uu=d, within_0p05=d <= 0.05, within_0p15=d <= 0.15)
            item["targets"] = targets
        sockets[n] = item
    meas["sockets"] = sockets
    mats = {}
    for label, act in sorted(actors.items()):
        for i, m in enumerate(act["materials"]):
            if not m:
                continue
            key = "%s [%d]" % (label, i)
            tex = (m.get("textures") or [])
            mats[key] = {"material": m["path"], "parents": m.get("parents"), "base_material": m.get("base_material"),
                         "vector_parameters": m.get("vector_parameters"), "scalar_parameters": m.get("scalar_parameters"),
                         "textures": tex,
                         "texture_contract_ok": all(
                             (t["srgb"] and t["compression"] == "TC_DEFAULT") if t["path"].endswith("_BC") else
                             (not t["srgb"] and t["compression"] == "TC_NORMALMAP" and not t["flip_green"]) if t["path"].endswith("_N") else
                             (not t["srgb"] and t["compression"] == "TC_MASKS") if t["path"].endswith("_ORM") else
                             (not t["srgb"]) for t in tex)}
    meas["materials"] = mats
    meas["lights"] = {"lights": build["lights"], "shadow_casting": build["shadow_casting_lights"],
                      "exposure_volume": build["exposure_volume"]}
    (out / "measurements.json").write_text(json.dumps(meas, indent=1, sort_keys=True, ensure_ascii=False) + "\n",
                                           encoding="utf-8", newline="\n")

    # ---------------------------------------------------------------- repro barrel frames
    if a.repro_tag:
        rr = json.loads((runs / a.repro_tag / "control-scene-report.json").read_text(encoding="utf-8"))
        res = {"repro_tag": a.repro_tag, "barrel_asset": rr["scene_spec"]["actors"][[s["label"] for s in rr["scene_spec"]["actors"]].index("P17 barrel")]["asset"],
               "threshold_from": "noise.json main_set threshold_full / threshold_centre (2 x repeat noise)",
               "frames": {}}
        for name in sorted(rr["frames"]):
            if name not in common:
                continue
            rep_img = load(runs / a.repro_tag / name)
            vs = {t: {"full": round(mad(rep_img, load(runs / t / name)), 4),
                      "centre_960x540": round(mad(rep_img[roi_c], load(runs / t / name)[roi_c]), 4)} for t in a.tags}
            res["frames"][name] = {"vs_repeats": vs, "max_full": max(v["full"] for v in vs.values()),
                                   "max_centre": max(v["centre_960x540"] for v in vs.values()),
                                   "threshold_full": noise["main_set"]["threshold_full"],
                                   "threshold_centre": noise["main_set"]["threshold_centre"]}
            res["frames"][name]["within"] = (res["frames"][name]["max_full"] <= noise["main_set"]["threshold_full"] and
                                             res["frames"][name]["max_centre"] <= noise["main_set"]["threshold_centre"])
        res["all_within"] = all(v["within"] for v in res["frames"].values())
        (out / "repro-frames.json").write_text(json.dumps(res, indent=1, sort_keys=True) + "\n", encoding="utf-8",
                                               newline="\n")
    print(json.dumps({"noise_main_full": noise["main_set"]["noise_full"], "threshold_full": noise["main_set"]["threshold_full"],
                      "idempotent_report": idem["identical"]}, indent=1))


if __name__ == "__main__":
    main()
