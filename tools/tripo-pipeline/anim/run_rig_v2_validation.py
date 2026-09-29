"""Прогон validate_clip.py против контракта рига v2 (волна 4, W4-D): позитивная фикстура и негативы.

python tools/tripo-pipeline/anim/run_rig_v2_validation.py [--blender <path>] [--out-dir <dir>]

Каждый кейс задаёт ожидаемый код выхода и точный набор FAIL (и обязательные WARN). Отчёты и
summary.json пишутся в docs/art-pipeline/animation-library/validation-rig-v2/ (или --out-dir).
Исходные файлы только читаются. Позитивная фикстура создаётся make_fixtures.py rigv2.
Blender запускается только headless (-b).

Код выхода 0 — все кейсы выполнены и дали ожидаемый итог; 1 — хотя бы один не выполнен
(нет входа, нет отчёта) или итог не совпал с ожиданием.
"""
import argparse
import json
import os
import subprocess
import sys

REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
OUT = os.path.join(REPO, "docs/art-pipeline/animation-library/validation-rig-v2")
SCRIPT = os.path.join(REPO, "tools/tripo-pipeline/anim/validate_clip.py")
DRAFT = "blender/ASSET-MEDUSA-001/export"
V2FIX = "docs/art-pipeline/animation-library/fixtures/rig-contract-v2/AM_RigV2_LungeAttack_weaponL.fbx"
ARTHUR_SK = "art/pipeline-candidates/ASSET-KING-ARTHUR-001/20260928-cli-um-fbx-v1/export/SK_KingArthur_Candidate.fbx"
MERLIN_SK = "art/pipeline-candidates/ASSET-MERLIN-001/20260928-cli-um-fbx-v1/export/SK_Merlin_Candidate.fbx"
TRIPO_CLIP = ("art/pipeline-candidates/ASSET-MEDUSA-001/tripo-rig-20260928-p16/fixtures/tripo-preset-stoya-otdyh-d562/"
              "tripo_convert_93b4445d-b871-4057-a0d7-1317f45a1548.fbx")
V1 = "--skeleton=UM_HUMANOID_17_v1"

