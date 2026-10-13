"""Write the Achilles UE import profile (stage 7a) from the Angel r3 template with Achilles values.

    python write_import_profile.py <out json> [lut path] [lut sha256] [rev note] [profile_id] [previous path] [previous sha] [previous run] [extra figure params json]
"""
import json
import sys

REPO = "C:/Users/ren/WebstormProjects/unmached/unmached"
src = REPO + "/art/pipeline-candidates/ASSET-ANGEL-001/build-profiles/angel-h2ld-lookdev-ue-import-r3.json"
p = json.load(open(src, encoding="utf-8"))
A = "art/pipeline-candidates/ASSET-ACHILLES-001"
LD = A + "/20261014-h2-lookdev-r2"
out = sys.argv[1]
lut_path = sys.argv[2] if len(sys.argv) > 2 else LD + "/textures/T_UM_MatLUT_Achilles.dds"
lut_sha = sys.argv[3] if len(sys.argv) > 3 else "11ce2c149866870683a4be481c2ff54ec70d744fb266cd1fd76813aeb573b57b"
rev_note = sys.argv[4] if len(sys.argv) > 4 else ""
profile_id = sys.argv[5] if len(sys.argv) > 5 else "achilles-h2ld-lookdev-ue-import/1"
prev = sys.argv[6:9] if len(sys.argv) > 8 else None
extra_params = json.loads(sys.argv[9]) if len(sys.argv) > 9 else {}

p["profile_id"] = profile_id
p["asset_id"] = "ASSET-ACHILLES-001"
p["status"] = "proposed"
p["status_note"] = (
    "3d-model-pipeline stage 7a (pilot 2026-10-14): UE import of the Achilles look-dev run 20261014-h2-lookdev-r2 "
    "(profile achilles-h2-lookdev/3: generic h2_bake H2 figure of the bake run 20261014-h2-bake-r2 + UV1 in metres, "
    "MatID, Edge, graded BC/ORM; TeamAccent of profile achilles-h2-lookdev-teamaccent/3 = sword-belt/pteruges leather "
    "1.47 % + kilt hem 0.61 % = 2.23 % of the figure, below the 5-12 % range under P3-4/P3-4b) through the CLI profile "
    "skeletal-adopt (normaliser h2-lookdev/1) onto the canonical skeleton "
    "/Game/PipelineCandidates/Achilles/Rig/SK_Achilles_Skeleton. Spear in the RIGHT hand (weapon.R, UE weapon side +Y "
    "as King Arthur and Angel); the round shield on the left forearm is part of the body mesh (rigid on arm_lower.L, no "
    "bone). MI of /Game/UM/Materials/v2/M_UM_Figure_v2 (UseTeamAccent, UseUV1Metres) with the TeamAccent mask and the "
    "look-dev LUT as is (UE look-dev iteration 0); base on M_UM_BaseMarker. Teams = the active C-11 palette P1 #E8C06A / "
    "P2 #5A7F9F (user decision 'accents + ring'). At most 'technically imported'; art acceptance of the model by "
    "delegation (stage 4 r2 pass 8.8, evidence/acceptance/20261014-r2/card.json)." + rev_note)
p["derived_from"] = [
    "art/pipeline-candidates/ASSET-ANGEL-001/build-profiles/angel-h2ld-lookdev-ue-import-r3.json (skeletal-adopt h2-lookdev/1 of the pilot, weapon.R right hand, candidate.figure_top_part, M_UM_Figure_v2.1 UseTeamAccent)",
    "art/pipeline-candidates/ASSET-ANCIENT-LESHEN-001/build-profiles/ancient-leshen-h2ld-lookdev-ue-import-r4.json (base footprint from the rig report's expected UE bounds)",
    "art/pipeline-candidates/ASSET-MEDUSA-001/build-profiles/medusa-h2ld-lookdev-ue-import.json (skeletal-adopt, normaliser h2-lookdev/1, M_UM_Figure_v2.1)",
    "art/pipeline-candidates/ASSET-KING-ARTHUR-001/build-profiles/king-arthur-h2ld-lookdev-ue-import.json (weapon in the right hand: weapon.R, UE weapon side +Y)",
    "art/pipeline-candidates/ASSET-ACHILLES-001/build-profiles/achilles-h2-bake-h2-r2.json (armature, scale, axes, sockets, atlas slot M_Achilles_H2_Atlas)",
    "art/pipeline-candidates/ASSET-ACHILLES-001/build-profiles/achilles-h2-lookdev-r2.json (look-dev run: MatID classes, LUT, UV1)",
    "art/pipeline-candidates/ASSET-ACHILLES-001/build-profiles/achilles-h2-lookdev-teamaccent-r2.json (TeamAccent /3)",
    "docs/art-pipeline/material-library/team-accent.md §1 (LDV-13: TeamDyeGain 0.8 / Y_p50, TeamDyeCeiling 0.9 / Y_p95) and section Achilles",
]
c = p["candidate"]
c["dir"] = LD
c["bake_profile"] = A + "/build-profiles/achilles-h2-lookdev-r2.json"
c["bake_profile_id"] = "achilles-h2-lookdev/3"
c["extra_reports"] = {"run_manifest": "reports/run-manifest.json",
                      "source_rig_report": "../20261014-h2-bake-r2/reports/rig-report.json",
                      "source_textures_report": "../20261014-h2-bake-r2/reports/textures-report.json"}
