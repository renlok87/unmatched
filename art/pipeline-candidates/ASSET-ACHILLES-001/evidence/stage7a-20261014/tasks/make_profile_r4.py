"""Scratch: import profile rev 4 of ASSET-ACHILLES-001 = copy of the committed rev 3 pointing at the r3 model runs.
Changes only the inputs of the r3 model (look-dev run 20261014-h2-lookdev-r3 / bake run 20261014-h2-bake-r3: rig.junctions
arm|cloak and arm|cuirass, band 0.04 m - the ragged edge behind the right armpit closed) and TeamDyeGain/Ceiling recomputed
by the LDV-13 rule from the r3 TeamAccent report. The UE look-dev LUT T_UM_MatLUT_Achilles_UE_r3 (warm bronze F0, cloth
sheen) stays: the r3 look-dev LUT and its overrides are byte-identical to r2 (the base of the UE r3 overrides).
Axes, figure_top_part, sockets, base footprint, expectations and texture settings carry over (asserted unchanged).
    python make_profile_r4.py <out.json>
"""
import hashlib
import json
import sys
from pathlib import Path

REPO = Path("C:/Users/ren/WebstormProjects/unmached/unmached")
A = "art/pipeline-candidates/ASSET-ACHILLES-001"
R3 = REPO / A / "build-profiles/achilles-h2ld-lookdev-ue-import-r3.json"
LD = A + "/20261014-h2-lookdev-r3"
LD2 = A + "/20261014-h2-lookdev-r2"
BK = A + "/20261014-h2-bake-r3"


def sha(p):
    return hashlib.sha256((REPO / p).read_bytes()).hexdigest()


p = json.loads(R3.read_text(encoding="utf-8"))
ta = json.loads((REPO / LD / "reports/ld-team-accent-report.json").read_text(encoding="utf-8"))["team_dye_gain"]
fbx = json.loads((REPO / LD / "reports/ld-fbx-report.json").read_text(encoding="utf-8"))
prep = json.loads((REPO / BK / "reports/prepare-report.json").read_text(encoding="utf-8"))
rig = json.loads((REPO / BK / "reports/rig-report.json").read_text(encoding="utf-8"))
man = json.loads((REPO / LD / "reports/run-manifest.json").read_text(encoding="utf-8"))
y50, y95 = ta["accent_Y_p50_p95"]
gain = round(0.8 / y50, 3)
ceil = round(0.9 / y95, 4)
assert abs(gain - ta["gain_for_median"]) < 0.01, (gain, ta["gain_for_median"])
crest_top = prep["parts"]["tripo_part_6"]["final_bounds_m"][1][2]
assert abs(crest_top - 0.55) < 1e-6, crest_top
tris = fbx["checks"]["triangles_as_h21"]["measured"]
assert tris == p["expectations"]["triangles"], tris
base_b = rig["expected_ue_bounds_uu_at_import_scale_1"]["base"]
assert base_b == {"max": [14.971, 14.971, 5.805], "min": [-14.997, -14.999, 0.003]}, base_b
assert man["profile"]["profile_id"] == "achilles-h2-lookdev/4", man["profile"]
# the UE r3 LUT was built on the r2 look-dev LUT: valid only if the r3 look-dev LUT is the same bytes
for f in ("textures/T_UM_MatLUT_Achilles.dds", "textures/T_UM_MatLUT_Achilles.overrides.json",
          "textures/T_Achilles_H2LD_TeamAccent_2K.png"):
    assert sha(LD + "/" + f) == sha(LD2 + "/" + f), f
lut = p["candidate"]["library_inputs"]["LUT"]
assert lut["path"].endswith("T_UM_MatLUT_Achilles_UE_r3.dds") and lut["sha256"] == sha(lut["path"]), lut

