"""tools/tripo-pipeline/ue7a без Unreal: чистая логика (пути героя, перенацеливание шаблона, LDV-13, --set), --dry-run
UE-шагов, задача редактора на поддельном модуле unreal, подготовка приёмки клипов и генераторы профиля импорта и
конфига съёмки на синтетическом чекауте.

    python -B -m pytest -q tools/tripo-pipeline/tests/test_ue7a.py
"""
import json
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

TESTS = Path(__file__).resolve().parent
UE7A = TESTS.parent / "ue7a"
sys.path.insert(0, str(UE7A))
import _ue7a as c  # noqa: E402
import delete_prev  # noqa: E402
import discard_master  # noqa: E402
import prep_acceptance  # noqa: E402
import refresh_carrier  # noqa: E402
import write_import_profile as wip  # noqa: E402
import write_review_config as wrc  # noqa: E402


def wj(path: Path, obj):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=1), encoding="utf-8")
    return path


# ------------------------------------------------------------------------------------------------- общие помощники
def test_hero_paths_and_bad_key():
    p = c.hero_paths("Achilles")
    assert p["carrier"] == "/Game/PipelineCandidates/Achilles/Rig/SK_Achilles"
    assert p["skeleton"] == "/Game/PipelineCandidates/Achilles/Rig/SK_Achilles_Skeleton"
    assert c.hero_paths("Harpy", "H3LD")["stage"] == "/Game/PipelineCandidates/Harpy/H3LD"
    with pytest.raises(ValueError):
        c.hero_paths("achilles")


def test_retarget_respects_word_boundaries():
    pairs = c.name_pairs("Ant", "Achilles", "ant", "achilles", "ASSET-ANT-001", "ASSET-ACHILLES-001")
    src = {"a": "SK_Ant_H2_Body", "b": "/Game/PipelineCandidates/Ant/H2LD", "c": "Antlers are important",
           "d": "ant-h2-lookdev/3", "e": "art/pipeline-candidates/ASSET-ANT-001/x", "f": ["T_UM_MatLUT_Ant.dds"],
           "SK_Ant_H2_Spear": 1200}
    out = c.retarget(src, pairs)
    assert out["a"] == "SK_Achilles_H2_Body" and out["b"] == "/Game/PipelineCandidates/Achilles/H2LD"
    assert out["c"] == "Antlers are important"  # не внутри слова
    assert out["d"] == "achilles-h2-lookdev/3" and out["e"] == "art/pipeline-candidates/ASSET-ACHILLES-001/x"
    assert out["f"] == ["T_UM_MatLUT_Achilles.dds"] and out["SK_Achilles_H2_Spear"] == 1200
    assert c.leftovers(out, "Ant") == []
    assert c.leftovers({"x": "MI_Ant_P1"}, "Ant") == ['"x": "MI_Ant_P1"']


def test_team_dye_ldv13_and_apply_sets():
    assert c.team_dye(0.03512, 0.10434) == (22.779, 8.6256)  # Achilles r3, profile rev 4
    with pytest.raises(ValueError):
        c.team_dye(0, 0.1)
    o = {"a": {"b": [{"c": 1}, {"c": 2}]}, "drop": {"x": 1}}
    c.apply_sets(o, sets=["a.b.1.c=text", "new.key=v"], set_jsons=['a.n=[1, 2]'], drops=["drop.x"])
    assert o == {"a": {"b": [{"c": 1}, {"c": "text"}], "n": [1, 2]}, "drop": {}, "new": {"key": "v"}}
    with pytest.raises(ValueError):
        c.apply_sets(o, sets=["no-equals"])


def test_run_ue_task_dry_run_needs_no_editor(capsys):
    res = c.run_ue_task(UE7A / "discard_master.py", Path("x.json"), dry_run=True, package="/Game/X")
    assert res["dry_run"] and res["args"] == {"package": "/Game/X"} and res["script"].endswith("discard_master.py")
    assert json.loads(capsys.readouterr().out)["dry_run"] is True


