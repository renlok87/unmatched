#!/usr/bin/env python3
"""ENV-MAPS P5a live wrapper (copy of P3 live_run.py; lock owner ENV-MAPS-P5a) (scratch, outside git): one run-phase2-demo / run-combat-demo pair on the
worktree's packaged build against :3120, with nvidia-smi sampling (gpu csv + pmon), client-log copy
(room code redacted), perf.json and run-record.json; failed runs keep traces in failed-<stamp>/attempt.json.
Credentials: backend/.env via tools/s09/run-with-env.cjs (environment only, never argv)."""
from __future__ import annotations
import argparse, datetime as dt, json, re, shutil, subprocess, sys, threading, time
from pathlib import Path

WT = Path(r"C:\tmp\wt-envmaps")
sys.path.insert(0, str(WT / "tools" / "art"))
import art004_live_k2 as L  # noqa: E402

LOCK = Path(r"C:\tmp\unmatched-gpu.lock")
ROOM_CODE = re.compile(r"createGame -> room=([A-Za-z0-9_-]+) code=([A-Z0-9-]{4,12})")
SCRIPTS = {"phase2": WT / "tools" / "s08" / "run-phase2-demo.ps1", "combat": WT / "tools" / "s09" / "run-combat-demo.ps1"}
PREFIX = {"phase2": "phase2-client", "combat": "combat-client"}
STAGE = str(L.STAGE_ROOT).lower()


