"""UE editor Python (run in the LIVE editor via `py "<this file>" <out.json>`): read-only editor state.

Dirty map/content packages, current level, project directory, engine version and the console
variables this task toggles. Writes <out.json>; changes nothing.
"""
import json
import sys

import unreal as u

out_path = sys.argv[-1]
cvars = {}
for name in ("Interchange.FeatureFlags.Import.FBX", "Interchange.FeatureFlags.Import.Enable"):
    try:
        cvars[name] = u.SystemLibrary.get_console_variable_bool_value(name)
    except Exception as exc:  # noqa: BLE001 - report instead of failing
        cvars[name] = "error: %s" % exc
world = u.get_editor_subsystem(u.UnrealEditorSubsystem).get_editor_world()
data = {
    "engine_version": u.SystemLibrary.get_engine_version(),
    "project_dir": u.Paths.convert_relative_path_to_full(u.Paths.project_dir()),
    "current_level": world.get_path_name() if world else None,
    "dirty_maps": sorted(p.get_name() for p in u.EditorLoadingAndSavingUtils.get_dirty_map_packages()),
    "dirty_content": sorted(p.get_name() for p in u.EditorLoadingAndSavingUtils.get_dirty_content_packages()),
    "cvars": cvars,
}
with open(out_path, "w", encoding="utf-8", newline="\n") as handle:
    handle.write(json.dumps(data, indent=1, sort_keys=True) + "\n")
u.log("TRIPO_UE_PY_OK editor_state")
