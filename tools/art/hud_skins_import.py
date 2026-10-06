"""VS-2 HB-10 (docs/game-design/visual/06-tasks/hud.csv HB-10; 02-visual-design.md §4.2; 04-hud-spec.md §4.4; HUD-RULES
П9): import the accepted 9-slice skins of HB-08 (art/imagegen/hud-skins-v1-codex, accepted by delegation fb2b246c) into
/Game/S08/UI/Skins and bind them into the HUD theme DA_UmHudTheme.Skins / SkinsX2.

Runs inside the editor (worktree project only; the main checkout's GUI editor may be live):

  UnrealEditor-Cmd <uproject> -run=pythonscript -script=<this file> -unattended -nullrhi

Sources: vector/x1/T_Skin_<Name>.png and vector/x2/T_Skin_<Name>.png (the package's exact-size exports, never a downscale
of the x4 master) and slice-margins.json (pixels per file; stretch nine_slice | none).
Assets: /Game/S08/UI/Skins/T_Skin_<Name> (x1) and T_Skin_<Name>_x2 (x2) - 58 textures, settings as the v3 icons
(tools/art/icons_v3_import.py): UserInterface2D (TC_EDITOR_ICON), no mips, TEXTUREGROUP_UI, sRGB, bilinear, never stream.
Theme key: the file name without T_Skin_, CamelCase and "_" split into lower-case dot parts (PanelInset -> panel.inset,
BtnPrimary_Hover -> btn.primary.hover) - the 29 keys of the ВР-HB06 fallback brushes (hud-style-tokens.json "skins").
Brush: DrawAs Box (Image for stretch none), Margin = the file's pixels / its size, ImageSize = the x1 size in su; x2 is
picked by UUmHudTheme::SkinFor at DPI x UI scale >= 1.5. The card.frame.* keys (CP-14) are not touched.
hud_theme_import.py calls bind_theme() after it refills the theme, so a token re-import keeps the PNG skins.
Report: art/imagegen/hud-skins-v1-codex/ue-import-report.json (source sha256, asset, size, margins per texture).
Stdlib + unreal (lazy): the planning half is importable by pytest (tools/art/tests/test_hud_skins_import.py).
"""

from __future__ import annotations

import hashlib
import json
import re
import struct
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PACKAGE = ROOT / "art/imagegen/hud-skins-v1-codex"
MARGINS = PACKAGE / "slice-margins.json"
REPORT = PACKAGE / "ue-import-report.json"
TOKENS = ROOT / "docs/unreal/contracts/hud/hud-style-tokens.json"
DEST = "/Game/S08/UI/Skins"
THEME = "/Game/S08/UI/Theme/DA_UmHudTheme"
SCALES = ("x1", "x2")
CAMEL_RE = re.compile(r"[A-Z][a-z0-9]*")


def skin_key(file_name: str) -> str:
    """T_Skin_BtnPrimary_Hover.png -> btn.primary.hover (CamelCase and '_' split, lower case, dots)."""
    stem = Path(file_name).stem
    if not stem.startswith("T_Skin_"):
        raise ValueError(f"{file_name}: not a T_Skin_* file")
    parts: list[str] = []
    for chunk in stem[len("T_Skin_"):].split("_"):
        words = CAMEL_RE.findall(chunk)
        if "".join(words) != chunk:
            raise ValueError(f"{file_name}: chunk {chunk!r} is not CamelCase")
        parts.extend(w.lower() for w in words)
    return ".".join(parts)


def png_size(data: bytes) -> tuple[int, int]:
    if data[:8] != b"\x89PNG\r\n\x1a\n" or data[12:16] != b"IHDR":
        raise RuntimeError("not a PNG with an IHDR chunk")
    return struct.unpack(">II", data[16:24])


def token_skin_keys() -> list[str]:
    """The 29 skin keys of hud-style-tokens.json (the ВР-HB06 fallback brushes)."""
    tokens = json.loads(TOKENS.read_text(encoding="utf-8"))
    return sorted(tokens["skins"].keys())


def plan(package: Path = PACKAGE) -> list[dict]:
    """One entry per skin: key, asset names, files, PNG sizes, margins (px per file) and stretch."""
    margins = json.loads((package / "slice-margins.json").read_text(encoding="utf-8"))["files"]
    out = []
    for x1 in sorted((package / "vector/x1").glob("T_Skin_*.png")):
        name = x1.stem
        x2 = package / "vector/x2" / x1.name
        if not x2.exists():
            raise RuntimeError(f"{x2}: the x2 export is missing")
        entry = {"key": skin_key(x1.name), "name": name, "assets": {}, "files": {}, "sizes": {}, "margins": {}}
        stretch = None
        for scale, path in (("x1", x1), ("x2", x2)):
            rel = path.relative_to(package).as_posix()
            m = margins.get(rel)
            if m is None:
                raise RuntimeError(f"slice-margins.json: no entry for {rel}")
            if stretch is not None and m["stretch"] != stretch:
                raise RuntimeError(f"{name}: x1 and x2 stretch differ")
            stretch = m["stretch"]
            data = path.read_bytes()
            w, h = png_size(data)
            if m["left"] + m["right"] >= w or m["top"] + m["bottom"] >= h:
                if m["stretch"] != "none":
                    raise RuntimeError(f"{rel}: margins {m} do not fit {w}x{h}")
            entry["assets"][scale] = f"T_Skin_{name[len('T_Skin_'):]}" + ("" if scale == "x1" else "_x2")
            entry["files"][scale] = path.relative_to(ROOT).as_posix() if path.is_relative_to(ROOT) else str(path)
            entry["sha256"] = entry.get("sha256", {})
            entry["sha256"][scale] = hashlib.sha256(data).hexdigest()
            entry["sizes"][scale] = [w, h]
            entry["margins"][scale] = [m["left"], m["top"], m["right"], m["bottom"]]
        entry["stretch"] = stretch
        out.append(entry)
    return out


