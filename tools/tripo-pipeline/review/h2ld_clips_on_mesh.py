"""Look-dev C: do the H2Anim clips of a hero play on its look-dev mesh? (LIVE editor, read only, no level touched)

    python tools/tripo-pipeline/review/h2ld_clips_on_mesh.py --spec <hero h2anim spec json> --mesh <SK package> \
        --out <report json>

Runs review/ue_py/measure_clips.py (the H2Anim measurement: frame 0 vs the skeleton reference pose, peak bone
displacement over all keys, Weapon / Head sockets on sample frames, evaluated WITH the mesh) for every clip of the spec on
the given mesh, and compares with the H2Anim measurement on the preview mesh (<h2anim run>/reports/ue-measure-clips.json):
the clip's skeleton must be the mesh's canonical skeleton, the evaluated pose must equal the H2Anim one (same skeleton,
same keys) and the mesh's sockets must be found on the posed mesh. Editor diagnostics, not an animation acceptance.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import math
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
sys.path.insert(0, str(HERE))


def main() -> int:
    from ue_live import Ue, URL
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--spec", required=True)
    ap.add_argument("--mesh", required=True)
    ap.add_argument("--skeleton", required=True, help="canonical skeleton package the mesh was imported onto")
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    spec = json.loads((REPO / a.spec).read_text(encoding="utf-8"))
    run = REPO / spec["run_dir"]
    prev = json.loads((run / "reports/ue-measure-clips.json").read_text(encoding="utf-8"))
    prev_by = {c["anim"]: c for c in prev["clips"]}
    clips = []
    for n, c in spec["clips"].items():
        k = int(c["frames"])
        clips.append({"anim": "%s/AM_%s_%s" % (spec["ue"]["clips_folder"], spec["ue_hero"], n), "mesh": a.mesh,
                      "source_duration_s": round(k / 24.0, 6), "source_frames": k + 1,
                      "sample_frames": sorted(set(c.get("key_frames", [0, k // 2, k])))})
    height = max(c["peak_bone_displacement"]["height_uu"] for c in prev["clips"])
    out = Path(a.out).resolve()
    out.parent.mkdir(parents=True, exist_ok=True)
    ue = Ue()
    res = ue.run_task(str(HERE / "ue_py" / "measure_clips.py"), str(out.with_suffix(".task.json")), timeout=900,
                      clips=clips, height_uu=height, min_pose_change=0.02)
    tmp = out.with_suffix(".task.json")
    if tmp.exists():
        tmp.unlink()
    rows, ok_all = {}, True
    skel_obj = a.skeleton + "." + a.skeleton.rsplit("/", 1)[-1]
    for c in res["clips"]:
        p = prev_by.get(c["anim"]) or {}
        pk, ppk = c["peak_bone_displacement"], (p.get("peak_bone_displacement") or {})
        socks = sorted(set(c.get("sockets_available") or []))
        checks = {
            "clip_skeleton_is_the_mesh_skeleton": c["skeleton"] == skel_obj,
            "frame0_pose_on_mesh_equals_h2anim": p.get("component_max_offset_frame0_vs_reference_uu") is not None and
            abs(c["component_max_offset_frame0_vs_reference_uu"] - p["component_max_offset_frame0_vs_reference_uu"]) <= 0.01,
            "peak_displacement_equals_h2anim": bool(ppk) and abs(pk["uu"] - ppk["uu"]) <= 0.01 and pk["bone"] == ppk["bone"]
            and pk["frame"] == ppk["frame"],
            "clip_moves_the_mesh": not pk["below_threshold"] or bool(ppk.get("below_threshold")),
            "mesh_sockets_on_posed_mesh": "Head" in socks and "Weapon" in socks,
            "length_as_source": abs(c.get("length_delta_s") or 0.0) <= 0.05,
        }
        ok_all &= all(checks.values())
        rows[c["anim"].rsplit("/", 1)[-1]] = {
            "checks": checks, "length_s": c["length_s"], "frames": c["num_frames"], "fps": c["frame_rate"],
            "peak_bone_displacement": pk, "h2anim_peak": ppk,
            "frame0_offset_uu": c["component_max_offset_frame0_vs_reference_uu"],
            "h2anim_frame0_offset_uu": p.get("component_max_offset_frame0_vs_reference_uu"),
            "sockets": socks, "samples": c.get("samples"),
            "bone0_track": c.get("track_" + c["bone0"])}
    rep = {"schema": "unmatched.h2ld-clips-on-mesh/1", "tool": "tools/tripo-pipeline/review/h2ld_clips_on_mesh.py",
           "at": dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat(), "editor": URL,
           "spec": a.spec, "mesh": a.mesh, "skeleton": a.skeleton, "h2anim_measure": str(
               (run / "reports/ue-measure-clips.json").relative_to(REPO)).replace("\\", "/"),
           "passed": ok_all, "clips": rows,
           "note": "AnimPose evaluated with the look-dev mesh (AnimPoseEvaluationOptions.optional_skeletal_mesh); the "
                   "clip plays on the mesh when its skeleton is the mesh's canonical skeleton and the posed bones equal "
                   "the H2Anim measurement on the preview mesh Rig/SK_<Hero>. Read only."}
    out.write_text(json.dumps(rep, indent=1, sort_keys=True, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n")
    for n, r in rows.items():
        print(n, "OK" if all(r["checks"].values()) else "FAIL", r["checks"], "peak", r["peak_bone_displacement"]["uu"],
              r["peak_bone_displacement"]["bone"])
    print("passed", ok_all)
    return 0 if ok_all else 1


if __name__ == "__main__":
    sys.exit(main())
