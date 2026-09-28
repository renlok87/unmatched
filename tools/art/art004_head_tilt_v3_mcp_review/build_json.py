"""Writes head-tilt-v3-review-measurements.json into the probe directory (run from the scratch dir, _paths.SCRATCH)."""
import hashlib, json, os

from _paths import PROBE as P
meta = {}
for l in ("cobble", "forest-probe", "paddock-probe"):
    meta.update(json.load(open(f"frames_ev13/meta-{l}.json")))
kept = json.load(open("assembled_manifest.json"))
ue_probe = json.load(open("ue_import_probe.json"))
sockets = json.load(open("ue_sockets.json"))
face = json.load(open("ue_face_metrics.json"))
diffs = json.load(open("ue_frame_diffs.json"))
enc = json.load(open("blender/junction_enclosed.json"))
ramp = json.load(open("blender/rampprobe_metrics.json"))
# Added 2026-09-28 (P0 review fixes): headless follow-up (socket, per-frame clip counts,
# HitReact render), headless K1 bbox, list of files pruned from the probe directory.
fu = json.load(open("followup/followup-measurements.json", encoding="utf-8"))
bm = json.load(open(P + "blender-measurements.json", encoding="utf-8"))
pruned = json.load(open("removed_from_probe_dir.json", encoding="utf-8"))
px_mm2 = (160.0 / 1024) ** 2  # ortho 0.16 m over 1024 px


def mm2(px):
    return round(px * px_mm2, 1)


junction = {}
for k in sorted({k.rsplit("-", 1)[0] for k in enc}):
    v2, v3 = enc[k + "-v2.png"], enc[k + "-v3.png"]
    row = {"v2_enclosed_px": v2["enclosed_gap_px"], "v3_enclosed_px": v3["enclosed_gap_px"],
           "v2_largest_px": v2["largest"][:2], "v3_largest_px": v3["largest"][:2]}
    if not k.startswith("id-cull-k2") and "low" not in k:
        row.update({"v2_mm2": mm2(v2["enclosed_gap_px"]), "v3_mm2": mm2(v3["enclosed_gap_px"])})
    row["face_x_collar_zone_px"] = {"v2": v2["face_x_collar_zone_px"], "v3": v3["face_x_collar_zone_px"]}
    row["rear_zones"] = {z: {t: {f: e["rear_zones"][z][f] for f in ("zone_px", "enclosed_gap_px", "junction_only_px")}
                             for t, e in (("v2", v2), ("v3", v3))}
                         for z in ("neck_back_x_collar", "crown_x_collar")}
    junction[k.replace("id-cull-", "")] = row


def ratio(a, b):
    return round(100.0 * (b / a - 1), 1)


face_summary = {
    "facial_feature_mask_px": {"v2": face["v2"]["face_features_px"], "v3": face["v3"]["face_features_px"],
                               "change_percent": ratio(face["v2"]["face_features_px"], face["v3"]["face_features_px"])},
    "eroded_mask_px": {"v2": face["v2"]["face_eroded_px"], "v3": face["v3"]["face_eroded_px"],
                       "change_percent": ratio(face["v2"]["face_eroded_px"], face["v3"]["face_eroded_px"])},
    "per_light": {l: {"gradient_sum_change_percent": ratio(face["v2"][l]["face_gradient_sum"], face["v3"][l]["face_gradient_sum"]),
                      "gradient_mean_change_percent": ratio(face["v2"][l]["face_gradient_mean"], face["v3"][l]["face_gradient_mean"])}
                  for l in ("cobble", "forest-probe", "paddock-probe")},
    "reading": "The +64..69 % gradient SUM is mostly the larger visible face area (eroded mask +57 %); per pixel the "
               "mean gradient rises only +4..8 %. Both describe the same gain in visible face area, not two independent "
               "proofs of more facial detail (verifier vc, 2026-09-28)."}

OWN = "head-tilt-v3-review-measurements.json"
files_now = {}
for root, _dirs, names in os.walk(P):
    for n in sorted(names):
        rel = os.path.relpath(os.path.join(root, n), P).replace(os.sep, "/")
        if rel != OWN:
            files_now[rel] = hashlib.sha256(open(os.path.join(root, n), "rb").read()).hexdigest()
files_now = dict(sorted(files_now.items()))

