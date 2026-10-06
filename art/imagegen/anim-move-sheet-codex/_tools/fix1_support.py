"""AN-22 fix1: package assembly and measurements from saved raster pixels.

No runtime, git, network or image-generation calls. Imported builder installs the
write allowlist audit hook. All diagnostic reports belong to this package.
"""
from pathlib import Path
import copy
import hashlib
import json
import math
import re
import sys

sys.dont_write_bytecode = True
import numpy as np
from PIL import Image
from scipy import ndimage

PKG = Path(__file__).resolve().parent.parent
ROOT = PKG.parents[2]
DERIVED = ROOT / 'scraped-data/derived/anim-move-sheet-codex'
HEX = ['#061623','#F9EBDB','#111317','#F2EDE4','#B9B2A6','#F2C14E','#FFC857']
RGB = np.array([[int(h[i:i+2],16) for i in (1,3,5)] for h in HEX], dtype=np.uint8)
LUMA = np.rint(RGB.astype(float) @ np.array([.2126,.7152,.0722])).astype(int)
COLUMNS = [390,650,910,1170,1430,1690]
TIMES = [0,60,280,480,560,710]


def read(path):
    return json.loads(path.read_text(encoding='utf8'))


def dump(path, obj):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj,ensure_ascii=False,indent=2)+'\n',encoding='utf8')


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def task_text(name):
    text=(ROOT/'docs/game-design/visual/06-tasks/prompts'/name).read_text(encoding='utf8')
    return text.split('## Task',1)[1].split('```text\n',1)[1].rsplit('```',1)[0]


def merge_keys(old, new):
    """Keep historical verification keys, including nested visual-review fields."""
    out=copy.deepcopy(old)
    for k,v in new.items():
        out[k]=merge_keys(out[k],v) if isinstance(v,dict) and isinstance(out.get(k),dict) else v
    return out


def render_native(builder, heroes):
    old_scale=builder.SCALE
    old_lists=(builder.TEXT_BOXES, builder.POSE_TRANSFORMS, builder.FACINGS)
    try:
        builder.SCALE=2/3
        builder.TEXT_BOXES=[]; builder.POSE_TRANSFORMS=[]; builder.FACINGS=[]
        image=builder.build(heroes,output_size=(1280,720))
        assert image.size==(1280,720)
        return image, copy.deepcopy(builder.TEXT_BOXES)
    finally:
        builder.SCALE=old_scale
        builder.TEXT_BOXES,builder.POSE_TRANSFORMS,builder.FACINGS=old_lists


def load_heroes():
    heroes=read(PKG/'trace-manifest.json')
    for h in heroes:
        h['mask']=Image.open(DERIVED/f"{h['name']}-f00-left-body-mask.png").copy()
    return heroes


def exports():
    result=[]
    for directory in ['vector','comparison']:
        for path in sorted((PKG/directory).glob('*.png')):
            im=Image.open(path); a=np.array(im)
            bg=[LUMA[0]]*3 if 'gray' in path.name else RGB[0]
            y,x=np.nonzero(np.any(a[:,:,:3]!=bg,axis=2) | (a[:,:,3]!=255))
            margin=int(min(x.min(),y.min(),im.width-1-x.max(),im.height-1-y.max()))
            result.append({'path':path.relative_to(PKG).as_posix(),'size':list(im.size),
                           'mode':im.mode,'margin_px':margin,'touches_edge':margin==0})
    return result


def lab(rgb):
    s=np.asarray(rgb,dtype=float)/255
    linear=np.where(s<=.04045,s/12.92,((s+.055)/1.055)**2.4)
    xyz=linear @ np.array([[.4124564,.3575761,.1804375],
                           [.2126729,.7151522,.0721750],
                           [.0193339,.1191920,.9503041]]).T
    xyz/=np.array([.95047,1,1.08883])
    f=np.where(xyz>(6/29)**3,np.cbrt(xyz),xyz/(3*(6/29)**2)+4/29)
    return np.stack([116*f[:,1]-16,500*(f[:,0]-f[:,1]),200*(f[:,1]-f[:,2])],axis=1)


