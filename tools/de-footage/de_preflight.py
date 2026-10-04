"""Preflight for the live Unmatched: Digital Edition study (docs/game-design/de-footage/task/04-de-live-research.md).

usage: python tools/de-footage/de_preflight.py
Checks: ffmpeg + NVENC, the venv with soundcard (WASAPI loopback), default output device, no Unreal
clients or editor running, the DE window is open (title has "Unmatched"), free disk space.
Prints PASS/WARN/FAIL per line; exit 1 if any FAIL.
"""
import json
import os
import shutil
import subprocess
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
VENV_PY = r"C:\tmp\de-footage\tools\venv\Scripts\python.exe"
OUT_ROOT = r"C:\tmp\de-live"
fails = 0


def report(level, what, detail=""):
    global fails
    fails += level == "FAIL"
    print(f"{level:4}  {what}" + (f" - {detail}" if detail else ""), flush=True)


def ps(cmd):
    r = subprocess.run(["powershell", "-NoProfile", "-Command",
                        "[Console]::OutputEncoding=[Text.Encoding]::UTF8; " + cmd],
                       capture_output=True, text=True, encoding="utf-8", errors="replace")
    return r.stdout.strip()


# ffmpeg + NVENC
ff = shutil.which("ffmpeg")
if not ff:
    report("FAIL", "ffmpeg", "not in PATH (winget install Gyan.FFmpeg)")
else:
    enc = subprocess.run([ff, "-hide_banner", "-encoders"], capture_output=True, text=True).stdout
    report("PASS" if "h264_nvenc" in enc else "FAIL", "ffmpeg + h264_nvenc", ff)

# venv + soundcard loopback
if not os.path.exists(VENV_PY):
    report("FAIL", "venv", f"{VENV_PY} missing: python -m venv C:\\tmp\\de-footage\\tools\\venv && "
                            "C:\\tmp\\de-footage\\tools\\venv\\Scripts\\python -m pip install soundcard numpy \"yt-dlp[default]\"")
else:
    code = ("import warnings,json,soundcard as sc;warnings.filterwarnings('ignore');"
            "s=sc.default_speaker();m=sc.get_microphone(id=str(s.name),include_loopback=True);"
            "print(json.dumps({'speaker':s.name,'loopback':m.name}))")
    r = subprocess.run([VENV_PY, "-c", code], capture_output=True, text=True, encoding="utf-8", errors="replace")
    if r.returncode:
        report("FAIL", "soundcard loopback", r.stderr.strip().splitlines()[-1] if r.stderr else "error")
    else:
        d = json.loads(r.stdout.strip().splitlines()[-1])
        report("PASS", "WASAPI loopback", f"default output: {d['speaker']} (the game must play here)")

# Unreal processes of THIS project (GPU load + capture): the editor and packaged clients from the repo.
# DE itself may also be called Unmatched.exe, so the project's clients are told apart by their path.
ue = ps("Get-Process | Where-Object { $_.Name -match '^UnrealEditor' -or ($_.Path -and $_.Path -like '*unmached*unreal*') } | "
        "ForEach-Object { \"$($_.Id) $($_.Name) $($_.Path)\" }")
report("WARN" if ue else "PASS", "project Unreal processes", ue.replace("\n", "; ") if ue else "none")

# DE window
titles = ps("Get-Process | Where-Object { $_.MainWindowTitle -match 'Unmatched' -and $_.Path -match 'steamapps' } | "
            "ForEach-Object { \"$($_.Name)|$($_.MainWindowTitle)\" }")
if titles:
    for line in titles.splitlines():
        name, title = line.split("|", 1)
        report("PASS", "DE window", f"process {name}, title '{title}'"
               + ("" if title.isascii() else " - NOT ASCII: pass the title to de_record.py from PowerShell"))
else:
    report("FAIL", "DE window", "no Steam window with 'Unmatched' in the title - launch the game and open the main menu")

# disk
free = shutil.disk_usage("C:\\").free / 2**30
report("PASS" if free > 20 else "WARN", "free disk C:", f"{free:.0f} GiB (60 fps NVENC ~ 1-2 GiB/hour)")
os.makedirs(OUT_ROOT, exist_ok=True)
report("PASS", "output root", OUT_ROOT)
sys.exit(1 if fails else 0)
