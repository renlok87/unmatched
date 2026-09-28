"""UE editor Python runner: `py "<this file>" <args.json>`; args.json = {"script": <path>, "out": <path>, ...}.

Executes the script with ARGS (the parsed args.json) in its globals. Any exception is written to
args["out"] as {"error": ..., "traceback": ...}, so the host never waits for a missing file.
"""
import json
import sys
import traceback

import unreal as u

_args_path = sys.argv[-1]
ARGS = json.load(open(_args_path, encoding="utf-8"))
try:
    _code = open(ARGS["script"], encoding="utf-8").read()
    exec(compile(_code, ARGS["script"], "exec"), {"__name__": "__ue_task__", "ARGS": ARGS, "unreal": u})
except Exception as exc:  # noqa: BLE001 - reported to the host
    with open(ARGS["out"], "w", encoding="utf-8", newline="\n") as handle:
        handle.write(json.dumps({"error": "%s: %s" % (type(exc).__name__, exc),
                                 "traceback": traceback.format_exc()}, indent=1) + "\n")
    u.log_error("TRIPO_UE_PY_FAILED %s" % ARGS["script"])
