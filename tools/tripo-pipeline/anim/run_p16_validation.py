"""Воспроизводит прогон P1.6: валидация тестовых клипов Medusa, фикстур BVH/GLB и Tripo-пресета.

python tools/tripo-pipeline/anim/run_p16_validation.py [--blender <path>]

Пишет отчёты в docs/art-pipeline/animation-library/validation/ и сводку
summary.json. Исходные клипы только читаются. Фикстуры лежат в отслеживаемом
art/pipeline-candidates/ASSET-MEDUSA-001/tripo-rig-20260928-p16/fixtures/ и
пересоздаются make_fixtures.py. Blender запускается только headless (-b).

Контракт v2 (2026-09-29): черновые клипы и фикстуры P1.6 — файлы скелета UM_HUMANOID_17_v1, который
закрыт для новых клипов; кейсы ниже проверяют их явно с --skeleton=UM_HUMANOID_17_v1 (WARN
skeleton_version по sha256) и с ролью границы клипа (DeathSettle — terminal). --out-dir позволяет
повторить прогон, не переписывая отчёты P1.6 в validation/ (они — свидетельство P1.6 от 2026-09-28).
Кейсы контракта v2 — run_rig_v2_validation.py.

Код выхода 0 — все кейсы выполнены и дали ожидаемый итог. Код 1 — хотя бы один
кейс не выполнен (нет входного файла, нет отчёта) или итог не совпал с ожиданием,
включая перекрёстную проверку ветки GLB против FBX.
"""
import argparse
import json
import os
import subprocess
import sys

REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
VAL = os.path.join(REPO, "docs/art-pipeline/animation-library/validation")
SCRIPT = os.path.join(REPO, "tools/tripo-pipeline/anim/validate_clip.py")
RUN = "art/pipeline-candidates/ASSET-MEDUSA-001/tripo-rig-20260928-p16"
FIX = RUN + "/fixtures"
TRIPO_CLIP = FIX + "/tripo-preset-stoya-otdyh-d562/tripo_convert_93b4445d-b871-4057-a0d7-1317f45a1548.fbx"

V1 = "--skeleton=UM_HUMANOID_17_v1"  # закрытый скелет черновиков (контракт v2); WARN skeleton_version по sha256

CASES = [
    # (report name, clip, extra args, expected exit, expected warnings)
    ("AM_Medusa_Idle", "blender/ASSET-MEDUSA-001/export/AM_Medusa_Idle.fbx",
     [V1, "--expect-duration=2.3333", "--loop=true"], 0, ["visible_pose_change", "skeleton_version"]),
    ("AM_Medusa_LungeAttack", "blender/ASSET-MEDUSA-001/export/AM_Medusa_LungeAttack.fbx",
     [V1, "--expect-duration=0.5833"], 0, ["skeleton_version"]),
    ("AM_Medusa_HitReact", "blender/ASSET-MEDUSA-001/export/AM_Medusa_HitReact.fbx",
     [V1, "--expect-duration=0.375"], 0, ["skeleton_version"]),
    ("AM_Medusa_DeathSettle", "blender/ASSET-MEDUSA-001/export/AM_Medusa_DeathSettle.fbx",
     [V1, "--expect-duration=0.875", "--clip-role=terminal"], 0, ["skeleton_version"]),
    ("bvh-roundtrip-AM_Medusa_LungeAttack", FIX + "/AM_Medusa_LungeAttack.bvh",
     [V1, "--bvh-up=Z", "--expect-duration=0.5833"], 0, ["skeleton_version"]),
    ("glb-roundtrip-AM_Medusa_LungeAttack", FIX + "/AM_Medusa_LungeAttack.glb",
     [V1, "--expect-duration=0.5833"], 0, ["skeleton_version"]),
    ("tripo-preset-stoya-otdyh-d562", TRIPO_CLIP,
     ["--retarget-map=tripo_ue5_mannequin_to_um17", "--loop=true"], 0, []),
    ("negative-SK_Medusa-static", "blender/ASSET-MEDUSA-001/export/SK_Medusa.fbx", [V1], 1, []),
    ("negative-tripo-preset-direct-contract", TRIPO_CLIP, [], 1, []),
]

# Ветка GLB должна давать те же рост и пик сдвига, что FBX того же клипа.
GLB_CROSS = {"case": "glb-roundtrip-AM_Medusa_LungeAttack", "reference": "AM_Medusa_LungeAttack",
             "height_rel_tol": 0.02, "peak_rel_tol": 0.25}


def check_value(rep, name):
    return next((c for c in rep.get("checks", []) if c["check"] == name), {})


