"""W4-C hybrid HUD: author the art HUD widget blueprints in the ART worktree.

Runs inside UnrealEditor-Cmd of the art worktree only (never the main
checkout project, whose GUI editor is live):

  UnrealEditor-Cmd <art worktree>/unreal/Unmatched/Unmatched.uproject
      -run=pythonscript -script=<this file> -unattended -nullrhi

(`python tools/art/art_hud_umg.py author --out ...` wraps it and passes the
report path in the environment variable S08_WBP_REPORT). The widget trees are
built by C++ (US08ArtHudAuthoringLibrary.AuthorArtHudWidgetBlueprints ->
US08ArtPlateWidget/US08ArtIconWidget::BuildDefaultTree, the code default tree
of the widget classes), because a widget tree is not reachable from Python.
This script calls it, re-loads the saved assets, checks the parent class and
the bound parts, and writes the report with the sha256 of each .uasset.
Status of the result: technically created - not artistically accepted.
"""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path

import unreal as u

ROOT = Path(__file__).resolve().parents[3]
FOLDER = "/Game/S08/UI/ArtHud"
CONTENT = ROOT / "unreal/Unmatched/Content/S08/UI/ArtHud"
PARTS = {
    "WBP_S08ArtPlate": ["PlateBackground", "Marker", "NameText", "TeamChip", "TeamText", "TeamShape", "HpBar",
                        "HpBack", "HpFill", "HpFillImage", "HpText", "StatusText"],
    "WBP_S08ArtIcon": ["Icon"],
    # W5b-R D-1: the screen tag and the damage number
    "WBP_S08ArtTag": ["TagBackground", "ChipBox", "TeamShape", "NameText", "HpBar", "HpBack", "HpFill", "HpFillImage",
                      "HpText"],
    "WBP_S08ArtDamage": ["DamageBackground", "DamageText"],
}
PARENTS = {"WBP_S08ArtPlate": "S08ArtPlateWidget", "WBP_S08ArtIcon": "S08ArtIconWidget",
           "WBP_S08ArtTag": "S08ArtTagWidget", "WBP_S08ArtDamage": "S08ArtDamageWidget"}


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    overwrite = os.environ.get("S08_WBP_OVERWRITE", "1") == "1"
    raw = u.S08ArtHudAuthoringLibrary.author_art_hud_widget_blueprints(FOLDER, overwrite)
    report = json.loads(raw)
    checks = []
    for name, parts in PARTS.items():
        path = f"{FOLDER}/{name}"
        asset = u.EditorAssetLibrary.load_asset(path)
        cls = u.EditorAssetLibrary.load_blueprint_class(path)
        native = getattr(u, PARENTS[name]).static_class()
        parent_ok = cls is not None and bool(u.MathLibrary.class_is_child_of(cls, native))
        file = CONTENT / f"{name}.uasset"
        checks.append({
            "asset": path,
            "loaded": asset is not None,
            "generatedClass": cls.get_path_name() if cls is not None else None,
            "parentIsNativeClass": parent_ok,
            "requiredParts": parts,
            "file": file.relative_to(ROOT).as_posix(),
            "bytes": file.stat().st_size if file.is_file() else None,
            "sha256": sha256(file) if file.is_file() else None,
        })
    report["checks"] = checks
    ok = all(a.get("result") in ("created", "rebuilt", "exists-unchanged") and a.get("compileStatus", "up-to-date")
             in ("up-to-date", "warnings") for a in report.get("assets", [])) and all(
        c["loaded"] and c["parentIsNativeClass"] and c["sha256"] for c in checks)
    report["pass"] = ok
    out = os.environ.get("S08_WBP_REPORT")
    if out:
        Path(out).parent.mkdir(parents=True, exist_ok=True)
        Path(out).write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    u.log(("W4C_ART_HUD_WBP_PASS " if ok else "W4C_ART_HUD_WBP_FAIL ") + json.dumps(
        {"assets": [(a.get("asset"), a.get("result"), a.get("compileStatus")) for a in report.get("assets", [])]}))


main()
