"""Правила калибровки 2026-10-09, раунд 3: развилка возврата по S, пустой rework_fix_list при возврате, устойчивый
pass для concept и anim, сверка входа (frames.json против карточки), яркость якорного класса leave-one-out и семейство
тона, новые кадры (крупные планы со спины, compare-*, лист и uv-layout не шире 2000 px), набор калибровки в репозитории.

    python -m pytest tools/art/acceptance/tests -q
"""
import hashlib
import json
import subprocess
import sys
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
sys.path.insert(0, str(HERE))

import capture_acceptance_set as cap  # noqa: E402
import validate_card as vc  # noqa: E402
from _tone import tone_table  # noqa: E402
from test_validate_card import anim_card, concept_card, fix, model_card, run  # noqa: E402

SCRIPT = str(HERE.parent / "validate_card.py")
REPO = HERE.parents[3]
CALIB = REPO / "docs" / "art-pipeline" / "evidence" / "acceptance-calibration-20261009"


def cli(*args):
    return subprocess.run([sys.executable, SCRIPT, *map(str, args)], capture_output=True, text=True,
                          encoding="utf-8", errors="replace")


def write(tmp_path, name, card):
    p = tmp_path / name
    p.write_text(json.dumps(card, ensure_ascii=False), encoding="utf-8")
    return p


# ------------------------------------------------------------------ развилка возврата по S (негатив, п.4)

def ret(S, verdict):
    return model_card(S=S, F=1.5, T=1.0, D=1.5, verdict=verdict)


def test_S_zero_other_character_only_stage_1():
    assert run(ret(0.0, "return_to_stage_1"))[0] == []
    errs = run(ret(0.0, "return_to_stage_2"))[0]
    assert any(e.startswith("verdict:") and "return_to_stage_1" in e for e in errs)


def test_S_half_or_one_either_return_route():
    for s in (0.5, 1.0):
        for v in ("return_to_stage_1", "return_to_stage_2"):
            assert run(ret(s, v))[0] == [], (s, v)


def test_return_by_S_needs_empty_fix_list_and_known_issues_allowed():
    card = ret(1.0, "return_to_stage_2")
    card["rework_fix_list"] = [fix("F"), fix("T", "close-head.jpg"), fix("D", "pose-01.jpg")]
    assert any("S < 1,5" in e and "пуст" in e for e in run(card)[0])
    card["rework_fix_list"] = []
    card["known_issues"] = [{"item": "F", "frame": "wire-front.jpg", "note": "край клинка неровный в шейдинге"},
                            {"item": "T", "frame": "turn-180.jpg", "note": "пятно переноса на плаще сзади справа"}]
    assert run(card)[0] == []


def test_print_verdict_S_zero(tmp_path):
    r = cli(write(tmp_path, "c.json", ret(0.0, "return_to_stage_1")), "--print-verdict")
    assert r.returncode == 0 and r.stdout.strip() == "return_to_stage_1"


# ------------------------------------------------------------------ устойчивый pass для concept и anim

def test_concept_unstable_pass_needs_second(tmp_path):
    card = concept_card(S=1.5, C=1.5, Q=1.5, P=2)  # 8,1
    assert card["score"] == 8.1
    r = cli(write(tmp_path, "c.json", card), "--print-verdict")
    assert r.returncode == vc.EXIT_NEEDS_SECOND and r.stdout.strip() == "needs_second_acceptor"
    stable = concept_card()  # 9,4
    assert cli(write(tmp_path, "s.json", stable), "--print-verdict").returncode == 0


def test_anim_unstable_pass_needs_second(tmp_path):
    card = anim_card(R=2, C=1.5, D=1.5, L=1.5)  # 8,1
    r = cli(write(tmp_path, "a.json", card), "--print-verdict")
    assert r.returncode == vc.EXIT_NEEDS_SECOND and r.stdout.strip() == "needs_second_acceptor"


