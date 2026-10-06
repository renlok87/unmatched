"""UE editor task of tools/art/hero/base_digit_import.py (AN-31, ВР-07/ВР-72, ВР-Z1R-03): the harpy base-digit assets.

Creates / updates and saves:
  /Game/UM/Fonts/F_UM_RobotoBoldCondensed_Offline  the OFFLINE (texture-page, distance-field) font of the digits 0-9,
      Roboto Bold Condensed from the engine's Slate fonts (GDI face "Roboto Cn" bold). UTrueTypeFontFactory renders
      it through GDI: the TTF is made visible to GDI with AddFontResourceExW(FR_PRIVATE) inside this editor process only
      (nothing is installed), and the factory options are filled by the C++ helper
      US08BaseDigitAuthoringLibrary::AuthorOfflineDigitFont (FFontImportOptionsData is not Python-visible).
  /Game/UM/Materials/v2/M_UM_BaseDigit      the disc: Unlit, opaque, emissive = EyeAdaptationInverse(VectorParameter
      "Color") - the game-layer rule (the token lands on screen whatever the exposure).
  /Game/UM/Materials/v2/M_UM_BaseDigitText  the digit: Unlit, masked (clip 0.5 on the distance field), emissive =
      EyeAdaptationInverse(VectorParameter "Color", default card.cream), opacity mask = FontSampleParameter "Font".A
      (the TextRender MID cache sets the font page).
Then the editor quits. Everything is verified (read back) and reported as JSON.
"""
import ctypes
import json
import os
import traceback

import unreal as u

ARGS = json.load(open(os.environ["DE010_ARGS"], encoding="utf-8"))
EAL = u.EditorAssetLibrary
AT = u.AssetToolsHelpers.get_asset_tools()
MEL = u.MaterialEditingLibrary
TTF = u.Paths.convert_relative_path_to_full(u.Paths.engine_content_dir()) + "Slate/Fonts/Roboto-BoldCondensed.ttf"
GDI_FACE = "Roboto Cn"  # nameID 1 of Roboto-BoldCondensed.ttf (the Bold style of the "Roboto Cn" family)
FONT_NAME = "F_UM_RobotoBoldCondensed_Offline"
# card tokens (02-visual-design §2) as linear colours; the runtime MIDs set the exact FLinearColor::FromSRGBColor
CARD_NAVY = u.LinearColor(r=0.001821, g=0.008023, b=0.016807, a=1.0)   # #061623
CARD_CREAM = u.LinearColor(r=0.947307, g=0.830770, b=0.701102, a=1.0)  # #F9EBDB
FR_PRIVATE = 0x10


def obj(path):
    return path if "." in path.rsplit("/", 1)[-1] else "%s.%s" % (path, path.rsplit("/", 1)[-1])


def enum(cls, *names):
    for n in names:
        if hasattr(cls, n):
            return getattr(cls, n)
    raise RuntimeError("%s has none of %s" % (cls, names))


UNLIT = enum(u.MaterialShadingModel, "UNLIT", "MSM_UNLIT")
OPAQUE = enum(u.BlendMode, "OPAQUE", "BLEND_OPAQUE")
MASKED = enum(u.BlendMode, "MASKED", "BLEND_MASKED")


def gdi_face_check():
    """Adds the TTF for this process only and asks GDI which face a bold 'Roboto Cn' resolves to."""
    gdi = ctypes.windll.gdi32
    user = ctypes.windll.user32
    vp = ctypes.c_void_p
    user.GetDC.restype = vp
    user.GetDC.argtypes = [vp]
    user.ReleaseDC.argtypes = [vp, vp]
    gdi.CreateFontW.restype = vp
    gdi.SelectObject.restype = vp
    gdi.SelectObject.argtypes = [vp, vp]
    gdi.DeleteObject.argtypes = [vp]
    gdi.GetTextFaceW.argtypes = [vp, ctypes.c_int, ctypes.c_wchar_p]
    added = gdi.AddFontResourceExW(ctypes.c_wchar_p(TTF), FR_PRIVATE, None)
    hdc = user.GetDC(None)
    font = gdi.CreateFontW(-64, 0, 0, 0, 700, 0, 0, 0, 1, 0, 0, 4, 0, ctypes.c_wchar_p(GDI_FACE))
    old = gdi.SelectObject(hdc, font)
    buf = ctypes.create_unicode_buffer(64)
    gdi.GetTextFaceW(hdc, 64, buf)
    gdi.SelectObject(hdc, old)
    gdi.DeleteObject(font)
    user.ReleaseDC(None, hdc)
    return {"ttf": TTF, "added": int(added), "face": buf.value, "ok": added > 0 and buf.value == GDI_FACE}