def ours(c: dict) -> bool:
    return bool(c.get("exe")) and str(c["exe"]).lower().startswith(STAGE)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--kind", choices=sorted(SCRIPTS), required=True)
    ap.add_argument("--label", required=True)
    ap.add_argument("--evidence-dir", required=True)
    ap.add_argument("--work", default=r"C:\tmp\envmaps-research\p5a\live\work")
    ap.add_argument("--perf-note", default="измерено; dev-PC (RTX 4090), не D-07; запись, не заявка ACC-022")
    ap.add_argument("demo_args", nargs=argparse.REMAINDER)
    a = ap.parse_args()
    dargs = [x for x in a.demo_args if x != "--"]
    lock = LOCK.read_text(encoding="utf-8", errors="replace") if LOCK.is_file() else ""
    if "ENV-MAPS-P5a" not in lock:
        print(f"REFUSED: GPU lock not held by ENV-MAPS-P5a: {lock!r}")
        return 2
    backend = L.listeners(3120)
    if len(backend) != 1:
        print(f"REFUSED: expected one backend listener on :3120, got {backend}")
        return 2
    evidence = Path(a.evidence_dir).resolve()
    evidence.mkdir(parents=True, exist_ok=True)
    work = Path(a.work) / f"{a.label}-{dt.datetime.now():%Y%m%d-%H%M%S}"
    work.mkdir(parents=True, exist_ok=True)
    pre = [c for c in L.find_client_pids(0) if ours(c)]
    if pre:
        print(f"REFUSED: worktree clients already running: {pre}")
        return 2
    cmd = ["node", str(WT / "tools" / "s09" / "run-with-env.cjs"), "powershell", "-NoProfile", "-ExecutionPolicy",
           "Bypass", "-File", str(SCRIPTS[a.kind]), "-EvidenceDir", str(evidence)] + dargs
    rec = {"schema": "unmatched.envmaps-p5a-live-run/1", "label": a.label, "kind": a.kind, "startedLocal": L.now_local(),
           "argv": [L.rel(Path(c)) if c.startswith(str(WT)) else c for c in cmd],
           "credentials": "backend/.env exported by tools/s09/run-with-env.cjs into the child environment only",
           "gpuLock": lock.strip(),
           "backend": {"port": 3120, "pid": backend[0], "process": L.process_info(backend[0])},
           "staged": {p.name: L.sha256_file(p) for p in sorted((L.STAGE_ROOT / "Unmatched" / "Content" / "Paks").glob("*"))
                      if p.is_file()}}
    rec["staged"]["Unmatched.exe(inner)"] = L.sha256_file(L.STAGED_INNER_EXE)
    samplers = L.Samplers(work)
    t0 = time.time()
    samplers.start()
    time.sleep(2)
    seen: dict = {}
    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, cwd=str(WT / "backend"),
                            creationflags=L.NO_WINDOW)
    rec["demoPid"] = proc.pid
    chunks: list = []
    th = threading.Thread(target=lambda: [chunks.append(x) for x in iter(proc.stdout.readline, b"")], daemon=True)
    th.start()
    while proc.poll() is None:
        for c in L.find_client_pids(t0):
            if ours(c):
                seen.setdefault(c["pid"], c)
        time.sleep(2)
    th.join(10)
    time.sleep(2)
    samplers.stop()
    stdout = b"".join(chunks).decode("utf-8", errors="replace")
    (work / "demo.stdout.txt").write_text(stdout, encoding="utf-8", newline="\n")
    rec.update(demoExit=proc.returncode, finishedLocal=L.now_local(), durationS=round(time.time() - t0, 1))
    m = re.search(r"published evidence run dir: (.+?) \(pointer", stdout)
    run_dir = Path(m.group(1).strip()) if m else None
    st = re.search(r"staging: (\S+)", stdout)
    rec["staging"] = st.group(1) if st else None
    rec["cleanupLine"] = next((x for x in stdout.splitlines() if x.startswith("cleanup:")), None)
    cl = rec["cleanupLine"] or ""
    rec["roomStatus"] = ("ABORTED" if "status=ABORTED (verified)" in cl else
                         "FINISHED" if "already terminal (FINISHED)" in cl else None)
    codes: set = set()
    sp = Path(rec["staging"]) if rec["staging"] else None
    if sp and sp.is_dir():
        for tp in sp.glob("*.trace.log"):
            codes |= {mm.group(2) for mm in ROOM_CODE.finditer(tp.read_text(encoding="utf-8", errors="replace"))}
    failed = run_dir is None or proc.returncode != 0
    if run_dir is None:
        run_dir = evidence / f"failed-{dt.datetime.now():%Y%m%d-%H%M%S}"
        run_dir.mkdir(parents=True, exist_ok=True)
        if sp and sp.is_dir():
            for tp in sp.glob("*.trace.log"):
                text = tp.read_text(encoding="utf-8", errors="replace")
                for c in codes:
                    text = text.replace(c, "<redacted>")
                (run_dir / tp.name).write_text(text, encoding="utf-8", newline="\n")
    rec["runDir"] = L.rel(run_dir)
    logs_dir = run_dir / "client-logs"
    logs_dir.mkdir(exist_ok=True)
    copied = []
    for f in sorted(L.STAGED_LOGS.glob("Unmatched*.log")) if L.STAGED_LOGS.is_dir() else []:
        if f.stat().st_mtime >= t0 - 1:
            text = f.read_text(encoding="utf-8-sig", errors="replace")
            cc = {mm.group(2) for mm in ROOM_CODE.finditer(text)} | codes
            for c in cc:
                text = text.replace(c, "<redacted>")
            dst = logs_dir / f.name
            dst.write_text(text, encoding="utf-8", newline="\n")
            copied.append({"name": f.name, "bytes": dst.stat().st_size, "sha256": L.sha256_file(dst),
                           "roomCodeRedacted": bool(cc)})
    rec["clientLogs"] = copied
    out_stdout = stdout
    for c in codes:
        out_stdout = out_stdout.replace(c, "<redacted>")
    (run_dir / "demo.stdout.txt").write_text(out_stdout, encoding="utf-8", newline="\n")
    shutil.copy2(samplers.gpu_csv, run_dir / samplers.gpu_csv.name)
    crash = []
    for c in copied:
        for ln in (logs_dir / c["name"]).read_text(encoding="utf-8", errors="replace").splitlines():
            if "Unhandled Exception" in ln or "[Callstack]" in ln or "Fatal error" in ln:
                crash.append(f"{c['name']}: {ln.strip()}")
    rec["crashLines"] = crash[:40]
    rec["clientProcesses"] = list(seen.values())
    gpu = L.parse_gpu_csv(samplers.gpu_csv)
    pmon = L.parse_pmon(samplers.pmon_txt)
    pids = set(seen)
    both = sorted({r["t"] for r in pmon if r["pid"] in pids and
                   sum(1 for q in pmon if q["t"] == r["t"] and q["pid"] in pids) >= 2})
    win = (both[0], both[-1]) if both else None
    in_win = [r for r in gpu if win and win[0] <= r["t"] <= win[1]]
    per_pid = {str(pid): L.stats([r["sm"] for r in pmon if r["pid"] == pid and win and win[0] <= r["t"] <= win[1]])
               for pid in pids}
    perf = {"schema": "unmatched.art004-perf/1", "status": a.perf_note,
            "scope": "текущий ПК разработки (RTX 4090), не целевой ПК D-07", "clientFpsCap": 30,
            "clients": {}, "pmonSmPctPerClientPid": per_pid,
            "gpuTotal": {"window": [win[0].isoformat(), win[1].isoformat()] if win else None,
                         "utilizationPct": L.stats([r["gpu"] for r in in_win]),
                         "memUsedMiB": L.stats([r["memUsedMiB"] for r in in_win])}}
    for side in ("host", "joiner"):
        tp = run_dir / f"{PREFIX[a.kind]}-{side}.trace.log"
        if tp.is_file():
            perf["clients"][side] = L.parse_perf(tp)
    L.write_json(run_dir / "perf.json", perf)
    if failed:
        rec["failure"] = [x for x in stdout.splitlines() if re.search(r"throw|Exception|missing|failed|FAILED|error", x)][:20]
        L.write_json(run_dir / "attempt.json", {"schema": "unmatched.envmaps-p5a-attempt/1",
                     "status": "измерено (прогон не прошёл гейт скрипта; не доказательство)",
                     **{k: rec.get(k) for k in ("label", "kind", "argv", "demoExit", "failure", "cleanupLine", "staged")}})
    L.write_json(run_dir / "run-record.json", rec)
    man = run_dir / "manifest.json"
    if man.is_file() and not failed:
        doc = json.loads(man.read_text(encoding="utf-8-sig"))
        listed = {e["name"].replace("\\", "/") for e in doc["files"]}
        for f in sorted(run_dir.rglob("*")):
            if f.is_file() and f.name != "manifest.json":
                name = f.relative_to(run_dir).as_posix()
                if name not in listed:
                    doc["files"].append({"name": name, "bytes": f.stat().st_size, "sha256": L.sha256_file(f)})
        doc["extendedBy"] = "C:/tmp/envmaps-research/p5a/live/live_run.py (client logs, perf, nvidia-smi, stdout, run-record)"
        man.write_text(json.dumps(doc, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
    left = [c for c in L.find_client_pids(0) if ours(c)]
    print(json.dumps({"label": a.label, "demoExit": proc.returncode, "runDir": rec["runDir"],
                      "roomStatus": rec["roomStatus"], "durationS": rec["durationS"], "crashLines": len(crash),
                      "clientPids": sorted(pids), "clientsStillRunning": left,
                      "gpuPair": perf["gpuTotal"]["utilizationPct"]}, ensure_ascii=False))
    return 0 if not failed else 1


if __name__ == "__main__":
    sys.exit(main())
