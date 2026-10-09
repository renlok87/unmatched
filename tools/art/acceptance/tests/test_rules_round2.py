"""Правила калибровки 2026-10-09 (раунд 2): устойчивый pass и второй приёмщик, покрытие rework_fix_list, S вне
списка, known_issues, лист в кадрах, потолок T из tone.json, тон классов, новые кадры и помощники съёмки.

    python -m pytest tools/art/acceptance/tests -q
"""
import json
import subprocess
import sys
from pathlib import Path

import numpy as np
import pytest

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
sys.path.insert(0, str(HERE))

import capture_acceptance_set as cap  # noqa: E402
import validate_card as vc  # noqa: E402
from _framing import best_separating_azimuth, clamp_close_scale, min_distance, projected_gap  # noqa: E402
from _tone import tone_table  # noqa: E402
from test_validate_card import EV, fix, model_card, run  # noqa: E402

SCRIPT = str(HERE.parent / "validate_card.py")


def cli(*args):
    return subprocess.run([sys.executable, SCRIPT, *map(str, args)], capture_output=True, text=True,
                          encoding="utf-8", errors="replace")


def write(tmp_path, name, card):
    p = tmp_path / name
    p.write_text(json.dumps(card, ensure_ascii=False), encoding="utf-8")
    return p


# ------------------------------------------------------------------ rework_fix_list (калибровка п.16)

def test_rework_by_score_needs_every_FTD_below_2():
    """Вариант T10 калибровки: score < 8 из-за T = 1,0, в списке только F — теперь код 1."""
    card = model_card(S=2, F=1.5, T=1.0, D=1.5, verdict="rework_blender", rework_fix_list=[fix("F")])
    assert card["score"] == 7.5
    errs = run(card)[0]
    assert any("нет пунктов для D, T" in e for e in errs)
    card["rework_fix_list"] = [fix("F"), fix("T", "close-head.jpg"), fix("D", "pose-01.jpg")]
    assert run(card)[0] == []


def test_rework_with_S_1_5_lists_only_FTD():
    """S = 1,5 и score < 8: S в список не входит (в Blender не правится), F/T/D ниже 2 — обязательно."""
    card = model_card(S=1.5, F=1.5, T=1.5, D=1.5, verdict="rework_blender",
                      rework_fix_list=[fix("F"), fix("T"), fix("D")])
    assert run(card)[0] == []
    card["rework_fix_list"].append(fix("S"))
    assert any("'S'" in e and "Blender" in e for e in run(card)[0])


def test_S_below_1_5_only_return_routes():
    for verdict in ("rework_blender", "pass"):
        card = model_card(S=1.0, F=2, T=2, D=2, verdict=verdict,
                          rework_fix_list=[fix("F")] if verdict == "rework_blender" else [])
        assert any(e.startswith("verdict:") for e in run(card)[0])


def test_gate_fail_with_high_score_needs_only_gate():
    card = model_card(S=2, F=2, T=1.5, D=2, verdict="rework_blender", rework_fix_list=[fix("G-UV", "uv-layout.png")])
    card["gates"]["G-UV"]["status"] = "FAIL"
    assert run(card)[0] == []


# ------------------------------------------------------------------ known_issues, лист

def test_known_issues_valid_and_checked():
    card = model_card()
    card["known_issues"] = [{"item": "T", "frame": "close-weapon.jpg", "note": "синие полосы на подкладке разреза"},
                            {"item": "G-TOPO", "frame": "wire-front.jpg", "note": "1 почти вырожденный треугольник"}]
    assert run(card)[0] == []
    card["known_issues"].append({"item": "X", "frame": "nope.jpg", "note": "плохой пункт"})
    errs = run(card)[0]
    assert errs  # схема (item) и сверка (кадр)


def test_known_issues_frame_must_exist():
    card = model_card()
    card["known_issues"] = [{"item": "T", "frame": "close-feet.jpg", "note": "кадра нет в наборе"}]
    assert any("known_issues[0].frame" in e for e in run(card)[0])


