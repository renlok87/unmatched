"""EN-01 deterministic masks, compositing, review sheets and verification.
Run with PYTHONDONTWRITEBYTECODE=1. Never imports or edits the icon snapshot.
"""
from pathlib import Path
import argparse, hashlib, json, shutil
import numpy as np
from PIL import Image, ImageDraw, ImageFont
from scipy.ndimage import distance_transform_edt, binary_dilation, binary_closing

ROOT = Path(__file__).resolve().parents[4]
PKG = ROOT / 'art/imagegen/env-u16-marmoreal-codex'
IMG = ROOT / 'scraped-data/derived/env-u16-marmoreal-codex'
SOURCE = ROOT / 'scraped-data/derived/concepts/env-v1/marmoreal-v1.png'
INPUTS = [
 'docs/game-design/visual/06-tasks/prompts/EN-01.codex.md',
 'scraped-data/derived/concepts/env-v1/marmoreal-v1.png',
 'art/imagegen/env-v1/concepts/manifest.json',
 'tools/art/concept_paste/marmoreal.paste.json',
 'tools/art/concept_paste/manifest.marmoreal.json',
 'docs/art-pipeline/ENV-CONCEPT-PASTE.md',
 'docs/game-design/evidence/ENV-MAPS/p7-concept-paste-2026-10-01/marmoreal-concept-flag/bench-K1-1920x1080.png',
 'tools/art/concept_paste/sarpedon.paste.json',
 'docs/game-design/de-footage/task/01-decisions.md',
 'scraped-data/images/maps/marmoreal.png',
]
SPOTS = [('nw',424,90),('ne',1245,88),('sw',152,497),('se',1520,505),('door-w',787,27),('door-e',877,27)]
FIELD_BASE = [(426,253),(1237,253),(1297,713),(375,713)]
# Expanded in the image of the board plane, 2% on all four sides.
FIELD = [(414,244),(1248,244),(1311,721),(359,721)]
REGIONS = [
 [(357,22),(451,28),(488,167),(486,204),(369,204),(315,297),(246,311),(240,218),(288,191),(335,130)],
 [(1204,26),(1295,28),(1339,167),(1425,209),(1456,290),(1398,332),(1317,262),(1181,199),(1181,154)],
 [(111,420),(211,423),(250,531),(218,635),(311,717),(314,783),(233,810),(178,740),(109,661),(74,581),(83,485)],
 [(1440,422),(1549,427),(1610,517),(1607,598),(1550,658),(1499,762),(1417,809),(1352,780),(1360,704),(1421,633),(1426,554)],
 [(774,0),(803,0),(806,71),(795,93),(775,81)],
 [(862,0),(891,0),(897,78),(878,95),(859,71)],
]
PROMPT = '''Use case: precise-object-edit.
Asset: EN-01 Marmoreal clean painted backdrop, variant {variant}.
Image 1 is the edit target: original concept C0 with the complete board field already filled neutral #808080. Do not generate or redraw any board image. Keep the grey field and wooden frame exactly in place. Keep the entire 1672x941 composition, no crop, zoom, or camera changes.
Remove only these painted elements: the four lit lanterns on the stone pedestals (glass heads, caps and hooks; each pedestal stays with a plain stone cap) at about (424,90), (1245,88), (152,497), (1520,505) pixels of this 1672x941 image; their warm light pools on the paving, the pedestals, the balustrades and the blossoms around them; the two small lit wall sconces beside the palace door at about (787,27) and (877,27) and their glow. Replace lantern silhouettes with the existing foliage/architecture behind them. Reconstruct only their small missing areas. Keep all four stone pedestal bodies, with plain flat stone caps, no knobs or replacement ornaments.
Fill the removed areas with the surrounding painted ground, stone and foliage, matching brush texture, light direction and colour of the existing painting. Keep everything else pixel-identical. Painted night scene, cold blue-grey moonlight from the west. The ONLY retained warm light is inside the open palace door at about (835,30). Remove all other orange/yellow illumination, including spill on the side stone rails, ground and adjacent cherry blossoms. Preserve pink blossom pigment.
No new objects, no figures, no text. Do not redraw the field or the painted wooden frame. Do not change the colonnade, cherry tree shapes, balustrade shapes or sky; only remove the specified local light spill on them. No water, no relief, no global de-lighting or grading. The two grey pawns are already hidden by the field.
Forbidden: copying or imitating pixels, assets, splash art, logos, card text or fonts of any commercial digital edition of a board game; brush-stroke banners and ink splatter; invented game data (card names, numbers, hero names, HP, boards, spaces); text, letters or numbers baked into textures; red fills; any element on screen that carries meaning only by colour.
{direction}
'''

