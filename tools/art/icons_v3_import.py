"""HUD icon motion v3 (docs/unreal/contracts/hud/ICON-MOTION-PLAN.md, phase D): import the v3 icon textures the
motion contract and the gallery use into /Game/S08/UI/IconsV3 (cooked with /Game/S08).

Runs inside the editor:

  UnrealEditor-Cmd unreal/Unmatched/Unmatched.uproject -run=pythonscript -script=<this file> -unattended -nullrhi

Sources: art/imagegen/hud-icons-v3/{sizes,layers}/<name>-<px>.png rendered from vector at each size (no downscale).
Names: T_IV3_<name with '-' -> '_'>_<px> (S08IconMotion::TextureObjectPath). IC-33: the sizes of a texture are the
`ue_sizes` of its contract record (default 18/24/32/36/48/64 - 18 and 36 are the 24 su icon at DPI 0.75 and at 150 %,
02 §3.2 / §5.3); a variant takes its base icon's sizes, a layer its icon's. Names: `order` + `accepted_vr44` + variants +
layers. Cursors (cursor-*, IC-58…IC-61) are not imported here - HB-12 imports them under /Game/S08/UI/Cursors.
Partial runs: ICONS_V3_ONLY=<id>,<id> (those icons and their layers) and ICONS_V3_SIZES=<px>,<px> (those sizes); every
other texture keeps its report entry, whose source must still match.
Settings as the existing exact-size HUD icons (tools/art/art004_hud_icon_import.py): UserInterface2D (BGRA, no
compression), no mipmaps, TEXTUREGROUP_UI, sRGB, bilinear, never stream. Idempotent (replace_existing).
Report: art/imagegen/hud-icons-v3/ue-import-report.json (source sha256 per texture).

IC-35 (VS-6 F1, ВР-IC15, по делегированию): ICONS_V3_WORLD=1 imports only the world fallback of the target token -
masters/action-attack-token.png as is (1024, POT) -> T_IV3_action_attack_token_World with a mip chain,
TEXTUREGROUP_World, sRGB, TF_Trilinear, never streamed, the compression of the mvp-v1 world sprite
T_UI_Action_AttackConcept (read from that asset); its report entry carries its own "settings" and replaces the old one,
every other entry stays.
"""

from __future__ import annotations

import hashlib
import json
import os
import struct
from pathlib import Path

import unreal as u

ROOT = Path(__file__).resolve().parents[2]
ICONS = ROOT / "art/imagegen/hud-icons-v3"
CONTRACT = ROOT / "docs/unreal/contracts/hud/icon-motion.json"
DEST = "/Game/S08/UI/IconsV3"
REPORT = ICONS / "ue-import-report.json"
SIZES_DEFAULT = (18, 24, 32, 36, 48, 64)  # a record without `ue_sizes` (motion_contract.py UE_SIZES_DEFAULT)


def is_cursor(name: str) -> bool:
    return name.startswith("cursor-")


def texture_plan() -> dict[str, tuple[int, ...]]:
    """Texture name -> sizes (IC-33): `ue_sizes` of the record; variants take the base, layers their icon."""
    c = json.loads(CONTRACT.read_text(encoding="utf-8"))
    icons = c["icons"]
    plan: dict[str, set[int]] = {}

    def sizes(icon: str) -> tuple[int, ...]:
        return tuple(icons.get(icon, {}).get("ue_sizes", SIZES_DEFAULT))

    def add(name: str, px: tuple[int, ...]) -> None:
        if not is_cursor(name):
            plan.setdefault(name, set()).update(px)

    for icon in list(c["order"]) + list(c.get("accepted_vr44", [])):
        add(icon, sizes(icon))
    for variant, base in c.get("variants", {}).items():
        add(variant, sizes(base))
    for icon, d in icons.items():
        for layer in d["layers"]:
            src = layer["src"]
            names = [f"{src[:-1]}_f{i:02d}" for i in range(layer["frames"])] if src.endswith("#") else [src]
            for n in names:
                add(n, sizes(icon))
    return {n: tuple(sorted(px)) for n, px in sorted(plan.items())}


def texture_names() -> list[str]:
    return list(texture_plan())


def png_size(data: bytes) -> tuple[int, int, int]:
    if data[:8] != b"\x89PNG\r\n\x1a\n" or data[12:16] != b"IHDR":
        raise RuntimeError("not a PNG with an IHDR chunk")
    width, height = struct.unpack(">II", data[16:24])
    return width, height, data[25]


WORLD_SRC = ICONS / "masters/action-attack-token.png"
WORLD_ASSET = "T_IV3_action_attack_token_World"
WORLD_LEGACY = "/Game/ArtTests/ARTMarkers/Textures/T_UI_Action_AttackConcept"


