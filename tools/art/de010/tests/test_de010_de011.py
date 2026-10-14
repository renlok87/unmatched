"""de010 / de011 apply without Unreal: --only (F157, RB-02 item 5), the master skip by graph_signature, the editor tasks.

  python -B -m pytest -q tools/art/de010/tests

The editor is never started: run_editor is replaced by a recorder, the UE scripts run against a fake `unreal` module
(MagicMock) with empty clip / MIC lists, the master file and master-builds.json are temporary copies.
"""
import json
import runpy
import sys
from pathlib import Path
from unittest import mock

import pytest

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
sys.path.insert(0, str(HERE.parents[1] / "de011"))
import de010  # noqa: E402
import de011  # noqa: E402

SIG = "d" * 64


def ns(**kw):
    base = {"frames": "unused", "only": None, "dry_run": False, "rebuild_master": False}
    base.update(kw)
    return type("A", (), base)()


@pytest.fixture
def master_files(monkeypatch, tmp_path):
    """A temporary master .uasset and an empty master-builds.json, wired into de010."""
    uasset = tmp_path / "M_UM_Figure_v2.uasset"
    uasset.write_bytes(b"master v1")
    record = tmp_path / "master-builds.json"
    monkeypatch.setattr(de010, "MASTER_UASSET", uasset)
    monkeypatch.setattr(de010, "MASTER_BUILDS", record)
    return uasset, record


# ---- --only ------------------------------------------------------------------------------------------------------------

def test_select_heroes():
    keys = [h[0] for h in de010.HEROES]
    assert [h[0] for h in de010.select_heroes(None)] == keys
    assert [h[0] for h in de010.select_heroes("Achilles")] == ["Achilles"]
    # HEROES order, duplicates and blanks ignored
    assert [h[0] for h in de010.select_heroes(" Achilles,Angel,Achilles,")] == ["Angel", "Achilles"]
    with pytest.raises(SystemExit, match="Nobody not in HEROES"):
        de010.select_heroes("Achilles,Nobody")
    with pytest.raises(SystemExit, match="needs a key"):
        de010.select_heroes(" , ")


def test_de010_plan_only_touches_the_listed_hero(master_files, capsys):
    plan, master, _ = de010.apply_plan(ns(only="Achilles"))
    assert plan["heroes"] == ["Achilles"] and [c["key"] for c in plan["clips"]] == ["Achilles"]
    assert plan["clips"][0]["path"] == "/Game/PipelineCandidates/Achilles/H2Anim/AM_Achilles_LungeAttack"
    assert plan["warning"] is None and "WARNING" not in capsys.readouterr().err
    assert master["signature"] == plan["master"]["graph_signature"]


def test_de010_plan_without_only_warns_with_the_count(master_files, capsys):
    plan, _, _ = de010.apply_plan(ns())
    n = len(de010.HEROES)
    assert len(plan["clips"]) == n
    err = capsys.readouterr().err
    assert f"rewrites all {n} heroes" in err and plan["warning"] in err


def test_de011_plan_only_touches_the_listed_hero(master_files, capsys):
    plan, _, _ = de011.apply_plan(ns(only="Angel"))
    assert [m["asset"].rsplit("/", 1)[1] for m in plan["mics"]] == ["MI_Angel_H2LD_P1_Dissolve",
                                                                   "MI_Angel_H2LD_P2_Dissolve"]
    assert all(m["parent"].startswith("/Game/PipelineCandidates/Angel/") for m in plan["mics"])
    assert plan["warning"] is None
    plan, _, _ = de011.apply_plan(ns())
    assert len(plan["mics"]) == 2 * len(de010.HEROES)
    assert f"rewrites all {len(de010.HEROES)} heroes" in capsys.readouterr().err


def test_dry_run_starts_no_editor(monkeypatch, master_files, tmp_path, capsys):
    monkeypatch.setattr(de010, "run_editor", mock.Mock(side_effect=AssertionError("editor started")))
    frames = tmp_path / "frames"
    de010.cmd_apply(ns(frames=str(frames), only="Achilles", dry_run=True))
    de011.cmd_apply(ns(frames=str(frames), only="Achilles", dry_run=True))
    out = capsys.readouterr().out
    assert '"tool": "de010 apply"' in out and '"tool": "de011 apply"' in out
    assert not frames.exists()


def test_main_parses_only(monkeypatch, master_files, capsys):
    assert de010.main(["apply", "--dry-run", "--only", "Merlin", "--frames", "x"]) == 0
    assert json.loads(capsys.readouterr().out)["heroes"] == ["Merlin"]
    assert de011.main(["apply", "--dry-run", "--only", "Merlin", "--frames", "x"]) == 0
    assert json.loads(capsys.readouterr().out)["heroes"] == ["Merlin"]


