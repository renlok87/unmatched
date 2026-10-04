"""UE editor task (UnrealEditor-Cmd -ExecutePythonScript, -RenderOffScreen), run by tools/art/de011/de011.py apply.

ARGS: JSON file named by the environment variable DE010_ARGS (the runner of tools/art/de010/de010.py):
  {"out": <report.json>, "master": {<ARGS of tools/art/material_library/ue/um_v2_master.py>, "out": <json>},
   "master_script": <path of um_v2_master.py>, "switch": "UseDissolve",
   "mics": [{"asset": <dissolve MIC>, "parent": <hero body MI>}]}
1. M_UM_Figure_v2 is rebuilt in place by the existing builder um_v2_master.py with the v2.3 graph of
   tools/art/material_library/ue_v2_master.py (static switch UseDissolve, default off); "instances" is empty, so no MI
   of a hero or of the test scene is touched.
2. One dissolve MIC per hero body MI (P1 and P2): parent = the hero MI (every texture, knob and static switch is
   inherited), UseDissolve = true, blend mode override Masked. Created or updated in place, saved.
Then the editor quits.
"""
import json
import os
import traceback

import unreal as u

ARGS = json.load(open(os.environ["DE010_ARGS"], encoding="utf-8"))
MEL = u.MaterialEditingLibrary
EAL = u.EditorAssetLibrary
AT = u.AssetToolsHelpers.get_asset_tools()
ROOT = "/Game/UM/Materials/v2/Dissolve/"


def obj(path):
    return path if "." in path.rsplit("/", 1)[-1] else "%s.%s" % (path, path.rsplit("/", 1)[-1])


def load(path):
    a = u.load_asset(obj(path))
    if a is None:
        raise RuntimeError("asset not found: %s" % path)
    return a


def stats(mat):
    st = MEL.get_statistics(mat)
    res = {}
    for k in ("num_vertex_shader_instructions", "num_pixel_shader_instructions", "num_samplers",
              "num_interpolator_scalars"):
        try:
            res[k] = int(st.get_editor_property(k))
        except Exception as exc:  # noqa: BLE001
            res[k] = "ERR %s" % exc
    return res


def switches(mi, master):
    return {str(n): bool(MEL.get_material_instance_static_switch_parameter_value(mi, n))
            for n in MEL.get_static_switch_parameter_names(master)}


report = {}
try:
    m = dict(ARGS["master"])
    code = open(ARGS["master_script"], encoding="utf-8").read()
    exec(compile(code, ARGS["master_script"], "exec"), {"__name__": "__ue_task__", "ARGS": m, "unreal": u})
    report["master"] = json.load(open(m["out"], encoding="utf-8"))
    master = load(m["master"])
    report["master"]["blend_mode"] = str(master.get_editor_property("blend_mode"))
    report["mics"] = {}
    for spec in ARGS["mics"]:
        path = spec["asset"]
        if not path.startswith(ROOT):
            raise RuntimeError("refusing to write outside %s: %s" % (ROOT, path))
        parent = load(spec["parent"])
        created = False
        if EAL.does_asset_exist(path):
            mic = load(path)
            if not isinstance(mic, u.MaterialInstanceConstant):
                raise RuntimeError("%s exists and is a %s" % (path, mic.get_class().get_name()))
        else:
            folder, name = path.rsplit("/", 1)
            mic = AT.create_asset(name, folder, u.MaterialInstanceConstant, u.MaterialInstanceConstantFactoryNew())
            created = True
        mic.modify()
        MEL.clear_all_material_instance_parameters(mic)
        MEL.set_material_instance_parent(mic, parent)
        MEL.set_material_instance_static_switch_parameter_value(mic, ARGS["switch"], True)
        ov = mic.get_editor_property("base_property_overrides")
        ov.set_editor_property("override_blend_mode", True)
        ov.set_editor_property("blend_mode", u.BlendMode.BLEND_MASKED)
        mic.set_editor_property("base_property_overrides", ov)
        MEL.update_material_instance(mic)
        if not EAL.save_loaded_asset(mic, False):
            raise RuntimeError("could not save %s" % path)
        ov = mic.get_editor_property("base_property_overrides")
        report["mics"][path] = {
            "created": created, "parent": mic.get_editor_property("parent").get_path_name().split(".")[0],
            "blend_override": bool(ov.get_editor_property("override_blend_mode")),
            "blend_mode": str(ov.get_editor_property("blend_mode")),
            "switches": switches(mic, master), "parent_switches": switches(parent, master),
            "statistics": stats(mic), "parent_statistics": stats(parent)}
    u.log("DE011_APPLY_COMPLETE")
except Exception:  # noqa: BLE001 - reported to the host
    report["error"] = traceback.format_exc()
    u.log_error("DE011_APPLY_FAILED\n" + report["error"])
with open(ARGS["out"], "w", encoding="utf-8", newline="\n") as handle:
    handle.write(json.dumps(report, indent=1, sort_keys=True) + "\n")
u.SystemLibrary.quit_editor()
