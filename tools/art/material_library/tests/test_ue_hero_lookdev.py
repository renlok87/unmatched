"""Tests of ue_hero_lookdev.py without an editor (wave 2 of the 3d-model-pipeline skill rework, W2-b): apply-mi (RC-10),
settle of the review frames (F153) and the luma noise band (F155).

  python -m pytest tools/art/material_library/tests/test_ue_hero_lookdev.py -q
"""
from __future__ import annotations

import base64
import contextlib
import hashlib
import io
import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

import numpy as np
from PIL import Image

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))

import ue_hero_lookdev as U  # noqa: E402
import ue_live  # noqa: E402  (imported by ue_hero_lookdev: tools/tripo-pipeline/review)
import ue_lock  # noqa: E402


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


# ------------------------------------------------------------------ F155 noise band
class NoiseBandTest(unittest.TestCase):
    def test_f155_bronze_does_not_flip(self):
        # the same zone measured 1.159 and 1.118 in two editor sessions (tolerance 0.15): one verdict, not two
        self.assertEqual(U.luma_state(1.159, 0.15), "noise_band")
        self.assertEqual(U.luma_state(1.118, 0.15), "noise_band")

    def test_clear_cases(self):
        self.assertEqual(U.luma_state(1.0, 0.15), "within")
        self.assertEqual(U.luma_state(1.10, 0.15), "within")
        self.assertEqual(U.luma_state(1.25, 0.15), "off")
        self.assertEqual(U.luma_state(0.80, 0.15), "off")
        self.assertEqual(U.luma_state(0.86, 0.15), "noise_band")
        self.assertEqual(U.luma_state(1.159, 0.15, band=0.0), "off")

    def test_within_to_off_needs_more_than_twice_the_band(self):
        for yr in np.linspace(0.6, 1.5, 181):
            s = U.luma_state(float(yr), 0.15)
            for k in (0.96, 1.04):
                t = U.luma_state(float(yr) * k, 0.15)
                self.assertFalse({s, t} == {"within", "off"}, (yr, k, s, t))

    def test_zone_state_and_verdicts(self):
        self.assertEqual(U.zone_state("within", True, False), "off")
        self.assertEqual(U.zone_state("noise_band", True, True), "noise_band")
        self.assertEqual(U.zone_verdict(False, True), "board light")
        self.assertEqual(U.zone_verdict(True, False), "off on the reading exposure only")


# ------------------------------------------------------------------ F153 settle
class SettleTest(unittest.TestCase):
    def test_status_of_reports(self):
        self.assertEqual(U.settle_status(None)["status"], "unknown")
        good = {"warmup_mean_abs_diff": [1.2, 0.6, 0.5, 0.5],
                "frames": {"front-neutral": {"settle_mean_abs_diff": [0.8, 0.5, 0.4]},
                           "k2-5x-p1": {"settle_mean_abs_diff": [0.9, 1.52]}}}
        st = U.settle_status(good)
        self.assertEqual(st["status"], "settled")
        self.assertEqual(st["unsettled_other_shots"], ["k2-5x-p1"])  # K2 shot: a warning only
        bad_warm = dict(good, warmup_mean_abs_diff=[2.3, 2.8, 2.6])  # Ancient Leshen r1-r3
        self.assertEqual(U.settle_status(bad_warm)["status"], "not_settled")
        bad_shot = dict(good, frames={"side-debug": {"settle_mean_abs_diff": [1.9, 1.3, 1.2]}})
        st = U.settle_status(bad_shot)
        self.assertEqual((st["status"], st["unsettled_measured_shots"]), ("not_settled", ["side-debug"]))

    def test_warm_up_waits_for_convergence(self):
        it = iter([0, 40, 80, 81, 81, 81, 81, 81, 81])
        diffs, ok = U.warm_up(lambda: Image.new("RGB", (4, 4), (next(it),) * 3),
                              dict(U.SETTLE, min_diffs=6, max_diffs=8), sleep=lambda s: None)
        self.assertTrue(ok)
        self.assertEqual(len(diffs), 6)  # waited for min_diffs although converged at 4
        it2 = iter([(i % 2) * 2 for i in range(20)])
        diffs, ok = U.warm_up(lambda: Image.new("RGB", (4, 4), (next(it2),) * 3),
                              dict(U.SETTLE, min_diffs=3, max_diffs=5), sleep=lambda s: None)
        self.assertEqual((ok, len(diffs)), (False, 5))


