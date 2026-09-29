#!/usr/bin/env python3
"""W4-C hybrid UMG HUD harness (user decision 2026-09-28 "HUD: hybrid UMG now").

Runs in the ART worktree. Subcommands:

  author    UnrealEditor-Cmd (art worktree project, -nullrhi, MCP auto-start
            off) -run=pythonscript tools/art/umg/ue_author_art_hud.py: builds
            WBP_S08ArtPlate / WBP_S08ArtIcon under /Game/S08/UI/ArtHud from
            the code default tree of US08ArtPlateWidget / US08ArtIconWidget
            (C++ US08ArtHudAuthoringLibrary), compiles and saves them; writes
            wbp-author.json (+ the in-editor report with sha256 of each
            .uasset). Never run against the main checkout (its GUI editor is live).
  compare   Reads packaged pair runs (tools/art/art004_live_k2.py run dirs) and
            writes the W4-C verdict JSON:
              - same-frame parity: every `SHOT widget` / `HUD sample=N SHOT
                widget` group of a compare-mode trace (-ArtHudImpl=compare):
                UMG part bbox vs Slate-twin part bbox, max edge difference
                <= 1 px, both geom=painted;
              - SHOT plate bbox = `SHOT widget id=plate` bbox of the shown view;
              - cross-run: SHOT plate / icon / label bboxes of UMG runs vs
                Slate runs of the same scenario (+-1 px);
              - delta GT: PERF summary scope=artHud gameMs p95, mean(UMG) -
                mean(Slate) per client role (<= 0.3 ms);
              - qa010 plate / marker gate results already written into each run
                (tools/art/art004_hud_t22.py qa <run>).

Statuses stay honest: a green verdict is "измерено / технически", never
"художественно принято".
"""
from __future__ import annotations

import argparse
import json
import os
import re
import statistics
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from art004_hud_t22 import (EDITOR_CMD, EDITOR_DLL, MCP_OFF, NO_WINDOW, REPO, UPROJECT, now_local,  # noqa: E402
                            rel, sha256_file, write_json)

AUTHOR_SCRIPT = REPO / "tools" / "art" / "umg" / "ue_author_art_hud.py"
WBP_DIR = REPO / "unreal" / "Unmatched" / "Content" / "S08" / "UI" / "ArtHud"

TS = re.compile(r"^\s*(\d{4}\.\d{2}\.\d{2}-\d{2}\.\d{2}\.\d{2})\s+(.*?)\s*$")
WIDGET = re.compile(
    r"^(?:HUD sample=(\d+) )?SHOT widget id=(\S+) impl=(umg|slate) state=(\S+) fighter=(\S+) "
    r"bbox=\((-?\d+),(-?\d+),(-?\d+),(-?\d+)\) geom=(painted|unpainted) visible=([01]) twin=([01]) source=(\S+)"
    r"(?: .*)?$")  # W5b-R: late lines append frame= (and tag/damage fields)
SHOT_PLATE = re.compile(r"^SHOT plate fighter=(\S+) bbox=\((-?\d+),(-?\d+),(-?\d+),(-?\d+)\) overlapReachable=(\d+)")
SHOT_ICON = re.compile(r"^SHOT icon fighter=(\S+) bbox=\((-?\d+),(-?\d+),(-?\d+),(-?\d+)\)")
SHOT_LABEL = re.compile(r"^SHOT label fighter=(\S+) mode=(\S+) bbox=\((-?\d+),(-?\d+),(-?\d+),(-?\d+)\)")
HUD_IMPL = re.compile(r"^HUD art impl=(\S+) plateViews=(\S+) iconViews=(\S+) textTable=(\S+) entries=(\d+) "
                      r"missingKeys=(\d+)")
PERF_ART = re.compile(r"^PERF summary scope=artHud impl=(\S+) .*?frames=(\d+) .*?frameMs avg=([\d.]+) .*? "
                      r"gpuMs avg=([\d.]+) p50=([\d.]+) p95=([\d.]+) gameMs avg=([\d.]+) p95=([\d.]+) "
                      r"renderMs avg=([\d.]+) p95=([\d.]+)")
