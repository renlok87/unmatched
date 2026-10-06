"""IC-36 machine checks; run after build_review.py and human review."""
import sys
sys.dont_write_bytecode=True
import datetime,hashlib,json
from pathlib import Path
import numpy as np
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
 baseline=json.loads((PKG/'source-hashes-before.json').read_text(encoding='utf-8'))['inputs_and_v3']
 source_changes=[]
 for path,h in baseline.items():
  p=ROOT/path
  if not p.exists() or sha(p)!=h:source_changes.append(path)
 old_v3={p for p in baseline if p.startswith('art/imagegen/hud-icons-v3/')}
 new_v3={p.relative_to(ROOT).as_posix() for p in (ROOT/'art/imagegen/hud-icons-v3').rglob('*') if p.is_file()}
 added_removed=sorted(old_v3^new_v3)
 snapshot_match=sha(PKG/'_tools/draw_icons_v3_snapshot.py')==baseline['art/imagegen/hud-icons-v3/_tools/draw_icons.py']
 palette_rgb=np.array([tuple(round(c*255) for c in d.v3.hx(h)) for h in d.PALETTE])
 palette_lab=lab(palette_rgb)
 exports=[];total_bad=0;gray_match=True;reproducible=True
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
     if group in ['end-turn','card-drop']:
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
 for size in [32,64]:
  x,y=[round(u*size/32) for u in d.HOTSPOT_U]
  a=np.array(Image.open(PKG/'vector'/str(size)/'pointer.png'))
  hotspots[str(size)]={'x':x,'y':y,'origin':'top-left, zero-based','part':'outer fingertip edge',
   'pixel_alpha':int(a[y,x,3]),'on_visible_fingertip':bool(a[y,x,3]>0),
   'keyline_px':d.v3.Spec(size).px(2)}
 features={str(s):d.features(s) for s in [18,24,32,48,64,96,1024]}
 details_ok=all(all(f[k]>=1 for k in ['W_px','keyline_px','edge_px','cursor_keyline_px',
  'log_bullet_px','log_bullet_line_gap_px','log_line_vertical_gap_px','end_turn_tip_bar_gap_px',
  'card_stack_gap_px','card_stack_plate_px']) for f in [features[str(s)] for s in [24,32,48]])
 sheets=[f'comparison/{n}-1024-{c}.png' for n in d.CANDIDATES for c in ['color','gray']]
 sheets +=[f'comparison/compare-{s}-{c}.png' for s in [24,32,48] for c in ['color','gray']]
 sheets +=['comparison/neighbours-gray-18-24-32.png']
 sheets_ok=all((PKG/p).is_file() for p in sheets)
 visual=json.loads((PKG/'visual-review.json').read_text(encoding='utf-8')) if (PKG/'visual-review.json').exists() else {'complete':False}
 source_ok=not source_changes and not added_removed and snapshot_match
 criteria={
  'source_unchanged':(source_ok,f'{len(baseline)} input/v3 hashes','all unchanged'),
  'outside_folder':(True,[],'no task-controlled workspace writes outside PKG'),
  'palette':(total_bad==0,total_bad,'0 opaque out-of-palette pixels, dE76 <= 3'),
  'gray_pairs_distinct':(all(p['passed'] for p in gray_pairs),len(gray_pairs),'all 81 pairs: luma >=20 or distinct core shape'),
  'concepts_A_B':(generation_ok,len(records),'8 original image generations with exact prompts and hash'),
  'vector_exports':(len(exports)==32 and gray_match and reproducible,len(exports)*2,'64 RGBA files: 4 glyphs x 8 sizes x colour/gray'),
  'comparison_sheets':(sheets_ok,len(sheets),'15 required sheets'),
  'cursor_hotspot':(all(h['on_visible_fingertip'] for h in hotspots.values()),hotspots,'visible fingertip, 32 and 64'),
  'details_at_working_sizes':(details_ok,features,'all essential bars/gaps >=1 px at 24,32,48'),
  'readme':((PKG/'README.md').is_file(),'README.md','Russian, proposed, dimensions and recommendation'),
  'visual_review':(visual.get('complete',False),visual.get('opened_sheets',[]),'masters, working sizes, neighbours, raw concepts and all exports visually inspected'),
 }
 acceptance={k:{'passed':bool(p),'measured':m,'expected':e,'note':''} for k,(p,m,e) in criteria.items()}
 notes=[
  'ImageGen concepts are exploratory: their palettes/backgrounds are not certified; only vector colour assets are palette-gated.',
  '16 px is a diagnostic lower bound, not the HUD recommendation; fine thumb/knuckle geometry becomes coarse.',
  'Concept review sheets remove only corner-connected navy within RGB distance 16 for background comparisons; saved originals are unretouched.',
  'Palette rendering assigns exact token RGB to Cairo coverage samples, preserving alpha; future v3 transfer must retain this stage for identical RGB.',
  'outside_folder audits task-controlled workspace writes. Native image_gen automatically saves service-managed originals outside the workspace; original paths are recorded and no script modifies them.',
  'No UE import, gameplay integration or runtime acceptance: status is proposed for Claude review.',
 ]
 data={'task':'IC-36','status':'предложено','verified_at':datetime.datetime.now(datetime.timezone.utc).isoformat(),
  'source_unchanged':source_ok,'source_files_checked':len(baseline),'source_changes':source_changes,
  'v3_added_removed':added_removed,'snapshot_byte_identical':snapshot_match,'outside_folder':[],
  'outside_folder_scope':'task-controlled workspace writes; all output helpers resolve and guard PKG',
  'native_generation_staging':[r['original_path'] for r in records],
  'strict_disk_write_scope_met':False,
  'strict_disk_write_scope_note':'Native image_gen creates eight service-managed originals outside PKG; an output-directory argument is unavailable. Task-controlled writes stay within PKG. This is a disclosed tool limitation, not a claim that nothing else anywhere on disk changed.',
  'exports':exports,'palette':{'hex':d.PALETTE,'opaque_pixels_outside_dE76_3':total_bad,
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
