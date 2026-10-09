"""Тесты чистых функций capture_acceptance_set.py (без Blender): выбор текстур, подставка, сборка кадра.

    python -m pytest tools/art/acceptance/tests -q
"""
import sys
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))

import capture_acceptance_set as cap  # noqa: E402


def touch(d, *names):
    for n in names:
        (d / n).write_bytes(b"")


def test_pick_texture_prefers_2k_and_skips_opengl(tmp_path):
    touch(tmp_path, "T_Hero_H2LD_BC.png", "T_Hero_H2LD_2K_BC.png", "T_Hero_H2LD_2K_N.png",
          "T_Hero_H2LD_2K_N_OpenGL.png", "T_Hero_H2LD_N.png")
    assert cap.pick_texture(tmp_path, "_BC", None).name == "T_Hero_H2LD_2K_BC.png"
    assert cap.pick_texture(tmp_path, "_N", None).name == "T_Hero_H2LD_2K_N.png"


def test_pick_texture_ambiguous_needs_key(tmp_path):
    touch(tmp_path, "T_A_H2LD_2K_ORM.png", "T_B_H2LD_2K_ORM.png")
    with pytest.raises(SystemExit):
        cap.pick_texture(tmp_path, "_ORM", None)
    assert cap.pick_texture(tmp_path, "_ORM", "B").name == "T_B_H2LD_2K_ORM.png"


def test_pick_texture_missing(tmp_path):
    with pytest.raises(SystemExit):
        cap.pick_texture(tmp_path, "_BC", None)


def test_find_base_sibling(tmp_path):
    fbx = tmp_path / "SK_Hero_H2LD.fbx"
    touch(tmp_path, fbx.name)
    assert cap.find_base(fbx) is None
    touch(tmp_path, "SM_Hero_H2LD_Base.fbx")
    assert cap.find_base(fbx).name == "SM_Hero_H2LD_Base.fbx"


def test_finish_frame_mask_and_border(tmp_path):
    from PIL import Image

    im = Image.new("RGBA", (100, 100), (0, 0, 0, 0))
    for x in range(40, 60):
        for y in range(20, 80):
            im.putpixel((x, y), (200, 100, 50, 255))
    im.save(tmp_path / "a.png")
    c = cap.finish_frame(tmp_path / "a.png", tmp_path / "a.jpg")
    assert c["foreground_share"] == pytest.approx(0.12, abs=1e-3) and not c["touches_border"]
    out = Image.open(tmp_path / "a.jpg")
    assert out.mode == "RGB" and out.getpixel((2, 2))[0] in range(cap.BG[0] - 3, cap.BG[0] + 4)
    im.putpixel((0, 50), (255, 255, 255, 255))
    im.save(tmp_path / "b.png")
    assert cap.finish_frame(tmp_path / "b.png", tmp_path / "b.jpg")["touches_border"]
