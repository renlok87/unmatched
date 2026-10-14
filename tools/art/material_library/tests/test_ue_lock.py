"""Tests for tools/art/material_library/ue_lock.py: the heartbeat of a held lock (RB-21, skill pilot 2026-10-13) and
the holder data / limits of review gap R-02 (2026-10-14).

A lock is stale by its mtime after STALE_S (25 min). Without a heartbeat a live step longer than that was taken over
by the next agent. While held, the lock's mtime is now refreshed every POLL_S (heartbeat_s); a lock whose content is
no longer ours is never touched. R-02: the lock names its PID and host; the heartbeat stops after max_hold_s (a hung
live step no longer holds the editor forever); a lock of a dead PID on this host is stale at once; a waiter gives up
after wait_timeout_s naming the owner and PID. Temporary lock files only, short intervals, no UE.

  python -m unittest discover -s tools/art/material_library/tests -v
"""
from __future__ import annotations

import os
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))

import ue_lock as ul  # noqa: E402

OLD = 1000.0  # seconds the mtime is pushed back: far beyond the stale_s of the waiter below


def backdate(lock: Path, seconds: float = OLD) -> None:
    t = time.time() - seconds
    os.utime(str(lock), (t, t))


def age(lock: Path) -> float:
    return time.time() - lock.stat().st_mtime


def wait_until(cond, timeout: float = 3.0) -> bool:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if cond():
            return True
        time.sleep(0.02)
    return cond()


class UeLockHeartbeatTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.lock = Path(self._tmp.name) / "ue-editor.lock"

    def tearDown(self):
        self._tmp.cleanup()

    def test_heartbeat_refreshes_mtime_while_held_and_stops_after_release(self):
        with ul.ue_lock("probe", owner="t", poll_s=0.05, lock=self.lock) as info:
            backdate(self.lock)
            self.assertGreater(age(self.lock), OLD - 5)
            self.assertTrue(wait_until(lambda: age(self.lock) < 5), "mtime was not refreshed while held")
            self.assertGreater(info["heartbeats"], 0)
        self.assertFalse(self.lock.exists())
        self.assertFalse(any(t.name == "ue-lock-heartbeat" and t.is_alive() for t in threading.enumerate()))

    def test_waiter_does_not_take_over_a_long_held_lock(self):
        """A held step that outlives stale_s keeps its lock: the waiter waits instead of taking it over."""
        got = {}
        with ul.ue_lock("long step", owner="holder", poll_s=0.05, lock=self.lock):
            backdate(self.lock)
            self.assertTrue(wait_until(lambda: age(self.lock) < 5))

            def waiter():
                with ul.ue_lock("next", owner="waiter", poll_s=0.05, stale_s=2.0, lock=self.lock) as w:
                    got.update(w)

            th = threading.Thread(target=waiter, daemon=True)
            th.start()
            time.sleep(0.5)
            self.assertFalse(got, "the waiter took the lock while it was held")
            self.assertTrue(self.lock.read_text(encoding="utf-8").startswith("holder "))
        th.join(timeout=5.0)
        self.assertIsNone(got.get("stale_taken"))
        self.assertTrue(got["stamp"].startswith("waiter "))
        self.assertFalse(self.lock.exists())

    def test_heartbeat_never_touches_a_foreign_lock(self):
        with ul.ue_lock("probe", owner="t", poll_s=0.05, lock=self.lock) as info:
            self.lock.write_text("someone-else 2026-10-14T00:00:00+00:00 other step\n", encoding="utf-8")
            backdate(self.lock)
            time.sleep(0.4)
            self.assertGreater(age(self.lock), OLD - 5, "the heartbeat refreshed a lock that is not ours")
            beats = info["heartbeats"]
        self.assertTrue(self.lock.exists())        # not ours: the finally block leaves it alone
        self.assertEqual(info["heartbeats"], beats)

    def test_heartbeat_can_be_turned_off(self):
        with ul.ue_lock("probe", owner="t", poll_s=0.05, lock=self.lock, heartbeat_s=0) as info:
            backdate(self.lock)
            time.sleep(0.3)
            self.assertGreater(age(self.lock), OLD - 5)
            self.assertEqual(info["heartbeats"], 0)
        self.assertFalse(self.lock.exists())

    def test_default_interval_is_poll_s(self):
        self.assertEqual(ul.POLL_S, 20.0)
        self.assertLess(ul.POLL_S, ul.STALE_S)


def dead_pid() -> int:
    """PID of a process of this machine that has already exited."""
    p = subprocess.Popen([sys.executable, "-c", "pass"])
    p.wait()
    return p.pid


