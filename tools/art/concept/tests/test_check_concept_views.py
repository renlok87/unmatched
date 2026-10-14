"""check_concept_views.py на синтетических наборах (без Blender/сети): схема отчёта, коды выхода, каждая проверка
ловит свой дефект, сырые файлы не меняются.

    python -m pytest tools/art/concept/tests -q
"""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

import numpy as np
import pytest
from PIL import Image, ImageDraw

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))

import check_concept_views as C  # noqa: E402

W, H = 600, 800


def figure(bg=(30, 31, 34), size=(W, H), base_bottom=0.93, top=0.05, cx=0.5, vignette=12.0, extra=False,
           body=(150, 60, 50), base=(70, 65, 60)):
    """Фигура на подставке: эллиптическая подставка, тело-трапеция, голова. Фон с мягкой виньеткой."""
    w, h = size
    yy, xx = np.mgrid[0:h, 0:w]
    r = np.sqrt(((xx - w / 2) / (w / 2)) ** 2 + ((yy - h / 2) / (h / 2)) ** 2)
    a = np.empty((h, w, 3), np.float64)
    for k in range(3):
        a[..., k] = bg[k] + vignette * (0.5 - r)  # центр светлее, углы темнее
    im = Image.fromarray(np.clip(a, 0, 255).astype(np.uint8))
    d = ImageDraw.Draw(im)
    bx, bb, tp = cx * w, base_bottom * h, top * h
    fig_h = bb - tp
    bw = 0.5 * w
    bh = 0.08 * fig_h
    d.rectangle([bx - bw / 2, bb - bh, bx + bw / 2, bb - bh / 2], fill=base)
    d.ellipse([bx - bw / 2, bb - bh * 0.7, bx + bw / 2, bb], fill=base)
    d.ellipse([bx - bw / 2, bb - bh * 1.3, bx + bw / 2, bb - bh * 0.7], fill=tuple(c + 20 for c in base))
    d.polygon([(bx - 0.18 * w, bb - bh), (bx + 0.18 * w, bb - bh), (bx + 0.1 * w, tp + 0.18 * fig_h),
               (bx - 0.1 * w, tp + 0.18 * fig_h)], fill=body)
    d.ellipse([bx - 0.07 * w, tp, bx + 0.07 * w, tp + 0.2 * fig_h], fill=(200, 170, 150))
    if extra:
        d.ellipse([0.05 * w, 0.4 * h, 0.05 * w + 0.12 * w, 0.4 * h + 0.12 * w], fill=(200, 200, 40))
    return im


def make_set(tmp_path: Path, key="test-hero", overrides=None, views=("front", "side", "back"), **common):
    set_dir = tmp_path / "set"
    set_dir.mkdir(parents=True, exist_ok=True)
    overrides = overrides or {}
    for v in views:
        kw = dict(common)
        kw.update(overrides.get(v, {}))
        figure(**kw).save(set_dir / f"{key}-{v}.png")
    return set_dir


def run(set_dir: Path, key="test-hero", *extra):
    out = set_dir.parent / "out"
    code = C.main(["--set", str(set_dir), "--key", key, "--out", str(out), *extra])
    rep = out / "checks-report.json"
    report = json.loads(rep.read_text(encoding="utf-8")) if rep.exists() else None
    return code, report, out


def result(report, cid, scope=None):
    rows = [c for c in report["checks"] if c["id"] == cid and (scope is None or c["scope"] == scope)]
    assert rows, cid
    return rows[0]["result"]


def test_consistent_set_passes_and_writes_sheet(tmp_path):
    set_dir = make_set(tmp_path)
    before = {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in set_dir.iterdir()}
    code, rep, out = run(set_dir, "test-hero", "--sheet")
    assert code == 0, [c for c in rep["checks"] if c["result"] == "FAIL"]
    assert rep["schema"] == "unmatched.concept-checks/1"
    assert rep["verdict"] == "PASS" and rep["summary"]["FAIL"] == 0
    assert rep["views"] == ["front", "side", "back"]
    assert {i["view"] for i in rep["inputs"]} == {"front", "side", "back"}
    assert all(len(i["sha256"]) == 64 for i in rep["inputs"])
    m = rep["measurements"]["front"]["mask"]
    assert abs(m["bottom_pct"] - 93.0) < 0.6 and abs(m["top_pct"] - 5.0) < 0.6
    assert abs(m["base_center_x_pct"] - 50.0) < 0.6
    assert (out / "sheet-test-hero.png").is_file()
    sheet = Image.open(out / "sheet-test-hero.png").convert("RGB")
    assert (np.asarray(sheet) == np.array(C.GUIDE_RGB, np.uint8)).all(2).sum() > 500  # направляющие #00C8FF есть
    after = {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in set_dir.iterdir()}
    assert before == after  # сырые виды не тронуты, в каталог набора ничего не записано


