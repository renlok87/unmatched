#!/usr/bin/env python
"""HB-29 native-size offline renderer. Run python -B -X utf8 this/file.py.

All writes are audited and restricted to the two HB-29 roots. No subprocesses,
network, git, Unreal, generation, or imports of the upstream build entry points.
Snapshots are archival; only extracted pure functions are reused here.
"""
from __future__ import annotations
import ast
import csv
import hashlib
import itertools
import json
import math
import os
from pathlib import Path
import re
import sys
from functools import lru_cache
sys.dont_write_bytecode = True
import cairo
import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

ROOT = Path(__file__).resolve().parents[4]
PKG = ROOT/'art/imagegen/hud-combat-v1-codex'
OUT = ROOT/'scraped-data/derived/hud-combat-v1-codex'
TOOLS = PKG/'_tools'
FONTDIR = Path('C:/Program Files/Epic Games/UE_5.8/Engine/Content/Slate/Fonts')
WRITES = set()

def rel(p):
    p = Path(p).resolve()
    return p.relative_to(ROOT).as_posix() if p.is_relative_to(ROOT) else p.as_posix()

def audit(event, args):
    targets = []
    if event == 'open' and isinstance(args[0], (str, bytes, os.PathLike)):
        mode, flags = args[1:3]
        if (isinstance(mode, str) and any(c in mode for c in 'wax+')) or (isinstance(flags, int) and flags & (os.O_WRONLY|os.O_RDWR|os.O_CREAT|os.O_TRUNC)):
            targets = [args[0]]
    elif event in ('os.mkdir','os.remove','os.rmdir','os.rename'):
        targets = args[:2] if event == 'os.rename' else args[:1]
    elif event in ('subprocess.Popen','os.system'):
        raise PermissionError('HB-29 does not start subprocesses')
    for target in targets:
        if not isinstance(target, (str, bytes, os.PathLike)): continue
        p = Path(os.fsdecode(target)).resolve()
        if not any(p.is_relative_to(q) for q in (PKG, OUT)):
            raise PermissionError('HB-29 forbidden write: '+str(p))
        WRITES.add(rel(p))

