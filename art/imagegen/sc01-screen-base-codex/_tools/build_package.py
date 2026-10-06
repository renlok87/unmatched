#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""SC-01 build and measured audit. Writes only to the two task-owned directories.

Run from the project root: python -B art/imagegen/sc01-screen-base-codex/_tools/build_package.py
"""
from __future__ import annotations

from itertools import combinations
from pathlib import Path
import csv
import hashlib
import json
import sys

import numpy as np
from PIL import Image, ImageDraw

from screen_mockup_base import (Canvas, Theme, Viewport, STATES, contrast, draw_base_modal,
                               draw_screen, luma709, mix, modal_rect, wcag_luminance)
from source_audit import ROOT, PACKAGE, FONT_ROOT, sha256
from fix1_audit import inventory, compact_sources, freeze_inputs, finish_audit, refresh_manifest

DERIVED = ROOT / 'scraped-data/derived/sc01-screen-base-codex'
PROMPT = 'docs/game-design/visual/06-tasks/prompts/SC-01.codex.md'
HUD = 'docs/game-design/visual/04-hud-spec.md'
DESIGN = 'docs/game-design/visual/02-visual-design.md'
TOKENS = 'docs/unreal/contracts/hud/hud-style-tokens.json'
BOARDS = {
    'marmoreal': {
        'name': 'Marmoreal original',
        'frame': 'docs/game-design/evidence/ENV-MAPS/p7-concept-paste-2026-10-01/marmoreal-concept-flag/bench-K1-1920x1080.png',
        'trace': 'docs/game-design/evidence/ENV-MAPS/p7-concept-paste-2026-10-01/marmoreal-concept-flag/bench.trace.log',
        'figures': [(489,267,607,339),(474,351,585,431),(492,451,549,529),
                    (478,563,579,635),(1260,597,1339,665),(1188,707,1270,790)],
        'field_envelope': (300,220,1620,900),
    },
    'sarpedon': {
        'name': 'Sarpedon original',
        'frame': 'docs/game-design/evidence/ENV-MAPS/p10-sarpedon-rework-2026-10-03/sarpedon-packaged/bench-K1-1920x1080.png',
        'trace': 'docs/game-design/evidence/ENV-MAPS/p10-sarpedon-rework-2026-10-03/sarpedon-packaged/bench.trace.txt',
        'figures': [(390,490,482,557),(505,530,599,603),(384,599,478,665),
                    (647,476,710,546),(1138,551,1206,616),(1088,641,1155,719)],
        'field_envelope': (290,210,1620,925),
    },
}
STRINGS = {
    'title': 'Покинуть партию', 'body': 'Партия прервётся для обоих игроков',
    'loading': 'Подготовка поля…', 'cancel': 'Отмена', 'confirm': 'Да',
    'why': 'Заполните email и пароль', 'why_code': 'Введите 6 символов',
    'login': 'Войти', 'email': 'Email', 'password': 'Пароль',
    'credentials': 'Неверный email или пароль', 'ru': 'Русский', 'en': 'English',
    'background': 'фон-заглушка: в игре фигур нет (ВР-75)',
}
FROZEN = {}


def write_json(path, data):
    path = Path(path).resolve()
    if not (path.is_relative_to(PACKAGE) or path.is_relative_to(DERIVED)):
        raise ValueError('Output outside task roots')
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


def save_pair(image, path):
    path = Path(path).resolve()
    if not (path.is_relative_to(PACKAGE / 'comparison') or path.is_relative_to(DERIVED)):
        raise ValueError('Image outside task roots')
    path.parent.mkdir(parents=True, exist_ok=True)
    image.save(path)
    gray_path = path.with_stem(path.stem + '-gray')
    luma709(image).save(gray_path)
    return [path.relative_to(ROOT).as_posix(), gray_path.relative_to(ROOT).as_posix()]


def facts():
    """Every visible string has an input occurrence, or a documented transformation."""
    rows = {}
    named = {
        **{k: ('docs/unreal/contracts/hud/st-screens.csv', ref) for k,ref in {
            'title':'screens.pause.leave','body':'screens.pause.leave.confirm',
            'loading':'screens.loading.board','email':'screens.login.email',
            'password':'screens.login.password','credentials':'screens.login.error.credentials',
            'login':'screens.login.submit / screens.lobby.code.submit',
            'ru':'settings.interface.language.ru','en':'settings.interface.language.en'}.items()},
        'cancel': ('docs/game-design/visual/06-tasks/screens.csv', 'SC-01.do common.confirm.cancel'),
        'confirm': ('docs/game-design/visual/06-tasks/screens.csv', 'SC-01.do common.confirm.yes'),
        'why': ('docs/unreal/contracts/hud/why-reasons.json', 'why.login.fields'),
        'why_code': ('docs/unreal/contracts/hud/why-reasons.json', 'why.code.length'),
        'background': ('docs/game-design/visual/06-tasks/prompts/SC-01.fix1.codex.md', 'Fix 4'),
    }
    for key, (path, ref) in named.items():
        value = STRINGS[key]
        lines = FROZEN.get(path, ROOT/path).read_text(encoding='utf-8-sig').splitlines()
        match = next((i for i, line in enumerate(lines, 1) if value in line), None)
        if match is None:
            # A source phrase may continue on the next line (why.login.fields).
            joined = ' '.join(line.strip() for line in lines)
            if value not in joined:
                raise ValueError(f'Unsourced string {key}: {value}')
            match = next(i for i, line in enumerate(lines, 1) if value.split()[0] in line)
        rows[key] = {'text': value, 'input': path, 'line': match, 'reference': ref,
                     'transform': 'button text uppercased; whitespace joined if wrapped'}
    for state in STATES:
        rows['state.'+state] = {'text': state, 'input': PROMPT, 'reference': 'States: buttons', 'transform': 'none'}
    rows['dimensions'] = {'input': PROMPT, 'reference': 'canvas, modal 640x360, progress 480x8, spinner 48, safe margins 24/16, buttons 32, DPI 1/.75 and UI 100/150'}
    rows['annotation'] = {'input': PROMPT, 'reference': 'SC-01, base-modal, overlay, resolution/scale and layout class; technical annotations only'}
    rows['geometry'] = {'input': HUD, 'reference': '§1.6, FIELD envelopes; manual conservative figure bounds measured on the two named source PNGs'}
    rows['password-mask'] = {'text':'••••••••','input':'docs/game-design/visual/06-tasks/screens.csv',
        'reference':'SC-01.do ВР-SC09: exactly eight dots; fixed length, no password value'}
    rows['primary-selected-annotation'] = {'text':'у главной не бывает (02 §4.3)',
        'input':'docs/game-design/visual/06-tasks/prompts/SC-01.fix1.codex.md','reference':'Fix 3'}
    return rows


def dependencies():
    path='docs/game-design/visual/06-tasks/hud.csv'
    with FROZEN.get(path, ROOT/path).open(encoding='utf-8-sig', newline='') as file:
        return {r['id']: r['status'] for r in csv.DictReader(file)
                if r['id'] in ('HB-04','HB-05','HB-06','HB-09','HB-11')}


def overlay(viewport, theme):
    c = Canvas(viewport, theme)
    c.grid()
    w, h = viewport.canvas
    margin = viewport.margin
    c.rounded((margin,margin,w-2*margin,h-2*margin), None, 0, theme.color('card.cream'))
    c.rounded((32,32,w-64,h-64), None, 0, theme.color('text.secondary'))
    c.text((48,48), f'SC-01 · overlay · {viewport.layout_class} · {w:.0f}×{h:.0f} su', 'type.title', source='annotation')
    c.text((48,88), f'поле {margin} su',
           'type.body', source='dimensions')
    c.text((48,118), 'кнопки 32 su', 'type.body', source='dimensions')
    c.line([(margin,94),(44,94)],theme.color('card.cream'))
    c.line([(32,124),(44,124)],theme.color('text.secondary'))
    x,y,mw,mh = modal_rect(viewport)
    c.panel((x,y,mw,mh))
    c.text((x+16,y+16), '640×360 su · base-modal', 'type.title', source='dimensions')
    c.text((x+16,y+62), '16 su', 'type.body', source='dimensions')
    for xx in (x+mw-368,x+mw-184):
        c.rounded((xx,y+mh-64,168,48), None, 4, theme.color('card.cream'))
        c.text((xx,y+mh-88),'168×48 su','type.caption',source='dimensions')
        c.geometry.append({'kind':'button-outline','rect_su':[xx,y+mh-64,168,48]})
    c.text((x+mw-284,y+mh-40), STRINGS['cancel'].upper(), 'type.button', anchor='mm', source='cancel')
    c.text((x+mw-100,y+mh-40), STRINGS['confirm'].upper(), 'type.button', anchor='mm', source='confirm')
    c.line([(w/2,y-16),(w/2,y)], theme.color('card.glyph'), 2)
    c.line([(x-16,h/2),(x,h/2)], theme.color('card.glyph'), 2)
    c.text((48,h-48), 'panel.veil 0.6 · panel.bg 1.0 · panel.edge 0.45',
           'type.caption', source='dimensions')
    return c


def state_sheet(viewport, theme):
    c = Canvas(viewport, theme)
    w,h = viewport.canvas
    margin = max(32,viewport.margin)
    c.text((margin,margin), 'SC-01 · buttons', 'type.title', source='annotation')
    c.text((margin,margin+38), 'normal / primary · HB-08',
           'type.caption', source='state.selected')
    cell_w = (w-2*margin-32)/3
    cell_h = min(244,(h-margin-100-16)/2)
    # Minimum height 244 at 720p150 would not fit; dense layout uses 234 su.
    for i,state in enumerate(STATES):
        x = margin+(i%3)*(cell_w+16)
        y = 104+(i//3)*(cell_h+16)
        c.panel((x,y,cell_w,cell_h), 'screen')
        c.text((x+16,y+12), state, 'type.heading', source='state.'+state)
        disabled = state == 'disabled'
        c.button((x+16,y+48,cell_w-32,48), STRINGS['login'] if disabled else STRINGS['cancel'],state,
            why=('why.code.length',STRINGS['why_code']) if disabled else None,
            source='screens.lobby.code.submit' if disabled else 'common.confirm.cancel')
        if state == 'selected':
            c.text((x+16,y+150),'у главной не бывает (02 §4.3)','type.caption',
                source='primary-selected-annotation')
        else:
            c.button((x+16,y+136,cell_w-32,48), STRINGS['login'] if disabled else STRINGS['confirm'],state,primary=True,
                why=('why.login.fields',STRINGS['why']) if disabled else None,
                source='screens.login.submit' if disabled else 'common.confirm.yes')
    return c


def component_sheet(viewport, theme):
    c = Canvas(viewport,theme)
    w,h = viewport.canvas
    x,y = (w-800)/2,(h-480)/2
    c.panel((x,y,800,480),'screen')
    c.text((x+16,y+16),'SC-01 · components · HB-08','type.title',source='annotation')
    for i,(label,state,value) in enumerate([('email','normal',''),('password','focus','••••••••'),('email','error','')]):
        xx=x+16+i*256
        c.text((xx,y+68),STRINGS[label],source='screens.login.'+label)
        c.text_field((xx,y+100,232,48),value,state,source='password-mask' if value else None)
        c.text((xx,y+190),'Input_'+state.capitalize(),'type.caption',source='annotation')
        if state=='error':
            c.text((xx,y+158),STRINGS['credentials'],'type.caption',source='screens.login.error.credentials')
    c.chip((x+16,y+234,120,40),STRINGS['ru'],True,'settings.interface.language.ru')
    c.chip((x+152,y+234,120,40),STRINGS['en'],source='settings.interface.language.en')
    c.key_chip((x+304,y+238,32,32),'Esc',source='annotation')
    c.checkbox((x+368,y+242),False);c.checkbox((x+408,y+242),True)
    c.text((x+16,y+302),STRINGS['loading'],source='screens.loading.board')
    c.progress((x+16,y+334))
    for i in range(8):
        c.spinner((x+16+i*76,y+382),i)
    c.text((x+16,y+446),'480×8 su · spinner 48 su · 8 steps', 'type.caption',source='dimensions')
    return c


def mask_from_rects(rects, viewport):
    image=Image.new('1',(viewport.width,viewport.height))
    draw=ImageDraw.Draw(image)
    sx,sy=viewport.width/1920,viewport.height/1080
    for a,b,d,e in rects:
        draw.rectangle((round(a*sx),round(b*sy),round(d*sx)-1,round(e*sy)-1),fill=1)
    return np.asarray(image,dtype=bool)


def geometry_mask(canvas, kinds):
    image=Image.new('1',(canvas.viewport.width,canvas.viewport.height))
    draw=ImageDraw.Draw(image)
    factor=canvas.viewport.factor
    for item in canvas.geometry:
        if item['kind'] not in kinds:continue
        x,y,w,h=item['rect_su']
        draw.rounded_rectangle((round(x*factor),round(y*factor),round((x+w)*factor)-1,
            round((y+h)*factor)-1),radius=round(8*factor),fill=1)
    return np.asarray(image,dtype=bool)


def geometry_audit(c,board):
    data=BOARDS[board]
    masks={ 'figures': mask_from_rects(data['figures'],c.viewport),
            'spaces': mask_from_rects([data['field_envelope']],c.viewport)}
    result={}
    for kind in ('persistent','modal'):
        panel=geometry_mask(c,{kind})
        result[kind]={'panel_count':sum(i['kind']==kind for i in c.geometry),
            'panel_area_px2':int(panel.sum()),
            'overlap_figures_px2':int((panel&masks['figures']).sum()),
            'overlap_spaces_px2':int((panel&masks['spaces']).sum()),
            'exempt':kind=='modal'}
    result['mask_method']='Conservative bounding boxes manually annotated on the hashed K1 PNGs; spaces envelope includes all field art, not a claim of engine segmentation.'
    return result


def pixel_edge_audit(viewport, theme, background):
    before=Canvas(viewport,theme,background)
    before.veil()
    before_rgb=np.asarray(before.finish())
    after=Canvas(viewport,theme,background)
    after.veil();after.panel(modal_rect(viewport))
    after_rgb=np.asarray(after.finish())
    x,y,w,h=modal_rect(viewport); f=viewport.factor
    # Middle of straight edges; rounded corners and antialias fringe excluded.
    yy=round(y*f);xx=round(x*f);right=round((x+w)*f)-1;bottom=round((y+h)*f)-1
    n=max(1,round(f));mask=np.zeros((viewport.height,viewport.width),bool)
    a,b=round((x+12)*f),round((x+w-12)*f)
    d,e=round((y+12)*f),round((y+h-12)*f)
    mask[yy:yy+n,a:b]=True;mask[bottom-n+1:bottom+1,a:b]=True
    mask[d:e,xx:xx+n]=True;mask[d:e,right-n+1:right+1]=True
    la=wcag_luminance(after_rgb[mask]);lb=wcag_luminance(before_rgb[mask])
    ratios=(np.maximum(la,lb)+.05)/(np.minimum(la,lb)+.05)
    ideal=mix(theme.color('panel.edge'),theme.color('panel.bg'),theme.alpha('panel.edge'))
    outside=before_rgb[mask]
    lideal=wcag_luminance(ideal);lo=wcag_luminance(outside)
    ideal_ratios=(np.maximum(lideal,lo)+.05)/(np.minimum(lideal,lo)+.05)
    body=wcag_luminance(theme.color('panel.bg'))
    body_ratios=(np.maximum(body,lo)+.05)/(np.minimum(body,lo)+.05)
    boundary=np.maximum(ratios,body_ratios)
    return {'boundary':{'min':float(boundary.min()),'p05':float(np.quantile(boundary,.05)),
                'median':float(np.median(boundary)),'share_ge_3':float((boundary>=3).mean())},
            'body_only':{'min':float(body_ratios.min()),'p05':float(np.quantile(body_ratios,.05)),
                'median':float(np.median(body_ratios)),'share_ge_3':float((body_ratios>=3).mean())},
            'edge_only':{'min':float(ratios.min()),'p05':float(np.quantile(ratios,.05)),
                'median':float(np.median(ratios)),'share_ge_3':float((ratios>=3).mean())},
            'pass_boundary':bool(np.all(boundary>=3)),
            'ideal_edge_to_veiled_background_min':float(ideal_ratios.min()),
            'raster_edge_to_veiled_background_min':float(ratios.min()),
            'raster_edge_p05':float(np.quantile(ratios,.05)),
            'fraction_raster_below_3':float((ratios<3).mean()),
            'sample_count':int(mask.sum()),'pass_ideal':bool(ideal_ratios.min()>=3),
            'pass_raster':bool(ratios.min()>=3),'method':'Straight edge pixels compared against same coordinates of backdrop with veil, prior to panel; excludes corner AA.'}


def bounds_audit(c):
    w,h=c.viewport.canvas;m=c.viewport.margin
    buttons=[i for i in c.geometry if i['kind']=='button']
    def clearance(rect):
        x,y,rw,rh=rect;return min(x,y,w-x-rw,h-y-rh)
    return {'layout_class':c.viewport.layout_class,'canvas_su':[w,h],
        'required_content_margin_su':m,'required_button_margin_su':32,
        'min_button_margin_su':min(clearance(i['rect_su']) for i in buttons),
        'buttons_within_margin':all(clearance(i['rect_su'])>=32 for i in buttons),
        'text_within_frame':all(0<=i['bbox_px'][0]<=i['bbox_px'][2]<=c.viewport.width and
            0<=i['bbox_px'][1]<=i['bbox_px'][3]<=c.viewport.height for i in c.text_runs),
        'minimum_text_px':min(i['size_px'] for i in c.text_runs),
        'minimum_render_font_px':min(i['font_render_px'] for i in c.text_runs),
        'primary_button_count':sum(i['primary'] for i in buttons)}


def text_contrasts(theme):
    result=[]
    for bg in ['panel.bg','panel.bg.inset','panel.bg.hover','panel.bg.pressed']:
        for fg in ['text.primary','text.secondary']:
            ratio=contrast(theme.color(fg),theme.color(bg))
            result.append({'foreground':fg,'background':bg,'ratio':ratio,
                           'pass_4_5':ratio>=4.5,'pass_13':ratio>=13})
    for fg,bg in [('card.glyph','state.pending'),('card.navy','turn.flash.yellow')]:
        ratio=contrast(theme.color(fg),theme.color(bg))
        result.append({'foreground':fg,'background':bg,'ratio':ratio,'pass_4_5':ratio>=4.5,'pass_13':ratio>=13})
    return result


def grayscale_states(theme, viewport):
    comparisons={}
    for primary in (False,True):
        crops={}
        metrics={}
        states=[s for s in STATES if not (primary and s=='selected')]
        for state in states:
            vp=Viewport(round(320*viewport.factor),round(120*viewport.factor),viewport.dpi,viewport.ui)
            c=Canvas(vp,theme)
            c.button((8,8,220,48),STRINGS['confirm'] if primary else STRINGS['cancel'],state,
                primary=primary,why=('why.login.fields',STRINGS['why']) if state=='disabled' else None)
            a=np.asarray(luma709(c.finish()))
            h=round(64*vp.factor);w=round(236*vp.factor)
            crops[state]=a[:h,:w]
            item=next(i for i in c.geometry if i['kind']=='button')
            metrics[state]={'text_contrast':contrast(item['ink'],item['fill']),
                'edge_to_body':contrast(item['edge'],item['fill']),
                'cue':{'normal':'HB-08 normal','hover':'HB-08 full cream edge and hover body',
                    'pressed':'HB-08 full cream edge, pressed body and text displaced 1 su',
                    'disabled':'HB-08 inactive skin + visible why.*','focus':'HB-08 2 su ring / 2 su gap',
                    'selected':'HB-08 teal body and full glyph edge'}[state],
                'exempt_inactive':item['exempt_inactive'], 'skin':item['skin']}
        pairs=[{'a':a,'b':b,'changed_pixels':int(np.any(crops[a]!=crops[b],axis=2).sum()),
                'mean_luma_delta':float(np.abs(crops[a].astype(float)-crops[b]).mean())}
                for a,b in combinations(states,2)]
        comparisons['primary' if primary else 'normal']={'states':metrics,'pairs':pairs,
            'all_distinct':all(p['changed_pixels']>0 for p in pairs),
            'semantic_review':'Accepted HB-08 skin boundaries, body luma, focus ring and pressed text shift; no added marks. Pixel differences support direct gray visual inspection.',
            'primary_selected':'forbidden' if primary else None}
    return comparisons



if __name__ == '__main__':
    sys.stdout.reconfigure(encoding='utf-8')
    from fix1_audit import build
    build(sys.modules[__name__])
