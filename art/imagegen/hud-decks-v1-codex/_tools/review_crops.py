"""Native-pixel review crops of every corrected state; writes only derived."""
import json
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont
import numpy as np

ROOT=Path(__file__).resolve().parents[4]
PKG=ROOT/'art/imagegen/hud-decks-v1-codex'
OUT=ROOT/'scraped-data/derived/hud-decks-v1-codex'
facts=json.loads((PKG/'facts.json').read_text('utf8'))
font=ImageFont.truetype('C:/Program Files/Epic Games/UE_5.8/Engine/Content/Slate/Fonts/Roboto-BoldCondensed.ttf',16)

def crop(o,gray=False):
    r=o['rectangles_su']['DECKPANEL'] if o['panel_geometry'] else o['rectangles_su']['CHIP-0']
    x,y,w,h=r
    if not o['panel_geometry']:
        last=o['rectangles_su']['CHIP-1'];w=last[0]+last[2]-x
    s=o['su_to_px'];box=(round(x*s)-2,round(y*s)-2,round((x+w)*s)+2,round((y+h)*s)+2)
    with Image.open(OUT/(o['id']+('-gray' if gray else '')+'.png')) as im:return im.crop(box)

def save(sheet,p,gray):
    assert p.resolve().is_relative_to(OUT.resolve());p.parent.mkdir(exist_ok=True)
    if gray:
        a=np.array(sheet);luma=np.rint(a[:,:,:3]@np.array([.2126,.7152,.0722])).astype('uint8');a[:,:,:3]=luma[:,:,None];sheet=Image.fromarray(a)
    sheet.save(p)

for board in ('marmoreal','sarpedon'):
    for w,h,ui in ((1920,1080,100),(1920,1080,150),(1280,720,100),(1280,720,150)):
        outputs=[o for o in facts['rendered_outputs'] if o['board']==board and o['resolution']==[w,h] and o['ui_scale_percent']==ui and o['language']=='ru']
        order=('own','own-end','own-discard','opp','opp-end','chips','chips-stale')
        outputs=sorted(outputs,key=lambda o:order.index(o['state']))
        for gray in (False,True):
            crops=[crop(o,gray) for o in outputs];cw=max(im.width for im in crops)+12;ch=max(im.height for im in crops)+32
            sheet=Image.new('RGBA',(cw*3,ch*3),(6,22,35,255));d=ImageDraw.Draw(sheet)
            for i,(o,im) in enumerate(zip(outputs,crops)):
                x=(i%3)*cw;y=(i//3)*ch;d.text((x+4,y+4),o['state'],font=font,fill=(242,237,228),anchor='lt');sheet.alpha_composite(im,(x+4,y+26))
            p=OUT/'fix1-review'/f'{board}-{w}x{h}-{ui}{"-gray" if gray else ""}.png'
            save(sheet,p,gray)
for gray in (False,True):
    outputs=[o for o in facts['rendered_outputs'] if o['language']=='en'];crops=[crop(o,gray) for o in outputs];cw=max(im.width for im in crops)+12;ch=max(im.height for im in crops)+32
    sheet=Image.new('RGBA',(cw*2,ch),(6,22,35,255));d=ImageDraw.Draw(sheet)
    for i,(o,im) in enumerate(zip(outputs,crops)):
        d.text((i*cw+4,4),o['state']+' EN',font=font,fill=(242,237,228),anchor='lt');sheet.alpha_composite(im,(i*cw+4,26))
    p=OUT/'fix1-review'/f'sarpedon-en{"-gray" if gray else ""}.png';save(sheet,p,gray)
print('18 native-pixel review sheets written to derived/fix1-review')
