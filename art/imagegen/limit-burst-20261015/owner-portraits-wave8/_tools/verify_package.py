"""Verify only this blocked evidence package. Never edits source inputs."""
from pathlib import Path
import hashlib
import json

PACKAGE=Path(__file__).resolve().parents[1]
ROOT=PACKAGE.parents[3]
def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def read(path):return json.loads(Path(path).read_text(encoding="utf-8-sig"))
def save(path,data):Path(path).write_text(json.dumps(data,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")

def main():
    before=read(PACKAGE/"source-hashes-before.json")
    checks=[{**s,"after_sha256":sha(ROOT/s["path"]),"unchanged":s["sha256"]==sha(ROOT/s["path"])} for s in before]
    preflight=read(PACKAGE/"preflight.json")
    refs={e["asset_key"]:e for e in preflight["entries"]}
    records=read(PACKAGE/"generation-records.json")
    proof=[]
    for record in records:
        key=record["asset_key"]
        prompt=PACKAGE/record["exact_prompt"]
        args_path=PACKAGE/record["tool_arguments"]
        args=read(args_path)
        error_path=PACKAGE/record["error_record"]
        error=read(error_path)
        exact=prompt.read_text(encoding="utf-8").rstrip("\n")==args["prompt"]
        reference_sha=sha(ROOT/record["reference_image"])
        record["reference_sha256_before"]=refs[key]["reference_sha256"]
        record["reference_sha256_after"]=reference_sha
        record["prompt_sha256"]=sha(prompt)
        record["error_sha256"]=sha(error_path)
        assert exact and error["code"]=="moderation_blocked" and error["http_status"]==400
        assert error["request_id"]==record["request_id"]
        assert record["selected_sha256"] is None and record["original_path"] is None
        proof.append({"asset_key":key,"exact_prompt_matches_tool_arguments":exact,"prompt_sha256":sha(prompt),
            "tool_arguments_sha256":sha(args_path),"error_sha256":sha(error_path),"request_id":record["request_id"],
            "reference_unchanged":reference_sha==refs[key]["reference_sha256"],"png_created":False})
    save(PACKAGE/"generation-records.json",records)
    ledger=read(PACKAGE/"ledger-handoff.json")
    ledger["records"]=records
    save(PACKAGE/"ledger-handoff.json",ledger)
    pngs=list(PACKAGE.rglob("*.png"))
    assert not pngs
    snapshot_checks=[]
    for name in ["live-owner-evidence.json","live-roster-snapshot.json"]:
        source=ROOT/"art/imagegen/limit-burst-20261015/review-wave8"/name
        snapshot_checks.append({"file":name,"sha256":sha(PACKAGE/name),"equal_original":sha(PACKAGE/name)==sha(source)})
    verification={"schema":"blocked-portrait-package/1","card_id":"CP-34","date":"2026-10-15",
        "generation_calls":4,"successful_outputs":0,"blocked_outputs":4,"selected_outputs":0,
        "retry_calls":0,"fallback_calls":0,"png_count":len(pngs),"source_visual_review":"not applicable: no output PNG",
        "circle_and_native_review":"not performed: no output PNG","source_unchanged":all(s["unchanged"] for s in checks),
        "sources":checks,"changed_context_sources":[s for s in checks if not s["unchanged"]],
        "source_mutation_note":"Before hashes retained; any coordinator context changes reported honestly, without rewriting historical inputs.",
        "image_reference_count":len(proof),"image_references_unchanged":all(x["reference_unchanged"] for x in proof),
        "input_snapshot_copies":snapshot_checks,"input_snapshot_copies_equal":all(x["equal_original"] for x in snapshot_checks),
        "call_proof":proof,"runtime_ready":False,"formal_accepted":False,
        "json_utf8_without_replacement_characters":all(chr(0xfffd) not in f.read_text(encoding="utf-8-sig") for f in PACKAGE.rglob("*.json")),
        "shared_ledger_runtime_gallery_git_written":False,"background_processes_started":False}
    save(PACKAGE/"verification.json",verification)
    manifest={f.relative_to(PACKAGE).as_posix():sha(f) for f in sorted(PACKAGE.rglob("*")) if f.is_file() and f.name!="manifest-sha256.json"}
    save(PACKAGE/"manifest-sha256.json",manifest)
    assert all(sha(PACKAGE/path)==digest for path,digest in manifest.items())
    print(json.dumps({"members":len(manifest),"manifest_sha256":sha(PACKAGE/"manifest-sha256.json"),
        "MiB":round(sum(f.stat().st_size for f in PACKAGE.rglob("*") if f.is_file())/1024**2,3),
        "source_unchanged":verification["source_unchanged"],"inputs":len(checks),"refs_unchanged":verification["image_references_unchanged"],
        "snapshot_copies_equal":verification["input_snapshot_copies_equal"],"calls":4,"outputs":0,"blocked":4,"pngs":0}))
if __name__=="__main__":main()
