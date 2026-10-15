"""Mockup of the turn stage strip (HUD v2 tokens, HUD v3 icons) over a real 1920x1080 game frame."""
import sys
from PIL import Image, ImageDraw, ImageFont, ImageOps, ImageFilter

REPO = sys.argv[1]
OUT = sys.argv[2]
ICONS = REPO + "/art/imagegen/hud-icons-v3/sizes/"
ROBOTO = "C:/Program Files/Epic Games/UE_5.8/Engine/Content/Slate/Fonts/Roboto-BoldCondensed.ttf"
ROBOTO_R = "C:/Program Files/Epic Games/UE_5.8/Engine/Content/Slate/Fonts/Roboto-Regular.ttf"
DISPLAY = REPO + "/unreal/Unmatched/Content/UM/Fonts/TTF/Philosopher-Bold.ttf"

NAVY = (11, 22, 38, 236)
GOLD = (201, 164, 90, 255)
GOLD_HI = (246, 206, 110, 255)
GREY = (120, 132, 150, 255)
P2 = (143, 180, 217, 255)
TEXT = (236, 236, 242, 255)
TEXT2 = (170, 178, 196, 255)


def icon(name, px):
    return Image.open(f"{ICONS}{name}-64.png").convert("RGBA").resize((px, px), Image.LANCZOS)


def faded(im, alpha, grey=True):
    if grey:
        g = ImageOps.grayscale(im.convert("RGB")).convert("RGBA")
        g.putalpha(im.getchannel("A"))
        im = g
    a = im.getchannel("A").point(lambda v: int(v * alpha))
    im = im.copy()
    im.putalpha(a)
    return im


