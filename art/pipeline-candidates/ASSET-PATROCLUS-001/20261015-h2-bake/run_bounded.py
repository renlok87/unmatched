"""Own hidden four-thread sequential Blender children; only prepare is a pipeline stage."""
from pathlib import Path
import datetime
import hashlib
import importlib.util
import json
import subprocess
import sys
import time

sys.dont_write_bytecode = True
OUT = Path(__file__).resolve().parent
REPO = OUT.parents[3]
EXE = Path("C:/Program Files/Blender Foundation/Blender 5.2/blender.exe")
MODE = sys.argv[1] if len(sys.argv)>1 else "measure"
assert MODE in ("measure", "prepare", "preview")

def launch(exe, script, args, log):
    cmd = [str(exe), "--background", "--factory-startup", "--threads", "4", "--python-exit-code", "1", "--python", str(script), "--"] + [str(x) for x in args]
    record = {"mode":MODE,"command":cmd,"cwd":str(REPO),"started_utc":datetime.datetime.now(datetime.timezone.utc).isoformat(),"script_sha256":hashlib.sha256(Path(script).read_bytes()).hexdigest(),"parent_pid":__import__('os').getpid()}
    dest = OUT / (MODE+"-process-record.json")
    start = time.monotonic()
    with Path(log).open("w",encoding="utf-8") as fh:
        proc = subprocess.Popen(cmd,cwd=REPO,stdout=fh,stderr=subprocess.STDOUT,creationflags=getattr(subprocess,"CREATE_NO_WINDOW",0))
        record["pid"] = proc.pid
        dest.write_text(json.dumps(record,indent=2)+"\n",encoding="utf-8")
        try:
            record["exit_code"] = proc.wait(timeout=900)
        except subprocess.TimeoutExpired:
            proc.kill(); proc.wait()
            record.update(timed_out=True,exit_code=proc.returncode)
        finally:
            record.update(elapsed_s=round(time.monotonic()-start,3),finished_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),child_reaped=proc.poll() is not None)
            dest.write_text(json.dumps(record,indent=2)+"\n",encoding="utf-8")
    print(json.dumps(record,indent=2),flush=True)
    if proc.returncode != 0:
        raise RuntimeError("own Blender child failed; inspect "+str(log))

if MODE == "prepare":
    path = REPO / "tools/tripo-pipeline/blender/h2_bake/run_h2_bake.py"
    spec = importlib.util.spec_from_file_location("own_bounded_h2_runner",path)
    runner = importlib.util.module_from_spec(spec); spec.loader.exec_module(runner)
    runner.blender = launch  # preserve generic stage and reports, add only required process/threads controls
    sys.argv = [str(path),"--profile",str(OUT.parent/"build-profiles/patroclus-h2-bake-h2.json"),"--run-dir",str(OUT),"--stages","prepare","--blender",str(EXE)]
    runner.main()
else:
    script = OUT / ("measure_landmarks.py" if MODE == "measure" else "render_prepared_hp.py")
    launch(EXE,script,[],OUT/(MODE+".log"))