# ---------------------------------------------------------------------------------------------- UE-шаги, --dry-run
def test_delete_prev_plan_and_dry_run(tmp_path, capsys):
    man = {"stages": {"ue-import": {"ue_owned_assets": [
        "/Game/PipelineCandidates/Achilles/H2LD/Textures/T_Achilles_H2LD_BC",
        "/Game/PipelineCandidates/Achilles/H2LD/Meshes/SK_Achilles_H2LD",
        "/Game/PipelineCandidates/Achilles/H2LD/Materials/MI_Achilles_H2LD",
        "/Game/PipelineCandidates/Achilles/H2LD/Materials/MI_Achilles_H2LD_P1",
        "/Game/PipelineCandidates/Achilles/Rig/SK_Achilles_Skeleton",
        "/Game/UM/Materials/v2/M_UM_Figure_v2"]}}}
    plan = delete_prev.plan(man, "Achilles")
    assert plan == ["/Game/PipelineCandidates/Achilles/H2LD/Materials/MI_Achilles_H2LD_P1",
                    "/Game/PipelineCandidates/Achilles/H2LD/Materials/MI_Achilles_H2LD",
                    "/Game/PipelineCandidates/Achilles/H2LD/Meshes/SK_Achilles_H2LD",
                    "/Game/PipelineCandidates/Achilles/H2LD/Textures/T_Achilles_H2LD_BC"]
    wj(tmp_path / "prev" / "manifest.json", man)
    assert delete_prev.main(["--key", "Achilles", "--prev-run", str(tmp_path / "prev"), "--dry-run"]) == 0
    assert json.loads(capsys.readouterr().out)["plan"] == plan
    assert delete_prev.main(["--key", "Achilles", "--prev-run", str(tmp_path / "none"), "--dry-run"]) == 2


def test_discard_master_dry_run_and_bad_package(tmp_path, capsys):
    assert discard_master.main(["--out", str(tmp_path / "d.json"), "--dry-run"]) == 0
    assert json.loads(capsys.readouterr().out)["args"]["package"] == c.MASTER_FIGURE
    assert discard_master.main(["--out", str(tmp_path / "d.json"), "--package", "M_UM_Figure_v2"]) == 2


def fake_unreal(dirty_after=()):
    pkg = SimpleNamespace(is_dirty=lambda: True)
    asset = SimpleNamespace(get_outermost=lambda: pkg)
    named = [SimpleNamespace(get_name=lambda n=n: n) for n in dirty_after]
    return SimpleNamespace(
        EditorAssetLibrary=SimpleNamespace(load_asset=lambda p: asset),
        ReloadPackagesInteractionMode=SimpleNamespace(ASSUME_POSITIVE=1),
        EditorLoadingAndSavingUtils=SimpleNamespace(reload_packages=lambda pkgs, mode: (True, ""),
                                                    get_dirty_content_packages=lambda: named,
                                                    get_dirty_map_packages=lambda: []))


def test_discard_master_as_editor_task(tmp_path):
    """Как ue_py/_run.py: exec файла с __name__ == "__ue_task__", ARGS и unreal в globals."""
    out = tmp_path / "res.json"
    code = (UE7A / "discard_master.py").read_text(encoding="utf-8")
    exec(compile(code, "discard_master.py", "exec"),
         {"__name__": "__ue_task__", "ARGS": {"package": c.MASTER_FIGURE, "out": str(out)}, "unreal": fake_unreal()})
    res = json.loads(out.read_text(encoding="utf-8"))
    assert res["dirty_before"] is True and res["dirty_content_after"] == [] and res["package"] == c.MASTER_FIGURE


def test_refresh_carrier_dry_run_from_spec(tmp_path, capsys):
    fbx = tmp_path / "art/x/export/SK_Achilles_H2.fbx"
    fbx.parent.mkdir(parents=True)
    fbx.write_bytes(b"fbx")
    wj(tmp_path / "spec.json", {"ue_hero": "Achilles", "target": {"sk_fbx": "art/x/export/SK_Achilles_H2.fbx"}})
    args = ["--key", "Achilles", "--spec", "spec.json", "--out", "r.json", "--repo", str(tmp_path), "--dry-run"]
    assert refresh_carrier.main(args) == 0
    plan = json.loads(capsys.readouterr().out)
    assert plan["args"]["mesh"] == "/Game/PipelineCandidates/Achilles/Rig/SK_Achilles"
    assert plan["args"]["skeleton"].endswith("/Rig/SK_Achilles_Skeleton") and plan["args"]["fbx"].endswith(".fbx")
    assert refresh_carrier.main(["--key", "Angel", "--spec", "spec.json", "--out", "r.json", "--repo", str(tmp_path),
                                 "--dry-run"]) == 2  # спека другого героя
    assert refresh_carrier.main(["--key", "Achilles", "--fbx", "missing.fbx", "--out", "r.json", "--repo",
                                 str(tmp_path), "--dry-run"]) == 2


