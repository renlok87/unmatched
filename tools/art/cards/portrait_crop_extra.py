#!/usr/bin/env python3
"""CP-07 crop for portraits outside the MVP pair (VC C4, ВР-VC-20, CLOSEOUT п. 8): the server bot of VS_AI, T. Rex.

The same rule as the accepted CP-07 package (art/imagegen/portrait-crop-v1-codex, variant B, accepted by delegation
165c3be7): a start crop (cx, cy, d) in fractions of the source side, B = start shifted up by `shift` with the diameter
-0.06; the eye landmarks (marked by hand in original pixels) must lie inside the central 60 % of the circle; every
display (32...160 su at x1 / x1.5 / x2 / x3) is listed against the 1.6x magnification limit. The circle is drawn with
the package's own `portrait()` (Cairo edge + Pillow bilinear UV sampling of the original pixels, no enhancement).

Source: <repo>/scraped-data/derived/ue-media-v1/avatars/<hero>.png (CP-01 convert of the backend's Hero.avatarUrl,
tools/art/cards/convert_card_media.py, pixel-equal to the WebP). Out of git (ВР-VS4-01): the review sheets with the
avatar go to scraped-data/derived/visual-evidence/VC-C4/portrait-<hero>/ (colour + grey). In git: the crop record
art/cards-v1/portrait-crops-extra.json (read by ue_import_card_media.py next to the CP-07 portrait-crops.json) and the
verification art/cards-v1/portrait-crop-extra-verification.json (numbers and sheet hashes, no pixels).

  python tools/art/cards/portrait_crop_extra.py            build record + verification + sheets
  python tools/art/cards/portrait_crop_extra.py --check    recompute and compare with the committed record (no writes)
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import math
import sys
from pathlib import Path

from PIL import Image, ImageDraw

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
PACKAGE = REPO / "art/imagegen/portrait-crop-v1-codex"
RECORD = REPO / "art/cards-v1/portrait-crops-extra.json"
VERIFY = REPO / "art/cards-v1/portrait-crop-extra-verification.json"
SOURCE_ROOT = REPO / "scraped-data/derived/ue-media-v1"
REVIEW = REPO / "scraped-data/derived/visual-evidence/VC-C4"
# start (cx, cy, d), shift as in CP-07 (heroes 0.04); eyes in original pixels (one eye: the head is in profile)
CHARACTERS = {
    "t-rex": {"source": "avatars/t-rex.png", "start": (0.52, 0.40, 0.78), "shift": 0.04, "eyes": [(334, 145)],
              "monogram": "TR", "why": "the head in profile: the eye, the brow ridge and the open jaw with the teeth are "
              "the read at 32 su; the neck and the ferns are cut"},
}
SIZES = (32, 40, 64, 80, 120, 160)
SCALES = (("x1", 1.0), ("x1.5", 1.5), ("x2", 2.0), ("x3", 3.0))
LIMIT = 1.6
EYE_FRACTION = 0.6


def package_module():
    spec = importlib.util.spec_from_file_location("cp07_build_portraits", PACKAGE / "_tools/build_portraits.py")
    mod = importlib.util.module_from_spec(spec)
    sys.dont_write_bytecode = True
    spec.loader.exec_module(mod)
    return mod


def crop_b(c: dict) -> tuple[float, float, float]:
    x, y, d = c["start"]
    return (x, round(y - c["shift"], 6), round(d - 0.06, 6))


def eye_rows(c: dict, crop, side: int) -> list[dict]:
    cx, cy, d = crop
    r = d * side / 2
    out = []
    for ex, ey in c["eyes"]:
        dist = math.hypot(ex - cx * side, ey - cy * side)
        out.append({"eye_px": [ex, ey], "distance_px": round(dist, 2), "radius_px": round(r, 2),
                    "fraction_of_radius": round(dist / r, 4), "inside_central_60": dist <= EYE_FRACTION * r + 1e-9})
    return out


def magnification_rows(crop, side: int) -> list[dict]:
    src = side * crop[2]
    rows = []
    for su in SIZES:
        for tag, k in SCALES:
            n = round(su * k)
            rows.append({"su": su, "scale": tag, "display_px": n, "source_crop_px": round(src, 3),
                         "magnification": round(n / src, 4), "allowed": n <= LIMIT * src + 1e-9})
    return rows


def compute() -> dict:
    out = {}
    for name, c in CHARACTERS.items():
        path = SOURCE_ROOT / c["source"]
        with Image.open(path) as im:
            side, h = im.size
        if side != h:
            raise SystemExit(f"{name}: source {side}x{h} is not square")
        crop = crop_b(c)
        box = [(crop[0] - crop[2] / 2) * side, (crop[1] - crop[2] / 2) * side,
               (crop[0] + crop[2] / 2) * side, (crop[1] + crop[2] / 2) * side]
        out[name] = {"crop": crop, "side": side, "box_px": [round(v, 2) for v in box],
                     "inside_source": box[0] >= 0 and box[1] >= -1e-6 and box[2] <= side and box[3] <= side + 1e-6,
                     "eyes": eye_rows(c, crop, side), "magnification": magnification_rows(crop, side),
                     "source": {"path": f"scraped-data/derived/ue-media-v1/{c['source']}",
                                "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}}
    return out


def sheets(name: str, c: dict, res: dict, mod) -> list[Path]:
    src = Image.open(SOURCE_ROOT / c["source"]).convert("RGBA")
    crop = res["crop"]
    dest = REVIEW / f"portrait-{name}"
    dest.mkdir(parents=True, exist_ok=True)
    written = []
    for tag, k in SCALES[:3]:
        w = 40 + sum(round(su * k) + 24 for su in SIZES) + 40 + 2 * (round(80 * k) + 24)
        h = 110 + round(160 * k) + 60
        im = mod.sheet(max(w, 720), h, f"VC C4 / CP-07 B / {name} / {tag}",
                       f"cx {crop[0]:.2f}  cy {crop[1]:.2f}  d {crop[2]:.2f} - own pixels, no resize of the sheet")
        x = 28
        for su in SIZES:
            n = round(su * k)
            im.alpha_composite(mod.portrait(src, crop, n, su), (x, 110))
            mod.label(im, (x, 110 + n + 6), f"{su}", 12)
            x += n + 24
        x += 16
        n = round(80 * k)
        im.alpha_composite(mod.fallback(n, 80, c["monogram"]), (x, 110))  # the monogram it replaces
        mod.label(im, (x, 110 + n + 6), "was: monogram", 12)
        x += n + 24
        loser = mod.portrait(src, crop, n, 80)
        loser = mod.grey(loser)
        a = loser.getchannel("A").point(lambda v: round(v * 0.6))
        loser.putalpha(a)
        im.alpha_composite(loser, (x, 110))
        mod.label(im, (x, 110 + n + 6), "fallen 0.6", 12)
        p = dest / f"working-{tag}.png"
        im.save(p)
        mod.grey(im).save(p.with_stem(p.stem + "-gray"))
        written += [p, p.with_stem(p.stem + "-gray")]
    # landmark sheet: original pixels, crop circle, central 60 %
    side = res["side"]
    view = 520
    lm = src.resize((view, view), Image.Resampling.BILINEAR)
    d = ImageDraw.Draw(lm)
    s = view / side
    cx, cy, dd = crop
    r = dd * side / 2 * s
    d.ellipse((cx * side * s - r, cy * side * s - r, cx * side * s + r, cy * side * s + r), outline="#FFFFFF", width=2)
    r6 = r * EYE_FRACTION
    d.ellipse((cx * side * s - r6, cy * side * s - r6, cx * side * s + r6, cy * side * s + r6), outline="#F9EBDB",
              width=1)
    for ex, ey in c["eyes"]:
        d.line((ex * s - 6, ey * s, ex * s + 6, ey * s), fill="#00FF00", width=2)
        d.line((ex * s, ey * s - 6, ex * s, ey * s + 6), fill="#00FF00", width=2)
    sheet = mod.sheet(view + 56, view + 140, f"VC C4 / CP-07 eye landmark / {name}",
                      "white = crop B circle, cream = central 60 %, green = eye (original pixels)")
    sheet.alpha_composite(lm, (28, 110))
    p = dest / "eye-landmarks.png"
    sheet.save(p)
    mod.grey(sheet).save(p.with_stem(p.stem + "-gray"))
    written += [p, p.with_stem(p.stem + "-gray")]
    return written


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--check", action="store_true")
    a = ap.parse_args(argv)
    res = compute()
    record = {k: dict(zip(("cx", "cy", "d"), v["crop"])) for k, v in res.items()}
    ok = all(v["inside_source"] and all(e["inside_central_60"] for e in v["eyes"]) for v in res.values())
    if a.check:
        committed = json.loads(RECORD.read_text(encoding="utf-8")) if RECORD.is_file() else None
        same = committed == record
        print(f"PORTRAIT-CROP-EXTRA check {'ok' if same and ok else 'FAILED'} record={'same' if same else 'differs'}")
        return 0 if same and ok else 1
    mod = package_module()
    files = []
    for name, c in CHARACTERS.items():
        files += sheets(name, c, res[name], mod)
    RECORD.write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8", newline="\n")
    verify = {
        "schema": "unmatched.portrait-crop-extra/1", "card": "CP-07 (VC C4, ВР-VC-20)",
        "rule": "CP-07 variant B: start shifted up by shift, d - 0.06; eyes inside the central 60 % of the circle; "
                "magnification <= 1.6x listed per display (art/imagegen/portrait-crop-v1-codex/README.md)",
        "image_generation_used": False,
        "characters": {k: dict(v, why=CHARACTERS[k]["why"], start=CHARACTERS[k]["start"]) for k, v in res.items()},
        "over_limit": [dict(r, character=k) for k, v in res.items() for r in v["magnification"] if not r["allowed"]],
        "acceptance": ok,
        "sheets_out_of_git": [{"path": p.relative_to(REPO).as_posix(),
                               "sha256": hashlib.sha256(p.read_bytes()).hexdigest()} for p in files],
    }
    VERIFY.write_text(json.dumps(verify, indent=1, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n")
    for k, v in res.items():
        print(f"PORTRAIT-CROP-EXTRA {k} crop={v['crop']} eyes={[e['fraction_of_radius'] for e in v['eyes']]} "
              f"overLimit={sum(not r['allowed'] for r in v['magnification'])}")
    print(f"PORTRAIT-CROP-EXTRA {'ok' if ok else 'FAILED'} sheets={len(files)} record={RECORD.relative_to(REPO)}")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
