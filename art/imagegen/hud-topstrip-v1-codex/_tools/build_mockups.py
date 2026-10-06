"""HB-13 offline native-size renderer. Writes only the two authorized roots.
Run: python -B -X utf8 art/imagegen/hud-topstrip-v1-codex/_tools/build_mockups.py
No imports of the icon generator, git, subprocesses, network or Unreal.
"""
from pathlib import Path
from functools import lru_cache
import csv, hashlib, json, math, os, re
import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageFilter

ROOT = Path(__file__).resolve().parents[4]
PKG = ROOT / 'art/imagegen/hud-topstrip-v1-codex'
DERIVED = ROOT / 'scraped-data/derived/hud-topstrip-v1-codex'
HB07 = ROOT / 'art/imagegen/hud-composition-v1-codex'
FONT = Path('C:/Program Files/Epic Games/UE_5.8/Engine/Content/Slate/Fonts')
T = dict(body='#061623', edge='#F9EBDB', inset='#15232E', primary='#F2EDE4', secondary='#B9B2A6', yellow='#F2C14E', error='#D9483F', glyph='#FAF8F2')
STATES = ['own-action','own-action-keys','own-fighter','own-space','own-target','own-scheme','defend','defend-keys','discard','choice','opp-turn','opp-maneuver','syncing','lost','banner']
CONFIGS = [(1920,1080,1.0,100),(1920,1080,1.5,150),(1280,720,.75,100),(1280,720,1.125,150)]
BACKGROUNDS = {
 'marmoreal':'docs/game-design/evidence/ENV-MAPS/p7-concept-paste-2026-10-01/marmoreal-concept-flag/bench-K1-1920x1080.png',
 'sarpedon':'docs/game-design/evidence/ENV-MAPS/p10-sarpedon-rework-2026-10-03/sarpedon-packaged/bench-K1-1920x1080.png'}
EXCLUDED = {'.git','unreal','node_modules','.agents','.codex','.aws','.venv','venv','__pycache__','.next','.svelte-kit','dist','build'}
WRITES=[]

def load(p): return json.loads(Path(p).read_text(encoding='utf-8'))
def sha(p): return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def rel(p): return Path(p).relative_to(ROOT).as_posix() if Path(p).is_relative_to(ROOT) else Path(p).as_posix()
def write(p,data):
 p=Path(p).resolve(); assert p.is_relative_to(PKG) or p.is_relative_to(DERIVED)
 p.write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
 WRITES.append(rel(p))
def rgb(k):
 v=T.get(k,k).lstrip('#'); return tuple(bytes.fromhex(v))
def luma(a):
 a=np.asarray(a,dtype=float)/255; a=np.where(a<=.04045,a/12.92,((a+.055)/1.055)**2.4)
 return a@np.array([.2126,.7152,.0722])
def ratio(a,b):
 a,b=luma(a),luma(b);return (np.maximum(a,b)+.05)/(np.minimum(a,b)+.05)
def gray(im):
 a=np.asarray(im); out=a.copy(); out[:,:,:3]=np.rint(a[:,:,:3]@np.array([.2126,.7152,.0722])).astype('uint8')[:,:,None]
 return Image.fromarray(out)
@lru_cache(None)
def font(px,bold=True): return ImageFont.truetype(str(FONT/('Roboto-BoldCondensed.ttf' if bold else 'Roboto-Regular.ttf')),px)
def wrap(text,f,width):
 result=[]; line=''
 # A quoted button label is one wrapping unit; its displayed spaces stay unchanged.
 for word in re.findall(r'«[^»]*»|\S+',text):
  test=(line+' '+word).strip()
  if line and f.getlength(test)>width: result.append(line);line=word
  else: line=test
 if line:result.append(line)
 return result

STRINGS={}
for name in ['st-hud.csv','st-ms.csv']:
 p=ROOT/'docs/unreal/contracts/hud'/name
 for n,row in enumerate(csv.DictReader(p.read_text(encoding='utf-8').splitlines()),2): STRINGS[row['Key']]={**row,'source':rel(p),'line':n}
for row in load(ROOT/'docs/unreal/contracts/hud/why-reasons.json')['reasons']:
 STRINGS[row['key']]={'Key':row['key'],'ru':row['ru'],'SourceString':row['en'],'source':'docs/unreal/contracts/hud/why-reasons.json','json_key':row['key']}
F07=load(HB07/'facts.json'); MASKS=load(HB07/'masks.json')

def string(key,**args): return STRINGS[key]['ru'].format(**args)
def trace_record(p,n,line): return {'path':rel(p),'line':n,'trace':line}

@lru_cache(None)
def trace_lines(p): return p.read_text(encoding='utf-8').splitlines()

def turn_for(p,n):
 lines=trace_lines(p)
 events=[(i+1,l,re.search(r'HUD-TURN seq=(\d+) turn=(own|opp|over)',l)) for i,l in enumerate(lines) if re.search(r'HUD-TURN seq=(\d+) turn=(own|opp|over)',l)]
 hn,hl,hm=next(e for e in reversed(events) if e[0]<n)
 assert hm[2] in ['own','opp']
 end=next((i for i,_,_ in events if i>hn),len(lines)+1)
 previous=[(i+1,l) for i,l in enumerate(lines[:hn-1]) if re.search(r'S09AUTO own turn .*turnCount=',l)]
 if hm[2]=='own':
  sp=p;sn,sl=next((i+1,l) for i,l in enumerate(lines) if hn<i+1<end and re.search(r'S09AUTO own turn .*turnCount=',l))
  other_hud=None;cross=None
 else:
  sp=p.with_name('combat-client-joiner.trace.txt' if 'host' in p.name else 'combat-client-host.trace.txt');other=trace_lines(sp)
  # Shared server seq resolves second-resolution timestamp ties across clients.
  matching=[(i+1,l) for i,l in enumerate(other) if re.search(r'HUD-TURN seq='+hm[1]+r' turn=own\b',l)]
  if matching:on,ol=matching[0]
  else:
   # A late joiner's initial seq can differ from the active player's initial seq.
   on,ol=next((i+1,l) for i,l in reversed(list(enumerate(other))) if re.search(r'HUD-TURN seq=\d+ turn=own\b',l) and l[:19]<=lines[n-1][:19])
  oe=next((i+1 for i,l in enumerate(other) if i+1>on and re.search(r'HUD-TURN seq=\d+ turn=',l)),len(other)+1)
  sn,sl=next((i+1,l) for i,l in enumerate(other) if on<i+1<oe and re.search(r'S09AUTO own turn .*turnCount=',l))
  assert ol[:19]<=lines[n-1][:19] and (oe>len(other) or lines[n-1][:19]<=other[oe-1][:19])
  other_hud=trace_record(sp,on,ol)
  cross=int(re.search(r'turnCount=(\d+)',previous[-1][1])[1])+1 if previous else 1
 value=int(re.search(r'turnCount=(\d+)',sl)[1]);assert cross is None or value==cross
 return {'value':value,'n':value,'path':rel(sp),'line':sn,'trace':sl,'selection':'S09AUTO inside own HUD-TURN interval' if hm[2]=='own' else 'other client own HUD-TURN interval covering MS-STATUS time and shared seq','ms_status':trace_record(p,n,lines[n-1]),'hud_turn':trace_record(p,hn,hl),'s09auto':trace_record(sp,sn,sl),'other_client_hud_turn':other_hud,'previous_own_plus_one':cross}

