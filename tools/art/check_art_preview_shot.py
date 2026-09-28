"""Conservative pixel gate for a live Cobble art-review screenshot.

Geometry/zone count and authoritative state are checked separately in the
client traces. This gate only rejects empty, unlit, missing-HUD and
wrong-resolution captures; it does not approve K1 readability by itself.
"""
import json
import statistics
import sys
from pathlib import Path

from PIL import Image


def fraction_lit(pixels):
    return sum(max(rgb) > 20 for rgb in pixels) / max(1, len(pixels))


path = Path(sys.argv[1])
im = Image.open(path).convert("RGB")
w, h = im.size
all_pixels = list(im.get_flattened_data())
board = list(im.crop((int(.35 * w), int(.63 * h), int(.65 * w), int(.84 * h))).get_flattened_data())
top_hud = list(im.crop((0, 0, int(.25 * w), int(.13 * h))).get_flattened_data())
hand = list(im.crop((int(.25 * w), int(.91 * h), int(.75 * w), h)).get_flattened_data())
lightness = [0.2126 * r + 0.7152 * g + 0.0722 * b for r, g, b in board]
measured = {
    "resolution": [w, h],
    "frame_nonblack_fraction": round(fraction_lit(all_pixels), 4),
    "board_nonblack_fraction": round(fraction_lit(board), 4),
    "board_luma_stddev": round(statistics.pstdev(lightness), 2),
    "top_hud_nonblack_fraction": round(fraction_lit(top_hud), 4),
    "hand_nonblack_fraction": round(fraction_lit(hand), 4),
}
reasons = []
if (w, h) != (1920, 1080):
    reasons.append("capture is not 1920x1080")
if measured["frame_nonblack_fraction"] < .25:
    reasons.append("mostly black frame")
if measured["board_nonblack_fraction"] < .75 or measured["board_luma_stddev"] < 7:
    reasons.append("board region is missing, unlit, or flat")
if measured["top_hud_nonblack_fraction"] < .08:
    reasons.append("top HUD region missing")
if measured["hand_nonblack_fraction"] < .12:
    reasons.append("card hand region missing")
print(json.dumps({"pass": not reasons, "reasons": reasons, "measurements": measured},
                 ensure_ascii=False, indent=2))
sys.exit(0 if not reasons else 1)
