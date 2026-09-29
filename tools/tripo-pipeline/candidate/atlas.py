"""Stage `atlas`: pack the per-part Tripo textures of a segmented GLB into one BC / Normal / ORM atlas.

Run only through tripo_pipeline.py with the workspace Python (needs Pillow + numpy):
    python atlas.py <params.json>
params.json: {"source": abs GLB, "profile": abs build-profile JSON, "out_dir": abs dir,
              "report_out": abs path, "repo_root": abs path}

Algorithm is the one of blender/ASSET-MEDUSA-001/pack_segmented_atlas.py (that file
writes into its own asset folder, so it is ported here instead of called):
parts sorted by (-texture width, part index) are placed into a quadtree of square
cells; each part texture is resized into its cell minus a gutter and the gutter is
filled by edge bleed. BaseColor is multiplied by the (uniform) glTF baseColorFactor,
ORM = (occlusion fill, Tripo roughness G, Tripo metallic B), the DirectX normal is
the OpenGL normal with the green channel inverted. The source GLB is only read.

Profile options (tool 0.5.0; absent = the 0.4.0 behaviour, byte-identical outputs):
  atlas.exclude_parts {part: reason}  parts left out of the atlas (e.g. a Tripo base replaced by a parametric
                                      base in the build: Harpy's 9 parts do not fit 2K at native size otherwise)
  atlas.normal_renormalise true        normal texels renormalised to unit length after the resize (Tripo's part
                                      normal maps are 97.6-99.9 % unit length; LANCZOS upscaling overshoots);
                                      near-zero texels become flat (0, 0, 1)
  team_color.mask {method, texture, ...}  optional TeamColor mask (8-bit grey, linear) from the BC atlas, written as
                                      atlas output "TeamMask" (proposal, AD-CNF-58):
      hsv-hard-gaussian  hue >= hue_min_deg or <= hue_max_deg, s >= s_min, v_min <= v <= v_max inside the part
                         cells, Gaussian blur blur_sigma_px, limited to the cells (King Arthur red cloth)
      hsv-smooth-box     smoothstep ramps on hue_deg [lo, hi] (hue_ramp_deg), s_min and v_min (ramp) inside the
                         inner rect of the listed cells, 3x3 box blur (Merlin bronze trim)
"""

import hashlib
import io
import json
import struct
import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageFilter

MARKER = "TRIPO_PIPELINE_STAGE_OK atlas"


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


def hsv_float(rgb):
    """HSV (hue in degrees, s, v) of an H x W x 3 float array in [0, 1]."""
    mx, mn = rgb.max(axis=2), rgb.min(axis=2)
    d = np.maximum(mx - mn, 1e-6)
    r, g, b = rgb[..., 0], rgb[..., 1], rgb[..., 2]
    hue = np.where(mx == r, ((g - b) / d) % 6, np.where(mx == g, (b - r) / d + 2, (r - g) / d + 4)) * 60.0
    sat = np.where(mx > 0, (mx - mn) / np.maximum(mx, 1e-6), 0.0)
    return hue, sat, mx


def hsv_masked(a):
    """HSV like hsv_float but hue 0 where max == min (grey); each branch assigned once (r before g before b)."""
    r, g, b = a[..., 0], a[..., 1], a[..., 2]
    mx, mn = a.max(-1), a.min(-1)
    d = mx - mn
    h = np.zeros_like(mx)
    m = d > 1e-6
    rr = (mx == r) & m
    gg = (mx == g) & m & ~rr
    bb = m & ~rr & ~gg
    h[rr] = ((g - b)[rr] / d[rr]) % 6
    h[gg] = ((b - r)[gg] / d[gg]) + 2
    h[bb] = ((r - g)[bb] / d[bb]) + 4
    return h * 60.0, np.where(mx > 0, d / np.maximum(mx, 1e-6), 0.0), mx


def smooth(x):
    x = np.clip(x, 0.0, 1.0)
    return x * x * (3 - 2 * x)


