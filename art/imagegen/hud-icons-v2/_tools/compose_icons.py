"""Compose the HUD icon set v2, wave 1 (docs/unreal/contracts/hud/HUD-AND-ICONS.md §3.4).

ImageGen (Codex) draws only the white glyph masks in ../glyphs/ (brief: IMAGEGEN-BRIEF-icons.md). This script
puts every glyph into its card-language shape with the exact token colours of hud-style-tokens.json, adds the
dark outer keyline (rule I-2) and writes 1024 px masters to art/imagegen/hud-icons-v2/<id>.png.
Geometric glyphs (attack starburst, shield, lightning) come from tools/art/move_selection/card_icons.py.

  python art/imagegen/hud-icons-v2/_tools/compose_icons.py [--glyphs DIR] [--out DIR]

Numbers (BOOST "+N", order, threat count, hint rank) are not baked: the game draws them as text (HUD-AND-ICONS §1.3).
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import sys
from pathlib import Path

from PIL import Image, ImageChops, ImageDraw

ROOT = Path(__file__).resolve().parents[4]
HERE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools/art/move_selection"))
import card_icons as CI  # noqa: E402

TOK = json.loads((ROOT / "docs/unreal/contracts/hud/hud-style-tokens.json").read_text(encoding="utf-8"))["colors"]


def rgba(name, a=255):
    h = TOK[name]["hex"].lstrip("#")
    return (int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16), a)


NAVY, NAVY2, CREAM, GLYPH = rgba("card.navy"), rgba("card.navy.2"), rgba("card.cream"), rgba("card.glyph")
KEY, ERR, PEND = rgba("mark.keyline"), rgba("state.error"), rgba("zone.purple")
TOKEN_BODY, TOKEN_RIM = rgba("icon.token.body"), rgba("icon.token.rim")
S = 1024          # master size
SS = 2            # supersampling
K = 26            # outer keyline (mark.keyline), px at 1024
RIM = 64          # cream rim, px at 1024 (>= 2 px at 32 px)


# ------------------------------------------------------------------ helpers
def canvas(w=S, h=S):
    return Image.new("RGBA", (w * SS, h * SS), (0, 0, 0, 0))


def done(im):
    return im.resize((im.width // SS, im.height // SS), Image.LANCZOS)


def load_mask(path: Path) -> Image.Image:
    """White glyph on transparent (alpha) or on flat black (luminance) -> L mask trimmed to its bbox."""
    im = Image.open(path).convert("RGBA")
    a = im.getchannel("A")
    if a.getextrema()[0] >= 250:            # no real alpha: use luminance
        a = im.convert("L").point(lambda v: 0 if v < 60 else min(255, int((v - 60) * 255 / 160)))
    else:                                   # alpha, but keep only light pixels
        lum = im.convert("L").point(lambda v: 0 if v < 110 else 255)
        a = ImageChops.multiply(a, lum)
    bb = a.getbbox()
    return a.crop(bb) if bb else a


def paste_mask(im, mask, box, color):
    """Fit mask into box (x0,y0,x1,y1) keeping aspect, paint it with color."""
    x0, y0, x1, y1 = (int(v * SS) for v in box)
    bw, bh = x1 - x0, y1 - y0
    k = min(bw / mask.width, bh / mask.height)
    m = mask.resize((max(1, int(mask.width * k)), max(1, int(mask.height * k))), Image.LANCZOS)
    layer = Image.new("RGBA", m.size, color)
    im.paste(layer, (x0 + (bw - m.width) // 2, y0 + (bh - m.height) // 2), m)


def poly_mask(fn, size=1024):
    """Render a card_icons polygon glyph (white) into an L mask."""
    m = Image.new("L", (size, size), 0)
    fn(ImageDraw.Draw(m), size / 2, size / 2, size * 0.48, 255)
    bb = m.getbbox()
    return m.crop(bb)


def block(body, glyph_mask, glyph_frac=0.56, keyline=True, glyph_color=GLYPH):
    """Card type block: dark keyline, cream rim, flat body, flat white glyph."""
    im = canvas()
    d = ImageDraw.Draw(im)
    k = K if keyline else 0
    d.rounded_rectangle((0, 0, S * SS - 1, S * SS - 1), radius=0.17 * S * SS, fill=KEY if keyline else CREAM)
    d.rounded_rectangle((k * SS, k * SS, (S - k) * SS - 1, (S - k) * SS - 1), radius=0.15 * S * SS, fill=CREAM)
    r = k + RIM
    d.rounded_rectangle((r * SS, r * SS, (S - r) * SS - 1, (S - r) * SS - 1), radius=0.11 * S * SS, fill=body)
    g = S * glyph_frac
    paste_mask(im, glyph_mask, ((S - g) / 2, (S - g) / 2, (S + g) / 2, (S + g) / 2), glyph_color)
    return done(im)


def title_plate(glyph_mask, w=2 * S, h=S):
    """Title plate (shape.title_plate): glyph slot card.navy.2 on the left, empty navy text field on the right."""
    im = canvas(w, h)
    d = ImageDraw.Draw(im)
    d.rounded_rectangle((0, 0, w * SS - 1, h * SS - 1), radius=0.2 * h * SS, fill=KEY)
    d.rounded_rectangle((K * SS, K * SS, (w - K) * SS - 1, (h - K) * SS - 1), radius=0.18 * h * SS, fill=CREAM)
    r = K + RIM
    d.rounded_rectangle((r * SS, r * SS, (w - r) * SS - 1, (h - r) * SS - 1), radius=0.12 * h * SS, fill=NAVY)
    d.rounded_rectangle((r * SS, r * SS, (h - r // 2) * SS - 1, (h - r) * SS - 1), radius=0.12 * h * SS, fill=NAVY2)
    g = h * 0.58
    paste_mask(im, glyph_mask, ((h - g) / 2, (h - g) / 2, (h + g) / 2, (h + g) / 2), GLYPH)
    return done(im)


def boost_disc():
    """shape.boost_disc: navy disc, thin white ring at the edge, no digit (the game draws "+N")."""
    im = canvas()
    d = ImageDraw.Draw(im)
    d.ellipse((0, 0, S * SS - 1, S * SS - 1), fill=KEY)
    ring = S / 16 * 1.4                       # d/16 on the card; x1.4 keeps it >= 1 px at 24 px
    d.ellipse((K * SS, K * SS, (S - K) * SS - 1, (S - K) * SS - 1), fill=GLYPH)
    i = K + ring
    d.ellipse((i * SS, i * SS, (S - i) * SS - 1, (S - i) * SS - 1), fill=NAVY)
    return done(im)


def disc_base(d):
    d.ellipse((0, 0, S * SS - 1, S * SS - 1), fill=KEY)
    d.ellipse((K * SS, K * SS, (S - K) * SS - 1, (S - K) * SS - 1), fill=CREAM)
    r = K + RIM
    d.ellipse((r * SS, r * SS, (S - r) * SS - 1, (S - r) * SS - 1), fill=NAVY)


def signal(d, cx, cy, scale, color, arcs=3):
    """Dot + concentric arcs (signal), drawn upward from (cx, cy)."""
    w = int(0.075 * S * scale * SS)
    rd = 0.07 * S * scale
    d.ellipse(((cx - rd) * SS, (cy - rd) * SS, (cx + rd) * SS, (cy + rd) * SS), fill=color)
    for i in range(1, arcs + 1):
        R = (0.12 + 0.13 * i) * S * scale
        d.arc(((cx - R) * SS, (cy - R) * SS, (cx + R) * SS, (cy + R) * SS), 225, 315, fill=color, width=w)


def heart_poly(cx, cy, r):
    pts = []
    for i in range(240):
        t = 2 * math.pi * i / 240
        x = 16 * math.sin(t) ** 3
        y = 13 * math.cos(t) - 5 * math.cos(2 * t) - 2 * math.cos(3 * t) - math.cos(4 * t)
        pts.append(((cx + x * r / 17) * SS, (cy - y * r / 17) * SS))
    return pts


def heater_shield(d, cx, cy, r, fill):
    """Defense glyph like the card: flat top, straight upper sides, curved sides meeting in a bottom point."""
    w, h = r * 1.55, r * 1.9
    top, mid, bot = cy - h / 2, cy - h / 2 + h * 0.42, cy + h / 2
    right = []
    for i in range(41):
        t = i / 40
        x = cx + (w / 2) * (1 - t ** 1.6)
        y = mid + (bot - mid) * t
        right.append((x, y))
    pts = [(cx - w / 2, top), (cx + w / 2, top)] + right + [(2 * cx - x, y) for x, y in reversed(right)]
    d.polygon(pts, fill=fill)


def diamond_poly(cx, cy, r):
    return [((cx) * SS, (cy - r) * SS), ((cx + r) * SS, cy * SS), (cx * SS, (cy + r) * SS), ((cx - r) * SS, cy * SS)]


# ------------------------------------------------------------------ icons
def build(glyphs: Path):
    g = {p.stem: load_mask(p) for p in sorted(glyphs.glob("glyph-*.png"))}
    need = ["glyph-lock", "glyph-hourglass", "glyph-map-pin", "glyph-move-arrows", "glyph-lightbulb", "glyph-eye",
            "glyph-chain", "glyph-footprint", "glyph-circular-arrow"]
    missing = [n for n in need if n not in g]
    star, shield, bolt = poly_mask(CI._starburst), poly_mask(heater_shield), poly_mask(CI._lightning)
    out = {}
    out["state-boost"] = boost_disc()
    for iid, gl, body in (("state-enemy", "glyph-lock", NAVY), ("state-sent", "glyph-hourglass", NAVY),
                          ("state-pending-move", "glyph-move-arrows", PEND), ("state-pending-place", "glyph-map-pin", PEND),
                          ("state-immobilized", "glyph-chain", NAVY), ("action-maneuver", "glyph-footprint", NAVY)):
        if gl in g:
            out[iid] = block(body, g[gl])
    for iid, gl in (("state-hint", "glyph-lightbulb"), ("state-threat", "glyph-eye")):
        if gl in g:
            out[iid] = title_plate(g[gl])
    out["action-attack"] = block(NAVY, star, 0.62)
    out["action-defense"] = block(NAVY, shield, 0.56)
    out["action-scheme"] = block(NAVY, bolt, 0.58)
    # attack token (D-5 geometry: token body, 1 px rim at 48 px ~= 2 %, no keyline) + its glyph mask
    im = canvas()
    d = ImageDraw.Draw(im)
    d.rounded_rectangle((0, 0, S * SS - 1, S * SS - 1), radius=0.18 * S * SS, fill=TOKEN_RIM)
    t = 0.03 * S
    d.rounded_rectangle((t * SS, t * SS, (S - t) * SS - 1, (S - t) * SS - 1), radius=0.16 * S * SS, fill=TOKEN_BODY)
    paste_mask(im, star, (0.2 * S, 0.2 * S, 0.8 * S, 0.8 * S), GLYPH)
    out["action-attack-token"] = done(im)
    im = canvas()
    paste_mask(im, star, (0.2 * S, 0.2 * S, 0.8 * S, 0.8 * S), (255, 255, 255, 255))
    out["action-attack-token-glyphmask"] = done(im)
    # marker-status: hero ribbon, white top block (tinted in game), navy body, notch
    im = canvas()
    d = ImageDraw.Draw(im)
    w = S / 1.55
    x0, x1 = (S - w) / 2, (S + w) / 2
    notch = w * 0.28

    def ribbon(inset, fill):
        pts = [(x0 + inset, inset), (x1 - inset, inset), (x1 - inset, S - inset), (S / 2, S - notch - inset * 0.6),
               (x0 + inset, S - inset)]
        d.polygon([(x * SS, y * SS) for x, y in pts], fill=fill)
    ribbon(0, KEY)
    ribbon(K, CREAM)
    ribbon(K + RIM * 0.7, NAVY)
    i = K + RIM * 0.7
    d.rectangle(((x0 + i) * SS, i * SS, (x1 - i) * SS, (i + w * 0.42) * SS), fill=GLYPH)
    out["marker-status"] = done(im)
    # loader spinner: navy disc, white three-quarter arc
    im = canvas()
    d = ImageDraw.Draw(im)
    disc_base(d)
    R = S * 0.30
    d.arc(((S / 2 - R) * SS, (S / 2 - R) * SS, (S / 2 + R) * SS, (S / 2 + R) * SS), -90, 180, fill=GLYPH,
          width=int(0.1 * S * SS))
    out["loader-spinner"] = done(im)
    # action pips (diamond = action on the HUD)
    for iid, full in (("resource-action-full", True), ("resource-action-empty", False)):
        im = canvas()
        d = ImageDraw.Draw(im)
        c, r = S / 2, S / 2
        d.polygon(diamond_poly(c, c, r), fill=KEY)
        d.polygon(diamond_poly(c, c, r - K * 1.4), fill=NAVY if full else CREAM)
        d.polygon(diamond_poly(c, c, r - K * 1.4 - 0.08 * S), fill=CREAM if full else NAVY)
        out[iid] = done(im)
    # mini card (no art, no text, no logo)
    im = canvas()
    d = ImageDraw.Draw(im)
    cw = S * 5 / 7
    x0 = (S - cw) / 2
    d.rounded_rectangle((x0 * SS, 0, (x0 + cw) * SS - 1, S * SS - 1), radius=0.08 * S * SS, fill=KEY)
    d.rounded_rectangle(((x0 + K) * SS, K * SS, (x0 + cw - K) * SS - 1, (S - K) * SS - 1), radius=0.07 * S * SS, fill=CREAM)
    r = K + RIM
    d.rounded_rectangle(((x0 + r) * SS, r * SS, (x0 + cw - r) * SS - 1, (S - r) * SS - 1), radius=0.05 * S * SS, fill=NAVY)
    q = r + 0.07 * S
    d.rounded_rectangle(((x0 + q) * SS, q * SS, (x0 + cw - q) * SS - 1, (S - q) * SS - 1), radius=0.03 * S * SS,
                        outline=CREAM, width=int(0.022 * S * SS))
    out["resource-card"] = done(im)
    # connection: signal arcs on a navy disc
    im = canvas()
    d = ImageDraw.Draw(im)
    disc_base(d)
    signal(d, S / 2, S * 0.66, 1.0, GLYPH)
    out["resource-connection-online"] = done(im)
    if "glyph-circular-arrow" in g:
        im = canvas()
        d = ImageDraw.Draw(im)
        disc_base(d)
        paste_mask(im, g["glyph-circular-arrow"], (0.2 * S, 0.2 * S, 0.8 * S, 0.8 * S), GLYPH)
        d = ImageDraw.Draw(im)
        signal(d, S / 2, S * 0.58, 0.42, GLYPH, arcs=1)
        out["resource-connection-reconnecting"] = done(im)
    im = canvas()
    d = ImageDraw.Draw(im)
    disc_base(d)
    signal(d, S * 0.46, S * 0.62, 0.9, (150, 146, 140, 255), arcs=2)
    b0, b1 = S * 0.52, S * 0.98
    d.rounded_rectangle((b0 * SS, b0 * SS, b1 * SS, b1 * SS), radius=0.08 * S * SS, fill=KEY)
    d.rounded_rectangle(((b0 + K) * SS, (b0 + K) * SS, (b1 - K) * SS, (b1 - K) * SS), radius=0.07 * S * SS, fill=ERR)
    CI._x(d, (b0 + b1) / 2 * SS, (b0 + b1) / 2 * SS, (b1 - b0) * 0.3 * SS, GLYPH)
    out["resource-connection-lost"] = done(im)
    # HP hearts
    for iid, full in (("resource-hp-full", True), ("resource-hp-empty", False)):
        im = canvas()
        d = ImageDraw.Draw(im)
        c = S / 2
        d.polygon(heart_poly(c, c + 0.02 * S, S * 0.5), fill=KEY)
        d.polygon(heart_poly(c, c + 0.02 * S, S * 0.5 - K * 1.3), fill=NAVY if full else CREAM)
        d.polygon(heart_poly(c, c + 0.02 * S, S * 0.5 - K * 1.3 - 0.07 * S), fill=CREAM if full else NAVY)
        out[iid] = done(im)
    return out, missing


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--glyphs", type=Path, default=HERE / "glyphs")
    ap.add_argument("--out", type=Path, default=HERE)
    a = ap.parse_args(argv)
    icons, missing = build(a.glyphs)
    a.out.mkdir(parents=True, exist_ok=True)
    rows = []
    for iid, im in sorted(icons.items()):
        p = a.out / f"{iid}.png"
        im.save(p, optimize=True)
        rows.append({"id": iid, "file": p.name, "width": im.width, "height": im.height,
                     "sha256": hashlib.sha256(p.read_bytes()).hexdigest()})
    print(json.dumps({"written": len(rows), "missing_glyphs": missing}, ensure_ascii=False))
    return rows, missing


if __name__ == "__main__":
    main()
