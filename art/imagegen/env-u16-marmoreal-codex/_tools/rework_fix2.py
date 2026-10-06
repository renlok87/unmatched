"""EN-01 fix2. All writes stay in PKG/IMG. Run python -B.

Reuses frozen measurement helpers, never executes the fix1 build/finalizers.
Imagegen is called separately; raw outputs are copied byte-for-byte.
"""
import argparse, csv, hashlib, json, shutil
import re
from pathlib import Path
import numpy as np
from PIL import Image, ImageDraw
from scipy.ndimage import distance_transform_edt as edt, gaussian_filter
import rework_r3 as r
from build_plate import ROOT, PKG, IMG, SOURCE, SPOTS, gray, sheet, digest, rel, save_json

COMP = IMG / 'comparison'
BASELINE = PKG / 'fix2-baseline.json'
REGIONS = {
    'nw': {'crop_box':[328,0,520,192], 'polygon':[(405,40),(419,41),(426,51),(431,65),(431,87),(430,102),(397,102),(390,88),(386,68),(390,53)], 'feather_inward_px':8},
    'ne': {'crop_box':[1149,0,1341,192], 'polygon':[(1242,40),(1254,41),(1266,56),(1271,76),(1266,94),(1260,102),(1230,102),(1230,78),(1233,58),(1238,48)], 'feather_inward_px':8},
}

def prepare():
    old = Image.open(COMP/'fix2-before-clean.png').convert('RGB')
    field = np.asarray(Image.open(IMG/'marmoreal-field-mask.png'))>0
    for spot,entry in REGIONS.items():
        x0,y0,x1,y1=entry['crop_box']
        assert not field[y0:y1,x0:x1].any()
        path=IMG/f'concepts/EN-01-R3-{spot}-1-input.png'
        prompt=PKG/f'prompts/EN-01-R3-{spot}-1.txt'
        assert not path.exists() and not prompt.exists()
        old.crop(entry['crop_box']).resize((1024,1024),Image.Resampling.LANCZOS).save(path)
        text=(f'Edit this crop of a painted night garden at the {spot.upper()} pedestal. Remove the dark leftover lantern silhouette standing on the stone pedestal: the peaked roof outline with curled corners, the two thin vertical posts of its frame and the stem in its centre. Replace it with the dark night background that surrounds it: the dark window recess, the thin dark vines and the small pink blossoms, matching the brush texture and the cold blue-grey moonlight from the west. Keep the stone pedestal with its plain flat cap, the marble columns and every blossom outside the silhouette unchanged. No new objects, no lantern, no figures, no text, no warm light. '+r.FORBIDDEN)
        prompt.write_text(text,encoding='utf-8')
    print('Prepared NW and NE, SE inspection: no roof, posts or hook; retained.')

def record(spot,source):
    assert spot in REGIONS
    records=json.loads((PKG/'generation-records.json').read_text(encoding='utf-8'))
    b=json.loads(BASELINE.read_text(encoding='utf-8'))
    previous=b['generation_records_before']['generations']
    assert records['generations'][:len(previous)]==previous
    assert len(records['generations'])-len(previous)<3
    variant=f'R3-{spot}-1'
    assert not any(x['variant']==variant for x in records['generations'])
    dst=IMG/f'concepts/EN-01-{variant}-raw.png'
    assert not dst.exists()
    shutil.copyfile(source,dst)
    prompt=PKG/f'prompts/EN-01-{variant}.txt';inp=IMG/f'concepts/EN-01-{variant}-input.png'
    records['generations'].append({'variant':variant,'run':'CX-07r fix2','prompt_key':f'EN-01-{variant}','prompt_file':rel(prompt),'prompt_sha256':digest(prompt),'input':rel(inp),'input_sha256':digest(inp),'raw_file':rel(dst),'raw_sha256':digest(dst),'raw_size':list(Image.open(dst).size),'crop_box':REGIONS[spot]['crop_box'],'retouched':False,'tool_managed_source':str(source),'submitted_prompt_sha256':digest(prompt),'submitted_prompt_normalization':'exact UTF-8 file text'})
    records.update(rework_budget=4,rework_generations=len(records['generations'])-4,fix2_budget=3,fix2_generations=len(records['generations'])-len(previous))
    save_json(PKG/'generation-records.json',records)
    print({'recorded':variant,'size':Image.open(dst).size})

