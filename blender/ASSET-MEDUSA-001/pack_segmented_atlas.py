"""Pack the Tripo part textures into one 2K game atlas without changing geometry.

Run with the workspace Python. GLB UVs keep their original orientation; the
companion Blender build remaps each part's UVs into the recorded cell.
"""

from __future__ import annotations

import io
import json
import struct
from pathlib import Path

import numpy as np
from PIL import Image


ROOT = Path(__file__).resolve().parent
SOURCE = ROOT / "tripo-source/b6253e58/medusa-segmented-retopo.glb"
DEST = ROOT / "textures"
SIZE = 2048
GUTTER = 4


def glb_data(path: Path):
    data = path.read_bytes()
    assert data[:4] == b"glTF"
    assert struct.unpack_from("<I", data, 8)[0] == len(data)
    json_len = struct.unpack_from("<I", data, 12)[0]
    model = json.loads(data[20 : 20 + json_len])
    binary_offset = 20 + json_len + 8
    return data, model, binary_offset


def image_for(data, model, binary_offset, texture_index):
    image = model["images"][model["textures"][texture_index]["source"]]
    view = model["bufferViews"][image["bufferView"]]
    start = binary_offset + view.get("byteOffset", 0)
    return Image.open(io.BytesIO(data[start : start + view["byteLength"]])).convert("RGB")


def pack_cells(parts):
    free = [(0, 0, SIZE)]
    cells = {}
    for name, images in sorted(parts.items(), key=lambda item: (-item[1][0].width, int(item[0].split("_")[-1]))):
        width = images[0].width
        eligible = next((i for i, cell in enumerate(free) if cell[2] >= width), None)
        if eligible is None:
            raise RuntimeError(f"Cannot fit {name} at {width}px")
        x, y, cell_size = free.pop(eligible)
        while cell_size > width:
            half = cell_size // 2
            free[:0] = [(x + half, y, half), (x, y + half, half), (x + half, y + half, half)]
            cell_size = half
        cells[name] = {"x": x, "y_top": y, "cell": cell_size, "inset": GUTTER}
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


def main():
    DEST.mkdir(parents=True, exist_ok=True)
    data, model, binary_offset = glb_data(SOURCE)
    parts = {}
    for node in model["nodes"]:
        if "mesh" not in node:
            continue
        primitive = model["meshes"][node["mesh"]]["primitives"][0]
        material = model["materials"][primitive["material"]]
        pbr = material["pbrMetallicRoughness"]
        base = image_for(data, model, binary_offset, pbr["baseColorTexture"]["index"])
        rm = image_for(data, model, binary_offset, pbr["metallicRoughnessTexture"]["index"])
        normal = image_for(data, model, binary_offset, material["normalTexture"]["index"])
        assert base.width == base.height
        assert tuple(pbr["baseColorFactor"]) == (0.800000011920929,) * 3 + (1.0,)
        parts[node["name"]] = (base, rm, normal)
    assert len(parts) == 15

    cells = pack_cells(parts)
    atlases = {
        "BC": Image.new("RGB", (SIZE, SIZE), (128, 128, 128)),
        "N_OpenGL": Image.new("RGB", (SIZE, SIZE), (128, 128, 255)),
        "ORM": Image.new("RGB", (SIZE, SIZE), (255, 220, 0)),
    }
    for name, (base, rm, normal) in parts.items():
        # Tripo stores the same 0.8 base-color factor on all 15 materials.
        color = Image.fromarray(np.round(np.asarray(base, dtype=np.float32) * 0.8).astype(np.uint8))
        rough_metal = np.asarray(rm)
        orm = np.empty_like(rough_metal)
        orm[:, :, 0] = 255  # Tripo does not provide an occlusion map for these parts.
        orm[:, :, 1:] = rough_metal[:, :, 1:]
        for key, image in (("BC", color), ("N_OpenGL", normal), ("ORM", Image.fromarray(orm))):
            paste_with_bleed(atlases[key], image, cells[name])

    directx = np.array(atlases["N_OpenGL"])
    directx[:, :, 1] = 255 - directx[:, :, 1]
    atlases["N"] = Image.fromarray(directx)
    files = {}
    for suffix, image in atlases.items():
        path = DEST / f"T_Medusa_Atlas_{suffix}.png"
        image.save(path, optimize=True)
        files[suffix] = path.relative_to(ROOT).as_posix()
    report = {"source": SOURCE.relative_to(ROOT).as_posix(), "size": SIZE, "cells": cells, "files": files}
    (ROOT / "atlas-report.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"parts": len(parts), "files": files}, indent=2))


if __name__ == "__main__":
    main()
