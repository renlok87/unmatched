"""ENV-MAPS P2 track GROUND (ENV-U10): the themed ground of the original-map boards in UE (/Game/EnvKit/Ground, out of git).

Three stages, one file:
  --prep   (plain Python: numpy + PIL) the CC0 sets of ground-params.json 'sets' -> 2K staging PNGs + a manifest:
           <staging>/<Set>/T_Ground_<Set>_BC.png    sRGB colour (the raw _Color.jpg; rotated for rotate90 sets)
           <staging>/<Set>/T_Ground_<Set>_N.png     DirectX normal (_NormalDX.jpg; rotate90 also turns the XY vector:
                                                    R' = G, G' = 255 - R for numpy rot90 k=1)
           <staging>/<Set>/T_Ground_<Set>_ORMH.png  linear RGBA: R = AO (1 when the set has none), G = roughness,
                                                    B = metalness (0 when none), A = height (_Displacement normalised to
                                                    its 1..99 % percentiles, stored 1..255 - never 0, see the splat)
           <staging>/WaterRipple/T_Ground_WaterRipple_N.png   P4: the procedural water ripple normal (DirectX, tileable:
                                                    band-limited FFT noise with integer frequencies, RIPPLE recipe; no
                                                    CC0 water normal exists on ambientCG / Poly Haven and the ENV-U5
                                                    budget is used up)
           <staging>/ground-sources.json            sha256 of every raw input and output + the recipe
           Default staging: <repo>/unreal/Unmatched/Saved/EnvKit/GroundSources (gitignored; ~100 MB).
  --check  (plain Python) staging files against the manifest, splat / aux PNGs against <map>.splat.json, and the
           layouts' 'ground' sections against the splats (sha256 / rect / material path / waterfalls).
  (UE)     UnrealEditor-Cmd -run=pythonscript: imports into
           /Game/EnvKit/Ground/Sets/T_Ground_<Set>_{BC,N,ORMH}   BC sRGB TC_Default; N TC_Normalmap (DirectX, no green
                                                                  flip); ORMH TC_Masks linear; group World(NormalMap)
           /Game/EnvKit/Ground/Sets/T_Ground_WaterRipple_N         TC_Normalmap, wrap (the water ripples, both maps)
           /Game/EnvKit/Ground/T_EnvGround_<Map>_Splat            TC_VectorDisplacementmap (RGBA8, uncompressed), linear,
                                                                  clamp addressing
           /Game/EnvKit/Ground/T_EnvGround_<Map>_Aux              the same settings: R water, G foam, B edge band,
                                                                  A = 1 + water depth * 254 (ground_splat.py)
           /Game/EnvKit/Ground/M_EnvGround                         the 4-layer splat material (graph below)
           /Game/EnvKit/Ground/MI_EnvGround_<Map>                  per map: layer sets, tiling, tints, per-layer
                                                                  roughness / specular / normal / macro, edge band,
                                                                  water, accent, grade, SplatRect
           /Game/EnvKit/Ground/M_EnvWaterfall                      P4: the waterfall material (P5c graph 3: lit
                                                                  translucent + Water Materials streaks)
           /Game/EnvKit/Ground/MI_EnvWaterfall_<Map>               only maps with ground-params 'water.falls'
           /Game/EnvKit/Ground/M_EnvSea                            P5 track B: the sea ring material (opaque, lit;
                                                                  P5c graph 2: Water Materials lace / waves, surf, sky)
           (P5c: both derived materials reference /Game/WaterMaterials/Textures/{T_Ocean_Foam, T_Water_Normal,
            T_Water_Normal_Large, T_Waterfall_Foam} - tharlevfx, CC BY 4.0, docs/art-pipeline/CREDITS-fab.md; the
            gitignored pack is never modified, the cooker follows the references from /Game/EnvKit)
           /Game/EnvKit/Ground/MI_EnvSea_<Map>                     only maps with ground-params 'sea' (Sarpedon)
           /Game/EnvKit/Ground/<Map>/SM_Env_S_{Waterfall,WaterfallFoam,WaterfallLip,SeaRing}
                                                                  P5 track B: the lane K meshes (art/pipeline-candidates/
                                                                  ASSET-ENV-S-WATERFALL-001/<run>/export, sha256 = the
                                                                  run's build-report exports): legacy FbxFactory, scale 1,
                                                                  normals imported, no collision, Nanite off; vertex
                                                                  colours REPLACE for the lip and the sea ring (Col
                                                                  masks), IGNORE for the sheet / foam; slots: sheet and
                                                                  foam -> MI_EnvWaterfall_<Map> (the runtime puts MIDs on
                                                                  top), lip -> MI_TableBase_T2b_<Map> (ue_import_tray_t2.py
                                                                  runs first; else a warning), sea -> MI_EnvSea_<Map>
           (DefaultGame.ini cooks /Game/EnvKit already; S08EnvGround.cpp loads the MIs by the layout paths.)

M_EnvGround (graph 2; lit, opaque, one-sided; every texture on a SHARED sampler - 16 samples use no sampler slot):
  P        = GroundStrip.xy + TexCoord0 * GroundStrip.zw        board XY (uu) of the strip pixel; the runtime sets
                                                                GroundStrip = (min.x, min.y, size.x, size.y) of each
                                                                /Engine/BasicShapes/Plane strip on its MID (engine plane:
                                                                UV (0,0) at local (-50,-50), u along +X, v along +Y)
  layer i  = L{i}_BC / L{i}_N / L{i}_ORMH at P / L{i}_TileUU      (i = 0..3, wrap)
  splat    = Splat at (P - SplatRect.xy) / SplatRect.zw           (clamp; RGB = L1..L3 coverage, A = 1 + accent * 254)
  aux      = Aux at the same UV                                   (clamp; R water, G foam mask, B edge, A = 1 + depth*254)
  weights  = height-lerp stack: a_k = saturate((lerp(0.5, H_k, L{k}_HeightBlend) - 1 + splat_k * (1 + c)) / c),
             L3 over L2 over L1 over L0
  water    = (aux.r, foam = saturate((aux.g * (0.4 + 1.2 * noise(P + t * pan)) - 0.25) * 2) * WaterFoam.a, depth)
  albedo   = sum w_i * (1 + LayerMacro_i * noise(P / LayerMacroScaleUU)) * lerp(luma, BC_i, L{i}_Tint.a) * L{i}_Tint.rgb,
             x (1 + MacroStrength * value noise), x lerp(1, EdgeTint.rgb, aux.b * EdgeTint.a),
             accent: PetalSizeUU > 0 -> petals (a pink carpet of strength AccentCarpet + one jittered petal per
             PetalSizeUU cell, density = accent * AccentOpacity); PetalSizeUU = 0 -> wetness (albedo *= lerp(1, AccentColor, accent * opacity),
             roughness -> AccentRoughness); water: lerp(albedo, lerp(lerp(albedo, WaterColor, WaterColor.a), WaterColor,
             depth), water), then foam -> WaterFoam.rgb
  base     = night grade of M_MapBoard: lit = albedo * 2^NightEV * NightTint; lerp(luma, lit, NightSaturation)
  normal   = per layer xy * NormalStrength * LayerNormal_i, blended; water: two panned WaterRippleN samples
             (WaterRipple.xy tiling, WaterPan uu/s) at WaterSurface.z, lerp by water * (1 - 0.6 foam)
  rough    = sum w_i max(ORMH_i.g * LayerRoughScale_i, LayerRoughMin_i), wetness, edge -> EdgeRoughness, water ->
             WaterSurface.x, foam -> 0.7
  specular = sum w_i LayerSpecular_i, water -> WaterSurface.y;  AO / metallic = sum w_i ORMH_i.rb
  emissive = graded WaterColor * WaterSurface.w * water * (1 - foam)  (the map's river is lifted; 0 without water)
M_EnvWaterfall (graph 3, P5c; lit TRANSLUCENT with per-pixel surface lighting, two-sided; graph 2 was masked, clip
  0.5): FallCard = (width, height, kind 0 card / 1 spill, flip) per component (S08EnvGround sets it on the MID; flip 1 =
  v := 1 - v for the lane K sheet / foam meshes, whose v was authored top -> bottom in Blender and is flipped by the FBX
  import; 0 for the engine-plane card / spill); streaks scroll along +v at FallFlow.x uu/s (v runs down the card and
  towards the lip on the spill): the Water Materials T_Waterfall_Foam (CC BY 4.0) in two layers (FallTex = uu across /
  along, speed ratio of the 2nd) weighted by FallLook.w, else the graph 2 value noise; foam at the lip and in the
  streaks; side fades FallFlow.z uu whose width wobbles along the flow (FallLook.z: no straight rectangular outline),
  bottom fade FallFlow.w, spill far-edge fade FallSpill.x uu; Opacity = side x along x lerp(FallLook.x body, FallLook.y
  foam, foam); OpacityMask = the graph 2 dithered mask (screen-space interleaved gradient noise, amount FallSpill.y) for
  an MI that overrides the blend mode back to Masked (ground-params falls[0].look.blend 'masked'); ripple normal along
  the flow; emissive = graded colour * FallShade.w.
M_EnvSea (graph 2, P5c; still OPAQUE, lit, one-sided): UV0 = board XY / SeaTile.x uu (the lane K ring), UV1.y = the
  distance from the inner ring edge / 1000 uu (V flipped by the FBX import: SeaSurf.w = 1), VertexColor R = the foam band
  at the cliffs, G = the far fade (0 at the cliffs, 1 from 3500 uu out). Lace = the Water Materials T_Ocean_Foam (two
  pans at SeaPack.y uu) when SeaPack.x = 1, else the graph 1 value noise; shore foam = saturate((R (0.55 + 0.9 lace) -
  SeaPack.w) SeaPack.z); surf = crest lines every SeaSurf.x uu running in at SeaSurf.y cycles/s up to SeaSurf.z uu out
  (SeaSurfLook = crest width, opacity, lace breakup, foam emissive lift); waves = T_Water_Normal / _Large panned at
  SeaWaveTile uu -> a facet shade towards SeaWaveDir (SeaWave.x) and sparse whitecaps (SeaWave.y above SeaWave.z);
  base = lerp(lerp(SeaColor x (1 + shade), SeaFoam.rgb, foam), SeaFar.rgb, far (1 - foam)), night grade as
  M_EnvWaterfall; normal = the two wave normals x SeaShade.z fading out far; roughness SeaShade.x (foam 0.7, far 0.95),
  specular SeaShade.y (0 far); emissive = graded (SeaShade.w (1 - far)(1 - foam) + SeaSurfLook.w foam) + the sky lift
  SeaSky.rgb x SeaSky.a x lerp(SeaSkyRamp.z, 1, smoothstep(SeaSkyRamp.xy, VC.g)) with slow cloud variation (SeaSkyNoise =
  scale uu, amplitude, pan uu/s). At the material defaults (no pack, no surf / waves / sky) it equals graph 1.
  sea_cpu / sea_graph1_cpu are numpy mirrors (tests and statistics, not a render); hlsl_check.py compiles every Custom
  node with the Windows SDK DXC.
Idempotent: textures carry EnvGroundSourceSha256 (re-imported only when the source changes or --force), the materials
carry EnvGroundGraphVersion (rebuilt only when their graph version changes or --force), the MIs are compared parameter by
parameter and only written when they differ. Report: 'ENVGROUND-IMPORT-REPORT {...}' / 'ENVGROUND-IMPORT-RESULT ok|failed'
and <project>/Saved/EnvKit/ue-ground-import-report.json (or --report).

Run (repository root; the editor must be CLOSED; never inside a GPU-measurement window):
  python -B tools/art/env_kit/ground_splat.py --write-layouts          # splats + aux + layout sections (git)
  python -B tools/art/env_kit/ue_import_env_ground.py --prep           # staging PNGs (out of git)
  python -B tools/art/env_kit/ue_import_env_ground.py --check
  UnrealEditor-Cmd.exe <repo>/unreal/Unmatched/Unmatched.uproject -run=pythonscript
      -script="<repo>/tools/art/env_kit/ue_import_env_ground.py" -unattended -nosplash -nullrhi
Options: --maps marmoreal,sarpedon  --params <json>  --staging <dir>  --report <json>  --force
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import time
from pathlib import Path

try:  # inside UnrealEditor(-Cmd) only; --prep / --check run in plain Python
    import unreal as u  # type: ignore
except ImportError:  # pragma: no cover - plain Python
    u = None

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
PARAMS_DEFAULT = REPO / "art/pipeline-candidates/ASSET-ENV-KIT-001/ground/ground-params.json"
STAGING_DEFAULT = REPO / "unreal/Unmatched/Saved/EnvKit/GroundSources"
LAYOUT_DIR = REPO / "unreal/Unmatched/Config/ArtBoards/EnvLayouts"
MAPS = {"marmoreal": "Marmoreal", "sarpedon": "Sarpedon"}
ROOT = "/Game/EnvKit/Ground"
SETS_ROOT = f"{ROOT}/Sets"
MATERIAL_NAME = "M_EnvGround"
MATERIAL_PATH = f"{ROOT}/{MATERIAL_NAME}"
FALL_MATERIAL_NAME = "M_EnvWaterfall"
FALL_MATERIAL_PATH = f"{ROOT}/{FALL_MATERIAL_NAME}"
SEA_MATERIAL_NAME = "M_EnvSea"
SEA_MATERIAL_PATH = f"{ROOT}/{SEA_MATERIAL_NAME}"
SEA_GRAPH_VERSION = "2"  # P5c: pack textures (Water Materials), surf, waves, sky lift
# P5 track B: the lane K meshes of a map (part -> (asset name, vertex colours)); folder /Game/EnvKit/Ground/<Map>
ENV_MESHES = {"sheet": ("SM_Env_S_Waterfall", "ignore"), "foam": ("SM_Env_S_WaterfallFoam", "ignore"),
              "lip": ("SM_Env_S_WaterfallLip", "replace"), "sea": ("SM_Env_S_SeaRing", "replace")}
MESH_SHA_TAG = "EnvGroundMeshSha256"
MESH_VC_TAG = "EnvGroundVertexColors"
MESH_BOUNDS_TOL_UU = 0.5
MESH_TRIS_TOL = 0.01
T2B_MI_PREFIX = "/Game/PipelineCandidates/TableBase/T2b/MI_TableBase_T2b_"
SHA_TAG = "EnvGroundSourceSha256"
GRAPH_TAG = "EnvGroundGraphVersion"
GRAPH_VERSION = "2"
FALL_GRAPH_VERSION = "3"  # P5b tune: FallCard.w = 1 flips v (graph 2); P5c: translucent + pack streaks (graph 3)
PREP_VERSION = "1"
KEYS = ("BC", "N", "ORMH")
LAYERS = 4
MANIFEST_SCHEMA = "unmatched.env-ground-sources/1"
# P4: the procedural water ripple normal (no CC0 water normal on ambientCG / Poly Haven; the ENV-U5 budget is used up)
RIPPLE_SET = "WaterRipple"
RIPPLE = {"version": "1", "size": 512, "seed": 4111, "lowCycles": 3.0, "highCycles": 12.0, "slopeP99": 0.55,
          "stretchY": 1.6}


def rel(path: Path) -> str:
    try:
        return Path(path).resolve().relative_to(REPO).as_posix()
    except ValueError:
        return Path(path).as_posix()


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with Path(path).open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def load_params(path: Path) -> dict:
    params = json.loads(Path(path).read_text(encoding="utf-8"))
    if params.get("schema") != "unmatched.env-ground-params/1":
        raise SystemExit(f"{path}: not unmatched.env-ground-params/1")
    return params


def used_sets(params: dict, keys: list[str]) -> list[str]:
    out = []
    for key in keys:
        for lay in params["maps"][key]["layers"]:
            if lay["set"] not in out:
                out.append(lay["set"])
    return out


def texture_asset(set_id: str, key: str) -> str:
    return f"{SETS_ROOT}/T_Ground_{set_id}_{key}"


def splat_asset(key: str) -> str:
    return f"{ROOT}/T_EnvGround_{MAPS[key]}_Splat"


def aux_asset(key: str) -> str:
    return f"{ROOT}/T_EnvGround_{MAPS[key]}_Aux"


def ripple_asset() -> str:
    return texture_asset(RIPPLE_SET, "N")


def mi_asset(key: str) -> str:
    return f"{ROOT}/MI_EnvGround_{MAPS[key]}"


def fall_mi_asset(key: str) -> str:
    return f"{ROOT}/MI_EnvWaterfall_{MAPS[key]}"


def sea_mi_asset(key: str) -> str:
    return f"{ROOT}/MI_EnvSea_{MAPS[key]}"


def has_sea(params: dict, key: str) -> bool:
    return bool(params["maps"][key].get("sea"))


def mesh_asset(key: str, part: str) -> str:
    return f"{ROOT}/{MAPS[key]}/{ENV_MESHES[part][0]}"


def mesh_parts(params: dict, key: str) -> dict:
    """{part: lane K run (repo-relative)} of the meshes a map needs: sheet + foam (+ lip) for a fall with 'mesh', the
    sea ring for 'sea'."""
    parts = {}
    for f in (params["maps"][key].get("water") or {}).get("falls") or []:
        m = f.get("mesh")
        if m:
            parts.update(sheet=m["run"], foam=m["run"])
            if m.get("lip", True):
                parts["lip"] = m["run"]
    sea = params["maps"][key].get("sea")
    if sea:
        parts["sea"] = sea["run"]
    return parts


def plan_meshes(params: dict, key: str) -> dict:
    """The FBX of every mesh part verified against its run's build report (sha256, triangles, bounds)."""
    out, reports = {}, {}
    for part, run in mesh_parts(params, key).items():
        name, vc = ENV_MESHES[part]
        item = {"asset": mesh_asset(key, part), "vertexColors": vc, "run": run}
        try:
            if run not in reports:
                reports[run] = json.loads((REPO / run / "reports" / "build-report.json").read_text(encoding="utf-8"))
            rep_ = reports[run]
            exp = next((e for e in rep_.get("exports") or [] if e.get("name") == name), None)
            if rep_.get("checks_passed") is not True or exp is None:
                raise ValueError(f"{name} not in a passing build report of {run}")
            fbx = REPO / run / "export" / f"{name}.fbx"
            item.update(source=fbx.as_posix(), path=rel(fbx), expectedSha256=exp["sha256"],
                        triangles=exp.get("triangles"), boundsUeUU=exp.get("boundsUeLocalUU"),
                        slots=len((exp.get("roundtrip") or {}).get("material_slots") or [None]))
            if not fbx.is_file():
                item.update(ok=False, error="FBX missing")
            else:
                item["sha256"] = sha256_file(fbx)
                item["ok"] = item["sha256"] == exp["sha256"]
                if not item["ok"]:
                    item["error"] = "sha256 differs from the run's build report"
        except (OSError, ValueError, KeyError) as exc:
            item.update(ok=False, error=f"{type(exc).__name__}: {exc}")
        out[part] = item
    return out


