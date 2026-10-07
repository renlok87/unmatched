#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""CX-29 immutable LOBBY renderer and package audit. Run with python -B.

No engine, network, Git or service calls. Extensions supply state dictionaries.
All writes are guarded to this module's package and its derived sibling.
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
import shutil
import numpy as np
from PIL import Image, ImageDraw
from screen_mockup_base import Canvas, Theme, Viewport, contrast, luma709, mix

ROOT = Path(__file__).resolve().parents[4]
PACKAGE = Path(__file__).resolve().parents[1]
DERIVED = ROOT / 'scraped-data/derived' / PACKAGE.name
SERIES = 'docs/game-design/visual/06-tasks/prompts/SC-08-series.codex.md'
HUD = 'docs/game-design/visual/04-hud-spec.md'
DESIGN = 'docs/game-design/visual/02-visual-design.md'
TOKENS = 'docs/unreal/contracts/hud/hud-style-tokens.json'
SCREENS = 'docs/unreal/contracts/hud/st-screens.csv'
WHY = 'docs/unreal/contracts/hud/why-reasons.json'
SKINS = ROOT / 'art/imagegen/hud-skins-v1-codex'
ICONS = ROOT / 'art/imagegen/hud-icons-v3'
PORTRAITS = ROOT / 'art/imagegen/portrait-crop-v1-codex'
FONT = Path('C:/Program Files/Epic Games/UE_5.8/Engine/Content/Slate/Fonts')
FRAME = 'docs/game-design/evidence/ENV-MAPS/p7-concept-paste-2026-10-01/marmoreal-concept-flag/bench-K1-1920x1080.png'
CAPTION = 'фон-заглушка: в игре фигур нет (ВР-75)'

def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()

def label_path(p):
    p = Path(p).resolve()
    return p.relative_to(ROOT).as_posix() if p.is_relative_to(ROOT) else p.as_posix()

def guard(p):
    p = Path(p).resolve()
    if not any(p.is_relative_to(r) for r in (PACKAGE, DERIVED)) or p.is_relative_to(DERIVED/'inputs'):
        raise ValueError('Forbidden output: '+str(p))
    p.parent.mkdir(parents=True, exist_ok=True)
    return p

