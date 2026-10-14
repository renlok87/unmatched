"""sheet_acceptance.py без Codex: аргументы приёмщика, разбор событий, сбой песочницы, и полная подготовка приёмки
(preflight пакета + промпт §11) на синтетическом чекауте с настоящим check_concept_views.py.

    python -m pytest tools/art/pipeline_batch/tests/test_batch_sheet_acceptance.py -q
"""
from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path

import pytest
from PIL import Image, ImageDraw

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
sys.path.insert(0, str(HERE))

import _batch as b  # noqa: E402
import sheet_acceptance as S  # noqa: E402
from batch_fixtures import SKILL_MD  # noqa: E402

K, AID = "test-hero", "ASSET-TEST-HERO-001"


def test_base_args_psq_events(tmp_path):
    a = S.base_args(Path("R"), Path("o.json"), [Path("a.png"), Path("b.png")], "gpt-6.1-sol", "xhigh")
    assert a[:2] == ["exec", "--ignore-user-config"] and a[-2:] == ["--", "-"]
    assert a.count("-i") == 2 and "--output-schema" in a and 'model_reasoning_effort="xhigh"' in a
    assert "--output-schema" not in S.base_args(Path("R"), Path("o"), [], "m", "low", schema=False)
    assert S.psq("it's") == "'it''s'"
    ev = tmp_path / "e.jsonl"
    ev.write_text('{"type": "thread.started", "thread_id": "t1"}\nnot json\n{"item": {"type": "command_execution", '
                  '"status": "failed", "aggregated_output": "helper_unknown_error"}}\n', encoding="utf-8")
    evs = S.events(ev)
    assert len(evs) == 2 and len(S.env_failures(evs)) == 1
    assert S.events(tmp_path / "missing") == []


def view_png(p: Path):
    im = Image.new("RGB", (300, 400), (40, 40, 42))
    d = ImageDraw.Draw(im)
    d.ellipse([75, 340, 225, 372], fill=(70, 65, 60))
    d.rectangle([120, 90, 180, 350], fill=(150, 60, 50))
    d.ellipse([130, 40, 170, 95], fill=(200, 170, 150))
    p.parent.mkdir(parents=True, exist_ok=True)
    im.save(p)