PERF_ALT = re.compile(r"^PERF summary scope=(artHudUmg|artHudSlate) impl=(\S+) swaps=(\d+) periodS=([\d.]+) .*?"
                      r"frames=(\d+) .*?frameMs avg=([\d.]+) .*? gpuMs avg=([\d.]+) p50=([\d.]+) p95=([\d.]+) "
                      r"gameMs avg=([\d.]+) p95=([\d.]+) renderMs avg=([\d.]+) p95=([\d.]+)"
                      r"(?: gameP50=([\d.]+) gameP99=([\d.]+))?")
ALT_PERIOD = re.compile(r"^HUD alternate period=(\d+) impl=(umg|slate) frames=(\d+) gameAvg=([\d.]+) "
                        r"gameP50=([\d.]+) gameP95=([\d.]+) gpuP95=([\d.]+)")
ALT_CONFIG = re.compile(r"^HUD alternate config periodS=([\d.]+) startAt=([\d.]+) first=(\S+)")
PERF_WARM = re.compile(r"^PERF summary scope=afterWarmup .*? gameMs avg=([\d.]+) p95=([\d.]+)")
PLATE_TOL_PX = 1
GT_LIMIT_MS = 0.3


# ------------------------------------------------------------------ author
def cmd_author(a) -> int:
    out = Path(a.out).resolve()
    out.mkdir(parents=True, exist_ok=True)
    log = out / "wbp-author.log"
    report = out / "wbp-author-report.json"
    env = os.environ.copy()
    env["S08_WBP_REPORT"] = str(report)
    env["S08_WBP_OVERWRITE"] = "1" if a.overwrite else "0"
    args = [str(UPROJECT), "-run=pythonscript", f"-script={AUTHOR_SCRIPT}", "-unattended", "-nosplash", "-nullrhi",
            "-nullaudio", MCP_OFF, "-log", f"-abslog={log}"]
    started = time.time()
    r = subprocess.run([str(EDITOR_CMD)] + args, capture_output=True, text=True, encoding="utf-8",
                       errors="replace", timeout=a.timeout, creationflags=NO_WINDOW, env=env)
    text = log.read_text(encoding="utf-8", errors="replace") if log.is_file() else ""
    rec = {"schema": "unmatched.w4c-wbp-author/1", "startedLocal": now_local(),
           "durationS": round(time.time() - started, 1), "exitCode": r.returncode, "log": rel(log),
           "command": "UnrealEditor-Cmd <art uproject> -run=pythonscript -script=tools/art/umg/ue_author_art_hud.py "
                      "-unattended -nosplash -nullrhi -nullaudio (MCP auto-start off)",
           "why": "UWidgetBlueprint::WidgetTree is not reachable from Python and the UMGToolSet functions are "
                  "AICallable only; the tree is built by US08ArtHudAuthoringLibrary (C++, editor-only) from the "
                  "same BuildDefaultTree the widget classes use at runtime",
           "editorDll": {"path": rel(EDITOR_DLL), "sha256": sha256_file(EDITOR_DLL) if EDITOR_DLL.is_file() else None},
           "pass": re.findall(r"W4C_ART_HUD_WBP_PASS .*", text),
           "fail": re.findall(r"W4C_ART_HUD_WBP_FAIL .*", text),
           "pythonErrors": [ln for ln in text.splitlines() if "LogPython: Error" in ln][:30],
           "blueprintErrors": [ln for ln in text.splitlines() if re.search(r"LogBlueprint.*Error|Compile.*error", ln)][:30],
           "report": json.loads(report.read_text(encoding="utf-8")) if report.is_file() else None,
           "files": [{"path": rel(p), "bytes": p.stat().st_size, "sha256": sha256_file(p)}
                     for p in sorted(WBP_DIR.glob("*.uasset"))] if WBP_DIR.is_dir() else []}
    write_json(out / "wbp-author.json", rec)
    print(json.dumps({"exit": r.returncode, "pass": bool(rec["pass"]), "files": rec["files"],
                      "pythonErrors": len(rec["pythonErrors"])}, ensure_ascii=False))
    for ln in rec["pythonErrors"][:10] + rec["blueprintErrors"][:10]:
        print("  |", ln[:300])
    return 0 if r.returncode == 0 and rec["pass"] and not rec["fail"] else 1


