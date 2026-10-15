"""Freeze prep-only findings from personally viewed real renders and measured source."""
import hashlib
import json
from pathlib import Path

OUT = Path(__file__).resolve().parent
REPO = OUT.parents[3]

def read(p):
    return json.loads(p.read_text(encoding="utf-8"))

def write(name, value):
    (OUT/name).write_text(json.dumps(value, indent=2, ensure_ascii=False)+"\n",encoding="utf-8")

def pin(p):
    p = Path(p)
    if not p.is_absolute():
        p=REPO/p
    with p.open("rb") as f:
        h=hashlib.file_digest(f,"sha256").hexdigest()
    return {"path":p.relative_to(REPO).as_posix(),"bytes":p.stat().st_size,"sha256":h}

inv=read(OUT/"source-inventory.json")
measurement=read(OUT/"measurements.json")
# Compact the first scout's measured output without rerendering or changing any measurement.
# Its process record pins the original script. Current scout_details.py reproduces this compact representation.
if "raw_hp_loop_counts_ge_5mm" not in measurement:
    measurement["raw_hp_loop_counts_ge_5mm"]={n:len(rows) for n,rows in measurement["boundary_inventory_raw_hp"].items()}
    measurement["boundary_inventory_raw_hp"]={n:[{k:v for k,v in row.items() if k not in ("co","verts","points")} for row in rows[:8]] for n,rows in measurement["boundary_inventory_raw_hp"].items()}
    measurement["boundary_note"]="Existing st_close.loop_rows on raw imported HP in proposed scale; largest 8 rows per part retained, full counts separate. NOT retopologized LP, NOT a cap selection list: raw topology contains many small fragmented boundaries. Must repeat after real prepare/retopo with textured geometry identity proven. No caps made."
    measurement["postprocess"]="prepare_handoff.py retained existing measured scalars and largest 8 rows per part; removed bulky coordinates and vertex indexes. No measurements recalculated."
    write("measurements.json",measurement)

