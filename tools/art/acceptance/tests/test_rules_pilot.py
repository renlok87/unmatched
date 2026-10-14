"""Правила по пилоту скилла 2026-10-13 (волна 1, пакет W1-c): оттенок только у хроматических медиан (RB-06), CLI
таблицы тона (RB-19), tone.json и frames.json модели читаются всегда (RB-16), машинные гейты пересчитываются по отчётам
(RB-05).

    python -m pytest tools/art/acceptance/tests -q
"""
import copy
import hashlib
import json
import subprocess
import sys
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
sys.path.insert(0, str(HERE))

import validate_card as vc  # noqa: E402
from _tone import tone_table  # noqa: E402
from test_rules_round3 import measure_anchor, zone  # noqa: E402
from test_validate_card import fix, model_card, run  # noqa: E402

TONE = str(HERE.parent / "_tone.py")
SCRIPT = str(HERE.parent / "validate_card.py")
REPO = HERE.parents[3]
PILOT = REPO / "art" / "pipeline-candidates"


def jdump(p, data):
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    return p


# ------------------------------------------------------------------ RB-06: оттенок только у хроматических медиан

def test_grey_main_class_hue_ignored():
    """Сталь (sat 0,02 / 0,04, оттенок — шум): dHue −114° не выносит основной класс за допуск, t_cap 2,0."""
    zones = {"steel": zone(600, 0.20, 0.30, hc=200, hl=86, sc=0.02, sl=0.04), "skin": zone(400, 0.40, 0.60)}
    t = tone_table(measure_anchor(zones, "skin"))
    row = {r["class"]: r for r in t["classes"]}["steel"]
    assert row["role"] == "main" and row["hue_checked"] is False and row["status"] == "ok"
    assert t["t_cap"] == 2.0 and t["out_of_tolerance"] == []


def test_chromatic_hue_still_checked():
    zones = {"cloth": zone(600, 0.20, 0.30, hc=10, hl=30), "skin": zone(400, 0.40, 0.60)}
    t = tone_table(measure_anchor(zones, "skin"))
    assert {r["class"]: r for r in t["classes"]}["cloth"]["hue_checked"] is True
    assert t["t_cap"] == 1.0 and t["out_of_tolerance"] == ["cloth"]


def test_neutral_to_chromatic_is_family_not_hue():
    """Одна медиана серая, другая насыщенная: оттенок не сравнивается, переход ловит семейство (S)."""
    zones = {"cloth": zone(600, 0.20, 0.30, hc=10, hl=60, sc=0.05, sl=0.45), "skin": zone(400, 0.40, 0.60)}
    t = tone_table(measure_anchor(zones, "skin"))
    assert t["out_of_tolerance"] == [] and t["family_changed_main"] == ["cloth"]


def test_angel_metal_forged_not_out_by_hue():
    """Воспроизведение RB-06: Angel 20261013-h2-lookdev, metal_forged sat 0,020/0,043, dHue −114,3°."""
    p = PILOT / "ASSET-ANGEL-001" / "20261013-h2-lookdev" / "reports"
    if not (p / "measure-report.json").is_file():
        pytest.skip("нет measure-report Angel")
    t = tone_table(json.loads((p / "measure-report.json").read_text(encoding="utf-8")),
                   json.loads((p / "ld-maps-report.json").read_text(encoding="utf-8")))
    row = {r["class"]: r for r in t["classes"]}["metal_forged"]
    assert row["d_hue_deg"] < -100 and row["hue_checked"] is False and row["status"] == "ok"
    assert "metal_forged" not in t["out_of_tolerance"] and t["t_cap"] == 1.5  # legacy_bake и silk — по яркости


# ------------------------------------------------------------------ RB-19: CLI таблицы тона

def tone_cli(*args):
    return subprocess.run([sys.executable, TONE, *map(str, args)], capture_output=True, text=True, encoding="utf-8",
                          errors="replace")


