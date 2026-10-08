"""VS-6 F1 editor task (tools/art/fx/fx_field.py runs it headless): the three asset steps in ONE editor process.

1. ue_fx_field.py (the FX-07 / FX-15 marks, the FX-13 / FX-16 board print + systems) - writes the report itself;
2. ue_move_plate_material.build_material(force=True) - M_UM_MovePlate graph 4 (FX-08 choice, FX-09 pulse, FX-14 path);
3. icons_v3_import.py with ICONS_V3_WORLD=1 - the IC-35 world token.
The results of 2 and 3 are merged into the report of 1 ("plate", "world").
"""
import json
import os
import runpy
import sys
import traceback
from pathlib import Path

import unreal as u

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
ARGS = json.load(open(os.environ["DE010_ARGS"], encoding="utf-8"))
REPORT = Path(ARGS["out"])

runpy.run_path(str(HERE / "ue_fx_field.py"), run_name="ue_fx_field")
report = json.loads(REPORT.read_text(encoding="utf-8"))
try:
    sys.path.insert(0, str(REPO / "tools/art/move_selection"))
    import ue_move_plate_material as plate  # noqa: E402
    report["plate"] = {"ok": True, "build": plate.build_material(True)}
except Exception:  # noqa: BLE001
    report["plate"] = {"ok": False, "error": traceback.format_exc()}
try:
    os.environ["ICONS_V3_WORLD"] = "1"
    runpy.run_path(str(REPO / "tools/art/icons_v3_import.py"), run_name="icons_v3_import")
    tex = u.load_asset("/Game/S08/UI/IconsV3/T_IV3_action_attack_token_World")
    report["world"] = {"ok": tex is not None,
                       "size": [tex.blueprint_get_size_x(), tex.blueprint_get_size_y()] if tex else None,
                       "lodGroup": str(tex.get_editor_property("lod_group")) if tex else None,
                       "mipGen": str(tex.get_editor_property("mip_gen_settings")) if tex else None,
                       "compression": str(tex.get_editor_property("compression_settings")) if tex else None}
except Exception:  # noqa: BLE001
    report["world"] = {"ok": False, "error": traceback.format_exc()}
REPORT.write_text(json.dumps(report, indent=1, sort_keys=True, default=str) + "\n", encoding="utf-8")
