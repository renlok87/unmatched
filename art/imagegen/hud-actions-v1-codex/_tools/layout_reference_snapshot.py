#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""HB-07. Offline composition and audit; all writes constrained to two output roots.

python -B -X utf8 art/imagegen/hud-composition-v1-codex/_tools/build_mockups.py --capture
python -B -X utf8 art/imagegen/hud-composition-v1-codex/_tools/build_mockups.py

The icon generator snapshot is provenance only: never import or execute it.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import math
import re
from pathlib import Path
from functools import lru_cache
import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageOps

ROOT = Path(__file__).resolve().parents[4]
PACKAGE = ROOT / 'art/imagegen/hud-composition-v1-codex'
DERIVED = ROOT / 'scraped-data/derived/hud-composition-v1-codex'
PROMPT = 'docs/game-design/visual/06-tasks/prompts/HB-07.codex.md'
SPEC = 'docs/game-design/visual/04-hud-spec.md'
DESIGN = 'docs/game-design/visual/02-visual-design.md'
CARD_MANIFEST = 'art/imagegen/mvp-v1/reused-cardart.json'
FONT_DIR = Path('C:/Program Files/Epic Games/UE_5.8/Engine/Content/Slate/Fonts')
ICONS = ROOT / 'art/imagegen/hud-icons-v3'
STATES = ('own-turn', 'opp-turn', 'combat-defense')
CONFIGS = ((1920,1080,1.0,100), (1920,1080,1.0,150),
           (1280,720,.75,100), (1280,720,.75,150))
T = {'panel.bg':'#061623', 'panel.edge':'#F9EBDB', 'panel.bg.inset':'#15232E',
     'text.primary':'#F2EDE4', 'text.secondary':'#B9B2A6', 'card.navy':'#061623',
     'card.cream':'#F9EBDB','card.glyph':'#FAF8F2','turn.flash.yellow':'#F2C14E',
     'turn.flash.orange':'#E8812C','state.pending':'#0D7A89','state.warning':'#E8812C',
     'state.error':'#D9483F','team.p1.screen':'#DAC576','team.p2.screen':'#5786A8',
     'card.type.attack':'#DC2F33','card.type.defense':'#2976AE',
     'card.type.versatile':'#6B4E8F','card.type.scheme':'#FDBE72'}
BOARD = {
 'marmoreal':{'background':'docs/game-design/evidence/ENV-MAPS/p7-concept-paste-2026-10-01/p7c/packaged-marmoreal/bench-K1-1920x1080.png',
   'field':[410,255,1440,850], 'run':'docs/game-design/evidence/DE-FOOTAGE/2026-10-05/I/marmoreal/combat-20261005-235827',
   'own':'medusa','opponent':'king-arthur','hp':[14,17], 'hand':['gaze-of-stone','gaze-of-stone','snipe','clutching-claws','dash'],
   'deck':23,'discard':2,'oppHand':5,'oppDeck':24,'oppDiscard':1,'turn':3,
   'turn_trace':'combat-client-host.trace.txt',
   'polygons':[
    [[520,269],[543,267],[557,276],[602,267],[584,288],[579,307],[571,320],[555,322],[545,311],[536,287]],
    [[483,360],[507,363],[520,373],[554,365],[574,357],[563,380],[550,391],[547,405],[529,418],[510,408],[509,390],[492,381]],
    [[498,476],[502,463],[512,460],[526,475],[534,488],[543,518],[531,529],[506,529],[494,516]],
    [[474,596],[497,580],[506,566],[519,567],[531,582],[548,592],[564,611],[534,615],[529,625],[508,625],[499,615],[480,617]],
    [[1264,628],[1278,612],[1289,599],[1304,596],[1316,609],[1329,638],[1322,659],[1279,662]],
    [[1190,754],[1207,732],[1215,716],[1233,709],[1246,721],[1258,738],[1278,757],[1265,788],[1207,792]]]},
 'sarpedon':{'background':'docs/game-design/evidence/ENV-MAPS/p10-sarpedon-rework-2026-10-03/sarpedon-packaged/bench-K1-1920x1080.png',
   'field':[380,250,1490,860], 'run':'docs/game-design/evidence/DE-FOOTAGE/2026-10-05/I/sarpedon/combat-20261005-235948',
   'own':'king-arthur','opponent':'medusa','hp':[18,14], 'hand':['the-holy-grail','noble-sacrifice','swift-strike'],
   'deck':25,'discard':2,'oppHand':6,'oppDeck':23,'oppDiscard':2,'turn':2,
   'turn_trace':'combat-client-joiner.trace.txt',
   'polygons':[
    [[391,494],[416,499],[433,511],[445,506],[475,494],[473,512],[455,528],[461,546],[449,556],[427,556],[416,546],[420,526],[400,518]],
    [[497,566],[521,551],[530,539],[544,533],[559,548],[579,562],[589,580],[564,583],[562,594],[537,598],[521,583],[505,585]],
    [[378,631],[397,616],[406,601],[421,599],[435,614],[459,629],[479,645],[452,648],[445,660],[416,662],[405,648],[386,649]],
    [[653,508],[658,489],[667,477],[680,481],[686,494],[702,521],[699,544],[657,545]],
    [[1138,580],[1154,562],[1166,552],[1180,560],[1188,575],[1205,597],[1197,618],[1155,621]],
    [[1080,688],[1094,671],[1101,653],[1114,646],[1130,653],[1143,671],[1162,688],[1155,726],[1098,731]]]},
}

def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()

def relative(p):
    try: return Path(p).resolve().relative_to(ROOT).as_posix()
    except ValueError: return Path(p).as_posix()

