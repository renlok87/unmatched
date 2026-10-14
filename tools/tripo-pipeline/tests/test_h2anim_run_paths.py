"""h2anim_run.py: --out-dir and paths outside the repository (review gap R-13, 2026-10-14).

The smoke run of stage 3 (animation-vfx-sfx.md §6.6) keeps everything in <bake run>/work/smoke/. Before the fix
h2anim_run.py wrote the validate reports into docs/art-pipeline/animation-library/validation-h2anim/ (VAL_DIR fixed) and
died on relative_to(REPO) for a spec or run_dir outside the repository. Blender is replaced by a fake that writes the
validate / contact reports; the default VAL_DIR is redirected into the temp dir, so a regression cannot touch docs/.

    python -m pytest tools/tripo-pipeline/tests/test_h2anim_run_paths.py -q
"""
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

TOOL = Path(__file__).resolve().parents[1]
ANIM = TOOL / "anim"

DRIVER = r'''
import json, sys
from pathlib import Path
anim, val_default = sys.argv[1], sys.argv[2]
sys.path.insert(0, anim)
import h2anim_run as h
h.VAL_DIR = Path(val_default)

def fake_blender(script, *args, timeout=1800):
    out = next(str(a)[len("--out="):] for a in args if str(a).startswith("--out="))
    rep = {"result": "pass", "fails": 0, "warnings": 0, "checks": []}
    Path(out).write_text(json.dumps(rep), encoding="utf-8")
    return {"code": 0, "seconds": 0.0, "lines": []}

h.blender = fake_blender
sys.argv = ["h2anim_run.py"] + sys.argv[3:]
h.main()
'''


class H2AnimRunPathsTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name).resolve()
        self.smoke = self.root / "bake-run" / "work" / "smoke"
        self.smoke.mkdir(parents=True)
        self.val_default = self.root / "default-validation-h2anim"
        spec = {"run_dir": (self.smoke / "run").as_posix(), "ue_hero": "ProbeSmoke", "character": "Probe",
                "clips": {"Idle": {"frames": 24, "role": "idle"}, "HitReact": {"frames": 12, "role": "hit"}}}
        self.spec = self.smoke / "probe-h2anim-smoke.json"
        self.spec.write_text(json.dumps(spec), encoding="utf-8")

    def tearDown(self):
        self._tmp.cleanup()

    def run_tool(self, *args):
        env = dict(os.environ, PYTHONIOENCODING="utf-8")
        p = subprocess.run([sys.executable, "-c", DRIVER, str(ANIM), str(self.val_default), str(self.spec),
                            "--no-author", "--no-probe", *args], capture_output=True, env=env, timeout=120)
        self.assertEqual(p.returncode, 0, p.stderr.decode("utf-8", "replace"))
        return json.loads((self.smoke / "run/reports/h2anim-run.json").read_text(encoding="utf-8"))

    def test_spec_run_and_out_dir_outside_the_repo(self):
        out = self.smoke / "validation"
        summary = self.run_tool("--out-dir", str(out))
        for clip in ("Idle", "HitReact"):
            self.assertTrue((out / ("AM_ProbeSmoke_%s.validation.json" % clip)).is_file(), clip)
            entry = summary["clips"][clip]
            self.assertTrue(entry["passed"])
            self.assertEqual(entry["validate"]["report"], (out / ("AM_ProbeSmoke_%s.validation.json" % clip)).as_posix())
            self.assertEqual(entry["contact"]["report"], (self.smoke / ("run/reports/contact-%s.json" % clip)).as_posix())
        self.assertEqual(summary["spec"], self.spec.as_posix())
        self.assertEqual(summary["validation_dir"], out.as_posix())
        self.assertFalse(self.val_default.exists(), "the default validation dir was written")

    def test_default_dir_and_val_dir_alias(self):
        summary = self.run_tool()
        self.assertTrue((self.val_default / "AM_ProbeSmoke_Idle.validation.json").is_file())
        self.assertEqual(summary["validation_dir"], self.val_default.as_posix())
        alias = self.root / "alias"
        self.run_tool("--clips=Idle", "--val-dir", str(alias))
        self.assertTrue((alias / "AM_ProbeSmoke_Idle.validation.json").is_file())

    def test_rel_and_compact_sheet_outside_the_repo(self):
        from PIL import Image

        sys.path.insert(0, str(ANIM))
        try:
            import h2anim_run as h
        finally:
            sys.path.remove(str(ANIM))
        self.assertEqual(h.rel(h.REPO / "docs" / "x.json"), "docs/x.json")
        frames = self.smoke / "run" / "preview" / "frames"
        frames.mkdir(parents=True)
        Image.new("RGB", (40, 30), (1, 2, 3)).save(frames / "ProbeSmoke-Idle-sheet.png")
        (frames / "ProbeSmoke-Idle-f00-front.png").write_bytes(b"png")
        got = h.compact_sheet(self.smoke / "run", "ProbeSmoke-Idle")
        jpg = self.smoke / "run" / "preview" / "ProbeSmoke-Idle-blender-sheet.jpg"
        self.assertEqual(got, jpg.as_posix())
        self.assertTrue(jpg.is_file())
        self.assertEqual(sorted(p.name for p in frames.iterdir()), [])


if __name__ == "__main__":
    unittest.main()
