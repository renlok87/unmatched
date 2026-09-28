"""PNG I/O helpers. Inputs are only ever read; outputs go to caller paths."""

from __future__ import annotations

import hashlib
from pathlib import Path

import numpy as np

try:
    from PIL import Image
except ImportError as exc:  # pragma: no cover - environment guard
    raise SystemExit("qa010 image commands need Pillow (pip install pillow)") from exc


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def load_rgb(path: Path) -> np.ndarray:
    """Load any PNG/JPEG as uint8 (H, W, 3). Alpha is dropped, not composited."""
    with Image.open(path) as im:
        im.load()
        if im.mode in ("I;16", "I;16B", "I;16L", "I", "F"):
            raise ValueError(f"{path}: {im.mode} images are not 8-bit sRGB screenshots")
        rgb = im.convert("RGB")
        return np.asarray(rgb, dtype=np.uint8).copy()


def load_mask(path: Path, size: tuple[int, int] | None = None) -> np.ndarray:
    """Binary mask from PNG. Uses alpha >= 128 when the file has an alpha
    channel that is not fully opaque; otherwise grayscale value >= 128.
    ``size`` = (width, height) the mask must match (no silent resampling)."""
    with Image.open(path) as im:
        im.load()
        if size is not None and im.size != tuple(size):
            raise ValueError(f"mask {path} is {im.size[0]}x{im.size[1]}, frame is {size[0]}x{size[1]}")
        has_alpha = im.mode in ("RGBA", "LA", "PA") or "transparency" in im.info
        if has_alpha:
            alpha = np.asarray(im.convert("RGBA"), dtype=np.uint8)[..., 3]
            if alpha.min() < 255:
                return alpha >= 128
        return np.asarray(im.convert("L"), dtype=np.uint8) >= 128


def save_rgb(path: Path, rgb_u8: np.ndarray) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    Image.fromarray(np.ascontiguousarray(rgb_u8, dtype=np.uint8)).save(path, format="PNG", optimize=False)


def save_mask(path: Path, mask: np.ndarray) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    Image.fromarray(np.ascontiguousarray(mask.astype(np.uint8) * 255)).save(path, format="PNG")
