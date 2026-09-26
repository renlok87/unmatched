from pathlib import Path
import textwrap

from PIL import Image, ImageDraw, ImageFont


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "public" / "assets" / "decks" / "deadpool"
OUT = SRC / "ru"
FONT_DIR = Path("C:/Windows/Fonts")


def font(name: str, size: int) -> ImageFont.FreeTypeFont:
    candidates = [
        FONT_DIR / name,
        FONT_DIR / "comic.ttf",
        FONT_DIR / "ARIALUNI.TTF",
        FONT_DIR / "arial.ttf",
    ]
    for candidate in candidates:
        if candidate.exists():
            return ImageFont.truetype(str(candidate), size=size)
    return ImageFont.load_default()


FONT_REGULAR = "comic.ttf"
FONT_BOLD = "comicbd.ttf"
FONT_HAND = "Inkfree.ttf"


def text_size(draw: ImageDraw.ImageDraw, text: str, fnt: ImageFont.FreeTypeFont) -> tuple[int, int]:
    box = draw.textbbox((0, 0), text, font=fnt)
    return box[2] - box[0], box[3] - box[1]


def wrap_for_width(draw: ImageDraw.ImageDraw, text: str, fnt: ImageFont.FreeTypeFont, width: int) -> list[str]:
    lines: list[str] = []
    for paragraph in text.split("\n"):
        words = paragraph.split()
        current = ""
        for word in words:
            candidate = f"{current} {word}".strip()
            if text_size(draw, candidate, fnt)[0] <= width or not current:
                current = candidate
            else:
                lines.append(current)
                current = word
        if current:
            lines.append(current)
    return lines