# ----------------------------------------------------------------- compare
def payloads(trace: Path) -> list[str]:
    out = []
    for raw in trace.read_text(encoding="utf-8-sig", errors="replace").splitlines():
        m = TS.match(raw)
        out.append(m.group(2) if m else raw.strip())
    return out


def parse_trace(trace: Path) -> dict:
    """SHOT blocks (ctx .. requested) with plate/icon/label/widget lines, the HUD
    sample groups, the HUD impl line and the PERF artHud summary."""
    d = {"impl": None, "shots": [], "samples": {}, "perfArtHud": None, "perfAlt": {}, "afterWarmupGameMsP95": None,
         "swaps": 0}
    cur = None
    for p in payloads(trace):
        if (m := HUD_IMPL.match(p)):
            d["impl"] = {"impl": m.group(1), "plateViews": m.group(2), "iconViews": m.group(3),
                         "table": m.group(4), "entries": int(m.group(5)), "missingKeys": int(m.group(6))}
        elif p.startswith("SHOT ctx "):
            cur = {"widgets": [], "plate": None, "icon": None, "labels": {}}
        elif (m := WIDGET.match(p)):
            w = {"id": m.group(2), "impl": m.group(3), "state": m.group(4), "fighter": m.group(5),
                 "bbox": [int(m.group(i)) for i in range(6, 10)], "geom": m.group(10),
                 "visible": m.group(11) == "1", "twin": m.group(12) == "1", "source": m.group(13)}
            if m.group(1):
                d["samples"].setdefault(int(m.group(1)), []).append(w)
            elif cur is not None:
                cur["widgets"].append(w)
        elif cur is not None and (m := SHOT_PLATE.match(p)):
            cur["plate"] = {"fighter": m.group(1), "bbox": [int(m.group(i)) for i in range(2, 6)],
                            "overlapReachable": int(m.group(6))}
        elif cur is not None and (m := SHOT_ICON.match(p)):
            cur["icon"] = {"fighter": m.group(1), "bbox": [int(m.group(i)) for i in range(2, 6)]}
        elif cur is not None and (m := SHOT_LABEL.match(p)):
            cur["labels"][m.group(1)] = {"mode": m.group(2), "bbox": [int(m.group(i)) for i in range(3, 7)]}
        elif cur is not None and p.startswith("SHOT requested"):
            cur["file"] = re.split(r"[\\/]", p.split("->", 1)[-1].strip())[-1]
            d["shots"].append(cur)
            cur = None
        elif (m := PERF_ALT.match(p)):
            d["perfAlt"][m.group(2)] = {"swaps": int(m.group(3)), "periodS": float(m.group(4)),
                                        "frames": int(m.group(5)), "frameMsAvg": float(m.group(6)),
                                        "gpuMsAvg": float(m.group(7)), "gpuMsP95": float(m.group(9)),
                                        "gameMsAvg": float(m.group(10)), "gameMsP95": float(m.group(11)),
                                        "renderMsAvg": float(m.group(12)), "renderMsP95": float(m.group(13)),
                                        "gameMsP50": float(m.group(14)) if m.group(14) else None,
                                        "gameMsP99": float(m.group(15)) if m.group(15) else None}
        elif (m := ALT_PERIOD.match(p)):
            d.setdefault("periods", []).append({"period": int(m.group(1)), "impl": m.group(2),
                                                "frames": int(m.group(3)), "gameAvg": float(m.group(4)),
                                                "gameP50": float(m.group(5)), "gameP95": float(m.group(6)),
                                                "gpuP95": float(m.group(7))})
        elif (m := ALT_CONFIG.match(p)):
            d["alternateConfig"] = {"periodS": float(m.group(1)), "startAt": float(m.group(2)), "first": m.group(3)}
        elif p.startswith("HUD alternate swap="):
            d["swaps"] += 1
        elif (m := PERF_WARM.match(p)):
            d["afterWarmupGameMsP95"] = float(m.group(2))
        elif (m := PERF_ART.match(p)):
            d["perfArtHud"] = {"impl": m.group(1), "frames": int(m.group(2)), "frameMsAvg": float(m.group(3)),
                               "gpuMsAvg": float(m.group(4)), "gpuMsP95": float(m.group(6)),
                               "gameMsAvg": float(m.group(7)), "gameMsP95": float(m.group(8)),
                               "renderMsAvg": float(m.group(9)), "renderMsP95": float(m.group(10))}
    return d


