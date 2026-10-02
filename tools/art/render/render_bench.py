#!/usr/bin/env python3
"""W4-A render bench driver: packaged Development client in -Bench mode.

The client (S08FlowGameMode.cpp RunRenderBench) replays the captured Cobble 5x6
game state (Config/Bench/S08BenchCobble.json) without a backend, warms up,
then per view (K1 overview, K2 5x on Medusa) settles, measures frame / GPU /
game / render thread ms with no frame cap (t.MaxFPS 0, VSync 0), records a
CSV profiler window (-csvGpuStats: per-pass GPU ms), dumps one ProfileGPU
frame and takes one 1920x1080 SHOT with the RENDER fingerprint.

  python tools/art/render/render_bench.py run --variant dx12-lumen-high --repeats 3 --out <dir>
  python tools/art/render/render_bench.py run --variant dx12-lumen-high-v2 --name marmoreal --out <dir>
      --views K1+K1x0.65+K2x1.6 --bench-fixture ../../../Unmatched/Config/Bench/S08BenchMarmoreal.json  (ENV-MAPS)
  python tools/art/render/render_bench.py summarize --out <dir> <variant dirs...>
  python tools/art/render/render_bench.py variants

Variants (one binary; the pre-W4 look is emulated with -S08LegacyRender):
  dx12-lumen-high      reference: DX12 SM6, Lumen GI + reflections, sg.* = 2, SP 100, profile rev 2
  dx12-lumen-high-v2   reference + -ArtPreviewHeroesV2 -ArtPreviewDiorama (5c-B heroes and diorama tray)
  dx12-lumen-high-v2-fps60  the same capped at 60 FPS (-BenchFps=60): effective FPS of one client
  dx12-lumen-high-v2-nohero the v2 reference without the ENV-MAPS P9 hero light (-NoHeroLight): gate H5 (its cost)
  dx12-lumen-high-vsm  same + r.Shadow.Virtual.Enable 1 (VSM instead of the profile CSM)
  dx12-lumen-high-csmdefault  profile CSM block removed (engine default 40000 uu / 4 cascades)
  dx11-legacy          -dx11 -S08LegacyRender + profile rev 1 (Unitless points + point fill, no sky,
                       no exposure volume, M_S08_Solid game layer), sg.* = 3, auto screen percentage,
                       GI/reflection method 0 - the pre-W4 packaged state
  dx12sm5-legacy       the same pre-W4 state on D3D12 at SM5 (bubble-free GPU timing for the comparison)
  dx12-medium / dx12-low  proposed UI steps (sg.* = 1 / 0; Medium = Lumen irradiance volume, Low = no Lumen)
  dx12-sm5-fallback    -sm5: DX12 without SM6 (what GTX 1060 / RX 580 class drivers without SM 6.6 get)
  dx11-fallback        -dx11 with the W4-A data: no DX12 at all
  sky-<k>              calibration: reference with every profile sky intensity x <k> (override file)

Statuses stay honest: every number is "измерено" on this PC (RTX 4090), never a D-07 budget.
"""
from __future__ import annotations

import argparse
import csv
import datetime as dt
import hashlib
import json
import math
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
PROJECT = REPO / "unreal" / "Unmatched"
STAGE = PROJECT / "Saved" / "StagedBuilds" / "Windows"
EXE = STAGE / "Unmatched.exe"
STAGED_CSV = STAGE / "Unmatched" / "Saved" / "Profiling" / "CSV"
PROFILES = PROJECT / "Config" / "ArtBoards" / "S08ArtBoardProfiles.json"
PROFILES_REV1_COMMIT = "4a1cad9a"  # pre-W4 profile data (Unitless points + point fill)
NO_WINDOW = 0x08000000
MAP = "/Game/S08/S08Arena?game=/Script/Unmatched.S08FlowGameMode"
REFERENCE = REPO / "docs" / "art-pipeline" / "render-reference.json"
sys.path.insert(0, str(REPO / "tools" / "art"))
import render_fingerprint as RF  # noqa: E402


def sha256(p: Path) -> str:
    h = hashlib.sha256()
    with Path(p).open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def write_json(p: Path, doc) -> None:
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(doc, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")


def rel(p: Path) -> str:
    try:
        return Path(p).resolve().relative_to(REPO).as_posix()
    except ValueError:
        return Path(p).resolve().as_posix()


# ------------------------------------------------------------------ variants
def profiles_override(out: Path, name: str, mutate) -> Path:
    doc = json.loads(PROFILES.read_text(encoding="utf-8"))
    mutate(doc)
    p = out / f"profiles-{name}.json"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(doc, ensure_ascii=False, indent=1) + "\n", encoding="utf-8", newline="\n")
    return p


def profiles_rev1(out: Path) -> Path:
    p = out / "profiles-rev1-pre-w4.json"
    if not p.is_file():
        blob = subprocess.run(["git", "-C", str(REPO), "show",
                               f"{PROFILES_REV1_COMMIT}:unreal/Unmatched/Config/ArtBoards/S08ArtBoardProfiles.json"],
                              capture_output=True, check=True, creationflags=NO_WINDOW).stdout
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(blob)
    return p