def png_b64(level):
    buf = io.BytesIO()
    Image.new("RGB", (32, 18), (level,) * 3).save(buf, "PNG")
    return base64.b64encode(buf.getvalue()).decode()


class ShotUe:
    def __init__(self, levels):
        self.levels = iter(levels)
        self.grabs = 0

    def run_task(self, script, out, timeout=600, **kw):
        return {}

    def call(self, toolset, tool, args=None, record=True):
        assert (toolset, tool) == ("app", "CaptureViewport")
        self.grabs += 1
        return {"value": {"image": {"data": png_b64(next(self.levels))}}}


class ShotExtraGrabsTest(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="lookdev-shot-"))

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def shot(self, levels, extra):
        ue = ShotUe(levels)
        ss = U.Session(ue, self.tmp, "t", "Hero", extra_grabs=extra)
        view = {"eye": [0, 250, 29], "rot": [0, -90, 0], "yaw": 90.0, "kind": "front"}
        with mock.patch.object(U.time, "sleep"):
            ss.shot("front-neutral", view, {"variant": "neutral"})
        return ue, ss.frames["front-neutral"]

    def test_unsettled_shot_regrabs_until_settled(self):
        ue, info = self.shot([0, 10, 20, 30, 31, 31, 31], extra=6)
        self.assertEqual(ue.grabs, 5)  # 4 grabs (diffs 10, 10, 10) + 1 extra (diff 1.0 <= threshold)
        self.assertEqual(info["settle_mean_abs_diff"], [10.0, 10.0, 10.0, 1.0])
        self.assertTrue(info["settled"])

    def test_former_fixed_grabs_without_extra(self):
        ue, info = self.shot([0, 10, 20, 30], extra=0)
        self.assertEqual(ue.grabs, 4)
        self.assertFalse(info["settled"])


# ------------------------------------------------------------------ measure: noise band + settle in the report
class MeasureTest(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="lookdev-measure-"))
        (self.tmp / "frames").mkdir()

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def frame(self, name, regions):
        a = np.zeros((64, 64, 3), np.uint8)
        for (r0, r1, c0, c1), col in regions:
            a[r0:r1, c0:c1] = col
        Image.fromarray(a).save(self.tmp / "frames" / ("hero-t1-front-%s.png" % name))

    def test_zone_in_the_noise_band_is_not_decided_and_settle_is_reported(self):
        A, B = (5, 30, 5, 30), (34, 59, 34, 59)
        ca, cb = (180, 140, 120), (120, 150, 180)
        self.frame("plate", [])
        self.frame("debug", [(A, (200, 40, 40)), (B, (40, 200, 40))])
        for var in ("neutral", "reading"):
            self.frame(var, [(A, ca), (B, cb)])
        stats = U.hsv_stats(np.array([cb], np.uint8))
        # a concept 'linen' that puts the UE zone at a Y ratio between 1.15 / 1.04 and 1.15 / 0.96
        cbc, yr = None, None
        for s in np.linspace(0.90, 0.97, 71):
            c = tuple(int(round(x * s)) for x in cb)
            y = stats["luma_Y_linear"] / U.hsv_stats(np.array([c], np.uint8))["luma_Y_linear"]
            if 1.15 / 1.04 < y < 1.15 / 0.96 and abs(y - 1.15) > 0.01:
                cbc, yr = c, y
                break
        self.assertIsNotNone(cbc)
        concept = {"zones": {"skin": {"concept": U.hsv_stats(np.array([ca], np.uint8))},
                             "linen": {"concept": U.hsv_stats(np.array([cbc], np.uint8))}}}
        (self.tmp / "concept.json").write_text(json.dumps(concept), encoding="utf-8")
        cfg = {"hero": "Hero", "variants": {"neutral": "/Game/MI_N", "debug": "/Game/MI_D"},
               "zones": ["skin", "linen"], "key_zones": ["skin"], "anchor_zone": "skin",
               "tolerance_zones": ["skin", "linen"], "tolerance": {"luma_ratio": 0.15, "hue_deg": 12.0, "sat": 0.1},
               "concept_zones": (self.tmp / "concept.json").as_posix(), "min_px": 100,
               "debug_calibration": {"13": [200, 40, 40], "10": [40, 200, 40]}}
        (self.tmp / "review-t1.json").write_text(json.dumps({"warmup_mean_abs_diff": [2.4, 2.5, 2.3], "frames": {}}),
                                                 encoding="utf-8")
        with contextlib.redirect_stdout(io.StringIO()):
            res = U.cmd_measure(SimpleNamespace(out=str(self.tmp), tag="t1"), cfg)
        d = res["exposure"]["neutral"]["deltas"]
        self.assertAlmostEqual(d["linen"]["Y_ratio_exposure_normalised"], yr, places=2)
        self.assertEqual(d["linen"]["luma_state"], "noise_band")
        self.assertEqual(d["skin"]["state"], "within")
        self.assertEqual(res["verdicts"]["zones"], {"skin": "within both", "linen": "noise band: neutral + reading"})
        self.assertIn(res["verdicts"]["zones_hard"]["linen"], ("within both", "off on both"))
        self.assertEqual(res["measurement_status"], "not_settled")
        self.assertFalse(res["settle"]["warmup_converged"])


