"""W2-c opt-in options of the skill pilot (2026-10-14): base.flatten_bottom (F83, prepare), base.rim_smooth (F104, retopo),
textures.team_mask.base_band.height_m (F143 / F150, uv: TeamMask.G + base vertex mask UM_Mask.R), textures.band_repaint
(F107, textures) and the look-dev metal_f0 (F138, ld_maps). A profile without a key takes the old code path.

Plain Python: validation, the stage-input map of reuse.py, the bpy-free helpers (base_ops.py, materials.band_repaint,
lookdev.metal_f0) on synthetic data. Blender headless (skipped without Blender 5.2): the uv-stage vertex mask on a toy
two-tier base survives an FBX round trip with the export setting of candidate_build.core (colors_type SRGB).
Run: python -m pytest tools/tripo-pipeline/blender/h2_bake/tests -q"""

import copy
import json
import math
import os
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest

HERE = Path(__file__).resolve().parent
PKG = HERE.parent
REPO = HERE.parents[4]
sys.path.insert(0, str(PKG.parent))

from h2_bake import base_ops as B  # noqa: E402
from h2_bake import lookdev as LD  # noqa: E402
from h2_bake import materials as MAT  # noqa: E402
from h2_bake import profile as PR  # noqa: E402
from h2_bake import reuse as RU  # noqa: E402
from h2_bake import textures as TX  # noqa: E402

MEDUSA = REPO / "art/pipeline-candidates/ASSET-MEDUSA-001/build-profiles/medusa-h2-bake-h2.json"
BLENDER = os.environ.get("H2_BAKE_BLENDER", "C:/Program Files/Blender Foundation/Blender 5.2/blender.exe")
FLAGS = getattr(subprocess, "CREATE_NO_WINDOW", 0)


@pytest.fixture()
def medusa():
    return json.loads(MEDUSA.read_text(encoding="utf-8"))


def part_of(p, role):
    return next(n for n, c in sorted(p["parts"].items()) if c["mesh"] == role)


# ------------------------------------------------------------------ profile: absent keys, valid and invalid values
def test_profiles_without_the_keys_are_unchanged(medusa):
    assert "base" not in medusa and "band_repaint" not in medusa["textures"]
    assert PR.base_flatten(medusa) is None and PR.base_rim_smooth(medusa) is None
    assert PR.base_band_height(medusa) is None and PR.band_repaint(medusa) == []
    assert PR.w2c_problems(medusa) == [] and PR.validate(medusa) == []


def test_valid_w2c_keys(medusa):
    p = copy.deepcopy(medusa)
    body, base = part_of(p, "body"), part_of(p, "base")
    p["base"] = {"flatten_bottom": {}, "rim_smooth": {"z_band_m": [0.05, 0.064], "parts": [base, body]}, "note": "x"}
    p["textures"]["team_mask"]["base_band"]["height_m"] = [0.0, 0.0325]
    other = next(n for n in p["parts"] if n not in (body, base))
    p["textures"]["band_repaint"] = [{"name": "collar", "part": body, "near": [other], "band_m": 0.01,
                                      "keep_hsv": {"s_min": 0.6}, "detail": [0.85, 1.15],
                                      "exclude_boxes_m": [{"min_m": [0, 0, 0], "max_m": [0.1, 0.1, 0.1]}]}]
    assert PR.validate(p) == []
    assert PR.base_flatten(p) == {} and PR.base_rim_smooth(p)["z_band_m"] == [0.05, 0.064]
    assert PR.base_band_height(p) == [0.0, 0.0325] and PR.band_repaint(p)[0]["name"] == "collar"


