"""draft_orthos.py: аргументы и коды выхода (без Blender) + интеграционный прогон на синтетическом GLB с метками
сторон (пропускается, если Blender 5.2 не установлен; ~15 с).

    python -m pytest tools/art/concept/tests -q
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import numpy as np
import pytest
from PIL import Image

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))

import draft_orthos as D  # noqa: E402

BLENDER = Path(D.DEFAULT_BLENDER)

# Синтетическая «миниатюра»: подставка-цилиндр, тело-куб, голова-сфера; красная метка на левом боку фигуры (+X),
# зелёная — на лице (−Y). Оси — BLENDER-MODEL-HANDBOOK §2.1.
MAKE_GLB = r"""
import bpy, sys
out = sys.argv[sys.argv.index('--') + 1]
for ob in list(bpy.data.objects):
    bpy.data.objects.remove(ob, do_unlink=True)
def mat(name, rgb):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    b = next(n for n in m.node_tree.nodes if n.type == 'BSDF_PRINCIPLED')
    b.inputs['Base Color'].default_value = (*rgb, 1.0)
    b.inputs['Emission Color'].default_value = (*rgb, 1.0)
    b.inputs['Emission Strength'].default_value = 1.0
    return m
def add(op, mat_, **kw):
    op(**kw)
    ob = bpy.context.active_object
    ob.data.materials.append(mat_)
