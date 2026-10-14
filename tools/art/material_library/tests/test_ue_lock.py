"""Tests for tools/art/material_library/ue_lock.py: the heartbeat of a held lock (RB-21, skill pilot 2026-10-13).

A lock is stale by its mtime after STALE_S (25 min). Without a heartbeat a live step longer than that was taken over
by the next agent. While held, the lock's mtime is now refreshed every POLL_S (heartbeat_s); a lock whose content is
no longer ours is never touched. Temporary lock files only, short intervals, no UE.

  python -m unittest discover -s tools/art/material_library/tests -v
"""
from __future__ import annotations

import os
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


if __name__ == "__main__":
    unittest.main()
