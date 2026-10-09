"""New-character bench scene (.agents/skills/3d-model-pipeline/references/new-character-registration.md D-2):
tools/art/render/env_bench_fixtures.cts --variant (seat 1 re-cast on f-1-hero / f-1-sk0) and
tools/art/render/live_tune.py bench --fixture / --dry-run. No UE, no GPU lock.

  python -B -m pytest -q tools/art/tests/test_bench_fixture_variant.py
"""
from __future__ import annotations

import contextlib
import copy
import io
import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO / "tools" / "art" / "render"))
import live_tune as LT  # noqa: E402

BENCH = REPO / "unreal/Unmatched/Config/Bench"
TS_NODE = REPO / "backend/node_modules/ts-node/dist/bin.js"
GENERATOR = REPO / "tools/art/render/env_bench_fixtures.cts"
CANON = {"marmoreal": "S08BenchMarmoreal.json", "sarpedon": "S08BenchSarpedon.json"}
RECAST = ("f-1-hero", "f-1-sk0")


def run_generator(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(["node", str(TS_NODE), "--transpile-only", "-P", str(REPO / "backend/tsconfig.json"), str(GENERATOR),
                           *args], cwd=str(REPO), capture_output=True, text=True, timeout=180)


def state_of(doc: dict) -> dict:
    return json.loads(doc["raw"]["data"]["gameState"]["state"])


@unittest.skipUnless(shutil.which("node") and TS_NODE.exists(), "node + backend/node_modules/ts-node required")
class GeneratorVariant(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.out = Path(cls.tmp.name)
        cls.gen = run_generator("--variant", "Perseus", "--hero-name", "Perseus", "--hero-slug", "perseus",
                                "--sidekick-name", "Pegasus", "--out-dir", str(cls.out))

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def test_writes_one_variant_per_real_board(self):
        self.assertEqual(self.gen.returncode, 0, self.gen.stderr)
        self.assertEqual(sorted(p.name for p in self.out.iterdir()),
                         ["S08BenchMarmoreal-Perseus.json", "S08BenchSarpedon-Perseus.json"])

    def test_variant_equals_template_except_the_recast(self):
        for map_key, name in CANON.items():
            base = json.loads((BENCH / name).read_text(encoding="utf-8"))
            var = json.loads((self.out / name.replace(".json", "-Perseus.json")).read_text(encoding="utf-8"))
            # root: the same keys in the same order plus benchVariant; only source differs among the shared ones
            self.assertEqual([k for k in var if k != "benchVariant"], list(base))
            for k in base:
                if k not in ("source", "raw"):
                    self.assertEqual(var[k], base[k], f"{map_key} {k}")
            self.assertEqual(var["benchVariant"], {"key": "Perseus", "base": name, "heroName": "Perseus",
                                                   "heroSlug": "perseus", "sidekickName": "Pegasus",
                                                   "recast": list(RECAST)})
            self.assertTrue(var["source"].startswith(f"Variant Perseus of {name}"))
            # the game state: identical but name / heroSlug of the two seat-1 fighters
            gs_b = dict(base["raw"]["data"]["gameState"])
            gs_v = dict(var["raw"]["data"]["gameState"])
            sb, sv = json.loads(gs_b.pop("state")), json.loads(gs_v.pop("state"))
            self.assertEqual(gs_v, gs_b)
            want = copy.deepcopy(sb)
            for f in want["fighters"]:
                if f["id"] == "f-1-hero":
                    f.update(name="Perseus", heroSlug="perseus")
                elif f["id"] == "f-1-sk0":
                    f.update(name="Pegasus", heroSlug="perseus")
            self.assertEqual(sv, want, map_key)
            # positions, ids and the board did not move
            self.assertEqual(sv["boardState"], sb["boardState"])
            self.assertEqual([(f["id"], f["position"]) for f in sv["fighters"]],
                             [(f["id"], f["position"]) for f in sb["fighters"]])

    def test_check_covers_the_variants_and_catches_drift(self):
        r = run_generator("--check", "--out-dir", str(self.out))
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("marmoreal variant=Perseus ok", r.stdout)
        self.assertIn("sarpedon variant=Perseus ok", r.stdout)
        self.assertIn("marmoreal ok S08BenchMarmoreal.json", r.stdout)
        with tempfile.TemporaryDirectory() as t2:
            bad = Path(t2) / "S08BenchSarpedon-Perseus.json"
            doc = json.loads((self.out / bad.name).read_text(encoding="utf-8"))
            st = state_of(doc)
            st["fighters"][0]["position"] = {"x": 0, "y": 0}
            doc["raw"]["data"]["gameState"]["state"] = json.dumps(st, separators=(",", ":"))
            bad.write_text(json.dumps(doc, indent=1) + "\n", encoding="utf-8")
            r = run_generator("--check", "--out-dir", t2)
            self.assertEqual(r.returncode, 1, r.stdout)
            self.assertIn("sarpedon variant=Perseus DRIFT", r.stdout)

    def test_without_sidekick_name_merlin_stays(self):
        with tempfile.TemporaryDirectory() as t2:
            r = run_generator("--variant", "Solo", "--hero-name", "Solo Hero", "--hero-slug", "solo-hero", "--maps", "marmoreal",
                              "--out-dir", t2)
            self.assertEqual(r.returncode, 0, r.stderr)
            self.assertEqual([p.name for p in Path(t2).iterdir()], ["S08BenchMarmoreal-Solo.json"])
            doc = json.loads((Path(t2) / "S08BenchMarmoreal-Solo.json").read_text(encoding="utf-8"))
            fs = {f["id"]: f for f in state_of(doc)["fighters"]}
            self.assertEqual((fs["f-1-hero"]["name"], fs["f-1-hero"]["heroSlug"]), ("Solo Hero", "solo-hero"))
            self.assertEqual((fs["f-1-sk0"]["name"], fs["f-1-sk0"]["heroSlug"]), ("Merlin", "solo-hero"))
            self.assertNotIn("sidekickName", doc["benchVariant"])

    def test_usage_errors(self):
        for args in (["--variant", "bad-key", "--hero-name", "X", "--hero-slug", "x"],
                     ["--variant", "Ok", "--hero-slug", "x"],
                     ["--variant", "Ok", "--hero-name", "X", "--hero-slug", "Not_A_Slug"],
                     ["--variant", "Ok", "--hero-name", "X", "--hero-slug", "x", "--maps", "cobble"],
                     ["--check", "--variant", "Ok"],
                     ["--bogus"]):
            with tempfile.TemporaryDirectory() as t2:
                r = run_generator(*args, "--out-dir", t2)
                self.assertEqual(r.returncode, 2, f"{args}: {r.stdout} {r.stderr}")
                self.assertEqual(list(Path(t2).iterdir()), [], f"{args} wrote files")


class LiveTuneFixture(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        base = json.loads((BENCH / CANON["sarpedon"]).read_text(encoding="utf-8"))
        self.var = self.root / "S08BenchSarpedon-Perseus.json"
        self.var.write_text(json.dumps({**base, "benchVariant": {"key": "Perseus"}}), encoding="utf-8")

    def tearDown(self):
        self.tmp.cleanup()

    def test_default_is_unchanged(self):
        for mode, map_key, want in (("packaged", "marmoreal", "../../../Unmatched/Config/Bench/S08BenchMarmoreal.json"),
                                    ("editor", "sarpedon", str(REPO / "unreal/Unmatched/Config/Bench/S08BenchSarpedon.json"))):
            args = LT.bench_args(mode, map_key, Path("C:/tmp/lt/b"), "K1", LT.BENCH[mode], [])
            self.assertEqual([a for a in args if a.startswith("-BenchFixture=")], [f"-BenchFixture={want}"])

    def test_variant_sources(self):
        empty = self.root / "none.txt"
        v, info = LT.resolve_fixture("editor", "sarpedon", str(self.var), empty)
        self.assertEqual((v, info["source"], info["variant"]), (str(self.var.resolve()), "worktree", "Perseus"))
        v, info = LT.resolve_fixture("packaged", "sarpedon", str(self.var), empty)
        self.assertEqual((v, info["source"]), (self.var.resolve().as_posix(), "loose"))
        # a Config/Bench file the staged build lists: the pak copy (by name)
        manifest = self.root / "m.txt"
        manifest.write_text("Unmatched/Config/Bench/S08BenchMarmoreal.json\t2026-10-06T03:03:04.516Z\n", encoding="utf-8")
        v, info = LT.resolve_fixture("packaged", "marmoreal", "S08BenchMarmoreal.json", manifest)
        self.assertEqual((v, info["source"]), ("../../../Unmatched/Config/Bench/S08BenchMarmoreal.json", "pak"))
        v, info = LT.resolve_fixture("packaged", "marmoreal", "S08BenchMarmoreal.json", empty)
        self.assertEqual(info["source"], "loose", "not staged -> the loose worktree file")

    def test_usage_errors_exit_2(self):
        for kw in ({"map_key": "marmoreal", "fixture": str(self.var)},
                   {"map_key": "sarpedon", "fixture": str(self.root / "missing.json")}):
            with self.assertRaises(LT.LiveTuneError) as cm:
                LT.resolve_fixture("editor", **kw)
            self.assertEqual(cm.exception.code, 2)
        with self.assertRaises(LT.LiveTuneError) as cm:
            LT.bench_args("editor", "sarpedon", self.root, "K1", LT.BENCH["editor"], ["-BenchFixture=x.json"])
        self.assertEqual(cm.exception.code, 2)
        spaced = self.root / "with space"
        spaced.mkdir()
        shutil.copy(self.var, spaced / self.var.name)
        with self.assertRaises(LT.LiveTuneError) as cm:
            LT.resolve_fixture("editor", "sarpedon", str(spaced / self.var.name))
        self.assertEqual(cm.exception.code, 2)

    def test_cli_dry_run_launches_nothing(self):
        out = self.root / "run"
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            rc = LT.main(["bench", "--map", "sarpedon", "--views", "K1+K2x1.6", "--out", str(out), "--packaged",
                          "--fixture", str(self.var), "--extra=-BenchFocusFighter=f-1-hero", "--dry-run"])
        self.assertEqual(rc, 0)
        res = json.loads(buf.getvalue())
        self.assertTrue(res["dryRun"])
        self.assertEqual(res["fixture"]["variant"], "Perseus")
        self.assertIn(f"-BenchFixture={self.var.resolve().as_posix()}", res["args"])
        self.assertIn("-BenchFocusFighter=f-1-hero", res["args"])
        self.assertFalse(out.exists(), "a dry run makes no out folder")
        with contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(LT.main(["bench", "--map", "marmoreal", "--views", "K1", "--out", str(out),
                                      "--fixture", str(self.var), "--dry-run"]), 2)


if __name__ == "__main__":
    unittest.main()
