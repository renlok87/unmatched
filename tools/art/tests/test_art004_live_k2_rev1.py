"""Tests of the thresholds.json revision rev1-t23 (stage 3, T2.3) in tools/art/art004_live_k2.py.

They run on the real T1.1 packaged-live frames (11 runs x host/joiner = 22 frames), the T1.2 Blender ID
renders and the T2.3 depth maps that are in the repository; nothing is written outside a temp dir.

  python -m unittest discover -s tools/art/tests -p test_art004_live_k2_rev1.py -v
"""
from __future__ import annotations

import argparse
import json
import math
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))

import art004_junction_zones as jz  # noqa: E402
import art004_live_k2 as k2  # noqa: E402

REPO = k2.REPO
E = REPO / "docs/game-design/evidence/ART-004"
RUNS = [E / r for r in (
    "live-v2-k2-control/5x-noflag/run-20260928-150841", "live-v2-k2-control/5x-noflag/run-20260928-150947",
    "live-v2-k2-control/5x-noflag/run-20260928-151054", "live-v2-k2-control/5x/run-20260928-151159",
    "live-v2-k2-control/5x/run-20260928-151427", "live-v2-k2-control/1p6/run-20260928-151640",
    "live-v2-k2-control/1p6/run-20260928-151853", "live-head-tilt-v3-k2/5x/run-20260928-151307",
    "live-head-tilt-v3-k2/5x/run-20260928-151532", "live-head-tilt-v3-k2/1p6/run-20260928-151748",
    "live-head-tilt-v3-k2/1p6/run-20260928-151959")]
V2_5X, V3_5X = RUNS[3], RUNS[7]
V3_1P6 = RUNS[9]
RECORD = E / "live-head-tilt-v3-k2/k2-metrics-rev1-t23.json"
REVIEW = E / "live-head-tilt-v3-k2/k2-placement-review-rev1-t23.json"
REGISTERED_RECORD = E / "live-head-tilt-v3-k2/k2-metrics.json"
T11_RECORD_SHA256 = "91d7f3fb5ece4a65465a5c4bcad41724790739c14588ac3199725dfe9706fa24"  # k2-metrics.json of T1.1 as in HEAD a2ed1e0
PERF_SUMMARY = E / "live-head-tilt-v3-k2/perf-summary.json"
V2_MESH, V3_MESH, V31_MESH = ("SK_Medusa_FaceNeck_v2Candidate", "SK_Medusa_HeadTilt_v3Candidate",
                              "SK_Medusa_HeadTilt_v31Candidate")

_CACHE: dict = {}


def rev():
    if "rev" not in _CACHE:
        _CACHE["rev"] = k2.load_threshold_set(k2.THRESHOLD_SET_REV1)
    return _CACHE["rev"]


def masks_cache():
    return _CACHE.setdefault("masks", {})


def shot(run: Path, role: str) -> dict:
    return k2.parse_shot((run / f"phase2-client-{role}.trace.log").read_text(encoding="utf-8-sig"))


def medusa_head(s: dict, role: str) -> dict:
    if role == "host":
        return next(h for h in s["heads"] if h["fighter"] == s["selected"])
    return next(h for h in s["heads"] if h["mesh"] in rev()["params"]["maskSources"]["meshes"])


def record_row(run: Path, role: str) -> dict:
    doc = _CACHE.setdefault("record", json.loads(RECORD.read_text(encoding="utf-8")))
    return next(r for r in doc["rows"] if r["run"] == k2.rel(run) and r["role"] == role)


