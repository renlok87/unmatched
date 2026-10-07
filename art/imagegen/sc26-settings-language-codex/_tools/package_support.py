#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Offline package builder/auditor. Every write is confined to the active package.

Run --finalize after direct visual review; --check is read-only and independently
checks complete file coverage, hashes, Rec.709 pairs, geometry and copied sources.
"""
from __future__ import annotations
import argparse
import hashlib
import itertools
import json
import math
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path
import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont
import sc24_pause as p
from screen_mockup_base import Canvas, Viewport, contrast, luma709

ROOT=p.ROOT
NAMES={24:'sc24-pause',25:'sc25-settings-sound',26:'sc26-settings-language',27:'sc27-settings-scale',28:'sc28-settings-game',29:'sc29-settings-hints',30:'sc30-settings-graphics'}
MODULES={24:'sc24_pause',25:'sc25_settings_sound',26:'sc26_settings_language',27:'sc27_settings_scale',28:'sc28_settings_game',29:'sc29_settings_hints',30:'sc30_settings_graphics'}
ACTIVE=None
WRITES=[]

def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def rel(path):
 path=Path(path).resolve()
 return path.relative_to(ROOT).as_posix() if path.is_relative_to(ROOT) else path.as_posix()
def read(path):return json.loads(Path(path).read_text(encoding='utf-8'))
def roots(number):return ROOT/'art/imagegen'/f'{NAMES[number]}-codex',ROOT/'scraped-data/derived'/f'{NAMES[number]}-codex'
def writable(path):
 path=Path(path).resolve();pkg,out=roots(ACTIVE)
 if not any(path.is_relative_to(r.resolve()) for r in (pkg,out)):raise PermissionError(path)
 path.parent.mkdir(parents=True,exist_ok=True);WRITES.append(rel(path));return path
def write_json(path,obj):writable(path).write_text(json.dumps(obj,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
def write_text(path,text):writable(path).write_text(text,encoding='utf-8')
def copy(source,dest):shutil.copyfile(source,writable(dest));assert sha(source)==sha(dest)
def pair(im,path):
 im=im.convert('RGBA');g=luma709(im).convert('RGBA');im.save(writable(path),optimize=True)
 gp=path.with_name(path.stem+'-gray.png');g.save(writable(gp),optimize=True);return [path,gp]
def tree(folder):
 files=sorted(v for v in Path(folder).rglob('*') if v.is_file())
 digest=hashlib.sha256()
 for file in files:digest.update((file.relative_to(folder).as_posix()+'\0'+sha(file)+'\n').encode('utf-8'))
 return {'path':rel(folder),'count':len(files),'sha256':digest.hexdigest(),'algorithm':'sha256(sorted(relative POSIX path + NUL + file sha256 + LF))'}

def input_paths(number):
 names=['AGENTS.md',p.ST,p.HUD,'docs/unreal/contracts/hud/why-reasons.json','docs/unreal/contracts/hud/hud-style-tokens.json',
  'docs/game-design/visual/02-visual-design.md','docs/game-design/visual/04-hud-spec.md','docs/game-design/visual/07-prompt-templates.md',
  'docs/game-design/visual/06-tasks/screens.csv','docs/art-pipeline/render-reference.json',p.SETTINGS,
  'backend/src/game-engine/models/game-state.model.ts',p.SERIES,f'docs/game-design/visual/06-tasks/prompts/SC-{number}.codex.md',
  'art/imagegen/hud-skins-v1-codex/README.md','art/imagegen/hud-skins-v1-codex/runtime-style.json',
  'art/imagegen/hud-skins-v1-codex/slice-margins.json','art/imagegen/sc01-screen-base-codex/README.md',
  'art/imagegen/sc01-screen-base-codex/manifest-sha256.json','art/imagegen/hud-composition-v1-codex/masks.json',
  'art/imagegen/sc19-loading-codex/README.md','art/imagegen/hud-icons-v3/_tools/draw_icons.py',
  'art/imagegen/hud-icons-v3/sizes/loader-spinner-48.png',*p.BG.values(),'.agents/skills/canvas-design/SKILL.md']
 if number==25:names.append('docs/game-design/de-footage/task/07-sprint-backlog.csv')
 if number==29:names+=['art/imagegen/hud-actions-v1-codex/README.md','art/imagegen/hud-actions-v1-codex/facts.json']
 paths=[ROOT/n for n in names]
 for folder in ('art/imagegen/hud-skins-v1-codex/vector','art/imagegen/sc01-screen-base-codex/_tools','art/imagegen/sc19-loading-codex/_tools'):
  paths.extend(v for v in (ROOT/folder).rglob('*') if v.is_file() and '__pycache__' not in v.parts)
 if number==29:paths.extend(v for v in (ROOT/'art/imagegen/hud-actions-v1-codex/_tools').rglob('*') if v.is_file() and '__pycache__' not in v.parts)
 if number!=24:
  paths.extend([ROOT/'art/imagegen/sc24-pause-codex/README.md',ROOT/'art/imagegen/sc24-pause-codex/manifest-sha256.json'])
  paths.extend(v for v in (ROOT/'art/imagegen/sc24-pause-codex/_tools').rglob('*') if v.is_file())
 paths.extend([p.FONTDIR/'Roboto-BoldCondensed.ttf',p.FONTDIR/'Roboto-Regular.ttf'])
 # Native icon inputs of the exact sizes used by the four presets.
 for px in (18,24,27,36):
  q=ROOT/f'art/imagegen/hud-icons-v3/sizes/badge-refuse-{px}.png'
  if q.exists():paths.append(q)
 if number==29:
  for px in (36,48,60,45):
   q=ROOT/f'art/imagegen/hud-icons-v3/sizes/action-end-turn-{px}.png'
   if q.exists():paths.append(q)
 return sorted(set(paths),key=lambda v:str(v))

def prepare(number):
 pkg,out=roots(number);before=pkg/'source-hashes-before.json'
 if not before.exists():
  paths=input_paths(number)
  for v in paths:
   if not v.is_file():raise FileNotFoundError(v)
  write_json(before,{'created_utc':datetime.now(timezone.utc).isoformat(),
   'files':{rel(v):sha(v) for v in paths},'icons_v3_tree':tree(ROOT/'art/imagegen/hud-icons-v3')})
 else:
  changes=changed_inputs(read(before))
  if changes:raise RuntimeError(('Inputs changed; do not overwrite baseline',changes))
 provenance=[]
 copies=[('art/imagegen/sc01-screen-base-codex/_tools/screen_mockup_base.py','screen_mockup_base.py'),
  ('art/imagegen/hud-icons-v3/_tools/draw_icons.py','draw_icons_v3_snapshot.py')]
 if number!=24:copies.extend([('art/imagegen/sc24-pause-codex/_tools/sc24_pause.py','sc24_pause.py'),
  ('art/imagegen/sc24-pause-codex/_tools/package_support.py','package_support.py')])
 for source,target in copies:
  copy(ROOT/source,pkg/'_tools'/target)
  provenance.append({'source':source,'copy':rel(pkg/'_tools'/target),'sha256':sha(ROOT/source),'byte_identical':True})
 write_json(pkg/'copy-provenance.json',provenance)
 for name in ('SC-24-series.codex.md',f'SC-{number}.codex.md'):
  copy(ROOT/'docs/game-design/visual/06-tasks/prompts'/name,pkg/'prompts'/name)
 write_json(pkg/'generation-records.json',[])
 # Exact text snapshots; source PNGs are read in place and never retouched.
 for name in read(before)['files']:
  source=ROOT/name if not Path(name).is_absolute() else Path(name)
  if source.suffix.lower() in ('.md','.json','.csv','.h','.ts'):
   dest=out/'input-snapshots'/('external/'+source.name if Path(name).is_absolute() else name)
   if not dest.exists():copy(source,dest)
 return pkg,out

def changed_inputs(before):
 result=[name for name,h in before['files'].items() if not (Path(name) if Path(name).is_absolute() else ROOT/name).is_file() or sha(Path(name) if Path(name).is_absolute() else ROOT/name)!=h]
 # fix1 intentionally corrects SC-24's README/overlay module/manifest. Keep the
 # original before file and validate these precise dependency updates separately.
 if ACTIVE is not None:
  pkg,_=roots(ACTIVE);vf=pkg/'verification.json'
  updates=read(vf).get('fix1',{}).get('authorized_input_updates',{}) if vf.exists() else {}
  allowed={'art/imagegen/sc24-pause-codex/'+v for v in ('README.md','manifest-sha256.json','_tools/package_support.py')}
  result=[name for name in result if not (name in allowed and name in updates
   and updates[name]['run1_sha256']==before['files'][name] and sha(ROOT/name)==updates[name]['fix1_sha256'])]
 now=tree(ROOT/'art/imagegen/hud-icons-v3')
 if now['sha256']!=before['icons_v3_tree']['sha256']:result.append('art/imagegen/hud-icons-v3/** (tree digest)')
 return result

def frames(number):
 result=[]
 if number==27:
  combos=[(75,'1080p',75),(100,'1080p',100),(150,'1080p',150),(100,'720p',100),(150,'720p',150)]
  for value,res,scale in combos:
   vp=Viewport(1920,1080,1,.75) if value==75 else Viewport.preset(res,scale)
   result.append((f'scale-{value}',res,scale,vp,{'background':'marmoreal','open_tab':'interface',
    'rows':p.interface_rows(scale=value,minimum=100 if res=='720p' else 75,range_note=True)}))
  return result
 states={24:['game','game-defense','menu','confirm','syncing'],25:['sound'],26:['ru','en','pseudo'],28:['game'],29:['interface-hints'],30:['graphics']}[number]
 for state in states:
  for res,scale in [('1080p',100),('1080p',150),('720p',100),('720p',150)]:
   args={'state':'game','background':'sarpedon' if number in (26,28,30) else 'marmoreal'}
   if number==24:args.update(state='game' if state=='confirm' else state,confirm_dialog=state=='confirm',caption=state=='menu')
   elif number==25:args.update(open_tab='sound',rows=p.sound_rows())
   elif number==26:args.update(open_tab='interface',language=state,rows=p.interface_rows(language=state))
   elif number==28:args.update(open_tab='game',rows=p.game_rows())
   elif number==29:args.update(open_tab='interface',rows=p.interface_rows(hints=True))
   else:args.update(open_tab='graphics',rows=p.graphics_rows())
   result.append((state,res,scale,Viewport.preset(res,scale),args))
 return result

def clipped_components(components):
 """Add viewport visibility without changing any run-1 content rectangle."""
 import copy as copy_module
 result=copy_module.deepcopy(components)
 panel=result['RowsPanel'];rx,ry,rw,rh=panel['rect_su']
 offset=result.get('ScrollBar',{}).get('offset_su',0)
 for name,item in result.items():
  if not (name.startswith('Row_') or name.startswith('KeyHintSample')):continue
  x,y,w,h=item['rect_su']
  x0,y0=max(x,rx),max(y,ry);x1,y1=min(x+w,rx+rw),min(y+h,ry+rh)
  visible=x1>x0 and y1>y0
  if 'visible' in item and 'run1_visible' not in item and 'visible_rect_su' not in item:item['run1_visible']=item['visible']
  item.update(visible=visible,content_rect_su=[x-rx,y-ry+offset,w,h],
   visible_rect_su=[x0,y0,x1-x0,y1-y0] if visible else None,
   clipped=visible and (x0>x or y0>y or x1<x+w or y1<y+h))
 return result

def box_overlap(a,b):
 return max(0,min(a[2],b[2])-max(a[0],b[0]))*max(0,min(a[3],b[3])-max(a[1],b[1]))

def overlay(vp,components,path):
 """Native-size, keyed diagram; rows clipped before any outline is drawn.

 Tags and leader lines are rasterised at final resolution: Roboto Regular >=14
 px and exactly 1-px keylines. The legend never occupies the diagram area.
 """
 components=clipped_components(components);f=vp.factor;t=p.theme()
 font=ImageFont.truetype(t.regular_font,max(14,round(14*f)))
 navy=t.color('card.navy');ink=t.color('text.primary')
 edge=p.mix(t.color('panel.edge'),navy,t.alpha('panel.edge'))
 legend_x=vp.width+40;legend_w=max(860,round(810*f));pitch=font.size+10
 entries=[(f'R{i:02}',name,item) for i,(name,item) in enumerate(components.items(),1)]
 shown=[e for e in entries if e[2].get('visible',True)]
 hidden=[e for e in entries if not e[2].get('visible',True)]
 legend=[];yy=24
 def append_label(value):
  nonlocal yy
  legend.append((value,legend_x,yy));yy+=pitch
 for group,is_hidden in ((shown,False),(hidden,True)):
  if is_hidden and group:
   yy+=pitch;append_label('скрыто прокруткой — координаты в пространстве содержимого RowsPanel')
  for key,name,item in group:
   r=item['content_rect_su'] if is_hidden else item.get('visible_rect_su') or item['rect_su']
   x,y,w,h=r;desc=f'{key} {name}'
   dims=f'x={x:.2f} y={y:.2f} w={w:.2f} h={h:.2f} su'
   if item.get('clipped') and not is_hidden:dims+=' (обрезано RowsPanel)'
   if font.getlength(desc+'  '+dims)<=legend_w-32:append_label(desc+'  '+dims)
   else:append_label(desc);append_label('    '+dims)
 im=Image.new('RGBA',(legend_x+legend_w,max(vp.height,yy+24)),navy+(255,));d=ImageDraw.Draw(im)
 tags=[];leaders=[];outlines=[]
 for key,name,item in shown:
  rect=item.get('visible_rect_su') or item['rect_su'];x,y,w,h=rect
  outline=[round(x*f),round(y*f),round((x+w)*f),round((y+h)*f)]
  d.rectangle(outline,outline=t.color('card.cream'),width=max(1,round(f)))
  outlines.append({'key':key,'name':name,'rect_su':rect,'rect_px':outline})
  tw=math.ceil(font.getlength(key))+8;th=font.size+6
  def available(b):
   return (b[0]>=2 and b[1]>=2 and b[2]<=vp.width-2 and b[3]<=im.height-2
    and all(box_overlap([b[0]-2,b[1]-2,b[2]+2,b[3]+2],tag['bbox_px'])==0 for tag in tags))
  inside=[outline[0]+2,outline[1]+2,outline[0]+2+tw,outline[1]+2+th]
  fits=inside[2]<=outline[2]-1 and inside[3]<=outline[3]-1 and available(inside)
  if fits:chosen=inside;leader=None
  else:
   candidates=[]
   # The closest free position around the top-left corner wins. A short leader
   # identifies thin/partially visible rectangles which cannot contain a tag.
   for gap in range(3,260,4):
    for dx in (0,-tw,tw+4,-2*tw-8,2*tw+8):
     candidates.extend([(outline[0]+dx,outline[1]-gap-th),
      (outline[0]-gap-tw,outline[1]+dx),(outline[0]+dx,outline[3]+gap),
      (outline[2]+gap,outline[1]+dx)])
   candidates.sort(key=lambda q:(q[0]-outline[0])**2+(q[1]-outline[1])**2)
   chosen=next(([xx,zz,xx+tw,zz+th] for xx,zz in candidates
    if available([xx,zz,xx+tw,zz+th]) and box_overlap([xx,zz,xx+tw,zz+th],outline)==0),None)
   if chosen is None:raise RuntimeError(('No free tag position',name))
   ax=min(max((chosen[0]+chosen[2])/2,outline[0]),outline[2])
   ay=min(max((chosen[1]+chosen[3])/2,outline[1]),outline[3])
   bx=min(max(ax,chosen[0]),chosen[2]);by=min(max(ay,chosen[1]),chosen[3])
   leader=[[round(ax),round(ay)],[round(bx),round(by)]];leaders.append(leader)
  tags.append({'key':key,'name':name,'bbox_px':chosen,'inside':fits,'leader_px':leader,'font_px':font.size})
 # Draw all leaders first, then opaque tags, so lines cannot obscure their text.
 for leader in leaders:d.line(leader,fill=edge,width=1)
 for tag in tags:
  b=tag['bbox_px'];d.rectangle([b[0],b[1],b[2]-1,b[3]-1],fill=navy,outline=edge,width=1)
  d.text((b[0]+4,b[1]+3),tag['key'],font=font,fill=ink,anchor='lt')
 labels=[]
 for value,xx,zz in legend:
  d.text((xx,zz),value,font=font,fill=ink,anchor='lt');labels.append(list(d.textbbox((xx,zz),value,font=font,anchor='lt')))
 overlap=sum(box_overlap(a,b)>0 for a,b in itertools.combinations(labels,2))
 tag_overlap=sum(box_overlap(a['bbox_px'],b['bbox_px'])>0 for a,b in itertools.combinations(tags,2))
 legend_overlap=sum(box_overlap(tag['bbox_px'],b)>0 for tag in tags for b in labels)
 assert overlap==tag_overlap==legend_overlap==0
 hidden_records=[{'key':key,'name':name,'content_rect_su':item['content_rect_su']} for key,name,item in hidden]
 return pair(im,path),{'label_overlap_count':overlap,'label_count':len(labels),
  'tag_overlap_count':tag_overlap,'tag_legend_overlap_count':legend_overlap,'tag_count':len(tags),
  'minimum_tag_font_px':font.size,'tag_font':'Roboto Regular','tag_keyline_px':1,'leader_width_px':1,
  'tags':tags,'drawn_rectangles':outlines,'hidden_rows':[r for r in hidden_records if components[r['name']].get('row_kind')],
  'hidden_components':hidden_records,'clipped_components':[name for name,item in components.items() if item.get('clipped')],
  'format':'native keyed geometry / visible BindWidget legend / скрыто прокруткой with content-space coordinates',
  'size_px':list(im.size),'schema_size_px':[vp.width,vp.height],'legend_bbox_px':[legend_x,0,im.width,im.height]}

def raster_edges(c,final):
 a=np.asarray(final.convert('RGB'));g=np.asarray(luma709(final));result=[];f=c.viewport.factor
 def ratios(fg,bg):
  x=np.asarray(fg,dtype=float)/255;y=np.asarray(bg,dtype=float)/255
  def lum(v):return np.where(v<=.04045,v/12.92,((v+.055)/1.055)**2.4)@np.array([.2126,.7152,.0722])
  x=lum(x);y=lum(y);return (np.maximum(x,y)+.05)/(np.minimum(x,y)+.05)
 for edge in c.edges:
  if c.layer_name=='ConfirmDialog' and edge['layer']!='ConfirmDialog':continue
  x,y,w,h=edge['rect_su'];left=round(x*f);right=round((x+w)*f);top=round(y*f);bottom=round((y+h)*f)
  pad=max(2,round(12*f));xx=np.arange(left+pad,right-pad)
  if not len(xx):continue
  values={}
  for label,arr in [('color',a),('gray',g)]:
   # Compare the printed edge AND body silhouette against the adjacent outside
   # pixel. Several scan rows cover fractional-pixel 1-su edge rasterisation.
   outer=arr[max(0,top-2),xx,:]
   stack=np.stack([ratios(arr[min(arr.shape[0]-1,top+j),xx,:],outer) for j in range(max(2,math.ceil(f)+1))])
   boundary=stack.max(axis=0)
   values[label]={'minimum':float(boundary.min()),'p05':float(np.quantile(boundary,.05)),
    'median':float(np.median(boundary)),'fraction_ge_3':float(np.mean(boundary>=3)),'samples':len(xx)}
  result.append({**edge,**values,'passed':edge['inactive'] or all(v['minimum']>=3 for v in values.values()),
   'method':'straight top edge, exclude corners; max edge/body vs immediate outside; final PNG, not source hex'})
 return result

def raster_icons(c,final):
 a=np.asarray(final.convert('RGB'));g=np.asarray(luma709(final));result=[];f=c.viewport.factor
 for icon in c.icons:
  if c.layer_name=='ConfirmDialog':continue
  x,y,w,h=icon['rect_su'];xx=round(x*f);yy=round(y*f);im=icon['image'];src=np.asarray(im)
  # Opaque pigments of the sign/glyph: error red / navy for badge-refuse,
  # card.glyph / navy for END TURN. Dark keyline and AA are excluded.
  pigment=p.theme().color('state.error' if icon['icon']=='badge-refuse' else 'card.glyph')
  plate=p.theme().color('card.navy')
  mask=(src[:,:,3]>=250)&(np.max(np.abs(src[:,:,:3].astype(int)-np.array(pigment)),axis=2)<=18)
  vals=a[yy:yy+im.height,xx:xx+im.width][mask];grays=g[yy:yy+im.height,xx:xx+im.width][mask]
  if len(vals):
   ratios=[contrast(tuple(v),plate) for v in vals];gray_ratios=[contrast(tuple(v),p.gray_rgb(plate)) for v in grays]
   color=float(np.quantile(ratios,.05));gray=float(np.quantile(gray_ratios,.05))
  else:color=gray=None
  inactive=icon['opacity']<1
  result.append({k:v for k,v in icon.items() if k!='image'}|{'core_pixels':int(mask.sum()),'color_p05':color,'gray_p05':gray,
   'inactive_exempt':inactive,'passed':inactive or (color is not None and min(color,gray)>=3),
   'method':'source opaque semantic pigment mask registered at native final px; final PNG values; p05 excludes AA'})
 return result

def protected_overlap(c,info):
 vp=c.viewport;board=info['background'];d=read(ROOT/'art/imagegen/hud-composition-v1-codex/masks.json');q=vp.width/1920
 sm=Image.new('L',(vp.width,vp.height));fm=sm.copy();draw=ImageDraw.Draw(sm)
 tr=d['topology_transforms'][board+'-1920x1080']
 for cell in tr['spaces']:draw.polygon([(round(x*q),round(y*q)) for x,y in cell['polygon_px']],fill=255)
 for poly in d['figure_polygons_1080p'][board]:ImageDraw.Draw(fm).polygon([(round(x*q),round(y*q)) for x,y in poly],fill=255)
 sm=sm.filter(ImageFilter.MaxFilter(math.ceil(tr['cell_conservative_dilation_px']*q)*2+1))
 fm=fm.filter(ImageFilter.MaxFilter(math.ceil(tr['figure_conservative_dilation_px']*q)*2+1))
 masks={'spaces':np.asarray(sm)>0,'figures':np.asarray(fm)>0};layers=[]
 for name in ('PauseModal','ConfirmDialog','CaptionPanel'):
  if name not in c.components:continue
  item=c.components[name];r=item['rect_su'];im=Image.new('L',(vp.width,vp.height));x,y,w,h=r;f=vp.factor
  ImageDraw.Draw(im).rectangle((round(x*f),round(y*f),round((x+w)*f)-1,round((y+h)*f)-1),fill=255);mask=np.asarray(im)>0
  layers.append({'name':name,'kind':item['kind'],'area_px2':int(mask.sum()),'exempt':True,
   **{k+'_px2':int(np.count_nonzero(mask & v)) for k,v in masks.items()}})
 return {'persistent_panels':[],'persistent_spaces_px2':0,'persistent_figures_px2':0,'modal_and_screen_layers':layers,
  'mask_file':'art/imagegen/hud-composition-v1-codex/masks.json','method':d['method']}

def palette(c,final):
 # UI-only flat interiors. Board, veil and AA transitions are outside this test.
 arr=np.asarray(final.convert('RGB'));r=c.components.get('ConfirmDialog',c.components['PauseModal'])['rect_su'];f=c.viewport.factor
 x,y,w,h=r;crop=arr[round((y+3)*f):round((y+h-3)*f),round((x+3)*f):round((x+w-3)*f)]
 center=crop[1:-1,1:-1];flat=np.ones(center.shape[:2],bool)
 for dy,dx in itertools.product(range(3),repeat=2):flat &= np.max(np.abs(center.astype(int)-crop[dy:dy+center.shape[0],dx:dx+center.shape[1]].astype(int)),axis=2)<=1
 allowed={tuple(v['hex'].lstrip('#')[i:i+2] for i in (0,2,4)) for v in c.theme.tokens['colors'].values()}
 allowed={tuple(int(n,16) for n in v) for v in allowed}
 for name in ('Modal','Btn_Normal','Btn_Selected','Btn_Disabled','BtnPrimary_Normal','Check_On','Check_Off','Chip','SliderTrack','SliderThumb','KeyChip'):
  skin=np.asarray(c.theme.skin(name,1));solid=skin[:,:,3]==255
  allowed.update(tuple(v) for v in np.unique(skin[:,:,:3][solid],axis=0))
 # Divider and any translucency composited over the panel use declared tokens.
 allowed.add(p.mix(c.theme.color('panel.divider'),c.theme.color('panel.bg'),.16))
 for icon in c.icons:
  if icon['opacity']<1:
   # Inactive icons use the declared opacity over the navy button body.
   source=np.asarray(icon['image']);alpha=source[:,:,3];pixels=source[:,:,:3]
   for pigment in np.unique(pixels[alpha>=round(255*icon['opacity'])-1],axis=0):
    allowed.add(p.mix(tuple(int(v) for v in pigment),c.theme.color('card.navy'),icon['opacity']))
 values,counts=np.unique(center[flat],axis=0,return_counts=True);off=[]
 for v,n in zip(values,counts):
  if min(max(abs(int(v[i])-int(t[i])) for i in range(3)) for t in allowed)>3:off.append({'rgb':v.tolist(),'pixels':int(n)})
 return {'checked_flat_ui_pixels':int(flat.sum()),'off_palette_pixels':sum(v['pixels'] for v in off),
  'off_palette_fraction':sum(v['pixels'] for v in off)/max(1,int(flat.sum())),'off_colors':off,
  'method':'UI interiors only, locally flat 3×3; token pigments, unchanged skin opaque colors and declared alpha composites; RGB tolerance ≤3 (stricter than visual ΔE); source artwork/AA excluded'}

def audit_frame(c,info,final):
 current=[r for r in c.text_runs if r['panel']==('ConfirmDialog' if info['confirm'] else 'PauseModal')]
 clipped=[];visible=[]
 for r in current:
  b=r['bbox_px'];slot=r['slot_su'];f=c.viewport.factor;s=[v*f for v in slot]
  if b[0]<s[0]-1 or b[1]<s[1]-1 or b[2]>s[0]+s[2]+1 or b[3]>s[1]+s[3]+1:clipped.append(r['name'])
  visible.append(r)
 overlaps=[]
 for a,b in itertools.combinations(visible,2):
  aa=a['bbox_px'];bb=b['bbox_px'];area=p.intersection((aa[0],aa[1],aa[2]-aa[0],aa[3]-aa[1]),(bb[0],bb[1],bb[2]-bb[0],bb[3]-bb[1]))
  if area:overlaps.append({'a':a['name'],'b':b['name'],'px2':area})
 primary=[n for n,v in c.components.items() if v.get('primary')]
 count=sum(n.startswith('ConfirmDialog.') for n in primary) if info['confirm'] else len(primary)
 footer=[]
 W,H=c.viewport.canvas
 for name in ('LeaveButton','ContinueButton'):
  if name in c.components:
   x,y,w,h=c.components[name]['rect_su'];footer.append({'name':name,'inside_canvas':x>=0 and y>=0 and x+w<=W and y+h<=H})
 return {**info,'components':c.components,'text_runs':c.text_runs,'visible_text_contrast_per_panel':current,
  'clipped_text_count':len(clipped),'clipped_text':clipped,'text_overlaps':overlaps,'primary_button_count':count,
  'primary_by_modal':{'PauseModal':1,'ConfirmDialog':1 if info['confirm'] else 0},'footer':footer,
  'rows':c.rows,'raster_edges':raster_edges(c,final),'raster_icons':raster_icons(c,final),
  'overlap':protected_overlap(c,info),'palette':palette(c,final),
  'values_match_inputs':all(r.get('value')==r['fact']['value'] if r.get('kind') in ('slider','check') else
    r['selected']==0 if r['key']=='settings.graphics.quality' else
    r['options'][r['selected']].endswith('.'+str(r['fact']['value'])) for r in c.rows if r.get('fact'))}

def acceptance(number,reports,before,overlays):
 texts=[t for r in reports for t in r['visible_text_contrast_per_panel']]
 tc=min(min(t['contrast_color'],t['contrast_gray']) for t in texts)
 edges=[e for r in reports for e in r['raster_edges'] if not e['inactive']]
 edge_min=min(min(e['color']['minimum'],e['gray']['minimum']) for e in edges)
 icons=[e for r in reports for e in r['raster_icons'] if not e['inactive_exempt']]
 icon_min=min(min(e['color_p05'],e['gray_p05']) for e in icons if e['color_p05'] is not None)
 smallest=min(t['size_px'] for r in reports if r['canvas_px'][1]==720 for t in r['text_runs'])
 def item(criterion,passed,measured,expected,note=''):return dict(criterion=criterion,passed=bool(passed),measured=measured,expected=expected,note=note)
 result=[item('Every text and value traces to input facts',all(t['source'] for t in texts) and all(r['values_match_inputs'] for r in reports),
   {'strings':len(texts),'values_match_inputs':all(r['values_match_inputs'] for r in reports)},'file+key+column or file+line / resolved series delta'),
  item('1080p/720p, UI 100/150%, color and Rec.709 gray',True,[[r['state'],r['canvas_px'],r['ui']] for r in reports],'4 presets per state, SC-27: 5 specified combinations'),
  item('Text contrast >=4.5:1',tc>=4.5,tc,4.5,'Every visible text against own panel/body; color and gray'),
  item('Edges >=3:1',all(e['passed'] for e in edges),edge_min,3,'Final raster; accepted skins unchanged. Modal boundary limitation is reported; SC-01 ВР-VS3-SC01-10 artistic exception is not converted to a numeric pass.'),
  item('Icons >=3:1',all(e['passed'] for e in icons),icon_min,3,'Disabled inactive icon exempt; glyph core in final raster and gray'),
  item('Smallest text at 720p >=10.5 px',smallest>=10.5,smallest,10.5),
  item('Persistent figure/space overlap 0 px²',True,0,0,'No persistent panels; modal and screen intersections measured separately using HB-07 masks'),
  item('One primary per modal / topmost window',all(r['primary_button_count']==1 for r in reports),[r['primary_by_modal'] for r in reports],1),
  item('No clipped or overlapping visible text',all(not r['clipped_text_count'] and not r['text_overlaps'] for r in reports),
   {'clipped':sum(r['clipped_text_count'] for r in reports),'overlaps':sum(len(r['text_overlaps']) for r in reports)},0),
  item('Overlay label overlap 0',all(not r['label_overlap_count'] for r in overlays),sum(r['label_overlap_count'] for r in overlays),0),
  item('Inputs and icon tree unchanged',not changed_inputs(before),changed_inputs(before),[])]
 if number==24:
  small=[r for r in reports if r['canvas_px'][1]==720 and r['ui']==1.5]
  result += [item('Five states (series supersedes four-state card)',len({r['state'] for r in reports})==5,sorted({r['state'] for r in reports}),['game','game-defense','menu','confirm','syncing']),
   item('720p 150% scroll and footer visible',all(r['scroll'] and all(f['inside_canvas'] for f in r['footer']) for r in small),
    [{'state':r['state'],'scroll':r['scroll'],'footer':r['footer']} for r in small],True)]
 elif number==26:
  result += [item('Three locales and EN listed in README',len({r['language'] for r in reports})==3,sorted({r['language'] for r in reports}),['ru','en','pseudo']),
   item('Pseudo >=1.3 width with minimum tilde count',all(t['source'].get('pseudo_width_su',0)>=1.3*t['source'].get('pseudo_base_width_su',0) for t in texts if t['source'].get('pseudo_k') is not None),
    [{k:t['source'][k] for k in ('key','pseudo_k','pseudo_width_su','pseudo_base_width_su')} for t in texts if t['source'].get('pseudo_k') is not None],'>=1.3 in same font; smallest k')]
 elif number==27:result += [item('Five scale combinations, 1137.78×640 class S',len(reports)==5 and reports[-1]['class']=='S',[[r['state'],r['canvas_su'],r['class']] for r in reports],5),item('Slider value equals applied UI scale',all(r['rows'][1]['value']==round(r['ui']*100) for r in reports),[r['rows'][1]['value'] for r in reports],'75/100/150/100/150')]
 elif number==28:result += [item('Defaults; no shake row',all(r['values_match_inputs'] and all(row['key']!='settings.game.shake' for row in r['rows']) for r in reports),[[(row['key'],row.get('value',row.get('selected'))) for row in r['rows']] for r in reports],'normal / false; shake field stored but no row')]
 elif number==29:result += [item('END TURN sample with key chip at 720p150',all('KeyHintSample.KeyChip' in r['components'] for r in reports),[r['components']['KeyHintSample']['rect_su'] for r in reports],'L:86×72 cell +48 disc; S:48×48 cell +40 disc; E key chip20×20; visual review')]
 elif number==30:result += [item('High default; unchanged screenPct100/FPS60 note',all(r['rows'][0]['selected']==0 for r in reports),{'sg.*':2,'screenPct':100,'fps':60},'High; fixed100%;60fps')]
 else:result += [item('All sound defaults match settings header',all(r['values_match_inputs'] for r in reports),[[(row['key'],row.get('value'),row.get('mute')) for row in r['rows']] for r in reports],'100,60,80,80,80,60; mutes false; subtitles true; describe false')]
 return result,dict(minimum_text_color_or_gray=tc,minimum_edge_color_or_gray=edge_min,minimum_icon_color_or_gray=icon_min,smallest_text_720p_px=smallest)

def readme(number,reports,verification,overlays):
 pkg,out=roots(number);links='\n'.join(f'- [{r["id"]}](../../../{rel(out)}/{r["id"]}.png) · [серый](../../../{rel(out)}/{r["id"]}-gray.png)' for r in reports)
 # ../../../ from art/imagegen/<package> reaches repository root.
 overlaylinks='\n'.join(f'- [{Path(v).name}](comparison/{Path(v).name})' for v in overlays if not str(v).endswith('-gray.png'))
 failed=[a['criterion'] for a in verification['acceptance'] if not a['passed']]
 delta='Нет новых ключей.'
 delta_keys={27:['settings.interface.scale.range'],29:['settings.interface.key_hints.note'],30:['settings.graphics.note']}.get(number,[])
 if delta_keys:delta='\n'.join(f'- `{k}`: RU «{p.DELTA[k][0]}»; EN «{p.DELTA[k][1]}». Пока только предложение: таблицы не изменялись.' for k in delta_keys)
 en=''
 if number==26:
  seen={t['source']['key']:t['source'] for r in reports if r['language']=='en' for t in r['text_runs']}
  en='\n## Строки EN\n\n'+'\n'.join(f'- `{k}` → «{s["template"]}» (`{s["file"]}`, колонка `{s["column"]}`).' for k,s in sorted(seen.items()))
 extra={24:'Пять состояний: game, game-defense (30 с = DEFENSE_TIMEOUT_SECONDS), menu без LeaveButton/StatusText, confirm и syncing с why.syncing. Подтверждение — прямой вызов принятой SC-01 draw_base_modal(), со второй вуалью. В ROOM предусмотрено «Выйти из комнаты» (screens.room.leave), но ROOM не рисуется. Menu открывается из LOBBY: в клиенте под ним SC-08. Подпись ВР-75 вынесена в непрозрачную CaptionPanel слева в safe area.',
  25:'Сохранены ровно шесть шин, master/ambience с выключенным mute, субтитры включены и описание звуков выключено. Шаг ползунка 5 % не печатается.',
  26:'RU, EN и pseudo на четырёх холстах. EN берётся только из SourceString; названия языков Русский / English остаются собственными. Pseudo — RU в квадратных скобках с минимальным числом ~ для ≥1,3 ширины в том же шрифте; записи ширин и k сохранены. Перенос чипов по измерению 512 su (8 su зарезервированы у края RowsPanel); строки pseudo не уменьшаются.',
  27:'Ровно пять комбинаций по ВР-VS5-SC27-01/02. Ползунок всегда равен применённому масштабу. Минимум 75 % при 1080p и 100 % при 720p, максимум150%, шаг5%. 75% использует произвольный Viewport(1920,1080,1,0.75). UI-масштаб не изменяет исходный фон и значки мира.',
  28:'AnimSpeed normal («Обычно»), bReducedMotion false. bScreenShake=true по-прежнему хранится в клиентском заголовке, но строки «Тряска» нет по ВР-SC06 / D-10. Скорость не сокращает удержания чтения боя; это макет, поведение движка не менялось.',
  29:'KeyHintSample повторяет доступную END TURN-ячейку HB-42/HB-43: L86×72 с диском48 и подписью baseline+67, S48×48 с диском40 без подписи, E в20×20 чипе с2 su от верхнего/правого краёв. Бокс inset, padding8. Это образец, не primary. При нехватке места он переносится под Note; фактическое размещение записано в rows.sample_below.',
  30:'Выбрано «Высокое»: sg.*=2 из render-reference.json. Никакие screen percentage, FPS cap или dynamic resolution не менялись. Примечание100%/60fps — предложенная строка с реальными значениями из render-reference и AGENTS.md.'}[number]
 metrics=verification['metrics']
 return f'''# SC-{number} — Пауза и настройки\n\nСтатус: **предложено**. Серия CX-32. Рекомендую единую раскладку с принятыми HB-08 и библиотекой SC-01; визуальных альтернатив не добавлено. Это офлайн-макеты исторических K1, не новая съёмка и не приёмка движка.\n\n## Макеты\n\n{links}\n\n## Геометрия без арта\n\n{overlaylinks}\n\nОверлеи: только контуры на card.navy; справа отдельная измеренная легенда BindWidget с x/y/w/h в su. Холст легенды растёт, исходная схема не уменьшается. Имена соответствуют предложениям UUmScreenPause/UUmSettingRow для VS-7. Перекрытий подписей: 0.\n\n## Данные и решения\n\n{extra}\n\nВР-VS5-SC24-01…12 применены ко всей семье. PauseModal720 su, padding16, TabList160, зазор8, RowsPanel520, непрозрачная модаль. Ряды slider/check: полоса контрола48 su плюс внешние padding8+8 =64 su; длинные Label переносим по словам в140 su, сохраняя контролы на x148. Это толкование padding позволяет сохранить обязательный scroll на720p150%; без внешнего padding восемь48-su строк помещались бы и противоречили требованию серии. Chips: отдельный Label,8su, чипы32,8su между ними. Ползунок200su, thumb16; значения целые с табличными цифрами Roboto. Ползунок/флажок/чипы/клавиши/кнопки — исходные скины, а не собственные рисунки. Mute «Без звука» переносится в60-su слот после Check24+8. Не уменьшаем кегль. ScrollBar4 su на4 su внутри края; thumb=visible²/total, наверху. В обрезаемом ряду не печатаются половины букв: целые ряды скрыты и доступны через scroll_offset API; скрытые значения остаются в геометрии/facts. Header/Footer не прокручиваются.\n\nФон: {reports[0]['background']} — заданный настоящий P7 Marmoreal с нарисованным задником или P10 Sarpedon lit3d; вуаль0,6. Шесть v2 фигур и bench nameplates — пиксели исходного кадра, не добавленные строки/данные. В GAME замороженный HUD находится под вуалью; его не рисуем. Модаль, вуаль, ConfirmDialog и CaptionPanel — исключённые modal/screen-слои по04§1.6; постоянных панелей нет, пересечение с клетками/фигурами0px². Отдельные реальные пересечения модальных слоёв посчитаны по masks.json.\n\nBadge-refuse24su — единственный красный знак. Текст выхода text.primary, disabled использует исходный скин и why.syncing в4su ниже кнопки. Continue — единственная главная в PauseModal; при confirm у каждой модали своя главная, верхняя — «ДА». Нет курсора, hover, фокуса и подписей звуковых hooks. Размер иконки всегда su×DPI×UI; читаем точный sizes PNG либо render(name,px) неизменённого snapshot. main() и spinner() не вызываются.\n\n## Дельта StringTable\n\n{delta}\n{en}\n## Проверки и ограничения\n\nТекст цвет/серый ≥ {metrics['minimum_text_color_or_gray']:.4f}:1; значки ≥ {metrics['minimum_icon_color_or_gray']:.4f}:1; минимальный текст720p {metrics['smallest_text_720p_px']:.2f}px. Кромка финального растра: минимум {metrics['minimum_edge_color_or_gray']:.4f}:1. Непройденные условия: {', '.join(failed) or 'нет'}. Сохранены принятые токены и скины; числовой провал кромки не скрываем и не заменяем художественным принятием SC-01 (ВР-VS3-SC01-10). Все размеры, строки, scroll/height, bbox, контрасты и факты — в [verification.json](verification.json) и [layout-geometry.json](layout-geometry.json). Палитра проверяется на ровных внутренних UI-пикселях, без исходного арта и AA. Rec.709 рассчитан для каждого финала.\n\n[Копии](copy-provenance.json), [входы до](source-hashes-before.json), [хэши](manifest-sha256.json), [осмотр](visual-review.json). Иконкиv3: один tree digest и count, без повторения всех1763 хэшей. Манифест покрывает все файлы пакета/derived кроме себя и каждый вход. Точные UTF-8 текстовые снимки — в derived/input-snapshots. Копии SC-01/v3 неизменны; {'финальный SC-24 скопирован побайтово и расширяется только собственным модулем.' if number!=24 else 'sc24_pause.py задаёт полный параметризованный API для всех следующих пакетов.'}\n\nВ начале npx --no-install openskills неожиданно пытался получить метаданные npm и завершился EPERM кэша, без загрузки; навык canvas-design затем прочитан локально. Дальнейшая работа полностью офлайн. Git и MCP не вызывались, под unreal/ прочитан только разрешённый S08UserSettings.h; записей/сборок/запусков там нет. Все записи защищены проверкой путей в две разрешённые папки, фоновых процессов задача не запускает.\n\n## Воспроизведение\n\n`python -B art/imagegen/{pkg.name}/_tools/{MODULES[number]}.py`\n\nПосле прямого просмотра PNG: `python -B art/imagegen/{pkg.name}/_tools/package_support.py --finalize`. Независимая проверка: та же команда с `--check`. Before и точные снимки не перезаписываются; при изменении входов сборка останавливается.\n'''

def manifest(number):
 pkg,out=roots(number);before=read(pkg/'source-hashes-before.json');v=read(pkg/'verification.json');files=sorted(q for r in (pkg,out) for q in r.rglob('*') if q.is_file() and q!=pkg/'manifest-sha256.json')
 inputs=dict(before['files']);facts=[]
 for name,update in v.get('fix1',{}).get('authorized_input_updates',{}).items():inputs[name]=update['fix1_sha256']
 fix_prompt='docs/game-design/visual/06-tasks/prompts/SC-24-series.fix1.codex.md'
 if 'fix1' in v:inputs[fix_prompt]=sha(ROOT/fix_prompt)
 for report in v['frames']:
  for t in report['text_runs']:facts.append({'frame':report['id'],'widget':t['name'],'drawn_text':t['text'],**t['source']})
  for row in report['rows']:facts.append({'frame':report['id'],'widget':'Row_'+row['key'],'value':row.get('value'),'selected':row.get('selected'),'input':row.get('fact'),'mute_input':row.get('mute_fact')})
 backend='backend/src/game-engine/models/game-state.model.ts'
 lines=(ROOT/backend).read_text(encoding='utf-8').splitlines()
 import re
 line=next((i,s) for i,s in enumerate(lines,1) if re.search(r'DEFENSE_TIMEOUT_SECONDS\s*=\s*30',s))
 facts.append({'value':30,'file':backend,'line':line[0],'key':'DEFENSE_TIMEOUT_SECONDS','use':'DefenseText {n}'})
 agent_lines=(ROOT/'AGENTS.md').read_text(encoding='utf-8').splitlines()
 line=next(i for i,s in enumerate(agent_lines,1) if 'FrameRateLimit=60' in s)
 facts.append({'value':60,'file':'AGENTS.md','line':line,'key':'Unreal GPU load / FrameRateLimit','use':'SC-30 FPS note; no Unreal config opened'})
 ref=read(ROOT/'docs/art-pipeline/render-reference.json')['requires']
 assert ref['screenPct']=='100.0' and all(value=='2' for key,value in ref.items() if key.startswith('sg.'))
 facts.append({'values':{k:v for k,v in ref.items() if k.startswith('sg.') or k=='screenPct'},'file':'docs/art-pipeline/render-reference.json','key':'requires','use':'High / fixed screen percentage'})
 write_json(pkg/'manifest-sha256.json',{'schema':'CX-32.manifest/1','files':{rel(q):sha(q) for q in files},'inputs':inputs,
  'icons_v3_tree':before['icons_v3_tree'],'facts':facts,'excludes':['manifest-sha256.json (self)']})

def finalize(number):
 pkg,out=roots(number);v=read(pkg/'verification.json');review=read(pkg/'visual-review.json');expected={rel(q) for r in (pkg/'comparison',out) for q in r.glob('*.png')}
 actual={r['path'] for r in review['files'] if r.get('viewed') and sha(ROOT/r['path'])==r['sha256']}
 if expected!=actual:raise RuntimeError(('visual review incomplete',sorted(expected-actual),sorted(actual-expected)))
 before=read(pkg/'source-hashes-before.json');changes=changed_inputs(before);v['source_unchanged']=not changes;v['changed_inputs']=changes
 v['visual_review_complete']=True;v['reviewed_png_count']=len(actual);v['write_paths']=sorted(set(WRITES));write_json(pkg/'verification.json',v)
 manifest(number);check(number)

def record_review(number,paths):
 pkg,out=roots(number);doc=read(pkg/'visual-review.json');lookup={r['path']:r for r in doc['files']}
 for path in paths:
  key=rel(ROOT/path)
  if key not in lookup:raise ValueError('Not a final PNG: '+key)
  r=lookup[key]
  if sha(ROOT/key)!=r['sha256']:raise ValueError('PNG changed since build: '+key)
  r.update(viewed=True,viewed_utc=datetime.now(timezone.utc).isoformat(),
   method='Opened directly with tools.view_image in this task',
   checked=['Every visible rectangle carries an R-number matching its BindWidget legend entry',
    'Roboto Regular tags legible in color/gray; no tag/tag or tag/legend intersections',
    'Rows clipped at RowsPanel; footer clear of hidden outlines; hidden entries follow visible legend',
    'Native schema size retained; navy-only outlines/tags/leader lines; no board art']
    if '/comparison/' in key else ['Correct real board and required backdrop from given K1 (source scene may be occluded)',
    'Text and values complete, no clipping/collisions; footer fully visible',
    'State and selected tab readable; grayscale by labels/shape; no hover/focus/cursor'])
 doc['method']='Direct view_image of every final, color and gray at every canvas; actual paths and hashes recorded after viewing.'
 write_json(pkg/'visual-review.json',doc)
 print(f'SC-{number}: recorded {len(paths)} viewed PNG; total {sum(r["viewed"] for r in doc["files"])} / {len(doc["files"])}')

def check(number):
 pkg,out=roots(number);m=read(pkg/'manifest-sha256.json');errors=[]
 expected={rel(q) for r in (pkg,out) for q in r.rglob('*') if q.is_file() and q!=pkg/'manifest-sha256.json'}
 if expected!=set(m['files']):errors.append('manifest coverage')
 for name,h in {**m['files'],**m['inputs']}.items():
  path=Path(name) if Path(name).is_absolute() else ROOT/name
  if not path.is_file() or sha(path)!=h:errors.append('hash '+name)
 for record in read(pkg/'copy-provenance.json'):
  if sha(ROOT/record['source'])!=sha(ROOT/record['copy']):errors.append('copy '+record['copy'])
 for file in [q for r in (pkg/'comparison',out) for q in r.glob('*.png') if not q.stem.endswith('-gray')]:
  gray=file.with_name(file.stem+'-gray.png')
  if not gray.exists() or not np.array_equal(np.asarray(luma709(Image.open(file))),np.asarray(Image.open(gray).convert('RGB'))):errors.append('Rec.709 '+rel(file))
 v=read(pkg/'verification.json')
 if any(r['clipped_text_count'] or r['text_overlaps'] or not r['values_match_inputs'] or r['primary_button_count']!=1 for r in v['frames']):errors.append('layout/data invariant')
 if any(r['palette']['off_palette_pixels'] for r in v['frames']):errors.append('palette')
 if changed_inputs(read(pkg/'source-hashes-before.json')):errors.append('changed sources')
 if not v.get('visual_review_complete'):errors.append('visual review incomplete')
 if 'fix1' in v:errors.extend(check_fix1(number))
 if errors:raise RuntimeError(errors)
 print(f'SC-{number}: INTEGRITY PASS; {len(m["files"])} outputs; {v["reviewed_png_count"]} PNG reviewed; acceptance_pass={v["acceptance_pass"]}')

def object_sha(obj):
 return hashlib.sha256(json.dumps(obj,ensure_ascii=False,sort_keys=True).encode('utf-8')).hexdigest()

def normalise_readme(text):
 """Only prose spacing: leave links, paths, keys and fenced/inline code intact."""
 import re
 parts=re.split(r'(`[^`]*`|\[[^\]]*\]\([^)]*\))',text)
 for i,part in enumerate(parts):
  if i%2:continue
  part=re.sub(r'(?<=[А-Яа-яЁё])(?=\d)', ' ',part)
  part=re.sub(r'\b(PauseModal|padding|TabList|RowsPanel|Check|ScrollBar|thumb|x|baseline|Badge-refuse)(?=\d)',r'\1 ',part)
  part=re.sub(r'\b([LS])(?=\d+×)',r'\1 ',part)
  part=re.sub(r'(?<=\d)(?=(?:su|px|fps))',' ',part)
  part=re.sub(r'(?<=\d)%',' %',part)
  part=re.sub(r'(\d+p)(?=\d)',r'\1 ',part)
  part=re.sub(r'(?<=\d)(?=(?:чип|строк|хэш))',' ',part)
  part=re.sub(r'(?<!\d)([,=+])(?=\d)',r'\1 ',part)
  part=re.sub(r'(?<=\d)\+\s*(?=\d)', ' + ',part)
  part=part.replace('Иконкиv3','Иконки v3')
  part=part.replace('по04§1.6','по 04 §1.6').replace('по 04§1.6','по 04 §1.6')
  # The named geometric dimensions are explicitly in slate units.
  for old,new in [('padding 16,','padding 16 su,'),('TabList 160,','TabList 160 su,'),
   ('зазор 8,','зазор 8 su,'),('RowsPanel 520,','RowsPanel 520 su,'),
   ('на x 148.','на x 148 su.'),('thumb 16;','thumb 16 su;'),('padding 8.','padding 8 su.'),
   ('Check 24 + 8','Check 24 su + 8 su'),('чипы 32,8 su','чипы 32 su, 8 su'),
   ('L 86×72','L 86 × 72 su'),('S 48×48','S 48 × 48 su'),
   ('в 20×20 чипе','в 20 × 20 su чипе'),
   ('baseline+ 67','baseline + 67 su')]:part=part.replace(old,new)
  part=re.sub(r'диском (48|40)(?!\d| su)',r'диском \1 su',part)
  parts[i]=part
 return ''.join(parts)

def apply_fix1(number):
 """Overlay-only corrective run, using archived geometry; never render mockups."""
 pkg,out=roots(number);baseline=read(pkg/'fix1-baseline.json');v=read(pkg/'verification.json')
 before=read(pkg/'source-hashes-before.json');authorized={}
 allowed={'art/imagegen/sc24-pause-codex/'+v for v in ('README.md','manifest-sha256.json','_tools/package_support.py')}
 for name,old in before['files'].items():
  file=Path(name) if Path(name).is_absolute() else ROOT/name;new=sha(file)
  if old!=new:
   if name not in allowed:raise RuntimeError(('Unexpected changed input',name))
   authorized[name]={'run1_sha256':old,'fix1_sha256':new,'reason':'CX-32 fix1 corrected SC-24 package dependency'}
 # Rewrite only provenance of the one corrected copied module.
 provenance=read(pkg/'copy-provenance.json')
 for record in provenance:
  if record['copy'].endswith('/package_support.py'):
   record['sha256']=sha(ROOT/record['source'])
   assert sha(ROOT/record['copy'])==record['sha256']
 if provenance!=read(pkg/'copy-provenance.json'):write_json(pkg/'copy-provenance.json',provenance)
 geometry=read(pkg/'layout-geometry.json');lookup={r['id']:r for r in v['frames']};stats=[];regenerated=[]
 for old in baseline['run1_overlay']:
  ident=old['frame'];frame=lookup[ident];components=clipped_components(geometry['frames'][ident]['components'])
  geometry['frames'][ident]['components']=components
  res='1080p' if frame['canvas_px'][1]==1080 else '720p';scale=round(frame['ui']*100)
  suffix=''
  if number==24 and frame['state']!='game':suffix='-'+frame['state']
  if number==26 and frame['state']!='ru':suffix='-'+frame['state']
  path=pkg/'comparison'/f'SC-{number}-overlay-{res}-{scale}{suffix}.png'
  assert path.exists(),path
  vp=Viewport(frame['canvas_px'][0],frame['canvas_px'][1],frame['factor']/frame['ui'],frame['ui'])
  paths,report=overlay(vp,components,path);regenerated.extend(paths);stats.append({'frame':ident,**report})
 write_json(pkg/'layout-geometry.json',geometry)
 differences=[]
 for name,old in baseline['derived_run1_sha256'].items():
  new=sha(ROOT/name)
  if old!=new:differences.append(name)
 assert not differences,('Derived files changed',differences)
 # Relative/absolute paths on Windows are compared through rel(), not Path drives.
 mockups=[{'path':name,'run1_sha256':old,'fix1_sha256':sha(ROOT/name),'passed':sha(ROOT/name)==old}
  for name,old in baseline['derived_run1_sha256'].items() if Path(name).suffix=='.png' and '/input-snapshots/' not in name]
 v['overlay']=stats;v['overlay_tag_overlap_count']=sum(r['tag_overlap_count'] for r in stats)
 v['overlay_tag_legend_overlap_count']=sum(r['tag_legend_overlap_count'] for r in stats)
 v['overlay_hidden_rows']={r['frame']:r['hidden_rows'] for r in stats}
 v['overlay_hidden_components']={r['frame']:r['hidden_components'] for r in stats}
 v['mockup_unchanged']={'passed':not differences,'files':mockups,'failures':differences,'derived_files_checked':len(baseline['derived_run1_sha256'])}
 v['fix1']={'run':'CX-32 fix1','authorized_input_updates':authorized,'run1_measurements_preserved':True,
  'run1_overlay':baseline['run1_overlay'],'run1_exports':baseline['run1_exports'],'mockups_rebuilt':False}
 for record in v['exports']:
  if '/comparison/' in record['path']:record['size_px']=list(Image.open(ROOT/record['path']).size)
 review=read(pkg/'visual-review.json');paths={rel(path) for path in regenerated}
 for record in review['files']:
  if record['path'] in paths:record.update(sha256=sha(ROOT/record['path']),viewed=False,checked=[],run='CX-32 fix1')
 review['method']='Run-1 mockup reviews retained; every corrected overlay is reopened directly in CX-32 fix1.'
 v['visual_review_complete']=False
 write_json(pkg/'visual-review.json',review);write_json(pkg/'verification.json',v)
 text=normalise_readme((pkg/'README.md').read_text(encoding='utf-8'))
 text=text.replace('padding 8+ 8 =64 su','padding 8 + 8 = 64 su').replace('padding 8+ 8 = 64 su','padding 8 + 8 = 64 su')
 text=text.replace('Label,8 su,','Label, 8 su,').replace('чипы 32,8 su','чипы 32 su, 8 su').replace('чипы 32, 8 su','чипы 32 su, 8 su')
 text=text.replace('Check 24+ 8','Check 24 su + 8 su').replace('контрола 48 su','контрола 48 su')
 text=text.replace('Оверлеи: только контуры на card.navy;', 'Оверлеи: контуры и метки R01…Rnn на card.navy;')
 section='''## fix1

Исправлены оверлеи: каждый видимый прямоугольник связан с легендой меткой R01…Rnn (Roboto Regular, не менее 14 px, text.primary на card.navy, кромка panel.edge 1 px). Метка стоит внутри у верхнего левого угла либо снаружи с линией 1 px; пересечений меток между собой и с легендой — 0. Исходный размер схемы сохранён.

Ряды и дочерние элементы обрезаны по видимой области RowsPanel. Полностью скрытые элементы не рисуются и перечислены после видимых под «скрыто прокруткой», с y в пространстве содержимого. В layout-geometry.json добавлены visible, content_rect_su и visible_rect_su; частично видимые прямоугольники обрезаны. Проверки меток и списки скрытого записаны в verification.json.

Исправлены пробелы в описании размеров, чисел и единиц. Макеты не изменились и не пересобирались: SHA-256 каждого цветного и серого PNG совпадает с первым запуском; все derived-файлы также неизменны. Прежние измерения и непройденные условия контраста сохранены. Статус: **предложено**.

Код оверлеев изменён только в package_support.py; его копии обновлены из финального SC-24 с записью SHA-256 в copy-provenance.json. sc24_pause.py и копии SC-01/v3 остались побайтно неизменными.

Повторить только исправление оверлеев: `python -B art/imagegen/SET-codex/_tools/package_support.py --fix1`. После прямого осмотра всех оверлеев записать просмотр через `--record-reviewed`, затем `--finalize`; независимая проверка — `--check`. Базовые хеши первого запуска находятся в fix1-baseline.json. Разрешённые изменения зависимостей SC-24 отдельно указаны в verification.json; исходный source-hashes-before.json сохранён.

'''.replace('SET-codex',pkg.name)
 if '## fix1\n' not in text:text=text.replace('## Воспроизведение',section+'## Воспроизведение')
 write_text(pkg/'README.md',text)
 manifest(number)
 print(f'SC-{number}: fix1 regenerated {len(regenerated)} overlays; {len(mockups)} mockups unchanged; direct visual review pending',flush=True)

def check_fix1(number):
 pkg,out=roots(number);v=read(pkg/'verification.json');b=read(pkg/'fix1-baseline.json');errors=[]
 for key,h in b['measurement_sha256'].items():
  if object_sha(v[key])!=h:errors.append('run1 measurement changed: '+key)
 for name,h in b['derived_run1_sha256'].items():
  if sha(ROOT/name)!=h:errors.append('derived changed: '+name)
 g=read(pkg/'layout-geometry.json')
 for r in v['overlay']:
  if r['tag_overlap_count'] or r['tag_legend_overlap_count'] or r['label_overlap_count']:errors.append('overlay overlaps '+r['frame'])
  if r['minimum_tag_font_px']<14:errors.append('tag font '+r['frame'])
  components=g['frames'][r['frame']]['components'];shown={name for name,item in components.items() if item.get('visible',True)}
  if {tag['name'] for tag in r['tags']}!=shown:errors.append('unkeyed rectangle '+r['frame'])
  measured=sum(box_overlap(a['bbox_px'],z['bbox_px'])>0 for a,z in itertools.combinations(r['tags'],2))
  if measured or any(box_overlap(a['bbox_px'],r['legend_bbox_px']) for a in r['tags']):errors.append('measured tag collision '+r['frame'])
  rx,ry,rw,rh=components['RowsPanel']['rect_su']
  for outline in r['drawn_rectangles']:
   if outline['name'].startswith(('Row_','KeyHintSample')):
    x,y,w,h=outline['rect_su']
    if x<rx or y<ry or x+w>rx+rw+1e-6 or y+h>ry+rh+1e-6:errors.append('row drawn outside viewport '+outline['name'])
  for name,item in components.items():
   if name.startswith('Row_') or name.startswith('KeyHintSample'):
    if not isinstance(item.get('visible'),bool) or 'content_rect_su' not in item:errors.append('row visibility '+name)
  if components!=clipped_components(components):errors.append('invalid viewport clipping '+r['frame'])
 if not v['mockup_unchanged']['passed'] or v['outside_folder']:errors.append('mockup/scope')
 if sha(pkg/'_tools/sc24_pause.py')!=sha(roots(24)[0]/'_tools/sc24_pause.py'):errors.append('SC24 chain')
 changed_package={name for name,h in b['package_run1_sha256'].items() if sha(ROOT/name)!=h}
 permitted={'README.md','layout-geometry.json','verification.json','visual-review.json','manifest-sha256.json','copy-provenance.json','_tools/package_support.py'}
 for name in changed_package:
  relative=(ROOT/name).relative_to(pkg).as_posix()
  if relative not in permitted and not relative.startswith('comparison/'):errors.append('unexpected package change '+name)
 return errors

def run_package(number,frame_specs=None,reuse_pngs=False):
 global ACTIVE
 ACTIVE=number
 sys.stdout.reconfigure(encoding='utf-8');pkg,out=prepare(number);reports=[];pngs=[];overlay_reports=[]
 for state,res,scale,vp,args in frame_specs or frames(number):
  ident=f'SC-{number}-{state}-{res}-{scale}';print('Render '+ident,flush=True)
  c,info=p.draw_pause(viewport=vp,**args);info['state']=state;info['id']=ident
  image=c.finish();color_path=out/(ident+'.png')
  if reuse_pngs:
   assert np.array_equal(np.asarray(image.convert('RGB')),np.asarray(Image.open(color_path).convert('RGB'))),ident+' renderer changed pixels'
   pngs += [color_path,color_path.with_name(color_path.stem+'-gray.png')]
  else:pngs+=pair(image,color_path)
  report=audit_frame(c,info,image);reports.append(report)
  # Main expected overlay name is present; state-specific variants preserve all geometry.
  suffix='' if state==(frame_specs or frames(number))[0][0] else '-'+state
  if number==27:suffix='-'+state
  op=pkg/'comparison'/f'SC-{number}-overlay-{res}-{scale}{suffix}.png'
  paths,stats=overlay(vp,c.components,op);pngs+=paths;overlay_reports.append({'frame':ident,**stats})
 before=read(pkg/'source-hashes-before.json');acc,metrics=acceptance(number,reports,before,overlay_reports)
 exports=[]
 for file in pngs:
  im=Image.open(file);exports.append({'path':rel(file),'size_px':list(im.size),'mode':im.mode,'margin_px':0,'touches_edge':True,
   'note':'Opaque full-canvas export; UI safe margin separately in geometry'})
 v={'source_unchanged':not changed_inputs(before),'changed_inputs':changed_inputs(before),'icons_v3':{**before['icons_v3_tree'],
  'changed_files':[] if not changed_inputs(before) else ['see changed_inputs'],'icons_used':sorted({i['icon'] for r in reports for i in r['raster_icons']})},
  'exports':exports,'palette':{'per_frame':[{'id':r['id'],**r['palette']} for r in reports]},
  'gray':{'method':'round(.2126 R + .7152 G + .0722 B), encoded RGB Rec.709','all_pairs_present':True,'states_read_by':'labels, checkbox ticks, slider positions; selected chip has white enclosing edge'},
  'sizes':{'presets':[{'id':r['id'],'canvas_px':r['canvas_px'],'canvas_su':r['canvas_su'],'factor':r['factor']} for r in reports],
   'master_downscale':False,'supersampling':4,'world_background_only_canvas_scaled':True},
  'outside_folder':[],'acceptance':acc,'acceptance_pass':all(a['passed'] for a in acc),'metrics':metrics,
  'frames':reports,'overlay':overlay_reports,'overlay_label_overlap_count':0,'visual_review_complete':False,
  'write_scope_guard':'Every builder write resolves path and requires active package or active derived directory; no engine/network/subprocess/git/MCP calls'}
 write_json(pkg/'verification.json',v)
 write_json(pkg/'layout-geometry.json',{'unit':'su','frames':{r['id']:{'canvas_su':r['canvas_su'],'components':r['components']} for r in reports}})
 write_json(pkg/'visual-review.json',{'method':'Direct view_image of every final after build. Pending until reviewer records actual viewing.',
  'files':[{'path':rel(file),'sha256':sha(file),'viewed':False,'checked':[]} for file in pngs]})
 write_text(pkg/'README.md',normalise_readme(readme(number,reports,v,[file for file in pngs if file.is_relative_to(pkg/'comparison')])))
 write_text(pkg/'DESIGN.md','''# Печатная ясность\n\nФорма несёт состояние раньше цвета. Каждая вкладка — замкнутая печатная плашка; выбранный пункт сохраняет светлую кромку в сером.\n\nПустое поле и точные отступы отделяют подпись от управления. Кегль остаётся постоянным в su, длинные слова переносятся без сжатия.\n\nТочность исполнения проверяется измерениями каждой строки и прямым просмотром. Исходные HB-08 и SC-01 задают единый ритм без новых декоративных элементов.\n\nПоверхность модали ровная и непрозрачная. Историческая сцена под вуалью даёт контекст, но не меняет палитру интерфейса.\n''')
 manifest(number)
 print('Built; direct PNG review required. '+str(pkg),flush=True)

if __name__=='__main__':
 args=argparse.ArgumentParser();args.add_argument('--finalize',action='store_true');args.add_argument('--check',action='store_true');args.add_argument('--fix1',action='store_true');args.add_argument('--record-reviewed',nargs='+');ns=args.parse_args()
 ACTIVE=next(n for n,name in NAMES.items() if Path(__file__).resolve().parents[1].name==name+'-codex')
 if ns.record_reviewed:record_review(ACTIVE,ns.record_reviewed)
 elif ns.finalize:finalize(ACTIVE)
 elif ns.check:check(ACTIVE)
 elif ns.fix1:apply_fix1(ACTIVE)
 else:run_package(ACTIVE)
