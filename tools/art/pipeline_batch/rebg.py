"""Заменить студийный задник фронта unstability.ai (пол, горизонт, виньетка) ровным нейтрально-серым фоном (этап 1a, лицензированные фигуры).

Проверки 1a (check_concept_views.py) требуют ровного однотонного фона; Flux рисует «продуктовый» пол, который
проверка читает как часть фигуры. Модель фона — полином 4-й степени по x, y на канал плюс построчная поправка,
переподгоняемая по пикселям фона. Пиксель — фон, если близок к модели по цвету и локально гладкий; фон растёт от
рамки кадра, замкнутые карманы, совпадающие с моделью (между ног), тоже присоединяются. Фигура, касающаяся верха или
низа кадра, ужимается в рамку с полями (размер и аспект кадра сохраняются).
Был C:/tmp/concept-wave/rebg.py (concept-sheet.md §13).

    python tools/art/pipeline_batch/rebg.py <in.png> <out.png> [tone] [grad]
        tone — порог цвета к модели фона (14), grad — порог градиента гладкости (6)

Код выхода: 0 — записано, 2 — ошибка входа (файла нет, фигура не найдена).
"""
import argparse
import sys

import numpy as np
from PIL import Image
from scipy import ndimage as ndi

BG = np.array([46.0, 46.0, 48.0])  # neutral dark grey, close to the Codex 1a fronts


def feats(h, w, deg=4):
    yy, xx = np.mgrid[0:h, 0:w]
    x = xx / (w - 1) * 2 - 1
    y = yy / (h - 1) * 2 - 1
    cols = [x ** i * y ** j for i in range(deg + 1) for j in range(deg + 1 - i)]
    return np.stack(cols, -1).reshape(-1, len(cols))


def fit_model(rgb, sel, F):
    h, w, _ = rgb.shape
    idx = np.flatnonzero(sel.ravel())
    if idx.size > 150_000:
        idx = idx[np.linspace(0, idx.size - 1, 150_000).astype(np.int64)]
    coef, *_ = np.linalg.lstsq(F[idx], rgb.reshape(-1, 3)[idx], rcond=None)
    model = (F @ coef).reshape(h, w, 3)
    res = rgb - model
    rowcorr = np.zeros((h, 3))
    for y in range(h):
        m = sel[y]
        if m.sum() > 20:
            rowcorr[y] = np.median(res[y][m], axis=0)
    rowcorr = ndi.uniform_filter1d(ndi.median_filter(rowcorr, size=(9, 1)), 5, axis=0)
    return model + rowcorr[:, None, :]


def segment(rgb, tone, gthr):
    h, w, _ = rgb.shape
    F = feats(h, w)
    sm = ndi.gaussian_filter(rgb, sigma=(1.2, 1.2, 0))
    g = np.zeros((h, w))
    for c in range(3):
        g = np.maximum(g, np.hypot(ndi.sobel(sm[..., c], 1), ndi.sobel(sm[..., c], 0)) / 8.0)
    band = max(4, int(0.02 * min(h, w)))
    sel = np.zeros((h, w), bool)
    sel[:band] = sel[-band:] = True
    sel[:, :band] = sel[:, -band:] = True
    for _ in range(4):
        model = fit_model(sm, sel, F)
        close = np.abs(sm - model).max(2) < tone
        elig = close & (g < gthr)
        seed = np.zeros_like(elig)
        seed[[0, -1], :] = True
        seed[:, [0, -1]] = True
        bg = ndi.binary_propagation(seed & elig, mask=elig)
        sel = ndi.binary_erosion(bg, iterations=3)
    fg = ~bg
    fg = ndi.binary_opening(fg, iterations=2)
    # pedestal zone (bottom quarter): thick shapes only, drops thin floor streaks and shadow rims
    z = int(h * 0.75)
    fg[z:] = ndi.binary_opening(fg[z:], iterations=6)
    thin = fg[z:].sum(0) < 0.02 * h
    fg[z:, thin] = False
    # enclosed pockets of backdrop (between the legs, under the arms): smooth, grey, near the model
    chroma = sm.max(2) - sm.min(2)
    pocket = fg & (g < gthr) & (chroma < 14) & (np.abs(sm - model).max(2) < tone * 1.5)
    pocket[: int(h * 0.45)] = False
    pl, pn = ndi.label(pocket)
    if pn:
        sizes = ndi.sum(pocket, pl, range(1, pn + 1))
        big = np.zeros(pn + 1, bool)
        big[1:] = sizes >= 1500
        fg &= ~big[pl]
    lab, n = ndi.label(fg)
    if n > 1:
        sizes = ndi.sum(fg, lab, range(1, n + 1))
        keep = np.zeros(n + 1, bool)
        keep[1:] = sizes >= sizes.max() * 0.01
        fg = keep[lab]
    filled = ndi.binary_fill_holes(fg)
    holes = filled & ~fg
    hl, hn = ndi.label(holes)
    for i in range(1, hn + 1):
        m = hl == i
        if m.sum() < 300 or close[m].mean() < 0.85:
            fg |= m
    return fg


