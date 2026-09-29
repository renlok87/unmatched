#!/usr/bin/env python3
"""W4-A RENDER fingerprint: parse, bind to a SHOT and check against the reference.

The packaged client writes, inside every SHOT block (between `SHOT ctx` and
`SHOT requested`), one line (S08Render.cpp S08RenderFingerprint):

  RENDER tag=SHOT rhi=D3D12 featureLevel=SM6 shaderPlatform=PCD3D_SM6 ... gi=lumen refl=lumen
         shadows=csm sg.res=100 sg.view=2 ... screenPct=100.0 aa=TSR exposure=fixed-histogram ...
         lightUnits=candelas sky=1 ... profilesSha256=<hex> profilesSource=pak legacyRender=0 ...
         tMaxFPS=30.0 vsync=0 frameRateLimit=60.0 ... viewport=1920x1080 reference=1

docs/art-pipeline/render-reference.json holds the reference (user decision
2026-09-28: DX12/SM6 + Lumen, High). A frame without a fingerprint, or with a
value that differs from `requires`, is not an acceptance frame for K1-K3,
QA-010, GD-058 or ACC-022 (classify_evidence --strict, qa010 render/checklist).

  python tools/art/render_fingerprint.py check --trace T [--shot NAME] [--reference R]
      exit 0 = on the reference, 1 = off the reference, 3 = no fingerprint for that SHOT
  python tools/art/render_fingerprint.py --self-test
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_REFERENCE = REPO_ROOT / "docs" / "art-pipeline" / "render-reference.json"
TS = re.compile(r"^\s*\d{4}\.\d{2}\.\d{2}-\d{2}\.\d{2}\.\d{2}\s+")
PAIR = re.compile(r"(\S+?)=(\S+)")
EXIT_OK, EXIT_OFF, EXIT_MISSING = 0, 1, 3


def payload(line: str) -> str:
    return TS.sub("", line.rstrip("\r\n"), count=1).strip()


def parse_render_line(line: str) -> dict | None:
    """'RENDER tag=SHOT k=v ...' -> {'tag': 'SHOT', 'k': 'v', ...}; None for other lines."""
    body = payload(line)
    if not body.startswith("RENDER "):
        return None
    return dict(PAIR.findall(body[len("RENDER "):]))


def load_reference(path: Path | None = None) -> dict:
    return json.loads(Path(path or DEFAULT_REFERENCE).read_text(encoding="utf-8"))


def check(fp: dict | None, ref: dict) -> tuple[bool, list[str]]:
    """(on reference, reasons). A missing fingerprint is never the reference."""
    if not fp:
        return False, ["no RENDER fingerprint for this SHOT"]
    reasons = []
    for key, want in (ref.get("requires") or {}).items():
        got = fp.get(key)
        if got != str(want):
            reasons.append(f"{key}={got if got is not None else '<missing>'} (reference {want})")
    for key, pattern in (ref.get("requiresPattern") or {}).items():
        got = fp.get(key)
        if got is None or not re.fullmatch(pattern, got):
            reasons.append(f"{key}={got if got is not None else '<missing>'} (reference /{pattern}/)")
    return not reasons, reasons


def shot_fingerprints(lines: list[str]) -> list[dict]:
    """One entry per SHOT block: {'shot': name|None, 'line': n, 'render': dict|None}.
    A block runs from 'SHOT ctx' to 'SHOT requested'; the RENDER tag=SHOT line
    inside it belongs to that shot."""
    out: list[dict] = []
    cur: dict | None = None
    for n, raw in enumerate(lines, start=1):
        body = payload(raw)
        if body.startswith("SHOT ctx"):
            if cur is not None:
                out.append(cur)
            cur = {"shot": None, "line": n, "render": None}
        elif body.startswith("RENDER ") and cur is not None:
            fp = parse_render_line(body)
            if fp and fp.get("tag") == "SHOT":
                cur["render"] = fp
                cur["renderLine"] = n
        elif body.startswith("SHOT requested") and cur is not None:
            cur["shot"] = re.split(r"[\\/]", body.strip())[-1]
            out.append(cur)
            cur = None
    if cur is not None:
        out.append(cur)
    return out


def fingerprint_for_shot(lines: list[str], shot_name: str | None) -> dict | None:
    """The block whose 'SHOT requested' names shot_name (last one wins, as on
    disk); without a name the single block of the trace."""
    blocks = shot_fingerprints(lines)
    if shot_name:
        hits = [b for b in blocks if b["shot"] == shot_name]
        return hits[-1] if hits else None
    return blocks[0] if len(blocks) == 1 else None


def read_lines(path: Path) -> list[str]:
    raw = Path(path).read_bytes()
    if raw.startswith((b"\xff\xfe", b"\xfe\xff")):
        return raw.decode("utf-16", errors="replace").splitlines()
    return raw.decode("utf-8-sig", errors="replace").splitlines()


def evaluate(trace: Path, shot: str | None, ref: dict) -> dict:
    block = fingerprint_for_shot(read_lines(trace), shot)
    fp = block["render"] if block else None
    ok, reasons = check(fp, ref)
    return {"trace": str(trace).replace("\\", "/"), "shot": shot or (block or {}).get("shot"),
            "blockFound": block is not None, "fingerprint": fp, "reference": ok, "reasons": reasons,
            "referenceFile": "docs/art-pipeline/render-reference.json", "referenceRevision": ref.get("revision")}


SELF_TEST_REF = {"requires": {"rhi": "D3D12", "gi": "lumen", "sg.shadow": "2", "screenPct": "100.0"},
                 "requiresPattern": {"profilesSha256": "^[0-9a-f]{64}$"}}
SELF_TEST_TRACE = [
    "2026.09.29-10.00.00 S08 trace open",
    "2026.09.29-10.00.01 SHOT ctx viewport=1920x1080 viewTarget=Cam cam=(0,1,2) rot=(-55,-90,0)",
    "2026.09.29-10.00.01 RENDER tag=SHOT rhi=D3D12 gi=lumen sg.shadow=2 screenPct=100.0 profilesSha256=" + "a" * 64
    + " reference=1",
    "2026.09.29-10.00.01 SHOT requested: FScreenshotRequest(bShowUI) -> C:/x/good.png",
    "2026.09.29-10.00.02 SHOT ctx viewport=1920x1080 viewTarget=Cam cam=(0,1,2) rot=(-55,-90,0)",
    "2026.09.29-10.00.02 RENDER tag=SHOT rhi=D3D11 gi=lumen-unsupported sg.shadow=3 screenPct=0.0 profilesSha256=- reference=0",
    "2026.09.29-10.00.02 SHOT requested: FScreenshotRequest(bShowUI) -> C:/x/dx11.png",
    "2026.09.29-10.00.03 SHOT ctx viewport=1920x1080 viewTarget=Cam cam=(0,1,2) rot=(-55,-90,0)",
    "2026.09.29-10.00.03 SHOT requested: FScreenshotRequest(bShowUI) -> C:/x/legacy.png",
]


def self_test() -> tuple[bool, list[dict]]:
    res = []
    for shot, want in (("good.png", True), ("dx11.png", False), ("legacy.png", False)):
        block = fingerprint_for_shot(SELF_TEST_TRACE, shot)
        ok, reasons = check(block["render"] if block else None, SELF_TEST_REF)
        res.append({"shot": shot, "expectedReference": want, "reference": ok, "reasons": reasons, "pass": ok == want})
    missing = [r for r in res if r["shot"] == "legacy.png"][0]
    missing["pass"] = missing["pass"] and missing["reasons"] == ["no RENDER fingerprint for this SHOT"]
    return all(r["pass"] for r in res), res


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--self-test", action="store_true")
    sub = ap.add_subparsers(dest="cmd")
    c = sub.add_parser("check", help="check the SHOT fingerprint of a trace against the reference")
    c.add_argument("--trace", required=True)
    c.add_argument("--shot", help="PNG basename of the SHOT (default: the single SHOT block)")
    c.add_argument("--reference", help="reference JSON (default docs/art-pipeline/render-reference.json)")
    a = ap.parse_args(argv)
    if a.self_test:
        ok, res = self_test()
        print(json.dumps({"selfTest": "PASS" if ok else "FAIL", "cases": res}, ensure_ascii=False, indent=2))
        return 0 if ok else 1
    if a.cmd != "check":
        ap.print_usage(sys.stderr)
        return 2
    r = evaluate(Path(a.trace), a.shot, load_reference(Path(a.reference) if a.reference else None))
    print(json.dumps(r, ensure_ascii=False, indent=2))
    if r["fingerprint"] is None:
        return EXIT_MISSING
    return EXIT_OK if r["reference"] else EXIT_OFF


if __name__ == "__main__":
    sys.exit(main())