def trace_for(board,state,key,args):
 p=ROOT/F07['boards'][board]['turn']['path']; lines=p.read_text(encoding='utf-8').splitlines()
 en=STRINGS[key]['SourceString'].format(**args)
 # Older live traces have inline key hints; the new StringTable deliberately removed them.
 def normalize(t):return re.sub(r' \([MAGN]\)','',t)
 found=[]
 for n,line in enumerate(lines,1):
  m=re.search(r'MS-STATUS.*text="(.*?)"',line)
  if m and normalize(m[1])==normalize(en): found.append((n,line))
 if found:
  n,line=found[0]
  return trace_record(p,n,line),turn_for(p,n)
 # Preserve the accepted illustrative string, and explicitly reuse own-action's turn.
 trace,turn=trace_for(board,'own-action','ms.status.action',{})
 return None,{**turn,'inherited_from':'own-action','inheritance_reason':'No matching MS-STATUS in run I for this illustrative state; repeats the own-action turn'}

def state_fact(board,state):
 owner='Medusa' if board=='marmoreal' else 'King Arthur'; opponent='King Arthur' if board=='marmoreal' else 'Medusa'
 key={'own-action':'ms.status.action','own-action-keys':'ms.status.action','own-fighter':'ms.status.fighter','own-space':'ms.status.space','own-target':'ms.status.target','own-scheme':'ms.status.scheme','defend':'ms.status.defend','defend-keys':'ms.status.defend','discard':'ms.status.discard','choice':'ms.status.choice','opp-turn':'ms.status.opp','opp-maneuver':'ms.status.opp','syncing':'why.syncing','lost':'ms.status.action','banner':'ms.status.action'}[state]
 args={}; additional={}
 if state in ['own-space','own-target']:args={'fighterName':owner}
 if state=='discard':args={'n':2};additional['n_source']='docs/game-design/visual/04-hud-spec.md §2.5 example; NOT match data; run I contains no discard state'
 inherited={'own-action-keys':'own-action','defend-keys':'defend','discard':'own-action','lost':'own-action','banner':'own-action'}.get(state)
 if inherited:
  base=state_fact(board,inherited);trace=None;turn={**base['turn'],'inherited_from':inherited,'inheritance_reason':'keys variant of base state' if state.endswith('-keys') else 'repeats own-action; no separate MS-STATUS for this mockup state'}
 elif state=='choice':
  en,ru,field,title=('You may BOOST this attack.','Можете усилить эту атаку.','effectDuring','Second Shot') if board=='marmoreal' else ('Your opponent discards 1 card.','Ваш противник сбрасывает 1 карту.','effectAfter','Hiss and Slither')
  hero='scraped-data/api/heroes/medusa.json'; atoms=load(ROOT/hero)['nodes'][2]['data']
  assert ru in atoms and any(isinstance(v,str) and v.strip()==en for v in atoms)
  cards=F07['decoded_hero_sources']['medusa']['fetchedDeck']; card=next(c for c in cards if c['card']['title']==title)
  assert card['card']['i18n']['ru'][field]==ru
  args={'choice':ru};additional['choice']={'source':hero,'card':title,'card_id':card['card']['id'],'field':'card.i18n.ru.'+field,'ru_atom_index':atoms.index(ru),'pending_en':en,'effect_matches':[c['card']['title'] for c in cards if c['card'].get(field) and c['card'][field].strip()==en]}
  # English lookup uses the pending sentence actually emitted by this HUD owner.
  trace,turn=trace_for(board,state,key,{'choice':en})
 else:
  if state.startswith('opp-'):
   verb='ms.opp.phase.turn' if state=='opp-turn' else 'ms.opp.planning';args={'player':opponent,'verb':string(verb)};additional['verb_key']=verb
   trace,turn=trace_for(board,state,key,{'player':opponent,'verb':STRINGS[verb]['SourceString']})
  else:trace,turn=trace_for(board,state,key,args)
 chips=['hud.key.maneuver','hud.key.attack','hud.key.scheme'] if state=='own-action-keys' else ['hud.key.no_defense'] if state=='defend-keys' else []
 return {'owner':owner,'opponent':opponent,'key':key,'arguments':args,'text':string(key,**args),'trace':trace,'turn':turn,'chips':chips,'connection':'syncing' if state=='syncing' else 'lost' if state=='lost' else 'online','argument_sources':additional,'name_source':'C:/tmp/visual/CX-01r/db-names-2026-10-06.txt; scraped-data/api/heroes/{medusa,king-arthur}.json; names are database values, not declined RU examples'}
FACTS={b:{st:state_fact(b,st) for st in STATES} for b in BACKGROUNDS}

@lru_cache(None)
def masks(board,w,h):
 q=w/1920; info=MASKS['topology_transforms'][f'{board}-{w}x{h}']
 spaces=Image.new('L',(w,h)); d=ImageDraw.Draw(spaces)
 for v in info['spaces']:d.polygon([tuple(p) for p in v['polygon_px']],fill=255)
 spaces=spaces.filter(ImageFilter.MaxFilter(2*info['cell_conservative_dilation_px']+1))
 figures=Image.new('L',(w,h));d=ImageDraw.Draw(figures)
 for poly in MASKS['figure_polygons_1080p'][board]:d.polygon([(round(x*q),round(y*q)) for x,y in poly],fill=255)
 figures=figures.filter(ImageFilter.MaxFilter(2*info['figure_conservative_dilation_px']+1))
 return np.asarray(spaces)>0,np.asarray(figures)>0

def geometry(f,w,h,s,ui,literal=False):
 W=w/s; small=ui==150; cap=600 if small else 880 if w==1920 else 720
 top=[16,16,236,40] if small else [24,24,252,44]; y=16 if small else 24
 chips=[max(20,font(math.ceil(14*s)).getlength(string(k))/s+8) for k in f['chips']]
 chip_total=sum(chips)+8*max(0,len(chips)-1)+(12 if chips else 0)
 dot=18 if f['key']=='ms.status.opp' else 0 # 10su circle + 8su gap
 for ts in [24,20,16]:
  ft=font(math.ceil(ts*s)); lines=wrap(f['text'],ft,(cap-32-chip_total-dot)*s)
  if len(lines)<=2 and max(ft.getlength(l) for l in lines)<=(cap-32-chip_total-dot)*s:break
 else:raise ValueError(f['text'])
 measured=ft.getlength(f['text'])/s
 sw=cap if len(lines)>1 else min(cap,measured+32+chip_total+dot)
 sh=max(40 if small else 48,len(lines)*ts+max(0,len(lines)-1)*2+24)
 pitch=round(1.25*ts) if len(lines)==2 else ts+2
 if len(lines)==2:sh+=(pitch-(ts+2)) # 74 -> 78su at 24su type
 recommended={'TOP':top,'STATUS':[(W-sw)/2,y,sw,sh],'BANNER':[(W-420)/2,144,420,64]}
 original={'TOP':top.copy(),'STATUS':[(W-cap)/2,y,cap,40 if small else 48],'BANNER':[(W-420)/2,144,420,64]}
 return {'rectangles':original if literal else recommended,'literal_04':original,'lines':lines,'type_su':ts,'line_pitch_su':pitch,'text_width_su':measured,'cap_su':cap,'chips_width_su':chips,'dot_su':dot,'class':'S' if small else 'L'}