def edge_diff(a: list[int], b: list[int]) -> int:
    return max(abs(x - y) for x, y in zip(a, b))


def pair_group(widgets: list[dict]) -> dict:
    """UMG (shown) vs Slate twin, per part id, inside one frame."""
    shown = {w["id"]: w for w in widgets if w["impl"] == "umg" and not w["twin"]}
    twin = {w["id"]: w for w in widgets if w["impl"] == "slate" and w["twin"]}
    parts = {}
    for pid in sorted(set(shown) | set(twin)):
        a, b = shown.get(pid), twin.get(pid)
        if not a or not b:
            parts[pid] = {"error": f"missing {'umg' if not a else 'slate twin'}"}
            continue
        painted = a["geom"] == "painted" and b["geom"] == "painted"
        dd = edge_diff(a["bbox"], b["bbox"])
        parts[pid] = {"umg": a["bbox"], "slate": b["bbox"], "maxEdgeDiffPx": dd, "painted": painted,
                      "pass": painted and dd <= PLATE_TOL_PX}
    return parts


def pixel_diff(run_a: Path, run_b: Path, role: str, shot_a: dict, shot_b: dict) -> dict:
    """Informative: the same plate / icon boxes in the UMG and the Slate frame of
    two runs (different processes, so the 3D scene under a translucent-free
    widget can still differ by Lumen / TSR noise; the whole frame is the noise
    reference). Opaque widget pixels are expected to be identical."""
    try:
        from PIL import Image, ImageChops
    except ImportError:
        return {"error": "PIL missing"}
    fa = run_a / f"phase2-board-{role}-1920x1080.png"
    fb = run_b / f"phase2-board-{role}-1920x1080.png"
    if not (fa.is_file() and fb.is_file()):
        return {"error": "frame missing"}
    ia, ib = Image.open(fa).convert("RGB"), Image.open(fb).convert("RGB")
    out = {"frames": [rel(fa), rel(fb)]}

    def stats(box):
        ca, cb = ia.crop(box), ib.crop(box)
        diff = ImageChops.difference(ca, cb)
        px = list(diff.getdata())
        n = len(px) or 1
        return {"box": list(box), "pixels": n, "identical": sum(1 for p in px if p == (0, 0, 0)) / n,
                "meanAbs": round(sum(sum(p) for p in px) / (3 * n), 3), "maxAbs": max((max(p) for p in px), default=0)}
    for key in ("plate", "icon"):
        if shot_a[key] and shot_b[key] and shot_a[key]["bbox"] == shot_b[key]["bbox"]:
            out[key] = stats(tuple(shot_a[key]["bbox"]))
    if shot_a["plate"]:
        x0, y0, x1, y1 = shot_a["plate"]["bbox"]
        out["plateMarkerStrip"] = stats((x0, y0, x1, y0 + 3))
    out["wholeFrame"] = stats((0, 0, ia.width, ia.height))
    return out


def role_of(trace: Path) -> str:
    return "host" if "host" in trace.name else "joiner" if "joiner" in trace.name else trace.stem