def build():
    b=json.loads(BASELINE.read_text(encoding='utf-8'))
    previous=r.rgb(COMP/'fix2-before-clean.png');base=r.rgb(SOURCE)
    assert digest(COMP/'fix2-before-clean.png')==b['files'][rel(IMG/'marmoreal-clean.png')]['sha256']
    remove=np.asarray(Image.open(IMG/'marmoreal-remove-mask.png'));field=np.asarray(Image.open(IMG/'marmoreal-field-mask.png'))>0
    support=(remove>0)&~field
    decisions=json.loads((PKG/'_tools/fix2-edit-review.json').read_text(encoding='utf-8'))
    spec=b['mask_spec_before'];plate=previous.copy();zones={}
    for spot,entry in REGIONS.items():
        fix=r.polygon(entry['polygon']);assert np.all(support[fix])
        x0,y0,x1,y1=entry['crop_box'];assert not field[y0:y1,x0:x1].any()
        assert not fix[:y0].any() and not fix[y1:].any() and not fix[:,:x0].any() and not fix[:,x1:].any()
        accepted=decisions[spot]['passed'];zones[spot]=fix if accepted else np.zeros(field.shape,dtype=bool)
        if not accepted:continue
        fa=r.smooth(edt(fix)/entry['feather_inward_px'])
        patch=np.asarray(Image.open(IMG/f'concepts/EN-01-R3-{spot}-1-raw.png').convert('RGB').resize((x1-x0,y1-y0),Image.Resampling.LANCZOS))
        a=fa[y0:y1,x0:x1,None]
        plate[y0:y1,x0:x1]=np.rint(plate[y0:y1,x0:x1]*(1-a)+patch*a).astype('uint8')
        spec['r3_fix_regions'].append(dict(entry,spot=spot,generation=f'R3-{spot}-1',pedestal_cap_excluded=True,columns_excluded=True,run='CX-07r fix2'))
        Image.fromarray(np.uint8(np.rint(fa*255))).save(COMP/f'fix2-{spot}-fix-mask.png')
    plate[field]=128
    Image.fromarray(plate).save(IMG/'marmoreal-clean.png')
    spec['r3_glow']['composite_formula']='max(min(glow, remove/255), core * (remove>0)); zero on field and beyond radius'
    spec['fix2_se_inspection']=decisions['se']
    save_json(PKG/'_tools/mask-spec.json',spec)
    core_alpha=np.zeros(field.shape);core_region=np.zeros(field.shape,dtype=bool);core_polys=np.zeros(field.shape,dtype=bool)
    for entry in spec['r3_cores'].values():
        binary=r.polygon(entry['polygon']);core_polys|=binary;dist=edt(~binary)
        core_region|=dist<=entry['dilation_px']
        core_alpha=np.maximum(core_alpha,1-r.smooth(np.maximum(dist-entry['dilation_px'],0)/entry['soft_edge_px']))
    lc=r.lab(base);lp=r.lab(plate)
    g=np.clip(np.maximum((np.maximum(lc[...,0]-lp[...,0],0)-3)/20,(np.maximum(lc[...,2]-lp[...,2],0)-4)/25),0,1)
    yy,xx=np.indices(field.shape);glow=np.zeros(field.shape);radius_union=np.zeros(field.shape,dtype=bool)
    for name,x,y in SPOTS:
        R=130 if name.startswith('door') else 260;rr=np.hypot(xx-x,yy-y)
        window=1-r.smooth((rr-.6*R)/(.4*R));radius_union|=rr<=R
        blurred=gaussian_filter(g*window,sigma=3);blurred[rr>R]=0;glow=np.maximum(glow,blurred)
    glow[glow<8/255]=0
    m=np.rint(np.maximum(np.minimum(glow,remove/255),core_alpha*(remove>0))*255).astype('uint8')
    m[field|~radius_union]=0
    Image.fromarray(m).save(IMG/'marmoreal-lantern-mask.png')
    overlay_alpha=m[...,None].astype(float)/255
    lit=np.rint(plate*(1-overlay_alpha)+base*overlay_alpha).astype('uint8')
    Image.fromarray(lit).save(COMP/'r3-lit-full.png')
    frame=np.asarray(Image.open(COMP/'painted-frame-protection.png'))>0
    before=r.seam_cells(previous,base,support,field,frame);after=r.seam_cells(plate,base,support,field,frame)
    changed=np.any(plate!=previous,axis=2);union=np.logical_or.reduce(list(zones.values()))
    v=r.measure(plate,base,lit,m,core_polys,core_region,radius_union,support,field,before,after,changed,union,np.zeros(field.shape,dtype=bool))
    v['run']='CX-07r fix2'
    v['changes_vs_previous_plate']={'reference':'fix1 plate; comparison/fix2-before-clean.png','total':int(changed.sum()),**{spot:int((changed&zones.get(spot,np.zeros(field.shape,dtype=bool))).sum()) for spot in ['nw','ne','se']},'elsewhere':int((changed&~union).sum()),'SW_unchanged':bool(np.array_equal(plate[r.polygon(spec['r3_fix_regions'][0]['polygon'])],previous[r.polygon(spec['r3_fix_regions'][0]['polygon'])]))}
    mm=v['lantern_mask'];mm.pop('constraint_conflict',None)
    mm.update(core_polygons_all_255=bool(np.all(m[core_polys&support]==255)),dilated_cores_all_255=bool(np.all(m[core_region&support]==255)),core_clipped_pixels=int(np.count_nonzero(core_region&support&(m!=255))),core_pixels_outside_support=int(np.count_nonzero(core_region&~support)),core_condition='255 only where remove>0; outside support m=0 and clean=C0')
    per_core=[]
    for name,entry in spec['r3_cores'].items():
        poly=r.polygon(entry['polygon']);dilated=edt(~poly)<=2
        per_core.append({'spot':name,'polygon_pixels':int(poly.sum()),'polygon_pixels_in_support':int((poly&support).sum()),'polygon_pixels_below_255_in_support':int((poly&support&(m!=255)).sum()),'dilated_pixels_below_255_in_support':int((dilated&support&(m!=255)).sum()),'lit_pixels_different_from_C0':int((dilated&np.any(lit!=base,axis=2)).sum())})
    mm['per_core']=per_core
    # Exclude pairs touching the exact 2.5 px core soft edge. This also excludes
    # the support boundary immediately next to a core, as amended by fix2.
    exclusion=edt(~core_region)<=2.5;steps=[]
    for axis in [0,1]:
        s=np.abs(np.diff(m.astype(int),axis=axis))
        allowed=(~exclusion[:-1]&~exclusion[1:]) if axis==0 else (~exclusion[:,:-1]&~exclusion[:,1:])
        steps.append(int(s[allowed].max(initial=0)))
    mm['max_4_neighbour_step_outside_core_edges']=max(steps)
    mm['step_core_exclusion']='pairs touching dilated cores or their 2.5 px Euclidean soft edge; includes support boundary immediately next to a core'
    v['lit_check']['cores_equal_C0_exactly']=bool(np.array_equal(lit[core_region],base[core_region]))
    v['lit_check']['polygon_cores_equal_C0_exactly']=bool(np.array_equal(lit[core_polys],base[core_polys]))
    v['lit_check']['core_condition']='checked inside and outside support, including 2 px dilation'
    v['edit_review']=decisions
    save_json(PKG/'verification.json',v)
    Image.fromarray(changed.astype('uint8')*255).save(COMP/'r3-diff-vs-previous.png')
    outside=np.any(plate!=base,axis=2)&(remove==0)
    Image.fromarray(outside.astype('uint8')*255).save(COMP/'08-diff-outside-remove-mask.png')
    r.make_sheets(base,previous,plate,lit,m,before,after)
    # Preserve accepted seam-cell layouts, showing fix1/fix2 even though fix1
    # already has no non-exempt failures.
    images=[Image.fromarray(a) for a in [base,previous,plate]]
    for row in spec['r3_seam']['widened_cells']:
        x,y=row['x'],row['y'];box=(x-16,y-16,x+48,y+48)
        ims=[im.crop(box).resize((192,192),Image.Resampling.NEAREST) for im in images]
        for mono in [False,True]:sheet(f'r3-seam-cell-{x}-{y}',ims,['C0','fix1','fix2; 3x nearest'],cols=3,mono=mono)
    ims=[];labels=[]
    for name,x,y in SPOTS:
        for a,title in [(base,'C0'),(previous,'fix1'),(plate,'fix2')]:
            # PIL crop retains black padding for the two top-edge sconces.
            im=Image.fromarray(a).crop((x-60,y-60,x+60,y+60))
            boosted=Image.fromarray(np.uint8(np.clip(np.rint(np.asarray(im).astype(float)*2.5),0,255)))
            ims.append(boosted.resize((480,480),Image.Resampling.LANCZOS));labels.append(f'{name} {title}; brightness x2.5 4x')
    for mono in [False,True]:sheet('r3-K2-six-4x-boost',ims,labels,cols=3,mono=mono)
    old=Image.open(COMP/'fix2-before-lantern-mask.png').convert('RGB');new=Image.fromarray(m).convert('RGB')
    overlay=Image.fromarray(np.uint8(base*.6+np.stack([m,np.zeros_like(m),m],axis=-1)*.4))
    for mono in [False,True]:sheet('r3-lantern-mask',[old,new,overlay],['fix1 mask','fix2 mask','fix2 alpha over C0'],cols=3,mono=mono)
    ims=[];labels=[]
    for name,x,y in SPOTS:
        for a,title in [(base,'C0'),(plate,'fix2')]:
            ims.append(Image.fromarray(a).crop((x-60,y-60,x+60,y+60)).resize((480,480),Image.Resampling.LANCZOS));labels.append(f'{name} {title}; source 120x120 4x')
    for mono in [False,True]:sheet('r3-inspection-cores',ims,labels,cols=2,mono=mono)
    fix_alpha=np.zeros(field.shape)
    for entry in spec['r3_fix_regions']:fix_alpha=np.maximum(fix_alpha,r.smooth(edt(r.polygon(entry['polygon']))/entry['feather_inward_px']))
    Image.fromarray(np.uint8(np.rint(fix_alpha*255))).save(COMP/'r3-fix-mask.png')
    print(json.dumps({'changes':v['changes_vs_previous_plate'],'R4':{k:x for k,x in after.items() if k!='cells'},'mask':mm,'lit':v['lit_check']},ensure_ascii=True))

