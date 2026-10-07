"""ENV-MAPS P7 (ENV-U15) concept paste, track A: import the concept-paste textures and meshes into UE (out of git).

Sources (checked by sha256 before anything is imported; a mismatching / missing file is never imported):
  textures  <derived>/<map>/T_<Name>_Concept<Key>.png   tools/art/concept_paste/cp_bake.py, OUT of git (ENV-U3 / U7:
            painted over a render of the original map); manifest.<map>.json (git) holds their sha256
  meshes    art/pipeline-candidates/ASSET-ENV-CONCEPT-PASTE-001/20261001-p7/export/*.fbx (git, UM_FBX_v1, headless
            Blender: cp_proxies.py / blender_cp_assets.py); reports/build-report.json holds their sha256
Targets (the asset names of S08ArtBoardProfiles.json conceptPaste and of EnvLayouts/<map>.concept.layout.json):
  /Game/EnvMaps/<Name>/ConceptPaste/T_<Name>_ConceptPlateA   plate A (centre, x2 detail) RGBA, sRGB, BC7, mips, clamp
  /Game/EnvMaps/<Name>/ConceptPaste/T_<Name>_ConceptPlateB   plate B (outskirts) RGBA (A = matte x cut), sRGB, BC7, clamp
  /Game/EnvMaps/<Name>/ConceptPaste/T_<Name>_ConceptSea      sea layer RGB, sRGB, BC7, clamp
  /Game/EnvMaps/<Name>/ConceptPaste/T_<Name>_ConceptWater    (Sarpedon) flow masks R waterfall / G bay surf / B sea,
                                                             linear, TC_Masks, clamp
  /Game/EnvMaps/<Name>/ConceptPaste/T_<Name>_ConceptAnim     (Marmoreal, VS-5 EN-07) the anim masks R lantern glow /
                                                             G crowns / B mist / A petal area, linear, TC_Masks, mips, clamp
  /Game/EnvMaps/<Name>/ConceptPaste/SM_<Name>_ConceptSheet   the relief depth sheet (board space, pivot = map centre),
                                                             Nanite off, no collision; slot -> M_ConceptPaste when it
                                                             exists (tools/art/concept_paste/ue_concept_material.py)
  /Game/EnvKit/ConceptPaste/SM_EnvCP_LanternHead             the hanging lantern (slot -> /Game/EnvKit/Sarpedon/
                                                             MI_Env_LanternPost: same UVs as the post)
  /Game/EnvKit/ConceptPaste/SM_EnvCP_BannerCloth             the hanging banner cloth (P7c: procedural grid, slot ->
                                                             MI_EnvCP_Banner of M_EnvCP_Banner, built here)
  /Game/EnvKit/ConceptPaste/M_EnvCP_Banner / MI_EnvCP_Banner P7c: lit two-sided cloth, crimson + the painted pale hexagram
                                                             from UV0, emissive fill (the painted cloth's display
                                                             colour), WPO wind x WindLive (MI 0 = still: the frozen
                                                             -Bench; the board actor sets 1 on a MID in live runs)
  /Game/EnvKit/ConceptPaste/SM_EnvCP_Cannon                  P7c: a copy of the kit SM_Env_Cannon on MI_EnvCP_CannonIron
                                                             (M_EnvProp child, the kit cannon's textures, desaturated
                                                             and darkened: the painted barrels are dark iron)
/Game/EnvMaps and /Game/EnvKit are cooked by DirectoriesToAlwaysCook (never under /Game/EnvMaps/Data). The material and
the per-map MI are track B's (ue_concept_material.py); the board actor binds the textures from the profile block.

Idempotent: an asset whose metadata tag EnvMapsConceptSha256 equals the source sha256 and whose settings match is left
alone (--force re-imports). A JSON report is printed ('CONCEPT-PASTE-IMPORT-REPORT {...}', 'CONCEPT-PASTE-IMPORT-RESULT
ok|failed') and written to <project>/Saved/EnvMaps/concept-paste-import-report.json (or --report).

Run (the editor must be CLOSED; never inside a GPU-measurement window; UnrealEditor-Cmd holds the project):
  UnrealEditor-Cmd.exe <repo>/unreal/Unmatched/Unmatched.uproject -run=pythonscript
      -script="<repo>/tools/art/concept_paste/ue_import_concept_paste.py --maps sarpedon,marmoreal"
      -unattended -nosplash -nullrhi
Pre-check without UE (plain Python: presence + sha256 of every source, the kit MIs the details need are listed):
  python -B tools/art/concept_paste/ue_import_concept_paste.py --check
Options: --maps a,b  --derived <dir with <map>/T_*.png>  --report <json>  --force  --no-details
Derived directory order: --derived, env UM_CONCEPT_PASTE_DERIVED, <repo>/scraped-data/derived/concept-paste, the main
checkout's scraped-data/derived/concept-paste.
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
if u is not None and not hasattr(u, "EditorAssetLibrary"):  # the repo's unreal/ folder as a namespace package
    u = None

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
MAIN_CHECKOUT = Path("C:/Users/ren/WebstormProjects/unmached/unmached")
MAPS = {"marmoreal": "Marmoreal", "sarpedon": "Sarpedon"}
RUN = REPO / "art" / "pipeline-candidates" / "ASSET-ENV-CONCEPT-PASTE-001" / "20261001-p7"
BUILD_REPORT = RUN / "reports" / "build-report.json"
ENVMAPS_ROOT = "/Game/EnvMaps"
KIT_ROOT = "/Game/EnvKit"
FOLDER = ENVMAPS_ROOT + "/{name}/ConceptPaste"
DETAIL_FOLDER = KIT_ROOT + "/ConceptPaste"
MATERIAL = ENVMAPS_ROOT + "/ConceptPaste/M_ConceptPaste"
SHA_TAG = "EnvMapsConceptSha256"
DETAILS = {  # mesh -> the MI its slots take (same UVs as the source prop; P7c: the banner has its own material)
    "SM_EnvCP_LanternHead": DETAIL_FOLDER + "/MI_EnvCP_LanternHead",
    "SM_EnvCP_BannerCloth": DETAIL_FOLDER + "/MI_EnvCP_Banner",
}
# P7 tune: the concept's lanterns are lit panes (C0 crops: the kit glass at x7.6 reads as a dark frame with a spark);
# a child of the kit MI (same M_EnvProp emissive window of tools/art/env_kit/env_prop_look.py) with a wider window and a
# stronger glass glow. name -> (parent, scalar overrides, vector overrides)
DETAIL_MIS = {
    DETAIL_FOLDER + "/MI_EnvCP_LanternHead": (
        KIT_ROOT + "/Sarpedon/MI_Env_LanternPost",
        # P7c: the painted panes glow over their whole height (C0 crops): a wider value window, a bit stronger
        {"EmissiveIntensity": 9.0},
        {"EmissiveWindow": (42.0, 18.0, 0.2, 0.4, 0.0), "EmissiveColor": (1.0, 0.42, 0.1, 1.0)},
    ),
    # P7c: the painted banner (concept at C0: cloth median sRGB (57, 13, 13), sigil lines up to (178, 113, 71)). Tuned in
    # UE frames at C0 (t3: Fill 0.7 + ClothA 0.32 read (117, 52, 47) - the key / lantern light dominates the lit cloth):
    # albedo ~ the painted scene value / the measured irradiance (~2), a small emissive fill
    DETAIL_FOLDER + "/MI_EnvCP_Banner": (
        DETAIL_FOLDER + "/M_EnvCP_Banner",
        {"WindLive": 0.0, "Fill": 0.1, "SigilBoost": 2.0, "Aspect": 4.0, "Roughness": 0.85},
        {"ClothA": (0.15, 0.033, 0.032, 1.0), "ClothB": (0.07, 0.014, 0.014, 1.0), "Sigil": (0.42, 0.19, 0.11, 1.0),
         "Rod": (0.05, 0.034, 0.024, 1.0), "SigilC": (0.5, 0.5, 0.46, 0.024),
         "Wind": (3.0, 0.35, 5.0, 0.35)},
    ),
}
DETAIL_MI_TAG = "EnvMapsConceptDetailMi"
DETAIL_MI_VERSION = "6"
# P7c: M_EnvCP_Banner (built here, idempotent by its graph tag) - the HLSL of its two Custom nodes
BANNER_MATERIAL = DETAIL_FOLDER + "/M_EnvCP_Banner"
BANNER_GRAPH_TAG = "EnvMapsGraphVersion"
BANNER_GRAPH_VERSION = "2"
_BANNER_PATTERN = """float2 uv = UV;
float rod = step(uv.y, 0.0);
float2 p = float2(uv.x - SigilC.x, (uv.y - SigilC.y) * Aspect);
float R = SigilC.z;
float lw = SigilC.w;
float r = length(p);
float wob = 0.010 * sin(uv.y * 37.0 + uv.x * 11.0) + 0.007 * sin(uv.x * 53.0 - uv.y * 23.0);
float sig = 0.0;
for (int i = 0; i < 6; i++) {
  float a = 0.5235988 + 1.0471976 * i;
  float d = abs(dot(p, float2(cos(a), sin(a))) - R * 0.5 + wob);
  sig = max(sig, 1.0 - smoothstep(lw * 0.5, lw * 0.5 + 0.012, d));
}
sig *= 1.0 - smoothstep(R * 1.06, R * 1.14, r);
float fold = 0.5 + 0.5 * sin(6.2831853 * 2.5 * uv.x + 0.7);
float edge = smoothstep(0.0, 0.08, uv.x) * smoothstep(0.0, 0.08, 1.0 - uv.x);
float n = frac(sin(dot(floor(uv * float2(18.0, 70.0)), float2(12.9898, 78.233))) * 43758.5453);
float3 c = lerp(ClothB, ClothA, saturate(0.3 + 0.7 * fold));
c *= lerp(0.7, 1.0, edge) * lerp(0.86, 1.04, n) * lerp(1.0, 0.6, smoothstep(0.78, 1.0, uv.y));
c = lerp(c, Sigil * lerp(0.82, 1.0, n), saturate(sig) * 0.92);
sig *= 1.0 - rod;
c = lerp(c, Rod, rod);
"""
BANNER_HLSL_ALBEDO = _BANNER_PATTERN + "return c;\n"
BANNER_HLSL_EMISSIVE = _BANNER_PATTERN + "return c * Fill * (1.0 + SigilBoost * sig) * (1.0 - rod);\n"
# local offset (uu before the prop scale): out of the cloth plane (X) and sideways (Y), 0 at the rail, growing to the hem
BANNER_HLSL_WIND = """float h = pow(saturate(UV.y), 1.4) * step(0.0, UV.y);
float ph = 6.2831853 * Wind.y * T * Live;
float x = Wind.x * h * (0.8 * sin(ph + UV.y * Wind.z + UV.x * 1.7) + 0.35 * sin(2.3 * ph + UV.y * 2.1 * Wind.z + 1.3));
float y = Wind.w * Wind.x * h * sin(0.7 * ph + 1.1 + UV.y * 1.9);
return float3(x, y, 0.0);
"""
BANNER_VECTORS = ("ClothA", "ClothB", "Sigil", "Rod", "SigilC", "Wind")
BANNER_SCALARS = ("WindLive", "Fill", "SigilBoost", "Aspect", "Roughness")
# P7c: the dark-iron cannon (copy of the kit mesh on an M_EnvProp child with the kit cannon's textures)
KIT_CANNON = KIT_ROOT + "/Sarpedon/SM_Env_Cannon"
CANNON_MESH = DETAIL_FOLDER + "/SM_EnvCP_Cannon"
CANNON_MI = DETAIL_FOLDER + "/MI_EnvCP_CannonIron"
ENV_PROP_MASTER = KIT_ROOT + "/Shared/M_EnvProp"
CANNON_TEXTURES = ("BaseColorTexture", "NormalTexture", "ORMTexture")
# P7c tune (C0 crops): the painted barrels are neutral dark iron with bright rims; v1 (S x 0.15, V x 0.42, rough
# 0.25..0.75) read dark brown under the lantern light -> grey (S x 0), a bit lighter, glossier
# ENV-MAPS P10 (RD-3 V-3): in the lit3d ship ports the barrels still read black (ΔL* to the hull side <= 5 at C0) ->
# lighter iron (V x 0.55 -> 1.2) and glossier (roughness 0.12..0.35: the moon / lantern highlight on the rims)
CANNON_LOOK = {"vectors": {"RestAdjust": (0.0, 1.2, 0.0, 0.0)}, "scalars": {"RoughnessMin": 0.12, "RoughnessMax": 0.35}}
CANNON_TAG = "EnvMapsConceptCannon"
CANNON_VERSION = "2"  # the mesh copy (unchanged since P7c)
CANNON_MI_VERSION = "3"  # P10: the MI look alone
LINEAR_KEYS = ("Water", "Anim")  # VS-5 EN-07: T_<Name>_ConceptAnim = the AnimMask (linear masks)


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with Path(path).open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def rel(path: Path) -> str:
    try:
        return Path(path).resolve().relative_to(REPO).as_posix()
    except ValueError:
        return Path(path).as_posix()


def derived_root(arg: str | None) -> Path:
    for cand in (arg, os.environ.get("UM_CONCEPT_PASTE_DERIVED")):
        if cand:
            return Path(cand)
    local = REPO / "scraped-data" / "derived" / "concept-paste"
    return local if local.is_dir() else MAIN_CHECKOUT / "scraped-data" / "derived" / "concept-paste"


def load_manifest(key: str) -> dict:
    path = HERE / f"manifest.{key}.json"
    m = json.loads(path.read_text(encoding="utf-8"))
    if m.get("schema") != "unmatched.concept-paste.derived/1" or m.get("map") != key:
        raise RuntimeError(f"{path}: not the concept-paste manifest of {key}")
    return m


def texture_asset(key: str, file_name: str) -> str:
    return f"{FOLDER.format(name=MAPS[key])}/{Path(file_name).stem}"


def mesh_asset(name: str) -> str:
    if name in DETAILS:
        return f"{DETAIL_FOLDER}/{name}"
    for key, n in MAPS.items():
        if name.startswith(f"SM_{n}_Concept"):
            return f"{FOLDER.format(name=n)}/{name}"
    raise KeyError(name)


def plan(keys: list[str], root: Path, details: bool = True) -> dict:
    """sha256 of every source against the manifests / the build report (plain Python)."""
    out = {"maps": {}, "meshes": {}, "ok": True}
    rep = json.loads(BUILD_REPORT.read_text(encoding="utf-8")) if BUILD_REPORT.is_file() else None
    exports = {e["name"]: e for e in (rep or {}).get("exports", [])}
    if rep is None:
        out["ok"] = False
        out["errors"] = [f"{rel(BUILD_REPORT)} missing (cp_proxies.py build)"]
    for key in keys:
        entry = {"name": MAPS[key], "textures": {}, "ok": True}
        try:
            man = load_manifest(key)
        except (OSError, RuntimeError) as exc:
            entry.update(ok=False, error=str(exc))
            out["maps"][key] = entry
            out["ok"] = False
            continue
        entry["materialContract"] = man.get("materialContract")
        for tkey, o in man["outputs"].items():
            src = root / key / o["file"]
            item = {"key": tkey, "source": src.as_posix(), "sha256Manifest": o["sha256"], "size": o["size"],
                    "channels": o["channels"], "asset": texture_asset(key, o["file"]),
                    "linear": tkey in LINEAR_KEYS}
            if not src.is_file():
                item.update(verified=False, error="source missing (run cp_bake.py bake)")
            else:
                got = sha256_file(src)
                item.update(sha256=got, verified=got == o["sha256"])
                if got != o["sha256"]:
                    item["error"] = "sha256 differs from the manifest"
            entry["ok"] = entry["ok"] and item["verified"]
            entry["textures"][tkey] = item
        sheet = f"SM_{MAPS[key]}_ConceptSheet"
        entry["sheet"] = sheet
        out["maps"][key] = entry
        out["ok"] = out["ok"] and entry["ok"]
        if sheet not in exports:
            out["ok"] = False
            entry["ok"] = False
            entry["error"] = f"{sheet} not in the build report"
        else:
            out["meshes"][sheet] = None
    names = list(out["meshes"]) + (list(DETAILS) if details else [])
    for name in names:
        e = exports.get(name)
        item = {"asset": mesh_asset(name), "mi": DETAILS.get(name, MATERIAL)}
        if e is None:
            item.update(verified=False, error="not in the build report")
        else:
            src = REPO / e["fbx"]
            item.update(source=src.as_posix(), sha256Report=e["sha256"], triangles=e["triangles"],
                        boundsUU=e["boundsUeLocalUU"], checks=all(e["checks"].values()))
            if not src.is_file():
                item.update(verified=False, error="FBX missing")
            else:
                got = sha256_file(src)
                item.update(sha256=got, verified=got == e["sha256"] and item["checks"])
                if not item["verified"]:
                    item["error"] = "sha256 differs from the build report" if got != e["sha256"] else "build checks failed"
        out["meshes"][name] = item
        out["ok"] = out["ok"] and item["verified"]
    return out


# ---------------------------------------------------------------------------------------------------- UE side
def texture_settings(linear: bool) -> dict:
    tcs, mips, grp = u.TextureCompressionSettings, u.TextureMipGenSettings, u.TextureGroup
    wanted = ({"compression_settings": tcs.TC_MASKS, "srgb": False} if linear
              else {"compression_settings": tcs.TC_BC7, "srgb": True})
    wanted.update({"mip_gen_settings": mips.TMGS_FROM_TEXTURE_GROUP, "lod_group": grp.TEXTUREGROUP_WORLD,
                   "never_stream": False, "address_x": u.TextureAddress.TA_CLAMP,
                   "address_y": u.TextureAddress.TA_CLAMP})
    return wanted


def settings_match(obj, wanted: dict) -> bool:
    return all(obj.get_editor_property(k) == v for k, v in wanted.items())


def describe_texture(t) -> dict:
    return {"srgb": bool(t.get_editor_property("srgb")), "compression": str(t.get_editor_property("compression_settings")),
            "address": [str(t.get_editor_property("address_x")), str(t.get_editor_property("address_y"))],
            "sizeX": int(t.blueprint_get_size_x()), "sizeY": int(t.blueprint_get_size_y())}


def import_texture(item: dict, force: bool) -> dict:
    eal = u.EditorAssetLibrary
    path = item["asset"]
    wanted = texture_settings(item["linear"])
    tex = u.load_asset(path) if eal.does_asset_exist(path) else None
    if tex is not None and not force and eal.get_metadata_tag(tex, SHA_TAG) == item["sha256"] and settings_match(tex, wanted):
        return {"action": "unchanged", **describe_texture(tex)}
    action = "reimported" if tex is not None else "imported"
    folder, leaf = path.rsplit("/", 1)
    task = u.AssetImportTask()
    task.filename = item["source"]
    task.destination_path = folder
    task.destination_name = leaf
    task.automated = True
    task.replace_existing = True
    task.save = False
    u.AssetToolsHelpers.get_asset_tools().import_asset_tasks([task])
    tex = u.load_asset(path)
    if tex is None or not isinstance(tex, u.Texture2D):
        raise RuntimeError(f"import of {item['source']} did not produce the texture {path}")
    for k, v in wanted.items():  # compression first (dict order), then sRGB, mips, group, address
        tex.set_editor_property(k, v)
    eal.set_metadata_tag(tex, SHA_TAG, item["sha256"])
    if not eal.save_loaded_asset(tex, False):
        raise RuntimeError(f"could not save {path}")
    if not settings_match(tex, wanted):
        raise RuntimeError(f"{path}: settings did not stick: {describe_texture(tex)}")
    got = describe_texture(tex)
    if [got["sizeX"], got["sizeY"]] != list(item["size"]):
        raise RuntimeError(f"{path}: size {got['sizeX']}x{got['sizeY']} != {item['size']} (LOD group clamp?)")
    return {"action": action, **got}


def kit():
    sys.path.insert(0, str(REPO / "tools" / "art" / "env_kit"))
    import ue_import_env_kit as K  # noqa: E402  (import_mesh / sm_api / setp: the kit's FBX route)
    return K


def import_mesh(name: str, item: dict, force: bool) -> dict:
    eal = u.EditorAssetLibrary
    K = kit()
    path = item["asset"]
    mesh = u.load_asset(path) if eal.does_asset_exist(path) else None
    action = "unchanged"
    res = {}
    if mesh is None or force or eal.get_metadata_tag(mesh, SHA_TAG) != item["sha256"]:
        action = "reimported" if mesh is not None else "imported"
        res = K.import_mesh({"abs": item["source"], "path": rel(Path(item["source"]))}, path, 1.0)
        mesh = u.load_asset(path)
        if mesh is None or not isinstance(mesh, u.StaticMesh):
            raise RuntimeError(f"import of {item['source']} did not produce the static mesh {path}")
        eal.set_metadata_tag(mesh, SHA_TAG, item["sha256"])
    sms = K.sm_api()
    changes = []
    nanite = mesh.get_editor_property("nanite_settings")
    if nanite.get_editor_property("enabled"):
        nanite.set_editor_property("enabled", False)
        mesh.set_editor_property("nanite_settings", nanite)
        changes.append("nanite off")
    if sms.get_simple_collision_count(mesh) > 0:
        sms.remove_collisions(mesh)
        changes.append("simple collision removed")
    try:
        body = mesh.get_editor_property("body_setup")
        flag = u.CollisionTraceFlag.CTF_USE_SIMPLE_AS_COMPLEX
        if body is not None and body.get_editor_property("collision_trace_flag") != flag:
            body.set_editor_property("collision_trace_flag", flag)
            changes.append("collision trace simple-as-complex (no collision)")
    except Exception as exc:  # noqa: BLE001 - optional hardening
        changes.append(f"collision trace flag not set ({type(exc).__name__}: {exc})")
    mi_path = item["mi"]
    mi = u.load_asset(mi_path) if eal.does_asset_exist(mi_path) else None
    slots = len(mesh.get_editor_property("static_materials"))
    if mi is None:
        changes.append(f"slots left as imported: {mi_path} missing" +
                       (" (track B: ue_concept_material.py)" if mi_path == MATERIAL else " (run ue_import_env_kit.py)"))
    else:
        for i in range(slots):
            cur = mesh.get_material(i)
            if cur is None or cur.get_path_name() != mi.get_path_name():
                mesh.set_material(i, mi)
                changes.append(f"slot {i} -> {mi.get_name()}")
    if changes or action != "unchanged":
        if not eal.save_loaded_asset(mesh, False):
            raise RuntimeError(f"could not save {path}")
    box = mesh.get_bounding_box()
    got = [round(box.min.x, 2), round(box.min.y, 2), round(box.min.z, 2), round(box.max.x, 2), round(box.max.y, 2),
           round(box.max.z, 2)]
    want = item["boundsUU"]["min"] + item["boundsUU"]["max"]
    err = max(abs(a - b) for a, b in zip(got, want))
    if err > 0.5:
        raise RuntimeError(f"{path}: bounds {got} differ from the build report {want} by {err:.2f} uu (import scale?)")
    return {"action": action, **res, "changes": changes, "slots": slots, "boundsUU": got, "boundsErrUU": round(err, 3),
            "mi": mi_path if mi is not None else None}


def _mexpr(material, cls, x, y):
    node = u.MaterialEditingLibrary.create_material_expression(material, cls, x, y)
    if node is None:
        raise RuntimeError(f"could not create {cls}")
    return node


def _mconnect(src, out, dst, inp):
    if not u.MaterialEditingLibrary.connect_material_expressions(src, out, dst, inp):
        raise RuntimeError(f"could not connect {src.get_name()}.{out or '<0>'} -> {dst.get_name()}.{inp}")


def _custom(material, name, code, inputs, out_type, x, y):
    node = _mexpr(material, u.MaterialExpressionCustom, x, y)
    node.set_editor_property("description", name)
    node.set_editor_property("output_type", out_type)
    pins = []
    for pin in inputs:
        ci = u.CustomInput()
        ci.set_editor_property("input_name", pin)
        pins.append(ci)
    node.set_editor_property("inputs", pins)
    node.set_editor_property("code", code)
    return node


def ensure_banner_material(force: bool) -> dict:
    """P7c: M_EnvCP_Banner - default lit, two-sided, opaque; BaseColor / Emissive from the painted pattern (UV0), WPO =
    TransformVector(local -> world, the wind offset x WindLive)."""
    eal, mel = u.EditorAssetLibrary, u.MaterialEditingLibrary
    m = u.load_asset(BANNER_MATERIAL) if eal.does_asset_exist(BANNER_MATERIAL) else None
    if m is not None and not force and eal.get_metadata_tag(m, BANNER_GRAPH_TAG) == BANNER_GRAPH_VERSION:
        return {"action": "unchanged", "path": BANNER_MATERIAL, "graphVersion": BANNER_GRAPH_VERSION}
    action = "rebuilt" if m is not None else "created"
    if m is None:
        folder, name = BANNER_MATERIAL.rsplit("/", 1)
        m = u.AssetToolsHelpers.get_asset_tools().create_asset(name, folder, u.Material, u.MaterialFactoryNew())
    mel.delete_all_material_expressions(m)
    m.set_editor_property("shading_model", u.MaterialShadingModel.MSM_DEFAULT_LIT)
    m.set_editor_property("blend_mode", u.BlendMode.BLEND_OPAQUE)
    m.set_editor_property("two_sided", True)
    uv = _mexpr(m, u.MaterialExpressionTextureCoordinate, -1500, 0)
    t = _mexpr(m, u.MaterialExpressionTime, -1500, 120)
    params = {}
    y = -500
    for name in BANNER_VECTORS:
        node = _mexpr(m, u.MaterialExpressionVectorParameter, -1500, y)
        node.set_editor_property("parameter_name", name)
        params[name] = node
        y += 110
    for name in BANNER_SCALARS:
        node = _mexpr(m, u.MaterialExpressionScalarParameter, -1500, y)
        node.set_editor_property("parameter_name", name)
        params[name] = node
        y += 90
    f3, f4 = u.CustomMaterialOutputType.CMOT_FLOAT3, u.CustomMaterialOutputType.CMOT_FLOAT4
    pattern_pins = ("UV", "ClothA", "ClothB", "Sigil", "Rod", "SigilC", "Aspect")
    albedo = _custom(m, "BannerAlbedo", BANNER_HLSL_ALBEDO, pattern_pins, f3, -700, -300)
    emissive = _custom(m, "BannerEmissive", BANNER_HLSL_EMISSIVE, pattern_pins + ("Fill", "SigilBoost"), f3, -700, 0)
    wind = _custom(m, "BannerWind", BANNER_HLSL_WIND, ("UV", "T", "Live", "Wind"), f3, -700, 300)
    for node in (albedo, emissive):
        _mconnect(uv, "", node, "UV")
        for pin in ("ClothA", "ClothB", "Sigil", "Rod"):
            _mconnect(params[pin], "RGB", node, pin)
        if not mel.connect_material_expressions(params["SigilC"], "RGBA", node, "SigilC"):
            app = _mexpr(m, u.MaterialExpressionAppendVector, -1100, -200)
            _mconnect(params["SigilC"], "RGB", app, "A")
            _mconnect(params["SigilC"], "A", app, "B")
            _mconnect(app, "", node, "SigilC")
        _mconnect(params["Aspect"], "", node, "Aspect")
    _mconnect(params["Fill"], "", emissive, "Fill")
    _mconnect(params["SigilBoost"], "", emissive, "SigilBoost")
    _mconnect(uv, "", wind, "UV")
    _mconnect(t, "", wind, "T")
    _mconnect(params["WindLive"], "", wind, "Live")
    if not mel.connect_material_expressions(params["Wind"], "RGBA", wind, "Wind"):
        app = _mexpr(m, u.MaterialExpressionAppendVector, -1100, 300)
        _mconnect(params["Wind"], "RGB", app, "A")
        _mconnect(params["Wind"], "A", app, "B")
        _mconnect(app, "", wind, "Wind")
    tv = _mexpr(m, u.MaterialExpressionTransform, -350, 300)
    src_enum, dst_enum = u.MaterialVectorCoordTransformSource, u.MaterialVectorCoordTransform
    tv.set_editor_property("transform_source_type",
                           getattr(src_enum, "TRANSFORMSOURCE_LOCAL", None) or getattr(src_enum, "LOCAL"))
    tv.set_editor_property("transform_type", getattr(dst_enum, "TRANSFORM_WORLD", None) or getattr(dst_enum, "WORLD"))
    _mconnect(wind, "", tv, "")
    mel.connect_material_property(albedo, "", u.MaterialProperty.MP_BASE_COLOR)
    mel.connect_material_property(emissive, "", u.MaterialProperty.MP_EMISSIVE_COLOR)
    mel.connect_material_property(params["Roughness"], "", u.MaterialProperty.MP_ROUGHNESS)
    mel.connect_material_property(tv, "", u.MaterialProperty.MP_WORLD_POSITION_OFFSET)
    mel.layout_material_expressions(m)
    mel.recompile_material(m)
    eal.set_metadata_tag(m, BANNER_GRAPH_TAG, BANNER_GRAPH_VERSION)
    if not eal.save_loaded_asset(m, False):
        raise RuntimeError(f"could not save {BANNER_MATERIAL}")
    got = {"vector": sorted(str(n) for n in mel.get_vector_parameter_names(m)),
           "scalar": sorted(str(n) for n in mel.get_scalar_parameter_names(m))}
    missing = [n for n in BANNER_VECTORS if n not in got["vector"]] + [n for n in BANNER_SCALARS if n not in got["scalar"]]
    if missing:
        raise RuntimeError(f"{BANNER_MATERIAL}: parameters missing after the build: {missing}")
    return {"action": action, "path": BANNER_MATERIAL, "graphVersion": BANNER_GRAPH_VERSION, "params": got,
            "expressions": int(mel.get_num_material_expressions(m)), "twoSided": True, "shading": "default-lit"}


def ensure_cannon(force: bool) -> dict:
    """P7c: MI_EnvCP_CannonIron (M_EnvProp child with the kit cannon's textures, desaturated / darkened) and
    SM_EnvCP_Cannon (a copy of the kit mesh, every slot on it); idempotent via a version tag."""
    eal, mel = u.EditorAssetLibrary, u.MaterialEditingLibrary
    out = {}
    kit_mesh = u.load_asset(KIT_CANNON) if eal.does_asset_exist(KIT_CANNON) else None
    master = u.load_asset(ENV_PROP_MASTER) if eal.does_asset_exist(ENV_PROP_MASTER) else None
    if kit_mesh is None or master is None:
        return {"action": "skipped", "error": f"{KIT_CANNON} or {ENV_PROP_MASTER} missing (run ue_import_env_kit.py)"}
    kit_mi = kit_mesh.get_material(0)
    mi = u.load_asset(CANNON_MI) if eal.does_asset_exist(CANNON_MI) else None
    if mi is None or force or eal.get_metadata_tag(mi, CANNON_TAG) != CANNON_MI_VERSION:
        action = "updated" if mi is not None else "created"
        if mi is None:
            folder, name = CANNON_MI.rsplit("/", 1)
            mi = u.AssetToolsHelpers.get_asset_tools().create_asset(name, folder, u.MaterialInstanceConstant,
                                                                     u.MaterialInstanceConstantFactoryNew())
        mel.set_material_instance_parent(mi, master)
        textures = {}
        for name in CANNON_TEXTURES:
            tex = mel.get_material_instance_texture_parameter_value(kit_mi, name) if kit_mi else None
            if tex is not None:
                mel.set_material_instance_texture_parameter_value(mi, name, tex)
                textures[name] = tex.get_path_name()
        if "BaseColorTexture" not in textures:
            raise RuntimeError(f"{KIT_CANNON}: its MI {kit_mi.get_path_name() if kit_mi else None} has no BaseColorTexture")
        for k, v in CANNON_LOOK["vectors"].items():
            mel.set_material_instance_vector_parameter_value(mi, k, u.LinearColor(*[float(x) for x in v]))
        for k, v in CANNON_LOOK["scalars"].items():
            mel.set_material_instance_scalar_parameter_value(mi, k, float(v))
        eal.set_metadata_tag(mi, CANNON_TAG, CANNON_MI_VERSION)
        if not eal.save_loaded_asset(mi, False):
            raise RuntimeError(f"could not save {CANNON_MI}")
        out["mi"] = {"action": action, "parent": ENV_PROP_MASTER, "kitMi": kit_mi.get_path_name() if kit_mi else None,
                     "textures": textures, **CANNON_LOOK}
    else:
        out["mi"] = {"action": "unchanged"}
    mesh = u.load_asset(CANNON_MESH) if eal.does_asset_exist(CANNON_MESH) else None
    if mesh is None or force or eal.get_metadata_tag(mesh, CANNON_TAG) != CANNON_VERSION:
        if mesh is not None:
            eal.delete_asset(CANNON_MESH)
        if not eal.duplicate_asset(KIT_CANNON, CANNON_MESH):
            raise RuntimeError(f"could not duplicate {KIT_CANNON} -> {CANNON_MESH}")
        mesh = u.load_asset(CANNON_MESH)
        for i in range(len(mesh.get_editor_property("static_materials"))):
            mesh.set_material(i, mi)
        eal.set_metadata_tag(mesh, CANNON_TAG, CANNON_VERSION)
        if not eal.save_loaded_asset(mesh, False):
            raise RuntimeError(f"could not save {CANNON_MESH}")
        out["mesh"] = {"action": "duplicated", "from": KIT_CANNON, "slots": len(mesh.get_editor_property("static_materials"))}
    else:
        out["mesh"] = {"action": "unchanged"}
    box = mesh.get_bounding_box()
    out["mesh"]["boundsUU"] = [round(box.min.x, 2), round(box.min.y, 2), round(box.min.z, 2), round(box.max.x, 2),
                               round(box.max.y, 2), round(box.max.z, 2)]
    return out


def ensure_detail_mis(force: bool) -> dict:
    """MI_EnvCP_* children of the kit MIs (DETAIL_MIS); idempotent via a version tag."""
    eal, mel = u.EditorAssetLibrary, u.MaterialEditingLibrary
    out = {}
    for path, (parent_path, scalars, vectors) in DETAIL_MIS.items():
        parent = u.load_asset(parent_path) if eal.does_asset_exist(parent_path) else None
        if parent is None:
            out[path] = {"action": "skipped", "error": f"{parent_path} missing (run ue_import_env_kit.py)"}
            continue
        mi = u.load_asset(path) if eal.does_asset_exist(path) else None
        if mi is not None and not force and eal.get_metadata_tag(mi, DETAIL_MI_TAG) == DETAIL_MI_VERSION:
            out[path] = {"action": "unchanged"}
            continue
        action = "updated" if mi is not None else "created"
        if mi is None:
            folder, name = path.rsplit("/", 1)
            mi = u.AssetToolsHelpers.get_asset_tools().create_asset(name, folder, u.MaterialInstanceConstant,
                                                                     u.MaterialInstanceConstantFactoryNew())
        mel.set_material_instance_parent(mi, parent)
        for k, v in scalars.items():
            mel.set_material_instance_scalar_parameter_value(mi, k, float(v))
        for k, v in vectors.items():
            mel.set_material_instance_vector_parameter_value(mi, k, u.LinearColor(*[float(x) for x in v[:4]]))
        eal.set_metadata_tag(mi, DETAIL_MI_TAG, DETAIL_MI_VERSION)
        if not eal.save_loaded_asset(mi, False):
            raise RuntimeError(f"could not save {path}")
        out[path] = {"action": action, "parent": parent_path, "scalars": scalars,
                     "vectors": {k: list(v[:4]) for k, v in vectors.items()}}
    return out


def run_import(p: dict, force: bool) -> bool:
    ok = True
    try:
        p["bannerMaterial"] = ensure_banner_material(force)
    except Exception as exc:
        p["bannerMaterial"] = {"action": "failed", "error": str(exc)}
        ok = False
    try:
        p["detailMis"] = ensure_detail_mis(force)
    except Exception as exc:
        p["detailMis"] = {"action": "failed", "error": str(exc)}
        ok = False
    try:
        p["cannon"] = ensure_cannon(force)
        ok = ok and p["cannon"].get("action") != "skipped"
    except Exception as exc:
        p["cannon"] = {"action": "failed", "error": str(exc)}
        ok = False
    for key, entry in p["maps"].items():
        entry["ue"] = {}
        if not entry["ok"]:
            entry["ue"]["skipped"] = "source verification failed; nothing imported for this map"
            ok = False
            continue
        for tkey, item in entry["textures"].items():
            try:
                entry["ue"][tkey] = import_texture(item, force)
            except Exception as exc:  # report and continue
                entry["ue"][tkey] = {"action": "failed", "error": str(exc)}
                ok = False
    for name, item in p["meshes"].items():
        if not item.get("verified"):
            item["ue"] = {"action": "skipped", "error": item.get("error")}
            ok = False
            continue
        try:
            item["ue"] = import_mesh(name, item, force)
        except Exception as exc:
            item["ue"] = {"action": "failed", "error": str(exc)}
            ok = False
    return ok


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n", 1)[0])
    ap.add_argument("--maps", default="sarpedon,marmoreal")
    ap.add_argument("--derived", default=None)
    ap.add_argument("--report", default=None)
    ap.add_argument("--check", action="store_true", help="verify the sources only (no UE import)")
    ap.add_argument("--force", action="store_true")
    ap.add_argument("--no-details", action="store_true", help="skip the lantern head / banner cloth meshes")
    a = ap.parse_args(argv)
    keys = [k.strip() for k in a.maps.split(",") if k.strip()]
    unknown = [k for k in keys if k not in MAPS]
    if unknown:
        print(f"unknown map key(s) {unknown}; known: {sorted(MAPS)}")
        return 2
    t0 = time.time()
    root = derived_root(a.derived)
    p = plan(keys, root, not a.no_details)
    report = {"schema": "unmatched.concept-paste-ue-import/1", "tool": "tools/art/concept_paste/ue_import_concept_paste.py",
              "mode": "check" if (a.check or u is None) else "import", "derivedRoot": root.as_posix(),
              "buildReport": rel(BUILD_REPORT), "material": MATERIAL, **p}
    ok = p["ok"]
    if report["mode"] == "import":
        ok = run_import(p, a.force) and ok
        for k in ("bannerMaterial", "detailMis", "cannon"):  # set by run_import after the report copy
            report[k] = p.get(k)
        report["engine"] = str(u.SystemLibrary.get_engine_version())
    report["ok"] = ok
    report["seconds"] = round(time.time() - t0, 1)
    text = json.dumps(report, ensure_ascii=False, indent=1)
    if a.report:
        rp = Path(a.report)
    elif u is not None:
        rp = Path(u.Paths.project_saved_dir()) / "EnvMaps" / "concept-paste-import-report.json"
    else:
        rp = None
    if rp is not None:
        rp.parent.mkdir(parents=True, exist_ok=True)
        rp.write_text(text + "\n", encoding="utf-8")
        report["reportPath"] = rp.as_posix()
    print("CONCEPT-PASTE-IMPORT-REPORT " + json.dumps(report, ensure_ascii=False))
    print(f"CONCEPT-PASTE-IMPORT-RESULT {'ok' if ok else 'failed'} mode={report['mode']} maps={','.join(keys)}")
    return 0 if ok else 1


if __name__ == "__main__":
    code = main(sys.argv[1:])
    if u is None:
        sys.exit(code)
    elif code != 0:
        raise RuntimeError("concept-paste import failed - see CONCEPT-PASTE-IMPORT-REPORT")