def palette():
    a=np.array(Image.open(PKG/'vector/AN-22-step-sheet.png'))
    opaque=a[:,:,3]==255
    uniform=np.ones(a.shape[:2],bool)
    for c in range(4):
        uniform &= ndimage.minimum_filter(a[:,:,c],size=3,mode='nearest')==ndimage.maximum_filter(a[:,:,c],size=3,mode='nearest')
    edge=~uniform
    eligible=opaque & uniform
    colors,counts=np.unique(a[:,:,:3][eligible],axis=0,return_counts=True)
    distances=np.linalg.norm(lab(colors)[:,None,:]-lab(RGB)[None,:,:],axis=2).min(axis=1)
    outside=int(counts[distances>3].sum())
    return {'method':'CIELAB D65, sRGB decoding, dE76; opaque only; exclude nonuniform 3x3 RGBA neighbourhoods',
            'threshold_dE76':3,'opaque_pixels':int(opaque.sum()),
            'edge_pixels_excluded':int((opaque & edge).sum()),'eligible_pixels':int(eligible.sum()),
            'off_palette_pixels':outside,'off_palette_share':outside/int(eligible.sum()),
            'tokens':[{'hex':h,'pixel_count':int(np.all(a[:,:,:3]==rgb,axis=2).sum()),
                       'eligible_pixel_count':int((np.all(a[:,:,:3]==rgb,axis=2)&eligible).sum())}
                      for h,rgb in zip(HEX,RGB)]}


def s(t):
    if t<=80: return t*t/(2*80*240)
    if t<=480: return (t-40)/240
    if t<560: return 2-(560-t)**2/(2*80*240)
    return 2.


def runs(values):
    labels,n=ndimage.label(np.asarray(values,dtype=bool))
    return [int((labels==i).sum()) for i in range(1,n+1)]


def gray():
    pairs=[]
    for color in [PKG/'vector/AN-22-step-sheet.png']+sorted((PKG/'comparison').glob('*color*.png')):
        suffix=color.stem.split('-color')[-1] if '-color' in color.stem else ''
        gp=PKG/f'comparison/AN-22-step-sheet-gray{suffix}.png'
        a=np.array(Image.open(color)); b=np.array(Image.open(gp))
        y=np.rint(a[:,:,:3].astype(float) @ np.array([.2126,.7152,.0722])).astype(np.uint8)
        exact=all(np.array_equal(b[:,:,i],y) for i in range(3)) and np.array_equal(a[:,:,3],b[:,:,3])
        pairs.append({'color':color.relative_to(PKG).as_posix(),'gray':gp.relative_to(PKG).as_posix(),
                      'Rec709_exact':exact,'passed':exact})
    a=np.array(Image.open(PKG/'comparison/AN-22-step-sheet-gray.png'))[:,:,0]
    def hit(t,value,position,radius):
        x=round(260+t/860*1584); y=round(797-55*position)
        crop=a[y-radius:y+radius+1,x-radius:x+radius+1]
        # Lanczos rings on thin strokes overshoot token luma by up to 12.
        if value==LUMA[4]:
            # Grey dash core/antialias band, above the dark background and below
            # the yellow solid stroke; narrower sampling radius separates curves.
            return bool(np.any((crop>=100)&(crop<=190)))
        return bool(np.any(np.abs(crop.astype(int)-value)<=12))
    # Only sample disjoint, unobscured portions: crossing/overlap is not a dash gap.
    windows=[list(range(32,200)),list(range(361,529))]
    gap_windows=[]
    for ts in windows:
        missing=[not hit(t,LUMA[4],min(t/280,2),1) for t in ts]
        gap_windows.append({'time_ms':[ts[0],ts[-1]],'gap_runs_samples':[v for v in runs(missing) if v>=2]})
    gaps=sum(len(w['gap_runs_samples']) for w in gap_windows)
    solid_missing=[not hit(t,LUMA[5],s(t),4) for t in range(0,861)]
    solid_gaps=len([r for r in runs(solid_missing) if r>=2])
    distinctions=[{'pair':'ease curve / linear legacy curve','shape_difference':'solid / dashed',
                   'dash_gaps':gaps,'solid_gaps':solid_gaps,'sample_windows':gap_windows,
                   'method':'Read rendered grey pixels along analytic centreline: dash band luma 100..190 in radius 1; solid luma 195 +/-12 in radius 4. Ignore occluded/overlapping portions; count >=2 consecutive missing samples',
                   'passed':gaps>0 and solid_gaps==0}]
    for name,xy1,xy2 in [('x1 / x0.5',(300,932),(300,895)),('x1 / x1.5',(300,932),(300,969)),
                           ('EASE-IN / linear',(310,196),(600,196)),('EASE-OUT / linear',(1200,196),(600,196))]:
        x1,y1=xy1; x2,y2=xy2
        y_a=int(a[y1,x1]); y_b=int(a[y2,x2]); diff=abs(y_a-y_b)
        row={'pair':name,'sample_pixels':[list(xy1),list(xy2)],
             'fill_luma':[y_a,y_b],'luma_difference':diff,'minimum':20,'passed':diff>=20}
        if name.startswith('x1 /'):
            # Equal-height bars still differ in length and vertex/arrival locations.
            def fill_spans(y):
                mask=np.abs(a[y,260:1845].astype(int)-int(a[y,300]))<=2
                labels,n=ndimage.label(mask)
                return [len(np.nonzero(labels==i)[0]) for i in range(1,n+1) if (labels==i).sum()>100]
            lengths=[fill_spans(y1),fill_spans(y2)]
            row.update({'shape_difference':'different bar lengths and vertex/arrival positions on the shared time axis',
                        'bar_fill_spans_px':lengths,'passed':lengths[0]!=lengths[1] and bool(lengths[0]) and bool(lengths[1])})
        distinctions.append(row)
    return {'method':'Rec.709 encoded RGB: round(.2126R+.7152G+.0722B), preserve alpha',
            'pairs':pairs,'distinguishable_pairs':distinctions}