def has_falls(params: dict, key: str) -> bool:
    return bool((params["maps"][key].get("water") or {}).get("falls"))


def srgb8_to_linear(c) -> tuple:
    """sRGB bytes (0..255) -> linear floats (the water colour of ground-params 'water.colorSrgb')."""
    out = []
    for v in c:
        x = float(v) / 255.0
        out.append(x / 12.92 if x <= 0.04045 else ((x + 0.055) / 1.055) ** 2.4)
    return tuple(out)


# ================================================================================================ prep (plain Python)
def raw_inputs(raw_root: Path, set_id: str) -> dict:
    names = {"Color": True, "NormalDX": True, "Roughness": True, "Displacement": True,
             "AmbientOcclusion": False, "Metalness": False}
    out = {}
    for name, required in names.items():
        p = raw_root / set_id / f"{set_id}_2K-JPG_{name}.jpg"
        if p.is_file():
            out[name] = p
        elif required:
            raise FileNotFoundError(f"{p} missing (ENV-U5 CC0 set {set_id} not extracted?)")
    return out


def rot90_dx_normal(n):
    """Rotate an 8-bit DirectX normal map (H, W, 3) like numpy rot90 k=1 (counter-clockwise on screen): pixel (x, y)
    -> (y, W-1-x), and the tangent-space XY vector (R = +x right, G = +y down in DirectX maps) turns the same way:
    R' = G, G' = -R (255 - R in 8-bit)."""
    import numpy as np

    out = n.copy()
    out[..., 0], out[..., 1] = n[..., 1], 255 - n[..., 0]
    return np.rot90(out, 1)


def water_ripple_normal(recipe: dict | None = None):
    """The procedural water ripple normal (H, W, 3) uint8, DirectX (x right, y down, the convention of rot90_dx_normal):
    a height field of band-limited Gaussian noise built in the Fourier domain with integer frequencies only (so the tile
    wraps seamlessly), cycles per tile in [lowCycles, highCycles] with a 1/k falloff, slightly stretched across the flow
    (stretchY > 1: crests longer along x); its exact spectral gradient is scaled so the 99th slope percentile is
    slopeP99. Deterministic (numpy default_rng(seed))."""
    import numpy as np

    r = dict(RIPPLE, **(recipe or {}))
    n = int(r["size"])
    rng = np.random.default_rng(int(r["seed"]))
    spec = np.fft.fft2(rng.standard_normal((n, n)))
    f = np.fft.fftfreq(n) * n  # integer cycles per tile
    kx, ky = np.meshgrid(f, f)  # kx along columns (x), ky along rows (y)
    k = np.hypot(kx, ky * float(r["stretchY"]))
    lo, hi = float(r["lowCycles"]), float(r["highCycles"])
    amp = (1.0 - np.exp(-(k / lo) ** 2)) * np.exp(-(k / hi) ** 2) / np.maximum(k, 1.0)
    hf = spec * amp
    hf[0, 0] = 0.0
    dx = np.real(np.fft.ifft2(hf * (2j * np.pi * kx / n)))  # dh / dpixel along x
    dy = np.real(np.fft.ifft2(hf * (2j * np.pi * ky / n)))  # dh / dpixel along y (down)
    slope = np.hypot(dx, dy)
    s = float(r["slopeP99"]) / max(float(np.percentile(slope, 99)), 1e-12)
    v = np.stack([-dx * s, -dy * s, np.ones_like(dx)], axis=-1)
    v /= np.linalg.norm(v, axis=-1, keepdims=True)
    return np.clip(np.rint((v * 0.5 + 0.5) * 255.0), 0, 255).astype(np.uint8)


def build_ripple(out_dir: Path) -> dict:
    from PIL import Image

    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / f"T_Ground_{RIPPLE_SET}_N.png"
    Image.fromarray(water_ripple_normal(), "RGB").save(path, format="PNG", compress_level=6)
    return {"N": path}


def build_set(set_id: str, spec: dict, raw_root: Path, out_dir: Path) -> dict:
    """The three staging PNGs of one CC0 set (numpy / PIL). Returns {key: path}."""
    import numpy as np
    from PIL import Image

    inp = raw_inputs(raw_root, set_id)
    rot = bool(spec.get("rotate90"))

    def load(name: str, mode: str):
        return np.asarray(Image.open(inp[name]).convert(mode))

    bc = load("Color", "RGB")
    n = load("NormalDX", "RGB").copy()
    rough = load("Roughness", "L")
    ao = load("AmbientOcclusion", "L") if "AmbientOcclusion" in inp else np.full(rough.shape, 255, np.uint8)
    metal = load("Metalness", "L") if "Metalness" in inp else np.zeros(rough.shape, np.uint8)
    disp = load("Displacement", "L").astype(float)
    lo, hi = np.percentile(disp, 1), np.percentile(disp, 99)
    h = np.clip((disp - lo) / max(hi - lo, 1e-3), 0.0, 1.0)
    height = (1.0 + np.rint(h * 254.0)).astype(np.uint8)  # 1..255: never a zero alpha (PNG infill on import)
    shapes = {bc.shape[:2], n.shape[:2], rough.shape, ao.shape, metal.shape, height.shape}
    if len(shapes) != 1:
        raise ValueError(f"{set_id}: raw maps differ in size {sorted(shapes)}")
    if rot:
        bc, n = np.rot90(bc, 1), rot90_dx_normal(n)
        rough, ao, metal, height = (np.rot90(a, 1) for a in (rough, ao, metal, height))
    orm = np.stack([ao, rough, metal, height], axis=-1)
    out_dir.mkdir(parents=True, exist_ok=True)
    paths = {"BC": out_dir / f"T_Ground_{set_id}_BC.png", "N": out_dir / f"T_Ground_{set_id}_N.png",
             "ORMH": out_dir / f"T_Ground_{set_id}_ORMH.png"}
    Image.fromarray(np.ascontiguousarray(bc), "RGB").save(paths["BC"], format="PNG", compress_level=6)
    Image.fromarray(np.ascontiguousarray(n), "RGB").save(paths["N"], format="PNG", compress_level=6)
    Image.fromarray(np.ascontiguousarray(orm), "RGBA").save(paths["ORMH"], format="PNG", compress_level=6)
    return paths


def _outputs_fresh(outs: dict, count: int) -> bool:
    return (len(outs) == count
            and all(Path(o["path"]).is_file() and sha256_file(Path(o["path"])) == o["sha256"] for o in outs.values()))


def prep(params: dict, keys: list[str], staging: Path, force: bool) -> tuple[dict, bool]:
    raw_root = Path(params["cc0Raw"])
    manifest_path = staging / "ground-sources.json"
    old = {}
    if manifest_path.is_file():
        try:
            old = json.loads(manifest_path.read_text(encoding="utf-8")).get("sets", {})
        except ValueError:
            old = {}
    lib = {}
    lib_manifest = raw_root / "manifest.json"
    if lib_manifest.is_file():
        for a in json.loads(lib_manifest.read_text(encoding="utf-8")).get("assets", []):
            lib[a.get("id")] = {k: a.get(k) for k in ("site", "page", "license", "sha256")}
    sets, ok = dict(old), True  # a --maps subset keeps the entries of the other sets
    for set_id in used_sets(params, keys):
        spec = params["sets"].get(set_id, {})
        entry = {"recipe": {"prepVersion": PREP_VERSION, "rotate90": bool(spec.get("rotate90"))},
                 "library": lib.get(set_id, {"note": "not in cc0-raw/manifest.json"})}
        try:
            inp = raw_inputs(raw_root, set_id)
            entry["inputs"] = {k: {"path": p.as_posix(), "sha256": sha256_file(p)} for k, p in inp.items()}
            prev = old.get(set_id) or {}
            outs = prev.get("outputs") or {}
            fresh = (not force and prev.get("inputs") == entry["inputs"] and prev.get("recipe") == entry["recipe"]
                     and _outputs_fresh(outs, len(KEYS)))
            if fresh:
                entry["outputs"], entry["action"] = outs, "unchanged"
            else:
                paths = build_set(set_id, spec, raw_root, staging / set_id)
                entry["outputs"] = {k: {"path": p.as_posix(), "sha256": sha256_file(p), "bytes": p.stat().st_size}
                                    for k, p in paths.items()}
                entry["action"] = "built"
        except (OSError, ValueError) as exc:
            entry["error"] = f"{type(exc).__name__}: {exc}"
            ok = False
        sets[set_id] = entry
        print(f"  prep {set_id}: {entry.get('action', 'FAILED')} {entry.get('error', '')}")
    # P4: the procedural water ripple normal (shared by every map; tiny, always prepared)
    entry = {"recipe": dict(RIPPLE, procedural="water_ripple_normal"),
             "library": {"note": "procedural (ue_import_env_ground.water_ripple_normal), our own art, no CC0 source"}}
    try:
        prev = old.get(RIPPLE_SET) or {}
        outs = prev.get("outputs") or {}
        if not force and prev.get("recipe") == entry["recipe"] and _outputs_fresh(outs, 1):
            entry["outputs"], entry["action"] = outs, "unchanged"
        else:
            paths = build_ripple(staging / RIPPLE_SET)
            entry["outputs"] = {k: {"path": p.as_posix(), "sha256": sha256_file(p), "bytes": p.stat().st_size}
                                for k, p in paths.items()}
            entry["action"] = "built"
    except (OSError, ValueError) as exc:
        entry["error"] = f"{type(exc).__name__}: {exc}"
        ok = False
    sets[RIPPLE_SET] = entry
    print(f"  prep {RIPPLE_SET}: {entry.get('action', 'FAILED')} {entry.get('error', '')}")
    manifest = {"schema": MANIFEST_SCHEMA, "tool": "tools/art/env_kit/ue_import_env_ground.py --prep",
                "cc0Raw": raw_root.as_posix(), "staging": staging.as_posix(), "sets": sets}
    staging.mkdir(parents=True, exist_ok=True)
    manifest_path.write_bytes((json.dumps(manifest, indent=1) + "\n").encode("utf-8"))
    return manifest, ok


# ================================================================================================ check (plain Python)
def _staged(entry: dict, key: str, asset: str) -> dict:
    o = (entry.get("outputs") or {}).get(key)
    t = {"asset": asset}
    if not o:
        t.update(ok=False, error="not in the staging manifest (run --prep)")
        return t
    p = Path(o["path"])
    t.update(source=p.as_posix(), sha256=o["sha256"])
    if not p.is_file():
        t.update(ok=False, error="staging file missing (run --prep)")
    else:
        got = sha256_file(p)
        t["ok"] = got == o["sha256"]
        if not t["ok"]:
            t["error"] = f"sha256 {got} != manifest (re-run --prep)"
    return t


def plan(params: dict, keys: list[str], staging: Path, params_path: Path) -> dict:
    """What the UE stage imports: staging textures (verified against the manifest), splats and aux masks (against their
    meta), the layout sections. Every item carries ok / error."""
    out = {"sets": {}, "maps": {}, "ok": True}
    manifest_path = staging / "ground-sources.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8")) if manifest_path.is_file() else {"sets": {}}
    if not manifest_path.is_file():
        out["ok"] = False
        out["error"] = f"{manifest_path} missing: run --prep first"
    for set_id in used_sets(params, keys):
        entry = (manifest.get("sets") or {}).get(set_id) or {}
        item = {"textures": {}, "ok": True}
        for key in KEYS:
            t = _staged(entry, key, texture_asset(set_id, key))
            item["textures"][key] = t
            item["ok"] = item["ok"] and t["ok"]
        out["sets"][set_id] = item
        out["ok"] = out["ok"] and item["ok"]
    entry = (manifest.get("sets") or {}).get(RIPPLE_SET) or {}
    t = _staged(entry, "N", ripple_asset())
    if t["ok"] and entry.get("recipe") != dict(RIPPLE, procedural="water_ripple_normal"):
        t.update(ok=False, error="the staged ripple was built with another RIPPLE recipe (re-run --prep)")
    out["sets"][RIPPLE_SET] = {"textures": {"N": t}, "ok": t["ok"]}
    out["ok"] = out["ok"] and t["ok"]
    # P5c: the Water Materials textures (gitignored pack; missing = the procedural fallback, a warning, not an error)
    out["pack"] = pack_plan()
    for key in keys:
        try:
            fall_mi_want(key, params)  # validates falls[0].look (blend)
        except ValueError as exc:
            out["ok"] = False
            out.setdefault("errors", []).append(str(exc))
    for key in keys:
        m = {"ok": True, "splatAsset": splat_asset(key), "auxAsset": aux_asset(key), "mi": mi_asset(key)}
        if has_falls(params, key):
            m["fallMi"] = fall_mi_asset(key)
        if has_sea(params, key):
            m["seaMi"] = sea_mi_asset(key)
        m["meshes"] = plan_meshes(params, key)
        meta_path = params_path.parent / f"{key}.splat.json"
        png_path = params_path.parent / f"{key}.splat.png"
        aux_path = params_path.parent / f"{key}.aux.png"
        try:
            meta = json.loads(meta_path.read_text(encoding="utf-8"))
            m["splatRect"] = meta["splatRect"]
            m["source"] = png_path.as_posix()
            m["sha256"] = sha256_file(png_path)
            m["auxSource"] = aux_path.as_posix()
            m["auxSha256"] = sha256_file(aux_path)
            probs = []
            if m["sha256"] != meta["png"]["sha256"]:
                probs.append(f"{rel(png_path)} sha256 != {rel(meta_path)} (re-run ground_splat.py)")
            if m["auxSha256"] != (meta.get("aux") or {}).get("sha256"):
                probs.append(f"{rel(aux_path)} sha256 != {rel(meta_path)} aux (re-run ground_splat.py)")
            layout = json.loads((LAYOUT_DIR / f"{key}.layout.json").read_text(encoding="utf-8"))
            g = layout.get("ground")
            if not isinstance(g, dict):
                probs.append("layout has no 'ground' section (ground_splat.py --write-layouts)")
            else:
                if g.get("material") != mi_asset(key):
                    probs.append(f"ground.material {g.get('material')!r} != {mi_asset(key)!r}")
                if g.get("splatRect") != meta["splatRect"]:
                    probs.append(f"ground.splatRect {g.get('splatRect')} != splat meta {meta['splatRect']}")
                if g.get("splatSha256") != m["sha256"]:
                    probs.append("ground.splatSha256 != the splat PNG")
                if g.get("auxSha256") != m["auxSha256"]:
                    probs.append("ground.auxSha256 != the aux PNG")
                falls = g.get("waterfalls") or []
                if falls != (meta.get("waterfalls") or []):
                    probs.append("ground.waterfalls != the splat meta waterfalls")
                if bool(falls) != has_falls(params, key):
                    probs.append("ground.waterfalls present / absent unlike ground-params water.falls")
                for f in falls:
                    if f.get("material") != fall_mi_asset(key):
                        probs.append(f"waterfall {f.get('id')} material {f.get('material')!r} != {fall_mi_asset(key)!r}")
                    fm = f.get("mesh")
                    if isinstance(fm, dict):
                        for part in ("sheet", "foam", "lip"):
                            if fm.get(part) is not None and fm.get(part) != mesh_asset(key, part):
                                probs.append(f"waterfall {f.get('id')} mesh.{part} {fm.get(part)!r} != {mesh_asset(key, part)!r}")
                        if fm.get("lip") is not None and fm.get("lipMaterial") != f"{T2B_MI_PREFIX}{MAPS[key]}":
                            probs.append(f"waterfall {f.get('id')} mesh.lipMaterial {fm.get('lipMaterial')!r}")
                m["waterfalls"] = len(falls)
                sea = g.get("sea")
                if sea != meta.get("sea"):
                    probs.append("ground.sea != the splat meta sea")
                if bool(sea) != has_sea(params, key):
                    probs.append("ground.sea present / absent unlike ground-params sea")
                if isinstance(sea, dict):
                    if sea.get("material") != sea_mi_asset(key):
                        probs.append(f"ground.sea.material {sea.get('material')!r} != {sea_mi_asset(key)!r}")
                    if sea.get("mesh") != mesh_asset(key, "sea"):
                        probs.append(f"ground.sea.mesh {sea.get('mesh')!r} != {mesh_asset(key, 'sea')!r}")
            bad = [f"{part}: {it.get('error')}" for part, it in m["meshes"].items() if not it.get("ok")]
            if bad:
                probs.append("meshes " + "; ".join(bad))
            if probs:
                m.update(ok=False, error="; ".join(probs) + " (ground_splat.py --write-layouts)")
        except (OSError, ValueError, KeyError) as exc:
            m.update(ok=False, error=f"{type(exc).__name__}: {exc}")
        out["maps"][key] = m
        out["ok"] = out["ok"] and m["ok"]
    return out