def make_repo(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    (repo / b.SKILL).parent.mkdir(parents=True)
    (repo / b.SKILL).write_text(SKILL_MD, encoding="utf-8")
    tool = repo / "tools/art/concept/check_concept_views.py"
    tool.parent.mkdir(parents=True)
    shutil.copy2(b.REPO / "tools/art/concept/check_concept_views.py", tool)
    qref = "art/imagegen/hero-quality-v1/reference/q.png"
    view_png(repo / qref)
    A = repo / f"art/pipeline-candidates/{AID}"
    A.mkdir(parents=True)
    (A / "asset-card.yaml").write_text(f"ASSET_ID: {AID}\nROLE: hero\nSIDE_VIEW: left\nQUALITY_REFERENCE:\n  - {qref}\n",
                                       encoding="utf-8")
    orth = A / "20261014-draft-tripo/orthos"
    for v in ("front", "left", "back"):
        view_png(orth / f"ortho_{v}.png")
    (orth / "ortho-framing.json").write_text("{}", encoding="utf-8")
    (A / "evidence/acceptance-concept/20261014-sheet-r1").mkdir(parents=True)
    p = repo / f"art/imagegen/concept-{K}-codex"
    (p / "concepts/1c").mkdir(parents=True)
    for v in ("front", "side", "back"):
        view_png(p / f"{K}-{v}.png")
        shutil.copy2(p / f"{K}-{v}.png", p / f"concepts/1c/{K}-{v}-g1.png")
    view_png(p / f"design/{K}-front.png")
    (p / "palette.json").write_text(json.dumps({"main": [{"name": "red", "hex": "#963C32"}],
                                                "accent": {"name": "gold", "hex": "#C8A040"}}), encoding="utf-8")
    (p / "prompts").mkdir()
    (p / "prompts/concept-prompts.json").write_text(json.dumps({f"1c-{v}": "PROMPT" for v in ("front", "side", "back")}),
                                                    encoding="utf-8")
    (p / "verification.json").write_text(json.dumps({"limit_reached": []}), encoding="utf-8")
    recs = []
    for v in ("front", "side", "back"):
        saved = f"art/imagegen/concept-{K}-codex/concepts/1c/{K}-{v}-g1.png"
        recs.append({"stage": "1c", "view": v, "attempt": 1, "selected": True, "prompt_key": f"1c-{v}",
                     "saved_path": saved, "sha256": b.sha256(repo / saved), "references": []})
        (p / f"checks/{v}-g1").mkdir(parents=True)
        (p / f"checks/{v}-g1/checks-report.json").write_text("{}", encoding="utf-8")
    (p / "generation-records.json").write_text(json.dumps(recs), encoding="utf-8")
    r = b.run([sys.executable, "tools/art/concept/check_concept_views.py", "--set", b.rel(p, repo), "--key", K,
               "--views", "front,side,back", "--role", "hero", "--palette", b.rel(p / "palette.json", repo), "--sheet",
               "--out", b.rel(p, repo)], repo)
    assert r.returncode == 0, r.stdout + r.stderr
    files = {f.relative_to(p).as_posix(): {"sha256": b.sha256(f), "bytes": f.stat().st_size}
             for f in p.rglob("*") if f.is_file()}
    (p / "manifest-sha256.json").write_text(json.dumps({"files": files}), encoding="utf-8")
    return repo


def args(repo: Path, work: Path, *extra):
    return ["--work", str(work), "--repo", str(repo), "--date", "2026-10-14", "--exe", "codex-not-used", *extra]


def test_prepare_builds_prompt_without_codex(tmp_path, capsys):
    repo = make_repo(tmp_path)
    work = tmp_path / "work"
    work.mkdir()
    (work / "sheet-acceptance-owned.json").write_text(json.dumps([{"asset_id": AID, "key": K, "status": "claimed",
                                                                   "package": f"art/imagegen/concept-{K}-codex"}]),
                                                      encoding="utf-8")
    assert S.main(["prepare", K, "1", *args(repo, work, "--user-quote", "проверь пачку")]) == 0
    out = json.loads(capsys.readouterr().out)
    e = repo / out["evidence"]
    assert out["images"] == 3 + 2 + 3 + 1  # виды, лист и дизайн, три орто, эталон качества
    prompt = (e / "acceptor-prompt.md").read_text(encoding="utf-8")
    assert "RUBRIC 1C TEXT" in prompt and "«проверь пачку»" in prompt and "Не знаю. Делай сам" in prompt
    const = json.loads((e / "launcher-inputs.json").read_text(encoding="utf-8"))["constants"]
    assert const["cycle"] == "r1" and const["date"] == "2026-10-14" and const["previous_card"] is None
    assert const["executor_session_id"] == "launcher:stage-1c-sheet-20261014"
    assert json.loads((e / "launcher-preflight.json").read_text(encoding="utf-8"))["recheck_same"] is True


def test_prepare_refuses_changed_package(tmp_path, capsys):
    repo = make_repo(tmp_path)
    work = tmp_path / "work"
    work.mkdir()
    (work / "sheet-acceptance-owned.json").write_text(json.dumps([{"asset_id": AID, "key": K, "status": "claimed",
                                                                   "package": f"art/imagegen/concept-{K}-codex"}]),
                                                      encoding="utf-8")
    (repo / f"art/imagegen/concept-{K}-codex/stray.json").write_text("{}", encoding="utf-8")  # вне манифеста
    assert S.main(["prepare", K, "1", *args(repo, work)]) == 2
    assert "manifest coverage" in capsys.readouterr().err
    assert S.main(["prepare", "nobody", "1", *args(repo, work)]) == 2


def test_accept_blocks_without_claimed_folder(tmp_path):
    repo = make_repo(tmp_path)
    work = tmp_path / "work"
    shutil.rmtree(repo / f"art/pipeline-candidates/{AID}/evidence/acceptance-concept/20261014-sheet-r1")
    s = S.Sheet(type("A", (), {"repo": str(repo), "work": str(work), "date": "2026-10-14", "log": None,
                               "exe": "codex-not-used", "model": "m", "effort": "low", "user_quote": []})())
    with pytest.raises(RuntimeError, match="взятого каталога"):
        s.preflight({"asset_id": AID, "key": K, "package": f"art/imagegen/concept-{K}-codex"}, 1)
