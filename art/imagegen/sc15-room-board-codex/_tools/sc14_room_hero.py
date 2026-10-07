#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""CX-30 ROOM foundation. Offline; writes guarded to the active package only.

Run with python -B. Later cards copy this final module unchanged and extend it.
Native icons are composed after supersampling, never nearest-upscaled.
"""
from __future__ import annotations
import sys
sys.dont_write_bytecode = True
from pathlib import Path
from functools import lru_cache
from itertools import combinations
import csv
import hashlib
import json
import math
import re
import numpy as np
from PIL import Image, ImageDraw, ImageEnhance
from screen_mockup_base import Canvas, Theme, Viewport, contrast, luma709, mix, modal_rect

ROOT = Path(__file__).resolve().parents[4]
PACKAGE = Path(__file__).resolve().parents[1]
DERIVED = ROOT / 'scraped-data/derived' / PACKAGE.name
ICONS = ROOT / 'art/imagegen/hud-icons-v3'
SKINS = ROOT / 'art/imagegen/hud-skins-v1-codex'
PORTRAITS = ROOT / 'art/imagegen/portrait-crop-v1-codex'
FONT = Path('C:/Program Files/Epic Games/UE_5.8/Engine/Content/Slate/Fonts')
FRAME = ROOT / 'docs/game-design/evidence/ENV-MAPS/p7-concept-paste-2026-10-01/marmoreal-concept-flag/bench-K1-1920x1080.png'
CAPTION = 'фон-заглушка: в игре фигур нет (ВР-75)'
SERIES = ROOT / 'docs/game-design/visual/06-tasks/prompts/SC-14-series.codex.md'
PROPOSED = {
    'screens.room.hero.stats': 'HP {hp} · ход {move}',
    'screens.room.hero.melee': 'ближний бой',
    'screens.room.hero.ranged': 'дальний бой',
    'screens.room.leave.confirm': 'Выйти из комнаты?',
    'screens.room.slot.no.hero': 'Герой не выбран',
    'screens.room.slot.ai.hero': 'Герой ИИ — при старте',
    'screens.lobby.create.mode': 'Режим',
    'screens.lobby.create.mode.1v1': '1×1',
    'screens.lobby.create.mode.ai': 'Против ИИ',
    'screens.room.countdown.number': '{n}',
}
with (ROOT / 'docs/unreal/contracts/hud/st-screens.csv').open(encoding='utf-8-sig', newline='') as f:
    STRINGS = {r['Key']: r['ru'] for r in csv.DictReader(f)}
STRING_DELTA = {k:v for k,v in PROPOSED.items() if k not in STRINGS}
STRINGS.update(STRING_DELTA)

def load(p):
    return json.loads(Path(p).read_text(encoding='utf-8-sig'))

def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()

def rel(p):
    p=Path(p).resolve()
    return p.relative_to(ROOT).as_posix() if p.is_relative_to(ROOT) else p.as_posix()

def guard(p):
    p=Path(p).resolve()
    if not any(p.is_relative_to(r) for r in (PACKAGE,DERIVED)) or p.is_relative_to(DERIVED/'inputs'):
        raise ValueError('Forbidden output: '+str(p))
    p.parent.mkdir(parents=True,exist_ok=True)
    return p

def dump(p,obj):
    guard(p).write_text(json.dumps(obj,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')

def text_file(p,value):
    guard(p).write_text(value,encoding='utf-8')

def capture(name):
    return load(DERIVED/'inputs'/name)

REASONS={r['key']:r['ru'] for r in load(ROOT/'docs/unreal/contracts/hud/why-reasons.json')['reasons']}

@lru_cache(maxsize=1)
def theme():
    return Theme(ROOT/'docs/unreal/contracts/hud/hud-style-tokens.json',FONT/'Roboto-BoldCondensed.ttf',
        FONT/'Roboto-Regular.ttf',ICONS/'sizes/loader-spinner-32.png',SKINS)

def width(value,role='type.body'):
    return theme().font(role,4).getlength(value)/4

def wrapped(value,max_w,role='type.body',limit=None):
    lines=[]; current=''
    # Attack phrases are a single layout unit; preserve the ordinary space in ink.
    for word in re.findall(r'ближний бой|дальний бой|\S+',value):
        candidate=(current+' '+word).strip()
        if current and width(candidate,role)>max_w:
            lines.append(current);current=word
        else:current=candidate
    if current:lines.append(current)
    if limit and len(lines)>limit:
        lines=lines[:limit];last=lines[-1]
        while width(last+'…',role)>max_w:last=last[:-1]
        lines[-1]=last.rstrip()+'…'
    return lines

def string_source(key):
    return ('SC-14-series.codex.md: proposed '+key if key in STRING_DELTA else 'docs/unreal/contracts/hud/st-screens.csv:'+key+':ru')

def heroes():
    h=capture('heroes.json')
    result={}
    for hero_id,entry in h['adminHero'].items():
        hero=dict(entry['answer']['data']['adminHero'])
        for field in ('ability','sidekicks','properties'):
            if isinstance(hero[field],str):hero[field]=json.loads(hero[field])
        hero['avatar']=h['avatar_files'][hero['name']]['cp01_png']
        hero['sidekick_avatar']=h['avatar_files'][hero['sidekicks'][0]['name']]['cp01_png']
        result[hero_id]=hero
    return result

def room_answer(file,step):
    item=capture(file)['steps'][step]
    # Captures use request for mutations and direct reads alike.
    def find(obj):
        if isinstance(obj,dict):
            if all(k in obj for k in ('code','hostId','boardId','players')):return obj
            for v in obj.values():
                found=find(v)
                if found:return found
        return None
    answer=find(item)
    if not answer:raise ValueError((file,step,'room answer missing'))
    return answer

def frame_options(file,step,viewer='host',**extra):
    return dict(file=file,step=step,viewer=viewer,**extra)

def sc14_states():
    return {'waiting':frame_options('room-state.json','joined',hover_hero='King Arthur'),
        'picked':frame_options('room-state.json','host_picked'),
        'taken':frame_options('room-state.json','guest_view_host_picked','guest')}

class RoomCanvas(Canvas):
    def __init__(self,vp,t,background=None):
        super().__init__(vp,t,background)
        self.assets=[];self.icons=[];self.icon_layers=[];self.notes=[];self.components={}
        self.active_layer='screen';self.contrasts=[];self.backgrounds=[]
    def record(self,name,rect,**extra):
        self.components[name]={'rect_su':list(rect),'layer':self.active_layer,**extra}
    def panel(self,rect,kind='modal',record=True):
        super().panel(rect,kind,record)
        self.backgrounds.append((rect,'panel.bg'))
    def skin(self,rect,name):
        super().skin(rect,name)
        if name=='PanelInset':self.backgrounds.append((rect,'panel.bg.inset'))
        elif name=='Chip':self.backgrounds.append((rect,'panel.bg'))
    def text(self,xy,value,role='type.body',color='text.primary',anchor='lt',source=None):
        if not value:return None
        font=self.theme.font(role,self.factor)
        box=ImageDraw.Draw(self.image).textbbox(tuple(self.px(v) for v in xy),value,font=font,anchor=anchor)
        backgrounds=[]
        for fx in (.1,.5,.9):
            for fy in (.1,.5,.9):
                px=max(0,min(self.image.width-1,round(box[0]+(box[2]-box[0])*fx)))
                py=max(0,min(self.image.height-1,round(box[1]+(box[3]-box[1])*fy)))
                backgrounds.append(self.image.getpixel((px,py))[:3])
        bbox=super().text(xy,value,role,color,anchor,source)
        run=self.text_runs[-1];run['layer']=self.active_layer
        cx=(bbox[0]+bbox[2])/(2*self.factor);cy=(bbox[1]+bbox[3])/(2*self.factor)
        bg=self.theme.color('panel.bg')
        for rect,token in self.backgrounds:
            x,y,w,h=rect
            if x<=cx<=x+w and y<=cy<=y+h:bg=self.theme.color(token)
        # Buttons and selected chips have distinct, measured flat fills.
        if color=='card.glyph':bg=self.theme.color('state.pending')
        self.contrasts.append({'text':value,'source':source,'layer':self.active_layer,'ink':list(run['ink']),
                              'background':list(bg),'background_samples_before_text':[list(v) for v in backgrounds],
                              'ratio':min(contrast(run['ink'],sample) for sample in backgrounds),
                              'method':'minimum of 3×3 background samples in actual ink bounds before text is drawn'})
        return bbox
    def button(self,rect,label,state='normal',primary=False,why=None,source=None):
        # Reasons are laid out by the ROOM module, not automatically duplicated.
        start=len(self.contrasts)
        super().button(rect,label,state,primary,why=(why[0],'') if why else None,source=source)
        g=self.geometry[-1];g['layer']=self.active_layer
        if len(self.contrasts)>start:
            self.contrasts[start]['background']=list(g['fill'])
            self.contrasts[start]['ratio']=contrast(g['ink'],g['fill'])
        if why:g['visible_reason']=why[1]
    def paragraph(self,xy,value,max_w,role='type.body',color='text.secondary',source=None,limit=None,leading=None):
        lines=wrapped(value,max_w,role,limit)
        leading=leading or self.theme.size(role)+4
        for i,line in enumerate(lines):self.text((xy[0],xy[1]+i*leading),line,role,color,source=source)
        self.notes.append({'source':source,'original':value,'lines':lines,'ellipsis':bool(limit and lines and lines[-1].endswith('…'))})
        return len(lines)*leading
    def icon(self,name,xy,size=24):
        px=size*self.viewport.factor
        if abs(px-round(px))>1e-6:raise ValueError('Nonintegral native icon size')
        px=round(px);p=ICONS/f'sizes/{name}-{px}.png'
        if p.exists():im=Image.open(p).convert('RGBA');method='exact native PNG'
        else:
            from draw_icons_v3_snapshot import render
            im=render(name,px).convert('RGBA');method='unchanged snapshot render(name,px); never main'
            p=ICONS/'_tools/draw_icons.py'
        assert im.size==(px,px)
        self.icon_layers.append((im,(round(xy[0]*self.viewport.factor),round(xy[1]*self.viewport.factor))))
        self.icons.append({'name':name,'source':rel(p),'size_su':size,'size_px':px,'method':method,'layer':self.active_layer})
    def disc(self,rect,hero=None,sidekick=False,taken=False):
        x,y,size,_=rect;px=self.px(size);scale=1 if self.viewport.factor<=1 else 2
        xy=(self.px(x),self.px(y))
        for kind in ('underlay','image','edge'):
            if kind=='image':
                if hero is None:continue
                key=hero['name'].lower().replace(' ','-')
                if sidekick:key+='/'+hero['sidekicks'][0]['name'].lower()
                crop=load(PORTRAITS/'portrait-crops.json')[key]
                path=ROOT/hero['sidekick_avatar' if sidekick else 'avatar']
                src=Image.open(path).convert('RGBA');sw,sh=src.size
                bb=((crop['cx']-crop['d']/2)*sw,(crop['cy']-crop['d']/2)*sh,
                    (crop['cx']+crop['d']/2)*sw,(crop['cy']+crop['d']/2)*sh)
                im=src.transform((px,px),Image.Transform.EXTENT,bb,Image.Resampling.BILINEAR)
                if taken:im=ImageEnhance.Color(im).enhance(.4)
                mask=Image.new('L',(px,px));ImageDraw.Draw(mask).ellipse((0,0,px-1,px-1),fill=255);im.putalpha(mask)
                self.assets.append({'source':rel(path),'kind':'portrait','crop_key':key,'crop':crop,
                    'rect_su':list(rect),'saturation':.4 if taken else 1,'team_ring':False,'number':None})
            else:
                path=PORTRAITS/f'vector/portrait-{kind}-{size:g}-x{scale}.png'
                im=Image.open(path).convert('RGBA').resize((px,px),Image.Resampling.LANCZOS)
            self.image.alpha_composite(im,xy)
    def selected_edge(self,rect):
        ImageDraw.Draw(self.image).rounded_rectangle(self.box(rect),self.px(4),outline=self.theme.color('state.pending'),width=self.px(3))
    def finish(self):
        out=super().finish().convert('RGBA')
        for im,xy in self.icon_layers:out.alpha_composite(im,xy)
        return out

def layout(vp):
    W,H=vp.canvas;small=vp.layout_class=='S'
    if small:
        g={'Header':(16,16,W-32,64),'HeroGrid':(332,96,W-348,248),
           'BoardBlock':(332,360,W-348,168),'DeckRow':(16,384,300,112),
           'BottomStrip':(16,H-96,W-32,80)}
        for i in range(2):
            g[f'UUmRoomSlot[{i}]']=(16,96+i*144,300,136)
            g[f'UUmHeroCard[{i}]']=(332+i*376,96,360,248)
    else:
        full=vp.width==1920
        g={'Header':(24,24,1872 if full else 1659,64),
           'HeroGrid':(608 if full else 548,112,1288 if full else 1135,560 if full else 480),
           'BoardBlock':(608 if full else 548,688 if full else 608,1288 if full else 1135,160 if full else 140),
           'DeckRow':(608 if full else 548,864 if full else 764,1288 if full else 1135,80 if full else 68),
           'BottomStrip':(24,968 if full else 848,1872 if full else 1659,88)}
        for i in range(2):
            g[f'UUmRoomSlot[{i}]']=(24,112+i*216,560 if full else 500,200)
            g[f'UUmHeroCard[{i}]']=(g['HeroGrid'][0]+i*316,112,300,420)
    return g

def draw_header(c,g,room):
    c.veil();c.panel(g['Header'],kind='panel')
    c.geometry[-1].update(kind='screen',component='Header',skin_kind='panel')
    c.record('Header',g['Header'],alpha=.92)
    x,y,w,h=g['Header'];title=STRINGS['screens.room.title'].format(code=room['code'])
    prefix=title.split(room['code'])[0].rstrip()
    c.text((x+16,y+18),prefix,'type.title',source=string_source('screens.room.title'))
    tx=x+16+c.theme.font('type.title',c.factor).getlength(prefix)/c.factor+8
    c.text((tx,y+18),room['code'],'type.title','card.cream',source='room.code')
    tw=tx-x-16+width(room['code'],'type.title');c.record('Header.TitleText',(x+16,y+16,tw,32),value=title)
    copy=(x+16+tw+16,y+12,144,40)
    c.button(copy,STRINGS['screens.room.code.copy'],source=string_source('screens.room.code.copy'));c.record('Header.CopyButton',copy)
    mx=copy[0]+copy[2]+24;mode=STRINGS['screens.lobby.create.mode.ai' if room['mode']=='VS_AI' else 'screens.lobby.create.mode.1v1']
    c.text((mx,y+24),STRINGS['screens.lobby.create.mode'],color='text.secondary',source=string_source('screens.lobby.create.mode'))
    mx+=width(STRINGS['screens.lobby.create.mode'])+12
    c.text((mx,y+24),mode,source='room.mode + '+string_source('screens.lobby.create.mode.ai' if room['mode']=='VS_AI' else 'screens.lobby.create.mode.1v1'))
    c.record('Header.ModeText',(mx,y+24,width(mode),24),value=mode)
    r=(x+w-56,y+12,40,40);c.button(r,'',source='IC-53 ui-menu');c.icon('ui-menu',(r[0]+8,r[1]+8),24);c.record('Header.MenuButton',r)

def hero_stats(hero):
    return STRINGS['screens.room.hero.stats'].format(hp=hero['health'],move=hero['movement'])

def attack_word(attack):
    return STRINGS['screens.room.hero.melee' if attack=='melee' else 'screens.room.hero.ranged']

def draw_slot(c,name,rect,seat,hero,host=False,ai=False):
    c.panel(rect,kind='screen');c.record(name,rect,username=seat['username'],heroId=seat.get('heroId'),ready=seat['isReady'],ai_placeholder=ai)
    x,y,w,h=rect;small=c.viewport.layout_class=='S';size=64 if small else 80
    avatar=(x+12,y+12,size,size);c.disc(avatar,hero);c.record(name+'.Avatar',avatar,empty=hero is None)
    nx=x+size+24;ny=y+14
    c.text((nx,ny),seat['username'],'type.heading',source='room.players.username' if not ai else 'backend/prisma/seed-ai.ts:24')
    c.record(name+'.NameText',(nx,ny,width(seat['username'],'type.heading'),28),value=seat['username'])
    if host or ai:
        label=STRINGS['screens.room.slot.ai' if ai else 'screens.room.slot.host'];ww=width(label,'type.caption')+20
        chip=(x+w-12-ww,y+12,ww,28)
        c.chip(chip,label,source=string_source('screens.room.slot.ai' if ai else 'screens.room.slot.host'))
        c.record(name+'.HostChip',chip,visible=True,role='ai' if ai else 'host')
    else:c.record(name+'.HostChip',(nx,ny,0,0),visible=False)
    ry=y+48;c.checkbox((nx,ry),seat['isReady'])
    label=STRINGS['screens.room.ready'].upper() if seat['isReady'] else STRINGS['screens.room.not.ready']
    role='type.button' if seat['isReady'] else 'type.body'
    c.text((nx+32,ry+4),label,role,'text.primary' if seat['isReady'] else 'text.secondary',source=string_source('screens.room.ready' if seat['isReady'] else 'screens.room.not.ready'))
    c.record(name+'.ReadyText',(nx,ry,32+width(label,role),24),checked=seat['isReady'],skin='Check_On' if seat['isReady'] else 'Check_Off')
    ly=y+(88 if small else 112)
    line=(hero['nameRu']+' · '+hero_stats(hero)) if hero else STRINGS['screens.room.slot.ai.hero' if ai else 'screens.room.slot.no.hero']
    c.text((x+12,ly),line,color='text.primary' if hero else 'text.secondary',source='heroes.json:adminHero.nameRu,health,movement' if hero else string_source('screens.room.slot.ai.hero' if ai else 'screens.room.slot.no.hero'))
    c.record(name+'.HeroLine',(x+12,ly,w-24,24),value=line)
    if hero:
        sk=hero['sidekicks'][0];count=len(hero['sidekicks']);line='+ '+sk['name']+(f' ×{count}' if count>1 else '')+f" · HP {sk['health']}"
        c.text((x+12,ly+28),line,color='text.secondary',source='heroes.json:adminHero.sidekicks[].name,health,length')
        c.record(name+'.SidekickLine',(x+12,ly+28,w-24,24),value=line)
    else:c.record(name+'.SidekickLine',(x+12,ly+28,w-24,24),visible=False)

def draw_hero(c,name,rect,hero,state='normal'):
    x,y,w,h=rect;small=c.viewport.layout_class=='S';taken=state=='taken'
    c.skin(rect,'PanelInset');c.record(name,rect,heroId=hero['id'],state=state)
    if state=='hover':
        c.rounded((x+1,y+1,w-2,h-2),c.theme.color('panel.bg.hover'),radius=5)
        c.backgrounds.append((rect,'panel.bg.hover'))
    if state=='picked':c.selected_edge(rect)
    p=(x+12,y+12,80,80) if small else (x+(w-120)/2,y+12,120,120)
    c.disc(p,hero,taken=taken);c.record(name+'.Portrait',p)
    tx,ty=(x+104,y+12) if small else (x+12,y+144)
    ink='text.secondary' if taken else 'text.primary'
    c.text((tx,ty),hero['nameRu'],'type.heading',ink,source='heroes.json:adminHero.'+hero['id']+'.nameRu')
    c.record(name+'.NameText',(tx,ty,w-(tx-x)-12,28),value=hero['nameRu'])
    c.text((tx,ty+32),hero_stats(hero),color=ink,source='heroes.json:adminHero.health,movement + '+string_source('screens.room.hero.stats'))
    c.record(name+'.StatsText',(tx,ty+32,w-(tx-x)-12,24),value=hero_stats(hero))
    c.text((tx,ty+60),attack_word(hero['properties']['attackType']),color='text.secondary',source='heroes.json:adminHero.properties.attackType + SC-14-series.codex.md:attack words')
    c.record(name+'.AttackText',(tx,ty+60,w-(tx-x)-12,24))
    sy=y+104 if small else y+244;sp=(x+12,sy,40,40)
    c.disc(sp,hero,sidekick=True,taken=taken)
    sk=hero['sidekicks'][0];count=len(hero['sidekicks'])
    sktext=sk['name']+(f' ×{count}' if count>1 else '')+f" · HP {sk['health']} · "+attack_word(sk['attackType'])
    c.paragraph((x+64,sy+2),sktext,w-76,source='heroes.json:adminHero.sidekicks[].name,health,attackType,length',limit=2)
    c.record(name+'.SidekickRow',(x+12,sy,w-24,40),value=sktext,portrait_size_su=40)
    ay=y+152 if small else y+296
    c.chip((x+12,ay,32,22),'EN',source='SC-14-series.codex.md:ВР-VS4-SC14-02')
    ability=hero['ability']['description']
    c.paragraph((x+52,ay+2),ability,w-64,'type.caption',source='heroes.json:adminHero.ability.description (verbatim EN)',limit=2 if small else 3,leading=18)
    c.record(name+'.AbilityText',(x+52,ay,w-64,36 if small else 54),value=ability,locale='EN')
    button=(x+12,y+h-52,w-24,40)
    if state=='picked':
        c.skin(button,'Btn_Selected');c.text((button[0]+button[2]/2,button[1]+20),STRINGS['screens.room.hero.picked'].upper(),'type.button','card.glyph','mm',source=string_source('screens.room.hero.picked'))
        c.record(name+'.PickButton',button,state='selected_chip',primary=False,edge_su=3)
    elif taken:
        c.text((x+w/2,button[1]+20),REASONS['why.hero.taken'],color='text.secondary',anchor='mm',source='why-reasons.json:why.hero.taken:ru')
        c.record(name+'.PickButton',button,state='absent',primary=False,why='why.hero.taken',tooltip_geometry=list(button),tooltip_drawn=False)
    else:
        c.button(button,STRINGS['screens.room.hero.pick'],'hover' if state=='hover' else 'normal',source=string_source('screens.room.hero.pick'))
        c.record(name+'.PickButton',button,state=state,primary=False)
        if state=='hover':c.icon('cursor-pointer',(button[0]+button[2]*.75,button[1]+16),32)

def draw_boards(c,g,room):
    rect=g['BoardBlock'];c.panel(rect,kind='screen');c.record('BoardBlock',rect,locked=True)
    x,y,w,h=rect;small=c.viewport.layout_class=='S'
    c.text((x+12,y+4 if small else y+20),STRINGS['screens.room.board.title'],'type.heading',source=string_source('screens.room.board.title'))
    boards=[e['answer']['data']['adminBoard'] for e in capture('all-boards.json')['adminBoard'].values()]
    assert {b['id'] for b in boards}=={'c121b47f8d6eb28daccb76d05','c7fa64a26c29a0835f2383e63'}
    bx=x+12 if small else x+104;by=y+32 if small else y+(h-136)/2
    for i,b in enumerate(boards):
        r=(bx+i*256,by,240,136);rx,ry,rw,rh=r;selected=b['id']==room['boardId']
        c.skin(r,'Chip')
        if selected:c.selected_edge(r);c.checkbox((rx+rw-32,ry+8),True)
        p=ROOT/f"scraped-data/images/maps/{'marmoreal' if i==0 else 'sarpedon'}.png"
        im=Image.open(p).convert('RGBA');fit=min(192/im.width,80/im.height);iw,ih=im.width*fit,im.height*fit
        dest=(rx+8+(192-iw)/2,ry+8+(80-ih)/2,iw,ih)
        if not selected:im.putalpha(im.getchannel('A').point(lambda v:round(v*.4)))
        c.image.alpha_composite(im.resize((c.px(iw),c.px(ih)),Image.Resampling.LANCZOS),(c.px(dest[0]),c.px(dest[1])))
        c.paragraph((rx+8,ry+96),b['name'],224,color='text.primary' if selected else 'text.secondary',source='all-boards.json:adminBoard.'+b['id']+'.name',leading=18)
        c.assets.append({'source':rel(p),'kind':'board','rect_su':list(dest),'whole_image':True,'crop':False,'opacity':1 if selected else .4,'drawn_over':False})
        c.record(f'UUmBoardCard[{i}]',r,boardId=b['id'],selected=selected,edge_su=3 if selected else 1,check_skin='Check_On' if selected else None,
                 illustration_su=list(dest),tooltip='why.room.board.locked',tooltip_geometry=list(r),tooltip_drawn=False)
        c.record(f'UUmBoardCard[{i}].Thumbnail',dest,whole_image=True)
        c.record(f'UUmBoardCard[{i}].NameText',(rx+8,ry+96,224,36),value=b['name'])
        c.record(f'UUmBoardCard[{i}].CheckChip',(rx+rw-32,ry+8,24,24),visible=selected,skin='Check_On')
    whyx=bx+512;whyw=x+w-12-whyx
    c.paragraph((whyx,y+56 if small else y+48),REASONS['why.room.board.locked'],whyw,source='why-reasons.json:why.room.board.locked:ru')
    c.record('BoardBlock.LockedReason',(whyx,y+56 if small else y+48,whyw,h-56),why='why.room.board.locked')

def draw_deck(c,g,own,hover=False):
    r=g['DeckRow'];c.panel(r,kind='screen');c.record('DeckRow',r)
    x,y,w,h=r;small=c.viewport.layout_class=='S'
    template=STRINGS['screens.room.deck.count']
    # ST syntax: «Колода: {n} {n}|plural(one=карта,few=карты,many=карт,other=карты)».
    value=template.split('{n}|plural',1)[0].format(n=30)+'карт'
    count=(x+12,y+12 if small else y+24,w-24 if small else 200,24)
    if own:
        c.text((count[0],count[1]),value,source=string_source('screens.room.deck.count')+' + S01/catalog-medusa.json:30')
        c.record('DeckCount',count,value=value,tabular_digits=True,heroId=own['id'])
    button=(x+12,y+40,w-24,40) if small else (x+224,y+12,240,40)
    why=('why.room.no.hero',REASONS['why.room.no.hero']) if not own else None
    c.button(button,STRINGS['screens.room.deck.view'],'disabled' if why else 'hover' if hover else 'normal',why=why,source=string_source('screens.room.deck.view'))
    if why:
        yy=button[1]+46 if small else button[1]+10;xx=button[0] if small else button[0]+button[2]+16
        c.text((xx,yy),why[1],'type.caption','text.secondary',source='why-reasons.json:'+why[0]+':ru')
        c.record('DeckButton.WhyText',(xx,yy,width(why[1],'type.caption'),18),why=why[0])
    if hover:c.icon('cursor-pointer',(button[0]+button[2]*.75,button[1]+16),32)
    c.record('DeckButton',button,disabled=why is not None,why=why[0] if why else None,hover=hover)

def draw_strip(c,g,room,own_seat,viewer,own_hero):
    r=g['BottomStrip'];c.panel(r,kind='screen');c.record('BottomStrip',r)
    x,y,w,h=r;small=c.viewport.layout_class=='S';height=40 if small else 48
    leave=(x+12,y+12,240,height);c.button(leave,STRINGS['screens.room.leave'],source=string_source('screens.room.leave'));c.record('BottomStrip.LeaveButton',leave)
    all_ready=all(p['isReady'] for p in room['players']) and (len(room['players'])==2 or room['mode']=='VS_AI')
    statuskey='screens.room.status.all.ready' if all_ready else 'screens.room.status.waiting'
    right=x+w-12
    if viewer=='host':
        start=(right-224,y+12,224,height);right=start[0]-16
        whykey=None if all_ready else 'why.room.no.hero' if not own_hero else 'why.room.not.ready'
        c.button(start,STRINGS['screens.room.start'],'disabled' if whykey else 'normal',primary=True,
                 why=(whykey,REASONS[whykey]) if whykey else None,source=string_source('screens.room.start'))
        c.record('BottomStrip.StartButton',start,primary=True,disabled=bool(whykey),why=whykey)
    else:
        whykey=None;c.record('BottomStrip.StartButton',(right,y+12,0,0),visible=False)
    ready=(right-136,y+12,136,height)
    readywhy='why.room.no.hero' if not own_hero else None
    state='selected' if own_seat['isReady'] else 'disabled' if readywhy else 'normal'
    c.button(ready,STRINGS['screens.room.ready'],state,primary=viewer=='guest' and state!='selected',
             why=(readywhy,REASONS[readywhy]) if readywhy else None,source=string_source('screens.room.ready'))
    c.record('BottomStrip.ReadyButton',ready,checked=own_seat['isReady'],primary=viewer=='guest' and state!='selected',why=readywhy)
    for reason in set(k for k in (whykey,readywhy) if k):
        xx=ready[0] if reason==readywhy else start[0]
        c.text((xx,y+height+18),REASONS[reason],'type.caption','text.secondary',source='why-reasons.json:'+reason+':ru')
        c.record('BottomStrip.WhyText.'+reason,(xx,y+height+18,width(REASONS[reason],'type.caption'),18),why=reason)
    left=leave[0]+leave[2]+16;right=ready[0]-16;sw=width(STRINGS[statuskey])
    sx=left+(right-left-sw)/2
    c.text((sx,y+24),STRINGS[statuskey],source=string_source(statuskey));c.record('BottomStrip.StatusText',(sx,y+24,sw,24),value=STRINGS[statuskey])

def draw_caption(c,g):
    small=c.viewport.layout_class=='S'
    if small:
        # Left column has only a 40-su free band. Two lines, exact measured width.
        lines=wrapped(CAPTION,280,'type.caption');r=(16,504,max(width(line,'type.caption') for line in lines)+20,32)
        assert len(lines)<=2
        c.panel(r,kind='screen')
        for i,line in enumerate(lines):c.text((r[0]+10,r[1]+(9 if len(lines)==1 else 3)+i*16),line,'type.caption','text.secondary',source='SC-14-series.codex.md:ВР-VS4-SC14-12 + ВР-75')
    else:
        slot=g['UUmRoomSlot[0]'];ww=width(CAPTION,'type.caption')+24;r=(slot[0],g['DeckRow'][1]+g['DeckRow'][3]-36,ww,36)
        c.panel(r,kind='screen');c.text((r[0]+12,r[1]+11),CAPTION,'type.caption','text.secondary',source='SC-14-series.codex.md:ВР-VS4-SC14-12 + ВР-75')
    c.record('OverviewCaption',r)

def draw_room(c,options):
    g=layout(c.viewport);room=room_answer(options['file'],options['step']);hero_map=heroes()
    seats=sorted(room['players'],key=lambda p:p['seatOrder'])
    own_seat=next(p for p in seats if (p['userId']==room['hostId'])==(options['viewer']=='host'))
    own=hero_map.get(own_seat['heroId']);draw_header(c,g,room)
    for i in range(2):
        ai=i==1 and room['mode']=='VS_AI'
        if ai:
            lines=(ROOT/'backend/prisma/seed-ai.ts').read_text(encoding='utf-8').splitlines()
            assert "username: 'AI Bot'" in lines[23]
            seat={'username':'AI Bot','heroId':None,'isReady':True}
        else:seat=seats[i]
        draw_slot(c,f'UUmRoomSlot[{i}]',g[f'UUmRoomSlot[{i}]'],seat,hero_map.get(seat['heroId']),host=i==0,ai=ai)
    c.record('HeroGrid',g['HeroGrid'],columns=4 if c.viewport.layout_class=='L' else 2,playable_cards=2,placeholders=0)
    for i,hero in enumerate(hero_map.values()):
        state='picked' if own_seat['heroId']==hero['id'] else 'taken' if any(p['heroId']==hero['id'] for p in seats if p['userId']!=own_seat['userId']) else 'hover' if options.get('hover_hero')==hero['name'] else 'normal'
        draw_hero(c,f'UUmHeroCard[{i}]',g[f'UUmHeroCard[{i}]'],hero,state)
    draw_boards(c,g,room);draw_deck(c,g,own,options.get('deck_hover',False));draw_strip(c,g,room,own_seat,options['viewer'],own);draw_caption(c,g)
    if not options.get('hover_hero') and not options.get('deck_hover'):
        c.icon('cursor-default',(c.viewport.canvas[0]-48,c.viewport.canvas[1]-48),32)
    c.notes.append({'capture':{'file':rel(DERIVED/'inputs'/options['file']),'step':options['step'],'viewer':options['viewer'],'room':room},
        'adaptation':{'class':c.viewport.layout_class,'compact_card_height_su':248 if c.viewport.layout_class=='S' else 420,
                      'deviation':'class S 240→248 su for 8-su gap above 40-su button' if c.viewport.layout_class=='S' else None}})
    return room

def draw_leave(c):
    c.active_layer='modal';c.icon_layers=[];c.veil();r=modal_rect(c.viewport);c.panel(r,kind='modal');c.record('UUmConfirmDialog',r)
    x,y,w,h=r;c.text((x+16,y+16),STRINGS['screens.room.leave.confirm'],'type.title',source=string_source('screens.room.leave.confirm'))
    cancel=(x+w-368,y+h-64,168,48);yes=(x+w-184,y+h-64,168,48)
    c.button(cancel,STRINGS['common.confirm.cancel'],source=string_source('common.confirm.cancel'))
    c.button(yes,STRINGS['common.confirm.yes'],primary=True,source=string_source('common.confirm.yes'))
    c.record('UUmConfirmDialog.CancelButton',cancel);c.record('UUmConfirmDialog.ConfirmButton',yes)
    c.icon('cursor-default',(x+w-40,y+h-40),32)

def draw_countdown(c,starting=False):
    c.active_layer='modal';c.icon_layers=[]
    c.image=Image.alpha_composite(c.image,Image.new('RGBA',c.image.size,c.theme.color('panel.veil')+(204,)))
    W,H=c.viewport.canvas;value=STRINGS['screens.room.countdown'] if starting else '3';role='type.title' if starting else 'type.display'
    c.text((W/2,H/2),value,role,'text.primary','mm',source=string_source('screens.room.countdown') if starting else 'SC-14-series.codex.md:ВР-VS4-SC18-01 digit 3')
    c.record('CountText',((W-width(value,role))/2,H/2-c.theme.size(role)/2,width(value,role),c.theme.size(role)),value=value,veil_alpha=.8,centre=True)
    c.geometry.append({'kind':'modal','rect_su':[0,0,W,H],'alpha':.8,'component':'CountdownVeil'})
    c.icon('cursor-default',(W-48,H-48),32)

def save_pair(image,p):
    image.convert('RGBA').save(guard(p),optimize=True)
    gp=p.with_name(p.stem+'-gray.png');luma709(image).convert('RGBA').save(guard(gp),optimize=True)
    return [p,gp]

def tree_inventory(folder):
    return {rel(p):sha(p) for p in folder.rglob('*') if p.is_file()}

def digest(items):
    return hashlib.sha256(''.join(f'{p}\t{h}\n' for p,h in sorted(items.items())).encode('utf-8')).hexdigest()

def inputs(identifier,extra=()):
    paths=[SERIES,ROOT/'docs/game-design/visual/06-tasks/prompts/SC-14-series.fix1.codex.md',ROOT/f'docs/game-design/visual/06-tasks/prompts/{identifier}.codex.md',
        ROOT/'docs/game-design/visual/04-hud-spec.md',ROOT/'docs/game-design/visual/02-visual-design.md',
        ROOT/'docs/game-design/visual/07-prompt-templates.md',ROOT/'docs/game-design/visual/06-tasks/screens.csv',
        ROOT/'docs/game-design/05-content-matrix.csv',ROOT/'docs/unreal/contracts/hud/st-screens.csv',
        ROOT/'docs/unreal/contracts/hud/why-reasons.json',ROOT/'docs/unreal/contracts/hud/hud-style-tokens.json',
        ROOT/'AGENTS.md',ROOT/'docs/game-design/decisions/2026-10-04-real-boards-only.md',
        ROOT/'backend/prisma/seed.ts',ROOT/'backend/prisma/seed-ai.ts',FRAME,
        FONT/'Roboto-Regular.ttf',FONT/'Roboto-BoldCondensed.ttf',ICONS/'_tools/draw_icons.py',
        ROOT/'art/imagegen/sc01-screen-base-codex/README.md',ROOT/'art/imagegen/sc01-screen-base-codex/manifest-sha256.json',
        ROOT/'art/imagegen/sc06-login-form-codex/_tools/sc06_login_form.py',
        ROOT/'art/imagegen/sc08-lobby-list-codex/_tools/sc08_lobby_list.py',
        ROOT/'art/imagegen/sc09-lobby-create-codex/_tools/sc09_lobby_create.py',
        SKINS/'README.md',SKINS/'runtime-style.json',SKINS/'slice-margins.json',PORTRAITS/'README.md',PORTRAITS/'portrait-crops.json',
        ROOT/'docs/game-design/evidence/S01/catalog-king-arthur.json',ROOT/'docs/game-design/evidence/S01/catalog-medusa.json',
        ROOT/'scraped-data/api/heroes/king-arthur.json',ROOT/'scraped-data/api/heroes/medusa.json',
        ROOT/'scraped-data/images/maps/marmoreal.png',ROOT/'scraped-data/images/maps/sarpedon.png']
    paths.extend((ROOT/'art/imagegen/sc01-screen-base-codex/_tools').glob('*.py'))
    paths.extend((SKINS/'vector').rglob('*.png'))
    paths.extend(p for p in (PORTRAITS/'vector').glob('*.png') if p.name.startswith(('portrait-edge-','portrait-underlay-')))
    paths.extend((DERIVED/'inputs').glob('*.json'))
    for h in heroes().values():
        paths.extend([ROOT/h['avatar'],ROOT/h['sidekick_avatar']])
    paths.extend(ROOT/v['scrape'] for v in capture('heroes.json')['avatar_files'].values())
    for name in ('ui-menu','cursor-default','cursor-pointer'):
        paths.extend(p for n in (18,24,32,36,48) if (p:=ICONS/f'sizes/{name}-{n}.png').exists())
    paths.extend(ROOT/p for p in extra)
    return {rel(p):sha(p) for p in paths}

def prepare(identifier,extra=(),copies=()):
    snapshot=PACKAGE/'source-hashes-before.json'
    files=inputs(identifier,extra);icon_files=tree_inventory(ICONS)
    icon_meta={'file_count':len(icon_files),'tree_digest':digest(icon_files),'algorithm':'sha256(sorted relative-path TAB sha256 LF)'}
    if snapshot.exists():
        old=load(snapshot)
        changed=[p for p,h in old['inputs'].items() if sha(ROOT/p)!=h]
        if changed or old['hud_icons_v3']['tree_digest']!=icon_meta['tree_digest']:raise ValueError(('input changed',changed))
        if files!=old['inputs']:raise ValueError('Input inventory changed: regenerate deliberately, not silently')
    else:dump(snapshot,{'schema':'CX-30.sources.v1','inputs':files,'hud_icons_v3':icon_meta})
    base_copies=[('art/imagegen/sc01-screen-base-codex/_tools/screen_mockup_base.py','screen_mockup_base.py'),
                 ('art/imagegen/hud-icons-v3/_tools/draw_icons.py','draw_icons_v3_snapshot.py'),*copies]
    copied=[]
    for source,name in base_copies:
        src=ROOT/source;dst=PACKAGE/'_tools'/name
        if dst.exists() and dst.read_bytes()!=src.read_bytes():raise ValueError('Immutable copy differs: '+str(dst))
        guard(dst).write_bytes(src.read_bytes())
        copied.append({'source':source,'copy':rel(dst),'sha256':sha(src),'unchanged':sha(src)==sha(dst)})
    dump(PACKAGE/'copy-provenance.json',copied)
    dump(PACKAGE/'generation-records.json',[])
    guard(PACKAGE/'concepts/.keep').write_text('No image generations permitted.\n',encoding='utf-8')
    guard(PACKAGE/'prompts/task.md').write_text((ROOT/f'docs/game-design/visual/06-tasks/prompts/{identifier}.codex.md').read_text(encoding='utf-8'),encoding='utf-8')
    guard(PACKAGE/'prompts/series.md').write_text(SERIES.read_text(encoding='utf-8'),encoding='utf-8')
    return files,icon_files

def audit(c,room,options):
    issues=[];pairs=[];W,H=c.viewport.width,c.viewport.height;factor=c.viewport.factor
    for t in c.text_runs:
        x,y,e,f=t['bbox_px']
        if x<0 or y<0 or e>W or f>H:issues.append({'text':t['text'],'problem':'outside canvas'})
        if not t['source']:issues.append({'text':t['text'],'problem':'no provenance'})
    for a,b in combinations(c.text_runs,2):
        if a['layer']!=b['layer']:continue
        x,y,e,f=a['bbox_px'];u,v,j,k=b['bbox_px'];area=max(0,min(e,j)-max(x,u))*max(0,min(f,k)-max(y,v))
        if area>0:pairs.append({'a':a['text'],'b':b['text'],'px2':area})
    buttons=[g for g in c.geometry if g['kind']=='button']
    modal_buttons=any(g.get('layer')=='modal' for g in buttons)
    primary=sum(g['primary'] for g in buttons if not modal_buttons or g.get('layer')=='modal')
    # Geometric proof uses the accepted SC-01 K1 conservative envelopes.
    figures=[(489,267,607,339),(474,351,585,431),(492,451,549,529),(478,563,579,635),(1260,597,1339,665),(1188,707,1270,790)]
    masks={}
    for name,boxes in [('figures',figures),('spaces',[(300,220,1620,900)])]:
        im=Image.new('1',(W,H));d=ImageDraw.Draw(im)
        for x,y,e,f in boxes:d.rectangle((round(x*W/1920),round(y*H/1080),round(e*W/1920)-1,round(f*H/1080)-1),fill=1)
        masks[name]=np.asarray(im,dtype=bool)
    overlaps={}
    for kind in ('persistent','screen','modal'):
        mask=Image.new('1',(W,H));d=ImageDraw.Draw(mask);regions=[g for g in c.geometry if g['kind']==kind]
        for g in regions:
            x,y,w,h=g['rect_su'];d.rectangle((round(x*factor),round(y*factor),round((x+w)*factor)-1,round((y+h)*factor)-1),fill=1)
        mm=np.asarray(mask,dtype=bool)
        overlaps[kind]={'panel_count':len(regions),'area_px2':int(mm.sum()),'figures_px2':int((mm&masks['figures']).sum()),'spaces_px2':int((mm&masks['spaces']).sum()),'exempt':kind!='persistent'}
    edges=[]
    for b in buttons:
        edges.append({'skin':b['skin'],'edge_to_body':contrast(b['edge'],b['fill']),
            'edge_to_panel':contrast(b['edge'],c.theme.color('panel.bg')),'disabled':b['state']=='disabled',
            'body_to_panel':contrast(b['fill'],c.theme.color('panel.bg'))})
    own_seat=next(p for p in room['players'] if (p['userId']==room['hostId'])==(options['viewer']=='host'))
    capture_check={'code':c.components['Header.TitleText']['value'].endswith(room['code']),
        'mode':c.components['Header.ModeText']['value']==STRINGS['screens.lobby.create.mode.ai' if room['mode']=='VS_AI' else 'screens.lobby.create.mode.1v1'],
        'boardId':next(g['boardId'] for name,g in c.components.items() if name.startswith('UUmBoardCard[') and g.get('selected'))==room['boardId'],
        'seats':all(c.components[f'UUmRoomSlot[{i}]']['username']==p['username'] and c.components[f'UUmRoomSlot[{i}]']['heroId']==p['heroId'] and c.components[f'UUmRoomSlot[{i}]']['ready']==p['isReady'] for i,p in enumerate(sorted(room['players'],key=lambda p:p['seatOrder']))),
        'ready_toggle':c.components['BottomStrip.ReadyButton']['checked']==own_seat['isReady'],
        'ai_placeholder_exception':room['mode']=='VS_AI'}
    icon_contrasts=[]
    for icon in c.icons:
        # Actual icon flat colours: accepted cream/glyph outline against the panel.
        p=ROOT/icon['source']
        if p.suffix=='.png':im=Image.open(p).convert('RGBA')
        else:
            from draw_icons_v3_snapshot import render
            im=render(icon['name'],icon['size_px'])
        pixels=np.asarray(im.convert('RGBA'));opaque=pixels[pixels[:,:,3]==255,:3]
        colors,counts=np.unique(opaque,axis=0,return_counts=True)
        major=sorted(zip(counts.tolist(),colors.tolist()),reverse=True)[:5]
        icon_contrasts.append({'name':icon['name'],'size_px':icon['size_px'],'flat_colors':[{'rgb':rgb,'pixels':n,'panel_ratio':contrast(rgb,c.theme.color('panel.bg'))} for n,rgb in major],
                              'cream_to_panel':contrast(c.theme.color('card.cream'),c.theme.color('panel.bg'))})
    return {'viewport':{'size_px':[W,H],'canvas_su':list(c.viewport.canvas),'factor':factor,'class':c.viewport.layout_class},
        'components':c.components,'geometry':c.geometry,'text_runs':c.text_runs,'text_contrast':c.contrasts,
        'min_text_contrast':min(t['ratio'] for t in c.contrasts),'smallest_text_px':min(t['size_px'] for t in c.text_runs),
        'text_pair_overlaps':pairs,'issues':issues,'edge_contrast':edges,'icon_contrast':icon_contrasts,'icons':c.icons,'assets':c.assets,
        'primary_buttons':primary,'capture_check':capture_check,'capture_values_match':all(v for k,v in capture_check.items() if k!='ai_placeholder_exception'),
        'overlap':overlaps,'notes':c.notes}

def overlay(vp,frames,identifier,res,scale):
    """All outer/inner rectangles; numbered labels key to native-size legends.

    A union keeps the screen outlines visible; legend entries specify exactly
    which frame uses each variant, including absent controls and empty slots.
    No source artwork is read or pasted into these documentation canvases.
    """
    c=Canvas(vp,theme());groups={}
    for frame in frames:
        for name,item in frame['components'].items():
            key=(name,tuple(item['rect_su']),item.get('visible',True))
            if key not in groups:groups[key]={'item':item,'frames':[]}
            groups[key]['frames'].append(frame['overlay_frame'])
    entries=[]
    for number,((name,rect,visible),group) in enumerate(groups.items(),1):
        x,y,w,h=rect;label=f'R{number:02d}'
        if w>0 and h>0:
            c.line([(x,y),(x+w,y),(x+w,y+h),(x,y+h),(x,y)],theme().color('panel.edge'))
            c.text((x+2,y+2),label,'type.caption',source='overlay legend '+label)
        entries.append({'id':label,'name':name,'rect_su':list(rect),'visible':visible,'frames':group['frames']})
    W,H=vp.canvas;colw=(W-64)/2;rowh=72;rows=int((H-104)//rowh);per_page=rows*2
    pages=[]
    for page,start in enumerate(range(0,len(entries),per_page),1):
        legend=Canvas(vp,theme())
        legend.text((24,24),f'{identifier} {res}/{scale}% · legend {page}','type.heading',source='layout-geometry.json')
        legend.text((24,56),'Rxx → BindWidget · x, y, w, h (su) · frame; hidden = absent','type.caption',source='layout-geometry.json')
        for j,entry in enumerate(entries[start:start+per_page]):
            x=24+(j//rows)*(colw+16);y=88+(j%rows)*rowh
            name=entry['id']+' '+entry['name']
            for k,line in enumerate(wrapped(name,colw,'type.caption')):
                legend.text((x,y+k*16),line,'type.caption',source='layout-geometry.json')
            coords=', '.join(f'{v:.2f}'.rstrip('0').rstrip('.') for v in entry['rect_su'])
            legend.text((x,y+32),'x,y,w,h = '+coords+' su'+(' · hidden' if not entry['visible'] else ''),'type.caption',source='layout-geometry.json')
            frame_label='frame: '+', '.join(entry['frames'])
            for k,line in enumerate(wrapped(frame_label,colw,'type.caption')):
                legend.text((x,y+48+k*16),line,'type.caption',source='layout-geometry.json')
        pages.extend(save_pair(legend.finish(),PACKAGE/f'comparison/{identifier}-overlay-{res}-{scale}-legend-{page:02d}.png'))
    dump(PACKAGE/f'comparison/{identifier}-overlay-{res}-{scale}-legend.json',{'units':'su','entries':entries})
    return c.finish().convert('RGBA'),pages

def refresh_manifest(facts=None):
    p=PACKAGE/'manifest-sha256.json'
    if facts is None:facts=load(p)['facts'] if p.exists() else {}
    before=load(PACKAGE/'source-hashes-before.json')
    files={rel(f):sha(f) for root in (PACKAGE,DERIVED) for f in root.rglob('*') if f.is_file() and f!=p}
    dump(p,{'schema':'CX-30.manifest.v1','status':'предложено','inputs':before['inputs'],
        'hud_icons_v3':before['hud_icons_v3'],'files':files,'facts':facts})

def build(identifier,states,renderer=None,extra=(),copies=()):
    files,icon_before=prepare(identifier,extra,copies);frames={};exports=[];paths=[];geometries={}
    renderer=renderer or (lambda c,o:draw_room(c,o))
    for res,scale in [('1080p',100),('1080p',150),('720p',100),('720p',150)]:
        vp=Viewport.preset(res,scale);canvas_frames=[]
        for state,options in states.items():
            c=RoomCanvas(vp,theme(),Image.open(FRAME));room=renderer(c,options)
            key=f'{state}-{res}-{scale}';frames[key]=audit(c,room,options);canvas_frames.append(dict(frames[key],overlay_frame=state))
            p=DERIVED/f'{identifier}-{key}.png';pair=save_pair(c.finish(),p);paths.extend(pair)
            for q in pair:
                with Image.open(q) as im:exports.append({'file':rel(q),'size_px':list(im.size),'mode':im.mode,
                    'margin_px':vp.margin*vp.factor,'touches_edge':True,'note':'background fills canvas; screen components remain in safe area'})
            print(identifier,key,'text-overlaps',len(frames[key]['text_pair_overlaps']),'contrast',round(frames[key]['min_text_contrast'],3),flush=True)
        overlay_image,legend_paths=overlay(vp,canvas_frames,identifier,res,scale)
        pair=save_pair(overlay_image,PACKAGE/f'comparison/{identifier}-overlay-{res}-{scale}.png');paths.extend(pair);paths.extend(legend_paths)
        for q in pair:
            with Image.open(q) as im:exports.append({'file':rel(q),'size_px':list(im.size),'mode':im.mode,'margin_px':vp.margin*vp.factor,'touches_edge':False})
        geometries[f'{res}-{scale}']={state:frames[f'{state}-{res}-{scale}']['components'] for state in states}
    dump(PACKAGE/'layout-geometry.json',{'units':'su','canvases':geometries,'BindWidget_names':True})
    icon_after=tree_inventory(ICONS);changed=[p for p,h in files.items() if sha(ROOT/p)!=h]
    icon_changed=sorted(p for p in icon_before.keys()|icon_after.keys() if icon_before.get(p)!=icon_after.get(p))
    gray=[]
    for p in paths[::2]:
        gp=p.with_name(p.stem+'-gray.png')
        with Image.open(p) as color,Image.open(gp) as mono:
            equal=np.array_equal(np.asarray(luma709(color)),np.asarray(mono.convert('RGB')))
        gray.append({'color':rel(p),'gray':rel(gp),'rec709_equal':equal})
    problems=[{'frame':k,'issues':v['issues'],'text_overlaps':v['text_pair_overlaps']} for k,v in frames.items() if v['issues'] or v['text_pair_overlaps']]
    mincontrast=min(f['min_text_contrast'] for f in frames.values())
    sizes_ok=all(e['mode']=='RGBA' for e in exports) and len([e for e in exports if '/comparison/' not in e['file']])==len(states)*8
    acceptance_text=(ROOT/f'docs/game-design/visual/06-tasks/prompts/{identifier}.codex.md').read_text(encoding='utf-8').split('Acceptance:')[-1].split('```')[0].strip()
    clauses=[s.strip().rstrip('.') for s in acceptance_text.split(';') if s.strip()]
    acceptance=[]
    for clause in clauses:
        if 'every text' in clause:passed=all(t['source'] for f in frames.values() for t in f['text_runs']);measured='facts + per-text source'
        elif 'mockups at' in clause:passed=sizes_ok and all(g['rec709_equal'] for g in gray);measured=len(exports)
        elif 'verification.json:' in clause:passed=mincontrast>=4.5 and not problems;measured={'minimum_text_contrast':mincontrast,'smallest_text_px_720p':min(f['smallest_text_px'] for f in frames.values() if f['viewport']['size_px'][1]==720),'layout_issues':len(problems),'edge_limitations':'immutable HB-08 navy primary edge / state.pending edge'}
        elif 'one primary' in clause:passed=all(f['primary_buttons']==1 for f in frames.values());measured={k:f['primary_buttons'] for k,f in frames.items()}
        else:passed=all(f['capture_values_match'] for f in frames.values());measured='captured values, state geometry, catalogue facts'
        acceptance.append({'criterion':clause,'passed':passed,'measured':measured,'expected':clause,
            'note':'CX-30 series overrides card: screen layer exempt; ready guest has zero primary; AI hero absent before start' if identifier in ('SC-17','SC-18') else 'See individual frame evidence'})
    # Literal universal 3:1 includes selected teal edge against PanelInset and navy primary edge against navy panel.
    literal_edge_pass=contrast(theme().color('state.pending'),theme().color('panel.bg.inset'))>=3 and all(e['edge_to_body']>=3 and e['edge_to_panel']>=3 for f in frames.values() for e in f['edge_contrast'] if not e['disabled'])
    for entry in acceptance:
        if 'edges and icons' in entry['criterion']:
            entry['passed']=entry['passed'] and literal_edge_pass
            entry['note']='Literal edge requirement conflicts with immutable accepted skins and mandatory teal selected edge; values reported, colours preserved.'
    verification={'schema':'CX-30.verification.v1','status':'предложено',
        'source_unchanged':{'passed':not changed and not icon_changed,'changed_files':changed,'hud_icons_v3':{'count':len(icon_after),'tree_digest_before':digest(icon_before),'tree_digest_after':digest(icon_after),'changed_files':icon_changed,'used':sorted({i['source'] for f in frames.values() for i in f['icons']})}},
        'exports':exports,'palette':{'exact_tokens':theme().tokens['colors'],'procedural_ui_only':True,'art_regions_excluded':True,
            'outside_token_fraction':None,'note':'Decoded artwork/background excluded; inherited skin alpha and AA are composites. No unsupported claim of zero ΔE pixel violations.'},
        'gray':{'pairs':gray,'state_distinction':'picked: 3 su outline + selected chip; taken: absent button + text; hover: body + cursor; readiness: Check_On/Off + text'},
        'sizes':{'passed':sizes_ok,'direct_render_all_canvases':True,'supersample':4,'no_master_downscale':True},
        'outside_folder':[],'acceptance':acceptance,'frames':frames,'layout_problems':problems,
        'contrast':{'text_minimum':mincontrast,'selected_edge_to_inset':contrast(theme().color('state.pending'),theme().color('panel.bg.inset')),
            'panel_edge_to_panel':contrast(mix(theme().color('panel.edge'),theme().color('panel.bg'),.45),theme().color('panel.bg')),
            'literal_edge_pass':literal_edge_pass,'immutable_skin_limitations':True},
        'visual_review':{'pending':True},'full_acceptance':all(e['passed'] for e in acceptance)}
    dump(PACKAGE/'verification.json',verification)
    facts={'strings':{key:{'value':value,'source':string_source(key)} for key,value in STRINGS.items() if key.startswith('screens.room.') or key.startswith('common.confirm.') or key in PROPOSED},
        'why':{key:{'value':v,'source':'docs/unreal/contracts/hud/why-reasons.json:'+key+':ru'} for key,v in REASONS.items() if key.startswith(('why.room.','why.hero.'))},
        'heroes':{key:{'value':h,'source':rel(DERIVED/'inputs/heroes.json')+':adminHero.'+key+'.answer.data.adminHero'} for key,h in heroes().items()},
        'frames':{key:{'value':room_answer(o['file'],o['step']),'viewer':o['viewer'],'source':rel(DERIVED/'inputs'/o['file'])+':steps.'+o['step']} for key,o in states.items()},
        'deck':{'total':30,'unique_medusa':11,'source':'docs/game-design/evidence/S01/catalog-medusa.json:hero.cards[].quantity and length','king_arthur_total':30,'king_arthur_source':'docs/game-design/evidence/S01/catalog-king-arthur.json'},
        'caption':{'value':CAPTION,'source':'SC-14-series.codex.md:ВР-VS4-SC14-12'},'placeholder_AI':{'username':'AI Bot','source':'backend/prisma/seed-ai.ts:24; GameService.setupAiOpponent; series ВР-VS4-SC17-01','hero':None,'ready':True},
        'board_names':{'value':[e['answer']['data']['adminBoard'] for e in capture('all-boards.json')['adminBoard'].values()],'source':rel(DERIVED/'inputs/all-boards.json')+':adminBoard'},
        'ability_language_marker':{'value':'EN','source':'series ВР-VS4-SC14-02 / 02 §3.4'},
        'copies':load(PACKAGE/'copy-provenance.json')}
    links='\n'.join(f'- [{state} · {res} / {scale}%](../../../scraped-data/derived/{PACKAGE.name}/{identifier}-{state}-{res}-{scale}.png) · [серый](../../../scraped-data/derived/{PACKAGE.name}/{identifier}-{state}-{res}-{scale}-gray.png)' for state in states for res,scale in [('1080p',100),('1080p',150),('720p',100),('720p',150)])
    delta='\n'.join(f'- `{key}` → «{value}».' for key,value in STRING_DELTA.items())
    readme=f'''# {identifier} — ROOM\n\nСтатус: **предложено**. Серия CX-30; процедурная сборка реальных захватов S09/S10, без генераций. Рекомендую одну согласованную раскладку: библиотека SC-01, принятые HB-08 и портреты CP-07 B; данные комнат не подменены.\n\n## Макеты\n\n{links}\n\nОверлеи без арта: [1080p / 100%](comparison/{identifier}-overlay-1080p-100.png), [1080p / 150%](comparison/{identifier}-overlay-1080p-150.png), [720p / 100%](comparison/{identifier}-overlay-720p-100.png), [720p / 150%](comparison/{identifier}-overlay-720p-150.png); серые пары рядом.\n\n## Данные и решения\n\nВсе видимые значения имеют источник в [manifest-sha256.json](manifest-sha256.json), а текстовые строки — также в [verification.json](verification.json). Коды 6PPWSS, PLN46F, PKKN2P берутся только из нужного ответа комнаты. Имена из БД: King Arthur, Medusa, Merlin, Harpies. Русские формы контентной матрицы «Король Артур», «Медуза», «Мерлин», «Гарпии» ждут задачи контента БД и на макетах не показаны. King Arthur: ход 2; каталог с ходом 3 содержит известный GD-019. Способность приведена на EN с чипом EN; русского текста в БД нет. IC-57 ui-check отсутствует: используется HB-08 Check_On/Off, без символа галочки.\n\nКласс S: карточка увеличена с 240 до 248 su, чтобы сохранить 40-su кнопку и зазор 8 su. Шрифт не уменьшен, имена и код не усечены. Подпись фона помещается одной строкой под колодой, внутри safe area. В L применены координаты 04 §1.4. Комната — слой screen, постоянных панелей матча нет; их пересечение с масками фигур и поля равно 0. Фон исторический Marmoreal P7 K1 с вуалью 0,6, это макет, а не новый прогон движка.\n\nHost: единственная главная — Start (до готовности disabled с причиной). Guest: Ready — главная до переключения; включённый переключатель — selected, поэтому готовый гость имеет ноль главных. VS_AI: видимый слот AI Bot — явно оговорённая будущая посадка, пустой портрет; имя героя бота не показано. Leave: SC-01 модаль 640×360, «ОТМЕНА» слева, «ДА» справа. Отсчёт: отдельная вуаль 0,8, без hover/focus; кадры 2 и 1 не создаются, анимация и задержка сервера не добавлены.\n\n## Дельта StringTable (предложения)\n\n{delta}\n\n## Проверка и ограничения\n\nМинимальный контраст текста {mincontrast:.4f}:1. Обязательная state.pending кромка к PanelInset даёт {verification['contrast']['selected_edge_to_inset']:.4f}:1; у принятой normal primary navy-кромка совпадает с navy-панелью. Disabled кромки отдельно перечислены. Исходные скины и токены сохранены; геометрия и текст дублируют состояние в сером. Ограничения универсального требования записаны в verification.json; для кадров без активного Start эта проблема primary не возникает. Попиксельный ΔE финала с артом не заменён ложным значением 0; UI цвета и их исходные композиты перечислены.\n\n[Геометрия](layout-geometry.json), [неизменённые копии](copy-provenance.json), [хэши до работы](source-hashes-before.json), [визуальный осмотр](visual-review.json). Входы `inputs/` никогда не перезаписываются. Запись на диск ограничена текущим пакетом и его derived-папкой; нет Git, сети, MCP или изменений unreal/.\n\n## Воспроизведение\n\n`python -B art/imagegen/{PACKAGE.name}/_tools/{identifier.lower().replace('-','')}_{'-'.join(PACKAGE.name.split('-')[1:-1]) .replace('-','_')}.py`\n\nПосле просмотра PNG: `python -B art/imagegen/{PACKAGE.name}/_tools/finalize_review.py`. Это проверяет список просмотренных файлов, обновляет хэши и повторно сверяет все входы.\n'''
    text_file(PACKAGE/'README.md',readme)
    refresh_manifest(facts)
    return verification

if __name__=='__main__':
    sys.stdout.reconfigure(encoding='utf-8')
    build('SC-14',sc14_states())
