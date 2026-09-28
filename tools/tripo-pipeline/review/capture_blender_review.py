"""Host driver: editor review frames of a pipeline candidate from the LIVE Blender via blender_mcp.py.

    python tools/tripo-pipeline/review/capture_blender_review.py --run-dir <run> --out <dir> [--max-size 1600]

Frames are editor viewport screenshots (orthographic, solid shading with texture
colour; backface culling as listed per view). Left figure = untouched Tripo GLB
scaled to the candidate height, right figure = the candidate from the run's work
.blend. They illustrate the orientation (winding) contract; they are NOT art
acceptance, NOT game camera and NOT UE rendering. The live file is never saved;
teardown always runs and restores the viewport.
"""

import argparse
import json
import subprocess
import sys
import tempfile
import time
from pathlib import Path

CLIENT = "C:/Users/ren/.claude/mcp-servers/clients/blender_mcp.py"
SCRIPT = Path(__file__).resolve().parent / "blender_review.py"
SOURCE_OFFSET_X = -0.45

VIEWS = [
    # pair views: front = source left / candidate right; rear = candidate left / source right
    {"name": "front-pair-culling", "euler_deg": [90, 0, 0], "center_m": [-0.225, 0, 0.29], "distance": 0.75,
     "backface_culling": True},
    {"name": "rear-pair-culling", "euler_deg": [90, 0, 180], "center_m": [-0.225, 0, 0.29], "distance": 0.75,
     "backface_culling": True},
    {"name": "front-pair-no-culling", "euler_deg": [90, 0, 0], "center_m": [-0.225, 0, 0.29], "distance": 0.75,
     "backface_culling": False},
]
for tag, x in (("source", SOURCE_OFFSET_X), ("candidate", 0.0)):
    VIEWS += [
        {"name": "front-head-%s-culling" % tag, "euler_deg": [90, 0, 0], "center_m": [x, 0, 0.43], "distance": 0.2,
         "backface_culling": True},
        {"name": "rear-neck-%s-culling" % tag, "euler_deg": [90, 0, 180], "center_m": [x, 0, 0.41], "distance": 0.2,
         "backface_culling": True},
        {"name": "front-arms-%s-culling" % tag, "euler_deg": [90, 0, 0], "center_m": [x, 0, 0.31], "distance": 0.26,
         "backface_culling": True},
        {"name": "rear-bow-arm-%s-culling" % tag, "euler_deg": [90, 0, 180], "center_m": [x + 0.08, 0, 0.31],
         "distance": 0.2, "backface_culling": True},
    ]
VIEWS.append({"name": "three-quarter-candidate", "euler_deg": [70, 0, 35], "center_m": [0.0, 0, 0.27],
              "distance": 0.45, "backface_culling": True})


def exec_blender(mode, params):
    code = "REVIEW_MODE = %r\nREVIEW_PARAMS = %r\n" % (mode, params) + SCRIPT.read_text(encoding="utf-8")
    with tempfile.NamedTemporaryFile("w", suffix=".py", delete=False, encoding="utf-8") as handle:
        handle.write(code)
        path = handle.name
    try:
        proc = subprocess.run([sys.executable, CLIENT, "exec", path], capture_output=True, timeout=600)
    finally:
        Path(path).unlink(missing_ok=True)
    res = json.loads(proc.stdout.decode("utf-8", "replace") or "{}")
    if proc.returncode != 0 or res.get("status") == "error":
        raise RuntimeError("blender %s failed: %s" % (mode, json.dumps(res)[:1500]))
    return (res.get("result") or {}).get("result", "")


def shot(path, max_size):
    proc = subprocess.run([sys.executable, CLIENT, "shot", str(path), str(max_size)], capture_output=True, timeout=600)
    res = json.loads(proc.stdout.decode("utf-8", "replace") or "{}")
    if proc.returncode != 0 or res.get("status") == "error":
        raise RuntimeError("screenshot failed: %s" % json.dumps(res)[:800])
    return res.get("result") or {}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--run-dir", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--max-size", type=int, default=1600)
    args = ap.parse_args()
    run = Path(args.run_dir).resolve()
    manifest = json.loads((run / "manifest.json").read_text(encoding="utf-8"))
    profile = json.loads((Path(__file__).resolve().parents[3] / manifest["config"]["build_profile"]).read_text(encoding="utf-8"))
    blend = run / ("work/%s-candidate.blend" % manifest["config"]["export_basename"])
    src = manifest["sources"][manifest["config"]["primary_source"]]
    glb = next(f["path"] for f in src["files"] if f["role"] == manifest["config"]["primary_role"])
    repo = Path(__file__).resolve().parents[3]
    out = Path(args.out).resolve()
    out.mkdir(parents=True, exist_ok=True)
    meta = {"run_dir": run.name, "kind": "editor viewport frames (live Blender via blender-mcp), not art acceptance",
            "left": "untouched Tripo GLB %s scaled to %.2f m" % (glb, profile["scale"]["figure_height_m"]),
            "right": "candidate work .blend (build stage)", "shading": "SOLID, texture colour, studio light, overlays off",
            "frames": {}}
    params = {"blend": str(blend), "source_glb": str(repo / glb), "height_m": profile["scale"]["figure_height_m"],
              "source_offset_x_m": SOURCE_OFFSET_X}
    meta["setup"] = exec_blender("setup", params).strip()[-400:]
    try:
        for v in VIEWS:
            exec_blender("view", {"view": v})
            time.sleep(0.5)
            path = out / ("blender-%s.png" % v["name"])
            info = shot(path, args.max_size)
            meta["frames"][path.name] = {"view": v, "width": info.get("width"), "height": info.get("height"),
                                         "method": info.get("method")}
            print(path.name, info.get("width"), info.get("height"), info.get("method"))
    finally:
        meta["teardown"] = exec_blender("teardown", {}).strip()[-200:]
    (out / "blender-frames.json").write_text(json.dumps(meta, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    print("teardown:", meta["teardown"])


if __name__ == "__main__":
    main()
