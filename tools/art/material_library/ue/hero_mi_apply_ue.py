"""UE editor Python task (LIVE editor via review/ue_live.py run_task): apply-mi of ue_hero_lookdev.py (RC-10).

ARGS: {"out", "op": "read" | "apply", ...}
  read   {"instances": {mi package: {"scalars": [names], "vectors": [names], "textures": [names], "switches": [names]}},
          "textures": [texture package, ...]}
         read only: per MI its parent, the overridden scalar / vector / texture values and the EFFECTIVE value of each
         named parameter (own override or inherited; MaterialEditingLibrary); per texture its settings, the source files
         of its import data and the sha stamp (package metadata UM_SourceSha256); the dirty packages.
  apply  {"changes": {mi package: {"scalars": {name: value}, "vectors": {name: [r, g, b, a]}, "textures": {name: package},
                                    "switches": {name: bool}}},
          "lut": null | {"asset", "source_file", "sha256", "settings": {python property: value (enums by NAME)}}}
         sets the listed MI values (update_material_instance per MI), re-imports the LUT texture over itself
         (AssetImportTask replace_existing: the MIs keep their reference), sets its settings, stamps its sha and saves
         ONLY the changed packages. Nothing is created, deleted or renamed; no level is touched.
Only packages under /Game/PipelineCandidates/ are written.
"""
import json

import unreal as u

args = ARGS  # noqa: F821 - injected by ue_py/_run.py
op = args["op"]
EAL = u.EditorAssetLibrary
ELS = u.EditorLoadingAndSavingUtils
MEL = u.MaterialEditingLibrary
TAG = "UM_SourceSha256"
ENUMS = {"compression_settings": u.TextureCompressionSettings, "mip_gen_settings": u.TextureMipGenSettings,
         "filter": u.TextureFilter, "lod_group": u.TextureGroup}


def obj(path):
    return path if "." in path.rsplit("/", 1)[-1] else "%s.%s" % (path, path.rsplit("/", 1)[-1])


def load(path):
    asset = u.load_asset(obj(path))
    if asset is None:
        raise RuntimeError("asset not found: %s" % path)
    return asset


def pkg(o):
    return o.get_path_name().split(".")[0] if o else None


def enum_name(value):
    s = str(value)
    if "." in s:
        s = s.split(".")[-1]
    return s.split(":")[0].strip("<> ")


def enum_value(enum, name):
    """'TMGS_NoMipmaps' (profile, C++ spelling) -> TextureMipGenSettings.TMGS_NO_MIPMAPS (Python spelling)."""
    if hasattr(enum, name):
        return getattr(enum, name)
    key = name.replace("_", "").upper()
    for attr in dir(enum):
        if attr.replace("_", "").upper() == key:
            return getattr(enum, attr)
    raise RuntimeError("%s has no value %s" % (enum, name))


def dirty():
    return sorted(str(p.get_name()) for p in ELS.get_dirty_content_packages())


def texture_info(path):
    tex = load(path)
    info = {"asset": path, "class": tex.get_class().get_name(), "size": [tex.blueprint_get_size_x(), tex.blueprint_get_size_y()],
            "srgb": bool(tex.get_editor_property("srgb")), "never_stream": bool(tex.get_editor_property("never_stream"))}
    for k in ("compression_settings", "mip_gen_settings", "filter", "lod_group"):
        info[k] = enum_name(tex.get_editor_property(k))
    aid = tex.get_editor_property("asset_import_data")
    info["source_files"] = [str(x).replace("\\", "/") for x in aid.extract_filenames()] if aid else []
    info["sha_stamp"] = str(EAL.get_metadata_tag(tex, TAG) or "") or None
    return info


