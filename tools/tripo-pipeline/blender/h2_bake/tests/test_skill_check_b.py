"""Skill check Beowulf 2026-10-14, package B (h2-bake 0.9.0): docs/art-pipeline/evidence/skill-check-beowulf-2026-10-14/
NOTES.md C18-C24, C36, C49. New rules apply to profile_version >= 2 (the source H2 profile of a look-dev run); the MVP and
pilot profiles (version 1) keep their bytes (the Medusa byte tests of test_cloth_shell.py, test_pilot_stage3_fixes.py and
test_w1d_reuse_determinism.py run the same code paths).

  C18  look-dev metal_f0 "self": F0 from the concept zones of this run's ld_measure; determinism rule lut_f0_self
  C19  ta_report gold_unchanged_by_dye: views without trim pixels "not measured", no trim class "not applicable"
  C20  ld_measure exposure largest_class (v2 default)
  C21  seams loop_cover per_vertex (v2 default)
  C22  close check caps_not_seen_only_from_behind (v2)
  C24  --reuse-from with a stage subset, work/smoke never carried, band-only reuse of the uv stage (v2)
  C36  cloth_shell face tag (v2) and the FBX-side shell detection of the acceptance capture
  C49  F139 cloth start values in the look-dev LUT (v2 default)

Plain Python, except the Blender toy tests (skipped without Blender 5.2).
Run: python -m pytest tools/tripo-pipeline/blender/h2_bake/tests -q -p no:cacheprovider"""

import copy
import json
import os
import subprocess
import sys
from pathlib import Path

import numpy as np
import pytest

HERE = Path(__file__).resolve().parent
PKG = HERE.parent
REPO = HERE.parents[4]
ACCEPT = REPO / "tools" / "art" / "acceptance"
sys.path.insert(0, str(PKG.parent))
sys.path.insert(0, str(HERE))

from h2_bake import determinism as DET  # noqa: E402
from h2_bake import lookdev as LD  # noqa: E402
from h2_bake import lookdev_accent as ACC  # noqa: E402
from h2_bake import profile as PR  # noqa: E402
from h2_bake import reuse as RU  # noqa: E402
from test_w1d_reuse_determinism import MEDUSA, fake_source, make_run, medusa, write  # noqa: E402

BLENDER = os.environ.get("H2_BAKE_BLENDER", "C:/Program Files/Blender Foundation/Blender 5.2/blender.exe")
FLAGS = getattr(subprocess, "CREATE_NO_WINDOW", 0)
NEED_BLENDER = pytest.mark.skipif(not Path(BLENDER).is_file(), reason="Blender 5.2 not installed")
BEOWULF_T4 = REPO / "art/pipeline-candidates/ASSET-BEOWULF-001/build-profiles/beowulf-h2-bake-h2-t4.json"


def run_blender(script_text, args, tmp_path, timeout=600):
    script = tmp_path / "script.py"
    script.write_text(script_text, encoding="utf-8")
    r = subprocess.run([BLENDER, "-b", "--factory-startup", "--python-exit-code", "1", "--python", str(script), "--"]
                       + [str(a) for a in args], capture_output=True, text=True, timeout=timeout, creationflags=FLAGS)
    assert r.returncode == 0, r.stdout[-3000:] + r.stderr[-3000:]
    return r


def band_change(p):
    q = copy.deepcopy(p)
    q["textures"]["team_mask"]["base_band"]["height_m"] = [0.003, 0.029]
    return q


# ------------------------------------------------------------------ C24: band-only reuse, stage subset, work/smoke
def test_band_only_plan_keeps_bake_and_aux(tmp_path):
    p = medusa()
    src = fake_source(tmp_path / "src", p, MEDUSA)
    q = band_change(p)
    plan = RU.plan(src, q, REPO, None, PR.load, band_only=True)
    row = {r["stage"]: r for r in plan["stages"]}
    assert row["uv"]["action"] == "band" and plan["band"] == ["uv"]
    assert plan["reused"] == ["prepare", "retopo", "close", "bake", "aux"]
    assert plan["first_recomputed"] == "textures" and "uv" not in plan["recomputed"]
    # the ledger fingerprint of the band stage: the old one with the new band sub-key (no stale entry at the manifest)
    fp = row["uv"]["old_fingerprint"]
    assert RU.differences(RU.fingerprint("uv", q, REPO, None), fp) == ([], [])
    # profile_version 1 (band_only False, the driver's default for the MVP and the pilot): recompute from uv as before
    plan1 = RU.plan(src, q, REPO, None, PR.load)
    assert plan1["first_recomputed"] == "uv" and plan1["band"] == []