@pytest.mark.parametrize("tool", ["discard_master", "delete_prev", "refresh_carrier", "prep_acceptance",
                                  "write_import_profile", "write_review_config"])
def test_every_tool_has_help(tool, capsys):
    mod = __import__(tool)
    assert mod.main(["--help"]) == 0
    assert "usage" in capsys.readouterr().out.lower()
    assert mod.__doc__.splitlines()[0].strip()  # README-строка в начале файла


# ---------------------------------------------------------------------------------------- подготовка приёмки клипов
TEMPLATE = """# Приёмка клипа AM_Testo_{clip}, цикл {{{{CYCLE}}}}

<!-- ЗАГОТОВКА этапа 6: подставить {{{{E}}}} … -->

## Вход
- Кадры: {{{{E}}}}/{clip}/frames/ — {{{{FRAMES_FILES_JSON}}}}
- Предыдущая карточка: {{{{PREVIOUS_CARD_JSON}}}} (null на r1).
- Клип: accepted_object [{{"path": "{fbx}", "sha256": "{sha}"}}]
   date "{{{{DATE}}}}", cycle "{{{{CYCLE}}}}"
"""


def jpg(path: Path, size=(64, 48), colour=(120, 90, 60)) -> Path:
    from PIL import Image

    path.parent.mkdir(parents=True, exist_ok=True)
    Image.new("RGB", size, colour).save(path, "JPEG", quality=90)
    return path


def make_clip_repo(root: Path, clips=("Idle", "LungeAttack"), template=None):
    adir = root / "art/pipeline-candidates/ASSET-TESTO-001"
    run = adir / "20261014-h2anim"
    spec = wj(adir / "build-profiles/testo-h2anim.json",
              {"ue_hero": "Testo", "clips": {cl: {"key_frames": [0, 7]} for cl in clips}})
    pv = run / "preview"
    for cl in clips:
        jpg(pv / f"Testo-{cl}-blender-sheet.jpg", (840, 1260))          # лист Blender (пилот 1680 × 2520)
        jpg(pv / f"closeups-blender/Testo-{cl}-f04-q34.jpg", (1100, 1100))
        jpg(pv / f"ue/Testo-{cl}-f00-front-ue-editor.jpg", (1920, 1080))  # UE-кадр как в пилоте
        for rel in (f"ue/Testo-{cl}-f00-q34-ue-editor.jpg", f"ue/Testo-{cl}-f07-front-ue-editor.jpg",
                    f"ue/Testo-{cl}-f07-q34-ue-editor.jpg"):
            jpg(pv / rel)
    jpg(pv / "ue/Testo-LungeAttack-f07-closeup-ue-editor.jpg")
    jpg(pv / "Testo-H2Anim-ue-sheet.jpg", (4200, 1860))                  # UE-лист пилота
    fbx_rel = "art/pipeline-candidates/ASSET-TESTO-001/20261014-h2anim/export/AM_Testo.fbx"
    (root / fbx_rel).parent.mkdir(parents=True, exist_ok=True)
    (root / fbx_rel).write_bytes(b"clip-v1")
    for cl in clips:
        t = adir / "evidence/acceptance-anim-prompts" / cl / "acceptor-prompt.md"
        t.parent.mkdir(parents=True, exist_ok=True)
        t.write_text((template or TEMPLATE).format(clip=cl, fbx=fbx_rel, sha=c.sha256(root / fbx_rel)), encoding="utf-8")
    (adir / "evidence/acceptance-anim-prompts/run-acceptor.ps1").write_text("# ps1", encoding="utf-8")
    return adir, run, spec, fbx_rel