@pytest.mark.parametrize("patch, message", [
    ({"base": []}, "base must be an object"),
    ({"base": {"flatten": {}}}, "base: unknown key flatten"),
    ({"base": {"flatten_bottom": True}}, "flatten_bottom must be an object"),
    ({"base": {"flatten_bottom": {"band_m": 0.02}}}, "band_m must be in [0, 0.015]"),
    ({"base": {"flatten_bottom": {"floor_quantile": 1.5}}}, "floor_quantile must be in [0, 1]"),
    ({"base": {"flatten_bottom": {"down_normal_z": 0.2}}}, "down_normal_z must be in (-1, 0)"),
    ({"base": {"rim_smooth": {}}}, "z_band_m must be [z0, z1]"),
    ({"base": {"rim_smooth": {"z_band_m": [0.06, 0.05]}}}, "z_band_m must be [z0, z1]"),
    ({"base": {"rim_smooth": {"z_band_m": [0.05, 0.06], "max_shift_m": 0.01}}}, "max_shift_m must be in (0, 0.004]"),
    ({"base": {"rim_smooth": {"z_band_m": [0.05, 0.06], "parts": ["tripo_part_99"]}}}, "unknown part tripo_part_99"),
    ({"base": {"rim_smooth": {"z_band_m": [0.05, 0.06], "ring_weight": 2}}}, "ring_weight must be in [0, 1]"),
    ({"height_m": [0.03, 0.01]}, "height_m must be [z0, z1]"),
    ({"height_m": [0.0, 0.2]}, "height_m must be [z0, z1]"),
    ({"band_repaint": []}, "band_repaint must be a non-empty list"),
    ({"band_repaint": [{"name": "a", "part": "BODY", "near": ["BODY"], "band_m": 0.01}]}, "near must be a non-empty list"),
    ({"band_repaint": [{"name": "a", "part": "BODY", "near": ["BASE"], "band_m": 0.1}]}, "band_m must be in (0, 0.05]"),
    ({"band_repaint": [{"name": "a", "part": "BODY", "near": ["BASE"], "band_m": 0.01, "keys": ["N"]}]}, "keys must be"),
    ({"band_repaint": [{"name": "a", "part": "BODY", "near": ["BASE"], "band_m": 0.01, "feather_m": 0.02}]}, "feather_m"),
    ({"band_repaint": [{"name": "a", "part": "BODY", "near": ["BASE"], "band_m": 0.01, "detail": [1.2, 1.5]}]}, "detail"),
    ({"band_repaint": [{"name": "a", "part": "BODY", "near": ["BASE"], "band_m": 0.01},
                       {"name": "a", "part": "BODY", "near": ["BASE"], "band_m": 0.01}]}, "unique"),
    ({"band_repaint": [{"name": "a", "part": "BODY", "near": ["BASE"], "band_m": 0.01,
                        "include_boxes_m": [{"min_m": [0, 0, 0], "max_m": [0, 1, 1]}]}]}, "with min < max"),
])
def test_invalid_w2c_keys(medusa, patch, message):
    p = copy.deepcopy(medusa)
    sub = {"BODY": part_of(p, "body"), "BASE": part_of(p, "base")}
    for key, value in patch.items():
        value = json.loads(json.dumps(value).replace('"BODY"', json.dumps(sub["BODY"])).replace('"BASE"', json.dumps(sub["BASE"])))
        if key == "base":
            p["base"] = value
        elif key == "height_m":
            p["textures"]["team_mask"]["base_band"]["height_m"] = value
        else:
            p["textures"][key] = value
    problems = PR.validate(p)
    assert any(message in s for s in problems), problems


# ------------------------------------------------------------------ reuse: which stage reads the new keys
def test_stage_inputs_and_unset_keys(medusa):
    assert "base.flatten_bottom" in RU.STAGE_INPUTS["prepare"]["profile"]
    assert "base.rim_smooth" in RU.STAGE_INPUTS["retopo"]["profile"]
    assert RU.PKG + "base_ops.py" in RU.STAGE_INPUTS["uv"]["code"]
    assert "base" not in RU.unmapped_keys(dict(medusa, base={}))  # a base block recomputes from prepare, not everything
    new = RU.fingerprint("prepare", medusa, REPO, "B")
    old = copy.deepcopy(new)
    del old["profile"]["base.flatten_bottom"]  # a ledger written before the key was mapped
    assert RU.differences(new, old) == ([], [])
    p = copy.deepcopy(medusa)
    p["base"] = {"flatten_bottom": {}}
    assert RU.differences(RU.fingerprint("prepare", p, REPO, "B"), old)[0] == ["profile base.flatten_bottom"]
    # a rim smoothing change leaves prepare reusable and recomputes from retopo
    p["base"] = {"rim_smooth": {"z_band_m": [0.05, 0.06]}}
    assert RU.differences(RU.fingerprint("prepare", p, REPO, "B"), new) == ([], [])
    assert RU.differences(RU.fingerprint("retopo", p, REPO, "B"),
                          RU.fingerprint("retopo", medusa, REPO, "B"))[0] == ["profile base.rim_smooth"]


