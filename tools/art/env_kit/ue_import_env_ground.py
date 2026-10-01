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
           /Game/EnvKit/Ground/M_EnvWaterfall                      P4: the waterfall card material (masked, lit)
           /Game/EnvKit/Ground/MI_EnvWaterfall_<Map>               only maps with ground-params 'water.falls'
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
M_EnvWaterfall (masked, clip 0.5, lit, two-sided): FallCard = (width, height, kind 0 card / 1 spill, 0) per
  component (S08EnvGround sets it on the MID); streaks scroll along +v at FallFlow.x uu/s (v runs down the card and
  towards the lip on the spill), foam at the lip and in the streaks, side fade FallFlow.z uu, bottom fade FallFlow.w,
  spill far-edge fade FallSpill.x uu, the soft fades dithered in screen space (interleaved gradient noise on
  SvPosition, amount FallSpill.y; no DitherTemporalAA node - it is not in the UE 5.8 headers); ripple normal along the
  flow; emissive = graded colour * FallShade.w.
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
SHA_TAG = "EnvGroundSourceSha256"
GRAPH_TAG = "EnvGroundGraphVersion"
GRAPH_VERSION = "2"
FALL_GRAPH_VERSION = "1"
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
    for key in keys:
        m = {"ok": True, "splatAsset": splat_asset(key), "auxAsset": aux_asset(key), "mi": mi_asset(key)}
        if has_falls(params, key):
            m["fallMi"] = fall_mi_asset(key)
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
                m["waterfalls"] = len(falls)
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


# --- M_EnvWaterfall (P4, review gap 1): the waterfall card + the spill over the T2 lip ---------------------------------
HLSL_FALL_CORE = """// P4 M_EnvWaterfall: FallCard = (width uu, height uu, kind: 0 the vertical card / 1 the flat spill, 0) per component
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
float2 p = UV * size;  // uu: x across the fall, y along the flow (down the card / towards the lip on the spill)
float sc = max(FallFlow.y, 1.0);
float2 q = float2(p.x / sc, (p.y - Time * FallFlow.x) / (sc * 5.0));
float streak = 0.6 * F.ValueNoise(q) + 0.4 * F.ValueNoise(q * float2(2.1, 1.7) + 7.3);
float foam = spill ? saturate(UV.y * 1.4 - 0.5) * (0.5 + streak)
                   : saturate(streak * 1.5 - 0.35) * (0.55 + 0.45 * saturate(1.0 - UV.y * 1.5)) + 0.6 * saturate(1.0 - p.y / 14.0);
foam = saturate(foam) * WaterFoam.a;
float side = smoothstep(0.0, max(FallFlow.z, 0.5), p.x) * smoothstep(0.0, max(FallFlow.z, 0.5), size.x - p.x);
float alpha = side * (0.75 + 0.5 * streak);
alpha *= spill ? smoothstep(0.0, max(FallSpill.x, 0.5), p.y)
               : 1.0 - smoothstep(1.0 - FallFlow.w, 1.0, UV.y + 0.25 * (streak - 0.5));
float3 base = lerp(WaterColor.rgb, WaterFoam.rgb, foam);
float3 lit = base * exp2(NightEV) * NightTint;
float luma = dot(lit, float3(0.2126, 0.7152, 0.0722));
float3 graded = max(lerp(luma.xxx, lit, NightSaturation), 0.0);
"""
FALL_CORE_INPUTS = ("UV", "Time", "FallCard", "FallFlow", "FallSpill", "WaterColor", "WaterFoam", "NightEV",
                    "NightSaturation", "NightTint")