# Roles below are visual observations from the contact pages and targeted context renders.
roles=[
 ("cape and shoulder drape with clasp", "body", "both", "high", "cloth", "Cape incorporates the shoulder clasp. Thickness/inside opening differs by region; do not assume a uniform sheet."),
 ("two-tier circular pedestal with foot contact cutouts", "base", None, "high", "static", "Visible top cutouts need the LP/base see-through checks; no claim that base is already watertight."),
 ("round shield, decorated face and rear shell", "body", "L", "high", "shield", "Own-left arm; rear grip openings need checking in the shield/hand/forearm group."),
 ("linen corslet front with diagonal strap, belt, hanging tabs and side scabbard/strap forms", "body", "both", "high", "torso", "Mixed linen/leather/bronze; back is cut away under cape. Not a solid torso volume."),
 ("helmet plume / crest", "body", None, "high", "head", "Plume is NOT the face. Upper attached headgear establishes proposed figure top."),
 ("face, ears and neck surface", "body", None, "high", "neck", "Separate open surface under helmet/hair; this is the required name=face dense region part."),
 ("helmet and hair shell", "body", None, "high", "head", "Helmet and hair share this part; do not label the entire mesh bronze."),
 ("own-right greave, sandal and lower leg", "body", "R", "high", "legR", "Toes split to part 23; mixed skin/bronze/leather."),
 ("short sword blade and guard", "weapon", "R", "high", "weapon", "Only mesh=weapon part; blade enters the fist at a contact cut. Does not prove an internal continuous handle."),
 ("own-right bracer / forearm shell", "body", "R", "high", "armR", "Use same positional chain as upper arm and fist, not a separately guessed rigid bracer."),
 ("own-left exposed thigh and knee", "body", "L", "high", "legL", "From skirt to greave."),
 ("own-left bracer / forearm shell behind shield", "body", "L", "high", "armL", "Shares cut surfaces with shield/upper arm; inspect rider gap and posed seams."),
 ("own-left greave, sandal and lower leg", "body", "L", "high", "legL", "Toes split to part 22; mixed skin/bronze/leather."),
 ("lower pleated linen tunic / skirt hem", "body", "both", "high", "cloth", "Open upper/contact regions; cape and skirt shell choices are not decided by appearance alone."),
 ("own-right exposed thigh and knee", "body", "R", "high", "legR", "From skirt to greave."),
 ("own-right upper arm and exposed elbow region", "body", "R", "high", "armR", "Shoulder saddle under cape is a candidate for a measured junction or contact cap."),
 ("own-right fist around sword grip", "body", "R", "high", "armR", "Blade/guard and pommel bracket this fist. Needs grip checks after actual rig."),
 ("own-left upper arm and exposed elbow region", "body", "L", "high", "armL", "Own-left shoulder under cape."),
 ("own-left hand at rear shield grip", "body", "L", "high", "armL", "Visible palm/fingers in left-shield-grip.png; not another weapon mesh."),
 ("own-left small tunic waist/flank panel beneath belt", "body", "L", "medium", "torso", "Orange context render confirms location under belt. Exact textile/leather class remains unproven before PBR."),
 ("own-right small tunic waist/flank panel beneath belt", "body", "R", "medium", "torso", "Orange context render confirms location under belt. Exact textile/leather class remains unproven before PBR."),
 ("sword pommel with adjoining hand/grip surface fragment", "body", "R", "high", "pommel", "The sphere is the pommel; attached irregular patch is NOT pure metal. Check split across hand before choosing final rigid assignment."),
 ("own-left exposed toes", "body", "L", "high", "legL", "Matches opening in part 12 sandal."),
 ("own-right exposed toes", "body", "R", "high", "legR", "Matches opening in part 7 sandal."),
]
targets=[5000,1600,2600,3500,2000,3500,2300,1600,1200,650,700,650,1600,2200,700,1000,700,950,700,200,200,200,200,200]
role_map={}
weights={}
for i,(role,mesh,side,confidence,weight_kind,note) in enumerate(roles):
    n=f"tripo_part_{i}"
    refs=[f"renders/{n}-front34.png",f"renders/{n}-back34.png","assembled-context.png"]
    if i in (19,20,21): refs.append(f"details/{n}-context.png")
    if i in (8,16,21): refs.append("details/sword-grip-isolated.png")
    if i in (2,11,17,18): refs.append("details/left-shield-grip.png")
    role_map[n]={"role":role,"mesh":mesh,"own_side":side,"visual_confidence":confidence,
                 "source_triangles":inv["parts"][n]["triangles"],"proposed_target_tris":targets[i],
                 "visual_evidence":refs,"uncertainty_or_next_check":note}
    if weight_kind=="static": continue
    if weight_kind in ("armL","armR"):
        s=weight_kind[-1]; rule={"kind":"chain","chain":["spine",f"arm_upper.{s}",f"arm_lower.{s}",f"hand.{s}"],"bands_m":[0.010,0.012,0.007]}
    elif weight_kind in ("legL","legR"):
        s=weight_kind[-1]; rule={"kind":"chain","chain":["hips",f"leg_upper.{s}",f"leg_lower.{s}",f"foot.{s}"],"bands_m":[0.012,0.010,0.008]}
    elif weight_kind=="cloth":
        rule={"kind":"cloth","base_bone":"hips","top_bone":"spine","top_blend_z":[0.22,0.25],"legs":{"L":"leg_upper.L","R":"leg_upper.R"},"leg_start_z":0.20,"leg_full_z":0.10 if i==0 else 0.18,"leg_max":0.40,"side_band_m":0.016}
    elif weight_kind=="torso":
        rule={"kind":"cloth","base_bone":"hips","top_bone":"spine","top_blend_z":[0.235,0.265],"legs":{"L":"leg_upper.L","R":"leg_upper.R"},"leg_start_z":0.21,"leg_full_z":0.18,"leg_max":0.35,"side_band_m":0.016}
    elif weight_kind=="neck": rule={"kind":"zblend","stops":[["spine",0.327],["head",0.343]]}
    else: rule={"kind":"rigid","bone":{"head":"head","weapon":"weapon.R","shield":"arm_lower.L","pommel":"weapon.R"}[weight_kind]}
    weights[n]=rule
