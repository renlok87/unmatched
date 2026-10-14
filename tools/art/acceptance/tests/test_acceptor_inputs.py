"""Тесты acceptor_inputs.py (W2-d: F152, F147, RA-10, F38, F99): выдержка входов приёмщика без заметок исполнителя.

    python -m pytest tools/art/acceptance/tests/test_acceptor_inputs.py -q
"""
import json
import sys
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))

import acceptor_inputs as ai  # noqa: E402

PILOT = [
    "art/pipeline-candidates/ASSET-ACHILLES-001/evidence/acceptance/20261014-r3",
    "art/pipeline-candidates/ASSET-ANCIENT-LESHEN-001/evidence/acceptance/20261014-r3",
    "art/pipeline-candidates/ASSET-ANGEL-001/evidence/acceptance/20261013-r1",
]


def note_values(obj, out=None):
    """Строки-значения ключей-заметок (note, *_note, history …) на любой глубине."""
    out = [] if out is None else out
    if isinstance(obj, dict):
        for k, v in obj.items():
            if ai.NOTE_KEY.search(str(k)):
                if isinstance(v, str):
                    out.append(v)
                else:
                    out.extend(s for s in json.dumps(v, ensure_ascii=False).split('"') if len(s) > 30)
            else:
                note_values(v, out)
    elif isinstance(obj, list):
        for v in obj:
            note_values(v, out)
    return out


def test_strip_notes_any_depth():
    src = {"meshes": {"body": "SK_X_Body", "note": "исполнитель"}, "status_note": "r3",
           "rig": {"junctions": [{"parts": [1, 2], "note": "кромка"}], "weights_note": "w"},
           "history": {"previous_profiles": []}, "NOTES": "x", "keep": [{"a": 1, "comment": "c"}]}
    assert ai.strip_notes(src) == {"meshes": {"body": "SK_X_Body"}, "rig": {"junctions": [{"parts": [1, 2]}]},
                                   "keep": [{"a": 1}]}


@pytest.mark.parametrize("e", PILOT)
def test_pilot_excerpt_has_no_executor_notes(e):
    """F152: на профилях пилота в выдержке нет ни ключей-заметок, ни их текста (bake-профиль, заявка)."""
    frames = ai.REPO / e / "frames"
    if not (frames / "frames.json").is_file():
        pytest.skip("нет кадров пилота %s" % e)
    data = ai.build(frames)
    dump = json.dumps(data, ensure_ascii=False)
    prof = json.loads((ai.REPO / data["g_names"]["bake_profile"]["path"]).read_text(encoding="utf-8"))
    notes = [s for s in note_values(prof) if len(s) > 30]
    assert len(notes) > 10  # профили пилота действительно несут заметки исполнителя (F147)
    leaked = [s[:60] for s in notes if s in dump]
    assert not leaked, leaked
    card_text = (ai.REPO / data["sources"]["asset_card"]["path"]).read_text(encoding="utf-8")
    import yaml
    card_notes = [v for k, v in yaml.safe_load(card_text).items() if ai.NOTE_KEY.search(k) and isinstance(v, str)]
    assert all(s not in dump for s in card_notes)
    g = data["g_names"]
    assert set(g["bake_profile"]) == {"path", "sha256", "meshes", "materials.atlas", "exports.fbx_preset",
                                      "scale.figure_top_m"}
    assert g["UE_NAMES"]["skeletal_mesh"].startswith("SK_") and isinstance(g["height"]["body_top_m"]["value"], float)
    assert data["team_accent"]["report"].endswith("reports/ld-team-accent-report.json")
    assert data["team_accent"]["texture_sha256"] in [o["sha256"] for o in
                                                    json.loads((frames / "frames.json").read_text("utf-8"))[
                                                        "accepted_object"]]
    assert data["anchors"] and not data["warnings"]
    assert all("{{" not in v for v in data["placeholders"].values())


