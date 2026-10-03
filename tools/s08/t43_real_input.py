#!/usr/bin/env python3
"""T4.3 real OS input on the packaged client (RD-5, docs/game-design/decisions/2026-10-03-delegated-decisions.md).

Rule (user delegation 2026-09-29, kept by RD-5): real input only while the user is idle >= 10 min by GetLastInputInfo,
and it stops at the first move of the user. Nothing is simulated by flags: every step goes through SendInput and is
proven by the client's own trace line 'INPUT ... src=os'.

  python tools/s08/t43_real_input.py idle                       # current idle seconds
  python tools/s08/t43_real_input.py run [--wait-idle 600] [--max-wait-min 720] [--board-id <cuid>]
         [--api http://localhost:3000/graphql] [--backend-env <.env with S08_DEMO_*>] [--out <evidence dir>]
  python tools/s08/t43_real_input.py --check                    # self-test without UE (structures, trace parsing, mapping)

run:
  1. waits until the user is idle >= --wait-idle seconds (polls every 15 s, gives up after --max-wait-min);
  2. takes C:/tmp/unmatched-gpu.lock (owner=T43) - waits while another GPU run holds it;
  3. starts tools/s08/run-phase2-demo.ps1 -VisibleHost (host window shown, joiner offscreen; credentials S08_DEMO_*
     from --backend-env into the child environment only);
  4. low-level mouse/keyboard hooks from here on: any event WITHOUT the injected flag is the user -> abort, no more
     input is sent;
  5. after the host's evidence shot ('SHOT captured'), finds the host window (DPI-aware, physical pixels), maps the own
     hero's traced projection (body point = midpoint of 'SHOT fighter' feet and 'SHOT head') into the window and sends:
     hover (cursor path onto the hero), left click, wheel in x2, wheel out x2, Space, hover off. Before every event:
     the host is the foreground window and the target point belongs to it, otherwise nothing is sent;
     each step waits for its trace line and the client area is captured (PIL ImageGrab) after hover / click / zoom;
  6. lets the demo finish (its own assertions, evidence publish, scoped game abort), releases the lock, writes
     <out>/report.json and README.md.
Statuses stay honest: «выполнено» only when every step has its src=os trace line.
"""
from __future__ import annotations

import argparse
import ctypes
import ctypes.wintypes as wt
import datetime as dt
import json
import os
import re
import subprocess
import sys
import threading
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
DEMO = REPO / "tools" / "s08" / "run-phase2-demo.ps1"
GPU_LOCK = Path(os.environ.get("UNMATCHED_GPU_LOCK", "C:/tmp/unmatched-gpu.lock"))
# Real game map only (user decision 2026-10-04): Marmoreal · original map, `marmoreal-original` in S08ArtBoardProfiles.json.
MAP_BOARD_ID = "c121b47f8d6eb28daccb76d05"
TAG = 0x54343354                               # dwExtraInfo of our SendInput events ('T43T')
NO_WINDOW = 0x08000000

# ------------------------------------------------------------------------------------------------ Win32
user32 = ctypes.WinDLL("user32", use_last_error=True) if os.name == "nt" else None
kernel32 = ctypes.WinDLL("kernel32", use_last_error=True) if os.name == "nt" else None
ULONG_PTR = ctypes.c_size_t


class MOUSEINPUT(ctypes.Structure):
    _fields_ = [("dx", wt.LONG), ("dy", wt.LONG), ("mouseData", wt.DWORD), ("dwFlags", wt.DWORD),
                ("time", wt.DWORD), ("dwExtraInfo", ULONG_PTR)]


class KEYBDINPUT(ctypes.Structure):
    _fields_ = [("wVk", wt.WORD), ("wScan", wt.WORD), ("dwFlags", wt.DWORD), ("time", wt.DWORD),
                ("dwExtraInfo", ULONG_PTR)]


class HARDWAREINPUT(ctypes.Structure):
    _fields_ = [("uMsg", wt.DWORD), ("wParamL", wt.WORD), ("wParamH", wt.WORD)]


class _INPUTUNION(ctypes.Union):
    _fields_ = [("mi", MOUSEINPUT), ("ki", KEYBDINPUT), ("hi", HARDWAREINPUT)]


