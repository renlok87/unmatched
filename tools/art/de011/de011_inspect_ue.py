"""UE editor task (UnrealEditor-Cmd -ExecutePythonScript), run by tools/art/de011/de011.py inspect.

ARGS (env DE010_ARGS, the runner of tools/art/de010/de010.py): {"out": <report.json>, "materials": [<MI path>, ...],
"meshes": [<mesh path>, ...]}. For every figure MI (body and pedestal, P1 and P2): the parent chain down to the
master, the overridden scalar / vector / texture / static switch parameters, the blend mode of the master. For every
mesh: the bounds. Nothing is saved. A dissolve MID copies the MI parameters (scalars, vectors, textures) onto the
masked dissolve master; static switches are not copied, so they must be the master defaults.
"""
import json
import os
import traceback

import unreal as u

ARGS = json.load(open(os.environ["DE010_ARGS"], encoding="utf-8"))
MEL = u.MaterialEditingLibrary


def obj(path):
    return path if "." in path.rsplit("/", 1)[-1] else "%s.%s" % (path, path.rsplit("/", 1)[-1])


def load(path):
    a = u.load_asset(obj(path))
    if a is None:
        raise RuntimeError("asset not found: %s" % path)
    return a


report = {"materials": {}, "meshes": {}}
try:
    for path in ARGS["materials"]:
        mi = load(path)
        chain, cur = [], mi
        while isinstance(cur, u.MaterialInstance):
            chain.append(cur.get_path_name().split(".")[0])
            cur = cur.get_editor_property("parent")
        master = cur
        info = {"chain": chain, "master": master.get_path_name().split(".")[0] if master else None,
                "blend_mode": str(master.get_editor_property("blend_mode")) if master else None,
                "switches": {}, "scalars": {}, "vectors": {}, "textures": {}}
        if master:
            for name in MEL.get_static_switch_parameter_names(master):
                info["switches"][str(name)] = {
                    "mi": bool(MEL.get_material_instance_static_switch_parameter_value(mi, name)),
                    "master": bool(MEL.get_material_default_static_switch_parameter_value(master, name))}
        for p in mi.get_editor_property("scalar_parameter_values"):
            info["scalars"][str(p.get_editor_property("parameter_info").get_editor_property("name"))] = round(
                float(p.get_editor_property("parameter_value")), 6)
        for p in mi.get_editor_property("vector_parameter_values"):
            c = p.get_editor_property("parameter_value")
            info["vectors"][str(p.get_editor_property("parameter_info").get_editor_property("name"))] = [
                round(c.r, 6), round(c.g, 6), round(c.b, 6), round(c.a, 6)]
        for p in mi.get_editor_property("texture_parameter_values"):
            t = p.get_editor_property("parameter_value")
            info["textures"][str(p.get_editor_property("parameter_info").get_editor_property("name"))] = (
                t.get_path_name().split(".")[0] if t else None)
        report["materials"][path] = info
    for path in ARGS["meshes"]:
        m = load(path)
        b = m.get_bounds()
        report["meshes"][path] = {"origin": [round(b.origin.x, 3), round(b.origin.y, 3), round(b.origin.z, 3)],
                                  "extent": [round(b.box_extent.x, 3), round(b.box_extent.y, 3),
                                             round(b.box_extent.z, 3)]}
    u.log("DE011_INSPECT_COMPLETE")
except Exception:  # noqa: BLE001 - reported to the host
    report["error"] = traceback.format_exc()
    u.log_error("DE011_INSPECT_FAILED\n" + report["error"])
with open(ARGS["out"], "w", encoding="utf-8", newline="\n") as handle:
    handle.write(json.dumps(report, indent=1, sort_keys=True) + "\n")
u.SystemLibrary.quit_editor()
