"""Тесты съёмки приёмки, волна 2 доработки скилла (W2-d): кадры приёмщика не больше 1200 px (RC-22, F97) и сравнение
с прежним циклом frames.json#changed_vs_previous (F151, RC-19). Без Blender.

    python -m pytest tools/art/acceptance/tests/test_capture_review.py -q
"""
import json
import sys
from pathlib import Path

import numpy as np
import pytest
from PIL import Image

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))

import capture_acceptance_set as cap  # noqa: E402

ACHILLES = cap.REPO / "art/pipeline-candidates/ASSET-ACHILLES-001/evidence/acceptance"


# ------------------------------------------------------------------ 1200 px по длинной стороне (RC-22, F97)

def test_fit_long_side_wide_tall_small():
    assert cap.fit_long_side(Image.new("RGB", (2645, 1138))).size == (1200, 516)
    assert cap.fit_long_side(Image.new("RGB", (1600, 1776))).size == (1081, 1200)
    small = Image.new("RGB", (900, 600))
    assert cap.fit_long_side(small) is small


def test_uv_layout_review_copy_is_1200_palette_and_coverage_unchanged(tmp_path):
    uv = np.array([[0.1, 0.1], [0.6, 0.1], [0.1, 0.6], [0.6, 0.6]], dtype=np.float32)
    np.savez(tmp_path / "uv.npz", **{"Body__uv": uv, "Body__tri": np.array([[0, 1, 2], [1, 3, 2]]),
                                     "Body__tri_island": np.array([0, 0]), "Body__bedge": np.array([[0, 1], [1, 3]])})
    Image.new("RGB", (256, 256), (180, 120, 60)).save(tmp_path / "bc.png")
    meta = cap.draw_uv_layout(tmp_path / "uv.npz", tmp_path / "bc.png", tmp_path / "uv-layout.png", {})
    im = Image.open(tmp_path / "uv-layout.png")
    assert max(im.size) == cap.REVIEW_PX and list(im.size) == meta["size_px"] and im.mode == "P"
    assert meta["drawn_px"][0] == cap.UV_SIZE  # покрытие считается на рисунке UV_SIZE, как до RC-22
    assert meta["coverage"] == pytest.approx(0.25, abs=0.01)


# ------------------------------------------------------------------ сравнение с прежним циклом (F151)

def _img(path, base=(90, 90, 90), patch=None, noise=0, seed=0, size=(200, 200)):
    a = np.full((size[1], size[0], 3), base, dtype=np.int16)
    if noise:
        rng = np.random.default_rng(seed)
        a += rng.integers(-noise, noise + 1, size=a.shape)
    if patch:
        x0, y0, x1, y1, delta = patch
        a[y0:y1 + 1, x0:x1 + 1] += delta
    Image.fromarray(np.clip(a, 0, 255).astype(np.uint8)).save(path)


def test_frame_diff_noise_is_unchanged_patch_is_changed(tmp_path):
    _img(tmp_path / "a.png")
    _img(tmp_path / "n.png", noise=7, seed=1)          # шум повторной съёмки: канал ≤ 7 (Achilles r2 → r3)
    _img(tmp_path / "p.png", patch=(20, 30, 29, 39, 60))
    _img(tmp_path / "w.png", size=(300, 200))
    n = cap.frame_diff(tmp_path / "a.png", tmp_path / "n.png")
    assert not n["changed"] and n["comparable"] and n["changed_px"] == 0 and n["max"] <= 7
    p = cap.frame_diff(tmp_path / "a.png", tmp_path / "p.png")
    assert p["changed"] and p["changed_px"] == 100 and p["bbox_px"] == [20, 30, 29, 39] and p["max"] == 60
    _img(tmp_path / "few.png", patch=(5, 5, 5, 6, 60))   # 2 пикселя < NOISE_MIN_PX — одиночные выбросы не считаются
    assert not cap.frame_diff(tmp_path / "a.png", tmp_path / "few.png")["changed"]
    w = cap.frame_diff(tmp_path / "a.png", tmp_path / "w.png")
    assert w["changed"] and not w["comparable"] and "200x200" in w["reason"]