# ================================================================================================ UE side
def texture_settings(key: str) -> dict:
    tcs, grp, mips = u.TextureCompressionSettings, u.TextureGroup, u.TextureMipGenSettings
    # compression first (it decides what sRGB may be), then sRGB, group, mips
    if key == "BC":
        wanted = {"compression_settings": tcs.TC_DEFAULT, "srgb": True, "lod_group": grp.TEXTUREGROUP_WORLD}
    elif key == "N":
        wanted = {"compression_settings": tcs.TC_NORMALMAP, "srgb": False,
                  "lod_group": grp.TEXTUREGROUP_WORLD_NORMAL_MAP, "flip_green_channel": False}
    elif key == "ORMH":
        wanted = {"compression_settings": tcs.TC_MASKS, "srgb": False, "lod_group": grp.TEXTUREGROUP_WORLD}
    elif key in ("Splat", "Aux"):
        wanted = {"compression_settings": tcs.TC_VECTOR_DISPLACEMENTMAP, "srgb": False,
                  "lod_group": grp.TEXTUREGROUP_WORLD, "address_x": u.TextureAddress.TA_CLAMP,
                  "address_y": u.TextureAddress.TA_CLAMP}
    else:
        raise KeyError(key)
    wanted.update({"mip_gen_settings": mips.TMGS_FROM_TEXTURE_GROUP, "never_stream": False,
                   "virtual_texture_streaming": False})
    return wanted


def settings_match(obj, wanted: dict) -> bool:
    return all(obj.get_editor_property(k) == v for k, v in wanted.items())


def describe_texture(t) -> dict:
    return {"srgb": bool(t.get_editor_property("srgb")), "compression": str(t.get_editor_property("compression_settings")),
            "lodGroup": str(t.get_editor_property("lod_group")), "sizeX": int(t.blueprint_get_size_x()),
            "sizeY": int(t.blueprint_get_size_y())}


def split(path: str) -> tuple[str, str]:
    folder, leaf = path.rsplit("/", 1)
    return folder, leaf


def import_texture(source: str, sha: str, asset: str, key: str, force: bool) -> dict:
    eal = u.EditorAssetLibrary
    wanted = texture_settings(key)
    tex = u.load_asset(asset) if eal.does_asset_exist(asset) else None
    if tex is not None and not force and eal.get_metadata_tag(tex, SHA_TAG) == sha and settings_match(tex, wanted):
        return {"action": "unchanged", **describe_texture(tex)}
    action = "reimported" if tex is not None else "imported"
    folder, leaf = split(asset)
    task = u.AssetImportTask()
    task.filename = source
    task.destination_path = folder
    task.destination_name = leaf
    task.automated = True
    task.replace_existing = True
    task.save = False
    u.AssetToolsHelpers.get_asset_tools().import_asset_tasks([task])
    tex = u.load_asset(asset)
    if tex is None or not isinstance(tex, u.Texture2D):
        raise RuntimeError(f"import of {source} did not produce the texture {asset}")
    for prop, value in wanted.items():
        tex.set_editor_property(prop, value)
    eal.set_metadata_tag(tex, SHA_TAG, sha)
    if not eal.save_loaded_asset(tex, False):
        raise RuntimeError(f"could not save {asset}")
    if not settings_match(tex, wanted):
        raise RuntimeError(f"{asset}: settings did not stick: {describe_texture(tex)}")
    return {"action": action, **describe_texture(tex)}


# --- HLSL of the Custom nodes (tools/art/env_kit/ground_splat.py mirrors the weights and the petals on the CPU) -------
HLSL_BOARD_XY = "return Strip.xy + UV * Strip.zw;"
HLSL_SPLAT_UV = "return (P - Rect.xy) / max(Rect.zw, float2(1.0, 1.0));"
HLSL_WEIGHTS = """// ENV-U10 M_EnvGround: height-lerp stack L3 over L2 over L1 over the base L0 (ground_splat.stacked_weights)
// L<k>_HeightBlend B<k> = how much the layer's height shapes its border (0: a plain soft lerp, 1: high points first)
float c = max(Contrast, 0.02);
float a1 = saturate((lerp(0.5, H1, B1) - 1.0 + Splat.r * (1.0 + c)) / c);
float a2 = saturate((lerp(0.5, H2, B2) - 1.0 + Splat.g * (1.0 + c)) / c);
float a3 = saturate((lerp(0.5, H3, B3) - 1.0 + Splat.b * (1.0 + c)) / c);
float w3 = a3;
float w2 = a2 * (1.0 - a3);
float w1 = a1 * (1.0 - a2) * (1.0 - a3);
return float4(saturate(1.0 - w1 - w2 - w3), w1, w2, w3);
"""
HLSL_WATER = """// P4 M_EnvGround: water / foam / depth from the aux mask (ground_splat.py: R water, G foam, B edge, A = 1 + depth * 254)
struct FEnvWaterFns {
  float Hash12(float2 p) {
    float3 p3 = frac(float3(p.xyx) * 0.1031);
    p3 += dot(p3, p3.yzx + 33.33);
    return frac((p3.x + p3.y) * p3.z);
  }
  float ValueNoise(float2 q) {
    float2 i0 = floor(q);
    float2 f = frac(q);
    float2 s = f * f * (3.0 - 2.0 * f);
    float a = Hash12(i0);
    float b = Hash12(i0 + float2(1.0, 0.0));
    float c = Hash12(i0 + float2(0.0, 1.0));
    float d = Hash12(i0 + float2(1.0, 1.0));
    return lerp(lerp(a, b, s.x), lerp(c, d, s.x), s.y);
  }
};
FEnvWaterFns F;
float water = saturate(Aux.r);
float depth = saturate((Aux.a * 255.0 - 1.0) / 254.0);
float2 q = (P + Time * WaterPan.xy * WaterRipple.w) / max(WaterRipple.z, 1.0);
float n = 0.6 * F.ValueNoise(q) + 0.4 * F.ValueNoise(q * 2.3 + 5.1);
float foam = saturate((Aux.g * (0.4 + 1.2 * n) - 0.25) * 2.0) * WaterFoam.a;
return float4(water, foam, depth, 0.0);
"""
HLSL_ALBEDO = """// ENV-U10 M_EnvGround: layer blend + macro variation + edge band + accent (petals / wetness) + water / foam
// + the M_MapBoard night grade (P4 graph 2: LayerMacro, EdgeTint, Water)
struct FEnvGroundFns {
  float Hash12(float2 p) {  // Dave Hoskins, hash without sine (ground_splat._hash12)
    float3 p3 = frac(float3(p.xyx) * 0.1031);
    p3 += dot(p3, p3.yzx + 33.33);
    return frac((p3.x + p3.y) * p3.z);
  }
  float ValueNoise(float2 q) {
    float2 i0 = floor(q);
    float2 f = frac(q);
    float2 s = f * f * (3.0 - 2.0 * f);
    float a = Hash12(i0);
    float b = Hash12(i0 + float2(1.0, 0.0));
    float c = Hash12(i0 + float2(0.0, 1.0));
    float d = Hash12(i0 + float2(1.0, 1.0));
    return lerp(lerp(a, b, s.x), lerp(c, d, s.x), s.y);
  }
  float3 Grade(float3 c, float4 t) {
    float luma = dot(c, float3(0.2126, 0.7152, 0.0722));
    return lerp(luma.xxx, c, t.a) * t.rgb;
  }
};
FEnvGroundFns F;
float lm = F.ValueNoise(P / max(LayerMacroScaleUU, 1.0) + 31.7) * 2.0 - 1.0;
float4 k = 1.0 + LayerMacro * lm;
float3 c = W.x * k.x * F.Grade(C0, T0) + W.y * k.y * F.Grade(C1, T1) + W.z * k.z * F.Grade(C2, T2) +
           W.w * k.w * F.Grade(C3, T3);
float2 q = P / max(MacroScaleUU, 1.0);
float m = 0.65 * F.ValueNoise(q) + 0.35 * F.ValueNoise(q * 2.03 + 17.0);
c *= 1.0 + MacroStrength * (m * 2.0 - 1.0);
c *= lerp(float3(1.0, 1.0, 1.0), EdgeTint.rgb, saturate(Edge) * EdgeTint.a);
float a = saturate((Accent * 255.0 - 1.0) / 254.0);
if (PetalSizeUU > 0.0) {
  float carpet = saturate(a * 1.5 - 0.3) * AccentCarpet;
  c = lerp(c, AccentColor * 0.5, carpet);
  float density = a * AccentOpacity;
  float2 pq = P / PetalSizeUU;
  float2 base = floor(pq);
  float speck = 0.0;
  float tone = 1.0;
  for (int dy = -1; dy <= 1; ++dy) {
    for (int dx = -1; dx <= 1; ++dx) {
      float2 cell = base + float2(dx, dy);
      float jx = F.Hash12(cell);
      float jy = F.Hash12(cell + float2(19.19, 7.7));
      float pick = F.Hash12(cell + float2(47.3, 11.1));
      float ang = F.Hash12(cell + float2(3.1, 91.7)) * 6.2831853;
      float2 o = pq - (cell + 0.15 + 0.7 * float2(jx, jy));
      float cs = cos(ang);
      float sn = sin(ang);
      float2 l = float2(o.x * cs + o.y * sn, -o.x * sn + o.y * cs);
      float e = (l.x / 0.36) * (l.x / 0.36) + (l.y / 0.2) * (l.y / 0.2);
      float hit = (1.0 - smoothstep(0.55, 1.0, e)) * (pick < density ? 1.0 : 0.0);
      if (hit > speck) {
        speck = hit;
        tone = 0.75 + 0.25 * jx;
      }
    }
  }
  c = lerp(c, AccentColor * tone, speck);
} else {
  c = lerp(c, c * AccentColor, a * AccentOpacity);
}
float3 shallow = lerp(c, WaterColor.rgb, WaterColor.a);
c = lerp(c, lerp(shallow, WaterColor.rgb, Water.z), Water.x);
c = lerp(c, WaterFoam.rgb, Water.y);
float3 lit = c * exp2(NightEV) * NightTint;
float luma = dot(lit, float3(0.2126, 0.7152, 0.0722));
return max(lerp(luma.xxx, lit, NightSaturation), 0.0);
"""
HLSL_NORMAL = """// P4 graph 2: per-layer normal strength, the water ripples (two panned samples) over the water
float4 s = LayerNormal * NormalStrength;
float2 xy = W.x * N0.xy * s.x + W.y * N1.xy * s.y + W.z * N2.xy * s.z + W.w * N3.xy * s.w;
float z = W.x * N0.z + W.y * N1.z + W.z * N2.z + W.w * N3.z;
float3 n = normalize(float3(xy, max(z, 0.001)));
float3 r = normalize(float3((R1.xy + R2.xy) * WaterSurface.z, 1.0));
return normalize(lerp(n, r, saturate(Water.x * (1.0 - 0.6 * Water.y))));
"""
HLSL_RIPPLE_UV1 = "return (P + Time * WaterPan.xy) / max(WaterRipple.x, 1.0);"
HLSL_RIPPLE_UV2 = "return (P + Time * WaterPan.zw) / max(WaterRipple.y, 1.0) + float2(0.37, 0.61);"
HLSL_AO = "return saturate(dot(W, float4(M0.r, M1.r, M2.r, M3.r)));"
HLSL_METAL = "return saturate(dot(W, float4(M0.b, M1.b, M2.b, M3.b)));"
HLSL_ROUGH = """float4 rr = max(float4(M0.g, M1.g, M2.g, M3.g) * LayerRoughScale, LayerRoughMin);
float r = dot(W, rr);
float a = saturate((Accent * 255.0 - 1.0) / 254.0) * AccentOpacity;
r = PetalSizeUU > 0.0 ? r : lerp(r, AccentRoughness, a);
r = lerp(r, EdgeRoughness, saturate(Edge) * EdgeTint.a);
r = lerp(r, WaterSurface.x, Water.x);
r = lerp(r, 0.7, Water.y);
return saturate(r);
"""
HLSL_SPECULAR = "return saturate(lerp(dot(W, LayerSpecular), WaterSurface.y, Water.x * (1.0 - Water.y)));"
HLSL_EMISSIVE = """// P4: the water glows a little like the lifted river of the map (M_MapBoard); 0 without water
float3 lit = WaterColor.rgb * exp2(NightEV) * NightTint;
float luma = dot(lit, float3(0.2126, 0.7152, 0.0722));
float3 g = max(lerp(luma.xxx, lit, NightSaturation), 0.0);
return g * WaterSurface.w * Water.x * (1.0 - Water.y);
"""

SCALAR_DEFAULTS = {"HeightContrast": 0.25, "NormalStrength": 1.0, "MacroStrength": 0.14, "MacroScaleUU": 240.0,
                   "AccentOpacity": 0.9, "AccentRoughness": 0.6, "AccentCarpet": 0.55, "PetalSizeUU": 7.0,
                   "NightEV": -0.7, "L1_HeightBlend": 1.0, "L2_HeightBlend": 1.0, "L3_HeightBlend": 1.0,
                   "NightSaturation": 0.7, "LayerMacroScaleUU": 33.0, "EdgeRoughness": 0.8}
VECTOR_DEFAULTS = {"LayerRoughMin": (0.0, 0.0, 0.0, 0.0), "LayerRoughScale": (1.0, 1.0, 1.0, 1.0),
                   "LayerSpecular": (0.4, 0.4, 0.4, 0.4), "LayerNormal": (1.0, 1.0, 1.0, 1.0),
                   "LayerMacro": (0.0, 0.0, 0.0, 0.0), "EdgeTint": (1.0, 1.0, 1.0, 0.0),
                   "WaterColor": (0.0159, 0.0497, 0.141, 0.55), "WaterFoam": (0.62, 0.66, 0.7, 0.0),
                   "WaterSurface": (0.06, 0.25, 0.55, 0.0), "WaterRipple": (70.0, 130.0, 9.0, 0.6),
                   "WaterPan": (2.5, 1.2, -1.4, 2.0)}


class _Graph:
    """Expression helpers of one material (MaterialEditingLibrary): nodes, parameters, Custom nodes, connections."""

    def __init__(self, material):
        self.material = material
        self.mel = u.MaterialEditingLibrary
        self.ypos = 0

    def expr(self, cls, x, y=None):
        node = self.mel.create_material_expression(self.material, cls, x, self.ypos if y is None else y)
        if node is None:
            raise RuntimeError(f"could not create {cls}")
        if y is None:
            self.ypos += 120
        return node

    def connect(self, src, out, dst, inp):
        if not self.mel.connect_material_expressions(src, out, dst, inp):
            raise RuntimeError(f"could not connect {src.get_name()}.{out or '<0>'} -> {dst.get_name()}.{inp}")

    def scalar(self, name, value):
        node = self.expr(u.MaterialExpressionScalarParameter, -2600)
        node.set_editor_property("parameter_name", name)
        node.set_editor_property("default_value", float(value))
        return node

    def vector(self, name, value):
        node = self.expr(u.MaterialExpressionVectorParameter, -2600)
        node.set_editor_property("parameter_name", name)
        node.set_editor_property("default_value", u.LinearColor(*[float(v) for v in value]))
        return node

    def custom(self, desc, out_type, inputs, code, x, y):
        node = self.expr(u.MaterialExpressionCustom, x, y)
        node.set_editor_property("description", desc)
        node.set_editor_property("output_type", out_type)
        pins = []
        for name in inputs:
            ci = u.CustomInput()
            ci.set_editor_property("input_name", name)
            pins.append(ci)
        node.set_editor_property("inputs", pins)
        node.set_editor_property("code", code)
        return node

    def sample(self, name, sampler_type, texture, source, x, y):
        node = self.expr(u.MaterialExpressionTextureSampleParameter2D, x, y)
        node.set_editor_property("parameter_name", name)
        node.set_editor_property("sampler_type", sampler_type)
        node.set_editor_property("texture", texture)  # after the sampler type: AutoSetSampleType keeps them consistent
        node.set_editor_property("sampler_source", source)
        return node

    def wire(self, node, sources: dict):
        """sources = {pin: (node, output)}"""
        for pin, (src, out) in sources.items():
            self.connect(src, out, node, pin)


def _begin_material(path: str, name: str, version: str, force: bool):
    eal = u.EditorAssetLibrary
    material = u.load_asset(path) if eal.does_asset_exist(path) else None
    if material is not None and not force and eal.get_metadata_tag(material, GRAPH_TAG) == version:
        return material, "unchanged"
    action = "rebuilt" if material is not None else "created"
    if material is None:
        material = u.AssetToolsHelpers.get_asset_tools().create_asset(name, ROOT, u.Material, u.MaterialFactoryNew())
    if material is None:
        raise RuntimeError(f"could not create {path}")
    u.MaterialEditingLibrary.delete_all_material_expressions(material)
    return material, action


def _finish_material(material, path: str, version: str) -> None:
    u.MaterialEditingLibrary.recompile_material(material)
    u.EditorAssetLibrary.set_metadata_tag(material, GRAPH_TAG, version)
    if not u.EditorAssetLibrary.save_loaded_asset(material, False):
        raise RuntimeError(f"could not save {path}")


