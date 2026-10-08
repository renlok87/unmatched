"""VS-6 F2 editor task (tools/art/fx/fx_figure.py runs it headless): the two asset steps in ONE editor process.

1. ue_fx_figure.py - T_FX_HitStar_4x2, M_FX_FigurePrint + MI_FX_HitStar / MI_FX_Heal, NS_FX_HitStar, NS_FX_HealMotes,
   M_FX_FigureCue (writes the report itself);
2. icons_v3_import.py with ICONS_V3_ONLY=state-heal - the IC-49 textures T_IV3_state_heal_<px>.
The result of 2 is merged into the report of 1 ("icon").
"""
import json
import os
import runpy
import traceback
from pathlib import Path

import unreal as u

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
ARGS = json.load(open(os.environ["DE010_ARGS"], encoding="utf-8"))
REPORT = Path(ARGS["out"])

runpy.run_path(str(HERE / "ue_fx_figure.py"), run_name="ue_fx_figure")
report = json.loads(REPORT.read_text(encoding="utf-8"))
try:
    os.environ["ICONS_V3_ONLY"] = "state-heal"
    runpy.run_path(str(REPO / "tools/art/icons_v3_import.py"), run_name="icons_v3_import")
    found = {px: u.EditorAssetLibrary.does_asset_exist("/Game/S08/UI/IconsV3/T_IV3_state_heal_%d" % px)
             for px in (18, 24, 32, 36, 48, 64)}
    report["icon"] = {"ok": all(found.values()), "textures": found}
except Exception:  # noqa: BLE001
    report["icon"] = {"ok": False, "error": traceback.format_exc()}
REPORT.write_text(json.dumps(report, indent=1, sort_keys=True, default=str) + "\n", encoding="utf-8")
