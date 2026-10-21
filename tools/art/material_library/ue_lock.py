"""Exclusive lock of the shared live UnrealEditor (orchestrator rule 2026-09-30, after the 02:03-02:06 collision of the
look-dev C and anim-v2 captures in L_P17ControlScene).

Every UE step (import, level load, capture, restore) runs under C:/tmp/ue-editor.lock:
  - the lock is created atomically (os.open O_CREAT | O_EXCL); content (first line unchanged since 2026-09-30):
        <owner> <ISO time> <step>
        pid=<PID> host=<hostname> since=<epoch s> max_hold_s=<s>
        cmd=<command line>                       (CLI only)
  - an existing lock -> wait and retry every 20 s. The lock is stale (recorded and taken over) when
      * dead_pid: its PID is not alive and its host is this machine (no 25 min wait after a crash), or
      * max_hold: it is held longer than the max_hold_s written in it (the holder's limit), or
      * mtime: its mtime is older than 25 min (also an old-format lock without the PID line);
  - while the lock is held, a daemon thread refreshes its mtime every POLL_S (heartbeat, RB-21), so a live step longer
    than 25 min is not judged stale; it never touches a lock whose content is no longer ours. The heartbeat stops after
    max_hold_s (default 2 h, UE_LOCK_MAX_HOLD_S; 0 = no limit): a hung but live step no longer holds the editor forever
    (review gap R-02, 2026-10-14);
  - a waiter gives up after wait_timeout_s (default: wait forever; UE_LOCK_WAIT_TIMEOUT_S) with UeLockTimeout naming
    the owner, PID, host and step of the lock;
  - the lock is deleted in a finally block (only if it is still ours).
Keep each locked step short (one hero / one scene part per lock).

    from ue_lock import ue_lock
    with ue_lock("accent wall") as info:
        ...                                   # info["waited_s"], info["stale_taken"], info["max_hold_exceeded"]

    python tools/art/material_library/ue_lock.py --step "<step>" [--wait-timeout S] [--max-hold S] -- <command ...>
        # runs a command under the lock; exit code = the command's, 124 = gave up waiting (--wait-timeout)

One lock file per live editor (DS-3a 2026-10-21, docs/game-design/decisions/2026-10-21-parallel-7a-editor-slots.md): the
7a editor of slot N (tools/tripo-pipeline/ue7a/editor_slot.py, MCP port 8123+N) has its own lock, so the steps of two
heroes in two editors never wait for each other. The lock file is, in this order:
  --lock PATH (CLI) | UE_EDITOR_LOCK | --slot N (CLI) / UE_EDITOR_SLOT=N -> lock_path_for_slot(N) | C:/tmp/ue-editor.lock
Slot 0 IS the old single editor (port 8123, C:/tmp/ue-editor.lock): without these variables nothing changes.
    python tools/art/material_library/ue_lock.py --slot 1 --step "<step>" -- <command ...>
    python tools/art/material_library/ue_lock.py --lock C:/tmp/clip-manifest.lock --step "manifest" -- <command ...>

capture_gpu_token(step): the GPU token C:/tmp/unmatched-gpu.lock (UNMATCHED_GPU_LOCK; the token of live_tune.py and
render_bench.py) around an editor capture, so the look-dev / clip frames of one slot are not shot while another slot
(or a bench) renders (F153 unsettled frames, F155 anchor noise). Taken only in slot mode (UE_EDITOR_SLOT set) or with
UE_CAPTURE_GPU_TOKEN=1; UE_CAPTURE_GPU_TOKEN=0 or no slot -> a no-op, as before.
"""
from __future__ import annotations

import argparse
import datetime as dt
import os
import socket
import subprocess
import sys
import threading
import time
from contextlib import contextmanager
from pathlib import Path


def _env_float(name: str, default: float | None) -> float | None:
    raw = os.environ.get(name, "").strip()
    if not raw:
        return default
    try:
        return float(raw)
    except ValueError:
        return default


DEFAULT_LOCK = Path("C:/tmp/ue-editor.lock")  # slot 0: the single 7a editor of DS-3 (MCP :8123)
MAX_SLOT = 9


