"""VS-2 HB-06 / HB-11 (04-hud-spec.md §4.1, ВР-H14; HUD-RULES П9): generate the widget blueprints of the UMG HUD from
their C++ bases (UUmHudAuthoringLibrary -> BuildDefaultTree of each class), in the worktree project only:

  UnrealEditor-Cmd <uproject> -run=pythonscript -script=<this file> -unattended -nullrhi

  /Game/S08/UI/Root/WBP_UmHudRoot     parent UmHudRoot   parts Screens, Modals, Reconnect
  /Game/S08/UI/Hud/WBP_UI_SCR_GAME    parent UmGameHud   parts Canvas + 18 block slots (04 §4.2)
  /Game/S08/UI/Common/WBP_UmButton    parent UmButton    parts Box, Body, Content, Icon, Label, KeyChip, KeyText, FocusRing
  /Game/S08/UI/Common/WBP_UmCursor    parent UmCursor    parts Box, Image (VS-2 HB-12)
  /Game/S08/UI/Common/WBP_UmPortrait  parent S08TurnPortraitWidget  parts Panel, Avatar, DiscBox, Disc, AvatarImage,
                                      MonogramText, NameText, StatusText, Stats, HpText, TrackerRow (VS-2 CP-08)
  /Game/S08/UI/Common/WBP_UmConnectionBadge  parent UmConnectionBadge  parts Box, Icon, FallbackText (VS-2 HB-14)
  /Game/S08/UI/Hud/WBP_UI_HUD_TOP     parent UmHudTop    parts Plate, Row, MenuButton, Conn, TurnText, LogButton (HB-14)
  /Game/S08/UI/Hud/WBP_UI_HUD_STATUS  parent UmHudStatusLine  parts Frame, BodyBox, Body, Row, PulseDot, StatusText,
                                      KeyChip, KeyRow, KeyBox0..2, Key0..2, KeyText0..2 (VS-2 HB-15)
  /Game/S08/UI/Hud/WBP_UI_HUD_BANNER  parent UmHudBanner parts Plate, Text (VS-2 HB-16)
  /Game/S08/UI/Hud/WBP_UI_HUD_PANEL_LOC  parent UmHudPlayerPanel  parts Panel, Canvas, Portrait (WBP_UmPortrait), NameText,
                                      StatusRow, PulseDot, StatusText, HpRow, HeartIcon, HpText, TrackerRow, SidekickRow
                                      (VS-2 HB-18); WBP_UI_HUD_PANEL_OPP the same, mirrored (HB-20)
  /Game/S08/UI/Hud/WBP_UI_HUD_OPP_HAND  parent UmHudOppHand  parts Panel, Column, Backs, Caption (VS-2 HB-21)
  /Game/S08/UI/Common/WBP_UmCard       parent UmCardWidget  parts Box, Card, Layers, Underlay, Face, Frame, FlashLayer,
                                      FocusRing, NewDot, BoostChip, BoostText (+ optional icons / fallback) (VS-3 CP-15)
  /Game/S08/UI/Hud/WBP_UI_HUD_HAND     parent UmHudHand     parts Row, CountPlate, CountBox, CountText, WhyPlate, WhyBox,
                                      WhyText, BoostRibbon, RibbonRow, RibbonIcon, RibbonText (VS-3 HB-24; the cards are
                                      pooled WBP_UmCard instances made at run time)
  /Game/S08/UI/Common/WBP_UmSpinner    parent UmSpinner     parts Box, Icon (VS-3 HB-47)
  /Game/S08/UI/Hud/WBP_UI_HUD_DECKS    parent UmHudDecks    parts Row, DeckChip, DiscardChip (WBP_UmButton), DeckMini,
                                      DiscardMini (WBP_UmCard), DeckCount, DiscardCount, DiscardIcon (VS-3 HB-27)
  /Game/S08/UI/Hud/WBP_UI_HUD_DECKPANEL  parent UmHudDeckPanel  parts Root, Panel, Body, Title, Tabs, TabOwn, TabOpp,
                                      CloseButton, Summary, Backs, FilterButton, Rows, Skeleton (VS-3 HB-28; the rows are
                                      pooled UUmDeckRow made at run time)

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
    "/Game/S08/UI/Common/WBP_UmCursor": "UmCursor",
    "/Game/S08/UI/Common/WBP_UmPortrait": "S08TurnPortraitWidget",
    "/Game/S08/UI/Common/WBP_UmConnectionBadge": "UmConnectionBadge",
    "/Game/S08/UI/Hud/WBP_UI_HUD_TOP": "UmHudTop",
    "/Game/S08/UI/Hud/WBP_UI_HUD_STATUS": "UmHudStatusLine",
    "/Game/S08/UI/Hud/WBP_UI_HUD_BANNER": "UmHudBanner",
    "/Game/S08/UI/Hud/WBP_UI_HUD_PANEL_LOC": "UmHudPlayerPanel",
    "/Game/S08/UI/Hud/WBP_UI_HUD_PANEL_OPP": "UmHudPlayerPanel",
    "/Game/S08/UI/Hud/WBP_UI_HUD_OPP_HAND": "UmHudOppHand",
    "/Game/S08/UI/Common/WBP_UmCard": "UmCardWidget",
    "/Game/S08/UI/Hud/WBP_UI_HUD_HAND": "UmHudHand",
    "/Game/S08/UI/Common/WBP_UmSpinner": "UmSpinner",
    "/Game/S08/UI/Hud/WBP_UI_HUD_DECKS": "UmHudDecks",
    "/Game/S08/UI/Hud/WBP_UI_HUD_DECKPANEL": "UmHudDeckPanel",
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
