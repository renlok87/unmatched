"""Этап 1b после одного черновика Tripo Studio: перенос GLB, проверка контейнера, source-spec + register-source, tripo-run.json, ортопроекции draft_orthos.

tripo3d-stages.md §5.2 п.6–9, §6 п.7–8, 10. Переносит GLB в <run>/source/<ck>-draft-tripo-<task8>.glb, проверяет
контейнер glTF 2, пишет source-specs/tripo-<task8>-draft.json и регистрирует его, пишет reports/tripo-run.json,
рендерит орто (tools/art/concept/draft_orthos.py, аспект 4:3 у winged-biped). Строку журнала трат пишет вызывающий
сразу после клика (§6 п.6, tripo_log.py). Был C:/tmp/concept-wave/post_1b.py.

    python tools/art/pipeline_batch/post_1b.py <content-key> <task_uuid> <downloaded.glb> <balance_before> <balance_after> \
        [--quoted 30] [--date YYYYMMDD] [--dry-run]

--dry-run: проверить контейнер и напечатать план, ничего не переносить, не писать и не запускать.
Код выхода: 0 — готово, 1 — контейнер FAIL или register/орто с ошибкой, 2 — ошибка входа.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _batch as b  # noqa: E402


def draft_spec(*, aid: str, k: str, task: str, dst_rel: str, glb_sha: str, glb_bytes: int, g: dict, front_rel: str,
               front_sha: str, date_iso: str, quoted: float, before: float, after: float, report_rel: str) -> dict:
    t8 = task[:8]
    return {
        "schema": "unmatched.tripo-pipeline.source-spec/1", "source_id": f"tripo-{t8}-draft", "asset_id": aid,
        "service": "tripo-studio", "task_id": task, "parent_task_id": None,
        "task_url": f"https://studio.tripo3d.ai/ru/workspace/generate/{task}", "date": date_iso,
        "iteration": "этап 1b 3d-model-pipeline: черновик для ортопроекций",
        "model_version": {"ui_label": "H3.1 - Макс.кач.", "backend": None, "note": "подпись UI формы"},
        "generation": {
            "mode": "single-image",
            "views": {"front": {"path": front_rel, "sha256": front_sha}, "left": None, "right": None, "back": None},
            "input_manifest": None, "concept_prompts": f"art/imagegen/concept-{k}-codex/prompts.md",
            "slot_note": "черновик: один дизайн-front (tripo3d-stages.md §5.2)",
            "settings": {"output": "Геометрия и текстура (по умолчанию формы)", "generate_parts": False,
                         "parts_mode": None, "ultra_mesh_quality": None, "polygon_count": None, "texture_8k": False,
                         "remove_lighting": None, "pbr": False, "privacy": True, "topology": None,
                         "ai_completion": None, "seed": None,
                         "settings_note": "форма HD модель по умолчанию, по частям выкл., 8K выкл., Приватный"}},
        "operations": [{"op": "generate", "mode": "HD модель, одно изображение, H3.1 Макс.кач.", "history_time": None,
                        "evidence": report_rel,
                        "credits": {"unit": "studio-credits", "quoted": quoted, "observed_debit": before - after,
                                    "balance_before": before, "balance_after": after}}],
        "files": [{"role": "draft-glb", "path": dst_rel, "expected_sha256": glb_sha, "expected_bytes": glb_bytes,
                   "produced_by": "generate", "origin": "Studio GLB export, unmodified", "in_git": False}],
        "git_policy": "черновик не идёт в этап 3, GLB не коммитится (tripo3d-stages.md §5.2 п.10); восстанавливается по task_url",
        "expectations": {"draft-glb": {"glb_mesh_count": g["mesh_count"], "glb_triangles": g["triangles"],
                                       "glb_materials": g["materials"], "glb_images": g["images"], "glb_skins": g["skins"],
                                       "armatures": 0}},
        "evidence": [report_rel, "docs/game-design/visual/credits-ledger.json"],
    }


def main(argv=None) -> int:
    b.utf8_streams()
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0],
                                 formatter_class=argparse.RawDescriptionHelpFormatter, epilog=__doc__)
    ap.add_argument("key", help="content-key (kebab)")
    ap.add_argument("task", help="task uuid Studio")
    ap.add_argument("glb", help="выгруженный GLB (Downloads)")
    ap.add_argument("before", type=float, help="баланс кредитов до")
    ap.add_argument("after", type=float, help="баланс кредитов после")
    ap.add_argument("--quoted", type=float, default=30)
    ap.add_argument("--date", default=dt.date.today().strftime("%Y%m%d"))
    ap.add_argument("--repo", default=str(b.REPO))
    ap.add_argument("--dry-run", action="store_true")
    try:
        a = ap.parse_args(argv)
    except SystemExit as exc:
        return int(exc.code or 0)
    repo = Path(a.repo)
    try:
        k, task, t8 = a.key, a.task, a.task[:8]
        aid = b.asset_id(k)
        A = repo / f"art/pipeline-candidates/{aid}"
        card = (A / "asset-card.yaml").read_text(encoding="utf-8")
        aspect = "4:3" if b.scalar(card, "ANATOMY") == "winged-biped" else "3:4"
        run_dir = A / f"{a.date}-draft-tripo"
        dst = run_dir / "source" / f"{k}-draft-tripo-{t8}.glb"
        src = dst if dst.exists() else Path(a.glb)
        data = src.read_bytes()
        front = repo / f"art/imagegen/concept-{k}-codex/design/{k}-front.png"
        if not front.is_file():
            raise ValueError(f"нет принятого фронта {front}")
    except (OSError, ValueError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    ok = b.container_ok(data)
    if a.dry_run:
        print(json.dumps({"dry_run": True, "asset_id": aid, "glb": src.as_posix(), "dst": b.rel(dst.parent, repo) + "/"
                          + dst.name, "container": "OK" if ok else "FAIL", "bytes": len(data), "aspect": aspect},
                         ensure_ascii=False, indent=1))
        return 0 if ok else 1
    dst.parent.mkdir(parents=True, exist_ok=True)
    if not dst.exists():
        shutil.move(a.glb, dst)
    g = b.inspect_glb(dst)
    report_rel = b.rel(run_dir, repo) + "/reports/tripo-run.json"
    date_iso = f"{a.date[:4]}-{a.date[4:6]}-{a.date[6:]}"
    spec = draft_spec(aid=aid, k=k, task=task, dst_rel=b.rel(dst, repo), glb_sha=b.sha256(dst), glb_bytes=len(data), g=g,
                      front_rel=b.rel(front, repo), front_sha=b.sha256(front), date_iso=date_iso, quoted=a.quoted,
                      before=a.before, after=a.after, report_rel=report_rel)
    (A / "source-specs").mkdir(exist_ok=True)
    sp = A / f"source-specs/tripo-{t8}-draft.json"
    sp.write_text(json.dumps(spec, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (run_dir / "reports").mkdir(exist_ok=True)
    if not (run_dir / "reports/tripo-run.json").exists():
        (run_dir / "reports/tripo-run.json").write_text("{}", encoding="utf-8")
    reg = b.run([sys.executable, "tools/tripo-pipeline/tripo_pipeline.py", "register-source", "--run-dir",
                 b.rel(run_dir, repo) + "/generation-request", "--spec", b.rel(sp, repo)], repo)
    report = {
        "asset_id": aid, "stage": "1b draft", "task_id": task, "task_url": spec["task_url"], "date": date_iso,
        "studio_settings_before": {"tab": "Модель → HD модель", "input": "одно изображение",
                                   "general": "Геометрия и текстура", "generate_parts": False, "texture_8k": False,
                                   "privacy": "Приватный", "model": "H3.1 - Макс.кач."},
        "studio_settings_after": "не менялись (форма по умолчанию совпадает со скиллом)",
        "price_on_button": a.quoted, "balance_before": a.before, "balance_after": a.after,
        "glb": {"path": b.rel(dst, repo), "sha256": spec["files"][0]["expected_sha256"], "bytes": len(data),
                "container": "OK" if ok else "FAIL", **g},
        "register_source": {"exit": reg.returncode, "out": (reg.stdout + reg.stderr).strip()[-400:]},
        "findings": [],
    }
    o = b.run([sys.executable, "tools/art/concept/draft_orthos.py", "--glb", b.rel(dst, repo), "--out",
               b.rel(run_dir, repo) + "/orthos", "--views", "front,left,back,right", "--aspect", aspect], repo)
    report["orthos"] = {"exit": o.returncode, "dir": b.rel(run_dir, repo) + "/orthos",
                        "out": (o.stdout + o.stderr).strip()[-400:]}
    (run_dir / "reports/tripo-run.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n",
                                                    encoding="utf-8")
    print(k, "container", "OK" if ok else "FAIL", "tris", g["triangles"], "register", reg.returncode, "orthos",
          o.returncode, (o.stdout + o.stderr).strip()[-200:] if o.returncode else "")
    return 0 if ok and reg.returncode == 0 and o.returncode == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
