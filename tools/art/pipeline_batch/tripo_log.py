"""Строка журнала трат на один черновик Tripo этапа 1b (tripo3d-stages.md §6 п.6) через tools/art/visual/ledger.py add + запись в tripo-tasks.jsonl пачки.

Пишется сразу после клика генерации, до выгрузки GLB (post_1b.py). Номер карточки AN-NN — --an или из очереди пачки
prep_1b.py (--queue: поле "an" строки с этим content-key). Был C:/tmp/concept-wave/tripo-log.sh.

    python tools/art/pipeline_batch/tripo_log.py <content-key> <task_uuid> <before> <after> --queue <work>/tripo-queue.json \
        [--records <work>/tripo-tasks.jsonl] [--date YYYYMMDD] [--quoted 30] [--dry-run]

--dry-run: напечатать команду ledger.py, ничего не писать. Код выхода — код ledger.py add (2 — ошибка входа).
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _batch as b  # noqa: E402

UNITS = "single-image, HD модель, H3.1 Макс.кач., геометрия и текстура, без частей, без 8K, приватно"


def an_from_queue(queue: list, key: str) -> str:
    hit = [x["an"] for x in queue if x.get("key") == key]
    if not hit:
        raise ValueError(f"{key!r} нет в очереди пачки")
    return hit[0]


def ledger_args(*, key: str, task: str, before: float, after: float, an: str, date: str, quoted: float,
                note: str = "этап 1b: черновик") -> list[str]:
    aid = b.asset_id(key)
    return ["tools/art/visual/ledger.py", "add", "--task", an, "--template", "T-TRIPO-PART", "--service", "Tripo",
            "--model", "Tripo Studio H3.1", "--units", UNITS, "--quoted", f"{quoted:g}", "--before", f"{before:g}",
            "--after", f"{after:g}", "--service-task-id", task,
            "--result", f"art/pipeline-candidates/{aid}/{date}-draft-tripo/source/", "--note", note]


def main(argv=None) -> int:
    b.utf8_streams()
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0],
                                 formatter_class=argparse.RawDescriptionHelpFormatter, epilog=__doc__)
    ap.add_argument("key", help="content-key (kebab)")
    ap.add_argument("task", help="task uuid Studio")
    ap.add_argument("before", type=float)
    ap.add_argument("after", type=float)
    src = ap.add_mutually_exclusive_group(required=True)
    src.add_argument("--an", help="карточка AN-NN")
    src.add_argument("--queue", help="очередь prep_1b.py (tripo-queue.json)")
    ap.add_argument("--records", default=None, help="jsonl пачки: {key, task, before, after}")
    ap.add_argument("--date", default=dt.date.today().strftime("%Y%m%d"))
    ap.add_argument("--quoted", type=float, default=30)
    ap.add_argument("--note", default="этап 1b: черновик")
    ap.add_argument("--repo", default=str(b.REPO))
    ap.add_argument("--dry-run", action="store_true")
    try:
        a = ap.parse_args(argv)
    except SystemExit as exc:
        return int(exc.code or 0)
    try:
        an = a.an or an_from_queue(json.loads(Path(a.queue).read_text(encoding="utf-8")), a.key)
        args = ledger_args(key=a.key, task=a.task, before=a.before, after=a.after, an=an, date=a.date, quoted=a.quoted,
                           note=a.note)
    except (OSError, ValueError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    if a.dry_run:
        print(json.dumps({"dry_run": True, "cmd": [sys.executable, *args]}, ensure_ascii=False))
        return 0
    r = b.run([sys.executable, *args], Path(a.repo))
    print(((r.stdout + r.stderr).strip().splitlines() or [""])[-1])
    if r.returncode == 0 and a.records:
        with open(a.records, "a", encoding="utf-8") as fh:
            fh.write(json.dumps({"key": a.key, "task": a.task, "before": a.before, "after": a.after}) + "\n")
    return r.returncode


if __name__ == "__main__":
    sys.exit(main())
