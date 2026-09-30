"""UE editor Python task (LIVE editor): remove look-dev "LDv2 *" leftovers from the P1.7 control level and discard its
unsaved in-memory changes WITHOUT saving (orchestrator request 2026-09-30, after the 02:03-02:06 collision).

ARGS {"level": "/Game/ArtTests/P17ControlScene/L_P17ControlScene", "prefix": "LDv2 ", "reload": bool,
      "unload_prefix": "/Game/UM/Materials/v2/_probe/" | null}
Acts only when the review level is the open world. Destroys every actor whose label starts with the prefix, then (reload)
reloads the level from disk with EditorLoadingAndSavingUtils.load_map (the in-memory package is replaced; nothing is
saved). Reports the dirty map/content packages before and after. Never saves anything.
"""
import json

import unreal as u

args = ARGS  # noqa: F821 - injected by ue_py/_run.py
LS = u.EditorLoadingAndSavingUtils
sub = u.get_editor_subsystem(u.EditorActorSubsystem)


def world_path():
    w = u.get_editor_subsystem(u.UnrealEditorSubsystem).get_editor_world()
    p = w.get_path_name().split(".")[0] if w else None
    del w
    return p


def dirty():
    return {"maps": sorted(p.get_path_name() for p in LS.get_dirty_map_packages()),
            "content": sorted(p.get_path_name() for p in LS.get_dirty_content_packages())}


out = {"world_before": world_path(), "dirty_before": dirty()}
if out["world_before"] != args["level"]:
    out["skipped"] = "the review level is not the open world"
else:
    try:
        u.get_editor_subsystem(u.LevelEditorSubsystem).eject_pilot_level_actor()
    except Exception as exc:  # noqa: BLE001
        out["eject_error"] = str(exc)
    gone = []
    for a in list(sub.get_all_level_actors()):
        label = a.get_actor_label()
        if label.startswith(args["prefix"]):
            sub.destroy_actor(a)
            gone.append(label)
    out["destroyed"] = sorted(gone)
    out["dirty_after_destroy"] = dirty()
    if args.get("reload"):
        w2 = LS.load_map(args["level"])
        out["reloaded"] = w2.get_path_name() if w2 else None
        del w2
    out["world_after"] = world_path()
    out["left_with_prefix"] = sorted(a.get_actor_label() for a in sub.get_all_level_actors()
                                     if a.get_actor_label().startswith(args["prefix"]))
    out["actor_count_after"] = len(sub.get_all_level_actors())
prefix = args.get("unload_prefix")
if prefix:
    # scratch probe packages (unsaved MIs / textures of the accent test): unload WITHOUT saving, then drop the folder
    pk = [p for p in list(LS.get_dirty_content_packages()) + list(LS.get_dirty_map_packages())
          if p.get_path_name().startswith(prefix)]
    out["probe_dirty_before_unload"] = sorted(p.get_path_name() for p in pk)
    if pk:
        out["probe_unloaded"] = bool(LS.unload_packages(pk))
    del pk
    folder = prefix.rstrip("/")
    if u.EditorAssetLibrary.does_directory_exist(folder):
        out["probe_dir_deleted"] = bool(u.EditorAssetLibrary.delete_directory(folder))
out["dirty_after"] = dirty()
with open(args["out"], "w", encoding="utf-8", newline="\n") as handle:
    handle.write(json.dumps(out, indent=1, sort_keys=True) + "\n")
