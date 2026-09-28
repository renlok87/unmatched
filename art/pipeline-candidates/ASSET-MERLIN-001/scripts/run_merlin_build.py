#!/usr/bin/env python3
"""Run the Merlin build stage headless with the parameters tools/tripo-pipeline would pass (exec_build).

    python art/pipeline-candidates/ASSET-MERLIN-001/scripts/run_merlin_build.py \
        --run-dir art/pipeline-candidates/ASSET-MERLIN-001/20260928-blender-um-fbx-v1

Reads the run manifest written by tripo_pipeline.py (primary source, build profile, atlas outputs), refuses
to run unless preflight/import/verify/atlas are completed and the atlas files still match their hashes,
then runs build_merlin_candidate.py in a fresh `blender -b --factory-startup` process. Like the CLI it
requires the stage marker and no traceback in the log (Blender can exit 0 after a Python error). Outputs:
export/<skeletal>.fbx, export/<base>.fbx, work/<basename>-candidate.blend, reports/build-report.json,
logs/build.log. The CLI manifest is not modified: the CLI's own build stage (build_candidate.py) is
Medusa-specific, see the build profile status_note.
"""

import argparse
import hashlib
import json
import re
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
BUILDER = HERE / "build_merlin_candidate.py"
DEFAULT_BLENDER = "C:/Program Files/Blender Foundation/Blender 5.2/blender.exe"
MARKER = "TRIPO_PIPELINE_STAGE_OK build"


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--run-dir", required=True)
    ap.add_argument("--blender", default=DEFAULT_BLENDER)
    args = ap.parse_args()
    run = (REPO / args.run_dir).resolve() if not Path(args.run_dir).is_absolute() else Path(args.run_dir)
    manifest = json.loads((run / "manifest.json").read_text(encoding="utf-8"))
    cfg = manifest["config"]
    for stage in ("preflight", "import", "verify", "atlas"):
        if (manifest["stages"].get(stage) or {}).get("status") != "completed":
            sys.exit("stage %s is not completed in the manifest" % stage)
    for rel, info in manifest["stages"]["atlas"]["outputs"].items():
        if sha256(run / rel) != info["sha256"]:
            sys.exit("atlas output changed since the atlas stage: %s" % rel)
    src = manifest["sources"][cfg["primary_source"]]
    primary = next(f for f in src["files"] if f["role"] == cfg["primary_role"])
    source = REPO / primary["path"]
    if sha256(source) != primary["sha256"]:
        sys.exit("primary source changed since registration")
    profile_path = REPO / cfg["build_profile"]
    profile = json.loads(profile_path.read_text(encoding="utf-8"))
    params = {
        "source": str(source), "profile": str(profile_path),
        "atlas_report": str(run / "reports/atlas-report.json"), "textures_dir": str(run / "textures"),
        "repo_root": str(REPO), "blend_out": str(run / ("work/%s-candidate.blend" % cfg["export_basename"])),
        "sk_fbx_out": str(run / "export" / profile["exports"]["skeletal_fbx"]),
        "base_fbx_out": str(run / "export" / profile["exports"]["base_fbx"]),
        "report_out": str(run / "reports/build-report.json"),
        "fbx_preset": str(REPO / profile["fbx_preset"]),
    }
    (run / "work").mkdir(exist_ok=True)
    (run / "logs").mkdir(exist_ok=True)
    params_path = run / "work/build-params.json"
    params_path.write_text(json.dumps(params, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    proc = subprocess.run([args.blender, "-b", "--factory-startup", "--python", str(BUILDER), "--", str(params_path)],
                          stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=1800,
                          creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    text = proc.stdout.decode("utf-8", "replace")
    (run / "logs/build.log").write_text(text, encoding="utf-8")
    if proc.returncode != 0 or MARKER not in text or re.search(r"Traceback|Error: script failed", text):
        print(text[-4000:])
        sys.exit("build failed (exit %s); see %s" % (proc.returncode, run / "logs/build.log"))
    report = json.loads((run / "reports/build-report.json").read_text(encoding="utf-8"))
    for key in ("skeletal", "base"):
        path = run / "export" / report["exports"][key]["file"]
        if sha256(path) != report["exports"][key]["sha256"]:
            sys.exit("build report hash mismatch for %s" % path.name)
    failed = sorted(k for k, c in report["checks"].items() if not c["passed"])
    print("build: passed=%s checks=%d failed=%s sk=%s base=%s" % (report["passed"], len(report["checks"]), failed,
          report["exports"]["skeletal"]["sha256"][:12], report["exports"]["base"]["sha256"][:12]))
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    sys.exit(main())