def test_sheet_required_in_model_frames():
    card = model_card()
    card["frames"]["files"].remove("sheet.png")
    assert any("sheet.png" in e for e in run(card)[0])
    card["frames"]["files"].append("sheet-medusa.png")  # прежнее имя копии листа тоже принимается
    assert run(card)[0] == []


def test_new_hero_frames_required():
    for name in ("close-hands.jpg", "close-torso.jpg", "close-base.jpg", "pose-03b.jpg"):
        card = model_card()
        card["frames"]["files"].remove(name)
        assert any(name in e for e in run(card)[0]), name


# ------------------------------------------------------------------ устойчивый pass и второй приёмщик

def unstable_pass(profile="Opus xhigh", session="workflow:acc-1"):
    card = model_card(S=2, F=1.5, T=1.5, D=1.5)  # 8,1
    card["acceptor"] = {"profile": profile, "session_id": session}
    return card


def test_unstable_pass_exit_3_and_needs_second(tmp_path):
    card = unstable_pass()
    assert card["score"] == 8.1
    r = cli(write(tmp_path, "c.json", card), "--print-verdict")
    assert r.returncode == vc.EXIT_NEEDS_SECOND and r.stdout.strip() == "needs_second_acceptor"
    stable = model_card()  # 9,4
    r = cli(write(tmp_path, "s.json", stable), "--print-verdict")
    assert r.returncode == 0 and r.stdout.strip() == "pass"


def test_rework_card_needs_no_second(tmp_path):
    card = model_card(S=1.5, F=1.5, T=1.5, D=1.5, verdict="rework_blender",
                      rework_fix_list=[fix("F"), fix("T"), fix("D")])
    r = cli(write(tmp_path, "c.json", card), "--print-verdict")
    assert r.returncode == 0 and r.stdout.strip() == "rework_blender"


def test_second_acceptor_min_score_decides(tmp_path):
    a = unstable_pass()
    b = model_card(S=2, F=1.5, T=1.0, D=1.5, verdict="rework_blender",
                   rework_fix_list=[fix("F"), fix("T"), fix("D")])  # 7,5
    b["acceptor"] = {"profile": "Sol 6.1 xhigh", "session_id": "codex:thread-1"}
    out = tmp_path / "final.json"
    r = cli(write(tmp_path, "a.json", a), "--second", write(tmp_path, "b.json", b), "--print-verdict",
            "--final-json", out)
    assert r.returncode == 0, r.stderr
    assert r.stdout.strip() == "rework_blender"
    fin = json.loads(out.read_text(encoding="utf-8"))
    assert fin["score"] == 7.5 and fin["verdict"] == "rework_blender" and fin["source_card"].endswith("b.json")


def test_second_acceptor_both_pass(tmp_path):
    a = unstable_pass()
    b = model_card()  # 9,4 pass
    b["acceptor"] = {"profile": "Sol 6.1 xhigh", "session_id": "codex:thread-2"}
    r = cli(write(tmp_path, "a.json", a), "--second", write(tmp_path, "b.json", b), "--print-verdict")
    assert r.returncode == 0 and r.stdout.strip() == "pass"
    assert "8.1" in r.stderr  # итоговый score — минимум


def test_second_acceptor_stricter_route_wins(tmp_path):
    """У второй карточки score выше, но вето (D = 0,5): строгий маршрут не теряется."""
    a = unstable_pass()
    b = model_card(S=2, F=2, T=2, D=0.5, verdict="rework_blender", rework_fix_list=[fix("D", "pose-01.jpg")])  # 8,1
    b["acceptor"] = {"profile": "Sol 6.1 xhigh", "session_id": "codex:thread-3"}
    r = cli(write(tmp_path, "a.json", a), "--second", write(tmp_path, "b.json", b), "--print-verdict")
    assert r.returncode == 0 and r.stdout.strip() == "rework_blender"


