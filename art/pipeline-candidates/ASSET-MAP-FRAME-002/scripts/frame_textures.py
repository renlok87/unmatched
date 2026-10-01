"""ASSET-MAP-FRAME-002: the dark weathered iron of the brackets and rivets (system Python: numpy + PIL).

  python -B art/pipeline-candidates/ASSET-MAP-FRAME-002/scripts/frame_textures.py \
      --params art/pipeline-candidates/ASSET-MAP-FRAME-002/20261001-frame-v1/reports/frame-params.json

Sources: CC0 ambientCG Metal038 (dark cast metal) and Metal017 (rusted paint), already in the local library (no download).
  BC  sRGB 1024: Metal038 Color x base_value_scale, mixed with Metal017 Color x rust_value_scale by a tiling low-frequency
      rust mask (rust_amount of the area, periodic value noise, seamless);
  N   linear 1024: Metal038 NormalDX (DirectX: flip_green false in UE);
  ORM linear 1024: R = 1 (no AO), G = roughness (Metal038 roughness remapped to roughness_range, rust -> 0.92),
      B = metallic (Metal038 metalness x (1 - rust)).
The wood slot has no new texture: it is a MID of M_MapFrameWood (T_old_wood, the P4 frameWood look).
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import numpy as np
from PIL import Image

HERE = Path(__file__).resolve()
REPO = HERE.parents[4]


def sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def periodic_noise(size, cell, seed):
    """Seamless value noise (period = size) in [0, 1], smooth (bicubic-ish via smoothstep)."""
    n = max(1, size // cell)
    rng = np.random.default_rng(seed)
    g = rng.random((n, n))
    y, x = np.mgrid[0:size, 0:size] / cell
    x0, y0 = np.floor(x).astype(int) % n, np.floor(y).astype(int) % n
    x1, y1 = (x0 + 1) % n, (y0 + 1) % n
    fx, fy = x - np.floor(x), y - np.floor(y)
    fx, fy = fx * fx * (3 - 2 * fx), fy * fy * (3 - 2 * fy)
    a = g[y0, x0] * (1 - fx) + g[y0, x1] * fx
    b = g[y1, x0] * (1 - fx) + g[y1, x1] * fx
    return a * (1 - fy) + b * fy


def load(path, size, mode="RGB"):
    return np.asarray(Image.open(path).convert(mode).resize((size, size), Image.BOX), dtype=np.float64) / 255.0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--params", required=True)
    a = ap.parse_args(argv)
    P = json.loads(Path(a.params).read_text(encoding="utf-8"))
    T = P["iron_textures"]
    lib = Path(T["lib"])
    size = int(T["size"])
    base, rust = T["base"], T["rust"]
    src = {"base_color": lib / base / f"{base}_2K-JPG_Color.jpg", "base_normal": lib / base / f"{base}_2K-JPG_NormalDX.jpg",
           "base_rough": lib / base / f"{base}_2K-JPG_Roughness.jpg", "base_metal": lib / base / f"{base}_2K-JPG_Metalness.jpg",
           "rust_color": lib / rust / f"{rust}_2K-JPG_Color.jpg"}
    bc0 = load(src["base_color"], size) * float(T["base_value_scale"])
    rc = load(src["rust_color"], size) * float(T["rust_value_scale"])
    noise = 0.65 * periodic_noise(size, int(T["rust_noise_px"]), 7) + 0.35 * periodic_noise(size, int(T["rust_noise_px"]) // 3, 11)
    thr = np.quantile(noise, 1.0 - float(T["rust_amount"]))
    m = np.clip((noise - thr) / 0.06, 0.0, 1.0)[..., None]
    bc = bc0 * (1 - m) + rc * m
    rough = load(src["base_rough"], size, "L")
    lo, hi = T["roughness_range"]
    rough = lo + (hi - lo) * (rough - rough.min()) / max(rough.max() - rough.min(), 1e-6)
    rough = rough * (1 - m[..., 0]) + 0.92 * m[..., 0]
    metal = load(src["base_metal"], size, "L") * (1 - m[..., 0])
    orm = np.stack([np.ones_like(rough), rough, metal], -1)
    out = (REPO / P["run_dir"] / "export").resolve()
    out.mkdir(parents=True, exist_ok=True)
    pre = T["prefix"]
    paths = {"BC": out / f"{pre}_BC.png", "N": out / f"{pre}_N.png", "ORM": out / f"{pre}_ORM.png"}
    Image.fromarray((np.clip(bc, 0, 1) * 255 + 0.5).astype(np.uint8)).save(paths["BC"], optimize=True)
    Image.open(src["base_normal"]).convert("RGB").resize((size, size), Image.BOX).save(paths["N"], optimize=True)
    Image.fromarray((np.clip(orm, 0, 1) * 255 + 0.5).astype(np.uint8)).save(paths["ORM"], optimize=True)
    luma = bc @ np.array([0.2126, 0.7152, 0.0722])
    rep = {"schema": "unmatched.map-frame-002.textures/1", "status": "measured",
           "sources": {k: {"path": v.as_posix(), "sha256": sha(v)} for k, v in src.items()},
           "license": "CC0 1.0 (ambientCG) Metal038, Metal017",
           "outputs": {k: {"path": v.relative_to(REPO).as_posix(), "sha256": sha(v), "bytes": v.stat().st_size,
                           "size": [size, size]} for k, v in paths.items()},
           "stats": {"bcMeanLumaSrgb": round(float(luma.mean()), 4), "rustFraction": round(float(m.mean()), 4),
                     "roughnessMean": round(float(rough.mean()), 4), "metallicMean": round(float(metal.mean()), 4)},
           "ue": {"BC": "sRGB TC_Default Wrap", "N": "TC_Normalmap DirectX (flip_green false) Wrap", "ORM": "TC_Masks linear Wrap"}}
    (REPO / P["run_dir"] / "reports" / "textures-report.json").write_text(
        json.dumps(rep, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print("FRAME-TEXTURES ok", json.dumps(rep["stats"]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
