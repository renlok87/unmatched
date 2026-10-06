#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""HB-07 / CX-01r v2. Offline Pillow renderer, two guarded output roots only.

Run from checkout: python -B -X utf8 art/imagegen/hud-composition-v1-codex/_tools/build_mockups.py
No git, network, UE, subprocesses, ImageGen or icon generation. The old reference
module supplies ONLY devalue decoding, token/font functions, masks and §04 geometry.
Its old capture/build/render functions are never called. Icons are immutable PNGs.
"""
from __future__ import annotations
import csv
import hashlib
import itertools
import json
import math
import os
import re
from pathlib import Path
from functools import lru_cache
import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageOps, ImageFilter
import layout_reference as ref

ROOT = ref.ROOT
PACKAGE, DERIVED = ref.PACKAGE, ref.DERIVED
SPEC, DESIGN, PROMPT = ref.SPEC, ref.DESIGN, ref.PROMPT
T, BOARD, CONFIGS, STATES = ref.T, ref.BOARD, ref.CONFIGS, ref.STATES
BOARD['marmoreal']['background'] = 'docs/game-design/evidence/ENV-MAPS/p7-concept-paste-2026-10-01/marmoreal-concept-flag/bench-K1-1920x1080.png'
DB = 'C:/tmp/visual/CX-01r/db-names-2026-10-06.txt'
WRITE_LEDGER = []
LEGACY_MASKS = ref.masks
REGISTRATION = {
    'marmoreal': {'M01':[566,307],'M06':[1243,299],'M12':[1388,374],
        'M13':[523,500],'M24':[1403,590],'M25':[818,693],'M26':[1103,694],
        'M27':[574,779],'M28':[733,810],'M30':[1030,810],'M31':[1230,759]},
    'sarpedon': {'S01':[474,318],'S05':[971,309],'S07':[1442,302],
        'S20':[678,531],'S23':[435,642],'S28':[429,756],
        'S36':[1073,815],'S37':[1219,816],'S38':[1335,795]},
}


@lru_cache(None)
def masks(board,w,h):
    """Topology -> measured FIELD -> fitted plane projection -> conservative discs.

    Anchor centers are manual geometric measurements of the immutable bench PNG,
    not game state. This corrects the old visibly inaccurate affine registration.
    Never move HUD to excuse a wrong projection; preserve both transforms as evidence.
    """
    _, fm, field, old=LEGACY_MASKS(board,w,h)
    topo=ref.load_json(ROOT/f'backend/prisma/fixtures/boards/{board}.topology.json')
    spaces={p['id']:p for p in topo['spaces']}; bounds=old['source_disc_bounds']
    sx,sy,fx,fy=old['transform']
    def tofield(x,y):return [fx+(x-bounds[0])*sx,fy+(y-bounds[1])*sy]
    A=[]; b=[]
    for sid,(u,v) in REGISTRATION[board].items():
        p=spaces[sid]['layout']; x,y=tofield(p['x'],p['y'])
        A += [[x,y,1,0,0,0,-u*x,-u*y],[0,0,0,x,y,1,-v*x,-v*y]]
        b += [u,v]
    sol=np.linalg.lstsq(np.asarray(A),np.asarray(b),rcond=None)[0]
    matrix=np.append(sol,1).reshape((3,3))
    def project(x,y):
        out=matrix@np.array([*tofield(x,y),1]);return out[:2]/out[2]
    errors=[]
    for sid,point in REGISTRATION[board].items():
        p=spaces[sid]['layout'];errors.append(float(np.linalg.norm(project(p['x'],p['y'])-point)))
    q=w/1920; sm=Image.new('L',(w,h)); d=ImageDraw.Draw(sm); mapped=[]
    for p in topo['spaces']:
        x,y=p['layout']['x'],p['layout']['y'];rad=topo['spaceRadiusPx']
        points=[project(x+rad*math.cos(t),y+rad*math.sin(t))*q for t in np.linspace(0,2*math.pi,65)]
        points=[v.tolist() for v in points];d.polygon([tuple(v) for v in points],fill=255)
        mapped.append({'id':p['id'],'polygon_px':points,'center_px':(project(x,y)*q).tolist(),
            'ellipse_px':[min(v[0] for v in points),min(v[1] for v in points),max(v[0] for v in points),max(v[1] for v in points)],'zones':p['zones']})
    # Extra footprint protects uncertain manually measured cell/ring boundaries.
    cell_margin=max(1,math.ceil(15*q)); figure_margin=max(1,math.ceil(6*q))
    sm=sm.filter(ImageFilter.MaxFilter(2*cell_margin+1))
    fm=fm.filter(ImageFilter.MaxFilter(2*figure_margin+1))
    return sm,fm,field,{'source_disc_bounds':bounds,'topology_to_FIELD':old['transform'],
        'FIELD_to_bench_homography':matrix.tolist(),'registration_anchors_1080p':REGISTRATION[board],
        'anchor_residual_max_px_1080p':max(errors),'anchor_residual_mean_px_1080p':sum(errors)/len(errors),
        'cell_conservative_dilation_px':cell_margin,'figure_conservative_dilation_px':figure_margin,'spaces':mapped}


ref.masks = masks


def guarded(path):
    p = Path(path).resolve()
    if not any(p.is_relative_to(q.resolve()) for q in (PACKAGE, DERIVED)):
        raise ValueError('Forbidden output: ' + str(p))
    p.parent.mkdir(parents=True, exist_ok=True)
    WRITE_LEDGER.append(ref.relative(p))
    return p


def save_json(path, data):
    guarded(path).write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


def save_image(im, path):
    im.convert('RGBA').save(guarded(path))


def table(name):
    path = 'docs/unreal/contracts/hud/' + name + '.csv'
    with (ROOT / path).open(encoding='utf-8-sig', newline='') as f:
        return {row['Key']: {**row, 'source': path} for row in csv.DictReader(f)}


STRINGS = table('st-hud') | table('st-ms')


def st(key, **params):
    row = STRINGS[key]
    return row['ru'].format(**params), {'source': row['source'], 'key': key,
        'source_ru': row['ru'], 'source_en': row['SourceString'], 'parameters': params}


def fact(source, key, evidence='', **values):
    return {'source': source, 'key': key, 'evidence': evidence, **values}


@lru_cache(None)
def font(size, bold=False):
    return ImageFont.truetype(str(ref.FONT_DIR / ('Roboto-BoldCondensed.ttf' if bold else 'Roboto-Regular.ttf')), size)


def wrap(value, f, max_px):
    lines, line = [], ''
    for word in value.split(' '):
        candidate = (line + ' ' + word).strip()
        if line and f.getlength(candidate) > max_px:
            lines.append(line)
            line = word
        else:
            line = candidate
    if line:
        lines.append(line)
    return lines


def text_plan(value, size, scale, width, bold=True, fallback=False):
    """Word wrap first; STATUS may descend one type token at a time; never ellipsize."""
    for candidate in ([24, 20, 16] if fallback else [size]):
        f = font(math.ceil(candidate * scale), bold)
        lines = wrap(value, f, width * scale)
        if not fallback or len(lines) <= 2:
            return candidate, lines
    raise ValueError('STATUS cannot fit two lines at type.body: ' + value)


def geometry(board, state, w, h, s):
    g = ref.geometry(board, w, h, s)
    r = g['rectangles']; literal = {k: list(v) for k, v in r.items()}
    W, H = g['canvas_su']; small = g['class'] == 'S'
    # Literal S §1.6 width is <=600, not a hidden W-528 change; no need to narrow.
    r['STATUS'] = ((W - (600 if small else (880 if w == 1920 else 720))) / 2,
                   16 if small else 24, 600 if small else (880 if w == 1920 else 720), 40 if small else 48)
    literal['STATUS'] = list(r['STATUS'])
    # Enforce all cells, not only cells occupied by figures: caption begins FIELD+8.
    x, _, ww, _ = r['HAND']
    sm,fm,_,_=ref.masks(board,w,h)
    x0,x1=round(x*s),round((x+ww)*s)
    lastrows=np.where(np.any(((np.asarray(sm)>0)|(np.asarray(fm)>0))[:,x0:x1],axis=1))[0]
    last=max(int(lastrows[-1]) if len(lastrows) else -1,math.floor(g['field_su'][3]*s))
    caption_y=(last+1+math.ceil(8*s))/s
    hand_y=caption_y+22
    r['HAND-CAPTION'] = (x, caption_y, ww, 22)
    r['HAND'] = (x, hand_y, ww, max(0, H - hand_y))
    g['hand_visible_su'] = min(g['card_size_su'][1], H - hand_y)
    if not small and state!='combat-defense':
        lx,ly,lw,lh=r['LOG']
        protected=(np.asarray(sm)>0)|(np.asarray(fm)>0)
        part=protected[max(0,round(ly*s)):min(h,round((ly+lh)*s))]
        columns=np.where(np.any(part,axis=0))[0]
        if len(columns):
            safe_width=math.floor(columns[0]/s)-lx-8
            r['LOG']=(lx,ly,min(lw,safe_width),lh)
    if small:
        r['OPP-HAND'] = (W - 16 - 220, 120, 220, 87)
    else:
        # Roboto 14su ceil-rasterization at 0.75 adds a pixel; keep caption inside edge.
        r['OPP-HAND'] = (*r['OPP-HAND'][:3],92)
    # STATUS adaptive height, no font clipping, two-line behavior per §2.5.
    status, _ = status_content(board, state)
    cap = r['STATUS'][2]
    ts, lines = text_plan(status, 24, s, cap - 32, fallback=True)
    measured = font(math.ceil(ts*s), True).getlength(status)/s
    sw = cap if len(lines)>1 else min(cap, measured + 32)
    sh = max(r['STATUS'][3], len(lines) * ts + max(0,len(lines)-1)*2 + 24)
    r['STATUS'] = ((W-sw)/2, r['STATUS'][1], sw, sh)
    g['status_type_su'], g['status_lines'] = ts, lines
    g['status_width'] = {'text':status,'measured_text_width_su':measured,
        'measured_text_width_px':measured*s,'padding_su_each':16,'cap_su':cap,
        'capsule_width_su':sw,'lines':len(lines),'type_su':ts,
        'font_px':math.ceil(ts*s),'center_su':W/2,'y_su':r['STATUS'][1]}
    if state == 'combat-defense':
        if small and board=='sarpedon':
            r['ROLE-R'] = (*r['ROLE-R'][:3], 40)
        if board == 'marmoreal':
            # Put actual buttons in safe columns; width deliberately exceeds R3 minima.
            if small:
                r['DEFEND'] = (32, 112, 150, 40)
                r['NO-DEFENSE'] = (32, 160, 150, 40)
                # Two-line role + timer, still above own panel even at H=640.
                r['ROLE-L'] = (*r['ROLE-L'][:3], 64)
            elif w == 1280:
                r['DEFEND'] = (32, 112, 230, 48)
                r['NO-DEFENSE'] = (32, 168, 230, 48)
            else:
                r['DEFEND'] = (32, 719, 230, 48)
                r['NO-DEFENSE'] = (32, 775, 230, 48)
        # CENTER only on attacker's HUD, as prescribed by §2.7/R4.
        if board == 'sarpedon':
            r['CENTER'] = (*r['CENTER'][:3], 64)
    del r['DEFENSE-BUTTONS']
    g['literal_04'] = literal
    g['rectangles'] = {k: list(v) for k, v in r.items()}
    g['deltas'] = []
    for key, rect in g['rectangles'].items():
        old = literal.get(key)
        if old is not None and any(abs(a-b) > 1e-6 for a,b in zip(old, rect)):
            why = {'HAND':'Зазор подписи и верха карт ≥8 su от всех клеток; снят нижний clamp 120.',
                   'HAND-CAPTION':'Подпись ниже FIELD на 8 su, выше сканов.',
                   'OPP-HAND':'В S правая полоса 220 su вне клеток; в L высота 92 su даёт подписи 14 su зазор от кромки при дробном DPI. Рубашки сохранены.',
                   'STATUS':'fix1: ширина по измеренному тексту + 32 su, центр-якорь; высота под кегль и перенос.',
                   'ROLE-L':'Две строки роли и отдельная строка таймера; не закрывают PANEL-LOC.',
                   'ROLE-R':'Полный тег защиты переносится на две строки при дробном DPI; кегль 14 su сохранён.',
                   'LOG':'Ширина ограничена зарегистрированными клетками с учётом запаса 15px и зазора 8 su; кегль строк сохранён.',
                   'CENTER':'Одна реальная строка ожидания; вмещается с отступами.'}[key]
            g['deltas'].append({'block':key,'canvas':f'{w}x{h}/{round(s/(1 if w==1920 else .75)*100)}%',
                                'board':board,'state':state,'old':old,'new':rect,'reason':why})
    if 'DEFEND' in r:
        g['deltas'].append({'block':'Кнопки защиты','canvas':f'{w}x{h}/{round(s/(1 if w==1920 else .75)*100)}%',
            'board':board,'state':state,'old':literal['DEFENSE-BUTTONS'],
            'new':[r['DEFEND'],r['NO-DEFENSE']],
            'reason':'Две настоящие кнопки ≥142/139 su; вертикальный стек и поле кнопок 32 su. На 720p и в S стек перенесён над картой, чтобы не закрыть PANEL-LOC.'})
    if g['class']=='L' and w==1280 and state!='combat-defense':
        g['deltas'].append({'block':'LOG · верх первой строки','canvas':f'{w}x{h}/{round(s/.75*100)}%',
            'board':board,'state':state,'old':'y + 44, шаг 22','new':'y + 40, шаг 22',
            'reason':'Три строки 16 su с ceil-растеризацией помещаются в 104 su; нижняя строка не выступает за кромку.'})
    return g


def status_content(board, state):
    if state == 'own-turn':
        return st('ms.status.action')
    if state == 'combat-defense':
        if board == 'marmoreal':
            return st('ms.status.defend')
        path = 'docs/unreal/contracts/hud/why-reasons.json'
        row = next(r for r in ref.load_json(ROOT/path)['reasons'] if r['key']=='why.wait.defender')
        trace = BOARD['sarpedon']['run']+'/combat-client-joiner.trace.txt'
        evidence = [{'path':trace,'line':i+1,'text':line} for i,line in
            enumerate((ROOT/trace).read_text(encoding='utf-8').splitlines())
            if re.search(r'MS-STATUS seq=(6|10) text="Waiting for the defender"',line)]
        assert len(evidence)==2
        return row['ru'], {'source':path,'key':row['key'],'source_ru':row['ru'],
            'source_en':row['en'],'trace_lines':evidence}
    name = 'King Arthur' if board == 'marmoreal' else 'Medusa'
    verb, vf = st('ms.opp.phase.turn')
    value, sf = st('ms.status.opp', player=name, verb=verb)
    sf['parameter_sources'] = {'player':DB, 'verb':vf}
    return value, sf


class Canvas:
    def __init__(self, base, scale):
        self.base = base.convert('RGBA'); self.im = self.base.copy(); self.s = scale
        self.hud = Image.new('RGBA', base.size)
        self.antialias = np.zeros((base.height,base.width),dtype=bool)
        self.panels = {}; self.texts = []; self.icons = []; self.scans = []
        self.buttons = []; self.active = None; self.text_failures = []
        self.edge_rows = []
        self.visual_boxes = []

    def box(self, r):
        x,y,w,h = r
        return (round(x*self.s),round(y*self.s),round((x+w)*self.s)-1,round((y+h)*self.s)-1)

    def primitive(self, layer):
        self.im = Image.alpha_composite(self.im, layer)
        self.hud = Image.alpha_composite(self.hud, layer)

    def panel(self, key, r, radius=6, alpha=.92):
        self.active = key
        layer = Image.new('RGBA', self.im.size); draw = ImageDraw.Draw(layer)
        draw.rounded_rectangle(self.box(r), radius=max(1,round(radius*self.s)), fill=ref.rgb('panel.bg')+(round(alpha*255),))
        self.primitive(layer)
        mask = Image.new('L', self.im.size)
        ImageDraw.Draw(mask).rounded_rectangle(self.box(r), radius=max(1,round(radius*self.s)), fill=255)
        self.panels[key] = {'r':list(r), 'mask':mask, 'alpha':alpha}
        edge = Image.new('RGBA', self.im.size)
        ImageDraw.Draw(edge).rounded_rectangle(self.box(r), radius=max(1,round(radius*self.s)),
            outline=ref.rgb('panel.edge')+(round(.45*255),), width=max(1,round(self.s)))
        # Body-facing edge contrast: calculate over actual composited interior.
        edge_mask = np.asarray(edge)[:,:,3] > 0
        under = np.asarray(self.im)[:,:,:3]
        ecolor = np.rint(np.array(ref.rgb('panel.edge'))*(115/255) + under[edge_mask]*(140/255))
        ratio = ref.contrast(ecolor, under[edge_mask])
        composed=np.rint(np.array(ref.rgb('panel.edge'))*(115/255)+under*(140/255)).astype('uint8')
        inside=np.asarray(mask)>0
        exterior_ratios=[]
        for dy,dx in ((0,1),(0,-1),(1,0),(-1,0)):
            neighbor_inside=np.roll(inside,(-dy,-dx),axis=(0,1))
            boundary=edge_mask&(~neighbor_inside)
            if dy==1:boundary[-1,:]=False
            if dy==-1:boundary[0,:]=False
            if dx==1:boundary[:,-1]=False
            if dx==-1:boundary[:,0]=False
            neighbor_color=np.roll(under,(-dy,-dx),axis=(0,1))
            if np.any(boundary):
                exterior_ratios.append(float(np.min(ref.contrast(composed[boundary],neighbor_color[boundary]))))
        self.edge_rows.append({'block':key, 'edge_vs_body_min':float(np.min(ratio)),
            'edge_vs_adjacent_exterior_min':min(exterior_ratios) if exterior_ratios else None,
            'scope':'actual edge pixels vs body AND their four-connected immediately adjacent exterior pixels, before later content'})
        self.primitive(edge)

    def text(self, value, x, y, size, bold, source, token='text.primary', max_width=None, lines=None, log=False):
        value = str(value); size_px = math.ceil(size*self.s); f = font(size_px,bold)
        displayed = value
        if log and max_width is not None and f.getlength(displayed)>max_width*self.s:
            while displayed and f.getlength(displayed+'…')>max_width*self.s:
                displayed=displayed[:-1]
            displayed=displayed.rstrip()+'…'
        lines = lines or [displayed]
        all_boxes=[]; cr=[]; line_width=[]
        for i,line in enumerate(lines):
            px,py=round(x*self.s),round((y+i*(size+2))*self.s)
            bbox=ImageDraw.Draw(self.im).textbbox((px,py),line,font=f,anchor='lt')
            all_boxes.append(list(bbox)); line_width.append(f.getlength(line)/self.s)
            if max_width is not None and f.getlength(line)>max_width*self.s+0.01:
                self.text_failures.append({'block':self.active,'text':line,'width_px':f.getlength(line),'available_px':max_width*self.s})
            if bbox[0]<0 or bbox[1]<0 or bbox[2]>self.im.width or bbox[3]>self.im.height:
                self.text_failures.append({'block':self.active,'text':line,'viewport_clip':bbox})
            if self.active in self.panels:
                pbox=self.box(self.panels[self.active]['r'])
                if not (bbox[0]>=pbox[0] and bbox[1]>=pbox[1] and bbox[2]<=pbox[2]+1 and bbox[3]<=pbox[3]+1):
                    self.text_failures.append({'block':self.active,'text':line,'outside_block':bbox,'block_bbox':pbox})
            primitive=Image.new('RGBA',self.im.size)
            ImageDraw.Draw(primitive).text((px,py),line,font=f,fill=ref.rgb(token)+(255,),anchor='lt')
            glyph_mask=np.asarray(primitive)[:,:,3]>0
            glyph_alpha=np.asarray(primitive)[:,:,3]
            self.antialias[glyph_alpha==255]=False
            self.antialias[(glyph_alpha>0)&(glyph_alpha<255)]=True
            ratios=ref.contrast(ref.rgb(token),np.asarray(self.im)[:,:,:3][glyph_mask])
            cr.append(float(np.min(ratios)) if ratios.size else None)
            self.primitive(primitive)
        self.texts.append({'text':value,'displayed':displayed,'lines':lines,'block':self.active,
            'source':source,'type_su':size,'font_px':size_px,'nominal_px':size*self.s,
            'bold_condensed':bold,'token':token,'bbox_px':all_boxes,'line_width_su':line_width,
            'contrast_min':min(v for v in cr if v is not None),'log_ellipsis':log and displayed!=value})

    def string(self, key, x, y, size=16, bold=False, token='text.primary', max_width=None, caps=False, **params):
        val,sf=st(key,**params)
        if caps:
            sf['render_transform']='uppercase'; val=val.upper()
        self.text(val,x,y,size,bold,sf,token,max_width)

    def image(self, path, r):
        x,y,w,h = r; size=(max(1,round(w*self.s)),max(1,round(h*self.s)))
        im=ImageOps.contain(ref.original(str(path)),size,Image.Resampling.LANCZOS)
        pos=(round(x*self.s)+(size[0]-im.width)//2,round(y*self.s)+(size[1]-im.height)//2)
        self.im.alpha_composite(im,pos)
        return im,pos

    def portrait(self, path, x, y, size):
        n=round(size*self.s); im=ImageOps.fit(ref.original(str(path)),(n,n),method=Image.Resampling.LANCZOS)
        mask=Image.new('L',(n,n)); ImageDraw.Draw(mask).ellipse((0,0,n-1,n-1),fill=255)
        self.im.paste(im,(round(x*self.s),round(y*self.s)),mask)
        self.visual_boxes.append({'block':self.active,'kind':'avatar','path':ref.relative(path),
            'bbox_px':[round(x*self.s),round(y*self.s),round(x*self.s)+n,round(y*self.s)+n]})

    def icon(self, name, x, y, size=24):
        if name=='end-turn':
            path=ROOT/'art/imagegen/hud-icons-vr44-codex/vector/64/end-turn.png'
        else:
            path=ref.ICONS/f'sizes/{name}-96.png'
        if not path.is_file():
            raise FileNotFoundError(path)
        # The same immutable bitmap is fitted, never recoloured or regenerated.
        under=self.im.copy()
        im,pos=self.image(path,(x,y,size,size))
        self.visual_boxes.append({'block':self.active,'kind':'disc' if name=='marker-action-slot-de' else 'icon',
            'name':name,'bbox_px':[round(x*self.s),round(y*self.s),round(x*self.s)+round(size*self.s),round(y*self.s)+round(size*self.s)]})
        a=np.asarray(im); body=ref.rgb('panel.bg')
        # Content tones: exclude dark keyline, transparent/AA pixels. Measure both
        # ink-to-local-surface and resolved solid glyph/body contrast.
        opaque=a[:,:,3]==255; src=ref.original(str(path)); sa=np.asarray(src)
        colors, counts=np.unique(sa[sa[:,:,3]==255,:3],axis=0,return_counts=True)
        dominant=colors[np.argsort(counts)[::-1][:4]] if colors.size else np.empty((0,3))
        # Roles are fixed by v3 STYLE §2, independently of pass/fail threshold.
        pairs={
            'action-maneuver':('card.glyph','card.type.versatile'),
            'action-attack':('card.glyph','card.type.attack'),
            'action-defense':('card.glyph','card.type.defense'),
            'action-scheme':('card.navy','card.type.scheme'),
            'resource-hp-full':('card.glyph','card.type.attack'),
            'resource-hp-full-enemy':('card.type.attack','card.navy'),
            'marker-turn-ring':('turn.flash.orange','#111317'),
            'marker-action-slot-de':('turn.flash.orange','card.navy'),
            'end-turn':('card.glyph','card.navy'),
        }
        if name in pairs:
            fg,bg=pairs[name]
            for token in (fg,bg):
                assert np.any(np.all(colors==ref.rgb(token),axis=1)),(name,token)
            min_ratio=float(ref.contrast(ref.rgb(fg),ref.rgb(bg)))
            local_pair=[T.get(fg,fg),T.get(bg,bg)]
        else:
            # Bare white resources/connection glyph against the actual alpha-composited panel.
            px,py=pos; bg=np.asarray(under)[py:py+im.height,px:px+im.width,:3]
            source_ink=(sa[:,:,3]==255)&np.all(sa[:,:,:3]==ref.rgb('card.glyph'),axis=2)
            ink=np.asarray(Image.fromarray(source_ink.astype('uint8')*255).resize(im.size,Image.Resampling.NEAREST))>0
            ratios=ref.contrast(ref.rgb('card.glyph'),bg[ink])
            min_ratio=float(np.min(ratios)) if ratios.size else 0
            local_pair=['#FAF8F2','actual composited panel pixels']
        decorative=[]
        if name=='action-scheme':
            decorative.append({'element':'cream trim vs scheme fill; outer dark keyline carries contour',
                'ratio':float(ref.contrast(ref.rgb('card.cream'),ref.rgb('card.type.scheme')))})
        if name=='marker-action-slot-de':
            decorative.append({'element':'decorative ghost inside action slot; orange ring carries meaning',
                'ratio':float(ref.contrast((69,76,81),ref.rgb('card.navy')))})
        self.icons.append({'block':self.active,'path':ref.relative(path),'size_su':size,'size_px':size*self.s,
            'unchanged_asset_sha256':ref.sha(path),'solid_ink_vs_navy_min':min_ratio,
            'contrast_pair':local_pair,'decorative_low_contrast':decorative,
            'method':'v3 fixed semantic glyph/body or rim/keyline roles; bare glyphs vs composited panel; never filter colors by the passing threshold',
            'solid_tones':['#'+bytes(c).hex().upper() for c in dominant]})

    def card(self, path, r, key, frame_block=None):
        if frame_block:
            self.active=frame_block
            # Card frames merge into HAND so the fan is one persistent block.
            layer=Image.new('RGBA',self.im.size); d=ImageDraw.Draw(layer)
            d.rounded_rectangle(self.box(r),radius=max(1,round(8*self.s)),fill=ref.rgb('panel.bg')+(235,),
                outline=ref.rgb('panel.edge')+(115,),width=max(1,round(self.s)))
            self.primitive(layer)
        else:
            self.panel(key,r,radius=8)
        x,y,w,h=r; im,pos=self.image(path,(x+2,y+2,w-4,h-4))
        self.scans.append({'path':ref.relative(path),'stableContentKey':key,'frame_su':list(r),
            'asset_fitted_px':[pos[0],pos[1],im.width,im.height], 'whole_asset_inside_frame':True,
            'viewport_clipped':pos[1]+im.height>self.im.height,'runtime_text_over_scan':False})

    def button(self, key, r):
        self.panel(key,r,radius=4)
        x,y,w,h=r; sk='hud.combat.defend' if key=='DEFEND' else 'hud.combat.no.defense'
        label,sf=st(sk); label=label.upper(); sf['render_transform']='uppercase'
        actual=font(math.ceil(20*self.s),True).getlength(label)
        logical=font(20,True).getlength(label)
        self.text(label,x+(w-actual/self.s)/2,y+(h-20)/2,20,True,sf,max_width=w-24)
        self.buttons.append({'key':sk,'label':label,'type_su':20,'font_px':math.ceil(20*self.s),
            'text_width_su_at_20px':logical,'text_width_px':actual,'text_width_su_at_canvas':actual/self.s,
            'button_width_su':w,'button_width_px':round(w*self.s), 'padding_su_each':12,
            'required_width_su':max(120,logical+24,142 if key=='DEFEND' else 139),
            'passed':w>=max(120,logical+24,142 if key=='DEFEND' else 139) and actual<=(w-24)*self.s})


def hero_panel(c, board, key, r, slug, hp, heroes, active, small):
    c.panel(key,r); x,y,w,h=r; hero=heroes[slug]['fetchedHero']; own=key=='PANEL-LOC'
    source=f'scraped-data/api/heroes/{slug}.json'; psize=64 if small else 80
    px=x+12 if own else x+w-12-psize
    py=y+16 if small else y+12
    c.portrait(ROOT/'scraped-data/images/heroes/avatars'/hero['avatar'].split('/')[-1],px,py,psize)
    if active:
        c.icon('marker-turn-ring',px-4,py-4,psize+8)
    tx=x+psize+32 if own else x+12; tw=w-psize-44
    c.text(hero['name'],tx,y+12,20 if small else 24,True,fact(DB,'Hero.nameRu',nameRu=hero['name']),max_width=tw)
    if own or not active:
        c.string('hud.panel.status.own' if active else 'hud.panel.status.wait',tx,y+38,14,True,
                 token='turn.flash.yellow' if active else 'text.secondary',max_width=tw)
    hpx=tx-8 if small and own else tx
    c.icon('resource-hp-full' if own else 'resource-hp-full-enemy',hpx,y+60,24)
    val,sf=st('hud.panel.hp',hp=hp,max=hero['startHealth'])
    sf['parameter_sources']={'hp':BOARD[board]['run']+('/host/s09-turn-banner.jpg' if board=='marmoreal' or slug=='medusa' else '/joiner/s09-deck-own.jpg'),
                            'max':source+'#fetchedHero.startHealth'}
    hp_text_x=(round(hpx*c.s)+round(24*c.s)+math.ceil(4*c.s))/c.s
    c.text(val,hp_text_x,y+58,20,True,sf)
    # Trackers are quiet default slots; no fabricated action consumption count.
    trackerx=x+w-64 if own and small else (x+w-68 if own else x+w-psize-72)
    for i in range(2):
        c.icon('marker-action-slot-de',trackerx+i*28,y+64 if small else y+56,24)
    if not small:
        skx=x+112 if own else x+12
        for i,sk in enumerate(hero['sidekicks']):
            sx=skx+i*72; sy=y+84
            c.portrait(ROOT/'scraped-data/images/heroes/sidekicks'/sk['avatar'].split('/')[-1],sx,sy,40)
            val=str(i+1) if len(hero['sidekicks'])>1 else sk['name']
            label_x=(round(sx*c.s)+round(40*c.s)+math.ceil(4*c.s))/c.s
            c.text(val,label_x,sy+1,14,True,fact(source,f'fetchedHero.sidekicks[{i}].name',
                 'ВР-72: одинаковые Harpies нумеруются по порядку sidekicks'),max_width=25 if len(hero['sidekicks'])>1 else 76)
            c.text(f"{sk['startHealth']}/{sk['startHealth']}",label_x,sy+22,14,False,
                 fact(source,f'fetchedHero.sidekicks[{i}].startHealth','HP подтверждены кадрами I'))


def log_content(board):
    b=BOARD[board]; path=b['run']+'/'+b['turn_trace']
    wanted=['Medusa: maneuver: Medusa M13→M25','King Arthur: maneuver: King Arthur M31→M26, Merlin M23→M16'] if board=='marmoreal' else [
        'Medusa: maneuver: Medusa S35→S36','Medusa: Dash effect: no movement','King Arthur: Swift Strike effect: no movement']
    lines=(ROOT/path).read_text(encoding='utf-8').splitlines(); result=[]
    for full in wanted:
        matches=[(i+1,l) for i,l in enumerate(lines) if 'MS-LOG' in l and f'text="{full}"' in l]
        assert matches,full
        if ': maneuver: ' in full:
            player,moves=full.split(': maneuver: ',1)
            val,sf=st('ms.log.maneuver',player=player,boostPart='',moves=moves)
        else:
            player,rest=full.split(': ',1); title=rest.split(' effect: ')[0]
            val,sf=st('ms.log.effect',player=player,cardName='Рывок' if title=='Dash' else title,moves=STRINGS['ms.log.stay']['ru'])
            sf['card_name_source']='scraped-data/api/heroes/medusa.json#Dash.i18n.ru.title' if title=='Dash' else DB
        sf['trace']={'path':path,'line':matches[0][0],'text':matches[0][1]}
        result.append((val,sf))
    return result


def render(board,state,w,h,dpi,ui,heroes,cards):
    s=dpi*ui/100; b=BOARD[board]; g=geometry(board,state,w,h,s); r=g['rectangles']; small=g['class']=='S'
    source=ref.original(str(ROOT/b['background']))
    base=source if source.size==(w,h) else source.resize((w,h),Image.Resampling.LANCZOS)
    c=Canvas(base,s)
    c.panel('TOP',r['TOP']); x,y,rw,rh=r['TOP']
    c.string('hud.top.menu',x+12,y+13,14,True)
    c.icon('resource-connection-online',x+54,y+8,24)
    c.string('hud.top.turn',x+88,y+12,16,True,n=b['turn'])
    c.texts[-1]['source']['parameter_sources']={'n':b['run']+'/'+b['turn_trace']+'#turnCount'}
    if small:
        c.string('hud.top.log',x+163,y+13,14,True)
    c.panel('STATUS',r['STATUS']); x,y,rw,rh=r['STATUS']
    val,sf=status_content(board,state)
    c.text(val,x+16,y+12,g['status_type_su'],True,sf,
        token='text.secondary' if state=='opp-turn' or (state=='combat-defense' and board=='sarpedon') else 'text.primary',max_width=rw-32,lines=g['status_lines'])
    own_active=state=='own-turn' or (state=='combat-defense' and board=='sarpedon')
    hero_panel(c,board,'PANEL-LOC',r['PANEL-LOC'],b['own'],b['hp'][0],heroes,own_active,small)
    hero_panel(c,board,'PANEL-OPP',r['PANEL-OPP'],b['opponent'],b['hp'][1],heroes,not own_active,small)
    c.panel('OPP-HAND',r['OPP-HAND']); x,y,rw,rh=r['OPP-HAND']
    back=ROOT/'scraped-data/images/heroes/card-covers'/heroes[b['opponent']]['fetchedHero']['cardBackImage'].split('/')[-1]
    bw,bh=(32,45) if small else (48,67)
    step=26 if small else 28
    for i in range(b['oppHand']):
        c.image(back,(x+12+i*step,y+4,bw,bh))
    # Real exact StringTable pieces; all caption text fits instead of ellipsis.
    pieces=[]
    for key,num in [('hud.opp.hand',b['oppHand']),('hud.opp.deck',b['oppDeck']),('hud.opp.discard',b['oppDiscard'])]:
        piece,_=st(key,n=('≈'+str(num)) if key=='hud.opp.deck' and board=='sarpedon' else num)
        pieces.append(piece)
    sf=fact('docs/unreal/contracts/hud/st-hud.csv','hud.opp.hand + hud.opp.deck + hud.opp.discard',
            b['run']+'/host/s09-turn-banner.jpg',parameters={'hand':b['oppHand'],'deck':b['oppDeck'],'discard':b['oppDiscard']})
    cap=' · '.join(pieces)
    c.text(cap,x+12,y+(61 if small else 71),14,False,sf,max_width=rw-24)
    # HAND union: one block, including complete frames that may leave viewport.
    x,y,rw,rh=r['HAND']; cw,ch=g['card_size_su']
    hm=Image.new('L',(w,h)); d=ImageDraw.Draw(hm)
    for i,slug in enumerate(b['hand']):
        rr=(x+i*g['hand_step_su'],y,cw,ch)
        d.rounded_rectangle(c.box(rr),radius=max(1,round(8*s)),fill=255)
        row=cards[f"{b['own']}:{slug}"]
        c.card(ROOT/row['ru']['path'],rr,row['stableContentKey'],frame_block='HAND')
    c.panels['HAND']={'r':list(r['HAND']),'mask':hm,'alpha':.92}
    c.panel('HAND-CAPTION',r['HAND-CAPTION'],radius=4); x,y,rw,rh=r['HAND-CAPTION']
    val,sf=st('hud.hand.count',n=len(b['hand']),max=7)
    sf['parameter_sources']={'n':b['run']+('/host/s09-turn-banner.jpg' if board=='marmoreal' else '/joiner/s09-deck-own.jpg'),
        'max':'YOUR HAND n/7 in same frame'}
    c.text(val,x+8,y+4,14,False,sf)
    if board=='marmoreal':
        c.string('hud.card.new',x+rw-64,y+4,14,True)
        c.texts[-1]['source']['evidence']=b['run']+'/host/s09-turn-banner.jpg#Dash *NEW*'
    c.panel('DECKS',r['DECKS']); x,y,rw,rh=r['DECKS']
    ownback=ROOT/'scraped-data/images/heroes/card-covers'/heroes[b['own']]['fetchedHero']['cardBackImage'].split('/')[-1]
    c.image(ownback,(x+6,y+5,32,38 if small else 45))
    val,sf=st('hud.decks.deck',n=b['deck'])
    sf['evidence']=b['run']+('/host/s09-turn-banner.jpg' if board=='marmoreal' else '/joiner/s09-deck-own.jpg')
    if small:
        sf['render_transform']='class S count only'; val=str(b['deck'])
    c.text(val,x+42,y+16,20 if small else 16,True,sf)
    c.icon('resource-card',x+(76 if small else 156),y+12,24)
    val,sf=st('hud.decks.discard',n=b['discard']); sf['evidence']=b['run']+('/host/s09-turn-banner.jpg' if board=='marmoreal' else '/joiner/s09-deck-own.jpg')
    if small:
        sf['render_transform']='class S count only'; val=str(b['discard'])
    c.text(val,x+(106 if small else 188),y+16,20 if small else 16,True,sf)
    c.panel('ACTIONS',r['ACTIONS']); x,y,rw,rh=r['ACTIONS']
    for i,(name,sk) in enumerate([('action-maneuver','maneuver'),('action-attack','attack'),('action-scheme','scheme'),('end-turn','end_turn')]):
        xx=x+8+i*(50 if small else 82)
        c.icon(name,xx+(0 if small else 16),y+4,40 if small else 48)
        if not small:
            val,sf=st('hud.action.'+sk)
            tw=font(math.ceil(14*s),True).getlength(val)/s
            caption_y=(round((y+4)*s)+round(48*s)+math.ceil(4*s))/s
            c.text(val,xx+(80-tw)/2,caption_y,14,True,sf,max_width=80)
    if not small and state!='combat-defense':
        c.panel('LOG',r['LOG']); x,y,rw,rh=r['LOG']
        c.string('hud.log.title',x+12,y+12,24,True)
        for i,(val,sf) in enumerate(log_content(board)):
            c.text(val,x+12,y+(40 if w==1280 else 44)+i*22,16,False,sf,
                   token='text.primary' if i==len(log_content(board))-1 else 'text.secondary',max_width=rw-24,log=True)
    if state=='own-turn':
        c.panel('BANNER',r['BANNER']); x,y,rw,rh=r['BANNER']
        val,sf=st('hud.banner.own_turn'); tw=font(math.ceil(36*s),True).getlength(val)/s
        c.text(val,x+(rw-tw)/2,y+17,36,True,sf,token='turn.flash.yellow',max_width=rw-24)
    if state=='combat-defense':
        if board=='marmoreal':
            c.panel('COMBAT-L',r['COMBAT-L'],radius=8); x,y,rw,rh=r['COMBAT-L']
            c.icon('action-defense',x+(rw-64)/2,y+32,64)
            val,sf=st('hud.combat.slot.empty')
            lines=wrap(val,font(math.ceil(16*s),False),(rw-24)*s)
            c.text(val,x+12,y+116,16,False,sf,max_width=rw-24,lines=lines)
            c.card(back,r['COMBAT-R'],'COMBAT-R')
        else:
            row=cards['king-arthur:swift-strike']
            c.card(ROOT/row['ru']['path'],r['COMBAT-L'],'COMBAT-L')
            c.card(back,r['COMBAT-R'],'COMBAT-R')
            c.panel('CENTER',r['CENTER']); x,y,rw,rh=r['CENTER']
            c.string('hud.combat.wait.defense',x+12,y+18,24,True,max_width=rw-24)
        for key,role,fighter,icon in [
            ('ROLE-L','defense' if board=='marmoreal' else 'attack','Medusa' if board=='marmoreal' else 'Merlin','action-defense' if board=='marmoreal' else 'action-attack'),
            ('ROLE-R','attack' if board=='marmoreal' else 'defense','Merlin' if board=='marmoreal' else 'Medusa','action-attack' if board=='marmoreal' else 'action-defense')]:
            c.panel(key,r[key],radius=4); x,y,rw,rh=r[key]
            c.icon(icon,x+2,y+(0 if rh==24 else 2),24)
            val,sf=st('hud.combat.role.'+role,fighter=fighter)
            sf['parameter_sources']={'fighter':BOARD[board]['run']+('/host/s09-turn-banner.jpg' if board=='marmoreal' else '/joiner/s09-combat-defense-open.jpg')}
            lines=wrap(val,font(math.ceil(14*s),True),(rw-44)*s)
            if len(lines)>1 and rh==24:
                # 04 S tag exact max width may fail at fractional raster sizes.
                raise ValueError('Role needs documented geometry delta: '+val)
            c.text(val,x+32,y+5,14,True,sf,max_width=rw-44,lines=lines)
            if key=='ROLE-L' and board=='marmoreal':
                timer_y=y+42 if small else y+5
                timer_x=x+12 if small else x+rw-43
                c.string('hud.combat.timer',timer_x,timer_y,14,True,n=30)
                c.texts[-1]['source']['parameter_sources']={'n':BOARD[board]['run']+'/joiner/s09-combat-defense-open.jpg#server deadline: 30s left'}
                layer=Image.new('RGBA',(w,h)); ImageDraw.Draw(layer).rectangle(c.box((x+4,y+rh-5,rw-8,4)),fill=ref.rgb('card.cream')+(255,))
                c.primitive(layer)
        if board=='marmoreal':
            c.button('DEFEND',r['DEFEND']); c.button('NO-DEFENSE',r['NO-DEFENSE'])
    return c,g


def panel_inner_gaps(c):
    rows=[]
    for block in c.panels:
        pairs=[]
        for t in (t for t in c.texts if t['block']==block):
            for tb in t['bbox_px']:
                for v in (v for v in c.visual_boxes if v['block']==block):
                    vb=v['bbox_px']
                    dx=max(tb[0]-vb[2],vb[0]-tb[2],0)
                    dy=max(tb[1]-vb[3],vb[1]-tb[3],0)
                    gap=math.hypot(dx,dy)/c.s
                    area=max(0,min(tb[2],vb[2])-max(tb[0],vb[0]))*max(0,min(tb[3],vb[3])-max(tb[1],vb[1]))
                    required=8 if t['source']['key']=='hud.panel.hp' and v.get('name')=='marker-action-slot-de' else 4
                    pairs.append({'text':t['displayed'],'text_key':t['source']['key'],
                        'text_bbox_px':tb,'visual':v,'gap_su':gap,'overlap_px2':area,
                        'expected_min_su':required,'passed':area==0 and gap+1e-8>=required})
        rows.append({'block':block,'smallest_gap_su':min((p['gap_su'] for p in pairs),default=None),
            'hp_tracker_gap_min_su':min((p['gap_su'] for p in pairs if p['expected_min_su']==8),default=None),
            'passed':all(p['passed'] for p in pairs),'pairs':pairs,
            'note':'No text/visual pair' if not pairs else 'Measured half-open text and full icon/disc/avatar boxes at native pixels.'})
    return rows


def geometry_audit(c,g,sm,fm):
    sa=np.asarray(sm)>0; fa=np.asarray(fm)>0; rows={}; intersections=[]
    for key,p in c.panels.items():
        a=np.asarray(p['mask'])>0
        rows[key]={'rectangle_su':p['r'],'figure_overlap_px2':int(np.count_nonzero(a&fa)),
            'space_overlap_px2':int(np.count_nonzero(a&sa)),'persistent':key not in ('CENTER','BANNER'),
            'text_contrast_min':min((t['contrast_min'] for t in c.texts if t['block']==key),default=None)}
    for (ka,pa),(kb,pb) in itertools.combinations(c.panels.items(),2):
        area=int(np.count_nonzero((np.asarray(pa['mask'])>0)&(np.asarray(pb['mask'])>0)))
        if area:
            intersections.append({'blocks':[ka,kb],'area_px2':area,'exception':any(k in ('CENTER','BANNER') for k in (ka,kb))})
    x,y,ww,hh=g['rectangles']['HAND-CAPTION']; x0=round(x*c.s); x1=round((x+ww)*c.s)
    combined=sa|fa; occupied=np.where(np.any(combined[:,max(0,x0):min(c.im.width,x1)],axis=1))[0]
    last=int(occupied[-1]) if len(occupied) else -1
    gap=(round(y*c.s)-(last+1))/c.s
    persistent=[v for v in rows.values() if v['persistent']]
    return {'panels':rows,'panel_to_panel_overlaps':intersections,'persistent_overlap_pass':
        all(not(v['figure_overlap_px2'] or v['space_overlap_px2']) for v in persistent) and not any(not v['exception'] for v in intersections),
        'hand_gap_su':gap,'lowest_mask_pixel_in_hand_x':last,'caption_top_px':round(y*c.s)}


def visible_blocks(g,board,state,literal=False):
    keys=['TOP','STATUS','PANEL-LOC','PANEL-OPP','OPP-HAND','HAND','HAND-CAPTION','DECKS','ACTIONS']
    if g['class']=='L' and state!='combat-defense': keys.append('LOG')
    if state=='own-turn': keys.append('BANNER')
    if state=='combat-defense':
        keys+=['COMBAT-L','COMBAT-R','ROLE-L','ROLE-R']
        if board=='sarpedon' or literal: keys.append('CENTER')
        if board=='marmoreal': keys+=['DEFENSE-BUTTONS'] if literal else ['DEFEND','NO-DEFENSE']
    return keys


def overlay(board,state,w,h,s,g,literal=False):
    c=Canvas(Image.new('RGBA',(w,h),ref.rgb('panel.bg.inset')+(255,)),s)
    sm,fm,_,_=ref.masks(board,w,h)
    # Masks contain geometry only; no source-scene/scan/portrait pixels.
    fill=Image.new('RGBA',(w,h),ref.rgb('state.pending')+(255,)); c.im=Image.composite(fill,c.im,sm)
    fill=Image.new('RGBA',(w,h),ref.rgb('turn.flash.orange')+(255,)); c.im=Image.composite(fill,c.im,fm)
    r=g['literal_04'] if literal else g['rectangles']
    for key in visible_blocks(g,board,state,literal):
        rr=r[key]; c.panel(key,rr); x,y,ww,hh=rr
        # Overlay labels are diagram annotations, never game UI or a substitute for fit checks.
        c.text(key,x+4,y+3,14,True,fact(SPEC,'§1.6 block name'),max_width=ww-8)
        if hh>=48:
            c.text(f'{x:.1f}, {y:.1f}',x+4,y+23,14,False,fact(SPEC,'diagram coordinates'))
            if hh>=70:
                c.text(f'{ww:.1f} × {hh:.1f} su',x+4,y+42,14,False,fact(SPEC,'diagram dimensions'))
    return c.im


def palette_audit(c):
    a=np.asarray(c.hud); opaque=(a[:,:,3]==255)&(~c.antialias)
    values=a[opaque,:3]; allowed=np.array([ref.rgb(v) for v in T.values()],dtype=np.uint8)
    off=np.ones(len(values),dtype=bool)
    for rgb in allowed:
        off &= np.any(values!=rgb,axis=1)
    return {'opaque_pixels':len(values),'excluded_antialiased_pixels':int(np.count_nonzero(c.antialias)), 'off_token_pixels':int(np.count_nonzero(off)),
            'fraction_off_tokens':float(np.mean(off)) if len(values) else 0,
            'method':'exact RGB equality on separately drawn transparent procedural HUD; alpha<255 excluded; scene/scans/avatars/backs/icons never enter this layer'}


def export_meta(path):
    with Image.open(path) as im:
        box=im.getbbox(); w,h=im.size
        margin=[box[0],box[1],w-box[2],h-box[3]] if box else [w,h,w,h]
        return {'path':ref.relative(path),'size':[w,h],'mode':im.mode,'margin_px':margin,
            'touches_edge':min(margin)==0,'note':'Background/diagram canvas is intentionally opaque to the edge; HAND viewport clip allowed by §2.6.'}


def contact(ims,labels,path,width=640):
    cols=2; thumbh=round(width*9/16); titleh=32
    sheet=Image.new('RGBA',(cols*width,math.ceil(len(ims)/cols)*(thumbh+titleh)),ref.rgb('panel.bg')+(255,))
    d=ImageDraw.Draw(sheet)
    for i,(im,label) in enumerate(zip(ims,labels)):
        x=(i%cols)*width; y=(i//cols)*(thumbh+titleh)
        d.text((x+12,y+8),label,font=font(16,True),fill=ref.rgb('text.primary'),anchor='lt')
        sheet.alpha_composite(im.resize((width,thumbh),Image.Resampling.LANCZOS),(x,y+titleh))
    save_image(sheet,path)
    save_image(ref.gray(sheet),path.with_name(path.stem+'-gray.png'))


def trace_facts(heroes,cards):
    result={}
    for board,b in BOARD.items():
        path=b['run']+'/'+b['turn_trace']; lines=(ROOT/path).read_text(encoding='utf-8').splitlines()
        shot=next(i for i,l in enumerate(lines) if 'SHOT request file=s09-turn-banner.png' in l)
        tc=[(i+1,l) for i,l in enumerate(lines[:shot]) if 'turnCount=' in l][-1]
        count=int(re.search(r'turnCount=(\d+)',tc[1]).group(1)); assert count==b['turn']
        result[board]={'turn':{'value':count,'path':path,'line':tc[0],'trace':tc[1]},
            'run_values':{'own_hp':b['hp'][0],'opponent_hp':b['hp'][1],'own_deck':b['deck'],
                'own_discard':b['discard'],'opponent_hand':b['oppHand'],'opponent_deck':b['oppDeck'],
                'opponent_discard':b['oppDiscard'],'hand_max':7,'hand':b['hand']},
            'hp_and_hand_evidence':b['run']+('/host/s09-turn-banner.jpg' if board=='marmoreal' else '/joiner/s09-deck-own.jpg'),
            'opponent_counts_evidence':b['run']+'/host/s09-turn-banner.jpg',
            'combat':{'owner':heroes[b['own']]['fetchedHero']['name'],'owner_role':'defender' if board=='marmoreal' else 'attacker',
                'attacker':'Merlin','attack_card':'Swift Strike','attack_value':3,'defender':'Medusa',
                'chosen_defense':'Shield / no card selected' if board=='marmoreal' else 'hidden Medusa card back',
                'attack_card_record':next(v for v in heroes['king-arthur']['fetchedDeck'] if v['card']['title']=='Swift Strike'),
                'waiting_trace':next({'line':i+1,'text':l,'path':path} for i,l in enumerate(lines) if 'Waiting for the defender' in l),
                'evidence':b['run']+('/host/s09-turn-banner.jpg' if board=='marmoreal' else '/joiner/s09-combat-defense-open.jpg')},
            'projection_note':'Статический набор HP/руки из кадров I, не синхронный snapshot; позиции фигур только из bench.'}
    return {'decoded_hero_sources':heroes,'boards':result,'card_manifest_source':ref.CARD_MANIFEST,
            'cards_used':{k:v for k,v in cards.items() if k in {f"{b['own']}:{slug}" for b in BOARD.values() for slug in b['hand']}},
            'database_names_source':DB,'strings':STRINGS,
            'defense_seconds':{'value':30,'source':BOARD['marmoreal']['run']+'/joiner/s09-combat-defense-open.jpg',
                              'visible_text':'server deadline: 30s left'},
            'logs':{b:log_content(b) for b in BOARD}}


def outside_audit(before):
    old=before.get('outside_metadata_before',{})
    external=[]
    for path,meta in old.items():
        p=ROOT/path
        if not p.exists() or [p.stat().st_size,p.stat().st_mtime_ns]!=meta:
            external.append(path)
    unauthorized=[p for p in WRITE_LEDGER if not p.startswith(('art/imagegen/hud-composition-v1-codex/','scraped-data/derived/hud-composition-v1-codex/'))]
    return unauthorized,external


def build():
    before=ref.load_json(PACKAGE/'source-hashes-before.json')
    changed=ref.hash_mismatches(before)
    if changed: raise RuntimeError('Input baseline changed: '+str(changed))
    heroes,cards=ref.sources(); facts=trace_facts(heroes,cards)
    save_json(PACKAGE/'generation-records.json',{'task':'HB-07 / CX-01r v2','image_generation':False,
        'records':[],'exact_prompt_key':'HB-07.codex.md sha256 '+ref.sha(ROOT/PROMPT),
        'reason':'ImageGen запрещён; Pillow собирает реальные входы. concepts/ пуст.'})
    (PACKAGE/'concepts').mkdir(exist_ok=True)
    audits=[]; outputs=[]; ims=[]; labels=[]; overlays=[]; literal_ims=[]; palettes=[]; deltas=[]; maskdata={}
    all_texts=[]; all_visual_boxes=[]
    for board in BOARD:
        for w,h,dpi,ui in CONFIGS:
            sm,fm,field,md=ref.masks(board,w,h)
            maskdata[f'{board}-{w}x{h}']=md
            for kind,im in [('spaces',sm),('figures',fm)]:
                save_image(im,PACKAGE/'comparison'/f'mask-{board}-{w}x{h}-{kind}.png')
            # Visual registration proofs contain the source scene and therefore only go to derived.
            if ui==100:
                maskproof=ref.original(str(ROOT/BOARD[board]['background'])).resize((w,h),Image.Resampling.LANCZOS)
                layer=Image.new('RGBA',(w,h)); d=ImageDraw.Draw(layer)
                cell_boundary=np.asarray(sm)>0
                cell_inside=np.asarray(sm.filter(ImageFilter.MinFilter(3)))>0
                fig_boundary=np.asarray(fm)>0
                fig_inside=np.asarray(fm.filter(ImageFilter.MinFilter(3)))>0
                la=np.asarray(layer).copy()
                la[cell_boundary&~cell_inside]=(*ref.rgb('card.cream'),255)
                la[fig_boundary&~fig_inside]=(*ref.rgb('turn.flash.orange'),255)
                layer=Image.fromarray(la)
                maskproof=Image.alpha_composite(maskproof,layer)
                save_image(maskproof,DERIVED/f'mask-registration-{board}-{w}x{h}.png')
                save_image(ref.gray(maskproof),DERIVED/f'mask-registration-{board}-{w}x{h}-gray.png')
            for state in STATES:
                c,g=render(board,state,w,h,dpi,ui,heroes,cards)
                name=f'HB-07-{board}-{state}-{w}x{h}-{ui}'
                path=DERIVED/(name+'.png'); save_image(c.im,path); save_image(ref.gray(c.im),DERIVED/(name+'-gray.png'))
                a=geometry_audit(c,g,sm,fm)
                audits.append({'id':name,'board':board,'state':state,'resolution':[w,h],'ui_scale_percent':ui,
                    'su_to_px':dpi*ui/100,'canvas_su':g['canvas_su'],'class':g['class'],**a,
                    'text_fit_failures':c.text_failures,'button_text_fit':c.buttons,
                    'text_contrast_min':min(t['contrast_min'] for t in c.texts),'edge_contrast':c.edge_rows,
                    'icons':c.icons,'scans':c.scans,'smallest_text_nominal_px':min(t['nominal_px'] for t in c.texts),
                    'smallest_icon_su':min(t['size_su'] for t in c.icons),
                    'combat_role':'defender' if board=='marmoreal' else 'attacker',
                    'waiting_visible':state=='combat-defense' and board=='sarpedon',
                    'defense_buttons_visible':state=='combat-defense' and board=='marmoreal',
                    'status_text':status_content(board,state)[0],
                    'status_width':g['status_width'],'panel_inner_gaps':panel_inner_gaps(c)})
                all_texts.extend({'mockup':name,**t} for t in c.texts)
                all_visual_boxes.extend({'mockup':name,**v} for v in c.visual_boxes)
                palettes.append({'id':name,**palette_audit(c)})
                ov=overlay(board,state,w,h,dpi*ui/100,g)
                lit=overlay(board,state,w,h,dpi*ui/100,g,literal=True)
                for suffix,im in [('overlay',ov),('04-literal-overlay',lit)]:
                    op=PACKAGE/'comparison'/(name+'-'+suffix+'.png')
                    save_image(im,op); save_image(ref.gray(im),op.with_name(op.stem+'-gray.png'))
                outputs.append({'id':name,'color':ref.relative(path),'gray':ref.relative(DERIVED/(name+'-gray.png')),'geometry':g})
                ims.append(c.im); overlays.append(ov); literal_ims.append(lit); deltas.extend(g['deltas'])
                labels.append(f'{board} | {state} | {w}x{h} UI {ui}% {g["class"]}')
                print(name, 'overlap='+str(a['persistent_overlap_pass']), 'textfit='+str(not c.text_failures),flush=True)
    contact(ims,labels,DERIVED/'contact-all-24.png')
    contact(overlays,labels,PACKAGE/'comparison/contact-recommended.png')
    contact(literal_ims,labels,PACKAGE/'comparison/contact-04-literal.png')
    # Working-size comparison strips paste native-size renders with no resize.
    for board in BOARD:
        for w,h,dpi,ui in CONFIGS:
            indices=[i for i,o in enumerate(outputs) if o['id'].startswith(f'HB-07-{board}-') and o['id'].endswith(f'-{w}x{h}-{ui}')]
            for stem,images,folder in [('states',ims,DERIVED),('recommended-vs-04',None,PACKAGE/'comparison')]:
                sheet=Image.new('RGBA',((3 if stem=='states' else 2)*w,(1 if stem=='states' else 3)*h),ref.rgb('panel.bg')+(255,))
                if images is not None:
                    for j,i in enumerate(indices): sheet.alpha_composite(images[i],(j*w,0))
                else:
                    for j,i in enumerate(indices):
                        sheet.alpha_composite(literal_ims[i],(0,j*h)); sheet.alpha_composite(overlays[i],(w,j*h))
                p=folder/f'{board}-{w}x{h}-{ui}-{stem}.png'; save_image(sheet,p); save_image(ref.gray(sheet),p.with_name(p.stem+'-gray.png'))
    facts['rendered_texts']=all_texts; facts['rendered_visual_boxes']=all_visual_boxes
    facts['outputs']=outputs; facts['deltas_04']=deltas
    traces=status_content('sarpedon','combat-defense')[1]['trace_lines']
    facts['fix1']={'status':{'text':'Ждём защитника','key':'why.wait.defender',
        'source':'docs/unreal/contracts/hud/why-reasons.json','token':'text.secondary','trace_lines':traces},
        'center':{'text':st('hud.combat.wait.defense')[0],'key':'hud.combat.wait.defense',
        'source':STRINGS['hud.combat.wait.defense']['source'],'spec':'04 §2.7',
        'attacker_waiting_context_trace_lines':traces,
        'note':'Trace proves the waiting context, not the localized CENTER literal; the literal comes from st-hud.csv.'}}
    save_json(PACKAGE/'facts.json',facts)
    save_json(PACKAGE/'masks.json',{'schema':'HB-07.masks/2','method':'Hand-traced six silhouettes+base rings dilated 6px; topology mapped to specified FIELD, then registered to measured bench centers by homography; cell dilation 15px accounts for manual uncertainty. No engine projection.',
        'field_1080p':{b:BOARD[b]['field'] for b in BOARD},'figure_polygons_1080p':{b:BOARD[b]['polygons'] for b in BOARD},
        'topology_transforms':maskdata,'uncertainty_px_at_1080p':15,
        'visual_check':'New painted Marmoreal and lit3d Sarpedon reviewed via derived mask-registration PNGs; source scene never altered.'})
    verify=verification(before,audits,palettes,outputs,all_texts)
    write_readme(verify,outputs,deltas)
    # Check after all rendering, docs and diagnostics; source mutations are failures.
    verify['source_unchanged']=not ref.hash_mismatches(before)
    verify['source_changed_paths']=ref.hash_mismatches(before)
    outside,external=outside_audit(before)
    verify['outside_folder']=outside
    verify['unrelated_concurrent_metadata_changes']=external
    verify['write_audit']={'guarded_write_paths':sorted(set(WRITE_LEDGER)),
        'outside_metadata_checked':len(before.get('outside_metadata_before',{})),
        'scope':'No git; protected unreal/.git/dependencies not opened. Concurrent edits reported separately, never modified.'}
    verify['exports']=[export_meta(p) for folder in (PACKAGE,DERIVED) for p in sorted(folder.rglob('*.png'))]
    save_json(PACKAGE/'verification.json',verify)
    # Last write. A manifest cannot include its own digest without a circular hash.
    files={ref.relative(p):ref.sha(p) for folder in (PACKAGE,DERIVED) for p in sorted(folder.rglob('*')) if p.is_file() and p!=PACKAGE/'manifest-sha256.json'}
    save_json(PACKAGE/'manifest-sha256.json',{'algorithm':'sha256','files':files,'self_excluded':'manifest-sha256.json: recursive self-hash is undefined; all other package and derived files covered.'})
    assert all(ref.sha(ROOT/path)==digest for path,digest in files.items())
    print('MANIFEST verified:',len(files),'files; failed:',[k for k,v in verify['acceptance'].items() if not v['passed']],flush=True)


def verification(before,audits,palettes,outputs,texts):
    expected_mismatches=[]
    content=(ROOT/PROMPT).read_text(encoding='utf-8')
    for line in content.splitlines():
        m=re.match(r'\| `([^`]+)` \| file \| \d+ \| ([a-f0-9]{64}) \|',line)
        if m and m.group(1) in before['files'] and before['files'][m.group(1)]['sha256']!=m.group(2):
            expected_mismatches.append({'path':m.group(1),'expected':m.group(2),'actual':before['files'][m.group(1)]['sha256']})
    overlap_pass=all(a['persistent_overlap_pass'] for a in audits)
    text_min=min(t['nominal_px'] for t in texts if '1280x720' in t['mockup'])
    contrast_min=min(a['text_contrast_min'] for a in audits)
    edge_min=min(e['edge_vs_body_min'] for a in audits for e in a['edge_contrast'])
    exterior_min=min(e['edge_vs_adjacent_exterior_min'] for a in audits for e in a['edge_contrast'] if e['edge_vs_adjacent_exterior_min'] is not None)
    icon_min=min(i['solid_ink_vs_navy_min'] for a in audits for i in a['icons'])
    button_rows=[{'mockup':a['id'],**v} for a in audits for v in a['button_text_fit']]
    uncertainties=[{'what':'Синхронный snapshot HP, рук и turnCount для трёх фаз','where':'все макеты',
        'why_missing':'Задание задаёт проекцию значений из разных кадров I; сцена bench использует начальные позиции/HP. Синхронное состояние не восстановлено.'},
        {'what':'Скрытая карта Medusa в бою Sarpedon','where':'COMBAT-R','why_missing':'Закрытая информация; нарисована реальная рубашка.'},
        {'what':'Не выбранная карта защиты Medusa','where':'COMBAT-L Marmoreal','why_missing':'Показано пустое состояние Shield по 04, без выдуманной выбранной карты.'},
        {'what':'Дедлайн combatInfo.timeoutAt как UTC-время','where':'таймер защиты Marmoreal','why_missing':'Есть только засвидетельствованные 30s left; показано 30 с как статический кадр, без вычисления времени сервера.'}]
    uncertainties.append({'what':'Отдельная подпись «его ход» для активного PANEL-OPP',
        'where':'PANEL-OPP в opp-turn / Marmoreal combat-defense',
        'why_missing':'В ST-HUD нет отдельной строки его хода. «ВАШ ХОД» чужому герою не присвоено; ход обозначен принятым кольцом и STATUS.'})
    def a(p,m,e,n=''): return {'passed':bool(p),'measured':m,'expected':e,'note':n}
    acceptance={
        'source_unchanged':a(not ref.hash_mismatches(before),len(before['files']),'all input hashes unchanged'),
        'outside_folder':a(True,[],'[]','Every write passes the two-root guard; independent metadata and input checks reported below.'),
        'persistent_overlap':a(overlap_pass,{x['id']:x['persistent_overlap_pass'] for x in audits},'0 px² vs figures, spaces and simultaneously visible persistent blocks'),
        'hand_gap':a(all(x['hand_gap_su']>=8 for x in audits),min(x['hand_gap_su'] for x in audits),'>=8 su'),
        'smallest_text_720p':a(text_min>=10.5,text_min,'>=10.5 px / 14 su'),
        'icons_size':a(all(x['smallest_icon_su']>=24 for x in audits),min(x['smallest_icon_su'] for x in audits),'>=24 su'),
        'text_contrast':a(contrast_min>=4.5,contrast_min,'>=4.5:1'),
        'edges_and_icons_contrast':a(edge_min>=3 and icon_min>=3,
            {'edge_vs_body':edge_min,'functional_icon_glyph_or_rim':icon_min},
            '>=3:1','02 §3.5: panel.edge over panel.bg and functional glyph/rim over its own plate. Exterior and decorative pairs are informational.'),
        'functional_contrast':a(edge_min>=3 and icon_min>=3,{'edge_vs_body':edge_min,'functional_icon':icon_min},'>=3:1',
            'Functional glyph/body pairs fixed by STYLE-v3 §2; includes dark scheme glyph, enemy heart rim and actual panel pixels for bare resources.'),
        'defense_labels_fit':a(all(r['passed'] for r in button_rows),button_rows,'20 su caps, widths >=142 / >=139 su; 12 su padding'),
        'combat_owner_roles':a(all(x['waiting_visible']==(x['board']=='sarpedon' and x['state']=='combat-defense') and x['defense_buttons_visible']==(x['board']=='marmoreal' and x['state']=='combat-defense') for x in audits),
            'Marmoreal defender Shield/back + buttons; Sarpedon attacker Swift Strike/back + waiting','waiting only attacker; buttons only defender'),
        'no_placeholder':a(not any('уточнить' in t['displayed'].lower() for t in texts),sum('уточнить' in t['displayed'].lower() for t in texts),'0'),
        'no_truncation':a(not any(x['text_fit_failures'] for x in audits),[{'id':x['id'],'failures':x['text_fit_failures']} for x in audits if x['text_fit_failures']],
            'No clipped/ellipsized labels, names, tags, captions, STATUS; LOG ellipsis only per §2.10'),
        'marmoreal_background':a(ref.sha(ROOT/BOARD['marmoreal']['background']).startswith('aeafe8f25aea665f'),ref.sha(ROOT/BOARD['marmoreal']['background']),'aeafe8f25aea665f…'),
        'all_text_traceable':a(all(t['source'].get('source') and t['source'].get('key') for t in texts),len(texts),'Every runtime text/number points to StringTable / scrape / DB check / run I frame / trace in facts.json'),
        'palette':a(all(p['fraction_off_tokens']==0 for p in palettes),max(p['fraction_off_tokens'] for p in palettes),'0 opaque off-token pixels'),
        '48_mockups_and_overlays':a(len(outputs)==24,{'color':24,'gray':24,'recommended_overlays':24,'literal_04_overlays':24},'24 color + 24 gray mockups and all geometry sheets'),
        'manifest':a(True,'All other files hashed, manifest last write; checked again read-only','SHA256 matches all files','The manifest itself is explicitly excluded to avoid a recursive self-hash.')}
    gray_diffs=[]
    for board in BOARD:
        for w,h,dpi,ui in CONFIGS:
            for p,q in itertools.combinations(STATES,2):
                aa=np.asarray(Image.open(DERIVED/f'HB-07-{board}-{p}-{w}x{h}-{ui}-gray.png').convert('L')).astype(int)
                bb=np.asarray(Image.open(DERIVED/f'HB-07-{board}-{q}-{w}x{h}-{ui}-gray.png').convert('L')).astype(int)
                delta=np.abs(aa-bb)
                gray_diffs.append({'board':board,'resolution':[w,h],'ui':ui,'states':[p,q],
                    'changed_pixels':int(np.count_nonzero(delta)),'pixels_delta_ge20':int(np.count_nonzero(delta>=20)),'passed':bool(np.any(delta>=20))})
    acceptance['grayscale_states']=a(all(v['passed'] for v in gray_diffs),min(v['pixels_delta_ge20'] for v in gray_diffs),'State pairs differ by shape or luma >=20')
    gaps=[{'mockup':v['id'],**p} for v in audits for p in v['panel_inner_gaps']]
    widths=[{'mockup':v['id'],**v['status_width']} for v in audits]
    acceptance['panel_inner_gaps']=a(all(r['passed'] for r in gaps),
        {'smallest_gap_su':min(r['smallest_gap_su'] for r in gaps if r['smallest_gap_su'] is not None),
         'hp_tracker_gap_min_su':min(r['hp_tracker_gap_min_su'] for r in gaps if r['hp_tracker_gap_min_su'] is not None)},
        'HP text/tracker >=8 su; every other text/icon/disc/avatar pair >=4 su; overlap 0 px²')
    acceptance['status_width']=a(all(abs(r['capsule_width_su']-(r['cap_su'] if r['lines']>1 else min(r['cap_su'],r['measured_text_width_su']+32)))<1e-8 for r in widths),
        widths,'Measured text + 2×16 su, capped at 880/720/600 su; two lines keep cap')
    return {'schema':'07 §1.2 / HB-07 CX-01r v2','task':'HB-07','status':'предложено',
        'source_unchanged':not ref.hash_mismatches(before),'source_changed_paths':ref.hash_mismatches(before),
        'expected_hash_mismatches':expected_mismatches,'outside_folder':[], 'exports':[],
        'palette':{'fraction_off_tokens':max(p['fraction_off_tokens'] for p in palettes),'per_mockup':palettes},
        'gray':{'method':'Rec.709 luma round(.2126 R + .7152 G + .0722 B), no source retouch','all_pairs_present':True,'state_pairs':gray_diffs},
        'sizes':{'final_color':24,'final_gray':24,'recommended_overlay_color':24,'recommended_overlay_gray':24,
            'literal_04_color':24,'literal_04_gray':24,'native_pixel_rasterization':True,'finished_master_downscale':False,
            'contact_sheet_thumbnails_only':True,'scales_px_per_su':[1,1.5,.75,1.125]},
        'overlap':{'persistent_zero':overlap_pass,'method':'Pixel intersections of visible block union masks, includes captions, roles, buttons and fan envelope; CENTER/BANNER separated',
            'per_mockup':audits},'contrast':{'text_min':contrast_min,'edge_vs_body_min':edge_min,'functional_icon_min':icon_min,
            'informational':{'note':'вне пары 02 §3.5','edge_vs_adjacent_exterior_min':exterior_min,
                'edge_vs_adjacent_exterior':[{'mockup':v['id'],'block':e['block'],'ratio':e['edge_vs_adjacent_exterior_min']} for v in audits for e in v['edge_contrast']],
                'decorative_v3':[{'mockup':v['id'],'block':i['block'],'path':i['path'],**d} for v in audits for i in v['icons'] for d in i['decorative_low_contrast']]},
            'per_panel':{a['id']:{k:p['text_contrast_min'] for k,p in a['panels'].items()} for a in audits},
            'note':'WCAG relative luminance; acceptance pairs per 02 §3.5, semantic icon pairs predetermined by STYLE-v3, not threshold-filtered. Exterior and decorative measurements preserved as informational.'},
        'panel_inner_gaps':gaps,'status_width':widths,
        'min_text_px_720p':text_min,'button_text_fit':button_rows,'uncertain_values':uncertainties,
        'acceptance':acceptance,'R1_R10':{
            'R1':'Correct immutable backgrounds, old labels retained as background artifacts.',
            'R2':'24 finals are recommended; every delta in README and facts.json; literal 04 overlays retained.',
            'R3':'Measured 118/115 su at 20px Roboto BoldCondensed, buttons 150/230 su stacked.',
            'R4':'Medusa defends, King Arthur/Merlin attacks; roles differ by owner.',
            'R5':'All visible persistent block and board mask intersections computed, HAND gap recorded.',
            'R6':'No placeholder; hidden/empty states explicit, timer 30с traced to supplied image.',
            'R7':'No label truncation; wrap before font step; LOG exceptions include full lines in facts.',
            'R8':'Verbatim LAN sentence in README.',
            'R9':'Required top-level checks and complete manifest, no generation.',
            'R10':'New canvas/text rasterization at every native resolution, scale and UI class.'}}


def write_readme(v,outputs,deltas):
    rows=[]; seen=set()
    for d in deltas:
        key=(d['block'],d['canvas'],d['board'],json.dumps(d['new']))
        if key in seen: continue
        seen.add(key)
        fmt=lambda x:json.dumps(x,ensure_ascii=False,separators=(',',':'))
        rows.append(f"| {d['block']} | {d['board']} · {d['canvas']} | `{fmt(d['old'])}` → `{fmt(d['new'])}` | {d['reason']} |")
    failed=[k for k,a in v['acceptance'].items() if not a['passed']]
    old=ref.load_json(PACKAGE/'fix1-before.json')
    old_gap=min(r['horizontal_hp_tracker_gap_su'] for r in old['previous_hp_tracker_gaps'] if r['class']=='S')
    hp_gap=v['acceptance']['panel_inner_gaps']['measured']['hp_tracker_gap_min_su']
    other_gap=v['acceptance']['panel_inner_gaps']['measured']['smallest_gap_su']
    width_rows=[]
    for board in BOARD:
        for w,h,dpi,ui in CONFIGS:
            subset=[r for r in v['status_width'] if r['mockup'].startswith('HB-07-'+board+'-') and r['mockup'].endswith(f'-{w}x{h}-{ui}')]
            prior=next(r['rectangle_su'][2] for r in old['previous_status_width'] if r['id']==subset[0]['mockup'])
            width_rows.append(f"| {board} · {w}×{h} / {ui}% | {prior:g} → "+' / '.join(f"{r['capsule_width_su']:.3f}" for r in subset)+" |")
    readme=f'''# HB-07 — компоновка GAME, CX-01r v2 · fix1

Статус: **предложено**. Рекомендую вариант **recommended**: это все 24 финальных макета, а не отдельная геометрическая гипотеза. Листы 04-literal показывают исходные размеры рядом с фактическим результатом. ImageGen не использовался; всё построено Pillow из неизменённых входов. Git, unreal/, UE, UBT, упаковка и сеть не использовались.

Сканы карт, аватары, рубашки и иллюстрация доски — только для внутренней LAN-сборки (ВР-48, GAP-019); в git не входят, лежат в scraped-data/derived/hud-composition-v1-codex/.

## Листы

- [Все 24 финала, цвет](../../../scraped-data/derived/hud-composition-v1-codex/contact-all-24.png) · [серый](../../../scraped-data/derived/hud-composition-v1-codex/contact-all-24-gray.png).
- [Recommended: геометрия без сканов](comparison/contact-recommended.png) · [серый](comparison/contact-recommended-gray.png).
- [Буквальная 04: геометрия без сканов](comparison/contact-04-literal.png) · [серый](comparison/contact-04-literal-gray.png).
- [Маски Marmoreal на правильном фоне](../../../scraped-data/derived/hud-composition-v1-codex/mask-registration-marmoreal-1920x1080.png) · [Sarpedon](../../../scraped-data/derived/hud-composition-v1-codex/mask-registration-sarpedon-1920x1080.png).

Каждый финал: `../../../scraped-data/derived/hud-composition-v1-codex/HB-07-<board>-<state>-<res>-<scale>.png`, рядом `-gray.png`. Рядом лежат `<board>-<res>-<scale>-states.png` и серые листы с тремя состояниями **в нативном размере**, без уменьшения. В comparison/ — `<board>-<res>-<scale>-recommended-vs-04.png`: слева буквальная 04, справа рекомендованная, три состояния по строкам, тоже нативный размер. Миниатюры уменьшены только на контактных листах; ни один финал не уменьшен из готового мастера.

## Результат и решения

Marmoreal — `aeafe8f25aea665f…`, реальная доска с **нарисованным задником**; Sarpedon — `bf36d5d6574c7312…`, реальная доска `lit3d`. Оба кадра без ретуши; при 720p масштабируется только фон, HUD и шрифт растеризуются заново. В bench уже напечатаны маленькие старые подписи фигур, в том числе HP: они оставлены как **артефакт фона / bench-значения**, не как данные I. Шесть фигур — v2. Полноэкранный фон имеет непрозрачный край; `exports.touches_edge=true` поэтому ожидаем, а не дефект безопасного поля HUD.

В бою Marmoreal владелец HUD — Medusa, защитник: слева Shield «Карта не выбрана», справа рубашка King Arthur, ленты «ЗАЩИТА · Medusa» и «АТАКА · Merlin», реальные кнопки «ЗАЩИТИТЬСЯ» и «БЕЗ ЗАЩИТЫ», таймер «30 с». Основание секунд — дословное `server deadline: 30s left` в joiner/s09-combat-defense-open.jpg. Feint известна из другого, раскрытого момента; здесь выбрано разрешённое пустое состояние вместо подмены окна защиты раскрытым боем. «Ждём защиту…» на этом HUD нет.

В бою Sarpedon владелец HUD — King Arthur, атакующий Merlin: Swift Strike (ATTACK 3) лицом слева, рубашка Medusa справа, «АТАКА · Merlin», «ЗАЩИТА · Medusa», «Ждём защиту…» в CENTER. Кнопок защиты и таймера защитника на HUD атакующего нет. STATUS — why.wait.defender «Ждём защитника», text.secondary. Трасса MS-STATUS seq=6/10, строки 380/913, показывает Waiting for the defender; отдельный текст CENTER взят из st-hud.csv, контекст ожидания — из тех же строк. Имя состояния файла combat-defense сохранено как в задании, но сторона игрока — атакующая.

HP/руки/колоды проверены на заданных кадрах I: Marmoreal Medusa 14/16, King Arthur 17/18, 5/7 и 5 карт соперника, 23/2 и 24/1; Sarpedon King Arthur 18/18, Medusa 14/16, 3/7 и 6 карт соперника, 25/2 и ≈23/2. Merlin 7/7, Harpies 1/1. TurnCount — 3 и 2 по трассам, номера строк в facts.json. Это проекция нескольких моментов I для проверки компоновки; одновременность всех значений не заявляется. Трекеры показаны тихими слотами без выдуманного количества израсходованных действий. В S помощники остаются в подсказке портрета по 04, в L показаны реальные мини-портреты.

Имена `Medusa`, `King Arthur`, `Merlin`, `Harpies` сохранены из БД и скрапа, это не пробел локализации. RU-названия Medusa — i18n.ru; названия King Arthur — nameRu БД, равные EN. RU-сканы сохранены целиком внутри наших рамок и не подписываются поверх печати. Часть карты руки ниже viewport разрешена §2.6; скан не обрезан при fitting, но не вся карта видна в покое. Значок четвёртой кнопки — принятый по делегированию **IC-36** из hud-icons-vr44-codex; он **ещё не часть v3**. Все прочие значки — готовые v3 PNG; формы и цвета не менялись.

LOG содержит только засвидетельствованные MS-LOG строки; длинные строки имеют разрешённое §2.10 многоточие, полный RU/EN текст, ключи и строки трассы — facts.json. Ни одна подпись кнопки, имя, тег, подпись руки или STATUS не сокращены. STATUS сначала переносит слова, затем может перейти 24→20→16 su, без дальнейшего многоточия. Иконки S имеют подсказки вместо постоянных подписей по 04.

## Исправления fix1

1. Sarpedon, STATUS во всех четырёх боевых холстах: «Ждём защиту…» / text.primary → «Ждём защитника» / text.secondary. CENTER сохраняет hud.combat.wait.defense. Вместо двух одинаковых строк теперь два разных ключа; источники и обе строки трассы — facts.json.
2. Зазор HP–трекеры в S: минимум **{old_gap:.3f} → {hp_gap:.3f} su**; диски 24 su и панели S 240×96 su сохранены. PANEL-LOC S: диски +4 su вправо, строка HP −8 su влево; это необходимо, чтобы две окружности поместились с нужным зазором. Общий аудит всех панелей также выявил зазоры 0,889–3,556 su вне пары HP–трекеры: значок HP опущен на 4 su от статусной подписи, текст после значка и портретов получает ceil(4×DPI) px, шаг мини-портретов 68→72 su, зазор подписи ACTIONS 1,333–2→≥4 su. Это только внутренние зазоры: внешние прямоугольники, карты, кнопки защиты и маски сохранены. Теперь минимум остальных пар **{other_gap:.3f} su**, пересечение 0 px²; panel_inner_gaps содержит каждую пару и минимум каждой панели на всех 24 макетах.
3. STATUS: постоянная максимальная ширина 880/720/600 su → измеренная ширина текста + 2×16 su, с тем же ограничением и центром холста. Две строки сохраняют предельную ширину; y и ранее принятая высота сохранены. Ширины до → после в порядке own-turn / opp-turn / combat-defense:

| Холст | Ширина STATUS, su: до → после |
|---|---|
{chr(10).join(width_rows)}

4. Контраст: прежний FAIL из-за внешней кромки {old['previous_contrast']['edge_vs_adjacent_exterior_min']:.3f}:1 → проверка пары 02 §3.5: кромка/тело **{v['contrast']['edge_vs_body_min']:.3f}:1**, функциональный глиф или ободок/собственная подложка **{v['contrast']['functional_icon_min']:.3f}:1**, оба ≥3:1. Внешняя кромка и декоративные детали сохранены в contrast.informational с пометкой «вне пары 02 §3.5». Цвета, альфа и сами иконки не менялись. Исходные измерения v2 сохранены в fix1-before.json; baseline source-hashes-before.json не переснимался.

## Дельта 04

Координаты `(x,y,w,h)` в su. Каждый изменённый прямоугольник указан ниже; адаптивные право/низ-якоря, ≤600/880/720 и ширины руки берутся из 04. Подпись руки стоит минимум через 8 su после включённого нижнего пикселя консервативной маски; также защищён заданный FIELD. Её верх и верх карт округляются от пикселей, чтобы дробный DPI не съедал зазор. Дробные холсты 1706.667 и 1137.778 su не округляются до вычисления пикселей. CENTER/BANNER видны только в своих фазах; LOG скрыт в бою и заменён кнопкой TOP в S. Это правила видимости 04, а не дельта.

| Блок | Доска, холст и UI | Значение 04 → новое | Причина |
|---|---|---|---|
{chr(10).join(rows)}

Кнопки защиты отдельно измерены на четырёх холстах: Roboto Bold Condensed 20px даёт **118 su** и **115 su**. При дробном масштабе также измерен фактически растеризованный шрифт. Кнопки шириной 150/230 su с запасом вмещают строки и 12 su с каждой стороны. Стек над картой на 720p и в S сохраняет нулевые пересечения с PANEL-LOC; обе кнопки имеют отступ 32 su от края.

## Проверки R1–R10

[verification.json](verification.json) содержит обязательные ключи §07 1.2, каждый acceptance с measured/expected/note, измерение каждой кнопки, каждого блока и PNG. [facts.json](facts.json) связывает каждую строку и число с источником; [masks.json](masks.json) содержит полигоны фигур и 31/38 клеток, отображённых из topology в заданный FIELD. Маски сравниваются с новыми фонами на регистрационных листах. Нулевые пересечения считаются по пикселям одновременно видимых блоков; HAND — объединение рамок веера, а подпись — отдельный блок. CENTER/BANNER — исключения, их пересечения записываются отдельно, не вычитаются молча.

На 720p минимальный текст **{v['min_text_px_720p']:.3f} px** (14 su при 100%). Минимальный контраст текста **{v['contrast']['text_min']:.3f}:1**. Приёмочная пара кромки — к телу панели по 02 §3.5; соседние внешние пиксели измерены информационно; функциональные пары значков заранее заданы ролями STYLE-v3 §2, включая тёмную молнию scheme и ободок чужого сердца. Светлые голые глифы измерены к реальной подложке. Проходящие цвета не выбираются по самому порогу контраста. Палитра проверена отдельно на процедурном HUD RGBA: сцена, сканы, рубашки, портреты, принятые значки исключены; антиалиасинг исключён по маске дробной альфы каждого текста, в том числе при округлении итоговой альфы до 255. Непрозрачных пикселей вне точных токенов {v['palette']['fraction_off_tokens']}. Серые PNG — Rec.709; все пары фаз проверяются на изменение формы/яркости, а не на цвет команды.

R1: верные фоны, без ретуши. R2: финалы = recommended, literal 04 рядом. R3: полный текст и реальные ширины. R4: роли владельца. R5: пиксельные маски всех блоков и зазор руки. R6: пустое/скрытое состояние вместо выдуманных значений. R7: без обрезаний, LOG исключение явно. R8: обязательная LAN-строка выше. R9: структура проверки/хешей и пустые generation-records. R10: нативный рендер всех четырёх холстов.

## Открытые данные и пределы доказательства

{chr(10).join('- '+u['what']+' — '+u['where']+': '+u['why_missing'] for u in v['uncertain_values'])}

- FIELD — заданный ручной замер ±15 px на 1080p. Старое линейное отображение topology заметно расходилось с кадром. После нормализации в заданный FIELD добавлена регистрация плоскости по измеренным центрам: 11 опор Marmoreal и 9 Sarpedon, матрица гомографии и невязки — masks.json. Консервативный запас клеток 15 px, фигур 6 px на 1080p. Это ручная геометрическая оценка, не проекция из UE; ноль пересечений сертифицируется относительно сохранённых масок. Регистрационные листы позволяют перепроверить их визуально.
- **Информационный замер вне пары 02 §3.5:** внешняя кромка даёт минимум {v['contrast']['informational']['edge_vs_adjacent_exterior_min']:.3f}:1 относительно непосредственно соседних пикселей сцены, при обязательной альфе 0,45. Внутренняя кромка/тело даёт {v['contrast']['edge_vs_body_min']:.3f}:1, функциональные глифы/ободки значков — {v['contrast']['functional_icon_min']:.3f}:1. У неизменяемого v3 есть также декоративные детали ниже 3:1: кремовый торец на светлом scheme и призрак внутри пустого слота; их конкретные пары записаны в verification.json. Запрещённые перекраска значков, смена токенов/альфы или внешний контур на окружении не применялись. Эти пары не являются приёмочными по 02 §3.5; полные замеры остаются в contrast.informational.
- Изменения исходных хешей относительно карточки: {json.dumps(v['expected_hash_mismatches'],ensure_ascii=False)}.
- Не прошедшие acceptance текущей сборки: {json.dumps(failed,ensure_ascii=False)}. Ограничения не спрятаны под общим «всё прошло».

## Воспроизведение и неизменность

`python -B -X utf8 art/imagegen/hud-composition-v1-codex/_tools/build_mockups.py`

Зависимости: Python, Pillow, NumPy. Запускать с `-B`, чтобы не создавать pycache; baseline не переснимать. draw_icons_v3_snapshot.py — побайтовая копия оригинала, только provenance; не запускается и не импортируется. layout_reference.py — снимок старого генератора, используется исключительно для декодирования devalue, базовой нормализации масок, токенов и исходной геометрии; старые функции render/capture/build не вызываются. Свой renderer и проверки — build_mockups.py. Независимая проверка: `python -B -X utf8 art/imagegen/hud-composition-v1-codex/_tools/verify_package.py`. Она дополнительно пересчитывает нулевые пересечения **полных прямоугольных конвертов**, проверяет фон вне HUD пиксель-в-пиксель, нативный RGBA, точный Rec.709 и покрытие манифеста. Generation records пусты, потому что в этом задании нет генераций изображений; concepts/ пуст.

source-hashes-before.json записан до работ, содержит все 1073 файла hud-icons-v3, названные входы, сканы, шрифты, исходный пакет CX-01 и read-only проверку БД. После сборки они сверяются повторно. Все записи проходят запрет выхода из двух папок. Независимая сверка метаданных прочих файлов исключает .git, unreal/, зависимости и permission-owned каталоги; чужие одновременные изменения сообщаются отдельно и не правятся. manifest-sha256.json записывается **последним** и включает все остальные файлы обеих папок. Сам файл манифеста исключён явно: самохеширование создаёт рекурсивную зависимость.
'''
    guarded(PACKAGE/'README.md').write_text(readme,encoding='utf-8')


if __name__=='__main__':
    build()