c["fbx"] = {"skeletal": "export/SK_Achilles_H2LD.fbx", "base": "export/SM_Achilles_H2LD_Base.fbx"}
c["textures"] = {k: "textures/T_Achilles_H2LD_2K_%s.png" % k for k in ("BC", "N", "ORM", "TeamMask", "MatID", "Edge")}
c["library_inputs"] = {
    "LUT": {"path": lut_path, "sha256": lut_sha,
            "note": "look-dev LUT as is (UE look-dev iteration 0; ld-maps-report lut)" if lut_path.endswith("T_UM_MatLUT_Achilles.dds")
            else "UE look-dev iteration (ue_hero_lookdev.py lut --overrides %s)" % lut_path.replace(".dds", ".overrides.json")},
    "TeamAccent": {"path": LD + "/textures/T_Achilles_H2LD_TeamAccent_2K.png",
                   "sha256": "05ac5d86348fe1406a2aa95361a3d30d7a3dba0268b26154847c61689aa4b3f5",
                   "note": "TeamAccent L8 linear 2048^2 (ld-team-accent-report.json outputs): sword-belt and pteruges leather (leather_smooth) 1.47 % + kilt hem (linen) 0.61 % = 2.23 % of the figure"}}
c["top_part"] = "tripo_part_6"
c["figure_top_part"] = "tripo_part_6"
c["figure_top_part_note"] = (
    "pilot fix F80 (cd3ee7fe; skeletal_adopt_formats.h2_lookdev): the figure top for figure_height_as_profile = the final "
    "top of the helmet crest tripo_part_6 in ../20261014-h2-bake-r2/reports/prepare-report.json (0.55 m; the rig-report "
    "skeletal top 54.993 uu is the crest too), not the spear tip (tripo_part_10, 0.5375 m, lower than the crest)")
p["armature"]["bones_note"] = ("UM_HUMANOID_17_v2: 16 body bones + weapon.R (spear, right hand; rig-contract characters.Achilles "
                               "weapon_bone weapon.R). In UE the armature object SKEL_UM_Humanoid becomes bone 0 (18 bones), "
                               "'.' becomes '_' (weapon_R)")
assert p["armature"]["bones"][-1] == ["weapon.R", "hand.R"]
p["scale"] = {"figure_height_m": 0.55, "top_part": "tripo_part_6",
              "note": "base bottom -> top of the helmet crest (tripo_part_6 final top 0.550 m, prepare-report) = hero budget 55 uu (asset card FIGURE_HEIGHT_M); the spear tip (tripo_part_10, 0.5375 m) is lower and not part of the height (HANDBOOK §2.10)"}
p["meshes"] = {
    "body": {"object": "SK_Achilles_H2_Body"},
    "weapon": {"object": "SK_Achilles_H2_Spear", "bone": "weapon.R"},
    "base": {"object": "SM_Achilles_H2_Base", "footprint_m": [0.29968, 0.2997, 0.05805], "pivot": "centre of the base bottom",
             "footprint_note": "rig-report expected_ue_bounds_uu_at_import_scale_1.base [-14.997, -14.999, 0.003] .. [14.971, 14.971, 5.805] uu (the H2 bake r2 base top is 5.805 uu, not the 6.0 of card 04; base_footprint_pivot compares with 0.05 uu tolerance)"}}
