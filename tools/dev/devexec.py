"""Interactive dev loop driver for the Unmatched UE client (tools/dev/DEV-LOOP.md).

User request 2026-10-15: «Я не хочу полностью пересобирать игру каждый раз во время фикса. Запусти ее так чтобы ты мог
интерактивно ее фиксить».

  python tools/dev/devexec.py start [--vsai] [--res 1920x1080] [--packaged] [--extra "-Flag ..."]
  python tools/dev/devexec.py run "click 960 540" "wait 1" "shot C:/tmp/devexec/shots/a.png"
  python tools/dev/devexec.py shot [name]             # viewport + UI -> C:/tmp/devexec/shots/<name>.png
  python tools/dev/devexec.py lc                      # Live Coding compile, waits for the result in the log
  python tools/dev/devexec.py log [--grep TEXT] [-n 60]
  python tools/dev/devexec.py stop

The client (uncooked `UnrealEditor.exe Unmatched.uproject -game -LiveCoding` by default) polls
<dir>/cmd-<seq>.txt and answers <dir>/done-<seq>.json (S08DevExec.cpp). Clicks are synthetic Slate events, the OS
mouse and keyboard are never touched.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
UPROJECT = ROOT / "unreal" / "Unmatched" / "Unmatched.uproject"
UE_ROOT = Path(os.environ.get("UE_ROOT", r"C:\Program Files\Epic Games\UE_5.8"))
EDITOR = UE_ROOT / "Engine" / "Binaries" / "Win64" / "UnrealEditor.exe"
PACKAGED = ROOT / "unreal" / "Unmatched" / "Saved" / "StagedBuilds" / "Windows" / "Unmatched" / "Binaries" / "Win64" / "Unmatched.exe"
DIR = Path(os.environ.get("DEVEXEC_DIR", r"C:\tmp\devexec"))
SHOTS = DIR / "shots"
LOG = DIR / "client.log"
SESSION = DIR / "session.json"


def session() -> dict:
    if not SESSION.exists():
        sys.exit("no session: run `devexec.py start` first")
    return json.loads(SESSION.read_text(encoding="utf-8"))


def alive(pid: int) -> bool:
    out = subprocess.run(["tasklist", "/FI", f"PID eq {pid}", "/NH"], capture_output=True, text=True).stdout
    return str(pid) in out


def next_seq() -> int:
    n = 0
    for p in DIR.glob("*-*.*"):
        m = re.match(r"(?:cmd|done)-(\d+)\.", p.name)
        if m:
            n = max(n, int(m.group(1)))
    return n + 1


def send(lines: list[str], timeout: float = 120.0) -> dict:
    s = session()
    seq = next_seq()
    tmp = DIR / f"cmd-{seq}.tmp"
    tmp.write_text("\n".join(lines) + "\n", encoding="utf-8")
    tmp.replace(DIR / f"cmd-{seq}.txt")
    done = DIR / f"done-{seq}.json"
    t0 = time.time()
    while time.time() - t0 < timeout:
        if done.exists():
            return json.loads(done.read_text(encoding="utf-8"))
        if not alive(s["pid"]):
            sys.exit(f"client pid {s['pid']} is gone (see {LOG})")
        time.sleep(0.05)
    sys.exit(f"no done-{seq}.json within {timeout:.0f} s")


def print_result(r: dict) -> int:
    for line in r.get("lines", []):
        out = line.get("out", "").strip()
        print(("ok  " if line.get("ok") else "ERR ") + line["cmd"] + (f"\n    {out}" if out else ""))
    print(f"[{r.get('ms')} ms]")
    return 0 if r.get("ok") else 1


def cmd_start(a) -> int:
    DIR.mkdir(parents=True, exist_ok=True)
    SHOTS.mkdir(parents=True, exist_ok=True)
    if SESSION.exists():
        old = json.loads(SESSION.read_text(encoding="utf-8"))
        if alive(old["pid"]):
            print(f"already running pid {old['pid']}")
            return 0
    for p in DIR.glob("cmd-*"):
        p.unlink()
    for p in DIR.glob("done-*"):
        p.unlink()
    (DIR / "ready.json").unlink(missing_ok=True)
    w, h = a.res.lower().split("x")
    if a.packaged:
        args = [str(PACKAGED)]
    else:
        args = [str(EDITOR), str(UPROJECT), "-game", "-LiveCoding"]
    args += [f"-DevExec={DIR}", "-windowed", f"-ResX={w}", f"-ResY={h}", f"-abslog={LOG}", "-NoSplash", "-nosound" if a.mute else ""]
    env = dict(os.environ)
    if a.vsai:
        args += ["-S08Auto", "-S08Create", "-S08Mode=VS_AI"]
        if a.hero:
            args.append(f"-S08HeroId={a.hero}")
        env.setdefault("S08_EMAIL", a.email)
        env.setdefault("S08_PASSWORD", a.password)
    if a.extra:
        args += a.extra.split()
    args = [x for x in args if x]
    p = subprocess.Popen(args, env=env, creationflags=subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP)
    SESSION.write_text(json.dumps({"pid": p.pid, "args": args, "started": time.time()}, indent=1), encoding="utf-8")
    print(f"pid {p.pid}; waiting for ready.json")
    t0 = time.time()
    while time.time() - t0 < a.timeout:
        if (DIR / "ready.json").exists():
            print(f"ready in {time.time() - t0:.0f} s")
            return 0
        if p.poll() is not None:
            print(f"client exited with {p.returncode}; log {LOG}")
            return 1
        time.sleep(1)
    print("ready.json not seen yet (shader compile?); check `devexec.py log`")
    return 2


def cmd_run(a) -> int:
    return print_result(send(a.lines, a.timeout))


def cmd_shot(a) -> int:
    name = a.name or time.strftime("shot-%H%M%S")
    path = SHOTS / (name if name.endswith(".png") else name + ".png")
    r = send([f"shot {path.as_posix()}"], 60)
    rc = print_result(r)
    if rc == 0:
        print(path)
    return rc


def log_size() -> int:
    return LOG.stat().st_size if LOG.exists() else 0


def read_log_from(pos: int) -> str:
    with open(LOG, "rb") as f:
        f.seek(pos)
        return f.read().decode("utf-8", "replace")


def cmd_lc(a) -> int:
    pos = log_size()
    print_result(send(["LiveCoding.Compile"], 30))
    t0 = time.time()
    while time.time() - t0 < a.timeout:
        text = read_log_from(pos)
        for pat, rc in ((r"Live coding succeeded", 0), (r"No changes applied", 0), (r"Live coding failed|error C\d+|Compile failed", 1)):
            if re.search(pat, text, re.I):
                for line in text.splitlines():
                    if "LiveCoding" in line or "error" in line.lower():
                        print(line)
                if rc:
                    ubt = Path(os.environ.get("LOCALAPPDATA", "")) / "UnrealBuildTool" / "Log.txt"
                    if ubt.exists():
                        errs = [l for l in ubt.read_text(encoding="utf-8", errors="replace").splitlines()
                                if re.search(r"error C\d+|error LNK|: error", l)]
                        print("\n".join(errs[-15:]))
                return rc
        time.sleep(0.5)
    print("no Live Coding result in the log yet")
    return 2


def cmd_log(a) -> int:
    lines = read_log_from(0).splitlines() if LOG.exists() else []
    if a.grep:
        lines = [l for l in lines if re.search(a.grep, l, re.I)]
    print("\n".join(lines[-a.n:]))
    return 0


def cmd_stop(a) -> int:
    s = session()
    if alive(s["pid"]):
        try:
            send(["quit"], 15)
        except SystemExit:
            pass
        for _ in range(30):  # the exe and its DLLs stay locked until the process is really gone (LNK1104)
            if not alive(s["pid"]):
                break
            time.sleep(0.5)
        if alive(s["pid"]):
            subprocess.run(["taskkill", "/PID", str(s["pid"]), "/T", "/F"])
            for _ in range(20):
                if not alive(s["pid"]):
                    break
                time.sleep(0.5)
    SESSION.unlink(missing_ok=True)
    print("stopped")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("start")
    p.add_argument("--res", default="1920x1080")
    p.add_argument("--packaged", action="store_true")
    p.add_argument("--vsai", action="store_true", help="auto login + VS_AI game (S08_EMAIL/S08_PASSWORD)")
    p.add_argument("--hero", default="")
    p.add_argument("--email", default="veteran@unmatched.com")  # never test1 - the user plays on it (AGENTS.md)
    p.add_argument("--password", default="password123")
    p.add_argument("--mute", action="store_true")
    p.add_argument("--extra", default="")
    p.add_argument("--timeout", type=float, default=600)
    p.set_defaults(fn=cmd_start)
    p = sub.add_parser("run")
    p.add_argument("lines", nargs="+")
    p.add_argument("--timeout", type=float, default=120)
    p.set_defaults(fn=cmd_run)
    p = sub.add_parser("shot")
    p.add_argument("name", nargs="?")
    p.set_defaults(fn=cmd_shot)
    p = sub.add_parser("lc")
    p.add_argument("--timeout", type=float, default=600)
    p.set_defaults(fn=cmd_lc)
    p = sub.add_parser("log")
    p.add_argument("--grep", default="")
    p.add_argument("-n", type=int, default=60)
    p.set_defaults(fn=cmd_log)
    p = sub.add_parser("stop")
    p.set_defaults(fn=cmd_stop)
    a = ap.parse_args()
    return a.fn(a)


if __name__ == "__main__":
    sys.exit(main())
