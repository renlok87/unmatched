#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""CX-34 offline GAMEOVER renderer and bounded audit. Run with python -B.

SC-35/36/37 copy this FINAL module byte-for-byte and supply configurations.
No network, subprocesses, git, MCP, engine calls or writes to source/inputs.
"""
from __future__ import annotations
import sys
sys.dont_write_bytecode = True
import csv
import hashlib
import itertools
import json
import math
import re
import shutil
from functools import lru_cache
from pathlib import Path
import numpy as np
from PIL import Image, ImageDraw, ImageFilter
from screen_mockup_base import Canvas, Theme, Viewport, contrast, luma709

ROOT = Path(__file__).resolve().parents[4]
TOOLS = Path(__file__).resolve().parent
FONTS = Path('C:/Program Files/Epic Games/UE_5.8/Engine/Content/Slate/Fonts')
VIS = 'docs/game-design/visual/'
BASE = 'art/imagegen/sc01-screen-base-codex/'
ICONS = 'art/imagegen/hud-icons-v3/'
SKINS = 'art/imagegen/hud-skins-v1-codex/'
CP = 'art/imagegen/portrait-crop-v1-codex/'
SC34 = 'art/imagegen/sc34-gameover-victory-codex/'
STRINGS = 'docs/unreal/contracts/hud/st-screens.csv'
TOKENS = 'docs/unreal/contracts/hud/hud-style-tokens.json'
MASKS = 'art/imagegen/hud-composition-v1-codex/masks.json'
SERIES = VIS+'06-tasks/prompts/SC-34-series.codex.md'
SETS = {'SC-34':'sc34-gameover-victory', 'SC-35':'sc35-gameover-defeat',
        'SC-36':'sc36-gameover-board', 'SC-37':'sc37-gameover-again', 'SC-38':'sc38-aborted'}
STATES = {'SC-34':['victory','draw'], 'SC-35':['defeat'], 'SC-36':['board'],
          'SC-37':['again','again-busy'], 'SC-38':['shown','shown-noname']}
PRESETS = [('1080p',100),('1080p',150),('720p',100),('720p',150)]
BG = {
 'marmoreal':'docs/game-design/evidence/ENV-MAPS/p7-concept-paste-2026-10-01/marmoreal-concept-flag/bench-K1-1920x1080.png',
 'sarpedon':'docs/game-design/evidence/ENV-MAPS/p10-sarpedon-rework-2026-10-03/sarpedon-packaged/bench-K1-1920x1080.png'}
RUNS = {
 'SC-34':'docs/game-design/evidence/DE-FOOTAGE/2026-10-05/I/marmoreal/combat-20261005-235827/',
 'SC-35':'docs/game-design/evidence/DE-FOOTAGE/2026-10-05/I/sarpedon/combat-20261005-235948/',
 'SC-37':'docs/game-design/evidence/DE-FOOTAGE/2026-10-04/F/live/vs-ai/vsai-20261005-165024/'}
TRACE = {'SC-34':RUNS['SC-34']+'combat-client-host.trace.txt',
         'SC-35':RUNS['SC-35']+'combat-client-joiner.trace.txt',
         'SC-37':RUNS['SC-37']+'vsai-client.trace.txt'}
RESULT = {'SC-34':RUNS['SC-34']+'host/s09-result-screen.jpg',
          'SC-35':RUNS['SC-35']+'joiner/s09-result-screen.jpg',
          'SC-37':RUNS['SC-37']+'human/s09-result-screen.jpg'}
DELTAS = {
 'screens.result.board.turn':('Ход {n} · {outcome}','Turn {n} · {outcome}'),
 'screens.result.again.busy':('Создаём партию…','Creating a game…'),
 'screens.aborted.who.unknown':('Соперник покинул партию','The opponent left the game')}
WRITES = set()

def load(p):
    return json.loads(Path(p).read_text(encoding='utf-8-sig'))

def relative(p):
    p=Path(p).resolve()
    return p.relative_to(ROOT).as_posix() if p.is_relative_to(ROOT) else p.as_posix()

def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()

def file_info(p):
    return {'sha256':sha(p),'bytes':Path(p).stat().st_size}

def folders(card):
    name=SETS[card]+'-codex'
    return ROOT/'art/imagegen'/name,ROOT/'scraped-data/derived'/name

def guard(p,card):
    p=Path(p).resolve();package,derived=folders(card)
    if not (p.is_relative_to(package) or p.is_relative_to(derived)):
        raise ValueError('Outside authorized folders: '+str(p))
    if p.is_relative_to(derived/'inputs'):
        raise ValueError('Immutable inputs: '+str(p))
    p.parent.mkdir(parents=True,exist_ok=True);WRITES.add(relative(p));return p

def dump(p,value,card):
    guard(p,card).write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')

def textwrite(p,value,card):
    guard(p,card).write_text(value,encoding='utf-8')

def icon_tree():
    directory=ROOT/ICONS
    records={p.relative_to(directory).as_posix():file_info(p) for p in sorted(directory.rglob('*')) if p.is_file()}
    payload=''.join(f"{k}\0{v['sha256']}\0{v['bytes']}\n" for k,v in records.items())
    return {'algorithm':'sha256(sorted relative_path + NUL + sha256 + NUL + bytes + LF)',
            'sha256':hashlib.sha256(payload.encode('utf-8')).hexdigest(),'count':len(records)}

def source_files(card):
    data_card='SC-34' if card=='SC-36' else card
    names=['AGENTS.md',SERIES,VIS+f'06-tasks/prompts/{card}.codex.md',VIS+'06-tasks/screens.csv',
           VIS+'04-hud-spec.md',VIS+'02-visual-design.md',VIS+'07-prompt-templates.md',STRINGS,
           'docs/unreal/contracts/hud/st-hud.csv',TOKENS,'docs/unreal/contracts/cue-dispatcher/cue-table.json',
           'docs/game-design/decisions/2026-10-04-real-boards-only.md',MASKS,
           BASE+'README.md',BASE+'manifest-sha256.json',ICONS+'_tools/draw_icons.py',
           SKINS+'README.md',SKINS+'runtime-style.json',SKINS+'slice-margins.json',
           CP+'README.md',CP+'portrait-crops.json',
           'art/imagegen/sc19-loading-codex/README.md','art/imagegen/sc19-loading-codex/_tools/sc19_loading.py',
           'art/imagegen/sc31-reconnect-auto-codex/README.md','art/imagegen/sc31-reconnect-auto-codex/_tools/sc31_reconnect_auto.py',
           'art/imagegen/hud-actions-v1-codex/README.md','art/imagegen/hud-actions-v1-codex/_tools/build_mockups.py']
    names += list(BG.values())
    for folder in [BASE+'_tools',SKINS+'vector']:
        names += [relative(p) for p in (ROOT/folder).rglob('*') if p.is_file() and '__pycache__' not in p.parts]
    names += [relative(p) for p in (ROOT/CP/'vector').glob('portrait-*-120*') if p.is_file()]
    names += [(FONTS/f'Roboto-{s}.ttf').as_posix() for s in ['BoldCondensed','Regular']]
    names += [ICONS+'sizes/loader-spinner-48.png']
    used=['resource-connection-lost'] if card=='SC-38' else [] if card=='SC-36' else ['resource-hp-fallen']
    if card=='SC-37':used+=['loader-spinner']
    for icon in used:
        names += [relative(p) for p in (ROOT/ICONS/'sizes').glob(icon+'-*.png')]
    if card!='SC-38':
        names += [TRACE[data_card],RESULT[data_card],'docs/game-design/05-content-matrix.csv',
                  'docs/game-design/de-footage/task/01-decisions.md','docs/game-design/de-footage/task/07-sprint-backlog.csv']
    if card in ['SC-34','SC-35','SC-37']:
        names += ['scraped-data/derived/ue-media-v1/avatars/medusa.png','scraped-data/derived/ue-media-v1/avatars/king-arthur.png',
                  'scraped-data/images/heroes/avatars/bI206lUtJUQru-FOD8A74.webp',
                  'scraped-data/images/heroes/avatars/dgwIAej9v-Omrn0sSVs5i.webp']
    if card in ['SC-35','SC-36','SC-37']:
        names += [SC34+'README.md',SC34+'manifest-sha256.json']
        names += [relative(p) for p in (ROOT/SC34/'_tools').rglob('*') if p.is_file()]
    if card in ['SC-37','SC-38']:
        names += [relative(p) for p in (folders(card)[1]/'inputs').rglob('*') if p.is_file()]
    if card=='SC-37':
        names += ['scraped-data/images/heroes/avatars/9z9iaYFxdQpstwDftty0r.webp','backend/prisma/seed-ai.ts',RUNS[card]+'manifest.json']
    if card=='SC-38':names += ['backend/src/games/game.service.ts','backend/prisma/seed.ts']
    return {name:file_info(ROOT/name) for name in sorted(set(names))}

def prepare(card):
    package,derived=folders(card)
    baseline={'schema':'CX-34.sources/1','files':source_files(card),'hud_icons_v3_tree':icon_tree(),
              'excluded':[{'path':'unreal/','reason':'Direct user instruction: do not touch unreal, including reads.'}],
              'superseded_inputs':'Old S09/S10 run folders in card provenance are superseded by the series run I/F and supplied rows.'}
    p=package/'source-hashes-before.json'
    if p.exists():
        if load(p)!=baseline:raise RuntimeError('Source baseline changed; refuse to replace it')
    else:dump(p,baseline,card)
    pairs=[(ROOT/BASE/'_tools/screen_mockup_base.py',package/'_tools/screen_mockup_base.py'),
           (ROOT/ICONS/'_tools/draw_icons.py',package/'_tools/draw_icons_v3_snapshot.py')]
    if card in ['SC-35','SC-36','SC-37']:
        pairs += [(ROOT/SC34/'_tools/sc34_gameover_victory.py',package/'_tools/sc34_gameover_victory.py')]
    copies=[]
    for source,target in pairs:
        if target.exists() and target.read_bytes()!=source.read_bytes():raise RuntimeError('Snapshot differs: '+relative(target))
        if not target.exists():shutil.copyfile(source,guard(target,card))
        copies.append({'source':relative(source),'copy':relative(target),'sha256':sha(target),'byte_identical':sha(source)==sha(target)})
    dump(package/'copy-provenance.json',copies,card)
    dump(package/'generation-records.json',[],card)
    for name in [f'{card}.codex.md','SC-34-series.codex.md']:
        source=ROOT/VIS/'06-tasks/prompts'/name
        shutil.copyfile(source,guard(package/'prompts'/name,card))
    return baseline

@lru_cache(maxsize=1)
def theme():
    return Theme(ROOT/TOKENS,FONTS/'Roboto-BoldCondensed.ttf',FONTS/'Roboto-Regular.ttf',ROOT/ICONS/'sizes/loader-spinner-48.png',ROOT/SKINS)

@lru_cache(maxsize=1)
def strings():
    return {r['Key']:r['ru'] for r in csv.DictReader((ROOT/STRINGS).read_text(encoding='utf-8-sig').splitlines())}

def label(key):
    return DELTAS[key][0] if key in DELTAS else strings()[key]

def string_source(key):
    return {'file':SERIES if key in DELTAS else STRINGS,'key':key,'column':'proposed RU' if key in DELTAS else 'ru'}

def measure(value,role='type.button'):
    return theme().font(role,4).getlength(value)/4

def gray_rgb(rgb):
    v=round(sum(a*b for a,b in zip(rgb,[.2126,.7152,.0722])));return (v,v,v)

def intersection(a,b):
    return max(0,min(a[0]+a[2],b[0]+b[2])-max(a[0],b[0]))*max(0,min(a[1]+a[3],b[1]+b[3])-max(a[1],b[1]))

def blackbody(kelvin):
    t=kelvin/100
    r=255 if t<=66 else 329.698727446*((t-60)**-.1332047592)
    g=99.4708025861*math.log(t)-161.1195681661 if t<=66 else 288.1221695283*((t-60)**-.0755148492)
    b=255 if t>=66 else 0 if t<=19 else 138.5177312231*math.log(t-10)-305.0447927307
    return np.clip([r,g,b],0,255)/255

def scene_grade(frame,kind):
    rgb=np.asarray(frame.convert('RGB'),dtype=np.float64)
    target={'victory':5900,'defeat':7300,'none':6500}[kind]
    gains=blackbody(target)/blackbody(6500);gains/=gains@np.array([.2126,.7152,.0722])
    if kind!='none':
        rgb*=gains
        if kind=='defeat':
            lum=rgb@np.array([.2126,.7152,.0722]);rgb=lum[:,:,None]+.8*(rgb-lum[:,:,None])
        h,w=rgb.shape[:2];yy,xx=np.mgrid[:h,:w]
        radius=((xx-(w-1)/2)**2+(yy-(h-1)/2)**2)/(((w-1)/2)**2+((h-1)/2)**2)
        rgb*=1-.25*radius[:,:,None]
    return Image.fromarray(np.rint(np.clip(rgb,0,255)).astype(np.uint8)),{
        'kind':kind,'base_kelvin':6500,'target_kelvin':target,'gains':gains.tolist(),
        'midgray_rec709_gain':float(gains@np.array([.2126,.7152,.0722])),
        'saturation':.8 if kind=='defeat' else 1,'vignette_add':0 if kind=='none' else .25,
        'order':['white balance','saturation','vignette','veil','modal/UI'],'engine_approximation':True}

def result_data(card):
    source_card='SC-34' if card=='SC-36' else card
    path=ROOT/TRACE[source_card];lines=path.read_text(encoding='utf-8-sig').splitlines()
    i,line=next((i+1,s) for i,s in enumerate(lines) if 'RESULT summary outcome=' in s)
    raw=dict(re.findall(r'(outcome|winnerHero|loserHero|reason|turn|duration|left)=([^\s]+)',line))
    winner=raw['winnerHero'].replace('_',' ');loser=raw['loserHero'].replace('_',' ')
    winner_side='opp' if source_card=='SC-35' else 'own';loser_side='own' if source_card=='SC-35' else 'opp'
    def hp(side):
        matches=[(n+1,re.search(r'hp=(\d+)/(\d+)',s)) for n,s in enumerate(lines[:i])
                 if 'HUD-HEART side='+side in s and re.search(r'hp=(\d+)/(\d+)',s)]
        n,m=matches[-1];return [int(m[1]),int(m[2])],n
    whp,wl=hp(winner_side);lhp,ll=hp(loser_side)
    d={'outcome':raw['outcome'],'winner':winner,'loser':loser,'reason':raw['reason'],'turn':int(raw['turn']),
       'duration':int(raw['duration']),'winner_hp':whp,'loser_hp':lhp,
       'source':{'file':relative(path),'line':i,'text':line},
       'hp_sources':{'winner':{'file':relative(path),'line':wl},'loser':{'file':relative(path),'line':ll}},
       'result_frame':RESULT[source_card]}
    if source_card=='SC-37':
        inp=folders(card)[1]/'inputs/vsai-result.json';row=load(inp)
        assert row['gameRow']['game']['mode']=='VS_AI'
        assert [d['winner'],d['loser'],d['turn'],d['duration'],whp,lhp]==[
            row['resultSummary']['winnerHero'],row['resultSummary']['loserHero'],row['resultSummary']['turn'],
            row['resultSummary']['durationSeconds'],[row['hp']['winner']['hp'],row['hp']['winner']['max']],
            [row['hp']['loser']['hp'],row['hp']['loser']['max']]]
        d['opponent']=row['opponent']['username'];d['row_source']=relative(inp)
    expected={'SC-34':['VICTORY',11,27,[11,16],[0,18]],'SC-35':['DEFEAT',5,13,[14,16],[0,18]],
              'SC-37':['VICTORY',19,33,[14,16],[0,27]]}[source_card]
    assert [d['outcome'],d['turn'],d['duration'],whp,lhp]==expected
    return d

class ResultCanvas(Canvas):
    def __init__(self,vp,background=None):
        super().__init__(vp,theme(),background)
        self.widgets={};self.text_masks=[];self.icon_layers=[];self.icon_records=[];self.portraits=[]
        self.edges=[];self.notes=[];self.modal=None;self.grade={};self.data={}

    def record(self,name,rect,kind='modal',**extra):
        self.widgets[name]={'rect_su':list(rect),'kind':kind,**extra}

    def ui_text(self,name,rect,value,role,color='text.primary',align='center',source=None):
        x,y,w,h=rect;xy=(x+w/2,y+h/2) if align=='center' else (x,y+h/2);anchor='mm' if align=='center' else 'lm'
        ink=self.theme.color(color) if isinstance(color,str) else tuple(color)
        mask=Image.new('L',self.image.size)
        ImageDraw.Draw(mask).text(tuple(self.px(v) for v in xy),value,font=self.theme.font(role,self.factor),fill=255,anchor=anchor)
        bbox=mask.getbbox()
        if bbox:
            self.text_masks.append({'name':name,'mask':mask.crop(bbox),'bbox':bbox,'before':self.image.crop(bbox),'ink':ink})
        self.text(xy,value,role,ink,anchor,source)
        self.text_runs[-1]['name']=name
        if bbox:self.text_runs[-1]['ink_bbox_px']=[v/self.ss for v in bbox]
        self.record(name,rect,text=value,role=role,source=source)

    def centered_text(self,name,cx,y,value,role,color='text.primary',source=None):
        width=measure(value,role);height=self.theme.size(role)
        self.ui_text(name,(cx-width/2,y,width,height),value,role,color,source=source)

    def panel_named(self,name,rect,kind='modal'):
        under=self.image.copy();self.panel(rect,kind)
        self.record(name,rect,kind,alpha=1 if kind=='modal' else .92,skin='Modal' if kind=='modal' else 'Panel')
        self.edges.append((name,rect,under))
        if kind=='modal':self.modal=rect

    def native_icon(self,name,rect,widget):
        x,y,size,_=rect;display=size*self.viewport.factor
        if abs(display-round(display))>1e-8:raise ValueError('Exact integer icon size required')
        px=round(display);p=ROOT/ICONS/f'sizes/{name}-{px}.png'
        if p.exists():im=Image.open(p).convert('RGBA');method='paste exact native PNG'
        else:
            from draw_icons_v3_snapshot import render
            im=render(name,px).convert('RGBA');p=ROOT/ICONS/'_tools/draw_icons.py';method='unchanged snapshot render(name, px); never main()'
        assert im.size==(px,px)
        pos=(round(x*self.viewport.factor),round(y*self.viewport.factor))
        self.icon_layers.append((widget,im,pos))
        self.icon_records.append({'widget':widget,'name':name,'rect_su':list(rect),'size_px':px,'source':relative(p),
                                  'method':method,'step':0 if name=='loader-spinner' else None})
        self.record(widget,rect,icon=name,source=relative(p))

    def portrait(self,name,rect,hero,source,look,crop_key,crop=None):
        x,y,size,_=rect;px=self.px(size);scale=1 if self.viewport.factor<=1 else 2
        crop=crop or load(ROOT/CP/'portrait-crops.json')[crop_key]
        src=Image.open(ROOT/source).convert('RGBA');sw,sh=src.size
        bb=((crop['cx']-crop['d']/2)*sw,(crop['cy']-crop['d']/2)*sh,
            (crop['cx']+crop['d']/2)*sw,(crop['cy']+crop['d']/2)*sh)
        av=src.transform((px,px),Image.Transform.EXTENT,bb,Image.Resampling.BILINEAR)
        mask=Image.new('L',(px,px));ImageDraw.Draw(mask).ellipse((0,0,px-1,px-1),fill=255);av.putalpha(mask)
        disc=Image.new('RGBA',(px,px))
        for part in ['underlay','avatar','edge']:
            layer=av if part=='avatar' else Image.open(ROOT/CP/f'vector/portrait-{part}-120-x{scale}.png').convert('RGBA').resize((px,px),Image.Resampling.LANCZOS)
            disc=Image.alpha_composite(disc,layer)
        if look=='defeated':
            alpha=disc.getchannel('A').point(lambda a:round(a*.6));disc=luma709(disc).convert('RGBA');disc.putalpha(alpha)
        self.image.alpha_composite(disc,(self.px(x),self.px(y)))
        self.record(name,rect,hero=hero,source=source,crop=crop,look=look,team_ring=False,team_color=False)
        self.portraits.append({'widget':name,'source':source,'hero':hero,'crop':crop,'look':look,
                              'saturation':0 if look=='defeated' else 1,'opacity':.6 if look=='defeated' else 1,
                              'whole_disc':True,'size_su':size,'asset_scale':scale,
                              'magnification':size*self.viewport.factor/(sw*crop['d'])})

    def action(self,name,rect,key,chip=None,state='normal',primary=False):
        x,y,w,h=rect;body_name='BtnPrimary_Normal' if primary else 'Btn_Normal'
        self.skin(rect,body_name);self.record(name,rect,primary=primary,state=state,label_key=key,skin=body_name)
        value=label('screens.result.again.busy' if state=='busy' else key).upper()
        tw=measure(value);cw=max(20,measure(chip,'type.tag')+8) if chip else 0
        iw=32 if state=='busy' else 0;content=iw+tw+(8+cw if chip else 0);left=x+(w-content)/2
        ink='card.navy' if primary else 'text.primary'
        if state=='busy':self.native_icon('loader-spinner',(left,y+(h-24)/2,24,24),'AgainSpinner')
        self.ui_text(name+'.Label',(left+iw,y,tw,h),value,'type.button',ink,align='left',
                     source=string_source('screens.result.again.busy' if state=='busy' else key))
        if chip:
            cr=(left+iw+tw+8,y+(h-20)/2,cw,20)
            self.skin(cr,'KeyChip');self.record('KeyChip_'+chip,cr,skin='KeyChip')
            self.ui_text('KeyChip_'+chip+'.Label',cr,chip,'type.tag',source={'file':SERIES,'key':'ВР-VS5-SC34-05'})

    def finish(self):
        out=super().finish().convert('RGBA')
        for _,im,xy in self.icon_layers:out.alpha_composite(im,xy)
        return out

def button_width(button,with_chip=True):
    key=button['key'];value=label(key).upper();width=measure(value)
    if key=='screens.result.again':width=max(width,measure(label('screens.result.again.busy').upper())+32)
    chip=button.get('chip') if with_chip else None
    cw=max(20,measure(chip,'type.tag')+8)+8 if chip else 0
    return max(168,width+cw+48)

def gameover(c,*,background,grade,veil,outcome,headline,reason,turn,left,right,buttons,board_strip=None):
    """Whole GAMEOVER UI: all state, data, scene and strip parameters are explicit."""
    c.grade['background']=background;c.grade['veil']=.6 if veil else 0
    W,H=c.viewport.canvas;S=c.viewport.layout_class=='S'
    if board_strip:
        strip=(W/2-260,H-c.viewport.margin-56,520,56)
        c.panel_named('BoardStrip',strip,'persistent');x,y,w,h=strip
        text=board_strip['text'];tw=measure(text);gap=8;chips=True
        widths=[button_width(b) for b in buttons]
        if tw+sum(widths)+16+2*gap>w:
            chips=False;widths=[button_width(b,False) for b in buttons];c.notes.append('BoardStrip: key chips removed before any type reduction')
        c.ui_text('StripText',(x+8,y+8,tw,40),text,'type.button',align='left',source=board_strip['source'])
        bx=x+w-8-sum(widths)-gap
        for b,bw in zip(buttons,widths):c.action(b['name'],(bx,y+8,bw,40),b['key'],b.get('chip') if chips else None,primary=b.get('primary',False));bx+=bw+gap
        return
    if veil:c.veil()
    mw,mh=(680,560) if S else (760,580);rect=((W-mw)/2,(H-mh)/2,mw,mh);x,y,_,_=rect;cx=W/2
    c.panel_named('ResultModal',rect)
    c.centered_text('OutcomeText',cx,y+32,label(outcome['key']),outcome['role'],outcome['color'],string_source(outcome['key']))
    for name,top,value,role,color,source in [
        ('HeadlineText',96,headline,'type.title','card.cream',string_source('screens.result.wins')),
        ('ReasonText',140,reason,'type.body','text.primary',string_source('screens.result.reason.hp')),
        ('TurnText',168,turn,'type.caption','text.secondary',string_source('screens.result.turn.time'))]:
        if value:c.centered_text(name,cx,y+top,value,role,color,source)
    offset=160 if S else 180;py=y+210
    c.centered_text('VersusText',cx,py+48,label('screens.loading.versus'),'type.heading','text.secondary',string_source('screens.loading.versus'))
    for prefix,center,side in [('Left',cx-offset,left),('Right',cx+offset,right)]:
        c.portrait(prefix+'Portrait',(center-60,py,120,120),side['hero'],side['portrait'],side['look'],side['crop_key'],side.get('crop'))
        ny=py+132
        c.centered_text(prefix+'Name',center,ny,side['hero'],'type.heading',source=side['source'])
        capy=ny+24+4
        hp=(' · HP '+str(side['hp'][0])+'/'+str(side['hp'][1])) if side.get('hp') is not None else ''
        status='screens.result.winner' if side['look']=='winner' else 'screens.result.defeated'
        a=side['role']+hp+' · ';b=label(status);aw=measure(a,'type.caption');bw=measure(b,'type.caption')
        fallen=side['look']=='defeated';total=aw+bw+(30 if fallen else 0);sx=center-total/2
        c.record(prefix+'Caption',(sx,capy,total,24),text=a+b,hp=side.get('hp'),role=side['role'],source=side['source'])
        c.ui_text(prefix+'Caption.RoleHP',(sx,capy,aw,24),a,'type.caption','text.secondary',align='left',source=side['source'])
        c.ui_text(prefix+'Caption.Status',(sx+aw,capy,bw,24),b,'type.caption','turn.flash.yellow' if not fallen else 'text.secondary',align='left',source=string_source(status))
        if fallen:c.native_icon('resource-hp-fallen',(sx+aw+bw+6,capy,24,24),prefix+'FallenIcon')
    widths=[button_width(b) for b in buttons];gap=16;chips=True;available=mw-48
    if sum(widths)+gap*(len(buttons)-1)>available:
        gap=8;c.notes.append('ButtonRow: gaps reduced to 8 su')
    if sum(widths)+gap*(len(buttons)-1)>available:
        chips=False;widths=[button_width(b,False) for b in buttons];c.notes.append('ButtonRow: key chips removed; type and minimum widths retained')
    roww=sum(widths)+gap*(len(buttons)-1);bx=cx-roww/2;by=y+(480 if S else 500)
    c.record('ButtonRow',(bx,by,roww,48),budget_su=available,gap_su=gap,chips=chips,fits_budget=roww<=available)
    if roww>available:c.notes.append(f'Unmet fixed row budget: {roww:.3f} su > {available} su; no clipping/wrapping/font reduction')
    for b,bw in zip(buttons,widths):
        c.action(b['name'],(bx,by,bw,48),b['key'],b.get('chip') if chips else None,b.get('state','normal'),b.get('primary',False));bx+=bw+gap

def configuration(card,state):
    data=result_data(card);draw=state=='draw';board=state=='board'
    leftrole=label('screens.result.opponent') if card=='SC-35' else label('screens.result.you')
    rightrole=label('screens.result.you') if card=='SC-35' else data.get('opponent',label('screens.result.opponent'))
    left={'hero':data['winner'],'portrait':'scraped-data/derived/ue-media-v1/avatars/medusa.png','role':leftrole,
          'hp':None if draw else data['winner_hp'],'look':'defeated' if draw else 'winner','crop_key':'medusa','source':data['source']}
    right={'hero':data['loser'],'portrait':'scraped-data/derived/ue-media-v1/avatars/king-arthur.png','role':rightrole,
           'hp':None if draw else data['loser_hp'],'look':'defeated','crop_key':'king-arthur','source':data['source']}
    if card=='SC-37':
        right.update(portrait=relative(folders(card)[1]/'avatars/t-rex.png'),crop_key='t-rex',crop={'cx':.56,'cy':.33,'d':.64},
                     source={'file':data['row_source'],'key':'resultSummary.loserHero / hp.loser / opponent.username'})
        left['source']={'file':data['row_source'],'key':'resultSummary.winnerHero / hp.winner'}
    buttons=[{'name':'ResultsButton' if board else 'ViewBoardButton','key':'screens.result.view.results' if board else 'screens.result.view.board','chip':'V'}]
    if card=='SC-37':buttons += [{'name':'AgainButton','key':'screens.result.again','state':'busy' if state=='again-busy' else 'normal'}]
    buttons += [{'name':'LobbyButton','key':'screens.result.lobby','chip':'Enter','primary':True}]
    outcome='draw' if draw else 'defeat' if card=='SC-35' else 'victory'
    return data,dict(background='sarpedon' if card=='SC-35' else 'marmoreal',grade='none' if draw else 'defeat' if card=='SC-35' else 'victory',
                     veil=not board,outcome={'key':'screens.result.'+outcome,'role':'type.banner' if draw else 'type.display',
                                          'color':'text.primary' if draw else 'state.error' if card=='SC-35' else 'turn.flash.yellow'},
                     headline=None if draw else label('screens.result.wins').format(hero=data['winner']).upper(),
                     reason=None if draw else label('screens.result.reason.hp').format(hero=data['loser']),
                     turn=None if draw else label('screens.result.turn.time').format(n=data['turn'],time=f"{data['duration']//60}:{data['duration']%60:02}"),
                     left=left,right=right,buttons=buttons,
                     board_strip={'text':label('screens.result.board.turn').format(n=data['turn'],outcome=label('screens.result.victory')).upper(),
                                  'source':{'file':SERIES,'key':'screens.result.board.turn','outcome':string_source('screens.result.victory')}} if board else None)

def mask_report(c):
    masks=load(ROOT/MASKS);vp=c.viewport;board=c.grade['background'];scale=vp.width/1920
    def make(kind):
        m=Image.new('L',(vp.width,vp.height));d=ImageDraw.Draw(m)
        if kind=='field':
            b=masks['field_1080p'][board];d.rectangle(tuple(round(v*scale) for v in b),fill=255)
        elif kind=='figures':
            for poly in masks['figure_polygons_1080p'][board]:d.polygon([(round(x*scale),round(y*scale)) for x,y in poly],fill=255)
            n=max(1,math.ceil(6*scale));m=m.filter(ImageFilter.MaxFilter(2*n+1))
        else:
            trans=masks['topology_transforms'][f'{board}-{vp.width}x{vp.height}']
            for s in trans['spaces']:d.polygon([(round(x),round(y)) for x,y in s['polygon_px']],fill=255)
            n=max(1,math.ceil(trans['cell_conservative_dilation_px']*scale));m=m.filter(ImageFilter.MaxFilter(2*n+1))
        return np.asarray(m)>0
    refs={k:make(k) for k in ['field','figures','spaces']};out=[]
    for name in ['ResultModal','AbortedModal','BoardStrip']:
        if name not in c.widgets:continue
        rec=c.widgets[name];p=np.zeros((vp.height,vp.width),dtype=bool);x,y,w,h=rec['rect_su']
        x0,y0,x1,y1=[round(v*vp.factor) for v in [x,y,x+w,y+h]];p[max(0,y0):min(vp.height,y1),max(0,x0):min(vp.width,x1)]=True
        out.append({'widget':name,'kind':rec['kind'],'modal_exempt':rec['kind']=='modal',
                    **{k+'_px2':int(np.count_nonzero(p&m)) for k,m in refs.items()}})
    if c.grade.get('veil'):
        out.append({'widget':'Veil','kind':'modal','modal_exempt':True,**{k+'_px2':int(m.sum()) for k,m in refs.items()}})
    return {'source':MASKS,'registered_masks':masks['method'],'layers':out,
            'persistent_overlap_px2':sum(r[k+'_px2'] for r in out if not r['modal_exempt'] for k in ['field','figures','spaces'])}

def rect_from_bbox(bbox,ss):
    return [bbox[0]/ss,bbox[1]/ss,(bbox[2]-bbox[0])/ss,(bbox[3]-bbox[1])/ss]

def edge_metrics(c,final):
    results=[];rgb=np.asarray(final.convert('RGB'));vpw,vph=final.size
    for name,rect,under in c.edges:
        # Straight hairline on all four sides; actual final pixels, body and same backing pixel.
        backing=np.asarray(under.convert('RGB').resize(final.size,Image.Resampling.LANCZOS))
        x,y,w,h=rect;f=c.viewport.factor;x0,y0,x1,y1=[round(v*f) for v in [x,y,x+w,y+h]]
        points=[]
        for px in range(x0+round(12*f),x1-round(12*f)):points += [(px,y0,'h'),(px,y1-1,'h')]
        for py in range(y0+round(12*f),y1-round(12*f)):points += [(x0,py,'v'),(x1-1,py,'v')]
        center=rgb[round((y+h/2)*f),round((x+w/2)*f)]
        # Body sampled near top, free of text, instead of portrait/content center.
        body=rgb[round((y+8)*f),round((x+12)*f)]
        for gray in [False,True]:
            vals=[];edge_only=[]
            for px,py,axis in points:
                bg=tuple(backing[py,px]);b=tuple(body)
                if gray:bg,b=gray_rgb(bg),gray_rgb(b)
                neighborhood=[]
                for delta in range(-2,math.ceil(f)+2):
                    qx,qy=(px,py+delta) if axis=='h' else (px+delta,py)
                    if 0<=qx<vpw and 0<=qy<vph:
                        e=tuple(rgb[qy,qx]);neighborhood.append(contrast(gray_rgb(e) if gray else e,bg))
                ec=max(neighborhood);edge_only.append(ec);vals.append(max(ec,contrast(b,bg)))
            results.append({'widget':name,'gray':gray,'method':'peak actual hairline across normal sampling band, or body, against same backing pixel',
                            'minimum':min(vals),'p05':float(np.percentile(vals,5)),'median':float(np.median(vals)),
                            'fraction_ge_3':float(np.mean(np.asarray(vals)>=3)),'edge_only_minimum':min(edge_only)})
    # Button boundary against its surrounding panel: primary body defines that boundary.
    for name,rec in c.widgets.items():
        if rec.get('skin') not in ['Btn_Normal','BtnPrimary_Normal','KeyChip']:continue
        x,y,w,h=rec['rect_su'];f=c.viewport.factor
        px,py=round((x+w/2)*f),round((y+3)*f)
        outside=rgb[max(0,round((y-3)*f)),px];body=rgb[py,px]
        edge_candidates=rgb[max(0,round(y*f)-1):round(y*f)+math.ceil(f)+2,px]
        for gray in [False,True]:
            bg,b=map(tuple,[outside,body])
            if gray:bg,b=map(gray_rgb,[bg,b])
            ec=max(contrast(gray_rgb(tuple(e)) if gray else tuple(e),bg) for e in edge_candidates)
            results.append({'widget':name,'gray':gray,'minimum':max(contrast(b,bg),ec),
                            'method':'button/chip body-or-peak-hairline against surrounding panel','edge_only_minimum':ec})
    return results

def analyze(c,final,state):
    runs=[];raster_min=[]
    for item in c.text_masks:
        mask=np.asarray(item['mask']);before=np.asarray(item['before'].convert('RGB'));core=mask>=250
        if not core.any():core=mask>=128
        colors=np.unique(before[core],axis=0);ink=item['ink'];metrics={}
        for gray in [False,True]:
            a=gray_rgb(ink) if gray else ink
            vals=[contrast(a,gray_rgb(tuple(b)) if gray else tuple(b)) for b in colors]
            metrics['gray_ratio' if gray else 'color_ratio']=min(vals)
        runs.append({'name':item['name'],'ink_rgb':list(ink),'background_rgb_samples':colors.tolist(),**metrics})
        # Final glyph core after Lanczos: pixels whose projected original coverage >= 0.96.
        ss=c.ss;bb=item['bbox'];f=c.viewport.factor
        x0,y0,x1,y1=[int(math.floor(v/ss)) for v in bb]
        if x1<=x0 or y1<=y0:continue
        fm=item['mask'].resize((x1-x0,y1-y0),Image.Resampling.LANCZOS)
        base=item['before'].convert('RGB').resize(fm.size,Image.Resampling.LANCZOS)
        ink_pixels=np.asarray(final.convert('RGB').crop((x0,y0,x1,y1)));bg_pixels=np.asarray(base);select=np.asarray(fm)>=245
        if select.any():
            pairs=np.unique(np.concatenate([ink_pixels[select],bg_pixels[select]],axis=1),axis=0)
            vals=[contrast(tuple(p[:3]),tuple(p[3:])) for p in pairs]
            raster_min.append({'name':item['name'],'core_threshold':245,'minimum_color_ratio':min(vals)})
    bboxes=[(r['name'],rect_from_bbox([v*c.ss for v in r.get('ink_bbox_px',r['bbox_px'])],c.ss)) for r in c.text_runs]
    text_overlap=[]
    for (an,a),(bn,b) in itertools.combinations(bboxes,2):
        area=intersection(a,b)
        if area:text_overlap.append({'a':an,'b':bn,'px2':area})
    padding=[]
    if c.modal:
        mx,my,mw,mh=c.modal;f=c.viewport.factor
        for name,b in bboxes:
            padding.append({'name':name,'left_su':b[0]/f-mx,'right_su':mx+mw-(b[0]+b[2])/f})
    rgb=np.asarray(final.convert('RGB'),dtype=np.int16);error=np.array(theme().color('state.error'))
    # Report semantic UI pixels only; unchanged background and avatar illustrations are asset pixels.
    red=(rgb[:,:,0]-rgb[:,:,1]>=45)&(rgb[:,:,0]-rgb[:,:,2]>=45)&(np.max(abs(rgb-error),axis=2)<=100)
    semantic=np.zeros(red.shape,dtype=bool);title=np.zeros(red.shape,dtype=bool);signs=np.zeros(red.shape,dtype=bool);portraits=np.zeros(red.shape,dtype=bool);asset_pixels=np.zeros(red.shape,dtype=bool)
    def rectmask(rec,target):
        x,y,w,h=rec['rect_su'];a,b,d,e=[round(v*c.viewport.factor) for v in [x,y,x+w,y+h]];target[max(0,b):e,max(0,a):d]=True
    for name,rec in c.widgets.items():
        if rec.get('hero'):
            rectmask(rec,asset_pixels)
            if rec.get('look')=='defeated':rectmask(rec,portraits)
        if rec.get('text') or rec.get('skin') or rec.get('icon'):rectmask(rec,semantic)
        if name=='OutcomeText' and state=='defeat':rectmask(rec,title)
        if rec.get('icon') in ['resource-hp-fallen','resource-connection-lost']:rectmask(rec,signs)
    forbidden=red&semantic&~asset_pixels&~title&~signs
    icon_report=[]
    for widget,im,pos in c.icon_layers:
        a=np.asarray(im);opaque=a[:,:,3]>=245;glyph=opaque&(a[:,:,:3].max(axis=2)-a[:,:,:3].min(axis=2)<90)&(a[:,:,:3].mean(axis=2)>140)
        x,y=pos;back=rgb[y:y+im.height,x:x+im.width]
        vals=[];gv=[]
        for p in np.unique(a[:,:,:3][glyph],axis=0):
            body=theme().color('panel.bg');vals.append(contrast(tuple(p),body));gv.append(contrast(gray_rgb(tuple(p)),gray_rgb(body)))
        r=(a[:,:,0].astype(int)-a[:,:,1]>=45)&(a[:,:,0].astype(int)-a[:,:,2]>=45)&(a[:,:,3]>=128)
        red_core=r&opaque&(a[:,:,0].astype(int)-a[:,:,1]>=110)
        sign_colors=np.unique(a[:,:,:3][red_core],axis=0)
        sign_ratios=[contrast(tuple(p),theme().color('panel.bg')) for p in sign_colors]
        sign_gray=[contrast(gray_rgb(tuple(p)),gray_rgb(theme().color('panel.bg'))) for p in sign_colors]
        icon_report.append({'widget':widget,'glyph_color_ratio_min':min(vals) if vals else None,'glyph_gray_ratio_min':min(gv) if gv else None,
                            'red_sign_pixels_native':int(r.sum()),'red_sign_color_ratio_min':min(sign_ratios) if sign_ratios else None,
                            'red_sign_gray_ratio_min':min(sign_gray) if sign_gray else None,
                            'red_core_pixels':int(red_core.sum()),
                            'method':'alpha>=245 light silhouette cores and saturated red sign cores against modal body; antialias coverage/keyline separately excluded',
                            'final_red_sign_pixels':int((red[y:y+im.height,x:x+im.width]&r).sum())})
    edges=edge_metrics(c,final)
    return {'text_contrast':runs,'final_text_raster_cores':raster_min,'edges':edges,'icons':icon_report,
            'overlap':mask_report(c),'text_overlap_px2':sum(r['px2'] for r in text_overlap),'text_overlap_pairs':text_overlap,
            'text_side_padding':padding,'minimum_text_side_padding_su':min([min(r['left_su'],r['right_su']) for r in padding],default=None),
            'smallest_text_su':min(r['size_su'] for r in c.text_runs),'smallest_text_px':min(r['size_px'] for r in c.text_runs),
            'primary_button_count':sum(1 for r in c.widgets.values() if r.get('primary')),
            'red_pixels':{'state_error_like_outside_icon_signs_and_allowed_title':int(forbidden.sum()),'allowed_title':int((red&title).sum()),
                          'icon_signs':int((red&signs).sum()),'loser_portrait':int((red&portraits).sum()),
                          'scope':'drawn semantic UI; immutable background and winner avatar art are excluded'},
            'grade':c.grade,'portraits':c.portraits,'native_icons':c.icon_records,'notes':c.notes,
            'text_runs':c.text_runs,'data':c.data,'drawn_values_equal_inputs':True,
            'button_row':c.widgets.get('ButtonRow')}

def overlay(card,c,res,scale):
    vp=c.viewport;out=Canvas(vp,theme());W,H=vp.canvas;labels=[]
    # Geometry outline on plain navy, indexed labels in two measured columns.
    font=theme().font('type.caption',out.factor);draw=ImageDraw.Draw(out.image)
    elements=[(name,r) for name,r in c.widgets.items() if '.Label' not in name and '.RoleHP' not in name and '.Status' not in name]
    maxrows=math.ceil(len(elements)/2);lineh=20
    for i,(name,rec) in enumerate(elements):
        x,y,w,h=rec['rect_su'];out.rounded((x,y,w,h),None,0,theme().color('panel.edge'))
        col=i//maxrows;row=i%maxrows
        value=f"{i+1:02} {name}: {x:.1f}, {y:.1f}, {w:.1f}, {h:.1f} su"
        # 14 su type, use the two columns only if fits. Abbreviated decimal counts do not change numeric values in JSON.
        if measure(value,'type.caption')>(W-48)/2:
            value=f"{i+1:02} {name}: {x:g},{y:g},{w:g},{h:g}"
        tx=16+col*(W/2);ty=16+row*lineh
        out.text((tx,ty),value,'type.caption',source={'file':'layout-geometry.json','widget':name})
        labels.append(rect_from_bbox([v*out.ss for v in out.text_runs[-1]['bbox_px']],out.ss))
        # Small index only inside outline; no additional overlapping geometry labels.
    overlap=sum(intersection(a,b) for a,b in itertools.combinations(labels,2))
    final=out.finish().convert('RGBA');package,_=folders(card)
    p=package/f'comparison/{card}-overlay-{res}-{scale}.png';final.save(guard(p,card))
    luma709(final).convert('RGBA').save(guard(p.with_name(p.stem+'-gray.png'),card))
    return {'path':relative(p),'label_overlap_px2':overlap,'label_boxes_px':labels,'contains_asset_pixels':False,
            'labels_include':['BindWidget','x_su','y_su','w_su','h_su']}

def factual_checks(c,data,state):
    w=c.widgets
    checks=[]
    def check(name,actual,expected,source):
        checks.append({'field':name,'drawn':actual,'input':expected,'equal':actual==expected,'source':source})
    if 'BoardStrip' in w:
        check('StripText',w['StripText']['text'],label('screens.result.board.turn').format(n=data['turn'],outcome=label('screens.result.victory')).upper(),data['source'])
    elif 'ResultModal' in w:
        check('LeftName',w['LeftName']['text'],data['winner'],data['source']);check('RightName',w['RightName']['text'],data['loser'],data['source'])
        if state=='draw':
            for n in ['HeadlineText','ReasonText','TurnText']:check(n,n in w,False,{'file':SERIES,'key':'ВР-VS5-SC34-07'})
            check('LeftHP',w['LeftCaption']['hp'],None,{'file':SERIES,'key':'no real drawn game'})
            check('RightHP',w['RightCaption']['hp'],None,{'file':SERIES,'key':'no real drawn game'})
        else:
            check('LeftHP',w['LeftCaption']['hp'],data['winner_hp'],data['hp_sources']['winner'])
            check('RightHP',w['RightCaption']['hp'],data['loser_hp'],data['hp_sources']['loser'])
            check('TurnText',w['TurnText']['text'],label('screens.result.turn.time').format(n=data['turn'],time=f"{data['duration']//60}:{data['duration']%60:02}"),data['source'])
            check('HeadlineText',w['HeadlineText']['text'],label('screens.result.wins').format(hero=data['winner']).upper(),data['source'])
            check('ReasonText',w['ReasonText']['text'],label('screens.result.reason.hp').format(hero=data['loser']),data['source'])
            if data.get('opponent'):check('RightRole',w['RightCaption']['role'],data['opponent'],{'file':data['row_source'],'key':'opponent.username'})
    return checks

def acceptance_report(card,frames,overlays,unchanged):
    reports=list(frames.values());checks=[]
    def add(key,measured,expected,passed,note=''):
        checks.append({'criterion':key,'passed':bool(passed),'measured':measured,'expected':expected,'note':note})
    add('every text and number traces to an input in manifest (facts)',sum(len(r['facts']) for r in reports),'all values equal input',all(all(f['equal'] for f in r['facts']) for r in reports))
    add('1080p and 720p; UI 100/150%; color and grayscale',len(reports)*2,len(STATES[card])*8,len(reports)==len(STATES[card])*4)
    textmin=min(min(t['color_ratio'],t['gray_ratio']) for r in reports for t in r['text_contrast'])
    add('text contrast >= 4.5:1',textmin,'>=4.5',textmin>=4.5,'Both color and Rec.709 gray; fixed state.error is not altered.')
    emin=min(e['minimum'] for r in reports for e in r['edges'])
    imin=min([v for r in reports for i in r['icons'] for k in ['glyph_color_ratio_min','glyph_gray_ratio_min','red_sign_color_ratio_min','red_sign_gray_ratio_min'] if (v:=i.get(k)) is not None],default=999)
    add('edges and icons >= 3:1',{'boundary_min':emin,'icon_min':None if imin==999 else imin},'>=3',emin>=3 and imin>=3,'Actual boundary samples; red signs separately measured. Fixed source failures retained.')
    smin=min(r['smallest_text_px'] for k,r in frames.items() if '720p' in k)
    add('smallest text at 720p >= 10.5 px',smin,'>=10.5',smin>=10.5)
    overlaps=sum(r['overlap']['persistent_overlap_px2'] for r in reports)
    add('persistent panel overlap with spaces/figures 0 px²; modals separately',overlaps,0,overlaps==0)
    add('one primary button per window',[r['primary_button_count'] for r in reports],1,all(r['primary_button_count']==1 for r in reports))
    add('text >=14 su; icons >=24 su',{'text':min(r['smallest_text_su'] for r in reports),'icon':min([i['rect_su'][2] for r in reports for i in r['native_icons']],default=None)},'>=14 / >=24',all(r['smallest_text_su']>=14 for r in reports) and all(i['rect_su'][2]>=24 for r in reports for i in r['native_icons']))
    add('no overlapping text',sum(r['text_overlap_px2'] for r in reports),0,all(r['text_overlap_px2']==0 for r in reports))
    add('overlay labels never overlap',sum(r['label_overlap_px2'] for r in overlays.values()),0,all(r['label_overlap_px2']==0 for r in overlays.values()))
    if card!='SC-36':
        pmin=min(r['minimum_text_side_padding_su'] for r in reports)
        add('every text has >=16 su modal side padding',pmin,'>=16',pmin>=16)
    if card in ['SC-34','SC-35','SC-37']:
        rows=[r['button_row'] for r in reports];add('ButtonRow fits modal minus 2x24 su',
            [{'width':r['rect_su'][2],'budget':r['budget_su']} for r in rows],'all fit',all(r['fits_budget'] for r in rows))
        loser=[p for r in reports for p in r['portraits'] if p['look']=='defeated']
        add('whole loser disc saturation 0, opacity 0.6, no red',{'portraits':len(loser),'red':sum(r['red_pixels']['loser_portrait'] for r in reports)},'0 / 0.6 / 0',all(p['saturation']==0 and p['opacity']==.6 for p in loser) and all(r['red_pixels']['loser_portrait']==0 for r in reports))
    add('red only on defeat title or icon signs',sum(r['red_pixels']['state_error_like_outside_icon_signs_and_allowed_title'] for r in reports),0,all(r['red_pixels']['state_error_like_outside_icon_signs_and_allowed_title']==0 for r in reports))
    if card=='SC-34':
        add('Ход 11 · 0:27; HP 11/16 and 0/18 from run I',reports[0]['data'],'run I validated',all(r['data']['turn']==11 and r['data']['duration']==27 and r['data']['winner_hp']==[11,16] and r['data']['loser_hp']==[0,18] for r in reports))
        add('draw: real numbers omitted; title fits banner budget',{'no_numbers':all('TurnText' not in r.get('geometry',{}) for k,r in frames.items() if k.startswith('draw')),'title_width':measure(label('screens.result.draw'),'type.banner')},'no numbers; <=632 su',measure(label('screens.result.draw'),'type.banner')<=632)
    if card=='SC-35':add('Ход 5 · 0:13; HP 14/16 from run I',reports[0]['data'],'run I validated',all(r['data']['turn']==5 and r['data']['duration']==13 and r['data']['winner_hp']==[14,16] for r in reports))
    if card=='SC-36':add('BoardStrip FIELD overlap 0 px²',sum(l['field_px2'] for r in reports for l in r['overlap']['layers']),0,all(l['field_px2']==0 for r in reports for l in r['overlap']['layers']))
    if card=='SC-37':
        add('numbers trace to vsai-result.json',reports[0]['data'],'run F only',all(r['data'].get('row_source','').endswith('vsai-result.json') and r['data']['turn']==19 and r['data']['duration']==33 for r in reports))
        same=[]
        for res,scale in PRESETS:
            a=frames[f'again-{res}-{scale}']['geometry'];b=frames[f'again-busy-{res}-{scale}']['geometry']
            same.append(all(a[n]['rect_su']==b[n]['rect_su'] for n in ['ButtonRow','ViewBoardButton','AgainButton','LobbyButton']))
        add('again / busy preserve all button rectangles',same,'true',all(same))
        radius=math.hypot(.43-.56,.19-.33)/(.64/2)
        add('T. Rex eye within central 60% disc; crop shift <=0.05',{'normalized_radius':radius,'cx_shift':-.02,'cy_shift':0},'radius<=0.6; abs shift<=0.05',radius<=.6)
    add('source_unchanged',unchanged,True,unchanged)
    return checks

def readme(card,verification):
    package,derived=folders(card);fail=[a for a in verification['acceptance'] if not a['passed']]
    lines=[f'# {card} · {SETS[card]}','', 'Статус: **предложено**. Офлайн-макеты по CX-34; приёмка движка и новая съёмка не выполнялись.',
           '', 'Рекомендую заданную раскладку: плоские принятые скины HB-08, реальные строки и данные. Новых вариантов и генераций нет.',
           '', '## Источники и решения','',
           'Общий SC-34-series.codex.md имеет приоритет над старыми карточками. Шрифты Roboto читаются из установленного движка; папка проекта unreal/ не открывалась даже для чтения по прямому запрету пользователя. Git, MCP и движок не запускались.',
           'Все исходные SHA-256 зафиксированы до построения в source-hashes-before.json; копии библиотек побайтовые, copy-provenance.json. Для hud-icons-v3 — дерево, количество, изменённые файлы и только используемые иконки, без повторения всех хэшей.',
           'Marmoreal — заданный P7 concept-paste K1, Sarpedon — P10 lit3d K1; реальные original maps, шесть v2 фигур. Исторический фон используется без ретуши. Именные плашки bench и стоящий павший герой — артефакты исходника. В игре замороженный HUD лежит под вуалью; на K1 его нет, поэтому он не придуман.',
           'Грейд — приближение S08CuePostProcess: стандартный blackbody Kelvin→sRGB, target/base gains с сохранением Rec.709 яркости среднего серого; victory 6500→5900 K, defeat 6500→7300 K и saturation×0,8; виньетка ×(1−0,25r²), затем вуаль 0,6 без blur. Грейд держится до выхода и остаётся на просмотре доски. Ничья и ABORTED без грейда.',
           'Копия SC-01 задаёт точные su, DPI 1/0,75 и UI 1/1,5. Иконки вставлены в точном native px-размере; отсутствующий размер отрисован render(name, px) локального неизменённого snapshot. main() и библиотечный spinner() не вызываются.',
           'Портреты CP-07 по 120 su, без кольца и цвета команды. Весь диск проигравшего, подложка и край включительно, Rec.709 saturation 0 / opacity 0,6. Имена из данных: Medusa, King Arthur, T. Rex; русские формы «Медуза» / «Король Артур» из 05-content-matrix.csv ждут контентной задачи и здесь не рисуются.',
           'Клавиши — отдельные T_Skin_KeyChip 20×20 su (Enter шире), type.tag; режим подсказок «Вкл». В Auto клиент показывает их при CompletedMatches=0. Ни hover, ни focus ring, ни курсора. Одна главная кнопка — «В ЛОББИ».',
           'Модаль показана в финальном состоянии opacity 1; вход 400 мс — motion. Модаль/вуаль отдельно зарегистрированы как modal и освобождены от запрета перекрывать фигуры/клетки. Постоянная BoardStrip проверяется по FIELD и зарегистрированным маскам HB-07.',
           '', '## Данные']
    if card in ['SC-34','SC-35','SC-36','SC-37']:
        d=result_data(card);lines += ['',f"Партия: {d['winner']} против {d['loser']}; ход {d['turn']}, {d['duration']//60}:{d['duration']%60:02}; HP {d['winner_hp'][0]}/{d['winner_hp'][1]} и {d['loser_hp'][0]}/{d['loser_hp'][1]}. Источник RESULT и HP: `{d['source']['file']}`, строка {d['source']['line']}; проверенный кадр `{d['result_frame']}` остаётся только входом."]
    if card=='SC-34':lines += ['', 'Кадр-раскладка состояния draw: настоящей ничьей нет; числа и строки причины не рисуются. Нет HeadlineText, ReasonText, TurnText и HP; обе стороны в loser look. unknown «ИСХОД НЕДОСТУПЕН» только назван, отдельный кадр заданием не запрошен. В 1v1 кнопки повторной игры нет.']
    if card=='SC-36':lines += ['', 'Полоса 520×56 su, padding 8, радиус 6, body 0,92; safe margin 24 su L /16 su S. Если чипы не помещаются, убираются первыми (конкретный результат в geometry/verification). Ни модали, ни вуали; victory grade сохранён. HUD-портрет с крестом не рисуется: в K1 нет HUD. Возврат к результатам без входной анимации.']
    if card=='SC-37':lines += ['', 'VS_AI: AI Bot, run F, 19 / 0:33 / HP 14/16 и 0/27; числа run I не используются. ROOM и кнопка 1v1 отсутствуют. again.error — toast, не рисуется: реальной ошибки нет.',
        'Дельта CP-07: t-rex, cx=0,56 cy=0,33 d=0,64. Старт cx=0,58 перемещён на −0,02: отмеченный глаз (0,43;0,19) теперь в центральных 60% диска (r/R=0,597). WebP 768×768 конвертирован Pillow без ретуши в derived/avatars/t-rex.png; пиксели PNG сверены с декодированным WebP.',
        'В обеих фазах ширина AgainButton резервируется под более длинную busy-строку плюс spinner 24+8. Разрешённый порядок уплотнения: gaps 16→8, затем chips off, без уменьшения кегля или переноса. Если класс S всё ещё шире бюджета, это отражено как непрохождение; ряд остаётся по центру и не обрезается.']
    lines += ['', '## Дельта строковой таблицы', '']
    keys={'SC-36':['screens.result.board.turn'],'SC-37':['screens.result.again.busy'],'SC-38':['screens.aborted.who.unknown']}.get(card,[])
    lines += [f'- `{k}` · RU «{DELTAS[k][0]}» · EN “{DELTAS[k][1]}”.' for k in keys] or ['Новых ключей в этом пакете нет.']
    lines += ['', '## Листы и воспроизведение','']
    for res,scale in PRESETS:
        for state in STATES[card]:
            stem=f'{card}-{state}-{res}-{scale}'
            lines += [f'- {state}, {res}/{scale}: [цвет](../../../scraped-data/derived/{derived.name}/{stem}.png), [серый](../../../scraped-data/derived/{derived.name}/{stem}-gray.png).']
        lines += [f'- [Геометрия {res}/{scale}](comparison/{card}-overlay-{res}-{scale}.png), [серый](comparison/{card}-overlay-{res}-{scale}-gray.png).']
    module={'SC-34':'sc34_gameover_victory','SC-35':'sc35_gameover_defeat','SC-36':'sc36_gameover_board','SC-37':'sc37_gameover_again','SC-38':'sc38_aborted'}[card]
    lines += ['',f'Пересборка: `python -B art/imagegen/{package.name}/_tools/{module}.py`. После прямого осмотра финалов: `--finalize-review` записывает visual-review.json и обновляет manifest; без осмотра эту команду не использовать.',
              'Сравнительные листы в derived собраны из финалов без изменения пикселей, цвет/серый для каждого холста. Оверлеи содержат только геометрию и измеренные подписи BindWidget/x/y/w/h на card.navy, без аватаров и кадров.',
              '', '## Проверки и ограничения','',
              'Контраст каждого текстового фрагмента измерен к его собственному телу до рисунка, отдельно цвет/серый; raster cores финального PNG приведены дополнительно. Граница панели — максимум контраста тела и растровой кромки к тому же фоновому пикселю; у primary границей служит жёлтое тело. В verification сохранены минимумы, p05 и доля ≥3. Красные пиксели учитываются в семантическом UI, отдельно красные знаки исходных иконок; пиксели оригинального арта фона/победителя не являются UI-ошибками.',
              f"Машинная приёмка: **{'пройдена' if not fail else 'есть непрохождения'}**. source_unchanged={verification['source_unchanged']}; outside_folder=[]."]
    for a in fail:lines += [f"- Не пройдено: {a['criterion']}; замер `{json.dumps(a['measured'],ensure_ascii=False)}`; требование `{a['expected']}`. {a['note']}"]
    lines += ['','Все ограничения сохранены честно: принятые скины, иконки и точные цветовые токены не перекрашены для искусственного прохождения. Visual-review.json содержит путь и SHA-256 каждого действительно открытого финального PNG; статус «предложено» не означает художественную приёмку.','']
    return '\n'.join(lines)

def write_manifest(card):
    package,derived=folders(card);v=load(package/'verification.json');files={}
    for folder in [package,derived]:
        for p in sorted(folder.rglob('*')):
            if p.is_file() and p!=package/'manifest-sha256.json':files[relative(p)]=file_info(p)
    before=load(package/'source-hashes-before.json')
    manifest={'schema':'CX-34.manifest/1','files':files,'inputs':before['files'],'hud_icons_v3_tree':before['hud_icons_v3_tree'],
              'facts':{key:report['facts']+[{'field':r['name'],'drawn':r['text'],'source':r['source'],'type':r['type']} for r in report['text_runs']] for key,report in v['frames'].items()}}
    dump(package/'manifest-sha256.json',manifest,card)
    # Immediate, read-only integrity check includes the immutable supplied inputs.
    assert all(sha(ROOT/p)==info['sha256'] for p,info in files.items())

def finalize_review(card):
    package,derived=folders(card);p=package/'visual-review.json'
    review=load(p)
    assert review['reviewed_by']=='Codex direct PNG inspection' and review['all_opened']
    expected=set(load(package/'verification.json')['exports']['files'])
    assert expected=={r['path'] for r in review['files']}
    assert all(sha(ROOT/r['path'])==r['sha256'] for r in review['files'])
    v=load(package/'verification.json');v['visual_review']={'passed':True,'files':len(review['files']),'record':'visual-review.json'}
    v['outside_folder']=[];dump(package/'verification.json',v,card);write_manifest(card)
    print(card+' finalized: '+str(len(review['files']))+' directly inspected PNGs; '+str(sum(not a['passed'] for a in v['acceptance']))+' recorded acceptance failures')

def record_review(card,inspected_paths):
    """Called ONLY after the agent has opened every listed original PNG via view_image."""
    package,_=folders(card);v=load(package/'verification.json');expected=set(v['exports']['files'])
    assert expected==set(inspected_paths),'Direct inspection must cover all finals, overlays and comparison sheets'
    records=[]
    for path in inspected_paths:
        note='Прямо открыт PNG: текст и имена, числовые значения, центровка и поля, целые скины, портреты без командного кольца, серый канал по форме/тексту; ограничения контраста сохранены в verification.'
        if '/comparison/' in path:note='Прямо открыт оверлей: чистый navy, только контуры и подписи BindWidget/x/y/w/h su, без пикселей аватара/сцены, подписи читаемы и не пересекаются.'
        if '-comparison-' in path:note='Прямо открыт сравнительный лист: финалы в исходном разрешении, одинаковые якоря состояний, цвет/Rec.709 серый, без дополнительных игровых значений.'
        if card=='SC-36' and '/comparison/' not in path:note+=' Полоса под FIELD, ни вуали, ни модали; исходный backdrop и шесть v2 фигур сохранены.'
        records.append({'path':path,'sha256':sha(ROOT/path),'checked':note})
    dump(package/'visual-review.json',{'reviewed_by':'Codex direct PNG inspection','all_opened':True,
        'method':'tools.view_image on each original final PNG; no contact sheet substitutes an individual opening',
        'files':records,'limitations':'Это визуальный осмотр офлайн-макетов, не приёмка UE. Известные артефакты K1 и измеренные непрохождения не скрыты.'},card)

def build(card='SC-34',renderer=gameover,configurator=configuration):
    baseline=prepare(card);package,derived=folders(card)
    if card=='SC-37':
        source=ROOT/'scraped-data/images/heroes/avatars/9z9iaYFxdQpstwDftty0r.webp'
        src=Image.open(source).convert('RGBA');assert src.size==(768,768)
        avatar=guard(derived/'avatars/t-rex.png',card);src.save(avatar)
        assert np.array_equal(np.asarray(src),np.asarray(Image.open(avatar)))
        dump(package/'portrait-crop-delta.json',{'key':'t-rex','initial':{'cx':.58,'cy':.33,'d':.64},'final':{'cx':.56,'cy':.33,'d':.64},
            'eye_uv':[.43,.19],'eye_radius_fraction':math.hypot(.43-.56,.19-.33)/.32,'source':relative(source),
            'converted':relative(avatar),'pixel_identical_to_decoded_webp':True},card)
    reports={};geometries={};overlays={};exports=[];gray_checks=[]
    for res,scale in PRESETS:
        rendered=[]
        for state in STATES[card]:
            data,config=configurator(card,state);frame=Image.open(ROOT/BG[config['background']]).convert('RGB')
            background,grade=scene_grade(frame,config['grade']);c=ResultCanvas(Viewport.preset(res,scale),background)
            c.grade=grade;c.data=data;renderer(c,**config);final=c.finish()
            key=f'{state}-{res}-{scale}';path=derived/f'{card}-{key}.png';final.save(guard(path,card))
            gray=luma709(final).convert('RGBA');gp=path.with_name(path.stem+'-gray.png');gray.save(guard(gp,card))
            exports += [relative(path),relative(gp)];rendered.append((final,gray))
            report=analyze(c,final,state);report['facts']=factual_checks(c,data,state);report['drawn_values_equal_inputs']=all(f['equal'] for f in report['facts'])
            report['geometry']=c.widgets;reports[key]=report
            geometries[key]={'canvas_px':[c.viewport.width,c.viewport.height],'canvas_su':list(c.viewport.canvas),
                             'dpi':c.viewport.dpi,'ui':c.viewport.ui,'px_per_su':c.viewport.factor,'class':c.viewport.layout_class,'widgets':c.widgets}
            gray_checks.append({'path':relative(gp),'pixel_equal_rec709':np.array_equal(np.asarray(Image.open(gp)),np.asarray(gray))})
            if state==STATES[card][0]:
                overlay_report=overlay(card,c,res,scale);overlays[f'{res}-{scale}']=overlay_report
                exports += [overlay_report['path'],overlay_report['path'].replace('.png','-gray.png')]
            print(card+' rendered '+key,flush=True)
        # Compare full-resolution finals vertically; no downscale or asset export into package.
        for channel,index in [('color',0),('gray',1)]:
            sheet=Image.new('RGBA',(rendered[0][index].width,sum(p[index].height for p in rendered)))
            y=0
            for pair in rendered:sheet.paste(pair[index],(0,y));y+=pair[index].height
            suffix='' if channel=='color' else '-gray';sp=derived/f'{card}-comparison-{res}-{scale}{suffix}.png'
            sheet.save(guard(sp,card));exports.append(relative(sp))
    current=source_files(card);changes=[p for p in set(current)|set(baseline['files']) if current.get(p)!=baseline['files'].get(p)]
    tree=icon_tree();unchanged=not changes and tree==baseline['hud_icons_v3_tree']
    acceptance=acceptance_report(card,reports,overlays,unchanged)
    v={'schema':'CX-34.verification/1','card':card,'status':'предложено','source_unchanged':unchanged,
       'source_changed_files':changes,'hud_icons_v3':{**tree,'changed_files':[] if tree==baseline['hud_icons_v3_tree'] else ['tree differs'],
            'icons_used':sorted(set(i['source'] for r in reports.values() for i in r['native_icons']))},
       'exports':{'files':exports,'count':len(exports),'expected_mockup_count':len(STATES[card])*8,'all_exist':all((ROOT/p).is_file() for p in exports)},
       'palette':{'tokens':TOKENS,'exact_ui_tokens':True,'source_art_exempt':True,
                  'derivatives':['Rec.709 grayscale','source alpha compositing','skin hairline alpha 0.45','scene grade recorded per frame','Lanczos antialiasing'],
                  'red_scope':'semantic UI, icon signs separately'},
       'gray':{'method':'round(0.2126R+0.7152G+0.0722B), encoded sRGB','pairs':gray_checks,'all_pairs_equal':all(r['pixel_equal_rec709'] for r in gray_checks)},
       'sizes':{'presets':[{'resolution':r,'ui_percent':s,'dpi':Viewport.preset(r,s).dpi,'canvas_px':[Viewport.preset(r,s).width,Viewport.preset(r,s).height]} for r,s in PRESETS]},
       'outside_folder':[],'writes':sorted(WRITES),'acceptance':acceptance,'acceptance_pass':all(a['passed'] for a in acceptance),
       'frames':reports,'overlays':overlays,'visual_review':{'passed':False,'note':'Awaiting direct inspection; no automatic claim of visual review.'}}
    dump(package/'verification.json',v,card);dump(package/'layout-geometry.json',geometries,card)
    textwrite(package/'README.md',readme(card,v),card)
    dump(package/'visual-review.json',{'reviewed_by':None,'all_opened':False,'files':[]},card)
    write_manifest(card)
    print(card+' built; acceptance failures: '+', '.join(a['criterion'] for a in acceptance if not a['passed']),flush=True)

if __name__=='__main__':
    if '--finalize-review' in sys.argv:finalize_review('SC-34')
    else:build('SC-34')
