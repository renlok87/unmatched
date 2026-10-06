"""Independent read-only checks of fix1 trace provenance and native-pixel layouts."""
from pathlib import Path
import hashlib,json,math,re
import numpy as np
from PIL import Image,ImageDraw,ImageFont

ROOT=Path(__file__).resolve().parents[4]
P=ROOT/'art/imagegen/hud-topstrip-v1-codex';D=ROOT/'scraped-data/derived/hud-topstrip-v1-codex'
def load(p):return json.loads(p.read_text(encoding='utf-8'))
def digest(a):return hashlib.sha256(a.tobytes()).hexdigest()

def verify_fix1():
 f=load(P/'facts.json');v=load(P/'verification.json');before=load(P/'_tools/fix1-before.json');errors=[]
 def check(ok,name):
  if not ok:errors.append(name)
 check(hashlib.sha256((P/'source-hashes-before.json').read_bytes()).hexdigest()==before['source_baseline_sha256'],'original source baseline preserved')
 for b,states in f['states'].items():
  for st,rec in states.items():
   t=rec['turn'];prefix=b+'/'+st
   if not all(k in t for k in ['ms_status','hud_turn','s09auto','n']):check(False,'turn provenance '+prefix);continue
   records={}
   for k in ['ms_status','hud_turn','s09auto']:
    r=t[k];lines=(ROOT/r['path']).read_text(encoding='utf-8').splitlines();check(lines[r['line']-1]==r['trace'],'exact '+k+' '+prefix);records[k]=(r,lines)
   mr,ml=records['ms_status'];hr,hl=records['hud_turn'];sr,sl=records['s09auto']
   last=max(i+1 for i,l in enumerate(ml[:mr['line']-1]) if re.search(r'HUD-TURN seq=\d+ turn=(own|opp)\b',l))
   check(hr['path']==mr['path'] and hr['line']==last,'last HUD-TURN '+prefix)
   n=int(re.search(r'turnCount=(\d+)',sr['trace'])[1]);check(n==t['value']==t['n'],'turnCount '+prefix)
   own='turn=own' in hr['trace']
   own_start=max(i+1 for i,l in enumerate(sl[:sr['line']-1]) if re.search(r'HUD-TURN seq=\d+ turn=(own|opp)\b',l))
   check('turn=own' in sl[own_start-1],'own S09AUTO interval '+prefix)
   if own:check(sr['path']==hr['path'] and own_start==hr['line'],'own client interval '+prefix)
   else:
    check(sr['path']!=hr['path'] and Path(sr['path']).parent==Path(hr['path']).parent,'same match other client '+prefix)
    next_turn=next((l for l in sl[sr['line']:] if re.search(r'HUD-TURN seq=\d+ turn=',l)),None)
    check(sl[own_start-1][:19]<=mr['trace'][:19] and (next_turn is None or mr['trace'][:19]<=next_turn[:19]),'opponent time interval '+prefix)
    previous=[int(re.search(r'turnCount=(\d+)',l)[1]) for l in hl[:hr['line']-1] if re.search(r'S09AUTO own turn .*turnCount=',l)]
    check(n==(previous[-1]+1 if previous else 1),'previous own plus one '+prefix)
   if t.get('inherited_from'):
    bt=states[t['inherited_from']]['turn'];check(t['n']==bt['n'] and t['ms_status']==bt['ms_status'],'inherited base '+prefix)
   else:check(rec['trace']==t['ms_status'],'state MS-STATUS '+prefix)
 check(f['states']['marmoreal']['defend']['turn'].get('n')==2 and f['states']['marmoreal']['opp-turn']['turn'].get('n')==2,'Marmoreal reviewed examples')
 check(f['states']['sarpedon']['defend']['turn'].get('n')==3 and f['states']['sarpedon']['opp-turn']['turn'].get('n')==1,'Sarpedon reviewed examples')
 bases={};sheets={};layout_count=0;banner_count=0;pulse_count=0;preserved_count=0;sheet_rows=0
 for entry in v['sizes']['native']:
  key=entry['mockup'];b=next(b for b in f['states'] if key.startswith('HB-13-'+b+'-'));st=before['renders'][key]['state'];s=entry['px_per_su'];w,h=entry['canvas_px'];a=np.asarray(Image.open(D/(key+'.png')))
  if (b,w,h) not in bases:
   im=Image.open(ROOT/f['backgrounds'][b]['path']).convert('RGBA');bases[b,w,h]=im if im.size==(w,h) else im.resize((w,h),Image.Resampling.LANCZOS)
  overlap=v['overlap'][key];rect=overlap['STATUS']['rect_su'];x,y,rw,rh=rect
  old=before['renders'][key];mask=np.ones((h,w),bool);tx,ty,tw,th=overlap['TOP']['rect_su'];mask[round(ty*s):round((ty+th)*s),round((tx+88)*s):round((tx+163)*s)]=False
  if not old['unchanged_status_required']:
   cap=600 if entry['ui_scale']==150 else (880 if w==1920 else 720);cx=w/s/2;mask[round(y*s):round((y+80)*s),round((cx-cap/2)*s):round((cx+cap/2)*s)]=False
  if st=='banner':
   bx,by,bw,bh=overlap['BANNER']['rect_su'];mask[round((by+1)*s):round((by+bh-1)*s),round((bx+1)*s):round((bx+bw-1)*s)]=False
  check(digest(a[mask])==old['preserved_pixels_sha256'],'unrequested pixels unchanged '+key);preserved_count+=1
  if old['unchanged_status_required']:
   check(rect==old['status_rect_su'] and digest(a[round(y*s):round((y+rh)*s),round(x*s):round((x+rw)*s)])==old['status_pixels_sha256'],'single-line STATUS unchanged '+key)
  # Reconstruct only the specified panel, then measure ink from actual image differences.
  def ink_bounds(block,region):
   px,py,pw,ph=block;layer=Image.new('RGBA',(w,h));ImageDraw.Draw(layer).rounded_rectangle((round(px*s),round(py*s),round((px+pw)*s)-1,round((py+ph)*s)-1),radius=max(1,round(4*s)),fill=(6,22,35,235),outline=(249,235,219,115),width=max(1,round(s)))
   ground=np.asarray(Image.alpha_composite(bases[b,w,h],layer));l,t,r,bt=region;diff=np.any(a[t:bt,l:r]!=ground[t:bt,l:r],axis=2);rows=np.where(np.any(diff,axis=1))[0]
   return (t+int(rows[0]),t+int(rows[-1])+1) if len(rows) else None
  fit=v['status_text_fit'][key]
  check(all(k in fit for k in ['line_pitch_su','ink_top_pad_su','ink_bottom_pad_su','min_gap_between_lines_px']),'status metrics '+key)
  if st in ['defend','defend-keys'] and entry['ui_scale']==150:
   layout_count+=1;check(fit['lines']==['Вас атакуют: выберите карту защиты или','«Без защиты»'] and fit['type_su']==24,'whole quotation '+key)
   check(fit.get('line_pitch_su')==30,'30su line pitch '+key)
   boxes=fit.get('ink_line_bboxes_px',[])
   if len(boxes)==2:
    actual=[ink_bounds(rect,(bb[0]-1,bb[1]-1,bb[2]+1,bb[3]+1)) for bb in boxes]
    check(all(bb is not None for bb in actual),'visible status ink '+key)
    top=(actual[0][0]-round(y*s))/s;bottom=(round((y+rh)*s)-actual[-1][1])/s;gap=actual[1][0]-actual[0][1]
    check(abs(top-bottom)<=1 and min(top,bottom)>=10,'centred status ink '+key)
    check(abs(top-fit['ink_top_pad_su'])<1e-8 and abs(bottom-fit['ink_bottom_pad_su'])<1e-8 and gap==fit['min_gap_between_lines_px'],'measured status metrics '+key)
    check(actual[1][0]-actual[0][0] in [math.floor(30*s),math.ceil(30*s)],'actual native line pitch '+key)
   else:check(False,'two actual ink boxes '+key)
  if st.startswith('opp-'):
   pulse_count+=1;dot=v.get('pulse_dot',{}).get(key)
   if dot:
    bb=dot['bbox_px'];pixels=a[bb[1]:bb[3],bb[0]:bb[2],:3];hit=np.all(pixels==[185,178,166],axis=2);ys,xs=np.where(hit)
    check(dot['diameter_su']==10 and bb[2]-bb[0]==bb[3]-bb[1]==math.ceil(10*s),'pulse diameter '+key)
    check(len(xs)>0 and xs.max()-xs.min()+1==bb[2]-bb[0] and ys.max()-ys.min()+1==bb[3]-bb[1],'actual circle extent '+key)
    check(abs(dot['centre_y_px']-dot['cap_height_middle_px'])<=.5 and dot['gap_su']==8,'pulse alignment and gap '+key)
    check(bb[2]-bb[0]>=7.5 if s==.75 else True,'720p visible dot '+key)
   else:check(False,'pulse metric '+key)
  if st=='banner':
   banner_count+=1;block=overlap['BANNER']['rect_su'];bx,by,bw,bh=block;actual=ink_bounds(block,(round((bx+2)*s),round((by+2)*s),round((bx+bw-2)*s),round((by+bh-2)*s)))
   pads=v.get('banner_ink_padding',{}).get(key)
   if actual and pads:
    top=actual[0]-round(by*s);bottom=round((by+bh)*s)-actual[1];check(abs(top-bottom)<=1 and top==pads['ink_top_pad_px'] and bottom==pads['ink_bottom_pad_px'],'actual centred banner ink '+key)
   else:check(False,'banner ink metrics '+key)
  tag=f'{b}-{w}x{h}-{entry["ui_scale"]}';bandh=round(360*s);labelh=math.ceil(30*s);index=list(f['states'][b]).index(st);offset=index*(bandh+labelh)+labelh
  for root,kind in [(D,'scene'),(P/'comparison','HUD')]:
   sk=(tag,kind)
   if sk not in sheets:sheets[sk]=np.asarray(Image.open(root/f'HB-13-{tag}-states.png'))
   row=sheets[sk][offset:offset+bandh]
   if kind=='scene':check(np.array_equal(row,a[:bandh]),'state sheet uses current final '+key)
   else:
    for tr in f['text_records'][key]:
     l,t,r,bt=tr['bbox_px'];color=list(bytes.fromhex(tr['color'][1:]));check(np.array_equal(np.all(row[t:bt,l:r,:3]==color,axis=2),np.all(a[t:bt,l:r,:3]==color,axis=2)),'HUD sheet native ink '+key+' '+tr['text'])
  sheet_rows+=1
  if st in ['own-action','banner']:
   for root,kind in [(D,'scene'),(P/'comparison','HUD')]:
    sk=(tag,kind,'keyframes')
    if sk not in sheets:sheets[sk]=np.asarray(Image.open(root/f'HB-13-{tag}-banner-keyframes.png'))
    for frame in ([0,3] if st=='own-action' else [1,2]):
     offset=frame*(bandh+labelh)+labelh;row=sheets[sk][offset:offset+bandh]
     if kind=='scene':check(np.array_equal(row,a[:bandh]),'keyframe sheet uses current final '+key+' '+str(frame))
     elif st=='banner':
      bx,by,bw,bh=overlap['BANNER']['rect_su'];region=(slice(round(by*s),round((by+bh)*s)),slice(round(bx*s),round((bx+bw)*s)));check(np.array_equal(np.all(row[region][:,:,:3]==[242,193,78],axis=2),np.all(a[region][:,:,:3]==[242,193,78],axis=2)),'HUD keyframe centred ink '+key+' '+str(frame))
 check(layout_count==8 and pulse_count==16 and banner_count==8 and preserved_count==120,'fix1 case coverage')
 return {'passed':not errors,'errors':errors,'two_line_cases':layout_count,'pulse_cases':pulse_count,'banner_cases':banner_count,'preservation_cases':preserved_count,'current_state_sheet_rows':sheet_rows}

if __name__=='__main__':
 result=verify_fix1();print(json.dumps(result,ensure_ascii=False));raise SystemExit(0 if result['passed'] else 1)
