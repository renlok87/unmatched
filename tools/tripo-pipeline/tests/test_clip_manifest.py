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


# ---------------------------------------------- C53 (2026-10-14): происхождение движения из pattern / MOTION_SOURCE
def _clip_spec(**top):
    spec = {"clips": {"Idle": {"template": {"file": "blender/ASSET-MEDUSA-001/export/AM_Medusa_Idle.fbx"},
                               "reference": "art/animation-refs/ASSET-KING-ARTHUR-001/ARTH-Idle",
                               "reference_kind": "library pattern (D-11), not a X video"}}}
    spec.update(top)
    return spec


def _asset(tmp_path, card_line=None):
    """<asset>/build-profiles/x-h2anim.json (путь спеки) и при card_line — <asset>/asset-card.yaml."""
    (tmp_path / "build-profiles").mkdir(parents=True, exist_ok=True)
    if card_line is not None:
        (tmp_path / "asset-card.yaml").write_text("ASSET_ID: X\n%s\n  \"MOTION_SOURCE\": \"nested, ignored\"\n"
                                                 % card_line, encoding="utf-8")
    return str(tmp_path / "build-profiles" / "x-h2anim.json")


def test_provenance_without_pattern_keys_is_the_old_text(tmp_path):
    txt, kind = cm.provenance(_clip_spec(), _asset(tmp_path), "Idle")
    assert kind == "video"
    assert txt == ("шаблон дельт blender/ASSET-MEDUSA-001/export/AM_Medusa_Idle.fbx + авторский слой по видео-референсу "
                   "art/animation-refs/ASSET-KING-ARTHUR-001/ARTH-Idle")
    # MOTION_SOURCE «syntx: …» — видео-референс, текст прежний
    txt2, kind2 = cm.provenance(_clip_spec(), _asset(tmp_path, 'MOTION_SOURCE: "syntx: полёт"'), "Idle")
    assert (txt2, kind2) == (txt, "video")


def test_provenance_from_history_pattern_spec_and_card(tmp_path):
    spec = _clip_spec(history={"pattern_spec": "art/x/angel-h2anim-r2.json", "pattern_sha256": "ab"})
    txt, kind = cm.provenance(spec, _asset(tmp_path, 'MOTION_SOURCE: "library: Angel (r2)"   # ДС-6'), "Idle")
    assert kind == "pattern"
    assert "ключи паттерна библиотеки art/x/angel-h2anim-r2.json" in txt
    assert "MOTION_SOURCE «library: Angel (r2)»" in txt and "по видео-референсу" not in txt
    assert "reference_kind: library pattern (D-11), not a X video" in txt and "AM_Medusa_Idle.fbx" in txt


def test_provenance_pattern_key_forms_and_motion_source_only(tmp_path):
    p = _asset(tmp_path)
    txt, kind = cm.provenance(_clip_spec(pattern={"spec": "art/k/king-arthur-h2anim.json", "key": "KingArthur"}), p,
                              "Idle")
    assert kind == "pattern" and "art/k/king-arthur-h2anim.json (KingArthur)" in txt
    assert cm.pattern_of(_clip_spec(pattern="art/k/a.json")) == {"spec": "art/k/a.json"}
    txt, kind = cm.provenance(_clip_spec(motion_source="library: Merlin"), p, "Idle")
    assert kind == "pattern" and "авторский слой по паттерну библиотеки" in txt and "«library: Merlin»" in txt
    txt, kind = cm.provenance(_clip_spec(), _asset(tmp_path, "MOTION_SOURCE: tripo-preset: slash"), "Idle")
    assert kind == "pattern" and "пресета Tripo" in txt and "«tripo-preset: slash»" in txt
    assert cm.motion_source({}, _asset(tmp_path, "MOTION_SOURCE: 'library: Harpy'  # c")) == "library: Harpy"
    assert cm.pattern_of({"history": {"previous_specs": ["a"]}}) is None


def test_committed_heroes_keep_their_text_and_beowulf_names_the_angel_pattern():
    """Только Beowulf (history.pattern_spec + MOTION_SOURCE заявки) получает новый текст; у остальных героев H2ANIM
    заметка прежняя (вид video)."""
    for char in cm.H2ANIM:
        for clip in cm.TARGETS:
            rel = cm.spec_for(char, clip)
            spec = cm.load_json(rel)
            txt, kind = cm.provenance(spec, rel, clip)
            if char == "Beowulf":
                assert kind == "pattern" and "angel-h2anim-r2.json" in txt and "по видео-референсу" not in txt
            else:
                assert kind == "video" and "по видео-референсу" in txt, (char, clip)
