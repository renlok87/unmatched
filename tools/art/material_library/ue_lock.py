"""Exclusive lock of the shared live UnrealEditor (orchestrator rule 2026-09-30, after the 02:03-02:06 collision of the
look-dev C and anim-v2 captures in L_P17ControlScene).

Every UE step (import, level load, capture, restore) runs under C:/tmp/ue-editor.lock:
  - the lock is created atomically (os.open O_CREAT | O_EXCL) with the content "<owner> <ISO time> <step>";
  - an existing lock -> wait and retry every 20 s; a lock older than 25 min is stale: it is recorded and taken over;
  - while the lock is held, a daemon thread refreshes its mtime every POLL_S (heartbeat, RB-21), so a live step longer
    than 25 min is not judged stale; it never touches a lock whose content is no longer ours;
  - the lock is deleted in a finally block (only if it is still ours).
Keep each locked step short (one hero / one scene part per lock).

    from ue_lock import ue_lock
    with ue_lock("accent wall") as info:
        ...                                   # info["waited_s"], info["stale_taken"]

    python tools/art/material_library/ue_lock.py --step "<step>" -- <command ...>   # run a command under the lock
"""
from __future__ import annotations

import argparse
import datetime as dt
import os
import subprocess
import sys
import threading
import time
from contextlib import contextmanager
from pathlib import Path

LOCK = Path(os.environ.get("UE_EDITOR_LOCK", "C:/tmp/ue-editor.lock"))  # one lock file per live editor
OWNER = os.environ.get("UE_LOCK_OWNER", "look-dev-C")  # parallel groups name themselves (e.g. look-dev-C-A)
POLL_S = 20.0
STALE_S = 25 * 60.0
EVENTS = []   # stale takeovers etc. of this process (for the reports)


def _now() -> str:
    return dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat()


def _heartbeat(lock: Path, stamp: str, every_s: float, stop: threading.Event, info: dict) -> None:
    """RB-21: refresh the mtime of our held lock every every_s until stop is set; stop on a foreign or missing lock."""
    while not stop.wait(every_s):
        try:
            if lock.read_text(encoding="utf-8", errors="replace").strip() != stamp:
                return                  # taken over or replaced: never refresh someone else's lock
            os.utime(str(lock), None)
        except OSError:                 # vanished (FileNotFoundError) or not accessible: the finally block reports it
            return
        info["heartbeats"] += 1


@contextmanager
def ue_lock(step: str, owner: str = OWNER, poll_s: float = POLL_S, stale_s: float = STALE_S, lock: Path = LOCK,
            heartbeat_s: float | None = None):
    """heartbeat_s: how often the held lock's mtime is refreshed (default poll_s; 0 or less turns it off)."""
    lock.parent.mkdir(parents=True, exist_ok=True)
    t0 = time.time()
    info = {"step": step, "owner": owner, "waited_s": 0.0, "stale_taken": None, "waits": 0}
    while True:
        try:
            fd = os.open(str(lock), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        except FileExistsError:
            try:
                age = time.time() - lock.stat().st_mtime
                held = lock.read_text(encoding="utf-8", errors="replace").strip()
            except FileNotFoundError:
                continue
            if age > stale_s:
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
                ev = {"at": _now(), "step": step, "stale_lock": held, "age_s": round(age, 1), "kept_as": str(aside)}
                EVENTS.append(ev)
                info["stale_taken"] = ev
                print("UE LOCK: stale lock taken over: %r (age %.0f s)" % (held, age), flush=True)
                continue
            if info["waits"] % 3 == 0:
                print("UE LOCK: busy (%r, age %.0f s); waiting" % (held, age), flush=True)
            info["waits"] += 1
            time.sleep(poll_s)
            continue
        stamp = "%s %s %s" % (owner, _now(), step)
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(stamp + "\n")
        info["stamp"] = stamp
        break
    info["waited_s"] = round(time.time() - t0, 1)
    info["heartbeats"] = 0
    every = poll_s if heartbeat_s is None else heartbeat_s
    stop = threading.Event()
    beat = None
    if every > 0:
        beat = threading.Thread(target=_heartbeat, args=(lock, stamp, every, stop, info),
                                name="ue-lock-heartbeat", daemon=True)
        beat.start()
    try:
        yield info
    finally:
        stop.set()
        if beat is not None:
            beat.join(timeout=5.0)
        try:
            if lock.read_text(encoding="utf-8", errors="replace").strip() == stamp:
                lock.unlink()
            else:
                print("UE LOCK: lock content changed while held; not deleting it", flush=True)
        except FileNotFoundError:
            print("UE LOCK: lock vanished while held", flush=True)


def main() -> int:
    for stream in (sys.stdout, sys.stderr):  # RB-11/F47: UTF-8 even in a cp1251 pipe (agents' Bash tool)
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="backslashreplace")
    ap = argparse.ArgumentParser(description="run one command under the shared UE editor lock")
    ap.add_argument("--step", required=True)
    ap.add_argument("cmd", nargs=argparse.REMAINDER)
    a = ap.parse_args()
    cmd = a.cmd[1:] if a.cmd and a.cmd[0] == "--" else a.cmd
    if not cmd:
        raise SystemExit("no command")
    with ue_lock(a.step) as info:
        print("UE LOCK: held %s (waited %.0f s)" % (info["stamp"], info["waited_s"]), flush=True)
        rc = subprocess.call(cmd)
    return rc


if __name__ == "__main__":
    sys.exit(main())