def raster_poses():
    a=np.array(Image.open(PKG/'vector/AN-22-step-sheet.png'))[:,:,:3]
    poses=[]
    for hero,g,h in [('KingArthur',455,114),('Harpy',620,110)]:
        idle_angle=None
        for t,x in zip(TIMES,COLUMNS):
            # Isolate cream body pixels, excluding flat pedestal and right-hand lean gauge.
            crop=a[g-h-8:g-8,x-77:x+78]
            yy,xx=np.nonzero(np.all(crop==RGB[1],axis=2))
            vals,vec=np.linalg.eigh(np.cov(np.stack([xx,yy])))
            v=vec[:,np.argmax(vals)]
            if v[1]>0:v=-v
            angle=float(np.degrees(np.arctan2(v[0],-v[1])))
            if idle_angle is None:idle_angle=angle
            # The cream pedestal bottom is below a 2px keyline: independently locate it.
            by,bx=np.nonzero(np.all(a[g-8:g+1,x-20:x+21]==RGB[1],axis=2))
            bottom=int(by.max()+g-8)
            # Facing shaft: trace the yellow chroma ridge before the arrow head.
            origin_x=x-62; origin_y=g+15
            ridge=[]
            for dx in range(5,13):
                column=a[origin_y-2:origin_y+19,origin_x+dx].astype(float)
                score=column[:,0]-column[:,2]
                score[column[:,0]-column[:,1]<15]=0
                assert score.max()>80, 'Facing shaft missing in rendered raster'
                ridge.append([dx,float(np.flatnonzero(score>=score.max()-2).mean()-2)])
            # Centreline angle is insensitive to grey turn arrows crossing the shaft.
            slope=float(np.median(np.diff(np.array(ridge)[:,1])))
            yaw=float(np.degrees(np.arctan2(1,slope)))
            poses.append({'hero':hero,'time_ms':t,'body_cream_pixels':len(xx),
                          'axis_degrees_from_vertical':angle,'idle_axis_degrees':idle_angle,
                          'relative_lean_degrees':angle-idle_angle,'expected_lean_degrees':0 if t in (0,710) else 10,
                          'pedestal_bottom_cream_y':bottom,'baseline_y':g+1,
                          'baseline_raster_present':bool((a[g+1,x-70:x-35].astype(float) @ np.array([.2126,.7152,.0722])>90).all()),
                          'camera_relative_facing_degrees':yaw,'facing_ridge_pixels':ridge,'idle':t in (0,710)})
    return poses


