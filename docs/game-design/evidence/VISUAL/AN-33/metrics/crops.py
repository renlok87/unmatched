"""crops.py <out> <view> <x0,y0,x1,y1> <scale> <run>...: colour row + grey row per run."""
import sys
from PIL import Image, ImageOps, ImageDraw
out, view, box, sc = sys.argv[1], sys.argv[2], tuple(int(v) for v in sys.argv[3].split(",")), int(sys.argv[4])
runs = sys.argv[5:]
w, h = (box[2] - box[0]) * sc, (box[3] - box[1]) * sc
W = Image.new("RGB", (w * 2 + 8, (h + 16) * len(runs)), (24, 24, 24)); d = ImageDraw.Draw(W)
for i, r in enumerate(runs):
    im = Image.open(f"{r}/bench-{view}-1920x1080.png").convert("RGB").crop(box).resize((w, h), Image.LANCZOS)
    W.paste(im, (0, i * (h + 16) + 16)); W.paste(ImageOps.grayscale(im).convert("RGB"), (w + 8, i * (h + 16) + 16))
    d.text((4, i * (h + 16) + 2), r.split("/")[-1] + " " + view, fill=(255, 255, 255))
W.save(out); print(out, W.size)
