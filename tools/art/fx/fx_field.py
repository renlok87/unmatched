"""VS-6 F1 (visual chat): build the field / choice FX assets of FX-07, FX-08, FX-09, FX-13, FX-14, FX-15, FX-16 and IC-35.

    python tools/art/fx/fx_field.py            # one headless editor run (the editor of THIS checkout must be closed)
    python tools/art/fx/fx_field.py --check    # plain Python: the plan (tokens, grade, scripts present)

One UnrealEditor-Cmd process (tools/art/de010 run_editor) runs tools/art/fx/ue_fx_field_all.py, which executes:
  1. tools/art/fx/ue_fx_field.py                      M_FX_FieldMark + MI_FX_SelectionRing / MI_FX_TargetArc,
                                                      M_FX_BoardPrint + MI_FX_Dust / MI_FX_Chevron, NS_FX_Dust,
                                                      NS_FX_AttackChevrons (/Game/S08/FX/**)
  2. tools/art/move_selection/ue_move_plate_material.py --force   M_UM_MovePlate graph 4 (choice / pulse / path)
  3. tools/art/icons_v3_import.py with ICONS_V3_WORLD=1           T_IV3_action_attack_token_World (IC-35)
The colours are the linear values of docs/unreal/contracts/hud/hud-style-tokens.json (no literals); the board print
grade is the conceptPaste grade fit of the two original maps (equal on both; S08FlowGameModeFx ApplyProfileGrade).
Report: C:/tmp/visual/vs6f1/fx-field.json (+ the editor log next to it).
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(REPO / "tools" / "art" / "de010"))
sys.path.insert(0, str(REPO / "tools" / "art" / "material_library"))

PROFILES = REPO / "unreal/Unmatched/Config/ArtBoards/S08ArtBoardProfiles.json"
WORK = Path("C:/tmp/visual/vs6f1")
TOKENS_USED = ("board.choice", "board.keyline", "board.target", "mark.keyline", "text.secondary", "card.cream")
MAPS = ("marmoreal-original", "sarpedon-original")


def plan() -> dict:
    import fx_import
    tok = fx_import.tokens()
    lin = {name: fx_import.linear_color(tok[name]) for name in TOKENS_USED}
    prof = json.loads(PROFILES.read_text(encoding="utf-8"))
    grades = []
    for board in prof["boards"]:
        if board.get("id") in MAPS:
            g = board["conceptPaste"]["grade"]
            grades.append((tuple(g["fitScale"]), tuple(g["fitPower"])))
    if len(set(grades)) != 1:
        raise SystemExit("the grade fits of the two maps differ - the baked board-print grade needs a runtime path")
    scale, power = grades[0]
    grade = {"GradeScale": [round(k, 6) for k in scale] + [0.0],
             "GradePow": [round(1.0 / k, 6) for k in power] + [0.0]}  # the paste convention (fx_import)
    return {"tokens": lin, "grade": grade}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--check", action="store_true")
    a = ap.parse_args(argv)
    p = plan()
    for script in (HERE / "ue_fx_field.py", HERE / "ue_fx_field_all.py",
                   REPO / "tools/art/move_selection/ue_move_plate_material.py", REPO / "tools/art/icons_v3_import.py"):
        if not script.is_file():
            raise SystemExit("missing %s" % script)
    if a.check:
        print(json.dumps(p, indent=1))
        print("FX_FIELD_CHECK PASS")
        return 0
    import de010
    out = WORK / "fx-field.json"
    data = de010.run_editor(HERE / "ue_fx_field_all.py", {"out": str(out), **p}, WORK, "fx-field", timeout=1800)
    ok = data.get("ok") and data.get("plate", {}).get("ok") and data.get("world", {}).get("ok")
    print(json.dumps({k: v for k, v in data.items() if k in ("ok", "plate", "world", "_editor")}, indent=1))
    print("FX_FIELD", "PASS" if ok else "FAIL")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
