"""sheet_acceptance.py: Opus-путь (preflight пакета + промпт §11 + аргументы workflow, приём карточки finish) на
синтетическом чекауте с настоящим check_concept_views.py; полоса Sol (codex exec) отключена 2026-10-20 — код 2.

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


def test_sol_and_zcode_paths_stop_with_a_reason(tmp_path, capsys):
    """2026-10-20: accept / all / probe и --acceptor sol — Sol отключён; --acceptor zcode — заглушка; codex не ищется."""
    work = ["--work", str(tmp_path / "w"), "--repo", str(tmp_path)]
    for argv in (["accept", K, "1"], ["all"], ["probe"], ["prepare", K, "1", "--acceptor", "sol"]):
        assert S.main(argv + work) == 2
    err = capsys.readouterr().err
    assert err.count("Sol отключён 2026-10-20") == 4 and "AI tools and side models" in err and "acceptor-args.json" in err
    assert S.main(["prepare", K, "1", "--acceptor", "zcode", *work]) == 2
    assert "zcode login zai" in capsys.readouterr().err
    assert not (tmp_path / "w").exists()
    for gone in ("base_args", "run_cli", "default_exe", "env_failures"):
        assert not hasattr(S, gone), gone


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
    return ["--work", str(work), "--repo", str(repo), "--date", "2026-10-14", *extra]


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
    assert "«Opus xhigh»" in prompt and "workflow:acceptor-ASSET-TEST-HERO-001-r1" in prompt and "инструментом Read" in prompt
    for gone in ("codex", "Codex", "отдельными -i", "OEM", "Sol"):
        assert gone not in prompt.replace(f"concept-{K}-codex", ""), gone
    const = json.loads((e / "launcher-inputs.json").read_text(encoding="utf-8"))["constants"]
    assert const["cycle"] == "r1" and const["date"] == "2026-10-14" and const["previous_card"] is None
    assert const["executor_session_id"] == "launcher:stage-1c-sheet-20261014"
    assert const["acceptor"] == {"profile": "Opus xhigh", "session_id": "workflow:acceptor-ASSET-TEST-HERO-001-r1"}
    assert json.loads((e / "launcher-preflight.json").read_text(encoding="utf-8"))["recheck_same"] is True
    raw = (e / "acceptor-args.json").read_bytes()
    assert raw.isascii() and out["args"].endswith("/acceptor-args.json")
    wa = json.loads(raw)
    assert wa["kind"] == "concept" and "Sol 6.1 xhigh" not in wa["schema"]["properties"]["acceptor"]["properties"][
        "profile"]["enum"]
    assert wa["items"] == [{"asset": AID, "evidence": out["evidence"], "label": "acceptor-ASSET-TEST-HERO-001-r1",
                            "prompt": out["evidence"] + "/acceptor-prompt.md"}]
    assert json.loads((work / "acceptor-args-20261014.json").read_text(encoding="ascii"))["items"] == wa["items"]


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


def sheet(repo: Path, work: Path, **extra):
    return S.Sheet(type("A", (), {"repo": str(repo), "work": str(work), "date": "2026-10-14", "log": None,
                                  "user_quote": [], **extra})())


@pytest.mark.parametrize("manifest_form", ["mapping", "list"])
@pytest.mark.parametrize("damage", ["intact", "unlisted", "missing", "hash", "bytes"])
def test_preflight_checks_nested_historical_manifest(tmp_path, manifest_form, damage):
    repo = make_repo(tmp_path)
    p = repo / f"art/imagegen/concept-{K}-codex"
    manifest = p / "manifest-sha256.json"
    archived = p / "history/20261013/preexisting-metadata/manifest-sha256.json"
    archived.parent.mkdir(parents=True)
    shutil.copy2(manifest, archived)
    name = archived.relative_to(p).as_posix()
    m = json.loads(manifest.read_text(encoding="utf-8"))
    m["files"][name] = {"sha256": b.sha256(archived), "bytes": archived.stat().st_size}
    if damage == "unlisted":
        del m["files"][name]
    elif damage == "missing":
        archived.unlink()
    elif damage == "hash":
        archived.write_bytes(archived.read_bytes().replace(b'"files"', b'"other"', 1))  # same byte count
    elif damage == "bytes":
        m["files"][name]["bytes"] += 1  # correct hash, wrong byte count
    if manifest_form == "list":
        m["files"] = [dict(path=path, **item) for path, item in m["files"].items()]
    manifest.write_text(json.dumps(m), encoding="utf-8")
    s = sheet(repo, tmp_path / "work")
    row = {"asset_id": AID, "key": K, "package": b.rel(p, repo)}
    if damage == "intact":
        s.preflight(row, 1)
        result = json.loads((s.ev_dir(AID, 1) / "launcher-preflight.json").read_text(encoding="utf-8"))
        assert result["manifest"] is True and result["recheck_same"] is True
        assert result["package_hashes"][b.rel(archived, repo)] == b.sha256(archived)
    else:
        error = "manifest coverage mismatch" if damage == "unlisted" else "manifest mismatch " + name
        with pytest.raises(RuntimeError, match=error):
            s.preflight(row, 1)


def test_preflight_creates_missing_cycle_folder(tmp_path):
    """C8: каталог цикла заводит сам инструмент; неизвестный ассет — по-прежнему ошибка, без каталогов-сирот."""
    repo = make_repo(tmp_path)
    e = repo / f"art/pipeline-candidates/{AID}/evidence/acceptance-concept/20261014-sheet-r1"
    shutil.rmtree(e)
    s = sheet(repo, tmp_path / "work")
    s.preflight({"asset_id": AID, "key": K, "package": f"art/imagegen/concept-{K}-codex"}, 1)
    assert (e / "launcher-preflight.json").is_file()
    with pytest.raises(RuntimeError, match="нет каталога ассета"):
        s.preflight({"asset_id": "ASSET-NOBODY-001", "key": "nobody", "package": f"art/imagegen/concept-{K}-codex"}, 1)
    assert not (repo / "art/pipeline-candidates/ASSET-NOBODY-001").exists()


def test_prepare_without_owned_file_and_executor_id(tmp_path, capsys):
    """C8: одна фигура без --owned; C9: --executor-session-id в константы карточки, без флага — прежняя строка
    и предупреждение; C13: пустой limit_reached — без строки в промпте."""
    repo = make_repo(tmp_path)
    work = tmp_path / "work"
    sid = "claude-code:0f1e/agent:beowulf-1c"
    assert S.main(["prepare", K, "1", *args(repo, work, "--executor-session-id", sid)]) == 0
    e = repo / json.loads(capsys.readouterr().out)["evidence"]
    const = json.loads((e / "launcher-inputs.json").read_text(encoding="utf-8"))["constants"]
    assert const["executor_session_id"] == sid
    prompt = (e / "acceptor-prompt.md").read_text(encoding="utf-8")
    assert "исчерпал генерации" not in prompt and sid in prompt
    assert S.main(["prepare", K, "1", *args(repo, work)]) == 0
    assert "WARN: --executor-session-id" in capsys.readouterr().err
    assert S.main(["prepare", "nobody", "1", "--owned", str(work / "missing.json"), *args(repo, work)]) == 2
    assert S.main(["prepare", "Bad_Key", "1", *args(repo, work)]) == 2


def test_limit_line_only_when_limit_reached(tmp_path):
    assert S.limit_line([]) == "" and S.limit_line(None) == ""
    line = S.limit_line([{"view": "back", "failed_items": ["weapon side", "framing"]}, {"view": "side",
                                                                                     "failed_items": "pose"}])
    assert line.startswith("Генератор исчерпал генерации запуска; проваленные пункты CHECKLIST: back: weapon side, framing; "
                           "side: pose; оцени их по рубрике")
    repo = make_repo(tmp_path)
    p = repo / f"art/imagegen/concept-{K}-codex"
    (p / "verification.json").write_text(json.dumps({"limit_reached": [{"view": "back", "failed_items": ["x"]}]}),
                                         encoding="utf-8")
    m = json.loads((p / "manifest-sha256.json").read_text(encoding="utf-8"))
    m["files"]["verification.json"] = {"sha256": b.sha256(p / "verification.json"),
                                       "bytes": (p / "verification.json").stat().st_size}
    (p / "manifest-sha256.json").write_text(json.dumps(m), encoding="utf-8")
    e, _p, prompt, _i = sheet(repo, tmp_path / "work").prepare({"asset_id": AID, "key": K, "package": b.rel(p, repo)}, 1)
    assert "проваленные пункты CHECKLIST: back: x;" in prompt


def test_prepare_second_writes_opus_prompt_and_ascii_args(tmp_path, capsys):
    """C10/C34: промпт второго приёмщика того же листа (профиль Opus, session workflow:…, изображения — Read) и
    ASCII-аргументы workflow second-acceptor со схемой concept; без первой карточки и при изменённом пакете — отказ."""
    repo = make_repo(tmp_path)
    work = tmp_path / "work"
    row = {"asset_id": AID, "key": K, "package": f"art/imagegen/concept-{K}-codex"}
    assert S.main(["prepare-second", K, "1", *args(repo, work)]) == 2  # нет card.json
    assert "нет первой карточки" in capsys.readouterr().err
    s = sheet(repo, work)
    e, _p, first, _i = s.prepare(row, 1)
    (e / "card.json").write_text("{}", encoding="utf-8")
    assert S.main(["prepare-second", K, "1", *args(repo, work)]) == 0
    out = json.loads(capsys.readouterr().out)
    p2 = (e / "acceptor-prompt-2.md").read_text(encoding="utf-8")
    assert (e / "acceptor-prompt.md").read_text(encoding="utf-8") == first  # промпт первого приёмщика не тронут
    assert "«Opus xhigh»" in p2 and "workflow:acceptor2-ASSET-TEST-HERO-001-r1" in p2 and "инструментом Read" in p2
    assert "отдельными -i" not in p2 and "codex:pending" not in p2
    c1 = json.loads((e / "launcher-inputs.json").read_text(encoding="utf-8"))["constants"]
    c2 = json.loads((e / "launcher-inputs-2.json").read_text(encoding="utf-8"))["constants"]
    assert c2["frames"] == c1["frames"] and c2["accepted_object"] == c1["accepted_object"]
    assert c2["acceptor"] == {"profile": "Opus xhigh", "session_id": "workflow:acceptor2-ASSET-TEST-HERO-001-r1"}
    raw = (e / "second-acceptor-args.json").read_bytes()
    assert raw.isascii()
    wa = json.loads(raw)
    assert wa["kind"] == "concept" and wa["schema"]["properties"]["kind"]["enum"] == ["concept"]
    assert "description" not in json.dumps(wa["schema"]) and "title" not in wa["schema"]
    assert wa["items"] == [{"asset": AID, "evidence": s.rel(e), "label": "acceptor2-ASSET-TEST-HERO-001-r1",
                            "prompt": s.rel(e / "acceptor-prompt-2.md")}]
    batch = json.loads((work / "second-acceptor-args-20261014.json").read_text(encoding="ascii"))
    assert batch["items"] == wa["items"] and out["args"].endswith("second-acceptor-args.json")
    (e / "card-2.json").write_text("{}", encoding="utf-8")
    assert S.main(["prepare-second", K, "1", *args(repo, work)]) == 2  # вторая карточка уже есть
    (e / "card-2.json").unlink()
    p = repo / f"art/imagegen/concept-{K}-codex"
    (p / "README.md").write_text("правка после первой приёмки\n", encoding="utf-8")  # пакет цел, но уже другой
    m = json.loads((p / "manifest-sha256.json").read_text(encoding="utf-8"))
    m["files"]["README.md"] = {"sha256": b.sha256(p / "README.md"), "bytes": (p / "README.md").stat().st_size}
    (p / "manifest-sha256.json").write_text(json.dumps(m), encoding="utf-8")
    with pytest.raises(RuntimeError, match="пакет изменился после первой приёмки"):
        s.prepare(row, 1, second=True)


def test_ledger_templates_after_codex_switch_off(tmp_path):
    """C11 — история: T-CODEX-ACCEPT остаётся в живом 07-prompt-templates.md (старые строки), но строка Codex больше не
    пишется (Sol и Codex отключены 2026-10-20); генерации Gemini пишутся шаблоном T-GEMINI-IMG."""
    sys.path.insert(0, str(b.REPO / "tools/art/visual"))
    import ledger

    root = tmp_path / "root"
    (root / "docs/game-design/visual/06-tasks").mkdir(parents=True)
    (root / "docs/game-design/visual/06-tasks/anim.csv").write_text("id,area,title\nAN-145,hero,x\n", encoding="utf-8")
    shutil.copy2(b.REPO / "docs/game-design/visual/07-prompt-templates.md",
                 root / "docs/game-design/visual/07-prompt-templates.md")
    led = root / "ledger.json"
    led.write_text(json.dumps({"schema": ledger.SCHEMA, "entries": [], "totals": {}}), encoding="utf-8")
    common = ["--root", str(root), "--ledger", str(led), "add", "--task", "AN-145"]
    assert ledger.main(common + ["--template", "T-CODEX-ACCEPT", "--service", "Codex", "--model",
                                 "codex exec gpt-6.1-sol xhigh", "--units", "пакет приёмки Sol, 0 генераций image_gen",
                                 "--result", "art/x/card.json"]) == 2
    assert json.loads(led.read_text(encoding="utf-8"))["entries"] == []
    assert ledger.main(common + ["--template", "T-GEMINI-IMG", "--service", "Gemini", "--model", "Gemini app",
                                 "--generations", "3", "--result", "art/imagegen/concept-x-codex/"]) == 0
    e = json.loads(led.read_text(encoding="utf-8"))["entries"][-1]
    assert e["template"] == "T-GEMINI-IMG" and e["units"] == "3 генераций" and e["cost"] is None
    assert ledger.main(common + ["--template", "T-GEMINI-NOPE", "--service", "Gemini", "--model", "m",
                                 "--generations", "1"]) == 2


def prepared(tmp_path, monkeypatch, validate_code=0):
    """prepare r1 на синтетике, фальшивый validate_card (код validate_code) и карточка «Opus xhigh» по константам."""
    repo = make_repo(tmp_path)
    work = tmp_path / "work"
    assert S.main(["prepare", K, "1", *args(repo, work)]) == 0
    e = repo / f"art/pipeline-candidates/{AID}/evidence/acceptance-concept/20261014-sheet-r1"
    const = json.loads((e / "launcher-inputs.json").read_text(encoding="utf-8"))["constants"]
    card = dict(const, gates={"G-CHECKS": {"status": "PASS", "source": const["reports"][0], "note": None,
                                           "source_defect": None}},
                scores={d: {"value": 2, "rationale": "r", "frames": [f"{K}-front.png"]} for d in "SCQP"},
                score=10.0, verdict="pass", verdict_reason="null", rework_fix_list=[], known_issues=None,
                status_note="художественно принято, по делегированию")
    real_run, calls = b.run, []

    def fake_run(argv, cwd):
        if "validate_card.py" not in " ".join(map(str, argv)):
            return real_run(argv, cwd)
        calls.append(argv)
        return type("R", (), {"returncode": validate_code, "stdout": "pass\n" if validate_code == 0 else "",
                              "stderr": "" if validate_code == 0 else "FAIL: verdict\n"})()

    monkeypatch.setattr(b, "run", fake_run)
    wf = tmp_path / "wf.json"
    wf.write_text(json.dumps({"result": [{"asset": AID, "evidence": b.rel(e, repo), "card": card}]},
                             ensure_ascii=False), encoding="utf-8")
    return repo, work, e, wf, card, calls


def test_finish_writes_first_card_and_logs(tmp_path, monkeypatch, capsys):
    repo, work, e, wf, card, calls = prepared(tmp_path, monkeypatch)
    capsys.readouterr()
    assert S.main(["finish", str(wf), *args(repo, work)]) == 0
    saved = json.loads((e / "card.json").read_text(encoding="utf-8"))
    assert saved["acceptor"]["profile"] == "Opus xhigh" and "verdict_reason" not in saved and "known_issues" not in saved
    assert len(calls) == 1 and "--check-files" in calls[0]
    rec = json.loads((work / "acceptance-log-1c.jsonl").read_text(encoding="utf-8").splitlines()[-1])
    assert rec["verdict"] == "pass" and rec["validate_exit"] == 0 and rec["card_path"].endswith("card.json")
    assert "DONE" in capsys.readouterr().out
    assert S.main(["finish", str(wf), *args(repo, work)]) == 1  # карточка уже есть
    assert S.main(["finish", str(tmp_path / "missing.json"), *args(repo, work)]) == 2


def test_finish_rejects_wrong_acceptor_and_keeps_invalid_card(tmp_path, monkeypatch, capsys):
    repo, work, e, wf, card, _calls = prepared(tmp_path, monkeypatch, validate_code=1)
    bad = dict(card, acceptor={"profile": "Sol 6.1 xhigh", "session_id": "codex:pending"})
    wb = tmp_path / "wb.json"
    wb.write_text(json.dumps([{"asset": AID, "evidence": b.rel(e, repo), "card": bad}], ensure_ascii=False),
                  encoding="utf-8")
    assert S.main(["finish", str(wb), *args(repo, work)]) == 1
    assert not (e / "card.json").exists() and "BLOCKED" in capsys.readouterr().out
    assert S.main(["finish", str(wf), *args(repo, work)]) == 1  # validate_card 1: карточка — в card-invalid-1.json
    assert not (e / "card.json").exists() and (e / "card-invalid-1.json").is_file()
    rec = json.loads((work / "acceptance-log-1c.jsonl").read_text(encoding="utf-8").splitlines()[-1])
    assert rec["verdict"] == "card_invalid" and "FAIL: verdict" in rec["notes"]