class INPUT(ctypes.Structure):
    _anonymous_ = ("u",)
    _fields_ = [("type", wt.DWORD), ("u", _INPUTUNION)]


class LASTINPUTINFO(ctypes.Structure):
    _fields_ = [("cbSize", wt.UINT), ("dwTime", wt.DWORD)]


class MSLLHOOKSTRUCT(ctypes.Structure):
    _fields_ = [("pt", wt.POINT), ("mouseData", wt.DWORD), ("flags", wt.DWORD), ("time", wt.DWORD),
                ("dwExtraInfo", ULONG_PTR)]


class KBDLLHOOKSTRUCT(ctypes.Structure):
    _fields_ = [("vkCode", wt.DWORD), ("scanCode", wt.DWORD), ("flags", wt.DWORD), ("time", wt.DWORD),
                ("dwExtraInfo", ULONG_PTR)]


INPUT_MOUSE, INPUT_KEYBOARD = 0, 1
MOUSEEVENTF_MOVE, MOUSEEVENTF_LEFTDOWN, MOUSEEVENTF_LEFTUP = 0x0001, 0x0002, 0x0004
MOUSEEVENTF_WHEEL, MOUSEEVENTF_VIRTUALDESK, MOUSEEVENTF_ABSOLUTE = 0x0800, 0x4000, 0x8000
KEYEVENTF_KEYUP = 0x0002
VK_SPACE = 0x20
SM_XVIRTUALSCREEN, SM_YVIRTUALSCREEN, SM_CXVIRTUALSCREEN, SM_CYVIRTUALSCREEN = 76, 77, 78, 79
WH_KEYBOARD_LL, WH_MOUSE_LL = 13, 14
LLMHF_INJECTED, LLKHF_INJECTED = 0x01, 0x10
WM_QUIT = 0x0012
GA_ROOT = 2
HOOKPROC = ctypes.WINFUNCTYPE(ctypes.c_ssize_t, ctypes.c_int, wt.WPARAM, wt.LPARAM)


def win_setup() -> str:
    """Per-monitor DPI awareness v2 (physical pixels everywhere) + typed signatures."""
    mode = "per-monitor-v2"
    try:
        if not user32.SetProcessDpiAwarenessContext(ctypes.c_void_p(-4)):
            mode = "unchanged"
    except AttributeError:
        mode = "unavailable"
    user32.SendInput.argtypes = [wt.UINT, ctypes.POINTER(INPUT), ctypes.c_int]
    user32.SendInput.restype = wt.UINT
    user32.SetWindowsHookExW.argtypes = [ctypes.c_int, HOOKPROC, wt.HINSTANCE, wt.DWORD]
    user32.SetWindowsHookExW.restype = wt.HHOOK
    user32.CallNextHookEx.argtypes = [wt.HHOOK, ctypes.c_int, wt.WPARAM, wt.LPARAM]
    user32.CallNextHookEx.restype = ctypes.c_ssize_t
    user32.WindowFromPoint.argtypes = [wt.POINT]
    user32.WindowFromPoint.restype = wt.HWND
    user32.GetAncestor.argtypes = [wt.HWND, wt.UINT]
    user32.GetAncestor.restype = wt.HWND
    user32.GetForegroundWindow.restype = wt.HWND
    kernel32.GetModuleHandleW.restype = wt.HMODULE
    return mode


def idle_seconds() -> float:
    lii = LASTINPUTINFO(ctypes.sizeof(LASTINPUTINFO), 0)
    if not user32.GetLastInputInfo(ctypes.byref(lii)):
        raise OSError(ctypes.get_last_error(), "GetLastInputInfo")
    return ((kernel32.GetTickCount() - lii.dwTime) & 0xFFFFFFFF) / 1000.0


