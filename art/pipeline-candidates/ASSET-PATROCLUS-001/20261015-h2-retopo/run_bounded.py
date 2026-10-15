"""Retopo-only continuation from byte-copied, verified frozen prepare. No source mutation."""
from pathlib import Path
import datetime
import hashlib
import importlib.util
import json
import os
import shutil
import subprocess
import sys
import time

sys.dont_write_bytecode = True
OUT = Path(__file__).resolve().parent
REPO = OUT.parents[3]
SOURCE = OUT.parent/"20261015-h2-bake"
PROFILE = OUT.parent/"build-profiles/patroclus-h2-bake-h2.json"
EXE = Path("C:/Program Files/Blender Foundation/Blender 5.2/blender.exe")
MODE = sys.argv[1] if len(sys.argv)>1 else "retopo"
assert MODE in ("retopo","inventory")
read = lambda p: json.loads(p.read_text(encoding="utf-8"))
sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()

def launch(exe,script,args,log):
    cmd = [str(exe),"--background","--factory-startup","--threads","4","--python-exit-code","1","--python",str(script),"--"]+[str(x) for x in args]
    record = {"mode":MODE,"command":cmd,"cwd":str(REPO),"started_utc":datetime.datetime.now(datetime.timezone.utc).isoformat(),"script_sha256":sha(Path(script)),"parent_pid":os.getpid()}
    dest = OUT/(MODE+"-process-record.json")
    start = time.monotonic()
    with Path(log).open("w",encoding="utf-8") as fh:
        proc = subprocess.Popen(cmd,cwd=REPO,stdout=fh,stderr=subprocess.STDOUT,creationflags=getattr(subprocess,"CREATE_NO_WINDOW",0))
        record["pid"] = proc.pid
        dest.write_text(json.dumps(record,indent=2)+"\n",encoding="utf-8")
        try:
            record["exit_code"] = proc.wait(timeout=1800)
        except subprocess.TimeoutExpired:
            proc.kill();proc.wait()
            record.update(timed_out=True,exit_code=proc.returncode)
        finally:
            record.update(elapsed_s=round(time.monotonic()-start,3),finished_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),child_reaped=proc.poll() is not None)
            dest.write_text(json.dumps(record,indent=2)+"\n",encoding="utf-8")
    print(json.dumps(record,indent=2),flush=True)
    if proc.returncode != 0:
        raise RuntimeError("own Blender child failed; inspect "+str(log))

if MODE == "retopo":
    if (OUT/"source-copy-record.json").exists():
        raise SystemExit("Refuse to repeat retopo or overwrite carried inputs in this completed/started run")
    manifest = read(SOURCE/"hash-manifest.json")
    expected = {x["path"]:x for x in manifest["owned_outputs"]}
    assert sha(PROFILE) == "23f3fd46f8110d2e02bae705803cd542bb64ce12377c9e3192f9b58fa2d0e00d"
    original = []
    for row in manifest["owned_outputs"]:
        f=REPO/row["path"]
        assert sha(f)==row["sha256"] and f.stat().st_size==row["bytes"],str(f)
        original.append(row)
    copies=[]
    for relative in ("work/hp.blend","reports/prepare-report.json","work/stages.json"):
        src=SOURCE/relative;dst=OUT/relative
        assert not dst.exists()
        dst.parent.mkdir(parents=True,exist_ok=True)
        shutil.copy2(src,dst)
        assert sha(src)==sha(dst)
        copies.append({"source":src.relative_to(REPO).as_posix(),"destination":dst.relative_to(REPO).as_posix(),"sha256":sha(src),"bytes":src.stat().st_size,"method":"shutil.copy2, separate files, no hardlinks"})
    snapshot={"schema":"unmatched.patroclus-retopo-carry/1","frozen_prepare_manifest":str((SOURCE/"hash-manifest.json").relative_to(REPO)).replace("\\","/"),"frozen_prepare_manifest_sha256":sha(SOURCE/"hash-manifest.json"),"frozen_owned_bytes":original,"profile_sha256":sha(PROFILE),"copies":copies,"pipeline_prepare_executed":False,"authorization_note":"Parent authorizes retopo-only with frozen profile targets; descriptive profile execution_scope still says original prepare-only and remains unchanged."}
    (OUT/"source-copy-record.json").write_text(json.dumps(snapshot,indent=2)+"\n",encoding="utf-8")
    path=REPO/"tools/tripo-pipeline/blender/h2_bake/run_h2_bake.py"
    loader=importlib.util.spec_from_file_location("own_bounded_runner",path)
    runner=importlib.util.module_from_spec(loader);loader.loader.exec_module(runner)
    runner.blender=launch
    sys.argv=[str(path),"--profile",str(PROFILE),"--run-dir",str(OUT),"--stages","retopo","--blender",str(EXE)]
    runner.main()
else:
    launch(EXE,OUT/"inventory_and_render.py",[],OUT/"inventory.log")