def _cycle(root, name, files, fbx_sha="aa"):
    d = root / name / "frames"
    d.mkdir(parents=True)
    (d / "frames.json").write_text(json.dumps({"files": sorted(files + ["frames.json"]),
                                               "inputs": {"fbx": {"sha256": fbx_sha}}}), encoding="utf-8")
    return d


def test_find_previous_by_cycle_dir(tmp_path):
    r1 = _cycle(tmp_path, "20261013-r1", [])
    r2 = _cycle(tmp_path, "20261014-r2", [])
    assert cap.find_previous(r2) == r1
    assert cap.find_previous(r1) is None
    r2b = _cycle(tmp_path, "20261015-r2", [])
    r3 = tmp_path / "20261016-r3" / "frames"
    assert cap.find_previous(r3) == r2b           # две даты r2 — последняя по имени
    (tmp_path / "20261017-r4" / "frames").mkdir(parents=True)
    assert cap.find_previous(tmp_path / "20261018-r5" / "frames") is None  # r4 без frames.json
    assert cap.find_previous(tmp_path / "w2d-r3" / "frames") is None       # не каталог цикла: только --previous


def test_changed_vs_previous_block(tmp_path):
    prev = _cycle(tmp_path, "20261014-r1", ["a.jpg", "b.jpg", "tone.json", "old.jpg"], fbx_sha="aa")
    cur = tmp_path / "20261014-r2" / "frames"
    cur.mkdir(parents=True)
    for d in (prev, cur):
        _img(d / "a.jpg")
    _img(prev / "b.jpg")
    _img(cur / "b.jpg", patch=(50, 50, 80, 90, 40))
    _img(cur / "new.jpg")
    (prev / "tone.json").write_text(json.dumps({"t_cap": 2.0, "sources": {"measure_report": "r1/x.json"}}), "utf-8")
    (cur / "tone.json").write_text(json.dumps({"t_cap": 2.0, "sources": {"measure_report": "r2/x.json"}}), "utf-8")
    files = ["a.jpg", "b.jpg", "frames.json", "new.jpg", "tone.json"]
    r = cap.changed_vs_previous(prev, cur, files, fbx_sha="bb", source="test")
    assert r["changed"] == ["b.jpg", "new.jpg"] and r["unchanged"] == ["a.jpg", "tone.json"]
    assert r["not_comparable"] == ["new.jpg"] and r["removed"] == ["old.jpg"]
    assert r["previous"]["same_fbx"] is False and r["previous"]["fbx_sha256"] == "aa"
    bb = r["frames"]["b.jpg"]["bbox_px"]  # JPEG размывает край пятна на 1–2 пикселя
    assert "frames.json" not in r["frames"] and all(abs(x - y) <= 3 for x, y in zip(bb, [50, 50, 80, 90]))
    (cur / "tone.json").write_text(json.dumps({"t_cap": 1.5, "sources": {}}), "utf-8")
    assert "tone.json" in cap.changed_vs_previous(prev, cur, files)["changed"]


def test_pilot_achilles_r3_changed_only_pose02():
    """F151: Achilles r3 (правка только весов) против r2 — по пикселям изменён только pose-02."""
    r3 = ACHILLES / "20261014-r3" / "frames"
    if not (r3 / "frames.json").is_file() or not (ACHILLES / "20261014-r2" / "frames" / "frames.json").is_file():
        pytest.skip("нет кадров пилота Achilles r2/r3")
    assert cap.find_previous(r3) == ACHILLES / "20261014-r2" / "frames"
    man = json.loads((r3 / "frames.json").read_text(encoding="utf-8"))
    r = cap.changed_vs_previous(cap.find_previous(r3), r3, man["files"], man["inputs"]["fbx"]["sha256"])
    assert r["changed"] == ["pose-02.jpg"] and not r["not_comparable"] and r["previous"]["same_fbx"] is False
