"""Sample imported Medusa animation tracks; prove the four clips drive the rig."""

import json
import math
from pathlib import Path

import unreal as u


ROOT = Path(__file__).resolve().parents[2]
BASE = "/Game/ART004/Medusa/Animation/AM_Medusa_"
OUT = ROOT / "blender/ASSET-MEDUSA-001/ue-animation-report.json"
SAMPLES = {
    "Idle": (0.0, 1.16, 2.32),
    "LungeAttack": (0.0, 0.29, 0.54),
    "HitReact": (0.0, 0.125, 0.34),
    "DeathSettle": (0.0, 0.46, 0.86),
}
BONES = ("root", "hips", "spine", "head", "arm_upper_L", "arm_upper_R", "weapon")


def numbers(vector):
    return [round(vector.x, 4), round(vector.y, 4), round(vector.z, 4)]


def sample(sequence, bone, seconds):
    transform = u.AnimationLibrary.get_bone_pose_for_time(sequence, bone, seconds, False)
    q = transform.rotation
    return {"translation": numbers(transform.translation),
            "rotation": [round(q.x, 5), round(q.y, 5), round(q.z, 5), round(q.w, 5)],
            "scale": numbers(transform.scale3d)}


def main():
    report = {"clips": {}, "checks": {}}
    for name, times in SAMPLES.items():
        sequence = u.load_asset(BASE + name + "_Anim")
        if not sequence:
            raise RuntimeError("Missing " + name)
        samples = {str(t): {bone: sample(sequence, bone, t) for bone in BONES} for t in times}
        report["clips"][name] = {"duration_s": sequence.get_play_length(), "sample_times_s": times}
        first = samples[str(times[0])]
        middle = samples[str(times[1])]
        root_delta = max(abs(samples[str(t)]["root"]["translation"][i] - first["root"]["translation"][i])
                         for t in times for i in range(3))
        # q and -q encode the same orientation: compare abs(dot), not component deltas.
        pose_changes = {}
        for bone in BONES:
            a = first[bone]["rotation"]
            b = middle[bone]["rotation"]
            dot = min(1.0, abs(sum(a[i] * b[i] for i in range(4))))
            pose_changes[bone] = round(math.degrees(2.0 * math.acos(dot)), 3)
        check = {"root_delta_uu": root_delta, "rotation_delta_deg": pose_changes,
                 "root_stable": root_delta < 0.01,
                 "animated": max(pose_changes.values()) > (1.0 if name == "Idle" else 5.0)}
        report["checks"][name] = check
        if not (check["root_stable"] and check["animated"]):
            raise RuntimeError(name + " failed pose check: " + str(check))
    OUT.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    u.log("ART004_ANIMATION_VERIFIED " + str(OUT))


main()
