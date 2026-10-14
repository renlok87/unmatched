"""W1-d (2026-10-14): determinism verdict with a tolerance table (RB-14), the new-hero profile rules (RB-15), the stage
ledger and --reuse-from (RC-07 / RC-08), the look-dev FBX staging (RB-13).

Plain Python on synthetic run directories, except the look-dev staging tests (Blender headless, skipped without Blender
5.2 or the local Medusa H2 work files, which are not in git) and the ownership test on the committed runs.
Run: python -m pytest tools/tripo-pipeline/blender/h2_bake/tests -q -p no:cacheprovider"""

import copy
import json
import os
import subprocess
import sys
from pathlib import Path

import numpy as np
import pytest
from PIL import Image

HERE = Path(__file__).resolve().parent
PKG = HERE.parent
REPO = HERE.parents[4]
sys.path.insert(0, str(PKG.parent))

from h2_bake import determinism as DET  # noqa: E402
from h2_bake import profile as PR  # noqa: E402
from h2_bake import reuse as RU  # noqa: E402

MEDUSA = REPO / "art/pipeline-candidates/ASSET-MEDUSA-001/build-profiles/medusa-h2-bake-h2.json"
MEDUSA_RUN = REPO / "art/pipeline-candidates/ASSET-MEDUSA-001/20260929-h2-bake"
MEDUSA_LD = REPO / "art/pipeline-candidates/ASSET-MEDUSA-001/build-profiles/medusa-h2-lookdev.json"
MEDUSA_LD_RUN = REPO / "art/pipeline-candidates/ASSET-MEDUSA-001/20260929-h2-lookdev"
BLENDER = os.environ.get("H2_BAKE_BLENDER", "C:/Program Files/Blender Foundation/Blender 5.2/blender.exe")
FLAGS = getattr(subprocess, "CREATE_NO_WINDOW", 0)


def medusa():
    return json.loads(MEDUSA.read_text(encoding="utf-8"))