# ------------------------------------------------------------------ base_ops: flatten, profile, rim, band
def test_floor_level_is_the_area_weighted_quantile():
    z = np.array([0.0, 0.001, 0.006, 0.0063, 0.5])
    nz = np.array([-1.0, -1.0, -1.0, -0.9, 1.0])  # the last face looks up: not part of the underside
    area = np.array([0.1, 0.1, 1.0, 1.0, 50.0])
    assert B.floor_level(z, nz, area, {}) == pytest.approx(0.006)
    assert B.floor_level(z, nz, area, {"floor_quantile": 0.0}) == pytest.approx(0.0)
    with pytest.raises(ValueError):
        B.floor_level(z, np.ones(5), area, {})


def test_flatten_z_snap_raises_bumps_lowers_lifted_rim_keeps_top():
    z = np.array([0.0, 0.002, 0.003, 0.0035, 0.01, 0.006, 0.03, 0.06])
    co = np.stack([np.arange(8) * 0.01, np.zeros(8), z], 1)
    bottom = np.array([True, True, True, True, True, False, False, False])
    out, st = B.flatten_z(co, bottom, 0.003, 0.008)  # falloff 0: snap
    assert out[:5] == pytest.approx([0, 0, 0, 0, 0], abs=1e-12)  # bump (0, 2 mm) up, lifted rim (3.5, 10 mm) down
    assert out[5] == pytest.approx((0.006 - 0.003) * 0.06 / 0.057)  # a wall vertex above the floor: rescaled only
    assert out[-1] == 0.06 and st["raised_to_floor"] == 2 and st["lowered_to_floor"] == 2
    assert st["max_raise_mm"] == pytest.approx(3.0) and st["max_lower_mm"] == pytest.approx(7.0)
    out2, st2 = B.flatten_z(co, bottom, 0.0, 0.0)  # floor at the minimum and no band: nothing moves
    assert out2 == pytest.approx(z) and st2["raised_to_floor"] == st2["lowered_to_floor"] == 0


def test_flatten_z_falloff_moves_the_wall_above_a_lifted_rim():
    # underside: a flat floor at 0 except a rim vertex lifted 4 mm at x = 0.15; a wall above the lifted rim (x = 0.15)
    # at 6, 10 and 30 mm and a wall above the flat part (x = -0.15) at 6 mm
    co = np.array([[0.0, 0.0, 0.0], [0.15, 0.0, 0.004], [-0.15, 0.0, 0.0],
                   [0.15, 0.0, 0.006], [0.15, 0.0, 0.010], [0.15, 0.0, 0.030], [-0.15, 0.0, 0.006], [0.0, 0.0, 0.06]])
    bottom = np.array([True, True, True, False, False, False, False, False])
    out, st = B.flatten_z(co, bottom, 0.0, 0.008, 0.012, k=1)
    assert out[1] == pytest.approx(0.0, abs=1e-12)  # the lifted rim reaches the floor
    assert out[3] == pytest.approx(0.006 - 0.004 * (1 - 0.002 / 0.012))  # 2 mm above the rim: most of the lift
    assert out[4] == pytest.approx(0.010 - 0.004 * (1 - 0.006 / 0.012))  # 6 mm above: half of it
    assert out[5] == 0.030 and out[6] == 0.006 and out[7] == 0.06  # above the falloff / over the flat floor: unchanged
    assert np.all(np.diff(out[[1, 3, 4, 5]]) > 0)  # the wall keeps its order: no fold
    assert st["followers_lowered"] == 2 and st["lowered_to_floor"] == 1
    # the brute-force neighbour search and a scipy KD-tree agree
    from scipy.spatial import cKDTree
    out_kd, _ = B.flatten_z(co, bottom, 0.0, 0.008, 0.012, k=1,
                            nearest=lambda s, q, k: cKDTree(s).query(q, k=k))
    assert out_kd == pytest.approx(out)


