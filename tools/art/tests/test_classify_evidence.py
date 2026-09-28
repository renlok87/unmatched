"""Tests for tools/art/classify_evidence.py.

Self-test (required by stage 3 / T0): 3 known positives from the repository
and 1 negative (an editor PNG renamed as a live host frame). The synthetic
cases below pin the individual rules without touching the repository: every
fixture is written into a temporary directory and removed afterwards.

  python -m unittest discover -s tools/art/tests -v
"""
from __future__ import annotations

import contextlib
import hashlib
import io
import json
import shutil
import struct
import sys
import tempfile
import unittest
import zlib
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))

import classify_evidence as ce  # noqa: E402

REPO = ce.REPO_ROOT
EXE = "a" * 64


def png_bytes(width: int = 1920, height: int = 1080, text: dict | None = None, salt: bytes = b"") -> bytes:
    def chunk(kind: bytes, body: bytes) -> bytes:
        return struct.pack(">I", len(body)) + kind + body + struct.pack(">I", zlib.crc32(kind + body) & 0xFFFFFFFF)
    out = b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0))
    for k, v in (text or {}).items():
        out += chunk(b"tEXt", k.encode("latin-1") + b"\x00" + v.encode("latin-1"))
    if salt:
        out += chunk(b"tEXt", b"Comment\x00" + salt)
    return out + chunk(b"IEND", b"")


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


TRACE = """2026.09.28-01.38.55 --- S08 trace open 2026.09.28-01.38.55 ---
2026.09.28-01.39.13 BOARD 5x6 cells | control points
2026.09.28-01.39.13 ARTPREVIEW fighter=Medusa hero=1 eligible=1 visual=1 mesh=SK_Medusa_FaceNeck_v2Candidate
2026.09.28-01.39.13 FIGHTERS synced n=6 alive=6 own=4 enemy=2
2026.09.28-01.39.25 SHOT ctx viewport=1920x1080 viewTarget=CameraActor_1 cam=(0,171,344) rot=(-55,-90,0)
2026.09.28-01.39.25 SHOT requested: FScreenshotRequest(bShowUI) -> C:\\Temp\\s08\\phase2-board-host-1920x1080.png
2026.09.28-01.39.33 --- S08 trace close ---
"""


class LiveRun:
    """A synthetic live run directory: live-synthetic/run-20260928-000000/."""

    def __init__(self, root: Path, png: bytes | None = None, trace: str = TRACE):
        self.dir = root / "live-synthetic" / "run-20260928-000000"
        self.dir.mkdir(parents=True)
        self.png = self.dir / "phase2-board-host-1920x1080.png"
        self.png.write_bytes(png or png_bytes())
        self.trace = self.dir / "phase2-client-host.trace.log"
        self.trace.write_bytes(trace.replace("\n", "\r\n").encode("utf-8"))
        self.write_manifest()

    def write_manifest(self, png_sha: str | None = None, trace_sha: str | None = None) -> None:
        files = [
            {"name": self.trace.name, "sha256": trace_sha or sha(self.trace.read_bytes())},
            {"name": self.png.name, "sha256": png_sha or sha(self.png.read_bytes())},
        ]
        (self.dir / "manifest.json").write_text(json.dumps({"stamp": "x", "files": files}), encoding="utf-8")

    def write_sidecar(self, **over) -> None:
        doc = {
            "schema": ce.SIDECAR_SCHEMA, "class": "packaged-live", "frameSha256": sha(self.png.read_bytes()),
            "build": {"exeSha256": EXE, "stagedInnerExeSha256": EXE, "result": "Succeeded",
                      "flags": ["-WaitMutex", "-NoXGE", "-NoUBA", "-MaxParallelActions=2"]},
            "run": {"roomStatus": "ABORTED", "boardId": "cmuhgs4b2001mwik4f2b2xtf8"},
        }
        for k, v in over.items():
            doc[k] = {**doc[k], **v} if isinstance(v, dict) else v
        self.png.with_name(self.png.stem + ".evidence.json").write_text(json.dumps(doc), encoding="utf-8")