def test_tone_cli_cap_out_floor(tmp_path):
    zones = {"cloth": zone(600, 0.20, 0.30), "skin": zone(300, 0.40, 0.60), "stone": zone(50, 0.03, 0.09)}
    m = jdump(tmp_path / "run" / "reports" / "measure-report.json", measure_anchor(zones, "skin"))
    r = tone_cli(m)
    assert r.returncode == 2 and "t_cap: 1.5" in r.stdout and "out: stone" in r.stdout and "floor: —" in r.stdout
    maps = jdump(tmp_path / "maps.json", {"grade": {"median_floor_applied": {"stone": {}}}})
    r = tone_cli(m, maps)
    assert r.returncode == 0 and "t_cap: 2.0" in r.stdout and "floor: stone" in r.stdout and "out: —" in r.stdout
    jdump(m.with_name("ld-maps-report.json"), {"grade": {"median_floor_applied": {"stone": {}}}})
    r = tone_cli(tmp_path / "run")  # каталог run и ld-maps-report рядом по умолчанию — как съёмка
    assert r.returncode == 0 and "floor: stone" in r.stdout
    r = tone_cli(m, "--json")
    assert r.returncode == 0 and json.loads(r.stdout)["schema"] == "unmatched.acceptance-tone/1"
    assert tone_cli(tmp_path / "nope.json").returncode == 1


def test_tone_cli_medusa():
    p = PILOT / "ASSET-MEDUSA-001" / "20260929-h2-lookdev"
    if not (p / "reports" / "measure-report.json").is_file():
        pytest.skip("нет measure-report Medusa")
    r = tone_cli(p)
    assert r.returncode == 0 and "t_cap: 2.0" in r.stdout and "floor: leather_smooth, stone_base, wood" in r.stdout


# ------------------------------------------------------------------ RB-16: tone.json и frames.json читаются всегда

def frames_dir(tmp_path, card, man=None, tone=None):
    fdir = tmp_path / card["frames"]["dir"]
    fdir.mkdir(parents=True, exist_ok=True)
    if man is not None:
        jdump(fdir / "frames.json", man)
    if tone is not None:
        jdump(fdir / "tone.json", tone)
    return fdir


def test_tone_cap_checked_when_not_listed(tmp_path):
    card = model_card(T=2)
    assert "tone.json" not in card["frames"]["files"]
    frames_dir(tmp_path, card, tone={"t_cap": 1.5})
    assert any("t_cap 1.5" in e for e in run(card, check_files=True, repo=tmp_path)[0])


def test_frames_manifest_checked_when_not_listed(tmp_path):
    card = model_card()
    card["frames"]["files"].remove("frames.json")
    frames_dir(tmp_path, card, man={"files": card["frames"]["files"], "inputs": {"fbx": {"sha256": "1" * 64}}})
    assert any("не с принимаемого FBX" in e for e in run(card, check_files=True, repo=tmp_path)[0])


def test_model_without_frames_manifest(tmp_path):
    card = model_card()
    frames_dir(tmp_path, card)
    assert any("нет манифеста кадров" in e for e in run(card, check_files=True, repo=tmp_path)[0])


def test_tone_named_by_manifest_but_missing(tmp_path):
    card = model_card()
    frames_dir(tmp_path, card, man={"files": card["frames"]["files"], "tone": {"file": "tone.json", "t_cap": 2.0}})
    assert any("frames.json его называет" in e for e in run(card, check_files=True, repo=tmp_path)[0])


def test_tone_replaced_after_capture(tmp_path):
    card = model_card(T=1.5)
    card["frames"]["files"].append("tone.json")
    frames_dir(tmp_path, card, man={"files": card["frames"]["files"], "tone": {"file": "tone.json", "t_cap": 1.0}},
               tone={"t_cap": 2.0})
    errs = run(card, check_files=True, repo=tmp_path)[0]
    assert any("заменён после съёмки" in e for e in errs)


def test_stale_tone_cap_is_warning(tmp_path):
    """tone.json снят старым правилом (оттенок серого класса выносил его за допуск): WARN, а проверяет t_cap файла."""
    zones = {"steel": zone(600, 0.20, 0.30, hc=200, hl=86, sc=0.02, sl=0.04), "skin": zone(400, 0.40, 0.60)}
    mrel = "art/pipeline-candidates/ASSET-TEST-001/20261014-h2-lookdev/reports/measure-report.json"
    jdump(tmp_path / mrel, measure_anchor(zones, "skin"))
    card = model_card(T=1.0)
    frames_dir(tmp_path, card, tone={"t_cap": 1.0, "sources": {"measure_report": mrel, "maps_report": None}})
    assert any("пересчёт текущим _tone.py" in w and "= 2.0" in w for w in vc.tone_warnings(card, tmp_path))


# ------------------------------------------------------------------ RB-05: машинные гейты из отчётов

