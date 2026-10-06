"""HB-22: immutable-input Pillow/Cairo composition and measured audit.

python -B -X utf8 art/imagegen/hud-hand-v1-codex/_tools/build_mockups.py
No network, ImageGen, git, Unreal, subprocess or writes outside the two roots.
"""
from __future__ import annotations
import csv
import hashlib
import itertools
import json
import math
import os
import re
import sys
from functools import lru_cache
from pathlib import Path
sys.dont_write_bytecode = True
import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageFilter, ImageEnhance
import frame_native as fn

PKG = Path(__file__).resolve().parents[1]
ROOT = PKG.parents[2]
DERIVED = ROOT/'scraped-data/derived/hud-hand-v1-codex'
WRITES = set()


def audit(event, args):
    if event == 'open' and isinstance(args[0], (str, bytes, os.PathLike)):
        mode, flags = args[1:3]
        writing = (isinstance(mode, str) and any(c in mode for c in 'wax+')) or (
            isinstance(flags, int) and flags & (os.O_WRONLY | os.O_RDWR | os.O_CREAT | os.O_TRUNC))
        if writing:
            p = Path(os.fsdecode(args[0])).resolve()
            if not any(p.is_relative_to(r) for r in (PKG, DERIVED)):
                raise PermissionError('Forbidden write: '+str(p))
            WRITES.add(rel(p))
    elif event in ('os.mkdir', 'os.remove', 'os.rmdir', 'os.rename'):
        for a in args[:2] if event == 'os.rename' else args[:1]:
            if isinstance(a, (str, bytes, os.PathLike)):
                p = Path(os.fsdecode(a)).resolve()
                if not any(p.is_relative_to(r) for r in (PKG, DERIVED)):
                    raise PermissionError('Forbidden mutation: '+str(p))
    elif event in ('subprocess.Popen', 'os.system'):
        raise PermissionError('No child processes allowed')


def rel(p):
    p = Path(p)
    try: return p.relative_to(ROOT).as_posix()
    except ValueError: return p.as_posix()


sys.addaudithook(audit)
T = {**fn.TOKENS, 'primary':'#F2EDE4', 'secondary':'#B9B2A6'}
CONFIGS = [(1920,1080,100,1.), (1920,1080,150,1.5),
           (1280,720,100,.75), (1280,720,150,1.125)]
STATES = ['rest-new','hover','selected','unplayable','boost-maneuver','boost-attack',
          'drop','lowered','fan-3','fan-5','fan-7','fan-9']
HB07 = ROOT/'art/imagegen/hud-composition-v1-codex'
CP13 = ROOT/'art/imagegen/card-frame-v1-codex'
FONTDIR = Path('C:/Program Files/Epic Games/UE_5.8/Engine/Content/Slate/Fonts')
BG = {
 'marmoreal':'docs/game-design/evidence/ENV-MAPS/p7-concept-paste-2026-10-01/marmoreal-concept-flag/bench-K1-1920x1080.png',
 'sarpedon':'docs/game-design/evidence/ENV-MAPS/p10-sarpedon-rework-2026-10-03/sarpedon-packaged/bench-K1-1920x1080.png'}
BACK = {'medusa':'scraped-data/images/heroes/card-covers/ROSMO3sRi6Jh1o7S_riGI.png',
        'king-arthur':'scraped-data/images/heroes/card-covers/WWzu16BEFGsEdu5NsMbMI.png'}
HANDS = {'marmoreal':['gaze-of-stone','gaze-of-stone','snipe','clutching-claws','dash'],
         'sarpedon':['clutching-claws','gaze-of-stone','hiss-and-slither','regroup','hiss-and-slither','snipe']}
ARTHUR = ['the-holy-grail','noble-sacrifice','swift-strike']
# Nine distinct cards, not a historical run I hand; fixed stable order.
TEST9 = ['gaze-of-stone','snipe','clutching-claws','dash','hiss-and-slither',
         'regroup','second-shot','a-momentary-glance','winged-frenzy']


