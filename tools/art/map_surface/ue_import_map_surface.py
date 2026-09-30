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

M_MapBoard (lit, default surface; parameters BaseColor, GameMask, NightEV, NightSaturation, NightTint, Lift) is the
night grade of the K1 mocks (manifest.<key>.json k1.grade_b_c):
  lit      = BC * 2^NightEV * NightTint
  base     = lerp(desaturate(lit, NightSaturation), lit, mask)      (outside the game layer: graded + desaturated)
  emissive = Lift * BC * mask                                       (inside: a readability lift, unlit share)
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

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
MAIN_CHECKOUT = Path("C:/Users/ren/WebstormProjects/unmached/unmached")
MAPS = {"marmoreal": "Marmoreal", "sarpedon": "Sarpedon"}
ROOT = "/Game/EnvMaps"
MATERIAL_NAME = "M_MapBoard"
MATERIAL_PATH = f"{ROOT}/{MATERIAL_NAME}"
SHA_TAG = "EnvMapsSourceSha256"
GRAPH_TAG = "EnvMapsGraphVersion"
GRAPH_VERSION = "1"
# manifest output key -> file/asset suffix (T_<Name>_Map_<suffix>_4K)
LAYERS = {"bc": "BC", "mask": "GameMask", "sdf": "GameSDF", "id": "SpaceID"}
# not sampled by M_MapBoard yet: imported under DATA_ROOT, which DefaultGame.ini never cooks (S08MapSurfaceSpec::DataRoot)
DATA_ROOT = f"{ROOT}/Data"
DATA_LAYERS = ("sdf", "id")
# Profile contract of S08BoardArt.h (S08MapSurfaceSpec::ParamBaseColor / ParamGameMask)
PARAM_BC = "BaseColor"
PARAM_MASK = "GameMask"
DEFAULT_GRADE = {"ev": -0.7, "saturation": 0.7, "lift": 0.35, "tint_lin_luma_normalised": [0.9317, 1.0042, 1.1595]}

BASE_HLSL = """// ENV-MAPS M_MapBoard (tools/art/map_surface/ue_import_map_surface.py): night grade of the K1 mocks
float3 lit = BC.rgb * exp2(NightEV) * NightTint.rgb;
float luma = dot(lit, float3(0.2126, 0.7152, 0.0722));
float3 outside = lerp(luma.xxx, lit, NightSaturation);
return lerp(outside, lit, saturate(Mask.r));
"""


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

    base = expr(u.MaterialExpressionCustom, -500, 0)
    base.set_editor_property("description", "MapBoardNightGrade")
    base.set_editor_property("output_type", u.CustomMaterialOutputType.CMOT_FLOAT3)
    inputs = []
    for input_name in ("BC", "Mask", "NightEV", "NightSaturation", "NightTint"):
        ci = u.CustomInput()
        ci.set_editor_property("input_name", input_name)
        inputs.append(ci)
    base.set_editor_property("inputs", inputs)
    base.set_editor_property("code", BASE_HLSL)
    connect(bc, "RGB", base, "BC")
    connect(mask, "R", base, "Mask")
    connect(ev, "", base, "NightEV")
    connect(sat, "", base, "NightSaturation")
    connect(tint, "", base, "NightTint")
    mel.connect_material_property(base, "", u.MaterialProperty.MP_BASE_COLOR)

    lift_bc = expr(u.MaterialExpressionMultiply, -500, 500)
    connect(bc, "RGB", lift_bc, "A")
    connect(lift, "", lift_bc, "B")
    emissive = expr(u.MaterialExpressionMultiply, -300, 500)
    connect(lift_bc, "", emissive, "A")
    connect(mask, "R", emissive, "B")
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
    ev, sat, lift = float(grade.get("ev", -0.7)), float(grade.get("saturation", 0.7)), float(grade.get("lift", 0.35))
    r, g, b = (grade.get("tint_lin_luma_normalised") or DEFAULT_GRADE["tint_lin_luma_normalised"])[:3]
    mel.set_material_instance_scalar_parameter_value(mi, "NightEV", ev)
    mel.set_material_instance_scalar_parameter_value(mi, "NightSaturation", sat)
    mel.set_material_instance_scalar_parameter_value(mi, "Lift", lift)
    mel.set_material_instance_vector_parameter_value(mi, "NightTint", u.LinearColor(r, g, b, 1.0))
    mel.update_material_instance(mi)
    if not eal.save_loaded_asset(mi, False):
        raise RuntimeError(f"could not save {path}")
    bound_bc = mel.get_material_instance_texture_parameter_value(mi, PARAM_BC)
    bound_mask = mel.get_material_instance_texture_parameter_value(mi, PARAM_MASK)
    if bound_bc != textures["bc"] or bound_mask != textures["mask"]:
        raise RuntimeError(f"{path}: texture parameters did not bind ({bound_bc}, {bound_mask})")
    return {"action": action, "path": path, "parent": MATERIAL_PATH,
            "params": {"NightEV": ev, "NightSaturation": sat, "Lift": lift, "NightTint": [r, g, b],
                       PARAM_BC: textures["bc"].get_path_name(), PARAM_MASK: textures["mask"].get_path_name()}}


def run_import(plan: dict, force: bool) -> tuple[dict, bool]:
    result, ok, material = {}, True, None
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
              "contentRoot": ROOT, "dataRoot": DATA_ROOT, "material": MATERIAL_PATH, "maps": {}}
    plan = verify_sources(keys, root)
    ok = all(entry["ok"] for entry in plan.values())
    report["maps"] = plan
    if report["mode"] == "import":
        imported, import_ok = run_import(plan, args.force)
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