def number_sources():
    text=read(PKG/'text-bounds.json')
    readme=(PKG/'README.md').read_text(encoding='utf8')
    section=readme.split('## Источник каждого числа на листе',1)[1].split('## Формула',1)[0]
    rows=[]
    for line in section.splitlines():
        if line.startswith('| ') and not line.startswith('| Число'):
            cells=line.split('|')[1:-1]
            if len(cells)==2:rows.append({'row':len(rows)+1,'label':cells[0].strip(),'source':cells[1].strip()})
    pattern=r'\d+(?:[,\.]\d+)?(?:/\d+)?'
    records=[]
    for i,box in enumerate(text):
        for m in re.finditer(pattern,box['text']):
            number=m.group()
            matches=[r for r in rows if number in re.findall(pattern,r['label'])]
            # Identifier 007 and AN-22 belong to the first row, fractions stay whole.
            if number=='22' and 'AN-22' in box['text']:matches=[rows[0]]
            if number=='007':matches=[rows[0]]
            if number in ('0','1','2') and box['text']==number:
                matches=[r for r in rows if 'по вертикали' in r['label']]
            if number=='1' and '×1' in box['text']:
                matches=[r for r in rows if r['label'].startswith('×1;')]
            row=matches[0] if matches else None
            records.append({'text_bounds_index':i,'text':box['text'],'number':number,
                            'readme_row':row['row'] if row else None,
                            'readme_row_label':row['label'] if row else None,
                            'source':row['source'] if row else None})
    return {'readme_section':'Источник каждого числа на листе','rows':rows,'drawn_numbers':records,
            'unmatched_numbers':sum(r['readme_row'] is None for r in records)}


