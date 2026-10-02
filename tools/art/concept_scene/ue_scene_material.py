"""ENV-MAPS P8 track B (docs/art-pipeline/ENV-P8-3D-UNDER-PAINT-TASK.md section 4 P8.2): M_EnvScene, MPC_EnvScene, the MIs.

The lit 3D island of Sarpedon (S08ConceptPaste.h, profile block conceptPaste.lit3d, layout overlay EnvLayouts/
sarpedon.scene.layout.json) is lit only by the engine. Its materials (all cooked: /Game/EnvMaps is DirectoriesToAlwaysCook):

  /Game/EnvMaps/Scene/MPC_EnvScene         scalars Live (default 0 = still: the frozen -Bench; the board actor sets 1 in live
                                           runs: wind + lantern flicker) and Emissive (default 1; -ArtPreviewLightsOff = 0)
  /Game/EnvMaps/Scene/M_EnvScene           Default Lit, opaque, one-sided; never unlit (layer B, task 0.2 #1)
  /Game/EnvMaps/Scene/M_EnvScene_Masked    the same graph, BLEND_MASKED (opacity = BC alpha x UseOpacity), two-sided:
                                           foliage cards of the pack trees / bushes
  /Game/EnvMaps/Sarpedon/Scene/MI_Env_S_<Name>        the BAKED route: one per manifest mesh (BC / N / ORM of the mesh's
                                                      UV atlas, Projected 0)
  /Game/EnvMaps/Sarpedon/Scene/MI_EnvScene_Proj_<Look> the PROJECTED route (pack meshes keep their own UVs / normals):
                                                      Projected 1, Albedo = T_Env_S_AlbedoC0 at the C0 projection of the
                                                      world position, blended by facing with the mesh's own BC (or white)
                                                      x FallbackTint
  /Game/EnvMaps/Sarpedon/Scene/MI_EnvScene_LanternGlass emissive lantern glass (EmissiveStrength x flicker x MPC Emissive)

Graph: TextureObjectParameters BC (sRGB) / N (normal map, DirectX green, tangent space) / ORM (linear: R AO, G roughness,
B metal, A emissive mask) / Albedo (sRGB, the C0 plate), sampled in Custom nodes with UV0 (the sampler type of a texture
object only matters for the editor's default-texture validation, as in M_ConceptPaste):
  SceneBase      base colour: own = BC.rgb x (BakedTint | FallbackTint by Projected); the projected route samples Albedo at
                 the C0 pixel of the absolute world position (CONCEPT_HLSL math of tools/art/concept_paste/
                 ue_concept_material.py = S08ConceptPaste::ShaderSample: CamPos / CamRight / CamUp / CamForward / CamTan,
                 homography rows HRow0..2, plate rectangle AlbedoRect in concept px [x0, y0, w, h]) and blends
                 lerp(own, Albedo x AlbedoGain, ProjStrength x facing^FacingPower x inside x in-front x Projected) with
                 facing = saturate(dot(VertexNormalWS, dir to C0)) (back faces / faces turned away keep the own colour)
  SceneNormal    lerp(flat, unpacked N, UseNormal x NormalStrength)
  SceneSurface   roughness / metallic / AO from ORM x UseORM, else the scalars Roughness / Metallic (AO 1)
  SceneEmissive  EmissiveColor x EmissiveStrength x lerp(1, ORM.a, UseEmissiveMask) x (1 + FlickerAmp x Live x noise) x
                 MPC Emissive (lantern glass: flicker only in live runs)
  SceneWind      WPO: WindDir x WindAmp x Live x h^1.5 x sway (h = height above the object pivot / WindHeight) - trees /
                 bushes in live runs only (Live = 0 in the frozen -Bench: reproducible frames)
  SceneOpacity   (masked master) lerp(1, BC.a, UseOpacity)

ENV-MAPS P9 track B (the six fixes, docs/game-design/evidence/ENV-MAPS/p8-3d-under-paint-2026-10-02/README.md "open"):
  F6 foliage wind  SceneWind gains a leaf flutter (WindFlutter uu x h, WindFlutterHz, per-vertex phase) on top of the
                   trunk sway; FOLIAGE_WIND (WindAmp 8, WindHeight 120 - the P8 G7 suggestion - + flutter) is merged over
                   the manifest's Foliage look (track A wrote WindAmp 2 there) and under scene-tune.sarpedon.json. Live
                   runs only (MPC Live = 1); the frozen -Bench (Live = 0) stays still. GRAPH_VERSION 2 / MI_VERSION 2.
  F2 frame band    MI_EnvScene_FrameWood (M_EnvScene, Planks023A BC / N / ORMH on the mesh's UV0, BakedTint = the dark
                   concept frame colour: concept band median sRGB (38, 28, 22) at C0 -> albedo ~ (50, 39, 30) by the P8
                   display / albedo ratio of the island, / the Planks023A mean) and MI_EnvScene_FrameIron (M_EnvScene, the
                   frame-002 iron textures T_MapFrame002_Iron_*: the same iron as the inner frame).
  F4 cascade       MI_EnvScene_FallsSheet / MI_EnvScene_FallsFoam: children of the P5c MI_EnvWaterfall_Sarpedon (M_EnvWaterfall
                   graph 3 - lit translucent, the Water Materials streaks, the map's water colour and night grade) with the
                   cascade's FallCard / FallFlow / FallLook (UV0: u across the sheet 0..1, v along the flow authored top ->
                   bottom in Blender, so FallCard.w = 1 as the lane K meshes; FallCard.xy = the sheet size in uu).
  Material-route MIs live at MAP_ROOT/MI_EnvScene_<Name> (MATERIAL_LOOKS). Track A names them in the manifest: a mesh
  "mi" / "slots" entry (bare names resolve to MAP_ROOT; ue_import_concept_scene.py also takes per-slot MIs in
  "meshesExistingMaterial"), optional value overrides in a top-level "materials": {"<Name>": {"scalars", "vectors"}} (or a
  "looks" entry of the same name: merged into the material MI, no projected MI_EnvScene_Proj_<Name> is made), then the
  tune file's "materials" block.

MIs: the baked list = manifest.sarpedon.json "meshes" (optional per mesh: "mi" (an explicit MI path), "material":
{"masked": bool, "scalars": {...}, "vectors": {...}}); the projected looks = manifest "looks" ([{"name", "masked", "bc"
(a UE texture path or null), "scalars", "vectors"}]) or DEFAULT_LOOKS below; MI_EnvScene_LanternGlass always. Without a
manifest (track A not done) only the masters, the MPC, the default looks and the lantern glass are built.

Run (the editor must be CLOSED - UnrealEditor-Cmd holds the project; never inside a GPU-measurement window):
  UnrealEditor-Cmd.exe <repo>/unreal/Unmatched/Unmatched.uproject -run=pythonscript
      -script="<repo>/tools/art/concept_scene/ue_scene_material.py [--force]" -unattended -nosplash -nullrhi
  (tools/art/concept_scene/ue_import_concept_scene.py calls build_all() itself after importing the textures)
Plain Python (no UE):
  python -B tools/art/concept_scene/ue_scene_material.py --check
      the names vs S08ConceptPaste.h (paths, MPC parameters, the lights-off emissive scalar), the shipped lit3d block, the
      projection mirror vs ue_concept_material.shader_sample and the P7a design pixels, the MI plan, DXC compile of every
      Custom node (tools/art/env_kit/hlsl_check.find_dxc; 'skipped' without DXC)
Idempotent: masters rebuilt only when the EnvMapsGraphVersion tag differs, MIs when EnvMapsSceneMi differs (or --force).
Report 'SCENE-MATERIAL-REPORT {...}' / 'SCENE-MATERIAL-RESULT ok|failed', <project>/Saved/EnvMaps/scene-material-report.json.
Status: предложено (the look is measured in UE frames in P8.3, not here).
"""
from __future__ import annotations