def rebg(src, dst, tone=14.0, gthr=6.0):
    rgb = np.asarray(Image.open(src).convert("RGB")).astype(np.float64)
    fg = segment(rgb, tone, gthr)
    h, w = fg.shape
    e = int(0.02 * w)  # leftover floor streaks at the side edges; the figure never reaches them
    fg[:, :e] = False
    fg[:, -e:] = False
    lab, n = ndi.label(fg)
    if n > 1:
        sizes = ndi.sum(fg, lab, range(1, n + 1))
        fg = np.isin(lab, 1 + np.flatnonzero(sizes >= sizes.max() * 0.05))
    a = ndi.gaussian_filter(fg.astype(float), 0.8)[..., None]
    out = rgb * a + BG * (1 - a)
    ys, xs = np.nonzero(fg)
    if ys.size == 0:
        raise ValueError(f"{src}: фигура не найдена (весь кадр — фон)")
    top, bot = ys.min() / h, ys.max() / h
    if top < 0.04 or bot > 0.97:  # touches top/bottom: shrink into a padded flat frame, keep size and aspect
        k = min(0.90 / (bot - top), 0.95)
        nh, nw = int(h * k), int(w * k)
        small = Image.fromarray(out.clip(0, 255).astype(np.uint8)).resize((nw, nh), Image.LANCZOS)
        canvas = Image.new("RGB", (w, h), tuple(int(v) for v in BG))
        y0 = int((h - (bot - top) * nh) / 2 - top * nh)  # centre the figure bbox vertically
        canvas.paste(small, ((w - nw) // 2, y0))
        out = np.asarray(canvas).astype(np.float64)
        print(f"  padded k={k:.3f} y0={y0}")
    Image.fromarray(out.clip(0, 255).astype(np.uint8)).save(dst)
    print(f"{str(src).replace(chr(92), '/').split('/')[-1]}: fg {fg.mean():.3f} x {xs.min()/w:.3f}-{xs.max()/w:.3f} "
          f"y {ys.min()/h:.3f}-{ys.max()/h:.3f}")
    return fg


def main(argv=None) -> int:
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            try:
                stream.reconfigure(encoding="utf-8", errors="replace")
            except (OSError, ValueError):
                pass
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0],
                                 formatter_class=argparse.RawDescriptionHelpFormatter, epilog=__doc__)
    ap.add_argument("src")
    ap.add_argument("dst")
    ap.add_argument("tone", nargs="?", type=float, default=14.0)
    ap.add_argument("grad", nargs="?", type=float, default=6.0)
    try:
        a = ap.parse_args(argv)
    except SystemExit as exc:
        return int(exc.code or 0)
    try:
        rebg(a.src, a.dst, a.tone, a.grad)
    except (OSError, ValueError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
