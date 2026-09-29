"""Blender entry of the H2 bake stages (headless only):

  blender -b --factory-startup --python-exit-code 1 --python tools/tripo-pipeline/blender/h2_bake/blender_entry.py -- <params.json>

params: {"stage": prepare|retopo|close|uv|bake|aux|rig|seams|preview|curve|ld_fbx|ld_preview, "profile": <json>, "run_dir": <dir>,
"repo_root": <dir>, ...}; look-dev stages also get "lookdev": <look-dev profile> (profile = its source H2 profile).
The package is imported fresh from its directory (the parent directory also provides candidate_build, read-only)."""

import importlib
import json
import sys
import traceback
from pathlib import Path

import bpy

if not bpy.app.background:
    raise RuntimeError("h2_bake/blender_entry.py: headless only (blender -b)")

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))

STAGES = {"prepare": "st_prepare", "retopo": "st_retopo", "close": "st_close", "uv": "st_uv", "bake": "st_bake", "aux": "st_aux",
          "rig": "st_rig", "seams": "st_seams", "preview": "st_preview", "curve": "st_curve",
          "ld_fbx": "st_lookdev", "ld_preview": "st_lookdev"}


def main():
    params = json.loads(Path(sys.argv[sys.argv.index("--") + 1]).read_text(encoding="utf-8"))
    for name in [m for m in list(sys.modules) if m == "h2_bake" or m.startswith("h2_bake.")]:
        del sys.modules[name]
    prof = importlib.import_module("h2_bake.profile")
    profile = prof.load(params["profile"])
    stage = importlib.import_module("h2_bake." + STAGES[params["stage"]])
    stage.run(params, profile)
    print("H2_BAKE_STAGE_OK", params["stage"], flush=True)


try:
    main()
except Exception:
    traceback.print_exc()
    sys.stdout.flush()
    raise