import argparse
import json
import math
import os
import re
import subprocess
import sys
import tempfile
import time
from pathlib import Path

try:  # inside UnrealEditor(-Cmd) only
    import unreal as u  # type: ignore
except ImportError:  # pragma: no cover - plain Python
    u = None
if u is not None and not hasattr(u, "EditorAssetLibrary"):  # the repo's unreal/ folder as a namespace package
    u = None

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
sys.path.insert(0, str(REPO / "tools" / "art" / "concept_paste"))
import ue_concept_material as CPM  # noqa: E402  (Camera, shader_sample, CONCEPT_HLSL: the C0 projection)

HEADER = REPO / "unreal/Unmatched/Source/Unmatched/S08/S08ConceptPaste.h"
SOURCE = REPO / "unreal/Unmatched/Source/Unmatched/S08/S08ConceptPaste.cpp"
PROFILES = REPO / "unreal/Unmatched/Config/ArtBoards/S08ArtBoardProfiles.json"
MANIFEST = HERE / "manifest.sarpedon.json"
# P8.3 tune (parameters only, journal C:/tmp/envmaps-research/p8/tune/log.md): merged last over the manifest / default
# values - {"baked": {"*" | "<Name>": {"scalars", "vectors"}}, "looks": {"*" | "<Look>": {...}}, "lanternGlass": {...},
# "lanternHead": {"parent": <MI path>, "scalars", "vectors"} (MI_EnvScene_LanternHead: a child of the P7c lantern MI)};
# "vectorsMul": {"<Vector>": [r, g, b]} multiplies a value already planned (e.g. the manifest's measured FallbackTint)
TUNE = HERE / "scene-tune.sarpedon.json"
LANTERN_HEAD = "MI_EnvScene_LanternHead"
BOARD_ID = "sarpedon-original"

SCENE_ROOT = "/Game/EnvMaps/Scene"
MAP_ROOT = "/Game/EnvMaps/Sarpedon/Scene"
MATERIAL_NAME = "M_EnvScene"
MASKED_NAME = "M_EnvScene_Masked"
MPC_NAME = "MPC_EnvScene"
MATERIAL_PATH = f"{SCENE_ROOT}/{MATERIAL_NAME}"
MASKED_PATH = f"{SCENE_ROOT}/{MASKED_NAME}"
MPC_PATH = f"{SCENE_ROOT}/{MPC_NAME}"
MPC_LIVE = "Live"
MPC_EMISSIVE = "Emissive"
MPC_DEFAULTS = {MPC_LIVE: 0.0, MPC_EMISSIVE: 1.0}
GRAPH_TAG = "EnvMapsGraphVersion"
GRAPH_VERSION = "2"  # P9 F6: SceneWind leaf flutter (WindFlutter / WindFlutterHz)
MI_TAG = "EnvMapsSceneMi"
MI_VERSION = "2"  # P9: rebuilt with the graph-2 wind / the material-route MIs
LANTERN_GLASS = "MI_EnvScene_LanternGlass"
ALBEDO_DEFAULT_RECT = (-384.0, -216.0, 2688.0, 1512.0)  # cp_bake.py contract sarpedon: rectB = the extended canvas

TEXTURES = ("BC", "N", "ORM", "Albedo")
TEXTURE_DEFAULTS = {"BC": "/Engine/EngineResources/WhiteSquareTexture", "N": "/Engine/EngineMaterials/DefaultNormal",
                    "ORM": "/Engine/EngineResources/WhiteSquareTexture", "Albedo": "/Engine/EngineResources/WhiteSquareTexture"}
SCALARS = {"Projected": 0.0, "ProjStrength": 1.0, "FacingPower": 1.0, "UseNormal": 1.0, "NormalStrength": 1.0,
           "UseORM": 1.0, "Roughness": 0.9, "RoughnessScale": 1.0, "Metallic": 0.0, "AOStrength": 1.0,
           "EmissiveStrength": 0.0, "UseEmissiveMask": 0.0, "FlickerAmp": 0.0, "FlickerHz": 4.0,
           "WindAmp": 0.0, "WindHz": 0.3, "WindHeight": 300.0, "WindFlutter": 0.0, "WindFlutterHz": 1.7,
           "UseOpacity": 0.0}
VECTORS = {"BakedTint": (1.0, 1.0, 1.0, 1.0), "FallbackTint": (1.0, 1.0, 1.0, 1.0), "AlbedoGain": (1.0, 1.0, 1.0, 1.0),
           "EmissiveColor": (1.0, 0.45, 0.12, 1.0), "WindDir": (1.0, 0.3, 0.0, 0.0),
           "CamPos": (0.0, 1557.046, 2223.692, 0.0), "CamRight": (1.0, 0.0, 0.0, 0.0),
           "CamUp": (0.0, -0.819152, 0.573576, 0.0), "CamForward": (0.0, -0.573576, -0.819152, 0.0),
           "CamTan": (0.315299, 0.177356, 1920.0, 1080.0),
           "HRow0": (1.0, 0.0, 0.0, 0.0), "HRow1": (0.0, 1.0, 0.0, 0.0), "HRow2": (0.0, 0.0, 1.0, 0.0),
           "AlbedoRect": ALBEDO_DEFAULT_RECT}
# the projected looks without a manifest "looks" list (P8.3 tunes the tints against the plate's local mean)
DEFAULT_LOOKS = [
    {"name": "Rock", "masked": False, "bc": None, "scalars": {"Roughness": 0.9}, "vectors": {"FallbackTint": (0.16, 0.15, 0.14, 1.0)}},
    {"name": "RockWet", "masked": False, "bc": None, "scalars": {"Roughness": 0.35}, "vectors": {"FallbackTint": (0.10, 0.10, 0.10, 1.0)}},
    {"name": "Wood", "masked": False, "bc": None, "scalars": {"Roughness": 0.9}, "vectors": {"FallbackTint": (0.20, 0.12, 0.07, 1.0)}},
    {"name": "Ground", "masked": False, "bc": None, "scalars": {"Roughness": 0.95}, "vectors": {"FallbackTint": (0.18, 0.15, 0.10, 1.0)}},
    {"name": "Foliage", "masked": True, "bc": None,
     "scalars": {"Roughness": 0.9, "WindAmp": 8.0, "WindHz": 0.35, "WindHeight": 120.0, "WindFlutter": 1.5,
                 "WindFlutterHz": 1.8, "UseOpacity": 1.0},
     "vectors": {"FallbackTint": (0.05, 0.08, 0.05, 1.0)}},
]
# P9 F6 (G7 foliage motion 0.16 % live in P8: WindAmp 2 uu x (h / 300)^1.5 on trees of 50..300 uu = sub-pixel): merged
# over the manifest's Foliage look (track A's measured tints stay), under the tune file. A 100 uu tree top: h = 0.83 ->
# 8 x 0.76 = 6 uu sway (~6 px at C0 / K1) + the 1.5 uu leaf flutter.
FOLIAGE_WIND = {"Foliage": {"scalars": {"WindAmp": 8.0, "WindHz": 0.35, "WindHeight": 120.0, "WindFlutter": 1.5,
                                        "WindFlutterHz": 1.8}}}

# P9 F2 / F4: the material-route MIs (fixed names, MAP_ROOT/MI_EnvScene_<Name>), see the module docstring.
PLANKS = "/Game/EnvKit/Ground/Sets/T_Ground_Planks023A"
FRAME_IRON = "/Game/EnvMaps/Frame/T_MapFrame002_Iron"
FALLS_PARENT = "/Game/EnvKit/Ground/MI_EnvWaterfall_Sarpedon"  # P5c ue_import_env_ground.py: graph 3, the map's water
FALL_PARAMS = {"scalars": ("NightEV", "NightSaturation", "RippleTileUU"),
               "vectors": ("FallCard", "FallFlow", "FallSpill", "FallShade", "FallLook", "FallTex", "WaterColor",
                           "WaterFoam", "NightTint")}
