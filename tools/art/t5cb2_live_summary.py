#!/usr/bin/env python3
"""Wave 5c-B2 (RUNS stage): trace-level summary of packaged-live run directories.

Reads only what the run harnesses published (tools/art/art004_live_k2.py run -> run-phase2-demo,
tools/art/t52_art3_live.py k3 -> run-combat-demo): run-record.json, perf.json, the *.evidence.json
sidecars and the two client traces. Writes one JSON with, per run and per client:

  * render fingerprint of every SHOT (count, reference=1 count, expMin / ev100 / profile values);
  * 'SHOT captured' lines (pixel provenance);
  * heroes v2 (-ArtPreviewHeroesV2): the summary line, every 'ARTPREVIEW heroesV2 fighter=' line
    (mesh, MI, yaw, scale, clips, boundsTop), the 'missing=' fallbacks and every
    'ARTPREVIEW anim' clip event (Idle / LungeAttack / HitReact / DeathSettle, death hold / hidden);
  * the diorama tray line (-ArtPreviewDiorama);
  * K2 camera (focus request, settled distance, zoom) and the SHOT head projection;
  * game state: max applied seq, GAME_OVER / RESULT winner, FINISHED, damage CUEs, fighters alive;
  * client perf: 'PERF summary' (phase2) or the aggregate of the 5 s 'PERF window' samples (combat,
    the duel exits right after GAME_OVER, so no exit summary is guaranteed);
  * perf.json GPU total (nvidia-smi) of the pair.

Statuses stay 'измерено': nothing here is an artistic acceptance.

  python tools/art/t5cb2_live_summary.py --out <summary.json> <run dir> [<run dir> ...]
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]

TS = re.compile(r"^(\d{4})\.(\d{2})\.(\d{2})-(\d{2})\.(\d{2})\.(\d{2})")
RENDER_SHOT = re.compile(r"RENDER tag=SHOT .*?expMin=([\d.]+) .*?ev100=([\d.-]+) .*?profile=(\S+) .*reference=(\d)")
SHOT_CAPTURED = re.compile(r"SHOT captured file=(\S+) frame=(\d+) px=(\d+)x(\d+) sha256=([0-9a-f]{64}) order=BGRA saved=1")
V2_SUMMARY = re.compile(r"ARTPREVIEW heroesV2 summary (.*)$")
V2_FIGHTER = re.compile(r"ARTPREVIEW heroesV2 fighter=(\S+) mesh=(\S+) mi=(\S+) yaw=([-\d.]+) scale=([\d.]+) name=(.+?) "
                        r"hero=(\d) look=(\S+) base=(\S+) baseMi=(\S+) skeleton=(\S+) clips=(\d+)/4 boundsTop=([-\d.]+) "
                        r"figureTop=([-\d.]+) budget=([-\d.]+)")
V2_MISSING = re.compile(r"ARTPREVIEW (heroesV2 fighter=\S+ missing=\S+|anim fighter=\S+ clip=\S+ missing=1.*)")
ANIM = re.compile(r"ARTPREVIEW anim fighter=(\S+) clip=(\S+) len=([\d.]+) event=(\S+) loop=(\d) phase=([-\d.]+) seq=(-?\d+)")
DEATH_HOLD = re.compile(r"ARTPREVIEW anim fighter=(\S+) death hold=([\d.]+)")
DEATH_HIDDEN = re.compile(r"ARTPREVIEW anim fighter=(\S+) death hidden=(\d)")
TRAY = re.compile(r"ARTPREVIEW diorama tray=(\S+) mi=(\S+) surface=(\S+) yaw=([-\d.]+) .*size=(\S+) topZ=([-\d.]+) "
                  r"boardHalf=(\S+) rimUU=([-\d.]+)")
TRAY_MISSING = re.compile(r"ARTPREVIEW diorama tray (missing|hidden).*")
MEDUSA_VISUAL = re.compile(r"visual=1 mesh=(SK_\S+)")
SEQ = re.compile(r"SNAPSHOT applied seq=(\d+)")
RESULT = re.compile(r"RESULT seq=(\d+) outcome=(\w+) winner=(.+)$")
FINISHED = re.compile(r"status=FINISHED")
CUE = re.compile(r"CUE damage (\S+) -(\d+) seq=(\d+)")
COMBAT_RESULT = re.compile(r"COMBAT-RESULT seq=(\d+) damage=(-?\d+)")
ALIVE = re.compile(r"FIGHTERS synced n=(\d+) alive=(\d+)")
CAM_FOCUS = re.compile(r"CAMERA focus src=flag from=([\d.]+) to=([\d.]+) requested=([\d.]+) zoom=([\d.]+) clamp=(\d)")
CAM_SETTLED = re.compile(r"CAMERA settled elapsed=([\d.]+) dist=([\d.]+) target=([\d.]+)")
SHOT_HEAD = re.compile(r"SHOT head fighter=(\S+) socket=(\S+) mesh=(\S+) .*?headPx=([\d.]+)")
SHOT_REQ = re.compile(r"SHOT requested: .*[\\/]([^\\/]+\.png)\s*$")
PERF_SUMMARY = re.compile(r"PERF summary scope=(\w+)(?: impl=\w+)? (?:warmup=\d+ )?elapsed=([\d.]+) frames=(\d+) fps=([\d.]+) "
                          r"frameMs avg=([\d.]+) p50=([\d.]+) p95=([\d.]+) p99=([\d.]+) max=([\d.]+) hitches50=(\d+) "
                          r"gpuMs avg=([\d.]+) p50=([\d.]+) p95=([\d.]+)")
PERF_WINDOW = re.compile(r"PERF window t=([\d.]+)-([\d.]+) frames=(\d+) fps=([\d.]+) frameMs avg=([\d.]+) p50=([\d.]+) "
                         r"p95=([\d.]+) p99=([\d.]+) max=([\d.]+) hitches50=(\d+) gpuMs avg=([\d.]+) p50=([\d.]+) p95=([\d.]+)")


def rel(p: Path) -> str:
    try:
        return p.resolve().relative_to(REPO).as_posix()
    except ValueError:
        return p.as_posix()


def ts_seconds(line: str) -> int | None:
    m = TS.match(line)
    if not m:
        return None
    y, mo, d, h, mi, s = (int(x) for x in m.groups())
    return ((d * 24 + h) * 60 + mi) * 60 + s


def pct(vals: list[float], q: float) -> float | None:
    if not vals:
        return None
    v = sorted(vals)
    k = (len(v) - 1) * q
    lo, hi = int(k), min(int(k) + 1, len(v) - 1)
    return round(v[lo] + (v[hi] - v[lo]) * (k - lo), 3)


def trace_summary(tp: Path) -> dict:
    lines = tp.read_text(encoding="utf-8", errors="replace").splitlines()
    t = [ts_seconds(x) for x in lines if ts_seconds(x) is not None]
    out: dict = {"trace": rel(tp), "sessionS": (t[-1] - t[0]) if t else None}
    renders = [RENDER_SHOT.search(x) for x in lines]
    renders = [m for m in renders if m]
    out["render"] = {"shots": len(renders), "reference1": sum(1 for m in renders if m.group(4) == "1"),
                     "expMin": sorted({m.group(1) for m in renders}), "ev100": sorted({m.group(2) for m in renders}),
                     "profiles": sorted({m.group(3) for m in renders})}
    out["shotRequested"] = [m.group(1) for m in (SHOT_REQ.search(x) for x in lines) if m]
    out["shotCaptured"] = [{"file": m.group(1), "frame": int(m.group(2)), "px": f"{m.group(3)}x{m.group(4)}",
                            "sha256": m.group(5)} for m in (SHOT_CAPTURED.search(x) for x in lines) if m]
    # heroes v2
    summ = [m.group(1) for m in (V2_SUMMARY.search(x) for x in lines) if m]
    fighters = {}
    for m in (V2_FIGHTER.search(x) for x in lines):
        if m and m.group(1) in fighters:  # re-applied on a move: keep the spawn line, log the yaw history
            fighters[m.group(1)]["yawHistory"].append(float(m.group(4)))
        elif m:
            fighters[m.group(1)] = {"yawHistory": [float(m.group(4))],"mesh": m.group(2).rsplit("/", 1)[-1].split(".")[0], "meshPath": m.group(2),
                                    "mi": m.group(3).rsplit("/", 1)[-1].split(".")[0], "yaw": float(m.group(4)),
                                    "scale": float(m.group(5)), "name": m.group(6), "hero": int(m.group(7)),
                                    "look": m.group(8), "base": m.group(9).rsplit("/", 1)[-1].split(".")[0],
                                    "clips": int(m.group(12)), "boundsTop": float(m.group(13))}
    anim = []
    for m in (ANIM.search(x) for x in lines):
        if m:
            anim.append({"fighter": m.group(1), "clip": m.group(2), "len": float(m.group(3)), "event": m.group(4),
                         "loop": int(m.group(5)), "phase": float(m.group(6)), "seq": int(m.group(7))})
    counts: dict = {}
    for a in anim:
        k = f"{a['clip']}/{a['event']}"
        counts[k] = counts.get(k, 0) + 1
    idle_fighters = sorted({a["fighter"] for a in anim if a["clip"] == "Idle"})
    out["heroesV2"] = {
        "summaryLines": sorted(set(summ)),
        "figures": len(fighters),
        "fighters": fighters,
        "yaws": sorted({y for f in fighters.values() for y in f["yawHistory"]}),
        "spawnYaws": {k: f["yaw"] for k, f in fighters.items()},
        "missing": sorted({m.group(1) for m in (V2_MISSING.search(x) for x in lines) if m}),
        "idleFighters": len(idle_fighters),
        "animCounts": counts,
        "clipLens": {c: sorted({a["len"] for a in anim if a["clip"] == c}) for c in sorted({a["clip"] for a in anim})},
        "combatAnim": [a for a in anim if a["clip"] != "Idle" or a["event"] != "spawn"],
        "deathHold": [{"fighter": m.group(1), "hold": float(m.group(2))} for m in (DEATH_HOLD.search(x) for x in lines) if m],
        "deathHidden": [{"fighter": m.group(1), "hidden": int(m.group(2))} for m in (DEATH_HIDDEN.search(x) for x in lines) if m],
    } if (summ or fighters or anim) else None
    trays = [m for m in (TRAY.search(x) for x in lines) if m]
    out["diorama"] = ({"tray": trays[-1].group(1).rsplit("/", 1)[-1], "mi": trays[-1].group(2).rsplit("/", 1)[-1],
                       "surface": trays[-1].group(3), "size": trays[-1].group(5), "topZ": float(trays[-1].group(6)),
                       "boardHalf": trays[-1].group(7), "rimUU": float(trays[-1].group(8)), "lines": len(trays),
                       "missingOrHidden": sorted({m.group(0) for m in (TRAY_MISSING.search(x) for x in lines) if m})}
                      if trays or any(TRAY_MISSING.search(x) for x in lines) else None)
    out["medusaVisualMeshes"] = sorted({m.group(1) for m in (MEDUSA_VISUAL.search(x) for x in lines) if m})
    # K2 camera and head
    foc = [m for m in (CAM_FOCUS.search(x) for x in lines) if m]
    st = [m for m in (CAM_SETTLED.search(x) for x in lines) if m]
    heads = [m for m in (SHOT_HEAD.search(x) for x in lines) if m]
    out["camera"] = {"focus": ({"from": float(foc[-1].group(1)), "to": float(foc[-1].group(2)),
                                "zoom": float(foc[-1].group(4)), "clamp": int(foc[-1].group(5))} if foc else None),
                     "settled": ({"elapsed": float(st[-1].group(1)), "dist": float(st[-1].group(2))} if st else None),
                     "shotHeadMedusa": next(({"fighter": m.group(1), "mesh": m.group(3), "headPx": float(m.group(4))}
                                             for m in reversed(heads) if "Medusa" in m.group(3)), None),
                     "shotHeads": len(heads)}
    # game state
    seqs = [int(m.group(1)) for m in (SEQ.search(x) for x in lines) if m]
    res = [m for m in (RESULT.search(x) for x in lines) if m]
    alive = [(int(m.group(1)), int(m.group(2))) for m in (ALIVE.search(x) for x in lines) if m]
    cues = [(m.group(1), int(m.group(2)), int(m.group(3))) for m in (CUE.search(x) for x in lines) if m]
    out["game"] = {"maxSeq": max(seqs) if seqs else None,
                   "result": ({"seq": int(res[-1].group(1)), "outcome": res[-1].group(2), "winner": res[-1].group(3)}
                              if res else None),
                   "finishedSeen": any(FINISHED.search(x) for x in lines),
                   "damageCues": len(set(cues)), "cues": sorted(set(cues), key=lambda c: c[2]),
                   "combatResults": sorted({(int(m.group(1)), int(m.group(2))) for m in (COMBAT_RESULT.search(x) for x in lines) if m}),
                   "minAlive": min((a for _, a in alive), default=None),
                   "fightersN": sorted({n for n, _ in alive})}
    # perf
    summaries = {}
    for m in (PERF_SUMMARY.search(x) for x in lines):
        if m:
            summaries[m.group(1)] = {"elapsed": float(m.group(2)), "frames": int(m.group(3)), "fps": float(m.group(4)),
                                     "frameMsP50": float(m.group(6)), "frameMsP95": float(m.group(7)),
                                     "frameMsMax": float(m.group(9)), "hitches50": int(m.group(10)),
                                     "gpuMsP50": float(m.group(12)), "gpuMsP95": float(m.group(13))}
    wins = [m for m in (PERF_WINDOW.search(x) for x in lines) if m]
    out["perf"] = {"summary": summaries,
                   "windows": {"n": len(wins),
                               "span": [float(wins[0].group(1)), float(wins[-1].group(2))] if wins else None,
                               "fpsMedian": pct([float(m.group(4)) for m in wins], 0.5),
                               "fpsMin": min((float(m.group(4)) for m in wins), default=None),
                               "frameMsP50Median": pct([float(m.group(6)) for m in wins], 0.5),
                               "frameMsP95Median": pct([float(m.group(7)) for m in wins], 0.5),
                               "frameMsP95Max": max((float(m.group(7)) for m in wins), default=None),
                               "gpuMsP50Median": pct([float(m.group(12)) for m in wins], 0.5),
                               "gpuMsP95Median": pct([float(m.group(13)) for m in wins], 0.5),
                               "gpuMsP95Max": max((float(m.group(13)) for m in wins), default=None),
                               "hitches50": sum(int(m.group(10)) for m in wins)}}
    return out


def run_summary(run: Path) -> dict:
    rr = json.loads((run / "run-record.json").read_text(encoding="utf-8")) if (run / "run-record.json").is_file() else {}
    kind = "combat" if list(run.glob("combat-client-*.trace.log")) else "phase2"
    traces = {side: (run / f"{'combat' if kind == 'combat' else 'phase2'}-client-{side}.trace.log") for side in ("host", "joiner")}
    side = next(iter(sorted(run.rglob("*.evidence.json"))), None)
    sd = json.loads(side.read_text(encoding="utf-8")) if side else {}
    perf = json.loads((run / "perf.json").read_text(encoding="utf-8")) if (run / "perf.json").is_file() else {}
    argv = rr.get("argv") or []
    out = {"run": rel(run), "kind": kind, "label": rr.get("label"), "startedLocal": rr.get("startedLocal"),
           "durationS": rr.get("durationS"), "demoExit": rr.get("demoExit"),
           "room": rr.get("roomStatus") or ("ABORTED" if rr.get("roomAborted") else None),
           "cleanupLine": rr.get("cleanupLine"),
           "flags": [a for a in argv if isinstance(a, str) and a.startswith("-") and a[1:2].isupper()],
           "zoom": rr.get("zoom"), "shotAfter": rr.get("shotAfter"), "runSeconds": rr.get("runSeconds"),
           "exeSha256": ((sd.get("build") or {}).get("stagedInnerExeSha256")),
           "stagedInnerExe": (rr.get("staged") or {}).get("Unmatched.exe(inner)"),
           "crashLines": len(rr.get("crashLines") or []),
           "validation": rr.get("validation"),
           "frames": sorted(p.relative_to(run).as_posix() for p in run.rglob("*.png")),
           "gpuTotal": (perf.get("gpuTotal") or {}).get("utilizationPct"),
           "perfStatus": perf.get("status"),
           "clients": {s: trace_summary(tp) for s, tp in traces.items() if tp.is_file()}}
    return out


CLIP_MANIFEST = REPO / "docs" / "art-pipeline" / "animation-library" / "clip-manifest.json"
CHAR_PREFIX = {"Medusa": "MED", "Harpies": "HAR", "King Arthur": "ARTH", "Merlin": "MER"}
LEN_TOL_S = 0.05  # ART-013: clip length +-0.05 s


def clip_lengths() -> dict:
    doc = json.loads(CLIP_MANIFEST.read_text(encoding="utf-8"))
    out = {}
    for c in doc.get("clips", []):
        if c.get("role") == "production" and (c.get("duration_s") or {}).get("measured") is not None:
            out[c["id"]] = float(c["duration_s"]["measured"])
    return out


def heroes_checks(run: dict, lens: dict) -> dict | None:
    """ART-012/013 trace checks of one -ArtPreviewHeroesV2 run (measured, not an acceptance)."""
    cl = run["clients"]
    if not any(c.get("heroesV2") for c in cl.values()):
        return None
    out: dict = {"clients": {}}
    for side, c in cl.items():
        h = c.get("heroesV2") or {}
        fighters = h.get("fighters") or {}
        names = {fid: f["name"] for fid, f in fighters.items()}
        anim = h.get("combatAnim") or []
        idle_spawn = {fid for fid in fighters} if h.get("idleFighters") == len(fighters) else set()
        len_bad = []
        for fid, f in fighters.items():
            pre = CHAR_PREFIX.get(f["name"])
            for clip in ("Idle", "LungeAttack", "HitReact", "DeathSettle"):
                seen = sorted({a["len"] for a in anim if a["fighter"] == fid and a["clip"] == clip})
                ref = lens.get(f"{pre}-{clip}")
                for v in seen:
                    if ref is None or abs(v - ref) > LEN_TOL_S:
                        len_bad.append({"fighter": fid, "clip": clip, "traced": v, "manifest": ref})
        cues = [tuple(x) for x in (c["game"].get("cues") or [])]
        hit = {(a["fighter"], a["seq"]) for a in anim if a["clip"] == "HitReact"}
        death = [a for a in anim if a["clip"] == "DeathSettle"]
        dead = {a["fighter"] for a in death}
        last_cue = {}
        for f, _amt, seq in cues:
            last_cue[f] = max(seq, last_cue.get(f, -1))
        cue_unmatched = [{"fighter": f, "amount": amt, "seq": seq} for f, amt, seq in cues
                         if (f, seq) not in hit and not (f in dead and seq == last_cue.get(f))]
        attacks = sum(1 for a in anim if a["clip"] == "LungeAttack")
        out["clients"][side] = {
            "summary6of6": "fighters=6 mapped=6 v2=6" in (h.get("summaryLines") or []),
            "v2Figures": h.get("figures"), "idleOn": h.get("idleFighters"),
            "missing": h.get("missing") or [],
            "spawnYaws": h.get("spawnYaws"), "yawsSeen": h.get("yaws"),
            "yawsOnlyNinetyOr270": set(h.get("yaws") or []) <= {90.0, 270.0},
            "meshes": sorted({f["mesh"] for f in fighters.values()}),
            "clipsPerFigure": sorted({f["clips"] for f in fighters.values()}),
            "clipLengthsVsManifest": {"tolS": LEN_TOL_S, "outOfTolerance": len_bad},
            "animCounts": h.get("animCounts"),
            "lungeAttack": attacks, "combatResults": len(c["game"].get("combatResults") or []),
            "hitReact": len(hit), "damageCues": len(cues), "cuesWithoutHitReact": cue_unmatched,
            "deathSettle": [{"fighter": a["fighter"], "name": names.get(a["fighter"]), "len": a["len"]} for a in death],
            "deathHold": h.get("deathHold"), "deathHidden": h.get("deathHidden"),
            "minAlive": c["game"].get("minAlive"),
            "diorama": bool(c.get("diorama") and c["diorama"].get("tray") and not c["diorama"].get("missingOrHidden")),
            "idleSpawnAll": bool(idle_spawn),
        }
    h, j = out["clients"].get("host", {}), out["clients"].get("joiner", {})
    out["seqConverged"] = (cl.get("host", {}).get("game", {}).get("maxSeq") ==
                           cl.get("joiner", {}).get("game", {}).get("maxSeq"))
    out["animCountsAgree"] = h.get("animCounts") == j.get("animCounts")
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out", required=True)
    ap.add_argument("runs", nargs="+")
    a = ap.parse_args()
    runs = [run_summary(Path(r)) for r in a.runs]
    lens = clip_lengths()
    for r in runs:
        chk = heroes_checks(r, lens)
        if chk:
            r["heroesV2Checks"] = chk
    doc = {"schema": "unmatched.t5cb2-live-summary/1", "status": "измерено (трассы packaged-live; не приёмка)",
           "tool": "tools/art/t5cb2_live_summary.py", "runs": runs}
    Path(a.out).parent.mkdir(parents=True, exist_ok=True)
    Path(a.out).write_text(json.dumps(doc, ensure_ascii=False, indent=1) + "\n", encoding="utf-8", newline="\n")
    for r in runs:
        c = r["clients"]
        print(r["label"], r["kind"], r["demoExit"], r["room"], r["durationS"],
              {s: (v["render"]["reference1"], v["render"]["shots"], len(v["shotCaptured"]),
                   (v["heroesV2"] or {}).get("figures"), v["game"]["maxSeq"]) for s, v in c.items()})
    return 0


if __name__ == "__main__":
    sys.exit(main())
