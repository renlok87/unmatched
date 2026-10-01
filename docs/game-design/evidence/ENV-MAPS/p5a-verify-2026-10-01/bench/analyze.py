"""ENV-MAPS P5a (copy of P3 analyze.py): aggregate packaged -Bench runs (trace + CSV counters + nvidia-smi in window + pmon)."""
import csv, json, re, sys, datetime as dt, math
from pathlib import Path
RUNS = Path("C:/tmp/envmaps-research/p5a/bench/runs-raw")
MAPS = ["cobble", "marmoreal", "sarpedon"]
VIEWS = ["K1", "K1x0.65", "K2x1.6", "K2x2.5"]
COUNTERS = ["RHI/DrawCalls", "RHI/PrimitivesDrawn", "LightCount/All", "LightCount/UpdatedShadowMaps",
            "DrawCall/Basepass", "DrawCall/ShadowDepths", "DrawCall/Prepass"]
PASSES = ["GPUTime", "GPU/Basepass", "GPU/Prepass", "GPU/ShadowDepths", "GPU/Lights", "GPU/LumenSceneLighting",
          "GPU/LumenScreenProbeGather", "GPU/LumenReflections", "GPU/LumenSceneUpdate", "GPU/DiffuseIndirectAndAO",
          "GPU/RenderDeferredLighting", "GPU/Translucency", "GPU/TSR", "GPU/Postprocessing", "GPU/Fog", "GPU/HZB",
          "GPU/Unaccounted"]

def csv_rows(p):
    rows = list(csv.reader(open(p, encoding="utf-8", errors="replace", newline="")))
    if rows and rows[-1] and rows[-1][0] == "[HasHeaderRowAtEnd]":
        head, body = rows[-2], rows[1:-2]
    else:
        head, body = rows[0], rows[1:]
    return {h: i for i, h in enumerate(head)}, body

def col_mean(idx, body, name):
    i = idx.get(name)
    if i is None: return None
    v = []
    for r in body:
        try: v.append(float(r[i]) if i < len(r) else 0.0)
        except ValueError: pass
    return round(sum(v) / len(v), 3) if v else None

def stats(vals):
    vals = [x for x in vals if x is not None]
    if not vals: return {"n": 0}
    m = sum(vals) / len(vals)
    return {"n": len(vals), "mean": round(m, 3), "min": round(min(vals), 3), "max": round(max(vals), 3),
            "noise": round(max(vals) - min(vals), 3)}