class UserGuard:
    """Low-level hooks: a mouse or keyboard event without the injected flag is the user -> tripped."""

    def __init__(self):
        self.tripped: str | None = None
        self.injected = 0
        self._tid = None
        self._ready = threading.Event()
        self._procs = []
        self._thread = threading.Thread(target=self._run, daemon=True)

    def start(self):
        self._thread.start()
        if not self._ready.wait(5):
            raise RuntimeError("hook thread did not start")

    def _run(self):
        self._tid = kernel32.GetCurrentThreadId()

        def mouse(code, wparam, lparam):
            if code >= 0:
                info = ctypes.cast(lparam, ctypes.POINTER(MSLLHOOKSTRUCT)).contents
                if info.flags & LLMHF_INJECTED:
                    self.injected += 1
                elif self.tripped is None:
                    self.tripped = f"mouse msg=0x{wparam:04x} at ({info.pt.x},{info.pt.y}) {now_local()}"
            return user32.CallNextHookEx(None, code, wparam, lparam)

        def keyboard(code, wparam, lparam):
            if code >= 0:
                info = ctypes.cast(lparam, ctypes.POINTER(KBDLLHOOKSTRUCT)).contents
                if info.flags & LLKHF_INJECTED:
                    self.injected += 1
                elif self.tripped is None:
                    self.tripped = f"keyboard vk=0x{info.vkCode:02x} {now_local()}"
            return user32.CallNextHookEx(None, code, wparam, lparam)

        self._procs = [HOOKPROC(mouse), HOOKPROC(keyboard)]
        hmod = kernel32.GetModuleHandleW(None)
        hooks = [user32.SetWindowsHookExW(WH_MOUSE_LL, self._procs[0], hmod, 0),
                 user32.SetWindowsHookExW(WH_KEYBOARD_LL, self._procs[1], hmod, 0)]
        self._ready.set()
        msg = wt.MSG()
        while user32.GetMessageW(ctypes.byref(msg), None, 0, 0) > 0:
            pass
        for h in hooks:
            if h:
                user32.UnhookWindowsHookEx(h)

    def stop(self):
        if self._tid:
            user32.PostThreadMessageW(self._tid, WM_QUIT, 0, 0)
        self._thread.join(3)


class Injector:
    def __init__(self, guard: UserGuard, log: list):
        self.guard, self.log = guard, log
        self.vx = user32.GetSystemMetrics(SM_XVIRTUALSCREEN)
        self.vy = user32.GetSystemMetrics(SM_YVIRTUALSCREEN)
        self.vw = user32.GetSystemMetrics(SM_CXVIRTUALSCREEN)
        self.vh = user32.GetSystemMetrics(SM_CYVIRTUALSCREEN)

    def _send(self, *inputs: INPUT):
        if self.guard.tripped:
            raise UserActive(self.guard.tripped)
        arr = (INPUT * len(inputs))(*inputs)
        if user32.SendInput(len(inputs), arr, ctypes.sizeof(INPUT)) != len(inputs):
            raise OSError(ctypes.get_last_error(), "SendInput")

    def _mouse(self, flags, dx=0, dy=0, data=0) -> INPUT:
        return INPUT(type=INPUT_MOUSE, mi=MOUSEINPUT(dx, dy, data & 0xFFFFFFFF, flags, 0, TAG))

    def move(self, x: int, y: int):
        nx = round((x - self.vx) * 65535 / max(self.vw - 1, 1))
        ny = round((y - self.vy) * 65535 / max(self.vh - 1, 1))
        self._send(self._mouse(MOUSEEVENTF_MOVE | MOUSEEVENTF_ABSOLUTE | MOUSEEVENTF_VIRTUALDESK, nx, ny))

    def nudge(self):
        self._send(self._mouse(MOUSEEVENTF_MOVE, 0, 0))

    def click(self):
        self._send(self._mouse(MOUSEEVENTF_LEFTDOWN))
        time.sleep(0.06)
        self._send(self._mouse(MOUSEEVENTF_LEFTUP))

    def wheel(self, notches: int):
        self._send(self._mouse(MOUSEEVENTF_WHEEL, data=120 * notches))

    def key(self, vk: int, scan: int = 0):
        self._send(INPUT(type=INPUT_KEYBOARD, ki=KEYBDINPUT(vk, scan, 0, 0, TAG)))
        time.sleep(0.05)
        self._send(INPUT(type=INPUT_KEYBOARD, ki=KEYBDINPUT(vk, scan, KEYEVENTF_KEYUP, 0, TAG)))


