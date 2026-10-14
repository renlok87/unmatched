"""Этап 0 (поля этапа 1 asset-card.yaml, palette.json) и файлы заданий Codex 1a для пачки фигур из файла ростера.

concept-sheet.md §5.4, §6.1, §6.2, §9: шаблоны B-CONCEPT-PACKAGE, файл задания 1a и ядро CORE-1A берутся из скилла
ДОСЛОВНО (блоки кода под заголовками), плейсхолдеры {{…}} заполняются из ростера; незаполненный — ошибка. Был
C:/tmp/concept-wave/make_tasks.py (ростер был зашит в код — теперь только файл).

Ростер — JSON-список; строка — объект {"key": "robin-hood", "Key": "RobinHood", "game_role": "hero",
"weapon_hand": "left|right|none", "description_en": "...", "anchors_en": "...", "palette": [["forest green",
"#3E6B2F"], …], "accent": ["red fletching", "#B23A2E"]} или список в том же порядке (формат C:/tmp/concept-wave).

    python tools/art/pipeline_batch/make_tasks.py --roster roster.json --tasks-out <work>/tasks.txt \
        [--date YYYY-MM-DD] [--quality-ref <png>] [--generations-allowed 2] [--force] [--dry-run]

Пишет art/pipeline-candidates/<ASSET_ID>/asset-card.yaml (кроме существующей без --force),
art/imagegen/concept-<key>-codex/palette.json и docs/game-design/visual/06-tasks/prompts/<ASSET_ID>-concept.codex.md,
список путей заданий — в --tasks-out (вход codex_lane.py). Код выхода: 0 — готово, 2 — ошибка входа или шаблона.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _batch as b  # noqa: E402

QREF = "art/imagegen/hero-quality-v1/reference/medusa-quality-reference.png"
POSE = {"humanoid": "Neutral standing pose of a tabletop miniature: both feet planted on the pedestal, weight even, both "
                    "arms held slightly away from the torso with a visible gap between each arm and the body, elbows "
                    "slightly bent; not a T-pose and not an A-pose."}
WSIDE = {"right": "The weapon is held in the figure's own RIGHT hand, which appears on the viewer's LEFT in the front view.",
         "left": "The weapon is held in the figure's own LEFT hand, which appears on the viewer's RIGHT in the front view.",
         "none": "No weapon or held object."}
POSE_CHECK = "(both arms clearly apart from the torso, not a T-pose, not an A-pose)"
PEDESTAL = ("PEDESTAL: one round dark stone pedestal under the feet, two low stacked discs with plain bevelled edges, "
            "diameter about 0.55 of the figure height, flat top, no cobbles, no scenery, no coloured ring and no metal "
            "band. The camera is level with the pedestal: the pedestal is seen exactly edge-on, its top surface is not "
            "visible, its front edge is a straight horizontal line.")
FIELDS = ("key", "Key", "game_role", "weapon_hand", "description_en", "anchors_en", "palette", "accent")


def roster_rows(data) -> list[dict]:
    rows = []
    for r in data:
        row = dict(zip(FIELDS, r)) if isinstance(r, (list, tuple)) else dict(r)
        miss = [f for f in FIELDS if f not in row]
        if miss:
            raise ValueError(f"строка ростера {row.get('key')!r}: нет полей {miss}")
        if row["weapon_hand"] not in WSIDE:
            raise ValueError(f"{row['key']}: weapon_hand {row['weapon_hand']!r} не из {sorted(WSIDE)}")
        b.asset_id(row["key"])
        row["palette"] = [tuple(x) for x in row["palette"]]
        row["accent"] = tuple(row["accent"])
        rows.append(row)
    return rows


def extract(text: str) -> tuple[str, str, str]:
    """(B-CONCEPT-PACKAGE §5.4, файл задания §6.1, ядро CORE-1A §6.2) из concept-sheet.md."""
    return (b.skill_block(text, "### 5.4 Блок B-CONCEPT-PACKAGE"),
            b.skill_block(text, "### 6.1 Файл задания", "````markdown\n", "\n````"),
            b.skill_block(text, "### 6.2 Ядро CORE-1A"))


def card_text(row: dict, aid: str, adir: str, date: str, qref: str) -> str:
    pal = row["palette"]
    return "\n".join([
        f"# asset-card.yaml — 3d-model-pipeline, этап 0 (поля этапа 1). Записан пакетно {date} "
        "(tools/art/pipeline_batch/make_tasks.py).",
        "# Реестр asset-registry.json, строка 06-tasks/anim.csv и поля этапов 2+ — отдельными шагами пачки.",
        "ASSET_ID: " + aid, "CONTENT_KEY: " + row["key"], "KEY: " + row["Key"], "ROLE: hero", "ANATOMY: humanoid",
        "GAME_ROLE: " + row["game_role"], "WEAPON_HAND: " + row["weapon_hand"], "SIDE_VIEW: left",
        "DESCRIPTION_EN: " + json.dumps(row["description_en"], ensure_ascii=False),
        "ANCHORS_EN: " + json.dumps(row["anchors_en"], ensure_ascii=False),
        "PALETTE:", "  main:"] + ["    - {name: %s, hex: \"%s\"}" % (n, h) for n, h in pal] + [
        "  accent: {name: %s, hex: \"%s\"}" % row["accent"], "QUALITY_REFERENCE:", "  - " + qref,
        "ASSET_DIR: " + adir, "decided_by: delegated (ВР-реестр 2026-10-06)", ""])


def task_mapping(row: dict, aid: str, adir: str, date: str, card_sha: str, qref: str, qref_sha: str,
                 palette_sha: str, generations: int) -> dict:
    pal_en = ", ".join("%s %s" % (n, h) for n, h in row["palette"]) + ", accent %s %s" % row["accent"]
    return {"ASSET_ID": aid, "CONTENT_KEY": row["key"], "ASSET_DIR": adir, "DATE": date, "ASSET_CARD_SHA256": card_sha,
            "GENERATIONS_ALLOWED": str(generations), "QUALITY_REFERENCE": qref, "QUALITY_REFERENCE_SHA256": qref_sha,
            "PALETTE_SHA256": palette_sha, "DESCRIPTION_EN": row["description_en"], "ANCHORS_EN": row["anchors_en"],
            "PALETTE_EN": pal_en, "POSE_EN": POSE["humanoid"], "WEAPON_SIDE_EN": WSIDE[row["weapon_hand"]],
            "PEDESTAL_EN": PEDESTAL, "ASPECT_EN": "portrait aspect ratio 3:4", "ROLE_ARG": "hero",
            "POSE_CHECK_EN": POSE_CHECK, "ONE_BASE_EN": "one pedestal", "AND_PEDESTAL_EN": " and pedestal",
            "EDGE_ON_CHECK_EN": "the pedestal is seen exactly edge-on, its top surface is not visible"}


def main(argv=None) -> int:
    b.utf8_streams()
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0],
                                 formatter_class=argparse.RawDescriptionHelpFormatter, epilog=__doc__)
    ap.add_argument("--roster", required=True, help="JSON-список фигур (формат — в описании)")
    ap.add_argument("--tasks-out", required=True, help="файл списка заданий для codex_lane.py")
    ap.add_argument("--date", default=dt.date.today().isoformat())
    ap.add_argument("--quality-ref", default=QREF)
    ap.add_argument("--generations-allowed", type=int, default=2)
    ap.add_argument("--force", action="store_true", help="перезаписать существующие asset-card.yaml")
    ap.add_argument("--repo", default=str(b.REPO))
    ap.add_argument("--dry-run", action="store_true", help="проверить ростер и шаблоны, ничего не писать")
    try:
        a = ap.parse_args(argv)
    except SystemExit as exc:
        return int(exc.code or 0)
    repo = Path(a.repo)
    try:
        rows = roster_rows(json.loads(Path(a.roster).read_text(encoding="utf-8")))
        pkg, tpl, core = extract((repo / b.SKILL).read_text(encoding="utf-8"))
        qref_sha = b.sha256(repo / a.quality_ref)
        out = []
        for row in rows:
            aid = b.asset_id(row["key"])
            adir = f"art/pipeline-candidates/{aid}"
            pdir = repo / f"art/imagegen/concept-{row['key']}-codex"
            card = repo / adir / "asset-card.yaml"
            tp = repo / f"docs/game-design/visual/06-tasks/prompts/{aid}-concept.codex.md"
            if a.dry_run:  # шаблоны заполняются в памяти (дрейф скилла ловится без записи), sha — заглушки
                m = task_mapping(row, aid, adir, a.date, "0" * 64, a.quality_ref, qref_sha, "0" * 64,
                                 a.generations_allowed)
                m["B_CONCEPT_PACKAGE"], m["CORE_1A"] = b.fill(pkg, m), b.fill(core, m)
                print(json.dumps({"asset_id": aid, "card_exists": card.is_file(), "task": b.rel(tp, repo),
                                  "task_chars": len(b.fill(tpl, m))}, ensure_ascii=False))
                continue
            if card.is_file() and not a.force:
                print(f"{aid}: asset-card.yaml уже есть — пропуск (--force перезапишет)", file=sys.stderr)
                continue
            card.parent.mkdir(parents=True, exist_ok=True)
            pdir.mkdir(parents=True, exist_ok=True)
            palette = {"main": [{"name": n, "hex": h} for n, h in row["palette"]],
                       "accent": {"name": row["accent"][0], "hex": row["accent"][1]}}
            (pdir / "palette.json").write_text(json.dumps(palette, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            card.write_text(card_text(row, aid, adir, a.date, a.quality_ref), encoding="utf-8")
            m = task_mapping(row, aid, adir, a.date, b.sha256(card), a.quality_ref, qref_sha,
                             b.sha256(pdir / "palette.json"), a.generations_allowed)
            m["B_CONCEPT_PACKAGE"] = b.fill(pkg, m)
            m["CORE_1A"] = b.fill(core, m)
            task = b.fill(tpl, m)
            tp.parent.mkdir(parents=True, exist_ok=True)
            tp.write_text(task + "\n", encoding="utf-8")
            out.append(str(tp))
    except KeyError as exc:
        print(f"ERROR: плейсхолдер {{{{{exc.args[0]}}}}} шаблона скилла не заполняется — make_tasks.py устарел", file=sys.stderr)
        return 2
    except (OSError, ValueError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    if not a.dry_run:
        Path(a.tasks_out).parent.mkdir(parents=True, exist_ok=True)
        with open(a.tasks_out, "a", encoding="utf-8") as fh:
            fh.writelines(p + "\n" for p in out)
        print(len(out), "tasks →", a.tasks_out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
