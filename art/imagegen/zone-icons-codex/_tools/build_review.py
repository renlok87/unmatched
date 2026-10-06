"""Review sheets; generated concepts remain byte-for-byte untouched."""
import json
from pathlib import Path
from PIL import Image,ImageDraw,ImageFont
from zone_icons import PACKAGE,KEYS,BOARDS,COLORS,rgba,gray,render,save,glyph_mask,colored

FONT=ImageFont.truetype('C:/Windows/Fonts/arial.ttf',16)

def label(im,xy,text,color=COLORS['glyph']):
    ImageDraw.Draw(im).text(xy,text,font=FONT,fill=rgba(color))

def concept(key,variant,size):
    p=PACKAGE/f'concepts/zone-{key}-{variant}.png'
    if p.exists():
        return Image.open(p).convert('RGBA').resize((size,size),Image.Resampling.LANCZOS)
    im=Image.new('RGBA',(size,size),rgba(COLORS['navy']))
    # A missing concept is never substituted with a procedural drawing.
    if size>=96:
        label(im,(8,8),'NOT GENERATED')
    return im

def comparisons():
    for size in (1024,24,32,48):
        zoom=1 if size==1024 else 4
        n=size*zoom
        cell_w=n+28
        cell_h=n+48
        sheet=Image.new('RGBA',(cell_w*4+120,cell_h*8+44),rgba(COLORS['navy']))
        headers=['Концепт A','Концепт B','Marmoreal','Sarpedon']
        for col,h in enumerate(headers):
            label(sheet,(120+col*cell_w,10),h)
        for row,key in enumerate(KEYS):
            y=44+row*cell_h
            label(sheet,(8,y+12),key)
            imgs=[concept(key,'A',size),concept(key,'B',size),render(key,size)]
            imgs.append(render(key,size,BOARDS['sarpedon'][key]) if key in BOARDS['sarpedon'] else None)
            for col,im in enumerate(imgs):
                x=120+col*cell_w
                if im is None:
                    label(sheet,(x,y+12),'нет зоны')
                else:
                    if zoom>1:
                        im=im.resize((n,n),Image.Resampling.NEAREST)
                    sheet.alpha_composite(im,(x,y))
                    if col<2 and not (PACKAGE/f'concepts/zone-{key}-{"AB"[col]}.png').exists():
                        label(sheet,(x,y+n+4),'NOT GENERATED')
        save(sheet,Path(f'comparison/concepts-vector-{size}-color.png'))
        save(gray(sheet),Path(f'comparison/concepts-vector-{size}-gray.png'))

def contexts():
    for board,colors in BOARDS.items():
        for size in (1024,24,32,48):
            z=1 if size==1024 else 4
            n=size*z
            w=n+32
            h=n+48
            keys=[key for key in KEYS if key in colors]
            sheet=Image.new('RGBA',(2*w+128,h*len(keys)+40),rgba(COLORS['navy']))
            label(sheet,(8,8),f'{board} / {size}')
            for col,bg in enumerate((COLORS['cream'],COLORS['neutral'])):
                label(sheet,(128+col*w,8),bg)
                for row,key in enumerate(keys):
                    y=40+row*h
                    label(sheet,(8,y+12),key)
                    tile=Image.new('RGBA',(w,n+24),rgba(bg))
                    im=render(key,size,colors[key]).resize((n,n),Image.Resampling.NEAREST)
                    tile.alpha_composite(im,(16,12))
                    sheet.alpha_composite(tile,(128+col*w,y))
            save(sheet,Path(f'comparison/context-{board}-{size}-color.png'))
            save(gray(sheet),Path(f'comparison/context-{board}-{size}-gray.png'))

def overview():
    sheet=Image.new('RGBA',(8*168+104,2*192+52),rgba(COLORS['navy']))
    label(sheet,(8,8),'Eight shapes / neutral disc / Rec.709 grayscale / nearest x4')
    for row,size in enumerate((24,32)):
        y=52+row*192
        label(sheet,(8,y+20),f'{size} px')
        for col,key in enumerate(KEYS):
            n=size*4
            x=104+col*168
            im=render(key,size,COLORS['neutral']).resize((n,n),Image.Resampling.NEAREST)
            sheet.alpha_composite(im,(x+(128-n)//2,y))
            label(sheet,(x,y+140),key)
    save(gray(sheet),Path('comparison/all-eight-gray-24-32.png'))
    # Native geometry atlas makes every pixel inspectable, including boundary sizes.
    sheet=Image.new('RGBA',(8*144+80,7*160+52),rgba(COLORS['navy']))
    label(sheet,(8,8),'Direct vector rasterization; sizes 16 / 21 / 24 / 32 / 48 / 64 / 96')
    for row,size in enumerate((16,21,24,32,48,64,96)):
        y=52+row*160
        label(sheet,(8,y+12),str(size))
        for col,key in enumerate(KEYS):
            z=4 if size<=32 else 1
            im=render(key,size).resize((size*z,size*z),Image.Resampling.NEAREST)
            sheet.alpha_composite(im,(80+col*144,y))
            label(sheet,(80+col*144,y+136),key)
    save(sheet,Path('comparison/vector-all-sizes-color.png'))
    save(gray(sheet),Path('comparison/vector-all-sizes-gray.png'))

if __name__=='__main__':
    comparisons()
    contexts()
    overview()
    print('27 review sheets written')
