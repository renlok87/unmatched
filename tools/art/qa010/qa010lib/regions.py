"""Region specs -> boolean masks, and per-region luma statistics.

Region spec grammar (NAME=KIND:ARGS):
  NAME=bbox:x0,y0,x1,y1        integer pixel box, half-open [x0,x1) x [y0,y1)
  NAME=poly:x,y;x,y;x,y        polygon in screen pixels (filled with PIL)
  NAME=mask:PATH.png           mask PNG, same size as the frame (alpha>=128
                               if the PNG has non-opaque alpha, else gray>=128)
  NAME=trace-cells:all         union of projected board cells of the SHOT block
  NAME=trace-cells:x,y;x,y     union of the listed cells only
  NAME=trace-ring:IN,OUT       ring around the board between IN and OUT cells
                               outside its edge (a *proxy* for tray/decor
                               until stencil masks exist; flagged as proxy)
  NAME=frame                   whole frame
trace-* kinds need a trace + SHOT block (see trace.py / projection.py).
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import numpy as np
from PIL import Image, ImageDraw

from . import color
from .geometry import parse_points
from .imageio import load_mask
from .projection import Camera, board_world_rect, cell_world_quad, project_polygon
from .trace import Board


class RegionError(ValueError):
    pass


@dataclass
class TraceContext:
    board: Board
    camera: Camera
    projection: dict  # ProjectionReport.to_dict()


@dataclass
class Region:
    name: str
    spec: str
    mask: np.ndarray
    proxy: bool = False
    note: str = ""
    kind: str = ""


def _poly_mask(size, polys, holes=()) -> np.ndarray:
    w, h = size
    im = Image.new("L", (w, h), 0)
    d = ImageDraw.Draw(im)
    for p in polys:
        d.polygon([(float(x), float(y)) for x, y in p], fill=255)
    for p in holes:
        d.polygon([(float(x), float(y)) for x, y in p], fill=0)
    return np.asarray(im, dtype=np.uint8) >= 128


def _scale_poly(poly, sx, sy):
    return [(x * sx, y * sy) for x, y in poly]


def parse_region(spec: str, size: tuple[int, int], trace_ctx: Optional[TraceContext] = None,
                 base_dir: Optional[Path] = None) -> Region:
    if "=" not in spec:
        raise RegionError(f"region needs NAME=KIND:ARGS, got {spec!r}")
    name, rest = spec.split("=", 1)
    name = name.strip()
    kind, _, args = rest.partition(":")
    kind = kind.strip()
    w, h = size
    if kind == "frame":
        return Region(name, spec, np.ones((h, w), dtype=bool), kind=kind)
    if kind == "bbox":
        parts = [int(round(float(v))) for v in args.split(",")]
        if len(parts) != 4:
            raise RegionError(f"bbox needs x0,y0,x1,y1: {spec!r}")
        x0, x1 = sorted((parts[0], parts[2]))
        y0, y1 = sorted((parts[1], parts[3]))
        x0, x1 = max(0, x0), min(w, x1)
        y0, y1 = max(0, y0), min(h, y1)
        if x1 <= x0 or y1 <= y0:
            raise RegionError(f"bbox outside frame or empty: {spec!r}")
        m = np.zeros((h, w), dtype=bool)
        m[y0:y1, x0:x1] = True
        return Region(name, spec, m, kind=kind)
    if kind == "poly":
        pts = parse_points(args)
        if len(pts) < 3:
            raise RegionError(f"poly needs >= 3 points: {spec!r}")
        return Region(name, spec, _poly_mask(size, [pts]), kind=kind)
    if kind == "mask":
        p = Path(args)
        if not p.is_absolute() and base_dir is not None:
            p = base_dir / p
        return Region(name, spec, load_mask(p, size), kind=kind)
    if kind in ("trace-cells", "trace-ring"):
        if trace_ctx is None:
            raise RegionError(f"{spec!r} needs --trace (and a matching SHOT block)")
        if not trace_ctx.projection.get("ok"):
            raise RegionError(f"{spec!r}: projection not validated ({trace_ctx.projection.get('reason')})")
        cam, board = trace_ctx.camera, trace_ctx.board
        vw, vh = cam.viewport
        sx, sy = w / vw, h / vh  # screenshot may differ from traced viewport
        if kind == "trace-cells":
            if args.strip() in ("", "all"):
                cells = [(x, y) for y in range(board.height) for x in range(board.width)]
            else:
                cells = [(int(a), int(b)) for a, b in (c.split(",") for c in args.split(";") if c)]
            polys = []
            for x, y in cells:
                if not (0 <= x < board.width and 0 <= y < board.height):
                    raise RegionError(f"cell ({x},{y}) outside BOARD {board.width}x{board.height}")
                q = project_polygon(cam, cell_world_quad(board, x, y))
                if q is not None:
                    polys.append(_scale_poly(q, sx, sy))
            return Region(name, spec, _poly_mask(size, polys),
                          note=f"{len(polys)} projected cells from trace", kind=kind)
        inner, outer = (float(v) for v in args.split(","))
        if outer <= inner:
            raise RegionError(f"trace-ring needs IN < OUT: {spec!r}")
        po = project_polygon(cam, board_world_rect(board, outer))
        pi = project_polygon(cam, board_world_rect(board, inner))
        if po is None or pi is None:
            raise RegionError(f"{spec!r}: ring crosses the camera near plane")
        return Region(name, spec, _poly_mask(size, [_scale_poly(po, sx, sy)], [_scale_poly(pi, sx, sy)]),
                      proxy=True, note="board-ring proxy (not a stencil layer mask)", kind=kind)
    raise RegionError(f"unknown region kind {kind!r} in {spec!r}")


def nearest_rank(sorted_vals: np.ndarray, q: float) -> float:
    """Percentile as in tools/s05/s05_frame_measure.ps1: sorted[floor(n*q)]."""
    n = sorted_vals.size
    k = min(n - 1, int(np.floor(n * q)))
    return float(sorted_vals[k])


def luma_stats(rgb_u8: np.ndarray, mask: Optional[np.ndarray] = None, stride: int = 1) -> dict:
    """Rec.709 luma p50/p90 (+mean/min/max, dark/bright shares) and mean
    relative luminance of the pixels selected by mask on a stride grid."""
    if stride < 1:
        raise ValueError("stride must be >= 1")
    img = rgb_u8[::stride, ::stride]
    sel = None if mask is None else mask[::stride, ::stride]
    px = img.reshape(-1, 3) if sel is None else img[sel]
    n = int(px.shape[0])
    if n == 0:
        return {"pixels": 0}
    y = color.luma_u8(px)
    ys = np.sort(y)
    lum = color.relative_luminance(px)
    return {
        "pixels": n,
        "luma_mean": round(float(y.mean()), 3),
        "luma_p50": round(nearest_rank(ys, 0.50), 3),
        "luma_p90": round(nearest_rank(ys, 0.90), 3),
        "luma_min": round(float(ys[0]), 3),
        "luma_max": round(float(ys[-1]), 3),
        "dark_under_30_pct": round(float((y < 30).mean() * 100), 3),
        "bright_over_150_pct": round(float((y > 150).mean() * 100), 3),
        "rel_luminance_mean": round(float(lum.mean()), 6),
    }