def disc(n=48, r=0.15, h=0.06, lift=None):
    """Closed prism: bottom ring (z from lift(angle)), top ring, centre vertices; triangles."""
    a = np.linspace(0, 2 * np.pi, n, endpoint=False)
    zb = np.zeros(n) if lift is None else lift(a)
    co = np.concatenate([np.stack([r * np.cos(a), r * np.sin(a), zb], 1), np.stack([r * np.cos(a), r * np.sin(a), np.full(n, h)], 1),
                         [[0, 0, 0], [0, 0, h]]])
    tris = []
    for i in range(n):
        j = (i + 1) % n
        tris += [[i, j, n + j], [i, n + j, n + i], [2 * n, j, i], [2 * n + 1, n + i, n + j]]
    return co, np.array(tris)


def test_bottom_profile_flat_and_lifted():
    co, tris = disc()
    flat = B.bottom_profile(co, tris, 0)
    assert flat["columns"] > 200 and flat["share_gt_1mm"] == 0.0 and flat["max_mm"] == pytest.approx(0.0, abs=1e-9)
    co2, tris2 = disc(lift=lambda a: np.where(np.cos(a) > 0.5, 0.004, 0.0))  # the +X third of the rim lifted 4 mm
    front = B.bottom_profile(co2, tris2, 0)  # seen from the front the lifted arc is the right end of the bottom edge
    side = B.bottom_profile(co2, tris2, 1)  # seen from the side the flat rest of the underside hides it
    assert 0.15 < front["share_gt_1mm"] < 0.3 and front["max_mm"] < 4.0
    assert side["share_gt_1mm"] == 0.0


def zigzag_loop(n=120, r=0.04, z0=0.058, amp=0.0012):
    a = np.linspace(0, 2 * np.pi, n, endpoint=False)
    return np.stack([r * np.cos(a), r * np.sin(a), z0 + amp * (-1) ** np.arange(n)], 1)


def test_smooth_loop_removes_teeth_within_the_clamp():
    pts = zigzag_loop()
    z_new, st = B.smooth_loop_z(pts, 0.006, 0.002)
    assert st["tooth_mm_p95_max_before"][1] > 1.0 and st["tooth_mm_p95_max_after"][1] < 0.1
    assert np.abs(z_new - pts[:, 2]).max() <= 0.002 + 1e-12
    _z, st2 = B.smooth_loop_z(pts, 0.006, 0.0005)  # clamp binds: every vertex moves 0.5 mm at most
    assert st2["max_shift_mm"] == pytest.approx(0.5) and st2["clamped_vertices"] == 120
    flat = zigzag_loop(amp=0.0)
    z3, st3 = B.smooth_loop_z(flat, 0.006, 0.002)
    assert z3 == pytest.approx(flat[:, 2]) and st3["max_shift_mm"] == pytest.approx(0.0, abs=1e-9)
    assert B.loop_in_band(pts, (0.05, 0.064)) and not B.loop_in_band(pts, (0.0585, 0.064))


def test_height_band_and_corner_colours():
    fz = np.array([0.001, 0.02, 0.031, 0.034, 0.05, 0.0])
    fnz = np.array([0.0, 0.1, 0.9, 1.0, 0.0, -1.0])  # the last face is the underside
    band = B.height_band_faces(fz, fnz, [0.0, 0.0325])
    assert band.tolist() == [True, True, True, False, False, False]
    cols = B.mask_corner_colours(band, [3, 3, 4, 3, 3, 3])
    assert cols.shape == (19, 4) and cols.dtype == np.float32
    assert cols[:10, 0].tolist() == [1.0] * 10 and cols[10:, 0].tolist() == [0.0] * 9
    assert (cols[:, 1:3] == 0).all() and (cols[:, 3] == 1).all()  # G = B = 0: no instance pips


