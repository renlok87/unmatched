"""Тесты validate_card.py: по одному кейсу на каждое правило вердикта Р-6.4/Р-6.6/Р-7.2 + сверки полей.

    python -m pytest tools/art/acceptance/tests -q
"""
import copy
import json
import subprocess
import sys
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))

import validate_card as vc  # noqa: E402

SCHEMA = json.loads(vc.SCHEMA_PATH.read_text(encoding="utf-8"))
MODEL_FILES = vc.MODEL_FRAMES + vc.POSE_FRAMES + ["frames.json", "sheet.png"]
EV = "art/pipeline-candidates/ASSET-TEST-001/evidence/acceptance/20261009-r1"


def dim(value, frames=("turn-000.jpg",)):
    return {"value": value, "rationale": "обоснование балла по кадрам",
            "frames": list(frames) if value is not None else []}


def gate(status="PASS", **extra):
    g = {"status": status, "source": "art/pipeline-candidates/ASSET-TEST-001/20261009-h2/reports/x.json"}
    g.update(extra)
    return g


def model_card(S=2, F=2, T=1.5, D=2, verdict="pass", cycle="r1", **over):
    scores = {"S": dim(S), "F": dim(F, ["wire-front.jpg"]), "T": dim(T, ["close-head.jpg"]),
              "D": dim(D, ["pose-01.jpg"])}
    card = {
        "schema": "unmatched.asset-acceptance/2", "kind": "model", "asset_id": "ASSET-TEST-001",
        "cycle": cycle, "date": "2026-10-09", "previous_card": None,
        "accepted_object": [{"path": "art/pipeline-candidates/ASSET-TEST-001/20261009-h2-lookdev/export/SK_Test_H2LD.fbx",
                             "sha256": "0" * 64}],
        "frames": {"dir": EV + "/frames", "files": list(MODEL_FILES)},
        "reports": ["art/pipeline-candidates/ASSET-TEST-001/20261009-h2/reports/run-manifest.json"],
        "gates": {g: gate() for g in vc.GATES["model"]},
        "scores": scores, "score": vc.compute_score(scores, "model"), "verdict": verdict,
        "rework_fix_list": [],
        "acceptor": {"profile": "Opus xhigh", "session_id": "acc-1"},
        "executor_session_id": "exe-1", "decided_by": "delegated (ВР-реестр 2026-10-06)",
        "status_note": "художественно принято, по делегированию",
    }
    if cycle != "r1":
        card["previous_card"] = EV.replace("r1", "r%d" % (int(cycle[1]) - 1)) + "/card.json"
    if verdict != "pass":
        card["verdict_reason"] = "маршрут выбран по правилу Р-6.4"
        card["status_note"] = ""
    card.update(over)
    return card


def concept_card(S=2, C=2, Q=1.5, P=2, verdict="pass", cycle="r1", checks="PASS"):
    scores = {k: dim(v, ["sheet-test.png"]) for k, v in dict(S=S, C=C, Q=Q, P=P).items()}
    card = model_card(verdict=verdict, cycle=cycle)
    card.update({"schema": "unmatched.concept-acceptance/1", "kind": "concept",
                 "frames": {"dir": "art/imagegen/concept-test-codex", "files": ["sheet-test.png", "test-front.png"]},
                 "gates": {"G-CHECKS": gate(checks)}, "scores": scores, "score": vc.compute_score(scores, "concept")})
    return card


def anim_card(R=2, C=2, D=1.5, L=2, verdict="pass", cycle="r1", contact="PASS", rework_fix_list=()):
    scores = {k: dim(v, ["Test-Idle-blender-sheet.jpg"]) for k, v in dict(R=R, C=C, D=D, L=L).items()}
    card = model_card(verdict=verdict, cycle=cycle)
    card.update({"schema": "unmatched.anim-acceptance/1", "kind": "anim", "clip": "Idle",
                 "frames": {"dir": "art/pipeline-candidates/ASSET-TEST-001/20261009-h2anim/preview",
                            "files": ["Test-Idle-blender-sheet.jpg"]},
                 "gates": {"G-VALIDATE": gate(), "G-CONTACT": gate(contact), "G-MANIFEST": gate()},
                 "scores": scores, "score": vc.compute_score(scores, "anim"),
                 "rework_fix_list": list(rework_fix_list)})
    return card


def run(card, **kw):
    return vc.validate(card, SCHEMA, **kw)


def fix(item, frame="turn-000.jpg"):
    return {"item": item, "frame": frame, "fix": "исправить по брифу §10", "tool": "h2_bake profile"}


# ------------------------------------------------------------------ schema / score

def test_schema_is_valid_draft_2020_12():
    jsonschema = pytest.importorskip("jsonschema")
    jsonschema.Draft202012Validator.check_schema(SCHEMA)


@pytest.mark.parametrize("vals,expected", [((2, 2, 1.5, 2), 9.4), ((2, 2, 2, 0.5), 8.1), ((1.5,) * 4, 7.5),
                                           ((2, 2, 1.5, None), 9.2), ((1, 1, 1, 1), 5.0)])
