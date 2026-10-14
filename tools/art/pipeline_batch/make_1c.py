"""Файлы заданий Codex 1c (виды поверх ортопроекций черновика 1b) для каждой фигуры, у которой есть orthos/ortho-framing.json.

concept-sheet.md §8.1, §8.2, §9: шаблоны файла задания 1c, ядро CORE-1C и B-CONCEPT-PACKAGE берутся из скилла
дословно. Пишет docs/game-design/visual/06-tasks/prompts/<ASSET_ID>-concept-views.codex.md (существующие пропускает)
и дописывает пути: в --tasks-out (полосы Codex) или, для лицензированных фигур с решением пользователя
(evidence/acceptance-concept/*/user-decision.json), в --ust-out (их 1c сначала пробуется в Codex, unstability — только
если Codex отказал весь вид: F7/F8). Лимит генераций на вид — min(2, 4 − уже сделанных 1c этого вида). Был
C:/tmp/concept-wave/make_1c.py.

    python tools/art/pipeline_batch/make_1c.py --tasks-out <work>/tasks-1c.txt --ust-out <work>/tasks-1c-ust.txt \
        [--only ASSET-ACHILLES-001,…] [--date YYYY-MM-DD] [--dry-run]

Код выхода: 0 — готово, 2 — ошибка входа или шаблона.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _batch as b  # noqa: E402

WSIDE = {"right": ("The weapon is held in the figure's own RIGHT hand, which appears on the viewer's LEFT in the front view.",
                   "The weapon in the figure's own RIGHT hand appears on the viewer's RIGHT."),
         "left": ("The weapon is held in the figure's own LEFT hand, which appears on the viewer's RIGHT in the front view.",
                  "The weapon in the figure's own LEFT hand appears on the viewer's LEFT."),
         "none": ("No weapon or held object.", "")}
VIEWBLOCK = {
    "front": ("FRONT", "FRONT: strict front orthographic view, the figure faces the camera, no three-quarter turn.", ""),
    "left": ("LEFT SIDE", "LEFT SIDE: strict profile, the figure's OWN left side faces the camera, its face toward the left "
             "edge of the image, no three-quarter view.", ""),
    "right": ("RIGHT SIDE", "RIGHT SIDE: strict profile, the figure's OWN right side faces the camera, its face toward the "
              "right edge of the image, no three-quarter view.", ""),
    "back": ("BACK", "BACK: camera directly behind, no face visible, no three-quarter view. {{BACK_WEAPON_EN}}",
             "Image 3 is the finished side view of the SAME miniature, for continuity of colours and details only."),
}


PEDESTAL_1C = ("PEDESTAL: paint it as the dark stone pedestal of the approved design (image 2), two low stacked discs with "
               "plain bevelled edges; keep the shape and size of image 1 but not its light grey draft material; no "
               "coloured ring and no metal band.")


def clause(sentence: str) -> str:
    """Фраза для строки CHECKLIST «…; back - …;»: без конечной точки (C13: было «view.; back»)."""
    return sentence.strip().rstrip(".")


def templates(text: str) -> tuple[str, str, str]:
    """(B-CONCEPT-PACKAGE §5.4, файл задания 1c §8.1, ядро CORE-1C §8.2)."""
    return (b.skill_block(text, "### 5.4 Блок B-CONCEPT-PACKAGE"), b.skill_block(text, "### 8.1 Файл задания"),
            b.skill_block(text, "### 8.2 Ядро CORE-1C"))


def allowed_generations(records: list) -> dict:
    """Генераций на вид в этом запуске: min(2, 4 − уже сделанных записей 1c этого вида)."""
    used = {v: sum(1 for r in records if r.get("stage") == "1c" and r.get("view") == v) for v in ("front", "side", "back")}
    return {v: max(0, min(2, 4 - n)) for v, n in used.items()}


def build_task(repo: Path, framing: Path, core_tpl: str, task_tpl: str, pkg_tpl: str, date: str) -> tuple[str, str]:
    """(ASSET_ID, текст файла задания 1c)."""
    A = framing.parents[2]
    aid = A.name
    card = (A / "asset-card.yaml").read_text(encoding="utf-8")
    k = b.scalar(card, "CONTENT_KEY")
    hand = b.scalar(card, "WEAPON_HAND") or "none"
    side = b.scalar(card, "SIDE_VIEW") or "left"
    winged = b.scalar(card, "ANATOMY") == "winged-biped"
    pkgdir = repo / f"art/imagegen/concept-{k}-codex"
    pal = json.loads((pkgdir / "palette.json").read_text(encoding="utf-8"))
    pal_en = (", ".join(f"{x['name']} {x['hex']}" for x in pal["main"])
              + f", accent {pal['accent']['name']} {pal['accent']['hex']}")
    fj = json.loads(framing.read_text(encoding="utf-8"))
    pp = fj["placement_pct"]
    orth = b.rel(framing.parent, repo)
    recs = json.loads((pkgdir / "generation-records.json").read_text(encoding="utf-8")) \
        if (pkgdir / "generation-records.json").exists() else []
    allowed = allowed_generations(recs)
    ws, bw = WSIDE[hand]
    base = {"ASSET_ID": aid, "CONTENT_KEY": k, "ASSET_DIR": b.rel(A, repo), "VIEWS": "front,side,back",
            "SIDE_VIEW": side, "ORTHO_DIR": orth, "ROLE_ARG": "creature" if winged else "hero",
            "WEAPON_SIDE_EN": ws, "BACK_WEAPON_EN": bw, "FRAME_CHECK_EN": "the same pedestal position and size",
            "DESCRIPTION_EN": b.scalar(card, "DESCRIPTION_EN"), "ANCHORS_EN": b.scalar(card, "ANCHORS_EN"),
            "PALETTE_EN": pal_en, "ASPECT_EN": "landscape aspect ratio 4:3" if winged else "portrait aspect ratio 3:4",
            "KEEP_EN": "silhouette, pose, proportions, arm and weapon positions, hand grip, pedestal shape, scale and framing",
            "WHOLE_EN": "The whole subject and the whole pedestal visible.", "PEDESTAL_1C_EN": PEDESTAL_1C,
            "TOP_Y": f"{pp['figure_top_y']:.1f}", "BASE_TOP_Y": f"{pp['base_top_y_est']:.1f}",
            "BASE_BOTTOM_Y": f"{pp['base_bottom_y']:.1f}"}
    cores = {}
    for slot, ov in (("FRONT", "front"), ("SIDE", side), ("BACK", "back")):
        name, vb, img3 = VIEWBLOCK[ov]
        bw_pct = fj["views"][ov]["base_width_pct"]
        m = dict(base, VIEW_NAME_EN=name, VIEW_BLOCK_EN=b.fill(vb, base), IMAGE3_EN=img3,
                 BASE_X0=f"{50 - bw_pct / 2:.1f}", BASE_X1=f"{50 + bw_pct / 2:.1f}")
        m["FRAMING_BASE_EN"] = b.fill("pedestal x{{BASE_X0}}%-{{BASE_X1}}%, pedestal top y{{BASE_TOP_Y}}%, "
                                      "pedestal bottom y{{BASE_BOTTOM_Y}}%", m)
        cc = "\n".join(ln for ln in b.fill(core_tpl, m).split("\n") if ln.strip() != "")  # пустой IMAGE3 — без строки
        cores[slot] = cc.replace(" \n", "\n").rstrip()
    # В тексте задания (8.1) сторона оружия стоит только в строке CHECKLIST «front and side - …; back - …;» — там фразы
    # без конечной точки; у WEAPON_HAND none пустой back заменяется той же фразой «No weapon or held object».
    m = dict(base, B_CONCEPT_PACKAGE=b.fill(pkg_tpl, base), CORE_1C_FRONT=cores["FRONT"], CORE_1C_SIDE=cores["SIDE"],
             CORE_1C_BACK=cores["BACK"], WEAPON_SIDE_EN=clause(ws), BACK_WEAPON_EN=clause(bw or ws))
    body = b.fill(task_tpl, m)
    inputs = [(f"{orth}/ortho_front.png", "draft render FRONT (image 1 of the front view)"),
              (f"{orth}/ortho_{side}.png", f"draft render {side.upper()} SIDE (image 1 of the side view)"),
              (f"{orth}/ortho_back.png", "draft render BACK (image 1 of the back view)"),
              (f"{orth}/ortho-framing.json", "framing numbers of the draft renders (not an image input)"),
              (f"art/imagegen/concept-{k}-codex/design/{k}-front.png", "approved design front (image 2 of every view)"),
              (f"art/imagegen/concept-{k}-codex/palette.json", "palette of the asset card (not an image input)")]
    rows = "\n".join(f"| {i} | `{p}` | {w} | {b.sha256(repo / p)} |" for i, (p, w) in enumerate(inputs, 1))
    head = f"""# {aid} concept 1c - Codex task (views over the draft orthos)

