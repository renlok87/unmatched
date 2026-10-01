"""ENV-MAPS track S: import the original-map surface into UE (out of git) and build M_MapBoard + MI per map.

The textures of tools/art/map_surface/build_map_textures.py (manifest.<key>.json) live OUT of git (user decisions
ENV-U3 / ENV-U7): scraped-data/derived/maps/<key>/T_<Name>_Map_{BC,GameMask,GameSDF,SpaceID}_4K.png in the main
checkout. This script puts them into the project's gitignored Content (unreal/Unmatched/.gitignore: Content/),
where the S08 board actor loads them by the paths of the 'map-image' board profiles
(unreal/Unmatched/Config/ArtBoards/S08ArtBoardProfiles.json; cooked through DirectoriesToAlwaysCook /Game/EnvMaps,
except /Game/EnvMaps/Data, which DefaultGame.ini never cooks):

  /Game/EnvMaps/M_MapBoard                          lit surface material (graph below), shared by both maps
  /Game/EnvMaps/<Name>/T_<Name>_Map_BC_4K           sRGB, default compression (BC1), mips
  /Game/EnvMaps/<Name>/T_<Name>_Map_GameMask_4K     linear grayscale (G8), mips
  /Game/EnvMaps/Data/<Name>/T_<Name>_Map_GameSDF_4K linear HDR (RGBA16F: the 16-bit distance codes stay precise)
  /Game/EnvMaps/Data/<Name>/T_<Name>_Map_SpaceID_4K linear half float (R16F), nearest filter, no mips
  /Game/EnvMaps/<Name>/MI_<Name>_MapBoard           child of M_MapBoard with the map's BC / mask and night grade

M_MapBoard (lit, default surface; parameters BaseColor, GameMask, NightEV, NightSaturation, NightTint, Lift and, since
graph v2 (ENV-MAPS P4, zone separation under the night light), MaskSaturation, MaskInverseTint, LiftSaturation) is the
night grade of the K1 mocks (k1_mock._night; manifest.<key>.json k1.grade_b_c = the light profile's mapGrade):
  lit      = BC * 2^NightEV * NightTint
  inside   = max(lerp(luma, lit * MaskInverseTint, MaskSaturation), 0)        (graph v2; identity at 1 / (1,1,1))
  base     = lerp(desaturate(lit, NightSaturation), inside, mask)    (outside the game layer: graded + desaturated)
  emissive = Lift * max(lerp(luma, BC, LiftSaturation), 0) * mask    (inside: a readability lift, unlit share)
The MI carries the profile grade (the board actor sets the same values on its MID at runtime, ApplyMapGrade).

ENV-MAPS P4 readability materials (map-image boards whose profile has a "readability" block; shared by both maps):
  /Game/EnvMaps/M_MapFrameWood      lit: the ART-005 wood (T_old_wood_D/N/ORM_1024) with FrameValueScale (linear albedo
                                    multiplier) and FrameSaturation - the darker map frame (review gap 9)
  /Game/EnvMaps/M_MapContactShadow  unlit, BLEND_MODULATE: a soft radial blob (Strength, Softness) on the engine plane
                                    under every fighter base
ENV-MAPS P5 track C night backdrop (map-image boards whose profile has a "backdrop" block; shared by both maps, HLSL and
numpy mirror in backdrop.py; Apply Fogging off on both - the night fog would wash them out):
  /Game/EnvMaps/M_MapBackdropMist   unlit, BLEND_TRANSLUCENT: 3-octave value-noise mist in uu (SizeUU, PanUU x Time,
                                    NoiseScaleUU, Coverage, Seed), elliptic EdgeFade; Emissive = Tint, Opacity x density
  /Game/EnvMaps/M_MapBackdropMoon   unlit, BLEND_ADDITIVE: soft gaussian glow + small disc (Tint, Intensity, Softness,
                                    DiscRadius, DiscIntensity; graph 2 / P5c: DiscSoftness = the disc edge falloff,
                                    DiscLimb = limb shading) on the engine plane (UV 0..1)
The SDF and the space-ID map are imported for the next steps (highlight by ID, crisp game layer) and are not
sampled by M_MapBoard yet; they sit under /Game/EnvMaps/Data (never cooked, ~0.4 GB kept out of the pak). Once
M_MapBoard samples them, move them out of Data and drop the DirectoriesToNeverCook line (the cooker drops a
never-cook package even when a cooked asset references it).

Before any import the sha256 of every source PNG is checked against manifest.<key>.json (a mismatching or missing
file is never imported). Idempotent: a texture whose metadata tag EnvMapsSourceSha256 equals the manifest sha and
whose settings already match is left alone; the material graph is rebuilt only when its EnvMapsGraphVersion tag
differs; the MI parameters are always re-applied (cheap). A JSON report is printed (line 'ENVMAPS-IMPORT-REPORT
{...}') and written to <project>/Saved/EnvMaps/ue-import-report.json (or --report).

Run (the editor must be CLOSED - UnrealEditor-Cmd holds the project; never inside the GPU-measurement window):
  UnrealEditor-Cmd.exe <repo>/unreal/Unmatched/Unmatched.uproject -run=pythonscript
      -script="<repo>/tools/art/map_surface/ue_import_map_surface.py --maps marmoreal,sarpedon"
      -unattended -nosplash -nullrhi
Pre-check without UE (plain Python: sha256 of the sources against the manifests only, no import):
  python -B tools/art/map_surface/ue_import_map_surface.py --check
Options: --maps a,b  --derived <dir with <key>/T_*.png>  --report <json path>  --force (re-import everything).
Source directory order: --derived, env UM_MAPS_DERIVED, <repo>/scraped-data/derived/maps (if present), the main
checkout C:/Users/ren/WebstormProjects/unmached/unmached/scraped-data/derived/maps.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import time
from pathlib import Path

try:  # inside UnrealEditor(-Cmd) only; --check runs in plain Python
    import unreal as u  # type: ignore
except ImportError:  # pragma: no cover - plain Python
    u = None

sys.path.insert(0, str(Path(__file__).resolve().parent))
import backdrop as backdrop_lib  # noqa: E402  (HLSL + parameter defaults of the backdrop materials; plain Python)

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
MAIN_CHECKOUT = Path("C:/Users/ren/WebstormProjects/unmached/unmached")
MAPS = {"marmoreal": "Marmoreal", "sarpedon": "Sarpedon"}
ROOT = "/Game/EnvMaps"
MATERIAL_NAME = "M_MapBoard"
MATERIAL_PATH = f"{ROOT}/{MATERIAL_NAME}"
SHA_TAG = "EnvMapsSourceSha256"
GRAPH_TAG = "EnvMapsGraphVersion"
GRAPH_VERSION = "2"  # v2 (ENV-MAPS P4): MaskSaturation / MaskInverseTint / LiftSaturation
# manifest output key -> file/asset suffix (T_<Name>_Map_<suffix>_4K)
LAYERS = {"bc": "BC", "mask": "GameMask", "sdf": "GameSDF", "id": "SpaceID"}
# not sampled by M_MapBoard yet: imported under DATA_ROOT, which DefaultGame.ini never cooks (S08MapSurfaceSpec::DataRoot)
DATA_ROOT = f"{ROOT}/Data"
DATA_LAYERS = ("sdf", "id")
# Profile contract of S08BoardArt.h (S08MapSurfaceSpec::ParamBaseColor / ParamGameMask)
PARAM_BC = "BaseColor"
PARAM_MASK = "GameMask"
DEFAULT_GRADE = {"ev": -0.7, "saturation": 0.7, "lift": 0.35, "tint_lin_luma_normalised": [0.9317, 1.0042, 1.1595],
                 "mask_saturation": 1.0, "lift_saturation": 1.0, "mask_inverse_tint_lin": [1.0, 1.0, 1.0]}

BASE_HLSL = """// ENV-MAPS M_MapBoard graph v2 (tools/art/map_surface/ue_import_map_surface.py): night grade of the K1 mocks
// + mask-only zone separation (P4). MaskSaturation 1 / MaskInverseTint (1,1,1) = graph v1 exactly.
float3 LumaW = float3(0.2126, 0.7152, 0.0722);
float3 lit = BC.rgb * exp2(NightEV) * NightTint.rgb;
float3 outside = lerp(dot(lit, LumaW).xxx, lit, NightSaturation);
float3 litIn = lit * MaskInverseTint.rgb;
float3 inside = max(lerp(dot(litIn, LumaW).xxx, litIn, MaskSaturation), 0.0);
return lerp(outside, inside, saturate(Mask.r));
"""

LIFT_HLSL = """// ENV-MAPS M_MapBoard graph v2: the unlit readability lift inside the game mask, chroma x LiftSaturation (P4)
float3 LumaW = float3(0.2126, 0.7152, 0.0722);
float3 c = max(lerp(dot(BC.rgb, LumaW).xxx, BC.rgb, LiftSaturation), 0.0);
return Lift * c * saturate(Mask.r);
"""

# ---- ENV-MAPS P4 readability materials (S08BoardArt.h S08MapSurfaceSpec::FrameWoodMaterialPath / ContactShadowMaterialPath)
FRAME_WOOD_NAME = "M_MapFrameWood"
FRAME_WOOD_PATH = f"{ROOT}/{FRAME_WOOD_NAME}"
FRAME_WOOD_VERSION = "1"
FRAME_WOOD_TEXTURES = {"D": "/Game/ArtTests/ART005/Textures/T_old_wood_D_1024",
                       "N": "/Game/ArtTests/ART005/Textures/T_old_wood_N_1024",
                       "ORM": "/Game/ArtTests/ART005/Textures/T_old_wood_ORM_1024"}  # = M_ART005_Wood_Probe's textures
FRAME_WOOD_DEFAULTS = {"FrameValueScale": round(0.7 ** 2.2, 4), "FrameSaturation": 0.75}
FRAME_WOOD_HLSL = """// ENV-MAPS P4 M_MapFrameWood: the ART-005 frame wood, darker (FrameValueScale = linear albedo multiplier, the
// profile's display V scale ^ 2.2) and less saturated (FrameSaturation).
float3 LumaW = float3(0.2126, 0.7152, 0.0722);
return max(lerp(dot(D, LumaW).xxx, D, FrameSaturation), 0.0) * FrameValueScale;
"""
CONTACT_SHADOW_NAME = "M_MapContactShadow"
CONTACT_SHADOW_PATH = f"{ROOT}/{CONTACT_SHADOW_NAME}"
CONTACT_SHADOW_VERSION = "1"
CONTACT_SHADOW_DEFAULTS = {"Strength": 0.5, "Softness": 0.55}
CONTACT_SHADOW_HLSL = """// ENV-MAPS P4 M_MapContactShadow (BLEND_MODULATE, unlit): the scene behind is multiplied by this - 1 at the
// plane edge, 1 - Strength at the centre, gaussian of width Softness (fraction of the radius).
float2 d = UV * 2.0 - 1.0;
float r = length(d);
float a = Strength * exp(-(r * r) / max(Softness * Softness, 1e-4)) * saturate((1.0 - r) * 6.0);
return (1.0 - saturate(a)).xxx;
"""


# ---- ENV-MAPS P5 track C night backdrop (S08BoardArt.h S08MapSurfaceSpec::BackdropMistMaterialPath / ...MoonMaterialPath)
BACKDROP_MIST_NAME = "M_MapBackdropMist"
BACKDROP_MIST_PATH = f"{ROOT}/{BACKDROP_MIST_NAME}"
BACKDROP_MOON_NAME = "M_MapBackdropMoon"
BACKDROP_MOON_PATH = f"{ROOT}/{BACKDROP_MOON_NAME}"
BACKDROP_VERSION = "1"
BACKDROP_MOON_VERSION = "2"  # ENV-MAPS P5c: DiscSoftness / DiscLimb (soft disc edge, limb shading)


def mi_params(grade: dict) -> dict:
    """MI_<Name>_MapBoard scalar / vector parameters of a grade (manifest k1.grade_b_c, i.e. the profile mapGrade; the
    graph-v2 terms default to identity). Pure Python: tools/art/map_surface/test_map_surface.py checks it."""
    tint = (grade.get("tint_lin_luma_normalised") or grade.get("tint_lin") or DEFAULT_GRADE["tint_lin_luma_normalised"])[:3]
    inv = (grade.get("mask_inverse_tint_lin") or DEFAULT_GRADE["mask_inverse_tint_lin"])[:3]
    return {"scalar": {"NightEV": float(grade.get("ev", DEFAULT_GRADE["ev"])),
                       "NightSaturation": float(grade.get("saturation", DEFAULT_GRADE["saturation"])),
                       "Lift": float(grade.get("lift", DEFAULT_GRADE["lift"])),
                       "MaskSaturation": float(grade.get("mask_saturation", 1.0)),
                       "LiftSaturation": float(grade.get("lift_saturation", 1.0))},
            "vector": {"NightTint": [float(x) for x in tint], "MaskInverseTint": [float(x) for x in inv]}}


def asset_name(name: str, layer: str) -> str:
    return f"T_{name}_Map_{LAYERS[layer]}_4K"


def asset_folder(name: str, layer: str) -> str:
    return f"{DATA_ROOT if layer in DATA_LAYERS else ROOT}/{name}"


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def derived_root(arg: str | None) -> Path:
    for cand in (arg, os.environ.get("UM_MAPS_DERIVED")):
        if cand:
            return Path(cand)
    local = REPO / "scraped-data" / "derived" / "maps"
    return local if local.is_dir() else MAIN_CHECKOUT / "scraped-data" / "derived" / "maps"


def load_manifest(key: str) -> dict:
    path = HERE / f"manifest.{key}.json"
    manifest = json.loads(path.read_text(encoding="utf-8"))
    if manifest.get("schema") != "unmatched.map-surface-manifest/1" or manifest.get("map") != key:
        raise RuntimeError(f"{path}: not the map-surface manifest of {key}")
    return manifest


def verify_sources(keys: list[str], root: Path) -> dict:
    """sha256 of every source PNG against manifest.<key>.json; nothing is imported for a map with a mismatch."""
    plan = {}
    for key in keys:
        name = MAPS[key]
        manifest = load_manifest(key)
        entry = {"name": name, "manifest": f"tools/art/map_surface/manifest.{key}.json", "layers": {}, "ok": True,
                 "grade": (manifest.get("k1") or {}).get("grade_b_c") or DEFAULT_GRADE}
        for layer in LAYERS:
            out = manifest["outputs"][layer]
            src = root / key / Path(out["path"]).name
            item = {"source": str(src), "sha256Manifest": out["sha256"], "bytesManifest": out.get("bytes"),
                    "size": [out.get("width"), out.get("height")], "format": out.get("format"),
                    "asset": f"{asset_folder(name, layer)}/{asset_name(name, layer)}"}
            if not src.is_file():
                item.update(verified=False, error="source missing")
            else:
                got = sha256_file(src)
                item.update(sha256=got, bytes=src.stat().st_size, verified=got == out["sha256"])
                if got != out["sha256"]:
                    item["error"] = "sha256 differs from the manifest (rebuild with build_map_textures.py or fix the manifest)"
            entry["ok"] = entry["ok"] and item["verified"]
            entry["layers"][layer] = item
        plan[key] = entry
    return plan


# ---------------------------------------------------------------------------------------------------- UE side
def texture_settings(layer: str) -> dict:
    """Editor properties per layer (the S08 test Unmatched.S08.BoardArt.MapAssets checks the same contract)."""
    tcs, mips, filt = u.TextureCompressionSettings, u.TextureMipGenSettings, u.TextureFilter
    # compression first (it decides what sRGB may be), then sRGB, mips, filter, group
    if layer == "bc":
        wanted = {"compression_settings": tcs.TC_DEFAULT, "srgb": True,
                  "mip_gen_settings": mips.TMGS_FROM_TEXTURE_GROUP, "filter": filt.TF_DEFAULT}
    elif layer == "mask":
        wanted = {"compression_settings": tcs.TC_GRAYSCALE, "srgb": False,
                  "mip_gen_settings": mips.TMGS_FROM_TEXTURE_GROUP, "filter": filt.TF_DEFAULT}
    elif layer == "sdf":  # RGBA16 PNG -> RGBA16F: d_px = (code - 32768) / 512 survives (fp16 step <= 1/16 px)
        wanted = {"compression_settings": tcs.TC_HDR, "srgb": False,
                  "mip_gen_settings": mips.TMGS_FROM_TEXTURE_GROUP, "filter": filt.TF_DEFAULT}
    elif layer == "id":  # Gray16 k/65535 -> R16F keeps every k exactly (k <= 38); nearest, no mips: never blended
        wanted = {"compression_settings": tcs.TC_HALF_FLOAT, "srgb": False,
                  "mip_gen_settings": mips.TMGS_NO_MIPMAPS, "filter": filt.TF_NEAREST}
    else:
        raise KeyError(layer)
    wanted.update({"lod_group": u.TextureGroup.TEXTUREGROUP_WORLD, "never_stream": False})
    return wanted


def settings_match(texture, wanted: dict) -> bool:
    return all(texture.get_editor_property(k) == v for k, v in wanted.items())


def describe_texture(texture) -> dict:
    return {
        "srgb": bool(texture.get_editor_property("srgb")),
        "compression": str(texture.get_editor_property("compression_settings")),
        "mipGen": str(texture.get_editor_property("mip_gen_settings")),
        "filter": str(texture.get_editor_property("filter")),
        "lodGroup": str(texture.get_editor_property("lod_group")),
        "sizeX": int(texture.blueprint_get_size_x()),
        "sizeY": int(texture.blueprint_get_size_y()),
    }


def import_texture(item: dict, layer: str, name: str, force: bool) -> dict:
    eal = u.EditorAssetLibrary
    path = item["asset"]
    wanted = texture_settings(layer)
    texture = u.load_asset(path) if eal.does_asset_exist(path) else None
    if (texture is not None and not force and eal.get_metadata_tag(texture, SHA_TAG) == item["sha256"]
            and settings_match(texture, wanted)):
        return {"action": "unchanged", **describe_texture(texture)}
    action = "reimported" if texture is not None else "imported"
    task = u.AssetImportTask()
    task.filename = item["source"]
    task.destination_path = asset_folder(name, layer)
    task.destination_name = asset_name(name, layer)
    task.automated = True
    task.replace_existing = True
    task.save = False
    u.AssetToolsHelpers.get_asset_tools().import_asset_tasks([task])
    texture = u.load_asset(path)
    if texture is None or not isinstance(texture, u.Texture2D):
        raise RuntimeError(f"import of {item['source']} did not produce the texture {path}")
    # every property with the default notification (PostEditChange requeues the platform-data build; the texture
    # compiler builds the last state once)
    for key, value in wanted.items():
        texture.set_editor_property(key, value)
    eal.set_metadata_tag(texture, SHA_TAG, item["sha256"])
    if not eal.save_loaded_asset(texture, False):
        raise RuntimeError(f"could not save {path}")
    if not settings_match(texture, wanted):
        raise RuntimeError(f"{path}: settings did not stick: {describe_texture(texture)}")
    return {"action": action, **describe_texture(texture)}


def build_material(bc_texture, mask_texture, force: bool) -> dict:
    """M_MapBoard: lit default surface. Rebuilt only when the graph version tag differs (or --force)."""
    eal, mel = u.EditorAssetLibrary, u.MaterialEditingLibrary
    material = u.load_asset(MATERIAL_PATH) if eal.does_asset_exist(MATERIAL_PATH) else None
    if material is not None and not force and eal.get_metadata_tag(material, GRAPH_TAG) == GRAPH_VERSION:
        return {"action": "unchanged", "path": MATERIAL_PATH, "graphVersion": GRAPH_VERSION}
    action = "rebuilt" if material is not None else "created"
    if material is None:
        material = u.AssetToolsHelpers.get_asset_tools().create_asset(MATERIAL_NAME, ROOT, u.Material, u.MaterialFactoryNew())
    if material is None:
        raise RuntimeError(f"could not create {MATERIAL_PATH}")
    material.set_editor_property("shading_model", u.MaterialShadingModel.MSM_DEFAULT_LIT)
    material.set_editor_property("two_sided", False)
    mel.delete_all_material_expressions(material)

    def expr(cls, x, y):
        node = mel.create_material_expression(material, cls, x, y)
        if node is None:
            raise RuntimeError(f"could not create {cls}")
        return node

    def connect(src, out, dst, inp):
        if not mel.connect_material_expressions(src, out, dst, inp):
            raise RuntimeError(f"could not connect {src.get_name()}.{out or '<0>'} -> {dst.get_name()}.{inp}")

    bc = expr(u.MaterialExpressionTextureSampleParameter2D, -1100, -200)
    bc.set_editor_property("parameter_name", PARAM_BC)
    bc.set_editor_property("sampler_type", u.MaterialSamplerType.SAMPLERTYPE_COLOR)
    bc.set_editor_property("texture", bc_texture)  # after the sampler type: AutoSetSampleType keeps them consistent
    mask = expr(u.MaterialExpressionTextureSampleParameter2D, -1100, 150)
    mask.set_editor_property("parameter_name", PARAM_MASK)
    mask.set_editor_property("sampler_type", u.MaterialSamplerType.SAMPLERTYPE_LINEAR_GRAYSCALE)
    mask.set_editor_property("texture", mask_texture)
    ev = expr(u.MaterialExpressionScalarParameter, -1100, 450)
    ev.set_editor_property("parameter_name", "NightEV")
    ev.set_editor_property("default_value", DEFAULT_GRADE["ev"])
    sat = expr(u.MaterialExpressionScalarParameter, -1100, 550)
    sat.set_editor_property("parameter_name", "NightSaturation")
    sat.set_editor_property("default_value", DEFAULT_GRADE["saturation"])
    tint = expr(u.MaterialExpressionVectorParameter, -1100, 650)
    tint.set_editor_property("parameter_name", "NightTint")
    r, g, b = DEFAULT_GRADE["tint_lin_luma_normalised"]
    tint.set_editor_property("default_value", u.LinearColor(r, g, b, 1.0))
    lift = expr(u.MaterialExpressionScalarParameter, -1100, 850)
    lift.set_editor_property("parameter_name", "Lift")
    lift.set_editor_property("default_value", DEFAULT_GRADE["lift"])
    # graph v2 (ENV-MAPS P4): mask-only zone separation, identity defaults
    mask_sat = expr(u.MaterialExpressionScalarParameter, -1100, 950)
    mask_sat.set_editor_property("parameter_name", "MaskSaturation")
    mask_sat.set_editor_property("default_value", 1.0)
    lift_sat = expr(u.MaterialExpressionScalarParameter, -1100, 1050)
    lift_sat.set_editor_property("parameter_name", "LiftSaturation")
    lift_sat.set_editor_property("default_value", 1.0)
    inv_tint = expr(u.MaterialExpressionVectorParameter, -1100, 1150)
    inv_tint.set_editor_property("parameter_name", "MaskInverseTint")
    inv_tint.set_editor_property("default_value", u.LinearColor(1.0, 1.0, 1.0, 1.0))

    def custom(name, x, y, input_names, code):
        node = expr(u.MaterialExpressionCustom, x, y)
        node.set_editor_property("description", name)
        node.set_editor_property("output_type", u.CustomMaterialOutputType.CMOT_FLOAT3)
        pins = []
        for input_name in input_names:
            ci = u.CustomInput()
            ci.set_editor_property("input_name", input_name)
            pins.append(ci)
        node.set_editor_property("inputs", pins)
        node.set_editor_property("code", code)
        return node

    base = custom("MapBoardNightGrade", -500, 0,
                  ("BC", "Mask", "NightEV", "NightSaturation", "NightTint", "MaskSaturation", "MaskInverseTint"),
                  BASE_HLSL)
    connect(bc, "RGB", base, "BC")
    connect(mask, "R", base, "Mask")
    connect(ev, "", base, "NightEV")
    connect(sat, "", base, "NightSaturation")
    connect(tint, "", base, "NightTint")
    connect(mask_sat, "", base, "MaskSaturation")
    connect(inv_tint, "", base, "MaskInverseTint")
    mel.connect_material_property(base, "", u.MaterialProperty.MP_BASE_COLOR)

    emissive = custom("MapBoardLift", -500, 500, ("BC", "Mask", "Lift", "LiftSaturation"), LIFT_HLSL)
    connect(bc, "RGB", emissive, "BC")
    connect(mask, "R", emissive, "Mask")
    connect(lift, "", emissive, "Lift")
    connect(lift_sat, "", emissive, "LiftSaturation")
    mel.connect_material_property(emissive, "", u.MaterialProperty.MP_EMISSIVE_COLOR)

    rough = expr(u.MaterialExpressionConstant, -300, 750)
    rough.set_editor_property("r", 0.9)
    mel.connect_material_property(rough, "", u.MaterialProperty.MP_ROUGHNESS)
    spec = expr(u.MaterialExpressionConstant, -300, 850)
    spec.set_editor_property("r", 0.25)
    mel.connect_material_property(spec, "", u.MaterialProperty.MP_SPECULAR)

    mel.layout_material_expressions(material)
    mel.recompile_material(material)
    eal.set_metadata_tag(material, GRAPH_TAG, GRAPH_VERSION)
    if not eal.save_loaded_asset(material, False):
        raise RuntimeError(f"could not save {MATERIAL_PATH}")
    return {"action": action, "path": MATERIAL_PATH, "graphVersion": GRAPH_VERSION,
            "expressions": int(mel.get_num_material_expressions(material))}


def build_instance(name: str, material, textures: dict, grade: dict) -> dict:
    eal, mel = u.EditorAssetLibrary, u.MaterialEditingLibrary
    path = f"{ROOT}/{name}/MI_{name}_MapBoard"
    mi = u.load_asset(path) if eal.does_asset_exist(path) else None
    action = "updated" if mi is not None else "created"
    if mi is None:
        mi = u.AssetToolsHelpers.get_asset_tools().create_asset(
            f"MI_{name}_MapBoard", f"{ROOT}/{name}", u.MaterialInstanceConstant, u.MaterialInstanceConstantFactoryNew())
    if mi is None:
        raise RuntimeError(f"could not create {path}")
    mel.set_material_instance_parent(mi, material)
    mel.set_material_instance_texture_parameter_value(mi, PARAM_BC, textures["bc"])
    mel.set_material_instance_texture_parameter_value(mi, PARAM_MASK, textures["mask"])
    params = mi_params(grade)
    for pname, value in params["scalar"].items():
        mel.set_material_instance_scalar_parameter_value(mi, pname, value)
    for pname, (r, g, b) in params["vector"].items():
        mel.set_material_instance_vector_parameter_value(mi, pname, u.LinearColor(r, g, b, 1.0))
    mel.update_material_instance(mi)
    if not eal.save_loaded_asset(mi, False):
        raise RuntimeError(f"could not save {path}")
    bound_bc = mel.get_material_instance_texture_parameter_value(mi, PARAM_BC)
    bound_mask = mel.get_material_instance_texture_parameter_value(mi, PARAM_MASK)
    if bound_bc != textures["bc"] or bound_mask != textures["mask"]:
        raise RuntimeError(f"{path}: texture parameters did not bind ({bound_bc}, {bound_mask})")
    return {"action": action, "path": path, "parent": MATERIAL_PATH,
            "params": {**params["scalar"], **params["vector"],
                       PARAM_BC: textures["bc"].get_path_name(), PARAM_MASK: textures["mask"].get_path_name()}}


def _new_material(path: str, name: str, version_tag: str, version: str, force: bool):
    """(material, action) for a rebuild, or (material, None) when its version tag is current (and not --force)."""
    eal, mel = u.EditorAssetLibrary, u.MaterialEditingLibrary
    material = u.load_asset(path) if eal.does_asset_exist(path) else None
    if material is not None and not force and eal.get_metadata_tag(material, version_tag) == version:
        return material, None
    action = "rebuilt" if material is not None else "created"
    if material is None:
        material = u.AssetToolsHelpers.get_asset_tools().create_asset(name, ROOT, u.Material, u.MaterialFactoryNew())
    if material is None:
        raise RuntimeError(f"could not create {path}")
    mel.delete_all_material_expressions(material)
    return material, action


def _custom_node(material, name, x, y, input_names, code):
    node = u.MaterialEditingLibrary.create_material_expression(material, u.MaterialExpressionCustom, x, y)
    if node is None:
        raise RuntimeError("could not create a Custom node")
    node.set_editor_property("description", name)
    node.set_editor_property("output_type", u.CustomMaterialOutputType.CMOT_FLOAT3)
    pins = []
    for input_name in input_names:
        ci = u.CustomInput()
        ci.set_editor_property("input_name", input_name)
        pins.append(ci)
    node.set_editor_property("inputs", pins)
    node.set_editor_property("code", code)
    return node


def _connect(src, out, dst, inp):
    if not u.MaterialEditingLibrary.connect_material_expressions(src, out, dst, inp):
        raise RuntimeError(f"could not connect {src.get_name()}.{out or '<0>'} -> {dst.get_name()}.{inp}")


def _scalar(material, name, value, x, y):
    node = u.MaterialEditingLibrary.create_material_expression(material, u.MaterialExpressionScalarParameter, x, y)
    node.set_editor_property("parameter_name", name)
    node.set_editor_property("default_value", value)
    return node


def _finish(material, path: str, tag: str, version: str, action: str) -> dict:
    eal, mel = u.EditorAssetLibrary, u.MaterialEditingLibrary
    mel.layout_material_expressions(material)
    mel.recompile_material(material)
    eal.set_metadata_tag(material, tag, version)
    if not eal.save_loaded_asset(material, False):
        raise RuntimeError(f"could not save {path}")
    return {"action": action, "path": path, "graphVersion": version,
            "expressions": int(mel.get_num_material_expressions(material))}


def build_frame_wood(force: bool) -> dict:
    """M_MapFrameWood (ENV-MAPS P4, review gap 9): the ART-005 probe wood, darker and less saturated, lit."""
    mel = u.MaterialEditingLibrary
    material, action = _new_material(FRAME_WOOD_PATH, FRAME_WOOD_NAME, GRAPH_TAG, FRAME_WOOD_VERSION, force)
    if action is None:
        return {"action": "unchanged", "path": FRAME_WOOD_PATH, "graphVersion": FRAME_WOOD_VERSION}
    textures = {k: u.load_asset(v) for k, v in FRAME_WOOD_TEXTURES.items()}
    missing = [FRAME_WOOD_TEXTURES[k] for k, t in textures.items() if t is None]
    if missing:
        raise RuntimeError(f"{FRAME_WOOD_PATH}: wood textures missing {missing}")
    material.set_editor_property("shading_model", u.MaterialShadingModel.MSM_DEFAULT_LIT)
    material.set_editor_property("two_sided", False)
    samplers = {}
    for i, (key, sampler) in enumerate((("D", u.MaterialSamplerType.SAMPLERTYPE_COLOR),
                                        ("N", u.MaterialSamplerType.SAMPLERTYPE_NORMAL),
                                        ("ORM", u.MaterialSamplerType.SAMPLERTYPE_MASKS))):
        node = mel.create_material_expression(material, u.MaterialExpressionTextureSample, -1100, -200 + 300 * i)
        node.set_editor_property("sampler_type", sampler)
        node.set_editor_property("texture", textures[key])
        samplers[key] = node
    value = _scalar(material, "FrameValueScale", FRAME_WOOD_DEFAULTS["FrameValueScale"], -1100, 700)
    satur = _scalar(material, "FrameSaturation", FRAME_WOOD_DEFAULTS["FrameSaturation"], -1100, 800)
    grade = _custom_node(material, "MapFrameWoodGrade", -500, -200, ("D", "FrameValueScale", "FrameSaturation"),
                         FRAME_WOOD_HLSL)
    _connect(samplers["D"], "RGB", grade, "D")
    _connect(value, "", grade, "FrameValueScale")
    _connect(satur, "", grade, "FrameSaturation")
    mel.connect_material_property(grade, "", u.MaterialProperty.MP_BASE_COLOR)
    mel.connect_material_property(samplers["N"], "RGB", u.MaterialProperty.MP_NORMAL)
    mel.connect_material_property(samplers["ORM"], "R", u.MaterialProperty.MP_AMBIENT_OCCLUSION)
    mel.connect_material_property(samplers["ORM"], "G", u.MaterialProperty.MP_ROUGHNESS)
    mel.connect_material_property(samplers["ORM"], "B", u.MaterialProperty.MP_METALLIC)
    return _finish(material, FRAME_WOOD_PATH, GRAPH_TAG, FRAME_WOOD_VERSION, action)


def build_contact_shadow(force: bool) -> dict:
    """M_MapContactShadow (ENV-MAPS P4): unlit modulate radial blob on the engine plane (UV 0..1)."""
    mel = u.MaterialEditingLibrary
    material, action = _new_material(CONTACT_SHADOW_PATH, CONTACT_SHADOW_NAME, GRAPH_TAG, CONTACT_SHADOW_VERSION, force)
    if action is None:
        return {"action": "unchanged", "path": CONTACT_SHADOW_PATH, "graphVersion": CONTACT_SHADOW_VERSION}
    material.set_editor_property("shading_model", u.MaterialShadingModel.MSM_UNLIT)
    material.set_editor_property("blend_mode", u.BlendMode.BLEND_MODULATE)
    material.set_editor_property("two_sided", False)
    uv = mel.create_material_expression(material, u.MaterialExpressionTextureCoordinate, -1100, 0)
    strength = _scalar(material, "Strength", CONTACT_SHADOW_DEFAULTS["Strength"], -1100, 200)
    softness = _scalar(material, "Softness", CONTACT_SHADOW_DEFAULTS["Softness"], -1100, 300)
    blob = _custom_node(material, "MapContactShadow", -500, 0, ("UV", "Strength", "Softness"), CONTACT_SHADOW_HLSL)
    _connect(uv, "", blob, "UV")
    _connect(strength, "", blob, "Strength")
    _connect(softness, "", blob, "Softness")
    mel.connect_material_property(blob, "", u.MaterialProperty.MP_EMISSIVE_COLOR)
    return _finish(material, CONTACT_SHADOW_PATH, GRAPH_TAG, CONTACT_SHADOW_VERSION, action)


def _vector(material, name, value, x, y):
    node = u.MaterialEditingLibrary.create_material_expression(material, u.MaterialExpressionVectorParameter, x, y)
    node.set_editor_property("parameter_name", name)
    node.set_editor_property("default_value", u.LinearColor(*[float(v) for v in value]))
    return node


def _translucent_unlit(material, blend) -> dict:
    """Unlit translucent with Apply Fogging off (UMaterial::bUseTranslucencyVertexFog, display name 'Apply Fogging')."""
    material.set_editor_property("shading_model", u.MaterialShadingModel.MSM_UNLIT)
    material.set_editor_property("blend_mode", blend)
    material.set_editor_property("two_sided", False)
    flags = {}
    for prop, value in (("use_translucency_vertex_fog", False), ("output_translucent_velocity", False)):
        try:
            material.set_editor_property(prop, value)
            flags[prop] = bool(material.get_editor_property(prop))
        except Exception as exc:  # noqa: BLE001 - engine-version dependent; reported, never silently assumed
            flags[prop] = f"n/a ({exc})"
    if flags.get("use_translucency_vertex_fog") is not False:
        raise RuntimeError(f"{material.get_name()}: could not switch Apply Fogging off: {flags}")
    return flags


def _check_params(material, path: str, want: dict) -> dict:
    mel = u.MaterialEditingLibrary
    got = {"vector": sorted(str(n) for n in mel.get_vector_parameter_names(material)),
           "scalar": sorted(str(n) for n in mel.get_scalar_parameter_names(material))}
    missing = [p for k in ("vector", "scalar") for p in want[k] if p not in got[k]]
    if missing:
        raise RuntimeError(f"{path}: parameters missing after the build: {missing}")
    return got


def build_backdrop_mist(force: bool) -> dict:
    """M_MapBackdropMist (ENV-MAPS P5 gap 8): unlit translucent value-noise mist (backdrop.MIST_HLSL), no fog."""
    mel = u.MaterialEditingLibrary
    material, action = _new_material(BACKDROP_MIST_PATH, BACKDROP_MIST_NAME, GRAPH_TAG, BACKDROP_VERSION, force)
    if action is None:
        return {"action": "unchanged", "path": BACKDROP_MIST_PATH, "graphVersion": BACKDROP_VERSION}
    flags = _translucent_unlit(material, u.BlendMode.BLEND_TRANSLUCENT)
    P = backdrop_lib.MIST_PARAMS
    uv = mel.create_material_expression(material, u.MaterialExpressionTextureCoordinate, -1300, -300)
    time = mel.create_material_expression(material, u.MaterialExpressionTime, -1300, -200)
    vec = {n: _vector(material, n, v, -1300, -100 + 120 * i) for i, (n, v) in enumerate(P["vector"].items())}
    sca = {n: _scalar(material, n, v, -1300, 300 + 100 * i) for i, (n, v) in enumerate(P["scalar"].items())}
    density = _custom_node(material, "MapBackdropMist", -700, 0, backdrop_lib.MIST_INPUTS, backdrop_lib.MIST_HLSL)
    density.set_editor_property("output_type", u.CustomMaterialOutputType.CMOT_FLOAT1)
    _connect(uv, "", density, "UV")
    _connect(time, "", density, "Time")
    _connect(vec["SizeUU"], "RGB", density, "Size")
    _connect(vec["PanUU"], "RGB", density, "Pan")
    for pin, param in (("NoiseScale", "NoiseScaleUU"), ("EdgeFade", "EdgeFade"), ("Coverage", "Coverage"), ("Seed", "Seed")):
        _connect(sca[param], "", density, pin)
    alpha = mel.create_material_expression(material, u.MaterialExpressionMultiply, -350, 100)
    _connect(density, "", alpha, "A")
    _connect(sca["Opacity"], "", alpha, "B")
    mel.connect_material_property(alpha, "", u.MaterialProperty.MP_OPACITY)
    mel.connect_material_property(vec["Tint"], "RGB", u.MaterialProperty.MP_EMISSIVE_COLOR)
    out = _finish(material, BACKDROP_MIST_PATH, GRAPH_TAG, BACKDROP_VERSION, action)
    out.update(flags=flags, params=_check_params(material, BACKDROP_MIST_PATH, P), blend="translucent")
    return out


def build_backdrop_moon(force: bool) -> dict:
    """M_MapBackdropMoon (ENV-MAPS P5 gap 8): unlit additive moon glow (backdrop.MOON_HLSL), no fog."""
    mel = u.MaterialEditingLibrary
    material, action = _new_material(BACKDROP_MOON_PATH, BACKDROP_MOON_NAME, GRAPH_TAG, BACKDROP_MOON_VERSION, force)
    if action is None:
        return {"action": "unchanged", "path": BACKDROP_MOON_PATH, "graphVersion": BACKDROP_MOON_VERSION}
    flags = _translucent_unlit(material, u.BlendMode.BLEND_ADDITIVE)
    P = backdrop_lib.MOON_PARAMS
    uv = mel.create_material_expression(material, u.MaterialExpressionTextureCoordinate, -1100, -200)
    tint = _vector(material, "Tint", P["vector"]["Tint"], -1100, -100)
    sca = {n: _scalar(material, n, v, -1100, 50 + 100 * i) for i, (n, v) in enumerate(P["scalar"].items())}
    glow = _custom_node(material, "MapBackdropMoon", -500, 0, backdrop_lib.MOON_INPUTS, backdrop_lib.MOON_HLSL)
    _connect(uv, "", glow, "UV")
    _connect(tint, "RGB", glow, "Tint")
    for pin in backdrop_lib.MOON_INPUTS[2:]:  # Intensity, Softness, DiscRadius, DiscIntensity, DiscSoftness, DiscLimb
        _connect(sca[pin], "", glow, pin)
    mel.connect_material_property(glow, "", u.MaterialProperty.MP_EMISSIVE_COLOR)
    out = _finish(material, BACKDROP_MOON_PATH, GRAPH_TAG, BACKDROP_MOON_VERSION, action)
    out.update(flags=flags, params=_check_params(material, BACKDROP_MOON_PATH, P), blend="additive")
    return out


def run_import(plan: dict, force: bool) -> tuple[dict, bool]:
    result, ok, material = {}, True, None
    # ENV-MAPS P4 readability materials (map independent; a failure is reported, the maps still import)
    readability = {}
    for key, builder in (("frameWood", build_frame_wood), ("contactShadow", build_contact_shadow),
                         ("backdropMist", build_backdrop_mist), ("backdropMoon", build_backdrop_moon)):
        try:
            readability[key] = builder(force)
        except Exception as exc:  # report and continue
            readability[key] = {"action": "failed", "error": str(exc)}
            ok = False
    result["_readability"] = readability
    for key, entry in plan.items():
        name = entry["name"]
        out = {"layers": {}}
        result[key] = out
        if not entry["ok"]:
            out["skipped"] = "source verification failed (sha256 / missing); nothing imported for this map"
            ok = False
            continue
        textures = {}
        for layer, item in entry["layers"].items():
            try:
                out["layers"][layer] = import_texture(item, layer, name, force)
                textures[layer] = u.load_asset(item["asset"])
            except Exception as exc:  # report and continue with the next map
                out["layers"][layer] = {"action": "failed", "error": str(exc)}
                ok = False
        if "bc" not in textures or "mask" not in textures:
            out["material"] = {"action": "skipped", "error": "BC or mask missing"}
            ok = False
            continue
        try:
            if material is None:
                out["masterMaterial"] = build_material(textures["bc"], textures["mask"], force)
                material = u.load_asset(MATERIAL_PATH)
            out["materialInstance"] = build_instance(name, material, textures, entry["grade"])
        except Exception as exc:
            out["materialInstance"] = {"action": "failed", "error": str(exc)}
            ok = False
    return result, ok


# ---------------------------------------------------------------------------------------------------- entry
def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n", 1)[0])
    parser.add_argument("--maps", default=",".join(MAPS), help="comma list of map keys (marmoreal,sarpedon)")
    parser.add_argument("--derived", default=None, help="directory with <key>/T_<Name>_Map_*_4K.png")
    parser.add_argument("--report", default=None, help="report JSON path")
    parser.add_argument("--check", action="store_true", help="verify the source sha256 only (no UE import)")
    parser.add_argument("--force", action="store_true", help="re-import textures and rebuild the material")
    args = parser.parse_args(argv)
    keys = [k.strip() for k in args.maps.split(",") if k.strip()]
    unknown = [k for k in keys if k not in MAPS]
    if unknown:
        print(f"unknown map key(s) {unknown}; known: {sorted(MAPS)}")
        return 2
    started = time.time()
    root = derived_root(args.derived)
    report = {"schema": "unmatched.env-maps-ue-import/1", "tool": "tools/art/map_surface/ue_import_map_surface.py",
              "mode": "check" if (args.check or u is None) else "import", "derivedRoot": str(root),
              "contentRoot": ROOT, "dataRoot": DATA_ROOT, "material": MATERIAL_PATH, "graphVersion": GRAPH_VERSION,
              "readability": {"frameWood": FRAME_WOOD_PATH, "contactShadow": CONTACT_SHADOW_PATH,
                              "backdropMist": BACKDROP_MIST_PATH, "backdropMoon": BACKDROP_MOON_PATH}, "maps": {}}
    plan = verify_sources(keys, root)
    ok = all(entry["ok"] for entry in plan.values())
    report["maps"] = plan
    if report["mode"] == "import":
        imported, import_ok = run_import(plan, args.force)
        report["readabilityMaterials"] = imported.pop("_readability", {})
        for key, value in imported.items():
            report["maps"][key]["ue"] = value
        ok = ok and import_ok
        report["engine"] = str(u.SystemLibrary.get_engine_version())
    report["ok"] = ok
    report["seconds"] = round(time.time() - started, 1)
    text = json.dumps(report, ensure_ascii=False, indent=1)
    if args.report:
        report_path = Path(args.report)
    elif u is not None:
        report_path = Path(u.Paths.project_saved_dir()) / "EnvMaps" / "ue-import-report.json"
    else:
        report_path = None
    if report_path is not None:
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text(text + "\n", encoding="utf-8")
        report["reportPath"] = str(report_path)
    print("ENVMAPS-IMPORT-REPORT " + json.dumps(report, ensure_ascii=False))
    print(f"ENVMAPS-IMPORT-RESULT {'ok' if ok else 'failed'} mode={report['mode']} maps={','.join(keys)}")
    return 0 if ok else 1


if __name__ == "__main__":
    code = main(sys.argv[1:])
    if u is None:
        sys.exit(code)
    elif code != 0:
        # inside UE: an exception makes the pythonscript commandlet log an error (the report says what failed)
        raise RuntimeError("ENVMAPS import failed - see ENVMAPS-IMPORT-REPORT")