def test_pilot_leshen_height_rule_uses_bounds_top():
    frames = ai.REPO / PILOT[1] / "frames"
    if not (frames / "frames.json").is_file():
        pytest.skip("нет кадров пилота Leshen")
    rule = ai.build(frames)["placeholders"]["HEIGHT_RULE"]
    assert "FIGURE_BOUNDS_TOP_M 0.7358" in rule and "SK_AncientLeshen_H2_Body" in rule


# ------------------------------------------------------------------ синтетический ассет (без живых данных)

def _w(p, data):
    p.parent.mkdir(parents=True, exist_ok=True)
    if isinstance(data, (dict, list)):
        data = json.dumps(data, ensure_ascii=False)
    p.write_text(data, encoding="utf-8")
    return p


@pytest.fixture
def asset(tmp_path, monkeypatch):
    monkeypatch.setattr(ai, "REPO", tmp_path)
    A = tmp_path / "art/pipeline-candidates/ASSET-X-001"
    _w(A / "asset-card.yaml", "ASSET_ID: ASSET-X-001\nNOTES: заметка заявки не для приёмщика\n"
                              "ANCHORS: old\nANCHORS_EN: \"horns; axe in the RIGHT hand\"\n"
                              "FIGURE_HEIGHT_M: 0.55\nFIGURE_BOUNDS_TOP_M: 0.70\n"
                              "UE_NAMES: {stage: H2LD, skeletal_mesh: SK_X_H2LD, base: SM_X_H2LD_Base}\n")
    prof = {"status_note": "ИСПОЛНИТЕЛЬ: r2 закрыл всё", "meshes": {"body": "SK_X_H2_Body", "weapon": "SK_X_H2_Axe"},
            "materials": {"atlas": "M_X_H2_Atlas", "slots_note": "ИСПОЛНИТЕЛЬ: слот"},
            "exports": {"fbx_preset": "UM_FBX_v1.json"}, "scale": {"figure_top_m": 0.55},
            "rig": {"junctions": [{"note": "ИСПОЛНИТЕЛЬ: кромка"}], "weights_note": "ИСПОЛНИТЕЛЬ: веса"}}
    _w(A / "build-profiles/x-bake.json", prof)
    LD = A / "20261014-h2-lookdev-r2"
    _w(LD / "export/SK_X_H2LD.fbx", "fbx")
    _w(LD / "textures/T_X_H2LD_TeamAccent_2K.png", "ta")
    ta_sha = ai.sha256(LD / "textures/T_X_H2LD_TeamAccent_2K.png")
    _w(LD / "reports/run-manifest.json", {"asset_id": "ASSET-X-001",
                                          "source_profile": {"path": "art/pipeline-candidates/ASSET-X-001/build-profiles/x-bake.json",
                                                             "sha256": ai.sha256(A / "build-profiles/x-bake.json")},
                                          "source_run": {"path": "art/pipeline-candidates/ASSET-X-001/20261014-h2-bake-r2"}})
    _w(LD / "reports/ld-fbx-report.json", {"roundtrip": {"ld": {"skeletal": {"meshes": {
        "SK_X_H2_Body": {"bounds_m": {"max": [0.1, 0.1, 0.7001]}}, "SK_X_H2_Axe": {"bounds_m": {"max": [0, 0, 0.61]}}}}}}})
    _w(A / "20261014-h2-bake-r2/reports/rig-report.json",
       {"checks": {"unit_scale_1_and_height": {"measured": {"skeletal_top_cm": 70.01}}}})
    # отдельный прогон TeamAccent (F38): своего отчёта у look-dev нет
    _w(A / "20261014-h2-lookdev-teamaccent-b/reports/ld-team-accent-report.json",
       {"passed": True, "outputs": {"T_X_H2LD_TeamAccent_2K.png": {"sha256": ta_sha}},
        "pins": {"lookdev_run:2K_MatID": {"path": "art/pipeline-candidates/ASSET-X-001/20261014-h2-lookdev-r2/textures/T_X_H2LD_2K_MatID.png"}}})
    _w(A / "20261013-h2-lookdev-teamaccent-a/reports/ld-team-accent-report.json",
       {"passed": True, "outputs": {"T_X_H2LD_TeamAccent_2K.png": {"sha256": "0" * 64}}, "pins": {}})
    E = A / "evidence/acceptance"
    _w(E / "20261014-r2/frames/frames.json", {"inputs": {"fbx": {"path": "art/pipeline-candidates/ASSET-X-001/20261014-h2-lookdev-r2/export/SK_X_H2LD.fbx"}},
                                               "accepted_object": [{"path": "art/pipeline-candidates/ASSET-X-001/20261014-h2-lookdev-r2/textures/T_X_H2LD_TeamAccent_2K.png",
                                                                    "sha256": ta_sha}]})
    _w(E / "20261013-r1/card.json", {"cycle": "r1", "rework_fix_list": []})
    _w(E / "20261013-r1/card-2.json", {"cycle": "r1", "known_issues": [],
                                        "rework_fix_list": [{"item": "F", "frame": "close-head.jpg", "fix": "закрыть щель",
                                                             "tool": "closure"}]})
    _w(E / "20261013-r1/final.json", {"source_card": str(E / "20261013-r1/card-2.json")})
    return E / "20261014-r2/frames"


