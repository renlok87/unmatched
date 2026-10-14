"""git_lock.py (F82): блокировка снимается, только если старше порога и git не запущен; worktree через gitdir:.

    python -m pytest tools/art/pipeline_batch/tests/test_batch_git_lock.py -q
"""
from __future__ import annotations

import os
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
import git_lock as G  # noqa: E402


def test_verdicts_and_worktree(tmp_path, monkeypatch, capsys):
    repo = tmp_path / "repo"
    (repo / ".git").mkdir(parents=True)
    r = G.inspect(repo, 60, procs=[])
    assert r["verdict"] == "none" and not r["exists"]
    lock = repo / ".git/index.lock"
    lock.write_text("", encoding="utf-8")
    assert G.inspect(repo, 60, procs=[])["verdict"] == "live"  # свежая
    old = time.time() - 600
    os.utime(lock, (old, old))
    assert G.inspect(repo, 60, procs=[{"pid": 1, "cmdline": "git diff"}])["verdict"] == "live"  # git работает
    assert G.inspect(repo, 60, procs=[])["verdict"] == "stale"
    monkeypatch.setattr(G, "git_processes", lambda: [])
    assert G.main(["--repo", str(repo), "--stale-sec", "60"]) == 1 and lock.exists()  # без --remove-stale не трогает
    assert G.main(["--repo", str(repo), "--stale-sec", "60", "--remove-stale"]) == 0 and not lock.exists()
    wt = tmp_path / "wt"
    wt.mkdir()
    gd = tmp_path / "repo/.git/worktrees/wt"
    gd.mkdir(parents=True)
    (wt / ".git").write_text(f"gitdir: {gd}\n", encoding="utf-8")
    assert G.git_dir(wt) == gd
    assert G.main(["--repo", str(tmp_path / "nogit")]) == 2
    capsys.readouterr()
