"""Stage-3 tool fixes from the 3d-model-pipeline pilot 2026-10-13 (docs/art-pipeline/evidence/skill-pilot-2026-10-13/
NOTES.md). Every fix is a bug fix or an opt-in key; profiles written before keep their bytes (Medusa).

  F51  textures: a metal-free hero gets an all-zero work/uv/metal_mask.npy (look-dev reads it)
  F52  textures: team_mask_cloth_share is "not applicable" when team_mask.cloth_parts is empty
  F55/F65  seams: the ray grid is pushed out to the posed bounds where a probe pose leaves rest + margin
  F60  compose: an empty preview.closeups; TeamAccent manifest: a profile outside the repo
  F32  ta_report: a failed check raises (the driver exits non-zero, as after ta_maps)
  F25  rig: the FBX pair is staged under work/ and published to export/ only on PASS
  F28/F58  prepare: optional scale.figure_top_part (the budget top: head under a raised blade, skull under antlers)

Plain Python, except the Blender tests (skipped without Blender 5.2 or the local Medusa H2 work files, which are not
in git): the Medusa seams stage re-run gives the committed seams-report.json byte for byte, and a rig run that fails its
checks leaves export/ empty.
Run: python -m pytest tools/tripo-pipeline/blender/h2_bake/tests -q"""

import copy
import importlib.util
import json
import os
import shutil
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

from h2_bake import profile as PR  # noqa: E402

MEDUSA = REPO / "art/pipeline-candidates/ASSET-MEDUSA-001/build-profiles/medusa-h2-bake-h2.json"
MEDUSA_RUN = REPO / "art/pipeline-candidates/ASSET-MEDUSA-001/20260929-h2-bake"
BLENDER = os.environ.get("H2_BAKE_BLENDER", "C:/Program Files/Blender Foundation/Blender 5.2/blender.exe")
FLAGS = getattr(subprocess, "CREATE_NO_WINDOW", 0)


