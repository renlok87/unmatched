"""Прогон H2Anim одного героя (волна 5c): авторинг -> validate_clip v2 -> контакты -> контактный лист Blender.

    python tools/tripo-pipeline/anim/h2anim_run.py <spec.json> [--clips=Idle,LungeAttack] [--no-author] [--no-probe]
        [--out-dir <каталог отчётов validate>]

Системный Python; Blender запускается только headless (`-b --factory-startup`), по одному процессу за раз,
процесс завершается сам (os._exit) — фоновых процессов не остаётся. Шаги на клип:
  1. anim/clip_author.py — FBX клипа в <run>/export и reports/author-<Clip>.json (sha цели сверяется со спекой;
     при несовпадении — код 3, клип не пишется: цель изменилась, перезапечь по новой спеке);
  2. anim/validate_clip.py --skeleton=UM_HUMANOID_17_v2 --character=<Hero> --clip-role --expect-fps 24
     --expect-duration N/24 --root-policy in_place --min-pose-change 0.02 [--loop true] ->
     <out-dir>/AM_<Hero>_<Clip>.validation.json (по умолчанию docs/art-pipeline/animation-library/validation-h2anim —
     отчёт гейта G-VALIDATE настоящих клипов);
  3. anim/clip_contact_check.py -> reports/contact-<Clip>.json;
  4. anim/clip_pose_probe.py (кадры key_frames спеки, виды front/left/q34) + overlay_bones.py ->
     preview/<Hero>-<Clip>-blender-sheet.jpg (покадровые PNG удаляются, 2D-кости в preview/frames/*.json).
Итог — reports/h2anim-run.json (коды выхода и вердикты). Код выхода 0 только если всё PASS.

Пути (ревью 2026-10-14, R-13): спека, run_dir (относительный — от корня репозитория, абсолютный — как есть), цели спеки
и --out-dir могут лежать вне репозитория; пути в отчётах — от корня репозитория, вне его — абсолютные. Дымовой прогон
этапа 3 (animation-vfx-sfx.md §6.6) кладёт всё в <bake run>/work/smoke/: --out-dir <bake run>/work/smoke/validation,
отчёты validate настоящих клипов в docs/ не трогаются.

Спека дыма — ключ `"smoke": true` (C28, 2026-10-14): цели образца (`weapon_tip` острия, `hand_follow`) привязаны к его
пропорциям и на другом герое не сходятся, поэтому в вердикт дыма не входят — clip_contact_check ставит weapon_tip
info (status_without_smoke), а здесь у клипа блок `smoke` с этим статусом и недотянутыми кадрами hand_follow из журнала
автора. Без --out-dir отчёты validate дыма ложатся в <run_dir>/../validation (по раскладке §6.6 это
<bake run>/work/smoke/validation), а не в docs/.
"""
import argparse
import json
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
BLENDER = "C:/Program Files/Blender Foundation/Blender 5.2/blender.exe"
VAL_DIR = REPO / "docs/art-pipeline/animation-library/validation-h2anim"
NO_WINDOW = 0x08000000 if sys.platform == "win32" else 0


def rel(path):
    """Путь для отчёта: от корня репозитория, вне его — абсолютный (R-13: спека и прогон могут лежать вне репозитория)."""
    p = Path(path).resolve()
    try:
        return p.relative_to(Path(REPO).resolve()).as_posix()
    except ValueError:
        return p.as_posix()


def blender(script, *args, timeout=1800):
    cmd = [BLENDER, "-b", "--factory-startup", "--python", str(HERE / script), "--"] + [str(a) for a in args]
    t0 = time.time()
    p = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=timeout,
                       creationflags=NO_WINDOW)
    tail = [ln for ln in p.stdout.splitlines() if ln.startswith(("CLIP_", "Traceback", "  File", "RuntimeError",
                                                                    "KeyError", "ValueError", "AttributeError",
                                                                    "TypeError", "NameError"))]
    return {"code": p.returncode, "seconds": round(time.time() - t0, 1), "lines": tail[-12:]}


