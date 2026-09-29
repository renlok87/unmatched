"""UE editor Python task (LIVE editor, run by tools/art/material_library/ue_v2.py through review/ue_live.run_task).

Imports the M_UM_Figure v2 inputs written by build_ue_inputs.py into /Game/UM/Materials/v2/Textures and sets the
texture settings of README section 4/5/7 (ARGS["textures"]: [{"file", "asset", "settings"}]). Only the listed
assets are written and saved; nothing outside /Game/UM/Materials/v2 is touched. ARGS["delete_dirs"] (only paths under
/Game/UM/Materials/v2/) are removed first (probe leftovers).

Result: per asset its class, size, the settings read back, and the package file.
"""
import json

import unreal as u

args = ARGS  # noqa: F821 - injected by ue_py/_run.py
ROOT = "/Game/UM/Materials/v2"
EAL = u.EditorAssetLibrary

ENUMS = {
    "compression_settings": u.TextureCompressionSettings,
    "mip_gen_settings": u.TextureMipGenSettings,
    "filter": u.TextureFilter,
    "lod_group": u.TextureGroup,
    "address_x": u.TextureAddress,
    "address_y": u.TextureAddress,
    "address_z": u.TextureAddress,
}


def to_value(name, value):
    if name in ENUMS:
        return getattr(ENUMS[name], value)
    return value


out = {"assets": {}, "deleted": []}
for d in args.get("delete_dirs", []):
    if not d.startswith(ROOT + "/"):
        raise RuntimeError("refusing to delete outside %s: %s" % (ROOT, d))
    if EAL.does_directory_exist(d):
        EAL.delete_directory(d)
        out["deleted"].append(d)

for spec in args["textures"]:
    asset_path = spec["asset"]
    if not asset_path.startswith(ROOT + "/"):
        raise RuntimeError("asset outside %s: %s" % (ROOT, asset_path))
    folder, name = asset_path.rsplit("/", 1)
    task = u.AssetImportTask()
    task.set_editor_property("filename", spec["file"])
    task.set_editor_property("destination_path", folder)
    task.set_editor_property("destination_name", name)
    task.set_editor_property("automated", True)
    task.set_editor_property("replace_existing", True)
    task.set_editor_property("save", False)
    u.AssetToolsHelpers.get_asset_tools().import_asset_tasks([task])
    paths = list(task.get_editor_property("imported_object_paths"))
    if len(paths) != 1:
        raise RuntimeError("import of %s gave %r" % (spec["file"], paths))
    tex = u.load_asset(paths[0])
    if tex.get_class().get_name() != spec["class"]:
        raise RuntimeError("%s imported as %s, expected %s" % (spec["file"], tex.get_class().get_name(), spec["class"]))
    tex.modify()
    for key, value in spec["settings"].items():
        tex.set_editor_property(key, to_value(key, value))
    if hasattr(tex, "post_edit_change"):
        tex.post_edit_change()
    EAL.save_loaded_asset(tex, False)
    info = {"class": tex.get_class().get_name(), "object": paths[0]}
    for key in spec["settings"]:
        info[key] = str(tex.get_editor_property(key)).split(".")[-1].rstrip(">").split(":")[0]
    if isinstance(tex, u.Texture2D):
        info["size"] = [tex.blueprint_get_size_x(), tex.blueprint_get_size_y()]
    out["assets"][asset_path] = info

with open(args["out"], "w", encoding="utf-8", newline="\n") as handle:
    handle.write(json.dumps(out, indent=1, sort_keys=True) + "\n")
