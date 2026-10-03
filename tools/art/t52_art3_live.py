#!/usr/bin/env python3
"""HISTORICAL (2026-10-04): kept as the record of stage 3 T5.2; not rebased. Its board set (Cobble City 5x6 and the
ART FIXTURE Sherwood Forest / T. Rex Paddock grids) left the client data and the DB on 2026-10-04 (user decision «Давай
оставим только доски, которые осуществлены на реальных досках из игры.»,
docs/game-design/decisions/2026-10-04-real-boards-only.md), so new runs of `k3` / `analyze` on those boards are refused
by the demo scripts and do not count as evidence (НД-6). New work uses the original maps (Marmoreal, Sarpedon).

Stage 3 T5.2 «Арт 3 живьём»: K3 packaged pairs + QA-010 derivatives on three boards.

Runs in the art worktree against ONE packaged build (the G/P records of
art004_live_k2.py build/package) and the art-worktree backend on :3120.

  k3        One tools/s09/run-combat-demo.ps1 pair (host Medusa attacks, joiner
            King Arthur defends and resolves) on a registered art board, both
            clients at -ClientFps, W4-A render preset High and
            -RequireRenderReference. Demo accounts: S08_DEMO_* from
            backend/.env, passed to the child as S09_DEMO_* in the environment
            only (never argv). Samples nvidia-smi, copies the packaged client
            logs, writes perf.json, validation.json (the check_art003 combat
            rules), a strict sidecar <frame>.evidence.json for every published
            PNG and extends manifest.json. A failed run keeps its traces (room
            code redacted) in <evidence>/failed-<stamp>/ with attempt.json.
  analyze   QA-010 measurements of one board: derive (gray, deuteranopia; full
            size outside git, sha256 in the manifest), luma p50/p90 per light
            section / zone / board, С-9 (qa010 c9; decor = ring proxy), zone
            mark and zone boundary contrast (colour, gray, deuteranopia),
            icon 24/32/48 (qa010 icon --mask, method rev 2, + guard) and plate
            vs reachable (qa010), multizone readability, per-fighter team ring
            visibility, world label / damage number contrast (W5-live3),
            render fingerprint, classify_evidence --strict --render-reference,
            the QA-010 checklist.
  mi        Medusa material identity over every K1/K3 trace of the given dirs
            ('ARTPREVIEW medusa materials ... miSha256='), plus sha256 of the
            MI .uasset sources and of the staged paks.
  icon-template
            W5-live3, icon method rev 2: the bbox-sized icon mask from the
            difference of a K3 frame with the icon and the same view without
            it (Cobble). 'analyze' measures the icon with this explicit mask;
            auto-Otsu stays as superseded diagnostics plus a guard.
  readability-sheets
            W5-live3: crop sheets of the per-fighter team rings and of the
            world labels / damage numbers measured by 'analyze'.

  errata-w5br
            W5b-R errata of the T5.2 checklists (no re-shoot, no re-measure):
            plate-k1-host.json joins the results, the K3 row is split
            (target frame/arcs vs icon), the damage frame is marked as an
            ability's damage (CUE seq before the first COMBAT_RESOLVE, from the
            joiner trace), the Cobble plate under King Arthur and the combat
            panel over the board are noted; the checklists are regenerated.

W5-live3 order: icon-template -> analyze (each board) -> readability-sheets.
W5b-R: errata-w5br (after analyze; 'analyze' applies the same errata itself).

Statuses stay honest: «измерено», never «принято». Thresholds are the ones
registered before the shots (<evidence>/t52-thresholds.json).
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import math
import os
import re
import shutil
import subprocess
import sys
import threading
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE / "qa010"))
import art004_live_k2 as L  # noqa: E402

REPO = L.REPO
QA010 = HERE / "qa010" / "qa010.py"
CLASSIFY = HERE / "classify_evidence.py"
COMBAT = REPO / "tools" / "s09" / "run-combat-demo.ps1"
FIXTURES = REPO / "backend" / "prisma" / "fixtures" / "art-boards"
PROFILES = L.ART_BOARDS
HUD_EXCLUDE = ["hud_tl=bbox:0,0,610,140", "hud_tr=bbox:1425,0,1920,120", "hud_hand=bbox:330,975,1590,1080"]
MEDUSA_MI = ["unreal/Unmatched/Content/ArtPreview/Medusa/Materials/MI_Medusa_Blue.uasset",
             "unreal/Unmatched/Content/ArtPreview/Medusa/Materials/MI_Medusa_Red.uasset",
             "unreal/Unmatched/Content/ArtPreview/Medusa/Materials/M_Medusa_Atlas.uasset"]
PAKS = L.STAGE_ROOT / "Unmatched" / "Content" / "Paks"
ROOM_CODE = re.compile(r"createGame -> room=([A-Za-z0-9_-]+) code=([A-Z0-9-]{4,12})")
CUE = re.compile(r"CUE damage (\S+) -(\d+) seq=(\d+)")
NUMBER = re.compile(r"ARTPREVIEW damage-number fighter=(\S+) amount=(\d+) seq=(\d+)")
RESULT = re.compile(r"COMBAT-RESULT seq=(\d+) damage=(-?\d+)")
MAX_SEQ = re.compile(r"SNAPSHOT applied seq=(\d+)")
MI_LINE = re.compile(r"ARTPREVIEW medusa materials fighter=(\S+) team=(\w+) mesh=(\S+) slots=(\d+) mi=(\S+) "
                     r"slot1=(\S+) base=(\S+) parent=(\S+) params=(\d+) miSha256=([0-9a-f]{64})")


def rel(p: Path) -> str:
    return L.rel(Path(p))


def board_profile(board_id: str) -> dict:
    b = L.registered_art_board(board_id)
    if b is None:
        raise SystemExit(f"REFUSED: {board_id} is not a registered art board")
    return b


# ------------------------------------------------------------------ k3
def combat_validation(run_dir: Path) -> dict:
    """check_art003_combat_evidence rules, without its fixed 8-file count
    (the run manifest is extended with logs/perf/sidecars afterwards)."""
    out = {"schema": "unmatched.t52-combat-validation/1", "rules": "tools/art/check_art003_combat_evidence.py "
           "check_trace (CUE damage == ARTPREVIEW damage-number exactly once, target icon bound and cleared, first "
           "COMBAT-RESULT damage > 0 and equal to its CUE, authoritative seq) + host/joiner convergence",
           "trace": {}, "problems": []}
    for side in ("host", "joiner"):
        tp = run_dir / f"combat-client-{side}.trace.log"
        text = tp.read_text(encoding="utf-8", errors="replace")
        cues: dict = {}
        for f, a, s in CUE.findall(text):
            cues[(f, int(a), int(s))] = cues.get((f, int(a), int(s)), 0) + 1
        nums: dict = {}
        for f, a, s in NUMBER.findall(text):
            nums[(f, int(a), int(s))] = nums.get((f, int(a), int(s)), 0) + 1
        results = [(int(s), int(d)) for s, d in RESULT.findall(text)]
        seqs = [int(s) for s in MAX_SEQ.findall(text)]
        t = {"damage_cues": sum(cues.values()), "unique_damage_numbers": sum(nums.values()),
             "cues_equal_numbers": cues == nums and bool(cues),
             "no_duplicate_number": (max(nums.values()) == 1) if nums else False,
             "target_icon_bound": "target=1 icon=1" in text, "target_icon_cleared": "target=0 icon=0" in text,
             "combat_results": len(results), "max_seq": max(seqs) if seqs else None}
        if results:
            fs, fd = results[0]
            t["first_combat_result"] = {"seq": fs, "damage": fd}
            t["first_result_matches_cue"] = fd > 0 and any(s == fs and a == fd for (_, a, s) in cues)
            # T5.2 note: after a post-reveal BOOST_CHOICE pause the server applies the damage inside
            # COMBAT_RESOLVE (CUE at seq N) and closes the combat one snapshot later (COMBAT-RESULT at N+1).
            t["first_result_matches_cue_prev2"] = fd > 0 and any(fs - 2 <= s <= fs and a == fd
                                                                 for (_, a, s) in cues)
        else:
            t["first_combat_result"] = None
            t["first_result_matches_cue"] = t["first_result_matches_cue_prev2"] = False
        for k in ("cues_equal_numbers", "no_duplicate_number", "target_icon_bound", "target_icon_cleared",
                  "first_result_matches_cue_prev2"):
            if not t[k]:
                out["problems"].append(f"{side}: {k} is false")
        if not t["first_result_matches_cue"] and t["first_result_matches_cue_prev2"]:
            out.setdefault("notes", []).append(
                f"{side}: the strict check_art003 rule (CUE at the SAME seq as the first COMBAT-RESULT) is not met; "
                f"a CUE with the same amount lies within 2 preceding snapshots (damage applied inside "
                f"COMBAT_RESOLVE, result closed on the next snapshot)")
        out["trace"][side] = t
    h, j = out["trace"]["host"], out["trace"]["joiner"]
    out["seqConverged"] = h["max_seq"] is not None and h["max_seq"] == j["max_seq"]
    out["firstResultAgrees"] = h["first_combat_result"] == j["first_combat_result"]
    if not out["seqConverged"]:
        out["problems"].append(f"seq host={h['max_seq']} joiner={j['max_seq']}")
    if not out["firstResultAgrees"]:
        out["problems"].append("clients disagree on the first combat result")
    out["status"] = ("fail" if out["problems"] else "pass_with_note" if out.get("notes")
                     else "pass_technical_evidence_only")
    return out


def cmd_revalidate(a) -> int:
    run_dir = Path(a.run_dir).resolve()
    val = combat_validation(run_dir)
    L.write_json(run_dir / "validation.json", val)
    man = run_dir / "manifest.json"
    doc = json.loads(man.read_text(encoding="utf-8-sig"))
    for e in doc["files"]:
        f = run_dir / e["name"].replace(chr(92), "/")
        if e["name"] in ("validation.json", "run-record.json") and f.is_file():
            e["bytes"], e["sha256"] = f.stat().st_size, L.sha256_file(f)
    man.write_text(json.dumps(doc, ensure_ascii=False, indent=2) + chr(10), encoding="utf-8", newline=chr(10))
    print(json.dumps({"runDir": rel(run_dir), "status": val["status"], "problems": val["problems"],
                      "notes": val.get("notes", [])}, ensure_ascii=False))
    return 0 if val["status"].startswith("pass") else 1


def cmd_k3(a) -> int:
    prof = board_profile(a.board_id)
    evidence = Path(a.evidence_dir).resolve()
    evidence.mkdir(parents=True, exist_ok=True)
    work = Path(a.work).resolve() / f"{a.label}-{dt.datetime.now():%Y%m%d-%H%M%S}"
    work.mkdir(parents=True, exist_ok=True)
    backend = L.listeners(3120)
    if len(backend) != 1:
        print(f"REFUSED: expected exactly one backend listener on :3120, got {backend}")
        return 2
    env = os.environ.copy()
    benv = L.load_backend_env()
    for role in ("HOST", "JOINER"):
        for what in ("EMAIL", "PASSWORD"):
            env[f"S09_DEMO_{role}_{what}"] = benv[f"S08_DEMO_{role}_{what}"]  # environment only, never argv
    cmd = ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(COMBAT),
           "-Api", L.API, "-EvidenceDir", str(evidence), "-ArtPreview", "-FullHd", "-ClientFps", str(a.client_fps),
           "-ArtPreviewBoardId", a.board_id, "-ArtPreviewMedusaVariant", a.variant, "-RunSeconds", str(a.run_seconds),
           "-ClientRenderPreset", "High", "-RequireRenderReference", "-ClientPerf"] + list(a.extra_demo_arg or [])
    record = {"schema": "unmatched.t52-k3-run/1", "label": a.label, "startedLocal": L.now_local(),
              "argv": [c if not c.startswith(str(REPO)) else rel(Path(c)) for c in cmd],
              "credentials": "S08_DEMO_* from backend/.env injected as S09_DEMO_* into the child environment only",
              "backend": {"port": 3120, "pid": backend[0], "process": L.process_info(backend[0])},
              "artBoard": {"boardId": a.board_id, "profile": prof.get("id"),
                           "size": f"{prof['match'].get('width')}x{prof['match'].get('height')}",
                           "light": prof.get("light"), "artFixture": bool(prof.get("artFixture"))},
              "clientFps": a.client_fps, "runSeconds": a.run_seconds, "variant": a.variant,
              "staged": {p.name: L.sha256_file(p) for p in sorted(PAKS.glob("*")) if p.is_file()}}
    record["staged"]["Unmatched.exe(inner)"] = L.sha256_file(L.STAGED_INNER_EXE)
    samplers = L.Samplers(work)
    t_start = time.time()
    samplers.start()
    time.sleep(2)
    seen: dict = {}
    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, env=env, cwd=str(REPO),
                            creationflags=L.NO_WINDOW)
    chunks: list = []
    th = threading.Thread(target=lambda: [chunks.append(x) for x in iter(proc.stdout.readline, b"")], daemon=True)
    th.start()
    while proc.poll() is None:
        for c in L.find_client_pids(t_start):
            seen.setdefault(c["pid"], c)
        time.sleep(2)
    th.join(10)
    time.sleep(2)
    samplers.stop()
    stdout = b"".join(chunks).decode("utf-8", errors="replace")
    (work / "demo.stdout.txt").write_text(stdout, encoding="utf-8", newline="\n")
    record.update(demoExit=proc.returncode, finishedLocal=L.now_local(), durationS=round(time.time() - t_start, 1))
    m = re.search(r"published evidence run dir: (.+?) \(pointer", stdout)
    run_dir = Path(m.group(1).strip()) if m else None
    staging = re.search(r"staging: (\S+)", stdout)
    record["staging"] = staging.group(1) if staging else None
    record["cleanupLine"] = next((x for x in stdout.splitlines() if x.startswith("cleanup:")), None)
    record["roomStatus"] = ("ABORTED" if record["cleanupLine"] and "status=ABORTED (verified)" in record["cleanupLine"]
                            else "FINISHED" if record["cleanupLine"] and "already terminal (FINISHED)" in record["cleanupLine"]
                            else None)
    failed = run_dir is None
    if failed:
        run_dir = evidence / f"failed-{dt.datetime.now():%Y%m%d-%H%M%S}"
        run_dir.mkdir(parents=True, exist_ok=True)
        st = Path(record["staging"]) if record["staging"] else None
        code = None
        if st and st.is_dir():
            for tp in st.glob("*.trace.log"):
                mm = ROOM_CODE.search(tp.read_text(encoding="utf-8", errors="replace"))
                if mm:
                    code = mm.group(2)
            for tp in st.glob("*.trace.log"):
                text = tp.read_text(encoding="utf-8", errors="replace")
                if code:
                    text = text.replace(code, "<redacted>")
                (run_dir / tp.name).write_text(text, encoding="utf-8", newline="\n")
        record["failedTracesRoomCodeRedacted"] = bool(code)
    record["runDir"] = rel(run_dir)
    logs_dir = run_dir / "client-logs"
    logs_dir.mkdir(exist_ok=True)
    copied = []
    for f in sorted(L.STAGED_LOGS.glob("Unmatched*.log")) if L.STAGED_LOGS.is_dir() else []:
        if f.stat().st_mtime >= t_start - 1:
            text = f.read_text(encoding="utf-8-sig", errors="replace")
            codes = {mm.group(2) for mm in ROOM_CODE.finditer(text)}
            for c in codes:  # the published traces carry <redacted>; keep the logs consistent
                text = text.replace(c, "<redacted>")
            dst = logs_dir / f.name
            dst.write_text(text, encoding="utf-8", newline="\n")
            copied.append({"name": f.name, "bytes": dst.stat().st_size, "sha256": L.sha256_file(dst),
                           "roomCodeRedacted": bool(codes)})
    record["clientLogs"] = copied
    shutil.copy2(work / "demo.stdout.txt", run_dir / "demo.stdout.txt")
    shutil.copy2(samplers.gpu_csv, run_dir / samplers.gpu_csv.name)
    raw_dir = L.RAW_ROOT / f"t52-{run_dir.name}"
    raw_dir.mkdir(parents=True, exist_ok=True)
    shutil.copy2(samplers.pmon_txt, raw_dir / samplers.pmon_txt.name)
    record["rawOutsideGit"] = [{"path": rel(raw_dir / samplers.pmon_txt.name),
                                "sha256": L.sha256_file(raw_dir / samplers.pmon_txt.name)}]
    crash = []
    for c in copied:
        for ln in (logs_dir / c["name"]).read_text(encoding="utf-8", errors="replace").splitlines():
            if "Unhandled Exception" in ln or "[Callstack]" in ln or "Fatal error" in ln:
                crash.append(f"{c['name']}: {ln.strip()}")
    record["crashLines"] = crash[:40]
    record["clientProcesses"] = list(seen.values())
    # perf (contaminated by the H2 background line: recorded, not evaluated)
    gpu = L.parse_gpu_csv(samplers.gpu_csv)
    pmon = L.parse_pmon(samplers.pmon_txt)
    pids = {c["pid"] for c in seen.values()}
    both = sorted({r["t"] for r in pmon if r["pid"] in pids and
                   sum(1 for q in pmon if q["t"] == r["t"] and q["pid"] in pids) >= 2})
    win = (both[0], both[-1]) if both else None
    in_win = [r for r in gpu if win and win[0] <= r["t"] <= win[1]]
    perf = {"schema": "unmatched.art004-perf/1",
            "status": getattr(a, "perf_status", None) or
                      "измерено; ЗАГРЯЗНЕНО фоном H2 (headless Blender/Cycles параллельной линии героев) — не для ACC-022",
            "scope": "текущий ПК разработки (RTX 4090), не целевой ПК D-07",
            "concurrentGpuUsers": getattr(a, "concurrent_gpu_users", None),
            "clientFpsCap": a.client_fps, "clients": {},
            "gpuTotal": {"window": [win[0].isoformat(), win[1].isoformat()] if win else None,
                         "utilizationPct": L.stats([r["gpu"] for r in in_win]),
                         "memUsedMiB": L.stats([r["memUsedMiB"] for r in in_win])}}
    for side in ("host", "joiner"):
        tp = run_dir / f"combat-client-{side}.trace.log"
        if tp.is_file():
            perf["clients"][side] = L.parse_perf(tp)
    L.write_json(run_dir / "perf.json", perf)
    if not failed:
        val = combat_validation(run_dir)
        L.write_json(run_dir / "validation.json", val)
        record["validation"] = {"status": val["status"], "problems": val["problems"]}
        build = json.loads(Path(a.build_record).read_text(encoding="utf-8"))
        pkg = json.loads(Path(a.package_record).read_text(encoding="utf-8"))
        for png in sorted(run_dir.rglob("*.png")):
            side = {"schema": L.SIDECAR_SCHEMA, "class": "packaged-live",
                    "frame": png.relative_to(run_dir).as_posix(), "frameSha256": L.sha256_file(png),
                    "build": {"label": build.get("label"), "result": build.get("result"), "flags": build.get("flags"),
                              "log": build.get("log"), "withLiveCoding": build.get("withLiveCodingValues"),
                              "exeSha256": (pkg.get("exe") or {}).get("binariesSha256"),
                              "stagedInnerExeSha256": (pkg.get("exe") or {}).get("stagedInnerSha256"),
                              "buildRecord": rel(Path(a.build_record)), "packageRecord": rel(Path(a.package_record))},
                    "run": {"boardId": a.board_id, "roomStatus": record["roomStatus"], "variantFlag": a.variant,
                            "zoom": 0, "runSeconds": a.run_seconds, "clientFps": a.client_fps,
                            "cleanupLine": record["cleanupLine"], "demo": "tools/s09/run-combat-demo.ps1"},
                    "status": "измерено (боевой кадр K3 с HUD и boardState; художественная приёмка не выполнялась)"}
            L.write_json(png.with_name(png.stem + ".evidence.json"), side)
        L.write_json(run_dir / "run-record.json", record)  # listed in the manifest below
        man = run_dir / "manifest.json"
        doc = json.loads(man.read_text(encoding="utf-8-sig"))
        listed = {e["name"].replace("\\", "/") for e in doc["files"]}
        for f in sorted(run_dir.rglob("*")):
            if f.is_file() and f.name != "manifest.json":
                name = f.relative_to(run_dir).as_posix()
                if name not in listed:
                    doc["files"].append({"name": name, "bytes": f.stat().st_size, "sha256": L.sha256_file(f)})
        doc["extendedBy"] = "tools/art/t52_art3_live.py k3 (client logs, perf, validation, sidecars, nvidia-smi, stdout)"
        man.write_text(json.dumps(doc, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
    else:
        fail_lines = [x for x in stdout.splitlines() if re.search(r"throw|Exception|missing|failed|FAILED", x)]
        record["failure"] = fail_lines[:12]
        L.write_json(run_dir / "attempt.json", {"schema": "unmatched.t52-combat-attempt/1",
                                                "status": "измерено (прогон не прошёл гейт боя; не K3-доказательство)",
                                                **{k: record[k] for k in ("label", "argv", "demoExit", "failure",
                                                                         "cleanupLine", "artBoard", "staged")}})
    L.write_json(run_dir / "run-record.json", record)
    print(json.dumps({"label": a.label, "demoExit": proc.returncode, "runDir": record["runDir"],
                      "roomStatus": record["roomStatus"], "validation": record.get("validation"),
                      "crashLines": len(crash)}, ensure_ascii=False))
    for x in [x for x in stdout.splitlines() if re.search(r"throw|Exception|FAILED|missing|WARN|render fingerprint|markers", x)][:12]:
        print("  |", x[:300])
    return 0 if (proc.returncode == 0 and not failed and record["validation"]["status"].startswith("pass")) else 1


# ------------------------------------------------------------------ analyze
BOARDS = {
    "sherwood-forest-8x5": {"boardId": "c37a3b6643a96c45fa71f10de", "fixture": "sherwood-forest.art-fixture.json"},
    "t-rex-paddock-7x5": {"boardId": "c70e9f624617750c2a2b856fd", "fixture": "t-rex-paddock.art-fixture.json"},
    "cobble-5x6": {"boardId": "cmuhgs4b2001mwik4f2b2xtf8", "dbExport": "analysis/cobble-board-cells.json"},
}
K3_ORDER = ["s09-combat-resolve-revealed.png", "s09-combat-resolve-window.png", "s09-combat-defense-open.png",
            "s09-damage-number.png"]
# T5.2 finding: on s09-combat-result.png the trace still writes 'SHOT icon ... geom=painted' and
# 'SHOT widget id=icon ... visible=1', but the icon is NOT in the pixels (combat closed; checked on
# all six result frames, analysis/k3-icon-bbox-crops.png). That frame is never the icon K3 frame.
# W5-live3 extension (icon method rev 2): even on a frame where the icon IS drawn, qa010's auto-Otsu mask is
# not trusted. On light fixture tiles it picks the DARK class (brown hilts + the pedestal of the fighter behind
# the target, which sits inside the bbox) and reported 2.66-3.16:1 instead of ~1.1:1. The icon is measured
# with an explicit mask (icon-template), and icon-k3-guard.json checks (a) the icon is in the pixels
# (difference against the same view without the icon), (b) the auto mask against the template, (c) the share
# of non-tile pixels (pedestal, ring) in the bbox background.
K3_ICON_STALE = {"s09-combat-result.png"}


def qa(args: list[str], json_out: Path) -> tuple[int, dict | None]:
    """Run qa010.py (read-only on inputs) and return (exit code, parsed JSON)."""
    json_out.parent.mkdir(parents=True, exist_ok=True)

    def repo_rel(s: str) -> str:
        # evidence JSON keeps repository-relative paths (qa010 records the paths it is given)
        p = Path(s)
        if p.is_absolute():
            try:
                return p.resolve().relative_to(REPO).as_posix()
            except ValueError:
                return s
        return s
    r = subprocess.run([sys.executable, str(QA010)] + [repo_rel(x) for x in args] + ["--json", repo_rel(str(json_out))],
                       capture_output=True, text=True, encoding="utf-8", errors="replace", cwd=str(REPO),
                       creationflags=L.NO_WINDOW)
    doc = json.loads(json_out.read_text(encoding="utf-8")) if json_out.is_file() else None
    if doc is None:
        print("  qa010 failed:", " ".join(args[:3]), r.stderr[-400:])
    return r.returncode, doc


def board_cells(evidence: Path, key: str) -> list[dict]:
    spec = BOARDS[key]
    if "fixture" in spec:
        doc = json.loads((FIXTURES / spec["fixture"]).read_text(encoding="utf-8"))
        return [{"x": c["x"], "y": c["y"], "zones": list(c.get("zones") or []),
                 "obstacle": bool(c.get("isObstacle"))} for c in doc["cells"]]
    doc = json.loads((evidence / spec["dbExport"]).read_text(encoding="utf-8"))
    return [{"x": c["x"], "y": c["y"], "zones": list(c.get("zones") or ([c["zone"]] if c.get("zone") else [])),
             "obstacle": bool(c.get("isObstacle"))} for c in doc["board"]["cells"]]


def light_sections(prof: dict, light: dict, cells: list[dict]) -> dict:
    """art_board_fixtures.light_sections_vs_zones rule: cells whose centre is within half the
    attenuation radius of a non-fill point light (INT-019 cell centres)."""
    w, h = prof["match"]["width"], prof["match"]["height"]
    out = {}
    for p in light.get("points", []):
        if p.get("role") == "fill":
            continue
        if "at" in p:
            lx, ly = p["at"][0] * w * 100.0, p["at"][1] * h * 100.0
        else:
            lx, ly = p["posUU"][0], p["posUU"][1]
        sec = [(c["x"], c["y"]) for c in cells if not c["obstacle"] and
               math.dist(((c["x"] - (w - 1) / 2.0) * 100.0, (c["y"] - (h - 1) / 2.0) * 100.0), (lx, ly))
               <= 0.5 * p["radiusUU"]]
        out[p["name"]] = {"role": p.get("role"), "cells": sec}
    return out


class Frame:
    def __init__(self, png: Path, trace: Path):
        import numpy as np
        from qa010lib import color as C
        from qa010lib.imageio import load_rgb
        from qa010lib.projection import build_projection, cell_world_quad, project_polygon
        from qa010lib.trace import parse_trace
        self.png, self.trace_path = png, trace
        self.rgb = load_rgb(png)
        self.h, self.w = self.rgb.shape[:2]
        tr = parse_trace(trace)
        self.shot = tr.find_shot(None, png.name)
        self.board = self.shot.board or tr.board
        self.proj = build_projection(self.shot, 35.0, 2.0, "auto")
        cam = self.proj.camera
        self.quads = {}
        for y in range(self.board.height):
            for x in range(self.board.width):
                q = project_polygon(cam, cell_world_quad(self.board, x, y))
                if q is not None:
                    self.quads[(x, y)] = q
        self.occupied = {tuple(f.cell) for f in self.shot.fighters if f.alive}
        self.variants = {"color": self.rgb, "gray": C.grayscale(self.rgb), "deuteranopia": C.deuteranopia(self.rgb)}
        self.lab = {k: C.linear_to_lab(C.u8_to_linear(v)) for k, v in self.variants.items()}
        self.np = np

    def mask(self, cells) -> "object":
        from qa010lib.regions import _poly_mask
        polys = [self.quads[c] for c in cells if c in self.quads]
        return _poly_mask((self.w, self.h), polys) if polys else self.np.zeros((self.h, self.w), dtype=bool)


def _stats(v, m, C, np) -> dict | None:
    px = v[m]
    if px.shape[0] == 0:
        return None
    med = np.median(px.reshape(-1, 3), axis=0)
    rl = C.relative_luminance(px)
    return {"pixels": int(px.shape[0]), "medianRgb": [round(float(x), 1) for x in med],
            "medianRelLum": round(float(np.median(rl)), 5), "medianLuma": round(float(np.median(C.luma_u8(px))), 2),
            "lab": [round(float(x), 2) for x in C.linear_to_lab(C.u8_to_linear(np.floor(med + 0.5).astype(np.uint8)))]}


DIAG_MARK_DELTA_E = 25.0  # diagnostic tolerance (not registered): tonemapped game-layer colours
TILE_HALF_UU = 18.0  # central square of a cell: glyph slots sit at (+-32, +-32) uu, strokes at the edges


def zone_metrics(fr: Frame, cells: list[dict], styles: dict, th: dict) -> dict:
    """Zone marks vs the tile they sit on, in colour / gray / deuteranopia, and the zone boundary pairs.

    Geometry (S08BoardArt.cpp): glyphs in the corner slots (+-32, +-32) uu, strokes along the cell
    sides, so the central +-18 uu square of a cell carries no mark: it is the tile reference. Mark
    pixels = pixels of the zone's free cells OUTSIDE that square whose CIELAB distance to the zone
    colour (profile hex; the game layer is unlit + EyeAdaptationInverse) is <= markDeltaE and whose
    distance to the tile median is > markDeltaE. When the tile median itself lies within
    markDeltaE of the zone colour, the mark cannot be told from the tile by colour: reported as a
    colour clash, the contrast is the one of the zone colour against the tile median."""
    import numpy as np
    from qa010lib import color as C
    from qa010lib.projection import cell_world_quad, project_polygon
    from qa010lib.regions import _poly_mask
    zm = th["zoneMarks"]
    keys = sorted({z for c in cells for z in c["zones"]})
    passable = {(c["x"], c["y"]): c for c in cells if not c["obstacle"]}
    cam = fr.proj.camera

    def centre_mask(cl):
        polys = []
        for (x, y) in cl:
            q = project_polygon(cam, cell_world_quad(fr.board, x, y, cell_size=2 * TILE_HALF_UU))
            if q is not None:
                polys.append(q)
        return _poly_mask((fr.w, fr.h), polys) if polys else np.zeros((fr.h, fr.w), dtype=bool)

    def hex_rgb(hexc):
        return np.array([int(hexc[i:i + 2], 16) for i in (1, 3, 5)], dtype=np.uint8)

    variant_fn = {"color": lambda a: a, "gray": C.grayscale, "deuteranopia": C.deuteranopia}
    zones = {}
    for k in keys:
        hexc = styles[k]["color"]
        target_rgb = hex_rgb(hexc)
        target = C.linear_to_lab(C.u8_to_linear(target_rgb))
        zc = [p for p, c in passable.items() if k in c["zones"]]
        free = [p for p in zc if p not in fr.occupied] or zc
        cm = fr.mask(free)
        centre = centre_mask(free) & cm
        tile_lab = np.median(fr.lab["color"][centre].reshape(-1, 3), axis=0) if centre.any() else None
        d_tile_target = float(np.linalg.norm(tile_lab - target)) if tile_lab is not None else None
        clash = d_tile_target is not None and d_tile_target <= zm["markDeltaE"]
        ring = cm & ~centre
        mark = ring & (np.linalg.norm(fr.lab["color"] - target, axis=-1) <= zm["markDeltaE"])
        if tile_lab is not None:
            mark &= np.linalg.norm(fr.lab["color"] - tile_lab, axis=-1) > zm["markDeltaE"]
        per_cell = [int((fr.mask([p]) & mark).sum()) for p in free]
        z = {"cells": len(zc), "freeCellsUsed": len(free), "hex": hexc, "stroke": styles[k].get("stroke"),
             "glyph": styles[k].get("glyph"),
             "tileVsZoneColourDE76": round(d_tile_target, 2) if d_tile_target is not None else None,
             "colourClashWithTile": bool(clash), "markPixels": int(mark.sum()),
             "markPixelsPerCellMedian": float(np.median(per_cell)) if per_cell else 0.0,
             "markPixelsPerCellMin": int(min(per_cell)) if per_cell else 0, "variants": {}}
        z["visible"] = bool((not clash) and z["markPixelsPerCellMedian"] >= zm["minMarkPixelsPerZoneCell"])
        for vn, img in fr.variants.items():
            ts = _stats(img, centre, C, np)
            if clash or not mark.any():
                # the zone colour as the unlit game layer draws it, in this variant, against the tile median
                trgb = variant_fn[vn](target_rgb.reshape(1, 1, 3)).reshape(1, 3)
                ms = {"pixels": 0, "source": "profile hex (mark not separable from the tile by colour)",
                      "medianRgb": [float(x) for x in trgb[0]],
                      "medianRelLum": round(float(C.relative_luminance(trgb)[0]), 5),
                      "medianLuma": round(float(C.luma_u8(trgb)[0]), 2),
                      "lab": [round(float(x), 2) for x in C.linear_to_lab(C.u8_to_linear(trgb))[0]]}
            else:
                ms = _stats(img, mark, C, np)
            if not ts:
                z["variants"][vn] = {"mark": ms, "tile": None, "wcag": None, "pass": False}
                continue
            wc = float(C.wcag_contrast_ratio(ms["medianRelLum"], ts["medianRelLum"]))
            z["variants"][vn] = {"mark": ms, "tile": ts, "wcag": round(wc, 3),
                                 "dLuma": round(ms["medianLuma"] - ts["medianLuma"], 2),
                                 "dE76": round(float(np.linalg.norm(np.array(ms["lab"]) - np.array(ts["lab"]))), 2),
                                 "pass": bool(wc >= zm["markVsTileMinContrast"] and z["visible"])}
        zones[k] = z
    zb = th["zoneBoundaries"]
    pairs: dict = {}
    for (x, y), c in passable.items():
        for dx, dy in ((1, 0), (0, 1)):
            n = passable.get((x + dx, y + dy))
            if not n:
                continue
            a, b = set(c["zones"]), set(n["zones"])
            for za in a - b:
                for zb_ in b - a:
                    key = tuple(sorted((za, zb_)))
                    pairs[key] = pairs.get(key, 0) + 1
    out_pairs = []
    for (za, zb_), edges in sorted(pairs.items()):
        A, B = zones[za], zones[zb_]
        shape = A["stroke"] != B["stroke"] or A["glyph"] != B["glyph"]
        rec = {"pair": [za, zb_], "edges": edges, "shapeDiffers": shape,
               "strokes": [A["stroke"], B["stroke"]], "glyphs": [A["glyph"], B["glyph"]], "variants": {}}
        for vn in fr.variants:
            va, vb = A["variants"][vn], B["variants"][vn]
            de = float(np.linalg.norm(np.array(va["mark"]["lab"]) - np.array(vb["mark"]["lab"])))
            dy = abs(va["mark"]["medianLuma"] - vb["mark"]["medianLuma"])
            if vn == "gray":
                by_color, rule = dy >= zb["grayMinDeltaY"], f"|dY'| >= {zb['grayMinDeltaY']}"
            elif vn == "deuteranopia":
                by_color, rule = de >= zb["deutMinDeltaE76"], f"dE76 >= {zb['deutMinDeltaE76']}"
            else:
                by_color, rule = de >= zb["colorMinDeltaE76"], f"dE76 >= {zb['colorMinDeltaE76']}"
            readable = bool(va["pass"] and vb["pass"])
            if not readable:
                verdict = "fail"
                why = "метка не читается на плитке: " + ", ".join(
                    f"{z_} {zones[z_]['variants'][vn]['wcag']}:1"
                    + (" (цвет = плитка)" if zones[z_]["colourClashWithTile"] else "")
                    for z_ in (za, zb_) if not zones[z_]["variants"][vn]["pass"])
            elif by_color:
                verdict, why = "pass", f"различимы цветом/яркостью ({rule})" + (" и формой" if shape else "")
            elif shape:
                verdict, why = "pass: только формой", f"цвет/яркость ниже порога ({rule}), форма различается"
            else:
                verdict, why = "fail", "одинаковая форма и цвет/яркость ниже порога"
            rec["variants"][vn] = {"dE76": round(de, 2), "dLuma": round(dy, 2), "byColor": bool(by_color),
                                   "readable": readable, "verdict": verdict, "why": why}
        out_pairs.append(rec)
    return {"zones": zones, "boundaries": out_pairs, "tileHalfUU": TILE_HALF_UU}


def luma_sections(fr: Frame, cells: list[dict], sections: dict) -> dict:
    from qa010lib.regions import luma_stats
    passable = [(c["x"], c["y"]) for c in cells if not c["obstacle"]]
    regions = {"board(all cells)": [(c["x"], c["y"]) for c in cells], "passable": passable}
    for name, s in sections.items():
        regions[f"section:{name} ({s['role']})"] = s["cells"]
    for k in sorted({z for c in cells for z in c["zones"]}):
        regions[f"zone:{k}"] = [(c["x"], c["y"]) for c in cells if k in c["zones"] and not c["obstacle"]]
    out = {}
    for name, cl in regions.items():
        m = fr.mask(cl)
        entry = {"cells": len(cl)}
        for vn in ("color", "deuteranopia"):
            st = luma_stats(fr.variants[vn], m)
            entry[vn] = {k: st.get(k) for k in ("pixels", "luma_p50", "luma_p90", "luma_mean", "dark_under_30_pct")}
        out[name] = entry
    return out


def cmd_analyze(a) -> int:
    evidence = Path(a.evidence).resolve()
    th = json.loads((evidence / "t52-thresholds.json").read_text(encoding="utf-8"))
    prof_doc = json.loads(PROFILES.read_text(encoding="utf-8"))
    key = a.board
    spec = BOARDS[key]
    prof = board_profile(spec["boardId"])
    styles = prof_doc["zoneStyles"]
    light = prof_doc["lightProfiles"][prof["light"]]
    cells = board_cells(evidence, key)
    out = evidence / "analysis" / key
    out.mkdir(parents=True, exist_ok=True)
    k1 = Path(a.k1_run).resolve()
    k3 = Path(a.k3_run).resolve()
    k1_host, k1_join = k1 / "phase2-board-host-1920x1080.png", k1 / "phase2-board-joiner-1920x1080.png"
    k1_host_t, k1_join_t = k1 / "phase2-client-host.trace.log", k1 / "phase2-client-joiner.trace.log"
    k3_join_t = k3 / "combat-client-joiner.trace.log"
    from qa010lib.trace import parse_trace
    jt = parse_trace(k3_join_t)

    def block(name):
        hits = [s for s in jt.shots if s.name == name]
        return hits[-1] if hits else None
    published = [n for n in K3_ORDER if (k3 / "joiner" / n).is_file()]
    both = [n for n in published if block(n) and block(n).icon and "SHOT damage" in _block_text(k3_join_t, n)]
    icon_frames = [n for n in published if block(n) and block(n).icon]
    k3_main = (icon_frames or published)[0]
    k3_damage = "s09-damage-number.png" if (k3 / "joiner" / "s09-damage-number.png").is_file() else None
    k3_png = k3 / "joiner" / k3_main
    summary = {"schema": "unmatched.t52-analysis/1", "board": key, "boardId": spec["boardId"],
               "profile": prof["id"], "light": prof["light"], "status": "измерено (не приёмка)",
               "thresholds": rel(evidence / "t52-thresholds.json"),
               "frames": {"K1_host": rel(k1_host), "K1_joiner": rel(k1_join), "K3": rel(k3_png),
                          "K3_damage": rel(k3 / "joiner" / k3_damage) if k3_damage else None},
               "k3Choice": {"rule": "первый опубликованный кадр присоединившегося из " + ", ".join(K3_ORDER) +
                            ", в SHOT-блоке которого есть 'SHOT icon'. s09-combat-result.png исключён: трасса пишет "
                            "иконку видимой, а в пикселях её нет (устаревшая трасса после закрытия боя, T5.2)",
                            "excluded": sorted(K3_ICON_STALE), "withIconAndDamage": both, "withIcon": icon_frames}}
    # derive (full size outside git; manifest with sha256 in git)
    derived = Path(a.derived_root) / key
    frames_all = [k1_host, k1_join, k3_png] + ([k3 / "joiner" / k3_damage] if k3_damage else [])
    rc, dm = qa(["derive"] + [str(f) for f in frames_all] + ["--out", str(derived)], out / "derive-manifest.json")
    summary["derive"] = {"exit": rc, "entries": len((dm or {}).get("entries", [])), "outputsOutsideGit": str(derived)}
    # compact contact sheet in git: colour | gray | deuteranopia for K1 (joiner) and K3, 640x360 tiles
    from PIL import Image
    ents = {Path(e["input"]).as_posix(): e for e in (dm or {}).get("entries", [])}
    rows_ = [(rel(k1_join), "K1 joiner"), (rel(k3_png), "K3 " + k3_png.name)]
    sheet = Image.new("RGB", (640 * 3, 360 * len(rows_)), (0, 0, 0))
    for ri, (rp, _label) in enumerate(rows_):
        e = ents.get(rp)
        srcs = [REPO / rp] + ([Path(e["gray"]["path"]), Path(e["deuteranopia"]["path"])] if e else [])
        for ci, sp in enumerate(srcs):
            with Image.open(sp) as im:
                sheet.paste(im.convert("RGB").resize((640, 360), Image.LANCZOS), (640 * ci, 360 * ri))
    sheet_p = out / "contact-k1-k3-color-gray-deuteranopia.jpg"
    sheet.save(sheet_p, quality=85)
    summary["contactSheet"] = {"path": rel(sheet_p), "layout": "rows: K1 joiner, K3; columns: colour, gray, deuteranopia; "
                               "640x360 tiles (downscaled, LANCZOS); full-size derivatives outside git"}
    # render fingerprint per frame
    summary["render"] = {}
    for png, tr in ((k1_host, k1_host_t), (k1_join, k1_join_t), (k3_png, k3_join_t)):
        rc, doc = qa(["render", "--trace", str(tr), "--frame", str(png)], out / f"render-{png.parent.name}-{png.stem}.json")
        summary["render"][png.name if png.parent != k3 / "joiner" else "K3:" + png.name] = {
            "exit": rc, "reference": (doc or {}).get("reference")}
    # luma (qa010, frame level for the checklist)
    qa(["luma", str(k1_host), str(k3_png)], out / "luma-frames.json")
    # C-9 on K1 (host + joiner), decor = ring proxy
    passable = ";".join(f"{c['x']},{c['y']}" for c in cells if not c["obstacle"])
    summary["c9"] = {}
    for png, tr, tag in ((k1_host, k1_host_t, "k1-host"), (k1_join, k1_join_t, "k1-joiner"), (k3_png, k3_join_t, "k3")):
        for gname, gspec in (("all", "board=trace-cells:all"), ("passable", f"passable=trace-cells:{passable}")):
            args = ["c9", str(png), "--trace", str(tr), "--game", gspec, "--decor", th["c9"]["decor"].split(" ")[0]]
            for ex in HUD_EXCLUDE:
                args += ["--exclude", ex]
            rc, doc = qa(args, out / f"c9-{tag}-{gname}.json")
            d = doc or {}
            summary["c9"][f"{tag}/{gname}"] = {
                "exit": rc, "status": d.get("status"), "result_normative": d.get("result_normative"),
                "result_on_proxy": d.get("result_on_proxy"), "dEV": (d.get("delta_ev") or {}).get("used"),
                "dChroma": ((d.get("verdicts") or {}).get("more_saturated") or {}).get("value")}
    # icon on K3 (the SHOT icon bbox of the K3 block), method rev 2: explicit icon mask + guard
    summary["icon"] = measure_icon(evidence, out, k3, k3_main, k3_join_t)
    # plate vs reachable (K1 host, new traces)
    rc, doc = qa(["plate", "--trace", str(k1_host_t), "--shot", k1_host.name, "--frame", str(k1_host)],
                 out / "plate-k1-host.json")
    d = doc or {}
    summary["plate"] = {"exit": rc, "status": d.get("status"), "result": d.get("result"),
                        "checkedCells": (d.get("checked_cells") or {}).get("count"),
                        "violations": len(d.get("violations") or []), "reason": d.get("reason")}
    # zone marks / boundaries / luma sections (joiner K1 = no selection overlay; host K1 for comparison)
    sections = light_sections(prof, light, cells)
    zones = {}
    lumas = {}
    for png, tr, tag in ((k1_join, k1_join_t, "K1_joiner"), (k1_host, k1_host_t, "K1_host"), (k3_png, k3_join_t, "K3")):
        fr = Frame(png, tr)
        if not fr.proj.ok:
            zones[tag] = {"error": f"projection not validated: {fr.proj.reason}"}
            continue
        zones[tag] = {"projection": fr.proj.to_dict(), "occupied": sorted(fr.occupied), **zone_metrics(fr, cells, styles, th)}
        # Diagnostic only, NOT the registered method: the game layer passes the tonemapper, so the drawn
        # colour of some zones lies farther than markDeltaE from the profile hex (e.g. Cobble blue).
        th_diag = json.loads(json.dumps(th))
        th_diag["zoneMarks"]["markDeltaE"] = DIAG_MARK_DELTA_E
        diag = zone_metrics(fr, cells, styles, th_diag)
        zones[tag]["diagnosticMarkDeltaE25"] = {"status": "диагностика вне зарегистрированного метода (T5.2 после съёмки)",
                                                "markDeltaE": DIAG_MARK_DELTA_E, **diag}
        lumas[tag] = luma_sections(fr, cells, sections)
    L.write_json(out / "zone-contrast.json", {"schema": "unmatched.t52-zone-contrast/1", "status": "измерено",
                                              "thresholds": th["zoneMarks"] | {"boundaries": th["zoneBoundaries"]},
                                              "frames": zones})
    L.write_json(out / "luma-sections.json", {"schema": "unmatched.t52-luma-sections/1", "status": "измерено (порога нет)",
                                              "method": th["lumaSections"]["method"],
                                              "sections": {k: v["cells"] for k, v in sections.items()}, "frames": lumas})
    zj = zones.get("K1_joiner", {})
    summary["zoneMarks"] = {k: {"visible": v["visible"], "perCellMedian": v["markPixelsPerCellMedian"],
                                **{vn: v["variants"][vn].get("wcag") for vn in ("color", "gray", "deuteranopia")}}
                            for k, v in (zj.get("zones") or {}).items()}
    summary["boundaries"] = [{"pair": "/".join(b["pair"]), "edges": b["edges"], "shapeDiffers": b["shapeDiffers"],
                              **{vn: b["variants"][vn]["verdict"] for vn in b["variants"]}}
                             for b in zj.get("boundaries", [])]
    zd = zj.get("diagnosticMarkDeltaE25") or {}
    summary["zoneMarksDiagDE25"] = {k: {"visible": v["visible"], "perCellMedian": v["markPixelsPerCellMedian"],
                                        **{vn: v["variants"][vn].get("wcag") for vn in ("color", "gray", "deuteranopia")}}
                                    for k, v in (zd.get("zones") or {}).items()}
    summary["boundariesDiagDE25"] = [{"pair": "/".join(b["pair"]), **{vn: b["variants"][vn]["verdict"] for vn in b["variants"]}}
                                     for b in zd.get("boundaries", [])]
    # W5-live3: multizone readability (the trace zonesListed = zonesMarked proves geometry, not readability)
    summary["multizone"] = multizone_readability(cells, zj.get("zones") or {})
    # W5-live3: team rings and world labels / damage numbers, measured on the same frames
    k1_run_frames = [("K1_host", k1_host, k1_host_t, "host"), ("K1_joiner", k1_join, k1_join_t, "joiner"),
                     ("K3", k3_png, k3_join_t, "joiner")]
    rings = {"schema": "unmatched.t52-team-rings/1", "status": "измерено (W5-live3, после съёмки)",
             "method": RING_METHOD, "frames": {}}
    for tag, png, tr, client in k1_run_frames:
        rings["frames"][tag] = ring_metrics(png, tr, client)
    L.write_json(out / "team-rings.json", rings)
    summary["rings"] = {tag: [{k: r[k] for k in ("fighter", "name", "cell", "team", "fraction", "visible")}
                              for r in fr_["fighters"]] for tag, fr_ in rings["frames"].items()}
    label_frames = k1_run_frames + ([("K3_damage", k3 / "joiner" / k3_damage, k3_join_t, "joiner")] if k3_damage else [])
    labels = {"schema": "unmatched.t52-labels-damage/1", "status": "измерено (W5-live3, после съёмки)",
              "method": LABEL_METHOD, "frames": {}}
    for tag, png, tr, _client in label_frames:
        labels["frames"][tag] = label_metrics(png, tr)
    L.write_json(out / "labels-damage.json", labels)
    summary["labels"] = {tag: [{k: r[k] for k in ("kind", "fighter", "name", "verdict", "crHp", "crName", "tileEdgeCrosses")
                                if k in r} for r in fr_["items"]] for tag, fr_ in labels["frames"].items()}
    # classify (strict + render reference)
    cl = subprocess.run([sys.executable, str(CLASSIFY), str(k1_host), str(k1_join), str(k3_png)] +
                        ([str(k3 / "joiner" / k3_damage)] if k3_damage else []) + ["--strict", "--render-reference"],
                        capture_output=True, text=True, encoding="utf-8", errors="replace", creationflags=L.NO_WINDOW)
    cls = json.loads(cl.stdout) if cl.stdout.strip().startswith("[") else []
    (out / "classify-strict-render-reference.json").write_text(cl.stdout, encoding="utf-8", newline="\n")
    summary["classify"] = {"exit": cl.returncode, "frames": [{"frame": Path(r["frame"]).name, "class": r["class"],
                                                              "grade": r["grade"], "rejected": r["rejected"]} for r in cls]}
    # QA-010 checklist (K1 + K3 of this board; K2 is T5.1)
    prov = "packaged-live (strict + render-reference: tools/art/classify_evidence.py --strict --render-reference)"
    host_text = k1_host_t.read_text(encoding="utf-8", errors="replace")
    rc, pj = qa(["project", "--trace", str(k1_host_t), "--shot", k1_host.name, "--frame", str(k1_host)],
                out / "project-k1-host.json")
    cif = (((pj or {}).get("shots") or [{}])[-1]).get("cells_in_frame") or {}
    mz = re.findall(r"ARTPREVIEW board multizone cells=(\d+) zonesListed=(\d+) zonesMarked=(\d+)", host_text)
    sel = re.findall(r"ARTPREVIEW selection ownHero=1 selected=1[^\n]*", host_text)
    zfail = [k for k, v in summary["zoneMarks"].items() if not all(v.get(vn) and v[vn] >= th["zoneMarks"]["markVsTileMinContrast"]
                                                               for vn in ("color", "gray", "deuteranopia")) or not v["visible"]]
    mzr = summary["multizone"]
    ring_bad = sorted({f"{r['name']} ({r['cell'][0]},{r['cell'][1]}) {tag} {r['fraction']}"
                       for tag, rows_ in summary["rings"].items() for r in rows_ if not r["visible"]})
    by_verdict: dict = {}
    for tag, rows_ in summary["labels"].items():
        for r in rows_:
            if r["kind"] == "label":
                by_verdict.setdefault(r["verdict"], {}).setdefault(r["name"], []).append(tag)
    lab_note = "; ".join(f"{v}: " + ", ".join(f"{n} [{' '.join(t)}]" for n, t in sorted(by_verdict[v].items()))
                         for v in ("fail", "AA-large only", "AA") if v in by_verdict)
    manual = {
        "K1.cells_all": {"note": f"проекция трассы: клеток целиком в кадре {cif.get('full')}/{cif.get('total')} "
                                 f"(частично {cif.get('partial')}); различимость — глазами"},
        "K1.multizone": {"note": ("трасса хоста: multizone cells={0} zonesListed={1} zonesMarked={2} — это доказательство "
                                  "геометрии (штрих и глиф заспавнены), не читаемости. ".format(*mz[-1])
                                  + (f"Замер K1 присоединившегося: в {len(mzr['cellsWithUnreadableZone'])} из "
                                     f"{mzr['multizoneCells']} мультизонных клеток метка хотя бы одной зоны не "
                                     f"отделяется от плитки по цвету ({', '.join(mzr['unreadableZones'])}): "
                                     + " ".join(f"({c['cell'][0]},{c['cell'][1]})" for c in mzr['cellsWithUnreadableZone'])
                                     + " — такая клетка читается как однозонная (zone-contrast.json)"
                                     if mzr["cellsWithUnreadableZone"] else "все зоны мультизонных клеток отделяются "
                                     "от плитки по цвету"))
                         if mz and int(mz[-1][0]) > 0
                         else "на этой доске мультизонных клеток нет (строк multizone нет или cells=0)"},
        "K1.hero_helper": {"note": "фигуры: Medusa-кандидат + серые блок-ауты; подписи мира (имя + HP, белый текст без "
                                   "подложки) против светлого фона в SHOT label bbox (labels-damage.json; fail < 3:1, "
                                   "AA-large only 3..4,5:1, AA ≥ 4,5:1, худшая строка): " + (lab_note or "нет данных")},
        "K1.teams_gray": {"note": "команды: MI_Medusa_Blue / MI_Medusa_Red и кольца подставок (W4-B: пара С-11 почти "
                                  "изолюминантна, Q-304); серый — глазами по производным. Кольцо команды в цвете "
                                  f"(доля пикселей цвета команды в кольце, порог {RING_MIN_FRACTION}, team-rings.json) "
                                  "не видно: " + ("; ".join(ring_bad) or "нет")},
        "K1.selected": {"note": ("хост: " + sel[-1][:120]) if sel else "строки выделения в трассе хоста нет"},
        "K1.zones_deut": {"note": "метка зоны против плитки (WCAG ≥ 3:1, зарегистрировано до съёмки) — не проходят: "
                                  + (", ".join(zfail) or "нет") + "; форма (штрих+глиф) у всех пар соседних зон разная; "
                                  "буквы зон не реализованы — zone-contrast.json"},
        "K3.attack_result": {"note": "COMBAT-RESULT и числа урона сходятся у обоих клиентов (validation.json); цель — кольцо-дуги "
                                     "и иконка; иконка висит над целью и ложится на подставку фигуры в клетке за ней "
                                     "(k3-icon-bbox-crops.png); на s09-combat-result.png иконки в пикселях нет, хотя трасса "
                                     "пишет visible=1; атакующий — без позы (клипы не подключены). Число урона: совпадение "
                                     "CUE = число — это счёт, не видимость; читаемость и столкновения с подписями — "
                                     "labels-damage.json"},
        "K3.icon_sizes": {"note": "метод иконки rev 2 (W5-live3): явная маска иконки (analysis/icon-mask-template-32.png), "
                                  "auto-Otsu заменён — на светлой плитке он берёт тёмный передний план (рукояти + подставка "
                                  "соседней фигуры); icon-k3-guard.json"},
    }
    renders = sorted(out.glob("render-*.json"))
    k1r = next((p for p in renders if p.name.endswith("phase2-board-host-1920x1080.json")), None)
    k3r = next((p for p in renders if p.name == f"render-joiner-{k3_png.stem}.json"), None)
    fighters = re.findall(r"FIGHTERS synced n=(\d+) alive=(\d+)", host_text)
    casters = re.findall(r"RENDER tag=SHOT .*?shadowCasters=(\d+)", host_text)
    cfg = {
        "title": f"QA-010 чек-лист T5.2 — {key} ({prof['id']}): K1 + K3 (K2 — задача T5.1). Не приёмка",
        "run": {"задача": "этап 3 T5.2 «Арт 3 живьём»", "доска": f"{key} boardId={spec['boardId']}",
                "K1_хост": rel(k1_host), "K1_присоединившийся": rel(k1_join), "K3": rel(k3_png),
                "производные": f"{a.derived_root} (вне git; sha256 в derive-manifest.json)",
                "пороги": rel(evidence / "t52-thresholds.json")},
        "frames": {"K1": {"path": rel(k1_host), "provenance": prov}, "K3": {"path": rel(k3_png), "provenance": prov}},
        "results": [{"k": "K1..K3", "path": "derive-manifest.json"}, {"k": "K1..K3", "path": "luma-frames.json"},
                    {"k": "K1", "path": "c9-k1-host-all.json"}, {"k": "K3", "path": "icon-k3.json"},
                    {"k": "K1", "path": "project-k1-host.json"}]
                   + ([{"k": "K1", "path": k1r.name}] if k1r else []) + ([{"k": "K3", "path": k3r.name}] if k3r else []),
        "manual": manual,
        "viewer": {"kind": "agent", "note": "самоприёмка агента T5.2: агент смотрел кадры, кропы и листы (Read рендерит PNG "
                                            "в этой сессии) и пиксельные замеры; не независимый зритель — нужен взгляд "
                                            "пользователя"},
        "elements": [
            {"frame": "K1", "id": "facade", "status": "отложено", "reason": "фасадов в сцене S08Arena нет (кандидаты пайплайна не расставлены)"},
            {"frame": "K1", "id": "lantern", "status": "отложено", "reason": "фонаря в сцене нет"},
            {"frame": "K1", "id": "tray_darkness", "status": "есть",
             "reason": "деревянная рама и тёмный фон (профиль доски); рваного края подноса нет"},
            {"frame": "K1", "id": "fog", "status": "отложено", "reason": "туман в профиле рендера не задан"},
            {"frame": "K1", "id": "vignette", "status": "отложено", "reason": "виньетка не задана"},
            {"frame": "K1", "id": "zone_pictograms", "status": "отложено",
             "reason": "пиктограммы зон по краю подноса не реализованы; глифы зон — в клетках (T4.2)"},
            {"frame": "K1", "id": "hud", "status": "есть", "reason": "UMG-гибрид W4-C (панели сверху, рука снизу)"},
            {"frame": "K1", "id": "shadow_casters_1", "status": "есть" if casters and set(casters) == {"1"} else "нет",
             "reason": f"RENDER shadowCasters={','.join(sorted(set(casters))) or '?'} (трасса хоста)"},
            {"frame": "K1", "id": "six_fighters", "status": "есть" if fighters and fighters[-1] == ("6", "6") else "нет",
             "reason": "FIGHTERS synced n=6 alive=6: кандидат Medusa v2 + серые блок-ауты гарпий, Артура и Мерлина"},
            {"frame": "K2", "id": "facade_hidden", "status": "отложено", "reason": "K2 — вне T5.2 (T5.1)"},
            {"frame": "K2", "id": "plate", "status": "отложено",
             "reason": "K2 — T5.1; плашка и её перекрытие с клетками выбора измерены на K1 хоста (plate-k1-host.json)"},
            {"frame": "K2", "id": "base_profile", "status": "отложено", "reason": "K2 — вне T5.2 (T5.1)"},
            {"frame": "K3", "id": "poses", "status": "отложено", "reason": "клипы боя не подключены — «постановка» (фигуры в покое)"},
            {"frame": "K3", "id": "inspector_2d", "status": "отложено", "reason": "инспектор карты с 2D-артом не реализован (D-09)"},
            {"frame": "K3", "id": "target_frame_icon", "status": "есть" if summary["icon"]["sizes"] else "нет",
             "reason": "кольцо цели + иконка UMG (SHOT icon src=combat в SHOT-блоке кадра K3)"},
            {"frame": "K3", "id": "damage_result", "status": "есть",
             "reason": "числа урона: ARTPREVIEW damage-number = CUE damage ровно по одному (validation.json); итог боя — "
                       "панель результата S09 (кадр s09-combat-result.png)"},
        ],
    }
    apply_errata_w5br(cfg, key, k3)
    L.write_json(out / "checklist-config.json", cfg)
    ck = subprocess.run([sys.executable, str(QA010), "checklist", "--config", rel(out / "checklist-config.json"),
                         "--out-md", rel(out / "qa010-checklist.md"), "--out-json", rel(out / "qa010-checklist.json")],
                        capture_output=True, text=True, encoding="utf-8", errors="replace", cwd=str(REPO),
                        creationflags=L.NO_WINDOW)
    summary["checklist"] = {"exit": ck.returncode, "md": rel(out / "qa010-checklist.md"),
                            "statusCounts": (json.loads((out / "qa010-checklist.json").read_text(encoding="utf-8"))
                                             .get("status_counts") if (out / "qa010-checklist.json").is_file() else None)}
    L.write_json(out / "summary.json", summary)
    print(json.dumps({k: summary[k] for k in ("board", "frames", "icon", "plate")}, ensure_ascii=False)[:1500])
    return 0


# ---------------------------------------------------------------- W5b-R errata of T5.2 (checklists)
ERRATA_W5BR_DATE = "2026-09-29"
ERRATA_W5BR_REF = ("эррата W5b-R (docs/game-design/evidence/ART-005/art3-live-3boards-r2-2026-09-29.md §9; "
                   "art3-live-3boards-2026-09-29.md §9.1)")
ERRATA_PLATE_UNDER = {
    "cobble-5x6": "Эррата W5b-R: плашка Medusa на K1 хоста лежит сразу под фигурой King Arthur (2,3) и читается как его "
                  "плашка; пересечение плашки с фигурами в T5.2 не мерилось (правило plateVsFigures и привязка плашки "
                  "к владельцу — W5b-R)",
}
ERRATA_PANEL = {
    "cobble-5x6": "панель боя в левом верхнем углу доходит до рамки доски; клетки не закрывает (агент, по кадру)",
    "sherwood-forest-8x5": "панель боя в левом верхнем углу закрывает часть клеток (0,0) и (1,0), панель руки — край "
                           "нижнего ряда (агент, по кадру)",
    "t-rex-paddock-7x5": "панель боя в левом верхнем углу закрывает часть клеток (0,0), (1,0) и (0,1), панель руки — "
                         "край нижнего ряда (агент, по кадру)",
}


def first_damage_vs_combat(trace: Path) -> dict:
    """Seq of the first CUE damage and of the first COMBAT_RESOLVE snapshot in a combat client trace."""
    text = trace.read_text(encoding="utf-8", errors="replace") if trace.is_file() else ""
    dmg = re.search(r"CUE damage (\S+) -(\d+) seq=(\d+)", text)
    res = re.search(r"SNAPSHOT applied seq=(\d+) phase=COMBAT_RESOLVE", text)
    out = {"damageFighter": dmg.group(1) if dmg else None, "damageAmount": int(dmg.group(2)) if dmg else None,
           "damageSeq": int(dmg.group(3)) if dmg else None, "firstCombatResolveSeq": int(res.group(1)) if res else None}
    out["source"] = ("способность/эффект (урон раньше первого COMBAT_RESOLVE)"
                     if out["damageSeq"] is not None and out["firstCombatResolveSeq"] is not None
                     and out["damageSeq"] < out["firstCombatResolveSeq"] else "бой или не определено")
    return out


def apply_errata_w5br(cfg: dict, key: str, k3_run: Path | None) -> dict:
    """W5b-R errata of a T5.2 checklist config (idempotent)."""
    res = cfg.setdefault("results", [])
    if not any(r.get("path") == "plate-k1-host.json" for r in res):
        res.append({"k": "K1", "path": "plate-k1-host.json"})
    fd = first_damage_vs_combat(k3_run / "combat-client-joiner.trace.log") if k3_run else {}
    notes = {
        "K3.attack_result": (
            "Эррата W5b-R — строка делится на два вердикта: «рамка/дуги цели и итог в HUD» — есть с оговоркой (агент); "
            "«иконка цели» — нет (строка K3.icon_sizes, метод rev 2). Кадр числа урона s09-damage-number.png — "
            f"{fd.get('source', 'не определено')}: CUE damage {fd.get('damageFighter')} -{fd.get('damageAmount')} "
            f"seq={fd.get('damageSeq')}, первый COMBAT_RESOLVE seq={fd.get('firstCombatResolveSeq')} (трасса "
            f"присоединившегося). HUD-панели K3: {ERRATA_PANEL.get(key, 'не проверялось')}; строк SHOT panel в "
            "трассах T5.2 нет, перекрытие не измерялось"),
    }
    if key in ERRATA_PLATE_UNDER:
        notes["K1.selected"] = ERRATA_PLATE_UNDER[key]
    manual = cfg.setdefault("manual", {})
    for row, note in notes.items():
        m = manual.setdefault(row, {})
        base = m.get("note", "")
        if "Эррата W5b-R" in base:
            base = base.split(" | Эррата W5b-R")[0]
        m["note"] = (base + " | " if base else "") + note
    cfg["errata"] = {"date": ERRATA_W5BR_DATE, "ref": ERRATA_W5BR_REF, "firstDamage": fd,
                     "changes": ["results: + plate-k1-host.json (k=K1; сама строка K2.plate — задача T5.1)",
                                 "K3.attack_result: разделена (рамка/дуги vs иконка), кадр урона помечен",
                                 "K1.selected: плашка под King Arthur (только Cobble)"]}
    return cfg


PERF_H2 = "измерено; ЗАГРЯЗНЕНО фоном H2 (headless Blender/Cycles параллельной линии героев) — не для ACC-022"


def errata_k1_perf(evidence: Path) -> list[dict]:
    """W5b-R errata: the K1 perf.json / perf-csv.json of T5.2 lacked the H2 background label (the K3 ones had it) and
    named a stale editor PID; relabel them and re-hash their manifest.json entries (idempotent)."""
    out = []
    for run in sorted((evidence / "k1").glob("*/run-*")):
        man_p = run / "manifest.json"
        if not man_p.is_file():
            continue
        man = json.loads(man_p.read_text(encoding="utf-8"))
        changed = []
        for name in ("perf.json", "perf-csv.json"):
            fp = run / name
            if not fp.is_file():
                continue
            doc = json.loads(fp.read_text(encoding="utf-8"))
            before = L.sha256_file(fp)
            if doc.get("status") != PERF_H2:
                doc["errata"] = {"date": ERRATA_W5BR_DATE, "ref": ERRATA_W5BR_REF,
                                 "previousStatus": doc.get("status"),
                                 "why": "метка фона H2 добавлена после съёмки: K1 и K3 T5.2 снимались при одном фоне "
                                        "(акт T5.2 §3), в K3 метка стояла с начала"}
                doc["status"] = PERF_H2
                if "concurrentGpuUsers" in doc:
                    doc["errata"]["previousConcurrentGpuUsers"] = doc["concurrentGpuUsers"]
                    doc["concurrentGpuUsers"] = ("живой UnrealEditor PID 31756 (главный checkout, MCP :8123), Blender MCP "
                                                 ":9876/:9877 и headless-процессы линии героев H2; см. perProcessSmPct "
                                                 "(эррата W5b-R: прежний текст называл PID 19540 — строка-шаблон "
                                                 "art004_live_k2 T1.1)")
                L.write_json(fp, doc)
            after = L.sha256_file(fp)
            for e in man.get("files", []):
                if e.get("name") == name and (e.get("sha256") != after or e.get("bytes") != fp.stat().st_size):
                    e["sha256"], e["bytes"] = after, fp.stat().st_size
                    changed.append({"name": name, "before": before, "after": after})
        if changed:
            man.setdefault("errata", []).append({"date": ERRATA_W5BR_DATE, "ref": ERRATA_W5BR_REF, "rehashed": changed})
            L.write_json(man_p, man)
        out.append({"run": rel(run), "rehashed": changed})
    return out


def cmd_errata_w5br(a) -> int:
    evidence = Path(a.evidence).resolve()
    print(json.dumps({"k1Perf": errata_k1_perf(evidence)}, ensure_ascii=False))
    rc = 0
    for key in BOARDS:
        out = evidence / "analysis" / key
        cfg_p = out / "checklist-config.json"
        if not cfg_p.is_file():
            print(f"skip {key}: no checklist-config.json")
            continue
        k3_dirs = sorted((evidence / "k3" / key).glob("combat-*"))
        cfg = json.loads(cfg_p.read_text(encoding="utf-8"))
        apply_errata_w5br(cfg, key, k3_dirs[-1] if k3_dirs else None)
        L.write_json(cfg_p, cfg)
        ck = subprocess.run([sys.executable, str(QA010), "checklist", "--config", rel(cfg_p),
                             "--out-md", rel(out / "qa010-checklist.md"), "--out-json", rel(out / "qa010-checklist.json")],
                            capture_output=True, text=True, encoding="utf-8", errors="replace", cwd=str(REPO),
                            creationflags=L.NO_WINDOW)
        rc = max(rc, 0 if ck.returncode in (0, 1) else ck.returncode)
        sp = out / "summary.json"
        if sp.is_file():
            summary = json.loads(sp.read_text(encoding="utf-8"))
            summary["checklist"] = {"exit": ck.returncode, "md": rel(out / "qa010-checklist.md"),
                                    "statusCounts": json.loads((out / "qa010-checklist.json").read_text(
                                        encoding="utf-8")).get("status_counts"),
                                    "errata": cfg["errata"]}
            L.write_json(sp, summary)
        print(json.dumps({"board": key, "checklistExit": ck.returncode, "firstDamage": cfg["errata"]["firstDamage"]},
                         ensure_ascii=False))
    return rc


def cmd_mi(a) -> int:
    """Medusa material identity across every K1/K3 run of the evidence dir."""
    evidence = Path(a.evidence).resolve()
    rows = []
    for tp in sorted(list(evidence.glob("k1/*/run-*/phase2-client-*.trace.log")) +
                     list(evidence.glob("k3/*/combat-*/combat-client-*.trace.log"))):
        run = tp.parent
        board = run.parent.name
        role = "host" if "host" in tp.name else "joiner"
        kind = run.parent.parent.name.upper()
        for m in MI_LINE.finditer(tp.read_text(encoding="utf-8", errors="replace")):
            rows.append({"k": kind, "board": board, "run": run.name, "client": role, "fighter": m.group(1),
                         "team": m.group(2), "mesh": m.group(3), "slots": int(m.group(4)), "mi": m.group(5),
                         "slot1": m.group(6), "base": m.group(7), "parent": m.group(8), "params": int(m.group(9)),
                         "miSha256": m.group(10)})
    by_team: dict = {}
    for r in rows:
        by_team.setdefault(r["team"], set()).add((r["mi"], r["slot1"], r["base"], r["parent"], r["params"], r["miSha256"]))
    runs = sorted({(r["k"], r["board"], r["run"], r["client"]) for r in rows})
    boards = sorted({r["board"] for r in rows})
    per_board = {b: {t: sorted({r["miSha256"] for r in rows if r["board"] == b and r["team"] == t})
                     for t in sorted(by_team)} for b in boards}
    identical = all(len(v) == 1 for v in by_team.values()) and all(
        all(len(per_board[b][t]) == 1 for t in per_board[b]) for b in boards)
    src = {}
    for relp in MEDUSA_MI:
        p = REPO / relp
        src[relp] = L.sha256_file(p) if p.is_file() else None
    paks = {p.name: L.sha256_file(p) for p in sorted(PAKS.glob("*")) if p.is_file()}
    k3_staged = []
    for rr in sorted(evidence.glob("k3/*/combat-*/run-record.json")):
        d = json.loads(rr.read_text(encoding="utf-8"))
        k3_staged.append({"run": rr.parent.name, "board": rr.parent.parent.name,
                          "stagedEqualsNow": {k: v == paks.get(k) for k, v in (d.get("staged") or {}).items() if k in paks}})
    doc = {"schema": "unmatched.t52-medusa-mi/1",
           "rule": "строки 'ARTPREVIEW medusa materials' (S08FighterActor, T5.2): путь MI в слотах тела и подставки, путь "
                   "родителя, число переопределённых параметров и sha256 канонической строки «путь|родитель|параметры» "
                   "загруженного (cooked) MI; одинаковы по команде во всех прогонах всех досок",
           "identicalAcrossBoards": identical, "lines": len(rows), "runs": [list(x) for x in runs],
           "boards": boards, "perTeam": {t: [dict(zip(("mi", "slot1", "base", "parent", "params", "miSha256"), x))
                                             for x in sorted(v)] for t, v in by_team.items()},
           "perBoard": per_board, "sourceUassetSha256": src, "stagedPakSha256Now": paks,
           "k3RunsStagedPakEqualsNow": k3_staged,
           "note": "K1-прогоны (art004_live_k2.py run) не пишут хеши пака; единственный пак P1 не пересобирался между "
                   "первым K1 и последним K3 (mtime пака раньше первого прогона, хеши K3-прогонов = текущие)",
           "rows": rows}
    L.write_json(evidence / "analysis" / "medusa-mi-identity.json", doc)
    print(json.dumps({"identicalAcrossBoards": identical, "lines": len(rows), "runs": len(runs),
                      "perBoard": per_board}, ensure_ascii=False, indent=1))
    return 0 if identical else 1


def cmd_icon_crops(a) -> int:
    """Sheet of the traced icon bbox (+8 px) of every published K3 frame, x6 nearest: shows where the icon
    is really drawn (the trace of s09-combat-result.png claims a painted icon that is not in the pixels)."""
    from PIL import Image, ImageDraw
    evidence = Path(a.evidence).resolve()
    tiles, rows = [], []
    for run in sorted(evidence.glob("k3/*/combat-*")):
        for side in ("joiner", "host"):
            tp = run / f"combat-client-{side}.trace.log"
            for png in sorted((run / side).glob("*.png")):
                text = _block_text(tp, png.name)
                m = re.search(r"SHOT icon fighter=(\S+) bbox=\((\d+),(\d+),(\d+),(\d+)\)", text)
                if not m:
                    rows.append({"frame": rel(png), "iconTraced": False})
                    continue
                x0, y0, x1, y1 = map(int, m.groups()[1:])
                with Image.open(png) as im:
                    crop = im.convert("RGB").crop((x0 - 8, y0 - 8, x1 + 8, y1 + 8)).resize((288, 288), Image.NEAREST)
                tiles.append((crop, f"{run.parent.name.rsplit('-', 1)[0]} {side} {png.stem.replace('s09-', '')}"))
                rows.append({"frame": rel(png), "iconTraced": True, "fighter": m.group(1), "bbox": [x0, y0, x1, y1],
                             "widgetVisibleTraced": "SHOT widget id=icon" in text and "visible=1" in text})
    cols = 6
    sheet = Image.new("RGB", (cols * 296, ((len(tiles) + cols - 1) // cols) * 316), (24, 24, 24))
    d = ImageDraw.Draw(sheet)
    for i, (crop, label) in enumerate(tiles):
        x, y = (i % cols) * 296 + 4, (i // cols) * 316 + 4
        sheet.paste(crop, (x, y))
        d.text((x, y + 290), label, fill=(255, 255, 255))
    out = evidence / "analysis" / "k3-icon-bbox-crops.png"
    sheet.save(out)
    L.write_json(evidence / "analysis" / "k3-icon-bbox-crops.json",
                 {"schema": "unmatched.t52-icon-crops/1", "sheet": rel(out),
                  "method": "traced SHOT icon bbox of the LAST SHOT block of each frame, +8 px, x6 nearest; the "
                            "presence of the icon is judged by eye (agent) on this sheet", "frames": rows})
    print(rel(out), len(tiles))
    return 0


def _block_text(trace: Path, name: str) -> str:
    """Text of the LAST SHOT block that requested <name> (as on disk)."""
    lines = trace.read_text(encoding="utf-8", errors="replace").splitlines()
    cur, last = [], ""
    for ln in lines:
        if "SHOT ctx" in ln:
            cur = []
        cur.append(ln)
        if "SHOT requested" in ln and re.split(r"[\\/]", ln.strip())[-1] == name:
            last = "\n".join(cur)
    return last


# ------------------------------------------------------------------ W5-live3: readability re-measurement
# Review of T5.2 (W5-live3) found four overstated verdicts. The measurements below replace them on the SAME
# published frames (no re-shoot): the target icon with an explicit icon mask (method rev 2), multizone cells
# with a readability check, team rings per fighter and world labels / damage numbers against their local
# background. Thresholds marked «после съёмки» were NOT registered before the shots.
FIGHTER_NAMES = {"f-0-hero": "Medusa", "f-0-sk0": "Harpies 1", "f-0-sk1": "Harpies 2", "f-0-sk2": "Harpies 3",
                 "f-1-hero": "King Arthur", "f-1-sk0": "Merlin"}
LABEL_LINE = re.compile(r"SHOT label fighter=(\S+) mode=(\S+) bbox=\((-?\d+),(-?\d+),(-?\d+),(-?\d+)\)")
DAMAGE_LINE = re.compile(r"SHOT damage fighter=(\S+) bbox=\((-?\d+),(-?\d+),(-?\d+),(-?\d+)\)")
MI_TEAM = re.compile(r"ARTPREVIEW medusa materials fighter=(f-\d+)-\S+ team=(own|enemy)")
ICON_TEMPLATE = Path("analysis") / "icon-mask-template-32.png"
ICON_TEMPLATE_RUN = "k3/cobble-5x6/combat-20260929-143232"
ICON_NO_ICON_FRAME = "s09-combat-result.png"
ICON_DIFF_THRESHOLD = 16      # max |ΔRGB| of the icon frame against the same view without the icon
ICON_PRESENT_MIN_IOU = 0.6    # difference mask vs template, rows >= ICON_ROWS_FROM (below the attacker ring)
ICON_ROWS_FROM = 10
ICON_AUTO_VALID_MIN_IOU = 0.5
ICON_FOREIGN_DLUMA = 40       # bbox background pixel farther than this from the tile luma = pedestal / ring
RING_INNER_UU, RING_OUTER_UU = 12.0, 26.0
RING_MIN_FRACTION = 0.05      # после съёмки; the measured distribution is bimodal (see team-rings.json)
TEXT_AA, TEXT_AA_LARGE = 4.5, 3.0  # WCAG 2.x 1.4.3 (normal / large text); not registered before the shots
RING_METHOD = (
    "Кольцо команды — подставка-цилиндр цвета команды (S08FighterActor: свой (0.02,0.25,1.5) синий, чужой "
    "(0.85,0.2,0.2) красный; у арт-фигур верх диска на z=0 актора, т.е. в плоскости верха плитки). Кольцевая зона "
    f"{RING_INNER_UU:g}..{RING_OUTER_UU:g} uu × масштаб фигуры (герой 1,0, помощник 0,78) вокруг SHOT fighter world, "
    "спроецирована камерой SHOT-блока (qa010 projection). Пиксель цвета команды (CIELAB): синий — hue 240..300°, "
    "C* ≥ 15, L* ≥ 40; красный — hue 345..40°, C* ≥ 15, L* ≥ 55 (коричневая подставка Medusa L* ≈ 40 и жёлтое "
    "кольцо выбора hue 70..110° не считаются). Доля = пиксели цвета команды / пиксели кольцевой зоны. Кольцо «видно» "
    f"при доле ≥ {RING_MIN_FRACTION} — порог назначен ПОСЛЕ съёмки (распределение двугорбое), не зарегистрирован. "
    "Свой/чужой — по строке ARTPREVIEW medusa materials team= клиента кадра.")
LABEL_METHOD = (
    "Подписи мира (TextRender, белый текст без подложки: имя сверху, HP снизу) и числа урона — по bbox из строк "
    "SHOT label / SHOT damage SHOT-блока кадра. Текст — пиксели bbox с luma ≥ p99(bbox) − 6 и C* < 12; фон — "
    "luma < p99 − 30 и дальше 2 px от пикселей текста (без сглаженных краёв букв). Контраст WCAG = текст (медиана) против светлого фона "
    "(медиана пикселей фона с luma ≥ 120, если их ≥ 10 %; иначе медиана всего фона) — отдельно для строки имени "
    "(верхняя половина bbox) и строки HP (нижняя). Вердикт: ≥ 4,5 : 1 — AA; 3..4,5 — только AA для крупного "
    "текста; < 3 — fail (WCAG 2.x 1.4.3; порог взят из WCAG ПОСЛЕ съёмки, не зарегистрирован). «Край плитки "
    "режет подпись» — в фоне строки ≥ 10 % тёмных (luma < 60: шов, пустота) и ≥ 10 % светлых (≥ 120) пикселей. "
    "Число урона: пересечение его bbox с bbox подписей того же блока (доля площади числа).")


def _shot_block_text(trace: Path, name: str) -> str:
    return _block_text(trace, name)


def _same_view(a, b) -> tuple[bool, str]:
    if a.viewport != b.viewport or a.cam != b.cam or a.rot != b.rot:
        return False, f"camera differs: {a.cam}/{a.rot} vs {b.cam}/{b.rot}"
    sa = {f.fighter_id: f.screen for f in a.fighters if f.alive}
    sb = {f.fighter_id: f.screen for f in b.fighters if f.alive}
    moved = [k for k in sa if k in sb and sa[k] != sb[k]]
    if moved:
        return False, "fighters moved: " + ", ".join(moved)
    return True, "same viewport, camera and fighter screen points"


def _iou(a, b) -> float:
    u = int((a | b).sum())
    return round(float((a & b).sum()) / u, 4) if u else 0.0


def _dilate(m, r: int = 1):
    import numpy as np
    out = m.copy()
    h, w = m.shape
    p = np.pad(m, r)
    for dy in range(-r, r + 1):
        for dx in range(-r, r + 1):
            out |= p[r + dy:r + dy + h, r + dx:r + dx + w]
    return out


def cmd_icon_template(a) -> int:
    """Icon mask template (bbox-sized) from the difference of a K3 frame with the icon and the same client's
    frame of the same view without it (the icon is hidden on s09-combat-result.png although the trace says
    visible=1). Built on Cobble: on its mid-grey stone both the light blades and the brown hilts differ strongly
    from the background; on the light fixture tiles the blades almost equal the tile (an incomplete difference)
    and the attacker's yellow ring disappears in the same bbox. The widget is 32x32 on every board."""
    import numpy as np
    from PIL import Image
    from qa010lib.imageio import load_rgb
    from qa010lib.trace import parse_trace
    evidence = Path(a.evidence).resolve()
    run = evidence / a.run
    png, ref = run / "joiner" / "s09-combat-resolve-revealed.png", run / "joiner" / ICON_NO_ICON_FRAME
    trace = run / "combat-client-joiner.trace.log"
    tr = parse_trace(trace)
    b, rb = tr.find_shot(None, png.name), tr.find_shot(None, ref.name)
    same, why = _same_view(b, rb)
    if b.icon is None or not same:
        print(f"REFUSED: icon={b.icon is not None} sameView={same} ({why})")
        return 2
    x0, y0, x1, y1 = (int(v) for v in b.icon.value["bbox"])
    A, B = load_rgb(png).astype(int), load_rgb(ref).astype(int)
    d = np.abs(A - B).max(axis=-1)
    m = d[y0:y1, x0:x1] > a.threshold
    ring = d[y0 - 8:y1 + 8, x0 - 8:x1 + 8].copy()
    ring[8:-8, 8:-8] = -1
    rv = ring[ring >= 0]
    out = evidence / ICON_TEMPLATE
    Image.fromarray((m * 255).astype(np.uint8), "L").save(out)
    doc = {"schema": "unmatched.t52-icon-template/1", "status": "измерено (W5-live3, метод иконки rev 2)",
           "template": rel(out), "templateSha256": L.sha256_file(out), "size": [x1 - x0, y1 - y0],
           "pixels": int(m.sum()), "threshold": a.threshold,
           "iconFrame": {"path": rel(png), "sha256": L.sha256_file(png), "bbox": [x0, y0, x1, y1],
                         "traceLine": b.icon.line_no},
           "noIconFrame": {"path": rel(ref), "sha256": L.sha256_file(ref),
                           "note": "тот же клиент и вид; трасса пишет иконку видимой, в пикселях её нет (T5.2)"},
           "sameView": why, "trace": rel(trace),
           "noiseOutsideBbox": {"ringPx": 8, "p50": float(np.percentile(rv, 50)), "p90": float(np.percentile(rv, 90)),
                                "p99": float(np.percentile(rv, 99))},
           "rule": "маска = max|ΔRGB| кадра с иконкой и кадра без неё > threshold внутри SHOT icon bbox; маска "
                   "bbox-размера (32x32), qa010 icon --mask принимает её на любой доске (виджет 32 px, та же "
                   "текстура); совпадение с иконкой на доске проверяется в icon-k3-guard.json"}
    L.write_json(out.with_suffix(".json"), doc)
    print(json.dumps({k: doc[k] for k in ("template", "pixels", "threshold", "sameView", "noiseOutsideBbox")},
                     ensure_ascii=False))
    return 0


