"""ASSET-TABLE-BASE-001 T2: run the whole SM_TableBase_T2 build (system Python; every Blender step is a fresh
headless `blender -b --factory-startup`, CPU only - never a running Blender GUI or MCP session).

  python -B art/pipeline-candidates/ASSET-TABLE-BASE-001/scripts/tray_t2_run.py \
      [--params art/pipeline-candidates/ASSET-TABLE-BASE-001/20261001-tray-t2/reports/tray-t2-params.json] \
      [--steps textures,build,readback,preview] [--blender <blender.exe>]

Steps:
  textures  tray_t2_textures.py (numpy + PIL): Rock058 -> export/T_TableBase_T2_{BC,N,ORM}.png, reports/textures-report.json
  build     tray_t2_build.py (Blender): export/SM_TableBase_T2.fbx, reports/build-report.json, reports/kit-instances.json
  readback  tools/tripo-pipeline/blender/check_static_prop_fbx.py (independent): reports/fbx-readback.json
  preview   tray_t2_preview.py (Blender, Cycles on the CPU): preview/tray-t2-*.jpg + preview/preview.json
Logs: <scratch_dir>/logs/<step>.log. Exit code 1 on the first failing step.
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve()
REPO = HERE.parents[4]
DEFAULT_PARAMS = REPO / "art/pipeline-candidates/ASSET-TABLE-BASE-001/20261001-tray-t2/reports/tray-t2-params.json"
BLENDER = os.environ.get("BLENDER", "C:/Program Files/Blender Foundation/Blender 5.2/blender.exe")
NO_WINDOW = 0x08000000 if os.name == "nt" else 0


def run(cmd, log: Path) -> int:
    log.parent.mkdir(parents=True, exist_ok=True)
    t0 = time.time()
    with log.open("w", encoding="utf-8", errors="replace") as f:
        code = subprocess.call(cmd, cwd=str(REPO), stdout=f, stderr=subprocess.STDOUT, creationflags=NO_WINDOW)
    print(f"  {log.stem}: exit {code} in {time.time() - t0:.1f} s  (log {log})")
    return code


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n", 1)[0])
    ap.add_argument("--params", default=str(DEFAULT_PARAMS))
    ap.add_argument("--steps", default="textures,build,readback,preview")
    ap.add_argument("--blender", default=BLENDER)
    a = ap.parse_args(argv)
    params = Path(a.params).resolve()
    P = json.loads(params.read_text(encoding="utf-8"))
    run_dir = (REPO / P["run_dir"]).resolve()
    logs = Path(P["scratch_dir"]) / "logs"
    bl = [a.blender, "-b", "--factory-startup", "--python-exit-code", "1", "--python"]
    steps = {
        "textures": [sys.executable, "-B", str(HERE.parent / "tray_t2_textures.py"), "--params", str(params)],
        "build": bl + [str(HERE.parent / "tray_t2_build.py"), "--", str(params)],
        "readback": bl + [str(REPO / "tools/tripo-pipeline/blender/check_static_prop_fbx.py"), "--",
                          str(run_dir / "export" / f"{P['asset_name']}.fbx"),
                          str(run_dir / "reports" / "fbx-readback.json")],
        "preview": bl + [str(HERE.parent / "tray_t2_preview.py"), "--", str(params)],
    }
    for name in [s.strip() for s in a.steps.split(",") if s.strip()]:
        if name not in steps:
            raise SystemExit(f"unknown step {name}; known: {list(steps)}")
        if run(steps[name], logs / f"{name}.log") != 0:
            print(f"T2-RUN failed at {name}")
            return 1
    print("T2-RUN ok")
    return 0


if __name__ == "__main__":
    sys.exit(main())
