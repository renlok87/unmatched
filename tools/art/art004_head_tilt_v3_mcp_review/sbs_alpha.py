import sys
from PIL import Image, ImageDraw
def flat(p):
    im = Image.open(p).convert("RGBA")
    bg = Image.new("RGBA", im.size, (255, 0, 255, 255))
    bg.alpha_composite(im)
    return bg.convert("RGB")
def sbs(a, b, out, box=None, scale=1.0):
    ia, ib = flat(a), flat(b)
    if box:
        ia, ib = ia.crop(box), ib.crop(box)
    w, h = ia.size
    W, H = int(w * scale), int(h * scale)
    im = Image.new("RGB", (W * 2 + 10, H + 20), (40, 40, 40))
    im.paste(ia.resize((W, H), Image.NEAREST), (0, 20)); im.paste(ib.resize((W, H), Image.NEAREST), (W + 10, 20))
    d = ImageDraw.Draw(im); d.text((4, 4), "v2 " + a.split("\\")[-1].split("/")[-1], fill=(255, 255, 0)); d.text((W + 14, 4), "v3 " + b.split("\\")[-1].split("/")[-1], fill=(255, 255, 0))
    im.save(out)
if __name__ == "__main__":
    box = tuple(int(v) for v in sys.argv[4].split(",")) if len(sys.argv) > 4 and sys.argv[4] != "-" else None
    sbs(sys.argv[1], sys.argv[2], sys.argv[3], box, float(sys.argv[5]) if len(sys.argv) > 5 else 1.0)