def fit_font(draw: ImageDraw.ImageDraw, text: str, box: tuple[int, int, int, int], max_size: int, min_size: int = 10,
             font_name: str = FONT_REGULAR) -> tuple[ImageFont.FreeTypeFont, list[str]]:
    x0, y0, x1, y1 = box
    width = x1 - x0
    height = y1 - y0
    for size in range(max_size, min_size - 1, -1):
        fnt = font(font_name, size)
        lines = wrap_for_width(draw, text, fnt, width)
        line_h = text_size(draw, "Йу", fnt)[1] + max(3, size // 7)
        if line_h * len(lines) <= height:
            return fnt, lines
    fnt = font(font_name, min_size)
    return fnt, wrap_for_width(draw, text, fnt, width)


def draw_wrapped(draw: ImageDraw.ImageDraw, text: str, box: tuple[int, int, int, int], *,
                 max_size: int, fill=(20, 20, 20), font_name: str = FONT_REGULAR,
                 align: str = "left", min_size: int = 10) -> None:
    x0, y0, x1, _ = box
    fnt, lines = fit_font(draw, text, box, max_size, min_size, font_name)
    line_h = text_size(draw, "Йу", fnt)[1] + max(3, fnt.size // 7)
    y = y0
    for line in lines:
        line_w = text_size(draw, line, fnt)[0]
        if align == "center":
            x = x0 + ((x1 - x0) - line_w) // 2
        elif align == "right":
            x = x1 - line_w
        else:
            x = x0
        draw.text((x, y), line, font=fnt, fill=fill)
        y += line_h


def draw_rotated_text(base: Image.Image, text: str, xy: tuple[int, int], *,
                      size: int, angle: float, fill=(255, 255, 255),
                      font_name: str = FONT_BOLD, anchor: str = "lt") -> None:
    fnt = font(font_name, size)
    dummy = Image.new("RGBA", (1, 1))
    d = ImageDraw.Draw(dummy)
    w, h = text_size(d, text, fnt)
    layer = Image.new("RGBA", (w + 16, h + 16), (0, 0, 0, 0))
    ld = ImageDraw.Draw(layer)
    ld.text((8, 8), text, font=fnt, fill=fill)
    rotated = layer.rotate(angle, expand=True, resample=Image.Resampling.BICUBIC)
    x, y = xy
    if anchor == "center":
        x -= rotated.width // 2
        y -= rotated.height // 2
    base.alpha_composite(rotated, (x, y))


def patch_card(name: str) -> tuple[Image.Image, ImageDraw.ImageDraw]:
    image = Image.open(SRC / f"{name}.webp").convert("RGBA")
    return image, ImageDraw.Draw(image)


def save(image: Image.Image, name: str) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    image.save(OUT / f"{name}-ru.png", "PNG", optimize=True)


def time_out() -> None:
    image, draw = patch_card("time-out-time-out-time-out")
    draw.rectangle((21, 330, 336, 548), fill=(223, 223, 212, 255))
    draw_wrapped(
        draw,
        "Немедленно: объявите тайм-аут.\nПросмотрите свою колоду и выберите карту, которую можете сыграть. "
        "Сбросьте эту карту и вместо нее сыграйте выбранную.",
        (34, 354, 323, 487),
        max_size=24,
        font_name=FONT_REGULAR,
    )
    draw.polygon([(237, 98), (349, 101), (350, 253), (238, 254)], fill=(235, 229, 198, 226))
    draw_wrapped(
        draw,
        "ТАЙМ-АУТ\nТАЙМ-АУТ\nТАЙМ-АУТ!",
        (242, 116, 346, 244),
        max_size=20,
        font_name=FONT_BOLD,
        fill=(145, 56, 43),
        align="center",
    )
    draw.polygon([(18, 49), (54, 43), (57, 174), (22, 178)], fill=(35, 34, 31, 228))
    draw_rotated_text(image, "ДЕДПУЛ", (36, 116), size=15, angle=270, fill=(225, 57, 44), anchor="center")
    save(image, "time-out-time-out-time-out")


def transit_card() -> None:
    image, draw = patch_card("transit-card")
    draw.rounded_rectangle((18, 340, 238, 548), radius=22, fill=(232, 234, 228, 255), outline=(130, 146, 154), width=3)
    draw_wrapped(
        draw,
        "После боя:\nпереместитесь на любую клетку в вашей зоне.",
        (35, 367, 222, 483),
        max_size=23,
        font_name=FONT_REGULAR,
    )
    draw.rectangle((312, 67, 349, 273), fill=(180, 52, 47, 238))
    draw_rotated_text(image, "ПРОЕЗДНОЙ", (331, 170), size=15, angle=270, fill=(255, 255, 255), anchor="center")
    draw.rectangle((49, 104, 72, 245), fill=(229, 237, 239, 220))
    draw_rotated_text(image, "ЛЬГОТНЫЙ ПРОЕЗД", (60, 176), size=11, angle=270, fill=(40, 44, 47), anchor="center")
    draw.polygon([(17, 75), (55, 71), (55, 174), (18, 181)], fill=(34, 33, 31, 228))
    draw_rotated_text(image, "ДЕДПУЛ", (36, 130), size=14, angle=270, fill=(225, 57, 44), anchor="center")
    save(image, "transit-card")


def underrated_super_heroes() -> None:
    image, draw = patch_card("underrated-super-heroes")
    draw.rectangle((12, 407, 151, 448), fill=(142, 37, 42, 235))
    draw_wrapped(
        draw,
        "НЕДООЦЕНЕННЫЕ\nСУПЕРГЕРОИ",
        (17, 410, 147, 447),
        max_size=17,
        min_size=8,
        font_name=FONT_BOLD,
        fill=(255, 255, 255),
        align="center",
    )
    draw.polygon([(9, 58), (54, 54), (55, 306), (8, 311)], fill=(30, 30, 29, 220))
    draw_rotated_text(image, "ДЕДПУЛ", (31, 190), size=20, angle=270, fill=(244, 244, 244), anchor="center")
    save(image, "underrated-super-heroes")


def wanna_bet() -> None:
    image, draw = patch_card("wanna-bet")
    draw.polygon([(42, 134), (163, 105), (179, 183), (57, 210)], fill=(228, 225, 206, 210))
    draw_rotated_text(image, "СПОРИМ?", (107, 161), size=29, angle=345, fill=(158, 54, 42), font_name=FONT_HAND, anchor="center")
    draw.rectangle((18, 356, 348, 548), fill=(247, 243, 228, 255))
    draw_wrapped(
        draw,
        "После игры: если вы выиграли игру, противник покупает вам напиток. "
        "Если вы проиграли игру, вы покупаете напиток ему.",
        (31, 381, 335, 504),
        max_size=22,
        font_name=FONT_REGULAR,
    )
    draw.polygon([(18, 18), (59, 14), (58, 122), (17, 130)], fill=(179, 61, 48, 220))
    draw_wrapped(draw, "2", (26, 37, 53, 78), max_size=42, font_name=FONT_BOLD, fill=(230, 228, 207), align="center")
    save(image, "wanna-bet")


def xavier_faculty() -> None:
    image, draw = patch_card("xavier-institute-faculty")
    draw.rounded_rectangle((78, 54, 380, 104), radius=6, fill=(118, 43, 39, 242))
    draw_wrapped(
        draw,
        "ПРЕПОДАВАТЕЛЬ",
        (87, 64, 340, 96),
        max_size=24,
        min_size=10,
        font_name=FONT_BOLD,
        fill=(245, 245, 240),
        align="center",
    )
    draw.polygon([(18, 69), (64, 73), (63, 214), (17, 219)], fill=(28, 27, 26, 224))
    draw_rotated_text(image, "ПРОФ. ДЕДПУЛ", (41, 150), size=13, angle=270, fill=(245, 245, 245), anchor="center")
    draw.rounded_rectangle((22, 344, 340, 468), radius=8, fill=(244, 244, 238, 255))
    draw_wrapped(
        draw,
        "Вы можете сыграть эту карту как дальнюю атаку.",
        (44, 376, 316, 448),
        max_size=24,
        font_name=FONT_REGULAR,
        align="center",
    )
    draw.rectangle((22, 466, 382, 548), fill=(238, 238, 232, 255))
    draw_wrapped(
        draw,
        "ПРИ НАХОЖДЕНИИ ВЕРНУТЬ ОХРАНЕ КАМПУСА",
        (45, 473, 330, 493),
        max_size=13,
        font_name=FONT_BOLD,
        fill=(112, 112, 112),
        align="center",
    )
    save(image, "xavier-institute-faculty")


def main() -> None:
    time_out()
    transit_card()
    underrated_super_heroes()
    wanna_bet()
    xavier_faculty()
    print("Generated 5 Deadpool RU card assets")


if __name__ == "__main__":
    main()