def test_concept_pair_min_decides(tmp_path):
    a = concept_card(S=1.5, C=1.5, Q=1.5, P=2)  # 8,1 pass
    b = concept_card(S=1.5, C=1.5, Q=1.0, P=2, verdict="return_to_stage_1")  # 7,5
    b["acceptor"] = {"profile": "Sol 6.1 xhigh", "session_id": "codex:thread-c"}
    out = tmp_path / "final.json"
    r = cli(write(tmp_path, "a.json", a), "--second", write(tmp_path, "b.json", b), "--print-verdict",
            "--final-json", out)
    assert r.returncode == 0, r.stderr
    assert r.stdout.strip() == "return_to_stage_1"
    assert json.loads(out.read_text(encoding="utf-8"))["score"] == 7.5


def test_anim_pair_both_pass(tmp_path):
    a = anim_card(R=2, C=1.5, D=1.5, L=1.5)
    b = anim_card()
    b["acceptor"] = {"profile": "Sol 6.1 xhigh", "session_id": "codex:thread-a"}
    r = cli(write(tmp_path, "a.json", a), "--second", write(tmp_path, "b.json", b), "--print-verdict")
    assert r.returncode == 0 and r.stdout.strip() == "pass"


# ------------------------------------------------------------------ сверка входа: frames.json против карточки

def frames_repo(tmp_path, card, sheet_bytes=b"sheet", **man_over):
    fdir = tmp_path / card["frames"]["dir"]
    fdir.mkdir(parents=True)
    for f in card["frames"]["files"]:
        if f != "frames.json":
            (fdir / f).write_bytes(sheet_bytes if f == "sheet.png" else b"x")
    obj = tmp_path / card["accepted_object"][0]["path"]
    obj.parent.mkdir(parents=True)
    obj.write_bytes(b"fbx")
    card["accepted_object"][0]["sha256"] = hashlib.sha256(b"fbx").hexdigest()
    for r in card["reports"] + [g["source"] for g in card["gates"].values()]:
        (tmp_path / r).parent.mkdir(parents=True, exist_ok=True)
        (tmp_path / r).write_text("{}", encoding="utf-8")
    man = {"files": list(card["frames"]["files"]),
           "inputs": {"fbx": {"sha256": hashlib.sha256(b"fbx").hexdigest()}},
           "sheet": {"sha256": hashlib.sha256(b"sheet").hexdigest(), "key_match": True, "source": "x/sheet-test.png"}}
    man.update(man_over)
    (fdir / "frames.json").write_text(json.dumps(man), encoding="utf-8")
    return card


def test_frames_manifest_ok(tmp_path):
    card = frames_repo(tmp_path, model_card())
    assert run(card, check_files=True, repo=tmp_path)[0] == []
    assert vc.file_warnings(card, tmp_path) == []


def test_frames_manifest_files_must_match(tmp_path):
    card = model_card()
    card = frames_repo(tmp_path, card, files=card["frames"]["files"] + ["compare-front.jpg"])
    assert any("frames.json#files" in e and "compare-front.jpg" in e for e in run(card, check_files=True,
                                                                                 repo=tmp_path)[0])


def test_frames_manifest_fbx_must_be_accepted(tmp_path):
    card = frames_repo(tmp_path, model_card(), inputs={"fbx": {"sha256": "1" * 64}})
    assert any("не с принимаемого FBX" in e for e in run(card, check_files=True, repo=tmp_path)[0])


def test_frames_manifest_sheet_swapped(tmp_path):
    card = frames_repo(tmp_path, model_card(), sheet_bytes=b"other sheet")
    assert any("лист подменён" in e for e in run(card, check_files=True, repo=tmp_path)[0])


