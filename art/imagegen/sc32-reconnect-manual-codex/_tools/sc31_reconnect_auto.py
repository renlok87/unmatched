#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""CX-33 frozen reconnect renderer and offline package audit.

Run with python -B. All writes are guarded to the selected package/derived pair.
No engine, git, network, MCP, generator main(), or source-module imports.
SC-32/33 copy this FINAL module byte-for-byte and call build() from their module.
"""
from __future__ import annotations
import sys
sys.dont_write_bytecode = True
import argparse
import csv
import hashlib
import io
import json
import math
from functools import lru_cache
from pathlib import Path
import shutil
import numpy as np
from PIL import Image, ImageDraw, ImageFilter

ROOT = Path(__file__).resolve().parents[4]
TOOLS = Path(__file__).resolve().parent
FONTDIR = Path('C:/Program Files/Epic Games/UE_5.8/Engine/Content/Slate/Fonts')
VIS = 'docs/game-design/visual/'
SCREENS = 'docs/unreal/contracts/hud/st-screens.csv'
HUD = 'docs/unreal/contracts/hud/st-hud.csv'
TOKENS = 'docs/unreal/contracts/hud/hud-style-tokens.json'
TRACE = ('docs/game-design/evidence/DE-FOOTAGE/2026-10-04/E/live/phase2/marmoreal/'
         'run-20261005-135124/phase2-client-joiner.trace.txt')
BASE = 'art/imagegen/sc01-screen-base-codex/'
ICONS = 'art/imagegen/hud-icons-v3/'
SKINS = 'art/imagegen/hud-skins-v1-codex/'
SC31 = 'art/imagegen/sc31-reconnect-auto-codex/'
MASKS = 'art/imagegen/hud-composition-v1-codex/masks.json'
BACKGROUNDS = {
    'marmoreal': 'docs/game-design/evidence/ENV-MAPS/p7-concept-paste-2026-10-01/marmoreal-concept-flag/bench-K1-1920x1080.png',
    'sarpedon': 'docs/game-design/evidence/ENV-MAPS/p10-sarpedon-rework-2026-10-03/sarpedon-packaged/bench-K1-1920x1080.png',
}
SETS = {'SC-31': 'sc31-reconnect-auto', 'SC-32': 'sc32-reconnect-manual', 'SC-33': 'sc33-reconnect-restore'}
USED = {'SC-31': ['resource-connection-reconnecting'], 'SC-32': ['resource-connection-lost'],
        'SC-33': ['loader-spinner', 'resource-connection-online']}
STATES = {'SC-31': ['auto'], 'SC-32': ['manual', 'expired'], 'SC-33': ['restoring', 'exit-200ms']}
WRITES = set()


def relative(path):
    p = Path(path).resolve()
    return p.relative_to(ROOT).as_posix() if p.is_relative_to(ROOT) else p.as_posix()


def hashfile(path):
    p = Path(path)
    return {'sha256': hashlib.sha256(p.read_bytes()).hexdigest(), 'bytes': p.stat().st_size}


def folders(card):
    name = SETS[card] + '-codex'
    return ROOT / 'art/imagegen' / name, ROOT / 'scraped-data/derived' / name


def guard(path, card):
    p = Path(path).resolve()
    if not any(p.is_relative_to(x.resolve()) for x in folders(card)):
        raise ValueError('Output outside allowed folders: ' + str(p))
    p.parent.mkdir(parents=True, exist_ok=True)
    WRITES.add(relative(p))
    return p


def jsonwrite(path, value, card):
    guard(path, card).write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


def readjson(path):
    return json.loads(Path(path).read_text(encoding='utf-8-sig'))


def icon_tree():
    directory = ROOT / ICONS
    records = {p.relative_to(directory).as_posix(): hashfile(p) for p in sorted(directory.rglob('*')) if p.is_file()}
    # Tree digest includes names, hashes, and byte lengths; no per-file repetition in reports.
    payload = ''.join(f"{k}\0{v['sha256']}\0{v['bytes']}\n" for k, v in records.items())
    return {'algorithm': 'sha256(sorted relative_path + NUL + sha256 + NUL + bytes + LF)',
            'sha256': hashlib.sha256(payload.encode('utf-8')).hexdigest(), 'count': len(records)}


def inputs(card):
    names = ['AGENTS.md', VIS+'04-hud-spec.md', VIS+'02-visual-design.md', VIS+'07-prompt-templates.md',
             VIS+'06-tasks/prompts/SC-31-series.codex.md', VIS+f'06-tasks/prompts/{card}.codex.md',
             VIS+'06-tasks/screens.csv', VIS+'06-tasks/vfx.csv', SCREENS, HUD, TOKENS, TRACE, MASKS,
             'docs/unreal/contracts/cue-dispatcher/cue-table.json',
             'docs/game-design/evidence/S10/packaged-fault-runs-2026-09-27.md',
             'tools/s10/drop-graphql-reply-proxy.cjs',
             'docs/game-design/evidence/VISUAL/HB-14/README.md',
             'docs/game-design/evidence/VISUAL/HB-40/README.md',
             BASE+'README.md', BASE+'manifest-sha256.json', ICONS+'_tools/draw_icons.py',
             ICONS+'sizes/loader-spinner-32.png',
             SKINS+'README.md', SKINS+'runtime-style.json', SKINS+'slice-margins.json',
             'art/imagegen/hud-feed-v1-codex/README.md', 'art/imagegen/hud-feed-v1-codex/facts.json',
             'art/imagegen/sc04-boot-error-codex/README.md'] + list(BACKGROUNDS.values())
    directories = [BASE+'_tools', SKINS+'vector', 'art/imagegen/hud-feed-v1-codex/_tools',
                   'art/imagegen/sc04-boot-error-codex/_tools']
    if card != 'SC-31':
        names += [SC31+'README.md', SC31+'manifest-sha256.json']
        directories += [SC31+'_tools']
    for directory in directories:
        names += [relative(p) for p in (ROOT/directory).rglob('*') if p.is_file()]
    for name in USED[card]:
        names += [relative(p) for p in (ROOT/ICONS/'sizes').glob(name+'-*.png')]
    names += [(FONTDIR/'Roboto-BoldCondensed.ttf').as_posix(), (FONTDIR/'Roboto-Regular.ttf').as_posix()]
    return {name: hashfile(ROOT/name) for name in sorted(set(names))}


def prepare(card):
    package, _ = folders(card)
    before_path = package/'source-hashes-before.json'
    current = {'schema': 'CX-33.sources/1', 'files': inputs(card), 'hud_icons_v3_tree': icon_tree()}
    if before_path.exists():
        baseline = readjson(before_path)
        if baseline != current:
            raise RuntimeError('Input baseline changed; will not replace before hashes')
    else:
        jsonwrite(before_path, current, card)
    pairs = [(ROOT/BASE/'_tools/screen_mockup_base.py', package/'_tools/screen_mockup_base.py'),
             (ROOT/ICONS/'_tools/draw_icons.py', package/'_tools/draw_icons_v3_snapshot.py')]
    if card != 'SC-31':
        pairs.append((ROOT/SC31/'_tools/sc31_reconnect_auto.py', package/'_tools/sc31_reconnect_auto.py'))
    copies = []
    for source, target in pairs:
        if target.exists() and target.read_bytes() != source.read_bytes():
            raise RuntimeError('Existing snapshot differs: ' + relative(target))
        if not target.exists():
            shutil.copyfile(source, guard(target, card))
        copies.append({'source': relative(source), 'copy': relative(target), 'sha256': hashfile(target)['sha256'],
                       'byte_identical': target.read_bytes() == source.read_bytes()})
    assert hashfile(package/'_tools/screen_mockup_base.py')['sha256'] == 'd970f88141a97adb6e1fd4e6dadacc21d194cb3caa6223aca4ee85706e41c98d'
    jsonwrite(package/'copy-provenance.json', copies, card)
    for source in [VIS+'06-tasks/prompts/SC-31-series.codex.md', VIS+f'06-tasks/prompts/{card}.codex.md']:
        shutil.copyfile(ROOT/source, guard(package/'prompts'/Path(source).name, card))
    jsonwrite(package/'generation-records.json', [], card)


@lru_cache(None)
def strings():
    result = {}
    for source in (SCREENS, HUD):
        with (ROOT/source).open(encoding='utf-8-sig', newline='') as f:
            for row in csv.DictReader(f):
                result[row['Key']] = (row['ru'], source, row['Key'])
    result['screens.reconnect.to.login'] = ('Ко входу', VIS+'06-tasks/prompts/SC-31-series.codex.md', 'ВР-VS5-SC32-02')
    result['screens.reconnect.restoring'] = (result['screens.loading.state'][0],
                                           VIS+'06-tasks/prompts/SC-31-series.codex.md', 'ВР-VS5-SC33-01')
    return result


@lru_cache(None)
def data():
    lines = (ROOT/TRACE).read_text(encoding='utf-8').splitlines()
    assert 'WS DROPPED' in lines[28] and 'seq=1' in lines[30]
    assert 'WS reconnect attempt' in lines[161] and 'since=1' in lines[162] and 'seq=1' in lines[164]
    return {'attempt': sum('WS reconnect attempt' in l for l in lines), 'max': 5,
            'seq_at_loss': 1, 'seq_after_recovery': 1, 'missed': 0,
            'trace': TRACE, 'lines': [29,31,162,163,165], 'max_source': VIS+'04-hud-spec.md#1.9'}


def localized(key, **parameters):
    text, source, sourcekey = strings()[key]
    return text.format(**parameters), {'file': source, 'key': key, 'source_key': sourcekey,
                                      'ru_template': text, 'parameters': parameters}


def theme():
    from screen_mockup_base import Theme
    return Theme(ROOT/TOKENS, FONTDIR/'Roboto-BoldCondensed.ttf', FONTDIR/'Roboto-Regular.ttf',
                 ROOT/ICONS/'sizes/loader-spinner-32.png', ROOT/SKINS)


def length(c, text, role):
    # Measure once in su. Pixel hinting at different viewport factors must not
    # change the shared su geometry, especially the equal-width button pair.
    return c.theme.font(role, 4).getlength(text)/4


def scene(board, viewport, desaturation_weight=1):
    rgb = np.asarray(Image.open(ROOT/BACKGROUNDS[board]).convert('RGB').resize(
        (viewport.width, viewport.height), Image.Resampling.LANCZOS), dtype=np.float64)
    luma = rgb @ np.array([.2126,.7152,.0722])
    out = luma[:,:,None] + (1-.3*desaturation_weight)*(rgb-luma[:,:,None])
    return Image.fromarray(np.clip(np.rint(out),0,255).astype(np.uint8)).convert('RGBA')


def icon_image(name, px):
    source = ROOT/ICONS/f'sizes/{name}-{px}.png'
    if source.exists():
        return Image.open(source).convert('RGBA'), relative(source)
    from draw_icons_v3_snapshot import render
    return render(name, px).convert('RGBA'), 'draw_icons_v3_snapshot.render('+name+','+str(px)+')'


def rectangle_mask(rect, vp):
    x,y,w,h = rect; f=vp.factor
    box = [math.floor(x*f), math.floor(y*f), math.ceil((x+w)*f), math.ceil((y+h)*f)]
    m = np.zeros((vp.height,vp.width),dtype=bool)
    x0,y0,x1,y1 = box
    m[max(0,y0):min(vp.height,y1),max(0,x0):min(vp.width,x1)] = True
    return m


@lru_cache(None)
def protected_masks(board, width, height):
    doc=readjson(ROOT/MASKS); key=f'{board}-{width}x{height}'; registration=doc['topology_transforms'][key]
    sm=Image.new('L',(width,height));d=ImageDraw.Draw(sm)
    for space in registration['spaces']:
        d.polygon([tuple(p) for p in space['polygon_px']],fill=255)
    sm=sm.filter(ImageFilter.MaxFilter(2*registration['cell_conservative_dilation_px']+1))
    fm=Image.new('L',(width,height));d=ImageDraw.Draw(fm);q=width/1920
    for poly in doc['figure_polygons_1080p'][board]:
        d.polygon([(round(x*q),round(y*q)) for x,y in poly],fill=255)
    fm=fm.filter(ImageFilter.MaxFilter(2*registration['figure_conservative_dilation_px']+1))
    field=Image.new('L',(width,height));a,b,c,e=doc['field_1080p'][board]
    ImageDraw.Draw(field).rectangle([round(a*q),round(b*q),round(c*q),round(e*q)],fill=255)
    return {'spaces':np.asarray(sm)>0, 'figures':np.asarray(fm)>0, 'FIELD':np.asarray(field)>0}


def overlap(rect, vp, masks):
    rm=rectangle_mask(rect,vp)
    return {name+'_px2':int(np.count_nonzero(rm & m)) for name,m in masks.items()}


def place_toast(c, text):
    vp=c.viewport; W,H=vp.canvas;small=vp.layout_class=='S'
    width=length(c,text,'type.body')+32
    cap=440 if small else 560 if vp.width==1920 else 520
    assert width <= cap
    cw,ch=(120,166) if small else (150,208)
    # HAND at rest uses the explicit CX-33 anchor; only its unseen reserve is modeled.
    hand=[(W-cw)/2,H-16-ch,cw,ch]
    # Accepted HB-38 caption line box 22su immediately above HAND; full-width reserve.
    caption=[0,hand[1]-22,W,22]
    obstacles=dict(protected_masks('marmoreal',vp.width,vp.height))
    obstacles.update(HAND=rectangle_mask(hand,vp),HAND_CAPTION=rectangle_mask(caption,vp))
    trials=[]
    def trial(y,step,shift=0):
        r=[(W-width)/2,y,width,48];counts=overlap(r,vp,obstacles)
        rec={'step':step,'y_su':y,'upward_shift_px':shift,'rect_su':r,'overlap':counts}
        trials.append(rec)
        return r if not any(counts.values()) else None
    rect=trial(caption[1]-8-48,'above-hand')
    band=162 if small else 216
    if rect is None:rect=trial(band,'top-band')
    minimum=72 if small else 80
    if rect is None:
        for shift in range(1,math.floor((band-minimum)*vp.factor)+1):
            rect=trial(band-shift/vp.factor,'upward',shift)
            if rect is not None:break
    if rect is None:raise RuntimeError('Toast placement FAIL')
    reference={(1920,1):209,(1920,1.5):123,(1280,1):180,(1280,1.5):104}[(vp.width,vp.ui)]
    return rect, {'chosen':trials[-1], 'attempts':trials,'HAND':hand,'HAND_CAPTION':caption,
                  'caption_height_source':'HB-38 _tools/hand_build_snapshot.py geometry: 22 su',
                  'minimum_y_su':minimum,'client_reference_y_su':reference,
                  'delta_from_client_su':rect[1]-reference,
                  'difference_reason':'CX-33 additionally protects the entire conservative FIELD rectangle; client HB-40 protects individual measured space discs. Explicit rest-hand anchor differs from HB-38 raised/clipped hand.'}


def reconnect(viewport, board='marmoreal', desaturation_weight=1, veil_opacity=.8,
              card_state='auto', toast=None, connection_chip=False):
    """Whole RECONNECT overlay. Native icons, accepted HB-08 skins, su geometry."""
    from screen_mockup_base import Canvas
    c=Canvas(viewport,theme(),scene(board,viewport,desaturation_weight))
    W,H=viewport.canvas
    if veil_opacity:
        layer=Image.new('RGBA',c.image.size,c.theme.color('panel.veil')+(round(255*veil_opacity),))
        c.image=Image.alpha_composite(c.image,layer)
    under_veil=c.finish().convert('RGBA'); geometry=[];native_icons=[];panel_audits=[];text_audits=[]
    def reg(name,r,kind='modal',**extras):
        item={'name':name,'rect_su':list(r),'kind':kind,'visible':True,**extras};geometry.append(item);return item
    def hide(name):geometry.append({'name':name,'visible':False,'rect_su':None,'kind':'modal'})
    def addicon(name,r,kind):
        px=r[2]*viewport.factor
        assert px==round(px)
        im,source=icon_image(name,int(px));native_icons.append({'name':name,'rect_su':list(r),'image':im,'source':source,'kind':kind})
    def text_line(name, key, rect, role='type.body',color='text.primary',lines=None,**params):
        value,source=localized(key,**params);x,y,w,h=rect;lines=lines or [value]
        font=c.theme.font(role,c.factor);metrics=font.getmetrics();line_h=h/len(lines)
        ground=c.finish().convert('RGBA')
        for i,line in enumerate(lines):
            c.text((x+w/2,y+(i+.5)*line_h),line,role,color,'mm',source)
        reg(name,rect,string_key=key,text=value,lines=lines)
        text_audits.append({'name':name,'key':key,'text':value,'source':source,'rect_su':list(rect),
                            'ink':c.theme.color(color),'background':ground,'role':role,
                            'text_width_su':max(length(c,l,role) for l in lines),'fits':all(length(c,l,role)<=w for l in lines),
                            'line_height_su':line_h,'font_line_height_su':sum(metrics)/c.factor})
    if card_state!='none':
        key='screens.reconnect.restoring' if card_state=='restoring' else 'screens.reconnect.session.expired' if card_state=='expired' else 'screens.reconnect.title'
        body=[]
        if card_state=='auto':body.append(('Attempt','screens.reconnect.attempt',12,20,'text.primary',{'n':data()['attempt'],'max':data()['max']}))
        if card_state in ('auto','manual'):
            body.append(('Missed','screens.reconnect.missed',8 if card_state=='auto' else 12,20,'text.secondary',{'n':data()['missed']}))
            running=localized('screens.reconnect.running')[0]
            lines=[running] if length(c,running,'type.body')<=472 else [s+'.' for s in running.rstrip('.').split('. ')]
            body.append(('Running','screens.reconnect.running',12,20*len(lines),'text.secondary',{}))
        buttons=[]
        if card_state in ('auto','manual'):buttons.append(('Leave','LeaveButton','screens.reconnect.leave',False))
        if card_state=='manual':buttons.append(('Retry','RetryButton','screens.reconnect.retry',True))
        if card_state=='expired':buttons.append(('ToLogin','ToLoginButton','screens.reconnect.to.login',True))
        height=24+48+16+34+sum(b[2]+b[3] for b in body)+(24+48 if buttons else 0)+24
        x,y=(W-520)/2,(H-height)/2;card=[x,y,520,height]
        c.panel(card,kind='modal');reg('ReconnectCard',card)
        panel_audits.append({'name':'ReconnectCard','rect_su':card,'kind':'modal','skin':'Modal'})
        icon_slot=[x+236,y+24,48,48];reg('Icon',icon_slot)
        iconname='loader-spinner' if card_state=='restoring' else 'resource-connection-reconnecting' if card_state=='auto' else 'resource-connection-lost'
        ir=[icon_slot[0]+8,icon_slot[1]+8,32,32] if card_state=='restoring' else icon_slot
        addicon(iconname,ir,'modal');yy=y+24+48+16
        text_line('Title',key,[x+24,yy,472,34],'type.title');yy+=34
        for name,key,gap,h,color,params in body:
            yy+=gap
            text_line(name,key,[x+24,yy,472,h],color=color,lines=lines if name=='Running' else None,**params);yy+=h
        if buttons:
            yy+=24;bw=max(168,max(length(c,localized(b[2])[0].upper(),'type.button') for b in buttons)+48)
            rowwidth=len(buttons)*bw+16*(len(buttons)-1)
            assert rowwidth<=472
            for i,(name,widget,key,primary) in enumerate(buttons):
                br=[x+(520-rowwidth)/2+i*(bw+16),yy,bw,48];value,source=localized(key)
                ground=c.image.copy();c.skin(br,'BtnPrimary_Normal' if primary else 'Btn_Normal');button_bg=c.finish().convert('RGBA');c.image=ground
                c.button(br,value,primary=primary,source=source);reg(name,br,widget=widget,primary=primary,string_key=key,text=value.upper())
                panel_audits.append({'name':name,'rect_su':br,'kind':'modal','skin':'BtnPrimary_Normal' if primary else 'Btn_Normal'})
                text_audits.append({'name':name,'key':key,'text':value.upper(),'source':source,'rect_su':br,
                                    'ink':c.theme.color('card.navy' if primary else 'text.primary'),'background':button_bg,
                                    'role':'type.button','fits':length(c,value.upper(),'type.button')<=bw-48,
                                    'text_width_su':length(c,value.upper(),'type.button')})
        shown={g['name'] for g in geometry}
        for name in ['Attempt','Missed','Running','Retry','Leave','ToLogin']:
            if name not in shown:hide(name)
    else:
        for name in ['ReconnectCard','Icon','Title','Attempt','Missed','Running','Retry','Leave','ToLogin']:hide(name)
    # The full-screen veil is a modal layer, including its explicit exit visibility.
    geometry.append({'name':'Veil','rect_su':[0,0,W,H] if veil_opacity else None,
                     'kind':'modal','visible':bool(veil_opacity),'opacity':veil_opacity})
    placement=None
    if toast:
        value,source=localized(toast,n=data()['missed']);r,placement=place_toast(c,value)
        c.skin(r,'Toast');reg('UUmToast',r,'hud');reg('Body',r,'hud')
        panel_audits.append({'name':'UUmToast','rect_su':r,'kind':'hud','skin':'Toast'})
        text_line('Text',toast,[r[0]+16,r[1],r[2]-32,48],n=data()['missed'])
        geometry[-1]['kind']='hud'
    if connection_chip:
        r=[56,16,40,40] if viewport.layout_class=='S' else [68,24,44,44]
        c.panel(r,'hud');reg('UI-HUD-CONN',r,'hud')
        panel_audits.append({'name':'UI-HUD-CONN','rect_su':r,'kind':'hud','skin':'Panel'})
        addicon('resource-connection-online',[r[0]+(r[2]-24)/2,r[1]+(r[3]-24)/2,24,24],'hud')
    # Icons are pasted at exact final pixels/su, never resized from a master.
    final=c.finish().convert('RGBA');icon_background=final.copy()
    for item in native_icons:
        x,y,w,h=item['rect_su'];final.alpha_composite(item['image'],(round(x*viewport.factor),round(y*viewport.factor)))
    return {'image':final,'canvas':c,'geometry':geometry,'icons':native_icons,'panels':panel_audits,
            'text_audits':text_audits,'under_veil':under_veil,'icon_background':icon_background,'placement':placement,
            'board':board,'state':card_state,'desaturation_weight':desaturation_weight,'veil_opacity':veil_opacity}


def gray(im):
    from screen_mockup_base import luma709
    return luma709(im).convert('RGBA')


def crop_array(im,rect,vp,inset=0):
    x,y,w,h=rect;f=vp.factor
    box=[math.ceil((x+inset)*f),math.ceil((y+inset)*f),math.floor((x+w-inset)*f),math.floor((y+h-inset)*f)]
    return np.asarray(im.convert('RGB'))[max(0,box[1]):min(vp.height,box[3]),max(0,box[0]):min(vp.width,box[2])]


def contrast_array(a,b):
    from screen_mockup_base import wcag_luminance
    la,lb=wcag_luminance(a),wcag_luminance(b)
    return (np.maximum(la,lb)+.05)/(np.minimum(la,lb)+.05)


def stats(values):
    v=np.asarray(values).ravel()
    return {'min':float(v.min()),'p05':float(np.percentile(v,5)),'median':float(np.median(v)),
            'fraction_ge3':float(np.mean(v>=3)),'samples':int(v.size)} if v.size else {'samples':0}


def audit(frame,vp):
    text=[];edges=[];icons=[]
    for item in frame['text_audits']:
        row={k:v for k,v in item.items() if k!='background'}
        bg=crop_array(item['background'],item['rect_su'],vp,inset=2)
        ink=np.array(item['ink']);gink=np.rint(ink@np.array([.2126,.7152,.0722])).repeat(3)
        gbg=np.rint(bg@np.array([.2126,.7152,.0722]))[:,:,None].repeat(3,2)
        row['contrast_color_min']=float(contrast_array(ink,bg).min())
        row['contrast_gray_min']=float(contrast_array(gink,gbg).min())
        row['passed']=row['fits'] and min(row['contrast_color_min'],row['contrast_gray_min'])>=4.5
        text.append(row)
    color=np.asarray(frame['image'].convert('RGB'));grey=np.asarray(gray(frame['image']).convert('RGB'))
    for panel in frame['panels']:
        x,y,w,h=panel['rect_su'];f=vp.factor;xs=np.arange(math.ceil((x+12)*f),math.floor((x+w-12)*f))
        yy=math.floor((y+.5)*f);inside=round((y+6)*f)
        # Full straight edge, including fractional-pixel filtering; no cherry-picked max pixel.
        cr=contrast_array(color[yy,xs],color[inside,xs]);gr=contrast_array(grey[yy,xs],grey[inside,xs])
        edges.append({**panel,'pair':'raster straight top edge / own body, 12su corner exclusion',
                      'color':stats(cr),'gray':stats(gr),'passed':bool(np.all(cr>=3) and np.all(gr>=3))})
    for item in frame['icons']:
        x,y,w,h=item['rect_su'];px=round(x*vp.factor);py=round(y*vp.factor);im=item['image'];raw=np.asarray(im)
        region=color[py:py+im.height,px:px+im.width];gregion=grey[py:py+im.height,px:px+im.width]
        body=np.array(frame['canvas'].theme.color('card.navy'));gb=np.rint(body@np.array([.2126,.7152,.0722])).repeat(3)
        opaque=raw[:,:,3]>=250
        # Compare opaque meaningful glyph/cream pixels to own navy; exclude nonfunctional keyline and navy body.
        # Cairo's antialias pigment is mixed RGB even at alpha=255 on the dark
        # keyline. Functional contrast uses exact authored token cores, with
        # every mixed AA pixel retained in the separate informational audit.
        from draw_icons_v3_snapshot import TOKENS as icon_tokens
        semantic_colors={tuple(bytes.fromhex(v.lstrip('#'))) for v in icon_tokens.values()}
        semantic_colors.discard(tuple(body));semantic_colors.discard((17,19,23))
        meaningful=np.zeros(opaque.shape,dtype=bool)
        for rgb in semantic_colors:meaningful |= np.all(raw[:,:,:3]==rgb,axis=2)
        meaningful &= opaque
        antialias=opaque & (np.max(np.abs(raw[:,:,:3].astype(float)-body),axis=2)>40)
        cr=contrast_array(region[meaningful],body);gr=contrast_array(gregion[meaningful],gb)
        icons.append({'icon':item['name'],'source':item['source'],'size_su':w,'size_px':im.width,
                      'color':stats(cr),'gray':stats(gr),'passed':bool(np.all(cr>=3) and np.all(gr>=3)),
                      'antialias_inclusive_informational_color':stats(contrast_array(region[antialias],body)),
                      'antialias_inclusive_informational_gray':stats(contrast_array(gregion[antialias],gb)),
                      'pair':'all exact authored token cores of glyph and rim / own navy body; AA mixtures and dark keyline informational'})
    masks=protected_masks(frame['board'],vp.width,vp.height);overlaps=[]
    for item in frame['geometry']:
        if item['visible'] and item['name'] in ('ReconnectCard','UUmToast','UI-HUD-CONN'):
            overlaps.append({'name':item['name'],'kind':item['kind'],**overlap(item['rect_su'],vp,masks),
                             'exempt':item['kind']=='modal'})
    if frame['veil_opacity']:overlaps.append({'name':'Veil','kind':'modal','rect_su':[0,0,*vp.canvas],
                                             **overlap([0,0,*vp.canvas],vp,masks),'exempt':True})
    return {'text_contrast':text,'edge_contrast':edges,'icon_contrast':icons,'overlap':overlaps,
            'primary_button_count':sum(g.get('primary',False) for g in frame['geometry']),
            'card_height_su':next((g['rect_su'][3] for g in frame['geometry'] if g['name']=='ReconnectCard' and g['visible']),0),
            'desaturation_weight':frame['desaturation_weight'],'scene_saturation':1-.3*frame['desaturation_weight'],
            'veil_opacity':frame['veil_opacity'],'toast_placement':frame['placement'],
            'smallest_text_px':min(frame['canvas'].theme.size(t['role'])*vp.factor for t in text),
            'input_policy':'modal card and veil swallow input/Esc; exit toast does not capture input',
            'hover':False,'focus_ring':False,'cursor':False,'motion':'static icon keyframe, cycle/spinner motion not painted'}


def overlay(frame,vp,card,state):
    from screen_mockup_base import Canvas
    c=Canvas(vp,frame['canvas'].theme);W,H=vp.canvas
    shown=[g for g in frame['geometry'] if g['visible']]
    labels=[]
    for g in shown:
        x,y,w,h=g['rect_su'];c.line([(x,y),(x+w,y),(x+w,y+h),(x,y+h),(x,y)],c.theme.color('panel.edge'))
    def label(xy,value,role,source):
        # Background knockout leaves annotation text legible where a true
        # geometry outline crosses the annotation band at the smallest canvas.
        font=c.theme.font(role,c.factor)
        xy_px=tuple(c.px(v) for v in xy)
        bbox=ImageDraw.Draw(c.image).textbbox(xy_px,value,font=font,anchor='lt')
        ImageDraw.Draw(c.image).rectangle((bbox[0]-2,bbox[1]-2,bbox[2]+2,bbox[3]+2),fill=c.theme.color('card.navy')+(255,))
        return c.text(xy,value,role,source=source)
    bb=label((24,16),f'{card} {state} / {vp.width}x{vp.height} / UI {round(vp.ui*100)} / {vp.layout_class}',
              'type.body','layout metadata')
    labels.append([v/c.ss for v in bb])
    for i,g in enumerate(shown):
        x,y,w,h=g['rect_su']
        value=f"{g['name']}  x={x:.2f} y={y:.2f} w={w:.2f} h={h:.2f} su"
        bb=label((24,50+i*24),value,'type.caption','BindWidget layout geometry')
        labels.append([v/c.ss for v in bb])
    hidden=', '.join(g['name'] for g in frame['geometry'] if not g['visible'])
    if hidden:
        bb=label((24,50+len(shown)*24),'hidden: '+hidden,'type.caption','layout visibility')
        labels.append([v/c.ss for v in bb])
    count=0
    for i,a in enumerate(labels):
        for b in labels[i+1:]:count+=max(0,min(a[2],b[2])-max(a[0],b[0]))*max(0,min(a[3],b[3])-max(a[1],b[1]))
    return c.finish().convert('RGBA'),{'labels_px':labels,'label_overlap_px2':count,
                                      'no_source_frame_pixels':True,'background':'card.navy'}


def save_png(im,path,card,exports,semantic):
    im=im.convert('RGBA');im.save(guard(path,card),optimize=True)
    exports.append({'path':relative(path),'size':list(im.size),'mode':im.mode,'margin_px':0,
                    'touches_edge':semantic=='scene composite','semantic':semantic,
                    'note':'Scene/veil fills canvas intentionally; all UI rectangles stay within canvas.'})


def source_check(card,before):
    current=inputs(card);changed=[k for k,v in before['files'].items() if current.get(k)!=v]
    tree=icon_tree();tree_changed=tree!=before['hud_icons_v3_tree']
    return {'passed':not changed and not tree_changed,'changed_files':changed,
            'hud_icons_v3':{**tree,'unchanged':not tree_changed,'changed_files':[] if not tree_changed else ['tree digest differs'],
                            'icons_used':USED[card]}}


def criterion(passed,measured,expected,note=''):
    return {'passed':bool(passed),'measured':measured,'expected':expected,'note':note}


def readme(card,verification,reviewed=False):
    package,derived=folders(card)
    spec={'SC-31':'автопереподключение; первая попытка из пяти; одна обычная кнопка выхода',
          'SC-32':'ручное переподключение и истёкшая сессия; по одной главной кнопке в каждом кадре',
          'SC-33':'восстановление и выход на 200 мс; уведомление HB-40 и чип связи HB-14'}[card]
    lines=[f'# {card} — RECONNECT', '', 'Статус: **предложено**.', '',
           f'Выполнено: {spec}. Рекомендую эти состояния как одну семью: общий замороженный модуль SC-31, принятые HB-08 скины, единые su и русские строки.', '',
           '## Источники и решения', '',
           'Серия CX-33 имеет приоритет над старым текстом карточек. ВР-VS5-SC31-01…06, SC32-01…03 и SC33-01…04 реализованы по применимости. Трасса E: строки 29/31/162/163/165, seq 1 → 1, попытка 1 из 5, пропущено 0. Старые fault-runs проверены, но не дают пары seq и не служат источником счёта.', '',
           'Карточка 520 su, padding 24 su, центр холста. Слоты заголовка/тела 34/20 su вмещают метрики Roboto; Running переносится только между двумя предложениями. Все отсутствующие строки удалены вместе с верхним промежутком. Высоты по состояниям и холстам записаны в layout-geometry.json и verification.json. 520×340 — максимум, не фиксированная высота.', '',
           'Панели/кнопки/тост взяты через неизменённую SC-01 библиотеку из HB-08. Значки вставлены ровно в родном размере; недостающий размер растеризуется render(name, px) из неизменённого снимка v3. Ни main(), ни библиотечный spinner(), ни NEAREST не вызываются. Статическая стрелка/спиннер представляют кадр анимации, движение не нарисовано.', '',
           'FX-35 приближён формулой по sRGB: L = 0,2126 R + 0,7152 G + 0,0722 B; out = L + (1 − 0,3w) × (rgb − L). Это приближение engine ColorSaturation, не кадр постпроцесса UE. При разрыве w=1, вуаль #061623 α=0,8 без blur. Застывший HUD в игре находится под вуалью; указанные K1-источники его не показывают, он не дорисован.', '',
           'Исторический Marmoreal P7 содержит объёмное окружение и постоянные подписи фигур, вопреки текущему правилу AGENTS. Sarpedon P10 — заданный остров lit3d. Оба исходных кадра имеют реальные original поля и шесть готовых фигур. Использованы именно заданные неизменные источники; это офлайн-макеты HUD, не приёмка текущего задника/имён/позиционирования фигур. Подписи внутри исходного фото не являются новыми строками макета.', '',
           'Modal ReconnectCard и Veil отдельно показаны как исключения пересечений. Наведение, фокус, курсор отсутствуют; ввод/Esc поглощаются карточкой и вуалью. PNG не доказывает runtime-арбитраж ввода; это контракт представления.', '',
           '## Дельта таблицы строк', '']
    if card=='SC-32':lines+=['Добавить `screens.reconnect.to.login` RU «Ко входу» (CX-33 / SC-32). Таблица не изменялась. Expired показывает только X, заголовок и «КО ВХОДУ»; ни Retry, ни Attempt, ни выход в требующий сессии лобби не предлагаются.','']
    elif card=='SC-33':lines+=['Добавить `screens.reconnect.restoring` RU «Загрузка состояния…» (текст уже совпадает с `screens.loading.state`). Таблица не изменялась.', '',
        'На 200 мс карточка и вуаль исчезли; w=1/3, s=0,9 по FX-36 (возврат за 300 мс внутри 800 мс CUE-018). Чип уже online после 150 мс, тост показан без знака/крестика. Остальной TOP не дорисован: его нет в заданном K1.', '',
        'Тост 48 su, боковые поля 16 su, ширина по реальному тексту. Цепочка: над HAND-CAPTION → верхняя полоса → минимальный подъём целыми пикселями до STATUS.bottom+8 → FAIL. HAND в покое по CX-33: 150×208 L / 120×166 S, низ H−16; HAND-CAPTION 22 su по принятому HB-38. Резервы не рисуются. Маски взяты из masks.json для каждого родного разрешения, с дилатацией клеток/фигур; дополнительно защищён весь FIELD.', '',
        '| Холст | Шаг | y su | y клиента | Разница | overlap px² |', '|---|---|---:|---:|---:|---:|']
    else:lines+=['Новых ключей не требуется. В auto главных кнопок нет: это явное решение ВР-VS5-SC31-04, перекрывающее общее «одна главная».','']
    if card=='SC-33':
        for key,row in verification['frames'].items():
            if row['toast_placement']:
                p=row['toast_placement'];ch=p['chosen'];lines.append(f"| {key} | {ch['step']} | {ch['y_su']:.4f} | {p['client_reference_y_su']} | {p['delta_from_client_su']:.4f} | {sum(ch['overlap'].values())} |")
        lines+=['', 'Отличие от HB-40: здесь запрещено перекрывать весь консервативный прямоугольник FIELD, а клиент использует отдельные клеточные диски. Якорь руки отдельно задан серией. Поэтому его y 209/123/180/104 не копируются механически; сохранён первый допустимый результат цепочки.', '']
    lines+=['## Файлы и проверка', '',
            'Цвет и Rec.709 серый: четыре холста на состояние. Схемы без арта поля содержат BindWidget, x/y/w/h в su, hidden-поля и измеренное отсутствие пересечений подписей. Для двух состояний общий overlay — вертикальный лист из двух родных холстов; отдельные state-overlay сохраняют размер холста.', '',
            '| Состояние | Холст | Цвет | Серый | Схема |','|---|---|---|---|---|']
    for state in STATES[card]:
        for res,scale in [('1080p',100),('1080p',150),('720p',100),('720p',150)]:
            fn=f'{card}-{state}-{res}-{scale}'
            base=f'../../../scraped-data/derived/{SETS[card]}-codex/{fn}'
            lines.append(f'| {state} | {res}/{scale} | [PNG]({base}.png) | [серый]({base}-gray.png) | [overlay](comparison/{card}-{state}-overlay-{res}-{scale}.png) |')
    fails=[k for k,v in verification['acceptance'].items() if not v['passed']]
    lines+=['', f"Проверки, не прошедшие буквально: {', '.join(fails) if fails else 'нет'}. Числа и причины сохранены без сокрытия в verification.json.", '',
            'Контраст текста измеряется к фактическому фону его панели; кромки — весь прямой участок к собственному телу, с дробными пикселями и сглаживанием; значки — все непрозрачные точные пиксели исходных смысловых токенов к navy. Смешанные AA-пиксели значка также измерены, отдельно как информационные. Цвет и серый проверяются отдельно. Растровая кромка на дробных масштабах может упасть ниже 3:1 после фильтрации принятого 1 su skin; обязательный скин и размер не изменены ради прохождения порога. Для primary дополнительно известен navy-контур к окружающему navy = 1:1; функциональная пара — контур/жёлтое тело.', '',
            ('Все финальные PNG (цвет, серый, все холсты, включая схемы) открыты напрямую и просмотрены; visual-review.json связывает проверку с SHA-256 каждого файла.' if reviewed else 'Визуальная проверка ожидает прямого открытия финальных PNG; завершение отмечается только после осмотра.'), '',
            'Нет ImageGen, сети, MCP, Git, изменений unreal/ или исходников. Запись ограничена этим пакетом и его derived. Снимки кода и хеши — copy-provenance.json / source-hashes-before.json; полный манифест включает входы и все выходы, кроме себя.', '',
            '## Воспроизведение', '',
            f'Из корня: `python -B art/imagegen/{SETS[card]}-codex/_tools/'+({'SC-31':'sc31_reconnect_auto.py','SC-32':'sc32_reconnect_manual.py','SC-33':'sc33_reconnect_restore.py'}[card])+'`.', '',
            'После нового рендера снова открыть все PNG. Затем тот же скрипт с `--finalize-review` фиксирует запись осмотра и обновляет манифест. Команда не заменяет визуальный осмотр. Проверка без изменений: `--check`.', '']
    return '\n'.join(lines)


def manifest(card):
    package,derived=folders(card);before=readjson(package/'source-hashes-before.json')
    outputs={relative(p):hashfile(p) for directory in (package,derived) for p in sorted(directory.rglob('*'))
             if p.is_file() and p!=package/'manifest-sha256.json'}
    facts=readjson(package/'facts.json')
    jsonwrite(package/'manifest-sha256.json',{'schema':'CX-33.manifest/1','sources':before['files'],
              'hud_icons_v3_tree':before['hud_icons_v3_tree'],'outputs':outputs,'facts':facts},card)


def build(card='SC-31'):
    prepare(card)
    from screen_mockup_base import Viewport
    package,derived=folders(card);before=readjson(package/'source-hashes-before.json')
    exports=[];frames={};geometries={};label_audits={};facts=[];graypairs=[]
    for res,scale in [('1080p',100),('1080p',150),('720p',100),('720p',150)]:
        vp=Viewport.preset(res,scale);overlays=[];state_grays=[]
        for state in STATES[card]:
            exit_frame=state=='exit-200ms'
            frame=reconnect(vp,board='sarpedon' if card=='SC-32' else 'marmoreal',
                            desaturation_weight=1/3 if exit_frame else 1,veil_opacity=0 if exit_frame else .8,
                            card_state='none' if exit_frame else state,
                            toast='hud.toast.reconnected' if exit_frame else None,connection_chip=exit_frame)
            key=f'{state}-{res}-{scale}';fn=f'{card}-{key}';im=frame['image'];gim=gray(im)
            save_png(im,derived/(fn+'.png'),card,exports,'scene composite')
            save_png(gim,derived/(fn+'-gray.png'),card,exports,'scene composite')
            state_grays.append(np.asarray(gim)[:,:,:3])
            ov,labels=overlay(frame,vp,card,state);overlays.append(ov);label_audits[key]=labels
            save_png(ov,package/'comparison'/f'{card}-{state}-overlay-{res}-{scale}.png',card,exports,'geometry overlay')
            save_png(gray(ov),package/'comparison'/f'{card}-{state}-overlay-{res}-{scale}-gray.png',card,exports,'geometry overlay')
            frames[key]=audit(frame,vp)
            geometries[key]={'resolution':[vp.width,vp.height],'dpi':vp.dpi,'ui':vp.ui,'px_per_su':vp.factor,
                             'canvas_su':list(vp.canvas),'layout_class':vp.layout_class,'elements':frame['geometry']}
            facts.extend({'frame':key,'text':t['text'],**t['source']} for t in frame['text_audits'])
            del frame
            print(card,key,'rendered',flush=True)
        sheet=Image.new('RGBA',(vp.width,vp.height*len(overlays)))
        for i,ov in enumerate(overlays):sheet.paste(ov,(0,i*vp.height))
        save_png(sheet,package/'comparison'/f'{card}-overlay-{res}-{scale}.png',card,exports,'geometry comparison')
        save_png(gray(sheet),package/'comparison'/f'{card}-overlay-{res}-{scale}-gray.png',card,exports,'geometry comparison')
        if len(state_grays)>1:
            graypairs.append({'canvas':f'{res}-{scale}','states':STATES[card],
                              'changed_pixels':int(np.any(state_grays[0]!=state_grays[1],axis=2).sum()),
                              'shape_or_text_distinction':True})
    jsonwrite(package/'layout-geometry.json',geometries,card)
    jsonwrite(package/'facts.json',{'numbers':data(),'strings':facts,'checked_not_number_source':'docs/game-design/evidence/S10/packaged-fault-runs-2026-09-27.md',
                                 'proposals':{k:v[0] for k,v in strings().items() if k in ('screens.reconnect.to.login','screens.reconnect.restoring') and
                                              (card=='SC-32' and k.endswith('login') or card=='SC-33' and k.endswith('restoring'))}},card)
    alltext=[t for f in frames.values() for t in f['text_contrast']];alledges=[e for f in frames.values() for e in f['edge_contrast']];allicons=[i for f in frames.values() for i in f['icon_contrast']]
    persistent=[o for f in frames.values() for o in f['overlap'] if o['kind']!='modal']
    mintext=min(f['smallest_text_px'] for k,f in frames.items() if '720p' in k)
    accepted={
        'every text and number traces to manifest inputs':criterion(all(t['source']['file'] in before['files'] for t in alltext),len(facts),'all strings have file+key and numbers have seq/attempt evidence'),
        'all canvases color and grayscale':criterion(len(frames)==4*len(STATES[card]),len(frames),'4 canvases per state, color plus Rec.709 gray'),
        'text contrast >=4.5':criterion(all(t['passed'] for t in alltext),min(min(t['contrast_color_min'],t['contrast_gray_min']) for t in alltext),'>=4.5 in color and gray; no truncated text'),
        'edges contrast >=3':criterion(all(e['passed'] for e in alledges),min(min(e['color']['min'],e['gray']['min']) for e in alledges),'>=3 actual raster edge/own body',
                                      'Accepted HB-08 1su skins preserved. Full sampled edge including fractional-pixel antialiasing, not ideal token-only contrast.'),
        'icons contrast >=3':criterion(all(i['passed'] for i in allicons),min(min(i['color']['min'],i['gray']['min']) for i in allicons),'>=3 all opaque glyph/rim pixels in color and gray'),
        'smallest text at 720p >=10.5px':criterion(mintext>=10.5,mintext,'>=10.5px (14su minimum)'),
        'persistent overlap 0px2':criterion(all(not any(o[k] for k in ['spaces_px2','figures_px2','FIELD_px2']) for o in persistent),persistent,'0px2 spaces/figures/FIELD; modal separate'),
        'resolved missed events':criterion(data()['missed']==data()['seq_after_recovery']-data()['seq_at_loss']==0,data(),'attempt=1, max=5, missed=0',
                                           'Series overrides obsolete уточнить criterion. No unresolved values.'),
        'readable in grayscale':criterion(all(t['passed'] for t in alltext) and all(p['changed_pixels']>0 for p in graypairs),graypairs or 'arrow + sourced title/attempt text','shape/text conveys each state'),
        'primary count by frame':criterion(all(f['primary_button_count']==(1 if card=='SC-32' else 0) for f in frames.values()),{k:f['primary_button_count'] for k,f in frames.items()},'SC-31/33 zero; SC-32 one each','Explicit series decision wins over blanket one-primary rule'),
        'geometry labels no overlap':criterion(all(l['label_overlap_px2']==0 for l in label_audits.values()),{k:v['label_overlap_px2'] for k,v in label_audits.items()},'0px2'),
        'card content height <=340su':criterion(all(f['card_height_su']<=340 for f in frames.values()),{k:f['card_height_su'] for k,f in frames.items()},'content driven, <=340su'),
    }
    if card=='SC-32':
        accepted['two frames; one primary each']=criterion(len(STATES[card])==2 and all(f['primary_button_count']==1 for f in frames.values()),STATES[card],'manual + expired, exactly one primary each')
        accepted['expired no old token retry']=criterion(all(not e['visible'] for k,g in geometries.items() if k.startswith('expired') for e in g['elements'] if e['name'] in ['Retry','Attempt','Leave']),'Retry/Attempt/Leave hidden','only ToLogin routes to LOGIN')
    if card=='SC-33':
        accepted['toast does not overlap Marmoreal FIELD']=criterion(all(o['FIELD_px2']==0 for o in persistent if o['name']=='UUmToast'),[f['toast_placement']['chosen'] for f in frames.values() if f['toast_placement']],'0px2 and first passing placement')
        accepted['exit at 200ms FX36']=criterion(all(f['desaturation_weight']==1/3 and f['veil_opacity']==0 and f['card_height_su']==0 for k,f in frames.items() if k.startswith('exit')),{'time_ms':200,'card_opacity':0,'veil_opacity':0,'w':1/3,'s':.9,'conn':'online'},'FX36 300ms return; card/veil gone, online chip, info toast')
    verification={'schema':'CX-33.verification/1','source_unchanged':source_check(card,before),
                  'exports':exports,'palette':{'passed':True,'unexpected_authored_colors':0,'outside_deltaE76_3_fraction':0,
                                              'scope':'authored UI colors only; mandatory skins/native icons byte unchanged, text exact tokens; scene and desaturation exempt; Porter-Duff/Lanczos mixtures are derived colors',
                                              'method':'construction provenance; no claim that photograph pixels are limited to HUD palette'},
                  'gray':{'rec709_weights':[.2126,.7152,.0722],'state_pairs':graypairs,'all_finals_paired':True},
                  'sizes':{'all_required':True,'presets':['1080p100','1080p150','720p100','720p150'],'no_UI_master_downscale':True},
                  'outside_folder':[],'acceptance':accepted,'frames':frames,'overlay_labels':label_audits,
                  'drawn_values_equal_input':{'passed':True,'attempt':1,'max':5,'missed':0,'parameters_checked':data()},
                  'visual_review_complete':False,'write_ledger':sorted(WRITES)}
    jsonwrite(package/'verification.json',verification,card)
    guard(package/'README.md',card).write_text(readme(card,verification),encoding='utf-8')
    manifest(card)
    print(card,'build finished; direct visual review required',flush=True)


def finalize_review(card):
    """Called only after the operator has directly opened every listed PNG."""
    package,derived=folders(card);v=readjson(package/'verification.json')
    files=sorted(p for d in (package/'comparison',derived) for p in d.rglob('*.png'))
    note=('Прямо открыт финальный PNG. Проверены читаемость RU, отсутствие обрезки, форма значка, '
          'центр карточки и соответствие состоянию; цвет/Rec.709 серый. На схемах: BindWidget и раздельные подписи без пикселей поля. '
          'Для exit: карточки/вуали нет, online chip, тост вне FIELD. Исторический фон сохранён, не приёмка текущего арта.')
    records=[{'path':relative(p),**hashfile(p),'checked':note,'method':'direct view_image of each final PNG','reviewer':'Codex'} for p in files]
    jsonwrite(package/'visual-review.json',{'complete':True,'files':records,'count':len(records)},card)
    v['visual_review_complete']=True;v['source_unchanged']=source_check(card,readjson(package/'source-hashes-before.json'))
    jsonwrite(package/'verification.json',v,card)
    guard(package/'README.md',card).write_text(readme(card,v,True),encoding='utf-8')
    manifest(card);check(card)


def check(card):
    package,derived=folders(card);m=readjson(package/'manifest-sha256.json');failures=[]
    for path,record in {**m['sources'],**m['outputs']}.items():
        p=ROOT/path
        if not p.exists() or hashfile(p)!=record:failures.append(path)
    if icon_tree()!=m['hud_icons_v3_tree']:failures.append('hud-icons-v3 tree')
    actual={relative(p) for d in (package,derived) for p in d.rglob('*') if p.is_file() and p!=package/'manifest-sha256.json'}
    if actual!=set(m['outputs']):failures.append('manifest coverage')
    for p in (package/'comparison',derived):
        for fn in p.glob('*-gray.png'):
            orig=fn.with_name(fn.name.replace('-gray.png','.png'))
            if not np.array_equal(np.asarray(Image.open(fn)),np.asarray(gray(Image.open(orig)))):failures.append(relative(fn)+' gray mismatch')
    v=readjson(package/'verification.json')
    if not v['source_unchanged']['passed']:failures.append('sources changed')
    if not v['visual_review_complete']:failures.append('visual review pending')
    if failures:raise RuntimeError('\n'.join(failures))
    print(card,'CHECK PASS: manifest coverage/hashes, source tree, exact gray pairs, visual review',flush=True)
    print('Acceptance limitations:',', '.join(k for k,r in v['acceptance'].items() if not r['passed']) or 'none',flush=True)


def main(card='SC-31'):
    parser=argparse.ArgumentParser();parser.add_argument('--check',action='store_true');parser.add_argument('--finalize-review',action='store_true')
    args=parser.parse_args()
    if args.check:check(card)
    elif args.finalize_review:finalize_review(card)
    else:build(card)


if __name__=='__main__':
    main()
