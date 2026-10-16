"""HUD "Стол" T1 (docs/game-design/hud-redesign/03-CONCEPT.md §5.1): import the four box-canon skins of
art/imagegen/hud-table-t1 (hud.table.card / .strip / .slip / .dial) into /Game/S08/UI/Skins and bind them into
DA_UmHudTheme next to the existing skins. hud_skins_import.py's check_plan wants the full 29-key token set, which this
add-on package does not carry; the texture import and the binding are its own functions.

  UnrealEditor-Cmd <uproject> -run=pythonscript -script="<repo>/tools/art/hud_table_import.py" -unattended -nullrhi
"""
import sys
from pathlib import Path

sys.argv += ["--package=art/imagegen/hud-table-t1", "--with-hud"]
sys.path.insert(0, str(Path(__file__).resolve().parent))
import hud_skins_import as h  # noqa: E402


def main() -> None:
    import unreal as u

    entries = h.plan()
    keys = sorted(e["key"] for e in entries)
    if keys != ["hud.table.card", "hud.table.dial", "hud.table.slip", "hud.table.strip"]:
        raise RuntimeError(f"unexpected kit keys {keys}")
    imported = h.import_textures(entries)
    theme = u.EditorAssetLibrary.load_asset(h.THEME)
    if theme is None:
        raise RuntimeError(f"{h.THEME}: missing")
    bound = h.bind_theme(theme, entries)
    if bound != len(entries) or not u.EditorAssetLibrary.save_loaded_asset(theme, only_if_is_dirty=False):
        raise RuntimeError(f"theme: {bound} of {len(entries)} bound or save failed")
    u.log(f"HUD_TABLE_IMPORT_PASS textures={imported} skins={bound}")


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:  # the commandlet exit code stays 0; the log line is the verdict
        import unreal as u
        u.log_error(f"HUD_TABLE_IMPORT_FAIL {exc}")
        raise
