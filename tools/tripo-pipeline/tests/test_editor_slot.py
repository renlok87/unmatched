"""tools/tripo-pipeline/ue7a/editor_slot.py без Unreal (ДС-3a): адреса слота, окружение, командная строка, реестр,
сторож общих записей, перенос слота в ue_lock и GPU-токен съёмки.

    python -B -m pytest -q tools/tripo-pipeline/tests/test_editor_slot.py
"""
import json
import sys
import threading
import time
from pathlib import Path

import pytest

TESTS = Path(__file__).resolve().parent
sys.path.insert(0, str(TESTS.parent / "ue7a"))
import editor_slot as es  # noqa: E402

ul = es.ue_lock
UPROJ = es.UPROJECT.as_posix()


def test_slot_zero_is_the_old_single_editor():
    p = es.slot_paths(0)
    assert p["port"] == 8123 and p["url"] == "http://127.0.0.1:8123/mcp"
    assert p["lock"] == "C:/tmp/ue-editor.lock"
    assert ul.lock_path_for_slot(0) == ul.DEFAULT_LOCK


def test_slot_n_has_its_own_port_lock_and_drop(tmp_path):
    p = es.slot_paths(2, tmp_path / "w")
    assert p["port"] == 8125 and p["lock"] == "C:/tmp/ue-editor-slot2.lock"
    assert p["drop"] == (tmp_path / "w" / "drop").as_posix()
    env = es.slot_env(2, tmp_path / "w", "Sherlock")
    assert env == {"UE_EDITOR_SLOT": "2", "UE_MCP_URL": "http://127.0.0.1:8125/mcp",
                   "UE_EDITOR_LOCK": "C:/tmp/ue-editor-slot2.lock", "UE_CONSOLE_DROP": p["drop"],
                   "UE_LOCK_OWNER": "7a-slot2-Sherlock"}
    with pytest.raises(es.SlotError):
        es.slot_paths(10)
    with pytest.raises(ValueError):
        ul.lock_path_for_slot(-1)


def test_env_formats():
    env = {"A": "x y", "B": "it's"}
    assert es.format_env(env, "bash") == "export A='x y'\nexport B='it'\\''s'"
    assert es.format_env(env, "ps") == "$env:A = 'x y'\n$env:B = 'it''s'"
    assert json.loads(es.format_env(env, "json")) == env


def test_editor_command_follows_the_pilot_recipe():
    cmd = es.editor_command(1, Path("C:/tmp/ue7a-slot1"))
    assert cmd.startswith('"') and "UnrealEditor.exe" in cmd.split('"')[1]
    assert " -ModelContextProtocolPort=8124 " in cmd
    assert '-ExecCmds="ModelContextProtocol.StartServer 8124,py ' in cmd and 'C:/tmp/ue7a-slot1/drop"' in cmd
    assert "bAutoStartServer=False" in cmd  # the ini server never autostarts on its own port
    for flag in ("-RenderOffScreen", "-unattended", "-nosplash", "-NoSound", "-abslog=C:/tmp/ue7a-slot1/editor.log"):
        assert flag in cmd
    assert "-LiveCoding" not in cmd
    with pytest.raises(es.SlotError, match="пробел"):
        es.editor_command(1, Path("C:/tmp/with space"))


def procs(*rows):
    return [(pid, "UnrealEditor.exe", cmd) for pid, cmd in rows]


def test_editor_processes_and_our_editor():
    p1 = es.slot_paths(1, Path("C:/tmp/s1"))
    agent = es.editor_command(1, Path("C:/tmp/s1")).replace('"', "")
    rows = procs((11, agent), (12, "UnrealEditor.exe " + UPROJ + " -log"),
                 (13, "UnrealEditor.exe C:/other/X.uproject -unattended -RenderOffScreen"))
    eds = es.editor_processes(procs=rows)
    assert [(e["pid"], e["agent"], e["port"]) for e in eds] == [(11, True, 8124), (12, False, None)]
    assert es.is_our_editor(11, p1, cmdline=agent)
    assert not es.is_our_editor(11, es.slot_paths(2, Path("C:/tmp/s1")), cmdline=agent)  # другой порт
    assert not es.is_our_editor(12, p1, cmdline=rows[1][2])


def test_shared_write_guard():
    one = procs((11, es.editor_command(1, Path("C:/tmp/s1")).replace('"', "")))
    two = one + procs((12, es.editor_command(2, Path("C:/tmp/s2")).replace('"', "")))
    assert len(es.shared_write_guard("um_masters build", procs=one, environ={})) == 1
    with pytest.raises(es.SharedWriteRefused, match="um_masters build"):
        es.shared_write_guard("um_masters build", procs=two, environ={})
    assert len(es.shared_write_guard("x", procs=two, environ={"UE7A_SHARED_WRITE_OK": "1"})) == 2


