"""prompt_build.py: card row -> task file with shared blocks of 07 expanded verbatim, {{set}} filled, inputs hashed.

  python -B -m pytest -q tools/art/visual/tests
"""
import csv
import hashlib
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import prompt_build as pb  # noqa: E402
from visual_common import VisualError, repo_root  # noqa: E402

FIELDS = ["id", "area", "title", "priority", "depends_on", "purpose", "trigger", "timing", "keyframes", "states",
          "readability", "palette_tokens", "type_tokens", "references", "do", "dont", "tool", "prompt",
          "deliverable", "ue_target", "budget", "acceptance", "status"]

TEMPLATES_MD = """# 07 fake

### 0.3 Shared blocks

**[[B-STYLE]]** — style:

```text
Style: flat printed token language.
Shape first, colour third.
```

**[[B-PALETTE-CORE]]** — palette:

```text
Palette: card.navy #061623, card.cream #F9EBDB.
```

**[[B-FORBID]]** — forbidden:

```text
Forbidden: copying any commercial digital edition; red fills.
```

**[[B-PACKAGE]]** — announced here, defined in 1.1.

### 1.1 Package contract

**[[B-PACKAGE]]** (text):

```text
Package contract.
- Write ONLY inside art/imagegen/{{set}}-codex/.
```

### 1.4 T-CODEX-LAYOUT

### 2.10 T-SYNTX-UPSCALE
"""


