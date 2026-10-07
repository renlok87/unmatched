#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""CX-32 PAUSE renderer. Read-only inputs; caller owns output paths.

48-su slider/check control bands have additional 8-su outer row padding.
The SC-01 and v3 snapshots are never modified. No engine/network operations.
"""
from __future__ import annotations
import csv
import json
import math
from functools import lru_cache
from pathlib import Path
import numpy as np
from PIL import Image, ImageDraw, ImageFilter
from screen_mockup_base import Canvas, Theme, Viewport, mix, contrast, luma709, draw_base_modal, modal_rect

ROOT = Path(__file__).resolve().parents[4]
ST = 'docs/unreal/contracts/hud/st-screens.csv'
HUD = 'docs/unreal/contracts/hud/st-hud.csv'
SERIES = 'docs/game-design/visual/06-tasks/prompts/SC-24-series.codex.md'
SETTINGS = 'unreal/Unmatched/Source/Unmatched/S08/S08UserSettings.h'
BG = {
 'marmoreal': 'docs/game-design/evidence/ENV-MAPS/p7-concept-paste-2026-10-01/marmoreal-concept-flag/bench-K1-1920x1080.png',
 'sarpedon': 'docs/game-design/evidence/ENV-MAPS/p10-sarpedon-rework-2026-10-03/sarpedon-packaged/bench-K1-1920x1080.png'}
FONTDIR = Path('C:/Program Files/Epic Games/UE_5.8/Engine/Content/Slate/Fonts')
DELTA = {
 'settings.interface.scale.range': ('{min}–{max} %', '{min}–{max} %'),
 'settings.interface.key_hints.note': ('Авто — только в первой партии', 'Auto - first match only'),
 'settings.graphics.note': ('Масштаб экрана 100 % и лимит 60 кадров/с не меняются', 'Screen percentage 100 % and the 60 fps cap stay unchanged')}

@lru_cache(None)
def theme():
 return Theme(ROOT/'docs/unreal/contracts/hud/hud-style-tokens.json', FONTDIR/'Roboto-BoldCondensed.ttf',
  FONTDIR/'Roboto-Regular.ttf', ROOT/'art/imagegen/hud-icons-v3/sizes/loader-spinner-48.png',
  ROOT/'art/imagegen/hud-skins-v1-codex')

@lru_cache(None)
def tables():
 result = {}
 for file in (ST, HUD):
  with (ROOT/file).open(encoding='utf-8-sig', newline='') as f:
   result.update({r['Key']:dict(r, file=file) for r in csv.DictReader(f)})
 why=json.loads((ROOT/'docs/unreal/contracts/hud/why-reasons.json').read_text(encoding='utf-8'))
 for r in why['reasons']:
  result[r['key']]={'ru':r['ru'],'SourceString':r['en'],'file':'docs/unreal/contracts/hud/why-reasons.json'}
 return result

def measure(value, role='type.body'):
 return theme().font(role,4).getlength(value)/4

def pseudo(value,role):
 k=0
 while measure('['+value+'~'*k+']',role)<measure(value,role)*1.3:
  k+=1
 return '['+value+'~'*k+']',k

def string(key,language='ru',role='type.body',caps=False,**args):
 column='SourceString' if language=='en' else 'ru'
 if key in DELTA:
  raw=DELTA[key][language=='en']; file=SERIES; delta=True
 else:
  item=tables()[key]; raw=item[column]; file=item['file']; delta=False
 value=raw.format(**args)
 if caps:value=value.upper()
 original=value
 if language=='pseudo':value,k=pseudo(value,role)
 else:k=None
 return value, {'file':file,'key':key,'column':column,'template':raw,'arguments':args,
  'transform':('upper; ' if caps else '')+('pseudo ≥1.3 rendered width' if language=='pseudo' else 'format'),
  'source_text':original,'delta':delta,'pseudo_k':k,
  'pseudo_base_width_su':measure(original,role) if k is not None else None,
  'pseudo_width_su':measure(value,role) if k is not None else None}

def wrap(value,width,role='type.body'):
 lines=['']
 for word in value.split():
  candidate=(lines[-1]+' '+word).strip()
  if lines[-1] and measure(candidate,role)>width:lines.append(word)
  else:lines[-1]=candidate
 if any(measure(line,role)>width for line in lines):raise ValueError(('unbreakable text',lines,width))
 return lines

def defaults():
 import re
 text=(ROOT/SETTINGS).read_text(encoding='utf-8')
 result={}
 for field in ('MasterVolume','bMasterMuted','MusicVolume','SfxVolume','UiVolume','VoVolume','AmbienceVolume',
  'bAmbienceMuted','bSubtitles','bDescribeSounds','AnimSpeed','bReducedMotion','bRuleHints','KeyHintsMode','UiScalePercent','bScreenShake'):
  m=re.search(r'\b'+field+r'\s*=\s*(TEXT\("[^"]+"\)|true|false|\d+)\s*;',text)
  if not m:raise ValueError(field)
  raw=m.group(1); value=raw[6:-2] if raw.startswith('TEXT(') else raw=='true' if raw in ('true','false') else int(raw)
  result[field]={'value':value,'file':SETTINGS,'line':text[:m.start()].count('\n')+1,'field':field}
 return result

def sound_rows():
 d=defaults(); rows=[]
 for key,field in [('master','MasterVolume'),('music','MusicVolume'),('effects','SfxVolume'),('interface','UiVolume'),('voices','VoVolume'),('ambience','AmbienceVolume')]:
  row={'kind':'slider','key':'settings.sound.'+key,'value':d[field]['value'],'fact':d[field],'min':0,'max':100}
  if key in ('master','ambience'):
   field='bMasterMuted' if key=='master' else 'bAmbienceMuted'
   row.update(mute=d[field]['value'],mute_fact=d[field])
  rows.append(row)
 for key,field in [('subtitles','bSubtitles'),('describe','bDescribeSounds')]:
  rows.append({'kind':'check','key':'settings.sound.'+key,'value':d[field]['value'],'fact':d[field]})
 return rows

def interface_rows(language='ru',scale=None,minimum=75,range_note=False,hints=False):
 d=defaults()
 rows=[{'kind':'chips','key':'settings.interface.language','options':['settings.interface.language.ru','settings.interface.language.en'],
  'selected':1 if language=='en' else 0,'own_names':True,'fact':{'file':'docs/game-design/visual/04-hud-spec.md','key':'§1.8 / UI-ACC-010','value':'en' if language=='en' else 'ru'}},
  {'kind':'slider','key':'settings.interface.scale','value':d['UiScalePercent']['value'] if scale is None else scale,'min':minimum,'max':150,
   'fact':d['UiScalePercent'] if scale is None else {'file':SERIES,'key':'ВР-VS5-SC27-01','value':scale}},
  {'kind':'check','key':'settings.interface.rule_hints','value':d['bRuleHints']['value'],'fact':d['bRuleHints']},
  {'kind':'chips','key':'settings.interface.key_hints','options':['settings.interface.key_hints.'+v for v in ('auto','on','off')],
   'selected':('auto','on','off').index(d['KeyHintsMode']['value']),'fact':d['KeyHintsMode']}]
 if range_note:rows[1].update(note='settings.interface.scale.range',note_args={'min':minimum,'max':150})
 if hints:rows[3].update(note='settings.interface.key_hints.note',sample=True)
 return rows

def game_rows():
 d=defaults(); options=['none','fast','normal','slow']
 return [{'kind':'chips','key':'settings.game.anim_speed','options':['settings.game.anim_speed.'+o for o in options],
  'selected':options.index(d['AnimSpeed']['value']),'fact':d['AnimSpeed']},
  {'kind':'check','key':'settings.game.reduced_motion','value':d['bReducedMotion']['value'],'fact':d['bReducedMotion']}]

def graphics_rows():
 return [{'kind':'chips','key':'settings.graphics.quality','options':['settings.graphics.quality.'+v for v in ('high','medium','low')],
  'selected':0,'fact':{'file':'docs/art-pipeline/render-reference.json','line':18,'key':'sg.*','value':2},'note':'settings.graphics.note'}]

def intersection(a,b):
 return max(0,min(a[0]+a[2],b[0]+b[2])-max(a[0],b[0]))*max(0,min(a[1]+a[3],b[1]+b[3])-max(a[1],b[1]))

class PauseCanvas(Canvas):
 def __init__(self,vp,background):
  super().__init__(vp,theme(),background)
  self.components={};self.edges=[];self.icons=[];self.rows=[];self.layer_name='PauseModal'
 def record(self,name,rect,**kw):
  self.components[name]={'rect_su':list(rect),'kind':'modal',**kw}
 def text(self,xy,value,role='type.body',color='text.primary',anchor='lt',source=None):
  # Capture the local background before printing, including selected/primary bodies.
  ink=self.theme.color(color) if isinstance(color,str) else color
  point=(self.px(xy[0]),self.px(xy[1]))
  point=(min(self.image.width-1,max(0,point[0])),min(self.image.height-1,max(0,point[1])))
  bg=self.image.getpixel(point)[:3]
  result=super().text(xy,value,role,color,anchor,source)
  run=self.text_runs[-1];run.update(background=bg,panel=self.layer_name,
   contrast_color=contrast(ink,bg),contrast_gray=contrast(gray_rgb(ink),gray_rgb(bg)))
  return result
 def text_named(self,name,rect,key,language='ru',role='type.body',color='text.primary',align='left',caps=False,**args):
  value,src=string(key,language,role,caps,**args);x,y,w,h=rect
  self.record(name,rect,key=key)
  xy=(x+w/2,y+h/2) if align=='center' else (x+w,y+h/2) if align=='right' else (x,y+h/2)
  anchor='mm' if align=='center' else 'rm' if align=='right' else 'lm'
  self.text(xy,value,role,color,anchor,src);self.text_runs[-1].update(name=name,slot_su=list(rect))
  return value,src
 def label_lines(self,name,x,y,width,key,language,role='type.body',color='text.primary',**args):
  value,src=string(key,language,role,**args);lines=wrap(value,width,role);height=20 if role=='type.body' else 18
  self.record(name,(x,y,width,len(lines)*height),key=key,lines=lines)
  for i,line in enumerate(lines):
   self.text((x,y+i*height+height/2),line,role,color,'lm',dict(src,wrapped_line=i+1))
   self.text_runs[-1].update(name=name+'.Line'+str(i+1),slot_su=[x,y+i*height,width,height])
  return len(lines)*height
 def button_named(self,name,rect,key,language,primary=False,disabled=False,icon=False):
  label,src=string(key,language,'type.button',True);x,y,w,h=rect
  if not icon:
   start=len(self.text_runs);self.button(rect,label,primary=primary,source=src)
   self.text_runs[start].update(name=name+'.Text',slot_su=list(rect))
  else:
   self.skin(rect,'Btn_Disabled' if disabled else 'Btn_Normal')
   group=24+8+measure(label,'type.button');left=x+(w-group)/2
   self.icon(name+'.Icon',(left,y+12,24,24),'badge-refuse',.4 if disabled else 1)
   self.text((left+32,y+24),label,'type.button','text.primary','lm',src)
   self.text_runs[-1].update(name=name+'.Text',slot_su=[left+32,y,measure(label,'type.button')+1,h])
  self.record(name,rect,primary=primary,disabled=disabled)
  self.edge(name,rect,inactive=disabled)
 def edge(self,name,rect,inactive=False):
  self.edges.append({'name':name,'rect_su':list(rect),'inactive':inactive,'layer':self.layer_name})
 def icon(self,name,rect,icon_name,opacity=1):
  x,y,w,h=rect;px=round(w*self.viewport.factor)
  source=ROOT/f'art/imagegen/hud-icons-v3/sizes/{icon_name}-{px}.png'
  if source.exists():im=Image.open(source).convert('RGBA');method='native PNG'
  else:
   import draw_icons_v3_snapshot as icons
   im=icons.render(icon_name,px);source=Path(__file__).with_name('draw_icons_v3_snapshot.py');method='render(name,px)'
  assert im.size==(px,px)
  if opacity!=1:
   im=im.copy();im.putalpha(im.getchannel('A').point(lambda a:round(a*opacity)))
  self.image.alpha_composite(im.resize((px*self.ss,px*self.ss),Image.Resampling.LANCZOS),(self.px(x),self.px(y)))
  self.record(name,rect)
  self.icons.append({'name':name,'icon':icon_name,'rect_su':list(rect),'px':px,'source':str(source),
   'method':method,'opacity':opacity,'image':im})

def gray_rgb(rgb):
 n=round(sum(a*b for a,b in zip(rgb,(.2126,.7152,.0722))))
 return (n,n,n)

def row_plan(row,language,vp):
 r=dict(row);key=r['key'];label=string(key,language)[0]
 if r['kind']=='sample' and not r.get('options'):
  r['band']=88 if vp.layout_class=='L' else 64;r['height']=r['band']+16;r['label_lines']=[]
  return r
 if r['kind'] in ('slider','check'):
  r['label_lines']=wrap(label,140);r['band']=max(48,len(r['label_lines'])*20)
  r['height']=r['band']+16
 elif r['kind'] in ('chips','sample'):
  r['label_lines']=wrap(label,512);r['chips']=[];xx=0;yy=0
  for i,k in enumerate(r['options']):
   lang='ru' if r.get('own_names') and language!='pseudo' else language
   text,src=string(k,lang,'type.caption');w=measure(text,'type.caption')+24
   if xx and xx+w>512:xx=0;yy+=40
   r['chips'].append({'key':k,'language':lang,'x':xx,'y':yy,'w':w,'selected':i==r['selected']});xx+=w+8
  r['chips_height']=yy+32;r['chip_line_count']=yy//40+1
  r['band']=len(r['label_lines'])*20+8+r['chips_height'];r['height']=r['band']+16
 else:
  r['label_lines']=wrap(string(key,language,'type.caption')[0],512,'type.caption')
  r['band']=len(r['label_lines'])*18;r['height']=r['band']+16
 if r.get('note'):
  width=512
  if r.get('sample'):
   r['sample_size']=(102,88) if vp.layout_class=='L' else (64,64)
   note=string(r['note'],language,'type.caption',**r.get('note_args',{}))[0]
   chips_right=max(c['x']+c['w'] for c in r['chips'])
   r['sample_below']=max(chips_right,measure(note,'type.caption'))+16+r['sample_size'][0]>512
   if not r['sample_below']:width=512-r['sample_size'][0]-16
  note=string(r['note'],language,'type.caption',**r.get('note_args',{}))[0]
  r['note_lines']=wrap(note,width,'type.caption');r['height']+=8+len(r['note_lines'])*18
  if r.get('sample'):
   if r['sample_below']:r['height']+=8+r['sample_size'][1]
   else:r['height']=max(r['height'],16+20+8+r['sample_size'][1])
 return r

def draw_sample(c,x,y,vp,language):
 large=vp.layout_class=='L';cw,ch=(86,72) if large else (48,48);size=48 if large else 40
 c.record('KeyHintSample',(x,y,cw+16,ch+16));c.rounded((x,y,cw+16,ch+16),theme().color('panel.bg.inset'),4)
 x+=8;y+=8;c.record('KeyHintSample.Cell',(x,y,cw,ch));c.skin((x,y,cw,ch),'Btn_Normal');c.edge('KeyHintSample.Cell',(x,y,cw,ch))
 c.icon('KeyHintSample.Disc',(x+(cw-size)/2,y+4,size,size),'action-end-turn')
 if large:
  value,src=string('hud.action.end_turn','ru','type.tag',True)
  c.text((x+cw/2,y+67),value,'type.tag','text.primary','ms',src)
  c.record('KeyHintSample.Label',(x,y+54,cw,18));c.text_runs[-1].update(name='KeyHintSample.Label',slot_su=[x,y+54,cw,18])
 key=(x+cw-22,y+2,20,20);c.record('KeyHintSample.KeyChip',key)
 value,src=string('hud.key.end_turn','ru','type.caption')
 c.key_chip(key,value,source=src);c.text_runs[-1].update(name='KeyHintSample.KeyChip.Text',slot_su=list(key))

def draw_row(c,r,x,y,language,vp,visible=True):
 name='Row_'+r['key'];h=r['height'];c.record(name,(x,y,520,h),row_kind=r['kind'],visible=visible,
  value=r.get('value'),selected=r.get('selected'),fact=r.get('fact'),chip_line_count=r.get('chip_line_count'),sample_below=r.get('sample_below'))
 if not visible:
  # Preserve geometry of every child even when its row is offscreen, without
  # printing hidden text or counting it in visible contrast/overlap checks.
  saved=c.image.copy();nt=len(c.text_runs);ne=len(c.edges);ni=len(c.icons)
  draw_row(c,r,x,y,language,vp,True)
  c.image=saved;del c.text_runs[nt:];del c.edges[ne:];del c.icons[ni:]
  for child,item in c.components.items():
   if child==name or child.startswith(name+'.'):item['visible']=False
  return
 band=r['band'];kind=r['kind'];base=y+8
 if kind in ('slider','check'):
  lab_h=len(r['label_lines'])*20
  c.label_lines(name+'.Label',x,base+(band-lab_h)/2,140,r['key'],language)
  mid=base+band/2
  if kind=='check':
   cr=(x+148,mid-12,24,24);c.checkbox(cr[:2],r['value']);c.record(name+'.Check',cr,checked=r['value']);c.edge(name+'.Check',cr)
   c.text_named(name+'.Value',(x+180,mid-12,90,24),'settings.value.on' if r['value'] else 'settings.value.off',language,color='text.secondary')
  else:
   track=(x+148,mid-4,200,8);c.skin(track,'SliderTrack');c.record(name+'.Slider',track,min=r['min'],max=r['max'],value=r['value'])
   amount=(r['value']-r['min'])/(r['max']-r['min']);amount=max(0,min(1,amount))
   if amount:c.rounded((x+149,mid-3,max(.5,198*amount),6),theme().color('card.cream'),3)
   thumb=(x+148+200*amount-8,mid-8,16,16);c.skin(thumb,'SliderThumb');c.record(name+'.Slider.Thumb',thumb)
   value=string('settings.value.percent',language,n=r['value'])[0];vw=max(56,measure(value)+2)
   c.text_named(name+'.Value',(x+356,mid-12,vw,24),'settings.value.percent',language,align='right',n=r['value'])
   if 'mute' in r:
    cr=(x+420,mid-12,24,24);c.checkbox(cr[:2],r['mute']);c.record(name+'.Mute',cr,checked=r['mute']);c.edge(name+'.Mute',cr)
    c.label_lines(name+'.Mute.Label',x+452,mid-18,60,'settings.sound.mute',language,'type.caption','text.secondary')
  if r.get('note'):c.label_lines(name+'.Note',x,base+band+8,512,r['note'],language,'type.caption','text.secondary',**r.get('note_args',{}))
 elif kind=='sample' and not r.get('options'):
  draw_sample(c,x,base,vp,language)
 elif kind in ('chips','sample'):
  lab_h=c.label_lines(name+'.Label',x,base,512,r['key'],language);cy=base+lab_h+8
  c.record(name+'.Chips',(x,cy,512,r['chips_height']),lines=r['chip_line_count'])
  for i,ch in enumerate(r['chips']):
   rect=(x+ch['x'],cy+ch['y'],ch['w'],32);v,src=string(ch['key'],ch['language'],'type.caption')
   c.chip(rect,v,ch['selected'],source=src);c.record(name+'.Chips.'+str(i+1),rect,selected=ch['selected'])
   c.text_runs[-1].update(name=name+'.Chips.'+str(i+1)+'.Text',slot_su=list(rect));c.edge(name+'.Chips.'+str(i+1),rect)
  if r.get('note'):
   ny=cy+r['chips_height']+8;nh=c.label_lines(name+'.Note',x,ny,512 if not r.get('sample') or r['sample_below'] else 512-r['sample_size'][0]-16,
    r['note'],language,'type.caption','text.secondary',**r.get('note_args',{}))
   if r.get('sample'):
    sx=x if r['sample_below'] else x+512-r['sample_size'][0];sy=ny+nh+8 if r['sample_below'] else cy
    draw_sample(c,sx,sy,vp,language)
 elif kind=='note':c.label_lines(name+'.Note',x,base,512,r['key'],language,'type.caption','text.secondary')

def draw_pause(*,viewport,background='marmoreal',open_tab='sound',header_lines=None,rows=None,
 footer_buttons=None,confirm_dialog=False,language='ru',state='game',caption=False,scroll_offset=0):
 """Full reusable modal API; arbitrary Viewport and parameterised contents.

 Footer specs: name/key/primary/icon/disabled. Header specs: name/key/type/color/args.
 Rows: slider/check/chips/note/sample; explicit row dictionaries, not screenshots.
 """
 vp=viewport;c=PauseCanvas(vp,Image.open(ROOT/BG[background]));c.veil()
 if header_lines is None:
  header_lines=[{'name':'TitleText','key':'screens.pause.title','type':'type.title'}]
  if state!='menu':header_lines.append({'name':'StatusText','key':'screens.pause.running','color':'text.secondary'})
  if state=='game-defense':header_lines.append({'name':'DefenseText','key':'screens.pause.defense.left','args':{'n':30}})
 if rows is None:rows=sound_rows()
 plans=[row_plan(r,language,vp) for r in rows];total=sum(r['height'] for r in plans)
 if footer_buttons is None:
  footer_buttons=[] if state=='menu' else [{'name':'LeaveButton','key':'screens.pause.leave','icon':True,'disabled':state=='syncing'}]
  footer_buttons.append({'name':'ContinueButton','key':'screens.pause.continue','primary':True})
 header_h=16+sum((34 if s.get('type')=='type.title' else 24)+8 for s in header_lines)-8+16+1+16
 footer_h=16+1+16+48+16+(22 if any(b.get('disabled') for b in footer_buttons) else 0)
 W,H=vp.canvas;desired=header_h+max(216,total)+footer_h;mh=min(800,H-2*vp.margin,desired)
 if mh<header_h+216+footer_h:raise ValueError('viewport cannot contain fixed tabs/header/footer')
 visible=mh-header_h-footer_h;scroll=visible<total
 x=(W-720)/2;y=(H-mh)/2;c.panel((x,y,720,mh));c.record('PauseModal',(x,y,720,mh));c.edge('PauseModal',(x,y,720,mh))
 cy=y+16
 for s in header_lines:
  role=s.get('type','type.body');lh=34 if role=='type.title' else 24
  c.text_named(s['name'],(x+16,cy,688,lh),s['key'],language,role,s.get('color','text.primary'),**s.get('args',{}));cy+=lh+8
 divider=y+header_h-17;c.line([(x+16,divider),(x+704,divider)],mix(theme().color('panel.divider'),theme().color('panel.bg'),.16))
 by=y+header_h;c.record('TabList',(x+16,by,160,216))
 for i,tab in enumerate(('sound','interface','game','graphics')):
  name='Tab'+tab.capitalize();rect=(x+16,by+i*56,160,48);v,src=string('settings.tab.'+tab,language,'type.button',True)
  c.button(rect,v,state='selected' if tab==open_tab else 'normal',source=src);c.record(name,rect,selected=tab==open_tab)
  c.text_runs[-1].update(name=name+'.Text',slot_su=list(rect));c.edge(name,rect)
 rx=x+184;c.record('RowsPanel',(rx,by,520,visible),total_height_su=total,visible_height_su=visible,scroll=scroll)
 before=c.image.copy();start_text=len(c.text_runs);offset=min(max(0,scroll_offset),max(0,total-visible));ry=by-offset
 for r in plans:
  fully=ry>=by-1e-6 and ry+r['height']<=by+visible+1e-6
  draw_row(c,r,rx,ry,language,vp,fully)
  c.rows.append({k:v for k,v in r.items() if k not in ('chips',)}|{'visible':fully,'y_su':ry})
  ry+=r['height']
  if ry<by+visible:c.line([(rx,ry),(rx+512,ry)],mix(theme().color('panel.divider'),theme().color('panel.bg'),.16))
 # Keep strict clipping even for arbitrary offset: only the RowsPanel patch survives.
 patch=c.image.crop((c.px(rx),c.px(by),c.px(rx+520),c.px(by+visible)))
 c.image=before;c.image.paste(patch,(c.px(rx),c.px(by)))
 if scroll:
  sr=(rx+512,by,4,visible);c.rounded(sr,theme().color('panel.bg.inset'),2)
  th=visible*visible/total;ty=by+offset/total*visible;c.rounded((sr[0],ty,4,th),theme().color('card.cream'),2)
  c.record('ScrollBar',sr,total_su=total,visible_su=visible,thumb_height_su=th,offset_su=offset)
 fy=by+visible+33;c.line([(x+16,fy-17),(x+704,fy-17)],mix(theme().color('panel.divider'),theme().color('panel.bg'),.16))
 for b in footer_buttons:
  value=string(b['key'],language,'type.button',True)[0];width=max(168,measure(value,'type.button')+48+(32 if b.get('icon') else 0))
  bx=x+704-width if b.get('primary') else x+16
  c.button_named(b['name'],(bx,fy,width,48),b['key'],language,b.get('primary',False),b.get('disabled',False),b.get('icon',False))
  if b.get('disabled'):c.text_named('LeaveWhy',(bx,fy+52,width,18),'why.syncing',language,'type.caption','text.secondary')
 if caption:
  text='фон-заглушка: в игре фигур нет (ВР-75)';maxw=max(96,x-vp.margin-8-24)
  lines=wrap(text,maxw,'type.caption');cw=max(measure(v,'type.caption') for v in lines)+24;ch=12+len(lines)*18+6
  cr=(vp.margin,H-vp.margin-ch,cw,ch);c.panel(cr,'screen');c.record('CaptionPanel',cr,kind_override='screen')
  c.components['CaptionPanel']['kind']='screen'
  for i,line in enumerate(lines):
   c.text((cr[0]+12,cr[1]+6+i*18+9),line,'type.caption','text.secondary','lm',{'file':SERIES,'key':'ВР-VS5-SC24-04 / ВР-75'})
   c.text_runs[-1].update(name='CaptionPanel.Text'+str(i+1),slot_su=[cr[0]+12,cr[1]+6+i*18,cw-24,18])
 if confirm_dialog:
  c.layer_name='ConfirmDialog';start=len(c.text_runs)
  keys=['screens.pause.leave','screens.pause.leave.confirm','common.confirm.cancel','common.confirm.yes']
  vals={k:string(key,language,'type.title' if k=='title' else 'type.body' if k=='body' else 'type.button',k in ('cancel','confirm'))[0]
   for k,key in zip(('title','body','cancel','confirm'),keys)}
  draw_base_modal(c,vals)
  cr=modal_rect(vp);cx,cy,cw,ch=cr;c.record('ConfirmDialog',cr);c.edge('ConfirmDialog',cr)
  slots=[(cx+16,cy+16,608,34),(cx+16,cy+64,608,24),(cx+272,cy+296,168,48),(cx+456,cy+296,168,48)]
  for i,(name,key,slot) in enumerate(zip(('Title','Body','CancelButton','YesButton'),keys,slots)):
   c.record('ConfirmDialog.'+name,slot,primary=name=='YesButton')
   run=c.text_runs[start+i];run.update(name='ConfirmDialog.'+name,slot_su=list(slot),source=string(key,language,run['type'],name.endswith('Button'))[1])
 return c, {'background':background,'state':state,'language':language,'canvas_px':[vp.width,vp.height],'canvas_su':list(vp.canvas),
  'factor':vp.factor,'ui':vp.ui,'class':vp.layout_class,'modal_height_su':mh,'desired_height_su':desired,'total_rows_height_su':total,
  'visible_rows_height_su':visible,'scroll':scroll,'offset_su':offset,'row_count':len(rows),'confirm':bool(confirm_dialog)}

if __name__=='__main__':
 from package_support import run_package
 run_package(24)
