"""ENV-MAPS P5a: P3 vs P5a packaged -Bench (same variant, views, fixtures; 3 repeats each). Significant if |d| > 2 x max(noise)."""
import json
from pathlib import Path
P3 = json.loads(Path("C:/tmp/wt-envmaps/docs/game-design/evidence/ENV-MAPS/p3-packaged-2026-10-01/bench/p3-bench-summary.json").read_text(encoding="utf-8"))
P5 = json.loads(Path("C:/tmp/envmaps-research/p5a/bench/p5a-bench-summary.json").read_text(encoding="utf-8"))
KEYS = ["gpuMsAvg", "gpuMsP95", "fps", "frameMsAvg", "renderMsAvg", "gameMsAvg"]
CNT = ["RHI/DrawCalls", "RHI/PrimitivesDrawn", "LightCount/All"]
PASSES = ["GPU/Basepass", "GPU/Lights", "GPU/RenderDeferredLighting", "GPU/LumenReflections", "GPU/ShadowDepths",
          "GPU/LumenSceneUpdate", "GPU/Translucency", "GPU/Prepass", "GPU/Postprocessing", "GPU/Unaccounted"]
def cmp(a, b):
    if not a or not b or not a.get("n") or not b.get("n"):
        return None
    d = b["mean"] - a["mean"]; thr = 2 * max(a["noise"], b["noise"])
    return {"p3": a["mean"], "p5a": b["mean"], "delta": round(d, 3), "pct": round(100 * d / a["mean"], 1) if a["mean"] else None,
            "threshold2xNoise": round(thr, 3), "significant": abs(d) > thr}
out = {"schema": "unmatched.envmaps-p5a-vs-p3-bench/1", "rule": "|delta| > 2 x max(noise of 3 repeats) = significant", "boards": {}}
for m in ("cobble", "marmoreal", "sarpedon"):
    out["boards"][m] = {}
    for v in ("K1", "K1x0.65", "K2x1.6", "K2x2.5"):
        a, b = P3["maps"][m][v], P5["maps"][m][v]
        rec = {k: cmp(a.get(k), b.get(k)) for k in KEYS}
        rec["counters"] = {k: cmp(a["counters"].get(k), b["counters"].get(k)) for k in CNT}
        rec["csvGpuMeanMs"] = {k: cmp(a["csvGpuMeanMs"].get(k), b["csvGpuMeanMs"].get(k)) for k in PASSES}
        rec["nvidiaSmiUtilP50"] = cmp(a.get("nvidiaSmiUtilP50"), b.get("nvidiaSmiUtilP50"))
        rec["vramMiBMax"] = cmp(a.get("vramMiBMax"), b.get("vramMiBMax"))
        # environment cost relative to the board's own Cobble baseline (same run set)
        out["boards"][m][v] = rec
for m in ("marmoreal", "sarpedon"):
    for v in ("K1", "K1x0.65", "K2x1.6", "K2x2.5"):
        c3, c5 = P3["maps"]["cobble"][v]["gpuMsAvg"]["mean"], P5["maps"]["cobble"][v]["gpuMsAvg"]["mean"]
        m3, m5 = P3["maps"][m][v]["gpuMsAvg"]["mean"], P5["maps"][m][v]["gpuMsAvg"]["mean"]
        out["boards"][m][v]["envCostVsCobbleGpuMs"] = {"p3": round(m3 - c3, 3), "p5a": round(m5 - c5, 3), "change": round((m5 - c5) - (m3 - c3), 3)}
Path("C:/tmp/envmaps-research/p5a/bench/p5a-vs-p3.json").write_text(json.dumps(out, ensure_ascii=False, indent=1) + "\n", encoding="utf-8", newline="\n")
for m, vs in out["boards"].items():
    for v, r in vs.items():
        g = r["gpuMsAvg"]; f = r["fps"]; rt = r["renderMsAvg"]; gm = r["gameMsAvg"]
        env = r.get("envCostVsCobbleGpuMs")
        top = sorted(((k, x["delta"]) for k, x in r["csvGpuMeanMs"].items() if x), key=lambda t: -abs(t[1]))[:4]
        print(f"{m:9s} {v:7s} gpu {g['p3']:.3f}->{g['p5a']:.3f} d={g['delta']:+.3f} thr={g['threshold2xNoise']:.3f} sig={g['significant']} | p95 {r['gpuMsP95']['p3']:.2f}->{r['gpuMsP95']['p5a']:.2f} | fps {f['p3']:.1f}->{f['p5a']:.1f} | rt {rt['p3']:.2f}->{rt['p5a']:.2f} | game {gm['p3']:.2f}->{gm['p5a']:.2f} | dc {r['counters']['RHI/DrawCalls']['p3']:.0f}->{r['counters']['RHI/DrawCalls']['p5a']:.0f} prims {r['counters']['RHI/PrimitivesDrawn']['p3']/1e6:.2f}->{r['counters']['RHI/PrimitivesDrawn']['p5a']/1e6:.2f} lights {r['counters']['LightCount/All']['p5a']:.0f} | env {env} | {top}")
