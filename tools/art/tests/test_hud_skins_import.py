"""VS-2 HB-10: the planning half of tools/art/hud_skins_import.py (no Unreal needed)."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import hud_skins_import as hs  # noqa: E402


@pytest.mark.parametrize("name,key", [
    ("T_Skin_Panel.png", "panel"),
    ("T_Skin_PanelInset.png", "panel.inset"),
    ("T_Skin_BtnPrimary_Hover.png", "btn.primary.hover"),
    ("T_Skin_Btn_Normal.png", "btn.normal"),
    ("T_Skin_KeyChip.png", "key.chip"),
    ("T_Skin_ToastWarning.png", "toast.warning"),
    ("T_Skin_Check_On.png", "check.on"),
])
def test_skin_key(name, key):
    assert hs.skin_key(name) == key


def test_skin_key_refuses_other_files():
    with pytest.raises(ValueError):
        hs.skin_key("T_IV3_action_attack_24.png")


def test_plan_matches_the_29_token_skins():
    entries = hs.plan()
    assert len(entries) == 29
    assert hs.check_plan(entries) == []
    assert sorted(e["key"] for e in entries) == hs.token_skin_keys()
    names = [e["assets"][s] for e in entries for s in hs.SCALES]
    assert len(names) == len(set(names)) == 58
    assert all(n.startswith("T_Skin_") for n in names)
    assert all(e["assets"]["x2"] == e["assets"]["x1"] + "_x2" for e in entries)


def test_plan_margins_and_stretch():
    for e in hs.plan():
        for s in hs.SCALES:
            w, h = e["sizes"][s]
            left, top, right, bottom = e["margins"][s]
            if e["stretch"] == "nine_slice":
                assert min(left, top, right, bottom) > 0, e["name"]
                assert left + right < w and top + bottom < h, (e["name"], s)
        # stretch 'none' is only the fixed 24 su checkbox (ВР-VS2-HB08-04)
        assert (e["stretch"] == "none") == e["key"].startswith("check."), e["name"]


def test_check_plan_flags_a_wrong_x2():
    entries = hs.plan()
    entries[0]["sizes"]["x2"] = [entries[0]["sizes"]["x1"][0] * 3, entries[0]["sizes"]["x1"][1] * 3]
    assert any("not twice" in e for e in hs.check_plan(entries))


# ---- VS-2 HB-12: the software cursors (--cursors) ----------------------------------------------------------------------
def test_cursor_plan_names_and_hotspots():
    entries = hs.cursor_plan()
    assert len(entries) == 44  # default, pointer, denied x 4 sizes + busy 8 frames x 4 sizes
    names = {e["name"] for e in entries}
    for want in ("T_Cursor_Default", "T_Cursor_Pointer_24", "T_Cursor_Denied_48", "T_Cursor_Pointer_x2",
                 "T_Cursor_Busy_00", "T_Cursor_Busy_07_x2"):
        assert want in names
    pointer = {e["px"]: e["hotspot"] for e in entries if e["state"] == "Pointer"}
    assert pointer == {24: [8, 2], 32: [11, 2], 48: [17, 3], 64: [22, 4]}  # IC-36 fix1 fingertip (11, 2) u
    busy = {e["px"]: e["hotspot"] for e in entries if e["state"] == "Busy"}
    assert busy == {24: [12, 12], 32: [16, 16], 48: [24, 24], 64: [32, 32]}


def test_cursor_config_copy_is_current():
    """unreal/Unmatched/Config/Cursors/S08CursorHotspots.json (read by UUmCursor) = the plan of cursor-hotspots.json."""
    import json
    on_disk = json.loads(hs.CURSOR_HOTSPOTS_CONFIG.read_text(encoding="utf-8"))
    assert on_disk == hs.cursor_hotspots_config(hs.cursor_plan())