def lock_path_for_slot(slot) -> Path:
    """The lock file of the 7a editor slot N: 0 -> C:/tmp/ue-editor.lock (unchanged), N -> C:/tmp/ue-editor-slot<N>.lock."""
    n = int(slot)
    if n < 0 or n > MAX_SLOT:
        raise ValueError("editor slot %r: want 0..%d" % (slot, MAX_SLOT))
    return DEFAULT_LOCK if n == 0 else DEFAULT_LOCK.with_name("ue-editor-slot%d.lock" % n)


def env_lock_path(environ=None) -> Path:
    """UE_EDITOR_LOCK, else the lock of UE_EDITOR_SLOT, else C:/tmp/ue-editor.lock."""
    env = os.environ if environ is None else environ
    if env.get("UE_EDITOR_LOCK", "").strip():
        return Path(env["UE_EDITOR_LOCK"].strip())
    if env.get("UE_EDITOR_SLOT", "").strip():
        return lock_path_for_slot(env["UE_EDITOR_SLOT"].strip())
    return DEFAULT_LOCK


LOCK = env_lock_path()  # one lock file per live editor
GPU_LOCK = Path(os.environ.get("UNMATCHED_GPU_LOCK", "C:/tmp/unmatched-gpu.lock"))  # live_tune.py / render_bench.py token
OWNER = os.environ.get("UE_LOCK_OWNER", "look-dev-C")  # parallel groups name themselves (e.g. look-dev-C-A)
POLL_S = _env_float("UE_LOCK_POLL_S", 20.0) or 20.0  # wait poll and heartbeat period (one editor, heroes interleaved: 2-5 s)
STALE_S = 25 * 60.0
MAX_HOLD_S = _env_float("UE_LOCK_MAX_HOLD_S", 2 * 3600.0)   # heartbeat limit of a held lock; 0 or less = no limit
WAIT_TIMEOUT_S = _env_float("UE_LOCK_WAIT_TIMEOUT_S", None)  # None = wait forever
EXIT_WAIT_TIMEOUT = 124  # CLI: gave up waiting (as coreutils timeout)
HOST = socket.gethostname()
EVENTS = []   # stale takeovers etc. of this process (for the reports)


class UeLockTimeout(TimeoutError):
    """The lock stayed busy longer than wait_timeout_s; .holder = parse_lock() of the busy lock."""

    def __init__(self, message: str, holder: dict, waited_s: float):
        super().__init__(message)
        self.holder = holder
        self.waited_s = waited_s


def _now() -> str:
    return dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat()


def _same_host(host: str | None) -> bool:
    return bool(host) and host.lower() == HOST.lower()


_K32 = None


def _kernel32():
    global _K32
    if _K32 is None:
        import ctypes
        from ctypes import wintypes

        k = ctypes.WinDLL("kernel32", use_last_error=True)
        k.OpenProcess.restype = wintypes.HANDLE
        k.OpenProcess.argtypes = (wintypes.DWORD, wintypes.BOOL, wintypes.DWORD)
        k.GetExitCodeProcess.restype = wintypes.BOOL
        k.GetExitCodeProcess.argtypes = (wintypes.HANDLE, ctypes.POINTER(wintypes.DWORD))
        k.CloseHandle.argtypes = (wintypes.HANDLE,)
        _K32 = k
    return _K32


def pid_alive(pid: int | None) -> bool:
    """Is the process PID alive on THIS machine? Unknown -> True (never judge a lock dead on a guess)."""
    if not pid or pid <= 0:
        return False
    if pid == os.getpid():
        return True
    if sys.platform == "win32":
        import ctypes
        from ctypes import wintypes

        k = _kernel32()
        h = k.OpenProcess(0x1000, False, pid)  # PROCESS_QUERY_LIMITED_INFORMATION
        if not h:
            return ctypes.get_last_error() != 87  # ERROR_INVALID_PARAMETER = no such process; access denied = alive
        try:
            code = wintypes.DWORD()
            if not k.GetExitCodeProcess(h, ctypes.byref(code)):
                return True
            return code.value == 259  # STILL_ACTIVE
        finally:
            k.CloseHandle(h)
    try:
        os.kill(pid, 0)  # POSIX only: on Windows signal 0 is CTRL_C_EVENT
    except ProcessLookupError:
        return False
    except OSError:
        return True
    return True