def make_repo(tmp_path, rows):
    root = tmp_path / "repo"
    (root / "docs/game-design/visual/06-tasks").mkdir(parents=True)
    (root / "docs/game-design/visual/07-prompt-templates.md").write_text(TEMPLATES_MD, encoding="utf-8")
    with (root / "docs/game-design/visual/06-tasks/hud.csv").open("w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=FIELDS)
        w.writeheader()
        for r in rows:
            w.writerow({k: r.get(k, "") for k in FIELDS})
    (root / "docs/frames").mkdir(parents=True)
    (root / "docs/frames/k1.png").write_bytes(b"frame-k1")
    (root / "art/imagegen/icons/sizes").mkdir(parents=True)
    (root / "art/imagegen/icons/sizes/a-24.png").write_bytes(b"icon")
    return root


def card(**kw):
    base = {
        "id": "HB-90", "title": "Макет", "priority": "P1", "depends_on": "—", "tool": "Codex",
        "status": "готово к работе",
        "references": "04 §1.6; фон — docs/frames/k1.png (Marmoreal); docs/frames/missing.png; "
                      "art/imagegen/icons/sizes/",
        "deliverable": "пакет art/imagegen/demo-v1-codex/ (README); макеты scraped-data/derived/demo-v1-codex/x.png",
        "prompt": "[T-CODEX-LAYOUT] Prompt file docs/game-design/visual/06-tasks/prompts/HB-90.codex.md; insert "
                  "[[B-PACKAGE]], [[B-STYLE]], [[B-FORBID]] verbatim with set = demo-v1. Task HB-90 - Demo mockup. "
                  "[[B-PACKAGE]] Inputs: docs/frames/k1.png (" + hashlib.sha256(b"frame-k1").hexdigest()[:16] +
                  ", frame). Colours: [[B-PALETTE-CORE]] [[B-STYLE]] [[B-FORBID]] Output in "
                  "scraped-data/derived/{{set}}-codex/.",
    }
    base.update(kw)
    return base


def test_blocks_parsed_verbatim_from_markdown():
    blocks = pb.parse_blocks(TEMPLATES_MD)
    assert blocks["B-STYLE"] == "Style: flat printed token language.\nShape first, colour third."
    assert blocks["B-PACKAGE"].startswith("Package contract.\n- Write ONLY inside art/imagegen/{{set}}-codex/.")
    assert set(pb.REQUIRED_BLOCKS) <= set(blocks)


def test_missing_block_definition_fails():
    with pytest.raises(VisualError, match="B-FORBID"):
        pb.parse_blocks(TEMPLATES_MD.replace("**[[B-FORBID]]**", "**FORBID**"))


def test_conflicting_block_definitions_fail():
    md = TEMPLATES_MD + "\n**[[B-STYLE]]** again:\n\n```text\nStyle: something else.\n```\n"
    with pytest.raises(VisualError, match="defined twice"):
        pb.parse_blocks(md)


def test_build_writes_task_file(tmp_path):
    root = make_repo(tmp_path, [card()])
    out, warnings = pb.build(root, "HB-90", date="2026-10-06")
    assert out == root / "docs/game-design/visual/06-tasks/prompts/HB-90.codex.md"
    text = out.read_text(encoding="utf-8")
    # header
    assert "| id | HB-90 |" in text and "| date | 2026-10-06 |" in text
    assert "| template | T-CODEX-LAYOUT |" in text and "| set | demo-v1" in text
    # shared blocks verbatim, {{set}} filled, nothing left
    task = text.split("## Task", 1)[1]
    assert "Style: flat printed token language.\nShape first, colour third." in task
    assert "Palette: card.navy #061623, card.cream #F9EBDB." in task
    assert "- Write ONLY inside art/imagegen/demo-v1-codex/." in task
    assert "scraped-data/derived/demo-v1-codex/" in task
    assert "{{" not in text and "[[B-" not in task
    # the preamble addressed to Claude is not part of the task
    assert "Prompt file docs/game-design" not in task
    assert task.lstrip().startswith("```text\nTask HB-90 - Demo mockup.")
    # inputs from references with sha256; missing listed; directory hashed as a tree
    assert hashlib.sha256(b"frame-k1").hexdigest() in text
    assert "`docs/frames/missing.png` | missing" in text
    assert "`art/imagegen/icons/sizes/` | directory, 1 files" in text
    assert any("missing.png" in w for w in warnings)


def test_stated_hash_mismatch_is_reported(tmp_path):
    c = card(references="04 §1.6")
    c["prompt"] = c["prompt"].replace(hashlib.sha256(b"frame-k1").hexdigest()[:16], "0123456789abcdef")
    root = make_repo(tmp_path, [c])
    out, warnings = pb.build(root, "HB-90", date="2026-10-06")
    assert "MISMATCH" in out.read_text(encoding="utf-8")
    assert any("differs from the card's 0123456789abcdef" in w for w in warnings)


def test_unknown_id_fails_loudly(tmp_path, capsys):
    root = make_repo(tmp_path, [card()])
    assert pb.main(["NOPE-1", "--root", str(root)]) == 2
    assert "unknown card id 'NOPE-1'" in capsys.readouterr().err


def test_unfilled_variable_fails(tmp_path):
    c = card()
    c["prompt"] += " Title: {{title}}."
    root = make_repo(tmp_path, [c])
    with pytest.raises(VisualError, match=r"unfilled variable\(s\) \{\{title\}\}"):
        pb.build(root, "HB-90", date="2026-10-06")
    assert not (root / "docs/game-design/visual/06-tasks/prompts/HB-90.codex.md").exists()


def test_unknown_block_fails(tmp_path):
    c = card()
    c["prompt"] += " [[B-NOPE]]"
    root = make_repo(tmp_path, [c])
    with pytest.raises(VisualError, match=r"\[\[B-NOPE\]\]"):
        pb.build(root, "HB-90")


def test_set_contradiction_fails(tmp_path):
    c = card()
    c["prompt"] = c["prompt"].replace("set = demo-v1", "set = other-v2")
    root = make_repo(tmp_path, [c])
    with pytest.raises(VisualError, match="contradicts"):
        pb.build(root, "HB-90")


def test_card_without_template_tag_fails(tmp_path):
    root = make_repo(tmp_path, [card(prompt="—", tool="UE")])
    with pytest.raises(VisualError, match="no template tag"):
        pb.build(root, "HB-90")


def test_strict_inputs(tmp_path):
    root = make_repo(tmp_path, [card()])
    with pytest.raises(VisualError, match="missing.png"):
        pb.build(root, "HB-90", strict_inputs=True)


def test_syntx_template_writes_txt(tmp_path):
    c = card(prompt="[T-SYNTX-UPSCALE] Prompt file at launch: x. Task HB-90 — upscale. "
                    "Prompt: \"Upscale 2x.\" [[B-FORBID]]")
    root = make_repo(tmp_path, [c])
    out, _ = pb.build(root, "HB-90", out_dir=tmp_path / "o", date="2026-10-06")
    assert out.name == "HB-90.syntx.txt"
    assert "Forbidden: copying any commercial digital edition; red fills." in out.read_text(encoding="utf-8")


def test_real_cards_build(tmp_path):
    """The real 07 and 06-tasks parse: HB-07 (first Codex package of VS-1) builds with no placeholder left."""
    root = repo_root()
    blocks = pb.parse_blocks((root / "docs/game-design/visual/07-prompt-templates.md").read_text(encoding="utf-8"))
    assert blocks["B-STYLE"].startswith("Style: flat printed board-game token language.")
    assert "{{set}}" in blocks["B-PACKAGE"]
    for cid in ("HB-07", "IC-36", "EN-01", "SC-01"):
        out, _ = pb.build(root, cid, out_dir=tmp_path, date="2026-10-06")
        text = out.read_text(encoding="utf-8")
        task = text.split("## Task", 1)[1]
        assert "{{" not in text and "[[B-PACKAGE]]" not in task and "[[B-STYLE]]" not in task
        assert f"Task {cid}" in task
    assert "art/imagegen/hud-composition-v1-codex/" in (tmp_path / "HB-07.codex.md").read_text(encoding="utf-8")
