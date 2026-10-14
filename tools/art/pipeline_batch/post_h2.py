"""Этап 2 (Tripo H2) после выгрузки GLB одного героя: source-spec, register-source, превью draft_orthos, отчёт tripo-run.json с рамками частей по вершинам (F10).

tripo3d-stages.md §6 п.7–10. Ждёт в <run>/source/ два файла Studio, уже перенесённых из Downloads:
`<ck>-h2-tripo-<task8>-parts<N>.glb` (по частям, без текстуры) и `<ck>-h2-tripo-<task8>-tex8k-pbr.glb` (8K + PBR).
Пишет source-specs/tripo-<task8>-h2.json, регистрирует его (tripo_pipeline.py register-source), рендерит превью
(tools/art/concept/draft_orthos.py), пишет reports/tripo-run.json (claims все false) с рамками частей для профиля
этапа 3. Строки журнала трат пишет вызывающий (сразу после клика, §6 п.6). Был C:/tmp/concept-wave/post_h2.py.

    python tools/art/pipeline_batch/post_h2.py <content-key> <task_uuid> --gen <до> <после> --tex <до> <после> \
        --pbr <до> <после> [--tex-quoted 30] [--gen-quoted 60] [--pbr-quoted 5] [--date YYYYMMDD] [--dry-run]

--dry-run: проверить файлы, посчитать рамки частей и напечатать сводку; ничего не писать и не запускать.
Код выхода: 0 — готово, 1 — register-source или превью вернули ошибку, 2 — ошибка входа.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _batch as b  # noqa: E402

SETTINGS = {"output": "геометрия без текстуры (текстура — отдельным шагом 8K)", "generate_parts": True,
            "parts_mode": "Баланс (Balanced)", "ultra_mesh_quality": True, "polygon_count": 2000000,
            "texture_8k": True, "remove_lighting": True, "pbr": True, "privacy": True, "topology": "Треугольник",
            "ai_completion": None, "seed": None,
            "settings_note": "texture_8k/remove_lighting/pbr — последующие шаги генератора текстур и PBR на той же "
                             "задаче, не настройки генерации геометрии"}


def operations(a, evidence: str) -> list:
    def op(name, mode, quoted, ba):
        return {"op": name, "mode": mode, "history_time": None, "evidence": evidence,
                "credits": {"unit": "studio-credits", "quoted": quoted, "observed_debit": ba[0] - ba[1],
                            "balance_before": ba[0], "balance_after": ba[1]}}
    return [op("generate", "HD модель, из нескольких видов, H3.1 Макс.кач., по частям (Баланс), ультра-сетка 2M, "
                           "треугольники, без текстуры", a.gen_quoted, a.gen),
            op("texture", "Генератор текстур 8K, Удалить освещение, по видам задачи, на high-poly модели по частям",
               a.tex_quoted, a.tex),
            op("pbr", "Генератор PBR после 8K", a.pbr_quoted, a.pbr)]


def main(argv=None) -> int:
    b.utf8_streams()
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0],
                                 formatter_class=argparse.RawDescriptionHelpFormatter, epilog=__doc__)
    ap.add_argument("key", help="content-key (kebab), префикс файлов")
    ap.add_argument("task", help="task uuid Studio")
    for flag in ("--gen", "--tex", "--pbr"):
        ap.add_argument(flag, nargs=2, type=float, required=True, metavar=("BEFORE", "AFTER"),
                        help="баланс кредитов до и после операции")
    ap.add_argument("--gen-quoted", type=float, default=60)
    ap.add_argument("--tex-quoted", type=float, default=30)
    ap.add_argument("--pbr-quoted", type=float, default=5)
    ap.add_argument("--date", default=dt.date.today().strftime("%Y%m%d"), help="дата прогона YYYYMMDD (<date>-h2-tripo)")
    ap.add_argument("--asset-id", default=None, help="по умолчанию ASSET-<KEY>-001")
    ap.add_argument("--settings-before", default="форма стояла на H2-настройках (по частям Баланс, без текстуры, "
                                                  "ультра 2M, 8K выкл., Приватный)")
    ap.add_argument("--settings-after", default="не менялись: форма остаётся на H2-настройках для следующих героев")
    ap.add_argument("--repo", default=str(b.REPO))
    ap.add_argument("--dry-run", action="store_true")
    try:
        a = ap.parse_args(argv)
    except SystemExit as exc:
        return int(exc.code or 0)
    repo = Path(a.repo)
    try:
        k, task, t8 = a.key, a.task, a.task[:8]
        aid = a.asset_id or b.asset_id(k)
        A = repo / "art/pipeline-candidates" / aid
        card = (A / "asset-card.yaml").read_text(encoding="utf-8")
        side = b.scalar(card, "SIDE_VIEW") or "left"
        winged = b.scalar(card, "ANATOMY") == "winged-biped"
        run_dir = A / f"{a.date}-h2-tripo"
        src = run_dir / "source"
        parts_l = sorted(src.glob(f"{k}-h2-tripo-{t8}-parts*.glb"))
        tex = src / f"{k}-h2-tripo-{t8}-tex8k-pbr.glb"
        if len(parts_l) != 1 or not tex.is_file():
            raise ValueError(f"в {src} нужен один {k}-h2-tripo-{t8}-parts*.glb и {tex.name} (найдено {len(parts_l)})")
        parts = parts_l[0]
        C = repo / f"art/imagegen/concept-{k}-codex"
        views = {"front": C / f"{k}-front.png", side: C / f"{k}-side.png", "back": C / f"{k}-back.png"}
        gviews = {s: ({"path": b.rel(views[s], repo), "sha256": b.sha256(views[s])} if s in views else None)
                  for s in ("front", "left", "right", "back")}
        boxes = b.part_boxes(parts.read_bytes())
    except (OSError, ValueError, KeyError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    gp, gt = b.inspect_glb(parts), b.inspect_glb(tex)
    if a.dry_run:
        print(json.dumps({"dry_run": True, "asset_id": aid, "parts_glb": b.rel(parts, repo), "tex_glb": b.rel(tex, repo),
                          "mesh_count": [gp["mesh_count"], gt["mesh_count"]], "triangles": [gp["triangles"], gt["triangles"]],
                          "parts": boxes}, ensure_ascii=False, indent=1))
        return 0
    rep_rel = b.rel(run_dir, repo) + "/reports/tripo-run.json"
    url = f"https://studio.tripo3d.ai/ru/workspace/generate/{task}"
    date_iso = f"{a.date[:4]}-{a.date[4:6]}-{a.date[6:]}"
    ops = operations(a, rep_rel)
    slot_note = (f"Боковой вид этапа 1c нарисован поверх ortho_{side} (SIDE_VIEW: {side} в карточке), подан в слот "
                 f"{side.upper()}: согласовано (tripo3d-stages.md §5.5); второй боковой слот пуст.")
    files = [
        {"role": "h2-parts-glb", "path": b.rel(parts, repo), "expected_sha256": b.sha256(parts),
         "expected_bytes": parts.stat().st_size, "produced_by": "generate",
         "origin": "Studio GLB export, high-poly по частям без текстуры, unmodified", "in_git": False},
        {"role": "h2-tex8k-pbr-glb", "path": b.rel(tex, repo), "expected_sha256": b.sha256(tex),
         "expected_bytes": tex.stat().st_size, "produced_by": "pbr",
         "origin": "Studio GLB export после текстуры 8K (Удалить освещение) и PBR, unmodified", "in_git": False}]

    def expect(g):
        return {"glb_mesh_count": g["mesh_count"], "glb_triangles": g["triangles"], "glb_materials": g["materials"],
                "glb_images": g["images"], "glb_skins": g["skins"], "armatures": 0}

    spec = {
        "schema": "unmatched.tripo-pipeline.source-spec/1", "source_id": f"tripo-{t8}-h2", "asset_id": aid,
        "service": "tripo-studio", "task_id": task, "parent_task_id": None, "task_url": url, "date": date_iso,
        "iteration": "этап 2 3d-model-pipeline: H2 по видам этапа 1c",
        "model_version": {"ui_label": "H3.1 - Макс.кач.", "backend": None, "note": "подпись UI формы"},
        "generation": {"mode": "multi-view", "views": gviews, "input_manifest": None,
                       "concept_prompts": b.rel(C / "prompts.md", repo) if (C / "prompts.md").exists() else None,
                       "slot_note": slot_note, "settings": SETTINGS},
        "operations": ops, "files": files,
        "git_policy": "Сырые GLB не коммитятся (.gitignore ассета *-tripo/source/*.glb); восстанавливаются выгрузкой из "
                      "Studio по task_url и проверяются по expected_sha256/expected_bytes",
        "expectations": {"h2-parts-glb": expect(gp), "h2-tex8k-pbr-glb": expect(gt)},
        "evidence": [rep_rel, "docs/game-design/visual/credits-ledger.json"],
    }
    (A / "source-specs").mkdir(exist_ok=True)
    sp = A / f"source-specs/tripo-{t8}-h2.json"
    sp.write_text(json.dumps(spec, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (run_dir / "reports").mkdir(exist_ok=True)
    if not (run_dir / "reports/tripo-run.json").exists():
        (run_dir / "reports/tripo-run.json").write_text("{}", encoding="utf-8")
    reg = b.run([sys.executable, "tools/tripo-pipeline/tripo_pipeline.py", "register-source", "--run-dir",
                 b.rel(run_dir, repo) + "/generation-request", "--spec", b.rel(sp, repo)], repo)
    prev = b.run([sys.executable, "tools/art/concept/draft_orthos.py", "--glb", b.rel(tex, repo), "--out",
                  b.rel(run_dir, repo) + "/preview", "--views", "front,left,back,right",
                  "--aspect", "4:3" if winged else "3:4"], repo)
    total = sum(o["credits"]["observed_debit"] for o in ops)
    report = {
        "schema": "unmatched.tripo-pipeline.studio-run-evidence/1", "task": b.scalar(card, "VISUAL_CARD_ID"),
        "asset_id": aid, "date": date_iso, "service": "tripo-studio",
        "performed_by": "запускающий агент (оркестратор 3d-model-pipeline) в браузере пользователя через Windows-MCP: "
                        "клики формы, цены с кнопки, балансы с шапки Studio, экспорт GLB в Downloads и перенос в source/",
        "tasks": [{"task_id": task, "task_url": url}],
        "generation": {"mode": "multi-view", "ui": "HD модель, из нескольких видов, H3.1 Макс.кач.",
                       "model_ui_label": "H3.1 - Макс.кач.", "views": gviews,
                       "slot_mapping": f"FRONT=front, {side.upper()}=side, BACK=back, "
                                       f"{'RIGHT' if side == 'left' else 'LEFT'} пуст",
                       "slot_consistency": slot_note, "settings": SETTINGS,
                       "studio_settings_before": a.settings_before, "studio_settings_after": a.settings_after},
        "operations": ops,
        "exports": [{"file": f["path"], "stage": f["produced_by"], "format": "GLB", "sha256": f["expected_sha256"],
                     "bytes": f["expected_bytes"], "container": "OK" if b.container_ok((repo / f["path"]).read_bytes())
                     else "FAIL", **(gp if f["role"] == "h2-parts-glb" else gt)} for f in files],
        "parts_vs_textured": {"meshes_equal": gp["mesh_count"] == gt["mesh_count"],
                              "tris_equal": gp["triangles"] == gt["triangles"]},
        "parts": boxes, "parts_note": "рамки по вершинам (accessor min/max Tripo не годится: DBL_MIN, F10)",
        "register_source": {"exit": reg.returncode, "out": (reg.stdout + reg.stderr).strip()[-400:]},
        "preview": {"exit": prev.returncode, "dir": b.rel(run_dir, repo) + "/preview",
                    "out": (prev.stdout + prev.stderr).strip()[-300:]},
        "findings": [],
        "credits": {"unit": "studio-credits", "this_hero_total_observed": total,
                    "ledger": "docs/game-design/visual/credits-ledger.json"},
        "claims": {"art_accepted": False, "game_ready": False, "budgets_declared": False},
    }
    (run_dir / "reports/tripo-run.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n",
                                                    encoding="utf-8")
    print(k, "parts", gp["mesh_count"], "tris", gp["triangles"], "==" if report["parts_vs_textured"]["tris_equal"]
          else "!=", "register", reg.returncode, (reg.stdout + reg.stderr).strip()[-160:], "| preview", prev.returncode,
          "| total", total)
    return 0 if reg.returncode == 0 and prev.returncode == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
