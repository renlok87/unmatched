"""Scratch: review-config-r4.json of ASSET-ACHILLES-001 = copy of the committed review-config.json (stage 7a, import run r3)
pointing at import run r4 (model r3), the r3 look-dev measure report, the r3 clip run and TeamDyeGain of import profile rev 4.
    python make_review_config_r4.py <out.json>
"""
import json
import sys
from pathlib import Path

REPO = Path("C:/Users/ren/WebstormProjects/unmached/unmached")
A = "art/pipeline-candidates/ASSET-ACHILLES-001"
cfg = json.loads((REPO / A / "20261014-h2ld-ldc-ue/review-config.json").read_text(encoding="utf-8"))
prof = json.loads((REPO / A / "build-profiles/achilles-h2ld-lookdev-ue-import-r4.json").read_text(encoding="utf-8"))
old = "LUT iteration 0 (look-dev run 20261014-h2-lookdev-r2 as is)"
assert old in cfg["note"]
cfg["note"] = cfg["note"].replace(old, "model r3 (look-dev run 20261014-h2-lookdev-r3: junction weights at the right "
                                       "armhole), LUT = T_UM_MatLUT_Achilles_UE_r3 (UE look-dev r3: warm bronze F0, cloth "
                                       "sheen), MI knobs of import profile rev 4 (= rev 3)")
assert cfg["run_dir"] == A + "/20261014-h2ld-ue-import-r3", cfg["run_dir"]
cfg["run_dir"] = A + "/20261014-h2ld-ue-import-r4"
cfg["concept_zones"] = A + "/20261014-h2-lookdev-r3/reports/measure-report.json"
fi = cfg["verify"]["instances"]["figure_instance"]["scalars"]
fi["TeamDyeGain"] = prof["ue"]["figure_parameters"]["TeamDyeGain"]
fi["TeamDyeCeiling"] = prof["ue"]["figure_parameters"]["TeamDyeCeiling"]
assert cfg["verify"]["clips_reference"] == A + "/20261014-h2anim/reports/ue-measure-clips.json"
cfg["verify"]["clips_reference"] = A + "/20261014-h2anim-r3/reports/ue-measure-clips.json"
out = Path(sys.argv[1])
out.write_text(json.dumps(cfg, ensure_ascii=False, indent=1) + "\n", encoding="utf-8", newline="\n")
print("wrote", out, "TeamDyeGain", fi["TeamDyeGain"], "height_uu", cfg["verify"]["height_uu"])