# ------------------------------------------------------------------ textures: band repaint on a synthetic atlas
def tx_namespace():
    return SimpleNamespace(rgb_to_hsv=TX.rgb_to_hsv, bilinear=TX.bilinear, dilate=TX.dilate, blur3=TX.blur3)


def test_band_repaint_replaces_the_smear_and_nothing_else():
    s = 64
    part_ids = np.full((s, s), -1, np.int32)
    part_ids[:, :48] = 0  # cloak: x = column (1 mm per texel), the neck (part 1) sits at x < 0 in 3D
    part_ids[:, 52:] = 1
    pos = np.zeros((s, s, 3), np.float32)
    xs = np.arange(s, dtype=np.float32)
    pos[..., 0] = np.where(xs[None, :] < 48, xs[None, :] * 0.001, -(xs[None, :] - 52) * 0.001 - 0.001)
    pos[..., 2] = np.arange(s, dtype=np.float32)[:, None] * 0.001
    ok = part_ids >= 0
    red = np.array([0.55, 0.12, 0.12], np.float32)
    bc = np.zeros((s, s, 3), np.float32)
    bc[part_ids == 0] = red
    bc[part_ids == 1] = [0.8, 0.6, 0.45]
    bc[:, :6] = [0.62, 0.58, 0.40]  # olive-beige smear in the first 6 mm next to the neck
    maps = {"BC": bc.copy(), "RM": np.zeros((s, s, 3), np.float32), "AO": np.ones((s, s, 3), np.float32)}
    alpha = {k: ok.copy() for k in ("BC", "RM", "AO", "NORMAL", "HIT")}
    cfg = {"name": "collar", "part": "p0", "near": ["p1"], "band_m": 0.0085, "ring_m": 0.006, "feather_m": 0.002,
           "keep_hsv": {"s_min": 0.6}}
    rows = MAT.band_repaint(maps, alpha, part_ids, ["p0", "p1"], pos, ok, np.zeros((s, s), bool), [cfg], tx_namespace())
    r = rows[0]
    assert r["band_texels"] == 8 * s  # column c is (c + 1) mm from the neck: columns 0..7 (<= 8.5 mm)
    assert r["band_share_outside_keep_hsv"]["before"] > 0.6 and r["band_share_outside_keep_hsv"]["after"] == 0.0
    assert np.allclose(maps["BC"][:, :6], red, atol=1e-5)  # the smear is red now
    assert np.array_equal(maps["BC"][:, 8:], bc[:, 8:])  # ring and the rest of the cloak untouched
    assert np.array_equal(maps["BC"][part_ids == 1], bc[part_ids == 1])  # the neck untouched
    assert np.array_equal(maps["RM"], np.zeros((s, s, 3), np.float32))  # keys default BC only
    # exclusion box over the lower half: those band texels keep the smear
    maps2 = {"BC": bc.copy(), "RM": maps["RM"].copy(), "AO": maps["AO"].copy()}
    cfg2 = dict(cfg, exclude_boxes_m=[{"min_m": [-1, -1, -1], "max_m": [1, 1, 0.0315]}])
    rows2 = MAT.band_repaint(maps2, alpha, part_ids, ["p0", "p1"], pos, ok, np.zeros((s, s), bool), [cfg2], tx_namespace())
    assert rows2[0]["band_texels"] == 8 * 32
    assert np.array_equal(maps2["BC"][:32, :6], bc[:32, :6]) and np.allclose(maps2["BC"][32:, :6], red, atol=1e-5)


