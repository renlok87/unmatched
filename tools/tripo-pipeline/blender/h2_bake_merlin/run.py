"""Driver of the H2 bake of Merlin (system python). Runs the stages in order as separate processes.

python tools/tripo-pipeline/blender/h2_bake_merlin/run.py --profile <profile.json> [stage ...]
  stages: source retopo uv bake maps rig probe preview sheets  (default: all)
  --blender <exe>    Blender executable (default: profile "blender")

Every Blender stage runs `blender -b --factory-startup --python-exit-code 1 --python <stage> -- <profile>`; its
stdout/stderr go to <run>/logs/<stage>.log. Timings go to <run>/logs/timings.json (not a report: reports stay
byte-deterministic). Exit code != 0 on the first failed stage.
"""

import argparse
import json
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import common as C  # noqa: E402

STAGES = ["source", "retopo", "uv", "bake", "maps", "rig", "probe", "preview", "sheets"]
BLENDER_STAGES = {"source": "stage_source.py", "retopo": "stage_retopo.py", "uv": "stage_uv.py",
                  "bake": "stage_bake.py", "rig": "stage_rig.py", "preview": "stage_preview.py"}
PYTHON_STAGES = {"maps": "maps.py", "sheets": "sheets.py"}


def run(cmd, log, env=None):
    log.parent.mkdir(parents=True, exist_ok=True)
    with open(log, "wb") as handle:
        proc = subprocess.run(cmd, stdout=handle, stderr=subprocess.STDOUT, env=env,
                              creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    return proc.returncode


def probe(prof, blender, logs):
    """rig_deform_probe.py (headless) on the rig .blend and on the exported FBX turned back to the authored frame."""
    tools = C.REPO / "tools" / "tripo-pipeline"
    out = prof.preview / "deform"
    out.mkdir(parents=True, exist_ok=True)
    fbx = prof.export / prof["exports"]["skeletal_fbx"]
    authored = prof.work / "probe-fbx-authored.blend"
    conv = C.REPO / "art" / "pipeline-candidates" / "ASSET-MERLIN-001" / "scripts" / "fbx_to_authored_blend.py"
    rc = run([blender, "-b", "--factory-startup", "--python-exit-code", "1", "--python", str(conv), "--",
              str(fbx), str(authored)], logs / "probe-fbx-authored.log")
    if rc:
        return rc
    rc = run([blender, "-b", "--factory-startup", "--python", str(tools / "anim" / "validate_clip.py"), "--", str(fbx),
              "--skeleton=%s" % prof["armature"]["skeleton"], "--character=Merlin", "--kind=skeletal-mesh",
              "--out=%s" % (prof.reports / "validate-skeletal-mesh.json")], logs / "validate-skeletal-mesh.log")
    # validate_clip ends the process with os._exit(status); its verdict is read from the report by the caller
    for label, src in (("merlin-h2-blend", prof.work / "h2-rig.blend"), ("merlin-h2-fbx", authored)):
        rc = run([blender, "-b", "--factory-startup", "--python-exit-code", "1", "--python",
                  str(tools / "anim" / "rig_deform_probe.py"), "--", str(src), str(out), label],
                 logs / ("probe-%s.log" % label))
        if rc:
            return rc
        rc = run([sys.executable, str(tools / "anim" / "overlay_bones.py"), str(out), label],
                 logs / ("overlay-%s.log" % label))
        if rc:
            return rc
    # the shared rig_deform_probe.py leaves Blender's render stamps in its PNGs (File = host path of the opened
    # .blend, Date, Time, RenderTime): drop those chunks here (pixels untouched), so the committed frames carry no host
    # path and are byte-stable
    stripped = {}
    for png in sorted(out.glob("merlin-h2-*.png")):
        dropped = C.strip_png_metadata(png)
        if dropped:
            stripped[png.name] = len(dropped)
    left = [p.name for p in sorted(out.glob("merlin-h2-*.png")) if C.host_path_hits(p)]
    print("probe: PNG metadata chunks dropped in %d files; files with host paths left: %s" % (len(stripped), left),
          flush=True)
    return 1 if left else 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--profile", required=True)
    ap.add_argument("--blender")
    ap.add_argument("stages", nargs="*")
    a = ap.parse_args()
    prof = C.Profile(a.profile)
    blender = a.blender or prof["blender"]
    stages = a.stages or STAGES
    logs = prof.run_dir / "logs"
    timings_path = logs / "timings.json"
    timings = json.loads(timings_path.read_text(encoding="utf-8")) if timings_path.exists() else {}
    for stage in stages:
        t0 = time.time()
        if stage in BLENDER_STAGES:
            rc = run([blender, "-b", "--factory-startup", "--python-exit-code", "1", "--python",
                      str(HERE / BLENDER_STAGES[stage]), "--", str(prof.path)], logs / (stage + ".log"))
        elif stage in PYTHON_STAGES:
            rc = run([sys.executable, str(HERE / PYTHON_STAGES[stage]), str(prof.path)], logs / (stage + ".log"))
        elif stage == "probe":
            rc = probe(prof, blender, logs)
        else:
            raise SystemExit("unknown stage %s" % stage)
        timings[stage] = {"seconds": round(time.time() - t0, 1), "returncode": rc,
                          "finished": time.strftime("%Y-%m-%dT%H:%M:%S")}
        timings_path.parent.mkdir(parents=True, exist_ok=True)
        timings_path.write_text(json.dumps(timings, indent=1, sort_keys=True) + "\n", encoding="utf-8")
        print("stage %-8s rc=%d %.1fs" % (stage, rc, time.time() - t0), flush=True)
        if rc:
            print("see", logs / (stage + ".log"))
            return rc
    return 0


if __name__ == "__main__":
    sys.exit(main())