def measure_icon(evidence: Path, out: Path, k3: Path, k3_main: str, trace: Path) -> dict:
    """K3 icon contrast, method rev 2: qa010 icon --mask <template> is the measurement; the auto-Otsu run is
    kept as superseded diagnostics, and the guard records why it is not valid on light tiles."""
    png = k3 / "joiner" / k3_main
    tmpl = evidence / ICON_TEMPLATE
    if not tmpl.is_file():
        raise SystemExit(f"REFUSED: {rel(tmpl)} is missing; run 'icon-template' first")
    rc_auto, auto = qa(["icon", str(png), "--trace", str(trace), "--shot", k3_main], out / "icon-k3-auto-otsu.json")
    rc, doc = qa(["icon", str(png), "--trace", str(trace), "--shot", k3_main, "--mask", str(tmpl)],
                 out / "icon-k3.json")
    guard = icon_guard(png, trace, k3_main, tmpl, doc or {}, auto or {}, k3 / "joiner" / ICON_NO_ICON_FRAME)
    L.write_json(out / "icon-k3-guard.json", guard)

    def sizes(d):
        return [{k: s.get(k) for k in ("size_px", "contrast_ratio", "contrast_ratio_vs_ring", "upscaled", "pass")}
                for s in (d or {}).get("sizes", [])]
    return {"method": "rev 2 (W5-live3): qa010 icon --mask " + rel(tmpl), "exit": rc,
            "result": (doc or {}).get("result"), "bboxSource": (doc or {}).get("bbox_source"), "sizes": sizes(doc),
            "guard": {k: guard[k] for k in ("verdict", "iconInPixels", "autoOtsu", "bboxBackground", "partsVsTile")},
            "supersededAutoOtsu": {"file": "icon-k3-auto-otsu.json", "exit": rc_auto,
                                   "foreground": ((auto or {}).get("foreground") or {}).get("foreground"),
                                   "sizes": sizes(auto)}}