KEY = "Test"
LD = "art/pipeline-candidates/ASSET-TEST-001/20261014-h2-lookdev"
BK = "art/pipeline-candidates/ASSET-TEST-001/20261014-h2-bake"
PROF = "art/pipeline-candidates/ASSET-TEST-001/build-profiles/test-h2-bake-h2.json"
MAPS = ("BC", "N", "ORM", "MatID", "Edge")
SHA = {x: hashlib.sha256(x.encode()).hexdigest() for x in MAPS + ("TeamAccent",)}
ASSET_CARD = {
    "POLY_BUDGET": {"figure_tris_max": 45000, "base_tris_max": 2500}, "FIGURE_HEIGHT_M": 0.55,
    "UE_NAMES": {"stage": "H2LD", "skeletal_mesh": "SK_Test_H2LD", "base": "SM_Test_H2LD_Base",
                 "textures": ["T_Test_H2LD_{BC,N,ORM,MatID,TeamAccent}", "T_Test_H2LD_Edge (или _EdgeMask)",
                              "T_UM_MatLUT_Test"]},
}


def passed(*keys):
    return {k: {"passed": True} for k in keys}


def gate_reports(body_top=0.55):
    meshes = {"SK_Test_H2_Body": 40000, "SK_Test_H2_Sword": 1000, "SM_Test_H2_Base": 1500}
    ld_fbx = {
        "passed": True,
        "checks": {"triangles_as_h21": {"passed": True, "measured": dict(meshes)},
                   **passed("bones_and_parents_as_h21", "bone_heads_tails_as_h21", "positions_and_uv0_per_loop_as_h21",
                            "export_frame_face_points_along_rotated_front_ue_plus_x")},
        "meshes_pre_export": {m: {"triangles": t, "near_degenerate_triangles": 1 if m.endswith("Body") else 0,
                                  "material_slots": ["M_Test_H2_Atlas"]} for m, t in meshes.items()},
        "exports": {"skeletal_fbx": {"path": LD + "/export/SK_Test_H2LD.fbx"},
                    "base_fbx": {"path": LD + "/export/SM_Test_H2LD_Base.fbx"},
                    "settings": {"preset": {"name": "UM_FBX_v1"}, "unit_scale_factor_after_patch": 1.0}},
        "roundtrip": {"ld": {"skeletal": {"armature_objects": ["SKEL_UM_Humanoid"],
                                          "meshes": {"SK_Test_H2_Body": {"bounds_m": {"max": [0.1, 0.1, body_top]}},
                                                     "SK_Test_H2_Sword": {"bounds_m": {"max": [0.1, 0.2, 0.60]}}}},
                             "base": {"meshes": {"SM_Test_H2_Base": {"bounds_m": {"max": [0.15, 0.15, 0.06]}}}}}},
    }
    outs = {"%s_2K_%s.png" % ("T_Test_H2LD", x): {"px": [2048, 2048], "sha256": SHA[x]} for x in MAPS if x != "N"}
    outs["T_Test_H2LD_2K_N.png"] = {"copied_from": "T_Test_H2_2K_N.png", "sha256": SHA["N"]}
    outs["T_Test_H2LD_BC.png"] = {"px": [4096, 4096], "sha256": "4k"}
    return {
        LD + "/reports/ld-fbx-report.json": ld_fbx,
        LD + "/reports/ld-maps-report.json": {
            "passed": True, "outputs": outs, "pins": {"2K_N": {"sha256": SHA["N"]}},
            "checks": passed("matid_values_valid", "matid_decodes_to_labels_4k", "orm_metallic_binary_per_class_4k")},
        LD + "/reports/ld-team-accent-report.json": {
            "passed": True, "outputs": {"T_Test_H2LD_TeamAccent_2K.png": {"px": [2048, 2048], "sha256": SHA["TeamAccent"]}}},
        BK + "/reports/seams-report.json": {"passed": True},
        BK + "/reports/close-report.json": {"passed": True},
        BK + "/reports/uv-report.json": {"passed": True, "checks": passed(
            "raster_overlap_px", "island_gap_px_at_4k", "no_folded_uv_triangles")},
        BK + "/reports/textures-report.json": {
            "passed": True, "outputs": {"T_Test_H2_2K_N.png": {"px": [2048, 2048], "sha256": SHA["N"]}},
            "checks": passed("sizes_2k", "dx_equals_opengl_g_inverted_2k", "normal_length_2k",
                             "orm_occlusion_baked_not_constant")},
        BK + "/reports/rig-report.json": {"passed": True, "checks": passed(
            "bones_and_parents_as_profile", "max_influences", "no_unweighted_vertices", "material_slots",
            "unit_scale_1_and_height")},
        BK + "/reports/probes-report.json": {"passed": True, "plausible": {"test-h2-blend": 7, "test-h2-fbx": 7},
                                             "validate_clip_v2": {"result": "pass"}},
        BK + "/reports/validate-skeletal-mesh-v2.json": {"result": "pass"},
    }