def test_report_defaults_to_set_dir(tmp_path):
    set_dir = make_set(tmp_path)
    code = C.main(["--set", str(set_dir), "--key", "test-hero"])
    assert code == 0
    assert (set_dir / "checks-report.json").is_file()
    assert not (set_dir / "sheet-test-hero.png").exists()  # лист только с --sheet


@pytest.mark.parametrize("override,cid", [
    ({"side": {"base_bottom": 0.86}}, "set.base_bottom"),
    ({"back": {"cx": 0.6}}, "set.base_center"),
    ({"side": {"top": 0.15}}, "set.height"),
    ({"front": {"top": -0.02}}, "view.top_margin"),
    ({"front": {"base_bottom": 1.02}}, "view.bottom_margin"),
    ({"back": {"bg": (34, 30, 46)}}, "view.bg_neutral"),
    ({"back": {"bg": (60, 60, 60)}}, "set.bg_same"),
    ({"front": {"size": (W, H + 40)}}, "set.size"),
])
def test_each_defect_fails(tmp_path, override, cid):
    code, rep, _ = run(make_set(tmp_path, overrides=override))
    assert code == 1
    scope = next(iter(override)) if cid.startswith("view.") else "set"
    assert result(rep, cid, scope) == "FAIL"


def test_moderate_drift_is_warn_not_fail(tmp_path):
    # между числом Р-9 (WARN) и калиброванным порогом (FAIL)
    code, rep, _ = run(make_set(tmp_path, overrides={"side": {"base_bottom": 0.905}, "back": {"cx": 0.535}}))
    assert code == 0
    assert result(rep, "set.base_bottom") == "WARN"
    assert result(rep, "set.base_center") == "WARN"


def test_extra_component_and_midgray_are_warnings(tmp_path):
    code, rep, _ = run(make_set(tmp_path, bg=(128, 128, 128), overrides={"front": {"extra": True}}))
    assert code == 0
    assert result(rep, "view.single_component", "front") == "WARN"
    assert result(rep, "view.bg_dark", "front") == "WARN"


def test_frame_top_1a_is_warn_only_with_flag(tmp_path):
    # шаг 1a: верхняя точка выше y 4 % (живой тест Robin Hood: 3,3 %) — WARN view.frame_top, код 0
    set_dir = make_set(tmp_path, views=("front",), top=0.03)
    code, rep, _ = run(set_dir, "test-hero", "--views", "front", "--min-top-pct", "4")
    assert code == 0
    assert result(rep, "view.frame_top", "front") == "WARN"
    assert rep["frame"] == {"min_top_pct": 4.0}
    # без флага проверки нет (1c и принятые наборы с верхом 1,9–4 % её не получают)
    code, rep, _ = run(set_dir, "test-hero", "--views", "front")
    assert code == 0
    assert not [c for c in rep["checks"] if c["id"] == "view.frame_top"]
    assert rep["frame"] == {"min_top_pct": None}


def test_frame_top_1a_passes_inside_frame(tmp_path):
    set_dir = make_set(tmp_path, views=("front",), top=0.05)
    code, rep, _ = run(set_dir, "test-hero", "--views", "front", "--min-top-pct", "4")
    assert code == 0
    assert result(rep, "view.frame_top", "front") == "PASS"


def test_frame_top_bad_value_exit_2(tmp_path):
    set_dir = make_set(tmp_path, views=("front",))
    assert C.main(["--set", str(set_dir), "--key", "test-hero", "--views", "front", "--min-top-pct", "60"]) == 2
    assert C.main(["--set", str(set_dir), "--key", "test-hero", "--views", "front", "--min-top-pct", "x"]) == 2


