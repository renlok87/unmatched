"""codex_lane.py на заглушке вместо codex (без трат): задание закрывается по -o + «tokens used», полоса гасит своё
дерево процессов по PID (заглушка и её дочерний процесс-«хук» живы после ответа, RC-11); обычный выход, предел
времени, claim между полосами, STOP-файл, --dry-run.

    python -m pytest tools/art/pipeline_batch/tests/test_batch_codex_lane.py -q
"""
from __future__ import annotations

import json
import sys
import threading
import time
from pathlib import Path

import psutil
import pytest

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
import codex_lane as L  # noqa: E402

STUB = r'''
import json, os, subprocess, sys, time
argv = sys.argv[1:]
mode, last = argv[0], argv[argv.index("-o") + 1]
prompt = sys.stdin.buffer.read()
if mode == "silent":
    time.sleep(60); sys.exit(0)
if mode in ("429", "429once", "fail"):
    cnt = last + ".count"
    n = int(open(cnt).read()) if os.path.exists(cnt) else 0
    open(cnt, "w").write(str(n + 1))
    sys.stderr.write("user\nRetry the view; sha 9f429ab1\n")  # эхо промпта: «retry» и 429 внутри хэша — не лимит
    if mode == "fail":
        sys.stderr.write("ERROR: something else broke\n"); sys.exit(1)
    if mode == "429" or n == 0:
        sys.stderr.write("ERROR: exceeded retry limit, last status: 429 Too Many Requests, request id: x\n")
        sys.exit(1)
    mode = "exit"
time.sleep(0.3)
open(last, "w", encoding="utf-8").write("answer %d\n" % len(prompt))
enc = "utf-16-le" if mode == "hang16" else "utf-8"
sys.stderr.buffer.write("hook: Stop Failed\ntokens used\n165 779\n".encode(enc)); sys.stderr.flush()
if mode == "exit":
    sys.exit(0)
child = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(60)"])
json.dump({"stub": os.getpid(), "child": child.pid}, open(last + ".pids", "w"))
time.sleep(60)
'''


def setup(tmp_path: Path, n=2, mode="hang"):
    stub = tmp_path / "stub_codex.py"
    stub.write_text(STUB, encoding="utf-8")
    tasks = []
    for i in range(n):
        t = tmp_path / "tasks" / f"T{i}-concept.codex.md"
        t.parent.mkdir(exist_ok=True)
        t.write_text(f"prompt {i}", encoding="utf-8")
        tasks.append(str(t))
    lst = tmp_path / "tasks.txt"
    lst.write_text("# очередь\n" + "\n".join(tasks) + "\n", encoding="utf-8")
    return lst, ["--exe", sys.executable, "--codex-args-json", json.dumps([str(stub), mode]), "--logs",
                 str(tmp_path / "logs"), "--tasks", str(lst), "--poll", "0.1", "--grace", "0.3", "--repo", str(tmp_path)]


def done(logs: Path, task_id: str) -> str:
    return (logs / f"{task_id}.done").read_text(encoding="utf-8").strip()


@pytest.mark.parametrize("mode", ["hang", "hang16"])
def test_answer_then_hang_kills_own_tree(tmp_path, mode, capsys):
    _lst, args = setup(tmp_path, n=2, mode=mode)
    t0 = time.monotonic()
    assert L.main(args + ["--name", "s1", "--once"]) == 0
    assert time.monotonic() - t0 < 30  # не ждали 60 с зависания заглушки
    logs = tmp_path / "logs"
    for i in range(2):
        assert done(logs, f"T{i}-concept.codex").endswith("done-killed")
        pids = json.loads((logs / f"T{i}-concept.codex-last.txt.pids").read_text())
        assert not psutil.pid_exists(pids["stub"]) and not psutil.pid_exists(pids["child"])
        assert (logs / f"T{i}-concept.codex-last.txt").read_text(encoding="utf-8").startswith("answer")
    journal = (logs / "s1.log").read_text(encoding="utf-8")
    assert journal.count("KILL ") == 2 and "LANE STOP" in journal
    assert json.loads(capsys.readouterr().out.splitlines()[-1])["tasks"][0]["reason"] == "done-killed"


