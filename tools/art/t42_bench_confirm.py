#!/usr/bin/env python3
"""Stage 3 T4.2: packaged confirmation of the editor sky calibration (tools/art/t42_sky_calib_editor.py) with the
live K1 camera, through the W4-A backend-less bench (-Bench, Config/Bench/S08BenchCobble.json on the Cobble 5x6
board, FOV 35 at 1931 uu, 1920x1080, SP 100, High) and diagnostic override profiles (-ArtBoardProfiles=<file>;
the RENDER fingerprint marks them profilesSource=override, so none of these frames is a reference frame).

    python tools/art/t42_bench_confirm.py run --editor-report <t42-sky-calib-editor.json> --out <dir>
        [--profiles <final S08ArtBoardProfiles.json>] [--repeats 3] [--variants legacy-cobble,rev2-cobble,...]
    python tools/art/t42_bench_confirm.py summarize --out <dir>

Variants (the Cobble review board's light profile swapped in an override copy of the profiles file):
  legacy-<p>  the DX11-era editor probe of profile p exactly as the editor calibration shot it: the ART-005 /
              ART-005I review lights read back from the level (key pitch -55 yaw 30 with the engine CSM, colours as
              the probe bytes decode, i.e. colorLinear = sRGB-decode(byte)), the 'fill' point at the P17 stand
              (0, 100, 500), no sky, exposure EV100 1.3, and GI / reflections off (-ExecCmds
              r.DynamicGlobalIlluminationMethod 0, r.ReflectionMethod 0). legacy-cobble reproduces the P17 control
              frame (the W4-A Cobble target, 131.2) - the check that the emulation holds in packaged;
  rev2-<p>    the profile's rev 2 rig from the final profiles file (calibrated sky), Lumen on - what the Sherwood /
              T. Rex boards ship, but on the Cobble board with the same camera as its target;
rev2-<p>@<s> the same rig with the sky intensity replaced by <s> (packaged refinement step).
Verdict per profile: |rev2 - legacy| <= max(2 x repeat noise, 0.5 luma) of the K1 board p50 (x 600-1360,
y 700-940), the W4-A rule. Needs the GPU token (C:/tmp/unmatched-gpu.lock).
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
sys.path.insert(0, str(HERE / "render"))
sys.path.insert(0, str(HERE))
import render_bench as B  # noqa: E402

PROFILES = REPO / "unreal" / "Unmatched" / "Config" / "ArtBoards" / "S08ArtBoardProfiles.json"
LIGHT = {"cobble": "cobble-probe", "forest": "forest-probe", "paddock": "paddock-probe"}
P17_FILL = [0.0, 100.0, 500.0]
KEY_LABEL = "ART005 cool scene key - proposed"
FILL_LABEL = "ART005 neutral readability fill - review only"
WARM_LABEL = "ART005 warm lantern accent - proposed"
EXTRA_PREFIX = "ART005I extra light "
LUMA_FLOOR = 0.5
SCHEMA = "unmatched.t42-bench-confirm/1"


def srgb_decode(b: float) -> float:
    return b / 12.92 if b <= 0.04045 else ((b + 0.055) / 1.055) ** 2.4


def probe_color(c: dict) -> list[float]:
    """lightColor as MCP read it back (= byte / 255 of the level's FColor) -> the linear colour the renderer used."""
    return [round(srgb_decode(float(c[k])), 6) for k in "rgb"]


def legacy_profile(editor_prof: dict, exposure: dict) -> dict:
    rl = editor_prof["prep"]["reviewLights"]

    def loc(t):
        return [round(t["location"][k], 3) for k in "xyz"]
    key = rl[KEY_LABEL]
    kt = key["transform"]
    lp = {"source": "T4.2 packaged emulation of the DX11-era editor probe (review lights of the level, P17 fill stand)",
          "units": {"point": "candelas", "directional": "lux"},
          "directional": {"name": "key", "posUU": loc(kt),
                          "rotation": [round(kt["rotation"]["pitch"], 3), round(kt["rotation"]["yaw"], 3),
                                       round(kt["rotation"]["roll"], 3)],
                          "intensity": key["intensity"], "colorLinear": probe_color(key["lightColor"]),
                          "castShadows": bool(key.get("castShadows", True))},
          "exposure": exposure, "points": []}
    for label, spec in sorted(rl.items()):
        if label == KEY_LABEL:
            continue
        role = "fill" if label == FILL_LABEL else "warm" if label == WARM_LABEL else "secondary"
        pos = P17_FILL if label == FILL_LABEL else loc(spec["transform"])
        lp["points"].append({"name": role, "role": role, "posUU": pos, "intensity": spec["intensity"],
                             "radiusUU": spec["attenuationRadius"], "colorLinear": probe_color(spec["lightColor"])})
    return lp


def override(profiles: dict, light_id: str, extra_light: dict | None, out: Path, name: str) -> Path:
    doc = json.loads(json.dumps(profiles))
    if extra_light is not None:
        doc["lightProfiles"][light_id] = extra_light
    for b in doc["boards"]:
        if b["id"] == "cobble-city":
            b["light"] = light_id
    p = out / f"profiles-{name}.json"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(doc, ensure_ascii=False, indent=1) + "\n", encoding="utf-8", newline="\n")
    return p