def test_prep_acceptance_r1_then_r2(tmp_path):
    adir, run, spec, fbx_rel = make_clip_repo(tmp_path)
    base = ["--asset-dir", str(adir), "--key", "Testo", "--date", "2026-10-14", "--repo", str(tmp_path)]
    assert prep_acceptance.main(base + ["--run", str(run), "--spec", str(spec), "--cycle", "r1"]) == 0
    e1 = adir / "evidence/acceptance-anim/20261014-r1"
    lunge = (e1 / "LungeAttack/acceptor-prompt.md").read_text(encoding="utf-8")
    files = sorted(p.name for p in (e1 / "LungeAttack/frames").iterdir())
    assert len(files) == 8 and "Testo-LungeAttack-f07-closeup-ue-editor.jpg" in files
    assert "{{" not in lunge and "<!--" not in lunge and 'cycle "r1"' in lunge and "null (null на r1)" in lunge
    assert "art/pipeline-candidates/ASSET-TESTO-001/evidence/acceptance-anim/20261014-r1/LungeAttack/frames/" in lunge
    assert lunge.index("- UE-кадры") < lunge.index("- Клип:") and "/Rig/SK_Testo" in lunge
    assert (e1 / "run-acceptor.ps1").is_file()
    # карточки r1 → r2 на новом прогоне; клип перепечён → без --refresh-sha отказ
    for cl in ("Idle", "LungeAttack"):
        wj(e1 / cl / "card.json", {"frames": {"files": sorted(p.name for p in (e1 / cl / "frames").iterdir())}})
    run3 = adir / "20261014-h2anim-r3"
    import shutil
    shutil.copytree(run / "preview", run3 / "preview")
    (tmp_path / fbx_rel).write_bytes(b"clip-v2")
    r2 = base + ["--run", str(run3), "--cycle", "r2", "--previous", str(e1)]
    assert prep_acceptance.main(r2) == 2
    assert prep_acceptance.main(r2 + ["--refresh-sha", "--replace", "цикл {{CYCLE}}=цикл {{CYCLE}} (модель r3)"]) == 0
    e2 = adir / "evidence/acceptance-anim/20261014-r2"
    idle = (e2 / "Idle/acceptor-prompt.md").read_text(encoding="utf-8")
    assert '"art/pipeline-candidates/ASSET-TESTO-001/evidence/acceptance-anim/20261014-r1/Idle/card.json"' in idle
    assert c.sha256(tmp_path / fbx_rel) in idle and "(модель r3)" in idle
    assert sorted(p.name for p in (e2 / "Idle/frames").iterdir()) == \
        json.loads((e1 / "Idle/card.json").read_text(encoding="utf-8"))["frames"]["files"]


def test_prep_acceptance_dry_run_reports_missing_frame(tmp_path, capsys):
    adir, run, spec, _ = make_clip_repo(tmp_path)
    (run / "preview/Testo-H2Anim-ue-sheet.jpg").unlink()
    args = ["--asset-dir", str(adir), "--key", "Testo", "--date", "2026-10-14", "--repo", str(tmp_path),
            "--run", str(run), "--spec", str(spec), "--cycle", "r1"]
    assert prep_acceptance.main(args + ["--dry-run"]) == 0
    assert any("H2Anim-ue-sheet" in p for p in json.loads(capsys.readouterr().out)["problems"])
    assert prep_acceptance.main(args) == 2
    assert not (adir / "evidence/acceptance-anim/20261014-r1").exists()


def r1_args(adir, run, spec, root):
    return ["--asset-dir", str(adir), "--key", "Testo", "--date", "2026-10-14", "--repo", str(root),
            "--run", str(run), "--spec", str(spec), "--cycle", "r1"]