def test_band_only_needs_the_band_to_be_the_only_change(tmp_path):
    p = medusa()
    src = fake_source(tmp_path / "src", p, MEDUSA)
    q = band_change(p)
    q["uv"]["min_gap_px"] = q["uv"]["min_gap_px"] + 1  # another uv key: the whole uv stage again
    assert RU.plan(src, q, REPO, None, PR.load, band_only=True)["first_recomputed"] == "uv"
    led = RU.load_ledger(src)  # code drift of st_uv.py: strict unless allowed (then listed)
    led["stages"]["uv"]["fingerprint"]["code"][RU.PKG + "st_uv.py"] = "0" * 64
    RU.save_ledger(src, led)
    q = band_change(p)
    assert RU.plan(src, q, REPO, None, PR.load, band_only=True)["first_recomputed"] == "uv"
    plan = RU.plan(src, q, REPO, None, PR.load, allow_code_drift=True, band_only=True)
    assert plan["band"] == ["uv"] and plan["code_drift"]["uv"] == ["st_uv.py"]


def test_band_apply_carries_the_uv_files_and_private_copies(tmp_path):
    p = medusa()
    src = fake_source(tmp_path / "src", p, MEDUSA)
    write(src / "work" / "uv" / "base_band.npy", b"old band")
    write(src / "work" / "smoke" / "validation" / "x.json", {"clip": 1})  # stage-3 smoke run of the old run
    plan = RU.plan(src, band_change(p), REPO, None, PR.load, band_only=True)
    new = tmp_path / "new"
    got = RU.apply(plan, new, REPO)
    assert (new / "work" / "lp_uv.blend").is_file() and (new / "reports" / "uv-report.json").is_file()
    assert not (new / "work" / "smoke").exists() and "work/smoke/validation/x.json" not in got["unowned"]
    band = new / "work" / "uv" / "base_band.npy"
    if got["link"]:
        assert band.stat().st_nlink == 2
        assert RU.private_copies(new, RU.BAND_FILES) == ["work/uv/base_band.npy"]
        assert band.stat().st_nlink == 1 and band.read_bytes() == b"old band"
        band.write_bytes(b"new band")  # the old run keeps its bytes
        assert (src / "work" / "uv" / "base_band.npy").read_bytes() == b"old band"
    assert RU.private_copies(new, RU.BAND_FILES) == []


@pytest.mark.parametrize("rel, stage", [("work/smoke/AM_X_Idle.fbx", None), ("work/smoke/validation/a.json", None),
                                        ("logs/uv-band.log", "uv"), ("work/params/uv-band.json", None),
                                        ("work/reuse-plan.json", None)])
def test_owner_of_the_new_paths(rel, stage):
    assert RU.owner(rel) == stage