DECIDES = {"G-TOPO": "ld-fbx-report.json", "G-UV": "uv-report.json", "G-TEX": "ld-maps-report.json",
           "G-RIG": "rig-report.json", "G-NAMES": "ld-fbx-report.json"}


def gate_repo(tmp_path, card=None, **kw):
    """Синтетический H2-герой: отчёты, профиль, textures/ look-dev и карточка со ссылками на них."""
    reports = gate_reports(**kw)
    for rel, data in reports.items():
        jdump(tmp_path / rel, data)
    jdump(tmp_path / LD / "reports" / "run-manifest.json", {"source_profile": {"path": PROF}})
    jdump(tmp_path / PROF, {"meshes": {"body": "SK_Test_H2_Body", "weapon": "SK_Test_H2_Sword",
                                       "base": "SM_Test_H2_Base"}, "materials": {"atlas": "M_Test_H2_Atlas"}})
    tdir = tmp_path / LD / "textures"
    tdir.mkdir(parents=True, exist_ok=True)
    for n in ["T_Test_H2LD_2K_%s.png" % x for x in MAPS] + ["T_Test_H2LD_TeamAccent_2K.png", "T_UM_MatLUT_Test.dds",
                                                              "T_Test_H2LD_BC.png"]:
        (tdir / n).write_bytes(b"x")
    card = card or model_card()
    card["reports"] = list(reports)
    card["accepted_object"] = ([{"path": LD + "/export/SK_Test_H2LD.fbx", "sha256": "0" * 64}]
                               + [{"path": "%s/textures/T_Test_H2LD_2K_%s.png" % (LD, x), "sha256": SHA[x]} for x in MAPS]
                               + [{"path": LD + "/textures/T_Test_H2LD_TeamAccent_2K.png", "sha256": SHA["TeamAccent"]}])
    for g, name in DECIDES.items():
        card["gates"][g]["source"] = next(r for r in reports if r.endswith("/" + name))
    return card


def edit(tmp_path, name, fn):
    p = next((tmp_path / r) for r in gate_reports() if r.endswith("/" + name))
    data = json.loads(p.read_text(encoding="utf-8"))
    fn(data)
    jdump(p, data)


def statuses(card, tmp_path, ac=ASSET_CARD):
    res, warns = vc.recompute_gates(card, tmp_path, copy.deepcopy(ac))
    return {g: r["status"] for g, r in res.items()}, res, warns


def test_gates_all_pass(tmp_path):
    card = gate_repo(tmp_path)
    st, res, warns = statuses(card, tmp_path)
    assert set(st.values()) == {"PASS"} and not any(r["partial"] for r in res.values()) and warns == []
    assert vc.gate_errors(card, tmp_path, copy.deepcopy(ASSET_CARD)) == []


def test_gate_topo_budget_and_degenerate(tmp_path):
    card = gate_repo(tmp_path)
    ac = copy.deepcopy(ASSET_CARD)
    ac["POLY_BUDGET"]["figure_tris_max"] = 40500  # Body 40000 + Sword 1000 = 41000
    st, res, _ = statuses(card, tmp_path, ac)
    assert st["G-TOPO"] == "FAIL" and "41000 > POLY_BUDGET.figure_tris_max 40500" in res["G-TOPO"]["why"][0]
    edit(tmp_path, "ld-fbx-report.json",
         lambda d: d["meshes_pre_export"]["SK_Test_H2_Sword"].update(near_degenerate_triangles=2))  # 0,2 % > 0,1 %
    st, res, _ = statuses(card, tmp_path)
    assert st["G-TOPO"] == "FAIL" and any("SK_Test_H2_Sword.near_degenerate_triangles = 2" in w
                                          for w in res["G-TOPO"]["why"])
    errs = vc.gate_errors(card, tmp_path, copy.deepcopy(ASSET_CARD))
    assert len(errs) == 1 and errs[0].startswith("gates.G-TOPO: в карточке PASS, пересчёт по отчётам — FAIL")