def variant_args(name: str, out: Path) -> tuple[list[str], list[str], dict]:
    """(client args, extra ExecCmds, notes)."""
    if name == "dx12-lumen-high":
        return ["-S08RenderPreset=High"], [], {"rhi": "default DX12", "profiles": "pak rev 2"}
    if name == "dx12-lumen-high-v2-nohero":
        # ENV-MAPS P9 gate H5 (docs/art-pipeline/ENV-HERO-LIGHT.md): the v2 reference minus the hero light rig
        return (["-S08RenderPreset=High", "-ArtPreviewHeroesV2", "-ArtPreviewDiorama", "-NoHeroLight"], [],
                {"heroesV2": True, "diorama": True, "heroLight": "off (-NoHeroLight)", "profiles": "pak rev 2"})
    if name in ("dx12-lumen-high-v2", "dx12-lumen-high-v2-fps60"):
        # Wave 6 (GD-058 interim): the reference plus the 5c-B look-dev heroes (-ArtPreviewHeroesV2) and the
        # diorama tray (-ArtPreviewDiorama) on the same Cobble bench state; -fps60 caps the single client at
        # 60 FPS (-BenchFps=60, the packaged default) to record the effective frame rate, not the pass cost.
        args = ["-S08RenderPreset=High", "-ArtPreviewHeroesV2", "-ArtPreviewDiorama"]
        notes = {"heroesV2": True, "diorama": True, "profiles": "pak rev 2"}
        if name.endswith("-fps60"):
            args.append("-BenchFps=60")
            notes["fpsCap"] = "t.MaxFPS 60 (-BenchFps=60): effective FPS of one client, not a pass-cost number"
        return args, [], notes
    if name == "dx12-lumen-high-vsm":
        return ["-S08RenderPreset=High"], ["r.Shadow.Virtual.Enable 1"], {"shadows": "VSM (runtime cvar)"}
    if name == "dx12-lumen-high-csmdefault":
        def drop(doc):
            for lp in doc["lightProfiles"].values():
                lp["directional"].pop("shadow", None)
        p = profiles_override(out, "csmdefault", drop)
        return ["-S08RenderPreset=High", f"-ArtBoardProfiles={p}"], [], {"shadows": "engine CSM default", "profiles": rel(p)}
    if name in ("dx11-legacy", "dx12sm5-legacy"):
        # pre-W4 state: sg 3 (Epic), screen percentage auto by display resolution (G05), no GI /
        # reflection method, Unitless points + point fill, no sky / exposure volume, M_S08_Solid game
        # layer. dx12sm5-legacy runs the same state on the D3D12 RHI at SM5: its GPU timings are
        # bubble-free (D3D12 removes idle gaps; the CPU-bound DX11 spans include them).
        p = profiles_rev1(out)
        rhi = ["-dx11"] if name == "dx11-legacy" else ["-sm5"]
        return (rhi + ["-S08LegacyRender", "-S08RenderPreset=Epic", f"-ArtBoardProfiles={p}"],
                ["r.ScreenPercentage 0", "r.ScreenPercentage.Default.Desktop.Mode 1",
                 "r.DynamicGlobalIlluminationMethod 0", "r.ReflectionMethod 0"],
                {"emulates": "pre-W4 packaged state (" + ("DX11" if name == "dx11-legacy" else "D3D12 at") +
                             " SM5, no GI/reflection method, sg 3, auto SP by display resolution, Unitless points + "
                             "point fill, no sky / exposure volume, M_S08_Solid game layer)", "profiles": rel(p)})
    if name in ("dx12-medium", "dx12-low"):
        preset = "Medium" if name == "dx12-medium" else "Low"
        return [f"-S08RenderPreset={preset}"], [], {"preset": f"{preset} (sg.* = {1 if preset == 'Medium' else 0}; "
                                                              "proposed UI step, not the reference)"}
    if name == "dx12-sm5-fallback":
        return ["-sm5", "-S08RenderPreset=High"], [], {"emulates": "DX12 without SM6 (no SM 6.6 / 64-bit atomics)"}
    if name == "dx11-fallback":
        return ["-dx11", "-S08RenderPreset=High"], [], {"emulates": "no DX12 at all"}
    m = re.fullmatch(r"sky-([0-9.]+)", name)
    if m:
        k = float(m.group(1))

        def scale(doc):
            for lp in doc["lightProfiles"].values():
                if "sky" in lp:
                    lp["sky"]["intensity"] = round(lp["sky"]["intensity"] * k, 4)
        p = profiles_override(out, f"sky-x{k:g}", scale)
        return ["-S08RenderPreset=High", f"-ArtBoardProfiles={p}"], [], {"calibration": f"sky x{k:g}", "profiles": rel(p)}
    raise SystemExit(f"unknown variant {name!r}")