def test_normal_exit_and_timeout(tmp_path):
    _lst, args = setup(tmp_path, n=1, mode="exit")
    assert L.main(args + ["--name", "e", "--once"]) == 0
    assert done(tmp_path / "logs", "T0-concept.codex") == "0 exit"
    sub = tmp_path / "silent"
    sub.mkdir()
    _lst, args = setup(sub, n=1, mode="silent")
    t0 = time.monotonic()
    assert L.main(args + ["--name", "t", "--once", "--timeout", "1"]) == 0
    assert time.monotonic() - t0 < 30
    assert done(sub / "logs", "T0-concept.codex").endswith("timeout")


def test_claims_are_exclusive_and_dry_run(tmp_path, capsys):
    _lst, args = setup(tmp_path, n=3, mode="exit")
    assert L.main(args + ["--name", "d", "--dry-run"]) == 0
    out = capsys.readouterr().out.splitlines()
    assert len([ln for ln in out if ln.startswith("{")]) == 3 and "free 3" in out[-1]
    assert not (tmp_path / "logs").exists() or not list((tmp_path / "logs").glob("*.claim"))
    a, b = {}, {}
    ta = threading.Thread(target=lambda: a.update(code=L.main(args + ["--name", "a", "--once"])))
    tb = threading.Thread(target=lambda: b.update(code=L.main(args + ["--name", "b", "--once"])))
    ta.start(); tb.start(); ta.join(60); tb.join(60)  # noqa: E702
    logs = tmp_path / "logs"
    starts = [ln for f in ("a.log", "b.log") for ln in (logs / f).read_text(encoding="utf-8").splitlines() if " START " in ln]
    assert sorted(ln.split(" START ")[1] for ln in starts) == [f"T{i}-concept.codex" for i in range(3)]  # каждое — 1 раз
    assert L.main(args + ["--name", "c", "--once", "--dry-run"]) == 0
    assert "free 0" in capsys.readouterr().out


def test_stop_file_ends_lane_and_missing_task(tmp_path):
    lst, args = setup(tmp_path, n=1, mode="exit")
    lst.write_text(lst.read_text(encoding="utf-8") + str(tmp_path / "tasks/missing.codex.md") + "\n", encoding="utf-8")
    stop = tmp_path / "STOP-1c"
    th = threading.Thread(target=lambda: L.main(args + ["--name", "w", "--stop-file", str(stop), "--idle-sleep", "1"]))
    th.start()
    time.sleep(3)
    stop.write_text("stop", encoding="utf-8")
    th.join(20)
    assert not th.is_alive()
    logs = tmp_path / "logs"
    assert done(logs, "T0-concept.codex") == "0 exit" and done(logs, "missing.codex") == "None missing-task"
    assert (logs / "w.log").read_text(encoding="utf-8").rstrip().endswith("LANE STOP")


def test_429_is_retried_after_pause_and_attempt_kept(tmp_path):
    """C4: отказ по лимиту — копия попытки в attempts/, пауза, повтор той же полосой; .done по последней попытке."""
    _lst, args = setup(tmp_path, n=1, mode="429once")
    assert L.main(args + ["--name", "r", "--once", "--retry-429", "2", "--retry-pause", "0.2"]) == 0
    logs = tmp_path / "logs"
    assert done(logs, "T0-concept.codex") == "0 exit"
    journal = (logs / "r.log").read_text(encoding="utf-8")
    assert journal.count(" START ") == 2 and "RATE-LIMIT T0-concept.codex attempt=1 exit=1 retry-in=0s" in journal
    a1 = logs / "attempts/T0-concept.codex/a1"
    assert "429 Too Many Requests" in (a1 / "T0-concept.codex.err").read_text(encoding="utf-8")
    assert (logs / "T0-concept.codex-last.txt").read_text(encoding="utf-8").startswith("answer")