def team_mask(bc_image, cells, size, cfg):
    """Optional TeamColor mask (see the module docstring). Returns (PIL "L" image, report dict)."""
    method = cfg["method"]
    bc = np.asarray(bc_image.convert("RGB")).astype(np.float32) / 255.0
    if method == "hsv-hard-gaussian":
        hue, sat, val = hsv_float(bc)
        inside = np.zeros((size, size), dtype=bool)
        for c in cells.values():
            inside[c["y_top"]:c["y_top"] + c["cell"], c["x"]:c["x"] + c["cell"]] = True
        hard = (((hue >= cfg["hue_min_deg"]) | (hue <= cfg["hue_max_deg"])) & (sat >= cfg["s_min"]) &
                (val >= cfg["v_min"]) & (val <= cfg["v_max"]) & inside)
        soft = Image.fromarray((hard * 255).astype(np.uint8), "L").filter(ImageFilter.GaussianBlur(cfg["blur_sigma_px"]))
        image = Image.fromarray(np.where(inside, np.asarray(soft), 0).astype(np.uint8), "L")
        rule = {k: cfg[k] for k in ("hue_min_deg", "hue_max_deg", "s_min", "v_min", "v_max", "blur_sigma_px")}
        considered = sorted(cells)
    elif method == "hsv-smooth-box":
        h, s, v = hsv_masked(bc)
        lo, hi = cfg["hue_deg"]
        ramp_h = cfg["hue_ramp_deg"]
        hue_w = smooth((h - lo) / ramp_h) * smooth((hi - h) / ramp_h)
        raw = hue_w * smooth((s - cfg["s_min"]) / cfg["ramp"] + 0.5) * smooth((v - cfg["v_min"]) / cfg["ramp"] + 0.5)
        inside = np.zeros(raw.shape, dtype=bool)
        for part in cfg["cells"]:
            c = cells[part]
            inside[c["y_top"] + c["inset"]:c["y_top"] + c["cell"] - c["inset"],
                   c["x"] + c["inset"]:c["x"] + c["cell"] - c["inset"]] = True
        mask = np.where(inside, raw, 0.0)
        image = Image.fromarray(np.round(mask * 255).astype(np.uint8), "L").filter(ImageFilter.BoxBlur(1))
        rule = {k: cfg[k] for k in ("hue_deg", "hue_ramp_deg", "s_min", "v_min", "ramp", "cells")}
        considered = sorted(cfg["cells"])
    else:
        raise RuntimeError("team_color.mask.method %r is not one of hsv-hard-gaussian, hsv-smooth-box" % method)
    arr = np.asarray(image)
    coverage = {}
    for name, c in sorted(cells.items(), key=lambda kv: int(kv[0].split("_")[-1])):
        inner = arr[c["y_top"] + c["inset"]:c["y_top"] + c["cell"] - c["inset"],
                    c["x"] + c["inset"]:c["x"] + c["cell"] - c["inset"]]
        coverage[name] = round(float((inner >= 128).mean()), 5)
    return image, {"method": method, "rule": rule, "cells_considered": considered,
                   "coverage_by_cell_inner_rect_ge_0_5": coverage,
                   "cells_with_coverage_over_1pct": sorted(k for k, v in coverage.items() if v > 0.01),
                   "colour_space": "linear (UE: sRGB off, TC_Grayscale)", "status": "предложено (AD-CNF-58 open)"}