p["profile_id"] = "achilles-h2ld-lookdev-ue-import/4"
p["status_note"] += (
    " Rev 4 (2026-10-14, model r3): the inputs move to the r3 model - look-dev run 20261014-h2-lookdev-r3 (profile "
    "achilles-h2-lookdev/4) of bake run 20261014-h2-bake-r3 (achilles-h2-bake/4: rig.junctions arm|cloak and "
    "arm|cuirass, band 0.04 m - the ragged edge behind the right armpit closed by junction weights). Model acceptance r3: "
    "evidence/acceptance/20261014-r3 (pair Sol 8.1 + Opus 8.8 -> 8.1 pass). The UE look-dev LUT T_UM_MatLUT_Achilles_UE_r3 "
    "(warm bronze F0, cloth sheen) stays: the r3 look-dev LUT, its overrides and the TeamAccent map are byte-identical to "
    "r2. TeamDyeGain / TeamDyeCeiling by the same LDV-13 rule from the r3 TeamAccent report (0.8 / Y_p50 %.5f = %.3f, "
    "0.9 / Y_p95 %.5f = %.4f; unchanged). Axes, figure_top_part, sockets, base footprint and texture settings carry over "
    "from rev 3. Re-import by references/ue-import-package.md 4.4 (assets of 20261014-h2ld-ue-import-r3 deleted by "
    "script) into run 20261014-h2ld-ue-import-r4." % (y50, gain, y95, ceil))
p["derived_from"] = [
    "art/pipeline-candidates/ASSET-ACHILLES-001/build-profiles/achilles-h2ld-lookdev-ue-import-r3.json "
    "(rev 3; everything but the r3 inputs and TeamDyeGain/Ceiling)"] + [
    d.replace("achilles-h2-bake-h2-r2.json", "achilles-h2-bake-h2-r3.json")
     .replace("achilles-h2-lookdev-r2.json", "achilles-h2-lookdev-r3.json")
     .replace("achilles-h2-lookdev-teamaccent-r2.json", "achilles-h2-lookdev-teamaccent-r3.json")
     .replace("(TeamAccent /3)", "(TeamAccent /4)")
    for d in p["derived_from"]]
c = p["candidate"]
c["dir"] = LD
c["bake_profile"] = A + "/build-profiles/achilles-h2-lookdev-r3.json"
c["bake_profile_id"] = "achilles-h2-lookdev/4"
c["extra_reports"] = {"run_manifest": "reports/run-manifest.json",
                      "source_rig_report": "../20261014-h2-bake-r3/reports/rig-report.json",
                      "source_textures_report": "../20261014-h2-bake-r3/reports/textures-report.json"}
tam = LD + "/textures/T_Achilles_H2LD_TeamAccent_2K.png"
c["library_inputs"]["TeamAccent"]["path"] = tam
c["library_inputs"]["TeamAccent"]["sha256"] = sha(tam)
c["library_inputs"]["LUT"]["note"] += ("; rev 4: kept - the r3 look-dev LUT (ld-maps-report lut.dds_sha256 11ce2c14...) "
                                       "and its overrides are byte-identical to r2, the base of the UE r3 overrides")
c["figure_top_part_note"] = c["figure_top_part_note"].replace("20261014-h2-bake-r2", "20261014-h2-bake-r3")
p["meshes"]["base"]["footprint_note"] = p["meshes"]["base"]["footprint_note"].replace("H2 bake r2", "H2 bake r2/r3")
ue = p["ue"]
ue["figure_parameters"]["TeamDyeGain"] = gain
ue["figure_parameters"]["TeamDyeCeiling"] = ceil
ue["figure_parameters_note"] = ue["figure_parameters_note"].replace(
    "20261014-h2-lookdev-r2/reports/ld-team-accent-report.json",
    "20261014-h2-lookdev-r3/reports/ld-team-accent-report.json; rev 4 recomputed, unchanged against r2")
p["history"] = {"previous": {"path": str(R3.relative_to(REPO)).replace("\\", "/"), "sha256": sha(R3.relative_to(REPO)),
                             "run": A + "/20261014-h2ld-ue-import-r3"}}
s = json.dumps(p, ensure_ascii=False, indent=2)
left = [ln for ln in s.splitlines() if ("-r2" in ln and "Rev 2" not in ln and "ue-import-r2" not in ln
                                        and "UE_r2" not in ln and "byte-identical to r2" not in ln
                                        and "H2 bake r2/r3" not in ln and "Rev 3" not in ln)]
assert not left, left
out = Path(sys.argv[1])
out.write_text(s + "\n", encoding="utf-8", newline="\n")
print("wrote", out, "gain", gain, "ceil", ceil, "lut", lut["sha256"][:8], "ta", c["library_inputs"]["TeamAccent"]["sha256"][:8])
