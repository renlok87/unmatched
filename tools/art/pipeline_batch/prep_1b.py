"""Добор этапа 0 и подготовка 1b (tripo3d-stages.md §5.2, §6 п.2–4) для каждой фигуры с принятым дизайн-фронтом 1a; очередь Tripo пачки.

Фронт принят: решение пользователя (evidence/acceptance-concept/*/user-decision.json), пара приёмщиков pass
(final.json) или одна карточка pass с баллом ≥ 8,5. Для каждой такой фигуры (не ANATOMY non-humanoid):
строка карточки anim.csv (следующий свободный AN-NN, area hero; уже есть по заголовку — берётся она), недостающие поля
asset-card.yaml (POLY_BUDGET, CREDITS, VISUAL_CARD_ID; остальные не трогаются), generation-request init, проверка
дубликата фронта по sha256 в source-specs, prepare-generation --dry-run. Пишет очередь <queue-out> (порядок: герои,
потом помощники, по ключу). Идемпотентно. Был C:/tmp/concept-wave/prep_1b.py.

    python tools/art/pipeline_batch/prep_1b.py --queue-out <work>/tripo-queue.json [--date YYYYMMDD] [--only key,…]
        [--tripo-limit-note "…"] [--dry-run]

--dry-run: только решить, кто готов, и напечатать план (anim.csv, карточки и generation-request не трогаются).
Код выхода: 0 — готово, 2 — ошибка входа.
"""
from __future__ import annotations

import argparse
import csv
import datetime as dt
import hashlib
import io
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _batch as b  # noqa: E402

TRIPO = [sys.executable, "tools/tripo-pipeline/tripo_pipeline.py"]


def accepted(acc_dir: Path) -> str | None:
    """Почему фронт 1a принят: user-decision | pair-pass | pass (≥ 8,5); иначе None."""
    if list(acc_dir.glob("*/user-decision.json")):
        return "user-decision"
    cards = sorted(acc_dir.glob("*/card.json"))
    if not cards:
        return None
    ev = cards[-1].parent
    if (ev / "final.json").exists():
        f = json.loads((ev / "final.json").read_text(encoding="utf-8"))
        return "pair-pass" if f.get("verdict") == "pass" else None
    c = json.loads(cards[-1].read_text(encoding="utf-8"))
    return "pass" if c.get("verdict") == "pass" and (c.get("score") or 0) >= 8.5 else None


def next_an(rows: list) -> int:
    nums = [int(r[0][3:]) for r in rows[1:] if r and re.fullmatch(r"AN-\d+", r[0])]
    return (max(nums) if nums else 0) + 1


def card_additions(card: str, an: str, limit_note: str) -> list[str]:
    add = []
    if not re.search(r"^POLY_BUDGET:", card, re.M):
        add.append("POLY_BUDGET: {figure_tris_max: 45000, base_tris_max: 2500}")
    if not re.search(r"^CREDITS:", card, re.M):
        add += ["CREDITS:", '  ledger: "docs/game-design/visual/credits-ledger.json"',
                f'  tripo_limit: "{limit_note}"', '  planned: "черновик ≈ 30 + H2 95"']
    if not re.search(r"^VISUAL_CARD_ID:", card, re.M):
        add.append(f'VISUAL_CARD_ID: "{an}"')
    return add


def anim_row(header: list, an: str, key_name: str, role: str, aid: str, date: str, status: str) -> list:
    r = {h: "" for h in header}
    r.update({"id": an, "area": "hero", "title": f"{key_name}: черновая модель Tripo (этап 1b 3d-model-pipeline)",
              "priority": "P6", "purpose": f"Новая фигура {key_name} ({role}) из ростера БД: черновик Tripo по принятому "
                                           "дизайн-front этапа 1a.",
              "tool": "Tripo Studio H3.1", "template": "T-TRIPO-PART",
              "deliverable": f"art/pipeline-candidates/{aid}/{date}-draft-tripo/ (GLB, orthos/)",
              "budget": "≈ 30 studio-credits (черновик) + 95 (H2)",
              "acceptance": "references/tripo3d-stages.md §5.2; лист 1c и приёмка concept-sheet §11", "status": status})
    return [r.get(h, "") for h in header]