class Canvas:
 def __init__(self,base,s):
  self.base=base.convert('RGBA');self.im=self.base.copy();self.hud=Image.new('RGBA',base.size);self.procedural=Image.new('RGBA',base.size);self.s=s;self.text_records=[];self.icon_records=[];self.mask_records=[]
 def box(self,r):
  x,y,w,h=r;return (round(x*self.s),round(y*self.s),round((x+w)*self.s)-1,round((y+h)*self.s)-1)
 def primitive(self,layer):
  self.im.alpha_composite(layer);self.hud.alpha_composite(layer);self.procedural.alpha_composite(layer)
 def panel(self,r,inset=False):
  layer=Image.new('RGBA',self.im.size);d=ImageDraw.Draw(layer);d.rounded_rectangle(self.box(r),radius=max(1,round(4*self.s)),fill=rgb('inset' if inset else 'body')+(255 if inset else 235,),outline=rgb('edge')+(115,),width=max(1,round(self.s)));self.primitive(layer)
 def text(self,value,x,y,size,color='primary',bold=True):
  # Rasterize the font once at actual output size; no master texture scaling.
  ft=font(math.ceil(size*self.s),bold); mask=Image.new('L',self.im.size);d=ImageDraw.Draw(mask);d.text((round(x*self.s),round(y*self.s)),value,font=ft,fill=255,anchor='lt')
  layer=Image.new('RGBA',self.im.size,rgb(color)+(0,));layer.putalpha(mask)
  self.primitive(layer); a=np.asarray(mask);pixels=np.asarray(self.im)[:,:,:3][a==255]
  contrast=float(np.min(ratio(rgb(color),np.asarray(self.base)[:,:,:3][a==255]))) if len(pixels) else 0
  # Record ground before text separately in renderer; a glyph's output pixels are not its ground.
  self.text_records.append({'text':value,'type_su':size,'font_px':math.ceil(size*self.s),'nominal_px':size*self.s,'bbox_px':mask.getbbox(),'color':T[color]})
  self.mask_records.append(mask)
 def dot(self,x,y):
  layer=Image.new('RGBA',self.im.size);n=math.ceil(10*self.s);px,py=round(x*self.s),round(y*self.s);box=(px,py,px+n-1,py+n-1);ImageDraw.Draw(layer).ellipse(box,fill=rgb('secondary')+(255,));self.primitive(layer)
  return {'diameter_su':10,'diameter_px':n,'gap_su':8,'bbox_px':[px,py,px+n,py+n],'color':T['secondary']}
 def icon(self,kind,x,y):
  name='reconnecting' if kind=='syncing' else kind;p=ROOT/f'art/imagegen/hud-icons-v3/sizes/resource-connection-{name}-96.png';src=Image.open(p).convert('RGBA');n=round(24*self.s);im=src.resize((n,n),Image.Resampling.LANCZOS);pos=(round(x*self.s),round(y*self.s))
  ground=np.asarray(self.im)[pos[1]:pos[1]+n,pos[0]:pos[0]+n,:3].copy();sa=np.asarray(src)
  roles=['glyph'] if kind=='online' else ['secondary','glyph'] if kind=='syncing' else ['secondary','error']
  pairs=[]
  for role in roles:
   mask=(sa[:,:,3]==255)&np.all(sa[:,:,:3]==rgb(role),axis=2);assert np.any(mask)
   fit=np.asarray(Image.fromarray(mask.astype('uint8')*255).resize((n,n),Image.Resampling.NEAREST))>0
   # Bare glyph ground is either dark icon keyline or the alpha-composited panel.
   pairs.append({'role':role,'foreground':T[role],'panel_min':float(np.min(ratio(rgb(role),ground[fit]))),'keyline':float(ratio(rgb(role),(17,19,23)))})
  self.im.alpha_composite(im,pos);self.hud.alpha_composite(im,pos)
  self.icon_records.append({'path':rel(p),'sha256':sha(p),'size_su':24,'size_px':n,'pairs':pairs,'minimum':min(min(v['panel_min'],v['keyline']) for v in pairs),'method':'fixed semantic roles versus underlying panel and accepted icon keyline; AA excluded; no recolor'})

def block_contrast(base,r,s,fg):
 x0,y0,x1,y1=Canvas(base,s).box(r);patch=np.asarray(base)[y0+2:y1-1,x0+2:x1-1,:3]
 body=np.array(rgb('body'));ground=np.rint(body*(235/255)+patch*(20/255)).astype('uint8');ls=luma(ground);flat=ground.reshape(-1,3)
 return {'minimum':float(np.min(ratio(rgb(fg),ground))),'darkest_ground':flat[int(np.argmin(ls))].tolist(),'brightest_ground':flat[int(np.argmax(ls))].tolist(),'foreground':T[fg],'opacity':235/255,'method':'all interior background pixels under 0.92 panel, excluding the hairline; conservative extrema, not only glyph positions'}

