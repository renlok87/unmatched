"""Stage `atlas` for Harpy (ASSET-HARPY-001): pack the per-part Tripo textures of the segmented retopology into
one 2K BC / Normal / ORM atlas for the figure, WITHOUT the Tripo base part.

    python atlas_harpy.py --run-dir art/pipeline-candidates/ASSET-HARPY-001/20260928-blender-um-fbx-v1

Why not the CLI atlas stage (tools/tripo-pipeline/candidate/atlas.py, called by tripo_pipeline.py atlas):
it packs every mesh node of the GLB at its native texture size. Harpy's 9 parts carry 3 x 1024^2 + 4 x 512^2
+ 2 x 256^2 = 4 325 376 px, more than a 2048^2 atlas holds (4 194 304 px); atlas.py stops with
"cannot fit tripo_part_7 at 256px" (reproduced in logs/atlas-cli-2k-probe.log), and a 4K atlas would be 74 %
empty. The Tripo base (tripo_part_4, 512^2) is replaced by a parametric base without textures in the
build (04 §3.8: bases are parameter/vertex-colour objects), so it is excluded here and the 8 figure parts
(4 063 232 px) fit at native size. Everything else is atlas.py unchanged (algorithm, conventions, report
schema): quadtree cells by (-texture width, part index), LANCZOS resize into the cell minus the gutter,
edge bleed, BaseColor x uniform baseColorFactor, ORM = (occlusion fill, Tripo roughness G, metallic B),
DirectX normal = OpenGL normal with the green channel inverted. One addition: the normal texels are renormalised
to unit length after the resize (Tripo's per-part normal maps are only 97.6-99.9 % unit length and the
LANCZOS upscale into the BC-sized cells overshoots; atlas.py's own unit-length check then fails at 0.98).
The source GLB is only read.

Reads the run manifest (tripo_pipeline.py init/register-source) for the primary source and the build
profile; requires preflight/import/verify completed. Writes textures/<prefix>_{BC,N_OpenGL,N,ORM}.png,
reports/atlas-report.json and logs/atlas.log. The CLI manifest is not modified (its atlas stage stays
pending, as the CLI's build stage for Arthur/Merlin).
"""

import argparse
import hashlib
import io
import json
import struct
import sys
from pathlib import Path

import numpy as np
from PIL import Image

MARKER = "TRIPO_PIPELINE_STAGE_OK atlas"
HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
BUILDER = "art/pipeline-candidates/ASSET-HARPY-001/scripts/atlas_harpy.py"


def sha256_bytes(data):
    return hashlib.sha256(data).hexdigest()


def sha256_file(path):
    return sha256_bytes(Path(path).read_bytes())


def glb_data(path):
    data = Path(path).read_bytes()
    if data[:4] != b"glTF" or struct.unpack_from("<I", data, 8)[0] != len(data):
        raise RuntimeError("not a complete binary glTF: %s" % path)
    json_len = struct.unpack_from("<I", data, 12)[0]
    model = json.loads(data[20:20 + json_len])
    return data, model, 20 + json_len + 8


def image_for(data, model, binary_offset, texture_index):
    image = model["images"][model["textures"][texture_index]["source"]]
    view = model["bufferViews"][image["bufferView"]]
    start = binary_offset + view.get("byteOffset", 0)
    return Image.open(io.BytesIO(data[start:start + view["byteLength"]])).convert("RGB")


def part_index(name):
    return int(name.split("_")[-1])


def pack_cells(parts, size, gutter):
    free = [(0, 0, size)]
    cells = {}
    for name, images in sorted(parts.items(), key=lambda item: (-item[1][0].width, part_index(item[0]))):
        width = images[0].width
        eligible = next((i for i, cell in enumerate(free) if cell[2] >= width), None)
        if eligible is None:
            raise RuntimeError("cannot fit %s at %dpx" % (name, width))
        x, y, cell_size = free.pop(eligible)
        while cell_size > width:
            half = cell_size // 2
            free[:0] = [(x + half, y, half), (x, y + half, half), (x + half, y + half, half)]
            cell_size = half
        cells[name] = {"x": x, "y_top": y, "cell": cell_size, "inset": gutter}
    return cells


