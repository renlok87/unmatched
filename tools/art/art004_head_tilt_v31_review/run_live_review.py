"""Live-Blender review of Medusa v2 vs head-tilt v3.1 (stage 3 T1.2, 2026-09-28).

System Python, with a running Blender 5.2 GUI and the MCP add-on on 127.0.0.1:9876:

  python tools/art/art004_head_tilt_v31_review/run_live_review.py [OUT_DIR]

OUT_DIR defaults to C:/tmp/t12-v31/live (scratch, not in git). Steps, all through
C:/Users/ren/.claude/mcp-servers/clients/blender_mcp.py:
  live_l0_state.py   snapshot of the user's session (window scene, datablock counts, viewport);
  live_l1_setup.py   isolated scene T12_V31_Review: imports the saved v2 and v3.1 a/b/c FBX
                     (medusa.blend is never opened), one textured material from
                     textures/T_Medusa_Atlas_BC.png, one camera;
  live_l2_view.py    per shot: camera + viewport in camera view, solid/studio/texture,
                     backface culling on (UE materials are one-sided), overlays off;
                     then get_viewport_screenshot;
  live_l9_cleanup.py removes exactly the datablocks created since l1 (pointer diff, no
                     orphans_purge), restores the viewport; l0 is repeated and must match.
Viewport screenshots are editor/Blender frames: not UE, not packaged, not byte-reproducible.
Never call read_factory_settings / SystemExit in the live Blender (it drops the MCP server).
"""

import json
import math
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
CLIENT = "C:/Users/ren/.claude/mcp-servers/clients/blender_mcp.py"
OUT = Path(sys.argv[1] if len(sys.argv) > 1 else "C:/tmp/t12-v31/live")

_C, _S = math.cos(math.radians(55)), math.sin(math.radians(55))


def d10(tx, tz, dist=2.0):
    return [tx, -dist * _C, tz + dist * _S]


# Figures: v2 at x = -0.25 m, v3.1 a/b/c at 0, 0.25, 0.5 m (live_l1_setup.py OFFSET).
SHOTS = {
    "d10-heads-v2-v31a": ("O", d10(-0.145, .44), [-0.145, 0, .44], .40),
    "d10-heads-v31a-b-c": ("O", d10(0.23, .44), [0.23, 0, .44], .66),
    "k2-persp-v2-v31a": ("P", d10(-0.145, .29, 1.3), [-0.145, 0, .29], 35),
    "neck34R-v2": ("O", [-0.27 + 1.41, -1.41, .40], [-0.27, 0, .40], .16),
    "neck34R-v31a": ("O", [-0.02 + 1.41, -1.41, .40], [-0.02, 0, .40], .16),
    "rear34L-v2": ("O", [-0.27 - 1.41, 1.41, .42], [-0.30, .04, .42], .22),
    "rear34L-v31a": ("O", [-0.02 - 1.41, 1.41, .42], [-0.05, .04, .42], .22),
    "bowarm-rear-v2": ("O", [-0.25 + .04, 2, .32], [-0.25 + .04, 0, .32], .20),
    "bowarm-rear-v31a": ("O", [.04, 2, .32], [.04, 0, .32], .20),
    "hands-front-v2-v31a": ("O", [-0.125, -2, .31], [-0.125, 0, .31], .48),
}


def call(*args):
    res = subprocess.run(["python", CLIENT, *args], capture_output=True, text=True, encoding="utf-8")
    if '"status": "success"' not in res.stdout:
        raise RuntimeError("blender_mcp %s failed: %s %s" % (args[0], res.stdout[-400:], res.stderr[-400:]))
    return json.loads(res.stdout)


def run_file(name, prefix=""):
    code = prefix + (HERE / name).read_text(encoding="utf-8")
    return call("exec-str", code)["result"]["result"]


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    before = run_file("live_l0_state.py")
    asset = (REPO / "blender/ASSET-MEDUSA-001").as_posix() + "/"
    setup = run_file("live_l1_setup.py", "import bpy\nbpy.app.driver_namespace['T12_V31_ROOT'] = %r\n" % asset)
    shots = {}
    try:
        for name, shot in SHOTS.items():
            run_file("live_l2_view.py", "import bpy\nbpy.app.driver_namespace['T12_V31_SHOT'] = %r\n" % (tuple(shot),))
            time.sleep(0.8)
            path = OUT / (name + ".png")
            call("shot", str(path), "1400")
            shots[name] = path.name
    finally:
        cleanup = run_file("live_l9_cleanup.py")
    after = run_file("live_l0_state.py")
    same = json.loads(before)["ids"] == json.loads(after)["ids"] and \
        json.loads(before)["windows"] == json.loads(after)["windows"]
    report = {"setup": setup, "shots": shots, "cleanup": cleanup, "state_before": before,
              "state_after": after, "session_restored": same}
    (OUT / "live-review.json").write_text(json.dumps(report, indent=1) + "\n", encoding="utf-8")
    print("ART004_V31_LIVE_REVIEW", "RESTORED" if same else "NOT_RESTORED", OUT)
    return 0 if same else 1


if __name__ == "__main__":
    sys.exit(main())
