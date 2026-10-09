"""Правила калибровки 2026-10-09, раунд 4 (после прогона Opus ×3 и Sol на кадрах раунда 3): кадр wire-back,
тени EEVEE в frames.json, мост G-TEX для N (ld_maps копирует N из bake и не пишет px), пример карточки §7 рубрики
проходит валидатор с --check-files против набора калибровки medusa-r1.

    python -m pytest tools/art/acceptance/tests -q
"""
import json
import re
import subprocess
import sys
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
sys.path.insert(0, str(HERE))

import capture_acceptance_set as cap  # noqa: E402
import validate_card as vc  # noqa: E402
from test_validate_card import model_card, run  # noqa: E402

SCRIPT = str(HERE.parent / "validate_card.py")
REPO = HERE.parents[3]
CALIB = REPO / "docs" / "art-pipeline" / "evidence" / "acceptance-calibration-20261009"
RUBRIC = REPO / ".agents" / "skills" / "3d-model-pipeline" / "references" / "acceptance-and-blender.md"
MEDUSA = REPO / "art" / "pipeline-candidates" / "ASSET-MEDUSA-001"


def test_wire_back_in_tool_and_validator():
    assert "wire-back.jpg" in cap.FIXED and "wire-back.jpg" in vc.MODEL_FRAMES
    # всё, что инструмент снимает у любого ассета, кроме uv-layout (PNG снимается отдельно), валидатор требует
    assert set(cap.FIXED) == set(vc.MODEL_FRAMES) - {"uv-layout.png"}


def test_card_without_wire_back_rejected():
    card = model_card()
    if "wire-back.jpg" not in card["frames"]["files"]:
        card["frames"]["files"].append("wire-back.jpg")
    assert run(card)[0] == []
    card["frames"]["files"].remove("wire-back.jpg")
    assert any("wire-back.jpg" in e for e in run(card)[0])


@pytest.mark.parametrize("run_dir", ["medusa-r1", "king-arthur-r1", "king-arthur-neg-r1"])
def test_calibration_sets_have_wire_back_and_shadows(run_dir):
    fdir = CALIB / run_dir / "frames"
    if not (fdir / "frames.json").is_file():
        pytest.skip("набор калибровки не снят")
    man = json.loads((fdir / "frames.json").read_text(encoding="utf-8"))
    assert "wire-back.jpg" in man["files"] and (fdir / "wire-back.jpg").is_file()
    wb = next(f for f in man["frames"] if f["name"] == "wire-back.jpg")
    assert wb["material"] == "wire" and wb["azimuth_deg"] == 180
    assert "тени EEVEE" in man["render"]["shadows"]


def test_gtex_bridge_for_copied_normal_map():
    """Рубрика §4: у N в ld-maps-report нет px (копия bake) — размер берётся из textures-report через pins."""
    ld = MEDUSA / "20260929-h2-lookdev" / "reports" / "ld-maps-report.json"
    tx = MEDUSA / "20260929-h2-bake" / "reports" / "textures-report.json"
    ta = MEDUSA / "20260929-h2-lookdev" / "reports" / "ld-team-accent-report.json"
    if not (ld.is_file() and tx.is_file() and ta.is_file()):
        pytest.skip("отчёты Medusa не найдены")
    ldr = json.loads(ld.read_text(encoding="utf-8"))
    txr = json.loads(tx.read_text(encoding="utf-8"))
    tar = json.loads(ta.read_text(encoding="utf-8"))
    n = ldr["outputs"]["T_Medusa_H2LD_2K_N.png"]
    assert "px" not in n and n["copied_from"] == "T_Medusa_H2_2K_N.png"
    assert ldr["pins"]["2K_N"]["sha256"] == n["sha256"]
    bake_n = txr["outputs"]["T_Medusa_H2_2K_N.png"]
    assert bake_n["px"] == [2048, 2048] and bake_n["sha256"] == n["sha256"]
    for name in ("BC", "ORM", "MatID", "Edge"):
        assert ldr["outputs"]["T_Medusa_H2LD_2K_%s.png" % name]["px"] == [2048, 2048]
    assert tar["outputs"]["T_Medusa_H2LD_TeamAccent_2K.png"]["px"] == [2048, 2048]
    rubric = RUBRIC.read_text(encoding="utf-8")
    assert "textures-report.json#outputs.T_<Key>_H2_2K_N.png.px" in rubric
    assert "ld-team-accent-report.json#outputs.T_<Key>_H2LD_TeamAccent_2K.png.px" in rubric


def rubric_example_card():
    text = RUBRIC.read_text(encoding="utf-8")
    sec7 = text[text.index("## 7. Карточка"):text.index("## 8. Проведение приёмки")]
    m = re.search(r"```json\n(\{\n  \"schema\".*?\n\})\n```", sec7, re.S)
    assert m, "пример карточки §7 не найден"
    return json.loads(m.group(1))


def test_rubric_example_card_valid_against_calibration(tmp_path):
    card = rubric_example_card()
    fdir = CALIB / "medusa-r1" / "frames"
    if not (fdir / "frames.json").is_file():
        pytest.skip("набор калибровки не снят")
    man = json.loads((fdir / "frames.json").read_text(encoding="utf-8"))
    assert sorted(card["frames"]["files"]) == sorted(man["files"])
    card["frames"]["dir"] = "docs/art-pipeline/evidence/acceptance-calibration-20261009/medusa-r1/frames"
    p = tmp_path / "card.json"
    p.write_text(json.dumps(card, ensure_ascii=False), encoding="utf-8")
    r = subprocess.run([sys.executable, SCRIPT, str(p), "--print-verdict", "--check-files"], capture_output=True,
                       text=True, encoding="utf-8", errors="replace", cwd=str(REPO))
    assert r.returncode == 0, r.stdout + r.stderr
    assert r.stdout.strip().splitlines()[-1] == "pass"