def new_material(path, name):
    mat = EAL.load_asset(obj(path))
    created = False
    if mat is None:
        mat = AT.create_asset(name, path.rsplit("/", 1)[0], u.Material, u.MaterialFactoryNew())
        created = True
    if mat is None:
        raise RuntimeError("could not create %s" % path)
    MEL.delete_all_material_expressions(mat)
    return mat, created


def expr(mat, cls, x, y):
    node = MEL.create_material_expression(mat, cls, x, y)
    if node is None:
        raise RuntimeError("could not create %s" % cls)
    return node


def connect(src, out, dst, inp):
    if not MEL.connect_material_expressions(src, out, dst, inp):
        raise RuntimeError("could not connect %s.%s -> %s.%s" % (src.get_name(), out, dst.get_name(), inp))


def color_eai(mat, default, y):
    """VectorParameter Color -> EyeAdaptationInverse (alpha 1) -> the emissive."""
    color = expr(mat, u.MaterialExpressionVectorParameter, -600.0, y)
    color.set_editor_property("parameter_name", "Color")
    color.set_editor_property("default_value", default)
    one = expr(mat, u.MaterialExpressionConstant, -600.0, y + 200.0)
    one.set_editor_property("r", 1.0)
    eai = expr(mat, u.MaterialExpressionEyeAdaptationInverse, -300.0, y)
    connect(color, "", eai, "LightValueInput")
    connect(one, "", eai, "AlphaInput")
    MEL.connect_material_property(eai, "", u.MaterialProperty.MP_EMISSIVE_COLOR)


def finish(mat, res):
    MEL.recompile_material(mat)
    EAL.save_loaded_asset(mat, False)
    res["shading_model"] = str(mat.get_editor_property("shading_model"))
    res["blend_mode"] = str(mat.get_editor_property("blend_mode"))
    res["vector"] = sorted(str(n) for n in MEL.get_vector_parameter_names(mat))
    res["expressions"] = int(MEL.get_num_material_expressions(mat))
    return res


def build_disc():
    path = ARGS["materials"] + "/M_UM_BaseDigit"
    mat, created = new_material(path, "M_UM_BaseDigit")
    mat.set_editor_property("shading_model", UNLIT)
    mat.set_editor_property("blend_mode", OPAQUE)
    color_eai(mat, CARD_NAVY, 0.0)
    res = finish(mat, {"asset": path, "created": created})
    res["ok"] = mat.get_editor_property("shading_model") == UNLIT and "Color" in res["vector"]
    return res


def build_text(font):
    path = ARGS["materials"] + "/M_UM_BaseDigitText"
    mat, created = new_material(path, "M_UM_BaseDigitText")
    mat.set_editor_property("shading_model", UNLIT)
    mat.set_editor_property("blend_mode", MASKED)
    mat.set_editor_property("opacity_mask_clip_value", 0.5)
    color_eai(mat, CARD_CREAM, 0.0)
    sample = expr(mat, u.MaterialExpressionFontSampleParameter, -600.0, 400.0)
    sample.set_editor_property("parameter_name", "Font")
    sample.set_editor_property("font", font)
    sample.set_editor_property("font_texture_page", 0)
    MEL.connect_material_property(sample, "A", u.MaterialProperty.MP_OPACITY_MASK)
    res = finish(mat, {"asset": path, "created": created})
    res["ok"] = (mat.get_editor_property("shading_model") == UNLIT and mat.get_editor_property("blend_mode") == MASKED
                 and "Color" in res["vector"])
    return res


out = {"gdi": {}, "font": {}, "material": {}, "text_material": {}}
try:
    out["gdi"] = gdi_face_check()
    if not out["gdi"]["ok"]:
        raise RuntimeError("GDI does not resolve the face %r (got %r) - no font import" % (GDI_FACE, out["gdi"]["face"]))
    report = u.S08BaseDigitAuthoringLibrary.author_offline_digit_font(
        ARGS["fonts"], FONT_NAME, GDI_FACE, float(ARGS.get("height", 32)), True, True, "0123456789", True)
    out["font"] = json.loads(report)
    font = EAL.load_asset(obj(ARGS["fonts"] + "/" + FONT_NAME))
    out["font"]["ok"] = (font is not None and out["font"].get("cacheType") == "offline" and out["font"].get("pages", 0) > 0
                         and len(out["font"].get("cells", [])) == 10 and bool(out["font"].get("saved")))
    out["material"] = build_disc()
    out["text_material"] = build_text(font)
    ctypes.windll.gdi32.RemoveFontResourceExW(ctypes.c_wchar_p(TTF), FR_PRIVATE, None)
except Exception:
    out["error"] = traceback.format_exc()
with open(ARGS["out"], "w", encoding="utf-8") as handle:
    json.dump(out, handle, indent=1)
