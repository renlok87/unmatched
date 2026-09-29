"""Прогон H2Anim одного героя (волна 5c): авторинг -> validate_clip v2 -> контакты -> контактный лист Blender.

    python tools/tripo-pipeline/anim/h2anim_run.py <spec.json> [--clips=Idle,LungeAttack] [--no-author] [--no-probe]

Системный Python; Blender запускается только headless (`-b --factory-startup`), по одному процессу за раз,
процесс завершается сам (os._exit) — фоновых процессов не остаётся. Шаги на клип:
  1. anim/clip_author.py — FBX клипа в <run>/export и reports/author-<Clip>.json (sha цели сверяется со спекой;
     при несовпадении — код 3, клип не пишется: цель изменилась, перезапечь по новой спеке);
  2. anim/validate_clip.py --skeleton=UM_HUMANOID_17_v2 --character=<Hero> --clip-role --expect-fps 24
     --expect-duration N/24 --root-policy in_place --min-pose-change 0.02 [--loop true] ->
     docs/art-pipeline/animation-library/validation-h2anim/AM_<Hero>_<Clip>.validation.json;
  3. anim/clip_contact_check.py -> reports/contact-<Clip>.json;
  4. anim/clip_pose_probe.py (кадры key_frames спеки, виды front/left/q34) + overlay_bones.py ->
     preview/<Hero>-<Clip>-blender-sheet.jpg (покадровые PNG удаляются, 2D-кости в preview/frames/*.json).
Итог — reports/h2anim-run.json (коды выхода и вердикты). Код выхода 0 только если всё PASS.
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
    return jpg.relative_to(REPO).as_posix()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("spec")
    ap.add_argument("--clips")
    ap.add_argument("--no-author", action="store_true")
    ap.add_argument("--no-probe", action="store_true")
    a = ap.parse_args()
    spec_path = Path(a.spec).resolve()
    spec = json.loads(spec_path.read_text(encoding="utf-8"))
    run = REPO / spec["run_dir"]
    (run / "reports").mkdir(parents=True, exist_ok=True)
    (run / "preview").mkdir(parents=True, exist_ok=True)
    VAL_DIR.mkdir(parents=True, exist_ok=True)
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
        val_out = VAL_DIR / (stem + ".validation.json")
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
                              "warnings": vrep.get("warnings"), "report": val_out.relative_to(REPO).as_posix()},
                 "contact": {"code": c["code"], "result": crep.get("result"), "fails": crep.get("fails"),
                             "report": c_out.relative_to(REPO).as_posix(),
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
                        "--base=" + str(REPO / spec["target"]["base_fbx"]), "--res=420")
            ov = subprocess.run([sys.executable, str(HERE / "overlay_bones.py"), str(run / "preview" / "frames"),
                                 "%s-%s" % (spec["ue_hero"], name)], capture_output=True, text=True,
                                creationflags=NO_WINDOW)
            entry["probe"] = {"code": p["code"], "overlay_code": ov.returncode,
                              "sheet": compact_sheet(run, "%s-%s" % (spec["ue_hero"], name))}
        elif (summary["clips"].get(name) or {}).get("probe"):
            entry["probe"] = summary["clips"][name]["probe"]  # --no-probe: лист прошлого прогона
        ok = vrep.get("result") == "pass" and crep.get("result") == "pass"
        entry["passed"] = ok
        ok_all &= ok
        summary["clips"][name] = entry
    summary["spec"] = spec_path.relative_to(REPO).as_posix()
    out_path.write_text(json.dumps(summary, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    sys.exit(0 if ok_all else 1)


if __name__ == "__main__":
    main()
