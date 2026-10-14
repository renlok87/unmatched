"""RB-11 / F47 (skill pilot 2026-10-13): CLI entry points print UTF-8 even when the pipe is cp1251.

In the agents' Bash tool `sys.stdout.encoding` is cp1251. h2anim_run.py prints the warn/fail contact checks, and 11 of
the 14 warn/fail checks of the pilot carry «×» (e.g. skin_stretch), which cp1251 cannot encode: the run died with
UnicodeEncodeError before it wrote reports/h2anim-run.json. Every entry point now reconfigures stdout/stderr to UTF-8
first (errors="backslashreplace").

1. h2anim_run.main() in a child Python with PYTHONIOENCODING=cp1251; Blender is replaced by a fake that writes
   validate/contact reports (a warn check with «×»): the run prints it, writes h2anim-run.json and exits 0.
2. The other entry points of the RB-11 list reconfigure before they parse arguments (source check).

Run from the repo root:  python -m pytest tools/tripo-pipeline/tests/test_utf8_console.py -q
"""

import json
import os
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

TOOL = Path(__file__).resolve().parents[1]
REPO = TOOL.parents[1]
ANIM = TOOL / "anim"

DRIVER = r'''
import json, sys
from pathlib import Path
anim, root = sys.argv[1], Path(sys.argv[2]).resolve()
sys.path.insert(0, anim)
import h2anim_run as h
h.REPO = root
h.VAL_DIR = root / "val"

def fake_blender(script, *args, timeout=1800):
    out = next(str(a)[len("--out="):] for a in args if str(a).startswith("--out="))
    if script == "validate_clip.py":
        rep = {"result": "pass", "fails": 0, "warnings": 0, "checks": []}
    else:
        rep = {"result": "pass", "fails": 0, "checks": [
            {"check": "skin_stretch", "status": "warn", "detail": "stretch ×1.31 > ×1.25"}]}
    Path(out).write_text(json.dumps(rep, ensure_ascii=False), encoding="utf-8")
    return {"code": 0, "seconds": 0.0, "lines": []}

h.blender = fake_blender
sys.argv = ["h2anim_run.py", str(root / "spec.json"), "--no-author", "--no-probe"]
h.main()
'''

# entry point -> the function that must reconfigure before it parses arguments
ENTRY_POINTS = {
    "tools/tripo-pipeline/anim/h2anim_run.py": "main",
    "tools/tripo-pipeline/anim/h2anim_ue.py": "main",
    "tools/tripo-pipeline/tripo_pipeline.py": "main",
    "tools/tripo-pipeline/review/base_seethrough.py": "host_main",
    "tools/art/visual/ledger.py": "main",
    "tools/art/material_library/ue_hero_lookdev.py": "main",
    "tools/art/material_library/ue_lock.py": "main",
    "tools/s08/cue_contract/cue_contract.py": "main",
    "tools/art/render_fingerprint.py": "main",
}


class Utf8ConsoleTests(unittest.TestCase):
    def test_h2anim_run_prints_times_sign_into_a_cp1251_pipe(self):
        self.assertRaises(UnicodeEncodeError, "×".encode, "cp1251")   # the premise of F47
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp).resolve()
            spec = {"run_dir": "run", "ue_hero": "Probe", "character": "Probe",
                    "clips": {"Idle": {"frames": 24, "role": "idle"}}}
            (root / "spec.json").write_text(json.dumps(spec), encoding="utf-8")
            env = dict(os.environ, PYTHONIOENCODING="cp1251", PYTHONUTF8="0")
            proc = subprocess.run([sys.executable, "-c", DRIVER, str(ANIM), str(root)], capture_output=True,
                                  env=env, timeout=120)
            err = proc.stderr.decode("utf-8", "replace")
            self.assertNotIn("UnicodeEncodeError", err)
            self.assertEqual(proc.returncode, 0, err)
            self.assertIn("×1.31", proc.stdout.decode("utf-8"))
            summary = json.loads((root / "run/reports/h2anim-run.json").read_text(encoding="utf-8"))
            self.assertTrue(summary["clips"]["Idle"]["passed"])

    def test_entry_points_reconfigure_before_parsing(self):
        for rel, func in ENTRY_POINTS.items():
            with self.subTest(entry=rel):
                src = (REPO / rel).read_text(encoding="utf-8")
                m = re.search(r"^def %s\(.*?(?=^def |^if __name__)" % func, src, re.S | re.M)
                self.assertIsNotNone(m, "%s: def %s() not found" % (rel, func))
                body = m.group(0)
                fix = body.find('reconfigure(encoding="utf-8", errors="backslashreplace")')
                self.assertGreater(fix, 0, "%s: %s() does not reconfigure stdout/stderr to UTF-8" % (rel, func))
                parse = body.find("parse_args(")
                self.assertTrue(parse < 0 or fix < parse, "%s: reconfigure comes after parse_args" % rel)


if __name__ == "__main__":
    unittest.main()
