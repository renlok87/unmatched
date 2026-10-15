"""Deterministic review-only full100 circle previews; never changes source PNG bytes."""
from pathlib import Path
import hashlib
import json
import sys
from PIL import Image, ImageDraw, ImageOps

WAVE = Path(__file__).resolve().parents[1]

def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def circle(original, size):
    rgb = original.convert("RGB").resize((size, size), Image.Resampling.LANCZOS)
    mask = Image.new("L", (size * 4, size * 4), 0)
    ImageDraw.Draw(mask).ellipse((0, 0, size * 4 - 1, size * 4 - 1), fill=255)
    rgb.putalpha(mask.resize((size, size), Image.Resampling.LANCZOS))
    return rgb

for key in sys.argv[1:]:
    package = WAVE / key
    source = package / "portrait-source-candidate.png"
    before = sha(source)
    review = package / "review"
    review.mkdir(exist_ok=True)
    with Image.open(source) as original:
        assert original.width == original.height, "Non-square output requires an actual framing review before full100 proof"
        dimensions = list(original.size)
        images = {}
        for size in [40, 80, 160, 320]:
            images[size] = circle(original, size)
            images[size].save(review / ("circle-full100-" + str(size) + ".png"))
        gray = ImageOps.grayscale(images[80].convert("RGB")).convert("RGBA")
        gray.putalpha(images[80].getchannel("A"))
        gray.save(review / "circle-full100-80-gray.png")
        gray160 = ImageOps.grayscale(images[160].convert("RGB")).convert("RGBA")
        gray160.putalpha(images[160].getchannel("A"))
        gray160.save(review / "circle-full100-160-gray.png")
        sheet = Image.new("RGB", (980, 740), "#17191F")
        draw = ImageDraw.Draw(sheet)
        draw.text((18, 15), key + " | full100 crop review only | source remains byte-preserved", fill="#F2EDE4")
        draw.text((18, 40), "Complete square scaled into circle; no source crop or zoom", fill="#B9B2A6")
        sheet.paste(images[320], (20, 88), images[320])
        draw.text((20, 420), "320 preview; source " + str(original.width) + "x" + str(original.height), fill="#F2EDE4")
        for index, (name, color) in enumerate([("navy", "#061623"), ("cream", "#F9EBDB"), ("gray", "#808080")]):
            x = 370 + index * 195
            draw.rectangle((x, 80, x + 175, 205), fill=color)
            sheet.paste(images[40], (x + 10, 112), images[40])
            sheet.paste(images[80], (x + 80, 97), images[80])
            draw.text((x, 218), name + ": native 40 / 80", fill="#F2EDE4")
        nearest40 = images[40].resize((160, 160), Image.Resampling.NEAREST)
        nearest80 = images[80].resize((320, 320), Image.Resampling.NEAREST)
        sheet.paste(nearest40, (370, 272), nearest40)
        sheet.paste(nearest80, (560, 240), nearest80)
        draw.text((370, 445), "40x4 nearest", fill="#F2EDE4")
        draw.text((560, 525), "80x4 nearest", fill="#F2EDE4")
        sheet.paste(images[160], (20, 490), images[160])
        sheet.paste(gray160, (205, 490), gray160)
        sheet.paste(gray, (405, 550), gray)
        draw.text((20, 665), "Native 160 color", fill="#F2EDE4")
        draw.text((205, 665), "Native 160 gray", fill="#F2EDE4")
        draw.text((405, 645), "Native 80 gray", fill="#F2EDE4")
        sheet.save(review / "full100-review-sheet.png")
    assert sha(source) == before
    (review / "crop-contract.json").write_text(json.dumps({
        "source_sha256": before, "source_dimensions": dimensions,
        "source_pixels_modified": False, "native_sizes": [40, 80, 160], "grayscale_sizes": [80, 160],
        "circle_diameter_percent_of_square": 100, "source_crop": None, "zoom": 1.0,
        "derivatives": "Review evidence only: Lanczos downsample of entire square, circle alpha; nearest magnification on contact sheet.",
        "runtime_widget_or_dpi_test": False,
    }, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"key": key, "dimensions": dimensions, "source_sha256": before, "crop_previews_written": True}))
