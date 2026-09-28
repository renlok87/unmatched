"""ART-004 stage 3 T2.2: import the pre-filtered 24/32/48 px combat icons as UI
textures (no mips, UI LOD group, uncompressed BGRA "UserInterface2D") into the
already-cooked /Game/ArtTests/ARTMarkers/Textures. Runs inside the ART worktree
editor only:

  UnrealEditor-Cmd <art worktree>/unreal/Unmatched/Unmatched.uproject
      -run=pythonscript -script=<this file> -unattended -nullrhi

(`python tools/art/art004_hud_t22.py import-icons --out ...` wraps it). The
sources come from `art004_hud_t22.py icons` (linear-light area filter of the
ART-003 concept ui-action-attack-normal.png). Idempotent: replace_existing.
Status: imported concept sizes for the 24/32/48 px check - not approved art.
"""

from __future__ import annotations

import hashlib
import json
import struct
from pathlib import Path

import unreal as u


ROOT = Path(__file__).resolve().parents[2]
SIZED = ROOT / "art/imagegen/mvp-v1/ui/actions/sized"
DEST = "/Game/ArtTests/ARTMarkers/Textures"
CONTENT = ROOT / "unreal/Unmatched/Content/ArtTests/ARTMarkers/Textures"
REPORT = ROOT / "docs/game-design/evidence/ART-004/hud-input-t22/icon-import-report.json"
SIZES = (24, 32, 48)


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def png_size(data: bytes) -> tuple[int, int, int]:
    if data[:8] != b"\x89PNG\r\n\x1a\n" or data[12:16] != b"IHDR":
        raise RuntimeError("not a PNG with an IHDR chunk")
    width, height = struct.unpack(">II", data[16:24])
    return width, height, data[25]


def main() -> None:
    manifest = json.loads((SIZED / "sized-manifest.json").read_text(encoding="utf-8"))
    entries = []
    for size in SIZES:
        source = SIZED / f"ui-action-attack-normal-{size}.png"
        data = source.read_bytes()
        width, height, color_type = png_size(data)
        if (width, height) != (size, size) or color_type != 6:
            raise RuntimeError(f"{source.name}: expected {size}x{size} RGBA, got {width}x{height} type={color_type}")
        listed = next((o for o in manifest["outputs"] if o["size"] == size), None)
        if not listed or listed["sha256"] != sha256(source):
            raise RuntimeError(f"{source.name}: sha256 differs from sized-manifest.json")
        name = f"T_UI_Action_Attack_{size}"
        task = u.AssetImportTask()
        task.filename = str(source)
        task.destination_path = DEST
        task.destination_name = name
        task.automated = True
        task.replace_existing = True
        task.save = False
        u.AssetToolsHelpers.get_asset_tools().import_asset_tasks([task])
        asset = u.load_asset(f"{DEST}/{name}")
        if not asset or not isinstance(asset, u.Texture2D):
            raise RuntimeError(f"{name}: not imported as Texture2D")
        asset.set_editor_property("compression_settings", u.TextureCompressionSettings.TC_EDITOR_ICON)
        asset.set_editor_property("mip_gen_settings", u.TextureMipGenSettings.TMGS_NO_MIPMAPS)
        asset.set_editor_property("lod_group", u.TextureGroup.TEXTUREGROUP_UI)
        asset.set_editor_property("srgb", True)
        asset.set_editor_property("filter", u.TextureFilter.TF_BILINEAR)
        asset.set_editor_property("never_stream", True)
        # set_editor_property runs Pre/PostEditChange itself (texture rebuild).
        if not u.EditorAssetLibrary.save_loaded_asset(asset, only_if_is_dirty=False):
            raise RuntimeError(f"{name}: save failed")
        actual = (asset.blueprint_get_size_x(), asset.blueprint_get_size_y())
        if actual != (size, size):
            raise RuntimeError(f"{name}: imported as {actual}")
        uasset = CONTENT / f"{name}.uasset"
        entries.append({
            "size": size,
            "source": source.relative_to(ROOT).as_posix(),
            "sourceSha256": sha256(source),
            "asset": f"{DEST}/{name}",
            "uasset": uasset.relative_to(ROOT).as_posix(),
            "uassetSha256": sha256(uasset) if uasset.is_file() else None,
            "importedDimensions": list(actual),
            "settings": {
                "compression": str(asset.get_editor_property("compression_settings")),
                "mipGen": str(asset.get_editor_property("mip_gen_settings")),
                "lodGroup": str(asset.get_editor_property("lod_group")),
                "srgb": bool(asset.get_editor_property("srgb")),
                "filter": str(asset.get_editor_property("filter")),
                "neverStream": bool(asset.get_editor_property("never_stream")),
            },
        })
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text(json.dumps({
        "schema": "unmatched.t22-icon-import/1",
        "status": "технически импортировано (концепт ART-003 в размерах 24/32/48 px; не художественно принято)",
        "concept": manifest["source"],
        "conceptSha256": manifest["sourceSha256"],
        "method": manifest["method"],
        "why": "T_UI_Action_AttackConcept (1254 px) has no mipmaps: drawn at 24 px it aliases; each HUD size "
               "gets its own exact-size texture sampled 1:1",
        "textures": entries,
    }, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
    u.log(f"ART004_HUD_ICON_IMPORT_PASS sizes={','.join(str(s) for s in SIZES)} dest={DEST}")


main()