class SelfTest(unittest.TestCase):
    """3 positive + 1 negative cases on real repository evidence."""

    def test_positive_packaged_live(self):
        r = ce.classify_frame(REPO / ce.SELF_TEST_CASES[0][1])
        self.assertEqual(r["class"], "packaged-live")
        self.assertFalse(r["rejected"])
        self.assertEqual(r["grade"], "legacy")  # historical run: no build/run sidecar
        self.assertEqual(r["live"]["trace"]["binding"], "shot-requested")
        self.assertEqual(r["live"]["trace"]["mesh"], "SK_Medusa_FaceNeck_v2Candidate")

    def test_positive_editor_mcp_viewport(self):
        r = ce.classify_frame(REPO / ce.SELF_TEST_CASES[1][1])
        self.assertEqual(r["class"], "editor-mcp-viewport")
        self.assertTrue(any("MCP capture markers" in b for b in r["basis"]))

    def test_positive_blender(self):
        r = ce.classify_frame(REPO / ce.SELF_TEST_CASES[2][1])
        self.assertEqual(r["class"], "blender")
        self.assertTrue(r["basis"][0].startswith("R1 png-metadata"))

    def test_negative_renamed_editor_png(self):
        with tempfile.TemporaryDirectory() as tmp:
            fake = Path(tmp) / "phase2-board-host-1920x1080.png"
            shutil.copyfile(REPO / ce.NEGATIVE_SOURCE, fake)
            r = ce.classify_frame(fake)
        self.assertNotEqual(r["class"], "packaged-live")
        self.assertTrue(r["rejected"])

    def test_cli_self_test_exit_code(self):
        ok, results = ce.self_test()
        self.assertTrue(ok, results)
        self.assertEqual([c["case"] for c in results], ["positive", "positive", "positive", "negative"])


