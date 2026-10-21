#!/usr/bin/env python3
"""Промпт приёмщика модели (этап 4 скилла 3d-model-pipeline): шаблон §8.2 `references/acceptance-and-blender.md`,
заполненный по `frames/frames.json`, `acceptor-inputs.json` (acceptor_inputs.py) и заявке ассета.

    python tools/art/acceptance/model_prompt.py --evidence <ASSET_DIR>/evidence/acceptance/<YYYYMMDD>-r<N> \
        --executor-session-id <id запускающего> [--second] [--date YYYY-MM-DD]

Без `--second` пишет `<evidence>/acceptor-prompt.md` (первый приёмщик «Opus xhigh», session_id
`workflow:acceptor-<ASSET_ID>-r<N>`); с `--second` — `acceptor-prompt-2.md` («Opus high»,
`workflow:acceptor2-<ASSET_ID>-r<N>`; §8.1 п.5а). Плейсхолдер, оставшийся незаполненным, — код 1 (приёмщика не
вызывать, §8.1 п.3). Код 2 — ошибка входа. Мини-пачка 2026-10-20: до этого промпт заполнялся вручную у каждой фигуры.
"""
import argparse
import json
import re
import sys
from pathlib import Path

import yaml

REPO = Path(__file__).resolve().parents[3]
RUBRIC = REPO / ".agents/skills/3d-model-pipeline/references/acceptance-and-blender.md"
PROFILES = {False: ("Opus xhigh", "acceptor"), True: ("Opus high", "acceptor2")}


def template() -> str:
    text = RUBRIC.read_text(encoding="utf-8")
    start = text.index("```markdown\n", text.index("### 8.2")) + len("```markdown\n")
    return text[start:text.index("\n```\n", start)] + "\n"


def palette(p: dict) -> str:
    main = ", ".join(f"{c['name']} {c['hex']}" for c in p.get("main", []))
    acc = p.get("accent") or {}
    return f"main: {main}; accent: {acc.get('name', '')} {acc.get('hex', '')}".strip()


def build(evidence: Path, executor: str, second: bool, date: str | None) -> str:
    rel = lambda p: Path(p).resolve().relative_to(REPO).as_posix()  # noqa: E731
    e = rel(evidence)
    frames = json.loads((evidence / "frames/frames.json").read_text(encoding="utf-8"))
    inputs = json.loads((evidence / "acceptor-inputs.json").read_text(encoding="utf-8"))
    card_path = REPO / inputs["sources"]["asset_card"]["path"]
    card = yaml.safe_load(card_path.read_text(encoding="utf-8"))
    m = re.search(r"(\d{8})-r(\d+)$", evidence.name)
    if not m:
        raise ValueError(f"каталог приёмки не <YYYYMMDD>-r<N>: {evidence.name}")
    d8, cycle = m.group(1), f"r{m.group(2)}"
    date = date or f"{d8[:4]}-{d8[4:6]}-{d8[6:]}"
    side = card.get("SIDE_VIEW") or frames.get("side_view") or "left"
    prev = inputs["sources"].get("previous_card")
    profile, label = PROFILES[second]
    ph = dict(inputs["placeholders"])
    ph.update({
        "ASSET_ID": card["ASSET_ID"], "CYCLE": cycle, "DATE": date, "E": e,
        "SIDE_VIEW": side, "SIDE_TURN": "turn-090.jpg" if side == "left" else "turn-270.jpg",
        "QUALITY_REFERENCE": (card.get("QUALITY_REFERENCE") or ["art/imagegen/hero-quality-v1/reference/medusa-quality-reference.png"])[0],
        "BAKE": inputs["sources"]["bake_run"], "LD": inputs["sources"]["look_dev_run"],
        "ROLE": card.get("ROLE", "hero"), "PALETTE": palette(card.get("PALETTE") or {}),
        "WEAPON_HAND": card.get("WEAPON_HAND", "none"),
        "POLY_BUDGET": json.dumps(card.get("POLY_BUDGET") or {}, ensure_ascii=False),
        "PREVIOUS_CARD": prev or "null", "PREVIOUS_CARD_JSON": json.dumps(prev),
        "ACCEPTED_OBJECT_JSON": json.dumps(frames["accepted_object"], ensure_ascii=False),
        "FRAMES_FILES_JSON": json.dumps(frames["files"], ensure_ascii=False),
        "ACCEPTOR_PROFILE": profile, "ACCEPTOR_SESSION_ID": f"workflow:{label}-{card['ASSET_ID']}-{cycle}",
        "EXECUTOR_SESSION_ID": executor,
    })
    out = template()
    for k, v in ph.items():
        out = out.replace("{{" + k + "}}", str(v))
    return out


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--evidence", required=True, help="<ASSET_DIR>/evidence/acceptance/<YYYYMMDD>-r<N>")
    ap.add_argument("--executor-session-id", required=True)
    ap.add_argument("--second", action="store_true", help="второй приёмщик «Opus high» → acceptor-prompt-2.md")
    ap.add_argument("--date", help="дата приёмки YYYY-MM-DD (по умолчанию — из имени каталога)")
    a = ap.parse_args(argv)
    ev = Path(a.evidence)
    ev = ev if ev.is_absolute() else REPO / ev
    try:
        text = build(ev, a.executor_session_id, a.second, a.date)
    except (OSError, KeyError, ValueError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    left = sorted(set(re.findall(r"\{\{[A-Z_]+\}\}", text)))
    if left:
        print(f"FAIL: незаполненные плейсхолдеры {left}", file=sys.stderr)
        return 1
    dst = ev / ("acceptor-prompt-2.md" if a.second else "acceptor-prompt.md")
    dst.write_text(text, encoding="utf-8", newline="\n")
    print(f"OK: {dst.relative_to(REPO).as_posix()} ({len(text)} chars, {PROFILES[a.second][0]})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
