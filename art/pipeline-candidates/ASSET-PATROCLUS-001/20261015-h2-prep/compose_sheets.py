"""Compose real Blender scout renders; no generative or substitute imagery."""
import json
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

out = Path(__file__).resolve().parent
data = json.loads((out / "source-inventory.json").read_text())
font = ImageFont.truetype("C:/Windows/Fonts/arial.ttf", 22)
small = ImageFont.truetype("C:/Windows/Fonts/arial.ttf", 17)
names = list(data["parts"])

def sheet(items, filename):
    cols, tw, th = 3, 720, 412
    canvas = Image.new("RGB", (cols * tw, ((len(items)+cols-1)//cols) * th + 76), (22, 25, 32))
    d = ImageDraw.Draw(canvas)
    d.text((16, 8), "PATROCLUS | raw H2 parts | isolated global front34 / back34", font=font, fill="white")
    d.text((16, 40), "SHA256 " + data["source"]["sha256_before"] + " | source unchanged | NOT acceptance", font=small, fill=(180,190,205))
    for j, name in enumerate(items):
        x,y = (j%cols)*tw, (j//cols)*th+76
        meta=data["parts"][name]
        d.rectangle((x+5,y+3,x+tw-5,y+th-3), outline=tuple(meta["color_rgb"]), width=2)
        d.text((x+14,y+8), name + " | " + str(meta["triangles"]) + " tris", font=font, fill="white")
        for k, view in enumerate(("front34","back34")):
            im=Image.open(out / "renders" / (name+"-"+view+".png")).convert("RGB")
            im.thumbnail((350,350))
            canvas.paste(im,(x+10+k*355,y+42))
            d.text((x+20+k*355,y+382), view, font=small, fill=(180,190,205))
    canvas.save(out / filename)
sheet(names,"contact-all24.png")
sheet(names[:12],"contact-parts00-11.png")
sheet(names[12:],"contact-parts12-23.png")
context=Image.new("RGB",(2400,1200),(22,25,32))
for i,view in enumerate(("front34","back34")):
    context.paste(Image.open(out/"renders"/("assembled-"+view+".png")).convert("RGB"),(i*1200,0))
context.save(out/"assembled-context.png")
print("Composed 24 real part pairs, 2 pages and assembled context")