def mi_info(path, names):
    mi = load(path)
    rec = {"asset": path, "parent": pkg(mi.get_editor_property("parent")), "overrides": {"scalars": {}, "vectors": {},
                                                                                         "textures": {}},
           "scalars": {}, "vectors": {}, "textures": {}, "switches": {}}
    for p in mi.get_editor_property("scalar_parameter_values"):
        rec["overrides"]["scalars"][str(p.get_editor_property("parameter_info").get_editor_property("name"))] = round(
            float(p.get_editor_property("parameter_value")), 6)
    for p in mi.get_editor_property("vector_parameter_values"):
        c = p.get_editor_property("parameter_value")
        rec["overrides"]["vectors"][str(p.get_editor_property("parameter_info").get_editor_property("name"))] = [
            round(c.r, 6), round(c.g, 6), round(c.b, 6), round(c.a, 6)]
    for p in mi.get_editor_property("texture_parameter_values"):
        rec["overrides"]["textures"][str(p.get_editor_property("parameter_info").get_editor_property("name"))] = pkg(
            p.get_editor_property("parameter_value"))
    for n in names.get("scalars") or []:
        rec["scalars"][n] = round(float(MEL.get_material_instance_scalar_parameter_value(mi, n)), 6)
    for n in names.get("vectors") or []:
        c = MEL.get_material_instance_vector_parameter_value(mi, n)
        rec["vectors"][n] = [round(c.r, 6), round(c.g, 6), round(c.b, 6), round(c.a, 6)]
    for n in names.get("textures") or []:
        rec["textures"][n] = pkg(MEL.get_material_instance_texture_parameter_value(mi, n))
    for n in names.get("switches") or []:
        rec["switches"][n] = bool(MEL.get_material_instance_static_switch_parameter_value(mi, n))
    return rec


out = {"op": op, "dirty_before": dirty()}
if op == "read":
    out["instances"] = {p: mi_info(p, n) for p, n in sorted((args.get("instances") or {}).items())}
    out["textures"] = {p: texture_info(p) for p in args.get("textures") or []}
elif op == "apply":
    changed, report = [], {}
    for path, ch in sorted((args.get("changes") or {}).items()):
        if not path.startswith("/Game/PipelineCandidates/"):
            raise RuntimeError("refusing to change %s (outside /Game/PipelineCandidates/)" % path)
        mi = load(path)
        res = {}
        for n, v in sorted((ch.get("scalars") or {}).items()):
            res["scalar " + n] = bool(MEL.set_material_instance_scalar_parameter_value(mi, n, float(v)))
        for n, v in sorted((ch.get("vectors") or {}).items()):
            res["vector " + n] = bool(MEL.set_material_instance_vector_parameter_value(
                mi, n, u.LinearColor(float(v[0]), float(v[1]), float(v[2]), float(v[3]))))
        for n, v in sorted((ch.get("textures") or {}).items()):
            res["texture " + n] = bool(MEL.set_material_instance_texture_parameter_value(mi, n, load(v)))
        for n, v in sorted((ch.get("switches") or {}).items()):
            res["switch " + n] = bool(MEL.set_material_instance_static_switch_parameter_value(mi, n, bool(v)))
        MEL.update_material_instance(mi)
        report[path] = res
        changed.append(path)
    out["set"] = report
    lut = args.get("lut")
    if lut:
        path = lut["asset"]
        if not path.startswith("/Game/PipelineCandidates/"):
            raise RuntimeError("refusing to re-import %s (outside /Game/PipelineCandidates/)" % path)
        folder, name = path.rsplit("/", 1)
        before = texture_info(path)
        task = u.AssetImportTask()
        task.set_editor_property("filename", lut["source_file"])
        task.set_editor_property("destination_path", folder)
        task.set_editor_property("destination_name", name)
        task.set_editor_property("replace_existing", True)
        task.set_editor_property("replace_existing_settings", False)
        task.set_editor_property("automated", True)
        task.set_editor_property("save", False)
        u.AssetToolsHelpers.get_asset_tools().import_asset_tasks([task])
        tex = load(path)
        for k, v in sorted((lut.get("settings") or {}).items()):
            tex.set_editor_property(k, enum_value(ENUMS[k], v) if k in ENUMS else v)
        EAL.set_metadata_tag(tex, TAG, lut["sha256"])
        out["lut"] = {"asset": path, "source_file": lut["source_file"], "before": before,
                      "imported_objects": [str(x) for x in task.get_editor_property("imported_object_paths")]}
        changed.append(path)
    out["dirty_after_set"] = dirty()
    out["saved"] = {p: bool(EAL.save_asset(p, only_if_is_dirty=False)) for p in changed}
    if lut:
        out["lut"]["after"] = texture_info(lut["asset"])
else:
    raise RuntimeError("unknown op %s" % op)
out["dirty_after"] = dirty()
with open(args["out"], "w", encoding="utf-8", newline="\n") as handle:
    handle.write(json.dumps(out, indent=1, sort_keys=True, default=str) + "\n")
u.log("TRIPO_UE_PY_OK hero_mi_apply_ue %s" % op)