class ThresholdRevisionRecord(unittest.TestCase):
    """revisions[] got a new «предложено» record; the registered values are untouched (E3)."""

    def test_revision_appended_originals_unchanged(self):
        doc = json.loads(k2.THRESHOLDS_JSON.read_text(encoding="utf-8"))
        self.assertEqual(doc["revisions"][0], {"date": "2026-09-28", "by": "T0 этапа 3",
                                               "what": "первая регистрация до любой съёмки этапа 3"})
        r = next(x for x in doc["revisions"] if x.get("id") == k2.THRESHOLD_SET_REV1)
        self.assertEqual(r["status"], "предложено")
        k201 = next(m for m in doc["E1_k2_live"]["metrics"] if m["id"] == "K2-01")
        self.assertIn("3 × экранной высоты головы", k201["definition"])
        perf02 = next(s for s in doc["perf"]["setups"] if s["id"] == "PERF-02")
        self.assertEqual(perf02["threshold"]["p95FrameTimeMsEach"], 33.3)
        for key in ("crop", "blenderView", "maskSources", "masks", "reprojectionPlane", "placementGate", "perf02"):
            self.assertIn(key, r["params"])
        self.assertEqual(r["params"]["crop"], {"centerDzUu": 12, "segmentDzUu": 24, "factor": 3, "minSidePx": 96})
        self.assertEqual(r["params"]["perf02"]["toleranceMs"], 0.5)
        self.assertEqual({m["id"] for m in r["E1_k2_live"]} >= {"K2-01", "K2-02", "K2-03", "K2-04"}, True)

    def test_threshold_set_selection(self):
        reg = k2.load_threshold_set(k2.THRESHOLD_SET_REGISTERED)
        self.assertEqual(reg["id"], "registered")
        self.assertIn("metrics", reg["E1_k2_live"])
        self.assertEqual(rev()["id"], "rev1-t23")
        with self.assertRaises(KeyError):
            k2.load_threshold_set("rev9-missing")

    def test_blender_view_is_the_t12_k2_camera(self):
        v = rev()["params"]["blenderView"]
        c55, s55 = math.cos(math.radians(55)), math.sin(math.radians(55))
        self.assertAlmostEqual(v["cameraM"][1], -3 * c55, places=6)
        self.assertAlmostEqual(v["cameraM"][2], 0.29 + 3 * s55, places=6)
        self.assertEqual((v["hfovDeg"], v["resolution"]), (35.0, [1920, 1080]))
        cam = k2.blender_camera_in_world(v, [0.0, -50.0, 0.0], 0.0)
        self.assertAlmostEqual(cam.pitch, -55.0, places=6)
        self.assertAlmostEqual(cam.yaw, -90.0, places=6)
        # the T1.2 socket (Blender metres, face -Y) is the traced socket in UE component space
        meas = json.loads((E / "head-tilt-v31-probe-2026-09-28/blender-measurements.json").read_text(encoding="utf-8"))
        local = k2.blender_m_to_ue_local(meas["head_socket"]["socket_source_m"])
        np.testing.assert_allclose(local, rev()["params"]["headSocketLocalUu"], atol=1e-9)


class CameraModelOnT11Frames(unittest.TestCase):
    """The board camera rebuilt from the trace reproduces the traced projections of all 22 frames."""

    def test_head_projection_all_frames(self):
        n = 0
        for run in RUNS:
            for role in ("host", "joiner"):
                s = shot(run, role)
                head = medusa_head(s, role)
                cam, chk = k2.ue_camera_from_trace(s, head)
                self.assertTrue(chk["ok"], (run.name, role, chk))
                self.assertLessEqual(max(chk["residualPx"].values()), k2.CAM_RESIDUAL_TOL_PX)
                # fighters are printed with %.0f: every projected fighter within rounding (+ model error)
                for fid, f in s["fighters"].items():
                    x, y, _ = cam.project(k2._vec(f["world"]))
                    sx, sy = k2._vec(f["screen"])
                    self.assertLessEqual(max(abs(x - sx), abs(y - sy)), 0.6, (run.name, role, fid))
                n += 1
        self.assertEqual(n, 22)

    def test_fitted_camera_matches_code_position(self):
        """Independent check: S08FlowGameMode puts the camera at focus + dist * (0, cos55, sin55); the focus is
        the selected hero cell + (0, 0, 28) (host, zoomed) or the board centre (joiner, overview)."""
        back = np.array([0.0, math.cos(math.radians(55)), math.sin(math.radians(55))])
        for run, role, tol in ((V3_5X, "host", 0.15), (V3_1P6, "host", 0.35), (V3_5X, "joiner", 0.7)):
            s = shot(run, role)
            head = medusa_head(s, role)
            cam, _ = k2.ue_camera_from_trace(s, head)
            dist = float(s["camera"]["dist"])
            focus = (np.array(k2._vec(s["fighters"][s["selected"]]["world"])) + [0.0, 0.0, 28.0]
                     if role == "host" else np.zeros(3))
            self.assertLessEqual(float(np.linalg.norm(cam.C - (focus + dist * back))), tol, (run.name, role))

    def test_wrong_rotation_refused(self):
        s = shot(V3_5X, "host")
        s["ctx"] = dict(s["ctx"], rot="(-45,-90,0)")
        with self.assertRaises(ValueError):
            k2.ue_camera_from_trace(s, medusa_head(s, "host"))