# (кейс, файл, аргументы, код выхода, точный набор FAIL (None — не проверять), обязательные WARN, смысл)
CASES = [
    ("pos-rigv2-Medusa-oneshot", V2FIX, ["--character=Medusa", "--expect-duration=0.5833"], 0, [], [],
     "фикстура v2: SKEL_UM_Humanoid, weapon.L, ref-поза +X, кадр 0 и последний = rest"),
    ("neg-rigv2-as-Arthur", V2FIX, ["--character=Arthur", "--expect-duration=0.5833"], 1,
     ["skeleton_contract", "weapon_side"], [], "у Arthur кость оружия weapon.R, а в файле weapon.L"),
    ("neg-draft-Lunge-v2", DRAFT + "/AM_Medusa_LungeAttack.fbx", ["--expect-duration=0.5833"], 1,
     ["armature_object_name", "weapon_side", "ref_pose_facing"], ["skeleton_contract", "ref_pose_root_axis"],
     "черновик как новый клип: SKEL_Medusa, одно имя weapon (без --character это лишняя кость = WARN "
     "skeleton_contract и FAIL weapon_side), лицо -Y (без поворота UM_FBX_v1)"),
    ("legacy-draft-Lunge-v1-grandfathered", DRAFT + "/AM_Medusa_LungeAttack.fbx", [V1, "--expect-duration=0.5833"],
     0, [], ["skeleton_version", "armature_object_name"], "старый черновик на закрытом v1: допущен по sha256 с WARN"),
    ("neg-rigv2-on-closed-v1", V2FIX, [V1, "--expect-duration=0.5833"], 1, ["skeleton_version", "skeleton_contract"], [],
     "новый файл на закрытом v1: FAIL skeleton_version"),
    ("neg-draft-DeathSettle-v1-as-oneshot", DRAFT + "/AM_Medusa_DeathSettle.fbx",
     [V1, "--expect-duration=0.875", "--clip-role=oneshot"], 1, ["clip_boundary_rest"],
     ["skeleton_version", "armature_object_name"], "DeathSettle с ролью oneshot: последний кадр не rest"),
    ("legacy-draft-DeathSettle-v1-terminal", DRAFT + "/AM_Medusa_DeathSettle.fbx",
     [V1, "--expect-duration=0.875", "--clip-role=terminal"], 0, [], ["skeleton_version", "armature_object_name"],
     "DeathSettle с ролью terminal: финальная поза допустима"),
    ("neg-sk-Arthur-cli-v1-as-v2", ARTHUR_SK, ["--kind=skeletal-mesh", "--character=Arthur"], 1,
     ["skeleton_contract", "weapon_side"], [],
     "SK Arthur CLI 20260928 (одно имя weapon под hand.R): до пересборки с weapon.R (профиль /4) не соответствует v2; "
     "кость 0 и ref-поза уже по v2"),
    ("neg-sk-Merlin-cli-v1-as-v2", MERLIN_SK, ["--kind=skeletal-mesh", "--character=Merlin"], 1,
     ["skeleton_contract", "weapon_side"], [], "SK Merlin CLI 20260928: то же, что у Arthur (профиль /4 — weapon.R)"),
    ("ext-tripo-preset-retarget-map-v2", TRIPO_CLIP, ["--retarget-map=tripo_ue5_mannequin_to_um17", "--loop=true"], 0, [],
     [], "внешний клип с картой ретаргета: имя кости 0, ref-поза и граница — info"),
    ("err-unknown-character", V2FIX, ["--character=Nobody"], 2, None, [], "неизвестный персонаж — ошибка запуска"),
]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--blender", default="C:/Program Files/Blender Foundation/Blender 5.2/blender.exe")
    ap.add_argument("--out-dir", default=OUT)
    a = ap.parse_args()
    out_dir = os.path.abspath(a.out_dir)
    os.makedirs(out_dir, exist_ok=True)
    summary, bad = [], 0
    for name, clip, extra, want_exit, want_fails, want_warns, meaning in CASES:
        clip_abs = os.path.join(REPO, clip)
        entry = {"case": name, "clip": clip, "args": extra, "meaning": meaning,
                 "expected_exit": want_exit, "expected_fails": want_fails, "expected_warnings": want_warns}
        if not os.path.exists(clip_abs):
            bad += 1
            summary.append({**entry, "result": "skipped_missing_input", "expectation_met": False})
            print(name, "SKIPPED_MISSING_INPUT", clip)
            continue
        out = os.path.join(out_dir, name + ".validation.json")
        if os.path.exists(out):
            os.remove(out)
        cmd = [a.blender, "-b", "--factory-startup", "--python", SCRIPT, "--", clip_abs, *extra, "--out=" + out]
        p = subprocess.run(cmd, cwd=REPO, capture_output=True, text=True, encoding="utf-8", errors="replace")
        line = next((l for l in p.stdout.splitlines() if l.startswith("CLIP_VALIDATION")), "")
        rep = None
        if os.path.exists(out):
            with open(out, encoding="utf-8") as f:
                rep = json.load(f)
        if want_exit == 2:
            ok = p.returncode == 2 and rep is None
            entry.update({"exit": p.returncode, "result": "launch_error" if p.returncode == 2 else "unexpected",
                          "line": line, "expectation_met": ok})
        elif rep is None:
            ok = False
            entry.update({"exit": p.returncode, "result": "no_report", "expectation_met": False})
        else:
            fails, warns = rep.get("fails", []), rep.get("warnings", [])
            ok = (p.returncode == want_exit and (want_fails is None or sorted(fails) == sorted(want_fails))
                  and all(w in warns for w in want_warns))
            entry.update({"exit": p.returncode, "result": rep["result"], "fails": fails, "warnings": warns,
                          "expectation_met": ok, "clip_sha256": rep.get("clip_sha256")})
        bad += 0 if ok else 1
        summary.append(entry)
        print(name, p.returncode, "OK" if ok else "UNEXPECTED", line)
    with open(os.path.join(out_dir, "summary.json"), "w", encoding="utf-8", newline="\n") as f:
        json.dump({"schema": "unmatched.clip-validation-summary/1", "contract": "docs/art-pipeline/rig/rig-contract.json",
                   "runner": "tools/tripo-pipeline/anim/run_rig_v2_validation.py", "cases": summary,
                   "result": "pass" if bad == 0 else "fail"}, f, ensure_ascii=False, indent=1)
        f.write("\n")
    print("SUMMARY", "OK" if bad == 0 else f"FAIL: {bad} case(s) not run or expectation not met")
    return 0 if bad == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