def test_prep_acceptance_frames_fit_1200_px_originals_untouched(tmp_path, capsys):
    """Ревью 2026-10-14 R-03 (ДС-8): копии кадров клипа ≤ 1200 px по длинной стороне, JPEG q92; листы — целиком."""
    from PIL import Image

    adir, run, spec, _ = make_clip_repo(tmp_path)
    pv = run / "preview"
    before = {p: c.sha256(p) for p in pv.rglob("*.jpg")}
    assert prep_acceptance.main(r1_args(adir, run, spec, tmp_path)) == 0
    assert "resized 3 to <= 1200 px" in capsys.readouterr().out          # лист Blender, UE-кадр 1920, UE-лист
    fr = adir / "evidence/acceptance-anim/20261014-r1/LungeAttack/frames"
    sizes = {p.name: Image.open(p).size for p in fr.iterdir()}
    assert sizes["Testo-H2Anim-ue-sheet.jpg"] == (1200, 531)               # 4200 × 1860: уменьшен целиком
    assert sizes["Testo-LungeAttack-blender-sheet.jpg"] == (800, 1200)
    assert sizes["Testo-LungeAttack-f00-front-ue-editor.jpg"] == (1200, 675)
    assert sizes["Testo-LungeAttack-f04-q34.jpg"] == (1100, 1100)
    assert max(max(s) for s in sizes.values()) <= 1200 and len(sizes) == 8
    assert Image.open(fr / "Testo-H2Anim-ue-sheet.jpg").format == "JPEG"
    small = "Testo-LungeAttack-f07-q34-ue-editor.jpg"                    # не больше предела — байт в байт
    assert c.sha256(fr / small) == c.sha256(pv / "ue" / small)
    assert {p: c.sha256(p) for p in pv.rglob("*.jpg")} == before          # оригиналы не тронуты
    # --max-px 0 — копия как есть (прежнее поведение)
    assert prep_acceptance.main(r1_args(adir, run, spec, tmp_path) + ["--max-px", "0", "--evidence", "ev-asis"]) == 0
    sheet = tmp_path / "ev-asis/Idle/frames/Testo-H2Anim-ue-sheet.jpg"
    assert c.sha256(sheet) == c.sha256(pv / "Testo-H2Anim-ue-sheet.jpg")


def test_copy_frame_png_and_unreadable(tmp_path):
    from PIL import Image

    src = tmp_path / "a.png"
    Image.new("RGBA", (1600, 800), (10, 20, 30, 255)).save(src)
    rec = prep_acceptance.copy_frame(src, tmp_path / "out.png", 1200)
    assert rec == {"name": "out.png", "resized": True, "px": [1200, 600], "source_px": [1600, 800]}
    with Image.open(tmp_path / "out.png") as im:
        assert (im.format, im.size) == ("PNG", (1200, 600))
    bad = tmp_path / "bad.jpg"
    bad.write_bytes(b"not an image")
    with pytest.raises(OSError):
        prep_acceptance.copy_frame(bad, tmp_path / "bad-out.jpg", 1200)


def test_prep_acceptance_unreadable_frame_is_an_error(tmp_path, capsys):
    adir, run, spec, _ = make_clip_repo(tmp_path)
    (run / "preview/ue/Testo-Idle-f07-q34-ue-editor.jpg").write_bytes(b"broken")
    assert prep_acceptance.main(r1_args(adir, run, spec, tmp_path)) == 2
    assert "не читается как картинка" in capsys.readouterr().err


TEMPLATE_KL = TEMPLATE.replace("- Клип:", "- Известные пределы этой фигуры: {{{{KNOWN_LIMITS}}}}\n- Клип:")


def test_prep_acceptance_known_limits_placeholder(tmp_path, capsys):
    """F141/F156, ревью R-14: {{KNOWN_LIMITS}} — из <prompts>/known-limits.md, один список во все промпты героя."""
    adir, run, spec, _ = make_clip_repo(tmp_path, template=TEMPLATE_KL)
    args = r1_args(adir, run, spec, tmp_path)
    assert prep_acceptance.main(args + ["--dry-run"]) == 0
    out = json.loads(capsys.readouterr().out)
    assert out["known_limits"] is None and any("{{KNOWN_LIMITS}}" in p for p in out["problems"])
    assert prep_acceptance.main(args) == 2                                 # заготовка ждёт список, файла нет
    assert "known-limits.md" in capsys.readouterr().err
    kl = adir / "evidence/acceptance-anim-prompts/known-limits.md"
    kl.write_text("<!-- этап 6: один список на фигуру -->\nщит без кости; кромка плаща у подмышки\n", encoding="utf-8")
    assert prep_acceptance.main(args) == 0
    e1 = adir / "evidence/acceptance-anim/20261014-r1"
    for cl in ("Idle", "LungeAttack"):
        text = (e1 / cl / "acceptor-prompt.md").read_text(encoding="utf-8")
        assert "- Известные пределы этой фигуры: щит без кости; кромка плаща у подмышки\n" in text
        assert "{{" not in text and "<!--" not in text
    own = tmp_path / "limits-empty.md"
    own.write_text("<!-- всё закрыто поздним фиксом -->\n", encoding="utf-8")
    assert prep_acceptance.main(args + ["--known-limits", str(own), "--evidence", "ev-own"]) == 0
    assert "пределы этой фигуры: нет\n" in (tmp_path / "ev-own/Idle/acceptor-prompt.md").read_text(encoding="utf-8")
    assert prep_acceptance.main(args + ["--known-limits", str(tmp_path / "missing.md")]) == 2
    with pytest.raises(prep_acceptance.PrepError):
        prep_acceptance.fill_prompt("- a: {{KNOWN_LIMITS}}\n- Клип: x", e_rel="e", date="d", cycle="r1",
                                    previous_card=None, files=[], note="")


