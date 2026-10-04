"""UE editor task (UnrealEditor-Cmd -ExecutePythonScript, -RenderOffScreen), run by tools/art/de010/de010.py apply.

ARGS: JSON file named by the environment variable DE010_ARGS:
  {"out": <report.json>, "master": {<ARGS of tools/art/material_library/ue/um_v2_master.py>, "out": <json>},
   "master_script": <path of um_v2_master.py>, "clips": [{"key", "path", "frame", "fps"}], "notify_class": "S08ContactAnimNotify"}
1. M_UM_Figure_v2 is rebuilt in place by the existing builder um_v2_master.py with the v2.2 graph of
   tools/art/material_library/ue_v2_master.py (hit tint, CPD 12); "instances" is empty, so no MI is touched.
2. Every LungeAttack gets exactly one "Contact" notify (US08ContactAnimNotify) on the notify track "Contact" at
   frame / fps of its build profile; an earlier "Contact" notify is removed first (idempotent). The play length and
   the frame count are read before and after (they must not change). The clips are saved.
Then the editor quits.
"""
import json
import os
import traceback

import unreal as u

ARGS = json.load(open(os.environ["DE010_ARGS"], encoding="utf-8"))
LIB = u.AnimationLibrary
EAL = u.EditorAssetLibrary
TRACK = "Contact"


def obj(path):
    return path if "." in path.rsplit("/", 1)[-1] else "%s.%s" % (path, path.rsplit("/", 1)[-1])


def load(path):
    a = u.load_asset(obj(path))
    if a is None:
        raise RuntimeError("asset not found: %s" % path)
    return a


def notifies(seq):
    res = []
    for ev in LIB.get_animation_notify_events(seq):
        n = ev.get_editor_property("notify")
        res.append({"name": str(ev.get_editor_property("notify_name")),
                    "time": round(float(LIB.get_anim_notify_event_trigger_time(ev)), 5),
                    "class": n.get_class().get_name() if n else None})
    return res


def clip_info(seq):
    return {"play_length": round(float(seq.get_play_length()), 5), "frames": int(LIB.get_num_frames(seq)),
            "tracks": [str(t) for t in LIB.get_animation_notify_track_names(seq)], "notifies": notifies(seq)}


report = {}
try:
    m = dict(ARGS["master"])
    code = open(ARGS["master_script"], encoding="utf-8").read()
    exec(compile(code, ARGS["master_script"], "exec"), {"__name__": "__ue_task__", "ARGS": m, "unreal": u})
    report["master"] = json.load(open(m["out"], encoding="utf-8"))
    cls = getattr(u, ARGS["notify_class"]).static_class()
    report["clips"] = {}
    for clip in ARGS["clips"]:
        seq = load(clip["path"])
        before = clip_info(seq)
        removed = LIB.remove_animation_notify_events_by_name(seq, "Contact")
        if not LIB.is_valid_anim_notify_track_name(seq, TRACK):
            LIB.add_animation_notify_track(seq, TRACK, u.LinearColor(1.0, 0.25, 0.2, 1.0))
        t = float(clip["frame"]) / float(clip["fps"])
        notify = LIB.add_animation_notify_event(seq, TRACK, t, cls)
        if notify is None:
            raise RuntimeError("could not add the Contact notify to %s at %.4f s" % (clip["path"], t))
        if not EAL.save_loaded_asset(seq, False):
            raise RuntimeError("could not save %s" % clip["path"])
        after = clip_info(seq)
        report["clips"][clip["key"]] = {"path": clip["path"], "frame": clip["frame"], "fps": clip["fps"],
                                        "time": round(t, 5), "removed": int(removed), "before": before,
                                        "after": after}
    u.log("DE010_APPLY_COMPLETE")
except Exception:  # noqa: BLE001 - reported to the host
    report["error"] = traceback.format_exc()
    u.log_error("DE010_APPLY_FAILED\n" + report["error"])
with open(ARGS["out"], "w", encoding="utf-8", newline="\n") as handle:
    handle.write(json.dumps(report, indent=1, sort_keys=True) + "\n")
u.SystemLibrary.quit_editor()