MATERIAL_LOOKS = [
    {"name": "FrameWood", "parent": MATERIAL_PATH, "kind": "scene",
     "textures": {"BC": f"{PLANKS}_BC", "N": f"{PLANKS}_N", "ORM": f"{PLANKS}_ORMH"},
     "scalars": {"Projected": 0.0, "UseORM": 1.0, "UseNormal": 1.0, "NormalStrength": 1.5, "AOStrength": 1.3,
                 "RoughnessScale": 1.0},
     # concept band median sRGB (38, 28, 22) (C0, 30..85 uu around frame-002) -> albedo lin ~ (0.033, 0.020, 0.014) by the
     # P8 island ratio display / albedo 0.59; / Planks023A mean lin (0.102, 0.079, 0.062)
     "vectors": {"BakedTint": (0.33, 0.25, 0.22, 1.0)},
     "for": "F2 the heavy dark outer frame band around frame-002 (bevelled planks: UV0 1 = one Planks023A tile ~ 100 uu)"},
    {"name": "FrameIron", "parent": MATERIAL_PATH, "kind": "scene",
     "textures": {"BC": f"{FRAME_IRON}_BC", "N": f"{FRAME_IRON}_N", "ORM": f"{FRAME_IRON}_ORM"},
     "scalars": {"Projected": 0.0, "UseORM": 1.0, "UseNormal": 1.0, "NormalStrength": 1.0},
     "vectors": {"BakedTint": (0.85, 0.85, 0.85, 1.0)},
     "for": "F2 the iron corner brackets / mid-edge straps / rivets (the frame-002 iron textures)"},
    {"name": "FallsSheet", "parent": FALLS_PARENT, "kind": "falls", "textures": {},
     "scalars": {},
     "vectors": {"FallCard": (320.0, 70.0, 0.0, 1.0), "FallFlow": (48.0, 6.0, 18.0, 0.12),
                 "FallLook": (0.62, 0.96, 0.6, 1.0), "FallTex": (40.0, 110.0, 1.6, 0.0)},
     "for": "F4 the cascade sheets (2-3 tiers down the front cliff; translucent lit, streaks along v)"},
    {"name": "FallsFoam", "parent": FALLS_PARENT, "kind": "falls", "textures": {},
     "scalars": {},
     "vectors": {"FallCard": (320.0, 30.0, 0.0, 1.0), "FallFlow": (22.0, 3.0, 22.0, 0.3),
                 "FallLook": (0.85, 1.0, 0.8, 1.0), "FallTex": (24.0, 60.0, 1.3, 0.0),
                 "WaterColor": (0.30, 0.36, 0.42, 0.6), "WaterFoam": (0.80, 0.85, 0.90, 1.0)},
     "for": "F4 the white foam at each tier landing and at the sea"},
]
MATERIAL_NAMES = tuple(m["name"] for m in MATERIAL_LOOKS)


def material_mi_path(name: str) -> str:
    return f"{MAP_ROOT}/MI_EnvScene_{name}"


LANTERN = {"scalars": {"Projected": 0.0, "UseORM": 0.0, "UseNormal": 0.0, "Roughness": 0.3, "EmissiveStrength": 8.0,
                       "FlickerAmp": 0.15, "FlickerHz": 4.5},
           "vectors": {"BakedTint": (0.9, 0.6, 0.3, 1.0), "EmissiveColor": (1.0, 0.45, 0.12, 1.0)}}

# ---------------------------------------------------------------------------------------------------- HLSL (Custom nodes)
# pins: (name, type) - the type the material wires in (float / float2 / float3 / float4 / Texture2D)
HLSL_BASE = """// ENV-MAPS P8 M_EnvScene graph 1 SceneBase (tools/art/concept_scene/ue_scene_material.py).
// The C0 projection is CONCEPT_HLSL of tools/art/concept_paste/ue_concept_material.py (C++ mirror
// S08ConceptPaste::ShaderSample); the plates are rectified by cp_bake.py (identity homography by default).
float4 bc = Texture2DSample(BC, BCSampler, UV);
float isProj = step(0.5, Projected);
float3 own = bc.rgb * lerp(BakedTint.rgb, FallbackTint.rgb, isProj);
float3 d = WP - CamPos.xyz;
float z = dot(d, CamForward.xyz);
float zs = max(z, 1e-3);
float sx = dot(d, CamRight.xyz) / zs / CamTan.x;
float sy = dot(d, CamUp.xyz) / zs / CamTan.y;
float2 c0 = float2((sx + 1.0) * 0.5 * CamTan.z, (1.0 - sy) * 0.5 * CamTan.w);
float3 p = float3(c0, 1.0);
float hw = dot(HRow2.xyz, p);
float2 c = float2(dot(HRow0.xyz, p), dot(HRow1.xyz, p)) / hw;
float2 uv = (c - AlbedoRect.xy) / AlbedoRect.zw;
float inside = step(0.0, min(uv.x, uv.y)) * step(max(uv.x, uv.y), 1.0);
float3 toCam = normalize(CamPos.xyz - WP);
float facing = pow(saturate(dot(normalize(VN), toCam)), max(FacingPower, 0.01));
float w = saturate(ProjStrength) * facing * inside * step(1e-3, z) * isProj;
float3 plate = Texture2DSample(Albedo, AlbedoSampler, saturate(uv)).rgb * AlbedoGain.rgb;
return lerp(own, plate, w);
"""
HLSL_NORMAL = """float4 n = Texture2DSample(N, NSampler, UV);
float2 xy = n.rg * 2.0 - 1.0;
float3 tn = float3(xy, sqrt(saturate(1.0 - dot(xy, xy))));
return normalize(lerp(float3(0.0, 0.0, 1.0), tn, saturate(UseNormal) * NormalStrength));
"""
HLSL_SURFACE = """float4 orm = Texture2DSample(ORM, ORMSampler, UV);
float use = saturate(UseORM);
float rough = lerp(Roughness, orm.g * RoughnessScale, use);
float metal = lerp(Metallic, orm.b, use);
float ao = lerp(1.0, lerp(1.0, orm.r, AOStrength), use);
return float3(saturate(rough), saturate(metal), saturate(ao));
"""
HLSL_EMISSIVE = """float4 orm = Texture2DSample(ORM, ORMSampler, UV);
float mask = lerp(1.0, orm.a, saturate(UseEmissiveMask));
float ph = frac(sin(dot(OP.xy, float2(12.9898, 78.233))) * 43758.5453) * 6.2831853;
float t = 6.2831853 * FlickerHz * Time;
float n = 0.6 * sin(t + ph) + 0.4 * sin(t * 2.37 + ph * 1.7);
float flick = 1.0 + FlickerAmp * saturate(Live) * n;
return EmissiveColor.rgb * EmissiveStrength * mask * flick * saturate(Emissive);
"""
HLSL_WIND = """// P9 F6: trunk sway (WindAmp x h^1.5) + leaf flutter (WindFlutter x h, per-vertex phase); Live = 0 -> still.
float h = saturate((WP.z - OP.z) / max(WindHeight, 1.0));
float ph = frac(sin(dot(floor(OP.xy / 7.0), float2(12.9898, 78.233))) * 43758.5453) * 6.2831853;
float t = 6.2831853 * WindHz * Time;
float s = sin(t + ph) + 0.35 * sin(2.3 * t + ph + WP.z * 0.02);
float2 dir = normalize(WindDir.xy + float2(1e-4, 0.0));
float live = saturate(Live);
float3 sway = float3(dir * (WindAmp * pow(h, 1.5) * s), 0.0);
float vp = dot(WP, float3(0.071, 0.053, 0.097)) * 6.2831853;
float tf = 6.2831853 * WindFlutterHz * Time;
float3 flutter = float3(sin(tf + vp), cos(1.31 * tf + vp * 1.7), 0.5 * sin(1.73 * tf + vp * 0.6)) * (WindFlutter * h);
return (sway + flutter) * live;
"""
HLSL_OPACITY = """float4 bc = Texture2DSample(BC, BCSampler, UV);
return lerp(1.0, bc.a, saturate(UseOpacity));
"""
_CAM = ("CamPos", "CamRight", "CamUp", "CamForward", "CamTan", "HRow0", "HRow1", "HRow2", "AlbedoRect")
NODES = {  # name -> (output dims, pins, code)
    "SceneBase": (3, [("WP", "float3"), ("VN", "float3"), ("UV", "float2"), ("BC", "Texture2D"), ("Albedo", "Texture2D")]
                  + [(n, "float4") for n in _CAM + ("BakedTint", "FallbackTint", "AlbedoGain")]
                  + [(n, "float") for n in ("Projected", "ProjStrength", "FacingPower")], HLSL_BASE),
    "SceneNormal": (3, [("UV", "float2"), ("N", "Texture2D"), ("UseNormal", "float"), ("NormalStrength", "float")], HLSL_NORMAL),
    "SceneSurface": (3, [("UV", "float2"), ("ORM", "Texture2D")]
                     + [(n, "float") for n in ("UseORM", "Roughness", "RoughnessScale", "Metallic", "AOStrength")], HLSL_SURFACE),
    "SceneEmissive": (3, [("UV", "float2"), ("ORM", "Texture2D"), ("OP", "float3"), ("Time", "float"),
                          ("EmissiveColor", "float4")]
                      + [(n, "float") for n in ("EmissiveStrength", "UseEmissiveMask", "FlickerAmp", "FlickerHz", "Live",
                                                "Emissive")], HLSL_EMISSIVE),
    "SceneWind": (3, [("WP", "float3"), ("OP", "float3"), ("Time", "float"), ("WindDir", "float4")]
                  + [(n, "float") for n in ("WindAmp", "WindHz", "WindHeight", "WindFlutter", "WindFlutterHz", "Live")],
                  HLSL_WIND),
    "SceneOpacity": (1, [("UV", "float2"), ("BC", "Texture2D"), ("UseOpacity", "float")], HLSL_OPACITY),
}


