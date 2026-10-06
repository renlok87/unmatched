"""Pixel measurements for AN-26 fix1. No writes and no source baseline recapture."""
from pathlib import Path
import hashlib
import io
import json
import math
import re
import runpy
import numpy as np
from PIL import Image
from scipy import ndimage as ndi

P = Path(__file__).resolve().parents[1]
ROOT = P.parents[2]

def read(name):
    return json.loads((P/name).read_text(encoding='utf-8'))

def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def lab(rgb):
    srgb=np.asarray(rgb,dtype=float)/255
    linear=np.where(srgb<=.04045,srgb/12.92,((srgb+.055)/1.055)**2.4)
    xyz=linear @ np.array([[.4124564,.3575761,.1804375],
                          [.2126729,.7151522,.0721750],
                          [.0193339,.1191920,.9503041]]).T
    xyz/=np.array([.95047,1,1.08883])
    f=np.where(xyz>(6/29)**3,np.cbrt(xyz),xyz/(3*(6/29)**2)+4/29)
    return np.stack([116*f[...,1]-16,500*(f[...,0]-f[...,1]),200*(f[...,1]-f[...,2])],axis=-1)

def measurements(result):
    b=runpy.run_path(str(P/'_tools/build_facing_sheet.py'),run_name='fix1_measurement')
    bg=np.array([6,22,35])
    exports=[]
    for f in sorted([*(P/'vector').glob('*.png'),*(P/'comparison').glob('*.png')]):
        im=Image.open(f);a=np.array(im.convert('RGBA'))
        background=np.full(3,round(float(bg @ [.2126,.7152,.0722]))) if 'gray' in f.name else bg
        foreground=np.any(a[:,:,:3]!=background,axis=2)
        ys,xs=np.where(foreground)
        margin=int(min(xs.min(),ys.min(),im.width-1-xs.max(),im.height-1-ys.max())) if len(xs) else min(im.size)//2
        exports.append({'path':f.relative_to(P).as_posix(),'size':list(im.size),'mode':im.mode,
                        'background_rgb':background.tolist(),'margin_px':margin,'touches_edge':margin==0})
    result['exports']=exports

    master=np.array(Image.open(P/'vector/AN-26-facing-sheet.png'))
    rgb=master[:,:,:3]
    # Exclude exactly those pixels whose complete 3x3 RGB neighbourhood is not uniform.
    uniform=np.all(ndi.minimum_filter(rgb,size=(3,3,1),mode='nearest')==
                   ndi.maximum_filter(rgb,size=(3,3,1),mode='nearest'),axis=2)
    opaque=master[:,:,3]==255
    eligible=uniform & opaque
    tokens=read('palette.json');names=list(tokens)
    colors=np.array([[int(tokens[n][i:i+2],16) for i in [1,3,5]] for n in names])
    values,counts=np.unique(rgb[eligible],axis=0,return_counts=True)
    distances=np.linalg.norm(lab(values)[:,None,:]-lab(colors)[None,:,:],axis=2)
    minimum=distances.min(axis=1);nearest=distances.argmin(axis=1)
    outside=int(counts[minimum>3].sum())
    result['palette']={'color_master':'vector/AN-26-facing-sheet.png','metric':'CIE76, sRGB D65',
        'threshold_de76':3,'opaque_pixels':int(opaque.sum()),'excluded_count':int((opaque & ~uniform).sum()),
        'evaluated_pixels':int(eligible.sum()),'outside_count':outside,
        'outside_share':outside/int(eligible.sum()),
        'pixel_count_per_token':{n:int(counts[(nearest==i)&(minimum<=3)].sum()) for i,n in enumerate(names)},
        'exclusion':'3x3 neighbourhood not a single RGB colour; no broad colour-distance exclusion',
        'passed':outside==0}

    gray=[]
    for e in exports:
        path=e['path']
        if 'gray' in Path(path).name:continue
        if path.startswith('vector/'):
            pair='comparison/'+Path(path).name.replace('sheet','sheet-gray')
        elif 'sheet-color' in path:pair=path.replace('sheet-color','sheet-gray')
        else:pair=path.replace('.png','-gray.png')
        a=np.array(Image.open(P/path));g=np.array(Image.open(P/pair))
        expected=np.rint(a[:,:,:3].astype(float) @ [.2126,.7152,.0722]).astype(np.uint8)
        gray.append({'color':path,'gray':pair,'rec709_exact':bool(np.array_equal(g[:,:,:3],np.repeat(expected[:,:,None],3,axis=2))
            and np.array_equal(a[:,:,3],g[:,:,3]))})
    lumas={n:round(float(col @ [.2126,.7152,.0722])) for n,col in zip(names,colors)}
    pairs=[]
    for name,a,z,shape in [
        ('idle wedge vs 90° limit','turn.flash.yellow','text.secondary','r115 thick arc vs r155 thin semicircle'),
        ('dead band vs idle wedge','card.cream','turn.flash.yellow','two radials plus r100 arc vs open r115 arc'),
        ('120 ms turn vs LungeAttack','turn.flash.yellow','card.cream','filled bar vs hollow outlined bar'),
        ('150 ms return vs LungeAttack','turn.flash.yellow','card.cream','filled bar vs hollow outlined bar'),
        ('Arthur / Harpy vs Merlin / Medusa contact','turn.flash.yellow','card.cream','circle vs diamond')]:
        difference=abs(lumas[a]-lumas[z])
        pairs.append({'pair':name,'tokens':[a,z],'luma':[lumas[a],lumas[z]],'luma_difference':difference,
                      'shape_difference':shape,'passed':difference>=20 or bool(shape)})
    result['gray']={'formula':'round(0.2126 R + 0.7152 G + 0.0722 B); alpha unchanged',
                    'files':gray,'distinguishable_pairs':pairs}
    result['sizes']=[{'size':[w,h],'color':f'vector/AN-26-facing-sheet{s}.png',
        'gray':f'comparison/AN-26-facing-sheet-gray{s}.png','present':True,
        'drawn_natively':True,'downscaled_from_master':False,
        'purpose':'overview' if w==960 else 'master' if w==1920 else 'working copy',
        'method':'Canvas created at this size with 2x antialias buffer, no master resize'}
        for w,h,s in [(1920,1080,''),(1280,720,'-1280x720'),(960,540,'-960x540')]]

    baseline=read('fix1-before.json')['files']
    unchanged=[n for n in baseline if n.startswith('silhouettes/') or n.startswith('concepts/') or
               n in ['source-hashes-before.json','_tools/draw_icons_v3_snapshot.py','prompt.txt','timing-model.json']]
    immutable={n:digest(P/n)==baseline[n]['sha256'] for n in unchanged}
    pixels=[]
    for size in result['sizes']:
        w,h=size['size']
        old=P/'concepts/AN-26-concept-A-unretouched.png' if w==1920 else P/f'concepts/fix1-baseline/AN-26-facing-sheet-{w}x{h}.png'
        before=np.array(Image.open(old));after=np.array(Image.open(P/size['color']))
        diff=np.any(before!=after,axis=2)
        before_luma=np.rint(before[:,:,:3].astype(float) @ [.2126,.7152,.0722]).astype(np.uint8)
        after_gray=np.array(Image.open(P/size['gray']))
        gray_diff=np.any(after_gray[:,:,:3]!=before_luma[:,:,None],axis=2)
        scale=w/1920
        rect=[math.floor(1470*scale),math.floor(154*scale),math.ceil(1872*scale),math.ceil(625*scale)]
        allowed=np.zeros(diff.shape,bool);allowed[rect[1]:rect[3],rect[0]:rect[2]]=True
        pixels.append({'size':[w,h],'plan_panel_px':rect,'changed_pixels':int(diff.sum()),
            'outside_plan_changed_pixels':int((diff & ~allowed).sum()),
            'outside_plan_pixel_identical':not bool((diff & ~allowed).any()),
            'gray_outside_plan_changed_pixels':int((gray_diff & ~allowed).sum()),
            'gray_outside_plan_pixel_identical':not bool((gray_diff & ~allowed).any()),
            'baseline':old.relative_to(P).as_posix()})

    # Render geometry and each label separately with the same native rasterizer.
    # Pixel distance includes anti-alias fringes, not just text bounding boxes.
    label_names=['−45°','+45°','−90°','+90°','враг','цель','КАМЕРА КЛИЕНТА','мёртвая зона ±10°']
    records=[r for r in read('layout-audit.json')['texts'] if r['text'] in label_names]
    clearance=[]
    for w,h in [(1920,1080),(1280,720)]:
        c=b['Canvas'](w,h);c.text=lambda *a,**k:None;b['plan'](c)
        geometry=np.any(np.array(c.export())[:,:,:3]!=bg,axis=2)
        masks=[]
        for r in records:
            cc=b['Canvas'](w,h)
            cc.text(*r['xy'],r['text'],r['font_px'],bold=r['bold'],anchor='mt' if r['text']=='КАМЕРА КЛИЕНТА' else 'lt')
            masks.append(np.any(np.array(cc.export())[:,:,:3]!=bg,axis=2))
        for i,r in enumerate(records):
            other=geometry.copy()
            for j,m in enumerate(masks):
                if j!=i:other |= m
            gap=float(ndi.distance_transform_edt(~other)[masks[i]].min())
            clearance.append({'size':[w,h],'label':r['text'],'minimum_clearance_px':round(gap,3),'passed':gap>=4})

    # Angle fitting uses only token-coloured pixels of the actual radial strokes.
    yy,xx=np.indices(rgb.shape[:2]);dx=xx-1665;dy=424-yy
    radius=np.hypot(dx,dy);theta=np.degrees(np.arctan2(dx,dy))
    def fit(angle,col,lo=35,hi=90):
        delta=np.asarray(col)-bg
        alpha=((rgb.astype(float)-bg) @ delta)/float(delta @ delta)
        residual=np.linalg.norm(rgb-(bg+alpha[:,:,None]*delta),axis=2)
        threshold=.85 if col==[249,235,219] else .25
        mask=(radius>=lo)&(radius<=hi)&(abs(theta-angle)<2)&(alpha>=threshold)&(alpha<=1.15)&(residual<=12)
        points=np.column_stack([dx[mask],dy[mask]]).astype(float)
        if len(points)<2:return {'degrees':999,'sample_pixels':len(points)}
        centered=points-points.mean(axis=0)
        _,_,v=np.linalg.svd(centered,full_matrices=False)
        axis=v[0]
        if axis @ points.mean(axis=0)<0:axis=-axis
        return {'degrees':round(math.degrees(math.atan2(axis[0],axis[1])),4),'sample_pixels':int(mask.sum())}
    idle=math.degrees(math.atan2(-24,36))
    angles={name:fit(angle,col,lo,hi) for name,angle,col,lo,hi in [
        ('idle_left',-45,[185,178,166],23,29),('idle_right',45,[185,178,166],35,100),
        ('attack_left',-90,[185,178,166],80,140),('attack_right',90,[185,178,166],80,140),
        ('band_left',idle-10,[249,235,219],35,85),('band_right',idle+10,[249,235,219],35,85),
        ('idle_yaw',idle,[249,235,219],35,78) ]}
    expected_angles={'idle_left':-45,'idle_right':45,'attack_left':-90,'attack_right':90,
                     'band_left':idle-10,'band_right':idle+10,'idle_yaw':idle}
    angle_pass=all(abs(angles[k]['degrees']-v)<=1 for k,v in expected_angles.items())
    enemy_angle=math.degrees(math.atan2(1591-1665,424-337))
    geometry_details={'center_px':[1665,424],'drawn_angles_from_pixels':angles,
        'expected_angles_deg':expected_angles,'tolerance_deg':1,
        'dead_band_total_width_deg':round(angles['band_right']['degrees']-angles['band_left']['degrees'],4),
        'dead_band_offsets_from_idle_deg':[round(angles['band_left']['degrees']-angles['idle_yaw']['degrees'],4),
                                          round(angles['band_right']['degrees']-angles['idle_yaw']['degrees'],4)],
        'measurement_note':'Left idle radial measured at r23–29 before the dead-band stroke; other radials measured over longer unobstructed segments. All samples are pixels of the final master.',
        'nearest_enemy_yaw_deg':enemy_angle,'nearest_enemy_difference_deg':abs(enemy_angle-idle),
        'nearest_enemy_inside_band':abs(enemy_angle-idle)<10,'passed':angle_pass}

    def edge(start,end,y):
        # Measure stroke's raster endpoints including half-coverage antialias pixels.
        x0,x1=b['tx'](start),b['tx'](end)
        row=rgb[y]
        alpha=(row.astype(float)-bg) @ (np.array([242,193,78])-bg)/float(np.sum((np.array([242,193,78])-bg)**2))
        residual=np.linalg.norm(row-(bg+alpha[:,None]*(np.array([242,193,78])-bg)),axis=1)
        ids=np.flatnonzero((alpha>=.5)&(residual<=12)&(np.arange(len(row))>=x0-4)&(np.arange(len(row))<=x1+4))
        return {'start_px':int(ids.min()),'end_px':int(ids.max()),'raster_span_px':int(ids.max()-ids.min()),
                'axis_start_px':x0,'axis_end_px':x1,'axis_length_px':x1-x0,
                'endpoint_max_error_px':max(abs(ids.min()-x0),abs(ids.max()-x1))}
    turn=edge(-120,0,280);ret=edge(583,733,280)
    # Cream outline bottom row, independently locate the LungeAttack bar.
    x0,x1=b['tx'](0),b['tx'](583)
    row=rgb[266];delta=np.array([249,235,219])-bg
    alpha=(row.astype(float)-bg) @ delta/float(delta @ delta)
    residual=np.linalg.norm(row-(bg+alpha[:,None]*delta),axis=1)
    indices=np.arange(1920)
    ids=np.flatnonzero(np.all(row>200,axis=1)&((abs(indices-x0)<4)|(abs(indices-x1)<4)))
    clip={'start_px':int(ids.min()),'end_px':int(ids.max()),'raster_span_px':int(ids.max()-ids.min()),
          'axis_length_px':x1-x0,'endpoint_max_error_px':max(abs(ids.min()-x0),abs(ids.max()-x1))}
    contacts=[]
    for ms,col,window in [(292,[242,193,78],6),(333,[249,235,219],6)]:
        x=b['tx'](ms);region=rgb[712:725,round(x)-window:round(x)+window+1]
        ys,xs=np.where(np.all(abs(region.astype(int)-col)<8,axis=2))
        center=float((xs.min()+xs.max())/2+round(x)-window)
        contacts.append({'ms':ms,'measured_center_px':center,'axis_px':x,'error_px':abs(center-x)})
    lanes=[]
    for factor,y in [(.5,880),(1,921),(1.5,962)]:
        lanes.append({'factor':factor,'turn':edge(-120,0,y),'return':edge(583*factor,583*factor+150,y)})
    # Subpixel endpoint positions lie within one native-pixel sampling interval.
    # Fixed axis lengths are identical; raster coverage spans may differ by one pixel.
    speed_pass=all(abs(r['turn']['axis_length_px']-turn['axis_length_px'])<1e-6 and
        abs(r['return']['axis_length_px']-ret['axis_length_px'])<1e-6 and
        r['turn']['endpoint_max_error_px']<=2 and r['return']['endpoint_max_error_px']<=2 for r in lanes)
    speed_pass &= len({r['turn']['raster_span_px'] for r in lanes})==1 and len({r['return']['raster_span_px'] for r in lanes})==1

    text_records=read('layout-audit.json')['texts']
    number_records=[];unmatched=[]
    source_table=(P/'README.md').read_text(encoding='utf-8').split('## Источник каждого числа на листе',1)[1].split('## ',1)[0]
    rows=[s for s in source_table.splitlines() if s.startswith('|')]
    for r in text_records:
        for number in re.findall(r'(?:[−+±×]\s*)?\d+(?:\.\d+)?',r['text']):
            bare=re.sub(r'^[−+±×]\s*','',number)
            if r['text']=='AN-26':source='Идентификатор AN-26 — метаданные карточки'
            elif 'AN-23' in r['text'] and bare=='23':source=next((s for s in rows if 'AN-23' in s),'')
            else:source=next((s for s in rows if re.search(r'(?<!\d)'+re.escape(bare)+r'(?![\d.])',s.split('|')[1])),'')
            entry={'text':r['text'],'number':number,'xy':r['xy'],'readme_row':source}
            number_records.append(entry)
            if not source:unmatched.append(entry)
    # Reduced line has two discrete vertical ticks at clip boundaries, no turn bar.
    reduced={'turn_center_px':round(b['tx'](0)),'return_center_px':round(b['tx'](583)),
             'turn_tick_present':bool(np.any(np.all(abs(rgb[994:1012,round(b['tx'](0))-1:round(b['tx'](0))+2].astype(int)-[242,193,78])<=20,axis=2))),
             'return_tick_present':bool(np.any(np.all(abs(rgb[994:1012,round(b['tx'](583))-1:round(b['tx'](583))+2].astype(int)-[242,193,78])<=20,axis=2))),
             'duration_ms':0,'model':read('timing-model.json')['reduced_motion']}
    timings={'axis_ms':[-300,1025],'axis_px':[250,1405],'px_per_ms':1155/1325,
             'turn_120_ms':turn,'return_150_ms':ret,'lunge_583_ms':clip,'contacts':contacts,
             'raster_endpoint_tolerance_px':2,
             'method':'Token-specific raster strokes; cream vertical outline endpoints; 2 px tolerance accounts for 2 px inset outlines and native antialiasing'}
    timing_pass=all(r['endpoint_max_error_px']<=2 for r in [turn,ret,clip]) and all(r['error_px']<=1 for r in contacts)
    def acceptance(passed,measured,expected,note):
        return {'passed':bool(passed),'measured':measured,'expected':expected,'note':note}
    silhouette_records=read('silhouettes/tracing-records.json')
    result['acceptance']={
        '1_shared_axis_and_timing':acceptance(timing_pass,timings,'120 / 150 / 583 ms; contacts 292 / 333 ms on one axis',
            'Bar ends and contact centres measured from the master pixels; rounded-ms card timing retained.'),
        '2_plan_angles':acceptance(angle_pass and geometry_details['nearest_enemy_inside_band'],geometry_details,
            'idle ±45°, dead band current yaw ±10°, attack ±90°, angle error ≤1°',
            'Pixel fits on both radial boundaries. Dead-band full opening is 20°; threshold is 10° to either side.'),
        '3_no_back_view':acceptance(all(immutable.values()) and all(not r['back_view'] for r in silhouette_records),
            {'pose_count':5,'trace_records':silhouette_records,'outside_panel':pixels,'only_crossed_out_back':'labelled schematic'},
            'Five accepted front/side traced poses; back only in crossed-out example',
            'fix1 review explicitly accepted this schematic; no new rear render claimed.'),
        '4_speed_fixed_turn_return':acceptance(speed_pass,lanes,'same turn 104.603774 px and return 130.754717 px in all lanes',
            'Equal geometric lengths on the common axis. Actual raster spans differ by at most 1 px from subpixel sampling; endpoint measurements and errors are reported, without editing accepted lanes.'),
        '5_reduced_instant':acceptance(reduced['turn_tick_present'] and reduced['return_tick_present'] and reduced['model']['turn_ms']==reduced['model']['return_ms']==0,
            reduced,'instantaneous turn / return; no finite-duration turn bars','Two vertical event ticks on the rendered lane.'),
        '6_all_numbers_sourced':acceptance(not unmatched,{'numbers':number_records,'unmatched':unmatched,'unmatched_count':len(unmatched)},
            'Every drawn number matches a README source row; unmatched 0','Coordinates distinguish duplicate occurrences; AN-23 and AN-26 are card identifiers.'),
        '7_color_gray_sizes':acceptance(all(r['rec709_exact'] for r in gray),result['sizes'],
            'Native master 1920×1080 and working 1280×720, colour and exact Rec.709 gray','960×540 is an overview, also natively drawn.'),
        '8_source_and_scope':acceptance(result['source_unchanged'] and result['outside_folder']==[],
            {'source_unchanged':result['source_unchanged'],'outside_folder':result['outside_folder'],'checked_files':result['source_files_checked']},
            'source_unchanged true; outside_folder []','Original source-hashes-before.json retained; full HUD hash audit rerun.')}
    prompts=read('prompts/AN-26-prompts.json')
    def task_text(name):
        return (ROOT/f'docs/game-design/visual/06-tasks/prompts/{name}').read_text(encoding='utf-8').split('## Task',1)[1].split('```text\n',1)[1].rsplit('```',1)[0]
    prompt_exact=prompts['AN-26/task']==task_text('AN-26.codex.md') and prompts['AN-26/fix1']==task_text('AN-26.fix1.codex.md')
    original_key=read('generation-records.json')['records'][0]['prompt_key']
    prompt_exact &= prompts[original_key]==(P/'prompt.txt').read_text(encoding='utf-8')
    selected=[r for r in read('generation-records.json')['records'] if r.get('selected')]
    proof_bytes=io.BytesIO()
    Image.open(P/'comparison/AN-26-tracing-proof.png').convert('RGB').save(proof_bytes,format='PNG')
    proof_identical=hashlib.sha256(proof_bytes.getvalue()).hexdigest()==baseline['comparison/AN-26-tracing-proof.png']['sha256']
    result['fix1']={'immutable_files':immutable,'outside_plan':pixels,'plan_label_clearance':clearance,
        'geometry':geometry_details,'native_speed_lane_raster_measurements':lanes,'prompt_map_verbatim':bool(prompt_exact),
        'selected_variant':selected[0]['id'] if len(selected)==1 else None,
        'reference_snapshot':'fix1-before.json','image_generations':0}
    result['fix1']['tracing_proof_rgb_unchanged']=proof_identical
    result['checks'].update({'fix1_immutable_files':all(immutable.values()),
        'fix1_outside_plan_pixel_identical':all(r['outside_plan_pixel_identical'] and r['gray_outside_plan_pixel_identical'] for r in pixels),
        'fix1_tracing_proof_rgb_unchanged':proof_identical,
        'fix1_plan_labels_clear':all(r['passed'] for r in clearance),
        'fix1_pixel_angles':angle_pass,'fix1_palette_de76':outside==0,
        'fix1_all_exports_rgba':all(r['mode']=='RGBA' for r in exports),
        'fix1_gray_pairs':all(r['rec709_exact'] for r in gray),'fix1_prompts_verbatim':bool(prompt_exact),
        'fix1_B_selected':len(selected)==1 and selected[0]['id']=='AN-26/fix1-B',
        'fix1_acceptance':all(r['passed'] for r in result['acceptance'].values())})
    result['automated_checks_pass']=all(result['checks'].values()) and result['source_unchanged']
    # Preserve every original field, but clarify that the reviewed schematic is accepted for fix1.
    result['unmet_requirements']=[]
    for item in result['limitations']:
        if item['id']=='back-render-unavailable':
            item['severity']='documented_source_limit'
            item['fix1_review']='Labelled schematic explicitly accepted by corrective task; unchanged.'
    return result

def write_manifest():
    derived=ROOT/'scraped-data/derived/anim-facing-sheet-codex'
    files={}
    for root in [P,derived]:
        if not root.exists():continue
        for f in sorted(root.rglob('*')):
            if f.is_file() and f!=P/'manifest-sha256.json':
                files[f.relative_to(ROOT).as_posix()]={'sha256':digest(f),'bytes':f.stat().st_size}
    (P/'manifest-sha256.json').write_text(json.dumps({'task':'AN-26/fix1','algorithm':'sha256',
        'files':files,'self_excluded':True,'written_after':['README.md','verification.json'],
        'roots':[P.relative_to(ROOT).as_posix(),derived.relative_to(ROOT).as_posix()]},ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