class SyntheticRules(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="classify-evidence-test-"))

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_live_legacy_then_strict_with_sidecar(self):
        run = LiveRun(self.tmp)
        r = ce.classify_frame(run.png)
        self.assertEqual((r["class"], r["grade"]), ("packaged-live", "legacy"))
        self.assertEqual(r["live"]["missingStrict"], ["S4_sidecar_build_run"])
        run.write_sidecar()
        r = ce.classify_frame(run.png, expect_mesh="SK_Medusa_FaceNeck_v2Candidate")
        self.assertEqual((r["class"], r["grade"]), ("packaged-live", "strict"))

    def test_strict_rejects_nolivecoding_and_stub_exe(self):
        run = LiveRun(self.tmp)
        run.write_sidecar(build={"flags": ["-NoLiveCoding"]})
        self.assertEqual(ce.classify_frame(run.png)["grade"], "legacy")
        run.write_sidecar(build={"stagedInnerExeSha256": "b" * 64})
        self.assertEqual(ce.classify_frame(run.png)["grade"], "legacy")

    def test_expect_mesh_mismatch_is_not_strict(self):
        run = LiveRun(self.tmp)
        run.write_sidecar()
        r = ce.classify_frame(run.png, expect_mesh="SK_Medusa_HeadTilt_v31Candidate")
        self.assertEqual(r["grade"], "legacy")
        self.assertIn("S3_artpreview_mesh", r["live"]["missingStrict"])

    def test_manifest_sha_mismatch_rejected(self):
        run = LiveRun(self.tmp)
        run.write_manifest(png_sha="0" * 64)
        r = ce.classify_frame(run.png)
        self.assertTrue(r["rejected"])
        self.assertNotEqual(r["class"], "packaged-live")

    def test_trace_hash_mismatch_rejected(self):
        run = LiveRun(self.tmp)
        run.write_manifest(trace_sha="0" * 64)
        self.assertTrue(ce.classify_frame(run.png)["rejected"])

    def test_trace_without_board_rejected(self):
        run = LiveRun(self.tmp, trace="\n".join(l for l in TRACE.splitlines() if "BOARD" not in l) + "\n")
        r = ce.classify_frame(run.png)
        self.assertTrue(r["rejected"])
        self.assertTrue(any("board" in x for x in r["reasons"]))

    def test_editor_png_swapped_into_live_run_rejected(self):
        run = LiveRun(self.tmp)
        shutil.copyfile(REPO / ce.NEGATIVE_SOURCE, run.png)  # manifest still holds the original sha
        r = ce.classify_frame(run.png)
        self.assertTrue(r["rejected"])
        self.assertNotEqual(r["class"], "packaged-live")

    def test_blender_render_named_live_rejected(self):
        run = LiveRun(self.tmp, png=png_bytes(text={"RenderTime": "00:00.03", "Scene": "Scene", "Camera": "Cam"}))
        r = ce.classify_frame(run.png)
        self.assertEqual(r["class"], "blender")
        self.assertTrue(r["rejected"])

    def test_live_named_frame_without_manifest_rejected(self):
        d = self.tmp / "live-x" / "run-20260928-000001"
        d.mkdir(parents=True)
        p = d / "k2.png"
        p.write_bytes(png_bytes())
        r = ce.classify_frame(p)
        self.assertTrue(r["claimsLive"])
        self.assertTrue(r["rejected"])

    def test_cli_report_in_same_dir(self):
        d = self.tmp / "probe"
        d.mkdir()
        p = d / "medusa-k2-headtiltprobe.png"
        p.write_bytes(png_bytes(salt=b"cli"))
        (d / "medusa-k2-report.json").write_text(json.dumps({
            "level": "/Game/X", "output": "C:\\A\\Artifacts\\ART004Face\\medusa-k2-headtiltprobe.png",
            "camera_location": [0, 1, 2], "scene_saved": False}), encoding="utf-8")
        self.assertEqual(ce.classify_frame(p)["class"], "editor-cli")

    def test_sidecar_declares_editor_class(self):
        p = self.tmp / "frame.png"
        p.write_bytes(png_bytes(salt=b"side"))
        p.with_name("frame.evidence.json").write_text(json.dumps({
            "schema": ce.SIDECAR_SCHEMA, "class": "editor-mcp-viewport", "frameSha256": sha(p.read_bytes())}),
            encoding="utf-8")
        self.assertEqual(ce.classify_frame(p)["class"], "editor-mcp-viewport")

    def test_sidecar_cannot_declare_packaged_live(self):
        p = self.tmp / "frame.png"
        p.write_bytes(png_bytes(salt=b"side2"))
        p.with_name("frame.evidence.json").write_text(json.dumps({
            "schema": ce.SIDECAR_SCHEMA, "class": "packaged-live", "frameSha256": sha(p.read_bytes())}),
            encoding="utf-8")
        self.assertNotEqual(ce.classify_frame(p)["class"], "packaged-live")

    def test_require_exit_codes(self):
        run = LiveRun(self.tmp)

        def cli(*args: str) -> int:
            with contextlib.redirect_stdout(io.StringIO()):
                return ce.main([str(run.dir), *args])
        self.assertEqual(cli("--require", "packaged-live"), 0)
        self.assertEqual(cli("--require", "packaged-live", "--strict"), 3)
        run.write_sidecar()
        self.assertEqual(cli("--require", "packaged-live", "--strict"), 0)


class RepositoryExtras(unittest.TestCase):
    """Further real evidence (read-only) that pins classes beyond the self-test."""

    def test_s05_staged_frame(self):
        r = ce.classify_frame(REPO / "docs/game-design/evidence/S05/art-references/frames/frame-K3-combat.png")
        self.assertEqual(r["class"], "packaged-staged")
        self.assertFalse(r["rejected"])

    def test_s08_run_is_live_legacy(self):
        r = ce.classify_frame(REPO / "docs/game-design/evidence/S08/run/run-20260926-010051/phase2-board-host-1920x1080.png")
        self.assertEqual((r["class"], r["grade"]), ("packaged-live", "legacy"))
        self.assertIn("S2_viewport_matches_png_1080p", r["live"]["missingStrict"])  # SHOT ctx 888x500


if __name__ == "__main__":
    unittest.main()