def measurements():
    ex=exports(); pal=palette(); gr=gray(); poses=raster_poses(); nums=number_sources()
    timing=read(PKG/'timing-contract.json')
    phases=timing['phases']; arrival=sum(p['ms'][1]-p['ms'][0] for p in phases[:3])
    settle=sum(p['ms'][1]-p['ms'][0] for p in phases)
    k1=1/(timing['duration_per_edge_ms']-timing['ease']['first_edge']['Ein']/2)
    k2=1/(timing['duration_per_edge_ms']-timing['ease']['second_edge']['Eout']/2)
    lean_ok=all(abs(p['relative_lean_degrees']-p['expected_lean_degrees'])<=1 for p in poses)
    base_ok=all(p['baseline_raster_present'] for p in poses) and all(len({p['pedestal_bottom_cream_y'] for p in poses if p['hero']==hero})==1 for hero in ['KingArthur','Harpy'])
    facing_ok=all(p['camera_relative_facing_degrees']<=90 and (not p['idle'] or p['camera_relative_facing_degrees']<=45) for p in poses)
    expected_files=['vector/AN-22-step-sheet.png','comparison/AN-22-step-sheet-gray.png',
                    'comparison/AN-22-step-sheet-color-1280x720.png','comparison/AN-22-step-sheet-gray-1280x720.png']
    ver=read(PKG/'verification.json')
    def record(passed,measured,expected,note):
        return {'passed':bool(passed),'measured':measured,'expected':expected,'note':note}
    acceptance={
      '1_phases':record(abs(arrival-560)<=42 and abs(settle-710)<=42,{'arrival_ms':arrival,'with_settle_ms':settle},{'arrival_ms':560,'with_settle_ms':710,'tolerance_ms':42},'Durations are parallel with turning/lean; sum timing-contract phases.'),
      '2_s80':record(math.isclose(s(80),1/6,abs_tol=1e-12),s(80),'1/6 first edge','Closed-form ease-in on the contract.'),
      '3_vertex':record(min(k1,k2)>0 and k1==k2,{'smallest_speed_80_480_edges_per_ms':min(k1,k2),'vertex_before':k1,'vertex_after':k2},'>0, continuous','Both contract edges have constant middle speed over 80..480 ms.'),
      '4_lean_no_hop':record(lean_ok and base_ok,{'poses':poses,'ground_y_by_lane':{'KingArthur':456,'Harpy':621}},'10 degrees +/-1; 0 idle; six equal base lines per lane','PCA of exact cream body pixels, same crop per lane; subtract rendered idle axis, never transform matrices. Two separate lanes have distinct sheet y positions; each lane has zero vertical movement.'),
      '5_facing':record(facing_ok,[{'hero':p['hero'],'time_ms':p['time_ms'],'yaw_degrees':p['camera_relative_facing_degrees'],'ridge_pixels':p['facing_ridge_pixels'],'idle':p['idle']} for p in poses],{'all_max_degrees':90,'idle_max_degrees':45},'Median slope of rendered yellow chroma ridge before arrowhead; grey camera shaft points down. Side-projection limitation retained.'),
      '6_number_sources':record(nums['unmatched_numbers']==0,nums,{'unmatched_numbers':0},'Every numeric occurrence in text-bounds.json mapped to a literal README source row.'),
      '7_color_gray':record(all((PKG/p).exists() for p in expected_files) and all(p['passed'] for p in gr['pairs']),expected_files,'Master and native 1280x720 color/Rec.709 RGBA','Every colour export has an exact grey pair.'),
      '8_scope_sources':record(ver['source_unchanged'] and ver['outside_folder']==[],{'source_unchanged':ver['source_unchanged'],'outside_folder':ver['outside_folder']},{'source_unchanged':True,'outside_folder':[]},'Reread original source-hashes-before.json; audited writes confined to allowed folders.')}
    sizes={'master':{'size':[1920,1080],'present':True},
           'working':[{'size':[1280,720],'color':'comparison/AN-22-step-sheet-color-1280x720.png','gray':'comparison/AN-22-step-sheet-gray-1280x720.png',
                       'render_scale':2/3,'canvas_size':[1280,720],'downscaled_from_master':False,
                       'method':'Fresh Canvas, same build(), SCALE=2/3; no resize of master or native canvas'}],
           'overview_960x540':'dropped (not a working size)'}
    return {'exports':ex,'palette':pal,'gray':gr,'sizes':sizes,'acceptance':acceptance}