def test_foreign_sheet_is_warning(tmp_path):
    card = frames_repo(tmp_path, model_card(), sheet={"sha256": hashlib.sha256(b"sheet").hexdigest(),
                                                      "key_match": False, "source": "c/sheet-medusa.png",
                                                      "content_key": "medusa"})
    assert run(card, check_files=True, repo=tmp_path)[0] == []
    w = vc.file_warnings(card, tmp_path)
    assert w and "sheet-medusa.png" in w[0]


# ------------------------------------------------------------------ тон: якорь leave-one-out, семейство

def zone(px, yc, yl, hc=20.0, hl=20.0, sc=0.4, sl=0.4):
    d_hue = ((hl - hc + 180) % 360) - 180
    return {"pixels_ld": px, "concept": {"luma_Y_linear": yc, "hue_deg": hc, "sat": sc},
            "ld": {"luma_Y_linear": yl, "hue_deg": hl, "sat": sl},
            "delta_ld_vs_concept": {"Y_ratio_exposure_normalised": None, "dHue_deg": d_hue, "dSat": sl - sc}}


def measure_anchor(zones, anchor):
    """Как ld_measure: k по якорному классу, Y_ratio = Y_ld / (Y_concept / k)."""
    k = zones[anchor]["concept"]["luma_Y_linear"] / zones[anchor]["ld"]["luma_Y_linear"]
    for z in zones.values():
        z["delta_ld_vs_concept"]["Y_ratio_exposure_normalised"] = round(
            z["ld"]["luma_Y_linear"] / (z["concept"]["luma_Y_linear"] / k), 3)
    return {"zones": zones, "exposure": {"mode": "anchor_class", "class": anchor}, "exposure_k_concept_over_ld": k}


def test_anchor_class_brightness_checked_leave_one_out():
    """Якорь нормировки (платье) в 1,5 раза светлее концепта относительно остальной фигуры: y_ratio = 1 по
    построению, но y_ratio_loo ловит — основной класс вне допуска, t_cap 1,0."""
    zones = {"cloth": zone(600, 0.04, 0.09), "skin": zone(200, 0.40, 0.60), "gold": zone(200, 0.10, 0.15)}
    t = tone_table(measure_anchor(zones, "cloth"))
    row = {r["class"]: r for r in t["classes"]}
    assert row["cloth"]["y_ratio"] == 1.0 and row["cloth"]["anchor"] is True
    assert row["cloth"]["y_ratio_loo"] == pytest.approx(1.5, abs=0.01)
    assert t["t_cap"] == 1.0 and "cloth" in t["out_of_tolerance"]
    zones = {"cloth": zone(600, 0.04, 0.06), "skin": zone(200, 0.40, 0.60), "gold": zone(200, 0.10, 0.15)}
    t = tone_table(measure_anchor(zones, "cloth"))
    assert t["t_cap"] == 2.0 and {r["class"]: r for r in t["classes"]}["cloth"]["y_ratio_loo"] == pytest.approx(1.0)


def test_loo_unavailable_warns_and_floor_excluded():
    zones = {"cloth": zone(950, 0.04, 0.06), "stone": zone(50, 0.03, 0.09)}
    t = tone_table(measure_anchor(zones, "cloth"), {"grade": {"median_floor_applied": {"stone": {}}}})
    assert {r["class"]: r for r in t["classes"]}["cloth"]["y_ratio_loo"] is None
    assert any(w.startswith("loo_unavailable: cloth") for w in t["warnings"])


def test_tone_family_changed_main():
    zones = {"cloth": zone(600, 0.04, 0.06, hc=10, hl=60), "skin": zone(400, 0.40, 0.60)}
    t = tone_table(measure_anchor(zones, "skin"))
    assert t["family_changed_main"] == ["cloth"]
    zones = {"cloth": zone(600, 0.04, 0.06, hc=10, hl=20, sc=0.19, sl=0.17), "skin": zone(400, 0.40, 0.60)}
    assert tone_table(measure_anchor(zones, "skin"))["family_changed_main"] == []  # угольно-сливовое ~ серо-бежевое
    zones = {"cloth": zone(600, 0.04, 0.06, sc=0.05, sl=0.45), "skin": zone(400, 0.40, 0.60)}
    assert tone_table(measure_anchor(zones, "skin"))["family_changed_main"] == ["cloth"]  # серое -> насыщенное