def test_driver_reuse_with_a_stage_subset(tmp_path):
    p = medusa()
    src = fake_source(tmp_path / "src", p, MEDUSA)
    cmd = [sys.executable, str(PKG / "run_h2_bake.py"), "--profile", str(MEDUSA), "--reuse-from", str(src),
           "--blender", sys.executable]
    # everything reusable: --stages compose is carried, nothing runs
    r = subprocess.run(cmd + ["--run-dir", str(tmp_path / "a"), "--stages", "compose"], capture_output=True, text=True,
                       timeout=300, creationflags=FLAGS)
    assert r.returncode == 0, r.stdout[-3000:] + r.stderr[-3000:]
    assert (tmp_path / "a" / "reports" / "compose-report.json").is_file()
    assert not (tmp_path / "a" / "reports" / "run-manifest.json").exists()  # manifest not requested
    # a later stage than the first one to recompute is refused before anything is carried
    q = copy.deepcopy(p)
    q["seams"]["max_new_blob_px"] = 9
    qp = write(tmp_path / "q.json", json.dumps(q))
    r = subprocess.run([sys.executable, str(PKG / "run_h2_bake.py"), "--profile", str(qp), "--reuse-from", str(src),
                        "--blender", sys.executable, "--run-dir", str(tmp_path / "b"), "--stages", "compose"],
                       capture_output=True, text=True, timeout=300, creationflags=FLAGS)
    assert r.returncode != 0 and "first stage to recompute is seams" in (r.stdout + r.stderr)
    assert not (tmp_path / "b").exists() or not any(x.is_file() for x in (tmp_path / "b").rglob("*"))


# ------------------------------------------------------------------ C18: metal_f0 "self"
def presets():
    return LD.ue_inputs(REPO).load_presets()


def test_metal_f0_self_validation():
    cfg = {"anchor_class": "skin", "classes": {"bronze": {}}}
    assert any("concept_report" in m for m in LD.metal_f0_problems({"metal_f0": cfg}, presets()))  # v1: required
    assert LD.metal_f0_problems({"metal_f0": cfg}, presets(), v2=True) == []  # v2: absent = self
    assert LD.metal_f0_problems({"metal_f0": dict(cfg, concept_report="self")}, presets()) == []  # explicit, any version
    assert LD.metal_f0_self({"metal_f0": cfg}, True) and not LD.metal_f0_self({"metal_f0": cfg}, False)
    assert not LD.metal_f0_self({"metal_f0": dict(cfg, concept_report="a/measure-report.json")}, True)


def zones_bronze_skin(dy=0.0):
    return {"bronze": {"concept": {"hue_deg": 30.9, "sat": 0.574, "luma_Y_linear": 0.1136 + dy}},
            "skin": {"concept": {"hue_deg": 26.3, "sat": 0.484, "luma_Y_linear": 0.2807}}}


def self_run(root, ld):
    """A look-dev run after ld_maps in self mode: textures/<lut>.overrides.json + ld-maps-report.json (pending)."""
    area = {"bronze": {"bc_linear_median": [0.9216, 0.5776, 0.2582]}, "skin": {"bc_linear_median": [0.6105, 0.2462, 0.0802]}}
    ov = {"bronze": {"bc": [0.9216, 0.5776, 0.2582], "ymedClassHero": 0.6}, "skin": {"bc": [0.6105, 0.2462, 0.0802]}}
    (root / "textures").mkdir(parents=True)
    (root / "work").mkdir()
    UI = LD.ue_inputs(REPO)
    pres = UI.load_presets()
    pending = LD.metal_f0_pending(ld, ov)
    lut, lut_rep, outs = LD.write_lut(root, ld, UI, pres, ov)
    checks = LD.lut_checks(lut, lut_rep, pres, area, pending)
    assert "lut_metal_f0_from_concept" not in checks and checks["lut_metal_f0_plausible"]["passed"]
    write(root / "reports" / "ld-maps-report.json", {"classes": area, "lut": lut_rep, "outputs": dict(outs), "checks": checks,
                                                     "metal_f0": pending, "passed": True})
    return root


SELF_LD = {"lut_name": "T_UM_MatLUT_Test", "lut_hero": "Test", "asset_id": "ASSET-TEST-001",
           "metal_f0": {"concept_report": "self", "anchor_class": "skin", "classes": {"bronze": {"worn": {"y_ratio": 2.5}}}}}


