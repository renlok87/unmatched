"""_batch.py: скаляры заявки, плейсхолдеры, ASSET_ID, контейнер GLB и рамки частей по вершинам (F10).

    python -m pytest tools/art/pipeline_batch/tests -q
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
sys.path.insert(0, str(HERE))

import _batch as b  # noqa: E402
from batch_fixtures import SKILL_MD, make_glb  # noqa: E402

CARD = """# comment
ASSET_ID: ASSET-ACHILLES-001
KEY: Achilles
SIDE_VIEW: left            # SIDE_VIEW
DESCRIPTION_EN: "Achilles, \\"the\\" greatest: spear in the RIGHT hand"
NOTES: x
delegated:
  KEY: "nested — не верхний уровень"
"""


def test_scalar_and_asset_id():
    assert b.scalar(CARD, "KEY") == "Achilles"
    assert b.scalar(CARD, "SIDE_VIEW") == "left"
    assert b.scalar(CARD, "DESCRIPTION_EN") == 'Achilles, "the" greatest: spear in the RIGHT hand'
    assert b.scalar(CARD, "ANATOMY") == ""
    assert b.asset_id("ancient-leshen") == "ASSET-ANCIENT-LESHEN-001"
    with pytest.raises(ValueError):
        b.asset_id("Ancient Leshen")


def test_fill_and_skill_block():
    assert b.fill("{{A}} and {{B_2}}", {"A": 1, "B_2": "x"}) == "1 and x"
    with pytest.raises(KeyError):
        b.fill("{{MISSING}}", {})
    assert b.skill_block(SKILL_MD, "### 5.4 Блок B-CONCEPT-PACKAGE").startswith("PACKAGE {{ASSET_ID}}")
    tpl = b.skill_block(SKILL_MD, "### 6.1 Файл задания", "````markdown\n", "\n````")
    assert tpl.startswith("# {{ASSET_ID}} 1a") and "```text" in tpl


def test_container_ok():
    glb = make_glb({"p0": [[0, 0, 0], [1, 1, 1], [0, 1, 0]]})
    assert b.container_ok(glb)
    assert not b.container_ok(glb + b"junk")  # хвост за последним чанком
    assert not b.container_ok(glb[:-4])
    assert not b.container_ok(b"glTF")


@pytest.mark.parametrize("stride", [12, 24])
def test_part_boxes_from_vertices_not_accessor_minmax(stride):
    glb = make_glb({"tripo_part_0": [[-0.1, 0.2, 0.0], [0.1, 0.8, 0.05], [0.0, 0.5, -0.02]],
                    "tripo_part_1": [[0.3, 0.0, 0.0], [0.35, 0.55, 0.01], [0.32, 0.1, 0.0]]}, stride=stride)
    boxes = b.part_boxes(glb)
    assert [x["node"] for x in boxes] == ["tripo_part_0", "tripo_part_1"]  # узел без меша (root) пропущен
    assert boxes[0]["min"] == [-0.1, 0.2, -0.02] and boxes[0]["max"] == [0.1, 0.8, 0.05]
    assert boxes[1]["min"][1] == 0.0  # не DBL_MIN из accessor.min
    assert boxes[0]["tris"] == 1


@pytest.mark.parametrize("tool", ["codex_lane", "finish_second", "make_1c", "make_tasks", "post_1b", "post_h2", "prep_1b",
                                  "rebg", "sheet_acceptance", "tripo_log"])
def test_every_tool_has_help_and_readme_line(tool, capsys):
    mod = __import__(tool)
    assert mod.main(["--help"]) == 0
    assert "usage" in capsys.readouterr().out.lower()
    assert mod.__doc__.splitlines()[0].strip() and "C:/tmp/concept-wave" in mod.__doc__  # откуда перенесён
