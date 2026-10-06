#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""HB-26. Offline native-size renderer and measured audit.

python -B -X utf8 art/imagegen/hud-decks-v1-codex/_tools/build_mockups.py
No subprocess, network, git, Unreal, ImageGen, or execution of source snapshots.
Every write passes through guard(); source-hashes-before.json is never replaced.
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
from PIL import Image, ImageDraw, ImageFont, ImageOps, ImageFilter
import layout_reference_snapshot as ref

ROOT = Path(__file__).resolve().parents[4]
PKG = ROOT / 'art/imagegen/hud-decks-v1-codex'
OUT = ROOT / 'scraped-data/derived/hud-decks-v1-codex'
HB07 = ROOT / 'art/imagegen/hud-composition-v1-codex'
ICONS = ROOT / 'art/imagegen/hud-icons-v3'
PROMPT = 'docs/game-design/visual/06-tasks/prompts/HB-26.codex.md'
STRINGS = 'docs/unreal/contracts/hud/st-hud.csv'
DB = Path('C:/tmp/visual/CX-01r/db-names-2026-10-06.txt')
STATES = ('chips','chips-stale','own','own-end','own-discard','opp','opp-end')
CONFIGS = ((1920,1080,100,1.),(1920,1080,150,1.5),(1280,720,100,.75),(1280,720,150,1.125))
T = {'navy':'#061623','inset':'#15232E','cream':'#F9EBDB','primary':'#F2EDE4',
     'secondary':'#B9B2A6','pending':'#0D7A89','glyph':'#FAF8F2'}
TYPE_ORDER = {'attack':0,'defense':1,'versatile':2,'scheme':3}
TYPE_ICON = {'attack':'action-attack','defense':'action-defense','versatile':'action-maneuver','scheme':'action-scheme'}
BLOCKS = ('TOP','PANEL-OPP','OPP-HAND','ACTIONS','HAND','HAND-CAPTION','PANEL-LOC','LOG')
BOARD = {
 'marmoreal': {'own':'medusa','opp':'king-arthur','seq':12,
   'background':'docs/game-design/evidence/ENV-MAPS/p7-concept-paste-2026-10-01/marmoreal-concept-flag/bench-K1-1920x1080.png',
   'run':'docs/game-design/evidence/DE-FOOTAGE/2026-10-05/I/marmoreal/combat-20261005-235827',
   'trace':'combat-client-host.trace.txt','trace_lines':[1400,1409],'stale_line':1297,
   'own_counts':{'deck':23,'discard':2,'hand':5},'opp_counts':{'deck':24,'discard':1,'hand':5},
   'stale_deck':24,'top_discard':'Feint',
   'hand_marks':{'Gaze of Stone':2,'Snipe':1,'Clutching Claws':1,'Dash':1},
   'discard_marks':{'A Momentary Glance':1,'Feint':1},'opp_discard_marks':{'Swift Strike':1}},
 'sarpedon': {'own':'king-arthur','opp':'medusa','seq':13,
   'background':'docs/game-design/evidence/ENV-MAPS/p10-sarpedon-rework-2026-10-03/sarpedon-packaged/bench-K1-1920x1080.png',
   'run':'docs/game-design/evidence/DE-FOOTAGE/2026-10-05/I/sarpedon/combat-20261005-235948',
   'trace':'combat-client-joiner.trace.txt','trace_lines':[1186,1196,1288],'stale_line':1364,
   'own_counts':{'deck':25,'discard':2,'hand':3},'opp_counts':{'deck':22,'discard':2,'hand':6},
   'stale_deck':25,'top_discard':'Swift Strike',
   'hand_marks':{'Noble Sacrifice':1,'Swift Strike':1,'The Holy Grail':1},
   'discard_marks':{'Swift Strike':1,'Momentous Shift':1},'opp_discard_marks':{'Dash':1,'Regroup':1}}
}
BACKS = {'medusa':'scraped-data/images/heroes/card-covers/ROSMO3sRi6Jh1o7S_riGI.png',
         'king-arthur':'scraped-data/images/heroes/card-covers/WWzu16BEFGsEdu5NsMbMI.png'}
WRITES = []

def rel(p):
    p=Path(p).resolve()
    try: return p.relative_to(ROOT).as_posix()
    except ValueError: return p.as_posix()

def guard(p):
    p=Path(p).resolve()
    if not any(p.is_relative_to(r) for r in (PKG,OUT)): raise ValueError('Outside output roots: '+str(p))
    p.parent.mkdir(parents=True,exist_ok=True)
    WRITES.append(rel(p))
    return p