def test_recheck_with_out_matches_without_generated_at(tmp_path):
    # перепроверка запускающего (concept-sheet.md §5.5 п.2): --out вне пакета, сравнение без generated_at и sheet
    set_dir = make_set(tmp_path)
    assert C.main(["--set", str(set_dir), "--key", "test-hero", "--sheet"]) == 0
    assert C.main(["--set", str(set_dir), "--key", "test-hero", "--sheet", "--out", str(tmp_path / "re")]) == 0
    a = json.loads((set_dir / "checks-report.json").read_text(encoding="utf-8"))
    b = json.loads((tmp_path / "re" / "checks-report.json").read_text(encoding="utf-8"))
    for d in (a, b):
        d.pop("generated_at")
        d.pop("sheet")
    assert a == b


def test_object_in_border_fails(tmp_path):
    set_dir = make_set(tmp_path)
    p = set_dir / "test-hero-front.png"
    im = Image.open(p)
    ImageDraw.Draw(im).rectangle([0, 0, W, 10], fill=(220, 220, 220))  # полоса по верхней рамке
    im.save(p)
    code, rep, _ = run(set_dir)
    assert code == 1
    assert result(rep, "view.border_uniform", "front") == "FAIL"


def test_empty_frame_fails_mask(tmp_path):
    set_dir = make_set(tmp_path)
    Image.new("RGB", (W, H), (30, 31, 34)).save(set_dir / "test-hero-side.png")
    code, rep, _ = run(set_dir)
    assert code == 1
    assert result(rep, "view.mask", "side") == "FAIL"


def test_input_errors_exit_2(tmp_path):
    set_dir = make_set(tmp_path)
    assert C.main(["--set", str(set_dir), "--key", "test-hero", "--views", "front,left"]) == 2  # нет файла
    assert C.main(["--set", str(tmp_path / "nope"), "--key", "test-hero"]) == 2
    assert C.main(["--set", str(set_dir), "--key", "Test_Hero"]) == 2
    assert C.main(["--set", str(set_dir), "--key", "test-hero", "--views", "front,front"]) == 2
    bad = tmp_path / "bad.json"
    bad.write_text('{"main": [{"name": "x", "hex": "#GG0000"}]}', encoding="utf-8")
    assert C.main(["--set", str(set_dir), "--key", "test-hero", "--palette", str(bad)]) == 2
    assert C.main(["--set", str(set_dir), "--key", "test-hero", "--palette", str(tmp_path / "missing.json")]) == 2
    assert C.main(["--set", str(set_dir), "--key", "test-hero", "--role", "dragon"]) == 2


@pytest.mark.parametrize("data,n", [
    ({"main": [{"name": "green", "hex": "#3E6B2F"}, {"name": "brown", "hex": "6b4a2b"}],
      "accent": {"name": "red", "hex": "#B23A2E"}}, 3),
    ({"colors": ["#112233", {"name": "gold", "hex": "#C8A040"}]}, 2),
    (["#112233", "#445566"], 2),
    ({"robe": "#1F3A8A", "trim": "#C8A040", "note": "not a colour"}, 2),
])
def test_palette_formats(tmp_path, data, n):
    p = tmp_path / "palette.json"
    p.write_text(json.dumps(data), encoding="utf-8")
    pal = C.load_palette(p)
    assert len(pal) == n
    import re
    assert all(re.fullmatch(r"#[0-9A-F]{6}", s["hex"]) for s in pal)


def test_palette_from_set_dir_is_drawn(tmp_path):
    set_dir = make_set(tmp_path)
    (set_dir / "palette.json").write_text(json.dumps({"main": [{"name": "body", "hex": "#963C32"}],
                                                      "accent": {"name": "gold", "hex": "#00FF00"}}),
                                          encoding="utf-8")
    code, rep, out = run(set_dir, "test-hero", "--sheet")
    assert code == 0
    sw = {s["name"]: s for s in rep["palette"]["swatches"]}
    assert sw["body"]["figure_share_within_40_pct"] > 20.0  # цвет тела присутствует
    assert sw["gold"]["figure_share_within_40_pct"] == 0.0
    sheet = np.asarray(Image.open(out / "sheet-test-hero.png").convert("RGB"))
    assert (sheet == np.array([0, 255, 0], np.uint8)).all(2).sum() > 1000  # свотч нарисован