report = {
    "status": "measured_diagnostic_not_art_acceptance",
    "date": "2026-09-28",
    "scope": "A1: static head-tilt v3 vs face-neck v2. Editor-only frames; no packaged K2, no HUD, no boardState; draft clips are diagnostic only.",
    "image_inspection_method": "PNG frames were viewed directly with the Read tool in this session (rendered inline) plus pixel metrics with Pillow/numpy/scipy; zai analyze_image was not used.",
    "inputs_sha256": {
        "blender/ASSET-MEDUSA-001/medusa.blend": "2a2534f89093e2a296d34e5b4da41290f1549109d6bc2ef4b1ba29ca978ed903",
        "blender/ASSET-MEDUSA-001/variants/face-section-neck-v2/SK_Medusa_FaceSectionNeck_v2.fbx": "bd125c6bbeb2559b28f6fc4908a1790e0d05fd572b128bd9188c2daeea046592",
        "blender/ASSET-MEDUSA-001/variants/head-tilt-v3/SK_Medusa_HeadTilt_v3.fbx": "b9cea0fe05071b07732b8d72ecc75b074c366bc665679c378cd4e397e1f822a2",
        "blender/ASSET-MEDUSA-001/export/SM_Medusa_Base.fbx": "a49bfbbfe6e51856aebcd9d3e7cc9a45bc142f0ff110830f446a28c76997ba4f",
        "blender/ASSET-MEDUSA-001/atlas-report.json": "f0f6b9428d822e4b595792842853708737a34475060b176414c6cff4fe06b8aa"},
    "v3_edit": {
        "source": "tools/art/art004_face_skeletal_export.py::tilt_head (uncommitted diff in the art worktree)",
        "rotation_deg_about_x_source_axes": -15.0, "pivot_cm": [0, 0, 38.5],
        "moved_parts": {"tripo_part_1 crown": 2633, "tripo_part_10 face/throat": 587, "tripo_part_14 rear neck": 480},
        "moved_vertices": 4717,
        "excluded": "tripo_part_3 shoulder/collar (100% head-weighted, not rotated), quiver, bow, hands",
        "bones_changed": False,
        "effect": "top of the head moves backward (away from the front), the face turns up toward the elevated D-10 camera"},
    "blender_headless_reproducible": {
        "script": "tools/art/art004_head_tilt_v3_measure.py",
        "output": "blender-measurements.json + blender-id-*.png + blender-tex-*.png",
        "rerun_2026-09-28": "exit 0; blender-measurements.json byte-identical; 22 PNG pixel-identical (only PNG Date/RenderTime metadata differs)"},
    "blender_live_mcp": {
        "session": "live Blender 5.2.2 GUI via MCP 127.0.0.1:9876, isolated scene A1V3_Review (appended read-only from medusa.blend + both FBX imported); removed after the review, nothing saved",
        "v3_fbx_vs_live_tilt_of_source_max_abs_cm": 2e-06,
        "fbx_structure": {"body_triangles": 18199, "bow_triangles": 1197, "body_material_slots": 2,
                          "bow_material_slots": 1, "armature_bones": 17,
                          "same_topology_uv_winding_v2_v3": True},
        "draft_clip_head_vs_nonhead_intersecting_triangle_pairs": {
            "Idle": {"v2_max": 0, "v3_max": 0}, "LungeAttack": {"v2_max": 0, "v3_max": 0},
            "DeathSettle": {"v2_max": 0, "v3_max": 0},
            "HitReact": {"v2_max": 0, "v3_max": 40, "v3_mean": 9.5, "v3_worst_frame": 4, "v3_pair": "crown x quiver"},
            "per_frame_headless_followup": {a: {"frame_range": v["frame_range"], "v2": v["v2"]["per_frame"], "v3": v["v3"]["per_frame"],
                                                "v3_crown_quiver": v["v3"]["crown_quiver_per_frame"]}
                                            for a, v in fu["draft_clip_per_frame"].items()},
            "per_frame_matches_blender_measurements_max_mean": fu["draft_clip_matches_blender_measurements_max_mean"],
            "hitreact_render": {"file": "compare-blender-hitreact-f4.png", "frame": fu["hitreact_render"]["frame"],
                                "camera": fu["hitreact_render"]["camera"],
                                "replaces": "blender-mcp-live/viewport-cmp-hitreact-f4.png (live viewport, two different cameras, unlabelled, other figure's base in frame)"}},
        "rest_clearance_cm": {"crown_to_quiver_v2": 1.074, "crown_to_quiver_v3": 0.308,
                              "moved_parts_to_bow_v2": 10.124, "moved_parts_to_bow_v3": 11.374},
        "viewport_comparisons": "blender-mcp-live/viewport-cmp-fbx-d10-{front,rear}.png: left v2, right v3 (matched pixel-exactly to the single live shots), caption strip added 2026-09-28; same camera relative to each figure's spine bone",
        "rest_interpenetration_pairs_moved_vs_static": {"v2": 28, "v3": 88,
                                                        "v3_by_pair": {"crown|shoulder_collar": 46, "neck_back|shoulder_collar": 42}},
        "neck_junction_see_through_backface_culled": {
            "note": "enclosed transparent pixels near the face/throat (part 10) x collar (part 3) boundary; ortho 16 cm views at 1024 px (0.156 mm/px); k2 = 1920x1080 D-10 300 uu",
            "rear_zones_note": "added 2026-09-28 after vc: in rear views the face zone is empty or nearly empty (face_x_collar_zone_px), so its 0 was 0 by construction. rear_zones = neck_back (part 14) x collar and crown (part 1) x collar, same band, recomputed on the same live renders; junction_only_px excludes enclosed regions bordered by the quiver or bow (>= 10 px: background seen between separate pieces, e.g. crown / collar / quiver strap). Components can fall in both zones, so the two zones are not summed.",
            "views": junction},
        "k2_front_visible_px_1920x1080": {
            "facial_features_z_ge_42cm": {"v2": 809, "v3": 1242},
            "throat_z_lt_42cm": {"v2": 1434, "v3": 1697},
            "whole_face_part_10": {"v2": 2243, "v3": 2939},
            "crown": {"v2": 10517, "v3": 11761}, "quiver": {"v2": 577, "v3": 416},
            "quiver_note": "whole visible quiver (mostly its top with the fletching), not the fletching alone; recomputed in ue_face_metrics.py (quiver_px), throat likewise (throat_px)",
            "bow": {"v2": 6663, "v3": 6663}, "collar": {"v2": 6448, "v3": 6530}},
        "k2_rear_visible_px": {"crown": {"v2": 13791, "v3": 11684}, "rear_neck": {"v2": 318, "v3": 21},
                               "collar": {"v2": 3156, "v3": 1949}},
        "k1_figure_bbox_px_headless": {
            "v2": bm["blender_views"]["d10-k1scale-front"]["v2"]["figure_bbox_px"],
            "v3": bm["blender_views"]["d10-k1scale-front"]["v3"]["figure_bbox_px"],
            "note": "K1 fit distance, 1920x1080: v2 about 47 x 72 px (width x height incl. base), v3 top 3 px higher"},
        "crown_top_band_from_headless_ids": "see blender-measurements.json blender_views: K2 front rows with >=3 separate crown runs 9 -> 18, background gaps 271 -> 434 px; K2 rear 4 -> 0 rows, 693 -> 519 px",
        "ramp_probe_diagnostic_not_candidate": {
            "definition": "in memory only: same -15 deg, face and rear-neck angle smoothstep from 0 at z=38.5 cm to full at z=42 cm; crown full; not exported, not imported to UE",
            "enclosed_gap_px": {k: {t: ramp[k][t]["enclosed_gap_px"] for t in ("v2", "v3", "rampprobe")} for k in ramp},
            "k2_front_face_part_px": {t: ramp["k2-front-d300"][t]["face_px"] for t in ("v2", "v3", "rampprobe")},
            "crown_to_quiver_cm": 0.308}},
    "ue_live_mcp": {
        "editor": "live UnrealEditor 5.8 with C:/Users/ren/WebstormProjects/unmached/unmached/unreal/Unmatched, MCP 127.0.0.1:8123; no UnrealEditor-Cmd was started",
        "import": {
            "tool": "SkeletalMeshTools.import_file / StaticMeshTools.import_file (FbxImportUI + FbxFactory, defaults: import normals, tangents recomputed, uniform scale 1)",
            "difference_to_game_import_script": "art004_import_v2_game_candidate.py uses FBXNIM_IMPORT_NORMALS_AND_TANGENTS; MCP frames are compared only with MCP frames",
            "assets": ["/Game/ArtTests/ART004_V3Review/Meshes/SK_Medusa_V2Review",
                       "/Game/ArtTests/ART004_V3Review/Meshes/SK_Medusa_V3Review",
                       "/Game/ArtTests/ART004_V3Review/Meshes/SM_Medusa_BaseReview"],
            "production_or_artpreview_touched": False,
            "measured": ue_probe},
        "sockets": {
            "added_like_game_import": {"Weapon": "bone weapon, offset (0,0,0)", "Head": "bone head, offset (0,0,4)"},
            "component_space_cm": {k.split(" ")[1]: {"Head": v["socket_Head"]["component_space_cm"],
                                                     "Weapon": v["socket_Weapon"]["component_space_cm"]}
                                   for k, v in sockets.items()},
            "note_bone_name_collision": "get_socket_location('head') resolves the Head socket first (FName is case-insensitive), so bone_head_cm in the raw probe equals the socket",
            "head_socket_vs_geometry": {
                "socket_to_facial_feature_centroid_cm": {"v2": fu["head_socket"]["v2"]["socket_to_feature_centroid_uu"],
                                                         "v3": fu["head_socket"]["v3"]["socket_to_feature_centroid_uu"]},
                "socket_nearest_surface_cm": fu["head_socket"]["v3"]["socket_nearest_surface_uu"],
                "socket_inside_mesh": fu["head_socket"]["v3"]["ray_forward_hits"] % 2 == 1,
                "v3_socket_if_rotated_with_head_ue_component_cm": fu["head_socket"]["v3_socket_if_rotated_with_head_ue_component_uu"],
                "v3_socket_offset_vs_rotated_cm": fu["head_socket"]["v3_socket_offset_vs_rotated_uu"],
                "tilt_direction_check_max_uu": {"minus15": fu["head_socket"]["saved_v3_face_vs_v2_rotated_minus15_max_uu"],
                                                "plus15": fu["head_socket"]["saved_v3_face_vs_v2_rotated_plus15_max_uu"]},
                "provenance": "Recomputed headless by tools/art/art004_head_tilt_v3_followup.py (followup-measurements.json). "
                              "blender/b9_socket.py was corrected after the live run: the executed copy rotated by +15 deg; the "
                              "saved -15 deg file was never run. The earlier hand-typed values (7.639/8.511/1.122, "
                              "(0;3.864;39.535), 1.044) are confirmed by this recomputation and by the verifier's independent check."},
            "weapon_socket_changed": False},
        "capture_setup": {
            "levels": {"cobble": "/Game/ArtTests/ART005H/L_ART005H_CornerReview",
                       "forest-probe": "/Game/ArtTests/ART005I/L_ART005I_ForestReferenceLight",
                       "paddock-probe": "/Game/ArtTests/ART005I/L_ART005I_PaddockReferenceLight"},
            "in_memory_only": "fill 'ART005 neutral readability fill - review only' moved (0,-100,550)->(0,100,500), animation-review Medusa moved to (10000,10000,0), base + v2/v3 SkeletalMeshActors at (0,-50,0); levels reloaded from disk without saving (umap mtimes unchanged)",
            "materials": "both body slots and the base = /Game/ART004/Medusa/Materials/MI_Medusa_Blue (as in the CLI capture script)",
            "viewport": {
                "capture": "EditorAppToolset.CaptureViewport with captureTransform",
                "fov_deg": 35, "aspect_constraint": "AspectRatio_MaintainXFOV", "viewport_px": [2033, 1216],
                "crop": "centre 2033x1144 (16:9), Lanczos to 1920x1080",
                "exposure": "fixed EV100 1.3 (viewport 'Game settings' off) calibrated to the CLI SceneCapture frames on the lower floor (calib.py windows): CLI vs MCP +1..4 % mean RGB (v3 frames, three lights; the first note said ~1-6 %). In the top corners the CLI frames are darker (SceneCapture vignette): -6..-13 % in 300x200 px windows, -12..-21 % in 150x100 px windows (frame_metrics.diffs.exposure_cli_vs_mcp_v3_percent). This does not affect v2 vs v3 inside the MCP set.",
                "grid_show_flag": "off", "r.EyeAdaptationQuality": 0,
                "restored_after": {"fov_deg": 90, "exposure": "Game settings, EV100 1.0", "grid": "on",
                                   "r.EyeAdaptationQuality": 2, "level": "/Game/S08/S08Arena", "dirty_packages": 0}},
            "d10_k2": "camera = figure + (0, 300cos55, 29+300sin55) looking at (x, y, 29); rear = mirrored Y; K1 = fit expression of art004_face_static_ue_capture.py",
            "frames": meta},
        "frame_metrics": {
            "face_readability_proxy_k2_front": {
                "definition": "UE frame pixels inside the Blender facial-feature mask (same D-10 camera, pixel-aligned); Sobel gradient of display luminance",
                "values": face,
                "summary": face_summary},
            "diffs": diffs,
            "calibration_note": "MCP viewport vs CLI SceneCapture differ by ~14/255 mean abs in the head region, more than v2 vs v3 (~6/255): never mix the two sets in one comparison"}},
    "files_in_probe_dir": files_now,
    "probe_dir_pruning_2026-09-28": {
        "reason": "keep only key frames in git (P0 review): K2 Cobble UE frames, composites, part-ID renders, JSON; 54 MB -> about 14 MB",
        "removed_sha256": pruned["removed"],
        "replaced_unlabelled_originals_sha256": pruned["replaced_unlabelled_originals"],
        # Added after the P0 manifest review: the byte-identical rename of the git-ignored *.log
        # and a per-file check of where every pruned file still exists.
        "renamed": pruned["renamed"],
        "cli_rear_unlit_crop": kept["ue-cli-headtiltprobe"]["cli-rear-unlit-head-crop-v3.png"],
        "where_now": {
            "ue-mcp-live forest/paddock K2 (8) and Cobble close-ups (4)":
                "NOT durable: only in C:/tmp (backup C:/tmp/a1-probe-backup/head-tilt-v3-probe-2026-09-28.full and scratch "
                "C:/tmp/a1v3/frames_ev13, pixel-identical). Live-editor frames, not bit-reproducible. In git remain their "
                "crops in compare-ue-*.png and the metrics computed from them (ue_live_mcp.frame_metrics).",
            "blender-mcp-live/viewport-cmp-hitreact-f4.png (1)":
                "NOT durable: only in C:/tmp (backup; C:/tmp/a1v3/blender/cmp-hitreact-f4.png is byte-identical). Superseded by "
                "compare-blender-hitreact-f4.png from the headless tools/art/art004_head_tilt_v3_followup.py.",
            "ue-cli-headtiltprobe CLI PNG (4)":
                "local only: byte-identical in the git-ignored unreal/Unmatched/Artifacts/ART004Face of the art worktree "
                "(and in the backup).",
            "blender-tex-*.png (8)":
                "durable: regenerated pixel-identically by tools/art/art004_head_tilt_v3_measure.py from inputs in git.",
            "viewport-cmp-fbx-d10-{front,rear}.png unlabelled originals (2)":
                "durable: the labelled files in git are pixel-identical to them below the 40 px caption strip.",
            "ue-cli-headtiltprobe/headtilt-export.log (1)":
                "in git as the byte-identical headtilt-export-log.txt (see renamed)."},
        "durability_check": pruned["durability_check"]},
    "side_effects": {
        "ue_main_checkout": "5 review assets in /Game/ArtTests/ART004_V3Review/Meshes (Content is git-ignored, about 10.4 MB) reference the production /Game/ART004/Medusa/Materials/MI_Medusa_Blue; keep or delete is an open orchestrator decision",
        "blender_live_session": "b99_cleanup.py ran bpy.data.orphans_purge, which also removed one unused material from the user's unsaved start-up session (2 -> 1 materials); nothing was saved. Do not repeat in user sessions."},
    "headless_followup": {"script": "tools/art/art004_head_tilt_v3_followup.py", "runner": fu["runner"],
                          "inputs_sha256": fu["inputs_sha256"]},
    "verdict": {"decision": "rework (v3.1)", "v3_as_static_candidate": "not accepted",
                "v2": "remains the isolated game candidate", "art_accepted": False, "gd_058": "open",
                "open_art_question": "seven separate snake heads are not readable at K2 in v2 or v3; 04-blender-production.md asks for a readable crown, not detailed snakes, so this is an open art question, not a failed check"}}

json.dump(report, open(P + OWN, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print("written", len(json.dumps(report)))