def compact_sheet(run, label):
    """Лист PNG -> preview/<label>-blender-sheet.jpg (качество 88); покадровые PNG удаляются (пересоздаются
    clip_pose_probe.py), bones2d/probe JSON остаются. Возвращает путь листа относительно репозитория."""
    from PIL import Image
    frames = run / "preview" / "frames"
    png = frames / ("%s-sheet.png" % label)
    jpg = run / "preview" / ("%s-blender-sheet.jpg" % label)
    if png.exists():
        Image.open(png).convert("RGB").save(jpg, quality=88, optimize=True)
        png.unlink()
    for f in frames.glob("%s-f*.png" % label):
        f.unlink()
    return rel(jpg)


def smoke_entry(crep, arep):
    """Блок `smoke` клипа (C28): что исключено из вердикта дыма и замеры этих целей образца — статус weapon_tip без
    дыма (contact) и hand_follow из журнала автора: кадры, где IK руки не дотянулась, и наибольший дефицит досягаемости
    по стороне (follow_<S>_reach_deficit_cm > 0 — цель дальше вытянутой руки)."""
    tip = next((k for k in (crep or {}).get("checks", []) if k.get("check") == "weapon_tip"), {})
    unreached, deficit = [], {}
    for row in (arep or {}).get("ik_log") or []:
        for k, v in row.items():
            if k.startswith("follow_") and k[len("follow_"):] in ("L", "R") and v is False:
                unreached.append(row["f"])
            if k.startswith("follow_") and k.endswith("_reach_deficit_cm") and v is not None:
                s = k[len("follow_"):-len("_reach_deficit_cm")]
                deficit[s] = max(deficit.get(s, v), v)
    return {"excluded_from_verdict": ["weapon_tip", "hand_follow"],
            "weapon_tip_without_smoke": tip.get("status_without_smoke", tip.get("status")),
            "hand_follow": {"configured": bool((arep or {}).get("hand_follow")),
                            "unreached_frames": sorted(set(unreached)),
                            "max_reach_deficit_cm": deficit},
            "note": "цели образца привязаны к его пропорциям (C28): замер для отчёта сдачи модели, не вердикт"}