def test_metal_f0_self_applied_by_ld_measure(tmp_path):
    run = self_run(tmp_path / "run", SELF_LD)
    mf = LD.apply_metal_f0_self(run, SELF_LD, REPO, zones_bronze_skin())
    rep = json.loads((run / "reports" / "ld-maps-report.json").read_text(encoding="utf-8"))
    assert rep["passed"] and rep["checks"]["lut_metal_f0_from_concept"]["passed"]
    assert rep["metal_f0"]["concept_source"] == "self" and rep["metal_f0"]["applied_by"] == "ld_measure"
    assert rep["metal_f0"]["concept_report"]["source"] == "self" and rep["metal_f0"]["lut_column"] == {"bronze": 6}
    y_skin = float(LD.luma(np.array([0.6105, 0.2462, 0.0802])))
    assert mf["classes"]["bronze"]["target"]["Y"] == pytest.approx(0.1136 / 0.2807 * y_skin, abs=1e-5)  # as two runs
    dds = run / "textures" / "T_UM_MatLUT_Test.dds"
    assert rep["outputs"]["T_UM_MatLUT_Test.dds"]["sha256"] == LD.sha256(dds)
    lut = LD.read_dds_rgba16f(dds)
    assert float(LD.luma(lut[0, 6, :3].astype(np.float64))) == pytest.approx(mf["classes"]["bronze"]["target"]["Y"], abs=2e-3)
    first = dds.read_bytes()
    LD.apply_metal_f0_self(run, SELF_LD, REPO, zones_bronze_skin())  # a repeated ld_measure starts from the ld_maps LUT
    assert dds.read_bytes() == first


def test_determinism_lut_f0_self_tolerance(tmp_path):
    runs = {}
    for name, dy in (("a", 0.0), ("b", 0.0004), ("c", 0.02)):
        run = self_run(tmp_path / name, SELF_LD)
        LD.apply_metal_f0_self(run, SELF_LD, REPO, zones_bronze_skin(dy))
        runs[name] = run
    rep = DET.compare(runs["a"], runs["b"], REPO)  # one mask pixel: a small F0 shift
    assert rep["verdict"] == "pass", rep["failures"]
    assert rep["files"]["textures/T_UM_MatLUT_Test.dds"]["rule"] == "lut_f0_self"
    assert rep["files"]["reports/ld-maps-report.json"]["result"] in ("within tolerance", "identical")
    rep = DET.compare(runs["a"], runs["c"], REPO)  # beyond the tolerance
    assert rep["verdict"] == "fail" and "textures/T_UM_MatLUT_Test.dds" in rep["failures"]
    # another LUT cell differs: not covered by the rule
    b = runs["b"] / "textures" / "T_UM_MatLUT_Test.dds"
    raw = bytearray(b.read_bytes())
    raw[148 + (2 * 16 + 3) * 8] ^= 1  # row 2, column 3 (specular of metal_forged)
    b.write_bytes(bytes(raw))
    rep = DET.compare(runs["a"], runs["b"], REPO)
    assert rep["files"]["textures/T_UM_MatLUT_Test.dds"]["ok"] is False
    # without "self" in both runs the DDS is compared byte for byte (exact rule)
    assert DET.rule_for("textures/T_UM_MatLUT_Test.dds")["rule"] == "exact"
    assert DET.rule_for("reports/ld-maps-report.json")["rule"] == "json"


# ------------------------------------------------------------------ C20: exposure largest_class
def test_largest_class_anchor():
    zones = {"wool_coarse": {"pixels_ld": 536117}, "stone_base": {"pixels_ld": 900000}, "metal_forged": {"pixels_ld": 700000},
             "skin": {"pixels_ld": 35108}, "leather_worn": {"pixels_ld": 158076}}
    lib_k = sorted(zones)
    out = LD.largest_class_anchor({"mode": "largest_class"}, zones, lib_k, presets(), {"stone_base"})
    assert out["mode"] == "anchor_class" and out["class"] == "wool_coarse" and out["selected_by"] == "largest_class"
    assert "metal_forged" in out["excluded"] and "stone_base" in out["excluded"]
    out = LD.largest_class_anchor({"mode": "largest_class", "exclude": ["wool_coarse"]}, zones, lib_k, presets(), set())
    assert out["class"] == "stone_base"  # the base only when it is not excluded


def test_base_classes_from_the_source_profile():
    p = json.loads(BEOWULF_T4.read_text(encoding="utf-8"))
    ld = {"classes": {"part_default": {"13": "stone_base", "0": "wool_coarse"}}}
    assert LD.base_classes(ld, p) == {"stone_base"}
    assert LD.base_classes(ld, None) == {"stone_base"}


