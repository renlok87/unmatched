"""Create the requested deterministic comparison sheets and candidate exports.

Original generated concepts stay byte-for-byte intact. Only requested grayscale,
size previews and sheet composition use Pillow. No outside-file writes.
"""
from pathlib import Path
import hashlib
import json
import sys
sys.dont_write_bytecode = True
import numpy as np
from PIL import Image, ImageDraw, ImageFont
import draw_icons_v3_snapshot as v3
import draw_icons_codex as own

ROOT = Path(__file__).resolve().parents[1]
BG = '#161A28'
INK = '#FAF8F2'
DIM = '#B9B2A6'
ROWS = [
    ('turn', 'marker-turn-ring', '01 / TURN RING'),
    ('fallen', 'resource-hp-fallen', '02 / FALLEN HEART'),
    ('stamp', 'marker-x-stamp', '03 / NO DEFENSE'),
    ('slot', 'marker-action-slot-de', '04 / ACTION SLOT'),
]
FONT = 'C:/Windows/Fonts/arial.ttf'

def font(n):
    return ImageFont.truetype(FONT, n)

def gray(im):
    rgba = im.convert('RGBA')
    a = np.asarray(rgba).copy()
    a[..., :3] = np.round(a[..., :3] @ np.array([.2126, .7152, .0722]))[..., None]
    return Image.fromarray(a)

def panel(im):
    out = Image.new('RGBA', im.size, BG)
    out.alpha_composite(im.convert('RGBA'))
    return out.convert('RGB')

def save(im, path):
    path = ROOT / path
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.parent == ROOT/'comparison' and path.name.endswith('-gray.png'):
        # The requested grayscale sheet includes the background and labels.
        im = gray(im).convert('RGB')
    im.save(path)

def vectors(engine, name, size):
    return engine.render(name, size)

def concept(stem, size):
    # Full generated canvas, with its original margin; no crop or retouch.
    return Image.open(ROOT / 'concepts' / (stem+'.png')).convert('RGBA').resize((size,size), Image.Resampling.LANCZOS)

def comparison_master(family, name, title, mono):
    im = Image.new('RGB', (3240, 2280), BG)
    d = ImageDraw.Draw(im)
    d.text((36, 24), title+' / 1024 PX / '+('GRAY' if mono else 'COLOR'), fill=INK, font=font(36))
    for col, label in enumerate(['IMAGEGEN CONCEPT', 'VECTOR V3 AS IS', 'CODEX PROPOSAL']):
        d.text((36+1080*col, 83), label, fill=DIM, font=font(28))
    for row, variant in enumerate(['a','b']):
        d.text((36, 136+1060*row), 'CONCEPT '+variant.upper(), fill=DIM, font=font(24))
        cells = [concept(family+'-'+variant,1024), vectors(v3,name,1024), vectors(own,name,1024)]
        for col, cell in enumerate(cells):
            if mono: cell=gray(cell)
            im.paste(panel(cell),(28+1080*col,184+1060*row))
    save(im, f'comparison/{family}-1024-'+('gray' if mono else 'color')+'.png')

def comparison_small(size, mono):
    im = Image.new('RGB',(1024,1230),BG)
    d = ImageDraw.Draw(im)
    mode = 'GRAY' if mono else 'COLOR'
    d.text((24,20),f'DE-012 / {size} PX / {mode}',fill=INK,font=font(26))
    d.text((24,57),'Native at left of each cell; x8 NEAREST at right. Concepts keep original margins.',fill=DIM,font=font(16))
    for col,label in enumerate(['IMAGEGEN CONCEPT','VECTOR V3 AS IS','CODEX PROPOSAL']):
        d.text((24+336*col,92),label,fill=INK,font=font(18))
    for i,(family,name,title) in enumerate(ROWS):
        for j,variant in enumerate(['a','b']):
            row=i*2+j
            y=130+row*132
            d.text((24,y),f'{family.upper()} / {variant.upper()}',fill=DIM,font=font(15))
            cells=[concept(family+'-'+variant,size),vectors(v3,name,size),vectors(own,name,size)]
            for col,cell in enumerate(cells):
                if mono: cell=gray(cell)
                tile=panel(cell)
                x=24+336*col
                im.paste(tile,(x,y+35))
                # Larger cells in the 32px sheet need more row height than 16px.
                mult=3 if size==32 else 4 if size==24 else 6
                im.paste(tile.resize((size*mult,size*mult),Image.Resampling.NEAREST),(x+75,y+29))
    # The header states the actual multiplier (all enlarged cells are 96px).
    d.rectangle((24,54,1010,81),fill=BG)
    d.text((24,57),f'Native at left; x{3 if size==32 else 4 if size==24 else 6} NEAREST at right. Full concept canvas, no crop.',fill=DIM,font=font(16))
    save(im,f'comparison/compare-{size}px-'+('gray' if mono else 'color')+'.png')