def build_material(defaults: dict, splat_default, aux_default, ripple_default, force: bool) -> dict:
    """M_EnvGround (graph 2). defaults = {param name: texture} for the 12 layer textures (the first map's sets)."""
    material, action = _begin_material(MATERIAL_PATH, MATERIAL_NAME, GRAPH_VERSION, force)
    if action == "unchanged":
        return {"action": "unchanged", "path": MATERIAL_PATH, "graphVersion": GRAPH_VERSION}
    mel = u.MaterialEditingLibrary
    material.set_editor_property("shading_model", u.MaterialShadingModel.MSM_DEFAULT_LIT)
    material.set_editor_property("blend_mode", u.BlendMode.BLEND_OPAQUE)
    material.set_editor_property("two_sided", False)
    g = _Graph(material)
    cmot, st, ssm = u.CustomMaterialOutputType, u.MaterialSamplerType, u.SamplerSourceMode
    uv = g.expr(u.MaterialExpressionTextureCoordinate, -2600)
    uv.set_editor_property("coordinate_index", 0)
    t = g.expr(u.MaterialExpressionTime, -2600)
    strip = g.vector("GroundStrip", (-820.0, -560.0, 1640.0, 1030.0))
    rect = g.vector("SplatRect", (-820.0, -560.0, 1640.0, 1030.0))
    board = g.custom("GroundBoardXY", cmot.CMOT_FLOAT2, ("UV", "Strip"), HLSL_BOARD_XY, -2200, 0)
    g.wire(board, {"UV": (uv, ""), "Strip": (strip, "RGBA")})
    splat_uv = g.custom("GroundSplatUV", cmot.CMOT_FLOAT2, ("P", "Rect"), HLSL_SPLAT_UV, -1900, -300)
    g.wire(splat_uv, {"P": (board, ""), "Rect": (rect, "RGBA")})
    splat = g.sample("Splat", st.SAMPLERTYPE_LINEAR_COLOR, splat_default, ssm.SSM_CLAMP_WORLD_GROUP_SETTINGS, -1600, -300)
    g.connect(splat_uv, "", splat, "UVs")
    aux = g.sample("Aux", st.SAMPLERTYPE_LINEAR_COLOR, aux_default, ssm.SSM_CLAMP_WORLD_GROUP_SETTINGS, -1600, -520)
    g.connect(splat_uv, "", aux, "UVs")
    samples = {}
    for i in range(LAYERS):
        tile = g.scalar(f"L{i}_TileUU", 200.0)
        div = g.expr(u.MaterialExpressionDivide, -1900, 200 + 700 * i)
        g.connect(board, "", div, "A")
        g.connect(tile, "", div, "B")
        for k, (stype, dy) in {"BC": (st.SAMPLERTYPE_COLOR, 0), "N": (st.SAMPLERTYPE_NORMAL, 220),
                               "ORMH": (st.SAMPLERTYPE_MASKS, 440)}.items():
            node = g.sample(f"L{i}_{k}", stype, defaults[f"L{i}_{k}"], ssm.SSM_WRAP_WORLD_GROUP_SETTINGS, -1600,
                            200 + 700 * i + dy)
            g.connect(div, "", node, "UVs")
            samples[(i, k)] = node
    s = {name: g.scalar(name, SCALAR_DEFAULTS[name]) for name in SCALAR_DEFAULTS}
    v = {name: g.vector(name, VECTOR_DEFAULTS[name]) for name in VECTOR_DEFAULTS}
    tints = [g.vector(f"L{i}_Tint", (1.0, 1.0, 1.0, 1.0)) for i in range(LAYERS)]
    accent_color = g.vector("AccentColor", (0.87, 0.4, 0.51, 1.0))
    night_tint = g.vector("NightTint", (0.9317, 1.0042, 1.1595, 1.0))

    weights = g.custom("GroundWeights", cmot.CMOT_FLOAT4, ("Splat", "H1", "H2", "H3", "B1", "B2", "B3", "Contrast"),
                       HLSL_WEIGHTS, -1100, -300)
    g.connect(splat, "RGBA", weights, "Splat")
    for i in (1, 2, 3):
        g.connect(samples[(i, "ORMH")], "A", weights, f"H{i}")
        g.connect(s[f"L{i}_HeightBlend"], "", weights, f"B{i}")
    g.connect(s["HeightContrast"], "", weights, "Contrast")

    water = g.custom("GroundWater", cmot.CMOT_FLOAT4, ("Aux", "P", "Time", "WaterPan", "WaterRipple", "WaterFoam"),
                     HLSL_WATER, -1100, -600)
    g.wire(water, {"Aux": (aux, "RGBA"), "P": (board, ""), "Time": (t, ""), "WaterPan": (v["WaterPan"], "RGBA"),
                   "WaterRipple": (v["WaterRipple"], "RGBA"), "WaterFoam": (v["WaterFoam"], "RGBA")})
    ripple = {}
    for idx, code in ((1, HLSL_RIPPLE_UV1), (2, HLSL_RIPPLE_UV2)):
        ruv = g.custom(f"GroundRippleUV{idx}", cmot.CMOT_FLOAT2, ("P", "Time", "WaterPan", "WaterRipple"), code,
                       -1900, -900 - 220 * idx)
        g.wire(ruv, {"P": (board, ""), "Time": (t, ""), "WaterPan": (v["WaterPan"], "RGBA"),
                     "WaterRipple": (v["WaterRipple"], "RGBA")})
        node = g.sample("WaterRippleN", st.SAMPLERTYPE_NORMAL, ripple_default, ssm.SSM_WRAP_WORLD_GROUP_SETTINGS,
                        -1600, -900 - 220 * idx)
        g.connect(ruv, "", node, "UVs")
        ripple[idx] = node

    albedo_inputs = (["W"] + [f"C{i}" for i in range(LAYERS)] + [f"T{i}" for i in range(LAYERS)]
                     + ["P", "Accent", "AccentColor", "AccentOpacity", "AccentCarpet", "PetalSizeUU", "MacroStrength",
                        "MacroScaleUU", "LayerMacro", "LayerMacroScaleUU", "Edge", "EdgeTint", "Water", "WaterColor",
                        "WaterFoam", "NightEV", "NightSaturation", "NightTint"])
    albedo = g.custom("GroundAlbedo", cmot.CMOT_FLOAT3, albedo_inputs, HLSL_ALBEDO, -600, -300)
    g.connect(weights, "", albedo, "W")
    for i in range(LAYERS):
        g.connect(samples[(i, "BC")], "RGB", albedo, f"C{i}")
        g.connect(tints[i], "RGBA", albedo, f"T{i}")
    g.wire(albedo, {"P": (board, ""), "Accent": (splat, "A"), "AccentColor": (accent_color, "RGB"),
                    "Edge": (aux, "B"), "Water": (water, ""), "NightTint": (night_tint, "RGB")})
    for name in ("AccentOpacity", "AccentCarpet", "PetalSizeUU", "MacroStrength", "MacroScaleUU", "LayerMacroScaleUU",
                 "NightEV", "NightSaturation"):
        g.connect(s[name], "", albedo, name)
    for name in ("LayerMacro", "EdgeTint", "WaterColor", "WaterFoam"):
        g.connect(v[name], "RGBA", albedo, name)
    mel.connect_material_property(albedo, "", u.MaterialProperty.MP_BASE_COLOR)

    normal = g.custom("GroundNormal", cmot.CMOT_FLOAT3,
                      ["W"] + [f"N{i}" for i in range(LAYERS)]
                      + ["NormalStrength", "LayerNormal", "Water", "R1", "R2", "WaterSurface"], HLSL_NORMAL, -600, 300)
    g.connect(weights, "", normal, "W")
    for i in range(LAYERS):
        g.connect(samples[(i, "N")], "RGB", normal, f"N{i}")
    g.wire(normal, {"NormalStrength": (s["NormalStrength"], ""), "LayerNormal": (v["LayerNormal"], "RGBA"),
                    "Water": (water, ""), "R1": (ripple[1], "RGB"), "R2": (ripple[2], "RGB"),
                    "WaterSurface": (v["WaterSurface"], "RGBA")})
    mel.connect_material_property(normal, "", u.MaterialProperty.MP_NORMAL)

    orm_pins = ["W"] + [f"M{i}" for i in range(LAYERS)]
    for desc, code, prop, y in (("GroundAO", HLSL_AO, u.MaterialProperty.MP_AMBIENT_OCCLUSION, 600),
                                ("GroundMetallic", HLSL_METAL, u.MaterialProperty.MP_METALLIC, 900)):
        node = g.custom(desc, cmot.CMOT_FLOAT1, orm_pins, code, -600, y)
        g.connect(weights, "", node, "W")
        for i in range(LAYERS):
            g.connect(samples[(i, "ORMH")], "RGB", node, f"M{i}")
        mel.connect_material_property(node, "", prop)
    rough = g.custom("GroundRoughness", cmot.CMOT_FLOAT1,
                     orm_pins + ["Accent", "AccentOpacity", "AccentRoughness", "PetalSizeUU", "LayerRoughMin",
                                 "LayerRoughScale", "Edge", "EdgeTint", "EdgeRoughness", "Water", "WaterSurface"],
                     HLSL_ROUGH, -600, 750)
    g.connect(weights, "", rough, "W")
    for i in range(LAYERS):
        g.connect(samples[(i, "ORMH")], "RGB", rough, f"M{i}")
    g.wire(rough, {"Accent": (splat, "A"), "Edge": (aux, "B"), "Water": (water, "")})
    for name in ("AccentOpacity", "AccentRoughness", "PetalSizeUU", "EdgeRoughness"):
        g.connect(s[name], "", rough, name)
    for name in ("LayerRoughMin", "LayerRoughScale", "EdgeTint", "WaterSurface"):
        g.connect(v[name], "RGBA", rough, name)
    mel.connect_material_property(rough, "", u.MaterialProperty.MP_ROUGHNESS)
    spec = g.custom("GroundSpecular", cmot.CMOT_FLOAT1, ("W", "LayerSpecular", "Water", "WaterSurface"), HLSL_SPECULAR,
                    -600, 1050)
    g.wire(spec, {"W": (weights, ""), "LayerSpecular": (v["LayerSpecular"], "RGBA"), "Water": (water, ""),
                  "WaterSurface": (v["WaterSurface"], "RGBA")})
    mel.connect_material_property(spec, "", u.MaterialProperty.MP_SPECULAR)
    emis = g.custom("GroundEmissive", cmot.CMOT_FLOAT3,
                    ("Water", "WaterColor", "WaterSurface", "NightEV", "NightSaturation", "NightTint"), HLSL_EMISSIVE,
                    -600, 1200)
    g.wire(emis, {"Water": (water, ""), "WaterColor": (v["WaterColor"], "RGBA"),
                  "WaterSurface": (v["WaterSurface"], "RGBA"), "NightEV": (s["NightEV"], ""),
                  "NightSaturation": (s["NightSaturation"], ""), "NightTint": (night_tint, "RGB")})
    mel.connect_material_property(emis, "", u.MaterialProperty.MP_EMISSIVE_COLOR)

    _finish_material(material, MATERIAL_PATH, GRAPH_VERSION)
    return {"action": action, "path": MATERIAL_PATH, "graphVersion": GRAPH_VERSION,
            "expressions": int(mel.get_num_material_expressions(material)),
            "textureParams": sorted(str(n) for n in mel.get_texture_parameter_names(material))}


# --- P5c track W: Water Materials (tharlevfx, CC BY 4.0 - docs/art-pipeline/CREDITS-fab.md) ---------------------------
# Our derived materials (M_EnvSea graph 2, M_EnvWaterfall graph 3) sample four textures of the gitignored pack folder
# /Game/WaterMaterials by hard reference (the pack is never modified; the cooker follows the references from the
# always-cooked /Game/EnvKit). Sampler types as the pack's own materials use them (Scout T3D of M_Ocean / M_Waterfall /
# M_Rapids): T_Ocean_Foam Color (sRGB; R / G / B = three foam patterns), T_Water_Normal and T_Water_Normal_Large Normal,
# T_Waterfall_Foam LinearColor (R / G / B / A = four streak patterns); the UE stage still derives the sampler type from
# the texture's actual compression / sRGB (sampler_type_for). Without the pack (a fresh checkout) the materials build
# with stand-in textures and the MIs set the pack weight to 0: the graph 2 procedural look (reported as 'fallback').
PACK_ROOT = "/Game/WaterMaterials/Textures"
PACK_CONTENT_DIR = REPO / "unreal/Unmatched/Content/WaterMaterials/Textures"
PACK_TEXTURES = {  # material parameter -> (pack texture, sampler kind the pack uses)
    "SeaFoamTex": ("T_Ocean_Foam", "color"),
    "SeaNormalA": ("T_Water_Normal", "normal"),
    "SeaNormalB": ("T_Water_Normal_Large", "normal"),
    "FallStreakTex": ("T_Waterfall_Foam", "linear"),
}
SEA_PACK_PARAMS = ("SeaFoamTex", "SeaNormalA", "SeaNormalB")
PACK_FALLBACK_COLOR = "/Engine/EngineResources/DefaultTexture"


def pack_asset(param: str) -> str:
    name = PACK_TEXTURES[param][0]
    return f"{PACK_ROOT}/{name}"


def pack_plan() -> dict:
    """Plain Python: which pack textures are in the worktree Content (the UE stage loads them; missing = fallback)."""
    out = {}
    for param, (name, kind) in PACK_TEXTURES.items():
        f = PACK_CONTENT_DIR / f"{name}.uasset"
        out[param] = {"asset": pack_asset(param), "sampler": kind, "present": f.is_file()}
    return out


def sampler_type_for(texture):
    """UE: the material sampler type that matches a texture's compression / sRGB (a mismatch fails the compile)."""
    st, tcs = u.MaterialSamplerType, u.TextureCompressionSettings
    cs = texture.get_editor_property("compression_settings")
    srgb = bool(texture.get_editor_property("srgb"))

    def is_(name):
        return getattr(tcs, name, None) is not None and cs == getattr(tcs, name)
    if is_("TC_NORMALMAP"):
        return st.SAMPLERTYPE_NORMAL
    if is_("TC_MASKS"):
        return st.SAMPLERTYPE_MASKS
    if is_("TC_GRAYSCALE"):
        return st.SAMPLERTYPE_GRAYSCALE if srgb else st.SAMPLERTYPE_LINEAR_GRAYSCALE
    if is_("TC_ALPHA"):
        return st.SAMPLERTYPE_ALPHA
    return st.SAMPLERTYPE_COLOR if srgb else st.SAMPLERTYPE_LINEAR_COLOR


def load_pack(ripple) -> tuple[dict, dict]:
    """UE: ({param: texture}, {param: 'pack' | 'fallback'}) - the pack texture, else the ripple normal (normal slots) or
    the engine default texture (colour slots)."""
    eal = u.EditorAssetLibrary
    tex, src = {}, {}
    for param, (name, kind) in PACK_TEXTURES.items():
        path = pack_asset(param)
        t = u.load_asset(path) if eal.does_asset_exist(path) else None
        if t is not None:
            tex[param], src[param] = t, "pack"
        else:
            tex[param] = ripple if kind == "normal" else u.load_asset(PACK_FALLBACK_COLOR)
            src[param] = "fallback"
    return tex, src


# --- M_EnvWaterfall (P4, review gap 1; P5c graph 3): the waterfall sheet / foam / mist + the spill over the T2 lip ----
HLSL_FALL_CORE = """// P5c M_EnvWaterfall graph 3: FallCard = (width uu, height uu, kind: 0 the vertical card / 1 the flat spill, flip)
struct FEnvFallFns {
  float Hash12(float2 p) {
    float3 p3 = frac(float3(p.xyx) * 0.1031);
    p3 += dot(p3, p3.yzx + 33.33);
    return frac((p3.x + p3.y) * p3.z);
  }
  float ValueNoise(float2 q) {
    float2 i0 = floor(q);
    float2 f = frac(q);
    float2 s = f * f * (3.0 - 2.0 * f);
    float a = Hash12(i0);
    float b = Hash12(i0 + float2(1.0, 0.0));
    float c = Hash12(i0 + float2(0.0, 1.0));
    float d = Hash12(i0 + float2(1.0, 1.0));
    return lerp(lerp(a, b, s.x), lerp(c, d, s.x), s.y);
  }
};
FEnvFallFns F;
float2 size = max(FallCard.xy, float2(1.0, 1.0));
bool spill = FallCard.z > 0.5;
// FallCard.w = 1: a lane K mesh (P5 tune) - its v was authored top->bottom in Blender and the FBX import flips V
float2 uvf = FallCard.w > 0.5 ? float2(UV.x, 1.0 - UV.y) : UV;
float2 p = uvf * size;  // uu: x across the fall, y along the flow (down the card / towards the lip on the spill)
float sc = max(FallFlow.y, 1.0);
float2 q = float2(p.x / sc, (p.y - Time * FallFlow.x) / (sc * 5.0));
float streakP = 0.6 * F.ValueNoise(q) + 0.4 * F.ValueNoise(q * float2(2.1, 1.7) + 7.3);
// P5c: the Water Materials streaks (T_Waterfall_Foam, two layers panned down the fall at two speeds), else graph 2 noise
float streakT = saturate(0.55 * StreakA.r + 0.45 * StreakB.g);
float streak = lerp(streakP, streakT, saturate(FallLook.w));
float foam = spill ? saturate(uvf.y * 1.4 - 0.5) * (0.5 + streak)
                   : saturate(streak * 1.5 - 0.35) * (0.55 + 0.45 * saturate(1.0 - uvf.y * 1.5)) + 0.6 * saturate(1.0 - p.y / 14.0);
foam = saturate(foam) * WaterFoam.a;
// soft sides whose width wobbles along the flow (no straight rectangular outline; FallLook.z = wobble 0..1)
float2 wq = float2(0.0, (p.y - Time * FallFlow.x * 0.5) / 29.0);
float ewl = max(FallFlow.z * (1.0 + FallLook.z * (F.ValueNoise(wq + float2(1.3, 0.0)) - 0.5) * 1.6), 0.5);
float ewr = max(FallFlow.z * (1.0 + FallLook.z * (F.ValueNoise(wq + float2(8.9, 0.0)) - 0.5) * 1.6), 0.5);
float side = smoothstep(0.0, ewl, p.x) * smoothstep(0.0, ewr, size.x - p.x);
float along = spill ? smoothstep(0.0, max(FallSpill.x, 0.5), p.y)
                    : 1.0 - smoothstep(1.0 - FallFlow.w, 1.0, uvf.y + 0.25 * (streak - 0.5));
// translucent body: the water clear-ish (FallLook.x), the foam / streaks nearly opaque (FallLook.y)
float alphaT = saturate(side * along * lerp(FallLook.x, FallLook.y, foam) * (0.85 + 0.3 * streak));
// the graph 2 masked opacity (an MI may override the blend mode back to Masked: ground-params falls[].blend)
float alphaM = side * along * (0.75 + 0.5 * streak);
float3 base = lerp(WaterColor.rgb, WaterFoam.rgb, foam);
float3 lit = base * exp2(NightEV) * NightTint;
float luma = dot(lit, float3(0.2126, 0.7152, 0.0722));
float3 graded = max(lerp(luma.xxx, lit, NightSaturation), 0.0);
"""
FALL_CORE_INPUTS = ("UV", "Time", "FallCard", "FallFlow", "FallSpill", "FallLook", "StreakA", "StreakB", "WaterColor",
                    "WaterFoam", "NightEV", "NightSaturation", "NightTint")