def lock_content(owner: str, step: str, max_hold_s: float | None, cmd: str | None = None, since: float | None = None,
                 pid: int | None = None, host: str | None = None) -> str:
    """The text of a lock file (without the final newline)."""
    stamp = "%s %s %s" % (owner, _now(), step)
    meta = "pid=%d host=%s since=%.3f max_hold_s=%g" % (os.getpid() if pid is None else pid, host or HOST,
                                                       time.time() if since is None else since,
                                                       max_hold_s if max_hold_s and max_hold_s > 0 else 0)
    lines = [stamp, meta]
    if cmd:
        lines.append("cmd=" + " ".join(str(cmd).split())[:500])
    return "\n".join(lines).strip()  # compared with read_text().strip() by the heartbeat and the finally block


def parse_lock(text: str) -> dict:
    """{stamp, owner, step, pid, host, since, max_hold_s, cmd} of a lock's text; an old-format lock (first line only)
    gives pid / host / since / max_hold_s None."""
    lines = [ln.strip() for ln in (text or "").strip().splitlines()]
    stamp = lines[0] if lines else ""
    parts = stamp.split(" ", 2)
    out = {"stamp": stamp, "owner": parts[0] if parts else "", "step": parts[2] if len(parts) > 2 else "",
           "pid": None, "host": None, "since": None, "max_hold_s": None, "cmd": None}
    for ln in lines[1:]:
        if ln.startswith("cmd="):
            out["cmd"] = ln[4:]
            continue
        for tok in ln.split():
            k, sep, v = tok.partition("=")
            if not sep:
                continue
            try:
                if k == "pid":
                    out["pid"] = int(v)
                elif k == "host":
                    out["host"] = v
                elif k == "since":
                    out["since"] = float(v)
                elif k == "max_hold_s":
                    out["max_hold_s"] = float(v) if float(v) > 0 else None
            except ValueError:
                pass
    return out


def stale_reason(holder: dict, age_s: float, stale_s: float, now: float | None = None) -> str | None:
    """Why a busy lock may be taken over: "dead_pid", "max_hold", "mtime" or None (still held)."""
    now = time.time() if now is None else now
    if holder.get("pid") and _same_host(holder.get("host")) and not pid_alive(holder["pid"]):
        return "dead_pid"
    if holder.get("max_hold_s") and holder.get("since") is not None and now - holder["since"] > holder["max_hold_s"]:
        return "max_hold"
    if age_s > stale_s:
        return "mtime"
    return None


def describe(holder: dict, age_s: float | None = None) -> str:
    s = "owner %r, pid %s on %s, step %r" % (holder.get("owner"), holder.get("pid") or "?", holder.get("host") or "?",
                                            holder.get("step"))
    if age_s is not None:
        s += ", mtime age %.0f s" % age_s
    if holder.get("cmd"):
        s += ", cmd %s" % holder["cmd"]
    return s


def _heartbeat(lock: Path, content: str, every_s: float, stop: threading.Event, info: dict,
               deadline: float | None) -> None:
    """RB-21: refresh the mtime of our held lock every every_s until stop is set; stop on a foreign or missing lock and
    after the max hold (deadline, time.monotonic)."""
    while True:
        wait = every_s if deadline is None else min(every_s, max(0.0, deadline - time.monotonic()))
        if stop.wait(wait):
            return
        if deadline is not None and time.monotonic() >= deadline:
            info["max_hold_exceeded"] = True
            print("UE LOCK: held longer than max_hold_s %.0f s: heartbeat stopped, waiters may take the lock over (%s)"
                  % (info["max_hold_s"], info["stamp"]), flush=True)
            return
        try:
            if lock.read_text(encoding="utf-8", errors="replace").strip() != content:
                return                  # taken over or replaced: never refresh someone else's lock
            os.utime(str(lock), None)
        except OSError:                 # vanished (FileNotFoundError) or not accessible: the finally block reports it
            return
        info["heartbeats"] += 1


