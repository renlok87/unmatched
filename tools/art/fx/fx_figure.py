"""VS-6 F2 (visual chat): build the figure FX assets of FX-21, FX-24, the figure cue overlay (Z-2 leftovers of FX-05 /
FX-19) and import the IC-49 icon.

    python tools/art/fx/fx_figure.py            # one headless editor run (the editor of THIS checkout must be closed)
    python tools/art/fx/fx_figure.py --check    # plain Python: the plan (tokens, grade, sources present)

One UnrealEditor-Cmd process (tools/art/de010 run_editor) runs tools/art/fx/ue_fx_figure_all.py:
  1. tools/art/fx/ue_fx_figure.py   T_FX_HitStar_4x2 (the accepted FX-20 mask), M_FX_FigurePrint + MI_FX_HitStar /
                                    MI_FX_Heal, NS_FX_HitStar, NS_FX_HealMotes (/Game/S08/FX/**), M_FX_FigureCue
  2. tools/art/icons_v3_import.py with ICONS_V3_ONLY=state-heal   T_IV3_state_heal_{18,24,32,36,48,64} (IC-49)
The colours are the linear values of docs/unreal/contracts/hud/hud-style-tokens.json (no literals); the print grade is
the conceptPaste grade fit of the two original maps (equal on both, as fx_field.py checks).
Report: C:/tmp/visual/vs6-f2/fx-figure.json (+ the editor log next to it).
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(REPO / "tools" / "art" / "de010"))
sys.path.insert(0, str(REPO / "tools" / "art" / "material_library"))

WORK = Path("C:/tmp/visual/vs6-f2")
HITSTAR = REPO / "art/imagegen/fx-hitstar-codex/vector/T_FX_HitStar_4x2.png"
TOKENS_USED = ("fx.impact", "fx.rim", "fx.heal", "fx.flash", "mark.keyline")


def plan() -> dict:
    import fx_field
    import fx_import
    tok = fx_import.tokens()
    lin = {name: fx_import.linear_color(tok[name]) for name in TOKENS_USED}
    grade = fx_field.plan()["grade"]
    if not HITSTAR.is_file():
        raise SystemExit("missing %s" % HITSTAR)
    return {"tokens": lin, "grade": grade, "fxGrade": grade,
            "hitstar": {"png": str(HITSTAR), "sha256": hashlib.sha256(HITSTAR.read_bytes()).hexdigest()}}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--check", action="store_true")
    a = ap.parse_args(argv)
    p = plan()
    for script in (HERE / "ue_fx_figure.py", HERE / "ue_fx_figure_all.py", REPO / "tools/art/icons_v3_import.py"):
        if not script.is_file():
            raise SystemExit("missing %s" % script)
    if a.check:
        print(json.dumps(p, indent=1))
        print("FX_FIGURE_CHECK PASS")
        return 0
    import de010
    out = WORK / "fx-figure.json"
    data = de010.run_editor(HERE / "ue_fx_figure_all.py", {"out": str(out), **p}, WORK, "fx-figure", timeout=1800)
    ok = data.get("ok") and data.get("icon", {}).get("ok")
    print(json.dumps({k: data.get(k) for k in ("ok", "texture", "icon", "_editor")}, indent=1, default=str))
    print(json.dumps({k: (data.get(k) or {}).get("statistics") for k in ("figurePrint", "figureCue")}))
    print("FX_FIGURE", "PASS" if ok else "FAIL")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