def run_one(variant: str, prof_file: Path, legacy: bool, rdir: Path, a) -> dict:
    rdir.mkdir(parents=True, exist_ok=True)
    trace, log = rdir / "bench.trace.log", rdir / "client.log"
    execs = ["DisableAllScreenMessages"] + (["r.DynamicGlobalIlluminationMethod 0", "r.ReflectionMethod 0"] if legacy else [])
    cmd = [str(B.EXE), B.MAP, "-windowed", "-resx=1920", "-resy=1080", "-ForceRes", "-RenderOffScreen", "-ArtPreview",
           "-Bench", f"-BenchOut={rdir}", f"-S08Trace={trace}", "-BenchViews=K1", f"-BenchWarmup={a.warmup}",
           f"-BenchSettle={a.settle}", f"-BenchMeasure={a.measure}", "-BenchNoProfileGPU", f"-abslog={log}",
           "-S08RenderPreset=High", f"-ArtBoardProfiles={prof_file}", "-ExecCmds=" + ", ".join(execs)]
    rec = {"schema": SCHEMA, "variant": variant, "startedLocal": dt.datetime.now().astimezone().isoformat(timespec="seconds"),
           "argv": [c.replace(str(REPO), "<repo>") for c in cmd],
           "exeSha256": B.sha256(B.EXE.parent / "Unmatched" / "Binaries" / "Win64" / "Unmatched.exe"),
           "profilesOverrideSha256": B.sha256(prof_file)}
    started = time.time()
    p = subprocess.Popen(cmd, creationflags=B.NO_WINDOW)
    rec["pid"] = p.pid
    try:
        p.wait(timeout=a.warmup + a.settle + a.measure + 150)
    except subprocess.TimeoutExpired:
        subprocess.run(["taskkill", "/PID", str(p.pid), "/T", "/F"], capture_output=True, creationflags=B.NO_WINDOW)
        rec["timeout"] = True
    rec["exitCode"] = p.returncode
    rec["durationS"] = round(time.time() - started, 1)
    rec["trace"] = B.parse_trace(trace) if trace.is_file() else None
    png = rdir / "bench-K1-1920x1080.png"
    if png.is_file():
        rec["shot"] = {"file": png.name, "sha256": B.sha256(png), "luma": B.luma_stats(png, None)}
        from PIL import Image
        import numpy as np
        a8 = np.asarray(Image.open(png).convert("RGB")).astype(np.float64)
        L = 0.2126 * a8[..., 0] + 0.7152 * a8[..., 1] + 0.0722 * a8[..., 2]
        x0, y0, x1, y1 = (600, 700, 1360, 940)
        rec["boardK1P50"] = round(float(np.percentile(L[y0:y1, x0:x1], 50)), 2)
    lines = B.RF.read_lines(trace) if trace.is_file() else []
    rec["traceLines"] = [B.RF.payload(ln) for ln in lines if any(
        k in ln for k in ("ARTPREVIEW board profiles source", "ARTPREVIEW lights applied", "ARTPREVIEW sky profile",
                          "ARTPREVIEW exposure profile", "ARTPREVIEW zone content", "ARTPREVIEW board glyph meshes",
                          "ARTPREVIEW render profile", "RENDER tag=SHOT", "BENCH done", "BENCH FAILED"))]
    B.write_json(rdir / "bench-run.json", rec)
    return rec


def stats(vals):
    return {"n": len(vals), "mean": round(sum(vals) / len(vals), 3), "min": min(vals), "max": max(vals),
            "noise": round(max(vals) - min(vals), 3), "values": vals}