def test_prep_acceptance_known_limits_file_without_placeholder_warns(tmp_path, capsys):
    adir, run, spec, _ = make_clip_repo(tmp_path)                          # заготовка пилота: блок текстом
    (adir / "evidence/acceptance-anim-prompts/known-limits.md").write_text("щит без кости", encoding="utf-8")
    assert prep_acceptance.main(r1_args(adir, run, spec, tmp_path)) == 0
    assert "WARNING" in capsys.readouterr().err
    text = (adir / "evidence/acceptance-anim/20261014-r1/Idle/acceptor-prompt.md").read_text(encoding="utf-8")
    assert "щит без кости" not in text


# ------------------------------------------------------------------------------ профиль импорта и конфиг съёмки
def make_profile_repo(root: Path):
    adir = root / "art/pipeline-candidates/ASSET-TESTO-001"
    adir.mkdir(parents=True)
    (adir / "asset-card.yaml").write_text("ASSET_ID: ASSET-TESTO-001\nCONTENT_KEY: testo\nKEY: Testo\n", encoding="utf-8")
    ld = adir / "20261014-h2-lookdev-r2"
    (ld / "textures").mkdir(parents=True)
    (ld / "textures/T_UM_MatLUT_Testo.dds").write_bytes(b"lut")
    (ld / "textures/T_Testo_H2LD_TeamAccent_2K.png").write_bytes(b"ta")
    wj(ld / "reports/ld-team-accent-report.json", {"team_dye_gain": {"accent_Y_p50_p95": [0.04, 0.12]}})
    tris = {"SK_Testo_H2_Body": 40000, "SK_Testo_H2_Spear": 1200, "SM_Testo_H2_Base": 1348}
    wj(ld / "reports/ld-fbx-report.json", {"checks": {"triangles_as_h21": {"measured": tris}}})
    wj(ld / "reports/measure-report.json", {})
    bk = adir / "20261014-h2-bake-r2"
    wj(bk / "reports/rig-report.json", {"expected_ue_bounds_uu_at_import_scale_1": {
        "base": {"min": [-15.0, -14.0, 0.0], "max": [15.0, 14.0, 6.0]}}})
    wj(bk / "reports/prepare-report.json", {"parts": {"tripo_part_6": {"final_bounds_m": [[0, 0, 0.4], [0, 0, 0.55]]},
                                                      "tripo_part_4": {"final_bounds_m": [[0, 0, 0.1], [0, 0, 0.3]]}}})
    lp = wj(adir / "build-profiles/testo-h2-lookdev-r2.json", {"profile_id": "testo-h2-lookdev/2"})
    tpl = wj(root / "art/pipeline-candidates/ASSET-TMPL-001/build-profiles/tmpl-h2ld-lookdev-ue-import-r3.json", {
        "profile_id": "tmpl-h2ld-lookdev-ue-import/3", "asset_id": "ASSET-TMPL-001", "status_note": "Tmpl note",
        "derived_from": ["art/pipeline-candidates/ASSET-TMPL-001/x.json"], "history": {"previous": {"path": "p"}},
        "candidate": {"dir": "art/pipeline-candidates/ASSET-TMPL-001/ld", "figure_top_part": "tripo_part_4",
                      "library_inputs": {"LUT": {"note": "n"}, "TeamAccent": {}}},
        "scale": {"figure_height_m": 0.55, "top_part": "tripo_part_4"},
        "meshes": {"body": {"object": "SK_Tmpl_H2_Body"}, "weapon": {"object": "SK_Tmpl_H2_Sword", "bone": "weapon.R"},
                   "base": {"object": "SM_Tmpl_H2_Base"}},
        "ue": {"target_skeleton": "/Game/PipelineCandidates/Tmpl/Rig/SK_Tmpl_Skeleton", "skeletal_asset": "SK_Tmpl_H2LD",
               "figure_instance": "MI_Tmpl_H2LD", "team_instances": {"figure": "MI_Tmpl_H2LD_{team}"}}})
    return adir, ld, bk, lp, tpl, tris


