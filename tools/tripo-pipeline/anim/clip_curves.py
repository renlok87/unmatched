"""Кривые авторского слоя клипов H2Anim (волна 5c): чистый Python, stdlib.

Их вызывает clip_author.py (headless Blender) и проверяют юнит-тесты
tools/tripo-pipeline/tests/test_clip_curves.py.

Канал = список ключей (кадр, значение) одной компоненты (градусы поворота или сантиметры сдвига).
Интерполяция — кубический Эрмит с касательными Катмулла–Рома, «автоклампом» как в Blender
(в локальном экстремуме касательная 0) и ограничением Фритча–Карлсона (|m| ≤ 3 × наклон соседних хорд), поэтому
между монотонными ключами нет перелёта; нулевые касательные
на концах разомкнутого клипа. Для петли (idle) касательные периодические: кадр N = кадр 0.
Волны — аддитивные синусоиды с целым числом периодов на клип (шов петли бесшовный по построению).
"""
import math

SHAPES = ("sin", "raised_cos")


def _sorted_keys(keys):
    out = {}
    for f, v in keys:
        out[int(f)] = float(v)
    return sorted(out.items())


def tangents(keys, loop=False, period=None):
    """Касательные (значение/кадр) в ключах: Катмулл–Ром с автоклампом.

    loop=True: соседи берутся по кругу с периодом `period` (кадр period совпадает с кадром 0)."""
    n = len(keys)
    out = []
    for i, (f, v) in enumerate(keys):
        if n == 1:
            out.append(0.0)
            continue
        if loop:
            fp, vp = keys[i - 1] if i > 0 else (keys[-1][0] - period, keys[-1][1])
            fn, vn = keys[i + 1] if i < n - 1 else (keys[0][0] + period, keys[0][1])
        else:
            if i == 0 or i == n - 1:
                out.append(0.0)
                continue
            fp, vp = keys[i - 1]
            fn, vn = keys[i + 1]
        if (v - vp) * (vn - v) <= 0.0:  # локальный экстремум или плато: без перелёта
            out.append(0.0)
            continue
        m = (vn - vp) / float(fn - fp)
        # ограничение Фритча–Карлсона: |m| <= 3 x наклон соседних хорд, иначе сегмент с малым наклоном
        # перелетает следующий ключ (найдено тестом test_monotone_segment_between_monotone_keys)
        d_prev = (v - vp) / float(f - fp)
        d_next = (vn - v) / float(fn - f)
        lim = 3.0 * min(abs(d_prev), abs(d_next))
        out.append(max(-lim, min(lim, m)))
    return out


def hermite(p0, m0, p1, m1, t, dt):
    t2, t3 = t * t, t * t * t
    return ((2 * t3 - 3 * t2 + 1) * p0 + (t3 - 2 * t2 + t) * dt * m0 +
            (-2 * t3 + 3 * t2) * p1 + (t3 - t2) * dt * m1)


def eval_channel(keys, frame, loop=False, period=None):
    """Значение канала в кадре `frame` (float). Пустой канал = 0; вне ключей — удержание крайнего."""
    ks = _sorted_keys(keys)
    if not ks:
        return 0.0
    if loop and period is None:
        raise ValueError("loop channel needs a period")
    if loop:
        # ключ в кадре period дублирует кадр 0: берём по модулю, собственный ключ period отбрасываем
        ks = [(f, v) for f, v in ks if f < period]
        if not ks:
            return 0.0
        frame = frame % period
    ms = tangents(ks, loop, period)
    if len(ks) == 1:
        return ks[0][1]
    if not loop:
        if frame <= ks[0][0]:
            return ks[0][1]
        if frame >= ks[-1][0]:
            return ks[-1][1]
    segs = list(zip(range(len(ks)), range(1, len(ks))))
    if loop:
        segs.append((len(ks) - 1, 0))
    for i, j in segs:
        f0, v0 = ks[i]
        f1, v1 = ks[j]
        if loop and j == 0:
            f1 = f1 + period
            fr = frame if frame >= f0 else frame + period
        else:
            fr = frame
        if f0 <= fr <= f1:
            dt = float(f1 - f0)
            return hermite(v0, ms[i], v1, ms[j], (fr - f0) / dt, dt)
    # loop: до первого ключа (кадр < ks[0][0]) — сегмент последний -> первый уже покрыл по модулю
    return ks[0][1]


def wave(frame, frames, amp, cycles=1, phase=0.0, shape="sin"):
    """Аддитивная волна: sin — amp*sin(2π(cycles*f/N + phase)); raised_cos — amp*(1-cos(2π*cycles*f/N))/2
    (0 в кадрах 0 и N, пик amp в середине периода; phase сдвигает долю периода)."""
    if shape not in SHAPES:
        raise ValueError("wave shape must be one of %s" % (SHAPES,))
    x = cycles * frame / float(frames) + phase
    if shape == "sin":
        return amp * math.sin(2 * math.pi * x)
    return amp * (1.0 - math.cos(2 * math.pi * x)) / 2.0


def channels_from_keys(keys, field="bones"):
    """keys: [{"f": кадр, "bones": {кость: [x, y, z]}}] -> {кость: [[(f, x)], [(f, y)], [(f, z)]]}."""
    out = {}
    for k in keys:
        for bone, xyz in (k.get(field) or {}).items():
            ch = out.setdefault(bone, [[], [], []])
            for axis in range(3):
                ch[axis].append((int(k["f"]), float(xyz[axis])))
    return out


def with_boundary(channel_axes, frames, role):
    """Добавляет нулевые ключи на границах клипа по роли (контракт v2 clip_boundaries):
    idle/oneshot — кадр 0 и N = rest; terminal — только кадр 0. Явные ключи на границе не перетираются."""
    out = []
    for axis in channel_axes:
        fs = {f for f, _ in axis}
        axis = list(axis)
        if 0 not in fs:
            axis.append((0, 0.0))
        if role in ("idle", "oneshot") and frames not in fs:
            axis.append((frames, 0.0))
        out.append(sorted(axis))
    return out


def weight_curve(keys, frame):
    """Кусочно-линейный вес (IK стоп и т. п.): keys [[кадр, вес]]; вне ключей — удержание. Пусто = 1."""
    if not keys:
        return 1.0
    ks = sorted((float(f), float(w)) for f, w in keys)
    if frame <= ks[0][0]:
        return ks[0][1]
    for (f0, w0), (f1, w1) in zip(ks, ks[1:]):
        if f0 <= frame <= f1:
            t = (frame - f0) / (f1 - f0) if f1 > f0 else 1.0
            t = t * t * (3 - 2 * t)  # smoothstep: без рывка в начале и конце перехода
            return w0 + (w1 - w0) * t
    return ks[-1][1]