# ------------------------------------------------------------------ apply-mi (RC-10)
F = "/Game/PipelineCandidates/Hero/H2LD"


def names():
    n = {"skeletal": F + "/Meshes/SK_Hero_H2LD", "base": F + "/Meshes/SM_Hero_H2LD_Base",
         "figure_instance": F + "/Materials/MI_Hero_H2LD", "base_instance": F + "/Materials/MI_Hero_H2LD_Base",
         "extra:MI_Hero_H2LD_Neutral": F + "/Materials/MI_Hero_H2LD_Neutral"}
    for t in ("P1", "P2"):
        n["team:figure:" + t] = F + "/Materials/MI_Hero_H2LD_" + t
        n["team:base:" + t] = F + "/Materials/MI_Hero_H2LD_Base_" + t
    for k in ("BC", "N", "ORM", "MatID", "LUT"):
        n["texture:" + k] = F + "/Textures/T_Hero_" + k
    return n


def profile(lut_rel, lut_sha, **ue_over):
    tex = {k: {"file_key": k, "asset": "T_Hero_" + k, "srgb": k == "BC", "compression": "TC_Default"}
           for k in ("BC", "N", "ORM", "MatID")}
    tex["LUT"] = {"file_key": "LUT", "asset": "T_Hero_LUT", "srgb": False, "compression": "TC_HDR",
                  "properties": {"Filter": "TF_Nearest", "MipGenSettings": "TMGS_NoMipmaps", "NeverStream": True}}
    ue = {"skeletal_asset": "SK_Hero_H2LD", "base_asset": "SM_Hero_H2LD_Base",
          "target_skeleton": "/Game/PipelineCandidates/Hero/Rig/SK_Hero_Skeleton", "material_route": "um-master",
          "masters": {"figure": "/Game/UM/Materials/v2/M_UM_Figure_v2", "base": "/Game/UM/Materials/M_UM_BaseMarker"},
          "figure_instance": "MI_Hero_H2LD", "base_instance": "MI_Hero_H2LD_Base",
          "teams": {"P1": "#E8C06A", "P2": "#5A7F9F"},
          "team_instances": {"figure": "MI_Hero_H2LD_{team}", "base": "MI_Hero_H2LD_Base_{team}"},
          "team_color_mode": "none", "figure_parameters": {"TeamDye": 1.0, "TeamDyeGain": 22.5, "Saturation": 1.2},
          "figure_textures": {"MatIDTexture": "MatID", "MatLUT": "LUT"},
          "figure_static_switches": {"UseUV1Metres": True},
          "extra_instances": [{"asset": "MI_Hero_H2LD_Neutral", "parent": "figure_instance", "scalars": {"TeamDye": 0.0},
                               "vectors": {"TeamColor": {"linear": [1.0, 1.0, 1.0, 1.0]}}}],
          "base_marker": {"textures": True, "parameters": {"SideBandWeight": 1.0}}, "textures": tex}
    ue.update(ue_over)
    return {"candidate": {"dir": "cand", "fbx": {"skeletal": "export/SK.fbx", "base": "export/SM.fbx"},
                          "textures": {k: "tex/%s.png" % k for k in ("BC", "N", "ORM", "MatID")},
                          "library_inputs": {"LUT": {"path": lut_rel, "sha256": lut_sha}}}, "ue": ue}