def test_score_formula(vals, expected):
    scores = {k: {"value": v} for k, v in zip("SFTD", vals)}
    assert vc.compute_score(scores, "model") == expected


def test_pass_valid_card():
    errs, allowed, _, score = run(model_card())
    assert errs == [] and allowed == {"pass"} and score == 9.4


def test_score_mismatch_rejected():
    card = model_card()
    card["score"] = 9.5
    errs, *_ = run(card)
    assert any(e.startswith("score:") for e in errs)


# ------------------------------------------------------------------ verdict rules (model)

def test_threshold_is_ge_8():  # 8.1 >= 8.0 → pass; 7.5 → rework_blender
    errs, allowed, _, score = run(model_card(S=2, F=2, T=1.5, D=1.0))
    assert score == 8.1 and allowed == {"pass"} and errs == []


def test_score_below_threshold_rework():
    card = model_card(S=1.5, F=1.5, T=1.5, D=1.5, verdict="rework_blender",
                      rework_fix_list=[fix("T", "close-head.jpg"), fix("F"), fix("D", "pose-01.jpg")])
    errs, allowed, _, score = run(card)
    assert score == 7.5 and allowed == {"rework_blender"} and errs == []
    card["verdict"] = "pass"
    card["status_note"] = "художественно принято, по делегированию"
    errs, *_ = run(card)
    assert any(e.startswith("verdict:") for e in errs)


def test_veto_below_1_blocks_pass_even_with_high_score():
    card = model_card(S=2, F=2, T=2, D=0.5)  # score 8.1, но D = 0,5
    errs, allowed, _, score = run(card)
    assert score == 8.1 and allowed == {"rework_blender"}
    assert any(e.startswith("verdict:") for e in errs)
    ok = model_card(S=2, F=2, T=2, D=0.5, verdict="rework_blender", rework_fix_list=[fix("D", "pose-01.jpg")])
    assert run(ok)[0] == []


def test_silhouette_below_1_5_returns_to_stage_1_or_2_regardless_of_sum():
    card = model_card(S=1.0, F=2, T=2, D=2, verdict="return_to_stage_1")  # score 8.8
    errs, allowed, _, score = run(card)
    assert score == 8.8 and allowed == {"return_to_stage_1", "return_to_stage_2"} and errs == []
    card2 = model_card(S=1.0, F=2, T=2, D=2, verdict="return_to_stage_2")
    assert run(card2)[0] == []
    bad = model_card(S=1.0, F=2, T=2, D=2, verdict="rework_blender", rework_fix_list=[fix("S")])
    assert any(e.startswith("verdict:") for e in run(bad)[0])


def test_return_requires_reason():
    card = model_card(S=1.0, verdict="return_to_stage_1")
    del card["verdict_reason"]
    errs, *_ = run(card)
    assert any("verdict_reason" in e for e in errs)


def test_gate_fail_rework_blender():
    card = model_card(verdict="rework_blender", rework_fix_list=[fix("G-UV", "uv-layout.png")])
    card["gates"]["G-UV"] = gate("FAIL")
    errs, allowed, *_ = run(card)
    assert allowed == {"rework_blender"} and errs == []


def test_gate_fail_with_source_defect_returns_to_stage_2():
    card = model_card(verdict="return_to_stage_2")
    card["gates"]["G-TOPO"] = gate("FAIL", source_defect=True)
    errs, allowed, *_ = run(card)
    assert allowed == {"return_to_stage_2"} and errs == []
    card["verdict"] = "rework_blender"
    card["rework_fix_list"] = [fix("G-TOPO")]
    assert any(e.startswith("verdict:") for e in run(card)[0])


def test_gate_fail_overrides_high_score():
    card = model_card(S=2, F=2, T=2, D=2)  # score 10
    card["gates"]["G-NAMES"] = gate("FAIL")
    errs, allowed, *_ = run(card)
    assert allowed == {"rework_blender"} and any(e.startswith("verdict:") for e in errs)


def test_last_cycle_without_pass_escalates():
    card = model_card(S=1.5, F=1.5, T=1.5, D=1.5, verdict="escalate_user", cycle="r3",
                      rework_fix_list=[fix("T")])
    errs, allowed, *_ = run(card)
    assert allowed == {"escalate_user"} and errs == []
    card["verdict"] = "rework_blender"
    assert any(e.startswith("verdict:") for e in run(card)[0])


def test_last_cycle_pass_stays_pass():
    errs, allowed, *_ = run(model_card(cycle="r3"))
    assert allowed == {"pass"} and errs == []


# ------------------------------------------------------------------ field consistency

def test_prop_without_rig_D_null_and_rig_na():
    card = model_card(D=None)
    card["gates"]["G-RIG"] = gate("n/a")
    card["frames"]["files"] = list(vc.MODEL_FRAMES) + ["sheet.png"]  # позы и кисти не нужны
    card["score"] = vc.compute_score(card["scores"], "model")
    errs, allowed, _, score = run(card)
    assert errs == [] and allowed == {"pass"} and score == 9.2


