"""clip_manifest.py: регистрация героев H2ANIM в check() (RB-07) и переопределение спеки на клип (F103).

  python -B -m pytest -q tools/tripo-pipeline/tests -k clip_manifest

Без Blender и UE. Закоммиченный манифест только читается; build пишет во временный файл (monkeypatch MANIFEST).
"""
import json
import sys
from pathlib import Path

import pytest

TESTS = Path(__file__).resolve().parent
sys.path.insert(0, str(TESTS.parent / "anim"))
import clip_manifest as cm  # noqa: E402

ACH_SPEC = "art/pipeline-candidates/ASSET-ACHILLES-001/build-profiles/achilles-h2anim-r3.json"
COMMITTED = cm.MANIFEST  # read only; build in the tests writes a temporary file


def committed() -> dict:
    with open(COMMITTED, encoding="utf-8") as f:
        return json.load(f)


def spec_copy(tmp_path: Path, drop_clip: str = "") -> str:
    """Копия спеки Achilles r3 (тот же run_dir: те же FBX, отчёты и UE-импорт) во временной папке."""
    spec = json.loads((Path(cm.REPO) / ACH_SPEC).read_text(encoding="utf-8"))
    if drop_clip:
        del spec["clips"][drop_clip]
    p = tmp_path / "achilles-h2anim-copy.json"
    p.write_text(json.dumps(spec, ensure_ascii=False), encoding="utf-8")
    return str(p)


@pytest.fixture
def tmp_manifest(monkeypatch, tmp_path):
    out = tmp_path / "clip-manifest.json"
    monkeypatch.setattr(cm, "MANIFEST", str(out))
    return out


def test_check_passes_on_the_committed_manifest(capsys):
    assert cm.registration_errors(committed()) == []
    assert cm.check() == 0
    assert "MANIFEST_CHECK PASS" in capsys.readouterr().out


def test_every_h2anim_hero_has_four_h2anim_records():
    m = committed()
    ids = {c["id"]: c for c in m["clips"] if c["role"] == "production"}
    for char in cm.H2ANIM:
        pre = cm.CHARS[char][0]
        for clip in cm.TARGETS:
            rec = ids[f"{pre}-{clip}"]
            assert rec["source"]["reference"] == cm.spec_for(char, clip)
            assert rec["validation"]["report"].endswith(f"_{clip}.validation.json")


def test_spec_typo_fails_check_with_the_hero_name(monkeypatch, capsys):
    """RB-07: опечатка в пути спеки — раньше пустой слот slot() и MANIFEST_CHECK PASS."""
    monkeypatch.setitem(cm.H2ANIM, "Achilles", ACH_SPEC.replace("-r3", "-r9"))
    errs = cm.registration_errors(committed())
    assert len(errs) == 4 and all(e.startswith("Achilles ") and "нет спеки" in e for e in errs)
    assert cm.check() == 1
    out = capsys.readouterr().out
    assert "MANIFEST_CHECK FAIL" in out and "Achilles" in out


def test_build_with_a_typo_writes_a_slot_but_check_fails(monkeypatch, tmp_manifest, capsys):
    monkeypatch.setitem(cm.H2ANIM, "Achilles", ACH_SPEC.replace("-r3", "-r9"))
    cm.build()
    built = json.loads(tmp_manifest.read_text(encoding="utf-8"))
    ach = [c for c in built["clips"] if c["id"].startswith("ACH-")]
    assert len(ach) == 4 and all(c["source"]["type"] == "none" for c in ach)  # the silent fallback is still built
    assert cm.check() == 1
    assert "Achilles Idle" in capsys.readouterr().out


def test_spec_without_the_clip(monkeypatch, tmp_path):
    monkeypatch.setitem(cm.H2ANIM, "Achilles", spec_copy(tmp_path, drop_clip="HitReact"))
    errs = cm.registration_errors(committed())
    assert any(e.startswith("Achilles HitReact:") and "нет клипа HitReact" in e for e in errs)


def test_missing_fbx_and_report(monkeypatch, tmp_path):
    spec = json.loads((Path(cm.REPO) / ACH_SPEC).read_text(encoding="utf-8"))
    spec["run_dir"] = "art/pipeline-candidates/ASSET-ACHILLES-001/no-such-run"
    p = tmp_path / "s.json"
    p.write_text(json.dumps(spec), encoding="utf-8")
    monkeypatch.setitem(cm.H2ANIM, "Achilles", str(p))
    errs = cm.registration_errors(committed())
    assert len(errs) == 4 and all(e.startswith("Achilles ") and "нет FBX" in e for e in errs)


def test_clip_override_moves_one_clip(monkeypatch, tmp_path, tmp_manifest, capsys):
    """F103: доработка одного клипа новым прогоном — одна строка H2ANIM_CLIP, остальные клипы не трогаются."""
    spec = spec_copy(tmp_path)
    monkeypatch.setattr(cm, "H2ANIM_CLIP", {("Achilles", "HitReact"): spec})
    assert cm.spec_for("Achilles", "HitReact") == spec
    assert cm.spec_for("Achilles", "Idle") == ACH_SPEC
    # the committed manifest is stale for the moved clip only
    stale = cm.registration_errors(committed())
    assert len(stale) == 1 and stale[0].startswith("Achilles HitReact:") and "собрана не из" in stale[0]
    cm.build()
    built = {c["id"]: c for c in json.loads(tmp_manifest.read_text(encoding="utf-8"))["clips"]}
    assert built["ACH-HitReact"]["source"]["reference"] == spec
    assert built["ACH-HitReact"]["status"] == "technically_imported"
    assert built["ACH-Idle"]["source"]["reference"] == ACH_SPEC
    assert cm.check() == 0
    assert "MANIFEST_CHECK PASS" in capsys.readouterr().out


def test_override_of_an_unknown_hero_or_clip(monkeypatch):
    monkeypatch.setattr(cm, "H2ANIM_CLIP", {("Nobody", "Idle"): ACH_SPEC, ("Achilles", "Dance"): ACH_SPEC})
    errs = cm.registration_errors(committed())
    assert sum("H2ANIM_CLIP" in e for e in errs) == 2


def test_hero_in_h2anim_without_chars(monkeypatch):
    monkeypatch.setitem(cm.H2ANIM, "Ghost", ACH_SPEC)
    assert "Ghost: есть в H2ANIM, нет в CHARS" in cm.registration_errors(committed())
