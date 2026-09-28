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
           K2-02/K2-03 on the registered fallback bands are reported as
           formally computed but "не измерено (невалидно)": the bands miss the
           face and the crown on screen (FALLBACK_BAND_AUDIT); band overlays
           k2-bands-*.png are written for the placement check.

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
    mm.add_argument("run_dirs", nargs="+")
    a = ap.parse_args(argv)
    return {"build": cmd_build, "package": cmd_package, "run": cmd_run, "baseline": cmd_baseline,
            "metrics": cmd_metrics, "csvsummary": cmd_csvsummary,
            "perfsummary": cmd_perfsummary}[a.cmd](a)


if __name__ == "__main__":
    sys.exit(main())