class UeLockHolderTests(unittest.TestCase):
    """Review gap R-02 (2026-10-14): PID and host in the lock, max hold, wait timeout, dead-PID staleness."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.lock = Path(self._tmp.name) / "ue-editor.lock"

    def tearDown(self):
        self._tmp.cleanup()

    def write_foreign(self, owner="ghost", pid=None, host=None, since=None, max_hold_s=7200, old_format=False):
        if old_format:
            text = "%s 2026-10-14T00:00:00+00:00 old step" % owner
        else:
            text = ul.lock_content(owner, "foreign step", max_hold_s, since=since, pid=pid, host=host)
        self.lock.write_text(text + "\n", encoding="utf-8")
        return text

    def test_defaults(self):
        self.assertEqual(ul.MAX_HOLD_S, 2 * 3600.0)
        self.assertIsNone(ul.WAIT_TIMEOUT_S)
        self.assertGreater(ul.MAX_HOLD_S, ul.STALE_S)

    def test_lock_carries_pid_host_and_max_hold(self):
        with ul.ue_lock("probe", owner="t", poll_s=0.05, lock=self.lock, max_hold_s=60) as info:
            text = self.lock.read_text(encoding="utf-8")
            h = ul.parse_lock(text)
            self.assertEqual(text.splitlines()[0], info["stamp"])     # first line: "<owner> <ISO time> <step>" as before
            self.assertTrue(info["stamp"].startswith("t ") and info["stamp"].endswith(" probe"))
            self.assertEqual((h["owner"], h["step"], h["pid"], h["host"]), ("t", "probe", os.getpid(), ul.HOST))
            self.assertEqual(h["max_hold_s"], 60.0)
            self.assertLess(abs(h["since"] - time.time()), 5)
            self.assertEqual((info["pid"], info["host"], info["max_hold_s"]), (os.getpid(), ul.HOST, 60))
        self.assertFalse(self.lock.exists())

    def test_parse_old_format_lock(self):
        h = ul.parse_lock("look-dev-C 2026-10-14T00:00:00+00:00 ue_v2 capture P1\n")
        self.assertEqual((h["owner"], h["step"], h["pid"], h["host"], h["max_hold_s"]),
                         ("look-dev-C", "ue_v2 capture P1", None, None, None))

    def test_pid_alive(self):
        self.assertTrue(ul.pid_alive(os.getpid()))
        self.assertFalse(ul.pid_alive(dead_pid()))
        self.assertFalse(ul.pid_alive(None))

    def test_heartbeat_stops_after_max_hold(self):
        with ul.ue_lock("hung", owner="t", poll_s=0.05, lock=self.lock, max_hold_s=0.3) as info:
            self.assertTrue(wait_until(lambda: info["max_hold_exceeded"]), "the heartbeat did not stop at max_hold_s")
            beats = info["heartbeats"]
            backdate(self.lock)
            time.sleep(0.3)
            self.assertGreater(age(self.lock), OLD - 5, "the heartbeat refreshed the lock after max_hold_s")
            self.assertEqual(info["heartbeats"], beats)
        self.assertFalse(self.lock.exists())  # still ours: deleted as before

    def test_waiter_takes_over_a_lock_held_past_its_max_hold(self):
        got = {}
        with ul.ue_lock("hung step", owner="holder", poll_s=0.05, lock=self.lock, max_hold_s=0.4) as held:
            def waiter():
                with ul.ue_lock("next", owner="waiter", poll_s=0.05, stale_s=1000.0, lock=self.lock) as w:
                    got.update(w)

            th = threading.Thread(target=waiter, daemon=True)
            th.start()
            time.sleep(0.2)
            self.assertFalse(got, "taken before max_hold_s")
            th.join(timeout=5.0)
            self.assertEqual(got["stale_taken"]["reason"], "max_hold")
            self.assertEqual(got["stale_taken"]["holder"]["owner"], "holder")
            self.assertTrue(wait_until(lambda: held["max_hold_exceeded"]))
        self.assertFalse(self.lock.exists())

    def test_dead_pid_on_this_host_is_stale_at_once(self):
        pid = dead_pid()
        self.write_foreign(pid=pid, host=ul.HOST)
        t0 = time.monotonic()
        with ul.ue_lock("next", owner="waiter", poll_s=0.05, stale_s=1000.0, lock=self.lock) as w:
            self.assertEqual(w["stale_taken"]["reason"], "dead_pid")
            self.assertEqual(w["stale_taken"]["holder"]["pid"], pid)
        self.assertLess(time.monotonic() - t0, 2.0)
        kept = list(Path(self._tmp.name).glob("ue-editor.lock.stale.*"))
        self.assertEqual(len(kept), 1)

    def test_dead_pid_on_another_host_is_not_judged(self):
        pid = dead_pid()
        self.write_foreign(pid=pid, host="OTHER-HOST")
        with self.assertRaises(ul.UeLockTimeout) as cm:
            with ul.ue_lock("next", owner="waiter", poll_s=0.05, stale_s=1000.0, lock=self.lock, wait_timeout_s=0.3):
                self.fail("took a lock of another host")
        self.assertIn("ghost", str(cm.exception))
        self.assertIn(str(pid), str(cm.exception))
        self.assertTrue(self.lock.exists())

    def test_wait_timeout_names_owner_and_pid(self):
        errors = []
        with ul.ue_lock("long step", owner="holder", poll_s=0.05, lock=self.lock):
            def waiter():
                try:
                    with ul.ue_lock("next", owner="waiter", poll_s=0.05, lock=self.lock, wait_timeout_s=0.3):
                        errors.append("acquired")
                except ul.UeLockTimeout as exc:
                    errors.append(exc)

            t0 = time.monotonic()
            th = threading.Thread(target=waiter, daemon=True)
            th.start()
            th.join(timeout=5.0)
            self.assertLess(time.monotonic() - t0, 3.0)
        self.assertEqual(len(errors), 1)
        exc = errors[0]
        self.assertIsInstance(exc, ul.UeLockTimeout)
        self.assertIsInstance(exc, TimeoutError)
        self.assertEqual((exc.holder["owner"], exc.holder["pid"]), ("holder", os.getpid()))
        self.assertIn("'holder'", str(exc))
        self.assertIn("pid %d" % os.getpid(), str(exc))
        self.assertIn("long step", str(exc))

    def test_old_format_lock_waits_then_is_stale_by_mtime(self):
        self.write_foreign(old_format=True)
        with self.assertRaises(ul.UeLockTimeout):
            with ul.ue_lock("next", owner="waiter", poll_s=0.05, stale_s=2.0, lock=self.lock, wait_timeout_s=0.2):
                pass
        backdate(self.lock)
        with ul.ue_lock("next", owner="waiter", poll_s=0.05, stale_s=2.0, lock=self.lock) as w:
            self.assertEqual(w["stale_taken"]["reason"], "mtime")

    def test_max_hold_zero_means_no_limit(self):
        with ul.ue_lock("probe", owner="t", poll_s=0.05, lock=self.lock, max_hold_s=0) as info:
            self.assertIsNone(ul.parse_lock(self.lock.read_text(encoding="utf-8"))["max_hold_s"])
            time.sleep(0.3)
            self.assertFalse(info["max_hold_exceeded"])
            self.assertGreater(info["heartbeats"], 0)


class UeLockCliTests(unittest.TestCase):
    TOOL = HERE.parent / "ue_lock.py"

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.lock = Path(self._tmp.name) / "ue-editor.lock"
        self.env = dict(os.environ, UE_EDITOR_LOCK=str(self.lock), UE_LOCK_OWNER="cli-test", PYTHONIOENCODING="utf-8")
        self.env.pop("UE_LOCK_WAIT_TIMEOUT_S", None)
        self.env.pop("UE_LOCK_MAX_HOLD_S", None)

    def tearDown(self):
        self._tmp.cleanup()

    def run_cli(self, *args, timeout=60):
        return subprocess.run([sys.executable, str(self.TOOL), *args], capture_output=True, env=self.env,
                              timeout=timeout)

    def test_cli_runs_the_command_and_writes_cmd_into_the_lock(self):
        show = "import os, sys; print(open(os.environ['UE_EDITOR_LOCK'], encoding='utf-8').read()); sys.exit(7)"
        p = self.run_cli("--step", "probe", "--max-hold", "120", "--", sys.executable, "-c", show)
        out = p.stdout.decode("utf-8")
        self.assertEqual(p.returncode, 7, p.stderr.decode("utf-8", "replace"))
        h = ul.parse_lock(out.split("UE LOCK: held", 1)[1].split("\n", 1)[1])
        self.assertEqual((h["owner"], h["step"], h["max_hold_s"]), ("cli-test", "probe", 120.0))
        self.assertIsNotNone(h["pid"])
        self.assertIn("-c", h["cmd"])
        self.assertFalse(self.lock.exists())

    def test_cli_wait_timeout_exit_code(self):
        with ul.ue_lock("held by test", owner="holder", poll_s=0.05, lock=self.lock):
            p = self.run_cli("--step", "probe", "--wait-timeout", "0.3", "--", sys.executable, "-c", "pass")
        err = p.stderr.decode("utf-8")
        self.assertEqual(p.returncode, ul.EXIT_WAIT_TIMEOUT, err)
        self.assertIn("'holder'", err)
        self.assertIn("pid %d" % os.getpid(), err)


if __name__ == "__main__":
    unittest.main()