# ------------------------------------------------------------------ C49: F139 cloth start values
def test_lut_start_values_v2_and_library():
    area = {"wool_coarse": {}, "skin": {}}
    ov = {}
    got = LD.lut_start_values({"lut_overrides": {"wool_coarse": {"specular": 0.2}}}, area, ov, v2=True)
    assert got == {"wool_coarse": {"roughTypical": 0.85, "sheenIntensity": 0.0}}  # the profile's specular wins
    assert ov == {"wool_coarse": {"roughTypical": 0.85, "sheenIntensity": 0.0}}  # linen: not used by the hero
    assert LD.lut_start_values({}, area, {}, v2=False) is None  # v1: the presets as before
    assert LD.lut_start_values({"lut_start_values": "library"}, area, {}, v2=True) is None
    assert LD.lut_start_values({"lut_start_values": "f139"}, {"linen": {}}, {}, v2=False) == {
        "linen": {"roughTypical": 0.85, "sheenIntensity": 0.0, "specular": 0.1}}
    with pytest.raises(ValueError, match="lut_start_values"):
        LD.lut_start_mode({"lut_start_values": "x"})
    # the values build a valid LUT column (apply_overrides knows the fields)
    UI = LD.ue_inputs(REPO)
    cols = UI.class_columns(presets())
    UI.apply_overrides(cols, {"classes": {"linen": LD.LUT_START_F139["linen"]}}, presets())


def test_source_is_v2(tmp_path):
    assert LD.source_is_v2({"source": {"profile": str(BEOWULF_T4)}}, REPO)
    assert not LD.source_is_v2({"source": {"profile": str(MEDUSA)}}, REPO)
    assert not LD.source_is_v2({}, REPO)


# ------------------------------------------------------------------ C19: gold_unchanged_by_dye
def test_gold_check_not_measured_and_not_applicable():
    gd = {"k2_5x_az0": {"ld_p1": 0.4, "ld_p2": 0.6}, "k2_1p6_az180": {"ld_p1": None, "ld_p2": None}}
    checks = {}
    ACC.gold_check(checks, gd, "gold_antique", 2.0)
    c = checks["gold_unchanged_by_dye"]
    assert c["passed"] and c["measured"]["not_measured_no_trim_px"]["views"] == ["k2_1p6_az180"]
    ACC.gold_check(checks, {"v": {"ld_p1": 3.0, "ld_p2": 0.1}}, "gold_antique", 2.0)
    assert not checks["gold_unchanged_by_dye"]["passed"]
    ACC.gold_check(checks, {"v": {"ld_p1": None, "ld_p2": None}}, None, 2.0)  # no trim class
    assert checks["gold_unchanged_by_dye"]["passed"] and "not_applicable" in checks["gold_unchanged_by_dye"]["measured"]
    full = {"a": {"ld_p1": 0.4, "ld_p2": 0.6}, "b": {"ld_p1": 1.0, "ld_p2": 0.2}}  # Medusa: every view measured
    ACC.gold_check(checks, full, "gold_antique", 2.0)
    assert checks["gold_unchanged_by_dye"] == {
        "passed": True, "measured": full, "note": "",
        "expected": "median dE of the gold pixels (meander, belt) with P1 / P2 against no dye <= 2.0"}  # the old bytes


