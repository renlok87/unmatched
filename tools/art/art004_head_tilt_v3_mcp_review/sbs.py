import sys
from PIL import Image, ImageDraw
def sbs(a, b, box, out, scale=2, labels=("v2", "v3")):
    ia, ib = Image.open(a).crop(box), Image.open(b).crop(box)
    w, h = ia.size
    im = Image.new("RGB", (w * 2 * scale + 10, h * scale + 24), (30, 30, 30))
    im.paste(ia.resize((w * scale, h * scale), Image.LANCZOS), (0, 24))
    im.paste(ib.resize((w * scale, h * scale), Image.LANCZOS), (w * scale + 10, 24))
    d = ImageDraw.Draw(im)
    d.text((6, 4), labels[0] + "  " + a.split("/")[-1].split("\\")[-1], fill=(255, 255, 0))
    d.text((w * scale + 16, 4), labels[1] + "  " + b.split("/")[-1].split("\\")[-1], fill=(255, 255, 0))
    im.save(out)
if __name__ == "__main__":
    box = tuple(int(v) for v in sys.argv[3].split(","))
    sbs(sys.argv[1], sys.argv[2], box, sys.argv[4], int(sys.argv[5]) if len(sys.argv) > 5 else 2)
