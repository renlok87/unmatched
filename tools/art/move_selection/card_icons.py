"""Move-selection icon set v2 in the visual language of the game's cards.

Derived from the real RU card faces (scraped-data/images/decks/*, mapped in art/imagegen/mvp-v1/reused-cardart.json):
- type block: flat colour square with a white flat glyph at the top of the left banner
  (attack #DC2F33 starburst, defense #2976AE shield, versatile #6B4E8F, scheme #FDBE72 lightning);
- banner: navy #061623 vertical ribbon ending in a notch;
- BOOST: white disc with a thick navy ring and a bold navy numeral;
- titles: bold condensed caps on navy, cream card border #F9EBDB.
Font: Bahnschrift "Bold Condensed" (closest system face to the card titles).
Every icon is returned as an RGBA image; sizes are in pixels of the target canvas.
"""
from __future__ import annotations

import math

from PIL import Image, ImageDraw, ImageFont

NAVY = (6, 22, 35, 255)
NAVY_2 = (8, 39, 46, 255)
CREAM = (249, 235, 219, 255)
WHITE = (250, 248, 242, 255)
TYPE = {"attack": (220, 47, 51, 255), "defense": (41, 118, 174, 255), "versatile": (107, 78, 143, 255),
        "scheme": (253, 190, 114, 255)}
ERR = (217, 72, 63, 255)            # state.error (03 4.2) - only with X / !
PEND = (138, 86, 198, 255)          # pending marker (03 6)
P1S, P2S = (218, 197, 118, 255), (87, 134, 168, 255)
BAHN = "C:/Windows/Fonts/bahnschrift.ttf"
SYM = "C:/Windows/Fonts/seguisym.ttf"


def bahn(size: int) -> ImageFont.FreeTypeFont:
    f = ImageFont.truetype(BAHN, size)
    f.set_variation_by_name("Bold Condensed")
    return f


def sym(size: int) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(SYM, size)


# ---------------------------------------------------------------- glyphs (white, flat, card style)
def _starburst(d, cx, cy, r, fill):
    pts = []
    for i in range(24):
        a = math.radians(i * 15 - 90)
        rr = r if i % 2 == 0 else r * 0.48
        pts.append((cx + rr * math.cos(a), cy + rr * math.sin(a)))
    d.polygon(pts, fill=fill)


def _shield(d, cx, cy, r, fill):
    w, h = r * 1.5, r * 1.8
    pts = [(cx - w / 2, cy - h / 2), (cx + w / 2, cy - h / 2), (cx + w / 2, cy + h * 0.05),
           (cx, cy + h / 2), (cx - w / 2, cy + h * 0.05)]
    d.polygon(pts, fill=fill)


def _lightning(d, cx, cy, r, fill):
    pts = [(cx + r * 0.25, cy - r), (cx - r * 0.55, cy + r * 0.12), (cx - r * 0.02, cy + r * 0.12),
           (cx - r * 0.3, cy + r), (cx + r * 0.6, cy - r * 0.2), (cx + r * 0.05, cy - r * 0.2)]
    d.polygon(pts, fill=fill)


def _x(d, cx, cy, r, fill):
    w = r * 0.42
    for s in (1, -1):
        d.line([(cx - r * 0.75, cy - s * r * 0.75), (cx + r * 0.75, cy + s * r * 0.75)], fill=fill, width=int(w))


def _excl(d, cx, cy, r, fill):
    d.rounded_rectangle((cx - r * 0.2, cy - r * 0.95, cx + r * 0.2, cy + r * 0.35), radius=r * 0.12, fill=fill)
    d.ellipse((cx - r * 0.22, cy + r * 0.55, cx + r * 0.22, cy + r * 0.98), fill=fill)


def _sym(ch):
    def draw(d, cx, cy, r, fill):
        f = sym(int(r * 1.7))
        d.text((cx, cy), ch, font=f, fill=fill, anchor="mm")
    return draw


def _chevrons(d, cx, cy, r, fill):
    w = r * 0.32
    for dx in (-0.35, 0.3):
        x = cx + dx * r
        d.line([(x - r * 0.35, cy - r * 0.6), (x + r * 0.2, cy), (x - r * 0.35, cy + r * 0.6)], fill=fill, width=int(w), joint="curve")


GLYPH = {
    "attack": _starburst, "defense": _shield, "scheme": _lightning, "x": _x, "excl": _excl, "chevrons": _chevrons,
    "lock": _sym("\U0001F512"), "hourglass": _sym("\u231B"), "pin": _sym("\U0001F4CD"), "star": _sym("\u2605"),
    "eye": _sym("\U0001F441"), "chain": _sym("\u26D3"),
}


