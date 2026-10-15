"""Package integrity verification; a PASS here does NOT turn failed retopo into a model PASS."""
from pathlib import Path
import ctypes
import hashlib
import importlib.util
import json
import sys
from PIL import Image

sys.dont_write_bytecode=True
OUT=Path(__file__).resolve().parent
REPO=OUT.parents[3]
PROFILE=OUT.parent/"build-profiles/patroclus-h2-bake-h2.json"
read=lambda p:json.loads(p.read_text(encoding="utf-8"))
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
rel=lambda p:p.relative_to(REPO).as_posix()
r=read(OUT/"reports/retopo-report.json")
inventory=read(OUT/"reports/lp-boundary-contact-inventory.json")
copy=read(OUT/"source-copy-record.json")
diag=read(OUT/"diagnostic-preview/preview-record.json")
hub=read(OUT/"art-hub-handoff.json")
checks={}
checks["retopo_fail_preserved"] = r["passed"] is False and [k for k,v in r["checks"].items() if not v["passed"]] == ["all_parts_outward_low_poly"]
checks["actual_budget_preserved"] = r["triangles_figure"] == 52360 and r["triangles_by_mesh"] == {"base":18633,"body":51164,"weapon":1196} and r["triangles_total"] == 70993
checks["failed_parts17_19_threshold_unchanged"] = r["checks"]["all_parts_outward_low_poly"]["measured"]["tripo_part_17"] == .4573 and r["checks"]["all_parts_outward_low_poly"]["measured"]["tripo_part_19"] == .1742 and read(PROFILE)["orientation"]["min_score_after_fix"] == .5
checks["no_flips_no_near_degenerate_faces"] = r["checks"]["flipped_low_poly_parts"]["measured"] == [] and r["checks"]["near_degenerate_faces"]["passed"]
checks["frozen_profile_unchanged"] = sha(PROFILE) == copy["profile_sha256"] == "23f3fd46f8110d2e02bae705803cd542bb64ce12377c9e3192f9b58fa2d0e00d"
checks["all28_frozen_prepare_owned_files_unchanged"] = len(copy["frozen_owned_bytes"]) == 28 and all(sha(REPO/x["path"]) == x["sha256"] and (REPO/x["path"]).stat().st_size == x["bytes"] for x in copy["frozen_owned_bytes"])
checks["frozen_prepare_manifest_unchanged"] = sha(REPO/copy["frozen_prepare_manifest"]) == copy["frozen_prepare_manifest_sha256"]
checks["three_bytecopies_still_match"] = len(copy["copies"]) == 3 and all(sha(REPO/x["source"]) == sha(REPO/x["destination"]) == x["sha256"] for x in copy["copies"])
checks["no_false_retopo_success_marker"] = list(read(OUT/"work/stages.json")["stages"]) == ["prepare"]
log=(OUT/"logs/retopo.log").read_text(encoding="utf-8",errors="replace")
checks["retopo_log_records_real_failure"] = "retopo checks failed: ['all_parts_outward_low_poly']" in log and "H2_BAKE_STAGE_OK retopo" not in log
checks["read_only_diagnostics_keep_lp_hp_bytes"] = diag["input_sha256_before"] == diag["input_sha256_after"] == {"lp":sha(OUT/"work/lp.blend"),"hp":sha(OUT/"work/hp.blend")}
checks["inventory_tied_to_actual_lp"] = inventory["source_lp_sha256"] == sha(OUT/"work/lp.blend")
checks["complete24part_loop_inventory"] = len(inventory["parts"]) == 24 and sum(x["all_loop_count"] for x in inventory["parts"].values()) == 17469 and sum(x["significant_ge_0_5cm_count"] for x in inventory["parts"].values()) == 13860 and sum(x["ge_1cm_count"] for x in inventory["parts"].values()) == 8172
checks["complete_significant_rows"] = all(sum(row["significant_ge_0_5cm"] for row in x["retained_loops"]) == x["significant_ge_0_5cm_count"] for x in inventory["parts"].values())
checks["contacts_and_20_lp_sections_measured"] = len(inventory["contacts"]) == 36 and len(inventory["LP_sections_compared_to_HP"]) == 20
checks["no_closure_rig_acceptance_claims"] = not any(hub["claims"].values()) and not inventory["claims"]["closure_run"] and diag["pipeline_stages_executed_in_this_script"] == []
checks["hub_marks_preparepass_retopofail_stop"] = hub["prepare"]["status"] == "PASS" and hub["retopo"]["status"] == "FAIL" and hub["queue_action"] == "stop_after_current_batch" and hub["frozen"]
images=[]
for row in diag["renders"]:
    f=REPO/row["path"]
    with Image.open(f) as im:im.verify()
    with Image.open(f) as im:dimensions=list(im.size)
    assert dimensions == row["dimensions"]
    images.append({"path":rel(f),"dimensions":dimensions,"sha256":sha(f)})
