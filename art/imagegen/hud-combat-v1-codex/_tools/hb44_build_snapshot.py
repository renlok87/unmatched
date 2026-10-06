#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""HB-44. Static review mockups only; never creates runtime numeral textures.

Run: python art/imagegen/hud-world-v1-codex/_tools/build_hb44.py
Recheck: same command --verify-only. Writes only to the two contracted folders.
The v3 engine snapshot is immutable; this separate module reads its literal palette
without importing it (which would bind its ROOT and require cairo).
"""
from __future__ import annotations
import argparse
import ast
import hashlib
import json
import math
from pathlib import Path
import re
import sys

import numpy as np
from PIL import Image, ImageDraw, ImageFont

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[4]
PKG = ROOT / 'art/imagegen/hud-world-v1-codex'
DERIVED = ROOT / 'scraped-data/derived/hud-world-v1-codex'
FONTS = Path('C:/Program Files/Epic Games/UE_5.8/Engine/Content/Slate/Fonts')
BC = FONTS / 'Roboto-BoldCondensed.ttf'
RG = FONTS / 'Roboto-Regular.ttf'
SNAPSHOT = PKG / '_tools/draw_icons_v3_snapshot.py'
TOKENS = next(ast.literal_eval(n.value) for n in ast.parse(SNAPSHOT.read_text(encoding='utf-8')).body
              if isinstance(n, ast.Assign) and any(isinstance(t, ast.Name) and t.id == 'TOKENS' for t in n.targets))
TOKENS.update({'text.primary':'#F2EDE4','hp.fill':'#50BE64','hp.back':'#461E1E',
               'damage.text':'#FFE0AF','fx.heal':'#8CE69A'})
ICON = ROOT / 'art/imagegen/hud-icons-v3/sizes/action-attack-token-96.png'
BOARDS = {
 'marmoreal': 'docs/game-design/evidence/ENV-MAPS/p7-concept-paste-2026-10-01/marmoreal-concept-flag/bench-K1-1920x1080.png',
 'sarpedon': 'docs/game-design/evidence/ENV-MAPS/p10-sarpedon-rework-2026-10-03/sarpedon-packaged/bench-K1-1920x1080.png',
}
EXPECTED = {
 BOARDS['marmoreal']:'aeafe8f25aea665f', BOARDS['sarpedon']:'bf36d5d6574c7312',
 'scraped-data/api/heroes/medusa.json':'7842bdfdc73a256f',
 'scraped-data/api/heroes/king-arthur.json':'820e2c3fc1486a31',
 'docs/game-design/visual/02-visual-design.md':'159cd647e038ed383eb897e6c13e614661691ab80dd4243fb8833035bc72f1e5',
 'docs/game-design/visual/04-hud-spec.md':'199c6b34a378207ad9f6c364bc7b02babd122bd94b266ac312ece1076f7da34e',
 'docs/game-design/evidence/DE-FOOTAGE/2026-10-05/I/marmoreal/combat-20261005-235827/host/s09-turn-banner.jpg':'246f8aaa887c70f664f05c471a41513aeac874cee8ab6dce3e75cbcbd69eeb36',
 'docs/game-design/evidence/DE-FOOTAGE/2026-10-05/I/marmoreal/combat-20261005-235827/host/s09-damage-combat.jpg':'65bfd3db46d612b73840acd4759f39fa39923d99377f387c5b7aa5c3094eb8cf',
 'docs/game-design/evidence/DE-FOOTAGE/2026-10-05/I/sarpedon/combat-20261005-235948/joiner/s09-damage-number.jpg':'8bc3653a1bf59ef4f57f2225a25d120f617bf53f3ab9b11c9ffdb640cf72e8ba',
 'art/imagegen/hud-icons-v3/sizes/action-attack-token-96.png':'c03a364f8d9541076bcaafe833210b69dec65857144b999ab691dbf5d9f857a4',
}
TRACE = 'docs/game-design/evidence/DE-FOOTAGE/2026-10-05/I/marmoreal/combat-20261005-235827/combat-client-host.trace.txt'
IDS = ['medusa','harpy1','harpy2','harpy3','arthur','merlin']
GEOMETRY = {}
CONFIGS = [('1920x1080','100',1920,1080,1.0,1.0), ('1280x720','150',1280,720,.75,1.5)]
ANCHOR_CACHE = {}

def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()
def save_json(path, obj): path.write_text(json.dumps(obj,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
def rgb(key): return tuple(bytes.fromhex(TOKENS.get(key,key).lstrip('#')))
def font(size, regular=False): return ImageFont.truetype(str(RG if regular else BC),max(1,round(size)))
def gray(im):
    a=np.asarray(im.convert('RGB'),dtype=np.float64)
    y=np.rint(a@np.array([.2126,.7152,.0722])).astype(np.uint8)
    return Image.fromarray(y).convert('RGB')
def output(path,im):
    path.parent.mkdir(parents=True,exist_ok=True); im.convert('RGBA').save(path)
    gray(im).convert('RGBA').save(path.with_name(path.stem+'-gray.png'))

def decode(slug):
    raw=json.loads((ROOT/f'scraped-data/api/heroes/{slug}.json').read_text(encoding='utf-8'))
    d=raw['nodes'][2]['data']; memo={}
    def r(i):
        if i<0:return None
        if i in memo:return memo[i]
        x=d[i]
        if isinstance(x,dict):
            memo[i]={}; memo[i].update({k:r(v) for k,v in x.items()});return memo[i]
        if isinstance(x,list):
            memo[i]=[];memo[i].extend(r(v) for v in x);return memo[i]
        return x
    return r(0)

def data():
    m=decode('medusa'); a=decode('king-arthur')
    hero_m=m['fetchedHero'];hero_a=a['fetchedHero']
    actors={'medusa':dict(hero_m,hero=True,team=1),'arthur':dict(hero_a,hero=True,team=2)}
    for i,s in enumerate(hero_m['sidekicks'],1):actors[f'harpy{i}']=dict(s,hero=False,team=1,digit=i)
    actors['merlin']=dict(hero_a['sidekicks'][0],hero=False,team=2)
    for v in actors.values():v['startHealth']=int(v['startHealth'])
    grail=next(v['card'] for v in a['fetchedDeck'] if v['card']['title']=='The Holy Grail')
    numbers=[int(n) for n in re.findall(r'\d+',grail['effectAfter'])]
    assert numbers==[4,8],numbers
    trace=(ROOT/TRACE).read_text(encoding='utf-8')
    run={}
    for key in ['medusa','arthur']:
        n=actors[key]['name']; maximum=actors[key]['startHealth']
        hp=re.findall(r'name='+re.escape(n)+r' hp=(\d+)/'+str(maximum),trace)
        value=next(int(v) for v in hp if int(v)<maximum)
        run[key]=value
    assert run=={'medusa':14,'arthur':17}
    assert 'damage=1' in trace
    provenance={'actors':{k:{f:v.get(f) for f in ['name','hero','team','attack','startHealth','digit']} for k,v in actors.items()},
                'run_I':run,'heal_example':{'card':grail['title'],'effectAfter':grail['effectAfter'],
                'before':numbers[0],'after':numbers[1],'delta':numbers[1]-numbers[0]},
                'localized_names_missing':[k for k,v in actors.items() if not v.get('i18n',{}).get('ru')],
                'trace_path':TRACE,'decode':'SvelteKit devalue reference indices, nodes[2].data'}
    return actors,run,provenance

class Canvas:
    def __init__(self,im,scale):
        self.im=im.convert('RGBA');self.scale=scale;self.panels=[];self.texts=[];self.primitives=[]
    def panel(self,box,kind,rad=6,onboard=False):
        s=self.scale; layer=Image.new('RGBA',self.im.size);d=ImageDraw.Draw(layer)
        if onboard:d.rounded_rectangle([box[0]-s,box[1]-s,box[2]+s,box[3]+s],radius=(rad+1)*s,fill=rgb('mark.keyline')+(255,))
        # Edge is composited ON TOP of 0.92 navy, not substituted for body alpha.
        body=Image.new('RGBA',self.im.size); bd=ImageDraw.Draw(body)
        bd.rounded_rectangle(box,radius=rad*s,fill=rgb('card.navy')+(round(.92*255),))
        layer=Image.alpha_composite(layer,body)
        edge=Image.new('RGBA',self.im.size);ImageDraw.Draw(edge).rounded_rectangle(box,radius=rad*s,outline=rgb('card.cream')+(round(.45*255),),width=max(1,round(s)))
        layer=Image.alpha_composite(layer,edge);self.im=Image.alpha_composite(self.im,layer)
        mask=Image.new('1',self.im.size)
        mb=[box[0]-s,box[1]-s,box[2]+s,box[3]+s] if onboard else box
        ImageDraw.Draw(mask).rounded_rectangle(mb,radius=(rad+1)*s if onboard else rad*s,fill=1)
        self.panels.append({'kind':kind,'box':list(box),'radius_su':rad,'mask':mask})
    def text(self,xy,value,su=14,color='text.primary',center=False,regular=False,cap=None):
        f=font(su*self.scale,regular)
        if cap is not None:
            target=cap*self.scale
            f=font(14*self.scale)
            while f.getbbox(value)[3]-f.getbbox(value)[1]<target:f=font(f.size+1)
        d=ImageDraw.Draw(self.im);b=d.textbbox((0,0),value,font=f)
        x,y=xy
        if center:x-=(b[2]-b[0])/2;y-=(b[3]-b[1])/2
        bounds=(max(0,math.floor(x)),max(0,math.floor(y)),min(self.im.width,math.ceil(x+b[2]-b[0]+1)),min(self.im.height,math.ceil(y+b[3]-b[1]+1)))
        region=self.im.crop(bounds).convert('RGB')
        # Test only pixels actually covered by the glyph core. Whitespace in a numeral
        # bounding box can touch its cream disc border and is not text background.
        glyph=Image.new('L',region.size)
        ImageDraw.Draw(glyph).text((x-b[0]-bounds[0],y-b[1]-bounds[1]),value,font=f,fill=255)
        self.texts.append({'text':value,'su':su,'font_px':f.size,'ink_height_px':b[3]-b[1],
                           'color':color,'background_worst_contrast':contrast_worst(rgb(color),region,glyph),
                           'xy':[x,y], 'regular':regular,
                           'panel':next((p['kind'] for p in reversed(self.panels) if p['box'][0]<=x<=p['box'][2] and p['box'][1]<=y<=p['box'][3]),None)})
        d.text((x-b[0],y-b[1]),value,font=f,fill=rgb(color)+(255,))
    def chip(self,xy,team,size=24):
        x,y=xy;s=size*self.scale;r=s/2;d=ImageDraw.Draw(self.im);color=rgb(f'team.p{team}.screen')+(255,)
        if team==1:d.ellipse([x-r,y-r,x+r,y+r],fill=color)
        else:d.regular_polygon((x,y,r),6,rotation=30,fill=color)

def lum(v):
    v=np.asarray(v,dtype=float)/255
    return np.where(v<=.04045,v/12.92,((v+.055)/1.055)**2.4)@np.array([.2126,.7152,.0722])
def contrast_worst(fg,bg,glyph=None):
    if bg.width==0 or bg.height==0:return None
    f=lum(fg);b=lum(np.asarray(bg));r=(np.maximum(f,b)+.05)/(np.minimum(f,b)+.05)
    if glyph is not None:
        r=r[np.asarray(glyph)>=128]
        if not r.size:return None
    return round(float(r.min()),4)

def masks(board,w,h):
    geo=GEOMETRY[board]; sx=w/1920;sy=h/1080
    out={n:Image.new('1',(w,h)) for n in ['figures','spaces','field','seams']}
    def rect(b):return [round(b[0]*sx),round(b[1]*sy),round(b[2]*sx),round(b[3]*sy)]
    d=ImageDraw.Draw(out['figures'])
    for b in geo['figures'].values():d.rectangle(rect(b),fill=1)
    d=ImageDraw.Draw(out['spaces'])
    for x,y,rx,ry in geo['spaces']:d.ellipse(rect([x-rx,y-ry,x+rx,y+ry]),fill=1)
    ImageDraw.Draw(out['field']).rectangle(rect(geo['field']),fill=1)
    d=ImageDraw.Draw(out['seams'])
    for b in geo['seams']:
        pts=rect(b);d.line([(pts[0],pts[1]),(pts[2],pts[3])],fill=1,width=max(2,round(4*sx)))
    return out
def overlap(a,b):return int(np.count_nonzero(np.asarray(a,dtype=bool)&np.asarray(b,dtype=bool)))

def tag(c,actor,hp,xy,key,maskset=None):
    s=c.scale;x,y=xy;digit=actor.get('digit');width=144 if digit else 126;height=40
    box=[x-width*s/2,y,x+width*s/2,y+height*s]
    c.panel(box,'tag.'+key,rad=8,onboard=True)
    x=box[0]+12*s;c.chip((x+12*s,y+20*s),actor['team'])
    x+=25*s
    if digit:
        d=ImageDraw.Draw(c.im);d.ellipse([x,y+12*s,x+16*s,y+28*s],fill=rgb('card.navy')+(255,),outline=rgb('card.cream')+(255,),width=max(1,round(s)))
        c.text((x+8*s,y+20*s),str(digit),14,'card.cream',center=True,cap=10)
        x+=22*s
    d=ImageDraw.Draw(c.im);d.rectangle([x,y+18*s,x+40*s,y+22*s],fill=rgb('hp.back')+(255,))
    d.rectangle([x,y+18*s,x+40*s*hp/actor['startHealth'],y+22*s],fill=rgb('hp.fill')+(255,))
    c.text((x+44*s,y+13*s),f"{hp}/{actor['startHealth']}")
    return box

def place_tag(board,key,w,h,s,maskset,existing):
    cache_key=(board,key,w,h,s)
    if cache_key in ANCHOR_CACHE:
        x,y=ANCHOR_CACHE[cache_key];width=(144 if key.startswith('harpy') else 126)*s
        m=Image.new('1',(w,h));ImageDraw.Draw(m).rounded_rectangle([x-width/2-s,y-s,x+width/2+s,y+41*s],radius=9*s,fill=1)
        existing.append(m);return x,y
    x,y=GEOMETRY[board]['bases'][key];sx=w/1920;sy=h/1080
    fig=GEOMETRY[board]['figures'][key];width=(144 if key.startswith('harpy') else 126)*s
    # Start below the WHOLE base; move minimally if the larger DPI label hits a neighbour.
    center=x*sx;top=(fig[3]+7)*sy
    candidates=[]
    for dy in range(0,181,6):
        for dx in [0,-12,12,-24,24,-36,36,-48,48,-60,60,-72,72,-84,84,-96,96,-108,108,-120,120,-132,132,-144,144,-156,156,-168,168,-180,180,-192,192,-204,204,-216,216,-228,228,-240,240]:
            bx=[center+dx-width/2,top+dy,center+dx+width/2,top+dy+40*s]
            if bx[0]<12 or bx[2]>w-12 or bx[3]>h-12:continue
            crop=[math.floor(bx[0]-s),math.floor(bx[1]-s),math.ceil(bx[2]+s)+1,math.ceil(bx[3]+s)+1]
            if any(maskset[n].crop(crop).getbbox() for n in ['figures','seams']):continue
            if any(e.crop(crop).getbbox() for e in existing):continue
            m=Image.new('1',(w,h));ImageDraw.Draw(m).rounded_rectangle([bx[0]-s,bx[1]-s,bx[2]+s,bx[3]+s],radius=9*s,fill=1)
            candidates.append((dy*2+abs(dx),center+dx,top+dy,m))
        # Later rows cannot improve the current weighted nearest-position score
        # once their vertical cost alone exceeds its best value.
        if candidates and (dy+6)*2>=min(q[0] for q in candidates):break
    if not candidates:raise RuntimeError('No collision-free tag anchor '+board+' '+key)
    _,x,y,m=min(candidates,key=lambda q:q[0]);existing.append(m)
    ANCHOR_CACHE[cache_key]=(x,y)
    return x,y


if __name__ == "__main__":
    import hb44_fix1
    import hb44_fix2
    hb44_fix2.install(sys.modules[__name__], hb44_fix1)
    sys.stdout.reconfigure(encoding="utf-8")
    hb44_fix1.run(sys.modules[__name__])