# ------------------------------------------------------------------ look-dev: metal F0 from the concept
def test_colour_of_luma_hits_the_target():
    for hue, sat, y in ((30.9, 0.574, 0.12613), (210.0, 0.2, 0.3), (5.0, 0.7, 0.02)):
        rgb, v, ok = LD.colour_of_luma(hue, sat, y)
        assert ok and float(LD.luma(rgb)) == pytest.approx(y, abs=1e-6)
        h, s_, v8 = TX.rgb_to_hsv(LD.srgb(rgb)[None])
        assert float(h[0]) == pytest.approx(hue, abs=1e-6) and float(s_[0]) == pytest.approx(sat, abs=1e-6)
    _rgb, v, ok = LD.colour_of_luma(30.0, 0.9, 0.95)  # unreachable: the brightest colour of that hue / saturation
    assert not ok and v == 1.0


def presets():
    return LD.ue_inputs(REPO).load_presets()


def test_metal_f0_from_concept(tmp_path):
    rep = {"zones": {"bronze": {"concept": {"hue_deg": 30.9, "sat": 0.574, "luma_Y_linear": 0.1136}},
                     "skin": {"concept": {"hue_deg": 26.3, "sat": 0.484, "luma_Y_linear": 0.2807}}}}
    (tmp_path / "measure-report.json").write_text(json.dumps(rep), encoding="utf-8")
    ld = {"metal_f0": {"concept_report": "measure-report.json", "anchor_class": "skin",
                       "classes": {"bronze": {"worn": {"y_ratio": 2.5}}}}}
    assert LD.metal_f0_problems(ld, presets()) == []
    area = {"bronze": {"bc_linear_median": [0.9216, 0.5776, 0.2582]}, "skin": {"bc_linear_median": [0.6105, 0.2462, 0.0802]}}
    ov = {"bronze": {"bc": [0.9216, 0.5776, 0.2582]}, "skin": {"bc": [0.6105, 0.2462, 0.0802]}}
    out = LD.metal_f0(ld, tmp_path, area, ov)
    row = out["classes"]["bronze"]
    y_skin = float(LD.luma(np.array([0.6105, 0.2462, 0.0802])))
    assert row["target"]["Y"] == pytest.approx(0.1136 / 0.2807 * y_skin, abs=1e-5)  # 0.126 (pilot UE r3 by hand: 0.104)
    assert float(LD.luma(np.array(ov["bronze"]["bc"]))) == pytest.approx(row["target"]["Y"], abs=2e-4)
    assert row["replaced_bc_Y"] == pytest.approx(0.6277, abs=1e-3)  # the preset-derived F0 of the look-dev run (F138)
    assert float(LD.luma(np.array(ov["bronze"]["wornBC"]))) == pytest.approx(2.5 * row["target"]["Y"], abs=5e-4)
    assert ov["skin"]["bc"] == [0.6105, 0.2462, 0.0802]  # the anchor is read, not written
    assert out["concept_report"]["sha256"] and math.isclose(row["concept"]["hue_deg"], 30.9)


@pytest.mark.parametrize("cfg, message", [
    ({"concept_report": "", "anchor_class": "skin", "classes": {"bronze": {}}}, "concept_report"),
    ({"concept_report": "x", "anchor_class": "bronze", "classes": {"bronze": {}}}, "anchor_class must be a dielectric"),
    ({"concept_report": "x", "anchor_class": "skin", "classes": {"skin": {}}}, "not a metal class"),
    ({"concept_report": "x", "anchor_class": "skin", "classes": {"bronze": {"y_scale": 0}}}, "y_scale"),
    ({"concept_report": "x", "anchor_class": "skin", "classes": {"bronze": {"worn": {}}}}, "worn.y_ratio"),
    ({"concept_report": "x", "anchor_class": "skin", "classes": {"bronze": {"tint": 1}}}, "unknown key tint"),
])
def test_metal_f0_invalid(cfg, message):
    problems = LD.metal_f0_problems({"metal_f0": cfg}, presets())
    assert any(message in s for s in problems), problems


def test_metal_f0_conflicts_with_lut_overrides():
    ld = {"metal_f0": {"concept_report": "x", "anchor_class": "skin", "classes": {"bronze": {}}},
          "lut_overrides": {"bronze": {"bc": [0.2, 0.1, 0.03]}}}
    assert any("both set the bc" in s for s in LD.metal_f0_problems(ld, presets()))
    assert LD.metal_f0_problems({}, presets()) == []