class UserActive(RuntimeError):
    pass


# ------------------------------------------------------------------------------------------------ trace / window
VIEWER_RE = re.compile(r"viewerTeam=(P\d) p1=(\S+) p2=(\S+)")
FIGHTER_RE = re.compile(r"SHOT fighter (\S+) pos=\(\S+\) world=\(\S+\) screen=\((-?\d+),(-?\d+)\) projected=1 alive=1")
HEAD_RE = re.compile(r"SHOT head fighter=(\S+) .*? screen=\((-?[\d.]+),(-?[\d.]+)\)")
CTX_RE = re.compile(r"SHOT ctx viewport=(\d+)x(\d+)")


def own_hero_target(trace: str) -> dict:
    """Own hero id and its body point in viewport pixels (midpoint of the traced feet and head projections)."""
    m = VIEWER_RE.findall(trace)
    if not m:
        raise ValueError("no 'viewerTeam=' line")
    team, p1, p2 = m[-1]
    own = (p1 if team == "P1" else p2).split(",")
    hero = next((f for f in own if f.endswith("-hero")), own[0])
    feet = [(int(x), int(y)) for fid, x, y in FIGHTER_RE.findall(trace) if fid == hero]
    heads = [(float(x), float(y)) for fid, x, y in HEAD_RE.findall(trace) if fid == hero]
    vp = CTX_RE.findall(trace)
    if not feet or not vp:
        raise ValueError(f"no projected 'SHOT fighter {hero}' / 'SHOT ctx' line")
    fx, fy = feet[-1]
    hx, hy = heads[-1] if heads else (fx, fy - 30)
    return {"team": team, "hero": hero, "feet": [fx, fy], "head": [hx, hy],
            "body": [round((fx + hx) / 2), round((fy + hy) / 2)], "viewport": [int(vp[-1][0]), int(vp[-1][1])]}


def to_screen(pt, viewport, client_origin, client_size):
    sx = client_size[0] / viewport[0]
    sy = client_size[1] / viewport[1]
    return round(client_origin[0] + pt[0] * sx), round(client_origin[1] + pt[1] * sy)


def find_window(pid: int):
    found = []

    @ctypes.WINFUNCTYPE(wt.BOOL, wt.HWND, wt.LPARAM)
    def cb(hwnd, _):
        p = wt.DWORD()
        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(p))
        if p.value == pid and user32.IsWindowVisible(hwnd):
            r = wt.RECT()
            user32.GetClientRect(hwnd, ctypes.byref(r))
            found.append((r.right * r.bottom, hwnd, r.right, r.bottom))
        return True

    user32.EnumWindows(cb, 0)
    if not found:
        return None
    _, hwnd, w, h = max(found)
    o = wt.POINT(0, 0)
    user32.ClientToScreen(hwnd, ctypes.byref(o))
    return {"hwnd": hwnd, "origin": [o.x, o.y], "size": [w, h]}


def owns_point(hwnd, x, y) -> bool:
    h = user32.WindowFromPoint(wt.POINT(x, y))
    return bool(h) and user32.GetAncestor(h, GA_ROOT) == hwnd


def ensure_foreground(inj: Injector, hwnd) -> bool:
    if user32.GetForegroundWindow() == hwnd:
        return True
    inj.nudge()                      # an input event of this process unlocks SetForegroundWindow (no Alt: menu mode)
    user32.SetForegroundWindow(hwnd)
    user32.BringWindowToTop(hwnd)
    time.sleep(0.4)
    return user32.GetForegroundWindow() == hwnd


class TraceTail:
    def __init__(self, path: Path):
        self.path, self.pos = path, 0

    def read_all(self) -> str:
        return self.path.read_text(encoding="utf-8", errors="replace") if self.path.exists() else ""

    def mark(self):
        self.pos = len(self.read_all())

    def wait(self, pattern: str, timeout: float) -> str | None:
        rx = re.compile(pattern)
        end = time.time() + timeout
        while time.time() < end:
            text = self.read_all()[self.pos:]
            for ln in text.splitlines():
                if rx.search(ln):
                    return ln
            time.sleep(0.1)
        return None


