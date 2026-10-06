"""Independent, read-only HB-13 output verification. Never writes files."""
from pathlib import Path
import hashlib,json,math,re
import numpy as np
from PIL import Image,ImageDraw,ImageFilter

ROOT=Path(__file__).resolve().parents[4]
P=ROOT/'art/imagegen/hud-topstrip-v1-codex';D=ROOT/'scraped-data/derived/hud-topstrip-v1-codex'
def load(p):return json.loads(p.read_text(encoding='utf-8'))
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
v=load(P/'verification.json');f=load(P/'facts.json');m=load(P/'manifest-sha256.json');sources=load(P/'source-hashes-before.json');errors=[]
def check(ok,label):
 if not ok:errors.append(label)
actual={p.relative_to(ROOT).as_posix() for root in [P,D] for p in root.rglob('*') if p.is_file() and p!=P/'manifest-sha256.json'}
check(actual==set(m['files']),'manifest complete coverage')
for path,h in m['files'].items():check(sha(ROOT/path)==h,'manifest '+path)
for path,r in sources['files'].items():
 p=Path(path) if Path(path).is_absolute() else ROOT/path
 check(p.is_file() and sha(p)==r['sha256'],'input unchanged '+path)
check(sha(P/'_tools/draw_icons_v3_snapshot.py')==sha(ROOT/'art/imagegen/hud-icons-v3/_tools/draw_icons.py'),'icon snapshot byte equality')
check(v['source_unchanged'] and v['outside_folder']==[],'source/outside declaration')
for key,r in v['acceptance'].items():check(r['passed'],'acceptance '+key)
for key,fit in v['status_text_fit'].items():
 check(' '.join(fit['lines'])==fit['original_text'] and not fit['ellipsis'],'complete status '+key)
 check(fit['line_count']<=2 and max(fit['line_widths_px'])<=fit['available_width_px'],'fit '+key)
check(f['aliases']=={'vs-ai':'opp-turn'},'VS_AI alias')
check('Сканы карт, аватары, рубашки и иллюстрация доски — только для внутренней LAN-сборки (ВР-48, GAP-019); в git не входят, лежат в scraped-data/derived/hud-topstrip-v1-codex/.' in (P/'README.md').read_text(encoding='utf-8'),'LAN wording')
maskdata=load(ROOT/'art/imagegen/hud-composition-v1-codex/masks.json');cache={};basecache={}
def protected(board,w,h):
 key=(board,w,h)
 if key in cache:return cache[key]
 info=maskdata['topology_transforms'][f'{board}-{w}x{h}'];s=Image.new('L',(w,h));d=ImageDraw.Draw(s)
 for space in info['spaces']:d.polygon([tuple(p) for p in space['polygon_px']],fill=255)
 s=s.filter(ImageFilter.MaxFilter(2*info['cell_conservative_dilation_px']+1));g=Image.new('L',(w,h));d=ImageDraw.Draw(g)
 for poly in maskdata['figure_polygons_1080p'][board]:d.polygon([(round(x*w/1920),round(y*w/1920)) for x,y in poly],fill=255)
 g=g.filter(ImageFilter.MaxFilter(2*info['figure_conservative_dilation_px']+1));cache[key]=(np.asarray(s)>0,np.asarray(g)>0);return cache[key]
pngs={r['path']:r for r in v['exports']};check(len(pngs)==320,'320 unique PNG exports')
for path,r in pngs.items():
 p=ROOT/path
 with Image.open(p) as im:
  check(list(im.size)==r['size'] and im.mode=='RGBA','size/mode '+path)
  if p.stem.endswith('-gray'):continue
  gp=p.with_name(p.stem+'-gray.png');check(gp.is_file(),'gray counterpart '+path)
  a=np.asarray(im);g=np.asarray(Image.open(gp));expected=np.rint(a[:,:,:3]@np.array([.2126,.7152,.0722])).astype('uint8')
  check(np.array_equal(g[:,:,:3],np.repeat(expected[:,:,None],3,axis=2)) and np.array_equal(a[:,:,3],g[:,:,3]),'exact Rec.709 '+path)
  match=re.fullmatch(r'HB-13-(marmoreal|sarpedon)-('+ '|'.join(re.escape(s) for s in f['states']['marmoreal']) +r')-(1920x1080|1280x720)-(100|150)',p.stem)
  if match:
   board,state,res,ui=match.groups();w,h=map(int,res.split('x'));scale=(1 if w==1920 else .75)*int(ui)/100;key=p.stem
   if (board,w,h) not in basecache:
    base=Image.open(ROOT/f['backgrounds'][board]['path']).convert('RGBA');basecache[board,w,h]=np.asarray(base if base.size==(w,h) else base.resize((w,h),Image.Resampling.LANCZOS))
   envelope=np.zeros((h,w),bool);rects={};sm,fm=protected(board,w,h)
   for name,record in v['overlap'][key].items():
    if 'rect_su' not in record:continue
    x,y,rw,rh=record['rect_su'];rect=np.zeros((h,w),bool);rect[round(y*scale):round((y+rh)*scale),round(x*scale):round((x+rw)*scale)]=True;rects[name]=rect;envelope|=rect
    measured_s=int(np.count_nonzero(rect&sm));measured_f=int(np.count_nonzero(rect&fm));check(measured_s==record['spaces_px2'] and measured_f==record['figures_px2'],'independent mask overlap '+key+' '+name)
    if name in ['TOP','STATUS']:check(measured_s==0 and measured_f==0,'protected HUD '+key+' '+name)
   check(not np.any(rects['TOP']&rects['STATUS']),'TOP/STATUS '+key)
   if 'BANNER' in rects:check(not np.any(rects['BANNER']&rects['STATUS']),'BANNER/STATUS '+key)
   check(np.array_equal(a[~envelope],basecache[board,w,h][~envelope]),'background untouched outside HUD '+key)
from verify_fix1 import verify_fix1
fix1=verify_fix1();errors.extend(fix1['errors'])
print('PASS' if not errors else 'FAIL',json.dumps({'verified_files':len(m['files']),'PNG_exports':len(pngs),'fix1':fix1,'errors':errors},ensure_ascii=False))
raise SystemExit(1 if errors else 0)