HLSL_FALL_ALBEDO = HLSL_FALL_CORE + "return graded;\n"
HLSL_FALL_EMISSIVE = HLSL_FALL_CORE + "return graded * FallShade.w;\n"
HLSL_FALL_OPACITY = HLSL_FALL_CORE + "return alphaT;\n"
HLSL_FALL_OPACITY_MASK = HLSL_FALL_CORE + """// screen-space dither of the soft fades (masked override only: clip 0.5; TSR smooths it)
float2 px = Parameters.SvPosition.xy;
float ign = frac(52.9829189 * frac(dot(px, float2(0.06711056, 0.00583715))));
return saturate(alphaM + (ign - 0.5) * FallSpill.y);
"""
HLSL_FALL_ROUGH = HLSL_FALL_CORE + "return saturate(lerp(FallShade.x, 0.6, foam));\n"
HLSL_FALL_RIPPLE_UV = """float2 p = (FallCard.w > 0.5 ? float2(UV.x, 1.0 - UV.y) : UV) * max(FallCard.xy, float2(1.0, 1.0));
return float2(p.x, p.y - Time * FallFlow.x) / max(RippleTileUU, 1.0);
"""
# the two streak layers: uu across / along the flow (FallTex.xy), the second one faster (FallTex.z) and offset
HLSL_FALL_STREAK_UV1 = """float2 p = (FallCard.w > 0.5 ? float2(UV.x, 1.0 - UV.y) : UV) * max(FallCard.xy, float2(1.0, 1.0));
return float2(p.x / max(FallTex.x, 1.0), (p.y - Time * FallFlow.x) / max(FallTex.y, 1.0));
"""
HLSL_FALL_STREAK_UV2 = """float2 p = (FallCard.w > 0.5 ? float2(UV.x, 1.0 - UV.y) : UV) * max(FallCard.xy, float2(1.0, 1.0));
return float2(p.x / max(FallTex.x * 0.71, 1.0) + 0.37, (p.y - Time * FallFlow.x * max(FallTex.z, 0.1)) / max(FallTex.y * 1.3, 1.0));
"""
HLSL_FALL_NORMAL = "return normalize(float3(R.xy * FallShade.z, 1.0));"
HLSL_FALL_SPECULAR = "return saturate(FallShade.y);"
FALL_SCALAR_DEFAULTS = {"NightEV": -1.0, "NightSaturation": 0.7, "RippleTileUU": 70.0}
FALL_VECTOR_DEFAULTS = {"FallCard": (200.0, 230.0, 0.0, 0.0), "FallFlow": (55.0, 9.0, 12.0, 0.35),
                        "FallSpill": (18.0, 0.5, 0.0, 0.0), "FallShade": (0.08, 0.25, 0.5, 0.6),
                        "FallLook": (0.55, 0.95, 0.6, 0.0), "FallTex": (36.0, 110.0, 1.6, 0.0),
                        "WaterColor": (0.0159, 0.0497, 0.141, 0.55), "WaterFoam": (0.62, 0.66, 0.7, 0.85),
                        "NightTint": (0.9317, 1.0042, 1.1595, 1.0)}
FALL_BLENDS = ("translucent", "masked")


def _translucent_lit(material) -> dict:
    """Lit translucent with per-pixel surface lighting (the sheet takes the key light and its specular like an opaque
    surface; the volumetric default reads flat). Engine-version dependent names are reported, not assumed."""
    material.set_editor_property("blend_mode", u.BlendMode.BLEND_TRANSLUCENT)
    flags = {}
    tlm = getattr(getattr(u, "TranslucencyLightingMode", None), "TLM_SURFACE_PER_PIXEL_LIGHTING", None)
    if tlm is not None:
        try:
            material.set_editor_property("translucency_lighting_mode", tlm)
            flags["translucencyLightingMode"] = "TLM_SURFACE_PER_PIXEL_LIGHTING"
        except Exception as exc:  # noqa: BLE001 - engine-version dependent
            flags["translucencyLightingMode"] = f"n/a ({type(exc).__name__}: {exc})"
    else:
        flags["translucencyLightingMode"] = "n/a (enum missing: engine default)"
    return flags


def build_waterfall_material(ripple_default, streak_default, force: bool) -> dict:
    material, action = _begin_material(FALL_MATERIAL_PATH, FALL_MATERIAL_NAME, FALL_GRAPH_VERSION, force)
    if action == "unchanged":
        return {"action": "unchanged", "path": FALL_MATERIAL_PATH, "graphVersion": FALL_GRAPH_VERSION}
    mel = u.MaterialEditingLibrary
    material.set_editor_property("shading_model", u.MaterialShadingModel.MSM_DEFAULT_LIT)
    flags = _translucent_lit(material)
    material.set_editor_property("opacity_mask_clip_value", 0.5)  # the masked MI override (falls[].blend 'masked')
    material.set_editor_property("two_sided", True)
    g = _Graph(material)
    cmot, ssm = u.CustomMaterialOutputType, u.SamplerSourceMode
    uv = g.expr(u.MaterialExpressionTextureCoordinate, -2000)
    uv.set_editor_property("coordinate_index", 0)
    t = g.expr(u.MaterialExpressionTime, -2000)
    s = {name: g.scalar(name, val) for name, val in FALL_SCALAR_DEFAULTS.items()}
    v = {name: g.vector(name, val) for name, val in FALL_VECTOR_DEFAULTS.items()}
    src = {"UV": (uv, ""), "Time": (t, ""), "NightEV": (s["NightEV"], ""),
           "NightSaturation": (s["NightSaturation"], ""), "NightTint": (v["NightTint"], "RGB")}
    for name in ("FallCard", "FallFlow", "FallSpill", "FallLook", "FallTex", "WaterColor", "WaterFoam", "FallShade"):
        src[name] = (v[name], "RGBA")
    streak_type = sampler_type_for(streak_default)
    for idx, code in ((1, HLSL_FALL_STREAK_UV1), (2, HLSL_FALL_STREAK_UV2)):
        suv = g.custom(f"FallStreakUV{idx}", cmot.CMOT_FLOAT2, ("UV", "Time", "FallCard", "FallFlow", "FallTex"), code,
                       -1500, 1100 + 220 * idx)
        g.wire(suv, {k: src[k] for k in ("UV", "Time", "FallCard", "FallFlow", "FallTex")})
        node = g.sample("FallStreakTex", streak_type, streak_default, ssm.SSM_WRAP_WORLD_GROUP_SETTINGS, -1200,
                        1100 + 220 * idx)
        g.connect(suv, "", node, "UVs")
        src["StreakA" if idx == 1 else "StreakB"] = (node, "RGBA")
    nodes = {}
    for desc, code, out_type, extra, y in (
            ("FallAlbedo", HLSL_FALL_ALBEDO, cmot.CMOT_FLOAT3, (), -300),
            ("FallEmissive", HLSL_FALL_EMISSIVE, cmot.CMOT_FLOAT3, ("FallShade",), 0),
            ("FallOpacity", HLSL_FALL_OPACITY, cmot.CMOT_FLOAT1, (), 300),
            ("FallOpacityMask", HLSL_FALL_OPACITY_MASK, cmot.CMOT_FLOAT1, (), 450),
            ("FallRoughness", HLSL_FALL_ROUGH, cmot.CMOT_FLOAT1, ("FallShade",), 600)):
        pins = FALL_CORE_INPUTS + extra
        node = g.custom(desc, out_type, pins, code, -800, y)
        g.wire(node, {p_: src[p_] for p_ in pins})
        nodes[desc] = node
    ruv = g.custom("FallRippleUV", cmot.CMOT_FLOAT2, ("UV", "Time", "FallCard", "FallFlow", "RippleTileUU"),
                   HLSL_FALL_RIPPLE_UV, -1500, 900)
    g.wire(ruv, {"UV": src["UV"], "Time": src["Time"], "FallCard": src["FallCard"], "FallFlow": src["FallFlow"],
                 "RippleTileUU": (s["RippleTileUU"], "")})
    rs = g.sample("WaterRippleN", u.MaterialSamplerType.SAMPLERTYPE_NORMAL, ripple_default,
                  ssm.SSM_WRAP_WORLD_GROUP_SETTINGS, -1200, 900)
    g.connect(ruv, "", rs, "UVs")
    normal = g.custom("FallNormal", cmot.CMOT_FLOAT3, ("R", "FallShade"), HLSL_FALL_NORMAL, -800, 900)
    g.wire(normal, {"R": (rs, "RGB"), "FallShade": src["FallShade"]})
    spec = g.custom("FallSpecular", cmot.CMOT_FLOAT1, ("FallShade",), HLSL_FALL_SPECULAR, -800, 1100)
    g.wire(spec, {"FallShade": src["FallShade"]})
    mel.connect_material_property(nodes["FallAlbedo"], "", u.MaterialProperty.MP_BASE_COLOR)
    mel.connect_material_property(nodes["FallEmissive"], "", u.MaterialProperty.MP_EMISSIVE_COLOR)
    mel.connect_material_property(nodes["FallOpacity"], "", u.MaterialProperty.MP_OPACITY)
    mel.connect_material_property(nodes["FallOpacityMask"], "", u.MaterialProperty.MP_OPACITY_MASK)
    mel.connect_material_property(nodes["FallRoughness"], "", u.MaterialProperty.MP_ROUGHNESS)
    mel.connect_material_property(normal, "", u.MaterialProperty.MP_NORMAL)
    mel.connect_material_property(spec, "", u.MaterialProperty.MP_SPECULAR)
    _finish_material(material, FALL_MATERIAL_PATH, FALL_GRAPH_VERSION)
    return {"action": action, "path": FALL_MATERIAL_PATH, "graphVersion": FALL_GRAPH_VERSION, "blend": "translucent",
            "flags": flags, "expressions": int(mel.get_num_material_expressions(material))}


# --- M_EnvSea (P5 track B, review gap 8; P5c graph 2): the sea ring under the Sarpedon island ---------------------------
# Graph 2 stays OPAQUE (lit, one-sided). The pack's M_Ocean was not used as is: it is translucent and depth-faded (it
# needs a seabed under the ring, adds translucency over Lumen, its waves are world-scale WPO at 1024..8192 uu and its
# colour depends on the depth below) - with an opaque ring the measured surround / map ratio and the background band
# stay predictable, and the pack's own foam / normal textures give the waves, the surf and the whiter foam here.
HLSL_SEA_CORE = """// P5c M_EnvSea graph 2: VC.r = the foam band at the cliffs, VC.g = the far fade, UV1.y = distance from the inner ring
// edge / 1000 uu (lane K SM_Env_S_SeaRing; the FBX import flips V: SeaSurf.w = 1), UV0 = XY / SeaTile.x
struct FEnvSeaFns {
  float Hash12(float2 p) {
    float3 p3 = frac(float3(p.xyx) * 0.1031);
    p3 += dot(p3, p3.yzx + 33.33);
    return frac((p3.x + p3.y) * p3.z);
  }
  float ValueNoise(float2 q) {
    float2 i0 = floor(q);
    float2 f = frac(q);
    float2 s = f * f * (3.0 - 2.0 * f);
    float a = Hash12(i0);
    float b = Hash12(i0 + float2(1.0, 0.0));
    float c = Hash12(i0 + float2(0.0, 1.0));
    float d = Hash12(i0 + float2(1.0, 1.0));
    return lerp(lerp(a, b, s.x), lerp(c, d, s.x), s.y);
  }
};
FEnvSeaFns F;
float2 p = UV * max(SeaTile.x, 1.0);  // board uu
float far = saturate(VC.g) * SeaFar.a;
float nearW = 1.0 - saturate(VC.g);
// lace: the pack foam (T_Ocean_Foam, two pans) or the graph 1 value noise (SeaPack.x = 0: no pack)
float sc = max(SeaFlow.z, 1.0);
float n = 0.6 * F.ValueNoise(p / sc + Time * SeaFlow.w * float2(0.7, 0.3))
        + 0.4 * F.ValueNoise(p / (sc * 0.43) - Time * SeaFlow.w * float2(0.2, 0.6) + 5.1);
float lace = lerp(n, saturate(0.6 * FoamA.r + 0.4 * FoamB.g), saturate(SeaPack.x));
// shore foam: the VC.r band at the cliffs, sharper (SeaPack.z) from the threshold SeaPack.w, broken by the lace
float shore = saturate((saturate(VC.r) * (0.55 + 0.9 * lace) - SeaPack.w) * max(SeaPack.z, 0.5)) * SeaFoam.a;
// surf: crest lines parallel to the cliffs, running in towards them (SeaSurf = spacing uu, cycles / s, reach uu, flip)
float d = (SeaSurf.w > 0.5 ? 1.0 - UV1.y : UV1.y) * 1000.0;
float ph = d / max(SeaSurf.x, 1.0) + Time * SeaSurf.y + (F.ValueNoise(p / 70.0 + 3.7) - 0.5) * 0.9;
float x = frac(ph);
float w = clamp(SeaSurfLook.x, 0.02, 0.9);
float crest = smoothstep(1.0 - w, 1.0 - 0.8 * w, x) * (1.0 - smoothstep(1.0 - 0.8 * w, 1.0, x));
float env = 1.0 - smoothstep(0.35 * max(SeaSurf.z, 1.0), max(SeaSurf.z, 1.0), d);
float surf = crest * env * lerp(1.0, smoothstep(0.3, 0.65, lace), saturate(SeaSurfLook.z)) * SeaSurfLook.y;
// waves: two panned normals (pack T_Water_Normal / _Large, else the ripple) -> a facet shade towards SeaWaveDir and
// sparse whitecaps on the lit facets
float2 slope = NA.xy * 0.6 + NB.xy * 0.4;
float shade = dot(slope, normalize(SeaWaveDir.xy + float2(1e-4, 0.0)));
float waveShade = clamp(shade * SeaWave.x, -0.6, 0.6) * nearW;
float caps = lace * (0.6 + 0.8 * F.ValueNoise(p / 260.0 + Time * 0.02 * float2(1.0, 0.4)));
float whitecap = smoothstep(SeaWave.z, SeaWave.z + 0.12, caps) * saturate(0.5 + 2.0 * shade) * SeaWave.y
               * nearW * nearW * nearW;
float foam = saturate(max(max(shore, surf), whitecap));
float3 water = SeaColor.rgb * max(1.0 + waveShade, 0.0);
float3 base = lerp(lerp(water, SeaFoam.rgb, foam), SeaFar.rgb, far * (1.0 - foam));
float3 lit = base * exp2(NightEV) * NightTint;
float luma = dot(lit, float3(0.2126, 0.7152, 0.0722));
float3 graded = max(lerp(luma.xxx, lit, NightSaturation), 0.0);
// sky lift (P5c): the open sea mirrors a dim night sky with slow cloud reflections (SeaSky rgb x a; SeaSkyNoise = scale
// uu, amplitude, pan uu / s; SeaSkyRamp = VC.g where it starts / is full, the share already at the cliffs) - the only
// background the opaque ring leaves visible around the island
float skyW = lerp(saturate(SeaSkyRamp.z), 1.0, smoothstep(SeaSkyRamp.x, max(SeaSkyRamp.y, SeaSkyRamp.x + 0.001), saturate(VC.g)));
float2 cq = p / max(SeaSkyNoise.x, 1.0) + Time * SeaSkyNoise.z / max(SeaSkyNoise.x, 1.0) * float2(0.6, 0.2);
float cloud = 0.65 * F.ValueNoise(cq) + 0.35 * F.ValueNoise(cq * 2.2 + 9.2);
float3 sky = SeaSky.rgb * SeaSky.a * skyW * max(1.0 + SeaSkyNoise.y * (cloud - 0.5) * 2.0, 0.0);
"""
SEA_CORE_INPUTS = ("UV", "UV1", "Time", "VC", "FoamA", "FoamB", "NA", "NB", "SeaColor", "SeaFar", "SeaFoam", "SeaFlow",
                   "SeaTile", "SeaPack", "SeaSurf", "SeaSurfLook", "SeaWave", "SeaWaveDir", "SeaSky", "SeaSkyNoise",
                   "SeaSkyRamp", "NightEV", "NightSaturation", "NightTint")
