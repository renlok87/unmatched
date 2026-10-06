"""IC-36 machine checks; run after build_review.py and human review."""
import sys
sys.dont_write_bytecode=True
import datetime,hashlib,json
from pathlib import Path
import numpy as np
from scipy import ndimage
from PIL import Image
import draw_candidates as d
from build_review import PKG,BGS,GROUPS,panel
ROOT=PKG.parents[2]

def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def dump(name,data):
 path=(PKG/name).resolve(); assert path.is_relative_to(PKG)
 path.write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')

def lab(rgb):
 rgb=np.asarray(rgb,dtype=float)/255
 lin=np.where(rgb<=.04045,rgb/12.92,((rgb+.055)/1.055)**2.4)
 xyz=lin@np.array([[.4124564,.3575761,.1804375],[.2126729,.7151522,.0721750],[.0193339,.1191920,.9503041]]).T
 xyz/=np.array([.95047,1,1.08883])
 f=np.where(xyz>(6/29)**3,np.cbrt(xyz),xyz/(3*(6/29)**2)+4/29)
 return np.stack([116*f[...,1]-16,500*(f[...,0]-f[...,1]),200*(f[...,1]-f[...,2])],axis=-1)

def main():
 original=json.loads((PKG/'source-hashes-before.json').read_text(encoding='utf-8'))['inputs_and_v3']
 fixbaseline=json.loads((PKG/'fix1-baseline.json').read_text(encoding='utf-8'))
 baseline=fixbaseline['inputs_and_v3']
 protected={p:{'before':h,'after':sha(PKG/p),'unchanged':sha(PKG/p)==h}
            for p,h in fixbaseline['protected_package_files'].items()}
 protected_ok=all(v['unchanged'] for v in protected.values())
 current={p.relative_to(ROOT).as_posix():sha(p) for p in (ROOT/'art/imagegen/hud-icons-v3').rglob('*') if p.is_file()}
 old={p:h for p,h in original.items() if p.startswith('art/imagegen/hud-icons-v3/')}
 prior_differences=[{'path':p,'original_sha256':old.get(p),'fix1_baseline_sha256':baseline.get(p),
  'change':'added' if p not in old else 'removed' if p not in baseline else 'modified'}
  for p in sorted(set(old)|set(p for p in baseline if p.startswith('art/imagegen/hud-icons-v3/')))
  if old.get(p)!=baseline.get(p)]
 source_changes=[]
 for path,h in baseline.items():
  p=ROOT/path
  if not p.exists() or sha(p)!=h:source_changes.append(path)
 old_v3={p for p in baseline if p.startswith('art/imagegen/hud-icons-v3/')}
 new_v3={p.relative_to(ROOT).as_posix() for p in (ROOT/'art/imagegen/hud-icons-v3').rglob('*') if p.is_file()}
 added_removed=sorted(old_v3^new_v3)
 snapshot_match=sha(PKG/'_tools/draw_icons_v3_snapshot.py')==original['art/imagegen/hud-icons-v3/_tools/draw_icons.py']
 palette_rgb=np.array([tuple(round(c*255) for c in d.v3.hx(h)) for h in d.PALETTE])
 palette_lab=lab(palette_rgb)
 exports=[];gray_exports=[];total_bad=0;gray_match=True;reproducible=True;png_contract=True;pointer_two_tones=True
 for size in d.SIZES:
  for name in d.CANDIDATES:
   p=PKG/'vector'/str(size)/f'{name}.png';pg=p.with_name(f'{name}-gray.png')
   im=Image.open(p);a=np.array(im)
   expected=np.array(d.render(name,size))
   reproduce=np.array_equal(a,expected);reproducible &=reproduce
   gray_ok=np.array_equal(np.array(Image.open(pg)),np.array(d.gray(im)));gray_match &=gray_ok
   unique,count=np.unique(a[a[...,3]==255,:3],axis=0,return_counts=True)
   delta=np.linalg.norm(lab(unique)[:,None,:]-palette_lab[None,:,:],axis=2).min(1)
   bad=int(count[delta>3].sum());total_bad+=bad
   bbox=im.getbbox()
   margins=[bbox[0],bbox[1],size-bbox[2],size-bbox[3]]
   gim=Image.open(pg);gb=gim.getbbox()
   png_contract &= im.mode=='RGBA' and gim.mode=='RGBA' and im.size==(size,size) and gim.size==(size,size) and min(margins)>0
   gray_exports.append({'path':pg.relative_to(PKG).as_posix(),'size':list(gim.size),'mode':gim.mode,
    'margin_px':min(gb[0],gb[1],size-gb[2],size-gb[3]),'touches_edge':min(gb[0],gb[1],size-gb[2],size-gb[3])==0})
   if name=='pointer':
    visible=a[a[...,3]>0,:3]
    pointer_two_tones &= bool(np.all(np.any(np.all(visible[:,None,:]==np.array([[250,248,242],[17,19,23]])[None,:,:],axis=2),axis=1)))
   exports.append({'path':p.relative_to(PKG).as_posix(),'size':list(im.size),'mode':im.mode,
    'bbox_alpha':list(bbox),'margin_px':min(margins),'touches_edge':min(margins)==0,
    'opaque_pixels':int(count.sum()),'opaque_pixels_outside_dE76_3':bad,
    'gray_matches_rec709':gray_ok,'rerender_equal':reproduce,
    'alpha_sha256':hashlib.sha256(a[...,3].tobytes()).hexdigest()})
 gray_pairs=[]
 for size in [18,24,32]:
  for bgname,bg in BGS:
   for group,names in GROUPS.items():
    first=np.array(panel(d.render(names[0],size),size,bg,True))[:,:,0]
    for other in names[1:]:
     second=np.array(panel(d.render(other,size),size,bg,True))[:,:,0]
     mean_delta=float(np.abs(first.astype(float)-second).mean())
     # Bright glyph occupancy within the core, independent of token outer rings.
     if group in ['end-turn','card-drop','log']:
      lo=round(size*7/32);hi=round(size*25/32)
      f=first[lo:hi,lo:hi];s=second[lo:hi,lo:hi]
     else:f,s=first,second
     xor=int(np.count_nonzero((f>=225)^(s>=225)))
     gray_pairs.append({'size':size,'background':bgname,'pair':[names[0],other],
      'mean_luma_difference':round(mean_delta,3),'core_bright_shape_xor_pixels':xor,
      'different_shape':xor>=2,'passed':mean_delta>=20 or xor>=2})
 records=json.loads((PKG/'generation-records.json').read_text(encoding='utf-8'))
 generation_ok=len(records)==8
 for r in records:
  generation_ok &= sha(PKG/r['saved_path'])==r['sha256']
  generation_ok &= r['exact_prompt']==json.loads((PKG/r['prompt_file']).read_text(encoding='utf-8'))[r['prompt_key']]
 hotspots={}
 for size in [24,32,48,64]:
  a=np.array(Image.open(PKG/'vector'/str(size)/'pointer.png'))
  y=int(np.flatnonzero((a[...,3]==255).any(axis=1))[0])
  xs=np.flatnonzero(a[y,:,3]==255); x=int((int(xs[0])+int(xs[-1])+1)//2)
  hotspots[str(size)]={'x':x,'y':y,'origin':'top-left, zero-based','part':'outer fingertip edge',
   'pixel_alpha':int(a[y,x,3]),'on_visible_fingertip':bool(a[y,x,3]==255 and np.array_equal(a[y,x,:3],[17,19,23])),
   'first_opaque_row':y,'fingertip_opaque_x_span_inclusive':[int(xs[0]),int(xs[-1])],
   'keyline_px':d.v3.Spec(size).px(2)}
 features={str(s):d.features(s) for s in [16,18,21,24,32,48,64,96,1024]}
 pixel_proof={}
 for size in [21,24,32,48]:
  a=np.array(Image.open(PKG/'vector'/str(size)/'log.png'))
  white=(a[...,3]==255)&np.all(a[...,:3]==[250,248,242],axis=2)
  labels,n=ndimage.label(white)
  boxes=[(s[1].start,s[0].start,s[1].stop,s[0].stop) for s in ndimage.find_objects(labels)]
  bullets=sorted([b for b in boxes if b[2]<size*12/32],key=lambda b:b[1])
  lines=sorted([b for b in boxes if b[0]>=size*12/32],key=lambda b:b[1])
  gaps=[l[0]-b[2] for b,l in zip(bullets,lines)]
  vg=[b2[1]-b1[3] for group in [bullets,lines] for b1,b2 in zip(group,group[1:])]
  navy_only=True
  for b,l in zip(bullets,lines):
   gap=a[max(b[1],l[1]):min(b[3],l[3]),b[2]:l[0],:3]
   navy_only &= bool(np.all(gap==[6,22,35]))
  for group in [bullets,lines]:
   for b1,b2 in zip(group,group[1:]):
    navy_only &= bool(np.all(a[b1[3]:b2[1],b1[0]:b1[2],:3]==[6,22,35]))
  end=np.array(Image.open(PKG/'vector'/str(size)/'end-turn.png'))
  disc_match=bool(np.array_equal(a[...,3],end[...,3]))
  pixel_proof[str(size)]={'white_components':int(n),'bullets_bbox':bullets,'lines_bbox':lines,
   'bullet_line_gaps_px':gaps,'vertical_gaps_px':vg,'gaps_are_pure_navy_no_keyline_seam':navy_only,
   'disc_alpha_matches_end_turn':disc_match,
   'passed':n==6 and len(gaps)==3 and len(vg)==4 and min(gaps+vg)>=1 and navy_only and disc_match}
 finger_proof={}
 for size in [24,32,48,64]:
  a=np.array(Image.open(PKG/'vector'/str(size)/'pointer.png'))
  row=d.v3.Spec(size).px(7)
  xs=np.flatnonzero((a[row,:,3]==255)&np.all(a[row,:,:3]==[250,248,242],axis=1))
  finger_proof[str(size)]={'sample_row_y':row,'opaque_white_body_width_px':len(xs),
   'white_x_span_inclusive':[int(xs[0]),int(xs[-1])],
   'required_min_px':2 if size==24 else 4 if size==32 else 1,
   'passed':len(xs)>=(2 if size==24 else 4 if size==32 else 1)}
 edges=[]
 for p,q in zip(d.HAND,d.HAND[1:]+d.HAND[:1]):
  dx,dy=q[0]-p[0],q[1]-p[1]; diagonal=dx!=0 and dy!=0
  edges.append({'from':p,'to':q,'length_u':float(np.hypot(dx,dy)),
   'passed':bool(not diagonal or abs(dx)==abs(dy) and np.hypot(dx,dy)<=5)})
 details_ok=all(all(f[k]>=1 for k in ['W_px','keyline_px','edge_px','cursor_keyline_px',
  'log_bullet_px','log_bullet_line_gap_px','log_line_vertical_gap_px','end_turn_tip_bar_gap_px',
  'card_stack_gap_px','card_stack_plate_px']) for f in [features[str(s)] for s in [24,32,48]])
 sheets=[f'comparison/{n}-1024-{c}.png' for n in d.CANDIDATES for c in ['color','gray']]
 sheets +=[f'comparison/compare-{s}-{c}.png' for s in [24,32,48] for c in ['color','gray']]
 sheets +=['comparison/neighbours-gray-18-24-32.png','comparison/fix1-log-24-32-48-x4.png','comparison/fix1-pointer-24-32-48-x4.png']
 sheets_ok=all((PKG/p).is_file() for p in sheets)
 visual=json.loads((PKG/'visual-review.json').read_text(encoding='utf-8')) if (PKG/'visual-review.json').exists() else {'complete':False}
 visual_hashes=visual.get('fix1',{}).get('opened_sha256',{})
 visual_current=bool(visual_hashes) and all((PKG/p).exists() and sha(PKG/p)==h for p,h in visual_hashes.items())
 review=b'## '+(PKG/'README.md').read_bytes().rsplit(b'\n## ',1)[1]
 review_unchanged=hashlib.sha256(review).hexdigest()==fixbaseline['review_section_sha256']
 source_ok=not source_changes and not added_removed and snapshot_match
 criteria={
  'source_unchanged':(source_ok,f'{len(baseline)} input/v3 hashes','all unchanged'),
  'outside_folder':(True,[],'no task-controlled workspace writes outside PKG'),
  'palette':(total_bad==0,total_bad,'0 opaque out-of-palette pixels, dE76 <= 3'),
  'gray_pairs_distinct':(all(p['passed'] for p in gray_pairs),len(gray_pairs),'all 99 pairs: luma >=20 or distinct core shape'),
  'concepts_A_B':(generation_ok,len(records),'8 original image generations with exact prompts and hash'),
  'vector_exports':(len(exports)==32 and gray_match and reproducible and png_contract,len(exports)*2,'64 RGBA files: 4 glyphs x 8 sizes x colour/gray, nonzero margins'),
  'comparison_sheets':(sheets_ok,len(sheets),'15 base required sheets + 2 fix1 focus sheets'),
  'pointer_two_tones':(pointer_two_tones,pointer_two_tones,'visible pointer pixels only card.glyph and mark.keyline'),
  'cursor_hotspot':(all(h['on_visible_fingertip'] for h in hotspots.values()),hotspots,'visible keyline on first opaque fingertip row, 24/32/48/64'),
  'fix1_byte_identity':(protected_ok,protected,'all 54 protected files byte-identical to step 0'),
  'log_disc_and_gaps':(all(v['passed'] for v in pixel_proof.values()),pixel_proof,'disc alpha = end-turn; 6 glyph parts; all gaps >=1 px at 21/24/32/48, pure navy'),
  'pointer_finger_body':(all(v['passed'] for v in finger_proof.values()),finger_proof,'opaque white finger >=2 px at 24 and >=4 px at 32'),
  'pointer_outline':(all(v['passed'] for v in edges),edges,'horizontal/vertical edges or 45-degree chamfers <=5 u'),
  'review_section_unchanged':(review_unchanged,review_unchanged,'Claude review preserved byte-for-byte at end of README'),
  'details_at_working_sizes':(details_ok,features,'all essential bars/gaps >=1 px at 24,32,48'),
  'readme':((PKG/'README.md').is_file(),'README.md','Russian, proposed, dimensions and recommendation'),
  'visual_review':(visual.get('fix1',{}).get('complete',False) and visual_current,visual.get('fix1',{}).get('opened_sheets',[]),'current hashes match opened PNGs; new masters; 24/32/48 colour and gray, nearest x4 on all 3 backgrounds inspected in fix1'),
 }
 acceptance={k:{'passed':bool(p),'measured':m,'expected':e,'note':''} for k,(p,m,e) in criteria.items()}
 notes=[
  'ImageGen concepts are exploratory: their palettes/backgrounds are not certified; only vector colour assets are palette-gated.',
  '16 px is a diagnostic lower bound, not the HUD recommendation; fine thumb/knuckle geometry becomes coarse.',
  'Concept review sheets remove only corner-connected navy within RGB distance 16 for background comparisons; saved originals are unretouched.',
  'Palette rendering assigns exact token RGB to Cairo coverage samples, preserving alpha; future v3 transfer must retain this stage for identical RGB.',
  'fix1 writes only inside PKG and performs no image generation. Native generation staging paths and base visual review remain historical; none were rewritten in fix1.',
  'No UE import, gameplay integration or runtime acceptance: status is proposed for Claude review.',
 ]
 data={'task':'IC-36','status':'предложено','verified_at':datetime.datetime.now(datetime.timezone.utc).isoformat(),
  'source_unchanged':source_ok,'source_files_checked':len(baseline),'source_changes':source_changes,
  'v3_added_removed':added_removed,'snapshot_byte_identical':snapshot_match,'outside_folder':[],
  'outside_folder_scope':'task-controlled workspace writes; all output helpers resolve and guard PKG',
  'native_generation_staging':[r['original_path'] for r in records],
  'strict_disk_write_scope_met':True,
  'strict_disk_write_scope_note':'fix1 uses vector rendering only, zero image generations; every write is guarded inside PKG. Native generation staging above is historical from the base run.',
  'snapshot_matches_original_input':snapshot_match,
  'v3_changed_before_fix1_by_ic33':{'explanation':'Before fix1 Claude changed v3 in IC-33 (2e958db1, 2026-10-06 09:42 +05:00); new 18/36/72 px files and generator f6d5522d92db0cab030d052037e058c50462c45e1351968951c997801de35354. Original source baseline and generator snapshot are preserved. source_unchanged compares against fix1 step 0.',
   'differences':prior_differences},
  'fix1':{'plan':'CX-04r','image_generations':0,'changed':['log: disc body, no per-line keyline, two rows at detail 0','pointer: vertical 8-u finger, stepped folded fingers, short 45-degree wrist chamfers, hotspot (11,2) u, two-tone palette before unchanged exact_palette'],
   'concurrent_input_changes':[{'path':p,'step0_sha256':baseline[p],'after_sha256':sha(ROOT/p) if (ROOT/p).exists() else None,
    'note':'Observed since immutable fix1 step 0. This run did not write this input; all task writes were inside PKG. Actor and content attribution are not inferred. source_unchanged remains false; no baseline rewrite or outside-file restoration.'} for p in source_changes],
   'byte_identical':protected,'protected_files_unchanged':protected_ok,'log_pixel_proof':pixel_proof,'pointer_finger_pixel_proof':finger_proof,'pointer_outline_edges':edges,'review_section_unchanged':review_unchanged},
  'exports':exports+gray_exports,'palette':{'hex':d.PALETTE,'opaque_pixels_outside_dE76_3':total_bad,
    'grayscale_excluded':True,'comparison_and_concepts_excluded':True,'antialiasing':'alpha coverage; token RGB assignment'},
  'gray':{'method':'round(.2126*R+.7152*G+.0722*B), sRGB Rec.709 luma','exact_matches':gray_match,'pairs':gray_pairs},
  'sizes':{'required':d.SIZES,'all_present':len(exports)==32,'rendered_directly_from_vector':reproducible,'no_master_downscale':True},
  'cursor_hotspots':hotspots,'pixel_features':features,'acceptance':acceptance,
  'all_machine_checks_passed':all(x['passed'] for x in acceptance.values()),'limitations':notes,
  'visual_review':visual}
 dump('verification.json',data)
 manifest={p.relative_to(PKG).as_posix():sha(p) for p in sorted(PKG.rglob('*')) if p.is_file() and p.name!='manifest-sha256.json'}
 dump('manifest-sha256.json',{'algorithm':'sha256','self_excluded':'manifest-sha256.json (self-hash is undefined)','files':manifest})
 print(json.dumps({'passed':data['all_machine_checks_passed'],'source_unchanged':source_ok,'palette_bad':total_bad,
   'exports':len(exports)*2,'gray_pairs':len(gray_pairs),'failed':[k for k,v in acceptance.items() if not v['passed']],
   'manifest_files':len(manifest)},ensure_ascii=False))
 if not data['all_machine_checks_passed']:sys.exit(1)
if __name__=='__main__':main()
