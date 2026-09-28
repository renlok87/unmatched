#!/usr/bin/env python3
"""Probe: does Blender itself make Python's faulthandler print "Windows fatal exception: access violation"?

    python art/pipeline-candidates/ASSET-HARPY-001/scripts/probe_blender_exit_faulthandler.py \
        --out art/pipeline-candidates/ASSET-HARPY-001/20260928-blender-um-fbx-v1/reports/blender-exit-faulthandler-probe.json

Why: the first Harpy build log (build_harpy_candidate.py with faulthandler.enable()) ended with 25 such lines
after the stage marker, although Blender exited 0 and the FBX were byte-identical to later runs. This probe runs
`blender -b --factory-startup` N times with a script that does nothing but (a) enable faulthandler, or (b) not,
and records per run: exit code, number of access-violation reports, the thread they were reported on versus the
main thread, and their position between the end of the script and Python's atexit (start of finalisation).
No project data is read or written; the temporary probe script lives in a TemporaryDirectory.
"""

import argparse
import json
import re
import subprocess
import sys
import tempfile
from pathlib import Path

DEFAULT_BLENDER = "C:/Program Files/Blender Foundation/Blender 5.2/blender.exe"
PROBE = r'''
import atexit, os, sys, threading
if sys.argv[-1] == "fh":
    import faulthandler
    faulthandler.enable()
os.write(2, ("PROBE_SCRIPT_END main_thread=0x%08x\n" % threading.get_ident()).encode())
atexit.register(lambda: os.write(2, b"PROBE_PY_ATEXIT\n"))
'''


def run_once(blender, script, mode):
    proc = subprocess.run([blender, "-b", "--factory-startup", "--python", str(script), "--", mode],
                          stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=300,
                          creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    text = proc.stdout.decode("utf-8", "replace")
    lines = text.splitlines()
    main = re.search(r"main_thread=(0x[0-9a-f]+)", text)
    end = next((i for i, l in enumerate(lines) if l.startswith("PROBE_SCRIPT_END")), None)
    atexit_line = next((i for i, l in enumerate(lines) if l.startswith("PROBE_PY_ATEXIT")), None)
    av = [i for i, l in enumerate(lines) if "Windows fatal exception: access violation" in l]
    threads = sorted(set(re.findall(r"Thread (0x[0-9a-f]+)", text)))
    return {
        "exit_code": proc.returncode,
        "access_violation_reports": len(av),
        "reported_threads": threads,
        "main_thread": main.group(1) if main else None,
        "all_on_main_thread": bool(av) and threads == ([main.group(1)] if main else []),
        "all_after_script_end_before_py_atexit": (bool(av) and end is not None and atexit_line is not None
                                                  and all(end < i < atexit_line for i in av)),
        "blender_quit_line": "Blender quit" in text,
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    ap.add_argument("--blender", default=DEFAULT_BLENDER)
    ap.add_argument("--runs", type=int, default=8)
    args = ap.parse_args()
    version = subprocess.run([args.blender, "-b", "--factory-startup", "--version"], stdout=subprocess.PIPE,
                             stderr=subprocess.STDOUT, timeout=120,
                             creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0)).stdout.decode("utf-8", "replace")
    result = {"blender": version.splitlines()[0].strip() if version else None,
              "probe_script": PROBE.strip().splitlines(), "runs": {}}
    with tempfile.TemporaryDirectory() as tmp:
        script = Path(tmp) / "probe_exit.py"
        script.write_text(PROBE, encoding="utf-8")
        for mode in ("fh", "nofh"):
            result["runs"]["faulthandler_on" if mode == "fh" else "faulthandler_off"] = [
                run_once(args.blender, script, mode) for _ in range(args.runs)]
    on, off = result["runs"]["faulthandler_on"], result["runs"]["faulthandler_off"]
    with_av = [r for r in on if r["access_violation_reports"]]
    result["summary"] = {
        "faulthandler_on": {"runs": len(on), "runs_with_reports": len(with_av),
                            "reports_min_max": [min(r["access_violation_reports"] for r in on),
                                                max(r["access_violation_reports"] for r in on)],
                            "exit_codes": sorted(set(r["exit_code"] for r in on)),
                            "reports_all_on_main_thread": all(r["all_on_main_thread"] for r in with_av),
                            "reports_all_between_script_end_and_py_atexit":
                                all(r["all_after_script_end_before_py_atexit"] for r in with_av)},
        "faulthandler_off": {"runs": len(off),
                             "runs_with_reports": sum(1 for r in off if r["access_violation_reports"]),
                             "exit_codes": sorted(set(r["exit_code"] for r in off))},
    }
    result["conclusion"] = (
        "With an empty script, Blender reports first-chance access violations on its main thread during its own "
        "exit (after the script, before Python finalisation) only when faulthandler is on, and exits 0: Windows "
        "faulthandler logs exceptions from a vectored handler, i.e. before the process's own exception handlers "
        "deal with them (the process goes on to atexit and exits 0). "
        "They do not come from the Harpy build; the build keeps faulthandler off unless --faulthandler is given."
        if with_av and result["summary"]["faulthandler_on"]["reports_all_on_main_thread"]
        and result["summary"]["faulthandler_on"]["reports_all_between_script_end_and_py_atexit"]
        and result["summary"]["faulthandler_off"]["runs_with_reports"] == 0
        and set(r["exit_code"] for r in on + off) == {0}
        else "inconclusive: see runs")
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(result["summary"], sort_keys=True))
    print(result["conclusion"])
    return 0


if __name__ == "__main__":
    sys.exit(main())