def capture(rect, path: Path) -> str | None:
    try:
        from PIL import ImageGrab
        x, y, w, h = rect
        ImageGrab.grab(bbox=(x, y, x + w, y + h), all_screens=True).save(path)
        return path.name
    except Exception as exc:  # noqa: BLE001 - evidence capture is best effort, the trace line is the proof
        return f"capture failed: {exc!r}"


def now_local() -> str:
    return dt.datetime.now().astimezone().isoformat(timespec="seconds")


def load_env(path: Path) -> dict:
    env = {}
    for ln in path.read_text(encoding="utf-8").splitlines():
        if "=" in ln and not ln.lstrip().startswith("#"):
            k, v = ln.split("=", 1)
            env[k.strip()] = v.strip().strip('"')
    return env


# ------------------------------------------------------------------------------------------------ run
def input_sequence(inj: Injector, win: dict, target: dict, tail: TraceTail, out: Path, steps: list):
    hwnd = win["hwnd"]
    origin, size, vp = win["origin"], win["size"], target["viewport"]
    body = to_screen(target["body"], vp, origin, size)
    centre = (origin[0] + size[0] // 2, origin[1] + size[1] // 2)
    off = to_screen((vp[0] * 0.5, vp[1] * 0.12), vp, origin, size)   # top band: board edge / scenery, no fighter
    rect = (origin[0], origin[1], size[0], size[1])
    hero = re.escape(target["hero"])

    def guarded(point):
        if user32.GetForegroundWindow() != hwnd and not ensure_foreground(inj, hwnd):
            raise RuntimeError("host window is not in the foreground: input not sent")
        if not owns_point(hwnd, *point):
            raise RuntimeError(f"point {point} does not belong to the host window: input not sent")

    def step(name, pattern, action, timeout=3.0, shot=None):
        tail.mark()
        t0 = time.time()
        action()
        line = tail.wait(pattern, timeout)
        rec = {"step": name, "ok": line is not None, "trace": line, "ms": round((time.time() - t0) * 1000)}
        if shot:
            time.sleep(0.5)
            rec["capture"] = capture(rect, out / shot)
        steps.append(rec)
        return rec

    def path_to(dst, n=12):
        cur = wt.POINT()
        user32.GetCursorPos(ctypes.byref(cur))
        for i in range(1, n + 1):
            p = (round(cur.x + (dst[0] - cur.x) * i / n), round(cur.y + (dst[1] - cur.y) * i / n))
            inj.move(*p)
            time.sleep(0.03)

    guarded(centre)
    inj.move(*centre)
    time.sleep(0.3)
    guarded(body)
    step("hover", rf"INPUT hover src=os .*fighter={hero}\b", lambda: path_to(body), shot="t43-hover.png")
    guarded(body)
    step("click", rf"INPUT click button=left src=os .*fighter={hero}\b", inj.click, shot="t43-click.png")
    guarded(body)
    step("wheel-in", r"INPUT wheel dir=\S+ src=os", lambda: (inj.wheel(1), time.sleep(0.15), inj.wheel(1)),
         shot="t43-wheel-in.png")
    guarded(body)
    step("wheel-out", r"INPUT wheel dir=\S+ src=os", lambda: (inj.wheel(-1), time.sleep(0.15), inj.wheel(-1)))
    guarded(body)
    step("space", r"INPUT space src=os", lambda: inj.key(VK_SPACE, 0x39))
    guarded(off)
    step("hover-off", r"INPUT hover src=os .*fighter=(?!" + hero + r"\b)\S+", lambda: path_to(off), timeout=3.0)


def cmd_run(a) -> int:
    win_mode = win_setup()
    out = Path(a.out or REPO / "docs/game-design/evidence/ART-004" / f"t43-{dt.datetime.now():%Y%m%d-%H%M%S}")
    out.mkdir(parents=True, exist_ok=True)
    report = {"schema": "unmatched.t43-real-input/2", "task": "T4.3 real OS input (click, wheel, Space, hover) on the "
              "packaged client", "rule": "RD-5 / delegation 2026-09-29: only while the user is idle >= 10 min "
              "(GetLastInputInfo); abort at the first user input (low-level hooks, non-injected event)",
              "startedLocal": now_local(), "dpiAwareness": win_mode, "thresholdSeconds": a.wait_idle,
              "samples": [], "steps": [], "status": None}

    def finish(status, **extra):
        report.update(status=status, finishedLocal=now_local(), **extra)
        (out / "report.json").write_text(json.dumps(report, ensure_ascii=False, indent=1) + "\n", encoding="utf-8",
                                         newline="\n")
        print(f"T43 {status} -> {out}")
        return 0 if status == "выполнено" else 3

    deadline = time.time() + a.max_wait_min * 60
    while True:
        idle = idle_seconds()
        report["samples"].append({"local": now_local(), "idleSeconds": round(idle, 1)})
        if idle >= a.wait_idle:
            break
        if time.time() > deadline:
            return finish("не выполнено: пользователь активен", maxIdleSeconds=max(s["idleSeconds"] for s in report["samples"]))
        time.sleep(15)
    report["samples"] = report["samples"][-20:]

    env_file = Path(a.backend_env or os.environ.get("UNMATCHED_BACKEND_ENV") or REPO / "backend/.env")
    benv = load_env(env_file)
    keys = ("S08_DEMO_HOST_EMAIL", "S08_DEMO_HOST_PASSWORD", "S08_DEMO_JOINER_EMAIL", "S08_DEMO_JOINER_PASSWORD")
    if not all(benv.get(k) for k in keys):
        return finish("ошибка: нет S08_DEMO_* в " + env_file.name)
    while GPU_LOCK.exists():
        if time.time() > deadline:
            return finish("не выполнено: GPU занят (" + GPU_LOCK.read_text(encoding="utf-8", errors="replace").strip() + ")")
        time.sleep(30)
    GPU_LOCK.parent.mkdir(parents=True, exist_ok=True)
    GPU_LOCK.write_text(f"owner=T43 pid={os.getpid()} {now_local()} t43_real_input\n", encoding="utf-8")
    guard = UserGuard()
    proc = None
    try:
        guard.start()
        env = os.environ.copy()
        env.update({k: benv[k] for k in keys})          # environment only, never argv
        cmd = ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(DEMO), "-Api", a.api,
               "-EvidenceDir", str(out / "demo"), "-ArtPreviewBoardId", a.board_id, "-RunSeconds", str(a.run_seconds),
               "-ClientFps", "30", "-ArtPreviewShotAfter", str(a.shot_after), "-VisibleHost"]
        report["demoArgv"] = [c if not c.startswith(str(REPO)) else os.path.relpath(c, REPO) for c in cmd]
        proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, env=env, cwd=str(REPO),
                                creationflags=NO_WINDOW)
        lines: list[str] = []
        threading.Thread(target=lambda: [lines.append(b.decode("utf-8", "replace").rstrip())
                                         for b in iter(proc.stdout.readline, b"")], daemon=True).start()

        def grep(rx):
            for ln in list(lines):
                m = re.search(rx, ln)
                if m:
                    return m
            return None

        t_end = time.time() + a.shot_after + 120
        staging = host_pid = None
        while time.time() < t_end and proc.poll() is None and not (staging and host_pid):
            staging = staging or (grep(r"^staging: (\S+)") or [None, None])[1]
            host_pid = host_pid or (grep(r"^host pid=(\d+)") or [None, None])[1]
            time.sleep(0.5)
        if not (staging and host_pid):
            return finish("ошибка: демо не запустило хост", demoTail=lines[-20:])
        tail = TraceTail(Path(staging) / "phase2-client-host.trace.log")
        if not tail.wait(r"SHOT captured file=phase2-board-host", max(5.0, t_end - time.time())):
            return finish("ошибка: нет кадра хоста (SHOT captured)", demoTail=lines[-20:])
        if guard.tripped:
            return finish("прервано: ввод пользователя до начала", userInput=guard.tripped)
        target = own_hero_target(tail.read_all())
        win = find_window(int(host_pid))
        if not win:
            return finish("ошибка: окно хоста не найдено (видимое окно процесса)", target=target)
        report.update(target=target, window={"origin": win["origin"], "size": win["size"]})
        inj = Injector(guard, report["steps"])
        report["virtualScreen"] = [inj.vx, inj.vy, inj.vw, inj.vh]
        try:
            input_sequence(inj, win, target, tail, out, report["steps"])
        except UserActive as exc:
            return finish("прервано: ввод пользователя", userInput=str(exc))
        except RuntimeError as exc:
            return finish(f"ошибка: {exc}")
        finally:
            report["injectedSeen"] = guard.injected
        proc.wait(timeout=a.run_seconds + 300)
        report["demoExit"] = proc.returncode
        report["demoRunDir"] = (grep(r"published evidence run dir: (.+?) \(pointer") or [None, None])[1]
        report["demoTail"] = lines[-12:]
        ok = all(s["ok"] for s in report["steps"]) and len(report["steps"]) == 6
        return finish("выполнено" if ok and not guard.tripped else "частично: не все шаги подтверждены трассой")
    finally:
        guard.stop()
        if proc and proc.poll() is None:
            proc.wait(timeout=a.run_seconds + 300)
        try:
            if GPU_LOCK.read_text(encoding="utf-8").startswith(f"owner=T43 pid={os.getpid()} "):
                GPU_LOCK.unlink()
        except OSError:
            pass


