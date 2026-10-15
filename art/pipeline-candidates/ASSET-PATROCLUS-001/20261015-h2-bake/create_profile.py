"""Create a new prepare-only v2 profile from own scout and own HP measurements."""
from pathlib import Path
import hashlib
import importlib.util
import json
import sys

sys.dont_write_bytecode = True
OUT = Path(__file__).resolve().parent
REPO = OUT.parents[3]
TARGET = OUT.parent / "build-profiles/patroclus-h2-bake-h2.json"
if TARGET.exists():
    raise SystemExit("Refuse to overwrite an existing profile: " + str(TARGET))
read = lambda p: json.loads(p.read_text(encoding="utf-8"))
partial = read(OUT.parent/"20261015-h2-prep/stage3-config.proposed.json")["h2_profile_partial"]
m = read(OUT/"measurements-own-hp.json")
specpath = OUT.parent/"source-specs/tripo-e0b4d474-h2.json"
spec = read(specpath)
p = partial
p.update(profile_id="patroclus-h2-bake/1", status="предложено", history={"previous_profiles":[],"basis":"own scout plus separately measured own HP; no donor part IDs/bones/masks/caps"})
p["execution_scope"] = {"allowed_stages":["prepare"],"ready_for_all":False,"note":"This descriptive scope is not an enforced runner guard. Use run_bounded.py prepare only; later stages require separate authorization and completed LP/material/closure investigations."}
p["intake_decisions"] = {"game_role":"sidekick","asset_card_ROLE":"hero","asset_card_GAME_ROLE":"sidekick","conflict":"asset-card role fields conflict; no source/card mutation here","scale_authority":"parent explicitly adopts plume top 0.43 m and base diameter 0.24 m × height 0.05 m in this profile","figure_top_m":.43,"base_diameter_m":.24,"base_height_m":.05,"decided_by":"delegated, parent instruction 2026-10-15"}
p["sources"] = {"source_spec":str(specpath.relative_to(REPO)).replace("\\","/")}
for key, role in [("parts_glb","h2-parts-glb"),("tex_glb","h2-tex8k-pbr-glb")]:
    f = next(f for f in spec["files"] if f["role"] == role)
    path = REPO/f["path"]
    sha = hashlib.sha256(path.read_bytes()).hexdigest()
    assert sha == f["expected_sha256"] and path.stat().st_size == f["expected_bytes"]
    p["sources"][key] = {"role":role,"path":f["path"],"bytes":path.stat().st_size,"sha256":sha}
p["rig"]["bones"] = m["proposed_bones"]
p["rig"]["bones_note"] = "Own HP sections in measurements-own-hp.json. Provisional, not LP/rig acceptance. Remeasure on actual LP after retopo. Hips/spine centreline is explicit anatomical proposal; blade axis PCA and fist bounds locate initial grip."
p["rig"]["seam_radius_m"] = .001
p["rig"]["seam_pairs"] = []
p["rig"]["junctions"] = []
p["rig"]["pending"] = "No LP closure inventory or joint deformation tests yet. Empty junction/seam lists are NOT evidence of no repairs needed. Cape shell decision remains unresolved; no donor shell/cap list."
p["orientation"]["expected_inside_out_parts"] = []
p["orientation"]["note"] = "Empty before first prepare per HANDBOOK 4.2; actual negative parts must be reviewed and adopted in a NEW profile, no threshold relaxation."
p["retopo"]["cleanup"] = {"merge_distance_m":1e-6,"degenerate_distance_m":1e-7,"tiny_island_area_m2":2e-7,"degenerate_area_m2":1e-10}
p["retopo"]["caps"] = []
p["retopo"]["note"] = "Own scout starting budget 32550 figure + 1600 base. No actual LP produced; caps/shells must remain within 45000 figure/2500 base limits."
priority = p["uv"]["texel_priority"]
p["uv"]["texel_priority"] = {"default":1.0,"parts":priority,"regions":[]}
p["uv"]["charts"] = {"unwrap_method":"MINIMUM_STRETCH","normal_penalty":3.0,"max_rounds":6,"max_overlap_share":0.0,"max_stretch_log_p95":.5,"chart_area_cm2":{"default":18,"tripo_part_0":38,"tripo_part_1":120,"tripo_part_5":7,"tripo_part_8":6,"tripo_part_16":6,"tripo_part_18":6},"regions":[],"stretch_min_faces":12,"smooth_iterations":4,"note":"Unexecuted initial charts proposal for own part roles; validate on actual LP before bake."}
p["bake"] = {"device":"CPU","resolution":4096,"ao":{"samples":128,"distance_m":.0344,"seed":0,"note":"0.08 × own 0.43 m plume-top scale; unexecuted proposal"},"normal":{"space":"TANGENT","include_tripo_normal_map":True,"samples":1},"emission":{"samples":1},"cage":{"extrusion_from":"own retopo lo_to_hi and hi_to_lo p99, not yet measured","factor":1.5,"min_m":.0006,"max_m":.004,"max_ray_factor":2.5},"hit_check":{"max_miss_share_warn":.01},"ao_exclusions":[],"note":"Not run. CPU selected for later repeatability; actual cage/AO exclusions require own LP and contact measurements."}
p["textures"].update(edge_extend_px=16,maps={"BC":"sRGB RGB 8bit from own de-lit Tripo","N":"UE DirectX tangent normal","N_OpenGL":"Blender OpenGL tangent normal","ORM":"R AO / G Roughness / B Metallic","TeamMask":"legacy RG cloth/base mask; own thresholds pending"},ao_gate={"min_range_p1_p99":32,"min_occluded_fraction":.02,"occluded_below":250})
p["textures"]["pending"] = "Mixed bronze/linen/leather/hair parts require measured own masks and cloth HSV after actual BC bake. No donor metal mask or whole-part helmet-metal classification. Base lower-tier band height awaits own LP/BC measurement."
p["sockets"][1]["target_m"] = [(a+b)/2 for a,b in zip(m["parts"]["tripo_part_5"]["bounds_m"][0],m["parts"]["tripo_part_5"]["bounds_m"][1])]
p["sockets"][1]["location_uu"] = None
p["landmark_evidence"] = str((OUT/"measurements-own-hp.json").relative_to(REPO)).replace("\\","/")
p["pending_before_later_stages"] = ["HP anchors must be checked on actual LP; no rig authored.","Inspect actual LP loop/contact inventory after retopo before selecting closure, cap, junction or shell.","Test hidden sword grip continuity and part21-to-fist seam; no handle bridge implementation authorized.","Author own material and team masks from actual baked BC; mixed helmet/hair and pommel/fist must remain mixed.","Author own K2, seams, closeup and deformation frame configuration; no donor cameras or masks.","Proceed one stage at a time only after parent review; this profile is prepare-only."]
p["claims"] = {"art_accepted":False,"game_ready":False,"rig_authored":False,"lp_authored":False,"baked":False}
module = REPO/"tools/tripo-pipeline/blender/h2_bake/profile.py"
loader = importlib.util.spec_from_file_location("own_profile_schema",module)
M = importlib.util.module_from_spec(loader);loader.loader.exec_module(M)
problems = M.validate(p)
assert not problems, problems
TARGET.parent.mkdir(parents=True,exist_ok=True)
TARGET.write_text(json.dumps(p,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
print("PROFILE_VALID",str(TARGET),len(p["parts"]),len(p["rig"]["bones"]))