# ---- the master: skip while the file is recorded at the current graph ---------------------------------------------------

def test_master_plan(master_files):
    uasset, record = master_files
    assert de010.master_plan(SIG)["action"] == "rebuild"  # no record yet
    entry = de010.record_master_build(SIG, "test")
    assert entry["uasset_sha256"] == de010.file_sha256(uasset)
    plan = de010.master_plan(SIG)
    assert plan["action"] == "skip" and "test" in plan["reason"]
    assert de010.master_plan(SIG, rebuild=True)["action"] == "rebuild"
    other = de010.master_plan("e" * 64)
    assert other["action"] == "rebuild" and "graph changed" in other["reason"]
    uasset.write_bytes(b"re-saved by another tool")  # same graph, but a file the record does not know
    assert de010.master_plan(SIG)["action"] == "rebuild"
    uasset.unlink()
    assert "no master file" in de010.master_plan(SIG)["reason"]


def test_record_keeps_newest_first_and_bounded(master_files, monkeypatch):
    uasset, record = master_files
    monkeypatch.setattr(de010, "MASTER_BUILDS_KEEP", 3)
    for i in range(5):
        uasset.write_bytes(b"build %d" % i)
        de010.record_master_build("%064d" % i, "t")
    de010.record_master_build("%064d" % 4, "t")  # the same file again: no duplicate
    builds = json.loads(record.read_text(encoding="utf-8"))["builds"]
    assert [b["graph_signature"] for b in builds] == ["%064d" % i for i in (4, 3, 2)]


def fake_editor(calls, master_report):
    def run(script, args, work, name, timeout=1800):
        calls.append({"script": Path(script).name, "args": args})
        out = {"master": dict(master_report)}
        if Path(script).name == "de010_apply_ue.py":
            out["clips"] = {}
        else:
            out["mics"] = {}
        return out
    return run


@pytest.mark.parametrize("tool", [de010, de011])
def test_apply_skips_the_master_at_the_same_graph(monkeypatch, master_files, tmp_path, tool):
    sig = de010.vm.graph_signature(de010.vm.figure_v2_graph(de010.vm.load_spec()))
    de010.record_master_build(sig, "seed")
    before = master_files[1].read_text(encoding="utf-8")
    calls = []
    monkeypatch.setattr(de010, "run_editor", fake_editor(calls, {"skipped": True}))
    tool.cmd_apply(ns(frames=str(tmp_path / "f"), only="Achilles"))
    args = calls[0]["args"]
    assert args["master_skip"]["action"] == "skip" and args["master_skip"]["graph_signature"] == sig
    assert master_files[1].read_text(encoding="utf-8") == before  # nothing recorded on a skip
    rep = json.loads((tmp_path / "f" / "apply.json").read_text(encoding="utf-8"))
    assert rep["master"]["master_action"] == "skip" and rep["heroes"] == ["Achilles"]
    if tool is de010:
        assert [c["key"] for c in args["clips"]] == ["Achilles"]
    else:
        assert len(args["mics"]) == 2 and all("Achilles" in m["asset"] for m in args["mics"])


@pytest.mark.parametrize("tool", [de010, de011])
def test_apply_rebuild_records_the_new_file(monkeypatch, master_files, tmp_path, tool):
    calls = []
    monkeypatch.setattr(de010, "run_editor", fake_editor(calls, {"compile_errors": []}))
    tool.cmd_apply(ns(frames=str(tmp_path / "f"), only="Achilles"))
    assert calls[0]["args"]["master_skip"] is None
    builds = json.loads(master_files[1].read_text(encoding="utf-8"))["builds"]
    assert builds[0]["uasset_sha256"] == de010.file_sha256(master_files[0])
    assert builds[0]["tool"] == f"{tool.__name__} apply"
    # a rebuild with compile errors is not recorded (the next apply rebuilds again)
    master_files[0].write_bytes(b"broken build")
    monkeypatch.setattr(de010, "run_editor", fake_editor(calls, {"compile_errors": ["x"]}))
    tool.cmd_apply(ns(frames=str(tmp_path / "g"), only="Achilles", rebuild_master=True))
    assert len(json.loads(master_files[1].read_text(encoding="utf-8"))["builds"]) == 1


@pytest.mark.parametrize("log_text,clean", [("LogInit: x\nLogExit: Preparing to exit.\nLogExit: Exiting.\n", True),
                                            ("LogInit: x\nLogPython: script done\n", False)])