# ------------------------------------------------------------------ Blender: C21, C22, C24 band, C36
TOY_STAGES = r'''
import json, sys
from pathlib import Path
import bmesh, bpy
import numpy as np
from mathutils import Matrix, Vector
from mathutils.bvhtree import BVHTree
args = sys.argv[sys.argv.index("--") + 1:]
sys.path.insert(0, args[0])
sys.path.insert(0, args[1])
out = Path(args[2])
profiles = json.loads(Path(args[3]).read_text(encoding="utf-8"))
from h2_bake import st_close, st_rig, st_seams, st_uv
from h2_bake import base_ops as B
from _framing import shell_copy_mask, zero_uv_area_mask
res = {}
# C21: nearest other part per vertex; loop_cover_mode by profile version
plane = lambda z: BVHTree.FromPolygons([Vector((-1, -1, z)), Vector((1, -1, z)), Vector((1, 1, z)), Vector((-1, 1, z))], [[0, 1, 2, 3]])
surf = {0: plane(0.0), 1: plane(0.010), 2: plane(-0.004)}
d, lab = st_seams.nearest_other(surf, 0, np.array([[0, 0, 0.009], [0, 0, -0.003], [0, 0, 0.004]]))
res["nearest"] = [[round(float(x), 6) for x in d], [int(x) for x in lab]]
res["cover_mode"] = {k: st_seams.loop_cover_mode(p, p.get("seams", {})) for k, p in profiles.items()}
try:
    st_seams.loop_cover_mode(profiles["v2"], {"loop_cover": "x"})
    res["cover_bad"] = None
except ValueError as e:
    res["cover_bad"] = str(e)
# C22: caps seen only from behind (Beowulf run 1: neck_top 1163 px from behind, 0 from the front)
caps = [{"name": "neck_top", "rest_visibility": {"cap_backside_px": 1163, "fills_gap_px": 0, "covers_front_px": 0}},
        {"name": "shoulder_top_r", "rest_visibility": {"cap_backside_px": 21, "fills_gap_px": 42, "covers_front_px": 4}},
        {"name": "head_nape", "rest_visibility": {"cap_backside_px": 31, "fills_gap_px": 104, "covers_front_px": 4}}]
res["behind"] = st_close.backside_only_caps(caps, {})
res["behind_t4"] = st_close.backside_only_caps(caps[1:], {})
# C36: shell tag on a toy sheet + the FBX-side detection on its triangles
bpy.ops.wm.read_factory_settings(use_empty=True)
bm = bmesh.new()
nx, nz = 6, 4
vs = {}
for i in range(nx + 1):
    a = np.pi * i / nx
    for k in range(nz + 1):
        vs[i, k] = bm.verts.new((float(np.cos(a)) * 0.05, float(np.sin(a)) * 0.05, 0.02 * k))
uv = bm.loops.layers.uv.new("UVMap")
for i in range(nx):
    for k in range(nz):  # triangles (the figure is all-triangles), UV counter-clockwise like an unwrap
        for tri in ([vs[i, k], vs[i + 1, k], vs[i + 1, k + 1]], [vs[i, k], vs[i + 1, k + 1], vs[i, k + 1]]):
            f = bm.faces.new(tri)
            for l in f.loops:
                ii, kk = next(key for key, v in vs.items() if v == l.vert)
                l[uv].uv = (ii / nx, kk / nz)
bm.normal_update()
me = bpy.data.meshes.new("toy")
bm.to_mesh(me)
bm.free()
obj = bpy.data.objects.new("LP_toy", me)
bpy.context.scene.collection.objects.link(obj)
rep = st_rig.add_cloth_shell(obj, 0.0003, tag_attr=st_rig.SHELL_ATTR)
me = obj.data
tag = [0] * len(me.polygons)
me.attributes[st_rig.SHELL_ATTR].data.foreach_get("value", tag)
me.calc_loop_triangles()
co = np.array([v.co[:] for v in me.vertices])
uvs = np.array([d.uv[:] for d in me.uv_layers[0].data])
tl = np.array([t.loops[:] for t in me.loop_triangles])
tp = np.array([t.polygon_index for t in me.loop_triangles])
lv = np.array([l.vertex_index for l in me.loops])
m = shell_copy_mask(uvs[tl], co[lv[tl]])
z = zero_uv_area_mask(uvs[tl])
res["shell"] = {"report": rep, "tag_counts": {str(t): tag.count(t) for t in sorted(set(tag))},
                "detected_copy_polys": sorted(set(int(x) for x in tp[m])),
                "tagged_copy_polys": [i for i, t in enumerate(tag) if t == 1],
                "zero_uv_polys": sorted(set(int(x) for x in tp[z])), "tagged_bridge_polys": [i for i, t in enumerate(tag) if t == 2]}
# C24: band triangles of a two-tier toy base (UV from the cone primitive)
bpy.ops.wm.read_factory_settings(use_empty=True)
bm = bmesh.new()
bm.loops.layers.uv.new("UVMap")
bmesh.ops.create_cone(bm, cap_ends=True, segments=24, radius1=0.15, radius2=0.15, depth=0.03, calc_uvs=True,
                      matrix=Matrix.Translation((0, 0, 0.015)))
bmesh.ops.create_cone(bm, cap_ends=True, segments=24, radius1=0.11, radius2=0.11, depth=0.03, calc_uvs=True,
                      matrix=Matrix.Translation((0, 0, 0.045)))
bm.normal_update()
uvl = bm.loops.layers.uv.active
faces_h, tris_h = st_uv.band_triangles(bm, uvl, 64, {"normal_z_abs_max": 0.35}, [0.0, 0.025])
faces_n, tris_n = st_uv.band_triangles(bm, uvl, 64, {"normal_z_abs_max": 0.35}, None)
res["band"] = {"height_faces": int(faces_h.sum()), "height_tris": len(tris_h), "normal_faces": faces_n,
               "normal_tris": len(tris_n), "tri_per_side_face": 2}
out.write_text(json.dumps(res), encoding="utf-8")
'''


