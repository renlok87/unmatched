"""VS-2 HB-06 / HB-11 (04-hud-spec.md §4.1, ВР-H14; HUD-RULES П9): generate the widget blueprints of the UMG HUD from
their C++ bases (UUmHudAuthoringLibrary -> BuildDefaultTree of each class), in the worktree project only:

  UnrealEditor-Cmd <uproject> -run=pythonscript -script=<this file> -unattended -nullrhi

  /Game/S08/UI/Root/WBP_UmHudRoot     parent UmHudRoot   parts Screens, Modals, Reconnect
  /Game/S08/UI/Hud/WBP_UI_SCR_GAME    parent UmGameHud   parts Canvas + 18 block slots (04 §4.2)
  /Game/S08/UI/Common/WBP_UmButton    parent UmButton    parts Box, Body, Content, Icon, Label, KeyChip, KeyText, FocusRing

A widget tree is not reachable from Python, so the C++ library builds it (the same function the class uses without a
WBP) and this script re-loads every asset, checks the parent class, writes the report (env UM_HUD_WBP_REPORT, default
C:/tmp/visual/um-hud-wbp-report.json) with the sha256 of each .uasset. Content/ is git-ignored: commit with git add -f.
Status: technically created (no art acceptance - the slots are empty until their blocks move in).
"""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path

import unreal as u

ROOT = Path(__file__).resolve().parents[3]
CONTENT = ROOT / "unreal/Unmatched/Content"
ASSETS = {
    "/Game/S08/UI/Root/WBP_UmHudRoot": "UmHudRoot",
    "/Game/S08/UI/Hud/WBP_UI_SCR_GAME": "UmGameHud",
    "/Game/S08/UI/Common/WBP_UmButton": "UmButton",
}


def main() -> None:
    overwrite = os.environ.get("UM_HUD_WBP_OVERWRITE", "1") == "1"
    report = json.loads(u.UmHudAuthoringLibrary.author_um_hud_widget_blueprints(overwrite))
    checks = []
    ok = True
    for path, parent in ASSETS.items():
        cls = u.EditorAssetLibrary.load_blueprint_class(path)
        native = getattr(u, parent).static_class()
        parent_ok = cls is not None and bool(u.MathLibrary.class_is_child_of(cls, native))
        file = CONTENT / (path[len("/Game/"):] + ".uasset")
        checks.append({"asset": path, "parent": parent, "parentOk": parent_ok, "file": file.relative_to(ROOT).as_posix(),
                       "sha256": hashlib.sha256(file.read_bytes()).hexdigest() if file.exists() else None})
        ok &= parent_ok and file.exists()
    for a in report.get("assets", []):
        ok &= a.get("result") in ("created", "rebuilt", "exists-unchanged") and a.get("compileStatus", "up-to-date") != "error"
    report["checks"] = checks
    out = Path(os.environ.get("UM_HUD_WBP_REPORT", "C:/tmp/visual/um-hud-wbp-report.json"))
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    u.log(("UM_HUD_WBP_PASS" if ok else "UM_HUD_WBP_FAIL") + f" assets={len(checks)} report={out}")
    if not ok:
        raise RuntimeError(f"UM HUD WBP authoring failed - {out}")


if __name__ == "__main__":
    main()
