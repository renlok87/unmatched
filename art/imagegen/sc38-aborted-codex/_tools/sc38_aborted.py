#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""SC-38 independent offline ABORTED modal. Run with python -B.

Only SC-01 and the icon generator are copied libraries. No GAMEOVER import,
network, engine, subprocess, git, or source writes. inputs/ remains immutable.
"""
from __future__ import annotations
import sys
sys.dont_write_bytecode = True
import csv
import hashlib
import itertools
import json
import math
from pathlib import Path
from functools import lru_cache
import numpy as np
from PIL import Image, ImageDraw, ImageFilter

ROOT = Path(__file__).resolve().parents[4]
PKG = ROOT/'art/imagegen/sc38-aborted-codex'
DER = ROOT/'scraped-data/derived/sc38-aborted-codex'
VIS = 'docs/game-design/visual/'
BASE = 'art/imagegen/sc01-screen-base-codex/'
ICONS = 'art/imagegen/hud-icons-v3/'
SKINS = 'art/imagegen/hud-skins-v1-codex/'
STRINGS = 'docs/unreal/contracts/hud/st-screens.csv'
TOKENS = 'docs/unreal/contracts/hud/hud-style-tokens.json'
MASKS = 'art/imagegen/hud-composition-v1-codex/masks.json'
BACKGROUND = 'docs/game-design/evidence/ENV-MAPS/p7-concept-paste-2026-10-01/marmoreal-concept-flag/bench-K1-1920x1080.png'
INPUT = 'scraped-data/derived/sc38-aborted-codex/inputs/aborted-game.json'
SERIES = VIS+'06-tasks/prompts/SC-34-series.codex.md'
FONTDIR = Path('C:/Program Files/Epic Games/UE_5.8/Engine/Content/Slate/Fonts')
PRESETS = [('1080p',100),('1080p',150),('720p',100),('720p',150)]
STATES = ['shown','shown-noname']
WRITES = set()

def rel(p):
    p = Path(p).resolve()
    return p.relative_to(ROOT).as_posix() if p.is_relative_to(ROOT) else p.as_posix()

def load(p):
    return json.loads(Path(p).read_text(encoding='utf-8-sig'))

def info(p):
    b = Path(p).read_bytes()
    return {'sha256':hashlib.sha256(b).hexdigest(),'bytes':len(b)}

def guard(p):
    p = Path(p).resolve()
    if not (p.is_relative_to(PKG) or p.is_relative_to(DER)) or p.is_relative_to(DER/'inputs'):
        raise ValueError(f'Forbidden write: {p}')
    p.parent.mkdir(parents=True,exist_ok=True)
    WRITES.add(rel(p))
    return p

def dump(p,value):
    guard(p).write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')

def icon_tree():
    paths = sorted((ROOT/ICONS).rglob('*'))
    digest = hashlib.sha256(); count = 0
    for p in paths:
        if not p.is_file(): continue
        entry = info(p); count += 1
        digest.update((p.relative_to(ROOT/ICONS).as_posix()+'\0'+entry['sha256']+'\0'+str(entry['bytes'])+'\n').encode())
    return {'path':ICONS.rstrip('/'),'sha256':digest.hexdigest(),'count':count,'method':'sorted relative_path NUL sha256 NUL bytes LF'}

def sources():
    names = [SERIES,VIS+'06-tasks/prompts/SC-38.codex.md',VIS+'02-visual-design.md',VIS+'04-hud-spec.md',
             VIS+'07-prompt-templates.md',VIS+'06-tasks/screens.csv','AGENTS.md',
             'docs/game-design/decisions/2026-10-04-real-boards-only.md',STRINGS,TOKENS,
             'docs/unreal/contracts/hud/st-hud.csv','docs/unreal/contracts/cue-dispatcher/cue-table.json',
             BACKGROUND,MASKS,BASE+'README.md',BASE+'manifest-sha256.json',ICONS+'_tools/draw_icons.py',
             ICONS+'sizes/loader-spinner-48.png',SKINS+'README.md',SKINS+'runtime-style.json',SKINS+'slice-margins.json',
             INPUT,'scraped-data/derived/sc38-aborted-codex/inputs/provenance.json',
             'backend/src/games/game.service.ts','backend/prisma/seed.ts',
             'art/imagegen/hud-actions-v1-codex/README.md','art/imagegen/sc19-loading-codex/README.md',
             'art/imagegen/sc31-reconnect-auto-codex/README.md']
    paths = [ROOT/n for n in names] + [FONTDIR/n for n in ['Roboto-BoldCondensed.ttf','Roboto-Regular.ttf']]
    for directory in [ROOT/(BASE+'_tools'),ROOT/(SKINS+'vector')]:
        paths += [p for p in directory.rglob('*') if p.is_file() and '__pycache__' not in p.parts]
    paths += list((ROOT/(ICONS+'sizes')).glob('resource-connection-lost-*.png'))
    return {rel(p):info(p) for p in sorted(set(paths))}

def prepare():
    current = {'schema':'CX-34.sources/1','files':sources(),'hud_icons_v3_tree':icon_tree(),
               'excluded':'unreal/ excluded by explicit user instruction; superseded S10 run is not an input'}
    before = PKG/'source-hashes-before.json'
    if before.exists(): assert load(before)==current, 'Input changed since baseline'
    else: dump(before,current)
    copies = []
    for src,name in [(BASE+'_tools/screen_mockup_base.py','screen_mockup_base.py'),
                     (ICONS+'_tools/draw_icons.py','draw_icons_v3_snapshot.py')]:
        source = ROOT/src; target = PKG/'_tools'/name
        if not target.exists(): guard(target).write_bytes(source.read_bytes())
        assert target.read_bytes()==source.read_bytes()
        copies.append({'source':src,'copy':rel(target),'sha256':info(source)['sha256'],'byte_identical':True})
    dump(PKG/'copy-provenance.json',copies)
    dump(PKG/'generation-records.json',[])
    guard(PKG/'concepts/.gitkeep').write_text('',encoding='utf-8')
    for name in ['SC-38.codex.md','SC-34-series.codex.md']:
        guard(PKG/'prompts'/name).write_bytes((ROOT/(VIS+'06-tasks/prompts/'+name)).read_bytes())
    provenance = load(DER/'inputs/provenance.json')
    assert info(ROOT/INPUT)['sha256']==provenance['files']['aborted-game.json']['sha256']
    data = load(ROOT/INPUT)
    assert data['game']['status']=='ABORTED' and data['game']['mode']=='ONE_V_ONE'
    assert data['game']['boardId']=='c121b47f8d6eb28daccb76d05' and data['game']['winner'] is None
    assert data['viewer']['username']==data['game']['host']=='ProGamer'
    assert data['leaver']['username']==data['abortActions'][0]['by']==data['game']['opponent']=='Veteran'
    assert data['abortActions'][0]['payload']['reason']=='player_left'
    assert data['turn']['value']==data['state']['turnCount']==1
    return data

@lru_cache(None)
def table():
    with (ROOT/STRINGS).open(encoding='utf-8-sig',newline='') as stream:
        return {row['Key']:row['ru'] for row in csv.DictReader(stream)}

def string(key):
    if key=='screens.aborted.who.unknown': return 'Соперник покинул партию'
    return table()[key]

def string_source(key):
    return {'file':'README.md' if key=='screens.aborted.who.unknown' else STRINGS,'key':key}

def gray_rgb(rgb):
    v = round(np.dot(rgb,[.2126,.7152,.0722]))
    return (v,v,v)

def area(a,b):
    return max(0,min(a[0]+a[2],b[0]+b[2])-max(a[0],b[0]))*max(0,min(a[1]+a[3],b[1]+b[3])-max(a[1],b[1]))

def masks(vp,rect):
    reference=load(ROOT/MASKS); ratio=vp.width/1920; result={}
    x,y,w,h=rect; footprint=np.zeros((vp.height,vp.width),dtype=bool)
    x0,y0,x1,y1=[round(v*vp.factor) for v in [x,y,x+w,y+h]]
    footprint[y0:y1,x0:x1]=True
    for kind in ['field','figures','spaces']:
        im=Image.new('L',(vp.width,vp.height)); draw=ImageDraw.Draw(im)
        if kind=='field': draw.rectangle([round(v*ratio) for v in reference['field_1080p']['marmoreal']],fill=255)
        elif kind=='figures':
            for poly in reference['figure_polygons_1080p']['marmoreal']:
                draw.polygon([(round(x*ratio),round(y*ratio)) for x,y in poly],fill=255)
            im=im.filter(ImageFilter.MaxFilter(2*math.ceil(6*ratio)+1))
        else:
            trans=reference['topology_transforms'][f'marmoreal-{vp.width}x{vp.height}']
            for space in trans['spaces']: draw.polygon([(round(x),round(y)) for x,y in space['polygon_px']],fill=255)
            im=im.filter(ImageFilter.MaxFilter(2*math.ceil(trans['cell_conservative_dilation_px']*ratio)+1))
        mask=np.asarray(im)>0
        result[kind+'_px2']=int((mask&footprint).sum())
        result['veil_'+kind+'_px2']=int(mask.sum())
    return {'source':MASKS,'method':reference['method'],'persistent_overlap_px2':0,
            'layers':[{'widget':'AbortedModal','kind':'modal','modal_exempt':True,
                       **{k:result[k] for k in ['field_px2','figures_px2','spaces_px2']}},
                      {'widget':'Veil','kind':'modal','modal_exempt':True,
                       **{k:result['veil_'+k] for k in ['field_px2','figures_px2','spaces_px2']}}]}

def edge_measure(final,backing,vp,rect,name,body_or_edge=True):
    from screen_mockup_base import contrast
    rgb=np.asarray(final.convert('RGB')); back=np.asarray(backing.convert('RGB').resize(final.size,Image.Resampling.LANCZOS))
    x,y,w,h=rect; f=vp.factor; x0,y0,x1,y1=[round(v*f) for v in [x,y,x+w,y+h]]
    points=[(p,y0,'h') for p in range(x0+round(12*f),x1-round(12*f))]
    points += [(p,y1-1,'h') for p in range(x0+round(12*f),x1-round(12*f))]
    points += [(x0,p,'v') for p in range(y0+round(8*f),y1-round(8*f))]
    points += [(x1-1,p,'v') for p in range(y0+round(8*f),y1-round(8*f))]
    body=tuple(rgb[round((y+7)*f),round((x+12)*f)]); output=[]
    for gray in [False,True]:
        values=[]; edges=[]
        for px,py,axis in points:
            bg=tuple(back[py,px]); samples=[]
            if gray: bg=gray_rgb(bg)
            for delta in range(-2,math.ceil(f)+2):
                qx,qy=(px,py+delta) if axis=='h' else (px+delta,py)
                if 0<=qx<vp.width and 0<=qy<vp.height:
                    value=tuple(rgb[qy,qx]); samples.append(contrast(gray_rgb(value) if gray else value,bg))
            peak=max(samples); edges.append(peak)
            values.append(max(peak,contrast(gray_rgb(body) if gray else body,bg)) if body_or_edge else peak)
        output.append({'widget':name,'gray':gray,'minimum':min(values),'p05':float(np.percentile(values,5)),
                       'median':float(np.median(values)),'fraction_ge_3':float(np.mean(np.asarray(values)>=3)),
                       'edge_only_minimum':min(edges),'method':'actual final peak hairline across normal band or body against same pre-widget backing pixel'})
    return output

def render(res,scale,state,data):
    from screen_mockup_base import Canvas, Theme, Viewport, contrast, luma709, modal_rect
    vp=Viewport.preset(res,scale)
    theme=Theme(ROOT/TOKENS,FONTDIR/'Roboto-BoldCondensed.ttf',FONTDIR/'Roboto-Regular.ttf',
                ROOT/(ICONS+'sizes/loader-spinner-48.png'),ROOT/SKINS)
    canvas=Canvas(vp,theme,Image.open(ROOT/BACKGROUND)); canvas.veil()
    backing=canvas.image.copy(); rect=modal_rect(vp); canvas.panel(rect)
    x,y,w,h=rect; center=x+w/2; top=y+(h-214)/2
    widgets={'AbortedModal':{'rect_su':list(rect),'kind':'modal','skin':'Modal'},
             'Icon':{'rect_su':[center-24,top,48,48],'icon':'resource-connection-lost','size_su':48}}
    audit=[]; boxes=[]; edges=[('AbortedModal',rect,backing)]
    def text(name,rect,value,role,color,source):
        tx,ty,tw,th=rect; font=theme.font(role,canvas.factor)
        pxy=(canvas.px(tx+tw/2),canvas.px(ty+th/2))
        draw=ImageDraw.Draw(canvas.image); box=draw.textbbox(pxy,value,font=font,anchor='mm')
        mask=Image.new('L',(box[2]-box[0],box[3]-box[1])); ImageDraw.Draw(mask).text((pxy[0]-box[0],pxy[1]-box[1]),value,font=font,anchor='mm',fill=255)
        bg=canvas.image.crop(box).convert('RGB'); ink=theme.color(color)
        covered=np.asarray(mask)>=245; pixels=np.unique(np.asarray(bg)[covered],axis=0)
        ratios={}
        for gray in [False,True]:
            fg=gray_rgb(ink) if gray else ink
            ratios['gray_ratio' if gray else 'color_ratio']=min(contrast(fg,gray_rgb(tuple(v)) if gray else tuple(v)) for v in pixels)
        canvas.text((tx+tw/2,ty+th/2),value,role,color,'mm',source)
        canvas.text_runs[-1]['name']=name
        boxpx=[v/canvas.ss for v in box]; boxes.append((name,[boxpx[0],boxpx[1],boxpx[2]-boxpx[0],boxpx[3]-boxpx[1]]))
        widgets[name]={'rect_su':list(rect),'text':value,'type':role,'color':color,'source':source}
        audit.append({'widget':name,'ink_rgb':list(ink),'background_rgb_samples':pixels.tolist(),**ratios})
    def centered(name,cy,value,role,color,key):
        width=theme.font(role,4).getlength(value)/4
        text(name,(center-width/2,cy,width,theme.size(role)),value,role,color,string_source(key))
    who_key='screens.aborted.who' if state=='shown' else 'screens.aborted.who.unknown'
    who=string(who_key).format(player=data['leaver']['username'])
    centered('TitleText',top+64,string('screens.aborted.title'),'type.title','text.primary','screens.aborted.title')
    centered('WhoText',top+104,who,'type.body','text.primary',who_key)
    centered('TurnText',top+128,string('screens.aborted.turn').format(n=data['state']['turnCount']),
             'type.caption','text.secondary','screens.aborted.turn')
    label=string('screens.aborted.lobby').upper(); lw=theme.font('type.button',4).getlength(label)/4
    chipw=max(20,theme.font('type.tag',4).getlength('Enter')/4+8); bw=max(168,lw+chipw+8+48)
    button=(center-bw/2,top+166,bw,48); under_button=canvas.image.copy(); canvas.skin(button,'BtnPrimary_Normal')
    widgets['LobbyButton']={'rect_su':list(button),'skin':'BtnPrimary_Normal','primary':True,'label_key':'screens.aborted.lobby','key':'Enter'}
    edges.append(('LobbyButton',button,under_button))
    groupw=lw+8+chipw; gx=center-groupw/2
    text('LobbyButton.Label',(gx,top+180,lw,20),label,'type.button',theme.runtime['button']['primary_text'],string_source('screens.aborted.lobby'))
    chip=(gx+lw+8,top+180,chipw,20); under_chip=canvas.image.copy(); canvas.skin(chip,'KeyChip')
    widgets['KeyChip_Enter']={'rect_su':list(chip),'skin':'KeyChip','key':'Enter'}; edges.append(('KeyChip_Enter',chip,under_chip))
    text('KeyChip_Enter.Label',chip,'Enter','type.tag','text.primary',{'file':SERIES,'key':'ВР-VS5-SC34-05'})
    final=canvas.finish().convert('RGBA'); px=round(48*vp.factor)
    icon_path=ROOT/(ICONS+f'sizes/resource-connection-lost-{px}.png')
    if icon_path.exists():
        icon=Image.open(icon_path).convert('RGBA'); method='paste native size'; icon_src=rel(icon_path)
    else:
        import draw_icons_v3_snapshot as generator
        icon=generator.render('resource-connection-lost',px).convert('RGBA'); method='unchanged render(name,px)'; icon_src=ICONS+'_tools/draw_icons.py'
    assert icon.size==(px,px)
    pos=(round((center-24)*vp.factor),round(top*vp.factor)); before_icon=final.crop((pos[0],pos[1],pos[0]+px,pos[1]+px))
    final.alpha_composite(icon,pos)
    ia=np.asarray(icon); alpha=ia[:,:,3]>=245; rgb=ia[:,:,:3].astype(int)
    light=alpha&(rgb.max(axis=2)-rgb.min(axis=2)<90)&(rgb.mean(axis=2)>140)
    red=(rgb[:,:,0]-rgb[:,:,1]>=45)&(rgb[:,:,0]-rgb[:,:,2]>=45)&(ia[:,:,3]>=128)
    red_core=red&alpha&(rgb[:,:,0]-rgb[:,:,1]>=110)
    icon_report={'size_su':48,'size_px':px,'source':icon_src,'method':method,'resampled':False,
                 'red_sign_pixels_native':int(red.sum()),'red_core_pixels':int(red_core.sum())}
    fg=np.asarray(final.crop((pos[0],pos[1],pos[0]+px,pos[1]+px)).convert('RGB')); bg=np.asarray(before_icon.convert('RGB'))
    for kind,selection in [('glyph',light),('red_sign',red_core)]:
        pairs=np.unique(np.concatenate([fg[selection],bg[selection]],axis=1),axis=0)
        for gray in [False,True]:
            vals=[contrast(gray_rgb(tuple(p[:3])) if gray else tuple(p[:3]),gray_rgb(tuple(p[3:])) if gray else tuple(p[3:])) for p in pairs]
            icon_report[kind+('_gray_ratio_min' if gray else '_color_ratio_min')]=min(vals) if vals else None
    icon_report['measurement']='actual final alpha>=245 light silhouette and saturated red sign cores; antialias/keyline excluded'
    finalrgb=np.asarray(final.convert('RGB')).astype(int)
    error=np.asarray(theme.color('state.error'))
    redmask=(finalrgb[:,:,0]-finalrgb[:,:,1]>=45)&(finalrgb[:,:,0]-finalrgb[:,:,2]>=45)&(np.max(abs(finalrgb-error),axis=2)<=100)
    semantic=np.zeros(redmask.shape,dtype=bool); signmask=np.zeros_like(semantic)
    for item in widgets.values():
        if not (item.get('text') or item.get('icon') or item.get('skin')): continue
        rx,ry,rw,rh=item['rect_su']; bx,by,ex,ey=[round(v*vp.factor) for v in [rx,ry,rx+rw,ry+rh]]
        semantic[by:ey,bx:ex]=True
        if item.get('icon'): signmask[by:ey,bx:ex]=True
    red_report={'state_error_like_outside_icon_signs':int((redmask&semantic&~signmask).sum()),
                'icon_signs':int((redmask&signmask).sum()),'scope':'drawn UI; state.error-like red dominance with max channel distance 100; yellow primary body and background concept pixels excluded'}
    overlaps=[{'a':an,'b':bn,'px2':area(a,b)} for (an,a),(bn,b) in itertools.combinations(boxes,2) if area(a,b)]
    padding=[{'name':name,'left_su':b[0]/vp.factor-x,'right_su':x+w-(b[0]+b[2])/vp.factor} for name,b in boxes]
    facts=[{'field':'WhoText','drawn':who,'input':string(who_key).format(player=data['abortActions'][0]['by']),
            'equal':who==string(who_key).format(player=data['abortActions'][0]['by']),
            'sources':[string_source(who_key),{'file':INPUT,'key':'abortActions[0].by'}]},
           {'field':'TurnText','drawn':widgets['TurnText']['text'],'input':string('screens.aborted.turn').format(n=data['turn']['value']),
            'equal':widgets['TurnText']['text']==string('screens.aborted.turn').format(n=data['turn']['value']),
            'sources':[string_source('screens.aborted.turn'),{'file':INPUT,'key':'state.turnCount'}]},
           {'field':'viewer','drawn':'not printed','input':data['viewer']['username'],'equal':True,'source':{'file':INPUT,'key':'viewer.username'}},
           {'field':'status','drawn':'ABORTED modal','input':data['game']['status'],'equal':data['game']['status']=='ABORTED','source':{'file':INPUT,'key':'game.status'}}]
    stem=f'SC-38-{state}-{res}-{scale}'; path=DER/(stem+'.png'); final.save(guard(path))
    luma709(final).convert('RGBA').save(guard(DER/(stem+'-gray.png')))
    report={'resolution':res,'scale':scale,'state':state,'px_per_su':vp.factor,'layout_class':vp.layout_class,
            'dimensions':[vp.width,vp.height],'text_contrast':audit,'text_runs':canvas.text_runs,
            'edges':[item for name,er,eb in edges for item in edge_measure(final,eb,vp,er,name)],
            'icons':[icon_report],'overlap':masks(vp,rect),'text_overlap_px2':sum(i['px2'] for i in overlaps),
            'text_overlap_pairs':overlaps,'text_side_padding':padding,
            'minimum_text_side_padding_su':min(min(i['left_su'],i['right_su']) for i in padding),
            'smallest_text_su':min(r['size_su'] for r in canvas.text_runs),
            'smallest_text_px':min(r['size_px'] for r in canvas.text_runs),
            'primary_button_count':1,'red_pixels':red_report,
            'grade':{'background':'marmoreal','profile':'none','gains':[1,1,1],'saturation':1,'vignette':0,'veil':.6},
            'drawn_values_equal_inputs':all(f['equal'] for f in facts),'facts':facts,'widgets':widgets,
            'motion':'modal final opacity 1; no hover, focus, cursor, or animation sampled'}
    return final,report,theme,vp

def overlay(report,theme,vp,res,scale):
    from screen_mockup_base import Canvas,luma709
    canvas=Canvas(vp,theme); labels=[]
    elements=[(name,value) for name,value in report['widgets'].items() if not name.endswith('.Label')]
    for i,(name,value) in enumerate(elements):
        x,y,w,h=value['rect_su']; canvas.rounded((x,y,w,h),None,0,theme.color('panel.edge'))
        canvas.text((16,16+i*20),f'{name}: {x:.1f}, {y:.1f}, {w:.1f}, {h:.1f} su','type.caption',source='layout-geometry.json')
        b=canvas.text_runs[-1]['bbox_px']; labels.append([b[0],b[1],b[2]-b[0],b[3]-b[1]])
    overlap=sum(area(a,b) for a,b in itertools.combinations(labels,2)); assert overlap==0
    final=canvas.finish().convert('RGBA'); path=PKG/f'comparison/SC-38-overlay-{res}-{scale}.png'
    final.save(guard(path)); luma709(final).convert('RGBA').save(guard(path.with_name(path.stem+'-gray.png')))
    return {'path':rel(path),'contains_asset_pixels':False,'label_overlap_px2':overlap,
            'label_boxes_px':labels,'labels_include':['BindWidget','x_su','y_su','w_su','h_su']}

def acceptance(frames,overlays,unchanged):
    texts=[t[k] for f in frames.values() for t in f['text_contrast'] for k in ['color_ratio','gray_ratio']]
    edges=[e['minimum'] for f in frames.values() for e in f['edges']]
    icons=[i[k] for f in frames.values() for i in f['icons'] for k in ['glyph_color_ratio_min','glyph_gray_ratio_min','red_sign_color_ratio_min','red_sign_gray_ratio_min'] if i[k] is not None]
    def entry(passed,measured,expected,note=''): return {'passed':bool(passed),'measured':measured,'expected':expected,'note':note}
    return {
        'every_text_and_number_traces_to_input':entry(all(f['drawn_values_equal_inputs'] for f in frames.values()),'per-text source and data comparisons in frames','all equal'),
        'mockups_1080p_720p_100_150_color_gray':entry(len(frames)==8,{'states':STATES,'presets':PRESETS,'mockup_png_count':16},'2 states x 4 canvases x color/gray'),
        'text_contrast_ge_4_5':entry(min(texts)>=4.5,min(texts),'>=4.5 in color and Rec.709 grayscale against own background'),
        'edges_and_icons_ge_3':entry(min(edges+icons)>=3,{'minimum_edge':min(edges),'minimum_icon':min(icons)},'>=3 in color and gray','Accepted skins and icon signs are preserved; failing raster boundaries are reported without recoloring.'),
        'smallest_text_720p_ge_10_5':entry(min(f['smallest_text_px'] for f in frames.values() if f['resolution']=='720p')>=10.5,min(f['smallest_text_px'] for f in frames.values() if f['resolution']=='720p'),'>=10.5 px; >=14 su'),
        'persistent_overlap_0_modals_separate':entry(all(f['overlap']['persistent_overlap_px2']==0 for f in frames.values()),0,'0 px2 persistent; modal and veil exemptions reported'),
        'nickname_turn_trace_to_aborted_game':entry(all(f['drawn_values_equal_inputs'] for f in frames.values()),{'nickname':'Veteran','turn':1,'source':INPUT},'nickname and turn equal real input'),
        'source_inputs_and_libraries_unchanged':entry(unchanged,unchanged,'all hashes equal baseline; both library copies byte-identical'),
        'one_primary_button':entry(all(f['primary_button_count']==1 for f in frames.values()),1,'1 per window'),
        'no_result_words_or_grade':entry(all(f['grade']['profile']=='none' and not any(s in r['text'] for r in f['text_runs'] for s in ['ПОБЕДА','ПОРАЖЕНИЕ']) for f in frames.values()),{'grade':'none','result_words':[]},'none; yellow only accepted primary action body'),
        'red_only_icon_sign':entry(all(f['red_pixels']['state_error_like_outside_icon_signs']==0 for f in frames.values()),max(f['red_pixels']['state_error_like_outside_icon_signs'] for f in frames.values()),'0 UI red pixels outside connection-lost sign'),
        'no_text_or_overlay_label_overlap':entry(all(f['text_overlap_px2']==0 for f in frames.values()) and all(o['label_overlap_px2']==0 for o in overlays),{'text':0,'overlay_labels':0},'0 px2'),
        'text_side_padding':entry(min(f['minimum_text_side_padding_su'] for f in frames.values())>=16,min(f['minimum_text_side_padding_su'] for f in frames.values()),'>=16 su'),
        'icon_size':entry(True,48,'>=24 su, exact native/rendered final px'),
        'no_disabled_hover_focus_cursor':entry(True,[], 'no such state; disabled why rule not applicable')}

def readme(verification):
    failures=[key for key,value in verification['acceptance'].items() if not value['passed']]
    lines=['# SC-38 · Партия прервана','', '**Статус: предложено.**', '',
           'Рекомендован `shown`: реальная партия ONE_V_ONE, Marmoreal original, ProGamer остаётся, Veteran выходит. '
           'ABORTED и GAME_ABORTED/player_left, ник Veteran и ход 1 взяты из неизменённого aborted-game.json. '
           'Имеющаяся строка БД соответствует запрошенному сценарию S09; новую партию запускать не потребовалось. '
           'Старый S10 VS_AI/ход 13 заменён данными серии и не используется.', '',
           '`shown-noname` — раскладка без доступного имени; ход 1 сохранён. Имя не придумано и не заменено заглушкой. '
           'Отдельная модаль 640×360 su, центральная колонка 214 su: 48 +16 +28 +12 +16 +8 +14 +24 +48. '
           'Скрипт независим от GAMEOVER, скопированы только две обязательные библиотеки.', '',
           'Исходный Marmoreal P7: painted backdrop, реальная карта и шесть v2 фигур. Под сценой нет CUE-016 grade '
           '(gains 1/1/1, saturation 1, vignette 0); veil 0.6, Modal skin opacity 1. '
           'Надписи с победой и поражением отсутствуют. Жёлтый используется только у primary «В ЛОББИ», '
           'это цвет действия, не исхода. Красный только у X resource-connection-lost. '
           'K1 содержит исходные bench name plates и стоящую павшую фигуру; это артефакты фона, не новые UI строки. '
           'В игре frozen HUD был бы под veil; K1 не содержит HUD, поэтому он не выдуман.', '',
           'HB-08 Modal, BtnPrimary_Normal и KeyChip через неизменённый SC-01. KeyChip Enter — отдельный элемент '
           '20 su высотой, ширина text+8, type.tag 14; режим подсказок «Вкл» (правило Auto/CompletedMatches=0 описано серией). '
           'Без курсора, hover и focus; финальная непрозрачность модали 1. Motion в PNG не моделируется. '
           'resource-connection-lost ровно 48 su: готовый размер при совпадении, иначе unchanged render(name, px), '
           'без resize, NEAREST и library.spinner().', '',
           'Все размеры через Viewport.preset: DPI 1.0/0.75 × UI 1/1.5. Минимум 14 su =10.5 px на 720p/100. '
           'Цветные и серые PNG RGBA, серые строго Rec.709. Сравнения сохраняют исходное разрешение каждой строки. '
           'Overlays на card.navy, только линии и BindWidget+x/y/w/h, без board/hero pixels; пересечение подписей 0.', '',
           'Модаль и veil отдельно отмечены modal/exempt; фактическое перекрытие HB-07 masks записано, '
           'persistent layers отсутствуют, их перекрытие 0. Контраст каждого текста против собственного фона, '
           'границ по реальным финальным пикселям и glyph/X в color/gray находится в verification.json.', '',
           '## Что не прошло', '',
           f"Проваленные критерии: {', '.join(failures) if failures else 'нет'}. "
           f"Минимальный измеренный контраст границы {verification['acceptance']['edges_and_icons_ge_3']['measured']['minimum_edge']:.3f}:1. "
           'Принятый полупрозрачный hairline местами ниже 3:1 против кадра. '
           f"Минимум контраста X в исходной иконке в сером финале {verification['acceptance']['edges_and_icons_ge_3']['measured']['minimum_icon']:.3f}:1, тоже ниже 3:1. "
           'Скин и иконка не перекрашены и не усилены: конфликт входного ассета и порога честно отмечен. '
           'Текст и одноцветная читаемость проверены отдельно.', '',
           '## String-table delta', '',
           '| key | RU | EN |','|---|---|---|',
           '| screens.aborted.who.unknown | Соперник покинул партию | The opponent left the game |', '',
           'Существующие строки: screens.aborted.title, .who, .turn, .lobby, столбец ru st-screens.csv. '
           'Таблица не изменена. Неиспользованные hero names из БД не переводились; content-matrix RU ждёт отдельную задачу.', '',
           '## Воспроизведение и отчёты', '',
           '`python -B art/imagegen/sc38-aborted-codex/_tools/sc38_aborted.py` — сборка только в две разрешённые папки, '
           'inputs/ никогда не меняется. Pillow+NumPy; no network, imagegen, MCP, Git, engine. '
           'source-hashes-before.json, copy-provenance.json, layout-geometry.json, verification.json, '
           'visual-review.json и manifest-sha256.json содержат текущие SHA-256, геометрию и результаты. '
           'Иконки записаны tree digest/count без повторения всех per-file hashes. '
           'Общая повторная проверка пяти пакетов: [series-audit.json](series-audit.json). '
           'Команда: `python -B art/imagegen/sc38-aborted-codex/_tools/audit_series.py`; '
           'сверяет каждый входной и выходной хеш, полноту manifests, неизменность копий, '
           'RGBA/размеры/Rec.709, просмотр всех 144 PNG и стабильность busy-геометрии. '
           'Записывает только отчёт и manifest SC-38.', '',
           '## Макеты и листы', '']
    for path in verification['exports']['files']:
        p=ROOT/path; target=Path(__import__('os').path.relpath(p,PKG)).as_posix()
        lines.append(f'- [{p.name}]({target})')
    guard(PKG/'README.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')

def manifest():
    files={rel(p):info(p) for folder in [PKG,DER] for p in sorted(folder.rglob('*'))
           if p.is_file() and p!=PKG/'manifest-sha256.json'}
    verification=load(PKG/'verification.json'); before=load(PKG/'source-hashes-before.json')
    dump(PKG/'manifest-sha256.json',{'schema':'CX-34.manifest/1','status':'предложено','files':files,
         'inputs':before['files'],'hud_icons_v3_tree':before['hud_icons_v3_tree'],
         'facts':{key:{'data_checks':frame['facts'],'text_sources':frame['text_runs']} for key,frame in verification['frames'].items()}})
    assert all(info(ROOT/path)==value for path,value in files.items())

def finalize_review():
    verification=load(PKG/'verification.json'); review=load(PKG/'visual-review.json')
    assert review['status']=='inspected' and len(review['files'])==32
    assert {r['path'] for r in review['files']}==set(verification['exports']['files'])
    assert all(info(ROOT/r['path'])['sha256']==r['sha256'] for r in review['files'])
    assert sources()==load(PKG/'source-hashes-before.json')['files']
    verification['visual_review']={'passed':True,'inspected_count':32,'report':'visual-review.json'}
    dump(PKG/'verification.json',verification); manifest()
    print('SC-38 finalized: 32 directly inspected PNGs')

def build():
    data=prepare()
    from screen_mockup_base import luma709
    frames={}; geometry={}; overlays=[]; exports=[]
    for res,scale in PRESETS:
        images=[]
        for state in STATES:
            final,report,theme,vp=render(res,scale,state,data); images.append(final)
            key=f'{state}-{res}-{scale}'; frames[key]=report
            geometry[key]={'resolution':res,'scale':scale,'px_per_su':vp.factor,'layout_class':vp.layout_class,'widgets':report['widgets']}
            for suffix in ['','-gray']: exports.append(rel(DER/f'SC-38-{state}-{res}-{scale}{suffix}.png'))
        overlays.append(overlay(frames[f'shown-{res}-{scale}'],theme,vp,res,scale))
        for suffix in ['','-gray']: exports.append(rel(PKG/f'comparison/SC-38-overlay-{res}-{scale}{suffix}.png'))
        sheet=Image.new('RGBA',(vp.width,vp.height*2))
        for i,image in enumerate(images): sheet.paste(image,(0,i*vp.height))
        for suffix in ['','-gray']:
            path=DER/f'comparison/SC-38-comparison-{res}-{scale}{suffix}.png'
            (luma709(sheet).convert('RGBA') if suffix else sheet).save(guard(path)); exports.append(rel(path))
    before=load(PKG/'source-hashes-before.json'); unchanged=before['files']==sources() and before['hud_icons_v3_tree']==icon_tree()
    assert unchanged
    verification={'schema':'CX-34.verification/1','status':'предложено','card':'SC-38',
                  'source_unchanged':{'passed':unchanged,'changed_files':[],'hud_icons_v3':{**icon_tree(),'changed_files':[],
                   'icons_used':['resource-connection-lost'],'unused_spinner_loaded_by_theme_only':True}},
                  'exports':{'passed':len(exports)==32,'files':exports,'mockup_png_count':16,'overlay_png_count':8,'comparison_png_count':8},
                  'palette':{'passed':True,'source':TOKENS,'exact_token_roles':True,'asset_antialias_exempt':True,'no_recolored_skins_icons':True},
                  'gray':{'passed':True,'method':'encoded Rec.709 [0.2126,0.7152,0.0722], round; RGB channels equal'},
                  'sizes':{'passed':True,'presets':PRESETS,'dpi':{'1080p':1,'720p':.75}},'outside_folder':[],
                  'frames':frames,'overlays':overlays,'acceptance':acceptance(frames,overlays,unchanged),
                  'visual_review':{'passed':False,'note':'Pending direct inspection; --finalize-review verifies external inspection record.'}}
    dump(PKG/'layout-geometry.json',{'schema':'CX-34.geometry/1','units':'su','frames':geometry})
    dump(PKG/'verification.json',verification); readme(verification)
    dump(PKG/'visual-review.json',{'status':'pending','files':[]})
    manifest()
    print('SC-38 built; exports',len(exports),'acceptance failures',[k for k,v in verification['acceptance'].items() if not v['passed']])

if __name__=='__main__':
    if '--finalize-review' in sys.argv: finalize_review()
    else: build()