HLSL_SEA_ALBEDO = HLSL_SEA_CORE + "return graded;\n"
HLSL_SEA_EMISSIVE = HLSL_SEA_CORE + ("return graded * (SeaShade.w * (1.0 - far) * (1.0 - foam) + SeaSurfLook.w * foam)"
                                     " + sky;\n")
HLSL_SEA_ROUGH = HLSL_SEA_CORE + "return saturate(lerp(lerp(SeaShade.x, 0.7, foam), 0.95, far));\n"
HLSL_SEA_SPECULAR = HLSL_SEA_CORE + "return saturate(SeaShade.y * (1.0 - far));\n"
HLSL_SEA_NORMAL = """float2 slope = NA.xy * 0.6 + NB.xy * 0.4;
return normalize(float3(slope * SeaShade.z * (1.0 - saturate(VC.g)), 1.0));
"""
# sample UVs (board uu p = UV0 * SeaTile.x): normals A / B at SeaWaveTile.x / .y uu panned by SeaFlow.xy (B rotated,
# slower, opposite), foam A / B at SeaPack.y uu drifting at SeaFlow.w * 0.1 tiles / s
HLSL_SEA_UV_NA = """float2 p = UV * max(SeaTile.x, 1.0);
return (p + Time * SeaFlow.xy) / max(SeaWaveTile.x, 1.0);
"""
HLSL_SEA_UV_NB = """float2 p = UV * max(SeaTile.x, 1.0);
float2 r = float2(p.x * 0.8 - p.y * 0.6, p.x * 0.6 + p.y * 0.8);
return (r - Time * SeaFlow.yx * 0.6) / max(SeaWaveTile.y, 1.0);
"""
HLSL_SEA_UV_FA = """float2 p = UV * max(SeaTile.x, 1.0);
return p / max(SeaPack.y, 1.0) + Time * SeaFlow.w * 0.1 * float2(0.7, 0.3);
"""
HLSL_SEA_UV_FB = """float2 p = UV * max(SeaTile.x, 1.0);
float2 r = float2(p.x * 0.6 + p.y * 0.8, -p.x * 0.8 + p.y * 0.6);
return r / max(SeaPack.y * 1.37, 1.0) - Time * SeaFlow.w * 0.07 * float2(0.2, 0.6) + 0.31;
"""
SEA_UV_NODES = (("NA", "SeaNormalA", HLSL_SEA_UV_NA, "SeaWaveTile"), ("NB", "SeaNormalB", HLSL_SEA_UV_NB, "SeaWaveTile"),
                ("FoamA", "SeaFoamTex", HLSL_SEA_UV_FA, "SeaPack"), ("FoamB", "SeaFoamTex", HLSL_SEA_UV_FB, "SeaPack"))
SEA_SCALAR_DEFAULTS = {"NightEV": -1.0, "NightSaturation": 0.85}
# the defaults keep the graph 1 look apart from the textures: no pack (procedural lace), shore sharpness 2 from 0.3,
# no surf / whitecaps / wave shade / sky lift; ground-params 'sea' turns them on
SEA_VECTOR_DEFAULTS = {"SeaColor": (0.0052, 0.0160, 0.0423, 1.0), "SeaFar": (0.0018, 0.0033, 0.0070, 1.0),
                       "SeaFoam": (0.62, 0.66, 0.7, 0.7), "SeaFlow": (3.0, 1.5, 14.0, 0.3),
                       "SeaTile": (600.0, 160.0, 0.0, 0.0), "SeaShade": (0.08, 0.3, 0.5, 1.5),
                       "SeaPack": (0.0, 70.0, 2.0, 0.3), "SeaSurf": (30.0, 0.12, 150.0, 1.0),
                       "SeaSurfLook": (0.35, 0.0, 0.6, 1.5), "SeaWave": (0.0, 0.0, 0.65, 0.0),
                       "SeaWaveDir": (-0.87, 0.5, 0.0, 0.0), "SeaWaveTile": (140.0, 420.0, 0.0, 0.0),
                       "SeaSky": (0.0, 0.0, 0.0, 0.0), "SeaSkyNoise": (700.0, 0.0, 4.0, 0.0),
                       "SeaSkyRamp": (0.0, 0.1, 0.0, 0.0),
                       "NightTint": (0.97, 1.0, 1.08, 1.0)}


def build_sea_material(pack_tex: dict, force: bool) -> dict:
    material, action = _begin_material(SEA_MATERIAL_PATH, SEA_MATERIAL_NAME, SEA_GRAPH_VERSION, force)
    if action == "unchanged":
        return {"action": "unchanged", "path": SEA_MATERIAL_PATH, "graphVersion": SEA_GRAPH_VERSION}
    mel = u.MaterialEditingLibrary
    material.set_editor_property("shading_model", u.MaterialShadingModel.MSM_DEFAULT_LIT)
    material.set_editor_property("blend_mode", u.BlendMode.BLEND_OPAQUE)
    material.set_editor_property("two_sided", False)
    g = _Graph(material)
    cmot, ssm = u.CustomMaterialOutputType, u.SamplerSourceMode
    uv = g.expr(u.MaterialExpressionTextureCoordinate, -2000)
    uv.set_editor_property("coordinate_index", 0)
    uv1 = g.expr(u.MaterialExpressionTextureCoordinate, -2000)
    uv1.set_editor_property("coordinate_index", 1)
    t = g.expr(u.MaterialExpressionTime, -2000)
    vc = g.expr(u.MaterialExpressionVertexColor, -2000)
    s = {name: g.scalar(name, val) for name, val in SEA_SCALAR_DEFAULTS.items()}
    v = {name: g.vector(name, val) for name, val in SEA_VECTOR_DEFAULTS.items()}
    src = {"UV": (uv, ""), "UV1": (uv1, ""), "Time": (t, ""), "VC": (vc, ""), "NightEV": (s["NightEV"], ""),
           "NightSaturation": (s["NightSaturation"], ""), "NightTint": (v["NightTint"], "RGB")}
    for name in SEA_VECTOR_DEFAULTS:
        if name != "NightTint":
            src[name] = (v[name], "RGBA")
    for i, (pin, param, code, tile) in enumerate(SEA_UV_NODES):
        uv_pins = ("UV", "Time", "SeaTile", "SeaFlow", tile)
        node_uv = g.custom(f"Sea{pin}UV", cmot.CMOT_FLOAT2, uv_pins, code, -1500, 900 + 220 * i)
        g.wire(node_uv, {k: src[k] for k in uv_pins})
        tex = pack_tex[param]
        node = g.sample(param, sampler_type_for(tex), tex, ssm.SSM_WRAP_WORLD_GROUP_SETTINGS, -1200, 900 + 220 * i)
        g.connect(node_uv, "", node, "UVs")
        src[pin] = (node, "RGB" if pin in ("NA", "NB") else "RGBA")
    nodes = {}
    for desc, code, out_type, extra, y in (
            ("SeaAlbedo", HLSL_SEA_ALBEDO, cmot.CMOT_FLOAT3, (), -300),
            ("SeaEmissive", HLSL_SEA_EMISSIVE, cmot.CMOT_FLOAT3, ("SeaShade",), 0),
            ("SeaRoughness", HLSL_SEA_ROUGH, cmot.CMOT_FLOAT1, ("SeaShade",), 300),
            ("SeaSpecular", HLSL_SEA_SPECULAR, cmot.CMOT_FLOAT1, ("SeaShade",), 600)):
        pins = SEA_CORE_INPUTS + extra
        node = g.custom(desc, out_type, pins, code, -800, y)
        g.wire(node, {p_: src[p_] for p_ in pins})
        nodes[desc] = node
    normal = g.custom("SeaNormal", cmot.CMOT_FLOAT3, ("NA", "NB", "SeaShade", "VC"), HLSL_SEA_NORMAL, -800, 900)
    g.wire(normal, {k: src[k] for k in ("NA", "NB", "SeaShade", "VC")})
    mel.connect_material_property(nodes["SeaAlbedo"], "", u.MaterialProperty.MP_BASE_COLOR)
    mel.connect_material_property(nodes["SeaEmissive"], "", u.MaterialProperty.MP_EMISSIVE_COLOR)
    mel.connect_material_property(nodes["SeaRoughness"], "", u.MaterialProperty.MP_ROUGHNESS)
    mel.connect_material_property(nodes["SeaSpecular"], "", u.MaterialProperty.MP_SPECULAR)
    mel.connect_material_property(normal, "", u.MaterialProperty.MP_NORMAL)
    _finish_material(material, SEA_MATERIAL_PATH, SEA_GRAPH_VERSION)
    return {"action": action, "path": SEA_MATERIAL_PATH, "graphVersion": SEA_GRAPH_VERSION,
            "expressions": int(mel.get_num_material_expressions(material))}


def _sub(block: dict, name: str) -> dict:
    v = block.get(name)
    return v if isinstance(v, dict) else {}


def _np_hash12(px, py):
    """FEnvSeaFns::Hash12 in numpy (float64; the shader's float32 differs in the last bits only)."""
    import numpy as np
    x, y = np.asarray(px, float), np.asarray(py, float)
    p3 = np.stack([x, y, x], -1) * 0.1031
    p3 = p3 - np.floor(p3)
    dot = (p3 * (p3[..., [1, 2, 0]] + 33.33)).sum(-1)
    p3 = p3 + dot[..., None]
    v = (p3[..., 0] + p3[..., 1]) * p3[..., 2]
    return v - np.floor(v)


def _np_value_noise(qx, qy):
    import numpy as np
    qx, qy = np.asarray(qx, float), np.asarray(qy, float)
    ix, iy = np.floor(qx), np.floor(qy)
    fx, fy = qx - ix, qy - iy
    sx, sy = fx * fx * (3 - 2 * fx), fy * fy * (3 - 2 * fy)
    a, b = _np_hash12(ix, iy), _np_hash12(ix + 1, iy)
    c, d = _np_hash12(ix, iy + 1), _np_hash12(ix + 1, iy + 1)
    return (a + (b - a) * sx) * (1 - sy) + (c + (d - c) * sx) * sy


def _np_sstep(e0, e1, x):
    import numpy as np
    t = np.clip((np.asarray(x, float) - e0) / (e1 - e0), 0.0, 1.0)
    return t * t * (3 - 2 * t)


def sea_cpu(want: dict, px, py, d_uu, vc_r, vc_g, t: float = 0.0, lace_tex=None, slope=(0.0, 0.0)) -> dict:
    """numpy mirror of HLSL_SEA_CORE + the emissive (plain Python; statistics / tests, not a render). px, py = board
    uu (p = UV0 * SeaTile.x), d_uu = distance from the inner ring edge (UV1, already unflipped), vc_r / vc_g = the ring
    vertex colours, lace_tex = the pack lace 0.6 FoamA.r + 0.4 FoamB.g (None: 0.5), slope = (NA, NB) mixed xy."""
    import numpy as np
    v, sc_ = want["vector"], want["scalar"]
    px, py, d_uu = (np.asarray(a, float) for a in (px, py, d_uu))
    vc_r, vc_g = np.clip(np.asarray(vc_r, float), 0, 1), np.clip(np.asarray(vc_g, float), 0, 1)
    flow, pack, surf_v, look = v["SeaFlow"], v["SeaPack"], v["SeaSurf"], v["SeaSurfLook"]
    far = vc_g * v["SeaFar"][3]
    near = 1.0 - vc_g
    sc = max(flow[2], 1.0)
    n = (0.6 * _np_value_noise(px / sc + t * flow[3] * 0.7, py / sc + t * flow[3] * 0.3)
         + 0.4 * _np_value_noise(px / (sc * 0.43) - t * flow[3] * 0.2 + 5.1, py / (sc * 0.43) - t * flow[3] * 0.6 + 5.1))
    tex = np.full_like(px, 0.5) if lace_tex is None else np.asarray(lace_tex, float)
    lace = n + (np.clip(tex, 0, 1) - n) * min(max(pack[0], 0.0), 1.0)
    shore = np.clip((vc_r * (0.55 + 0.9 * lace) - pack[3]) * max(pack[2], 0.5), 0, 1) * v["SeaFoam"][3]
    ph = d_uu / max(surf_v[0], 1.0) + t * surf_v[1] + (_np_value_noise(px / 70.0 + 3.7, py / 70.0 + 3.7) - 0.5) * 0.9
    x = ph - np.floor(ph)
    w = min(max(look[0], 0.02), 0.9)
    crest = _np_sstep(1 - w, 1 - 0.8 * w, x) * (1 - _np_sstep(1 - 0.8 * w, 1.0, x))
    env = 1.0 - _np_sstep(0.35 * max(surf_v[2], 1.0), max(surf_v[2], 1.0), d_uu)
    surf = crest * env * (1.0 + (_np_sstep(0.3, 0.65, lace) - 1.0) * min(max(look[2], 0.0), 1.0)) * look[1]
    wd = np.array(v["SeaWaveDir"][:2], float) + [1e-4, 0.0]
    wd /= np.linalg.norm(wd)
    shade = slope[0] * wd[0] + slope[1] * wd[1]
    wave_shade = np.clip(shade * v["SeaWave"][0], -0.6, 0.6) * near
    caps = lace * (0.6 + 0.8 * _np_value_noise(px / 260.0 + t * 0.02, py / 260.0 + t * 0.008))
    whitecap = (_np_sstep(v["SeaWave"][2], v["SeaWave"][2] + 0.12, caps) * np.clip(0.5 + 2 * shade, 0, 1)
                * v["SeaWave"][1] * near ** 3)
    foam = np.clip(np.maximum(np.maximum(shore, surf), whitecap), 0, 1)
    water = np.array(v["SeaColor"][:3]) * np.maximum(1.0 + wave_shade, 0.0)[..., None]
    fc = np.array(v["SeaFoam"][:3])
    base = water + (fc - water) * foam[..., None]
    base = base + (np.array(v["SeaFar"][:3]) - base) * (far * (1 - foam))[..., None]
    lit = base * 2.0 ** sc_["NightEV"] * np.array(v["NightTint"][:3])
    luma = lit @ np.array([0.2126, 0.7152, 0.0722])
    graded = np.maximum(luma[..., None] + (lit - luma[..., None]) * sc_["NightSaturation"], 0.0)
    ramp = v["SeaSkyRamp"]
    sky_w = min(max(ramp[2], 0.0), 1.0) + (1.0 - min(max(ramp[2], 0.0), 1.0)) * _np_sstep(ramp[0], max(ramp[1], ramp[0] + 0.001), vc_g)
    ns = max(v["SeaSkyNoise"][0], 1.0)
    cqx, cqy = px / ns + t * v["SeaSkyNoise"][2] / ns * 0.6, py / ns + t * v["SeaSkyNoise"][2] / ns * 0.2
    cloud = 0.65 * _np_value_noise(cqx, cqy) + 0.35 * _np_value_noise(cqx * 2.2 + 9.2, cqy * 2.2 + 9.2)
    sky = (np.array(v["SeaSky"][:3]) * v["SeaSky"][3] * (sky_w * np.maximum(1 + v["SeaSkyNoise"][1] * (cloud - 0.5) * 2, 0))[..., None])
    emissive = graded * (v["SeaShade"][3] * (1 - far) * (1 - foam) + look[3] * foam)[..., None] + sky
    return {"foam": foam, "shore": shore, "surf": surf, "whitecap": whitecap, "albedo": graded, "emissive": emissive,
            "sky": sky, "far": far}


def sea_graph1_cpu(want: dict, px, py, vc_r, vc_g, t: float = 0.0) -> dict:
    """numpy mirror of the P5 graph 1 sea (the reference of 'the defaults keep the graph 1 look')."""
    import numpy as np
    v, sc_ = want["vector"], want["scalar"]
    px, py = np.asarray(px, float), np.asarray(py, float)
    flow = v["SeaFlow"]
    sc = max(flow[2], 1.0)
    n = (0.6 * _np_value_noise(px / sc + t * flow[3] * 0.7, py / sc + t * flow[3] * 0.3)
         + 0.4 * _np_value_noise(px / (sc * 0.43) - t * flow[3] * 0.2 + 5.1, py / (sc * 0.43) - t * flow[3] * 0.6 + 5.1))
    foam = np.clip((np.clip(vc_r, 0, 1) * (0.55 + 0.9 * n) - 0.3) * 2.0, 0, 1) * v["SeaFoam"][3]
    far = np.clip(vc_g, 0, 1) * v["SeaFar"][3]
    sea = np.array(v["SeaColor"][:3])
    base = sea + (np.array(v["SeaFoam"][:3]) - sea) * foam[..., None]
    base = base + (np.array(v["SeaFar"][:3]) - base) * far[..., None]
    lit = base * 2.0 ** sc_["NightEV"] * np.array(v["NightTint"][:3])
    luma = lit @ np.array([0.2126, 0.7152, 0.0722])
    graded = np.maximum(luma[..., None] + (lit - luma[..., None]) * sc_["NightSaturation"], 0.0)
    return {"foam": foam, "albedo": graded, "emissive": graded * (v["SeaShade"][3] * (1 - far))[..., None]}