HLSL_FALL_ALBEDO = HLSL_FALL_CORE + "return graded;\n"
HLSL_FALL_EMISSIVE = HLSL_FALL_CORE + "return graded * FallShade.w;\n"
HLSL_FALL_OPACITY = HLSL_FALL_CORE + """// screen-space dither of the soft fades (opacity mask clip 0.5; TSR smooths it)
float2 px = Parameters.SvPosition.xy;
float ign = frac(52.9829189 * frac(dot(px, float2(0.06711056, 0.00583715))));
return saturate(alpha + (ign - 0.5) * FallSpill.y);
"""
HLSL_FALL_ROUGH = HLSL_FALL_CORE + "return saturate(lerp(FallShade.x, 0.6, foam));\n"
HLSL_FALL_RIPPLE_UV = """float2 p = UV * max(FallCard.xy, float2(1.0, 1.0));
return float2(p.x, p.y - Time * FallFlow.x) / max(RippleTileUU, 1.0);
"""
HLSL_FALL_NORMAL = "return normalize(float3(R.xy * FallShade.z, 1.0));"
HLSL_FALL_SPECULAR = "return saturate(FallShade.y);"
FALL_SCALAR_DEFAULTS = {"NightEV": -1.0, "NightSaturation": 0.7, "RippleTileUU": 70.0}
FALL_VECTOR_DEFAULTS = {"FallCard": (200.0, 230.0, 0.0, 0.0), "FallFlow": (55.0, 9.0, 12.0, 0.35),
                        "FallSpill": (18.0, 0.5, 0.0, 0.0), "FallShade": (0.08, 0.25, 0.5, 0.6),
                        "WaterColor": (0.0159, 0.0497, 0.141, 0.55), "WaterFoam": (0.62, 0.66, 0.7, 0.85),
                        "NightTint": (0.9317, 1.0042, 1.1595, 1.0)}


def build_waterfall_material(ripple_default, force: bool) -> dict:
    material, action = _begin_material(FALL_MATERIAL_PATH, FALL_MATERIAL_NAME, FALL_GRAPH_VERSION, force)
    if action == "unchanged":
        return {"action": "unchanged", "path": FALL_MATERIAL_PATH, "graphVersion": FALL_GRAPH_VERSION}
    mel = u.MaterialEditingLibrary
    material.set_editor_property("shading_model", u.MaterialShadingModel.MSM_DEFAULT_LIT)
    material.set_editor_property("blend_mode", u.BlendMode.BLEND_MASKED)
    material.set_editor_property("opacity_mask_clip_value", 0.5)
    material.set_editor_property("two_sided", True)
    g = _Graph(material)
    cmot, st, ssm = u.CustomMaterialOutputType, u.MaterialSamplerType, u.SamplerSourceMode
    uv = g.expr(u.MaterialExpressionTextureCoordinate, -2000)
    uv.set_editor_property("coordinate_index", 0)
    t = g.expr(u.MaterialExpressionTime, -2000)
    s = {name: g.scalar(name, val) for name, val in FALL_SCALAR_DEFAULTS.items()}
    v = {name: g.vector(name, val) for name, val in FALL_VECTOR_DEFAULTS.items()}
    src = {"UV": (uv, ""), "Time": (t, ""), "NightEV": (s["NightEV"], ""),
           "NightSaturation": (s["NightSaturation"], ""), "NightTint": (v["NightTint"], "RGB")}
    for name in ("FallCard", "FallFlow", "FallSpill", "WaterColor", "WaterFoam", "FallShade"):
        src[name] = (v[name], "RGBA")
    nodes = {}
    for desc, code, out_type, extra, y in (
            ("FallAlbedo", HLSL_FALL_ALBEDO, cmot.CMOT_FLOAT3, (), -300),
            ("FallEmissive", HLSL_FALL_EMISSIVE, cmot.CMOT_FLOAT3, ("FallShade",), 0),
            ("FallOpacity", HLSL_FALL_OPACITY, cmot.CMOT_FLOAT1, (), 300),
            ("FallRoughness", HLSL_FALL_ROUGH, cmot.CMOT_FLOAT1, ("FallShade",), 600)):
        pins = FALL_CORE_INPUTS + extra
        node = g.custom(desc, out_type, pins, code, -800, y)
        g.wire(node, {p: src[p] for p in pins})
        nodes[desc] = node
    ruv = g.custom("FallRippleUV", cmot.CMOT_FLOAT2, ("UV", "Time", "FallCard", "FallFlow", "RippleTileUU"),
                   HLSL_FALL_RIPPLE_UV, -1500, 900)
    g.wire(ruv, {"UV": src["UV"], "Time": src["Time"], "FallCard": src["FallCard"], "FallFlow": src["FallFlow"],
                 "RippleTileUU": (s["RippleTileUU"], "")})
    rs = g.sample("WaterRippleN", st.SAMPLERTYPE_NORMAL, ripple_default, ssm.SSM_WRAP_WORLD_GROUP_SETTINGS, -1200, 900)
    g.connect(ruv, "", rs, "UVs")
    normal = g.custom("FallNormal", cmot.CMOT_FLOAT3, ("R", "FallShade"), HLSL_FALL_NORMAL, -800, 900)
    g.wire(normal, {"R": (rs, "RGB"), "FallShade": src["FallShade"]})
    spec = g.custom("FallSpecular", cmot.CMOT_FLOAT1, ("FallShade",), HLSL_FALL_SPECULAR, -800, 1100)
    g.wire(spec, {"FallShade": src["FallShade"]})
    mel.connect_material_property(nodes["FallAlbedo"], "", u.MaterialProperty.MP_BASE_COLOR)
    mel.connect_material_property(nodes["FallEmissive"], "", u.MaterialProperty.MP_EMISSIVE_COLOR)
    mel.connect_material_property(nodes["FallOpacity"], "", u.MaterialProperty.MP_OPACITY_MASK)
    mel.connect_material_property(nodes["FallRoughness"], "", u.MaterialProperty.MP_ROUGHNESS)
    mel.connect_material_property(normal, "", u.MaterialProperty.MP_NORMAL)
    mel.connect_material_property(spec, "", u.MaterialProperty.MP_SPECULAR)
    _finish_material(material, FALL_MATERIAL_PATH, FALL_GRAPH_VERSION)
    return {"action": action, "path": FALL_MATERIAL_PATH, "graphVersion": FALL_GRAPH_VERSION,
            "expressions": int(mel.get_num_material_expressions(material))}


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


