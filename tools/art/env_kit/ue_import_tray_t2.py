"""ENV-MAPS track TRAY (ENV-U10): import the shared rocky tray SM_TableBase_T2 into UE (out of git, like the env kit).

Source: the headless-Blender run art/pipeline-candidates/ASSET-TABLE-BASE-001/20261001-tray-t2 (tray_t2_run.py):
  export/SM_TableBase_T2.fbx          UM_FBX_v1 (centimetres = uu, UnitScaleFactor 1.0); pivot XY = the centre of the
                                      flat top (1560 x 940 at Z -3), Z = 0 = the board play plane; long side = UE X
  export/T_TableBase_T2_{BC,N,ORM}    TILING 2K textures (CC0 Rock058 toned to the T1 skirt; UV0 is a world box
                                      projection, 180 uu per repeat): BC sRGB, N DirectX, ORM linear (R AO, G rough, B 0)
Targets (S08Diorama.h T2MeshPath / T2MaterialPath; DefaultGame.ini always cooks the folder):
  /Game/PipelineCandidates/TableBase/T2/SM_TableBase_T2      legacy FbxFactory, import_uniform_scale 1.0, normals
                                                              imported, no materials / textures from the FBX, no
                                                              collision (decor; the board keeps the click surfaces),
                                                              Nanite off, the one slot -> MI_TableBase_T2
  /Game/PipelineCandidates/TableBase/T2/T_TableBase_T2_BC    sRGB TC_Default, address Wrap (tiling UVs)
  /Game/PipelineCandidates/TableBase/T2/T_TableBase_T2_N     linear TC_Normalmap, flip_green false (DirectX), Wrap
  /Game/PipelineCandidates/TableBase/T2/T_TableBase_T2_ORM   linear TC_Masks, Wrap
  /Game/PipelineCandidates/TableBase/T2/MI_TableBase_T2      child of /Game/UM/Materials/M_UM_Figure (the decor route
                                                              of T1 MI_TableBase_Candidate and the env kit): the three
                                                              textures, TeamColor white, TeamMask T_UM_Mask_Black,
                                                              one-sided
Helpers come from ue_import_env_kit.py (same FBX options, mesh settings, master check, metadata tags), so the tray is
imported exactly like the kit props. Checks before any import: the four sources exist and their sha256 equal the run's
reports (build-report.json export.sha256, textures-report.json outputs.*.sha256); a mismatch is never imported. After
the import: bounds equal the Blender build (geometry.boundsUeUU, +-0.5 uu), triangles within 1 % of the build (UE drops
degenerate triangles), Nanite off, no simple collision, the slot on the MI, nothing foreign / numbered in the folder.
Idempotent (metadata tag EnvKitSourceSha256 per asset). Report: 'TRAYT2-IMPORT-REPORT {...}', 'TRAYT2-IMPORT-RESULT
ok|failed', written to <project>/Saved/TableBaseT2/ue-import-report.json (or --report).

P5 track B (--variant t2b, the DEFAULT since 2026-10-01): the lane K tray SM_TableBase_T2b with its moss material
M_TableBase_T2b + MI_TableBase_T2b(_<Map>) in /Game/PipelineCandidates/TableBase/T2b (see the T2b section below; the T2
rock textures are verified / imported first). S08Diorama.h prefers T2b on the map-image boards and falls back to T2 (then
T1) when it is not in the build. --variant t2 imports the T2 tray exactly as before.

Run (the editor must be CLOSED; one UE process at a time in this workflow):
  UnrealEditor-Cmd.exe <repo>/unreal/Unmatched/Unmatched.uproject -run=pythonscript
      -script="<repo>/tools/art/env_kit/ue_import_tray_t2.py [--variant t2b|t2]" -unattended -nosplash -nullrhi
Pre-check without UE (plain Python: presence + sha256 + envelope + looks, no import):
  python -B tools/art/env_kit/ue_import_tray_t2.py --check [--variant t2b|t2]
Options: --variant t2b|t2  --run <run dir>  --t2-run <T2 run dir (rock set)>  --ground-params <json>  --report <json>
         --force (re-import all)
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import ue_import_env_kit as K  # noqa: E402  (shared FBX / mesh / MI helpers; imports `unreal` when inside UE)

u = K.u
REPO = K.REPO
RUN_DEFAULT = REPO / "art" / "pipeline-candidates" / "ASSET-TABLE-BASE-001" / "20261001-tray-t2"
FOLDER = "/Game/PipelineCandidates/TableBase/T2"
MESH = "SM_TableBase_T2"
MI = "MI_TableBase_T2"
TEX = "T_TableBase_T2"
ASSETS = {"mesh": f"{FOLDER}/{MESH}", "mi": f"{FOLDER}/{MI}",
          **{f"tex:{k}": f"{FOLDER}/{TEX}_{k}" for k in K.TEXTURE_KEYS}}
BOUNDS_TOL_UU = 0.5
TRIS_TOL = 0.01


def plan(run: Path) -> dict:
    out = {"run": K.rel(run), "assets": ASSETS, "sources": {}, "ok": True, "verified": True, "reports": {}}
    reports = {}
    for name in ("build-report.json", "textures-report.json"):
        path = run / "reports" / name
        try:
            reports[name] = json.loads(path.read_text(encoding="utf-8"))
            out["reports"][name] = {"path": K.rel(path), "sha256": K.sha256_file(path),
                                    "checksPassed": reports[name].get("checks_passed")}
        except (OSError, ValueError) as exc:
            out["reports"][name] = {"path": K.rel(path), "error": f"unreadable: {exc}"}
            out["ok"] = False
    build, tex = reports.get("build-report.json", {}), reports.get("textures-report.json", {})
    want = {"fbx": (build.get("export") or {}).get("sha256")}
    want.update({k: ((tex.get("outputs") or {}).get(k) or {}).get("sha256") for k in K.TEXTURE_KEYS})
    files = {"fbx": run / "export" / f"{MESH}.fbx", **{k: run / "export" / f"{TEX}_{k}.png" for k in K.TEXTURE_KEYS}}
    for key, path in files.items():
        item = {"path": K.rel(path), "abs": str(path)}
        if not path.is_file():
            item["status"] = "missing"
            out["ok"] = False
        else:
            got = K.sha256_file(path)
            item.update(sha256=got, bytes=path.stat().st_size)
            if not want.get(key):
                item["status"] = "unverified"
                out["verified"] = False
                out["ok"] = False  # the tray is always built with its reports: no report = not this run's file
            elif got == want[key]:
                item["status"] = "verified"
            else:
                item.update(status="mismatch", expected=want[key], error="sha256 differs from the run's report")
                out["ok"] = False
        out["sources"][key] = item
    geo = build.get("geometry") or {}
    out["expected"] = {"boundsUeUU": geo.get("boundsUeUU"), "triangles": geo.get("triangles"),
                       "flatTop": geo.get("flatTop"), "checksPassed": build.get("checks_passed")}
    if build.get("checks_passed") is False:
        out["ok"] = False
        out["error"] = "the build report has failing checks"
    return out


# ------------------------------------------------------------------------------------------------ UE side
def texture_wanted(key: str) -> dict:
    wanted = K.texture_settings(key, "directx")
    wanted.update({"address_x": u.TextureAddress.TA_WRAP, "address_y": u.TextureAddress.TA_WRAP})
    return wanted


def import_texture(src: dict, asset: str, key: str, force: bool) -> dict:
    """ue_import_env_kit.import_texture + Wrap addressing (the T2 UVs tile)."""
    eal = u.EditorAssetLibrary
    wanted = texture_wanted(key)
    texture = u.load_asset(asset) if eal.does_asset_exist(asset) else None
    if (texture is not None and not force and eal.get_metadata_tag(texture, K.SHA_TAG) == src["sha256"]
            and K.settings_match(texture, wanted)):
        return {"action": "unchanged", **K.describe_texture(texture)}
    action = "reimported" if texture is not None else "imported"
    if texture is None or force or eal.get_metadata_tag(texture, K.SHA_TAG) != src["sha256"]:
        folder, leaf = K.split(asset)
        task = u.AssetImportTask()
        task.filename = src["abs"]
        task.destination_path = folder
        task.destination_name = leaf
        task.automated = True
        task.replace_existing = True
        task.save = False
        u.AssetToolsHelpers.get_asset_tools().import_asset_tasks([task])
        texture = u.load_asset(asset)
    else:
        action = "settings"
    if texture is None or not isinstance(texture, u.Texture2D):
        raise RuntimeError(f"import of {src['path']} did not produce the texture {asset}")
    for prop, value in wanted.items():
        texture.set_editor_property(prop, value)
    eal.set_metadata_tag(texture, K.SHA_TAG, src["sha256"])
    if not eal.save_loaded_asset(texture, False):
        raise RuntimeError(f"could not save {asset}")
    if not K.settings_match(texture, wanted):
        raise RuntimeError(f"{asset}: settings did not stick: {K.describe_texture(texture)}")
    return {"action": action, **K.describe_texture(texture),
            "address": [str(texture.get_editor_property("address_x")), str(texture.get_editor_property("address_y"))]}


def ensure_instance(master, textures: dict, mask) -> dict:
    eal, mel = u.EditorAssetLibrary, u.MaterialEditingLibrary
    path = ASSETS["mi"]
    mi = u.load_asset(path) if eal.does_asset_exist(path) else None
    action = "updated"
    if mi is None:
        folder, leaf = K.split(path)
        mi = u.AssetToolsHelpers.get_asset_tools().create_asset(leaf, folder, u.MaterialInstanceConstant,
                                                                 u.MaterialInstanceConstantFactoryNew())
        action = "created"
    if mi is None:
        raise RuntimeError(f"could not create {path}")
    white = u.LinearColor(1.0, 1.0, 1.0, 1.0)

    def rgba(c) -> tuple:
        return tuple(round(float(getattr(c, k)), 5) for k in ("r", "g", "b", "a"))

    def current() -> dict:
        parent = mi.get_editor_property("parent")
        state = {"parent": parent.get_path_name() if parent else None,
                 K.PARAM_TEAM: rgba(mel.get_material_instance_vector_parameter_value(mi, K.PARAM_TEAM))}
        for key, param in K.PARAMS.items():
            bound = mel.get_material_instance_texture_parameter_value(mi, param)
            state[param] = bound.get_path_name() if bound else None
        if mask is not None:
            bound = mel.get_material_instance_texture_parameter_value(mi, K.PARAM_MASK)
            state[K.PARAM_MASK] = bound.get_path_name() if bound else None
        return state

    want = {"parent": master.get_path_name(), K.PARAM_TEAM: rgba(white)}
    want.update({param: textures[key].get_path_name() for key, param in K.PARAMS.items()})
    if mask is not None:
        want[K.PARAM_MASK] = mask.get_path_name()
    if action == "updated" and current() == want:
        return {"action": "unchanged", "path": path, "params": {k: str(v) for k, v in want.items()}}
    mel.set_material_instance_parent(mi, master)
    for key, param in K.PARAMS.items():
        mel.set_material_instance_texture_parameter_value(mi, param, textures[key])
    if mask is not None:
        mel.set_material_instance_texture_parameter_value(mi, K.PARAM_MASK, mask)
    mel.set_material_instance_vector_parameter_value(mi, K.PARAM_TEAM, white)
    mel.update_material_instance(mi)
    if not eal.save_loaded_asset(mi, False):
        raise RuntimeError(f"could not save {path}")
    got = current()
    if got != want:
        raise RuntimeError(f"{path}: parameters did not bind: {got}")
    return {"action": action, "path": path, "params": {k: str(v) for k, v in want.items()}}


def measure(mesh, expected: dict) -> dict:
    sms = K.sm_api()
    box = mesh.get_bounding_box()
    mn, mx = box.min, box.max
    out = {"boundsMin": [round(mn.x, 3), round(mn.y, 3), round(mn.z, 3)],
           "boundsMax": [round(mx.x, 3), round(mx.y, 3), round(mx.z, 3)],
           "sizeUU": [round(mx.x - mn.x, 3), round(mx.y - mn.y, 3), round(mx.z - mn.z, 3)],
           "nanite": bool(mesh.get_editor_property("nanite_settings").get_editor_property("enabled")),
           "simpleCollision": int(sms.get_simple_collision_count(mesh)),
           "slots": [mesh.get_material(i).get_path_name() if mesh.get_material(i) else None
                     for i in range(len(mesh.get_editor_property("static_materials")))]}
    try:
        out["trianglesLod0"] = int(mesh.get_num_triangles(0))
    except Exception:  # noqa: BLE001 - not exposed in every engine version
        out["trianglesLod0"] = None
    try:
        out["verticesLod0"] = int(sms.get_number_verts(mesh, 0))
    except Exception as exc:  # noqa: BLE001 - measurement only
        out["verticesLod0"] = f"n/a ({exc})"
    out.update(compare(out, expected))
    return out


def compare(measured: dict, expected: dict) -> dict:
    """World-free (also exercised by --check): bounds against the Blender build, triangle drift."""
    res = {}
    b = expected.get("boundsUeUU") or {}
    if b.get("min") and b.get("max"):
        delta = [round(measured["boundsMin"][i] - b["min"][i], 3) for i in range(3)] + \
                [round(measured["boundsMax"][i] - b["max"][i], 3) for i in range(3)]
        res["bounds"] = {"blenderMin": b["min"], "blenderMax": b["max"], "deltaUU": delta,
                         "ok": all(abs(d) <= BOUNDS_TOL_UU for d in delta)}
    t = expected.get("triangles")
    if t and isinstance(measured.get("trianglesLod0"), int):
        drift = abs(measured["trianglesLod0"] - t) / t
        res["triangles"] = {"blender": t, "ue": measured["trianglesLod0"], "drift": round(drift, 5),
                            "ok": drift <= TRIS_TOL}
    return res


def run_import(p: dict, force: bool) -> tuple[dict, bool]:
    eal = u.EditorAssetLibrary
    result: dict = {}
    master = u.load_asset(K.MASTER)
    if master is None:
        return {"error": f"master {K.MASTER} missing (tools/tripo-pipeline/um_masters.py builds it)"}, False
    result["master"] = K.check_master(master)
    if result["master"]["missing"]:
        return result, False
    mask = u.load_asset(K.MASK_NONE) if eal.does_asset_exist(K.MASK_NONE) else None
    result["teamMask"] = K.MASK_NONE if mask is not None else "missing (TeamColor white keeps BC unchanged anyway)"
    before = K.folder_listing(FOLDER) if eal.does_directory_exist(FOLDER) else []
    ok = True
    try:
        textures = {}
        result["textures"] = {}
        for key in K.TEXTURE_KEYS:
            result["textures"][key] = import_texture(p["sources"][key], ASSETS[f"tex:{key}"], key, force)
            textures[key] = u.load_asset(ASSETS[f"tex:{key}"])
        result["materialInstance"] = ensure_instance(master, textures, mask)
        mi = u.load_asset(ASSETS["mi"])
        fbx = p["sources"]["fbx"]
        mesh = u.load_asset(ASSETS["mesh"]) if eal.does_asset_exist(ASSETS["mesh"]) else None
        if (mesh is not None and not force and eal.get_metadata_tag(mesh, K.SHA_TAG) == fbx["sha256"]
                and eal.get_metadata_tag(mesh, K.SCALE_TAG) == "1"):
            result["mesh"] = {"action": "unchanged"}
        else:
            result["mesh"] = dict(K.import_mesh(fbx, ASSETS["mesh"], 1.0),
                                  action="reimported" if mesh is not None else "imported")
            mesh = u.load_asset(ASSETS["mesh"])
            if mesh is None or not isinstance(mesh, u.StaticMesh):
                raise RuntimeError(f"{ASSETS['mesh']} is not a static mesh after the import")
            eal.set_metadata_tag(mesh, K.SHA_TAG, fbx["sha256"])
            eal.set_metadata_tag(mesh, K.SCALE_TAG, "1")
        settings = K.ensure_mesh_settings(mesh, mi)
        result["mesh"]["settingsChanged"] = settings["changes"]
        if settings["changes"] or result["mesh"]["action"] != "unchanged":
            if not eal.save_loaded_asset(mesh, False):
                raise RuntimeError(f"could not save {ASSETS['mesh']}")
        m = result["measure"] = measure(mesh, p["expected"])
        problems = []
        if m["nanite"]:
            problems.append("nanite still on")
        if m["simpleCollision"]:
            problems.append("simple collision left")
        if not m["slots"] or any(s != mi.get_path_name() for s in m["slots"]):
            problems.append("material slots not on the MI")
        if not (m.get("bounds") or {}).get("ok"):
            problems.append(f"bounds differ from the Blender build: {m.get('bounds')}")
        if (m.get("triangles") or {}).get("ok") is False:
            problems.append(f"triangles differ from the build by > {TRIS_TOL:.0%}: {m.get('triangles')}")
        result["problems"] = problems
        ok = not problems
    except Exception as exc:  # report it
        result["error"] = f"{type(exc).__name__}: {exc}"
        ok = False
    after = K.folder_listing(FOLDER) if eal.does_directory_exist(FOLDER) else []
    planned = set(ASSETS.values())
    result["folder"] = {"path": FOLDER, "before": before, "after": after,
                        "foreign": [a for a in after if a not in planned],
                        "numberedDuplicates": [a for a in after if re.search(r"_\d+$", a)],
                        "missing": sorted(planned - set(after))}
    ok = ok and not result["folder"]["missing"] and not result["folder"]["numberedDuplicates"]
    return result, ok


# ================================================================================================ T2b (P5 track B)
# The chunky shared tray of lane K (art/pipeline-candidates/ASSET-TABLE-BASE-001/20261001-tray-t2b, tray_t2b via
# tools/art/env_kit/run_k_assets.py): SM_TableBase_T2b + its moss detail T_TableBase_T2b_Moss_{BC,N}; the rock set is the
# T2 one (T_TableBase_T2_{BC,N,ORM} in the T2 folder, imported / verified from the T2 run first). Material:
#   M_TableBase_T2b  (lit, opaque, one-sided) = the T2 rock graph of M_UM_Figure (BC, DirectX N, ORM R/G/B ->
#                    AO / roughness / metallic) + a moss lerp by VertexColor.R (lane K 'Col': R moss mask on the upper lip,
#                    G per-chunk random 0..1, B depth below the top 0..1):
#     M        = TrayMoss: saturate((R * MossAmount + (luma(MossBC) - 0.35) * MossBreakup - 0.5) * MossContrast + 0.5)
#                * saturate(R * MossAmount * 4)            (0 everywhere at MossAmount 0)
#     albedo   = lerp(BC * RockTint * (1 + ChunkVariation * (G - 0.5) * 2), MossBC * MossTint, M), petals (PetalColor.rgb,
#                density PetalColor.a * M, one jittered ellipse per PetalSizeUU cell of UV0 * UVTileUU), x lerp(1,
#                DepthTint.rgb, B * DepthTint.a)
#     normal   = lerp((0,0,1), lerp(N, MossN, M), NormalStrength);  roughness = lerp(max(ORM.g * RockRoughScale,
#                RockRoughMin), MossRoughness, M);  metallic = ORM.b * (1 - M);  AO = ORM.r
#     moss UV  = UV0 * MossTileScale (UV0 = the world box projection of the build, 180 uu per repeat)
#   At TRAY_LOOK_NEUTRAL (MossAmount 0, white tints, variation 0, depth / petal alpha 0) the output equals M_UM_Figure at
#   its neutral defaults with the T2 textures = the T2 look.
#   MI_TableBase_T2b            ground-params.json 'trayLook.defaults' (the mesh slot; any map without its own MI)
#   MI_TableBase_T2b_<Map>      defaults + maps.<key>.trayLook (Marmoreal moss + petals, Sarpedon damp dark rock); the board
#                               actor picks it (S08Diorama::LoadTrayT2Material), the Sarpedon waterfall lip uses it too.
# Mesh: legacy FbxFactory, scale 1, normals imported, vertex colours REPLACE (the Col masks drive the moss), no collision,
# Nanite off, slot -> MI_TableBase_T2b. Checks: bounds = the build (+-0.5 uu), triangles within 1 %, vertex colours present,
# the S08Diorama.h T2b envelope (top 780 x 470 at Z -3, overhang <= 40, lip top <= 2, depth 180..230 uu).
RUN_T2B_DEFAULT = REPO / "art" / "pipeline-candidates" / "ASSET-TABLE-BASE-001" / "20261001-tray-t2b"
GROUND_PARAMS_DEFAULT = REPO / "art" / "pipeline-candidates" / "ASSET-ENV-KIT-001" / "ground" / "ground-params.json"
T2B_FOLDER = "/Game/PipelineCandidates/TableBase/T2b"
T2B_MESH = "SM_TableBase_T2b"
T2B_MASTER_NAME = "M_TableBase_T2b"
T2B_MI = "MI_TableBase_T2b"
T2B_TEX = "T_TableBase_T2b_Moss"
T2B_TEX_KEYS = ("BC", "N")
T2B_MAPS = {"marmoreal": "Marmoreal", "sarpedon": "Sarpedon"}
T2B_ASSETS = {"mesh": f"{T2B_FOLDER}/{T2B_MESH}", "master": f"{T2B_FOLDER}/{T2B_MASTER_NAME}",
              "mi": f"{T2B_FOLDER}/{T2B_MI}",
              **{f"mi:{k}": f"{T2B_FOLDER}/{T2B_MI}_{v}" for k, v in T2B_MAPS.items()},
              **{f"tex:Moss_{k}": f"{T2B_FOLDER}/{T2B_TEX}_{k}" for k in T2B_TEX_KEYS}}
T2B_GRAPH_TAG = "TrayT2bGraphVersion"
T2B_GRAPH_VERSION = "1"
T2B_VC_TAG = "TrayT2bVertexColors"
# mirrors S08Diorama.h (T2TopHalfX / T2TopHalfY, TopZ, T2bMaxOverhangUU, T2LipTopZMax, T2bMinDepthUU / T2bMaxDepthUU)
T2B_ENVELOPE = {"topHalf": (780.0, 470.0), "topZ": -3.0, "maxOverhangUU": 40.0, "lipTopZMax": 2.0,
                "depthUU": (180.0, 230.0)}
TEX_PARAMS_T2B = {"BC": "BaseColorTexture", "N": "NormalTexture", "ORM": "ORMTexture",
                  "Moss_BC": "MossBaseColorTexture", "Moss_N": "MossNormalTexture"}
TRAY_LOOK_SCALARS = ("MossAmount", "MossContrast", "MossBreakup", "MossTileScale", "MossRoughness", "RockRoughScale",
                     "RockRoughMin", "ChunkVariation", "PetalSizeUU", "UVTileUU", "NormalStrength")
TRAY_LOOK_VECTORS = ("MossTint", "RockTint", "DepthTint", "PetalColor")
TRAY_LOOK_NEUTRAL = {"MossTint": (1.0, 1.0, 1.0, 1.0), "MossAmount": 0.0, "MossContrast": 3.0, "MossBreakup": 0.6,
                     "MossTileScale": 1.5, "MossRoughness": 0.85, "RockTint": (1.0, 1.0, 1.0, 1.0),
                     "RockRoughScale": 1.0, "RockRoughMin": 0.0, "ChunkVariation": 0.0,
                     "DepthTint": (1.0, 1.0, 1.0, 0.0), "PetalColor": (0.87, 0.4, 0.51, 0.0), "PetalSizeUU": 6.0,
                     "UVTileUU": 180.0, "NormalStrength": 1.0}

HLSL_TRAY_MOSS = """// P5 M_TableBase_T2b: the moss mask from VertexColor.R (lane K: moss on the upper lip), broken up by the moss texture
float luma = dot(MossBC, float3(0.2126, 0.7152, 0.0722));
float raw = saturate(VC.r) * MossAmount;
float m = saturate((raw + (luma - 0.35) * MossBreakup - 0.5) * max(MossContrast, 0.01) + 0.5);
return m * saturate(raw * 4.0);
"""
HLSL_TRAY_ALBEDO = """// P5 M_TableBase_T2b: rock (per-chunk variation by VC.g) -> moss by M, petals in the moss, depth darkening by VC.b
struct FTrayFns {
  float Hash12(float2 p) {
    float3 p3 = frac(float3(p.xyx) * 0.1031);
    p3 += dot(p3, p3.yzx + 33.33);
    return frac((p3.x + p3.y) * p3.z);
  }
};
FTrayFns F;
float3 rock = Rock * RockTint.rgb * max(1.0 + ChunkVariation * (saturate(VC.g) - 0.5) * 2.0, 0.0);
float3 c = lerp(rock, Moss * MossTint.rgb, M);
if (PetalColor.a > 0.0) {
  float2 q = UV * max(UVTileUU, 1.0) / max(PetalSizeUU, 0.5);
  float2 b = floor(q);
  float pet = 0.0;
  for (int dy = -1; dy <= 1; ++dy) {
    for (int dx = -1; dx <= 1; ++dx) {
      float2 cc = b + float2(dx, dy);
      float2 j = float2(F.Hash12(cc), F.Hash12(cc + float2(19.19, 7.7)));
      float pick = F.Hash12(cc + float2(47.3, 11.1));
      float ang = F.Hash12(cc + float2(3.1, 91.7)) * 6.2831853;
      float2 o = q - (cc + 0.15 + 0.7 * j);
      float2 l = float2(o.x * cos(ang) + o.y * sin(ang), -o.x * sin(ang) + o.y * cos(ang));
      float e = (l.x / 0.36) * (l.x / 0.36) + (l.y / 0.2) * (l.y / 0.2);
      pet = max(pet, saturate((1.0 - e) / 0.45) * (pick < PetalColor.a * M ? 1.0 : 0.0));
    }
  }
  c = lerp(c, PetalColor.rgb, pet);
}
c *= lerp(float3(1.0, 1.0, 1.0), DepthTint.rgb, saturate(VC.b) * DepthTint.a);
return max(c, 0.0);
"""
HLSL_TRAY_NORMAL = "return lerp(float3(0.0, 0.0, 1.0), lerp(RockN, MossN, M), NormalStrength);"
HLSL_TRAY_ROUGH = "return saturate(lerp(max(ORM.g * RockRoughScale, RockRoughMin), MossRoughness, M));"
HLSL_TRAY_METAL = "return ORM.b * (1.0 - M);"
HLSL_TRAY_MOSS_UV = "return UV * MossTileScale;"
TRAY_HLSL_INPUTS = {
    "TrayMoss": (HLSL_TRAY_MOSS, ("VC", "MossBC", "MossAmount", "MossContrast", "MossBreakup")),
    "TrayAlbedo": (HLSL_TRAY_ALBEDO, ("Rock", "Moss", "M", "VC", "UV", "RockTint", "MossTint", "ChunkVariation",
                                      "DepthTint", "PetalColor", "PetalSizeUU", "UVTileUU")),
    "TrayNormal": (HLSL_TRAY_NORMAL, ("RockN", "MossN", "M", "NormalStrength")),
    "TrayRoughness": (HLSL_TRAY_ROUGH, ("ORM", "M", "RockRoughScale", "RockRoughMin", "MossRoughness")),
    "TrayMetallic": (HLSL_TRAY_METAL, ("ORM", "M")),
    "TrayMossUV": (HLSL_TRAY_MOSS_UV, ("UV", "MossTileScale")),
}


def tray_look(params: dict, key: str | None) -> dict:
    """The MI parameters of MI_TableBase_T2b (key None) or MI_TableBase_T2b_<Map>: TRAY_LOOK_NEUTRAL <- ground-params
    'trayLook.defaults' <- 'maps.<key>.trayLook' (vectors padded to RGBA: tints a = 1). Raises ValueError on an
    unknown name or a bad value (the run never imports a half-valid look)."""
    look = dict(TRAY_LOOK_NEUTRAL)
    layers = [(params.get("trayLook") or {}).get("defaults") or {}]
    if key is not None:
        layers.append((params.get("maps") or {}).get(key, {}).get("trayLook") or {})
    for layer in layers:
        for name, value in layer.items():
            if name in ("note", "role"):
                continue
            if name in TRAY_LOOK_SCALARS:
                if isinstance(value, bool) or not isinstance(value, (int, float)) or value != value:
                    raise ValueError(f"trayLook {name}: {value!r} is not a number")
                look[name] = float(value)
            elif name in TRAY_LOOK_VECTORS:
                if (not isinstance(value, list) or len(value) not in (3, 4)
                        or not all(isinstance(v, (int, float)) and not isinstance(v, bool) for v in value)):
                    raise ValueError(f"trayLook {name}: {value!r} is not [r, g, b(, a)]")
                look[name] = tuple(float(v) for v in value) + ((1.0,) if len(value) == 3 else ())
            else:
                raise ValueError(f"trayLook: unknown parameter {name!r}")
    return look


def tray_moss_cpu(vc_r, moss_luma, look: dict):
    """CPU mirror of TrayMoss (numpy or float)."""
    import numpy as np
    raw = np.clip(vc_r, 0.0, 1.0) * look["MossAmount"]
    m = np.clip((raw + (moss_luma - 0.35) * look["MossBreakup"] - 0.5) * max(look["MossContrast"], 0.01) + 0.5, 0, 1)
    return m * np.clip(raw * 4.0, 0.0, 1.0)


def tray_albedo_cpu(rock, moss, vc, look: dict):
    """CPU mirror of TrayAlbedo without the petals (rock, moss: (..., 3) linear; vc: (..., 3) R moss, G chunk, B depth)."""
    import numpy as np
    rock, moss, vc = (np.asarray(a, float) for a in (rock, moss, vc))
    luma = (moss * np.array([0.2126, 0.7152, 0.0722])).sum(-1)
    m = tray_moss_cpu(vc[..., 0], luma, look)[..., None]
    var = np.maximum(1.0 + look["ChunkVariation"] * (np.clip(vc[..., 1:2], 0, 1) - 0.5) * 2.0, 0.0)
    c = rock * np.array(look["RockTint"][:3]) * var
    c = c * (1 - m) + moss * np.array(look["MossTint"][:3]) * m
    d = np.clip(vc[..., 2:3], 0, 1) * look["DepthTint"][3]
    c = c * (1 - d + d * np.array(look["DepthTint"][:3]))
    return np.maximum(c, 0.0)


def envelope_check(bmin: list, bmax: list) -> dict:
    """World-free: bounds (mesh space, UE uu) against T2B_ENVELOPE (the S08Diorama.h T2b constants)."""
    e = T2B_ENVELOPE
    hx, hy = e["topHalf"]
    over = max(bmax[0] - hx, -hx - bmin[0], bmax[1] - hy, -hy - bmin[1])
    depth = e["topZ"] - bmin[2]
    out = {"overhangUU": round(over, 3), "lipTopZ": round(bmax[2], 3), "depthUU": round(depth, 3),
           "coversTop": bmin[0] <= -hx and bmax[0] >= hx and bmin[1] <= -hy and bmax[1] >= hy,
           "centred": abs(bmin[0] + bmax[0]) <= 1.0 and abs(bmin[1] + bmax[1]) <= 1.0}
    out["ok"] = (out["coversTop"] and out["centred"] and over <= e["maxOverhangUU"]
                 and e["topZ"] <= bmax[2] <= e["lipTopZMax"] + 0.5
                 and e["depthUU"][0] - 0.5 <= depth <= e["depthUU"][1] + 0.5)
    return out


def plan_t2b(run: Path, t2_run: Path, ground_params: Path) -> dict:
    """Sources of T2b (FBX + moss PNGs against the run's reports), the T2 rock set (plan(t2_run)), the looks."""
    out = {"variant": "t2b", "run": K.rel(run), "assets": T2B_ASSETS, "sources": {}, "ok": True, "reports": {}}
    reports = {}
    for name in ("build-report.json", "textures-report.json"):
        path = run / "reports" / name
        try:
            reports[name] = json.loads(path.read_text(encoding="utf-8"))
            out["reports"][name] = {"path": K.rel(path), "sha256": K.sha256_file(path),
                                    "checksPassed": reports[name].get("checks_passed")}
        except (OSError, ValueError) as exc:
            out["reports"][name] = {"path": K.rel(path), "error": f"unreadable: {exc}"}
            out["ok"] = False
    build, tex = reports.get("build-report.json", {}), reports.get("textures-report.json", {})
    exp = next((e for e in build.get("exports") or [] if e.get("name") == T2B_MESH), {})
    outs = tex.get("outputs") or {}
    want = {"fbx": exp.get("sha256"),
            **{f"Moss_{k}": (outs.get(f"{T2B_TEX}_{k}.png") or {}).get("sha256") for k in T2B_TEX_KEYS}}
    files = {"fbx": run / "export" / f"{T2B_MESH}.fbx",
             **{f"Moss_{k}": run / "export" / f"{T2B_TEX}_{k}.png" for k in T2B_TEX_KEYS}}
    for key, path in files.items():
        item = {"path": K.rel(path), "abs": str(path)}
        if not path.is_file():
            item["status"] = "missing"
            out["ok"] = False
        else:
            got = K.sha256_file(path)
            item.update(sha256=got, bytes=path.stat().st_size)
            if not want.get(key):
                item["status"] = "unverified"
                out["ok"] = False
            elif got == want[key]:
                item["status"] = "verified"
            else:
                item.update(status="mismatch", expected=want[key], error="sha256 differs from the run's report")
                out["ok"] = False
        out["sources"][key] = item
    geo = build.get("geometry") or {}
    out["expected"] = {"boundsUeUU": geo.get("boundsUeUU"), "triangles": geo.get("triangles"),
                       "checksPassed": build.get("checks_passed"), "vertexColors": "Col (R moss, G chunk, B depth)"}
    b = geo.get("boundsUeUU") or {}
    out["envelope"] = envelope_check(b["min"], b["max"]) if b.get("min") and b.get("max") else {"ok": False}
    if build.get("checks_passed") is not True:
        out["ok"] = False
        out["error"] = "the build report is missing or has failing checks"
    if not out["envelope"].get("ok"):
        out["ok"] = False
        out["error"] = f"the build is outside the S08Diorama.h T2b envelope: {out['envelope']}"
    rock = plan(t2_run)
    out["rock"] = {"run": rock["run"], "ok": rock["ok"], "sources": {k: rock["sources"][k] for k in K.TEXTURE_KEYS}}
    out["ok"] = out["ok"] and all(rock["sources"][k].get("status") == "verified" for k in K.TEXTURE_KEYS)
    try:
        gp = json.loads(Path(ground_params).read_text(encoding="utf-8"))
        out["looks"] = {"mi": tray_look(gp, None), **{f"mi:{k}": tray_look(gp, k) for k in T2B_MAPS}}
        out["groundParams"] = {"path": K.rel(Path(ground_params)), "sha256": K.sha256_file(Path(ground_params))}
    except (OSError, ValueError) as exc:
        out["looks"] = {"error": f"{type(exc).__name__}: {exc}"}
        out["ok"] = False
    return out


# ------------------------------------------------------------------------------------------------ T2b, UE side
def build_t2b_master(textures: dict, force: bool) -> dict:
    """M_TableBase_T2b (graph above). textures = {BC, N, ORM, Moss_BC, Moss_N: Texture2D} (the sampler defaults)."""
    import ue_import_env_ground as G  # noqa: E402  (shared material-graph helper; `unreal` is loaded here)
    eal, mel = u.EditorAssetLibrary, u.MaterialEditingLibrary
    path = T2B_ASSETS["master"]
    material = u.load_asset(path) if eal.does_asset_exist(path) else None
    if material is not None and not force and eal.get_metadata_tag(material, T2B_GRAPH_TAG) == T2B_GRAPH_VERSION:
        return {"action": "unchanged", "path": path, "graphVersion": T2B_GRAPH_VERSION}
    action = "rebuilt" if material is not None else "created"
    if material is None:
        material = u.AssetToolsHelpers.get_asset_tools().create_asset(T2B_MASTER_NAME, T2B_FOLDER, u.Material,
                                                                      u.MaterialFactoryNew())
    if material is None:
        raise RuntimeError(f"could not create {path}")
    mel.delete_all_material_expressions(material)
    material.set_editor_property("shading_model", u.MaterialShadingModel.MSM_DEFAULT_LIT)
    material.set_editor_property("blend_mode", u.BlendMode.BLEND_OPAQUE)
    material.set_editor_property("two_sided", False)
    g = G._Graph(material)
    cmot, st, ssm = u.CustomMaterialOutputType, u.MaterialSamplerType, u.SamplerSourceMode
    uv = g.expr(u.MaterialExpressionTextureCoordinate, -2600)
    uv.set_editor_property("coordinate_index", 0)
    vc = g.expr(u.MaterialExpressionVertexColor, -2600)
    sca = {n: g.scalar(n, TRAY_LOOK_NEUTRAL[n]) for n in TRAY_LOOK_SCALARS}
    vec = {n: g.vector(n, TRAY_LOOK_NEUTRAL[n]) for n in TRAY_LOOK_VECTORS}
    moss_uv = g.custom("TrayMossUV", cmot.CMOT_FLOAT2, TRAY_HLSL_INPUTS["TrayMossUV"][1], HLSL_TRAY_MOSS_UV, -2200, 600)
    g.wire(moss_uv, {"UV": (uv, ""), "MossTileScale": (sca["MossTileScale"], "")})
    smp = {}
    for i, (key, stype) in enumerate((("BC", st.SAMPLERTYPE_COLOR), ("N", st.SAMPLERTYPE_NORMAL),
                                      ("ORM", st.SAMPLERTYPE_MASKS), ("Moss_BC", st.SAMPLERTYPE_COLOR),
                                      ("Moss_N", st.SAMPLERTYPE_NORMAL))):
        node = g.sample(TEX_PARAMS_T2B[key], stype, textures[key], ssm.SSM_FROM_TEXTURE_ASSET, -1800, -400 + 300 * i)
        g.connect(moss_uv if key.startswith("Moss") else uv, "", node, "UVs")
        smp[key] = node
    src = {"VC": (vc, ""), "UV": (uv, ""), "MossBC": (smp["Moss_BC"], "RGB"), "Rock": (smp["BC"], "RGB"),
           "Moss": (smp["Moss_BC"], "RGB"), "RockN": (smp["N"], "RGB"), "MossN": (smp["Moss_N"], "RGB"),
           "ORM": (smp["ORM"], "RGB")}
    src.update({n: (sca[n], "") for n in TRAY_LOOK_SCALARS})
    src.update({n: (vec[n], "RGBA") for n in TRAY_LOOK_VECTORS})
    moss = g.custom("TrayMoss", cmot.CMOT_FLOAT1, TRAY_HLSL_INPUTS["TrayMoss"][1], HLSL_TRAY_MOSS, -1300, 700)
    g.wire(moss, {p_: src[p_] for p_ in TRAY_HLSL_INPUTS["TrayMoss"][1]})
    src["M"] = (moss, "")
    nodes = {}
    for desc, out_type, y in (("TrayAlbedo", cmot.CMOT_FLOAT3, -300), ("TrayNormal", cmot.CMOT_FLOAT3, 0),
                              ("TrayRoughness", cmot.CMOT_FLOAT1, 300), ("TrayMetallic", cmot.CMOT_FLOAT1, 600)):
        code, pins = TRAY_HLSL_INPUTS[desc]
        node = g.custom(desc, out_type, pins, code, -800, y)
        g.wire(node, {p_: src[p_] for p_ in pins})
        nodes[desc] = node
    mel.connect_material_property(nodes["TrayAlbedo"], "", u.MaterialProperty.MP_BASE_COLOR)
    mel.connect_material_property(nodes["TrayNormal"], "", u.MaterialProperty.MP_NORMAL)
    mel.connect_material_property(nodes["TrayRoughness"], "", u.MaterialProperty.MP_ROUGHNESS)
    mel.connect_material_property(nodes["TrayMetallic"], "", u.MaterialProperty.MP_METALLIC)
    mel.connect_material_property(smp["ORM"], "R", u.MaterialProperty.MP_AMBIENT_OCCLUSION)
    mel.recompile_material(material)
    eal.set_metadata_tag(material, T2B_GRAPH_TAG, T2B_GRAPH_VERSION)
    if not eal.save_loaded_asset(material, False):
        raise RuntimeError(f"could not save {path}")
    params = {"texture": sorted(str(n) for n in mel.get_texture_parameter_names(material)),
              "vector": sorted(str(n) for n in mel.get_vector_parameter_names(material)),
              "scalar": sorted(str(n) for n in mel.get_scalar_parameter_names(material))}
    missing = ([p_ for p_ in TEX_PARAMS_T2B.values() if p_ not in params["texture"]]
               + [p_ for p_ in TRAY_LOOK_VECTORS if p_ not in params["vector"]]
               + [p_ for p_ in TRAY_LOOK_SCALARS if p_ not in params["scalar"]])
    if missing:
        raise RuntimeError(f"{path}: parameters missing after the build: {missing}")
    return {"action": action, "path": path, "graphVersion": T2B_GRAPH_VERSION,
            "expressions": int(mel.get_num_material_expressions(material)), "params": params}


def t2b_mi_want(textures: dict, look: dict) -> dict:
    return {"tex": {TEX_PARAMS_T2B[k]: t for k, t in textures.items()},
            "scalar": {n: float(look[n]) for n in TRAY_LOOK_SCALARS},
            "vector": {n: tuple(float(v) for v in look[n]) for n in TRAY_LOOK_VECTORS}}


def run_import_t2b(p: dict, force: bool) -> tuple[dict, bool]:
    import ue_import_env_ground as G  # noqa: E402
    eal = u.EditorAssetLibrary
    result: dict = {}
    before = K.folder_listing(T2B_FOLDER) if eal.does_directory_exist(T2B_FOLDER) else []
    ok = True
    try:
        textures, result["rockTextures"], result["textures"] = {}, {}, {}
        for key in K.TEXTURE_KEYS:  # the T2 rock set (unchanged when its sha256 tag already matches)
            result["rockTextures"][key] = import_texture(p["rock"]["sources"][key], ASSETS[f"tex:{key}"], key, force)
            textures[key] = u.load_asset(ASSETS[f"tex:{key}"])
        for key in T2B_TEX_KEYS:
            asset = T2B_ASSETS[f"tex:Moss_{key}"]
            result["textures"][f"Moss_{key}"] = import_texture(p["sources"][f"Moss_{key}"], asset, key, force)
            textures[f"Moss_{key}"] = u.load_asset(asset)
        result["master"] = build_t2b_master(textures, force)
        master = u.load_asset(T2B_ASSETS["master"])
        result["materialInstances"] = {}
        for mi_key, look in p["looks"].items():
            result["materialInstances"][mi_key] = G.ensure_instance(T2B_ASSETS[mi_key], master,
                                                                    t2b_mi_want(textures, look))
        mi = u.load_asset(T2B_ASSETS["mi"])
        fbx = p["sources"]["fbx"]
        mesh = u.load_asset(T2B_ASSETS["mesh"]) if eal.does_asset_exist(T2B_ASSETS["mesh"]) else None
        if (mesh is not None and not force and eal.get_metadata_tag(mesh, K.SHA_TAG) == fbx["sha256"]
                and eal.get_metadata_tag(mesh, T2B_VC_TAG) == "replace"):
            result["mesh"] = {"action": "unchanged"}
        else:
            result["mesh"] = dict(G.import_static_mesh(fbx["abs"], T2B_ASSETS["mesh"], "replace"),
                                  action="reimported" if mesh is not None else "imported")
            mesh = u.load_asset(T2B_ASSETS["mesh"])
            if mesh is None or not isinstance(mesh, u.StaticMesh):
                raise RuntimeError(f"{T2B_ASSETS['mesh']} is not a static mesh after the import")
            eal.set_metadata_tag(mesh, K.SHA_TAG, fbx["sha256"])
            eal.set_metadata_tag(mesh, K.SCALE_TAG, "1")
            eal.set_metadata_tag(mesh, T2B_VC_TAG, "replace")
        settings = K.ensure_mesh_settings(mesh, mi)
        result["mesh"]["settingsChanged"] = settings["changes"]
        if settings["changes"] or result["mesh"]["action"] != "unchanged":
            if not eal.save_loaded_asset(mesh, False):
                raise RuntimeError(f"could not save {T2B_ASSETS['mesh']}")
        m = result["measure"] = measure(mesh, p["expected"])
        try:
            m["hasVertexColors"] = bool(G.sm_api().has_vertex_colors(mesh))
        except Exception as exc:  # noqa: BLE001 - measurement only
            m["hasVertexColors"] = f"n/a ({type(exc).__name__})"
        m["envelope"] = envelope_check(m["boundsMin"], m["boundsMax"])
        problems = []
        if m["nanite"]:
            problems.append("nanite still on")
        if m["simpleCollision"]:
            problems.append("simple collision left")
        if not m["slots"] or any(s != mi.get_path_name() for s in m["slots"]):
            problems.append("material slots not on MI_TableBase_T2b")
        if not (m.get("bounds") or {}).get("ok"):
            problems.append(f"bounds differ from the Blender build: {m.get('bounds')}")
        if (m.get("triangles") or {}).get("ok") is False:
            problems.append(f"triangles differ from the build by > {TRIS_TOL:.0%}: {m.get('triangles')}")
        if m["hasVertexColors"] is False:
            problems.append("vertex colours missing (REPLACE): the moss mask would be 0")
        if not m["envelope"]["ok"]:
            problems.append(f"outside the S08Diorama.h T2b envelope: {m['envelope']}")
        result["problems"] = problems
        ok = not problems
    except Exception as exc:  # report it
        result["error"] = f"{type(exc).__name__}: {exc}"
        ok = False
    after = K.folder_listing(T2B_FOLDER) if eal.does_directory_exist(T2B_FOLDER) else []
    planned = set(T2B_ASSETS.values())
    result["folder"] = {"path": T2B_FOLDER, "before": before, "after": after,
                        "foreign": [a for a in after if a not in planned],
                        "numberedDuplicates": [a for a in after if re.search(r"_\d+$", a)],
                        "missing": sorted(planned - set(after))}
    ok = ok and not result["folder"]["missing"] and not result["folder"]["numberedDuplicates"]
    return result, ok


def main(argv: list | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n", 1)[0])
    ap.add_argument("--variant", choices=("t2b", "t2"), default="t2b")
    ap.add_argument("--run", default=None, help="run dir of the variant (default: the committed run)")
    ap.add_argument("--t2-run", default=str(RUN_DEFAULT), help="T2 run (the rock set of T2b)")
    ap.add_argument("--ground-params", default=str(GROUND_PARAMS_DEFAULT), help="trayLook source (T2b)")
    ap.add_argument("--report", default=None)
    ap.add_argument("--check", action="store_true", help="verify the sources only (no UE import)")
    ap.add_argument("--force", action="store_true")
    a = ap.parse_args(argv)
    started = time.time()
    t2b = a.variant == "t2b"
    if t2b:
        p = plan_t2b(Path(a.run or RUN_T2B_DEFAULT).resolve(), Path(a.t2_run).resolve(), Path(a.ground_params))
    else:
        p = plan(Path(a.run or RUN_DEFAULT).resolve())
    out = {"schema": "unmatched.table-base-t2b-ue-import/1" if t2b else "unmatched.table-base-t2-ue-import/1",
           "tool": "tools/art/env_kit/ue_import_tray_t2.py", "variant": a.variant,
           "mode": "check" if (a.check or u is None) else "import", "folder": T2B_FOLDER if t2b else FOLDER,
           "master": T2B_ASSETS["master"] if t2b else K.MASTER, "importScale": 1.0, "normalConvention": "directx",
           "vertexColors": "replace" if t2b else "ignore", "plan": p}
    ok = p["ok"]
    if out["mode"] == "import" and ok:
        out["ue"], import_ok = run_import_t2b(p, a.force) if t2b else run_import(p, a.force)
        out["engine"] = str(u.SystemLibrary.get_engine_version())
        ok = ok and import_ok
    out["ok"] = ok
    out["seconds"] = round(time.time() - started, 1)
    text = json.dumps(out, ensure_ascii=False, indent=1, default=str)
    if a.report:
        path = Path(a.report)
    elif u is not None:
        path = Path(u.Paths.project_saved_dir()) / "TableBaseT2" / ("ue-import-report-t2b.json" if t2b
                                                                    else "ue-import-report.json")
    else:
        path = None
    if path is not None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text + "\n", encoding="utf-8")
        out["reportPath"] = str(path)
    counts: dict = {}
    for item in p["sources"].values():
        counts[item["status"]] = counts.get(item["status"], 0) + 1
    print("TRAYT2-IMPORT-REPORT " + json.dumps(out, ensure_ascii=False, default=str))
    print(f"TRAYT2-IMPORT-RESULT {'ok' if ok else 'failed'} variant={a.variant} mode={out['mode']} "
          f"sources={json.dumps(counts, sort_keys=True)}")
    return 0 if ok else 1


if __name__ == "__main__":
    code = main(sys.argv[1:])
    if u is None:
        sys.exit(code)
    elif code != 0:
        raise RuntimeError("TRAYT2 import failed - see TRAYT2-IMPORT-REPORT")
