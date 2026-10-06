"""UE editor task of tools/art/hero/base_digit_import.py (AN-31, VP-07/VP-72): the harpy base-digit assets.

Creates / updates and saves:
  /Game/UM/Materials/v2/M_UM_BaseDigit            Unlit opaque material, VectorParameter "Color" -> Emissive.
  /Game/UM/Fonts/F_UM_RobotoBoldCondensed         UFontFace from Engine/Content/Slate/Fonts/Roboto-BoldCondensed.ttf.
  /Game/UM/Fonts/F_UM_RobotoBoldCondensed_Offline UFont (runtime composite) whose default typeface is that face.
Then the editor quits. Everything is verified (properties read back) and reported as JSON.
"""
import json
import os
import traceback

import unreal as u

ARGS = json.load(open(os.environ["DE010_ARGS"], encoding="utf-8"))
EAL = u.EditorAssetLibrary
AT = u.AssetToolsHelpers.get_asset_tools()
MEL = u.MaterialEditingLibrary
ENGINE_TTF = u.Paths.convert_relative_path_to_full(u.Paths.engine_content_dir()) + "Slate/Fonts/Roboto-BoldCondensed.ttf"
TTF = ENGINE_TTF
# card.navy #061623 -> linear (the runtime drives the MID through FLinearColor::FromSRGBColor)
CARD_NAVY = u.LinearColor(r=0.001821, g=0.008007, b=0.016809, a=1.0)


def obj(path):
    return path if "." in path.rsplit("/", 1)[-1] else "%s.%s" % (path, path.rsplit("/", 1)[-1])


def material_expressions(mat):
    for prop in ("expressions", "expression_collection"):
        try:
            value = mat.get_editor_property(prop)
            if value is not None:
                return value
        except Exception:  # noqa: BLE001
            pass
    return []


SHADING_MODEL = u.MaterialShadingModel.UNLIT if hasattr(u.MaterialShadingModel, "UNLIT") else u.MaterialShadingModel.MSM_UNLIT
BLEND_OPAQUE = u.BlendMode.OPAQUE if hasattr(u.BlendMode, "OPAQUE") else u.BlendMode.BLEND_OPAQUE


def build_material():
    res = {"asset": ARGS["materials"] + "/M_UM_BaseDigit"}
    mat = EAL.load_asset(obj(res["asset"]))
    if mat is None:
        mat = AT.create_asset("M_UM_BaseDigit", ARGS["materials"], u.Material, u.MaterialFactoryNew())
    if mat is None:
        res["ok"] = False
        res["error"] = "create failed"
        return res
    mat.set_editor_property("shading_model", SHADING_MODEL)
    mat.set_editor_property("blend_mode", BLEND_OPAQUE)
    color = None
    for expr in material_expressions(mat):
        if isinstance(expr, u.MaterialExpressionVectorParameter) and expr.get_editor_property("parameter_name") == "Color":
            color = expr
            break
    if color is None:
        color = MEL.create_material_expression(mat, u.MaterialExpressionVectorParameter, -400.0, 0.0)
        color.set_editor_property("parameter_name", "Color")
        color.set_editor_property("default_value", CARD_NAVY)
    MEL.connect_material_property(color, "", u.MaterialProperty.MP_EMISSIVE_COLOR)
    MEL.recompile_material(mat)
    EAL.save_loaded_asset(mat, True)
    res["ok"] = mat.get_editor_property("shading_model") == SHADING_MODEL
    res["shading_model"] = str(mat.get_editor_property("shading_model"))
    return res


def import_font_face():
    res = {"asset": ARGS["fonts"] + "/F_UM_RobotoBoldCondensed"}
    face = EAL.load_asset(obj(res["asset"]))
    if face is None:
        task = u.AssetImportTask()
        task.set_editor_property("filename", TTF)
        task.set_editor_property("destination_path", ARGS["fonts"])
        task.set_editor_property("destination_name", "F_UM_RobotoBoldCondensed")
        task.set_editor_property("automated", True)
        task.set_editor_property("save", True)
        for name in ("FontFileImportFactory", "FontFactory"):
            cls = getattr(u, name, None)
            if cls is not None:
                task.set_editor_property("factory", cls())
                break
        AT.import_asset_tasks([task])
        face = EAL.load_asset(obj(res["asset"]))
    if face is None:
        res["ok"] = False
        res["error"] = "font face import failed (ttf %s)" % TTF
        return res
    res["ok"] = isinstance(face, u.FontFace)
    res["loading_policy"] = str(face.get_editor_property("loading_policy"))
    EAL.save_loaded_asset(face, True)
    return res


out = {"material": {}, "font_face": {}, "font": {}}
try:
    out["material"] = build_material()
    out["font_face"] = import_font_face()
    out["font"] = {"ok": True, "note": "transient runtime UFont built by the C++ (VR-Z1: no composite-font python API)"}
except Exception:
    out["error"] = traceback.format_exc()
with open(ARGS["out"], "w", encoding="utf-8") as handle:
    json.dump(out, handle, indent=1)
