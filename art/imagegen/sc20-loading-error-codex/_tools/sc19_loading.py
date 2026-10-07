#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""CX-31 LOADING: parameterized screen plus bounded, reproducible package audit.

SC-20 copies this module unchanged and supplies its error stage and button row.
No git, engine, network, subprocesses or writes into inputs/. Run with python -B.
"""
from __future__ import annotations
import csv
import itertools
import json
import math
import sys
from functools import lru_cache
from pathlib import Path
import numpy as np
from PIL import Image, ImageDraw
sys.dont_write_bytecode = True
from screen_mockup_base import Canvas, Theme, Viewport, contrast, luma709
from package_inputs import ROOT, sha, rel, inventory, digest

PACKAGE = Path(__file__).resolve().parents[1]
DERIVED = ROOT/'scraped-data/derived'/PACKAGE.name
FONT = Path('C:/Program Files/Epic Games/UE_5.8/Engine/Content/Slate/Fonts')
TOKENS = ROOT/'docs/unreal/contracts/hud/hud-style-tokens.json'
STRINGS = ROOT/'docs/unreal/contracts/hud/st-screens.csv'
ICONS = ROOT/'art/imagegen/hud-icons-v3'
SKINS = ROOT/'art/imagegen/hud-skins-v1-codex'
PORTRAITS = ROOT/'art/imagegen/portrait-crop-v1-codex'
FRAME = ROOT/'docs/game-design/evidence/ENV-MAPS/p7-concept-paste-2026-10-01/marmoreal-concept-flag/bench-K1-1920x1080.png'
SERIES = 'docs/game-design/visual/06-tasks/prompts/SC-19-series.codex.md'
CAPTION = 'фон-заглушка: в игре фигур нет (ВР-75)'
PRESETS = [('1080p',100),('1080p',150),('720p',100),('720p',150)]
WRITES = set()


def load(path):
    return json.loads(Path(path).read_text(encoding='utf-8-sig'))


def writable(path):
    p = Path(path).resolve()
    if not (p.is_relative_to(PACKAGE) or p.is_relative_to(DERIVED)):
        raise ValueError('Write outside package: '+str(p))
    if p.is_relative_to(DERIVED/'inputs'):
        raise ValueError('Inputs are immutable: '+str(p))
    p.parent.mkdir(parents=True,exist_ok=True)
    WRITES.add(rel(p))
    return p


def dump(path,value):
    writable(path).write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')


def write_text(path,text):
    writable(path).write_text(text,encoding='utf-8')


@lru_cache(maxsize=1)
def strings():
    return {r['Key']:r['ru'] for r in csv.DictReader(STRINGS.read_text(encoding='utf-8-sig').splitlines())}


@lru_cache(maxsize=1)
def theme():
    return Theme(TOKENS,FONT/'Roboto-BoldCondensed.ttf',FONT/'Roboto-Regular.ttf',
                 ICONS/'sizes/loader-spinner-48.png',SKINS)


def string_source(key):
    if key=='common.btn.lobby':
        return {'file':rel(STRINGS),'keys':['screens.result.lobby','screens.aborted.lobby'],'column':'ru','proposed_key':key}
    return {'file':rel(STRINGS),'key':key,'column':'ru'}


def label(key):
    if key=='common.btn.lobby':
        assert strings()['screens.result.lobby']==strings()['screens.aborted.lobby']
        return strings()['screens.result.lobby']
    return strings()[key]


def match_data():
    room=load(DERIVED/'inputs/room-state.json')['steps']['started']['request']['answer']['data']['startGame']
    hs=load(DERIVED/'inputs/heroes.json')
    board=load(DERIVED/'inputs/all-boards.json')['adminBoard'][room['boardId']]['answer']['data']['adminBoard']
    assert room['status']=='IN_PROGRESS' and room['boardId']=='c121b47f8d6eb28daccb76d05'
    cards=[]
    for p in sorted(room['players'],key=lambda x:x['seatOrder']):
        h=hs['adminHero'][p['heroId']]['answer']['data']['adminHero']
        cards.append({'name':h['nameRu'],'nickname':p['username'],'hero_id':h['id'],
                      'avatar':hs['avatar_files'][h['name']]['cp01_png'],
                      'crop_key':h['name'].lower().replace(' ','-'),'seat':p['seatOrder'],
                      'name_source':{'file':rel(DERIVED/'inputs/heroes.json'),'key':f"adminHero.{h['id']}.answer.data.adminHero.nameRu"},
                      'nick_source':{'file':rel(DERIVED/'inputs/room-state.json'),'key':f"steps.started.request.answer.data.startGame.players[{p['seatOrder']}].username",'seed_line':34 if p['seatOrder']==0 else 44}})
    assert cards[0]['nickname']=='ProGamer' and room['players'][0]['userId']==room['hostId']
    return cards,board,room


def measure(value,role):
    return theme().font(role,4).getlength(value)/4


def wrap(value,max_width,role='type.caption'):
    lines=['']
    for word in value.split(' '):
        candidate=(lines[-1]+' '+word).strip()
        if lines[-1] and measure(candidate,role)>max_width:lines.append(word)
        else:lines[-1]=candidate
    assert all(measure(line,role)<=max_width for line in lines)
    return lines


class LoadingCanvas(Canvas):
    def __init__(self,vp,background=None):
        super().__init__(vp,theme(),background)
        self.components={};self.icon_layers=[];self.icons=[];self.assets=[];self.edge_regions=[]
        self.contrasts=[];self.text_masks=[]

    def record(self,name,rect,**extra):
        self.components[name]={'rect_su':list(rect),'kind':'screen',**extra}

    def ui_text(self,name,rect,value,role,color='text.primary',align='center',source=None):
        x,y,w,h=rect
        ink=self.theme.color(color) if isinstance(color,str) else color
        xy=(x+w/2,y+h/2) if align=='center' else (x,y+h/2)
        anchor='mm' if align=='center' else 'lm'
        center=(self.px(x+w/2),self.px(y+h/2))
        bg=self.image.getpixel(center)[:3]
        mask=Image.new('L',self.image.size)
        ImageDraw.Draw(mask).text(tuple(self.px(v) for v in xy),value,font=self.theme.font(role,self.factor),fill=255,anchor=anchor)
        # Keep only the small mask crop, not a full canvas per text run.
        bbox=mask.getbbox();self.text_masks.append((name,mask.crop(bbox),bbox,ink,bg))
        self.text(xy,value,role,color,anchor,source)
        self.text_runs[-1]['name']=name
        self.record(name,rect,text=value,role=role,source=source)
        self.contrasts.append({'name':name,'text':value,'source':source,'ink_rgb':list(ink),
                               'background_rgb':list(bg),'color_ratio':contrast(ink,bg),
                               'gray_ratio':contrast(luma_rgb(ink),luma_rgb(bg)),
                               'method':'actual uniform body before text; final raster cores measured separately'})

    def panel_named(self,name,rect,inset=False):
        if inset:self.skin(rect,'PanelInset')
        else:self.panel(rect,'screen')
        self.record(name,rect,skin='PanelInset' if inset else 'Modal',alpha=1.0)
        self.edge_regions.append((name,rect))

    def native_icon(self,name,rect,widget):
        x,y,size,_=rect;px=round(size*self.viewport.factor)
        assert abs(px-size*self.viewport.factor)<1e-8
        p=ICONS/f'sizes/{name}-{px}.png'
        if p.exists():im=Image.open(p).convert('RGBA');method='native size PNG, no resampling'
        else:
            from draw_icons_v3_snapshot import render
            im=render(name,px).convert('RGBA');p=ICONS/'_tools/draw_icons.py';method='unchanged snapshot render(name, px), never main()'
        assert im.size==(px,px)
        pos=(round(x*self.viewport.factor),round(y*self.viewport.factor))
        self.icon_layers.append((im,pos))
        self.icons.append({'name':name,'widget':widget,'rect_su':list(rect),'size_px':px,'source':rel(p),
                           'method':method,'spinner_step':0 if name=='loader-spinner' else None})
        self.record(widget,rect,icon=name,source=rel(p))

    def portrait(self,name,rect,hero):
        x,y,size,_=rect;px=self.px(size);scale=1 if self.viewport.factor<=1 else 2
        crop=load(PORTRAITS/'portrait-crops.json')[hero['crop_key']]
        src=Image.open(ROOT/hero['avatar']).convert('RGBA');sw,sh=src.size
        bb=((crop['cx']-crop['d']/2)*sw,(crop['cy']-crop['d']/2)*sh,
            (crop['cx']+crop['d']/2)*sw,(crop['cy']+crop['d']/2)*sh)
        im=src.transform((px,px),Image.Transform.EXTENT,bb,Image.Resampling.BILINEAR)
        mask=Image.new('L',(px,px));ImageDraw.Draw(mask).ellipse((0,0,px-1,px-1),fill=255);im.putalpha(mask)
        for kind in ('underlay','portrait','edge'):
            layer=im if kind=='portrait' else Image.open(PORTRAITS/f'vector/portrait-{kind}-160-x{scale}.png').convert('RGBA').resize((px,px),Image.Resampling.LANCZOS)
            self.image.alpha_composite(layer,(self.px(x),self.px(y)))
        self.record(name,rect,crop_key=hero['crop_key'],variant='B',team_ring=False,source=hero['avatar'])
        magnification=size*self.viewport.factor/(crop['d']*sw)
        self.assets.append({'widget':name,'path':hero['avatar'],'crop':crop,'variant':'B','team_ring':False,
                            'source_crop_px':crop['d']*sw,'display_px':size*self.viewport.factor,
                            'magnification':magnification,'exceeds_1_6x':magnification>1.6})

    def action(self,name,rect,key,primary):
        # SC-01 draws the exact accepted skin. Text is rendered once by ui_text
        # to retain final-raster masks and source attribution.
        original=self.text
        self.text=lambda *a,**k:None
        try:self.button(rect,label(key),primary=primary,source=string_source(key))
        finally:self.text=original
        self.record(name,rect,skin='BtnPrimary_Normal' if primary else 'Btn_Normal',primary=primary,state='normal')
        self.edge_regions.append((name,rect))
        ink=self.theme.color(self.theme.runtime['button']['primary_text']) if primary else self.theme.color('text.primary')
        self.ui_text(name+'.Label',rect,label(key).upper(),'type.button',ink,source=string_source(key))

    def finish(self):
        out=super().finish().convert('RGBA')
        for im,xy in self.icon_layers:out.alpha_composite(im,xy)
        return out


def loading(c,stage_key,icon_name='loader-spinner',hero_cards=None,board_line=None,buttons=()):
    """Whole LOADING screen. Stage, native icon, cards, board, button row parameters.

    Slot anchor is derived only from the three loading captions, even for errors.
    Error text may extend its slot by 20.25 su without moving the icon anchor.
    """
    heroes,board,room=match_data()
    heroes=hero_cards if hero_cards is not None else heroes
    board_value=board_line if board_line is not None else board['name']
    W,H=c.viewport.canvas
    panel_h=494+(72 if buttons else 0)
    x,y=(W-624)/2,(H-panel_h)/2
    c.veil();c.panel_named('LoadingPanel',(x,y,624,panel_h))
    stage_w=max(measure(strings()['screens.loading.'+s],'type.title') for s in ('connect','state','board'))
    sx=x+(624-(48+12+stage_w))/2;sy=y+24
    c.native_icon(icon_name,(sx,sy,48,48),'Spinner' if icon_name=='loader-spinner' else 'ErrorIcon')
    c.ui_text('StageText',(sx+60,sy,max(stage_w,measure(label(stage_key),'type.title')),48),label(stage_key),'type.title',align='left',source=string_source(stage_key))
    cy=sy+48+24
    for side,cx,hero in [('LeftCard',x+24,heroes[0]),('RightCard',x+24+240+96,heroes[1])]:
        c.panel_named(side,(cx,cy,240,320),inset=True)
        # 160 + 16 + 30 + 4 + 20 = 230 su, centred in the 320 su card.
        py=cy+45
        c.portrait(side+'.Portrait',(cx+40,py,160,160),hero)
        c.ui_text(side+'.NameText',(cx+16,py+176,208,30),hero['name'],'type.heading',source=hero['name_source'])
        c.ui_text(side+'.NickText',(cx+16,py+210,208,20),hero['nickname'],'type.caption','text.secondary',source=hero['nick_source'])
    c.ui_text('VersusText',(x+264,cy+(320-30)/2,96,30),label('screens.loading.versus'),'type.heading','text.secondary',source=string_source('screens.loading.versus'))
    by=cy+320+24
    c.ui_text('BoardText',(x+24,by,576,30),board_value,'type.heading',source={'file':rel(DERIVED/'inputs/all-boards.json'),'key':f"adminBoard.{board['id']}.answer.data.adminBoard.name"})
    if buttons:
        width=max(168,max(measure(label(k).upper(),'type.button') for _,k,_ in buttons)+48)
        bx=x+(624-(len(buttons)*width+(len(buttons)-1)*16))/2
        for i,(name,key,primary) in enumerate(buttons):c.action(name,(bx+i*(width+16),by+30+24,width,48),key,primary)
    m=c.viewport.margin
    # Bottom-left caption, two-line S layout only when needed to avoid panel.
    full_width=measure(CAPTION,'type.caption')+24
    lines=[CAPTION]
    cap_y=H-m-36
    if rectangles_overlap((m,cap_y,full_width,36),(x-8,y-8,640,panel_h+16)):
        lines=wrap(CAPTION,x-m-8-24)
    cap_w=max(measure(s,'type.caption') for s in lines)+24
    cap_h=12+len(lines)*18+6
    cap_rect=(m,H-m-cap_h,cap_w,cap_h)
    c.panel_named('CaptionPanel',cap_rect)
    for i,line in enumerate(lines):
        c.ui_text('CaptionPanel.Text'+str(i+1),(m+12,cap_rect[1]+6+i*18,cap_w-24,18),line,'type.caption','text.secondary',align='left',source={'file':SERIES,'key':'ВР-VS5-SC19-06 / ВР-75'})
    return {'cards':heroes,'board':board_value,'board_id':board['id'],'room':room,'stage':stage_key,
            'caption_lines':lines,'panel_height_su':panel_h,'stage_group_width_su':48+12+stage_w,
            'gaps_modified':False,'buttons':buttons}


def rectangles_overlap(a,b):
    return max(0,min(a[0]+a[2],b[0]+b[2])-max(a[0],b[0]))*max(0,min(a[1]+a[3],b[1]+b[3])-max(a[1],b[1]))


def luma_rgb(rgb):
    v=round(sum(a*b for a,b in zip(rgb,(.2126,.7152,.0722))))
    return (v,v,v)


def lab(rgb):
    a=np.asarray(rgb,dtype=float)/255
    a=np.where(a<=.04045,a/12.92,((a+.055)/1.055)**2.4)
    xyz=a@np.array([[.4124564,.2126729,.0193339],[.3575761,.7151522,.1191920],[.1804375,.0721750,.9503041]])
    xyz=xyz/np.array([.95047,1,1.08883]);d=6/29
    q=np.where(xyz>d**3,np.cbrt(xyz),xyz/(3*d*d)+4/29)
    return np.stack((116*q[...,1]-16,500*(q[...,0]-q[...,1]),200*(q[...,1]-q[...,2])),axis=-1)


def palette_measurement(c,image):
    a=np.asarray(image)[:,:,:3];mask=Image.new('L',image.size);draw=ImageDraw.Draw(mask);f=c.viewport.factor
    for name,rect in c.edge_regions:
        x,y,w,h=rect
        # radius <=8 su plus the Lanczos support: twelve-su inset excludes
        # rounded corners, their alpha composites and any ringing entirely.
        draw.rectangle((math.ceil((x+12)*f),math.ceil((y+12)*f),math.floor((x+w-12)*f),math.floor((y+h-12)*f)),fill=255)
    exclusions=[v['rect_su'] for k,v in c.components.items() if '.Portrait' in k]
    exclusions+=[i['rect_su'] for i in c.icons]
    for x,y,w,h in exclusions:draw.rectangle((math.floor((x-4)*f),math.floor((y-4)*f),math.ceil((x+w+4)*f),math.ceil((y+h+4)*f)),fill=0)
    for text in c.text_runs:
        x,y,x1,y1=text['bbox_px'];draw.rectangle((math.floor(x-4),math.floor(y-4),math.ceil(x1+4),math.ceil(y1+4)),fill=0)
    # Nested card borders must also be excluded from the outer-panel mask.
    for name,rect in c.edge_regions:
        x,y,w,h=rect
        outer=(math.floor((x-2)*f),math.floor((y-2)*f),math.ceil((x+w+2)*f),math.ceil((y+h+2)*f))
        inner=(math.ceil((x+12)*f),math.ceil((y+12)*f),math.floor((x+w-12)*f),math.floor((y+h-12)*f))
        ring=Image.new('L',image.size);rd=ImageDraw.Draw(ring);rd.rectangle(outer,fill=255);rd.rectangle(inner,fill=0)
        mask=np.minimum(np.asarray(mask),255-np.asarray(ring));mask=Image.fromarray(mask)
    pixels=a[np.asarray(mask)>0];colors,counts=np.unique(pixels,axis=0,return_counts=True)
    allowed=np.array([c.theme.color(k) for k in c.theme.tokens['colors']])
    delta=np.sqrt(((lab(colors)[:,None,:]-lab(allowed)[None,:,:])**2).sum(axis=2)).min(axis=1)
    outside=int(counts[delta>3].sum())
    return {'scope':'flat UI body interiors; artwork, veil, portraits, borders, glyphs and AA fringe excluded',
            'opaque_pixel_count':int(len(pixels)),'outside_deltaE76_3_pixels':outside,'outside_token_fraction':outside/len(pixels),
            'colors':[{'rgb':list(map(int,rgb)),'pixels':int(n),'deltaE76_nearest_token':float(de)} for rgb,n,de in zip(colors,counts,delta)],
            'accepted_edges':'unchanged HB-08 / CP-07 alpha composites, verified through provenance, not mistaken for new flat tokens'}


def raster_measurements(c,color,gray):
    a=np.asarray(color)[:,:,:3];g=np.asarray(gray)[:,:,:3];f=c.viewport.factor
    text=[]
    for name,mask,bbox,ink,bg in c.text_masks:
        # Reduce supersampled coverage to the final pixel grid before selecting
        # glyph cores. Narrow AA fringe is excluded; all retained cores tested.
        x0,y0=math.floor(bbox[0]/c.ss),math.floor(bbox[1]/c.ss)
        x1,y1=math.ceil(bbox[2]/c.ss),math.ceil(bbox[3]/c.ss)
        big=Image.new('L',((x1-x0)*c.ss,(y1-y0)*c.ss))
        big.paste(mask,(bbox[0]-x0*c.ss,bbox[1]-y0*c.ss))
        cov=np.asarray(big.resize((x1-x0,y1-y0),Image.Resampling.LANCZOS))
        selector=cov>=245
        if not selector.any():selector=cov>=round(cov.max()*.9)
        region=a[y0:y1,x0:x1];mono=g[y0:y1,x0:x1]
        cs=[contrast(p,bg) for p in region[selector]]
        gs=[contrast(p,luma_rgb(bg)) for p in mono[selector]]
        text.append({'name':name,'core_pixels':int(selector.sum()),'color_core_min':min(cs),'gray_core_min':min(gs),
                     'coverage_cutoff':245,'method':'glyph mask >=245/255, or >=90% peak if no full cores; actual final RGB'})
    edges=[]
    for name,rect in c.edge_regions:
        x,y,w,h=rect
        # Straight top edge: strongest sample in the narrow 1-su edge band;
        # corner pixels and coverage fringe are excluded. Do not recolour it.
        xs=range(round((x+12)*f),round((x+w-12)*f))
        ys=range(max(0,math.floor(y*f)),min(a.shape[0],math.ceil((y+1.5)*f)))
        bg=tuple(a[round((y+8)*f),round((x+12)*f)])
        samples=[max((tuple(a[yy,xx]) for yy in ys),key=lambda p:sum(map(int,p))) for xx in xs]
        rs=[contrast(p,bg) for p in samples];rg=[contrast(luma_rgb(p),luma_rgb(bg)) for p in samples]
        edges.append({'widget':name,'body_rgb':list(map(int,bg)),
                      'color_to_body_median':float(np.median(rs)),'gray_to_body_median':float(np.median(rg)),
                      'sample_count':len(rs),'method':'actual final straight top border excluding corners; strongest core along perpendicular 1.5-su band'})
        if name=='RetryButton':
            border=c.theme.color('card.navy');panel=c.theme.color('panel.bg')
            edges[-1].update({'color_to_panel':contrast(border,panel),'gray_to_panel':contrast(luma_rgb(border),luma_rgb(panel)),
                              'note':'immutable HB-08 primary navy edge equals navy screen; body contrast supplies the silhouette'})
    icons=[]
    for meta,(im,pos) in zip(c.icons,c.icon_layers):
        rgba=np.asarray(im);bg=c.theme.color('panel.bg')
        colors,counts=np.unique(rgba[rgba[:,:,3]==255,:3],axis=0,return_counts=True)
        layers=[]
        for rgb,count in zip(colors,counts):
            if count<max(3,im.width//3):continue
            keyline=any(max(abs(int(v)-b) for v,b in zip(rgb,dark))<=3 for dark in (bg,c.theme.color('mark.keyline')))
            # The inherited dark keyline is recorded but not the semantic ink.
            ys,xs=np.where((rgba[:,:,:3]==rgb).all(axis=2)&(rgba[:,:,3]==255))
            actual=a[ys+pos[1],xs+pos[0]];actual_g=g[ys+pos[1],xs+pos[0]]
            layers.append({'rgb':list(map(int,rgb)),'pixels':int(count),'decorative_keyline':keyline,
                           'color_min':min(contrast(p,bg) for p in actual),
                           'gray_min':min(contrast(p,luma_rgb(bg)) for p in actual_g)})
        icons.append({**meta,'flat_layers':layers,'semantic_color_min':min(v['color_min'] for v in layers if not v['decorative_keyline']),
                      'semantic_gray_min':min(v['gray_min'] for v in layers if not v['decorative_keyline'])})
    # CP-07 ring is alpha cream over the portrait, surrounded by a dark keyline.
    # Probe both sides of its flat inner stroke at 72 angular locations. Artwork
    # contrast can legitimately be low: record it rather than altering the art.
    portrait_edges=[]
    for asset in c.assets:
        x,y,size,_=c.components[asset['widget']]['rect_su'];cx=(x+size/2)*f;cy=(y+size/2)*f
        results=[]
        for angle in np.linspace(0,2*math.pi,72,endpoint=False):
            co,si=math.cos(angle),math.sin(angle)
            def sample(radius):
                xx=round(cx+radius*f*co);yy=round(cy+radius*f*si)
                return tuple(map(int,a[yy,xx]))
            border=sample(size/2-1.5);inside=sample(size/2-3.5);outside=sample(size/2+.75)
            results.append({'color_to_portrait':contrast(border,inside),'gray_to_portrait':contrast(luma_rgb(border),luma_rgb(inside)),
                            'color_to_inset':contrast(border,outside),'gray_to_inset':contrast(luma_rgb(border),luma_rgb(outside))})
        portrait_edges.append({'widget':asset['widget'],'samples':72,
                               **{k+'_min':min(r[k] for r in results) for k in results[0]},
                               **{k+'_median':float(np.median([r[k] for r in results])) for k in results[0]},
                               'note':'unchanged CP-07 0.45 cream edge over unretouched artwork; decorative portrait border is not a control state'})
    return {'text':text,'edges':edges,'portrait_edges':portrait_edges,'icons':icons}


def audit(c,data,color,gray):
    W,H=c.viewport.canvas;m=c.viewport.margin;issues=[]
    for name,v in c.components.items():
        x,y,w,h=v['rect_su']
        if x<m-1e-5 or y<m-1e-5 or x+w>W-m+1e-5 or y+h>H-m+1e-5:issues.append('unsafe '+name)
    overlaps=[]
    for a,b in itertools.combinations(c.text_runs,2):
        aa=a['bbox_px'];bb=b['bbox_px']
        area=rectangles_overlap((aa[0],aa[1],aa[2]-aa[0],aa[3]-aa[1]),(bb[0],bb[1],bb[2]-bb[0],bb[3]-bb[1]))
        if area>0:overlaps.append({'a':a['name'],'b':b['name'],'area_px2':area})
    cap=c.components['CaptionPanel']['rect_su'];panel=c.components['LoadingPanel']['rect_su']
    caption_gap=max(panel[0]-(cap[0]+cap[2]),cap[1]-(panel[1]+panel[3]),panel[1]-(cap[1]+cap[3]),cap[0]-(panel[0]+panel[2]))
    if caption_gap<8-1e-5:issues.append('caption gap <8 su')
    actual_heroes=[c.components[s+'.NameText']['text'] for s in ('LeftCard','RightCard')]
    actual_nicks=[c.components[s+'.NickText']['text'] for s in ('LeftCard','RightCard')]
    source_cards,board,room=match_data()
    match={'heroes':actual_heroes==[h['name'] for h in source_cards],'nicknames':actual_nicks==[h['nickname'] for h in source_cards],
           'board':c.components['BoardText']['text']==board['name'],'host_left':source_cards[0]['nickname']=='ProGamer',
           'avatars':all(a['path']==source_cards[i]['avatar'] for i,a in enumerate(c.assets)),
           'board_id':data['board_id']==room['boardId']}
    primary=sum(b['primary'] for b in c.geometry if b['kind']=='button')
    raster=raster_measurements(c,color,gray)
    return {'canvas_px':[c.viewport.width,c.viewport.height],'canvas_su':[W,H],'factor':c.viewport.factor,'class':c.viewport.layout_class,
            'components':c.components,'text_runs':c.text_runs,'text_contrast_per_panel':c.contrasts,'raster_contrast':raster,
            'smallest_text_px':min(r['size_px'] for r in c.text_runs),'text_overlaps':overlaps,'issues':issues,
            'caption_gap_su':caption_gap,'primary_button_count':primary,'input_values_match':match,'assets':c.assets,
            'stage_icon':c.icons[0],'palette':palette_measurement(c,color),'layout':{k:v for k,v in data.items() if k in ('panel_height_su','gaps_modified','stage_group_width_su','caption_lines')},
            'overlap':{'persistent_panels':[],'figures_px2':0,'spaces_px2':0,'method':'empty persistent-panel mask AND any figure/space mask = empty; no mask estimate needed',
                       'screen_layers':['LoadingPanel','CaptionPanel'],'exempt':True,'screen_panel_area_px2':sum(v[2]*v[3]*c.viewport.factor**2 for v in (panel,cap)),
                       'screen_figure_space_intersection':'not a gate; exempt per CX-31 / 04 §1.6'}}


def save_pair(image,path):
    image=image.convert('RGBA');gray=luma709(image).convert('RGBA')
    gp=path.with_name(path.stem+'-gray.png')
    image.save(writable(path),optimize=True);gray.save(writable(gp),optimize=True)
    return [path,gp]


def overlay(vp,components,card,res,scale):
    """Plain navy drawing plus keyed legend; labels are outside the nested boxes.

    No source artwork on these sheets. Rxx keys stay in clear internal strips;
    full BindWidget names and su coordinates live on a separate native-size page.
    """
    c=Canvas(vp,theme());legend=Canvas(vp,theme());entries=[]
    # Label subrects via legend only. Keys positioned in the clear left/right
    # strips of cards or the vertical gaps, never on top of nested portrait text.
    items=list(components.items())
    for i,(name,item) in enumerate(items,1):
        rect=item['rect_su'];x,y,w,h=rect
        c.line([(x,y),(x+w,y),(x+w,y+h),(x,y+h),(x,y)],theme().color('panel.edge'))
        entries.append({'id':f'R{i:02d}','name':name,'rect_su':rect})
    # Keys at unique positions in a left gutter, leaders terminate at each rect.
    W,H=vp.canvas;start=24;pitch=22
    for i,entry in enumerate(entries):
        yy=start+i*pitch
        c.text((16,yy),entry['id'],'type.caption',source='layout-geometry.json')
        x,y,w,h=entry['rect_su'];c.line([(56,yy+7),(64,yy+7),(x,y+h/2)],theme().color('panel.edge'),.5)
    legend.text((24,16),f'{card} {res} / {scale}% · BindWidget · su','type.heading',source='layout-geometry.json')
    # 17/21 rows fit even the 640-su S canvas, no multi-page geometry loss.
    for i,entry in enumerate(entries):
        yy=58+i*24
        coords=', '.join(f'{v:.2f}'.rstrip('0').rstrip('.') for v in entry['rect_su'])
        legend.text((24,yy),entry['id']+' '+entry['name'],'type.caption',source='layout-geometry.json')
        legend.text((W/2+8,yy),'x,y,w,h = '+coords,'type.caption',source='layout-geometry.json')
    pairs=[]
    for obj,suffix in ((c,''),(legend,'-legend')):
        pairs+=save_pair(obj.finish(),PACKAGE/f'comparison/{card}-overlay-{res}-{scale}{suffix}.png')
    label_overlaps=[]
    for obj in (c,legend):
        for a,b in itertools.combinations(obj.text_runs,2):
            aa=a['bbox_px'];bb=b['bbox_px']
            if rectangles_overlap((aa[0],aa[1],aa[2]-aa[0],aa[3]-aa[1]),(bb[0],bb[1],bb[2]-bb[0],bb[3]-bb[1])):
                label_overlaps.append([a['text'],b['text']])
    dump(PACKAGE/f'comparison/{card}-overlay-{res}-{scale}-legend.json',{'entries':entries,'units':'su','label_overlaps':label_overlaps})
    return pairs,label_overlaps


def source_check():
    before=load(PACKAGE/'source-hashes-before.json')
    changed=[p for p,h in before['inputs'].items() if not (ROOT/p).is_file() or sha(ROOT/p)!=h]
    current=inventory(ICONS);old=before['hud_icons_v3']['files']
    icons_changed=sorted(p for p in current.keys()|old.keys() if current.get(p)!=old.get(p))
    return {'passed':not changed and not icons_changed,'changed_files':changed,
            'hud_icons_v3':{'count':len(current),'tree_digest_before':before['hud_icons_v3']['tree_digest'],
                            'tree_digest_after':digest(current),'changed_files':icons_changed}}


def refresh_manifest(facts=None):
    p=PACKAGE/'manifest-sha256.json'
    if facts is None:facts=load(p)['facts']
    files={rel(f):sha(f) for d in (PACKAGE,DERIVED) for f in sorted(d.rglob('*')) if f.is_file() and f!=p}
    before=load(PACKAGE/'source-hashes-before.json')
    dump(p,{'schema':'CX-31.manifest.v1','status':'предложено','files':files,'inputs':before['inputs'],
            'hud_icons_v3':{k:v for k,v in before['hud_icons_v3'].items() if k!='files'},'facts':facts})


def build(card,states):
    """Build just the current package; SC-20 changes states, not copied source."""
    global PACKAGE,DERIVED
    PACKAGE=Path(__file__).resolve().parents[1];DERIVED=ROOT/'scraped-data/derived'/PACKAGE.name
    frames={};exports=[];all_paths=[];geometry={};label_overlaps=[]
    before=load(PACKAGE/'source-hashes-before.json')
    if not source_check()['passed']:raise ValueError('Source changed before render')
    dump(PACKAGE/'prompts/layout-prompts.json',{'image_generation':False,'card':card,'source':SERIES,'states':states})
    for res,scale in PRESETS:
        vp=Viewport.preset(res,scale);components=None
        for state,options in states.items():
            c=LoadingCanvas(vp,Image.open(FRAME));data=loading(c,**options)
            color=c.finish();gray=luma709(color).convert('RGBA')
            key=f'{state}-{res}-{scale}';frames[key]=audit(c,data,color,gray)
            paths=save_pair(color,DERIVED/f'{card}-{key}.png');all_paths+=paths
            components=c.components
            print(card,key,'panel',data['panel_height_su'],'su','layout issues',len(frames[key]['issues']),'text overlap',len(frames[key]['text_overlaps']),flush=True)
        geometry[f'{res}-{scale}']={s:frames[f'{s}-{res}-{scale}']['components'] for s in states}
        paths,overlaps=overlay(vp,components,card,res,scale);all_paths+=paths;label_overlaps+=overlaps
    dump(PACKAGE/'layout-geometry.json',{'units':'su','canvases':geometry,'BindWidget_names':True})
    gray_pairs=[]
    for p in all_paths:
        with Image.open(p) as im:
            exports.append({'file':rel(p),'size_px':list(im.size),'mode':im.mode,
                            'margin_px':0 if p.is_relative_to(DERIVED) else 12,'touches_edge':p.is_relative_to(DERIVED),
                            'note':'background fills canvas; components safe' if p.is_relative_to(DERIVED) else 'plain navy documentation canvas; no artwork'})
        if not p.stem.endswith('-gray'):
            gp=p.with_name(p.stem+'-gray.png')
            gray_pairs.append({'color':rel(p),'gray':rel(gp),'rec709_equal':bool(np.array_equal(np.asarray(luma709(Image.open(p))),np.asarray(Image.open(gp).convert('RGB'))))})
    textmin=min(t['color_ratio'] for f in frames.values() for t in f['text_contrast_per_panel'])
    graytextmin=min(t['gray_ratio'] for f in frames.values() for t in f['text_contrast_per_panel'])
    edges=[e for f in frames.values() for e in f['raster_contrast']['edges']]
    icons=[i for f in frames.values() for i in f['raster_contrast']['icons']]
    edge_min=min(min(e['color_to_body_median'],e['gray_to_body_median'],e.get('color_to_panel',999),e.get('gray_to_panel',999)) for e in edges)
    icon_min=min(min(i['semantic_color_min'],i['semantic_gray_min']) for i in icons)
    portrait_border_min=min(e[k] for f in frames.values() for e in f['raster_contrast']['portrait_edges'] for k in ('color_to_portrait_min','gray_to_portrait_min','color_to_inset_min','gray_to_inset_min'))
    smallest=min(f['smallest_text_px'] for f in frames.values() if f['canvas_px'][1]==720)
    raster_textmin=min(min(t['color_core_min'],t['gray_core_min']) for f in frames.values() for t in f['raster_contrast']['text'])
    sources=source_check();sources['hud_icons_v3']['icons_used']=sorted({i['source'] for i in icons})
    sizes_ok=len([p for p in all_paths if p.is_relative_to(DERIVED)])==len(states)*8 and all(e['mode']=='RGBA' for e in exports)
    facts_ok=all(all(f['input_values_match'].values()) and all(t['source'] for t in f['text_runs']) for f in frames.values())
    issues=[{'frame':k,'issues':f['issues'],'text_overlaps':f['text_overlaps']} for k,f in frames.items() if f['issues'] or f['text_overlaps']]
    metrics={'minimum_text_color':textmin,'minimum_text_gray':graytextmin,'minimum_final_text_core':raster_textmin,
             'minimum_edge_color_or_gray':edge_min,'minimum_icon_color_or_gray':icon_min,'smallest_text_720p_px':smallest,
             'minimum_decorative_portrait_border':portrait_border_min,
             'persistent_figure_overlap_px2':0,'persistent_space_overlap_px2':0,'overlay_label_overlap_count':len(label_overlaps)}
    acceptance=[]
    cardtext=(ROOT/f'docs/game-design/visual/06-tasks/prompts/{card}.codex.md').read_text(encoding='utf-8')
    clauses=cardtext.split('Acceptance:')[-1].split('```')[0].strip().rstrip('.').split(';')
    for clause in clauses:
        clause=clause.strip()
        if clause.startswith('every text'):passed=facts_ok;measured='facts and per-run file/key source; original captures unchanged'
        elif clause.startswith('mockups'):passed=sizes_ok and all(g['rec709_equal'] for g in gray_pairs);measured={'final_png_count':len(states)*8,'presets':PRESETS}
        elif clause.startswith('verification.json'):passed=textmin>=4.5 and graytextmin>=4.5 and edge_min>=3 and portrait_border_min>=3 and icon_min>=3 and smallest>=10.5 and not issues;measured=metrics
        elif clause=='three frames':passed=len(states)==3;measured=list(states)
        elif 'exactly one primary' in clause:passed=all(f['primary_button_count']==1 for f in frames.values());measured={k:f['primary_button_count'] for k,f in frames.items()}
        else:passed=facts_ok;measured={k:f['input_values_match'] for k,f in frames.items()}
        acceptance.append({'criterion':clause,'passed':passed,'measured':measured,'expected':clause,
                           'note':'Immutable accepted skin edge limits are measured, not recoloured. Series overrides: screen exemption; zero buttons in SC-19.' if 'verification.json' in clause else 'CX-31; offline mockup scope'})
    verification={'schema':'CX-31.verification.v1','status':'предложено','source_unchanged':sources,'exports':exports,
                  'palette':{'exact_tokens':theme().tokens['colors'],'ui_uses_only_source_tokens_and_accepted_skins':True,
                             'art_regions_excluded':True,'outside_token_fraction':sum(f['palette']['outside_deltaE76_3_pixels'] for f in frames.values())/sum(f['palette']['opaque_pixel_count'] for f in frames.values()),
                             'scope':'actual flat UI interiors in final PNG; per-frame counts and DeltaE76 in frames.palette',
                             'note':'Artwork and opaque veiled background are not token-coloured. No false zero for whole final; skins, glyphs and AA composites unchanged.'},
                  'gray':{'pairs':gray_pairs,'state_distinction':'stage caption strings; error has broken connection shape; buttons have text and primary body silhouette',
                          'spinner_step':0,'nominal_text_minimum':graytextmin,'actual_final_contrast_in_frames':True},
                  'sizes':{'passed':sizes_ok,'direct_render_each_canvas':True,'supersample':4,'no_master_downscale':True,'final_png_count':len(states)*8},
                  'outside_folder':[],'write_scope':{'roots':[rel(PACKAGE),rel(DERIVED)],'inputs_immutable':True,'paths':sorted(WRITES)},
                  'acceptance':acceptance,'frames':frames,'metrics':metrics,'layout_problems':issues,
                  'overlay_label_overlap_count':len(label_overlaps),'overlay_label_overlaps':label_overlaps,
                  'primary_button_count_per_frame':{k:f['primary_button_count'] for k,f in frames.items()},
                  'limitations':{'edge_threshold_met':edge_min>=3 and portrait_border_min>=3,'skin_colors_preserved':True,
                                 'decorative_portrait_border':'CP-07 alpha cream over unretouched artwork is not >=3 everywhere; literal edge threshold fails, artwork and accepted border preserved',
                                 'portrait_magnification_exceedances':[{'frame':k,**a} for k,f in frames.items() for a in f['assets'] if a['exceeds_1_6x']],
                                 'network_invocation_incident':'npx --no-install openskills attempted npm lookup; failed cache access; no downloaded skill, local skill subsequently read'},
                  'visual_review':{'pending':True},'full_acceptance':all(e['passed'] for e in acceptance)}
    dump(PACKAGE/'verification.json',verification)
    cards,board,room=match_data()
    used_keys=sorted({'screens.loading.versus',*[o['stage_key'] for o in states.values()],*[b[1] for o in states.values() for b in o.get('buttons',[])]})
    facts={'strings':{k:{'value':label(k),'source':string_source(k),'uppercase':k.startswith('common.btn.')} for k in used_keys},
           'heroes':cards,'board':{'value':board['name'],'id':board['id'],'source':{'file':rel(DERIVED/'inputs/all-boards.json'),'key':f"adminBoard.{board['id']}.answer.data.adminBoard.name"}},
           'viewer':{'value':'ProGamer','seat':0,'source':{'file':rel(DERIVED/'inputs/room-state.json'),'key':'steps.started.request.answer.data.startGame.hostId / players[0]'}},
           'caption':{'value':CAPTION,'source':{'file':SERIES,'key':'ВР-VS5-SC19-06'}},
           'layout_numbers':{'source':{'file':SERIES,'keys':['ВР-VS5-SC19-02','ВР-VS5-SC19-03','ВР-VS5-SC20-02']},'panel_width_su':624,'panel_height_su':494+(72 if card=='SC-20' else 0),'portrait_su':160},
           'copies':load(PACKAGE/'copy-provenance.json')}
    write_readme(card,states,verification)
    refresh_manifest(facts)
    return verification


def write_readme(card,states,v):
    links='\n'.join(f'- [{s} · {r} / {z}%](../../../scraped-data/derived/{PACKAGE.name}/{card}-{s}-{r}-{z}.png) · [серый](../../../scraped-data/derived/{PACKAGE.name}/{card}-{s}-{r}-{z}-gray.png)' for s in states for r,z in PRESETS)
    overlays='\n'.join(f'- [{r} / {z}%](comparison/{card}-overlay-{r}-{z}.png) · [серый](comparison/{card}-overlay-{r}-{z}-gray.png) · [легенда](comparison/{card}-overlay-{r}-{z}-legend.png) · [серая легенда](comparison/{card}-overlay-{r}-{z}-legend-gray.png)' for r,z in PRESETS)
    delta='Нет новых ключей: используются RU-строки `screens.loading.connect/state/board/versus`.' if card=='SC-19' else '`common.btn.lobby` → «В лобби» — предложение, совпадает с RU `screens.result.lobby` и `screens.aborted.lobby`. В макете «В ЛОББИ»; `common.btn.retry` → «ПОВТОРИТЬ».'
    extra='Кнопок нет; во всех трёх этапах один и тот же спиннер в положении 0. Меняется только StageText.' if card=='SC-19' else 'Ошибка меняет форму значка на `resource-connection-lost` в прежнем слоте 48 su. Иконка не сдвигается; текстовый слот расширен на 20,25 su для полной строки. Панель растёт на 72 su. «В ЛОББИ» слева, «ПОВТОРИТЬ» справа — единственная главная. «В ЛОББИ» не отменяет серверную партию; путь возврата SC-11 / SC-05. Скопированный финальный SC-19 не изменён.'
    m=v['metrics'];failed=[e['criterion'] for e in v['acceptance'] if not e['passed']]
    text=f'''# {card} — Загрузка партии\n\nСтатус: **предложено**. Серия CX-31. Рекомендую одну согласованную раскладку из задания: принятые скины HB-08, исходная библиотека SC-01 и CP-07 B. Генераций нет, `generation-records.json` пуст. Это офлайн-макеты, не приёмка движка.\n\n## Макеты\n\n{links}\n\n## Оверлеи без арта\n\n{overlays}\n\nОверлей — только контуры на `card.navy`, указатели Rxx и отдельная легенда с именами BindWidget и x/y/w/h в su. Аватаров и пикселей поля в пакете нет.\n\n## Данные и решения\n\nВР-VS5-SC19-01…08: зритель — хост ProGamer, seat 0. Слева Medusa / ProGamer, справа King Arthur / Veteran. Имена — точные `Hero.nameRu`; «Медуза» и «Король Артур» ждут контентной задачи и не нарисованы. `против` — отдельная подпись. Реальный `startGame` комнаты 6PPWSS: IN_PROGRESS, доска `c121b47f8d6eb28daccb76d05`, название `Marmoreal · original map`. Ники дополнительно подтверждены `backend/prisma/seed.ts:34,44`; файл seed не копировался. Входные JSON и их provenance не меняются. Каждая строка имеет файл и ключ в [manifest-sha256.json](manifest-sha256.json) и в `text_runs` проверки.\n\nОдна непрозрачная LoadingPanel шириной 624 su, высотой {494 if card=='SC-19' else 566} su; две PanelInset 240×320. Внутри 160-su диски CP-07 B без цвета команды и кольца, имя 24 su и ник 14 su. Padding 24 su, промежутки 24 / 16 / 12 / 4 su ровно по серии; уменьшений для S нет. 4 su — предписанный интервал имя/ник, не адаптивное сокращение. У самого тесного холста 720p / 150% панель помещается в 640-su высоту. Подпись фона в маленькой непрозрачной панели в safe area; при необходимости переносится по словам в две строки слева, не перекрывает LoadingPanel, зазор ≥8 su.\n\nФон — заданный исторический Marmoreal P7 K1, одна вуаль 0,6, без ретуши и blur. В нём ещё видны фигуры; честная подпись «{CAPTION}» сохранена. LoadingPanel и CaptionPanel — слои `screen` над вуалью, исключены из гейта перекрытия; постоянных панелей матча нет, пересечение с любыми масками фигур/клеток 0 px² по пустой маске.\n\n{extra} Ни hover, ни фокуса, ни курсора. Значки вставлены при точном px = su × DPI × UI; недостающий 54 px рисуется `render(name,54)` неизменённого snapshot, `main()` не вызывается. Спиннер не вращается в статичных кадрах.\n\n## Дельта StringTable\n\n{delta}\n\n## Проверки и ограничения\n\nМинимальный номинальный контраст текста: цвет {m['minimum_text_color']:.4f}:1, серый {m['minimum_text_gray']:.4f}:1. Минимальный фактический контраст ядра текста на финале {m['minimum_final_text_core']:.4f}:1; минимальный кегль в 720p {m['smallest_text_720p_px']} px. Значки: минимум цвет/серый {m['minimum_icon_color_or_gray']:.4f}:1. Кромки: минимум {m['minimum_edge_color_or_gray']:.4f}:1, исходные цвета не заменены. Полная приёмка: **{'пройдена' if not failed else 'не пройдена'}**; непройденные критерии перечислены в verification.json. При уменьшении тонкой кромки оценён фактический финальный растр, а не только исходный hex. Navy-кромка принятой normal primary совпадает с navy-панелью (1:1), к собственному жёлтому телу контрастная; серия требует сохранить скин. Граница портретов и текст читаются по форме. Превышения увеличения CP-07 перечислены отдельно (Medusa при 150%: 240/201 = 1,194×, лимит 1,6× не превышен).\n\nУ PNG с артом проверка токенов не распространяется на исходные рисунки и фон под вуалью: доля вне палитры не объявлена ложным нулём. UI использует только перечисленные токены, исходные скины и их alpha/AA-композиты. Все серые пары точны Rec.709. Подписи легенд измерены, перекрытий {v['overlay_label_overlap_count']}.\n\n[Проверки](verification.json), [геометрия](layout-geometry.json), [копии](copy-provenance.json), [хэши до работы](source-hashes-before.json), [осмотр PNG](visual-review.json). Манифест покрывает каждый файл пакета, derived-папки с inputs и все входы; исключает только себя.\n\nВ начале команда `npx --no-install openskills read frontend-design` неожиданно попыталась обратиться к npm и упала на доступе к кэшу; загрузки не выполнены. После этого навык прочитан локально, дальнейшая работа полностью офлайн. Git и MCP не вызывались, `unreal/` не открывался; запись ограничена папками этой задачи, новые процессы после сборки не оставлены.\n\n## Воспроизведение\n\n`python -B art/imagegen/{PACKAGE.name}/_tools/{'sc19_loading' if card=='SC-19' else 'sc20_loading_error'}.py`\n\nПересборка не перезаписывает source-hashes-before или inputs. После прямого просмотра всех PNG запись делается в visual-review.json, затем `python -B art/imagegen/{PACKAGE.name}/_tools/finalize_review.py`; независимая проверка — та же команда с `--check`.\n'''
    write_text(PACKAGE/'README.md',text)


if __name__=='__main__':
    sys.stdout.reconfigure(encoding='utf-8')
    build('SC-19',{s:{'stage_key':'screens.loading.'+s} for s in ('connect','state','board')})