# ---------------------------------------------------------------------------------------------------- plain-Python mirror
def camera_vectors(block: dict) -> dict:
    """The MI values of the C0 camera of a conceptPaste block (FS08ConceptPaste MaterialParams: CamPos .. CamTan)."""
    cam = CPM.Camera(block)
    h = block.get("homography", [[1, 0, 0], [0, 1, 0], [0, 0, 1]])
    return {"CamPos": tuple(cam.pos) + (0.0,), "CamRight": tuple(cam.right) + (0.0,), "CamUp": tuple(cam.up) + (0.0,),
            "CamForward": tuple(cam.fwd) + (0.0,), "CamTan": (cam.tan_h, cam.tan_v, float(cam.w), float(cam.h)),
            "HRow0": tuple(float(v) for v in h[0]) + (0.0,), "HRow1": tuple(float(v) for v in h[1]) + (0.0,),
            "HRow2": tuple(float(v) for v in h[2]) + (0.0,)}


def scene_sample(vectors: dict, scalars: dict, world, normal) -> dict:
    """The projection / facing weight of HLSL_BASE for one world point and its vertex normal (no texture)."""
    v = dict(VECTORS)
    v.update(vectors)
    s = dict(SCALARS)
    s.update(scalars)
    pos, right, up, fwd, tan = (v[k] for k in ("CamPos", "CamRight", "CamUp", "CamForward", "CamTan"))
    d = [w - p for w, p in zip(world, pos[:3])]
    z = sum(a * b for a, b in zip(d, fwd[:3]))
    zs = max(z, 1e-3)
    sx = sum(a * b for a, b in zip(d, right[:3])) / zs / tan[0]
    sy = sum(a * b for a, b in zip(d, up[:3])) / zs / tan[1]
    c0 = ((sx + 1.0) * 0.5 * tan[2], (1.0 - sy) * 0.5 * tan[3])
    h = (v["HRow0"], v["HRow1"], v["HRow2"])
    hw = h[2][0] * c0[0] + h[2][1] * c0[1] + h[2][2]
    c = ((h[0][0] * c0[0] + h[0][1] * c0[1] + h[0][2]) / hw, (h[1][0] * c0[0] + h[1][1] * c0[1] + h[1][2]) / hw)
    r = v["AlbedoRect"]
    uv = ((c[0] - r[0]) / r[2], (c[1] - r[1]) / r[3])
    inside = 1.0 if 0.0 <= min(uv) and max(uv) <= 1.0 else 0.0
    to_cam = [p - w for p, w in zip(pos[:3], world)]
    ln = math.sqrt(sum(a * a for a in to_cam)) or 1.0
    nn = math.sqrt(sum(a * a for a in normal)) or 1.0
    facing = max(0.0, min(1.0, sum(a * b for a, b in zip(normal, to_cam)) / ln / nn)) ** max(s["FacingPower"], 0.01)
    proj = 1.0 if s["Projected"] >= 0.5 else 0.0
    weight = max(0.0, min(1.0, s["ProjStrength"])) * facing * inside * (1.0 if z >= 1e-3 else 0.0) * proj
    return {"c0": c0, "concept": c, "uv": uv, "inside": inside, "facing": facing, "weight": weight, "z": z}


def compile_check() -> dict:
    """DXC compile of every Custom node, UE-style function wrappers (Texture2D pins -> the texture + its sampler)."""
    sys.path.insert(0, str(REPO / "tools" / "art" / "env_kit"))
    import hlsl_check as HC  # noqa: E402

    dxc = HC.find_dxc()
    if not dxc:
        return {"status": "skipped", "reason": "no dxc"}
    src = ["#define Texture2DSample(T, S, UV) T.Sample(S, UV)",
           "#define Texture2DSampleLevel(T, S, UV, L) T.SampleLevel(S, UV, L)",
           "struct FMaterialPixelParameters { float4 SvPosition; };",
           "Texture2D GTex; SamplerState GTexSampler;", ""]
    calls = []
    sample = {"float": "0.5", "float2": "float2(0.3, 0.6)", "float3": "float3(0.2, 0.4, 0.6)",
              "float4": "float4(0.2, 0.4, 0.6, 0.8)"}
    for name, (dim, pins, code) in NODES.items():
        params, args = ["FMaterialPixelParameters Parameters"], ["P"]
        for pin, typ in pins:
            if typ == "Texture2D":
                params += [f"Texture2D {pin}", f"SamplerState {pin}Sampler"]
                args += ["GTex", "GTexSampler"]
            else:
                params.append(f"{typ} {pin}")
                args.append(sample[typ])
        out = {1: "float", 3: "float3"}[dim]
        src.append(f"{out} {name}({', '.join(params)})\n{{\n{code}\n}}\n")
        calls.append(f"  acc += dot(float4({name}({', '.join(args)}){', 0.0' * (4 - dim)}), float4(1.0, 1.0, 1.0, 1.0));")
    src.append("float4 main(float4 pos : SV_Position) : SV_Target\n{\n  FMaterialPixelParameters P;\n  P.SvPosition = pos;\n"
               "  float acc = 0.0;\n" + "\n".join(calls) + "\n  return float4(acc, 0.0, 0.0, 1.0);\n}\n")
    with tempfile.TemporaryDirectory() as d:
        f = Path(d) / "scene.hlsl"
        f.write_text("\n".join(src), encoding="utf-8")
        r = subprocess.run([dxc, "-T", "ps_6_0", "-E", "main", "-HV", "2021", str(f), "-Fo", os.devnull],
                           capture_output=True, text=True)
    return {"status": "ok" if r.returncode == 0 else "failed", "nodes": len(NODES), "log": (r.stdout + r.stderr)[-3000:]}