# ------------------------------------------------------------------ Blender: vertex mask through the FBX
TOY = r'''
import json, sys
from pathlib import Path
import bmesh, bpy
import numpy as np
args = sys.argv[sys.argv.index("--") + 1:]
sys.path.insert(0, args[0])
from h2_bake import base_ops as B
from h2_bake import st_uv
out, fbx = Path(args[1]), Path(args[2])
bpy.ops.wm.read_factory_settings(use_empty=True)
bm = bmesh.new()
# two tiers: lower drum r 0.15 (z 0-0.03), step, upper drum r 0.11 (z 0.03-0.06)
bmesh.ops.create_cone(bm, cap_ends=True, segments=24, radius1=0.15, radius2=0.15, depth=0.03,
                      matrix=__import__("mathutils").Matrix.Translation((0, 0, 0.015)))
bmesh.ops.create_cone(bm, cap_ends=True, segments=24, radius1=0.11, radius2=0.11, depth=0.03,
                      matrix=__import__("mathutils").Matrix.Translation((0, 0, 0.045)))
bm.normal_update()
fz = np.array([f.calc_center_median().z for f in bm.faces])
fnz = np.array([f.normal.z for f in bm.faces])
band = B.height_band_faces(fz, fnz, [0.0, 0.025])
me = bpy.data.meshes.new("SM_Toy_Base")
bm.to_mesh(me)
bm.free()
obj = bpy.data.objects.new("SM_Toy_Base", me)
bpy.context.scene.collection.objects.link(obj)
rep = st_uv.write_base_mask(obj, band, [0.0, 0.025])
bpy.ops.object.select_all(action="DESELECT")
obj.select_set(True)
bpy.context.view_layer.objects.active = obj
bpy.ops.export_scene.fbx(filepath=str(fbx), use_selection=True, colors_type="SRGB", use_custom_props=False)
bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.fbx(filepath=str(fbx))
o = next(x for x in bpy.data.objects if x.type == "MESH")
m = o.data
attr = m.color_attributes[0]
cols = np.empty(len(attr.data) * 4, np.float32)
attr.data.foreach_get("color", cols)
cols = cols.reshape(-1, 4)
face_r = []
for p in m.polygons:
    face_r.append([float(cols[li][0]) for li in p.loop_indices] if attr.domain == "CORNER" else None)
face_z = [p.center.z for p in m.polygons]
face_nz = [p.normal.z for p in m.polygons]
out.write_text(json.dumps({"report": rep, "domain": attr.domain, "name": attr.name, "face_r": face_r, "face_z": face_z,
                           "face_nz": face_nz, "gb": [float(cols[:, 1].max()), float(cols[:, 2].max())]}), encoding="utf-8")
'''


@pytest.mark.skipif(not Path(BLENDER).is_file(), reason="Blender 5.2 not installed")
def test_vertex_mask_survives_fbx(tmp_path):
    script = tmp_path / "toy.py"
    script.write_text(TOY, encoding="utf-8")
    out = tmp_path / "toy.json"
    r = subprocess.run([BLENDER, "-b", "--factory-startup", "--python-exit-code", "1", "--python", str(script), "--",
                        str(PKG.parent), str(out), str(tmp_path / "toy.fbx")], capture_output=True, text=True, timeout=600,
                       creationflags=FLAGS)
    assert r.returncode == 0, r.stdout[-3000:] + r.stderr[-3000:]
    d = json.loads(out.read_text(encoding="utf-8"))
    assert d["report"]["faces"] == 24 and d["report"]["vertex_mask"]["attribute"] == "UM_Mask"  # the lower drum wall
    assert d["domain"] == "CORNER" and d["gb"] == [0.0, 0.0]
    for rs, z, nz in zip(d["face_r"], d["face_z"], d["face_nz"]):
        want = 1.0 if (z <= 0.025 and nz >= -0.5) else 0.0
        assert all(abs(v - want) < 1e-6 for v in rs), (z, nz, rs)