def test_gate_missing_report_is_fail(tmp_path):
    card = gate_repo(tmp_path)
    card["reports"] = [r for r in card["reports"] if not r.endswith("seams-report.json")]
    st, res, _ = statuses(card, tmp_path)
    assert st["G-TOPO"] == "FAIL" and "seams-report.json: нет в reports" in res["G-TOPO"]["why"][0]


def test_gate_uv_rig_tex(tmp_path):
    card = gate_repo(tmp_path)
    edit(tmp_path, "uv-report.json", lambda d: d["checks"]["raster_overlap_px"].update(passed=False))
    edit(tmp_path, "probes-report.json", lambda d: d["plausible"].update({"test-h2-fbx": 6}))
    edit(tmp_path, "ld-team-accent-report.json",
         lambda d: d["outputs"]["T_Test_H2LD_TeamAccent_2K.png"].update(px=[4096, 4096]))
    st, res, _ = statuses(card, tmp_path)
    assert st == {"G-TOPO": "PASS", "G-UV": "FAIL", "G-TEX": "FAIL", "G-RIG": "FAIL", "G-NAMES": "PASS"}
    assert "raster_overlap_px.passed" in res["G-UV"]["why"][0]
    assert "plausible.*-fbx = [6]" in res["G-RIG"]["why"][0]
    assert "TeamAccent_2K.png.px = [4096, 4096]" in res["G-TEX"]["why"][0]


def test_gate_tex_normal_bridge(tmp_path):
    """N копируется из bake: px берётся из textures-report по sha моста; sha N ≠ pins.2K_N — FAIL."""
    card = gate_repo(tmp_path)
    edit(tmp_path, "ld-maps-report.json", lambda d: d["pins"]["2K_N"].update(sha256="f" * 64))
    st, res, _ = statuses(card, tmp_path)
    assert st["G-TEX"] == "FAIL" and any("мост N" in w for w in res["G-TEX"]["why"])


def test_gate_names_ue_names_and_slots(tmp_path):
    card = gate_repo(tmp_path)
    ac = copy.deepcopy(ASSET_CARD)
    ac["UE_NAMES"]["skeletal_mesh"] = "SK_Test_H3LD"
    st, res, _ = statuses(card, tmp_path, ac)
    assert st["G-NAMES"] == "FAIL" and "UE_NAMES.skeletal_mesh SK_Test_H3LD.fbx" in res["G-NAMES"]["why"][0]
    (tmp_path / LD / "textures" / "T_UM_MatLUT_Test.dds").unlink()
    edit(tmp_path, "ld-fbx-report.json",
         lambda d: d["meshes_pre_export"]["SM_Test_H2_Base"].update(material_slots=["M_Other"]))
    st, res, _ = statuses(card, tmp_path)
    why = " | ".join(res["G-NAMES"]["why"])
    assert "T_UM_MatLUT_Test" in why and "SM_Test_H2_Base.material_slots" in why


def test_gate_names_edge_alternative(tmp_path):
    """«T_<Key>_H2LD_Edge (или _EdgeMask)»: годится любой из двух файлов."""
    card = gate_repo(tmp_path)
    tdir = tmp_path / LD / "textures"
    (tdir / "T_Test_H2LD_2K_Edge.png").rename(tdir / "T_Test_H2LD_2K_EdgeMask.png")
    card["accepted_object"] = [o for o in card["accepted_object"] if "_2K_Edge" not in o["path"]]
    assert statuses(card, tmp_path)[0]["G-NAMES"] == "PASS"


def test_gate_names_height_body_without_weapon(tmp_path):
    """F41/F78: рост — верх тела без оружия (меч выше головы роста не задаёт); деталь тела выше головы (рога) —
    по FIGURE_BOUNDS_TOP_M заявки."""
    card = gate_repo(tmp_path, body_top=0.5502)
    assert statuses(card, tmp_path)[0]["G-NAMES"] == "PASS"  # меч 0,60 м выше — не мешает
    card = gate_repo(tmp_path, body_top=0.7356)  # рога в меше тела
    st, res, _ = statuses(card, tmp_path)
    assert st["G-NAMES"] == "FAIL" and "0.7356 м ≠ FIGURE_HEIGHT_M 0.5500" in res["G-NAMES"]["why"][0]
    ac = dict(copy.deepcopy(ASSET_CARD), FIGURE_BOUNDS_TOP_M=0.7358)
    assert statuses(card, tmp_path, ac)[0]["G-NAMES"] == "PASS"