def test_tone_medusa_anchor_linen_in_tolerance():
    """Числа Medusa 20260929-h2-lookdev: якорь linen по leave-one-out 1,01, потолок 2,0."""
    p = REPO / "art/pipeline-candidates/ASSET-MEDUSA-001/20260929-h2-lookdev/reports"
    if not (p / "measure-report.json").is_file():
        pytest.skip("нет measure-report Medusa")
    t = tone_table(json.loads((p / "measure-report.json").read_text(encoding="utf-8")),
                   json.loads((p / "ld-maps-report.json").read_text(encoding="utf-8")))
    linen = {r["class"]: r for r in t["classes"]}["linen"]
    assert t["anchor_class"] == "linen" and linen["y_ratio_loo"] == pytest.approx(1.01, abs=0.005)
    assert t["t_cap"] == 2.0 and t["family_changed_main"] == [] and t["warnings"] == []


# ------------------------------------------------------------------ помощники съёмки

def test_tool_and_validator_agree_on_rig_frames():
    assert set(cap.RIG_ONLY) == set(vc.POSE_FRAMES)
    for n in ("close-head-back.jpg", "close-torso-back.jpg", "close-legs.jpg", "close-legs-back.jpg",
              "compare-front.jpg", "compare-side.jpg", "compare-back.jpg"):
        assert cap.STALE.fullmatch(n), n


def test_kebab_and_accepted_maps(tmp_path):
    assert cap.kebab("KingArthur") == "king-arthur" and cap.kebab("Medusa") == "medusa"
    gen = tmp_path / "gen"
    gen.mkdir()
    for n in ("T_Medusa_H2LD_2K_BC.png", "T_Medusa_H2LD_BC.png", "T_Medusa_H2LD_2K_N.png", "T_Medusa_H2LD_2K_N_OpenGL.png",
              "T_Medusa_H2LD_2K_ORM.png", "T_Medusa_H2LD_2K_MatID.png", "T_Medusa_H2LD_2K_Edge.png",
              "T_Medusa_H2LD_TeamAccent_2K.png", "T_Medusa_H2LD_TeamAccent_4K.png", "T_Medusa_H2LD_2K_TeamMask.png"):
        (gen / n).write_bytes(b"")
    found, missing = cap.accepted_maps(gen, "Medusa")
    assert missing == [] and [p.name for _k, p in found] == [
        "T_Medusa_H2LD_2K_BC.png", "T_Medusa_H2LD_2K_N.png", "T_Medusa_H2LD_2K_ORM.png", "T_Medusa_H2LD_2K_MatID.png",
        "T_Medusa_H2LD_2K_Edge.png", "T_Medusa_H2LD_TeamAccent_2K.png"]
    fork = tmp_path / "fork"
    fork.mkdir()
    for n in ("T_KingArthur_H2LD_BC_2K.png", "T_KingArthur_H2LD_N_2K.png", "T_KingArthur_H2LD_ORM_2K.png",
              "T_KingArthur_H2LD_MatID_2K.png", "T_KingArthur_H2LD_EdgeMask_2K.png",
              "T_KingArthur_H2LD_TeamAccent_2K.png"):
        (fork / n).write_bytes(b"")
    found, missing = cap.accepted_maps(fork, "KingArthur")
    assert missing == [] and dict(found)["Edge"].name == "T_KingArthur_H2LD_EdgeMask_2K.png"
    prop = tmp_path / "prop"
    prop.mkdir()
    for n in ("T_Barrel_BC.png", "T_Barrel_N.png", "T_Barrel_ORM.png"):
        (prop / n).write_bytes(b"")
    assert cap.accepted_maps(prop, None)[1] == ["MatID", "Edge", "TeamAccent"]


