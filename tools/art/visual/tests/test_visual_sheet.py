"""sheet.py: acceptance sheet per 02 13.2 - colour, gray Rec.709, deuteranopia; sizes; manifest; README template.

  python -B -m pytest -q tools/art/visual/tests
"""
import json
import sys
from pathlib import Path

import numpy as np
import pytest
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import sheet  # noqa: E402
from visual_common import VisualError, sha256_file  # noqa: E402


def px(rgb):
    return np.array([[rgb]], dtype=np.uint8)


def test_gray709_matches_the_documented_values():
    # 02 11.3: team.p1 #E8C06A reads 194 in gray
    assert sheet.gray709(px((0xE8, 0xC0, 0x6A)))[0, 0].tolist() == [194, 194, 194]
    assert sheet.gray709(px((255, 255, 255)))[0, 0].tolist() == [255, 255, 255]
    assert sheet.gray709(px((0, 255, 0)))[0, 0].tolist() == [182, 182, 182]


def test_deuteranopia_simulation():
    assert sheet.deuteranopia(px((255, 255, 255)))[0, 0].tolist() == [255, 255, 255]
    assert sheet.deuteranopia(px((0, 0, 0)))[0, 0].tolist() == [0, 0, 0]
    red = sheet.deuteranopia(px((0xDC, 0x2F, 0x33)))[0, 0].astype(int)   # card.type.attack
    green = sheet.deuteranopia(px((0x8C, 0xE6, 0x9A)))[0, 0].astype(int)  # fx.heal
    assert abs(red[0] - red[1]) < 40       # red loses its red-green contrast: an olive
    assert abs(green[0] - green[1]) < 25   # so does green
    assert red[2] < red[0]


def make_inputs(tmp_path):
    icon = Image.new("RGBA", (32, 32), (0, 0, 0, 0))
    for x in range(4, 28):
        for y in range(4, 28):
            icon.putpixel((x, y), (0xDC, 0x2F, 0x33, 255) if x < 16 else (0x8C, 0xE6, 0x9A, 255))
    frame = Image.new("RGB", (400, 225), (0x06, 0x16, 0x23))
    ip, fp = tmp_path / "icon-32.png", tmp_path / "frame.png"
    icon.save(ip)
    frame.save(fp)
    return ip, fp


def test_build_sheets_manifest_readme(tmp_path):
    ip, fp = make_inputs(tmp_path)
    out = tmp_path / "VISUAL" / "XX-01"
    m = sheet.build(tmp_path, "XX-01", [ip, fp], out, sizes=[24, 32], zoom=4, max_tile=200, date="2026-10-06")
    names = sorted(p.name for p in out.iterdir())
    assert names == ["README.md", "sheet-01-icon-32.png", "sheet-02-frame.png", "sheet-manifest.json",
                     "sheet-sizes.png"]
    man = json.loads((out / "sheet-manifest.json").read_text(encoding="utf-8"))
    assert man["id"] == "XX-01" and man["settings"]["sizes"] == [24, 32]
    assert [i["sha256"] for i in man["inputs"]] == [sha256_file(ip), sha256_file(fp)]
    assert [i["alpha"] for i in man["inputs"]] == [True, False]
    for o in man["outputs"]:
        assert sha256_file(out / o["file"]) == o["sha256"]
    # the icon sheet: 3 context rows (panel, cream, board) x 3 modes, x4 nearest tiles of 128 px
    with Image.open(out / "sheet-01-icon-32.png") as im:
        assert im.width >= 3 * 128 and im.height >= 3 * 128
    # the frame is scaled to the tile limit
    with Image.open(out / "sheet-02-frame.png") as im:
        assert im.width >= 3 * 200
    readme = (out / "README.md").read_text(encoding="utf-8")
    for field in ("**Решение:**", "по делегированию", "**Флаг отката:**", "Marmoreal original", "Sarpedon original",
                  "ARTLOOK", "Контраст", "ΔE76", "ΔGPU", "шесть фигур", sha256_file(ip)):
        assert field in readme
    assert m["readme_written"] is True


def test_gray_tiles_are_gray(tmp_path):
    ip, _ = make_inputs(tmp_path)
    img = Image.open(ip).convert("RGBA")
    flat = sheet.flatten(img, sheet.BACKGROUNDS["board"][1])
    g = np.asarray(sheet.apply_mode(flat, "gray Rec.709"))
    assert (g[..., 0] == g[..., 1]).all() and (g[..., 1] == g[..., 2]).all()
    assert g[0, 0].tolist() == [128, 128, 128]  # transparent corner over board grey #808080


def test_existing_readme_is_kept(tmp_path):
    ip, _ = make_inputs(tmp_path)
    out = tmp_path / "o"
    out.mkdir()
    (out / "README.md").write_text("решение уже записано", encoding="utf-8")
    m = sheet.build(tmp_path, "XX-02", [ip], out, date="2026-10-06")
    assert m["readme_written"] is False
    assert (out / "README.md").read_text(encoding="utf-8") == "решение уже записано"


def test_errors_are_loud(tmp_path, capsys):
    with pytest.raises(VisualError, match="input not found"):
        sheet.build(tmp_path, "XX-03", [tmp_path / "nope.png"], tmp_path / "o")
    ip, _ = make_inputs(tmp_path)
    with pytest.raises(VisualError, match="unknown background"):
        sheet.build(tmp_path, "XX-03", [ip], tmp_path / "o", backgrounds=["sky"])
    assert sheet.main(["XX-03", "--inputs", str(ip), "--sizes", "24,x", "--root", str(tmp_path)]) == 2
    assert "--sizes" in capsys.readouterr().err


def test_cli_default_out_folder(tmp_path):
    ip, _ = make_inputs(tmp_path)
    assert sheet.main(["XX-04", "--inputs", str(ip), "--root", str(tmp_path), "--date", "2026-10-06"]) == 0
    assert (tmp_path / "docs/game-design/evidence/VISUAL/XX-04/sheet-01-icon-32.png").is_file()