grey = mat('grey', (0.6, 0.6, 0.6))
add(bpy.ops.mesh.primitive_cylinder_add, grey, radius=0.3, depth=0.06, location=(0, 0, 0.03))
add(bpy.ops.mesh.primitive_cube_add, grey, size=1, location=(0, 0, 0.5), scale=(0.3, 0.2, 0.8))
add(bpy.ops.mesh.primitive_uv_sphere_add, grey, radius=0.12, location=(0, 0, 1.0))
add(bpy.ops.mesh.primitive_cube_add, mat('red', (1, 0, 0)), size=1, location=(0.2, 0, 0.6), scale=(0.1, 0.1, 0.2))
add(bpy.ops.mesh.primitive_cube_add, mat('green', (0, 1, 0)), size=1, location=(0, -0.15, 1.0), scale=(0.06, 0.1, 0.06))
bpy.ops.export_scene.gltf(filepath=out, export_format='GLB')
"""


def test_resolution():
    assert D.resolution("3:4", 1536) == (1152, 1536)
    assert D.resolution("4:3", 1536) == (1536, 1152)
    assert D.resolution("1:1", 1024) == (1024, 1024)
    with pytest.raises(ValueError):
        D.resolution("3x4", 1536)
    with pytest.raises(ValueError):
        D.resolution("0:4", 1536)


def test_input_errors_exit_1(tmp_path):
    glb = tmp_path / "x.glb"
    glb.write_bytes(b"glTF")
    assert D.main(["--glb", str(tmp_path / "missing.glb"), "--out", str(tmp_path / "o")]) == 1
    assert D.main(["--glb", str(glb), "--out", str(tmp_path / "o"), "--views", "front,top"]) == 1
    assert D.main(["--glb", str(glb), "--out", str(tmp_path / "o"), "--views", "front,front"]) == 1
    assert D.main(["--glb", str(glb), "--out", str(tmp_path / "o"), "--bg", "2"]) == 1
    assert D.main(["--glb", str(glb), "--out", str(tmp_path / "o"), "--blender", str(tmp_path / "no.exe")]) == 1
    assert D.main(["--glb", str(glb)]) == 1  # нет --out


def _centroid_x(img: np.ndarray, rgb_mask) -> float:
    ys, xs = np.nonzero(rgb_mask(img))
    assert xs.size > 20
    return float(xs.mean()) / img.shape[1]


@pytest.mark.skipif(not BLENDER.is_file(), reason="Blender 5.2 не установлен")
def test_render_synthetic_glb(tmp_path):
    glb = tmp_path / "probe.glb"
    r = subprocess.run([str(BLENDER), "-b", "--factory-startup", "--python-exit-code", "1", "--python-expr",
                        MAKE_GLB, "--", str(glb)], capture_output=True, text=True, timeout=300)
    assert r.returncode == 0 and glb.is_file(), r.stdout[-2000:] + r.stderr[-2000:]
    out = tmp_path / "orthos"
    assert D.main(["--glb", str(glb), "--out", str(out), "--long-side", "512"]) == 0
    fr = json.loads((out / "ortho-framing.json").read_text(encoding="utf-8"))
    assert fr["schema"] == "unmatched.draft-orthos/1"
    assert fr["resolution"] == [384, 512]
    assert fr["placement_pct"]["base_bottom_y"] == pytest.approx(94.0, abs=0.01)
    assert fr["placement_pct"]["base_center_x"] == 50.0
    # подставка-цилиндр: вершины только на ободах (z 0 и 0,06), между ними пустые слои — верх подставки всё равно
    # находится (≈ 0,06/1,12 роста выше низа), а не застревает у нижнего обода
    pp = fr["placement_pct"]
    assert 3.0 < pp["base_bottom_y"] - pp["base_top_y_est"] < 8.0, pp
    assert not any(p.name.startswith("draft-orthos-") and p.is_dir() for p in out.iterdir())  # временное убрано
    imgs = {}
    for v in ("front", "left", "back", "right"):
        p = out / f"ortho_{v}.png"
        im = Image.open(p)
        assert im.mode == "RGB" and im.size == (384, 512)
        a = np.asarray(im).astype(int)
        assert tuple(a[2, 2]) == (46, 46, 46)  # ровный фон --bg 0.18
        imgs[v] = a
    red = lambda a: (a[..., 0] > 150) & (a[..., 1] < 90) & (a[..., 2] < 90)  # noqa: E731
    green = lambda a: (a[..., 1] > 150) & (a[..., 0] < 90) & (a[..., 2] < 90)  # noqa: E731
    # левый бок фигуры (+X): на front справа в кадре, на back слева, на left — по центру к камере
    assert _centroid_x(imgs["front"], red) > 0.55
    assert _centroid_x(imgs["back"], red) < 0.45
    assert abs(_centroid_x(imgs["left"], red) - 0.5) < 0.1
    assert not red(imgs["right"]).any()  # с правого бока метку закрывает тело
    # лицо (−Y): на left смотрит влево в кадре, на right — вправо, на back не видно
    assert _centroid_x(imgs["left"], green) < 0.45
    assert _centroid_x(imgs["right"], green) > 0.55
    assert not green(imgs["back"]).any()


@pytest.mark.skipif(not BLENDER.is_file(), reason="Blender 5.2 не установлен")
def test_cli_cp1251_pipe_exit_0(tmp_path):
    """Финальная печать «→» в пайп cp1251 (Codex/PowerShell, Git Bash) не должна давать код 1 при записанных видах."""
    import os
    glb = tmp_path / "probe.glb"
    r = subprocess.run([str(BLENDER), "-b", "--factory-startup", "--python-exit-code", "1", "--python-expr",
                        MAKE_GLB, "--", str(glb)], capture_output=True, text=True, timeout=300)
    assert r.returncode == 0 and glb.is_file(), r.stdout[-2000:] + r.stderr[-2000:]
    env = {k: v for k, v in os.environ.items() if k not in ("PYTHONIOENCODING", "PYTHONUTF8")}
    env.update(PYTHONIOENCODING="cp1251", PYTHONUTF8="0")
    r = subprocess.run([sys.executable, str(HERE.parent / "draft_orthos.py"), "--glb", str(glb), "--out",
                        str(tmp_path / "o"), "--long-side", "256", "--views", "front"], capture_output=True, env=env,
                       timeout=600)
    out = r.stdout.decode("utf-8", "replace") + r.stderr.decode("utf-8", "replace")
    assert r.returncode == 0, out
    assert "OK:" in out and "Traceback" not in out

