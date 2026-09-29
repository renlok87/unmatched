"""W4-A render content (UnrealEditor-Cmd -run=pythonscript, ART WORKTREE only).

Creates, idempotently, the two assets the W4-A render policy needs under
/Game/S08/Render (cooked with /Game/S08 via DirectoriesToAlwaysCook):

  TC_S08_AmbientDome      long-lat TextureCube imported from the generated
                          radiance map (tools/art/render/make_ambient_dome_hdr.py);
                          source of the Movable SkyLight of every light profile.
  M_S08_GameLayerUnlit    game-layer master: Unlit, Opaque, Emissive =
                          EyeAdaptationInverse(Tint, Alpha 1), usage ISM + static
                          mesh. Same "Tint" vector parameter as M_S08_Solid, so a
                          MID only swaps its parent. The exposure of the light
                          profile (fixed EV100 1.3) is cancelled on the game layer:
                          zones, glyphs, rings and cell marks keep one brightness
                          under every profile and scalability level (memo §1 item 7).

Also records how M_S08_Solid (the pre-W4 game-layer base) is set up.
Writes a JSON report to W4A_REPORT (env) with class, settings and sha256 of
the saved .uasset files. Never touches /Game/ART004, /Game/ArtPreview or the
other /Game/S08 assets.

Run (from the art worktree root; the main-checkout project must never be used):
  UnrealEditor-Cmd.exe <art>/unreal/Unmatched/Unmatched.uproject -run=pythonscript
    -script=<art>/tools/art/render/w4a_render_content.py -unattended -nosplash -nullrhi
    -ini:Editor:[TextureImporter]:LoadHdrAsLongLatCubemap=1
    -ini:Engine:[ConsoleVariables]:Interchange.FeatureFlags.Import.HDR=False
  env W4A_HDR=<generated .hdr>, W4A_REPORT=<report .json>
"""
import hashlib
import json
import os

import unreal

FOLDER = "/Game/S08/Render"
CUBE = FOLDER + "/TC_S08_AmbientDome"
MAT = FOLDER + "/M_S08_GameLayerUnlit"
SOLID = "/Game/S08/M_S08_Solid"

report = {"schema": "unmatched.w4a-render-content/1", "steps": [], "errors": []}


def step(msg, **kw):
    kw["msg"] = msg
    report["steps"].append(kw)
    unreal.log("W4A " + msg + " " + json.dumps(kw, default=str))


def uasset_file(path):
    rel = path.replace("/Game/", "")
    return os.path.join(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_content_dir()), rel + ".uasset")


def sha(path):
    f = uasset_file(path)
    if not os.path.isfile(f):
        return None
    with open(f, "rb") as h:
        return hashlib.sha256(h.read()).hexdigest()


def inspect_solid():
    m = unreal.load_asset(SOLID)
    if not m:
        report["errors"].append("M_S08_Solid missing")
        return
    mel = unreal.MaterialEditingLibrary
    info = {
        "class": m.get_class().get_name(),
        "shading_model": str(m.get_editor_property("shading_model")),
        "blend_mode": str(m.get_editor_property("blend_mode")),
        "used_with_instanced_static_meshes": m.get_editor_property("used_with_instanced_static_meshes"),
        "vector_parameters": [str(n) for n in mel.get_vector_parameter_names(m)],
        "scalar_parameters": [str(n) for n in mel.get_scalar_parameter_names(m)],
        "emissive_connected": mel.get_material_property_input_node(m, unreal.MaterialProperty.MP_EMISSIVE_COLOR) is not None,
        "base_color_connected": mel.get_material_property_input_node(m, unreal.MaterialProperty.MP_BASE_COLOR) is not None,
    }
    report["solid"] = info
    step("inspected M_S08_Solid", **info)


