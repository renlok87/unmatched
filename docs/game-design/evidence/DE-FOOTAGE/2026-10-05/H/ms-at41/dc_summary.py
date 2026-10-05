"""Run H R-04 (MS-AT-41): draw calls and GPU per view, base vs plates, from the render_bench CSVs."""
import csv
import json
import sys
from pathlib import Path

ROOT = Path(sys.argv[1])
OUT = Path(sys.argv[2])
VIEWS = ["K1", "K2x1.6"]


def read_csv(p):
    rows = list(csv.reader(open(p, encoding="utf-8", errors="replace")))
    if rows[-1] and rows[-1][0] == "[HasHeaderRowAtEnd]":
        head, body = rows[-2], rows[1:-2]
    else:
        head, body = rows[0], rows[1:]
    idx = {h: i for i, h in enumerate(head)}
    fi = idx["FrameTime"]
    data = []
    for r in body:
        try:
            float(r[fi])
            data.append(r)
        except (ValueError, IndexError):
            pass
    out = {}
    for h, i in idx.items():
        if h == "RHI/DrawCalls" or h.startswith("DrawCall/") or h == "GPUTime":
            vals = []
            for r in data:
                try:
                    vals.append(float(r[i]) if i < len(r) else 0.0)
                except ValueError:
                    pass
            if vals:
                out[h] = sum(vals) / len(vals)
    return out


def run_dir(name):
    res = []
    for rd in sorted((ROOT / name).glob("r*")):
        rec = json.loads((rd / "bench-run.json").read_text(encoding="utf-8"))
        csvs = [rd / c["file"] for c in rec["csv"]]
        views = rec["trace"]["views"]
        per = {}
        for v, c in zip(VIEWS, csvs):
            s = read_csv(c)
            per[v] = {"gpuMs": (views.get(v, {}).get("gpuMs") or {}).get("avg"), "drawCalls": round(s["RHI/DrawCalls"], 2),
                      "passes": {k[9:]: round(val, 2) for k, val in s.items() if k.startswith("DrawCall/")}}
        res.append(per)
    return res


summary = {"schema": "run-h.ms-at-41/1",
           "rule": "06 MS-AT-41: GPU <= +0.30 ms, draw calls <= 7 + 4*S (S = MS-HL ghost sections; MS-T-10 not built, S = 0)",
           "package": "e35c69f1 (run H acceptance, R-02..R-05)", "gpu": "RTX 4090, no frame cap, packaged -Bench, same flags as run B",
           "maps": {}}
for m in ("marmoreal", "sarpedon"):
    base, plates = run_dir(f"{m}-base"), run_dir(f"{m}-plates2")
    plates0 = run_dir(f"{m}-plates0")
    mm = {}
    for v in VIEWS:
        b = [r[v] for r in base]
        p = [r[v] for r in plates]
        db = sum(x["drawCalls"] for x in b) / len(b)
        dp = sum(x["drawCalls"] for x in p) / len(p)
        gb = sum(x["gpuMs"] for x in b) / len(b)
        gp = sum(x["gpuMs"] for x in p) / len(p)
        passes = {}
        for k in sorted(set(b[0]["passes"]) | set(p[0]["passes"])):
            pb = sum(x["passes"].get(k, 0) for x in b) / len(b)
            pp = sum(x["passes"].get(k, 0) for x in p) / len(p)
            if abs(pp - pb) >= 0.05:
                passes[k] = round(pp - pb, 2)
        mm[v] = {"gpuMsBase": [x["gpuMs"] for x in b], "gpuMsPlates": [x["gpuMs"] for x in p], "dGpuMs": round(gp - gb, 3),
                 "drawCallsBase": [x["drawCalls"] for x in b], "drawCallsPlates": [x["drawCalls"] for x in p],
                 "dDrawCalls": round(dp - db, 2), "dPasses": passes,
                 "drawCallsCandidatesScene0": [r[v]["drawCalls"] for r in plates0]}
    summary["maps"][m] = mm
OUT.write_text(json.dumps(summary, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
for m, mm in summary["maps"].items():
    for v, d in mm.items():
        print(m, v, "dc", d["drawCallsBase"], "->", d["drawCallsPlates"], "d", d["dDrawCalls"], "gpu d", d["dGpuMs"], d["dPasses"],
              "scene0", d["drawCallsCandidatesScene0"])
