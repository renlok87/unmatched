"""Before/after sheet for the HUD icon set v2 (art/imagegen/hud-icons-v2): was (v2 card_icons / mvp-v1) -> now at 128/32/24 px,
24 px on a light background, greyscale 128 and 24 px; plus greyscale strips at 24 and 32 px (x4).

  python art/imagegen/hud-icons-v2/_tools/compare_icons.py
"""
import json, sys
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont, ImageOps

ROOT = Path("C:/Users/ren/WebstormProjects/unmached/unmached")
OUT = ROOT / "art/imagegen/hud-icons-v2"
SRC = Path(sys.argv[1]) if len(sys.argv) > 1 and not sys.argv[1].startswith("--") else OUT
MVP = ROOT / "art/imagegen/mvp-v1"
REF = OUT / "reference-v2"
# id -> before image path
BEFORE = {
 "state-boost": REF / "v2-boost-256.png", "state-enemy": REF / "v2-enemy-256.png", "state-sent": REF / "v2-sent-256.png",
 "state-pending-move": REF / "v2-pending-move-256.png", "state-pending-place": REF / "v2-pending-place-256.png",
 "state-hint": REF / "v2-hint-256.png", "state-threat": REF / "v2-threat-256.png", "state-immobilized": REF / "v2-immobilized-256.png",
 "action-attack": MVP / "ui/actions/ui-action-attack-normal.png", "action-attack-token": MVP / "ui/actions/sized/ui-action-attack-token-48.png",
 "action-defense": MVP / "ui/actions/ui-action-defense-normal.png", "action-maneuver": MVP / "ui/actions/ui-action-maneuver-normal.png",
 "action-scheme": MVP / "ui/actions/ui-action-scheme-normal.png", "marker-status": MVP / "markers/marker-status.png",
 "loader-spinner": MVP / "ui/loaders/ui-loader-spinner-normal.png",
 "resource-action-full": MVP / "ui/resources/ui-resource-action-full.png", "resource-action-empty": MVP / "ui/resources/ui-resource-action-empty.png",
 "resource-card": MVP / "ui/resources/ui-resource-card.png", "resource-connection-online": MVP / "ui/resources/ui-resource-connection-online.png",
 "resource-connection-reconnecting": MVP / "ui/resources/ui-resource-connection-reconnecting.png",
 "resource-connection-lost": MVP / "ui/resources/ui-resource-connection-lost.png",
 "resource-hp-full": MVP / "ui/resources/ui-resource-hp-full.png", "resource-hp-empty": MVP / "ui/resources/ui-resource-hp-empty.png",
}
FONT = ImageFont.truetype("C:/Windows/Fonts/arial.ttf", 14)


def key_green(im):
    """Flat #00FF00 background -> alpha (only if the image has no real alpha)."""
    im = im.convert("RGBA")
    if im.getchannel("A").getextrema()[0] < 250:
        return im
    px = im.load()
    for y in range(im.height):
        for x in range(im.width):
            r, g, b, a = px[x, y]
            if g > 180 and r < 120 and b < 120:
                px[x, y] = (0, 0, 0, 0)
    return im


def fit(im, s):
    im = im.copy()
    bb = im.getchannel("A").getbbox()
    if bb:
        im = im.crop(bb)
    wide = im.width > 1.5 * im.height          # title plates: judge by height, width 2x
    im.thumbnail((2 * s if wide else s, s), Image.LANCZOS)
    c = Image.new("RGBA", (2 * s if wide else s, s), (0, 0, 0, 0))
    c.alpha_composite(im, ((c.width - im.width) // 2, (c.height - im.height) // 2))
    return c


def cell(im, bg, s):
    f = fit(im, s)
    c = Image.new("RGBA", f.size, bg)
    c.alpha_composite(f)
    return c


def gray(im):
    g = ImageOps.grayscale(im.convert("RGB"))
    return Image.merge("RGBA", (g, g, g, im.getchannel("A")))


def main():
    ids = [i for i in BEFORE if (SRC / f"{i}.png").exists()]
    row_h = 140
    cols = [("было 128", 128), ("стало 128", 128), ("стало 32", 32), ("стало 24", 24), ("24 светлый", 24), ("серый 128", 128), ("24 серый", 24)]
    W = 260 + sum(max(2 * s, 60) + 20 for _, s in cols)
    S = Image.new("RGBA", (W, 50 + row_h * len(ids)), (6, 22, 35, 255))
    d = ImageDraw.Draw(S)
    x = 260
    for name, s in cols:
        d.text((x, 15), name, font=FONT, fill=(249, 235, 219))
        x += max(2 * s, 60) + 20
    for r, i in enumerate(ids):
        y = 50 + r * row_h
        before = key_green(Image.open(BEFORE[i]))
        after = key_green(Image.open(SRC / f"{i}.png"))
        d.text((12, y + 50), i, font=FONT, fill=(249, 235, 219))
        x = 260
        tiles = [cell(before, (40, 48, 60, 255), 128), cell(after, (40, 48, 60, 255), 128), cell(after, (40, 48, 60, 255), 32),
                 cell(after, (40, 48, 60, 255), 24), cell(after, (230, 220, 200, 255), 24), cell(gray(after), (128, 128, 128, 255), 128),
                 cell(gray(after), (128, 128, 128, 255), 24)]
        for t, (_, s) in zip(tiles, cols):
            S.alpha_composite(t, (x, y + (128 - s) // 2))
            x += max(2 * s, 60) + 20
    S.save(OUT / "compare-sheet.png", optimize=True)
    # 24 px gray strip: all icons side by side at 24 and 32 px (x4 nearest) for the distinctness check
    for s in (24, 32):
        strip = Image.new("RGBA", (len(ids) * (2 * s + 8) + 8, s + 16), (128, 128, 128, 255))
        for k, i in enumerate(ids):
            strip.alpha_composite(fit(gray(key_green(Image.open(SRC / f"{i}.png"))), s), (8 + k * (2 * s + 8), 8))
        strip.resize((strip.width * 4, strip.height * 4), Image.NEAREST).save(OUT / f"compare-gray-{s}px-x4.png", optimize=True)
    print("sheet rows:", len(ids), "missing:", [i for i in BEFORE if i not in ids])


if __name__ == "__main__":
    main()
