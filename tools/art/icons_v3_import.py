"""HUD icon motion v3 (docs/unreal/contracts/hud/ICON-MOTION-PLAN.md, phase D): import the v3 icon textures the
motion contract and the gallery use into /Game/S08/UI/IconsV3 (cooked with /Game/S08).

Runs inside the editor:

  UnrealEditor-Cmd unreal/Unmatched/Unmatched.uproject -run=pythonscript -script=<this file> -unattended -nullrhi

Sources: art/imagegen/hud-icons-v3/{sizes,layers}/<name>-<px>.png rendered from vector at each size (no downscale).
Names: T_IV3_<name with '-' -> '_'>_<px> (S08IconMotion::TextureObjectPath). Sizes 24/32/48/64 px.
Settings as the existing exact-size HUD icons (tools/art/art004_hud_icon_import.py): UserInterface2D (BGRA, no
compression), no mipmaps, TEXTUREGROUP_UI, sRGB, bilinear, never stream. Idempotent (replace_existing).
Report: art/imagegen/hud-icons-v3/ue-import-report.json (source sha256 per texture).
"""

from __future__ import annotations

import hashlib
import json
import struct
from pathlib import Path

import unreal as u

ROOT = Path(__file__).resolve().parents[2]
ICONS = ROOT / "art/imagegen/hud-icons-v3"
CONTRACT = ROOT / "docs/unreal/contracts/hud/icon-motion.json"
DEST = "/Game/S08/UI/IconsV3"
REPORT = ICONS / "ue-import-report.json"
SIZES = (24, 32, 48, 64)


def texture_names() -> list[str]:
    c = json.loads(CONTRACT.read_text(encoding="utf-8"))
    names = set(c["order"]) | set(c.get("variants", {}))
    for d in c["icons"].values():
        for layer in d["layers"]:
            src = layer["src"]
            if src.endswith("#"):
                names.update(f"{src[:-1]}_f{i:02d}" for i in range(layer["frames"]))
            else:
                names.add(src)
    return sorted(names)


def png_size(data: bytes) -> tuple[int, int, int]:
    if data[:8] != b"\x89PNG\r\n\x1a\n" or data[12:16] != b"IHDR":
        raise RuntimeError("not a PNG with an IHDR chunk")
    width, height = struct.unpack(">II", data[16:24])
    return width, height, data[25]


def main() -> None:
    tools = u.AssetToolsHelpers.get_asset_tools()
    entries = []
    for name in texture_names():
        sub = "layers" if "_" in name else "sizes"
        for size in SIZES:
            source = ICONS / sub / f"{name}-{size}.png"
            data = source.read_bytes()
            width, height, color_type = png_size(data)
            if height != size or width not in (size, 2 * size) or color_type != 6:
                raise RuntimeError(f"{source.name}: expected {size}px RGBA, got {width}x{height} type={color_type}")
            asset_name = f"T_IV3_{name.replace('-', '_')}_{size}"
            task = u.AssetImportTask()
            task.filename = str(source)
            task.destination_path = DEST
            task.destination_name = asset_name
            task.automated = True
            task.replace_existing = True
            task.save = False
            tools.import_asset_tasks([task])
            asset = u.load_asset(f"{DEST}/{asset_name}")
            if not asset or not isinstance(asset, u.Texture2D):
                raise RuntimeError(f"{asset_name}: not imported as Texture2D")
            asset.set_editor_property("compression_settings", u.TextureCompressionSettings.TC_EDITOR_ICON)
            asset.set_editor_property("mip_gen_settings", u.TextureMipGenSettings.TMGS_NO_MIPMAPS)
            asset.set_editor_property("lod_group", u.TextureGroup.TEXTUREGROUP_UI)
            asset.set_editor_property("srgb", True)
            asset.set_editor_property("filter", u.TextureFilter.TF_BILINEAR)
            asset.set_editor_property("never_stream", True)
            if not u.EditorAssetLibrary.save_loaded_asset(asset, only_if_is_dirty=False):
                raise RuntimeError(f"{asset_name}: save failed")
            actual = (asset.blueprint_get_size_x(), asset.blueprint_get_size_y())
            if actual != (width, height):
                raise RuntimeError(f"{asset_name}: imported as {actual}, source {width}x{height}")
            entries.append({"asset": f"{DEST}/{asset_name}", "source": source.relative_to(ROOT).as_posix(),
                            "sourceSha256": hashlib.sha256(data).hexdigest(), "size": [width, height]})
    REPORT.write_text(json.dumps({
        "schema": "unmatched.icons-v3-import/1",
        "status": "технически импортировано (значки v3 — ПРЕДЛОЖЕНИЕ до арт-приёмки)",
        "dest": DEST,
        "sizes": list(SIZES),
        "settings": {"compression": "TC_EDITOR_ICON", "mipGen": "TMGS_NO_MIPMAPS", "lodGroup": "TEXTUREGROUP_UI",
                     "srgb": True, "filter": "TF_BILINEAR", "neverStream": True},
        "count": len(entries),
        "textures": entries,
    }, ensure_ascii=False, indent=1) + "\n", encoding="utf-8", newline="\n")
    u.log(f"ICONS_V3_IMPORT_PASS textures={len(entries)} dest={DEST}")


main()
