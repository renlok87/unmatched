"""Launch one bounded headless subprocess, record exact command, exit and cleanup."""
import datetime
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import time

out = Path(__file__).resolve().parent
script_name = sys.argv[1] if len(sys.argv) > 1 else "scout_parts.py"
assert script_name in ("scout_parts.py", "scout_details.py")
stem = "scout" if script_name == "scout_parts.py" else "details"
cmd = [r"C:\Program Files\Blender Foundation\Blender 5.2\blender.exe", "--background", "--factory-startup", "--threads", "4", "--python-exit-code", "1", "--python", str(out / script_name)]
record = {"command": cmd, "cwd": str(out.parents[3]), "started_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(), "script_sha256": hashlib.sha256((out / script_name).read_bytes()).hexdigest()}
start = time.monotonic()
with (out / (stem + ".log")).open("w", encoding="utf-8") as log:
    proc = subprocess.Popen(cmd, cwd=out.parents[3], stdout=log, stderr=subprocess.STDOUT, creationflags=subprocess.CREATE_NO_WINDOW)
    record["pid"] = proc.pid
    record_path = out / ("process-record.json" if stem == "scout" else "details-process-record.json")
    record_path.write_text(json.dumps(record, indent=2), encoding="utf-8")
    try:
        record["exit_code"] = proc.wait(timeout=600)
    except subprocess.TimeoutExpired:
        # proc is exactly the process launched above; no name-based process cleanup.
        proc.kill()
        proc.wait()
        record["timed_out"] = True
        record["exit_code"] = proc.returncode
    finally:
        record["elapsed_s"] = round(time.monotonic() - start, 3)
        record["finished_utc"] = datetime.datetime.now(datetime.timezone.utc).isoformat()
        record["child_reaped"] = proc.poll() is not None
        record_path.write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")
print(json.dumps(record, indent=2))
raise SystemExit(record["exit_code"] != 0)
