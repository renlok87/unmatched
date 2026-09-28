"""Path roots of the offline A1 review scripts (added 2026-09-28 after the P0 manifest review).

Offline scripts (plain Python, no live editor): assemble.py, composites.py, build_json.py,
junction_enclosed.py, ue_frame_diffs.py; ue_face_metrics.py and analyze_id.py use only
paths relative to the scratch directory or argv. They import this module, so they also run
from the main checkout after integration. Run them with the scratch directory as the
current directory, as before.

REPO       checkout that contains this folder (tools/art/art004_head_tilt_v3_mcp_review),
           resolved from __file__; override with ART004_A1_REPO.
SCRATCH    scratch directory of the live review (frames_ev13/, blender/renders/, followup/,
           *.json); default C:/tmp/a1v3, override with ART004_A1_SCRATCH. Not in git and
           not durable.
ARTIFACTS  the art chat's CLI SceneCapture output (git-ignored). Default
           REPO/unreal/Unmatched/Artifacts/ART004Face; override with ART004_A1_ARTIFACTS.
           The v3 CLI frames exist only in the art worktree
           (C:/Users/ren/.codex/worktrees/art-foundation/unmached/unreal/Unmatched/Artifacts/ART004Face),
           so from the main checkout set ART004_A1_ARTIFACTS to it; otherwise
           assemble.py and ue_frame_diffs.py stop with FileNotFoundError.

Scripts that ran inside the live editors keep the absolute paths of the 2026-09-28 run as
a record and do not use this module: blender/b*.py (sent to the live Blender through
blender_mcp.py exec, no __file__ there), bview.py, and the UE-side ue_sockets.py,
ue_dirty_probe.py, calib.py (live UE MCP). Their paths were not changed after the run
(only b9_socket.py's angle/header and b99_cleanup.py's warning were edited, see there).
Running them from another checkout requires changing ROOT/SRC/OUT and C:/tmp/a1v3 in
them by hand.
"""
import os
from pathlib import Path


def _dir(value):
    return Path(value).resolve().as_posix().rstrip("/") + "/"


REPO = _dir(os.environ.get("ART004_A1_REPO") or Path(__file__).resolve().parents[3])
SCRATCH = _dir(os.environ.get("ART004_A1_SCRATCH") or "C:/tmp/a1v3")
ARTIFACTS = _dir(os.environ.get("ART004_A1_ARTIFACTS") or REPO + "unreal/Unmatched/Artifacts/ART004Face")
EVIDENCE = REPO + "docs/game-design/evidence/ART-004/"
PROBE = EVIDENCE + "head-tilt-v3-probe-2026-09-28/"
