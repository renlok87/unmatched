"""Проверка зависшего .git/index.lock перед коммитом пачки (F82): возраст блокировки и живые процессы git; снимать только устаревшую.

Приложение Codex раз в несколько секунд гоняет `git diff` по главному чекауту и дважды оставило .git/index.lock
(пилот 2026-10-14, 00:12 и 01:06) — коммиты падали. Правило: блокировка снимается, только если она старше
--stale-sec И ни одного процесса git не запущено; иначе ждать (git сам её снимет) — чужую живую операцию не ломать.
Сам git не запускает. Worktree: `.git`-файл → `gitdir:`.

    python tools/art/pipeline_batch/git_lock.py [--repo <checkout>] [--stale-sec 120] [--remove-stale] [--json]

Код выхода: 0 — блокировки нет (или устаревшая снята), 1 — блокировка есть (живая или не снята), 2 — не git-чекаут.
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _batch as b  # noqa: E402


def git_dir(repo: Path) -> Path:
    g = Path(repo) / ".git"
    if g.is_file():
        line = g.read_text(encoding="utf-8").strip()
        if not line.startswith("gitdir:"):
            raise ValueError(f"{g}: нет gitdir:")
        p = Path(line[len("gitdir:"):].strip())
        return p if p.is_absolute() else (Path(repo) / p).resolve()
    if g.is_dir():
        return g
    raise ValueError(f"{repo}: не git-чекаут")


def git_processes() -> list[dict]:
    """Запущенные процессы git (только чтение списка; ничего не гасится)."""
    try:
        import psutil
    except ImportError:
        return []
    out = []
    for p in psutil.process_iter(["pid", "name", "cmdline"]):
        name = (p.info.get("name") or "").lower()
        if name in ("git.exe", "git"):
            out.append({"pid": p.info["pid"], "cmdline": " ".join(p.info.get("cmdline") or [])[:200]})
    return out


def inspect(repo: Path, stale_sec: float, procs=None) -> dict:
    lock = git_dir(repo) / "index.lock"
    procs = git_processes() if procs is None else procs
    if not lock.exists():
        return {"lock": lock.as_posix(), "exists": False, "verdict": "none", "git_processes": procs}
    age = time.time() - lock.stat().st_mtime
    verdict = "stale" if age >= stale_sec and not procs else "live"
    return {"lock": lock.as_posix(), "exists": True, "age_s": round(age, 1), "git_processes": procs, "verdict": verdict}


def main(argv=None) -> int:
    b.utf8_streams()
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0],
                                 formatter_class=argparse.RawDescriptionHelpFormatter, epilog=__doc__)
    ap.add_argument("--repo", default=str(b.REPO))
    ap.add_argument("--stale-sec", type=float, default=120.0, help="возраст, с которого блокировка без git — устаревшая")
    ap.add_argument("--remove-stale", action="store_true", help="снять устаревшую блокировку")
    ap.add_argument("--json", action="store_true")
    try:
        a = ap.parse_args(argv)
    except SystemExit as exc:
        return int(exc.code or 0)
    try:
        r = inspect(Path(a.repo), a.stale_sec)
    except (OSError, ValueError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    r["removed"] = False
    if r["verdict"] == "stale" and a.remove_stale:
        Path(r["lock"]).unlink(missing_ok=True)
        r["removed"] = True
    print(json.dumps(r, ensure_ascii=False) if a.json else
          f"{r['verdict']}: {r['lock']}" + (f" age {r.get('age_s')} s, git processes {len(r['git_processes'])}"
                                            if r["exists"] else "") + (" — removed" if r["removed"] else ""))
    return 0 if (not r["exists"] or r["removed"]) else 1


if __name__ == "__main__":
    sys.exit(main())
