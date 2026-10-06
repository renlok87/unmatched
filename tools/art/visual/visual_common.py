"""Shared helpers of the visual production cycle tools (tools/art/visual/*.py).

Paths of the cycle (docs/game-design/visual/05-production-plan.md section 1.0):
  task cards       docs/game-design/visual/06-tasks/*.csv
  prompt templates docs/game-design/visual/07-prompt-templates.md
  credits ledger   docs/game-design/visual/credits-ledger.json
  acceptance sheet docs/game-design/evidence/VISUAL/<id>/
"""
from __future__ import annotations

import csv
import hashlib
import re
import sys
from pathlib import Path

TASKS_REL = "docs/game-design/visual/06-tasks"
PROMPTS_REL = TASKS_REL + "/prompts"
TEMPLATES_REL = "docs/game-design/visual/07-prompt-templates.md"
LEDGER_REL = "docs/game-design/visual/credits-ledger.json"
EVIDENCE_REL = "docs/game-design/evidence/VISUAL"

TEMPLATE_ID_RE = re.compile(r"^T-[A-Z0-9][A-Z0-9-]*$")


class VisualError(Exception):
    """A loud, user-facing failure: the tool prints the message and exits with code 2."""


def repo_root() -> Path:
    """Repository root: tools/art/visual/<this file> -> three levels up."""
    return Path(__file__).resolve().parents[3]


def load_cards(root: Path) -> dict[str, dict]:
    """All task cards by id from every 06-tasks/*.csv (UTF-8, optional BOM). Duplicate ids are an error."""
    files = sorted((root / TASKS_REL).glob("*.csv"))
    if not files:
        raise VisualError(f"no task tables found in {(root / TASKS_REL).as_posix()}")
    cards: dict[str, dict] = {}
    for path in files:
        with path.open(encoding="utf-8-sig", newline="") as fh:
            for row in csv.DictReader(fh):
                cid = (row.get("id") or "").strip()
                if not cid:
                    continue
                if cid in cards:
                    raise VisualError(f"duplicate card id {cid}: {cards[cid]['_file']} and {path.relative_to(root).as_posix()}")
                card = {k: (v if v is not None else "") for k, v in row.items() if k is not None}
                card["_file"] = path.relative_to(root).as_posix()
                cards[cid] = card
    return cards


def get_card(root: Path, cid: str) -> dict:
    cards = load_cards(root)
    if cid not in cards:
        prefix = cid.split("-")[0] if "-" in cid else cid
        near = sorted(k for k in cards if k.startswith(prefix))[:12]
        hint = f"; ids with prefix {prefix}: {', '.join(near)}" if near else ""
        raise VisualError(f"unknown card id {cid!r} (not in {TASKS_REL}/*.csv){hint}")
    return cards[cid]


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with Path(path).open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def sha256_tree(path: Path) -> tuple[str, int]:
    """Digest of a directory: sha256 over sorted lines '<relative posix path>\\0<file sha256>\\n'; skips __pycache__."""
    h = hashlib.sha256()
    count = 0
    for f in sorted(p for p in Path(path).rglob("*") if p.is_file() and "__pycache__" not in p.parts):
        rel = f.relative_to(path).as_posix()
        h.update(f"{rel}\0{sha256_file(f)}\n".encode("utf-8"))
        count += 1
    return h.hexdigest(), count


def rel_or_abs(root: Path, path: Path) -> str:
    """Repo-relative posix path when inside the repo, else the absolute posix path."""
    p = Path(path).resolve()
    try:
        return p.relative_to(root.resolve()).as_posix()
    except ValueError:
        return p.as_posix()


def utf8_console() -> None:
    """Russian card text must not crash or garble a cp1251 Windows console."""
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError, OSError):
            pass


def templates_text(root: Path) -> str:
    path = root / TEMPLATES_REL
    if not path.is_file():
        raise VisualError(f"prompt templates not found: {TEMPLATES_REL}")
    return path.read_text(encoding="utf-8")