parts_cfg={n:{"mesh":r["mesh"],"role":r["role"],**({"cloth":True} if i in (0,13) else {})} for i,(n,r) in enumerate(role_map.items())}
figure_target=sum(t for i,t in enumerate(targets) if i!=1)
write("part-role-map.json",{"schema":"patroclus.h2-prep-part-role-map/1","asset_id":"ASSET-PATROCLUS-001","source_sha256":inv["source"]["sha256_before"],"method":"Personally viewed every isolated front34/back34 pair, assembled-context and all five focused detail renders; geometric bounds used only after visual classification.","viewed_by":"Codex assembly scout in this session","side_convention":"Blender front -Y, own-left +X, own-right -X; visually confirmed sword and shield placement", "parts":role_map,"claims":{"art_acceptance":False,"finished_geometry":False,"finished_rig":False}})

partial={"schema":"unmatched.h2-bake-profile/1","profile_version":2,"profile_id":"patroclus-h2-bake/prep-unadopted","asset_id":"ASSET-PATROCLUS-001","status":"предложено","expected_part_count":24,
 "sources":{"parts_glb":{"role":"h2-parts-glb",**pin(inv["source"]["path"])}},
 "parts":parts_cfg,"scale":measurement["scale_proposal"],
 "orientation":{"method":"ray-escape","samples_per_part":4000,"seed":0,"flip_below_score":-0.5,"expected_inside_out_parts":[],"min_score_after_fix":0.5},
 "retopo":{"method":"decimate-collapse","seed":0,"deviation_samples":40000,"target_tris":{f"tripo_part_{i}":t for i,t in enumerate(targets)},"dense_regions":[{"part":"tripo_part_5","name":"face","box_m":[[-0.024,-0.024,0.338],[0.021,0.005,0.374]],"target_tris":1600,"note":"Proposed front facial subregion inside actual measured face bounds; verify eyes/nose/mouth after LP."}],"cleanup":{"merge_distance_m":1e-6,"degenerate_distance_m":1e-7,"tiny_island_area_m2":2e-7,"degenerate_area_m2":1e-10}},
 "uv":{"atlas_px":4096,"runtime_px":2048,"min_gap_px":8,"pack_margin_fraction":0.0013,"max_overlap_px":0,"density_reference_part":"tripo_part_3","texel_priority":{f"tripo_part_{i}":(2.0 if i==5 else 1.75 if i in (16,18) else 1.5 if i in (8,21) else 0.45 if i==1 else 1.0) for i in range(24)}},
 "rig":{"skeleton":"UM_HUMANOID_17_v2","armature_object":"SKEL_UM_Humanoid","character":"Patroclus","weapon_bone":"weapon.R","max_influences":4,"clean_below":0.01,"weights":weights},
 "textures":{"prefix":"T_Patroclus_H2","team_mask":{"cloth_parts":["tripo_part_0","tripo_part_13"],"base_band":{"part":"tripo_part_1","normal_z_abs_max":0.35}}},
 "sockets":[{"name":"Weapon","bone":"weapon.R","target":"bone_head","location_uu":[0,0,0]},{"name":"Head","bone":"head","target_m":[0.0,0.002,0.356],"location_uu":None}],
 "exports":{"fbx_preset":"blender/_tools/presets/UM_FBX_v1.json","skeletal_fbx":"SK_Patroclus_H2.fbx","base_fbx":"SM_Patroclus_H2_Base.fbx"},
 "meshes":{"body":"SK_Patroclus_H2_Body","weapon":"SK_Patroclus_H2_Sword","base":"SM_Patroclus_H2_Base"},"materials":{"atlas":"M_Patroclus_H2_Atlas"},
 "axes":{"blender_front":"-Y","expected_ue_front":"+X","own_right_weapon_side":"-X"},
 "preview":{"frame":{"checks_report":"art/imagegen/concept-patroclus-codex/checks-report.json","side":"right"},"concepts":{"front":"art/imagegen/concept-patroclus-codex/patroclus-front.png","side":"art/imagegen/concept-patroclus-codex/patroclus-side.png","back":"art/imagegen/concept-patroclus-codex/patroclus-back.png"}}}
