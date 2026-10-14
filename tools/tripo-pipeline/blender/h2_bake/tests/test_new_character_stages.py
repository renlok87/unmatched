"""h2-bake 0.6.1: the preview / compose / look-dev / TeamAccent stages for a NEW character (no earlier game candidate, a
concept of another size and aspect than Medusa's 1021 x 1540, a costume without a trim band or without a strap).

Plain Python except test_preview_and_compose_blender_without_previous_candidate (Blender headless; skipped when the
Blender executable is not there).
Run: python -m pytest tools/tripo-pipeline/blender/h2_bake/tests -q"""

import copy
import importlib.util
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

from h2_bake import framing as FR  # noqa: E402
from h2_bake import profile as PR  # noqa: E402

MEDUSA = REPO / "art/pipeline-candidates/ASSET-MEDUSA-001/build-profiles/medusa-h2-bake-h2.json"
BLENDER = os.environ.get("H2_BAKE_BLENDER", "C:/Program Files/Blender Foundation/Blender 5.2/blender.exe")


def load_local(name):
    spec = importlib.util.spec_from_file_location("h2t_" + name, PKG / (name + ".py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def checks_report(path, sizes, masks):
    """A minimal unmatched.concept-checks/1 report as check_concept_views.py writes it."""
    rep = {"schema": "unmatched.concept-checks/1",
           "measurements": {v: {"size": list(sizes[v]), "mask": dict(masks[v])} for v in sizes}}
    path.write_text(json.dumps(rep), encoding="utf-8")
    return path


# ------------------------------------------------------------------ framing
def old_medusa_camera(figure_top_m):
    """The arithmetic of st_preview / st_lookdev before 0.6.1 (hard-coded Medusa frame)."""
    W, H = 1021, 1540
    top, bottom, base_x = 0.02, 0.968, 0.45
    height_m = float(figure_top_m) / (bottom - top)
    zc = float(figure_top_m) - (0.5 - top) * height_m
    shift = (0.5 - base_x) * height_m * W / H
    return height_m, {"front": ((shift, -3.0, zc), (0, -1, 0)), "side": ((3.0, shift, zc), (1, 0, 0)),
                      "back": ((-shift, 3.0, zc), (0, 1, 0))}


def test_default_frame_is_the_old_medusa_arithmetic():
    cams, side, source = FR.cameras(None, 0.55)
    height_m, old = old_medusa_camera(0.55)
    assert side == "left" and source.startswith("default")
    for v in FR.VIEWS:
        assert cams[v]["px"] == [1021, 1540]
        assert cams[v]["ortho_scale"] == height_m  # exact: the same float operations
        assert cams[v]["loc"] == old[v][0] and cams[v]["dir"] == old[v][1]


def test_face_part_and_uv_reference_follow_the_profile():
    """Achilles pilot 2026-10-13: the face part comes from dense_regions "face" (Achilles: head = part 5, part 1 = base),
    the uv density reference from uv.density_reference_part; Medusa keeps the old hard-coded 1 and tripo_part_0."""
    medusa = PR.load(MEDUSA)
    assert PR.face_part_key(medusa) == 1
    assert PR.uv_density_reference_part(medusa) == "tripo_part_0"
    hero = copy.deepcopy(medusa)
    for region in hero["retopo"]["dense_regions"]:
        if region["name"] == "face":
            region["part"] = "tripo_part_5"
    hero["uv"]["density_reference_part"] = "tripo_part_7"
    assert PR.face_part_key(hero) == 5
    assert PR.uv_density_reference_part(hero) == "tripo_part_7"
    hero["retopo"]["dense_regions"] = []
    assert PR.face_part_key(hero) == 1


def test_frame_from_checks_report_3x4(tmp_path):
    sizes = {"front": (1152, 1536), "side": (1152, 1536), "back": (1152, 1536)}
    masks = {"front": {"top_pct": 4.0, "bottom_pct": 93.0, "base_center_x_pct": 50.0},
             "side": {"top_pct": 4.4, "bottom_pct": 92.6, "base_center_x_pct": 49.0},
             "back": {"top_pct": 4.1, "bottom_pct": 93.1, "base_center_x_pct": 51.0}}
    rep = checks_report(tmp_path / "checks-report.json", sizes, masks)
    cams, side, source = FR.cameras({"checks_report": str(rep), "side": "right"}, 0.5)
    assert side == "right" and "checks_report" in source
    for v in FR.VIEWS:
        c = cams[v]
        assert c["px"] == [1152, 1536]
        span = masks[v]["bottom_pct"] - masks[v]["top_pct"]
        assert c["ortho_scale"] == pytest.approx(0.5 / (span / 100.0))
        # the model origin (base centre) lands on the measured base centre of the concept view
        assert FR.project_base_centre(c, v) == pytest.approx(masks[v]["base_center_x_pct"] / 100.0)
        # base bottom (z = 0) and figure top on the measured rows
        top_z = c["centre_z_m"] + c["ortho_scale"] / 2
        assert (top_z - 0.5) / c["ortho_scale"] == pytest.approx(masks[v]["top_pct"] / 100.0)
        assert (top_z - 0.0) / c["ortho_scale"] == pytest.approx(masks[v]["bottom_pct"] / 100.0)
    # SIDE_VIEW right: the camera looks at the figure's right side (-X), left: +X
    assert cams["side"]["dir"] == (-1, 0, 0) and cams["side"]["loc"][0] < 0
    left, _s, _src = FR.cameras({"checks_report": str(rep), "side": "left"}, 0.5)
    assert left["side"]["dir"] == (1, 0, 0) and left["side"]["loc"][0] > 0
    assert FR.project_base_centre(left["side"], "side") == pytest.approx(0.49)


def test_frame_explicit_and_errors(tmp_path):
    frames, side, _src = FR.resolve({"px": [900, 1200], "top": 0.05, "bottom": 0.95, "base_x": 0.5,
                                     "views": {"side": {"base_x": 0.48}}})
    assert frames["front"]["px"] == [900, 1200] and frames["side"]["base_x"] == 0.48 and side == "left"
    with pytest.raises(FR.FrameError):
        FR.resolve({"side": "up"})
    with pytest.raises(FR.FrameError):
        FR.resolve({"top": 0.9, "bottom": 0.1})
    rep = checks_report(tmp_path / "c.json", {"front": (10, 10)}, {"front": {"top_pct": 1, "bottom_pct": 99,
                                                                             "base_center_x_pct": 50}})
    with pytest.raises(FR.FrameError, match="no measurements for view side"):
        FR.resolve({"checks_report": str(rep)})


# ------------------------------------------------------------------ look-dev measure: the concept must fit the frame
def test_measure_refuses_a_squashed_concept(tmp_path):
    lookdev = load_local("lookdev")
    c34 = tmp_path / "c34.png"
    Image.new("RGB", (1152, 1536), (60, 60, 60)).save(c34)
    with pytest.raises(ValueError, match="frame"):
        lookdev.concept_on_class_pass(c34, 1021, 1540)  # 3:4 concept on the default Medusa frame
    arr, info = lookdev.concept_on_class_pass(c34, 1152, 1536)
    assert arr.shape == (1536, 1152, 3) and info["aspect_rel_diff"] == 0.0
    medusa_side = tmp_path / "ms.png"
    Image.new("RGB", (1022, 1539)).save(medusa_side)
    _arr, info = lookdev.concept_on_class_pass(medusa_side, 1021, 1540)  # Medusa side view: within 1 %
    assert info["aspect_rel_diff"] < lookdev.CONCEPT_ASPECT_TOL


# ------------------------------------------------------------------ TeamAccent without a trim band / without a strap
CIDX = {"linen": 1, "gold_antique": 4, "leather_smooth": 6, "steel": 9, "stone_base": 14}


def synthetic_figure(gold=True, leather=True):
    """128 x 128 texels on a vertical plane (x = column, z = row): cloth (linen) everywhere, a gold band row strip low
    on the skirt, a leather strap high on the chest; part 0 = clothes, part 2 = base (last rows)."""
    n = 128
    rows, cols = np.mgrid[0:n, 0:n]
    pos = np.stack([cols * 0.002, np.zeros_like(cols, float), (n - rows) * 0.004], -1).astype(np.float64)
    lab = np.full((n, n), CIDX["linen"], np.int16)
    pid = np.zeros((n, n), np.int16)
    if gold:
        lab[100:104, :] = CIDX["gold_antique"]  # z ~ 0.1 m
    if leather:
        lab[20:44, 40:70] = CIDX["leather_smooth"]  # z ~ 0.35-0.43 m, 30 x 24 texels
    pid[120:, :] = 2
    lab[120:, :] = CIDX["stone_base"]
    cov = np.ones((n, n), bool)
    return lab, pid, pos, cov


def ta_cfg(hem=True, ribbon=True):
    t = {"blur_sigma_px": 1.0, "figure_exclude_parts": [2]}
    if hem:
        t["hem"] = {"parts": [0], "cloth_class": "linen", "band_class": "gold_antique", "band_z_max_m": 0.3,
                    "width_m": 0.01, "feather_m": 0.002, "normal_agree_min": 0.3, "search_max_m": 0.02}
    if ribbon:
        t["ribbon"] = {"parts": [0], "class": "leather_smooth", "z_min_m": 0.3, "open_radius_px": 3, "voxel_m": 0.004,
                       "min_component_opened_texels": 50, "reconstruct_px": 2}
    return t


def run_accent(acc_mod, lab, pid, pos, cov, tcfg):
    area, nrm = acc_mod.texel_geometry(pos, cov)
    return acc_mod.team_accent(lab, pid, pos, cov, area, nrm, tcfg, CIDX)


def test_teamaccent_medusa_like_both_components():
    acc_mod = load_local("lookdev_accent")
    acc, strip, ribbon, band, info = run_accent(acc_mod, *synthetic_figure(), ta_cfg())
    assert info["share_3d_hem"] > 0 and info["share_3d_ribbon"] > 0
    assert "skipped" not in info["hem"] and "skipped" not in info["ribbon"]
    assert acc_mod.accent_classes(ta_cfg()) == ("linen", "gold_antique")


def test_teamaccent_bandless_figure_keeps_the_ribbon():
    """An armoured / plain-tunic figure: hem configured but no band texels -> the hem is skipped, no IndexError."""
    acc_mod = load_local("lookdev_accent")
    acc, strip, ribbon, band, info = run_accent(acc_mod, *synthetic_figure(gold=False), ta_cfg())
    assert "skipped" in info["hem"] and info["share_3d_hem"] == 0
    assert info["share_3d_ribbon"] > 0 and float(acc.max()) > 0.5
    assert not band.any() and float(strip.max()) == 0.0


def test_teamaccent_strapless_figure_keeps_the_hem():
    """No strap: ribbon configured but no leather texels -> the ribbon is skipped, no ValueError on an empty array."""
    acc_mod = load_local("lookdev_accent")
    acc, strip, ribbon, band, info = run_accent(acc_mod, *synthetic_figure(leather=False), ta_cfg())
    assert "skipped" in info["ribbon"] and info["share_3d_ribbon"] == 0 and not ribbon.any()
    assert info["share_3d_hem"] > 0


def test_teamaccent_components_are_optional_keys():
    acc_mod = load_local("lookdev_accent")
    lab, pid, pos, cov = synthetic_figure()
    _acc, _s, _r, _b, info = run_accent(acc_mod, lab, pid, pos, cov, ta_cfg(hem=False))
    assert info["hem"]["skipped"].startswith("no team_accent.hem") and info["share_3d_ribbon"] > 0
    assert acc_mod.accent_classes(ta_cfg(hem=False)) == ("leather_smooth", None)
    t = ta_cfg(hem=False)
    t.update(cloth_class="linen", trim_class="steel")
    assert acc_mod.accent_classes(t) == ("linen", "steel")
    _acc, _s, _r, _b, info = run_accent(acc_mod, lab, pid, pos, cov, ta_cfg(ribbon=False))
    assert info["ribbon"]["skipped"].startswith("no team_accent.ribbon") and info["share_3d_hem"] > 0
    with pytest.raises(ValueError, match="at least one"):
        run_accent(acc_mod, lab, pid, pos, cov, ta_cfg(hem=False, ribbon=False))


# ------------------------------------------------------------------ compose without a previous candidate
def new_character_profile():
    """Medusa profile turned into a new unarmed character: no previous candidate, no H2.1 baseline, no pose / channel
    views, one close-up (what SKILL stage 3 p.2 tells the executor to do)."""
    p = json.loads(MEDUSA.read_text(encoding="utf-8"))
    p["asset_id"] = "ASSET-SYNTH-001"
    wp = next(n for n, c in p["parts"].items() if c["mesh"] == "weapon")
    p["parts"][wp]["mesh"] = "body"
    p["rig"]["bones"] = [b for b in p["rig"]["bones"] if b[0] not in PR.WEAPON_BONES]
    p["rig"]["weights"][wp] = {"kind": "rigid", "bone": "hand.L"}
    p["rig"]["character"] = "Synth"
    del p["meshes"]["weapon"]
    pv = p["preview"]
    for k in ("previous_candidate", "baseline", "pose_closeups", "channel_views", "quality_reference"):
        pv.pop(k, None)
    pv["closeups"] = pv["closeups"][:1]
    pv["samples"] = 1
    pv["k2"]["resolution"] = [192, 108]
    pv["frame"] = {"px": [102, 136], "top": 0.04, "bottom": 0.93, "base_x": 0.5, "side": "right"}
    p["uv"]["density_reference_part"] = "tripo_part_0"  # a new hero names it (W1-d, RB-15): the dress, a body part
    assert PR.validate(p) == []
    return p


def write_raw_set(raw, profile, sizes=None):
    raw.mkdir(parents=True, exist_ok=True)
    for v in FR.VIEWS:
        for t in ("hp", "h2"):
            Image.new("RGB", (102, 136), (90, 90, 90)).save(raw / ("ortho-%s-%s.png" % (v, t)))
    for c in profile["preview"]["closeups"]:
        for t in ("hp", "h2"):
            Image.new("RGB", (90, 90), (90, 90, 90)).save(raw / ("closeup-%s-%s.png" % (c["name"], t)))
    for k in profile["preview"]["k2"]["distances_uu"]:
        Image.new("RGBA", (192, 108), (90, 90, 90, 255)).save(raw / ("%s-h2.png" % k))


def test_compose_without_previous_candidate(tmp_path):
    comp = load_local("compose")
    prof = new_character_profile()
    run = tmp_path / "run"
    write_raw_set(run / "work" / "preview_raw", prof)
    (run / "reports").mkdir(parents=True)
    (run / "reports" / "rig-report.json").write_text(json.dumps(
        {"meshes_pre_export": {prof["meshes"]["body"]: {"triangles": 41000}, prof["meshes"]["base"]: {"triangles": 900}}}),
        encoding="utf-8")
    (run / "reports" / "prepare-report.json").write_text(json.dumps(
        {"parts": {"a": {"triangles": [1200000, 1200000]}, "b": {"triangles": [300000, 300000]}}}), encoding="utf-8")
    written = comp.run(run, prof, REPO)
    assert {"compare-front.jpg", "compare-side.jpg", "compare-back.jpg", "closeups-hp-vs-h2.jpg", "compare-k2-5x.jpg",
            "compare-k2-1p6.jpg", "frame-k2-5x.jpg", "frame-k2-1p6.jpg"} <= set(written)
    assert not any("h21" in k for k in written)  # no baseline -> no H2.1 sheets
    # three tiles (concept | high-poly | H2), no previous-candidate tile: width < 4 x the scaled tile
    im = Image.open(run / "preview" / "compare-front.jpg")
    assert im.height == 1100
    # the high-poly label comes from the profile's source spec and prepare-report, not Medusa's constants
    label = comp.hp_label(run, prof, REPO)
    assert label == "high-poly Tripo 40c4d1cd (1,50M tris, 8K/PBR)"
    prof2 = copy.deepcopy(prof)
    prof2["sources"]["source_spec"] = "nope/missing.json"
    assert comp.hp_label(run, prof2, REPO).startswith("high-poly Tripo ? (1,50M")


# ------------------------------------------------------------------ Blender: preview + compose end to end
BUILD_SCENE = r'''
import json, sys
from pathlib import Path
import bpy
args = json.loads(sys.argv[sys.argv.index("--") + 1])
out = Path(args["out"])
bpy.ops.wm.read_factory_settings(use_empty=True)
arm_data = bpy.data.armatures.new("arm")
arm = bpy.data.objects.new(args["armature"], arm_data)
bpy.context.scene.collection.objects.link(arm)
bpy.context.view_layer.objects.active = arm
bpy.ops.object.mode_set(mode="EDIT")
for name, head, tail, parent in args["bones"]:
    b = arm_data.edit_bones.new(name)
    b.head, b.tail = head, tail
    if parent:
        b.parent = arm_data.edit_bones[parent]
bpy.ops.object.mode_set(mode="OBJECT")
def box(name, loc, size):
    bpy.ops.mesh.primitive_cube_add(size=1.0, location=loc)
    o = bpy.context.active_object
    o.name = name
    o.scale = size
    bpy.ops.object.transform_apply(scale=True)
    bpy.ops.mesh.uv_texture_add()
    o.data.uv_layers[0].name = "UVMap"
    return o
body = box(args["body"], (0, 0, 0.3), (0.12, 0.08, 0.48))
base = box(args["base"], (0, 0, 0.03), (0.3, 0.3, 0.06))
for o in (body, base):
    o.parent = arm
    o.modifiers.new("arm", "ARMATURE").object = arm
bpy.ops.wm.save_as_mainfile(filepath=str(out / "sk_authored.blend"))
for o in list(bpy.data.objects):
    bpy.data.objects.remove(o)
hp = box("HPT_part_0", (0, 0, 0.3), (0.12, 0.08, 0.48))
bpy.ops.wm.save_as_mainfile(filepath=str(out / "hp.blend"))
'''


@pytest.mark.skipif(not Path(BLENDER).is_file(), reason="Blender 5.2 not installed")
def test_preview_and_compose_blender_without_previous_candidate(tmp_path):
    prof = new_character_profile()
    run = tmp_path / "run"
    work = run / "work"
    work.mkdir(parents=True)
    bones = {b[0]: b for b in prof["rig"]["bones"]}
    spec = {"out": str(work), "armature": prof["rig"]["armature_object"], "body": prof["meshes"]["body"],
            "base": prof["meshes"]["base"],
            "bones": [[b[0], b[2], b[3], b[1] if b[1] in bones else None] for b in prof["rig"]["bones"]]}
    script = tmp_path / "build_scene.py"
    script.write_text(BUILD_SCENE, encoding="utf-8")
    flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    r = subprocess.run([BLENDER, "-b", "--factory-startup", "--python-exit-code", "1", "--python", str(script), "--",
                        json.dumps(spec)], capture_output=True, text=True, timeout=300, creationflags=flags)
    assert r.returncode == 0, r.stdout[-3000:] + r.stderr[-3000:]
    tdir = run / "textures"
    tdir.mkdir()
    for k, col in (("BC", (150, 120, 100)), ("N_OpenGL", (128, 128, 255)), ("ORM", (255, 180, 0))):
        Image.new("RGB", (64, 64), col).save(tdir / ("%s_%s.png" % (prof["textures"]["prefix"], k)))
    (run / "reports").mkdir()
    (run / "reports" / "rig-report.json").write_text(json.dumps(
        {"meshes_pre_export": {prof["meshes"]["body"]: {"triangles": 12}, prof["meshes"]["base"]: {"triangles": 12}}}),
        encoding="utf-8")
    pfile = tmp_path / "profile.json"
    pfile.write_text(json.dumps(prof), encoding="utf-8")
    params = tmp_path / "params.json"
    params.write_text(json.dumps({"stage": "preview", "profile": str(pfile), "run_dir": str(run),
                                  "repo_root": str(REPO)}), encoding="utf-8")
    r = subprocess.run([BLENDER, "-b", "--factory-startup", "--python-exit-code", "1", "--python",
                        str(PKG / "blender_entry.py"), "--", str(params)], capture_output=True, text=True, timeout=900,
                       creationflags=flags)
    assert r.returncode == 0 and "H2_BAKE_STAGE_OK preview" in r.stdout, r.stdout[-4000:] + r.stderr[-3000:]
    rep = json.loads((run / "reports" / "preview-report.json").read_text(encoding="utf-8"))
    names = {s["name"] for s in rep["shots"]}
    assert not any(n.endswith("-prev") or n.endswith("-base") for n in names)
    assert {"ortho-front-h2", "ortho-side-hp", "k2-5x-h2", "k2-1p6-h2"} <= names
    assert rep["previous_candidate"] is None and rep["baseline"] is None
    assert rep["ortho_frame"]["side"] == "right" and rep["ortho_frame"]["px"] == [102, 136]
    assert Image.open(run / "work" / "preview_raw" / "ortho-side-h2.png").size == (102, 136)
    written = load_local("compose").run(run, prof, REPO)
    assert "compare-front.jpg" in written and "frame-k2-5x.jpg" in written