@NEED_BLENDER
def test_blender_toy_stage_rules(tmp_path):
    v1 = medusa()
    v2 = json.loads(BEOWULF_T4.read_text(encoding="utf-8"))
    pfile = write(tmp_path / "profiles.json", json.dumps({"v1": v1, "v2": v2, "v2_loop": dict(v2, seams=dict(
        v2["seams"], loop_cover="per_loop"))}))
    out = tmp_path / "out.json"
    run_blender(TOY_STAGES, [PKG.parent, ACCEPT, out, pfile], tmp_path)
    r = json.loads(out.read_text(encoding="utf-8"))
    # C21: each point against its nearest other surface
    assert r["nearest"] == [[0.001, 0.001, 0.006], [1, 2, 1]]
    assert r["cover_mode"] == {"v1": "per_loop", "v2": "per_vertex", "v2_loop": "per_loop"}
    assert "loop_cover" in r["cover_bad"]
    # C22: neck_top flagged, the caps of the accepted t4 bake pass
    assert r["behind"]["passed"] is False and r["behind"]["measured"]["seen_only_from_behind"] == ["neck_top"]
    assert r["behind_t4"]["passed"] is True
    # C36: tags 1 on the 48 inner copies, 2 on two bridge triangles per rim edge (2 x 6 + 2 x 4 rim edges)
    sh = r["shell"]
    assert sh["report"]["rim_edges_bridged"] == 20
    assert sh["tag_counts"]["1"] == 48 and sh["tag_counts"]["2"] == 40 and sh["tag_counts"]["0"] == 48
    assert sh["detected_copy_polys"] == sh["tagged_copy_polys"]  # the FBX-side detection finds exactly the copies
    assert sh["zero_uv_polys"] == sh["tagged_bridge_polys"]
    # C24: the band step's triangles (2 per lower drum side quad: the toy cone sides are quads)
    assert r["band"]["height_faces"] == 24 and r["band"]["height_tris"] == 48
    assert r["band"]["normal_faces"] is None and r["band"]["normal_tris"] == 2 * 48  # both drum walls (|n_z| <= 0.35)


# ------------------------------------------------------------------ determinism: make_run still passes (no self block)
def test_plain_runs_keep_the_old_rules(tmp_path):
    a, b = make_run(tmp_path / "a"), make_run(tmp_path / "b")
    write(a / "reports" / "ld-maps-report.json", {"metal_f0": {"concept_report": {"path": "x"}}, "passed": True})
    write(b / "reports" / "ld-maps-report.json", {"metal_f0": {"concept_report": {"path": "x"}}, "passed": True})
    rep = DET.compare(a, b, REPO)
    assert rep["verdict"] == "pass" and rep["files"]["reports/ld-maps-report.json"]["rule"] == "json"
