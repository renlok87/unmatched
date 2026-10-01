"""Concept paste (ENV-U15, track ENV-MAPS P7): shared geometry, image and camera helpers.

World = the S08 board frame of tools/art/map_surface/k1_mock.py (X right / east, Y towards the K1 camera / south,
Z up, map centre = origin, map plane Z = 0). The concept images (Codex imagegen edits of the k1_mock 'wide' base
render, scraped-data/derived/concepts/env-v1, OUT of git - ENV-U3/U7) are seen from the concept camera C0: pinhole
HFOV 35 deg, 16:9, pitch -55, yaw -90, looking at the origin from distance 1.45 x the S08 fit (2714.63 uu).

Everything in this package reads / writes images only outside git (C:/tmp/envmaps-research/p7/...); git holds the
scripts, the parameters and sha256 values.
"""
from __future__ import annotations

import hashlib
import json
import math
import sys
from pathlib import Path

import numpy as np
from PIL import Image
from scipy import ndimage

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
sys.path.insert(0, str(REPO / "tools/art/map_surface"))
import k1_mock  # noqa: E402

MAIN = Path("C:/Users/ren/WebstormProjects/unmached/unmached")
CONCEPTS = MAIN / "scraped-data/derived/concepts/env-v1"
DERIVED_MAPS = MAIN / "scraped-data/derived/maps"
EV_RESEARCH = REPO / "docs/game-design/evidence/ENV-MAPS/2026-09-30-research"
W, H = 1920, 1080
SRC_W, SRC_H = 1337, 866
UU_PER_PX = 2.0 / 3.0
MAP_HX, MAP_HY = SRC_W * UU_PER_PX / 2, SRC_H * UU_PER_PX / 2  # 445.667 x 288.667
FRAME_UU = 24.0
FRAME_HX, FRAME_HY = MAP_HX + FRAME_UU, MAP_HY + FRAME_UU      # 469.667 x 312.667 (ASSET-MAP-FRAME-002 wood)
FRAME_TOP_Z = 12.4                                              # frame-002 profile woodZ max
TRAY_TOP_Z = -3.0
TRAY_T2 = {"halfX": 780.0, "halfY": 470.0, "offsetY": -45.0}
SEA_Z = -172.0                                                  # SM_Env_S_SeaRing loc z (sarpedon.layout.json)
FIT = k1_mock.s08_fit_distance(MAP_HX, MAP_HY)                 # 1872.156
CONCEPT_MUL = 1.45
D_CONCEPT = FIT * CONCEPT_MUL                                   # 2714.63
D_K1 = FIT * 1.25                                               # 2340.20 (k1DistanceMul, ENV-U9)
D_FAR = FIT / 0.65                                              # 2880.24 (far wheel limit = bench K1x0.65)
D_K2 = D_K1 / 1.6                                               # 1462.62 (bench K2x1.6)
FOLLOW_Z = 28.0
MAPS = {"sarpedon": {"name": "Sarpedon", "concept": "sarpedon-v2.png", "base": "sarpedon-wide-base.png"},
        "marmoreal": {"name": "Marmoreal", "concept": "marmoreal-v1.png", "base": "marmoreal-wide-base.png"}}
# bench K2x1.6 focus on Medusa (P5c Sarpedon trace: cam (-218, 826, 1226) at D_K2 -> focus (-218, -13, 28))
K2_HERO_FOCUS = {"sarpedon": (-218.0, -13.0, FOLLOW_Z), "marmoreal": None}


class Cam:
    """Pinhole camera of the S08 rig: pitch -55, yaw -90, HFOV 35, looking at `focus` from `dist`."""

    def __init__(self, dist: float, focus=(0.0, 0.0, 0.0), w: int = W, h: int = H, hfov: float = 35.0,
                 pitch: float = 55.0):
        p = math.radians(pitch)
        self.focus = np.asarray(focus, float)
        self.dist = float(dist)
        self.pos = self.focus + np.array([0.0, dist * math.cos(p), dist * math.sin(p)])
        self.fwd = np.array([0.0, -math.cos(p), -math.sin(p)])
        self.right = np.array([1.0, 0.0, 0.0])
        self.up = np.array([0.0, -math.sin(p), math.cos(p)])
        self.tan_h = math.tan(math.radians(hfov / 2))
        self.tan_v = self.tan_h / (16.0 / 9.0)
        self.w, self.h = w, h
        self.f_px = (w / 2) / self.tan_h

    def rays(self, xs: np.ndarray, ys: np.ndarray) -> np.ndarray:
        """Unnormalised world ray directions through pixel coordinates (x right, y down, centres at i + 0.5)."""
        sx = (np.asarray(xs, float) / self.w * 2 - 1) * self.tan_h
        sy = (1 - np.asarray(ys, float) / self.h * 2) * self.tan_v
        return self.fwd + sx[..., None] * self.right + sy[..., None] * self.up

    def project(self, P) -> tuple[np.ndarray, np.ndarray]:
        """World points (..., 3) -> (pixel xy (..., 2), view depth along fwd (...))."""
        v = np.asarray(P, float) - self.pos
        z = v @ self.fwd
        sx = (v @ self.right) / z / self.tan_h
        sy = (v @ self.up) / z / self.tan_v
        return np.stack([(sx + 1) / 2 * self.w, (1 - sy) / 2 * self.h], -1), z

    def to_json(self) -> dict:
        return {"pos": [round(float(c), 3) for c in self.pos], "focus": [float(c) for c in self.focus],
                "dist": round(self.dist, 3), "pitch": -55, "yaw": -90, "hfov": 35, "size": [self.w, self.h]}


