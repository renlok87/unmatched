"""UE editor Python task (LIVE editor, run by tools/art/material_library/ue_v2.py `master`).

ARGS: master, settings, nodes {id: {class, props, x, y}}, links [[src, out, dst, in]], attrs {MP_*: [src, out]},
      instances [{asset, parent, scalars, vectors, textures, switches}], signature.
Creates M_UM_Figure_v2 (or rebuilds its graph in place: expressions deleted and re-added, so the asset identity and
the MIs that point at it survive), compiles it (MaterialEditingLibrary.recompile_material returns the compile errors
of the editor's shader platform), saves it, reads the statistics, creates/updates the MIs, saves them.
Writes only under /Game/UM/Materials/v2/.
"""
import json
import time

import unreal as u

args = ARGS  # noqa: F821 - injected by ue_py/_run.py
ROOT = "/Game/UM/Materials/v2/"
MEL = u.MaterialEditingLibrary
EAL = u.EditorAssetLibrary
AT = u.AssetToolsHelpers.get_asset_tools()

ENUM_PROPS = {"sampler_type": u.MaterialSamplerType, "shading_model": u.MaterialShadingModel,
              "output_type": u.CustomMaterialOutputType, "blend_mode": u.BlendMode}


def obj(path):
    return path if "." in path.rsplit("/", 1)[-1] else "%s.%s" % (path, path.rsplit("/", 1)[-1])


def load(path):
    a = u.load_asset(obj(path))
    if a is None:
        raise RuntimeError("asset not found: %s" % path)
    return a


def check_path(path):
    if not path.startswith(ROOT):
        raise RuntimeError("refusing to write outside %s: %s" % (ROOT, path))


def value_of(key, v):
    if key in ENUM_PROPS:
        return getattr(ENUM_PROPS[key], v)
    if key == "texture":
        return load(v)
    if key in ("default_value", "constant") and isinstance(v, dict):
        return u.LinearColor(v["r"], v["g"], v["b"], v["a"])
    if key == "inputs":
        res = []
        for name in v:
            ci = u.CustomInput()
            ci.set_editor_property("input_name", name)
            res.append(ci)
        return res
    if key == "additional_outputs":
        res = []
        for name, typ in v:
            co = u.CustomOutput()
            co.set_editor_property("output_name", name)
            co.set_editor_property("output_type", getattr(u.CustomMaterialOutputType, typ))
            res.append(co)
        return res
    return v


def get_or_create(path, cls, factory):
    check_path(path)
    if EAL.does_asset_exist(path):
        a = load(path)
        if not isinstance(a, cls):
            raise RuntimeError("%s exists and is a %s" % (path, a.get_class().get_name()))
        return a, False
    folder, name = path.rsplit("/", 1)
    return AT.create_asset(name, folder, cls, factory), True


out = {"master": args["master"]}
if EAL.does_directory_exist(ROOT + "_probe"):
    EAL.delete_directory(ROOT + "_probe")
    out["deleted_probe_dir"] = True
m, created = get_or_create(args["master"], u.Material, u.MaterialFactoryNew())
out["created"] = created
m.modify()
if not created:
    # delete_all_material_expressions left about a third of the nodes behind on a rebuild (measured 2026-09-29:
    # 100 expressions after rebuilding a 67-node graph); delete one by one until the graph is empty
    for _ in range(10):
        left = list(MEL.get_material_expressions(m))
        if not left:
            break
        for e in left:
            MEL.delete_material_expression(m, e)
    if MEL.get_num_material_expressions(m):
        raise RuntimeError("could not empty the graph: %d expressions left" % MEL.get_num_material_expressions(m))
s = args["settings"]
m.set_editor_property("blend_mode", getattr(u.BlendMode, s["blend_mode"]))
m.set_editor_property("shading_model", getattr(u.MaterialShadingModel, s["shading_model"]))
m.set_editor_property("two_sided", bool(s["two_sided"]))
m.set_editor_property("use_material_attributes", bool(s["use_material_attributes"]))
m.set_editor_property("tangent_space_normal", bool(s["tangent_space_normal"]))
out["usages"] = {}
for usage in s["usages"]:
    out["usages"][usage] = bool(MEL.set_material_usage(m, getattr(u.MaterialUsage, usage)))

expr = {}
for nid, n in args["nodes"].items():
    e = MEL.create_material_expression(m, getattr(u, n["class"]), int(n["x"]), int(n["y"]))
    if e is None:
        raise RuntimeError("could not create %s (%s)" % (nid, n["class"]))
    for key, v in n["props"].items():
        e.set_editor_property(key, value_of(key, v))
    expr[nid] = e