# ---------------------------------------------------------------------------------------------------- MI plan
def load_manifest(path: Path | None = None) -> dict | None:
    p = Path(path) if path else MANIFEST
    return json.loads(p.read_text(encoding="utf-8")) if p.is_file() else None


def sarpedon_block(profiles: dict | None = None) -> dict:
    prof = profiles or json.loads(PROFILES.read_text(encoding="utf-8"))
    return next(b for b in prof["boards"] if b["id"] == BOARD_ID)["conceptPaste"]


def _texture_ue(file_path: str) -> str:
    return f"{MAP_ROOT}/{Path(file_path).stem}"


def load_tune(path: Path | None = None) -> dict:
    p = Path(path) if path else TUNE
    return json.loads(p.read_text(encoding="utf-8")) if p.is_file() else {}


def _tuned(item: dict, *overrides) -> dict:
    for o in overrides:
        if not o:
            continue
        item["scalars"].update({k: float(v) for k, v in (o.get("scalars") or {}).items()})
        item["vectors"].update({k: tuple(float(x) for x in v) for k, v in (o.get("vectors") or {}).items()})
        for k, v in (o.get("vectorsMul") or {}).items():  # rgb x factor (alpha kept): e.g. the measured FallbackTint
            if k in item["vectors"]:
                a = item["vectors"][k]
                item["vectors"][k] = tuple(float(a[i]) * float(v[i]) if i < 3 else float(a[i]) for i in range(len(a)))
    return item


def mi_plan(manifest: dict | None, block: dict | None = None, tune: dict | None = None) -> list[dict]:
    """Every MI this tool builds: name, path, parent, textures (param -> UE path), scalars, vectors."""
    block = block or sarpedon_block()
    tune = load_tune() if tune is None else tune
    tb, tl, tm = tune.get("baked") or {}, tune.get("looks") or {}, tune.get("materials") or {}
    cam = camera_vectors(block)
    projected = (manifest or {}).get("projected") or {}
    albedo = projected.get("ue") or f"{MAP_ROOT}/T_Env_S_AlbedoC0"
    rect = tuple(float(v) for v in projected.get("rectC0Px", ALBEDO_DEFAULT_RECT))
    plan = []
    material_paths = {material_mi_path(n) for n in MATERIAL_NAMES}
    for m in (manifest or {}).get("meshes", []):
        if not isinstance(m, dict) or not isinstance(m.get("name"), str):
            continue  # ue_import_concept_scene.validate reports it
        if m.get("mi") in material_paths:
            continue  # P9: the mesh takes a material-route MI (built below), not a baked MI of its own
        mat = m.get("material") or {}
        tex = {k: _texture_ue(v) for k, v in (m.get("textures") or {}).items() if k in ("BC", "N", "ORM")}
        name = f"MI_Env_S_{m['name']}"
        path = m.get("mi") or f"{MAP_ROOT}/{name}"
        scalars = {"Projected": 0.0, "UseORM": 1.0 if "ORM" in tex else 0.0, "UseNormal": 1.0 if "N" in tex else 0.0}
        scalars.update({k: float(v) for k, v in (mat.get("scalars") or {}).items()})
        vectors = dict(cam)
        vectors.update({k: tuple(float(x) for x in v) for k, v in (mat.get("vectors") or {}).items()})
        plan.append(_tuned({"name": path.rsplit("/", 1)[1], "path": path, "route": "baked", "mesh": m["name"],
                            "parent": MASKED_PATH if mat.get("masked") else MATERIAL_PATH, "textures": tex,
                            "scalars": scalars, "vectors": vectors}, tb.get("*"), tb.get(m["name"])))
    looks = (manifest or {}).get("looks") or DEFAULT_LOOKS
    look_over = {}
    for look in looks:
        if look.get("name") in MATERIAL_NAMES:  # P9: a look named like a material-route MI only overrides its values
            look_over[look["name"]] = look
            continue
        tex = {"Albedo": albedo}
        if look.get("bc"):
            tex["BC"] = look["bc"]
        scalars = {"Projected": 1.0, "UseORM": 0.0, "UseNormal": 0.0}
        scalars.update({k: float(v) for k, v in (look.get("scalars") or {}).items()})
        vectors = dict(cam)
        vectors["AlbedoRect"] = rect
        vectors.update({k: tuple(float(x) for x in v) for k, v in (look.get("vectors") or {}).items()})
        name = f"MI_EnvScene_Proj_{look['name']}"
        plan.append(_tuned({"name": name, "path": f"{MAP_ROOT}/{name}", "route": "projected", "look": look["name"],
                            "parent": MASKED_PATH if look.get("masked") else MATERIAL_PATH, "textures": tex,
                            "scalars": scalars, "vectors": vectors},
                           FOLIAGE_WIND.get(look["name"]), tl.get("*"), tl.get(look["name"])))
    # P9 F2 / F4: the material-route MIs (always planned: track A's meshes name them; the defaults are documented above)
    over = (manifest or {}).get("materials") or {}
    for spec in MATERIAL_LOOKS:
        name = f"MI_EnvScene_{spec['name']}"
        vectors = dict(cam) if spec["kind"] == "scene" else {}
        vectors.update({k: tuple(float(x) for x in v) for k, v in spec["vectors"].items()})
        plan.append(_tuned({"name": name, "path": material_mi_path(spec["name"]),
                            "route": "material" if spec["kind"] == "scene" else "falls", "look": spec["name"],
                            "parent": spec["parent"], "textures": dict(spec["textures"]), "scalars": dict(spec["scalars"]),
                            "vectors": vectors},
                           look_over.get(spec["name"]), over.get(spec["name"]), tm.get(spec["name"])))
    plan.append(_tuned({"name": LANTERN_GLASS, "path": f"{MAP_ROOT}/{LANTERN_GLASS}", "route": "emissive",
                        "parent": MATERIAL_PATH, "textures": {}, "scalars": dict(LANTERN["scalars"]),
                        "vectors": dict(cam, **{k: tuple(v) for k, v in LANTERN["vectors"].items()})},
                       tune.get("lanternGlass")))
    lh = tune.get("lanternHead")
    if lh:  # a child of the P7c lantern MI (M_EnvProp parameters, not M_EnvScene): the lit3d lantern glass
        plan.append(_tuned({"name": LANTERN_HEAD, "path": f"{MAP_ROOT}/{LANTERN_HEAD}", "route": "child",
                            "parent": lh["parent"], "textures": {}, "scalars": {}, "vectors": {}}, lh))
    return plan


# ---------------------------------------------------------------------------------------------------- --check
def header_constants() -> dict:
    text = HEADER.read_text(encoding="utf-8")
    return dict(re.findall(r'inline const TCHAR\* const (Scene\w+|Kind\w+|DefaultSceneVariant|LightsOffFlagName) = TEXT\("([^"]+)"\);', text))


