"""Reproducible IC-36 vectors and review sheets. All writes stay in PKG."""
import sys
sys.dont_write_bytecode=True
import json
from pathlib import Path
import numpy as np
from scipy import ndimage
from PIL import Image,ImageDraw,ImageFont
import draw_candidates as d

PKG=Path(__file__).resolve().parents[1]
BGS=[('navy','#061623'),('cream','#F9EBDB'),('board-gray','#808080')]
FONT=ImageFont.truetype('C:/Windows/Fonts/arial.ttf',18)

def save(im,path):
    target=(PKG/path).resolve()
    assert target.is_relative_to(PKG)
    target.parent.mkdir(parents=True,exist_ok=True)
    im.save(target)

def concept(name,variant):
    im=Image.open(PKG/'concepts'/f'{name}-{variant}.png').convert('RGBA')
    a=np.array(im); rgb=a[...,:3].astype(float)
    # Review-only removal of corner-connected navy, never the original asset.
    navy=np.array([6,22,35])
    mask=np.sqrt(((rgb-navy)**2).sum(2))<=16
    labels,n=ndimage.label(mask)
    border=np.unique(np.concatenate([labels[0],labels[-1],labels[:,0],labels[:,-1]]))
    border=border[border!=0]
    bg=np.isin(labels,border)
    a[bg,3]=0
    return Image.fromarray(a,'RGBA')

def panel(asset,size,bg,gray=False):
    if asset.size!=(size,size): asset=asset.resize((size,size),Image.Resampling.LANCZOS)
    im=Image.new('RGBA',(size,size),bg);im.alpha_composite(asset)
    return d.gray(im) if gray else im

def masters(name,gray=False):
    ims=[concept(name,'A'),concept(name,'B'),d.render(name,1024)]
    out=Image.new('RGBA',(3168,3264),'#20232A');draw=ImageDraw.Draw(out)
    for col,title in enumerate(['Concept A','Concept B','Vector A / recommended']):
        draw.text((24+col*1056,12),f'{name} | {title} | 1024 px',font=FONT,fill='white')
    for row,(bgn,bg) in enumerate(BGS):
        y=48+row*1072
        draw.text((24,y-22),bgn,font=FONT,fill='white')
        for col,im in enumerate(ims):out.alpha_composite(panel(im,1024,bg,gray),(24+col*1056,y))
    if gray:out=d.gray(out)
    save(out,f'comparison/{name}-1024-{"gray" if gray else "color"}.png')

def working(size,gray=False):
    cell=max(160,size*4+24);cw=3*cell+190;rh=size*4+64
    out=Image.new('RGBA',(cw,60+12*rh),'#20232A');draw=ImageDraw.Draw(out)
    draw.text((12,12),f'IC-36 | {size}px | nearest x4 | A / B / vector',font=FONT,fill='white')
    for ni,name in enumerate(d.CANDIDATES):
        ims=[concept(name,'A'),concept(name,'B'),d.render(name,size)]
        for bi,(bgn,bg) in enumerate(BGS):
            y=60+(ni*3+bi)*rh
            draw.text((12,y+20),f'{name}\n{bgn}',font=FONT,fill='white')
            for ci,im in enumerate(ims):
                x=190+ci*cell
                draw.text((x,y),['A','B','Vector'][ci],font=FONT,fill='white')
                native=panel(im,size,bg,gray)
                out.alpha_composite(native.resize((size*4,size*4),Image.Resampling.NEAREST),(x,y+28))
    if gray:out=d.gray(out)
    save(out,f'comparison/compare-{size}-{"gray" if gray else "color"}.png')

GROUPS={
 'end-turn':['end-turn','state-boost','action-attack','action-defense','action-maneuver','action-scheme'],
 'card-drop':['card-drop','state-pending-place'],
 'log':['log','resource-card','menu'],
 'pointer':['pointer','plain-arrow'],
}