class MaskSources(unittest.TestCase):
    """Per-variant masks: provenance checks and identity with the T1.2 measurements."""

    def test_v2_v3_masks_match_t12_measurements(self):
        meas = json.loads((E / "head-tilt-v31-probe-2026-09-28/blender-measurements.json").read_text(encoding="utf-8"))
        for mesh, tag in ((V2_MESH, "v2"), (V3_MESH, "v3")):
            src = k2.load_mask_source(mesh, rev()["params"], masks_cache())
            self.assertTrue(src["ok"], src["problems"])
            self.assertEqual(src["fbxSha256"], src["importFbxSha256"])
            views = meas["part_id_views"][tag]
            self.assertEqual(src["gapPxAtRender"], views["k2-front-d300"]["face_x_collar"]["enclosed_gap_px"])
            self.assertEqual(src["classPxAtRender"]["features"],
                             views["idsplit-k2-front-d300"]["facial_features_z_ge_42_px"])
            self.assertEqual(src["classPxAtRender"]["crown"], views["idsplit-k2-front-d300"]["crown_px"])
            self.assertGreaterEqual(src["depth"]["alphaAgreement"], 0.9999)
        self.assertEqual(masks_cache()[V2_MESH]["gapPxAtRender"], 95)
        self.assertEqual(masks_cache()[V3_MESH]["gapPxAtRender"], 137)

    def test_gap_mask_is_the_junction_zones_metric(self):
        from PIL import Image
        im = np.array(Image.open(E / "head-tilt-v31-probe-2026-09-28/id-cull-k2-front-d300-v3.png").convert("RGBA"))
        self.assertEqual(int(k2.junction_gap_mask(im, 3).sum()), jz.enclosed_gap(im, 3)["enclosed_gap_px"])

    def test_v31_refused_without_import_report_and_unknown_mesh(self):
        src = k2.load_mask_source(V31_MESH, rev()["params"])
        self.assertFalse(src["ok"])
        self.assertTrue(any("отчёта импорта" in p for p in src["problems"]))
        self.assertFalse(k2.load_mask_source("SK_Unknown", rev()["params"])["ok"])


class DepthReprojection(unittest.TestCase):
    """Round trip: rendered surface points -> live frame (T1.1 cameras) -> back to the Blender render."""

    def test_round_trip_5x_1p6_1x(self):
        p = rev()["params"]
        src = k2.load_mask_source(V3_MESH, p, masks_cache())
        raw, filled = src["depthFull"]
        lab = src["label"]
        ys, xs = np.nonzero(~np.isnan(raw))
        pick = np.random.default_rng(7).choice(len(ys), 3000, replace=False)
        jb, ib = ys[pick], xs[pick]
        for run, role, min_ok in ((V3_5X, "host", 0.995), (V3_1P6, "host", 0.99), (V3_5X, "joiner", 0.99)):
            s = shot(run, role)
            head = medusa_head(s, role)
            ue, _ = k2.ue_camera_from_trace(s, head)
            W = np.array(k2._vec(s["fighters"][head["fighter"]]["world"]))
            bl = k2.blender_camera_in_world(p["blenderView"], W, 0.0)
            P = bl.C + raw[jb, ib][:, None] * bl.rays(ib + 0.5, jb + 0.5)
            xu, yu, _ = ue.project(P)
            rp = p["reprojectionPlane"]
            plane = (k2.fighter_to_world(rp["pointLocalUu"], W, 0.0), k2.fighter_dir_to_world(rp["normalLocal"], 0.0))
            xb, yb, _ = k2.live_to_blender(ue, bl, plane, xu, yu, (raw, filled), 8, 96)
            err = np.hypot(xb - (ib + 0.5), yb - (jb + 0.5))
            same = lab[np.clip(np.floor(yb).astype(int), 0, 1079), np.clip(np.floor(xb).astype(int), 0, 1919)] == lab[jb, ib]
            self.assertGreaterEqual(float((err <= 1.0).mean()), min_ok, (run.name, role))
            self.assertGreaterEqual(float(same.mean()), min_ok, (run.name, role))
            # without depth (plane only) the error is several Blender px: the depth pass is needed
            xb0, yb0, _ = k2.live_to_blender(ue, bl, plane, xu, yu, None)
            self.assertGreater(float(np.percentile(np.hypot(xb0 - (ib + 0.5), yb0 - (jb + 0.5)), 99)), 2.0)


