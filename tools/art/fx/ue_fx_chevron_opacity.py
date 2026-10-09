"""VC C3 (visual chat, 2026-10-09; vfx.csv FX-16 «прерывание (гаснут за 80 мс)», ВР-VS6-09 -> ВР-VC-13): binds the user
parameter User.Opacity of /Game/S08/FX/Board/NS_FX_AttackChevrons to the Opacity scalar of its material
(M_FX_BoardPrint via MI_FX_Chevron) - the C++ adapter (S08FlowGameModeFx.cpp) writes 1 -> 0 over 80 ms when a combat cue
interrupts CUE-008, instead of cutting the chevrons in one frame. ue_fx_field.py does the same on a full re-run.

  UnrealEditor-Cmd <uproject> -run=pythonscript -script="tools/art/fx/ue_fx_chevron_opacity.py" -unattended -nullrhi
  (add " --check" inside the -script quotes to only report)

Prints one FX_CHEVRON_OPACITY {json} line; ok = the system exposes User.Opacity (and, without --check, the binding saved).
"""
from __future__ import annotations

import json
import sys

import unreal as u  # type: ignore

PATH = "/Game/S08/FX/Board/NS_FX_AttackChevrons"
SPEC = [{"name": "Opacity", "type": "float", "default": 1.0}]


def user_names() -> list:
    d = json.loads(u.S08EnvFxAuthoringLibrary.describe_niagara_system(PATH)).get("describe", {})
    user = d.get("user") or {}
    return sorted(user.keys()) if isinstance(user, dict) else [str(x) for x in user]


def main(argv) -> int:
    check = "--check" in argv
    out = {"system": PATH, "check": check, "userBefore": user_names()}
    if not check:
        out["bind"] = json.loads(u.S08FxAuthoringLibrary.bind_user_material_parameters(PATH, "DirectionalBurst",
                                                                                       json.dumps(SPEC)))
        out["saved"] = bool(u.EditorAssetLibrary.save_asset(PATH, False))
    out["userAfter"] = user_names()
    out["ok"] = any("Opacity" in (n or "") for n in out["userAfter"]) and (check or out["bind"].get("ok", False))
    print("FX_CHEVRON_OPACITY " + json.dumps(out))
    return 0 if out["ok"] else 1


if __name__ == "__main__":
    main(sys.argv[1:])
