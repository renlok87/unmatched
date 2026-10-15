"""Build comparison sheets from rendered mockups: SHEET-states, SHEET-before-after, SHEET-materials, SHEET-fonts."""
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

HERE = Path(__file__).resolve().parent
FONT = ImageFont.truetype("C:/Windows/Fonts/arialbd.ttf", 26)
FONT2 = ImageFont.truetype("C:/Windows/Fonts/arialbd.ttf", 30)
BG = (14, 14, 18)
INK = (240, 235, 220)


def img(name):
    return Image.open(HERE / name).convert("RGB")


def grid(cells, cols, path, w=960, h=540):
    rows = (len(cells) + cols - 1) // cols
    out = Image.new("RGB", (cols * w + (cols - 1) * 10, rows * (h + 44)), BG)
    d = ImageDraw.Draw(out)
    for i, (p, t) in enumerate(cells):
        x, y = (i % cols) * (w + 10), (i // cols) * (h + 44)
        d.text((x + 8, y + 8), t, fill=INK, font=FONT)
        out.paste(img(p).resize((w, h)), (x, y + 44))
    out.save(HERE / path, quality=86)


def main():
    grid([("../frames/A0-current-1080p.jpg", "СЕЙЧАС · начало хода (живой клиент)"),
          ("A1-table-turn-start.jpg", "A1 · действие 1 из 2"),
          ("A2-table-attack-target.jpg", "A2 · атака: боец → карта → цель"),
          ("A3-table-combat-reveal.jpg", "A3 · бой 3 : 1 в центре, рука видна"),
          ("A4-table-defense.jpg", "A4 · защита: дуга дальнего боя, таймер"),
          ("A5-table-discard.jpg", "A5 · сброс до 7 (9 карт)"),
          ("A1b-table-hover-preview.jpg", "A1b · превью карты сбоку от руки, не над полем"),
          ("B1-table-ability-skip.jpg", "B1 · способность без цели: авто-пропуск с причиной"),
          ("B2-table-opponent-scheme.jpg", "B2 · схема соперника в слоте активной карты"),
          ("B3-table-parked-combat-choice.jpg", "B3 · бой «припаркован», выбор клетки после боя")], 2, "SHEET-states.jpg")
    grid([("C1-720p-turn-start.jpg", "1280×720 (класс S)"), ("C2-ui150-turn-start.jpg", "1920×1080, UI 150 % (класс S)"),
          ("C3-ui150-defense.jpg", "UI 150 % · защита"), ("A6-sarpedon-turn-start.jpg", "Sarpedon · 1920×1080")], 2,
         "SHEET-resolutions.jpg")
    grid([("../frames/A0-current-1080p.jpg", "БЫЛО"),
          ("A1-table-turn-start.jpg", "СТАЛО (концепт v2, M2 + Cormorant SC)")], 2, "SHEET-before-after.jpg")
    grid([("A1-table-turn-start.jpg", "Marmoreal"), ("A6-sarpedon-turn-start.jpg", "Sarpedon")], 2,
         "SHEET-boards.jpg")

    items = [("M1-light-stock.jpg", "M1 · светлый печатный картон"),
             ("M2-dark-stock.jpg", "M2 · тёмный картон + золотая нить (рекомендация)"),
             ("M3-marble-bronze.jpg", "M3 · мрамор и бронза")]
    out = Image.new("RGB", (1920, 3 * (330 + 48)), (18, 18, 22))
    d = ImageDraw.Draw(out)
    y = 0
    for n, t in items:
        im = img(n)
        d.text((16, y + 8), t, fill=INK, font=FONT2)
        y += 48
        out.paste(im.crop((0, 800, 960, 1080)).resize((960, 280)), (0, y))
        out.paste(im.crop((1460, 0, 1920, 200)).resize((460, 200)), (970, y))
        out.paste(im.crop((1380, 760, 1920, 1080)).resize((405, 240)), (1440, y))
        y += 330
    out.crop((0, 0, 1920, y)).save(HERE / "SHEET-materials.jpg", quality=88)

    items = [("T1-plates-r3-canon.jpg", "T1 · канон коробки: кремовая кромка + меандр (ImageGen)"),
             ("T2-plates-m2.jpg", "T2 · тёмный картон + золотая нить (ImageGen)"),
             ("T3-plates-m3.jpg", "T3 · мрамор + бронза (ImageGen)")]
    out = Image.new("RGB", (1920, 3 * (330 + 48)), (18, 18, 22))
    d = ImageDraw.Draw(out)
    y = 0
    for n, t in items:
        im = img(n)
        d.text((16, y + 8), t, fill=INK, font=FONT2)
        y += 48
        out.paste(im.crop((0, 800, 960, 1080)).resize((960, 280)), (0, y))
        out.paste(im.crop((1460, 0, 1920, 200)).resize((460, 200)), (970, y))
        out.paste(im.crop((1380, 760, 1920, 1080)).resize((405, 240)), (1440, y))
        y += 330
    out.crop((0, 0, 1920, y)).save(HERE / "SHEET-materials-real.jpg", quality=88)

    fs = [("F0-philosopher.jpg", "Philosopher Bold (сейчас)"), ("F1-cormorant.jpg", "Cormorant SC Bold"),
          ("F2-forum.jpg", "Forum, капс + трекинг")]
    out = Image.new("RGB", (3 * 640, 300), (18, 18, 22))
    d = ImageDraw.Draw(out)
    for i, (n, t) in enumerate(fs):
        out.paste(img(n).crop((0, 860, 620, 1080)), (i * 640, 60))
        d.text((i * 640 + 10, 14), t, fill=INK, font=FONT2)
    out.save(HERE / "SHEET-fonts.jpg", quality=88)
    print("sheets ok")


if __name__ == "__main__":
    main()