def node(layer, d, cx, cy, name, state, size, rim=GOLD):
    """state: done | current | next | skip"""
    r = size // 2
    if state == "current":
        glow = Image.new("RGBA", layer.size, (0, 0, 0, 0))
        gd = ImageDraw.Draw(glow)
        gd.ellipse((cx - r - 9, cy - r - 9, cx + r + 9, cy + r + 9), fill=rim[:3] + (110,))
        layer.alpha_composite(glow.filter(ImageFilter.GaussianBlur(6)))
        d.ellipse((cx - r - 5, cy - r - 5, cx + r + 5, cy + r + 5), outline=GOLD_HI if rim == GOLD else rim, width=3)
    ic = icon(name, size)
    if state == "next":
        ic = faded(ic, 0.55)
        d.ellipse((cx - r - 3, cy - r - 3, cx + r + 3, cy + r + 3), outline=GREY, width=1)
    elif state == "skip":
        ic = faded(ic, 0.3)
    layer.alpha_composite(ic, (cx - r, cy - r))
    if state == "skip":
        d.line((cx - r + 4, cy + r - 4, cx + r - 4, cy - r + 4), fill=(170, 178, 196, 200), width=3)
    if state == "done":
        b = 15
        bx, by = cx + r - 7, cy + r - 7
        d.ellipse((bx - b // 2 - 1, by - b // 2 - 1, bx + b // 2 + 1, by + b // 2 + 1), fill=(11, 22, 38, 255))
        layer.alpha_composite(icon("ui-check", b), (bx - b // 2, by - b // 2))


def strip(base, title, nodes, sub, caption, rim=GOLD, x0=24, y0=76):
    """nodes: list of (icon, state); sub: (index of the expanded node, [(icon, state)...]) or None"""
    layer = Image.new("RGBA", base.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    f_t = ImageFont.truetype(DISPLAY, 17)
    f_c = ImageFont.truetype(ROBOTO, 16)
    big, small, gap, sgap = 38, 26, 22, 12
    xs, x = [], x0 + 18
    for i, _ in enumerate(nodes):
        xs.append(x + big // 2)
        x += big + gap
        if sub and sub[0] == i:
            x += len(sub[1]) * (small + sgap) + 8
    w = x - gap + 18 - x0
    w = max(w, 252, int(d.textlength(caption, font=f_c)) + 28)
    h = 104
    d.rounded_rectangle((x0, y0, x0 + w, y0 + h), radius=8, fill=NAVY, outline=rim, width=2)
    d.text((x0 + 12, y0 + 6), title, font=f_t, fill=rim if rim != GOLD else GOLD_HI)
    cy = y0 + 54
    # connectors
    for i in range(len(nodes) - 1):
        a = xs[i] + big // 2 + 4
        b = xs[i + 1] - big // 2 - 4
        col = GOLD if nodes[i][1] == "done" else GREY
        d.line((a, cy, b, cy), fill=col, width=2)
    for i, (name, st) in enumerate(nodes):
        node(layer, d, xs[i], cy, name, st, big, rim)
        if sub and sub[0] == i:
            sx = xs[i] + big // 2 + 12
            bx0 = sx - 6
            for j, (sn, ss) in enumerate(sub[1]):
                scx = sx + small // 2
                if j:
                    d.line((scx - small - sgap + small // 2 + 2, cy, scx - small // 2 - 3, cy),
                           fill=GOLD if sub[1][j - 1][1] == "done" else GREY, width=2)
                node(layer, d, scx, cy, sn, ss, small, rim)
                sx += small + sgap
            d.rounded_rectangle((bx0, cy - small // 2 - 9, sx - sgap + 6, cy + small // 2 + 9), radius=6,
                                outline=(201, 164, 90, 140), width=1)
    d.text((x0 + 12, y0 + h - 24), caption, font=f_c, fill=TEXT2)
    base.alpha_composite(layer)
    return (x0, y0, x0 + w, y0 + h)


def main():
    frame = Image.open(sys.argv[3]).convert("RGBA")
    S = [
        ("A", "ВАШ ХОД", [("resource-action-empty", "current"), ("resource-action-empty", "next"),
                                  ("card-drop", "skip"), ("action-end-turn", "next")], None,
         "Действие 1 из 2 — на выбор", GOLD),
        ("B", "ВАШ ХОД", [("action-maneuver", "done"), ("action-attack", "current"),
                                  ("card-drop", "skip"), ("action-end-turn", "next")],
         (1, [("action-attack", "done"), ("action-defense", "current"), ("badge-conflict", "next"), ("ui-check", "next")]),
         "Атака: защита соперника", GOLD),
        ("C", "ХОД СОПЕРНИКА", [("action-scheme", "done"), ("action-attack", "current"),
                                        ("card-drop", "skip"), ("action-end-turn", "next")],
         (1, [("action-attack", "done"), ("action-defense", "current"), ("badge-conflict", "next"), ("ui-check", "next")]),
         "Атака соперника: ваша защита", P2),
        ("D", "ВАШ ХОД", [("action-maneuver", "done"), ("action-scheme", "done"),
                                  ("card-drop", "current"), ("action-end-turn", "next")], None,
         "Сброс до 7 карт", GOLD),
        ("E", "ВАШ ХОД", [("action-maneuver", "current"), ("resource-action-empty", "next"),
                                  ("card-drop", "skip"), ("action-end-turn", "next")],
         (0, [("resource-card", "done"), ("ui-step", "current")]),
         "Манёвр: движение", GOLD),
    ]
    crops = []
    for key, title, nodes, sub, cap, rim in S:
        img = frame.copy()
        box = strip(img, title, nodes, sub, cap, rim)
        img.convert("RGB").save(f"{OUT}/strip-{key}.png")
        c = img.crop((0, 0, max(box[2] + 40, 640), box[3] + 24))
        crops.append((key, c.resize((c.width * 2, c.height * 2), Image.LANCZOS)))
    W = max(c.width for _, c in crops)
    sheet = Image.new("RGBA", (W, sum(c.height + 8 for _, c in crops)), (18, 18, 22, 255))
    y = 0
    for _, c in crops:
        sheet.alpha_composite(c, (0, y))
        y += c.height + 8
    sheet.convert("RGB").save(f"{OUT}/strip-sheet.png")


main()