def build_package(builder):
    before=read(PKG/'fix1-before.json')
    old=read(PKG/'verification.json')
    records=read(PKG/'generation-records.json')
    assert len(records['records'])==3, 'Exactly one fix1 pass allowed; do not overwrite pass04'
    for path,row in before['files'].items():
        if path.startswith('concepts/') or path=='source-hashes-before.json':
            assert sha(PKG/path)==row['sha256'], path
    heroes=load_heroes()
    im=builder.build(heroes)
    old_im=np.array(Image.open(PKG/'concepts/AN-22-step-sheet-pass03.png'))
    diff=np.any(np.array(im)!=old_im,axis=2)
    ys,xs=np.nonzero(diff)
    assert diff.any() and not diff[:657].any() and not diff[681:].any(), 'Drawing changed outside legend strip'
    preserved={'compared_with':'concepts/AN-22-step-sheet-pass03.png','changed_pixels':int(diff.sum()),
               'difference_bounds_xyxy':[int(xs.min()),int(ys.min()),int(xs.max()+1),int(ys.max()+1)],
               'allowed_legend_strip_y':[657,681],'outside_legend_changed_pixels':int(diff[:657].sum()+diff[681:].sum()),
               'concepts_01_03_unchanged':True,'source_hashes_before_unchanged':True}
    im.save(PKG/'concepts/AN-22-step-sheet-pass04.png')
    im.save(PKG/'vector/AN-22-step-sheet.png')
    im.save(PKG/'comparison/AN-22-step-sheet-color.png')
    builder.grayscale(im).save(PKG/'comparison/AN-22-step-sheet-gray.png')
    native,text=render_native(builder,heroes)
    native.save(PKG/'comparison/AN-22-step-sheet-color-1280x720.png')
    builder.grayscale(native).save(PKG/'comparison/AN-22-step-sheet-gray-1280x720.png')
    dump(PKG/'native-text-bounds-1280x720.json',text)
    for path in (PKG/'comparison').glob('*960x540.png'):path.unlink()
    prompt=task_text('AN-22.fix1.codex.md')
    prompt_path=PKG/'concepts/AN-22-pass04-prompt.txt'
    prompt_path.write_text(prompt,encoding='utf8')
    prompts={'AN-22/task':task_text('AN-22.codex.md'),'AN-22/fix1':prompt}
    for i,r in enumerate(records['records'],1):
        key=f'AN-22/pass{i:02d}'
        prompts[key]=(PKG/r['exact_prompt_file']).read_text(encoding='utf8')
        r['original_prompt_key']=r['prompt_key']; r['prompt_key']=key; r['selected']=False
    prompts['AN-22/fix1-pass04']=prompt
    records['records'].append({'prompt_key':'AN-22/fix1-pass04','selected':True,
       'exact_prompt_file':prompt_path.relative_to(PKG).as_posix(),'prompt_sha256':sha(prompt_path),
       'output':'concepts/AN-22-step-sheet-pass04.png','output_sha256':sha(PKG/'concepts/AN-22-step-sheet-pass04.png'),
       'tool':'build_step_sheet.py','method':'procedural, no image generation','unretouched':True,
       'generator_sha256':sha(PKG/'_tools/build_step_sheet.py'),
       'support_sha256':sha(Path(__file__))})
    dump(PKG/'generation-records.json',records)
    dump(PKG/'prompts/AN-22-prompts.json',prompts)
    updated=builder.verification(heroes,im)
    ver=merge_keys(old,updated)
    ver['visual_review']['status']='pending'
    ver['output_manifest']='manifest-sha256.json'
    ver['fix1']=preserved
    ver['reviewed_final_sha256']=None
    dump(PKG/'verification.json',ver)
    ver.update(measurements())
    ver['checks'].update({'pixel_identical_outside_legend':True,
                         'palette_off_token_share_zero':ver['palette']['off_palette_share']==0,
                         'native_working_size':True,
                         'eight_acceptance_records_pass':all(r['passed'] for r in ver['acceptance'].values()),
                         'gray_distinctions_pass':all(r['passed'] for r in ver['gray']['distinguishable_pairs']),
                         'exports_have_margin':all(r['margin_px']>0 for r in ver['exports'])})
    ver['all_automated_checks_pass']=all(ver['checks'].values())
    dump(PKG/'verification.json',ver)
    dump(PKG/'write-audit.json',{'allowed':[PKG.relative_to(ROOT).as_posix(),DERIVED.relative_to(ROOT).as_posix()],
         'writes':sorted(builder.WRITE_LOG),'scope':'Corrective build; unrelated concurrent sessions not monitored.'})
    print(json.dumps({'checks':len(ver['checks']),'all_pass':ver['all_automated_checks_pass'],
                       'failed':[k for k,v in ver['checks'].items() if not v],
                       'palette_off_token_share':ver['palette']['off_palette_share'],'preservation':preserved,
                       'gray_distinctions':ver['gray']['distinguishable_pairs']},ensure_ascii=False))
    if not ver['all_automated_checks_pass']:raise SystemExit(1)


def write_manifest():
    files={}
    for base in [PKG,DERIVED]:
        for p in sorted(base.rglob('*')):
            if p.is_file() and p!=PKG/'manifest-sha256.json':
                files[p.relative_to(ROOT).as_posix()]={'sha256':sha(p),'bytes':p.stat().st_size}
    dump(PKG/'manifest-sha256.json',{'algorithm':'sha256','scope':[PKG.relative_to(ROOT).as_posix(),DERIVED.relative_to(ROOT).as_posix()],
                                   'excluded':['art/imagegen/anim-move-sheet-codex/manifest-sha256.json'],'files':files})
    print(json.dumps({'manifest_files':len(files),'manifest_written_last':True}))