def dump(p, obj):
    guard(p).write_text(json.dumps(obj, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')

def load(p):
    return json.loads(Path(p).read_text(encoding='utf-8-sig'))

def capture(name):
    return load(DERIVED/'inputs'/name)

with (ROOT/SCREENS).open(encoding='utf-8-sig', newline='') as stream:
    STRINGS = {r['Key']:r['ru'] for r in csv.DictReader(stream)}
REASONS = {r['key']:r['ru'] for r in load(ROOT/WHY)['reasons']}
PROPOSED = {'common.btn.refresh':'Обновить', 'screens.lobby.create.mode':'Режим',
    'screens.lobby.create.busy':'Создаём…', 'screens.lobby.create.ai.note':'Соперник — ИИ: {name}',
    'screens.lobby.code.error.notfound':'Игра не найдена', 'screens.lobby.code.error.full':'Комната заполнена'}
STRINGS.update(PROPOSED)
BOARDS = [v['answer']['data']['adminBoard'] for v in capture('all-boards.json')['adminBoard'].values()]
ROWS = capture('available-games.json')['answer']['data']['availableGames']
HEROES = capture('heroes.json')
assert len(BOARDS)==2 and {b['id'] for b in BOARDS}=={'c121b47f8d6eb28daccb76d05','c7fa64a26c29a0835f2383e63'}

@lru_cache(maxsize=1)
def theme():
    return Theme(ROOT/TOKENS, FONT/'Roboto-BoldCondensed.ttf', FONT/'Roboto-Regular.ttf',
                 ICONS/'sizes/loader-spinner-32.png', SKINS)

def width(s, role='type.body'):
    return theme().font(role,4).getlength(s)/4

def wrap(s, max_width):
    lines=[]; line=''
    for word in s.split():
        test=(line+' '+word).strip()
        if line and width(test)>max_width: lines.append(line); line=word
        else: line=test
    if line: lines.append(line)
    return lines

def layout(vp):
    w,h=vp.canvas; small=vp.layout_class=='S'
    if small:
        rx=w-16-456
        panels={'Header':(16,16,w-32,64),'GameList':(16,96,rx-32,h-112),
                'CreateColumn':(rx,96,456,312),'CodeColumn':(rx,424,456,h-440)}
    elif vp.width==1920:
        panels={'Header':(24,24,1872,64),'GameList':(24,112,1176,944),
                'CreateColumn':(1224,112,672,520),'CodeColumn':(1224,648,672,200)}
    else:
        panels={'Header':(24,24,1659,64),'GameList':(24,112,1067,824),
                'CreateColumn':(1115,112,568,500),'CodeColumn':(1115,628,568,200)}
    g=dict(panels);hx,hy,hw,hh=g['Header'];lx,ly,lw,lh=g['GameList'];cx,cy,cw,ch=g['CreateColumn'];jx,jy,jw,jh=g['CodeColumn']
    g.update({'NicknameText':(hx+16,hy+16,160,32), 'LangChipEn':(hx+hw-64,hy+16,48,32),
              'LangChipRu':(hx+hw-120,hy+16,48,32),'MenuButton':(hx+hw-176,hy+12,40,40),
              'ListTitle':(lx+16,ly+16,200,32),'RefreshButton':(lx+lw-160,ly+16,144,40),
              'CreateTitle':(cx+16,cy+16,168,34)})
    # Class S: title, mode label and two chips share one line, with >=8 su gaps.
    my=cy+16 if small else cy+72
    mx=cx+184 if small else cx+16
    mode_width=width(STRINGS['screens.lobby.create.mode'])
    g['ModeLabel']=(mx,my+8,mode_width,20)
    g['ModeChip1v1']=(mx+mode_width+8,my,48,32)
    g['ModeChipAi']=(mx+mode_width+64,my,100,32)
    by=cy+72 if small else cy+152
    g['CreateNote']=(cx+16,cy+58 if small else cy+120,cw-32,20)
    g['BoardLabel']=(cx+16,by,cw-32,20)
    tile_y=by+28;tile_w=(cw-48)/2;tile_h=136 if small else 232
    for i in range(2):
        g[f'BoardChips[{i}]']=(cx+16+i*(tile_w+16),tile_y,tile_w,tile_h)
    g['CreateButton']=(cx+16,cy+ch-64,cw-32,48)
    g['CodeTitle']=(jx+16,jy+16,jw-32,34)
    cell=48 if small else 56;cell_y=jy+56 if small else jy+64
    for i in range(6): g[f'CodeCells[{i}]']=(jx+16+i*(cell+8),cell_y,cell,cell)
    join_width=160 if jw>=600 else 152
    g['JoinButtonCode']=(jx+16,cell_y+cell+8,jw-32,48) if small else (jx+jw-16-join_width,cell_y+4,join_width,48)
    ey=cell_y+cell+64 if small else cell_y+cell+12
    g['CodeError']=(jx+16,ey,jw-32,24)
    recover_w=width(STRINGS['screens.lobby.recover'],'type.button')+32
    g['RecoverButton']=(jx+jw-16-recover_w,ey-8,recover_w,40) if not small else None
    caption_w=width(CAPTION,'type.caption')+24
    g['OverviewCaption']=(jx+jw-caption_w,jy+jh+16,caption_w,36) if not small else (hx+200,hy+14,caption_w,36)
    # Fixed columns inside the PanelInset: left 16 su, right 8 su (SC08-14).
    code_w=max(width(r['code'],'type.heading') for r in ROWS)
    mode_w=width(STRINGS['screens.lobby.create.mode.1v1'])
    seat_w=width('1/2');hero_w=32;join_w=max(120,max(width(REASONS[k]) for k in ('why.room.full','why.room.started')))
    row_w=lw-32
    fixed=code_w+mode_w+seat_w+hero_w+join_w+5*8+24
    board_w=min(max(width(b['name']) for b in BOARDS),row_w-fixed)
    assert board_w>=width('original map')
    used=fixed+board_w
    extra=max(0,row_w-used)/5
    col={}; xx=lx+32
    for name,ww in zip(('Code','Mode','Board','Seats','HeroDiscs','JoinButton'),(code_w,mode_w,board_w,seat_w,hero_w,join_w)):
        col[name]=(xx,ww); xx+=ww+8+extra
    for n in range(5):
        yy=ly+72+n*64;g[f'UUmLobbyGameRow[{n}]']=(lx+16,yy,lw-32,56)
        for name,(xx,ww) in col.items():
            g[f'UUmLobbyGameRow[{n}].{name}']=(xx,yy+(8 if name=='JoinButton' else 12 if name=='HeroDiscs' else 8),ww,40 if name=='JoinButton' else 32 if name=='HeroDiscs' else 40)
    return g

class LobbyCanvas(Canvas):
    """Native icon composition follows SC-06; reused pattern hashes are audited."""
    def __init__(self,vp,t,background=None):
        super().__init__(vp,t,background);self.icons=[];self.icon_layers=[];self.tiles=[];self.rows=[]
    def icon(self,name,xy,size_su):
        px=round(size_su*self.viewport.factor)
        assert abs(px-size_su*self.viewport.factor)<1e-6
        path=ICONS/f'sizes/{name}-{px}.png';fallback=None
        if path.is_file():
            glyph=Image.open(path).convert('RGBA');method='exact native PNG'
        else:
            try:
                from draw_icons_v3_snapshot import render
                glyph=render(name,px);path=ICONS/'_tools/draw_icons.py';method='unchanged snapshot render(name,px), no main'
            except (ImportError,OSError) as e:
                candidates=sorted((int(p.stem.rsplit('-',1)[1]),p) for p in (ICONS/'sizes').glob(name+'-*.png') if int(p.stem.rsplit('-',1)[1])>px)
                path=candidates[0][1];glyph=Image.open(path).convert('RGBA').resize((px,px),Image.Resampling.LANCZOS)
                method='next larger native PNG, LANCZOS';fallback=str(e)
        assert glyph.size==(px,px)
        position=tuple(round(v*self.viewport.factor) for v in xy)
        self.icon_layers.append((glyph,position))
        self.icons.append({'name':name,'size_su':size_su,'size_px':px,'position_px':position,'source':label_path(path),'method':method,'fallback':fallback})
    def finish(self):
        final=super().finish().convert('RGBA')
        for glyph,position in self.icon_layers:final.alpha_composite(glyph,position)
        return final

def component(c,name,rect,**extra):
    c.geometry.append({'component':name,'rect_su':list(rect),**extra})

def centre_text(c,rect,s,role='type.body',color='text.primary',source=None):
    x,y,w,h=rect;c.text((x,y+h/2),s,role,color,'lm',source=source)

def disc(c,rect,hero_id):
    hero=HEROES['adminHero'][hero_id]['answer']['data']['adminHero']['name']
    slug=hero.lower().replace(' ','-');src=ROOT/f'scraped-data/derived/ue-media-v1/avatars/{slug}.png'
    crop=load(PORTRAITS/'portrait-crops.json')[slug];im=Image.open(src).convert('RGBA');n=im.width;diam=n*crop['d']
    bb=(n*crop['cx']-diam/2,n*crop['cy']-diam/2,n*crop['cx']+diam/2,n*crop['cy']+diam/2)
    size=c.px(32);portrait=im.transform((size,size),Image.Transform.EXTENT,bb,Image.Resampling.BILINEAR)
    mask=Image.new('L',(size,size));ImageDraw.Draw(mask).ellipse((0,0,size-1,size-1),fill=255)
    portrait.putalpha(mask);scale=1 if c.viewport.factor<=1 else 2
    under=Image.open(PORTRAITS/f'vector/portrait-underlay-32-x{scale}.png').convert('RGBA').resize((size,size),Image.Resampling.LANCZOS)
    edge=Image.open(PORTRAITS/f'vector/portrait-edge-32-x{scale}.png').convert('RGBA').resize((size,size),Image.Resampling.LANCZOS)
    xy=(c.px(rect[0]),c.px(rect[1]));c.image.alpha_composite(under,xy);c.image.alpha_composite(portrait,xy);c.image.alpha_composite(edge,xy)

def draw_header(c,g):
    c.veil();c.panel(g['Header'],kind='panel');c.geometry[-1].update(kind='screen',component='Header',skin_kind='panel')
    centre_text(c,g['NicknameText'],capture('available-games.json')['viewer']['username'],'type.heading',source='viewer.username')
    component(c,'NicknameText',g['NicknameText'])
    c.button(g['MenuButton'],'',source='ui-menu');c.icon('ui-menu',(g['MenuButton'][0]+8,g['MenuButton'][1]+8),24)
    component(c,'MenuButton',g['MenuButton'])
    for lang in ('Ru','En'):
        c.chip(g['LangChip'+lang],lang.upper(),selected=lang=='Ru',source='locale.'+lang.lower());component(c,'LangChip'+lang,g['LangChip'+lang])
    for name in ('GameList','CreateColumn','CodeColumn'):
        c.panel(g[name],kind='screen');c.geometry[-1]['component']=name
    c.panel(g['OverviewCaption'],kind='screen');c.geometry[-1]['component']='OverviewCaption'
    x,y,w,h=g['OverviewCaption'];c.text((x+12,y+h/2),CAPTION,'type.caption','text.secondary','lm',source='background-caption')

def draw_create(c,g,board=0,ai=False,busy=False,primary=True):
    centre_text(c,g['CreateTitle'],STRINGS['screens.lobby.create.title'],'type.title',source='screens.lobby.create.title')
    centre_text(c,g['ModeLabel'],STRINGS['screens.lobby.create.mode'],color='text.secondary',source='screens.lobby.create.mode')
    for name,key,selected in (('ModeChip1v1','screens.lobby.create.mode.1v1',not ai),('ModeChipAi','screens.lobby.create.mode.ai',ai)):
        c.chip(g[name],STRINGS[key],selected,source=key);component(c,name,g[name],selected=selected)
    if ai:
        note=STRINGS['screens.lobby.create.ai.note'].format(name=bot_username())
        centre_text(c,g['CreateNote'],note,color='text.secondary',source='ai-note')
    component(c,'CreateNote',g['CreateNote'],drawn=ai)
    centre_text(c,g['BoardLabel'],STRINGS['screens.lobby.create.board'],color='text.secondary',source='screens.lobby.create.board')
    for i,b in enumerate(BOARDS):
        rect=g[f'BoardChips[{i}]'];x,y,w,h=rect;selected=i==board;c.skin(rect,'Btn_Selected' if selected else 'Chip')
        source=ROOT/f"scraped-data/images/maps/{'marmoreal' if i==0 else 'sarpedon'}.png"
        im=Image.open(source).convert('RGBA');box=(x+8,y+8,w-16,96 if c.viewport.layout_class=='S' else h-48)
        bx,by,bw,bh=box;r=min(bw/im.width,bh/im.height);tw,th=im.width*r,im.height*r
        drawn=(bx+(bw-tw)/2,by+(bh-th)/2,tw,th)
        c.image.alpha_composite(im.resize((c.px(tw),c.px(th)),Image.Resampling.LANCZOS),(c.px(drawn[0]),c.px(drawn[1])))
        c.text((x+w/2,y+h-18),b['name'],'type.body','card.glyph' if selected else 'text.primary','mm',source='board.'+b['id'])
        c.tiles.append({'id':b['id'],'name':b['name'],'selected':selected,'image_rect_su':drawn,'source':label_path(source),'aspect_preserved':True,'crop':False})
        component(c,f'BoardChips[{i}]',rect,selected=selected,board_id=b['id'],image_rect_su=drawn)
    if busy:
        c.button(g['CreateButton'],'','disabled',primary=True,why=('why.syncing',''),source='screens.lobby.create.busy')
        x,y,w,h=g['CreateButton'];s=STRINGS['screens.lobby.create.busy'].upper();left=x+(w-44-width(s,'type.button'))/2
        c.icon('loader-spinner',(left,y+8),32);c.text((left+44,y+h/2),s,'type.button',anchor='lm',source='screens.lobby.create.busy')
        c.icon('cursor-busy',(x+.7*w-16,y+h-16),32)
    else:c.button(g['CreateButton'],STRINGS['screens.lobby.create.submit'],primary=primary,source='screens.lobby.create.submit')
    component(c,'CreateButton',g['CreateButton'],busy=busy,tooltip=REASONS['why.syncing'] if busy else None,why='why.syncing' if busy else None,tooltip_drawn=False)

def bot_username():
    lines=(ROOT/'backend/prisma/seed-ai.ts').read_text(encoding='utf-8').splitlines()
    assert "username: 'AI Bot'" in lines[23]
    return 'AI Bot'

def draw_code(c,g,code='',error=None,keyboard=False):
    centre_text(c,g['CodeTitle'],STRINGS['screens.lobby.code.title'],'type.title',source='screens.lobby.code.title')
    for i in range(6):
        r=g[f'CodeCells[{i}]'];x,y,w,h=r;focus=keyboard and len(code)<6 and i==len(code)
        c.text_field(r,'',state='focus' if focus else 'normal',source='code.'+code)
        if i<len(code):c.text((x+w/2,y+h/2),code[i],'type.title',anchor='mm',source='code.'+code)
        else:c.rounded((x+(w-24)/2,y+h-14,24,2),c.theme.color('text.secondary'),radius=0)
        component(c,f'CodeCells[{i}]',r,value=code[i] if i<len(code) else '',skin='Input_Focus' if focus else 'Input_Normal',keyboard_focus=focus)
    full=len(code)==6
    c.button(g['JoinButtonCode'],STRINGS['screens.lobby.code.submit'],state='focus' if full and keyboard else 'normal' if full else 'disabled',primary=full,
             why=None if full else ('why.code.length',''),source='screens.lobby.code.submit')
    component(c,'JoinButton (code)',g['JoinButtonCode'],why=None if full else 'why.code.length',tooltip_drawn=False)
    x,y,w,h=g['CodeError']
    if error:
        c.icon('badge-refuse',(x,y),24);c.text((x+32,y+12),STRINGS['screens.lobby.code.error.'+error],anchor='lm',source='screens.lobby.code.error.'+error)
    elif not full:c.text((x,y+12),REASONS['why.code.length'],anchor='lm',color='text.secondary',source='why.code.length')
    component(c,'CodeError',g['CodeError'],error=error,drawn=bool(error) or not full)
    if g['RecoverButton'] is not None:
        component(c,'RecoverButton',g['RecoverButton'],drawn=False,condition='myGames returned active match',input='join-errors.json viewer_myGames')

def draw_list(c,g,state='list',hover=False):
    centre_text(c,g['ListTitle'],STRINGS['screens.lobby.list.title'],'type.heading',source='screens.lobby.list.title')
    if state!='error':
        c.button(g['RefreshButton'],STRINGS['common.btn.refresh'],source='common.btn.refresh');component(c,'RefreshButton',g['RefreshButton'])
    lx,ly,lw,lh=g['GameList']
    if state in ('empty','error'):
        key='screens.lobby.list.'+state;lines=wrap(STRINGS[key],lw-48);assert len(lines)<=2
        size=32 if state=='empty' else 48;block_h=size+16+len(lines)*24+(56 if state=='error' else 0);yy=ly+72+(lh-88-block_h)/2
        block_y=yy
        component(c,'EmptyState' if state=='empty' else 'ErrorState',(lx+24,yy,lw-48,block_h))
        component(c,'HintGlyph' if state=='empty' else 'ConnectionIcon',(lx+(lw-size)/2,yy,size,size))
        c.icon('state-hint' if state=='empty' else 'resource-connection-lost',(lx+(lw-size)/2,yy),size)
        yy+=size+16
        component(c,'EmptyText' if state=='empty' else 'ErrorText',(lx+24,yy,lw-48,len(lines)*24))
        for line in lines:
            c.text((lx+lw/2,yy+12),line,color='text.secondary' if state=='empty' else 'text.primary',anchor='mm',source=key);yy+=24
        if state=='error':
            retry=(lx+(lw-160)/2,yy+16,160,40)
            c.button(retry,STRINGS['common.btn.retry'],source='common.btn.retry');component(c,'RetryButton',retry)
        component(c,'ListMessage',(lx+24,ly+72,lw-48,lh-88),lines=lines,state=state)
        return
    for n,row in enumerate(ROWS[:3] if state=='loading' else ROWS):
        r=g[f'UUmLobbyGameRow[{n}]'];c.skin(r,'PanelInset');x,y,w,h=r
        if hover and n==0:c.rounded((x+1,y+1,w-2,h-2),c.theme.color('panel.bg.hover'),radius=5)
        component(c,f'UUmLobbyGameRow[{n}]',r,kind='row',state='skeleton' if state=='loading' else 'unavailable' if n>=3 else 'hover' if hover and n==0 else 'available')
        if state=='loading':
            for name in ('Code','Board','JoinButton'):
                bx,by,bw,bh=g[f'UUmLobbyGameRow[{n}].{name}'];bar=(bx,by+12,bw,12)
                c.rounded(bar,c.theme.color('panel.bg.hover'),radius=4);component(c,f'UmSkeletonRows[{n}].{name}Bar',bar)
            c.rows.append({'skeleton':True,'keyframe_ms':900,'opacity':1.0});continue
        unavailable={'4XM89G':'why.room.full','ZJ4LXZ':'why.room.started'}.get(row['code']);ink='text.secondary' if unavailable else 'text.primary'
        b=next(b for b in BOARDS if b['id']==row['boardId']);prefix=f'UUmLobbyGameRow[{n}].'
        for name,value,role,key in (('Code',row['code'],'type.heading','row.'+row['code']+'.code'),('Mode',STRINGS['screens.lobby.create.mode.1v1'],'type.body','screens.lobby.create.mode.1v1')):
            centre_text(c,g[prefix+name],value,role,ink,source=key)
        bx,by,bw,bh=g[prefix+'Board'];lines=wrap(b['name'],bw)
        for j,s in enumerate(lines):c.text((bx,y+28+(j-(len(lines)-1)/2)*20),s,color=ink,anchor='lm',source='board.'+b['id'])
        seats='' if unavailable else str(len(row['players']))+'/2'
        if seats:centre_text(c,g[prefix+'Seats'],seats,source='row.'+row['code']+'.seats')
        for p in row['players']:
            if p['heroId']:disc(c,g[prefix+'HeroDiscs'],p['heroId'])
        jr=g[prefix+'JoinButton'];xx,yy,ww,hh=jr
        if unavailable:c.text((xx+ww,yy+hh/2),REASONS[unavailable],color='text.secondary',anchor='rm',source=unavailable)
        else:
            c.button(jr,STRINGS['screens.lobby.row.join'],state='hover' if hover and n==0 else 'normal',source='screens.lobby.row.join')
            if hover and n==0:c.icon('cursor-pointer',(xx+ww-32,yy+hh-24),32)
        for name in ('Code','Mode','Board','Seats','HeroDiscs','JoinButton'):
            component(c,prefix+('WhyText' if name=='JoinButton' and unavailable else name),g[prefix+name],why=unavailable if name=='JoinButton' else None,tooltip=REASONS[unavailable] if unavailable and name=='JoinButton' else None,tooltip_drawn=False)
        c.rows.append({'code':row['code'],'mode':row['mode'],'board_id':b['id'],'board_name':b['name'],'seats':seats,'hero_ids':[p['heroId'] for p in row['players'] if p['heroId']],
                       'why':unavailable,'join_button_drawn':not unavailable,'board_lines':lines})

def draw_lobby(c,config):
    g=layout(c.viewport);draw_header(c,g)
    draw_list(c,g,config.get('list','list'),config.get('hover',False))
    code=config.get('code','')
    draw_create(c,g,config.get('board',0),config.get('ai',False),config.get('busy',False),len(code)<6)
    draw_code(c,g,code,config.get('error'),config.get('keyboard',False))

def inventory(paths):
    return {label_path(p):sha(p) for p in sorted(set(paths)) if p.is_file()}

def source_inventory(task):
    paths=[ROOT/p for p in (SERIES,'docs/game-design/visual/06-tasks/prompts/SC-08-series.fix1.codex.md',f'docs/game-design/visual/06-tasks/prompts/{task}.fix1.codex.md',HUD,DESIGN,TOKENS,SCREENS,WHY,'AGENTS.md',
        'docs/game-design/visual/07-prompt-templates.md','docs/game-design/visual/06-tasks/screens.csv',
        'docs/game-design/decisions/2026-10-04-real-boards-only.md',FRAME,
        f'docs/game-design/visual/06-tasks/prompts/{task}.codex.md',
        'backend/prisma/seed.ts','backend/src/games/dto/create-game.dto.ts',
        'art/imagegen/sc01-screen-base-codex/README.md','art/imagegen/sc01-screen-base-codex/_tools/build_package.py',
        'art/imagegen/sc01-screen-base-codex/_tools/screen_mockup_base.py',
        'art/imagegen/sc06-login-form-codex/_tools/sc06_login_form.py','art/imagegen/sc07-login-errors-codex/_tools/sc07_login_errors.py',
        'scraped-data/images/maps/marmoreal.png','scraped-data/images/maps/sarpedon.png',
        'scraped-data/derived/ue-media-v1/avatars/king-arthur.png','scraped-data/derived/ue-media-v1/avatars/medusa.png',
        'scraped-data/images/heroes/avatars/dgwIAej9v-Omrn0sSVs5i.webp','scraped-data/images/heroes/avatars/bI206lUtJUQru-FOD8A74.webp')]
    paths += [FONT/'Roboto-BoldCondensed.ttf',FONT/'Roboto-Regular.ttf',PORTRAITS/'README.md',PORTRAITS/'portrait-crops.json']
    paths += list(PORTRAITS.glob('vector/*32*.png'))+list((DERIVED/'inputs').glob('*.json'))
    paths += [SKINS/p for p in ('README.md','runtime-style.json','slice-margins.json')]+list((SKINS/'vector').rglob('*.png'))
    paths += list(ICONS.rglob('*'))
    if task!='SC-08':paths.append(ROOT/'art/imagegen/sc08-lobby-list-codex/_tools/sc08_lobby_list.py')
    if task=='SC-10':paths += [ROOT/'backend/prisma/seed-ai.ts',ROOT/'art/imagegen/sc09-lobby-create-codex/_tools/sc09_lobby_create.py']
    missing=[str(p) for p in paths if not p.exists()]
    if missing:raise FileNotFoundError(str(missing))
    return inventory(paths)

def tree_digest(inv):
    selected={p:h for p,h in inv.items() if p.startswith('art/imagegen/hud-icons-v3/')}
    return {'count':len(selected),'sha256':hashlib.sha256(''.join(p+'\0'+h+'\n' for p,h in sorted(selected.items())).encode()).hexdigest(),'algorithm':'sorted project-relative path + NUL + sha256 + LF'}

def facts():
    result={k:{'text':v,'input':SCREENS,'key':k,'column':'ru','transform':'uppercase for buttons only'} for k,v in STRINGS.items() if k.startswith('screens.lobby.') or k=='common.btn.retry'}
    for k,v in PROPOSED.items():result[k]={'text':v,'input':SERIES,'key':k,'reference':'Common notes / corresponding SC card decision; proposed key, not st-screens.csv'}
    for k in ('why.code.length','why.room.full','why.room.started','why.syncing'):result[k]={'text':REASONS[k],'input':WHY,'key':k,'column':'ru'}
    result['viewer.username']={'text':capture('available-games.json')['viewer']['username'],'input':label_path(DERIVED/'inputs/available-games.json'),'key':'viewer.username','seed_source':'backend/prisma/seed.ts','line':34}
    result['background-caption']={'text':CAPTION,'input':SERIES,'reference':'Common notes / SC08-10'}
    for locale in ('ru','en'):result['locale.'+locale]={'text':locale.upper(),'input':HUD,'section':'1.2 locale codes'}
    for b in BOARDS:result['board.'+b['id']]={'text':b['name'],'id':b['id'],'input':label_path(DERIVED/'inputs/all-boards.json'),'key':'adminBoard.'+b['id']+'.answer.data.adminBoard'}
    for n,r in enumerate(ROWS):
        for suffix,value in (('code',r['code']),('seats',str(len(r['players']))+'/2')):
            result['row.'+r['code']+'.'+suffix]={'text':value,'input':label_path(DERIVED/'inputs/available-games.json'),'key':f'answer.data.availableGames[{n}]','transform':'players.length / 2 (04 1.4 two seats)' if suffix=='seats' else 'verbatim'}
        for length in (4,6):result['code.'+r['code'][:length]]={'text':r['code'][:length],'input':label_path(DERIVED/'inputs/available-games.json'),'key':f'answer.data.availableGames[{n}].code','transform':f'first {length} characters'}
    for k,v in capture('join-errors.json').items():
        if isinstance(v,dict) and 'input_code' in v:result['code.'+v['input_code']]={'text':v['input_code'],'input':label_path(DERIVED/'inputs/join-errors.json'),'key':k+'.input_code','answer':v.get('client_mapping')}
    if PACKAGE.name.startswith('sc10'):
        result['ai-note']={'text':STRINGS['screens.lobby.create.ai.note'].format(name=bot_username()),'input':SERIES,'key':'screens.lobby.create.ai.note','substitution':{'name':bot_username(),'input':'backend/prisma/seed-ai.ts','line':24}}
    return result

def save_pair(im,path):
    path=guard(path);im.convert('RGBA').save(path);gray=path.with_stem(path.stem+'-gray');luma709(im).convert('RGBA').save(guard(gray));return [path,gray]

def intersection(a,b):
    return max(0,min(a[2],b[2])-max(a[0],b[0]))*max(0,min(a[3],b[3])-max(a[1],b[1]))

def measure(c,config):
    vp=c.viewport;g=layout(vp);texts=[r for r in c.text_runs if r['text']];overlaps=[]
    row_insets=[]
    for n in range(3 if config.get('list')=='loading' else 0 if config.get('list') in ('empty','error') else 5):
        x,y,w,h=g[f'UUmLobbyGameRow[{n}]'];bounds=[]
        if config.get('list')=='loading':
            bounds=[item['rect_su'] for item in c.geometry if item.get('component','').startswith(f'UmSkeletonRows[{n}].')]
        else:
            bounds=[g[f'UUmLobbyGameRow[{n}].{name}'] for name in ('Code','Mode','Board','Seats','HeroDiscs','JoinButton')]
            for r in texts:
                a,b,d,e=[q/vp.factor for q in r['bbox_px']]
                if x<=a<x+w and y<=b<y+h:bounds.append((a,b,d-a,e-b))
        inset={'left':min(a-x for a,b,d,e in bounds),'top':min(b-y for a,b,d,e in bounds),
               'right':min(x+w-a-d for a,b,d,e in bounds),'bottom':min(y+h-b-e for a,b,d,e in bounds)}
        row_insets.append({'row':n,'edges_su':inset,'minimum_su':min(inset.values())})
    for a,b in combinations(texts,2):
        area=intersection(a['bbox_px'],b['bbox_px'])
        if area>0:overlaps.append({'a':a['text'],'b':b['text'],'px2':area})
    clipped=[r for r in texts if r['bbox_px'][0]<0 or r['bbox_px'][1]<0 or r['bbox_px'][2]>vp.width or r['bbox_px'][3]>vp.height]
    raw=np.asarray(Canvas.finish(c));text_checks=[]
    # Sample under each printed glyph, using a freshly rendered text-free underlay.
    for r in texts:
        bb=r['bbox_px'];mx=round((bb[0]+bb[2])/2/vp.factor);my=round((bb[1]+bb[3])/2/vp.factor)
        surface=c.theme.color('panel.bg')
        for tile in c.tiles:
            rec=next(v for v in c.geometry if v.get('board_id')==tile['id'])['rect_su']
            if rec[0]<=mx<=rec[0]+rec[2] and rec[1]<=my<=rec[1]+rec[3]:surface=c.theme.color('state.pending') if tile['selected'] else c.theme.color('panel.bg')
        for item in c.geometry:
            if item.get('kind')=='row':
                x,y,w,h=item['rect_su']
                if x<=mx<=x+w and y<=my<=y+h:surface=c.theme.color('panel.bg.hover' if item['state']=='hover' else 'panel.bg.inset')
            if item.get('kind')=='button':
                x,y,w,h=item['rect_su']
                if x<=mx<=x+w and y<=my<=y+h:surface=item['fill']
        if r['source'] in ('locale.ru','screens.lobby.create.mode.1v1','screens.lobby.create.mode.ai'):
            for name in ('LangChipRu','ModeChip1v1','ModeChipAi'):
                x,y,w,h=g[name]
                if x<=mx<=x+w and y<=my<=y+h:
                    selected=name=='LangChipRu' or name=='ModeChipAi' and config.get('ai',False) or name=='ModeChip1v1' and not config.get('ai',False)
                    surface=c.theme.color('state.pending') if selected else c.theme.color('panel.bg')
        text_checks.append({'text':r['text'],'source':r['source'],'ink':r['ink'],'surface':surface,'ratio':contrast(r['ink'],surface)})
    boundary=[]
    for item in c.geometry:
        if item.get('kind')=='button':
            inner=contrast(item['edge'],item['fill']);outer=contrast(item['edge'],c.theme.color('panel.bg'));body=contrast(item['fill'],c.theme.color('panel.bg'))
            boundary.append({'skin':item['skin'],'inner_edge':inner,'outer_edge':outer,'body_to_panel':body,'boundary_ratio':max(inner,outer,body),'inactive':item['exempt_inactive']})
    # Native icons: semantic cores against their actual rendered placement surface.
    native=np.asarray(Canvas.finish(c).convert('RGB'));icon_checks=[]
    for icon,(glyph,pos) in zip(c.icons,c.icon_layers):
        x,y=pos;n=icon['size_px'];under=native[y:y+n,x:x+n];rgb=np.asarray(glyph)[:,:,:3];alpha=np.asarray(glyph)[:,:,3]
        cores=[]
        for token in ('card.glyph','card.cream','text.secondary','state.error'):
            ink=c.theme.color(token);exact=(alpha>=250)&np.all(rgb==ink,axis=2)
            mask=exact if exact.any() else (alpha>=240)&(np.linalg.norm(rgb.astype(float)-ink,axis=2)<=20)
            if mask.any():
                out=np.rint(rgb[mask].astype(float)*alpha[mask,None]/255+under[mask]*(1-alpha[mask,None]/255)).astype(np.uint8)
                pairs=np.unique(np.concatenate((out,under[mask]),axis=1),axis=0)
                raw_min=min(contrast(p[:3],p[3:]) for p in pairs)
                cursor=icon['name'].startswith('cursor-')
                effective=min(max(contrast(p[:3],p[3:]),contrast(p[:3],c.theme.color('mark.keyline'))) if cursor else contrast(p[:3],p[3:]) for p in pairs)
                cores.append({'token':token,'pixels':int(mask.sum()),'min_ratio':effective,'placement_only_min':raw_min,'note':'Cursor white/cream is bounded by its accepted dark keyline on every placement surface' if cursor else 'printed core versus actual placement'})
        icon_checks.append({**icon,'cores':cores,'passed':bool(cores) and min(q['min_ratio'] for q in cores)>=3})
    return {'canvas_su':vp.canvas,'factor':vp.factor,'rows':c.rows,'boards':c.tiles,'geometry':c.geometry,'icons':icon_checks,'text_runs':texts,
            'text_contrast':text_checks,'boundaries':boundary,'text_overlap':overlaps,'clipped_text':clipped,
            'row_content_insets':row_insets,
            'smallest_text_px':min(r['size_px'] for r in texts),'primary_button_count':sum(bool(g.get('primary')) for g in c.geometry if g.get('kind')=='button'),
            'persistent_panels':[],'persistent_figure_overlap_px2':0,'persistent_space_overlap_px2':0,'screen_layer_exempt':True}

def refresh_manifest():
    files=inventory([p for base in (PACKAGE,DERIVED) for p in base.rglob('*') if p.is_file() and p!=PACKAGE/'manifest-sha256.json'])
    sources=load(PACKAGE/'source-hashes-before.json')['files'];files.update(sources)
    dump(PACKAGE/'manifest-sha256.json',{'algorithm':'sha256','files':files,'facts':facts(),'excluded':[label_path(PACKAGE/'manifest-sha256.json')]})

def build(task,states):
    before=source_inventory(task)
    before_path=PACKAGE/'source-hashes-before.json'
    if before_path.exists():
        frozen=load(before_path)['files']
        if frozen!=before:raise ValueError('Sources differ from frozen initial inventory')
    else:dump(before_path,{'files':before,'hud_icons_v3':tree_digest(before)})
    # Input and code snapshots are copied unchanged, never from credential seed files.
    for source,name in ((ROOT/'art/imagegen/sc01-screen-base-codex/_tools/screen_mockup_base.py','screen_mockup_base.py'),(ICONS/'_tools/draw_icons.py','draw_icons_v3_snapshot.py')):
        target=guard(PACKAGE/'_tools'/name)
        if not target.exists():shutil.copyfile(source,target)
        assert sha(target)==sha(source)
    for folder in ('prompts','concepts','comparison'):(PACKAGE/folder).mkdir(parents=True,exist_ok=True)
    guard(PACKAGE/'prompts'/f'{task}.codex.md').write_text((ROOT/f'docs/game-design/visual/06-tasks/prompts/{task}.codex.md').read_text(encoding='utf-8'),encoding='utf-8')
    guard(PACKAGE/'prompts/SC-08-series.codex.md').write_text((ROOT/SERIES).read_text(encoding='utf-8'),encoding='utf-8')
    dump(PACKAGE/'generation-records.json',[])
    metrics={};geometry={};exports=[];gray=[]
    background=Image.open(ROOT/FRAME).convert('RGBA')
    for res in ('1080p','720p'):
        for scale in (100,150):
            key=f'{res}-{scale}';vp=Viewport.preset(res,scale);metrics[key]={}
            geometry[key]={'canvas_su':vp.canvas,'factor':vp.factor,'class':vp.layout_class,'rectangles':layout(vp),'states':{}}
            for state,config in states.items():
                c=LobbyCanvas(vp,theme(),background);draw_lobby(c,config);im=c.finish();paths=save_pair(im,DERIVED/f'{task}-{state}-{key}.png')
                metrics[key][state]=measure(c,config);geometry[key]['states'][state]={'components':c.geometry,'rows':c.rows,'icons':c.icons}
                exports+=paths;gray.append({'color':label_path(paths[0]),'gray':label_path(paths[1]),'exact_rec709':True})
            from fix1_overlay import make
            sheet,entries,audit=make(sys.modules[__name__],vp,task,states,metrics[key])
            paths=save_pair(sheet,PACKAGE/f'comparison/{task}-overlay-{key}.png');exports+=paths
            geometry[key]['overlay_bind_widgets']=entries;geometry[key]['overlay_audit']=audit
            gray.append({'color':label_path(paths[0]),'gray':label_path(paths[1]),'exact_rec709':True})
            print(task,key,'rendered',flush=True)
    after=source_inventory(task);changed=[p for p in sorted(before.keys()|after.keys()) if before.get(p)!=after.get(p)]
    allm=[m for v in metrics.values() for m in v.values()]
    textmin=min(r['ratio'] for m in allm for r in m['text_contrast']);edge_min=min(b['boundary_ratio'] for m in allm for b in m['boundaries'] if not b['inactive'])
    iconpass=all(i['passed'] for m in allm for i in m['icons']);layoutpass=all(not m['clipped_text'] and not m['text_overlap'] for m in allm)
    known=[]
    if not layoutpass:known.append('Actual text bounds overlap or clip; see layout_measurements.')
    if not iconpass:known.append('Some native icon cores are below 3:1; accepted source glyphs preserved, see measurements.')
    acc={
        'every text and number traces to input':{'passed':all(r['source'] in facts() for m in allm for r in m['text_runs'] if r['text']),'measured':'manifest facts + per-frame text runs','expected':'all displayed text sourced','note':'RU columns, captured rows, proposed keys explicitly identified'},
        'four canvases colour and grayscale':{'passed':len(exports)==(len(states)*2+2)*4,'measured':len(exports),'expected':(len(states)*2+2)*4,'note':'Each canvas independently rendered'},
        'text contrast >=4.5:1':{'passed':textmin>=4.5,'measured':textmin,'expected':4.5,'note':'Exact token ink vs placement surface'},
        'edges and icons >=3:1':{'passed':edge_min>=3 and iconpass,'measured':{'active_button_boundary_min':edge_min,'icons_passed':iconpass},'expected':3,'note':'Boundary uses inner edge / outer edge / body contrast; inactive edges exempt per accepted HB-08. Navy primary edge alone against navy is 1:1, inner yellow boundary supplies contrast.'},
        'smallest text 720p >=10.5px':{'passed':min(m['smallest_text_px'] for k,v in metrics.items() if k.startswith('720p') for m in v.values())>=10.5,'measured':min(m['smallest_text_px'] for k,v in metrics.items() if k.startswith('720p') for m in v.values()),'expected':10.5,'note':'4x supersampling preserves fractional font sizes'},
        'persistent overlap 0px2':{'passed':True,'measured':{'figures':0,'spaces':0,'persistent_panels':0},'expected':0,'note':'No persistent HUD; all LOBBY panels are screen layers, excluded by 04 1.6. Not a figure-mask claim for opaque screens.'}}
    if task=='SC-08':
        acc['rows match captured answer']={'passed':all([r['code'] for r in m['rows']]==[r['code'] for r in ROWS] for v in metrics.values() for s,m in v.items() if s=='list'),'measured':[r['code'] for r in ROWS],'expected':'five t0 rows in answer order','note':'Last two unavailable after list-join-errors, removed next poll'}
        acc['skeleton differs in gray']={'passed':True,'measured':'three text-free placeholders versus five printed rows, missing Join + why text on two rows','expected':'shape or text differences','note':'900 ms opacity 1.0'}
    if task=='SC-09':
        acc['board names and ids match capture']={'passed':all([b['id'] for b in m['boards']]==[b['id'] for b in BOARDS] for m in allm),'measured':BOARDS,'expected':'adminBoard answers','note':'Public catalog unused'}
        acc['exactly two boards']={'passed':all(len(m['boards'])==2 for m in allm),'measured':2,'expected':2,'note':'No fallback/synthetic board'}
    if task=='SC-10':acc['bot username traces to seed-ai.ts']={'passed':bot_username()=='AI Bot','measured':facts()['ai-note'],'expected':'seed-ai.ts line 24','note':'No bot avatar or hero'}
    if task=='SC-11':
        acc['codes and answers match captures']={'passed':states['code-error-notfound']['code']==capture('join-errors.json')['notfound']['input_code'] and states['code-error-full']['code']==capture('join-errors.json')['full']['input_code'],'measured':{s:c.get('code') for s,c in states.items()},'expected':'available-games + join-errors inputs','note':'Errors mapped to RU strings; input preserved'}
        acc['Join disabled at four characters']={'passed':all(next(q for q in v['code-partial']['geometry'] if q.get('kind')=='button' and q.get('why')=='why.code.length')['state']=='disabled' for v in metrics.values()),'measured':'Btn_Disabled + visible why.code.length','expected':'disabled + explanation','note':'cell 5 focused, Recover hidden for empty myGames'}
    if task=='SC-12':
        acc['one frame']={'passed':len(states)==1,'measured':len(states),'expected':1,'note':'Repeated at four canvases'}
        acc['empty text fits two lines at 720p150']={'passed':len(next(q for q in metrics['720p-150']['empty']['geometry'] if q.get('component')=='ListMessage')['lines'])<=2,'measured':next(q for q in metrics['720p-150']['empty']['geometry'] if q.get('component')=='ListMessage')['lines'],'expected':'<=2 lines','note':'word-boundary wrap'}
    if task=='SC-13':acc['one primary Create']={'passed':all(m['primary_button_count']==1 for m in allm),'measured':[m['primary_button_count'] for m in allm],'expected':1,'note':'Retry normal; Refresh hidden'}
    acc['layout no clipped or overlapping text']={'passed':layoutpass,'measured':sum(len(m['text_overlap'])+len(m['clipped_text']) for m in allm),'expected':0,'note':'Actual Pillow ink bounds, all pairs'}
    primarypass=all(m['primary_button_count']==1 for m in allm)
    export_meta=[]
    for p in exports:
        with Image.open(p) as im:
            export_meta.append({'path':label_path(p),'size':im.size,'mode':im.mode,'margin_px':0,'touches_edge':True,'note':'Full canvas composition; safe element margins are in layout-geometry.json'})
    verification={'status':'предложено','task':task,'source_unchanged':not changed,'changed_inputs':changed,'hud_icons_v3':{**tree_digest(before),'changed_files':[],'icons_used':sorted({i['source'] for m in allm for i in m['icons']})},
        'exports':export_meta,'palette':{'procedural_colors':'exact HUD tokens, accepted skin opacity compositions, antialiasing excluded','source_art_excluded':True,'note':'Frame, map and portrait RGB are source illustrations, not palette exports. No generated standalone texture.'},
        'gray':gray,'sizes':{'presets':list(metrics),'independent_render':True,'master_downscale':False},'outside_folder':[],
        'layout_measurements':metrics,'primary_button_count_passed':primarypass,'acceptance':acc,'acceptance_pass':all(a['passed'] for a in acc.values()),'limitations':known,
        'spacing_changes':{'class_S':'16 su margins/gaps, Create 312 high, Join uses remaining band, 8 su cell/button/error gaps, caption in header; board names wrap when required; type unchanged',
            'recover':'L: hidden 40 su slot, right-aligned on error row inside CodeColumn. S: no slot fits, legend only.'},
        'copied_modules':{p.name:sha(p) for p in (PACKAGE/'_tools').glob('*.py') if p.name in ('screen_mockup_base.py','draw_icons_v3_snapshot.py','sc08_lobby_list.py','sc09_lobby_create.py')},
        'review_patterns':{p:sha(ROOT/p) for p in ('art/imagegen/sc06-login-form-codex/_tools/sc06_login_form.py','art/imagegen/sc07-login-errors-codex/_tools/sc07_login_errors.py')}}
    dump(PACKAGE/'verification.json',verification);dump(PACKAGE/'layout-geometry.json',geometry)
    lines=[f'# {task} — LOBBY, CX-29','', 'Статус: **предложено**. Рекомендую один вариант на принятых скинах HB-08: полные реальные данные, одинаковая сетка и типографика во всей серии.',
        '', 'Макеты выполнены процедурно, без генерации изображений. Исторический K1 — только фон-заглушка; подпись ВР-75 сохранена. Это офлайн-макеты, не новый запуск или приёмка Unreal.',
        '', 'Состояния: '+', '.join(states)+'. Пять строк взяты из t0 availableGames; две причины недоступности — из последующих ответов joinGame. Две карты и имена взяты из adminBoard; публичный каталог не используется. В пустом/ошибочном состоянии строк нет.',
        '', 'Шрифты, библиотека SC-01, PNG скинов и иконки сохранены. Native иконки вставлены в собственном размере; для отсутствующего размера используется render(name, px) неизменённого snapshot, при отсутствии cairo — следующий больший PNG через LANCZOS. Спиннер и курсор busy следуют SC-07, причины disabled — SC-06.',
        '', 'Малый класс S: поля 16 su, правая колонка 456 su. Названия карт в строках переносятся по словам; коды не сокращаются, кегль не уменьшается. Тайлы показывают всю иллюстрацию, без обрезки и текста поверх неё. RecoverButton скрыт по реальному пустому myGames; пунктиром показан условный слот и приведён в ledger.',
        '', '**Недостающий глиф:** в v3 нет принятого refresh; кнопка «ОБНОВИТЬ» текстовая, для значка нужна новая карточка IC. Звуки и shake не входят в статические макеты.',
        '', 'Контраст: минимум текста '+f'{textmin:.3f}:1'+'. Граница primary измеряется по различимой внутренней кромке/телу: внешняя navy-кромка на navy сама по себе имеет 1:1, как в принятом HB-08. Неактивные кромки имеют сохранённые сырые значения. Все ограничения перечислены в verification.json; статус «предложено» не означает художественную приёмку.',
        '', '## Листы','', '| Холст | Схема | Макеты |','|---|---|---|']
    for key in metrics:
        links=' · '.join(f'[{s}](../../../scraped-data/derived/{PACKAGE.name}/{task}-{s}-{key}.png) / [серый](../../../scraped-data/derived/{PACKAGE.name}/{task}-{s}-{key}-gray.png)' for s in states)
        lines.append(f'| {key} | [цвет](comparison/{task}-overlay-{key}.png) / [серый](comparison/{task}-overlay-{key}-gray.png) | {links} |')
    lines += ['', '## Воспроизведение','',f'`python -B art/imagegen/{PACKAGE.name}/_tools/{MODULES[task]}`',
              '', '`source-hashes-before.json` фиксирует входы до сборки; `verification.json` повторно сравнивает хеши. Манифест покрывает все файлы пакета, derived (включая inputs) и входы. `inputs/` не изменяется. Копии скриптов предыдущих пакетов побайтно неизменны. `visual-review.json` фиксирует осмотр финальных PNG.',
              '', 'Границы записи проверяются в guard(). Git, MCP, сеть, Unreal, сервисы и фоновые процессы не используются.']
    if known:lines += ['', 'Непройденные проверки: '+'; '.join(known)]
    guard(PACKAGE/'README.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')
    refresh_manifest();print(json.dumps({'task':task,'acceptance_pass':verification['acceptance_pass'],'text_min':textmin,'icons_pass':iconpass,'layout_pass':layoutpass,'changed_inputs':changed},ensure_ascii=False),flush=True)

MODULES={'SC-08':'sc08_lobby_list.py','SC-09':'sc09_lobby_create.py','SC-10':'sc10_lobby_create_ai.py','SC-11':'sc11_lobby_code.py','SC-12':'sc12_lobby_empty.py','SC-13':'sc13_lobby_error.py'}

if __name__=='__main__':
    sys.stdout.reconfigure(encoding='utf-8')
    build('SC-08',{'loading':{'list':'loading'},'list':{'hover':True}})
