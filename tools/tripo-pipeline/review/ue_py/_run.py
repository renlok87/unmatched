"""UE editor Python runner: `py "<this file>" <args.json>`; args.json = {"script": <path>, "out": <path>, ...}.

Executes the script with ARGS (the parsed args.json) in its globals. Any exception is written to
args["out"] as {"error": ..., "traceback": ...}, so the host never waits for a missing file. The globals are
garbage-collected afterwards (no Python reference may keep a level's actors alive across a map change).
"""
import json
import sys
import traceback

import unreal as u

_args_path = sys.argv[-1]
ARGS = json.load(open(_args_path, encoding="utf-8"))
# proof for the host that the typed command started (ue_live.Ue.console retypes a lost command, never a started one)
with open(ARGS["out"] + ".started", "w", encoding="utf-8") as _handle:
    _handle.write("started\n")
try:
    _code = open(ARGS["script"], encoding="utf-8").read()
    exec(compile(_code, ARGS["script"], "exec"), {"__name__": "__ue_task__", "ARGS": ARGS, "unreal": u})
except Exception as exc:  # noqa: BLE001 - reported to the host
    with open(ARGS["out"], "w", encoding="utf-8", newline="\n") as handle:
        handle.write(json.dumps({"error": "%s: %s" % (type(exc).__name__, exc),
                                 "traceback": traceback.format_exc()}, indent=1) + "\n")
    u.log_error("TRIPO_UE_PY_FAILED %s" % ARGS["script"])
finally:
    # Drop the task's globals now: UE Python wrappers keep actors (and so their world) alive, and a world that is
    # still referenced when the editor loads another map is a fatal "World Memory Leaks" error (EditorServer.cpp).
    import gc
    gc.collect()