def test_card_fail_but_reports_pass(tmp_path):
    card = model_card(verdict="rework_blender", rework_fix_list=[fix("G-UV", "uv-layout.png")])
    card["gates"]["G-UV"]["status"] = "FAIL"
    card = gate_repo(tmp_path, card=card)
    errs = vc.gate_errors(card, tmp_path, copy.deepcopy(ASSET_CARD))
    assert errs == ["gates.G-UV: в карточке FAIL, пересчёт по отчётам — PASS (решающие ключи §4 в норме): статус "
                    "гейта ставится по отчёту"]


def test_without_asset_card_partial(tmp_path):
    """Нет заявки: POLY_BUDGET по умолчанию, UE_NAMES и рост не сверены — пересчёт G-NAMES неполный, FAIL карточки им
    не опровергается."""
    card = model_card(verdict="rework_blender", rework_fix_list=[fix("G-NAMES")])
    card["gates"]["G-NAMES"]["status"] = "FAIL"
    card = gate_repo(tmp_path, card=card)
    res, warns = vc.recompute_gates(card, tmp_path)
    assert res["G-NAMES"] == {"status": "PASS", "why": [], "partial": True}
    assert any("нет заявки" in w for w in warns) and any(w.startswith("G-NAMES пересчитан не целиком") for w in warns)
    assert vc.gate_errors(card, tmp_path) == []


def test_asset_card_yaml_default_path(tmp_path):
    yaml = pytest.importorskip("yaml")
    card = gate_repo(tmp_path)
    p = tmp_path / "art" / "pipeline-candidates" / "ASSET-TEST-001" / "asset-card.yaml"
    ac = copy.deepcopy(ASSET_CARD)
    ac["UE_NAMES"]["base"] = "SM_Wrong_Base"
    p.write_text(yaml.safe_dump(ac, allow_unicode=True), encoding="utf-8")
    res, warns = vc.recompute_gates(card, tmp_path)
    assert res["G-NAMES"]["status"] == "FAIL" and warns == []


def test_gates_wired_into_check_files(tmp_path):
    card = gate_repo(tmp_path)
    ac = copy.deepcopy(ASSET_CARD)
    ac["POLY_BUDGET"]["base_tris_max"] = 1000
    errs = run(card, check_files=True, repo=tmp_path, asset_card=ac)[0]
    assert any(e.startswith("gates.G-TOPO: в карточке PASS") for e in errs)
    assert not any(e.startswith("gates.G-TOPO") for e in run(card, check_files=True, repo=tmp_path,
                                                                 asset_card=copy.deepcopy(ASSET_CARD))[0])


def test_prop_and_fork_not_recomputed(tmp_path):
    prop = model_card(D=None)
    prop["gates"]["G-RIG"]["status"] = "n/a"
    res, warns = vc.recompute_gates(prop, tmp_path)
    assert res == {} and "пропа" in warns[0]
    res, warns = vc.recompute_gates(model_card(), tmp_path)  # нет ld-fbx-report.json — форк старше скилла
    assert res == {} and "ld-fbx-report.json" in warns[0]


# ------------------------------------------------------------------ карточки пилота и калибровки

PILOT_CARDS = sorted(PILOT.glob("ASSET-*/evidence/acceptance/*/card*.json"))


@pytest.mark.parametrize("path", PILOT_CARDS, ids=lambda p: "%s/%s/%s" % (p.parts[-5], p.parts[-2], p.name))
def test_pilot_cards_pass_recomputed_gates(path):
    """Карточки модели пилота 2026-10-13/14: гейты карточки совпадают с пересчётом, --check-files код 0 или 3."""
    r = subprocess.run([sys.executable, SCRIPT, str(path), "--check-files"], capture_output=True, text=True,
                       encoding="utf-8", errors="replace", cwd=str(REPO))
    assert r.returncode in (0, 3), r.stderr


def test_medusa_round3_sol_gtex_discrepancy_caught():
    """Калибровка раунд 3: Sol поставил G-TEX FAIL по буквальному чтению строки рубрики (разбор раунда 4) —
    пересчёт по отчётам даёт PASS, валидатор называет расхождение."""
    p = REPO / "docs/art-pipeline/evidence/acceptance-calibration-20261009/medusa-r1/round3-sol/card-2.json"
    if not p.is_file():
        pytest.skip("нет карточки калибровки")
    card = vc.strip_output_nulls(json.loads(p.read_text(encoding="utf-8")))
    errs = vc.gate_errors(card, REPO)
    assert errs and errs[0].startswith("gates.G-TEX: в карточке FAIL, пересчёт по отчётам — PASS")