checks["14_valid_current_pngs"] = len(images) == 14
kernel=ctypes.WinDLL("kernel32",use_last_error=True)
kernel.OpenProcess.argtypes=[ctypes.c_ulong,ctypes.c_int,ctypes.c_ulong];kernel.OpenProcess.restype=ctypes.c_void_p
kernel.GetExitCodeProcess.argtypes=[ctypes.c_void_p,ctypes.POINTER(ctypes.c_ulong)];kernel.CloseHandle.argtypes=[ctypes.c_void_p]
processes=[]
for mode,exit_expected in [("retopo",1),("inventory",0)]:
    record=read(OUT/(mode+"-process-record.json"));cmd=record["command"]
    handle=kernel.OpenProcess(0x1000,False,record["pid"]);live=False
    if handle:
        code=ctypes.c_ulong()
        if not kernel.GetExitCodeProcess(handle,ctypes.byref(code)):raise OSError("Cannot verify own child exit")
        live=code.value == 259;kernel.CloseHandle(handle)
    elif ctypes.get_last_error()!=87:raise OSError(ctypes.get_last_error(),"Cannot verify own child absence")
    script=Path(cmd[cmd.index("--python")+1])
    checks[mode+"_expected_exit_reaped_threads4_scriptpin"] = record["exit_code"] == exit_expected and record["child_reaped"] and not live and cmd[cmd.index("--threads")+1] == "4" and sha(script) == record["script_sha256"]
    processes.append({"mode":mode,"pid":record["pid"],"exit_code":record["exit_code"],"child_reaped":record["child_reaped"],"live_at_verification":live,"elapsed_s":record["elapsed_s"]})
frozen_manifest=read(REPO/copy["frozen_prepare_manifest"])
pins={x["path"]:x for x in frozen_manifest["read_only_inputs"]}
code_files=[REPO/"tools/tripo-pipeline/blender/h2_bake"/n for n in ["run_h2_bake.py","blender_entry.py","st_retopo.py","bl_util.py","st_close.py","profile.py"]]
checks["generic_stage_code_unchanged_since_prepare"] = all(rel(f) in pins and sha(f) == pins[rel(f)]["sha256"] for f in code_files)
profile=read(PROFILE)
checks["raw_glb_sources_still_pinned"] = all(sha(REPO/profile["sources"][key]["path"]) == profile["sources"][key]["sha256"] for key in ["parts_glb","tex_glb"])
verification={"schema":"unmatched.patroclus-failed-retopo-package-verification/1","package_integrity_passed":all(checks.values()),"model_status":"FAIL / blocked before closure","prepare_status":"PASS 5/5, reused bytes","retopo_status":"FAIL 2/3","checks":checks,"current_pngs":images,"processes":processes,"frozen_prepare_files_verified":28,"claims":hub["claims"],"stop_after_current_batch":True}
(OUT/"verification.json").write_text(json.dumps(verification,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
owned=[f for f in OUT.rglob("*") if f.is_file() and f.name!="hash-manifest.json"]
readonly=[PROFILE,REPO/copy["frozen_prepare_manifest"]]+[REPO/x["path"] for x in copy["frozen_owned_bytes"]]+code_files
readonly += [REPO/profile["sources"][key]["path"] for key in ["parts_glb","tex_glb"]]
readonly=list(dict.fromkeys(readonly))
entry=lambda f:{"path":rel(f),"bytes":f.stat().st_size,"sha256":sha(f)}
manifest={"schema":"unmatched.patroclus-failed-retopo-manifest/1","owned_outputs":[entry(f) for f in sorted(owned)],"read_only_inputs":[entry(f) for f in sorted(readonly)],"pipeline_stages_executed":["retopo"],"reused_pipeline_stages":["prepare"],"retopo_success":False,"network":{"paid_calls":0,"imagegen_calls":0},"claims":hub["claims"]}
(OUT/"hash-manifest.json").write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
print(json.dumps({"package_integrity_passed":verification["package_integrity_passed"],"model_status":"FAIL","checks_passed":sum(checks.values()),"checks_total":len(checks),"owned_files":len(owned),"read_only_files":len(readonly),"png_count":len(images),"retopo_report_sha256":sha(OUT/"reports/retopo-report.json"),"inventory_sha256":sha(OUT/"reports/lp-boundary-contact-inventory.json")}))
if not all(checks.values()):raise SystemExit(1)
