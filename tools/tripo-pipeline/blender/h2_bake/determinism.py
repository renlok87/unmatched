"""Determinism verdict of two runs of one profile (h2-bake 0.7.0, W1-d 2026-10-14: RB-14, F24, F33, F86, RC-08).
Plain Python (numpy + Pillow for PNG). Driver: run_h2_bake.py --compare-with <other run> (every mode).

Every file under export/ textures/ preview/ reports/ of both runs gets the FIRST rule of TOLERANCES whose pattern
matches its run-relative path (fnmatch, `*` crosses `/`):
  excluded         not compared (the manifest and this report; Cycles JPEGs with denoise; the optional curve stage)
  render           derived from Cycles frames: not compared byte for byte, but a top-level `passed` must agree
  textures_report  JSON equal after dropping outputs.<map>.{sha256, bytes} of the maps that passed the PNG rule
  png              same size and mode, max |a - b| <= PNG_MAX_ABS_DIFF per channel and value, differing pixels
                   <= PNG_MAX_DIFFERING_SHARE of the image (GPU bake noise of N / ORM)
  json             byte-identical, or equal after the run path -> <run> and without the top-level `reused_from`
  exact            byte-identical (FBX and everything else)
A file present in one run only fails (unless excluded / render). verdict = "pass" when every compared file is ok;
run_h2_bake.py exits with code 1 on "fail" and prints the failures.

Scope (RC-08): a stage both runs took from the same --reuse-from source is not evidence of determinism (its files are
hard links of one source). Such files are marked reused_in_both; the scope is then "recomputed_stages_only" and lists
the recomputed stages. Rule of the skill: the full repeat (scope "full") once per figure, on the run that goes to UE;
other runs with --reuse-from repeat only the recomputed stages."""

import fnmatch
import hashlib
import json
from pathlib import Path

SCHEMA = "unmatched.h2-bake-determinism/2"
OUTPUT_DIRS = ("export", "textures", "preview", "reports")
PNG_MAX_ABS_DIFF = 2
PNG_MAX_DIFFERING_SHARE = 1e-4
NOISE_MEASURED = ("pilot 2026-10-13/14, 11 repeats (Medusa, Achilles r1-r3, Angel, Ancient Leshen r1-r3; "
                  "C:/tmp/*-repro): N, N_OpenGL, ORM (4K and 2K) differ in 1-6 pixels by 1 level, Medusa ORM 4K one "
                  "pixel by 2; BC, TeamMask, TeamAccent, MatID, UV sheet always identical")

TOLERANCES = (
    {"pattern": "reports/run-manifest.json", "rule": "excluded",
     "why": "sha256 of every output and the profile path; rewritten by the manifest stage"},
    {"pattern": "reports/determinism-report.json", "rule": "excluded", "why": "this comparison"},
    {"pattern": "reports/decimation-curve.json", "rule": "excluded",
     "why": "optional exploratory stage curve (not in `all`)"},
    {"pattern": "preview/*.jpg", "rule": "excluded",
     "why": "Cycles frames with denoise (preview, ld_preview, ta_render): differ on every run, checked by eye"},
    {"pattern": "reports/compose-report.json", "rule": "render", "why": "sha256 of the JPEG sheets"},
    {"pattern": "reports/ld-compose-report.json", "rule": "render", "why": "sha256 of the look-dev JPEG sheets"},
    {"pattern": "reports/ld-team-*.json", "rule": "render",
     "why": "TeamAccent report, calibration and manifest are measured on / hash the ta_render Cycles frames (F86)"},
    {"pattern": "reports/textures-report.json", "rule": "textures_report",
     "why": "carries sha256 / bytes of the GPU-baked maps; the statistics must stay equal"},
    {"pattern": "*.png", "rule": "png", "max_abs_diff": PNG_MAX_ABS_DIFF, "max_differing_share": PNG_MAX_DIFFERING_SHARE,
     "why": "GPU bake (bake.device GPU) noise of N / N_OpenGL / ORM; " + NOISE_MEASURED},
    {"pattern": "*.json", "rule": "json",
     "why": "reports: exact, or equal after the run path -> <run> and without the top-level reused_from"},
    {"pattern": "*", "rule": "exact", "why": "FBX and everything else: byte for byte"},
)
OK_RESULTS = ("identical", "identical after normalisation", "within tolerance", "excluded", "render: verdict agrees")


