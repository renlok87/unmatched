"""Build ue-anim-report.json (stage 3 T2.1) from the live-UE measurements and the headless clip validator.

    python tools/tripo-pipeline/review/p1_anim_report.py <evidence dir>

Inputs in <evidence dir>: ue-anim-measure-raw.json (ue_py/measure_clips.py), ue-anim-import-1.json,
ue-anim-import-probes.json, ue-anim-import-2-reimport.json, ue-anim-listing-reimport.json (ue_py/import_clips.py)
and clip-validator/*.validation.json (tools/tripo-pipeline/anim/validate_clip.py, headless Blender).
Checks per clip (thresholds from the stage-3 plan T2.1): 24 fps; UE length = source length +-0.05 s;
bone 0 and pose bone root |delta| <= 0.5 uu per axis over all keys; frame 0 of every track equals the
target skeleton reference pose (compatibility); component scale 1.0 at the importer default scale;
Weapon/Head sockets keep their bone offset on 3 sample frames. The Idle clip is the negative control:
its peak joint shift is below the proposed 2 % threshold, so it must FAIL `visible_pose_change`.
Statuses: "measured" / "technically_imported" only; nothing here is art acceptance.
"""

import hashlib
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
DUR_TOL, ROOT_TOL, SOCKET_TOL, SCALE_TOL = 0.05, 0.5, 0.01, 1e-3
ROLES = {"AM_Medusa_LungeAttack_Draft": ("MED-LungeAttack-draft", "positive", "AM_Medusa_LungeAttack"),
         "AM_Medusa_HitReact_Draft": ("MED-HitReact-draft", "positive", "AM_Medusa_HitReact"),
         "AM_Medusa_Idle_Draft": ("MED-Idle-draft", "negative_control", "AM_Medusa_Idle")}


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def load(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def main(evidence):
    ev = Path(evidence).resolve()
    raw = load(ev / "ue-anim-measure-raw.json")
    imports = load(ev / "ue-anim-import-1.json")
    probes = load(ev / "ue-anim-import-probes.json")
    reimport = load(ev / "ue-anim-listing-reimport.json")
    by_name = {c["anim"].rsplit("/", 1)[-1]: c for c in raw["clips"]}
    clips, summary = [], {}
    for name, (clip_id, role, stem) in ROLES.items():
        m = by_name[name]
        vfile = ev / "clip-validator" / ("%s.validation.json" % stem if role == "positive"
                                         else "%s.negative-control.validation.json" % stem)
        val = load(vfile)
        src_fbx = REPO / val["clip"]
        checks = {}

        def check(key, passed, measured, expected, note=None):
            checks[key] = {"passed": bool(passed), "measured": measured, "expected": expected}
            if note:
                checks[key]["note"] = note

        check("fps_24", abs((m["frame_rate"] or 0) - 24.0) <= 1e-3, m["frame_rate"], 24.0)
        check("length_equals_source_within_0.05s", abs(m["length_s"] - val["duration_s"]) <= DUR_TOL,
              {"ue_s": m["length_s"], "source_s": val["duration_s"], "delta_s": round(m["length_s"] - val["duration_s"], 6)},
              "|delta| <= %.2f s" % DUR_TOL)
        check("keys_equal_source_frames", m["num_keys"] == val["frames"], m["num_keys"], val["frames"])
        b0 = m["track_" + m["bone0"]]
        rt = m.get("track_root") or {}
        check("bone0_in_place_0.5uu", max(b0["max_abs_delta_uu_xyz"]) <= ROOT_TOL and
              max(abs(x) for x in b0["first_to_last_delta_uu"]) <= ROOT_TOL,
              {"bone0": m["bone0"], "max_abs_delta_uu_xyz": b0["max_abs_delta_uu_xyz"],
               "first_to_last_delta_uu": b0["first_to_last_delta_uu"],
               "root_max_abs_delta_uu_xyz": rt.get("max_abs_delta_uu_xyz")}, "<= %.1f uu per axis" % ROOT_TOL,
              "root motion is read from bone 0 (ue-pipeline-traps 2); root_motion_enabled=%s" % m["root_motion_enabled"])
        comp = m["frame0_vs_reference_pose"]
        worst_rot = max(v["rotation_delta_deg"] for v in comp.values())
        worst_t = max(v["translation_delta_uu"] for v in comp.values())
        check("frame0_matches_target_reference_pose", worst_rot <= 0.01 and worst_t <= 0.01 and
              m["component_max_offset_frame0_vs_reference_uu"] <= 0.01,
              {"max_rotation_delta_deg": worst_rot, "max_translation_delta_uu": worst_t,
               "component_max_offset_uu": m["component_max_offset_frame0_vs_reference_uu"]}, 0.0,
              "the draft clips start in the rest pose, so frame 0 = reference pose of a compatible skeleton")
        check("component_scale_1_at_importer_default", abs(m["component_scale_ratio_frame0_vs_reference"] - 1) <= SCALE_TOL,
              m["component_scale_ratio_frame0_vs_reference"], 1.0)
        samples = m["samples"]
        w = [s.get("weapon_socket_to_hand_L_uu") for s in samples]
        h = [s.get("head_socket_to_head_bone_uu") for s in samples]
        check("sockets_follow_bones_on_3_frames", len(samples) == 3 and None not in w + h and
              max(w) - min(w) <= SOCKET_TOL and max(h) - min(h) <= SOCKET_TOL,
              {"frames": [s["frame"] for s in samples], "weapon_socket_to_hand_L_uu": w,
               "head_socket_to_head_bone_uu": h}, "constant within %.2f uu" % SOCKET_TOL,
              "sockets of the target mesh evaluated with AnimPoseExtensions.get_socket_pose (component space)")
        peak = m["peak_bone_displacement"]
        check("visible_pose_change_2pct", not peak["below_threshold"], peak, ">= 2 % of 55 uu (proposal, not calibrated)")
        val_ok = val["result"] == ("pass" if role == "positive" else "fail")
        passed_ue = all(c["passed"] for c in checks.values())
        if role == "positive":
            result = "PASS" if passed_ue and val["result"] == "pass" else "FAIL"
        else:
            failed = sorted(k for k, c in checks.items() if not c["passed"])
            result = "FAIL (expected: negative control caught)" if failed == ["visible_pose_change_2pct"] and \
                val["fails"] == ["visible_pose_change"] else "UNEXPECTED"
        clips.append({"clip_id": clip_id, "role": role, "ue_asset": m["anim"], "target_mesh": m["mesh"],
                      "target_skeleton": m["skeleton"],
                      "source": {"fbx": val["clip"], "sha256": sha(src_fbx), "bytes": src_fbx.stat().st_size},
                      "validator": {"report": vfile.relative_to(REPO).as_posix(), "result": val["result"],
                                    "fails": val["fails"], "warnings": val["warnings"], "as_expected": val_ok},
                      "ue": {k: m[k] for k in ("length_s", "num_frames", "num_keys", "frame_rate", "tracks",
                                               "root_motion_enabled", "translation_scale_ratio_median",
                                               "component_scale_ratio_frame0_vs_reference", "samples")},
                      "checks": checks, "result": result,
                      "status": "technically_imported" if result == "PASS" else "measured"})
        summary[clip_id] = result
    probes_m = {c["anim"].rsplit("/", 1)[-1]: c for c in raw["clips"] if "/Probes/" in c["anim"]}
    sp = probes_m["AM_Medusa_LungeAttack_ScaleProbe100"]
    up = probes_m["AM_Medusa_LungeAttack_OnT4UmFbxV1"]
    import_scale = {
        "importer_default_import_uniform_scale": imports["clips"][0]["import_uniform_scale_default"],
        "at_default_1.0": {"component_scale_ratio": 1.0, "bone0_scale": [1.0, 1.0, 1.0], "result": "matches the mesh"},
        "probe_100": {"component_scale_ratio": sp["component_scale_ratio_frame0_vs_reference"],
                      "bone0_scale_frame0": sp["frame0_vs_reference_pose"][sp["bone0"]]["scale_frame0"],
                      "local_translation_ratio": sp["translation_scale_ratio_median"],
                      "result": "x100 lands on bone 0 scale: the figure is 100 times too large"},
        "fact": "for these FBX (Blender FBX_SCALE_UNITS + UnitScaleFactor patched to 1.0, like UM_FBX_v1) the "
                "animation import scale is 1.0 (contract RIG-CONTRACT §5 / VALIDATION.md); the S05 value 100 "
                "belongs to FBX_SCALE_NONE exports (ue-pipeline-traps 3) and is wrong here",
        "probe_asset_deleted_after_measurement": True,
    }
    compat = {
        "T4LocalPass": {"skeleton": "/Game/PipelineCandidates/Medusa/T4LocalPass/Meshes/SK_Medusa_Candidate_Skeleton",
                        "compatible": True, "max_rotation_delta_deg": 0.0, "max_translation_delta_uu": 0.0,
                        "note": "same 18 bones and the same reference pose as the clips' rig (build_segmented_medusa.py) "
                                "and as /Game/ART004 (root local rotation roll 90)"},
        "T4UmFbxV1": {"skeleton": "/Game/PipelineCandidates/Medusa/T4UmFbxV1/Meshes/SK_Medusa_Candidate_Skeleton",
                      "compatible": False,
                      "root_rotation_delta_deg": up["frame0_vs_reference_pose"]["root"]["rotation_delta_deg"],
                      "component_max_offset_frame0_uu": up["component_max_offset_frame0_vs_reference_uu"],
                      "note": "UM_FBX_v1 bakes the +90 deg export rotation into the root reference pose (yaw -90); "
                              "the draft clips were exported without it, so their root track turns the figure back "
                              "by 90 deg (front +Y instead of +X). Needs clips re-exported with UM_FBX_v1; the probe "
                              "asset was deleted after the measurement"},
    }
    report = {
        "schema": "unmatched.p1-ue-anim-report/1", "task": "stage 3 T2.1", "date": "2026-09-28",
        "editor": "live UnrealEditor 5.8.2, project unreal/Unmatched of the main checkout, MCP :8123 + editor console `py`",
        "importer": {"cvar": imports["cvar"], "before": imports["cvar_before"], "during": imports["cvar_during_import"],
                     "after": imports["cvar_after"], "restored": imports["cvar_restored"] and probes["cvar_restored"],
                     "path": "legacy FBX (FbxImportUI FBXIT_ANIMATION, import_mesh false, no materials/textures)"},
        "destination": "/Game/PipelineCandidates/Medusa/DraftClips20260928/T4LocalPass",
        "destination_note": "a separate folder: anims inside /Game/PipelineCandidates/Medusa/T4LocalPass would break "
                            "that run's recursive ownership listing (tripo_pipeline ue-import refuses foreign assets)",
        "skeleton_compatibility": compat, "import_scale": import_scale,
        "reimport": {"unchanged_listing": reimport["unchanged"], "numbered_duplicates": reimport["numbered_duplicates"],
                     "replaced_existing": reimport["existed_before"], "cvar_restored": reimport["cvar_restored"]},
        "clips": clips, "summary": summary,
        "not_checked": ["art acceptance of the clips (draft 2-3 bone clips, ART-004)",
                        "playback in a packaged build (/Game/PipelineCandidates is not cooked)",
                        "UM_FBX_v1 re-export of the clips for the T4UmFbxV1 skeleton"],
    }
    out = ev / "ue-anim-report.json"
    out.write_text(json.dumps(report, indent=1, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps(summary, ensure_ascii=False))
    return 0 if all(v.startswith("PASS") or "expected" in v for v in summary.values()) else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1]))
