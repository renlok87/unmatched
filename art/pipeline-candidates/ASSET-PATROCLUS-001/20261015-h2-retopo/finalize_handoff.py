"""Package measured failed-retopo evidence for Art Hub without accepting or modifying model inputs."""
from pathlib import Path
import hashlib
import json

OUT=Path(__file__).resolve().parent
REPO=OUT.parents[3]
read=lambda p:json.loads(p.read_text(encoding="utf-8"))
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
rel=lambda p:p.relative_to(REPO).as_posix()
r=read(OUT/"reports/retopo-report.json")
i=read(OUT/"reports/lp-boundary-contact-inventory.json")
profile=OUT.parent/"build-profiles/patroclus-h2-bake-h2.json"
loops={"all":sum(x["all_loop_count"] for x in i["parts"].values()),"ge_0_5cm":sum(x["significant_ge_0_5cm_count"] for x in i["parts"].values()),"ge_1cm":sum(x["ge_1cm_count"] for x in i["parts"].values()),"retained_with_coordinates":sum(len(x["retained_loops"]) for x in i["parts"].values())}
failures={n:x["orientation"]["after"] for n,x in r["parts"].items() if (x["orientation"]["after"]["score"] or 0)<.5}
for x in failures.values():
    x["classified_area_inward_fraction"]=x["in_area_m2"]/(x["in_area_m2"]+x["out_area_m2"])
