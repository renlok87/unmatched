"""_framing.view_fit_scale: широкий проп (бочка) на ракурсе wire-34 (az 45°, el 15°) не обрезается.

    python -m pytest tools/art/acceptance/tests -q
"""
import math
import sys
from pathlib import Path

import numpy as np
import pytest

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))

from _framing import view_dir, view_fit_scale  # noqa: E402


def cylinder(radius, height, n=64):
    a = np.linspace(0, 2 * math.pi, n, endpoint=False)
    ring = np.stack([radius * np.cos(a), radius * np.sin(a)], 1)
    return np.concatenate([np.c_[ring, np.zeros(n)], np.c_[ring, np.full(n, height)]])


def test_view_dir_matches_capture_convention():
    assert np.allclose(view_dir(0, 0), [0, -1, 0])     # спереди: камера на -Y
    assert np.allclose(view_dir(90, 0), [1, 0, 0])     # левый бок фигуры (+X)
    assert np.allclose(view_dir(0, 90), [0, 0, 1], atol=1e-12)


def test_front_view_of_tall_figure_equals_height():
    pts = cylinder(0.1, 1.0)
    s = view_fit_scale(pts, (0, 0, 0.5), 0, 0, margin=1.0)
    assert s == pytest.approx(1.0, rel=1e-6)


def test_wide_barrel_wire34_needs_more_than_front_scale():
    """Бочка: рост 1, радиус 0,5. Старый масштаб max(h, 2r)·1,1 = 1,1; на el 15° верх обода выше половины кадра."""
    h, r = 1.0, 0.5
    pts = cylinder(r, h)
    old = max(h, 2 * r) * 1.10
    new = view_fit_scale(pts, (0, 0, h / 2), 45, 15)
    need = 2 * (h / 2 * math.cos(math.radians(15)) + r * math.sin(math.radians(15)))  # вертикальный габарит
    assert need > old  # именно этот случай обрезался
    assert new >= need * 1.10 - 1e-9


def test_all_points_inside_frame():
    rng = np.random.default_rng(1)
    pts = rng.uniform(-1, 1, (500, 3)) * [0.8, 0.3, 0.5] + [0, 0, 0.5]
    tgt = np.array([0, 0, 0.5])
    for az, el in ((0, 0), (45, 15), (135, 10), (270, 0)):
        s = view_fit_scale(pts, tgt, az, el, margin=1.0)
        d = view_dir(az, el)
        up = np.array([0, 0, 1.0]) - d[2] * d
        up /= np.linalg.norm(up)
        right = np.cross(up, d)
        rel = pts - tgt
        assert np.abs(rel @ right).max() <= s / 2 + 1e-9
        assert np.abs(rel @ up).max() <= s / 2 + 1e-9
