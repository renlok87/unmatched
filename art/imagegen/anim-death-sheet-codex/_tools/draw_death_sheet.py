#!/usr/bin/env python
"""AN-30: deterministic procedural sheet. All writes stay under this package.

Run: python -B art/imagegen/anim-death-sheet-codex/_tools/draw_death_sheet.py
The copied HUD generator is never run as a program; only its heart geometry is reused.
"""
from __future__ import annotations

import sys
sys.dont_write_bytecode = True
import hashlib
import importlib.util
import io
import json
import math
import re
from pathlib import Path

import cairo
import numpy as np
from PIL import Image, ImageDraw, ImageFont
from scipy import ndimage as ndi

PACKAGE = Path(__file__).resolve().parents[1]
REPO = PACKAGE.parents[2]
PALETTE = {
    'navy': '#061623', 'cream': '#F9EBDB', 'flash': '#FAF8F2',
    'keyline': '#111317', 'primary': '#F2EDE4', 'secondary': '#B9B2A6',
    'warm': '#FFB45C', 'p1': '#E8C06A', 'p2': '#5A7F9F',
}
FONT_DIR = Path('C:/Program Files/Epic Games/UE_5.8/Engine/Content/Slate/Fonts')
SOURCE = {
    'KingArthur': 'art/pipeline-candidates/ASSET-KING-ARTHUR-001/20260929-h2anim/preview',
    'Harpy': 'art/pipeline-candidates/ASSET-HARPY-001/20260929-h2anim/preview',
}
WRITE_LOG = set()
TEXT_LOG = []
TRACE_REPORT = []
EFFECT_REPORT = []
LAYOUT_REPORT = []


def output(name):
    p = (PACKAGE / name).resolve()
    if not p.is_relative_to(PACKAGE):
        raise ValueError(f'Output outside package: {p}')
    p.parent.mkdir(parents=True, exist_ok=True)
    WRITE_LOG.add(p.relative_to(REPO).as_posix())
    return p


def write_json(name, value):
    output(name).write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


