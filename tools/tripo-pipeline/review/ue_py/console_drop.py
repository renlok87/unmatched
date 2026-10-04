"""UE editor console by file drop: `py "<this file>" <drop dir>` (e.g. from -ExecCmds at the editor start).

For an editor started hidden (-RenderOffScreen: nothing on the user's screen), where SlateInspector cannot focus the
console box and ue_live.Ue.console's typing is lost (measured 2026-10-04, ART-016). The host (ue_live.Ue.console with
UE_CONSOLE_DROP=<drop dir>) writes <drop>/cmd-<seq>.json {"seq", "command"} atomically (.tmp -> rename); a Slate
post-tick callback here takes the files in seq order and runs each command on the game thread, as a typed command:
  py "<script>" [args]  -> the script runs with sys.argv = [script, args...] in fresh globals (the `py` console command);
  anything else         -> unreal.SystemLibrary.execute_console_command on the editor world (cvars, ShowFlag.*, ...).
Then <drop>/done-<seq>.json {"seq", "ok", "error", "ms"}. "quit-editor" closes the editor (unreal.SystemLibrary).
"""
import gc
import json
import os
import shlex
import sys
import time
import traceback

import unreal as u

DROP = sys.argv[-1]
os.makedirs(DROP, exist_ok=True)
_state = {"last": 0.0, "busy": False}


def _write(path, data):
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8", newline="\n") as handle:
        handle.write(json.dumps(data, indent=1) + "\n")
    os.replace(tmp, path)


def _world():
    try:
        return u.get_editor_subsystem(u.UnrealEditorSubsystem).get_editor_world()
    except Exception:  # noqa: BLE001
        return None


def _run(command):
    if command.strip() == "quit-editor":
        u.SystemLibrary.quit_editor()
        return
    if command.startswith("py "):
        parts = shlex.split(command[3:], posix=False)
        script = parts[0].strip('"')
        argv_before = list(sys.argv)
        sys.argv = [script] + [p.strip('"') for p in parts[1:]]
        try:
            glb = {"__name__": "__main__", "__file__": script}
            with open(script, encoding="utf-8") as handle:
                exec(compile(handle.read(), script, "exec"), glb)  # noqa: S102 - the host's own repo scripts
            glb.clear()
        finally:
            sys.argv = argv_before
            gc.collect()
        return
    u.SystemLibrary.execute_console_command(_world(), command)


def _tick(_dt):
    now = time.time()
    if _state["busy"] or now - _state["last"] < 0.25:
        return
    _state["last"] = now
    try:
        names = sorted((n for n in os.listdir(DROP) if n.startswith("cmd-") and n.endswith(".json")),
                       key=lambda n: int(n[4:-5]))
    except OSError:
        return
    for name in names:
        path = os.path.join(DROP, name)
        try:
            with open(path, encoding="utf-8") as handle:
                cmd = json.load(handle)
            os.replace(path, path + ".taken")
        except (OSError, ValueError):
            continue
        _state["busy"] = True
        t0 = time.time()
        res = {"seq": cmd.get("seq"), "command": cmd.get("command"), "ok": True, "error": None}
        try:
            _run(cmd["command"])
        except Exception as exc:  # noqa: BLE001 - reported to the host
            res.update(ok=False, error="%s: %s" % (type(exc).__name__, exc), traceback=traceback.format_exc()[-3000:])
            u.log_error("CONSOLE_DROP_FAILED %s" % cmd.get("command"))
        finally:
            _state["busy"] = False
        res["ms"] = round((time.time() - t0) * 1000.0, 1)
        _write(os.path.join(DROP, "done-%s.json" % cmd.get("seq")), res)


u.register_slate_post_tick_callback(_tick)
_write(os.path.join(DROP, "ready.json"), {"pid": os.getpid(), "drop": DROP, "time": time.time()})
u.log("CONSOLE_DROP_READY %s" % DROP)
