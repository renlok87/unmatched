#!/usr/bin/env python3
"""Live tune: parameter iterations in ONE running Unmatched client (tools/art/render/LIVE-TUNE.md, AGENTS.md "Iteration speed").

The client runs the -Bench fixture with -ArtLiveTune=<session dir> and serves a file protocol (S08LiveTune.h): this driver
writes <dir>/cmd-<seq>.json and waits for <dir>/done-<seq>.json. No sockets. One session at a time; it holds
C:/tmp/unmatched-gpu.lock (owner=LIVE-TUNE pid=<client pid> map=<map>) from start to stop.

  python tools/art/render/live_tune.py start --map sarpedon|marmoreal|cobble [--packaged] [--profiles <json>]
                                             [--env-dir <dir>] [--warmup 60] [--extra=-NoHeroLight ...]
  python tools/art/render/live_tune.py reload [--profiles <json>] [--env-dir <dir>]
  python tools/art/render/live_tune.py shot  --views K1+K2x1.6+K2x2.5 --out <dir> [--tag t] [--settle 6] [--measure 0]
                                             [--post 0] [--live] [--clock bench|free] [--append]
  python tools/art/render/live_tune.py cycle --views ... --out <dir> [--tag t]      (reload, then shot)
  python tools/art/render/live_tune.py state
  python tools/art/render/live_tune.py stop
  python tools/art/render/live_tune.py bench --map sarpedon --views K1+K2x1.6+K2x2.5 --out <dir> [--packaged]  (fresh -Bench)
  python tools/art/render/live_tune.py compare --a <run dir> --b <run dir> [--views K1+K2x1.6]   (fidelity numbers)
  python tools/art/render/live_tune.py --check                                     (self-test, fake client, no UE)

Reload covers S08ArtBoardProfiles.json (light profile, fog, grade, exposure, hero light, conceptPaste incl. lit3d lights /
winds / hide, readability, backdrop, ...) and Config/ArtBoards/EnvLayouts/*.layout.json (props, lights, fx, ground,
overlays). C++ changes, new meshes / textures, material instances (ue_scene_material.py, ...), zone styles / glyph meshes
need a relaunch (stop + start). Exit codes: 0 ok, 1 the client answered ok=false (or compare failed its gate), 2 usage /
no session, 3 timeout / the client died, 4 the frames were saved but are off the render reference (RENDER fingerprint,
e.g. profilesSource=override after a reload from a non-default path or in a --packaged session).
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import tempfile
import threading
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
UPROJECT = REPO / "unreal/Unmatched/Unmatched.uproject"
UE_EDITOR = Path(os.environ.get("UE_ROOT", r"C:\Program Files\Epic Games\UE_5.8")) / "Engine/Binaries/Win64/UnrealEditor.exe"
STAGED_EXE = REPO / "unreal/Unmatched/Saved/StagedBuilds/Windows/Unmatched.exe"
PROFILES = REPO / "unreal/Unmatched/Config/ArtBoards/S08ArtBoardProfiles.json"
ENV_DIR = REPO / "unreal/Unmatched/Config/ArtBoards/EnvLayouts"
FIXTURES = {"sarpedon": "S08BenchSarpedon.json", "marmoreal": "S08BenchMarmoreal.json", "cobble": "S08BenchCobble.json"}
GPU_LOCK = Path(os.environ.get("UNMATCHED_GPU_LOCK", "C:/tmp/unmatched-gpu.lock"))
ROOT = Path(os.environ.get("LIVE_TUNE_ROOT", "C:/tmp/live-tune"))
POINTER = "session.json"
OWNER = "owner=LIVE-TUNE"
CREATE_NO_WINDOW = 0x08000000
CREATE_NEW_PROCESS_GROUP = 0x00000200
# the -Bench values of the reference runners (p9b run_ed.py: measure 5, run_pkg.py: measure 3; both warm-up 60, settle 6, 60 fps)
BENCH = {"editor": {"warmup": 60.0, "settle": 6.0, "measure": 5.0}, "packaged": {"warmup": 60.0, "settle": 6.0, "measure": 3.0}}
FIDELITY = {"meanAbs": 0.5, "pxOver24Pct": 0.05}


class LiveTuneError(Exception):
    def __init__(self, message: str, code: int = 1):
        super().__init__(message)
        self.code = code


# ---- processes ------------------------------------------------------------------------------------------------------

def pid_alive(pid: int) -> bool:
    if pid <= 0:
        return False
    try:
        import psutil  # noqa: PLC0415
        return psutil.pid_exists(pid) and psutil.Process(pid).status() != psutil.STATUS_ZOMBIE
    except ImportError:
        out = subprocess.run(["tasklist", "/FI", f"PID eq {pid}", "/NH"], capture_output=True, text=True,
                             creationflags=CREATE_NO_WINDOW if os.name == "nt" else 0).stdout
        return str(pid) in out
    except Exception:  # noqa: BLE001 - access denied etc.: it exists
        return True


def pid_cmdline(pid: int) -> str:
    try:
        import psutil  # noqa: PLC0415
        return " ".join(psutil.Process(pid).cmdline())
    except Exception:  # noqa: BLE001
        return ""


def kill_own(pid: int, marker: str) -> bool:
    """Kill pid only when its command line carries this session's marker (-ArtLiveTune=<dir>)."""
    cmd = pid_cmdline(pid)
    if not cmd or marker.replace("\\", "/").lower() not in cmd.replace("\\", "/").lower():
        return False
    subprocess.run(["taskkill", "/PID", str(pid), "/T", "/F"], capture_output=True,
                   creationflags=CREATE_NO_WINDOW if os.name == "nt" else 0)
    return True


# ---- the GPU lock (atomic create, wait while present, remove only our own) -----------------------------------------