def check() -> tuple[dict, list[str]]:
    errors: list[str] = []
    report: dict = {}
    hc = header_constants()
    want = {"SceneMaterialPath": MATERIAL_PATH, "SceneCollectionPath": MPC_PATH, "SceneLiveParamName": MPC_LIVE,
            "SceneEmissiveParamName": MPC_EMISSIVE, "KindLit3d": "lit3d", "KindPaste": "paste", "DefaultSceneVariant": "scene",
            "LightsOffFlagName": "ArtPreviewLightsOff"}
    for k, v in want.items():
        if hc.get(k) != v:
            errors.append(f"S08ConceptPaste.h {k} = {hc.get(k)!r}, this tool uses {v!r}")
    src = SOURCE.read_text(encoding="utf-8")
    if 'FName(TEXT("EmissiveStrength"))' not in src:
        errors.append("S08ConceptPaste::LightsOffEmissiveParams does not zero EmissiveStrength (the M_EnvScene emissive scalar)")
    report["header"] = hc
    # parameter names unique across kinds
    names = list(TEXTURES) + list(SCALARS) + list(VECTORS)
    if len(names) != len(set(names)):
        errors.append("duplicate parameter names")
    for node, (_dim, pins, code) in NODES.items():
        for pin, _t in pins:
            if pin not in names and pin not in ("WP", "VN", "UV", "OP", "Time", MPC_LIVE, MPC_EMISSIVE):
                errors.append(f"{node}: pin {pin} has no source")
            if not re.search(r"\b" + re.escape(pin) + r"\b", code):
                errors.append(f"{node}: pin {pin} unused in its code")
    # the shipped lit3d block
    profiles = json.loads(PROFILES.read_text(encoding="utf-8"))
    board = next(b for b in profiles["boards"] if b["id"] == BOARD_ID)
    block = board["conceptPaste"]
    lit = block.get("lit3d") or {}
    if block.get("mode") != "lit3d" or not lit:
        errors.append("sarpedon-original: conceptPaste.mode must be lit3d with a lit3d object (P8 default)")
    if MATERIAL_PATH not in lit.get("required", []) or f"{MAP_ROOT}/SM_Env_S_Island" not in lit.get("required", []):
        errors.append("sarpedon lit3d.required must list M_EnvScene and SM_Env_S_Island")
    if lit.get("manifest") != "tools/art/concept_scene/manifest.sarpedon.json":
        errors.append(f"sarpedon lit3d.manifest {lit.get('manifest')!r}")
    # P9 F4: the P5c falls (sheet / lip / foam) are hidden - the scene overlay's cascade replaces them; the sea ring stays
    want_hide = {"tray", "ground", "waterfalls", "backdrop", "fog", "baseProps", "baseFx", "layoutLights"}
    if set(lit.get("hide", [])) != want_hide:
        errors.append(f"sarpedon lit3d.hide {lit.get('hide')} (P9: {sorted(want_hide)})")
    points = len(profiles["lightProfiles"][board["light"]].get("points", []))
    if points + len(lit.get("lights", [])) > 6 or len(lit.get("lights", [])) != 5:
        errors.append(f"sarpedon lit3d lights {len(lit.get('lights', []))} + profile points {points}: 5 lights, <= 6 points")
    # P8.3: lantern-deck-n's point moved to lantern-bay (the painted warm pool on the beach; the dock was over-lit)
    if {x["id"] for x in lit.get("lights", [])} != {"fire-fort", "fire-brazier", "lantern-left", "lantern-bay", "lantern-deck-se"}:
        errors.append("sarpedon lit3d lights must be fire-fort, fire-brazier, lantern-left, lantern-bay, lantern-deck-se")
    marm = next(b for b in profiles["boards"] if b["id"] == "marmoreal-original")["conceptPaste"]
    if "lit3d" in marm or marm.get("mode", "paste") != "paste" or marm.get("default") != "off":
        errors.append("marmoreal-original: the accepted look - no lit3d, paste comparison off by default")
    report["lit3d"] = {"variant": lit.get("variant"), "required": lit.get("required"), "lights": len(lit.get("lights", [])),
                       "casters": lit.get("casters"), "seaZUU": lit.get("seaZUU")}
    # the projection mirror = the paste's (same camera / rect -> the same C0 / concept px, uv = the plate B uv)
    cam = camera_vectors(block)
    vec = dict(cam, AlbedoRect=tuple(block.get("rectB", ALBEDO_DEFAULT_RECT)))
    fh = (445.6667 + 24, 288.6667 + 24)
    worst = 0.0
    for wpt in ((0.0, 0.0, 0.0), (-700.0, 350.0, -3.0), (831.2, -133.3, 49.1), (-555.1, 194.3, 112.1), (300.0, -900.0, -300.0)):
        a = scene_sample(vec, {"Projected": 1.0}, wpt, (0.0, 0.0, 1.0))
        b = CPM.shader_sample(block, fh, wpt)
        worst = max(worst, abs(a["uv"][0] - b["uvB"][0]), abs(a["uv"][1] - b["uvB"][1]),
                    abs(a["c0"][0] - b["c0"][0]) / 1920.0, abs(a["c0"][1] - b["c0"][1]) / 1080.0)
    report["mirrorMaxUvErr"] = worst
    if worst > 1e-9:
        errors.append(f"SceneBase projection differs from M_ConceptPaste by {worst}")
    if CPM.DESIGN.exists():
        design = json.loads(CPM.DESIGN.read_text(encoding="utf-8"))
        px_worst = 0.0
        for e in design["5_elements"]["keep_3D_animated"]:
            a = scene_sample(cam, {"Projected": 1.0}, e["world"], (0.0, 0.0, 1.0))
            px_worst = max(px_worst, math.hypot(a["c0"][0] - e["px"][0], a["c0"][1] - e["px"][1]))
        report["designDetailsMaxPx"] = round(px_worst, 3)
        if px_worst > 0.15:
            errors.append(f"SceneBase C0 puts a design detail {px_worst:.3f} px off")
    # facing: a face towards C0 takes the plate, a face turned away keeps its own colour, baked MIs never project
    up = scene_sample(vec, {"Projected": 1.0}, (-700.0, 350.0, -3.0), (0.0, 0.0, 1.0))
    away = scene_sample(vec, {"Projected": 1.0}, (-700.0, 350.0, -3.0), (0.0, -0.5736, -0.8192))
    baked = scene_sample(vec, {"Projected": 0.0}, (-700.0, 350.0, -3.0), (0.0, 0.0, 1.0))
    report["facing"] = {"up": round(up["weight"], 4), "away": away["weight"], "baked": baked["weight"]}
    if not (up["weight"] > 0.5 and away["weight"] == 0.0 and baked["weight"] == 0.0):
        errors.append(f"facing blend wrong: {report['facing']}")
    # the MI plan (with the manifest when track A wrote it)
    manifest = load_manifest()
    plan = mi_plan(manifest, block)
    report["manifest"] = "present" if manifest else "absent (default looks only)"
    report["mis"] = [{"name": m["name"], "route": m["route"], "parent": m["parent"].rsplit("/", 1)[1],
                      "textures": sorted(m["textures"])} for m in plan]
    for m in plan:
        if not m["path"].startswith("/Game/EnvMaps/") or m["path"].startswith("/Game/EnvMaps/Data/"):
            errors.append(f"{m['name']}: {m['path']} is not a cooked /Game/EnvMaps path")
        if not re.fullmatch(r"MI_(Env_S_[A-Za-z0-9]+|EnvScene_Proj_[A-Za-z0-9]+|EnvScene_LanternGlass|EnvScene_LanternHead|"
                            r"EnvScene_(" + "|".join(MATERIAL_NAMES) + r"))", m["name"]):
            errors.append(f"{m['name']}: not MI_Env_S_<Name> / MI_EnvScene_Proj_<Look> / MI_EnvScene_<Material>")
        if m["route"] == "child":
            if not m["parent"].startswith("/Game/EnvKit/ConceptPaste/MI_"):
                errors.append(f"{m['name']}: parent {m['parent']} is not a P7c ConceptPaste MI")
            continue
        if m["route"] == "falls":  # a child of the P5c waterfall MI: M_EnvWaterfall parameters only
            if m["parent"] != FALLS_PARENT:
                errors.append(f"{m['name']}: parent {m['parent']} is not {FALLS_PARENT}")
            for k in m["scalars"]:
                if k not in FALL_PARAMS["scalars"]:
                    errors.append(f"{m['name']}: {k} is not an M_EnvWaterfall scalar")
            for k, v in m["vectors"].items():
                if k not in FALL_PARAMS["vectors"]:
                    errors.append(f"{m['name']}: {k} is not an M_EnvWaterfall vector")
                elif len(v) != 4:
                    errors.append(f"{m['name']}: {k} needs 4 components")
            card = m["vectors"].get("FallCard")
            if card and not (card[0] > 0 and card[1] > 0 and card[2] in (0.0, 1.0) and card[3] in (0.0, 1.0)):
                errors.append(f"{m['name']}: FallCard {card} must be (width uu, height uu, kind 0 | 1, flip 0 | 1)")
            continue
        for k in list(m["scalars"]) + list(m["vectors"]) + list(m["textures"]):
            if k not in names:
                errors.append(f"{m['name']}: {k} is not an M_EnvScene parameter")
    if len({m["path"] for m in plan}) != len(plan):
        errors.append("duplicate MI paths")
    # P9 F6: the foliage wind is live-only and large enough to read (G7 foliage motion >= 3 %)
    fol = next((m for m in plan if m.get("look") == "Foliage"), None)
    if fol is None:
        errors.append("no MI_EnvScene_Proj_Foliage in the plan (the projected foliage route)")
    else:
        fs = fol["scalars"]
        report["foliageWind"] = {k: fs.get(k) for k in ("WindAmp", "WindHz", "WindHeight", "WindFlutter", "WindFlutterHz")}
        if not (fs.get("WindAmp", 0.0) >= 6.0 and fs.get("WindHeight", 300.0) <= 150.0 and fs.get("WindFlutter", 0.0) > 0.0):
            errors.append(f"Foliage wind {report['foliageWind']}: P9 F6 needs WindAmp >= 6, WindHeight <= 150, WindFlutter > 0")
    if "saturate(Live)" not in HLSL_WIND or "* live" not in HLSL_WIND:
        errors.append("SceneWind must scale every term by the MPC Live (frozen -Bench = still)")
    report["materialMis"] = {m["name"]: {"route": m["route"], "parent": m["parent"].rsplit("/", 1)[1],
                                         "textures": sorted(m["textures"].values())}
                             for m in plan if m["route"] in ("material", "falls")}
    for name in MATERIAL_NAMES:
        if f"MI_EnvScene_{name}" not in report["materialMis"]:
            errors.append(f"MI_EnvScene_{name} missing from the plan")
    report["hlsl"] = compile_check()
    if report["hlsl"]["status"] == "failed":
        errors.append("DXC: " + report["hlsl"]["log"][-800:])
    return report, errors


