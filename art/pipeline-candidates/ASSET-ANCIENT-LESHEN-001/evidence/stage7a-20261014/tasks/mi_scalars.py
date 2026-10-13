# UE task: read-back of MI scalar parameters (read only). ARGS = {"out", "mis": [paths], "names": [scalar names]}
import json
u = unreal  # noqa: F821
MEL = u.MaterialEditingLibrary
res = {}
for path in ARGS["mis"]:  # noqa: F821
    mi = u.load_asset(path)
    res[path] = {n: round(float(MEL.get_material_instance_scalar_parameter_value(mi, n)), 5) for n in ARGS["names"]}  # noqa: F821
with open(ARGS["out"], "w", encoding="utf-8") as h:  # noqa: F821
    json.dump(res, h, indent=1)
