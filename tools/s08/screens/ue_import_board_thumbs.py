"""VS-7 SC-09 (docs/game-design/visual/06-tasks/screens.csv SC-09; ВР-48, ВР-VS4-SC08-08): the two board thumbnails of the
LOBBY Create column - the whole map illustrations scraped-data/images/maps/<marmoreal|sarpedon>.png (LAN only, out of
git) as UI textures /Game/S08/UI/Boards/T_BoardThumb_<marmoreal|sarpedon> (out of git like the portraits:
unreal/Unmatched/.gitignore Content/, no git add -f). UI/UmBoardChip.h loads them; missing -> the board name alone.

  python tools/s08/screens/ue_import_board_thumbs.py --prepare
      plain Python + Pillow: the source PNG (aspect kept, no crop) resampled LANCZOS to 600 px wide into
      C:/tmp/visual/VS7/board-thumbs/ (the tile shows <= 468 px at 150 %; without mips a 2.2x source shimmers less than
      the 1337 px original), with the sha256 of source and output in board-thumbs.json
  UnrealEditor-Cmd <uproject> -run=pythonscript -script=<this file> -unattended -nullrhi
      inside UE: import the prepared PNGs - TC_EDITOR_ICON (UserInterface2D), TMGS_NO_MIPMAPS ("2 текстуры UI без mip",
      the SC-09 budget), TEXTUREGROUP_UI, sRGB, never stream, clamp; prints BOARD_THUMBS_PASS / _FAIL
Source order: <repo>/scraped-data/images/maps, else the main checkout's scraped-data/images/maps.
"""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
MAIN = Path("C:/Users/ren/WebstormProjects/unmached/unmached")
OUT = Path("C:/tmp/visual/VS7/board-thumbs")
MAPS = ("marmoreal", "sarpedon")
WIDTH = 600
DEST = "/Game/S08/UI/Boards"


def sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def source(name: str) -> Path:
    for root in (REPO, MAIN):
        p = root / "scraped-data/images/maps" / f"{name}.png"
        if p.exists():
            return p
    raise FileNotFoundError(f"{name}.png not found under scraped-data/images/maps")


def prepare() -> int:
    from PIL import Image

    OUT.mkdir(parents=True, exist_ok=True)
    report = {}
    for name in MAPS:
        src = source(name)
        im = Image.open(src).convert("RGB")
        h = round(im.height * WIDTH / im.width)
        out = OUT / f"T_BoardThumb_{name}.png"
        im.resize((WIDTH, h), Image.LANCZOS).save(out)
        report[name] = {"source": src.as_posix(), "sourceSha256": sha(src), "sourceSize": list(im.size),
                        "out": out.as_posix(), "outSha256": sha(out), "outSize": [WIDTH, h]}
    (OUT / "board-thumbs.json").write_text(json.dumps(report, indent=1) + "\n", encoding="utf-8")
    print("BOARD_THUMBS_PREPARED", json.dumps(report))
    return 0


def ue_import() -> None:
    import unreal as u

    tasks = []
    for name in MAPS:
        t = u.AssetImportTask()
        t.filename = str(OUT / f"T_BoardThumb_{name}.png")
        t.destination_path = DEST
        t.destination_name = f"T_BoardThumb_{name}"
        t.replace_existing = True
        t.automated = True
        t.save = False
        tasks.append(t)
    u.AssetToolsHelpers.get_asset_tools().import_asset_tasks(tasks)
    ok = True
    for name in MAPS:
        path = f"{DEST}/T_BoardThumb_{name}"
        tex = u.EditorAssetLibrary.load_asset(path)
        if not tex:
            ok = False
            u.log_error(f"BOARD_THUMBS missing {path}")
            continue
        tex.set_editor_property("compression_settings", u.TextureCompressionSettings.TC_EDITOR_ICON)
        tex.set_editor_property("mip_gen_settings", u.TextureMipGenSettings.TMGS_NO_MIPMAPS)
        tex.set_editor_property("lod_group", u.TextureGroup.TEXTUREGROUP_UI)
        tex.set_editor_property("srgb", True)
        tex.set_editor_property("never_stream", True)
        tex.set_editor_property("address_x", u.TextureAddress.TA_CLAMP)
        tex.set_editor_property("address_y", u.TextureAddress.TA_CLAMP)
        u.EditorAssetLibrary.save_asset(path, only_if_is_dirty=False)
        u.log(f"BOARD_THUMBS {path} {tex.blueprint_get_size_x()}x{tex.blueprint_get_size_y()}")
    u.log("BOARD_THUMBS_PASS" if ok else "BOARD_THUMBS_FAIL")
    if not ok:
        raise RuntimeError("board thumbnails import failed")


if __name__ == "__main__":
    if "--prepare" in sys.argv:
        sys.exit(prepare())
    ue_import()
