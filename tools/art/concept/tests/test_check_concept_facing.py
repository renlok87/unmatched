"""check_concept_views.py --side-ortho (F8): ракурс бокового вида против ортопроекции черновика 1b на синтетике.

    python -m pytest tools/art/concept/tests/test_check_concept_facing.py -q
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageOps

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))

import check_concept_views as C  # noqa: E402

W, H = 600, 800


def profile(bg=(46, 46, 46), body=(150, 60, 50), size=(W, H)):
    """Профиль на подставке: тело, голова и длинная рука-копьё вперёд вправо — силуэт несимметричен."""
    w, h = size
    im = Image.new("RGB", size, bg)
    d = ImageDraw.Draw(im)
    d.ellipse([0.25 * w, 0.86 * h, 0.75 * w, 0.93 * h], fill=(70, 65, 60))
    d.rectangle([0.42 * w, 0.30 * h, 0.58 * w, 0.88 * h], fill=body)
    d.ellipse([0.44 * w, 0.18 * h, 0.60 * w, 0.32 * h], fill=(200, 170, 150))
    d.rectangle([0.56 * w, 0.40 * h, 0.92 * w, 0.45 * h], fill=body)      # рука вперёд
    d.rectangle([0.86 * w, 0.10 * h, 0.89 * w, 0.80 * h], fill=(120, 100, 70))  # копьё
    return im


def make(tmp_path: Path, side: Image.Image, ortho: Image.Image):
    s = tmp_path / "set"
    s.mkdir()
    for v in ("front", "back"):
        profile().save(s / f"hero-{v}.png")
    side.save(s / "hero-side.png")
    o = tmp_path / "ortho_left.png"
    ortho.save(o)
    return s, o


def run(set_dir: Path, ortho: Path, *extra):
    out = set_dir.parent / "out"
    code = C.main(["--set", str(set_dir), "--key", "hero", "--out", str(out), "--side-ortho", str(ortho), *extra])
    rep = json.loads((out / "checks-report.json").read_text(encoding="utf-8")) if (out / "checks-report.json").exists() else None
    return code, rep


def facing(rep):
    return next(c for c in rep["checks"] if c["id"] == "view.facing")


def ortho_render():
    # черновой рендер: светлая фигура на тёмном фоне, кадр другого размера (вид растягивается на кадр орто)
    return profile(bg=(20, 20, 20), body=(210, 210, 210)).resize((660, 880))


def test_same_side_passes(tmp_path):
    code, rep = run(*make(tmp_path, profile(), ortho_render()))
    assert code == 0
    f = facing(rep)
    assert f["result"] == "PASS" and f["value"]["verdict"] == "OK" and f["scope"] == "side"
    assert rep["facing"]["iou_direct"] > rep["facing"]["iou_mirror"] + 0.05
    assert len(rep["facing"]["ortho_sha256"]) == 64


def test_mirrored_side_fails(tmp_path):
    code, rep = run(*make(tmp_path, ImageOps.mirror(profile()), ortho_render()))
    assert code == 1
    assert facing(rep)["result"] == "FAIL" and facing(rep)["value"]["verdict"] == "MIRRORED"


def test_symmetric_silhouette_is_warn(tmp_path):
    sym = Image.new("RGB", (W, H), (46, 46, 46))
    d = ImageDraw.Draw(sym)
    d.ellipse([0.25 * W, 0.86 * H, 0.75 * W, 0.93 * H], fill=(70, 65, 60))
    d.rectangle([0.42 * W, 0.20 * H, 0.58 * W, 0.88 * H], fill=(150, 60, 50))
    code, rep = run(*make(tmp_path, sym, sym))
    assert facing(rep)["result"] == "WARN" and facing(rep)["value"]["verdict"] == "UNCLEAR"


def test_without_flag_no_facing_and_bad_view_is_input_error(tmp_path):
    s, o = make(tmp_path, profile(), ortho_render())
    out = tmp_path / "plain"
    assert C.main(["--set", str(s), "--key", "hero", "--out", str(out)]) == 0
    rep = json.loads((out / "checks-report.json").read_text(encoding="utf-8"))
    assert "facing" not in rep and not any(c["id"] == "view.facing" for c in rep["checks"])
    assert C.main(["--set", str(s), "--key", "hero", "--out", str(out), "--side-ortho", str(o),
                   "--side-view", "left"]) == 2
