#!/usr/bin/env python3
"""Rebaseline chosen files of the stage-3 production snapshot (docs/art-pipeline/evidence/s3-baseline-2026-09-28/
production-baseline.json) after an intended, documented change - the W4-A way ('rebaselined' on the row +
an entry in revisions[]), without re-snapshotting everything.

    python tools/art/snapshot_rebaseline.py --root repo --root art-worktree \
        --path unreal/Unmatched/Content/ArtPreview/Medusa/Materials/MI_Medusa_P1.uasset \
        --path unreal/Unmatched/Content/ArtPreview/Medusa/Materials/MI_Medusa_P2.uasset \
        --by "5c-B1 (решение пользователя «Акценты + кольцо»)" --report <act.md> [--dry-run]

A path under one of productionDirs is added to that dir's files (new file) or updated; a path of productionFiles is
updated. The sha256 is read from disk now; a missing file is an error (nothing is written). The check command of
snapshot_baseline.py must then report 0 differences for these rows.
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
BASELINE = REPO / "docs/art-pipeline/evidence/s3-baseline-2026-09-28/production-baseline.json"
# the same roots as snapshot_baseline.py: "repo" is ALWAYS the main checkout (REPO would be the art worktree when the
# script runs from there - 5c-B1 ran it from the art worktree)
ROOTS = {"repo": Path("C:/Users/ren/WebstormProjects/unmached/unmached"),
         "art-worktree": Path("C:/Users/ren/.codex/worktrees/art-foundation/unmached")}


def sha256(p: Path) -> str:
    h = hashlib.sha256()
    with p.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def rebaseline(doc: dict, roots: dict, pairs: list[tuple[str, str]], by: str, report: str, date: str) -> list[dict]:
    changes = []
    for root, path in pairs:
        p = roots[root] / path
        if not p.is_file():
            raise FileNotFoundError(f"{root}:{path}")
        new = {"root": root, "path": path, "exists": True, "bytes": p.stat().st_size, "sha256": sha256(p)}
        row = next((r for r in doc["productionFiles"] if r["root"] == root and r["path"] == path), None)
        holder = None
        if row is None:
            for d in doc["productionDirs"]:
                if d["root"] == root and path.startswith(d["dir"].rstrip("/") + "/"):
                    holder = d
                    row = next((f for f in d["files"] if f["path"] == path), None)
                    break
            if holder is None:
                raise KeyError(f"{root}:{path} is neither a production file nor under a production dir")
        prev = row.get("sha256") if row else None
        if prev == new["sha256"]:
            changes.append({"root": root, "path": path, "change": "unchanged"})
            continue
        info = {"by": by, "previousSha256": prev, "report": report}
        if row is None:
            row = dict(new)
            holder["files"].append(row)
            holder["files"].sort(key=lambda f: f["path"])
            if "fileCount" in holder:
                holder["fileCount"] = len(holder["files"])
        else:
            row.update(new)
        row["rebaselined"] = info
        changes.append({"root": root, "path": path, "change": "added" if prev is None else "updated",
                        "sha256": new["sha256"], "previousSha256": prev})
    touched = [c for c in changes if c["change"] != "unchanged"]
    if touched:
        doc.setdefault("revisions", []).append({"date": date, "task": by, "report": report,
                                                "change": "; ".join(f"{c['root']}:{c['path']} {c['change']}"
                                                                    for c in touched)})
    return changes


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--root", action="append", choices=sorted(ROOTS), required=True)
    ap.add_argument("--path", action="append", required=True)
    ap.add_argument("--by", required=True)
    ap.add_argument("--report", required=True)
    ap.add_argument("--baseline", type=Path, default=BASELINE)
    ap.add_argument("--date", default=dt.date.today().isoformat())
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args(argv)
    doc = json.loads(a.baseline.read_text(encoding="utf-8"))
    pairs = [(r, p) for r in a.root for p in a.path]
    changes = rebaseline(doc, ROOTS, pairs, a.by, a.report, a.date)
    print(json.dumps(changes, ensure_ascii=False, indent=1))
    if not a.dry_run:
        a.baseline.write_text(json.dumps(doc, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
