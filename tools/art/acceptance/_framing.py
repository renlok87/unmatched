"""Кадрирование ортокамеры приёмки и геометрия кадров (только numpy: импортируется и в Blender,
и в тестах без Blender). Нужен широким пропам (бочка): на ракурсе с подъёмом (wire-34: az 45°, el 15°) фронтальный
габарит max(рост, 2·радиус) мал — верх крышки и низ дна уходят за кадр."""
import math

import numpy as np


def view_dir(az_deg, el_deg):
    """Направление от цели к камере; совпадает с _blender_capture.direction (az 0 = спереди, камера на -Y)."""
    a, e = math.radians(az_deg), math.radians(el_deg)
    return np.array([math.sin(a) * math.cos(e), -math.cos(a) * math.cos(e), math.sin(e)])


def view_fit_scale(points, target, az_deg, el_deg, margin=1.10):
    """ortho_scale квадратного кадра, при котором все точки видны с запасом margin при камере, смотрящей на target.

    Ось «вверх» кадра — мировая Z, спроецированная на плоскость кадра (как to_track_quat("-Z", "Y")); правая —
    перпендикуляр. Половина кадра = max |проекция| по обеим осям."""
    pts = np.asarray(points, dtype=float).reshape(-1, 3) - np.asarray(target, dtype=float).reshape(1, 3)
    d = view_dir(az_deg, el_deg)
    up = np.array([0.0, 0.0, 1.0]) - d[2] * d
    n = float(np.linalg.norm(up))
    up = up / n if n > 1e-9 else np.array([0.0, 1.0, 0.0])
    right = np.cross(up, d)
    half = max(float(np.abs(pts @ right).max()), float(np.abs(pts @ up).max()))
    return 2.0 * half * margin


def panel_fit_scale(points, target, az_deg, el_deg, aspect=0.5, margin=1.15):
    """ortho_scale портретной панели (ширина = aspect × высота; Blender относит ortho_scale к большей стороне — высоте),
    при котором все точки видны с запасом margin: половина высоты = max(|вверх|, |вправо| / aspect)."""
    pts = np.asarray(points, dtype=float).reshape(-1, 3) - np.asarray(target, dtype=float).reshape(1, 3)
    d = view_dir(az_deg, el_deg)
    up = np.array([0.0, 0.0, 1.0]) - d[2] * d
    n = float(np.linalg.norm(up))
    up = up / n if n > 1e-9 else np.array([0.0, 1.0, 0.0])
    right = np.cross(up, d)
    half = max(float(np.abs(pts @ up).max()), float(np.abs(pts @ right).max()) / aspect)
    return 2.0 * half * margin


def ang_diff(a, b):
    """Угол между азимутами, 0…180°."""
    return abs((float(a) - float(b) + 180.0) % 360.0 - 180.0)


def best_visible_azimuth(visible, avoid_deg, min_sep=60.0):
    """Азимут второго ракурса позы (pose-04b, F77): из {азимут: доля видимых вершин цели} — с наибольшей долей среди
    азимутов не ближе min_sep к avoid_deg (ракурс основного кадра); при равенстве — ближе к фронту (az 0), затем меньший
    азимут. (az, доля) или (None, None), если подходящих нет."""
    cands = [(float(v), -ang_diff(az, 0.0), -int(az), int(az)) for az, v in visible.items()
             if ang_diff(az, avoid_deg) >= min_sep]
    if not cands:
        return None, None
    best = max(cands)
    return best[3], best[0]


CLOSE_MIN, CLOSE_MAX = 0.12, 0.25  # крупный план кисти/хвата: рамка 12–25 % роста (решение скилла)


def clamp_close_scale(scale, height, lo=CLOSE_MIN, hi=CLOSE_MAX):
    """ortho_scale крупного плана кисти или хвата: не меньше lo и не больше hi роста фигуры."""
    return float(min(max(float(scale), lo * height), hi * height))


def _subsample(points, n=2500):
    pts = np.asarray(points, dtype=float).reshape(-1, 3)
    if len(pts) > n:
        pts = pts[np.linspace(0, len(pts) - 1, n).astype(int)]
    return pts


def min_distance(a, b, chunk=512):
    """Минимальное евклидово расстояние между двумя наборами точек (поднабор до 2500 точек каждого)."""
    a, b = _subsample(a), _subsample(b)
    best = math.inf
    for i in range(0, len(a), chunk):
        d = a[i:i + chunk, None, :] - b[None, :, :]
        best = min(best, float(np.sqrt((d * d).sum(-1)).min()))
    return best


def projected_gap(a, b, az_deg, el_deg, chunk=512):
    """Минимальное расстояние между проекциями двух наборов точек на плоскость кадра (az, el), в метрах."""
    d = view_dir(az_deg, el_deg)
    up = np.array([0.0, 0.0, 1.0]) - d[2] * d
    n = float(np.linalg.norm(up))
    up = up / n if n > 1e-9 else np.array([0.0, 1.0, 0.0])
    right = np.cross(up, d)
    basis = np.stack([right, up], 1)
    pa, pb = _subsample(a) @ basis, _subsample(b) @ basis
    best = math.inf
    for i in range(0, len(pa), chunk):
        q = pa[i:i + chunk, None, :] - pb[None, :, :]
        best = min(best, float(np.sqrt((q * q).sum(-1)).min()))
    return best


def best_separating_azimuth(a, b, el=10, candidates=range(0, 360, 30)):
    """Азимут (из candidates), на котором проекции наборов a и b дальше всего друг от друга; (az, зазор м).
    Нужен второму ракурсу pose-03: длинное оружие у лица — с какого ракурса виден зазор."""
    best_az, best_gap = None, -1.0
    for az in candidates:
        g = projected_gap(a, b, az, el)
        if g > best_gap + 1e-9:
            best_az, best_gap = int(az), g
    return best_az, best_gap
