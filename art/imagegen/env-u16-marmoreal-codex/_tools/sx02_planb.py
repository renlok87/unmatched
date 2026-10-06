"""EN-03 plan B (SX-02 cancelled by the price rule): classic Lanczos-3 x2 of the accepted EN-02 plates, no AI.
Written by Claude, 2026-10-07 (ВР-VS3-EN03-01). The kernel is the one of tools/art/concept_paste/cp_bake.py
(lanczos_sample, sRGB float 0..1, texel centres at i + 0.5, edge clamp, normalised weights), imported, not copied.

Run with python -B from the repository root:
  python -B art/imagegen/env-u16-marmoreal-codex/_tools/sx02_planb.py build
  python -B art/imagegen/env-u16-marmoreal-codex/_tools/sx02_planb.py sheets

Images (they contain the concept painting) go only to scraped-data/derived/env-u16-marmoreal-codex/.
No provider, git or Unreal calls.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw
from scipy import ndimage

ROOT = Path(__file__).resolve().parents[4]
PKG = ROOT / "art/imagegen/env-u16-marmoreal-codex"
IMG = ROOT / "scraped-data/derived/env-u16-marmoreal-codex"
sys.path.insert(0, str(ROOT / "tools/art/concept_paste"))
from cp_bake import lanczos_sample  # noqa: E402

PAIRS = [("marmoreal-clean-ext.png", "marmoreal-extended-2x.png"),
         ("marmoreal-lit-ext.png", "marmoreal-lit-extended-2x.png")]
SRC_SIZE = (2340, 1317)
OUT_SIZE = (4680, 2634)
BOX = (334, 188, 2006, 1129)
# EN-01 light positions in concept px (card EN-01 states) -> canvas (+334, +188) -> x2.
LIGHTS = {"lantern-nw": (424, 90), "lantern-ne": (1245, 88), "lantern-w": (152, 497), "lantern-e": (1520, 505),
          "sconce-door-w": (787, 27), "sconce-door-e": (877, 27)}


def sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def rel(p: Path) -> str:
    return p.resolve().relative_to(ROOT).as_posix()


def write_json(p: Path, v) -> None:
    assert p.resolve().is_relative_to(PKG)
    p.write_text(json.dumps(v, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def upscale(src: np.ndarray) -> np.ndarray:
    h, w = OUT_SIZE[1], OUT_SIZE[0]
    out = np.zeros((h, w, 3), np.float32)
    xs = (np.arange(w) + .5) / 2.0
    for r0 in range(0, h, 128):
        r1 = min(h, r0 + 128)
        ys = (np.arange(r0, r1) + .5) / 2.0
        PX, PY = np.meshgrid(xs, ys)
        out[r0:r1] = lanczos_sample(src, PX, PY, 1.0, 1.0, 3)
    return out


def luma8(a: np.ndarray) -> np.ndarray:
    return a[..., :3].astype(np.float64) @ np.array([.299, .587, .114])


def ssim(a: np.ndarray, b: np.ndarray) -> float:
    """Mean SSIM of 8-bit luma, Gaussian window sigma 1.5 (Wang et al. 2004 constants)."""
    c1, c2 = (0.01 * 255) ** 2, (0.03 * 255) ** 2
    f = lambda x: ndimage.gaussian_filter(x, 1.5, truncate=3.5)  # noqa: E731
    mu_a, mu_b = f(a), f(b)
    saa = f(a * a) - mu_a ** 2
    sbb = f(b * b) - mu_b ** 2
    sab = f(a * b) - mu_a * mu_b
    m = ((2 * mu_a * mu_b + c1) * (2 * sab + c2)) / ((mu_a ** 2 + mu_b ** 2 + c1) * (saa + sbb + c2))
    return float(m.mean())


def cmd_build(_a):
    field = np.asarray(Image.open(IMG / "marmoreal-field-mask.png").convert("L")) > 0
    canvas_field = np.zeros(SRC_SIZE[::-1], bool)
    canvas_field[BOX[1]:BOX[3], BOX[0]:BOX[2]] = field
    field2 = np.repeat(np.repeat(canvas_field, 2, 0), 2, 1)
    field2_core = ndimage.binary_erosion(field2, iterations=6)  # Lanczos ringing reaches 3 source px = 6 output px
    rec = {"card": "EN-03", "package": "SX-02 plan B", "created_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
           "method": "classic Lanczos-3 x2 (tools/art/concept_paste/cp_bake.py lanczos_sample, sRGB 0..1, texel centres "
                     "i + 0.5, edge clamp, normalised weights, clip 0..1, round to 8 bit); no AI, no new detail",
           "why": "ВР-VS3-EN03-01: get-model-info magnific/precision_v2 width 2340 height 1317 scale_factor 2x = 18 tokens "
                  "> 12 (ВР-PR04, card EN-03 do item 3); ledger.py check: 'cancel the run'",
           "outputs": {}}
    for src_name, out_name in PAIRS:
        t0 = time.time()
        sp = IMG / src_name
        src = np.asarray(Image.open(sp).convert("RGB")).astype(np.float32) / 255.0
        assert src.shape[1::-1] == SRC_SIZE
        up = upscale(src)
        out8 = np.clip(np.rint(up * 255), 0, 255).astype("uint8")
        op = IMG / out_name
        Image.fromarray(out8).save(op)
        # Self-check: back to the input size (2x2 box = exact inverse footprint) and SSIM; grey field flatness.
        back = out8.astype(np.float64).reshape(SRC_SIZE[1], 2, SRC_SIZE[0], 2, 3).mean((1, 3))
        src8 = (src * 255).round()
        s = ssim(luma8(src8), luma8(back))
        fvals = out8[field2_core].astype(np.float64)
        rec["outputs"][rel(op)] = {
            "input": rel(sp), "input_sha256": sha(sp), "sha256": sha(op), "size": list(OUT_SIZE),
            "conceptRectPx": [668, 376, 3344, 1882], "ssim_back_to_input_luma": s, "ssim_passed": s >= .95,
            "field_core_px": int(field2_core.sum()), "field_std_levels_per_channel": [float(v) for v in fvals.std(0)],
            "field_mean": [float(v) for v in fvals.mean(0)], "field_flat_passed": bool((fvals.std(0) <= 2).all()),
            "field_808080_exact_share": float((out8[field2_core] == 128).all(-1).mean()),
            "seconds": round(time.time() - t0, 1)}
        print(json.dumps({k: v for k, v in rec["outputs"][rel(op)].items() if k not in ("input",)}, ensure_ascii=False))
    write_json(PKG / "_tools/sx02-planb-check.json", rec)


def cmd_sheets(_a):
    d = IMG / "comparison"
    made = []
    for src_name, out_name in PAIRS:
        src = Image.open(IMG / src_name).convert("RGB")
        up = Image.open(IMG / out_name).convert("RGB")
        tag = "lit" if "lit" in out_name else "clean"
        tiles = []
        for name, (cx, cy) in list(LIGHTS.items()) + [("sakura-w-edge", (-40, 280)), ("sakura-e-edge", (1724, 374))]:
            kx = (cx + 334) * 2
            ky = (cy + 188) * 2
            x0, y0 = int(max(0, min(OUT_SIZE[0] - 360, kx - 180))), int(max(0, min(OUT_SIZE[1] - 360, ky - 180)))
            a = src.crop((x0 // 2, y0 // 2, x0 // 2 + 180, y0 // 2 + 180)).resize((360, 360), Image.Resampling.NEAREST)
            b = up.crop((x0, y0, x0 + 360, y0 + 360))
            t = Image.new("RGB", (730, 390), "#202020")
            t.paste(a, (0, 30))
            t.paste(b, (370, 30))
            ImageDraw.Draw(t).text((6, 8), f"{name}: source x2 nearest | Lanczos-3 x2 (100 %), plate px {x0},{y0}", fill="white")
            tiles.append(t)
        sheet = Image.new("RGB", (730 * 2, 390 * 4), "#202020")
        for i, t in enumerate(tiles):
            sheet.paste(t, ((i % 2) * 730, (i // 2) * 390))
        for suffix, im in (("colour", sheet), ("gray", None)):
            p = d / f"ext2x-planb-{tag}-K2-crops-{suffix}.png"
            if im is None:
                y = np.asarray(sheet).astype(np.float64) / 255
                y = np.where(y <= .04045, y / 12.92, ((y + .055) / 1.055) ** 2.4) @ np.array([.2126, .7152, .0722])
                g = np.where(y <= .0031308, 12.92 * y, 1.055 * y ** (1 / 2.4) - .055)
                im = Image.fromarray(np.clip(np.rint(g * 255), 0, 255).astype("uint8")).convert("RGB")
            im.save(p)
            made.append(rel(p))
    print(json.dumps(made, indent=1))


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("build")
    sub.add_parser("sheets")
    a = ap.parse_args()
    {"build": cmd_build, "sheets": cmd_sheets}[a.cmd](a)


if __name__ == "__main__":
    main()