hub={"schema":"unmatched.art-hub-stage-handoff/1","asset_id":"ASSET-PATROCLUS-001","character":"Patroclus","game_role":"sidekick","frozen":True,"queue_action":"stop_after_current_batch","prepare":{"status":"PASS","checks_passed":5,"checks_total":5,"report":rel(OUT.parent/"20261015-h2-bake/reports/prepare-report.json"),"report_sha256":sha(OUT.parent/"20261015-h2-bake/reports/prepare-report.json")},"retopo":{"status":"FAIL","report":rel(OUT/"reports/retopo-report.json"),"report_sha256":sha(OUT/"reports/retopo-report.json"),"checks_passed":2,"checks_total":3,"figure_triangles":r["triangles_figure"],"body_triangles":r["triangles_by_mesh"]["body"],"weapon_triangles":r["triangles_by_mesh"]["weapon"],"base_triangles":r["triangles_by_mesh"]["base"],"total_triangles":r["triangles_total"],"starting_target_figure":32550,"starting_target_base":1600,"budget_figure":45000,"budget_base":2500,"orientation_threshold":.5,"orientation_failures":failures,"flipped_parts":[],"success_stage_marker_written":False},"profile":{"path":rel(profile),"sha256":sha(profile),"modified_in_this_task":False},"inventory":{"path":rel(OUT/"reports/lp-boundary-contact-inventory.json"),"sha256":sha(OUT/"reports/lp-boundary-contact-inventory.json"),"native_loops":loops,"caps_or_closure_authored":False},"causal_analysis":{"measured":{"HP_boundary":i["HP_boundary_causal_evidence"],"retopo_order":"copy HPG mesh -> Decimate COLLAPSE -> cleanup(remove_doubles/degenerate/loose/tiny islands) -> orientation","caps":[],"cloth_shell_executed":False,"base_rim_smooth_configured":False,"dense_region_part":"tripo_part_5 only, not cape/base"},"inference":"Highly fragmented/coincident-edge HP connectivity is presented to QEM before welding, plausibly limiting safe collapses and opening surface cracks. Exact internal Blender collapse rejection reason is not exposed by this unchanged stage; no weld/retopo counterfactual was run.","not_supported":"Do not attribute overrun to added caps/shells, claim all normals reversed, weaken orientation threshold, or infer grip safety from unsigned contact minima."},"visual_review":{"personally_opened_png_count":14,"verdict":"failed candidate: widespread visible tears/faceting on cape, base, limbs, shield and sword; large-scale pose silhouette remains recognizable but surface continuity is unacceptable","preview_record":rel(OUT/"diagnostic-preview/preview-record.json")},"next_action":{"status":"not_started","owner":"root/user after stop","suggestion":"Investigate preserving/welding coincident HP connectivity before decimation in a separate bounded proposal, with exact topology/geometry-identity checks and no blind threshold change. Only after a valid budgeted LP should loop/contact caps be selected.","forbidden_advance":"No close, UV, bake, rig, runtime, new imagegen or paid task was run or queued."},"claims":{"art_accepted":False,"game_ready":False,"model_accepted":False,"retopo_passed":False,"rig_authored":False,"closure_run":False,"baked":False},"process_records":[rel(OUT/"retopo-process-record.json"),rel(OUT/"inventory-process-record.json")]}
(OUT/"art-hub-handoff.json").write_text(json.dumps(hub,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")

table="\n".join("| %s | %d → %d | %d | %d | %.4f | %.4f |"%(n,x["target_triangles"],x["triangles"],x["topology"]["boundary_edges"],i["parts"][n]["significant_ge_0_5cm_count"],x["orientation"]["after"]["score"],x["deviation"]["hi_to_lo_mm"]["p95"]) for n,x in sorted(r["parts"].items(),key=lambda it:int(it[0].rsplit("_",1)[1])))
text=f'''# Patroclus — retopo FAIL, frozen diagnostic handoff

**Prepare remains PASS 5/5. This single unchanged generic retopo attempt FAILS (2/3 checks pass).** The candidate is blocked before closure. All 14 actual diagnostic PNGs were personally opened. This batch stops here; no retry, repair, new profile, threshold change or following stage was performed.

Machine-readable Art Hub update: [art-hub-handoff.json](art-hub-handoff.json). Actual report: [reports/retopo-report.json](reports/retopo-report.json). Full native LP loop/contact evidence: [reports/lp-boundary-contact-inventory.json](reports/lp-boundary-contact-inventory.json). Integrity/lifecycle: [verification.json](verification.json), [hash-manifest.json](hash-manifest.json).

## Actual result

- Figure **52,360 triangles** = body **51,164** + sword **1,196**, against starting target **32,550**, budget **45,000**. Base **18,633** against target **1,600**, budget **2,500**. Total **70,993**. These are actual pre-closure LP counts; no shell/cap cost has been added.
- Failed `all_parts_outward_low_poly`: own-left upper arm **part17: 0.4573**, own-left waist/flank panel **part19: 0.1742**, unchanged required score **≥ 0.5**. `flipped_low_poly_parts: []` and zero near-degenerate faces pass. No successful retopo stage marker was written.
- Ray score is **(out_area − in_area)/(out_area + in_area)**, from the whole-figure ±normal escape test. The inward shares of the *classified sampled area* are **27.13%** for part17 and **41.29%** for part19. Both scores are positive and above the **−0.5** flip threshold; they are **not globally inside-out parts**. “27%/41% normals reversed” would be an incorrect interpretation: rays depend on actual surface openings and occlusion, and faces with both/neither ray escaping are omitted. Prepare HP scores were all 1.0; retopo changed surface connectivity/coverage. The data does not isolate all causes of each inward classification.
- Read-only inventory finds **{loops['all']:,} native loops**, **{loops['ge_0_5cm']:,} ≥ 0.5 cm**, **{loops['ge_1cm']:,} ≥ 1 cm**; **{loops['retained_with_coordinates']:,}** rows retain exact LP vertex indices/coordinates and nearest-three-part median/p90 distances. The retention threshold is 0.5 cm everywhere and 0.1 cm for base/feet/knee/grips/failing17/19. Native open-chain perimeter wraps a final chord; `closed:false` rows are not cap cycles. This inventory is **not a cap selection list**.

## Why the current stage did this

The code passes `target / hi_triangles` as the COLLAPSE modifier ratio, with triangulation on and symmetry off; it does not enforce a hard post-stage triangle budget. On cape0 (**596,290 HP triangles**) and base1 (**186,864**), no dense-region mask is configured. Dense face protection belongs only to face5. There is **no explicit shell/boundary-preservation switch** authored by this profile. No `retopo.caps`, `base.rim_smooth` or cloth-shell construction was executed, so added caps/shells cannot explain the excess.

The decisive measured input issue is fragmented topology **before** the modifier. Cape HP has **72,084 boundary edges / 390 islands**, base **70,316 / 739**. Read-only endpoint-coordinate comparison (round7 metres) finds **69,865 cape boundary edges (96.92%)** and **69,608 base boundary edges (98.99%)** coincide geometrically with another boundary edge while remaining topologically separate. HP vertex counts vs unique-position counts are cape **320,080 vs 299,248**, base **116,015 vs 93,784**. Geometry identity between the two GLBs checks position sets/triangles, not manifold connectivity.

In this unchanged implementation, **Decimate runs before cleanup/remove_doubles**. QEM therefore receives those disconnected seams/boundaries rather than a welded surface. This is strong evidence for topology constraints limiting collapses and seam cracks growing as patches simplify independently; the exact internal Blender collapse-rejection reason is not exposed by the stage and was not proved by a forbidden second experiment. Cleanup afterward merged only **286 cape** / **639 base** vertices and cannot undo already independently collapsed patches. Actual cape remains **23,853 triangles / 32,092 boundary edges**, base **18,633 / 30,086**. The outcome is visibly shredded across surfaces, not merely a clean shell kept slightly denser than its target.

Do not patch this failed candidate by adding thousands of contact caps. Investigate source connectivity before decimation as a separate bounded proposal after the stop, preserving true part seams/holes and verifying geometry identity. No such weld, modifier change or retry was run here.

## Personally viewed evidence and closure limits

- [LP front](diagnostic-preview/lp-front.png), [right](diagnostic-preview/lp-right.png), [back](diagnostic-preview/lp-back.png), [front 3/4](diagnostic-preview/lp-front34.png), [copied HP reference](diagnostic-preview/hp-front34-reference.png): silhouette is broadly recognizable, but many visible tears and missing patches affect cape, base, limbs, helmet, shield and sword. These Workbench clay/part-colour diagnostics are not PBR, rig or formal art acceptance. The HP/LP framing is derived separately from each geometry, so this is not a pixel-aligned silhouette gate.
- [Left knee10/shin12 boundaries](diagnostic-preview/lp-left-knee-boundaries.png): extensive scattered holes supersede the single local HP knee concern. Part10 has **330** significant loops; its largest native loop is **29.203 cm**, nearest cape0 median **13.717 mm**, not an immediately justified hidden-contact cap.
- [Foot/base boundaries](diagnostic-preview/lp-foot-base-boundaries.png): numerous base tears throughout the platform, plus foot openings. Base has **5,243** significant loops. Its largest loop is **33.988 cm**, nearest right shin7 median **77.403 mm**; this is not simply a foot contact cutout.
- Isolated sword grip [front](diagnostic-preview/lp-sword-grip-front.png) / [back](diagnostic-preview/lp-sword-grip-back.png): fist16/guard8/pommel21 meet locally, but surfaces are torn. Closest unsigned fist16→blade8 distance is **0.0172 mm**, fist16→pommel21 **0.0079 mm**; these minima do not prove handle continuity or deformation safety. Largest pommel21 loop (**4.067 cm**) is nearest fist16 at median **0.294 mm**, a *measurement for a future valid LP*, not an adopted cap. Blade8↔pommel21 surface minimum **14.7945 mm** is across the occupied fist region, not proof that a new handle bridge is required.
- [Shield rear/hand, cape removed](diagnostic-preview/lp-shield-hand-rear.png): the left fist and bracer are now visible. Hand18→shield2 minimum is **0.0002 mm**, median over all hand vertices **7.0461 mm**. Largest hand loop (**10.511 cm**) nearest shield2 median **1.238 mm**; no grip clearance or pose acceptance is established.
- Failed [upper arm17](diagnostic-preview/lp-failed-upper-arm17.png), waist19 [front](diagnostic-preview/lp-failed-waist-panel19-front.png) / [back](diagnostic-preview/lp-failed-waist-panel19-back.png), [cape](diagnostic-preview/lp-cape-boundaries.png): many surface openings; red curves mark retained boundaries, not proposed repairs. Workbench can show both sides, unlike final one-sided runtime materials.

LP section bands were measured at the same own-HP landmarks for comparison only; no bones or weights were authored/changed. Largest anchor displacement is **3.221 mm at shoulder.R**, then **2.074 mm chest**. Similar anchor positions do not validate the torn mesh. Face dense region retains **1,412 triangles** (target 1,600), face hi→lo p95 **0.1332 mm**. Cape p95/max deviation is **0.9739 / 3.3372 mm**, base **0.6888 / 5.0104 mm**. Nearest-surface deviation can stay small around a torn patch; it does not prove intact silhouette or topology.

## Per-part actuals

| Own part | Target → actual tris | Boundary edges | Loops ≥0.5 cm | Ray score | HP→LP p95 mm |
| --- | --- | --- | --- | --- | --- |
{table}

## Reuse, commands, lifecycle and stop

Frozen prepare/profile were verified against all **28** original owned hashes before reuse. `source-copy-record.json` records separate `shutil.copy2` byte copies of `work/hp.blend`, prepare report and prepare stage marker into this new directory; no hardlinks, rerun prepare or source write. The original profile SHA remains **23f3fd46f8110d2e02bae705803cd542bb64ce12377c9e3192f9b58fa2d0e00d**. Its original descriptive prepare-only scope remains unchanged; parent explicitly authorized this single retopo continuation with the same targets. The copied `work/stages.json` contains **prepare only**; retopo failed before a success marker.

```powershell
python -B art/pipeline-candidates/ASSET-PATROCLUS-001/20261015-h2-retopo/run_bounded.py retopo
python -B art/pipeline-candidates/ASSET-PATROCLUS-001/20261015-h2-retopo/run_bounded.py inventory
python -B art/pipeline-candidates/ASSET-PATROCLUS-001/20261015-h2-retopo/finalize_handoff.py
python -B art/pipeline-candidates/ASSET-PATROCLUS-001/20261015-h2-retopo/verify_and_manifest.py
```

Only the first command executes a pipeline stage, unchanged generic `--stages retopo`. Local launcher override adds hidden console, **4 threads**, exact script/argv/PID records and wait/reap. The inventory script calls native read-only loop/BVH helpers, **never `st_close.run`**, and saves no geometry. Retopo child **PID48252**, **19.242 s**, exit **1**, reaped. Inventory/render child **PID55640**, **35.441 s**, exit **0**, reaped. Both exact records are in this directory. No process was killed, no GUI/service started. Final verifier checks both children absent and frozen inputs unchanged.

No sibling profile was needed. No closure settings, caps, shell, masks, UV, bake, rig, paid call, image generation, runtime import, shared registry, source card, canonical source, Git or ledger edit was performed. The `ROLE: hero` / `GAME_ROLE: sidekick` card conflict remains disclosed by the original profile; this task did not resolve it.

**Frozen and stopped after this batch per the user's instruction.** Art Hub should show **prepare PASS / retopo FAIL / model blocked**, with the failed LP kept as evidence. Root owns integration, commit and push. No following iteration is started or queued.
'''
(OUT/"HANDOFF.md").write_text(text,encoding="utf-8")
(OUT/"README.md").write_text('''# Patroclus — retopo FAIL (frozen)

Prepare PASS 5/5 is preserved. One unchanged generic retopo failed: figure52,360/base18,633 tris; outward scores17=0.4573 and19=0.1742 below0.5. The LP is visibly torn and blocked before closure.

Read [HANDOFF.md](HANDOFF.md), [Art Hub handoff](art-hub-handoff.json), [actual retopo report](reports/retopo-report.json), [full LP loop/contact inventory](reports/lp-boundary-contact-inventory.json), [verification](verification.json) and [manifest](hash-manifest.json).

Fourteen personally viewed current diagnostics are listed in the handoff. No retry, closure, UV, bake, rig, paid/image generation or runtime acceptance. Frozen source prepare/profile stay unchanged. Stop after this batch; root handles commit/push.
''',encoding="utf-8")
print("HANDOFF_CREATED",json.dumps(loops),"retopo_fail",failures.keys())
