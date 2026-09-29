"""Compare a repeated asset run with the original one (stage 3, T3.1 dry repeat of ADDING-AN-ASSET.md).

    python tools/tripo-pipeline/review/repro_compare.py --base <run dir> --repro <run dir> --out <repro-report.json>
        [--frames <repro-frames.json of control_scene_analyze.py>] [--log <executor log .md>]

Byte level: every file under export/, preview/*uv0_layout.png and the CLI runs' export/ must have the same SHA-256.
Report level: the JSON reports are compared after one normalisation only -- the run token (directory name of --base
replaced by that of --repro, and the repro build profile id/path/sha by the base ones) -- and after dropping the keys
that record time or a registration moment. Anything else that differs is listed and makes the comparison fail.
Preview renders (EEVEE, not byte-stable) are compared by pixels (mean and max |dRGB|).
"""

import argparse
import hashlib
import json
from pathlib import Path

import numpy as np
from PIL import Image

VOLATILE = {"started_at", "finished_at", "registered_at", "generated_at", "created_at", "at", "time", "elapsed_s",
            "duration_s", "timestamp", "measured_at", "taken_at"}
REPORTS = ["reports/candidate-report.json", "reports/fbx-readback.json",
           "ue-passthrough/reports/import-report.json", "ue-passthrough/reports/verify-report.json",
           "ue-passthrough/reports/export-report.json", "ue-passthrough/reports/ue-import-report.json",
           "ue-candidate/reports/adopt-report.json", "ue-candidate/reports/ue-import-report.json"]
BYTES = ["export", "ue-passthrough/export"]


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def norm(obj, pairs):
    if isinstance(obj, dict):
        return {norm(k, pairs): norm(v, pairs) for k, v in obj.items() if k not in VOLATILE}
    if isinstance(obj, list):
        return [norm(v, pairs) for v in obj]
    if isinstance(obj, str):
        for a, b in pairs:
            obj = obj.replace(a, b)
        return obj
    return obj


def diff(a, b, path=""):
    out = []
    if isinstance(a, dict) and isinstance(b, dict):
        for k in sorted(set(a) | set(b)):
            out += diff(a.get(k), b.get(k), path + "/" + str(k))
    elif isinstance(a, list) and isinstance(b, list) and len(a) == len(b):
        for i, (x, y) in enumerate(zip(a, b)):
            out += diff(x, y, "%s[%d]" % (path, i))
    elif a != b:
        out.append({"path": path, "base": a, "repro": b})
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", required=True)
    ap.add_argument("--repro", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--frames")
    ap.add_argument("--log")
    a = ap.parse_args()
    base, rep = Path(a.base), Path(a.repro)
    pairs = [(rep.name, base.name)]
    # the repro build profile is a copy with its own id/path (ADDING-AN-ASSET.md §4.1 step 3)
    rman = json.loads((rep / "ue-candidate/manifest.json").read_text(encoding="utf-8"))
    bman = json.loads((base / "ue-candidate/manifest.json").read_text(encoding="utf-8"))
    rprof, bprof = rman["config"]["build_profile"], bman["config"]["build_profile"]
    pairs = [(rprof, bprof), (Path(rprof).stem, Path(bprof).stem),
             (sha(rprof), sha(bprof))] + pairs
    report = {"schema": "unmatched.p17-repro-report/1", "base": base.as_posix(), "repro": rep.as_posix(),
              "normalisation": [{"repro": x, "base": y} for x, y in pairs], "ignored_keys": sorted(VOLATILE),
              "bytes": {}, "reports": {}, "previews": {}}
    for d in BYTES:
        for f in sorted((base / d).glob("*")):
            if f.is_file():
                rel = f.relative_to(base).as_posix()
                g = rep / rel
                report["bytes"][rel] = {"base_sha256": sha(f), "repro_sha256": sha(g) if g.exists() else None,
                                        "bytes": f.stat().st_size}
                report["bytes"][rel]["equal"] = report["bytes"][rel]["base_sha256"] == report["bytes"][rel]["repro_sha256"]
    uv = "preview/%s_uv0_layout.png" % json.loads((base / "reports/candidate-report.json").read_text(encoding="utf-8"))[
        "params"]["asset_name"]
    report["bytes"][uv] = {"base_sha256": sha(base / uv), "repro_sha256": sha(rep / uv)}
    report["bytes"][uv]["equal"] = report["bytes"][uv]["base_sha256"] == report["bytes"][uv]["repro_sha256"]
    for rel in REPORTS:
        fb, fr = base / rel, rep / rel
        if not (fb.exists() and fr.exists()):
            report["reports"][rel] = {"compared": False, "base_exists": fb.exists(), "repro_exists": fr.exists()}
            continue
        jb = norm(json.loads(fb.read_text(encoding="utf-8")), [])
        jr = norm(json.loads(fr.read_text(encoding="utf-8")), pairs)
        d = diff(jb, jr)
        report["reports"][rel] = {"compared": True, "differences": d, "equal_after_normalisation": not d}
        if not d:
            # a report that differs from the base only by the run token is the same content: later reports that pin
            # its SHA-256 (adopt pins candidate-report.json and fbx-readback.json) compare with the base SHA
            pairs.append((sha(fr), sha(fb)))
            report["normalisation"].append({"repro": sha(fr), "base": sha(fb), "why": "%s equal after normalisation" % rel})
    for f in sorted((base / "preview").glob("*.png")):
        if f.name == Path(uv).name:
            continue
        g = rep / "preview" / f.name
        A = np.asarray(Image.open(f).convert("RGB"), np.int16)
        B = np.asarray(Image.open(g).convert("RGB"), np.int16)
        report["previews"][f.name] = {"mean_abs_diff": round(float(np.abs(A - B).mean()), 4),
                                      "max_abs_diff": int(np.abs(A - B).max()), "sha_equal": sha(f) == sha(g)}
    if a.frames:
        report["control_scene_frames"] = json.loads(Path(a.frames).read_text(encoding="utf-8"))
    report["summary"] = {
        "bytes_equal": all(v["equal"] for v in report["bytes"].values()),
        "reports_equal": all(v.get("equal_after_normalisation", False) for v in report["reports"].values() if v["compared"]),
        "reports_not_compared": [k for k, v in report["reports"].items() if not v["compared"]],
        "previews_max_abs_diff": max((v["max_abs_diff"] for v in report["previews"].values()), default=None),
        "frames_within_threshold": report.get("control_scene_frames", {}).get("all_within"),
        "credits_spent": 0, "tripo_calls": 0,
    }
    if a.log:
        report["executor_log"] = Path(a.log).name
    Path(a.out).parent.mkdir(parents=True, exist_ok=True)
    Path(a.out).write_text(json.dumps(report, indent=1, sort_keys=True, ensure_ascii=False) + "\n", encoding="utf-8",
                           newline="\n")
    print(json.dumps(report["summary"], indent=1))


if __name__ == "__main__":
    main()
