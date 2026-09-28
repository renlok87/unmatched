#!/usr/bin/env python3
"""Stage-3 baseline snapshot (T0): production hashes and process inventory.

Read-only with respect to both checkouts: it hashes files, lists processes and
ports, and writes JSON only into this evidence directory (or --out).

  python snapshot_baseline.py production [--out production-baseline.json]
  python snapshot_baseline.py check      [--baseline production-baseline.json]
  python snapshot_baseline.py processes  [--out process-inventory.json]

`check` re-hashes every file listed in production-baseline.json and exits 1 on
any difference (use it before and after every stage-3 task that could touch
production: "производство не тронуто").

`processes` needs Windows PowerShell (Get-NetTCPConnection, Win32_Process) and
the docker CLI; it never stops or starts anything.
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
MAIN = Path(__file__).resolve().parents[4]
ART = Path("C:/Users/ren/.codex/worktrees/art-foundation/unmached")
ROOTS = {"repo": MAIN, "art-worktree": ART}
UE = "unreal/Unmatched"

# Files whose bytes define "production is untouched" for stage 3.
PRODUCTION_FILES = [
    "blender/ASSET-MEDUSA-001/export/SK_Medusa.fbx",
    "blender/ASSET-MEDUSA-001/export/SM_Medusa_Base.fbx",
    "blender/ASSET-MEDUSA-001/medusa.blend",
    "blender/ASSET-MEDUSA-001/variants/face-section-neck-v2/SK_Medusa_FaceSectionNeck_v2.fbx",
    "blender/ASSET-MEDUSA-001/variants/head-tilt-v3/SK_Medusa_HeadTilt_v3.fbx",
    f"{UE}/Config/DefaultGame.ini",
    f"{UE}/Config/DefaultGameUserSettings.ini",
    f"{UE}/Config/DefaultEngine.ini",
]
# Directories hashed file by file (all files, sorted).
PRODUCTION_DIRS = [
    f"{UE}/Content/ArtPreview/Medusa",
    f"{UE}/Content/ART004/Medusa",
]
# Local, gitignored state that decides the effective FPS of a packaged client.
RUNTIME_FILES = [
    f"{UE}/Saved/StagedBuilds/Windows/Unmatched/Saved/Config/Windows/GameUserSettings.ini",
    f"{UE}/Binaries/Win64/Unmatched.exe",
    f"{UE}/Saved/StagedBuilds/Windows/Unmatched/Binaries/Win64/Unmatched.exe",
    f"{UE}/Saved/StagedBuilds/Windows/Unmatched.exe",
]
PORTS = [8123, 9876, 9877, 3120, 3100, 55434, 6381, 24680]


def sha256(p: Path) -> str:
    h = hashlib.sha256()
    with p.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def git(root: Path, *args: str, strip: bool = True) -> str:
    """Run git in root. strip=False keeps leading whitespace (porcelain XY codes such as " M")."""
    try:
        out = subprocess.run(["git", "-c", "core.longpaths=true", "-C", str(root), *args],
                             capture_output=True, text=True, check=True).stdout
    except (OSError, subprocess.CalledProcessError):
        return ""
    return out.strip() if strip else out.rstrip("\r\n")


def git_state(root: Path, rel: str) -> str:
    if git(root, "ls-files", "--", rel):
        return "tracked"
    r = subprocess.run(["git", "-C", str(root), "check-ignore", "-q", "--no-index", rel])
    return "ignored" if r.returncode == 0 else "untracked"


def file_row(root_name: str, rel: str) -> dict:
    root = ROOTS[root_name]
    p = root / rel
    row = {"root": root_name, "path": rel, "exists": p.is_file()}
    if p.is_file():
        row.update(bytes=p.stat().st_size, sha256=sha256(p), git=git_state(root, rel))
    return row


def frame_rate_limit(p: Path) -> str | None:
    if not p.is_file():
        return None
    for line in p.read_text(encoding="utf-8", errors="replace").splitlines():
        if line.strip().lower().startswith("frameratelimit="):
            return line.split("=", 1)[1].strip()
    return "absent"


def production(out: Path) -> dict:
    files, dirs, runtime, config = [], [], [], {}
    for root_name in ROOTS:
        for rel in PRODUCTION_FILES:
            files.append(file_row(root_name, rel))
        for d in PRODUCTION_DIRS:
            base = ROOTS[root_name] / d
            listing = sorted(p for p in base.rglob("*") if p.is_file()) if base.is_dir() else []
            dirs.append({
                "root": root_name, "dir": d, "exists": base.is_dir(), "fileCount": len(listing),
                "files": [file_row(root_name, p.relative_to(ROOTS[root_name]).as_posix()) for p in listing],
            })
        for rel in RUNTIME_FILES:
            runtime.append(file_row(root_name, rel))
        config[root_name] = {
            "DefaultGameUserSettings.FrameRateLimit": frame_rate_limit(ROOTS[root_name] / UE / "Config/DefaultGameUserSettings.ini"),
            "StagedSaved.GameUserSettings.FrameRateLimit": frame_rate_limit(
                ROOTS[root_name] / UE / "Saved/StagedBuilds/Windows/Unmatched/Saved/Config/Windows/GameUserSettings.ini"),
        }
    warnings = []
    for name, c in config.items():
        staged = c["StagedSaved.GameUserSettings.FrameRateLimit"]
        if staged not in (None, "absent"):
            try:
                if float(staged) != 60.0:
                    warnings.append(f"{name}: staged Saved/Config/Windows/GameUserSettings.ini FrameRateLimit={staged} "
                                    "overrides DefaultGameUserSettings (60); 0 = uncapped. A packaged client staged here "
                                    "would not run at the AGENTS.md default of 60 FPS unless -ClientFps/t.MaxFPS caps it.")
            except ValueError:
                warnings.append(f"{name}: unparsable staged FrameRateLimit={staged}")
        elif staged == "absent":
            warnings.append(f"{name}: staged GameUserSettings.ini has no FrameRateLimit line; the effective value is "
                            "not proven by config alone (expected: DefaultGameUserSettings 60) and must be measured.")
    heads = {name: {"branch": git(r, "rev-parse", "--abbrev-ref", "HEAD"), "commit": git(r, "rev-parse", "HEAD"),
                    "tree": git(r, "rev-parse", "HEAD^{tree}"),
                    "statusPorcelain": git(r, "status", "--porcelain", strip=False).splitlines()} for name, r in ROOTS.items()}
    doc = {
        "schema": "unmatched.s3-production-baseline/1",
        "createdUtc": dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "task": "Stage 3 / T0: базовый снимок «производство не тронуто»",
        "status": "измерено",
        "command": "python docs/art-pipeline/evidence/s3-baseline-2026-09-28/snapshot_baseline.py production",
        "checkCommand": "python docs/art-pipeline/evidence/s3-baseline-2026-09-28/snapshot_baseline.py check",
        "roots": {k: str(v).replace("\\", "/") for k, v in ROOTS.items()},
        "heads": heads,
        "productionFiles": files,
        "productionDirs": dirs,
        "runtimeLocalState": runtime,
        "effectiveFpsConfig": config,
        "warnings": warnings,
        "notes": [
            "SK_Medusa.fbx, SM_Medusa_Base.fbx, medusa.blend и /Game/ART004/Medusa — производственный кандидат арт-трека; этап 3 их не заменяет.",
            "/Game/ArtPreview/Medusa: 9 uasset v2 отслеживаются git (force-add); в арт-worktree дополнительно 2 gitignored uasset v3 (SK_Medusa_HeadTilt_v3Candidate{,_Skeleton}).",
            "/Game/ART004/Medusa в git не входит (Content gitignored) и воспроизводится tools/art/import_medusa_candidate.py.",
            "runtimeLocalState — локальные gitignored бинарники/настройки; меняются каждой сборкой и в «производство» не входят. Корневой StagedBuilds/Windows/Unmatched.exe — заглушка-лаунчер; сверять внутренний Binaries/Win64/Unmatched.exe (memory s09-duel-evidence-traps).",
            "effectiveFpsConfig — только конфиги. Эффективный FPS packaged-клиента не измерялся (измеряет T1.1/T6: AGENTS.md, ACC-022).",
        ],
    }
    out.write_text(json.dumps(doc, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
    return doc


def check(baseline: Path) -> int:
    doc = json.loads(baseline.read_text(encoding="utf-8"))
    rows = list(doc["productionFiles"]) + [f for d in doc["productionDirs"] for f in d["files"]]
    diffs = []
    for r in rows:
        p = ROOTS[r["root"]] / r["path"]
        now = sha256(p) if p.is_file() else None
        if now != r.get("sha256"):
            diffs.append({"root": r["root"], "path": r["path"], "baseline": r.get("sha256"), "now": now})
    for d in doc["productionDirs"]:
        base = ROOTS[d["root"]] / d["dir"]
        now_files = {p.relative_to(ROOTS[d["root"]]).as_posix() for p in base.rglob("*") if p.is_file()} if base.is_dir() else set()
        was = {f["path"] for f in d["files"]}
        for extra in sorted(now_files - was):
            diffs.append({"root": d["root"], "path": extra, "baseline": None, "now": "new file"})
    print(json.dumps({"checked": len(rows), "differences": diffs}, ensure_ascii=False, indent=2))
    return 1 if diffs else 0


PS_PROCESSES = r"""
$ports = @(%PORTS%)
$listen = Get-NetTCPConnection -State Listen -ErrorAction SilentlyContinue | Where-Object { $ports -contains $_.LocalPort }
$names = 'UnrealEditor','UnrealEditor-Cmd','Unmatched','blender','node','python','pythonw','com.docker.backend','Docker Desktop','wslrelay','vmmem','vmmemWSL'
$procs = Get-CimInstance Win32_Process | Where-Object { $n = [IO.Path]::GetFileNameWithoutExtension($_.Name); $names -contains $n -or ($listen.OwningProcess -contains $_.ProcessId) }
$out = [ordered]@{
  listeners = @($listen | ForEach-Object { [ordered]@{ port = $_.LocalPort; address = $_.LocalAddress; pid = $_.OwningProcess } })
  processes = @($procs | ForEach-Object { [ordered]@{ pid = $_.ProcessId; parentPid = $_.ParentProcessId; name = $_.Name; exe = $_.ExecutablePath; commandLine = $_.CommandLine; created = if ($_.CreationDate) { $_.CreationDate.ToUniversalTime().ToString('yyyy-MM-ddTHH:mm:ssZ') } else { $null } } })
  disks = @(Get-CimInstance Win32_LogicalDisk -Filter "DriveType=3" | ForEach-Object { [ordered]@{ drive = $_.DeviceID; freeGB = [math]::Round($_.FreeSpace/1GB,1); sizeGB = [math]::Round($_.Size/1GB,1) } })
  pagefile = @(Get-CimInstance Win32_PageFileUsage | ForEach-Object { [ordered]@{ name = $_.Name; allocatedMB = $_.AllocatedBaseSize; currentUsageMB = $_.CurrentUsage; peakUsageMB = $_.PeakUsage } })
  memory = (Get-CimInstance Win32_OperatingSystem | ForEach-Object { [ordered]@{ totalVisibleGB = [math]::Round($_.TotalVisibleMemorySize/1MB,1); freePhysicalGB = [math]::Round($_.FreePhysicalMemory/1MB,1); totalVirtualGB = [math]::Round($_.TotalVirtualMemorySize/1MB,1); freeVirtualGB = [math]::Round($_.FreeVirtualMemory/1MB,1) } })
}
$out | ConvertTo-Json -Depth 5 -Compress
"""


# Role annotation by command-line pattern (never by process name alone).
ROLE_RULES = [
    ("-ModelContextProtocolPort=8123", "UnrealEditor главного checkout с MCP :8123; запущен оркестратором этапа 3; не закрывать; пока открыт — UnrealEditor-Cmd/упаковка на главном проекте запрещены (UE-lock)"),
    ("blender_mcp_start_9877.py", "Blender MCP :9877 — линия кандидатов пайплайна (B2); не трогать"),
    ("blender_mcp_start.py", "Blender MCP :9876 — линия Medusa v3.1 (B1); не трогать"),
    ("glm-haiku-proxy", "GLM haiku proxy :24680 (сервис пользователя); не трогать"),
    ("UnrealEditor-Cmd", "UnrealEditor-Cmd — должен принадлежать текущей задаче; иначе выяснить владельца, не убивать"),
    ("snapshot_baseline.py", "этот сборщик инвентаря (завершается сам)"),
    ("mcp", "MCP-сервер сессии Claude/Codex; не трогать"),
    ("desktop-commander", "MCP-сервер сессии Claude/Codex (desktop-commander); не трогать"),
    ("agentmemory", "сервис памяти агента; не трогать"),
    ("vmmem", "виртуальная машина WSL2/Docker; не трогать"),
]


def role_of(proc: dict) -> str | None:
    text = f"{proc.get('name') or ''} {proc.get('commandLine') or ''}"
    for pattern, role in ROLE_RULES:
        if pattern.lower() in text.lower():
            return role
    return None


def processes(out: Path) -> dict:
    script = PS_PROCESSES.replace("%PORTS%", ",".join(str(p) for p in PORTS))
    r = subprocess.run(["powershell.exe", "-NoProfile", "-NonInteractive", "-Command", script],
                       capture_output=True, text=True, encoding="utf-8", errors="replace",
                       creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    data = json.loads(r.stdout) if r.stdout.strip() else {"error": r.stderr[-2000:]}
    try:
        d = subprocess.run(["docker", "ps", "-a", "--format", "{{json .}}"], capture_output=True, text=True, timeout=60,
                           creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        containers = [json.loads(line) for line in d.stdout.splitlines() if line.strip()]
        docker = {"exit": d.returncode, "stderr": d.stderr.strip()[-500:], "containers": [
            {k: c.get(k) for k in ("Names", "Image", "State", "Status", "Ports", "ID")} for c in containers]}
    except (OSError, subprocess.TimeoutExpired) as e:
        docker = {"error": str(e)}
    doc = {
        "schema": "unmatched.s3-process-inventory/1",
        "createdUtc": dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "status": "измерено",
        "command": "python docs/art-pipeline/evidence/s3-baseline-2026-09-28/snapshot_baseline.py processes",
        "portsQueried": PORTS,
        **data,
        "docker": docker,
    }
    for proc in doc.get("processes", []):
        proc["role"] = role_of(proc)
    listening = {l["port"] for l in doc.get("listeners", [])}
    doc["portSummary"] = {str(p): ("listening pid=" + ",".join(str(l["pid"]) for l in doc["listeners"] if l["port"] == p))
                          if p in listening else "not listening" for p in PORTS}
    out.write_text(json.dumps(doc, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
    return doc


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("mode", choices=["production", "check", "processes"])
    ap.add_argument("--out", type=Path)
    ap.add_argument("--baseline", type=Path, default=HERE / "production-baseline.json")
    a = ap.parse_args()
    if a.mode == "production":
        production(a.out or HERE / "production-baseline.json")
        return 0
    if a.mode == "check":
        return check(a.baseline)
    processes(a.out or HERE / "process-inventory.json")
    return 0


if __name__ == "__main__":
    sys.exit(main())