def test_429_gives_up_keeps_claim_and_release_frees_it(tmp_path, capsys):
    _lst, args = setup(tmp_path, n=1, mode="429")
    assert L.main(args + ["--name", "g", "--once", "--retry-429", "1", "--retry-pause", "0"]) == 0
    logs = tmp_path / "logs"
    assert done(logs, "T0-concept.codex") == "1 rate-limited"
    assert (logs / "T0-concept.codex.claim").exists()  # другая полоса задание не возьмёт
    assert sorted(p.name for p in (logs / "attempts/T0-concept.codex").iterdir()) == ["a1", "a2"]
    capsys.readouterr()
    assert L.main(args + ["--name", "g", "--release", "T0-concept.codex"]) == 0
    rel = json.loads(capsys.readouterr().out.splitlines()[-1])
    assert rel["released"] and not (logs / "T0-concept.codex.claim").exists()
    assert not (logs / "T0-concept.codex.done").exists()
    assert (Path(rel["archive"]) / "T0-concept.codex.done").read_text(encoding="utf-8").strip() == "1 rate-limited"
    assert L.main(args + ["--name", "g", "--release", "T0-concept.codex"]) == 0  # повтор — без ошибки
    assert json.loads(capsys.readouterr().out.splitlines()[-1])["released"] is False


def test_other_failure_and_prompt_echo_are_not_429(tmp_path):
    _lst, args = setup(tmp_path, n=1, mode="fail")
    assert L.main(args + ["--name", "f", "--once", "--retry-429", "3", "--retry-pause", "0"]) == 0
    logs = tmp_path / "logs"
    assert done(logs, "T0-concept.codex") == "1 exit" and "RATE-LIMIT" not in (logs / "f.log").read_text(encoding="utf-8")
    err = tmp_path / "x.err"
    err.write_bytes("ERROR: exceeded retry limit, last status: 429 Too Many Requests".encode("utf-16-le"))
    assert L.rate_limited([err])
    err.write_bytes(b"You've hit your usage limit. Try again later.")
    assert L.rate_limited([err])
    err.write_bytes(b"Retry the view; sha 9f429ab1; status 4290")
    assert not L.rate_limited([err])


def test_stop_during_429_pause_releases_claim(tmp_path):
    lst, args = setup(tmp_path, n=1, mode="429")
    stop = tmp_path / "STOP-429"
    th = threading.Thread(target=lambda: L.main(args + ["--name", "p", "--stop-file", str(stop), "--retry-429", "5",
                                                        "--retry-pause", "30", "--idle-sleep", "1"]))
    th.start()
    logs = tmp_path / "logs"
    t0 = time.monotonic()
    while "RATE-LIMIT" not in ((logs / "p.log").read_text(encoding="utf-8") if (logs / "p.log").exists() else ""):
        assert time.monotonic() - t0 < 20
        time.sleep(0.1)
    stop.write_text("stop", encoding="utf-8")
    th.join(20)
    assert not th.is_alive()
    assert not (logs / "T0-concept.codex.claim").exists() and not (logs / "T0-concept.codex.done").exists()
    assert "RELEASE T0-concept.codex" in (logs / "p.log").read_text(encoding="utf-8")


def test_answered_needs_both_signals(tmp_path):
    last, err = tmp_path / "x-last.txt", tmp_path / "x.err"
    err.write_bytes("tokens used\n1".encode("utf-16-le"))
    assert not L.answered(last, [err])  # нет -o
    last.write_text("", encoding="utf-8")
    assert not L.answered(last, [err])  # -o пуст
    last.write_text("ok", encoding="utf-8")
    assert L.answered(last, [err])
    err.write_bytes(b"still working")
    assert not L.answered(last, [err])
    assert L.default_codex_args(Path("R"))[:2] == ["exec", "-C"] and "--ignore-user-config" not in L.default_codex_args(Path("R"))