def concept_cam(w: int = W, h: int = H) -> Cam:
    return Cam(D_CONCEPT, (0, 0, 0), w, h)


def game_views(map_key: str) -> dict[str, Cam]:
    views = {"concept": concept_cam(), "K1": Cam(D_K1), "K1x0.65": Cam(D_FAR), "K2x1.6c": Cam(D_K2)}
    if K2_HERO_FOCUS.get(map_key):
        views["K2x1.6hero"] = Cam(D_K2, K2_HERO_FOCUS[map_key])
    return views


def src_to_world(px) -> np.ndarray:
    px = np.asarray(px, float)
    return np.stack([(px[..., 0] / SRC_W - 0.5) * 2 * MAP_HX, (px[..., 1] / SRC_H - 0.5) * 2 * MAP_HY], -1)


# ------------------------------------------------------------------ images
def sha256(path: Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def load_rgb(path: Path, size=None) -> np.ndarray:
    """sRGB float32 0..1; `size` = (w, h) resamples with Lanczos (PIL, classic - ENV-U6: no AI upscale)."""
    im = Image.open(path).convert("RGB")
    if size and im.size != tuple(size):
        im = im.resize(tuple(size), Image.LANCZOS)
    return np.asarray(im).astype(np.float32) / 255.0


def save_rgb(path: Path, img: np.ndarray, quality: int | None = None):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    a = np.clip(np.round(np.asarray(img, np.float32) * 255), 0, 255).astype(np.uint8)
    im = Image.fromarray(a, "L" if a.ndim == 2 else "RGB")
    if path.suffix.lower() in (".jpg", ".jpeg"):
        im.save(path, quality=quality or 90)
    else:
        im.save(path)


def luma(img: np.ndarray) -> np.ndarray:
    """Rec.709 luma of sRGB values (the measure.py convention: Y on 0..255 = 255 x this)."""
    return img[..., 0] * 0.2126 + img[..., 1] * 0.7152 + img[..., 2] * 0.0722


def bilinear(img: np.ndarray, x: np.ndarray, y: np.ndarray, fill=0.0) -> np.ndarray:
    """Sample img at pixel coordinates (centres at i + 0.5); outside -> fill."""
    h, w = img.shape[:2]
    fx, fy = np.asarray(x, np.float64) - 0.5, np.asarray(y, np.float64) - 0.5
    inside = (fx >= -0.5) & (fy >= -0.5) & (fx <= w - 0.5) & (fy <= h - 0.5)
    x0 = np.clip(np.floor(fx).astype(np.int64), 0, w - 1)
    y0 = np.clip(np.floor(fy).astype(np.int64), 0, h - 1)
    x1, y1 = np.clip(x0 + 1, 0, w - 1), np.clip(y0 + 1, 0, h - 1)
    ax = np.clip(fx - np.floor(fx), 0, 1).astype(np.float32)
    ay = np.clip(fy - np.floor(fy), 0, 1).astype(np.float32)
    if img.ndim == 3:
        ax, ay, ins = ax[..., None], ay[..., None], inside[..., None]
    else:
        ins = inside
    top = img[y0, x0] * (1 - ax) + img[y0, x1] * ax
    bot = img[y1, x0] * (1 - ax) + img[y1, x1] * ax
    return np.where(ins, top * (1 - ay) + bot * ay, fill).astype(np.float32)


def dump_json(path: Path, obj):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=1, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n")


def feather(mask: np.ndarray, px: float) -> np.ndarray:
    """Soft 0..1 edge: signed distance to the mask border mapped over [-px/2, +px/2]."""
    m = mask.astype(bool)
    d_in = ndimage.distance_transform_edt(m)
    d_out = ndimage.distance_transform_edt(~m)
    sd = np.where(m, d_in - 0.5, -(d_out - 0.5))
    return np.clip(sd / max(px, 1e-6) + 0.5, 0, 1).astype(np.float32)