def icon_guard(png: Path, trace: Path, shot: str, tmpl: Path, masked: dict, auto: dict, ref: Path) -> dict:
    """Why the icon number can be trusted (or not) on this frame:
    - iconInPixels: the icon frame against the same client's no-icon frame (same view) — the difference mask
      below the attacker ring matches the template (a stale 'visible=1' trace cannot pass);
    - autoOtsu: qa010's automatic foreground against the template (IoU, polarity). On light tiles Otsu takes
      the DARK class (brown hilts + the pedestal of the fighter behind the target), not the light blades;
    - bboxBackground: share of the bbox background that is not tile (pedestal, ring) — it pulls the background
      median of qa010 icon (background=bbox) away from the tile;
    - partsVsTile: blades / hilts / the whole icon against the tile of the lower half of the bbox."""
    import numpy as np
    from qa010lib import color as C
    from qa010lib.checks import auto_icon_mask, luma_levels, otsu_threshold
    from qa010lib.imageio import load_mask, load_rgb
    from qa010lib.trace import parse_trace
    rgb = load_rgb(png)
    h, w = rgb.shape[:2]
    x0, y0, x1, y1 = masked["bbox"]
    tm = load_mask(tmpl)
    g = {"schema": "unmatched.t52-icon-guard/1", "frame": rel(png), "template": rel(tmpl), "bbox": [x0, y0, x1, y1]}
    if tm.shape != (y1 - y0, x1 - x0):
        g.update(verdict="invalid: template size != bbox", iconInPixels=None, autoOtsu=None, bboxBackground=None,
                 partsVsTile=None)
        return g
    # 1) the icon is in the pixels (difference against the no-icon frame of the same view)
    tr = parse_trace(trace)
    present = {"noIconFrame": rel(ref), "available": False}
    if ref.is_file():
        same, why = _same_view(tr.find_shot(None, shot), tr.find_shot(None, ref.name))
        present.update(sameView=why)
        if same:
            d = np.abs(rgb.astype(int) - load_rgb(ref).astype(int)).max(axis=-1)[y0:y1, x0:x1] > ICON_DIFF_THRESHOLD
            iou = _iou(d[ICON_ROWS_FROM:], tm[ICON_ROWS_FROM:])
            present.update(available=True, rule=f"IoU(max|ΔRGB| > {ICON_DIFF_THRESHOLD}, template), строки bbox ≥ "
                           f"{ICON_ROWS_FROM} (ниже кольца атакующего) ≥ {ICON_PRESENT_MIN_IOU}",
                           iou=iou, present=iou >= ICON_PRESENT_MIN_IOU, diffPixelsWholeBbox=int(d.sum()))
    # 2) the automatic foreground of qa010 icon
    ring = int(masked.get("ring_px") or 8)
    cx0, cy0, cx1, cy1 = max(0, x0 - ring), max(0, y0 - ring), min(w, x1 + ring), min(h, y1 + ring)
    crop = rgb[cy0:cy1, cx0:cx1]
    inbox = np.zeros(crop.shape[:2], dtype=bool)
    inbox[y0 - cy0:y1 - cy0, x0 - cx0:x1 - cx0] = True
    fg, info = auto_icon_mask(crop, inbox)
    fgb = fg[y0 - cy0:y1 - cy0, x0 - cx0:x1 - cx0]
    luma = C.luma_u8(rgb[y0:y1, x0:x1])
    lum = C.relative_luminance(rgb[y0:y1, x0:x1])
    iou_auto = _iou(fgb, tm)
    auto_rec = {"foreground": info.get("foreground"), "basis": info.get("basis"), "threshold": info.get("threshold"),
                "pixels": int(fgb.sum()), "iouWithTemplate": iou_auto,
                "pixelsOutsideTemplate": int((fgb & ~_dilate(tm)).sum()),
                "valid": iou_auto >= ICON_AUTO_VALID_MIN_IOU,
                "sizes": [{k: s.get(k) for k in ("size_px", "contrast_ratio", "pass")} for s in auto.get("sizes", [])]}
    # 3) the bbox background (qa010 icon background=bbox) and the tile of the lower half
    bg = ~_dilate(tm)
    lower = bg.copy()
    lower[: (y1 - y0) // 2] = False
    tile_luma = float(np.median(luma[lower]))
    tile_lum = float(np.median(lum[lower]))
    foreign = bg & (np.abs(luma - tile_luma) > ICON_FOREIGN_DLUMA)
    bgr = {"pixels": int(bg.sum()), "tileLumaLowerHalf": round(tile_luma, 1),
           "foreignPixels": int(foreign.sum()), "foreignShare": round(float(foreign.sum()) / max(1, int(bg.sum())), 3),
           "foreignDarkPixels": int((foreign & (luma < tile_luma)).sum()),
           "rule": f"фон bbox = пиксели вне маски (+1 px); «чужие» — |luma − медиана нижней половины| > "
                   f"{ICON_FOREIGN_DLUMA} (подставка фигуры сзади, кольцо)"}
    # 4) parts of the icon against the tile
    t = otsu_threshold(luma_levels(luma)[tm])
    blades = tm & (luma_levels(luma) > t) if t is not None else tm
    hilts = tm & ~blades
    parts = {"tileLuma": round(tile_luma, 1), "otsuInsideMask": t}
    for name, m in (("icon", tm), ("blades", blades), ("hilts", hilts)):
        if m.any():
            parts[name] = {"pixels": int(m.sum()), "lumaMedian": round(float(np.median(luma[m])), 1),
                           "wcagVsTile": round(float(C.wcag_contrast_ratio(float(np.median(lum[m])), tile_lum)), 3)}
    ok = bool(present.get("present")) and masked.get("status") == "measured"
    g.update(iconInPixels=present, autoOtsu=auto_rec, bboxBackground=bgr, partsVsTile=parts,
             verdict=("valid: explicit mask, icon present in pixels" if ok else
                      "no data: icon not confirmed in pixels" if masked.get("status") == "measured" else "no data"),
             autoOtsuNote=("auto-Otsu superseded: its foreground is not the icon (IoU < "
                           f"{ICON_AUTO_VALID_MIN_IOU})" if not auto_rec["valid"] else
                           "auto-Otsu overlaps the icon, but it is still superseded by the explicit mask"))
    return g


def multizone_readability(cells: list[dict], zones: dict) -> dict:
    """Multizone cells with at least one zone whose mark cannot be told from the tile by colour
    (zone_metrics 'visible' = false: colour clash with the tile or no mark pixels found)."""
    unread = sorted(k for k, v in zones.items() if not v.get("visible"))
    mz = [c for c in cells if len(c["zones"]) > 1 and not c["obstacle"]]
    bad = [{"cell": [c["x"], c["y"]], "zones": c["zones"], "unreadable": [z for z in c["zones"] if z in unread]}
           for c in mz if any(z in unread for z in c["zones"])]
    gray_lost = {k for k, v in zones.items()
                 if (v.get("variants", {}).get("gray") or {}).get("wcag") is not None
                 and v["variants"]["gray"]["wcag"] < 1.2}
    return {"multizoneCells": len(mz), "unreadableZones": unread, "cellsWithUnreadableZone": bad,
            "grayVanishingZones(<1.2:1 in gray)": sorted(gray_lost),
            "cellsLosingAZoneInGray": [[c["x"], c["y"]] for c in mz if any(z in unread or z in gray_lost
                                                                           for z in c["zones"])],
            "rule": "зона нечитаема в цвете, если её метку нельзя отделить от плитки по цвету (zone-contrast.json: "
                    "visible=false — цвет = плитка или метки не найдены); zonesListed = zonesMarked трассы — "
                    "доказательство геометрии, не читаемости"}


def _own_side(text: str, client: str) -> str:
    m = MI_TEAM.search(text)
    if m:
        side, team = m.group(1), m.group(2)
        return side if team == "own" else ("f-1" if side == "f-0" else "f-0")
    return "f-0" if client == "host" else "f-1"


def ring_metrics(png: Path, trace: Path, client: str) -> dict:
    import numpy as np
    from qa010lib import color as C
    from qa010lib.imageio import load_rgb
    from qa010lib.projection import build_projection, project_polygon
    from qa010lib.regions import _poly_mask
    from qa010lib.trace import parse_trace
    rgb = load_rgb(png)
    h, w = rgb.shape[:2]
    shot = parse_trace(trace).find_shot(None, png.name)
    proj = build_projection(shot, 35.0, 2.0, "auto")
    lab = C.linear_to_lab(C.u8_to_linear(rgb))
    chroma = np.hypot(lab[..., 1], lab[..., 2])
    hue = (np.degrees(np.arctan2(lab[..., 2], lab[..., 1])) + 360.0) % 360.0
    blue = (chroma >= 15) & (lab[..., 0] >= 40) & (hue >= 240) & (hue < 300)
    red = (chroma >= 15) & (lab[..., 0] >= 55) & ((hue >= 345) | (hue < 40))
    yellow = (chroma >= 20) & (lab[..., 0] >= 70) & (hue >= 70) & (hue < 110)
    own = _own_side(trace.read_text(encoding="utf-8", errors="replace"), client)
    rows = []
    for f in shot.fighters:
        if not f.alive:
            continue
        fs = 1.0 if f.fighter_id.endswith("-hero") else 0.78

        def disc(r):
            return [(f.world[0] + r * math.cos(2 * math.pi * i / 64), f.world[1] + r * math.sin(2 * math.pi * i / 64),
                     f.world[2]) for i in range(64)]
        outer = project_polygon(proj.camera, disc(RING_OUTER_UU * fs))
        inner = project_polygon(proj.camera, disc(RING_INNER_UU * fs))
        if outer is None:
            continue
        ann = _poly_mask((w, h), [outer])
        if inner is not None:
            ann &= ~_poly_mask((w, h), [inner])
        team = "own" if f.fighter_id.startswith(own + "-") else "enemy"
        want = blue if team == "own" else red
        n, k = int(ann.sum()), int((ann & want).sum())
        xs = [p[0] for p in outer]
        ys = [p[1] for p in outer]
        rows.append({"fighter": f.fighter_id, "name": FIGHTER_NAMES.get(f.fighter_id, f.fighter_id),
                     "cell": list(f.cell), "team": team, "expected": "blue" if team == "own" else "red",
                     "screen": list(f.screen), "annulusBBox": [int(min(xs)), int(min(ys)), int(max(xs)) + 1,
                                                               int(max(ys)) + 1],
                     "annulusPx": n, "teamPx": k, "fraction": round(k / n, 4) if n else 0.0,
                     "yellowRingPx": int((ann & yellow).sum()),
                     "visible": bool(n and k / n >= RING_MIN_FRACTION)})
    return {"frame": rel(png), "trace": rel(trace), "client": client, "ownSide": own,
            "projection": {k: v for k, v in proj.to_dict().items()
                           if k in ("mode", "ok", "reason", "residual_max_px_used_camera", "tolerance_px")},
            "fighters": rows}


def label_metrics(png: Path, trace: Path) -> dict:
    import numpy as np
    from qa010lib import color as C
    from qa010lib.imageio import load_rgb
    rgb = load_rgb(png)
    h, w = rgb.shape[:2]
    text = _shot_block_text(trace, png.name)
    items = []
    for m in LABEL_LINE.finditer(text):
        items.append({"kind": "label", "fighter": m.group(1), "mode": m.group(2),
                      "bbox": [int(v) for v in m.groups()[2:]]})
    for m in DAMAGE_LINE.finditer(text):
        items.append({"kind": "damage", "fighter": m.group(1), "bbox": [int(v) for v in m.groups()[1:]]})
    for it in items:
        it["name"] = FIGHTER_NAMES.get(it["fighter"], it["fighter"])
        x0, y0, x1, y1 = it["bbox"]
        x0, y0, x1, y1 = max(0, x0), max(0, y0), min(w, x1), min(h, y1)
        px = rgb[y0:y1, x0:x1]
        luma = C.luma_u8(px)
        lum = C.relative_luminance(px)
        lab = C.linear_to_lab(C.u8_to_linear(px))
        ch = np.hypot(lab[..., 1], lab[..., 2])
        p99 = float(np.percentile(luma, 99))
        txt = (luma >= p99 - 6) & (ch < 12)
        # background = clearly-not-text pixels at least 2 px away from a text core (the anti-aliased letter
        # edges over a dark void would otherwise count as a light background)
        bg = (luma < p99 - 30) & ~_dilate(txt, 2)
        halves = {"whole": slice(0, y1 - y0)}
        if it["kind"] == "label" and it.get("mode") == "full":
            halves.update(name=slice(0, (y1 - y0) // 2), hp=slice((y1 - y0) // 2, y1 - y0))
        parts = {}
        for pn, sl in halves.items():
            t_, b_ = txt[sl], bg[sl]
            if not t_.any() or not b_.any():
                parts[pn] = {"textPx": int(t_.sum()), "bgPx": int(b_.sum()), "cr": None}
                continue
            lt = float(np.median(lum[sl][t_]))
            bl = luma[sl][b_]
            light = b_ & (luma[sl] >= 120)
            dark_share = float((bl < 60).mean())
            light_share = float((bl >= 120).mean())
            ref = float(np.median(lum[sl][light])) if light_share >= 0.1 else float(np.median(lum[sl][b_]))
            parts[pn] = {"textPx": int(t_.sum()), "textLuma": round(float(np.median(luma[sl][t_])), 1),
                         "bgPx": int(b_.sum()), "bgLumaMedian": round(float(np.median(bl)), 1),
                         "bgDarkShare": round(dark_share, 3), "bgLightShare": round(light_share, 3),
                         "cr": round(float(C.wcag_contrast_ratio(lt, ref)), 3),
                         "tileEdgeCrosses": bool(dark_share >= 0.1 and light_share >= 0.1)}
        it["parts"] = parts
        crs = [p["cr"] for k, p in parts.items() if k != "whole" and p.get("cr") is not None]
        if not crs and parts["whole"].get("cr") is not None:
            crs = [parts["whole"]["cr"]]
        worst = min(crs) if crs else None
        it["crWorst"] = worst
        it["crName"] = (parts.get("name") or {}).get("cr")
        it["crHp"] = (parts.get("hp") or {}).get("cr")
        it["tileEdgeCrosses"] = any(p.get("tileEdgeCrosses") for p in parts.values())
        it["verdict"] = ("no data" if worst is None else "AA" if worst >= TEXT_AA else
                         "AA-large only" if worst >= TEXT_AA_LARGE else "fail")
    for it in items:
        if it["kind"] != "damage":
            continue
        dx0, dy0, dx1, dy1 = it["bbox"]
        area = max(1, (dx1 - dx0) * (dy1 - dy0))
        hits = []
        for other in items:
            if other["kind"] != "label":
                continue
            lx0, ly0, lx1, ly1 = other["bbox"]
            iw, ih = min(dx1, lx1) - max(dx0, lx0), min(dy1, ly1) - max(dy0, ly0)
            if iw > 0 and ih > 0:
                hits.append({"label": other["name"], "shareOfDamageBbox": round(iw * ih / area, 3)})
        it["collidesWithLabels"] = hits
    return {"frame": rel(png), "trace": rel(trace), "items": items}


def cmd_readability_sheets(a) -> int:
    """Crop sheets for the eye (agent surrogate / user) from the per-board team-rings.json and
    labels-damage.json: every fighter's ring zone, every label and damage-number bbox."""
    from PIL import Image, ImageDraw
    evidence = Path(a.evidence).resolve()
    ana = evidence / "analysis"
    # rings: one row per board x frame, one column per fighter
    rows = []
    for key in BOARDS:
        p = ana / key / "team-rings.json"
        if not p.is_file():
            continue
        doc = json.loads(p.read_text(encoding="utf-8"))
        for tag, fr in doc["frames"].items():
            rows.append((key, tag, REPO / fr["frame"], sorted(fr["fighters"], key=lambda r: r["fighter"])))
    cw, chh, cap = 200, 120, 30
    sheet = Image.new("RGB", (6 * (cw + 4), len(rows) * (chh + cap)), (24, 24, 24))
    d = ImageDraw.Draw(sheet)
    for ri, (key, tag, png, fighters) in enumerate(rows):
        with Image.open(png) as im:
            im = im.convert("RGB")
            for ci, r in enumerate(fighters[:6]):
                x0, y0, x1, y1 = r["annulusBBox"]
                cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
                half_w, half_h = max(x1 - x0, 60) / 2 + 8, max(y1 - y0, 36) / 2 + 8
                crop = im.crop((int(cx - half_w), int(cy - half_h), int(cx + half_w), int(cy + half_h)))
                crop = crop.resize((cw, chh), Image.NEAREST)
                X, Y = ci * (cw + 4), ri * (chh + cap)
                sheet.paste(crop, (X, Y))
                col = (255, 255, 255) if r["visible"] else (255, 120, 120)
                d.text((X + 2, Y + chh + 2), f"{key.split('-')[0]} {tag} {r['name']} ({r['cell'][0]},{r['cell'][1]})",
                       fill=(220, 220, 220))
                d.text((X + 2, Y + chh + 15), f"{r['team']}/{r['expected']} {r['fraction']:.3f}"
                       + ("" if r["visible"] else "  NOT VISIBLE"), fill=col)
    ring_png = ana / "team-rings-crops.png"
    sheet.save(ring_png)
    # labels / damage numbers
    tiles = []
    for key in BOARDS:
        p = ana / key / "labels-damage.json"
        if not p.is_file():
            continue
        doc = json.loads(p.read_text(encoding="utf-8"))
        for tag, fr in doc["frames"].items():
            with Image.open(REPO / fr["frame"]) as im:
                im = im.convert("RGB")
                for it in fr["items"]:
                    x0, y0, x1, y1 = it["bbox"]
                    crop = im.crop((x0 - 4, y0 - 4, x1 + 4, y1 + 4))
                    crop = crop.resize((crop.width * 2, crop.height * 2), Image.NEAREST)
                    extra = ""
                    if it["kind"] == "damage" and it.get("collidesWithLabels"):
                        extra = " x " + ",".join(h["label"] for h in it["collidesWithLabels"])
                    tiles.append((crop, f"{key.split('-')[0]} {tag} {it['kind']} {it['name']}",
                                  f"{it['verdict']} {it['crWorst']}" + (" edge" if it["tileEdgeCrosses"] else "") + extra,
                                  it["verdict"] in ("AA",)))
    tw = max(t[0].width for t in tiles) + 4
    th = max(t[0].height for t in tiles) + 30
    cols = 5
    sheet = Image.new("RGB", (cols * tw, ((len(tiles) + cols - 1) // cols) * th), (60, 0, 60))
    d = ImageDraw.Draw(sheet)
    for i, (crop, l1, l2, ok) in enumerate(tiles):
        X, Y = (i % cols) * tw, (i // cols) * th
        sheet.paste(crop, (X, Y))
        d.text((X + 2, Y + crop.height + 2), l1, fill=(230, 230, 230))
        d.text((X + 2, Y + crop.height + 14), l2, fill=(160, 255, 160) if ok else (255, 150, 150))
    lab_png = ana / "labels-damage-crops.png"
    sheet.save(lab_png)
    L.write_json(ana / "readability-sheets.json", {
        "schema": "unmatched.t52-readability-sheets/1", "status": "листы для глаза (W5-live3), не замер",
        "teamRings": {"path": rel(ring_png), "layout": "строка = доска × кадр (K1_host, K1_joiner, K3); столбец = "
                      "боец; кроп вокруг кольцевой зоны, NEAREST; подпись: команда/ожидаемый цвет, доля; красным — "
                      f"доля < {RING_MIN_FRACTION}"},
        "labels": {"path": rel(lab_png), "layout": "bbox подписи или числа урона +4 px, ×2 NEAREST; подпись: вердикт "
                   "WCAG (худшая строка), 'edge' — край плитки режет подпись, 'x <имя>' — число урона пересекает "
                   "подпись"}})
    print(rel(ring_png), len(rows), rel(lab_png), len(tiles))
    return 0


# ------------------------------------------------------------------ main
def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    k = sub.add_parser("k3")
    k.add_argument("--label", required=True)
    k.add_argument("--evidence-dir", required=True)
    k.add_argument("--work", default=r"C:\tmp\t52\runs")
    k.add_argument("--board-id", required=True)
    k.add_argument("--variant", default="face-neck-v2", choices=["face-neck-v2", "head-tilt-v3"])
    k.add_argument("--run-seconds", type=int, default=240)
    k.add_argument("--client-fps", type=int, default=30)
    k.add_argument("--build-record", required=True)
    k.add_argument("--package-record", required=True)
    k.add_argument("--extra-demo-arg", action="append",
                   help="W5b-R: extra run-combat-demo.ps1 token per occurrence (use --extra-demo-arg=-Flag)")
    k.add_argument("--perf-status", default=None,
                   help="5c-B2: status text of perf.json (default: the W5b-R H2-background label)")
    k.add_argument("--concurrent-gpu-users", default=None,
                   help="5c-B2: free-text note of other GPU users during the run (perf.json)")
    rv = sub.add_parser("revalidate", help="recompute validation.json of a published combat run")
    rv.add_argument("run_dir")
    an = sub.add_parser("analyze", help="QA-010 measurements of one board")
    an.add_argument("--evidence", required=True, help="the T5.2 evidence dir (t52-thresholds.json inside)")
    an.add_argument("--board", required=True, choices=sorted(BOARDS))
    an.add_argument("--k1-run", required=True)
    an.add_argument("--k3-run", required=True)
    an.add_argument("--derived-root", default=r"C:\tmp\t52\derived", help="full-size derivatives (outside git)")
    ic = sub.add_parser("icon-crops", help="sheet of the traced icon bboxes of every K3 frame")
    ic.add_argument("--evidence", required=True)
    mi = sub.add_parser("mi", help="Medusa MI identity over every K1/K3 trace")
    mi.add_argument("--evidence", required=True)
    it = sub.add_parser("icon-template", help="icon mask template (method rev 2) from a K3 run, before 'analyze'")
    it.add_argument("--evidence", required=True)
    it.add_argument("--run", default=ICON_TEMPLATE_RUN, help="K3 run dir relative to the evidence dir")
    it.add_argument("--threshold", type=int, default=ICON_DIFF_THRESHOLD)
    er = sub.add_parser("errata-w5br", help="W5b-R errata of the T5.2 checklists (no re-measure)")
    er.add_argument("--evidence", required=True)
    rs = sub.add_parser("readability-sheets", help="crop sheets of team rings and labels (after 'analyze')")
    rs.add_argument("--evidence", required=True)
    a = ap.parse_args(argv)
    return {"k3": cmd_k3, "revalidate": cmd_revalidate, "analyze": cmd_analyze, "mi": cmd_mi,
            "icon-crops": cmd_icon_crops, "icon-template": cmd_icon_template,
            "readability-sheets": cmd_readability_sheets, "errata-w5br": cmd_errata_w5br}[a.cmd](a)


if __name__ == "__main__":
    sys.exit(main())
