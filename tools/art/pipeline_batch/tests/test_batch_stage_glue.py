"""Клей этапов 1a–2 на синтетике: finish_second (строки "null"), rebg (ровный фон), make_tasks / make_1c (шаблоны
скилла), prep_1b (кто готов к 1b), post_1b / post_h2 (--dry-run, рамки частей), tripo_log (команда журнала).

    python -m pytest tools/art/pipeline_batch/tests/test_batch_stage_glue.py -q
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
sys.path.insert(0, str(HERE))

import _batch as b  # noqa: E402
import finish_second  # noqa: E402
import make_1c  # noqa: E402
import make_tasks  # noqa: E402
import post_1b  # noqa: E402
import post_h2  # noqa: E402
import prep_1b  # noqa: E402
import rebg  # noqa: E402
import tripo_log  # noqa: E402
from batch_fixtures import SKILL_MD, make_glb  # noqa: E402


def wj(p: Path, obj):
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(obj, ensure_ascii=False, indent=1), encoding="utf-8")
    return p


def png(p: Path, color=(120, 60, 50), size=(60, 80)):
    p.parent.mkdir(parents=True, exist_ok=True)
    Image.new("RGB", size, color).save(p)
    return p


# ------------------------------------------------------------------------------------------------ finish_second
def test_clean_null_strings_and_second_card():
    card = {"clip": "null", "verdict_reason": "null", "score": 8.8, "verdict": "pass", "x": None,
            "gates": {"G-CHECKS": {"status": "PASS", "note": "null"}}, "known_issues": [{"item": "S", "frame": "null"}]}
    out = finish_second.second_card(card)
    assert out == {"score": 8.8, "verdict": "pass", "gates": {"G-CHECKS": {"status": "PASS"}},
                   "known_issues": [{"item": "S"}]}
    rw = finish_second.second_card({"verdict": "rework_blender", "verdict_reason": "D < 1"})
    assert rw["verdict_reason"] == "D < 1"  # у не-pass причина остаётся


def test_finish_second_main(tmp_path, monkeypatch, capsys):
    ev = tmp_path / "art/x/evidence/acceptance/r1"
    wj(ev / "card.json", {"score": 8.1})
    res = wj(tmp_path / "wf.json", {"result": [{"asset": "ASSET-X-001", "evidence": "art/x/evidence/acceptance/r1",
                                                "card": {"score": 8.8, "verdict": "pass", "verdict_reason": "null"}}]})
    assert finish_second.main([str(res), "--repo", str(tmp_path), "--dry-run"]) == 0
    assert not (ev / "card-2.json").exists() and '"card_2"' in capsys.readouterr().out
    calls = []

    def fake_run(args, cwd):
        calls.append(args)
        wj(ev / "final.json", {"score": 8.1, "verdict": "pass"})
        return type("R", (), {"returncode": 0, "stdout": "pass\n", "stderr": ""})()

    monkeypatch.setattr(b, "run", fake_run)
    assert finish_second.main([str(res), "--repo", str(tmp_path)]) == 0
    assert json.loads((ev / "card-2.json").read_text(encoding="utf-8")) == {"score": 8.8, "verdict": "pass"}
    assert "--second" in calls[0] and calls[0][-1] == "--print-verdict"
    assert finish_second.main([str(tmp_path / "missing.json")]) == 2


def test_finish_second_accepts_bare_list_and_other_shapes(tmp_path, monkeypatch):
    """C35: возврат workflow / журнал — голый список; уведомление — {"result": [...]} или строка JSON в result."""
    item = {"asset": "ASSET-X-001", "evidence": "art/x/evidence/acceptance/r1",
            "card": {"score": 8.1, "verdict": "pass", "verdict_reason": None}}
    for shape in ([item], {"result": [item]}, {"result": json.dumps([item])}, item):
        assert finish_second.results_of(shape) == [item]
    for bad in ({"x": 1}, [{"asset": "a"}], "text", {"result": {"no": "list"}}):
        try:
            finish_second.results_of(bad)
        except ValueError:
            continue
        raise AssertionError(f"accepted {bad!r}")
    ev = tmp_path / "art/x/evidence/acceptance/r1"
    wj(ev / "card.json", {"score": 8.1})
    monkeypatch.setattr(b, "run", lambda args, cwd: (wj(ev / "final.json", {"score": 8.1, "verdict": "pass"}),
                                                     type("R", (), {"returncode": 0, "stdout": "", "stderr": ""})())[1])
    bare = tmp_path / "journal-return.json"
    bare.write_text("﻿" + json.dumps([item]), encoding="utf-8")  # BOM от PowerShell Out-File тоже читается
    assert finish_second.main([str(bare), "--repo", str(tmp_path)]) == 0
    assert json.loads((ev / "card-2.json").read_text(encoding="utf-8")) == {"score": 8.1, "verdict": "pass"}
    wj(tmp_path / "bad.json", {"items": []})
    assert finish_second.main([str(tmp_path / "bad.json"), "--repo", str(tmp_path)]) == 2


SECOND_ACCEPTOR_JS = b.REPO / ".claude/workflows/second-acceptor.js"
HARNESS = r"""
import { readFileSync } from 'node:fs'
const code = readFileSync(process.argv[2], 'utf8').replace(/^export const meta/m, 'const meta')
const args = JSON.parse(readFileSync(process.argv[3], 'utf8'))
const calls = []
const AsyncFunction = Object.getPrototypeOf(async function () {}).constructor
const run = new AsyncFunction('args', 'phase', 'parallel', 'agent', code)
try {
  const res = await run(args, () => {}, async fs => Promise.all(fs.map(f => f())),
                        async (prompt, opts) => { calls.push({ prompt, opts }); return { kind: 'card' } })
  console.log(JSON.stringify({ res, calls }))
} catch (e) { console.log(JSON.stringify({ error: String(e.message) })) }
"""


def run_workflow(tmp_path: Path, args: dict) -> dict:
    import shutil
    import subprocess

    node = shutil.which("node")
    if not node:
        import pytest
        pytest.skip("node не найден")
    h, a = tmp_path / "harness.mjs", tmp_path / "args.json"
    h.write_text(HARNESS, encoding="utf-8")
    a.write_text(json.dumps(args), encoding="utf-8")
    r = subprocess.run([node, str(h), str(SECOND_ACCEPTOR_JS), str(a)], capture_output=True, text=True,
                       encoding="utf-8", timeout=60)
    assert r.returncode == 0, r.stderr
    return json.loads(r.stdout.strip().splitlines()[-1])


def test_second_acceptor_workflow_prompt_per_card_kind(tmp_path):
    """C10: вид карточки — из args.kind или enum схемы; кадры и id пунктов — своего вида, не модели."""
    sys.path.insert(0, str(b.REPO / "tools/art/acceptance"))
    import _output_schema as osch

    for kind, letters, frames in (("model", "S, F, T or D", "frames/frames.json#files"),
                                  ("concept", "S, C, Q or P, or the gate id G-CHECKS", "images are not attached"),
                                  ("anim", "R, C, D or L", "frames.files named in the prompt file")):
        args = osch.workflow_args(kind, [{"asset": "ASSET-X-001", "evidence": "art/x/evidence/acc/20261014-r1"}])
        args.pop("kind")  # вид выводится из схемы
        out = run_workflow(tmp_path, args)
        assert len(out["calls"]) == 1 and out["res"][0]["evidence"] == "art/x/evidence/acc/20261014-r1"
        p = out["calls"][0]["prompt"]
        assert f"card kind: {kind}" in p and letters in p and frames in p, p
        assert "art/x/evidence/acc/20261014-r1/acceptor-prompt-2.md" in p
        assert 'session_id = "workflow:acceptor2-ASSET-X-001-r1"' in p
        assert out["calls"][0]["opts"]["schema"] == args["schema"]
    old = run_workflow(tmp_path, {"items": [{"asset": "A", "evidence": "e", "label": "l"}],
                                  "schema": {"type": "object"}})  # старый вызов без kind — модель
    assert "card kind: model" in old["calls"][0]["prompt"]
    bad = run_workflow(tmp_path, {"kind": "concept", "items": [{"asset": "A", "evidence": "e", "label": "l"}],
                                  "schema": osch.build("model")})
    assert "does not match" in bad["error"]


# --------------------------------------------------------------------------------------------------------- rebg
def test_rebg_flattens_studio_floor_keeps_figure(tmp_path):
    w, h = 300, 400
    yy, xx = np.mgrid[0:h, 0:w]
    bg = np.stack([90 + 40 * (yy / h) + 10 * (xx / w)] * 3, -1)  # градиент «пола» и виньетка студии
    im = Image.fromarray(bg.clip(0, 255).astype(np.uint8))
    d = ImageDraw.Draw(im)
    d.rectangle([120, 100, 180, 330], fill=(170, 40, 40))  # фигура
    d.ellipse([90, 320, 210, 350], fill=(60, 55, 50))  # подставка
    src, dst = tmp_path / "raw.png", tmp_path / "out.png"
    im.save(src)
    assert rebg.main([str(src), str(dst)]) == 0
    out = np.asarray(Image.open(dst).convert("RGB")).astype(int)
    for y, x in ((5, 5), (5, w - 6), (h - 6, 5), (h - 6, w - 6), (60, 40)):
        assert np.abs(out[y, x] - rebg.BG).max() <= 2, (y, x, out[y, x])  # фон ровный
    assert np.abs(out[200, 150] - (170, 40, 40)).max() <= 3  # фигура не тронута
    assert rebg.main([str(tmp_path / "none.png"), str(dst)]) == 2


# ------------------------------------------------------------------------------------------ make_tasks / make_1c
def skill_repo(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    (repo / b.SKILL).parent.mkdir(parents=True)
    (repo / b.SKILL).write_text(SKILL_MD, encoding="utf-8")
    png(repo / make_tasks.QREF)
    return repo


ROSTER = [["test-hero", "TestHero", "hero", "right", "A test hero.", "sword in the RIGHT hand",
           [["red", "#AA0000"], ["blue", "#0000AA"]], ["gold", "#C8A040"]]]


def test_make_tasks_writes_card_palette_task(tmp_path):
    repo = skill_repo(tmp_path)
    roster = wj(tmp_path / "roster.json", ROSTER)
    tasks = tmp_path / "work/tasks.txt"
    assert make_tasks.main(["--roster", str(roster), "--tasks-out", str(tasks), "--date", "2026-10-14",
                            "--repo", str(repo)]) == 0
    aid = "ASSET-TEST-HERO-001"
    card = (repo / f"art/pipeline-candidates/{aid}/asset-card.yaml").read_text(encoding="utf-8")
    assert b.scalar(card, "KEY") == "TestHero" and b.scalar(card, "WEAPON_HAND") == "right"
    task = (repo / f"docs/game-design/visual/06-tasks/prompts/{aid}-concept.codex.md").read_text(encoding="utf-8")
    assert "{{" not in task and "PACKAGE ASSET-TEST-HERO-001" in task and "RIGHT hand" in task
    assert b.sha256(repo / f"art/pipeline-candidates/{aid}/asset-card.yaml") in task
    assert tasks.read_text(encoding="utf-8").strip().endswith(f"{aid}-concept.codex.md")
    # существующая заявка без --force не перезаписывается
    assert make_tasks.main(["--roster", str(roster), "--tasks-out", str(tasks), "--repo", str(repo)]) == 0
    assert len(tasks.read_text(encoding="utf-8").splitlines()) == 1


def test_make_tasks_decided_by_mapping_and_palette_asset_id(tmp_path):
    """C27: decided_by — один блок-отображение по полям (SKILL.md §7.2); C13: palette.json несёт asset_id (§4.5)."""
    repo = skill_repo(tmp_path)
    roster = wj(tmp_path / "roster.json", ROSTER)
    assert make_tasks.main(["--roster", str(roster), "--tasks-out", str(tmp_path / "t.txt"), "--date", "2026-10-14",
                            "--repo", str(repo)]) == 0
    aid = "ASSET-TEST-HERO-001"
    card = (repo / f"art/pipeline-candidates/{aid}/asset-card.yaml").read_text(encoding="utf-8")
    assert card.count("decided_by:") == 1 and "decided_by: delegated" not in card
    assert '  "SIDE_VIEW": "delegated (ВР-реестр 2026-10-06)"' in card
    pal = json.loads((repo / "art/imagegen/concept-test-hero-codex/palette.json").read_text(encoding="utf-8"))
    assert list(pal)[0] == "asset_id" and pal["asset_id"] == aid and pal["accent"]["hex"] == "#C8A040"
    try:
        import yaml
    except ImportError:
        return
    y = yaml.safe_load(card)
    assert isinstance(y["decided_by"], dict) and set(y["decided_by"]) == set(make_tasks.DELEGATED_FIELDS)
    assert y["ASSET_ID"] == aid and y["WEAPON_HAND"] == "right"


def test_make_tasks_template_drift_and_bad_roster(tmp_path):
    repo = skill_repo(tmp_path)
    (repo / b.SKILL).write_text(SKILL_MD.replace("{{ASPECT_EN}}", "{{NEW_FIELD_EN}}"), encoding="utf-8")
    roster = wj(tmp_path / "roster.json", ROSTER)
    assert make_tasks.main(["--roster", str(roster), "--tasks-out", str(tmp_path / "t.txt"), "--repo", str(repo),
                            "--dry-run"]) == 2
    bad = wj(tmp_path / "bad.json", [dict(zip(make_tasks.FIELDS, ROSTER[0]), weapon_hand="both")])
    assert make_tasks.main(["--roster", str(bad), "--tasks-out", str(tmp_path / "t.txt"), "--repo", str(repo)]) == 2


def test_live_skill_templates_fill():
    """Контракт с живым скиллом: блоки §5.4/§6.1/§6.2/§8.1/§8.2 есть и заполняются полями инструментов."""
    text = (b.REPO / b.SKILL).read_text(encoding="utf-8")
    pkg, tpl, core = make_tasks.extract(text)
    row = make_tasks.roster_rows(ROSTER)[0]
    m = make_tasks.task_mapping(row, "ASSET-TEST-HERO-001", "art/x", "2026-10-14", "0" * 64, make_tasks.QREF, "0" * 64,
                                "0" * 64, 2)
    m["B_CONCEPT_PACKAGE"], m["CORE_1A"] = b.fill(pkg, m), b.fill(core, m)
    assert "{{" not in b.fill(tpl, m)
    assert all(make_1c.templates(text))


def test_make_1c_builds_views_task(tmp_path):
    repo = skill_repo(tmp_path)
    aid, k = "ASSET-TEST-HERO-001", "test-hero"
    A = repo / f"art/pipeline-candidates/{aid}"
    A.mkdir(parents=True)
    (A / "asset-card.yaml").write_text(f'ASSET_ID: {aid}\nCONTENT_KEY: {k}\nWEAPON_HAND: right\nSIDE_VIEW: left\n'
                                       'ANATOMY: humanoid\nDESCRIPTION_EN: "Desc."\nANCHORS_EN: "Anchors."\n',
                                       encoding="utf-8")
    orth = A / "20261014-draft-tripo/orthos"
    for v in ("front", "left", "back", "right"):
        png(orth / f"ortho_{v}.png")
    wj(orth / "ortho-framing.json", {"placement_pct": {"figure_top_y": 4.21, "base_top_y_est": 88.0,
                                                        "base_bottom_y": 93.4},
                                     "views": {v: {"base_width_pct": 50.0} for v in ("front", "left", "back")}})
    P = repo / f"art/imagegen/concept-{k}-codex"
    wj(P / "palette.json", {"main": [{"name": "red", "hex": "#AA0000"}], "accent": {"name": "gold", "hex": "#C8A040"}})
    png(P / f"design/{k}-front.png")
    wj(P / "generation-records.json", [{"stage": "1c", "view": "side"}] * 3)
    assert make_1c.allowed_generations(json.loads((P / "generation-records.json").read_text())) == \
        {"front": 2, "side": 1, "back": 2}
    t1, t2 = tmp_path / "w/t1c.txt", tmp_path / "w/ust.txt"
    assert make_1c.main(["--tasks-out", str(t1), "--ust-out", str(t2), "--date", "2026-10-14", "--repo", str(repo)]) == 0
    text = (repo / f"docs/game-design/visual/06-tasks/prompts/{aid}-concept-views.codex.md").read_text(encoding="utf-8")
    assert "{{" not in text and "front 2, side 1, back 2" in text
    assert "SIDE: LEFT SIDE |" in text and "pedestal x25.0%-75.0%, pedestal top y88.0%" in text and "top y4.2%" in text
    assert "ortho_left.png" in text and t1.read_text(encoding="utf-8").count("concept-views") == 1
    assert t2.read_text(encoding="utf-8") == ""
    assert make_1c.main(["--tasks-out", str(t1), "--ust-out", str(t2), "--repo", str(repo)]) == 0  # уже есть — пропуск
    assert t1.read_text(encoding="utf-8").count("concept-views") == 1


def hero_1c_repo(tmp_path: Path, hand="right", skill_text=None) -> tuple[Path, str]:
    repo = skill_repo(tmp_path)
    if skill_text is not None:
        (repo / b.SKILL).write_text(skill_text, encoding="utf-8")
    aid, k = "ASSET-TEST-HERO-001", "test-hero"
    A = repo / f"art/pipeline-candidates/{aid}"
    A.mkdir(parents=True)
    (A / "asset-card.yaml").write_text(f'ASSET_ID: {aid}\nCONTENT_KEY: {k}\nWEAPON_HAND: {hand}\nSIDE_VIEW: left\n'
                                       'ANATOMY: humanoid\nDESCRIPTION_EN: "Desc."\nANCHORS_EN: "Anchors."\n',
                                       encoding="utf-8")
    orth = A / "20261014-draft-tripo/orthos"
    for v in ("front", "left", "back"):
        png(orth / f"ortho_{v}.png")
    wj(orth / "ortho-framing.json", {"placement_pct": {"figure_top_y": 4.21, "base_top_y_est": 88.0,
                                                        "base_bottom_y": 93.4},
                                     "views": {v: {"base_width_pct": 50.0} for v in ("front", "left", "back")}})
    P = repo / f"art/imagegen/concept-{k}-codex"
    wj(P / "palette.json", {"asset_id": aid, "main": [{"name": "red", "hex": "#AA0000"}],
                            "accent": {"name": "gold", "hex": "#C8A040"}})
    png(P / f"design/{k}-front.png")
    return repo, aid


def test_make_1c_on_live_skill_template(tmp_path):
    """Живой шаблон 8.1/8.2/5.4: C5 (нет имени скилла в шапке, запрет скиллов), C6 (допуски рамки и фона по
    check_concept_views), C7 (материал подставки в CORE), C12 (история 1a дописывается), C13 (нет «.;»)."""
    live = (b.REPO / b.SKILL).read_text(encoding="utf-8")
    for hand in ("right", "none"):
        sub = tmp_path / hand
        sub.mkdir()
        repo, aid = hero_1c_repo(sub, hand, live)
        assert make_1c.main(["--tasks-out", str(sub / "t.txt"), "--ust-out", str(sub / "u.txt"), "--date", "2026-10-14",
                             "--repo", str(repo)]) == 0
        text = (repo / f"docs/game-design/visual/06-tasks/prompts/{aid}-concept-views.codex.md").read_text(encoding="utf-8")
        assert "{{" not in text and "3d-model-pipeline skill" not in text.split("## Task")[0]
        assert "Do not load or read skills" in text and "npx openskills" in text
        assert "PASS or WARN there means these CHECKLIST items pass" in text
        assert text.count(make_1c.PEDESTAL_1C) == 3  # в ядре каждого из трёх видов
        assert "keep the earlier sections below unchanged" in text and "previous_runs" in text
        assert ".;" not in text
        line = next(ln for ln in text.splitlines() if ln.startswith("- weapon side:"))
        if hand == "right":
            assert line == ("- weapon side: front and side - The weapon is held in the figure's own RIGHT hand, which "
                            "appears on the viewer's LEFT in the front view; back - The weapon in the figure's own "
                            "RIGHT hand appears on the viewer's RIGHT;")
        else:
            assert line == "- weapon side: front and side - No weapon or held object; back - No weapon or held object;"
        # ядра видов держат полные предложения (с точкой)
        assert "PALETTE: red #AA0000, accent gold #C8A040. " in text
    assert make_1c.PEDESTAL_1C in live  # строка таблицы §8.2 и константа инструмента не разошлись


# ------------------------------------------------------------------------------------------------------ prep_1b
def test_prep_1b_accepted_and_card_additions(tmp_path):
    acc = tmp_path / "acc"
    assert prep_1b.accepted(acc) is None
    wj(acc / "r1/card.json", {"verdict": "pass", "score": 8.4})
    assert prep_1b.accepted(acc) is None  # pass ниже 8,5 — нужен второй приёмщик
    wj(acc / "r1/final.json", {"verdict": "pass"})
    assert prep_1b.accepted(acc) == "pair-pass"
    wj(acc / "r2/card.json", {"verdict": "pass", "score": 9.0})
    assert prep_1b.accepted(acc) == "pass"
    wj(acc / "u/user-decision.json", {})
    assert prep_1b.accepted(acc) == "user-decision"
    add = prep_1b.card_additions("KEY: X\nCREDITS:\n  ledger: x\n", "AN-200", "нет лимита")
    assert add[0].startswith("POLY_BUDGET") and add[-1] == 'VISUAL_CARD_ID: "AN-200"' and len(add) == 2
    assert prep_1b.next_an([["id"], ["AN-07"], ["AN-144"], ["ART-3"], []]) == 145


def test_prep_1b_dry_run_plan(tmp_path, capsys):
    repo = tmp_path / "repo"
    (repo / "docs/game-design/visual/06-tasks").mkdir(parents=True)
    (repo / "docs/game-design/visual/06-tasks/anim.csv").write_text("id,area,title\nAN-10,anim,x\n", encoding="utf-8")
    for k, score, role in (("alpha", 9.0, "hero"), ("beta", 7.0, "hero"), ("gamma", 9.2, "sidekick")):
        aid = b.asset_id(k)
        png(repo / f"art/imagegen/concept-{k}-codex/design/{k}-front.png")
        (repo / f"art/pipeline-candidates/{aid}").mkdir(parents=True)
        (repo / f"art/pipeline-candidates/{aid}/asset-card.yaml").write_text(
            f"KEY: {k.title()}\nGAME_ROLE: {role}\nANATOMY: humanoid\n", encoding="utf-8")
        wj(repo / f"art/pipeline-candidates/{aid}/evidence/acceptance-concept/r1/card.json",
           {"verdict": "pass", "score": score})
    assert prep_1b.main(["--queue-out", str(tmp_path / "q.json"), "--date", "20261014", "--repo", str(repo),
                         "--dry-run"]) == 0
    plan = json.loads(capsys.readouterr().out)
    assert [q["key"] for q in plan["queue"]] == ["alpha", "gamma"] and plan["new_anim_rows"] == ["AN-11", "AN-12"]
    assert not (tmp_path / "q.json").exists()
    assert "AN-11" not in (repo / "docs/game-design/visual/06-tasks/anim.csv").read_text(encoding="utf-8")


# ---------------------------------------------------------------------------------------------- post_1b / post_h2
def hero_repo(tmp_path: Path, k="test-hero") -> Path:
    repo = tmp_path / "repo"
    A = repo / f"art/pipeline-candidates/{b.asset_id(k)}"
    A.mkdir(parents=True)
    (A / "asset-card.yaml").write_text("SIDE_VIEW: left\nANATOMY: winged-biped\nVISUAL_CARD_ID: \"AN-200\"\n",
                                       encoding="utf-8")
    for v in ("front", "side", "back"):
        png(repo / f"art/imagegen/concept-{k}-codex/{k}-{v}.png")
    png(repo / f"art/imagegen/concept-{k}-codex/design/{k}-front.png")
    return repo


def test_post_1b_dry_run(tmp_path, capsys):
    repo = hero_repo(tmp_path)
    dl = tmp_path / "Downloads/model.glb"
    dl.parent.mkdir()
    dl.write_bytes(make_glb({"p": [[0, 0, 0], [1, 1, 1], [0, 1, 0]]}))
    assert post_1b.main(["test-hero", "2f8580c9-aaaa", str(dl), "100", "70", "--date", "20261014", "--repo", str(repo),
                         "--dry-run"]) == 0
    plan = json.loads(capsys.readouterr().out)
    assert plan["container"] == "OK" and plan["aspect"] == "4:3" and plan["dst"].endswith("test-hero-draft-tripo-2f8580c9.glb")
    assert dl.exists()  # в --dry-run не перенесён
    dl.write_bytes(dl.read_bytes() + b"junk")
    assert post_1b.main(["test-hero", "2f8580c9-aaaa", str(dl), "100", "70", "--repo", str(repo), "--dry-run"]) == 1
    spec = post_1b.draft_spec(aid="ASSET-TEST-HERO-001", k="test-hero", task="2f8580c9-aaaa", dst_rel="x.glb",
                              glb_sha="s", glb_bytes=3, g={"mesh_count": 1, "triangles": 1, "materials": 0, "images": 0,
                                                           "skins": 0}, front_rel="f.png", front_sha="fs",
                              date_iso="2026-10-14", quoted=30, before=100, after=70, report_rel="r.json")
    assert spec["source_id"] == "tripo-2f8580c9-draft" and spec["operations"][0]["credits"]["observed_debit"] == 30


def test_post_h2_dry_run_part_boxes(tmp_path, capsys):
    repo = hero_repo(tmp_path)
    src = repo / "art/pipeline-candidates/ASSET-TEST-HERO-001/20261014-h2-tripo/source"
    src.mkdir(parents=True)
    parts = {"tripo_part_0": [[0, 0, 0], [0.2, 0.55, 0.1], [0.1, 0.3, 0]], "tripo_part_1": [[0.3, 0.1, 0], [0.4, 0.5, 0], [0.35, 0.2, 0]]}
    (src / "test-hero-h2-tripo-b467cd91-parts2.glb").write_bytes(make_glb(parts))
    (src / "test-hero-h2-tripo-b467cd91-tex8k-pbr.glb").write_bytes(make_glb(parts))
    args = ["test-hero", "b467cd91-0000", "--gen", "500", "440", "--tex", "440", "410", "--pbr", "410", "405",
            "--date", "20261014", "--repo", str(repo)]
    assert post_h2.main(args + ["--dry-run"]) == 0
    plan = json.loads(capsys.readouterr().out)
    assert plan["mesh_count"] == [2, 2] and [p["node"] for p in plan["parts"]] == ["tripo_part_0", "tripo_part_1"]
    assert plan["parts"][0]["max"] == [0.2, 0.55, 0.1] and plan["parts"][1]["min"][1] == 0.1
    (src / "test-hero-h2-tripo-b467cd91-tex8k-pbr.glb").unlink()
    assert post_h2.main(args + ["--dry-run"]) == 2
    ops = post_h2.operations(type("A", (), {"gen": [500, 440], "tex": [440, 410], "pbr": [410, 405], "gen_quoted": 60,
                                            "tex_quoted": 30, "pbr_quoted": 5})(), "r.json")
    assert [o["credits"]["observed_debit"] for o in ops] == [60, 30, 5]


# ---------------------------------------------------------------------------------------------------- tripo_log
def test_tripo_log_command(tmp_path, capsys):
    q = wj(tmp_path / "q.json", [{"key": "test-hero", "an": "AN-200"}])
    assert tripo_log.main(["test-hero", "2f8580c9-aaaa", "100", "70", "--queue", str(q), "--date", "20261014",
                           "--dry-run"]) == 0
    cmd = json.loads(capsys.readouterr().out)["cmd"]
    i = cmd.index("--task")
    assert cmd[i + 1] == "AN-200" and cmd[cmd.index("--before") + 1] == "100" and cmd[cmd.index("--after") + 1] == "70"
    assert cmd[cmd.index("--result") + 1] == "art/pipeline-candidates/ASSET-TEST-HERO-001/20261014-draft-tripo/source/"
    assert "add" in cmd and cmd[cmd.index("--service") + 1] == "Tripo"
    assert tripo_log.main(["other", "t", "1", "0", "--queue", str(q), "--dry-run"]) == 2  # нет в очереди
    assert tripo_log.main(["test-hero", "t", "1", "0", "--dry-run"]) == 2  # нет ни --an, ни --queue
    capsys.readouterr()