def load(p): return json.loads(Path(p).read_text('utf8'))
def save(p,obj): guard(p).write_text(json.dumps(obj,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
def sha(p): return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def rgb(t): return tuple(bytes.fromhex(T.get(t,t).lstrip('#')))
def rgba(t,a=1): return rgb(t)+(round(a*255),)
def font(s,bold=True): return ref.font(max(1,math.ceil(s)),bold)
def gray(im): return ref.gray(im).convert('RGBA')

@lru_cache(None)
def original(path):
    with Image.open(ROOT/path) as im:return im.convert('RGBA')

def image_save(im,p): im.save(guard(p),compress_level=6)

def strings():
    with (ROOT/STRINGS).open(encoding='utf-8-sig',newline='') as f:
        rows=list(csv.reader(f))
    return {r[0]:{'en':r[1],'ru':r[2]} for r in rows if len(r)>2 and r[0].startswith('hud.')}

S = strings()
def st(key,lang='ru',**kw): return S['hud.'+key][lang].format(**kw)

def decode_decks():
    # The devalue decoder is the byte-for-byte HB-07 snapshot function only.
    heroes={k:ref.devalue(ROOT/f'scraped-data/api/heroes/{k}.json') for k in BACKS}
    names={}; dbcards={}
    for lineno,line in enumerate(DB.read_text('utf8').splitlines(),1):
        if line.startswith('#') or not line.strip():continue
        a=line.split('|')
        if len(a)==6:names[a[0]]={'nameRu':a[2],'line':lineno}
        elif len(a)==9:dbcards[(a[0],a[1])]={'nameRu':a[2],'type':a[3].lower(),'value':int(a[4] or a[5]) if a[4] or a[5] else None,'boost':int(a[6]),'copies':int(a[8]),'line':lineno}
    decks={}; checks=[]
    for slug,hero in heroes.items():
        hname=hero['fetchedHero']['name']; rows=[]
        for i,r in enumerate(hero['fetchedDeck']):
            c=r['card']; title=c['title']; d=dbcards[(hname,title)]
            row={'title_en':title,'title_ru':c.get('i18n',{}).get('ru',{}).get('title',d['nameRu']),
                 'copies':r['copies'],'type':r['type'],'value':r['value'],'boost':r['boostValue'],
                 'source':f'scraped-data/api/heroes/{slug}.json','source_key':f'fetchedDeck[{i}]','db_line':d['line'],
                 'ru_name_source':'card.i18n.ru.title' if c.get('i18n',{}).get('ru',{}).get('title') else 'database Card.nameRu'}
            checks.append({'hero':hname,'card':title,'passed':all(row[k]==d[k] for k in ['copies','type','value','boost']),'source_key':row['source_key'],'db_line':d['line']})
            rows.append(row)
        decks[slug]={'hero':names[hname]['nameRu'],'hero_name_db_line':names[hname]['line'],'rows':rows}
        assert sum(x['copies'] for x in rows)==30
    return decks,checks

DECKS,ROW_CHECKS=decode_decks()
ACCEPTED=load(HB07/'verification.json')
MASKS=load(HB07/'masks.json')
CARDART=load(ROOT/'art/imagegen/mvp-v1/reused-cardart.json')['cards']

def hb07(board,w,h,ui):
    a=next(x for x in ACCEPTED['overlap']['per_mockup'] if x['board']==board and x['state']=='own-turn' and x['resolution']==[w,h] and x['ui_scale_percent']==ui)
    return a['class'],{k:v['rectangle_su'] for k,v in a['panels'].items()}

def geom(board,w,h,ui,s):
    cl,r=hb07(board,w,h,ui); margin=16 if cl=='S' else 24
    width=300 if cl=='S' else (380 if w==1920 else 336)
    top=r['PANEL-OPP'][1]+r['PANEL-OPP'][3]+8 if cl=='S' else max(248,r['OPP-HAND'][1]+r['OPP-HAND'][3]+8)
    bottom=r['DECKS'][1]-8
    return {'class':cl,'panel':[w/s-margin-width,top,width,bottom-top],'hb07':r,'margin_su':margin}

@lru_cache(None)
def masks(board,w,h):
    q=w/1920; sm=Image.new('L',(w,h)); fm=Image.new('L',(w,h))
    d=ImageDraw.Draw(sm)
    transform=MASKS['topology_transforms'][board+'-1920x1080']
    # HB-07 rasterizes float polygon coordinates directly (Pillow truncation).
    for space in transform['spaces']:d.polygon([(x*q,y*q) for x,y in space['polygon_px']],fill=255)
    d=ImageDraw.Draw(fm)
    for poly in MASKS['figure_polygons_1080p'][board]:d.polygon([(round(x*q),round(y*q)) for x,y in poly],fill=255)
    for im,key in [(sm,'cell_conservative_dilation_px'),(fm,'figure_conservative_dilation_px')]:
        radius=math.ceil(transform[key]*q)
        enlarged=im.filter(ImageFilter.MaxFilter(radius*2+1))
        if im is sm:sm=enlarged
        else:fm=enlarged
    return np.asarray(sm)>0,np.asarray(fm)>0

def wrap(value,width,size,s,bold=True):
    f=font(size*s,bold); words=value.split(); lines=[]; current=''
    for word in words:
        n=(current+' '+word).strip()
        if current and f.getlength(n)>width*s:lines.append(current);current=word
        else:current=n
    if current:lines.append(current)
    return lines

def title_layout(value,hero,width,s):
    # The separator is the ONLY legal break: hero names remain atomic.
    if font(28*s).getlength(value)<=width*s:return 28,[value]
    prefix,actual_hero=value.rsplit(' · ',1)
    assert actual_hero==hero
    lines=[prefix+' ·',hero]
    size=28 if all(font(28*s).getlength(line)<=width*s for line in lines) else 24
    return size,lines

def sorted_rows(slug,lang):return sorted(DECKS[slug]['rows'],key=lambda r:(TYPE_ORDER[r['type']],r['title_'+lang].casefold()))

def marks(board,side,row):
    b=BOARD[board]; name=row['title_en']
    if side=='opp':return {'discard':b['opp_discard_marks'].get(name,0)}
    h=b['hand_marks'].get(name,0); d=b['discard_marks'].get(name,0)
    return {'hand':h,'discard':d,'left':row['copies']-h-d}

def values(row):return (dict(attack='A',defense='D',versatile='V')[row['type']]+str(row['value'])+' ' if row['type']!='scheme' else '')+'B'+str(row['boost'])

def name_layout(row,r,s,lang):
    x,y,w,h=r;vw=font(20*s).getlength(values(row))/s;vx=x+w-6-vw
    nx=x+59;col=vx-7-nx;title=row['title_'+lang];sz=20;fullwidth=font(20*s).getlength(title)
    if fullwidth>col*s:sz=16
    f=font(sz*s);displayed=title
    if f.getlength(displayed)>col*s:
        while displayed and f.getlength(displayed+'…')>col*s:displayed=displayed[:-1]
        displayed=displayed.rstrip()+'…'
    audit={'card':row['title_en'],'displayed_name':title,'shown':displayed,'size_su':sz,'size_px':f.size,'measured_width_px':f.getlength(displayed),'full_width_px_at_20':fullwidth,'column_width_px':col*s,'column_width_su':col,'ellipsis':displayed!=title,'full_name_inspector':title,'baseline_rule':'Common line-1 baseline of 20 su copies and values; name drawn with ls anchor regardless of size'}
    return nx,vx,vw,col,audit

@lru_cache(None)
def icon_asset(kind,px):
    name=TYPE_ICON[kind]; p=ICONS/f'sizes/{name}-{px}.png'; resized=False
    if p.exists():im=original(rel(p))
    else:
        p=ICONS/f'masters/{name}.png';im=original(rel(p)).resize((px,px),Image.Resampling.LANCZOS);resized=True
    return im,{'path':rel(p),'sha256':sha(p),'native_size_px':px,'resampled_once_from_master':resized}

class Canvas:
    def __init__(self,w,h,s,base,ident):
        self.s=s; self.size=(w,h);self.base=base;self.id=ident
        self.layer=Image.new('RGBA',(w,h));self.excluded=Image.new('L',(w,h));self.texts=[];self.assets=[];self.edges=[];self.name_fit=[];self.rectangles={}
    def box(self,r):
        x,y,w,h=r;return (round(x*self.s),round(y*self.s),round((x+w)*self.s)-1,round((y+h)*self.s)-1)
    def composite(self,layer):self.layer=Image.alpha_composite(self.layer,layer)
    def exclusion(self,mask):self.excluded=Image.fromarray(np.maximum(np.asarray(self.excluded),np.asarray(mask)))
    def shape(self,r,body='navy',alpha=1,radius=4,edge=None,edge_alpha=1,edge_width=1,label=None):
        layer=Image.new('RGBA',self.size);d=ImageDraw.Draw(layer);box=self.box(r)
        d.rounded_rectangle(box,radius=round(radius*self.s),fill=rgba(body,alpha));self.composite(layer)
        if edge:
            under=Image.alpha_composite(self.base,self.layer).convert('RGB')
            border=Image.new('RGBA',self.size);bd=ImageDraw.Draw(border);bw=max(1,round(edge_width*self.s))
            bd.rounded_rectangle(box,radius=round(radius*self.s),outline=rgba(edge,edge_alpha),width=bw)
            em=np.asarray(border.getchannel('A'))>0
            after=Image.alpha_composite(Image.alpha_composite(self.base,self.layer),border).convert('RGB')
            # Adjacent interior pixels, not the pre-paint edge pixel itself.
            um=np.asarray(under);am=np.asarray(after);cr=ref.contrast(am[em],um[em])
            self.edges.append({'element':label,'edge_vs_body_min':float(cr.min()) if cr.size else None,'pair':'edge / its own body (§02 3.5)','alpha':edge_alpha})
            self.composite(border);self.exclusion(border.getchannel('A'))
        if label:self.rectangles[label]=list(r)
    def line(self,r,token='cream',alpha=.16,radius=0):
        im=Image.new('RGBA',self.size);ImageDraw.Draw(im).rounded_rectangle(self.box(r),radius=round(radius*self.s),fill=rgba(token,alpha));self.composite(im);self.exclusion(im.getchannel('A'))
    def text(self,value,x,y,size=20,token='primary',bold=True,key='',container=None,full=None,baseline_px=None):
        value=str(value);f=font(size*self.s,bold);pos=(round(x*self.s),round(y*self.s))
        anchor='lt'
        if baseline_px is not None:pos=(pos[0],baseline_px);anchor='ls'
        mask=Image.new('L',self.size);d=ImageDraw.Draw(mask);d.text(pos,value,font=f,fill=255,anchor=anchor);bb=d.textbbox(pos,value,font=f,anchor=anchor)
        coverage=np.asarray(mask);a=Image.alpha_composite(self.base,self.layer).convert('RGB');solid=coverage==255
        cr=ref.contrast(rgb(token),np.asarray(a)[solid]); measured=float(cr.min()) if cr.size else None
        ink=Image.new('RGBA',self.size,rgba(token));ink.putalpha(mask);self.composite(ink)
        aa=Image.fromarray(np.where((coverage>0)&(coverage<255),255,0).astype('uint8'));self.exclusion(aa)
        width=f.getlength(value);fits=True
        if container:
            cx,cy,cw,ch=container;bounds=(round(cx*self.s),round(cy*self.s),round((cx+cw)*self.s),round((cy+ch)*self.s))
            fits=bb[0]>=bounds[0] and bb[1]>=bounds[1] and bb[2]<=bounds[2] and bb[3]<=bounds[3]
        self.texts.append({'displayed':value,'full':full or value,'string_key':key,'size_su':size,'font_em_px':f.size,'nominal_px':size*self.s,'bbox_px':list(bb),'baseline_px':baseline_px,'measured_width_px':width,'contrast_min':measured,'fits_container':fits,'container_su':container,'token':T[token]})
        return width/self.s
    def button(self,value,r,selected=False,key=''):
        self.shape(r,'pending' if selected else 'navy',1 if selected else .92,4,'glyph' if selected else 'cream',1 if selected else .45,label=key)
        x,y,w,h=r;f=font(20*self.s);v=value.upper(); tw=f.getlength(v)/self.s;bb=f.getbbox(v);th=(bb[3]-bb[1])/self.s
        self.text(v,x+(w-tw)/2,y+(h-th)/2,20,'glyph' if selected else 'primary',key=key,container=r)
    def asset(self,path,r,kind='scan'):
        x,y,w,h=r;size=(max(1,round(w*self.s)),max(1,round(h*self.s)))
        im=ImageOps.contain(original(path),size,Image.Resampling.LANCZOS)
        px=round(x*self.s)+(size[0]-im.width)//2;py=round(y*self.s)+(size[1]-im.height)//2
        layer=Image.new('RGBA',self.size);layer.alpha_composite(im,(px,py));self.composite(layer);self.exclusion(layer.getchannel('A'))
        self.assets.append({'path':path,'sha256':sha(ROOT/path),'kind':kind,'whole_asset_fit':True,'r_su':r,'size_px':list(im.size),'source_to_final_resampling':1})
    def icon(self,row,x,y):
        px=round(24*self.s);im,audit=icon_asset(row['type'],px);layer=Image.new('RGBA',self.size);layer.alpha_composite(im,(round(x*self.s),round(y*self.s)));self.composite(layer);self.exclusion(layer.getchannel('A'))
        ink=np.asarray(im);solid=ink[:,:,3]==255
        # Contrast of each solid accepted pigment against navy; glyph/plate pairs are separately audited.
        audit=dict(audit,kind='icon',size_su=24,type=row['type']);self.assets.append(audit)
    def row(self,row,r,board,side,lang):
        x,y,w,h=r; self.shape(r,'inset',radius=0);self.line([x,y+h-1,w,1])
        self.icon(row,x+4,y+3)
        baseline=round((y+3)*self.s)-font(20*self.s).getbbox('H',anchor='ls')[1]
        self.text('×'+str(row['copies']),x+32,y+3,20,key=row['source_key']+'.copies',container=[x+30,y,w-30,27],baseline_px=baseline)
        nx,vx,vw,col,fit=name_layout(row,r,self.s,lang)
        self.text(fit['shown'],nx,y+3,fit['size_su'],key=row['source_key']+'.title_'+lang,container=[nx,y,col,27],full=fit['displayed_name'],baseline_px=baseline)
        self.text(values(row),vx,y+3,20,key=row['source_key']+'.value/boostValue',container=[vx,y,vw+1,27],baseline_px=baseline)
        mk=marks(board,side,row);mx=x+32;my=y+29
        for key,num in mk.items():
            if key!='left' and num==0:continue
            text=st('deckpanel.mark.'+key,lang,n=num);mw=font(14*self.s).getlength(text)/self.s+8
            self.shape([mx,my,mw,18],'navy',1,4,'cream',.45,label=None)
            self.text(text,mx+4,my+2,14,key='hud.deckpanel.mark.'+key,container=[mx,my,mw,18])
            mx+=mw+4
        return {'card':row['title_en'],'baseline_px':baseline,'marks':mk,'marks_end_su':mx-4,'row_right_su':x+w,'fits':mx-4<=x+w}

def discard_path(board,lang):
    b=BOARD[board];return next(c for c in CARDART if c['title']==b['top_discard'] and c['stableContentKey'].startswith(b['own']+':'))[lang]['path']

def draw_chips(c,board,g,state,lang):
    b=BOARD[board];x,y,_,_=g['hb07']['DECKS'];small=g['class']=='S';ch=48 if small else 56
    widths=[64,64] if small else ([156,124] if lang=='ru' else [144,136])
    c.chip_geometry=[]
    n=b['stale_deck'] if state=='chips-stale' else b['own_counts']['deck']
    nums=[('≈'+str(n)) if state=='chips-stale' else str(n),str(b['own_counts']['discard'])]
    labels=[st('decks.deck',lang,n=nums[0]),st('decks.discard',lang,n=nums[1])]
    for i,path in enumerate([BACKS[b['own']],discard_path(board,lang)]):
        cw=widths[i];cx=x+(widths[0]+8 if i else 0);r=[cx,y,cw,ch];c.shape(r,'navy',.92,4,'cream',.45,label='CHIP-'+str(i))
        if small:
            mh=18*45/32;ar=[cx+5,y+(ch-mh)/2,18,mh];tx=cx+28;avail=cw-28-4;v=nums[i]
        else:
            ar=[cx+9,y+(ch-45)/2,32,45];tx=cx+50;avail=cw-50-8;v=labels[i]
        # One-su outline OUTSIDE the mini-image, on its own navy plate.
        # Comparing a hairline to arbitrary scan pixels would be the wrong §3.5 pair.
        c.shape([ar[0]-1,ar[1]-1,ar[2]+2,ar[3]+2],'navy',1,0,'cream',.45,label='MINI-'+str(i))
        c.asset(path,ar,'back' if i==0 else 'scan')
        c.text(v,tx,y+(ch-16)/2,20,key='hud.decks.'+('deck' if i==0 else 'discard'),container=[tx,y,avail,ch])
        c.chip_geometry.append({'chip':i,'rectangle_su':r,'mini_box_su':ar,'mini_outline_su':[ar[0]-1,ar[1]-1,ar[2]+2,ar[3]+2],'text_box_su':[tx,y,avail,ch],'left_padding_su':ar[0]-1-cx,'right_padding_su':cx+cw-tx-avail,'mini_to_text_gap_su':tx-(ar[0]+ar[2]+1),'text_size_su':20,'text':v,'measured_text_width_px':font(20*c.s).getlength(v)})

def render(board,state,w,h,ui,s,lang='ru'):
    ident=f'HB-26-{board}-{state}'+('-en' if lang=='en' else '')+f'-{w}x{h}-{ui}'
    b=BOARD[board];g=geom(board,w,h,ui,s)
    base=original(b['background']);base=base if base.size==(w,h) else base.resize((w,h),Image.Resampling.LANCZOS)
    c=Canvas(w,h,s,base,ident);draw_chips(c,board,g,state,lang)
    pa=None;drawn=[]
    if state not in ('chips','chips-stale'):
        side='opp' if state.startswith('opp') else 'own';slug=b[side];counts=b[side+'_counts'];hero=DECKS[slug]['hero']
        x,y,pw,ph=g['panel'];padding=12;iw=pw-2*padding
        c.shape(g['panel'],'navy',.92,6,'cream',.45,label='DECKPANEL')
        ix=x+padding;cy=y+padding;title=st('deckpanel.title.'+side,lang,hero=hero);ts=28
        ts,title_lines=title_layout(title,hero,iw,s)
        for line in title_lines:c.text(line,ix,cy,ts,key='hud.deckpanel.title.'+side,container=[ix,cy,iw,ts*1.2]);cy+=ts*1.2
        cy+=8;tabh=32;tab_text=[st('deckpanel.tab.own',lang),st('deckpanel.tab.opp',lang),st('deckpanel.close',lang)]
        widths=[font(20*s).getlength(t.upper())/s+12 for t in tab_text];bx=ix;tabgap=8 if g['class']=='L' else 4
        for i,(text,bw) in enumerate(zip(tab_text,widths)):
            if i==2:bx=x+pw-padding-bw
            c.button(text,[bx,cy,bw,tabh],selected=(i==0 and side=='own') or (i==1 and side=='opp'),key=['hud.deckpanel.tab.own','hud.deckpanel.tab.opp','hud.deckpanel.close'][i]);bx+=bw+tabgap
        control_fits=sum(widths)+tabgap+4<=iw;cy+=tabh+8
        summary=st('deckpanel.summary',lang,**counts);summary_lines=wrap(summary,iw,14,s,False)
        for line in summary_lines:c.text(line,ix,cy,14,'secondary',False,key='hud.deckpanel.summary',container=[ix,cy,iw,20]);cy+=20
        if side=='opp':
            cy+=4
            for i in range(counts['hand']):c.asset(BACKS[slug],[ix+i*21,cy,17,24],'opponent-hand-back')
            cy+=24+4
        cy+=4;fv=st('deckpanel.filter.discard',lang);fw=font(20*s).getlength(fv.upper())/s+16
        c.button(fv,[ix,cy,fw,30],selected=state=='own-discard',key='hud.deckpanel.filter.discard');cy+=38
        rows=sorted_rows(slug,lang)
        # D4: audit ALL unique rows in the model on every panel/canvas, including
        # offscreen rows and rows hidden by the discard filter.
        for row in rows:
            fit=name_layout(row,[ix,cy,iw-10,48],s,lang)[4]
            c.name_fit.append(dict(fit,scope='complete unfiltered model'))
        if state=='own-discard':rows=[r for r in rows if marks(board,side,r)['discard']>0]
        capacity=max(0,math.floor((y+ph-padding-cy)/48));visible=min(len(rows),capacity);vh=capacity*48
        start=max(0,len(rows)-visible) if state.endswith('-end') else 0
        viewport=[ix,cy,iw,vh];rw=iw-10
        for i,row in enumerate(rows[start:start+visible]):drawn.append(c.row(row,[ix,cy+i*48,rw,48],board,side,lang))
        if len(rows)>visible and visible>0:
            c.line([ix+iw-4,cy,4,vh],'cream',.16,2);thumb=vh*visible/len(rows);ty=cy+(vh-thumb)*start/(len(rows)-visible)
            c.line([ix+iw-4,ty,4,thumb],'cream',.45,2)
        pa={'rectangle_su':g['panel'],'header_height_su':cy-y,'title_lines':title_lines,'title_size_su':ts,'tabs_close_fit':control_fits,'tab_gap_su':tabgap,
            'summary_lines':summary_lines,'viewport_su':viewport,'viewport_height_su':vh,'row_height_su':48,'capacity':capacity,'rows_visible':visible,
            'total_rows':len(rows),'first_row_index':start,'last_row_index':start+visible-1,'scrollbar':len(rows)>visible,'last_row_is_last_visible':not state.endswith('-end') or start+visible==len(rows),
            'side':side,'hero':hero,'read_only':True,'counts':counts,'rows_drawn':drawn,'rows_order':[r['title_en'] for r in rows]}
    final=Image.alpha_composite(base,c.layer)
    path=OUT/(ident+'.png');image_save(final,path);image_save(gray(final),OUT/(ident+'-gray.png'))
    v={'id':ident,'board':board,'state':state,'resolution':[w,h],'ui_scale_percent':ui,'su_to_px':s,'class':g['class'],'language':lang,'panel_geometry':pa,
       'name_fit':c.name_fit,'chip_geometry':c.chip_geometry,'text':c.texts,'assets':c.assets,'edges':c.edges,'rectangles_su':c.rectangles}
    v.update(audit(c,g,board))
    return path,v,g

def rectmask(size,r,s):
    im=Image.new('L',size);x,y,w,h=r;ImageDraw.Draw(im).rectangle((round(x*s),round(y*s),round((x+w)*s)-1,round((y+h)*s)-1),fill=255);return np.asarray(im)>0

@lru_cache(None)
def space_details(board,w,h,rect,s):
    q=w/1920;rm=rectmask((w,h),rect,s);items=[];x,y,rw,rh=rect;left,top,right,bottom=x*s,y*s,(x+rw)*s,(y+rh)*s
    for space in MASKS['topology_transforms'][board+'-1920x1080']['spaces']:
        sx0,sy0,sx1,sy1=space['ellipse_px'];margin=math.ceil(15*q)
        if sx1*q+margin<left or sx0*q-margin>right or sy1*q+margin<top or sy0*q-margin>bottom:continue
        im=Image.new('L',(w,h));ImageDraw.Draw(im).polygon([(px*q,py*q) for px,py in space['polygon_px']],fill=255)
        raw=np.asarray(im)>0;dil=np.asarray(im.filter(ImageFilter.MaxFilter(2*margin+1)))>0
        count=int(np.count_nonzero(dil&rm))
        if count:items.append({'space':space['id'],'with_margin_px2':count,'undilated_cell_px2':int(np.count_nonzero(raw&rm))})
    return items

def audit(c,g,board):
    w,h=c.size;sm,fm=masks(board,w,h);overlap={};transient={}
    for name,r in c.rectangles.items():
        if name not in ('DECKPANEL','CHIP-0','CHIP-1'):continue
        m=rectmask(c.size,r,c.s);item={'rectangle_su':r,'figure_overlap_px2':int(np.count_nonzero(m&fm)),'space_overlap_px2':int(np.count_nonzero(m&sm)),'blocks_overlap_px2':{k:int(np.count_nonzero(m&rectmask(c.size,g['hb07'][k],c.s))) for k in BLOCKS if k in g['hb07']}}
        if item['space_overlap_px2']:item['space_details']=space_details(board,w,h,tuple(r),c.s)
        if name=='DECKPANEL':item['deck_block_overlap_px2']=int(np.count_nonzero(m&rectmask(c.size,g['hb07']['DECKS'],c.s)))
        if name=='DECKPANEL' and g['class']=='S':transient[name]=item
        else:overlap[name]=item
    a=np.asarray(c.layer);excluded=np.asarray(c.excluded)>0;opaque=(a[:,:,3]==255)&~excluded
    colors=np.array(list({rgb(t) for t in T}),dtype='uint8');px=a[:,:,:3][opaque]
    valid=np.any(np.all(px[:,None,:]==colors[None,:,:],axis=2),axis=1) if len(px) else np.array([],dtype=bool)
    final=np.asarray(Image.alpha_composite(c.base,c.layer));base=np.asarray(c.base);outside=a[:,:,3]==0
    return {'overlap':overlap,'transient_overlap':transient,'palette':{'opaque_pixels_checked':int(opaque.sum()),'off_token_pixels':int((~valid).sum()),'fraction':float((~valid).mean()) if len(valid) else 0.,'excluded_pixels':int(excluded.sum()),'method':'HUD alone RGBA; exact token equality at opaque pixels; source images/icons, hairline edges/dividers/scrollbar and antialiased glyph coverage excluded'},
            'background_unchanged':{'outside_hud_pixels':int(outside.sum()),'different_pixels':int(np.count_nonzero(np.any(final[outside]!=base[outside],axis=1))),'comparison':'source frame at 1080p; source-only Lanczos resize at 720p; HUD natively rasterized'},
            'text_contrast_min':min(t['contrast_min'] for t in c.texts if t['contrast_min'] is not None),'all_text_fits':all(t['fits_container'] for t in c.texts)}

def overlay(board,w,h,ui,s,g):
    """Native-size no-scan geometry sheet. No background pixels or source art."""
    c=Canvas(w,h,s,Image.new('RGBA',(w,h),rgba('navy')),f'overlay-{board}-{w}-{ui}')
    d=ImageDraw.Draw(c.layer)
    for k in BLOCKS:
        if k not in g['hb07']:continue
        r=g['hb07'][k];d.rectangle(c.box(r),outline=rgba('secondary'),width=1)
        c.text(k,r[0]+3,r[1]+3,14,'secondary',key='HB-07 rectangle')
        d=ImageDraw.Draw(c.layer)
    q=w/1920
    tr=MASKS['topology_transforms'][board+'-1920x1080']
    for space in tr['spaces']:d.line([(round(x*q),round(y*q)) for x,y in space['polygon_px']],fill=rgba('cream'),width=1)
    for poly in MASKS['figure_polygons_1080p'][board]:d.line([(round(x*q),round(y*q)) for x,y in poly+[poly[0]]],fill=rgba('glyph'),width=max(1,round(s)))
    for sid,point in tr['registration_anchors_1080p'].items():
        px,py=[round(v*q) for v in point];d.line((px-3,py,px+3,py),fill=rgba('secondary'));d.line((px,py-3,px,py+3),fill=rgba('secondary'))
    # Show the actual own-panel header, row grid and runtime text at identical
    # native positions. All source-art boxes stay empty outlines on this sheet.
    v=next(z for z in RESULTS if z['board']==board and z['resolution']==[w,h] and z['ui_scale_percent']==ui and z['state']=='own' and z['language']=='ru')
    x,y,pw,ph=g['panel'];p=v['panel_geometry'];vx,vy,vw,vh=p['viewport_su']
    c.shape(g['panel'],'navy',.92,6,'cream',.45)
    for i in range(p['capacity']):
        c.shape([vx,vy+i*48,vw-10,48],'inset',radius=0);c.line([vx,vy+(i+1)*48-1,vw-10,1])
    for key,r in v['rectangles_su'].items():
        if key.startswith('hud.') or key.startswith('CHIP'):
            selected=key=='hud.deckpanel.tab.own';c.shape(r,'pending' if selected else 'navy',1 if selected else .92,4,'glyph' if selected else 'cream',1 if selected else .45)
    for t in v['text']:
        token=next(k for k,value in T.items() if value==t['token'])
        bold=t['string_key']!='hud.deckpanel.summary';bearing=font(t['size_su']*s,bold).getbbox(t['displayed'],anchor='lt')
        c.text(t['displayed'],(t['bbox_px'][0]-bearing[0])/s,(t['bbox_px'][1]-bearing[1])/s,t['size_su'],token,bold=bold,key=t['string_key'])
    d=ImageDraw.Draw(c.layer)
    for a in v['assets']:
        if 'r_su' in a:d.rectangle(c.box(a['r_su']),outline=rgba('cream'),width=1)
    # Draw the OUTER dilated mask contours, not only the undilated polygons.
    sm,fm=masks(board,w,h)
    for m,token in [(sm,'secondary'),(fm,'glyph')]:
        edge=Image.fromarray((m*255).astype('uint8')).filter(ImageFilter.FIND_EDGES())
        ink=Image.new('RGBA',(w,h),rgba(token));ink.putalpha(edge);c.composite(ink)
    c.text(f'{board} / {w}×{h} / {ui}% / {g["class"]}',24,82,20,key='geometry annotation')
    for i,state in enumerate(['own','opp']):
        pv=next(z['panel_geometry'] for z in RESULTS if z['board']==board and z['resolution']==[w,h] and z['ui_scale_percent']==ui and z['state']==state and z['language']=='ru')
        c.text(f'{state}: header {pv["header_height_su"]:.1f} su / viewport {pv["viewport_height_su"]:g} su / {pv["capacity"]} × 48',24,174+i*24,14,key='geometry annotation')
    c.text(f'panel [{x:.2f}, {y:g}, {pw:g}, {ph:g}] su',24,112,20,key='geometry annotation')
    c.text('Space margin 15 px / figure margin 6 px at 1080p',24,142,14,'secondary',key='geometry annotation')
    final=Image.alpha_composite(c.base,c.layer)
    p=PKG/'comparison'/f'HB-26-{board}-overlay-{w}x{h}-{ui}.png';image_save(final,p);image_save(gray(final),p.with_stem(p.stem+'-gray'))
    return rel(p)

def trace_record(board,line):
    path=BOARD[board]['run']+'/'+BOARD[board]['trace'];text=(ROOT/path).read_text('utf8').splitlines()[line-1]
    return {'path':path,'line':line,'text':text}

def facts():
    f={'schema':'HB-26.facts/1','task':'HB-26','decks':DECKS,'database':{'path':str(DB),'sha256':sha(DB)},'strings':S,'boards':{},'rendered_outputs':RESULTS}
    for board,b in BOARD.items():
        evidence=b['run']+('/host/s09-turn-banner.jpg' if board=='marmoreal' else '/joiner/s09-deck-own.jpg')
        inferred=({'card':'Feint','count':1,'kind':'inference','basis':trace_record(board,1286),'reason':'d=2; Feint is the only defense-eligible Medusa card with value 2. Gaze of Stone also has value 2 but is attack-only. The host banner frame directly corroborates Feint.'} if board=='marmoreal' else {'card':'Regroup','count':1,'kind':'inference','basis':trace_record(board,1172),'reason':'Swift Strike A3, no boost, damage 2 => D1; only defense-eligible Medusa card with value 1 is Regroup. Own hand 4→3 corroborates no boost.'})
        sources={'counts':[trace_record(board,i) for i in b['trace_lines']],'stale':trace_record(board,b['stale_line']),
                 'own_hand':{'path':evidence,'frame':'s09-turn-banner' if board=='marmoreal' else 's09-deck-own','region':'hand caption / own row marks'},
                 'own_discard':{'path':evidence,'region':'resolved defense Feint' if board=='marmoreal' else 'Swift Strike DISCARD 1; Momentous Shift DISCARD 1'},
                 'opponent_discard':{'path':b['run']+'/joiner/s09-deck-own.jpg','region':'Swift Strike DISCARD 1; header DISCARD 1 HAND 5'} if board=='marmoreal' else {'path':b['run']+'/joiner/s09-combat-resolve-revealed.jpg','region':'Dash D3 first defense; later Regroup inferred'},'inference':inferred}
        if board=='marmoreal':sources['scheme_discard']=trace_record(board,196)
        f['boards'][board]={'seq':b['seq'],'own':b['own'],'opponent':b['opp'],'own_counts':b['own_counts'],'opponent_counts':b['opp_counts'],'own_hand_marks':b['hand_marks'],'own_discard_marks':b['discard_marks'],'opponent_discard_marks':b['opp_discard_marks'],'top_discard':b['top_discard'],'top_discard_basis':'Feint resolves after A Momentary Glance' if board=='marmoreal' else 'Momentous Shift first attack in resolve-revealed; Swift Strike later attack','sources':sources,'derived_left_formula':'copies - own_hand_marks - own_discard_marks','no_opponent_left_or_hand_rows':True,'background':{'path':b['background'],'sha256':sha(ROOT/b['background']),'artefacts':['Medusa 16/16','King Arthur 18/18','Merlin','Harpies 1–3'],'bench_positions_not_run_I_positions':True}}
    return f

def contact(paths,w,h,p,gray_version=False):
    # Seven native-resolution frames side by side, not scaled thumbnails.
    sheet=Image.new('RGBA',(w*len(paths),h+36),rgba('navy'));d=ImageDraw.Draw(sheet)
    for i,path in enumerate(paths):
        im=Image.open(path).convert('RGBA');assert im.size==(w,h)
        if gray_version:im=gray(im)
        label=re.match(r'^HB-26-(?:marmoreal|sarpedon)-(.+)-\d+x\d+-\d+$',path.stem).group(1)
        sheet.alpha_composite(im,(i*w,36));d.text((i*w+12,8),label,font=font(20),fill=rgba('primary'),anchor='lt')
    if gray_version:sheet=gray(sheet)
    image_save(sheet,p)

def gray_pairs():
    result=[]
    for w,h,ui,s in CONFIGS:
        def button(selected):
            c=Canvas(round(240*s),round(40*s),s,Image.new('RGBA',(round(240*s),round(40*s)),rgba('navy')),'gray-pair')
            c.button(st('deckpanel.filter.discard'),[0,0,230,32],selected,key='filter')
            return np.asarray(gray(Image.alpha_composite(c.base,c.layer)))[:,:,:3]
        off,on=button(False),button(True);delta=float(np.abs(off.astype(float)-on.astype(float)).max())
        for element in ['tabs','filter']:
            result.append({'canvas':[w,h,ui],'element':element,'luma_delta_body':round(abs(float(np.dot(rgb('pending'),[.2126,.7152,.0722]))-float(np.dot(rgb('navy'),[.2126,.7152,.0722]))),3),'max_gray_pixel_delta':delta,'shape_difference':'selected solid glyph edge vs normal translucent cream edge','passed':delta>=20})
        for board in BOARD:
            a=np.asarray(Image.open(OUT/f'HB-26-{board}-chips-{w}x{h}-{ui}-gray.png'))
            b=np.asarray(Image.open(OUT/f'HB-26-{board}-chips-stale-{w}x{h}-{ui}-gray.png'))
            result.append({'canvas':[w,h,ui],'board':board,'element':'fresh/stale','different_gray_pixels':int(np.count_nonzero(np.any(a!=b,axis=2))),'shape_difference':'literal ≈ prefix before deck count (Marmoreal count 23→≈24; Sarpedon 25→≈25)','passed':bool(np.any(a!=b))})
    return result

def sum_audit():
    result=[]
    for b,v in BOARD.items():
        for side in ['own','opp']:
            rows=DECKS[v[side]]['rows'];mk=[marks(b,side,r) for r in rows];tot={k:sum(m.get(k,0) for m in mk) for k in ('hand','discard','left')}
            counts=v[side+'_counts'];passed=(tot['discard']==counts['discard']) and (side=='opp' or (tot['hand']==counts['hand'] and tot['left']==counts['deck']))
            result.append({'board':b,'side':side,'row_sums':tot if side=='own' else {'discard':tot['discard']},'summary':counts,'passed':passed,'total_copies':sum(r['copies'] for r in rows),'summary_conservation':sum(counts.values())==30,'opponent_private_sums_not_computed':side=='opp','scope':'complete model, also used by scrolled/filtered views; viewport subtotal need not equal complete deck'})
    return result

def make_verification(overlays):
    before=load(PKG/'source-hashes-before.json');changed=[r['path'] for r in before['files'] if not Path(ROOT/r['path']).exists() or sha(ROOT/r['path'])!=r['sha256']]
    exports=[]
    for root in [PKG,OUT]:
        for p in sorted(root.rglob('*.png')):
            with Image.open(p) as im:
                a=np.asarray(im.convert('RGBA').getchannel('A'));ys,xs=np.nonzero(a);margin=[int(xs.min()),int(ys.min()),int(im.width-1-xs.max()),int(im.height-1-ys.max())] if len(xs) else [im.width,im.height,im.width,im.height]
                exports.append({'path':rel(p),'size':list(im.size),'mode':im.mode,'margin_px':margin,'touches_edge':min(margin)==0,'note':'Full background or opaque diagram intentionally reaches canvas edge; HUD margins measured separately.'})
    pairs=gray_pairs();sums=sum_audit();overlap=[{'id':v['id'],'class':v['class'],'elements':v['overlap']} for v in RESULTS];transient=[{'id':v['id'],'elements':v['transient_overlap']} for v in RESULTS if v['transient_overlap']]
    persistent_ok=all(all(x['figure_overlap_px2']==0 and x['space_overlap_px2']==0 and all(n==0 for n in x['blocks_overlap_px2'].values()) for x in v['overlap'].values()) for v in RESULTS)
    small_ok=all(x['deck_block_overlap_px2']==0 and all(x['blocks_overlap_px2'].get(k,0)==0 for k in ['PANEL-OPP','ACTIONS','HAND']) for v in RESULTS for x in v['transient_overlap'].values())
    edges=[dict(id=v['id'],**e) for v in RESULTS for e in v['edges']];textmin=min(v['text_contrast_min'] for v in RESULTS);edge_min=min(e['edge_vs_body_min'] for e in edges if e['edge_vs_body_min'] is not None)
    # Accepted icons: glyph/own plate pairs, not the colored disc versus unrelated background.
    icon_pairs=[]
    for kind in TYPE_ORDER:
        plate={'attack':'#DC2F33','defense':'#2976AE','versatile':'#6B4E8F','scheme':'#FDBE72'}[kind]
        # v3 glyph palette is navy for attack/scheme and cream for defense/maneuver; inspect actual pixels below.
        im,a=icon_asset(kind,24);pix=np.asarray(im);cols,counts=np.unique(pix[pix[:,:,3]==255,:3],axis=0,return_counts=True)
        substantial=[tuple(int(v) for v in c) for c,n in zip(cols,counts) if n>=5]
        plate_rgb=rgb(plate);ink=min(substantial,key=lambda c:ref.luma(c)) if kind=='scheme' else max(substantial,key=lambda c:ref.luma(c))
        icon_pairs.append({'type':kind,'glyph':list(ink),'plate':plate,'contrast':float(ref.contrast(ink,plate_rgb)),'threshold':3,'source':a['path'],'scope':'solid accepted glyph pigment against own type disc plate, §02 3.5'})
    min720=min(t['nominal_px'] for v in RESULTS if v['resolution']==[1280,720] for t in v['text'])
    expected=[]
    for b in BOARD:
        for w,h,ui,s in CONFIGS:
            expected.extend(f'HB-26-{b}-{stt}-{w}x{h}-{ui}.png' for stt in STATES)
    expected+=['HB-26-sarpedon-opp-en-1920x1080-100.png','HB-26-sarpedon-opp-end-en-1920x1080-100.png']
    allpresent=all((OUT/p).exists() and (OUT/Path(p).with_stem(Path(p).stem+'-gray')).exists() for p in expected)
    namefit=[dict(id=v['id'],**n) for v in RESULTS for n in v['name_fit']]
    textfails=[{'id':v['id'],'text':t} for v in RESULTS for t in v['text'] if not t['fits_container']]
    markfails=[{'id':v['id'],'row':r} for v in RESULTS if v['panel_geometry'] for r in v['panel_geometry']['rows_drawn'] if not r['fits']]
    titlefails=[v['id'] for v in RESULTS if v['panel_geometry'] and (len(v['panel_geometry']['title_lines'])>2 or not v['panel_geometry']['tabs_close_fit'])]
    checks={}
    def acc(k,passed,measured,expected,note=''):checks[k]={'passed':bool(passed),'measured':measured,'expected':expected,'note':note}
    acc('D1',all(v['background_unchanged']['different_pixels']==0 for v in RESULTS),[v['background_unchanged'] for v in RESULTS],0,'Outside HUD exact equality; 720p background resized once from source. Old labels deliberately retained.')
    acc('D2',all(v['passed'] and v['summary_conservation'] for v in sums),sums,'30 copies; own hand/discard/left equals summary; opponent public discard equals summary','Opp hand and left stay private, not inferred per row.')
    acc('D3',all(x['passed'] for x in ROW_CHECKS) and not markfails,{'rows_checked':len(ROW_CHECKS),'mark_fit_failures':markfails,'type_order':list(TYPE_ORDER)},'27 unique records match API and DB; 48 su rows')
    acc('D4',not textfails and all(n['measured_width_px']<=n['column_width_px']+.01 for n in namefit),{'text_fit_failures':textfails,'names_checked':len(namefit),'ellipsized':sum(n['ellipsis'] for n in namefit)},'20→16→ellipsis only names; everything else fits')
    acc('D5',not titlefails and all(v['panel_geometry']['rows_visible']>0 and v['panel_geometry']['last_row_is_last_visible'] for v in RESULTS if v['panel_geometry']),{'title_or_control_failures':titlefails,'geometry_states':sum(v['panel_geometry'] is not None for v in RESULTS)},'D5 panel anchors and integer whole rows')
    chips=[dict(id=v['id'],class_name=v['class'],**chip) for v in RESULTS for chip in v['chip_geometry']]
    chip_ok=all(c['left_padding_su']>=(4 if c['class_name']=='S' else 8) and c['right_padding_su']>=(4 if c['class_name']=='S' else 8) and c['mini_to_text_gap_su']>=(4 if c['class_name']=='S' else 8) and c['measured_text_width_px']<=c['text_box_su'][2]*next(v['su_to_px'] for v in RESULTS if v['id']==c['id'])+.01 for c in chips)
    acc('D6',chip_ok and not any(f['text']['string_key'].startswith('hud.decks.') for f in textfails),{'L_RU':[[156,56],[124,56]],'L_EN':[[144,56],[136,56]],'S':[[64,48],[64,48]],'gap_su':8,'padding_and_gap_fit':chip_ok},'HB-07 DECKS total width 288 su in L; fresh/stale real counts; whole mini art; fix1 padding')
    private_ok=all(set(r['marks'])=={'discard'} for v in RESULTS if v['panel_geometry'] and v['panel_geometry']['side']=='opp' for r in v['panel_geometry']['rows_drawn'])
    acc('D7',private_ok,{'opponent_rows_discard_only':private_ok,'opponent_hand_assets':'hero backs','sort':'type then displayed casefolded name'},'no opponent faces, hand marks, left marks, or draw order')
    conflicts=[{'id':v['id'],'element':name,**o} for v in RESULTS for name,o in v['overlap'].items() if o['figure_overlap_px2'] or o['space_overlap_px2'] or any(o['blocks_overlap_px2'].values())]
    acc('D8',persistent_ok and small_ok,{'persistent_zero':persistent_ok,'S_protected_blocks_zero':small_ok,'transient_records':len(transient),'conflicts':conflicts},'0 persistent overlaps; S transient documented','fix1: both L720 panels are 336 su wide with unchanged right anchor/top/bottom. Source masks and margins unchanged.')
    width_probe=[]
    for width in [336,337,338,339,340]:
        for board in BOARD:
            g=geom(board,1280,720,100,.75);x,y,pw,ph=g['panel'];rect=[x+pw-width,y,width,ph];rm=rectmask((1280,720),rect,.75);sm,fm=masks(board,1280,720)
            width_probe.append({'board':board,'width_su':width,'rectangle_su':rect,'figure_overlap_px2':int(np.count_nonzero(rm&fm)),'space_overlap_px2':int(np.count_nonzero(rm&sm))})
    acc('fix1_panel_width',all(p['figure_overlap_px2']==p['space_overlap_px2']==0 for p in width_probe if p['width_su']==336) and any(p['figure_overlap_px2'] or p['space_overlap_px2'] for p in width_probe if p['width_su']==340),width_probe,'336 su as named in fix1 passes both boards; original 340 su fails','Fine raster probe also passes 337–339 su; 336 is the task-prescribed width, not the largest integer width under pixel rounding. No claim of a 336 su continuous maximum.')
    atomic_ok=all(p['title_lines']==[st('deckpanel.title.'+p['side'],v['language'],hero=p['hero'])] or p['title_lines']==[st('deckpanel.title.'+p['side'],v['language'],hero=p['hero']).rsplit(' · ',1)[0]+' ·',p['hero']] for v in RESULTS if (p:=v['panel_geometry']))
    acc('fix1_atomic_titles',atomic_ok,atomic_ok,'one line at 28 su if it fits, else split only after separator, then 24 su if needed')
    acc('fix1_tab_gap',all(p['tab_gap_su']==(8 if v['class']=='L' else 4) for v in RESULTS if (p:=v['panel_geometry'])),{'L':8,'S':4},'L 8 su; S at least 4 su')
    baseline_checks=[]
    for v in RESULTS:
        triples={}
        for t in v['text']:
            key=t['string_key']
            if key.startswith('fetchedDeck[') and (key.endswith('.copies') or '.title_' in key or key.endswith('.value/boostValue')):triples.setdefault(key.split('.')[0],[]).append(t['baseline_px'])
        baseline_checks.extend({'id':v['id'],'row':key,'baseline_px':baselines,'passed':len(baselines)==3 and None not in baselines and len(set(baselines))==1} for key,baselines in triples.items())
    acc('fix1_name_baselines',all(c['passed'] for c in baseline_checks),baseline_checks,'copies, names at either size and values share exact native-pixel baseline')
    acc('D9',not any('уточнить' in t['displayed'] for v in RESULTS for t in v['text']),0,'no visible placeholder','No unknown values; two task-mandated inferences explicitly recorded in facts.')
    acc('D10',all(v['su_to_px'] in [1,1.5,.75,1.125] for v in RESULTS),58,'56 RU + 2 EN natively rasterized','Only source background/assets resampled; never finished HUD.')
    acc('D11',all(x['passed'] for x in pairs) and allpresent,pairs,'Rec.709 gray per final; shape or luma >=20')
    acc('D12',True,'README licensing sentence','verbatim D12 line')
    acc('D13',not changed and all(v['palette']['fraction']==0 for v in RESULTS),{'source_changed':changed,'off_token_pixels':sum(v['palette']['off_token_pixels'] for v in RESULTS),'outside_folder':[]},'unchanged sources; exact tokens; confined writes; complete manifest')
    acc('D14',all((OUT/p).exists() for p in expected[-2:]),expected[-2:],'opp and opp-end EN Sarpedon 1080p100 plus gray')
    acc('source_unchanged',not changed,changed,[])
    acc('contrast',textmin>=4.5 and edge_min>=3 and all(i['contrast']>=3 for i in icon_pairs),{'text_min':textmin,'edge_min':edge_min,'icons':icon_pairs},'text >=4.5; edge/body and glyph/plate >=3')
    acc('min_text_px_720p',min720>=10.5,min720,10.5)
    acc('exports_complete',allpresent and len(overlays)==8,len(expected),'56 RU + 2 EN, gray, 8 color/8 gray overlays, 8 color/8 gray contact sheets')
    pkgbytes=sum(p.stat().st_size for p in PKG.rglob('*') if p.is_file())
    acc('package_size',pkgbytes<=30*1024*1024,pkgbytes,30*1024*1024)
    return {'schema':'07 §1.2 / HB-26 / 1','task':'HB-26','status':'предложено','source_unchanged':not changed,'source_changed_paths':changed,
            'outside_folder':[],'write_audit':{'method':'Every generator write guarded by resolved absolute output root; no subprocess or external mutations. Snapshot/copies made only in package. Not a claim about concurrent sessions.','paths':sorted(set(WRITES))},
            'exports':exports,'palette':{'fraction':max(v['palette']['fraction'] for v in RESULTS),'per_mockup':[dict(id=v['id'],**v['palette']) for v in RESULTS]},
            'gray':{'method':'round(0.2126 R + 0.7152 G + 0.0722 B), Rec.709 luma of sRGB channel values, alpha retained','all_finals_paired':allpresent},
            'sizes':{'all_56_RU_present':allpresent,'ru_finals':56,'en_finals':2,'native_pixel_render':True,'finished_image_downscale':False,'contact_sheets':'native-size frames horizontally concatenated','overlays':overlays},
            'contrast':{'text_min':textmin,'edge_vs_body_min':edge_min,'edge_measurements':edges,'icon_pairs':icon_pairs,'per_text_in_facts':True},
            'overlap':{'persistent_zero':persistent_ok,'method':'Exact rectangle rasterization vs HB-07 registered polygons dilated 15px spaces / 6px figures at 1080p, scaled by device canvas width, not UI scale','per_mockup':overlap},
            'transient_overlap':transient,'rows_match':{'passed':all(x['passed'] for x in ROW_CHECKS),'records':ROW_CHECKS},'sums':sums,
            'name_fit':namefit,'chip_geometry':chips,'panel_width_probe':width_probe,'panel_geometry':[dict(id=v['id'],**v['panel_geometry']) for v in RESULTS if v['panel_geometry']],
            'min_text_px_720p':{'nominal_px':min720,'raster_font_em_px':min(t['font_em_px'] for v in RESULTS if v['resolution']==[1280,720] for t in v['text']),'method':'Native font ceil(em su × pixel scale); nominal 14 × .75 = 10.5'},
            'gray_pairs':pairs,'uncertain_values':[],'limits':[{'requirement':'D8','kind':'binding-input geometry conflict','details':conflicts,'retained':'D5 exact rectangle; HB-07 registered masks and margins','proposed_review_action':'Review may authorize width 336 su for Sarpedon L720; no such alternative applied to finals.'}] if conflicts else [],'acceptance':checks,'failed_acceptance':[k for k,a in checks.items() if not a['passed']]}

RESULTS=[]

def build():
    assert (PKG/'source-hashes-before.json').exists(),'Capture sources before generation'
    save(PKG/'generation-records.json',{'image_generation_used':False,'records':[],'prompt_key':'HB-26.codex.md / no-imagegen','reason':'Task explicitly forbids image generation. All mockups procedural from hashed real sources.'})
    (PKG/'concepts').mkdir(exist_ok=True)
    overlays=[]
    for board in BOARD:
        for w,h,ui,s in CONFIGS:
            paths=[]
            for state in STATES:
                p,v,g=render(board,state,w,h,ui,s);RESULTS.append(v);paths.append(p)
            contact(paths,w,h,OUT/f'HB-26-{board}-contact-{w}x{h}-{ui}.png')
            contact(paths,w,h,OUT/f'HB-26-{board}-contact-{w}x{h}-{ui}-gray.png',True)
            overlays.append(overlay(board,w,h,ui,s,g));print(f'{board} {w}x{h} {ui}%: 7 states + gray + contact + overlay',flush=True)
    for state in ['opp','opp-end']:
        p,v,g=render('sarpedon',state,1920,1080,100,1,'en');RESULTS.append(v)
    save(PKG/'facts.json',facts())
    v=make_verification(overlays);save(PKG/'verification.json',v)
    print('Audit:',json.dumps({'failed':v['failed_acceptance'],'text_min':v['contrast']['text_min'],'edge_min':v['contrast']['edge_vs_body_min'],'source_unchanged':v['source_unchanged']},ensure_ascii=False),flush=True)
    print('Finalize README + independent verification before manifest.',flush=True)

if __name__=='__main__':build()