def test_second_acceptor_pair_checks(tmp_path):
    a = unstable_pass()
    same_profile = unstable_pass(session="workflow:acc-2")
    r = cli(write(tmp_path, "a.json", a), "--second", write(tmp_path, "b.json", same_profile))
    assert r.returncode == 1 and "профиль" in r.stderr
    other_frames = unstable_pass(profile="Sol 6.1 xhigh", session="codex:t")
    other_frames["frames"] = dict(other_frames["frames"], dir=EV + "/frames-other")
    r = cli(write(tmp_path, "a.json", a), "--second", write(tmp_path, "c.json", other_frames))
    assert r.returncode == 1 and "frames" in r.stderr
    gates = unstable_pass(profile="Sol 6.1 xhigh", session="codex:t")
    gates["gates"]["G-UV"]["status"] = "FAIL"
    gates["verdict"], gates["verdict_reason"], gates["status_note"] = "rework_blender", "правило 3: G-UV FAIL", ""
    gates["rework_fix_list"] = [fix("G-UV", "uv-layout.png")]
    r = cli(write(tmp_path, "a.json", a), "--second", write(tmp_path, "d.json", gates))
    assert r.returncode == 1 and "гейтов" in r.stderr


# ------------------------------------------------------------------ tone.json → потолок T (--check-files)

def test_tone_cap_limits_T(tmp_path):
    card = model_card(T=2)
    card["frames"]["files"].append("tone.json")
    fdir = tmp_path / card["frames"]["dir"]
    fdir.mkdir(parents=True)
    (fdir / "tone.json").write_text(json.dumps({"t_cap": 1.5}), encoding="utf-8")
    errs = run(card, check_files=True, repo=tmp_path)[0]
    assert any("t_cap" in e for e in errs)
    card2 = model_card(T=1.5)
    card2["frames"]["files"].append("tone.json")
    assert not any("t_cap" in e for e in run(card2, check_files=True, repo=tmp_path)[0])


def measure(**ratios):
    zones = {}
    for cid, (px, y, hue) in ratios.items():
        zones[cid] = {"pixels_ld": px, "delta_ld_vs_concept": {"Y_ratio_exposure_normalised": y, "dHue_deg": hue,
                                                               "dSat": 0.0}}
    return {"zones": zones, "exposure_k_concept_over_ld": 0.84, "exposure": {"mode": "anchor_class"}}


def test_tone_table_medusa_numbers_cap_2():
    """Числа Medusa 20260929-h2-lookdev (measure-report + median_floor_applied): потолок 2,0."""
    m = measure(gold_antique=(232446, 0.988, 1.0), leather_smooth=(85717, 1.041, -2.3),
                leather_worn=(23980, 1.203, -1.7), legacy_bake=(116785, 1.072, 0.0), linen=(576731, 1.0, 0.0),
                skin=(175109, 0.965, -0.8), stone_base=(356286, 1.582, -2.8), wood=(43759, 1.466, -3.8))
    maps = {"grade": {"median_floor_applied": {"leather_smooth": {}, "stone_base": {}, "wood": {}}}}
    t = tone_table(m, maps)
    assert t["t_cap"] == 2.0 and t["floor_limited"] == ["leather_smooth", "stone_base", "wood"]
    assert t["out_of_tolerance"] == []
    t2 = tone_table(m, None)  # без отчёта карт пол не учитывается: камень (22 %) — основной класс вне допуска
    assert t2["t_cap"] == 1.0 and "stone_base" in t2["out_of_tolerance"]
    assert t["framing"] == "default"  # Medusa: the canon frame, no framing block in measure-report


def test_tone_table_marks_concept_framing():
    """h2-bake 0.6.1: measure-report of a look-dev profile with `frame` carries `framing` -> tone.json framing concept."""
    m = measure(linen=(1000, 1.0, 0.0))
    m["framing"] = {"frame": {"checks_report": "x/checks-report.json", "side": "right"}, "views": {}}
    assert tone_table(m)["framing"] == "concept"


def test_tone_table_secondary_and_hue():
    t = tone_table(measure(cloth=(900, 1.0, 0.0), belt=(50, 1.4, 0.0)))
    assert t["t_cap"] == 1.5
    t = tone_table(measure(cloth=(900, 1.0, 20.0), belt=(50, 1.0, 0.0)))
    assert t["t_cap"] == 1.0
    with pytest.raises(ValueError):
        tone_table({"zones": {}})


# ------------------------------------------------------------------ помощники съёмки

