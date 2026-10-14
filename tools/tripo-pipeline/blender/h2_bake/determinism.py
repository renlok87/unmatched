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
other runs with --reuse-from repeat only the recomputed stages.

Look-dev metal_f0 "self" (h2-bake 0.9.0, skill check C18): when BOTH runs' reports/ld-maps-report.json#metal_f0 has
concept_source "self", the F0 of those classes comes from this run's ld_measure (medians of Cycles class masks, C38).
Then the hero LUT (textures/T_UM_MatLUT_*.dds), its overrides JSON and ld-maps-report.json follow the rule lut_f0_self:
every LUT cell / JSON value equal except the F0 (row 0 RGB) and worn colour (row 6 RGB) of the metal_f0 classes and the
blocks derived from them, which may differ by <= F0_SELF_TOL (linear) — otherwise the json / exact rule as before."""

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

F0_SELF_TOL = 0.01  # linear F0 / worn colour channel: one mask pixel of the class pass moves a concept median (C38)
LUT_F0_ROWS = (0, 6)  # build_ue_inputs.LUT_ROWS: 0 bcR/G/B (F0 of a metal), 6 wornBCR/G/B

TOLERANCES = (
    {"pattern": "textures/T_UM_MatLUT_*.dds", "rule": "lut_f0_self", "when": "metal_f0_self", "tolerance": F0_SELF_TOL,
     "why": "look-dev metal_f0 \"self\" in both runs: F0 / worn colour cells of the metal_f0 classes within the "
            "tolerance, every other cell exact (C18)"},
    {"pattern": "textures/T_UM_MatLUT_*.overrides.json", "rule": "lut_f0_self", "when": "metal_f0_self",
     "tolerance": F0_SELF_TOL, "why": "the same for the overrides JSON (bc / wornBC of the metal_f0 classes)"},
    {"pattern": "reports/ld-maps-report.json", "rule": "lut_f0_self", "when": "metal_f0_self", "tolerance": F0_SELF_TOL,
     "why": "the same for ld-maps-report.json: blocks derived from the F0 (metal_f0, lut sha256 / applied, LUT outputs, "
            "measured values of the LUT checks) within the tolerance, the rest and every passed equal"},
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
    {"pattern": "reports/measure-report.json", "rule": "render",
     "why": "look-dev ld_measure: medians of the ID-pass masks on Cycles frames; Beowulf 2026-10-14 full repeat lost one "
            "mask pixel (2176 -> 2175, hue 25.2 -> 24.7) with every map / LUT / FBX identical (skill check C38)"},
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


def rule_for(rel, conditions=()):
    """First rule whose pattern matches; a rule with `when` counts only when that condition holds for the pair."""
    return next(t for t in TOLERANCES if fnmatch.fnmatchcase(rel, t["pattern"])
                and (t.get("when") is None or t["when"] in conditions))


def metal_f0_self_classes(run_dir):
    """{class: LUT column} of the metal_f0 "self" classes of a look-dev run (ld-maps-report.json), or None."""
    p = Path(run_dir) / "reports" / "ld-maps-report.json"
    try:
        mf = json.loads(p.read_text(encoding="utf-8")).get("metal_f0") or {}
    except (OSError, ValueError, AttributeError):
        return None
    if mf.get("concept_source") != "self" or not isinstance(mf.get("lut_column"), dict):
        return None
    return {k: int(v) for k, v in mf["lut_column"].items()}


def read_dds_half(path):
    """DDS DX10 RGBA16F, one 2D slice (lookdev.read_dds_rgba16f) -> float32 [H, W, 4]."""
    import numpy as np

    b = Path(path).read_bytes()
    h, w = (int(x) for x in np.frombuffer(b[12:20], "<u4"))
    return np.frombuffer(b[148:148 + h * w * 8], "<f2").reshape(h, w, 4).astype(np.float32), b[:148]


def _close(a, b, tol):
    """Numbers (nested lists / dicts) equal in structure and within tol."""
    if isinstance(a, dict) and isinstance(b, dict):
        return a.keys() == b.keys() and all(_close(a[k], b[k], tol) for k in a)
    if isinstance(a, list) and isinstance(b, list):
        return len(a) == len(b) and all(_close(x, y, tol) for x, y in zip(a, b))
    if isinstance(a, (int, float)) and isinstance(b, (int, float)) and not isinstance(a, bool) and not isinstance(b, bool):
        return abs(float(a) - float(b)) <= tol
    return a == b


def _lut_f0_compare(rel, pa, pb, run_a, run_b, repo, cols, tol):
    """lut_f0_self rule (module docstring) -> (ok, detail)."""
    import numpy as np

    if rel.endswith(".dds"):
        (a, ha), (b, hb) = read_dds_half(pa), read_dds_half(pb)
        if ha != hb or a.shape != b.shape:
            return False, "header / size"
        free = np.zeros(a.shape, bool)
        for c in cols.values():
            for row in LUT_F0_ROWS:
                free[row, c, :3] = True
        d = np.abs(a - b)
        ok = bool((d[~free] == 0).all() and (d[free] <= tol).all())
        return ok, {"max_f0_diff": round(float(d[free].max()), 5) if free.any() else 0.0,
                    "other_cells_differing": int((d[~free] > 0).sum())}
    da, db = normalised(pa, run_a, repo), normalised(pb, run_b, repo)
    fa, fb = {}, {}
    if rel.endswith(".overrides.json"):
        for data, out in ((da, fa), (db, fb)):
            for c in cols:
                e = (data.get("classes") or {}).get(c) or {}
                out[c] = {k: e.pop(k, None) for k in ("bc", "wornBC")}
    else:  # ld-maps-report.json: sha256 of the LUT files dropped, F0-derived numbers within the tolerance
        for data, out in ((da, fa), (db, fb)):
            mf = data.pop("metal_f0", None) or {}
            out["metal_f0"] = {c: {"f0": r.get("f0_linear"), "worn": (r.get("worn") or {}).get("linear"),
                                   "reached": r.get("reached")} for c, r in sorted((mf.get("classes") or {}).items())}
            lut = data.get("lut") or {}
            out["applied"] = lut.pop("applied", None)
            for k in ("dds_sha256", "overrides_sha256"):
                lut.pop(k, None)
            for name in (lut.get("dds"), lut.get("overrides_json")):
                (data.get("outputs") or {}).pop(name, None)
            checks = data.get("checks") or {}
            (checks.get("lut_dds_read_back") or {}).pop("measured", None)  # the DDS sha256
            for name, keys in (("lut_metal_f0_plausible", ("measured",)),
                               ("lut_metal_f0_from_concept", ("measured", "expected"))):
                for k in keys:
                    out["%s.%s" % (name, k)] = (checks.get(name) or {}).pop(k, None)
    ok = da == db and _close(fa, fb, tol)
    return ok, {"rest_equal": da == db, "f0_within_tolerance": _close(fa, fb, tol)}


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
    f0_cols = metal_f0_self_classes(run_dir)
    conditions = ("metal_f0_self",) if f0_cols and f0_cols == metal_f0_self_classes(other) else ()
    for rel in sorted(set(fa) | set(fb)):
        rule = rule_for(rel, conditions)
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
        elif rule["rule"] == "lut_f0_self":
            try:
                ok, detail = _lut_f0_compare(rel, fa[rel], fb[rel], run_dir, other, repo, f0_cols, rule["tolerance"])
            except (ValueError, OSError) as e:
                ok, detail = False, str(e)
            row.update(result="within tolerance" if ok else "different", ok=ok, detail=detail)
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