def import_cube():
    hdr = os.environ.get("W4A_HDR")
    if not hdr or not os.path.isfile(hdr):
        report["errors"].append(f"W4A_HDR missing: {hdr}")
        return
    with open(hdr, "rb") as h:
        report["hdrSha256"] = hashlib.sha256(h.read()).hexdigest()
    task = unreal.AssetImportTask()
    task.set_editor_property("filename", hdr)
    task.set_editor_property("destination_path", FOLDER)
    task.set_editor_property("destination_name", "TC_S08_AmbientDome")
    task.set_editor_property("replace_existing", True)
    task.set_editor_property("automated", True)
    task.set_editor_property("save", False)
    unreal.AssetToolsHelpers.get_asset_tools().import_asset_tasks([task])
    tex = unreal.load_asset(CUBE)
    if not tex:
        report["errors"].append("cubemap import produced no asset")
        return
    cls = tex.get_class().get_name()
    if cls != "TextureCube":
        report["errors"].append(f"cubemap imported as {cls}, expected TextureCube")
        return
    tex.set_editor_property("srgb", False)
    tex.set_editor_property("compression_settings", unreal.TextureCompressionSettings.TC_HDR)
    unreal.EditorAssetLibrary.save_asset(CUBE, only_if_is_dirty=False)
    step("imported cubemap", cls=cls, size=[tex.blueprint_get_size_x(), tex.blueprint_get_size_y()]
         if hasattr(tex, "blueprint_get_size_x") else None)


def connect(mel, src, dst, names):
    for n in names:
        if mel.connect_material_expressions(src, "", dst, n):
            return n
    return None


def build_material():
    mel = unreal.MaterialEditingLibrary
    at = unreal.AssetToolsHelpers.get_asset_tools()
    if unreal.EditorAssetLibrary.does_asset_exist(MAT):
        mat = unreal.load_asset(MAT)
        mel.delete_all_material_expressions(mat)
        step("material exists: expressions cleared for an idempotent rebuild")
    else:
        mat = at.create_asset("M_S08_GameLayerUnlit", FOLDER, unreal.Material, unreal.MaterialFactoryNew())
    mat.set_editor_property("shading_model", unreal.MaterialShadingModel.MSM_UNLIT)
    mat.set_editor_property("blend_mode", unreal.BlendMode.BLEND_OPAQUE)
    mat.set_editor_property("two_sided", False)
    mat.set_editor_property("used_with_instanced_static_meshes", True)
    tint = mel.create_material_expression(mat, unreal.MaterialExpressionVectorParameter, -700, 0)
    tint.set_editor_property("parameter_name", "Tint")
    tint.set_editor_property("default_value", unreal.LinearColor(1.0, 1.0, 1.0, 1.0))
    inv = mel.create_material_expression(mat, unreal.MaterialExpressionEyeAdaptationInverse, -350, 0)
    one = mel.create_material_expression(mat, unreal.MaterialExpressionConstant, -700, 220)
    one.set_editor_property("r", 1.0)
    pin_light = connect(mel, tint, inv, ["LightValue", "Light Value", "LightValueInput"])
    pin_alpha = connect(mel, one, inv, ["Alpha", "AlphaInput"])
    emissive = mel.connect_material_property(inv, "", unreal.MaterialProperty.MP_EMISSIVE_COLOR)
    if not (pin_light and pin_alpha and emissive):
        report["errors"].append(f"material wiring failed light={pin_light} alpha={pin_alpha} emissive={emissive}")
    mel.recompile_material(mat)
    unreal.EditorAssetLibrary.save_asset(MAT, only_if_is_dirty=False)
    info = {"pinLight": pin_light, "pinAlpha": pin_alpha, "emissive": emissive,
            "shading_model": str(mat.get_editor_property("shading_model")),
            "blend_mode": str(mat.get_editor_property("blend_mode")),
            "used_with_instanced_static_meshes": mat.get_editor_property("used_with_instanced_static_meshes"),
            "vector_parameters": [str(n) for n in mel.get_vector_parameter_names(mat)]}
    report["gameLayer"] = info
    step("built game-layer material", **info)


try:
    inspect_solid()
    import_cube()
    build_material()
except Exception as exc:  # report, never leave the commandlet silent
    report["errors"].append(repr(exc))
report["assets"] = {p: {"uasset": uasset_file(p), "sha256": sha(p)} for p in (CUBE, MAT)}
report["ok"] = not report["errors"]
out = os.environ.get("W4A_REPORT")
if out:
    with open(out, "w", encoding="utf-8", newline="\n") as h:
        json.dump(report, h, indent=2, ensure_ascii=False)
unreal.log("W4A content done ok=%s errors=%s" % (report["ok"], report["errors"]))