pending=["Parent completes stage-2 texture8K + de-lighting + PBR export and source-spec. No polling or placeholder textured GLB.","Parent registers Patroclus with weapon.R in rig-contract characters before stage-3 execution; no new bones. None registered here.","Adopt and record sidekick height/base in asset card (proposed 0.43m plume top, base 0.24 x 0.05m); current asset card has ROLE hero but GAME_ROLE sidekick.","Prove actual parts/textured GLB identity in real prepare. Proposed sources intentionally lacks tex_glb/source_spec.","Write rig.bones from this figure's LP sections/contact centres. Proposed weight bands/stops and socket target are untested starting values, not verified rig measurements.","Run LP boundary inventory after prepare/retopo: raw HP fragmented boundaries are diagnostic only. Populate closure.contact_caps, junctions, seam_pairs and cloth_shell only after measuring loops, wall thickness and rest visibility.","Set UV chart areas (face/hand/blade priority) and closure configuration from own LP; donor chart regions and cap lists must not be copied.","Complete bake block/device, texture maps/AO gates/cloth HSV/metal masks and all remaining profile fields. Masks must separate skin, hair, linen, leather, bronze and steel within mixed parts.","Measure base lower-tier band interval (do not copy Beowulf's 0.003..0.029m); check flatten_bottom/rim_smooth only if actual defect requires it.","Complete preview/closeup/seams cameras from Patroclus geometry; keep preview.frame right in bake AND lookdev. Omit Medusa baseline/previous_candidate.","Part21 contains pommel AND co-segmented hand surface: proposed rigid weapon.R matches split-weapon precedent but must pass grip/seam probe with fist16; consider measured junction to same arm chain if the hand patch stretches.","Shield2 rigid arm_lower.L is proposed; measure rear hand18/forearm11 contact, rest rider gap, poses. Use prepare.part_offsets_m only if an actual detached rigid gap is proven.","Material and TeamAccent class masks/coverage must be measured on final BC; blue cape, linen corslet and white plume retain concept identity. Prefer hem/ribbon accents; do not inherit Achilles's lowered area threshold without own measurement.","After real model passes: stage6 weapon.extra_parts includes pommel21 on weapon.R and shield2 on arm_lower.L with islands=true; author/test clips later."]
write("stage3-config.proposed.json",{"schema":"patroclus.h2-prep-config-proposal/1","ready_for_h2_runner":False,"do_not_execute":"This envelope and its partial profile are deliberately incomplete. No final bake authorized in this scout.","source_sha256":inv["source"]["sha256_before"],"h2_profile_partial":partial,"proposed_intake":{"CHARACTER":"Patroclus","FIGHTER_NAME":"Patroclus","GAME_ROLE":"sidekick","OWNER_HERO_SLUG":"achilles","FIGURE_HEIGHT_M":0.43,"FIGURE_HEIGHT_RANGE_M":[0.396,0.462],"WEAPON_HAND":"right","SIDE_VIEW":"right","base_diameter_m":0.24,"base_height_m":0.05,"status":"UNADOPTED proposal; parent owns card/registry decisions"},"budget":{"card_limit_figure_tris":45000,"card_limit_base_tris":2500,"proposed_raw_figure_target_tris":figure_target,"proposed_base_target_tris":targets[1],"headroom_before_caps_shells":45000-figure_target,"counting_rule":"final exported body + weapon includes caps, doubled shell faces and rim bridges; base counted separately","final_mesh_triangles":None},"pending_before_run":pending})

