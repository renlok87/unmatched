"""ENV-MAPS lane K driver: the Blender-made environment assets, one fresh headless Blender per step, low priority.

  python -B tools/art/env_kit/run_k_assets.py [--assets tray-t2b,frame,backwall,waterfall] \
      [--steps textures,build,readback,preview] [--blender <blender.exe>] [--threads 4]

Every Blender call is `blender -b --factory-startup -t <threads> --python-exit-code 1 --python <script> -- <params>`
started with BELOW_NORMAL priority and no console window (a GPU benchmark may run in parallel: no GPU work here, the
previews and bakes are Cycles on the CPU). Order matters for 'waterfall': it reads the south-edge rock profile written by
the tray-t2b build (reports/south-profile.json).

Steps per asset (missing ones are skipped):
  textures  system Python (numpy + PIL) texture script -> <run>/export/T_*.png + reports/textures-report.json
  build     Blender build script -> <run>/export/*.fbx, reports/build-report.json (+ asset specific reports)
  readback  for every FBX in build-report.json 'exports': tools/tripo-pipeline/blender/check_static_prop_fbx.py
            (independent, unchanged) -> reports/fbx-readback/<name>.json
  preview   Blender preview script (Cycles CPU) -> <run>/preview/*.jpg + preview.json
Logs: <scratch>/logs/<asset>-<step>.log. Exit code 1 on the first failing step.
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
REPO = HERE.parents[3]
BLENDER = os.environ.get("BLENDER", "C:/Program Files/Blender Foundation/Blender 5.2/blender.exe")
READBACK = REPO / "tools/tripo-pipeline/blender/check_static_prop_fbx.py"
NO_WINDOW = 0x08000000 if os.name == "nt" else 0
BELOW_NORMAL = 0x00004000 if os.name == "nt" else 0

TB = REPO / "art/pipeline-candidates/ASSET-TABLE-BASE-001"
ASSETS = {
    "tray-t2b": {"params": TB / "20261001-tray-t2b/reports/tray-t2b-params.json",
                 "textures": TB / "scripts/tray_t2b_textures.py", "build": TB / "scripts/tray_t2b_build.py",
                 "preview": TB / "scripts/tray_t2b_preview.py"},
    "frame": {"params": REPO / "art/pipeline-candidates/ASSET-MAP-FRAME-002/20261001-frame-v1/reports/frame-params.json",
              "textures": REPO / "art/pipeline-candidates/ASSET-MAP-FRAME-002/scripts/frame_textures.py",
              "build": REPO / "art/pipeline-candidates/ASSET-MAP-FRAME-002/scripts/frame_build.py",
              "preview": REPO / "art/pipeline-candidates/ASSET-MAP-FRAME-002/scripts/frame_preview.py"},
    "backwall": {"params": REPO / "art/pipeline-candidates/ASSET-ENV-M-BACKWALL-001/20261001-backwall-v1/reports/"
                                  "backwall-params.json",
                 "build": REPO / "art/pipeline-candidates/ASSET-ENV-M-BACKWALL-001/scripts/backwall_build.py",
                 "preview": REPO / "art/pipeline-candidates/ASSET-ENV-M-BACKWALL-001/scripts/backwall_preview.py"},
    "waterfall": {"params": REPO / "art/pipeline-candidates/ASSET-ENV-S-WATERFALL-001/20261001-waterfall-v1/reports/"
                                   "waterfall-params.json",
                  "build": REPO / "art/pipeline-candidates/ASSET-ENV-S-WATERFALL-001/scripts/waterfall_build.py",
                  "preview": REPO / "art/pipeline-candidates/ASSET-ENV-S-WATERFALL-001/scripts/waterfall_preview.py"},
}


def run(cmd, log: Path) -> int:
    log.parent.mkdir(parents=True, exist_ok=True)
    t0 = time.time()
    with log.open("w", encoding="utf-8", errors="replace") as f:
        code = subprocess.call([str(c) for c in cmd], cwd=str(REPO), stdout=f, stderr=subprocess.STDOUT,
                               creationflags=NO_WINDOW | BELOW_NORMAL)
    print(f"  {log.stem}: exit {code} in {time.time() - t0:.1f} s  (log {log})", flush=True)
    return code


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n", 1)[0])
    ap.add_argument("--assets", default="tray-t2b,frame,backwall,waterfall")
    ap.add_argument("--steps", default="textures,build,readback,preview")
    ap.add_argument("--blender", default=BLENDER)
    ap.add_argument("--threads", type=int, default=4)
    a = ap.parse_args(argv)
    bl = [a.blender, "-b", "--factory-startup", "-t", str(a.threads), "--python-exit-code", "1", "--python"]
    for key in [s.strip() for s in a.assets.split(",") if s.strip()]:
        if key not in ASSETS:
            raise SystemExit(f"unknown asset {key}; known: {list(ASSETS)}")
        A = ASSETS[key]
        P = json.loads(Path(A["params"]).read_text(encoding="utf-8"))
        run_dir = (REPO / P["run_dir"]).resolve()
        logs = Path(P["scratch_dir"]) / "logs"
        print(f"[{key}] {run_dir.relative_to(REPO).as_posix()}", flush=True)
        for step in [s.strip() for s in a.steps.split(",") if s.strip()]:
            if step == "readback":
                rep = json.loads((run_dir / "reports/build-report.json").read_text(encoding="utf-8"))
                for ex in rep["exports"]:
                    fbx = REPO / ex["fbx"]
                    out = run_dir / "reports/fbx-readback" / (fbx.stem + ".json")
                    out.parent.mkdir(parents=True, exist_ok=True)
                    if run(bl + [READBACK, "--", fbx, out], logs / f"{key}-readback-{fbx.stem}.log") != 0:
                        print(f"K-RUN failed at {key}/readback {fbx.name}")
                        return 1
                continue
            script = A.get(step)
            if script is None:
                continue
            if step == "textures":
                cmd = [sys.executable, "-B", script, "--params", A["params"]]
            else:
                cmd = bl + [script, "--", A["params"]]
            if run(cmd, logs / f"{key}-{step}.log") != 0:
                print(f"K-RUN failed at {key}/{step}")
                return 1
    print("K-RUN ok")
    return 0


if __name__ == "__main__":
    sys.exit(main())