VARIANTS = ["dx12-lumen-high", "dx12-lumen-high-v2", "dx12-lumen-high-v2-fps60", "dx12-lumen-high-v2-nohero",
            "dx12-lumen-high-vsm",
            "dx12-lumen-high-csmdefault", "dx11-legacy",
            "dx12sm5-legacy", "dx12-medium", "dx12-low", "dx12-sm5-fallback", "dx11-fallback", "sky-<k>"]


# ------------------------------------------------------------------ parsing
NUM = r"(-?\d+(?:\.\d+)?)"


def parse_trace(p: Path) -> dict:
    lines = RF.read_lines(p)
    out = {"views": {}, "render": {}, "heads": {}, "scene": None, "done": False, "failed": None, "lines": len(lines)}
    view = None
    for ln in lines:
        body = RF.payload(ln)
        if body.startswith("BENCH scene"):
            out["scene"] = dict(RF.PAIR.findall(body[len("BENCH scene"):]))
        elif body.startswith("BENCH view="):
            view = body.split()[1].split("=", 1)[1]
        elif body.startswith("BENCH measure view="):
            v = re.search(r"view=(\S+)", body).group(1)
            d = {}
            for key in ("frameMs", "gpuMs", "gameMs", "renderMs"):
                m = re.search(key + r" ((?:\w+=" + NUM + r"\s*)+)", body)
                if m:
                    d[key] = {k: float(x) for k, x in re.findall(r"(\w+)=" + NUM, m.group(1))}
            for key in ("frames", "fps", "hitches50", "window"):
                m = re.search(r"\b" + key + "=" + NUM, body)
                if m:
                    d[key] = float(m.group(1))
            out["views"][v] = d
        elif body.startswith("RENDER tag=BENCH"):
            if view:
                out["render"][view] = RF.parse_render_line(body)
        elif body.startswith("SHOT head fighter="):
            if view:
                d = dict(re.findall(r"(\w+)=(\([^)]*\)|\S+)", body[len("SHOT head "):]))
                out["heads"][view] = d
        elif body.startswith("BENCH done"):
            out["done"] = True
        elif body.startswith("BENCH FAILED"):
            out["failed"] = body
    # SHOT fingerprints per shot file (the acceptance tools use these)
    out["shotFingerprints"] = {b["shot"]: b["render"] for b in RF.shot_fingerprints(lines) if b["shot"]}
    return out


PROFILE_ROW = re.compile(r"┃\s*\d+\s*│\s*\d+\s*│\s*\d+\s*│\s*\d+\s*│\s*[\d.]+%\s*┊[^│]*│\s*([\d.]+) ms\s*┃"
                         r"\s*\d+\s*│\s*\d+\s*│\s*\d+\s*│\s*\d+\s*│\s*[\d.]+%\s*┊[^│]*│\s*([\d.]+) ms\s*┃(\s*)(.*?)\s*┃")
KEY_PASSES = ["<root>", "Scene", "PrePass", "Prepass", "BasePass", "Basepass", "ShadowDepths", "Lights",
              "LumenSceneUpdate", "LumenSceneLighting", "DiffuseIndirectAndAO", "LumenScreenProbeGather",
              "LumenReflections", "ReflectionEnvironmentAndSky", "PostProcessing", "Postprocessing",
              "TemporalSuperResolution", "Translucency", "VirtualShadowMaps", "RenderDeferredLighting",
              "DistanceFieldShadows", "ShadowProjection", "HZB", "AmbientOcclusion", "ScreenSpaceReflections"]


def parse_profilegpu(log: Path) -> list[dict]:
    """Each ProfileGPU dump: queues -> passes (name, depth, exclusive, inclusive ms)."""
    dumps: list[dict] = []
    cur = None
    queue = None
    for ln in RF.read_lines(log):
        # UE 5.8 prints one table per queue: "Copy pipeline 0 - GPU 0", then
        # "Compute pipeline 0 - GPU 0" (async compute), "Graphics pipeline 0 - GPU 0".
        m = re.search(r"LogRHI: Display: (?:GPU Profile for Frame \d+ - )?(\w+) pipeline (\d+) - GPU (\d+)\s*$", ln)
        if m:
            queue = f"{m.group(1)} pipeline {m.group(2)}"
            # a new dump starts at its first queue ("Copy" on D3D12; D3D11 prints only "Graphics")
            if m.group(1) == "Copy" or cur is None or queue in cur["queues"]:
                cur = {"queues": {}, "line": ln[:40]}
                dumps.append(cur)
            continue
        if cur is None:
            continue
        m = PROFILE_ROW.search(ln)
        if m:
            excl, incl, indent, name = float(m.group(1)), float(m.group(2)), len(m.group(3)), m.group(4).strip()
            q = cur["queues"].setdefault(queue or "queue?", [])
            q.append({"name": name, "indent": indent, "exclusiveMs": excl, "inclusiveMs": incl})
    for d in dumps:
        d["summary"] = {}
        for qname, rows in d["queues"].items():
            s = {}
            for r in rows:
                if r["name"] in KEY_PASSES and r["name"] not in s:
                    s[r["name"]] = r["inclusiveMs"]
            d["summary"][qname] = s
    return dumps