@contextmanager
def ue_lock(step: str, owner: str = OWNER, poll_s: float = POLL_S, stale_s: float = STALE_S, lock: Path = LOCK,
            heartbeat_s: float | None = None, max_hold_s: float | None = None, wait_timeout_s: float | None = None,
            cmd: str | None = None):
    """heartbeat_s: how often the held lock's mtime is refreshed (default poll_s; 0 or less turns it off).
    max_hold_s: the heartbeat stops after this hold time and waiters judge the lock stale (default MAX_HOLD_S = 2 h or
    UE_LOCK_MAX_HOLD_S; 0 or less = no limit). wait_timeout_s: give up waiting with UeLockTimeout (default
    WAIT_TIMEOUT_S = UE_LOCK_WAIT_TIMEOUT_S or wait forever; a negative value = wait forever). cmd: written to the lock."""
    lock = Path(lock)
    lock.parent.mkdir(parents=True, exist_ok=True)
    hold = MAX_HOLD_S if max_hold_s is None else max_hold_s
    hold = hold if hold and hold > 0 else None
    wait_limit = WAIT_TIMEOUT_S if wait_timeout_s is None else wait_timeout_s
    wait_limit = wait_limit if wait_limit is not None and wait_limit >= 0 else None
    t0 = time.time()
    info = {"step": step, "owner": owner, "waited_s": 0.0, "stale_taken": None, "waits": 0, "pid": os.getpid(),
            "host": HOST, "max_hold_s": hold, "max_hold_exceeded": False}
    while True:
        try:
            fd = os.open(str(lock), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        except FileExistsError:
            try:
                age = time.time() - lock.stat().st_mtime
                held = lock.read_text(encoding="utf-8", errors="replace").strip()
            except FileNotFoundError:
                continue
            holder = parse_lock(held)
            reason = stale_reason(holder, age, stale_s)
            if reason:
                # take over atomically: rename the stale file away, then check it was the one we judged stale
                aside = lock.with_name(lock.name + ".stale.%d.%d" % (os.getpid(), int(time.time())))
                try:
                    os.rename(str(lock), str(aside))
                except OSError:
                    continue
                got = aside.read_text(encoding="utf-8", errors="replace").strip()
                if got != held:
                    try:
                        os.rename(str(aside), str(lock))   # a fresh lock of someone else: give it back
                    except OSError:
                        pass
                    continue
                ev = {"at": _now(), "step": step, "stale_lock": held, "reason": reason, "holder": holder,
                      "age_s": round(age, 1), "kept_as": str(aside)}
                EVENTS.append(ev)
                info["stale_taken"] = ev
                print("UE LOCK: stale lock taken over (%s): %s" % (reason, describe(holder, age)), flush=True)
                continue
            waited = time.time() - t0
            if wait_limit is not None and waited >= wait_limit:
                raise UeLockTimeout("UE LOCK: still busy after %.0f s (wait timeout %.0f s): %s"
                                    % (waited, wait_limit, describe(holder, age)), holder, round(waited, 1))
            if info["waits"] % 3 == 0:
                print("UE LOCK: busy (%s); waiting" % describe(holder, age), flush=True)
            info["waits"] += 1
            time.sleep(poll_s if wait_limit is None else max(0.0, min(poll_s, t0 + wait_limit - time.time())))
            continue
        content = lock_content(owner, step, hold, cmd)
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(content + "\n")
        stamp = content.splitlines()[0]
        info["stamp"] = stamp
        info["content"] = content
        break
    info["waited_s"] = round(time.time() - t0, 1)
    info["heartbeats"] = 0
    every = poll_s if heartbeat_s is None else heartbeat_s
    stop = threading.Event()
    beat = None
    if every > 0:
        deadline = time.monotonic() + hold if hold else None
        beat = threading.Thread(target=_heartbeat, args=(lock, content, every, stop, info, deadline),
                                name="ue-lock-heartbeat", daemon=True)
        beat.start()
    try:
        yield info
    finally:
        stop.set()
        if beat is not None:
            beat.join(timeout=5.0)
        try:
            if lock.read_text(encoding="utf-8", errors="replace").strip() == content:
                lock.unlink()
            else:
                print("UE LOCK: lock content changed while held; not deleting it", flush=True)
        except FileNotFoundError:
            print("UE LOCK: lock vanished while held", flush=True)


def capture_token_wanted(environ=None) -> bool:
    """UE_CAPTURE_GPU_TOKEN=1/0 decides; unset -> only in slot mode (UE_EDITOR_SLOT set)."""
    env = os.environ if environ is None else environ
    v = env.get("UE_CAPTURE_GPU_TOKEN", "").strip().lower()
    if v in ("1", "true", "yes", "on"):
        return True
    if v in ("0", "false", "no", "off"):
        return False
    return bool(env.get("UE_EDITOR_SLOT", "").strip())


@contextmanager
def capture_gpu_token(step: str, lock: Path | None = None, wait_timeout_s: float | None = 3600.0,
                      max_hold_s: float = 3600.0, poll_s: float = 10.0, environ=None):
    """The GPU token around one editor capture (look-dev review, clip frames / close-ups) in slot mode.

    Atomic create as ue_lock (pid line, heartbeat, dead-PID takeover of OUR format); a live_tune.py / render_bench.py
    token (one line, no pid line, no heartbeat) is never judged stale by its mtime (stale_s = inf): we wait for it. Order
    is always editor lock -> GPU token (benches take no editor lock), so there is no lock cycle."""
    if not capture_token_wanted(environ):
        yield {"taken": False, "reason": "no UE_EDITOR_SLOT / UE_CAPTURE_GPU_TOKEN=0: single editor, no token"}
        return
    with ue_lock("gpu-capture " + step, owner=OWNER + "-capture", poll_s=poll_s, stale_s=float("inf"),
                 lock=Path(lock) if lock else GPU_LOCK, max_hold_s=max_hold_s, wait_timeout_s=wait_timeout_s) as info:
        info["taken"] = True
        info["lock"] = str(Path(lock) if lock else GPU_LOCK)
        yield info


def _cmdline(cmd: list) -> str:
    return subprocess.list2cmdline(cmd) if sys.platform == "win32" else " ".join(cmd)


def main(argv=None) -> int:
    for stream in (sys.stdout, sys.stderr):  # RB-11/F47: UTF-8 even in a cp1251 pipe (agents' Bash tool)
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="backslashreplace")
    ap = argparse.ArgumentParser(description="run one command under the UE editor lock (one lock per editor slot)")
    ap.add_argument("--step", required=True)
    where = ap.add_mutually_exclusive_group()
    where.add_argument("--slot", type=int, default=None,
                       help="the 7a editor slot N (editor_slot.py): lock C:/tmp/ue-editor-slot<N>.lock, 0 = "
                            "C:/tmp/ue-editor.lock (default: UE_EDITOR_LOCK, else UE_EDITOR_SLOT, else slot 0)")
    where.add_argument("--lock", default=None, help="an explicit lock file (e.g. C:/tmp/clip-manifest.lock)")
    ap.add_argument("--wait-timeout", type=float, default=None,
                    help="give up waiting for a busy lock after S seconds: exit %d with the owner and PID of the lock "
                         "(default UE_LOCK_WAIT_TIMEOUT_S or wait forever)" % EXIT_WAIT_TIMEOUT)
    ap.add_argument("--max-hold", type=float, default=None,
                    help="the heartbeat stops after S seconds of hold and waiters may take the lock over "
                         "(default UE_LOCK_MAX_HOLD_S or %.0f; 0 = no limit)" % (2 * 3600))
    ap.add_argument("cmd", nargs=argparse.REMAINDER)
    a = ap.parse_args(argv)
    cmd = a.cmd[1:] if a.cmd and a.cmd[0] == "--" else a.cmd
    if not cmd:
        raise SystemExit("no command")
    try:
        lock = Path(a.lock) if a.lock else (lock_path_for_slot(a.slot) if a.slot is not None else LOCK)
        with ue_lock(a.step, max_hold_s=a.max_hold, wait_timeout_s=a.wait_timeout, cmd=_cmdline(cmd),
                     lock=lock) as info:
            print("UE LOCK: held %s (pid %d, waited %.0f s, %s)" % (info["stamp"], info["pid"], info["waited_s"],
                                                                    lock.as_posix()), flush=True)
            rc = subprocess.call(cmd)
    except UeLockTimeout as exc:
        print(str(exc), file=sys.stderr, flush=True)
        return EXIT_WAIT_TIMEOUT
    return rc


if __name__ == "__main__":
    sys.exit(main())
