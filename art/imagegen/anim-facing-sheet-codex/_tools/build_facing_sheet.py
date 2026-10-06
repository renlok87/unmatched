#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""AN-26. Procedural exports; execute with python -B. Writes only PACKAGE.

The HUD generator snapshot is imported for its token helpers, never executed.
Source images remain untouched. There is no Git, Unreal, network, MCP or AI call.
"""
from __future__ import annotations
import datetime
import hashlib
import json
import math
from pathlib import Path
import runpy
import sys

import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageFilter
from scipy import ndimage as ndi

sys.dont_write_bytecode = True
PACKAGE = Path(__file__).resolve().parents[1]
ROOT = PACKAGE.parents[2]
SNAPSHOT = runpy.run_path(str(PACKAGE / '_tools/draw_icons_v3_snapshot.py'), run_name='hud_snapshot')
TOKENS = {k: SNAPSHOT['TOKENS'][k] for k in ('card.navy', 'card.cream', 'mark.keyline',
          'text.secondary', 'turn.flash.yellow', 'state.error')}
TOKENS['text.primary'] = '#F2EDE4'
N, C, K, T, S, Y, R = [TOKENS[k] for k in ('card.navy', 'card.cream', 'mark.keyline',
                     'text.primary', 'text.secondary', 'turn.flash.yellow', 'state.error')]
FONT_B = Path(SNAPSHOT['FONT_BC'])
FONT_R = Path(SNAPSHOT['FONT_RG'])
WRITES = set()
TEXT_RECORDS = []
TRACE_RECORDS = []
LAYOUT_ISSUES = []
SIZES = [(1920, 1080), (1280, 720), (960, 540)]
# Rounded milliseconds explicitly specified by the task, rather than invented timing.
BASE = {'pause': [-300, 0], 'turn': [-120, 0], 'clip': [0, 583],
        'return': [583, 733], 'contact_arthur_harpy': 292, 'contact_merlin_medusa': 333}

def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()

def output(name):
    p = (PACKAGE / name).resolve()
    if not p.is_relative_to(PACKAGE):
        raise ValueError(f'Output outside package: {p}')
    p.parent.mkdir(parents=True, exist_ok=True)
    WRITES.add(p.relative_to(PACKAGE).as_posix())
    return p

def save_json(name, obj):
    output(name).write_text(json.dumps(obj, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')

def source(hero, clip):
    asset = 'KING-ARTHUR' if hero == 'KingArthur' else 'MEDUSA'
    p = ROOT / f'art/pipeline-candidates/ASSET-{asset}-001/20260929-h2anim/preview'
    return p / f'{hero}-{clip}-blender-sheet.jpg', p / f'frames/{hero}-{clip}-bones2d.json'

def trace(hero, clip, tile):
    """Trace a source tile, remove only chromatic bone pixels supported by bones2d.

    Nearest uncontaminated pixels reconstruct underneath each bone. Difference
    from the measured flat background gives the silhouette. Small closing bridges
    JPEG seams; only tiny disconnected noise is discarded. No polygon hero is invented.
    """
    jpg, bones_path = source(hero, clip)
    bones = json.loads(bones_path.read_text(encoding='utf-8'))
    index = list(bones).index(tile)
    x, y = (index % 4) * 420, (index // 4) * 420
    crop = Image.open(jpg).convert('RGB').crop((x, y, x+420, y+420))
    a = np.array(crop).astype(np.int16)
    support = Image.new('L', crop.size)
    d = ImageDraw.Draw(support)
    for bone in bones[tile]['bones']:
        pa, pb = tuple(bone['a']), tuple(bone['b'])
        d.line([pa, pb], fill=255, width=9)
        for px, py in (pa, pb):
            d.ellipse((px-7, py-7, px+7, py+7), fill=255)
    red = (a[:,:,0] > a[:,:,1] + 42) & (a[:,:,0] > a[:,:,2]+42)
    yellow = (a[:,:,0] > 120) & (a[:,:,1] > 100) & (a[:,:,2] < 95) & (a[:,:,0] + a[:,:,1] > a[:,:,2]*3+160)
    overlay = (red | yellow) & (np.array(support) > 0)
    overlay = ndi.binary_dilation(overlay, iterations=2)
    nearest = ndi.distance_transform_edt(overlay, return_distances=False, return_indices=True)
    cleaned = a.copy()
    cleaned[overlay] = a[nearest[0][overlay], nearest[1][overlay]]
    bg = np.median(a[60:390, 12:60].reshape(-1,3), axis=0)
    mask = np.max(np.abs(cleaned-bg), axis=2) > 15
    mask[:36] = False
    mask[414:] = False
    mask[:,:10] = False
    mask[:,410:] = False
    mask = ndi.binary_closing(mask, iterations=2)
    labels, count = ndi.label(mask)
    sizes = np.bincount(labels.ravel())
    keep = sizes >= 100
    keep[0] = False
    mask = keep[labels]
    mask = ndi.binary_fill_holes(mask)
    # The cylindrical base is convex in these source renders. Dark base pixels
    # can equal the flat background; close each measured base scanline between
    # its observed left/right edges, retaining the actual rendered outline.
    for row in range(368, 401):
        present = np.flatnonzero(mask[row])
        if len(present) > 15:
            mask[row, present[0]:present[-1]+1] = True
    im = Image.fromarray((mask*255).astype('uint8'))
    name = f'{hero}-{clip}-{tile.replace(" ", "-")}'
    im.save(output(f'silhouettes/{name}-mask.png'))
    crop.save(output(f'concepts/{name}-source-tile.png'))
    ys, xs = np.where(mask)
    bbox = [int(xs.min()),int(ys.min()),int(xs.max()+1),int(ys.max()+1)]
    TRACE_RECORDS.append({'id':name,'source':jpg.relative_to(ROOT).as_posix(),
         'bones':bones_path.relative_to(ROOT).as_posix(),'tile':tile,'tile_index':index,
         'crop_xyxy':[x,y,x+420,y+420], 'mask_bbox':bbox,
         'overlay_pixels_removed':int(overlay.sum()), 'foreground_pixels':int(mask.sum()),
         'method':'bones2d-supported chromatic overlay removal; nearest valid pixel reconstruction; background difference; closing; component filtering; hole filling',
         'back_view':False})
    return im.crop(tuple(bbox))

class Canvas:
    def __init__(self, width, height):
        self.scale = width/1920
        self.ss = 2
        self.u = self.scale*self.ss
        self.image = Image.new('RGBA', (width*self.ss,height*self.ss), N)
        self.d = ImageDraw.Draw(self.image)
        self.size = (width,height)
    def xy(self, p): return tuple(round(v*self.u) for v in p)
    def line(self, points, color=S, width=1):
        self.d.line([self.xy(p) for p in points], fill=color, width=max(1,round(width*self.u)))
    def box(self, rect, fill=None, outline=None, width=1):
        self.d.rectangle(self.xy(rect), fill=fill, outline=outline, width=max(1,round(width*self.u)))
    def ellipse(self, rect, fill=None, outline=None, width=1):
        self.d.ellipse(self.xy(rect), fill=fill, outline=outline, width=max(1,round(width*self.u)))
    def polygon(self, points, fill, outline=None, width=1):
        ps=[self.xy(p) for p in points]
        self.d.polygon(ps, fill=fill)
        if outline:self.d.line(ps+[ps[0]],fill=outline,width=max(1,round(width*self.u)))
    def text(self, x, y, text, size=22, color=T, bold=False, anchor='lt'):
        font=ImageFont.truetype(str(FONT_B if bold else FONT_R),max(1,round(size*self.u)))
        pos=self.xy((x,y))
        bbox=self.d.textbbox(pos,text,font=font,anchor=anchor)
        if bbox[0]<0 or bbox[1]<0 or bbox[2]>self.image.width or bbox[3]>self.image.height:
            LAYOUT_ISSUES.append({'size':self.size,'text':text,'bbox':bbox})
        self.d.text(pos,text,font=font,fill=color,anchor=anchor)
        if self.size==(1920,1080):TEXT_RECORDS.append({'text':text,'xy':[x,y],'font_px':size,'bold':bold,'bbox':[v/self.u for v in bbox]})
    def arrow(self, a, b, color=Y, width=2, head=8):
        self.line([a,b],color,width)
        angle=math.atan2(b[1]-a[1],b[0]-a[0])
        self.polygon([b,(b[0]-head*math.cos(angle-.45),b[1]-head*math.sin(angle-.45)),
                       (b[0]-head*math.cos(angle+.45),b[1]-head*math.sin(angle+.45))],color)
    def arc(self, cx,cy,r,start,end,color=Y,width=2,arrow=False):
        # Angle measured away from camera direction, which points upward.
        pts=[(cx+r*math.sin(math.radians(v)),cy-r*math.cos(math.radians(v))) for v in np.linspace(start,end,80)]
        self.line(pts,color,width)
        if arrow:self.arrow(pts[-3],pts[-1],color,width)
    def pose(self, mask, cx, top, maxw=205, maxh=220):
        ratio=min(maxw/mask.width,maxh/mask.height)
        w,h=round(mask.width*ratio*self.u),round(mask.height*ratio*self.u)
        m=mask.resize((w,h),Image.Resampling.LANCZOS)
        layer=Image.new('RGBA',m.size,C);layer.putalpha(m)
        pad=max(2,round(3*self.u))
        big=Image.new('L',(w+pad*2,h+pad*2));big.paste(m,(pad,pad))
        outline=big.filter(ImageFilter.MaxFilter(pad*2+1))
        ink=Image.new('RGBA',outline.size,K);ink.putalpha(outline)
        px=round(cx*self.u-w/2);py=round(top*self.u+(maxh* self.u-h))
        self.image.alpha_composite(ink,(px-pad,py-pad))
        self.image.alpha_composite(layer,(px,py))
    def export(self): return self.image.resize(self.size,Image.Resampling.LANCZOS)

def tick(c,x,y,shape,color=C):
    if shape=='circle':c.ellipse((x-4,y-4,x+4,y+4),color)
    elif shape=='diamond':c.polygon([(x,y-5),(x+5,y),(x,y+5),(x-5,y)],color)
    else:c.line([(x,y-8),(x,y+8)],color,3)

X0,X1,MIN,MAX=250,1405,-300,1025
def tx(t):return X0+(t-MIN)/(MAX-MIN)*(X1-X0)

def bar(c,start,end,y,height=20,color=C,filled=False):
    c.box((tx(start),y,tx(end),y+height),fill=color if filled else N,outline=color,width=2)

def plan(c):
    c.text(1482,156,'ПЛАН ПОВОРОТА',24,bold=True)
    cx,cy=1665,424
    c.arc(cx,cy,155,-90,90,S,2)
    c.arc(cx,cy,115,-45,45,Y,4)
    for a in [-90,-45,45,90]:
        r=155 if abs(a)==90 else 115
        c.line([(cx,cy),(cx+r*math.sin(math.radians(a)),cy-r*math.cos(math.radians(a)))],S,1)
    c.arrow((cx,cy),(cx,243),C,2)
    c.text(cx,210,'КАМЕРА КЛИЕНТА',20,bold=True,anchor='mt')
    c.text(1490,287,'−45°',22,Y,bold=True)
    c.text(1795,285,'+45°',22,Y,bold=True)
    c.text(1495,437,'−90°',20,S)
    c.text(1790,437,'+90°',20,S)
    # Discs and headings in a schematic plane, no actual board illustration.
    enemy=(1591,337);target=(1529,369)
    c.ellipse((enemy[0]-13,enemy[1]-13,enemy[0]+13,enemy[1]+13),S,K,2)
    c.text(1545,255,'враг',18,S)
    c.ellipse((target[0]-15,target[1]-15,target[0]+15,target[1]+15),C,K,3)
    c.text(1482,322,'цель',18,C)
    c.arrow((cx,cy),enemy,S,2)
    c.arrow((cx,cy),target,Y,3)
    c.ellipse((cx-20,cy-20,cx+20,cy+20),N,C,3)
    idle = math.degrees(math.atan2(-24,36))
    for a in [idle-10,idle+10]:
        c.line([(cx+r*math.sin(math.radians(a)),cy-r*math.cos(math.radians(a)))
                for r in [30,100]],C,2)
    c.arc(cx,cy,100,idle-10,idle+10,C,4)
    c.arrow((cx,cy),(cx+90*math.sin(math.radians(idle)),
                          cy-90*math.cos(math.radians(idle))),C,3)
    c.text(1685,464,'мёртвая зона ±10°',18,T)
    c.text(1482,487,'Покой: к ближайшему живому врагу',20)
    c.text(1482,515,'в пределах ±45°; dead band 10°.',20,S)
    c.text(1482,550,'Атака: к цели, предел ±90°.',20)
    c.text(1482,578,'Цель не поворачивается.',20,S)
    c.text(1482,607,'меньше 10° от текущего угла — угол не меняется (AN-23)',14,T,True)

def draw(width,height,masks):
    c=Canvas(width,height)
    c.text(48,38,'ПОВОРОТ, ВЫПАД, ВОЗВРАТ',47,bold=True)
    c.text(48,98,'Idle / face / LungeAttack / Idle   ·   общий отсчёт от начала выпада',23,S)
    c.text(1872,43,'AN-26',31,Y,bold=True,anchor='rt')
    c.text(1872,87,'ПРЕДЛОЖЕНО',19,S,bold=True,anchor='rt')
    c.line([(48,135),(1872,135)],S)
    c.line([(1450,154),(1450,1030)],S)
    c.text(48,164,'ВРЕМЯ · мс',22,bold=True)
    c.line([(X0,195),(X1,195)],S,2)
    for t in [-300,-120,0,292,333,583,733]:
        x=tx(t);c.line([(x,193),(x,203)],Y if t in [292,333] else S,2)
        yy=157 if t!=333 else 174
        c.text(x,yy,str(t).replace('-','−'),20,Y if t in [292,333] else T,bold=True,anchor='mt')
    c.text(48,213,'ПОСЛЕ SLAM',20,S,bold=True)
    bar(c,-300,0,213,24,S)
    c.text((tx(-300)+tx(0))/2,215,'Счёт · 300 мс',19,S,anchor='mt')
    c.text(48,258,'ОРИЕНТАЦИЯ',20,bold=True)
    c.line([(tx(-300),267),(tx(-120),267)],C,3)
    c.text((tx(-300)+tx(-120))/2,249,'покой',19,C,anchor='mt')
    bar(c,-120,0,251,31,Y,True);c.text((tx(-120)+tx(0))/2,255,'120 мс',20,N,True,'mt')
    bar(c,0,583,251,31,C);c.text((tx(0)+tx(583))/2,255,'LungeAttack · 583 мс',21,C,True,'mt')
    bar(c,583,733,251,31,Y,True);c.text((tx(583)+tx(733))/2,255,'150 мс',20,N,True,'mt')
    c.text(48,298,'КАДРЫ · 24 fps',20,S,bold=True)
    for t,label in [(0,'0'),(292,'7'),(333,'8'),(583,'14')]:
        c.line([(tx(t),286),(tx(t),300)],S)
        c.text(tx(t),304,label,18,S,anchor='mt')
    c.text(48,347,'КЛЮЧЕВЫЕ ПОЗЫ',23,bold=True)
    # Editorial pose spacing; every card explicitly names its event time.
    poses=[(175,'ПОКОЙ','−300 мс · Idle · к. 0',masks[0]),
           (432,'К ЦЕЛИ','0 мс · Lunge · к. 0',masks[1]),
           (689,'КОНТАКТ','292 мс · Arthur · к. 7',masks[2]),
           (946,'ВЫПУСК СТРЕЛЫ','333 мс · Medusa · к. 8',masks[3]),
           (1203,'ВОЗВРАТ','733 мс · Idle · к. 0',masks[0])]
    for cx,title,subtitle,mask in poses:
        c.pose(mask,cx,383,205,207)
        c.line([(cx-103,595),(cx+103,595)],S)
        c.text(cx,607,title,21,bold=True,anchor='mt')
        c.text(cx,636,subtitle,17,S,anchor='mt')
        c.arrow((cx+83,560),(cx+83,522),C,2,6)
    c.text(1388,605,'камера',16,S,anchor='rt')
    c.text(48,679,'CUE · от контакта',21,bold=True)
    tick(c,1050,689,'circle',Y);c.text(1065,679,'Arthur / Harpy',18,S)
    tick(c,1225,689,'diamond',C);c.text(1240,679,'Merlin / Medusa',18,S)
    for t in [0,583,733]:
        for yy in range(710,1034,12):c.line([(tx(t),yy),(tx(t),yy+2)],S)
    for y,label in [(718,'Contact notify'),(750,'Flash · 70 мс'),(782,'Урон · +60 мс'),(814,'HP · +80 мс')]:
        c.text(48,y-9,label,19,S)
        c.line([(X0,y),(X1,y)],S)
        for contact,shape,color in [(292,'circle',Y),(333,'diamond',C)]:
            if label.startswith('Flash'):
                # Stagger micro-bars around one row so their overlaps remain visible in gray.
                offset=-4 if shape=='circle' else 4
                c.line([(tx(contact),y+offset),(tx(contact+70),y+offset)],color,4)
                tick(c,tx(contact),y+offset,shape,color)
            else:
                offset=60 if label.startswith('Урон') else 80 if label.startswith('HP') else 0
                tick(c,tx(contact+offset),y,shape,color)
    c.text(48,839,'СКОРОСТЬ',21,bold=True)
    c.text(1395,839,'Поворот и возврат не масштабируются',18,S,anchor='rt')
    for y,speed,rate in [(873,.5,2),(914,1,1),(955,1.5,.67)]:
        c.text(48,y-4,f'×{speed:g}  / rate {rate:g}',19,S)
        bar(c,-120,0,y,21,Y,True)
        end=583*speed
        bar(c,0,end,y,21,C)
        bar(c,end,end+150,y,21,Y,True)
        for t,shape,color in [(292*speed,'circle',Y),(333*speed,'diamond',C)]:tick(c,tx(t),y+10,shape,color)
    c.text(48,992,'Reduced motion',19,S)
    c.line([(tx(0),1003),(tx(583),1003)],C,2)
    # Reduced preserves the x1 clip; none removes that clip as well. Two shapes
    # at zero communicate none; turn/return instantaneous at clip boundaries in reduced.
    tick(c,tx(0),1003,'line',Y);tick(c,tx(583),1003,'line',Y)
    c.text(tx(0)+18,982,'поворот / возврат мгновенно',17,S)
    c.text(48,1023,'Скорость none',19,S)
    tick(c,tx(0),1033,'diamond',Y)
    c.text(tx(0)+18,1023,'snap · без клипа · поворот и возврат сразу',17,S)
    c.text(48,1051,'Покой пересчитывается: snapshot / конец хода / конец атаки; изменение yaw — короткая дуга за 150 мс.',18,S)
    plan(c)
    # Honest schematic rear orientation: a disc and a traced contour, not a fake back render.
    c.text(1482,627,'НЕДОПУСТИМО',23,bold=True)
    c.pose(masks[0],1550,663,93,119)
    c.line([(1524,707),(1577,741)],K,3) # cape indication, explicitly schematic
    c.line([(1505,677),(1594,786)],R,6)
    c.line([(1594,677),(1505,786)],R,6)
    c.text(1617,673,'Схема спины',21,bold=True)
    c.text(1617,708,'направление',19,S)
    c.text(1617,735,'от камеры',19,S)
    c.arrow((1708,790),(1708,764),C,2)
    c.arrow((1708,814),(1708,840),Y,3)
    c.text(1740,790,'камера',17,S)
    c.text(1482,881,'ПРАВИЛО ШАГА',23,bold=True)
    c.text(1482,918,'Наклон 10° · без подскока',20)
    c.text(1482,951,'Ease по 80 мс на концах пути',20,S)
    c.text(1482,990,'Дуги: поворот / возврат',20,Y)
    c.arc(1810,1022,22,-60,70,Y,3,True)
    return c.export()

def grayscale(im):
    a=np.array(im)
    gray=np.rint(a[:,:,:3].astype(float) @ np.array([.2126,.7152,.0722])).astype(np.uint8)
    return Image.fromarray(np.dstack([gray,gray,gray,a[:,:,3]]))

def build():
    prompt=ROOT/'docs/game-design/visual/06-tasks/prompts/AN-26.codex.md'
    text=prompt.read_text(encoding='utf-8').split('## Task',1)[1].split('```text\n',1)[1].rsplit('```',1)[0].rstrip('\n')
    output('prompt.txt').write_text(text,encoding='utf-8')
    key='AN-26/task/sha256:'+hashlib.sha256(text.encode('utf-8')).hexdigest()
    # fix1 reuses the accepted source tiles and traced masks without rewriting them.
    TRACE_RECORDS.extend(json.loads((PACKAGE/'silhouettes/tracing-records.json').read_text(encoding='utf-8')))
    masks=[Image.open(PACKAGE/f'silhouettes/{r["id"]}-mask.png').crop(tuple(r['mask_bbox']))
           for r in TRACE_RECORDS]
    # Unretouched source tiles alongside the extracted masks, proof of tracing.
    proof=Image.new('RGB',(1680,840),N)
    for i,rec in enumerate(TRACE_RECORDS):
        src=Image.open(PACKAGE/f'concepts/{rec["id"]}-source-tile.png')
        proof.paste(src,(420*i,0))
        raw=Image.open(PACKAGE/f'silhouettes/{rec["id"]}-mask.png')
        layer=Image.new('RGB',raw.size,C);bg=Image.new('RGB',raw.size,N);bg.paste(layer,mask=raw)
        proof.paste(bg,(420*i,420))
    proof=proof.convert('RGBA')
    proof.save(output('comparison/AN-26-tracing-proof.png'))
    grayscale(proof).save(output('comparison/AN-26-tracing-proof-gray.png'))
    for w,h in SIZES:
        im=draw(w,h,masks);gray=grayscale(im)
        suffix='' if w==1920 else f'-{w}x{h}'
        im.save(output(f'vector/AN-26-facing-sheet{suffix}.png'))
        im.save(output(f'comparison/AN-26-facing-sheet-color{suffix}.png'))
        gray.save(output(f'comparison/AN-26-facing-sheet-gray{suffix}.png'))
        if w==1920:
            im.save(output('concepts/AN-26-concept-B-fix1-unretouched.png'))
            for label,sheet in [('color',im),('gray',gray)]:
                sheet.crop((1470,195,1872,625)).resize((804,860),Image.Resampling.NEAREST).save(
                    output(f'concepts/review/AN-26-plan-fix1-{label}-x2.png'))
    def task_text(path):
        return path.read_text(encoding='utf-8').split('## Task',1)[1].split('```text\n',1)[1].rsplit('```',1)[0]
    prompt_map={'AN-26/task':task_text(prompt),
                'AN-26/fix1':task_text(ROOT/'docs/game-design/visual/06-tasks/prompts/AN-26.fix1.codex.md'),
                key:text}
    save_json('prompts/AN-26-prompts.json',prompt_map)
    generations=json.loads((PACKAGE/'generation-records.json').read_text(encoding='utf-8'))
    for r in generations['records']:r['selected']=False
    generations['records']=[r for r in generations['records'] if r.get('prompt_key')!='AN-26/fix1-B']
    prompt_map['AN-26/fix1-B']=prompt_map['AN-26/fix1']
    save_json('prompts/AN-26-prompts.json',prompt_map)
    generations['records'].append({'id':'AN-26/fix1-B','prompt_key':'AN-26/fix1-B',
        'card_id':'AN-26','tool':'_tools/build_facing_sheet.py','mode':'procedural',
        'date':datetime.datetime.now(datetime.timezone.utc).isoformat(),
        'references':[{'path':r['source'],'sha256':sha(ROOT/r['source'])} for r in TRACE_RECORDS]+
                     [{'path':r['bones'],'sha256':sha(ROOT/r['bones'])} for r in TRACE_RECORDS]+
                     [{'path':prompt.relative_to(ROOT).as_posix(),'sha256':sha(prompt)},
                      {'path':'docs/game-design/visual/06-tasks/prompts/AN-26.fix1.codex.md',
                       'sha256':sha(ROOT/'docs/game-design/visual/06-tasks/prompts/AN-26.fix1.codex.md')}],
        'original_path':'concepts/AN-26-concept-B-fix1-unretouched.png',
        'saved_path':'concepts/AN-26-concept-B-fix1-unretouched.png',
        'prompt_file':'prompts/AN-26-prompts.json','selected':True,
        'method':'native procedural redraw; accepted render-derived masks unchanged',
        'unretouched':'concepts/AN-26-concept-B-fix1-unretouched.png',
        'source_tiles':[f'concepts/{r["id"]}-source-tile.png' for r in TRACE_RECORDS],
        'retouching':False,'variant':'B-fix1','generator':'_tools/build_facing_sheet.py'})
    save_json('generation-records.json',generations)
    save_json('layout-audit.json',{'texts':TEXT_RECORDS,'outside_canvas':LAYOUT_ISSUES})
    speed=[]
    for factor,rate in [(.5,2),(1,1),(1.5,.67)]:
        speed.append({'factor':factor,'display_play_rate':rate,'exact_play_rate':1/factor,
             'turn':[-120,0],'clip':[0,583*factor],'return':[583*factor,583*factor+150],
             'contacts':[292*factor,333*factor],
             'mapping':'duration multiplier; 0.67 display is rounded from 2/3'})
    save_json('timing-model.json',{'base':BASE,'axis_ms':[MIN,MAX],'axis_master_px':[X0,X1],
          'clip_fps':24,'clip_frames':14,'speed_lanes':speed,
          'reduced_motion':{'turn_ms':0,'return_ms':0,'clip':[0,583]},
          'none':{'turn_ms':0,'return_ms':0,'clip_ms':0},
          'cue_offsets':{'notify':0,'flash_duration':70,'damage':60,'hp':80},
          'angles':{'idle_limit':45,'dead_band':10,'attack_limit':90,'step_tilt':10},
          'changed_idle_yaw_ms':150,'step_end_ease_ms':80})
    save_json('palette.json',TOKENS)
    save_json('write-ledger.json',{'allowed_root':PACKAGE.relative_to(ROOT).as_posix(),
               'files':sorted(WRITES),'outside_folder':[],
               'note':'All renderer writes resolve through output(), rejects paths outside PACKAGE.'})
    print('Built AN-26; traced',len(masks),'masks; exports',len(SIZES),'sizes; layout bounds issues:',len(LAYOUT_ISSUES))

if __name__=='__main__':build()