def main():
    for stream in (sys.stdout, sys.stderr):  # RB-11/F47: «×» of the contact checks in a cp1251 pipe (agents' Bash)
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="backslashreplace")
    ap = argparse.ArgumentParser()
    ap.add_argument("spec")
    ap.add_argument("--clips")
    ap.add_argument("--no-author", action="store_true")
    ap.add_argument("--no-probe", action="store_true")
    ap.add_argument("--out-dir", "--val-dir", dest="out_dir", default=None,
                    help="каталог отчётов validate AM_<Hero>_<Clip>.validation.json (по умолчанию "
                         "docs/art-pipeline/animation-library/validation-h2anim; дымовой прогон — свой каталог)")
    a = ap.parse_args()
    spec_path = Path(a.spec).resolve()
    spec = json.loads(spec_path.read_text(encoding="utf-8"))
    run = Path(REPO) / spec["run_dir"]       # абсолютный run_dir — как есть
    (run / "reports").mkdir(parents=True, exist_ok=True)
    (run / "preview").mkdir(parents=True, exist_ok=True)
    smoke = bool(spec.get("smoke", False))  # спека дыма §6.6 (C28)
    if a.out_dir:
        val_dir = Path(a.out_dir).resolve()
    else:
        val_dir = run.resolve().parent / "validation" if smoke else VAL_DIR  # дым не пишет в docs/
    val_dir.mkdir(parents=True, exist_ok=True)
    clips = a.clips.split(",") if a.clips else list(spec["clips"])
    out_path = run / "reports" / "h2anim-run.json"
    summary = json.loads(out_path.read_text(encoding="utf-8")) if out_path.exists() else {"clips": {}}
    ok_all = True
    if not a.no_author:
        res = blender("clip_author.py", spec_path, "--clips=" + ",".join(clips))
        print("author", res["code"], *res["lines"], sep="\n  ")
        summary["author"] = res
        if res["code"] != 0:
            ok_all = False
            if res["code"] in (2, 3):
                out_path.write_text(json.dumps(summary, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
                sys.exit(res["code"])
    for name in clips:
        clip = spec["clips"][name]
        n = int(clip["frames"])
        fbx = run / "export" / ("AM_%s_%s.fbx" % (spec["ue_hero"], name))
        stem = "AM_%s_%s" % (spec["ue_hero"], name)
        val_out = val_dir / (stem + ".validation.json")
        vargs = [fbx, "--skeleton=UM_HUMANOID_17_v2", "--character=" + spec["character"],
                 "--clip-role=" + clip["role"], "--expect-fps=24", "--expect-duration=%.4f" % (n / 24.0),
                 "--root-policy=in_place", "--min-pose-change=0.02", "--out=" + str(val_out)]
        if clip["role"] == "idle":
            vargs.append("--loop=true")
        v = blender("validate_clip.py", *vargs)
        vrep = json.loads(val_out.read_text(encoding="utf-8")) if val_out.exists() else {}
        c_out = run / "reports" / ("contact-%s.json" % name)
        c = blender("clip_contact_check.py", fbx, "--spec=" + str(spec_path), "--clip=" + name, "--out=" + str(c_out))
        crep = json.loads(c_out.read_text(encoding="utf-8")) if c_out.exists() else {}
        entry = {"validate": {"code": v["code"], "result": vrep.get("result"), "fails": vrep.get("fails"),
                              "warnings": vrep.get("warnings"), "report": rel(val_out)},
                 "contact": {"code": c["code"], "result": crep.get("result"), "fails": crep.get("fails"),
                             "report": rel(c_out),
                             "summary": {k["check"]: {kk: vv for kk, vv in k.items() if kk not in ("check",)}
                                         for k in crep.get("checks", [])}}}
        vpc = next((x for x in vrep.get("checks", []) if x["check"] == "visible_pose_change"), {})
        entry["validate"]["peak_joint_shift_of_height"] = vpc.get("peak_max_joint_shift_of_height")
        print(name, "validate", vrep.get("result"), vrep.get("fails"), vrep.get("warnings"),
              "peak", vpc.get("peak_max_joint_shift_of_height"), "| contact", crep.get("result"), crep.get("fails"))
        if c["code"] == 2 or v["code"] == 2:
            print("  ", *(v["lines"] + c["lines"]), sep="\n  ")
        for chk in crep.get("checks", []):
            if chk["status"] in ("fail", "warn"):
                print("   ", chk["status"].upper(), chk)
        if not a.no_probe:
            frames = ",".join(str(f) for f in clip.get("key_frames", [0, n // 2, n]))
            p = blender("clip_pose_probe.py", fbx, run / "preview" / "frames", "%s-%s" % (spec["ue_hero"], name),
                        "--frames=" + frames, "--views=" + clip.get("views", "front,left,q34"),
                        "--base=" + str(Path(REPO) / spec["target"]["base_fbx"]), "--res=420")
            ov = subprocess.run([sys.executable, str(HERE / "overlay_bones.py"), str(run / "preview" / "frames"),
                                 "%s-%s" % (spec["ue_hero"], name)], capture_output=True, text=True,
                                creationflags=NO_WINDOW)
            entry["probe"] = {"code": p["code"], "overlay_code": ov.returncode,
                              "sheet": compact_sheet(run, "%s-%s" % (spec["ue_hero"], name))}
        elif (summary["clips"].get(name) or {}).get("probe"):
            entry["probe"] = summary["clips"][name]["probe"]  # --no-probe: лист прошлого прогона
        if smoke:
            ap_ = run / "reports" / ("author-%s.json" % name)
            arep = json.loads(ap_.read_text(encoding="utf-8")) if ap_.exists() else {}
            entry["smoke"] = smoke_entry(crep, arep)
            print("    smoke (вне вердикта): weapon_tip", entry["smoke"]["weapon_tip_without_smoke"],
                  "| hand_follow unreached", entry["smoke"]["hand_follow"]["unreached_frames"][:8])
        ok = vrep.get("result") == "pass" and crep.get("result") == "pass"
        entry["passed"] = ok
        ok_all &= ok
        summary["clips"][name] = entry
    summary["spec"] = rel(spec_path)
    summary["validation_dir"] = rel(val_dir)
    if smoke:
        summary["smoke"] = True
    out_path.write_text(json.dumps(summary, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    sys.exit(0 if ok_all else 1)


if __name__ == "__main__":
    main()