p["axes"] = {"blender_front": "-Y", "blender_weapon_side": "-X", "expected_ue_front": "+X", "expected_ue_weapon_side": "+Y",
             "expected_ue_front_source": "UM_FBX_v1 preset (ART-001); ld_fbx measured the face normal (0.6676, -0.0056, -0.0241) along +X in the export frame; right-handed spear on Blender -X -> UE +Y as King Arthur and Angel"}
p["sockets"] = [
    {"name": "Weapon", "bone": "weapon.R", "location_uu": [0, 0, 0],
     "purpose": "rig-contract §7: Weapon on the weapon bone at (0,0,0) = the spear grip (rig-report target UE component (7.16, 9.52, 33.7) uu)"},
    {"name": "Head", "bone": "head", "location_uu": None,
     "purpose": "damage / status VFX and the evidence capture (S08FlowGameMode DoesSocketExist Head); location = the H2 bake's UE bone-space prediction (rig-report sockets: head centre under the helmet, offset (0, -4.803, 0.097) uu)"}]
p["expectations"] = {"triangles": {"SK_Achilles_H2_Body": 43604, "SK_Achilles_H2_Spear": 1200, "SM_Achilles_H2_Base": 1348},
                     "bones": 17, "skeletal_material_slots": 1, "base_material_slots": 1, "skeletal_lods": 1,
                     "note": "numbers of the look-dev read-back (ld-fbx-report triangles_as_h21); the FBX carries LOD0 only"}
p["proposed_limits_for_comparison_only"]["source"] = "GD-058 final (asset-card POLY_BUDGET: figure <= 45 000 tris, base <= 2 500), FIGURE_HEIGHT_RANGE_M [0.52, 0.56]; comparison only"
p["proposed_limits_for_comparison_only"]["height_uu"] = [52, 56]
u = p["ue"]
for k in list(u.keys()):
    if isinstance(u[k], str):
        u[k] = u[k].replace("Angel", "Achilles")
    elif isinstance(u[k], dict) and k == "team_instances":
        u[k] = {kk: vv.replace("Angel", "Achilles") for kk, vv in u[k].items()}
u["target_skeleton_note"] = "canonical hero skeleton of H2Anim (h2anim_ue.py skeleton from SK_Achilles_H2.fbx of the spec achilles-h2anim.json); the clips AM_Achilles_* are on it; the run neither creates nor deletes it"
u["team_color_mode_note"] = "v2.1: dye by TeamAccentTexture (UseTeamAccent = true), TeamMaskTexture = T_UM_Mask_Black; the red cloak (wool_coarse), the kilt cloth core (linen), bronze, skin, hair/crest, the spear shaft and the stone base (main colours of the concept) are never dyed, only the leather straps and the kilt hem"
gain = round(0.8 / 0.03512, 3)
ceil = round(0.9 / 0.10434, 4)
u["figure_parameters"] = dict({"TeamDye": 1.0, "TeamDyeGain": gain, "TeamDyeCeiling": ceil}, **extra_params)
u["figure_parameters_note"] = (
    "team-accent.md rule LDV-13, one MI for both teams: TeamDyeGain = 0.8 / Y_p50 (0.03512), TeamDyeCeiling = 0.9 / Y_p95 "
    "(0.10434) of the accent texels (20261014-h2-lookdev-r2/reports/ld-team-accent-report.json "
    "team_dye_gain.accent_Y_p50_p95; the report's own single-gain rule gives 10.5); effective min(%.3f, %.4f / maxc(team)) "
    "= P1 %.2f, P2 %.2f" % (gain, ceil, min(gain, ceil / 0.807), min(gain, ceil / 0.3467)))
if extra_params:
    u["figure_parameters_note"] += "; extra: " + json.dumps(extra_params)
for e in u["extra_instances"]:
    e["asset"] = e["asset"].replace("Angel", "Achilles")
for t in u["textures"].values():
    t["asset"] = t["asset"].replace("Angel", "Achilles")
p.pop("history", None)
if prev:
    p["history"] = {"previous": {"path": prev[0], "sha256": prev[1], "run": prev[2]}}
s = json.dumps(p, indent=2, ensure_ascii=False)
bad = [line for line in s.splitlines() if "Angel" in line and "ASSET-ANGEL-001" not in line and "King Arthur and Angel" not in line]
assert not bad, bad
open(out, "w", encoding="utf-8", newline="\n").write(s + "\n")
print(out, gain, ceil)