# ---------------------------------------------------------------------------------------------------- UE
def _expr(material, cls, x, y):
    node = u.MaterialEditingLibrary.create_material_expression(material, cls, x, y)
    if node is None:
        raise RuntimeError(f"could not create {cls}")
    return node


def _connect(src, out, dst, inp):
    if not u.MaterialEditingLibrary.connect_material_expressions(src, out, dst, inp):
        raise RuntimeError(f"could not connect {src.get_name()}.{out or '<0>'} -> {dst.get_name()}.{inp}")


def _connect_vector(material, node, dst, pin, y):
    """A vector parameter into a float4 pin (RGBA output, else Append(RGB, A))."""
    if u.MaterialEditingLibrary.connect_material_expressions(node, "RGBA", dst, pin):
        return
    append = _expr(material, u.MaterialExpressionAppendVector, -1200, y)
    _connect(node, "RGB", append, "A")
    _connect(node, "A", append, "B")
    _connect(append, "", dst, pin)


def ensure_collection(force: bool) -> dict:
    eal = u.EditorAssetLibrary
    mpc = u.load_asset(MPC_PATH) if eal.does_asset_exist(MPC_PATH) else None
    if mpc is not None and not force and eal.get_metadata_tag(mpc, GRAPH_TAG) == GRAPH_VERSION:
        return {"action": "unchanged", "path": MPC_PATH}
    action = "rebuilt" if mpc is not None else "created"
    if mpc is None:
        mpc = u.AssetToolsHelpers.get_asset_tools().create_asset(MPC_NAME, SCENE_ROOT, u.MaterialParameterCollection,
                                                                 u.MaterialParameterCollectionFactoryNew())
    if mpc is None:
        raise RuntimeError(f"could not create {MPC_PATH}")
    params = []
    for name, value in MPC_DEFAULTS.items():
        p = u.CollectionScalarParameter()
        p.set_editor_property("parameter_name", name)
        p.set_editor_property("default_value", float(value))
        params.append(p)
    mpc.set_editor_property("scalar_parameters", params)
    eal.set_metadata_tag(mpc, GRAPH_TAG, GRAPH_VERSION)
    if not eal.save_loaded_asset(mpc, False):
        raise RuntimeError(f"could not save {MPC_PATH}")
    return {"action": action, "path": MPC_PATH, "scalars": MPC_DEFAULTS}