def test_write_import_profile_from_other_hero(tmp_path):
    adir, ld, bk, lp, tpl, tris = make_profile_repo(tmp_path)
    note = tmp_path / "note.txt"
    note.write_text("Testo stage 7a", encoding="utf-8")
    out = tmp_path / "out.json"
    base = ["--template", str(tpl), "--asset-dir", str(adir), "--lookdev-run", str(ld), "--lookdev-profile", str(lp),
            "--bake-run", str(bk), "--profile-id", "testo-h2ld-lookdev-ue-import/1", "--repo", str(tmp_path),
            "--out", str(out)]
    assert wip.main(base) == 2  # шаблонный меч и верх части чужого героя
    assert wip.main(base + ["--status-note-file", str(note), "--set", "meshes.weapon.object=SK_Testo_H2_Spear",
                            "--set", "candidate.figure_top_part=tripo_part_6", "--set", "scale.top_part=tripo_part_6"]) == 0
    p = json.loads(out.read_text(encoding="utf-8"))
    assert p["asset_id"] == "ASSET-TESTO-001" and p["status_note"] == "Testo stage 7a"
    assert p["ue"]["target_skeleton"] == "/Game/PipelineCandidates/Testo/Rig/SK_Testo_Skeleton"
    assert p["ue"]["team_instances"]["figure"] == "MI_Testo_H2LD_{team}"
    assert p["ue"]["figure_parameters"] == {"TeamDye": 1.0, "TeamDyeGain": 20.0, "TeamDyeCeiling": 7.5}
    assert p["expectations"]["triangles"] == tris
    assert p["meshes"]["base"]["footprint_m"] == [0.3, 0.28, 0.06]
    assert p["candidate"]["library_inputs"]["LUT"]["sha256"] == c.sha256(ld / "textures/T_UM_MatLUT_Testo.dds")
    assert p["candidate"]["bake_profile_id"] == "testo-h2-lookdev/2"
    assert p["candidate"]["extra_reports"]["source_rig_report"] == "../20261014-h2-bake-r2/reports/rig-report.json"
    assert p["derived_from"][0].startswith("art/pipeline-candidates/ASSET-TMPL-001/build-profiles/") and "history" not in p
    assert not c.leftovers({k: v for k, v in p.items() if k != "derived_from"}, "Tmpl")


def test_write_import_profile_new_revision_of_own(tmp_path):
    adir, ld, bk, lp, tpl, tris = make_profile_repo(tmp_path)
    own = wj(adir / "build-profiles/testo-h2ld-lookdev-ue-import-r1.json", {
        "profile_id": "testo-h2ld-lookdev-ue-import/1", "asset_id": "ASSET-TESTO-001", "status_note": "rev 1.",
        "derived_from": ["a"], "scale": {"figure_height_m": 0.55, "top_part": "tripo_part_6"},
        "meshes": {"body": {"object": "SK_Testo_H2_Body"}},
        "ue": {"target_skeleton": "/Game/PipelineCandidates/Testo/Rig/SK_Testo_Skeleton"}})
    p = wip.build(json.loads(own.read_text(encoding="utf-8")), repo=tmp_path, key="Testo",
                  asset_id="ASSET-TESTO-001", content_key="testo", lookdev_run=str(ld), lookdev_profile=None,
                  bake_run=str(bk), profile_id="testo-h2ld-lookdev-ue-import/2", rev_note=" Rev 2.",
                  previous=str(own), previous_run="run-r1", template_rel="t.json")
    assert p["status_note"] == "rev 1. Rev 2." and p["derived_from"] == [
        "t.json (template; tools/tripo-pipeline/ue7a/write_import_profile.py)", "a"]
    assert p["history"]["previous"] == {"path": c.rel(own, tmp_path), "sha256": c.sha256(own), "run": "run-r1"}


