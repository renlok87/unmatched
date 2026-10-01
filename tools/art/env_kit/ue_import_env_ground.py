"""ENV-MAPS P2 track GROUND (ENV-U10): the themed ground of the original-map boards in UE (/Game/EnvKit/Ground, out of git).

Three stages, one file:
  --prep   (plain Python: numpy + PIL) the CC0 sets of ground-params.json 'sets' -> 2K staging PNGs + a manifest:
           <staging>/<Set>/T_Ground_<Set>_BC.png    sRGB colour (the raw _Color.jpg; rotated for rotate90 sets)
           <staging>/<Set>/T_Ground_<Set>_N.png     DirectX normal (_NormalDX.jpg; rotate90 also turns the XY vector:
                                                    R' = G, G' = 255 - R for numpy rot90 k=1)
           <staging>/<Set>/T_Ground_<Set>_ORMH.png  linear RGBA: R = AO (1 when the set has none), G = roughness,
                                                    B = metalness (0 when none), A = height (_Displacement normalised to
                                                    its 1..99 % percentiles, stored 1..255 - never 0, see the splat)
           <staging>/ground-sources.json            sha256 of every raw input and output + the recipe
           Default staging: <repo>/unreal/Unmatched/Saved/EnvKit/GroundSources (gitignored; ~100 MB).
  --check  (plain Python) staging files against the manifest, splat PNGs against <map>.splat.json, and the layouts'
           'ground' sections against the splats (sha256 / rect / material path).
  (UE)     UnrealEditor-Cmd -run=pythonscript: imports into
           /Game/EnvKit/Ground/Sets/T_Ground_<Set>_{BC,N,ORMH}   BC sRGB TC_Default; N TC_Normalmap (DirectX, no green
                                                                  flip); ORMH TC_Masks linear; group World(NormalMap)
           /Game/EnvKit/Ground/T_EnvGround_<Map>_Splat            TC_VectorDisplacementmap (RGBA8, uncompressed), linear,
                                                                  clamp addressing
           /Game/EnvKit/Ground/M_EnvGround                         the 4-layer splat material (graph below)
           /Game/EnvKit/Ground/MI_EnvGround_<Map>                  per map: layer sets, tiling, tints, accent, grade,
                                                                  SplatRect (= the layout 'ground.splatRect')
           (DefaultGame.ini cooks /Game/EnvKit already; S08EnvGround.cpp loads the MI by the layout path.)

M_EnvGround (lit, opaque, one-sided; every texture on a SHARED sampler - 13 samples use no sampler slot):
  P        = GroundStrip.xy + TexCoord0 * GroundStrip.zw        board XY (uu) of the strip pixel; the runtime sets
                                                                GroundStrip = (min.x, min.y, size.x, size.y) of each
                                                                /Engine/BasicShapes/Plane strip on its MID (engine plane:
                                                                UV (0,0) at local (-50,-50), u along +X, v along +Y)
  layer i  = L{i}_BC / L{i}_N / L{i}_ORMH at P / L{i}_TileUU      (i = 0..3, wrap)
  splat    = Splat at (P - SplatRect.xy) / SplatRect.zw           (clamp; RGB = L1..L3 coverage, A = 1 + accent * 254)
  weights  = height-lerp stack: a_k = saturate((lerp(0.5, H_k, L{k}_HeightBlend) - 1 + splat_k * (1 + c)) / c),
             L3 over L2 over L1 over L0
  albedo   = sum w_i * lerp(luma, BC_i, L{i}_Tint.a) * L{i}_Tint.rgb, x (1 + MacroStrength * value noise),
             accent: PetalSizeUU > 0 -> petals (a pink carpet of strength AccentCarpet + one jittered petal per
             PetalSizeUU cell, density = accent * AccentOpacity); PetalSizeUU = 0 -> wetness (albedo *= lerp(1, AccentColor, accent * opacity),
             roughness -> AccentRoughness)
  base     = night grade of M_MapBoard: lit = albedo * 2^NightEV * NightTint; lerp(luma, lit, NightSaturation)
  normal   = normalize(sum w_i N_i with xy * NormalStrength); AO / roughness / metallic = sum w_i ORMH_i.rgb
Idempotent: textures carry EnvGroundSourceSha256 (re-imported only when the source changes or --force), the material
carries EnvGroundGraphVersion (rebuilt only when GRAPH_VERSION changes or --force), the MIs are compared parameter by
parameter and only written when they differ. Report: 'ENVGROUND-IMPORT-REPORT {...}' / 'ENVGROUND-IMPORT-RESULT ok|failed'
and <project>/Saved/EnvKit/ue-ground-import-report.json (or --report).

Run (repository root; the editor must be CLOSED; never inside a GPU-measurement window):
  python -B tools/art/env_kit/ground_splat.py --write-layouts          # splats + layout sections (git)
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
SHA_TAG = "EnvGroundSourceSha256"
GRAPH_TAG = "EnvGroundGraphVersion"
GRAPH_VERSION = "1"
PREP_VERSION = "1"
KEYS = ("BC", "N", "ORMH")
LAYERS = 4
MANIFEST_SCHEMA = "unmatched.env-ground-sources/1"


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


def mi_asset(key: str) -> str:
    return f"{ROOT}/MI_EnvGround_{MAPS[key]}"


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
                     and len(outs) == len(KEYS)
                     and all(Path(o["path"]).is_file() and sha256_file(Path(o["path"])) == o["sha256"]
                             for o in outs.values()))
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
    manifest = {"schema": MANIFEST_SCHEMA, "tool": "tools/art/env_kit/ue_import_env_ground.py --prep",
                "cc0Raw": raw_root.as_posix(), "staging": staging.as_posix(), "sets": sets}
    staging.mkdir(parents=True, exist_ok=True)
    manifest_path.write_bytes((json.dumps(manifest, indent=1) + "\n").encode("utf-8"))
    return manifest, ok


# ================================================================================================ check (plain Python)
def plan(params: dict, keys: list[str], staging: Path, params_path: Path) -> dict:
    """What the UE stage imports: staging textures (verified against the manifest), splats (against their meta), the
    layout sections. Every item carries ok / error."""
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
            o = (entry.get("outputs") or {}).get(key)
            t = {"asset": texture_asset(set_id, key)}
            if not o:
                t.update(ok=False, error="not in the staging manifest (run --prep)")
            else:
                p = Path(o["path"])
                t.update(source=p.as_posix(), sha256=o["sha256"])
                if not p.is_file():
                    t.update(ok=False, error="staging file missing (run --prep)")
                else:
                    got = sha256_file(p)
                    t["ok"] = got == o["sha256"]
                    if not t["ok"]:
                        t["error"] = f"sha256 {got} != manifest (re-run --prep)"
            item["textures"][key] = t
            item["ok"] = item["ok"] and t["ok"]
        out["sets"][set_id] = item
        out["ok"] = out["ok"] and item["ok"]
    for key in keys:
        m = {"ok": True, "splatAsset": splat_asset(key), "mi": mi_asset(key)}
        meta_path = params_path.parent / f"{key}.splat.json"
        png_path = params_path.parent / f"{key}.splat.png"
        try:
            meta = json.loads(meta_path.read_text(encoding="utf-8"))
            m["splatRect"] = meta["splatRect"]
            m["source"] = png_path.as_posix()
            m["sha256"] = sha256_file(png_path)
            if m["sha256"] != meta["png"]["sha256"]:
                m.update(ok=False, error=f"{rel(png_path)} sha256 != {rel(meta_path)} (re-run ground_splat.py)")
            layout = json.loads((LAYOUT_DIR / f"{key}.layout.json").read_text(encoding="utf-8"))
            g = layout.get("ground")
            if not isinstance(g, dict):
                m.update(ok=False, error="layout has no 'ground' section (ground_splat.py --write-layouts)")
            else:
                probs = []
                if g.get("material") != mi_asset(key):
                    probs.append(f"ground.material {g.get('material')!r} != {mi_asset(key)!r}")
                if g.get("splatRect") != meta["splatRect"]:
                    probs.append(f"ground.splatRect {g.get('splatRect')} != splat meta {meta['splatRect']}")
                if g.get("splatSha256") != m["sha256"]:
                    probs.append("ground.splatSha256 != the splat PNG")
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
    elif key == "Splat":
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
HLSL_ALBEDO = """// ENV-U10 M_EnvGround: layer blend + macro variation + accent (petals / wetness) + the M_MapBoard night grade
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
float3 c = W.x * F.Grade(C0, T0) + W.y * F.Grade(C1, T1) + W.z * F.Grade(C2, T2) + W.w * F.Grade(C3, T3);
float2 q = P / max(MacroScaleUU, 1.0);
float m = 0.65 * F.ValueNoise(q) + 0.35 * F.ValueNoise(q * 2.03 + 17.0);
c *= 1.0 + MacroStrength * (m * 2.0 - 1.0);
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
float3 lit = c * exp2(NightEV) * NightTint;
float luma = dot(lit, float3(0.2126, 0.7152, 0.0722));
return max(lerp(luma.xxx, lit, NightSaturation), 0.0);
"""
HLSL_NORMAL = """float3 n = W.x * N0 + W.y * N1 + W.z * N2 + W.w * N3;
n.xy *= NormalStrength;
return normalize(float3(n.xy, max(n.z, 0.001)));
"""
HLSL_AO = "return saturate(dot(W, float4(M0.r, M1.r, M2.r, M3.r)));"
HLSL_METAL = "return saturate(dot(W, float4(M0.b, M1.b, M2.b, M3.b)));"
HLSL_ROUGH = """float r = dot(W, float4(M0.g, M1.g, M2.g, M3.g));
float a = saturate((Accent * 255.0 - 1.0) / 254.0) * AccentOpacity;
return saturate(PetalSizeUU > 0.0 ? r : lerp(r, AccentRoughness, a));
"""

SCALAR_DEFAULTS = {"HeightContrast": 0.25, "NormalStrength": 1.0, "MacroStrength": 0.14, "MacroScaleUU": 240.0,
                   "AccentOpacity": 0.9, "AccentRoughness": 0.6, "AccentCarpet": 0.55, "PetalSizeUU": 7.0,
                   "NightEV": -0.7, "L1_HeightBlend": 1.0, "L2_HeightBlend": 1.0, "L3_HeightBlend": 1.0,
                   "NightSaturation": 0.7}


def build_material(defaults: dict, splat_default, specular: float, force: bool) -> dict:
    """M_EnvGround. defaults = {param name: texture} for the 12 layer textures (the first map's sets)."""
    eal, mel = u.EditorAssetLibrary, u.MaterialEditingLibrary
    material = u.load_asset(MATERIAL_PATH) if eal.does_asset_exist(MATERIAL_PATH) else None
    if material is not None and not force and eal.get_metadata_tag(material, GRAPH_TAG) == GRAPH_VERSION:
        return {"action": "unchanged", "path": MATERIAL_PATH, "graphVersion": GRAPH_VERSION}
    action = "rebuilt" if material is not None else "created"
    if material is None:
        material = u.AssetToolsHelpers.get_asset_tools().create_asset(MATERIAL_NAME, ROOT, u.Material,
                                                                      u.MaterialFactoryNew())
    if material is None:
        raise RuntimeError(f"could not create {MATERIAL_PATH}")
    material.set_editor_property("shading_model", u.MaterialShadingModel.MSM_DEFAULT_LIT)
    material.set_editor_property("blend_mode", u.BlendMode.BLEND_OPAQUE)
    material.set_editor_property("two_sided", False)
    mel.delete_all_material_expressions(material)
    ypos = [0]

    def expr(cls, x, y=None):
        node = mel.create_material_expression(material, cls, x, ypos[0] if y is None else y)
        if node is None:
            raise RuntimeError(f"could not create {cls}")
        if y is None:
            ypos[0] += 120
        return node

    def connect(src, out, dst, inp):
        if not mel.connect_material_expressions(src, out, dst, inp):
            raise RuntimeError(f"could not connect {src.get_name()}.{out or '<0>'} -> {dst.get_name()}.{inp}")

    def scalar(name, value):
        node = expr(u.MaterialExpressionScalarParameter, -2600)
        node.set_editor_property("parameter_name", name)
        node.set_editor_property("default_value", float(value))
        return node

    def vector(name, value):
        node = expr(u.MaterialExpressionVectorParameter, -2600)
        node.set_editor_property("parameter_name", name)
        node.set_editor_property("default_value", u.LinearColor(*[float(v) for v in value]))
        return node

    def custom(desc, out_type, inputs, code, x, y):
        node = expr(u.MaterialExpressionCustom, x, y)
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

    def sample(name, sampler_type, texture, source, x, y):
        node = expr(u.MaterialExpressionTextureSampleParameter2D, x, y)
        node.set_editor_property("parameter_name", name)
        node.set_editor_property("sampler_type", sampler_type)
        node.set_editor_property("texture", texture)  # after the sampler type: AutoSetSampleType keeps them consistent
        node.set_editor_property("sampler_source", source)
        return node

    cmot, st, ssm = u.CustomMaterialOutputType, u.MaterialSamplerType, u.SamplerSourceMode
    uv = expr(u.MaterialExpressionTextureCoordinate, -2600)
    uv.set_editor_property("coordinate_index", 0)
    strip = vector("GroundStrip", (-820.0, -560.0, 1640.0, 1030.0))
    rect = vector("SplatRect", (-820.0, -560.0, 1640.0, 1030.0))
    board = custom("GroundBoardXY", cmot.CMOT_FLOAT2, ("UV", "Strip"), HLSL_BOARD_XY, -2200, 0)
    connect(uv, "", board, "UV")
    connect(strip, "RGBA", board, "Strip")
    splat_uv = custom("GroundSplatUV", cmot.CMOT_FLOAT2, ("P", "Rect"), HLSL_SPLAT_UV, -1900, -300)
    connect(board, "", splat_uv, "P")
    connect(rect, "RGBA", splat_uv, "Rect")
    splat = sample("Splat", st.SAMPLERTYPE_LINEAR_COLOR, splat_default, ssm.SSM_CLAMP_WORLD_GROUP_SETTINGS, -1600, -300)
    connect(splat_uv, "", splat, "UVs")
    samples = {}
    for i in range(LAYERS):
        tile = scalar(f"L{i}_TileUU", 200.0)
        div = expr(u.MaterialExpressionDivide, -1900, 200 + 700 * i)
        connect(board, "", div, "A")
        connect(tile, "", div, "B")
        for k, (stype, dy) in {"BC": (st.SAMPLERTYPE_COLOR, 0), "N": (st.SAMPLERTYPE_NORMAL, 220),
                               "ORMH": (st.SAMPLERTYPE_MASKS, 440)}.items():
            node = sample(f"L{i}_{k}", stype, defaults[f"L{i}_{k}"], ssm.SSM_WRAP_WORLD_GROUP_SETTINGS, -1600,
                          200 + 700 * i + dy)
            connect(div, "", node, "UVs")
            samples[(i, k)] = node
    s = {name: scalar(name, SCALAR_DEFAULTS[name]) for name in SCALAR_DEFAULTS}
    tints = [vector(f"L{i}_Tint", (1.0, 1.0, 1.0, 1.0)) for i in range(LAYERS)]
    accent_color = vector("AccentColor", (0.87, 0.4, 0.51, 1.0))
    night_tint = vector("NightTint", (0.9317, 1.0042, 1.1595, 1.0))

    weights = custom("GroundWeights", cmot.CMOT_FLOAT4, ("Splat", "H1", "H2", "H3", "B1", "B2", "B3", "Contrast"),
                     HLSL_WEIGHTS, -1100, -300)
    connect(splat, "RGBA", weights, "Splat")
    for i in (1, 2, 3):
        connect(samples[(i, "ORMH")], "A", weights, f"H{i}")
        connect(s[f"L{i}_HeightBlend"], "", weights, f"B{i}")
    connect(s["HeightContrast"], "", weights, "Contrast")

    albedo_inputs = (["W"] + [f"C{i}" for i in range(LAYERS)] + [f"T{i}" for i in range(LAYERS)]
                     + ["P", "Accent", "AccentColor", "AccentOpacity", "AccentCarpet", "PetalSizeUU", "MacroStrength",
                        "MacroScaleUU", "NightEV", "NightSaturation", "NightTint"])
    albedo = custom("GroundAlbedo", cmot.CMOT_FLOAT3, albedo_inputs, HLSL_ALBEDO, -600, -300)
    connect(weights, "", albedo, "W")
    for i in range(LAYERS):
        connect(samples[(i, "BC")], "RGB", albedo, f"C{i}")
        connect(tints[i], "RGBA", albedo, f"T{i}")
    connect(board, "", albedo, "P")
    connect(splat, "A", albedo, "Accent")
    connect(accent_color, "RGB", albedo, "AccentColor")
    for name in ("AccentOpacity", "AccentCarpet", "PetalSizeUU", "MacroStrength", "MacroScaleUU", "NightEV",
                 "NightSaturation"):
        connect(s[name], "", albedo, name)
    connect(night_tint, "RGB", albedo, "NightTint")
    mel.connect_material_property(albedo, "", u.MaterialProperty.MP_BASE_COLOR)

    normal = custom("GroundNormal", cmot.CMOT_FLOAT3, ["W"] + [f"N{i}" for i in range(LAYERS)] + ["NormalStrength"],
                    HLSL_NORMAL, -600, 300)
    connect(weights, "", normal, "W")
    for i in range(LAYERS):
        connect(samples[(i, "N")], "RGB", normal, f"N{i}")
    connect(s["NormalStrength"], "", normal, "NormalStrength")
    mel.connect_material_property(normal, "", u.MaterialProperty.MP_NORMAL)

    orm_pins = ["W"] + [f"M{i}" for i in range(LAYERS)]
    for desc, code, prop, extra, y in (
            ("GroundAO", HLSL_AO, u.MaterialProperty.MP_AMBIENT_OCCLUSION, [], 600),
            ("GroundRoughness", HLSL_ROUGH, u.MaterialProperty.MP_ROUGHNESS,
             ["Accent", "AccentOpacity", "AccentRoughness", "PetalSizeUU"], 750),
            ("GroundMetallic", HLSL_METAL, u.MaterialProperty.MP_METALLIC, [], 900)):
        node = custom(desc, cmot.CMOT_FLOAT1, orm_pins + extra, code, -600, y)
        connect(weights, "", node, "W")
        for i in range(LAYERS):
            connect(samples[(i, "ORMH")], "RGB", node, f"M{i}")
        if extra:
            connect(splat, "A", node, "Accent")
            for name in ("AccentOpacity", "AccentRoughness", "PetalSizeUU"):
                connect(s[name], "", node, name)
        mel.connect_material_property(node, "", prop)
    spec = expr(u.MaterialExpressionConstant, -600, 1050)
    spec.set_editor_property("r", float(specular))
    mel.connect_material_property(spec, "", u.MaterialProperty.MP_SPECULAR)

    mel.recompile_material(material)
    eal.set_metadata_tag(material, GRAPH_TAG, GRAPH_VERSION)
    if not eal.save_loaded_asset(material, False):
        raise RuntimeError(f"could not save {MATERIAL_PATH}")
    return {"action": action, "path": MATERIAL_PATH, "graphVersion": GRAPH_VERSION,
            "expressions": int(mel.get_num_material_expressions(material)),
            "textureParams": sorted(str(n) for n in mel.get_texture_parameter_names(material))}


def mi_want(key: str, params: dict, textures: dict, splat, rect: list) -> dict:
    """The MI parameters of one map: {'tex': {name: texture}, 'scalar': {name: value}, 'vector': {name: rgba}}."""
    mp = params["maps"][key]
    m = params["material"]
    tex, scal, vec = {"Splat": splat}, {}, {}
    for i, lay in enumerate(mp["layers"]):
        for k in KEYS:
            tex[f"L{i}_{k}"] = textures[(lay["set"], k)]
        scal[f"L{i}_TileUU"] = float(lay["tileUU"])
        if i > 0:
            scal[f"L{i}_HeightBlend"] = float(lay.get("heightBlend", 1.0))
        vec[f"L{i}_Tint"] = tuple(float(v) for v in lay["tint"]) + (float(lay["saturation"]),)
    ac, gr = mp["accent"], mp["grade"]
    scal.update({"HeightContrast": float(m["heightContrast"]), "NormalStrength": float(m["normalStrength"]),
                 "MacroStrength": float(m["macroStrength"]), "MacroScaleUU": float(m["macroScaleUU"]),
                 "AccentOpacity": float(ac["opacity"]), "AccentRoughness": float(ac["roughness"]),
                 "AccentCarpet": float(ac.get("carpet", 0.0)),
                 "PetalSizeUU": float(ac["petalSizeUU"]), "NightEV": float(gr["ev"]),
                 "NightSaturation": float(gr["saturation"])})
    x0, y0, x1, y1 = (float(v) for v in rect)
    vec.update({"AccentColor": tuple(float(v) for v in ac["color"]) + (1.0,),
                "NightTint": tuple(float(v) for v in gr["tint"]) + (1.0,),
                "SplatRect": (x0, y0, x1 - x0, y1 - y0), "GroundStrip": (x0, y0, x1 - x0, y1 - y0)})
    return {"tex": tex, "scalar": scal, "vector": vec}


def ensure_instance(key: str, material, want: dict) -> dict:
    eal, mel = u.EditorAssetLibrary, u.MaterialEditingLibrary
    path = mi_asset(key)
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
        return st

    target = {"parent": material.get_path_name()}
    target.update({"t:" + k: v.get_path_name() for k, v in want["tex"].items()})
    target.update({"s:" + k: round(v, 5) for k, v in want["scalar"].items()})
    target.update({"v:" + k: tuple(round(x, 5) for x in v) for k, v in want["vector"].items()})
    if action == "updated" and current() == target:
        return {"action": "unchanged", "path": path}
    mel.set_material_instance_parent(mi, material)
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
    splats = {}
    for key in keys:
        m = pl["maps"][key]
        out = {}
        result["maps"][key] = out
        if not m.get("ok"):
            out["splat"] = {"action": "skipped", "error": m.get("error")}
            ok = False
            continue
        try:
            out["splat"] = import_texture(m["source"], m["sha256"], m["splatAsset"], "Splat", force)
            splats[key] = u.load_asset(m["splatAsset"])
        except Exception as exc:  # noqa: BLE001
            out["splat"] = {"action": "failed", "error": f"{type(exc).__name__}: {exc}"}
            ok = False
    ready = [k for k in keys if k in splats and all((lay["set"], kk) in textures
                                                     for lay in params["maps"][k]["layers"] for kk in KEYS)]
    if not ready:
        result["material"] = {"action": "skipped", "error": "no map has all its textures"}
        return result, False
    first = ready[0]
    defaults = {f"L{i}_{k}": textures[(lay["set"], k)] for i, lay in enumerate(params["maps"][first]["layers"])
                for k in KEYS}
    try:
        result["material"] = build_material(defaults, splats[first], float(params["material"]["specular"]), force)
        material = u.load_asset(MATERIAL_PATH)
    except Exception as exc:  # noqa: BLE001
        result["material"] = {"action": "failed", "error": f"{type(exc).__name__}: {exc}"}
        return result, False
    for key in keys:
        if key not in ready:
            result["maps"][key]["materialInstance"] = {"action": "skipped", "error": "textures missing"}
            ok = False
            continue
        try:
            want = mi_want(key, params, textures, splats[key], pl["maps"][key]["splatRect"])
            result["maps"][key]["materialInstance"] = ensure_instance(key, material, want)
        except Exception as exc:  # noqa: BLE001
            result["maps"][key]["materialInstance"] = {"action": "failed", "error": f"{type(exc).__name__}: {exc}"}
            ok = False
    listing = sorted(str(p).split(".")[0] for p in u.EditorAssetLibrary.list_assets(ROOT, recursive=True,
                                                                                      include_folder=False))
    planned = {MATERIAL_PATH} | {mi_asset(k) for k in MAPS} | {splat_asset(k) for k in MAPS}
    planned |= {texture_asset(s, k) for s in params["sets"] for k in KEYS}
    result["folder"] = {"assets": len(listing), "foreign": [a for a in listing if a not in planned]}
    return result, ok


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
              "material": MATERIAL_PATH, "graphVersion": GRAPH_VERSION, "maps": keys}
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