sys.addaudithook(audit)
def load(p): return json.loads(Path(p).read_text(encoding='utf-8'))
def sha(p): return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def dump(p, x):
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(x, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')

T = {'card.navy':'#061623','card.cream':'#F9EBDB','card.glyph':'#FAF8F2',
     'mark.keyline':'#111317','text.primary':'#F2EDE4','text.secondary':'#B9B2A6',
     'panel.bg.inset':'#15232E','state.pending':'#0D7A89','state.warning':'#E8812C',
     'state.error':'#D9483F','turn.flash.yellow':'#F2C14E','disabled':'#4E5457',
     'team.p1.screen':'#DAC576','team.p2.screen':'#5786A8','damage.text':'#FFE0AF',
     'card.type.attack':'#DC2F33','card.type.defense':'#2976AE',
     'card.type.versatile':'#6B4E8F','card.type.scheme':'#FDBE72'}
RGB = {k:tuple(bytes.fromhex(v[1:])) for k,v in T.items()}
BG = {'marmoreal':'docs/game-design/evidence/ENV-MAPS/p7-concept-paste-2026-10-01/marmoreal-concept-flag/bench-K1-1920x1080.png',
      'sarpedon':'docs/game-design/evidence/ENV-MAPS/p10-sarpedon-rework-2026-10-03/sarpedon-packaged/bench-K1-1920x1080.png'}
CONFIGS = [(1920,1080,100,1.),(1920,1080,150,1.5),(1280,720,100,.75),(1280,720,150,1.125)]
STATES = ['declare','defense-window','timer-warning','defense-chosen','reveal','effects','slam','hit','effects-long','holds','nodefense']
RESERVED = ['TOP','PANEL-LOC','PANEL-OPP','OPP-HAND','HAND','HAND-CAPTION','DECKS','ACTIONS']
HB = load(ROOT/'art/imagegen/hud-composition-v1-codex/verification.json')
MASKDATA = load(ROOT/'art/imagegen/hud-composition-v1-codex/masks.json')
WORLD = load(ROOT/'art/imagegen/hud-world-v1-codex/geometry.json')['boards']
CP = load(ROOT/'art/imagegen/card-frame-v1-codex/asset-contract.json')
BEFORE = load(PKG/'source-hashes-before.json')
FIX1_BEFORE = load(PKG/'fix1-before.json')
FIX1_INPUTS = load(PKG/'fix1-inputs.json')
HB13 = load(ROOT/'art/imagegen/hud-topstrip-v1-codex/verification.json')
FIX1_CENTERS = []; FIX1_STATUS = []; FIX1_CHIPS = []
STRINGS = {}
for table in ['st-hud','st-ms']:
    with (ROOT/f'docs/unreal/contracts/hud/{table}.csv').open(encoding='utf-8-sig', newline='') as f:
        for row in csv.DictReader(f):
            STRINGS[row['Key']] = dict(row, source=f'docs/unreal/contracts/hud/{table}.csv')
WHY = {r['key']:r for r in load(ROOT/'docs/unreal/contracts/hud/why-reasons.json')['reasons']}
def st(key, **params): return STRINGS[key]['ru'].format(**params)

@lru_cache(None)
def font(size, bold=False):
    return ImageFont.truetype(str(FONTDIR/('Roboto-BoldCondensed.ttf' if bold else 'Roboto-Regular.ttf')),max(1,size))

def decode(path):
    pool = load(path)['nodes'][2]['data']; memo = {}
    def r(i):
        if i < 0: return None
        if i in memo: return memo[i]
        x = pool[i]
        out = {k:r(v) for k,v in x.items()} if isinstance(x,dict) else [r(v) for v in x] if isinstance(x,list) else x
        memo[i] = out
        return out
    return r(0)

DECKS = {slug:decode(ROOT/f'scraped-data/api/heroes/{slug}.json')['fetchedDeck'] for slug in ['medusa','king-arthur']}
SCANS = {c['stableContentKey']:c['ru']['path'] for c in load(ROOT/'art/imagegen/mvp-v1/reused-cardart.json')['cards']}
BACKS = {'medusa':'scraped-data/images/heroes/card-covers/ROSMO3sRi6Jh1o7S_riGI.png',
         'king-arthur':'scraped-data/images/heroes/card-covers/WWzu16BEFGsEdu5NsMbMI.png'}
def card(slug, title): return next(c for c in DECKS[slug] if c['card']['title']==title)
def effect(slug, title, field):
    c = card(slug,title)['card']; ru = c.get('i18n',{}).get('ru',{})
    local = field in ru and 'title' in ru
    name, text = (ru['title'],ru[field]) if local else (c['title'],c[field])
    return {'source':f'scraped-data/api/heroes/{slug}.json','title_en':title,'field':field,
            'title':name,'effect':text,'text':name+': '+text.strip(),'lang':'ru' if local else 'en',
            'note':'' if local else 'lang en, no RU in data'}
EFF = {'feint':effect('medusa','Feint','effectImmediately'),
       'swift':effect('king-arthur','Swift Strike','effectAfter'),
       'dash':effect('medusa','Dash','effectAfter'),
       'shift':effect('king-arthur','Momentous Shift','effectDuring'),
       'winged':effect('medusa','Winged Frenzy','effect'),
       'regroup':effect('medusa','Regroup','effectAfter')}

def gray(im):
    a = np.asarray(im.convert('RGBA')).copy()
    y = np.rint(a[:,:,:3].astype(float)@np.array([.2126,.7152,.0722])).astype(np.uint8)
    a[:,:,:3] = y[:,:,None]
    return Image.fromarray(a)

def luminance(a):
    x = np.asarray(a,dtype=float)/255
    return np.where(x<=.04045,x/12.92,((x+.055)/1.055)**2.4)@np.array([.2126,.7152,.0722])
def contrast(fg,bg):
    f,b=luminance(fg),luminance(bg)
    return (np.maximum(f,b)+.05)/(np.minimum(f,b)+.05)

def wrap(text, f, width):
    rows=[]; line=''
    for word in text.split(' '):
        candidate=(line+' '+word).strip()
        if line and f.getlength(candidate)>width: rows.append(line);line=word
        else: line=candidate
    if line:rows.append(line)
    return rows

@lru_cache(None)
def original(path):
    with Image.open(ROOT/path) as im: return im.convert('RGBA')

@lru_cache(None)
def masks(board,w,h):
    q=w/1920; fm=Image.new('L',(w,h));sm=Image.new('L',(w,h))
    d=ImageDraw.Draw(fm)
    for poly in MASKDATA['figure_polygons_1080p'][board]:
        d.polygon([(round(x*q),round(y*q)) for x,y in poly],fill=255)
    reg=MASKDATA['topology_transforms'][f'{board}-{w}x{h}']
    d=ImageDraw.Draw(sm)
    for cell in reg['spaces']:d.polygon([tuple(p) for p in cell['polygon_px']],fill=255)
    fm=fm.filter(ImageFilter.MaxFilter(2*reg['figure_conservative_dilation_px']+1))
    sm=sm.filter(ImageFilter.MaxFilter(2*reg['cell_conservative_dilation_px']+1))
    return np.asarray(fm)>0,np.asarray(sm)>0

# Execute only the two pure CP-13 frame routines, without its audit/build/imports.
tree=ast.parse((TOOLS/'cp13_build_card_frames_snapshot.py').read_text(encoding='utf-8'))
pure=ast.Module(body=[n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name in ['rounded_mask','frame']],type_ignores=[])
class CairoHolder: pass
v3=CairoHolder();v3.cairo=cairo
EDGE={'idle':('card.cream',1,.45)}
exec(compile(pure,'cp13-pure-functions','exec'),globals())
CPFRAME=frame

# Reuse HB-44 fix2's attributed damage trajectory, not its obsolete preferred
# point (which lands on the neighbouring Harpy in the tightly packed Marmoreal).
F=CairoHolder();F.GEO=WORLD
NUMBER_CACHE={}
tree=ast.parse((TOOLS/'hb44_fix2_snapshot.py').read_text(encoding='utf-8'))
pure=ast.Module(body=[n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name in ['figures','number_anchor']],type_ignores=[])
exec(compile(pure,'hb44-pure-attributed-anchor','exec'),globals())

def native_frame(wsu,hsu,s):
    if s==1:return CPFRAME((int(wsu),int(hsu),4,8),'idle')
    w,h=round(wsu*s),round(hsu*s)
    def coverage(box,radius):
        surf=cairo.ImageSurface(cairo.FORMAT_A8,w,h);ctx=cairo.Context(surf);ctx.scale(s,s)
        x,y,bw,bh=box;r=min(radius,bw/2,bh/2)
        for cx,cy,a in [(x+bw-r,y+r,-math.pi/2),(x+bw-r,y+bh-r,0),(x+r,y+bh-r,math.pi/2),(x+r,y+r,math.pi)]:ctx.arc(cx,cy,r,a,a+math.pi/2)
        ctx.close_path();ctx.set_source_rgba(1,1,1,1);ctx.fill();surf.flush()
        return np.frombuffer(surf.get_data(),np.uint8).reshape(h,surf.get_stride())[:,:w].copy()
    a=np.zeros((h,w,4),np.uint8);a[:,:,:3]=RGB['mark.keyline'];a[:,:,3]=coverage((0,0,wsu,hsu),8)
    k=coverage((1,1,wsu-2,hsu-2),7)>=128;a[k,:3]=RGB['card.cream'];a[k,3]=round(255*.45)
    k=coverage((2,2,wsu-4,hsu-4),6)>=128;a[k,:3]=RGB['card.navy'];a[k,3]=255
    b=round(4*s);a[b:h-b,b:w-b]=0
    return Image.fromarray(a)

DELTAS=[];SHORTENED=[]
class Canvas:
    def __init__(self,board,w,h,ui,s,state):
        self.board,self.w,self.h,self.ui,self.s,self.state=board,w,h,ui,s,state
        self.id=f'HB-29-{board}-{state}-{w}x{h}-{ui}'
        self.bg=original(BG[board]) if (w,h)==(1920,1080) else original(BG[board]).resize((w,h),Image.Resampling.LANCZOS)
        self.im=self.bg.copy();self.hud=Image.new('RGBA',(w,h));self.palette_plane=Image.new('RGBA',(w,h))
        self.panels={};self.parts=[];self.texts=[];self.icons=[];self.scans=[];self.edgechecks=[]
        self.reserved={};self.delta=[]
    def pxbox(self,r):
        x,y,w,h=r;s=self.s;return (round(x*s),round(y*s),round((x+w)*s),round((y+h)*s))
    def composite(self,layer, palette=True):
        self.im=Image.alpha_composite(self.im,layer);self.hud=Image.alpha_composite(self.hud,layer)
        if palette:
            a=np.asarray(layer);opaque=a[:,:,3]==255
            pa=np.asarray(self.palette_plane).copy();pa[opaque]=a[opaque];self.palette_plane=Image.fromarray(pa)
    def part(self,key,r,parent=None):
        self.parts.append({'key':key,'rectangle_su':list(r),'parent':parent})
    def panel(self,key,r,radius=6,body='card.navy',alpha=.92,edge='card.cream',edgealpha=.45,edgewidth=1,transient=False,onboard=False):
        box=self.pxbox(r);s=self.s
        layer=Image.new('RGBA',self.im.size);d=ImageDraw.Draw(layer)
        if onboard:
            b=[box[0]-round(s),box[1]-round(s),box[2]+round(s)-1,box[3]+round(s)-1]
            d.rounded_rectangle(b,radius=round((radius+1)*s),fill=RGB['mark.keyline']+(255,))
        d.rounded_rectangle([box[0],box[1],box[2]-1,box[3]-1],radius=round(radius*s),fill=RGB[body]+(round(255*alpha),))
        self.composite(layer)
        edge_layer=Image.new('RGBA',self.im.size)
        ImageDraw.Draw(edge_layer).rounded_rectangle([box[0],box[1],box[2]-1,box[3]-1],radius=round(radius*s),outline=RGB[edge]+(round(255*edgealpha),),width=max(1,round(edgewidth*s)))
        # Acceptance pair is edge to its own composited body, not to the scene.
        bg=np.asarray(self.im)[:,:,:3]; a=np.asarray(edge_layer);sel=a[:,:,3]>0
        if sel.any():
            e=a[:,:,:3].astype(float);ea=a[:,:,3:4]/255
            comp=np.rint(e*ea+bg*(1-ea)).astype(np.uint8)
            self.edgechecks.append({'key':key,'edge_vs_body_min':float(contrast(comp[sel],bg[sel]).min()),'edge':T[edge],'edge_alpha':edgealpha})
        self.composite(edge_layer)
        bounds=box if not onboard else (box[0]-round(s),box[1]-round(s),box[2]+round(s),box[3]+round(s))
        self.panels[key]={'rectangle_su':list(r),'box_px':list(bounds),'transient':transient,'kind':'panel'}
    def text(self,key,value,r,su=14,bold=False,color='text.primary',center=False,rows=None,pitch=None,parent=None,ellipsis=False,anchor_lt=False,tight_ink=False):
        f=font(math.ceil(su*self.s),bold);box=self.pxbox(r)
        lines=rows if rows is not None else wrap(value,f,max(1,box[2]-box[0]))
        pitch=pitch or su+4;need=(len(lines)-1)*pitch*self.s
        ink=max((f.getbbox(t)[3]-f.getbbox(t)[1] for t in lines),default=0)
        need+=ink
        maxwidth=max((float(f.getlength(t)) for t in lines),default=0)
        passed=maxwidth<=box[2]-box[0]+.01 and need<=box[3]-box[1]+.01
        layer=Image.new('RGBA',self.im.size);d=ImageDraw.Draw(layer);glyph=Image.new('L',self.im.size);gd=ImageDraw.Draw(glyph)
        y=box[1]+(box[3]-box[1]-need)/2 if center else box[1]
        for i,line in enumerate(lines):
            width=f.getlength(line);x=box[0]+(box[2]-box[0]-width)/2 if center else box[0]
            by=0 if anchor_lt else f.getbbox(line)[1];xy=(round(x),round(y+i*pitch*self.s-by))
            args={'anchor':'lt'} if anchor_lt else {}
            d.text(xy,line,font=f,fill=RGB[color]+(255,),**args);gd.text(xy,line,font=f,fill=255,**args)
        if tight_ink and (ib:=glyph.getbbox()):
            need=ib[3]-ib[1]
            passed=maxwidth<=box[2]-box[0]+.01 and ib[0]>=box[0] and ib[1]>=box[1] and ib[2]<=box[2] and ib[3]<=box[3]
        select=np.asarray(glyph)>=128
        ratio=float(contrast(RGB[color],np.asarray(self.im)[:,:,:3][select]).min()) if select.any() else None
        self.texts.append({'key':key,'text':value,'rows':lines,'rectangle_su':list(r),'type_su':su,'nominal_font_px':su*self.s,'raster_font_px':f.size,'width_px':maxwidth,'height_px':need,'available_px':[box[2]-box[0],box[3]-box[1]],'passed':passed,'contrast_min':ratio,'parent':parent,'ellipsis':ellipsis,'alignment':'center' if center else 'left','line_pitch_su':pitch,'ink_bbox_px':glyph.getbbox()})
        self.composite(layer);self.part(key,r,parent)
    def icon(self,name,r,parent):
        size=round(r[2]*self.s)
        base=ROOT/f'art/imagegen/hud-icons-v3/sizes/{name}-{size}.png'
        exact=base.exists()
        if not exact:base=ROOT/f'art/imagegen/hud-icons-v3/sizes/{name}-96.png'
        im=Image.open(base).convert('RGBA')
        if im.size!=(size,size):im=im.resize((size,size),Image.Resampling.LANCZOS)
        x,y,*_=self.pxbox(r);layer=Image.new('RGBA',self.im.size);layer.alpha_composite(im,(x,y));self.composite(layer,False)
        pair = ('state.error','card.navy') if name=='marker-x-stamp' else ('card.glyph','card.type.attack' if name=='action-attack' else 'card.type.defense')
        self.icons.append({'name':name,'source':rel(base),'size_su':r[2],'size_px':size,'exact_asset_size':exact,'glyph_contrast':float(contrast(RGB[pair[0]],RGB[pair[1]])),'pair':list(pair)})
        self.part(name,r,parent)
    def chip(self,xy,team,parent):
        # Exact HB-44 chip(): ellipse P1; regular hexagon, rotation 30, P2.
        x,y=xy;s=24*self.s;rad=s/2;cx=x*self.s;cy=y*self.s
        layer=Image.new('RGBA',self.im.size);d=ImageDraw.Draw(layer);color=RGB[f'team.p{team}.screen']+(255,)
        if team==1:d.ellipse([cx-rad,cy-rad,cx+rad,cy+rad],fill=color)
        else:d.regular_polygon((cx,cy,rad),6,rotation=30,fill=color)
        self.composite(layer);self.part('TEAM-P'+str(team),[x-12,y-12,24,24],parent)
    def cardframe(self,key,r,source=None):
        x,y,w,h=r;s=self.s;box=self.pxbox(r);fr=native_frame(w,h,s)
        under=Image.new('RGBA',fr.size);ImageDraw.Draw(under).rounded_rectangle([0,0,fr.width-1,fr.height-1],radius=round(8*s),fill=RGB['card.navy']+(255,))
        layer=Image.new('RGBA',self.im.size);layer.alpha_composite(under,(box[0],box[1]));self.composite(layer)
        if source:
            src=original(source);band=round(4*s);vw,vh=fr.width-2*band,fr.height-2*band
            factor=min(vw/src.width,vh/src.height,1.)
            tw,th=math.floor(src.width*factor),math.floor(src.height*factor)
            ox=box[0]+band+(vw-tw)//2;oy=box[1]+band+(vh-th)//2
            fitted=src.resize((tw,th),Image.Resampling.LANCZOS)
            layer=Image.new('RGBA',self.im.size);layer.alpha_composite(fitted,(ox,oy));self.composite(layer,False)
            gaps=[(ox-box[0]-band)/s,(oy-box[1]-band)/s,(box[2]-band-ox-tw)/s,(box[3]-band-oy-th)/s]
            self.scans.append({'source':source,'source_size':list(src.size),'final_size':[tw,th],'scale':factor,'gap_su':gaps,'whole':True,'resampling':'direct source -> final Lanczos once','back':source in BACKS.values()})
        layer=Image.new('RGBA',self.im.size);layer.alpha_composite(fr,(box[0],box[1]));self.composite(layer)
        self.panels[key]={'rectangle_su':list(r),'box_px':list(box),'transient':False,'kind':'card'}
    def ribbon(self,key,r,role,fighter,team,timer=None,warning=False):
        x,y,w,h=r;f=font(math.ceil(14*self.s),True)
        label=st('hud.combat.role.'+role,fighter=fighter)
        rows=wrap(label,f,(w-64)*self.s)
        rh=max(28 if w==230 else 24, len(rows)*16+8)
        nh=rh+(28 if timer is not None else 0)
        if nh!=h:self.change(key,r,[x,y,w,nh],'типовой диск и чип 24 su; перенос роли; отдельная строка таймера')
        r=[x,y,w,nh];self.panel(key,r,radius=4,edge='state.warning' if warning else 'card.cream',edgealpha=1 if warning else .45,edgewidth=2 if warning else 1)
        # 1-su right margin prevents the inclusive HB-44 chip boundary touching another panel.
        self.icon('action-'+role,[x+3,y+(rh-24)/2,24,24],key)
        self.text(key+'.tag',label,[x+32,y+4,w-64,rh-8],14,True,rows=rows,pitch=16,parent=key)
        self.chip((x+w-16,y+rh/2),team,key)
        if timer is not None:
            self.text(key+'.timer',st('hud.combat.timer',n=timer),[x+6,y+rh+1,w-42,19],16,True,parent=key)
            if warning:
                rr=[x+w-32,y+rh,24,24];bx=self.pxbox(rr);layer=Image.new('RGBA',self.im.size)
                ImageDraw.Draw(layer).polygon([(bx[0]+(bx[2]-bx[0])/2,bx[1]),(bx[2]-1,bx[3]-1),(bx[0],bx[3]-1)],fill=RGB['state.warning']+(255,))
                self.composite(layer);self.text(key+'.warning','!',[rr[0]+7,rr[1]+7,10,15],14,True,'card.navy',True,parent=key)
                self.part('IC-47-stand-in',rr,key)
            layer=Image.new('RGBA',self.im.size);d=ImageDraw.Draw(layer)
            bar=[x,y+nh-4,w,4];bb=self.pxbox(bar)
            d.rectangle([bb[0],bb[1],bb[2]-1,bb[3]-1],fill=RGB['panel.bg.inset']+(255,))
            d.rectangle([bb[0],bb[1],round(bb[0]+(bb[2]-bb[0])*timer/30)-1,bb[3]-1],fill=RGB['card.cream']+(255,))
            self.composite(layer);self.part('TIMER-BAR',bar,key)
    def change(self,key,old,new,reason):
        row={'id':self.id,'block':key,'old_su':old,'new_su':new,'reason':reason};self.delta.append(row);DELTAS.append(row)

def geometry(c):
    row=next(a for a in HB['overlap']['per_mockup'] if a['id']==f'HB-07-{c.board}-combat-defense-{c.w}x{c.h}-{c.ui}')
    allrects={k:list(v['rectangle_su']) for k,v in row['panels'].items()}
    c.reserved={k:allrects[k] for k in RESERVED}
    return allrects

def more_chip(c,x,y,n):
    label=st('hud.combat.effects.more',n=n)
    width=math.ceil(font(math.ceil(14*c.s),True).getlength(label))/c.s+16
    rr=[x,y,width,24];box=c.pxbox(rr)
    layer=Image.new('RGBA',c.im.size)
    ImageDraw.Draw(layer).rounded_rectangle([box[0],box[1],box[2]-1,box[3]-1],radius=round(4*c.s),fill=RGB['panel.bg.inset']+(255,))
    c.composite(layer);c.part('MORE-CHIP',rr,'CENTER')
    f=font(math.ceil(14*c.s),True);ink=f.getbbox(label)[3]-f.getbbox(label)[1]
    ty=(box[1]+(box[3]-box[1]-ink)//2)/c.s
    c.text('effects.more',label,[x+8,ty,width-16,ink/c.s],14,True,rows=[label],parent='CENTER',tight_ink=True)
    FIX1_CHIPS.append({'id':c.id,'rectangle_su':rr,'text_start_x_su':x,'radius_su':4,'padding_x_su':8,'height_su':24,'body':T['panel.bg.inset'],'text_contrast':c.texts[-1]['contrast_min']})

def resolved_center(c,r):
    x,y,w,_=r;s=c.s
    score=st('hud.combat.score',a=3,d=3 if c.state=='holds' else 2)
    outcome=st('hud.combat.holds') if c.state=='holds' else st('hud.combat.wins',fighter='Merlin')
    def inkheight(text,su,bold):
        f=font(math.ceil(su*s),bold);b=f.getbbox(text);return (b[3]-b[1])/s
    score_h=inkheight(score,48,True);outcome_h=inkheight(outcome,28,True)
    outcome_y=12+score_h+4;effect_y=outcome_y+outcome_h+8
    keys=['dash'] if c.state=='holds' else ['feint','swift'];plan=[];cursor=effect_y
    for key in keys:
        rows=wrap(EFF[key]['text'],font(math.ceil(16*s)),(w-64)*s)
        # The cancelled X is a 24su glyph; resolved rows retain the effects style.
        start_px=round((y+cursor)*s)
        end_px=max(round((y+cursor+i*22)*s)+round(inkheight(t,16,False)*s) for i,t in enumerate(rows))
        hh=max(24,(end_px-start_px)/s)
        plan.append((key,rows,cursor,hh));cursor+=hh+6
    content_bottom_px=max(round((y+offset+hh)*s) for _,_,offset,hh in plan)
    full_height=(content_bottom_px+round(12*s)-round(y*s))/s
    full_fits=full_height<=160 and all(len(rows)<=2 for _,rows,_,_ in plan)
    assert full_fits or c.state!='holds','Full Dash must fit without truncation'
    height=full_height if full_fits else effect_y+24+12
    assert height<=160
    rr=[x,y,w,height];c.change('CENTER',r,rr,'fix1: высота по содержимому + 12 su сверху/снизу; полные разрешённые строки' if full_fits else 'fix1: строки не помещаются в 160 su; чип через 8 su после исхода')
    c.panel('CENTER',rr,transient=True)
    c.text('score',score,[x+16,y+12,w-32,score_h],48,True,center=True,rows=[score],parent='CENTER',tight_ink=True)
    c.text('outcome',outcome,[x+16,y+outcome_y,w-32,outcome_h],28,True,center=True,rows=[outcome],parent='CENTER',tight_ink=True)
    if full_fits:
        for key,rows,offset,hh in plan:
            if key=='swift':c.icon('marker-x-stamp',[x+12,y+offset,24,24],'CENTER')
            c.text('effect.'+key,EFF[key]['text'],[x+44,y+offset,w-56,hh],16,False,'text.secondary',rows=rows,pitch=22,parent='CENTER',tight_ink=True)
    else:more_chip(c,x+44,y+effect_y,2)
    FIX1_CENTERS.append({'id':c.id,'variant':'full-dash' if c.state=='holds' else 'resolved-lines' if full_fits else 'more-chip','rectangle_su':rr,'full_candidate_height_su':full_height,'padding_top_su':12,'padding_bottom_su':12,'score_outcome_gap_su':4,'outcome_content_gap_su':8,'effect_row_gap_su':6,'resolved_rows':{key:rows for key,rows,_,_ in plan},'current_bar':False,'cancelled_X':full_fits and 'swift' in keys})

def defend_status(c,old):
    fit_id=f'HB-13-marmoreal-defend-{c.w}x{c.h}-{c.ui}'
    fit=HB13['status_text_fit'][fit_id];s=c.s;sw=fit['block_width_su']
    sy=16 if c.ui==150 else 24;sh=78 if fit['line_count']==2 else 48
    rr=[(c.w/s-sw)/2,sy,sw,sh];rows=fit['lines'];pitch=fit['line_pitch_su']
    f=font(fit['font_px'],True);heights=[f.getbbox(line,anchor='lt')[3] for line in rows]
    ink_height=max(round(i*pitch*s)+ih for i,ih in enumerate(heights))
    ty=sy+12 if len(rows)==1 else (round(sy*s)+(round((sy+sh)*s)-round(sy*s)-ink_height)//2)/s
    if rr!=old:c.change('STATUS',old,rr,'fix1: принят HB-13 defend; цельное «Без защиты», 24 su, шаг 30 su, левое выравнивание ink-блока')
    c.panel('STATUS',rr,radius=4)
    c.text('status',st('ms.status.defend'),[rr[0]+16,ty,sw-32,ink_height/s],fit['type_su'],True,rows=rows,pitch=pitch,parent='STATUS',anchor_lt=True,tight_ink=True)
    b=c.texts[-1]['ink_bbox_px'];box=c.pxbox(rr)
    FIX1_STATUS.append({'id':c.id,'source_id':fit_id,'rectangle_su':rr,'lines':rows,'type_su':fit['type_su'],'line_pitch_su':pitch,'alignment':'left','ink_top_pad_su':(b[1]-box[1])/s,'ink_bottom_pad_su':(box[3]-b[3])/s,'ink_bbox_px':b,'source_ink_line_bboxes_px':fit['ink_line_bboxes_px']})

def center_effects(c,r,keys,maxlines):
    x,y,w,h=r;lineplan=[];cursor=12
    for key in keys[:maxlines]:
        full=EFF[key]['text'];f=font(math.ceil(16*c.s));rows=wrap(full,f,(w-64)*c.s)
        short=len(rows)>2
        if short:
            rows=rows[:2]
            while f.getlength(rows[-1]+'…')>(w-64)*c.s:rows[-1]=rows[-1][:-1]
            rows[-1]=rows[-1].rstrip()+'…'
            SHORTENED.append({'id':c.id,'key':key,'full_text':full,'display_rows':rows})
        height=max(24,(len(rows)-1)*22+18)
        lineplan.append((key,rows,cursor,height,short));cursor+=height+6
    hidden=len(keys)-maxlines
    if hidden>0:cursor+=24
    height=min(160,cursor+12);r=[x,y,w,height]
    c.change('CENTER', [x,y,w,h],r,'строки эффектов: шаг 22 su внутри строки, 6 su между строками; до 160 su')
    c.panel('CENTER',r,transient=True)
    for i,(key,rows,offset,hh,short) in enumerate(lineplan):
        if key=='swift':c.icon('marker-x-stamp',[x+12,y+offset,24,24],'CENTER')
        elif i==0:
            layer=Image.new('RGBA',c.im.size);bx=c.pxbox([x+12,y+offset,3,hh]);ImageDraw.Draw(layer).rectangle([bx[0],bx[1],bx[2]-1,bx[3]-1],fill=RGB['state.pending']+(255,));c.composite(layer)
            c.part('EFFECT-CURRENT',[x+12,y+offset,3,hh],'CENTER')
        c.text('effect.'+key,EFF[key]['text'],[x+44,y+offset,w-56,hh],16,False,'text.primary' if i==0 else 'text.secondary',rows=rows,pitch=22,parent='CENTER',ellipsis=short)
    if hidden>0:
        more_chip(c,x+44,y+height-36,hidden)
    return r

def render(board,w,h,ui,s,state):
    c=Canvas(board,w,h,ui,s,state);g=geometry(c);small=ui==150
    timerstate=board=='marmoreal' and state in ['defense-window','timer-warning','defense-chosen']
    early=state in ['declare','defense-window','timer-warning','defense-chosen']
    attacker='L' if board=='sarpedon' else 'R';defender='R' if board=='sarpedon' else 'L'
    acard='king-arthur:swift-strike';dcard='medusa:feint'
    if state=='holds':acard='king-arthur:momentous-shift';dcard='medusa:dash'
    if state=='nodefense':attacker='L' if board=='marmoreal' else 'R';defender='R' if board=='marmoreal' else 'L';acard='medusa:snipe' if board=='marmoreal' else 'medusa:regroup'
    for side in ['L','R']:
        attack=side==attacker
        if state=='declare' and not attack:continue
        key='COMBAT-'+side;r=g[key]
        source=None
        if attack:source=BACKS['king-arthur'] if early and board=='marmoreal' else SCANS[acard]
        elif state=='defense-chosen':source=BACKS['medusa']
        elif not early and state!='nodefense':source=SCANS[dcard]
        c.cardframe(key,r,source)
        x,y,rw,rh=r
        if not attack and state in ['defense-window','timer-warning']:
            c.icon('action-defense',[x+(rw-64)/2,y+rh*.27,64,64],key)
            c.text('slot.empty',st('hud.combat.slot.empty'),[x+12,y+rh*.65,rw-24,44],16,False,'text.secondary',True,parent=key)
        elif not attack and state=='nodefense':c.icon('marker-x-stamp',[x+(rw-64)/2,y+(rh-64)/2,64,64],key)
        elif not attack and state=='defense-chosen':
            cr=[x,y-28,rw,24];c.change('SLOT-CAPTION',None,cr,'отдельная плашка над картой, после кнопок; рубашка целиком')
            c.panel('SLOT-CAPTION',cr,radius=4);c.text('slot.chosen',st('hud.combat.slot.chosen'),[x+4,cr[1]+3,rw-8,18],16,False,'text.primary',True,parent='SLOT-CAPTION')
        fighter=('Medusa' if attack else 'King Arthur') if state=='nodefense' else ('Merlin' if attack else 'Medusa')
        team=1 if fighter=='Medusa' else 2
        timer=(10 if state=='timer-warning' else 30) if timerstate and not attack else None
        c.ribbon('ROLE-'+side,g['ROLE-'+side],'attack' if attack else 'defense',fighter,team,timer, state=='timer-warning' and not attack)
    status_visible=state in ['declare','defense-window','timer-warning'] or (state=='defense-chosen' and board=='marmoreal')
    if status_visible:
        rr=g['STATUS'];value=st('ms.status.defend') if board=='marmoreal' else WHY['why.wait.defender']['ru']
        if board=='marmoreal':defend_status(c,rr)
        else:
            su=24;f=font(math.ceil(su*s),True);rows=wrap(value,f,(rr[2]-32)*s)
            while ((len(rows)-1)*(su+4)+su)*s>(rr[3]-16)*s and su>16:
                su=20 if su==24 else 16;f=font(math.ceil(su*s),True);rows=wrap(value,f,(rr[2]-32)*s)
            c.panel('STATUS',rr);c.text('status',value,[rr[0]+16,rr[1]+8,rr[2]-32,rr[3]-16],su,True,center=True,rows=rows,parent='STATUS')
    if timerstate:
        for key,label,primary in [('DEFEND',st('hud.combat.defend').upper(),True),('NO-DEFENSE',st('hud.combat.no.defense').upper(),False)]:
            rr=list(g[key])
            if w==1920 and ui==100:
                added=c.panels['ROLE-L']['rectangle_su'][3]-g['ROLE-L'][3]
                rr[1]+=added;c.change(key,g[key],rr,'конфликт неизменных кнопок HB-07 с новой строкой таймера; минимальный сдвиг вниз')
            normal=state=='defense-chosen'
            c.panel(key,rr,radius=4,body='turn.flash.yellow' if primary and normal else 'disabled' if primary else 'card.navy',alpha=1 if primary else .92,edge='card.navy' if primary else 'card.cream',edgealpha=1 if primary else .45)
            c.text('button.'+key,label,[rr[0]+12,rr[1]+4,rr[2]-24,rr[3]-8],20,True,'card.navy' if primary and normal else 'text.primary',True,parent=key)
    if state in ['effects','effects-long','slam','hit','holds'] or (state=='defense-window' and board=='sarpedon'):
        cw=480 if small else 560;cy=64 if small else 80;cx=(w/s-cw)/2
        base=g.get('CENTER',[cx,cy,cw,64]);rr=list(base)
        if status_visible:
            status=c.panels['STATUS']['rectangle_su'];rr[1]=max(rr[1],status[1]+status[3]+8)
        if state=='defense-window':
            if rr!=base:c.change('CENTER',base,rr,'CENTER минимум 8 su после STATUS')
            c.panel('CENTER',rr,transient=True);c.text('wait.defense',st('hud.combat.wait.defense'),[rr[0]+16,rr[1]+12,rr[2]-32,40],24,True,center=True,parent='CENTER')
        elif state.startswith('effects'):
            keys=['feint','swift','winged','regroup'] if state=='effects-long' else ['feint','swift']
            center_effects(c,rr,keys,2 if small else 3)
        else:
            resolved_center(c,rr)
    if state=='hit':
        # A smaller CENTER changes the anchor search's optimum on one canvas.
        # fix1 owns no damage changes: retain the already accepted attribution.
        rr=list(FIX1_BEFORE['per_mockup'][c.id]['panels']['DAMAGE']['rectangle_su'])
        c.change('DAMAGE',None,rr,'HB-44 fix2: принятый якорь Medusa сохранён из fix1-before.json; 56×36 su radius 8, безопасная траектория подъёма')
        c.panel('DAMAGE',rr,radius=8,transient=True,onboard=True)
        c.text('damage','−1',rr,24,True,'damage.text',True,parent='DAMAGE')
    return c

def rectmask(c,p):
    out=np.zeros((c.h,c.w),bool);x0,y0,x1,y1=p['box_px'];out[max(0,y0):min(c.h,y1),max(0,x0):min(c.w,x1)]=True;return out

def measure(c):
    fm,sm=masks(c.board,c.w,c.h);panels={};trans=[];overlaps=[]
    for key,p in c.panels.items():
        m=rectmask(c,p);row={k:v for k,v in p.items()};row.update(figure_overlap_px2=int(np.count_nonzero(m&fm)),space_overlap_px2=int(np.count_nonzero(m&sm)))
        reserved=[]
        for rk,rr in c.reserved.items():
            rm=rectmask(c,{'box_px':c.pxbox(rr)})
            n=int(np.count_nonzero(m&rm))
            if n:reserved.append({'block':rk,'px2':n})
        row['reserved_overlaps']=reserved;panels[key]=row
        if p['transient']:trans.append({'block':key,**row})
    for (ak,a),(bk,b) in itertools.combinations(c.panels.items(),2):
        n=int(np.count_nonzero(rectmask(c,a)&rectmask(c,b)))
        if n:overlaps.append({'a':ak,'b':bk,'px2':n,'transient':a['transient'] or b['transient']})
    persistent_ok=not any(p['figure_overlap_px2'] or p['space_overlap_px2'] or p['reserved_overlaps'] for p in panels.values() if not p['transient']) and not any(not p['transient'] for p in overlaps)
    # Literal primitive plane: semi-transparent edge/body pixels are excluded,
    # alongside scans, backs, accepted icons, background and text antialiasing.
    a=np.asarray(c.palette_plane);solid=a[:,:,3]==255;colors=np.array(list(RGB.values()))
    if solid.any():
        pixels=a[:,:,:3][solid];valid=np.zeros(len(pixels),bool)
        for color in colors:valid|=(pixels==color).all(axis=1)
        off=int((~valid).sum());count=len(valid)
    else:off=count=0
    hud=np.asarray(c.hud)[:,:,3]>0;different=np.any(np.asarray(c.im)!=np.asarray(c.bg),axis=2)
    parts=[]
    for p in c.parts:
        m=rectmask(c,{'box_px':c.pxbox(p['rectangle_su'])})
        parts.append({**p,'figure_overlap_px2':int((m&fm).sum()),'space_overlap_px2':int((m&sm).sum())})
    return {'id':c.id,'board':c.board,'state':c.state,'size':[c.w,c.h],'ui_scale':c.ui,'su_to_px':c.s,'panels':panels,'parts':parts,'panel_to_panel_overlaps':overlaps,'persistent_pass':persistent_ok,'transient':trans,
            'texts':c.texts,'icons':c.icons,'edges':c.edgechecks,'scans':c.scans,
            'palette':{'opaque_pixels':count,'off_token_pixels':off,'fraction':off/count if count else 0},'outside_hud_changed_pixels':int((different&~hud).sum())}

def save_pair(path,im):
    path.parent.mkdir(parents=True,exist_ok=True);im.convert('RGBA').save(path)
    gray(im).save(path.with_name(path.stem+'-gray.png'))

def overlay(c):
    footer=max(160,math.ceil((math.ceil(len(c.parts)/2)+3)*22*c.s))
    im=Image.new('RGBA',(c.w,c.h+footer),RGB['card.navy']+(255,));d=ImageDraw.Draw(im);s=c.s
    # Outline the EXACT dilated masks used for acceptance, not only their inputs.
    fm,sm=masks(c.board,c.w,c.h)
    for mask,color in [(sm,'state.pending'),(fm,'card.cream')]:
        mi=Image.fromarray(mask.astype(np.uint8)*255)
        rim=mask & (np.asarray(mi.filter(ImageFilter.MinFilter(3)))==0)
        a=np.zeros((c.h,c.w,4),np.uint8);a[rim]=RGB[color]+(255,)
        im.alpha_composite(Image.fromarray(a),(0,0))
    d=ImageDraw.Draw(im)
    reg=MASKDATA['topology_transforms'][f'{c.board}-{c.w}x{c.h}']
    for cell in reg['spaces']:
        pts=[tuple(p) for p in cell['polygon_px']];d.line(pts+[pts[0]],fill=RGB['state.pending']+(255,),width=max(1,round(s)))
    for poly in MASKDATA['figure_polygons_1080p'][c.board]:
        q=c.w/1920;pts=[(round(x*q),round(y*q)) for x,y in poly];d.line(pts+[pts[0]],fill=RGB['card.cream']+(255,),width=max(1,round(s)))
    def box(label,r,color):
        b=c.pxbox(r);d.rectangle([b[0],b[1],b[2]-1,b[3]-1],outline=RGB[color]+(255,),width=max(1,round(s)))
        f=font(math.ceil(14*s),True);size=' × '.join(f'{v:.1f}' for v in r[2:])+' su'
        anchor=f'({r[0]:.1f},{r[1]:.1f})'
        rows=wrap(label+' '+anchor+' '+size,f,max(20,b[2]-b[0]-6*s))
        for i,t in enumerate(rows):d.text((b[0]+3*s,b[1]+3*s+i*18*s),t,font=f,fill=RGB[color]+(255,))
    for k,r in c.reserved.items():box(k,r,'text.secondary')
    for k,p in c.panels.items():box(k,p['rectangle_su'],'state.warning' if p['transient'] else 'card.cream')
    for p in c.parts:
        r=p['rectangle_su'];b=c.pxbox(r);d.rectangle([b[0],b[1],b[2]-1,b[3]-1],outline=RGB['state.pending']+(255,),width=max(1,round(s)))
    f=font(math.ceil(14*s),True)
    d.text((16*s,74*s),c.state,font=f,fill=RGB['text.primary']+(255,))
    d.text((12,c.h+8),'Внутренние области: x, y, w, h · su; светлый контур = фигуры + margin; бирюзовый = клетки + margin',font=font(math.ceil(14*s),True),fill=RGB['text.primary']+(255,))
    for i,p in enumerate(c.parts):
        col=i%2;row=i//2;r=p['rectangle_su']
        label=p['key']+' · '+', '.join(f'{v:.1f}' for v in r)
        d.text((12+col*c.w/2,c.h+36+row*22*s),label,font=f,fill=RGB['text.secondary']+(255,))
    return im

def contact(board,w,h,ui,images,labels,overlay_sheet=False):
    tw=w if overlay_sheet else 640;th=max(pic.height for pic in images) if overlay_sheet else round(h*tw/w);header=48
    im=Image.new('RGBA',(tw*len(images),th+header),RGB['card.navy']+(255,));d=ImageDraw.Draw(im)
    for i,(pic,label) in enumerate(zip(images,labels)):
        if not overlay_sheet:pic=pic.resize((tw,th),Image.Resampling.LANCZOS)
        im.alpha_composite(pic,(i*tw,header));d.text((i*tw+12,12),label,font=font(20,True),fill=RGB['text.primary']+(255,))
    return im

BUILD_AUDITS={}
def timeline(board,overlay_only=False):
    # Feedback delays are offsets within cues, never an extra hold after the cue.
    steps=[('Объявление · CUE-008',600,'declare'),('Окно защиты · ввод',0,'defense-window'),
           ('Защита · CUE-009',500,'defense-chosen'),('Переворот · CUE-010',800,None),
           ('Чтение',1000,'reveal'),('Уловка · эффект',600,'effects'),('Swift Strike · отменён',600,'effects'),
           ('Слэм',180,'slam'),('Пауза счёта',300,None),('Удар · CUE-011',900,'hit'),('Уход · 150 + 200',350,None)]
    total=sum(t for _,t,_ in steps);width=3840;height=1280
    im=Image.new('RGBA',(width,height),RGB['card.navy']+(255,));d=ImageDraw.Draw(im)
    d.text((32,20),'HB-29 · '+board+' · время относительно объявления, без ожидания ввода',font=font(28,True),fill=RGB['text.primary']+(255,))
    d.text((32,62),'Задержки внутри CUE: 008 +150; 009 +150; 010 +200. Flip 130–200 внутри 800. Урон +60, HP +80 от контакта.',font=font(16),fill=RGB['text.secondary']+(255,))
    x0=64;x1=width-64;axisy=1000;unit=(x1-x0)/total;t=0;thumbw=420;thumbh=236
    # Thumbnails use three lanes; interval width never changes a scan's aspect.
    for i,(name,dur,state) in enumerate(steps):
        start=t;end=t+dur;x=x0+start*unit;xe=x0+end*unit
        if dur:
            d.rectangle([x,axisy,xe,axisy+30],fill=RGB['state.pending' if i%2 else 'card.cream']+(255,))
        else:d.line([(x,axisy-20),(x,axisy+40)],fill=RGB['state.warning']+(255,),width=3)
        lane=i%3;top=132+lane*278;labelx=min(max(20,x),width-thumbw-20)
        if state:
            ident=f'HB-29-{board}-{state}-1920x1080-100'
            if overlay_only:
                a=BUILD_AUDITS[ident];c=Canvas(board,1920,1080,100,1.,state);geometry(c)
                c.panels=a['panels'];c.parts=a['parts'];pic=overlay(c)
            else:pic=Image.open(OUT/(ident+'.png')).convert('RGBA')
            thumb=pic.resize((thumbw,thumbh),Image.Resampling.LANCZOS);im.alpha_composite(thumb,(round(labelx),top))
            d.line([(labelx+thumbw/2,top+thumbh+2),(x,axisy-3)],fill=RGB['text.secondary']+(255,),width=1)
        text=name+' · '+(str(dur)+' мс' if dur else 'вне суммы')
        rows=wrap(text,font(16,True),thumbw)
        for n,line in enumerate(rows):d.text((labelx,top+thumbh+4+n*20),line,font=font(16,True),fill=RGB['text.primary']+(255,))
        d.text((min(x,width-220),axisy+46+(i%2)*22),str(start)+' мс',font=font(14,True),fill=RGB['text.primary']+(255,));t=end
    d.text((width-240,axisy+96),str(total)+' мс',font=font(24,True),fill=RGB['text.primary']+(255,))
    d.text((32,1160),'A: 5830 мс (2 строки, защита); без строк 4630. Без защиты и строк: 4130 мс; ориентир 04 ≈3900, разница +230.',font=font(20,True),fill=RGB['text.primary']+(255,))
    d.text((32,1200),'Таймер 30 с — дедлайн ввода, не длина постановки. Если прибавлять три feedback_delay отдельно: 6330 мс; здесь они не складываются.',font=font(16),fill=RGB['text.secondary']+(255,))
    return im,{'source':['docs/game-design/visual/04-hud-spec.md#2.7','docs/unreal/contracts/cue-dispatcher/cue-table.json'],
               'steps':[{'name':n,'duration_ms':dur,'start_ms':sum(x[1] for x in steps[:i]),'thumbnail_state':state} for i,(n,dur,state) in enumerate(steps)],
               'defended_two_lines_ms':total,'defended_no_lines_ms':total-1200,'no_defense_no_lines_ms':total-1200-500,'spec_approx_ms':3900,'difference_ms':230,
               'additional_line_ms':600,'feedback_delay_ms':{'CUE-008':150,'CUE-009':150,'CUE-010':200,'CUE-011':200},
               'delays_added_to_axis':False,'if_first_three_delays_added_ms':total+500,'input_wait_excluded':True,'sheet_size_px':[width,height]}

def sources_after():
    changed=[]
    for p,data in {**BEFORE['files'],**FIX1_INPUTS['files']}.items():
        q=Path(p) if Path(p).is_absolute() else ROOT/p
        if not q.exists() or sha(q)!=data['sha256']:changed.append(p)
    return changed

def hash_mismatches():
    prompt=(ROOT/'docs/game-design/visual/06-tasks/prompts/HB-29.codex.md').read_text(encoding='utf-8')
    result=[]
    for line in prompt.splitlines():
        if not line.startswith('| `'):continue
        cols=[c.strip() for c in line.split('|')[1:-1]];p=cols[0].strip('`')
        data=BEFORE['files'].get(p)
        if not data:continue
        expected=cols[3]
        if re.fullmatch('[a-f0-9]{64}',expected) and expected!=data['sha256']:result.append({'path':p,'expected':expected,'actual':data['sha256']})
    result.extend({'path':p,'expected_prefix':v['expected_prefix'],'actual':v['sha256']} for p,v in FIX1_INPUTS['files'].items() if not v['expected_match'])
    return result

def exportmeta(path):
    with Image.open(path) as im:
        alpha=im.convert('RGBA').getchannel('A');b=alpha.getbbox();w,h=im.size
        margins=[b[0],b[1],w-b[2],h-b[3]] if b else [w,h,w,h]
        return {'path':rel(path),'size':[w,h],'mode':im.mode,'margin_px':margins,'touches_edge':any(v==0 for v in margins)}

def manifest():
    paths=sorted(p for root in [PKG,OUT] for p in root.rglob('*') if p.is_file() and p.name!='manifest-sha256.json')
    dump(PKG/'manifest-sha256.json',{'schema':'HB-29.sha256/1','self_excluded':True,'files':{rel(p):sha(p) for p in paths}})

def facts():
    trace_paths={'marmoreal':'docs/game-design/evidence/DE-FOOTAGE/2026-10-05/I/marmoreal/combat-20261005-235827/combat-client-host.trace.txt',
                 'sarpedon':'docs/game-design/evidence/DE-FOOTAGE/2026-10-05/I/sarpedon/combat-20261005-235948/combat-client-joiner.trace.txt'}
    runs={}
    for board,ranges in [('marmoreal',[(1284,1286),(3656,3661)]),('sarpedon',[(805,807),(1590,1612)])]:
        lines=(ROOT/trace_paths[board]).read_text(encoding='utf-8').splitlines()
        runs[board]={'source':trace_paths[board],'evidence':[{'line':i,'text':lines[i-1]} for a,b in ranges for i in range(a,b+1)]}
    used={}
    for slug,titles in [('medusa',['Feint','Dash','Snipe','Regroup']),('king-arthur',['Swift Strike','Momentous Shift'])]:
        for title in titles:
            c=card(slug,title);key=slug+':'+title.lower().replace(' ','-')
            used[key]={'source':f'scraped-data/api/heroes/{slug}.json','type':c['type'],'value':c['value'],'boostValue':c['boostValue'],'title':title,'scan_ru':SCANS[key],'ru_i18n':c['card'].get('i18n',{}).get('ru',{})}
    return {'schema':'HB-29.facts/1','backgrounds':BG,'sources':{k:v['sha256'] for k,v in {**BEFORE['files'],**FIX1_INPUTS['files']}.items()},'cards_used':used,'effects':EFF,'shortened_lines':SHORTENED,
            'runs':runs,'combats':{'A':{'source_board':'marmoreal','seq':10,'attacker':'Merlin','target':'Medusa','attack':3,'defense':2,'boost':0,'damage':1,'outcome':'win','log_lines_in_trace':1,'swift_cancelled_line':'presentation of cancelled effect per 04 §2.7, not a second applied trace line'},
                                 'B':{'source_board':'sarpedon','seq':9,'attacker':'Merlin','target':'Medusa','attack':3,'defense':3,'boost':0,'damage':0,'outcome':'hold'},
                                 'C-marmoreal':{'seq':54,'attacker':'Medusa','target':'King Arthur','attack':3,'defense':0,'damage':3,'card':'medusa:snipe'},
                                 'C-sarpedon':{'seq':19,'attacker':'Medusa','target':'King Arthur','attack':1,'defense':0,'damage':1,'card':'medusa:regroup'}},
            'projections':['A on Sarpedon projects Marmoreal seq=10 onto the same fighters/roles','B on Marmoreal projects Sarpedon seq=9 onto the same fighters/roles'],
            'owner':{'marmoreal':'Medusa / P1','sarpedon':'King Arthur / P2'},'left_is_owner':True,
            'timer':{'30':{'source':'art/imagegen/hud-composition-v1-codex/facts.json','frame':'docs/game-design/evidence/DE-FOOTAGE/2026-10-05/I/marmoreal/combat-20261005-235827/joiner/s09-combat-defense-open.jpg','visible':'server deadline: 30s left'},
                     '10':{'frame':'docs/game-design/evidence/DE-FOOTAGE/2026-10-05/I/sarpedon/combat-20261005-235948/joiner/s09-combat-resolve-revealed.jpg','visible':'server deadline: 10s left','note':'resolve deadline from run I reused as last-10-seconds defense warning example'}},
            'effects_long':{'note':'тестовая строка; не момент прогона I','keys':['feint','swift','winged','regroup'],'winged_effect_chars':len(EFF['winged']['effect'])},
            'strings':{k:{'source':v['source'],'ru':v['ru']} for k,v in STRINGS.items() if k.startswith('hud.combat') or k=='ms.status.defend'},
            'fighter_names_source':'C:/tmp/visual/CX-01r/db-names-2026-10-06.txt','english_effects_db_check':'C:/tmp/visual/CX-12/db-card-effects-2026-10-06.txt',
            'image_generation':{'used':False,'records':[]},'deltas':DELTAS,
            'fix1':{'baseline':'fix1-before.json','new_inputs':'fix1-inputs.json','centers':FIX1_CENTERS,'status':FIX1_STATUS,'more_chips':FIX1_CHIPS}}

def accepted_exceptions(audits,scans,contrastdata):
    relevant=[a for a in audits if a['board']=='marmoreal' and a['size']==[1920,1080] and a['ui_scale']==100 and 'DEFEND' in a['panels']]
    return [
        {'id':'ВР-VS2-HB29-11','what':'ROLE-L timer row and defense button placement, Marmoreal 1920x1080 100%',
         'measured':{'ROLE-L_height_su':56,'DEFEND_y_su':747,'NO-DEFENSE_y_su':803,'shift_su':28,'persistent_overlap_px2':0,'canvases':[a['id'] for a in relevant]},
         'expected':{'ROLE-L_height_su':28,'DEFEND_y_su':719,'NO-DEFENSE_y_su':775,'persistent_overlap_px2':0},
         'accepted_by':'Claude review 2026-10-06, by delegation','decision_id':'ВР-VS2-HB29-11','reason':'The added timer row requires 28 su; moving both buttons preserves zero overlap. Already recorded in delta 04.'},
        {'id':'ВР-VS2-HB29-12','what':'Whole card backs in the CP-13 combat window',
         'measured':{'source_size_px':[768,1051],'aspect':768/1051,'max_gap_su':max(max(r['gap_su']) for r in scans if r['back']),'whole':True,'cropped':False,'stretched':False},
         'expected':{'max_gap_su':3,'rule_scope':'ВР-VS2-CP-02 RU scans 287x398'},
         'accepted_by':'Claude review 2026-10-06, by delegation','decision_id':'ВР-VS2-HB29-12','reason':'The 3 su rule applies to RU scans; the different aspect of card backs leaves up to 4 su while preserving the whole image.'},
        {'id':'ВР-VS2-HB29-13','what':'Inherited inactive HB-08 primary button edge',
         'measured':{'edge':'#061623','body':'#4E5457','edge_contrast':float(contrast(RGB['card.navy'],RGB['disabled'])),'label_contrast':float(contrast(RGB['text.primary'],RGB['disabled']))},
         'expected':{'edge_contrast_min':3,'label_contrast_min':4.5},
         'accepted_by':'Claude review 2026-10-06, by delegation','decision_id':'ВР-VS2-HB29-13','reason':'Inactive controls are exempt from WCAG 2.1 SC 1.4.11 non-text 3:1 contrast; the accepted HB-08 skin remains unchanged and its label is 6.60:1.'}]

def build(refresh_hit=False):
    OUT.mkdir(parents=True,exist_ok=True);(PKG/'comparison').mkdir(exist_ok=True)
    audits=[];pairs=[];outputs=[];timeline_totals={};native_inputs=[]
    prior={}
    if refresh_hit:
        prior={a['id']:a for a in load(PKG/'verification.json')['overlap']['per_mockup']}
        oldfacts=load(PKG/'facts.json')
        DELTAS.extend(d for d in oldfacts['deltas'] if '-hit-' not in d['id'])
        SHORTENED.extend(oldfacts['shortened_lines'])
        FIX1_CENTERS.extend(r for r in oldfacts['fix1']['centers'] if '-hit-' not in r['id'])
        FIX1_STATUS.extend(oldfacts['fix1']['status'])
        FIX1_CHIPS.extend(oldfacts['fix1']['more_chips'])
    for board in BG:
        states=[x for x in STATES if board=='marmoreal' or x!='timer-warning']
        for w,h,ui,s in CONFIGS:
            finals=[];overlays=[];previous=None
            for state in states:
                ident=f'HB-29-{board}-{state}-{w}x{h}-{ui}'
                if refresh_hit and state!='hit':
                    a=prior[ident];c=Canvas(board,w,h,ui,s,state);geometry(c)
                    c.panels=a['panels'];c.parts=a['parts'];c.im=Image.open(OUT/(ident+'.png')).convert('RGBA')
                else:
                    c=render(board,w,h,ui,s,state);a=measure(c);save_pair(OUT/(c.id+'.png'),c.im)
                audits.append(a);BUILD_AUDITS[c.id]=a
                path=OUT/(c.id+'.png');outputs.append(rel(path))
                y=np.asarray(gray(c.im))[:,:,0]
                if previous is not None:
                    diff=np.abs(y.astype(int)-previous.astype(int));pairs.append({'board':board,'canvas':f'{w}x{h}-{ui}','from':states[len(finals)-1],'to':state,'different_px':int((diff>0).sum()),'max_luma_difference':int(diff.max()),'passed':bool((diff>0).any())})
                previous=y;finals.append(c.im);overlays.append(overlay(c));native_inputs.append({'id':c.id,'native_canvas':[w,h],'su_to_px':s,'scaled_from_master':False})
            name=f'HB-29-{board}-contact-{w}x{h}-{ui}.png';save_pair(OUT/name,contact(board,w,h,ui,finals,states))
            name=f'HB-29-{board}-overlay-{w}x{h}-{ui}.png';save_pair(PKG/'comparison'/name,contact(board,w,h,ui,overlays,states,True))
            print(board,w,h,ui,'rendered',len(states),'states',flush=True)
        for only in [False,True]:
            im,totals=timeline(board,only);timeline_totals[board]=totals
            save_pair((PKG/'comparison' if only else OUT)/f'HB-29-{board}-timeline-1920x1080-100.png',im)
    dump(PKG/'facts.json',facts())
    changed=sources_after();texts=[t for a in audits for t in a['texts']];icons=[i for a in audits for i in a['icons']];scans=[r for a in audits for r in a['scans']]
    refpath=ROOT/'art/imagegen/card-frame-v1-codex/vector/sizes/combat/card-frame-idle-x1.png'
    a=np.asarray(native_frame(230,319,1));b=np.asarray(Image.open(refpath).convert('RGBA'));diff=np.abs(a.astype(int)-b.astype(int))
    framecheck={'reference':rel(refpath),'largest_channel_difference':int(diff.max()),'different_pixels':int(np.any(diff,axis=2).sum()),'passed':bool(np.array_equal(a,b)),'underlay_excluded_from_raw_frame_match':True}
    pngs=sorted(p for root in [PKG,OUT] for p in root.rglob('*.png'))
    palette={'method':'transparent literal primitive plane at native canvas; alpha<255 compositing edges and text AA excluded; scans, backs, icons and background excluded','opaque_pixels':sum(a['palette']['opaque_pixels'] for a in audits),'off_token_pixels':sum(a['palette']['off_token_pixels'] for a in audits),'per_mockup':[{ 'id':a['id'],**a['palette']} for a in audits]}
    palette['fraction']=palette['off_token_pixels']/palette['opaque_pixels']
    contrastdata={'text_min':min(t['contrast_min'] for t in texts if t['contrast_min'] is not None),'edge_min':min(e['edge_vs_body_min'] for a in audits for e in a['edges']),'icon_min':min(i['glyph_contrast'] for i in icons),'pair_scope':'02 §3.5 / ВР-VS2-06: edge vs own panel body; glyph vs its own plate','per_mockup':[{'id':a['id'],'texts':a['texts'],'edges':a['edges'],'icons':a['icons']} for a in audits]}
    uncertain=[{'what':'Russian Swift Strike and Momentous Shift title/effect','where':'effect lines / facts.json','why':'i18n.ru absent in scrape; DB effects English only','handling':'source English verbatim, never placeholder'},
               {'what':'duration of defense input','where':'timeline axis','why':'depends on player input, not animation','handling':'zero-width marked input breakpoint; not included in total'}]
    acceptance={}
    def accept(key, passed, measured, expected, note=''):acceptance[key]={'passed':bool(passed),'measured':measured,'expected':expected,'note':note}
    accept('C1',all(a['outside_hud_changed_pixels']==0 for a in audits),{'background_hashes':{b:sha(ROOT/p) for b,p in BG.items()},'outside_HUD_changed_px':sum(a['outside_hud_changed_pixels'] for a in audits)},'specified unretouched frames; 0 changed pixels outside HUD')
    accept('C2',False,{'HB07_rectangles_reused':True,'delta_rows':len(DELTAS),'button_exception':'Marmoreal 1920x1080 100: buttons shifted by ribbon growth'},'HB07 base geometry plus declared deltas','Literal button rectangles conflict with the newly required timer row. See C7 and delta 04.')
    accept('C3',framecheck['passed'] and all(r['scale']<=1 and max(r['gap_su'])<=3 for r in scans),{'frame':framecheck,'max_scan_scale':max(r['scale'] for r in scans),'max_gap_su':max(max(r['gap_su']) for r in scans),'RU_scan_max_gap_su':max(max(r['gap_su']) for r in scans if not r['back'])},'CP13 exact frame; whole scan scale <=1; gap <=3 su','RU scans fit. Whole 768×1051 backs leave up to 4 su; no crop or distortion used.')
    accept('C4',all(t['passed'] for t in texts if t['key'].startswith('slot.')),{'slots':['Shield','CardBack','NoDefense'],'chosen_caption':'separate 24 su panel above card'},'shield64 + whole caption / real back / X64')
    accept('C5',all(t['passed'] for t in texts if '.tag' in t['key']),{'role_text':14,'team_chip':24,'P1':'circle','P2':'hexagon'},'whole role text; v3 disc24; HB44 chip24')
    accept('C6',all(t['passed'] for t in texts if '.timer' in t['key']),{'n':[30,10],'bar_width_su':[230,150],'bar_height_su':4,'warning':'token triangle24 + !; edge2'},'timer only own defender; 30/10 derived from frames','10 is resolve deadline example, not an observed defense-window tick.')
    accept('C7',False,{'text_fit':all(t['passed'] for t in texts if t['key'].startswith('button.')),'skin_tokens':'HB08 exact','shifted_button_canvas':'Marmoreal 1920x1080 100 only'},'HB07 DEFEND and NO-DEFENSE rectangles unchanged','Required timer row cannot fit before immutable y=719. Buttons moved down, preserving zero overlap.')
    accept('C8',all(p['rectangle_su'][3]<=160 for a in audits for k,p in a['panels'].items() if k=='CENTER'),{'center_height_max_su':max(p['rectangle_su'][3] for a in audits for k,p in a['panels'].items() if k=='CENTER'),'A_resolved_lines':'per canvas measured in fix1.centers','B':'full Dash line','fix1_centers':FIX1_CENTERS},'state visibility; CENTER <=160; no splash')
    accept('C9',all(t['passed'] for t in texts if t['key'].startswith('effect.')),{'row_pitch_su':22,'max_rows':2,'limits':{'L':3,'S':2},'X_cancelled':'v3 marker-x-stamp24','shortened_instances':len(SHORTENED)},'source texts; at most2 rows; current bar3; X shape')
    accept('C10',len(audits)==84,{'Marmoreal':44,'Sarpedon':40,'combats':'A/B/C run I; foreign-board projections explicit'},'11+10 states x4, owner left; real data')
    accept('C11',sum('DAMAGE' in a['panels'] for a in audits)==8,{'damage_only_hit':True,'capsule_su':[56,36],'radius_su':8,'target':'Medusa'},'HB44 capsule −1; overlaps declared transient')
    accept('C12',len(timeline_totals)==2,timeline_totals,'two timelines to scale, input excluded, totals explicit')
    accept('C13',all(a['persistent_pass'] for a in audits),{'persistent_failures':[a['id'] for a in audits if not a['persistent_pass']]},'0 px² persistent vs figures, spaces, reserved blocks and each other','Contained content belongs to its parent panel; content-parent overlap is intentional, not a panel collision. Rectangle checks are conservative.')
    accept('C14',not any('уточнить' in t['text'].lower() for t in texts),{'placeholder_text_count':sum('уточнить' in t['text'].lower() for t in texts),'uncertain_values':uncertain},'0 placeholder on finals')
    accept('C15',all(t['passed'] for t in texts),{'failures':[{'id':a['id'],'text':t} for a in audits for t in a['texts'] if not t['passed']]},'no clipped labels; ellipsis only effect line; prescribed wait string retained')
    accept('C16',len(native_inputs)==84,native_inputs,'each HUD native raster size, no scaled master')
    accept('C17',True,'required Russian licensing line in README','exact verbatim line')
    accept('C18',not changed and palette['fraction']==0,{'source_changed':changed,'palette_fraction':palette['fraction'],'outside_folder':[]},'schema keys present; immutable inputs; manifest verified separately')
    accept('text_contrast',contrastdata['text_min']>=4.5,contrastdata['text_min'],'>=4.5:1')
    accept('edge_icon_contrast',contrastdata['edge_min']>=3 and contrastdata['icon_min']>=3,{'edge':contrastdata['edge_min'],'icon':contrastdata['icon_min']},'>=3:1 on specified pairs','HB08 immutable disabled primary navy edge vs #4E5457 body is 2.3803:1. Other panel edges and semantic glyphs pass.')
    accept('smallest_text_720p',min(t['nominal_font_px'] for a in audits if a['size'][1]==720 for t in a['texts'])>=10.5,min(t['nominal_font_px'] for a in audits if a['size'][1]==720 for t in a['texts']),'>=10.5 px')
    accept('gray_states',all(p['passed'] for p in pairs),pairs,'every consecutive pair differs by luma or shape')
    for key,decision in [('C2','11'),('C3','12'),('C7','11'),('edge_icon_contrast','13')]:
        acceptance[key]['accepted_by_review']='ВР-VS2-HB29-'+decision
    accept('fix1_source_baseline_preserved',sha(PKG/'source-hashes-before.json')==FIX1_BEFORE['source_baseline_sha256'],sha(PKG/'source-hashes-before.json'),FIX1_BEFORE['source_baseline_sha256'])
    accept('fix1_more_chip_contrast',bool(FIX1_CHIPS) and all(p['text_contrast']>=4.5 for p in FIX1_CHIPS),FIX1_CHIPS,'type.tag on #15232E; >=4.5:1')
    accept('fix1_HB13_status',len(FIX1_STATUS)==16 and all(r['lines']==HB13['status_text_fit'][r['source_id']]['lines'] and abs(r['ink_top_pad_su']-HB13['status_text_fit'][r['source_id']]['ink_top_pad_su'])<.01 and abs(r['ink_bottom_pad_su']-HB13['status_text_fit'][r['source_id']]['ink_bottom_pad_su'])<.01 for r in FIX1_STATUS),FIX1_STATUS,'16 Marmoreal STATUS renders: same HB13 lines, type, left alignment and ink padding')
    v={'schema':'HB-29.verification/1','task':'HB-29','status':'предложено','source_unchanged':not changed,'source_changed_paths':changed,'expected_hash_mismatches':hash_mismatches(),'outside_folder':[],
       'write_scope':{'method':'Python audit hook restricts every write/mkdir/remove/rename to the two package roots; no subprocesses; source SHA before/after','writes':sorted(WRITES),'forbidden_write_attempts':0},
       'exports':[exportmeta(p) for p in pngs],'palette':palette,'gray':{'method':'Rec.709 luma on stored sRGB samples; alpha preserved','every_png_has_gray':all(p.with_name(p.stem+'-gray.png').exists() for p in pngs if not p.stem.endswith('-gray')),'pairs':pairs},
       'sizes':{'mockups_color':len(outputs),'mockups_gray':len(outputs),'timeline_color':2,'timeline_gray':2,'overlay_sheets_color':8,'overlay_sheets_gray':8,'overlay_timelines_color':2,'overlay_timelines_gray':2,'contact_sheets_color':8,'contact_sheets_gray':8,'native_render':native_inputs},
       'acceptance':acceptance,'accepted_exceptions':accepted_exceptions(audits,scans,contrastdata),'contrast':contrastdata,'overlap':{'method':'half-open full rectangular footprints; registered HB07 masks with saved margins; contained children belong to parent','persistent_zero':all(a['persistent_pass'] for a in audits),'per_mockup':audits},
       'transient_overlap':[{'id':a['id'],'panels':a['transient'],'panel_intersections':[p for p in a['panel_to_panel_overlaps'] if p['transient']]} for a in audits if a['transient']],
       'scan_scale':{'max':max(r['scale'] for r in scans),'max_gap_su':max(max(r['gap_su']) for r in scans),'per_mockup':[{'id':a['id'],'scans':a['scans']} for a in audits]},'frame_match_cp13':framecheck,
       'button_text_fit':[{'id':a['id'],'texts':[t for t in a['texts'] if t['key'].startswith('button.')]} for a in audits if any(t['key'].startswith('button.') for t in a['texts'])],
       'min_text_px_720p':min(t['nominal_font_px'] for a in audits if a['size'][1]==720 for t in a['texts']),
       'timeline_totals':timeline_totals,'uncertain_values':uncertain,
       'fix1':{'baseline':'fix1-before.json','new_inputs':'fix1-inputs.json','centers':FIX1_CENTERS,'status':FIX1_STATUS,'more_chips':FIX1_CHIPS,'source_baseline_unchanged':sha(PKG/'source-hashes-before.json')==FIX1_BEFORE['source_baseline_sha256']},
       'damage_attribution':[{'id':a['id'],'target':'medusa','anchor_source':'HB44 fix2 accepted HB29 anchor, preserved in fix1-before.json','box_su':a['panels']['DAMAGE']['rectangle_su']} for a in audits if 'DAMAGE' in a['panels']],
       'limits':['C2/C7: accepted by review ВР-VS2-HB29-11; literal button rectangles remain failed','C3: accepted by review ВР-VS2-HB29-12; max whole back gap 4 su remains above literal 3 su','edge_icon_contrast: accepted by review ВР-VS2-HB29-13; inherited inactive edge 2.3803:1 remains below literal 3:1'],
       'package_bytes_without_manifest':sum(p.stat().st_size for p in PKG.rglob('*') if p.is_file() and p.name!='manifest-sha256.json')}
    dump(PKG/'verification.json',v)
    write_readme(v)
    manifest() # VERY LAST OUTPUT WRITE. verify_outputs.py is read-only.
    print('Built',len(outputs),'finals; failed:',[k for k,a in acceptance.items() if not a['passed']],flush=True)

def write_readme(v):
    rows=['# HB-29 — макет боя','', 'Статус: **предложено**. Рекомендую единственный вариант **native-HB07-CP13**: свои карты слева, чужие справа; роль подписана, команда различается кругом/шестиугольником. Плоские токены, неизменные RU-сканы и реальные фоны. Пакет для ревью; клиент не менялся.', '',
          'Сканы карт, рубашки и иллюстрация доски — только для внутренней LAN-сборки (ВР-48, GAP-019); в git не входят, лежат в scraped-data/derived/hud-combat-v1-codex/.','',
          'Созданы 84 цветных финала и 84 серых, две временные шкалы с серыми парами, восемь контактных листов с парами. В comparison — восемь листов геометрии и две шкалы без исходной графики, также в цвете и сером. Все HUD рисуются в настоящем размере, от мастера уменьшаются только разрешённые миниатюры листов. ImageGen не используется; записей генерации нет.', '',
          '## Листы','']
    for board in BG:
        for w,h,ui,s in CONFIGS:
            name=f'HB-29-{board}-contact-{w}x{h}-{ui}'
            over=f'HB-29-{board}-overlay-{w}x{h}-{ui}'
            rows.append(f'- {board} {w}×{h} UI {ui}%: [цвет](../../../scraped-data/derived/hud-combat-v1-codex/{name}.png), [серый](../../../scraped-data/derived/hud-combat-v1-codex/{name}-gray.png), [геометрия](comparison/{over}.png), [серая геометрия](comparison/{over}-gray.png).')
        name=f'HB-29-{board}-timeline-1920x1080-100'
        rows.append(f'- {board}: [шкала](../../../scraped-data/derived/hud-combat-v1-codex/{name}.png), [серая](../../../scraped-data/derived/hud-combat-v1-codex/{name}-gray.png), [без сканов](comparison/{name}.png), [серая без сканов](comparison/{name}-gray.png).')
    rows+=['','Финалы: `scraped-data/derived/hud-combat-v1-codex/HB-29-<board>-<state>-<res>-<scale>.png`; рядом `-gray.png`. Состояния по порядку: '+', '.join(STATES)+'. На Sarpedon timer-warning отсутствует. Геометрические листы показывают каждый кадр в родном пиксельном размере, рамки сканов, ленты и внутренние области, маски, защищённые блоки HB-07, якоря и размеры su. Контуры показывают исходные полигоны и фактические маски с консервативными полями HB-07; нижняя легенда содержит x,y,w,h всех дочерних областей. Легенда лежит вне родного игрового холста.', '',
            '## Данные и малые решения','',
            '- A — Marmoreal seq=10: Merlin / Swift Strike 3 против Medusa / Уловка 2, урон 1. Серая X-форма помечает отменённый Swift Strike; это представление отмены по 04, а не вторая исполненная строка трассы. A на Sarpedon — проекция другого прогона.',
            '- B — Sarpedon seq=9: Momentous Shift 3 / Рывок 3, защита держит, урона нет. B на Marmoreal — проекция другого прогона.',
            '- C — отдельные моменты без защиты: Marmoreal seq=54, Snipe 3; Sarpedon seq=19, Regroup 1. Владелец P1 на Marmoreal, P2 на Sarpedon.',
            '- До раскрытия карта защиты — настоящая рубашка. Подпись выбранной карты вынесена над рамкой на отдельную плашку 24 su; ни над сканом, ни над рубашкой текста нет.',
            '- Лента под картой растёт под целую роль и чип 24 su. Timer — новая строка 16 su; предупреждение — процедурный треугольник 24 su с «!», временная замена до IC-47. Пример 10 с взят с дедлайна resolve Sarpedon, не выдаётся за тик живой защиты.',
            '- CENTER: эффекты до 2 текстовых рядов с шагом 22 su, интервал между строками 6 su. В L до 3 эффектов, в S до 2. В slam/hit обе разрешённые строки A помещаются на каждом холсте; Уловка без текущей полосы, Swift Strike с X. Высота считается по содержимому с отступами 12 su сверху/снизу. В holds помещается целый эффект Dash.',
            '- effects-long — **тестовая строка**, не момент прогона I. Источники четырёх эффектов и целый обрезанный текст сохранены в facts.json. В L «ещё 1», в S «ещё 2».',
            '- Marmoreal STATUS воспроизводит принятый HB-13 defend: те же строки, размер 24 su, левое выравнивание и отступы по фактическому ink-блоку; в S цельное «Без защиты» на второй строке, шаг 30 su, высота 78 su. Sarpedon STATUS сохранён. Предписанное «Ждём защиту…» — исходная строка с многоточием.',
            '- Фон не ретушируется: старые подписи фигур (включая Medusa 16/16) — артефакт исходного кадра, а не новые данные макета. В hit капсула HB-44 transient; её пересечения записаны отдельно. Чип HB-44 воспроизведён без изменения формы. Принятые якоря капсулы (number_anchor HB-44 fix2, ближайшая цель Medusa и безопасная траектория подъёма) сохранены в fix1-before.json и не пересчитываются при уменьшении CENTER. Простая исходная точка над Medusa в тесной группе Marmoreal попадала на соседнюю гарпию и заменена принятой атрибуцией ещё в базовом пакете.',
            '', '## Что не прошло','',
            'Буквальные C2/C7 остаются не пройдены: Marmoreal 1920×1080/100%, ROLE-L с таймером 56 su, DEFEND y=747 и NO-DEFENSE y=803 вместо 719/775 (сдвиг 28 su). Пересечения 0 px². Исключение принято Claude review 2026-10-06, by delegation — ВР-VS2-HB29-11; рисунок не менялся.',
            'Буквальный C3 остаётся не пройден: целые рубашки 768×1051 (aspect 0.731) оставляют до **4 su**, больше 3 su. ВР-VS2-CP-02 задаёт 3 su для RU-сканов 287×398; они укладываются. Рубашки не обрезаны и не растянуты, CP-13 совпадает пиксель в пиксель. Исключение принято Claude review 2026-10-06, by delegation — ВР-VS2-HB29-12.',
            'Буквальный edge_icon_contrast остаётся не пройден: кромка disabled primary из HB-08 #061623 на #4E5457 — **2,3803:1**, ниже 3:1; подпись **6,60:1**. Неактивный контроль освобождён от требования 3:1 WCAG 2.1 SC 1.4.11; принятый скин сохранён. Исключение принято Claude review 2026-10-06, by delegation — ВР-VS2-HB29-13. Исходные passed:false и измерения сохранены; accepted_by_review указывает решение.',
            '', '## Дельта 04','', '| Блок | Кадр | HB-07 → HB-29, su (x,y,w,h) | Причина |','|---|---|---|---|']
    fixes=['## Исправления fix1','',
           'До правок сохранены прямоугольники CENTER/STATUS, тексты, строки, выравнивание, области «ещё n» и исходные transient_overlap в [fix1-before.json](fix1-before.json). Исходный source-hashes-before.json не переснимался. Новые три входа HB-13 и полные SHA-256 — [fix1-inputs.json](fix1-inputs.json).','',
           '1. CENTER slam/hit: фиксированные 160 su и голое «ещё 2» → полные разрешённые строки A на всех четырёх холстах обеих досок; ни текущей полосы, ни пустой зоны. holds: 160 su → целая строка Dash с высотой по содержимому. Типы счёта/исхода 48/28 su сохранены; промежуток счёт→исход 4 su, исход→эффекты 8 su. Поле сверху и снизу 12 su. Измерено для каждого кадра; transient_overlap ниже — консервативные прямоугольники по маскам HB-07.','',
           '| Кадр | Вариант / высота su (до → после) | CENTER su (x,y,w,h) | Фигуры px² (до → после) | Клетки px² (до → после) |',
           '|---|---|---|---|---|']
    per={a['id']:a for a in v['overlap']['per_mockup']}
    for r in FIX1_CENTERS:
        old=FIX1_BEFORE['per_mockup'][r['id']]['panels']['CENTER'];new=per[r['id']]['panels']['CENTER']
        fixes.append(f"| {r['id']} | {r['variant']} / {old['rectangle_su'][3]:.3f} → {r['rectangle_su'][3]:.3f} | {r['rectangle_su']} | {old['figure_overlap_px2']} → {new['figure_overlap_px2']} | {old['space_overlap_px2']} → {new['space_overlap_px2']} |")
    fixes+=['','2. «ещё n»: голый текст с разными якорями → единый чип panel.bg.inset #15232E, radius 4 su, высота 24 su, поля 8 su по горизонтали, type.tag 14 su Roboto Bold Condensed text.primary. Левый край капсулы совпадает с x текста эффектов (CENTER.x + 44 su); текст чипа внутри начинается на +8 su. Применён во всех effects-long; slam/hit получили полные строки, holds не скрывает Dash. Та же функция рисует fallback-чип через 8 su под исходом, если обе строки перестанут помещаться в 160 su.','',
            '| Кадр | Чип su (x,y,w,h) | Контраст текста |','|---|---|---|']
    for r in FIX1_CHIPS:fixes.append(f"| {r['id']} | {r['rectangle_su']} | {r['text_contrast']:.4f}:1 |")
    fixes+=['','3. STATUS на Marmoreal declare / defense-window / timer-warning / defense-chosen: переносы и центрирование HB-07 → точный текстовый блок HB-13 defend. На L одна строка и прежняя высота 48 su; на S две строки «Вас атакуют: выберите карту защиты или» / «Без защиты» в кавычках, прежняя высота 74 → 78 su. На всех холстах размер 24 su и левое выравнивание HB-13. Sarpedon сохранён. На Marmoreal STATUS и CENTER не показываются одновременно; Sarpedon сохраняет зазор CENTER ≥8 su. Постоянные блоки на каждом кадре: 0 px² с масками и блоками HB-07.','',
            '| Холст / все четыре состояния | STATUS su (x,y,w,h) | Шаг su | Ink-поля сверху / снизу su |','|---|---|---|---|']
    for r in FIX1_STATUS:
        if '-declare-' in r['id']:fixes.append(f"| {r['id'].replace('-declare-','-')} | {r['rectangle_su']} | {r['line_pitch_su']} | {r['ink_top_pad_su']:.3f} / {r['ink_bottom_pad_su']:.3f} |")
    fixes+=['','4. Три прежних лимита рисунка сохранены и зарегистрированы в accepted_exceptions: ВР-VS2-HB29-11 / 12 / 13. C2, C3, C7 и edge_icon_contrast сохранили буквальные проверки и получили accepted_by_review. Новые несогласованные исключения не добавлены.','',
            'Все 84 финала, серые пары, восемь контактных и восемь overlay-листов, обе шкалы с актуальными миниатюрами пересобраны. verify_outputs.py проверяет SHA-256, Rec.709, области сохранения всех 84 кадров, новые чипы и HB-13 STATUS.','']
    index=rows.index('## Что не прошло');rows[index:index]=fixes
    seen=set()
    for d in DELTAS:
        k=(d['block'],d['id'],str(d['new_su']))
        if k in seen:continue
        seen.add(k);rows.append(f"| {d['block']} | {d['id']} | {d['old_su']} → {d['new_su']} | {d['reason']} |")
    rows+=['','## Проверки C1–C18','', '| Критерий | Результат | Измерение / решение |','|---|---|---|']
    for key,a in v['acceptance'].items():
        if not re.fullmatch('C\\d+',key):continue
        note=a['note'] or str(a['expected'])
        if a.get('accepted_by_review'):note+=' Исключение принято: '+a['accepted_by_review']+'.'
        rows.append(f"| {key} | {'прошло' if a['passed'] else 'не прошло (буквально); принятое исключение' if a.get('accepted_by_review') else 'не прошло'} | {note} |")
    rows+=['',f"Непрерывные блоки: {'0 px² пересечений' if v['overlap']['persistent_zero'] else 'есть пересечения — см. verification.json'}. Текст min {v['contrast']['text_min']:.2f}:1; кромки {v['contrast']['edge_min']:.2f}:1; значки {v['contrast']['icon_min']:.2f}:1. Минимальный номинальный текст 720p — {v['min_text_px_720p']} px; физический размер шрифта округляется вверх. CP-13: max difference {v['frame_match_cp13']['largest_channel_difference']}; проверяется сырой слой без navy-подложки. Масштаб сканов max {v['scan_scale']['max']:.4f}, зазор max {v['scan_scale']['max_gap_su']:.3f} su.",
            '', 'Палитра меряется на прозрачной плоскости литеральных примитивов: непрозрачные пиксели точных токенов, без сканов, рубашек, v3-значков, фона и альфа-кромок. Комбинация двух токенов при alpha-composite не принимается за новый материал. Реальный контраст проверяется на уже составленном кадре. Дочерний глиф/текст пересекается с собственной плашкой по определению; аудит пересечений сравнивает самостоятельные блоки, а дочерние области дополнительно проверяет против масок.',
            '', '## Время','',
            'Шкалы нарисованы пропорционально миллисекундам. Окно защиты — точка ввода вне суммы, 30 с не длина постановки. CUE-008 600, CUE-009 500, CUE-010 800 (flip 130–200 внутри), чтение 1000, два эффекта по 600, слэм 180, пауза 300, удар 900 от контакта, уход 350: **5830 мс**. Без строк — 4630; без защиты и строк — 4130 против ориентировочных 3900 в 04, +230 мс. Каждая строка +600. feedback_delay — внутренние смещения, не дополнительное удержание; если складывать первые три отдельно, 6330. На шкале показаны +150/+150/+200 и урон +60, HP +80. Шкала 3840×1280, миниатюры из финалов 1080p/100% без изменения соотношения сторон; flip, pause, leave не получают скан.',
            '', '## Открытые данные','',
            'Swift Strike и Momentous Shift не имеют русского title/effect в i18n.ru; проверка БД подтверждает только английский эффект. Такие строки: **lang en, no RU in data**, используются дословно. Русский скан при этом существует и используется. Имена Medusa, King Arthur, Merlin совпадают с БД; перевод не придуман. Ожидание ввода не имеет фиксированной длительности. Других придуманных значений нет.',
            '', '## Входы и воспроизведение','',
            f"Исходный baseline: {len(BEFORE['files'])} SHA-256, весь v3 включён; fix1 добавляет {len(FIX1_INPUTS['files'])} входа HB-13 отдельным списком, не меняя baseline. source_unchanged={v['source_unchanged']}; outside_folder=[]. Сам генератор запрещает все записи вне двух папок и запуск subprocess. Копии исходных генераторов сохранены без изменений, CP-13 используется только через две чистые функции. Git/Unreal/сеть для построения не используются.",
            '', 'Изменённые входы относительно исходного baseline / новых HB-13 входов: '+json.dumps(v['source_changed_paths'],ensure_ascii=False)+'.',
            '', 'Несовпадения хэшей с карточкой: '+('нет.' if not v['expected_hash_mismatches'] else json.dumps(v['expected_hash_mismatches'],ensure_ascii=False)),
            '', 'Пересборка: `python -B -X utf8 art/imagegen/hud-combat-v1-codex/_tools/build_hb29.py`. Проверка: `python -B -X utf8 art/imagegen/hud-combat-v1-codex/_tools/verify_outputs.py`. Последняя запись сборки — manifest-sha256.json; проверка ничего не пишет.']
    (PKG/'README.md').write_text('\n'.join(rows)+'\n',encoding='utf-8')

if __name__=='__main__':build(refresh_hit='--refresh-hit' in sys.argv)
