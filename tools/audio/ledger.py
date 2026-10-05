"""Append one SYNTX audio spend to the shared credits ledger (05-production-plan §1 «Учёт»).

    python tools/audio/ledger.py --card AUC-M03 --units MUS-MENU --op "music (Suno V6 cover)" --model "Suno V6"
        --quote 10 --before 478 --after 468 --task <id> --ref C:/tmp/audio-src/syntx-runs/AUC-M03 [--note TEXT]

Same file and the same locking as tools/art/syntx_video_refs/ledger_append.py: syntx.window.entries of
docs/art-pipeline/evidence/s3-baseline-2026-09-28/credits-ledger.json, read-modify-write under a lock file, temp file +
os.replace, json indent 2. spent / balanceEnd are recomputed.
"""
from __future__ import annotations

import argparse
import datetime
import json
import os
import sys
import time

REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
LEDGER = os.environ.get("CREDITS_LEDGER") or os.path.join(REPO, "docs", "art-pipeline", "evidence",
                                                          "s3-baseline-2026-09-28", "credits-ledger.json")


def append(entry: dict) -> None:
    lock = LEDGER + ".lock"
    for _ in range(300):
        try:
            fd = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            break
        except FileExistsError:
            time.sleep(0.2)
    else:
        raise SystemExit(f"ledger lock busy: {lock}")
    try:
        with open(LEDGER, encoding="utf-8", newline="") as fh:
            raw = fh.read()
        newline = "\r\n" if "\r\n" in raw else "\n"
        data = json.loads(raw)
        window = data["syntx"]["window"]
        window["entries"].append(entry)
        window["spent"] = round(sum(-e.get("delta", 0) for e in window["entries"] if e.get("delta", 0) < 0), 2)
        window["balanceEnd"] = entry["balanceAfter"]
        text = json.dumps(data, ensure_ascii=False, indent=2).replace("\n", newline) + newline
        tmp = LEDGER + ".tmp"
        with open(tmp, "w", encoding="utf-8", newline="") as fh:
            fh.write(text)
        os.replace(tmp, LEDGER)
    finally:
        os.close(fd)
        os.remove(lock)


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--card", required=True)
    ap.add_argument("--units", required=True)
    ap.add_argument("--op", required=True)
    ap.add_argument("--model", required=True)
    ap.add_argument("--quote", type=float, required=True)
    ap.add_argument("--before", type=float, required=True)
    ap.add_argument("--after", type=float, required=True)
    ap.add_argument("--task", default=None)
    ap.add_argument("--ref", required=True)
    ap.add_argument("--status", default="ok")
    ap.add_argument("--note")
    a = ap.parse_args(argv)
    entry = {"time": datetime.datetime.now().astimezone().isoformat(timespec="seconds"), "asset": a.units,
             "cue": a.card, "op": a.op, "model": a.model, "taskId": a.task, "quotedBeforeRun": a.quote,
             "balanceBefore": a.before, "balanceAfter": a.after, "delta": round(a.after - a.before, 2),
             "owner": "звук и музыка (аудио-чат, 2026-10-05; docs/game-design/audio/06-task-cards.csv)",
             "ref": a.ref, "status": a.status,
             "source": "get-model-info до запуска, get-balance до/после (MCP syntx-ai)"}
    if a.note:
        entry["note"] = a.note
    append(entry)
    print(json.dumps(entry, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