def verify():
    b=json.loads(BASELINE.read_text(encoding='utf-8'));v=json.loads((PKG/'verification.json').read_text(encoding='utf-8'))
    frozen={p:{'before':b['files'][p],'after':{'sha256':digest(ROOT/p),'bytes':(ROOT/p).stat().st_size},'unchanged':digest(ROOT/p)==b['files'][p]['sha256'] and (ROOT/p).stat().st_size==b['files'][p]['bytes']} for p in b['frozen']}
    v['frozen_unchanged']=frozen;v['source_unchanged']=all(frozen[p]['unchanged'] for p in b['sources'])
    records=json.loads((PKG/'generation-records.json').read_text(encoding='utf-8'));old_records=b['generation_records_before']['generations']
    v['generations']=records;v['generation_records_append_only']=records['generations'][:len(old_records)]==old_records
    v['generation_hash_checks']=[{'variant':x['variant'],'raw':digest(ROOT/x['raw_file'])==x['raw_sha256'],'input':digest(ROOT/x['input'])==x['input_sha256'],'prompt':digest(ROOT/x['prompt_file'])==x['prompt_sha256']} for x in records['generations']]
    new_records=records['generations'][len(old_records):]
    v['budget']={'original':4,'original_used':4,'rework':4,'rework_used':records['rework_generations'],'fix2':3,'fix2_used':len(new_records),'SYNTX':0,'one_edit_per_spot_no_retry':len({x['variant'] for x in new_records})==len(new_records)}
    v['tool_cache_outside_repo']=list(dict.fromkeys(x['tool_managed_source'] for x in records['generations'][4:]))
    v['tool_source_readback']=[{'variant':x['variant'],'source_byte_identical_to_raw':digest(Path(x['tool_managed_source']))==x['raw_sha256']} for x in records['generations'][4:]]
    plate=r.rgb(IMG/'marmoreal-clean.png');base=r.rgb(SOURCE);old=r.rgb(COMP/'fix2-before-clean.png')
    m=np.asarray(Image.open(IMG/'marmoreal-lantern-mask.png'));remove=np.asarray(Image.open(IMG/'marmoreal-remove-mask.png'));field=np.asarray(Image.open(IMG/'marmoreal-field-mask.png'))>0;support=(remove>0)&~field
    spec=json.loads((PKG/'_tools/mask-spec.json').read_text(encoding='utf-8'))
    core=np.zeros(field.shape,dtype=bool)
    for entry in spec['r3_cores'].values():core|=edt(~r.polygon(entry['polygon']))<=entry['dilation_px']
    alpha=m[...,None].astype(float)/255;lit=np.rint(plate*(1-alpha)+base*alpha).astype('uint8')
    union=np.zeros(field.shape,dtype=bool)
    for entry in spec['r3_fix_regions'][len(b['mask_spec_before']['r3_fix_regions']):]:union|=r.polygon(entry['polygon'])
    frame=np.asarray(Image.open(COMP/'painted-frame-protection.png'))>0
    prefix=(PKG/'README.md').read_bytes()[:b['readme_before']['bytes']]
    package_bytes=sum(p.stat().st_size for p in PKG.rglob('*') if p.is_file())
    checks={
        'fixed_task_hashes_match':digest(SOURCE)=='8f098ef2980162a9fa48fdec6865618388e5e0486c73b71247dff5fccc72e662' and digest(IMG/'marmoreal-field-mask.png')=='d3fe2452fe262b1a1392bd4954ac87d2fb3de454cd9dbf82dfdddcda2a82e2ca' and digest(IMG/'marmoreal-remove-mask.png')=='dc5d41e26228dd665c39fa63078ed54bb47440ee276758abba140cc84cf12099',
        'plate_RGB_1672x941':Image.open(IMG/'marmoreal-clean.png').mode=='RGB' and Image.open(IMG/'marmoreal-clean.png').size==r.SIZE,
        'mask_L_1672x941':Image.open(IMG/'marmoreal-lantern-mask.png').mode=='L' and Image.open(IMG/'marmoreal-lantern-mask.png').size==r.SIZE,
        'field_all_808080':bool(np.all(plate[field]==128)),
        'outside_remove_zero':bool(np.array_equal(plate[remove==0],base[remove==0])),
        'elsewhere_unchanged':bool(np.array_equal(plate[~union],old[~union])),
        'SW_unchanged':bool(np.array_equal(plate[r.polygon(spec['r3_fix_regions'][0]['polygon'])],old[r.polygon(spec['r3_fix_regions'][0]['polygon'])])),
        'SE_unchanged':bool(np.array_equal(plate[445:565,1460:1580],old[445:565,1460:1580])),
        'fixes_inside_support':bool(np.all(support[union])),
        'SW_fix_region_unchanged':spec['r3_fix_regions'][0]==b['mask_spec_before']['r3_fix_regions'][0],
        'seam_feather_unchanged':spec['r3_seam']==b['mask_spec_before']['r3_seam'],
        'core_polygons_unchanged':spec['r3_cores']==b['mask_spec_before']['r3_cores'],
        'painted_frame_unchanged':bool(np.array_equal(plate[frame],base[frame])),
        'door_interior_unchanged':bool(np.array_equal(plate[:99,803:867],base[:99,803:867])),
        'cores_255_inside_support':bool(np.all(m[core&support]==255)),
        'lit_cores_equal_C0_inside_and_outside_support':bool(np.array_equal(lit[core],base[core])),
        'lit_sheet_matches_formula':bool(np.array_equal(lit,r.rgb(COMP/'r3-lit-full.png'))),
        'glow_capped_outside_core_soft_edges':bool(np.all(m[edt(~core)>2.5]<=remove[edt(~core)>2.5])),
        'mask_zero_outside_support':bool(np.all(m[~support]==0)),
        'outside_diff_black':bool(np.all(np.asarray(Image.open(COMP/'08-diff-outside-remove-mask.png'))==0)),
        'old_mask_backup_byte_identical':digest(COMP/'fix2-before-lantern-mask.png')==b['files'][rel(IMG/'marmoreal-lantern-mask.png')]['sha256'],
        'old_plate_backup_byte_identical':digest(COMP/'fix2-before-clean.png')==b['files'][rel(IMG/'marmoreal-clean.png')]['sha256'],
        'README_original_bytes_unchanged':hashlib.sha256(prefix).hexdigest()==b['readme_before']['sha256'],
        'history_verification_byte_identical':digest(PKG/'history/verification-fix1.json')==b['files'][rel(PKG/'verification.json')]['sha256'],
        'history_manifest_byte_identical':digest(PKG/'history/manifest-sha256-fix1.json')==b['files'][rel(PKG/'manifest-sha256.json')]['sha256'],
        'generations_intact':all(all(x[k] for k in ['raw','input','prompt']) for x in v['generation_hash_checks']),
        'generation_budget':len(new_records)<=3 and records['rework_generations']<=4 and v['budget']['one_edit_per_spot_no_retry'],
        'package_under_5_MB':package_bytes<=5_000_000,
    }
    gray_checks={}
    for path in COMP.glob('r3-*-gray.png'):
        src=path.with_name(path.name.replace('-gray.png','-colour.png'))
        if src.exists():gray_checks[rel(path)]=bool(np.array_equal(np.asarray(gray(Image.open(src).convert('RGB'))),r.rgb(path)))
    gray_checks[rel(COMP/'r3-lit-full-gray.png')]=bool(np.array_equal(np.asarray(gray(Image.fromarray(lit))),r.rgb(COMP/'r3-lit-full-gray.png')))
    checks['Rec709_gray_sheets']=all(gray_checks.values())
    checks['R4_readback']=r.seam_cells(plate,base,support,field,frame)==v['R4']['after']
    repro_path=PKG/'_tools/reproducibility-fix2.json'
    repro=json.loads(repro_path.read_text(encoding='utf-8')) if repro_path.exists() else {}
    checks['reproducible_current_script']=repro.get('passed',False) and repro.get('script_sha256')==digest(PKG/'_tools/rework_fix2.py') and all(x['identical'] and digest(ROOT/p)==x['after'] for p,x in repro.get('files',{}).items())
    v['reproducibility']=repro
    v['independent_readback']={'checks':checks,'gray_checks':gray_checks,'package_bytes':package_bytes,'passed':all(checks.values())}
    paths=sorted(set(COMP.glob('r3-*.png'))|set(COMP.glob('fix2-*.png'))|set((IMG/'concepts').glob('EN-01-R3-*.png'))|{IMG/'marmoreal-clean.png',IMG/'marmoreal-lantern-mask.png',COMP/'08-diff-outside-remove-mask.png'})
    v['exports']={rel(p):{'size':list(Image.open(p).size),'mode':Image.open(p).mode,'sha256':digest(p)} for p in paths}
    v['gray']=[rel(p) for p in paths if 'gray' in p.name];v['sizes']={'plate':list(r.SIZE),'mask':list(r.SIZE),'working':[[1087,612],[836,471]],'K2_source':[120,120]}
    review_path=PKG/'_tools/visual-review-fix2.json'
    review=json.loads(review_path.read_text(encoding='utf-8')) if review_path.exists() else {}
    v['visual_review']=review
    inspected=review.get('inspected_images',{})
    required=set(COMP.glob('r3-*.png'))|{COMP/'08-diff-outside-remove-mask.png'}
    review_current=all(inspected.get(rel(path))==digest(path) for path in required)
    v['visual_review_current']=review_current
    card=next(row for row in csv.DictReader((ROOT/'docs/game-design/visual/06-tasks/env.csv').open(encoding='utf-8-sig')) if 'EN-01' in row.values())
    lines=re.findall(r'(?<!\S)[1-6]\).*?(?= [1-6]\)|$)',card['acceptance']);assert len(lines)==6
    mask=v['lantern_mask'];accept=[]
    def row(i,passed,measured,expected,note=''):accept.append({'line':lines[i-1],'passed':bool(passed),'measured':measured,'expected':expected,'note':note})
    row(1,v['source_unchanged'] and all(x['unchanged'] for x in frozen.values()) and all(checks.values()) and v['generation_records_append_only'],{'source_unchanged':v['source_unchanged'],'frozen_unchanged':all(x['unchanged'] for x in frozen.values()),'outside_folder':[],'outside_diff':v['changed_pixels_outside_remove_mask'],'elsewhere':v['changes_vs_previous_plate']['elsewhere']},'sources and frozen byte-identical; outside and elsewhere 0; all readbacks pass')
    row(2,review_current and review.get('silhouettes_removed',False) and review.get('pedestals_intact',False) and review.get('no_new_objects_water_figures_text',False) and v['field_all_808080'],review,'no silhouette at normal and x2.5 brightness 4x; intact pedestals; field #808080; warm residual outside support retained')
    row(3,all(x['passed'] for key in ['R1','R2','R3'] for x in v[key]) and v['R4']['after']['passed'] and review_current and review.get('K2_no_visible_boundary',False),{'R1':v['R1'],'R2':v['R2'],'R3':v['R3'],'R4_share':v['R4']['after']['s_le_4_share'],'R4_non_exempt_failures':len(v['R4']['after']['non_exempt_failures'])},'R1 spot<=ring+4; R2=0; R3<=1%; R4>=95%, all non-exempt<=4; no visible K2 boundary')
    row(4,review_current and review.get('gray_readable',False),review.get('gray_notes','pending inspection'),'pedestals, balustrades and colonnade readable on Rec.709 gray')
    mask_pass=mask['dilated_cores_all_255'] and mask['zero_outside_remove_support'] and mask['zero_on_field'] and mask['zero_beyond_radius'] and mask['share_ge_128']<=.1 and mask['max_4_neighbour_step_outside_core_edges']<=48
    lit_pass=v['lit_check']['cores_equal_C0_exactly'] and all(x['passed'] for x in v['lit_check']['per_light']) and review.get('lit_no_double_edges',False)
    row(5,mask_pass and lit_pass and review_current,{'mask':mask,'lit_check':v['lit_check'],'no_double_edges':review.get('lit_no_double_edges',False)},'cores 255 where remove>0; lit=C0 on all cores; zeros outside support/field/radius; >=128<=10%; noncore step<=48; mean dE76<=8 per light; no double edges',mask['step_core_exclusion'])
    row(6,True,{'agent_written_roots':[rel(PKG),rel(IMG)],'git_commands':0},'writes only within two authorized roots','User and corrective task prohibit every git command, so git status was not run. Images are in the explicitly authorized derived root; tool-managed CODEX_HOME cache is listed separately, never edited or deleted.')
    v['acceptance']=accept;v['acceptance_pass']=all(x['passed'] for x in accept)
    v['limits']=[{k:x[k] for k in ['line','measured','expected','note']} for x in accept if not x['passed']]
    v['outside_folder']=[]
    save_json(PKG/'verification.json',v)
    print(json.dumps({'source_unchanged':v['source_unchanged'],'frozen_unchanged':all(x['unchanged'] for x in frozen.values()),'readback':checks,'review_current':review_current,'acceptance':[x['passed'] for x in accept],'package_bytes':package_bytes},ensure_ascii=True))

def manifest():
    files=sorted(p for root in [PKG,IMG] for p in root.rglob('*') if p.is_file() and p!=PKG/'manifest-sha256.json')
    save_json(PKG/'manifest-sha256.json',{'schema':'en01.manifest/2','run':'CX-07r fix2','files':{rel(p):{'sha256':digest(p),'bytes':p.stat().st_size} for p in files}})
    print({'manifest_files':len(files)})

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('command',choices=['prepare','record','build','verify','manifest']);p.add_argument('--spot');p.add_argument('--source');a=p.parse_args()
    if a.command=='prepare':prepare()
    elif a.command=='record':record(a.spot,a.source)
    else:globals()[a.command]()