def write(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    if isinstance(data, (dict, list)):
        path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    elif isinstance(data, bytes):
        path.write_bytes(data)
    else:
        path.write_text(data, encoding="utf-8")
    return path


def png(path, arr):
    path.parent.mkdir(parents=True, exist_ok=True)
    Image.fromarray(arr.astype(np.uint8)).save(path)
    return path


# ------------------------------------------------------------------ RB-15: new-hero profile rules
def test_every_committed_h2_profile_still_validates():
    found = 0
    for f in sorted(REPO.glob("art/pipeline-candidates/*/build-profiles/*.json")):
        p = json.loads(f.read_text(encoding="utf-8"))
        if p.get("schema") != PR.SCHEMA:
            continue
        found += 1
        assert PR.profile_version(p) == 1, f.name
        assert PR.validate(p) == [], (f.name, PR.validate(p))
    assert found >= 9  # Medusa + Achilles x4 + Angel + Ancient Leshen x3


def new_hero():
    p = medusa()
    p["asset_id"] = "ASSET-NEWHERO-001"
    return p


def test_new_hero_needs_the_explicit_keys():
    p = new_hero()
    assert PR.profile_version(p) == 2 and PR.is_new_hero_profile(p)
    problems = PR.validate(p)
    assert any("uv.density_reference_part missing" in m for m in problems)
    assert any("preview.frame missing" in m for m in problems)
    assert not any("base_band" in m for m in problems)  # Medusa's tripo_part_2 is a base part of this copy
    body = next(n for n, c in p["parts"].items() if c["mesh"] == "body")
    base = next(n for n, c in p["parts"].items() if c["mesh"] == "base")
    p["uv"]["density_reference_part"] = body
    p["preview"]["frame"] = {"checks_report": "art/imagegen/concept-x-codex/checks-report.json", "side": "right"}
    assert PR.validate(p) == []
    del p["textures"]["team_mask"]["base_band"]["part"]
    assert any("base_band.part missing" in m for m in PR.validate(p))
    p["textures"]["team_mask"]["base_band"]["part"] = body
    assert any("must be a base part" in m and "F29" in m for m in PR.validate(p))
    p["textures"]["team_mask"]["base_band"]["part"] = base
    p["uv"]["density_reference_part"] = base
    assert any("uv.density_reference_part" in m and "must be a body part" in m for m in PR.validate(p))
    p["uv"]["density_reference_part"] = body
    p["preview"]["frame"] = {"checks_report": "art/imagegen/concept-x-codex/checks-report.json"}
    assert any("preview.frame.side" in m for m in PR.validate(p))
    p["preview"]["frame"]["side"] = "left"
    assert PR.validate(p) == []


def test_lookdev_of_a_new_hero_needs_a_frame(tmp_path):
    p = new_hero()
    p["uv"]["density_reference_part"] = next(n for n, c in p["parts"].items() if c["mesh"] == "body")
    p["preview"]["frame"] = {"checks_report": "art/imagegen/concept-x-codex/checks-report.json", "side": "left"}
    src = write(tmp_path / "newhero-h2.json", json.dumps(p))
    ld = json.loads(MEDUSA_LD.read_text(encoding="utf-8"))
    ld["source"]["profile"] = str(src)
    ld.pop("frame", None)
    ldp = write(tmp_path / "newhero-ld.json", json.dumps(ld))
    r = subprocess.run([sys.executable, str(PKG / "run_h2_bake.py"), "--mode", "lookdev", "--profile", str(ldp),
                        "--run-dir", str(tmp_path / "run"), "--stages", "ld_maps"],
                       capture_output=True, text=True, timeout=300, creationflags=FLAGS)
    assert r.returncode != 0 and "needs a top-level `frame`" in r.stderr
    assert not (tmp_path / "run" / "reports").exists() or not list((tmp_path / "run" / "reports").iterdir())


def test_profile_version_marker():
    p = new_hero()
    p["profile_version"] = 1
    assert any("only for the MVP and pilot" in m for m in PR.validate(p))
    p["profile_version"] = True
    assert any("integer" in m for m in PR.validate(p))
    m = medusa()
    m["profile_version"] = 2  # a legacy asset may opt in: then the new rules apply
    assert PR.is_new_hero_profile(m) and any("density_reference_part missing" in s for s in PR.validate(m))
    m = medusa()
    m["uv"]["density_reference_part"] = "tripo_part_99"
    assert any("unknown part" in s for s in PR.validate(m))  # roles are checked for legacy profiles too


# ------------------------------------------------------------------ RB-14: determinism verdict
def make_run(root, n_png_diff=0, png_level=0, fbx=b"FBX-1", stats=1.0, passed=True, jpg=b"J1", extra=None):
    run = root
    rng = np.random.default_rng(0)
    base = rng.integers(0, 250, (300, 300, 3))  # 90 000 px: the share cap allows 9
    arr = base.copy()
    if n_png_diff:
        idx = np.arange(n_png_diff)
        arr[idx // 300, idx % 300, 0] += png_level
    png(run / "textures" / "T_X_N.png", arr)
    png(run / "textures" / "T_X_BC.png", base)
    write(run / "export" / "SK_X.fbx", fbx)
    write(run / "reports" / "textures-report.json",
          {"outputs": {"T_X_N.png": {"sha256": DET.sha256(run / "textures" / "T_X_N.png"), "bytes": 1}},
           "stats": {"mean": stats}})
    write(run / "reports" / "rig-report.json", {"exports": {"path": run.resolve().as_posix() + "/export/SK_X.fbx"}})
    write(run / "reports" / "compose-report.json", {"jpg": jpg.decode()})
    write(run / "reports" / "ld-team-report.json", {"passed": passed, "share": 0.1 if jpg == b"J1" else 0.2})
    write(run / "preview" / "compare-front.jpg", jpg)
    write(run / "reports" / "run-manifest.json", {"t": str(root)})
    for rel, data in (extra or {}).items():
        write(run / rel, data)
    return run


def test_identical_runs_pass_with_tolerance_table(tmp_path):
    a = make_run(tmp_path / "a")
    b = make_run(tmp_path / "b", jpg=b"J2")  # other JPEG + render-derived report: excluded / render rule
    rep = DET.compare(a, b, REPO)
    assert rep["verdict"] == "pass" and rep["scope"] == "full", rep["failures"]
    assert rep["files"]["reports/rig-report.json"]["result"] == "identical after normalisation"
    assert rep["files"]["preview/compare-front.jpg"]["result"] == "excluded"
    assert rep["files"]["reports/ld-team-report.json"]["result"] == "render: verdict agrees"
    assert {t["rule"] for t in rep["tolerances"]} >= {"excluded", "render", "png", "json", "exact", "textures_report"}


def test_png_noise_within_tolerance_and_textures_report(tmp_path):
    a = make_run(tmp_path / "a")
    b = make_run(tmp_path / "b", n_png_diff=6, png_level=1)  # the pilot noise: 1 level in <= 6 px
    rep = DET.compare(a, b, REPO)
    assert rep["verdict"] == "pass", rep["failures"]
    row = rep["files"]["textures/T_X_N.png"]
    assert row["result"] == "within tolerance" and row["max_abs_diff"] == 1 and row["differing_pixels"] == 6
    assert rep["files"]["reports/textures-report.json"]["result"] == "identical after normalisation"


@pytest.mark.parametrize("kw, failing", [
    ({"n_png_diff": 1, "png_level": 3}, "textures/T_X_N.png"),            # > 2 levels
    ({"n_png_diff": 5, "png_level": 1, "stats": 2.0}, "reports/textures-report.json"),  # statistics changed
    ({"fbx": b"FBX-2"}, "export/SK_X.fbx"),                                # FBX byte for byte
    ({"passed": False}, "reports/ld-team-report.json"),                    # render-derived verdict differs
])
def test_outside_tolerance_fails(tmp_path, kw, failing):
    a = make_run(tmp_path / "a")
    b = make_run(tmp_path / "b", **kw)
    rep = DET.compare(a, b, REPO)
    assert rep["verdict"] == "fail" and failing in rep["failures"], rep["failures"]


def test_png_differing_share_cap(tmp_path):
    a = make_run(tmp_path / "a")
    b = make_run(tmp_path / "b", n_png_diff=2, png_level=1)
    assert DET.compare(a, b, REPO)["verdict"] == "pass"
    old = DET.PNG_MAX_DIFFERING_SHARE
    try:
        DET.PNG_MAX_DIFFERING_SHARE = 1.0 / 90000  # 1 px of 300 x 300
        rep = DET.compare(a, b, REPO)
        assert rep["verdict"] == "fail" and "textures/T_X_N.png" in rep["failures"]
    finally:
        DET.PNG_MAX_DIFFERING_SHARE = old


def test_missing_file_fails_and_reused_from_is_ignored(tmp_path):
    a = make_run(tmp_path / "a", extra={"reports/uv-report.json": {"x": 1}})
    b = make_run(tmp_path / "b", extra={"reports/uv-report.json": {"x": 1, "reused_from": {"run": "r2"}}})
    rep = DET.compare(a, b, REPO)
    assert rep["files"]["reports/uv-report.json"]["result"] == "identical after normalisation"
    (b / "export" / "SK_X.fbx").unlink()
    rep = DET.compare(a, b, REPO)
    assert rep["failures"] == {"export/SK_X.fbx": "missing in other run"}


def test_scope_recomputed_stages_only(tmp_path):
    a, b = make_run(tmp_path / "a"), make_run(tmp_path / "b")
    stage_of = lambda r: RU.owner(r) or None  # noqa: E731
    rep = DET.compare(a, b, REPO, stage_of=stage_of, reuse_a={"textures": "r2"}, reuse_b={"textures": "r2"})
    assert rep["scope"] == "recomputed_stages_only" and rep["stages_reused_in_both"] == ["textures"]
    assert rep["files"]["textures/T_X_N.png"]["reused_in_both"] is True
    assert "reused_in_both" not in rep["files"]["export/SK_X.fbx"]
    rep = DET.compare(a, b, REPO, stage_of=stage_of, reuse_a={"textures": "r2"}, reuse_b={})
    assert rep["scope"] == "full"  # reused outputs checked against a fresh run


# ------------------------------------------------------------------ RC-07 / RC-08: ownership, fingerprints, plan
@pytest.mark.parametrize("rel, stage", [
    ("work/hp.blend", "prepare"), ("work/lp.blend1", "retopo"), ("work/lp_closed.blend", "close"),
    ("work/uv/part_ids.npy", "uv"), ("work/uv/position.npy", "aux"), ("work/uv/metal_mask.npy", "textures"),
    ("work/bake/NORMAL.npy", "bake"), ("work/bake/AO_EX_alpha.npy", "aux"), ("work/bake/AO_CTRL.npy", "aux"),
    ("textures/T_X_H2_2K_N.png", "textures"), ("work/rig/export-staging/SK_X.fbx", "rig"), ("export/SK_X.fbx", "rig"),
    ("logs/probe-x-h2-fbx.log", "probes"), ("reports/deform/x-h2-blend-deform.json", "probes"),
    ("work/params/uv.json", "uv"), ("logs/seams.log", "seams"), ("preview/uv-layout-1024.png", "uv"),
    ("preview/compare-front.jpg", "compose"), ("reports/run-manifest.json", "manifest"),
    ("work/stages.json", None), ("reports/determinism-report.json", None), ("notes.txt", ""),
])
def test_owner(rel, stage):
    assert RU.owner(rel) == stage


@pytest.mark.parametrize("run", ["ASSET-MEDUSA-001/20260929-h2-bake", "ASSET-ACHILLES-001/20261014-h2-bake-r3",
                                 "ASSET-ANCIENT-LESHEN-001/20261014-h2-bake-r3", "ASSET-ANGEL-001/20261013-h2-bake"])
def test_every_committed_output_has_an_owner(run):
    d = REPO / "art/pipeline-candidates" / run
    files = [p.relative_to(d).as_posix() for sub in ("export", "textures", "preview", "reports")
             for p in (d / sub).rglob("*") if p.is_file()]
    assert files
    assert [f for f in files if RU.owner(f) == ""] == []


def first_changed(p_old, p_new):
    fp = lambda p: {s: RU.fingerprint(s, p, REPO, "B") for s in RU.REUSABLE}  # noqa: E731
    a, b = fp(p_old), fp(p_new)
    return next((s for s in RU.REUSABLE if RU.differences(b[s], a[s]) != ([], [])), None)


def test_fingerprints_follow_the_profile_blocks():
    p = medusa()
    q = copy.deepcopy(p)
    q["status_note"] = "x"
    q["history"] = {"note": "y"}
    q["profile_id"] = "medusa-h2-bake/9"
    assert first_changed(p, q) is None  # bookkeeping recomputes nothing
    q = copy.deepcopy(p)
    q["rig"].setdefault("junctions", []).append({"part": "tripo_part_0", "with": "tripo_part_1", "band_m": 0.04})
    assert first_changed(p, q) == "rig"  # Achilles r2 -> r3
    q = copy.deepcopy(p)
    q["textures"]["team_mask"]["cloth_hsv"] = {"v_max": 0.5}
    assert first_changed(p, q) == "textures"  # uv reads only team_mask.base_band
    q = copy.deepcopy(p)
    q["textures"]["team_mask"]["base_band"]["width_px"] = 3
    assert first_changed(p, q) == "uv"
    q = copy.deepcopy(p)
    q["seams"]["max_new_blob_px"] = 9
    assert first_changed(p, q) == "seams"
    q = copy.deepcopy(p)
    q["brand_new_key"] = 1  # unmapped key: treated as read by prepare
    assert first_changed(p, q) == "prepare"


def fake_source(root, profile, profile_path, blender=None, skip=()):
    """A finished run with a stage ledger: one small file per owned output pattern of each stage."""
    files = {"prepare": ["work/hp.blend", "reports/prepare-report.json", "logs/prepare.log", "work/params/prepare.json"],
             "retopo": ["work/lp.blend", "reports/retopo-report.json"], "close": ["work/lp_closed.blend", "reports/close-report.json"],
             "uv": ["work/lp_uv.blend", "work/uv/part_ids.npy", "preview/uv-layout-1024.png", "reports/uv-report.json"],
             "bake": ["work/bake/NORMAL.npy", "reports/bake-report.json"], "aux": ["work/uv/position.npy", "reports/aux-report.json"],
             "textures": ["textures/T_Medusa_H2_N.png", "work/uv/metal_mask.npy", "reports/textures-report.json"],
             "rig": ["work/sk_authored.blend", "export/SK_Medusa_H2.fbx", "reports/rig-report.json"],
             "probes": ["reports/probes-report.json"], "seams": ["reports/seams-report.json"],
             "preview": ["reports/preview-report.json"], "compose": ["preview/compare-front.jpg", "reports/compose-report.json"]}
    for stage, rels in files.items():
        for rel in rels:
            if rel.endswith(".json") and rel.startswith("reports/"):
                write(root / rel, {"stage": stage, "path": root.resolve().as_posix() + "/export/x", "passed": True})
            elif rel.endswith(".png"):
                png(root / rel, np.full((4, 4, 3), 7))
            else:
                write(root / rel, b"%s %s" % (stage.encode(), rel.encode()))
        if stage not in skip:
            RU.record(root, stage, RU.fingerprint(stage, profile, REPO, blender), str(profile_path), "sha", 1.0)
    write(root / "work" / "notes" / "scout.txt", "unowned")
    return root


def test_plan_reuses_up_to_the_first_changed_stage(tmp_path):
    p = medusa()
    src = fake_source(tmp_path / "src", p, MEDUSA)
    q = copy.deepcopy(p)
    q["rig"]["max_influences"] = 4 if p["rig"]["max_influences"] != 4 else 3
    plan = RU.plan(src, q, REPO, None, PR.load)
    assert plan["reused"] == ["prepare", "retopo", "close", "uv", "bake", "aux", "textures"]
    assert plan["first_recomputed"] == "rig" and plan["recomputed"][-1] == "manifest"
    assert "profile rig" in next(r for r in plan["stages"] if r["stage"] == "rig")["why"]
    # a stage the old run did not finish stops the reuse there
    src2 = fake_source(tmp_path / "src2", p, MEDUSA, skip=("bake",))
    assert RU.plan(src2, p, REPO, None, PR.load)["first_recomputed"] == "bake"
    # an output removed from the old run after its record
    (src / "work" / "lp.blend").unlink()
    assert RU.plan(src, p, REPO, None, PR.load)["first_recomputed"] == "retopo"


def test_code_drift_is_strict_unless_allowed(tmp_path):
    p = medusa()
    src = fake_source(tmp_path / "src", p, MEDUSA)
    led = RU.load_ledger(src)
    led["stages"]["uv"]["fingerprint"]["code"][RU.PKG + "st_uv.py"] = "0" * 64
    RU.save_ledger(src, led)
    plan = RU.plan(src, p, REPO, None, PR.load)
    assert plan["first_recomputed"] == "uv" and "st_uv.py" in next(r for r in plan["stages"] if r["stage"] == "uv")["why"]
    plan = RU.plan(src, p, REPO, None, PR.load, allow_code_drift=True)
    assert plan["first_recomputed"] is None and plan["reused"][-1] == "compose" and plan["recomputed"] == ["manifest"]
    assert plan["code_drift"] == {"uv": ["st_uv.py"]}


def test_apply_links_copies_reports_and_unshares(tmp_path):
    p = medusa()
    src = fake_source(tmp_path / "src", p, MEDUSA)
    q = copy.deepcopy(p)
    q["seams"]["max_new_blob_px"] = 9
    plan = RU.plan(src, q, REPO, None, PR.load)
    assert plan["first_recomputed"] == "seams"
    new = tmp_path / "new"
    got = RU.apply(plan, new, REPO)
    assert got["link"] + got["copy"] >= 10 and got["unowned"] == ["work/notes/scout.txt"]
    assert not (new / "work" / "params" / "prepare.json").exists()  # params are not carried
    assert not (new / "reports" / "seams-report.json").exists()  # recomputed stage: nothing carried
    rep = json.loads((new / "reports" / "rig-report.json").read_text(encoding="utf-8"))
    assert rep["reused_from"]["stage"] == "rig" and rep["path"] == new.resolve().as_posix() + "/export/x"
    hp = new / "work" / "hp.blend"
    if got["link"]:
        assert hp.stat().st_nlink == 2
        before = RU.snapshot_links(new)
        assert RU.unshare(new, "prepare") >= 1 and not hp.exists() and (src / "work" / "hp.blend").exists()
        # a stage that writes into another stage's hard-linked file is stopped
        before = RU.snapshot_links(new)
        lp = new / "work" / "lp.blend"
        os.utime(lp, ns=(lp.stat().st_atime_ns, lp.stat().st_mtime_ns + 10 ** 9))
        with pytest.raises(RU.ReuseError, match="hard-linked"):
            RU.check_links(new, before, "seams")


def test_ledger_invalidation(tmp_path):
    p = medusa()
    src = fake_source(tmp_path / "src", p, MEDUSA)
    RU.invalidate_from(src, "rig")
    assert sorted(RU.load_ledger(src)["stages"]) == sorted(["prepare", "retopo", "close", "uv", "bake", "aux", "textures"])


def test_legacy_manifest_evidence(tmp_path):
    """A run older than the ledger: fingerprints from run-manifest.json and its profile file (sha256 pinned)."""
    p = medusa()
    prof = write(tmp_path / "prof.json", json.dumps(p))
    src = fake_source(tmp_path / "src", p, prof)
    (src / "work" / "stages.json").unlink()
    code = {}
    for spec in RU.STAGE_INPUTS.values():
        code.update({c: RU.sha256(REPO / c) for c in spec["code"]})
    write(src / "reports" / "run-manifest.json", {
        "schema": RU.RUN_SCHEMA, "blender": None, "profile": {"path": str(prof), "sha256": RU.sha256(prof)},
        "modules": {k[len(RU.PKG):]: v for k, v in code.items() if k.startswith(RU.PKG)},
        "read_only_dependencies": dict({k: v for k, v in code.items() if k.startswith(RU.CB)},
                                       **{p["exports"]["fbx_preset"]: RU.sha256(REPO / p["exports"]["fbx_preset"])}),
        "outputs": {"reports/uv-report.json": {"sha256": RU.sha256(src / "reports/uv-report.json")}}})
    plan = RU.plan(src, p, REPO, None, PR.load)
    assert plan["evidence"].startswith("run-manifest.json")
    assert plan["reused"] == ["prepare", "retopo", "close", "uv", "bake", "aux", "textures"]
    assert "rig-contract.json not recorded" in next(r for r in plan["stages"] if r["stage"] == "rig")["why"]
    write(src / "reports" / "uv-report.json", {"changed": True})  # an output edited after the manifest
    assert RU.plan(src, p, REPO, None, PR.load)["first_recomputed"] == "uv"
    write(prof, json.dumps(dict(p, status="x")))  # the profile file changed since the run
    with pytest.raises(RU.ReuseError, match="changed since the run"):
        RU.plan(src, p, REPO, None, PR.load)


def test_driver_reuse_end_to_end_without_blender(tmp_path):
    """--reuse-from with every stage reusable: only the manifest runs (no Blender needed: the version probe of a
    non-Blender executable gives None, as recorded in the fake ledger); --compare-with the source passes."""
    p = medusa()
    src = fake_source(tmp_path / "src", p, MEDUSA)
    new = tmp_path / "new"
    r = subprocess.run([sys.executable, str(PKG / "run_h2_bake.py"), "--profile", str(MEDUSA), "--run-dir", str(new),
                        "--reuse-from", str(src), "--compare-with", str(src), "--blender", sys.executable],
                       capture_output=True, text=True, timeout=300, creationflags=FLAGS)
    assert r.returncode == 0, r.stdout[-3000:] + r.stderr[-3000:]
    man = json.loads((new / "reports" / "run-manifest.json").read_text(encoding="utf-8"))
    assert man["stages"]["reuse"]["reused"][-1] == "compose" and man["stages"]["stale"] == {}
    assert all(v["reused_from"] for v in man["stages"]["per_stage"].values())
    det = json.loads((new / "reports" / "determinism-report.json").read_text(encoding="utf-8"))
    assert det["verdict"] == "pass" and det["scope"] == "full"
    # a second reuse into a non-empty run directory is refused
    r = subprocess.run([sys.executable, str(PKG / "run_h2_bake.py"), "--profile", str(MEDUSA), "--run-dir", str(new),
                        "--reuse-from", str(src), "--blender", sys.executable],
                       capture_output=True, text=True, timeout=300, creationflags=FLAGS)
    assert r.returncode != 0 and "empty" in (r.stdout + r.stderr)


# ------------------------------------------------------------------ RB-13: look-dev FBX through staging (Blender)
NEED_MEDUSA_LD = pytest.mark.skipif(
    not Path(BLENDER).is_file() or not (MEDUSA_RUN / "work" / "sk_authored.blend").is_file()
    or not (MEDUSA_RUN / "work" / "rig" / "body_vertex_part.npy").is_file(),
    reason="Blender 5.2 or the local Medusa H2 work files (not in git) are missing")


def run_ld_fbx(profile_path, run):
    return subprocess.run([sys.executable, str(PKG / "run_h2_bake.py"), "--mode", "lookdev", "--profile", str(profile_path),
                           "--run-dir", str(run), "--stages", "ld_fbx", "--blender", BLENDER],
                          capture_output=True, text=True, timeout=900, creationflags=FLAGS)


@NEED_MEDUSA_LD
def test_lookdev_fbx_published_after_checks_byte_identical(tmp_path):
    run = tmp_path / "run"
    r = run_ld_fbx(MEDUSA_LD, run)
    assert r.returncode == 0, r.stdout[-3000:] + r.stderr[-3000:]
    committed = json.loads((MEDUSA_LD_RUN / "reports" / "ld-fbx-report.json").read_text(encoding="utf-8"))["exports"]
    for key in ("skeletal_fbx", "base_fbx"):
        name = Path(committed[key]["path"]).name
        assert PR.sha256(run / "export" / name) == committed[key]["sha256"], name
    assert not list((run / "work" / "ld_fbx" / "export-staging").glob("*.fbx"))
    old = (MEDUSA_LD_RUN / "reports" / "ld-fbx-report.json").read_text(encoding="utf-8")
    new = (run / "reports" / "ld-fbx-report.json").read_text(encoding="utf-8")
    assert new.replace(run.resolve().as_posix(), "<run>") == old.replace(
        "art/pipeline-candidates/ASSET-MEDUSA-001/20260929-h2-lookdev", "<run>")


@NEED_MEDUSA_LD
def test_failed_lookdev_fbx_publishes_nothing(tmp_path):
    ld = json.loads(MEDUSA_LD.read_text(encoding="utf-8"))
    ld["uv1"]["density_tolerance"] = 0.0  # uv1_metres_density_readback cannot pass
    pfile = write(tmp_path / "ld-fail.json", json.dumps(ld, ensure_ascii=False))
    run = tmp_path / "run"
    r = run_ld_fbx(pfile, run)
    assert r.returncode != 0
    rep = json.loads((run / "reports" / "ld-fbx-report.json").read_text(encoding="utf-8"))
    assert rep["passed"] is False and "uv1_metres_density_readback" in rep["failed"]
    assert not list((run / "export").glob("*.fbx"))
    staged = sorted(p.name for p in (run / "work" / "ld_fbx" / "export-staging").glob("*.fbx"))
    assert staged == sorted([ld["exports"]["skeletal_fbx"], ld["exports"]["base_fbx"]])
    assert rep["exports"]["skeletal_fbx"]["path"].endswith("/export/" + ld["exports"]["skeletal_fbx"])


# ------------------------------------------------------------------ RB-08 integration (W1-e probes): rig.probe_skip, n/N
def test_probe_skip_key():
    p = medusa()
    assert PR.probe_skip(p) == [] and PR.validate(p) == []  # absent: the probe command line stays as before
    p["rig"]["probe_skip"] = ["shin_l_bend", "shin_r_bend", "foot_l_flex", "foot_r_flex"]  # Ancient Leshen
    assert PR.validate(p) == [] and PR.probe_skip(p) == p["rig"]["probe_skip"]
    wb = next(b[0] for b in p["rig"]["bones"] if b[0].startswith("weapon"))
    p["rig"]["probe_skip"] = ["weapon_turn_" + wb, "hand_l_twist"]
    assert PR.validate(p) == []
    for bad, msg in ((["thigh_l_flex"], "legacy probes"), (["shin_bend"], "unknown probe"),
                     (["weapon_turn_weapon.X"], "unknown probe"), (["foot_l_flex", "foot_l_flex"], "duplicates"),
                     ("shin_l_bend", "must be a list")):
        p["rig"]["probe_skip"] = bad
        assert any(msg in m for m in PR.validate(p)), (bad, PR.validate(p))


def test_probe_skip_recomputes_from_rig():
    p = medusa()
    q = copy.deepcopy(p)
    q["rig"]["probe_skip"] = ["foot_l_flex"]
    assert first_changed(p, q) == "rig"


LESHEN_R3 = REPO / "art/pipeline-candidates/ASSET-ANCIENT-LESHEN-001/build-profiles/ancient-leshen-h2-bake-h2-r3.json"
LEGS = ("shin_l_bend", "shin_r_bend", "foot_l_flex", "foot_r_flex")


def driver():
    import importlib.util
    spec = importlib.util.spec_from_file_location("h2t_run_h2_bake", PKG / "run_h2_bake.py")
    drv = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(drv)
    return drv


def legless_probe(skip=()):
    """A rig_deform_probe report of a trunk without legs (Ancient Leshen): the 7 legacy probes plausible, shins and
    feet unweighted (or skipped), the right forearm and hand twist plausible."""
    legacy = [{"test": n, "status": "plausible"} for n in PR.PROBE_LEGACY]
    ext = [{"test": n, "status": "skipped" if n in skip else "unweighted"} for n in LEGS]
    ext += [{"test": "forearm_r_bend", "status": "plausible"}, {"test": "hand_r_twist", "status": "plausible"}]
    live = [t for t in legacy + ext if t["status"] != "skipped"]
    n = sum(1 for t in live if t["status"] == "plausible")
    return {"tests": legacy, "extended_tests": ext,
            "probes": {"plausible": n, "total": len(live), "summary": "%d/%d" % (n, len(live)), "passed": n == len(live)}}


def test_probes_v1_extended_failures_warn_only():
    """profile_version 1 (the committed Leshen r3 profile, no probe_skip): a rerun passes on the legacy 7, the legless
    extended probes are written to the report and warned about."""
    drv, prof = driver(), PR.load(LESHEN_R3)
    assert PR.profile_version(prof) == 1 and PR.probe_skip(prof) == []
    datas = {"ancient-leshen-h2-blend": legless_probe(), "ancient-leshen-h2-fbx": legless_probe()}
    rep = drv.probe_verdict(datas, prof, [], {"result": "pass"})
    assert rep["passed"] is True and rep["gate"].startswith("legacy 7")
    assert rep["plausible"] == {k: 7 for k in datas} and rep["total"] == {k: 7 for k in datas}
    assert rep["probes"]["ancient-leshen-h2-fbx"] == "9/13"
    assert rep["extended_warnings"]["ancient-leshen-h2-blend"] == list(LEGS)
    assert rep["rig_deform_probe"]["ancient-leshen-h2-blend"]["shin_l_bend"] == "unweighted"
    datas["ancient-leshen-h2-fbx"]["tests"][0]["status"] = "implausible"  # a legacy probe still gates
    assert drv.probe_verdict(datas, prof, [], {"result": "pass"})["passed"] is False


def test_probes_v2_extended_gate_and_skip():
    """profile_version 2 (a new hero): the same legless figure fails without rig.probe_skip and passes with it."""
    drv, prof = driver(), PR.load(LESHEN_R3)
    prof["profile_version"] = 2
    datas = {"x-h2-blend": legless_probe(), "x-h2-fbx": legless_probe()}
    rep = drv.probe_verdict(datas, prof, [], {"result": "pass"})
    assert rep["passed"] is False and rep["gate"].startswith("legacy + extended")
    assert rep["plausible"]["x-h2-fbx"] == 9 and rep["total"]["x-h2-fbx"] == 13 and "extended_warnings" not in rep
    datas = {"x-h2-blend": legless_probe(LEGS), "x-h2-fbx": legless_probe(LEGS)}
    rep = drv.probe_verdict(datas, prof, list(LEGS), {"result": "pass"})
    assert rep["passed"] is True and rep["total"]["x-h2-blend"] == 9 and rep["skipped"] == list(LEGS)
    assert drv.probe_counts({"tests": datas["x-h2-blend"]["tests"]}) == {
        "plausible": 7, "total": 7, "passed": True, "gate": "legacy 7", "summary": "7/7", "extended_failed": []}