donors=[
 ("Achilles", "art/pipeline-candidates/ASSET-ACHILLES-001/build-profiles/achilles-h2-bake-h2-r3.json",["Right weapon.R / own-left shield on arm_lower.L without new shield bone","Split weapon: one mesh weapon, remaining fragments body rigid weapon.R","Position-based identical limb chains across separate upper arm/bracer/fist parts","rig.junctions pattern for shoulder cuts opening during forward arm poses","Do not copy exact cape caps, weights bands, part numbers or 0.55/0.30/0.06 hero scale"]),
 ("Beowulf", "art/pipeline-candidates/ASSET-BEOWULF-001/build-profiles/beowulf-h2-bake-h2-t4.json",["Current profile_version 2, explicit face/density reference/base-band part and preview.frame","Right sword and separate left shield precedent, neck/collar seam checks","Separate material classes inside mixed geometry, measured base_band.height_m","v2 backside-only cap check and shell face tagging; do not blindly copy cloth_shell list","Do not inherit exact tunic/collar cut treatment or metallic colour thresholds"]),
 ("Merlin", "art/pipeline-candidates/ASSET-MERLIN-001/build-profiles/merlin-segmented-skeletal-h2.json",["Sidekick base_footprint_m 0.24,0.24,0.05; hood top 0.45m is helper scale precedent","weapon.R under hand.R; grip point derived from real contact loops","Source/textured identity and seam inventory discipline","Legacy driver/schema, Smart UV and custom assembly are historical; use current generic h2_bake instead"]),
]
write("recipe-reuse.json",{"schema":"patroclus.h2-prep-recipe-reuse/1","donors":[{"character":n,**pin(p),"reusable_patterns_and_limits":notes} for n,p,notes in donors],"current_generic_tools":[pin(p) for p in ["tools/tripo-pipeline/blender/h2_bake/run_h2_bake.py","tools/tripo-pipeline/blender/h2_bake/profile.py","tools/tripo-pipeline/blender/h2_bake/st_prepare.py","tools/tripo-pipeline/blender/h2_bake/st_close.py","tools/tripo-pipeline/blender/h2_bake/st_rig.py","tools/tripo-pipeline/blender/h2_bake/bl_util.py"]]})

processes=[read(OUT/"process-record.json"),read(OUT/"details-process-record.json")]
assert all(p["exit_code"]==0 and p["child_reaped"] for p in processes)
source_pin=pin(inv["source"]["path"])
assert source_pin["sha256"]==inv["source"]["sha256_before"]
card=read(REPO/inv["acceptance_card"]["path"])
assert card["score"]==9.4 and card["verdict"]=="pass"
for x in card["accepted_object"]:
    assert pin(x["path"])["sha256"]==x["sha256"]
write("verification.json",{"scope":"prep only; no model art acceptance","source":source_pin,"source_unchanged":True,"all_3_accepted_concept_hashes_match":True,"part_count":24,"source_triangles":1967447,"isolated_render_count":len(list((OUT/"renders").glob('tripo_part_*.png'))),"all24_visually_reviewed":True,"focused_detail_render_count":5,"headless_processes":[{"pid":p["pid"],"exit_code":p["exit_code"],"elapsed_s":p["elapsed_s"],"child_reaped":p["child_reaped"]} for p in processes],"cleanup":"Both owned Blender children exited normally and were waited/reaped by their Python parent. No service or user process stopped. CIM process inventory unavailable (access denied); Popen process handles establish ownership and exit.","final_bake_run":False,"source_geometry_written":False,"rig_or_fbx_authored":False,"shared_files_written":False})
print("PREP_READY", len(role_map), figure_target, "figure target; runner intentionally blocked")