def cmd_compare(a) -> int:
    runs = []
    for rd in map(Path, a.run_dirs):
        rd = rd.resolve()
        rec = {"run": rel(rd), "clients": {}}
        for trace in sorted(rd.glob("phase2-client-*.trace.log")):
            rec["clients"][role_of(trace)] = parse_trace(trace)
        qa = rd / "qa010" / "qa-summary.json"
        if qa.is_file():
            q = json.loads(qa.read_text(encoding="utf-8"))
            rec["qa010"] = {"plate": q["commands"]["plate"]["result"], "icon": q["commands"]["icon"]["result"],
                            "plateCrossCheck": (q["commands"]["plate"].get("clientCrossCheck") or {}).get("agree"),
                            "markerGate": q.get("plateMarkerGate", {}).get("passed"),
                            "markerStrip": [q.get("plateMarkerGate", {}).get(k) for k in
                                            ("stripInside", "stripExpected", "outside")]}
        rr = rd / "run-record.json"
        if rr.is_file():
            r = json.loads(rr.read_text(encoding="utf-8"))
            rec["argv"] = r.get("argv")
            rec["zoom"] = r.get("zoom")
        runs.append(rec)

    verdict = {"schema": "unmatched.w4c-hud-compare/1", "checkedLocal": now_local(),
               "status": "измерено (технически); художественно не принято", "tolerancePx": PLATE_TOL_PX,
               "runs": []}
    same_frame = {"frames": 0, "parts": 0, "failures": [], "maxEdgeDiffPx": 0}
    by_impl: dict[str, list[dict]] = {}
    for rec in runs:
        row = {"run": rec["run"], "zoom": rec.get("zoom"), "qa010": rec.get("qa010"), "clients": {}}
        for role, d in rec["clients"].items():
            impl = (d["impl"] or {}).get("impl")
            crow = {"impl": d["impl"], "shots": len(d["shots"]), "perfArtHud": d["perfArtHud"],
                    "samples": len(d["samples"])}
            if impl == "compare":
                groups = [("shot:" + s.get("file", "?"), s["widgets"]) for s in d["shots"] if s["widgets"]]
                groups += [(f"sample:{k}", v) for k, v in sorted(d["samples"].items())]
                crow["frames"] = []
                for name, widgets in groups:
                    parts = pair_group(widgets)
                    same_frame["frames"] += 1
                    for pid, pr in parts.items():
                        same_frame["parts"] += 1
                        if "maxEdgeDiffPx" in pr:
                            same_frame["maxEdgeDiffPx"] = max(same_frame["maxEdgeDiffPx"], pr["maxEdgeDiffPx"])
                        if not pr.get("pass"):
                            same_frame["failures"].append({"run": rec["run"], "role": role, "frame": name,
                                                           "part": pid, **pr})
                    crow["frames"].append({"frame": name, "parts": parts})
            # SHOT plate line = shown view's `SHOT widget id=plate` (same frame).
            consistency = []
            for s in d["shots"]:
                if s["plate"]:
                    shown = next((w for w in s["widgets"] if w["id"] == "plate" and not w["twin"]), None)
                    consistency.append({"file": s.get("file"), "shotPlate": s["plate"]["bbox"],
                                        "widgetPlate": shown["bbox"] if shown else None,
                                        "equal": bool(shown and shown["bbox"] == s["plate"]["bbox"])})
            crow["plateLineConsistency"] = consistency
            row["clients"][role] = crow
            if impl:
                by_impl.setdefault(impl, []).append({"run": rec["run"], "role": role, "zoom": rec.get("zoom"),
                                                     "trace": d})
        verdict["runs"].append(row)
    verdict["sameFrameParity"] = {**same_frame, "pass": same_frame["frames"] > 0 and not same_frame["failures"]}

    # Cross-run: UMG vs Slate runs of the same zoom (world labels and the placement are deterministic).
    cross = []
    for u in by_impl.get("umg", []):
        for s in by_impl.get("slate", []):
            if u["role"] != s["role"] or u["zoom"] != s["zoom"]:
                continue
            us, ss = (u["trace"]["shots"] or [None])[-1], (s["trace"]["shots"] or [None])[-1]
            if not us or not ss:
                continue
            item = {"umgRun": u["run"], "slateRun": s["run"], "role": u["role"], "zoom": u["zoom"], "checks": []}
            for key in ("plate", "icon"):
                if us[key] and ss[key]:
                    dd = edge_diff(us[key]["bbox"], ss[key]["bbox"])
                    item["checks"].append({"what": key, "umg": us[key]["bbox"], "slate": ss[key]["bbox"],
                                           "maxEdgeDiffPx": dd, "pass": dd <= PLATE_TOL_PX})
            # World labels are TextRender in the scene (not HUD widgets): informative only.
            item["labels"] = [{"fighter": fid, "umg": us["labels"][fid]["bbox"], "slate": ss["labels"][fid]["bbox"],
                               "maxEdgeDiffPx": edge_diff(us["labels"][fid]["bbox"], ss["labels"][fid]["bbox"])}
                              for fid in sorted(set(us["labels"]) & set(ss["labels"]))]
            if not item["checks"]:
                continue  # joiner at K1: no plate / icon on its frame
            item["pass"] = all(c["pass"] for c in item["checks"])
            item["pixels"] = pixel_diff(REPO / u["run"], REPO / s["run"], u["role"], us, ss)
            cross.append(item)
    # World-label reference: the same label across ALL 5x host shots of every implementation.
    label_sets: dict[str, dict] = {}
    for impl, rows in by_impl.items():
        for x in rows:
            if x["role"] != "host" or x["zoom"] != 5.0 or not x["trace"]["shots"]:
                continue
            for fid, lab in x["trace"]["shots"][-1]["labels"].items():
                label_sets.setdefault(fid, {}).setdefault(tuple(lab["bbox"]), []).append(f"{impl}:{Path(x['run']).name}")
    verdict["crossRun"] = {"pairs": cross, "pass": bool(cross) and all(c["pass"] for c in cross),
                           "gates": "plate and icon bbox of the shown view, UMG run vs Slate run (+-1 px)",
                           "worldLabelsInformative": {fid: {str(list(k)): v for k, v in boxes.items()}
                                                      for fid, boxes in sorted(label_sets.items())},
                           "worldLabelsNote": "SHOT label boxes are world TextRender labels drawn by the scene for "
                                              "both implementations (on a compare frame both views share them); their "
                                              "run-to-run variation is the pre-existing label zoom-ratio hysteresis "
                                              "(AS08FighterActor::SetLabelZoomRatio, 0.01 dead band), not the HUD view"}

    # Delta GT (game thread) p95 with the plate on screen.
    # Decisive: same-process A/B (-ArtHudImpl=alternate: the UMG pair and the
    # Slate pair swap every few seconds in ONE client; the first frames after a
    # swap are skipped by the client). Supplementary: separate umg / slate runs
    # (between-process drift shows in afterWarmup, which includes pre-plate frames).
    alt = []
    for x in by_impl.get("alternate", []):
        pa = x["trace"]["perfAlt"]
        if "umg" in pa and "slate" in pa and pa["umg"]["frames"] > 0 and pa["slate"]["frames"] > 0:
            alt.append({"run": x["run"], "role": x["role"], "swaps": pa["umg"]["swaps"],
                        "umg": pa["umg"], "slate": pa["slate"],
                        "deltaGameMsP95": round(pa["umg"]["gameMsP95"] - pa["slate"]["gameMsP95"], 3),
                        "deltaGameMsAvg": round(pa["umg"]["gameMsAvg"] - pa["slate"]["gameMsAvg"], 3),
                        "deltaGameMsP50": (round(pa["umg"]["gameMsP50"] - pa["slate"]["gameMsP50"], 3)
                                           if pa["umg"].get("gameMsP50") is not None else None),
                        "config": x["trace"].get("alternateConfig"),
                        "deltaGpuMsP95": round(pa["umg"]["gpuMsP95"] - pa["slate"]["gpuMsP95"], 3)})
    alt_host = [a for a in alt if a["role"] == "host"]
    alt_mean = round(statistics.mean(a["deltaGameMsP95"] for a in alt_host), 3) if alt_host else None
    # Paired periods: (1,2), (3,4), ... adjacent periods of the two implementations
    # inside one client, so a burst of external CPU load hits both halves of a
    # pair alike; the median over pairs is robust to the bursts that remain.
    pairs = []
    for x in by_impl.get("alternate", []):
        if x["role"] != "host":
            continue
        per = sorted(x["trace"].get("periods", []), key=lambda q: q["period"])
        for i in range(0, len(per) - 1, 2):
            first, second = per[i], per[i + 1]
            if first["impl"] == second["impl"] or min(first["frames"], second["frames"]) < 30:
                continue
            u, sl = (first, second) if first["impl"] == "umg" else (second, first)
            pairs.append({"run": Path(x["run"]).name, "periods": [first["period"], second["period"]],
                          "dP95": round(u["gameP95"] - sl["gameP95"], 3), "dP50": round(u["gameP50"] - sl["gameP50"], 3),
                          "dAvg": round(u["gameAvg"] - sl["gameAvg"], 3), "dGpuP95": round(u["gpuP95"] - sl["gpuP95"], 3)})
    paired = None
    if pairs:
        paired = {"pairs": len(pairs), "medianDP95": round(statistics.median(p["dP95"] for p in pairs), 3),
                  "meanDP95": round(statistics.mean(p["dP95"] for p in pairs), 3),
                  "medianDP50": round(statistics.median(p["dP50"] for p in pairs), 3),
                  "medianDAvg": round(statistics.median(p["dAvg"] for p in pairs), 3),
                  "medianDGpuP95": round(statistics.median(p["dGpuP95"] for p in pairs), 3),
                  "share_dP95_le_0p3": round(sum(1 for p in pairs if p["dP95"] <= GT_LIMIT_MS) / len(pairs), 3),
                  "list": pairs}
    gt = {}
    for role in ("host", "joiner"):
        vals = {impl: [x["trace"]["perfArtHud"]["gameMsP95"] for x in by_impl.get(impl, [])
                       if x["role"] == role and x["trace"]["perfArtHud"] and x["trace"]["perfArtHud"]["frames"] > 0]
                for impl in ("umg", "slate")}
        warm = {impl: [x["trace"]["afterWarmupGameMsP95"] for x in by_impl.get(impl, [])
                       if x["role"] == role and x["trace"]["perfArtHud"] and x["trace"]["perfArtHud"]["frames"] > 0]
                for impl in ("umg", "slate")}
        if vals["umg"] and vals["slate"]:
            delta = statistics.mean(vals["umg"]) - statistics.mean(vals["slate"])
            gt[role] = {"umgGameMsP95": vals["umg"], "slateGameMsP95": vals["slate"],
                        "deltaMs": round(delta, 3), "afterWarmupGameMsP95": warm,
                        "note": "separate processes: informative only (drift)"}
    verdict["deltaGtP95"] = {"pairedPeriods": paired, "sameProcess": alt, "sameProcessHostMeanDeltaMs": alt_mean,
                             "limitMs": GT_LIMIT_MS, "separateRuns": gt,
                             "pass": bool(paired) and paired["medianDP95"] <= GT_LIMIT_MS,
                             "pooledPass": alt_mean is not None and alt_mean <= GT_LIMIT_MS,
                             "rule": "primary: median over paired adjacent alternate periods (host) of gameMs "
                                     "p95(umg) - p95(slate) <= 0.3 ms; reported next to it: the pooled per-run p95 "
                                     "delta (pooledPass) and the separate-process runs; the joiner (K1, no "
                                     "selection) has no plate frames"}
    qa = [r.get("qa010") for r in runs if r.get("qa010")]
    verdict["qa010Plate"] = {"runs": len(qa), "pass": bool(qa) and all(q["plate"] == "pass" for q in qa),
                             "markerGatePass": bool(qa) and all(q["markerGate"] for q in qa)}
    verdict["pass"] = all(verdict[k]["pass"] for k in ("sameFrameParity", "crossRun", "deltaGtP95", "qa010Plate"))
    write_json(Path(a.out), verdict)
    print(json.dumps({k: verdict[k]["pass"] if isinstance(verdict[k], dict) and "pass" in verdict[k] else None
                      for k in ("sameFrameParity", "crossRun", "deltaGtP95", "qa010Plate")} |
                     {"frames": same_frame["frames"], "parts": same_frame["parts"],
                      "maxEdgeDiffPx": same_frame["maxEdgeDiffPx"], "gtSameProcess": alt_mean,
                      "gtPairedMedian": paired and paired["medianDP95"],
                      "gtSeparate": {k: v["deltaMs"] for k, v in gt.items()},
                      "pass": verdict["pass"]}, ensure_ascii=False))
    return 0 if verdict["pass"] else 1


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    au = sub.add_parser("author")
    au.add_argument("--out", required=True)
    au.add_argument("--overwrite", action="store_true", help="rebuild the tree of existing WBPs")
    au.add_argument("--timeout", type=int, default=900)
    co = sub.add_parser("compare")
    co.add_argument("--out", required=True)
    co.add_argument("run_dirs", nargs="+")
    a = ap.parse_args(argv)
    return {"author": cmd_author, "compare": cmd_compare}[a.cmd](a)


if __name__ == "__main__":
    sys.exit(main())
