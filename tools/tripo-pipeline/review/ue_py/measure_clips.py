"""UE editor Python task (LIVE editor via review/ue_live.py run_task): measure imported AnimSequences. Read only.

ARGS: {"out": ..., "height_uu": 55.0, "min_pose_change": 0.02,
       "clips": [{"anim": "/Game/.../AM_X", "mesh": "/Game/.../SK_X", "source_duration_s": 0.5833,
                  "source_frames": 15, "sample_frames": [0, 7, 14] | null}]}

Per clip: frame rate, length, frame count, track names; bone 0 (and pose bone root) local track
over every frame (max |delta| per axis vs frame 0, first->last drift); translation of every track
at frame 0 against the skeleton reference pose, plus the component-space distance ratio of frame 0 to
the reference pose (scale factor of the import: a x100 import lands on bone 0's scale, not on the
local translations); rotation of every track at frame 0 against the reference pose (compatibility); peak component-space bone
displacement vs frame 0 (share of height_uu); sockets Weapon/Head and bones hand_L/head in
component space on sample frames (evaluated with the mesh, so mesh sockets are included).
"""
import json
import math

import unreal as u

args = ARGS  # noqa: F821 - injected by ue_py/_run.py
AL, PE, SP = u.AnimationLibrary, u.AnimPoseExtensions, u.AnimPoseSpaces


def v3(v):
    return [round(v.x, 4), round(v.y, 4), round(v.z, 4)]


def rot(q):
    r = q.rotator()
    return [round(r.pitch, 3), round(r.yaw, 3), round(r.roll, 3)]


def quat_angle_deg(a, b):
    dot = abs(a.x * b.x + a.y * b.y + a.z * b.z + a.w * b.w)
    return round(math.degrees(2 * math.acos(min(1.0, dot))), 4)


def dist(a, b):
    return math.sqrt(sum((a[i] - b[i]) ** 2 for i in range(3)))