def smi_window(smi, end_utc, secs):
    # nvidia-smi timestamp is local time (UTC+5)
    out = []
    for r in smi:
        try:
            t = dt.datetime.strptime(r[0].strip(), "%Y/%m/%d %H:%M:%S.%f") - dt.timedelta(hours=5)
            if end_utc - dt.timedelta(seconds=secs) <= t <= end_utc:
                out.append((float(r[1]), float(r[2])))
        except (ValueError, IndexError):
            pass
    if not out: return None
    u = sorted(x[0] for x in out)
    return {"n": len(u), "utilP50": u[len(u)//2], "utilP95": u[min(len(u)-1, math.ceil(0.95*len(u))-1)],
            "memUsedMiBMax": max(x[1] for x in out)}

per = {}
for m in MAPS:
    for rd in sorted((RUNS / m).glob("r*")):
        rec = json.loads((rd / "bench-run.json").read_text(encoding="utf-8"))
        tr = rec["trace"] or {}
        smi = [r for r in csv.reader(open(rd / "nvidia-smi.csv", encoding="utf-8")) if len(r) >= 3][1:]
        tl = (rd / "bench.trace.log").read_text(encoding="utf-8", errors="replace").splitlines()
        ends = {}
        for ln in tl:
            mm = re.match(r"(\d{4}\.\d\d\.\d\d-\d\d\.\d\d\.\d\d) BENCH measure view=(\S+) window=([\d.]+)", ln)
            if mm:
                ends[mm.group(2)] = (dt.datetime.strptime(mm.group(1), "%Y.%m.%d-%H.%M.%S"), float(mm.group(3)))
        for vi, v in enumerate(VIEWS):
            d = (tr.get("views") or {}).get(v, {})
            c = rec["csv"][vi] if len(rec["csv"]) > vi else None
            cnt, pas = {}, {}
            if c:
                idx, body = csv_rows(rd / c["file"])
                cnt = {k: col_mean(idx, body, k) for k in COUNTERS}
                pas = {k: col_mean(idx, body, k) for k in PASSES}
            e = ends.get(v)
            per.setdefault(m, {}).setdefault(v, []).append({
                "run": rd.name, "fps": d.get("fps"), "frameMs": d.get("frameMs"), "gpuMs": d.get("gpuMs"),
                "renderMs": d.get("renderMs"), "gameMs": d.get("gameMs"), "hitches50": d.get("hitches50"),
                "frames": d.get("frames"), "counters": cnt, "csvGpuMeanMs": pas,
                "nvidiaSmiInWindow": smi_window(smi, e[0], e[1]) if e else None,
                "reference": (rec.get("referenceCheck") or {}).get(f"bench-{v.replace('.', 'p')}-1920x1080.png", {}).get("reference"),
                "exitCode": rec.get("exitCode"), "durationS": rec.get("durationS")})

summary = {"schema": "unmatched.envmaps-p5a-bench-summary/1",
           "status": "измерено; dev-PC (RTX 4090, i9-13900F), не D-07",
           "rule": "3 повтора; шум = max - min; разница значима, если |Δ| > 2 × max(шум)", "maps": {}, "vsCobble": {}}
for m, views in per.items():
    summary["maps"][m] = {}
    for v, runs in views.items():
        g = lambda f: stats([f(r) for r in runs])
        summary["maps"][m][v] = {
            "fps": g(lambda r: r["fps"]),
            "frameMsAvg": g(lambda r: (r["frameMs"] or {}).get("avg")), "frameMsP95": g(lambda r: (r["frameMs"] or {}).get("p95")),
            "gpuMsAvg": g(lambda r: (r["gpuMs"] or {}).get("avg")), "gpuMsP95": g(lambda r: (r["gpuMs"] or {}).get("p95")),
            "renderMsAvg": g(lambda r: (r["renderMs"] or {}).get("avg")), "renderMsP95": g(lambda r: (r["renderMs"] or {}).get("p95")),
            "gameMsAvg": g(lambda r: (r["gameMs"] or {}).get("avg")),
            "hitches50": g(lambda r: r["hitches50"]),
            "counters": {k: g(lambda r, k=k: r["counters"].get(k)) for k in COUNTERS},
            "csvGpuMeanMs": {k: g(lambda r, k=k: r["csvGpuMeanMs"].get(k)) for k in PASSES},
            "nvidiaSmiUtilP50": g(lambda r: (r["nvidiaSmiInWindow"] or {}).get("utilP50")),
            "nvidiaSmiUtilP95": g(lambda r: (r["nvidiaSmiInWindow"] or {}).get("utilP95")),
            "vramMiBMax": g(lambda r: (r["nvidiaSmiInWindow"] or {}).get("memUsedMiBMax")),
            "referenceAll": all(r["reference"] for r in runs), "runs": runs}

def cmp(a, b):
    if not a.get("n") or not b.get("n"): return None
    d = b["mean"] - a["mean"]; thr = 2 * max(a["noise"], b["noise"])
    return {"cobble": a["mean"], "map": b["mean"], "delta": round(d, 3),
            "pct": round(100 * d / a["mean"], 1) if a["mean"] else None, "threshold2xNoise": round(thr, 3), "significant": abs(d) > thr}
for m in ("marmoreal", "sarpedon"):
    summary["vsCobble"][m] = {}
    for v in VIEWS:
        A, B = summary["maps"]["cobble"][v], summary["maps"][m][v]
        c = {k: cmp(A[k], B[k]) for k in ("fps", "frameMsAvg", "gpuMsAvg", "gpuMsP95", "renderMsAvg")}
        c["counters"] = {k: cmp(A["counters"][k], B["counters"][k]) for k in COUNTERS}
        c["csvGpuMeanMs"] = {k: cmp(A["csvGpuMeanMs"][k], B["csvGpuMeanMs"][k]) for k in PASSES}
        summary["vsCobble"][m][v] = c
out = Path(sys.argv[1] if len(sys.argv) > 1 else "C:/tmp/envmaps-research/p5a/bench/p5a-bench-summary.json")
out.write_text(json.dumps(summary, ensure_ascii=False, indent=1) + "\n", encoding="utf-8", newline="\n")
for m in MAPS:
    for v in VIEWS:
        s = summary["maps"][m][v]
        f = lambda k: f"{s[k].get('mean')}±{s[k].get('noise')}"
        print(m, v, "fps", f("fps"), "gpu", f("gpuMsAvg"), "p95", f("gpuMsP95"), "rend", f("renderMsAvg"),
              "dc", s["counters"]["RHI/DrawCalls"].get("mean"), "prims", s["counters"]["RHI/PrimitivesDrawn"].get("mean"),
              "lights", s["counters"]["LightCount/All"].get("mean"), "smi", s["nvidiaSmiUtilP50"].get("mean"), "ref", s["referenceAll"])
