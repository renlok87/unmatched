#!/usr/bin/env python3
"""ART-004 live packaged K2 harness (stage 3, T1.1): build, package, run, record.

Runs in the art worktree (the only checkout with the v2/v3 candidate .uasset
files). Every step writes a JSON record next to its evidence so the frame
classifier (tools/art/classify_evidence.py, grade "strict") can prove provenance.

  build    Build.bat Unmatched Win64 Development (hidden). Result from the
           UTF-16 log via Select-String 'Result: (Succeeded|Failed)' (Build.bat
           may exit 0 on a compile error), WITH_LIVE_CODING of every game-target
           SharedDefinitions.*.h, sha256 of Binaries/Win64/Unmatched.exe.
  package  tools/s08/package-client.ps1 -SkipBuild (its guard refuses a
           -NoLiveCoding game target). --direct runs the same BuildCookRun
           -skipbuild WITHOUT that guard and exists only for the WITH_RELOAD
           A/B experiment. Checks the candidate names in DevelopmentAssetRegistry
           .bin and sha256(staged inner exe) == sha256(Binaries exe); the staged
           ROOT Unmatched.exe is a launcher stub and never matches.
  run      One tools/s08/run-phase2-demo.ps1 pair (host + joiner, -ClientFps,
           -ClientPerf). Demo accounts come from backend/.env into the child
           environment only (never argv). Samples nvidia-smi (GPU total and
           per-process pmon) during the run, copies the packaged client logs
           Unmatched*.log right after the run (the next package step wipes the
           stage dir), writes perf.json, timing.json, a sidecar
           <frame>.evidence.json per PNG and extends manifest.json.
  baseline nvidia-smi sample with no client running (reference for the pair).
  metrics  K2 crop metrics around the traced Head-socket projection
           (thresholds.json E1_k2_live K2-01..K2-05) for a set of run dirs.
           --threshold-set registered (default, T1.1 behaviour, host frames):
           K2-02/K2-03 on the registered fallback bands are reported as
           formally computed but "не измерено (невалидно)": the bands miss the
           face and the crown on screen (FALLBACK_BAND_AUDIT); band overlays
           k2-bands-*.png are written for the placement check.
           --threshold-set rev1-t23 (thresholds.json revisions[], T2.3,
           «предложено»): crop around proj(Head+12 uu), side 3 x proj(Head..
           Head+24 uu); face / crown / neck see-through masks are the Blender
           ID renders of the SAME variant (selected by the traced mesh)
           reprojected into the frame through the traced camera; host and
           joiner frames; K2-02..K2-04 count only after a placement review of
           the k2-bands-rev1-t23-*.png overlays (--placement-review).
  perf02   PERF-02 p95 frame time against a threshold set (perf-summary.json).

Statuses stay honest: a passing run is "измерено" (measured), never
"художественно принято" (artistically accepted).
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import math
import os
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
UE_ROOT = Path(os.environ.get("UE_ROOT", r"C:\Program Files\Epic Games\UE_5.8"))
PROJECT_DIR = REPO / "unreal" / "Unmatched"
UPROJECT = PROJECT_DIR / "Unmatched.uproject"
BIN_EXE = PROJECT_DIR / "Binaries" / "Win64" / "Unmatched.exe"
STAGE_ROOT = PROJECT_DIR / "Saved" / "StagedBuilds" / "Windows"
STAGED_ROOT_EXE = STAGE_ROOT / "Unmatched.exe"
STAGED_INNER_EXE = STAGE_ROOT / "Unmatched" / "Binaries" / "Win64" / "Unmatched.exe"
STAGED_LOGS = STAGE_ROOT / "Unmatched" / "Saved" / "Logs"
STAGED_CSV = STAGE_ROOT / "Unmatched" / "Saved" / "Profiling" / "CSV"
# Raw bulk captures (CSV profiler, nvidia-smi pmon) stay outside git (Artifacts/ is ignored); the run dir
# keeps their summaries plus sha256 and path.
RAW_ROOT = PROJECT_DIR / "Artifacts" / "ART004Face" / "t11-raw"
STAGED_GUS = STAGE_ROOT / "Unmatched" / "Saved" / "Config" / "Windows" / "GameUserSettings.ini"
DEFAULT_GUS = PROJECT_DIR / "Config" / "DefaultGameUserSettings.ini"
ASSET_REGISTRY = PROJECT_DIR / "Saved" / "Cooked" / "Windows" / "Unmatched" / "Metadata" / "DevelopmentAssetRegistry.bin"
GAME_DEFS = PROJECT_DIR / "Intermediate" / "Build" / "Win64" / "x64" / "Unmatched" / "Development"
DEMO = REPO / "tools" / "s08" / "run-phase2-demo.ps1"
PACKAGE = REPO / "tools" / "s08" / "package-client.ps1"
BACKEND_ENV = REPO / "backend" / ".env"
REVIEW_BOARD_ID = "cmuhgs4b2001mwik4f2b2xtf8"  # Board row of the 5x6 Cobble review board
API = "http://localhost:3120/graphql"
MESH = {"face-neck-v2": "SK_Medusa_FaceNeck_v2Candidate", "head-tilt-v3": "SK_Medusa_HeadTilt_v3Candidate"}
NO_WINDOW = 0x08000000  # CREATE_NO_WINDOW
SIDECAR_SCHEMA = "unmatched.evidence-frame/1"


# ------------------------------------------------------------------ helpers
def now_local() -> str:
    return dt.datetime.now().astimezone().isoformat(timespec="seconds")


def sha256_file(p: Path) -> str:
    h = hashlib.sha256()
    with p.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def write_json(p: Path, doc) -> None:
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(doc, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")


def rel(p: Path) -> str:
    try:
        return p.resolve().relative_to(REPO).as_posix()
    except ValueError:
        return p.resolve().as_posix()


def ps(command: str, timeout: int | None = None) -> subprocess.CompletedProcess:
    return subprocess.run(["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", command],
                          capture_output=True, text=True, encoding="utf-8", errors="replace",
                          timeout=timeout, creationflags=NO_WINDOW)


def ps_quote(s: str) -> str:
    return "'" + str(s).replace("'", "''") + "'"


def select_string(path: Path, pattern: str, simple: bool = False) -> list[str]:
    """Authoritative text search (handles the UTF-16 Build.bat log)."""
    sm = " -SimpleMatch" if simple else ""
    r = ps(f"Select-String -LiteralPath {ps_quote(path)}{sm} -Pattern {ps_quote(pattern)} | "
           "ForEach-Object { $_.Line }")
    return [ln for ln in r.stdout.splitlines() if ln.strip()]


def free_virtual_gb() -> dict:
    r = ps("$os=Get-CimInstance Win32_OperatingSystem; '{0} {1} {2} {3}' -f "
           "$os.TotalVisibleMemorySize,$os.FreePhysicalMemory,$os.TotalVirtualMemorySize,$os.FreeVirtualMemory")
    a = [int(x) for x in r.stdout.split()]
    return {"totalRamGB": round(a[0] / 2**20, 1), "freeRamGB": round(a[1] / 2**20, 1),
            "commitLimitGB": round(a[2] / 2**20, 1), "freeCommitGB": round(a[3] / 2**20, 1)}


def shared_definitions() -> dict:
    out = {}
    for p in sorted(GAME_DEFS.rglob("SharedDefinitions.*.h")):
        m = re.search(rb"#define WITH_LIVE_CODING (\d)", p.read_bytes())
        out[p.relative_to(PROJECT_DIR).as_posix()] = int(m.group(1)) if m else None
    return out


def listeners(port: int) -> list[int]:
    r = subprocess.run(["netstat", "-ano", "-p", "TCP"], capture_output=True, text=True, errors="replace",
                       creationflags=NO_WINDOW)
    pids = set()
    for ln in r.stdout.splitlines():
        parts = ln.split()
        if len(parts) >= 5 and parts[1].endswith(f":{port}") and parts[3].upper() == "LISTENING":
            pids.add(int(parts[4]))
    return sorted(pids)


def process_info(pid: int) -> dict:
    r = ps(f"$p=Get-CimInstance Win32_Process -Filter 'ProcessId={pid}'; if ($p) {{ "
           "[pscustomobject]@{pid=$p.ProcessId; parent=$p.ParentProcessId; name=$p.Name; exe=$p.ExecutablePath; "
           "cmd=$p.CommandLine; created=$p.CreationDate.ToString('o')} | ConvertTo-Json -Compress }")
    try:
        return json.loads(r.stdout.strip() or "{}")
    except ValueError:
        return {"pid": pid, "raw": r.stdout.strip()}


def load_backend_env() -> dict:
    env = {}
    for ln in BACKEND_ENV.read_text(encoding="utf-8").splitlines():
        if "=" in ln and not ln.lstrip().startswith("#"):
            k, v = ln.split("=", 1)
            env[k.strip()] = v.strip()
    return env


def ini_value(p: Path, key: str) -> str | None:
    if not p.is_file():
        return None
    for ln in p.read_text(encoding="utf-8-sig", errors="replace").splitlines():
        if ln.strip().lower().startswith(key.lower() + "="):
            return ln.split("=", 1)[1].strip()
    return None


# ------------------------------------------------------------------ build
def cmd_build(a) -> int:
    out = Path(a.out).resolve()
    out.mkdir(parents=True, exist_ok=True)
    mem = free_virtual_gb()
    # Error 1455 (paging file too small) hit PCH compiles on 2026-09-28 with XGE and 4 actions. The
    # commit limit, not RAM, is the constraint (4 GB page file): 4 actions only with >= 20 GB free commit.
    par = a.max_parallel or (4 if mem["freeCommitGB"] >= 20 else 2)
    flags = ["-WaitMutex", "-NoXGE", "-NoUBA", f"-MaxParallelActions={par}"] + (a.extra or [])
    log = out / f"{a.label}-game-build.log"
    bat = UE_ROOT / "Engine" / "Build" / "BatchFiles" / "Build.bat"
    arglist = ",".join(ps_quote(x) for x in ["Unmatched", "Win64", "Development", str(UPROJECT)] + flags)
    started = time.time()
    rec = {"schema": "unmatched.art004-build/1", "label": a.label, "target": "Unmatched Win64 Development",
           "startedLocal": now_local(), "flags": flags, "maxParallelActions": par, "memoryBefore": mem,
           "command": f"Build.bat Unmatched Win64 Development <uproject> {' '.join(flags)}",
           "launcher": "powershell Start-Process -WindowStyle Hidden -Wait (no console window)",
           "log": rel(log)}
    r = ps(f"$p = Start-Process -FilePath {ps_quote(bat)} -ArgumentList @({arglist}) -WindowStyle Hidden "
           f"-PassThru -Wait -RedirectStandardOutput {ps_quote(log)} -RedirectStandardError {ps_quote(str(log) + '.err')}; "
           "Write-Output \"EXIT=$($p.ExitCode)\"")
    m = re.search(r"EXIT=(-?\d+)", r.stdout)
    rec["exitCode"] = int(m.group(1)) if m else None
    rec["durationS"] = round(time.time() - started, 1)
    rec["finishedLocal"] = now_local()
    rec["resultLines"] = select_string(log, r"Result: (Succeeded|Failed)")
    rec["errorLines"] = select_string(log, r"error C\d+|error LNK\d+|fatal error|C3859|C1076|1455")[:20]
    rec["result"] = ("Succeeded" if any("Result: Succeeded" in x for x in rec["resultLines"])
                     and not any("Result: Failed" in x for x in rec["resultLines"]) else "Failed")
    defs = shared_definitions()
    rec["sharedDefinitionsWithLiveCoding"] = defs
    rec["withLiveCodingValues"] = sorted({v for v in defs.values() if v is not None})
    rec["exe"] = {"path": rel(BIN_EXE), "sha256": sha256_file(BIN_EXE) if BIN_EXE.is_file() else None,
                  "mtimeLocal": dt.datetime.fromtimestamp(BIN_EXE.stat().st_mtime).astimezone().isoformat(timespec="seconds")
                  if BIN_EXE.is_file() else None}
    mapfile = BIN_EXE.with_suffix(".map")
    if "-MapFile" in flags and mapfile.is_file():
        rec["mapFile"] = {"path": rel(mapfile), "sha256": sha256_file(mapfile)}
    write_json(out / f"{a.label}-build.json", rec)
    print(json.dumps({k: rec[k] for k in ("label", "result", "exitCode", "durationS", "withLiveCodingValues",
                                           "maxParallelActions")}, ensure_ascii=False))
    print("exe sha256", rec["exe"]["sha256"])
    return 0 if rec["result"] == "Succeeded" else 1


# ------------------------------------------------------------------ package
def cmd_package(a) -> int:
    out = Path(a.out).resolve()
    out.mkdir(parents=True, exist_ok=True)
    log = out / f"{a.label}-package.log"
    started = time.time()
    rec = {"schema": "unmatched.art004-package/1", "label": a.label, "startedLocal": now_local(),
           "mode": "direct-uat-no-guard" if a.direct else "package-client.ps1 -SkipBuild", "log": rel(log),
           "sharedDefinitionsBefore": shared_definitions()}
    if a.direct:
        uat = UE_ROOT / "Engine" / "Build" / "BatchFiles" / "RunUAT.bat"
        args = ["BuildCookRun", f"-project={UPROJECT}", "-noP4", "-platform=Win64", "-clientconfig=Development",
                "-cook", "-stage", "-pak", "-package", "-compressed", "-skipbuild", "-unattended", "-nosplash",
                "-AdditionalCookerArgs=-ini:EditorPerProjectUserSettings:[/Script/ModelContextProtocolEngine."
                "ModelContextProtocolSettings]:bAutoStartServer=False"]
        arglist = ",".join(ps_quote(x) for x in args)
        r = ps(f"$p = Start-Process -FilePath {ps_quote(uat)} -ArgumentList @({arglist}) -WindowStyle Hidden "
               f"-PassThru -Wait -RedirectStandardOutput {ps_quote(log)} -RedirectStandardError {ps_quote(str(log) + '.err')}; "
               "Write-Output \"UAT_EXIT=$($p.ExitCode)\"")
        stdout = r.stdout + r.stderr
    else:
        r = subprocess.run(["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(PACKAGE),
                            "-SkipBuild", "-Log", str(log)], capture_output=True, text=True, encoding="utf-8",
                           errors="replace", creationflags=NO_WINDOW)
        stdout = r.stdout + r.stderr
    (out / f"{a.label}-package.stdout.txt").write_text(stdout, encoding="utf-8", newline="\n")
    m = re.search(r"UAT_EXIT=(-?\d+)", stdout)
    rec["uatExit"] = int(m.group(1)) if m else None
    rec["scriptExit"] = r.returncode
    rec["refusedByGuard"] = "built with -NoLiveCoding" in stdout
    rec["durationS"] = round(time.time() - started, 1)
    rec["finishedLocal"] = now_local()
    rec["buildSuccessful"] = bool(log.is_file() and select_string(log, "BUILD SUCCESSFUL", simple=True))
    reg = {}
    if ASSET_REGISTRY.is_file():
        for name in MESH.values():
            reg[name] = bool(select_string(ASSET_REGISTRY, name, simple=True))
        rec["assetRegistry"] = {"path": rel(ASSET_REGISTRY), "sha256": sha256_file(ASSET_REGISTRY), "contains": reg}
    ok_stage = STAGED_INNER_EXE.is_file() and BIN_EXE.is_file()
    rec["exe"] = {
        "binariesSha256": sha256_file(BIN_EXE) if BIN_EXE.is_file() else None,
        "stagedInnerSha256": sha256_file(STAGED_INNER_EXE) if STAGED_INNER_EXE.is_file() else None,
        "stagedRootStubSha256": sha256_file(STAGED_ROOT_EXE) if STAGED_ROOT_EXE.is_file() else None,
        "stagedInnerPath": rel(STAGED_INNER_EXE),
        "note": "the staged ROOT Unmatched.exe is a launcher stub; only the inner Binaries/Win64 exe is compared"}
    rec["exe"]["innerEqualsBinaries"] = ok_stage and rec["exe"]["binariesSha256"] == rec["exe"]["stagedInnerSha256"]
    rec["frameRateLimit"] = {"defaultGameUserSettings": ini_value(DEFAULT_GUS, "FrameRateLimit"),
                             "stagedGameUserSettings": ini_value(STAGED_GUS, "FrameRateLimit"),
                             "stagedGameUserSettingsExists": STAGED_GUS.is_file()}
    write_json(out / f"{a.label}-package.json", rec)
    print(json.dumps({k: rec.get(k) for k in ("label", "mode", "uatExit", "scriptExit", "refusedByGuard",
                                               "buildSuccessful")}, ensure_ascii=False))
    print(json.dumps(rec.get("assetRegistry", {}).get("contains"), ensure_ascii=False), rec["exe"]["innerEqualsBinaries"])
    if a.expect_refusal:
        return 0 if rec["refusedByGuard"] and rec["scriptExit"] != 0 else 1
    good = rec["buildSuccessful"] and rec["exe"]["innerEqualsBinaries"] and all(reg.values() or [False])
    return 0 if good else 1


# ------------------------------------------------------------------ samplers
class Samplers:
    def __init__(self, out: Path):
        self.out = out
        self.gpu_csv = out / "nvidia-smi-gpu.csv"
        self.pmon_txt = out / "nvidia-smi-pmon.txt"
        self.procs: list[subprocess.Popen] = []

    def start(self):
        self.out.mkdir(parents=True, exist_ok=True)
        self._g = self.gpu_csv.open("w", encoding="utf-8", newline="\n")
        self._g.write("timestamp,utilization.gpu,utilization.memory,memory.used,power.draw,clocks.gr,temperature.gpu\n")
        self._g.flush()
        self.procs.append(subprocess.Popen(
            ["nvidia-smi", "--query-gpu=timestamp,utilization.gpu,utilization.memory,memory.used,power.draw,"
             "clocks.gr,temperature.gpu", "--format=csv,noheader,nounits", "-lms", "500"],
            stdout=self._g, stderr=subprocess.DEVNULL, creationflags=NO_WINDOW))
        self._p = self.pmon_txt.open("w", encoding="utf-8", newline="\n")
        self.procs.append(subprocess.Popen(["nvidia-smi", "pmon", "-s", "um", "-d", "1", "-o", "DT"],
                                           stdout=self._p, stderr=subprocess.DEVNULL, creationflags=NO_WINDOW))

    def stop(self):
        for p in self.procs:
            if p.poll() is None:
                p.terminate()
                try:
                    p.wait(10)
                except subprocess.TimeoutExpired:
                    p.kill()
        self._g.close()
        self._p.close()


def parse_gpu_csv(p: Path) -> list[dict]:
    rows = []
    for ln in p.read_text(encoding="utf-8", errors="replace").splitlines()[1:]:
        f = [x.strip() for x in ln.split(",")]
        if len(f) < 7:
            continue
        try:
            t = dt.datetime.strptime(f[0], "%Y/%m/%d %H:%M:%S.%f")
            rows.append({"t": t, "gpu": float(f[1]), "mem": float(f[2]), "memUsedMiB": float(f[3]),
                         "powerW": float(f[4]), "clockMHz": float(f[5])})
        except ValueError:
            continue
    return rows


def parse_pmon(p: Path) -> list[dict]:
    rows = []
    for ln in p.read_text(encoding="utf-8", errors="replace").splitlines():
        if ln.startswith("#") or not ln.strip():
            continue
        f = ln.split()
        # Date Time gpu pid type sm mem enc dec jpg ofa fb ccpm command
        if len(f) < 13:
            continue
        try:
            t = dt.datetime.strptime(f[0] + " " + f[1], "%Y%m%d %H:%M:%S")
            rows.append({"t": t, "pid": int(f[3]), "sm": None if f[5] == "-" else float(f[5]),
                         "mem": None if f[6] == "-" else float(f[6]),
                         "fbMiB": None if f[11] == "-" else float(f[11]), "name": " ".join(f[13:])})
        except (ValueError, IndexError):
            continue
    return rows


def stats(values: list[float]) -> dict:
    v = sorted(x for x in values if x is not None)
    if not v:
        return {"n": 0}
    pct = lambda q: v[min(len(v) - 1, max(0, math.ceil(q * len(v)) - 1))]  # noqa: E731  nearest rank
    return {"n": len(v), "mean": round(sum(v) / len(v), 2), "p50": pct(0.5), "p95": pct(0.95), "max": v[-1]}


# ------------------------------------------------------------------ CSV profiler summary
def summarize_csv(path: Path, warmup_frames: int = 150) -> dict:
    """Per-frame stats from a UE CSV profiler capture. GPU busy = sum of the GPU/<pass> columns
    (r.GPUCsvStatsEnabled via -csvGpuStats). GPUTime is the D3D11 BeginWork..EndWork interval of the
    frame, which spans the whole frame period under t.MaxFPS (not GPU busy time)."""
    lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    header = lines[0].split(",")
    idx = {name: i for i, name in enumerate(header)}
    gpu_cols = [i for i, name in enumerate(header) if name.startswith("GPU/") and name != "GPU/Unaccounted"]
    unacc = idx.get("GPU/Unaccounted")
    cols = {k: idx.get(k) for k in ("FrameTime", "GameThreadTime", "RenderThreadTime", "RHIThreadTime", "GPUTime")}
    data = {k: [] for k in cols}
    data["GPUBusy"] = []
    data["GPUUnaccounted"] = []
    for ln in lines[1:]:
        f = ln.split(",")
        if len(f) < len(header) - 1 or cols["FrameTime"] is None:
            continue
        try:
            ft = float(f[cols["FrameTime"]])
        except (ValueError, IndexError):
            continue
        for k, i in cols.items():
            try:
                data[k].append(float(f[i]) if i is not None and f[i] != "" else None)
            except (ValueError, IndexError):
                data[k].append(None)
        busy = 0.0
        for i in gpu_cols:
            try:
                busy += float(f[i]) if i < len(f) and f[i] != "" else 0.0
            except ValueError:
                pass
        data["GPUBusy"].append(busy)
        try:
            data["GPUUnaccounted"].append(float(f[unacc]) if unacc is not None and f[unacc] != "" else None)
        except (ValueError, IndexError):
            data["GPUUnaccounted"].append(None)
    n = len(data["FrameTime"])
    sl = slice(min(warmup_frames, n), n)
    meta = {}
    if lines and lines[-1].startswith("["):
        m = lines[-1].split(",")
        meta = {m[i].strip("[]"): m[i + 1] for i in range(0, len(m) - 1, 2)}
    out = {"file": path.name, "framesTotal": n, "warmupFramesSkipped": min(warmup_frames, n),
           "gpuPassColumns": len(gpu_cols),
           "metadata": {k: meta.get(k) for k in ("config", "buildversion", "targetframerate", "vsyncenabled", "commandline")
                        if k in meta}}
    for k, v in data.items():
        out[k] = stats([x for x in v[sl] if x is not None])
    ft = [x for x in data["FrameTime"][sl] if x is not None]
    out["effectiveFps"] = round(1000.0 * len(ft) / sum(ft), 2) if ft else None
    out["hitchesOver50ms"] = sum(1 for x in ft if x > 50)
    return out


def write_csv_summary(run_dir: Path) -> dict | None:
    csv_dir = RAW_ROOT / run_dir.name / "client-csv"
    if not csv_dir.is_dir():
        csv_dir = run_dir / "client-csv"
    if not csv_dir.is_dir():
        return None
    doc = {"schema": "unmatched.art004-perf-csv/1", "status": "измерено",
           "method": "UE CSV profiler (-csvCaptureFrames, -csvGpuStats); first 150 frames skipped as warm-up",
           "gpuBusyDefinition": "sum of the named GPU/<pass> times per frame (D3D11 timestamp queries), GPU/Unaccounted "
                                "excluded; means are inflated by rare long passes when other processes preempt the GPU, "
                                "p50 is the typical per-frame GPU cost",
           "gpuUnaccountedDefinition": "GPU/Unaccounted = BeginWork..EndWork time not covered by named passes (idle gaps "
                                       "and other processes' work on the shared GPU)",
           "gpuTimeCaveat": "GPUTime (and PERF gpuMs in the trace) is the D3D11 BeginWork..EndWork interval, which spans the "
                            "whole frame period under t.MaxFPS; use GPUBusy for the per-client GPU load",
           "rawOutsideGit": [], "clients": {}}
    for f in sorted(csv_dir.glob("*.csv")):
        role = f.name.split("-", 1)[0]
        doc["clients"][role] = summarize_csv(f)
        doc["rawOutsideGit"].append({"path": rel(f), "bytes": f.stat().st_size, "sha256": sha256_file(f)})
    write_json(run_dir / "perf-csv.json", doc)
    return doc


# ------------------------------------------------------------------ baseline
def cmd_baseline(a) -> int:
    out = Path(a.out).resolve()
    s = Samplers(out)
    start = dt.datetime.now()
    s.start()
    time.sleep(a.seconds)
    s.stop()
    gpu = parse_gpu_csv(s.gpu_csv)
    pmon = parse_pmon(s.pmon_txt)
    by_name: dict[str, list[float]] = {}
    for r in pmon:
        if r["sm"] is not None:
            by_name.setdefault(f"{r['name']}#{r['pid']}", []).append(r["sm"])
    doc = {"schema": "unmatched.art004-gpu-baseline/1", "startedLocal": start.astimezone().isoformat(timespec="seconds"),
           "seconds": a.seconds, "note": "no packaged client running; other GPU users listed per process",
           "gpuUtilizationPct": stats([r["gpu"] for r in gpu]), "memUsedMiB": stats([r["memUsedMiB"] for r in gpu]),
           "powerW": stats([r["powerW"] for r in gpu]),
           "perProcessSmPct": {k: stats(v) for k, v in sorted(by_name.items())}}
    write_json(out / "gpu-baseline.json", doc)
    print(json.dumps({"gpu": doc["gpuUtilizationPct"], "top": sorted(
        ((k, v.get("mean", 0)) for k, v in doc["perProcessSmPct"].items()), key=lambda kv: -kv[1])[:5]},
        ensure_ascii=False))
    return 0


# ------------------------------------------------------------------ run
TRACE_TS = re.compile(r"^(\d{4})\.(\d{2})\.(\d{2})-(\d{2})\.(\d{2})\.(\d{2})")


def trace_time(line: str):
    m = TRACE_TS.match(line)
    return dt.datetime(*map(int, m.groups()), tzinfo=dt.timezone.utc) if m else None


def parse_perf(trace: Path) -> dict:
    text = trace.read_text(encoding="utf-8-sig", errors="replace").splitlines()
    out = {"config": None, "windows": [], "summary": {}}
    num = r"(-?\d+(?:\.\d+)?)"
    for ln in text:
        if "PERF config" in ln:
            out["config"] = dict(re.findall(r"(\w+)=([^\s]+)", ln.split("PERF config", 1)[1]))
        elif "PERF window" in ln or "PERF summary" in ln:
            body = ln.split("PERF ", 1)[1]
            d = {}
            for key, grp in (("frameMs", "frameMs"), ("gpuMs", "gpuMs"), ("gameMs", "gameMs"), ("renderMs", "renderMs")):
                m = re.search(grp + r" ((?:\w+=" + num + r"\s*)+)", body)
                if m:
                    d[key] = {k: float(v) for k, v in re.findall(r"(\w+)=" + num, m.group(1))}
            for k in ("frames", "fps", "hitches50"):
                m = re.search(r"\b" + k + "=" + num, body)
                if m:
                    d[k] = float(m.group(1))
            if body.startswith("window"):
                m = re.search(r"t=" + num + "-" + num, body)
                d["t"] = [float(m.group(1)), float(m.group(2))] if m else None
                out["windows"].append(d)
            else:
                scope = re.search(r"scope=(\w+)", body).group(1)
                out["summary"][scope] = d
    return out


def parse_timing(trace: Path) -> dict:
    lines = trace.read_text(encoding="utf-8-sig", errors="replace").splitlines()
    t0 = next((trace_time(x) for x in lines if "S08 trace open" in x), None)

    def first(pat):
        for x in lines:
            if re.search(pat, x):
                t = trace_time(x)
                return (t - t0).total_seconds() if (t and t0) else None
        return None
    settled = next((x for x in lines if "CAMERA settled" in x), None)
    d = {"traceOpenUtc": t0.isoformat() if t0 else None,
         "startGameS": first(r"startGame -> "), "board5x6S": first(r"BOARD 5x6"),
         "selectionS": first(r"ARTPREVIEW selection ownHero=1"), "focusRequestedS": first(r"camera focus requested"),
         "cameraSettledS": first(r"CAMERA settled"), "shotS": first(r"SHOT requested"),
         "traceCloseS": first(r"S08 trace close"),
         "cameraSettledElapsed": float(re.search(r"elapsed=([\d.]+)", settled).group(1)) if settled else None}
    shot_cam = next((x for x in lines if "SHOT camera " in x), None)
    if shot_cam:
        d["shotCamera"] = dict(re.findall(r"(\w+)=([^\s]+)", shot_cam.split("SHOT camera", 1)[1]))
    heads = [x for x in lines if "SHOT head fighter=" in x]
    d["shotHeads"] = [dict(re.findall(r"(\w+)=(\([^)]*\)|[^\s]+)", x.split("SHOT head", 1)[1])) for x in heads]
    return d


def find_client_pids(since: float) -> list[dict]:
    r = ps("Get-CimInstance Win32_Process -Filter \"Name='Unmatched.exe'\" | ForEach-Object { "
           "[pscustomobject]@{pid=$_.ProcessId; parent=$_.ParentProcessId; exe=$_.ExecutablePath; "
           "created=$_.CreationDate.ToString('o')} } | ConvertTo-Json -Compress")
    try:
        d = json.loads(r.stdout.strip() or "[]")
    except ValueError:
        return []
    return d if isinstance(d, list) else [d]


def cmd_run(a) -> int:
    if a.board_id != REVIEW_BOARD_ID:
        print(f"REFUSED: board id {a.board_id!r} is not the 5x6 Cobble review Board row {REVIEW_BOARD_ID}")
        return 2
    evidence = Path(a.evidence_dir).resolve()
    evidence.mkdir(parents=True, exist_ok=True)
    work = Path(a.work).resolve() / f"{a.label}-{dt.datetime.now():%Y%m%d-%H%M%S}"
    work.mkdir(parents=True, exist_ok=True)
    backend = listeners(3120)
    if len(backend) != 1:
        print(f"REFUSED: expected exactly one backend listener on :3120, got {backend}")
        return 2
    env = os.environ.copy()
    benv = load_backend_env()
    for k in ("S08_DEMO_HOST_EMAIL", "S08_DEMO_HOST_PASSWORD", "S08_DEMO_JOINER_EMAIL", "S08_DEMO_JOINER_PASSWORD"):
        env[k] = benv[k]  # environment only, never argv
    cmd = ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(DEMO),
           "-Api", API, "-EvidenceDir", str(evidence), "-ArtPreviewBoardId", a.board_id,
           "-RunSeconds", str(a.run_seconds), "-ClientFps", str(a.client_fps),
           "-ArtPreviewShotAfter", str(a.shot_after), "-ClientPerf", "-ClientCsvFrames", str(a.csv_frames)]
    if a.zoom:
        cmd += ["-ArtPreviewFocusZoom", str(a.zoom)]
    if a.variant != "none":
        cmd += ["-ArtPreviewMedusaVariant", a.variant]
    record = {"schema": "unmatched.art004-live-run/1", "label": a.label, "startedLocal": now_local(),
              "argv": [c if not c.startswith(str(REPO)) else rel(Path(c)) for c in cmd],
              "credentials": "S08_DEMO_* from backend/.env injected into the child environment only (not argv)",
              "backend": {"port": 3120, "pid": backend[0], "process": process_info(backend[0])},
              "variantFlag": a.variant, "expectedMesh": MESH.get(a.variant if a.variant != "none" else "face-neck-v2"),
              "zoom": a.zoom, "shotAfter": a.shot_after, "runSeconds": a.run_seconds, "clientFps": a.client_fps}
    samplers = Samplers(work)
    t_start = time.time()
    samplers.start()
    time.sleep(2)
    seen_pids: dict[int, dict] = {}
    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, env=env, cwd=str(REPO),
                            creationflags=NO_WINDOW)
    # poll the client PIDs while the pair runs (per-process GPU attribution)
    out_chunks = []
    import threading

    def reader():
        for line in iter(proc.stdout.readline, b""):
            out_chunks.append(line)
    th = threading.Thread(target=reader, daemon=True)
    th.start()
    while proc.poll() is None:
        for c in find_client_pids(t_start):
            seen_pids.setdefault(c["pid"], c)
        time.sleep(2)
    th.join(10)
    time.sleep(2)
    samplers.stop()
    t_end = time.time()
    stdout = b"".join(out_chunks).decode("utf-8", errors="replace")
    (work / "demo.stdout.txt").write_text(stdout, encoding="utf-8", newline="\n")
    record["demoExit"] = proc.returncode
    record["finishedLocal"] = now_local()
    record["durationS"] = round(t_end - t_start, 1)
    m = re.search(r"published evidence run dir: (.+?) \(pointer", stdout)
    run_dir = Path(m.group(1).strip()) if m else None
    staging = re.search(r"staging: (\S+)", stdout)
    record["staging"] = staging.group(1) if staging else None
    record["roomAborted"] = bool(re.search(r"cleanup: aborted THIS run's game id=\S+ status=ABORTED \(verified\)", stdout))
    record["cleanupLine"] = next((x for x in stdout.splitlines() if x.startswith("cleanup:")), None)
    if run_dir is None:
        run_dir = evidence / f"failed-{dt.datetime.now():%Y%m%d-%H%M%S}"
        run_dir.mkdir(parents=True, exist_ok=True)
        if record["staging"] and Path(record["staging"]).is_dir():
            for f in Path(record["staging"]).iterdir():
                if f.is_file():
                    shutil.copy2(f, run_dir / f.name)
    record["runDir"] = rel(run_dir)
    # client logs: copy right away (the next package step cleans the stage dir)
    logs_dir = run_dir / "client-logs"
    logs_dir.mkdir(exist_ok=True)
    copied = []
    for f in sorted(STAGED_LOGS.glob("Unmatched*.log")) if STAGED_LOGS.is_dir() else []:
        if f.stat().st_mtime >= t_start - 1:
            shutil.copy2(f, logs_dir / f.name)
            copied.append({"name": f.name, "bytes": f.stat().st_size, "sha256": sha256_file(logs_dir / f.name)})
    record["clientLogs"] = copied
    # CSV profiler captures (per-frame FrameTime / GPU busy per pass), one per client
    raw_dir = RAW_ROOT / run_dir.name
    csv_dir = raw_dir / "client-csv"
    csvs = []
    for f in sorted(STAGED_CSV.glob("*.csv")) if STAGED_CSV.is_dir() else []:
        if f.stat().st_mtime >= t_start - 1:
            text = f.read_text(encoding="utf-8", errors="replace")
            role = "host" if "phase2-client-host" in text else "joiner" if "phase2-client-joiner" in text else "unknown"
            csv_dir.mkdir(parents=True, exist_ok=True)
            dst = csv_dir / f"{role}-{f.name.replace('(', '-').replace(')', '')}"
            shutil.copy2(f, dst)
            csvs.append({"role": role, "path": rel(dst), "bytes": dst.stat().st_size, "sha256": sha256_file(dst)})
    record["clientCsv"] = csvs
    for f in (work / "demo.stdout.txt", samplers.gpu_csv):
        shutil.copy2(f, run_dir / f.name)
    raw_dir.mkdir(parents=True, exist_ok=True)
    shutil.copy2(samplers.pmon_txt, raw_dir / samplers.pmon_txt.name)
    record["rawOutsideGit"] = csvs + [{"path": rel(raw_dir / samplers.pmon_txt.name),
                                       "bytes": samplers.pmon_txt.stat().st_size,
                                       "sha256": sha256_file(samplers.pmon_txt)}]
    # crash evidence (expected in the -NoLiveCoding A/B leg)
    crash = []
    for c in copied:
        for ln in (logs_dir / c["name"]).read_text(encoding="utf-8-sig", errors="replace").splitlines():
            if "Unhandled Exception" in ln or "[Callstack]" in ln or "Fatal error" in ln:
                crash.append(f"{c['name']}: {ln.strip()}")
    record["crashLines"] = crash[:40]
    record["clientProcesses"] = list(seen_pids.values())
    # perf
    traces = {role: run_dir / f"phase2-client-{role}.trace.log" for role in ("host", "joiner")}
    gpu = parse_gpu_csv(samplers.gpu_csv)
    pmon = parse_pmon(samplers.pmon_txt)
    client_pids = {c["pid"] for c in seen_pids.values()}
    both_alive = []
    if pmon:
        by_t: dict = {}
        for r in pmon:
            by_t.setdefault(r["t"], []).append(r)
        for t, rows in sorted(by_t.items()):
            present = [r for r in rows if r["pid"] in client_pids]
            if len(present) >= 2:
                both_alive.append(t)
    win = (min(both_alive), max(both_alive)) if both_alive else None
    in_win = [r for r in gpu if win and win[0] <= r["t"] <= win[1]]
    per_proc = {}
    for r in pmon:
        if r["pid"] in client_pids or r["name"].lower().startswith(("unrealeditor", "blender", "dwm")):
            per_proc.setdefault(f"{r['name']}#{r['pid']}", []).append(r["sm"])
    perf = {"schema": "unmatched.art004-perf/1", "status": "измерено",
            "scope": "текущий ПК разработки (RTX 4090), не целевой ПК D-07; ACC-022 не заявляется",
            "clientFpsCap": a.client_fps, "clients": {},
            "gpuTotal": {"window": [win[0].isoformat(), win[1].isoformat()] if win else None,
                         "windowRule": "seconds where nvidia-smi pmon lists both packaged client processes",
                         "utilizationPct": stats([r["gpu"] for r in in_win]),
                         "memUsedMiB": stats([r["memUsedMiB"] for r in in_win]),
                         "powerW": stats([r["powerW"] for r in in_win])},
            "perProcessSmPct": {k: stats(v) for k, v in sorted(per_proc.items())},
            "concurrentGpuUsers": "UnrealEditor PID 19540 (main checkout, orchestrator, idle viewport) and Blender MCP "
                                  "sessions 9876/9877 were running; see perProcessSmPct and gpu-baseline.json"}
    for role, tp in traces.items():
        if tp.is_file():
            perf["clients"][role] = parse_perf(tp)
    frl = {"defaultGameUserSettings": ini_value(DEFAULT_GUS, "FrameRateLimit"),
           "stagedGameUserSettings": ini_value(STAGED_GUS, "FrameRateLimit"),
           "stagedGameUserSettingsExists": STAGED_GUS.is_file(),
           "perClientTrace": {r: (perf["clients"].get(r) or {}).get("config") for r in traces}}
    perf["frameRateLimit"] = frl
    write_json(run_dir / "perf.json", perf)
    write_csv_summary(run_dir)
    timing = {role: parse_timing(tp) for role, tp in traces.items() if tp.is_file()}
    write_json(run_dir / "timing.json", timing)
    record["timing"] = timing
    # sidecars (strict grade) for published frames
    build = json.loads(Path(a.build_record).read_text(encoding="utf-8")) if a.build_record else {}
    pkg = json.loads(Path(a.package_record).read_text(encoding="utf-8")) if a.package_record else {}
    for png in sorted(run_dir.glob("phase2-board-*-1920x1080.png")):
        side = {"schema": SIDECAR_SCHEMA, "class": "packaged-live", "frame": png.name, "frameSha256": sha256_file(png),
                "build": {"label": build.get("label"), "result": build.get("result"), "flags": build.get("flags"),
                          "log": build.get("log"), "withLiveCoding": build.get("withLiveCodingValues"),
                          "exeSha256": (pkg.get("exe") or {}).get("binariesSha256"),
                          "stagedInnerExeSha256": (pkg.get("exe") or {}).get("stagedInnerSha256"),
                          "buildRecord": rel(Path(a.build_record)) if a.build_record else None,
                          "packageRecord": rel(Path(a.package_record)) if a.package_record else None},
                "run": {"boardId": a.board_id, "roomStatus": "ABORTED" if record["roomAborted"] else None,
                        "variantFlag": a.variant, "zoom": a.zoom, "shotAfter": a.shot_after,
                        "runSeconds": a.run_seconds, "clientFps": a.client_fps, "cleanupLine": record["cleanupLine"]},
                "status": "измерено (кадр с HUD и boardState; художественная приёмка лица не выполнялась)"}
        write_json(png.with_name(png.stem + ".evidence.json"), side)
    write_json(run_dir / "run-record.json", record)
    # extend the run manifest with everything added after publish
    man = run_dir / "manifest.json"
    if man.is_file():
        doc = json.loads(man.read_text(encoding="utf-8-sig"))
        listed = {e["name"] for e in doc["files"]}
        extra = []
        for f in sorted(run_dir.rglob("*")):
            if f.is_file() and f.name != "manifest.json":
                name = f.relative_to(run_dir).as_posix()
                if name not in listed:
                    extra.append({"name": name, "bytes": f.stat().st_size, "sha256": sha256_file(f)})
        doc["files"] += extra
        doc["extendedBy"] = "tools/art/art004_live_k2.py run (client logs, perf, timing, sidecars, nvidia-smi, stdout)"
        man.write_text(json.dumps(doc, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps({"label": a.label, "demoExit": proc.returncode, "runDir": record["runDir"],
                      "roomAborted": record["roomAborted"], "clientLogs": [c["name"] for c in copied],
                      "crashLines": len(crash)}, ensure_ascii=False))
    tail = [x for x in stdout.splitlines() if re.search(r"throw|Exception|trace missing|exited before|FAILED|missing", x)]
    for x in tail[:8]:
        print("  |", x[:300])
    if a.expect_crash:
        return 0 if proc.returncode != 0 and crash else 1
    return proc.returncode


# ------------------------------------------------------------------ metrics
# Band audit (T1.1 verify, 2026-09-28, checked pixel by pixel on the 5x and 1.6x host frames).
# The fallback bands are anchored to the traced Head socket, which sits at the base of the neck (bone head
# + 4 uu, world z 38.5 of a 55 uu figure), so the K2-01 crop is centred on the chest. On screen:
#   * the K2-02 band (Head+2..+9 uu; the literal "upper third of Head+-6" Head+2..+6 is even lower) lies on
#     the neck and the chiton neckline, not on the face. Its v3 gain at 5x comes from the dark V-band along
#     the neckline (defect P1 of the A1 act), not from facial detail;
#   * the K2-03 band (Head+10..+18 uu) holds v3's face (eyes, nose, mouth) but v2's crown and snakes. Its
#     connected components are background (the largest, ~2970 px at 5x, is the black shadow on the right)
#     and small contrast blobs on snakes, hair and face, not crown segments.
# A band fixed in screen space cannot separate face from crown across variants: the head tilt moves the one
# into the other's place. The registered thresholds are not changed retroactively (E3), so the numbers are
# kept as "formally computed on the registered band" and both metrics are "не измерено (невалидно)".
BAND_STATUS_INVALID = "не измерено (невалидно)"
FALLBACK_BAND_AUDIT = {
    "date": "2026-09-28",
    "by": "T1.1 verify (pixel check of the band placement) + T1.1 rework",
    "K2_02": {
        "status": BAND_STATUS_INVALID,
        "bandCovers": {"face-neck-v2": "шея и вырез хитона",
                       "head-tilt-v3": "шея и вырез хитона с тёмной V-полосой P1"},
        "reason": "полоса Head+2..+9 uu (и буквальная Head+2..+6 uu) в экранной проекции лежит ниже лица: сокет Head "
                  "стоит у основания шеи, кроп K2-01 центрирован на груди. Прирост у v3 при 5x даёт тёмная "
                  "V-полоса P1 по вырезу хитона, а не черты лица",
    },
    "K2_03": {
        "status": BAND_STATUS_INVALID,
        "bandCovers": {"face-neck-v2": "венец и змеи",
                       "head-tilt-v3": "лицо (глаза, нос, рот) и нижний край змей"},
        "reason": "полоса Head+10..+18 uu у v3 содержит лицо, у v2 — венец и змей; связные компоненты — фон "
                  "(крупнейшая, ~2970 px при 5x, — чёрная тень справа) и мелкие пятна контраста на змеях, волосах "
                  "и лице, а не сегменты венца; полоса у вариантов содержит разные части головы",
    },
    "consequence": "K2-02/K2-03 из T1.1 не подтверждают и не опровергают v3 >= v2; опорой для workingZoomProposal "
                   "(thresholds.json E1_k2_live) они служить не могут",
    "illustrations": "k2-crops/k2-bands-*-v2-left-v3-right.png",
}
# Diagnostics only (NOT registered metrics, no pass/fail, E3): the dark-pixel rule of the verify pass and
# the head/face zone the audit located by eye (crop rows 5..40 at 5x == Head+9.5..+17 uu on screen).
DARK_LUMA = 25.0
DARK_DILATE = 2
OBSERVED_HEAD_ZONE_Z = (9.5, 17.0)
PROPOSED_THRESHOLD_REVISION = {
    "status": "предложено, не применено; владелец thresholds.json — T0, правка только новой записью revisions "
              "до прогонов, к которым она применяется (E3)",
    "K2_01": "центр кропа — экранная проекция Head+12 uu, сторона — 3 x проекция отрезка Head..Head+24 uu (лицо, "
             "венец и змеи целиком), не меньше 96 px",
    "K2_02_K2_03_masks": "маски лица и венца — репроекция ID-маски Blender по той же камере отдельно для каждого "
                         "варианта: наклон головы переставляет лицо и венец, поэтому общая для v2 и v3 полоса в "
                         "экранных координатах их не разделяет",
    "K2_02_K2_03_fallback": "если репроекции нет: полосы от проекции лица и венца (у v3 при 5x лицо ≈ Head+10..+18 uu "
                            "в экранной проекции), подобранные по кадру-оверлею отдельно для каждого варианта и зума и "
                            "зарегистрированные до прогона",
    "placementGate": "K2-02/K2-03 засчитываются, только если оверлей полос (k2-bands-*.png) просмотрен и полоса лежит "
                     "на лице/венце у обоих вариантов; иначе — «не измерено (невалидно)»",
    "K2_02_darkPixels": "энергию K2-02 считать и без окрестности тёмных пикселей (luma < 25, ±2 px): тёмный шов или "
                        "просвет у шеи иначе засчитывается как деталь лица",
}


def _dig(d, path):
    for k in path:
        if not isinstance(d, dict):
            return None
        d = d.get(k)
    return d


def _zoom_tag(z) -> str:
    z = float(z)
    return f"{int(z)}x" if z.is_integer() else f"{z:g}".replace(".", "p")


def cmd_metrics(a) -> int:
    if getattr(a, "threshold_set", THRESHOLD_SET_REGISTERED) != THRESHOLD_SET_REGISTERED:
        return cmd_metrics_revision(a)
    import numpy as np
    from PIL import Image, ImageDraw
    from scipy import ndimage

    def luma(img):
        arr = np.asarray(img.convert("RGB"), dtype=np.float32)
        return 0.2126 * arr[..., 0] + 0.7152 * arr[..., 1] + 0.0722 * arr[..., 2], arr

    rows = []
    # Derived crops live outside the run dirs (they are not packaged-live frames themselves).
    crop_dir = Path(a.out).resolve().parent / "k2-crops"
    for d in a.run_dirs:
        rd = Path(d).resolve()
        png = rd / "phase2-board-host-1920x1080.png"
        timing = json.loads((rd / "timing.json").read_text(encoding="utf-8"))
        status = json.loads((rd / "art-preview-status.json").read_text(encoding="utf-8-sig"))
        host = timing["host"]
        tr = (rd / "phase2-client-host.trace.log").read_text(encoding="utf-8-sig", errors="replace")
        m = re.search(r"ARTPREVIEW selection ownHero=1 selected=1 .* fighterId=(\S+)", tr)
        sel = m.group(1) if m else None
        head = next((h for h in host.get("shotHeads", []) if h.get("fighter") == sel), None)
        if not head:
            rows.append({"run": rel(rd), "error": "no SHOT head line for the selected hero"})
            continue
        cx, cy = [float(v) for v in head["screen"].strip("()").split(",")]
        head_px = float(head["headPx"])
        side = max(96, int(round(3 * head_px)))
        x0, y0 = int(round(cx - side / 2)), int(round(cy - side / 2))
        img = Image.open(png)
        crop = img.crop((x0, y0, x0 + side, y0 + side))
        crop_dir.mkdir(parents=True, exist_ok=True)
        crop_path = crop_dir / f"k2crop-{rd.parent.parent.name}-{rd.parent.name}-{rd.name}-host.png"
        crop.save(crop_path)
        L, rgb = luma(crop)
        gx = ndimage.sobel(L, axis=1)
        gy = ndimage.sobel(L, axis=0)
        mag = np.hypot(gx, gy)
        # Screen scale along world Z at the head: the trace projects Head+-6 uu -> headPx.
        spu = head_px / 12.0
        hy = cy - y0  # Head socket row inside the crop

        def rect(z_lo, z_hi, half_w):
            r0 = max(0, int(round(hy - z_hi * spu)))
            r1 = min(side, max(r0 + 1, int(round(hy - z_lo * spu))))
            c0 = max(0, int(round(side / 2 - half_w)))
            c1 = min(side, max(c0 + 1, int(round(side / 2 + half_w))))
            return (slice(r0, r1), slice(c0, c1)), [c0, r0, c1, r1]

        # Registered fallback bands (FALLBACK_BAND_AUDIT: on screen they miss the face and the crown).
        lit, lit_box = rect(2.0, 6.0, side / 6.0)        # literal "upper third of Head +- 6 uu"
        face, face_box = rect(2.0, 9.0, side / 6.0)      # K2-02 band, middle third of the crop width
        crown, crown_box = rect(10.0, 18.0, 0.3 * side)  # K2-03 band, 60 % of the crop width
        zone, zone_box = rect(OBSERVED_HEAD_ZONE_Z[0], OBSERVED_HEAD_ZONE_Z[1], side / 6.0)
        k202 = float(mag[face].mean()) if mag[face].size else None
        k202_lit = float(mag[lit].mean()) if mag[lit].size else None
        # Dark-pixel diagnostics of the K2-02 band (verify rule: luma < 25, two 4-neighbour dilations).
        fb, fm = L[face], mag[face]
        dark = fb < DARK_LUMA
        darkd = ndimage.binary_dilation(dark, iterations=DARK_DILATE) if dark.any() else dark
        dark_diag = {"lumaBelow": DARK_LUMA, "dilateIterations": DARK_DILATE, "darkPx": int(dark.sum()),
                     "bandPx": int(fb.size),
                     "sobelShareNearDark": round(float(fm[darkd].sum() / fm.sum()), 3) if fm.sum() else None,
                     "energyWithoutDarkNeighbourhood": round(float(fm[~darkd].mean()), 3) if (~darkd).any() else None}
        band = L[crown]
        segs = None
        comps = []
        if band.size:
            thr = band.mean()
            lab, n = ndimage.label(np.abs(band - thr) > 12)
            sizes = ndimage.sum(np.ones_like(band), lab, range(1, n + 1)) if n else []
            keep = [i + 1 for i, sz in enumerate(sizes) if sz >= 6]
            segs = len(keep)
            crgb = rgb[crown]
            for i in keep:
                ys, xs = np.where(lab == i)
                comps.append({"px": int(len(ys)),
                              "bboxInCrop": [int(xs.min()) + crown_box[0], int(ys.min()) + crown_box[1],
                                             int(xs.max()) + crown_box[0] + 1, int(ys.max()) + crown_box[1] + 1],
                              "vsBandMean": "brighter" if float(band[lab == i].mean()) > thr else "darker",
                              "meanRGB": [int(round(float(x))) for x in crgb[lab == i].mean(axis=0)]})
            comps.sort(key=lambda c: -c["px"])
        variant = status.get("medusaVariant")
        rows.append({
            "run": rel(rd), "variant": variant, "explicit": status.get("medusaVariantExplicit"),
            "zoom": status.get("hostFocusZoom"), "selectedFighter": sel, "mesh": head.get("mesh"),
            "headSocketWorld": head.get("world"),
            "K2_01_crop": {"center": [cx, cy], "headPx": head_px, "side": side, "box": [x0, y0, x0 + side, y0 + side],
                           "pxPerUuZ": round(spu, 3), "file": rel(crop_path), "sha256": sha256_file(crop_path),
                           "note": "центр — проекция сокета Head у основания шеи, поэтому кроп центрирован на груди"},
            "K2_02": {"status": BAND_STATUS_INVALID,
                      "formalValueRegisteredBand": round(k202, 3) if k202 is not None else None,
                      "formalValueLiteralUpperThirdHeadSpan": round(k202_lit, 3) if k202_lit is not None else None,
                      "bandZ": "Head+2..Head+9 uu", "bandBoxInCrop": face_box,
                      "literalBandZ": "Head+2..Head+6 uu", "literalBandBoxInCrop": lit_box,
                      "method": "mean Sobel magnitude of display luma in the band; fallback without Blender ID-mask "
                                "reprojection, middle third of the crop width",
                      "bandCovers": FALLBACK_BAND_AUDIT["K2_02"]["bandCovers"].get(variant),
                      "darkPixelDiagnostics": dark_diag},
            "K2_03": {"status": BAND_STATUS_INVALID,
                      "formalValueRegisteredBand": segs,
                      "bandZ": "Head+10..Head+18 uu", "bandBoxInCrop": crown_box,
                      "rule": "connected components (4-neighbour) of |luma - band mean| > 12 with >= 6 px, 60 % of "
                              "the crop width",
                      "bandCovers": FALLBACK_BAND_AUDIT["K2_03"]["bandCovers"].get(variant),
                      "formalComponents": comps},
            "K2_04": {"status": "не измерено", "neckSeeThroughPx": None,
                      "note": "в packaged-кадре нет маски сегментации; репроекция ID-маски Blender не выполнялась"},
            "diagnostics": {
                "note": "не зарегистрированная метрика, без pass/fail (E3)",
                "observedHeadZone": {"bandZ": f"Head+{OBSERVED_HEAD_ZONE_Z[0]:g}..Head+{OBSERVED_HEAD_ZONE_Z[1]:g} uu "
                                              "(screen projection), middle third of the crop width",
                                     "boxInCrop": zone_box,
                                     "sobelEnergy": round(float(mag[zone].mean()), 3) if mag[zone].size else None}},
            "cropMeanRGB": [round(float(x), 2) for x in rgb.reshape(-1, 3).mean(axis=0)]})
    # K2-05 / E2: repeat noise = max pairwise mean |dRGB| of the same configuration in a fixed ROI (the crop box
    # of the first run of that configuration)
    groups: dict = {}
    for r in rows:
        if "error" in r:
            continue
        groups.setdefault((r["variant"], r["explicit"], r["zoom"]), []).append(r)
    noise = []
    for key, grp in groups.items():
        box = grp[0]["K2_01_crop"]["box"]
        arrs = [np.asarray(Image.open(REPO / g["run"] / "phase2-board-host-1920x1080.png").convert("RGB").crop(box),
                           dtype=np.float32) for g in grp]
        pairs = []
        for i in range(len(arrs)):
            for j in range(i + 1, len(arrs)):
                pairs.append(round(float(np.abs(arrs[i] - arrs[j]).mean()), 3))
        noise.append({"variant": key[0], "explicit": key[1], "zoom": key[2], "runs": [g["run"] for g in grp],
                      "roiBox": box, "pairwiseMeanAbsDeltaRGB": pairs, "maxPairwise": max(pairs) if pairs else None})
    # E2 noise from the 3-repeat control group (no variant flag), threshold = 2 x noise
    ctl = next((n for n in noise if n["explicit"] is False and len(n["runs"]) >= 3), None)
    noise_level = ctl["maxPairwise"] if ctl else None
    threshold = round(2 * noise_level, 3) if noise_level is not None else None
    for n in noise:
        n["K2_05_pass"] = (n["maxPairwise"] is not None and threshold is not None and n["maxPairwise"] <= threshold)
    comparisons = []
    overlays = []

    def mean(xs):
        xs = [x for x in xs if x is not None]
        return round(sum(xs) / len(xs), 3) if xs else None

    for z in sorted({r["zoom"] for r in rows if "error" not in r}):
        v2 = [r for r in rows if "error" not in r and r["zoom"] == z and r["variant"] == "face-neck-v2" and r["explicit"]]
        v3 = [r for r in rows if "error" not in r and r["zoom"] == z and r["variant"] == "head-tilt-v3"]
        if not v2 or not v3:
            continue
        box = v2[0]["K2_01_crop"]["box"]
        cross = []
        for a2 in v2:
            for a3 in v3:
                i2 = np.asarray(Image.open(REPO / a2["run"] / "phase2-board-host-1920x1080.png").convert("RGB").crop(box), dtype=np.float32)
                i3 = np.asarray(Image.open(REPO / a3["run"] / "phase2-board-host-1920x1080.png").convert("RGB").crop(box), dtype=np.float32)
                cross.append(round(float(np.abs(i2 - i3).mean()), 3))

        def col(rs, *path):
            return mean([_dig(r, path) for r in rs])

        comparisons.append({
            "zoom": z, "roiBox": box, "v2Runs": [r["run"] for r in v2], "v3Runs": [r["run"] for r in v3],
            "v2VsV3MeanAbsDeltaRGB": cross,
            "v2VsV3AboveNoiseThreshold": (min(cross) > threshold) if (cross and threshold) else None,
            "K2_02": {"status": BAND_STATUS_INVALID, "v3AtLeastV2": None,
                      "formal": {"v2": col(v2, "K2_02", "formalValueRegisteredBand"),
                                 "v3": col(v3, "K2_02", "formalValueRegisteredBand"),
                                 "literal": {"v2": col(v2, "K2_02", "formalValueLiteralUpperThirdHeadSpan"),
                                             "v3": col(v3, "K2_02", "formalValueLiteralUpperThirdHeadSpan")}},
                      "darkPx": {"v2": col(v2, "K2_02", "darkPixelDiagnostics", "darkPx"),
                                 "v3": col(v3, "K2_02", "darkPixelDiagnostics", "darkPx")},
                      "sobelShareNearDark": {"v2": col(v2, "K2_02", "darkPixelDiagnostics", "sobelShareNearDark"),
                                             "v3": col(v3, "K2_02", "darkPixelDiagnostics", "sobelShareNearDark")},
                      "withoutDarkNeighbourhood": {
                          "v2": col(v2, "K2_02", "darkPixelDiagnostics", "energyWithoutDarkNeighbourhood"),
                          "v3": col(v3, "K2_02", "darkPixelDiagnostics", "energyWithoutDarkNeighbourhood")},
                      "reason": FALLBACK_BAND_AUDIT["K2_02"]["reason"]},
            "K2_03": {"status": BAND_STATUS_INVALID, "v3AtLeastV2": None,
                      "formal": {"v2": col(v2, "K2_03", "formalValueRegisteredBand"),
                                 "v3": col(v3, "K2_03", "formalValueRegisteredBand")},
                      "reason": FALLBACK_BAND_AUDIT["K2_03"]["reason"]},
            "K2_04": "не измерено",
            "diagnostics": {"note": "не зарегистрированная метрика, без pass/fail (E3). В этой зоне у v2 лежит венец с "
                                    "резкими краями, у v3 — лицо: энергия градиента не отличает черты лица от края "
                                    "венца, поэтому число не подтверждает и не опровергает читаемость лица",
                            "observedHeadZoneSobelEnergy": {
                                "v2": col(v2, "diagnostics", "observedHeadZone", "sobelEnergy"),
                                "v3": col(v3, "diagnostics", "observedHeadZone", "sobelEnergy")}}})
        # Band overlay: v2 (left) and v3 (right), nearest-neighbour upscale; magenta = K2-02 band,
        # cyan = K2-03 band. A reviewer checks here whether a band lies on the face / crown.
        scale = max(1, int(round(680 / v2[0]["K2_01_crop"]["side"])))
        tiles = []
        for r in (v2[0], v3[0]):
            im = Image.open(REPO / r["run"] / "phase2-board-host-1920x1080.png").convert("RGB").crop(tuple(r["K2_01_crop"]["box"]))
            im = im.resize((im.width * scale, im.height * scale), Image.NEAREST)
            dr = ImageDraw.Draw(im)
            for bx, colr in ((r["K2_02"]["bandBoxInCrop"], (255, 0, 255)), (r["K2_03"]["bandBoxInCrop"], (0, 255, 255))):
                dr.rectangle([bx[0] * scale, bx[1] * scale, bx[2] * scale - 1, bx[3] * scale - 1], outline=colr, width=2)
            tiles.append(im)
        gap = 8
        sheet = Image.new("RGB", (tiles[0].width + gap + tiles[1].width, max(t.height for t in tiles)), (255, 255, 255))
        sheet.paste(tiles[0], (0, 0))
        sheet.paste(tiles[1], (tiles[0].width + gap, 0))
        crop_dir.mkdir(parents=True, exist_ok=True)
        ov_path = crop_dir / f"k2-bands-{_zoom_tag(z)}-v2-left-v3-right.png"
        sheet.save(ov_path)
        overlays.append({"zoom": z, "file": rel(ov_path), "sha256": sha256_file(ov_path), "scale": scale,
                         "v2Run": v2[0]["run"], "v3Run": v3[0]["run"],
                         "legend": "слева v2, справа v3; пурпурная рамка — полоса K2-02, голубая — полоса K2-03"})
    doc = {"schema": "unmatched.art004-k2-metrics/2",
           "status": "измерено: K2-01, K2-05 и разница v2<->v3 над шумом (K2-07 — artcheck в каталогах прогонов); "
                     "K2-02 и K2-03 — не измерено (невалидно): зарегистрированные полосы не попадают на лицо и "
                     "венец; K2-04 — не измерено",
           "supersedes": "unmatched.art004-k2-metrics/1 того же дня: в ней K2-02/K2-03 ошибочно записаны как "
                         "v3AtLeastV2=true (ложный PASS); формальные числа не изменились",
           "thresholds": "docs/art-pipeline/evidence/s3-baseline-2026-09-28/thresholds.json (E1_k2_live, E2_repeat_noise)",
           "noise": {"group": ctl["runs"] if ctl else None, "noiseMeanAbsDeltaRGB": noise_level,
                     "threshold2xNoise": threshold,
                     "rule": "E2: 3 repeats of one configuration, noise = max pairwise mean |dRGB| in the fixed ROI"},
           "bandAudit": FALLBACK_BAND_AUDIT, "bandOverlays": overlays,
           "proposedThresholdRevision": PROPOSED_THRESHOLD_REVISION,
           "visualObservation": "наблюдение исполнителя, не метрика и не подтверждение через K2-02/K2-03: при 5x у v3 "
                                "лицо открыто, у v2 венец закрывает глаза; у v3 по вырезу хитона тёмная V-полоса (P1). "
                                "При 1,6x черт лица не различить ни у одного варианта",
           "rows": rows, "repeatNoise": noise, "comparisons": comparisons,
           "caveat": "Metrics are computed on packaged-live frames with HUD, labels and boardState. They are "
                     "measurements, not an artistic acceptance of the face (open until T4.1/T6)."}
    write_json(Path(a.out).resolve(), doc)
    print(json.dumps([{"run": r.get("run"), "variant": r.get("variant"), "zoom": r.get("zoom"),
                       "K2_02_formal": _dig(r, ("K2_02", "formalValueRegisteredBand")),
                       "K2_03_formal": _dig(r, ("K2_03", "formalValueRegisteredBand"))} for r in rows],
                     ensure_ascii=False, indent=1))
    print(json.dumps(noise, ensure_ascii=False, indent=1))
    print(json.dumps({"noise": doc["noise"], "comparisons": comparisons, "bandOverlays": overlays},
                     ensure_ascii=False, indent=1))
    return 0


# ------------------------------------------------------------------ threshold revision rev1-t23 (stage 3, T2.3)
# thresholds.json keeps the registered E1_k2_live / perf entries untouched (E3); a revision is a new
# revisions[] record with a machine-readable "params" block that this tool reads. Everything below is
# only used with --threshold-set <revision id>; the registered path above is the T1.1 behaviour.
THRESHOLDS_JSON = REPO / "docs" / "art-pipeline" / "evidence" / "s3-baseline-2026-09-28" / "thresholds.json"
THRESHOLD_SET_REGISTERED = "registered"
THRESHOLD_SET_REV1 = "rev1-t23"
# S08FlowGameMode::SetupCameraForBoard / UpdateBoardCamera: horizontal FOV 35, rotation (-55, -90, 0)
UE_BOARD_HFOV_DEG = 35.0
UE_BOARD_ROT = (-55.0, -90.0, 0.0)
# Camera model tolerance: SHOT ctx cam is printed with %.0f (1 uu), SHOT head screen/top/bottom with %.1f,
# SHOT fighter screen with %.0f.
CAM_SHIFT_TOL_UU = 0.87      # |rounding of a 1-uu grid point| <= sqrt(3)/2
CAM_RESIDUAL_TOL_PX = 0.15
CAM_FIGHTER_TOL_PX = 0.6     # SHOT fighter screen is printed with %.0f
SOCKET_TOL_UU = 0.15
ID_CLASSES = (("features", (255, 0, 0)), ("throat", (255, 0, 255)), ("neck_back", (255, 255, 0)),
              ("crown", (0, 255, 0)), ("collar", (0, 255, 255)), ("quiver", (255, 255, 255)),
              ("bow", (0, 0, 255)), ("body", (0, 0, 0)))
CLASS_ID = {name: i + 1 for i, (name, _c) in enumerate(ID_CLASSES)}
GAP_ID = len(ID_CLASSES) + 1  # transparent, enclosed, inside the face x collar junction zone (see-through)
FIGURE_IDS = tuple(range(1, len(ID_CLASSES) + 1))
REV_PENDING = "ожидает проверки размещения (не засчитано)"
REV_MEASURED = "измерено по ревизии (ретроспективно; E3 — не гейт T1.1)"
REV_SMALL = "не измерено (маска меньше минимума)"
REV_PLACEMENT_FAILED = "не измерено (размещение маски не подтверждено проверкой)"


def load_threshold_set(name: str, path: Path | None = None) -> dict:
    """The registered entries, or the revisions[] record with this id (must carry "params")."""
    doc = json.loads(Path(path or THRESHOLDS_JSON).read_text(encoding="utf-8"))
    if name == THRESHOLD_SET_REGISTERED:
        return {"id": name, "E1_k2_live": doc["E1_k2_live"], "perf": doc["perf"]}
    for rev in doc.get("revisions", []):
        if rev.get("id") == name:
            if not isinstance(rev.get("params"), dict):
                raise ValueError(f"revision {name!r} in {path or THRESHOLDS_JSON} has no machine-readable params")
            return rev
    raise KeyError(f"threshold set {name!r} is not in revisions[] of {path or THRESHOLDS_JSON}")


def _vec(s: str) -> list[float]:
    return [float(x) for x in str(s).strip("()").split(",")]


SHOT_KV = re.compile(r"(\w+)=(\([^)]*\)|[^\s]+)")


def parse_shot(text: str) -> dict:
    """SHOT ctx / camera / head / fighter lines of one client trace (T1.1 format) and the host selection."""
    out = {"ctx": None, "camera": None, "heads": [], "fighters": {}, "requested": [], "selected": None}
    for ln in text.splitlines():
        if "SHOT ctx " in ln:
            out["ctx"] = dict(SHOT_KV.findall(ln.split("SHOT ctx", 1)[1]))
        elif "SHOT camera " in ln:
            out["camera"] = dict(SHOT_KV.findall(ln.split("SHOT camera", 1)[1]))
        elif "SHOT head fighter=" in ln:
            out["heads"].append(dict(SHOT_KV.findall(ln.split("SHOT head", 1)[1])))
        elif "SHOT fighter " in ln:
            m = re.search(r"SHOT fighter (\S+) (.*)$", ln)
            if m:
                out["fighters"][m.group(1)] = dict(SHOT_KV.findall(m.group(2)))
        elif "SHOT requested" in ln:
            out["requested"].append(ln.rsplit("-> ", 1)[-1].strip())
        m = re.search(r"ARTPREVIEW selection ownHero=1 selected=1 .* fighterId=(\S+)", ln)
        if m:
            out["selected"] = m.group(1)
    return out


class PinholeCamera:
    """UE-convention pinhole camera (world uu, left-handed, Z up). Horizontal FOV defines the focal length
    for both axes (square pixels), principal point at the viewport centre, image y grows downward -- the
    PlayerController::ProjectWorldLocationToScreen convention of the SHOT trace lines."""

    def __init__(self, loc, pitch_deg: float, yaw_deg: float, hfov_deg: float, width: int, height: int):
        import numpy as np
        p, y = math.radians(pitch_deg), math.radians(yaw_deg)
        self.C = np.asarray(loc, dtype=float)
        self.F = np.array([math.cos(p) * math.cos(y), math.cos(p) * math.sin(y), math.sin(p)])
        self.R = np.array([-math.sin(y), math.cos(y), 0.0])
        self.U = np.cross(self.F, self.R)
        self.pitch, self.yaw, self.hfov = pitch_deg, yaw_deg, hfov_deg
        self.w, self.h = int(width), int(height)
        self.cx, self.cy = self.w / 2.0, self.h / 2.0
        self.f = self.cx / math.tan(math.radians(hfov_deg) / 2.0)

    @classmethod
    def look_at(cls, loc, target, hfov_deg: float, width: int, height: int) -> "PinholeCamera":
        d = [t - s for s, t in zip(loc, target)]
        yaw = math.degrees(math.atan2(d[1], d[0]))
        pitch = math.degrees(math.atan2(d[2], math.hypot(d[0], d[1])))
        return cls(loc, pitch, yaw, hfov_deg, width, height)

    def project(self, P):
        import numpy as np
        v = np.asarray(P, dtype=float) - self.C
        d = v @ self.F
        return self.cx + self.f * (v @ self.R) / d, self.cy - self.f * (v @ self.U) / d, d

    def depth(self, P) -> float:
        import numpy as np
        return float((np.asarray(P, dtype=float) - self.C) @ self.F)

    def rays(self, x, y):
        """Un-normalised ray directions through image points (x, y); D . F == 1."""
        import numpy as np
        x = np.asarray(x, dtype=float)
        y = np.asarray(y, dtype=float)
        return self.F + ((x - self.cx) / self.f)[..., None] * self.R - ((y - self.cy) / self.f)[..., None] * self.U

    def ray_plane_points(self, x, y, point, normal):
        """World points where the rays through image points (x, y) meet the plane (point, normal)."""
        import numpy as np
        D = self.rays(x, y)
        n = np.asarray(normal, dtype=float)
        t = float((np.asarray(point, dtype=float) - self.C) @ n) / (D @ n)
        return self.C + t[..., None] * D

    def describe(self) -> dict:
        return {"location": [round(float(v), 3) for v in self.C], "pitch": round(self.pitch, 4),
                "yaw": round(self.yaw, 4), "hfovDeg": self.hfov, "viewport": [self.w, self.h],
                "focalPx": round(self.f, 3)}


def ue_camera_from_trace(shot: dict, head: dict, hfov_deg: float = UE_BOARD_HFOV_DEG) -> tuple:
    """Board camera of one frame: orientation and FOV from the S08 code; position from SHOT ctx cam (printed
    at 1 uu), refined against the trace: the offset along the view axis minimises the error of the traced
    fighter projections (SHOT fighter screen, printed at 1 px, far from the centre -> long lever), and for
    every such offset the image-plane shift puts the traced Head socket exactly on SHOT head screen.
    top/bottom (Head -+ 6 uu, printed at 0.1 px) and the fighters are the check."""
    import numpy as np
    ctx = shot["ctx"]
    w, h = (int(v) for v in ctx["viewport"].split("x"))
    rot = _vec(ctx["rot"])
    if [round(v) for v in rot] != [round(v) for v in UE_BOARD_ROT]:
        raise ValueError(f"SHOT ctx rot={ctx['rot']} is not the board camera rotation {UE_BOARD_ROT}")
    base = PinholeCamera(_vec(ctx["cam"]), UE_BOARD_ROT[0], UE_BOARD_ROT[1], hfov_deg, w, h)
    wh = np.array(_vec(head["world"]))
    xs, ys = _vec(head["screen"])
    marks = [(np.array(_vec(f["world"])), np.array(_vec(f["screen"]))) for f in shot["fighters"].values()
             if f.get("projected") == "1" and "world" in f and "screen" in f]

    def at(axial: float):
        c0 = base.C + axial * base.F
        v = wh - c0
        a_, b_, d_ = v @ base.R, v @ base.U, v @ base.F
        da = a_ - (xs - base.cx) * d_ / base.f
        db = b_ + (ys - base.cy) * d_ / base.f
        return PinholeCamera(c0 + da * base.R + db * base.U, UE_BOARD_ROT[0], UE_BOARD_ROT[1], hfov_deg, w, h), da, db

    def cost(cam):
        tot = 0.0
        for key, dz in (("top", 6.0), ("bottom", -6.0)):
            px, py, _ = cam.project(wh + np.array([0.0, 0.0, dz]))
            ox, oy = _vec(head[key])
            tot += ((px - ox) ** 2 + (py - oy) ** 2) / 0.029 ** 2   # %.1f rounding: sigma ~ 0.1/sqrt(12)
        for world, screen in marks:
            px, py, _ = cam.project(world)
            tot += ((px - screen[0]) ** 2 + (py - screen[1]) ** 2) / 0.29 ** 2  # %.0f rounding
        return tot

    axial = min(np.arange(-1.5, 1.5 + 1e-9, 0.01), key=lambda d: cost(at(float(d))[0]))
    fitted, da, db = at(float(axial))
    res = []
    for key, dz in (("screen", 0.0), ("top", 6.0), ("bottom", -6.0)):
        px, py, _ = fitted.project(wh + np.array([0.0, 0.0, dz]))
        ox, oy = _vec(head[key])
        res.append(max(abs(px - ox), abs(py - oy)))
    fres = [max(abs(px - sc[0]), abs(py - sc[1])) for (px, py, _), sc in ((fitted.project(wd), sc) for wd, sc in marks)]
    shift = math.sqrt(float(axial) ** 2 + float(da) ** 2 + float(db) ** 2)
    check = {"ctxCam": _vec(ctx["cam"]),
             "shiftUu": {"axial": round(float(axial), 3), "right": round(float(da), 3), "up": round(float(db), 3),
                         "norm": round(shift, 3)},
             "residualPx": {"screen": round(res[0], 3), "top": round(res[1], 3), "bottom": round(res[2], 3)},
             "fighterResidualPxMax": round(max(fres), 3) if fres else None, "fighters": len(marks),
             "tolerance": {"shiftNormUu": CAM_SHIFT_TOL_UU, "residualPx": CAM_RESIDUAL_TOL_PX,
                           "fighterResidualPx": CAM_FIGHTER_TOL_PX}}
    check["ok"] = bool(shift <= CAM_SHIFT_TOL_UU and max(res) <= CAM_RESIDUAL_TOL_PX
                       and (not fres or max(fres) <= CAM_FIGHTER_TOL_PX))
    return fitted, check


def fighter_dir_to_world(local, yaw_deg: float):
    import numpy as np
    c, s = math.cos(math.radians(yaw_deg)), math.sin(math.radians(yaw_deg))
    x, y, z = (float(v) for v in local)
    return np.array([x * c - y * s, x * s + y * c, z])


def fighter_to_world(local_uu, fighter_world, yaw_deg: float):
    import numpy as np
    return np.asarray(fighter_world, dtype=float) + fighter_dir_to_world(local_uu, yaw_deg)


def blender_m_to_ue_local(p_m):
    """Blender metres (face -Y) -> UE component uu (face +Y): the FBX import flips Y, scale 100."""
    return (100.0 * p_m[0], -100.0 * p_m[1], 100.0 * p_m[2])


def blender_camera_in_world(view: dict, fighter_world, yaw_deg: float) -> PinholeCamera:
    res = view["resolution"]
    return PinholeCamera.look_at(fighter_to_world(blender_m_to_ue_local(view["cameraM"]), fighter_world, yaw_deg),
                                 fighter_to_world(blender_m_to_ue_local(view["targetM"]), fighter_world, yaw_deg),
                                 view["hfovDeg"], res[0], res[1])


def rgba_pixels_sha256(arr) -> str:
    """sha256 of the (H, W, 4) uint8 array, row 0 = top: the pixels_sha256 of blender-measurements.json."""
    import numpy as np
    return hashlib.sha256(np.ascontiguousarray(arr).tobytes()).hexdigest()


def junction_gap_mask(idcull, band: int):
    """Enclosed transparent pixels in the face x collar zone of a part-ID render: the mask behind
    face_x_collar.enclosed_gap_px of tools/art/art004_junction_zones.enclosed_gap (same functions)."""
    import numpy as np
    import art004_junction_zones as jz
    a = idcull[..., 3] > 127
    rgb = idcull[..., :3].astype(int)
    face = a & jz.cls(rgb, jz.PAL["face"])
    collar = a & jz.cls(rgb, jz.PAL["collar"])
    zone = jz.dilate(face, band) & jz.dilate(collar, band)
    lab, _n = jz.label(~a)
    border = set(np.unique(np.concatenate([lab[0], lab[-1], lab[:, 0], lab[:, -1]]))) - {0}
    enclosed = ~a & ~np.isin(lab, list(border))
    return zone & enclosed


def id_label_image(idsplit, idcull, band: int):
    """uint8 label image: 0 background, CLASS_ID[...] for figure classes (idsplit colours), GAP_ID for the
    see-through junction pixels (from the unsplit id-cull render)."""
    import numpy as np
    a = idsplit[..., 3] > 127
    if not np.array_equal(a, idcull[..., 3] > 127):
        raise ValueError("idsplit and id-cull renders have different alpha (not the same camera/geometry)")
    rgb = idsplit[..., :3].astype(int)
    lab = np.zeros(a.shape, dtype=np.uint8)
    for name, colour in ID_CLASSES:
        lab[a & (np.abs(rgb - np.array(colour)).sum(axis=2) < 30)] = CLASS_ID[name]
    unknown = int((a & (lab == 0)).sum())
    if unknown:
        raise ValueError(f"{unknown} figure pixels with a colour outside the ID palette")
    red_cull = a & (np.abs(idcull[..., :3].astype(int) - np.array((255, 0, 0))).sum(axis=2) < 30)
    if not np.array_equal(red_cull, (lab == CLASS_ID["features"]) | (lab == CLASS_ID["throat"])):
        raise ValueError("face part of id-cull != features + throat of idsplit")
    gap = junction_gap_mask(idcull, band)
    lab[gap] = GAP_ID
    return lab


def full_depth(depth_uu, origin_xy, shape):
    """(raw, filled) full-render depth maps (uu along the Blender camera axis). raw: NaN where the render has
    no front-facing hit (background, see-through gaps, outside the stored bbox). filled: those pixels take the
    depth of the nearest hit pixel, so live samples next to the figure are lifted to the adjacent surface."""
    import numpy as np
    from scipy import ndimage
    raw = np.full(shape, np.nan, dtype=np.float32)
    x0, y0 = (int(v) for v in origin_xy)
    raw[y0:y0 + depth_uu.shape[0], x0:x0 + depth_uu.shape[1]] = depth_uu
    idx = ndimage.distance_transform_edt(np.isnan(raw), return_distances=False, return_indices=True)
    return raw, raw[tuple(idx)]


def load_mask_source(mesh: str, params: dict, cache: dict | None = None) -> dict:
    """Per-variant Blender ID masks for the traced mesh, with provenance checks. Returns a dict with "ok"; a
    mask is used only when the FBX of the render equals the FBX of the UE import of that mesh."""
    import numpy as np
    from PIL import Image
    if cache is not None and mesh in cache:
        return cache[mesh]
    ms = params["maskSources"]
    entry = ms["meshes"].get(mesh)
    out = {"mesh": mesh, "ok": False, "problems": []}
    if entry is None:
        out["problems"].append(f"нет ID-маски для сетки {mesh}")
        if cache is not None:
            cache[mesh] = out
        return out
    tag = entry["tag"]
    base = REPO / ms["dir"]
    meas = json.loads((base / ms["measurements"]).read_text(encoding="utf-8"))
    views = (meas.get("part_id_views") or {}).get(tag) or {}
    files = {"idsplit": base / ms["idsplitPattern"].format(tag=tag), "idcull": base / ms["idcullPattern"].format(tag=tag)}
    arrays, recs = {}, {}
    for kind, p in files.items():
        if not p.is_file():
            out["problems"].append(f"нет файла {rel(p)}")
            continue
        arr = np.array(Image.open(p).convert("RGBA"))
        arrays[kind] = arr
        want = (views.get(ms["idsplitView"]) if kind == "idsplit" else views.get(ms["idcullView"])) or {}
        got = rgba_pixels_sha256(arr)
        recs[kind] = {"file": rel(p), "sha256": sha256_file(p), "pixelsSha256": got,
                      "pixelsSha256Recorded": want.get("pixels_sha256"), "pixelsMatch": got == want.get("pixels_sha256")}
        if not recs[kind]["pixelsMatch"]:
            out["problems"].append(f"pixels_sha256 {rel(p)} не совпадает с {ms['measurements']}")
    fbx_sha = (meas.get("inputs_sha256") or {}).get(tag)
    imp = entry.get("importReport")
    out.update({"tag": tag, "variant": entry.get("variant"), "files": recs, "fbxSha256": fbx_sha,
                "importReport": imp, "headSocketLocalUu": entry.get("headSocketLocalUu") or params["headSocketLocalUu"]})
    if not imp:
        out["problems"].append("нет отчёта импорта UE с тем же sha256 FBX (для v3.1 — после T4.1)")
    else:
        rep = json.loads((REPO / imp).read_text(encoding="utf-8"))
        out["importFbxSha256"] = rep.get("source_fbx_sha256")
        if rep.get("source_fbx_sha256") != fbx_sha:
            out["problems"].append("sha256 FBX ID-рендера не совпадает с source_fbx_sha256 отчёта импорта")
        if not str(rep.get("skeletal_mesh", "")).endswith("." + mesh):
            out["problems"].append(f"отчёт импорта {imp} не про сетку {mesh}")
    depth = None
    dcfg = ms.get("depth")
    if dcfg:
        dbase = REPO / dcfg["dir"]
        dpath = dbase / dcfg["pattern"].format(tag=tag)
        drep = json.loads((dbase / dcfg["report"]).read_text(encoding="utf-8"))
        dv = (drep.get("variants") or {}).get(tag) or {}
        if not dpath.is_file():
            out["problems"].append(f"нет карты глубины {rel(dpath)}")
        else:
            with np.load(dpath) as z:
                d_uu, d_org = z["depth_uu"], z["origin_xy"]
            got = rgba_pixels_sha256(d_uu)
            out["depth"] = {"file": rel(dpath), "sha256": sha256_file(dpath), "depthSha256": got,
                            "report": rel(dbase / dcfg["report"]), "alphaAgreement": dv.get("alphaAgreement"),
                            "alphaWithoutHitPx": dv.get("alphaWithoutHitPx"), "hitWithoutAlphaPx": dv.get("hitWithoutAlphaPx")}
            if got != dv.get("depthSha256"):
                out["problems"].append("depthSha256 карты глубины не совпадает с depth-report.json")
            if dv.get("fbxSha256") != fbx_sha or dv.get("idsplitPixelsSha256") != (recs.get("idsplit") or {}).get("pixelsSha256"):
                out["problems"].append("карта глубины снята не с того FBX или не для того ID-рендера")
            if (dv.get("alphaAgreement") or 0.0) < float(dcfg["minAlphaAgreement"]):
                out["problems"].append("карта глубины не согласуется с альфой ID-рендера")
            depth = (d_uu, d_org)
    if len(arrays) == 2 and not out["problems"]:
        band = int(params["masks"]["gapZoneBandPx"])
        lab = id_label_image(arrays["idsplit"], arrays["idcull"], band)
        out["label"] = lab
        out["gapPxAtRender"] = int((lab == GAP_ID).sum())
        want_gap = ((views.get(ms["idcullView"]) or {}).get("face_x_collar") or {}).get("enclosed_gap_px")
        out["gapPxRecorded"] = want_gap
        if want_gap is not None and want_gap != out["gapPxAtRender"]:
            out["problems"].append(f"маска просвета {out['gapPxAtRender']} px != face_x_collar.enclosed_gap_px {want_gap}")
            out.pop("label")
        out["classPxAtRender"] = {name: int((lab == cid).sum()) for name, cid in CLASS_ID.items()}
        if depth is not None and "label" in out:
            out["depthFull"] = full_depth(depth[0], depth[1], lab.shape)
    out["ok"] = "label" in out and not out["problems"] and (not dcfg or "depthFull" in out)
    if cache is not None:
        cache[mesh] = out
    return out


def live_to_blender(ue_cam: PinholeCamera, bl_cam: PinholeCamera, plane: tuple, X, Y, depth=None,
                    iterations: int = 8, march_steps: int = 96, stats: dict | None = None):
    """Blender-render coordinates (continuous px, row 0 = top) of the surface seen through live image points
    (X, Y). First guess: the ray meets `plane` (point, normal) -- the figure's vertical plane. With `depth` =
    (raw, filled) full-render depth along the Blender camera axis (uu) each point is moved along its live ray
    to the depth of the Blender pixel it lands on (fixed-point iteration on the filled map); points that do
    not settle (steep depth, silhouette jumps) are resolved by marching along the live ray to the first point
    at or behind the rendered surface (raw map), or, without a crossing (the ray passes the surface:
    background or see-through), to the ray point closest in depth to the neighbouring rendered surface."""
    import numpy as np
    P = ue_cam.ray_plane_points(X, Y, *plane)
    xb, yb, db = bl_cam.project(P)
    if depth is None:
        return xb, yb, db
    raw, filled = depth
    H, W = raw.shape
    D = ue_cam.rays(X, Y)
    dF = D @ bl_cam.F
    c0 = float((ue_cam.C - bl_cam.C) @ bl_cam.F)
    step = np.zeros(np.shape(xb))
    for _ in range(iterations):
        ib = np.clip(np.floor(xb).astype(np.int64), 0, W - 1)
        jb = np.clip(np.floor(yb).astype(np.int64), 0, H - 1)
        t = (filled[jb, ib] - c0) / dF
        nx, ny, db = bl_cam.project(ue_cam.C + t[..., None] * D)
        step = np.maximum(np.abs(nx - xb), np.abs(ny - yb))
        xb, yb = nx, ny
    bad = step > 0.25
    found = 0
    if bad.any():
        zlo, zhi = float(np.nanmin(raw)) - 2.0, float(np.nanmax(raw)) + 2.0
        Db, dFb = D[bad], dF[bad]
        fx, fy = xb[bad].copy(), yb[bad].copy()
        hit = np.zeros(fx.shape, dtype=bool)
        best = np.full(fx.shape, np.inf)
        cx_, cy_ = fx.copy(), fy.copy()
        for z in np.linspace(zlo, zhi, march_steps):
            px, py, _ = bl_cam.project(ue_cam.C + ((z - c0) / dFb)[..., None] * Db)
            ib = np.clip(np.floor(px).astype(np.int64), 0, W - 1)
            jb = np.clip(np.floor(py).astype(np.int64), 0, H - 1)
            zm = raw[jb, ib]
            now = ~hit & ~np.isnan(zm) & (z >= zm)
            fx[now], fy[now] = px[now], py[now]
            hit |= now
            gap_ = np.abs(z - filled[jb, ib])  # closest approach to the rendered surface depth
            closer = gap_ < best
            best[closer], cx_[closer], cy_[closer] = gap_[closer], px[closer], py[closer]
        fx[~hit], fy[~hit] = cx_[~hit], cy_[~hit]
        xb[bad], yb[bad] = fx, fy
        found = int(hit.sum())
    if stats is not None:
        stats.update({"fixedPointIterations": iterations, "samples": int(step.size),
                      "notSettledSamples": int(bad.sum()), "resolvedByMarching": found, "marchSteps": march_steps,
                      "note": "не сошедшиеся за итерации отсчёты (скачки глубины у края силуэта и стыка) решены "
                              "проходом по лучу кадра до первой точки на/за поверхностью рендера; без пересечения "
                              "луч проходит мимо поверхности (фон или просвет) — берётся точка луча, ближайшая по "
                              "глубине к соседней поверхности рендера"})
    return xb, yb, db


def reproject_labels(ue_cam: PinholeCamera, bl_cam: PinholeCamera, plane: tuple, label, box, k: int,
                     depth=None, iterations: int = 8, stats: dict | None = None, march_steps: int = 96):
    """Coverage (0..1) of every label value for each pixel of `box` in the live frame: k x k sub-pixel
    samples per live pixel, mapped by live_to_blender(), nearest Blender pixel of the label image.
    Returns {label value: float32 (h, w)}."""
    import numpy as np
    x0, y0, x1, y1 = box
    w, h = x1 - x0, y1 - y0
    offs = (np.arange(k) + 0.5) / k
    xs = (x0 + np.repeat(np.arange(w), k) + np.tile(offs, w))
    ys = (y0 + np.repeat(np.arange(h), k) + np.tile(offs, h))
    X, Y = np.meshgrid(xs, ys)
    xb, yb, db = live_to_blender(ue_cam, bl_cam, plane, X, Y, depth, iterations, march_steps, stats)
    H, W = label.shape
    ib, jb = np.floor(xb).astype(np.int64), np.floor(yb).astype(np.int64)
    valid = (db > 0) & (ib >= 0) & (jb >= 0) & (ib < W) & (jb < H)
    lab = np.zeros(X.shape, dtype=np.uint8)
    lab[valid] = label[jb[valid], ib[valid]]
    cov = {}
    for v in range(0, GAP_ID + 1):
        m = (lab == v).reshape(h, k, w, k)
        cov[v] = m.mean(axis=(1, 3), dtype=np.float32)
    return cov


def plane_mapping_error(ue_cam: PinholeCamera, bl_cam: PinholeCamera, plane: tuple, points) -> float:
    """Max error (live px) of the plane reprojection for 3D points off the plane (depth spread of the head):
    the Blender-image distance between the true projection and the plane-lifted one, divided by the Blender
    px per live px at the plane point."""
    import numpy as np
    blender_px_per_live_px = ue_cam.depth(plane[0]) / bl_cam.depth(plane[0])
    worst = 0.0
    for p in points:
        xu, yu, _ = ue_cam.project(p)
        q = ue_cam.ray_plane_points(np.array([xu]), np.array([yu]), *plane)[0]
        xb1, yb1, _ = bl_cam.project(q)
        xb2, yb2, _ = bl_cam.project(p)
        worst = max(worst, math.hypot(float(xb1 - xb2), float(yb1 - yb2)) / blender_px_per_live_px)
    return worst


def silhouette_registration(alpha, mag, max_shift: int = 3) -> dict:
    """Automatic placement aid: mean live edge strength on the reprojected silhouette contour for integer
    shifts; the best shift must stay within +-1 px. Not a replacement for the overlay review."""
    import numpy as np
    from scipy import ndimage
    if not alpha.any():
        return {"ok": None, "note": "в кропе нет силуэта"}
    edge = (alpha & ~ndimage.binary_erosion(alpha)) | (ndimage.binary_dilation(alpha) & ~alpha)
    ys, xs = np.nonzero(edge)
    h, w = mag.shape
    scores = {}
    for dy in range(-max_shift, max_shift + 1):
        for dx in range(-max_shift, max_shift + 1):
            yy, xx = ys + dy, xs + dx
            keep = (yy >= 0) & (xx >= 0) & (yy < h) & (xx < w)
            scores[(dx, dy)] = float(mag[yy[keep], xx[keep]].mean()) if keep.any() else 0.0
    best = max(scores, key=lambda s: (scores[s], -abs(s[0]) - abs(s[1])))
    return {"contourPx": int(edge.sum()), "scoreAtZero": round(scores[(0, 0)], 3), "bestShift": list(best),
            "bestScore": round(scores[best], 3), "window": max_shift,
            "ok": bool(abs(best[0]) <= 1 and abs(best[1]) <= 1)}


def _k2_masks(cov: dict, cfg: dict):
    from scipy import ndimage
    thr = float(cfg["coverageMin"])
    alpha = sum(cov[i] for i in FIGURE_IDS) >= thr
    face = cov[CLASS_ID["features"]] >= thr
    crown = cov[CLASS_ID["crown"]] >= thr
    gap = cov[GAP_ID] >= thr
    it = int(cfg["erodePx"])
    erode = (lambda m: ndimage.binary_erosion(m, iterations=it)) if it > 0 else (lambda m: m)
    return {"alpha": alpha, "face": face, "crown": crown, "gap": gap, "gapCov": cov[GAP_ID],
            "faceMeasured": erode(face), "crownMeasured": erode(crown), "gapArea": float(cov[GAP_ID].sum()),
            "faceCoverageSum": float(cov[CLASS_ID["features"]].sum()),
            "crownCoverageSum": float(cov[CLASS_ID["crown"]].sum())}


def k2_revision_values(L, mag, masks: dict, cfg: dict) -> dict:
    """K2-02..K2-04 of one frame on the reprojected masks (thresholds.json revision params["masks"])."""
    import numpy as np
    from scipy import ndimage
    min_px = int(cfg["minMaskPx"])
    out = {}
    fm = masks["faceMeasured"]
    k202 = {"maskPx": int(masks["face"].sum()), "measuredPx": int(fm.sum()),
            "coverageSum": round(masks["faceCoverageSum"], 2)}
    if fm.sum() >= min_px:
        k202["value"] = round(float(mag[fm].mean()), 3)
        dark = (L < DARK_LUMA) & fm
        near = ndimage.binary_dilation(dark, iterations=DARK_DILATE) if dark.any() else dark
        k202["darkPixelDiagnostics"] = {
            "lumaBelow": DARK_LUMA, "dilateIterations": DARK_DILATE, "darkPx": int(dark.sum()),
            "energyWithoutDarkNeighbourhood": round(float(mag[fm & ~near].mean()), 3) if (fm & ~near).any() else None,
            "note": "диагностика (предложение T1.1), не зарегистрированная метрика"}
    else:
        k202["value"] = None
        k202["status"] = REV_SMALL
    out["K2_02"] = k202
    cm = masks["crownMeasured"]
    k203 = {"maskPx": int(masks["crown"].sum()), "measuredPx": int(cm.sum()),
            "coverageSum": round(masks["crownCoverageSum"], 2)}
    if cm.sum() >= min_px:
        thr = float(L[cm].mean())
        lab, n = ndimage.label(cm & (np.abs(L - thr) > float(cfg["contrastLuma"])))
        sizes = np.bincount(lab.ravel())[1:] if n else np.array([], dtype=int)
        keep = sorted((int(s) for s in sizes if s >= int(cfg["minComponentPx"])), reverse=True)
        k203.update({"value": len(keep), "maskMeanLuma": round(thr, 2), "componentPx": keep[:12]})
    else:
        k203["value"] = None
        k203["status"] = REV_SMALL
    out["K2_03"] = k203
    gm = masks["gap"]
    k204 = {"value": round(masks["gapArea"], 2), "unit": "px кадра (сумма покрытия)",
            "pxCoverageAtLeastHalf": int(gm.sum())}
    if gm.any():
        ring = ndimage.binary_dilation(gm, iterations=3) & ~gm & masks["alpha"]
        k204["liveDiagnostics"] = {
            "meanLumaUnderMask": round(float(L[gm].mean()), 2),
            "shareLumaBelow25": round(float((L[gm] < DARK_LUMA).mean()), 3),
            "meanLumaFigureRing3px": round(float(L[ring].mean()), 2) if ring.any() else None,
            "note": "диагностика: яркость живых пикселей под маской просвета и в кольце фигуры вокруг неё; "
                    "не метрика и не pass/fail"}
    out["K2_04"] = k204
    return out


def _outline(mask):
    from scipy import ndimage
    return mask & ~ndimage.binary_erosion(mask)


def write_revision_overlay(path: Path, tiles: list, target_px: int = 680) -> dict:
    """2 x 2 sheet: top raw crop, bottom masks (magenta outline = face features, cyan outline = crown,
    yellow = see-through at the junction, opacity 0.4 + 0.6 x coverage so that sub-pixel gaps stay visible);
    columns in `tiles` order."""
    import numpy as np
    from PIL import Image
    side = tiles[0]["crop"].shape[0]
    scale = max(1, int(round(target_px / side)))
    cells = []
    for t in tiles:
        raw = np.repeat(np.repeat(t["crop"], scale, axis=0), scale, axis=1)
        m = t["masks"]
        cov = np.clip(m["gapCov"], 0.0, 1.0)
        a = np.where(cov > 0, 0.4 + 0.6 * cov, 0.0)[..., None]  # visible even where the gap is sub-pixel
        marked = np.round(t["crop"] * (1.0 - a) + np.array((255.0, 255.0, 0.0)) * a).astype(np.uint8)
        marked[_outline(m["crown"])] = (0, 255, 255)
        marked[_outline(m["face"])] = (255, 0, 255)
        marked = np.repeat(np.repeat(marked, scale, axis=0), scale, axis=1)
        cells.append((raw, marked))
    gap = 8
    H = 2 * cells[0][0].shape[0] + gap
    W = len(cells) * cells[0][0].shape[1] + (len(cells) - 1) * gap
    sheet = np.full((H, W, 3), 255, dtype=np.uint8)
    for i, (raw, marked) in enumerate(cells):
        x = i * (raw.shape[1] + gap)
        sheet[:raw.shape[0], x:x + raw.shape[1]] = raw
        sheet[raw.shape[0] + gap:, x:x + raw.shape[1]] = marked
    path.parent.mkdir(parents=True, exist_ok=True)
    Image.fromarray(sheet).save(path)
    return {"file": rel(path), "sha256": sha256_file(path), "scale": scale}


def load_placement_review(path: str | None) -> dict:
    if not path:
        return {}
    doc = json.loads(Path(path).read_text(encoding="utf-8"))
    out = {"file": rel(Path(path)), "sha256": sha256_file(Path(path)), "reviewer": doc.get("reviewer"),
           "entries": {}}
    for e in doc.get("reviews", []):
        out["entries"][e["overlay"]] = e
    return out


def placement_verdict(review: dict, overlay: dict, key: str, variants=("face-neck-v2", "head-tilt-v3")) -> tuple:
    """(counted?, reason). A review counts only for the exact overlay bytes (sha256)."""
    e = (review.get("entries") or {}).get(overlay["file"])
    if not e:
        return False, REV_PENDING
    if e.get("sha256") != overlay["sha256"]:
        return False, REV_PENDING + ": sha256 оверлея не совпадает с проверенным"
    flags = e.get(key) or {}
    if all(flags.get(v) is True for v in variants):
        return True, "размещение подтверждено проверкой оверлея"
    return False, REV_PLACEMENT_FAILED


def revision_frame(rd: Path, role: str, rev: dict, cache: dict) -> dict:
    """Reprojected-mask K2 values of one packaged-live frame (host or joiner)."""
    import numpy as np
    from PIL import Image
    from scipy import ndimage
    p = rev["params"]
    png = rd / f"phase2-board-{role}-1920x1080.png"
    trace = rd / f"phase2-client-{role}.trace.log"
    row = {"run": rel(rd), "role": role, "frame": rel(png)}
    if not png.is_file() or not trace.is_file():
        row["error"] = "нет кадра или трассы клиента"
        return row
    row["frameSha256"] = sha256_file(png)
    status = json.loads((rd / "art-preview-status.json").read_text(encoding="utf-8-sig"))
    row.update({"variant": status.get("medusaVariant"), "explicit": status.get("medusaVariantExplicit")})
    shot = parse_shot(trace.read_text(encoding="utf-8-sig", errors="replace"))
    if len(shot["requested"]) != 1 or not shot["requested"][0].replace("\\", "/").endswith("/" + png.name):
        row["error"] = f"в трассе не ровно один SHOT requested для {png.name}: {shot['requested']}"
        return row
    known = p["maskSources"]["meshes"]
    if role == "host":
        head = next((h for h in shot["heads"] if h.get("fighter") == shot["selected"]), None)
    else:
        cands = [h for h in shot["heads"] if h.get("mesh") in known]
        head = cands[0] if len(cands) == 1 else None
    if head is None or not shot["ctx"] or not shot["camera"]:
        row["error"] = "нет SHOT ctx/camera/head для фигуры Medusa"
        return row
    fid = head["fighter"]
    zoom = float(shot["camera"]["zoom"])
    row.update({"fighter": fid, "mesh": head.get("mesh"), "zoom": zoom, "zoomTag": _zoom_tag(zoom),
                "cameraTrace": shot["camera"], "headTrace": head})
    fw = shot["fighters"].get(fid)
    if not fw:
        row["error"] = f"нет SHOT fighter {fid}"
        return row
    W = np.array(_vec(fw["world"]))
    yaw = 0.0 if W[1] < 0 else 180.0  # S08FighterActor: the 5x6 board's negative-Y side faces +Y
    row["fighterWorld"], row["fighterYaw"] = W.tolist(), yaw
    if yaw != 0.0:
        row["error"] = "фигура с yaw 180 видна сзади: маски ревизии есть только для фронтального K2 (k2-front-d300)"
        return row
    try:
        ue_cam, cam_check = ue_camera_from_trace(shot, head)
    except ValueError as e:
        row["error"] = str(e)
        return row
    row["camera"] = {"model": ue_cam.describe(), "check": cam_check}
    src = load_mask_source(head["mesh"], p, cache)
    row["maskSource"] = {k: src.get(k) for k in ("tag", "variant", "ok", "problems", "fbxSha256", "importReport")}
    sock = fighter_to_world(src.get("headSocketLocalUu") or p["headSocketLocalUu"], W, yaw)
    wh = np.array(_vec(head["world"]))
    row["socketCheck"] = {"expectedWorld": [round(float(v), 3) for v in sock], "tracedWorld": wh.tolist(),
                          "errUu": round(float(np.abs(sock - wh).max()), 3), "tolUu": SOCKET_TOL_UU}
    row["socketCheck"]["ok"] = row["socketCheck"]["errUu"] <= SOCKET_TOL_UU
    # K2-01 by the revision: centre proj(Head + cropCenterDz), side factor x |proj(Head + segmentDz) - proj(Head)|
    cp = p["crop"]
    ref = wh + np.array([0.0, 0.0, float(cp["centerDzUu"])])
    cx, cy, _ = ue_cam.project(ref)
    hx, hy, _ = ue_cam.project(wh)
    sx, sy, _ = ue_cam.project(wh + np.array([0.0, 0.0, float(cp["segmentDzUu"])]))
    seg = math.hypot(sx - hx, sy - hy)
    side = max(int(cp["minSidePx"]), int(round(float(cp["factor"]) * seg)))
    x0, y0 = int(round(cx - side / 2)), int(round(cy - side / 2))
    box = [x0, y0, x0 + side, y0 + side]
    row["K2_01_crop"] = {"center": [round(float(cx), 2), round(float(cy), 2)], "segmentPx": round(seg, 2),
                         "side": side, "box": box, "pxPerUuZ": round(seg / float(cp["segmentDzUu"]), 3)}
    if not (cam_check["ok"] and row["socketCheck"]["ok"] and src["ok"]):
        row["error"] = "маски не применены: " + "; ".join(
            (["модель камеры не согласуется с трассой"] if not cam_check["ok"] else [])
            + (["сокет Head не совпадает с ожидаемым для маски"] if not row["socketCheck"]["ok"] else [])
            + list(src.get("problems") or []))
        return row
    bl_cam = blender_camera_in_world(p["blenderView"], W, yaw)
    row["blenderCamera"] = bl_cam.describe()
    rp = p["reprojectionPlane"]
    plane = (fighter_to_world(rp["pointLocalUu"], W, yaw), fighter_dir_to_world(rp["normalLocal"], yaw))
    bpl = ue_cam.depth(ref) / bl_cam.depth(ref)  # Blender px per live px near the crop centre
    k = max(int(p["masks"]["minSupersample"]), int(math.ceil(2 * bpl)))
    dstats: dict = {}
    cov = reproject_labels(ue_cam, bl_cam, plane, src["label"], box, k, depth=src.get("depthFull"),
                           iterations=int(p["masks"]["depthIterations"]), stats=dstats,
                           march_steps=int(p["masks"]["depthMarchSteps"]))
    hb = p["headBoxLocalUu"]
    corners = [fighter_to_world((x, y, z), W, yaw) for x in hb["x"] for y in hb["y"] for z in hb["z"]]
    row["reprojection"] = {"method": "глубина ID-рендера (карта k2-id-depth) + итерация по лучу кадра; "
                                     "вертикальная плоскость фигуры — только начальное приближение",
                           "initialPlane": rp, "blenderPxPerLivePx": round(bpl, 4), "supersample": k,
                           "depthIteration": dstats,
                           "planeOnlyErrorBoundLivePx": round(plane_mapping_error(ue_cam, bl_cam, plane, corners), 3),
                           "planeOnlyErrorNote": "оценка ошибки без карты глубины (только плоскость) по углам габарита "
                                                 "головы headBoxLocalUu — обоснование, зачем нужна глубина",
                           "headBoxLocalUu": hb}
    img = Image.open(png).convert("RGB")
    crop = np.asarray(img.crop(tuple(box)), dtype=np.uint8)
    rgbf = crop.astype(np.float32)
    L = 0.2126 * rgbf[..., 0] + 0.7152 * rgbf[..., 1] + 0.0722 * rgbf[..., 2]
    mag = np.hypot(ndimage.sobel(L, axis=1), ndimage.sobel(L, axis=0))
    masks = _k2_masks(cov, p["masks"])
    row.update(k2_revision_values(L, mag, masks, p["masks"]))
    row["registration"] = silhouette_registration(masks["alpha"], mag, int(p["placementGate"]["autoWindowPx"]))
    row["_crop"], row["_masks"] = crop, masks
    return row


def _mean(xs):
    xs = [x for x in xs if x is not None]
    return round(sum(xs) / len(xs), 3) if xs else None


def cmd_metrics_revision(a) -> int:
    import numpy as np
    from PIL import Image
    rev = load_threshold_set(a.threshold_set, Path(a.thresholds) if getattr(a, "thresholds", None) else None)
    p = rev["params"]
    roles = [r.strip() for r in (a.roles or "host,joiner").split(",") if r.strip()]
    out_path = Path(a.out).resolve()
    crops_dir = Path(a.crops_dir).resolve() if a.crops_dir else out_path.parent / f"k2-crops-{rev['id']}"
    review = load_placement_review(a.placement_review)
    cache: dict = {}
    rows = [revision_frame(Path(d).resolve(), role, rev, cache) for d in a.run_dirs for role in roles]
    ok_rows = [r for r in rows if "error" not in r]
    # K2-05 / E2 in the revised crop: 3 control repeats (no variant flag) of each role/zoom
    groups: dict = {}
    for r in ok_rows:
        groups.setdefault((r["role"], r["zoomTag"], r["variant"], r["explicit"]), []).append(r)
    noise = []
    for (role, ztag, variant, explicit), grp in sorted(groups.items(), key=lambda kv: str(kv[0])):
        box = grp[0]["K2_01_crop"]["box"]
        arrs = [np.asarray(Image.open(REPO / g["frame"]).convert("RGB").crop(box), dtype=np.float32) for g in grp]
        pairs = [round(float(np.abs(arrs[i] - arrs[j]).mean()), 3) for i in range(len(arrs)) for j in range(i + 1, len(arrs))]
        spread = {}
        for key in ("K2_02", "K2_03", "K2_04"):
            vals = [g[key].get("value") for g in grp if g[key].get("value") is not None]
            spread[key] = round(max(vals) - min(vals), 3) if len(vals) >= 2 else None
        noise.append({"role": role, "zoomTag": ztag, "variant": variant, "explicit": explicit,
                      "runs": [g["run"] for g in grp], "roiBox": box, "pairwiseMeanAbsDeltaRGB": pairs,
                      "maxPairwise": max(pairs) if pairs else None, "metricRepeatSpread": spread})
    comparisons, overlays = [], []
    for role, ztag in sorted({(r["role"], r["zoomTag"]) for r in ok_rows}, key=lambda t: (t[0] != "host", t[1])):
        sel = [r for r in ok_rows if r["role"] == role and r["zoomTag"] == ztag]
        v2 = [r for r in sel if r["variant"] == "face-neck-v2" and r["explicit"]]
        v3 = [r for r in sel if r["variant"] == "head-tilt-v3"]
        ctl_all = [n for n in noise if n["role"] == role and n["explicit"] is False and len(n["runs"]) >= 3]
        ctl = next((n for n in ctl_all if n["zoomTag"] == ztag), ctl_all[0] if ctl_all else None)
        if not v2 or not v3:
            continue
        ov = write_revision_overlay(crops_dir / f"k2-bands-{rev['id']}-{ztag}-{role}-v2-left-v3-right.png",
                                    [{"crop": v2[0]["_crop"], "masks": v2[0]["_masks"]},
                                     {"crop": v3[0]["_crop"], "masks": v3[0]["_masks"]}])
        ov.update({"role": role, "zoomTag": ztag, "v2Frame": v2[0]["frame"], "v3Frame": v3[0]["frame"],
                   "legend": "слева v2, справа v3; верх — кроп без разметки, низ — маски: пурпурный контур — черты "
                             "лица (K2-02, считается после эрозии 1 px), голубой контур — венец (K2-03), жёлтый "
                             "(непрозрачность 0,4 + 0,6 × покрытие, чтобы был виден и просвет уже пикселя) — "
                             "сквозной просвет у стыка (K2-04)"})
        overlays.append(ov)
        box = v2[0]["K2_01_crop"]["box"]
        cross = []
        for r2 in v2:
            for r3 in v3:
                i2 = np.asarray(Image.open(REPO / r2["frame"]).convert("RGB").crop(box), dtype=np.float32)
                i3 = np.asarray(Image.open(REPO / r3["frame"]).convert("RGB").crop(box), dtype=np.float32)
                cross.append(round(float(np.abs(i2 - i3).mean()), 3))
        thr_noise = round(2 * ctl["maxPairwise"], 3) if ctl and ctl["maxPairwise"] is not None else None
        comp = {"role": role, "zoomTag": ztag, "zoom": sel[0]["zoom"], "v2Runs": [r["run"] for r in v2],
                "v3Runs": [r["run"] for r in v3], "overlay": ov["file"], "roiBox": box,
                "noise": {"controlRuns": ctl["runs"] if ctl else None, "controlZoomTag": ctl["zoomTag"] if ctl else None,
                          "maxPairwise": ctl["maxPairwise"] if ctl else None, "threshold2xNoise": thr_noise,
                          "note": "E2: 3 повтора без флага варианта той же роли клиента; для зума без своих повторов "
                                  "берётся шум контрольной группы этой роли (как в T1.1)"},
                "v2VsV3MeanAbsDeltaRGB": cross,
                "v2VsV3AboveNoiseThreshold": (min(cross) > thr_noise) if (cross and thr_noise) else None,
                "registrationOk": {"v2": [r["registration"].get("ok") for r in v2],
                                   "v3": [r["registration"].get("ok") for r in v3]}}
        for key, gate_key, better in (("K2_02", "faceMaskOnFace", ">="), ("K2_03", "crownMaskOnCrown", ">="),
                                      ("K2_04", "gapMaskOnNeckline", "<=")):
            m2 = _mean([r[key].get("value") for r in v2])
            m3 = _mean([r[key].get("value") for r in v3])
            small = any(r[key].get("value") is None for r in v2 + v3)
            counted, why = placement_verdict(review, ov, gate_key)
            entry = {"v2": m2, "v3": m3, "comparator": f"v3 {better} v2",
                     "controlRepeatSpread": ctl.get("metricRepeatSpread", {}).get(key)
                     if (ctl and ctl["zoomTag"] == ztag) else None}
            if small:
                entry.update({"status": REV_SMALL, "counted": False, "v3VsV2Holds": None})
            elif not counted:
                entry.update({"status": why, "counted": False, "v3VsV2Holds": None,
                              "v3VsV2Formal": (m3 >= m2) if better == ">=" else (m3 <= m2)})
            else:
                entry.update({"status": REV_MEASURED, "counted": True, "placement": why,
                              "v3VsV2Holds": (m3 >= m2) if better == ">=" else (m3 <= m2)})
            spread = entry["controlRepeatSpread"]
            if m2 is not None and m3 is not None and spread is not None:
                entry["differenceWithinControlRepeatSpread"] = abs(m3 - m2) <= spread
            comp[key] = entry
        comparisons.append(comp)
    # per (variant, zoom, role) reprojected label maps for inspection
    mask_files = []
    seen = set()
    colours = {CLASS_ID[n]: c for n, c in ID_CLASSES}
    colours[GAP_ID] = (255, 128, 0)
    for r in ok_rows:
        key = (r["maskSource"]["tag"], r["zoomTag"], r["role"])
        if key in seen:
            continue
        seen.add(key)
        m = r["_masks"]
        vis = np.full(m["alpha"].shape + (3,), 128, dtype=np.uint8)
        vis[m["alpha"]] = (60, 60, 60)
        vis[m["crown"]] = colours[CLASS_ID["crown"]]
        vis[m["face"]] = colours[CLASS_ID["features"]]
        vis[m["gap"]] = colours[GAP_ID]
        path = crops_dir / f"k2-masks-{rev['id']}-{key[0]}-{key[1]}-{key[2]}.png"
        crops_dir.mkdir(parents=True, exist_ok=True)
        Image.fromarray(vis).save(path)
        mask_files.append({"tag": key[0], "zoomTag": key[1], "role": key[2], "file": rel(path), "sha256": sha256_file(path),
                           "legend": "серый — фон, тёмно-серый — фигура, красный — черты лица, зелёный — венец, "
                                     "оранжевый — сквозной просвет (покрытие ≥ 0,5, до эрозии)"})
    public_rows = [{k: v for k, v in r.items() if not k.startswith("_")} for r in rows]
    summary = []
    for c in comparisons:
        for key, name in (("K2_02", "K2-02 лицо"), ("K2_03", "K2-03 венец"), ("K2_04", "K2-04 просвет")):
            e = c[key]
            verdict = ("выполнено" if e["v3VsV2Holds"] else "не выполнено") if e.get("counted") else e["status"]
            extra = ""
            if e.get("differenceWithinControlRepeatSpread") is not None:
                extra = (", разница в пределах разброса контрольных повторов" if e["differenceWithinControlRepeatSpread"]
                         else ", разница больше разброса контрольных повторов")
            summary.append(f"{c['zoomTag']} {c['role']}: {name}: v2 {e['v2']} -> v3 {e['v3']} ({e['comparator']}): "
                           f"{verdict}{extra}")
    counted_any = any(c[k].get("counted") for c in comparisons for k in ("K2_02", "K2_03", "K2_04"))
    doc = {"schema": "unmatched.art004-k2-metrics-revision/1",
           "thresholdSet": rev["id"], "thresholdSetStatus": rev.get("status"),
           "thresholds": f"{rel(Path(a.thresholds)) if getattr(a, 'thresholds', None) else rel(THRESHOLDS_JSON)} "
                         f"revisions[id={rev['id']}]",
           "status": ("измерено по ревизии (ретроспективно на кадрах T1.1; E3: ревизия зарегистрирована после этих "
                      "прогонов и не является их гейтом)" if counted_any else REV_PENDING),
           "frames": {"total": len(rows), "withMasks": len(ok_rows), "roles": roles},
           "maskSources": {m: {k: v for k, v in s.items() if k not in ("label", "depthFull")} for m, s in cache.items()},
           "params": p, "placementReview": {k: v for k, v in review.items() if k != "entries"} or None,
           "summary": summary,
           "overlays": overlays, "maskMaps": mask_files, "comparisons": comparisons, "repeatNoise": noise,
           "rows": public_rows,
           "caveat": "Кадры packaged-live с HUD, подписями и boardState. Маски — геометрия Blender (покой, без анимации) "
                     "той же сетки, репроецированная через камеру из трассы; K2-04 — геометрическая величина при камере "
                     "кадра, живые пиксели для неё только диагностика. Это измерение, не художественная приёмка лица "
                     "(открыта до T4.1/T6)."}
    write_json(out_path, doc)
    print(json.dumps([{"frame": r.get("frame"), "zoom": r.get("zoomTag"), "err": r.get("error"),
                       "K2_02": _dig(r, ("K2_02", "value")), "K2_03": _dig(r, ("K2_03", "value")),
                       "K2_04": _dig(r, ("K2_04", "value")), "reg": _dig(r, ("registration", "bestShift"))}
                      for r in public_rows], ensure_ascii=False, indent=1))
    print(json.dumps([{k: c[k] for k in ("role", "zoomTag", "K2_02", "K2_03", "K2_04", "v2VsV3AboveNoiseThreshold")}
                      for c in comparisons], ensure_ascii=False, indent=1))
    return 0 if all("error" not in r for r in rows) else 3


def perf02_evaluate(summary: dict, threshold_set: dict, registered: dict | None = None) -> dict:
    """PERF-02 per client of a perf-summary.json (trace PERF summary scope=started is the source; the CSV
    FrameTime p95 is a control) against the registered limit and the revised cap-relative limit."""
    reg = registered or threshold_set
    reg_limit = next(s for s in reg["perf"]["setups"] if s["id"] == "PERF-02")["threshold"]["p95FrameTimeMsEach"]
    tol = float(((threshold_set.get("params") or {}).get("perf02") or {}).get("toleranceMs", 0.0))
    clients = []
    for run in summary["runs"]:
        perf = json.loads((REPO / run["run"] / "perf.json").read_text(encoding="utf-8"))
        for role, c in run["clients"].items():
            cap = float(((perf["clients"].get(role) or {}).get("config") or {}).get("tMaxFPS") or 0.0)
            period = 1000.0 / cap if cap else None
            trace_p95 = c["traceStarted"]["frameMsP95"]
            csv_p95 = (c.get("csv") or {}).get("frameTimeP95")
            clients.append({"run": run["run"], "role": role, "tMaxFPS": cap, "periodMs": round(period, 4) if period else None,
                            "traceP95Ms": trace_p95, "csvP95Ms": csv_p95})
    out = {"thresholdSet": threshold_set.get("id"), "source": "trace PERF summary scope=started frameMs p95",
           "control": "CSV FrameTime p95 (first 1200 frames incl. pre-Started; only recorded)", "clients": clients}
    for c in clients:
        per = c["periodMs"]
        c["limits"] = {"registered": float(reg_limit), "t11_33p4": 33.4,
                       "t11_periodPlus1pct": round(per * 1.01, 4) if per else None,
                       "revisedPeriodPlusTol": round(per + tol, 4) if (per and tol) else None}
        c["pass"] = {k: {"trace": (c["traceP95Ms"] <= v) if (v is not None and c["traceP95Ms"] is not None) else None,
                         "csv": (c["csvP95Ms"] <= v) if (v is not None and c["csvP95Ms"] is not None) else None}
                     for k, v in c["limits"].items()}
    agg = {}
    for k in ("registered", "t11_33p4", "t11_periodPlus1pct", "revisedPeriodPlusTol"):
        agg[k] = {src: sum(1 for c in clients if c["pass"][k][src]) for src in ("trace", "csv")}
        agg[k]["n"] = len(clients)
    tr = [c["traceP95Ms"] for c in clients if c["traceP95Ms"] is not None]
    cs = [c["csvP95Ms"] for c in clients if c["csvP95Ms"] is not None]
    out["passCounts"] = agg
    out["ranges"] = {"traceP95Ms": [min(tr), max(tr)] if tr else None,
                     "csvP95Ms": [round(min(cs), 3), round(max(cs), 3)] if cs else None,
                     "periodMs": sorted({c["periodMs"] for c in clients})}
    out["toleranceMs"] = tol
    out["revisedPass"] = bool(clients) and all(c["pass"]["revisedPeriodPlusTol"]["trace"] for c in clients)
    return out


def cmd_perf02(a) -> int:
    rev = load_threshold_set(a.threshold_set, Path(a.thresholds) if a.thresholds else None)
    reg = load_threshold_set(THRESHOLD_SET_REGISTERED, Path(a.thresholds) if a.thresholds else None)
    doc = perf02_evaluate(json.loads(Path(a.summary).read_text(encoding="utf-8")), rev, reg)
    if a.out:
        write_json(Path(a.out).resolve(), doc)
    print(json.dumps({k: doc[k] for k in ("thresholdSet", "passCounts", "ranges", "toleranceMs", "revisedPass")},
                     ensure_ascii=False, indent=1))
    return 0


def cmd_csvsummary(a) -> int:
    for d in a.run_dirs:
        rd = Path(d).resolve()
        doc = write_csv_summary(rd)
        if doc is None:
            print(rd.name, "no client-csv")
            continue
        man = rd / "manifest.json"
        if man.is_file():
            m = json.loads(man.read_text(encoding="utf-8-sig"))
            p = rd / "perf-csv.json"
            m["files"] = [e for e in m["files"] if e["name"] != "perf-csv.json"]
            m["files"].append({"name": "perf-csv.json", "bytes": p.stat().st_size, "sha256": sha256_file(p)})
            man.write_text(json.dumps(m, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
        for role, c in doc["clients"].items():
            print(rd.name, role, "fps", c["effectiveFps"], "frame p95", c["FrameTime"].get("p95"),
                  "gpuBusy mean", c["GPUBusy"].get("mean"), "p95", c["GPUBusy"].get("p95"))
    return 0


def cmd_perfsummary(a) -> int:
    """Aggregate perf.json / perf-csv.json / timing.json of several run dirs into one table."""
    base = json.loads(Path(a.baseline).read_text(encoding="utf-8")) if a.baseline else None
    rows = []
    for d in a.run_dirs:
        rd = Path(d).resolve()
        perf = json.loads((rd / "perf.json").read_text(encoding="utf-8"))
        pcsv = json.loads((rd / "perf-csv.json").read_text(encoding="utf-8")) if (rd / "perf-csv.json").is_file() else {}
        timing = json.loads((rd / "timing.json").read_text(encoding="utf-8"))
        status = json.loads((rd / "art-preview-status.json").read_text(encoding="utf-8-sig"))
        row = {"run": rel(rd), "variant": status.get("medusaVariant"), "explicit": status.get("medusaVariantExplicit"),
               "zoom": status.get("hostFocusZoom"), "gpuTotalUtilPct": perf["gpuTotal"]["utilizationPct"],
               "gpuTotalPowerW": perf["gpuTotal"]["powerW"], "gpuMemUsedMiB": perf["gpuTotal"]["memUsedMiB"],
               "startGameS": (timing.get("host") or {}).get("startGameS"),
               "cameraSettledS": (timing.get("host") or {}).get("cameraSettledElapsed"),
               "clients": {}}
        for role in ("host", "joiner"):
            tr = ((perf["clients"].get(role) or {}).get("summary") or {}).get("started") or {}
            cs = (pcsv.get("clients") or {}).get(role) or {}
            row["clients"][role] = {
                "traceStarted": {"fps": tr.get("fps"), "frameMsP95": (tr.get("frameMs") or {}).get("p95"),
                                 "frameMsMax": (tr.get("frameMs") or {}).get("max"), "hitches50": tr.get("hitches50"),
                                 "gameMsAvg": (tr.get("gameMs") or {}).get("avg"),
                                 "renderMsAvg": (tr.get("renderMs") or {}).get("avg"),
                                 "gpuFrameIntervalMsAvg": (tr.get("gpuMs") or {}).get("avg")},
                "csv": {"effectiveFps": cs.get("effectiveFps"), "frameTimeP95": (cs.get("FrameTime") or {}).get("p95"),
                        "gpuBusyMsP50": (cs.get("GPUBusy") or {}).get("p50"),
                        "gpuBusyMsP95": (cs.get("GPUBusy") or {}).get("p95"),
                        "gpuBusyMsMean": (cs.get("GPUBusy") or {}).get("mean")} if cs else None}
        rows.append(row)
    allc = [c for r in rows for c in r["clients"].values()]
    agg = {
        "fpsMin": min(c["traceStarted"]["fps"] for c in allc if c["traceStarted"]["fps"] is not None),
        "fpsMax": max(c["traceStarted"]["fps"] for c in allc if c["traceStarted"]["fps"] is not None),
        "frameMsP95Max": max(c["traceStarted"]["frameMsP95"] for c in allc if c["traceStarted"]["frameMsP95"] is not None),
        "gpuBusyMsP50Range": [min(c["csv"]["gpuBusyMsP50"] for c in allc if c["csv"]),
                              max(c["csv"]["gpuBusyMsP50"] for c in allc if c["csv"])] if any(c["csv"] for c in allc) else None,
        "gpuTotalUtilMeanRange": [min(r["gpuTotalUtilPct"].get("mean", 0) for r in rows),
                                  max(r["gpuTotalUtilPct"].get("mean", 0) for r in rows)],
        "gpuTotalUtilP95Max": max(r["gpuTotalUtilPct"].get("p95", 0) for r in rows),
        "baselineGpuUtil": base["gpuUtilizationPct"] if base else None,
        "baselinePowerW": base["powerW"] if base else None}
    doc = {"schema": "unmatched.art004-perf-summary/1", "status": "измерено",
           "scope": "текущий ПК разработки (RTX 4090, i9-13900F), Development packaged, два offscreen-клиента по 30 FPS "
                    "(-ClientFps 30 -> t.MaxFPS 30); не целевой ПК D-07; ACC-022 и perf-gate GD-058 не заявляются",
           "thresholdsRef": "thresholds.json perf.PERF-02 (p95FrameTimeMsEach <= 33.3; GPU utilization only recorded)",
           "aggregate": agg, "runs": rows}
    write_json(Path(a.out).resolve(), doc)
    print(json.dumps(agg, ensure_ascii=False, indent=1))
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    b = sub.add_parser("build")
    b.add_argument("--label", required=True)
    b.add_argument("--out", required=True)
    b.add_argument("--max-parallel", type=int, default=0)
    b.add_argument("--extra", action="append", default=[],
                   help="one extra UBT flag per occurrence: --extra=-NoLiveCoding --extra=-MapFile")
    p = sub.add_parser("package")
    p.add_argument("--label", required=True)
    p.add_argument("--out", required=True)
    p.add_argument("--direct", action="store_true", help="A/B only: BuildCookRun -skipbuild without the guard")
    p.add_argument("--expect-refusal", action="store_true")
    r = sub.add_parser("run")
    r.add_argument("--label", required=True)
    r.add_argument("--evidence-dir", required=True)
    r.add_argument("--work", default=r"C:\tmp\t11\runs")
    r.add_argument("--board-id", default=REVIEW_BOARD_ID)
    r.add_argument("--variant", choices=["none", "face-neck-v2", "head-tilt-v3"], default="none")
    r.add_argument("--zoom", type=float, default=0.0)
    r.add_argument("--shot-after", type=int, default=36)
    r.add_argument("--run-seconds", type=int, default=50)
    r.add_argument("--client-fps", type=int, default=30)
    r.add_argument("--csv-frames", type=int, default=1200)
    r.add_argument("--build-record")
    r.add_argument("--package-record")
    r.add_argument("--expect-crash", action="store_true")
    g = sub.add_parser("baseline")
    g.add_argument("--out", required=True)
    g.add_argument("--seconds", type=int, default=20)
    cs = sub.add_parser("csvsummary", help="(re)write perf-csv.json for run dirs and list it in manifest.json")
    cs.add_argument("run_dirs", nargs="+")
    ps_ = sub.add_parser("perfsummary")
    ps_.add_argument("--out", required=True)
    ps_.add_argument("--baseline")
    ps_.add_argument("run_dirs", nargs="+")
    mm = sub.add_parser("metrics")
    mm.add_argument("--out", required=True)
    mm.add_argument("--threshold-set", default=THRESHOLD_SET_REGISTERED,
                    help="'registered' (T1.1 bands, host frames) or a thresholds.json revisions[] id, e.g. "
                         f"{THRESHOLD_SET_REV1} (reprojected Blender ID masks)")
    mm.add_argument("--thresholds", help="thresholds.json path (default: s3-baseline-2026-09-28)")
    mm.add_argument("--roles", help="revision sets only: client frames, default host,joiner")
    mm.add_argument("--placement-review", help="revision sets only: JSON review of the k2-bands-<set>-*.png overlays")
    mm.add_argument("--crops-dir", help="revision sets only: derived overlays / mask maps (default <out dir>/k2-crops-<set>)")
    mm.add_argument("run_dirs", nargs="+")
    pf = sub.add_parser("perf02", help="PERF-02 p95 per client of a perf-summary.json against a threshold set")
    pf.add_argument("--threshold-set", default=THRESHOLD_SET_REV1)
    pf.add_argument("--thresholds")
    pf.add_argument("--out")
    pf.add_argument("summary")
    a = ap.parse_args(argv)
    return {"build": cmd_build, "package": cmd_package, "run": cmd_run, "baseline": cmd_baseline,
            "metrics": cmd_metrics, "csvsummary": cmd_csvsummary,
            "perfsummary": cmd_perfsummary, "perf02": cmd_perf02}[a.cmd](a)


if __name__ == "__main__":
    sys.exit(main())