def fall_mi_want(key: str, params: dict, ripple=None) -> dict:
    """MI_EnvWaterfall_<Map>: the water colour / foam / grade of the map and the look of its first fall entry."""
    mp = params["maps"][key]
    w = mp.get("water") or {}
    f = (w.get("falls") or [{}])[0]
    gr = mp["grade"]
    wv = _water(params, key)
    tex = {"WaterRippleN": ripple} if ripple is not None else {}
    scal = {"NightEV": float(gr["ev"]), "NightSaturation": float(gr["saturation"]),
            "RippleTileUU": float(wv["WaterRipple"][0])}
    vec = {"WaterColor": wv["WaterColor"], "WaterFoam": wv["WaterFoam"],
           "NightTint": tuple(float(v) for v in gr["tint"]) + (1.0,),
           "FallFlow": (float(f.get("flowUUps", 55.0)), float(f.get("streakScaleUU", 9.0)),
                        float(f.get("edgeFadeUU", 12.0)), float(f.get("bottomFade", 0.35))),
           "FallSpill": (float(f.get("spillFadeUU", 18.0)), float(f.get("dither", 0.5)), 0.0, 0.0),
           "FallShade": (wv["WaterSurface"][0] + 0.02, wv["WaterSurface"][1], wv["WaterSurface"][2],
                         wv["WaterSurface"][3])}
    return {"tex": tex, "scalar": scal, "vector": vec}


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
    fall_material = None
    if any(has_falls(params, k) for k in ready):
        try:
            result["waterfallMaterial"] = build_waterfall_material(ripple, force)
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
                    fall_mi_asset(key), fall_material, fall_mi_want(key, params, ripple))
            except Exception as exc:  # noqa: BLE001
                result["maps"][key]["waterfallInstance"] = {"action": "failed",
                                                            "error": f"{type(exc).__name__}: {exc}"}
                ok = False
    listing = sorted(str(p).split(".")[0] for p in u.EditorAssetLibrary.list_assets(ROOT, recursive=True,
                                                                                      include_folder=False))
    result["folder"] = {"assets": len(listing), "foreign": [a for a in listing if a not in planned_assets(params)]}
    return result, ok


def planned_assets(params: dict) -> set:
    """Every asset this tool may own under /Game/EnvKit/Ground (the 'foreign' listing of the report)."""
    planned = {MATERIAL_PATH, FALL_MATERIAL_PATH, ripple_asset()}
    planned |= {mi_asset(k) for k in MAPS} | {splat_asset(k) for k in MAPS} | {aux_asset(k) for k in MAPS}
    planned |= {fall_mi_asset(k) for k in MAPS}
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
              "waterfallGraphVersion": FALL_GRAPH_VERSION, "maps": keys}
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
