"""UE inputs of a hero look-dev run for M_UM_Figure_v2 (LD-<hero>-ue): LUT in the v2 layout, EdgeMask, debug zone ID.

    python tools/art/material_library/lookdev_ue_inputs.py --config <build-profiles/<hero>-h2-lookdev-ue-lut.json>

The Blender look-dev stage of a hero writes its class tones and LUT overrides in its own format (Merlin: EXR 16 x 8,
Ymed in row 7.R, EdgeMask in TeamMaskRGBA.A, LDM-7/LDM-9). The v2 master reads a 16 x 16 RGBA16F LUT (ymedClassHero in
row 8, LDV-1) and a separate EdgeMaskTexture (LDV-8). This script converts, deterministically, into
<lookdev run>/ue-inputs/:

  T_UM_MatLUT_<Hero>.dds             16 x 16 RGBA16F, the one LUT generator (build_ue_inputs.class_columns/lut_array)
  T_UM_MatLUT_<Hero>.overrides.json  overrides actually applied: the Blender stage (ld-lut.json "overrides", converted
                                     to LUT fields) + the UE look-dev layer of the config (lut.ue_lookdev), in that order
  T_<Hero>_H2LD_EdgeMask_2K.png      L8, one channel of a look-dev texture (Merlin: TeamMaskRGBA.A)
  T_<Hero>_H2LD_ZoneID_2K.png        L8 DEBUG texture: look-dev zone index + 1, encoded x16+8 like MatID, so a debug MI
                                     (MatIDTexture = this, DebugView 1) paints every zone in its own colour; 2K = the
                                     majority of each 2 x 2 block of the 4K zone map of the look-dev stage (0 = none)
  ue-inputs-report.json              sha256/px/tier of every output (a textures report adopt can pin), the zone legend,
                                     the converted overrides and the sha256 of every input

The config is the only hand-edited input; the UE look-dev loop changes lut.ue_lookdev (and MI parameters of the import
profile), never the bake textures. Stdlib + numpy + PIL; no Blender, no UE. Same inputs -> same bytes.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

import numpy as np
from PIL import Image

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
sys.path.insert(0, str(HERE))
import build_ue_inputs as B  # noqa: E402

SCHEMA_CONFIG = "unmatched.um-v2-lookdev-ue-lut/1"
SCHEMA_REPORT = "unmatched.um-v2-lookdev-ue-inputs/1"
GENERATOR = "tools/art/material_library/lookdev_ue_inputs.py"
GENERATOR_VERSION = "1.0.0"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def rel(path: Path) -> str:
    return path.resolve().relative_to(REPO).as_posix()


def blender_overrides_to_lut(ov: dict) -> dict:
    """Overrides of the Blender look-dev stage (preset-shaped: baseColor.typicalLinear, roughness{...}, cloth.sheenColor,
    teamDyeAllowed, heroYmed) -> LUT fields of build_ue_inputs (bc, roughTypical, ..., ymedClassHero)."""
    out = {}
    for cid, f in sorted(ov.items()):
        o = {}
        for key, value in sorted(f.items()):
            if key == "note":
                continue
            if key == "baseColor":
                o["bc"] = [float(v) for v in value["typicalLinear"]]
            elif key == "teamDyeAllowed":
                o["teamDyeAllowed"] = 1.0 if value else 0.0
            elif key == "heroYmed":
                o["ymedClassHero"] = float(value)
            elif key == "roughness":
                o["roughTypical"] = float(value["typical"])
                o["roughLo"], o["roughHi"] = (float(v) for v in value["range"])
                o["roughVariation"] = float(value["variation"])
            elif key == "cloth":
                sc = value.get("sheenColor") or {}
                if "intensity" in sc:
                    o["sheenIntensity"] = float(sc["intensity"])
                if "tint" in sc:
                    o["sheenTint"] = float(sc["tint"])
                for k2 in value:
                    if k2 not in ("sheenColor",):
                        raise SystemExit("blender override %s.cloth.%s: no LUT field" % (cid, k2))
            else:
                raise SystemExit("blender override %s.%s: no LUT field" % (cid, key))
        out[cid] = o
    return out


def zone_palette(n: int, exposure: float) -> list:
    """n linear colours from the grid {0, 0.25, 0.8, 2.5}^3 (no black), greedy max-min distance of their sRGB display
    value clip(c x exposure) - deterministic (fixed grid order, first bright white-free pick = pure red)."""
    levels = (0.0, 0.25, 0.8, 2.5)
    grid = [np.array([r, g, b]) for r in levels for g in levels for b in levels if max(r, g, b) >= 0.8]
    disp = [B.linear_to_srgb8(np.clip(c * exposure, 0, 1)).astype(np.float64) for c in grid]
    chosen = [0]
    while len(chosen) < n:
        best, best_d = None, -1.0
        for i in range(len(grid)):
            if i in chosen:
                continue
            d = min(float(np.linalg.norm(disp[i] - disp[j])) for j in chosen)
            if d > best_d + 1e-9:
                best, best_d = i, d
        chosen.append(best)
    return [grid[i] for i in chosen]


def merge(*layers) -> dict:
    res = {}
    for layer in layers:
        for cid, fields in sorted(layer.items()):
            res.setdefault(cid, {}).update({k: v for k, v in fields.items() if k != "why"})
    return res


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--config", required=True)
    a = ap.parse_args()
    cfg_path = Path(a.config).resolve()
    cfg = json.loads(cfg_path.read_text(encoding="utf-8"))
    if cfg.get("schema") != SCHEMA_CONFIG:
        raise SystemExit("config schema %r, expected %s" % (cfg.get("schema"), SCHEMA_CONFIG))
    hero = cfg["hero"]
    run = REPO / cfg["lookdev_run"]
    out = run / "ue-inputs"
    out.mkdir(parents=True, exist_ok=True)
    inputs = {rel(cfg_path): sha(cfg_path)}

    # ---- LUT: presets -> Blender-stage overrides -> UE look-dev layer
    lut_rep_path = run / cfg["lut"]["blender_lut_report"]
    lut_rep = json.loads(lut_rep_path.read_text(encoding="utf-8"))
    inputs[rel(lut_rep_path)] = sha(lut_rep_path)
    if lut_rep.get("hero") != hero:
        raise SystemExit("LUT report hero %r != %s" % (lut_rep.get("hero"), hero))
    blender_layer = blender_overrides_to_lut(lut_rep["overrides"])
    ue_layer = cfg["lut"].get("ue_lookdev") or {}
    merged = merge(blender_layer, ue_layer)
    ov_doc = {"schema": "unmatched.um-v2-hero-overrides/1", "hero": hero, "generator": GENERATOR,
              "rebuild": "python %s --config %s" % (GENERATOR, rel(cfg_path)),
              "layers": {"blender_lookdev": {"source": rel(lut_rep_path) + "#overrides", "classes": blender_layer},
                         "ue_lookdev": {"source": rel(cfg_path) + "#lut.ue_lookdev", "classes": ue_layer}},
              "classes": merged}
    ov_path = out / ("T_UM_MatLUT_%s.overrides.json" % hero)
    ov_path.write_text(json.dumps(ov_doc, indent=1, sort_keys=True, ensure_ascii=False) + "\n", encoding="utf-8",
                       newline="\n")
    presets = B.load_presets()
    inputs[rel(B.PRESETS)] = sha(B.PRESETS)
    cols = B.class_columns(presets)
    applied = B.apply_overrides(cols, {"classes": merged}, presets)
    lut = B.lut_array(cols)
    lut_path = out / ("T_UM_MatLUT_%s.dds" % hero)
    B.write_dds(lut_path, [lut.astype(np.float16)], "R16G16B16A16_FLOAT")
    columns = {str(i): {k: (round(v, 6) if isinstance(v, float) else v) for k, v in sorted(f.items())}
               for i, f in sorted(cols.items())}

    # ---- EdgeMask: one channel of a look-dev texture
    em = cfg["edge_mask"]
    src = run / em["source"]
    inputs[rel(src)] = sha(src)
    im = Image.open(src)
    ch = im.getbands().index(em["channel"])
    edge = np.asarray(im)[..., ch].astype(np.uint8)
    edge_path = out / em["out"]
    Image.fromarray(edge, "L").save(edge_path, optimize=False, compress_level=9)

    # ---- debug zone ID (2K majority of the 4K zone map), zone index + 1
    zd = cfg["zone_debug"]
    maps_rep_path = run / zd["maps_report"]
    maps_rep = json.loads(maps_rep_path.read_text(encoding="utf-8"))
    inputs[rel(maps_rep_path)] = sha(maps_rep_path)
    zt = maps_rep["zone_texture"]
    zsrc = REPO / zt["path"]
    if not zsrc.is_file() or sha(zsrc) != zt["sha256"]:
        raise SystemExit("zone map missing or changed since the look-dev maps stage: %s" % zt["path"])
    inputs[zt["path"]] = zt["sha256"]
    order = maps_rep["zones"]
    if len(order) > 15:
        raise SystemExit("more than 15 zones")
    z4 = (np.asarray(Image.open(zsrc)).astype(np.int32) - 8) // 16          # 0..n-1
    h, w = z4.shape
    blocks = z4.reshape(h // 2, 2, w // 2, 2).transpose(0, 2, 1, 3).reshape(h // 2, w // 2, 4)
    counts = np.stack([(blocks == k).sum(-1) for k in range(len(order))], -1)
    z2 = counts.argmax(-1) + 1                                                 # ties -> lower zone index
    zone_path = out / zd["out"]
    Image.fromarray((z2 * 16 + 8).astype(np.uint8), "L").save(zone_path, optimize=False, compress_level=9)
    legend = {str(i + 1): {"zone": z, "class": maps_rep["zone_class"][z],
                           "texels_2k": int((z2 == i + 1).sum())} for i, z in enumerate(order)}
    # debug zone LUT: every zone id takes the metal path (bcMode 1, no Ymed, no detail AO, no dye, no wear) with a
    # distinct saturated colour in row 0, so DebugView 7 (albedo) + DebugBakeFromLUT 1 paints each zone in one flat
    # colour far from the others (the hashed pastel colours of DebugView 1 are only 10-20 sRGB levels apart)
    palette = zone_palette(len(order), float(zd.get("palette_exposure", 0.34)))
    zlut = np.zeros((B.LUT_H, B.LUT_W, 4), np.float32)
    for i, col in enumerate(palette):
        zlut[0, i + 1] = [col[0], col[1], col[2], 1.0]
        zlut[2, i + 1] = [0.5, 0.0, 0.0, 1.0]
        zlut[1, i + 1] = [1.0, 1.0, 1.0, 0.0]
        zlut[7, i + 1] = [0.0, 1.0, 1.0, 0.0]
    zlut_path = out / zd["lut_out"]
    B.write_dds(zlut_path, [zlut.astype(np.float16)], "R16G16B16A16_FLOAT")
    for i, col in enumerate(palette):
        legend[str(i + 1)]["debug_lut_colour"] = [round(float(c), 3) for c in col]

    def tex(path, tier, key, note):
        px = list(Image.open(path).size) if path.suffix == ".png" else [B.LUT_W, B.LUT_H]
        return {"path": rel(path), "sha256": sha(path), "bytes": path.stat().st_size, "px": px, "tier": tier,
                "map": key, "note": note}

    report = {
        "schema": SCHEMA_REPORT, "generator": GENERATOR, "generator_version": GENERATOR_VERSION, "hero": hero,
        "profile_id": cfg["lookdev_profile_id"], "config": rel(cfg_path), "inputs": dict(sorted(inputs.items())),
        "textures": {
            lut_path.name: tex(lut_path, "runtime_lut", "MatLUT",
                               "16 x 16 RGBA16F DDS (M_UM_Figure_v2 layout, LDV-1); UE TC_HDR, Nearest, NoMipmaps, "
                               "NeverStream, sRGB off"),
            edge_path.name: tex(edge_path, cfg["texture_tier"], "EdgeMask",
                                "L8 = %s.%s (LDM-9 -> LDV-8); UE TC_Grayscale, sRGB off" % (em["source"], em["channel"])),
            zone_path.name: tex(zone_path, cfg["texture_tier"], "ZoneID",
                                "DEBUG ONLY: zone index + 1, x16+8; UE TC_Grayscale, Nearest, NoMipmaps, NeverStream"),
            zlut_path.name: tex(zlut_path, "runtime_lut", "ZoneLUT",
                                "DEBUG ONLY: 16 x 16 RGBA16F, row 0 = flat zone colour (metal path), for the debug MI "
                                "with ZoneID in the MatID slot, DebugView 7, DebugBakeFromLUT 1"),
        },
        "conventions": {"MatLUT": "RGBA16F linear, rows 0-9 of build_ue_inputs.LUT_ROWS, column = class index",
                        "EdgeMask": "linear L8, 1 = convex edge", "ZoneID": "linear L8, value = (zone + 1) x 16 + 8",
                        "ZoneLUT": "RGBA16F debug LUT, row 0 = flat zone colour"},
        "zone_legend": legend,
        "lut": {"overrides_file": rel(ov_path), "overrides_sha256": sha(ov_path), "applied": applied,
                "columns": columns, "rows": {str(k): list(v) for k, v in B.LUT_ROWS.items()},
                "half_max_abs_error": round(float(np.abs(lut.astype(np.float16).astype(np.float32) - lut).max()), 6)},
        "edge_mask_stats": {"p50_p95_p99": [int(v) for v in np.percentile(edge, [50, 95, 99])]},
    }
    rp = out / "ue-inputs-report.json"
    rp.write_text(json.dumps(report, indent=1, sort_keys=True, ensure_ascii=False) + "\n", encoding="utf-8",
                  newline="\n")
    for name, t in report["textures"].items():
        print(name, t["sha256"][:12], t["px"])
    print("overrides", len(applied), "fields; report", rel(rp))
    return 0


if __name__ == "__main__":
    sys.exit(main())
