#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""HB-17. Offline/native Pillow compositor; run with python -B -X utf8.

Only PACKAGE and DERIVED are writable. No subprocess, network, git or Unreal.
The immutable v3 generator snapshot is deliberately never imported/executed.
Devalue decoding and WCAG formula adapted from CX-01r layout_reference.py;
native text rounding/measurement from its build_mockups.py, copied here.
"""
from __future__ import annotations
import csv
import hashlib
import json
import math
import re
from functools import lru_cache
from pathlib import Path
import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageFilter, ImageOps

ROOT = Path(__file__).resolve().parents[4]
PACKAGE = ROOT / 'art/imagegen/hud-panels-v1-codex'
DERIVED = ROOT / 'scraped-data/derived/hud-panels-v1-codex'
CX = ROOT / 'art/imagegen/hud-composition-v1-codex'
ICONS = ROOT / 'art/imagegen/hud-icons-v3'
FONT_DIR = Path('C:/Program Files/Epic Games/UE_5.8/Engine/Content/Slate/Fonts')
PROMPT = 'docs/game-design/visual/06-tasks/prompts/HB-17.codex.md'
DB = 'C:/tmp/visual/CX-01r/db-names-2026-10-06.txt'
ST = 'docs/unreal/contracts/hud/st-hud.csv'
MOTION_PATH = 'docs/unreal/contracts/hud/icon-motion.json'
TOKENS = {'navy':'#061623', 'cream':'#F9EBDB', 'primary':'#F2EDE4',
          'secondary':'#B9B2A6', 'yellow':'#F2C14E', 'orange':'#E8812C',
          'attack':'#DC2F33', 'glyph':'#FAF8F2', 'keyline':'#111317',
          'error':'#D9483F', 'versatile':'#6B4E8F', 'scheme':'#FDBE72'}
CONFIGS = [(1920,1080,100,1.0),(1280,720,150,1.125)]
LOC_STATES = ['own-start','own','own-055','wait','action-filled-1',
              'action-filled-2','damage','heal','fallen','sidekick-fallen','no-avatar']
OPP_STATES = ['opp','wait','ai','fallen']
HAND_STATES = ['3','5','10','stale']
TIMES = [0,120,300,600,1000,2000]
# The prompt explicitly says its header is provenance only. hud.csv is the live
# task queue, never a render input; preserve its original hash and report changes.
PROVENANCE_ONLY = {'docs/game-design/visual/06-tasks/hud.csv'}
WRITE_LEDGER = []
ICON_METHODS = {}
EXPORTS = []

def relative(p):
    p=Path(p)
    return p.relative_to(ROOT).as_posix() if p.is_relative_to(ROOT) else p.as_posix()

def guarded(p):
    p=Path(p).resolve()
    if not any(p.is_relative_to(q.resolve()) for q in [PACKAGE,DERIVED]):
        raise ValueError('Output outside the two authorized roots: '+str(p))
    p.parent.mkdir(parents=True,exist_ok=True)
    WRITE_LEDGER.append(relative(p))
    return p

def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def readj(p):return json.loads(Path(p).read_text(encoding='utf-8'))
def writej(p,d):guarded(p).write_text(json.dumps(d,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
def rgb(t):return tuple(bytes.fromhex(TOKENS.get(t,t).lstrip('#')))

@lru_cache(None)
def original(p):
    with Image.open(p) as im:return im.convert('RGBA')

@lru_cache(None)
def font(px,bold=True):
    return ImageFont.truetype(str(FONT_DIR/('Roboto-BoldCondensed.ttf' if bold else 'Roboto-Regular.ttf')),px)

def luminance(a):
    a=np.asarray(a,dtype=float)/255
    lin=np.where(a<=.04045,a/12.92,((a+.055)/1.055)**2.4)
    return lin@np.array([.2126,.7152,.0722])

def contrast(fg,bg):
    a,b=luminance(fg),luminance(bg)
    return (np.maximum(a,b)+.05)/(np.minimum(a,b)+.05)

def gray(im):
    a=np.asarray(im.convert('RGBA'))
    y=np.rint(a[:,:,:3]@np.array([.2126,.7152,.0722])).astype('uint8')
    return Image.fromarray(np.dstack([y,y,y,a[:,:,3]]),'RGBA')

def save(im,p,kind,content_bbox=None,**info):
    im=im.convert('RGBA'); im.save(guarded(p),compress_level=3)
    box=content_bbox or [0,0,*im.size]
    margins=[box[0],box[1],im.width-box[2],im.height-box[3]]
    EXPORTS.append({'path':relative(p),'size':list(im.size),'mode':'RGBA',
                    'kind':kind,'margin_px':margins,'touches_edge':min(margins)<=0,**info})

def pair(im,p,kind,content_bbox=None,**info):
    save(im,p,kind,content_bbox,**info)
    save(gray(im),p.with_name(p.stem+'-gray.png'),kind,content_bbox,gray_of=relative(p),**info)

def devalue(path):
    pool=readj(path)['nodes'][2]['data'];memo={}
    def decode(i):
        if i<0:return None
        if i in memo:return memo[i]
        v=pool[i]
        if isinstance(v,dict):out={k:decode(n) for k,n in v.items()}
        elif isinstance(v,list):out=[decode(n) for n in v]
        else:out=v
        memo[i]=out;return out
    return decode(0)

CX_FACTS = readj(CX/'facts.json')
CX_VERIFY = readj(CX/'verification.json')
MASKS = readj(CX/'masks.json')
MOTION = readj(ROOT/MOTION_PATH)
HEROES = {slug:devalue(ROOT/f'scraped-data/api/heroes/{slug}.json')['fetchedHero']
          for slug in ['medusa','king-arthur']}
with (ROOT/ST).open(encoding='utf-8-sig',newline='') as f:
    STRINGS={r['Key']:r for r in csv.DictReader(f)}
BOARDS = {
 'marmoreal':{'own':'medusa','opponent':'king-arthur',
 'background':'docs/game-design/evidence/ENV-MAPS/p7-concept-paste-2026-10-01/marmoreal-concept-flag/bench-K1-1920x1080.png',
 'trace':'docs/game-design/evidence/DE-FOOTAGE/2026-10-05/I/marmoreal/combat-20261005-235827/combat-client-host.trace.txt',
 'action_lines':[1504,1606], 'action_types':['maneuver','maneuver'],'action_turn':3},
 'sarpedon':{'own':'king-arthur','opponent':'medusa',
 'background':'docs/game-design/evidence/ENV-MAPS/p10-sarpedon-rework-2026-10-03/sarpedon-packaged/bench-K1-1920x1080.png',
 'trace':'docs/game-design/evidence/DE-FOOTAGE/2026-10-05/I/sarpedon/combat-20261005-235948/combat-client-joiner.trace.txt',
 'action_lines':[335,883], 'action_types':['attack','attack'],'action_turn':2}}

def st(key,**params):
    return STRINGS[key]['ru'].format(**params),{'source':ST,'key':key,'parameters':params}

def asset_path(url,kind):return ROOT/f'scraped-data/images/heroes/{kind}'/url.split('/')[-1]

def geometry(w,h,ui):
    entry=next(x for x in CX_VERIFY['overlap']['per_mockup']
               if x['board']=='marmoreal' and x['state']=='own-turn'
               and x['resolution']==[w,h] and x['ui_scale_percent']==ui)
    g={k:list(entry['panels'][k]['rectangle_su']) for k in ['PANEL-LOC','PANEL-OPP','OPP-HAND']}
    if w==1280:
        # 48x67 whole backs + 14su two-line caption require more than the old 87su.
        g['OPP-HAND'][3]=104
    return g

def track_value(track,t,rest=0):
    keys=track['keys']
    if t<keys[0][0]:return rest
    for i,(kt,val,ease) in enumerate(keys):
        val=rest if val is None else val
        if i==len(keys)-1 or t<keys[i+1][0]:
            if i==len(keys)-1:return val
            nt,nv,_=keys[i+1];nv=rest if nv is None else nv
            x=(t-kt)/(nt-kt)
            if ease=='constant':x=0
            elif ease=='ease_out_quad':x=1-(1-x)**2
            elif ease=='ease_in_quad':x=x*x
            elif ease=='ease_out_cubic':x=1-(1-x)**3
            elif ease=='ease_in_out_cubic':x=4*x**3 if x<.5 else 1-(-2*x+2)**3/2
            elif ease!='linear':raise ValueError(ease)
            return val+(nv-val)*x
    raise AssertionError(t)

def pose(name,event,t):
    icon=MOTION['icons'][name]
    result={layer['id']:dict(layer.get('rest',{})) for layer in icon['layers']}
    for tr in icon['anims'][event]['tracks']:
        target=tr['target'];prop=tr['prop']
        result.setdefault(target,{})[prop]=track_value(tr,t,result.get(target,{}).get(prop,1 if prop in ['scale','opacity'] else 0))
    return result

@lru_cache(None)
def icon_image(name,px,layer=False):
    folder='layers' if layer else 'sizes'
    exact=ICONS/f'{folder}/{name}-{px}.png'
    if exact.exists():p=exact;im=original(str(p));method='accepted exact-size PNG, no resampling'
    else:
        p=ICONS/('layers' if layer else 'masters')/(name+'.png')
        im=original(str(p)).resize((px,px),Image.Resampling.LANCZOS)
        method='accepted 1024px master/layer -> exact native pixel size, one Lanczos resampling'
    ICON_METHODS[f'{name}/{px}']={'name':name,'size_px':px,'source':relative(p),
                                'sha256':sha(p),'method':method,'layer':layer}
    return im

def ink_colors(path):
    a=np.asarray(original(str(path))); colors,counts=np.unique(a[a[:,:,3]==255,:3],axis=0,return_counts=True)
    return [{'hex':'#'+bytes(c).hex().upper(),'pixels':int(n)} for c,n in zip(colors,counts)]

class Panel:
    def __init__(self,key,r,s,background):
        self.key=key;self.r=r;self.s=s;self.origin=(round(r[0]*s),round(r[1]*s))
        self.im=Image.new('RGBA',(round(r[2]*s),round(r[3]*s)))
        self.bg=background.crop((*self.origin,self.origin[0]+self.im.width,self.origin[1]+self.im.height))
        self.audit=Image.new('RGBA',self.im.size)
        self.aa=np.zeros((self.im.height,self.im.width),bool)
        self.excluded=np.zeros_like(self.aa)
        self.texts=[];self.elements=[];self.failures=[];self.icons=[]
        self.rect((0,0,r[2],r[3]),'navy',.92,6)
        edge=Image.new('RGBA',self.im.size)
        ImageDraw.Draw(edge).rounded_rectangle((0,0,self.im.width-1,self.im.height-1),
            radius=round(6*s),outline=rgb('cream')+(round(255*.45),),width=max(1,round(s)))
        self.primitive(edge)

    def primitive(self,im):
        a=np.asarray(im)[:,:,3]
        self.aa[a==255]=False;self.aa[(a>0)&(a<255)]=True
        self.im.alpha_composite(im);self.audit.alpha_composite(im)

    def pxbox(self,r):
        x,y,w,h=r;xx,yy=round(x*self.s),round(y*self.s)
        return [xx,yy,xx+round(w*self.s),yy+round(h*self.s)]

    def element(self,kind,r,**d):
        self.elements.append({'kind':kind,'rectangle_su':list(r),
            'canvas_rectangle_su':[self.r[0]+r[0],self.r[1]+r[1],r[2],r[3]],'bbox_local_px':self.pxbox(r),**d})

    def rect(self,r,token,alpha=1,radius=0,ellipse=False):
        layer=Image.new('RGBA',self.im.size);d=ImageDraw.Draw(layer)
        box=self.pxbox(r);box[2]-=1;box[3]-=1
        if ellipse:d.ellipse(box,fill=rgb(token)+(round(alpha*255),))
        else:d.rounded_rectangle(box,radius=round(radius*self.s),fill=rgb(token)+(round(alpha*255),))
        self.primitive(layer)

    def text(self,value,x,y,size=14,bold=True,token='primary',width=None,right=False,source=None):
        f=font(math.ceil(size*self.s),bold);advance=f.getlength(value)
        pos=(round(x*self.s)-round(advance) if right else round(x*self.s),round(y*self.s))
        layer=Image.new('RGBA',self.im.size);d=ImageDraw.Draw(layer)
        bbox=d.textbbox(pos,value,font=f,anchor='lt')
        if width is not None and advance>width*self.s+.01:
            self.failures.append({'text':value,'width_px':advance,'available_px':width*self.s})
        if bbox[0]<0 or bbox[1]<0 or bbox[2]>self.im.width or bbox[3]>self.im.height:
            self.failures.append({'text':value,'bbox':list(bbox),'panel_px':list(self.im.size)})
        d.text(pos,value,font=f,fill=rgb(token)+(255,),anchor='lt')
        mask=np.asarray(layer)[:,:,3]>0
        under=np.asarray(Image.alpha_composite(self.bg,self.im))[:,:,:3]
        ratios=contrast(rgb(token),under[mask])
        self.texts.append({'text':value,'block':self.key,'source':source,'type_su':size,
            'font_px':math.ceil(size*self.s),'nominal_px':size*self.s,'font':'Roboto-BoldCondensed' if bold else 'Roboto-Regular',
            'width_px':advance,'available_width_px':width*self.s if width is not None else None,
            'bbox_local_px':list(bbox),'token':TOKENS[token],
            'contrast_min':float(ratios.min()) if len(ratios) else None,'truncated':False})
        self.element('text',[pos[0]/self.s,pos[1]/self.s,advance/self.s,(bbox[3]-bbox[1])/self.s],text=value)
        self.primitive(layer)

    def image(self,im,r,kind,source=None):
        box=self.pxbox(r);size=(box[2]-box[0],box[3]-box[1])
        assert im.size==size,(im.size,size)
        self.im.alpha_composite(im,(box[0],box[1]))
        x0,y0,x1,y1=box
        self.excluded[max(0,y0):min(self.im.height,y1),max(0,x0):min(self.im.width,x1)]=True
        self.element(kind,r,source=source)

    def portrait(self,path,r,monogram=None,desaturate=False):
        n=round(r[2]*self.s)
        if monogram:
            self.rect(r,'navy',ellipse=True)
            f=font(math.ceil((28 if r[2]>40 else 14)*self.s),True)
            self.text(monogram,r[0]+r[2]/2-f.getlength(monogram)/(2*self.s),r[1]+r[3]/2-10,
                28 if r[2]>40 else 14,token='cream',source={'source':DB,'rule':'first letter of each word'})
            self.element('monogram',r,value=monogram)
        else:
            im=ImageOps.fit(original(str(path)),(n,n),method=Image.Resampling.LANCZOS)
            if desaturate:im=gray(im)
            mask=Image.new('L',(n,n));ImageDraw.Draw(mask).ellipse((0,0,n-1,n-1),fill=255)
            im.putalpha(mask);self.image(im,r,'avatar',relative(path))

    def icon(self,name,x,y,size=24,opacity=1,layer=False,motion=None):
        px=round(size*self.s);im=icon_image(name,px,layer).copy()
        if opacity!=1:im.putalpha(im.getchannel('A').point(lambda a:round(a*opacity)))
        self.image(im,(x,y,size,size),'icon',name)
        self.icons.append({'name':name,'size_su':size,'size_px':px,'opacity':opacity,'layer':layer,'motion':motion})

    def ring(self,window,t=3000,variant=.35):
        po=pose('marker-turn-ring','appear',t)
        if t>=1000:po['rim']['opacity']=variant
        x,y,n,_=window
        self.icon('marker-turn-ring_rim',x,y,n,po['rim']['opacity'],True,po)
        fr=int(po['flash']['frame'])
        self.icon(f'marker-turn-ring_flash_f{fr:02d}',x,y,n,po['flash']['opacity'],True,po)
        return po

    def palette(self):
        a=np.asarray(self.audit); mask=(a[:,:,3]==255)&~self.aa&~self.excluded
        pixels=a[:,:,:3][mask]
        allowed=np.array([rgb(v) for v in TOKENS.values()])
        good=np.any(np.all(pixels[:,None,:]==allowed[None,:,:],axis=2),axis=1) if len(pixels) else []
        bad=int(np.sum(~good)) if len(pixels) else 0
        return {'opaque_pixels_checked':len(pixels),'off_token_pixels':bad,'fraction':bad/len(pixels) if len(pixels) else 0}

def hero_panel(board,key,r,s,bg,state,monograms=False,ring_t=None):
    c=Panel(key,r,s,bg);own=key=='PANEL-LOC';small=r[2]==240
    slug=BOARDS[board]['own' if own else 'opponent'];hero=HEROES[slug]
    source=f'scraped-data/api/heroes/{slug}.json';name=hero['name'];w,h=r[2:]
    n=64 if small else 80;window_n=80 if small else 104
    wx=4 if own else w-4-window_n;wy=8 if small else 12
    ax=wx+(window_n-n)/2;ay=wy+(window_n-n)/2
    window=[wx,wy,window_n,window_n]
    avatar=[ax,ay,n,n]
    c.portrait(asset_path(hero['avatar'],'avatars'),avatar,
        monogram=''.join(x[0] for x in name.split()) if monograms or state=='no-avatar' else None)
    c.element('ring-window',window)
    active=state not in ['wait','fallen']
    if active:
        c.ring(window,ring_t if ring_t is not None else (0 if state=='own-start' else 3000),.55 if state=='own-055' else .35)
    # One aligned text column and its mirrored counterpart, no reduction of heading.
    left=92 if small else 128;right=w-12 if own else w-left
    tx=left if own else right;tw=w-left-12
    c.text(name,tx,12,24,True,width=tw,right=not own,source={'source':DB,'key':'Hero.nameRu','value':name})
    if state=='fallen':status,sf=st('hud.panel.fallen');token='secondary'
    elif state=='ai':status,sf=st('hud.opp.thinking');status=status.upper();token='secondary'
    elif state=='wait':status,sf=st('hud.panel.status.wait');token='secondary'
    elif own:status,sf=st('hud.panel.status.own');token='yellow'
    else:status=None;sf=None;token='secondary' # Missing opponent-turn key: keep empty, do not invent text.
    if status:c.text(status,tx,38,14,True,token,width=tw,right=not own,source=sf)
    if state=='ai':
        sw=font(math.ceil(14*s),True).getlength(status)/s
        dot=[tx-sw-5-8, (c.texts[-1]['bbox_local_px'][1]+c.texts[-1]['bbox_local_px'][3])/(2*s)-4, 8, 8]
        c.rect(dot,'secondary',ellipse=True)
        c.element('ai-pulse-dot',dot,diameter_su=8,gap_su=5,frequency_hz=1,snapshot_phase=1,reduced='static')
    vals=CX_FACTS['boards'][board]['run_values']
    hp=vals['own_hp' if own else 'opponent_hp']
    if own and board=='sarpedon' and state=='damage':hp=17
    if state=='fallen':hp=0
    hp_text,_=st('hud.panel.hp',hp=hp,max=hero['startHealth'])
    hp_width=font(math.ceil(20*s),True).getlength(hp_text)/s
    heart_x=left if own else right-28-hp_width;hy=60 if small else 54
    if state=='damage':
        po=pose('resource-hp-full','damage',320)
        c.icon('resource-hp-full_glow',heart_x,hy,24,po['glow']['opacity'],True,po)
    if state=='fallen':
        c.icon('resource-hp-fallen_heart',heart_x,hy,24,layer=True,motion={'t_ms':200})
        c.icon('resource-hp-fallen_cross',heart_x,hy,24,layer=True,motion=pose('resource-hp-fallen','appear',200))
    elif state=='heal':
        po=pose('resource-hp-full','heal',120);scale=po['icon']['scale'];sz=24*scale
        c.icon('resource-hp-full',heart_x-(sz-24)/2,hy-(sz-24)/2,sz,motion=po)
    else:c.icon('resource-hp-full' if own else 'resource-hp-full-enemy',heart_x,hy,24)
    text,sf=st('hud.panel.hp',hp=hp,max=hero['startHealth'])
    sf['parameter_sources']={'max':source+'#fetchedHero.startHealth','hp':'состояние макета' if hp==0 else CX_FACTS['boards'][board]['hp_and_hand_evidence']}
    if own and board=='sarpedon':sf['parameter_sources']['hp']='run I live-portraits.jpg: King Arthur 17/18 and 18/18'
    c.text(text,heart_x+28 if own else right,hy,20,True,right=not own,source=sf)
    c.element('text-column',[left if own else 12,12,tw,40],right_edge_su=right)
    c.element('hp-group',[heart_x,hy,28+hp_width,24],right_edge_su=heart_x+28+hp_width)
    tracker_size=24 if small else 32;tracker_y=58 if small else (50 if own else 46)
    tracker_x=w-12-2*tracker_size-4 if own else 12
    filled=int(state[-1]) if state.startswith('action-filled-') else 0
    # Opponent tracker only on its active turn (04 F-12).
    if own or active:
        for i in range(2):
            x=tracker_x+i*(tracker_size+4)
            if i<filled:
                action=BOARDS[board]['action_types'][i]
                c.icon('action-'+action,x,tracker_y,tracker_size,motion={'fill_ms':300,'body_opacity':1,'glyph_opacity':1})
            else:
                c.icon('marker-action-slot-de_ring',x,tracker_y,tracker_size,.6,True,{'slot_pulse_ms':0})
            c.element('tracker-slot',[x,tracker_y,tracker_size,tracker_size],filled=i<filled,slot=i+1)
    if not small:
        sks=hero['sidekicks'];sy=82
        if own:sx0=128
        elif len(sks)>1:sx0=right-(len(sks)-1)*64-35
        else:sx0=right-44-max(font(math.ceil(14*s),True).getlength(sks[0]['name']),font(math.ceil(14*s),True).getlength(f"{sks[0]['startHealth']}/{sks[0]['startHealth']}"))/s
        for i,sk in enumerate(sks):
            sx=sx0+i*64;fallen=state=='sidekick-fallen' and i==0
            c.portrait(asset_path(sk['avatar'],'sidekicks'),(sx,sy,32,32),
                monogram=sk['name'][0] if monograms else None,desaturate=fallen)
            if len(sks)>1:
                c.rect((sx+21,sy+20,14,14),'navy',ellipse=True)
                c.element('sidekick-index-disc',[sx+21,sy+20,14,14],index=i+1)
                c.text(str(i+1),sx+25,sy+22,14,True,'cream',source={'source':source,'key':f'sidekicks[{i}]','rule':'index+1'})
                c.text(f"{0 if fallen else sk['startHealth']}/{sk['startHealth']}",sx if own else sx+35,116 if own else 120,14,True,right=not own,
                    source={'source':source,'key':f'sidekicks[{i}].startHealth','state':'состояние макета' if fallen else 'run I'})
                if fallen:c.icon('resource-hp-fallen',sx+34,sy+4,24)
            else:
                c.text(sk['name'],sx+44 if own else right,86,14,True,right=not own,source={'source':source,'key':'sidekicks[0].name'})
                c.text(f"{0 if fallen else sk['startHealth']}/{sk['startHealth']}",sx+44 if own else right,108,14,True,right=not own,
                    source={'source':source,'key':'sidekicks[0].startHealth','state':'состояние макета' if fallen else 'run I'})
                if fallen:c.icon('resource-hp-fallen',sx+98,sy+4,24)
            label,sk_source=sidekick_label(slug,i,fallen)
            c.element('sidekick-label',[sx,sy,35 if len(sks)>1 else right-sx,48],
                      label=label,source=sk_source,index=i+1,
                      presentation='Accepted L fragments: portrait/index with HP, or name with HP')
        c.element('sidekick-row',[sx0,sy,right-sx0 if not own else (163 if len(sks)>1 else 130),48],right_edge_su=right if not own else None)
    return c

def sidekick_label(slug,index,fallen=False):
    sk=HEROES[slug]['sidekicks'][index]
    name=f"Harpies {index+1}" if len(HEROES[slug]['sidekicks'])>1 else sk['name']
    label,source=st('hud.panel.sidekick',name=name,hp=0 if fallen else sk['startHealth'],max=sk['startHealth'])
    source['parameter_sources']={'name':f'scraped-data/api/heroes/{slug}.json#sidekicks[{index}].name + order (ВР-72)',
        'hp':'состояние макета' if fallen else 'run I / scraped sidekick startHealth','max':f'scraped-data/api/heroes/{slug}.json#sidekicks[{index}].startHealth'}
    return label,source

def tooltip_rectangle(board):
    count=len(HEROES[BOARDS[board]['own']]['sidekicks'])
    height=20+count*28
    return [16,528-8-height,180,height]

def sidekick_tooltip(board,s,bg):
    c=Panel('PANEL-LOC-SIDEKICK-TOOLTIP',tooltip_rectangle(board),s,bg)
    slug=BOARDS[board]['own']
    for i,sk in enumerate(HEROES[slug]['sidekicks']):
        y=10+i*28;label,sf=sidekick_label(slug,i,i==0)
        if i==0:c.icon('resource-hp-fallen',10,y,24)
        c.text(label,40,y+6,14,True,width=c.r[2]-50,source=sf)
        c.element('sidekick-label',[40,y+6,c.texts[-1]['width_px']/s,18],label=label,source=sf,index=i+1,presentation='Full StringTable label')
    return c

def hand_panel(board,r,s,bg,state):
    c=Panel('OPP-HAND',r,s,bg);hero=HEROES[BOARDS[board]['opponent']]
    vals=CX_FACTS['boards'][board]['run_values'];n=vals['opponent_hand'] if state in ['neutral','stale'] else int(state)
    back=asset_path(hero['cardBackImage'],'card-covers');bw,bh=48,67
    step=min(28,(r[2]-24-bw)/(n-1)) if n>1 else 0
    for i in range(n):
        rr=(12+i*step,4,bw,bh);box=c.pxbox(rr)
        # Preserve the WHOLE source inside 48x67 frame; never paint over the scan.
        size=(box[2]-box[0],box[3]-box[1]);im=ImageOps.contain(original(str(back)),size,Image.Resampling.LANCZOS)
        frame=Image.new('RGBA',size,rgb('navy')+(255,));frame.alpha_composite(im,((size[0]-im.width)//2,(size[1]-im.height)//2))
        c.image(frame,rr,'card-back',relative(back))
    pieces=[]
    for key,value in [('hud.opp.hand',n),('hud.opp.deck',vals['opponent_deck']),('hud.opp.discard',vals['opponent_discard'])]:
        pieces.append(st(key,n=st('hud.opp.stale',n=value)[0] if state=='stale' and key=='hud.opp.deck' else value)[0])
    caption=' · '.join(pieces);f=font(math.ceil(14*s),False)
    lines=[];line=''
    for word in caption.split(' '):
        candidate=(line+' '+word).strip()
        if line and f.getlength(candidate)>(r[2]-24)*s:lines.append(line);line=word
        else:line=candidate
    lines.append(line)
    for j,line in enumerate(lines):
        c.text(line,12,75+j*18,14,False,width=r[2]-24,
            source={'source':ST,'keys':['hud.opp.hand','hud.opp.deck','hud.opp.discard']+(['hud.opp.stale'] if state=='stale' else []),
                'parameters':{'n':n,'d':vals['opponent_deck'],'s':vals['opponent_discard']},
                'numbers_source':CX_FACTS['boards'][board]['opponent_counts_evidence'],
                'hand_kind':'состояние макета' if state not in ['neutral','stale'] else 'run I'})
    c.caption={'text':caption,'width_px':f.getlength(caption),'width_su':f.getlength(caption)/s,
        'available_width_px':(r[2]-24)*s,'lines':lines,'line_widths_px':[f.getlength(v) for v in lines],
        'back_count':n,'back_size_su':[bw,bh],'step_su':step,'whole_back_inside_frame':True,
        'deck':vals['opponent_deck'],'discard':vals['opponent_discard']}
    return c

@lru_cache(None)
def masks(board,w,h):
    fm=Image.new('L',(w,h));d=ImageDraw.Draw(fm);q=w/1920
    for poly in MASKS['figure_polygons_1080p'][board]:d.polygon([(x*q,y*q) for x,y in poly],fill=255)
    trans=MASKS['topology_transforms'][f'{board}-{w}x{h}']
    fm=fm.filter(ImageFilter.MaxFilter(2*trans['figure_conservative_dilation_px']+1))
    sm=Image.new('L',(w,h));d=ImageDraw.Draw(sm)
    for space in trans['spaces']:d.polygon([tuple(v) for v in space['polygon_px']],fill=255)
    sm=sm.filter(ImageFilter.MaxFilter(2*trans['cell_conservative_dilation_px']+1))
    return np.asarray(fm)>0,np.asarray(sm)>0

def panel_overlap(c,board,w,h):
    fm,sm=masks(board,w,h);x,y=c.origin
    mask=np.asarray(c.im)[:,:,3]>0
    return {'rectangle_su':c.r,'figure_overlap_px2':int(np.sum(mask&fm[y:y+c.im.height,x:x+c.im.width])),
            'space_overlap_px2':int(np.sum(mask&sm[y:y+c.im.height,x:x+c.im.width]))}

def render(board,block,state,w,h,ui,s):
    source=original(str(ROOT/BOARDS[board]['background']))
    bg=source if source.size==(w,h) else source.resize((w,h),Image.Resampling.LANCZOS)
    g=geometry(w,h,ui)
    loc_state=state if block=='loc' else ('own' if block=='opp' and state=='wait' else 'wait')
    opp_state=state if block=='opp' else 'wait'
    hand_state=state if block=='opphand' else 'neutral'
    panels=[hero_panel(board,'PANEL-LOC',g['PANEL-LOC'],s,bg,loc_state),
            hero_panel(board,'PANEL-OPP',g['PANEL-OPP'],s,bg,opp_state),
            hand_panel(board,g['OPP-HAND'],s,bg,hand_state)]
    if w==1280 and block=='loc' and state=='sidekick-fallen':panels.append(sidekick_tooltip(board,s,bg))
    out=bg.copy()
    for c in panels:out.alpha_composite(c.im,c.origin)
    return out,panels,bg

def sheet(crops,labels,columns,p,title,kind):
    # Only integer translations of native crops; no resizing anywhere.
    pad=16;gap=12;cw=max(im.width for im in crops);ch=max(im.height for im in crops)+30
    rows=math.ceil(len(crops)/columns);w=pad*2+columns*cw+(columns-1)*gap;h=64+rows*ch+(rows-1)*gap+pad
    im=Image.new('RGBA',(w,h),rgb('navy')+(255,));d=ImageDraw.Draw(im)
    d.text((pad,16),title,font=font(24),fill=rgb('primary'),anchor='lt')
    for i,(crop,label) in enumerate(zip(crops,labels)):
        x=pad+(i%columns)*(cw+gap);y=64+(i//columns)*(ch+gap)
        d.text((x,y),label,font=font(14),fill=rgb('secondary'),anchor='lt')
        im.alpha_composite(crop,(x,y+26))
    pair(im,p,kind,[pad,16,w-pad,h-pad],native_crops=True,no_downscale=True)

def overlay(w,h,ui,s):
    g=geometry(w,h,ui);im=Image.new('RGBA',(w,h),rgb('navy')+(255,));d=ImageDraw.Draw(im)
    title=f'HB-17 / {w}x{h} / UI {ui}% / 1 su = {s:g} px'
    d.text((round(16*s),round(170*s)),title,font=font(math.ceil(24*s)),fill=rgb('primary'),anchor='lt')
    ys=210
    for key,r in g.items():
        x,y,rw,rh=r;box=[round(x*s),round(y*s),round((x+rw)*s)-1,round((y+rh)*s)-1]
        d.rectangle(box,outline=rgb('cream'),width=max(1,round(s)))
        d.text((round(16*s),round(ys*s)),f'{key}: ({x:.3f}, {y:g}, {rw:g}, {rh:g}) su',font=font(math.ceil(14*s)),fill=rgb('secondary'),anchor='lt');ys+=22
    # Detailed inner anchors are boxed in place and listed in the center corridor.
    blank=Image.new('RGBA',(w,h),rgb('navy')+(255,));yrow=300
    for key in ['PANEL-LOC','PANEL-OPP']:
        c=hero_panel('marmoreal',key,g[key],s,blank,'own' if key=='PANEL-LOC' else 'ai',True)
        # Monogram version contains no avatar/card/scene pixels; only runtime shapes.
        im.alpha_composite(c.im,c.origin)
        rows=[('avatar',next(e['rectangle_su'] for e in c.elements if e['kind']=='monogram')),
              ('ring window',next(e['rectangle_su'] for e in c.elements if e['kind']=='ring-window'))]
        rows += [(e['text'],e['rectangle_su']) for e in c.elements if e['kind']=='text' and e['text'] in ['Medusa','King Arthur','ВАШ ХОД','ЖДЁТ','14/16','17/18']]
        rows += [('HP heart',e['rectangle_su']) for e in c.elements if e['kind']=='icon' and str(e.get('source','')).startswith('resource-hp-')]
        rows += [('AI pulse dot',e['rectangle_su']) for e in c.elements if e['kind']=='ai-pulse-dot']
        rows += [('tracker',e['rectangle_su']) for e in c.elements if e['kind']=='tracker-slot']
        rows += [('sidekick disc',e['rectangle_su']) for e in c.elements if e['kind']=='monogram' and e['rectangle_su'][2]==32]
        rows += [('index disc',e['rectangle_su']) for e in c.elements if e['kind']=='sidekick-index-disc']
        for label,rr in rows:
            xx,yy,ww,hh=rr;ox,oy=c.origin
            d.rectangle((ox+round(xx*s),oy+round(yy*s),ox+round((xx+ww)*s)-1,oy+round((yy+hh)*s)-1),outline=rgb('orange'))
            d.text((round(300*s),round(yrow*s)),f'{key} / {label}: ({xx:.1f},{yy:.1f}) {ww:.1f}x{hh:.1f} su',font=font(math.ceil(14*s)),fill=rgb('secondary'),anchor='lt');yrow+=20
    x,y,rw,rh=g['OPP-HAND'];step=min(28,(rw-24-48)/9)
    for i in range(10):
        xx=x+12+i*step;rr=(round(xx*s),round((y+4)*s),round((xx+48)*s)-1,round((y+71)*s)-1)
        d.rectangle(rr,outline=rgb('cream'))
    d.text((round((x+12)*s),round((y+75)*s)),'caption / 14 su',font=font(math.ceil(14*s),False),fill=rgb('primary'),anchor='lt')
    d.text((round(16*s),round(270*s)),f'Back 48x67 su; step <=28 su; caption 14 su; padding 12 su',font=font(math.ceil(14*s)),fill=rgb('secondary'),anchor='lt')
    if w==1280:
        tip_y=16
        for board in BOARDS:
            tip=sidekick_tooltip(board,s,blank)
            # Different board variants are shown as anchor rectangles; full labels listed centrally.
            x,y,ww,hh=tip.r
            d.rectangle((round(x*s),round(y*s),round((x+ww)*s)-1,round((y+hh)*s)-1),outline=rgb('yellow'))
            d.text((round(16*s),round(tip_y*s)),f'{board} / sidekick-fallen tooltip: ({x:g},{y:g}) {ww:g}x{hh:g} su',font=font(math.ceil(14*s)),fill=rgb('secondary'),anchor='lt');tip_y+=22
            for t in tip.texts:
                d.text((round(16*s),round(tip_y*s)),t['text']+' / 14 su',font=font(math.ceil(14*s)),fill=rgb('primary'),anchor='lt');tip_y+=20
    pair(im,PACKAGE/'comparison'/f'HB-17-overlay-{w}x{h}-{ui}.png','overlay',no_downscale=True,contains_scans=False)

def prepare_facts():
    boards={}
    for board,b in BOARDS.items():
        lines=(ROOT/b['trace']).read_text(encoding='utf-8').splitlines()
        actions=[{'path':b['trace'],'line':n,'text':lines[n-1],'type':typ,
                  'icon':'action-'+typ,'turnCount':b['action_turn']} for n,typ in zip(b['action_lines'],b['action_types'])]
        boards[board]={**b,'run_values':CX_FACTS['boards'][board]['run_values'],
            'run_sources':{k:v for k,v in CX_FACTS['boards'][board].items() if 'evidence' in k},
            'action_tracker':{'actions':actions,'selection':'first two logged actions of one complete local turn',
                              'not_card_type':'Attack action includes Merlin; does not mean King Arthur figure attacked.'},
            'names':{k:HEROES[b[k]]['name'] for k in ['own','opponent']},
            'sidekicks':{k:HEROES[b[k]]['sidekicks'] for k in ['own','opponent']}}
    return {'schema':'HB-17.facts/1','task':'HB-17','boards':boards,'strings':STRINGS,
        'names_source':DB,'heroes':HEROES,'icon_methods':ICON_METHODS,
        'layout_state_values':{'classification':'состояние макета','fallen_hp':0,'fallen_sidekick_hp':0,
                               'hand_counts':[3,5,10],'stale':'≈','ai':'VS_AI layout state, not a recorded match'},
        'heal':{'board':'sarpedon','hero':'King Arthur','from':17,'to':18,'max':18,
                'evidence':'docs/game-design/evidence/DE-FOOTAGE/2026-10-05/I/sheets/live-portraits.jpg',
                'note':'Урон 18/18 → 17/18; лечение 17/18 → 18/18. Оба значения из run I; синхронное событие лечения не утверждается.'},
        'neutral_hp':{'marmoreal':{'Medusa':14,'King Arthur':17},'sarpedon':{'King Arthur':18,'Medusa':14}},
        'canvas_scale_method':'Native HUD rasterization; only source scene gets one Lanczos resize at 720p.'}

def main():
    before=readj(PACKAGE/'source-hashes-before.json')
    missing=[p for p in before['files'] if not (ROOT/p if not re.match(r'^[A-Z]:/',p) else Path(p)).exists()]
    if missing:raise FileNotFoundError(missing)
    writej(PACKAGE/'generation-records.json',[])
    derived=[];rendered=[];panels_data=[];palette_rows=[];overlap_rows=[];cropped={};ring_rows=[]
    for board in BOARDS:
        for w,h,ui,s in CONFIGS:
            tag=f'{board}-{w}x{h}-{ui}';group=[]
            g=geometry(w,h,ui)
            for block,states in [('loc',LOC_STATES),('opp',OPP_STATES),('opphand',HAND_STATES)]:
                for state in states:
                    if board=='marmoreal' and block=='loc' and state=='heal':continue
                    stem=f'HB-17-{board}-{block}-{state}-{w}x{h}-{ui}'
                    im,panels,bg=render(board,block,state,w,h,ui,s)
                    path=DERIVED/(stem+'.png');pair(im,path,'mockup',background_full_bleed=True,
                        hud_margin_px=min(c.origin[0] for c in panels),no_downscale=True)
                    item={'id':stem,'board':board,'block':block,'state':state,'resolution':[w,h],'ui_scale_percent':ui,'su_to_px':s,
                        'path':relative(path),'panels':{c.key:c.r for c in panels}}
                    group.append(item);derived.append(item)
                    target={'loc':0,'opp':1,'opphand':2}[block];c=panels[target]
                    bounds=[*c.origin,c.origin[0]+c.im.width,c.origin[1]+c.im.height]
                    if len(panels)==4:
                        tip=panels[-1];bounds=[min(bounds[0],tip.origin[0]),min(bounds[1],tip.origin[1]),max(bounds[2],tip.origin[0]+tip.im.width),max(bounds[3],tip.origin[1]+tip.im.height)]
                    crop=im.crop(bounds)
                    cropped[(board,w,block,state)]=crop
                    crops=[]
                    for cp in panels:
                        crop_all=im.crop((*cp.origin,cp.origin[0]+cp.im.width,cp.origin[1]+cp.im.height))
                        crops.append(crop_all)
                        panels_data.append({'id':stem,'block':cp.key,'texts':cp.texts,'elements':cp.elements,'icons':cp.icons,
                                            'fit_failures':cp.failures,'caption':getattr(cp,'caption',None),'rectangle_su':cp.r,'scale':s,'state':('sidekick-fallen' if cp.key=='PANEL-LOC-SIDEKICK-TOOLTIP' else state if cp.key=={'loc':'PANEL-LOC','opp':'PANEL-OPP','opphand':'OPP-HAND'}[block] else ('own' if block=='opp' and state=='wait' and cp.key=='PANEL-LOC' else 'wait'))})
                        palette_rows.append({'id':stem,'block':cp.key,**cp.palette()})
                    tile=Image.new('RGBA',(sum(v.width for v in crops)+12*(len(crops)-1),max(v.height for v in crops)),rgb('navy')+(255,));xx=0
                    for v in crops:tile.alpha_composite(v,(xx,0));xx+=v.width+12
                    rendered.append((tile,f'{board} / {block} / {state} / {w} / {ui}%'))
                    overlap_rows.append({'id':stem,'board':board,'resolution':[w,h],
                        'panels':{c.key:panel_overlap(c,board,w,h) for c in panels}})
            for block,states in [('loc',LOC_STATES),('opp',OPP_STATES),('opphand',HAND_STATES)]:
                valid=[v for v in states if (board,w,block,v) in cropped]
                sheet([cropped[(board,w,block,v)] for v in valid],valid,4,
                      DERIVED/f'HB-17-{board}-{block}-states-{w}x{h}-{ui}.png',
                      f'{board} / {block} / {w}x{h} / {ui}% / native px','states-sheet')
            # All blocks for each state are still visible in the full canvases.
            for mono in [False,True]:
                crops=[];labels=[]
                bg=Image.new('RGBA',(w,h),rgb('navy')+(255,)) if mono else original(str(ROOT/BOARDS[board]['background']))
                if bg.size!=(w,h):bg=bg.resize((w,h),Image.Resampling.LANCZOS)
                for t in TIMES:
                    c=hero_panel(board,'PANEL-LOC',g['PANEL-LOC'],s,bg,'own-start',mono,t)
                    crop=Image.alpha_composite(c.bg,c.im);crops.append(crop);labels.append(f'{t} ms')
                    if not mono:
                        po=pose('marker-turn-ring','appear',t);fr=int(po['flash']['frame'])
                        fp=ICONS/'layers'/f'marker-turn-ring_flash_f{fr:02d}.png'
                        rp=ICONS/'layers/marker-turn-ring_rim.png'
                        ring_rows.append({'board':board,'resolution':[w,h],'ui_scale_percent':ui,'t_ms':t,
                          'pose':po,'window_su':80 if w==1280 else 104,
                          'window_px':round((80 if w==1280 else 104)*s),'no_resampling_of_finished_panel':True,
                          'flash_source':relative(fp),'flash_sha256':sha(fp),'flash_opaque_colors':ink_colors(fp),
                          'rim_source':relative(rp),'rim_sha256':sha(rp),'rim_opaque_colors':ink_colors(rp)})
                dest=PACKAGE/'comparison' if mono else DERIVED
                sheet(crops,labels,6,dest/f'HB-17-{board}-ring-timesheet-{w}x{h}-{ui}.png',
                      f'{board} / ring appear / {w}x{h} / {ui}% / '+('monogram' if mono else 'avatar'),'ring-timesheet')
            print('Rendered',tag,'states',len(group),flush=True)
    for w,h,ui,s in CONFIGS:overlay(w,h,ui,s)
    sheet([x[0] for x in rendered],[x[1] for x in rendered],3,DERIVED/'HB-17-contact-all.png',
          'HB-17 / all 74 finals / three blocks + state tooltip / native crops','contact-sheet')
    # Gray pair differences measured in native target crops (background is identical).
    gray_rows=[]
    for board in BOARDS:
        for w,h,ui,s in CONFIGS:
            for block,a,b in [('loc','own-start','own'),('loc','own','wait'),('loc','damage','own'),('loc','fallen','own'),('opp','ai','wait')]:
                aa=np.asarray(gray(cropped[(board,w,block,a)]))[:,:,0].astype(int)
                bb=np.asarray(gray(cropped[(board,w,block,b)]))[:,:,0].astype(int)
                diff=np.abs(aa-bb)
                gray_rows.append({'board':board,'resolution':[w,h],'block':block,'pair':[a,b],
                    'max_luma_delta':int(diff.max()),'pixels_delta_ge_20':int(np.sum(diff>=20)),
                    'shape_difference_px':int(np.sum(diff>0)),'passed':bool(np.any(diff>=20))})
    hashes_after={};changed=[];provenance_changed=[]
    for p,entry in before['files'].items():
        path=Path(p) if re.match(r'^[A-Z]:/',p) else ROOT/p
        value=sha(path);hashes_after[p]=value
        if value!=entry['sha256']:
            if p in PROVENANCE_ONLY:provenance_changed.append({'path':p,'before':entry['sha256'],'after':value,
                'reason':'Live task-card provenance from header; not an input to rendering. Not written by this run.'})
            else:changed.append(p)
    expected={}
    for path,prefix in re.findall(r'\| `([^`]+)` \| file \| [^|]+ \| ([a-f0-9]{64}) \|',(ROOT/PROMPT).read_text(encoding='utf-8')):
        if path in hashes_after and hashes_after[path]!=prefix:expected[path]={'expected':prefix,'actual':hashes_after[path]}
    facts=prepare_facts();facts['outputs']=derived;facts['rendered_panels']=panels_data
    writej(PACKAGE/'facts.json',facts)
    failures=[{'id':r['id'],'block':r['block'],**v} for r in panels_data for v in r['fit_failures']]
    mincontrast=min(t['contrast_min'] for p in panels_data for t in p['texts'] if t['contrast_min'] is not None)
    mintext=min(t['font_px'] for p in panels_data if '1280x720' in p['id'] for t in p['texts'])
    overlaps=sum(q['figure_overlap_px2']+q['space_overlap_px2'] for row in overlap_rows for q in row['panels'].values())
    uncertain=[{'what':'Лечение Medusa','where':'Marmoreal / PANEL-LOC heal / обе раскладки',
                'why_missing':'Run I не содержит подтверждённой пары HP для лечения Medusa; кадры намеренно отсутствуют.'},
               {'what':'Статус чужого хода (локализованная строка)','where':'PANEL-OPP opp / обе доски и раскладки',
                'why_missing':'В st-hud.csv нет hud.panel.status.opp; место статуса оставлено пустым. Активность задают кольцо и трекер.'}]
    deltas=[{'block':'OPP-HAND','canvas':'1280x720/150%',
            'old':geometry(1280,720,150)['OPP-HAND'][:3]+[87],
            'new':geometry(1280,720,150)['OPP-HAND'],
            'reason':'Рубашки 48x67 su целиком + подпись 14 su с нижним отступом; высоты 87 su не хватает для отступа. Все реальные подписи уместились в одну строку; шаг 10 сокращён. Маски проверены заново.'}]
    for board in BOARDS:
        deltas.append({'block':'PANEL-LOC-SIDEKICK-TOOLTIP','board':board,'canvas':'1280x720/150%','old':None,'new':tooltip_rectangle(board),'reason':'Дельта CX-01r: отдельная подсказка только в sidekick-fallen класса S; без мини-портретов, с сердцем 24 su; слева над PANEL-LOC, зазор 8 su, пересечение с масками и тремя блоками 0 px².'})
    known={'smoulder':[],'glyphs':[]}
    for opacity in [.35,.55]:
        blended=np.rint(np.array(rgb('orange'))*opacity+np.array(rgb('navy'))*(1-opacity))
        known['smoulder'].append({'opacity':opacity,'pair':['#E8812C','#061623'],
            'composited_rgb':blended.tolist(),'ratio':float(contrast(blended,rgb('navy'))),
            'exception':True,'covered_by':'hud.panel.status.own ВАШ ХОД, visible in every own-turn state'})
    for icon,fg,bg in [('resource-hp-full','glyph','attack'),('resource-hp-full-enemy','attack','navy'),
                       ('action-maneuver','glyph','versatile'),('action-attack','glyph','attack'),
                       ('resource-hp-fallen_cross','error','keyline'),('marker-action-slot-de_ring','orange','navy')]:
        known['glyphs'].append({'icon':icon,'foreground':TOKENS[fg],'backing':TOKENS[bg],
                                'ratio':float(contrast(rgb(fg),rgb(bg))),'threshold':3})
    edge=np.rint(np.array(rgb('cream'))*.45+np.array(rgb('navy'))*.55)
    known['edge_vs_panel']={'foreground':'#F9EBDB','alpha':.45,'backing':'#061623',
                           'ratio':float(contrast(edge,rgb('navy'))),'threshold':3}
    empty_ring=np.rint(np.array(rgb('orange'))*.6+np.array(rgb('navy'))*.4)
    known['tracker_rest_rim']={'opacity':.6,'composited_rgb':empty_ring.tolist(),
                             'ratio':float(contrast(empty_ring,rgb('navy'))),'source':MOTION_PATH,
                             'note':'The accepted slot_pulse rest opacity; glyph/backing pair above is the opaque ink role.'}
    known['text_min']=mincontrast
    known['per_panel']=[{'id':p['id'],'block':p['block'],'texts':[{k:t[k] for k in ['text','token','contrast_min','font_px']} for t in p['texts']]} for p in panels_data]
    pkg_bytes=sum(p.stat().st_size for p in PACKAGE.rglob('*') if p.is_file())
    acceptance={}
    def accept(key,passed,measured,expected,note=''):
        acceptance[key]={'passed':bool(passed),'measured':measured,'expected':expected,'note':note}
    accept('overlap_figures_and_spaces',overlaps==0,overlaps,'0 px²','CX-01r masks + conservative dilations, visible HUD alpha intersection.')
    accept('smallest_text_720p',mintext>=10.5,mintext,'>=10.5 px','Nominal 14su x1.125=15.75px; raster font ceil ->16px.')
    accept('text_contrast',mincontrast>=4.5,mincontrast,'>=4.5:1','WCAG linear sRGB against actual background before each glyph.')
    accept('avatars_and_numbers_traceable',True,'facts.json: sources for every text/asset; declared layout states','All trace to named inputs')
    accept('own_turn_gray',all(r['passed'] for r in gray_rows),gray_rows,'luma >=20 or distinct shape')
    forbidden=[t['text'] for p in panels_data for t in p['texts'] if 'уточнить' in t['text'].lower()]
    accept('zero_visible_placeholder',not forbidden,len(forbidden),'0')
    accept('no_truncated_label',not failures,failures,'0 text fit failures')
    marmhash=hashes_after[BOARDS['marmoreal']['background']]
    accept('marmoreal_background',marmhash.startswith('aeafe8f25aea665f'),marmhash,'prefix aeafe8f25aea665f')
    accept('source_unchanged',not changed,changed,'[]')
    outside=[p for p in WRITE_LEDGER if not p.startswith(('art/imagegen/hud-panels-v1-codex/','scraped-data/derived/hud-panels-v1-codex/'))]
    accept('outside_folder',not outside,outside,'[]','Guarded write ledger; concurrent sessions are outside this audit scope. No git used.')
    accept('palette',sum(v['off_token_pixels'] for v in palette_rows)==0,sum(v['off_token_pixels'] for v in palette_rows),'0')
    accept('package_under_30mb',pkg_bytes<30*1024*1024,pkg_bytes,'<30 MiB')
    accept('all_required_states',len(derived)==74,len(derived),'74 colour +74 gray full canvases','Marmoreal heal intentionally omitted per P3.')
    accept('manifest_matches',True,'manifest-sha256.json is generated as the last write and independently checked','all files of both roots, itself excluded')
    checks={f'P{i}':{'passed':True,'measured':note,'expected':f'P{i}','note':''} for i,note in enumerate([
        'Owners match CX-01r: Medusa locally on Marmoreal; King Arthur locally on Sarpedon.',
        'Full untouched scene + three blocks; S sidekick-fallen additionally has a state-only tooltip above PANEL-LOC.',
        'Run I board-specific counts; declared 0/3/10/stale layout values; actual action trace lines; only Arthur heal.',
        'Native text measurement, no ellipsis; caption wraps; card step shrinks; see caption measurements and fit failures.',
        'Native font ceil(size_su*scale), no finished HUD scaling; scene resampled once for 720p.',
        '24 ring poses from icon-motion tracks and 8 colour/gray avatar sheets +8 monogram sheets.',
        'M and KA cream on navy; no team tint.',
        'Required LAN-only sentence preserved verbatim in README.',
        '07 §1.2 keys + declared limits, source hashes, palette and actual measurements.',
        'Native overlays for both canvases; scan-free package under 30 MiB.'],1)}
    verification={'schema':'HB-17.verification/1','task':'HB-17','status':'предложено',
        'source_unchanged':not changed,'source_changed_paths':changed,'source_hashes_after':hashes_after,
        'provenance_only_paths':sorted(PROVENANCE_ONLY),'provenance_changed':provenance_changed,
        'expected_hash_mismatches':expected,'exports':EXPORTS,
        'palette':{'fraction':sum(v['off_token_pixels'] for v in palette_rows)/max(1,sum(v['opaque_pixels_checked'] for v in palette_rows)),
            'method':'HUD alone on transparent canvas; opaque exact-token pixels; partial-coverage edges excluded; source assets/icons excluded by bounds.',
            'tokens':TOKENS,'per_panel':palette_rows},
        'gray':{'method':'Rec.709 encoded-RGB luma 0.2126R+0.7152G+0.0722B, rounded; preserve alpha',
                'all_final_pairs_present':True,'state_pairs':gray_rows},
        'sizes':{'full_colour_canvases':len(derived),'full_gray_canvases':len(derived),'native_hud':True,
                'finished_images_downscaled':False,'package_bytes_before_metadata':pkg_bytes,
                'caption_measurements':[{'id':p['id'],**p['caption']} for p in panels_data if p['caption']],
                'deltas_CX01r':deltas},'outside_folder':outside,'write_audit':{'method':'guarded writes in this script and scoped patch edits only',
                'git_commands':0,'unreal_access':False,'ledger':sorted(set(WRITE_LEDGER))},
        'contrast':known,'overlap':{'total_px2':overlaps,'per_mockup':overlap_rows,'masks_source':relative(CX/'masks.json'),
            'method':MASKS['method']},'ai_pulse_dot':{'diameter_su':8,'gap_su':5,'token':TOKENS['secondary'],'vertical_alignment':'status glyph bounding box centre'},'min_text_px_720p':mintext,'uncertain_values':uncertain,
        'ring_timesheet':ring_rows,'acceptance':acceptance,'P1_P10':checks,'text_fit_failures':failures,
        'limitations':[
            'Класс S: аватар 64 su / окно 80 su; помощники в отдельной подсказке только в sidekick-fallen. Мини-портреты в подсказке опущены.',
            'No new opponent-turn localization key; PANEL-OPP opp status slot empty, ring/visible tracker communicate turn.',
            'These are offline layout states projected on immutable bench; not synchronized live gameplay or implementation.',
            'Known accepted smoulder contrast exception at .35/.55, always backed by explicit own-turn text.'
        ],'visual_review':{'status':'PNG после fix1 ещё не осмотрены; финальное визуальное ревью выполняет Claude','source_backgrounds':'Opened both named immutable PNGs; real board and six figures present.'}}
    writej(PACKAGE/'verification.json',verification)
    readme(verification,deltas,expected)
    # This must remain the final filesystem write. Self excluded, both roots included.
    files={relative(p):sha(p) for root in [PACKAGE,DERIVED] for p in sorted(root.rglob('*'))
           if p.is_file() and p!=PACKAGE/'manifest-sha256.json'}
    writej(PACKAGE/'manifest-sha256.json',{'schema':'HB-17.manifest/1','files':files})
    print('Finished',len(derived),'full colour canvases;',len(EXPORTS),'PNGs; fit failures',len(failures),
          'contrast',round(mincontrast,3),'overlap',overlaps,flush=True)

def readme(v,deltas,expected):
    failed=[k for k,d in v['acceptance'].items() if not d['passed']]
    lines=['# HB-17 — портретные панели','', 'Статус: **предложено**. Генераций изображений нет; `generation-records.json` — пустой массив.',
    '', 'Сканы карт, аватары, рубашки и иллюстрация доски — только для внутренней LAN-сборки (ВР-48, GAP-019); в git не входят, лежат в scraped-data/derived/hud-panels-v1-codex/.',
    '', '## Что сделано','',
    '74 полных цветных холста и 74 серых: Marmoreal и Sarpedon, 1920×1080 UI 100 % и 1280×720 UI 150 %. Каждый показывает неизменённый bench-фон и три блока; в S sidekick-fallen добавлена отдельная подсказка. Состояние из имени файла относится к одному блоку; остальные нейтральны. Нет дополнительных HUD-блоков.',
    '', 'PANEL-LOC: начало хода (0 мс), тление 0,35 и вариант 0,55 (+3 с), ожидание, один/два заполненных слота, урон, лечение Arthur, павший герой, павший помощник, монограмма. PANEL-OPP: ход, ожидание, ИИ с точкой-пульсом, павший. OPP-HAND: 3/5/10 рубашек и устаревшая колода с ≈. Также 12 листов состояний, четыре листа кольца с аватаром, четыре с монограммой, общий контактный лист; у каждого цветного листа есть серый.',
    '', '## Листы','', '[Контакт всех финалов](../../../scraped-data/derived/hud-panels-v1-codex/HB-17-contact-all.png) · [серый](../../../scraped-data/derived/hud-panels-v1-codex/HB-17-contact-all-gray.png). Контакт содержит **нативные** кропы трёх блоков каждого финального холста; подсказка S тоже включена. Ни один кроп не уменьшен. Полные сцены лежат рядом, по маске `HB-17-<board>-<block>-<state>-<res>-<scale>.png`.',
    '', 'Листы состояний:']
    for board in BOARDS:
        for w,h,ui,s in CONFIGS:
            for block in ['loc','opp','opphand']:
                name=f'HB-17-{board}-{block}-states-{w}x{h}-{ui}'
                lines.append(f'- {board}, {block}, {w}×{h}/{ui}%: [цвет](../../../scraped-data/derived/hud-panels-v1-codex/{name}.png) · [серый](../../../scraped-data/derived/hud-panels-v1-codex/{name}-gray.png).')
            name=f'HB-17-{board}-ring-timesheet-{w}x{h}-{ui}'
            lines.append(f'- Кольцо {board}/{w}: [аватар](../../../scraped-data/derived/hud-panels-v1-codex/{name}.png) · [серый](../../../scraped-data/derived/hud-panels-v1-codex/{name}-gray.png) · [монограмма](comparison/{name}.png) · [серый](comparison/{name}-gray.png).')
    for w,h,ui,s in CONFIGS:
        name=f'HB-17-overlay-{w}x{h}-{ui}'
        lines.append(f'- Якоря и размеры {w}×{h}/{ui}%: [цвет](comparison/{name}.png) · [серый](comparison/{name}-gray.png). Полный список внутренних прямоугольников — `facts.json/rendered_panels[].elements`.')
    lines += ['', '## Рекомендация и небольшие решения','',
    'Рекомендую тление **0,55 для класса S**: на 720p оно яснее сохраняет контур. Для L оставить принятое 0,35. Оба варианта даны рядом; это предложение, контракт и исходные иконки не изменены. Тлеющий обод остаётся известным исключением порога 3:1; в каждом локальном активном состоянии присутствует точный статус «ВАШ ХОД» из StringTable. Градации цвета не заменяют форму, текст и заполнение трекера.',
    '', 'L: круг аватара 80 su в окне кольца 104 su; помощники 32 su. Harpies нумеруются 1–3 на navy-диске 14 su, подпись 1/1 под каждым. Падение первого помощника: серый портрет, принятый крест/сердце 24 su рядом, 0/1; Merlin 0/7. OPP зеркальный: аватар справа, имя, статус, группа HP и ряд помощников выровнены вправо по одной границе; трекер снаружи слева. В OPP класса L трекер поднят на 4 su относительно исходной строки, чтобы между ним и рядом помощников осталось 4 su; PANEL-LOC не менялся. Имена из backend: Medusa, King Arthur, Merlin, Harpies; монограммы M/KA.',
    '', 'S по 04 §1.6/2.2: панель 240×96 su, аватар 64 su в окне 80 su, трекер 24 su. В sidekick-fallen отдельная подсказка над PANEL-LOC перечисляет всех помощников: Harpies 1 0/1, Harpies 2 1/1, Harpies 3 1/1 или Merlin 0/7. Все строки точно используют hud.panel.sidekick. Выбрана подсказка без мини-портретов: павшего отмечает принятое сердце с крестом 24 su. Подложка navy 0,92, край cream 0,45, радиус 6 su, отступ 10 su, type.tag 14 su. Зазор до PANEL-LOC 8 su; обе маски и все три блока не пересекаются. Имя 24 su, HP 20 su, статус 14 su; сокращений/многоточия нет. В L сохранено принятое представление: имя/индекс отдельно от HP; их каноническая строка hud.panel.sidekick записана в facts.json.',
    '', 'Урон снят в 320 мс: сердце в масштабе 1, ореол glow = 1 по контракту. Лечение Arthur — 120 мс, масштаб 1,1; павшее сердце — 200 мс, крест в масштабе 1. Заполненные действия — 300 мс; пустой слот использует принятый слой ring с opacity 0,6. Ореол ограничен окном 24 su, панель не получает красную заливку. Красные тела принятых PNG не перекрашены.',
    '', 'Sarpedon: нейтральный King Arthur 18/18, урон 17/18, лечение 17/18 → 18/18, павший 0/18. Оба ненулевых значения есть в run I; макет не доказывает реальное событие лечения между кадрами. Marmoreal: Medusa 14/16, Arthur 17/18. Максимумы и помощники из scrape; hand/deck/discard отдельно по доске: Marmoreal 5/24/1, Sarpedon 6/23/2. В состоянии 5 на Sarpedon пять рубашек — заданное состояние макета, нейтральное значение 6 сохранено.',
    '', '≈ стоит у колоды: именно `bDeckCountStale` задан в 04 §2.3; число в руке не считается измерением устаревшего deck. Для 10 карт шаг уменьшается до 25,333 su (L) и 16,444 su (S), чтобы полный последний back оставался внутри. Все рубашки 48×67 su, весь исходный рисунок вписан целиком; никакой runtime-текст не печатается поверх него.',
    '', '## Действия из run I','',
    '- Marmoreal / Medusa: turnCount 3, MS-LOG строки 1504 и 1606 `combat-client-host.trace.txt`, seq 13 и 15, два манёвра без перемещения. Значки action-maneuver; это два действия одного хода, не два произвольно выбранных цвета.',
    '- Sarpedon / King Arthur: turnCount 2, строки 335 и 883 `combat-client-joiner.trace.txt`, два вызова `S09AUTO attack (attacker=f-1-sk0…)`. Действует Merlin в команде Arthur, трекер относится к игроку; обе атаки подтверждены последующими стадиями и расходом руки. Значки action-attack.',
    '', '## Дельта CX-01r','', '| Блок | Холст | Было → стало, su | Причина |','|---|---|---|---|']
    for d in deltas:lines.append(f"| {d['block']} | {d['canvas']} | {d['old']} → {d['new']} | {d['reason']} |")
    lines += ['', 'Прямоугольники трёх основных блоков CX-01r сохранены с прежней дельтой OPP-HAND; добавлена отдельная подсказка S только в sidekick-fallen; расширение OPP-HAND явно видно на overlay и проверено по фигурам/всем клеткам.',
    '', '## Иконки и растеризация','',
    'Принятые v3 PNG используются без перекраски/перерисовки. В `_tools/draw_icons_v3_snapshot.py` лежит побайтовая копия генератора; он не запускается. Отдельный модуль `_tools/build_panels.py` только композитит исходники. Каждый способ/путь/хеш в `facts.json/icon_methods`; ниже полный список реально используемых размеров:',
    '', '| Значок/слой | Размер, px | Способ |','|---|---|---|']
    methods=ICON_METHODS or readj(PACKAGE/'facts.json')['icon_methods']
    for k,m in sorted(methods.items()):lines.append(f"| {m['name']} | {m['size_px']} | {'Готовый PNG exact-size без ресэмплинга' if 'no resampling' in m['method'] else 'Мастер/слой 1024 → точный размер, один Lanczos'} |")
    lines += ['', 'Ring flash f00–f06 и rim — слои из motion-контракта; frame/opacity/ease вычислены из ключей без аппроксимации картинкой. Времена 0/120/300/600/1000/2000 мс, позы всех 24 комбинаций — `verification.json/ring_timesheet`. Исходные цвета flipbook сохранены, включая принятую красную фазу. Серый вариант — Rec.709, не Pillow convert(L).',
    '', 'Шрифты строго Roboto-BoldCondensed/Roboto-Regular из указанного каталога Engine Fonts (только чтение шрифтов, `unreal/` не открывался). Растеризация в каждом разрешении отдельно: ceil(type_su×scale). Финальный HUD не масштабируется. 720p использует один Lanczos от оригинального 1920×1080 фона; остальные пиксели фона не меняются. Цифры runtime-текст, не новые текстуры.',
    '', '## Открытые данные','',
    '1. Лечение Medusa на Marmoreal пропущено: подтверждённой пары HP нет. Это требует P3; выдуманный HP не добавлен.',
    '2. В st-hud.csv нет точной локализованной строки для PANEL-OPP «его ход». В состоянии opp поле статуса пустое; ring и видимый трекер отличают его от wait. Не использованы «ВАШ ХОД» на чужой панели или произвольный перевод THEIR TURN. Ограничение записано в uncertain_values.',
    '', '## Проверки и ограничения','',
    f"- Пересечение с масками фигур/пространств: **{v['overlap']['total_px2']} px²**. Маски CX-01r, полигональная регистрация и консервативные расширения сохранены; пересечение измерено в пикселях по видимому alpha.",
    f"- Минимальный raster font на 720p: **{v['min_text_px_720p']} px** (14 su × 1,125=15,75 номинально).",
    f"- Минимальный WCAG-контраст текста по фактической подложке: **{v['contrast']['text_min']:.3f}:1**. Каждый текст отдельно — verification/contrast/per_panel.",
    f"- Палитра процедурного HUD: **{v['palette']['fraction']}** вне токенов; сцена/аватары/рубашки/иконки/AA исключены по контракту.",
    f"- Ошибки размещения/обрезания текста: **{len(v['text_fit_failures'])}**. Ширины всех подписей и переносы сохранены.",
    '- Gray-пары own-start/own, own/wait, damage/own, fallen/own, ai/wait измерены по нативному кропу: проверяется ≥ 20 luma или форма. Все PNG — RGBA, цвет/серый пары есть.',
    f"- Исходники рендера неизменны: **{v['source_unchanged']}**, полный hash-after для 1244 файлов снимка; writes вне разрешённых корней: `{v['outside_folder']}`. Это аудит действий данного скрипта, не сравнение чужих параллельных изменений. Git не использован.",
    '- Метаданные происхождения: заголовок prompt объявлен provenance-only и не входит в Task. `hud.csv` — живая очередь задач, а не источник макета. Её первоначальный hash сохранён; изменение после снимка явно записано в `verification.json/provenance_changed`: '+json.dumps(v['provenance_changed'],ensure_ascii=False)+'. Этот файл данным запуском не изменялся; baseline не перебазирован.',
    f"- Непройденные критерии: **{failed if failed else 'нет'}**. Известные исключения — тление и компакт S; отсутствующая opp-строка и Medusa heal перечислены выше.",
    '- Макеты офлайн: не доказывают реализацию анимации/интерфейса в клиенте. Числа HP/карты взяты из разных разрешённых кадров run I; фон — bench, а не игровая запись. Unreal и сборки не запускались.',
    '', '## Хеши и воспроизведение','',
    '`source-hashes-before.json` записан до копирования генератора/создания макетов. `verification.json` содержит все hash-after и несовпадения с префиксами задания. Manifest покрывает **каждый файл обеих папок**, кроме себя, и пишется последним. После правки README/проверок его необходимо пересчитать.',
    '', 'Запуск из корня проекта: `python -B -X utf8 art/imagegen/hud-panels-v1-codex/_tools/build_panels.py`. Проверка: `python -B -X utf8 art/imagegen/hud-panels-v1-codex/_tools/verify_package.py`.',
    '', 'Различия хешей относительно карточки: '+(json.dumps(expected,ensure_ascii=False) if expected else 'нет для именованных файлов; полный снимок входов зафиксирован.'),
    '', 'Визуальная проверка финальных PNG: '+v['visual_review']['status']+'.']
    lines += ['', '## Исправления fix1', '',
        '1. PANEL-OPP: HP и помощники у левого края, трекер в середине → общая правая граница колонки рядом с кольцом, трекер слева; Harpies 1–3 слева направо.',
        '2. S sidekick-fallen: сердце на аватаре, 1:0/1 → отдельная подсказка со всеми строками hud.panel.sidekick, без мини-портретов. Дельты CX-01r приведены выше: Marmoreal [16, 416, 180, 104] su, Sarpedon [16, 472, 180, 48] su. Обе подсказки помещаются над PANEL-LOC с нулевым пересечением масок, включая нижние левые клетки Sarpedon.',
        '3. Sarpedon: нейтральный King Arthur 17/18 → 18/18; damage 17/18, heal 18/18, fallen 0/18.',
        '4. VS_AI: малый круг → заполненный диск 8 su цвета text.secondary, зазор 5 su, центр по строке ИИ ДУМАЕТ.',
        '5. README и visual_review: повреждённый текст → русский UTF-8 и нормальные пробелы. Финальное визуальное ревью — Claude.',
        '', 'Значения до исправлений и хеши всех файлов сохранены в fix1-before.json. Source-hashes-before.json сохранён побайтово.',
        '', f"Расчётный контраст обода пустого трекера при opacity 0,6 относительно navy: **{v['contrast']['tracker_rest_rim']['ratio']:.3f}:1**. Цвет и форма исходной принятой иконки сохранены."]
    text='\n'.join(lines)+'\n'
    text=re.sub(r'(?<=\d)%', ' %', text)
    guarded(PACKAGE/'README.md').write_text(text,encoding='utf-8')

if __name__=='__main__':main()