def test_pick_texture_fork_suffix_naming(tmp_path):
    for n in ("T_KingArthur_H2LD_BC_2K.png", "T_KingArthur_H2LD_BC_4K.png", "T_KingArthur_H2LD_N_2K.png",
              "T_KingArthur_H2LD_N_4K.png", "T_KingArthur_H2LD_ORM_4K.png", "T_KingArthur_H2LD_TeamMaskRGBA_2K.png"):
        (tmp_path / n).write_bytes(b"")
    assert cap.pick_texture(tmp_path, "_BC", "KingArthur").name == "T_KingArthur_H2LD_BC_2K.png"
    assert cap.pick_texture(tmp_path, "_N", "KingArthur").name == "T_KingArthur_H2LD_N_2K.png"
    assert cap.pick_texture(tmp_path, "_ORM", "KingArthur").name == "T_KingArthur_H2LD_ORM_4K.png"  # 2K нет


def test_compose_panels_and_sheet_info(tmp_path):
    from PIL import Image

    Image.new("RGBA", (60, 120), (255, 0, 0, 255)).save(tmp_path / "r.png")
    Image.new("RGBA", (60, 120), (0, 0, 255, 255)).save(tmp_path / "l.png")
    cap.compose_panels(tmp_path / "r.png", tmp_path / "l.png", tmp_path / "o.png")
    o = Image.open(tmp_path / "o.png")
    assert o.size == (120, 120) and o.getpixel((5, 100))[0] == 255 and o.getpixel((115, 100))[2] == 255
    sheet = tmp_path / "sheet-x.png"
    Image.new("RGB", (10, 10)).save(sheet)
    assert cap.sheet_info(sheet)["compare_palette_by"] == "views"
    (tmp_path / "checks-report.json").write_text(json.dumps({"palette": {"swatches": [{"hex": "#112233"}]}}),
                                                 encoding="utf-8")
    info = cap.sheet_info(sheet)
    assert info["swatches"] == 1 and info["compare_palette_by"] == "swatches"


def test_find_measure(tmp_path):
    (tmp_path / "export").mkdir()
    (tmp_path / "reports").mkdir()
    fbx = tmp_path / "export" / "SK_X_H2LD.fbx"
    fbx.write_bytes(b"")
    assert cap.find_measure(fbx) is None
    (tmp_path / "reports" / "measure-report.json").write_text("{}", encoding="utf-8")
    assert cap.find_measure(fbx).name == "measure-report.json"


def test_stale_pattern_covers_new_files():
    for n in ("close-hands.jpg", "close-torso.jpg", "close-base.jpg", "pose-03b.jpg", "sheet.png", "tone.json"):
        assert cap.STALE.fullmatch(n), n
    assert not cap.STALE.fullmatch("card.json")


def test_close_scale_clamp_and_distances():
    assert clamp_close_scale(0.0, 1.0) == pytest.approx(0.12)
    assert clamp_close_scale(0.5, 1.0) == pytest.approx(0.25)
    a = np.array([[0.0, 0.0, 0.0], [0.0, 0.0, 0.1]])
    b = np.array([[0.3, 0.0, 0.0]])
    assert min_distance(a, b) == pytest.approx(0.3)
    # точки разведены по X: спереди (az 0) зазор 0,3, сбоку (az 90) проекции совпадают
    assert projected_gap(a, b, 0, 0) == pytest.approx(0.3)
    assert projected_gap(a, b, 90, 0) == pytest.approx(0.0, abs=1e-9)
    az, gap = best_separating_azimuth(a, b, el=0)
    assert az in (0, 180) and gap == pytest.approx(0.3)


def test_second_acceptor_same_profile_fallback(tmp_path):
    a = unstable_pass()
    b = unstable_pass(session="workflow:acc-2")
    out = tmp_path / "final.json"
    r = cli(write(tmp_path, "a.json", a), "--second", write(tmp_path, "b.json", b), "--same-profile-ok",
            "--final-json", out, "--print-verdict")
    assert r.returncode == 0 and r.stdout.strip() == "pass"
    assert json.loads(out.read_text(encoding="utf-8"))["same_profile_fallback"] is True