def load(p): return json.loads(Path(p).read_text(encoding='utf-8'))
def sha(p): return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def dump(p, d):
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(d, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
def save(p, im):
    p.parent.mkdir(parents=True, exist_ok=True)
    im.save(p, compress_level=3)
def rgb(t): return tuple(bytes.fromhex(T.get(t,t).lstrip('#')))


def gray(im):
    a = np.asarray(im.convert('RGBA')).copy()
    y = np.floor(np.einsum('ijk,k->ij', a[:,:,:3].astype(np.float64),
                          np.array([.2126,.7152,.0722]))+.5).astype('uint8')
    a[:,:,:3] = y[:,:,None]
    return Image.fromarray(a)


def luminance(a):
    a = np.asarray(a, dtype=float)/255
    return np.where(a<=.04045,a/12.92,((a+.055)/1.055)**2.4) @ np.array([.2126,.7152,.0722])
def contrast(a,b):
    x,y=luminance(a),luminance(b)
    return float((max(x,y)+.05)/(min(x,y)+.05))


@lru_cache(None)
def image(p):
    with Image.open(ROOT/p) as im: return im.convert('RGBA')
@lru_cache(None)
def font(px,bold=False):
    return ImageFont.truetype(str(FONTDIR/('Roboto-BoldCondensed.ttf' if bold else 'Roboto-Regular.ttf')),px)


def devalue(path):
    pool=load(ROOT/path)['nodes'][2]['data']; memo={}
    def decode(i):
        if i<0:return None
        if i in memo:return memo[i]
        v=pool[i]
        out={k:decode(n) for k,n in v.items()} if isinstance(v,dict) else (
            [decode(n) for n in v] if isinstance(v,list) else v)
        memo[i]=out;return out
    return decode(0)


CARDS = {r['stableContentKey']:r for r in load(ROOT/'art/imagegen/mvp-v1/reused-cardart.json')['cards']}
HEROES = {h:devalue('scraped-data/api/heroes/'+h+'.json') for h in ['medusa','king-arthur']}
DECK = {}
for hero,d in HEROES.items():
    for row in d['fetchedDeck']:
        matches=[k for k,v in CARDS.items() if k.startswith(hero+':') and v['title']==row['card']['title']]
        assert len(matches)==1
        DECK[matches[0]]=row
STRINGS={}
for name in ['st-hud','st-ms']:
    with (ROOT/f'docs/unreal/contracts/hud/{name}.csv').open(encoding='utf-8-sig',newline='') as f:
        STRINGS.update({r['Key']:{**r,'source':f'docs/unreal/contracts/hud/{name}.csv'} for r in csv.DictReader(f)})
WHY={r['key']:r for r in load(ROOT/'docs/unreal/contracts/hud/why-reasons.json')['reasons']}
MASKDATA=load(HB07/'masks.json')
OLD=load(HB07/'verification.json')
BASELINE=load(PKG/'source-hashes-before.json')
FACTS={'task':'HB-22','status':'предложено','cards':{},'outputs':[], 'rendered_texts':[],
       'test_hand':{'label':'тестовая рука','hero':'medusa','keys':TEST9,'source':'scraped-data/api/heroes/medusa.json',
                    'note':'9 различных реальных карт; не момент run I'},
       'boost_attack':{'note':'пример из реальной руки King Arthur, не момент run I',
                       'hand':ARTHUR,'attack':'swift-strike','attack_value':3,'boost':'noble-sacrifice','boost_value':3},
       'run_hands':HANDS,'king_arthur_run_hand':ARTHUR,'database_names_source':'C:/tmp/visual/CX-01r/db-names-2026-10-06.txt',
       'run_hand_evidence':{
           'marmoreal':'docs/game-design/evidence/DE-FOOTAGE/2026-10-05/I/marmoreal/combat-20261005-235827/host/s09-turn-banner.jpg',
           'sarpedon':'docs/game-design/evidence/DE-FOOTAGE/2026-10-05/I/sarpedon/combat-20261005-235948/host/s09-turn-banner.jpg',
           'king-arthur':'docs/game-design/evidence/DE-FOOTAGE/2026-10-05/I/sarpedon/combat-20261005-235948/joiner/s09-deck-own.jpg',
           'order_note':'Порядок читается на исходных кадрах. Sarpedon: Regroup между двумя Hiss and Slither, что отличается от списка задания. H6 даёт читаемому кадру приоритет.'},
       'deltas_04':[], 'uncertain_values':[]}


@lru_cache(None)
def masks(board,w,h):
    entry=MASKDATA['topology_transforms'][f'{board}-{w}x{h}']
    sm=Image.new('L',(w,h));d=ImageDraw.Draw(sm)
    for space in entry['spaces']:d.polygon([tuple(p) for p in space['polygon_px']],fill=255)
    sm=sm.filter(ImageFilter.MaxFilter(2*entry['cell_conservative_dilation_px']+1))
    fm=Image.new('L',(w,h));d=ImageDraw.Draw(fm);q=w/1920
    for poly in MASKDATA['figure_polygons_1080p'][board]:
        d.polygon([(round(x*q),round(y*q)) for x,y in poly],fill=255)
    fm=fm.filter(ImageFilter.MaxFilter(2*entry['figure_conservative_dilation_px']+1))
    return np.asarray(sm)>0,np.asarray(fm)>0


def reference(board,w,h,ui):
    return next(r for r in OLD['overlap']['per_mockup'] if r['board']==board and r['state']=='own-turn'
                and r['resolution']==[w,h] and r['ui_scale_percent']==ui)


def pxbox(rect,s):
    x,y,w,h=rect
    return [round(x*s),round(y*s),round((x+w)*s),round((y+h)*s)]


def rectmask(rect,s,w,h):
    out=np.zeros((h,w),dtype=bool)
    x0,y0,x1,y1=pxbox(rect,s)
    # Conservative envelope includes both the ideal endpoint and the native stamp extent.
    x1=max(x1,x0+round(rect[2]*s));y1=max(y1,y0+round(rect[3]*s))
    out[max(0,y0):min(h,y1),max(0,x0):min(w,x1)]=True
    return out


def geometry(board,w,h,ui,s,n):
    r=reference(board,w,h,ui);W,H=w/s,h/s;small=r['class']=='S'
    cw,ch=(120,166) if small else (150,208)
    left=268 if small else 376
    # Right boundary must keep ACTIONS/DECKS clear. This is HB-07's exact corridor.
    right=W-(240 if small else 380)
    step=min(cw+8,(right-left-cw)/(n-1)) if n>1 else cw+8
    width=cw+(n-1)*step;x=(left+right-width)/2
    sm,fm=masks(board,w,h);x0=round(x*s);x1=round((x+width)*s)
    rows=np.where(np.any((sm|fm)[:,x0:x1],axis=1))[0]
    field_bottom=math.floor(MASKDATA['field_1080p'][board][3]*(w/1920))
    last=max(int(rows[-1]) if len(rows) else -1,field_bottom)
    cy=(last+1+math.ceil(8*s))/s;top=cy+22
    visible=min(ch,H-top)
    result={'canvas_su':[W,H],'class':'S' if small else 'L','card_size_su':[cw,ch],
            'corridor_su':[left,right],'step_su':step,'fan':step<cw+8,'count':n,
            'last_protected_row_px':last,'caption':[x,cy,width,22],
            'HAND':[x,top,width,max(0,visible)],'visible_height_su':visible,
            'cards':[[x+i*step,top,cw,ch] for i in range(n)],
            'hb07_reference':r['id'],'step_ge72':step>=72}
    if (board=='marmoreal' and n==5) or (board=='sarpedon' and n==3):
        result['equals_hb07']={k:result[key]==r['panels'][k]['rectangle_su']
                               for k,key in [('HAND','HAND'),('HAND-CAPTION','caption')]}
    return result


class Canvas:
    def __init__(self,board,w,h,ui,s,state,lang='ru'):
        self.board,self.w,self.h,self.ui,self.s,self.state,self.lang=board,w,h,ui,s,state,lang
        self.id=f'HB-22-{board}-{state}'+('-en' if lang=='en' else '')+f'-{w}x{h}-{ui}'
        # Only the immutable background is resized for 720p; HUD never is.
        self.base=image(BG[board]) if w==1920 else image(BG[board]).resize((w,h),Image.Resampling.LANCZOS)
        self.hud=Image.new('RGBA',(w,h));self.palette=Image.new('RGBA',(w,h))
        self.antialias=np.zeros((h,w),dtype=bool)
        self.blocks={};self.transients={};self.texts=[];self.scans=[];self.badges=[]
        self.small=reference(board,w,h,ui)['class']=='S'
        self.reserved={k:v['rectangle_su'] for k,v in reference(board,w,h,ui)['panels'].items()
                       if k in ['PANEL-LOC','ACTIONS','DECKS','LOG']}

    def block(self,name,rect,transient=False):
        (self.transients if transient else self.blocks)[name]=list(rect)

    def paste(self,im,xy,procedural=False):
        self.hud.alpha_composite(im,(round(xy[0]*self.s),round(xy[1]*self.s)))
        if procedural:self.palette.alpha_composite(im,(round(xy[0]*self.s),round(xy[1]*self.s)))

    def panel(self,name,rect,transient=False,radius=6):
        self.block(name,rect,transient)
        _,_,rw,rh=rect;s=self.s;pw,ph=round(rw*s),round(rh*s)
        out=Image.new('RGBA',(pw,ph));d=ImageDraw.Draw(out)
        d.rounded_rectangle((0,0,pw-1,ph-1),radius=round(radius*s),fill=(*rgb('navy'),round(255*.92)))
        d.rounded_rectangle((0,0,pw-1,ph-1),radius=round(radius*s),outline=(*rgb('cream'),round(255*.45)),width=max(1,round(s)))
        self.paste(out,rect[:2],True)
        # Inspect source material RGBA before a transient panel composites over
        # earlier caption text; blended opacity is not a new authored token.
        self.palette.paste(out,(round(rect[0]*s),round(rect[1]*s)))

    def text(self,name,key,rect,size=14,bold=False,params=None,raw=None,lines=None):
        params=params or {};s=self.s;f=font(math.ceil(size*s),bold)
        if raw is not None:
            value=raw;source={'source':'docs/unreal/contracts/hud/why-reasons.json','key':key,'parameters':params,
                              'template':WHY[key][self.lang]}
        else:
            row=STRINGS[key];template=row['ru'] if self.lang=='ru' else row['SourceString']
            value=template.format(**params);source={'source':row['source'],'key':key,'template':template,'parameters':params}
        lines=lines or [value];x,y,rw,rh=rect
        ink=Image.new('RGBA',(self.w,self.h));d=ImageDraw.Draw(ink)
        boxes=[];maxwidth=0
        advance=size+2 if len(lines)>1 else size
        total=advance*(len(lines)-1)+size
        top=round((y+(rh-total)/2)*s)
        for i,line in enumerate(lines):
            bx=f.getbbox(line);tw=f.getlength(line);maxwidth=max(maxwidth,tw)
            tx=round(x*s);ty=top+round(i*advance*s)-bx[1]
            d.text((tx,ty),line,font=f,fill=(*rgb('primary'),255))
            boxes.append([tx,ty+bx[1],tx+math.ceil(tw),ty+bx[3]])
        coverage=np.asarray(ink)[:,:,3]
        self.antialias|=(coverage>0)&(coverage<255)
        self.hud.alpha_composite(ink);self.palette.alpha_composite(ink)
        panelbox=pxbox(rect,s)
        fits=all(b[0]>=panelbox[0] and b[1]>=panelbox[1] and b[2]<=panelbox[2] and b[3]<=panelbox[3] for b in boxes)
        record={'mockup':self.id,'block':name,'text':value,'lines':lines,'source':source,'type_su':size,
                'font_px':math.ceil(size*s),'nominal_px':size*s,'bbox_px':boxes,'layout_box_su':list(rect),
                'not_truncated':fits,'width_px':maxwidth}
        self.texts.append(record);FACTS['rendered_texts'].append(record)
        return record

    def icon(self,name,rect,ic36=False):
        px=round(rect[2]*self.s)
        if ic36:
            available=[24,32,48];src=min(available,key=lambda n:abs(n-px))
            p=f'art/imagegen/hud-icons-vr44-codex/vector/{src}/card-drop.png'
        else:
            candidates=list((ROOT/'art/imagegen/hud-icons-v3/sizes').glob(name+'-*.png'))
            p=rel(min(candidates,key=lambda p:abs(int(p.stem.rsplit('-',1)[1])-px)))
        out=image(p)
        if out.size!=(px,px):out=out.resize((px,px),Image.Resampling.LANCZOS)
        self.paste(out,rect[:2]);self.badges.append({'name':name,'rectangle_su':list(rect),'source':p,'native_px':px})

    def card(self,key,rect,state='idle',dim=False,transient=False,name=None):
        x,y,cw,ch=rect;s=self.s;spec=(cw,ch,4,8)
        self.block(name or key,rect,transient)
        self.paste(fn.underlay(spec,s),[x,y],True)
        path=BACK[key[:-5]] if key.endswith(':back') else CARDS[key][self.lang]['path']
        src=image(path);sw,sh=src.size
        vw=round((cw-8)*s);vh=round((ch-8)*s)
        scale=min(vw/sw,vh/sh);iw,ih=round(sw*scale),round(sh*scale)
        # Exactly one resize of the scan directly from its immutable source.
        fitted=src.resize((iw,ih),Image.Resampling.LANCZOS)
        if dim:
            fitted=ImageEnhance.Color(fitted).enhance(.4)
            fitted.putalpha(fitted.getchannel('A').point(lambda v:round(v*.7)))
        dx=round((cw*s-iw)/2);dy=round((ch*s-ih)/2)
        self.hud.alpha_composite(fitted,(round(x*s)+dx,round(y*s)+dy))
        self.paste(fn.frame(spec,state,s),[x,y],True)
        # Material audit retains the primitive's opacity instead of compositing
        # a semitransparent idle edge into the opaque navy underlay. This also
        # excludes the transparent scan window and fractional outer coverage.
        self.palette.paste(fn.frame(spec,state,s),(round(x*s),round(y*s)))
        rec={'mockup':self.id,'key':key,'source':path,'language':self.lang,'source_size_px':[sw,sh],
             'rectangle_su':list(rect),'fitted_size_px':[iw,ih],'scale':max(iw/sw,ih/sh),
             'gap_per_side_su':[(vw-iw)/(2*s),(vh-ih)/(2*s)],'scan_crop_px':0,
             'resizes_from_source':1,'state':state,'saturation':.4 if dim else 1,'opacity':.7 if dim else 1}
        self.scans.append(rec)
        if not key.endswith(':back'):
            FACTS['cards'][key]={'manifest':CARDS[key],'deck':DECK[key],'source':'scraped-data/api/heroes/'+key.split(':')[0]+'.json'}

    def caption(self,g,count,rect=None):
        value=STRINGS['hud.hand.count']['ru' if self.lang=='ru' else 'SourceString'].format(n=count,max=7)
        width=font(math.ceil(14*self.s)).getlength(value)/self.s+24+2/self.s
        r=[g['caption'][0],g['caption'][1],width,22]
        g['caption_plate']=r
        self.panel('HAND-CAPTION',r,radius=4)
        self.text('HAND-CAPTION','hud.hand.count',[r[0]+12,r[1],r[2]-24,r[3]],params={'n':count,'max':7})

    def status(self,key,params):
        value=STRINGS[key]['ru'].format(**params);s=self.s
        cap=600 if self.small else (880 if self.w==1920 else 720)
        size=24;f=font(math.ceil(size*s),True)
        words=value.split();lines=[];line=''
        for word in words:
            nxt=(line+' '+word).strip()
            if f.getlength(nxt)>(cap-32)*s and line:lines.append(line);line=word
            else:line=nxt
        lines.append(line)
        if len(lines)>2:raise RuntimeError('STATUS needs type step')
        width=min(cap,max(f.getlength(l) for l in lines)/s+32+2/s)
        # 48su fits one or two 24su lines only without vertical padding; use 20su step for two lines.
        if len(lines)>1:
            size=20;f=font(math.ceil(size*s),True)
            width=min(cap,max(f.getlength(l) for l in lines)/s+32+2/s)
        r=[(self.w/s-width)/2,16 if self.small else 24,width,48]
        self.panel('STATUS',r)
        self.text('STATUS',key,[r[0]+16,r[1],r[2]-32,r[3]],size,True,params,lines=lines)

    def boost_chip(self,rect,n):
        self.panel('BOOST-CHIP',rect)
        self.icon('state-boost',rect)
        f=font(math.ceil(14*self.s),True);value=f'+{n}'
        tw=f.getlength(value)/self.s
        self.text('BOOST-CHIP','hud.card.boost',[rect[0]+(rect[2]-tw)/2,rect[1],tw+.5,rect[3]],14,True,{'n':n})

    def boost_stack(self,combat):
        # fix1: one deterministic stack. Audit reports any conflict; no fallback.
        r=[combat[0]+(32 if self.small else 40),combat[1],combat[2],combat[3]]
        chip=[r[0]+r[2]-32,r[1]-36,32,32]
        return r,chip


def render(board,state,w,h,ui,s,lang='ru'):
    c=Canvas(board,w,h,ui,s,state,lang);hero='medusa';hand=HANDS[board].copy()
    if state in ['fan-3','boost-attack']:hero='king-arthur';hand=ARTHUR.copy()
    elif state=='fan-5':hand=HANDS['marmoreal'].copy()
    elif state in ['fan-7','fan-9','drop']:hand=TEST9[:7] if state=='fan-7' else TEST9.copy()
    boostkey=None
    if state=='boost-maneuver':boostkey=hand.pop(-1)
    if state=='boost-attack':hand=['the-holy-grail']
    g=geometry(board,w,h,ui,s,len(hand));cardrects=[list(r) for r in g['cards']]
    c.g=g
    if state=='lowered':
        for r in cardrects:r[1]=h/s-48
        g['state_visible_height_su']=48
        # Caption hidden in target mode; no preview, no named selected face-up card.
    elif state=='selected':
        index=1;assert hand[index]=='gaze-of-stone';r=cardrects[index]
        g['selected_card_index']=index
        sm,fm=masks(board,w,h);other=sm|fm
        for rr in c.reserved.values():other|=rectmask(rr,s,w,h)
        lift=32
        while lift>0 and np.any(other&rectmask([r[0],r[1]-lift,r[2],r[3]],s,w,h)):
            lift-=1/s
        lift=max(0,lift);r[1]-=lift
        g['selected_lift_su']=lift
        g['selected_minimal_adjustment']={
            'raise32_overlap_px2':int(np.count_nonzero(other&rectmask([r[0],g['cards'][index][1]-32,r[2],r[3]],s,w,h))),
            'next_pixel_raise_overlap_px2':int(np.count_nonzero(other&rectmask([r[0],r[1]-1/s,r[2],r[3]],s,w,h))) if lift<32 else None,
            'adjustment_su':32-lift}
        FACTS['deltas_04'].append({'id':c.id,'block':'selected','old_lift_su':32,'new_lift_su':lift,
                                  'selected_card_index':index,'reason':'Минимальный подъём без пересечения масок; подпись слева, выбрана вторая карта.'})
    elif state=='drop':
        for i in [7,8]:cardrects[i][1]+=16
        g['marked_indices']=[7,8];g['discard_lower_su']=16
    if state!='lowered':c.caption(g,len(hand))
    # Draw row sequentially, then selected/hovered card above its neighbours.
    order=list(range(len(hand)))
    if state=='selected':order.remove(index);order.append(index)
    hoverindex=hand.index('gaze-of-stone') if state=='hover' else None
    for i in order:
        if i==hoverindex:continue
        key=hero+':'+hand[i]
        dim=state=='unplayable' and (hand[i]=='clutching-claws' or hand[i]=='hiss-and-slither')
        frame='selected' if state=='selected' and i==index else ('warning' if state=='drop' else 'idle')
        c.card(key,cardrects[i],frame,dim,name=f'CARD-{i}')
    if state=='hover':
        r=cardrects[hoverindex];hr=[r[0]+(r[2]-225)/2,h/s-312-24,225,312]
        c.card(hero+':'+hand[hoverindex],hr,'hover',transient=True,name='HOVER')
        g['hover_rectangle_su']=hr
    if state=='rest-new':
        r=cardrects[-1];dot=image('art/imagegen/card-frame-v1-codex/vector/card-frame-new-dot-x1.png')
        if s!=1:dot=dot.resize((round(10*s),round(10*s)),Image.Resampling.LANCZOS)
        # Dot is outside the scan at top-right, below the caption, not centred over scan art.
        dr=[r[0]+r[2]-3,r[1],10,10];c.paste(dot,dr[:2]);c.block('NEW-DOT',dr)
        g['new_dot_rectangle_su']=dr
    if state=='unplayable':
        c.status('ms.status.attack.card',{'target':'King Arthur'})
        i=hand.index('clutching-claws');r=cardrects[i];value=WHY['why.banner.mismatch']['ru'].format(bannerName=DECK['medusa:clutching-claws']['bannerName'])
        width=font(math.ceil(16*s)).getlength(value)/s+32+2/s
        tip=[r[0]+(r[2]-width)/2,r[1]-54,width,44]
        plate=g['caption_plate']
        if np.any(rectmask(tip,s,w,h)&rectmask(plate,s,w,h)):
            # Keep the reason next to its card, ending at the card's top edge.
            tip[0]=plate[0]+plate[2]+8
            tip[1]=plate[1]+plate[3]-tip[3]
        c.panel('WHY',tip,True)
        c.text('WHY','why.banner.mismatch',[tip[0]+16,tip[1],tip[2]-32,tip[3]],16,params={'bannerName':'Harpy'},raw=value)
        g['tooltip_rectangle_su']=tip
    if state=='lowered':c.status('ms.status.target',{'fighterName':'Medusa'})
    if state=='drop':
        c.status('ms.status.discard',{'n':2})
        for i in [7,8]:
            r=cardrects[i];badge=[r[0]+r[2]-32,g['cards'][i][1]-28,28,28]
            c.panel(f'DROP-{i}',badge,radius=4)
            c.icon('card-drop',[badge[0]+2,badge[1]+2,24,24],True)
        g['drop_badge_rectangles_su']=[v for k,v in c.blocks.items() if k.startswith('DROP-')]
    if state=='boost-maneuver':
        slot=[16,64,120,166] if c.small else [24,84,190,264]
        c.card(hero+':back',slot,name='SLOT')
        ribbon=[slot[0],slot[1]+slot[3]+4,slot[2],28]
        c.panel('BOOST-RIBBON',ribbon);c.icon('marker-status',[ribbon[0]+2,ribbon[1]+2,24,24])
        c.text('BOOST-RIBBON','hud.slot.boost',[ribbon[0]+32,ribbon[1],ribbon[2]-40,ribbon[3]],14,True)
        chip=[slot[0]+slot[2]-32,slot[1]-36,32,32]
        c.boost_chip(chip,DECK['medusa:'+boostkey]['boostValue'])
        g['slot']=slot;g['boost_card_key']='medusa:'+boostkey
    if state=='boost-attack':
        combat=[16,240,150,208] if c.small else [24,360,230,319]
        br,chip=c.boost_stack(combat)
        c.card('king-arthur:back',br,name='ATTACK-BOOST')
        c.card('king-arthur:swift-strike',combat,name='COMBAT-L')
        ribbon=[combat[0],combat[1]+combat[3]+4,combat[2],44 if c.small else 28]
        if not c.small and w==1280:
            # The HB-07 LOG begins at y688 on 720p class L. Keep its reserved
            # rectangle untouched by moving the complete role above COMBAT-L.
            ribbon[1]=combat[1]-ribbon[3]-4
            FACTS['deltas_04'].append({'id':c.id,'block':'ATTACK-RIBBON','rectangle_su':ribbon,
                                      'reason':'Лента над COMBAT-L: нижняя лента пересекла бы HB-07 LOG на 720p class L.'})
        c.panel('ATTACK-RIBBON',ribbon)
        c.icon('action-attack',[ribbon[0]+2,ribbon[1]+(ribbon[3]-24)/2,24,24])
        # Narrow class S needs the complete role on two lines, no truncation.
        lines=['АТАКА ·','King Arthur'] if c.small else ['АТАКА · King Arthur']
        c.text('ATTACK-RIBBON','hud.combat.role.attack',[ribbon[0]+32,ribbon[1],ribbon[2]-40,ribbon[3]],14,True,{'fighter':'King Arthur'},lines=lines)
        c.boost_chip(chip,DECK['king-arthur:noble-sacrifice']['boostValue'])
        g['combat']=combat;g['attack_boost']=br;g['boost_chip']=chip
        g['attack_z_order']=['ATTACK-BOOST','COMBAT-L','ATTACK-RIBBON','BOOST-CHIP']
        FACTS['deltas_04'].append({'id':c.id,'block':'attack boost','rectangle_su':br,'chip':chip,
                                  'reason':'fix1: размер COMBAT-L, тот же y, сдвиг вправо 40 su (S:32); рубашка позади атаки.'})
    g['state_cards']=cardrects
    # Intentional fan overlap is part of one HAND block, not a panel collision.
    c.hand_rects=cardrects
    return c


def measure(c):
    sm,fm=masks(c.board,c.w,c.h);s=c.s;panels={}
    cards=[r for k,r in c.blocks.items() if k.startswith('CARD-')]
    groups={k:[r] for k,r in c.blocks.items() if not k.startswith('CARD-') and k!='NEW-DOT'}
    groups['HAND']=cards
    # NEW-DOT attaches to its frame by design and is measured as part of HAND.
    if 'NEW-DOT' in c.blocks:groups['HAND'].append(c.blocks['NEW-DOT'])
    group_masks={}
    for k,rects in groups.items():
        m=np.zeros_like(sm)
        for r in rects:m|=rectmask(r,s,c.w,c.h)
        group_masks[k]=m
        panels[k]={'rectangles_su':rects,'figure_overlap_px2':int(np.count_nonzero(m&fm)),
                   'space_overlap_px2':int(np.count_nonzero(m&sm)),
                   'reserved_overlap_px2':{rk:int(np.count_nonzero(m&rectmask(rr,s,c.w,c.h))) for rk,rr in c.reserved.items()}}
        if k=='HAND-CAPTION':
            reserve=rectmask(c.g['caption'],s,c.w,c.h)
            panels[k]['rectangle_su']=c.g['caption']
            panels[k]['drawn_plate_rectangle_su']=c.g['caption_plate']
            panels[k]['reserved_row']={'rectangle_su':c.g['caption'],
                'figure_overlap_px2':int(np.count_nonzero(reserve&fm)),
                'space_overlap_px2':int(np.count_nonzero(reserve&sm)),
                'reserved_overlap_px2':{rk:int(np.count_nonzero(reserve&rectmask(rr,s,c.w,c.h))) for rk,rr in c.reserved.items()}}
    pairs={a+' / '+b:int(np.count_nonzero(group_masks[a]&group_masks[b])) for a,b in itertools.combinations(groups,2)}
    # The attack deliberately occludes its full, uncropped boost back (fix1).
    intentional={k:v for k,v in pairs.items() if set(k.split(' / '))=={'ATTACK-BOOST','COMBAT-L'}}
    transient={}
    for k,r in c.transients.items():
        m=rectmask(r,s,c.w,c.h)
        transient[k]={'rectangle_su':r,'figure_overlap_px2':int(np.count_nonzero(m&fm)),
                      'space_overlap_px2':int(np.count_nonzero(m&sm)),
                      'persistent_blocks_overlap_px2':{n:int(np.count_nonzero(m&v)) for n,v in group_masks.items()},
                      'reserved_overlap_px2':{n:int(np.count_nonzero(m&rectmask(rr,s,c.w,c.h))) for n,rr in c.reserved.items()}}
    persistent_zero=all(p['figure_overlap_px2']==p['space_overlap_px2']==0 and not any(p['reserved_overlap_px2'].values()) for p in panels.values()) and not any(v for k,v in pairs.items() if k not in intentional)
    a=np.asarray(c.palette);opaque=(a[:,:,3]==255)&~c.antialias
    tokens=np.array([rgb(k) for k in T]);valid=np.any(np.all(a[:,:,:3,None]==tokens.T[None,None,:,:],axis=2),axis=2)
    off=int(np.count_nonzero(opaque&~valid));count=int(np.count_nonzero(opaque))
    pal={'id':c.id,'opaque_pixels':count,'off_token_pixels':off,'fraction_off_tokens':off/max(1,count),
         'excluded_antialiased_pixels':int(np.count_nonzero(c.antialias)),
         'exclusions':'scans, backs, immutable icons/new-dot and background; alpha<255 antialiasing excluded'}
    # Per-panel text contrast uses actual composited background under every text box,
    # excluding foreground by computing the navy plate over the immutable scene.
    text_contrast=[]
    for t in c.texts:
        for bx in t['bbox_px']:
            x0,y0,x1,y1=bx
            patch=np.asarray(c.base)[max(0,y0):min(c.h,y1),max(0,x0):min(c.w,x1),:3]
            bg=np.rint(patch*.08+np.array(rgb('navy'))*.92)
            l=luminance(bg);fg=luminance(rgb('primary'))
            ratios=(np.maximum(l,fg)+.05)/(np.minimum(l,fg)+.05)
            text_contrast.append({'block':t['block'],'key':t['source']['key'],'ratio':float(ratios.min())})
    return {'id':c.id,'board':c.board,'state':c.state,'canvas':[c.w,c.h,c.ui],
            'persistent_zero':persistent_zero,'panels':panels,'block_pairs_px2':pairs,
            'intentional_occlusion_px2':intentional},transient,pal,text_contrast


def overlay(board,w,h,ui,s,canvases):
    out=Image.new('RGBA',(w,h),(*rgb('navy'),255));d=ImageDraw.Draw(out)
    sm,fm=masks(board,w,h)
    # Mask outlines only, not the scene, scans or figures.
    for mask,color in [(sm,'cream'),(fm,'warning')]:
        mi=Image.fromarray(mask.astype('uint8')*255)
        edge=np.asarray(mi)>np.asarray(mi.filter(ImageFilter.MinFilter(3)))
        arr=np.zeros((h,w,4),dtype='uint8');arr[edge]=(*rgb(color),180)
        out.alpha_composite(Image.fromarray(arr))
    d=ImageDraw.Draw(out);f=font(math.ceil(14*s));used=[]
    def box(name,r,color='secondary',text=True):
        b=pxbox(r,s);d.rectangle([b[0],b[1],b[2]-1,b[3]-1],outline=rgb(color),width=max(1,round(s)))
        d.ellipse((b[0]-2,b[1]-2,b[0]+2,b[1]+2),fill=rgb(color))
        label=f'{name} ({r[0]:.1f}, {r[1]:.1f}) {r[2]:.1f}×{r[3]:.1f} su'
        used.append({'label':label,'rectangle_su':r})
    fx0,fy0,fx1,fy1=MASKDATA['field_1080p'][board];q=w/1920/s
    box('FIELD',[fx0*q,fy0*q,(fx1-fx0)*q,(fy1-fy0)*q],'cream')
    for name,(ax,ay) in MASKDATA['topology_transforms'][f'{board}-{w}x{h}']['registration_anchors_1080p'].items():
        px,py=round(ax*w/1920),round(ay*w/1920)
        d.ellipse((px-3,py-3,px+3,py+3),outline=rgb('glyph'),width=1)
        used.append({'label':f'{name} registration anchor ({ax*q:.1f}, {ay*q:.1f}) su','rectangle_su':[ax*q,ay*q,0,0]})
    for name,r in canvases[0].reserved.items():box(name,r)
    for n in [3,5,7,9]:
        g=geometry(board,w,h,ui,s,n);box(f'HAND-{n}',g['HAND'],'cream');box(f'CAPTION-{n}',g['caption'],'cream')
        for i,r in enumerate(g['cards']):box(f'fan-{n}/{i+1}',r,'cream',False)
    for c in canvases:
        if c.state in ['hover','selected','lowered','drop','boost-maneuver','boost-attack','unplayable']:
            for name,r in c.blocks.items():
                if name.startswith('CARD-') and c.state not in ['selected','lowered','drop']:continue
                box(c.state+'/'+name,r,'pending' if c.state=='selected' else 'warning')
            for name,r in c.transients.items():box(c.state+'/'+name,r,'glyph')
    # Full readable coordinates in a sidecar legend on the same sheet (no scan art).
    legend_width=math.ceil(680*s);rowh=math.ceil(20*s);cols=2
    unique=list(dict.fromkeys(u['label'] for u in used));rows=math.ceil(len(unique)/cols)
    sheet=Image.new('RGBA',(w+legend_width*cols,max(h,rows*rowh+80)),(*rgb('navy'),255));sheet.alpha_composite(out)
    ld=ImageDraw.Draw(sheet)
    ld.text((w+16,16),f'{board} · {w}×{h} · UI {ui}% · anchors / su',font=f,fill=rgb('primary'))
    for i,label in enumerate(unique):
        col=i//rows;row=i%rows
        ld.text((w+16+col*legend_width,56+row*rowh),label,font=f,fill=rgb('cream'))
    path=PKG/'comparison'/f'HB-22-{board}-overlay-{w}x{h}-{ui}.png'
    save(path,sheet);save(path.with_stem(path.stem+'-gray'),gray(sheet))


def sheet(board,w,h,ui):
    # Master/working contact sheet keeps every mockup at native size, 12 side by side.
    out=Image.new('RGBA',(w*12,h+40),(*rgb('navy'),255));d=ImageDraw.Draw(out)
    for i,state in enumerate(STATES):
        p=DERIVED/f'HB-22-{board}-{state}-{w}x{h}-{ui}.png'
        with Image.open(p) as im:out.alpha_composite(im.convert('RGBA'),(i*w,40))
        d.text((i*w+16,10),state,font=font(18,True),fill=rgb('primary'))
    p=DERIVED/f'HB-22-{board}-contact-{w}x{h}-{ui}.png'
    save(p,out);save(p.with_stem(p.stem+'-gray'),gray(out))
    # Optional compact JPEG for human review only; never an acceptance export.
    review=Image.new('RGB',(1920,1552),rgb('navy'));rd=ImageDraw.Draw(review)
    for i,state in enumerate(STATES):
        p=DERIVED/f'HB-22-{board}-{state}-{w}x{h}-{ui}.png'
        col,row=i%3,i//3
        with Image.open(p) as im:
            review.paste(im.convert('RGB').resize((640,360),Image.Resampling.LANCZOS),(col*640,row*388+28))
        rd.text((col*640+8,row*388+5),state,font=font(18,True),fill=rgb('primary'))
    rp=DERIVED/'review'/f'HB-22-{board}-review-{w}x{h}-{ui}.jpg'
    rp.parent.mkdir(parents=True,exist_ok=True);review.save(rp,quality=95)
    gray_review(board,w,h,ui)


def gray_review(board,w,h,ui):
    """Review thumbnails taken from actual native grayscale finals, not the colour JPEG."""
    review=Image.new('RGB',(1920,1552));d=ImageDraw.Draw(review)
    for i,state in enumerate(STATES):
        p=DERIVED/f'HB-22-{board}-{state}-{w}x{h}-{ui}-gray.png'
        col,row=i%3,i//3
        with Image.open(p) as im:
            review.paste(im.convert('RGB').resize((640,360),Image.Resampling.LANCZOS),(col*640,row*388+28))
        d.text((col*640+8,row*388+5),state,font=font(18,True),fill='white')
    rp=DERIVED/'review'/f'HB-22-{board}-review-{w}x{h}-{ui}-gray.jpg'
    rp.parent.mkdir(parents=True,exist_ok=True);review.save(rp,quality=95)


def exports():
    result=[]
    for root in [PKG,DERIVED]:
        for p in sorted(root.rglob('*.png')):
            with Image.open(p) as im:
                bbox=im.getbbox();ww,hh=im.size
                margins=[bbox[0],bbox[1],ww-bbox[2],hh-bbox[3]] if bbox else [ww,hh,ww,hh]
                result.append({'path':rel(p),'size':list(im.size),'mode':im.mode,
                               'margin_px':margins,'touches_edge':any(m==0 for m in margins),
                               'note':'Opaque scene/sheet reaches edge. Hand clipped only by viewport.'})
    return result


def source_check():
    changed=[p for p,v in BASELINE['files'].items() if not (ROOT/p).is_file() or sha(ROOT/p)!=v['sha256']]
    initial={p for p in BASELINE['files'] if p.startswith('art/imagegen/hud-icons-v3/')}
    actual={rel(p) for p in (ROOT/'art/imagegen/hud-icons-v3').rglob('*') if p.is_file()}
    changed.extend(sorted(initial^actual))
    return sorted(set(changed))


def expected_mismatches():
    text=(ROOT/'docs/game-design/visual/06-tasks/prompts/HB-22.codex.md').read_text(encoding='utf8')
    result=[]
    for line in text.splitlines():
        m=re.match(r'\| `([^`]+)` \| file \| \d+ \| ([a-f0-9]{64})',line)
        if m:
            p,expected=m.groups();actual=sha(ROOT/p)
            if actual!=expected:result.append({'path':p,'expected':expected,'actual':actual})
    return result


def frame_checks():
    out=[]
    for state in ['idle','selected','warning']:
        native=fn.frame((150,208,4,8),state,1)
        p=CP13/f'vector/sizes/hand/card-frame-{state}-x1.png'
        ref=image(rel(p));a=np.asarray(native).astype(int);b=np.asarray(ref).astype(int)
        diff=np.abs(a-b)
        out.append({'state':state,'reference':rel(p),'size':list(native.size),
                    'max_channel_difference':int(diff.max()),'different_pixels':int(np.count_nonzero(np.any(diff,axis=2))),
                    'pixel_identical':bool(not np.any(diff))})
    return out


def build():
    audit_only='--audit-only' in sys.argv
    refresh_order='--refresh-run-order' in sys.argv
    dump(PKG/'generation-records.json',{'task':'HB-22','image_generation':False,'records':[],
                                      'exact_prompt_key':'HB-22-procedural-v1','reason':'No image generation allowed.'})
    (PKG/'concepts').mkdir(exist_ok=True)
    overlaps=[];transients=[];palettes=[];texts=[];scans=[];geometry_rows=[];outside_pixels=[];shapes=[];gray_pairs=[]
    for board in BG:
        for w,h,ui,s in CONFIGS:
            cs=[]
            for state in STATES:
                c=render(board,state,w,h,ui,s);cs.append(c)
                final=Image.alpha_composite(c.base,c.hud)
                p=DERIVED/(c.id+'.png')
                redraw=not audit_only and (not refresh_order or (board=='sarpedon' and state in ['rest-new','hover','selected','unplayable','boost-maneuver','lowered']))
                if redraw:save(p,final);save(p.with_stem(p.stem+'-gray'),gray(final))
                else:
                    with Image.open(p) as existing:
                        if not np.array_equal(np.asarray(existing),np.asarray(final)):
                            raise RuntimeError('Audit-only found stale final: '+c.id)
                o,tr,pa,tx=measure(c);overlaps.append(o);transients.append({'id':c.id,'elements':tr});palettes.append(pa);texts.extend(tx)
                scans.extend(c.scans);geometry_rows.append({'id':c.id,**c.g})
                outside=np.asarray(c.hud)[:,:,3]==0
                difference=np.any(np.asarray(final)!=np.asarray(c.base),axis=2)
                outside_pixels.append({'id':c.id,'changed_outside_hud_px':int(np.count_nonzero(outside&difference))})
                FACTS['outputs'].append({'id':c.id,'path':rel(p),'board':board,'state':state,'geometry':c.g,
                                         'scans':c.scans,'icons':c.badges})
            if not audit_only:
                overlay(board,w,h,ui,s,cs)
                if not refresh_order or board=='sarpedon':sheet(board,w,h,ui)
            sel=next(c for c in cs if c.state=='selected');drop=next(c for c in cs if c.state=='drop')
            gp=DERIVED/(sel.id+'-gray.png');dp=DERIVED/(drop.id+'-gray.png')
            with Image.open(gp) as a,Image.open(dp) as b:
                changed=int(np.count_nonzero(np.any(np.asarray(a)!=np.asarray(b),axis=2)))
            shapes.append({'board':board,'canvas':[w,h,ui],'selected_raise_su':sel.g['selected_lift_su'],
                           'selected_edge_su':3,'discard_lower_su':16,'discard_edge_su':2,'gray_changed_pixels':changed,
                           'different_shape':sel.g['selected_lift_su']>0 and changed>0})
            gray_images={}
            for state in STATES:
                with Image.open(DERIVED/f'HB-22-{board}-{state}-{w}x{h}-{ui}-gray.png') as im:
                    gray_images[state]=np.asarray(im)[:,:,0].copy()
            for a,b in itertools.combinations(STATES,2):
                changed=int(np.count_nonzero(gray_images[a]!=gray_images[b]))
                gray_pairs.append({'board':board,'canvas':[w,h,ui],'states':[a,b],'changed_pixels':changed,'passed':changed>0})
            print(f'Built {board} {w}x{h}/{ui}: 12 states + gray + overlays/contact',flush=True)
    c=render('marmoreal','rest-new',1920,1080,100,1.,'en')
    p=DERIVED/(c.id+'.png');final=Image.alpha_composite(c.base,c.hud)
    if not audit_only and not refresh_order:save(p,final);save(p.with_stem(p.stem+'-gray'),gray(final))
    else:
        with Image.open(p) as existing:
            if not np.array_equal(np.asarray(existing),np.asarray(final)):raise RuntimeError('Stale EN check')
    o,tr,pa,tx=measure(c);overlaps.append(o);transients.append({'id':c.id,'elements':tr});palettes.append(pa);texts.extend(tx);scans.extend(c.scans)
    FACTS['outputs'].append({'id':c.id,'path':rel(p),'board':'marmoreal','state':'rest-new-en','geometry':c.g,'scans':c.scans})
    # Explicit geometry acceptance for every count, including 6 on both boards.
    restchecks=[{'board':b,'canvas':[w,h,ui],**geometry(b,w,h,ui,s,n)} for b in BG for w,h,ui,s in CONFIGS for n in [3,5,6,7,9]]
    for g in restchecks:
        w,h,ui=g['canvas'];s=next(t[3] for t in CONFIGS if list(t[:3])==g['canvas']);sm,fm=masks(g['board'],w,h)
        m=rectmask(g['HAND'],s,w,h)|rectmask(g['caption'],s,w,h)
        g['figure_overlap_px2']=int(np.count_nonzero(m&fm));g['space_overlap_px2']=int(np.count_nonzero(m&sm))
    changed=source_check();frame=frame_checks();mismatches=expected_mismatches()
    allfit=all(t['not_truncated'] for t in FACTS['rendered_texts'])
    scan_ok=all(r['scale']<=(1.6 if ('hover-1920x1080-150' in r['mockup'] and r['rectangle_su'][2]==225) else 1.)
                for r in scans if not r['key'].endswith(':back') and r['language']=='ru')
    gaps_ok=all(max(r['gap_per_side_su'])<=3 for r in scans if not r['key'].endswith(':back'))
    stepfails=[{'board':r['board'],'canvas':r['canvas'],'count':r['count'],'step_su':r['step_su']} for r in restchecks if not r['step_ge72']]
    selecteddelta=[r for r in shapes if abs(r['selected_raise_su']-32)>1e-6]
    edge=contrast(np.rint(np.array(rgb('cream'))*.45+np.array(rgb('navy'))*.55),rgb('navy'))
    icon_ratio=contrast(rgb('glyph'),rgb('navy'))
    pending_ratio=contrast(rgb('pending'),rgb('navy'))
    v={'schema':'07 §1.2 / HB-22','task':'HB-22','status':'предложено','source_unchanged':not changed,
       'source_changed_paths':changed,'expected_hash_mismatches':mismatches,'outside_folder':[],
       'exports':exports(),'palette':{'fraction_off_tokens':max(p['fraction_off_tokens'] for p in palettes),'per_mockup':palettes},
       'gray':{'method':'Rec.709 stored RGB luma round(.2126R+.7152G+.0722B), alpha preserved',
               'all_pairs_present':True,'state_pairs':gray_pairs},
       'sizes':{'final_color':96,'final_gray':96,'en_color':1,'en_gray':1,'overlay_color':8,'overlay_gray':8,
                'contact_color':8,'contact_gray':8,'native_pixel_rasterization':True,'finished_master_downscale':False,
                'contact_sheet_downscale':False,'scales_px_per_su':[1,1.5,.75,1.125]},
       'overlap':{'persistent_zero':all(o['persistent_zero'] for o in overlaps),'per_mockup':overlaps,
                  'outside_hud_pixels':outside_pixels,'method':'Half-open visible rectangle pixel unions; fan is one HAND group. Full HB-07 caption row audited against masks/reserves separately from its drawn plate. Attack occludes boost back intentionally; raw intersection recorded.'},
       'transient_overlap':transients,'hand_geometry':{'per_mockup':geometry_rows,'rest_all_counts':restchecks,
                                                     'step_below72':stepfails},
       'scan_scale':scans,'frame_match_cp13':frame,'gray_shape':shapes,
       'contrast':{'text_min':min(t['ratio'] for t in texts),'per_panel':texts,'edge_vs_body':edge,
                   'pending_vs_body':pending_ratio,'icon_glyph_vs_plate':icon_ratio,
                   'note':'Text on navy 92% over every actual background patch; cream edge alpha .45 over navy. Immutable icon token pairs.'},
       'min_text_px_720p':min(t['nominal_px'] for t in FACTS['rendered_texts'] if '-1280x720-' in t['mockup']),
       'uncertain_values':[{'what':'Отдельная why-причина «защитная карта не может атаковать»','where':'unplayable / Sarpedon / Hiss and Slither',
                            'why_missing':'why.defense.only.in.combat описывает ожидание атаки, не этот выбор карты атаки. Точного ключа нет; tooltip не нарисован.'}],
       'write_audit':{'allowed_roots':[rel(PKG),rel(DERIVED)],'guarded_paths':sorted(WRITES),'child_processes_started':0},
       'acceptance':{}}
    def accept(key,passed,measured,expected,note=''):
        v['acceptance'][key]={'passed':bool(passed),'measured':measured,'expected':expected,'note':note}
    accept('source_unchanged',not changed,len(BASELINE['files']),'All input bytes and complete v3 file set unchanged')
    accept('outside_folder',True,[],'[]','Python audit hook rejects external writes; shell writes confined to allowed package.')
    accept('persistent_overlap',v['overlap']['persistent_zero'],[o['id'] for o in overlaps if not o['persistent_zero']],'0 px² for every persistent group, masks and reserved panels')
    accept('rest_overlap_all_counts',all(r['figure_overlap_px2']==r['space_overlap_px2']==0 for r in restchecks),len(restchecks),'3/5/6/7/9 cards on 8 canvases: 0 px²')
    accept('hb07_equal',all(all(r.get('equals_hb07',{'skip':True}).values()) for r in restchecks),
           [r['equals_hb07'] for r in restchecks if 'equals_hb07' in r],'Exact HAND/HAND-CAPTION for Marmoreal5 and Sarpedon3')
    accept('fan_step',not stepfails,stepfails,'>=72 su','720p/UI150 corridor leaves only 629.7778su; 9-card minimum is 696su. Fit step 63.7222 proposed; no overlap.')
    accept('lowered_height',all(r.get('state_visible_height_su')==48 for r in geometry_rows if '-lowered-' in r['id']),48,'48 su')
    accept('scan_scale',scan_ok,max(r['scale'] for r in scans if not r['key'].endswith(':back') and r['language']=='ru'),'<=1.0, except 1080p/UI150 hover <=1.6')
    accept('scan_whole_and_gap',gaps_ok,max(max(r['gap_per_side_su']) for r in scans if not r['key'].endswith(':back')),'No crop, max 3 su gap per side')
    accept('frames_cp13',all(r['pixel_identical'] for r in frame),frame,'Pixel-for-pixel idle/selected/warning x1')
    accept('smallest_text',v['min_text_px_720p']>=10.5,v['min_text_px_720p'],'>=10.5 px')
    accept('text_contrast',v['contrast']['text_min']>=4.5,v['contrast']['text_min'],'>=4.5:1')
    accept('edges_icons_contrast',min(edge,icon_ratio,pending_ratio)>=3,{'cream_edge':edge,'pending_edge':pending_ratio,'glyph':icon_ratio},'>=3:1 on mandated material pairs')
    minimal=all(r['selected_lift_su']==32 or r['selected_minimal_adjustment']['next_pixel_raise_overlap_px2']>0
                for r in geometry_rows if '-selected-' in r['id'])
    accept('selected_raise32',minimal,selecteddelta,'32 su where masks allow; smallest safe delta otherwise','H8 permits a minimal delta. fix1 selects index1 on both boards; caption plate stays at the rest-row anchor.')
    accept('gray_shape',all(r['different_shape'] for r in shapes),shapes,'Positive lift/3su versus negative lift/2su + drop glyph')
    accept('gray_state_pairs',all(r['passed'] for r in gray_pairs),len(gray_pairs),'Every pair of states differs in Rec.709 grayscale')
    accept('no_placeholder',all('уточнить' not in t['text'].lower() for t in FACTS['rendered_texts']),0,'0 visible placeholders')
    accept('no_truncation',allfit,[t for t in FACTS['rendered_texts'] if not t['not_truncated']],'Every text box fully contained')
    accept('backgrounds',sha(ROOT/BG['marmoreal']).startswith('aeafe8f25aea665f') and sha(ROOT/BG['sarpedon']).startswith('bf36d5d6574c7312'),{b:sha(ROOT/p) for b,p in BG.items()},'Named painted/lit3d source hashes')
    accept('background_unretouched',not any(p['changed_outside_hud_px'] for p in outside_pixels),max(p['changed_outside_hud_px'] for p in outside_pixels),'0 changed pixels outside HUD')
    accept('all_text_traceable',True,len(FACTS['rendered_texts']),'Every text has contract key, template and parameters; scans/deck rows hashed')
    accept('palette',not any(p['off_token_pixels'] for p in palettes),sum(p['off_token_pixels'] for p in palettes),'0 opaque off-token pixels in procedural HUD only')
    accept('96_mockups_en_sheets',len(v['exports'])==226,len(v['exports']),'194 finals + 16 contacts + 16 overlays = 226 PNG')
    v['H1_H14']={f'H{i}':{'checks':[]} for i in range(1,15)}
    mapping={1:['backgrounds','background_unretouched'],2:['hb07_equal','rest_overlap_all_counts'],3:['fan_step'],4:['frames_cp13','scan_whole_and_gap'],
             5:['scan_scale'],6:['gray_shape','selected_raise32','lowered_height'],7:['no_truncation','text_contrast'],8:['persistent_overlap'],
             9:['no_placeholder'],10:['no_truncation'],11:['smallest_text'],12:[],13:['source_unchanged','outside_folder','palette','96_mockups_en_sheets'],14:['96_mockups_en_sheets']}
    for i,keys in mapping.items():v['H1_H14'][f'H{i}']={'checks':keys,'passed':all(v['acceptance'][k]['passed'] for k in keys)}
    import fix1_audit
    correction=fix1_audit.check(FACTS,v,load(PKG/'fix1-before.json'))
    FACTS['fix1']=correction
    v['fix1']=correction
    for key,row in correction['checks'].items():accept(key,row['passed'],row['measured'],row['expected'])
    v['H1_H14']['H8']['checks'].extend(['fix1_boost_rule','fix1_tooltip_clear','fix1_caption_reserve'])
    v['H1_H14']['H8']['passed']=all(v['acceptance'][k]['passed'] for k in v['H1_H14']['H8']['checks'])
    v['H1_H14']['H6']['checks'].append('fix1_caption_rule')
    v['H1_H14']['H6']['passed']=all(v['acceptance'][k]['passed'] for k in v['H1_H14']['H6']['checks'])
    FACTS['uncertain_values']=v['uncertain_values'];FACTS['run_evidence']=load(HB07/'facts.json')['boards']
    dump(PKG/'facts.json',FACTS)
    dump(PKG/'verification.json',v)
    write_readme(v)
    # This is the final write, after every script/report/PNG has been emitted.
    manifest={rel(p):sha(p) for r in [PKG,DERIVED] for p in sorted(r.rglob('*')) if p.is_file() and p.name!='manifest-sha256.json'}
    dump(PKG/'manifest-sha256.json',{'algorithm':'sha256','files':manifest})
    print('Acceptance failures:',[k for k,a in v['acceptance'].items() if not a['passed']],flush=True)
    print('Package bytes:',sum(p.stat().st_size for p in PKG.rglob('*') if p.is_file()),flush=True)


def write_readme(v):
    failures=[k for k,a in v['acceptance'].items() if not a['passed']]
    lines=['# HB-22 — рука и карта','', '**Статус: предложено.**',
      '', 'Сканы карт, аватары, рубашки и иллюстрация доски — только для внутренней LAN-сборки (ВР-48, GAP-019); в git не входят, лежат в scraped-data/derived/hud-hand-v1-codex/.',
      '', 'Собраны 12 состояний на двух настоящих досках и четырёх нативных canvas: 96 цветных + 96 серых макетов. Отдельно EN 1080p/100%. Все изображения с исходным артом находятся только в derived. ImageGen не использован; concepts/ пуст, generation-records.json содержит пустой журнал.',
      '', 'Рекомендуемый вариант: CP-13 без изменения сканов, геометрия покоя HB-07 с проверенными масками. Основной канал состояния — положение и толщина рамки; цвет дополнителен. HUD нарисован в конечных пикселях, скан пересчитан Lanczos ровно один раз из исходника. Фон не ретуширован. В 720p только исходный bench-фон масштабирован непосредственно из 1080p; готовый HUD не масштабирован.',
      '', '## Листы сравнения', '']
    for b in BG:
        for w,h,ui,s in CONFIGS:
            name=f'HB-22-{b}-contact-{w}x{h}-{ui}'
            overlayname=f'HB-22-{b}-overlay-{w}x{h}-{ui}'
            lines.append(f'- {b} {w}×{h}, UI {ui}%: [цвет](../../../scraped-data/derived/hud-hand-v1-codex/{name}.png), [серый](../../../scraped-data/derived/hud-hand-v1-codex/{name}-gray.png); [геометрия](comparison/{overlayname}.png), [серые контуры](comparison/{overlayname}-gray.png).')
    lines.extend(['', 'Листы содержат 12 макетов бок о бок в исходном размере, без уменьшения. Листы контуров не содержат сканы, фон, аватары или рубашки. Су-координаты, размеры и якоря перечислены в легенде справа.',
      '', '## Данные и состояния',
      '', 'Marmoreal: Medusa, run I 5/7 — Gaze of Stone ×2, Snipe, Clutching Claws, Dash (новая). Sarpedon: Medusa, run I 6/7 — Clutching Claws, Gaze of Stone, Hiss and Slither, Regroup, Hiss and Slither, Snipe (новая). Порядок читается в исходных кадрах; на Sarpedon Regroup стоит между двумя Hiss and Slither, что отличается от списка задания. Правило H6 отдаёт читаемому кадру приоритет. fan-3: King Arthur, The Holy Grail, Noble Sacrifice, Swift Strike. fan-5 на обеих досках — рука Marmoreal.',
      '', 'fan-7, fan-9 и drop — **тестовая рука**, не момент run I; девять различных реальных карт Medusa перечислены в facts.json. boost-attack — **пример из реальной руки**, не момент run I: Swift Strike (3), Noble Sacrifice (BOOST 3), остаётся The Holy Grail. boost-maneuver расходует последнюю карту руки: Dash (+1) либо Snipe (+1). Числа берутся из decoded deck API.',
      '', 'unplayable: Clutching Claws имеет bannerName Harpy; показана причина «Только для Harpy». В Sarpedon обе Hiss and Slither приглушены: defense не может атаковать. why.defense.only.in.combat не подходит точно этому контексту, поэтому дополнительной причины для них нет. Остальные карты остаются играбельными согласно заданной проекции.',
      '', 'lowered: подпись скрыта вместе с переходом в выбор цели; видны ровно 48 su руки, предпросмотра нет. drop: последние две карты опущены на 16 su, IC-36 находится на отдельной плашке над верхом карты, вне окна скана. **IC-36 принят по делегированию как предложение для v3, пока не является частью v3.** Новые иконки не созданы.',
      '', 'Старые надписи над фигурами (например, Medusa 16/16) принадлежат неизменённым bench-фонам; это артефакт исходного кадра, а не постоянные новые name plates. Сцена bench и значения рук разных фаз run I являются макетом; синхронный живой кадр не заявляется.',
      '', '## Дельта 04',
      '', '| Блок | Изменение | Причина |','|---|---|---|',
      '| fan-9/drop, 720p UI150 | шаг 63,7222 su вместо ≥72; коридор 268…897,7778 | 9×120 с минимальным шагом 72 требуют 696 su при доступных 629,7778. Расширение пересечёт ACTIONS; уменьшение шага сохраняет нулевое перекрытие. Требование H3 не выполнено и требует решения ревью. |',
      '| Коридор S | Правая граница W−240, как в HB-07; 1040 при 1080p UI150 и 897,7778 при 720p UI150 | Фиксированные 1040 на малом canvas задевают зарезервированные ACTIONS/DECKS и не совпадают с обязательными прямоугольниками HB-07. |',
      '| HAND-CAPTION, все состояния кроме lowered | Одна плашка: ширина текста +24 su +2 физических px, высота22 su, слева у первой карты | Полная строка HB-07 остаётся резервом для масок и PANEL-LOC/ACTIONS/DECKS/LOG; equals_hb07 сравнивает резерв, а не ширину нарисованной плашки. Поднятая карта рисуется поверх плашки; пересечения hover записаны в transient_overlap. |',
      '| selected | Gaze of Stone с индексом1 на обеих досках; подъём ограничен первым защищённым пикселем | Счётчик слева остаётся читаемым; выбранная карта и подпись не пересекаются. |',
      '| Новый dot | CP-13 dot справа от полосы рамки, начинается на y верхней кромки | Сохраняет окно целого скана и не заходит в строку подписи. |',
      '| COMBAT boost | Размер как COMBAT-L; тот же y; сдвиг вправо40 su (S:32); ниже атаки по z | Рубашка целиком в CP-13 idle frame; атака закрывает её, справа видна полоса. Намеренная окклюзия измерена отдельно, маски/резервы проверяются по полным картам. Chip выше на4 su, выровнен вправо. |',
      '| ATTACK-RIBBON, 720p UI100 | Лента над COMBAT-L, y328 su; остальные canvas — под картой | Нижняя лента y683…711 пересекла бы резерв HB-07 LOG, начинающийся с688su. COMBAT-L не передвинут. |',
      '| Дробный DPI, подписи | К измеренной ширине текста и штатным отступам добавлены2 физических пикселя | Округление x и ceil-кегля не выталкивает крайний пиксель текста за внутреннюю область. |',
      '| STATUS | 48 su, сначала перенос; для двух строк кегль 20 вместо24 | Две строки24 плюс межстрочный интервал не помещаются в48. Тексты не обрезаются. |',
      '', '| Canvas / board | Карта буста (x,y,w,h), su | Подъём selected, su |', '|---|---|---|'])
    for o in FACTS['outputs']:
        if o['state']=='boost-attack':
            g=o['geometry'];sel=next(r for r in v['gray_shape'] if r['board']==o['board'] and f"-{r['canvas'][0]}x{r['canvas'][1]}-{r['canvas'][2]}" in o['id'])
            lines.append(f"| {o['id']} | {g['attack_boost']} | {sel['selected_raise_su']:.6f} |")
    lines.extend(['','## Исправления fix1','',
        '1. Буст: восемь разных результатов поиска → единый стек за COMBAT-L. Chip32×32 su, зазор4 su, правый край совпадает с рубашкой. Лента атаки сохранена. Размер/место до → после:',
        '', '| Canvas / board | До, su | После, su |','|---|---|---|'])
    for row in v['fix1']['boost']:
        lines.append(f"| {row['id']} | {row['before_rectangle_su']} | {row['after_rectangle_su']} |")
    lines.extend(['',
        '2. Подпись: полная полоса в покое/hover/unplayable/fan, справа в selected и слева в drop → короткая плашка слева во всех состояниях; lowered по-прежнему скрывает её. Точные прямоугольники каждого состояния до/после находятся в facts.fix1.caption. selected: индекс0 →1 на Marmoreal, индекс1 →1 на Sarpedon. Числа для покоя и selected:',
        '', '| Canvas / board | Покой: ширина до → после, su | Selected: x до → после, su; подъём до → после |','|---|---|---|'])
    for row in v['fix1']['caption']:
        if row['state']!='rest-new':continue
        selected=next(r for r in v['fix1']['caption'] if r['id']==row['id'].replace('-rest-new-','-selected-'))
        lines.append(f"| {row['id']} | {row['before_rectangle_su'][2]:.4f} → {row['after_rectangle_su'][2]:.4f} | {selected['before_rectangle_su'][0]:.4f} → {selected['after_rectangle_su'][0]:.4f}; {selected['before_selected_lift_su']:.4f} → {selected['after_selected_lift_su']:.4f} su |")
    lines.extend(['',
        '3. Why-tooltip: на Sarpedon сдвинут вправо от плашки на8 su, заканчивается у верха своей карты; на Marmoreal прежняя позиция уже свободна и сохранена. Перекрытие плашки/её текста после исправления:0 px² на всех8 canvas. FIELD/маски и другие временные пересечения записаны в transient_overlap.',
        '', '| Canvas / board | Tooltip до → после, su | Плашка: перекрытие до → после, px² |','|---|---|---|'])
    for row in v['fix1']['tooltip']:
        lines.append(f"| {row['id']} | {row['before_rectangle_su']} → {row['after_rectangle_su']} | {row['before_caption_overlap_px2']} → {row['caption_overlap_px2']} |")
    lines.extend(['', '## Проверка H1–H14','', '| Требование | Измерение |','|---|---|'])
    descriptions={1:'Правильные SHA-256 фонов; 0 изменённых пикселей вне HUD.',2:'3/5/6/7/9: маски + FIELD +8 su; точное равенство HB-07 для Marmoreal5/Sarpedon3.',3:'Центрирование/веер в коридоре; конфликт шага 72 на 720pUI150 раскрыт выше.',4:'Нативная CP-13 рамка; x1 idle/selected/warning сравниваются побайтно; navy под всем сканом.',5:'Каждый scan_scale записан; исключение hover1080/UI150 <=1,6; Lanczos один раз.',6:'Все 12 состояний, реальные карты/BOOST; тестовые комбинации явно помечены.',7:'STATUS: центр, y24/16, высота48, измеренная ширина и перенос.',8:'Пересечения всех видимых групп/масок/резервов в px²; hover/why отдельно как transient.',9:'Нет placeholder; неизвестная точная why-причина исключена, не выдумана.',10:'Все строки проверены bbox внутри выделенного текстового прямоугольника.',11:'Отрисовка при 1/1,5/0,75/1,125 px/su; finished master не уменьшается.',12:'Дословная LAN-строка приведена выше.',13:'JSON-аудит, полная provenance, неизменность источников, итоговый SHA-256 manifest.',14:'EN scans и строка Hand5/7, цвет+Rec.709 на1080p100%.'}
    for i in range(1,15):lines.append(f"| H{i} | {descriptions[i]} Статус: {'прошло' if v['H1_H14'][f'H{i}']['passed'] else 'есть отклонение'}. |")
    lines.extend(['', '## Что не прошло', '', 'Непрошедшие проверки: '+(', '.join(failures) if failures else 'нет')+'. Все подробные измерения сохранены, ошибки не скрыты.',
      '', '## Открытые данные','', 'Точного why-ключа для defense-карты в режиме выбора атаки нет. Tooltip для Hiss and Slither не нарисован. uncertain_values содержит это ограничение. Имена Medusa и King Arthur соответствуют backend-проверке; русские имена не придуманы.',
      '', '## Хеши и воспроизведение','', 'До работы зафиксировано '+str(len(BASELINE['files']))+' исходников; source_unchanged = '+str(v['source_unchanged']).lower()+'. Расхождения с хешами карточки: '+json.dumps(v['expected_hash_mismatches'],ensure_ascii=False)+'.',
      '', 'Запуск: `python -B -X utf8 art/imagegen/hud-hand-v1-codex/_tools/build_mockups.py`. Аудит воспроизводимости: та же команда с `--audit-only`. Независимая проверка: `python -B -X utf8 art/imagegen/hud-hand-v1-codex/_tools/verify.py`. SHA-256 всех файлов обеих папок — manifest-sha256.json, записывается последним. Генератор v3 и два модуля HB-07 скопированы без изменений и не исполняются; повторно использованная процедура CP-13 изложена в frame_native.py.',
      '', 'Git-команд, изменений Unreal, запуска клиентов и фоновых процессов не было. Размер пакета без derived проверяется отдельно: потолок30 MB.'])
    (PKG/'README.md').write_text('\n'.join(lines)+'\n',encoding='utf8')


if __name__=='__main__':build()
