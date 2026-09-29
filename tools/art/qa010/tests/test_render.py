"""W4-A: `qa010 render` and the ALL.render_reference checklist row.

A K1..K3 frame counts only when its SHOT block carries a RENDER fingerprint
equal to docs/art-pipeline/render-reference.json (user decision 2026-09-28:
DX12/SM6 + Lumen, High). Pre-W4 frames (no fingerprint) and off-reference
frames (DX11, SM5 fallback, sg.* != 2, ...) are rejected.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))  # qa010 dir, any discovery root

import json
import tempfile
import unittest

from tests._util import REPO, run_cli
from qa010lib.checklist import build_checklist

REFERENCE = REPO / "docs" / "art-pipeline" / "render-reference.json"


def render_line(**over) -> str:
    ref = json.loads(REFERENCE.read_text(encoding="utf-8"))
    kv = {k: str(v) for k, v in ref["requires"].items()}
    kv["profilesSha256"] = "c" * 64
    kv.update({k: str(v) for k, v in over.items()})
    return "RENDER tag=SHOT " + " ".join(f"{k}={v}" for k, v in kv.items())


def trace_text(name: str, render: str | None) -> str:
    lines = ["2026.09.29-10.00.00 --- S08 trace open ---",
             "2026.09.29-10.00.05 SHOT ctx viewport=1920x1080 viewTarget=Cam cam=(0,1107,1581) rot=(-55,-90,0)"]
    if render:
        lines.append("2026.09.29-10.00.05 " + render)
    lines.append(f"2026.09.29-10.00.05 SHOT requested: FScreenshotRequest(bShowUI) -> C:/run/{name}")
    return "\n".join(lines) + "\n"


class RenderCliTests(unittest.TestCase):
    def run_case(self, render):
        with tempfile.TemporaryDirectory() as d:
            t = Path(d) / "phase2-client-host.trace.log"
            t.write_text(trace_text("phase2-board-host-1920x1080.png", render), encoding="utf-8")
            f = Path(d) / "phase2-board-host-1920x1080.png"
            f.write_bytes(b"png")
            return run_cli("render", "--trace", t, "--frame", f)

    def test_reference_frame_passes(self):
        code, out, err = self.run_case(render_line())
        self.assertEqual(code, 0, err)
        self.assertTrue(out["reference"])
        self.assertEqual(out["status"], "reference")
        self.assertTrue(out["frame"]["matches_shot"])

    def test_pre_w4_frame_is_missing(self):
        code, out, _ = self.run_case(None)
        self.assertEqual(code, 3)
        self.assertEqual(out["status"], "missing")

    def test_off_reference_frames_fail(self):
        for over in ({"rhi": "D3D11", "featureLevel": "SM5", "gi": "lumen-unsupported"},
                     {"sg.gi": "3"}, {"screenPct": "73.0"}, {"exposure": "engine-default"},
                     {"gameLayer": "solid-legacy"}):
            with self.subTest(over=over):
                code, out, _ = self.run_case(render_line(**over))
                self.assertEqual(code, 1)
                self.assertEqual(out["status"], "off-reference")
                self.assertTrue(out["reasons"])


class RenderChecklistTests(unittest.TestCase):
    def test_row_needs_a_bound_reference_result_per_frame(self):
        with tempfile.TemporaryDirectory() as td:
            d = Path(td)
            frames, results = {}, []
            for k in ("K1", "K2", "K3"):
                run = d / f"live-x/run-2026092{k[1]}-000000"
                run.mkdir(parents=True)
                name = "phase2-board-host-1920x1080.png"
                (run / name).write_bytes(b"png")
                trace = run / "phase2-client-host.trace.log"
                over = {"sg.shadow": "3"} if k == "K3" else {}
                trace.write_text(trace_text(name, render_line(**over)), encoding="utf-8")
                code, out, _ = run_cli("render", "--trace", trace, "--frame", run / name,
                                       "--json", d / f"render-{k}.json")
                frames[k] = {"path": str(run / name), "provenance": "packaged-live"}
                results.append({"k": k, "path": str(d / f"render-{k}.json")})
            rows = {r["id"]: r for r in build_checklist({"frames": frames, "results": results}, d)["rows"]}
            row = rows["ALL.render_reference"]
            self.assertTrue(row["status"].startswith("не годится для приёмки"), row["status"])
            self.assertIn("K3 (не эталон", row["status"])
            self.assertIn("K1: эталон", row["detail"])
            ok = {"frames": {k: frames[k] for k in ("K1", "K2")}, "results": results[:2]}
            row = {r["id"]: r for r in build_checklist(ok, d)["rows"]}["ALL.render_reference"]
            self.assertEqual(row["status"], "ок")
            none = {"frames": {"K1": frames["K1"]}, "results": []}
            row = {r["id"]: r for r in build_checklist(none, d)["rows"]}["ALL.render_reference"]
            self.assertIn("нет результата qa010 render", row["status"])


if __name__ == "__main__":
    unittest.main()