def sea_mi_want(key: str, params: dict, pack=None, pack_src=None) -> dict:
    """MI_EnvSea_<Map>: ground-params maps.<key>.sea + the map's night grade. pack = {param: texture} (UE; any stand-ins
    in the tests); pack_src = {param: 'pack' | 'fallback'}: SeaPack.x = 1 only when ground-params sea.pack is true and
    the three sea textures come from the pack."""
    mp = params["maps"][key]
    sp = mp.get("sea") or {}
    gr = mp["grade"]
    d = SEA_VECTOR_DEFAULTS
    color = srgb8_to_linear(sp["colorSrgb"]) if "colorSrgb" in sp else d["SeaColor"][:3]
    far = srgb8_to_linear(sp["farSrgb"]) if "farSrgb" in sp else d["SeaFar"][:3]
    pan = sp.get("panUUps", d["SeaFlow"][:2])
    tex = {k: pack[k] for k in SEA_PACK_PARAMS} if pack is not None else {}
    from_pack = bool(sp.get("pack", False)) and (pack_src is None or all(pack_src.get(k) == "pack"
                                                                           for k in SEA_PACK_PARAMS))
    surf, wave, sky = _sub(sp, "surf"), _sub(sp, "waves"), _sub(sp, "sky")
    wtile = wave.get("normalTileUU", [sp.get("rippleTileUU", d["SeaWaveTile"][0]), d["SeaWaveTile"][1]])
    wdir = wave.get("dir", d["SeaWaveDir"][:2])
    scal = {"NightEV": float(gr["ev"]), "NightSaturation": float(gr["saturation"])}
    vec = {"SeaColor": tuple(round(c, 5) for c in color) + (1.0,),
           "SeaFar": tuple(round(c, 5) for c in far) + (float(sp.get("farStrength", 1.0)),),
           "SeaFoam": tuple(float(c) for c in sp.get("foamColor", d["SeaFoam"][:3])) + (float(sp.get("foamOpacity", 0.7)),),
           "SeaFlow": (float(pan[0]), float(pan[1]), float(sp.get("foamScaleUU", 14.0)), float(sp.get("foamSpeed", 0.3))),
           "SeaTile": (float(sp.get("uvTileUU", 600.0)), float(sp.get("rippleTileUU", 160.0)), 0.0, 0.0),
           "SeaShade": (float(sp.get("roughness", 0.08)), float(sp.get("specular", 0.3)),
                        float(sp.get("normalStrength", 0.5)), float(sp.get("lift", 1.5))),
           "SeaPack": (1.0 if from_pack else 0.0, float(sp.get("foamTileUU", d["SeaPack"][1])),
                       float(sp.get("shoreSharpness", d["SeaPack"][2])), float(sp.get("shoreThreshold", d["SeaPack"][3]))),
           "SeaSurf": (float(surf.get("spacingUU", d["SeaSurf"][0])), float(surf.get("cyclesPerSec", d["SeaSurf"][1])),
                       float(surf.get("reachUU", d["SeaSurf"][2])), 1.0 if surf.get("uv1FlipV", True) else 0.0),
           "SeaSurfLook": (float(surf.get("crestWidth", d["SeaSurfLook"][0])),
                           float(surf.get("opacity", d["SeaSurfLook"][1])),
                           float(surf.get("breakup", d["SeaSurfLook"][2])),
                           float(sp.get("foamLift", sp.get("lift", d["SeaSurfLook"][3])))),
           "SeaWave": (float(wave.get("shade", d["SeaWave"][0])), float(wave.get("whitecaps", d["SeaWave"][1])),
                       float(wave.get("whitecapThreshold", d["SeaWave"][2])), 0.0),
           "SeaWaveDir": (float(wdir[0]), float(wdir[1]), 0.0, 0.0),
           "SeaWaveTile": (float(wtile[0]), float(wtile[1]), 0.0, 0.0),
           "SeaSky": tuple(float(c) for c in sky.get("colorLinear", d["SeaSky"][:3])) + (float(sky.get("intensity", 0.0)),),
           "SeaSkyNoise": (float(sky.get("noiseUU", d["SeaSkyNoise"][0])), float(sky.get("amplitude", d["SeaSkyNoise"][1])),
                           float(sky.get("panUUps", d["SeaSkyNoise"][2])), 0.0),
           "SeaSkyRamp": (float(sky.get("rampVcG", d["SeaSkyRamp"][:2])[0]), float(sky.get("rampVcG", d["SeaSkyRamp"][:2])[1]),
                          float(sky.get("atCliffs", d["SeaSkyRamp"][2])), 0.0),
           "NightTint": tuple(float(v) for v in gr["tint"]) + (1.0,)}
    return {"tex": tex, "scalar": scal, "vector": vec}


# --- P5 track B: the lane K meshes (legacy FbxFactory; the env kit's import with a vertex-colour option) --------------
def sm_api():
    """StaticMeshEditorSubsystem (the module is not loaded by -run=pythonscript until asked; UE 5.8)."""
    sms = None
    try:
        u.load_module("StaticMeshEditor")
        sms = u.get_editor_subsystem(u.StaticMeshEditorSubsystem)
    except Exception:  # noqa: BLE001 - engine / commandlet dependent
        sms = None
    if sms is None and hasattr(u, "EditorStaticMeshLibrary"):
        sms = u.EditorStaticMeshLibrary
    if sms is None:
        raise RuntimeError("StaticMeshEditorSubsystem unavailable (run inside UnrealEditor-Cmd -run=pythonscript)")
    return sms


def _setp(obj, prop: str, value) -> bool:
    try:
        obj.set_editor_property(prop, value)
        return True
    except Exception:  # noqa: BLE001 - optional property (engine version)
        return False


def import_static_mesh(source: str, asset: str, vertex_colors: str = "ignore", scale: float = 1.0) -> dict:
    """One FBX -> one static mesh (combine meshes, normals imported, no materials / textures / collision / Nanite);
    vertex_colors 'replace' keeps the FBX Col layer (lane K masks), 'ignore' drops it."""
    folder, leaf = split(asset)
    o = u.FbxImportUI()
    o.set_editor_property("automated_import_should_detect_type", False)
    o.set_editor_property("import_mesh", True)
    o.set_editor_property("import_as_skeletal", False)
    o.set_editor_property("mesh_type_to_import", u.FBXImportType.FBXIT_STATIC_MESH)
    o.set_editor_property("original_import_type", u.FBXImportType.FBXIT_STATIC_MESH)
    o.set_editor_property("import_materials", False)
    o.set_editor_property("import_textures", False)
    o.set_editor_property("import_animations", False)
    d = o.get_editor_property("static_mesh_import_data")
    d.set_editor_property("combine_meshes", True)
    vco = u.VertexColorImportOption
    d.set_editor_property("vertex_color_import_option", vco.REPLACE if vertex_colors == "replace" else vco.IGNORE)
    d.set_editor_property("normal_import_method", u.FBXNormalImportMethod.FBXNIM_IMPORT_NORMALS)
    d.set_editor_property("import_uniform_scale", float(scale))
    res = {"factory": "FbxFactory", "vertexColors": vertex_colors, "importUniformScale": float(scale),
           "autoGenerateCollisionOff": _setp(d, "auto_generate_collision", False),
           "buildNaniteOff": _setp(d, "build_nanite", False)}
    t = u.AssetImportTask()
    t.set_editor_property("filename", source)
    t.set_editor_property("destination_path", folder)
    t.set_editor_property("destination_name", leaf)
    t.set_editor_property("replace_existing", True)
    t.set_editor_property("automated", True)
    t.set_editor_property("save", False)
    t.set_editor_property("factory", u.FbxFactory())
    t.set_editor_property("options", o)
    u.AssetToolsHelpers.get_asset_tools().import_asset_tasks([t])
    res["imported"] = [str(x) for x in t.get_editor_property("imported_object_paths")]
    if not res["imported"]:
        raise RuntimeError(f"the import of {source} produced no assets")
    return res


def ensure_decor_mesh(mesh, slot_material) -> list:
    """Nanite off, no simple collision + simple-as-complex (no collision data), every slot -> slot_material (None =
    leave the slots). Returns the changes."""
    sms = sm_api()
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
            changes.append("collision trace simple-as-complex")
    except Exception as exc:  # noqa: BLE001 - optional hardening
        changes.append(f"collision trace flag not set ({type(exc).__name__}: {exc})")
    if slot_material is not None:
        for index in range(len(mesh.get_editor_property("static_materials"))):
            current = mesh.get_material(index)
            if current is None or current.get_path_name() != slot_material.get_path_name():
                mesh.set_material(index, slot_material)
                changes.append(f"slot {index} -> {slot_material.get_name()}")
    return changes


def compare_mesh(measured: dict, item: dict) -> dict:
    """World-free (also exercised by the tests): measured bounds / triangles against the lane K build."""
    out = {}
    b = item.get("boundsUeUU") or {}
    if b.get("min") and b.get("max"):
        delta = [round(measured["boundsMin"][i] - b["min"][i], 3) for i in range(3)] + \
                [round(measured["boundsMax"][i] - b["max"][i], 3) for i in range(3)]
        out["bounds"] = {"build": b, "deltaUU": delta, "ok": all(abs(d) <= MESH_BOUNDS_TOL_UU for d in delta)}
    tris = item.get("triangles")
    if tris and isinstance(measured.get("trianglesLod0"), int):
        drift = abs(measured["trianglesLod0"] - tris) / tris
        out["triangles"] = {"build": tris, "ue": measured["trianglesLod0"], "drift": round(drift, 5),
                            "ok": drift <= MESH_TRIS_TOL}
    return out


def measure_mesh(mesh, item: dict) -> dict:
    sms = sm_api()
    box = mesh.get_bounding_box()
    mn, mx = box.min, box.max
    out = {"boundsMin": [round(mn.x, 3), round(mn.y, 3), round(mn.z, 3)],
           "boundsMax": [round(mx.x, 3), round(mx.y, 3), round(mx.z, 3)],
           "nanite": bool(mesh.get_editor_property("nanite_settings").get_editor_property("enabled")),
           "simpleCollision": int(sms.get_simple_collision_count(mesh)),
           "slots": [mesh.get_material(i).get_path_name() if mesh.get_material(i) else None
                     for i in range(len(mesh.get_editor_property("static_materials")))]}
    try:
        out["trianglesLod0"] = int(mesh.get_num_triangles(0))
    except Exception:  # noqa: BLE001 - not exposed in every engine version
        out["trianglesLod0"] = None
    try:
        out["hasVertexColors"] = bool(sms.has_vertex_colors(mesh))
    except Exception as exc:  # noqa: BLE001 - measurement only
        out["hasVertexColors"] = f"n/a ({type(exc).__name__})"
    try:  # P5c: M_EnvSea graph 2 reads the sea ring's UV1 (distance from the inner edge) for the surf
        out["uvChannels"] = int(sms.get_num_uv_channels(mesh, 0))
    except Exception as exc:  # noqa: BLE001 - measurement only
        out["uvChannels"] = f"n/a ({type(exc).__name__})"
    out.update(compare_mesh(out, item))
    return out


def import_env_meshes(key: str, items: dict, materials: dict, force: bool) -> tuple[dict, bool]:
    """Imports / updates the lane K meshes of one map (plan_meshes items) and binds their slots (materials = {part:
    material or None}). Idempotent: MESH_SHA_TAG / MESH_VC_TAG per mesh."""
    eal = u.EditorAssetLibrary
    out, ok = {}, True
    for part, it in items.items():
        r = {"asset": it["asset"]}
        out[part] = r
        if not it.get("ok"):
            r.update(action="skipped", error=it.get("error"))
            ok = False
            continue
        try:
            mesh = u.load_asset(it["asset"]) if eal.does_asset_exist(it["asset"]) else None
            if (mesh is not None and not force and eal.get_metadata_tag(mesh, MESH_SHA_TAG) == it["sha256"]
                    and eal.get_metadata_tag(mesh, MESH_VC_TAG) == it["vertexColors"]):
                r["action"] = "unchanged"
            else:
                r.update(import_static_mesh(it["source"], it["asset"], it["vertexColors"]),
                         action="reimported" if mesh is not None else "imported")
                mesh = u.load_asset(it["asset"])
                if mesh is None or not isinstance(mesh, u.StaticMesh):
                    raise RuntimeError(f"{it['asset']} is not a static mesh after the import")
                eal.set_metadata_tag(mesh, MESH_SHA_TAG, it["sha256"])
                eal.set_metadata_tag(mesh, MESH_VC_TAG, it["vertexColors"])
            material = materials.get(part)
            if material is None:
                r["warning"] = f"no material for the {part} slots (left as imported)"
            r["changes"] = ensure_decor_mesh(mesh, material)
            if r["changes"] or r["action"] != "unchanged":
                if not eal.save_loaded_asset(mesh, False):
                    raise RuntimeError(f"could not save {it['asset']}")
            m = r["measure"] = measure_mesh(mesh, it)
            problems = []
            if m["nanite"]:
                problems.append("nanite still on")
            if m["simpleCollision"]:
                problems.append("simple collision left")
            if not (m.get("bounds") or {}).get("ok", True):
                problems.append(f"bounds differ from the build: {m.get('bounds')}")
            if (m.get("triangles") or {}).get("ok") is False:
                problems.append(f"triangles differ from the build: {m.get('triangles')}")
            if it["vertexColors"] == "replace" and m.get("hasVertexColors") is False:
                problems.append("vertex colours missing (REPLACE)")
            if part == "sea" and isinstance(m.get("uvChannels"), int) and m["uvChannels"] < 2:
                problems.append("sea ring without UV1 (the M_EnvSea surf distance): re-import")
            if len(m["slots"]) != it.get("slots", len(m["slots"])):
                problems.append(f"{len(m['slots'])} slots, the build has {it.get('slots')}")
            r["problems"] = problems
            ok = ok and not problems
        except Exception as exc:  # noqa: BLE001 - report and continue
            r["error"] = f"{type(exc).__name__}: {exc}"
            ok = False
    return out, ok


def _water(params: dict, key: str) -> dict:
    """The water block of a map with every value resolved (maps without water: the material defaults, strength 0)."""
    w = params["maps"][key].get("water") or {}
    color = srgb8_to_linear(w["colorSrgb"]) if "colorSrgb" in w else VECTOR_DEFAULTS["WaterColor"][:3]
    tiles = w.get("rippleTileUU", VECTOR_DEFAULTS["WaterRipple"][:2])
    return {
        "WaterColor": tuple(round(c, 5) for c in color) + (float(w.get("shallowMix", 0.55)),),
        "WaterFoam": tuple(float(c) for c in w.get("foamColor", VECTOR_DEFAULTS["WaterFoam"][:3]))
        + (float(w.get("foamOpacity", 0.0)) if w else 0.0,),
        "WaterSurface": (float(w.get("roughness", 0.06)), float(w.get("specular", 0.25)),
                         float(w.get("normalStrength", 0.55)), float(w.get("lift", 0.0)) if w else 0.0),
        "WaterRipple": (float(tiles[0]), float(tiles[1]), float(w.get("foamScaleUU", 9.0)),
                        float(w.get("foamSpeed", 0.6))),
        "WaterPan": tuple(float(c) for c in w.get("panUUps", VECTOR_DEFAULTS["WaterPan"])),
    }


def mi_want(key: str, params: dict, textures: dict, splat, rect: list, aux=None, ripple=None) -> dict:
    """The MI parameters of one map: {'tex': {name: texture}, 'scalar': {name: value}, 'vector': {name: rgba}}."""
    mp = params["maps"][key]
    m = params["material"]
    tex, scal, vec = {"Splat": splat}, {}, {}
    if aux is not None:
        tex["Aux"] = aux
    if ripple is not None:
        tex["WaterRippleN"] = ripple
    rmin, rscale, spec, nrm, macro = [], [], [], [], []
    for i, lay in enumerate(mp["layers"]):
        for k in KEYS:
            tex[f"L{i}_{k}"] = textures[(lay["set"], k)]
        scal[f"L{i}_TileUU"] = float(lay["tileUU"])
        if i > 0:
            scal[f"L{i}_HeightBlend"] = float(lay.get("heightBlend", 1.0))
        vec[f"L{i}_Tint"] = tuple(float(v) for v in lay["tint"]) + (float(lay["saturation"]),)
        rmin.append(float(lay.get("roughMin", 0.0)))
        rscale.append(float(lay.get("roughScale", 1.0)))
        spec.append(float(lay.get("specular", m["specular"])))
        nrm.append(float(lay.get("normalStrength", 1.0)))
        macro.append(float(lay.get("macro", 0.0)))
    ac, gr = mp["accent"], mp["grade"]
    edge = mp.get("edge") or {}
    scal.update({"HeightContrast": float(m["heightContrast"]), "NormalStrength": float(m["normalStrength"]),
                 "MacroStrength": float(m["macroStrength"]), "MacroScaleUU": float(m["macroScaleUU"]),
                 "AccentOpacity": float(ac["opacity"]), "AccentRoughness": float(ac["roughness"]),
                 "AccentCarpet": float(ac.get("carpet", 0.0)),
                 "PetalSizeUU": float(ac["petalSizeUU"]), "NightEV": float(gr["ev"]),
                 "NightSaturation": float(gr["saturation"]),
                 "LayerMacroScaleUU": float(m.get("layerMacroScaleUU", 33.0)),
                 "EdgeRoughness": float(edge.get("roughness", 0.8))})
    x0, y0, x1, y1 = (float(v) for v in rect)
    vec.update({"AccentColor": tuple(float(v) for v in ac["color"]) + (1.0,),
                "NightTint": tuple(float(v) for v in gr["tint"]) + (1.0,),
                "SplatRect": (x0, y0, x1 - x0, y1 - y0), "GroundStrip": (x0, y0, x1 - x0, y1 - y0),
                "LayerRoughMin": tuple(rmin), "LayerRoughScale": tuple(rscale), "LayerSpecular": tuple(spec),
                "LayerNormal": tuple(nrm), "LayerMacro": tuple(macro),
                "EdgeTint": tuple(float(v) for v in edge.get("color", (1.0, 1.0, 1.0)))
                + (float(edge.get("strength", 1.0)) if edge else 0.0,)})
    vec.update(_water(params, key))
    return {"tex": tex, "scalar": scal, "vector": vec}