def main(argv=None) -> int:
    b.utf8_streams()
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0],
                                 formatter_class=argparse.RawDescriptionHelpFormatter, epilog=__doc__)
    ap.add_argument("--queue-out", required=True, help="очередь Tripo пачки (JSON)")
    ap.add_argument("--date", default=dt.date.today().strftime("%Y%m%d"), help="дата прогона черновика YYYYMMDD")
    ap.add_argument("--only", default=None, help="content-key через запятую")
    ap.add_argument("--status", default="в работе (пакетный режим 3d-model-pipeline)", help="статус новых строк anim.csv")
    ap.add_argument("--tripo-limit-note", default="см. журнал трат (ledger.py check)", help="CREDITS.tripo_limit заявки")
    ap.add_argument("--repo", default=str(b.REPO))
    ap.add_argument("--dry-run", action="store_true")
    try:
        a = ap.parse_args(argv)
    except SystemExit as exc:
        return int(exc.code or 0)
    repo = Path(a.repo)
    only = {x.strip() for x in a.only.split(",")} if a.only else None
    anim = repo / "docs/game-design/visual/06-tasks/anim.csv"
    try:
        rows = list(csv.reader(io.StringIO(anim.read_text(encoding="utf-8"))))
    except OSError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    header, nxt = rows[0], next_an(rows)
    titles = {r[2]: r[0] for r in rows[1:] if len(r) > 2}
    new_rows, queue = [], []
    keys = sorted(p.name[len("concept-"):-len("-codex")] for p in repo.glob("art/imagegen/concept-*-codex"))
    for k in keys:
        if only and k not in only:
            continue
        aid = b.asset_id(k)
        adir = repo / f"art/pipeline-candidates/{aid}"
        why = accepted(adir / "evidence/acceptance-concept")
        front = repo / f"art/imagegen/concept-{k}-codex/design/{k}-front.png"
        if not why or not front.exists() or not (adir / "asset-card.yaml").is_file():
            continue
        card = (adir / "asset-card.yaml").read_text(encoding="utf-8")
        if re.search(r"^ANATOMY: non-humanoid", card, re.M):
            continue
        key_name, role = b.scalar(card, "KEY"), b.scalar(card, "GAME_ROLE")
        title = f"{key_name}: черновая модель Tripo (этап 1b 3d-model-pipeline)"
        an = titles.get(title)
        if not an:
            an = f"AN-{nxt:02d}"
            nxt += 1
            new_rows.append(anim_row(header, an, key_name, role, aid, a.date, a.status))
            titles[title] = an
        run_dir = f"art/pipeline-candidates/{aid}/{a.date}-draft-tripo"
        gr = f"{run_dir}/generation-request"
        rel_front = b.rel(front, repo)
        item = {"key": k, "asset_id": aid, "an": an, "role": role, "why": why, "run_dir": run_dir, "front": rel_front}
        if a.dry_run:
            item["card_additions"] = card_additions(card, an, a.tripo_limit_note)
            queue.append(item)
            continue
        add = card_additions(card, an, a.tripo_limit_note)
        if add:
            (adir / "asset-card.yaml").write_text(card.rstrip() + "\n" + "\n".join(add) + "\n", encoding="utf-8")
        if not (repo / gr / "manifest.json").exists():
            r = b.run(TRIPO + ["init", "--run-dir", gr, "--asset-id", aid, "--primary-source", "tripo-pending",
                               "--primary-role", "draft-glb"], repo)
            if r.returncode:
                print(k, "init FAIL", r.stdout[-300:], r.stderr[-300:])
                continue
        sha = hashlib.sha256(front.read_bytes()).hexdigest()
        dup = [b.rel(s, repo) for s in repo.glob("art/pipeline-candidates/*/source-specs/*.json")
               if sha in {(v or {}).get("sha256") for v in
                          ((json.loads(s.read_text(encoding="utf-8")).get("generation") or {}).get("views") or {}).values()}]
        if dup:
            print(k, "DUPLICATE", dup)
            continue
        if not list((repo / gr / "generation-requests").glob("*.json")):
            r = b.run(TRIPO + ["prepare-generation", "--run-dir", gr, "--dry-run", "--service", "tripo-studio", "--mode",
                               "single-image", "--model-label", "H3.1", "--view", f"front={rel_front}"], repo)
            if r.returncode:
                print(k, "prepare FAIL", r.returncode, r.stdout[-300:], r.stderr[-300:])
                continue
        queue.append(item)
    order = {"hero": 0, "sidekick": 1}
    queue.sort(key=lambda q: (order.get(q["role"], 2), q["key"]))
    if a.dry_run:
        print(json.dumps({"dry_run": True, "queue": queue, "new_anim_rows": [r[0] for r in new_rows]}, ensure_ascii=False,
                         indent=1))
        return 0
    if new_rows:
        buf = io.StringIO()
        csv.writer(buf, lineterminator="\n").writerows(new_rows)
        anim.write_text(anim.read_text(encoding="utf-8").rstrip("\n") + "\n" + buf.getvalue(), encoding="utf-8",
                        newline="")
    Path(a.queue_out).parent.mkdir(parents=True, exist_ok=True)
    Path(a.queue_out).write_text(json.dumps(queue, ensure_ascii=False, indent=1), encoding="utf-8")
    print("queue", len(queue), "new AN rows", len(new_rows), "→", a.queue_out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