out = {"clips": []}
for clip in args["clips"]:
    anim = u.load_asset(clip["anim"])
    mesh = u.load_asset(clip["mesh"])
    skel = anim.get_editor_property("skeleton")
    length = AL.get_sequence_length(anim)
    frames = AL.get_num_frames(anim)
    keys = AL.get_num_keys(anim)
    dt = AL.get_time_at_frame(anim, 1) - AL.get_time_at_frame(anim, 0)
    tracks = [str(t) for t in AL.get_animation_track_names(anim)]
    ref = PE.get_reference_pose(skel)
    bone_names = [str(n) for n in PE.get_bone_names(ref)]
    bone0 = bone_names[0]
    rec = {"anim": clip["anim"], "mesh": clip["mesh"], "skeleton": skel.get_path_name(),
           "length_s": round(length, 6), "num_frames": frames, "num_keys": keys,
           "frame_rate": round(1.0 / dt, 4) if dt else None, "tracks": tracks, "bone0": bone0,
           "root_motion_enabled": AL.is_root_motion_enabled(anim),
           "source_duration_s": clip.get("source_duration_s"), "source_frames": clip.get("source_frames")}
    if clip.get("source_duration_s") is not None:
        rec["length_delta_s"] = round(length - clip["source_duration_s"], 6)
    # bone 0 and root local tracks over every key
    for bone in (bone0, "root"):
        if bone not in bone_names:
            continue
        series = [AL.get_bone_pose_for_frame(anim, bone, f, False) for f in range(keys)]
        t0 = series[0].translation
        max_abs = [0.0, 0.0, 0.0]
        max_rot = 0.0
        for t in series:
            d = [t.translation.x - t0.x, t.translation.y - t0.y, t.translation.z - t0.z]
            max_abs = [max(max_abs[i], abs(d[i])) for i in range(3)]
            max_rot = max(max_rot, quat_angle_deg(series[0].rotation, t.rotation))
        last = series[-1].translation
        rec["track_" + bone] = {"frame0_t": v3(t0), "frame0_r": rot(series[0].rotation),
                                "ref_local_t": v3(PE.get_ref_bone_pose(ref, bone, SP.LOCAL).translation),
                                "ref_local_r": rot(PE.get_ref_bone_pose(ref, bone, SP.LOCAL).rotation),
                                "max_abs_delta_uu_xyz": [round(x, 5) for x in max_abs],
                                "first_to_last_delta_uu": [round(last.x - t0.x, 5), round(last.y - t0.y, 5),
                                                           round(last.z - t0.z, 5)],
                                "max_rotation_from_frame0_deg": round(max_rot, 4)}
    # frame 0 of every track vs the skeleton reference pose (local)
    compat = {}
    ratios = []
    for bone in bone_names:
        if bone not in tracks and bone != bone0:
            continue
        a = AL.get_bone_pose_for_frame(anim, bone, 0, False)
        r = PE.get_ref_bone_pose(ref, bone, SP.LOCAL)
        la, lr = a.translation.length(), r.translation.length()
        if lr > 1e-3:
            ratios.append(la / lr)
        compat[bone] = {"translation_delta_uu": round(dist(v3(a.translation), v3(r.translation)), 5),
                        "rotation_delta_deg": quat_angle_deg(a.rotation, r.rotation),
                        "scale_frame0": v3(a.scale3d), "scale_ref": v3(r.scale3d),
                        "translation_length_ratio": round(la / lr, 5) if lr > 1e-3 else None}
    rec["frame0_vs_reference_pose"] = compat
    rec["translation_scale_ratio_median"] = sorted(ratios)[len(ratios) // 2] if ratios else None
    # component-space poses with the mesh (sockets)
    opts = u.AnimPoseEvaluationOptions()
    opts.set_editor_property("optional_skeletal_mesh", mesh)
    opts.set_editor_property("extract_root_motion", False)
    base = PE.get_anim_pose_at_frame(anim, 0, opts)
    base_pos = {b: v3(PE.get_bone_pose(base, b, SP.WORLD).translation) for b in bone_names}
    ref_pos = {b: v3(PE.get_ref_bone_pose(ref, b, SP.WORLD).translation) for b in bone_names}
    comp_ratios = sorted(math.sqrt(sum(x * x for x in base_pos[b])) / math.sqrt(sum(x * x for x in ref_pos[b]))
                         for b in bone_names if math.sqrt(sum(x * x for x in ref_pos[b])) > 1.0)
    rec["component_scale_ratio_frame0_vs_reference"] = round(comp_ratios[len(comp_ratios) // 2], 5) if comp_ratios else None
    rec["component_max_offset_frame0_vs_reference_uu"] = round(max(dist(base_pos[b], ref_pos[b]) for b in bone_names), 4)
    peak = (0.0, None, None)
    for f in range(keys):
        pose = PE.get_anim_pose_at_frame(anim, f, opts)
        for b in bone_names:
            d = dist(v3(PE.get_bone_pose(pose, b, SP.WORLD).translation), base_pos[b])
            if d > peak[0]:
                peak = (d, b, f)
    height = float(args.get("height_uu", 55.0))
    rec["peak_bone_displacement"] = {"uu": round(peak[0], 4), "bone": peak[1], "frame": peak[2],
                                     "share_of_height": round(peak[0] / height, 5), "height_uu": height,
                                     "threshold_share": args.get("min_pose_change", 0.02),
                                     "below_threshold": peak[0] / height < args.get("min_pose_change", 0.02),
                                     "note": "bone joints only (no mesh vertices); validator counts heads and tails"}
    sample = clip.get("sample_frames") or [0, keys // 2, keys - 1]
    sockets = [str(s) for s in PE.get_socket_names(base)]
    rec["sockets_available"] = sockets
    samples = []
    for f in sample:
        pose = PE.get_anim_pose_at_frame(anim, f, opts)
        item = {"frame": f, "time_s": round(AL.get_time_at_frame(anim, f), 5)}
        for s in ("Weapon", "Head"):
            if s in sockets:
                item["socket_" + s] = v3(PE.get_socket_pose(pose, s, SP.WORLD).translation)
        for b in ("hand_L", "weapon", "head", bone0, "root"):
            if b in bone_names:
                item["bone_" + b] = v3(PE.get_bone_pose(pose, b, SP.WORLD).translation)
        if "socket_Weapon" in item and "bone_hand_L" in item:
            item["weapon_socket_to_hand_L_uu"] = round(dist(item["socket_Weapon"], item["bone_hand_L"]), 4)
        if "socket_Head" in item and "bone_head" in item:
            item["head_socket_to_head_bone_uu"] = round(dist(item["socket_Head"], item["bone_head"]), 4)
        samples.append(item)
    rec["samples"] = samples
    out["clips"].append(rec)
with open(args["out"], "w", encoding="utf-8", newline="\n") as handle:
    handle.write(json.dumps(out, indent=1, sort_keys=True) + "\n")
u.log("TRIPO_UE_PY_OK measure_clips")
