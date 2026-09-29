"""UE editor Python task (LIVE editor via review/ue_live.py run_task): read-only actor labels of the current level.

ARGS: {"out": ...}. Writes {"level": <path>, "labels": [...], "actors": [[label, class], ...]} to ARGS["out"]; changes nothing. Used by
anim/h2anim_ue.py frames to refuse a capture while another task's temporary actors (e.g. look-dev "LDv2 *") are
in the review level (anim-v2 fix, after the 2026-09-30 collision in L_P17ControlScene).
"""
import json

import unreal as u

args = ARGS  # noqa: F821 - injected by ue_py/_run.py
world = u.get_editor_subsystem(u.UnrealEditorSubsystem).get_editor_world()
actors = sorted([a.get_actor_label(), a.get_class().get_name()]
                for a in u.get_editor_subsystem(u.EditorActorSubsystem).get_all_level_actors())
with open(args["out"], "w", encoding="utf-8", newline="\n") as handle:
    handle.write(json.dumps({"level": world.get_path_name() if world else None, "labels": [x[0] for x in actors],
                             "actors": actors}, indent=1) + "\n")