def test_D_null_requires_rig_na():
    card = model_card(D=None)
    card["score"] = vc.compute_score(card["scores"], "model")
    assert any("G-RIG" in e for e in run(card)[0])


def test_missing_fixed_frame_rejected():
    card = model_card()
    card["frames"]["files"].remove("wire-34.jpg")
    assert any("wire-34.jpg" in e for e in run(card)[0])


def test_rework_fix_list_must_cover_fail_and_veto():
    card = model_card(S=2, F=2, T=2, D=0.5, verdict="rework_blender", rework_fix_list=[fix("T")])
    errs, *_ = run(card)
    assert any("'T'" in e for e in errs)  # T = 2 — пункт лишний
    assert any("нет пунктов для D" in e for e in errs)


def test_acceptor_session_must_differ():
    card = model_card()
    card["executor_session_id"] = card["acceptor"]["session_id"]
    assert any("session_id" in e for e in run(card)[0])


def test_previous_card_required_from_r2():
    card = model_card(verdict="pass", cycle="r2")
    card["previous_card"] = None
    assert any("previous_card" in e for e in run(card)[0])


def test_absolute_paths_rejected():
    card = model_card()
    card["reports"] = ["C:/Users/ren/x.json"]
    assert run(card)[0]


# ------------------------------------------------------------------ concept / anim

def test_concept_pass_and_fail_route():
    assert run(concept_card())[1] == {"pass"}
    card = concept_card(Q=0.5, verdict="return_to_stage_1")
    errs, allowed, *_ = run(card)
    assert allowed == {"return_to_stage_1"} and errs == []


def test_concept_checks_fail_and_r4_escalation():
    errs, allowed, *_ = run(concept_card(checks="FAIL", verdict="return_to_stage_1", cycle="r3"))
    assert allowed == {"return_to_stage_1"} and errs == []
    errs, allowed, *_ = run(concept_card(checks="FAIL", verdict="escalate_user", cycle="r4"))
    assert allowed == {"escalate_user"} and errs == []


def test_anim_gate_fail_rework_and_pass():
    assert run(anim_card())[1] == {"pass"}
    card = anim_card(contact="FAIL", verdict="rework_blender", rework_fix_list=[fix("G-CONTACT")])
    errs, allowed, *_ = run(card)
    assert allowed == {"rework_blender"} and errs == []


def test_anim_requires_clip():
    card = anim_card()
    del card["clip"]
    assert any("clip" in e for e in run(card)[0])


# ------------------------------------------------------------------ builtin validator == jsonschema

@pytest.mark.parametrize("make", [
    lambda: model_card(),
    lambda: model_card(S=1.0, verdict="return_to_stage_1"),
    lambda: dict(model_card(), verdict="maybe"),
    lambda: dict(model_card(), reports=["/abs/path.json"]),
    lambda: {k: v for k, v in model_card().items() if k != "acceptor"},
    lambda: dict(model_card(), scores=dict(model_card()["scores"], S=dim(1.25))),
    lambda: dict(concept_card(), gates={"G-TOPO": gate()}),
    lambda: {k: v for k, v in anim_card().items() if k != "clip"},
])
def test_builtin_validator_agrees_with_jsonschema(make):
    pytest.importorskip("jsonschema")
    card = make()
    a = vc.schema_errors(copy.deepcopy(card), SCHEMA, use_jsonschema=True)
    b = vc.schema_errors(copy.deepcopy(card), SCHEMA, use_jsonschema=False)
    assert bool(a) == bool(b), (a, b)


# ------------------------------------------------------------------ CLI

def test_cli_print_verdict_and_exit_codes(tmp_path):
    script = str(HERE.parent / "validate_card.py")
    good = tmp_path / "good.json"
    good.write_text(json.dumps(model_card(), ensure_ascii=False), encoding="utf-8")
    r = subprocess.run([sys.executable, script, str(good), "--print-verdict"], capture_output=True, text=True)
    assert r.returncode == 0 and r.stdout.strip() == "pass"
    bad = tmp_path / "bad.json"
    bad.write_text(json.dumps(model_card(S=1.0), ensure_ascii=False), encoding="utf-8")  # verdict pass при S=1
    r = subprocess.run([sys.executable, script, str(bad), "--print-verdict"], capture_output=True, text=True)
    assert r.returncode == 1 and r.stdout.strip() == "return_to_stage_1|return_to_stage_2"
    r = subprocess.run([sys.executable, script, str(tmp_path / "missing.json")], capture_output=True, text=True)
    assert r.returncode == 1


def test_check_files_detects_sha_mismatch(tmp_path):
    card = model_card()
    rel = "art/x/SK_Test_H2LD.fbx"
    (tmp_path / "art/x").mkdir(parents=True)
    (tmp_path / rel).write_bytes(b"fbx")
    card["accepted_object"] = [{"path": rel, "sha256": "0" * 64}]
    errs, *_ = run(card, check_files=True, repo=tmp_path)
    assert any("sha256" in e for e in errs)
    assert any("frames: нет файла" in e for e in errs)