def parse_csv(p: Path) -> dict:
    with p.open(encoding="utf-8", errors="replace", newline="") as f:
        rows = list(csv.reader(f))
    if not rows:
        return {}
    # UE CSV profiler: with [HasHeaderRowAtEnd] the complete header is the row
    # before the metadata row; data rows are positional and early rows are
    # shorter (stats that appeared later are appended as new columns = 0).
    if rows[-1] and rows[-1][0] == "[HasHeaderRowAtEnd]":
        head, body = rows[-2], rows[1:-2]
    else:
        head, body = rows[0], rows[1:]
    idx = {h: i for i, h in enumerate(head) if h not in ("EVENTS",)}
    fi = idx.get("FrameTime")
    data = []
    for r in body:
        try:
            if fi is None or fi >= len(r):
                continue
            float(r[fi])
        except ValueError:
            continue
        data.append(r)
    out = {"file": p.name, "frames": len(data), "gpu": {}}
    for h, i in idx.items():
        if h == "GPUTime" or h.startswith("GPU/") or h in ("FrameTime", "GameThreadTime", "RenderThreadTime"):
            vals = []
            for r in data:
                try:
                    vals.append(float(r[i]) if i < len(r) else 0.0)
                except ValueError:
                    pass
            if vals:
                vals.sort()
                out["gpu"][h] = {"mean": round(sum(vals) / len(vals), 4),
                                 "p50": round(vals[len(vals) // 2], 4),
                                 "p95": round(vals[min(len(vals) - 1, int(math.ceil(0.95 * len(vals))) - 1)], 4)}
    return out


# Face ROI, bound to where the face actually projects (W4-A fix; the first rule centred a square on the
# socket's screen X and missed the face: on the v2 candidate it covered the right third of the face,
# the robe and the black gap by the neck - a bimodal ROI, p50 85 vs mean 106).
#
# The traced Head socket sits at the neck base. The ROI is placed relative to its projection in
# "head units": u = headPx / 12 px, the screen length of 1 uu along world Z at the socket (the trace
# projects Head +-6 uu). Offsets are (dx, dz) in u: dx to the screen right, dz up. They are screen
# offsets, not world uu (the -55 deg board camera foreshortens Z), so a calibration holds for one mesh
# and the board camera only. It was fitted on the K2 5x frames of this run set (Head at (960, 517.7),
# headPx 56.4) and checked on every frame with face-roi-contact-sheet.jpg (tools/art/render/face_roi.py).
# Meshes without a calibration and heads smaller than FACE_ROI_MIN_HEAD_PX get no face ROI at all.
FACE_ROI_MIN_HEAD_PX = 40.0  # K1 heads are ~11 px: a face ROI there would be a handful of pixels
FACE_ROI_CALIBRATION = {
    "SK_Medusa_FaceNeck_v2Candidate": {
        # below the diadem tip down to the chin, inside the face outline -> box (925, 464)-(958, 480) at K2 5x
        "faceRoi": {"centre": (-3.95, 9.7), "half": (3.5, 1.7), "what": "face: below the diadem tip down to the chin"},
        # the verifier's box: face plus the throat below the chin -> (924, 462)-(956, 490) at K2 5x
        "faceNeckRoi": {"centre": (-4.25, 8.9), "half": (3.4, 3.0), "what": "face plus the throat below the chin"},
    },
}


def roi_stats(L, box) -> dict:
    import numpy as np
    x0, y0, x1, y1 = box
    roi = L[max(0, y0):max(0, y1), max(0, x0):max(0, x1)]
    if not roi.size:
        return {"box": list(box), "pixels": 0, "mean": None}
    pct = {f"p{q}": round(float(np.percentile(roi, q)), 2) for q in (5, 50, 95)}
    return {"box": list(box), "pixels": int(roi.size), "mean": round(float(roi.mean()), 2), **pct,
            "std": round(float(roi.std()), 2)}


def face_boxes(head: dict | None) -> tuple[dict, str | None]:
    """{roi name: (box, rule text)} for a traced SHOT head line, or ({}, reason)."""
    if not head or head.get("projected") != "1":
        return {}, "no projected Head socket (none traced or none passed)"
    mesh = head.get("mesh", "")
    cal = FACE_ROI_CALIBRATION.get(mesh)
    if not cal:
        return {}, f"no face ROI calibration for mesh {mesh or '?'}"
    head_px = float(head["headPx"])
    if head_px < FACE_ROI_MIN_HEAD_PX:
        return {}, f"head too small for a face ROI ({head_px:g} px < {FACE_ROI_MIN_HEAD_PX:g})"
    hx, hy = (float(v) for v in head["screen"].strip("()").split(","))
    u = head_px / 12.0
    out = {}
    for key, c in cal.items():
        (dx, dz), (hw, hh) = c["centre"], c["half"]
        cx, cy = hx + dx * u, hy - dz * u
        box = (int(round(cx - hw * u)), int(round(cy - hh * u)), int(round(cx + hw * u)), int(round(cy + hh * u)))
        out[key] = (box, f"{c['what']}; {mesh}: centre Head + ({dx:g}, {dz:g}) u, {2 * hw:g} x {2 * hh:g} u, "
                         f"u = headPx/12 = {u:.3f} px (screen offsets, board camera only); Rec.709 luma of the sRGB frame")
    return out, None


def luma_stats(png: Path, head: dict | None) -> dict:
    import numpy as np
    from PIL import Image
    a = np.asarray(Image.open(png).convert("RGB")).astype(np.float64)
    L = 0.2126 * a[..., 0] + 0.7152 * a[..., 1] + 0.0722 * a[..., 2]
    out = {"frame": {"p10": round(float(np.percentile(L, 10)), 2), "p50": round(float(np.percentile(L, 50)), 2),
                     "p90": round(float(np.percentile(L, 90)), 2), "mean": round(float(L.mean()), 2)},
           "center": round(float(L[440:640, 860:1060].mean()), 2)}
    boxes, why = face_boxes(head)
    if why:
        out["faceRoiSkipped"] = why
    for key, (box, rule) in boxes.items():
        out[key] = {**roi_stats(L, box), "pxPerUU": round(float(head["headPx"]) / 12.0, 3), "rule": rule}
    return out


# ------------------------------------------------------------------ run
def gpu_sampler(path: Path) -> subprocess.Popen:
    f = path.open("w", encoding="utf-8", newline="\n")
    f.write("timestamp,utilization.gpu,memory.used,power.draw\n")
    f.flush()
    return subprocess.Popen(["nvidia-smi", "--query-gpu=timestamp,utilization.gpu,memory.used,power.draw",
                             "--format=csv,noheader,nounits", "-lms", "500"], stdout=f, stderr=subprocess.DEVNULL,
                            creationflags=NO_WINDOW)


def run_one(variant: str, rdir: Path, a) -> dict:
    rdir.mkdir(parents=True, exist_ok=True)
    args, execs, notes = variant_args(variant, rdir.parent)
    trace = rdir / "bench.trace.log"
    log = rdir / "client.log"
    cmd = [str(Path(a.exe)), MAP, "-windowed", "-resx=1920", "-resy=1080", "-ForceRes", "-RenderOffScreen",
           "-ArtPreview", "-Bench", f"-BenchOut={rdir}", f"-S08Trace={trace}", f"-BenchViews={a.views}",
           f"-BenchWarmup={a.warmup}", f"-BenchSettle={a.settle}", f"-BenchMeasure={a.measure}",
           "-BenchCsv", "-csvGpuStats", f"-abslog={log}"] + args
    if a.bench_fixture:
        # ENV-MAPS: the same scene on another board (S08BenchMarmoreal/Sarpedon.json); a relative path is read
        # by the packaged client from its pak (cwd Binaries/Win64, e.g. ../../../Unmatched/Config/Bench/<file>)
        cmd.append(f"-BenchFixture={a.bench_fixture}")
        notes = {**notes, "benchFixture": a.bench_fixture}
    cmd.append("-ExecCmds=" + ", ".join(["DisableAllScreenMessages"] + execs))
    before = set(STAGED_CSV.glob("*.csv")) if STAGED_CSV.is_dir() else set()
    started = time.time()
    rec = {"schema": "unmatched.w4a-render-bench-run/1", "variant": variant, "notes": notes,
           "startedLocal": dt.datetime.now().astimezone().isoformat(timespec="seconds"),
           "argv": [c.replace(str(REPO), "<repo>") for c in cmd], "exeSha256": sha256(Path(a.exe).parent / "Unmatched" /
                                                                                     "Binaries" / "Win64" / "Unmatched.exe")}
    sampler = gpu_sampler(rdir / "nvidia-smi.csv")
    p = subprocess.Popen(cmd, creationflags=NO_WINDOW)
    rec["pid"] = p.pid
    timeout = a.warmup + max(2, len(a.views.split("+"))) * (a.settle + a.measure + 25) + 120
    try:
        p.wait(timeout=timeout)
    except subprocess.TimeoutExpired:
        # the staged root Unmatched.exe is a launcher stub: stop its whole tree (this run's PID only)
        subprocess.run(["taskkill", "/PID", str(p.pid), "/T", "/F"], capture_output=True, creationflags=NO_WINDOW)
        rec["timeout"] = True
    sampler.terminate()
    try:
        sampler.wait(10)
    except subprocess.TimeoutExpired:
        sampler.kill()
    rec["exitCode"] = p.returncode
    rec["durationS"] = round(time.time() - started, 1)
    csvs = sorted(set(STAGED_CSV.glob("*.csv")) - before) if STAGED_CSV.is_dir() else []
    rec["csv"] = []
    for i, c in enumerate(csvs):
        dst = rdir / f"csv-{i}-{c.name.replace('(', '-').replace(')', '')}"
        shutil.copy2(c, dst)
        rec["csv"].append({"file": dst.name, "sha256": sha256(dst), "summary": parse_csv(dst)})
    rec["trace"] = parse_trace(trace) if trace.is_file() else None
    rec["profileGpu"] = parse_profilegpu(log) if log.is_file() else []
    rec["shots"] = {}
    for png in sorted(rdir.glob("bench-*-1920x1080.png")):
        view = png.stem[len("bench-"):-len("-1920x1080")]
        head = (rec["trace"] or {}).get("heads", {}).get(view)
        rec["shots"][view] = {"file": png.name, "sha256": sha256(png), "luma": luma_stats(png, head)}
    ref = RF.load_reference(REFERENCE)
    rec["referenceCheck"] = {}
    for shot, fp in ((rec["trace"] or {}).get("shotFingerprints") or {}).items():
        ok, why = RF.check(fp, ref)
        rec["referenceCheck"][shot] = {"reference": ok, "reasons": why}
    write_json(rdir / "bench-run.json", rec)
    return rec


def cmd_run(a) -> int:
    # absolute: the client resolves -BenchOut / -S08Trace / -abslog against its own Binaries/Win64 directory
    out = Path(a.out).resolve() / (a.name or a.variant)
    lock = Path(r"C:\tmp\unmatched-gpu.lock")
    if not lock.is_file():
        print("REFUSED: take the GPU token first (C:/tmp/unmatched-gpu.lock)")
        return 2
    rc = 0
    for r in range(1, a.repeats + 1):
        rdir = out / f"r{r}"
        if rdir.exists() and any(rdir.iterdir()):
            print(f"skip existing {rel(rdir)}")
            continue
        rec = run_one(a.variant, rdir, a)
        t = rec["trace"] or {}
        views = {v: (d.get("fps"), (d.get("gpuMs") or {}).get("avg")) for v, d in t.get("views", {}).items()}
        print(json.dumps({"variant": a.variant, "r": r, "exit": rec["exitCode"], "done": t.get("done"),
                          "failed": t.get("failed"), "views(fps,gpuMs)": views,
                          "reference": {k: v["reference"] for k, v in rec["referenceCheck"].items()}}, ensure_ascii=False))
        if not t.get("done"):
            rc = 1
    return rc


# ------------------------------------------------------------------ summary
def _stats(vals: list[float]) -> dict:
    vals = [v for v in vals if v is not None]
    if not vals:
        return {"n": 0}
    m = sum(vals) / len(vals)
    return {"n": len(vals), "mean": round(m, 4), "min": round(min(vals), 4), "max": round(max(vals), 4),
            "noise": round(max(vals) - min(vals), 4)}


def summarize_variant(vdir: Path) -> dict:
    runs = [json.loads((r / "bench-run.json").read_text(encoding="utf-8")) for r in sorted(vdir.glob("r*"))
            if (r / "bench-run.json").is_file()]
    out = {"variant": vdir.name, "runs": len(runs), "views": {}}
    views = sorted({v for r in runs for v in ((r.get("trace") or {}).get("views") or {})})
    for v in views:
        per = [((r.get("trace") or {}).get("views") or {}).get(v, {}) for r in runs]
        vi = list(views).index(v)
        csvs = [r["csv"][vi]["summary"] if len(r.get("csv") or []) > vi else {} for r in runs]
        passes = sorted({k for c in csvs for k in (c.get("gpu") or {})})
        pg = [(r.get("profileGpu") or [])[vi] if len(r.get("profileGpu") or []) > vi else {} for r in runs]
        queues = sorted({q for d in pg for q in (d.get("summary") or {})})
        # shot keys are PNG stems ("K1x0p65"), trace views keep the dot ("K1x0.65")
        shots = [(r.get("shots") or {}).get(v) or (r.get("shots") or {}).get(v.replace(".", "p"), {}) for r in runs]
        out["views"][v] = {
            "fps": _stats([d.get("fps") for d in per]),
            "frameMsAvg": _stats([(d.get("frameMs") or {}).get("avg") for d in per]),
            "frameMsP95": _stats([(d.get("frameMs") or {}).get("p95") for d in per]),
            "gpuMsAvg": _stats([(d.get("gpuMs") or {}).get("avg") for d in per]),
            "gpuMsP95": _stats([(d.get("gpuMs") or {}).get("p95") for d in per]),
            "renderMsAvg": _stats([(d.get("renderMs") or {}).get("avg") for d in per]),
            "csvGpuMeanMs": {k: _stats([((c.get("gpu") or {}).get(k) or {}).get("mean") for c in csvs]) for k in passes},
            "profileGpuInclusiveMs": {q: {k: _stats([((d.get("summary") or {}).get(q) or {}).get(k) for d in pg])
                                          for k in sorted({k for d in pg for k in ((d.get("summary") or {}).get(q) or {})})}
                                      for q in queues},
            "luma": {"frameP50": _stats([((s.get("luma") or {}).get("frame") or {}).get("p50") for s in shots]),
                     "center": _stats([(s.get("luma") or {}).get("center") for s in shots]),
                     "faceRoiMean": _stats([((s.get("luma") or {}).get("faceRoi") or {}).get("mean") for s in shots]),
                     "faceRoiP5": _stats([((s.get("luma") or {}).get("faceRoi") or {}).get("p5") for s in shots]),
                     "faceRoiP95": _stats([((s.get("luma") or {}).get("faceRoi") or {}).get("p95") for s in shots]),
                     "faceNeckRoiMean": _stats([((s.get("luma") or {}).get("faceNeckRoi") or {}).get("mean") for s in shots])},
        }
    fps = [((r.get("trace") or {}).get("render") or {}) for r in runs]
    out["fingerprint"] = fps[0] if fps else {}
    out["referenceChecks"] = [r.get("referenceCheck") for r in runs]
    return out


TSR_RES = re.compile(r"TemporalSuperResolution\(sg\.AntiAliasingQuality=(\d)\) (\d+)x(\d+) -> (\d+)x(\d+)")


def derived_metrics(vdir: Path, view: str) -> dict:
    """Per-run derived numbers of one view, then stats over the runs:
    csvPassSum   sum of the CSV GPU/* pass means without GPU/Unaccounted (ms)
    pgGraphicsRoot / pgComputeRoot  ProfileGPU <root> inclusive per queue (one frame)
    pgLumen      ProfileGPU Lumen work: compute LumenSceneLighting + compute DiffuseIndirectAndAO +
                 graphics RenderDeferredLighting/DiffuseIndirectAndAO (composite + reflections) +
                 graphics LumenSceneUpdate*
    tsrInput     internal resolution fed to TSR (screen percentage actually rendered)"""
    per: dict[str, list] = {"csvPassSum": [], "pgGraphicsRoot": [], "pgComputeRoot": [], "pgLumen": [], "tsrInputPct": []}
    for rdir in sorted(vdir.glob("r*")):
        f = rdir / "bench-run.json"
        if not f.is_file():
            continue
        run = json.loads(f.read_text(encoding="utf-8"))
        views = list(((run.get("trace") or {}).get("views") or {}).keys())
        if view not in views:
            continue
        vi = views.index(view)
        if len(run.get("csv") or []) > vi:
            g = run["csv"][vi]["summary"].get("gpu") or {}
            per["csvPassSum"].append(round(sum(x["mean"] for k, x in g.items()
                                                if k.startswith("GPU/") and k != "GPU/Unaccounted"), 4))
        log = rdir / "client.log"
        dumps = parse_profilegpu(log) if log.is_file() else []
        if len(dumps) > vi:
            d = dumps[vi]
            gq = next((q for q in d["queues"] if q.startswith("Graphics")), None)
            cq = next((q for q in d["queues"] if q.startswith("Compute")), None)
            root = lambda q: next((r["inclusiveMs"] for r in d["queues"].get(q, []) if r["name"] == "<root>"), None)  # noqa: E731
            per["pgGraphicsRoot"].append(root(gq) if gq else None)
            per["pgComputeRoot"].append(root(cq) if cq else 0.0)
            lumen = 0.0
            for q, rows in d["queues"].items():
                for i, r in enumerate(rows):
                    if q.startswith("Compute") and r["name"] in ("LumenSceneLighting", "DiffuseIndirectAndAO"):
                        lumen += r["inclusiveMs"]
                    if q.startswith("Graphics") and r["name"].startswith("LumenSceneUpdate"):
                        lumen += r["inclusiveMs"]
                    if q.startswith("Graphics") and r["name"] == "DiffuseIndirectAndAO":
                        lumen += r["inclusiveMs"]
            per["pgLumen"].append(round(lumen, 4))
            for q, rows in d["queues"].items():
                m = next((TSR_RES.search(r["name"]) for r in rows if TSR_RES.search(r["name"])), None)
                if m:
                    per["tsrInputPct"].append(round(100.0 * int(m.group(2)) / int(m.group(4)), 1))
                    break
    return {k: _stats(v) for k, v in per.items()}


def compare(a: dict, b: dict, metric_path: list[str]) -> dict | None:
    def dig(d):
        for k in metric_path:
            d = (d or {}).get(k)
        return d
    sa, sb = dig(a), dig(b)
    if not sa or not sb or not sa.get("n") or not sb.get("n"):
        return None
    delta = sb["mean"] - sa["mean"]
    thr = 2.0 * max(sa["noise"], sb["noise"])
    return {"a": sa["mean"], "b": sb["mean"], "delta": round(delta, 4), "threshold2xNoise": round(thr, 4),
            "significant": abs(delta) > thr}


def cmd_summarize(a) -> int:
    out = {"schema": "unmatched.w4a-render-bench-summary/1", "status": "измерено (RTX 4090, не D-07)",
           "rule": "3 повтора на вариант; шум = max - min по повторам; разница значима, если |Δ| > 2 × шум",
           "variants": {}}
    for v in a.variant_dirs:
        s = summarize_variant(Path(v))
        out["variants"][s["variant"]] = s
    for s in out["variants"].values():
        for view, vs in s["views"].items():
            vs["derived"] = derived_metrics(Path(a.variant_dirs[0]).parent / s["variant"], view)
    pairs = [("dx11-legacy", "dx12-lumen-high"), ("dx12sm5-legacy", "dx12-lumen-high"), ("dx11-legacy", "dx12sm5-legacy"),
             ("dx12-sm5-fallback", "dx12-lumen-high"),
             ("dx12-lumen-high", "dx12-lumen-high-vsm"), ("dx12-lumen-high-csmdefault", "dx12-lumen-high"),
             ("dx12-lumen-high", "dx12-medium"), ("dx12-lumen-high", "dx12-low"), ("dx11-fallback", "dx12-lumen-high")]
    out["comparisons"] = {}
    for b, n in pairs:
        base, new = out["variants"].get(b), out["variants"].get(n)
        if not (base and new):
            continue
        cmp = {}
        for view in sorted(set(base["views"]) & set(new["views"])):
            c = {"gpuMsAvg (RHIGetGPUFrameCycles; DX11 includes submission bubbles)":
                     compare(base, new, ["views", view, "gpuMsAvg"]),
                 "frameMsAvg": compare(base, new, ["views", view, "frameMsAvg"]),
                 "csv GPUTime": compare(base, new, ["views", view, "csvGpuMeanMs", "GPUTime"]),
                 "csv sum of GPU/* passes (w/o Unaccounted)": compare(base, new, ["views", view, "derived", "csvPassSum"]),
                 "ProfileGPU graphics <root>": compare(base, new, ["views", view, "derived", "pgGraphicsRoot"]),
                 "ProfileGPU GI/AO passes (Lumen scene + DiffuseIndirectAndAO)": compare(base, new, ["views", view, "derived", "pgLumen"]),
                 "faceRoiMean (luma 0-255)": compare(base, new, ["views", view, "luma", "faceRoiMean"]),
                 "faceNeckRoiMean (luma 0-255)": compare(base, new, ["views", view, "luma", "faceNeckRoiMean"]),
                 "center luma": compare(base, new, ["views", view, "luma", "center"])}
            passes = set(base["views"][view]["csvGpuMeanMs"]) | set(new["views"][view]["csvGpuMeanMs"])
            c["csvPasses"] = {p: compare(base, new, ["views", view, "csvGpuMeanMs", p]) for p in sorted(passes)
                              if p.startswith("GPU/")}
            cmp[view] = c
        out["comparisons"][f"{b} -> {n}"] = cmp
    write_json(Path(a.out), out)
    print(json.dumps({k: v for k, v in out.items() if k not in ("variants",)}, ensure_ascii=False, indent=1)[:6000])
    return 0


def cmd_reluma(a) -> int:
    """Recompute the frame / face luma of existing run dirs (same PNG + trace)."""
    for d in a.run_dirs:
        f = Path(d) / "bench-run.json"
        rec = json.loads(f.read_text(encoding="utf-8"))
        for view, shot in (rec.get("shots") or {}).items():
            head = ((rec.get("trace") or {}).get("heads") or {}).get(view)
            shot["luma"] = luma_stats(Path(d) / shot["file"], head)
        log = Path(d) / "client.log"
        if log.is_file():
            rec["profileGpu"] = parse_profilegpu(log)
        write_json(f, rec)
        print(d, {v: (s["luma"].get("faceRoi") or {}).get("mean", s["luma"].get("faceRoiSkipped"))
                  for v, s in rec["shots"].items()})
    return 0


def main(argv=None) -> int:
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8")  # cp1251 console/pipe on Windows otherwise
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("run")
    r.add_argument("--variant", required=True)
    r.add_argument("--repeats", type=int, default=3)
    r.add_argument("--out", required=True)
    r.add_argument("--exe", default=str(EXE))
    r.add_argument("--views", default="K1+K2x5")
    r.add_argument("--warmup", type=int, default=30)
    r.add_argument("--settle", type=int, default=8)
    r.add_argument("--measure", type=int, default=20)
    r.add_argument("--bench-fixture", default="", help="-BenchFixture=<json> (default: the client's S08BenchCobble.json)")
    r.add_argument("--name", default="", help="output directory name under --out (default: the variant)")
    s = sub.add_parser("summarize")
    s.add_argument("--out", required=True)
    s.add_argument("variant_dirs", nargs="+")
    sub.add_parser("variants")
    rl = sub.add_parser("reluma", help="recompute shot luma (frame, face ROI) of existing run dirs")
    rl.add_argument("run_dirs", nargs="+")
    a = ap.parse_args(argv)
    if a.cmd == "variants":
        print("\n".join(VARIANTS))
        return 0
    if a.cmd == "run":
        return cmd_run(a)
    if a.cmd == "reluma":
        return cmd_reluma(a)
    return cmd_summarize(a)


if __name__ == "__main__":
    sys.exit(main())