class ApplyUe:
    """The editor side of apply-mi: MI values, the LUT texture's import data, and the apply op."""

    def __init__(self, plan, lut_source, lut_stamp=None):
        self.mi = {w["asset"]: {"parent": w["parent"], "scalars": dict(w["scalars"]), "vectors": dict(w["vectors"]),
                                "textures": {k: v.split(".")[0] for k, v in w["textures"].items()},
                                "switches": dict(w.get("switches") or {})} for w in plan.values()}
        self.lut = {"source_files": [lut_source], "sha_stamp": lut_stamp}
        self.ops = []

    def call(self, toolset, tool, args=None, record=True):
        return "/Game/S08/S08Arena.S08Arena"

    def run_task(self, script, out, timeout=600, **kw):
        self.ops.append((kw["op"], json.loads(json.dumps(kw))))
        if kw["op"] == "read":
            inst = {}
            for p, n in kw["instances"].items():
                m = self.mi[p]
                inst[p] = {"parent": m["parent"], **{s: {k: m[s].get(k) for k in n[s]} for s in
                                                     ("scalars", "vectors", "textures", "switches")}}
            return {"instances": inst, "textures": {p: dict(self.lut) for p in kw["textures"]}, "dirty_after": []}
        if kw["op"] == "apply":
            saved = {}
            for p, ch in kw["changes"].items():
                for s, vals in ch.items():
                    self.mi[p][s].update(vals)
                saved[p] = True
            if kw["lut"]:
                self.lut = {"source_files": [kw["lut"]["source_file"]], "sha_stamp": kw["lut"]["sha256"]}
                saved[kw["lut"]["asset"]] = True
            return {"saved": saved, "dirty_after": []}
        raise AssertionError(kw["op"])