def test_de011_warns_on_a_non_zero_editor_exit(monkeypatch, master_files, tmp_path, capsys, log_text, clean):
    """C56: Beowulf 7b - UnrealEditor-Cmd crashed 0xC0000005 after LogExit; the step still passes, with a WARN."""
    log = tmp_path / "apply.log"
    log.write_text(log_text, encoding="utf-8")

    def run(script, args, work, name, timeout=1800):
        return {"master": {"compile_errors": []}, "mics": {},
                "_editor": {"exit": 3221225477, "seconds": 15.6, "log": log.as_posix()}}
    monkeypatch.setattr(de010, "run_editor", run)
    de011.cmd_apply(ns(frames=str(tmp_path / "f"), only="Beowulf"))
    err = capsys.readouterr().err
    assert "WARN apply: UnrealEditor-Cmd exit 3221225477 (0xC0000005)" in err
    assert ("AFTER a clean" in err) is clean and ("check that the packages" in err) is (not clean)
    rep = json.loads((tmp_path / "f" / "apply.json").read_text(encoding="utf-8"))
    assert rep["editor_exit_warning"]["clean_logexit"] is clean and rep["editor_exit_warning"]["exit_hex"] == "0xC0000005"


def test_de011_no_warning_at_exit_zero(monkeypatch, master_files, tmp_path, capsys):
    monkeypatch.setattr(de010, "run_editor", lambda *a, **k: {"master": {"compile_errors": []}, "mics": {},
                                                             "_editor": {"exit": 0, "log": "x"}})
    de011.cmd_apply(ns(frames=str(tmp_path / "f"), only="Beowulf"))
    assert "WARN" not in capsys.readouterr().err
    assert "editor_exit_warning" not in json.loads((tmp_path / "f" / "apply.json").read_text(encoding="utf-8"))
    assert de011.editor_exit_check({}, "inspect") is None                  # fake runners without _editor


# ---- the editor tasks against a fake `unreal` ----------------------------------------------------------------------------

def run_ue_task(monkeypatch, tmp_path, script: Path, args: dict, builder_body: str) -> dict:
    builder = tmp_path / "builder.py"
    builder.write_text(builder_body, encoding="utf-8")
    args = dict(args, out=str(tmp_path / "report.json"), master_script=str(builder),
                master={"master": "/Game/UM/Materials/v2/M_UM_Figure_v2", "out": str(tmp_path / "m.json")})
    (tmp_path / "args.json").write_text(json.dumps(args), encoding="utf-8")
    monkeypatch.setenv("DE010_ARGS", str(tmp_path / "args.json"))
    monkeypatch.setitem(sys.modules, "unreal", mock.MagicMock(name="unreal"))
    runpy.run_path(str(script), run_name="__main__")
    return json.loads((tmp_path / "report.json").read_text(encoding="utf-8"))


BUILDER_FAILS = "raise RuntimeError('the master builder ran')\n"
BUILDER_OK = ("import json\nopen(ARGS['out'], 'w').write(json.dumps({'built': True, 'compile_errors': []}))\n")
TASKS = [(HERE.parent / "de010_apply_ue.py", {"clips": [], "notify_class": "S08ContactAnimNotify"}),
         (HERE.parents[1] / "de011" / "de011_apply_ue.py", {"mics": [], "switch": "UseDissolve"})]


@pytest.mark.parametrize("script,extra", TASKS, ids=["de010", "de011"])
def test_ue_task_skip_does_not_run_the_builder(monkeypatch, tmp_path, script, extra):
    skip = {"action": "skip", "reason": "same graph", "uasset_sha256": "a" * 64}
    rep = run_ue_task(monkeypatch, tmp_path, script, dict(extra, master_skip=skip), BUILDER_FAILS)
    assert "error" not in rep, rep.get("error")
    assert rep["master"]["skipped"] is True and rep["master"]["reason"] == "same graph"


@pytest.mark.parametrize("script,extra", TASKS, ids=["de010", "de011"])
def test_ue_task_without_skip_runs_the_builder(monkeypatch, tmp_path, script, extra):
    rep = run_ue_task(monkeypatch, tmp_path, script, dict(extra, master_skip=None), BUILDER_OK)
    assert "error" not in rep, rep.get("error")
    assert rep["master"]["built"] is True
    # the old ARGS (no master_skip key, e.g. tools/art/hero/figure_master_v24_apply.py) still rebuild
    rep = run_ue_task(monkeypatch, tmp_path, script, dict(extra), BUILDER_OK)
    assert rep["master"]["built"] is True