def glb_cross_check(reports):
    g, f = reports.get(GLB_CROSS["case"]), reports.get(GLB_CROSS["reference"])
    if not g or not f:
        return {"result": "not_run", "reason": "нет одного из отчётов"}
    hg, hf = g["reference_height"], f["reference_height"]
    pg = check_value(g, "visible_pose_change").get("peak_max_joint_shift_of_height")
    pf = check_value(f, "visible_pose_change").get("peak_max_joint_shift_of_height")
    items = {
        "height_rel_diff": round(abs(hg - hf) / hf, 5),
        "peak_rel_diff": round(abs(pg - pf) / pf, 5) if pg is not None and pf else None,
        "glb_reference_meshes": g.get("reference_meshes"),
        "glb_bone_length_plausible": check_value(g, "bone_length_plausible").get("status"),
        "glb_reference_height": hg, "fbx_reference_height": hf, "glb_peak": pg, "fbx_peak": pf,
    }
    ok = (items["height_rel_diff"] <= GLB_CROSS["height_rel_tol"]
          and items["peak_rel_diff"] is not None and items["peak_rel_diff"] <= GLB_CROSS["peak_rel_tol"]
          and items["glb_bone_length_plausible"] == "pass"
          and not any("Icosphere" in m for m in (items["glb_reference_meshes"] or [])))
    return {"result": "pass" if ok else "fail", **items,
            "tolerances": {"height_rel": GLB_CROSS["height_rel_tol"], "peak_rel": GLB_CROSS["peak_rel_tol"]}}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--blender", default="C:/Program Files/Blender Foundation/Blender 5.2/blender.exe")
    ap.add_argument("--out-dir", default=VAL, help="куда писать отчёты и summary.json (по умолчанию validation/)")
    a = ap.parse_args()
    val_dir = os.path.abspath(a.out_dir)
    os.makedirs(val_dir, exist_ok=True)
    summary, reports = [], {}
    bad = 0
    for name, clip, extra, expect_exit, expect_warn in CASES:
        clip_abs = os.path.join(REPO, clip)
        if not os.path.exists(clip_abs):
            bad += 1
            summary.append({"case": name, "clip": clip, "result": "skipped_missing_input",
                            "expectation_met": False})
            print(name, "SKIPPED_MISSING_INPUT", clip)
            continue
        out = os.path.join(val_dir, name + ".validation.json")
        if os.path.exists(out):
            os.remove(out)  # не читать устаревший отчёт, если Blender упадёт
        cmd = [a.blender, "-b", "--factory-startup", "--python", SCRIPT, "--", clip_abs, *extra, "--out=" + out]
        p = subprocess.run(cmd, cwd=REPO, capture_output=True, text=True, encoding="utf-8", errors="replace")
        line = next((l for l in p.stdout.splitlines() if l.startswith("CLIP_VALIDATION")), "")
        if not os.path.exists(out):
            bad += 1
            summary.append({"case": name, "clip": clip, "exit": p.returncode, "result": "no_report",
                            "expectation_met": False})
            print(name, p.returncode, "NO_REPORT")
            continue
        with open(out, encoding="utf-8") as f:
            rep = json.load(f)
        reports[name] = rep
        missing_warn = [w for w in expect_warn if w not in rep.get("warnings", [])]
        ok_expect = p.returncode == expect_exit and not missing_warn
        bad += 0 if ok_expect else 1
        summary.append({"case": name, "clip": clip, "exit": p.returncode, "result": rep["result"],
                        "fails": rep["fails"], "warnings": rep.get("warnings", []),
                        "expected_exit": expect_exit, "expected_warnings": expect_warn,
                        "expectation_met": ok_expect,
                        "fps": rep.get("fps"), "duration_s": rep.get("duration_s"),
                        "reference_height": rep.get("reference_height")})
        print(name, p.returncode, line)
    cross = glb_cross_check(reports)
    bad += 0 if cross["result"] == "pass" else 1
    print("GLB_CROSS_CHECK", cross["result"].upper(), "height_rel_diff", cross.get("height_rel_diff"),
          "peak_rel_diff", cross.get("peak_rel_diff"))
    with open(os.path.join(val_dir, "summary.json"), "w", encoding="utf-8") as f:
        json.dump({"schema": "unmatched.clip-validation-summary/1", "cases": summary,
                   "glb_cross_check": cross, "result": "pass" if bad == 0 else "fail"},
                  f, ensure_ascii=False, indent=1)
        f.write("\n")
    print("SUMMARY", "OK" if bad == 0 else f"FAIL: {bad} case(s) not run or expectation not met")
    return 0 if bad == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