def test_registry_update_and_live_entries(tmp_path):
    reg = tmp_path / "slots.json"
    es.update_registry(lambda d: d["slots"].__setitem__("1", {"pid": 999999, "hero": "A"}), path=reg)
    import os
    es.update_registry(lambda d: d["slots"].__setitem__("2", {"pid": os.getpid(), "hero": "B"}), path=reg)
    doc = es.load_registry(reg)
    assert doc["schema"] == "unmatched.ue7a-slots/1" and set(doc["slots"]) == {"1", "2"}
    assert set(es.live_entries(doc)) == {"2"}  # PID 999999 мёртв
    assert not Path(str(reg) + ".lock").exists()


def test_drop_command_protocol(tmp_path):
    drop = tmp_path / "drop"
    drop.mkdir()
    with pytest.raises(es.SlotError, match="ready.json"):
        es.drop_command(str(drop), "quit-editor", wait_done=False)
    (drop / "ready.json").write_text("{}", encoding="utf-8")

    def editor():  # поддельный console_drop.py
        for _ in range(100):
            for f in drop.glob("cmd-*.json"):
                cmd = json.loads(f.read_text(encoding="utf-8"))
                f.rename(str(f) + ".taken")
                (drop / ("done-%d.json" % cmd["seq"])).write_text(json.dumps({"seq": cmd["seq"], "ok": True}),
                                                                   encoding="utf-8")
                return
            time.sleep(0.05)

    t = threading.Thread(target=editor)
    t.start()
    assert es.drop_command(str(drop), "stat fps", wait_s=10)["ok"] is True
    t.join()


def test_ue_lock_env_and_cli_slot(tmp_path, monkeypatch):
    assert ul.env_lock_path({}) == ul.DEFAULT_LOCK
    assert ul.env_lock_path({"UE_EDITOR_SLOT": "3"}) == Path("C:/tmp/ue-editor-slot3.lock")
    assert ul.env_lock_path({"UE_EDITOR_SLOT": "3", "UE_EDITOR_LOCK": "D:/x.lock"}) == Path("D:/x.lock")
    lock = tmp_path / "x.lock"
    rc = ul.main(["--lock", str(lock), "--step", "probe", "--", sys.executable, "-c",
                  "import pathlib,sys; sys.exit(0 if pathlib.Path(%r).is_file() else 5)" % str(lock)])
    assert rc == 0 and not lock.exists()


def test_two_slot_locks_do_not_wait_for_each_other(tmp_path):
    a, b = tmp_path / "slot1.lock", tmp_path / "slot2.lock"
    with ul.ue_lock("hero A import", lock=a, heartbeat_s=0):
        t0 = time.time()
        with ul.ue_lock("hero B import", lock=b, heartbeat_s=0, wait_timeout_s=1.0) as info:
            assert info["waited_s"] < 0.5
        with pytest.raises(ul.UeLockTimeout):
            with ul.ue_lock("hero A second step", lock=a, poll_s=0.1, wait_timeout_s=0.3):
                pass
        assert time.time() - t0 < 5


def test_capture_gpu_token_only_in_slot_mode(tmp_path):
    gpu = tmp_path / "gpu.lock"
    with ul.capture_gpu_token("frames", lock=gpu, environ={}) as info:
        assert info["taken"] is False and not gpu.exists()
    with ul.capture_gpu_token("frames", lock=gpu, environ={"UE_EDITOR_SLOT": "1"}) as info:
        assert info["taken"] is True and gpu.is_file()
    assert not gpu.exists()
    with ul.capture_gpu_token("frames", lock=gpu, environ={"UE_EDITOR_SLOT": "1", "UE_CAPTURE_GPU_TOKEN": "0"}) as info:
        assert info["taken"] is False
    assert ul.capture_token_wanted({"UE_CAPTURE_GPU_TOKEN": "1"})


def test_capture_gpu_token_waits_for_a_bench_token(tmp_path):
    """A live_tune.py token (one line, no pid line, old mtime) is never taken over: the capture waits."""
    gpu = tmp_path / "gpu.lock"
    gpu.write_text("owner=LIVE-TUNE pid=4242 2026-10-21T10:00:00 live-tune bench marmoreal x\n", encoding="utf-8")
    import os
    old = time.time() - 3 * 3600
    os.utime(gpu, (old, old))
    with pytest.raises(ul.UeLockTimeout):
        with ul.capture_gpu_token("frames", lock=gpu, wait_timeout_s=0.3, poll_s=0.1, environ={"UE_EDITOR_SLOT": "1"}):
            pass
    assert gpu.read_text(encoding="utf-8").startswith("owner=LIVE-TUNE")
