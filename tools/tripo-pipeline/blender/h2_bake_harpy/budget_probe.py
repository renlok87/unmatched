"""Budget probe of an H2 bake (system Python + headless Blender): the lowpoly stage at scaled triangle targets in
temporary run directories, and the surface deviation converted to screen pixels of the game camera.

    python budget_probe.py <profile.json> <run_dir> <tmp_dir> 0.5 0.75 1.5

For every factor: copies <run>/work/h2-highpoly.blend into <tmp_dir>/budget_<f>/work, scales every
lowpoly.parts.*.target_triangles (and priority min_triangles) by the factor (repair plugs/caps unchanged), runs stage_lowpoly.py and
reads its report. Adds the run's own level (factor 1.0) and writes <run>/reports/budget-probe.json: worst-part p99/max
high->low distance in final millimetres (seat scale of h2-rig-report.json) and in pixels at K2 (7.5 m) and 4.8 m for
the game camera (horizontal FOV 35 deg, 1920 px). Temporary directories are removed afterwards.
"""

import json
import math
import shutil
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
profile_path, run, tmp = Path(sys.argv[1]).resolve(), Path(sys.argv[2]).resolve(), Path(sys.argv[3]).resolve()
factors = [float(x) for x in sys.argv[4:]]
B = "C:/Program Files/Blender Foundation/Blender 5.2/blender.exe"
levels = {}


def summarise(rep):
    return {"triangles_total": rep["triangles_total"],
            "parts": {p: {"tris": v["triangles"], "p50_mm": v["distance_high_to_low"]["p50_mm"],
                          "p99_mm": v["distance_high_to_low"]["p99_mm"], "max_mm": v["distance_high_to_low"]["max_mm"]}
                      for p, v in rep["parts"].items()}}


for fac in factors:
    d = tmp / ("budget_%g" % fac)
    (d / "work").mkdir(parents=True, exist_ok=True)
    shutil.copyfile(run / "work" / "h2-highpoly.blend", d / "work" / "h2-highpoly.blend")
    prof = json.loads(profile_path.read_text(encoding="utf-8"))
    for part, cfg in prof["lowpoly"]["parts"].items():
        if part.startswith(("plug", "cap")):
            continue
        cfg["target_triangles"] = int(round(cfg["target_triangles"] * fac))
        for reg in cfg.get("priority_regions", []):
            if reg.get("min_triangles"):
                reg["min_triangles"] = int(round(reg["min_triangles"] * fac))
    (d / "profile.json").write_text(json.dumps(prof, indent=1), encoding="utf-8")
    with open(d / "lowpoly.log", "w") as log:
        subprocess.run([B, "-b", "--factory-startup", "--python", str(HERE / "stage_lowpoly.py"), "--",
                        str(d / "profile.json"), str(d)], stdout=log, stderr=subprocess.STDOUT, check=True)
    levels[str(fac)] = summarise(json.loads((d / "reports" / "h2-lowpoly-report.json").read_text(encoding="utf-8")))
    shutil.rmtree(d)
levels["1.0"] = summarise(json.loads((run / "reports" / "h2-lowpoly-report.json").read_text(encoding="utf-8")))
s = json.loads((run / "reports" / "h2-rig-report.json").read_text(encoding="utf-8"))["seat"]["scale"]
k2 = 2 * 7.5 * math.tan(math.radians(17.5)) / 1920 * 1000
k2c = 2 * 4.8 * math.tan(math.radians(17.5)) / 1920 * 1000
table = {}
for f, v in sorted(levels.items(), key=lambda kv: float(kv[0])):
    ps = {p: q for p, q in v["parts"].items() if not p.startswith(("plug", "cap"))}
    wp99 = max(q["p99_mm"] for q in ps.values()) * s
    wmax = max(q["max_mm"] for q in ps.values()) * s
    table[f] = {"tris": v["triangles_total"], "worst_part_p99_final_mm": round(wp99, 3),
                "worst_part_max_final_mm": round(wmax, 3), "p99_px_K2": round(wp99 / k2, 2),
                "max_px_K2": round(wmax / k2, 2), "max_px_K2close": round(wmax / k2c, 2)}
out = {"mm_per_px": {"K2_7.5m": round(k2, 4), "K2close_4.8m": round(k2c, 4)}, "seat_scale": s, "levels": table,
       "per_level_parts": levels, "note": "surface deviation high->low per part (stage_lowpoly, 20 000 area samples), "
       "worst part; pixels at the camera target distance"}
(run / "reports" / "budget-probe.json").write_text(json.dumps(out, indent=1, sort_keys=True) + "\n", encoding="utf-8")
print("BUDGET_OK", json.dumps(table))