Written by Claude from {base['ASSET_DIR']}/asset-card.yaml and the step-1b orthos (template concept-sheet.md §8.1;
tools/art/pipeline_batch/make_1c.py). The task to execute is the text in the section **Task**. The header is
provenance only.

| field | value |
|---|---|
| id | {aid}-concept-views (stage 1c) |
| date | {date} |
| template | concept-sheet.md 1c (ledger template id T-CODEX-HEROVIEWS) |
| package | `art/imagegen/concept-{k}-codex/` |
| asset card | `{base['ASSET_DIR']}/asset-card.yaml`, sha256 {b.sha256(A / 'asset-card.yaml')} |
| image generations allowed in this run | front {allowed['front']}, side {allowed['side']}, back {allowed['back']} |

## Inputs

| # | path | what | sha256 |
|---|---|---|---|
{rows}

## Task

```text
{body}
```
"""
    if "{{" in head:
        raise ValueError(f"{aid}: остался плейсхолдер")
    return aid, head


def main(argv=None) -> int:
    b.utf8_streams()
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0],
                                 formatter_class=argparse.RawDescriptionHelpFormatter, epilog=__doc__)
    ap.add_argument("--tasks-out", required=True, help="список заданий Codex (дописывается)")
    ap.add_argument("--ust-out", required=True, help="список заданий лицензированных фигур (дописывается)")
    ap.add_argument("--only", default=None, help="ASSET_ID через запятую")
    ap.add_argument("--date", default=dt.date.today().isoformat())
    ap.add_argument("--repo", default=str(b.REPO))
    ap.add_argument("--dry-run", action="store_true", help="собрать задания в памяти, ничего не писать")
    try:
        a = ap.parse_args(argv)
    except SystemExit as exc:
        return int(exc.code or 0)
    repo = Path(a.repo)
    only = {x.strip() for x in a.only.split(",")} if a.only else None
    try:
        pkg, tpl, core = templates((repo / b.SKILL).read_text(encoding="utf-8"))
        ust = {p.parents[3].name for p in repo.glob("art/pipeline-candidates/*/evidence/acceptance-concept/*/user-decision.json")}
        out_codex, out_ust = [], []
        for fr in sorted(repo.glob("art/pipeline-candidates/ASSET-*-001/*-draft-tripo/orthos/ortho-framing.json")):
            aid = fr.parents[2].name
            if only and aid not in only:
                continue
            tp = repo / f"docs/game-design/visual/06-tasks/prompts/{aid}-concept-views.codex.md"
            if tp.exists():
                continue
            _aid, text = build_task(repo, fr, core, tpl, pkg, a.date)
            if a.dry_run:
                print(json.dumps({"asset_id": aid, "task": b.rel(tp, repo), "chars": len(text),
                                  "list": "ust" if aid in ust else "codex"}, ensure_ascii=False))
                continue
            tp.parent.mkdir(parents=True, exist_ok=True)
            tp.write_text(text, encoding="utf-8")
            (out_ust if aid in ust else out_codex).append(str(tp))
    except KeyError as exc:
        print(f"ERROR: плейсхолдер {{{{{exc.args[0]}}}}} не заполняется — шаблон скилла и make_1c.py разошлись", file=sys.stderr)
        return 2
    except (OSError, ValueError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    if not a.dry_run:
        for path, items in ((a.tasks_out, out_codex), (a.ust_out, out_ust)):
            Path(path).parent.mkdir(parents=True, exist_ok=True)
            with open(path, "a", encoding="utf-8") as fh:
                fh.writelines(p + "\n" for p in items)
        print("codex", len(out_codex), "licensed", len(out_ust))
    return 0


if __name__ == "__main__":
    sys.exit(main())