def test_write_review_config(tmp_path):
    adir, ld, bk, lp, tpl, tris = make_profile_repo(tmp_path)
    run = adir / "20261014-h2ld-ue-import"
    run.mkdir()
    prof = wj(adir / "build-profiles/p.json", {"ue": {"figure_parameters": {"TeamDye": 1.0, "TeamDyeGain": 20.0}}})
    concept = tmp_path / "art/imagegen/concept-testo-codex/testo-front.png"
    concept.parent.mkdir(parents=True)
    concept.write_bytes(b"png")
    t = wj(tmp_path / "tmpl-review-config.json", {
        "hero": "Tmpl", "run_dir": "art/pipeline-candidates/ASSET-TMPL-001/run", "note": "Tmpl",
        "concept": {"front": "art/imagegen/concept-tmpl-codex/tmpl-front.png"}, "debug_calibration": {"a": 1},
        "zones": ["linen", "skin"], "anchor_zone": "linen",
        "variants": {"P1": "/Game/PipelineCandidates/Tmpl/H2LD/Materials/MI_Tmpl_H2LD_P1"},
        "verify": {"hero_root": "/Game/PipelineCandidates/Tmpl", "expect": {"triangles": 1},
                   "instances": {"figure_instance": {"scalars": {"TeamDyeGain": 9.0}}}}})
    out = tmp_path / "rc.json"
    args = ["--template", str(t), "--asset-dir", str(adir), "--run-dir", str(run), "--height-uu", "54.99",
            "--lookdev-run", str(ld), "--clips-run", str(adir / "20261014-h2anim"), "--import-profile", str(prof),
            "--drop", "debug_calibration", "--set", "note=Testo look-dev", "--repo", str(tmp_path), "--out", str(out)]
    assert wrc.main(args) == 2 and not out.exists()   # R-09: якорь чужого героя не наследуется
    assert wrc.main(args + ["--set", "anchor_zone=bronze"]) == 2   # не из zones героя
    assert wrc.main(args + ["--set", "anchor_zone=skin"]) == 0
    cfg = json.loads(out.read_text(encoding="utf-8"))
    assert cfg["anchor_zone"] == "skin"
    assert cfg["hero"] == "Testo" and cfg["run_dir"] == "art/pipeline-candidates/ASSET-TESTO-001/20261014-h2ld-ue-import"
    assert cfg["variants"]["P1"] == "/Game/PipelineCandidates/Testo/H2LD/Materials/MI_Testo_H2LD_P1"
    assert cfg["concept"]["front"] == "art/imagegen/concept-testo-codex/testo-front.png"
    v = cfg["verify"]
    assert v["height_uu"] == 54.99 and v["expect"]["triangles"] == 41200  # тело + копьё, без подставки
    assert v["instances"]["figure_instance"]["scalars"] == {"TeamDye": 1.0, "TeamDyeGain": 20.0}
    assert v["clips_reference"].endswith("20261014-h2anim/reports/ue-measure-clips.json")
    assert "debug_calibration" not in cfg and cfg["note"] == "Testo look-dev"
    assert cfg["concept_zones"].endswith("20261014-h2-lookdev-r2/reports/measure-report.json")
    # свой прошлый конфиг как шаблон — якорь остаётся как был, --set не нужен (прежнее поведение)
    out2 = tmp_path / "rc-r2.json"
    assert wrc.main(["--template", str(out), "--asset-dir", str(adir), "--run-dir", str(run), "--repo", str(tmp_path),
                     "--out", str(out2)]) == 0
    assert json.loads(out2.read_text(encoding="utf-8"))["anchor_zone"] == "skin"


def test_write_review_config_anchor_message(capsys):
    with pytest.raises(wrc.ConfigError, match=r"--set anchor_zone=<зона Testo> \(одна из zones: linen, skin\)"):
        wrc.check_anchor_zone({"zones": ["linen", "skin"], "anchor_zone": "linen"}, {"anchor_zone": "linen"},
                              "Testo", "Tmpl", sets=["note=x"])
    wrc.check_anchor_zone({"anchor_zone": "fur"}, {}, "Testo", "Tmpl", set_jsons=['anchor_zone="fur"'])  # без zones
