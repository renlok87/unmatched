"""Write the Achilles UE look-dev review config (stage 7a) from the Angel config with Achilles values.

    python write_review_config.py <out json> <run_dir rel> <height_uu>
"""
import json
import sys

REPO = "C:/Users/ren/WebstormProjects/unmached/unmached"
cfg = json.load(open(REPO + "/art/pipeline-candidates/ASSET-ANGEL-001/20261014-h2ld-ldc-ue/review-config.json", encoding="utf-8"))
out, run_dir, height = sys.argv[1], sys.argv[2], float(sys.argv[3])
A = "art/pipeline-candidates/ASSET-ACHILLES-001"
H = "/Game/PipelineCandidates/Achilles"
M = H + "/H2LD/Materials/"
cfg["hero"] = "Achilles"
cfg["note"] = ("3d-model-pipeline stage 7a (pilot 2026-10-14): Achilles H2LD on the canonical skeleton, M_UM_Figure_v2.1 "
               "UseTeamAccent (dye only on the leather straps and the kilt hem), teams P1/P2 of the active C-11 palette, "
               "LUT iteration 0 (look-dev run 20261014-h2-lookdev-r2 as is). Frames: P1.7 control level, pinned cobble-probe "
               "light (rev 5, Harpy b3.2 report), High, SP 100; neutral / P1 / P2 / DebugClass / plate, reading exposure "
               "-0.75 EV. Editor frames (diagnostic), not K1/K2 acceptance. Exposure anchor = wool_coarse (the red cloak, "
               "the largest zone, as the Blender ld_measure). Metal hue matters (pilot F110/F120): bronze is judged by hue "
               "and saturation against the concept, not only luminance.")
cfg["run_dir"] = run_dir
cfg["concept"] = {v: "art/imagegen/concept-achilles-codex/achilles-%s.png" % v for v in ("front", "side", "back")}
cfg["concept_zones"] = A + "/20261014-h2-lookdev-r2/reports/measure-report.json"
cfg["side_camera"] = "+X"
cfg["side_camera_note"] = "SIDE_VIEW left (asset card): on the concept side view the figure faces left -> camera at +X (Leshen precedent; Angel's -X was F98)"
cfg["variants"] = {"neutral": M + "MI_Achilles_H2LD_Neutral", "P1": M + "MI_Achilles_H2LD_P1", "P2": M + "MI_Achilles_H2LD_P2",
                   "debug": M + "MI_Achilles_H2LD_DebugClass"}
cfg["base_mi"] = {"neutral": M + "MI_Achilles_H2LD_Base", "P1": M + "MI_Achilles_H2LD_Base_P1", "P2": M + "MI_Achilles_H2LD_Base_P2",
                  "debug": M + "MI_Achilles_H2LD_Base"}
cfg["zones"] = ["wool_coarse", "linen", "bronze", "skin", "leather_smooth", "leather_worn", "wood", "legacy_bake"]
cfg["key_zones"] = ["wool_coarse"]
cfg["tolerance_zones"] = ["wool_coarse", "linen", "bronze", "skin", "leather_smooth", "leather_worn", "wood"]
cfg["never_dye_zones"] = ["wool_coarse", "bronze", "skin", "leather_worn", "wood", "legacy_bake"]
cfg["anchor_zone"] = "wool_coarse"
cfg["tolerance"] = {"luma_ratio": 0.15, "hue_deg": 12.0, "sat": 0.1, "hue_min_sat": 0.1}
cfg["render_gates"] = {"legacy_bake": {"hue_deg": [[0, 15], [340, 360]], "s_min": 0.35}}
cfg["render_gates_note"] = ("legacy_bake = the red horsehair crest and the golden curls (MatID 0, the dark catch-all that also takes "
                            "the base top); the concept median is the red crest (hue 6.3): gate = the red cloth gate of the look-dev "
                            "profile (hue 0-15 / 340-360, s >= 0.35); reported, not in tolerance_zones (class 0 decode is "
                            "unreliable against the black backdrop, F90/F131)")
cfg.pop("debug_calibration", None)
cfg.pop("debug_calibration_note", None)
cfg.pop("render_regions", None)
v = cfg["verify"]
v["skeleton"] = H + "/Rig/SK_Achilles_Skeleton"
v["folder"] = H + "/H2LD"
v["hero_root"] = H
v["clips_folder"] = H + "/H2Anim"
v["height_uu"] = height
v["expect"]["triangles"] = 43604 + 1200
v["expect"]["bones"] = 18
assert "weapon_R" in v["expect"]["bone_names"]
v["clips_reference"] = A + "/20261014-h2anim/reports/ue-measure-clips.json"
s = json.dumps(cfg, indent=1, ensure_ascii=False)
s = s.replace("/Game/PipelineCandidates/Angel/", H + "/").replace("T_Angel_H2LD_", "T_Achilles_H2LD_") \
     .replace("T_UM_MatLUT_Angel", "T_UM_MatLUT_Achilles").replace("MI_Angel_H2LD", "MI_Achilles_H2LD")
cfg = json.loads(s)
fi = cfg["verify"]["instances"]["figure_instance"]
fi["scalars"] = {"TeamDye": 1.0, "TeamDyeGain": 22.779, "TeamDyeCeiling": 8.6256}
bad = [line for line in s.splitlines() if "Angel" in line and "F98" not in line]
assert not bad, bad
open(out, "w", encoding="utf-8", newline="\n").write(json.dumps(cfg, indent=1, ensure_ascii=False) + "\n")
print(out)