def lock_acquire(path: Path, what: str, timeout: float = 3600.0, poll: float = 10.0) -> None:
    t0 = time.time()
    said = False
    while True:
        try:
            fd = os.open(str(path), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            os.write(fd, f"{OWNER} pid={os.getpid()} {time.strftime('%Y-%m-%dT%H:%M:%S')} {what}\n".encode())
            os.close(fd)
            return
        except FileExistsError:
            if not said:
                print(f"live_tune: waiting for {path}: {lock_text(path)}", flush=True)
                said = True
            if time.time() - t0 > timeout:
                raise LiveTuneError(f"lock wait > {timeout:.0f} s: {path}: {lock_text(path)}", 3)
            time.sleep(poll)


def lock_text(path: Path) -> str:
    try:
        return path.read_text(errors="replace").strip()
    except FileNotFoundError:
        return "(gone)"


def lock_rewrite(path: Path, text: str) -> None:
    if lock_text(path).startswith(OWNER + " "):
        path.write_text(text + "\n", encoding="utf-8")


def lock_release(path: Path, pid: int | None = None) -> bool:
    """Remove the lock only when it is a LIVE-TUNE lock (and, given pid, that session's)."""
    text = lock_text(path)
    if not text.startswith(OWNER + " "):
        return False
    if pid is not None and f"pid={pid} " not in text + " ":
        return False
    try:
        path.unlink()
    except FileNotFoundError:
        return False
    return True


# ---- the file protocol ------------------------------------------------------------------------------------------------

def write_atomic(path: Path, text: str) -> None:
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(text, encoding="utf-8")
    os.replace(tmp, path)


def next_seq(session_dir: Path) -> int:
    seqs = [0]
    for p in session_dir.glob("*.json"):
        for prefix in ("cmd-", "done-"):
            if p.name.startswith(prefix) and p.name[len(prefix):-5].isdigit():
                seqs.append(int(p.name[len(prefix):-5]))
    return max(seqs) + 1


def send(session: dict, cmd: dict, timeout: float, poll: float = 0.1) -> dict:
    """Writes cmd-<seq>.json, waits for done-<seq>.json; raises when the client dies or times out."""
    d = Path(session["dir"])
    seq = next_seq(d)
    body = dict(cmd, seq=seq)
    write_atomic(d / f"cmd-{seq}.json", json.dumps(body, ensure_ascii=False))
    done = d / f"done-{seq}.json"
    t0 = time.time()
    pid = int(session.get("pid", 0))
    while True:
        if done.exists():
            try:
                res = json.loads(done.read_text(encoding="utf-8"))
                res["driverSeconds"] = round(time.time() - t0, 2)
                return res
            except json.JSONDecodeError:
                pass  # renamed into place: a half file never appears; retry once more
        if pid and not session.get("fake") and not pid_alive(pid):
            raise LiveTuneError(f"the client (pid {pid}) exited before done-{seq}.json; see {d / 'session.trace.log'}", 3)
        if time.time() - t0 > timeout:
            raise LiveTuneError(f"no done-{seq}.json within {timeout:.0f} s (action {cmd.get('action')})", 3)
        time.sleep(poll)


# ---- the session -------------------------------------------------------------------------------------------------------

def pointer_path(root: Path = ROOT) -> Path:
    return root / POINTER


def load_session(root: Path = ROOT) -> dict:
    p = pointer_path(root)
    if not p.exists():
        raise LiveTuneError(f"no live-tune session ({p} missing): run 'live_tune.py start --map ...'", 2)
    return json.loads(p.read_text(encoding="utf-8"))


def bench_args(mode: str, map_key: str, out: Path, views: str, bench: dict, extra: list[str]) -> list[str]:
    """A fresh -Bench run with the reference runners' arguments (p9b run_ed.py / run_pkg.py): the fidelity reference."""
    args = client_args(mode, map_key, out, 0.0, bench, None, None, extra)
    args = [x for x in args if not x.startswith(("-ArtLiveTune=", "-ArtLiveTuneWarmup=", "-BenchOut=", "-BenchViews=", "-S08Trace="))]
    i = args.index("-BenchNoProfileGPU")
    return args[:i] + [f"-BenchOut={out}", f"-BenchViews={views}", f"-S08Trace={out / 'bench.trace.log'}"] + args[i:]


def client_args(mode: str, map_key: str, session_dir: Path, warmup: float, bench: dict, profiles: str | None,
                env_dir: str | None, extra: list[str], art_view: bool = False) -> list[str]:
    fixture = FIXTURES[map_key]
    # art_view (Art Tuner, docs/art-pipeline/ART-TUNER-PLAN.md): -ArtView=<map> instead of -Bench - the same fixture scene
    # without the -Bench freeze (Niagara, flicker, wind and the hero breath run live), the free camera keys work
    common = ["/Game/S08/S08Arena?game=/Script/Unmatched.S08FlowGameMode", "-windowed", "-resx=1920", "-resy=1080", "-ForceRes",
              "-RenderOffScreen", "-nosplash", "-unattended", "-NoSound", "-ArtPreview", "-ArtPreviewDiorama",
              "-ArtPreviewHeroesV2", f"-ArtView={map_key}" if art_view else "-Bench"]
    if mode == "packaged":
        args = [str(STAGED_EXE)] + common + [f"-BenchFixture=../../../Unmatched/Config/Bench/{fixture}"]
    else:
        args = [str(UE_EDITOR), str(UPROJECT), common[0], "-game"] + common[1:] + [
            f"-BenchFixture={REPO / 'unreal/Unmatched/Config/Bench' / fixture}"]
    args += [f"-ArtLiveTune={session_dir}", f"-ArtLiveTuneWarmup={warmup:g}", f"-BenchOut={session_dir}", "-BenchViews=K1",
             f"-BenchWarmup={bench['warmup']:g}", f"-BenchSettle={bench['settle']:g}", f"-BenchMeasure={bench['measure']:g}",
             "-BenchNoProfileGPU", "-BenchFps=60", "-S08RenderPreset=High", f"-S08Trace={session_dir / 'session.trace.log'}",
             f"-abslog={session_dir / 'client.log'}", "-ExecCmds=DisableAllScreenMessages"]
    if profiles:
        args.append(f"-ArtBoardProfiles={profiles}")
    if env_dir:
        args.append(f"-ArtEnvLayouts={env_dir}")
    return args + list(extra)


def wait_ready(session: dict, timeout: float) -> dict:
    d = Path(session["dir"])
    ready = d / "ready.json"
    t0 = time.time()
    while True:
        if ready.exists():
            try:
                return json.loads(ready.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                pass
        if not session.get("fake") and not pid_alive(int(session["pid"])):
            raise LiveTuneError(f"the client exited during start-up; see {d / 'session.trace.log'} / client.log", 3)
        if time.time() - t0 > timeout:
            raise LiveTuneError(f"no ready.json within {timeout:.0f} s", 3)
        time.sleep(0.5)


def cmd_start(a: argparse.Namespace) -> int:
    root = Path(a.root)
    p = pointer_path(root)
    if p.exists():
        old = json.loads(p.read_text(encoding="utf-8"))
        if old.get("fake") or pid_alive(int(old.get("pid", 0))):
            raise LiveTuneError(f"a session is running (pid {old.get('pid')}, map {old.get('map')}): stop it first", 2)
        lock_release(GPU_LOCK if not a.lock else Path(a.lock), int(old.get("pid", 0)))
        p.unlink()
    mode = "packaged" if a.packaged else "editor"
    exe = STAGED_EXE if a.packaged else UE_EDITOR
    if not exe.exists():
        raise LiveTuneError(f"{exe} missing ({'package-client.ps1' if a.packaged else 'UE install'})", 2)
    bench = dict(BENCH[mode])
    for k in ("warmup", "settle", "measure"):
        v = getattr(a, f"bench_{k}")
        if v is not None:
            bench[k] = v
    session_dir = (Path(a.session) if a.session else root / f"{a.map}-{time.strftime('%Y%m%d-%H%M%S')}").resolve()
    session_dir.mkdir(parents=True, exist_ok=True)
    warmup = a.warmup if a.warmup is not None else bench["warmup"]
    # the packaged client reads the pak at start; its reloads read the worktree files (profilesSource=override)
    reload_profiles = a.profiles or (str(PROFILES) if a.packaged else None)
    reload_env = a.env_dir or (str(ENV_DIR) if a.packaged else None)
    extra = list(a.extra or [])
    if getattr(a, "tuner", False) or getattr(a, "tuner_file", None):
        extra.append("-ArtTuner")
    if getattr(a, "tuner_file", None):
        extra.append(f"-ArtTunerFile={Path(a.tuner_file).resolve().as_posix()}")
    args = client_args(mode, a.map, session_dir, warmup, bench, a.profiles, a.env_dir, extra,
                       art_view=getattr(a, "art_view", False))
    lock = Path(a.lock) if a.lock else GPU_LOCK
    lock_acquire(lock, f"live-tune {a.map} starting", timeout=a.lock_timeout)
    t0 = time.time()
    try:
        proc = subprocess.Popen(args, cwd=str(exe.parent), stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                                stderr=subprocess.DEVNULL, close_fds=True,
                                creationflags=(CREATE_NO_WINDOW | CREATE_NEW_PROCESS_GROUP) if os.name == "nt" else 0)
    except OSError as e:
        lock_release(lock)
        raise LiveTuneError(f"launch failed: {e}", 3) from e
    lock_rewrite(lock, f"{OWNER} pid={proc.pid} map={a.map} session={session_dir} {time.strftime('%Y-%m-%dT%H:%M:%S')} live-tune")
    session = {"pid": proc.pid, "dir": str(session_dir).replace("\\", "/"), "map": a.map, "mode": mode, "lock": str(lock),
               "started": time.strftime("%Y-%m-%dT%H:%M:%S"), "bench": bench, "warmup": warmup,
               "reloadProfiles": reload_profiles, "reloadEnvDir": reload_env, "marker": f"-ArtLiveTune={session_dir}",
               "cmdline": subprocess.list2cmdline(args)}
    (session_dir / "cmdline.txt").write_text(session["cmdline"] + "\n", encoding="utf-8")
    write_atomic(p, json.dumps(session, indent=2))
    try:
        ready = wait_ready(session, a.timeout)
    except LiveTuneError:
        if pid_alive(proc.pid):
            kill_own(proc.pid, session["marker"])
        lock_release(lock, proc.pid)
        p.unlink(missing_ok=True)
        raise
    session["readySeconds"] = round(time.time() - t0, 1)
    write_atomic(p, json.dumps(session, indent=2))
    print(json.dumps({"ok": True, "pid": proc.pid, "dir": session["dir"], "map": a.map, "mode": mode,
                      "readySeconds": session["readySeconds"], "profile": (ready.get("board") or {}).get("profile"),
                      "profilesSha256": (ready.get("profiles") or {}).get("sha256"),
                      "renderReference": ready.get("renderReference")}, indent=2))
    return 0


def reload_cmd(session: dict, profiles: str | None, env_dir: str | None) -> dict:
    cmd: dict = {"action": "reload"}
    profiles = profiles or session.get("reloadProfiles")
    env_dir = env_dir or session.get("reloadEnvDir")
    if profiles:
        cmd["profiles"] = str(Path(profiles).resolve()).replace("\\", "/")
    if env_dir:
        cmd["envDir"] = str(Path(env_dir).resolve()).replace("\\", "/")
    return cmd


def shot_cmd(a: argparse.Namespace) -> dict:
    cmd: dict = {"action": "shot", "views": a.views, "out": str(Path(a.out).resolve()).replace("\\", "/")}
    for key, attr in (("tag", "tag"), ("settle", "settle"), ("measure", "measure"), ("post", "post"), ("warmup", "shot_warmup"),
                      ("clock", "clock")):
        v = getattr(a, attr, None)
        if v is not None:
            cmd[key] = v
    if getattr(a, "live", False):
        cmd["live"] = True
    if getattr(a, "append", False):
        cmd["append"] = True
    if getattr(a, "no_fresh", False):
        cmd["fresh"] = False
    bench = {}
    if getattr(a, "bench_gap", None) is not None:
        bench["gap"] = a.bench_gap
    if getattr(a, "bench_gap_later", None) is not None:
        bench["gapLater"] = a.bench_gap_later
    if bench:
        cmd["bench"] = bench
    return cmd


def shot_timeout(cmd: dict) -> float:
    n = len(cmd["views"].split("+"))
    per = float(cmd.get("settle", 6.0)) + float(cmd.get("measure", 0.0)) + float(cmd.get("post", 0.0)) + 45.0
    return 60.0 + float(cmd.get("warmup", 0.0)) + n * per


def report(res: dict, fingerprint: bool = True) -> int:
    if fingerprint and res.get("action") == "shot" and res.get("ok"):
        res["fingerprints"] = check_fingerprints(res)
    print(json.dumps(res, ensure_ascii=False, indent=2))
    if not res.get("ok"):
        return 1
    if any(not f.get("reference") for f in res.get("fingerprints", [])):
        return 4  # saved, but off docs/art-pipeline/render-reference.json (e.g. profilesSource=override)
    return 0


def check_fingerprints(res: dict, ref: dict | None = None) -> list[dict]:
    """render_fingerprint.py check of every PNG against docs/art-pipeline/render-reference.json (or ref)."""
    sys.path.insert(0, str(REPO / "tools/art"))
    try:
        import render_fingerprint as RF  # noqa: PLC0415
    except ImportError:
        return []
    files = [Path(f) for f in res.get("files", [])]
    trace = next((f for f in files if f.name == "bench.trace.log"), None)
    if trace is None or not trace.exists():
        return []
    ref = ref or RF.load_reference()
    out = []
    for f in files:
        if f.suffix.lower() == ".png":
            r = RF.evaluate(trace, f.name, ref)
            out.append({"shot": f.name, "reference": r["reference"], "reasons": r["reasons"]})
    return out


def cmd_reload(a):
    s = load_session(Path(a.root))
    return report(send(s, reload_cmd(s, a.profiles, a.env_dir), a.timeout or 180.0))


def cmd_shot(a):
    s = load_session(Path(a.root))
    cmd = shot_cmd(a)
    return report(send(s, cmd, a.timeout or shot_timeout(cmd)), not a.no_fingerprint)


def cmd_cycle(a):
    s = load_session(Path(a.root))
    t0 = time.time()
    r = send(s, reload_cmd(s, a.profiles, a.env_dir), 180.0)
    if not r.get("ok"):
        return report(r)
    cmd = shot_cmd(a)
    res = send(s, cmd, a.timeout or shot_timeout(cmd))
    res["reload"] = {k: r.get(k) for k in ("ok", "ms", "revision", "sha256", "source", "buildCount", "warnings")}
    res["cycleSeconds"] = round(time.time() - t0, 1)
    return report(res, not a.no_fingerprint)


def cmd_state(a):
    s = load_session(Path(a.root))
    return report(send(s, {"action": "state"}, a.timeout or 60.0))


# ---- Art Tuner (docs/art-pipeline/ART-TUNER-PLAN.md section 8): the panel's code path, driven by an agent ----

def parse_value(text: str):
    """--value: JSON (7.5, true, "#FFE0C0", [0.6, 0.7, 1.0]); a bare word is taken as a string."""
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return text


def tune_cmd(a: argparse.Namespace) -> dict:
    sets = list(a.set or [])
    if a.pointer is not None:
        sets.insert(0, f"{a.pointer}={a.value}")
    entries = []
    for item in sets:
        if "=" not in item:
            raise LiveTuneError(f"--set needs <pointer or row id>=<json value>: {item}", 2)
        pointer, value = item.split("=", 1)
        entries.append({"pointer": pointer, "value": parse_value(value)})
    if not entries:
        raise LiveTuneError("tune: give --pointer/--value or --set pointer=value", 2)
    return {"action": "tune", "entries": entries}


def cmd_tune(a):
    s = load_session(Path(a.root))
    return report(send(s, tune_cmd(a), a.timeout or 60.0))


def cmd_tuner_state(a):
    s = load_session(Path(a.root))
    return report(send(s, {"action": "tunerState"}, a.timeout or 60.0))


def cmd_tuner_save(a):
    s = load_session(Path(a.root))
    cmd = {"action": "tunerSave"}
    if a.file:
        cmd["file"] = Path(a.file).resolve().as_posix()
    return report(send(s, cmd, a.timeout or 60.0))


def cmd_tuner_reset(a):
    s = load_session(Path(a.root))
    cmd = {"action": "tunerReset"}
    if a.group:
        cmd["group"] = a.group
    return report(send(s, cmd, a.timeout or 60.0))


def cmd_tuner_panel(a):
    s = load_session(Path(a.root))
    return report(send(s, {"action": "tunerPanel", "open": a.state == "open"}, a.timeout or 60.0))


def art_view_cmd(a: argparse.Namespace) -> dict:
    cmd: dict = {"action": "artView"}
    for key in ("view", "yaw", "pitch", "select"):
        v = getattr(a, key, None)
        if v is not None:
            cmd[key] = v
    if a.pan is not None:
        cmd["pan"] = [float(x) for x in a.pan.split(",")]
    for key in ("hero_light", "pause", "help"):
        v = getattr(a, key, None)
        if v is not None:
            cmd[{"hero_light": "heroLight"}.get(key, key)] = v == "on"
    return cmd


def cmd_art_view(a):
    s = load_session(Path(a.root))
    return report(send(s, art_view_cmd(a), a.timeout or 60.0))


def cmd_stop(a):
    root = Path(a.root)
    s = load_session(root)
    pid = int(s["pid"])
    lock = Path(s.get("lock") or GPU_LOCK)
    out = {"pid": pid, "quit": None, "killed": False}
    if s.get("fake") or pid_alive(pid):
        try:
            out["quit"] = send(s, {"action": "quit"}, a.timeout or 60.0).get("ok")
        except LiveTuneError as e:
            out["quitError"] = str(e)
        t0 = time.time()
        while not s.get("fake") and pid_alive(pid) and time.time() - t0 < 60.0:
            time.sleep(0.5)
        if not s.get("fake") and pid_alive(pid):
            out["killed"] = kill_own(pid, s["marker"])
    out["lockReleased"] = lock_release(lock, pid)
    pointer_path(root).unlink(missing_ok=True)
    print(json.dumps(out, indent=2))
    return 0


def cmd_bench(a):
    """One fresh -Bench launch (the frames live tune is proven against), under the GPU lock."""
    mode = "packaged" if a.packaged else "editor"
    bench = dict(BENCH[mode])
    for k in ("warmup", "settle", "measure"):
        v = getattr(a, f"bench_{k}")
        if v is not None:
            bench[k] = v
    out = Path(a.out).resolve()
    out.mkdir(parents=True, exist_ok=True)
    args = bench_args(mode, a.map, out, a.views, bench, a.extra or [])
    (out / "cmdline.txt").write_text(subprocess.list2cmdline(args) + "\n", encoding="utf-8")
    lock = Path(a.lock) if a.lock else GPU_LOCK
    lock_acquire(lock, f"live-tune bench {a.map} {out.name}", timeout=a.lock_timeout)
    t0 = time.time()
    try:
        exe = STAGED_EXE if a.packaged else UE_EDITOR
        p = subprocess.Popen(args, cwd=str(exe.parent), stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                             stderr=subprocess.DEVNULL, creationflags=CREATE_NO_WINDOW if os.name == "nt" else 0)
        lock_rewrite(lock, f"{OWNER} pid={p.pid} map={a.map} bench={out} {time.strftime('%Y-%m-%dT%H:%M:%S')}")
        try:
            p.wait(timeout=1800)
        except subprocess.TimeoutExpired:
            kill_own(p.pid, f"-BenchOut={out}")
            p.wait(30)
    finally:
        lock_release(lock)
    secs = round(time.time() - t0, 1)
    (out / "exit.txt").write_text(f"exit={p.returncode} seconds={secs:.0f}\n", encoding="utf-8")
    print(json.dumps({"ok": p.returncode == 0, "exit": p.returncode, "seconds": secs, "out": str(out)}, indent=2))
    return 0 if p.returncode == 0 else 1


# ---- fidelity numbers --------------------------------------------------------------------------------------------------

def frame_diff(a: Path, b: Path) -> dict:
    import numpy as np  # noqa: PLC0415
    from PIL import Image  # noqa: PLC0415
    x = np.asarray(Image.open(a).convert("RGB")).astype(np.int16)
    y = np.asarray(Image.open(b).convert("RGB")).astype(np.int16)
    if x.shape != y.shape:
        return {"error": f"size {x.shape} != {y.shape}"}
    d = np.abs(x - y)
    px = d.max(axis=2) > 24
    return {"meanAbs": round(float(d.mean()), 4), "pxOver24Pct": round(float(px.mean() * 100.0), 4),
            "pxOver24": int(px.sum()), "maxAbs": int(d.max())}


def noise_mask(a: Path, noise: Path, level: int = 8, grow: int = 3):
    """Pixels where two fresh -Bench runs already differ (> level in any channel), dilated by grow px: Niagara fires
    (non-deterministic emitters) and the water / falls / mist that pan with the world time (the start-up frame times
    differ per run)."""
    import numpy as np  # noqa: PLC0415
    from PIL import Image  # noqa: PLC0415
    from scipy import ndimage  # noqa: PLC0415
    x = np.asarray(Image.open(a).convert("RGB")).astype(np.int16)
    y = np.asarray(Image.open(noise).convert("RGB")).astype(np.int16)
    return ndimage.binary_dilation(np.abs(x - y).max(axis=2) > level, iterations=grow)


def frame_diff_masked(a: Path, b: Path, mask) -> dict:
    import numpy as np  # noqa: PLC0415
    from PIL import Image  # noqa: PLC0415
    x = np.asarray(Image.open(a).convert("RGB")).astype(np.int16)
    y = np.asarray(Image.open(b).convert("RGB")).astype(np.int16)
    keep = ~mask
    d = np.abs(x - y)[keep]
    px = (d.max(axis=1) > 24)
    return {"maskedPct": round(float(mask.mean() * 100.0), 3), "meanAbs": round(float(d.mean()), 4),
            "pxOver24Pct": round(float(px.sum() / mask.size * 100.0), 4), "pxOver24": int(px.sum())}


def compare_runs(a: Path, b: Path, views: list[str] | None = None, noise: Path | None = None) -> dict:
    """Gate (FIDELITY): mean |diff| <= 0.5 and pixels with a channel diff > 24 <= 0.05 % of the frame. With a second
    fresh -Bench run (noise), also the bench-to-bench numbers and the same gate outside the bench-noise mask."""
    names = sorted(p.name for p in a.glob("bench-*-1920x1080.png"))
    if views:
        names = [f"bench-{v.replace('.', 'p')}-1920x1080.png" for v in views]
    out = {"a": str(a), "b": str(b), "noise": str(noise) if noise else None, "gate": FIDELITY, "views": {}, "pass": True}
    if noise:
        out["passOutsideNoise"] = True
    for n in names:
        if not (a / n).exists() or not (b / n).exists():
            out["views"][n] = {"error": "missing"}
            out["pass"] = False
            continue
        r = frame_diff(a / n, b / n)
        r["pass"] = "error" not in r and r["meanAbs"] <= FIDELITY["meanAbs"] and r["pxOver24Pct"] <= FIDELITY["pxOver24Pct"]
        if noise and (noise / n).exists() and "error" not in r:
            r["benchVsBench"] = frame_diff(a / n, noise / n)
            m = frame_diff_masked(a / n, b / n, noise_mask(a / n, noise / n))
            m["pass"] = m["meanAbs"] <= FIDELITY["meanAbs"] and m["pxOver24Pct"] <= FIDELITY["pxOver24Pct"]
            r["outsideBenchNoise"] = m
            out["passOutsideNoise"] = out["passOutsideNoise"] and m["pass"]
        out["views"][n] = r
        out["pass"] = out["pass"] and r["pass"]
    return out


def cmd_compare(a):
    res = compare_runs(Path(a.a), Path(a.b), a.views.split("+") if a.views else None, Path(a.noise) if a.noise else None)
    print(json.dumps(res, indent=2))
    return 0 if res["pass"] or res.get("passOutsideNoise") else 1


# ---- self-test: a fake client that speaks the protocol -------------------------------------------------------------

class FakeClient(threading.Thread):
    """Answers cmd-<seq>.json like the game: reload (invalid JSON in the profiles -> ok=false), shot (writes the PNG names +
    bench.trace.log), state, quit."""

    def __init__(self, session_dir: Path):
        super().__init__(daemon=True)
        self.dir = session_dir
        self.last = 0
        self.stop_flag = threading.Event()
        self.revision = 1
        self.tuned: dict = {}

    def run(self):
        (self.dir / "ready.json").write_text(json.dumps({"state": "ready", "board": {"profile": "fake"}}), encoding="utf-8")
        while not self.stop_flag.is_set():
            cmds = sorted(int(p.name[4:-5]) for p in self.dir.glob("cmd-*.json") if p.name[4:-5].isdigit())
            pending = [s for s in cmds if s > self.last]
            if not pending:
                time.sleep(0.02)
                continue
            seq = pending[0]
            self.last = seq
            cmd = json.loads((self.dir / f"cmd-{seq}.json").read_text(encoding="utf-8"))
            res = {"seq": seq, "action": cmd.get("action"), "ok": True, "ms": 1.0, "errors": [], "warnings": [], "files": []}
            if cmd.get("seq") != seq:
                res.update(ok=False, errors=["seq mismatch"])
            elif cmd["action"] == "reload":
                path = cmd.get("profiles")
                try:
                    if path:
                        json.loads(Path(path).read_text(encoding="utf-8"))
                    self.revision += 1
                    res["revision"] = self.revision
                except (OSError, json.JSONDecodeError) as e:
                    res.update(ok=False, errors=[f"profiles: {e}"])
            elif cmd["action"] == "shot":
                out = Path(cmd["out"])
                out.mkdir(parents=True, exist_ok=True)
                trace = out / "bench.trace.log"
                lines = ["2026.10.02-00.00.00 --- S08 trace open ---"]
                for v in cmd["views"].split("+"):
                    name = f"bench-{v.replace('.', 'p')}-1920x1080.png"
                    (out / name).write_bytes(b"\x89PNG fake")
                    lines += ["2026.10.02-00.00.01 SHOT ctx viewport=1920x1080 viewTarget=Cam cam=(0,1,2) rot=(-55,-90,0)",
                              "2026.10.02-00.00.01 RENDER tag=SHOT rhi=D3D12 reference=1",
                              f"2026.10.02-00.00.01 SHOT requested: FScreenshotRequest(bShowUI) -> {out.as_posix()}/{name}"]
                    res["files"].append(str(out / name))
                trace.write_text("\n".join(lines) + "\n", encoding="utf-8")
                res["files"].append(str(trace))
            elif cmd["action"] == "state":
                res["state"] = {"profiles": {"revision": self.revision}}
            elif cmd["action"] == "tune":
                bad = [e["pointer"] for e in cmd.get("entries", []) if not str(e.get("pointer", "")).startswith(("/", "hero", "scene"))]
                if bad:
                    res.update(ok=False, errors=[f"{p} - not a tuner row" for p in bad])
                else:
                    self.tuned.update({e["pointer"]: e["value"] for e in cmd["entries"]})
                    res["applied"] = [{"pointer": e["pointer"], "value": e["value"]} for e in cmd["entries"]]
                    res["entries"] = len(self.tuned)
            elif cmd["action"] == "tunerState":
                res["tuner"] = {"active": True, "entries": [{"pointer": k, "value": v} for k, v in self.tuned.items()]}
            elif cmd["action"] == "tunerSave":
                path = Path(cmd.get("file") or (self.dir / "overrides.json"))
                path.write_text(json.dumps({"schema": "unmatched.art-tuner-overrides/1", "boards": [
                    {"board": "fake", "entries": [{"pointer": k, "value": v} for k, v in self.tuned.items()]}]}), encoding="utf-8")
                res["files"] = [str(path)]
            elif cmd["action"] == "tunerReset":
                self.tuned.clear()
            elif cmd["action"] in ("tunerPanel", "artView"):
                res["echo"] = {k: v for k, v in cmd.items() if k not in ("seq", "action")}
            elif cmd["action"] == "quit":
                self.stop_flag.set()
            write_atomic(self.dir / f"done-{seq}.json", json.dumps(res))


def self_check() -> list[str]:
    """Runs the driver against FakeClient in a temp root (no UE, no GPU lock of the machine). Returns the failures."""
    fails: list[str] = []
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        sdir = root / "fake-session"
        sdir.mkdir()
        lock = root / "gpu.lock"
        lock_acquire(lock, "self-test", timeout=5)
        lock_rewrite(lock, f"{OWNER} pid=4242 map=fake session={sdir} live-tune")
        session = {"pid": 4242, "dir": str(sdir), "map": "fake", "mode": "fake", "lock": str(lock), "fake": True,
                   "marker": f"-ArtLiveTune={sdir}"}
        write_atomic(pointer_path(root), json.dumps(session))
        client = FakeClient(sdir)
        client.start()
        try:
            if not wait_ready(session, 5).get("state") == "ready":
                fails.append("ready.json")
            good = root / "good.json"
            good.write_text('{"revision": 2}', encoding="utf-8")
            bad = root / "bad.json"
            bad.write_text('{"revision": ', encoding="utf-8")
            r = send(session, reload_cmd(session, str(good), None), 5)
            if not (r["ok"] and r["seq"] == 1 and r["action"] == "reload"):
                fails.append(f"reload ok: {r}")
            r = send(session, reload_cmd(session, str(bad), None), 5)
            if r["ok"] or not r["errors"]:
                fails.append(f"reload bad json must fail: {r}")
            ns = argparse.Namespace(views="K1+K2x1.6", out=str(root / "shot"), tag="t", settle=None, measure=None, post=None,
                                    shot_warmup=None, clock=None, live=False, append=False)
            r = send(session, shot_cmd(ns), 5)
            names = sorted(Path(f).name for f in r["files"])
            if names != ["bench-K1-1920x1080.png", "bench-K2x1p6-1920x1080.png", "bench.trace.log"]:
                fails.append(f"shot files {names}")
            fp = check_fingerprints(r, {"requires": {"rhi": "D3D12"}})
            if [f["reference"] for f in fp] != [True, True]:
                fails.append(f"fingerprints {fp}")
            r = send(session, {"action": "state"}, 5)
            if r["state"]["profiles"]["revision"] != 2:
                fails.append(f"state {r}")
            if next_seq(sdir) != 5:
                fails.append(f"next seq {next_seq(sdir)}")
            # Art Tuner commands (the command shapes; the real checks are the UE automation tests)
            ta = argparse.Namespace(pointer="heroKey.key.lux", value="7.5", set=["/x/colorSrgb=\"#FFE0C0\"", "/x/c=[0.6, 0.7, 1]"])
            tc = tune_cmd(ta)
            if [e["value"] for e in tc["entries"]] != [7.5, "#FFE0C0", [0.6, 0.7, 1]]:
                fails.append(f"tune values {tc}")
            r = send(session, tc, 5)
            if not r["ok"] or r["entries"] != 3:
                fails.append(f"tune {r}")
            r = send(session, {"action": "tunerSave", "file": str(root / "ov.json")}, 5)
            if not r["ok"] or not (root / "ov.json").exists():
                fails.append(f"tunerSave {r}")
            av = art_view_cmd(argparse.Namespace(view="K2x1.6", yaw=-60.0, pitch=None, select=None, pan="10,-20",
                                                 hero_light="off", pause=None, help=None))
            if av != {"action": "artView", "view": "K2x1.6", "yaw": -60.0, "pan": [10.0, -20.0], "heroLight": False}:
                fails.append(f"artView cmd {av}")
            r = send(session, {"action": "tunerReset"}, 5)
            if not r["ok"]:
                fails.append(f"tunerReset {r}")
            # stop: quit answered, the lock released (ours), the pointer gone
            rc = cmd_stop(argparse.Namespace(root=str(root), timeout=5))
            if rc != 0 or lock.exists() or pointer_path(root).exists():
                fails.append("stop")
            # a foreign lock is never removed
            lock.write_text("owner=ENV-MAPS-P9B pid=1 bench\n", encoding="utf-8")
            if lock_release(lock) or not lock.exists():
                fails.append("foreign lock removed")
            # a missing done -> timeout error (exit 3)
            try:
                send({"pid": 1, "dir": str(sdir), "fake": True}, {"action": "state"}, 0.3)
                fails.append("no timeout")
            except LiveTuneError as e:
                if e.code != 3:
                    fails.append(f"timeout code {e.code}")
        finally:
            client.stop_flag.set()
            client.join(2)
    # client command lines carry the -Bench reference values and the protocol folder
    ed = client_args("editor", "sarpedon", Path("C:/tmp/lt/x"), 30, BENCH["editor"], None, None, ["-NoHeroLight"])
    for want in ("-game", "-ArtLiveTune=C:", "-BenchWarmup=60", "-BenchSettle=6", "-BenchMeasure=5", "-BenchFps=60",
                 "-S08RenderPreset=High", "-ArtLiveTuneWarmup=30", "S08BenchSarpedon.json", "-NoHeroLight"):
        if not any(want in x for x in ed):
            fails.append(f"editor args miss {want}")
    bn = bench_args("editor", "cobble", Path("C:/tmp/lt/b"), "K1+K2x1.6", BENCH["editor"], [])
    if any(x.startswith("-ArtLiveTune") for x in bn) or "-BenchViews=K1+K2x1.6" not in bn or not any(
            x.startswith("-BenchOut=") for x in bn):
        fails.append(f"bench args {bn}")
    pk = client_args("packaged", "cobble", Path("C:/tmp/lt/y"), 60, BENCH["packaged"], None, None, [])
    if "-game" in pk or not any(x.startswith("-BenchMeasure=3") for x in pk) or "Unmatched.exe" not in pk[0]:
        fails.append(f"packaged args {pk[:3]}")
    return fails


# ---- CLI ---------------------------------------------------------------------------------------------------------------

def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--check", action="store_true", help="self-test against a fake client (no UE)")
    ap.add_argument("--root", default=str(ROOT), help="session root (session.json pointer); default C:/tmp/live-tune")
    sub = ap.add_subparsers(dest="cmd")
    st = sub.add_parser("start")
    st.add_argument("--map", required=True, choices=sorted(FIXTURES))
    st.add_argument("--packaged", action="store_true")
    st.add_argument("--profiles", help="-ArtBoardProfiles at start (override); --packaged reloads read the worktree file by default")
    st.add_argument("--env-dir", help="-ArtEnvLayouts at start")
    st.add_argument("--session", help="protocol folder (default <root>/<map>-<time>)")
    st.add_argument("--warmup", type=float, help="seconds before ready (default = the bench warm-up, 60)")
    st.add_argument("--bench-warmup", type=float)
    st.add_argument("--bench-settle", type=float)
    st.add_argument("--bench-measure", type=float)
    st.add_argument("--timeout", type=float, default=900.0)
    st.add_argument("--lock", help="GPU lock path (default C:/tmp/unmatched-gpu.lock)")
    st.add_argument("--lock-timeout", type=float, default=3600.0)
    st.add_argument("--extra", action="append", help="extra client argument (repeat; use --extra=-Flag)")
    st.add_argument("--art-view", action="store_true", help="-ArtView=<map> instead of -Bench: live fx, free camera (Art Tuner)")
    st.add_argument("--tuner", action="store_true", help="-ArtTuner: the panel model (tune / tuner-* commands)")
    st.add_argument("--tuner-file", help="-ArtTunerFile=<path>: the overrides file the tuner saves / loads (implies --tuner)")
    for name in ("reload", "cycle"):
        p = sub.add_parser(name)
        p.add_argument("--profiles")
        p.add_argument("--env-dir")
        p.add_argument("--timeout", type=float)
    for name in ("shot", "cycle"):
        p = sub.choices[name] if name in sub.choices else sub.add_parser(name)
        p.add_argument("--views", required=True)
        p.add_argument("--out", required=True)
        p.add_argument("--tag")
        p.add_argument("--settle", type=float)
        p.add_argument("--measure", type=float)
        p.add_argument("--post", type=float)
        p.add_argument("--warmup", dest="shot_warmup", type=float)
        p.add_argument("--clock", choices=["bench", "free"])
        p.add_argument("--live", action="store_true")
        p.add_argument("--append", action="store_true")
        p.add_argument("--no-fresh", action="store_true", help="keep the streamer's cached mips / the Lumen surface cache")
        p.add_argument("--bench-gap", type=float, help="clock model: first bench capture -> next anchor, s (-1 = the live gap)")
        p.add_argument("--bench-gap-later", type=float, help="clock model: the same after later captures, s")
        p.add_argument("--no-fingerprint", action="store_true")
        if name == "shot":
            p.add_argument("--timeout", type=float)
    for name in ("state", "stop"):
        sub.add_parser(name).add_argument("--timeout", type=float)
    tp = sub.add_parser("tune", help="Art Tuner: set panel rows (registry pointer or row id) and apply at once")
    tp.add_argument("--pointer", help="row pointer or id, e.g. heroKey.key.lux or /lightProfiles/sarpedon-night/heroLight/key/lux")
    tp.add_argument("--value", help="JSON value: 7.5, true, \"#FFE0C0\", [0.6,0.7,1.0]")
    tp.add_argument("--set", action="append", help="<pointer or id>=<json value> (repeat)")
    tp.add_argument("--timeout", type=float)
    sub.add_parser("tuner-state", help="Art Tuner: the rows, values and entries").add_argument("--timeout", type=float)
    sp = sub.add_parser("tuner-save", help="Art Tuner: write S08ArtTuner.overrides.json")
    sp.add_argument("--file")
    sp.add_argument("--timeout", type=float)
    rp = sub.add_parser("tuner-reset", help="Art Tuner: a group (or everything) back to the profile file")
    rp.add_argument("--group")
    rp.add_argument("--timeout", type=float)
    pp = sub.add_parser("tuner-panel", help="Art Tuner: open / close the panel (shots with the panel)")
    pp.add_argument("state", choices=["open", "close"])
    pp.add_argument("--timeout", type=float)
    vp = sub.add_parser("art-view", help="-ArtView camera / keys: view, orbit, pan, selection, hero light, pause, help")
    vp.add_argument("--view")
    vp.add_argument("--yaw", type=float)
    vp.add_argument("--pitch", type=float)
    vp.add_argument("--pan", help="x,y uu")
    vp.add_argument("--select", help="fighter id ('' clears)")
    vp.add_argument("--hero-light", choices=["on", "off"])
    vp.add_argument("--pause", choices=["on", "off"])
    vp.add_argument("--help-card", dest="help", choices=["on", "off"])
    vp.add_argument("--timeout", type=float)
    bp = sub.add_parser("bench", help="one fresh -Bench launch (the fidelity reference)")
    bp.add_argument("--map", required=True, choices=sorted(FIXTURES))
    bp.add_argument("--views", required=True)
    bp.add_argument("--out", required=True)
    bp.add_argument("--packaged", action="store_true")
    bp.add_argument("--bench-warmup", type=float)
    bp.add_argument("--bench-settle", type=float)
    bp.add_argument("--bench-measure", type=float)
    bp.add_argument("--lock")
    bp.add_argument("--lock-timeout", type=float, default=3600.0)
    bp.add_argument("--extra", action="append")
    cp = sub.add_parser("compare")
    cp.add_argument("--a", required=True)
    cp.add_argument("--b", required=True)
    cp.add_argument("--views")
    cp.add_argument("--noise", help="a second fresh -Bench run of the same config: bench-to-bench numbers + the gate outside its noise")
    a = ap.parse_args(argv)
    if a.check:
        fails = self_check()
        print(json.dumps({"selfTest": "PASS" if not fails else "FAIL", "failures": fails}, indent=2))
        return 0 if not fails else 1
    handlers = {"start": cmd_start, "reload": cmd_reload, "shot": cmd_shot, "cycle": cmd_cycle, "state": cmd_state,
                "stop": cmd_stop, "compare": cmd_compare, "bench": cmd_bench, "tune": cmd_tune,
                "tuner-state": cmd_tuner_state, "tuner-save": cmd_tuner_save, "tuner-reset": cmd_tuner_reset,
                "tuner-panel": cmd_tuner_panel, "art-view": cmd_art_view}
    if a.cmd not in handlers:
        ap.print_usage(sys.stderr)
        return 2
    try:
        return handlers[a.cmd](a)
    except LiveTuneError as e:
        print(json.dumps({"ok": False, "error": str(e)}, ensure_ascii=False), file=sys.stderr)
        return e.code


if __name__ == "__main__":
    sys.exit(main())
