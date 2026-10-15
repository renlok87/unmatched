"""Normalize generated material plates; all inputs/outputs stay beside this script."""
from pathlib import Path
import hashlib
import json

import numpy as np
from PIL import Image, ImageDraw, ImageOps

ROOT = Path(__file__).resolve().parent
SIZES = {
    'hero-card-plate': (840, 368), 'hp-dial': (256, 256),
    'pile-slip': (240, 64), 'question-strip': (1200, 88),
}
FAMILIES = ('R3', 'M2', 'M3')
LANCZOS = Image.Resampling.LANCZOS


def mask(size, radius=None, circle=False):
    scale = 4
    result = Image.new('L', (size[0] * scale, size[1] * scale))
    draw = ImageDraw.Draw(result)
    box = (0, 0, result.width - 1, result.height - 1)
    if circle:
        draw.ellipse(box, fill=255)
    else:
        draw.rounded_rectangle(box, radius=radius * scale, fill=255)
    return result.resize(size, LANCZOS)


def filled_rgb(image):
    """Extend edge colours under alpha before applying exact analytic silhouettes."""
    data = np.array(image.convert('RGBA'))
    for row in data:
        valid = np.where(row[:, 3] > 180)[0]
        if len(valid):
            row[:valid[0], :3] = row[valid[0], :3]
            row[valid[-1] + 1:, :3] = row[valid[-1], :3]
    return Image.fromarray(data[:, :, :3]).convert('RGBA')


def source(family, plate):
    image = Image.open(ROOT / 'raw' / family / f'{plate}.png').convert('RGBA')
    # Alpha threshold excludes cast shadows and isolated generation specks.
    box = image.getchannel('A').point(lambda x: 255 if x > 180 else 0).getbbox()
    if family == 'R3' and plate == 'pile-slip':
        box = (24, 147, 2032, 616)
    return image, box, image.crop(box)


def normalize_card(family, crop):
    if family == 'R3':
        # A 20 px cream stock edge is 2.38% of the 840 px card width.
        # Both the cream stock and dark body are real generated material samples.
        _, _, paper = source('R3', 'pile-slip')
        card = paper.crop((100, 20, paper.width - 100, paper.height - 20))
        card = filled_rgb(card).resize(SIZES['hero-card-plate'], LANCZOS)
        body = filled_rgb(crop.crop((18, 18, crop.width - 18, crop.height - 18)))
        card.paste(body.resize((800, 328), LANCZOS), (20, 20), mask((800, 328), 3))
    else:
        card = filled_rgb(crop).resize(SIZES['hero-card-plate'], LANCZOS)
    card.putalpha(mask(card.size, 20))
    return card


def normalize_dial(crop):
    dial = filled_rgb(crop).resize((256, 256), LANCZOS)
    # Radial resampling preserves the generated ring, paper window and rivet,
    # while giving every family an exactly centred 46%-diameter window.
    data = np.array(dial)
    mid = data[128, :, :3].mean(axis=1)
    left, right = 128, 128
    while left > 0 and mid[left - 1] > 150:
        left -= 1
    while right < 255 and mid[right + 1] > 150:
        right += 1
    old_r = (right - left + 1) / 2
    assert 40 < old_r < 90, (left, right)
    y, x = np.mgrid[0:256, 0:256].astype(float)
    dx, dy = x - 127.5, y - 127.5
    r = np.sqrt(dx * dx + dy * dy)
    target_r = 256 * .46 / 2
    mapped = np.where(r < target_r, r * old_r / target_r,
                      old_r + (r - target_r) * (128 - old_r) / (128 - target_r))
    factor = mapped / np.maximum(r, .0001)
    sx = np.clip(127.5 + dx * factor, 0, 254.999)
    sy = np.clip(127.5 + dy * factor, 0, 254.999)
    x0, y0 = sx.astype(int), sy.astype(int)
    wx, wy = (sx - x0)[..., None], (sy - y0)[..., None]
    out = ((data[y0, x0] * (1 - wx) + data[y0, x0 + 1] * wx) * (1 - wy)
           + (data[y0 + 1, x0] * (1 - wx) + data[y0 + 1, x0 + 1] * wx) * wy)
    dial = Image.fromarray(np.clip(out, 0, 255).astype('uint8'))
    dial.putalpha(mask(dial.size, circle=True))
    return dial


