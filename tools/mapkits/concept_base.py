"""Concept base for a map kit: the original board image lying flat on a dark stone tray, seen by the game camera.

Same idea as art/imagegen/env-v1/concepts/render_concept_base.py (Marmoreal/Sarpedon, P0 of ENV-MAPS), but without the
vector layers that only those two maps have: a pinhole camera (pitch -55 deg, HFOV 35 deg, 1920x1080) frames the board,
then pulls back x1.45 so the dark rim around the board is free space for the environment. Gemini paints around it.

    python tools/mapkits/concept_base.py --map scraped-data/images/maps/soho.png --out art/imagegen/mapkit-soho/base/soho-wide-base.png

Scale: 2/3 uu per board pixel (ENV-MAPS-PLAN), tray rim 170 uu (render_concept_base.py).
"""
from __future__ import annotations

import argparse
import math
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

W, H = 1920, 1080
PITCH = math.radians(55.0)
HFOV = math.radians(35.0)
UU_PER_PX = 2.0 / 3.0
TRAY_RIM = 170.0


def project(pts: np.ndarray, dist: float) -> np.ndarray:
    """World (x right, y away, z up) -> pixel. Camera looks at the origin from behind and above."""
    cam = np.array([0.0, -dist * math.cos(PITCH), dist * math.sin(PITCH)])
    fwd = -cam / np.linalg.norm(cam)
    right = np.array([1.0, 0.0, 0.0])
    up = np.cross(right, fwd)
    f = (W / 2) / math.tan(HFOV / 2)
    rel = pts - cam
    xc, yc, zc = rel @ right, rel @ up, rel @ fwd
    return np.stack([W / 2 + f * xc / zc, H / 2 - f * yc / zc], axis=1)


def fit_distance(hx: float, hy: float, fill: float = 0.92) -> float:
    corners = np.array([[sx * hx, sy * hy, 0.0] for sx in (-1, 1) for sy in (-1, 1)])
    lo, hi = 100.0, 20000.0
    for _ in range(60):
        mid = (lo + hi) / 2
        p = project(corners, mid)
        ok = p[:, 0].min() >= W * (1 - fill) / 2 and p[:, 0].max() <= W - W * (1 - fill) / 2 \
            and p[:, 1].min() >= H * (1 - fill) / 2 and p[:, 1].max() <= H - H * (1 - fill) / 2
        hi, lo = (mid, lo) if ok else (hi, mid)
    return hi


def perspective_coeffs(dst: np.ndarray, src: np.ndarray) -> list[float]:
    """Coefficients for PIL PERSPECTIVE: maps output (dst) pixels to input (src) pixels."""
    a = []
    for (x, y), (u, v) in zip(dst, src):
        a.append([x, y, 1, 0, 0, 0, -u * x, -u * y])
        a.append([0, 0, 0, x, y, 1, -v * x, -v * y])
    b = src.reshape(8)
    return list(np.linalg.solve(np.array(a, dtype=float), b))


def render(map_path: Path, out: Path, mul: float = 1.45) -> dict:
    board = Image.open(map_path).convert("RGB")
    bw, bh = board.size
    hx, hy = bw * UU_PER_PX / 2, bh * UU_PER_PX / 2
    dist = fit_distance(hx, hy) * mul
    rng = np.random.default_rng(7)
    img = Image.new("RGB", (W, H), (16, 17, 20))
    draw = ImageDraw.Draw(img)
    tx, ty = hx + TRAY_RIM, hy + TRAY_RIM
    tray = project(np.array([[-tx, -ty, 0], [tx, -ty, 0], [tx, ty, 0], [-tx, ty, 0]], float), dist)
    draw.polygon([tuple(p) for p in tray], fill=(46, 43, 40))
    noise = Image.fromarray((rng.normal(0, 9, (H, W)) + 128).clip(0, 255).astype(np.uint8), "L").filter(ImageFilter.GaussianBlur(1.2))
    mask = Image.new("L", (W, H), 0)
    ImageDraw.Draw(mask).polygon([tuple(p) for p in tray], fill=255)
    tex = Image.merge("RGB", [noise] * 3)
    img = Image.composite(Image.blend(img, tex, 0.12), img, mask)
    fx, fy = hx + 12, hy + 12
    frame = project(np.array([[-fx, -fy, 0], [fx, -fy, 0], [fx, fy, 0], [-fx, fy, 0]], float), dist)
    ImageDraw.Draw(img).polygon([tuple(p) for p in frame], fill=(58, 40, 28))
    quad = project(np.array([[-hx, hy, 0], [hx, hy, 0], [hx, -hy, 0], [-hx, -hy, 0]], float), dist)  # TL TR BR BL of image
    src = np.array([[0, 0], [bw, 0], [bw, bh], [0, bh]], float)
    warped = board.transform((W, H), Image.PERSPECTIVE, perspective_coeffs(quad, src), Image.BICUBIC)
    bmask = Image.new("L", (W, H), 0)
    ImageDraw.Draw(bmask).polygon([tuple(p) for p in quad], fill=255)
    img = Image.composite(warped, img, bmask)
    out.parent.mkdir(parents=True, exist_ok=True)
    img.save(out)
    return {"out": str(out), "distance_uu": round(dist, 1), "board_uu": [round(2 * hx, 1), round(2 * hy, 1)],
            "board_px": [bw, bh], "mul": mul}


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--map", required=True, type=Path, help="original board image (png/webp/jpg)")
    ap.add_argument("--out", required=True, type=Path)
    ap.add_argument("--mul", type=float, default=1.45, help="pull-back over the fit distance (1.0 = K1 framing)")
    print(render(ap.parse_args().map, ap.parse_args().out, ap.parse_args().mul))


if __name__ == "__main__":
    main()