def paste_with_bleed(canvas, source, cell):
    x, y, width, gutter = cell["x"], cell["y_top"], cell["cell"], cell["inset"]
    inner = width - 2 * gutter
    tile = source.resize((inner, inner), Image.Resampling.LANCZOS)
    canvas.paste(tile, (x + gutter, y + gutter))
    canvas.paste(tile.crop((0, 0, 1, inner)).resize((gutter, inner)), (x, y + gutter))
    canvas.paste(tile.crop((inner - 1, 0, inner, inner)).resize((gutter, inner)), (x + width - gutter, y + gutter))
    canvas.paste(tile.crop((0, 0, inner, 1)).resize((width, gutter)), (x, y))
    canvas.paste(tile.crop((0, inner - 1, inner, inner)).resize((width, gutter)), (x, y + width - gutter))


def cell_mask(cells, size):
    mask = np.zeros((size, size), dtype=bool)
    for cell in cells.values():
        mask[cell["y_top"]:cell["y_top"] + cell["cell"], cell["x"]:cell["x"] + cell["cell"]] = True
    return mask


def run(source, profile, out_dir, report_out):
    cfg = profile["atlas"]
    size, gutter, prefix = cfg["size"], cfg["gutter_px"], cfg["texture_prefix"]
    exclude = cfg.get("exclude_parts") or {}
    before = sha256_file(source)
    data, model, binary_offset = glb_data(source)
    parts, source_textures, factors, excluded = {}, {}, set(), {}
    for node in model["nodes"]:
        if "mesh" not in node:
            continue
        primitive = model["meshes"][node["mesh"]]["primitives"][0]
        material = model["materials"][primitive["material"]]
        pbr = material["pbrMetallicRoughness"]
        base = image_for(data, model, binary_offset, pbr["baseColorTexture"]["index"])
        rm = image_for(data, model, binary_offset, pbr["metallicRoughnessTexture"]["index"])
        normal = image_for(data, model, binary_offset, material["normalTexture"]["index"])
        info = {"base_px": base.width, "rm_px": rm.width, "normal_px": normal.width}
        if node["name"] in exclude:
            excluded[node["name"]] = dict(info, reason=exclude[node["name"]])
            continue
        if base.width != base.height:
            raise RuntimeError("non-square base texture on %s" % node["name"])
        nvec = np.asarray(normal, dtype=np.float32) / 127.5 - 1.0
        nlen = np.linalg.norm(nvec, axis=2)
        info["source_normal_unit_fraction"] = round(float(np.mean((nlen > 0.8) & (nlen < 1.2))), 4)
        factors.add(tuple(pbr.get("baseColorFactor", (1.0, 1.0, 1.0, 1.0))))
        parts[node["name"]] = (base, rm, normal)
        source_textures[node["name"]] = info
    expected = profile["expected_part_count"] - len(exclude)
    if len(parts) != expected or sorted(excluded) != sorted(exclude):
        raise RuntimeError("expected %d atlas parts (+ excluded %s), found %d (+ %s)"
                           % (expected, sorted(exclude), len(parts), sorted(excluded)))
    expected_factor = (cfg["base_color_factor_expected"],) * 3 + (1.0,)
    if factors != {expected_factor}:
        raise RuntimeError("baseColorFactor differs from profile: %s" % sorted(factors))
    pixels_all = sum(v["base_px"] ** 2 for v in source_textures.values()) + sum(v["base_px"] ** 2 for v in excluded.values())
    pixels_atlas = sum(v["base_px"] ** 2 for v in source_textures.values())

    cells = pack_cells(parts, size, gutter)
    bg = cfg["background"]
    atlases = {key: Image.new("RGB", (size, size), tuple(bg[key])) for key in ("BC", "N_OpenGL", "ORM")}
    factor = cfg["base_color_factor_expected"]
    for name, (base, rm, normal) in parts.items():
        color = Image.fromarray(np.round(np.asarray(base, dtype=np.float32) * factor).astype(np.uint8))
        rough_metal = np.asarray(rm)
        orm = np.empty_like(rough_metal)
        orm[:, :, 0] = cfg["orm_occlusion_fill"]  # Tripo gives no occlusion map for these parts
        orm[:, :, 1:] = rough_metal[:, :, 1:]
        for key, image in (("BC", color), ("N_OpenGL", normal), ("ORM", Image.fromarray(orm))):
            paste_with_bleed(atlases[key], image, cells[name])
    # Renormalise the tangent-space normals after the resize (deviation from atlas.py): Tripo's own normal maps
    # are only 97.6-99.9 % unit length per part (source_normal_unit_fraction) and LANCZOS upscaling of the
    # 512/256/128 normal maps into the BC-sized cells overshoots; near-zero texels become flat (0, 0, 1).
    raw = np.asarray(atlases["N_OpenGL"]).astype(np.float64) / 127.5 - 1.0
    length_raw = np.linalg.norm(raw, axis=2)
    flat = length_raw < 0.3
    unit = raw / np.maximum(length_raw, 1e-9)[:, :, None]
    unit[flat] = (0.0, 0.0, 1.0)
    renorm = np.clip(np.round((unit + 1.0) * 127.5), 0, 255).astype(np.uint8)
    renormalised = int((np.abs(renorm.astype(np.int16) - np.asarray(atlases["N_OpenGL"]).astype(np.int16)).max(axis=2) > 0).sum())
    atlases["N_OpenGL"] = Image.fromarray(renorm)
    directx = np.array(atlases["N_OpenGL"])
    directx[:, :, 1] = 255 - directx[:, :, 1]
    atlases["N"] = Image.fromarray(directx)

    out_dir.mkdir(parents=True, exist_ok=True)
    files = {}
    for key in ("BC", "N_OpenGL", "N", "ORM"):
        path = out_dir / ("%s_%s.png" % (prefix, key))
        atlases[key].save(path, optimize=True)
        files[key] = {"file": path.name, "sha256": sha256_file(path), "bytes": path.stat().st_size,
                      "pixels": [size, size], "mode": "RGB"}

    mask = cell_mask(cells, size)
    n_gl, n_dx = np.asarray(atlases["N_OpenGL"]).astype(np.int16), np.asarray(atlases["N"]).astype(np.int16)
    orm_px = np.asarray(atlases["ORM"])
    vec = n_dx[mask].astype(np.float32) / 127.5 - 1.0
    vec[:, 1] = -vec[:, 1]
    length = np.linalg.norm(vec, axis=1)
    cell_list = sorted(cells.values(), key=lambda c: (c["y_top"], c["x"]))
    overlaps = 0
    for i, a in enumerate(cell_list):
        for b in cell_list[i + 1:]:
            if (a["x"] < b["x"] + b["cell"] and b["x"] < a["x"] + a["cell"] and
                    a["y_top"] < b["y_top"] + b["cell"] and b["y_top"] < a["y_top"] + a["cell"]):
                overlaps += 1
    checks = {
        "part_count": {"passed": len(parts) == expected, "measured": len(parts),
                       "note": "figure parts; excluded: %s" % sorted(excluded)},
        "native_size_no_downscale": {"passed": all(cells[n]["cell"] == source_textures[n]["base_px"] for n in cells),
                                     "measured": {n: [source_textures[n]["base_px"], cells[n]["cell"]] for n in sorted(cells)},
                                     "note": "[source BC px, atlas cell px] per part"},
        "cells_do_not_overlap": {"passed": overlaps == 0, "measured": overlaps},
        "cells_inside_atlas": {"passed": all(c["x"] + c["cell"] <= size and c["y_top"] + c["cell"] <= size
                                             for c in cells.values()), "measured": size},
        "gutter_px_between_parts": {"passed": gutter >= 2, "measured": 2 * gutter,
                                    "note": "each cell keeps an edge-bleed inset on all sides: >= 2*inset px between islands of different parts"},
        "normal_directx_is_opengl_with_inverted_green": {
            "passed": bool(np.array_equal(n_dx[:, :, 1], 255 - n_gl[:, :, 1]) and
                           np.array_equal(n_dx[:, :, 0], n_gl[:, :, 0]) and np.array_equal(n_dx[:, :, 2], n_gl[:, :, 2])),
            "measured": "G_dx == 255 - G_gl; R, B equal"},
        "normal_vectors_unit_length_in_cells": {
            "passed": bool(np.mean((length > 0.8) & (length < 1.2)) > 0.99),
            "measured": round(float(np.mean((length > 0.8) & (length < 1.2))), 4),
            "note": "fraction of texels inside part cells with |n| in (0.8, 1.2)"},
        "orm_occlusion_channel_filled": {"passed": bool(np.all(orm_px[:, :, 0] == cfg["orm_occlusion_fill"])),
                                         "measured": int(orm_px[:, :, 0].min())},
        "orm_roughness_range_in_cells": {"passed": True, "measured": [int(orm_px[:, :, 1][mask].min()),
                                                                     int(orm_px[:, :, 1][mask].max())],
                                         "note": "informational"},
        "orm_metallic_range_in_cells": {"passed": True, "measured": [int(orm_px[:, :, 2][mask].min()),
                                                                    int(orm_px[:, :, 2][mask].max())],
                                        "note": "informational"},
        "cell_coverage_of_atlas": {"passed": True, "measured": round(float(mask.mean()), 4), "note": "informational"},
        "normal_renormalised_texels": {"passed": True, "measured": {"changed": renormalised, "flat_replaced": int(flat.sum())},
                                       "note": "informational: texels changed by the unit-length renormalisation (deviation from atlas.py)"},
        "cli_atlas_would_not_fit_2k": {"passed": True, "measured": {"all_parts_px": pixels_all, "figure_parts_px": pixels_atlas,
                                                                  "atlas_px": size * size},
                                       "note": "why the CLI atlas stage (all parts, native size) is not used for Harpy"},
    }
    after = sha256_file(source)
    checks["source_unchanged"] = {"passed": after == before, "measured": after}
    report = {
        "stage": "atlas",
        "builder": BUILDER,
        "builder_sha256": sha256_file(Path(__file__)),
        "profile": profile["profile_id"],
        "source": {"file": source.name, "sha256": before},
        "size": size,
        "gutter_px": gutter,
        "algorithm": "tools/tripo-pipeline/candidate/atlas.py port (quadtree cells, LANCZOS resize, edge bleed); "
                     "profile atlas.exclude_parts left out of the atlas; normal texels renormalised after the resize",
        "cells": cells,
        "excluded_parts": excluded,
        "source_textures": source_textures,
        "files": files,
        "conventions": {
            "BC": "sRGB colour; Tripo baseColorFactor %.3f multiplied in" % factor,
            "N_OpenGL": "linear; OpenGL (+Y) — Blender preview only",
            "N": "linear; DirectX (-Y) — for UE (flip_green_channel = false)",
            "ORM": "linear; R = occlusion (filled %d, Tripo has none), G = roughness, B = metallic" % cfg["orm_occlusion_fill"],
        },
        "reference_comparison": {},
        "checks": checks,
        "passed": all(c["passed"] for c in checks.values()),
    }
    report_out.parent.mkdir(parents=True, exist_ok=True)
    report_out.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    if not report["passed"]:
        raise RuntimeError("atlas checks failed: %s" % sorted(k for k, c in checks.items() if not c["passed"]))
    return report


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--run-dir", required=True)
    args = ap.parse_args()
    run_dir = Path(args.run_dir)
    run_dir = run_dir if run_dir.is_absolute() else (REPO / run_dir)
    manifest = json.loads((run_dir / "manifest.json").read_text(encoding="utf-8"))
    for stage in ("preflight", "import", "verify"):
        if (manifest["stages"].get(stage) or {}).get("status") != "completed":
            sys.exit("stage %s is not completed in the manifest" % stage)
    cfg = manifest["config"]
    src = manifest["sources"][cfg["primary_source"]]
    primary = next(f for f in src["files"] if f["role"] == cfg["primary_role"])
    source = REPO / primary["path"]
    if sha256_file(source) != primary["sha256"]:
        sys.exit("primary source changed since registration")
    profile = json.loads((REPO / cfg["build_profile"]).read_text(encoding="utf-8"))
    (run_dir / "logs").mkdir(exist_ok=True)
    report = run(source, profile, run_dir / "textures", run_dir / "reports" / "atlas-report.json")
    line = "%s %d parts %d excluded=%s" % (MARKER, len(report["cells"]), report["size"], sorted(report["excluded_parts"]))
    (run_dir / "logs" / "atlas.log").write_text(line + "\n" + json.dumps(
        {k: v["sha256"] for k, v in report["files"].items()}, sort_keys=True) + "\n", encoding="utf-8")
    print(line)


if __name__ == "__main__":
    main()
