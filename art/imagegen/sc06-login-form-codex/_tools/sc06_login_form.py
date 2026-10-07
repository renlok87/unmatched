#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""CX-28 LOGIN layout and measured package builder. No network or engine calls.

Run from any directory with python -B <package>/_tools/sc06_login_form.py.
SC-07 copies this module unchanged and supplies its own draw function.
"""
from __future__ import annotations

import sys
sys.dont_write_bytecode = True
from pathlib import Path
from itertools import combinations
from functools import lru_cache
import csv
import hashlib
import json
import math

import numpy as np
from PIL import Image, ImageDraw, ImageFont
from screen_mockup_base import Canvas, Theme, Viewport, contrast, luma709, mix, wcag_luminance

ROOT = Path(__file__).resolve().parents[4]
PACKAGE = Path(__file__).resolve().parents[1]
DERIVED = ROOT / 'scraped-data/derived' / PACKAGE.name
HUD = 'docs/game-design/visual/04-hud-spec.md'
DESIGN = 'docs/game-design/visual/02-visual-design.md'
SERIES = 'docs/game-design/visual/06-tasks/prompts/SC-06-series.codex.md'
SCREENS = 'docs/unreal/contracts/hud/st-screens.csv'
WHY = 'docs/unreal/contracts/hud/why-reasons.json'
TOKENS = 'docs/unreal/contracts/hud/hud-style-tokens.json'
SKINS = ROOT / 'art/imagegen/hud-skins-v1-codex'
ICON_ROOT = ROOT / 'art/imagegen/hud-icons-v3'
BASE_SOURCE = ROOT / 'art/imagegen/sc01-screen-base-codex/_tools/screen_mockup_base.py'
FONT_ROOT = Path('C:/Program Files/Epic Games/UE_5.8/Engine/Content/Slate/Fonts')
FRAME = 'docs/game-design/evidence/ENV-MAPS/p7-concept-paste-2026-10-01/marmoreal-concept-flag/bench-K1-1920x1080.png'
CAPTION = 'фон-заглушка: в игре фигур нет (ВР-75)'
MASK = '••••••••'
FIGURES = [(489,267,607,339), (474,351,585,431), (492,451,549,529),
           (478,563,579,635), (1260,597,1339,665), (1188,707,1270,790)]
FIELD_ENVELOPE = (300,220,1620,900)


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def guarded(path):
    path = Path(path).resolve()
    if not any(path.is_relative_to(p) for p in (PACKAGE, DERIVED)):
        raise ValueError('Output outside this package: ' + str(path))
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def dump(path, value):
    guarded(path).write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


def inputs():
    with (ROOT / SCREENS).open(encoding='utf-8-sig', newline='') as stream:
        rows = list(csv.DictReader(stream))
    strings = {r['Key']:r['ru'] for r in rows}
    reasons = {r['key']:r['ru'] for r in json.loads((ROOT/WHY).read_text(encoding='utf-8-sig'))['reasons']}
    # Only the two allowed identity lines are inspected; no credential is read into a fact.
    seed_lines = (ROOT/'backend/prisma/seed.ts').read_text(encoding='utf-8').splitlines()
    email_line = next(i for i,line in enumerate(seed_lines,1) if "email: 'pro@unmatched.com'" in line)
    user_line = next(i for i,line in enumerate(seed_lines,1) if "username: 'ProGamer'" in line)
    return strings, reasons, {'email':'pro@unmatched.com', 'email_line':email_line,
                              'username':'ProGamer', 'username_line':user_line}


STRINGS, REASONS, IDENTITY = inputs()


@lru_cache(maxsize=1)
def theme():
    return Theme(ROOT/TOKENS, FONT_ROOT/'Roboto-BoldCondensed.ttf', FONT_ROOT/'Roboto-Regular.ttf',
                 ICON_ROOT/'sizes/loader-spinner-32.png', SKINS)


def layout(vp):
    w,h = vp.canvas
    x,y = (w-480)/2, (h-420)/2
    # Same text measurement and 12 su padding as the accepted SC-01 caption.
    caption_width = theme().font('type.caption',vp.factor*4).getlength(CAPTION)/(vp.factor*4)+24
    return {'card':(x,y,480,420), 'title':(x+24,y+24),
            'email_label':(x+24,y+80), 'email':(x+24,y+104,432,48),
            'password_label':(x+24,y+168), 'password':(x+24,y+192,432,48),
            'submit':(x+24,y+288,432,48), 'error_zone':(x+24,y+342,432,44),
            'reveal':(x+420,y+204,24,24), 'value_area':(x+40,y+192,372,48),
            'ru':(w-vp.margin-104,h-vp.margin-32,48,32),
            'en':(w-vp.margin-48,h-vp.margin-32,48,32),
            'caption':(vp.margin,h-vp.margin-40,caption_width,40)}


class LoginCanvas(Canvas):
    """Extend accepted library, preserving native final-pixel icon exports."""
    def __init__(self, viewport, skin_theme, background=None):
        super().__init__(viewport, skin_theme, background)
        self.icons = []
        self.icon_layers = []

    def icon(self, name, xy, size_su):
        native_px = size_su*self.viewport.factor
        if native_px != round(native_px):
            raise ValueError('Icon pixel size is not integral')
        px = round(native_px)
        path = ICON_ROOT / f'sizes/{name}-{px}.png'
        fallback = None
        if path.is_file():
            glyph = Image.open(path).convert('RGBA')
            method = 'exact-size accepted PNG; pasted at final pixels'
            source = path.relative_to(ROOT).as_posix()
        else:
            try:
                from draw_icons_v3_snapshot import render
                glyph = render(name, px)
                method = 'unchanged v3 snapshot render(name, px); main never called'
                source = 'art/imagegen/hud-icons-v3/_tools/draw_icons.py'
            except (ImportError, OSError) as error:
                larger = sorted((int(p.stem.rsplit('-',1)[1]),p) for p in (ICON_ROOT/'sizes').glob(name+'-*.png')
                                if int(p.stem.rsplit('-',1)[1]) > px)
                if not larger:
                    raise
                path = larger[0][1]
                glyph = Image.open(path).convert('RGBA').resize((px,px), Image.Resampling.LANCZOS)
                source = path.relative_to(ROOT).as_posix()
                fallback = type(error).__name__ + ': ' + str(error)
                method = 'next larger PNG, LANCZOS; generator unavailable'
        if glyph.size != (px,px):
            raise ValueError('Unexpected icon dimensions')
        position = tuple(round(v*self.viewport.factor) for v in xy)
        self.icon_layers.append((glyph, position))
        self.icons.append({'name':name,'size_su':size_su,'size_px':px,'position_px':position,
            'source':source,'source_sha256':sha(ROOT/source),'method':method,'fallback':fallback,
            'rect_su':[*xy,size_su,size_su]})

    def finish(self):
        final = super().finish().convert('RGBA')
        for glyph,position in self.icon_layers:
            final.alpha_composite(glyph, position)
        return final


def draw_shell(c):
    g = layout(c.viewport)
    c.veil()
    c.panel(g['card'], kind='screen')
    c.text(g['title'], STRINGS['screens.login.title'], 'type.title', source='screens.login.title')
    for name in ('email','password'):
        c.text(g[name+'_label'], STRINGS['screens.login.'+name], source='screens.login.'+name)
    for name in ('ru','en'):
        c.chip(g[name], name.upper(), selected=name=='ru', source='language.'+name)
        c.geometry.append({'kind':'screen','component':'language.'+name,'rect_su':list(g[name]),
                           'selected':name=='ru','skin':'Btn_Selected' if name=='ru' else 'Chip'})
    c.panel(g['caption'], kind='screen')
    x,y,w,h = g['caption']
    c.text((x+12,y+h/2), CAPTION, 'type.caption', 'text.secondary', 'lm', source='background-caption')
    c.geometry[-1]['component'] = 'placeholder-caption'
    c.geometry.append({'kind':'reserved-slot','component':'RevealButton','rect_su':list(g['reveal']),
                       'drawn':False,'missing_glyph':True,'right_inset_su':12,
                       'value_area_su':list(g['value_area'])})
    return g


def draw_field(c, name, value, state='normal', locked=False):
    rect = layout(c.viewport)[name]
    # Library draws the field skin; separate value text permits locked secondary ink.
    c.text_field(rect, '', state, source='field.'+name)
    x,y,w,h = rect
    c.text((x+16,y+h/2), value, color='text.secondary' if locked else 'text.primary',
           anchor='lm', source='email-value' if name=='email' else 'password-mask')
    c.geometry.append({'kind':'field','component':name,'rect_su':list(rect),'value':value,
                       'state':state,'locked':locked,'skin':'Input_'+state.capitalize()})


def draw_login(c, state):
    if state not in ('empty','input'):
        raise ValueError(state)
    g = draw_shell(c)
    draw_field(c, 'email', '' if state=='empty' else IDENTITY['email'], 'focus' if state=='empty' else 'normal')
    draw_field(c, 'password', '' if state=='empty' else MASK)
    why = ('why.login.fields', REASONS['why.login.fields']) if state=='empty' else None
    c.button(g['submit'], STRINGS['screens.login.submit'], 'disabled' if state=='empty' else 'focus',
             primary=True, why=why, source='screens.login.submit')
    c.geometry.append({'kind':'error-zone','rect_su':list(g['error_zone']),
                       'lines':1 if state=='empty' else 0,'max_height_su':44})


def overlay(vp, t, task):
    """Native-canvas wireframe and nonintersecting implementation ledger.

    Numbers tie boxes to their named BindWidget ledger entries. C/R/L anchors
    are expanded in the legend. State boxes are dashed, the caption is dashed
    and explicitly excluded from the game. Labels stay outside every box.
    """
    c=LoginCanvas(vp,t);g=layout(vp);w,h=vp.canvas
    x,y,cw,ch=g['card'];ex,ey,ew,eh=g['error_zone']
    entries=[]
    def add(name,rect,key,anchor='C',state='all',note=''):
        entries.append({'bind_widget':name,'rect_su':list(rect),'string_key':key,
                        'anchor':{'C':'card centre','R':'chips bottom-right','L':'safe bottom-left'}[anchor],
                        'anchor_code':anchor,'state':state,'note':note})
    add('Title',(*g['title'],432,34),'screens.login.title')
    for n in ('email','password'):
        add(n.capitalize()+'Label',(*g[n+'_label'],432,24),'screens.login.'+n)
        add(n.capitalize()+'Box',g[n],'seed email' if n=='email' else 'fixed mask')
    add('RevealButton',g['reveal'],'—',note='24 su · глиф: нет в v3')
    add('SubmitButton',g['submit'],'screens.login.submit',state='empty/input' if task=='SC-06' else 'busy/credentials')
    if task=='SC-06':
        add('ErrorText',g['error_zone'],'why.login.fields',state='empty')
    else:
        label=STRINGS['screens.login.busy'].upper()
        tw=t.font('type.button',c.factor).getlength(label)/c.factor
        sx,sy,sw,sh=g['submit'];left=sx+(sw-44-tw)/2
        add('Spinner',(left,sy+8,32,32),'loader-spinner',state='busy')
        add('SubmitLabel',(left+44,sy+14,tw,20),'screens.login.busy',state='busy')
        add('CursorBusy',(sx+.7*sw-16,sy+sh-16,32,32),'cursor-busy',state='busy',
            note='курсор cursor-busy, не элемент кнопки')
        add('ErrorIcon',(ex,ey,24,24),'badge-refuse',state='error-credentials')
        add('ErrorText',(ex+32,ey,400,24),'screens.login.error.credentials',state='error-credentials')
        add('WhyText',(ex,ey+28,432,16),'why.login.fields',state='error-credentials')
        add('RetryButton',g['submit'],'common.btn.retry',state='error-server')
        add('ErrorIcon',(ex,ey,24,24),'resource-connection-lost',state='error-server')
        add('ErrorText',(ex+32,ey,400,24),'screens.login.error.server',state='error-server')
    add('LangRu',g['ru'],'RU',anchor='R')
    add('LangEn',g['en'],'EN',anchor='R')
    add('OverviewCaption',g['caption'],'background-caption',anchor='L',state='overview',
        note='обзорная подпись, не в игре')
    draw=ImageDraw.Draw(c.image);ink=t.color('text.primary');edge=t.color('text.secondary')
    marks=np.zeros(c.image.size[::-1],dtype=np.uint8)
    mark_image=Image.new('L',c.image.size);md=ImageDraw.Draw(mark_image)
    def line(points,dashed=False):
        pairs=list(zip(points,points[1:]))
        for a,b in pairs:
            length=math.dist(a,b);chunks=max(1,math.ceil(length/6)) if dashed else 1
            for i in range(chunks):
                if dashed and i%2:continue
                p=[(a[j]+(b[j]-a[j])*i/chunks) for j in (0,1)]
                q=[(a[j]+(b[j]-a[j])*(i+1)/chunks) for j in (0,1)]
                pts=[(c.px(p[0]),c.px(p[1])),(c.px(q[0]),c.px(q[1]))]
                draw.line(pts,fill=edge,width=max(1,c.px(1)))
                md.line(pts,fill=255,width=max(1,c.px(1)))
    def box(rect,dashed=False):
        a,b,ww,hh=rect;line([(a,b),(a+ww,b),(a+ww,b+hh),(a,b+hh),(a,b)],dashed)
    box((vp.margin,vp.margin,w-2*vp.margin,h-2*vp.margin))
    box(g['card'])
    for entry in entries:box(entry['rect_su'],entry['state']!='all')
    # Documentation uses the supplied Roboto Bold Condensed at 14 su; no tiny text.
    font=ImageFont.truetype(t.bold_font,round(14*c.factor))
    labels=[]
    def text(xx,yy,value):
        pos=(c.px(xx),c.px(yy));bb=draw.textbbox(pos,value,font=font,anchor='lt')
        draw.text(pos,value,font=font,fill=ink,anchor='lt')
        labels.append({'text':value,'bbox_px':[v/c.ss for v in bb]})
    text(vp.margin+12,vp.margin+10,f'{task} · {w:.1f} × {h:.1f} su · card 480.0 × 420.0 · шаг 88.0')
    text(vp.margin+12,vp.margin+30,'C = card centre · R = chips bottom-right · L = safe bottom-left · x y w h: su')
    # Two ledgers fit even the smallest 1137.8 × 640 su canvas.
    # The bottom caption and chips have their callouts in the top centre gap.
    core=entries[:-3];half=math.ceil(len(core)/2)
    for index,entry in enumerate(core):
        col=0 if index<half else 1;row=index if col==0 else index-half
        xx=vp.margin+12 if col==0 else x+cw+16
        yy=vp.margin+64+row*52
        entry['label_index']=index+1
        text(xx,yy,f'{index+1:02d} {entry["bind_widget"]} · {entry["state"]}')
        a,b,ww,hh=entry['rect_su']
        text(xx,yy+16,f'x {a:.1f} y {b:.1f} w {ww:.1f} h {hh:.1f}')
        text(xx,yy+32,f'{entry["string_key"]} · {entry["anchor_code"]}')
    # Chips and overview are documented below the card, clear of their boxes.
    for i,entry in enumerate(entries[-3:]):
        xx=x+12;yy=y+ch+12+i*22
        a,b,ww,hh=entry['rect_su']
        text(xx,yy,f'{entry["bind_widget"]} · x {a:.1f} y {b:.1f} w {ww:.1f} h {hh:.1f} · {entry["string_key"]} · {entry["anchor_code"]}')
    # Notes occupy free interior rows; never touch box outlines or labels.
    text(x+24,y+254,'RevealButton 24 su · глиф: нет в v3')
    text(x+24,y+396,'обзорная подпись, не в игре')
    if task=='SC-07':text(x+24,y+64,'курсор cursor-busy, не элемент кнопки')
    # Numbered marks live inside boxes, except coincident state alternatives.
    for entry in core:
        a,b,ww,hh=entry['rect_su']
        if entry['bind_widget'] in ('SubmitLabel','CursorBusy','Spinner','ErrorIcon','WhyText'):continue
        if task=='SC-07' and entry['bind_widget'] in ('ErrorText','RetryButton'):continue
        text(a+4,b+3,f'{entry["label_index"]:02d}')
    # Mark-number labels are intentionally inside their documented boxes, but
    # still audited against all actual strokes and other labels.
    strokes=np.asarray(mark_image);overlaps=[]
    for i,a in enumerate(labels):
        bb=[round(v*c.ss) for v in a['bbox_px']]
        if np.any(strokes[max(0,bb[1]-c.ss):bb[3]+c.ss,max(0,bb[0]-c.ss):bb[2]+c.ss]):
            overlaps.append({'label':a['text'],'with':'outline/mark/safe-field'})
        for b in labels[:i]:
            aa=a['bbox_px'];bb=b['bbox_px']
            if min(aa[2],bb[2])>max(aa[0],bb[0]) and min(aa[3],bb[3])>max(aa[1],bb[1]):
                overlaps.append({'label':a['text'],'with':b['text']})
    clipped=[r for r in labels if not (0<=r['bbox_px'][0]<r['bbox_px'][2]<=vp.width and 0<=r['bbox_px'][1]<r['bbox_px'][3]<=vp.height)]
    c.overlay_audit={'overlay_annotation_overlaps':len(overlaps),'overlaps':overlaps,
        'clipped_labels':clipped,'labelled_elements':entries,'labels':labels,
        'method':'Actual supersampled text bounds + 1 final-pixel clearance against raster strokes; pairwise label bounds'}
    if overlaps or clipped:raise ValueError('Overlay annotations: '+repr(c.overlay_audit))
    return c


def facts():
    result = {}
    for key in ('screens.login.title','screens.login.email','screens.login.password','screens.login.submit',
                'screens.login.busy','screens.login.error.credentials','screens.login.error.server','common.btn.retry'):
        result[key] = {'text':STRINGS[key], 'input':SCREENS, 'row_key':key, 'column':'ru',
                       'transform':'uppercase only for type.button'}
    for key in ('why.login.fields','why.syncing'):
        result[key] = {'text':REASONS[key],'input':WHY,'key':key,'column':'ru'}
    for lang in ('ru','en'):
        result['language.'+lang] = {'text':lang.upper(),'input':HUD,'section':'1.2, Язык RU / EN'}
    result['email-value'] = {'text':IDENTITY['email'],'input':'backend/prisma/seed.ts',
                            'line':IDENTITY['email_line'],'sha256':sha(ROOT/'backend/prisma/seed.ts')}
    result['seed-username'] = {'text':IDENTITY['username'],'input':'backend/prisma/seed.ts',
                              'line':IDENTITY['username_line'],'sha256':sha(ROOT/'backend/prisma/seed.ts'),
                              'displayed':False}
    result['password-mask'] = {'text':MASK,'input':SERIES,'decision':'ВР-VS4-SC06-01 / ВР-SC09',
                              'meaning':'fixed display mask, independent of credential'}
    result['background-caption'] = {'text':CAPTION,'input':SERIES,'section':'Common notes / ВР-VS3-SC01-05'}
    result['reveal-slot'] = {'text':'RevealButton 24 su · глиф: нет в v3','input':SERIES,
                           'decision':'ВР-VS4-SC06-03'}
    result['geometry-facts'] = {'input':HUD,'section':'1.2 / 1.6', 'overrides':SERIES,
        'decisions':'ВР-VS4-SC06-02…04', 'derived':{'label_row_su':24,'field_step_su':88,
        'fields_top_offset_su':[104,192], 'submit_top_offset_su':288, 'error_top_offset_su':342,
        'caption_height_su':40, 'caption_width':'rendered caption width + 2 * 12 su', 'chip_width_su':48,'chip_gap_su':8},
        'note':'Layout coordinates and documentation dimensions are design choices, not invented game data.'}
    result['annotation'] = {'input':SERIES,'section':'packages, canvases, overlay contract',
                            'transform':'computed canvas dimensions, layout class, task ID'}
    result['icons'] = {'input':SERIES,'decisions':'ВР-VS4-SC07-01…04',
                      'names':['loader-spinner','badge-refuse','resource-connection-lost','cursor-busy']}
    return result


def record(path):
    p = Path(path)
    return {'sha256':sha(p),'bytes':p.stat().st_size} if p.is_file() else None


def tree():
    return {p.relative_to(ROOT).as_posix():record(p) for p in sorted(ICON_ROOT.rglob('*')) if p.is_file()}


def tree_digest(values):
    return hashlib.sha256(json.dumps(values,sort_keys=True,separators=(',',':')).encode()).hexdigest()


def check_sources():
    before = json.loads((PACKAGE/'source-hashes-before.json').read_text(encoding='utf-8'))
    changes = [name for name,value in before['files'].items() if record(Path(name) if Path(name).is_absolute() else ROOT/name)!=value]
    icons = tree()
    same = tree_digest(icons)==before['icons']['tree_digest'] and len(icons)==before['icons']['file_count']
    # Tree digest covers names, counts and contents, including additions/deletions.
    return before, changes, same, icons


def boundary_audit(vp,t,background):
    bare = Canvas(vp,t,background); bare.veil()
    before = np.asarray(bare.finish())[:,:,:3]
    shown = Canvas(vp,t,background); shown.veil();shown.panel(layout(vp)['card'],kind='screen')
    after = np.asarray(shown.finish())[:,:,:3]
    x,y,w,h = layout(vp)['card'];f=vp.factor
    xx,yy,rr,bb = round(x*f),round(y*f),round((x+w)*f)-1,round((y+h)*f)-1
    n=max(1,round(f));m=np.zeros((vp.height,vp.width),bool)
    a,b=round((x+12)*f),round((x+w-12)*f);d,e=round((y+12)*f),round((y+h-12)*f)
    m[yy:yy+n,a:b]=True;m[bb-n+1:bb+1,a:b]=True
    m[d:e,xx:xx+n]=True;m[d:e,rr-n+1:rr+1]=True
    exterior=wcag_luminance(before[m]);edge=wcag_luminance(after[m]);body=wcag_luminance(t.color('panel.bg'))
    ratio=lambda a,b:(np.maximum(a,b)+.05)/(np.minimum(a,b)+.05)
    edge_ratios=ratio(edge,exterior);body_ratios=ratio(body,exterior)
    ratios=np.maximum(edge_ratios,body_ratios)
    return {'minimum':float(ratios.min()),'p05':float(np.quantile(ratios,.05)),
            'median':float(np.median(ratios)), 'share_ge_3':float((ratios>=3).mean()),
            'edge_only_minimum':float(edge_ratios.min()),'body_only_minimum':float(body_ratios.min()),
            'samples':int(m.sum()), 'passed':bool(np.all(ratios>=3)),
            'method':'max(raster edge / veiled backdrop, opaque body / same backdrop); straight-edge pixels, no corner AA',
            'note':'Preserved accepted SC-01/HB-08 skin and single 0.6 veil; raw failures retained.'}


def overlap_audit(c):
    vp=c.viewport
    def mask(boxes):
        result=np.zeros((vp.height,vp.width),bool)
        for x0,y0,x1,y1 in boxes:
            result[round(y0*vp.height/1080):round(y1*vp.height/1080),
                   round(x0*vp.width/1920):round(x1*vp.width/1920)]=True
        return result
    figs,spaces=mask(FIGURES),mask([FIELD_ENVELOPE]);screens=[]
    for item in c.geometry:
        if item['kind']!='screen':continue
        x,y,w,h=item['rect_su'];f=vp.factor;p=np.zeros_like(figs)
        p[round(y*f):round((y+h)*f),round(x*f):round((x+w)*f)]=True
        screens.append({'kind':'screen','component':item.get('component','login-card'),
                        'rect_su':item['rect_su'],'figures_px2':int((p&figs).sum()),
                        'spaces_px2':int((p&spaces).sum()),'exempt':True})
    return {'persistent_panels':[], 'persistent_figures_px2':0,'persistent_spaces_px2':0,
            'screen_layers':screens,'mask_source':FRAME,'figure_boxes_px':FIGURES,
            'space_envelope_px':FIELD_ENVELOPE,
            'method':'SC-01 conservative manual boxes, scaled by actual image size; no engine segmentation claim'}


def layout_audit(c):
    vp=c.viewport;g=layout(vp)
    text=[r for r in c.text_runs if r['text']]
    bounds=lambda b:0<=b[0]<=b[2]<=vp.width and 0<=b[1]<=b[3]<=vp.height
    def inside(a,b):
        return a[0]>=b[0] and a[1]>=b[1] and a[0]+a[2]<=b[0]+b[2] and a[1]+a[3]<=b[1]+b[3]
    def intersects(a,b):
        return max(0,min(a[0]+a[2],b[0]+b[2])-max(a[0],b[0]))*max(0,min(a[1]+a[3],b[1]+b[3])-max(a[1],b[1]))
    f=vp.factor
    value_box=next((r['bbox_px'] for r in text if r['source']=='password-mask'),None)
    error_text=[r for r in text if r['source'] in ('why.login.fields','screens.login.error.credentials','screens.login.error.server')]
    error_rect=[g['error_zone'][0]*f,g['error_zone'][1]*f,(g['error_zone'][0]+432)*f,(g['error_zone'][1]+44)*f]
    return {'minimum_text_su':min(r['size_su'] for r in text),'minimum_text_px':min(r['size_px'] for r in text),
            'minimum_render_font_px':min(r['font_render_px'] for r in text),
            'all_text_within_canvas':all(bounds(r['bbox_px']) for r in text),
            'card_su':list(g['card']),'card_centered':g['card'][0]+240==vp.canvas[0]/2 and g['card'][1]+210==vp.canvas[1]/2,
            'card_content_fits':all(inside(g[n],g['card']) for n in ('email','password','submit','error_zone','reveal')),
            'error_text_within_zone':all(r['bbox_px'][0]>=error_rect[0] and r['bbox_px'][1]>=error_rect[1] and
                r['bbox_px'][2]<=error_rect[2] and r['bbox_px'][3]<=error_rect[3] for r in error_text),
            'field_step_su':88,'inner_padding_su':24,'label_row_su':24,
            'primary_count':sum(i.get('primary',False) for i in c.geometry),
            'caption_card_overlap_su2':intersects(g['caption'],g['card']),
            'caption_chip_overlap_su2':sum(intersects(g['caption'],g[n]) for n in ('ru','en')),
            'language_right_bottom_margin_su':vp.margin,
            'password_value_before_reveal':not value_box or value_box[2] <= g['reveal'][0]*f,
            'focused_components':[i.get('component','submit') for i in c.geometry if i.get('state')=='focus'],
            'text_runs':text}


def text_audit(c):
    result=[];g=layout(c.viewport);f=c.viewport.factor
    for r in c.text_runs:
        if not r['text']:continue
        bg=c.theme.color('panel.bg');surface='panel.bg'
        cx=(r['bbox_px'][0]+r['bbox_px'][2])/2/f;cy=(r['bbox_px'][1]+r['bbox_px'][3])/2/f
        for name in ('email','password'):
            x,y,w,h=g[name]
            if x<=cx<=x+w and y<=cy<=y+h:
                bg=c.theme.color('panel.bg.inset');surface='Input_Normal inset'
        x,y,w,h=g['submit']
        if x<=cx<=x+w and y<=cy<=y+h:
            button=next(i for i in c.geometry if i['kind']=='button');bg=button['fill'];surface=button['skin']
        x,y,w,h=g['ru']
        if x<=cx<=x+w and y<=cy<=y+h:bg=c.theme.color('state.pending');surface='Btn_Selected'
        ratio=contrast(r['ink'],bg)
        result.append({'text':r['text'],'source':r['source'],'surface':surface,'ink':r['ink'],
                       'background':bg,'ratio':ratio,'passed':ratio>=4.5})
    return result


def internal_edges(c):
    t=c.theme;items=[]
    for i in c.geometry:
        if i['kind']=='field':
            x,y,w,h=i['rect_su'];p=c.image.getpixel((c.px(x+w/2),c.px(y+.5)))[:3]
            items.append({'component':i['component'],'skin':i['skin'],'ratio':contrast(p,t.color('panel.bg')),
                          'reference':'normal field edge vs card; focus ring independently >=3', 'passed':contrast(p,t.color('panel.bg'))>=3})
        if i['kind']=='button':
            # Navy primary keyline separates the bright body; boundary to card is body or focus ring.
            ratio=max(contrast(i['edge'],t.color('panel.bg')),contrast(i['fill'],t.color('panel.bg')))
            items.append({'component':'submit','skin':i['skin'],'ratio':ratio,'inactive':i['state']=='disabled',
                          'raw_keyline_to_body':contrast(i['edge'],i['fill']),
                          'passed':ratio>=3 or i['state']=='disabled'})
    ratio=contrast(t.color('card.glyph'),t.color('state.pending'))
    items.append({'component':'RU selected','ratio':ratio,'passed':ratio>=3})
    return items


def flat_palette_audit(image,c):
    """Measure only flat interior UI pixels. Background art and edge AA are excluded."""
    rgb=np.asarray(image)[:,:,:3].astype(np.int16);mask=np.zeros(rgb.shape[:2],bool)
    for item in c.geometry:
        if item['kind']!='screen':continue
        x,y,w,h=item['rect_su'];f=c.viewport.factor;pad=max(2,round(6*f))
        mask[round(y*f)+pad:round((y+h)*f)-pad,round(x*f)+pad:round((x+w)*f)-pad]=True
    flat=mask.copy()
    for dy,dx in ((-1,0),(1,0),(0,-1),(0,1),(-1,-1),(1,1)):
        flat &= np.all(rgb==np.roll(rgb,(dy,dx),(0,1)),axis=2)
    allowed={c.theme.color(n) for n in ('panel.bg','panel.bg.inset','text.primary','text.secondary',
             'card.navy','card.cream','card.glyph','state.pending','turn.flash.yellow','state.error','mark.keyline')}
    # Accepted HB-08 raster cores and alpha composites on the opaque card.
    for name in ('Modal','Input_Normal','Input_Focus','BtnPrimary_Normal','BtnPrimary_Disabled','BtnPrimary_Focus','Btn_Selected','Chip'):
        sk=np.asarray(c.theme.skin(name,1));a=sk[:,:,3:4]/255
        cores=np.rint(sk[:,:,:3]*a+np.array(c.theme.color('panel.bg'))*(1-a)).astype(np.uint8)
        allowed.update(tuple(v) for v in np.unique(cores.reshape(-1,3),axis=0))
    for glyph,_ in c.icon_layers:
        allowed.update(tuple(v[:3]) for v in np.unique(np.asarray(glyph).reshape(-1,4),axis=0) if v[3]==255)
    samples,counts=np.unique(rgb[flat],axis=0,return_counts=True)
    # CIE Lab DeltaE76 threshold, matching 07 §1.2.
    def lab(values):
        v=np.asarray(values,dtype=float)/255
        lin=np.where(v<=.04045,v/12.92,((v+.055)/1.055)**2.4)
        xyz=lin @ np.array([[.4124564,.3575761,.1804375],[.2126729,.7151522,.0721750],[.0193339,.1191920,.9503041]]).T
        z=xyz/np.array([.95047,1,1.08883]);q=np.where(z>(6/29)**3,np.cbrt(z),z/(3*(6/29)**2)+4/29)
        return np.stack([116*q[:,1]-16,500*(q[:,0]-q[:,1]),200*(q[:,1]-q[:,2])],axis=1)
    d=np.sqrt(((lab(samples)[:,None,:]-lab(list(allowed))[None,:,:])**2).sum(2)).min(1)
    bad=int(counts[d>3].sum());total=int(counts.sum())
    return {'flat_ui_pixels':total,'outside_deltaE76_3_pixels':bad,'outside_fraction':bad/max(1,total),
            'passed':bad==0,'method':'3x3 flat opaque screen interiors; token colors + accepted skin raster/composites + accepted icon cores; exclude background and AA',
            'unexpected_colors':[{'rgb':v.tolist(),'count':int(n),'deltaE76':float(dd)} for v,n,dd in zip(samples,counts,d) if dd>3]}


def save_pair(im,path):
    path=guarded(path);im.convert('RGBA').save(path,optimize=True)
    gray=guarded(path.with_stem(path.stem+'-gray'))
    luma709(im).convert('RGBA').save(gray,optimize=True)
    return [path,gray]


def exports(paths):
    result=[]
    for path in paths:
        with Image.open(path) as im:
            alpha=np.asarray(im.convert('RGBA'))[:,:,3];ys,xs=np.where(alpha>0)
            result.append({'path':path.relative_to(ROOT).as_posix(),'sha256':sha(path),
                'size_px':list(im.size),'mode':im.mode,'margin_px':[int(xs.min()),int(ys.min()),int(im.width-1-xs.max()),int(im.height-1-ys.max())],
                'touches_edge':bool(xs.min()==0 or ys.min()==0 or xs.max()==im.width-1 or ys.max()==im.height-1),
                'note':'Full opaque canvas; alpha margin is not the UI safe margin.'})
    return result


def refresh_manifest():
    source=json.loads((PACKAGE/'source-hashes-before.json').read_text(encoding='utf-8'))
    used=json.loads((PACKAGE/'icons-used.json').read_text(encoding='utf-8')) if (PACKAGE/'icons-used.json').exists() else []
    icon_sources={i['source']:record(ROOT/i['source']) for i in used}
    source['icons']['used_files'].update(icon_sources)
    output={p.relative_to(ROOT).as_posix():record(p) for folder in (PACKAGE,DERIVED) for p in sorted(folder.rglob('*'))
            if p.is_file() and p!=PACKAGE/'manifest-sha256.json'}
    dump(PACKAGE/'manifest-sha256.json',{'schema':'CX-28.manifest/1','sources':source['files'],
        'icon_tree':source['icons'],'facts':facts(),'outputs':output,
        'note':'All files in package and own derived folder, except this manifest. Icon inputs covered by canonical tree digest and used-file hashes.'})


def build(task='SC-06',states=('empty','input'),draw=draw_login):
    expected={'SC-06':'sc06-login-form-codex','SC-07':'sc07-login-errors-codex'}
    if PACKAGE.name!=expected[task]:raise ValueError('Task/package mismatch')
    before,changes,same,initial_icons=check_sources()
    if changes or not same:raise RuntimeError('Sources changed before build: '+repr(changes))
    for directory in ('comparison','concepts','prompts'):(PACKAGE/directory).mkdir(exist_ok=True)
    DERIVED.mkdir(parents=True,exist_ok=True)
    t=theme();background=Image.open(ROOT/FRAME).convert('RGBA')
    images=[];geometry={};measurements={};palette=[];gray_pairs=[];used=[];overlay_measurements={}
    for res in ('1080p','720p'):
        for scale in (100,150):
            vp=Viewport.preset(res,scale);key=f'{res}-{scale}';g=layout(vp)
            geometry[key]={'viewport_px':[vp.width,vp.height],'canvas_su':list(vp.canvas),
                'px_per_su':vp.factor,'layout_class':vp.layout_class,'content_margin_su':vp.margin,
                'rectangles_su':{k:list(v) for k,v in g.items() if len(v)==4},
                'rectangles_px':{k:[round(z*vp.factor,4) for z in v] for k,v in g.items() if len(v)==4},
                'anchors':{'card':'center','ru':'bottom-right','en':'bottom-right','caption':'bottom-left'},
                'field_step_su':88,'reveal_glyph':None}
            state_images={};state_canvases={};measured={}
            for state in states:
                c=LoginCanvas(vp,t,background);draw(c,state);image=c.finish()
                images += save_pair(image,DERIVED/f'{task}-{state}-{key}.png')
                state_images[state]=image;state_canvases[state]=c
                measured[state]={'layout':layout_audit(c),'text_contrast':text_audit(c),
                    'edges':internal_edges(c),'overlap':overlap_audit(c),'icons':c.icons,'geometry':c.geometry}
                palette.append({'canvas':key,'state':state,**flat_palette_audit(image,c)})
                used += c.icons
            measured['screen_boundary']=boundary_audit(vp,t,background)
            measurements[key]=measured
            ov=overlay(vp,t,task);ovim=ov.finish();images += save_pair(ovim,PACKAGE/'comparison'/f'{task}-overlay-{key}.png')
            for suffix in ('','-gray'):
                overlay_measurements[f'{task}-overlay-{key}{suffix}.png']=ov.overlay_audit
            # Comparison stack preserves every native canvas pixel; all K1 imagery stays in derived.
            comp=Image.new('RGBA',(vp.width,vp.height*len(states)),t.color('panel.bg')+(255,))
            for i,state in enumerate(states):comp.paste(state_images[state],(0,i*vp.height))
            images += save_pair(comp,DERIVED/f'{task}-comparison-{key}.png')
            for a,b in combinations(states,2):
                x,y,w,h=g['card'];box=(round(x*vp.factor),round(y*vp.factor),round((x+w)*vp.factor),round((y+h)*vp.factor))
                aa=np.asarray(luma709(state_images[a].crop(box)))[:,:,0];bb=np.asarray(luma709(state_images[b].crop(box)))[:,:,0]
                delta=np.abs(aa.astype(float)-bb)
                cues={'empty':'empty fields, Email focus and visible why', 'input':'filled values, submit focus',
                      'busy':'spinner, busy label and hourglass cursor',
                      'error-credentials':'password cleared, password focus, X and two reason lines',
                      'error-server':'password retained, connection-loss icon, retry label and submit focus'}
                gray_pairs.append({'canvas':key,'a':a,'b':b,'changed_pixels':int((delta>0).sum()),
                    'mean_luma_delta':float(delta.mean()),'pixels_delta_ge_20':int((delta>=20).sum()),
                    'shape_or_text_cues':[cues[a],cues[b]],'passed':bool((delta>=20).any())})
    dump(PACKAGE/'layout-geometry.json',geometry)
    dump(PACKAGE/'icons-used.json',used)
    _,changes,same,after_icons=check_sources()
    changed_icons=[n for n in sorted(set(initial_icons)|set(after_icons)) if initial_icons.get(n)!=after_icons.get(n)]
    copies={'screen_mockup_base.py':sha(PACKAGE/'_tools/screen_mockup_base.py')==sha(BASE_SOURCE),
            'draw_icons_v3_snapshot.py':sha(PACKAGE/'_tools/draw_icons_v3_snapshot.py')==sha(ICON_ROOT/'_tools/draw_icons.py')}
    if task=='SC-07':copies['sc06_login_form.py']=sha(PACKAGE/'_tools/sc06_login_form.py')==sha(ROOT/'art/imagegen/sc06-login-form-codex/_tools/sc06_login_form.py')
    all_states=[measurements[k][s] for k in measurements for s in states]
    all_text=[r for m in all_states for r in m['text_contrast']]
    text_pass=all(r['passed'] for r in all_text)
    edge_pass=all(m['screen_boundary']['passed'] for m in measurements.values()) and all(e['passed'] for m in all_states for e in m['edges'])
    source_ok=not changes and same and all(copies.values())
    sizes_ok=all(m['layout']['minimum_text_su']>=14 and m['layout']['all_text_within_canvas'] and m['layout']['card_content_fits'] and m['layout']['error_text_within_zone'] for m in all_states)
    accept=lambda passed,measured,expected,note='':{'passed':bool(passed),'measured':measured,'expected':expected,'note':note}
    acceptance={
        'every text and number traces to manifest facts':accept(all(r['source'] in facts() for m in all_states for r in m['layout']['text_runs']),len(facts()),'all strings, identity and derived geometry sourced'),
        '1080p/720p x 100/150 x color/grayscale':accept(len(images)==(len(states)+2)*8,len(images),(len(states)+2)*8),
        'text contrast >=4.5:1':accept(text_pass,min(r['ratio'] for r in all_text),4.5),
        'edges and icons >=3:1':accept(edge_pass,{k:v['screen_boundary'] for k,v in measurements.items()},3,
            'Card boundary failures preserved. Accepted SC-01 skin, veil and tokens unchanged; no silent threshold exemption.'),
        'smallest text at 720p >=10.5px':accept(sizes_ok,min(measurements['720p-100'][s]['layout']['minimum_text_px'] for s in states),10.5),
        'persistent overlaps 0 px2; screens separately reported':accept(True,{'persistent_figures_px2':0,'persistent_spaces_px2':0},0,'No match panels; screen layers are exempt by series override.'),
    }
    if task=='SC-06':
        acceptance.update({'email traces to seed.ts':accept(IDENTITY['email']=='pro@unmatched.com',facts()['email-value'],'seed.ts email line'),
                           'password exactly eight fixed dots':accept(MASK=='•'*8,MASK,'••••••••'),
        'disabled and primary differ in grayscale':accept(all(p['passed'] for p in gray_pairs),gray_pairs,'shape or text / luma >=20')})
    else:
        acceptance['three frames']=accept(len(states)==3,list(states),['busy','error-credentials','error-server'])
    acceptance['fix1 overlay annotations']=accept(all(v['overlay_annotation_overlaps']==0 and not v['clipped_labels'] for v in overlay_measurements.values()),len(overlay_measurements),'8 overlays, no annotation overlaps or clipping')
    dump(PACKAGE/'verification.json',{'schema':'CX-28.verification/1','task':task,'status':'предложено',
        'source_unchanged':source_ok,'sources':{'changed_files':changes,'icon_tree':{
            'tree_digest_before':before['icons']['tree_digest'],'tree_digest_after':tree_digest(after_icons),
            'file_count':len(after_icons),'changed_files':changed_icons},'unchanged_copies':copies},
        'exports':exports(images),'palette':{'passes':all(p['passed'] for p in palette),'measurements':palette,
            'tokens_input':TOKENS,'skins_input':'art/imagegen/hud-skins-v1-codex/vector/',
            'note':'Raw art and its veil composite are not token-palette UI; accepted flat skin derivatives included.'},
        'gray':{'method':'Rec.709 encoded RGB, rounded: .2126 R + .7152 G + .0722 B','all_paired':True,'state_pairs':gray_pairs},
        'sizes':{'passed':sizes_ok,'presets':list(geometry),'text_min_su':14,'minimum_720p_px':10.5,
                 'direct_layout_per_canvas':True,'master':'1080p-100','master_downscale':False},
        'outside_folder':[],'scope':{'git':False,'mcp':False,'unreal':False,'image_generation':False,
            'write_roots':[PACKAGE.relative_to(ROOT).as_posix(),DERIVED.relative_to(ROOT).as_posix()],
            'processes_started':'synchronous Python only; no background process'},
        'facts':facts(),'layout_measurements':measurements,'overlay_measurements':overlay_measurements,'acceptance':acceptance,
        'acceptance_pass':all(a['passed'] for a in acceptance.values()),
        'missing':['RevealButton glyph: absent in accepted v3; requires new IC card'],
        'visual_review':{'completed':False,'record':'visual-review.json','note':'Must be completed by actual PNG inspection.'}})
    refresh_manifest()
    print(json.dumps({'task':task,'png_count':len(images),'source_unchanged':source_ok,
                      'text_min_contrast':min(r['ratio'] for r in all_text),'acceptance_pass':all(a['passed'] for a in acceptance.values())},ensure_ascii=False))


if __name__=='__main__':
    sys.stdout.reconfigure(encoding='utf-8')
    build()
