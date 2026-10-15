"""Verify only the owned prepare package; hash read-only sources, do not mutate them."""
from pathlib import Path
import ctypes
import hashlib
import importlib.util
import json
import sys
from PIL import Image

sys.dont_write_bytecode = True
OUT = Path(__file__).resolve().parent
REPO = OUT.parents[3]
PROFILE = OUT.parent/"build-profiles/patroclus-h2-bake-h2.json"
read = lambda p: json.loads(p.read_text(encoding="utf-8"))
sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
rel = lambda p: p.relative_to(REPO).as_posix()
p = read(PROFILE)
module = REPO/"tools/tripo-pipeline/blender/h2_bake/profile.py"
loader = importlib.util.spec_from_file_location("own_validate",module)
M = importlib.util.module_from_spec(loader);loader.loader.exec_module(M)
checks = {"profile_valid_v2":not M.validate(p) and p["profile_version"] == 2}
report = read(OUT/"reports/prepare-report.json")
checks["actual_prepare_pass_5_of_5"] = report["passed"] and len(report["checks"]) == 5 and all(c["passed"] for c in report["checks"].values())
stages = read(OUT/"work/stages.json")
checks["only_prepare_pipeline_stage"] = list(stages["stages"]) == ["prepare"]
checks["geometry_identity_all24"] = len(report["parts"]) == 24 and all(x["unique_position_sets_equal"] and x["triangles"][0] == x["triangles"][1] for x in report["parts"].values())
checks["source_triangles_1967447"] = sum(x["triangles"][0] for x in report["parts"].values()) == 1967447
checks["orientation_all24_score1_no_flips"] = len(report["orientation"]) == 24 and all(x["score"] == 1 for x in report["orientation"].values()) and report["checks"]["orientation_inside_out_parts_as_profile"]["measured"] == []
inputs = []
for key in ("parts_glb","tex_glb"):
    x = p["sources"][key]; f=REPO/x["path"]
    ok = sha(f) == x["sha256"] and f.stat().st_size == x["bytes"]
    checks[key+"_source_untouched"] = ok
    inputs.append({"path":rel(f),"bytes":f.stat().st_size,"sha256":sha(f),"verified_against_profile":ok})
measure = read(OUT/"measurements-own-hp.json")
checks["own_measurement_untouched_source"] = measure["sha256_before"] == measure["sha256_after"] == p["sources"]["parts_glb"]["sha256"]
checks["own17_bones_match_measurement"] = p["rig"]["bones"] == measure["proposed_bones"] and len(p["rig"]["bones"]) == 17
diag = read(OUT/"diagnostic-preview/preview-record.json")
checks["prepared_hp_not_mutated_by_preview"] = diag["hp_blend_sha256_before"] == diag["hp_blend_sha256_after"] == sha(OUT/"work/hp.blend")
checks["three_actual8k_images"] = len(diag["images"]) == 3 and all(x["size"] == [8192,8192] for x in diag["images"])
images = []
for item in diag["renders"]:
    f = REPO/item["path"]
    with Image.open(f) as im:
        im.verify()
    with Image.open(f) as im:
        size=list(im.size)
    assert size == item["resolution"]
    images.append({"path":rel(f),"dimensions":size,"sha256":sha(f)})
checks["six_valid_current_pngs"] = len(images) == 6
processes = []
kernel = ctypes.WinDLL("kernel32",use_last_error=True)
kernel.OpenProcess.argtypes=[ctypes.c_ulong,ctypes.c_int,ctypes.c_ulong]
kernel.OpenProcess.restype=ctypes.c_void_p
kernel.GetExitCodeProcess.argtypes=[ctypes.c_void_p,ctypes.POINTER(ctypes.c_ulong)]
kernel.CloseHandle.argtypes=[ctypes.c_void_p]
for mode in ("measure","prepare","preview"):
    record = read(OUT/(mode+"-process-record.json"))
    command = record["command"]
    script = Path(command[command.index("--python")+1])
    handle = kernel.OpenProcess(0x1000,False,record["pid"])
    live=False
    if handle:
        code=ctypes.c_ulong()
        if not kernel.GetExitCodeProcess(handle,ctypes.byref(code)):
            raise OSError("Cannot verify own recorded child exit")
        live=code.value == 259
        kernel.CloseHandle(handle)
    else:
        err=ctypes.get_last_error()
        if err not in (87,):
            raise OSError(err,"Cannot establish own recorded child absence")
    ok = record["exit_code"] == 0 and record["child_reaped"] and not live and sha(script) == record["script_sha256"] and command[command.index("--threads")+1] == "4"
    checks[mode+"_process_finished_script_pinned_threads4"] = ok
    processes.append({"mode":mode,"pid":record["pid"],"exit_code":record["exit_code"],"child_reaped":record["child_reaped"],"live_at_verification":live})
cardpath=OUT.parent/"evidence/acceptance-concept/20261015-sheet-r1/card.json"
card=read(cardpath)
checks["accepted1c_inputs_unchanged"] = card["score"] == 9.4 and card["verdict"] == "pass" and all(sha(REPO/x["path"]) == x["sha256"] for x in card["accepted_object"])
read_only = [cardpath,REPO/p["sources"]["source_spec"],OUT.parent/"asset-card.yaml"]
read_only += [REPO/x["path"] for x in card["accepted_object"]]
read_only += [OUT.parent/"20261015-h2-prep"/name for name in ("HANDOFF.md","part-role-map.json","stage3-config.proposed.json","measurements.json")]
read_only += list((REPO/"tools/tripo-pipeline/blender/h2_bake").glob("*.py"))
inputs += [{"path":rel(f),"bytes":f.stat().st_size,"sha256":sha(f)} for f in read_only]
verification={"schema":"unmatched.patroclus-prepare-verification/1","passed":all(checks.values()),"checks":checks,"prepare_checks_passed":5,"source_part_count":24,"source_triangles_each":1967447,"current_pngs":images,"processes":processes,"claims":{"art_accepted":False,"game_ready":False,"rig_authored":False,"lp_authored":False,"baked":False},"limitations":["HP landmarks are provisional; LP must be measured later.","Local own-left knee opening and foot cutouts need LP loop inventory before closure.","Shield rear hand partly occluded; no grip clearance claim.","Card ROLE hero / GAME_ROLE sidekick conflict retained.","Diagnostic Workbench previews do not evaluate full PBR material or establish formal acceptance."]}
(OUT/"verification.json").write_text(json.dumps(verification,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
owned=[PROFILE]+[x for x in OUT.rglob("*") if x.is_file() and x.name!="hash-manifest.json"]
entries=[{"path":rel(f),"bytes":f.stat().st_size,"sha256":sha(f)} for f in sorted(owned)]
manifest={"schema":"unmatched.patroclus-prepare-manifest/1","owned_outputs":entries,"read_only_inputs":inputs,"pipeline_stages":["prepare"],"network":{"paid_calls":0,"imagegen_calls":0},"claims":verification["claims"]}
(OUT/"hash-manifest.json").write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
print(json.dumps({"passed":verification["passed"],"checks":len(checks),"owned_files":len(entries),"read_only_inputs":len(inputs),"current_pngs":len(images),"profile_sha256":sha(PROFILE),"report_sha256":sha(OUT/"reports/prepare-report.json")}))
if not verification["passed"]:
    raise SystemExit(1)