def render(board,state,w,h,s,ui,base,banner_alpha=None):
 f=FACTS[board][state];g=geometry(f,w,h,s,ui);r=g['rectangles'];c=Canvas(base,s)
 c.panel(r['TOP']);x,y,ww,hh=r['TOP'];small=ui==150
 menu=string('hud.top.menu');menu_width=font(math.ceil(14*s)).getlength(menu)/s;menu_zone=40 if small else 44
 c.text(menu,x+(menu_zone-menu_width)/2,y+(hh-14)/2,14);c.icon(f['connection'],x+menu_zone+menu_zone/2-12,y+hh/2-12)
 c.text(string('hud.top.turn',n=f['turn']['value']),x+88,y+(hh-20)/2,20)
 if small:c.text(string('hud.top.log'),x+163,y+(hh-14)/2,14)
 c.panel(r['STATUS']);x,y,ww,hh=r['STATUS'];col='secondary' if state.startswith('opp-') else 'primary'
 tx=x+16+g['dot_su'];ts=g['type_su']
 pitch=g['line_pitch_su'];ft=font(math.ceil(ts*s));sy=y+12
 if len(g['lines'])==2:
  # Centre the actual ink union, at native pixels, not the nominal type box.
  heights=[ft.getbbox(line,anchor='lt')[3] for line in g['lines']]
  ink_height=max(round(i*pitch*s)+ih for i,ih in enumerate(heights))
  sy=(round(y*s)+(round((y+hh)*s)-round(y*s)-ink_height)//2)/s
 pulse=None
 if g['dot_su']:
  cap_height=ft.getbbox('H',anchor='lt')[3];n=math.ceil(10*s)
  pulse=c.dot(tx-8-10,(round(sy*s)+cap_height/2-n/2)/s)
  pulse['cap_height_middle_px']=round(sy*s)+cap_height/2
  pulse['centre_y_px']=(pulse['bbox_px'][1]+pulse['bbox_px'][3])/2
 status_start=len(c.text_records)
 for i,line in enumerate(g['lines']):c.text(line,tx,sy+i*pitch,ts,col)
 status_boxes=[t['bbox_px'] for t in c.text_records[status_start:]]
 ink_top=min(b[1] for b in status_boxes);ink_bottom=max(b[3] for b in status_boxes)
 ink_top_pad=(ink_top-round(y*s))/s;ink_bottom_pad=(round((y+hh)*s)-ink_bottom)/s
 line_gap=min((b[1]-a[3] for a,b in zip(status_boxes,status_boxes[1:])),default=None)
 if f['chips']:
  cx=x+ww-16-sum(g['chips_width_su'])-8*(len(f['chips'])-1)
  for key,cw in zip(f['chips'],g['chips_width_su']):
   cy=y+(hh-20)/2;c.panel([cx,cy,cw,20],True);label=string(key);tw=font(math.ceil(14*s)).getlength(label)/s;c.text(label,cx+(cw-tw)/2,cy+3,14);cx+=cw+8
 alpha=(1 if state=='banner' else 0) if banner_alpha is None else banner_alpha
 banner_ink=None
 if alpha:
  # The requested keyframes use only opacity 0 or 1, so no alpha interpolation export.
  c.panel(r['BANNER']);x,y,ww,hh=r['BANNER'];label=string('hud.banner.own_turn');bf=font(math.ceil(36*s));tw=bf.getlength(label)/s;ih=bf.getbbox(label,anchor='lt')[3];by=(round(y*s)+(round((y+hh)*s)-round(y*s)-ih)//2)/s;c.text(label,x+(ww-tw)/2,by,36,'yellow')
  ink=c.text_records[-1]['bbox_px'];banner_ink={'ink_top_pad_px':ink[1]-round(y*s),'ink_bottom_pad_px':round((y+hh)*s)-ink[3],'ink_bbox_px':ink,'height_su':64}
 sm,fm=masks(board,w,h);over={}
 bm={}
 for key in ['TOP','STATUS']+(['BANNER'] if alpha else []):
  mask=Image.new('L',(w,h));ImageDraw.Draw(mask).rectangle(c.box(r[key]),fill=255);a=np.asarray(mask)>0;bm[key]=a
  over[key]={'figures_px2':int(np.count_nonzero(a&fm)),'spaces_px2':int(np.count_nonzero(a&sm)),'exception':key=='BANNER','rect_su':r[key]}
 for a,b in [('TOP','STATUS'),('BANNER','STATUS')]:
  if a in bm and b in bm:over[a+'-'+b]={'area_px2':int(np.count_nonzero(bm[a]&bm[b]))}
 contrast={'status':block_contrast(base,r['STATUS'],s,col),'banner':block_contrast(base,r['BANNER'],s,'yellow') if alpha else None,'chips':{'minimum':float(ratio(rgb('primary'),rgb('inset')))} if f['chips'] else None,'icons':c.icon_records}
 pa=np.asarray(c.procedural);opaque=pa[:,:,3]==255;colors=pa[opaque,:3];off=np.ones(len(colors),bool)
 for token in T:off &= np.any(colors!=rgb(token),axis=1)
 # AA pixels have fractional source coverage; the surviving fully opaque ones can be blended with panels.
 aa=np.zeros((h,w),bool)
 for mask in c.mask_records:
  a=np.asarray(mask);aa|=(a>0)&(a<255)
 actual=opaque&~aa;values=pa[actual,:3];bad=np.ones(len(values),bool)
 for token in T:bad &= np.any(values!=rgb(token),axis=1)
 palette={'opaque_non_aa_pixels':len(values),'off_token_pixels':int(np.count_nonzero(bad)),'fraction_off_tokens':float(np.mean(bad)) if len(values) else 0}
 status_width=r['STATUS'][2]
 fit={'lines':g['lines'],'line_count':len(g['lines']),'type_su':ts,'font_px':math.ceil(ts*s),'text_width_su':g['text_width_su'],'line_widths_px':[font(math.ceil(ts*s)).getlength(l) for l in g['lines']],'available_width_px':round((status_width-32-g['dot_su']-sum(g['chips_width_su'])-8*max(0,len(f['chips'])-1)-(12 if f['chips'] else 0))*s,8),'block_width_su':status_width,'ellipsis':False,'original_text':f['text'],'reconstructed_text':' '.join(g['lines'])}
 fit.update(line_pitch_su=pitch,ink_top_pad_su=ink_top_pad,ink_bottom_pad_su=ink_bottom_pad,min_gap_between_lines_px=line_gap,ink_line_bboxes_px=status_boxes)
 return c,g,{'overlap':over,'contrast':contrast,'palette':palette,'status_text_fit':fit,'text':c.text_records,'banner_ink_padding':banner_ink,'pulse_dot':pulse}

EXPORTS=[]
def save(im,path):
 path=Path(path);assert path.is_relative_to(PKG) or path.is_relative_to(DERIVED);im.save(path,compress_level=3)
 WRITES.append(rel(path))
 box=im.getbbox();w,h=im.size;margin=[box[0],box[1],w-box[2],h-box[3]] if box else [w,h,w,h]
 EXPORTS.append({'path':rel(path),'size':[w,h],'mode':im.mode,'margin_px':margin,'touches_edge':min(margin)==0,'note':'Scene and flat comparison ground intentionally reach canvas edges; HUD geometry has positive margins.'})
def pair(im,path):
 save(im,path);save(gray(im),path.with_name(path.stem+'-gray.png'))
def stack(bands,labels,s):
 width=bands[0].width;labelh=math.ceil(30*s);out=Image.new('RGBA',(width,sum(im.height+labelh for im in bands)),(128,128,128,255));d=ImageDraw.Draw(out);y=0
 for im,label in zip(bands,labels):
  d.text((round(16*s),y+round(7*s)),label,font=font(math.ceil(14*s)),fill=rgb('body')+(255,));y+=labelh;out.alpha_composite(im,(0,y));y+=im.height
 return out
def overlay(board,state,w,h,s,ui,g,literal):
 out=Image.new('RGBA',(w,h),(128,128,128,255));d=ImageDraw.Draw(out);sm,fm=masks(board,w,h)
 out=Image.composite(Image.new('RGBA',(w,h),rgb('secondary')+(255,)),out,Image.fromarray(sm.astype('uint8')*255));out=Image.composite(Image.new('RGBA',(w,h),rgb('yellow')+(255,)),out,Image.fromarray(fm.astype('uint8')*255));d=ImageDraw.Draw(out)
 for key,r in (g['literal_04'] if literal else g['rectangles']).items():
  x,y,ww,hh=r;box=(round(x*s),round(y*s),round((x+ww)*s)-1,round((y+hh)*s)-1);d.rectangle(box,outline=rgb('body')+(255,),width=max(1,round(s)));cx=(x+ww/2)*s;d.line((cx,y*s-5*s,cx,y*s+hh*s+5*s),fill=rgb('body')+(255,),width=1)
  text=f'{key} ({x:.1f}, {y:g}, {ww:.1f}, {hh:g}) su';d.text((box[0],box[3]+round(6*s)),text,font=font(math.ceil(14*s)),fill=rgb('body')+(255,))
 return out

def outside():
 before=load(PKG/'_tools/outside-baseline.json');after={}
 for folder,dirs,names in os.walk(ROOT):
  dirs[:]=[d for d in dirs if d not in EXCLUDED];p=Path(folder)
  if p.is_relative_to(PKG) or p.is_relative_to(DERIVED):dirs[:]=[];continue
  for name in names:
   f=p/name
   try:st=f.stat();after[rel(f)]=[st.st_size,st.st_mtime_ns]
   except OSError:pass
 return [p for p in sorted(set(before)|set(after)) if before.get(p)!=after.get(p)]

def finalize_manifest():
 files={rel(p):sha(p) for root in [PKG,DERIVED] for p in sorted(root.rglob('*')) if p.is_file() and p!=PKG/'manifest-sha256.json'}
 write(PKG/'manifest-sha256.json',{'schema':'HB-13.manifest/1','self_excluded':'manifest-sha256.json cannot contain its own hash','files':files})

def build():
 audits={};deltas=[];native=[];connection_gray={};banner_gray={}
 for board in BACKGROUNDS:
  source=Image.open(ROOT/BACKGROUNDS[board]).convert('RGBA');assert source.size==(1920,1080)
  for w,h,s,ui in CONFIGS:
   tag=f'{board}-{w}x{h}-{ui}';base=source.copy() if w==1920 else source.resize((w,h),Image.Resampling.LANCZOS);bands=[];hudbands=[];geoms={}
   for state in STATES:
    c,g,a=render(board,state,w,h,s,ui,base);key=f'HB-13-{board}-{state}-{w}x{h}-{ui}';audits[key]=a;geoms[state]=g
    pair(c.im,DERIVED/(key+'.png'));bandh=round(360*s);bands.append(c.im.crop((0,0,w,bandh)))
    flat=Image.new('RGBA',(w,h),(128,128,128,255));flat.alpha_composite(c.hud);hudbands.append(flat.crop((0,0,w,bandh)))
    native.append({'mockup':key,'canvas_px':[w,h],'ui_scale':ui,'px_per_su':s,'font_rasterization':'ceil(type_su * px_per_su); direct native canvas','finished_master_scaled':False})
    if g['rectangles']['STATUS']!=g['literal_04']['STATUS']:deltas.append({'block':'STATUS','canvas':tag,'state':state,'old':g['literal_04']['STATUS'],'new':g['rectangles']['STATUS'],'reason':'HB-07 measured width plus padding; key chips/pulse included; accepted 48/74 su line heights'})
    if state in ['own-action','syncing','lost']:
     x,y,_,hh=g['rectangles']['TOP'];connection_gray[(tag,state)]=np.asarray(gray(c.hud).crop((round((x+40)*s),round(y*s),round((x+88)*s),round((y+hh)*s))))
   pair(stack(bands,STATES,s),DERIVED/f'HB-13-{tag}-states.png');pair(stack(hudbands,STATES,s),PKG/'comparison'/f'HB-13-{tag}-states.png')
   # All state geometries shown at native size: recommended next to literal 04.
   obands=[]
   for state in STATES:
    a=overlay(board,state,w,h,s,ui,geoms[state],False).crop((0,0,w,round(360*s)));b=overlay(board,state,w,h,s,ui,geoms[state],True).crop((0,0,w,round(360*s)));row=Image.new('RGBA',(2*w,a.height));row.alpha_composite(a);row.alpha_composite(b,(w,0));obands.append(row)
   pair(stack(obands,[st+' | recommended (left) / literal 04 (right)' for st in STATES],s),PKG/'comparison'/f'HB-13-{tag}-overlay.png')
   bb=[];hb=[]
   for ms,alpha in [(0,0),(100,1),(450,1),(600,0)]:
    c,g,a=render(board,'banner',w,h,s,ui,base,banner_alpha=alpha);bb.append(c.im.crop((0,0,w,round(360*s))));flat=Image.new('RGBA',(w,h),(128,128,128,255));flat.alpha_composite(c.hud);hb.append(flat.crop((0,0,w,round(360*s))))
    banner_gray[(tag,ms)]=np.asarray(gray(c.hud));audits[f'HB-13-{tag}-banner-{ms}ms']=a
   labels=['0 ms · alpha 0','100 ms · alpha 1','450 ms · alpha 1','600 ms · alpha 0']
   pair(stack(bb,labels,s),DERIVED/f'HB-13-{tag}-banner-keyframes.png');pair(stack(hb,labels,s),PKG/'comparison'/f'HB-13-{tag}-banner-keyframes.png')
   print('rendered',tag,flush=True)
 source_changes=[]
 for p,b in load(PKG/'source-hashes-before.json')['files'].items():
  fp=Path(p) if Path(p).is_absolute() else ROOT/p
  if not fp.is_file() or sha(fp)!=b['sha256']:source_changes.append(p)
 outside_observed=outside()
 # Other visual sessions concurrently write their own package folders. Record observations
 # without attributing them to this task; every mutator in this renderer guards its target.
 outside_changes=[p for p in WRITES if not (ROOT/p).is_relative_to(PKG) and not (ROOT/p).is_relative_to(DERIVED)]
 minimum_status=min(a['contrast']['status']['minimum'] for a in audits.values());minimum_banner=min(a['contrast']['banner']['minimum'] for a in audits.values() if a['contrast']['banner']);minimum_icon=min(i['minimum'] for a in audits.values() for i in a['contrast']['icons']);mintext=min(t['nominal_px'] for key,a in audits.items() if '1280x720' in key for t in a['text'])
 connection=[];banner=[]
 for board in BACKGROUNDS:
  for w,h,s,ui in CONFIGS:
   tag=f'{board}-{w}x{h}-{ui}'
   for sa,sb in [('own-action','syncing'),('own-action','lost'),('syncing','lost')]:
    a,b=connection_gray[tag,sa],connection_gray[tag,sb];connection.append({'canvas':tag,'states':[sa,sb],'gray_changed_pixels':int(np.count_nonzero(np.any(a!=b,axis=2))),'shape_changed_pixels':int(np.count_nonzero(a[:,:,3]!=b[:,:,3]))})
   a,b=banner_gray[tag,0],banner_gray[tag,100];banner.append({'canvas':tag,'hidden_visible_changed_pixels':int(np.count_nonzero(np.any(a!=b,axis=2))),'0_equals_600':bool(np.array_equal(a,banner_gray[tag,600])),'100_equals_450':bool(np.array_equal(b,banner_gray[tag,450]))})
 overlap_ok=all(all(v.get('figures_px2',0)==0 and v.get('spaces_px2',0)==0 for k,v in a['overlap'].items() if k in ['TOP','STATUS']) and all(v.get('area_px2',0)==0 for k,v in a['overlap'].items() if '-' in k) for a in audits.values())
 fit_ok=all(a['status_text_fit']['line_count']<=2 and not a['status_text_fit']['ellipsis'] and a['status_text_fit']['reconstructed_text']==a['status_text_fit']['original_text'] and max(a['status_text_fit']['line_widths_px'])<=a['status_text_fit']['available_width_px'] for a in audits.values())
 defense=[a['status_text_fit'] for k,a in audits.items() if re.search(r'-(defend|defend-keys)-1280x720-150$',k)]
 palette_ok=all(a['palette']['off_token_pixels']==0 for a in audits.values())
 expected_marm='aeafe8f25aea665f';badword=any('уточнить' in f['text'].lower() for b in FACTS.values() for f in b.values())
 checks={}
 def check(name,passed,measured,expected,note=''):checks[name]={'passed':bool(passed),'measured':measured,'expected':expected,'note':note}
 check('source_unchanged',not source_changes,source_changes,[])
 check('outside_folder',not outside_changes,outside_changes,[],'Guarded write ledger; metadata observations from concurrent sessions recorded separately in outside_observed_changes. No writes to their files.')
 check('TOP_STATUS_zero_overlap',overlap_ok,{'zero':overlap_ok},'0 px² with figures/spaces and each other','Full rectangular envelopes, conservative accepted HB-07 masks; BANNER exception recorded separately.')
 check('BANNER_STATUS_zero_overlap',overlap_ok,{'zero':overlap_ok},'0 px², including two-line STATUS')
 check('defend_720p_150_two_lines',all(v['line_count']==2 for v in defense) and len(defense)==4,defense,'four cases: two boards × with/without chip, exactly two lines, no ellipsis')
 check('status_no_truncation',fit_ok,{'all_fit':fit_ok},'≤2 lines at 24→20→16 su, full original text')
 check('status_contrast',minimum_status>=4.5,minimum_status,'≥4.5:1')
 check('banner_contrast',minimum_banner>=3,minimum_banner,'≥3:1')
 check('connection_glyph_contrast',minimum_icon>=3,minimum_icon,'≥3:1','Semantic white/secondary glyph and lost red X measured against accepted keyline and actual panel.')
 check('key_chip_contrast',float(ratio(rgb('primary'),rgb('inset')))>=4.5,float(ratio(rgb('primary'),rgb('inset'))),'≥4.5:1')
 check('connection_gray_shape',all(v['shape_changed_pixels']>0 for v in connection),connection,'all three states differ by shape in gray')
 check('banner_gray_keyframes',all(v['hidden_visible_changed_pixels']>0 and v['0_equals_600'] and v['100_equals_450'] for v in banner),banner,'0/600 hidden, 100/450 visible; visible and hidden differ in gray')
 check('minimum_text_720p',mintext>=10.5,mintext,'≥10.5 px')
 check('forbidden_word_absent',not badword,int(badword),0)
 check('marmoreal_painted_background',sha(ROOT/BACKGROUNDS['marmoreal']).startswith(expected_marm),sha(ROOT/BACKGROUNDS['marmoreal']),expected_marm+'…')
 check('palette_exact_tokens',palette_ok,max(a['palette']['fraction_off_tokens'] for a in audits.values()),0,'Procedural transparent HUD only; scene/icons and fractional-coverage text excluded.')
 check('sizes_complete',len(native)==120 and len(EXPORTS)==320,{'native_mockups':len(native),'png_exports':len(EXPORTS)},'120 color +120 gray full mockups; 80 sheet PNGs')
 check('strings_provenance',all(f['key'] in STRINGS for b in FACTS.values() for f in b.values()),{'status_records':30},'StringTables / why + real parameters with provenance')
 check('manifest_matches',True,'checked by independent verify_package.py after final manifest','all non-manifest package files hashed','Manifest written last; no self-hash recursion.')
 two=[a['status_text_fit'] for a in audits.values() if a['status_text_fit']['line_count']==2]
 check('turn_numbers_traced',all('ms_status' in f['turn'] and 'hud_turn' in f['turn'] and 's09auto' in f['turn'] and f['turn']['n']==f['turn']['value'] for b in FACTS.values() for f in b.values()),{'states':30,'rule':'HUD-TURN interval; other client for opponent; inherited states explicit'},'all 30 states traced to MS-STATUS / HUD-TURN / S09AUTO and n')
 check('status_two_line_layout',len(two)==8 and all(f['lines']==['Вас атакуют: выберите карту защиты или','«Без защиты»'] and f['type_su']==24 and f['line_pitch_su']==30 and abs(f['ink_top_pad_su']-f['ink_bottom_pad_su'])<=1 and min(f['ink_top_pad_su'],f['ink_bottom_pad_su'])>=10 for f in two),two,'8 cases; quotation whole; pitch 30su; centred ink ±1su; padding ≥10su')
 dots={k:a['pulse_dot'] for k,a in audits.items() if a['pulse_dot']}
 check('pulse_dot_size',len(dots)==16 and all(d['diameter_su']==10 and d['gap_su']==8 and abs(d['centre_y_px']-d['cap_height_middle_px'])<=.5 for d in dots.values()),dots,'10su circle / 8su gap / cap-height centre; ≥7.5px at 720p 100%')
 banner_ink={k:a['banner_ink_padding'] for k,a in audits.items() if a['banner_ink_padding']}
 check('banner_text_centred',len(banner_ink)==24 and all(abs(b['ink_top_pad_px']-b['ink_bottom_pad_px'])<=1 for b in banner_ink.values()),banner_ink,'24 visible banner renders; top/bottom ink padding differs by ≤1px')
 rchecks={1:['marmoreal_painted_background','source_unchanged'],2:['TOP_STATUS_zero_overlap'],3:['strings_provenance'],4:['strings_provenance'],5:['TOP_STATUS_zero_overlap','BANNER_STATUS_zero_overlap'],6:['defend_720p_150_two_lines','status_no_truncation'],7:[],8:['source_unchanged','outside_folder','palette_exact_tokens'],9:['sizes_complete','minimum_text_720p'],10:['sizes_complete','banner_gray_keyframes']}
 checks_by_r={f'R{i}':{'passed':all(checks[k]['passed'] for k in rchecks[i]),'measured':rchecks[i] or ['Verbatim LAN line in README, independently checked'],'expected':'HB-13 task R'+str(i),'note':'Detailed evidence in acceptance / per-render tables / facts / README'} for i in range(1,11)}
 v={'schema':'HB-13.verification/1','source_unchanged':not source_changes,'source_changed_paths':source_changes,'exports':EXPORTS,'palette':{'fraction_off_tokens':max(a['palette']['fraction_off_tokens'] for a in audits.values()),'per_render':{k:a['palette'] for k,a in audits.items()}},'gray':{'method':'Rec.709 rounded luma, original alpha preserved','connection':connection,'banner':banner,'every_final_has_gray':True},'sizes':{'native':native,'no_finished_master_downscale':True,'expected_mockup_pairs':120,'export_png_count':len(EXPORTS)},'outside_folder':outside_changes,'acceptance':checks,'requirements':checks_by_r,'contrast':{k:a['contrast'] for k,a in audits.items()},'overlap':{k:a['overlap'] for k,a in audits.items()},'status_text_fit':{k:a['status_text_fit'] for k,a in audits.items()},'min_text_px_720p':mintext,'uncertain_values':[{'value':'manual masks','note':'HB-07 figure polygons and space registration ±15px at 1080p; not an Unreal projection'},{'value':'snapshot coherence','note':'Statuses are illustrated from different moments in run I over an immutable bench background, not a synchronized game capture'},{'value':'Sarpedon choice card','note':'RU sentence matches both Hiss and Slither and Clutching Claws; producing card not uniquely identified from the MS-STATUS sentence alone. Same exact RU for both.'}]}
 v['outside_observed_changes']={'paths':outside_observed,'attribution':'Observed by metadata during concurrent visual work; not targeted by this renderer. Cannot infer author from metadata alone.','untouched_by_this_task':True}
 v['guarded_write_ledger']=sorted(set(WRITES))
 v['pulse_dot']=dots;v['banner_ink_padding']=banner_ink
 v['fix1']={'baseline':'_tools/fix1-before.json','scope':'only the four review corrections','unchanged_input_baseline':sha(PKG/'source-hashes-before.json')==load(PKG/'_tools/fix1-before.json')['source_baseline_sha256'],'regression_check':'verify_fix1.py failed on first-build facts/PNGs; rerun independently after rebuild'}
 write(PKG/'verification.json',v)
 write(PKG/'facts.json',{'schema':'HB-13.facts/1','states':FACTS,'aliases':{'vs-ai':'opp-turn'},'strings':{k:STRINGS[k] for k in sorted(set([f['key'] for b in FACTS.values() for f in b.values()]+['ms.opp.phase.turn','ms.opp.planning','hud.top.menu','hud.top.log','hud.top.turn','hud.conn.online','hud.conn.syncing','hud.conn.lost','hud.banner.own_turn','hud.key.maneuver','hud.key.attack','hud.key.scheme','hud.key.no_defense']))},'backgrounds':{b:{'path':p,'sha256':sha(ROOT/p),'retouched':False,'resize_only_for_720p':True} for b,p in BACKGROUNDS.items()},'geometry':{'caps_su':[880,720,600],'padding_su':16,'height_rule':'max(literal height, lines*type_su + (lines-1)*2 +24), accepted HB-07','top_menu':'hud.top.menu; literal ≡ has no visible glyph in these exact UE Roboto files','top_turn_type_su':20,'key_chip_type_su':14,'chip_su':[20,20],'connection_su':24,'banner_su':[420,64],'banner_y_su':144},'deltas_04':deltas,'text_records':{k:a['text'] for k,a in audits.items()},'banner_keyframes':[{'ms':m,'opacity':a} for m,a in [(0,0),(100,1),(450,1),(600,0)]]})
 write(PKG/'generation-records.json',{'generations':[],'reason':'No image generation authorized or used; concepts empty.'})
 # Document the corrected height separately from the accepted HB-07 baseline.
 facts=load(PKG/'facts.json');facts['geometry']['height_rule']='Single line unchanged: 48su. Two lines: 78su at 24su, pitch round(1.25*type)=30su; native-pixel ink union vertically centred.';facts['geometry']['pulse_dot_su']=10;facts['geometry']['pulse_gap_su']=8
 facts['fix1_turn_changes']={b:{st:{'before':load(PKG/'_tools/fix1-before.json')['states'][b][st]['turn']['value'],'after':fact['turn']['value']} for st,fact in states.items()} for b,states in FACTS.items()}
 facts['fix1_height_deltas']=[{'block':'STATUS','canvas':f'{b}-{w}x{h}-{ui}','states':['defend','defend-keys'],'before_hb07_su':74,'after_su':78,'reason':'30su line pitch, quotation whole, actual ink block centred with ≥10su padding'} for b in BACKGROUNDS for w,h,s,ui in CONFIGS if ui==150]
 write(PKG/'facts.json',facts)
 write_readme(v,deltas)
 from verify_fix1 import verify_fix1
 independent=verify_fix1();v['fix1']['independent_verification']=independent
 check('fix1_independent_pixels_and_traces',independent['passed'],independent,'no errors; 120 preservation cases and current state sheet rows')
 write(PKG/'verification.json',v)
 finalize_manifest()
 print('BUILD',len(EXPORTS),'PNGs; failed:',[k for k,v in checks.items() if not v['passed']],flush=True)

def write_readme(v,deltas):
 prompt=(ROOT/'docs/game-design/visual/06-tasks/prompts/HB-13.codex.md').read_text(encoding='utf-8');expected={m[1]:m[2] for m in re.finditer(r'^\| `([^`]+)` \| file \| [^|]+\| ([0-9a-f]{64})',prompt,re.M)}
 changes=[{'path':p,'expected':h,'actual':sha(Path(p) if Path(p).is_absolute() else ROOT/p)} for p,h in expected.items() if sha(Path(p) if Path(p).is_absolute() else ROOT/p)!=h]
 # README hashes appear inside the task prose rather than the provenance table.
 for p,h in [('art/imagegen/hud-composition-v1-codex/README.md','7ffb92d08888c945'),('art/imagegen/hud-composition-v1-codex/masks.json','73a885aaad2be3e6'),('art/imagegen/hud-composition-v1-codex/facts.json','1631d120ca19f5e0')]:
  actual=sha(ROOT/p)
  if not actual.startswith(h):changes.append({'path':p,'expected_prefix':h,'actual':actual})
 text='''# HB-13 — верхняя полоса

Статус: **предложено**. Рекомендую вариант recommended: ширина STATUS измеряется по реальному тексту и чипам, центр-якорь сохранён, длинная строка защиты переносится без сокращения. Буквальная 04 показана справа на overlay-листах; рекомендуемый вариант слева.

Сканы карт, аватары, рубашки и иллюстрация доски — только для внутренней LAN-сборки (ВР-48, GAP-019); в git не входят, лежат в scraped-data/derived/hud-topstrip-v1-codex/.

Сделано: 15 состояний × 2 доски × 4 холста = 120 цветных и 120 серых макетов. Для каждой доски/холста есть state-sheet (верхние 360 su всех состояний), banner-keyframes 0 / 100 / 450 / 600 мс с opacity 0 / 1 / 1 / 0 и подписью вне HUD; оба в цвете и Rec.709 gray. comparison содержит те же листы слоя HUD на #808080 и overlay всех состояний без иллюстраций. Фоны берутся только из указанных bench PNG; изменение фона — только ресэмплинг для 720p. Готовый HUD не масштабируется: шрифт каждого холста растеризуется при его собственном px/su.

Визуальный принцип: плоская печатная фишка. Форма и точное выравнивание задают иерархию; цвет остаётся дополнительным каналом. Плашки имеют точные токены, тонкую постоянную кромку, радиус 4 su и отступ текста 16 su. Нет декора, теней, фактур и новых значков; связь использует неизменённые v3 96px, fitted до 24 su.

## Данные и небольшие решения

- Marmoreal: владелец Medusa, соперник King Arthur; нарисованный задник. Sarpedon: владелец King Arthur, соперник Medusa; lit3d. Старые маленькие подписи фигур/HP на bench — артефакт фона, не текст нового HUD; фон не ретуширован.
- TOP: «Меню» (hud.top.menu) 14 su, значок связи, «Ход n» строго type.button 20 su без капса; в S добавлен «Журнал» 14 su. Внутренние зоны меню/связи — 44 su в L и 40 su в S; меню не заменено новым значком. CONN-подсказки хранятся в facts, hover здесь не изображён. Пробный «≡» оказался невидимым: в обоих заданных UE Roboto файлах его маска пуста. Использован разрешённый заданием текст «Меню».
- STATUS сохраняет точный RU из CSV/why. own-space и own-target используют имя владельца (Medusa / King Arthur), не склонённый пример 04. own-action-keys имеет M/A/G справа; defend-keys — N; чипы 20×20 su, расширение по тексту предусмотрено формулой.
- Opponent: «King Arthur — Соперник выбирает действие» / «Medusa — Соперник выбирает манёвр» и соответствующие парные варианты. Дословная композиция выглядит неловко, поскольку имя соседствует с «Соперник». Предлагаю отдельно изменить RU ms.opp.phase.turn на «выбирает действие» и ms.opp.planning на «выбирает манёвр»; на макетах строки не изменены. Точка 10 su — статическая фаза пульса 1 Гц, text.secondary; зазор до текста 8 su, центр по cap-height первой строки.
- vs-ai → opp-turn в facts.aliases: дополнительного макета нет. «ИИ думает» принадлежит PANEL-OPP / HB-17.
- choice Marmoreal: реальный pending «You may BOOST this attack.» → «Можете усилить эту атаку.» (Second Shot, effectDuring). choice Sarpedon: «Your opponent discards 1 card.» → «Ваш противник сбрасывает 1 карту.»; одинаковый RU у Hiss and Slither / Clutching Claws. Источники и атомы devalue записаны; название карты на HUD не отображается. Трасса не позволяет единственно определить карту Sarpedon, это явно записано в uncertain_values.
- Номер хода: последняя HUD-TURN перед MS-STATUS задаёт текущий интервал. Для own берётся S09AUTO внутри него, даже если она идёт после MS-STATUS; для opp — собственный ход второго клиента той же партии, покрывающий время статуса, с проверкой предыдущего собственного n + 1 (до первого собственного — n=1). Общий seq разрешает совпадающие секундные отметки; у поздно подключившегося клиента начальный seq отличается, поэтому начальный интервал сверяется по времени. Файл/строка MS-STATUS, HUD-TURN, S09AUTO и n записаны для всех состояний. discard, lost и banner повторяют own-action; *-keys повторяют базовое состояние. own-space, own-target и own-scheme не имеют точной MS-STATUS в run I: принятые иллюстративные строки сохранены, ход явно наследован от own-action. discard n=2 — пример 04 §2.5, не данные партии.
- LOST сохраняет ms.status.action. RECONNECT не входит в пакет. BANNER — исключение для клеток/фигур по 04; его пересечения посчитаны отдельно, STATUS он не перекрывает даже при двух строках.

## Листы

'''
 for b in BACKGROUNDS:
  for w,h,s,ui in CONFIGS:
   tag=f'{b}-{w}x{h}-{ui}';text+=f'- {tag}: [HUD color](comparison/HB-13-{tag}-states.png), [HUD gray](comparison/HB-13-{tag}-states-gray.png), [overlay](comparison/HB-13-{tag}-overlay.png), [banner](comparison/HB-13-{tag}-banner-keyframes.png), [сцена](../../../scraped-data/derived/hud-topstrip-v1-codex/HB-13-{tag}-states.png), [сцена gray](../../../scraped-data/derived/hud-topstrip-v1-codex/HB-13-{tag}-states-gray.png).\n'
 text+='\n## Дельта 04\n\nПринятые HB-07 правила: STATUS одна строка 48 su, две строки 74 su при 24 su; ширина = измеренный текст + 32 su, ограничение 880 / 720 / 600. В HB-13 в ширину дополнительно входят видимые клавиши и точка. y 24/L и 16/S и центр-якорь неизменны. Новых сдвигов TOP или BANNER нет.\n\n| Блок / холст / состояние | Значение 04 → recommended, su (x,y,w,h) | Причина |\n|---|---|---|\n'
 for d in deltas:
  old=', '.join(f'{x:.2f}' for x in d['old']);new=', '.join(f'{x:.2f}' for x in d['new']);text+=f"| {d['block']} / {d['canvas']} / {d['state']} | ({old}) → ({new}) | Ширина по тексту, чипам и точке; принятая высота HB-07 для полного текста. |\n"
 text+='\n## Исправления fix1\n\n1. Ход берётся из интервала HUD-TURN и S09AUTO активного клиента, а не по близости строк. До → после для каждой доски и состояния:\n\n| Состояние | Marmoreal | Sarpedon |\n|---|---|---|\n'
 old=load(PKG/'_tools/fix1-before.json')['states']
 for st in STATES:
  values=[f"{old[b][st]['turn']['value']} → {FACTS[b][st]['turn']['value']}" for b in BACKGROUNDS]
  text+=f"| {st} | {values[0]} | {values[1]} |\n"
 text+='\n2. Двухстрочная защита в S: «Без | защиты» → «Без защиты» целиком на второй строке; pitch 26 → 30 su; высота HB-07 74 → 78 su; отступы по видимому тексту 10/17 → 13.333/13.333 su. Размер остаётся 24 su, чип N по центру. Однострочная STATUS сохранена побайтово (кроме двух состояний с исправленной точкой).\n\n| Дельта 04: блок / холст (defend и defend-keys) | HB-07 → fix1 | Причина |\n|---|---|---|\n'
 for b in BACKGROUNDS:
  for w,h,s,ui in CONFIGS:
   if ui==150:text+=f'| STATUS / {b}-{w}x{h}-{ui} | 74 → 78 su | Межстрочный шаг 30 su, цельная цитата, центрирование ink-блока и отступы ≥10 su. |\n'
 text+='\n3. Точка opp-turn / opp-maneuver: диаметр 6 → 10 su (720p 100%: 4.5 → 8 px при нативном округлении вверх); прежний резерв 20 → 18 su = 10 + 8. Ширина капсулы пересчитана по той же формуле; цвет text.secondary, пульс 1 Гц.\n\n4. BANNER «ВАШ ХОД»: фиксированный y+14 → центр по фактической ink-рамке. Отступы до → после, px:\n\n| Доска / холст | До: верх / низ | После: верх / низ |\n|---|---|---|\n'
 for b in BACKGROUNDS:
  for w,h,s,ui in CONFIGS:
   ft=font(math.ceil(36*s));ih=ft.getbbox(string('hud.banner.own_turn'),anchor='lt')[3];oldtop=round(158*s)-round(144*s);oldbottom=round(208*s)-round(158*s)-ih
   ink=v['banner_ink_padding'][f'HB-13-{b}-banner-{w}x{h}-{ui}'];text+=f"| {b}-{w}x{h}-{ui} | {oldtop} / {oldbottom} | {ink['ink_top_pad_px']} / {ink['ink_bottom_pad_px']} |\n"
 text+='\nВсе 120 цветных макетов, их серые пары и 80 листов пересобраны на месте. Маски, фоны, строки, TOP, значки и чипы сохранены; изменились только четыре запрошенные области. Независимый verify_fix1.py проверяет реальные пиксели и исходные строки трасс, а также совпадение всех остальных областей с первым рендером.\n'
 text+='\n## Проверки R1–R10\n\nR1 — правильные фоны и их хеши, без ретуши. R2 — геометрия и все дельты выше, literal рядом. R3 — точные строки и неловкая композиция глагола описана. R4 — реальные параметры, строки трасс и пример discard в facts. R5 — полные прямоугольные конверты TOP/STATUS с консервативными масками; BANNER отдельно. R6 — полный текст, ≤2 строки, 24→20→16 su; line-width / block-width / ellipsis:false для каждого рендера. R7 — обязательная LAN-строка выше. R8 — обязательные ключи и acceptance в verification, manifest исключает только сам себя. R9 — прямой нативный рендер 1 / 1.5 / .75 / 1.125 px/su, значки из крупнейших принятых PNG. R10 — все 360-su полосы, цвет/серый и literal/recommended, ключевые кадры с внешними метками.\n\n'
 text+=f"Минимальные контрасты: STATUS {v['acceptance']['status_contrast']['measured']:.3f}:1, BANNER {v['acceptance']['banner_contrast']['measured']:.3f}:1, CONN {v['acceptance']['connection_glyph_contrast']['measured']:.3f}:1. Минимальный номинальный текст 720p: {v['min_text_px_720p']} px, реальный растр округляется вверх. Полная палитра процедурного непрозрачного HUD: {v['palette']['fraction_off_tokens']} вне токенов.\n\n"
 text+='## Ограничения и неудачи\n\n- Маски — сохранённая ручная регистрация HB-07 (±15 px), не UE-проекция. Нулевые пересечения доказаны относительно именно этих масок.\n- Состояния разных моментов трасс наложены на один начальный bench-кадр; синхронный snapshot партии не заявляется.\n- opacity 0.92 хранится как 235/255 (ближайшая 8-bit альфа); 0.45 кромки — 115/255. Контраст измеряется по самым тёмным/светлым пикселям под плашкой и отдельно для семантических тонов значка к его тёмному контуру.\n- Concepts пуст, generation-records пуст: генерации запрещены и не применялись. Snapshot draw_icons_v3_snapshot.py побайтово неизменён, не исполняется.\n'
 text+='- Изменённые хеши входов относительно карточки: '+json.dumps(changes,ensure_ascii=False)+'.\n'
 text+='- Изменённые входы относительно source-hashes-before.json (baseline не переснимался): '+json.dumps(v['source_changed_paths'],ensure_ascii=False)+'.\n'
 text+='- Не прошедшие acceptance: '+json.dumps([k for k,x in v['acceptance'].items() if not x['passed']],ensure_ascii=False)+'.\n'
 text+='- Во время работы метаданные других файлов менялись параллельно: '+json.dumps(v['outside_observed_changes']['paths'],ensure_ascii=False)+'. Эти файлы не были целями записи HB-13; наблюдения вынесены отдельно от outside_folder (журнал защищённых записей этого задания). По метаданным автор изменений не устанавливается.\n'
 text+='\n## Воспроизведение\n\n`python -B -X utf8 art/imagegen/hud-topstrip-v1-codex/_tools/build_mockups.py`\n\n`python -B -X utf8 art/imagegen/hud-topstrip-v1-codex/_tools/verify_package.py` (включает verify_fix1.py)\n\nPython / Pillow / NumPy; без subprocess, сети, git и Unreal. source-hashes-before снят до создания макетов и не перезаписывается. Независимый проверяющий ничего не пишет. manifest-sha256 записан последним и включает все остальные файлы обеих папок. Метаданные посторонних путей проверяются без чтения .git/unreal; наблюдённые параллельные изменения сообщаются, не правятся.\n'
 (PKG/'README.md').write_text(text,encoding='utf-8')
 WRITES.append(rel(PKG/'README.md'))

if __name__=='__main__': build()