def load_local(name):
    spec = importlib.util.spec_from_file_location("h2p_" + name, PKG / (name + ".py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture()
def medusa():
    return json.loads(MEDUSA.read_text(encoding="utf-8"))


# ------------------------------------------------------------------ textures (F51, F52): a synthetic 64 px atlas
SIZE = 64


def synthetic_run(root, dark_share=0.75):
    """work/uv + work/bake of a two-part figure: tripo_part_0 (cloth, columns 4..31), tripo_part_1 (base, 32..59);
    the cloth is dark on its left `dark_share` and saturated red on the rest."""
    w = root / "work"
    (w / "uv").mkdir(parents=True)
    (w / "bake").mkdir(parents=True)
    (root / "reports").mkdir()  # the driver makes it
    pid = np.full((SIZE, SIZE), -1, np.int64)
    pid[:, 4:32] = 0
    pid[:, 32:60] = 1
    cov = pid >= 0
    np.save(w / "uv" / "part_ids.npy", pid)
    np.save(w / "uv" / "base_band.npy", np.zeros((SIZE, SIZE), bool))
    bc = np.zeros((SIZE, SIZE, 3), np.float32)
    split = 4 + int(round(28 * dark_share))
    bc[:, 4:split] = 0.1
    bc[:, split:32] = (0.9, 0.1, 0.1)
    bc[:, 32:60] = 0.5
    ao = np.repeat(np.linspace(0.3, 1.0, SIZE, dtype=np.float32)[None, :, None], SIZE, 0).repeat(3, 2)
    maps = {"NORMAL": np.broadcast_to(np.array([0.5, 0.5, 1.0], np.float32), (SIZE, SIZE, 3)).copy(), "AO": ao,
            "BC": bc, "RM": np.broadcast_to(np.array([0.0, 0.7, 0.0], np.float32), (SIZE, SIZE, 3)).copy()}
    for k, v in maps.items():
        np.save(w / "bake" / ("%s.npy" % k), v)
    for k in ("NORMAL", "AO", "BC", "RM", "HIT"):
        np.save(w / "bake" / ("%s_alpha.npy" % k), cov)
    return pid


def tex_profile(cloth_parts=("tripo_part_0",), materials=None):
    tm = {"cloth_parts": list(cloth_parts), "base_band": {"part": "tripo_part_1", "normal_z_abs_max": 0.35}, "blur": 0}
    if cloth_parts:
        tm["cloth_hsv"] = {"v_max": 0.4, "s_max": 0.34, "ramp": 0.04}
    t = {"prefix": "T_Synth_H2", "ao_gate": {"min_range_p1_p99": 0, "min_occluded_fraction": 0, "occluded_below": 250},
         "team_mask": tm, "edge_extend_px": 4}
    if materials is not None:
        t["materials"] = materials
    return {"parts": {"tripo_part_0": {"mesh": "body"}, "tripo_part_1": {"mesh": "base"}}, "textures": t}


@pytest.mark.parametrize("materials", [None, {"metal": {}}, {"metal": {"parts": {}}}, {"note": "no metal block"}])
def test_metal_free_hero_writes_a_zero_metal_mask(tmp_path, materials):
    tx = load_local("textures")
    pid = synthetic_run(tmp_path)
    rep = tx.run(tmp_path, tex_profile(materials=materials))
    mask = np.load(tmp_path / "work" / "uv" / "metal_mask.npy")
    assert mask.shape == pid.shape and mask.dtype == np.float32 and not mask.any()
    assert rep["metal_mask"]["value"] == 0.0
    assert not any(k.startswith("h21_") for k in rep["checks"])
    assert rep["passed"]


def test_metal_pass_needs_metal_parts(medusa):
    tx = load_local("textures")
    assert tx.metal_pass(medusa["textures"]["materials"])  # Medusa: the H2.1 metal path as before
    for m in (None, {}, {"metal": None}, {"metal": {}}, {"metal": {"parts": {}}}):
        assert not tx.metal_pass(m)


def test_empty_cloth_parts_is_not_applicable(tmp_path):
    tx = load_local("textures")
    synthetic_run(tmp_path)
    rep = tx.run(tmp_path, tex_profile(cloth_parts=()))
    chk = rep["checks"]["team_mask_cloth_share"]
    assert chk["passed"] and chk["not_applicable"] and chk["measured"] is None
    tm = np.asarray(Image.open(tmp_path / "textures" / "T_Synth_H2_TeamMask.png"))
    assert tm.shape == (SIZE, SIZE, 4) and not tm[..., 0].any()


def test_cloth_parts_keep_the_cloth_share_check(tmp_path):
    tx = load_local("textures")
    synthetic_run(tmp_path, dark_share=0.75)
    rep = tx.run(tmp_path, tex_profile())
    chk = rep["checks"]["team_mask_cloth_share"]
    assert "not_applicable" not in chk and 0.7 <= chk["measured"] <= 0.8 and chk["passed"]
    synthetic_run(tmp_path / "all-dark", dark_share=1.0)  # the old gate still fails a cloth part with no trim at all
    with pytest.raises(RuntimeError, match="team_mask_cloth_share"):
        tx.run(tmp_path / "all-dark", tex_profile())


def test_cloth_weight_and_remap_without_cloth():
    mat = load_local("materials")
    tx = load_local("textures")
    helpers = type("TX", (), {"rgb_to_hsv": staticmethod(tx.rgb_to_hsv)})
    pid = np.zeros((8, 8), np.int64)
    w = mat.cloth_weight(np.full((8, 8, 3), 0.1, np.float32), pid, ["tripo_part_0"], {"cloth_parts": []}, helpers)
    assert w.shape == (8, 8) and not w.any()
    rng = np.random.default_rng(0)
    maps = {"BC": rng.random((8, 8, 3)).astype(np.float32), "RM": rng.random((8, 8, 3)).astype(np.float32)}
    m = np.zeros((8, 8), np.float32)
    m[:4] = 1.0
    cfg = {"metal": {"basecolor": {"target_srgb": "#C8A050", "detail_clip": [0.5, 1.5], "detail_gamma": 0.5},
                     "roughness": {"min": 0.32, "max": 0.45}, "metallic": {"min": 0.9, "max": 1.0}},
           "cloth_roughness": {"lo": 0.8, "hi": 0.9, "apply": True}}
    st = mat.remap(maps, np.ones((8, 8), bool), m, w, cfg)
    assert st["before"]["cloth"] == {"texels": 0} and st["after"]["cloth"] == {"texels": 0}
    assert st["after"]["metal"]["texels"] == 32 and np.isfinite(maps["BC"]).all()


# ------------------------------------------------------------------ seams ray grid (F55 / F65)
def old_grid(rest_lo, rest_hi, margin):
    """The arithmetic of st_seams.see_through before the fix."""
    return np.asarray(rest_lo) - margin, np.asarray(rest_hi) + margin


def test_grid_unchanged_when_the_poses_stay_inside():
    # Medusa (measured 2026-10-14 on 20260929-h2-bake): arm_l_raise lifts the bow 92.8 mm past the rest +X bound,
    # thigh flex moves the base edge 18.5 mm; margin 0.1
    rest_lo, rest_hi = np.array([-0.151, -0.152, 0.0]), np.array([0.153, 0.149, 0.551])
    posed_lo, posed_hi = rest_lo - [0.0, 0.0185, 0.0], rest_hi + [0.0928, 0.0, 0.0]
    lo, hi, ext = PR.seams_grid_bounds(rest_lo, rest_hi, posed_lo, posed_hi, {"pitch_m": 0.0015, "margin_m": 0.1})
    olo, ohi = old_grid(rest_lo, rest_hi, 0.1)
    assert ext is None and np.array_equal(lo, olo) and np.array_equal(hi, ohi)
    lo, hi, ext = PR.seams_grid_bounds(rest_lo, rest_hi, posed_lo, posed_hi, {})  # defaults 0.1 / 0.005
    assert ext is None and np.array_equal(lo, olo)


def test_grid_extends_where_a_pose_leaves():
    # Achilles (20261013-h2-bake-2): arm_r_raise takes the spear 164.4 mm past the rest -X bound
    rest_lo, rest_hi = np.array([-0.2, -0.15, 0.0]), np.array([0.2, 0.16, 0.6])
    posed_lo, posed_hi = rest_lo - [0.1644, 0.0191, 0.0], rest_hi + [0.079, 0.0, 0.0]
    lo, hi, ext = PR.seams_grid_bounds(rest_lo, rest_hi, posed_lo, posed_hi, {"margin_m": 0.1})
    olo, ohi = old_grid(rest_lo, rest_hi, 0.1)
    assert lo[0] == pytest.approx(posed_lo[0] - 0.005) and lo[0] < olo[0]
    assert lo[1] == olo[1] and lo[2] == olo[2] and np.array_equal(hi, ohi)
    assert ext == [[pytest.approx(0.0694), 0.0, 0.0], [0.0, 0.0, 0.0]]
    lo2, _hi2, ext2 = PR.seams_grid_bounds(rest_lo, rest_hi, posed_lo, posed_hi,
                                           {"margin_m": 0.1, "posed_clearance_m": 0.02})
    assert lo2[0] == pytest.approx(posed_lo[0] - 0.02) and ext2[0][0] == pytest.approx(0.0844)
    _lo3, _hi3, ext3 = PR.seams_grid_bounds(rest_lo, rest_hi, posed_lo, posed_hi, {"margin_m": 0.2})  # pilot workaround
    assert ext3 is None


# ------------------------------------------------------------------ scale.figure_top_part (F28 / F58)
def test_figure_top_part_absent_is_the_old_rule(medusa, tmp_path):
    assert PR.figure_top_part(medusa) is None and PR.figure_top_part_problems(medusa) == []
    tops = {"tripo_part_0": 0.31, "tripo_part_4": 0.52, "tripo_part_13": 0.61}
    assert PR.figure_top_source_z(medusa, tops) == 0.61
    assert PR.frame_top_m(medusa, tmp_path / "no-run") is medusa["scale"]["figure_top_m"]  # no report read


def test_figure_top_part_maps_the_part_top(medusa, tmp_path):
    p = copy.deepcopy(medusa)
    body = sorted(n for n, c in p["parts"].items() if c["mesh"] == "body")[0]
    p["scale"]["figure_top_part"] = body
    assert PR.validate(p) == []
    tops = {body: 0.9, "x": 1.2}
    assert PR.figure_top_source_z(p, tops) == 0.9
    m = PR.frame_map(((-0.1, -0.1, 0.0), (0.1, 0.1, 0.06)), 0.9, p["scale"])
    assert PR.map_point(m, (0.0, 0.0, 0.9), False)[2] == pytest.approx(0.55)  # the head lands on the budget top
    assert PR.map_point(m, (0.0, 0.0, 1.2), False)[2] > 0.55  # a raised blade stays above it
    (tmp_path / "reports").mkdir()
    (tmp_path / "reports" / "prepare-report.json").write_text(
        json.dumps({"figure_bounds_final_m": [[-0.1, -0.1, 0.06], [0.1, 0.1, 0.71234]]}), encoding="utf-8")
    assert PR.frame_top_m(p, tmp_path) == 0.71234  # the concept framing spans the whole silhouette


@pytest.mark.parametrize("value, message", [("tripo_part_99", "unknown part"), ("BASE", "is the base")])
def test_figure_top_part_validation(medusa, value, message):
    p = copy.deepcopy(medusa)
    base = next(n for n, c in p["parts"].items() if c["mesh"] == "base")
    p["scale"]["figure_top_part"] = base if value == "BASE" else value
    assert any(message in s for s in PR.validate(p))


# ------------------------------------------------------------------ compose with an empty preview.closeups (F60)
def compose_profile(baseline=False):
    p = json.loads(MEDUSA.read_text(encoding="utf-8"))
    pv = p["preview"]
    for k in ("previous_candidate", "pose_closeups", "channel_views", "quality_reference") + (() if baseline else ("baseline",)):
        pv.pop(k, None)
    pv["closeups"] = []
    return p


def write_compose_inputs(run, p, baseline=False):
    raw = run / "work" / "preview_raw"
    raw.mkdir(parents=True)
    tags = ("hp", "h2") + (("base",) if baseline else ())
    for v in ("front", "side", "back"):
        for t in tags:
            Image.new("RGB", (102, 136), (90, 90, 90)).save(raw / ("ortho-%s-%s.png" % (v, t)))
    for k in p["preview"]["k2"]["distances_uu"]:
        for t in ("h2",) + (("base",) if baseline else ()):
            Image.new("RGBA", (192, 108), (90, 90, 90, 255)).save(raw / ("%s-%s.png" % (k, t)))
    (run / "reports").mkdir(parents=True)
    (run / "reports" / "rig-report.json").write_text(json.dumps(
        {"meshes_pre_export": {p["meshes"]["body"]: {"triangles": 41000}, p["meshes"]["base"]: {"triangles": 900}}}),
        encoding="utf-8")


@pytest.mark.parametrize("baseline", [False, True])
def test_compose_with_empty_closeups(tmp_path, baseline):
    comp = load_local("compose")
    p = compose_profile(baseline)
    write_compose_inputs(tmp_path, p, baseline)
    written = comp.run(tmp_path, p, REPO)
    assert "closeups-hp-vs-h2.jpg" not in written and "closeups-h2-vs-h21.jpg" not in written
    assert {"compare-front.jpg", "compare-k2-5x.jpg"} <= set(written)
    if baseline:
        assert "compare-h21-front.jpg" in written
    rep = json.loads((tmp_path / "reports" / "compose-report.json").read_text(encoding="utf-8"))
    assert rep["skipped"] == {"closeups-hp-vs-h2.jpg": "preview.closeups is empty"}


# ------------------------------------------------------------------ ta_report exits non-zero (F32), manifest path (F60)
def ta_fixture(tmp_path, monkeypatch, back_share):
    acc = load_local("lookdev_accent")
    monkeypatch.setattr(acc, "presets", lambda repo: {"classes": [{"id": "linen", "index": 1},
                                                                  {"id": "gold_antique", "index": 2}]})
    monkeypatch.setattr(acc, "sheets", lambda *a, **k: {})
    shares = {"k2_5x_front": 0.04, "k2_5x_back": back_share}

    def metrics(rdir, view, cidx, near_px, cloth, trim):
        e = {"screen_share_of_figure": shares[view], "delta_e_p1_vs_p2_accent": 40.0}
        for s in ("ld_p1", "ld_p2"):
            e[s] = {"delta_e_accent_vs_dress": 30.0}
            e["dress_unchanged_" + s] = {"share_delta_e_lt_3": 0.95, "dress_px": 900}
            e["gold_unchanged_" + s] = {"median_delta_e": 0.0}
        return e

    monkeypatch.setattr(acc, "view_metrics", metrics)
    (tmp_path / "reports").mkdir()
    (tmp_path / "reports" / "ld-team-accent-report.json").write_text(json.dumps(
        {"team_dye_gain": {"TeamDyeGain": 10.0}, "passed": True, "checks": {}}), encoding="utf-8")
    rdir = tmp_path / "work" / "ta" / "render"
    rdir.mkdir(parents=True)
    (rdir / "render-report.json").write_text(json.dumps({"lights": {"cobble": {"k1_board_p50": 131.0}}, "frames": []}),
                                             encoding="utf-8")
    ta = {"profile_id": "synth-ta/1", "team_accent": {"hem": {"cloth_class": "linen", "band_class": "gold_antique"}},
          "render": {"views": list(shares), "near_px": 4,
                     "readability": {"delta_e_accent_vs_dress_min": 15, "delta_e_p1_vs_p2_min": 20,
                                     "screen_share_min": 0.01, "dress_unchanged_share_min": 0.9,
                                     "gold_median_delta_e_max": 2.0}},
          "cobble": {"exposure_calibration": {"target_board_p50_luma": 131.2, "tolerance_luma": 3.0}}}
    return acc, ta


def test_ta_report_passes_and_returns(tmp_path, monkeypatch):
    acc, ta = ta_fixture(tmp_path, monkeypatch, back_share=0.03)
    rep = acc.run_report(tmp_path, ta, REPO)
    assert rep["passed"]


def test_ta_report_failure_raises_after_writing_the_report(tmp_path, monkeypatch):
    acc, ta = ta_fixture(tmp_path, monkeypatch, back_share=0.0)
    with pytest.raises(RuntimeError, match="team_accent_visible_k2_5x_front_and_back"):
        acc.run_report(tmp_path, ta, REPO)
    rep = json.loads((tmp_path / "reports" / "ld-team-report.json").read_text(encoding="utf-8"))
    assert rep["passed"] is False


def test_repo_rel_outside_the_repo(tmp_path):
    acc = load_local("lookdev_accent")
    assert acc.repo_rel(MEDUSA, REPO) == "art/pipeline-candidates/ASSET-MEDUSA-001/build-profiles/medusa-h2-bake-h2.json"
    outside = tmp_path / "scratch-profile.json"
    assert acc.repo_rel(outside, REPO) == outside.resolve().as_posix()


# ------------------------------------------------------------------ Blender: Medusa seams and the rig staging (F55, F25)
NEED_MEDUSA_WORK = pytest.mark.skipif(
    not Path(BLENDER).is_file() or not (MEDUSA_RUN / "work" / "sk_authored.blend").is_file()
    or not (MEDUSA_RUN / "work" / "probe-fbx-authored.blend").is_file() or not (MEDUSA_RUN / "work" / "lp_uv.blend").is_file(),
    reason="Blender 5.2 or the local Medusa H2 work files (not in git) are missing")


def run_stage(run, profile_path, stage, timeout=900):
    return subprocess.run([sys.executable, str(PKG / "run_h2_bake.py"), "--profile", str(profile_path), "--run-dir", str(run),
                           "--stages", stage, "--blender", BLENDER], capture_output=True, text=True, timeout=timeout,
                          creationflags=FLAGS)


@NEED_MEDUSA_WORK
def test_medusa_seams_report_is_byte_identical(tmp_path):
    """Medusa's probe poses stay inside rest + margin (92.8 of 100 mm): the grid, the pixel phases and the report keep
    their bytes with the posed-bounds grid."""
    prof = json.loads(MEDUSA.read_text(encoding="utf-8"))
    run = tmp_path / "run"
    for rel in ("work/sk_authored.blend", "work/probe-fbx-authored.blend", "reports/close-report.json",
                "textures/%s_2K_BC.png" % prof["textures"]["prefix"]):
        (run / rel).parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(MEDUSA_RUN / rel, run / rel)
    (run / "work" / "rig").mkdir(parents=True)
    for npy in (MEDUSA_RUN / "work" / "rig").glob("*.npy"):
        shutil.copy2(npy, run / "work" / "rig" / npy.name)
    r = run_stage(run, MEDUSA, "seams")
    assert r.returncode == 0, r.stdout[-3000:] + r.stderr[-3000:]
    got = (run / "reports" / "seams-report.json").read_bytes()
    assert got == (MEDUSA_RUN / "reports" / "seams-report.json").read_bytes()
    assert b"grid_extended_by_posed_bounds_m" not in got


@NEED_MEDUSA_WORK
def test_failed_rig_publishes_nothing(tmp_path):
    """A rig that fails its checks (face region moved away: 0 face polygons, as Achilles' first run) leaves export/
    without FBX; the pair stays under work/rig/export-staging."""
    prof = json.loads(MEDUSA.read_text(encoding="utf-8"))
    face = next(d for d in prof["retopo"]["dense_regions"] if d["name"] == "face")
    face["box_m"] = [[5.0, 5.0, 5.0], [6.0, 6.0, 6.0]]
    pfile = tmp_path / "medusa-rig-fail.json"
    pfile.write_text(json.dumps(prof, ensure_ascii=False), encoding="utf-8")
    run = tmp_path / "run"
    (run / "work").mkdir(parents=True)
    (run / "textures").mkdir()
    shutil.copy2(MEDUSA_RUN / "work" / "lp_uv.blend", run / "work" / "lp_uv.blend")
    bc = "%s_BC.png" % prof["textures"]["prefix"]
    shutil.copy2(MEDUSA_RUN / "textures" / bc, run / "textures" / bc)
    r = run_stage(run, pfile, "rig")
    assert r.returncode != 0
    rep = json.loads((run / "reports" / "rig-report.json").read_text(encoding="utf-8"))
    assert rep["passed"] is False and "export_frame_face_points_along_rotated_front" in rep["failed"]
    assert not list((run / "export").glob("*.fbx"))
    staged = sorted(p.name for p in (run / "work" / "rig" / "export-staging").glob("*.fbx"))
    assert staged == sorted([prof["exports"]["skeletal_fbx"], prof["exports"]["base_fbx"]])
    assert rep["exports"]["skeletal_fbx"]["path"].endswith("/export/" + prof["exports"]["skeletal_fbx"])