def neighbours():
    rows=3*3*4;rh=174
    out=Image.new('RGBA',(1510,60+rh*rows),'#20232A');draw=ImageDraw.Draw(out)
    draw.text((12,12),'IC-36 | grayscale neighbours | 18 / 24 / 32 px | native + nearest x4',font=FONT,fill='white')
    row=0
    for size in [18,24,32]:
        for bgn,bg in BGS:
            for group,names in GROUPS.items():
                y=60+row*rh; row+=1
                draw.text((12,y+32),f'{size}px\n{bgn}\n{group}',font=FONT,fill='white')
                for i,name in enumerate(names):
                    x=200+i*210
                    draw.text((x,y),name,font=FONT,fill='white')
                    im=panel(d.render(name,size),size,bg,True)
                    out.alpha_composite(im,(x,y+28))
                    out.alpha_composite(im.resize((size*4,size*4),Image.Resampling.NEAREST),(x+44,y+28))
    save(d.gray(out),'comparison/neighbours-gray-18-24-32.png')
    # Compact sheet convenient for human inspection, same samples and three sizes.
    compact=Image.new('RGBA',(1510,60+rh*12),'#20232A')
    compact.alpha_composite(out.crop((0,0,1510,60)),(0,0))
    for si in range(3):
        start=60+si*12*rh
        compact.alpha_composite(out.crop((0,start,1510,start+4*rh)),(0,60+si*4*rh))
    save(compact,'comparison/neighbours-gray-navy-compact.png')

def vector_overview():
    out=Image.new('RGBA',(1180,1180),'#20232A');draw=ImageDraw.Draw(out)
    for row,size in enumerate([24,32,48,64]):
        draw.text((8,row*290+8),f'{size}px nearest x4',font=FONT,fill='white')
        for col,name in enumerate(d.CANDIDATES):
            x=col*290+12;y=row*290+34
            draw.text((x,y),name,font=FONT,fill='white')
            im=panel(d.render(name,size),size,'#061623')
            out.alpha_composite(im.resize((size*4,size*4),Image.Resampling.NEAREST),(x,y+24))
    save(out,'comparison/vector-overview-color.png')
    save(d.gray(out),'comparison/vector-overview-gray.png')

def main():
    for size in d.SIZES:
        for name in d.CANDIDATES:
            im=d.render(name,size)
            save(im,f'vector/{size}/{name}.png')
            save(d.gray(im),f'vector/{size}/{name}-gray.png')
    vector_overview();neighbours()
    if all((PKG/'concepts'/f'{n}-{v}.png').exists() for n in d.CANDIDATES for v in 'AB'):
        audit_contacts()
        for name in d.CANDIDATES:
            for gray in [False,True]: masters(name,gray)
        for size in [24,32,48]:
            for gray in [False,True]: working(size,gray)
        print('64 exports, all concept/vector sheets and neighbours built')
    else:print('64 exports and vector/neighbour sheets built; concepts pending')
def audit_contacts():
    # All 64 exports, including gray and diagnostic 16/21 sizes.
    out=Image.new('RGBA',(1500,1160),'#20232A');draw=ImageDraw.Draw(out)
    for col,size in enumerate(d.SIZES):
        draw.text((col*185+10,10),f'{size}px',font=FONT,fill='white')
        for row,(name,isgray) in enumerate((n,g) for n in d.CANDIDATES for g in [False,True]):
            x=col*185+10;y=44+row*138
            suffix='-gray' if isgray else ''
            draw.text((x,y),name+suffix,font=FONT,fill='white')
            im=Image.open(PKG/'vector'/str(size)/f'{name}{suffix}.png').convert('RGBA')
            im=panel(im,size,'#F9EBDB',isgray)
            scale=max(1,96//size)
            thumb=im.resize((96,96),Image.Resampling.LANCZOS) if size==1024 else im.resize((size*scale,size*scale),Image.Resampling.NEAREST)
            out.alpha_composite(thumb,(x,y+28))
    save(out,'comparison/export-audit-all-64.png')
    raw=Image.new('RGBA',(1600,850),'#20232A');draw=ImageDraw.Draw(raw)
    for i,name in enumerate(d.CANDIDATES):
        for j,v in enumerate('AB'):
            im=Image.open(PKG/'concepts'/f'{name}-{v}.png').convert('RGBA').resize((380,380),Image.Resampling.LANCZOS)
            raw.alpha_composite(im,(i*400,40+j*410))
            draw.text((i*400+10,10+j*410),f'{name} {v}',font=FONT,fill='white')
    save(raw,'comparison/concepts-unretouched-contact.png')

if __name__=='__main__':main()