def normalize_strip(crop):
    strip = filled_rgb(crop).resize((1200, 88), LANCZOS)
    # The middle 80% is four repeats of a 240 px mirrored texture period.
    # Mirroring yields identical boundary columns without a colour jump.
    half = strip.crop((540, 0, 660, 88))
    tile = Image.new('RGBA', (240, 88))
    tile.paste(half, (0, 0))
    tile.paste(ImageOps.mirror(half), (120, 0))
    for x in range(120, 1080, 240):
        strip.paste(tile, (x, 0))
    # Blend outside the repeat region into the original end caps.
    for i in range(24):
        weight = (i + 1) / 24
        left = Image.blend(strip.crop((96+i, 0, 97+i, 88)),
                           tile.crop((216+i, 0, 217+i, 88)), weight)
        right = Image.blend(tile.crop((i, 0, i+1, 88)),
                            strip.crop((1080+i, 0, 1081+i, 88)), weight)
        strip.paste(left, (96+i, 0))
        strip.paste(right, (1080+i, 0))
    strip.putalpha(mask(strip.size, 22))
    return strip


def main():
    records = []
    for family in FAMILIES:
        (ROOT / family).mkdir(exist_ok=True)
        for plate, size in SIZES.items():
            raw, box, crop = source(family, plate)
            if plate == 'hero-card-plate':
                image = normalize_card(family, crop)
            elif plate == 'hp-dial':
                image = normalize_dial(crop)
            elif plate == 'question-strip':
                image = normalize_strip(crop)
            else:
                image = filled_rgb(crop).resize(size, LANCZOS)
                image.putalpha(mask(size, 13))
            # Remove hidden RGB residue outside the antialiased silhouette.
            pixels = np.array(image)
            pixels[pixels[:, :, 3] == 0, :3] = 0
            image = Image.fromarray(pixels)
            path = ROOT / family / f'{plate}.png'
            image.save(path)
            assert image.size == size and image.mode == 'RGBA'
            assert image.getchannel('A').getextrema() == (0, 255)
            assert image.getpixel((0, 0))[3] == 0
            assert image.getpixel((size[0]//2, size[1]//2))[3] == 255
            record = dict(family=family, plate=plate, raw_size=raw.size,
                          crop_box=box, normalized_size=size,
                          sha256=hashlib.sha256(path.read_bytes()).hexdigest())
            if plate == 'question-strip':
                a = np.array(image)
                assert np.array_equal(a[:, 120:360], a[:, 360:600])
                assert np.array_equal(a[:, 120], a[:, 1079])
                record.update(repeat_region=[120, 1080], repeat_period=240,
                              repeat_boundary_max_difference=0)
            records.append(record)

    # No labels, sample names or captions are rendered into either sheet.
    sheet = Image.new('RGB', (1600, 1200), '#17191E')
    for i, family in enumerate(FAMILIES):
        center = (i * 1600 // 3 + (i + 1) * 1600 // 3) // 2
        for plate, y, width in [('hero-card-plate', 110, 480),
                                 ('hp-dial', 430, 256),
                                 ('pile-slip', 790, 240),
                                 ('question-strip', 960, 480)]:
            image = Image.open(ROOT / family / f'{plate}.png')
            image = image.resize((width, round(image.height * width / image.width)), LANCZOS)
            sheet.paste(image, (center - image.width // 2, y), image)
    sheet.save(ROOT / 'swatch-sheet.png')

    # White background review sheet exposes halos and accidentally opaque pixels.
    review = Image.new('RGB', (1600, 1200), '#E5E5E5')
    for i, family in enumerate(FAMILIES):
        center = (i * 1600 // 3 + (i + 1) * 1600 // 3) // 2
        for plate, y, width in [('hero-card-plate', 110, 480), ('hp-dial', 430, 256),
                                 ('pile-slip', 790, 240), ('question-strip', 960, 480)]:
            image = Image.open(ROOT / family / f'{plate}.png')
            image = image.resize((width, round(image.height * width / image.width)), LANCZOS)
            review.paste(image, (center - image.width // 2, y), image)
    (ROOT / 'review').mkdir(exist_ok=True)
    review.save(ROOT / 'review' / 'alpha-on-light.png')
    (ROOT / 'validation.json').write_text(
        json.dumps(dict(tool='image_gen', plates=records, swatch_size=[1600, 1200],
                        moderation_blocked=False), ensure_ascii=False, indent=2), encoding='utf-8')
    print(f'Validated {len(records)} RGBA plates, exact sizes, transparent corners and repeat regions.')


if __name__ == '__main__':
    main()
