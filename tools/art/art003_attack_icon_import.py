"""Import the existing crossed-swords concept as an isolated K3 marker candidate."""

from __future__ import annotations

import hashlib
import json
import struct
from pathlib import Path

import unreal as u


ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / "art/imagegen/mvp-v1/ui/actions/ui-action-attack-normal.png"
DEST = "/Game/ArtTests/ARTMarkers/Textures"
NAME = "T_UI_Action_AttackConcept"
REPORT = ROOT / "docs/game-design/evidence/ART-003/attack-icon-import-report.json"


def main() -> None:
    data = SOURCE.read_bytes()
    if data[:8] != b"\x89PNG\r\n\x1a\n" or data[12:16] != b"IHDR":
        raise RuntimeError("Source is not a PNG with an IHDR chunk")
    width, height = struct.unpack(">II", data[16:24])
    color_type = data[25]
    if width != height or color_type != 6:
        raise RuntimeError(f"Expected square RGBA icon, got {width}x{height} type={color_type}")

    task = u.AssetImportTask()
    task.filename = str(SOURCE)
    task.destination_path = DEST
    task.destination_name = NAME
    task.automated = True
    task.replace_existing = True
    task.save = True
    u.AssetToolsHelpers.get_asset_tools().import_asset_tasks([task])
    asset = u.load_asset(f"{DEST}/{NAME}")
    if not asset or not isinstance(asset, u.Texture2D):
        raise RuntimeError("Unreal did not import the icon as Texture2D")
    actual_width = asset.blueprint_get_size_x()
    actual_height = asset.blueprint_get_size_y()
    if (actual_width, actual_height) != (width, height):
        raise RuntimeError(f"Texture dimensions changed: {actual_width}x{actual_height}")
    u.EditorAssetLibrary.save_loaded_asset(asset)
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text(json.dumps({
        "status": "imported_concept_not_approved",
        "source": str(SOURCE.relative_to(ROOT)).replace("\\", "/"),
        "source_sha256": hashlib.sha256(data).hexdigest(),
        "source_dimensions": [width, height],
        "source_png_color_type": color_type,
        "asset": f"{DEST}/{NAME}",
        "imported_dimensions": [actual_width, actual_height],
        "small_size_24px_review": "open",
    }, indent=2), encoding="utf-8")
    u.log(f"ART003_ATTACK_ICON_IMPORT_PASS {width}x{height} {DEST}/{NAME}")


main()