def digest(p): return hashlib.sha256(p.read_bytes()).hexdigest()
def rel(p): return p.relative_to(ROOT).as_posix()
def save_json(p,obj):
 p.parent.mkdir(parents=True,exist_ok=True)
 p.write_text(json.dumps(obj,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
def sources():
 paths=[ROOT/p for p in INPUTS]+sorted((ROOT/'art/imagegen/hud-icons-v3').rglob('*'))
 return {rel(p):{'sha256':digest(p),'bytes':p.stat().st_size} for p in paths if p.is_file()}
def prepare():
 for p in [PKG/'prompts',PKG/'_tools',IMG/'concepts',IMG/'comparison']: p.mkdir(parents=True,exist_ok=True)
 baseline=PKG/'source-hashes-before.json'
 if baseline.exists(): raise RuntimeError('Baseline exists: refusing to replace pre-work evidence')
 save_json(baseline,{'schema':'en01.sources/1','files':sources()})
 shutil.copyfile(ROOT/'art/imagegen/hud-icons-v3/_tools/draw_icons.py',PKG/'_tools/draw_icons_v3_snapshot.py')
 base=Image.open(SOURCE).convert('RGB')
 assert base.size==(1672,941)
 field=Image.new('L',base.size); ImageDraw.Draw(field).polygon(FIELD,fill=255)
 field.save(IMG/'marmoreal-field-mask.png')
 union=Image.new('L',base.size); d=ImageDraw.Draw(union)
 for poly in REGIONS:d.polygon(poly,fill=255)
 # Inward 6-pixel feather: exact zero outside support, no Gaussian tails.
 support=np.asarray(union)>0
 alpha=np.rint(np.clip(distance_transform_edt(support)/6,0,1)*255).astype('uint8')
 alpha[np.asarray(field)>0]=0
 Image.fromarray(alpha).save(IMG/'marmoreal-lantern-mask.png')
 # Contract exception: neutral field is an edit too, hence explicitly in remove mask.
 remove=alpha.copy();remove[np.asarray(field)>0]=255
 Image.fromarray(remove).save(IMG/'marmoreal-remove-mask.png')
 arr=np.asarray(base).copy();arr[np.asarray(field)>0]=128
 Image.fromarray(arr).save(IMG/'concepts/marmoreal-input-field-neutral.png')
 save_json(PKG/'_tools/mask-spec.json',{'coordinate_space':'actual source 1672x941 px; spec C0 1920x1080 multiplies x and y by 1672/1920','field_base':FIELD_BASE,'field_expanded':FIELD,'margin':'2% per side in perspective; snapped to source pixels','remove_regions':REGIONS,'feather_px':6,'field_in_remove_mask':True,'spots':SPOTS})
 for v,direction in [('A','Use the most conservative local restoration; restore stone and foliage under cool moonlight.'),('B','Independent alternative: prioritise continuous brush texture and a convincing plain stone cap at each former lamp; keep the same composition and local-only edits.')]:
  (PKG/f'prompts/EN-01-{v}.txt').write_text(PROMPT.format(variant=v,direction=direction),encoding='utf-8')
 save_json(PKG/'generation-records.json',{'budget':4,'provider':'built-in image_gen','generations':[]})
 print('Prepared hashes, snapshot, masks and two prompts.')

def expand_spill_masks():
 """Local painted-light footprint; original C0 versus unretouched variant A.
 No new image content: only a deterministic support mask for compositing.
 """
 b=np.asarray(Image.open(SOURCE).convert('RGB')).astype(int)
 a=np.asarray(Image.open(IMG/'concepts/EN-01-A-raw.png').convert('RGB')).astype(int)
 search=Image.new('L',(1672,941));d=ImageDraw.Draw(search)
 polys=[[(298,0),(489,0),(531,190),(385,210),(338,328),(194,317),(193,182),(288,131)],
 [(1158,0),(1310,0),(1477,182),(1490,329),(1340,370),(1273,233),(1148,195)],
 [(0,252),(228,253),(369,374),(347,651),(328,807),(175,822),(63,687),(0,480)],
 [(1340,230),(1630,236),(1671,489),(1643,695),(1496,837),(1332,800),(1327,583)]]
 for poly in polys:d.polygon(poly,fill=255)
 search=np.asarray(search)>0
 # Detect a fall in warm R-B and R-G chroma, not pink pigment alone.
 rb=b[...,0]-b[...,2];rg=b[...,0]-b[...,1]
 shift_rb=rb-(a[...,0]-a[...,2]);shift_rg=rg-(a[...,0]-a[...,1])
 seed=search&(rb>6)&(shift_rb>10)&(shift_rg>3)
 footprint=binary_dilation(binary_closing(seed,iterations=3),iterations=10)
 support=Image.new('L',(1672,941));d=ImageDraw.Draw(support)
 for poly in REGIONS:d.polygon(poly,fill=255)
 support=(np.asarray(support)>0)|footprint
 # Freeze the complete painted wooden frame and the retained door interior.
 frame_outer=Image.new('L',(1672,941));ImageDraw.Draw(frame_outer).polygon([(387,208),(1278,208),(1366,765),(305,765)],fill=255)
 field=np.asarray(Image.open(IMG/'marmoreal-field-mask.png'))>0
 frame=(np.asarray(frame_outer)>0)&~field
 support[frame]=False;support[field]=False
 support[0:99,803:867]=False
 alpha=np.rint(np.clip(distance_transform_edt(support)/6,0,1)*255).astype('uint8')
 Image.fromarray(alpha).save(IMG/'marmoreal-lantern-mask.png')
 remove=alpha.copy();remove[field]=255;Image.fromarray(remove).save(IMG/'marmoreal-remove-mask.png')
 Image.fromarray(frame.astype('uint8')*255).save(IMG/'comparison/painted-frame-protection.png')
 spec=json.loads((PKG/'_tools/mask-spec.json').read_text(encoding='utf-8'))
 spec['spill_expansion']={'reference':'concepts/EN-01-A-raw.png','reference_sha256':digest(IMG/'concepts/EN-01-A-raw.png'),'search_polygons':polys,'seed':'source R-B > 6; delta R-B > 10; delta R-G > 3','closing_iterations':3,'dilation_iterations':10,'feather_px':6,'painted_frame_protected':True,'door_interior_protected':[803,0,867,99]}
 save_json(PKG/'_tools/mask-spec.json',spec)
 print('Expanded local spill footprint; wooden frame excluded.')

def record(variant,source):
 records=json.loads((PKG/'generation-records.json').read_text(encoding='utf-8'))
 assert len(records['generations'])<4
 dest=IMG/f'concepts/EN-01-{variant}-raw.png'
 if dest.exists():raise RuntimeError('Refusing raw overwrite')
 shutil.copyfile(source,dest)
 p=PKG/f'prompts/EN-01-{variant}.txt'
 input_path=IMG/'concepts/marmoreal-input-field-neutral.png'
 if variant=='A-R1':input_path=IMG/'concepts/EN-01-A-raw.png'
 if variant=='A-R2':input_path=IMG/'concepts/EN-01-A-R1-raw.png'
 records['generations'].append({'variant':variant,'prompt_key':f'EN-01-{variant}','prompt_file':rel(p),'prompt_sha256':digest(p),'input':rel(input_path),'input_sha256':digest(input_path),'raw_file':rel(dest),'raw_sha256':digest(dest),'raw_size':list(Image.open(dest).size),'retouched':False,'tool_managed_source':source})
 save_json(PKG/'generation-records.json',records)
 print('Recorded',variant,Image.open(dest).size)

def lab_l(rgb):
 c=rgb.astype(float)/255
 linear=np.where(c<=0.04045,c/12.92,((c+0.055)/1.055)**2.4)
 y=linear@np.array([0.2126,0.7152,0.0722])
 return 116*np.where(y>(6/29)**3,np.cbrt(y),y/(3*(6/29)**2)+4/29)-16
def gray(im):
 a=np.asarray(im).astype(float)/255
 a=np.where(a<=.04045,a/12.92,((a+.055)/1.055)**2.4)
 y=a@np.array([.2126,.7152,.0722])
 srgb=np.where(y<=.0031308,y*12.92,1.055*y**(1/2.4)-.055)
 return Image.fromarray(np.uint8(np.clip(np.rint(srgb*255),0,255))).convert('RGB')
def sheet(name,images,labels,cols=2,mono=False):
 if mono:images=[gray(i) for i in images]
 w=max(i.width for i in images);h=max(i.height for i in images)
 canvas=Image.new('RGB',(cols*w,((len(images)+cols-1)//cols)*(h+28)),(32,32,32));d=ImageDraw.Draw(canvas)
 for n,(im,label) in enumerate(zip(images,labels)):
  x=(n%cols)*w;y=(n//cols)*(h+28)
  d.text((x+8,y+7),label,fill='white');canvas.paste(im,(x,y+28))
 canvas.save(IMG/f'comparison/{name}{"-gray" if mono else "-colour"}.png')
def finalize(selected):
 base=Image.open(SOURCE).convert('RGB');b=np.asarray(base)
 field=np.asarray(Image.open(IMG/'marmoreal-field-mask.png'))>0
 alpha=np.asarray(Image.open(IMG/'marmoreal-lantern-mask.png')).astype(float)/255
 remove=np.asarray(Image.open(IMG/'marmoreal-remove-mask.png'))
 records=json.loads((PKG/'generation-records.json').read_text(encoding='utf-8'))
 comps={};metrics={}
 yy,xx=np.indices(field.shape)
 for rec in records['generations']:
  v=rec['variant'];raw=Image.open(ROOT/rec['raw_file']).convert('RGB')
  # Size adaptation only; original raw preserved byte-for-byte above.
  edit=np.asarray(raw.resize(base.size,Image.Resampling.LANCZOS))
  out=np.rint(b*(1-alpha[...,None])+edit*alpha[...,None]).astype('uint8');out[field]=128
  im=Image.fromarray(out);im.save(IMG/f'concepts/EN-01-{v}-composite.png');comps[v]=im
  ls=lab_l(out);spot_metrics=[]
  for id,x,y in SPOTS:
   central=(xx>=x-12)&(xx<x+12)&(yy>=y-12)&(yy<y+12)
   r=np.hypot(xx-x,yy-y);ring=(r>=24)&(r<48)
   m=float(np.median(ls[central]));rm=float(np.median(ls[ring]));delta=abs(m-rm)
   spot_metrics.append({'id':id,'xy':[x,y],'central_Lstar':round(m,4),'ring_Lstar':round(rm,4),'abs_delta_Lstar':round(delta,4),'pass':delta<=4,'central_pixels':int(central.sum()),'ring_pixels':int(ring.sum()),'ring_clipped_by_image':y<48})
  metrics[v]=spot_metrics
 final=comps[selected];final.save(IMG/'marmoreal-clean.png');f=np.asarray(final)
 for mono in [False,True]:
  sheet('01-full',[base,final],['C0 original 1672x941',f'Clean {selected} 1672x941'],mono=mono)
  # K1 x0.65 image-plane framing; blank border denotes unpainted EN-02 area.
  frames=[]
  for im in [base,final]:
   small=im.resize((1087,612),Image.Resampling.LANCZOS)
   framed=Image.new('RGB',base.size,(48,48,48));framed.paste(small,((1672-1087)//2,(941-612)//2));frames.append(framed)
  sheet('02-K1-x065',frames,['C0 K1 x0.65 - unpainted border','Clean K1 x0.65 - EN-02 pending'],mono=mono)
  sheet('03-working-1087x612',[base.resize((1087,612),Image.Resampling.LANCZOS),final.resize((1087,612),Image.Resampling.LANCZOS)],['C0 working 1087x612','Clean working 1087x612'],mono=mono)
  sheet('04-working-836x471',[base.resize((836,471),Image.Resampling.LANCZOS),final.resize((836,471),Image.Resampling.LANCZOS)],['C0 working 836x471','Clean working 836x471'],mono=mono)
  crops=[];labels=[]
  for id,x,y in SPOTS:
   box=(max(0,x-96),max(0,y-64),min(1672,x+96),min(941,y+128))
   for im,tag in [(base,'C0'),(final,'clean')]:
    crops.append(im.crop(box).resize((384,384),Image.Resampling.NEAREST));labels.append(f'{id} {tag} K2 crop {box}')
  sheet('05-K2-six-lights',crops,labels,mono=mono)
  sheet('06-variants',[base.resize((836,471)),comps['A'].resize((836,471)),comps['B'].resize((836,471))],['C0','Variant A','Variant B'],cols=3,mono=mono)
  sheet('07-full-variants',[comps['A'],comps['B']],['Variant A master','Variant B master'],mono=mono)
  refinements=[comps[v] for v in ['A','A-R1','A-R2'] if v in comps]
  refinement_labels=[v for v in ['A','A-R1','A-R2'] if v in comps]
  sheet('11-refinements-master',refinements,refinement_labels,cols=3,mono=mono)
  sheet('12-refinements-working',[i.resize((836,471),Image.Resampling.LANCZOS) for i in refinements],refinement_labels,cols=3,mono=mono)
 changed=np.any(f!=b,axis=2);outside=changed&(remove==0)
 diff=np.zeros_like(b);diff[outside]=255;Image.fromarray(diff).save(IMG/'comparison/08-diff-outside-remove-mask.png')
 heat=np.max(np.abs(f.astype(int)-b.astype(int)),axis=2).astype('uint8');Image.fromarray(heat).save(IMG/'comparison/09-diff-all.png')
 # A visual mask overlay for review; field light gray, edit support cyan.
 overlay=b.copy();support=(remove>0)&~field;overlay[support]=(b[support]*.45+np.array([0,200,255])*.55).astype('uint8');overlay[field]=(b[field]*.4+128*.6).astype('uint8')
 Image.fromarray(overlay).save(IMG/'comparison/10-mask-overlay.png')
 before=json.loads((PKG/'source-hashes-before.json').read_text(encoding='utf-8'))['files'];after=sources()
 changed_sources=[p for p in sorted(set(before)|set(after)) if before.get(p)!=after.get(p)]
 failures=[s['id'] for s in metrics[selected] if not s['pass']]
 verification={'task':'EN-01','status':'предложено','selected':selected,'source_unchanged':not changed_sources,'changed_sources':changed_sources,'input_count':len(before),'outside_folder':[],
 'write_scope':'All agent filesystem writes are confined to the two authorised roots. Provider-managed imagegen staging is recorded separately in generation-records.json, not a repository file.',
 'source_hashes_after':after,'snapshot_unchanged_copy':digest(PKG/'_tools/draw_icons_v3_snapshot.py')==before['art/imagegen/hud-icons-v3/_tools/draw_icons.py']['sha256'],
 'generations':len(records['generations']),'budget':4,'output':{'size':list(final.size),'mode':final.mode},'masks':{p: {'size':list(Image.open(IMG/p).size),'mode':Image.open(IMG/p).mode} for p in ['marmoreal-field-mask.png','marmoreal-remove-mask.png','marmoreal-lantern-mask.png']},
 'changed_pixels_outside_remove_mask':int(outside.sum()),'outside_diff_max':int(diff.max()),'changed_pixels_total':int(changed.sum()),'field_all_808080':bool(np.all(f[field]==128)),
 'field_in_remove_mask':True,'composite':'C0 outside lantern support, generated edit inside 6px inward feather, field overwritten #808080 and included in remove support',
 'Lstar_method':'sRGB decode to linear Rec709/D65 Y, CIELAB L*; median in half-open 24x24 source-pixel square versus circular annulus 24<=r<48; top rings clipped to canvas, no padding',
 'six_spot_Lstar':metrics,'limits':[f'Lstar tolerance not met at {x}' for x in failures],
 'K1_framing':'2D image-plane x0.65 comparison only; no Unreal camera certification or outpainting. Empty outer border is neutral charcoal, not water.',
 'grayscale_method':'linear-light Rec709 luma encoded back to sRGB',
 'visual_review':{'performed':False,'note':'Populate only after opening final and comparison images'},
 'acceptance_pass':False}
 save_json(PKG/'verification.json',verification)
 print(json.dumps({'selected':selected,'Lstar':metrics,'outside_changed':int(outside.sum()),'source_unchanged':not changed_sources},ensure_ascii=False))
def manifest():
 files={rel(p):{'sha256':digest(p),'bytes':p.stat().st_size} for root in [PKG,IMG] for p in sorted(root.rglob('*')) if p.is_file() and p.name!='manifest-sha256.json'}
 save_json(PKG/'manifest-sha256.json',{'schema':'en01.manifest/1','excludes_self':True,'files':files})
 print('Manifest:',len(files),'files')
if __name__=='__main__':
 parser=argparse.ArgumentParser();parser.add_argument('action',choices=['prepare','expand-masks','record','finalize','manifest']);parser.add_argument('--variant',default='A');parser.add_argument('--source');a=parser.parse_args()
 if a.action=='prepare':prepare()
 elif a.action=='record':record(a.variant,a.source)
 elif a.action=='finalize':finalize(a.variant)
 elif a.action=='expand-masks':expand_spill_masks()
 else:manifest()
