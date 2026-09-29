"""UE editor Python task (LIVE editor via review/ue_live.py run_task): import FBX clips onto an existing skeleton.

ARGS: {"out": ..., "clips": [{"fbx": <abs path>, "folder": "/Game/PipelineCandidates/...", "name": "AM_...",
                              "skeleton": "/Game/.../X_Skeleton", "uniform_scale": null | float,
                              "force_root_lock": true (default)}]}

Legacy FBX importer through an explicit `task.factory = FbxFactory()` (W4-B, engine gate memo, importer topic):
AssetTools only routes a task to Interchange when it has no factory (AssetTools.cpp), so the clip import no longer
switches the global CVar Interchange.FeatureFlags.Import.FBX in the live editor (until W4-B this task set it to 0 for
the import and restored it). The CVar is only read and reported before/after (it must stay unchanged).
FbxImportUI as in VALIDATION.md step 2 / import_clip(): import_mesh False, import_as_skeletal True,
FBXIT_ANIMATION, import_animations True, no materials or textures, the given skeleton. `uniform_scale` null keeps the
importer default and reports it. After the import every AnimSequence gets bForceRootLock = true (rig contract v2 /
memo §1 item 5: bone 0 keeps its rest transform while the clip plays; root motion stays opt-in per clip); the value is
read back and reported. A clip that already exists is deleted first and imported fresh (an import over it took the
reimport path, which used Interchange despite the explicit factory, measured 2026-09-29); every sequence reports its
AssetImportData class (legacy_fbx_import). A fixed destination name: a second import replaces, never creates Name_1.
Only folders under /Game/PipelineCandidates/ are accepted. Saves the imported assets only.
"""
import json

import unreal as u

args = ARGS  # noqa: F821 - injected by ue_py/_run.py
cvar = args.get("cvar", "Interchange.FeatureFlags.Import.FBX")


def cvar_value():
    return u.SystemLibrary.get_console_variable_bool_value(cvar)


report = {"cvar": cvar, "cvar_before": cvar_value(), "factory": "FbxFactory (explicit, legacy)", "clips": []}
tools = u.AssetToolsHelpers.get_asset_tools()
try:
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
        ui.set_editor_property("original_import_type", u.FBXImportType.FBXIT_ANIMATION)
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
        task.set_editor_property("save", False)
        task.set_editor_property("factory", u.FbxFactory())
        task.set_editor_property("options", ui)
        target = "%s/%s" % (folder, clip["name"])
        existed = u.EditorAssetLibrary.does_asset_exist(target)
        if existed:
            # measured 2026-09-29 (W4-B): an import over an existing clip goes through the reimport path, and that
            # path used Interchange (InterchangeAssetImportData) even with task.factory = FbxFactory. The clip lives in
            # /Game/PipelineCandidates (checked above), so it is deleted first and imported fresh by the legacy factory.
            if not u.EditorAssetLibrary.delete_asset(target):
                raise RuntimeError("could not delete the previous clip %s" % target)
        tools.import_asset_tasks([task])
        imported = [str(p) for p in task.get_editor_property("imported_object_paths")]
        lock = bool(clip.get("force_root_lock", True))
        sequences = []
        for path in imported:
            asset = u.load_asset(path)
            if isinstance(asset, u.AnimSequence):
                asset.set_editor_property("force_root_lock", lock)
                aid = asset.get_editor_property("asset_import_data")
                sequences.append({"path": path, "force_root_lock": bool(asset.get_editor_property("force_root_lock")),
                                  "asset_import_data_class": aid.get_class().get_name() if aid else None})
            u.EditorAssetLibrary.save_asset(path.split(".")[0], only_if_is_dirty=False)
        report["clips"].append({"fbx": clip["fbx"], "folder": folder, "name": clip["name"],
                                "skeleton": clip["skeleton"], "existed_before": existed,
                                "import_uniform_scale_default": round(default_scale, 6),
                                "import_uniform_scale_used": round(used_scale, 6),
                                "imported_object_paths": imported, "sequences": sequences,
                                "force_root_lock_requested": lock,
                                "force_root_lock_ok": bool(sequences) and all(s["force_root_lock"] == lock
                                                                              for s in sequences),
                                "replaced_by_delete_and_import": existed,
                                "legacy_fbx_import": bool(sequences) and all(
                                    str(s["asset_import_data_class"] or "").startswith("Fbx") for s in sequences)})
finally:
    report["cvar_after"] = cvar_value()
    report["cvar_unchanged"] = report["cvar_after"] == report["cvar_before"]
    # keys of the T2.1 report format (review/p1_anim_report.py): the CVar is no longer switched during the import
    report["cvar_during_import"] = report["cvar_before"]
    report["cvar_restored"] = report["cvar_unchanged"]
    with open(args["out"], "w", encoding="utf-8", newline="\n") as handle:
        handle.write(json.dumps(report, indent=1, sort_keys=True) + "\n")
u.log("TRIPO_UE_PY_OK import_clips")
