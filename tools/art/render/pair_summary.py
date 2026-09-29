#!/usr/bin/env python3
"""W4-A (b)+(c): live pair perf and Medusa face luma, old DX11 build vs DX12 + Lumen High.

Reads run dirs written by tools/art/art004_live_k2.py run (run-phase2-demo pair at
-ClientFps 30, host K2 5x on Medusa, joiner K1) plus their idle-GPU baselines:
  * GPU total utilisation while both clients run (nvidia-smi 500 ms, whole GPU incl.
    the user's editor / browser), mean and p95, and the same minus the idle baseline;
  * per-client effective fps, frame p95, gpuMs (DX11 gpuMs includes idle bubbles);
  * host K2 5x face ROI luma (face, and face + throat), placed from the traced Head socket with the
    per-mesh screen offset of render_bench.FACE_ROI_CALIBRATION (render_bench.luma_stats), joiner K1
    frame luma;
  * the RENDER fingerprint of each SHOT (none on the pre-W4 build) against the reference.

  python tools/art/render/pair_summary.py --out <json> --set dx11-old=<dir> --set dx12-lumen=<dir>
Each <dir> holds run-*/ and baseline-*/gpu-baseline.json. Differences count only when
|delta| > 2 x the larger repeat noise (max - min over the runs).
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent))
import render_bench as B  # noqa: E402
import render_fingerprint as RF  # noqa: E402


def head_line(trace: Path) -> dict | None:
    head = None
    for ln in RF.read_lines(trace):
        body = RF.payload(ln)
        if body.startswith("SHOT head fighter="):
            head = dict(re.findall(r"(\w+)=(\([^)]*\)|\S+)", body[len("SHOT head "):]))
    return head


def summarize_set(d: Path, ref: dict) -> dict:
    runs = []
    for rd in sorted(d.glob("run-*")):
        perf = json.loads((rd / "perf.json").read_text(encoding="utf-8")) if (rd / "perf.json").is_file() else {}
        host_png = rd / "phase2-board-host-1920x1080.png"
        join_png = rd / "phase2-board-joiner-1920x1080.png"
        host_trace = rd / "phase2-client-host.trace.log"
        luma_host = B.luma_stats(host_png, head_line(host_trace)) if host_png.is_file() else None
        luma_join = B.luma_stats(join_png, None) if join_png.is_file() else None
        fps = {}
        for role in ("host", "joiner"):
            t = rd / f"phase2-client-{role}.trace.log"
            block = RF.fingerprint_for_shot(RF.read_lines(t), f"phase2-board-{role}-1920x1080.png") if t.is_file() else None
            ok, why = RF.check(block["render"] if block else None, ref)
            fps[role] = {"reference": ok, "reasons": why[:6],
                         "fingerprint": {k: (block["render"] or {}).get(k) for k in
                                         ("rhi", "featureLevel", "gi", "refl", "preset", "screenPct", "tMaxFPS", "lightUnits")}
                         if block and block["render"] else None}
        clients = {}
        for role, c in (perf.get("clients") or {}).items():
            s = (c.get("summary") or {}).get("started") or {}
            clients[role] = {"fps": s.get("fps"), "frameMsP95": (s.get("frameMs") or {}).get("p95"),
                             "gpuMsAvg": (s.get("gpuMs") or {}).get("avg"), "renderMsAvg": (s.get("renderMs") or {}).get("avg")}
        runs.append({"run": rd.name, "gpuTotal": (perf.get("gpuTotal") or {}).get("utilizationPct"),
                     "clients": clients, "hostK2": luma_host, "joinerK1": luma_join, "render": fps})
    base = [json.loads(p.read_text(encoding="utf-8"))["gpuUtilizationPct"] for p in sorted(d.glob("baseline-*/gpu-baseline.json"))]
    idle = B._stats([b.get("mean") for b in base])
    st = B._stats
    agg = {
        "gpuTotalMean": st([(r["gpuTotal"] or {}).get("mean") for r in runs]),
        "gpuTotalP95": st([(r["gpuTotal"] or {}).get("p95") for r in runs]),
        "idleBaselineMean": idle,
        "hostFps": st([r["clients"].get("host", {}).get("fps") for r in runs]),
        "joinerFps": st([r["clients"].get("joiner", {}).get("fps") for r in runs]),
        "hostFrameP95": st([r["clients"].get("host", {}).get("frameMsP95") for r in runs]),
        "joinerFrameP95": st([r["clients"].get("joiner", {}).get("frameMsP95") for r in runs]),
        "hostGpuMsAvg": st([r["clients"].get("host", {}).get("gpuMsAvg") for r in runs]),
        "hostFaceRoi": st([((r["hostK2"] or {}).get("faceRoi") or {}).get("mean") for r in runs]),
        "hostFaceRoiP5": st([((r["hostK2"] or {}).get("faceRoi") or {}).get("p5") for r in runs]),
        "hostFaceRoiP95": st([((r["hostK2"] or {}).get("faceRoi") or {}).get("p95") for r in runs]),
        "hostFaceNeckRoi": st([((r["hostK2"] or {}).get("faceNeckRoi") or {}).get("mean") for r in runs]),
        "hostFrameP50": st([((r["hostK2"] or {}).get("frame") or {}).get("p50") for r in runs]),
        "hostFrameP10": st([((r["hostK2"] or {}).get("frame") or {}).get("p10") for r in runs]),
        "joinerFrameP50": st([((r["joinerK1"] or {}).get("frame") or {}).get("p50") for r in runs]),
        "joinerCenter": st([(r["joinerK1"] or {}).get("center") for r in runs]),
    }
    if idle.get("n") and agg["gpuTotalMean"].get("n"):
        agg["pairAddsOverIdlePct"] = round(agg["gpuTotalMean"]["mean"] - idle["mean"], 2)
    return {"dir": B.rel(d), "runs": runs, "aggregate": agg}


def main(argv=None) -> int:
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out", required=True)
    ap.add_argument("--set", action="append", required=True, help="name=<dir with run-*/ and baseline-*/>")
    a = ap.parse_args(argv)
    ref = RF.load_reference()
    out = {"schema": "unmatched.w4a-pair-summary/1", "status": "измерено (RTX 4090, не D-07)",
           "rule": "шум = max - min по прогонам; разница значима, если |Δ| > 2 × max(шум)", "sets": {}}
    for s in a.set:
        name, path = s.split("=", 1)
        out["sets"][name] = summarize_set(Path(path), ref)
    names = list(out["sets"])
    if len(names) == 2:
        A, Bn = (out["sets"][n]["aggregate"] for n in names)
        cmp = {}
        for k in A:
            if isinstance(A.get(k), dict) and isinstance(Bn.get(k), dict) and A[k].get("n") and Bn[k].get("n"):
                delta = Bn[k]["mean"] - A[k]["mean"]
                thr = 2 * max(A[k]["noise"], Bn[k]["noise"])
                cmp[k] = {names[0]: A[k]["mean"], names[1]: Bn[k]["mean"], "delta": round(delta, 3),
                          "threshold2xNoise": round(thr, 3), "significant": abs(delta) > thr}
        out["comparison"] = cmp
    B.write_json(Path(a.out), out)
    print(json.dumps(out.get("comparison", {}), ensure_ascii=False, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