def import_world() -> None:
    """IC-35: the POT 1024 world token with mips (S08FighterActor TargetIcon; -S08IconLegacy keeps the concept)."""
    tools = u.AssetToolsHelpers.get_asset_tools()
    data = WORLD_SRC.read_bytes()
    width, height, color_type = png_size(data)
    if (width, height) != (1024, 1024) or color_type != 6:
        raise RuntimeError(f"{WORLD_SRC.name}: expected 1024 RGBA, got {width}x{height} type={color_type}")
    legacy = u.load_asset(WORLD_LEGACY)
    compression = legacy.get_editor_property("compression_settings") if legacy else u.TextureCompressionSettings.TC_DEFAULT
    task = u.AssetImportTask()
    task.filename = str(WORLD_SRC)
    task.destination_path = DEST
    task.destination_name = WORLD_ASSET
    task.automated = True
    task.replace_existing = True
    task.save = False
    tools.import_asset_tasks([task])
    asset = u.load_asset(f"{DEST}/{WORLD_ASSET}")
    if not asset or not isinstance(asset, u.Texture2D):
        raise RuntimeError(f"{WORLD_ASSET}: not imported as Texture2D")
    asset.set_editor_property("compression_settings", compression)
    asset.set_editor_property("mip_gen_settings", u.TextureMipGenSettings.TMGS_FROM_TEXTURE_GROUP)
    asset.set_editor_property("lod_group", u.TextureGroup.TEXTUREGROUP_WORLD)
    asset.set_editor_property("srgb", True)
    asset.set_editor_property("filter", u.TextureFilter.TF_TRILINEAR)
    asset.set_editor_property("never_stream", True)
    if not u.EditorAssetLibrary.save_loaded_asset(asset, only_if_is_dirty=False):
        raise RuntimeError(f"{WORLD_ASSET}: save failed")
    actual = (asset.blueprint_get_size_x(), asset.blueprint_get_size_y())
    if actual != (width, height):
        raise RuntimeError(f"{WORLD_ASSET}: imported as {actual}")
    report = json.loads(REPORT.read_text(encoding="utf-8"))
    entries = [t for t in report["textures"] if t["asset"] != f"{DEST}/{WORLD_ASSET}"]
    entries.append({"asset": f"{DEST}/{WORLD_ASSET}", "source": WORLD_SRC.relative_to(ROOT).as_posix(),
                    "sourceSha256": hashlib.sha256(data).hexdigest(), "size": [width, height],
                    "settings": {"compression": str(compression).split(".")[-1].split(":")[0].strip("<> "),
                                 "compressionFrom": WORLD_LEGACY.rsplit("/", 1)[-1],
                                 "mipGen": "TMGS_FROM_TEXTURE_GROUP", "lodGroup": "TEXTUREGROUP_World",
                                 "srgb": True, "filter": "TF_Trilinear", "neverStream": True,
                                 "card": "IC-35 (ВР-IC15)"}})
    report["textures"] = entries
    report["count"] = len(entries)
    REPORT.write_text(json.dumps(report, ensure_ascii=False, indent=1) + "\n", encoding="utf-8", newline="\n")
    u.log(f"ICONS_V3_WORLD_PASS asset={DEST}/{WORLD_ASSET} compression={compression}")


def main() -> None:
    if os.environ.get("ICONS_V3_WORLD") == "1":
        import_world()
        return
    tools = u.AssetToolsHelpers.get_asset_tools()
    # ICONS_V3_ONLY=<id>,<id>: re-import only these icons (and their layers); every other texture keeps its report
    # entry, which must still match its source (a changed source that is not re-imported fails the run).
    only = {x.strip() for x in os.environ.get("ICONS_V3_ONLY", "").split(",") if x.strip()}
    # IC-33: ICONS_V3_SIZES=18,36 imports only the new sizes; the existing 24/32/48/64 assets stay untouched.
    only_sizes = {int(x) for x in os.environ.get("ICONS_V3_SIZES", "").split(",") if x.strip()}
    previous = {}
    if (only or only_sizes) and REPORT.exists():
        previous = {e["asset"]: e for e in json.loads(REPORT.read_text(encoding="utf-8"))["textures"]}
    entries = []
    all_sizes: set[int] = set()
    reimported = 0
    for name, sizes in texture_plan().items():
        sub = "layers" if "_" in name else "sizes"
        all_sizes.update(sizes)
        for size in sizes:
            source = ICONS / sub / f"{name}-{size}.png"
            data = source.read_bytes()
            if (only and name.split("_")[0] not in only) or (only_sizes and size not in only_sizes):
                old = previous.get(f"{DEST}/T_IV3_{name.replace('-', '_')}_{size}")
                if not old or old["sourceSha256"] != hashlib.sha256(data).hexdigest():
                    raise RuntimeError(f"{source.name}: source changed (or never imported) but not in "
                                       f"ICONS_V3_ONLY / ICONS_V3_SIZES")
                entries.append(old)
                continue
            reimported += 1
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
        "sizes": sorted(all_sizes),
        "settings": {"compression": "TC_EDITOR_ICON", "mipGen": "TMGS_NO_MIPMAPS", "lodGroup": "TEXTUREGROUP_UI",
                     "srgb": True, "filter": "TF_BILINEAR", "neverStream": True},
        "count": len(entries),
        "textures": entries,
    }, ensure_ascii=False, indent=1) + "\n", encoding="utf-8", newline="\n")
    scope = "all" if not (only or only_sizes) else ",".join(sorted(only) or ["*"]) + "@" + ",".join(
        str(s) for s in sorted(only_sizes) or ["*"])
    u.log(f"ICONS_V3_IMPORT_PASS textures={len(entries)} imported={reimported} reimported={scope} dest={DEST}")


main()