def save_json(path, obj):
    guarded(path).write_text(json.dumps(obj,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')

def guarded(path):
    path = Path(path).resolve()
    if not any(path.is_relative_to(r.resolve()) for r in (PACKAGE,DERIVED)):
        raise ValueError('Write outside allowed roots: '+str(path))
    path.parent.mkdir(parents=True,exist_ok=True)
    return path

def save_image(im, path):
    im.save(guarded(path))

def load_json(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))

def collect_inputs():
    prompt=(ROOT/PROMPT).read_text(encoding='utf-8')
    paths={ROOT/PROMPT, ROOT/SPEC, ROOT/DESIGN}
    # Provenance tables enumerate all named files, without guessing wildcard paths.
    for s in re.findall(r'\| `([^`]+)` \|',prompt):
        p=ROOT/s
        if p.is_file(): paths.add(p)
    for b in BOARD.values():
        paths.add(ROOT/b['background'])
        paths.update((ROOT/b['run']).glob('*.trace.txt'))
    for p in ICONS.rglob('*'):
        if p.is_file(): paths.add(p)
    for row in load_json(ROOT/CARD_MANIFEST)['cards']:
        for lang in ('en','ru'): paths.add(ROOT/row[lang]['path'])
    paths.update(FONT_DIR/n for n in ('Roboto-BoldCondensed.ttf','Roboto-Regular.ttf'))
    paths.add(ROOT/'docs/unreal/contracts/hud/hud-style-tokens.json')
    return sorted(paths,key=relative)

def capture():
    path=PACKAGE/'source-hashes-before.json'
    if path.exists():
        raise RuntimeError('Baseline exists; never overwrite the before-work evidence.')
    files={relative(p):{'sha256':sha(p),'bytes':p.stat().st_size} for p in collect_inputs()}
    save_json(path,{'schema':'HB-07.source-hashes/1','files':files,
                   'icon_files':sum(k.startswith('art/imagegen/hud-icons-v3/') for k in files)})
    src=ICONS/'_tools/draw_icons.py'
    guarded(PACKAGE/'_tools/draw_icons_v3_snapshot.py').write_bytes(src.read_bytes())
    save_json(PACKAGE/'generation-records.json',{'task':'HB-07','image_generation':False,'records':[],
        'reason':'Задание запрещает ImageGen. Все выходы процедурно собраны из неизменённых исходников.'})
    (PACKAGE/'concepts').mkdir(exist_ok=True)
    print(f'Captured {len(files)} input hashes; copied icon generator byte-for-byte.')

def devalue(path):
    pool=load_json(path)['nodes'][2]['data']; memo={}
    def decode(i):
        if i<0: return None
        if i in memo: return memo[i]
        v=pool[i]
        if isinstance(v,dict): out={k:decode(n) for k,n in v.items()}
        elif isinstance(v,list): out=[decode(n) for n in v]
        else: out=v
        memo[i]=out
        return out
    return decode(0)

@lru_cache(None)
def original(path):
    with Image.open(path) as im: return im.convert('RGBA')

@lru_cache(None)
def font(size,bold=True):
    return ImageFont.truetype(str(FONT_DIR/('Roboto-BoldCondensed.ttf' if bold else 'Roboto-Regular.ttf')),size)

def rgb(token): return tuple(bytes.fromhex(T.get(token,token).lstrip('#')))

def luma(a):
    a=np.asarray(a,dtype=float)/255
    linear=np.where(a<=.04045,a/12.92,((a+.055)/1.055)**2.4)
    return linear @ np.array([.2126,.7152,.0722])

def contrast(fg,bg):
    a,b=luma(fg),luma(bg)
    return (np.maximum(a,b)+.05)/(np.minimum(a,b)+.05)

def gray(im):
    a=np.asarray(im.convert('RGB'),dtype=float)
    y=np.rint(a@np.array([.2126,.7152,.0722])).astype('uint8')
    return Image.fromarray(y).convert('RGB')

def geometry(board,w,h,s):
    W,H=w/s,h/s; small=W<1500; margin=16 if small else 24
    b=BOARD[board]; f=[v*(w/1920)/s for v in b['field']]
    rect={}
    rect['TOP']=(margin,margin,236 if small else 252,40 if small else 44)
    sw=(min(600,W-528) if small else (880 if w==1920 else 720))
    rect['STATUS']=((W-sw)/2,margin,sw,40 if small else 48)
    cw=480 if small else 560
    rect['CENTER']=((W-cw)/2,64 if small else 80,cw,104)
    rect['BANNER']=((W-420)/2,144,420,64)
    pw,ph=(240,96) if small else (340,136)
    rect['PANEL-LOC']=(margin,H-margin-ph,pw,ph)
    rect['PANEL-OPP']=(W-margin-pw,margin,pw,ph)
    rect['OPP-HAND']=(W-margin-300,120 if small else 168,300,87)
    cardw,cardh=(120,166) if small else (150,208)
    hand_left=268 if small else 376
    hand_right=W-(240 if small else 380)
    # Literal §2.6: bottom −16; clamp(H − FIELD.bottom −8,120,208).
    visible=min(cardh,max(120,H-f[3]-8))
    n=len(b['hand']); step=min(cardw+8,(hand_right-hand_left-cardw)/(n-1)) if n>1 else cardw
    total=cardw+(n-1)*step
    rect['HAND']=((hand_left+hand_right-total)/2,H-16-visible,total,visible)
    rect['HAND-CAPTION']=(rect['HAND'][0],rect['HAND'][1]-22,total,22)
    rect['DECKS']=(W-margin-(136 if small else 288),H-(120 if small else 160),136 if small else 288,48 if small else 56)
    rect['ACTIONS']=(W-margin-(216 if small else 344),H-margin-(48 if small else 72),216 if small else 344,48 if small else 72)
    rect['LOG']=(24,712 if w==1920 else 688,300,200 if w==1920 else 104)
    combatw,combath=(150,208) if small else (230,319)
    cy=240 if small else 360
    rect['COMBAT-L']=(margin,cy,combatw,combath)
    rect['COMBAT-R']=(W-margin-combatw,cy,combatw,combath)
    rect['ROLE-L']=(margin,cy+combath+4,combatw,24 if small else 28)
    rect['ROLE-R']=(W-margin-combatw,cy+combath+4,combatw,24 if small else 28)
    rect['DEFENSE-BUTTONS']=(margin,480 if small else 719,combatw,80 if small else 48)
    return {'canvas_su':[W,H],'class':'S' if small else 'L','field_su':f,'rectangles':rect,
            'card_size_su':[cardw,cardh],'hand_step_su':step,'hand_visible_su':visible}

def masks(board,w,h):
    b=BOARD[board]; topo=load_json(ROOT/f'backend/prisma/fixtures/boards/{board}.topology.json')
    rad=topo['spaceRadiusPx']; spaces=topo['spaces']
    # Map disc-inclusive source bounds into the measured FIELD (not the whole illustration).
    xs=[p['layout']['x'] for p in spaces]; ys=[p['layout']['y'] for p in spaces]
    bounds=[min(xs)-rad,min(ys)-rad,max(xs)+rad,max(ys)+rad]
    fx0,fy0,fx1,fy1=b['field']; q=w/1920
    sx=(fx1-fx0)/(bounds[2]-bounds[0]); sy=(fy1-fy0)/(bounds[3]-bounds[1])
    sm=Image.new('L',(w,h)); draw=ImageDraw.Draw(sm); mapped=[]
    for p in spaces:
        cx=fx0+(p['layout']['x']-bounds[0])*sx; cy=fy0+(p['layout']['y']-bounds[1])*sy
        box=[(cx-rad*sx)*q,(cy-rad*sy)*q,(cx+rad*sx)*q,(cy+rad*sy)*q]
        draw.ellipse(box,fill=255); mapped.append({'id':p['id'],'ellipse_px':box,'zones':p['zones']})
    fm=Image.new('L',(w,h)); d=ImageDraw.Draw(fm)
    for poly in b['polygons']: d.polygon([(round(x*q),round(y*q)) for x,y in poly],fill=255)
    field=Image.new('L',(w,h)); ImageDraw.Draw(field).rectangle([round(v*q) for v in b['field']],fill=255)
    return sm,fm,field,{'source_disc_bounds':bounds,'transform':[sx,sy,fx0,fy0], 'spaces':mapped}

class Canvas:
    def __init__(self,base,s):
        self.base=base.convert('RGBA'); self.s=s
        self.im=self.base.copy(); self.panels={}; self.texts=[]; self.icons=[]; self.scans=[]
    def box(self,r):
        x,y,w,h=r
        return (round(x*self.s),round(y*self.s),round((x+w)*self.s)-1,round((y+h)*self.s)-1)
    def panel(self,name,r,radius=6,alpha=.92):
        layer=Image.new('RGBA',self.im.size); d=ImageDraw.Draw(layer)
        box=self.box(r)
        d.rounded_rectangle(box,radius=round(radius*self.s),fill=rgb('panel.bg')+(round(alpha*255),))
        self.im=Image.alpha_composite(self.im,layer)
        mask=Image.new('L',self.im.size); ImageDraw.Draw(mask).rounded_rectangle(box,radius=round(radius*self.s),fill=255)
        self.panels[name]={'r':r,'mask':mask,'alpha':alpha}
        edge=Image.new('RGBA',self.im.size)
        ImageDraw.Draw(edge).rounded_rectangle(box,radius=round(radius*self.s),outline=rgb('panel.edge')+(round(.45*255),),width=max(1,round(self.s)))
        self.im=Image.alpha_composite(self.im,edge)
    def text(self,value,x,y,size=16,bold=False,token='text.primary',source=SPEC,key='',max_width=None):
        sizepx=max(1,math.ceil(size*self.s)); f=font(sizepx,bold)
        # Width overflow becomes ellipsis at the same size, never an undersized font.
        shown=str(value)
        if max_width is not None:
            while shown and f.getlength(shown)>max_width*self.s:
                shown=shown[:-2]+'…' if len(shown)>2 else '…'
                if shown=='…': break
        px,py=round(x*self.s),round(y*self.s)
        d=ImageDraw.Draw(self.im); bb=d.textbbox((px,py),shown,font=f,anchor='lt')
        # Contrast sampled from composed underlay BEFORE drawing glyphs.
        crop=np.asarray(self.im.convert('RGB'))[max(0,bb[1]):min(self.im.height,bb[3]),max(0,bb[0]):min(self.im.width,bb[2])]
        cr=float(np.min(contrast(rgb(token),crop))) if crop.size else None
        d.text((px,py),shown,font=f,fill=rgb(token),anchor='lt')
        self.texts.append({'text':str(value),'displayed':shown,'source':source,'key':key,
            'size_su':size,'font_em_px':sizepx,'nominal_px':size*self.s,'bbox_px':bb,
            'token':token,'contrast_min':cr})
    def image(self,path,r):
        x,y,w,h=r; size=(max(1,round(w*self.s)),max(1,round(h*self.s)))
        asset=ImageOps.contain(original(str(path)),size,Image.Resampling.LANCZOS)
        self.im.alpha_composite(asset,(round(x*self.s)+(size[0]-asset.width)//2,round(y*self.s)+(size[1]-asset.height)//2))
    def portrait(self,path,x,y,size):
        side=round(size*self.s); asset=ImageOps.fit(original(str(path)),(side,side),method=Image.Resampling.LANCZOS)
        mask=Image.new('L',(side,side)); ImageDraw.Draw(mask).ellipse((0,0,side-1,side-1),fill=255)
        self.im.paste(asset,(round(x*self.s),round(y*self.s)),mask)
    def icon(self,name,x,y,size=24):
        # No recolouring, token overrides or freshly drawn glyphs. Accepted PNG only.
        path=ICONS/f'sizes/{name}-96.png'
        if not path.exists(): raise RuntimeError('Missing accepted icon '+name)
        self.image(path,(x,y,size,size)); self.icons.append({'path':relative(path),'size_su':size,'size_px':size*self.s})
    def card(self,path,r,key):
        self.panel(key,r,radius=8)
        x,y,w,h=r; self.image(path,(x+2,y+2,w-4,h-4))
        self.scans.append({'path':relative(path),'frame_su':r,'whole_asset_fit':True,'text_over_asset':False})

def sources():
    heroes={k:devalue(ROOT/f'scraped-data/api/heroes/{k}.json') for k in ('medusa','king-arthur')}
    cards={row['stableContentKey']:row for row in load_json(ROOT/CARD_MANIFEST)['cards']}
    return heroes,cards

def localized_card(heroes,slug,title):
    entry=next(v for v in heroes[slug]['fetchedDeck'] if v['card']['title']==title)
    return entry['card'].get('i18n',{}).get('ru',{}).get('title','уточнить')

def hero_panel(c,rect,key,slug,hp,heroes,active,small):
    c.panel(key,rect); x,y,w,h=rect; hero=heroes[slug]['fetchedHero']
    avatar=ROOT/'scraped-data/images/heroes/avatars'/hero['avatar'].split('/')[-1]
    size=64 if small else 80
    c.portrait(avatar,x+12,y+12,size)
    if active: c.icon('marker-turn-ring',x+8,y+8,size+8)
    source=f'scraped-data/api/heroes/{slug}.json'
    c.text(hero['name'],x+size+24,y+14,20 if small else 24,True,source=source,key='fetchedHero.name',max_width=w-size-36)
    c.icon('resource-hp-full',x+size+24,y+45,24)
    c.text(f"{hp}/{hero['startHealth']}",x+size+52,y+47,20,True,source=source+' + '+BOARD[c.board]['run']+'/host/s09-turn-banner.jpg',key='HP observed / startHealth')
    if small:
        c.icon('marker-action-slot-de',x+size+24,y+70,24)
        c.icon('marker-action-slot-de',x+size+52,y+70,24)
    else:
        for i,sidekick in enumerate(hero['sidekicks']):
            sx=x+12+i*68; sy=y+94
            c.portrait(ROOT/'scraped-data/images/heroes/sidekicks'/sidekick['avatar'].split('/')[-1],sx,sy,40)
            c.text(str(i+1) if len(hero['sidekicks'])>1 else sidekick['name'],sx+43,sy+3,14,True,source=source,key=f'fetchedHero.sidekicks[{i}]',max_width=50 if len(hero['sidekicks'])==1 else 20)
            c.text(f"{sidekick['startHealth']}/{sidekick['startHealth']}",sx+43,sy+23,14,False,source=source,key=f'sidekicks[{i}].startHealth')
        c.icon('marker-action-slot-de',x+w-68,y+94,24)
        c.icon('marker-action-slot-de',x+w-36,y+94,24)

def render(board,state,w,h,dpi,ui,heroes,cards):
    s=dpi*ui/100; g=geometry(board,w,h,s); r=g['rectangles']; small=g['class']=='S'; b=BOARD[board]
    c=Canvas(original(str(ROOT/b['background'])).resize((w,h),Image.Resampling.LANCZOS),s); c.board=board
    c.panel('TOP',r['TOP']); x,y,rw,rh=r['TOP']
    c.text('Меню',x+12,y+12,14,True,key='hud.top.menu'); c.icon('resource-connection-online',x+50,y+8)
    c.text(f"Ход {b['turn']}",x+82,y+10,16,True,source=b['run']+'/'+b['turn_trace'],key='turnCount preceding reference SHOT')
    if small: c.text('Журнал',x+153,y+12,14,True,key='hud.log.title')
    c.panel('STATUS',r['STATUS']); x,y,rw,rh=r['STATUS']
    if state=='own-turn': text='Выберите действие: манёвр, атака или схема'; key='ms.status.action'
    elif state=='opp-turn': text=heroes[b['opponent']]['fetchedHero']['name']+' — выбирает действие'; key='ms.status.opp + ms.opp.phase.turn'
    else: text='Вас атакуют: выберите карту защиты или «Без защиты»'; key='ms.status.defend'
    c.text(text,x+12,y+12,20 if small else 24,True,token='text.secondary' if state=='opp-turn' else 'text.primary',key=key,max_width=rw-24)
    hero_panel(c,r['PANEL-LOC'],'PANEL-LOC',b['own'],b['hp'][0],heroes,state=='own-turn',small)
    hero_panel(c,r['PANEL-OPP'],'PANEL-OPP',b['opponent'],b['hp'][1],heroes,state!='own-turn',small)
    # OPP-HAND: compressed backs, count and real deck/discard counts outside scans.
    c.panel('OPP-HAND',r['OPP-HAND']); x,y,rw,rh=r['OPP-HAND']
    back=ROOT/'scraped-data/images/heroes/card-covers'/heroes[b['opponent']]['fetchedHero']['cardBackImage'].split('/')[-1]
    for i in range(b['oppHand']): c.image(back,(x+12+i*32,y+6,32,45))
    c.text(f"Рука {b['oppHand']}/7",x+12,y+61,14,False,source=b['run']+'/host/s09-turn-banner.jpg',key='opponent hand count')
    c.text(f"Колода {'≈' if board=='sarpedon' else ''}{b['oppDeck']} · Сброс {b['oppDiscard']}",x+115,y+61,14,False,source=b['run']+'/host/s09-turn-banner.jpg',key='opponent deck / discard',max_width=rw-127)
    # HAND: whole scan fitted in complete frame; portion below viewport is clipped by the canvas per §2.6.
    x,y,rw,rh=r['HAND']; cw,ch=g['card_size_su']
    for i,slug in enumerate(b['hand']):
        row=cards[f"{b['own']}:{slug}"]; path=ROOT/row['ru']['path']
        c.card(path,(x+i*g['hand_step_su'],y,cw,ch),f'HAND-{i}')
    c.panel('HAND-CAPTION',r['HAND-CAPTION'],radius=4)
    c.text(f"Рука {len(b['hand'])}/7",x+8,y-19,14,False,source=b['run']+'/host/s09-turn-banner.jpg' if board=='marmoreal' else b['run']+'/joiner/s09-deck-own.jpg',key='own hand count')
    # New-card label is outside the scan, in the caption row.
    if board=='marmoreal': c.text('Новая',x+rw-60,y-19,14,True,key='hud.card.new / Dash NEW in reference JPG')
    c.panel('DECKS',r['DECKS']); x,y,rw,rh=r['DECKS']
    ownback=ROOT/'scraped-data/images/heroes/card-covers'/heroes[b['own']]['fetchedHero']['cardBackImage'].split('/')[-1]
    c.image(ownback,(x+6,y+5,32,45 if not small else 38))
    c.text(str(b['deck']) if small else f"Колода {b['deck']}",x+42,y+16,20 if small else 16,True,source=b['run']+'/host/s09-turn-banner.jpg' if board=='marmoreal' else b['run']+'/joiner/s09-deck-own.jpg',key='own deck')
    c.icon('resource-card',x+(76 if small else 156),y+12,24)
    c.text(str(b['discard']) if small else f"Сброс {b['discard']}",x+(106 if small else 188),y+16,20 if small else 16,True,source=b['run']+'/host/s09-turn-banner.jpg' if board=='marmoreal' else b['run']+'/joiner/s09-deck-own.jpg',key='own discard')
    c.panel('ACTIONS',r['ACTIONS']); x,y,rw,rh=r['ACTIONS']
    for i,(name,label) in enumerate([('action-maneuver','МАНЁВР'),('action-attack','АТАКА'),('action-scheme','СХЕМА'),(None,'КОНЕЦ ХОДА')]):
        xx=x+8+i*(50 if small else 82)
        if name: c.icon(name,xx,y+4,40 if small else 48)
        else:
            # action-end-turn does not exist in v3; never substitute a misleading icon.
            c.text('уточнить',xx,y+12,14,True,source=PROMPT,key='missing accepted action-end-turn PNG')
        if not small: c.text(label,xx,y+54,14,True,key='hud.action.'+str(i),max_width=80)
    if not small and state!='combat-defense':
        c.panel('LOG',r['LOG']); x,y,rw,rh=r['LOG']
        c.text('Журнал',x+12,y+12,24,True,key='hud.log.title')
        # Exact names of combat cards, no invented event/sequence or score.
        c.text(localized_card(heroes,'king-arthur','Swift Strike'),x+12,y+48,16,False,source='scraped-data/api/heroes/king-arthur.json + '+b['run']+'/host/s09-turn-banner.jpg',key='combat attack card i18n.ru.title missing')
        defense_title='Feint' if board=='marmoreal' else 'Regroup'
        c.text(localized_card(heroes,'medusa',defense_title),x+12,y+72,16,False,source='scraped-data/api/heroes/medusa.json + '+b['run']+'/host/s09-turn-banner.jpg',key='combat defense card i18n.ru.title')
    if state=='own-turn':
        c.panel('BANNER',r['BANNER']); x,y,rw,rh=r['BANNER']
        c.text('ВАШ ХОД',x+140,y+17,36,True,token='turn.flash.yellow',key='hud.turn.banner')
    if state=='combat-defense':
        c.panel('CENTER',r['CENTER']); x,y,rw,rh=r['CENTER']
        c.text('Ждём защиту…',x+12,y+12,24,True,key='hud.combat.wait.defense')
        c.text('уточнить',x+12,y+48,16,False,source=PROMPT,key='combatInfo.timeoutAt absent / no invented seconds')
        c.text('Защититься · Без защиты',x+12,y+76,16,False,key='hud.combat.defend / hud.combat.no.defense')
        if board=='marmoreal':
            row=cards['medusa:feint']; c.card(ROOT/row['ru']['path'],r['COMBAT-L'],'COMBAT-L')
        else:
            c.panel('COMBAT-L',r['COMBAT-L']); x,y,rw,rh=r['COMBAT-L']
            c.icon('action-defense',x+(rw-64)/2,y+32,64)
            c.text('уточнить',x+12,y+116,16,False,source=PROMPT,key='run I lacks Arthur defense-window card')
        c.card(back,r['COMBAT-R'],'COMBAT-R')
        for name,label,icon in [('ROLE-L','ЗАЩИТА','action-defense'),('ROLE-R','АТАКА','action-attack')]:
            c.panel(name,r[name],radius=4); x,y,rw,rh=r[name]
            c.icon(icon,x+2,y+2,24); c.text(label,x+32,y+7,14,True,key='hud.combat.role.'+name,max_width=rw-40)
        c.panel('DEFENSE-BUTTONS',r['DEFENSE-BUTTONS'],radius=4); x,y,rw,rh=r['DEFENSE-BUTTONS']
        if small:
            c.text('ЗАЩИТИТЬСЯ',x+12,y+12,20,True,key='hud.combat.defend',max_width=rw-24)
            c.text('БЕЗ ЗАЩИТЫ',x+12,y+52,20,True,key='hud.combat.no.defense',max_width=rw-24)
        else:
            c.text('ЗАЩИТИТЬСЯ',x+12,y+16,20,True,key='hud.combat.defend',max_width=110)
            c.text('БЕЗ ЗАЩИТЫ',x+126,y+16,20,True,key='hud.combat.no.defense',max_width=rw-138)
    return c,g

def panel_audit(c,sm,fm,field):
    sa=np.asarray(sm)>0; fa=np.asarray(fm)>0; ra=np.asarray(field)>0
    rows={}
    for key,p in c.panels.items():
        a=np.asarray(p['mask'])>0
        # Per-panel contrast: opaque glyph against the actual alpha-composited underlay,
        # excluding edge pixels and content; worst case across the panel interior.
        x0,y0,x1,y1=c.box(p['r'])
        x0,y0=max(0,x0),max(0,y0); x1,y1=min(c.im.width,x1+1),min(c.im.height,y1+1)
        base=np.asarray(c.base.crop((x0,y0,x1,y1)).convert('RGB'),dtype=float)
        bg=np.rint(np.asarray(rgb('panel.bg'))*p['alpha']+base*(1-p['alpha']))
        local=a[y0:y1,x0:x1]; interior=local.copy()
        inset=max(2,round(c.s*2)); interior[:inset]=False; interior[-inset:]=False
        interior[:,:inset]=False; interior[:,-inset:]=False
        cr={t:float(np.min(contrast(rgb(t),bg[interior]))) if np.any(interior) else None for t in ('text.primary','text.secondary','turn.flash.yellow')}
        edge=np.rint(np.asarray(rgb('panel.edge'))*.45+bg*.55)
        edge_inside=contrast(edge,bg)
        # Same-pixel original scene is an exterior proxy, not a neighbouring edge sample.
        boundary=local.copy(); boundary[inset:-inset,inset:-inset]=False
        exterior_proxy=contrast(edge,base)
        rows[key]={'rectangle_su':p['r'],'figure_overlap_px2':int(np.count_nonzero(a&fa)),
            'space_overlap_px2':int(np.count_nonzero(a&sa)), 'field_rectangle_overlap_px2':int(np.count_nonzero(a&ra)),
            'text_contrast_worst_case':cr,
            'edge_vs_body_contrast_min':float(np.min(edge_inside[local])) if np.any(local) else None,
            'edge_vs_original_scene_proxy_min':float(np.min(exterior_proxy[boundary])) if np.any(boundary) else None,
            'persistent':key not in ('CENTER','BANNER')}
    return rows

def overlay(board,state,w,h,s,g,proposed=False):
    # An annotation drawing only: no scene, board pixels, portraits or card images.
    c=Canvas(Image.new('RGB',(w,h),rgb('panel.bg.inset')),s)
    sm,fm,field,_=masks(board,w,h)
    tint=Image.new('RGBA',(w,h),rgb('state.pending')+(95,)); c.im=Image.composite(tint,c.im,sm).convert('RGBA')
    tint=Image.new('RGBA',(w,h),rgb('turn.flash.orange')+(255,)); c.im=Image.composite(tint,c.im,fm).convert('RGBA')
    r=g['rectangles']; visible=['TOP','STATUS','PANEL-LOC','PANEL-OPP','OPP-HAND','HAND','HAND-CAPTION','DECKS','ACTIONS']
    if g['class']=='L' and state!='combat-defense': visible+=['LOG']
    if state=='combat-defense': visible+=['CENTER','COMBAT-L','COMBAT-R','ROLE-L','ROLE-R','DEFENSE-BUTTONS']
    if state=='own-turn': visible+=['BANNER']
    for key in visible:
        rr=list(r[key])
        if proposed and key=='HAND':
            rr[1]=g['field_su'][3]+30; rr[3]=max(1,g['canvas_su'][1]-16-rr[1])
        if proposed and key=='HAND-CAPTION': rr[1]=g['field_su'][3]+8
        if proposed and key=='OPP-HAND' and g['class']=='S': rr=[g['canvas_su'][0]-16-240,120,240,40]
        c.panel(key,rr)
        x,y,ww,hh=rr
        c.text(key,x+4,y+3,14,True,max_width=ww-8)
        if hh>=50:
            c.text(f'{x:.0f},{y:.0f} · {ww:.0f}×{hh:.0f} su',x+4,y+24,14,False,max_width=ww-8)
    return c.im.convert('RGB')

def proposal_audit(c,g,sm,fm,field):
    """Geometry-only alternative; keep actual text/content acceptance separate."""
    trial=Canvas(c.base,c.s)
    for key,p in c.panels.items():
        r=list(p['r'])
        if key.startswith('HAND-') and key!='HAND-CAPTION': r[1]=g['field_su'][3]+30
        if key=='HAND-CAPTION': r[1]=g['field_su'][3]+8
        if key=='OPP-HAND' and g['class']=='S': r=[g['canvas_su'][0]-16-240,120,240,40]
        trial.panel(key,r)
    rows=panel_audit(trial,sm,fm,field)
    return {'scope':'geometry only; proposed hand crop and count-only opponent hand, not content acceptance',
            'panels':rows,'persistent_overlap_pass':all(not(v['space_overlap_px2'] or v['figure_overlap_px2']) for v in rows.values() if v['persistent'])}

def panel_intersections(c):
    rows=[]; panels=list(c.panels.items())
    for i,(ka,pa) in enumerate(panels):
        for kb,pb in panels[i+1:]:
            a=c.box(pa['r']); b=c.box(pb['r'])
            box=[max(0,a[0],b[0]),max(0,a[1],b[1]),min(c.im.width,a[2]+1,b[2]+1),min(c.im.height,a[3]+1,b[3]+1)]
            if box[2]<=box[0] or box[3]<=box[1]: continue
            aa=np.asarray(pa['mask'].crop(box))>0; bb=np.asarray(pb['mask'].crop(box))>0
            area=int(np.count_nonzero(aa&bb))
            if area: rows.append({'blocks':[ka,kb],'area_px2':area})
    return rows

def icon_flat_tone_audit(paths):
    """Source PNG solid tones only. Anti-alias pixels are not treated as flat tones."""
    rows=[]
    for path in sorted(paths):
        a=np.asarray(original(str(ROOT/path))); opaque=a[a[:,:,3]==255,:3]
        colors,counts=np.unique(opaque,axis=0,return_counts=True)
        order=np.argsort(counts)[::-1]; tones=[colors[i] for i in order[:3]]
        pairs=[{'tones':['#'+bytes(tones[i]).hex().upper(),'#'+bytes(tones[j]).hex().upper()],
                'contrast':float(contrast(tones[i],tones[j]))} for i in range(len(tones)) for j in range(i+1,len(tones))]
        rows.append({'path':path,'dominant_three_solid_tones':['#'+bytes(t).hex().upper() for t in tones],
                     'pairwise_wcag':pairs,'scope':'diagnostic palette pairs, no spatial adjacency or exterior certification'})
    return rows

def contact(images,labels,path,thumbw=640):
    cols=2; rows=math.ceil(len(images)/cols); th=round(thumbw*9/16)
    sheet=Image.new('RGB',(cols*thumbw,rows*(th+32)),rgb('panel.bg'))
    d=ImageDraw.Draw(sheet)
    for i,(im,label) in enumerate(zip(images,labels)):
        x=(i%cols)*thumbw; y=(i//cols)*(th+32)
        d.text((x+12,y+7),label,font=font(16),fill=rgb('text.primary'))
        sheet.paste(im.resize((thumbw,th),Image.Resampling.LANCZOS),(x,y+32))
    save_image(sheet,path)

def hash_mismatches(before):
    changed=[]
    for path,meta in before['files'].items():
        p=ROOT/path if not Path(path).is_absolute() else Path(path)
        if not p.exists() or sha(p)!=meta['sha256']: changed.append(path)
    return changed

def build():
    before=load_json(PACKAGE/'source-hashes-before.json')
    if hash_mismatches(before): raise RuntimeError('Input changed since capture; preserve baseline and investigate.')
    heroes,cards=sources(); outputs=[]; audit=[]; overlayims=[]; proposalims=[]; labels=[]; mocks=[]; textfacts=[]
    maskdata={}
    for board in BOARD:
        for w,h,dpi,ui in CONFIGS:
            sm,fm,field,md=masks(board,w,h)
            save_image(sm,PACKAGE/'comparison'/f'mask-{board}-{w}x{h}-spaces.png')
            save_image(fm,PACKAGE/'comparison'/f'mask-{board}-{w}x{h}-figures.png')
            maskdata[f'{board}-{w}x{h}']=md
            for state in STATES:
                c,g=render(board,state,w,h,dpi,ui,heroes,cards)
                name=f'HB-07-{board}-{state}-{w}x{h}-{ui}'
                im=c.im.convert('RGB'); mockpath=DERIVED/(name+'.png'); graypath=DERIVED/(name+'-gray.png')
                save_image(im,mockpath); save_image(gray(im),graypath)
                panels=panel_audit(c,sm,fm,field)
                collisions={k:v for k,v in panels.items() if v['persistent'] and (v['space_overlap_px2'] or v['figure_overlap_px2'])}
                alltexts=c.texts; textfacts.extend({'mockup':name,**t} for t in alltexts)
                audit.append({'id':name,'board':board,'state':state,'resolution':[w,h], 'ui_scale_percent':ui,
                    'device_scale':dpi,'su_to_px':dpi*ui/100,'canvas_su':g['canvas_su'],'class':g['class'],
                    'panels':panels,'persistent_overlap_pass':not collisions,
                    'panel_to_panel_overlaps':panel_intersections(c),
                    'text_truncations':[t for t in alltexts if t['displayed']!=t['text']],
                    'proposal':proposal_audit(c,g,sm,fm,field),
                    'smallest_text_nominal_px':min(t['nominal_px'] for t in alltexts),
                    'smallest_text_font_em_px':min(t['font_em_px'] for t in alltexts),
                    'smallest_icon_su':min(t['size_su'] for t in c.icons),
                    'text_contrast_min':min(t['contrast_min'] for t in alltexts if t['contrast_min'] is not None),
                    'hand':{'card_size_su':g['card_size_su'],'step_su':g['hand_step_su'],
                        'visible_height_su':g['hand_visible_su'],'whole_scan_fitted_before_viewport_clip':True,
                        'scan_viewport_clipped':g['hand_visible_su']<g['card_size_su'][1]},
                    'accepted_icons':c.icons,'scans':c.scans,
                    'state_fidelity':'layout projection from multiple run-I snapshots; not synchronized replay',
                    'combat_defense_evidence': 'Medusa Feint was observed after reveal; attack stays hidden in this composition' if board=='marmoreal' else 'Arthur defense window not evidenced; placeholders shown' })
                ov=overlay(board,state,w,h,dpi*ui/100,g)
                save_image(ov,PACKAGE/'comparison'/(name+'-overlay.png'))
                save_image(gray(ov),PACKAGE/'comparison'/(name+'-overlay-gray.png'))
                prop=overlay(board,state,w,h,dpi*ui/100,g,True)
                save_image(prop,PACKAGE/'comparison'/(name+'-proposal-overlay.png'))
                save_image(gray(prop),PACKAGE/'comparison'/(name+'-proposal-overlay-gray.png'))
                overlayims.append(ov); proposalims.append(prop); labels.append(f'{board} | {state} | {w}x{h} UI {ui}% {g["class"]}'); mocks.append(im)
                outputs.append({'id':name,'color':relative(mockpath),'gray':relative(graypath),
                    'background':BOARD[board]['background'],'geometry':g})
                print(name, 'overlap PASS' if not collisions else 'overlap FAIL: '+','.join(collisions),flush=True)
    for board in BOARD:
        for w,h,dpi,ui in CONFIGS:
            ids=[i for i,row in enumerate(audit) if row['board']==board and row['resolution']==[w,h] and row['ui_scale_percent']==ui]
            group=DERIVED/f'comparison-{board}-{w}x{h}-{ui}.png'
            contact([mocks[i] for i in ids],[labels[i] for i in ids],group,thumbw=w)
            contact([gray(mocks[i]) for i in ids],[labels[i] for i in ids],group.with_stem(group.stem+'-gray'),thumbw=w)
            group=PACKAGE/'comparison'/f'comparison-{board}-{w}x{h}-{ui}.png'
            contact([overlayims[i] for i in ids],[labels[i] for i in ids],group,thumbw=w)
            contact([gray(overlayims[i]) for i in ids],[labels[i] for i in ids],group.with_stem(group.stem+'-gray'),thumbw=w)
    contact(mocks,labels,DERIVED/'contact-sheet.png')
    contact([gray(im) for im in mocks],labels,DERIVED/'contact-sheet-gray.png')
    contact(overlayims,labels,PACKAGE/'comparison/contact-sheet.png')
    contact([gray(im) for im in overlayims],labels,PACKAGE/'comparison/contact-sheet-gray.png')
    contact(proposalims,labels,PACKAGE/'comparison/proposal-contact-sheet.png')
    contact([gray(im) for im in proposalims],labels,PACKAGE/'comparison/proposal-contact-sheet-gray.png')
    save_json(PACKAGE/'masks.json',{'method':'manual conservative six-figure silhouette polygons from the specified frames; affine topology disc bounds mapped to measured FIELD',
        'uncertainty_px_1080p':15,'exact_camera_projection_available':False,
        'figures':{k:{'source':v['background'],'polygons_1080p':v['polygons']} for k,v in BOARD.items()},'space_mapping':maskdata})
    changed=hash_mismatches(before)
    snapshot=PACKAGE/'_tools/draw_icons_v3_snapshot.py'
    expected={p:h for p,h in re.findall(r'`([^`]+)`[^\n]*?\| file \| \d+ \| ([0-9a-f]{64}) \|',(ROOT/PROMPT).read_text(encoding='utf-8'))}
    mismatches=[{'path':p,'expected':h,'observed':before['files'][p]['sha256']} for p,h in expected.items() if p in before['files'] and before['files'][p]['sha256']!=h]
    failures=[]
    for row in audit:
        if not row['persistent_overlap_pass']: failures.append({'id':row['id'],'rule':'persistent panels overlap figure/space mask','blocks':[k for k,v in row['panels'].items() if v['persistent'] and (v['space_overlap_px2'] or v['figure_overlap_px2'])]})
        if row['text_contrast_min']<4.5: failures.append({'id':row['id'],'rule':'text contrast < 4.5','actual':row['text_contrast_min']})
    verification={'schema':'HB-07.verification/1','status':'предложено','acceptance_pass':False,
       'inputs_unchanged':not changed,'changed_inputs':changed,'input_count':len(before['files']),
       'expected_hash_mismatches':mismatches,'icon_snapshot_byte_identical':sha(snapshot)==sha(ICONS/'_tools/draw_icons.py'),
       'primary_mockups':24,'gray_copies':24,'grayscale_method':'Rec.709 luma on sRGB samples: round(.2126 R + .7152 G + .0722 B)',
       'minimum_text_su':min(t['size_su'] for t in textfacts),'minimum_720p_text_nominal_px':min(row['smallest_text_nominal_px'] for row in audit if row['resolution'][1]==720),
       'minimum_icon_su':min(row['smallest_icon_su'] for row in audit),'failure_details':failures,
       'proposal_geometry_pass_count':sum(row['proposal']['persistent_overlap_pass'] for row in audit),
       'icon_flat_tone_diagnostics':icon_flat_tone_audit({i['path'] for row in audit for i in row['accepted_icons']}),
       'limitations':[
        'Specified Marmoreal background has 3D palace and trees, not painted backdrop; both bench frames already contain permanent figure names / HP labels. Background unaltered, its text is not our HUD.',
        '§1.6 and §2.6 HAND clamp / bottom −16 plus caption overlap bottom spaces; hand viewport clips full scans. Literal specification is retained and collisions are reported.',
        'Class S OPP-HAND has no explicit S rectangle; inherited width 300 and top y120 collide with STATUS/CENTER and top-right field. Proposed compact count strip is on separate overlay sheets only.',
        'In class S 1138x640 the two stacked defense buttons from §2.7 overlap PANEL-LOC. Panel-to-panel intersections are recorded; proposal currently addresses field collisions only.',
        'The accepted v3 set has no action-end-turn PNG; literal уточнить is shown instead of inventing a glyph.',
        'No synchronized run-I own/opp/defense snapshots with all requested values; backgrounds have original figure placements and HP. Run-I data is a HUD sample, not an exact match replay.',
        'Arthur combat-defense cannot be reconstructed from the supplied run-I combat (Merlin attacks Medusa). Slot and timeout use уточнить.',
        'Masks are conservative manual figure outlines and affine topology ellipses, not extracted UE depth/object-ID masks or a calibrated perspective projection; zero on these masks would not prove exact runtime overlap.',
        'Printed card-scan text has fixed source typography and is not covered by procedural HUD minimum-size / WCAG checks.',
        'Panel edge is measured against body; full boundary contrast against exterior scene and every icon internal glyph edge is not certified. Numeric diagnostic is recorded, no blanket contrast pass.',
       ],'mockups':audit}
    save_json(PACKAGE/'verification.json',verification)
    facts={'heroes':heroes,'matches':{k:{key:value for key,value in v.items() if key not in ('polygons','background','field')} for k,v in BOARD.items()},
           'text_instances':textfacts,'ui_tokens':T,'token_source':DESIGN+' §§2–4 + task prompt',
           'match_data_scope':'explicit task values + reference JPG + turnCount near SHOT in trace; state snapshots intentionally not claimed synchronized'}
    save_json(PACKAGE/'facts.json',facts)
    write_readme(verification)
    alloutputs={}
    for root in (PACKAGE,DERIVED):
        for p in sorted(root.rglob('*')):
            if p.is_file() and p.name!='manifest.json': alloutputs[relative(p)]={'sha256':sha(p),'bytes':p.stat().st_size}
    save_json(PACKAGE/'manifest.json',{'schema':'HB-07.manifest/1','status':'предложено',
       'inputs':before['files'],'outputs':alloutputs,'mockups':outputs,'facts':'facts.json',
       'script':relative(Path(__file__)),'write_roots':[relative(PACKAGE),relative(DERIVED)],
       'generation_records':'generation-records.json','git_commands':False,'unreal_access':False})
    print('Completed package; acceptance intentionally FAIL where source/spec constraints conflict.')

def write_readme(v):
    failed=sum(not r['persistent_overlap_pass'] for r in v['mockups'])
    text=f'''# HB-07 — компоновка GAME

Статус: **предложено**. Приёмка: **не пройдена**; это воспроизводимая проверка заданной раскладки, а не утверждение о её готовности к внедрению.

Собраны 24 цветных макета и 24 Rec.709-копии: обе реальные доски, три состояния, четыре сочетания разрешения и масштаба UI. Фон — только два заданных bench-K1, без ретуши. Прогон I используется только для данных HUD. ImageGen не вызывался; [generation-records.json](generation-records.json) пуст, папка concepts/ предназначена только для генераций и остаётся пустой. Принятые v3 PNG используются без перекрашивания; генератор скопирован побайтно в _tools/draw_icons_v3_snapshot.py и не выполняется.

## Просмотр

- [Все макеты, цвет](../../../scraped-data/derived/hud-composition-v1-codex/contact-sheet.png) · [серый](../../../scraped-data/derived/hud-composition-v1-codex/contact-sheet-gray.png).
- [Все схемы, цвет](comparison/contact-sheet.png) · [серый](comparison/contact-sheet-gray.png). Здесь нет пикселей сканов, аватаров, доски или окружения.
- [Предлагаемая геометрия, цвет](comparison/proposal-contact-sheet.png) · [серый](comparison/proposal-contact-sheet-gray.png). Нулевое пересечение её постоянных блоков: {v['proposal_geometry_pass_count']} из 24; это проверка геометрии, не приёмка содержимого или полноты сканов.
- В comparison/: индивидуальные схемы `HB-07-<board>-<state>-<res>-<scale>-overlay.png`, серые копии и схемы предложения `*-proposal-overlay.png`.
- Листы `comparison-<board>-<res>-<scale>.png` собраны с исходным размером каждого кадра: 1920×1080 либо 1280×720. Их серые пары заканчиваются на `-gray.png`. Листы с артом находятся только в scraped-data/derived/hud-composition-v1-codex/; схемы — здесь.

## Что проверено

[verification.json](verification.json) содержит замеры каждого реально нарисованного блока: площадь пересечения с маской фигур, эллипсами всех клеток и прямоугольником FIELD; минимальный контраст каждого цвета текста на альфа-композите панели; кегль в su и px; контраст кромки к телу. Дополнительно измеряется контраст под каждой текстовой строкой до нанесения текста. Радиусы 4/6/8, тело #061623 с непрозрачностью 0,92, кромка #F9EBDB с непрозрачностью 0,45. Шрифты — заданные Roboto из Engine/Content/Slate/Fonts вне папки проекта unreal/.

Минимальный кегль нового HUD: {v['minimum_text_su']} su; при 720p 100% — {v['minimum_720p_text_nominal_px']} px (растеризуется с округлением вверх). Значки минимум {v['minimum_icon_su']} su. Текст сканов и уже имеющиеся надписи на фоновых кадрах не выдаются за текст нового HUD.

Пересечения постоянных блоков обнаружены в **{failed} из 24** макетов. Их значения не обнулены. Все входы проверяются против сохранённого до рендера [source-hashes-before.json](source-hashes-before.json), включая весь hud-icons-v3/**; итоговая неизменность — в verification.json. Полный список выходов и SHA-256 — [manifest.json](manifest.json), каждый текст и число — [facts.json](facts.json).

## Рекомендуемый вариант и предлагаемые изменения 04

Рекомендую **FIELD-aware вариант на proposal-overlay**, после отдельного согласования спецификации. Основные 24 макета сохраняют буквальную раскладку 04: их нельзя назвать вариантом с нулевыми перекрытиями.

1. HAND: верх видимой части поставить `FIELD.bottom + 30 su`, подпись — `FIELD.bottom + 8 su`; убрать нижний clamp 120 su при нехватке места. Это сохраняет клетки, но уменьшает видимую высоту карт; полнота скана в неподвижной руке тогда не достигается. Альтернатива требует изменить камеру/размер FIELD — здесь не выполнялась. Предлагается поправить формулу 04 §2.6, не менять макет скрытно.
2. OPP-HAND в S: полоса счётчика 240×40 под компактным PANEL-OPP вместо наследуемых 300×87; рубашки открывать по запросу. Схема предложения показывает место и размер, но не утверждает, что это уже принятый UX.
3. STATUS в S: ширина ограничена свободным коридором между TOP и PANEL-OPP (`min(600, W−528)`), допустимое «≤600» из 04. Длинная строка получает многоточие с сохранением кегля; полный текст указан в facts.json.
4. Адаптивные правые и нижние якоря вычисляются по точному дробному холсту (1137,78×640 и 1706,67×960), подписи схем округлены. 1138/1707 — отображаемое округление, не другой DPI.
5. LOG в бою скрыт; в S представлен кнопкой «Журнал» в TOP. CENTER и карты боя присутствуют только в combat-defense; BANNER — мгновение начала собственного хода. Это правила видимости из 04, а не пропущенные блоки.
6. Имя доски включено в имя файла, чтобы два набора состояний не перезаписывали друг друга. В S при 1138×640 две строки защиты из §2.7 пересекают PANEL-LOC; предлагаю в режиме защиты заменить ACTIONS двумя кнопками защиты справа снизу. Эта правка пока не нарисована на proposal-overlay и остаётся открытой; все межпанельные пересечения записаны отдельно.

## Ограничения и несовместимые исходные требования

- Оба SHA bench-кадров совпадают с заданием, но визуально Marmoreal содержит **объёмные дворец и деревья**, а не нарисованный задник. В обоих фонах уже есть подписи фигур и HP. Изменять фон или подменять его кадром I запрещено; оценка читаемости на требуемом ночном painted-Marmoreal этим входом не подтверждена.
- Шесть фигур вручную обведены консервативными полигонами с учётом подставок, координаты записаны в [masks.json](masks.json). Все 31/38 клеток отображены из topology: исходные границы центров плюс радиус нормализованы в измеренный FIELD. Это проверка заданной аппроксимации, не точная проекция камеры. FIELD имеет исходную погрешность ±15 px; это отдельно ограничивает доказательство.
- Формула видимой руки и отступ −16 конфликтуют с нулевым пересечением: подпись и верх карт заходят на нижние клетки. Целый скан вписан в рамку без нанесения текста поверх него, но часть рамки уходит за viewport, как требует 04 §2.6. Требование видеть весь скан одновременно не выполнено.
- В v3 отсутствует `action-end-turn`: на месте четвёртой кнопки буквально «уточнить»; новые значки запрещены.
- Запрошенные HP/руки взяты из нескольких моментов I; bench содержит другие позиции фигур и исходные HP. Это статическая композиция, не восстановленная синхронная партия. Для Сарпедона исходный бой — Merlin против Medusa, собственник HUD — King Arthur: его defense-window не засвидетельствован. Вместо выдуманной карты слот подписан «уточнить». Для Marmoreal выбранная Feint известна по раскрытому бою, атакующая карта в defense-window остаётся рубашкой.
- Уточнить: `Hero.nameRu (admin :5480)` — всех героев и помощников; имена показаны EN из скрапа. Уточнить: `Card.nameRu` King Arthur (кроме Feint/Regroup), `combatInfo.timeoutAt`, точный синхронный snapshot для каждой из трёх фаз. В макетах не придуманы секунды таймера или карта защиты Arthur.
- RU-названия Medusa и свойства каждой карты декодированы из SvelteKit devalue в facts.json; рука использует настоящие RU-сканы из reused-cardart.json. Новая Dash отмечена над сканом, в строке руки. Числа HP/колоды/руки не получены из предположительного игрового расчёта.
- Контраст кромки 0,45 рассчитан к телу; контраст внешней границы ко всему окружению и внутренние пары всех значков не сертифицированы. Нет общего утверждения о выполнении ≥3:1. Серая версия проверяет дополнительный канал формы; скрытые карты сохраняют рубашку и подпись, роли — текст и разные глифы.

## Воспроизведение

`python -B -X utf8 art/imagegen/hud-composition-v1-codex/_tools/build_mockups.py`

Первый capture уже выполнен; не перезаписывать baseline. Скрипт проверяет входы до и после, пишет только в две разрешённые папки, не вызывает git, UE, сеть или генерацию изображений. Для новой исходной ревизии нужен отдельный пакет с новым baseline. Зависимости: Python, Pillow, NumPy.

Изменённые хеши относительно таблицы задания: {json.dumps(v['expected_hash_mismatches'],ensure_ascii=False)}.
'''
    guarded(PACKAGE/'README.md').write_text(text,encoding='utf-8')

if __name__=='__main__':
    parser=argparse.ArgumentParser(); parser.add_argument('--capture',action='store_true'); args=parser.parse_args()
    capture() if args.capture else build()