def test_palette_asset_id_in_report_and_long_swatch_names_fit(tmp_path):
    """C13: asset_id palette.json (§4.5) попадает в отчёт; длинные имена свотчей не налезают на соседний свотч,
    все свотчи нарисованы."""
    set_dir = make_set(tmp_path)
    long_names = ["weathered oak shield wood", "iron grey chainmail rings", "fur brown wolf mantle", "gold torc"]
    pal = {"asset_id": "ASSET-TEST-HERO-001",
           "main": [{"name": n, "hex": h} for n, h in zip(long_names[:3], ("#8B6A43", "#5E6266", "#6E5236"))],
           "accent": {"name": long_names[3], "hex": "#00FF00"}}
    (set_dir / "palette.json").write_text(json.dumps(pal), encoding="utf-8")
    code, rep, out = run(set_dir, "test-hero", "--sheet")
    assert code == 0 and rep["palette"]["asset_id"] == "ASSET-TEST-HERO-001"
    sheet = np.asarray(Image.open(out / "sheet-test-hero.png").convert("RGB"))
    assert (sheet == np.array([0, 255, 0], np.uint8)).all(2).sum() > 1000  # последний (акцент) свотч нарисован
    font = C._font(17)
    pitch, labels = C.swatch_layout(C.load_palette(set_dir / "palette.json"), font, 2000)
    assert pitch >= C.SWATCH_PITCH_MIN
    for hx, name in labels:
        assert font.getlength(hx) <= pitch - C.SWATCH_LABEL_GAP and font.getlength(name) <= pitch - C.SWATCH_LABEL_GAP
    tight, cut = C.swatch_layout([{"hex": "#000000", "name": "x" * 80}] * 4, font, 4 * 140)
    assert tight == 140 and cut[0][1].endswith("…") and font.getlength(cut[0][1]) <= 140 - C.SWATCH_LABEL_GAP
    (set_dir / "palette.json").write_text(json.dumps({"main": [{"name": "a", "hex": "#112233"}]}), encoding="utf-8")
    assert run(set_dir, "test-hero")[1]["palette"]["asset_id"] is None


def test_cli_subprocess_exit_code(tmp_path):
    import subprocess
    set_dir = make_set(tmp_path, overrides={"side": {"top": 0.15}})
    r = subprocess.run([sys.executable, str(HERE.parent / "check_concept_views.py"), "--set", str(set_dir),
                        "--key", "test-hero", "--out", str(tmp_path / "o")], capture_output=True, text=True,
                       encoding="utf-8", env={**__import__("os").environ, "PYTHONIOENCODING": "utf-8"})
    assert r.returncode == 1, r.stderr
    assert "set.height" in r.stdout


def _cp1251_env():
    import os
    env = {k: v for k, v in os.environ.items() if k not in ("PYTHONIOENCODING", "PYTHONUTF8")}
    env["PYTHONIOENCODING"] = "cp1251"  # как пайп Codex/PowerShell или Git Bash агента на русской Windows
    env["PYTHONUTF8"] = "0"
    return env


def test_cli_cp1251_pipe_clean_set_exit_0(tmp_path):
    """Печать «→» в пайп cp1251 не должна ронять инструмент: код 1 значит «есть FAIL», а не «сбой кодировки»."""
    import subprocess
    set_dir = make_set(tmp_path)
    r = subprocess.run([sys.executable, str(HERE.parent / "check_concept_views.py"), "--set", str(set_dir),
                        "--key", "test-hero", "--out", str(tmp_path / "o"), "--sheet"], capture_output=True,
                       env=_cp1251_env())
    out = r.stdout.decode("utf-8", "replace") + r.stderr.decode("utf-8", "replace")
    assert r.returncode == 0, out
    assert "Traceback" not in out and "PASS:" in out


def test_internal_crash_is_exit_2_not_fail(tmp_path, monkeypatch):
    set_dir = make_set(tmp_path)

    def boom(*a, **k):
        raise RuntimeError("synthetic")
    monkeypatch.setattr(C, "measure_view", boom)
    code, _, _ = run(set_dir)
    assert code == 2