def sha256(path):
    d = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            d.update(chunk)
    return d.hexdigest()


def rule_for(rel):
    return next(t for t in TOLERANCES if fnmatch.fnmatchcase(rel, t["pattern"]))


def output_files(run_dir):
    run_dir = Path(run_dir)
    out = {}
    for d in OUTPUT_DIRS:
        for p in sorted((run_dir / d).rglob("*")):
            if p.is_file():
                out[p.relative_to(run_dir).as_posix()] = p
    return out


def path_tokens(run_dir, repo):
    """Spellings of the run directory inside reports: repo-relative, absolute posix, absolute Windows (also JSON-escaped)."""
    r = Path(run_dir).resolve()
    toks = []
    try:
        toks.append(r.relative_to(Path(repo).resolve()).as_posix())
    except ValueError:
        pass
    toks += [r.as_posix(), str(r), json.dumps(str(r))[1:-1]]
    return sorted({t for t in toks if t}, key=len, reverse=True)


def normalised(path, run_dir, repo, drop_reused=True):
    text = Path(path).read_text(encoding="utf-8")
    for tok in path_tokens(run_dir, repo):
        text = text.replace(tok, "<run>")
    data = json.loads(text)
    if drop_reused and isinstance(data, dict):
        data.pop("reused_from", None)
    return data


def png_compare(a, b):
    import numpy as np
    from PIL import Image

    ia, ib = Image.open(a), Image.open(b)
    if ia.size != ib.size or ia.mode != ib.mode:
        return {"ok": False, "detail": "size / mode %s %s vs %s %s" % (ia.size, ia.mode, ib.size, ib.mode)}
    x = np.asarray(ia).astype(np.int32)
    y = np.asarray(ib).astype(np.int32)
    diff = np.abs(x - y)
    per_px = diff.reshape(diff.shape[0], diff.shape[1], -1).max(-1)
    n_px = int(per_px.size)
    item = {"differing_values": int((diff > 0).sum()), "max_abs_diff": int(diff.max()),
            "differing_pixels": int((per_px > 0).sum()), "pixels": n_px}
    item["ok"] = item["max_abs_diff"] <= PNG_MAX_ABS_DIFF and item["differing_pixels"] <= PNG_MAX_DIFFERING_SHARE * n_px
    return item


def _textures_report_equal(pa, pb, run_a, run_b, repo, png_ok):
    a, b = normalised(pa, run_a, repo), normalised(pb, run_b, repo)
    for data in (a, b):
        for name, entry in (data.get("outputs") or {}).items():
            if isinstance(entry, dict) and png_ok.get("textures/%s" % name):
                entry.pop("sha256", None)
                entry.pop("bytes", None)
    return a == b