def cmd_check() -> int:
    assert ctypes.sizeof(INPUT) == (40 if ctypes.sizeof(ctypes.c_void_p) == 8 else 28), ctypes.sizeof(INPUT)
    assert ctypes.sizeof(MSLLHOOKSTRUCT) == (32 if ctypes.sizeof(ctypes.c_void_p) == 8 else 28)
    sample = "\n".join([
        "x ARTPREVIEW team mapping mode=absolute source=seatOrder viewerTeam=P1 p1=f-0-hero,f-0-sk0 p2=f-1-hero",
        "x SHOT ctx viewport=1920x1080 viewTarget=Cam cam=(0,1342,1917) rot=(-55,-90,0)",
        "x SHOT fighter f-0-hero pos=(2,2) world=(-218,-13,0) screen=(678,527) projected=1 alive=1",
        "x SHOT fighter f-1-hero pos=(4,4) world=(1,1,0) screen=(900,400) projected=1 alive=1",
        "x SHOT head fighter=f-0-hero socket=Head mesh=SK screen=(672.0,491.6) top=(1,1) bottom=(1,1) projected=1",
    ])
    t = own_hero_target(sample)
    assert t["hero"] == "f-0-hero" and t["body"] == [675, 509] and t["viewport"] == [1920, 1080], t
    assert to_screen(t["body"], t["viewport"], (100, 50), (1280, 720)) == (550, 389)
    assert re.search(r"INPUT hover src=os .*fighter=(?!f\-0\-hero\b)\S+", "INPUT hover src=os screen=(1,2) fighter=none")
    assert not re.search(r"INPUT hover src=os .*fighter=(?!f\-0\-hero\b)\S+", "INPUT hover src=os screen=(1,2) fighter=f-0-hero")
    if os.name == "nt":
        win_setup()
        print(f"idle now {idle_seconds():.1f} s")
    print("T43_CHECK_PASS")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--check", action="store_true")
    sub = ap.add_subparsers(dest="cmd")
    sub.add_parser("idle")
    r = sub.add_parser("run")
    r.add_argument("--wait-idle", type=float, default=600.0)
    r.add_argument("--max-wait-min", type=float, default=720.0)
    r.add_argument("--board-id", default=MAP_BOARD_ID)
    r.add_argument("--api", default="http://localhost:3000/graphql")
    r.add_argument("--backend-env")
    r.add_argument("--run-seconds", type=int, default=120)
    r.add_argument("--shot-after", type=int, default=30)
    r.add_argument("--out")
    a = ap.parse_args()
    if a.check:
        return cmd_check()
    if a.cmd == "idle":
        win_setup()
        print(f"{idle_seconds():.1f}")
        return 0
    if a.cmd == "run":
        return cmd_run(a)
    ap.print_help()
    return 2


if __name__ == "__main__":
    sys.exit(main())
