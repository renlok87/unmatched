"""UE editor task of tools/art/fx/fx_import.py (FX-02): the print material, its overlay twin and the MIs.

ARGS (DE010_ARGS, run by tools/art/de010/de010.run_editor):
  {"out": <report.json>, "masters": [{master, settings, nodes, links, attrs, instances, signature}],
   "texture": {"png": <star strip>, "asset": "/Game/S08/FX/Textures/T_FX_HitStar", "subUV": [8, 1]},
   "mis": [{asset, parent, scalars, vectors, textures, switches}]}

1. T_FX_HitStar: the 8-frame strip imported as a mask texture (BC7, sRGB off, no mips, never stream).
2. Both masters built / rebuilt in place (the graph emptied expression by expression, as um_v2_master.py does),
   compiled, saved; M_FX_Print_Overlay additionally sets disable_depth_test (ВР-Z2-02).
3. Every MI created / updated with its token colours, the SdfShape / UseSdf of its plan and the star texture.

Writes only under /Game/S08/FX/. Report: per master the compile errors, the parameters and the statistics, per
MI its created flag.
"""
import hashlib
import json
import os
import traceback

import unreal as u

ARGS = json.load(open(os.environ["DE010_ARGS"], encoding="utf-8"))
MEL = u.MaterialEditingLibrary
EAL = u.EditorAssetLibrary
AT = u.AssetToolsHelpers.get_asset_tools()
ROOT = "/Game/S08/FX/"

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


report = {"masters": [], "mis": {}}
try:
    # ---- 1. the placeholder star strip (ВР-Z2-03): mask texture, no sRGB, no mips, never stream
    tspec = ARGS["texture"]
    task = u.AssetImportTask()
    task.filename = tspec["png"]
    task.destination_path = tspec["asset"].rsplit("/", 1)[0]
    task.destination_name = tspec["asset"].rsplit("/", 1)[-1]
    task.automated = True
    task.replace_existing = True
    task.save = False
    AT.import_asset_tasks([task])
    tex = load(tspec["asset"])
    if not isinstance(tex, u.Texture2D):
        raise RuntimeError("star strip did not import as Texture2D")
    tex.set_editor_property("compression_settings", u.TextureCompressionSettings.TC_DEFAULT)  # BC7, 4 channels
    tex.set_editor_property("srgb", False)
    tex.set_editor_property("mip_gen_settings", u.TextureMipGenSettings.TMGS_NO_MIPMAPS)
    tex.set_editor_property("never_stream", True)
    EAL.save_loaded_asset(tex, False)
    report["texture"] = {"ok": True, "asset": tspec["asset"],
                         "size": [tex.blueprint_get_size_x(), tex.blueprint_get_size_y()],
                         "subUV": tspec["subUV"],
                         "sourceSha256": hashlib.sha256(open(tspec["png"], "rb").read()).hexdigest()}

    # ---- 2. the masters (the builder of um_v2_master.py, ROOT-guarded here; + disable_depth_test)
    for spec in ARGS["masters"]:
        m, created = get_or_create(spec["master"], u.Material, u.MaterialFactoryNew())
        m.modify()
        if not created:
            for _ in range(10):
                left = list(MEL.get_material_expressions(m))
                if not left:
                    break
                for e in left:
                    MEL.delete_material_expression(m, e)
            if MEL.get_num_material_expressions(m):
                raise RuntimeError("could not empty the graph: %d expressions left" % MEL.get_num_material_expressions(m))
        s = spec["settings"]
        m.set_editor_property("blend_mode", getattr(u.BlendMode, s["blend_mode"]))
        m.set_editor_property("shading_model", getattr(u.MaterialShadingModel, s["shading_model"]))
        m.set_editor_property("two_sided", bool(s["two_sided"]))
        m.set_editor_property("use_material_attributes", bool(s["use_material_attributes"]))
        m.set_editor_property("tangent_space_normal", bool(s["tangent_space_normal"]))
        m.set_editor_property("disable_depth_test", bool(s.get("disable_depth_test", False)))
        if s.get("translucency_pass"):
            m.set_editor_property("translucency_pass", getattr(u.MaterialTranslucencyPass, s["translucency_pass"]))
        usages = {}
        for usage in s["usages"]:
            usages[usage] = bool(MEL.set_material_usage(m, getattr(u.MaterialUsage, usage)))
        expr = {}
        for nid, n in spec["nodes"].items():
            e = MEL.create_material_expression(m, getattr(u, n["class"]), int(n["x"]), int(n["y"]))
            if e is None:
                raise RuntimeError("could not create %s (%s)" % (nid, n["class"]))
            for key, v in n["props"].items():
                e.set_editor_property(key, value_of(key, v))
            expr[nid] = e
        for src, o, dst, i in spec["links"]:
            ok = MEL.connect_material_expressions(expr[src], o, expr[dst], i)
            if not ok:
                raise RuntimeError("link %s.%r -> %s.%r failed" % (src, o, dst, i))
        for prop, (src, o) in spec["attrs"].items():
            if not MEL.connect_material_property(expr[src], o, getattr(u.MaterialProperty, prop)):
                raise RuntimeError("attribute %s <- %s.%r failed" % (prop, src, o))
        errors = MEL.recompile_material(m)
        EAL.save_loaded_asset(m, False)
        report["masters"].append({
            "master": spec["master"], "created": created, "usages": usages,
            "disable_depth_test": bool(m.get_editor_property("disable_depth_test")),
            "translucency_pass": str(m.get_editor_property("translucency_pass")),
            "compile_errors": [str(e) for e in (errors or [])], "statistics": stats(m),
            "parameters": {"scalar": sorted(str(x) for x in MEL.get_scalar_parameter_names(m)),
                           "vector": sorted(str(x) for x in MEL.get_vector_parameter_names(m)),
                           "texture": sorted(str(x) for x in MEL.get_texture_parameter_names(m)),
                           "static_switch": sorted(str(x) for x in MEL.get_static_switch_parameter_names(m))},
            "expressions": int(MEL.get_num_material_expressions(m))})

    # ---- 3. the MIs (the 7 of the card + the 4 placard MIs)
    for spec in ARGS["mis"]:
        mi, mi_created = get_or_create(spec["asset"], u.MaterialInstanceConstant,
                                       u.MaterialInstanceConstantFactoryNew())
        mi.modify()
        MEL.set_material_instance_parent(mi, load(spec["parent"]))
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
        # the MI's own static permutation (UseSdf on = the SDF branch): the master's statistics compile only the
        # default (flipbook) branch - the Z-2 review found an SDF compile error the master report could not show
        report["mis"][spec["asset"]] = {"created": mi_created, "tokens": spec.get("tokens", {}),
                                        "statistics": stats(mi)}
    report["ok"] = True
except Exception:  # noqa: BLE001
    report["ok"] = False
    report["error"] = traceback.format_exc()
with open(ARGS["out"], "w", encoding="utf-8", newline="\n") as handle:
    handle.write(json.dumps(report, indent=1, sort_keys=True) + "\n")
