"""VS-1 HB-04 (04-hud-spec.md §4.4, ВР-45, ВР-77, ВР-HB06): create / refresh the UMG theme asset
/Game/S08/UI/Theme/DA_UmHudTheme (UUmHudTheme) from docs/unreal/contracts/hud/hud-style-tokens.json.

Runs inside the editor (UE Python):

  UnrealEditor-Cmd unreal/Unmatched/Unmatched.uproject -run=pythonscript -script=<this file> -unattended -nullrhi

The aliases are resolved by the SAME code that writes S08HudTokens.generated.h (hud_tokens_codegen.collect), the values
go into the asset through the UUmHudTheme::Import* calls (colours: FLinearColor::FromSRGBColor(FColor::FromHex(hex))).
The asset stores sha256 of the JSON; hud_contract.py validate compares it with the header. Idempotent: the asset is
reset and refilled on every run. Content/ is git-ignored: commit the asset with git add -f (HUD-RULES П9).
"""
from __future__ import annotations

import sys
from pathlib import Path

import unreal as u

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import hud_tokens_codegen as cg  # noqa: E402

PACKAGE_DIR = "/Game/S08/UI/Theme"
ASSET_NAME = "DA_UmHudTheme"
ASSET_PATH = "%s/%s" % (PACKAGE_DIR, ASSET_NAME)


def hex_of(rgb) -> str:
    return "#%02X%02X%02X" % tuple(rgb)


def log(msg: str) -> None:
    u.log("HUD_THEME_IMPORT " + msg)


def create_or_load():
    if u.EditorAssetLibrary.does_asset_exist(ASSET_PATH):
        asset = u.EditorAssetLibrary.load_asset(ASSET_PATH)
        if asset is not None and isinstance(asset, u.UmHudTheme):
            return asset
        raise RuntimeError("%s exists but is not a UmHudTheme" % ASSET_PATH)
    factory = u.DataAssetFactory()
    factory.set_editor_property("data_asset_class", u.UmHudTheme)
    asset = u.AssetToolsHelpers.get_asset_tools().create_asset(ASSET_NAME, PACKAGE_DIR, u.UmHudTheme, factory)
    if asset is None:
        raise RuntimeError("could not create %s" % ASSET_PATH)
    return asset


def main() -> None:
    tokens = cg.load(cg.TOKENS)
    sha = cg.json_sha256(cg.TOKENS)
    header_sha = cg.header_sha(cg.HEADER)
    if header_sha != sha:
        raise RuntimeError("S08HudTokens.generated.h is stale (%s vs JSON %s): run hud_tokens_codegen.py first"
                           % (header_sha, sha))
    c = cg.collect(tokens)
    theme = create_or_load()
    theme.import_reset()
    for t in c["colors"]:
        if not theme.import_color(t["name"], t["hex"], t["alpha"]):
            raise RuntimeError("color %s" % t["name"])
    for t in c["alphas"]:
        theme.import_alpha(t["name"], t["value"])
    for t in c["types"]:
        theme.import_font(t["name"], t["face"], t["su"])
    for t in c["space"]:
        theme.import_space(t["name"], float(t["value"]))
    for t in c["radius"]:
        theme.import_radius(t["name"], float(t["value"]))
    for t in c["motion"]:
        theme.import_motion_ms(t["name"], float(t["value"]))
    for s in c["skins"]:
        ok = theme.import_rounded_skin(s["name"], hex_of(s["fill"]), s["fill_alpha"], hex_of(s["edge"]), s["edge_alpha"],
                                       s["edge_su"], s["radius"], s["half_height"])
        if not ok:
            raise RuntimeError("skin %s" % s["name"])
    theme.import_tokens_sha(sha)
    # VS-2 HB-10: the imported 9-slice PNG skins (tools/art/hud_skins_import.py) replace the fallback brushes again -
    # a token re-import must not drop them; 0 before the first skin import
    sys.path.insert(0, str(HERE.parents[1] / "art"))
    import hud_skins_import as skins  # noqa: E402
    texture_skins = skins.bind_theme(theme)
    # VS-3 CP-14: the card frames (tools/art/cards/ue_import_card_media.py --frames) likewise; 0 before their import
    sys.path.insert(0, str(HERE.parents[1] / "art" / "cards"))
    import ue_import_card_media as card_media  # noqa: E402
    card_frames = card_media.bind_frames(theme)
    if not u.EditorAssetLibrary.save_loaded_asset(theme, only_if_is_dirty=False):
        raise RuntimeError("could not save %s" % ASSET_PATH)
    log("saved %s colors=%d alphas=%d type=%d space=%d radius=%d motion=%d skins=%d textureSkins=%d cardFrames=%d "
        "sha256=%s" % (ASSET_PATH, len(c["colors"]), len(c["alphas"]), len(c["types"]), len(c["space"]),
                       len(c["radius"]), len(c["motion"]), len(c["skins"]), texture_skins, card_frames, sha))


if __name__ == "__main__":
    try:
        main()
    except Exception as e:  # noqa: BLE001 - the commandlet must report a failure in the log
        u.log_error("HUD_THEME_IMPORT FAIL %s" % e)
        raise