class RevisionMetricsOnT11Frames(unittest.TestCase):
    """revision_frame() on real frames reproduces the recorded k2-metrics-rev1-t23.json."""

    def check_row(self, run, role):
        row = k2.revision_frame(run, role, rev(), masks_cache())
        self.assertNotIn("error", row, row.get("error"))
        rec = record_row(run, role)
        self.assertEqual(row["K2_01_crop"], rec["K2_01_crop"])
        for key in ("K2_02", "K2_03", "K2_04"):
            self.assertEqual(row[key].get("value"), rec[key].get("value"), (run.name, role, key))
        self.assertTrue(row["registration"]["ok"])
        self.assertEqual(row["registration"]["bestShift"], [0, 0])
        self.assertTrue(row["socketCheck"]["ok"])
        return row

    def test_5x_host_v2_v3(self):
        r2 = self.check_row(V2_5X, "host")
        r3 = self.check_row(V3_5X, "host")
        self.assertEqual(r3["K2_01_crop"]["box"], [782, 281, 1139, 638])
        self.assertEqual(r3["K2_01_crop"]["side"], 357)  # 3 x |proj(Head+24) - proj(Head)| = 3 x 119.1 px
        self.assertEqual(r3["mesh"], V3_MESH)
        self.assertEqual(r2["maskSource"]["tag"], "v2")
        self.assertGreater(r3["K2_02"]["value"], r2["K2_02"]["value"])   # v3 face >= v2
        self.assertGreater(r3["K2_04"]["value"], r2["K2_04"]["value"])   # v3 see-through > v2 (P1)

    def test_joiner_overview_face_too_small(self):
        r = self.check_row(V3_5X, "joiner")
        self.assertEqual(r["zoomTag"], "1x")
        self.assertIsNone(r["K2_02"]["value"])
        self.assertEqual(r["K2_02"]["status"], k2.REV_SMALL)

    def test_yaw180_figure_refused(self):
        with tempfile.TemporaryDirectory() as td:
            dst = Path(td) / "run"
            dst.mkdir()
            for name in ("phase2-board-host-1920x1080.png", "art-preview-status.json"):
                shutil.copy2(V3_5X / name, dst / name)
            tr = (V3_5X / "phase2-client-host.trace.log").read_text(encoding="utf-8-sig")
            (dst / "phase2-client-host.trace.log").write_text(
                tr.replace("SHOT fighter f-0-hero pos=(2,2) world=(0,-50,0)", "SHOT fighter f-0-hero pos=(2,2) world=(0,50,0)"),
                encoding="utf-8")
            row = k2.revision_frame(dst, "host", rev(), masks_cache())
            self.assertIn("yaw 180", row["error"])