def test_copy_sheet_limits_width_and_compare_frame(tmp_path):
    from PIL import Image

    wide = tmp_path / "sheet-x.png"
    Image.new("RGB", (2645, 1138), (30, 30, 30)).save(wide)
    meta = cap.copy_sheet(wide, tmp_path / "sheet.png")
    assert meta["size_px"][0] == 2000 and meta["resized_from_px"] == [2645, 1138]
    assert Image.open(tmp_path / "sheet.png").size[0] == 2000
    small = tmp_path / "sheet-y.png"
    Image.new("RGB", (1500, 900)).save(small)
    assert cap.copy_sheet(small, tmp_path / "s2.png")["resized_from_px"] is None
    view = tmp_path / "front.png"
    Image.new("RGB", (1000, 1500), (40, 40, 40)).save(view)
    turn = tmp_path / "turn.jpg"
    Image.new("RGB", (1200, 1200), (72, 72, 72)).save(turn)
    m = cap.compare_frame(view, [100, 50, 900, 1450], turn, [300, 60, 900, 1140], tmp_path / "c.jpg", ("a", "b"))
    w, h = Image.open(tmp_path / "c.jpg").size
    assert w <= cap.MAX_REVIEW_PX and h <= cap.MAX_REVIEW_PX and m["size"] == [w, h]


def test_finish_frame_bbox(tmp_path):
    from PIL import Image

    im = Image.new("RGBA", (100, 100), (0, 0, 0, 0))
    for x in range(20, 41):
        for y in range(10, 81):
            im.putpixel((x, y), (200, 0, 0, 255))
    im.save(tmp_path / "r.png")
    c = cap.finish_frame(tmp_path / "r.png", tmp_path / "o.jpg")
    assert c["bbox_px"] == [20, 10, 40, 80] and not c["touches_border"]


# ------------------------------------------------------------------ набор калибровки в репозитории

@pytest.mark.parametrize("run_dir,key,key_match", [("medusa-r1", "medusa", True), ("king-arthur-r1", "king-arthur", True),
                                                    ("king-arthur-neg-r1", "medusa", False)])
def test_calibration_frames_in_repo(run_dir, key, key_match):
    from PIL import Image

    fdir = CALIB / run_dir / "frames"
    if not (fdir / "frames.json").is_file():
        pytest.skip("набор калибровки не снят")
    man = json.loads((fdir / "frames.json").read_text(encoding="utf-8"))
    on_disk = sorted(p.name for p in fdir.iterdir())
    assert sorted(man["files"]) == on_disk
    assert set(vc.MODEL_FRAMES + vc.POSE_FRAMES) <= set(man["files"])
    assert {"compare-front.jpg", "compare-side.jpg", "compare-back.jpg", "sheet.png"} <= set(man["files"])
    assert man["sheet"]["content_key"] == key and man["sheet"]["key_match"] is key_match
    assert man["sheet"]["source"].startswith("docs/art-pipeline/evidence/acceptance-calibration-20261009/")
    for name in ("sheet.png", "uv-layout.png", "compare-front.jpg", "compare-side.jpg", "compare-back.jpg"):
        assert max(Image.open(fdir / name).size) <= cap.MAX_REVIEW_PX, name
    assert hashlib.sha256((fdir / "sheet.png").read_bytes()).hexdigest() == man["sheet"]["sha256"]
    assert set(man["pose_checks"]) == {"pose-01", "pose-02", "pose-03", "pose-04"}
    for chk in man["pose_checks"].values():
        assert "weapon_head_min_distance_m" in chk and "weapon_body_min_distance_m" in chk
    assert man["accepted_object"][0]["sha256"] == man["inputs"]["fbx"]["sha256"]
    assert ("tone.json" in man["files"]) is (run_dir == "medusa-r1")
