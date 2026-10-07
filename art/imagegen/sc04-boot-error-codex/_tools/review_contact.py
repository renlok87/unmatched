#!/usr/bin/env python
"""Open every selected final PNG and emit a contact page in memory only.

No filesystem writes. Native-size samples complement these overview pages.
"""
import base64
import io
import sys
from pathlib import Path
from PIL import Image,ImageDraw,ImageFont
sys.dont_write_bytecode=True
import sc03_boot_loading as b
package=Path(__file__).resolve().parents[1]
derived=b.ROOT/('scraped-data/derived/'+package.name)
paths=sorted([p for folder in (package,derived) for p in folder.rglob('*.png')])
start=int(sys.argv[1]);take=int(sys.argv[2]) if len(sys.argv)>2 else 8
paths=paths[start:start+take]
sheet=Image.new('RGB',(1280,400*((len(paths)+1)//2)),(6,22,35))
draw=ImageDraw.Draw(sheet);font=ImageFont.truetype(str(b.FONTS/'Roboto-Regular.ttf'),14)
for i,path in enumerate(paths):
    x=(i%2)*640;y=(i//2)*400
    with Image.open(path) as im:
        im=im.convert('RGB');im.thumbnail((640,368),Image.Resampling.LANCZOS)
        sheet.paste(im,(x+(640-im.width)//2,y+28))
    draw.text((x+8,y+6),path.name,font=font,fill=(242,237,228))
out=io.BytesIO();sheet.save(out,format='JPEG',quality=35)
print(base64.b64encode(out.getvalue()).decode('ascii'))