def test_synthetic_excerpt(asset):
    d = ai.build(asset)
    dump = json.dumps(d, ensure_ascii=False)
    assert "ИСПОЛНИТЕЛЬ" not in dump and "заметка заявки" not in dump
    assert d["anchors"] == "horns; axe in the RIGHT hand"          # F39: ANCHORS_EN, не ANCHORS
    ta = d["team_accent"]
    assert ta["report"].endswith("20261014-h2-lookdev-teamaccent-b/reports/ld-team-accent-report.json")
    assert ta["same_run"] is False and ta["pins_this_look_dev"] is True and len(ta["candidates"]) == 1
    assert "отдельный прогон TeamAccent" in d["placeholders"]["TA_REPORT"]
    rule = d["placeholders"]["HEIGHT_RULE"]
    assert "0.7001" in rule and "FIGURE_BOUNDS_TOP_M 0.7" in rule and "SK_X_H2_Axe" in rule
    # прежний цикл — источник пары (final.json#source_card), пункт и текст прежнего приёмщика, без tool
    assert d["prev_fix_list"]["items"] == [{"list": "rework_fix_list", "n": 1, "item": "F", "frame": "close-head.jpg",
                                            "text": "закрыть щель"}]
    assert d["placeholders"]["PREV_FIX_LIST"] == "- r1 rework_fix_list п.1 · F · close-head.jpg — закрыть щель"
    assert json.loads(d["placeholders"]["BAKE_PROFILE_KEYS"])["materials.atlas"] == "M_X_H2_Atlas"


def test_synthetic_cli_writes_next_to_frames(asset, capsys):
    assert ai.main(["--frames", str(asset), "--previous-card", "none"]) == 0
    out = json.loads((asset.parent / "acceptor-inputs.json").read_text(encoding="utf-8"))
    assert out["schema"] == ai.SCHEMA and out["prev_fix_list"]["items"] == []


def test_missing_team_accent_report_is_reported(asset):
    for p in asset.parents[3].glob("*teamaccent*/reports/ld-team-accent-report.json"):
        p.unlink()
    d = ai.build(asset)
    assert d["team_accent"]["report"] is None and "FAIL" in d["placeholders"]["TA_REPORT"]
    assert any("TeamAccent" in w for w in d["warnings"])


def test_frames_outside_look_dev_export_is_input_error(asset):
    man = json.loads((asset / "frames.json").read_text(encoding="utf-8"))
    man["inputs"]["fbx"]["path"] = "C:/tmp/SK_X.fbx"
    (asset / "frames.json").write_text(json.dumps(man), encoding="utf-8")
    with pytest.raises(ai.InputError):
        ai.build(asset)