# ---------------------------------------------------------------- icon shapes
def type_block(size: int, glyph: str, color=NAVY, glyph_color=WHITE, rim=CREAM) -> Image.Image:
    """Square flat block like the card's type block, cream rim like the card border."""
    im = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    rim_w = max(2, size // 14)
    d.rounded_rectangle((0, 0, size - 1, size - 1), radius=size * 0.14, fill=rim)
    d.rounded_rectangle((rim_w, rim_w, size - 1 - rim_w, size - 1 - rim_w), radius=size * 0.1, fill=color)
    GLYPH[glyph](d, size / 2, size / 2, size * 0.34, glyph_color)
    return im


def pennant(width: int, number: str, top=P1S, body=NAVY, text=WHITE) -> Image.Image:
    """Order badge = the card's left banner: colour block on top, navy ribbon with the numeral, notch at the bottom."""
    h = int(width * 1.55)
    im = Image.new("RGBA", (width + 4, h + 4), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    notch = width * 0.28
    outline = [(0, 0), (width + 3, 0), (width + 3, h + 3), (width / 2 + 1.5, h + 3 - notch), (0, h + 3)]
    d.polygon(outline, fill=CREAM)
    inner = [(2, 2), (width + 1, 2), (width + 1, h + 1 - 1), (width / 2 + 1.5, h + 1 - notch), (2, h)]
    d.polygon(inner, fill=body)
    d.rectangle((2, 2, width + 1, 2 + width * 0.42), fill=top)
    d.text((width / 2 + 2, 2 + width * 0.42 + (h - notch - width * 0.42) / 2), number, font=bahn(int(width * 0.78)), fill=text, anchor="mm")
    return im


def boost_token(diam: int, text: str) -> Image.Image:
    """BOOST disc exactly like the card: white disc, thick navy ring, bold navy numeral."""
    im = Image.new("RGBA", (diam, diam), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    ring = max(3, diam // 9)
    d.ellipse((0, 0, diam - 1, diam - 1), fill=CREAM)
    d.ellipse((2, 2, diam - 3, diam - 3), fill=NAVY)
    d.ellipse((2 + ring, 2 + ring, diam - 3 - ring, diam - 3 - ring), fill=WHITE)
    d.text((diam / 2, diam / 2 + 1), text, font=bahn(int(diam * (0.58 if len(text) < 3 else 0.48))), fill=NAVY, anchor="mm")
    return im


def plate(text: str, height: int, glyph: str | None = None, glyph_color=WHITE, glyph_bg=None, fg=CREAM) -> Image.Image:
    """Navy title-bar plate with condensed caps text and an optional leading type block."""
    f = bahn(int(height * 0.62))
    tmp = ImageDraw.Draw(Image.new("RGBA", (1, 1)))
    tb = tmp.textbbox((0, 0), text, font=f)
    tw = tb[2] - tb[0]
    gw = height if glyph else 0
    w = int(tw + height * 0.7 + gw)
    im = Image.new("RGBA", (w + 4, height + 4), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    d.rounded_rectangle((0, 0, w + 3, height + 3), radius=height * 0.18, fill=CREAM)
    d.rounded_rectangle((2, 2, w + 1, height + 1), radius=height * 0.14, fill=NAVY)
    if glyph:
        d.rounded_rectangle((2, 2, 2 + gw, height + 1), radius=height * 0.14, fill=glyph_bg or NAVY_2)
        GLYPH[glyph](d, 2 + gw / 2, 2 + height / 2, height * 0.32, glyph_color)
    d.text((2 + gw + (w - gw) / 2, 2 + height / 2), text, font=f, fill=fg, anchor="mm")
    return im


def zone_disc(diam: int, color_hex: str) -> Image.Image:
    im = Image.new("RGBA", (diam, diam), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    h = color_hex.lstrip("#")
    c = (int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16), 255)
    d.ellipse((0, 0, diam - 1, diam - 1), fill=CREAM)
    d.ellipse((2, 2, diam - 3, diam - 3), fill=NAVY)
    r = max(3, diam // 7)
    d.ellipse((2 + r, 2 + r, diam - 3 - r, diam - 3 - r), fill=c)
    return im


# semantic icons used by the mockups (03 4.2 glyph column)
def icon(name: str, size: int, number: str | None = None) -> Image.Image:
    if name == "boost":            # V-02 / V-04b chip "+N"
        return boost_token(size, number or "")
    if name == "order":            # V-04 order badge
        return pennant(size, number or "1")
    if name == "order-p2":
        return pennant(size, number or "1", top=P2S)
    if name == "refuse":           # V-08
        return type_block(size, "x", color=ERR)
    if name == "conflict":         # V-09
        return pennant(size, "!", top=ERR, body=ERR)
    if name == "enemy":            # V-07 lock
        return type_block(size, "lock")
    if name == "ally":             # V-06 pass through
        return type_block(size, "chevrons")
    if name == "sent":             # V-10
        return type_block(size, "hourglass")
    if name == "pending-move":     # V-11 (effect of a card -> scheme lightning on the pending violet)
        return type_block(size, "scheme", color=PEND)
    if name == "pending-place":    # V-12
        return type_block(size, "pin", color=PEND)
    if name == "hint":             # V-13
        return type_block(size, "star", glyph_color=(255, 200, 87, 255))
    if name == "threat":           # V-16
        return plate(number or "", size, glyph="eye", glyph_color=P2S)
    if name == "immobilized":
        return type_block(size, "chain")
    if name == "attack-from":      # MS-R-14: card attack starburst, white on navy (red stays reserved for errors)
        return plate(number or "", size, glyph="attack")
    raise KeyError(name)
