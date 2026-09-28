"""Shared helpers for QA-010 tests (synthetic images, paths, CLI runner)."""

from __future__ import annotations

import io
import json
import math
import sys
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

import numpy as np
from PIL import Image

QA010_DIR = Path(__file__).resolve().parents[1]
REPO = QA010_DIR.parents[2]
EVIDENCE = REPO / "docs" / "game-design" / "evidence"
FIXTURE_TRACE = QA010_DIR / "fixtures" / "new-trace-k2-plate.trace.txt"
if str(QA010_DIR) not in sys.path:
    sys.path.insert(0, str(QA010_DIR))


def solid(w, h, rgb):
    a = np.zeros((h, w, 3), dtype=np.uint8)
    a[...] = rgb
    return a


def save_png(path: Path, arr: np.ndarray, mode: str | None = None) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    im = Image.fromarray(arr)
    if mode:
        im = im.convert(mode)
    im.save(path)
    return path


def srgb_decode(v: int) -> float:
    """Independent scalar IEC 61966-2-1 decode for expected values."""
    c = v / 255.0
    return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4


def rel_lum(rgb) -> float:
    return 0.2126 * srgb_decode(rgb[0]) + 0.7152 * srgb_decode(rgb[1]) + 0.0722 * srgb_decode(rgb[2])


def run_cli(*args) -> tuple[int, dict | None, str]:
    """Run qa010.main in-process; returns (exit code, parsed stdout JSON, stderr)."""
    import qa010  # noqa: WPS433 (module is the CLI script)
    out, err = io.StringIO(), io.StringIO()
    with redirect_stdout(out), redirect_stderr(err):
        code = qa010.main([str(a) for a in args])
    text = out.getvalue()
    try:
        data = json.loads(text) if text.strip() else None
    except json.JSONDecodeError:
        data = None
    return code, data, err.getvalue()


def topdown_trace(plate=None, reachable=None, icon=None, width=4, height=3, name="topdown.png",
                  cam_z=1000.0) -> str:
    """Synthetic trace: camera straight down (pitch -90, yaw 0) at cam_z uu
    above the board, so every cell projects to an axis-aligned rectangle of
    exactly 100/cam_z*focal px. Fighter screen values computed independently."""
    focal = 960.0 / math.tan(math.radians(17.5))
    c00 = (-(width - 1) * 50.0, -(height - 1) * 50.0)
    cmax = ((width - 1) * 50.0, (height - 1) * 50.0)
    lines = [
        f"2026.09.28-00.00.00 BOARD {width}x{height} cells | control points: (0,0)=({c00[0]:.0f},{c00[1]:.0f},0) "
        f"({width - 1},{height - 1})=({cmax[0]:.0f},{cmax[1]:.0f},0) | neighbor pair (dist 100 uu)",
        f"2026.09.28-00.00.01 SHOT ctx viewport=1920x1080 viewTarget=Cam cam=(0,0,{cam_z:.0f}) rot=(-90,0,0)",
    ]
    for i, (cx, cy) in enumerate([(0, 0), (width - 1, height - 1), (1, 1)]):
        wx, wy = c00[0] + cx * 100, c00[1] + cy * 100
        # camera right axis = +Y world, up axis = +X world, depth 1000
        sx = 960 + wy / cam_z * focal
        sy = 540 - wx / cam_z * focal
        lines.append(f"2026.09.28-00.00.01 SHOT fighter f-{i} pos=({cx},{cy}) world=({wx:.0f},{wy:.0f},0) "
                     f"screen=({sx:.2f},{sy:.2f}) projected=1 alive=1")
    if reachable is not None:
        cells = "".join(f"({x},{y})" for x, y in reachable)
        lines.append(f"2026.09.28-00.00.01 SHOT reachable fighter=f-0 n={len(reachable)} cells={cells}")
    if plate is not None:
        lines.append("2026.09.28-00.00.01 SHOT plate fighter=f-0 bbox=({},{},{},{})".format(*plate))
    if icon is not None:
        lines.append("2026.09.28-00.00.01 SHOT icon fighter=f-0 bbox=({},{},{},{})".format(*icon))
    lines.append(f"2026.09.28-00.00.01 SHOT requested: FScreenshotRequest(bShowUI) -> C:\\t\\{name}")
    return "\n".join(lines) + "\n"


def topdown_cell_rect(x, y, width=4, height=3, cam_z=1000.0):
    """Screen rect of a cell under topdown_trace (independent formula)."""
    focal = 960.0 / math.tan(math.radians(17.5))
    wx = -(width - 1) * 50.0 + x * 100
    wy = -(height - 1) * 50.0 + y * 100
    k = focal / cam_z
    sx0, sx1 = 960 + (wy - 50) * k, 960 + (wy + 50) * k
    sy0, sy1 = 540 - (wx + 50) * k, 540 - (wx - 50) * k
    return (sx0, sy0, sx1, sy1)
