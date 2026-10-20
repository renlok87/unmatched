"""Карточки второго приёмщика («Opus high», результат Workflow) → card-2.json каждой приёмки + пара через validate_card.py --second.

Workflow-приёмщик со строгой схемой возвращает необязательные поля строкой "null" ("clip": "null",
"verdict_reason": "null" — F6, F8): clean() снимает их вместе с None; у pass verdict_reason убирается. Затем
tools/art/acceptance/validate_card.py <card.json> --second <card-2.json> --final-json <final.json> --print-verdict.
С 2026-10-21 второй приёмщик «другим профилем» — «Opus high» (workflow second-acceptor с effort high; решение
пользователя: «Хорошо, использую Opus High вместо Z-код для приемщика.», AGENTS.md «AI tools and side models»): пара
«Opus xhigh» + «Opus high» — два профиля, флаг не нужен. Обе карточки одного профиля (пары 2026-10-20 — 2026-10-21,
когда оба приёмщика были «Opus xhigh», или аргументы workflow без effort high) — пара считается с --same-profile-ok
(final.json#same_profile_fallback = true), строка NOTE в выводе.
Был C:/tmp/concept-wave/finish_second.py.

    python tools/art/pipeline_batch/finish_second.py <workflow-output.json> [--dry-run]
    # вход — любая из форм (C35): возврат workflow / журнал — голый список
    #   [{"asset": "...", "evidence": "<каталог приёмки от корня репо>", "card": {...}}, ...];
    # уведомление workflow — {"result": [...]} (result может быть и JSON-строкой); один элемент — объект {asset, evidence, card}

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


def profile_of(card_path: Path) -> str | None:
    """acceptor.profile карточки или None (файл не JSON / поля нет)."""
    try:
        return (json.loads(card_path.read_text(encoding="utf-8-sig")).get("acceptor") or {}).get("profile")
    except (OSError, ValueError, AttributeError):
        return None


def results_of(obj) -> list:
    """Список {asset, evidence, card} из вывода workflow в любой форме (C35): голый список (возврат workflow, журнал),
    {"result": [...]} или {"result": "<JSON-строка>"} (уведомление), один объект-элемент."""
    if isinstance(obj, dict) and "result" in obj:
        obj = obj["result"]
        if isinstance(obj, str):
            obj = json.loads(obj)
    if isinstance(obj, dict) and "evidence" in obj and "card" in obj:
        obj = [obj]
    if not isinstance(obj, list):
        raise ValueError("ожидается список [{asset, evidence, card}] или {\"result\": [...]}")
    bad = [i for i, r in enumerate(obj) if not (isinstance(r, dict) and r.get("evidence") and isinstance(r.get("card"), dict))]
    if bad:
        raise ValueError(f"элементы без evidence или card (объект): {bad}")
    return obj


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
        res = results_of(json.loads(Path(a.result).read_text(encoding="utf-8-sig")))
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
        cmd = [sys.executable, "tools/art/acceptance/validate_card.py", str(ev / "card.json"), "--second",
               str(ev / "card-2.json"), "--final-json", str(ev / "final.json"), "--check-files", "--print-verdict"]
        p1, p2 = profile_of(ev / "card.json"), (card.get("acceptor") or {}).get("profile")
        if p1 and p1 == p2:
            cmd.insert(-2, "--same-profile-ok")
            print(r.get("asset"), f"NOTE: оба приёмщика «{p1}» — запасной путь того же профиля (второй профиль — "
                  f"«{b.side_models().SECOND}», workflow second-acceptor с effort high); "
                  "final.json#same_profile_fallback")
        v = b.run(cmd, repo)
        fin = json.loads((ev / "final.json").read_text(encoding="utf-8")) if (ev / "final.json").exists() else {}
        tail = (v.stdout + v.stderr).strip().splitlines()[-1:] if v.returncode else ""
        print(r.get("asset"), p2 or "?", card.get("score"), card.get("verdict"), "| exit", v.returncode, "| final",
              fin.get("score"), fin.get("verdict"), tail)
        if v.returncode:
            code = 1
    return code


if __name__ == "__main__":
    sys.exit(main())
