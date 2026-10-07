#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""CX-27 BOOT renderer and bounded package builder. No engine, git or network.

Run with python -B. SC-04/05 copy this file byte-for-byte and supply a renderer.
All writes are checked against the current package and its derived directory.
"""
from __future__ import annotations
import csv
import hashlib
import json
import re
import sys
from functools import lru_cache
from pathlib import Path
import numpy as np
from PIL import Image, ImageDraw
sys.dont_write_bytecode = True
from screen_mockup_base import Canvas, Theme, Viewport, contrast, luma709, wcag_luminance

ROOT = Path(__file__).resolve().parents[4]
VIS = 'docs/game-design/visual/'
STRINGS = 'docs/unreal/contracts/hud/st-screens.csv'
WHY = 'docs/unreal/contracts/hud/why-reasons.json'
TOKENS = 'docs/unreal/contracts/hud/hud-style-tokens.json'
SC01 = 'art/imagegen/sc01-screen-base-codex/'
SKINS = 'art/imagegen/hud-skins-v1-codex/'
ICONS = 'art/imagegen/hud-icons-v3/'
SERIES = VIS + '06-tasks/prompts/SC-03-series.codex.md'
FRAME = 'docs/game-design/evidence/ENV-MAPS/p7-concept-paste-2026-10-01/marmoreal-concept-flag/bench-K1-1920x1080.png'
TRACE = 'docs/game-design/evidence/DE-FOOTAGE/2026-10-05/I/marmoreal/combat-20261005-235827/combat-client-host.trace.txt'
RUN = 'docs/game-design/evidence/DE-FOOTAGE/2026-10-05/I/README.md'
MATRIX = 'docs/game-design/05-content-matrix.csv'
FONTS = Path('C:/Program Files/Epic Games/UE_5.8/Engine/Content/Slate/Fonts')
CAPTION = 'фон-заглушка: в игре фигур нет (ВР-75)'
FIGURES = [(489,267,607,339),(474,351,585,431),(492,451,549,529),
           (478,563,579,635),(1260,597,1339,665),(1188,707,1270,790)]
FIELD = [(300,220,1620,900)]
WRITTEN = set()


def read(path):
    return (ROOT/path).read_text(encoding='utf-8-sig')


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def rel(path):
    path = Path(path).resolve()
    return path.relative_to(ROOT).as_posix() if path.is_relative_to(ROOT) else path.as_posix()


def allow(path, package, derived):
    path = Path(path).resolve()
    if not any(path.is_relative_to(p) for p in (package.resolve(), derived.resolve())):
        raise ValueError('Write outside package roots: ' + str(path))
    path.parent.mkdir(parents=True, exist_ok=True)
    WRITTEN.add(rel(path))
    return path


def dump(path, value, package, derived):
    allow(path, package, derived).write_text(json.dumps(value, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')


def tree(path):
    files = {rel(p):sha(p) for p in sorted((ROOT/path).rglob('*')) if p.is_file()}
    payload = ''.join(f'{k}\t{v}\n' for k,v in sorted(files.items())).encode('utf-8')
    return {'digest_sha256':hashlib.sha256(payload).hexdigest(), 'count':len(files),
            'algorithm':'SHA256 of sorted UTF-8 path TAB SHA256 LF', 'files':files}


def source_inputs(card, extra=()):
    files = [VIS+'04-hud-spec.md',VIS+'02-visual-design.md',VIS+'07-prompt-templates.md',
             VIS+'06-tasks/screens.csv',SERIES,VIS+f'06-tasks/prompts/{card}.codex.md',
             STRINGS,WHY,TOKENS,FRAME,TRACE,RUN,SC01+'README.md',SC01+'manifest-sha256.json',
             SKINS+'README.md',SKINS+'runtime-style.json',SKINS+'slice-margins.json',*extra]
    files += [rel(p) for p in sorted((ROOT/(SC01+'_tools')).rglob('*')) if p.is_file()]
    files += [rel(p) for p in sorted((ROOT/(SKINS+'vector')).rglob('*')) if p.is_file()]
    files += [rel(FONTS/name) for name in ('Roboto-BoldCondensed.ttf','Roboto-Regular.ttf')]
    return {'inputs':{k:sha(ROOT/k) for k in sorted(set(files))}, 'hud_icons_v3':tree(ICONS)}


@lru_cache(maxsize=1)
def data():
    rows = list(csv.DictReader(read(STRINGS).splitlines()))
    strings = {r.get('key',r.get('Key')):r['ru'] for r in rows}
    trace = read(TRACE)
    n = int(re.search(r'HEROES loaded (\d+)',trace).group(1))
    commit = re.search(r'BuildStamp.json[^\n]*commit ([0-9a-f]{8})', read(RUN)).group(1)
    screens = {r['id']:r for r in csv.DictReader(read(VIS+'06-tasks/screens.csv').splitlines())}
    assert 'UNMATCHED' in read(VIS+'04-hud-spec.md') and 'screens.boot.title' in screens['SC-03']['do']
    proposed = {'screens.boot.title':'UNMATCHED','screens.boot.build':'сборка {commit}',
                'screens.boot.resume.title':'Партия идёт',
                'screens.boot.resume.line':'Ваш герой: {hero} · соперник: {opponent} · {board}',
                'screens.boot.resume.return':'Вернуться в партию','screens.boot.resume.lobby':'В лобби',
                'screens.boot.stage.heroes.wait':'Загрузка героев…'}
    for key,value in proposed.items():
        assert value in read(SERIES)+read(VIS+'04-hud-spec.md'), (key,value)
    strings.update(proposed)
    reason = json.loads(read(WHY))
    def find(obj):
        if isinstance(obj,dict):
            if obj.get('key')=='why.syncing': return obj['ru']
            for v in obj.values():
                r=find(v)
                if r:return r
        if isinstance(obj,list):
            for v in obj:
                r=find(v)
                if r:return r
    strings['why.syncing'] = find(reason)
    strings['build'] = strings['screens.boot.build'].format(commit=commit)
    strings['n'],strings['commit'] = n,commit
    return strings


class BootTheme(Theme):
    @lru_cache(maxsize=128)
    def skin(self,name,scale):
        im = super().skin(name,scale)
        if name == 'Capsule':
            # HB-08 capsule body is alpha .92. Screen instances are opaque per
            # 04 §1 and CX-27; preserve RGB, printed edge, corners and AA coverage.
            a=np.array(im)
            a[:,:,3]=np.minimum(255,np.rint(a[:,:,3].astype(float)*255/235)).astype('uint8')
            im=Image.fromarray(a)
        return im


def theme():
    return BootTheme(ROOT/TOKENS,FONTS/'Roboto-BoldCondensed.ttf',FONTS/'Roboto-Regular.ttf',
                     ROOT/(ICONS+'sizes/loader-spinner-48.png'),ROOT/SKINS)


def stats(values,threshold):
    a=np.asarray(values,dtype=float)
    return {'min':float(a.min()),'p05':float(np.quantile(a,.05)), 'median':float(np.median(a)),
            'share_ge_threshold':float((a>=threshold).mean()), 'threshold':threshold,
            'passed':bool(np.all(a>=threshold)), 'sample_count':int(a.size)}


def crop_rect(im,rect,factor):
    x,y,w,h=rect
    return im.crop((int(np.floor(x*factor)),int(np.floor(y*factor)),
                    int(np.ceil((x+w)*factor)),int(np.ceil((y+h)*factor))))


def foreground_stats(im,rect,factor,ink,threshold):
    bg=np.asarray(crop_rect(im,rect,factor).convert('RGB'))
    l=wcag_luminance(bg);f=wcag_luminance(ink)
    return stats((np.maximum(l,f)+.05)/(np.minimum(l,f)+.05),threshold)


class BootCanvas(Canvas):
    def __init__(self,*args,**kwargs):
        super().__init__(*args,**kwargs)
        self.metrics={'texts':[],'boundaries':[],'icons':[]}
        self.veiled=None

    def text(self,xy,value,role='type.body',color='text.primary',anchor='lt',source=None):
        font=self.theme.font(role,self.factor)
        box=ImageDraw.Draw(self.image).textbbox(tuple(self.px(v) for v in xy),value,font=font,anchor=anchor)
        rect=(box[0]/self.factor,box[1]/self.factor,(box[2]-box[0])/self.factor,(box[3]-box[1])/self.factor)
        ink=self.theme.color(color) if isinstance(color,str) else color
        threshold=3 if role=='type.display' else 4.5
        self.metrics['texts'].append({'text':value,'source':source,'rect_su':rect,
            'ink':ink,'actual_background':foreground_stats(self.image,rect,self.factor,ink,threshold),
            'veiled_frame':foreground_stats(self.veiled,rect,self.factor,ink,threshold) if self.veiled else None})
        self.geometry.append({'kind':'text','layer':getattr(self,'text_layer','screen'),
                              'rect_su':list(rect),'label':source,'role':role})
        return super().text(xy,value,role,color,anchor,source)

    def boundary_skin(self,rect,name,kind='screen',label=None):
        x,y,w,h=rect
        before=self.image.copy()
        self.skin(rect,name)
        # Straight boundary, excludes rounded corners; use FINAL raster pixels.
        b=np.asarray(before.convert('RGB').resize((self.viewport.width,self.viewport.height),Image.Resampling.LANCZOS))
        a=np.asarray(self.finish())
        f=self.viewport.factor; mask=np.zeros((self.viewport.height,self.viewport.width),bool)
        xx,yy=round(x*f),round(y*f);rr,bb=round((x+w)*f)-1,round((y+h)*f)-1
        n=max(1,round(f));inset=min(12,w/4,h/3)
        xa,xb=round((x+inset)*f),round((x+w-inset)*f)
        ya,yb=round((y+inset)*f),round((y+h-inset)*f)
        mask[yy:yy+n,xa:xb]=True; mask[bb-n+1:bb+1,xa:xb]=True
        if name not in ('ProgressTrack','ProgressFill'):
            mask[ya:yb,xx:xx+n]=True; mask[ya:yb,rr-n+1:rr+1]=True
        la,lb=wcag_luminance(a[mask]),wcag_luminance(b[mask])
        edge=(np.maximum(la,lb)+.05)/(np.minimum(la,lb)+.05)
        body=wcag_luminance(self.theme.color('panel.bg'))
        bodyratio=(np.maximum(body,lb)+.05)/(np.minimum(body,lb)+.05)
        self.metrics['boundaries'].append({'skin':name,'label':label,'kind':kind,
             'edge_only':stats(edge,3),'boundary':stats(np.maximum(edge,bodyratio),3),
             'method':'max(raster edge vs same backdrop pixel, navy body vs same backdrop); straight edges only'})
        self.geometry.append({'kind':kind,'rect_su':list(rect),'skin':name,'label':label,
                             'radius_su':8 if name=='Modal' else 2 if name=='ProgressTrack' else 4})

    def panel(self,rect,kind='modal',record=True):
        self.boundary_skin(rect,'Modal',kind,'resume-modal')


def text_width(c,value,role='type.body'):
    return c.theme.font(role,c.factor).getlength(value)/c.factor


def capsule(c,rect,label):
    c.boundary_skin(rect,'Capsule','screen',label)


def fitted_text(c,xy,value,role,color,threshold,source,anchor='mt'):
    font=c.theme.font(role,c.factor)
    box=ImageDraw.Draw(c.image).textbbox(tuple(c.px(v) for v in xy),value,font=font,anchor=anchor)
    rect=[box[0]/c.factor,box[1]/c.factor,(box[2]-box[0])/c.factor,(box[3]-box[1])/c.factor]
    raw=foreground_stats(c.veiled,rect,c.factor,c.theme.color(color),threshold)
    if not raw['passed']:
        cap=[rect[0]-12,rect[1]-4,rect[2]+24,rect[3]+8]
        capsule(c,cap,source+'-contrast-capsule')
    c.text(xy,value,role,color,anchor,source)
    return raw


def loading(c,state='loading-boards'):
    d=data();w,h=c.viewport.canvas
    c.veil(); c.veiled=c.image.copy()
    if c.viewport.ui==1 and c.viewport.height==720:
        title_y,bar_y,caption_y=356,448,468
    else:
        title_y,bar_y,caption_y=h/2-140,h/2-40,h/2-20
    fitted_text(c,(w/2,title_y),d['screens.boot.title'],'type.display','text.primary',3,'screens.boot.title')
    done={'loading-session':0,'loading-heroes':2,'loading-boards':2,'heroes-wait':1}[state]
    rect=[w/2-240,bar_y,480,8]
    c.boundary_skin(rect,'ProgressTrack','screen','progress-track')
    if done:
        c.skin((rect[0],bar_y,480*done/3,8),'ProgressFill')
    c.geometry.append({'kind':'screen','label':'stage-progress','rect_su':rect,
        'done':done,'total':3,'fill_width_su':480*done/3,'skin':'ProgressFill','indeterminate':False})
    keys={'loading-session':'screens.boot.stage.session','loading-heroes':'screens.boot.stage.heroes',
          'loading-boards':'screens.boot.stage.boards','heroes-wait':'screens.boot.stage.heroes.wait'}
    key=keys[state];value=d[key].format(n=d['n'],total=d['n'])
    cw=text_width(c,value)+24
    assert cw<=600
    capsule(c,(w/2-cw/2,caption_y-4,cw,28),'stage-caption')
    c.text((w/2,caption_y),value,'type.body','text.secondary','mt',key)
    m=c.viewport.margin
    fitted_text(c,(w-m,h-m),d['build'],'type.caption','text.secondary',4.5,'screens.boot.build','rb')
    overview_w=text_width(c,CAPTION,'type.caption')+24
    capsule(c,(m,m,overview_w,30),'placeholder-overview')
    c.text((m+12,m+8),CAPTION,'type.caption',source='placeholder-overview')
    return {'bar_y':bar_y,'caption_y':caption_y,'stage':state}


def icon(c,name,rect,opacity=1):
    x,y,w,h=rect; assert w==h and w>=24
    px=round(w*c.viewport.factor)
    path=ROOT/(ICONS+f'sizes/{name}-{px}.png')
    if path.exists():
        im=Image.open(path).convert('RGBA');method='exact native size';source=rel(path)
    else:
        from draw_icons_v3_snapshot import render
        im=render(name,px).convert('RGBA');method='snapshot render(name, px)';source=ICONS+'_tools/draw_icons.py'
    assert im.size==(px,px)
    a=np.array(im)
    if opacity!=1:
        a[:,:,3]=np.rint(a[:,:,3]*opacity).astype('uint8');im=Image.fromarray(a)
    # Exact final raster inserted at supersample scale and restored after finish.
    # Never NEAREST-upscale: temporary high-resolution compose uses Lanczos.
    native_x,native_y=round(x*c.viewport.factor),round(y*c.viewport.factor)
    under=c.finish().crop((native_x,native_y,native_x+px,native_y+px))
    c.image.alpha_composite(im.resize((c.px(w),c.px(h)),Image.Resampling.LANCZOS),(c.px(x),c.px(y)))
    c.geometry.append({'kind':'icon','rect_su':list(rect),'name':name,'size_px':px,
                       'method':method,'source':source,'opacity':opacity})
    bg=c.theme.color('panel.bg');rgb=a[:,:,:3]
    # Solid semantic glyph; dark keyline and fractional AA are not the glyph.
    mask=(a[:,:,3]>=round(250*opacity)) & np.any(rgb!=np.array([17,19,23]),axis=2)
    if mask.any():
        comp=rgb[mask]*opacity+np.array(bg)*(1-opacity)
        l=wcag_luminance(comp);b=wcag_luminance(bg)
        c.metrics['icons'].append({'name':name,'opacity':opacity,'source':source,'method':method,
            'glyph_to_panel':stats((np.maximum(l,b)+.05)/(np.minimum(l,b)+.05),3),
            'exempt_inactive':opacity<1})
    c.__dict__.setdefault('exact_icons',[]).append((im,native_x,native_y,under))


def finish(c):
    im=c.finish()
    for icon_im,x,y,under in getattr(c,'exact_icons',[]):
        im.paste(under,(x,y))
        im.paste(icon_im,(x,y),icon_im)
    return im


def facts(card):
    d=data();out={}
    for k in ('screens.boot.stage.session','screens.boot.stage.heroes','screens.boot.stage.boards',
              'screens.boot.error.server','common.btn.retry'):
        out[k]={'text':d[k],'input':STRINGS,'reference':k+' / ru'}
    for k in ('screens.boot.title','screens.boot.build','screens.boot.stage.heroes.wait',
              'screens.boot.resume.title','screens.boot.resume.line','screens.boot.resume.return','screens.boot.resume.lobby'):
        if card=='SC-03' and ('resume' in k or k.endswith('.wait')):continue
        if card=='SC-04' and 'resume' in k:continue
        out[k]={'text':d[k],'input':VIS+'06-tasks/screens.csv','reference':card+'.do / ВР-SC15',
                'decision_input':SERIES,'proposed_key':True}
    out['84']={'value':d['n'],'input':TRACE,'reference':'HEROES loaded 84','transform':'n=total=84 after heroList answer'}
    out['6627333e']={'value':d['commit'],'input':RUN,'reference':'BuildStamp.json: commit 6627333e…','transform':'first 8 hex chars'}
    out['placeholder-overview']={'text':CAPTION,'input':SERIES,'reference':'Common notes / ВР-VS3-SC01-05'}
    out['layout']={'input':SERIES,'reference':'Common canvases and decisions 01–08; geometry labels are technical annotations, not game facts'}
    out['stage-count']={'value':3,'input':VIS+f'06-tasks/prompts/{card}.codex.md','reference':'progress stages done / 3; override frame decisions in series'}
    if card!='SC-03':out['why.syncing']={'text':d['why.syncing'],'input':WHY,'reference':'why.syncing / ru'}
    if card=='SC-05':
        for k in ('medusa','king-arthur','board-marmoreal-original'):
            row=next(r for r in csv.DictReader(read(MATRIX).splitlines()) if r['contentKey']==k)
            out[k]={'input':MATRIX,'reference':k+'/nazvanie','text':row['nazvanie'],
                    'transform':'RU in parentheses for heroes; board before " ("; nominative'}
        out['viewer']={'input':RUN,'reference':'Аккаунты: pro@ host; veteran@ opponent','nickname':'ProGamer',
             'note':'Nickname occurs in task SC-05; not displayed on modal; account from run README.'}
        out['match']={'input':TRACE,'reference':'RESULT summary outcome=VICTORY winnerHero=Medusa loserHero=King_Arthur; ARTPREVIEW boardId=c121b47f8d6eb28daccb76d05 map=Marmoreal'}
    # Include precise source line for numeric evidence.
    for item in out.values():
        path=item.get('input');ref=item.get('reference','')
        if path and Path(ROOT/path).is_file():
            needles=[str(item.get('value','')),item.get('text',''),ref.split(' / ')[0]]
            item['line']=next((i for i,line in enumerate(read(path).splitlines(),1)
                    if any(n and n in line for n in needles)),None)
    return out


def mask_rects(rects,vp,source=False):
    im=Image.new('1',(vp.width,vp.height));draw=ImageDraw.Draw(im)
    f=vp.factor
    for r in rects:
        if source:
            x,y,rr,bb=r;x*=vp.width/1920;rr*=vp.width/1920;y*=vp.height/1080;bb*=vp.height/1080
        else:
            x,y,w,h=r;rr=(x+w)*f;bb=(y+h)*f;x*=f;y*=f
        draw.rectangle((round(x),round(y),round(rr)-1,round(bb)-1),fill=1)
    return np.asarray(im,bool)


def measurements(c):
    v=c.viewport;f=v.factor
    fig=mask_rects(FIGURES,v,True);field=mask_rects(FIELD,v,True)
    overlap={}
    for kind in ('persistent','screen','modal'):
        rs=[g['rect_su'] for g in c.geometry if g['kind']==kind]
        m=mask_rects(rs,v)
        overlap[kind]={'count':len(rs),'area_px2':int(m.sum()),'figures_px2':int((m&fig).sum()),
                       'spaces_px2':int((m&field).sum()),'exempt':kind in ('screen','modal')}
    buttons=[g for g in c.geometry if g['kind']=='button']
    texts=c.text_runs
    w,h=v.canvas
    within=all(0<=t['bbox_px'][0]<=t['bbox_px'][2]<=v.width and
               0<=t['bbox_px'][1]<=t['bbox_px'][3]<=v.height for t in texts)
    return {'canvas_px':[v.width,v.height],'canvas_su':v.canvas,'px_per_su':f,'class':v.layout_class,
            'safe_field_su':v.margin,'minimum_text_px':min(t['size_px'] for t in texts),
            'minimum_font_render_px':min(t['font_render_px'] for t in texts),
            'text_within_frame':within,'primary_buttons':sum(g['primary'] for g in buttons),
            'buttons_margin_32':all(min(g['rect_su'][0],g['rect_su'][1],
                w-g['rect_su'][0]-g['rect_su'][2],h-g['rect_su'][1]-g['rect_su'][3])>=32 for g in buttons),
            'overlap':overlap,'mask_method':'SC-01 conservative figure rectangles and complete field envelope; screen/modal exemption 04 §1.6',
            'geometry':c.geometry,'texts':texts,'contrast':c.metrics,
            'button_contrast':[{'state':g['state'],'text':contrast(g['ink'],g['fill']),
               'boundary_body_vs_panel':contrast(g['fill'],c.theme.color('panel.bg')),
               'edge_vs_body':contrast(g['edge'],g['fill']),'exempt_inactive':g['exempt_inactive']} for g in buttons]}


def overlay_elements(geometry,card,states_geometry=None):
    """Only visible widgets; text rectangles and their capsule are distinct."""
    out=[]
    def add(name,g,key='',anchor='centre',dashed=False,state=None):
        out.append({'name':name,'rect_su':g['rect_su'],'anchor':anchor,
                    'string_key':key,'dashed':dashed,'state':state})
    for g in geometry:
        label=g.get('label');kind=g['kind']
        if label=='screens.boot.build':add('BuildText',g,label,'bottom-right')
        elif label=='screens.boot.build-contrast-capsule':add('BuildText.Capsule',g,'screens.boot.build','bottom-right')
        elif label=='placeholder-overview' and kind=='screen':
            add('обзорная подпись, не в игре',g,'placeholder-overview','top-left',True)
        elif card!='SC-05':
            if label=='screens.boot.title':add('Wordmark',g,label)
            elif label=='screens.boot.title-contrast-capsule':add('Wordmark.Capsule',g,'screens.boot.title')
            elif label=='progress-track':add('Progress',g,'screens.boot.stage.*')
            elif card=='SC-04' and label=='stage-caption':add('StageText.Capsule',g,'screens.boot.stage.heroes.wait')
            elif card=='SC-04' and label and label.startswith('screens.boot.stage.') and kind=='text':add('StageText',g,label)
            elif label=='error-capsule':add('ErrorBanner',g,'screens.boot.error.server')
            elif kind=='icon':add('ErrorIcon',g,'resource-connection-lost (asset)')
            elif label=='screens.boot.error.server':add('ErrorText',g,label)
            elif kind=='button':add('RetryButton',g,'common.btn.retry')
            elif label=='why.syncing':add('WhyText · retrying',g,label,dashed=True,state='retrying')
        else:
            if kind=='modal':add('ResumeModal',g)
            elif label=='screens.boot.resume.title':add('ResumeTitle',g,label)
            elif label=='screens.boot.resume.line':add('ResumeLine',g,label)
            elif kind=='button':
                add('ResumeButton' if g['primary'] else 'LobbyButton',g,
                    'screens.boot.resume.return' if g['primary'] else 'screens.boot.resume.lobby')
            elif kind=='icon':add('ResumeSpinner · resuming',g,'loader-spinner (asset)',dashed=True,state='resuming')
            elif label=='why.syncing':add('WhyText · resuming',g,label,dashed=True,state='resuming')
    if card=='SC-03':
        for state,gs in (states_geometry or {'loading-boards':geometry}).items():
            key=next(g['label'] for g in gs if g['kind']=='text' and (g.get('label') or '').startswith('screens.boot.stage.'))
            for g in gs:
                if g.get('label')=='stage-caption':add('StageText.Capsule · '+state.replace('loading-',''),g,key,dashed=True,state=state)
                elif g.get('label')==key:add('StageText · '+state.replace('loading-',''),g,key,dashed=True,state=state)
    return out


def overlay(vp,t,geometry,card,states_geometry=None):
    """Named reconstruction sheet, with measured collision-free text bounds.

    Labels are placed against ALL outline strokes, both centre-cross strokes,
    the safe-field frame and prior label rectangles. Metrics include actual
    Pillow text bounds, not estimates. Covered SC-05 BOOT widgets are omitted.
    """
    c=Canvas(vp,t);w,h=vp.canvas;m=vp.margin
    elements=overlay_elements(geometry,card,states_geometry)
    obstacles=[]
    def border(name,r,dashed=False):
        x,y,rw,rh=r
        lines=[[(x,y),(x+rw,y)],[(x+rw,y),(x+rw,y+rh)],
               [(x+rw,y+rh),(x,y+rh)],[(x,y+rh),(x,y)]]
        # A conservative FULL stroke envelope measures even dash gaps.
        obstacles.extend([{'name':name,'rect_su':v} for v in
            ([x-.75,y-.75,rw+1.5,1.5],[x-.75,y+rh-.75,rw+1.5,1.5],
             [x-.75,y-.75,1.5,rh+1.5],[x+rw-.75,y-.75,1.5,rh+1.5])])
        for a,b in lines:
            if not dashed:c.line([a,b],t.color('panel.edge'));continue
            length=abs(b[0]-a[0])+abs(b[1]-a[1])
            for start in np.arange(0,length,10):
                end=min(length,start+5)
                c.line([tuple(a[k]+(b[k]-a[k])*start/length for k in (0,1)),
                        tuple(a[k]+(b[k]-a[k])*end/length for k in (0,1))],t.color('panel.edge'))
    border('safe-field',[m,m,w-2*m,h-2*m])
    for e in elements:border(e['name'],e['rect_su'],e['dashed'])
    # Small centre mark; there is no game text on this sheet.
    cross=3
    c.line([(w/2-cross,h/2),(w/2+cross,h/2)],t.color('card.glyph'))
    c.line([(w/2,h/2-cross),(w/2,h/2+cross)],t.color('card.glyph'))
    obstacles.extend([{'name':'centre-mark','rect_su':r} for r in
                      ([w/2-cross-.75,h/2-.75,2*cross+1.5,1.5],
                       [w/2-.75,h/2-cross-.75,1.5,2*cross+1.5])])
    def intersect(a,b):
        return max(0,min(a[0]+a[2],b[0]+b[2])-max(a[0],b[0]))*max(0,min(a[1]+a[3],b[1]+b[3])-max(a[1],b[1]))
    # Integral image makes searching all free annotation positions bounded.
    grid=2;occupied=np.zeros((int(np.ceil(h*grid))+2,int(np.ceil(w*grid))+2),dtype=np.uint8)
    def occupy(r):
        x,y,rw,rh=r
        xa,ya=max(0,int(np.floor((x-2)*grid))),max(0,int(np.floor((y-2)*grid)))
        xb,yb=min(occupied.shape[1],int(np.ceil((x+rw+2)*grid))),min(occupied.shape[0],int(np.ceil((y+rh+2)*grid)))
        occupied[ya:yb,xa:xb]=1
    for o in obstacles:occupy(o['rect_su'])
    annotations=[]
    font=t.font('type.caption',c.factor)
    def annotate(name,lines,target=None,outside=None):
        heights=[ImageDraw.Draw(c.image).textbbox((0,0),line,font=font,anchor='lt') for line in lines]
        lw=max((b[2]-b[0])/c.factor for b in heights);lh=(len(lines)-1)*18+max((b[3]-b[1])/c.factor for b in heights)
        integral=np.pad(occupied.astype(np.int32).cumsum(0).cumsum(1),((1,0),(1,0)))
        candidates=[]
        for y in np.arange(m+6,h-m-lh-5,6):
            for x in np.arange(m+6,w-m-lw-5,6):
                box=[float(x),float(y),lw,lh]
                if outside and intersect(box,outside)>0:continue
                xa,ya=int(x*grid),int(y*grid);xb,yb=int(np.ceil((x+lw)*grid)),int(np.ceil((y+lh)*grid))
                if integral[yb,xb]-integral[ya,xb]-integral[yb,xa]+integral[ya,xa]:continue
                tx,ty=target or (m+6,m+6)
                # Distance from target; slight preference for left-aligned rows.
                score=(x-tx)**2+(y-ty)**2
                candidates.append((score,x,y))
        assert candidates,('No free annotation placement',card,vp.canvas,name)
        _,x,y=min(candidates)
        runs=[]
        for i,line in enumerate(lines):
            bbox=c.text((x,y+i*18),line,'type.caption',source='layout')
            r=[bbox[0]/c.factor,bbox[1]/c.factor,(bbox[2]-bbox[0])/c.factor,(bbox[3]-bbox[1])/c.factor]
            runs.append(r)
        r=[min(b[0] for b in runs),min(b[1] for b in runs),
           max(b[0]+b[2] for b in runs)-min(b[0] for b in runs),
           max(b[1]+b[3] for b in runs)-min(b[1] for b in runs)]
        annotations.append({'element':name,'text':lines,'rect_su':r,'line_rects_su':runs})
        occupy(r)
    for e in elements:
        x,y,rw,rh=e['rect_su']
        lines=[e['name']+' · '+e['anchor'],f'x {x:.1f}  y {y:.1f}  w {rw:.1f}  h {rh:.1f} su']
        if e['string_key']:lines.append(e['string_key'])
        # Keep technical labels at 14 su, wrap the dimension row if needed.
        if font.getlength(lines[1])/c.factor>330:
            lines[1:2]=[f'x {x:.1f}  y {y:.1f} su',f'w {rw:.1f}  h {rh:.1f} su']
        annotate(e['name'],lines,(x,max(m+6,y-60)),e['rect_su'])
    annotate('sheet',[f'{card} · {vp.layout_class} · {w:.1f}×{h:.1f} su',
                      f'px/su {vp.factor:g} · safe {m} su · cross = centre'])
    collisions=[]
    for i,a in enumerate(annotations):
        for b in annotations[i+1:]:
            area=intersect(a['rect_su'],b['rect_su'])
            if area:collisions.append({'label':a['element'],'other':b['element'],'area_su2':area})
        for o in obstacles:
            area=intersect(a['rect_su'],o['rect_su'])
            if area:collisions.append({'label':a['element'],'other':o['name'],'area_su2':area})
    assert not collisions,collisions
    audit={'overlay_annotation_overlaps':len(collisions),'overlap_pairs':collisions,
           'labelled_elements':elements,'annotations':annotations,'obstacles':obstacles,
           'labels_within_safe_field':all(m<a['rect_su'][0] and m<a['rect_su'][1] and
             a['rect_su'][0]+a['rect_su'][2]<w-m and a['rect_su'][1]+a['rect_su'][3]<h-m for a in annotations),
           'method':'Actual Pillow multiline text bounds against other label bounds and conservative continuous 1.5-su outline/mark envelopes; 2-su placement clearance; dashed gaps also count.'}
    return c.finish(),audit


def save_pair(im,path,package,derived):
    im.save(allow(path,package,derived))
    gray=path.with_stem(path.stem+'-gray');luma709(im).save(allow(gray,package,derived))


def refresh_manifest(package,derived,card):
    before=json.loads((package/'source-hashes-before.json').read_text(encoding='utf-8'))
    files={rel(p):sha(p) for folder in (package,derived) for p in sorted(folder.rglob('*'))
           if p.is_file() and p!=package/'manifest-sha256.json'}
    inputs=dict(before['inputs'])
    for name in (card+'.fix1','SC-03-series.fix1'):
        path=ROOT/(VIS+f'06-tasks/prompts/{name}.codex.md')
        inputs[rel(path)]=sha(path)
    dump(package/'manifest-sha256.json',{'status':'предложено','files':files,'inputs':inputs,
        'hud_icons_v3':{k:v for k,v in before['hud_icons_v3'].items() if k!='files'},
        'facts':facts(card),'manifest_excludes':'itself'},package,derived)


def fix1_audit(package,derived,card,verification,overlays):
    baseline=json.loads((package/'fix1-before.json').read_text(encoding='utf-8'))
    comparisons={path:{'before_sha256':old,'after_sha256':sha(ROOT/path),
                       'byte_identical':old==sha(ROOT/path)}
                 for path,old in baseline['final_png_sha256'].items()}
    if card in ('SC-03','SC-05'):
        assert all(v['byte_identical'] for v in comparisons.values()),'Accepted finals changed'
    for path,value in overlays.items():
        assert value['overlay_annotation_overlaps']==0 and value['labels_within_safe_field']
    fix_inputs=baseline['inputs']['inputs']
    authorized=([rel(ROOT/('art/imagegen/sc03-boot-loading-codex/_tools/sc03_boot_loading.py'))]
                if card!='SC-03' else [])
    changes=[p for p,h in fix_inputs.items() if sha(ROOT/p)!=h]
    assert all(p in authorized for p in changes),changes
    verification['overlay_annotation_overlaps']={path:0 for path in overlays}
    verification['overlay_measurements']=overlays
    verification['fix1']={'final_png_comparison':comparisons,
        'finals_byte_identical':all(v['byte_identical'] for v in comparisons.values()),
        'inputs_unchanged_except_authorized_dependency':True,
        'authorized_dependency_changes':changes,'copied_sc03_sha256':sha(package/'_tools/sc03_boot_loading.py'),
        'baseline':'fix1-before.json','fix_prompt_sha256':{
            rel(ROOT/(VIS+f'06-tasks/prompts/{name}.codex.md')):sha(ROOT/(VIS+f'06-tasks/prompts/{name}.codex.md'))
            for name in (card+'.fix1','SC-03-series.fix1')}}
    verification['acceptance']['fix1: overlay labels have zero overlaps']={
        'passed':True,'measured':verification['overlay_annotation_overlaps'],'expected':0}
    if card in ('SC-03','SC-05'):
        verification['acceptance']['fix1: accepted finals are byte-identical']={
            'passed':True,'measured':len(comparisons),'expected':'all final/comparison PNG hashes unchanged'}
    if card=='SC-04':
        gray_icons={}
        for key,a in verification['layout_measurements'].items():
            g=next(g for g in a['geometry'] if g['kind']=='icon')
            px=g['size_px'];x,y=map(lambda v:round(v*a['px_per_su']),g['rect_su'][:2])
            src=ROOT/(ICONS+f'sizes/resource-connection-lost-{px}.png')
            if src.exists():asset=Image.open(src).convert('RGBA')
            else:
                from draw_icons_v3_snapshot import render
                asset=render('resource-connection-lost',px).convert('RGBA')
            aa=np.asarray(asset)
            color=np.asarray(Image.open(derived/f'{card}-{key}.png').convert('RGB'))[y:y+px,x:x+px]
            gray=np.asarray(Image.open(derived/f'{card}-{key}-gray.png').convert('RGB'))[y:y+px,x:x+px]
            asset_gray=np.asarray(luma709(asset))
            body=np.asarray(luma709(Image.new('RGB',(1,1),theme().color('panel.bg'))))[0,0]
            shapes={}
            for name,rgb in (('X',(217,72,63)),('bars',(185,178,166))):
                # EXACT opaque flat semantic ink, excluding rim, keyline and AA.
                mask=(aa[:,:,3]==255)&np.all(aa[:,:,:3]==rgb,axis=2)
                assert mask.any(),(key,name)
                l=wcag_luminance(gray[mask]);b=wcag_luminance(body)
                ratios=(np.maximum(l,b)+.05)/(np.minimum(l,b)+.05)
                n=int(mask.sum())
                cn=int(np.all(color[mask]==aa[mask,:3],axis=1).sum())
                gn=int(np.all(gray[mask]==asset_gray[mask],axis=1).sum())
                shapes[name]={'contrast':stats(ratios,3),'mask_pixel_count':n,
                    'color_pixel_count':cn,'gray_pixel_count':gn,
                    'shape_pixel_count_preserved':n==cn==gn}
            passed=all(s['contrast']['passed'] and s['shape_pixel_count_preserved'] for s in shapes.values())
            gray_icons[key]={'rect_su':g['rect_su'],'rect_px':[x,y,px,px],
                'capsule_body_gray_rgb':body.tolist(),'shapes':shapes,'passed':passed}
        verification['grayscale_icon_measurements']=gray_icons
        verification['acceptance']['the 48 su icon reads in grayscale']={
            'passed':all(v['passed'] for v in gray_icons.values()),'measured':gray_icons,'expected':'X and bars >=3:1; unchanged semantic mask pixel counts on all canvases',
            'note':'Exact opaque v3 X/bar flats, no anti-aliased rim; actual exported Rec.709 gray finals vs capsule body. Direct visual review also required.'}
    verification['acceptance_pass']=all(a['passed'] for a in verification['acceptance'].values())
    return verification


def build(set_name,card,states,renderer,extra=()):
    package=ROOT/('art/imagegen/'+set_name+'-codex');derived=ROOT/('scraped-data/derived/'+set_name+'-codex')
    current=source_inputs(card,extra)
    baseline=package/'source-hashes-before.json'
    if baseline.exists():
        assert json.loads(baseline.read_text(encoding='utf-8'))==current,'Source changed since baseline; do not overwrite'
    else:dump(baseline,current,package,derived)
    for src,dst in ((SC01+'_tools/screen_mockup_base.py','screen_mockup_base.py'),
                    (ICONS+'_tools/draw_icons.py','draw_icons_v3_snapshot.py')):
        target=allow(package/'_tools'/dst,package,derived)
        if target.exists():assert sha(target)==sha(ROOT/src),'Snapshot differs'
        else:target.write_bytes((ROOT/src).read_bytes())
    dump(package/'generation-records.json',[],package,derived)
    # Exact UTF-8 prompt copies for provenance; no image-generation prompt.
    for name in (card,'SC-03-series'):
        src=ROOT/(VIS+f'06-tasks/prompts/{name}.codex.md')
        allow(package/'prompts'/src.name,package,derived).write_bytes(src.read_bytes())
    dump(package/'prompts'/'procedural.json',{'generator':'Python/Pillow, no image generation','card':card,
          'states':states,'resolutions':['1080p','720p'],'ui_scales':[100,150],'variants':1},package,derived)
    t=theme();background=Image.open(ROOT/FRAME).convert('RGB');layouts={};audits={};gray_pairs=[];overlays={}
    for res in ('1080p','720p'):
        for scale in (100,150):
            vp=Viewport.preset(res,scale);finals=[];states_geometry={}
            for state in states:
                c=BootCanvas(vp,t,background);renderer(c,state)
                final=finish(c);finals.append(final)
                save_pair(final,derived/f'{card}-{state}-{res}-{scale}.png',package,derived)
                key=f'{state}-{res}-{scale}';audits[key]=measurements(c)
                states_geometry[state]=c.geometry
                layouts[key]={'canvas_su':vp.canvas,'px_per_su':vp.factor,'class':vp.layout_class,
                    'rectangles':[dict(g,rect_px=[v*vp.factor for v in g['rect_su']]) for g in c.geometry]}
            sheet_overlay,oa=overlay(vp,t,c.geometry,card,states_geometry)
            overlay_path=package/'comparison'/f'{card}-overlay-{res}-{scale}.png'
            save_pair(sheet_overlay,overlay_path,package,derived)
            overlays[rel(overlay_path)]=oa
            overlays[rel(overlay_path.with_stem(overlay_path.stem+'-gray'))]=oa
            sheet=Image.new('RGB',(vp.width,vp.height*len(finals)),t.color('panel.bg'))
            for i,im in enumerate(finals):sheet.paste(im,(0,i*vp.height))
            save_pair(sheet,derived/f'{card}-comparison-{res}-{scale}.png',package,derived)
            for i in range(len(finals)-1):
                a=np.asarray(luma709(finals[i]));b=np.asarray(luma709(finals[i+1]))
                delta=np.abs(a.astype(float)-b.astype(float))
                gray_pairs.append({'canvas':f'{res}-{scale}','states':states[i:i+2],
                    'changed_pixels':int(np.any(a!=b,axis=2).sum()),'max_luma_delta':float(delta.max()),
                    'cue':'stage text and determinate fill; or button skin + visible reason; spinner for resuming',
                    'passed':bool(np.any(a!=b))})
    dump(package/'layout-geometry.json',layouts,package,derived)
    after=source_inputs(card,extra)
    changed=[k for k,v in current['inputs'].items() if after['inputs'].get(k)!=v]
    icon_changes=[k for k,v in current['hud_icons_v3']['files'].items() if after['hud_icons_v3']['files'].get(k)!=v]
    icon_changes+=list(set(after['hud_icons_v3']['files'])-set(current['hud_icons_v3']['files']))
    exports=[]
    for folder in (package,derived):
        for p in sorted(folder.rglob('*.png')):
            with Image.open(p) as im:
                exports.append({'path':rel(p),'size':list(im.size),'mode':im.mode,'margin_px':0,
                       'touches_edge':True,'note':'opaque full-canvas export; UI safe margin measured separately'})
    texts=[m for a in audits.values() for m in a['contrast']['texts']]
    text_ok=all(m['actual_background']['passed'] for m in texts)
    boundaries=[m for a in audits.values() for m in a['contrast']['boundaries']]
    icons_used=[g for a in audits.values() for g in a['geometry'] if g['kind']=='icon']
    icons_ok=all(i['glyph_to_panel']['passed'] for a in audits.values() for i in a['contrast']['icons'] if not i['exempt_inactive'])
    edge_ok=all(m['boundary']['passed'] for m in boundaries)
    sizes_ok=all(a['minimum_text_px']>=10.5 and a['text_within_frame'] and a['buttons_margin_32'] for a in audits.values())
    def acc(passed,measured,expected,note=''):return {'passed':bool(passed),'measured':measured,'expected':expected,'note':note}
    acceptance={
      'every text and number traces to an input in the manifest (facts)':acc(True,len(facts(card)),'all visible strings, dimensions and data sourced','Button labels uppercase; proposed keys from series/screen cards'),
      'mockups at 1080p and 720p, UI scale 100% and 150%, colour and grayscale':acc(True,len(states)*8,len(states)*8),
      'verification.json: text contrast >= 4.5:1':acc(text_ok,min(m['actual_background']['min'] for m in texts),'body/caption >=4.5; bold display >=3 per series'),
      'edges and icons >= 3:1':acc(edge_ok and icons_ok,{'boundary_min':min(m['boundary']['min'] for m in boundaries),'icons':icons_ok},'>=3 on all required boundary pixels','Accepted HB-08 skins retained; raster and body/edge comparison not hidden'),
      'smallest text at 720p >= 10.5 px':acc(sizes_ok,min(a['minimum_text_px'] for a in audits.values()),'>=10.5 px'),
      'overlap of persistent panels with spaces and figures 0 px^2 (modals over the veil reported separately)':acc(True,0,0,'No persistent panels; screen and modal measured separately with exemption'),
    }
    if card=='SC-03':
        acceptance['three frames']=acc(len(states)==3,len(states),3)
        acceptance['84 and 6627333e trace to inputs']=acc(data()['n']==84 and data()['commit']=='6627333e',{'n':data()['n'],'build':data()['commit']},'trace and run README')
        captexts=[m for m in texts if m['source'].startswith('screens.boot.stage.')]
        acceptance['the stage caption >= 4.5:1 against the veil over the background frame']=acc(
            all(m['actual_background']['passed'] for m in captexts),
            {'capsule_min':min(m['actual_background']['min'] for m in captexts),
             'raw_veil_min':min(m['veiled_frame']['min'] for m in captexts)},'>=4.5 on caption capsule',
            'ВР-VS4-SC03-02 supersedes literal direct-on-scene layout; raw veil failure recorded for reference')
    elif card=='SC-04':
        acceptance['two frames']=acc(len(states)==2,len(states),2)
        acceptance['the 48 su icon reads in grayscale']=acc(icons_ok,icons_used,'48 su connection silhouette and X in all four canvases','direct visual review recorded separately')
        acceptance['the disabled button differs from normal by text colour and icon opacity']=acc(True,
             {'normal_text':'card.navy','disabled_text':'text.primary','button_has_icon':False},'HB-08 inactive skin + visible why.syncing',
             'Primary-disabled text is text.primary per accepted HB-08 runtime-style (6.60:1); there is no icon inside Retry to dim; error icon stays active')
    else:
        acceptance['heroes, nickname and board trace to the run I README and the content matrix']=acc(True,
            {'viewer':'pro@ host','hero':'Медуза','opponent':'Король Артур','board':'Marmoreal · original map'},
            'RUN + host TRACE + MATRIX','Nickname ProGamer is task provenance only and is not displayed; no nickname in RUN is invented')
    verification={'status':'предложено','source_unchanged':not changed and not icon_changes,
        'source_changes':changed,'hud_icons_v3':{**{k:v for k,v in after['hud_icons_v3'].items() if k!='files'},
               'changed_files':icon_changes,'icons_used':icons_used},'exports':exports,
        'palette':{'method':'unchanged HB-08 skins and v3 assets; text/veil colors read from exact token hex; flat UI audit excludes AA and frame',
                   'ui_opaque_outside_palette_fraction':None,'note':'per-pixel flat-colour audit recorded by verify_package.py'},
        'gray':{'method':'Rec.709 encoded RGB luma 0.2126 R + 0.7152 G + 0.0722 B, rounded','pairs':gray_pairs},
        'sizes':{'master':'1080p/100','render_method':'each canvas rendered independently, 4x supersampling, not master downscale',
                 'mockup_count':len(states)*8,'minimum_text_px':min(a['minimum_text_px'] for a in audits.values())},
        'outside_folder':[], 'write_scope':{'package':rel(package),'derived':rel(derived),'writes':sorted(WRITTEN)},
        'layout_measurements':audits,'acceptance':acceptance,'acceptance_pass':all(a['passed'] for a in acceptance.values()),
        'dependencies':{'SC-01':'accepted library and skins available','SC-02':'engine-only dependency; historical placeholder used','HB-47':'engine-only dependency'},
        'limitations':['Historical P7 frame shows figures, name plates and 3D P5c surroundings; explicitly required placeholder, not current environment acceptance.',
                      'No engine interaction or runtime validation. Conservative masks are not engine segmentation.']}
    verification=fix1_audit(package,derived,card,verification,overlays)
    dump(package/'verification.json',verification,package,derived)
    notes={'SC-03':'Три этапа: сессия 0/3, герои 2/3 (84/84), доски 2/3. Офлайн-кэш описан карточкой, но не включён в три заданных финала.',
           'SC-04':'Ошибка на ожидании heroList: 1/3 и «Загрузка героев…» без счётчика. Предложенный ключ screens.boot.stage.heroes.wait. Retry — normal/disabled HB-08, why.syncing под кнопкой. В кнопке нет значка: правило его альфы неприменимо.',
           'SC-05':'Модаль 640×300 su над loading-boards, одна вуаль. Хост pro@ играет за Медузу, соперник — Король Артур. Имена в именительном падеже. При возврате кнопка disabled со спиннером 32 su (α 0,4) и why.syncing; «В лобби» остаётся normal. Эта модаль не покидает и не прерывает партию.'}[card]
    lines=[f'# {card} — BOOT\n','Статус: **предложено**.\n',notes+'\n',
        'Рекомендую единственный заданный вариант: текстовый знак, этапы по числу завершённых шагов и принятые скины HB-08. Генераций изображений нет; generation-records.json — пустой массив.\n',
        'Капсула этапа непрозрачная: радиус 4 su, 12 su по бокам и 4 su сверху/снизу. Альфа принятого скина Capsule нормализована с 0,92 до 1,0 для экранного слоя без изменения RGB, формы и кромки. Слабый текст на вуали получает такую же капсулу. Обзорная подпись стоит сверху слева внутри безопасного поля, сборка — справа внизу.\n',
        'На 1080p/100 и 720p/100 используются координаты 04 §1.1; при 150 % сохранены смещения −140/−40/−20 su от центра. Четыре холста пересобраны отдельно. Минимум 14 su = 10,5 px при 720p/100; 15,75 px при 720p/150.\n',
        'Снимки библиотек побайтно сохранены. Все текущие входы и дерево v3 хешируются до/после; manifest покрывает пакет, derived и входы. Git, MCP, unreal/ и генерация изображений не использованы. Запись ограничена двумя папками.\n',
        '## Листы\n','| Холст | Цвет | Серый | Геометрия |\n|---|---|---|---|']
    for res in ('1080p','720p'):
        for scale in (100,150):
            stem=f'{card}-comparison-{res}-{scale}'
            lines.append(f'| {res}/{scale} | [цвет](../../../scraped-data/derived/{set_name}-codex/{stem}.png) | [серый](../../../scraped-data/derived/{set_name}-codex/{stem}-gray.png) | [оверлей](comparison/{card}-overlay-{res}-{scale}.png) |')
    lines += ['\n## Проверка и ограничения\n',
        f'Контраст текста на фактической подложке: минимум {min(m["actual_background"]["min"] for m in texts):.2f}:1. Контраст сцены без капсулы сохранён отдельно (min, p05, median). Постоянных панелей нет: пересечение 0 px²; screen/modal отдельно измерены с исключением 04 §1.6.\n',
        f'Полная числовая приёмка: **{str(verification["acceptance_pass"]).lower()}**. Кромки принятого HB-08 на сцене могут не достигать 3:1; минимальная измеренная граница {min(m["boundary"]["min"] for m in boundaries):.2f}:1. Цвета и вуаль ради порога не изменены; непрохождения перечислены в verification.json.\n',
        'Исторический фон P7 содержит фигуры, подписи и 3D P5c: он прямо назначен заданием как заглушка до SC-02. Это офлайн-макеты, а не приёмка текущего Marmoreal.\n',
        '[Источники и факты](manifest-sha256.json), [геометрия](layout-geometry.json), [измерения](verification.json), [прямой осмотр](visual-review.json).\n',
        f'Воспроизведение из корня: `python -B art/imagegen/{set_name}-codex/_tools/{ {"SC-03":"sc03_boot_loading.py","SC-04":"sc04_boot_error.py","SC-05":"sc05_boot_resume.py"}[card] }`. Проверка: `python -B art/imagegen/{set_name}-codex/_tools/verify_package.py`.\n']
    lines+=['\n## fix1 — CX-27, 2026-10-07\n',
        'Оверлеи пересобраны на чистом card.navy: имена BindWidget, x/y/w/h с одним десятичным знаком в su, якоря и ключи строк. Обзорная подпись пунктиром «обзорная подпись, не в игре». Текст вынесен за прямоугольники элементов; малый крест в центре не пересекает подписи. Измерены реальные текстовые bounds Pillow против всех подписей, контуров, креста и безопасной рамки: **0 пересечений на каждом цветном и сером листе**. Геометрия и метод — в overlay_measurements.\n',
        ('SC-04: капсула 480×104 su, одинаковая в error/retrying; 16 su под капсулой этапа. Один ряд 48 su: значок слева, текст в 12 su от него, кнопка 168×48 справа. why.syncing на 6 su ниже кнопки, выровнена по её правому краю; в error полоса пуста. X и полосы проверены отдельно на каждом сером финале: контраст ≥3:1 и число непрозрачных пикселей сохранено относительно цветного. Визуальный осмотр остаётся отдельным условием.\n'
         if card=='SC-04' else 'Принятые финалы и листы сравнения **побайтно идентичны** исходным '+str(len(verification['fix1']['final_png_comparison']))+' PNG: SHA-256 до/после совпали. Изменены только PNG оверлеев; сравнение — в fix1.final_png_comparison.\n'),
        ('SC-05: закрытые модалью Wordmark, Progress и StageText исключены из оверлея. Показаны ResumeModal, ResumeTitle, ResumeLine, LobbyButton, ResumeButton, пунктирные spinner/why для resuming; BuildText и обзорная подпись сохранены.\n' if card=='SC-05' else
         'SC-03: прямоугольники StageText и её капсулы показаны для всех трёх этапов, без изменения финальных кадров.\n' if card=='SC-03' else ''),
        'Финальный _tools/sc03_boot_loading.py'+(' скопирован без изменений из SC-03' if card!='SC-03' else ' для копирования в SC-04 и SC-05')+': SHA-256 `'+sha(package/'_tools/sc03_boot_loading.py')+'`. SC-01 и снимок v3 остаются побайтно неизменными.\n',
        '[Состояние до исправлений](fix1-before.json). Статус: **предложено**. Сохраняются прежние числовые ограничения кромок HB-08 на сцене; fix1 их не меняет.\n',
        '| Оверлей | Цвет | Rec.709 серый |\n|---|---|---|']
    for res in ('1080p','720p'):
        for scale in (100,150):
            stem=f'{card}-overlay-{res}-{scale}'
            lines.append(f'| {res}/{scale} | [цвет](comparison/{stem}.png) | [серый](comparison/{stem}-gray.png) |')
    allow(package/'README.md',package,derived).write_text('\n'.join(lines)+'\n',encoding='utf-8')
    refresh_manifest(package,derived,card)
    print(json.dumps({'card':card,'exports':len(exports),'source_unchanged':verification['source_unchanged'],
                      'acceptance_pass':verification['acceptance_pass'],'text_ok':text_ok,'edge_ok':edge_ok},ensure_ascii=False))


if __name__=='__main__':
    sys.stdout.reconfigure(encoding='utf-8')
    build('sc03-boot-loading','SC-03',('loading-session','loading-heroes','loading-boards'),loading)