def digest(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()


def rgb(token):
    s = PALETTE.get(token, token).lstrip('#')
    return tuple(int(s[i:i+2], 16) for i in (0, 2, 4))


# Import unchanged local snapshot, with no pycache creation and no build() call.
spec = importlib.util.spec_from_file_location('an30_hud_snapshot', PACKAGE / '_tools/draw_icons_v3_snapshot.py')
hud = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = hud
spec.loader.exec_module(hud)
hud.ROOT = str(PACKAGE)


def trace(actor, frame, view='q34'):
    """Extract silhouette from OUR JPEG tile, not a generated or invented character.

    Background is uniform gray. Remove saturated skeleton overlay, restore short
    interruptions with a local closing, keep meaningful connected components.
    Root/foot coordinates in the supplied bones JSON set the base-top crop.
    Row runs preserve the traced raster boundary exactly in the SVG source.
    """
    prefix = REPO / SOURCE[actor]
    bones = json.loads((prefix / f'frames/{actor}-DeathSettle-bones2d.json').read_text(encoding='utf-8'))
    key = f'f{frame:02d} {view}'
    index = list(bones).index(key)
    tile_size = 420
    box = ((index % 4)*tile_size, (index // 4)*tile_size,
           (index % 4+1)*tile_size, (index // 4+1)*tile_size)
    tile = Image.open(prefix / f'{actor}-DeathSettle-blender-sheet.jpg').convert('RGB').crop(box)
    a = np.array(tile).astype(np.int16)
    bg = np.median(a[50:90, 10:40], axis=(0, 1))
    distance = np.max(np.abs(a-bg), axis=2)
    red = (a[:, :, 0] > 150) & (a[:, :, 0] > a[:, :, 1]*1.7) & (a[:, :, 1] < 130)
    yellow = (a[:, :, 0] > 175) & (a[:, :, 1] > 170) & (a[:, :, 2] < 135)
    overlay = ndi.binary_dilation(red | yellow, iterations=4)
    raw = distance > 16
    # Everything under the sole endpoints is the render's round display base.
    feet = [b['b'][1] for b in bones[key]['bones'] if b['name'].startswith('foot.')]
    base_y = int(math.ceil(max(feet))) + 1
    raw[:42] = False
    raw[base_y:] = False
    raw[:, :16] = False
    raw[:, -16:] = False
    seed = raw & ~overlay
    # Recover rig-covered pixels only near actual figure material, never the
    # free-standing rig axis. Keep true background gaps between sword and cape.
    density = ndi.uniform_filter(seed.astype(float), size=25)
    mask = seed | (overlay & raw & (density > .25))
    mask |= ndi.binary_fill_holes(mask) & raw
    holes = ndi.binary_fill_holes(mask) & ~mask
    hole_labels, hole_count = ndi.label(holes)
    hole_areas = np.bincount(hole_labels.ravel())
    mask |= np.isin(hole_labels, [i for i in range(1,hole_count+1) if hole_areas[i] < 120])
    labels, count = ndi.label(mask)
    areas = np.bincount(labels.ravel())
    keep = [i for i in range(1, count+1) if areas[i] >= 20]
    mask = np.isin(labels, keep)
    mask[base_y:] = False
    ys, xs = np.where(mask)
    assert len(xs) > 1500, (actor, frame, len(xs))
    # Same actor placement and scale across all clip frames (never normalize each pose).
    Image.fromarray(mask.astype('uint8')*255).save(output(f'traces/{actor}-f{frame:02d}-{view}-mask.png'))
    paths = []
    for y, row in enumerate(mask):
        edges = np.diff(np.r_[False, row, False].astype(np.int8))
        for x0, x1 in zip(np.where(edges == 1)[0], np.where(edges == -1)[0]):
            paths.append(f'M{x0},{y}h{x1-x0}v1h{x0-x1}z')
    output(f'traces/{actor}-f{frame:02d}-{view}.svg').write_text(
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 420 420">'
        '<path fill="#F9EBDB" d="' + ''.join(paths) + '"/></svg>\n', encoding='utf-8')
    TRACE_REPORT.append({'actor': actor, 'frame': frame, 'view': view, 'tile_index': index,
                         'crop_xyxy': box, 'base_top_y': base_y, 'area_px': int(mask.sum()),
                         'bounds_xyxy': [int(xs.min()), int(ys.min()), int(xs.max()+1), int(ys.max()+1)],
                         'skeleton_overlay_removed': True, 'method': 'background difference + rig removal + density-gated reconstruction + small-hole repair; SVG row runs',
                         'pose_invented': False, 'source': SOURCE[actor] + f'/{actor}-DeathSettle-blender-sheet.jpg'})
    return mask, tile


class Canvas:
    def __init__(self, width=1920, height=1080):
        self.scale = width/1920
        self.im = Image.new('RGBA', (width, height), rgb('navy') + (255,))
        self.d = ImageDraw.Draw(self.im)
        self.labels = []

    def point(self, p):
        return tuple(round(v*self.scale) for v in p)

    def line(self, points, color='secondary', width=1):
        self.d.line([self.point(p) for p in points], fill=rgb(color), width=max(1, round(width*self.scale)))

    def rect(self, box, fill=None, outline=None, width=1):
        self.d.rectangle(self.point(box), fill=rgb(fill) if fill else None,
                         outline=rgb(outline) if outline else None, width=max(1, round(width*self.scale)))

    def text(self, xy, text, size=22, color='primary', bold=False, anchor='lt', clear_line=False):
        path = FONT_DIR / ('Roboto-BoldCondensed.ttf' if bold else 'Roboto-Regular.ttf')
        font = ImageFont.truetype(str(path), max(1, round(size*self.scale)))
        pt = self.point(xy)
        box = self.d.textbbox(pt, text, font=font, anchor=anchor)
        assert box[0] >= 0 and box[1] >= 0 and box[2] <= self.im.width and box[3] <= self.im.height, (text, box)
        if clear_line:
            pad = max(4, round(5*self.scale))
            self.d.rectangle((box[0]-pad,box[1]-pad,box[2]+pad,box[3]+pad),fill=rgb('navy'))
        self.d.text(pt, text, font=font, fill=rgb(color), anchor=anchor)
        self.labels.append({'text': text, 'bbox': box})
        if self.im.width == 1920:
            TEXT_LOG.append(text)

    def arrow(self, p0, p1, color='secondary', width=2):
        self.line([p0, p1], color, width)
        angle = math.atan2(p1[1]-p0[1], p1[0]-p0[0])
        for delta in [-.5, .5]:
            self.line([p1, (p1[0]-10*math.cos(angle+delta), p1[1]-10*math.sin(angle+delta))], color, width)

    def pose(self, mask, cx, bottom, actor, progress=0, reduced=False, dots=0):
        factor = (.46 if actor == 'KingArthur' else .59)*self.scale
        m = Image.fromarray(mask.astype('uint8')*255).resize((round(420*factor), round(420*factor)), Image.Resampling.NEAREST)
        a = np.array(m) > 0
        ys, xs = np.where(a)
        lo, hi = int(ys.min()), int(ys.max()+1)
        team = 'p1' if actor == 'KingArthur' else 'p2'
        layer = np.zeros((*a.shape, 4), dtype=np.uint8)
        if reduced:
            layer[a] = rgb('cream') + (round(255*(1-progress)),)
            edge = ndi.binary_dilation(a, iterations=max(1, round(2*self.scale))) & ~a
            layer[edge] = rgb('keyline') + (round(255*(1-progress)),)
        elif progress:
            front = hi-round((hi-lo)*progress)
            a[front:] = False
            edge = ndi.binary_dilation(a, iterations=max(1, round(2*self.scale))) & ~a
            layer[edge] = rgb('keyline') + (255,)
            layer[a] = rgb(team) + (255,)
            band = a.copy()
            band_height = max(1, round(6*self.scale))
            line_height = max(1, round(2*self.scale))
            band[:max(0, front-band_height)] = False
            layer[band] = rgb('warm') + (255,)
            separator = a.copy()
            separator[:max(0,front-band_height-line_height)] = False
            separator[max(0,front-band_height):] = False
            layer[separator] = rgb('keyline') + (255,)
            # Bottom closure and silhouette outline are the same 2 px keyline.
            assert set(map(tuple, layer[layer[:, :, 3] > 0, :3])) <= {rgb(team), rgb('warm'),rgb('keyline')}
            EFFECT_REPORT.append({'actor': actor, 'progress': progress, 'embers': dots,
                                  'front_rgb': rgb('warm'), 'ash_rgb': rgb(team), 'reduced': False})
        else:
            edge = ndi.binary_dilation(a, iterations=max(1, round(2*self.scale))) & ~a
            layer[edge] = rgb('keyline') + (255,)
            layer[a] = rgb('cream') + (255,)
        origin = (round(cx*self.scale-m.width/2), round(bottom*self.scale-hi))
        self.im.alpha_composite(Image.fromarray(layer), origin)
        if progress and not reduced:
            # One emitter budget shared by its pictured states: 10 + 10 per fighter.
            # Positions are deterministic and have no blur, smoke, glow or gradient.
            assert dots <= 40
            for i in range(dots):
                x = origin[0]+round((xs.min()+xs.max())/2) + round((i%5-2)*12*self.scale)
                y = origin[1]+front+round((i//5*14 + (i%3)*3 + 12)*self.scale)
                r = max(1, round(1.7*self.scale))
                self.d.ellipse((x-r, y-r, x+r, y+r), fill=rgb(team))

    def heart(self, cx, cy, size=36):
        n = max(1, round(size*self.scale))
        surface = cairo.ImageSurface(cairo.FORMAT_ARGB32, n, n)
        ctx = cairo.Context(surface)
        ctx.translate(n/2, n/2)
        ctx.scale(n/25, n/25)
        hud.heart_path(ctx, 0, 0)
        ctx.set_source_rgb(*(v/255 for v in rgb('cream')))
        ctx.fill_preserve()
        ctx.set_source_rgb(*(v/255 for v in rgb('keyline')))
        ctx.set_line_width(1.3)
        ctx.stroke()
        hud.heart_path(ctx, 0, 0, r=3.8, lx=3.8, ly=-2.2, tip=7)
        ctx.set_source_rgb(*(v/255 for v in rgb('keyline')))
        ctx.fill()
        ctx.set_source_rgb(*(v/255 for v in rgb('cream')))
        ctx.set_line_width(1.7)
        for a, b in [((-2.5,-1), (2.5,4)), ((-2.5,4), (2.5,-1))]:
            ctx.move_to(*a); ctx.line_to(*b); ctx.stroke()
        buf = io.BytesIO(); surface.write_to_png(buf); buf.seek(0)
        self.im.alpha_composite(Image.open(buf).convert('RGBA'), self.point((cx-size/2, cy-size/2)))

    def save(self, name):
        self.im.save(output(name))
        # Text overlap check: restricted to actual label boxes, excluding graphics.
        overlaps = []
        for i, a in enumerate(self.labels):
            for b in self.labels[i+1:]:
                aa, bb = a['bbox'], b['bbox']
                if min(aa[2],bb[2])-max(aa[0],bb[0]) > 1 and min(aa[3],bb[3])-max(aa[1],bb[1]) > 1:
                    overlaps.append([a['text'], b['text']])
        LAYOUT_REPORT.append({'file': name, 'width': self.im.width, 'height': self.im.height,
                              'text_in_bounds': True, 'overlapping_labels': overlaps})
        return self.im


def gray(im):
    a = np.array(im)
    y = np.rint(a[:, :, :3].astype(np.float64) @ np.array([.2126, .7152, .0722])).astype(np.uint8)
    return Image.fromarray(np.dstack([y, y, y, a[:, :, 3]]))


def axis_x(t):
    return 300 + (1820-300)*t/3125


def phases(c, y, actor):
    hero = actor == 'KingArthur'
    team = 'p1' if hero else 'p2'
    c.text((56,y+8), 'KING ARTHUR · P1' if hero else 'HARPY · P2', 22, team, True)
    spans = [(0,450,'HitReact · 450'), (450,1325,'DeathSettle · 875')]
    if hero: spans.append((1325,1625,'still · 300'))
    spans.append((1625 if hero else 1325,2125 if hero else 1725, 'ash · 500' if hero else 'ash · 400'))
    for start, end, label in spans:
        c.rect((axis_x(start),y,axis_x(end),y+34), outline=team, width=2)
        c.rect((axis_x(start),y+30,axis_x(end),y+34), fill='warm' if label.startswith('ash') else team)
        c.text(((axis_x(start)+axis_x(end))/2,y+8),label,20,'primary',True,'mt')
    end = 2125 if hero else 1725
    c.line([(axis_x(end),y+17),(1820,y+17)],team)
    c.text((axis_x(end)+12,y+3),f'gone · {end}',20,team,True,clear_line=True)
    if hero:
        c.text(((axis_x(end)+1820)/2,y+23),'+1000 → result',18,'secondary',False,'mt',clear_line=True)
    else:
        c.text((1820,y+3),'без result',18,'secondary',False,'rt',clear_line=True)


def sheet(masks, width=1920):
    c = Canvas(width, round(width*1080/1920))
    c.text((56,37),'AN-30 / СМЕРТЬ ПО ЭТАПАМ',48,'primary',True)
    c.text((1820,49),'CUE-013 · ПРЕДЛОЖЕНО',23,'warm',True,'rt')
    c.text((56,104),'От контакта смертельного удара · герой и помощник · принятые клипы без новой позы',24,'secondary')
    c.line([(56,147),(1820,147)],'p2')
    c.text((56,161),'ОБЩАЯ ОСЬ / мс',21,'secondary',True)
    c.line([(300,190),(1820,190)],'secondary')
    for t, yy in [(0,161),(450,161),(1325,161),(1625,161),(1725,194),(2125,161),(3125,161)]:
        c.line([(axis_x(t),184),(axis_x(t),194)],'secondary')
        c.text((axis_x(t),yy),str(t),20,'primary',True,'mt')
    phases(c,226,'KingArthur'); phases(c,277,'Harpy')
    c.text((56,328),'КЛИП / 24 fps',20,'secondary',True)
    c.line([(axis_x(450),337),(axis_x(1325),337)],'secondary')
    for frame,t in [(0,450),(3,575),(13,992),(21,1325)]:
        c.line([(axis_x(t),330),(axis_x(t),344)])
        c.text((axis_x(t),348),f'f{frame:02d}',18,'secondary',False,'mt')
    c.text((1820,334),'Ключевые позы ниже — равный шаг; время — на оси',18,'secondary',False,'rt')
    centers = [360,644,928,1212,1496,1780]
    for actor,top,bottom,team in [('KingArthur',393,565,'p1'),('Harpy',599,777,'p2')]:
        c.text((56,top+7),'KING ARTHUR' if actor=='KingArthur' else 'HARPY',25,team,True)
        c.text((56,top+43),'герой · P1' if actor=='KingArthur' else 'помощник · P2',20,'secondary')
        c.text((56,top+79),'камера',18,'secondary')
        c.arrow((95,top+145),(157,top+105),team)
        c.text((56,top+163),'q34 · ≤45°',19,'secondary')
        labels = ['f00 · 450 мс','f03 · 575 мс','f13 · 992 мс','f21 · 1325 мс','пепел · 35 %','пепел · 70 %']
        notes = ['старт DeathSettle','пошатывание','меч на подставке' if actor=='KingArthur' else 'голова опущена',
                 'опора на меч' if actor=='KingArthur' else 'мёртвая птица','снизу вверх','цвет команды']
        for j,cx in enumerate(centers):
            c.text((cx,top),labels[j],22,'warm' if j>=4 else 'primary',True,'mt')
            frame = [0,3,13,21,21,21][j]
            c.pose(masks[actor,frame],cx,bottom,actor,progress=0 if j<4 else [.35,.70][j-4],dots=0 if j<4 else 10)
            c.line([(cx-70,bottom+4),(cx+70,bottom+4)],team)
            c.text((cx,bottom+12),notes[j],18,'secondary',False,'mt')
    c.line([(56,819),(1820,819)],'p2')
    c.text((56,835),'СОБЫТИЯ CUE',23,'primary',True)
    c.line([(300,868),(1820,868)],'secondary')
    c.line([(axis_x(0),859),(axis_x(0),877)],'flash',3)
    c.rect((axis_x(0),861,axis_x(70),868),fill='flash')
    c.text((300,835),'Contact · 0 / flash · 70 мс',20,'flash',True)
    for t,yy,label in [(60,878,'−N · +60 мс'),(80,908,'HP · +80 мс')]:
        c.line([(axis_x(t),868),(axis_x(t),yy+8),(415,yy+8)],'secondary')
        c.text((429,yy),label,19,'secondary')
    c.heart(axis_x(1100),839)
    c.line([(axis_x(1100),858),(axis_x(1100),878)],'cream',2)
    c.text((axis_x(1100)+28,832),'сердце + крест',21,'cream',True)
    c.text((axis_x(1100),883),'1100 мс',20,'cream',True,'mt')
    c.line([(axis_x(3125),858),(axis_x(3125),878)],'warm',3)
    c.text((1820,835),'RESULT · 3125 мс',22,'warm',True,'rt')
    c.text((1820,883),'только смерть героя',19,'secondary',False,'rt')
    c.text((1120,918),'≤40 угольков · 600 мс · без дыма и свечения',19,'secondary',False,'mt')
    c.line([(56,936),(1820,936)],'p2')
    c.text((56,943),'REDUCED MOTION · fade без угольков',17,'primary',True)
    c.text((56,969),'KING ARTHUR',16,'secondary',True)
    for start,end,label in [(0,450,'HitReact · 450'),(450,1325,'DeathSettle · 875'),
                            (1325,1625,'still · 300'),(1625,2125,'fade · 500')]:
        c.rect((axis_x(start),967,axis_x(end),986),outline='secondary',width=2)
        c.text(((axis_x(start)+axis_x(end))/2,970),label,14,'secondary',True,'mt')
    c.text((axis_x(2125)+12,969),'gone · 2125',16,'secondary',True)
    c.text((56,994),'СКОРОСТЬ (UI-ACC-013)',16,'primary',True)
    c.text((300,994),'смерть не масштабируется скоростью; меняется только «−N»',14,'secondary')
    for j,(label,duration) in enumerate([('×0,5',450),('×1',900),('×1,5',1350),('«Нет»',450)]):
        y=1012+j*13
        c.text((56,y),label,13,'cream',True)
        c.rect((axis_x(0),y+1,axis_x(2125),y+3),fill='p1')
        c.rect((axis_x(60),y+6,axis_x(60+duration),y+10),outline='secondary')
        c.text((axis_x(2125)+12,y),f'−N · {duration} мс',13,'secondary',True)
    c.text((1560,1012),'SKIP НЕ ОБРЫВАЕТ',17,'warm',True)
    c.text((1560,1039),'клип и растворение',15,'secondary')
    c.text((56,1065),'Вполоборота ≤45° · к цели за 120 мс · возврат 150 мс · наклон 10° · без подскока · ease 80 мс',13,'secondary')
    c.text((1820,1065),'Без колен · flash не масштабируется',13,'secondary',False,'rt')
    name='vector/AN-30-death-sheet.png' if width==1920 else f'comparison/AN-30-death-sheet-{width}.png'
    im=c.save(name)
    gray_name='comparison/AN-30-death-sheet-gray.png' if width==1920 else f'comparison/AN-30-death-sheet-{width}-gray.png'
    gray(im).save(output(gray_name))
    return im


def comparison(masks, width=1920):
    c=Canvas(width, round(width*1080/1920))
    c.text((56,45),'AN-30 / ПЕПЕЛ И REDUCED MOTION',44,'primary',True)
    c.text((56,108),'Одна конечная поза · те же моменты · обычный fade сохраняет геометрию',24,'secondary')
    for actor,y,team in [('KingArthur',217,'p1'),('Harpy',634,'p2')]:
        c.text((56,y),'KING ARTHUR' if actor=='KingArthur' else 'HARPY',30,team,True)
        c.text((56,y+48),'ASH',22,'warm',True)
        c.text((56,y+224),'FADE',22,'cream',True)
        for j,p in enumerate([0,.35,.70,1]):
            x=400+j*450
            c.text((x,y),['поза удержана','35 %','70 %','фигура исчезла'][j],25,'primary',True,'mt')
            c.pose(masks[actor,21],x,y+207,actor,progress=p,dots=10 if p and p<1 else 0)
            c.pose(masks[actor,21],x,y+386,actor,progress=p,reduced=True)
    c.text((56,1050),'Фронт #FFB45C · P1 #E8C06A · P2 #5A7F9F · без градиентов · ≤40 точек; fade — без частиц',20,'secondary')
    suffix='' if width==1920 else f'-{width}'
    im=c.save(f'comparison/AN-30-ash-vs-fade{suffix}.png')
    gray(im).save(output(f'comparison/AN-30-ash-vs-fade{suffix}-gray.png'))


def source_audit():
    before=json.loads((PACKAGE/'source-hashes-before.json').read_text(encoding='utf-8'))
    after={'schema':1,'task':'AN-30','inputs':{},'hud_icons_v3':{}}
    changed=[]
    for group in ['inputs','hud_icons_v3']:
        for name,record in before[group].items():
            p=REPO/name
            measured={'sha256':digest(p),'bytes':p.stat().st_size} if p.exists() else None
            after[group][name]=measured
            if measured!=record: changed.append(name)
    actual={p.relative_to(REPO).as_posix() for p in (REPO/'art/imagegen/hud-icons-v3').rglob('*') if p.is_file()}
    added=sorted(actual-set(before['hud_icons_v3']))
    after['hud_file_count']=len(actual)
    write_json('source-hashes-after.json',after)
    return before,changed,added


def verify():
    previous_review={'performed':False,'note':'pending manual inspection'}
    old_verification=PACKAGE/'verification.json'
    if old_verification.exists():
        previous_review=json.loads(old_verification.read_text(encoding='utf-8')).get('visual_review',previous_review)
        reviewed=previous_review.get('artifact_sha256',{})
        if not reviewed or any(not (PACKAGE/name).exists() or digest(PACKAGE/name)!=h for name,h in reviewed.items()):
            previous_review={'performed':False,'note':'pending manual inspection of current artifacts'}
    before,changed,added=source_audit()
    snapshot_equal=digest(PACKAGE/'_tools/draw_icons_v3_snapshot.py')==before['hud_icons_v3']['art/imagegen/hud-icons-v3/_tools/draw_icons.py']['sha256']
    a=np.array(Image.open(PACKAGE/'vector/AN-30-death-sheet.png'))
    b=np.array(Image.open(PACKAGE/'comparison/AN-30-death-sheet-gray.png'))
    expected=np.rint(a[:,:,:3].astype(float) @ np.array([.2126,.7152,.0722])).astype('uint8')
    gray_ok=all(np.array_equal(b[:,:,i],expected) for i in range(3)) and np.array_equal(a[:,:,3],b[:,:,3])
    timings=json.loads((PACKAGE/'reports/timing.json').read_text(encoding='utf-8'))
    for role,gone,hold,ash in [('hero',2125,300,500),('sidekick',1725,0,400)]:
        schedule=timings[role]
        assert schedule['hitreact']==[0,450]
        assert schedule['deathsettle']==[450,450+875]
        assert schedule['ash']==[450+875+hold,450+875+hold+ash]
        assert schedule['gone']==gone==schedule['ash'][1]
    assert timings['hero']['result']==timings['hero']['gone']+1000==3125
    assert timings['sidekick']['result'] is None
    for f,t in timings['frame_times_ms'].items(): assert 450+round(int(f)*1000/24)==t
    all_gray=[]
    for p in sorted((PACKAGE/'comparison').glob('*-gray.png')):
        color=PACKAGE/'vector/AN-30-death-sheet.png' if p.name=='AN-30-death-sheet-gray.png' else p.with_name(p.name.replace('-gray.png','.png'))
        aa=np.array(Image.open(color));bb=np.array(Image.open(p))
        yy=np.rint(aa[:,:,:3].astype(float) @ np.array([.2126,.7152,.0722])).astype('uint8')
        ok=all(np.array_equal(bb[:,:,i],yy) for i in range(3)) and np.array_equal(aa[:,:,3],bb[:,:,3])
        all_gray.append({'file':p.relative_to(PACKAGE).as_posix(),'rec709_exact':ok})
        assert ok
    ember_total=sum(e['embers'] for e in EFFECT_REPORT[:4])
    all_overlap=[r for r in LAYOUT_REPORT if r['overlapping_labels']]
    allowed={'0','1','2','3','10','13','21','24','30','34','35','40','45','60','70','80','120','150',
             '300','400','450','500','575','600','875','992','1000','1100','1325','1625','1725','2125','3125','900','1350','0,5','1,5'}
    unknown=[]
    for label in set(TEXT_LOG):
        clean=re.sub(r'#[A-Fa-f0-9]{6}', '', label)
        for n in re.findall(r'\d+(?:,\d+)?',clean):
            if n.lstrip('0') not in allowed and n not in allowed and int(n.split(',')[0] or '0') != 0:
                unknown.append({'label':label,'number':n})
    assert not unknown, unknown
    checks={'source_unchanged':not changed and not added,'hud_snapshot_byte_identical':snapshot_equal,
            'rgba_1920x1080':a.shape==(1080,1920,4),'rec709_exact':gray_ok,'all_gray_exports':all_gray,
            'timing_arithmetic_checked':True,'printed_number_sources_covered':not unknown,
            'hero_gone_ms':2125,'sidekick_gone_ms':1725,'gone_error_ms':{'hero':0,'sidekick':0},
            'acceptance_tolerance_ms':42,'heart_cross_ms':1100,'hero_result_ms':3125,
            'embers_per_fighter_per_pictured_state':10,'main_sheet_ember_dots':ember_total,
            'runtime_ember_budget_per_fighter':40,'ember_lifetime_ms':600,
            'ash_exact_rgb':all(tuple(e['front_rgb'])==rgb('warm') and tuple(e['ash_rgb'])==rgb('p1' if e['actor']=='KingArthur' else 'p2') for e in EFFECT_REPORT),
            'reduced_motion':'plain uniform opacity fade of unaltered final silhouette; no particles, no front',
            'no_kneeling':'original standing/bowed source poses, feet endpoints unchanged; visual inspection required',
            'no_image_generation':True,'clip_frames':[0,3,13,21],'pose_view':'q34',
            'no_text_overlaps':not all_overlap}
    write_json('reports/layout.json',LAYOUT_REPORT)
    write_json('reports/printed-labels.json',sorted(set(TEXT_LOG)))
    files=list(PACKAGE.rglob('*'))
    preserved=json.loads(old_verification.read_text(encoding='utf-8'))
    replacement={
        'task':'AN-30','status':'предложено','source_unchanged':checks['source_unchanged'],
        'outside_folder':[], 'changed_sources':changed,'added_hud_files':added,
        'input_count':len(before['inputs']),'hud_file_count':len(before['hud_icons_v3']),
        'checks':checks,'layout':LAYOUT_REPORT,'effect_samples':EFFECT_REPORT,
        'write_audit':{'method':'all script writes resolve through output() package path guard; source hashes independently re-read after rendering; direct file edits and procedural studies were also confined to package',
                       'written_files':sorted(WRITE_LOG),'scope_limit':'No whole-disk or other-session change claim; outside_folder records writes by this task only. No writes to scraped-data were necessary.'},
        'limitations':[
            {'id':'INPUT-JPEG','detail':'Only annotated JPEG sheets are supplied; segmentation removes bones overlays heuristically. Thin sword/feather outlines can lose a few pixels. Masks and SVG row runs are supplied for review; no invented pose.'},
            {'id':'HITREACT-CONFLICT','detail':'02 §9.2 CUE-011 says lethal HitReact 550 ms; AN-30 and CUE-013/F-09 specify 450 ms. Task-specific 450 ms takes precedence.'},
            {'id':'SPEED-NONE','detail':'Resolved by ВР-VS3-AN30-01: death is unchanged by speed, ash remains ash; only damage-number duration scales. Static proposal; runtime not tested.'},
            {'id':'NO-RUNTIME','detail':'Static design package only. No Unreal, clip playback, runtime shader, skip handling, particle lifetime or performance validation was executed.'},
            {'id':'WORKING-SIZE','detail':'At 960×540 the full overview has small technical text; 1280×720 is the recommended working overview. Read timings from the master and README.'},
        ],'visual_review':previous_review,
    }
    preserved['checks'].update(replacement.pop('checks'))
    replacement['checks']=preserved['checks']
    replacement['limitations']=[dict(item, detail=('Resolved by ВР-VS3-AN30-01: speed never scales death; ash remains ash at every speed.' if item['id']=='SPEED-NONE' else item['detail'])) for item in preserved['limitations']]
    preserved.update(replacement)
    write_json('verification.json',preserved)
    assert not changed and not added, 'Source mutation detected'
    assert snapshot_equal and gray_ok and a.shape==(1080,1920,4)
    assert ember_total<=40, ember_total
    assert not all_overlap, all_overlap
    print(json.dumps({'checks':checks,'files':len(files)},ensure_ascii=False,indent=2))


def main():
    masks={}; tiles=[]
    for actor in SOURCE:
        for frame in [0,3,13,21]:
            masks[actor,frame],tile=trace(actor,frame)
            tiles.append((actor,frame,tile))
    write_json('reports/tracing.json',TRACE_REPORT)
    # Source render + traced flat silhouette comparison; neutral render only.
    board=Image.new('RGBA',(1680,840),rgb('navy')+(255,))
    for i,(actor,frame,tile) in enumerate(tiles):
        x=(i%4)*420; y=(i//4)*420
        board.alpha_composite(tile.convert('RGBA').resize((210,210)),(x,y+75))
        m=Image.fromarray(masks[actor,frame].astype('uint8')*255).resize((210,210),Image.Resampling.NEAREST)
        flat=Image.new('RGBA',(210,210),rgb('cream')+(255,));flat.putalpha(m)
        board.alpha_composite(flat,(x+210,y+75))
        d=ImageDraw.Draw(board);f=ImageFont.truetype(str(FONT_DIR/'Roboto-Regular.ttf'),19)
        d.text((x+12,y+20),f'{actor} / f{frame:02d} / q34',font=f,fill=rgb('primary'))
        d.text((x+12,y+305),'Source JPEG → traced silhouette',font=f,fill=rgb('secondary'))
    board.save(output('comparison/AN-30-source-vs-trace.png'))
    gray(board).save(output('comparison/AN-30-source-vs-trace-gray.png'))
    for width in [1920,1280,960]: sheet(masks,width)
    for width in [1920,1280,960]: comparison(masks,width)
    # Keep all original records and all original concepts byte-for-byte.
    master=PACKAGE/'vector/AN-30-death-sheet.png'
    raw=output('concepts/AN-30-death-sheet-fix1-unretouched.png')
    raw.write_bytes(master.read_bytes())
    records=json.loads((PACKAGE/'generation-records.json').read_text(encoding='utf-8'))
    records['corrective_runs']=[r for r in records.get('corrective_runs',[]) if r.get('prompt_key')!='AN-30/fix1']
    records['corrective_runs'].append({'id':'AN-30/fix1','card_id':'AN-30','prompt_key':'AN-30/fix1',
        'tool':'procedural Pillow / existing trace masks','mode':'corrective procedural redraw',
        'original_path':'concepts/AN-30-death-sheet-fix1-unretouched.png',
        'saved_path':'vector/AN-30-death-sheet.png','sha256':digest(master),
        'selected':True,'date':'2026-10-07','image_generations':0,
        'exact_prompt':json.loads((PACKAGE/'prompts/AN-30-prompts.json').read_text(encoding='utf-8'))['AN-30/fix1']})
    write_json('generation-records.json',records)
    write_json('reports/timing.json',{
        'origin':'killing blow Contact AnimNotify','fps':24,'frame_times_ms':{'0':450,'3':575,'13':992,'21':1325},
        'hero':{'hitreact':[0,450],'deathsettle':[450,1325],'still':[1325,1625],'ash':[1625,2125],'gone':2125,'result':3125},
        'sidekick':{'hitreact':[0,450],'deathsettle':[450,1325],'still_ms':0,'ash':[1325,1725],'gone':1725,'result':None},
        'cue':{'contact':0,'flash':[0,70],'damage':60,'hp':80,'fallen_heart':1100},
        'dissolve_samples':{'hero':{'35_percent_ms':1800,'70_percent_ms':1975},'sidekick':{'35_percent_ms':1465,'70_percent_ms':1605}},
        'speed_variants':{key:{'clip_duration_factor':1,'death_ms':[0,2125],
                             'damage_start_ms':60,'damage_duration_ms':duration,'ash_stays_ash':True}
                          for key,duration in [('0.5',450),('1',900),('1.5',1350),('none',450)]},
        'speed_scope':'ВР-VS3-AN30-01 / UI-ACC-013: duration multiplier for damage only; all CUE-013 death timing unchanged.',
        'skip_cuts_clip':False,'skip_cuts_dissolve':False,
        'reduced_motion':{'fade_hero_ms':500,'fade_sidekick_ms':400,'embers':0,'flash_replacement':'uniform opacity change, no flash'},
    })
    verify()


if __name__=='__main__':
    sys.stdout.reconfigure(encoding='utf-8')
    main()