def check_plan(entries: list[dict]) -> list[str]:
    """Problems of a plan: the keys must be the 29 token skins; x2 must be twice x1 (+-2 px)."""
    errors = []
    keys = sorted(e["key"] for e in entries)
    want = token_skin_keys()
    if keys != want:
        errors.append(f"skin keys {sorted(set(keys) ^ set(want))} differ from hud-style-tokens.json skins")
    for e in entries:
        (w1, h1), (w2, h2) = e["sizes"]["x1"], e["sizes"]["x2"]
        if abs(w2 - 2 * w1) > 2 or abs(h2 - 2 * h1) > 2:
            errors.append(f"{e['name']}: x2 {w2}x{h2} is not twice x1 {w1}x{h1}")
    return errors


def bind_theme(theme, entries: list[dict] | None = None) -> int:
    """Binds the imported textures into a loaded UUmHudTheme (no save). Returns the skins bound (0 = not imported)."""
    import unreal as u

    entries = entries if entries is not None else plan()
    bound = 0
    for e in entries:
        tex = {s: u.EditorAssetLibrary.load_asset(f"{DEST}/{e['assets'][s]}") for s in SCALES}
        if not all(isinstance(t, u.Texture2D) for t in tex.values()):
            continue
        size = {s: u.Vector2D(*e["sizes"][s]) for s in SCALES}
        margin = {s: u.Margin(*[float(v) for v in e["margins"][s]]) for s in SCALES}
        if not theme.import_texture_skin(e["key"], tex["x1"], tex["x2"], size["x1"], size["x2"], margin["x1"],
                                         margin["x2"], e["stretch"] != "none"):
            raise RuntimeError(f"theme: skin {e['key']} refused")
        bound += 1
    return bound


def import_textures(entries: list[dict]) -> int:
    import unreal as u

    tools = u.AssetToolsHelpers.get_asset_tools()
    count = 0
    for e in entries:
        for s in SCALES:
            name = e["assets"][s]
            task = u.AssetImportTask()
            task.filename = str(ROOT / e["files"][s])
            task.destination_path = DEST
            task.destination_name = name
            task.automated = True
            task.replace_existing = True
            task.save = False
            tools.import_asset_tasks([task])
            asset = u.load_asset(f"{DEST}/{name}")
            if not asset or not isinstance(asset, u.Texture2D):
                raise RuntimeError(f"{name}: not imported as Texture2D")
            asset.set_editor_property("compression_settings", u.TextureCompressionSettings.TC_EDITOR_ICON)
            asset.set_editor_property("mip_gen_settings", u.TextureMipGenSettings.TMGS_NO_MIPMAPS)
            asset.set_editor_property("lod_group", u.TextureGroup.TEXTUREGROUP_UI)
            asset.set_editor_property("srgb", True)
            asset.set_editor_property("filter", u.TextureFilter.TF_BILINEAR)
            asset.set_editor_property("never_stream", True)
            if not u.EditorAssetLibrary.save_loaded_asset(asset, only_if_is_dirty=False):
                raise RuntimeError(f"{name}: save failed")
            count += 1
    return count


def main() -> None:
    import unreal as u

    entries = plan()
    errors = check_plan(entries)
    if errors:
        raise RuntimeError("; ".join(errors))
    imported = import_textures(entries)
    theme = u.EditorAssetLibrary.load_asset(THEME)
    if theme is None or not isinstance(theme, u.UmHudTheme):
        raise RuntimeError(f"{THEME}: missing - run tools/s08/hud_contract/hud_theme_import.py first")
    bound = bind_theme(theme, entries)
    if bound != len(entries):
        raise RuntimeError(f"theme: {bound} of {len(entries)} skins bound")
    if not u.EditorAssetLibrary.save_loaded_asset(theme, only_if_is_dirty=False):
        raise RuntimeError(f"{THEME}: save failed")
    report = {
        "schema": "unmatched.hud-skins-import/1",
        "status": "технически импортировано (скины HB-08 приняты по делегированию; вид в UE — лист HB-10)",
        "dest": DEST,
        "theme": THEME,
        "settings": {"compression": "TC_EDITOR_ICON (UserInterface2D)", "mipGen": "TMGS_NO_MIPMAPS",
                     "lodGroup": "TEXTUREGROUP_UI", "srgb": True, "filter": "TF_BILINEAR", "neverStream": True},
        "x2FromPxPerSu": 1.5,
        "count": imported,
        "skins": [{
            "key": e["key"], "stretch": e["stretch"],
            "textures": [{"scale": s, "asset": f"{DEST}/{e['assets'][s]}", "source": e["files"][s],
                          "sourceSha256": e["sha256"][s], "size": e["sizes"][s], "marginPx": e["margins"][s]}
                         for s in SCALES],
        } for e in entries],
    }
    REPORT.write_text(json.dumps(report, ensure_ascii=False, indent=1) + "\n", encoding="utf-8", newline="\n")
    u.log(f"HUD_SKINS_IMPORT_PASS textures={imported} skins={bound} dest={DEST} theme={THEME}")


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:  # noqa: BLE001 - the commandlet must report a failure in the log
        import unreal as _u

        _u.log_error(f"HUD_SKINS_IMPORT FAIL {exc}")
        raise