class ApplyMiTest(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="lookdev-apply-mi-"))
        self.repo0 = U.REPO
        U.REPO = self.tmp
        for rel, data in (("cand/export/SK.fbx", b"sk"), ("cand/export/SM.fbx", b"sm"), ("lut/r1.dds", b"lut-r1"),
                          ("lut/r2.dds", b"lut-r2"), ("cand2/tex/BC.png", b"other bc")):
            (self.tmp / rel).parent.mkdir(parents=True, exist_ok=True)
            (self.tmp / rel).write_bytes(data)
        for k in ("BC", "N", "ORM", "MatID"):
            (self.tmp / "cand/tex").mkdir(parents=True, exist_ok=True)
            (self.tmp / ("cand/tex/%s.png" % k)).write_bytes(k.encode())
        self.names = names()
        run = self.tmp / "run"
        (run / "reports").mkdir(parents=True)
        self.p1 = profile("lut/r1.dds", sha(self.tmp / "lut/r1.dds"))
        (self.tmp / "profiles").mkdir()
        (self.tmp / "profiles/p1.json").write_text(json.dumps(self.p1), encoding="utf-8")
        (run / "manifest.json").write_text(json.dumps({"config": {"build_profile": "profiles/p1.json"}}), encoding="utf-8")
        (run / "reports/ue-import-report.json").write_text(json.dumps({"destination": {"assets": self.names}}),
                                                           encoding="utf-8")
        keys = U.profile_inputs(self.p1)
        self.adopt = {"keys": keys, "inputs": {p: sha(self.tmp / p) for p in keys.values()}}
        (run / "reports/adopt-report.json").write_text(json.dumps(self.adopt), encoding="utf-8")
        self.cfg = {"hero": "Hero", "run_dir": "run"}

    def tearDown(self):
        U.REPO = self.repo0
        shutil.rmtree(self.tmp, ignore_errors=True)

    def apply(self, fake, **kw):
        @contextlib.contextmanager
        def no_lock(step, *a, **k):
            yield {"step": step, "waited_s": 0.0, "stale_taken": None, "waits": 0}
        a = SimpleNamespace(out=str(self.tmp / "out"), tag="m1", profile=None, dry_run=False, no_verify=True)
        for k, v in kw.items():
            setattr(a, k, v)
        with mock.patch.object(ue_live, "Ue", lambda: fake), mock.patch.object(ue_lock, "ue_lock", no_lock), \
                contextlib.redirect_stdout(io.StringIO()):
            return U.cmd_apply_mi(a, self.cfg)

    def test_plan_is_the_cli_plan(self):
        plan = U.plan_instances(self.p1, self.names)
        fig = plan["figure_instance"]
        self.assertEqual(fig["parent"], "/Game/UM/Materials/v2/M_UM_Figure_v2")
        self.assertEqual(fig["scalars"], {"Saturation": 1.2, "TeamDye": 1.0, "TeamDyeGain": 22.5})
        self.assertEqual(fig["textures"]["MatLUT"], F + "/Textures/T_Hero_LUT")
        self.assertEqual(plan["team:figure:P1"]["vectors"]["TeamColor"], [0.806952, 0.527115, 0.144128, 1.0])
        self.assertEqual(plan["team:figure:P1"]["parent"], F + "/Materials/MI_Hero_H2LD")
        self.assertEqual(plan["extra:MI_Hero_H2LD_Neutral"]["scalars"], {"TeamDye": 0.0})

    def test_current_values_change_nothing(self):
        fake = ApplyUe(U.plan_instances(self.p1, self.names), (self.tmp / "lut/r1.dds").as_posix())
        rep = self.apply(fake)
        self.assertTrue(rep["passed"], rep["checks"])
        self.assertEqual(rep["changes"], {})
        self.assertIsNone(rep["applied"])
        self.assertEqual([o for o, _ in fake.ops], ["read", "read"])
        self.assertFalse(rep["lut"]["reimport"])

    def test_new_scalar_and_lut_go_onto_the_existing_mis(self):
        fake = ApplyUe(U.plan_instances(self.p1, self.names), (self.tmp / "lut/r1.dds").as_posix())
        p2 = json.loads(json.dumps(self.p1))
        p2["ue"]["figure_parameters"]["Saturation"] = 1.3
        p2["ue"]["teams"]["P2"] = "#4A6F8F"
        p2["candidate"]["library_inputs"]["LUT"] = {"path": "lut/r2.dds", "sha256": sha(self.tmp / "lut/r2.dds")}
        (self.tmp / "profiles/p2.json").write_text(json.dumps(p2), encoding="utf-8")
        rep = self.apply(fake, profile=str(self.tmp / "profiles/p2.json"))
        self.assertTrue(rep["passed"], rep["checks"])
        apply_kw = [kw for o, kw in fake.ops if o == "apply"][0]
        self.assertEqual(apply_kw["changes"][F + "/Materials/MI_Hero_H2LD"], {"scalars": {"Saturation": 1.3}})
        self.assertEqual(sorted(apply_kw["changes"]), [F + "/Materials/MI_Hero_H2LD", F + "/Materials/MI_Hero_H2LD_Base_P2",
                                                       F + "/Materials/MI_Hero_H2LD_P2"])
        self.assertEqual(apply_kw["lut"]["asset"], F + "/Textures/T_Hero_LUT")
        self.assertEqual(apply_kw["lut"]["settings"], {"srgb": False, "compression_settings": "TC_HDR",
                                                       "filter": "TF_Nearest", "mip_gen_settings": "TMGS_NoMipmaps",
                                                       "never_stream": True})
        self.assertTrue(rep["checks"]["only_changed_packages_saved"]["passed"])
        self.assertEqual(fake.mi[F + "/Materials/MI_Hero_H2LD"]["scalars"]["Saturation"], 1.3)
        # a second run is a no-op (the LUT now carries its sha stamp)
        rep2 = self.apply(fake, profile=str(self.tmp / "profiles/p2.json"))
        self.assertEqual((rep2["changes"], rep2["applied"], rep2["lut"]["how"]), ({}, None, "sha stamp"))

    def test_dry_run_changes_nothing(self):
        fake = ApplyUe(U.plan_instances(self.p1, self.names), (self.tmp / "lut/r1.dds").as_posix())
        p2 = json.loads(json.dumps(self.p1))
        p2["ue"]["figure_parameters"]["TeamDyeGain"] = 30.0
        (self.tmp / "profiles/p2.json").write_text(json.dumps(p2), encoding="utf-8")
        rep = self.apply(fake, profile=str(self.tmp / "profiles/p2.json"), dry_run=True)
        self.assertEqual(rep["changes"], {F + "/Materials/MI_Hero_H2LD": {"scalars": {"TeamDyeGain": 30.0}}})
        self.assertNotIn("apply", [o for o, _ in fake.ops])

    def test_new_texture_or_structure_is_refused(self):
        p2 = json.loads(json.dumps(self.p1))
        p2["candidate"]["textures"]["BC"] = "../cand2/tex/BC.png"
        why = U.apply_mi_refusals(self.p1, p2, self.adopt, self.names)
        self.assertEqual(len(why), 1)
        self.assertIn("texture:BC", why[0])
        p3 = json.loads(json.dumps(self.p1))
        p3["ue"]["extra_instances"].append({"asset": "MI_Hero_H2LD_DebugClass", "scalars": {"DebugView": 1.0}})
        self.assertIn("ue.extra_instances: other MIs or parents", U.apply_mi_refusals(self.p1, p3, self.adopt, self.names))
        p4 = json.loads(json.dumps(self.p1))
        p4["candidate"]["library_inputs"]["LUT"]["path"] = "lut/r2.dds"
        p4["ue"]["figure_parameters"]["Saturation"] = 2.0
        self.assertEqual(U.apply_mi_refusals(self.p1, p4, self.adopt, self.names), [])
        (self.tmp / "profiles/p2.json").write_text(json.dumps(p2), encoding="utf-8")
        with self.assertRaises(SystemExit) as cm:
            self.apply(ApplyUe(U.plan_instances(self.p1, self.names), "x"), profile=str(self.tmp / "profiles/p2.json"))
        self.assertIn("ue-import-package.md", str(cm.exception))

    def test_verify_overlay_takes_the_planned_values(self):
        plan = U.plan_instances(self.p1, self.names)
        cfg = {"verify": {"instances": {"figure_instance": {"parent": "x", "scalars": {"TeamDye": 1.0, "TeamDyeGain": 1.0},
                                                            "switches": {"UseTeamAccent": True}}}}}
        out = U.verify_overlay(cfg, plan)["verify"]["instances"]["figure_instance"]
        self.assertEqual(out["scalars"]["TeamDyeGain"], 22.5)
        self.assertEqual(out["scalars"]["Saturation"], 1.2)
        self.assertTrue(out["switches"]["UseTeamAccent"])  # kept: inherited expectation of the hand-written config
        self.assertEqual(cfg["verify"]["instances"]["figure_instance"]["scalars"]["TeamDyeGain"], 1.0)  # copy


if __name__ == "__main__":
    unittest.main()