def build_master(path: str, masked: bool, mpc, force: bool) -> dict:
    eal, mel = u.EditorAssetLibrary, u.MaterialEditingLibrary
    folder, name = path.rsplit("/", 1)
    material = u.load_asset(path) if eal.does_asset_exist(path) else None
    if material is not None and not force and eal.get_metadata_tag(material, GRAPH_TAG) == GRAPH_VERSION:
        return {"action": "unchanged", "path": path, "graphVersion": GRAPH_VERSION}
    action = "rebuilt" if material is not None else "created"
    if material is None:
        material = u.AssetToolsHelpers.get_asset_tools().create_asset(name, folder, u.Material, u.MaterialFactoryNew())
    if material is None:
        raise RuntimeError(f"could not create {path}")
    mel.delete_all_material_expressions(material)
    material.set_editor_property("shading_model", u.MaterialShadingModel.MSM_DEFAULT_LIT)
    material.set_editor_property("blend_mode", u.BlendMode.BLEND_MASKED if masked else u.BlendMode.BLEND_OPAQUE)
    material.set_editor_property("two_sided", bool(masked))
    if masked:
        material.set_editor_property("opacity_mask_clip_value", 0.5)
    sources = {}
    y = -900
    for key, cls in (("WP", u.MaterialExpressionWorldPosition), ("VN", u.MaterialExpressionVertexNormalWS),
                     ("UV", u.MaterialExpressionTextureCoordinate), ("OP", u.MaterialExpressionObjectPositionWS),
                     ("Time", u.MaterialExpressionTime)):
        sources[key] = _expr(material, cls, -1500, y)
        y += 90
    for key in (MPC_LIVE, MPC_EMISSIVE):
        node = _expr(material, u.MaterialExpressionCollectionParameter, -1500, y)
        node.set_editor_property("collection", mpc)
        node.set_editor_property("parameter_name", key)
        sources[key] = node
        y += 90
    for key in TEXTURES:
        node = _expr(material, u.MaterialExpressionTextureObjectParameter, -1500, y)
        node.set_editor_property("parameter_name", key)
        tex = u.load_asset(TEXTURE_DEFAULTS[key])
        if tex is not None:
            node.set_editor_property("texture", tex)
        sources[key] = node
        y += 120
    for key, value in SCALARS.items():
        node = _expr(material, u.MaterialExpressionScalarParameter, -1500, y)
        node.set_editor_property("parameter_name", key)
        node.set_editor_property("default_value", float(value))
        sources[key] = node
        y += 80
    for key, value in VECTORS.items():
        node = _expr(material, u.MaterialExpressionVectorParameter, -1500, y)
        node.set_editor_property("parameter_name", key)
        node.set_editor_property("default_value", u.LinearColor(*[float(v) for v in value]))
        sources[key] = node
        y += 100
    out_types = {1: u.CustomMaterialOutputType.CMOT_FLOAT1, 3: u.CustomMaterialOutputType.CMOT_FLOAT3}
    customs = {}
    cy = -600
    for node_name, (dim, pins, code) in NODES.items():
        if node_name == "SceneOpacity" and not masked:
            continue
        custom = _expr(material, u.MaterialExpressionCustom, -500, cy)
        custom.set_editor_property("description", node_name)
        custom.set_editor_property("output_type", out_types[dim])
        inputs = []
        for pin, _t in pins:
            ci = u.CustomInput()
            ci.set_editor_property("input_name", pin)
            inputs.append(ci)
        custom.set_editor_property("inputs", inputs)
        custom.set_editor_property("code", code)
        for pin, typ in pins:
            src = sources[pin]
            if typ == "float4":
                _connect_vector(material, src, custom, pin, cy)
            else:
                _connect(src, "", custom, pin)
        customs[node_name] = custom
        cy += 260
    surface = customs["SceneSurface"]
    masks = {}
    for ch in ("r", "g", "b"):
        m = _expr(material, u.MaterialExpressionComponentMask, -200, 200 + 80 * len(masks))
        for c in ("r", "g", "b", "a"):
            m.set_editor_property(c, c == ch)
        _connect(surface, "", m, "")
        masks[ch] = m
    mel.connect_material_property(customs["SceneBase"], "", u.MaterialProperty.MP_BASE_COLOR)
    mel.connect_material_property(customs["SceneNormal"], "", u.MaterialProperty.MP_NORMAL)
    mel.connect_material_property(masks["r"], "", u.MaterialProperty.MP_ROUGHNESS)
    mel.connect_material_property(masks["g"], "", u.MaterialProperty.MP_METALLIC)
    mel.connect_material_property(masks["b"], "", u.MaterialProperty.MP_AMBIENT_OCCLUSION)
    mel.connect_material_property(customs["SceneEmissive"], "", u.MaterialProperty.MP_EMISSIVE_COLOR)
    mel.connect_material_property(customs["SceneWind"], "", u.MaterialProperty.MP_WORLD_POSITION_OFFSET)
    if masked:
        mel.connect_material_property(customs["SceneOpacity"], "", u.MaterialProperty.MP_OPACITY_MASK)
    mel.layout_material_expressions(material)
    mel.recompile_material(material)
    eal.set_metadata_tag(material, GRAPH_TAG, GRAPH_VERSION)
    if not eal.save_loaded_asset(material, False):
        raise RuntimeError(f"could not save {path}")
    got = {"vector": sorted(str(n) for n in mel.get_vector_parameter_names(material)),
           "scalar": sorted(str(n) for n in mel.get_scalar_parameter_names(material)),
           "texture": sorted(str(n) for n in mel.get_texture_parameter_names(material))}
    missing = [n for n in VECTORS if n not in got["vector"]] + [n for n in SCALARS if n not in got["scalar"]] + \
              [n for n in TEXTURES if n not in got["texture"]]
    if missing:
        raise RuntimeError(f"{path}: parameters missing after the build: {missing}")
    return {"action": action, "path": path, "graphVersion": GRAPH_VERSION, "shading": "default-lit",
            "blend": "masked" if masked else "opaque", "twoSided": bool(masked),
            "expressions": int(mel.get_num_material_expressions(material))}


def build_mi(item: dict, force: bool) -> dict:
    eal, mel = u.EditorAssetLibrary, u.MaterialEditingLibrary
    path = item["path"]
    tag = MI_VERSION + ":" + json.dumps({k: item[k] for k in ("parent", "textures", "scalars", "vectors")}, sort_keys=True)
    tag_sha = __import__("hashlib").sha256(tag.encode("utf-8")).hexdigest()
    mi = u.load_asset(path) if eal.does_asset_exist(path) else None
    if mi is not None and not force and eal.get_metadata_tag(mi, MI_TAG) == tag_sha:
        return {"action": "unchanged", "path": path}
    missing = [p for p in item["textures"].values() if not eal.does_asset_exist(p)]
    action = "rebuilt" if mi is not None else "created"
    if mi is None:
        folder, name = path.rsplit("/", 1)
        mi = u.AssetToolsHelpers.get_asset_tools().create_asset(name, folder, u.MaterialInstanceConstant,
                                                                u.MaterialInstanceConstantFactoryNew())
    if mi is None:
        raise RuntimeError(f"could not create {path}")
    mel.set_material_instance_parent(mi, u.load_asset(item["parent"]))
    for key, tex_path in item["textures"].items():
        tex = u.load_asset(tex_path) if eal.does_asset_exist(tex_path) else None
        if tex is not None:
            mel.set_material_instance_texture_parameter_value(mi, key, tex)
    for key, value in item["scalars"].items():
        mel.set_material_instance_scalar_parameter_value(mi, key, float(value))
    for key, value in item["vectors"].items():
        mel.set_material_instance_vector_parameter_value(mi, key, u.LinearColor(*[float(x) for x in value]))
    # a texture still missing keeps the master default: re-run after the import (the tag stays stale on purpose)
    eal.set_metadata_tag(mi, MI_TAG, "" if missing else tag_sha)
    if not eal.save_loaded_asset(mi, False):
        raise RuntimeError(f"could not save {path}")
    return {"action": action, "path": path, "missingTextures": missing}


def build_all(manifest: dict | None, force: bool = False) -> dict:
    out = {"collection": ensure_collection(force)}
    mpc = u.load_asset(MPC_PATH)
    out["masters"] = [build_master(MATERIAL_PATH, False, mpc, force), build_master(MASKED_PATH, True, mpc, force)]
    out["mis"] = [build_mi(item, force) for item in mi_plan(manifest)]
    return out


# ---------------------------------------------------------------------------------------------------- entry
def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n", 1)[0])
    parser.add_argument("--check", action="store_true", help="plain-Python contract checks (no UE)")
    parser.add_argument("--manifest", default=None, help="manifest path (default tools/art/concept_scene/manifest.sarpedon.json)")
    parser.add_argument("--report", default=None, help="report JSON path")
    parser.add_argument("--force", action="store_true", help="rebuild even when the tags are current")
    args = parser.parse_args(argv)
    started = time.time()
    report: dict = {"schema": "unmatched.concept-scene-material/1", "tool": "tools/art/concept_scene/ue_scene_material.py",
                    "material": MATERIAL_PATH, "graphVersion": GRAPH_VERSION}
    ok = True
    if args.check or u is None:
        report["mode"] = "check"
        report["check"], errors = check()
        report["errors"] = errors
        ok = not errors
    else:
        report["mode"] = "build"
        try:
            report["build"] = build_all(load_manifest(Path(args.manifest) if args.manifest else None), args.force)
        except Exception as exc:  # reported; the commandlet logs the failure below
            report["build"] = {"action": "failed", "error": str(exc)}
            ok = False
        report["engine"] = str(u.SystemLibrary.get_engine_version())
    report["ok"] = ok
    report["seconds"] = round(time.time() - started, 2)
    text = json.dumps(report, ensure_ascii=False, indent=1)
    report_path = Path(args.report) if args.report else (
        Path(u.Paths.project_saved_dir()) / "EnvMaps" / "scene-material-report.json" if u is not None else None)
    if report_path is not None:
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text(text + "\n", encoding="utf-8")
    print("SCENE-MATERIAL-REPORT " + json.dumps(report, ensure_ascii=False))
    print(f"SCENE-MATERIAL-RESULT {'ok' if ok else 'failed'} mode={report['mode']}")
    return 0 if ok else 1


if __name__ == "__main__":
    code = main(sys.argv[1:])
    if u is None:
        sys.exit(code)
    elif code != 0:
        u.log_error(f"ue_scene_material.py failed (code {code}); see the SCENE-MATERIAL-REPORT line")