class RecordedRecompute(unittest.TestCase):
    """The recorded recompute of the 22 T1.1 frames and its placement gate."""

    def test_record(self):
        doc = json.loads(RECORD.read_text(encoding="utf-8"))
        self.assertEqual(doc["thresholdSet"], "rev1-t23")
        self.assertEqual(doc["frames"], {"total": 22, "withMasks": 22, "roles": ["host", "joiner"]})
        self.assertTrue(all("error" not in r and r["registration"]["ok"] for r in doc["rows"]))
        self.assertEqual({(c["role"], c["zoomTag"]) for c in doc["comparisons"]},
                         {("host", "5x"), ("host", "1p6"), ("joiner", "1x")})
        c5 = next(c for c in doc["comparisons"] if c["zoomTag"] == "5x")
        self.assertTrue(c5["K2_02"]["counted"] and c5["K2_02"]["v3VsV2Holds"])
        self.assertFalse(c5["K2_04"]["v3VsV2Holds"])
        for ov in doc["overlays"]:
            self.assertEqual(k2.sha256_file(REPO / ov["file"]), ov["sha256"])
        # the T1.1 record is not rewritten by the revision (task: separate file, k2-metrics.json unchanged)
        self.assertEqual(k2.sha256_file(REGISTERED_RECORD), T11_RECORD_SHA256)

    def test_placement_gate(self):
        doc = json.loads(RECORD.read_text(encoding="utf-8"))
        ov = next(o for o in doc["overlays"] if o["zoomTag"] == "5x")
        review = k2.load_placement_review(str(REVIEW))
        self.assertEqual(k2.placement_verdict({}, ov, "faceMaskOnFace"), (False, k2.REV_PENDING))
        self.assertTrue(k2.placement_verdict(review, ov, "faceMaskOnFace")[0])
        bad_sha = dict(ov, sha256="0" * 64)
        self.assertFalse(k2.placement_verdict(review, bad_sha, "faceMaskOnFace")[0])
        neg = {"entries": {ov["file"]: {"sha256": ov["sha256"], "faceMaskOnFace": {"face-neck-v2": True,
                                                                                  "head-tilt-v3": False}}}}
        self.assertEqual(k2.placement_verdict(neg, ov, "faceMaskOnFace"), (False, k2.REV_PLACEMENT_FAILED))


class Perf02(unittest.TestCase):
    """PERF-02 on the T1.1 perf-summary.json: the registered 33.3 ms is below the cap period."""

    def test_perf02(self):
        reg = k2.load_threshold_set(k2.THRESHOLD_SET_REGISTERED)
        doc = k2.perf02_evaluate(json.loads(PERF_SUMMARY.read_text(encoding="utf-8")), rev(), reg)
        self.assertEqual(len(doc["clients"]), 22)
        self.assertEqual(doc["passCounts"]["registered"]["trace"], 0)
        self.assertEqual(doc["passCounts"]["revisedPeriodPlusTol"], {"trace": 22, "csv": 22, "n": 22})
        self.assertEqual(doc["passCounts"]["t11_periodPlus1pct"]["csv"], 12)
        self.assertTrue(doc["revisedPass"])
        self.assertAlmostEqual(doc["clients"][0]["limits"]["revisedPeriodPlusTol"], 1000 / 30 + 0.5, places=3)
        just = next(r for r in json.loads(k2.THRESHOLDS_JSON.read_text(encoding="utf-8"))["revisions"]
                    if r.get("id") == "rev1-t23")["perf"]["justification"]
        self.assertEqual(just["traceP95Ms"], doc["ranges"]["traceP95Ms"])
        self.assertEqual(just["csvP95Ms"], doc["ranges"]["csvP95Ms"])


class RegisteredPathUnchanged(unittest.TestCase):
    """--threshold-set registered (default) still gives the T1.1 numbers of k2-metrics.json."""

    def test_registered_numbers(self):
        with tempfile.TemporaryDirectory() as td:
            out = Path(td) / "k2-metrics.json"
            a = argparse.Namespace(out=str(out), run_dirs=[str(r) for r in RUNS], threshold_set="registered")
            import contextlib
            import io
            with contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(k2.cmd_metrics(a), 0)
            new = json.loads(out.read_text(encoding="utf-8"))
        old = json.loads(REGISTERED_RECORD.read_text(encoding="utf-8"))
        self.assertEqual(new["noise"], old["noise"])
        self.assertEqual(len(new["rows"]), len(old["rows"]))
        for a_, b_ in zip(new["rows"], old["rows"]):
            self.assertEqual(a_["run"], b_["run"])
            self.assertEqual(a_["K2_01_crop"]["box"], b_["K2_01_crop"]["box"])
            self.assertEqual(a_["K2_01_crop"]["sha256"], b_["K2_01_crop"]["sha256"])
            self.assertEqual(a_["K2_02"]["formalValueRegisteredBand"], b_["K2_02"]["formalValueRegisteredBand"])
            self.assertEqual(a_["K2_03"]["formalValueRegisteredBand"], b_["K2_03"]["formalValueRegisteredBand"])
        self.assertEqual([c["v2VsV3MeanAbsDeltaRGB"] for c in new["comparisons"]],
                         [c["v2VsV3MeanAbsDeltaRGB"] for c in old["comparisons"]])


if __name__ == "__main__":
    unittest.main()