def compare(run_dir, other, repo, stage_of=None, reuse_a=None, reuse_b=None):
    """-> the determinism report (dict). stage_of(rel) -> owning stage or None; reuse_a / reuse_b = {stage: source run}
    of the stages each run took over with --reuse-from (empty / None for a full run)."""
    run_dir, other = Path(run_dir).resolve(), Path(other).resolve()
    fa, fb = output_files(run_dir), output_files(other)
    reuse_a, reuse_b = reuse_a or {}, reuse_b or {}
    rows, png_ok, deferred = {}, {}, []
    for rel in sorted(set(fa) | set(fb)):
        rule = rule_for(rel)
        row = {"rule": rule["rule"]}
        stage = stage_of(rel) if stage_of else None
        if stage:
            row["stage"] = stage
            if stage in reuse_a and reuse_a.get(stage) == reuse_b.get(stage):
                row["reused_in_both"] = True
        rows[rel] = row
        if rule["rule"] == "excluded":
            row.update(result="excluded", ok=True)
            continue
        if rel not in fa or rel not in fb:
            if rule["rule"] == "render":
                row.update(result="excluded", ok=True, note="render-derived file present in one run only")
            else:
                row.update(result="missing in " + ("this run" if rel not in fa else "other run"), ok=False)
            continue
        same = sha256(fa[rel]) == sha256(fb[rel])
        if rule["rule"] == "textures_report":
            if same:
                row.update(result="identical", ok=True)
            else:
                deferred.append(rel)
            continue
        if same:
            row.update(result="identical", ok=True)
            if rel.endswith(".png"):
                png_ok[rel] = True
            continue
        if rule["rule"] == "render":
            try:
                pa = json.loads(fa[rel].read_text(encoding="utf-8")).get("passed")
                pb = json.loads(fb[rel].read_text(encoding="utf-8")).get("passed")
            except (ValueError, AttributeError):
                pa = pb = None
            row.update(result="render: verdict agrees" if pa == pb else "render: verdict differs", ok=pa == pb,
                       passed=[pa, pb])
        elif rule["rule"] == "png":
            item = png_compare(fa[rel], fb[rel])
            ok = item.pop("ok")
            row.update(item, result="within tolerance" if ok else "different", ok=ok)
            png_ok[rel] = ok
        elif rule["rule"] == "json":
            try:
                eq = normalised(fa[rel], run_dir, repo) == normalised(fb[rel], other, repo)
            except ValueError:
                eq = False
            row.update(result="identical after normalisation" if eq else "different", ok=eq)
        else:
            row.update(result="different", ok=False)
    for rel in deferred:
        try:
            eq = _textures_report_equal(fa[rel], fb[rel], run_dir, other, repo, png_ok)
        except ValueError:
            eq = False
        rows[rel].update(result="identical after normalisation" if eq else "different", ok=eq,
                         note="outputs.<map>.sha256/bytes dropped for maps within the PNG tolerance")
    summary = {}
    for v in rows.values():
        summary[v["result"]] = summary.get(v["result"], 0) + 1
    failures = {k: v["result"] for k, v in rows.items() if not v["ok"]}
    shared = sorted({s for s in reuse_a if reuse_a.get(s) == reuse_b.get(s)})
    scope = "recomputed_stages_only" if shared else "full"
    rel_a, rel_b = _rel(run_dir, repo), _rel(other, repo)
    return {"schema": SCHEMA, "this_run": rel_a, "other_run": rel_b, "verdict": "fail" if failures else "pass",
            "failures": failures, "summary": summary, "files": rows,
            "scope": scope, "stages_reused_in_both": shared,
            "stages_reused": {"this_run": sorted(reuse_a), "other_run": sorted(reuse_b)},
            "rule": "full repeat (scope full) once per figure, on the run that goes to UE; a run made with "
                    "--reuse-from repeats only its recomputed stages (reused files are the same hard links)",
            "tolerances": [dict(t) for t in TOLERANCES]}


def _rel(path, repo):
    try:
        return Path(path).resolve().relative_to(Path(repo).resolve()).as_posix()
    except ValueError:
        return Path(path).resolve().as_posix()


def print_verdict(rep, tag, out):
    out("[%s] determinism %s (%s): %s" % (tag, rep["verdict"].upper(), rep["scope"], rep["summary"]))
    if rep["stages_reused_in_both"]:
        out("[%s]   stages reused in both runs (not compared as evidence): %s" % (tag, ", ".join(rep["stages_reused_in_both"])))
    for rel, res in sorted(rep["failures"].items()):
        out("[%s]   FAIL %s: %s" % (tag, rel, res))
