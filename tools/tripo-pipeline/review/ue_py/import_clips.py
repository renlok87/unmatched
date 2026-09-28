"""UE editor Python task (LIVE editor via review/ue_live.py run_task): import FBX clips onto an existing skeleton.

ARGS: {"out": ..., "cvar": "Interchange.FeatureFlags.Import.FBX",
       "clips": [{"fbx": <abs path>, "folder": "/Game/PipelineCandidates/...", "name": "AM_...",
                  "skeleton": "/Game/.../X_Skeleton", "uniform_scale": null | float}]}

Legacy FBX importer (the cvar is set to 0 for the imports and restored to its previous value in
`finally`, both values are reported). FbxImportUI as in VALIDATION.md step 2 / import_clip():
import_mesh False, import_as_skeletal True, FBXIT_ANIMATION, import_animations True, no materials or
textures, the given skeleton. `uniform_scale` null keeps the importer default and reports it.
replace_existing=True + a fixed destination name: a second import replaces, never creates Name_1.
Only folders under /Game/PipelineCandidates/ are accepted. Saves the imported assets only.
"""
import json

import unreal as u

args = ARGS  # noqa: F821 - injected by ue_py/_run.py
cvar = args.get("cvar", "Interchange.FeatureFlags.Import.FBX")


def cvar_value():
    return u.SystemLibrary.get_console_variable_bool_value(cvar)


report = {"cvar": cvar, "cvar_before": cvar_value(), "clips": []}
tools = u.AssetToolsHelpers.get_asset_tools()
try:
    u.SystemLibrary.execute_console_command(None, "%s 0" % cvar)
    report["cvar_during_import"] = cvar_value()
    if report["cvar_during_import"]:
        raise RuntimeError("could not switch %s off" % cvar)
    for clip in args["clips"]:
        folder = clip["folder"].rstrip("/")
        if not folder.startswith("/Game/PipelineCandidates/") or ".." in folder:
            raise RuntimeError("refusing destination outside /Game/PipelineCandidates: %s" % folder)
        skeleton = u.load_asset(clip["skeleton"])
        if skeleton is None:
            raise RuntimeError("skeleton not found: %s" % clip["skeleton"])
        ui = u.FbxImportUI()
        ui.set_editor_property("import_mesh", False)
        ui.set_editor_property("import_as_skeletal", True)
        ui.set_editor_property("mesh_type_to_import", u.FBXImportType.FBXIT_ANIMATION)
        ui.set_editor_property("import_animations", True)
        ui.set_editor_property("import_materials", False)
        ui.set_editor_property("import_textures", False)
        ui.set_editor_property("automated_import_should_detect_type", False)
        ui.set_editor_property("skeleton", skeleton)
        anim_data = ui.get_editor_property("anim_sequence_import_data")
        default_scale = anim_data.get_editor_property("import_uniform_scale")
        if clip.get("uniform_scale") is not None:
            anim_data.set_editor_property("import_uniform_scale", float(clip["uniform_scale"]))
        used_scale = anim_data.get_editor_property("import_uniform_scale")
        task = u.AssetImportTask()
        task.set_editor_property("filename", clip["fbx"])
        task.set_editor_property("destination_path", folder)
        task.set_editor_property("destination_name", clip["name"])
        task.set_editor_property("replace_existing", True)
        task.set_editor_property("automated", True)
        task.set_editor_property("save", True)
        task.set_editor_property("options", ui)
        existed = u.EditorAssetLibrary.does_asset_exist("%s/%s" % (folder, clip["name"]))
        tools.import_asset_tasks([task])
        imported = [str(p) for p in task.get_editor_property("imported_object_paths")]
        report["clips"].append({"fbx": clip["fbx"], "folder": folder, "name": clip["name"],
                                "skeleton": clip["skeleton"], "existed_before": existed,
                                "import_uniform_scale_default": round(default_scale, 6),
                                "import_uniform_scale_used": round(used_scale, 6),
                                "imported_object_paths": imported})
finally:
    u.SystemLibrary.execute_console_command(None, "%s %d" % (cvar, 1 if report["cvar_before"] else 0))
    report["cvar_after"] = cvar_value()
    report["cvar_restored"] = report["cvar_after"] == report["cvar_before"]
    with open(args["out"], "w", encoding="utf-8", newline="\n") as handle:
        handle.write(json.dumps(report, indent=1, sort_keys=True) + "\n")
u.log("TRIPO_UE_PY_OK import_clips")
