#!/usr/bin/env python3
"""Run the Harpy build stage headless with the parameters tools/tripo-pipeline would pass (exec_build),
plus the reference high-poly GLB for the per-face orientation vote.

    python art/pipeline-candidates/ASSET-HARPY-001/scripts/run_harpy_build.py \
        --run-dir art/pipeline-candidates/ASSET-HARPY-001/20260928-blender-um-fbx-v1

Reads the run manifest written by tripo_pipeline.py (primary source, reference source file, build profile),
refuses to run unless preflight/import/verify are completed in the manifest and the atlas stage of
atlas_harpy.py passed with its files still matching the atlas report, then runs build_harpy_candidate.py in a
fresh `blender -b --factory-startup` process. Like the CLI it requires the stage marker and no traceback in the
log (Blender can exit 0 after a Python error). Outputs: export/<skeletal>.fbx, export/<base>.fbx,
work/<basename>-candidate.blend, reports/build-report.json, logs/build.log. The CLI manifest is not
modified: the CLI's own build stage (build_candidate.py) is Medusa-specific, see the build profile status_note.

--faulthandler (diagnostics only) sets HARPY_BUILD_FAULTHANDLER=1 for the builder. On Windows, Python's
faulthandler also prints first-chance exceptions that Blender handles itself; Blender 5.2.2 prints 0-20
"Windows fatal exception: access violation" lines during its own exit even for an empty script, exit code 0.
Such a log is kept apart (logs/build-faulthandler.log) and is not the stage log.
"""

import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
BUILDER = HERE / "build_harpy_candidate.py"
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
    ap.add_argument("--faulthandler", action="store_true",
                    help="diagnostics: enable Python faulthandler in the builder (see the module docstring)")
    args = ap.parse_args()
    run = (REPO / args.run_dir).resolve() if not Path(args.run_dir).is_absolute() else Path(args.run_dir)
    manifest = json.loads((run / "manifest.json").read_text(encoding="utf-8"))
    cfg = manifest["config"]
    for stage in ("preflight", "import", "verify"):
        if (manifest["stages"].get(stage) or {}).get("status") != "completed":
            sys.exit("stage %s is not completed in the manifest" % stage)
    atlas = json.loads((run / "reports/atlas-report.json").read_text(encoding="utf-8"))
    if not atlas.get("passed"):
        sys.exit("atlas report did not pass")
    for key, info in atlas["files"].items():
        if sha256(run / "textures" / info["file"]) != info["sha256"]:
            sys.exit("atlas output changed since the atlas stage: %s" % info["file"])
    src = manifest["sources"][cfg["primary_source"]]
    primary = next(f for f in src["files"] if f["role"] == cfg["primary_role"])
    source = REPO / primary["path"]
    if sha256(source) != primary["sha256"]:
        sys.exit("primary source changed since registration")
    if atlas["source"]["sha256"] != primary["sha256"]:
        sys.exit("atlas was built from another source")
    profile_path = REPO / cfg["build_profile"]
    profile = json.loads(profile_path.read_text(encoding="utf-8"))
    rcfg = profile["orientation"]["per_face_reference"]
    ref_src = manifest["sources"][rcfg["source_id"]]
    ref = next(f for f in ref_src["files"] if f["role"] == rcfg["role"])
    reference = REPO / ref["path"]
    if sha256(reference) != ref["sha256"]:
        sys.exit("reference source changed since registration")
    params = {
        "source": str(source), "profile": str(profile_path), "reference_glb": str(reference),
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
    env = dict(os.environ)
    env.pop("HARPY_BUILD_FAULTHANDLER", None)
    if args.faulthandler:
        env["HARPY_BUILD_FAULTHANDLER"] = "1"
    log_path = run / ("logs/build-faulthandler.log" if args.faulthandler else "logs/build.log")
    proc = subprocess.run([args.blender, "-b", "--factory-startup", "--python", str(BUILDER), "--", str(params_path)],
                          stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=1800, env=env,
                          creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    text = proc.stdout.decode("utf-8", "replace")
    log_path.write_text(text, encoding="utf-8")
    if proc.returncode != 0 or MARKER not in text or re.search(r"Traceback|Error: script failed", text):
        print(text[-6000:])
        sys.exit("build failed (exit %s); see %s" % (proc.returncode, log_path))
    if not args.faulthandler and "Windows fatal exception" in text:
        sys.exit("unexpected faulthandler output with faulthandler off; see %s" % log_path)
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