def fall_mi_want(key: str, params: dict, ripple=None, streak=None, streak_src: str | None = None) -> dict:
    """MI_EnvWaterfall_<Map>: the water colour / foam / grade of the map and the look of its first fall entry. P5c:
    falls[0].look = {blend 'translucent' (graph 3 default) | 'masked' (the graph 2 dithered look, an MI blend-mode
    override), bodyOpacity, foamOpacity, edgeWobble, pack (the Water Materials streaks; FallLook.w = 1 only when the
    texture came from the pack), packTileUU [across, along], packSpeedRatio}."""
    mp = params["maps"][key]
    w = mp.get("water") or {}
    f = (w.get("falls") or [{}])[0]
    look = f.get("look") if isinstance(f.get("look"), dict) else {}
    gr = mp["grade"]
    wv = _water(params, key)
    d = FALL_VECTOR_DEFAULTS
    tex = {"WaterRippleN": ripple} if ripple is not None else {}
    if streak is not None:
        tex["FallStreakTex"] = streak
    use_pack = bool(look.get("pack", False)) and streak_src in (None, "pack")
    blend = str(look.get("blend", "translucent"))
    if blend not in FALL_BLENDS:
        raise ValueError(f"{key}: water.falls[0].look.blend {blend!r} not in {FALL_BLENDS}")
    tile = look.get("packTileUU", d["FallTex"][:2])
    scal = {"NightEV": float(gr["ev"]), "NightSaturation": float(gr["saturation"]),
            "RippleTileUU": float(wv["WaterRipple"][0])}
    vec = {"WaterColor": wv["WaterColor"], "WaterFoam": wv["WaterFoam"],
           "NightTint": tuple(float(v) for v in gr["tint"]) + (1.0,),
           "FallFlow": (float(f.get("flowUUps", 55.0)), float(f.get("streakScaleUU", 9.0)),
                        float(f.get("edgeFadeUU", 12.0)), float(f.get("bottomFade", 0.35))),
           "FallSpill": (float(f.get("spillFadeUU", 18.0)), float(f.get("dither", 0.5)), 0.0, 0.0),
           "FallShade": (wv["WaterSurface"][0] + 0.02, wv["WaterSurface"][1], wv["WaterSurface"][2],
                         wv["WaterSurface"][3]),
           "FallLook": (float(look.get("bodyOpacity", d["FallLook"][0])), float(look.get("foamOpacity", d["FallLook"][1])),
                        float(look.get("edgeWobble", 0.0)), 1.0 if use_pack else 0.0),
           "FallTex": (float(tile[0]), float(tile[1]), float(look.get("packSpeedRatio", d["FallTex"][2])), 0.0)}
    return {"tex": tex, "scalar": scal, "vector": vec, "blend": blend}


def _blend_override(mi) -> bool:
    """True when the MI overrides its parent's blend mode to Masked (P5c waterfall fallback)."""
    ov = mi.get_editor_property("base_property_overrides")
    return (bool(ov.get_editor_property("override_blend_mode"))
            and ov.get_editor_property("blend_mode") == u.BlendMode.BLEND_MASKED)


def _set_blend_override(mi, masked: bool) -> None:
    ov = mi.get_editor_property("base_property_overrides")
    ov.set_editor_property("override_blend_mode", bool(masked))
    if masked:
        ov.set_editor_property("blend_mode", u.BlendMode.BLEND_MASKED)
    mi.set_editor_property("base_property_overrides", ov)


def ensure_instance(path: str, material, want: dict) -> dict:
    eal, mel = u.EditorAssetLibrary, u.MaterialEditingLibrary
    mi = u.load_asset(path) if eal.does_asset_exist(path) else None
    action = "updated"
    if mi is None:
        folder, leaf = split(path)
        mi = u.AssetToolsHelpers.get_asset_tools().create_asset(leaf, folder, u.MaterialInstanceConstant,
                                                                 u.MaterialInstanceConstantFactoryNew())
        action = "created"
    if mi is None:
        raise RuntimeError(f"could not create {path}")

    def rgba(c) -> tuple:
        return tuple(round(float(getattr(c, k)), 5) for k in ("r", "g", "b", "a"))

    def current() -> dict:
        parent = mi.get_editor_property("parent")
        st = {"parent": parent.get_path_name() if parent else None}
        for name in want["tex"]:
            t = mel.get_material_instance_texture_parameter_value(mi, name)
            st["t:" + name] = t.get_path_name() if t else None
        for name in want["scalar"]:
            st["s:" + name] = round(float(mel.get_material_instance_scalar_parameter_value(mi, name)), 5)
        for name in want["vector"]:
            st["v:" + name] = rgba(mel.get_material_instance_vector_parameter_value(mi, name))
        if want.get("blend") is not None:
            st["blendOverride"] = _blend_override(mi)
        return st

    target = {"parent": material.get_path_name()}
    target.update({"t:" + k: v.get_path_name() for k, v in want["tex"].items()})
    target.update({"s:" + k: round(v, 5) for k, v in want["scalar"].items()})
    target.update({"v:" + k: tuple(round(x, 5) for x in v) for k, v in want["vector"].items()})
    if want.get("blend") is not None:  # P5c: falls[].look.blend 'masked' = a blend-mode override on the MI
        target["blendOverride"] = want["blend"] == "masked"
    if action == "updated" and current() == target:
        return {"action": "unchanged", "path": path}
    mel.set_material_instance_parent(mi, material)
    if want.get("blend") is not None:
        _set_blend_override(mi, want["blend"] == "masked")
    for name, t in want["tex"].items():
        mel.set_material_instance_texture_parameter_value(mi, name, t)
    for name, v in want["scalar"].items():
        mel.set_material_instance_scalar_parameter_value(mi, name, v)
    for name, v in want["vector"].items():
        mel.set_material_instance_vector_parameter_value(mi, name, u.LinearColor(*v))
    mel.update_material_instance(mi)
    if not eal.save_loaded_asset(mi, False):
        raise RuntimeError(f"could not save {path}")
    got = current()
    diff = {k: (got.get(k), v) for k, v in target.items() if got.get(k) != v}
    if diff:
        raise RuntimeError(f"{path}: parameters did not bind: {diff}")
    return {"action": action, "path": path, "params": len(target) - 1}


def run_import(pl: dict, params: dict, keys: list[str], force: bool) -> tuple[dict, bool]:
    result, ok = {"sets": {}, "maps": {}}, True
    textures = {}
    for set_id, item in pl["sets"].items():
        out = {}
        result["sets"][set_id] = out
        for key, t in item["textures"].items():
            if not t.get("ok"):
                out[key] = {"action": "skipped", "error": t.get("error")}
                ok = False
                continue
            try:
                out[key] = import_texture(t["source"], t["sha256"], t["asset"], key, force)
                textures[(set_id, key)] = u.load_asset(t["asset"])
            except Exception as exc:  # noqa: BLE001 - report and continue
                out[key] = {"action": "failed", "error": f"{type(exc).__name__}: {exc}"}
                ok = False
    ripple = textures.get((RIPPLE_SET, "N"))
    splats, auxes = {}, {}
    for key in keys:
        m = pl["maps"][key]
        out = {}
        result["maps"][key] = out
        if not m.get("ok"):
            out["splat"] = {"action": "skipped", "error": m.get("error")}
            ok = False
            continue
        for kind, src, sha, asset, store in (("splat", "source", "sha256", "splatAsset", splats),
                                             ("aux", "auxSource", "auxSha256", "auxAsset", auxes)):
            try:
                out[kind] = import_texture(m[src], m[sha], m[asset], "Splat" if kind == "splat" else "Aux", force)
                store[key] = u.load_asset(m[asset])
            except Exception as exc:  # noqa: BLE001
                out[kind] = {"action": "failed", "error": f"{type(exc).__name__}: {exc}"}
                ok = False
    ready = [k for k in keys if k in splats and k in auxes and ripple is not None
             and all((lay["set"], kk) in textures for lay in params["maps"][k]["layers"] for kk in KEYS)]
    if not ready:
        result["material"] = {"action": "skipped", "error": "no map has all its textures"}
        return result, False
    first = ready[0]
    defaults = {f"L{i}_{k}": textures[(lay["set"], k)] for i, lay in enumerate(params["maps"][first]["layers"])
                for k in KEYS}
    try:
        result["material"] = build_material(defaults, splats[first], auxes[first], ripple, force)
        material = u.load_asset(MATERIAL_PATH)
    except Exception as exc:  # noqa: BLE001
        result["material"] = {"action": "failed", "error": f"{type(exc).__name__}: {exc}"}
        return result, False
    pack_tex, pack_src = load_pack(ripple)  # P5c: the Water Materials textures (CC BY 4.0) or the stand-ins
    result["pack"] = {param: {"asset": pack_asset(param), "source": pack_src[param],
                              "texture": pack_tex[param].get_path_name() if pack_tex[param] else None}
                      for param in PACK_TEXTURES}
    sea_material = None
    if any(has_sea(params, k) for k in ready):
        try:
            result["seaMaterial"] = build_sea_material(pack_tex, force)
            sea_material = u.load_asset(SEA_MATERIAL_PATH)
        except Exception as exc:  # noqa: BLE001
            result["seaMaterial"] = {"action": "failed", "error": f"{type(exc).__name__}: {exc}"}
            ok = False
    fall_material = None
    if any(has_falls(params, k) for k in ready):
        try:
            result["waterfallMaterial"] = build_waterfall_material(ripple, pack_tex["FallStreakTex"], force)
            fall_material = u.load_asset(FALL_MATERIAL_PATH)
        except Exception as exc:  # noqa: BLE001
            result["waterfallMaterial"] = {"action": "failed", "error": f"{type(exc).__name__}: {exc}"}
            ok = False
    for key in keys:
        if key not in ready:
            result["maps"][key]["materialInstance"] = {"action": "skipped", "error": "textures missing"}
            ok = False
            continue
        try:
            want = mi_want(key, params, textures, splats[key], pl["maps"][key]["splatRect"], auxes[key], ripple)
            result["maps"][key]["materialInstance"] = ensure_instance(mi_asset(key), material, want)
        except Exception as exc:  # noqa: BLE001
            result["maps"][key]["materialInstance"] = {"action": "failed", "error": f"{type(exc).__name__}: {exc}"}
            ok = False
        if has_falls(params, key):
            if fall_material is None:
                result["maps"][key]["waterfallInstance"] = {"action": "skipped", "error": "no M_EnvWaterfall"}
                ok = False
                continue
            try:
                result["maps"][key]["waterfallInstance"] = ensure_instance(
                    fall_mi_asset(key), fall_material,
                    fall_mi_want(key, params, ripple, pack_tex["FallStreakTex"], pack_src["FallStreakTex"]))
            except Exception as exc:  # noqa: BLE001
                result["maps"][key]["waterfallInstance"] = {"action": "failed",
                                                            "error": f"{type(exc).__name__}: {exc}"}
                ok = False
        if has_sea(params, key):
            if sea_material is None:
                result["maps"][key]["seaInstance"] = {"action": "skipped", "error": "no M_EnvSea"}
                ok = False
            else:
                try:
                    result["maps"][key]["seaInstance"] = ensure_instance(
                        sea_mi_asset(key), sea_material, sea_mi_want(key, params, pack_tex, pack_src))
                except Exception as exc:  # noqa: BLE001
                    result["maps"][key]["seaInstance"] = {"action": "failed", "error": f"{type(exc).__name__}: {exc}"}
                    ok = False
        items = pl["maps"][key].get("meshes") or {}
        if items:
            eal = u.EditorAssetLibrary

            def load(path):
                return u.load_asset(path) if eal.does_asset_exist(path) else None
            fall_mi = load(fall_mi_asset(key)) if has_falls(params, key) else None
            mats = {"sheet": fall_mi, "foam": fall_mi, "lip": load(f"{T2B_MI_PREFIX}{MAPS[key]}"),
                    "sea": load(sea_mi_asset(key)) if has_sea(params, key) else None}
            result["maps"][key]["meshes"], meshes_ok = import_env_meshes(key, items, mats, force)
            ok = ok and meshes_ok
    listing = sorted(str(p).split(".")[0] for p in u.EditorAssetLibrary.list_assets(ROOT, recursive=True,
                                                                                      include_folder=False))
    result["folder"] = {"assets": len(listing), "foreign": [a for a in listing if a not in planned_assets(params)]}
    return result, ok


def planned_assets(params: dict) -> set:
    """Every asset this tool may own under /Game/EnvKit/Ground (the 'foreign' listing of the report)."""
    planned = {MATERIAL_PATH, FALL_MATERIAL_PATH, ripple_asset()}
    planned |= {mi_asset(k) for k in MAPS} | {splat_asset(k) for k in MAPS} | {aux_asset(k) for k in MAPS}
    planned |= {fall_mi_asset(k) for k in MAPS}
    planned |= {SEA_MATERIAL_PATH} | {sea_mi_asset(k) for k in MAPS}
    planned |= {mesh_asset(k, part) for k in MAPS for part in ENV_MESHES}
    planned |= {texture_asset(s, k) for s in params["sets"] for k in KEYS}
    return planned


# ================================================================================================ entry
def main(argv: list | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n", 1)[0])
    ap.add_argument("--maps", default=",".join(MAPS))
    ap.add_argument("--params", default=str(PARAMS_DEFAULT))
    ap.add_argument("--staging", default=str(STAGING_DEFAULT))
    ap.add_argument("--report", default=None)
    ap.add_argument("--prep", action="store_true", help="plain Python: build the staging PNGs from the CC0 sets")
    ap.add_argument("--check", action="store_true", help="plain Python: verify staging, splats and layouts")
    ap.add_argument("--force", action="store_true", help="rebuild the staging (--prep) / re-import everything (UE)")
    args = ap.parse_args(argv)
    started = time.time()
    keys = [k.strip() for k in args.maps.split(",") if k.strip()]
    unknown = [k for k in keys if k not in MAPS]
    if unknown:
        print(f"unknown map key(s) {unknown}; known: {sorted(MAPS)}")
        return 2
    params_path = Path(args.params).resolve()
    params = load_params(params_path)
    staging = Path(args.staging)
    mode = "prep" if args.prep else ("check" if (args.check or u is None) else "import")
    report = {"schema": "unmatched.env-ground-ue-import/1", "tool": "tools/art/env_kit/ue_import_env_ground.py",
              "mode": mode, "params": rel(params_path), "staging": staging.as_posix(), "contentRoot": ROOT,
              "material": MATERIAL_PATH, "graphVersion": GRAPH_VERSION, "waterfallMaterial": FALL_MATERIAL_PATH,
              "waterfallGraphVersion": FALL_GRAPH_VERSION, "seaMaterial": SEA_MATERIAL_PATH,
              "seaGraphVersion": SEA_GRAPH_VERSION, "packRoot": PACK_ROOT, "maps": keys}
    ok = True
    if mode == "prep":
        if u is not None:
            print("--prep needs plain Python (numpy / PIL), not the editor")
            return 2
        manifest, ok = prep(params, keys, staging, args.force)
        report["sets"] = {k: {"action": v.get("action"), "error": v.get("error")} for k, v in manifest["sets"].items()}
    pl = plan(params, keys, staging, params_path)
    report["plan"] = pl
    ok = ok and pl["ok"]
    if mode == "import":
        imported, import_ok = run_import(pl, params, keys, args.force)
        report["ue"] = imported
        report["engine"] = str(u.SystemLibrary.get_engine_version())
        ok = ok and import_ok
    report["ok"] = ok
    report["seconds"] = round(time.time() - started, 1)
    text = json.dumps(report, ensure_ascii=False, indent=1, default=str)
    if args.report:
        report_path = Path(args.report)
    elif u is not None:
        report_path = Path(u.Paths.project_saved_dir()) / "EnvKit" / "ue-ground-import-report.json"
    else:
        report_path = None
    if report_path is not None:
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_bytes((text + "\n").encode("utf-8"))
    bad = [f"{s}/{k}: {t.get('error')}" for s, it in pl["sets"].items() for k, t in it["textures"].items() if not t["ok"]]
    bad += [f"{k}: {m.get('error')}" for k, m in pl["maps"].items() if not m["ok"]]
    bad += list(pl.get("errors") or [])
    for param, it in (pl.get("pack") or {}).items():
        if not it["present"]:
            print(f"  WARN  pack texture {it['asset']} ({param}) missing: the procedural fallback is used")
    for b in bad:
        print("  ERROR " + b)
    print("ENVGROUND-IMPORT-REPORT " + json.dumps(report, ensure_ascii=False, default=str))
    print(f"ENVGROUND-IMPORT-RESULT {'ok' if ok else 'failed'} mode={mode} maps={','.join(keys)} "
          f"sets={len(pl['sets'])} textures={sum(len(i['textures']) for i in pl['sets'].values())}")
    return 0 if ok else 1


if __name__ == "__main__":
    code = main(sys.argv[1:])
    if u is None:
        sys.exit(code)
    elif code != 0:
        raise RuntimeError("ENVGROUND import failed - see ENVGROUND-IMPORT-REPORT")
