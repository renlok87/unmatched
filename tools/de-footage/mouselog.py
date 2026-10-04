"""Log mouse button presses (time + position) during a live DE session, to tell lost clicks from ignored ones.

usage: python tools/de-footage/mouselog.py <out_dir>
Writes <out_dir>/mouse.csv: wall,perf,event,x,y (event = ldown/lup/rdown/rup/wheel). Stops when <out_dir>/STOP exists.
Uses a low-level OS mouse hook (WH_MOUSE_LL): it sees only our own input, never the game's memory or files.
"""
import ctypes
import ctypes.wintypes as wt
import os
import sys
import threading
import time

out = sys.argv[1]
os.makedirs(out, exist_ok=True)
stop_flag = os.path.join(out, "STOP")
log = open(os.path.join(out, "mouse.csv"), "w", buffering=1, encoding="utf-8")
log.write("wall,perf,event,x,y\n")

user32 = ctypes.WinDLL("user32", use_last_error=True)
kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
WH_MOUSE_LL = 14
EVENTS = {0x0201: "ldown", 0x0202: "lup", 0x0204: "rdown", 0x0205: "rup", 0x020A: "wheel"}


class MSLLHOOKSTRUCT(ctypes.Structure):
    _fields_ = [("pt", wt.POINT), ("mouseData", wt.DWORD), ("flags", wt.DWORD), ("time", wt.DWORD),
                ("dwExtraInfo", ctypes.c_size_t)]


LRESULT = ctypes.c_ssize_t
HOOKPROC = ctypes.WINFUNCTYPE(LRESULT, ctypes.c_int, wt.WPARAM, wt.LPARAM)
user32.CallNextHookEx.argtypes = [wt.HHOOK, ctypes.c_int, wt.WPARAM, wt.LPARAM]
user32.CallNextHookEx.restype = LRESULT
user32.SetWindowsHookExW.argtypes = [ctypes.c_int, HOOKPROC, wt.HINSTANCE, wt.DWORD]
user32.SetWindowsHookExW.restype = wt.HHOOK
kernel32.GetModuleHandleW.argtypes = [wt.LPCWSTR]
kernel32.GetModuleHandleW.restype = wt.HMODULE  # 64-bit handle; the default int return truncates it


def proc(n, w, l):
    if n == 0 and w in EVENTS:
        s = ctypes.cast(l, ctypes.POINTER(MSLLHOOKSTRUCT)).contents
        log.write(f"{time.time():.4f},{time.perf_counter():.4f},{EVENTS[w]},{s.pt.x},{s.pt.y}\n")
    return user32.CallNextHookEx(None, n, w, l)


cb = HOOKPROC(proc)
hook = user32.SetWindowsHookExW(WH_MOUSE_LL, cb, kernel32.GetModuleHandleW(None), 0)
if not hook:
    raise SystemExit(f"SetWindowsHookExW failed: {ctypes.get_last_error()}")
tid = kernel32.GetCurrentThreadId()


def watch():
    while not os.path.exists(stop_flag):
        time.sleep(0.5)
    user32.PostThreadMessageW(tid, 0x0012, 0, 0)  # WM_QUIT


threading.Thread(target=watch, daemon=True).start()
msg = wt.MSG()
print("mouse log on; touch", stop_flag, "to stop", flush=True)
while user32.GetMessageW(ctypes.byref(msg), None, 0, 0) > 0:
    user32.TranslateMessage(ctypes.byref(msg))
    user32.DispatchMessageW(ctypes.byref(msg))
user32.UnhookWindowsHookEx(hook)
log.close()
print("mouse log stopped", flush=True)