def main():
    params = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
    profile = json.loads(Path(params["profile"]).read_text(encoding="utf-8"))
    cfg = profile["atlas"]
    size, gutter, prefix = cfg["size"], cfg["gutter_px"], cfg["texture_prefix"]
    exclude = cfg.get("exclude_parts") or {}
    source = Path(params["source"])
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
        factors.add(tuple(pbr.get("baseColorFactor", (1.0, 1.0, 1.0, 1.0))))
        parts[node["name"]] = (base, rm, normal)
        source_textures[node["name"]] = info
    expected_parts = profile["expected_part_count"] - len(exclude)
    if len(parts) != expected_parts or sorted(excluded) != sorted(exclude):
        raise RuntimeError("expected %d atlas parts (+ excluded %s), found %d (+ %s)"
                           % (expected_parts, sorted(exclude), len(parts), sorted(excluded)))
    expected_factor = (cfg["base_color_factor_expected"],) * 3 + (1.0,)
    if factors != {expected_factor}:
        raise RuntimeError("baseColorFactor differs from profile: %s" % sorted(factors))

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
    renormalised = None
    if cfg.get("normal_renormalise"):
        raw = np.asarray(atlases["N_OpenGL"]).astype(np.float64) / 127.5 - 1.0
        length_raw = np.linalg.norm(raw, axis=2)
        flat = length_raw < 0.3
        unit = raw / np.maximum(length_raw, 1e-9)[:, :, None]
        unit[flat] = (0.0, 0.0, 1.0)
        renorm = np.clip(np.round((unit + 1.0) * 127.5), 0, 255).astype(np.uint8)
        changed = np.abs(renorm.astype(np.int16) - np.asarray(atlases["N_OpenGL"]).astype(np.int16)).max(axis=2) > 0
        renormalised = {"changed": int(changed.sum()), "flat_replaced": int(flat.sum())}
        atlases["N_OpenGL"] = Image.fromarray(renorm)
    directx = np.array(atlases["N_OpenGL"])
    directx[:, :, 1] = 255 - directx[:, :, 1]
    atlases["N"] = Image.fromarray(directx)

    out_dir = Path(params["out_dir"])
    out_dir.mkdir(parents=True, exist_ok=True)
    repo = Path(params["repo_root"])
    files, reference = {}, {}
    for key in ("BC", "N_OpenGL", "N", "ORM"):
        path = out_dir / ("%s_%s.png" % (prefix, key))
        atlases[key].save(path, optimize=True)
        files[key] = {"file": path.name, "sha256": sha256_file(path), "bytes": path.stat().st_size,
                      "pixels": [size, size], "mode": "RGB"}
        ref_rel = (cfg.get("reference_textures") or {}).get(key)
        if ref_rel:
            ref = repo / ref_rel
            entry = {"path": ref_rel, "present": ref.is_file()}
            if ref.is_file():
                entry["sha256"] = sha256_file(ref)
                entry["bytes_identical"] = entry["sha256"] == files[key]["sha256"]
                ref_px = np.asarray(Image.open(ref).convert("RGB"))
                ours = np.asarray(atlases[key])
                entry["pixels_identical"] = bool(ref_px.shape == ours.shape and np.array_equal(ref_px, ours))
                if not entry["pixels_identical"] and ref_px.shape == ours.shape:
                    diff = np.abs(ref_px.astype(np.int16) - ours.astype(np.int16))
                    entry["max_abs_channel_diff"] = int(diff.max())
                    entry["differing_pixels"] = int((diff.max(axis=2) > 0).sum())
            reference[key] = entry
    mask_cfg = (profile.get("team_color") or {}).get("mask")
    team = None
    if mask_cfg:
        image, team = team_mask(atlases["BC"], cells, size, mask_cfg)
        path = out_dir / mask_cfg["texture"]
        image.save(path, optimize=True)
        files["TeamMask"] = {"file": path.name, "sha256": sha256_file(path), "bytes": path.stat().st_size,
                             "pixels": [size, size], "mode": "L"}

    mask = cell_mask(cells, size)
    n_gl, n_dx = np.asarray(atlases["N_OpenGL"]).astype(np.int16), np.asarray(atlases["N"]).astype(np.int16)
    orm_px = np.asarray(atlases["ORM"])
    vec = n_dx[mask].astype(np.float32) / 127.5 - 1.0
    vec[:, 1] = -vec[:, 1]  # back to OpenGL for the length test (length is convention independent)
    length = np.linalg.norm(vec, axis=1)
    cell_list = sorted(cells.values(), key=lambda c: (c["y_top"], c["x"]))
    overlaps = 0
    for i, a in enumerate(cell_list):
        for b in cell_list[i + 1:]:
            if (a["x"] < b["x"] + b["cell"] and b["x"] < a["x"] + a["cell"] and
                    a["y_top"] < b["y_top"] + b["cell"] and b["y_top"] < a["y_top"] + a["cell"]):
                overlaps += 1
    checks = {
        "part_count": {"passed": len(parts) == expected_parts, "measured": len(parts),
                       "note": "atlas parts; excluded (atlas.exclude_parts): %s" % sorted(excluded)},
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
        "cell_inner_px_vs_source_px": {
            "passed": True,
            "measured": {n: [source_textures[n]["base_px"], cells[n]["cell"] - 2 * cells[n]["inset"]] for n in sorted(cells)},
            "note": "informational: [source BC px, inner cell px]; the tile is LANCZOS-resized into the inner rect "
                    "(cell minus 2 x gutter)"},
    }
    if renormalised is not None:
        checks["normal_renormalised_texels"] = {"passed": True, "measured": renormalised,
                                                "note": "informational: texels changed by atlas.normal_renormalise"}
    after = sha256_file(source)
    checks["source_unchanged"] = {"passed": after == before, "measured": after}
    report = {
        "stage": "atlas",
        "profile": profile["profile_id"],
        "source": {"file": source.name, "sha256": before},
        "size": size,
        "gutter_px": gutter,
        "algorithm": "pack_segmented_atlas.py port (quadtree cells, LANCZOS resize, edge bleed)"
                     + ("; atlas.exclude_parts left out" if exclude else "")
                     + ("; normal texels renormalised after the resize" if renormalised is not None else ""),
        "cells": cells,
        "excluded_parts": excluded,
        "source_textures": source_textures,
        "team_mask": team,
        "files": files,
        "conventions": {
            "BC": "sRGB colour; Tripo baseColorFactor %.3f multiplied in" % factor,
            "N_OpenGL": "linear; OpenGL (+Y) — Blender preview only",
            "N": "linear; DirectX (-Y) — for UE (flip_green_channel = false)",
            "ORM": "linear; R = occlusion (filled %d, Tripo has none), G = roughness, B = metallic" % cfg["orm_occlusion_fill"],
            "TeamMask": "linear 8-bit grey (optional, team_color.mask); UE: sRGB off, TC_Grayscale",
        },
        "reference_comparison": reference,
        "checks": checks,
        "passed": all(c["passed"] for c in checks.values()),
    }
    Path(params["report_out"]).write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    if not report["passed"]:
        raise RuntimeError("atlas checks failed: %s" % sorted(k for k, c in checks.items() if not c["passed"]))
    print(MARKER, len(parts), "parts", size)


if __name__ == "__main__":
    main()