for src, o, dst, i in args["links"]:
    ok = MEL.connect_material_expressions(expr[src], o, expr[dst], i)
    if not ok:
        raise RuntimeError("link %s.%r -> %s.%r failed; outputs %s inputs %s" % (
            src, o, dst, i, [str(x) for x in MEL.get_material_expression_output_names(expr[src])],
            [str(x) for x in MEL.get_material_expression_input_names(expr[dst])]))
for prop, (src, o) in args["attrs"].items():
    if not MEL.connect_material_property(expr[src], o, getattr(u.MaterialProperty, prop)):
        raise RuntimeError("attribute %s <- %s.%r failed" % (prop, src, o))

t0 = time.time()
errors = MEL.recompile_material(m)
out["compile_seconds"] = round(time.time() - t0, 2)
out["compile_errors"] = [str(e) for e in (errors or [])]
EAL.save_loaded_asset(m, False)


def stats(mat):
    st = MEL.get_statistics(mat)
    res = {}
    for k in ("num_vertex_shader_instructions", "num_pixel_shader_instructions", "num_samplers",
              "num_vertex_texture_samples", "num_pixel_texture_samples", "num_virtual_texture_samples",
              "num_uv_scalars", "num_interpolator_scalars"):
        try:
            res[k] = int(st.get_editor_property(k))
        except Exception as exc:  # noqa: BLE001
            res[k] = "ERR %s" % exc
    return res


out["statistics"] = stats(m)
out["parameters"] = {"scalar": sorted(str(x) for x in MEL.get_scalar_parameter_names(m)),
                     "vector": sorted(str(x) for x in MEL.get_vector_parameter_names(m)),
                     "texture": sorted(str(x) for x in MEL.get_texture_parameter_names(m)),
                     "static_switch": sorted(str(x) for x in MEL.get_static_switch_parameter_names(m))}
out["expressions"] = int(MEL.get_num_material_expressions(m))
out["used_textures"] = sorted(t.get_path_name().split(".")[0] for t in MEL.get_used_textures(m))

out["instances"] = {}
for spec in args["instances"]:
    mi, mi_created = get_or_create(spec["asset"], u.MaterialInstanceConstant, u.MaterialInstanceConstantFactoryNew())
    mi.modify()
    MEL.clear_all_material_instance_parameters(mi)
    MEL.set_material_instance_parent(mi, load(spec["parent"]))
    copied = {}
    if spec.get("copy_from"):
        # regression MI: every parameter value of a v1 hero MI (textures, scalars, vectors) on the v2 master
        src = load(spec["copy_from"])
        v1 = src.get_editor_property("parent")
        for name in MEL.get_texture_parameter_names(v1):
            v = MEL.get_material_instance_texture_parameter_value(src, name)
            if v is not None:
                MEL.set_material_instance_texture_parameter_value(mi, name, v)
                copied[str(name)] = v.get_path_name().split(".")[0]
        for name in MEL.get_scalar_parameter_names(v1):
            val = MEL.get_material_instance_scalar_parameter_value(src, name)
            MEL.set_material_instance_scalar_parameter_value(mi, name, val)
            copied[str(name)] = round(float(val), 6)
        for name in MEL.get_vector_parameter_names(v1):
            c = MEL.get_material_instance_vector_parameter_value(src, name)
            MEL.set_material_instance_vector_parameter_value(mi, name, c)
            copied[str(name)] = [round(c.r, 6), round(c.g, 6), round(c.b, 6), round(c.a, 6)]
    for k, v in spec["scalars"].items():
        MEL.set_material_instance_scalar_parameter_value(mi, k, float(v))
    for k, v in spec["vectors"].items():
        MEL.set_material_instance_vector_parameter_value(mi, k, u.LinearColor(*[float(x) for x in v]))
    for k, v in spec["textures"].items():
        MEL.set_material_instance_texture_parameter_value(mi, k, load(v))
    for k, v in spec["switches"].items():
        MEL.set_material_instance_static_switch_parameter_value(mi, k, bool(v))
    MEL.update_material_instance(mi)
    EAL.save_loaded_asset(mi, False)
    info = {"created": mi_created}
    if copied:
        info["copied_from"] = spec["copy_from"]
        info["copied"] = copied
    if spec["switches"]:
        info["statistics"] = stats(mi)
    out["instances"][spec["asset"]] = info

with open(args["out"], "w", encoding="utf-8", newline="\n") as handle:
    handle.write(json.dumps(out, indent=1, sort_keys=True) + "\n")
