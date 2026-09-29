#!/usr/bin/env python3
"""Classify art evidence frames by provenance (read-only).

Stage 3 of the art track closes K1/K2/K3, QA-010 and GD-058 only with frames
from a live packaged client. This tool decides, for every frame (PNG/JPEG) or
for every frame inside an evidence directory, which of these classes it
belongs to:

  packaged-live        frame of a packaged client in a live game, proven by a
                       run manifest + client traces (S08/S09 trace format)
  packaged-staged      frame of a packaged build of a scripted scene (S05
                       smoke: run-summary.json with stage "packaged-smoke")
  editor-mcp-viewport  UE editor viewport captured through the MCP plugin
                       (EditorAppToolset.CaptureViewport, 127.0.0.1:8123)
  editor-cli           UE editor frame from UnrealEditor-Cmd / SceneCapture
                       scripts (reports with "output"/"camera_location")
  editor-unspecified   a UE editor frame whose capture path is not provable
                       (legacy "-ue-editor-" names without a report)
  blender              Blender render (PNG stamp metadata, or blender naming)
  unclassified         nothing proves an origin

Only "packaged-live" may back K1/K2/K3/QA-010/GD-058 rows; everything else is
diagnostic (QA-009 early rows, self-acceptance acts).

Rules, in the order they are applied
------------------------------------
R1  PNG metadata. A PNG whose tEXt chunks carry Blender's stamp keys
    ("RenderTime" plus "Scene" or "Camera") is a Blender render -> blender.
    UE screenshots (FScreenshotRequest, HighResShot, CaptureViewport after
    Pillow) carry no text chunks, so R1 never fires for them.
R2  Run manifest + traces (packaged-live). Look for manifest.json in the
    frame's directory and up to two parents. It must list the frame's file
    name with a sha256 equal to the file on disk, and list at least one
    *.trace.log whose sha256 also matches. The frame is bound to one trace:
    the trace whose "SHOT requested: ..." line names the frame's file name,
    otherwise the trace with the same role token (host/joiner) in its name.
    The bound trace must contain "S08 trace open", "SHOT ctx viewport=",
    "BOARD <W>x<H>" and "FIGHTERS synced n=". All of that -> packaged-live.
    A manifest that lists the frame but fails any check -> REJECTED.
    grade "strict" additionally needs:
      S1 binding by "SHOT requested" and the SHOT time not before trace open;
      S2 "SHOT ctx viewport=WxH" equal to the PNG size, and 1920x1080;
      S3 "ARTPREVIEW ... visual=1 mesh=<name>" (and <name> == --expect-mesh);
      S4 sidecar <frame-stem>.evidence.json (schema unmatched.evidence-frame/1):
         frame sha256, build.exeSha256 == build.stagedInnerExeSha256
         (the staged ROOT exe is a launcher stub, compare the inner
         Binaries/Win64 exe), build.result "Succeeded" and no -NoLiveCoding
         in build.flags, run.roomStatus ABORTED/FINISHED, run.boardId given.
      S5 W4-A RENDER fingerprint: the bound SHOT block carries a 'RENDER tag=SHOT'
         line and it equals docs/art-pipeline/render-reference.json (user
         decision 2026-09-28: DX12/SM6 + Lumen, High; tools/art/render_fingerprint.py).
    Otherwise grade "legacy" (historical runs) with the missing items listed.
    With --strict or --render-reference a packaged-live frame that fails S5 is
    REJECTED as an acceptance frame (K1-K3 / QA-010 / GD-058 / ACC-022): no
    fingerprint (every pre-W4 frame) or off the reference (DX11, SM5 fallback,
    sg.* != High, screen percentage != 100, legacy light units, ...).
R3  Sidecar for non-live classes: <frame-stem>.evidence.json with the same
    schema, a matching frameSha256 and class editor-mcp-viewport /
    editor-cli / blender / packaged-staged is accepted as declared. A sidecar
    that declares packaged-live is ignored unless R2 passes.
R4  Registration in a JSON report nearby (same directory and up to three
    parents, non-recursive, *.json <= 5 MB):
      * the frame's sha256 appears in the report -> "registered"; the JSON key
        under which it appears (usually a relative path) adds name tokens;
        MCP markers (CaptureViewport, 127.0.0.1:8123, ModelContextProtocol)
        in that report confirm editor-mcp-viewport;
      * a CLI capture report in the same directory with "output" whose file
        name equals the frame's and "camera_location" -> editor-cli;
      * a run-summary with stage "packaged-smoke" that lists the frame's
        repository path -> packaged-staged.
R5  Names (weakest; never sufficient for packaged-live). Path segments of the
    frame, lower case:
      "blender" in a segment / "-blender-"                -> blender
      "ue-mcp" in a segment, file "ue-axes-*"              -> editor-mcp-viewport
      "ue-cli" in a segment, file "cli-*", ".../artifacts/" -> editor-cli
      "-ue-editor-"                                       -> editor-unspecified
    Naming rule of stage 3: editor frames carry "-ue-editor-" or "-blender-";
    live frames live only in live-*/run-*/ next to a manifest.
Live claim. A frame "claims" packaged-live when it sits in live-*/run-*/ or
its name looks like a live capture (phase2-board-{host,joiner}-WxH.png,
frame-K<n>...). A claiming frame that does not end as packaged-live /
packaged-staged is REJECTED: a renamed editor PNG without a manifest and
traces must never pass as a live frame.

Output: JSON list, one object per frame. Exit code 0 = every frame classified
and none rejected; 2 = some frame rejected; 3 = --require not met; 1 = usage.

  python tools/art/classify_evidence.py <frame-or-dir> [...]
  python tools/art/classify_evidence.py <run-dir> --require packaged-live --strict
  python tools/art/classify_evidence.py --self-test
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import struct
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import render_fingerprint as RF  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parents[2]
IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg"}
SIDECAR_SCHEMA = "unmatched.evidence-frame/1"
CLASSES = ["packaged-live", "packaged-staged", "editor-mcp-viewport", "editor-cli",
           "editor-unspecified", "blender", "unclassified"]
LIVE_OK = {"packaged-live", "packaged-staged"}
MCP_MARKERS = ("CaptureViewport", "127.0.0.1:8123", "ModelContextProtocol")
TRACE_TS = re.compile(r"^(\d{4}\.\d{2}\.\d{2}-\d{2}\.\d{2}\.\d{2})")
LIVE_NAME = re.compile(r"^(phase2-board-(host|joiner)-\d+x\d+|frame-k\d)", re.IGNORECASE)
RUN_SEG = re.compile(r"^run-\d{8}-\d{6}$")
MAX_JSON = 5 * 1024 * 1024


# ---------------------------------------------------------------- file helpers
def sha256_file(p: Path) -> str:
    h = hashlib.sha256()
    with p.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def load_json(p: Path):
    try:
        if p.stat().st_size > MAX_JSON:
            return None
        return json.loads(p.read_text(encoding="utf-8-sig"))
    except (OSError, ValueError, UnicodeDecodeError):
        return None


def read_text_any(p: Path) -> str:
    raw = p.read_bytes()
    if raw.startswith((b"\xff\xfe", b"\xfe\xff")):
        return raw.decode("utf-16", errors="replace")
    return raw.decode("utf-8-sig", errors="replace")


def image_info(p: Path) -> dict:
    """Size and text metadata without third-party libraries."""
    info: dict = {"format": None, "width": None, "height": None, "text": {}}
    data = p.read_bytes()
    if data[:8] == b"\x89PNG\r\n\x1a\n":
        info["format"] = "png"
        pos = 8
        while pos + 8 <= len(data):
            n, ctype = struct.unpack(">I4s", data[pos:pos + 8])
            body = data[pos + 8:pos + 8 + n]
            if ctype == b"IHDR":
                info["width"], info["height"] = struct.unpack(">II", body[:8])
            elif ctype == b"tEXt" and b"\x00" in body:
                k, v = body.split(b"\x00", 1)
                info["text"][k.decode("latin-1")] = v.decode("latin-1", errors="replace")
            elif ctype == b"IEND":
                break
            pos += 12 + n
    elif data[:2] == b"\xff\xd8":
        info["format"] = "jpeg"
        pos = 2
        while pos + 4 <= len(data):
            if data[pos] != 0xFF:
                pos += 1
                continue
            marker = data[pos + 1]
            if marker in (0xD8, 0x01) or 0xD0 <= marker <= 0xD7:
                pos += 2
                continue
            seg_len = struct.unpack(">H", data[pos + 2:pos + 4])[0]
            if marker in (0xC0, 0xC1, 0xC2, 0xC3):
                info["height"], info["width"] = struct.unpack(">HH", data[pos + 5:pos + 9])
                break
            pos += 2 + seg_len
    return info


def rel_to_repo(p: Path) -> str:
    try:
        return p.resolve().relative_to(REPO_ROOT).as_posix()
    except ValueError:
        return p.resolve().as_posix()


def ancestors(p: Path, levels: int) -> list[Path]:
    out, cur = [], p.parent
    for _ in range(levels + 1):
        out.append(cur)
        if (cur / ".git").exists() or cur.parent == cur:
            break
        cur = cur.parent
    return out


def role_token(name: str) -> str | None:
    n = name.lower()
    for tok in ("host", "joiner"):
        if re.search(rf"(^|[-_]){tok}([-_.]|$)", n):
            return tok
    return None


def trace_time(line: str) -> str | None:
    m = TRACE_TS.match(line)
    return m.group(1) if m else None


# ---------------------------------------------------------------- rules
def rule_blender_metadata(info: dict) -> bool:
    t = info.get("text") or {}
    return "RenderTime" in t and ("Scene" in t or "Camera" in t)


def find_manifest(frame: Path) -> tuple[Path, dict, dict] | None:
    for d in ancestors(frame, 2):
        m = d / "manifest.json"
        if not m.is_file():
            continue
        doc = load_json(m)
        if not isinstance(doc, dict) or not isinstance(doc.get("files"), list):
            continue
        for entry in doc["files"]:
            if isinstance(entry, dict) and entry.get("name") == frame.name:
                return m, doc, entry
    return None


def check_live(frame: Path, info: dict, sha: str, expect_mesh: str | None) -> dict:
    res: dict = {"manifest": None, "core": {}, "strict": {}, "trace": None, "missingStrict": [], "reasons": [],
                 "render": None}
    found = find_manifest(frame)
    if not found:
        res["reasons"].append("no run manifest listing this frame (manifest.json in the frame dir or 2 parents)")
        return res
    mpath, mdoc, entry = found
    res["manifest"] = rel_to_repo(mpath)
    core = res["core"]
    core["C1_manifest_sha_matches"] = entry.get("sha256") == sha
    if not core["C1_manifest_sha_matches"]:
        res["reasons"].append(f"manifest sha256 {str(entry.get('sha256'))[:12]}… != file {sha[:12]}…")
    traces = []
    for e in mdoc["files"]:
        if not (isinstance(e, dict) and str(e.get("name", "")).endswith(".trace.log")):
            continue
        tp = mpath.parent / e["name"]
        ok = tp.is_file() and sha256_file(tp) == e.get("sha256")
        traces.append((tp, ok))
    core["C2_traces_listed_and_hash_ok"] = bool(traces) and all(ok for _, ok in traces)
    if not traces:
        res["reasons"].append("manifest lists no *.trace.log")
    elif not core["C2_traces_listed_and_hash_ok"]:
        res["reasons"].append("a listed trace is missing or its sha256 differs from the manifest")
    # bind frame -> trace
    bound, binding, shot_line = None, None, None
    for tp, ok in traces:
        if not ok:
            continue
        for line in read_text_any(tp).splitlines():
            if "SHOT requested" in line and re.split(r"[\\/]", line.strip())[-1] == frame.name:
                bound, binding, shot_line = tp, "shot-requested", line
                break
        if bound:
            break
    if not bound:
        role = role_token(frame.name)
        cands = [tp for tp, ok in traces if ok and role and role_token(tp.name) == role]
        if len(cands) == 1:
            bound, binding = cands[0], "role-name"
    core["C3_trace_bound"] = bound is not None
    if not bound:
        res["reasons"].append("no trace names this frame in 'SHOT requested' and no unique host/joiner trace")
        return res
    text = read_text_any(bound)
    lines = text.splitlines()
    res["trace"] = {"file": rel_to_repo(bound), "binding": binding}
    need = {
        "trace_open": any("S08 trace open" in ln for ln in lines),
        "shot_ctx": any("SHOT ctx viewport=" in ln for ln in lines),
        "board": any(re.search(r"\bBOARD \d+x\d+\b", ln) for ln in lines),
        "fighters_synced": any(re.search(r"FIGHTERS synced n=\d+", ln) for ln in lines),
    }
    core["C3_trace_markers"] = need
    for k, v in need.items():
        if not v:
            res["reasons"].append(f"bound trace lacks marker: {k}")
    core["C4_not_blender_render"] = not rule_blender_metadata(info)
    if not core["C4_not_blender_render"]:
        res["reasons"].append("PNG carries Blender stamp metadata")
    board = next((m.group(0) for ln in lines for m in [re.search(r"\bBOARD \d+x\d+\b", ln)] if m), None)
    mesh = next((m.group(1) for ln in lines for m in [re.search(r"ARTPREVIEW .*visual=1 mesh=(\S+)", ln)] if m), None)
    viewport = next((m.groups() for ln in lines for m in [re.search(r"SHOT ctx viewport=(\d+)x(\d+)", ln)] if m), None)
    res["trace"].update(board=board, mesh=mesh, viewport="x".join(viewport) if viewport else None)
    # strict
    st = res["strict"]
    open_t = next((trace_time(ln) for ln in lines if "S08 trace open" in ln), None)
    shot_t = trace_time(shot_line) if shot_line else None
    st["S1_shot_requested_binding"] = binding == "shot-requested" and bool(open_t) and bool(shot_t) and shot_t >= open_t
    st["S2_viewport_matches_png_1080p"] = (viewport is not None and info.get("width") == int(viewport[0])
                                           and info.get("height") == int(viewport[1])
                                           and (info.get("width"), info.get("height")) == (1920, 1080))
    st["S3_artpreview_mesh"] = mesh is not None and (expect_mesh is None or mesh == expect_mesh)
    # S5 (W4-A): the RENDER fingerprint of the bound SHOT against the reference.
    block = RF.fingerprint_for_shot(lines, frame.name) if binding == "shot-requested" else None
    if block is None and binding != "shot-requested":
        blocks = RF.shot_fingerprints(lines)
        block = blocks[-1] if blocks else None
    fp = block["render"] if block else None
    try:
        ok, why = RF.check(fp, RF.load_reference())
    except (OSError, ValueError) as exc:
        ok, why = False, [f"render reference unreadable: {exc}"]
    res["render"] = {"fingerprint": fp, "reference": ok, "reasons": why,
                     "referenceFile": "docs/art-pipeline/render-reference.json"}
    st["S5_render_reference"] = ok
    st["S4_sidecar_build_run"] = False
    side = frame.with_name(frame.stem + ".evidence.json")
    sdoc = load_json(side) if side.is_file() else None
    if isinstance(sdoc, dict) and sdoc.get("schema") == SIDECAR_SCHEMA:
        b, r = sdoc.get("build") or {}, sdoc.get("run") or {}
        hexok = lambda v: isinstance(v, str) and re.fullmatch(r"[0-9a-f]{64}", v) is not None  # noqa: E731
        st["S4_sidecar_build_run"] = (
            sdoc.get("frameSha256") == sha and sdoc.get("class") == "packaged-live"
            and hexok(b.get("exeSha256")) and b.get("exeSha256") == b.get("stagedInnerExeSha256")
            and b.get("result") == "Succeeded"
            and "-nolivecoding" not in " ".join(b.get("flags") or []).lower()
            and r.get("roomStatus") in ("ABORTED", "FINISHED") and bool(r.get("boardId")))
    res["missingStrict"] = [k for k, v in st.items() if not v]
    return res


def rule_sidecar(frame: Path, sha: str) -> str | None:
    side = frame.with_name(frame.stem + ".evidence.json")
    doc = load_json(side) if side.is_file() else None
    if (isinstance(doc, dict) and doc.get("schema") == SIDECAR_SCHEMA and doc.get("frameSha256") == sha
            and doc.get("class") in {"editor-mcp-viewport", "editor-cli", "blender", "packaged-staged"}):
        return doc["class"]
    return None


def _find_key_for_value(obj, needle: str, path: str = "") -> str | None:
    if isinstance(obj, dict):
        for k, v in obj.items():
            if v == needle:
                return str(k)
            hit = _find_key_for_value(v, needle, f"{path}/{k}")
            if hit is not None:
                return hit
    elif isinstance(obj, list):
        for v in obj:
            hit = _find_key_for_value(v, needle, path)
            if hit is not None:
                return hit
    return None


def rule_registration(frame: Path, sha: str) -> dict:
    out = {"registeredIn": [], "registeredAs": [], "mcpMarkers": False, "cliReport": None, "stagedSummary": None}
    frame_rel = rel_to_repo(frame).lower()
    for d in ancestors(frame, 3):
        for jp in sorted(d.glob("*.json")):
            if jp == frame.with_name(frame.stem + ".evidence.json"):
                continue
            try:
                if jp.stat().st_size > MAX_JSON:
                    continue
                text = jp.read_text(encoding="utf-8-sig", errors="replace")
            except OSError:
                continue
            if sha in text:
                out["registeredIn"].append(rel_to_repo(jp))
                doc = load_json(jp)
                key = _find_key_for_value(doc, sha) if doc is not None else None
                if key:
                    out["registeredAs"].append(key)
                if any(m in text for m in MCP_MARKERS):
                    out["mcpMarkers"] = True
            doc = None
            if d == frame.parent and '"output"' in text and "camera_location" in text:
                doc = load_json(jp)
                if isinstance(doc, dict) and re.split(r"[\\/]", str(doc.get("output", "")))[-1] == frame.name:
                    out["cliReport"] = rel_to_repo(jp)
            if '"packaged-smoke"' in text:
                doc = doc or load_json(jp)
                if isinstance(doc, dict) and doc.get("stage") == "packaged-smoke":
                    listed = [str(x).replace("\\", "/").lower() for x in doc.get("frames") or []]
                    if frame_rel in listed:
                        out["stagedSummary"] = rel_to_repo(jp)
    return out


def rule_names(frame: Path, extra_tokens: list[str]) -> str | None:
    segs = [s.lower() for s in Path(rel_to_repo(frame)).parts] + [t.lower() for t in extra_tokens]
    name = frame.name.lower()
    joined = "/".join(segs)
    if any("blender" in s for s in segs) or "-blender-" in name:
        return "blender"
    if any("ue-mcp" in s for s in segs) or name.startswith("ue-axes"):
        return "editor-mcp-viewport"
    if any("ue-cli" in s for s in segs) or name.startswith("cli-") or "/artifacts/" in f"/{joined}/":
        return "editor-cli"
    if "-ue-editor-" in name:
        return "editor-unspecified"
    return None


def claims_live(frame: Path) -> bool:
    parts = [p.lower() for p in Path(rel_to_repo(frame)).parts]
    in_run = any(RUN_SEG.match(parts[i]) and parts[i - 1].startswith("live-") for i in range(1, len(parts)))
    return in_run or bool(LIVE_NAME.match(frame.name))


# ---------------------------------------------------------------- driver
def classify_frame(frame: Path, expect_mesh: str | None = None, render_reference: bool = False) -> dict:
    frame = frame.resolve()
    info = image_info(frame)
    sha = sha256_file(frame)
    r: dict = {"frame": rel_to_repo(frame), "sha256": sha, "size": [info["width"], info["height"]],
               "class": "unclassified", "grade": None, "basis": [], "rejected": False, "reasons": [],
               "claimsLive": claims_live(frame)}
    live = check_live(frame, info, sha, expect_mesh)
    r["live"] = {k: live[k] for k in ("manifest", "core", "strict", "trace", "missingStrict", "render")}
    if rule_blender_metadata(info):
        r["class"], r["basis"] = "blender", ["R1 png-metadata: " + ", ".join(sorted(info["text"]))]
    elif live["manifest"]:
        core = live["core"]
        ok = (core.get("C1_manifest_sha_matches") and core.get("C2_traces_listed_and_hash_ok")
              and core.get("C3_trace_bound") and all((core.get("C3_trace_markers") or {}).values())
              and core.get("C4_not_blender_render"))
        if ok:
            r["class"] = "packaged-live"
            r["grade"] = "strict" if not live["missingStrict"] else "legacy"
            r["basis"] = [f"R2 manifest {live['manifest']}", f"R2 trace {live['trace']['file']} ({live['trace']['binding']})"]
        else:
            r["rejected"] = True
            r["reasons"] += ["R2 run manifest lists the frame but provenance fails"] + live["reasons"]
    if r["class"] == "unclassified" and not r["rejected"]:
        declared = rule_sidecar(frame, sha)
        if declared:
            r["class"], r["basis"] = declared, ["R3 sidecar " + frame.stem + ".evidence.json"]
    if r["class"] == "unclassified" and not r["rejected"]:
        reg = rule_registration(frame, sha)
        r["registration"] = reg
        if reg["stagedSummary"]:
            r["class"], r["basis"] = "packaged-staged", [f"R4 run-summary {reg['stagedSummary']} (packaged-smoke)"]
        elif reg["cliReport"]:
            r["class"], r["basis"] = "editor-cli", [f"R4 CLI capture report {reg['cliReport']}"]
        else:
            by_name = rule_names(frame, reg["registeredAs"])
            if by_name:
                r["class"] = by_name
                r["basis"] = ["R5 name tokens"]
                if reg["registeredIn"]:
                    r["basis"].append("R4 sha256 registered in " + ", ".join(reg["registeredIn"]))
                if by_name == "editor-mcp-viewport" and reg["mcpMarkers"]:
                    r["basis"].append("R4 MCP capture markers in the registering report")
    if r["claimsLive"] and r["class"] not in LIVE_OK:
        r["rejected"] = True
        r["reasons"].append("frame claims packaged-live (live-*/run-*/ location or live capture name) "
                            "but has no valid run manifest and traces")
    if r["class"] == "unclassified" and not r["reasons"]:
        r["reasons"].append("no metadata, manifest, sidecar, registering report or name rule applies")
    if render_reference and r["class"] == "packaged-live" and not r["rejected"]:
        rend = live.get("render") or {}
        if not rend.get("reference"):
            r["rejected"] = True
            r["reasons"].append("W4-A render reference: " + "; ".join(rend.get("reasons") or ["no RENDER fingerprint"]))
    return r


def iter_frames(paths: list[Path]) -> list[Path]:
    out: list[Path] = []
    for p in paths:
        if p.is_dir():
            out += sorted(q for q in p.rglob("*") if q.suffix.lower() in IMAGE_SUFFIXES and q.is_file())
        elif p.is_file():
            out.append(p)
        else:
            raise FileNotFoundError(p)
    return out


SELF_TEST_CASES = [
    ("positive", "docs/game-design/evidence/ART-004/live-k2-label-probe-5x/run-20260928-063853/phase2-board-host-1920x1080.png", "packaged-live"),
    ("positive", "docs/game-design/evidence/ART-004/head-tilt-v3-probe-2026-09-28/ue-mcp-live/ue-mcp-cobble-d10-k2-d300-v3.png", "editor-mcp-viewport"),
    ("positive", "docs/game-design/evidence/ART-004/head-tilt-v3-probe-2026-09-28/blender-id-d10-k2-front-d300-v3.png", "blender"),
]
NEGATIVE_SOURCE = "docs/game-design/evidence/ART-004/head-tilt-v3-probe-2026-09-28/ue-mcp-live/ue-mcp-cobble-d10-k2-d300-v3.png"


def self_test() -> tuple[bool, list[dict]]:
    """3 known positives + 1 negative (editor PNG renamed as a live host frame)
    + 1 W4-A negative (a pre-W4 live frame under --render-reference)."""
    results = []
    for kind, rel, expected in SELF_TEST_CASES:
        r = classify_frame(REPO_ROOT / rel)
        passed = r["class"] == expected and not r["rejected"]
        results.append({"case": kind, "frame": rel, "expected": expected, "got": r["class"],
                        "grade": r["grade"], "rejected": r["rejected"], "pass": passed})
    rel_live = SELF_TEST_CASES[0][1]
    r = classify_frame(REPO_ROOT / rel_live, render_reference=True)
    results.append({"case": "negative-render", "frame": rel_live,
                    "expected": "rejected under --render-reference (pre-W4 frame, no RENDER fingerprint)",
                    "got": r["class"], "grade": r["grade"], "rejected": r["rejected"],
                    "reasons": r["reasons"][-1:], "pass": r["class"] == "packaged-live" and r["rejected"]})
    tmp = Path(tempfile.mkdtemp(prefix="classify-evidence-neg-"))
    try:
        fake = tmp / "phase2-board-host-1920x1080.png"
        shutil.copyfile(REPO_ROOT / NEGATIVE_SOURCE, fake)
        r = classify_frame(fake)
        passed = r["class"] != "packaged-live" and r["rejected"]
        results.append({"case": "negative", "frame": f"<tmp>/{fake.name} (copy of {NEGATIVE_SOURCE})",
                        "expected": "rejected, not packaged-live", "got": r["class"], "grade": r["grade"],
                        "rejected": r["rejected"], "reasons": r["reasons"], "pass": passed})
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    return all(x["pass"] for x in results), results


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("paths", nargs="*", type=Path, help="frames (PNG/JPEG) or evidence directories")
    ap.add_argument("--require", choices=CLASSES, help="exit 3 unless every frame has this class")
    ap.add_argument("--strict", action="store_true", help="with --require packaged-live: also require grade strict")
    ap.add_argument("--expect-mesh", help="strict S3: mesh name expected in 'ARTPREVIEW ... visual=1 mesh='")
    ap.add_argument("--render-reference", action="store_true",
                    help="reject packaged-live frames whose SHOT has no RENDER fingerprint or one off "
                         "docs/art-pipeline/render-reference.json (implied by --strict)")
    ap.add_argument("--self-test", action="store_true", help="run the built-in 3 positive + 1 negative cases")
    a = ap.parse_args(argv)
    if a.self_test:
        ok, results = self_test()
        print(json.dumps({"selfTest": "PASS" if ok else "FAIL", "cases": results}, ensure_ascii=False, indent=2))
        return 0 if ok else 1
    if not a.paths:
        ap.print_usage(sys.stderr)
        return 1
    try:
        frames = iter_frames(a.paths)
    except FileNotFoundError as e:
        print(f"not found: {e}", file=sys.stderr)
        return 1
    results = [classify_frame(f, a.expect_mesh, render_reference=a.strict or a.render_reference) for f in frames]
    print(json.dumps(results, ensure_ascii=False, indent=2))
    if a.require:
        bad = [r for r in results if r["class"] != a.require
               or (a.strict and a.require == "packaged-live" and r["grade"] != "strict")]
        if bad or not results:
            return 3
    if any(r["rejected"] for r in results):
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