def cmd_run(a) -> int:
    lock = Path(r"C:\tmp\unmatched-gpu.lock")
    if not lock.is_file():
        print("REFUSED: take the GPU token first (C:/tmp/unmatched-gpu.lock)")
        return 2
    out = Path(a.out).resolve()
    profiles = json.loads(Path(a.profiles).read_text(encoding="utf-8"))
    ed = json.loads(Path(a.editor_report).read_text(encoding="utf-8"))
    exposure = profiles["lightProfiles"]["cobble-probe"]["exposure"]
    plan = {}
    for v in a.variants.split(","):
        kind, key = v.split("-", 1)
        if kind == "legacy":
            lid = f"t42-legacy-{key}"
            plan[v] = (override(profiles, lid, legacy_profile(ed["profiles"][key], exposure), out, v), True)
        elif "@" in key:  # rev2-<p>@<sky>: packaged refinement step, the profile's sky intensity replaced
            key, sky = key.split("@", 1)
            lp = json.loads(json.dumps(profiles["lightProfiles"][LIGHT[key]]))
            lp["sky"]["intensity"] = float(sky)
            plan[v] = (override(profiles, LIGHT[key], lp, out, v), False)
        else:
            plan[v] = (override(profiles, LIGHT[key], None, out, v), False)
    for r in range(1, a.repeats + 1):  # interleaved: a drift of the machine hits every variant alike
        for v, (pf, legacy) in plan.items():
            rec = run_one(v, pf, legacy, out / v / f"r{r}", a)
            print(f"{v} r{r}: K1 board p50 {rec.get('boardK1P50')} exit {rec['exitCode']} "
                  f"done={bool(rec['trace'] and rec['trace']['done'])} {rec['durationS']}s", flush=True)
    return cmd_summarize(a)


def cmd_summarize(a) -> int:
    out = Path(a.out).resolve()
    rows = {}
    for d in sorted(p for p in out.iterdir() if p.is_dir()):
        vals, fps = [], []
        for r in sorted(d.glob("r*/bench-run.json")):
            rec = json.loads(r.read_text(encoding="utf-8"))
            if rec.get("boardK1P50") is not None and rec["trace"] and rec["trace"]["done"]:
                vals.append(rec["boardK1P50"])
                fp = (rec["trace"].get("shotFingerprints") or {})
                fps.append(next(iter(fp.values()), {}) if fp else {})
        if vals:
            rows[d.name] = dict(stats(vals), fingerprint={k: (fps[0] or {}).get(k) for k in (
                "rhi", "featureLevel", "gi", "refl", "profilesSource", "profile", "sky", "expMin", "reference")})
    verdicts = {}
    for name, rv in rows.items():  # rev2-<p> (the profiles file) and rev2-<p>@<sky> (refinement) against legacy-<p>
        if not name.startswith("rev2-"):
            continue
        key = name[len("rev2-"):].split("@", 1)[0]
        lg = rows.get(f"legacy-{key}")
        if lg:
            noise = max(lg["noise"], rv["noise"])
            thr = max(2 * noise, LUMA_FLOOR)
            d = round(rv["mean"] - lg["mean"], 3)
            verdicts[name] = {"legacy": lg["mean"], "rev2": rv["mean"], "delta": d, "threshold": round(thr, 3),
                              "matched": abs(d) <= thr}
    doc = {"schema": SCHEMA + "-summary", "rows": rows, "verdicts": verdicts,
           "p17Reference": {"boardK1P50": 131.2, "source": "W4-A face_roi / render-dx12-lumen §5 (P17 editor K1)"}}
    B.write_json(out / "bench-confirm-summary.json", doc)
    print(json.dumps(verdicts, ensure_ascii=False, indent=1))
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("run")
    r.add_argument("--editor-report", required=True)
    r.add_argument("--out", required=True)
    r.add_argument("--profiles", default=str(PROFILES))
    r.add_argument("--repeats", type=int, default=3)
    r.add_argument("--variants", default="legacy-cobble,rev2-cobble,legacy-forest,rev2-forest,legacy-paddock,rev2-paddock")
    r.add_argument("--warmup", type=int, default=20)
    r.add_argument("--settle", type=int, default=6)
    r.add_argument("--measure", type=int, default=6)
    s = sub.add_parser("summarize")
    s.add_argument("--out", required=True)
    a = ap.parse_args(argv)
    return {"run": cmd_run, "summarize": cmd_summarize}[a.cmd](a)


if __name__ == "__main__":
    sys.exit(main())
