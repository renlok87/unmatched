"""UE editor Python task (LIVE editor, ue_v2.py `stats`): read-only material statistics and usage flags.

ARGS: {"materials": [paths]} -> MaterialEditingLibrary.get_statistics (the editor's shader platform: PCD3D_SM6 in
this project), usage flags, shading model, and whether the package is dirty. Nothing is modified or saved.
"""
import json

import unreal as u

args = ARGS  # noqa: F821 - injected by ue_py/_run.py
MEL = u.MaterialEditingLibrary
out = {"materials": {}}
for path in args["materials"]:
    m = u.load_asset(path if "." in path.rsplit("/", 1)[-1] else "%s.%s" % (path, path.rsplit("/", 1)[-1]))
    st = MEL.get_statistics(m)
    d = {k: int(st.get_editor_property(k)) for k in (
        "num_vertex_shader_instructions", "num_pixel_shader_instructions", "num_samplers", "num_vertex_texture_samples",
        "num_pixel_texture_samples", "num_virtual_texture_samples", "num_uv_scalars", "num_interpolator_scalars")}
    base = m.get_base_material() if hasattr(m, "get_base_material") else m
    d["class"] = m.get_class().get_name()
    for k in ("used_with_skeletal_mesh", "used_with_instanced_static_meshes", "use_material_attributes",
              "shading_model", "blend_mode"):
        try:
            d[k] = str(base.get_editor_property(k))
        except Exception:  # noqa: BLE001
            pass
    d["dirty"] = bool(m.get_outermost().is_dirty()) if hasattr(m.get_outermost(), "is_dirty") else None
    out["materials"][path] = d
with open(args["out"], "w", encoding="utf-8", newline="\n") as handle:
    handle.write(json.dumps(out, indent=1, sort_keys=True) + "\n")
