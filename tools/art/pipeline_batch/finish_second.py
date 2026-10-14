"""Карточки второго приёмщика (Opus xhigh, результат Workflow) → card-2.json каждой приёмки + пара через validate_card.py --second.

Workflow-приёмщик со строгой схемой возвращает необязательные поля строкой "null" ("clip": "null",
"verdict_reason": "null" — F6, F8): clean() снимает их вместе с None; у pass verdict_reason убирается. Затем
tools/art/acceptance/validate_card.py <card.json> --second <card-2.json> --final-json <final.json> --print-verdict.
Был C:/tmp/concept-wave/finish_second.py.

    python tools/art/pipeline_batch/finish_second.py <workflow-output.json> [--dry-run]
    # вход: {"result": [{"asset": "...", "evidence": "<каталог приёмки от корня репо>", "card": {...}}, ...]}

--dry-run: напечатать очищенные карточки, ничего не писать и validate_card не запускать.
Код выхода: 0 — все пары посчитаны (validate_card 0), 1 — хотя бы одна пара с ошибкой, 2 — ошибка входа.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _batch as b  # noqa: E402


def clean(o):
    """Снять None и строки "null" рекурсивно (словари); списки сохраняют длину, их элементы чистятся."""
    if isinstance(o, dict):
        return {k: clean(v) for k, v in o.items() if v is not None and v != "null"}
    if isinstance(o, list):
        return [clean(v) for v in o]
    return o


def second_card(card: dict) -> dict:
    out = clean(card)
    if out.get("verdict") == "pass":
        out.pop("verdict_reason", None)
    return out


def main(argv=None) -> int:
    b.utf8_streams()
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0],
                                 formatter_class=argparse.RawDescriptionHelpFormatter, epilog=__doc__)
    ap.add_argument("result", help="JSON вывода Workflow второго приёмщика")
    ap.add_argument("--repo", default=str(b.REPO))
    ap.add_argument("--dry-run", action="store_true")
    try:
        a = ap.parse_args(argv)
    except SystemExit as exc:
        return int(exc.code or 0)
    repo = Path(a.repo)
    try:
        res = json.loads(Path(a.result).read_text(encoding="utf-8"))["result"]
        if not isinstance(res, list):
            raise ValueError("result должен быть списком")
    except (OSError, ValueError, KeyError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    code = 0
    for r in res:
        ev = repo / r["evidence"]
        card = second_card(r["card"])
        if a.dry_run:
            print(json.dumps({"asset": r.get("asset"), "evidence": r["evidence"], "card_2": card}, ensure_ascii=False))
            continue
        if not (ev / "card.json").is_file():
            print(r.get("asset"), "ERROR: нет", (ev / "card.json").as_posix(), file=sys.stderr)
            code = 1
            continue
        (ev / "card-2.json").write_text(json.dumps(card, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        v = b.run([sys.executable, "tools/art/acceptance/validate_card.py", str(ev / "card.json"), "--second",
                   str(ev / "card-2.json"), "--final-json", str(ev / "final.json"), "--check-files", "--print-verdict"], repo)
        fin = json.loads((ev / "final.json").read_text(encoding="utf-8")) if (ev / "final.json").exists() else {}
        tail = (v.stdout + v.stderr).strip().splitlines()[-1:] if v.returncode else ""
        print(r.get("asset"), "opus", card.get("score"), card.get("verdict"), "| exit", v.returncode, "| final",
              fin.get("score"), fin.get("verdict"), tail)
        if v.returncode:
            code = 1
    return code


if __name__ == "__main__":
    sys.exit(main())