def overview(mono):
    im=Image.new('RGB',(1024,1024),BG)
    d=ImageDraw.Draw(im)
    d.text((24,18),'DE-012 / CONCEPT - V3 - CODEX',fill=INK,font=font(28))
    d.text((24,58),'A / B generated concepts     |     existing vector     |     proposal',fill=DIM,font=font(18))
    for row,(family,name,title) in enumerate(ROWS):
        y=100+row*225
        d.text((24,y),title,fill=DIM,font=font(18))
        cells=[concept(family+'-a',160),concept(family+'-b',160),vectors(v3,name,160),vectors(own,name,160)]
        for col,(cell,x) in enumerate(zip(cells,[24,196,520,804])):
            if mono: cell=gray(cell)
            im.paste(panel(cell),(x,y+30))
        for x,label in zip([24,196,520,804],['A','B','V3','CODEX']):
            d.text((x,y+195),label,fill=INK,font=font(14))
    save(im,'comparison/overview-1024-'+('gray' if mono else 'color')+'.png')

def states():
    im=Image.new('RGB',(1280,850),BG)
    d=ImageDraw.Draw(im)
    d.text((24,18),'DE-012 / STATE REFERENCES / CANDIDATES ONLY',fill=INK,font=font(26))
    d.text((24,74),'TURN: whole rim, 1000 ms; F-07 retains red terminal frame. No sparks.',fill=DIM,font=font(19))
    cells=[v3.render('marker-turn-ring',128,layer='flash',frame=i) for i in [0,3,6]]
    resting=v3.render('marker-turn-ring',128)
    resting.putalpha(resting.getchannel('A').point(lambda a:round(a*.35)))
    cells.append(resting)
    for j,(cell,label) in enumerate(zip(cells,['0 ms / YELLOW','500 ms / ORANGE','<1000 ms / RED','1000+ / RIM .35'])):
        x=40+j*300; im.paste(panel(cell),(x,110)); d.text((x,247),label,fill=INK,font=font(16))
    d.text((24,290),'FALLEN: blackened heart -> X stamp 200 ms, impact 120 ms; starts contact +1100 ms.',fill=DIM,font=font(19))
    for j,layer in enumerate(['heart',None]):
        cell=own.render('resource-hp-fallen',128,layer=layer)
        im.paste(panel(cell),(40+300*j,326))
        d.text((40+300*j,461),['BLACKENED','STAMPED X'][j],fill=INK,font=font(16))
    d.text((24,512),'DE SLOT: selection fills in 300 ms; Undo 150 ms; empty ring pulse 770 ms.',fill=DIM,font=font(19))
    slotcells=[own.render('marker-action-slot-de',128)]+[v3.render('action-'+n,128) for n in ['attack','defense','maneuver','scheme']]
    for j,(cell,label) in enumerate(zip(slotcells,['EMPTY','ATTACK','DEFENSE','MANEUVER','SCHEME'])):
        x=40+245*j; im.paste(panel(cell),(x,552)); d.text((x,690),label,fill=INK,font=font(16))
    d.text((24,754),'Filled disks / glyphs reuse accepted v3 art exactly. Default tracker stays v3 until art acceptance.',fill=DIM,font=font(18))
    d.text((24,786),'Reduced motion: static turn rim .35; stamp / fill opacity <=100 ms; slot ring static.',fill=DIM,font=font(18))
    save(im,'comparison/state-reference.png')

def main():
    for family,name,title in ROWS:
        for size in [1024,16,24,32]:
            for label,engine in [('vector-as-is',v3),('vector-codex',own)]:
                im=engine.render(name,size)
                save(im,f'{label}/{size}/{name}.png')
                save(gray(im),f'{label}/{size}/{name}-gray.png')
            for variant in ['a','b']:
                im=concept(family+'-'+variant,size)
                save(im,f'concept-previews/{size}/{family}-{variant}.png')
                save(gray(im),f'concept-previews/{size}/{family}-{variant}-gray.png')
        for mono in [False,True]: comparison_master(family,name,title,mono)
    for size in [16,24,32]:
        for mono in [False,True]: comparison_small(size,mono)
    for mono in [False,True]: overview(mono)
    states()
    for size in [1024,16,24,32]:
        for layer in ['heart','cross']:
            save(own.render('resource-hp-fallen',size,layer=layer),f'vector-codex/{size}/resource-hp-fallen_{layer}.png')
        for action in ['attack','defense','maneuver','scheme']:
            save(v3.render('action-'+action,size),f'vector-codex/{size}/slot-filled-{action}.png')
    print('Comparison sheets, native sizes, grayscale exports and state references written inside',ROOT)

if __name__=='__main__': main()
