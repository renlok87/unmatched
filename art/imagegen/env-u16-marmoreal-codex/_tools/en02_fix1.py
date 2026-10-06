"""CX-17 fix1: local tile inputs, immutable raw archive, composites and proof.
Run python -B; writes are restricted to PKG and IMG. No providers/git/Unreal.
"""
import argparse
import hashlib
import json
import shutil
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw
from scipy.ndimage import gaussian_filter1d

import en02 as base

ROOT, PKG, IMG = base.ROOT, base.PKG, base.IMG
BOX, SIZE = base.BOX, base.SIZE
read, write, sha, rel = base.read_json, base.write_json, base.sha, base.rel
TILES = {2: (0, 0, 1536, 1317), 3: (804, 0, 2340, 1317),
         4: (0, 0, 1536, 1317), 5: (804, 0, 2340, 1317)}


def stem(n):
    return f'EN-02-OUTPAINT-{n:02d}'


def make_input(n):
    box = TILES[n]
    source = IMG / 'concepts/EN-02-outpaint-input.png'
    if n in (3, 5):
        source = IMG / f'concepts/{stem(n-1)}-pasteback.png'
    image = Image.open(source).crop(box)
    dest = IMG / f'concepts/{stem(n)}-input.png'
    assert not dest.exists()
    image.save(dest)
    prompt = (PKG / 'prompts/EN-02-OUTPAINT-01.txt').read_text(encoding='utf-8')
    x0 = max(334-box[0], 0); x1 = min(2006-box[0], 1536)-1
    prompt = prompt.replace('EN-02-outpaint-input.png, 2340x1317', f'{stem(n)}-input.png, 1536x1317')
    prompt = prompt.replace('x=334..2005, y=188..1128 (1672x941)', f'x={x0}..{x1}, y=188..1128 (visible crop of 1672x941)')
    prompt = prompt.replace('2340x1317 with exact registration', '1536x1317 with exact registration')
    prompt = prompt.replace('Transparent pixels around that rectangle', 'Transparent pixels outside the fixed context')
    if n in (3, 5):
        prompt = prompt.replace('The unchanged original occupies', 'The unchanged original and previously painted left overlap are fixed context. The original occupies')
    p = PKG / f'prompts/{stem(n)}.txt'
    assert not p.exists()
    p.write_text(prompt, encoding='utf-8')
    print(prompt)


def archive(n, source):
    source = Path(source)
    dest = IMG / f'concepts/{stem(n)}-raw.png'
    assert not dest.exists()
    shutil.copyfile(source, dest)
    assert sha(source) == sha(dest)
    record = read(PKG / 'generation-records.json')
    data = record['EN-02']
    p = PKG / f'prompts/{stem(n)}.txt'; inp = IMG / f'concepts/{stem(n)}-input.png'
    raw_size = Image.open(dest).size
    entry = dict(prompt_key=stem(n), prompt_file=rel(p), prompt_sha256=sha(p),
                 submitted_prompt_sha256=sha(p), submitted_prompt_normalization='exact UTF-8 file text',
                 input=rel(inp), input_sha256=sha(inp), raw_file=rel(dest), raw_sha256=sha(dest),
                 raw_size=list(raw_size), tile_box=list(TILES[n]),
                 resample_factor=[1536/raw_size[0], 1317/raw_size[1]], retouched=False,
                 provider='built-in image_gen', tool_managed_source=str(source), run='CX-17 fix1')
    data['generations'].append(entry)
    data['attempted_generations'] = len(data['generations'])
    data['status'] = 'generation_in_progress'
    data['built_in_imagegen_called'] = True
    write(PKG / 'generation-records.json', record)
    print(json.dumps(entry))


def compose(n):
    box = TILES[n]; bx, by, ex, ey = box
    generated = Image.open(IMG / f'concepts/{stem(n)}-raw.png').convert('RGB').resize((ex-bx, ey-by), Image.Resampling.LANCZOS)
    original = Image.open(base.ORIGINAL).convert('RGB')
    original_canvas = Image.new('RGB', SIZE)
    original_canvas.paste(original, BOX[:2])
    yy, xx = np.indices((SIZE[1], SIZE[0]))
    inside = (xx >= BOX[0]) & (xx < BOX[2]) & (yy >= BOX[1]) & (yy < BOX[3])
    band = inside & ((xx < BOX[0]+32) | (xx >= BOX[2]-32) | (yy < BOX[1]+32) | (yy >= BOX[3]-32))
    known = np.asarray(original_canvas)[by:ey,bx:ex].astype(float)
    raw = np.asarray(generated).astype(float)
    registration = float(np.abs(raw-known)[band[by:ey,bx:ex]].mean())
    if n in (3,5):
        canvas = Image.open(IMG / f'concepts/{stem(n-1)}-pasteback.png').convert('RGBA')
        a = np.asarray(canvas).copy()
        weight = np.clip((np.arange(bx,ex)-bx)/ (1536-bx), 0,1)[None,:,None]
        old = a[by:ey,bx:ex,:3].astype(float)
        blended = np.rint(old*(1-weight)+raw*weight).astype('uint8')
        a[by:ey,bx:ex,:3] = blended
        a[by:ey,bx:ex,3] = 255
        canvas = Image.fromarray(a)
    else:
        canvas = Image.open(IMG / 'concepts/EN-02-outpaint-input.png').convert('RGBA')
        canvas.paste(generated.convert('RGBA'),(bx,by))
    canvas.paste(original.convert('RGBA'), BOX[:2])
    canvas.save(IMG / f'concepts/{stem(n)}-pasteback.png')
    record = read(PKG / 'generation-records.json')
    entry = next(e for e in record['EN-02']['generations'] if e['prompt_key']==stem(n))
    entry['registration_before_pasteback'] = dict(mean_absolute_RGB_32px_inside_border=registration,
        method='Lanczos resize to tile box; no translation/warp; union of 32px original border bands')
    entry['overlap_blend'] = dict(width_px=732, formula='linear feather left previous to right current; original pasted back') if n in (3,5) else None
    write(PKG / 'generation-records.json', record)
    print(json.dumps({'tile': n, 'registration_RGB_MAE': registration}))


def seam(image):
    y = base.linear_luma(image)*255
    x0,y0,x1,y1=BOX
    results={}
    for side in ('left','right','top','bottom'):
        rows=[]
        for d in range(-64,65):
            if side=='left': v=np.abs(y[y0:y1,x0-d]-y[y0:y1,x0-1-d])
            elif side=='right': v=np.abs(y[y0:y1,x1+d]-y[y0:y1,x1-1+d])
            elif side=='top': v=np.abs(y[y0-d,x0:x1]-y[y0-1-d,x0:x1])
            else: v=np.abs(y[y1+d,x0:x1]-y[y1-1+d,x0:x1])
            rows.append(v)
        rows=np.array(rows); g=rows.mean(axis=1)
        median=float(np.median(np.r_[g[:64],g[65:]]))
        segments=[]
        for start in range(0,rows.shape[1],64):
            gg=rows[:,start:start+64].mean(axis=1); med=float(np.median(np.r_[gg[:64],gg[65:]]))
            segments.append(dict(start_px=start,end_px=min(start+64,rows.shape[1]),G0=float(gg[64]),median=med,
                                 ratio=float(gg[64]/med) if med else None))
        results[side]=dict(G0=float(g[64]),median=median,ratio=float(g[64]/median) if median else None,
            passed=bool(g[64]<=1.5*median),profile_offsets=list(range(-64,65)),profile_G=g.tolist(),
            segments_64px=segments,segments_above_1_5=[s for s in segments if s['ratio'] is None or s['ratio']>1.5])
    return dict(definition='ВР-VS2-EN.7: linear Rec.709 Y*255; per-side mean perpendicular pair difference; d=0 old border; d<0 original; median 1<=|d|<=64',sides=results,passed=all(v['passed'] for v in results.values()))


def correct(n):
    """Low-frequency RGB correction only, 32px inside strip, sigma24, fade96."""
    image=Image.open(IMG / f'concepts/{stem(n)}-pasteback.png').convert('RGB')
    a=np.asarray(image).astype(float)
    # Recover generated values BEFORE paste-back for the correction measurement.
    previous=np.asarray(Image.open(IMG / f'concepts/{stem(n-1)}-raw.png').convert('RGB').resize((1536,1317),Image.Resampling.LANCZOS)).astype(float)
    current=np.asarray(Image.open(IMG / f'concepts/{stem(n)}-raw.png').convert('RGB').resize((1536,1317),Image.Resampling.LANCZOS)).astype(float)
    g=np.zeros_like(a);g[:,:1536]=previous
    w=np.clip((np.arange(804,2340)-804)/732,0,1)[None,:,None]
    g[:,804:]=g[:,804:]*(1-w)+current*w
    x0,y0,x1,y1=BOX
    differences={
        'left':(a[y0:y1,x0:x0+32]-g[y0:y1,x0:x0+32]).mean(axis=1),
        'right':(a[y0:y1,x1-32:x1]-g[y0:y1,x1-32:x1]).mean(axis=1),
        'top':(a[y0:y0+32,x0:x1]-g[y0:y0+32,x0:x1]).mean(axis=0),
        'bottom':(a[y1-32:y1,x0:x1]-g[y1-32:y1,x0:x1]).mean(axis=0)}
    yy,xx=np.indices(a.shape[:2]); delta=np.zeros_like(a); total=np.zeros(a.shape[:2])
    for side, diff in differences.items():
        diff=gaussian_filter1d(diff,24,axis=0,mode='nearest')
        if side in ('left','right'):
            dist=x0-xx if side=='left' else xx-x1+1
            idx=np.clip(yy-y0,0,y1-y0-1)
        else:
            dist=y0-yy if side=='top' else yy-y1+1
            idx=np.clip(xx-x0,0,x1-x0-1)
        f=np.where(dist>0,np.clip(1-(dist-1)/96,0,1),0)
        delta+=diff[idx]*f[...,None]; total+=f
    a+=delta/np.maximum(total,1)[...,None]
    # Darken extension smoothly in linear light. 1 at old border, .85 at outer edge.
    dx=np.maximum(np.maximum((x0-xx)/334,(xx-(x1-1))/334),0)
    dy=np.maximum(np.maximum((y0-yy)/188,(yy-(y1-1))/188),0)
    t=np.clip(np.maximum(dx,dy),0,1); factor=1-.15*t*t*(3-2*t)
    s=np.clip(a/255,0,1); linear=np.where(s<=.04045,s/12.92,((s+.055)/1.055)**2.4)
    linear*=factor[...,None]; s=np.where(linear<=.0031308,12.92*linear,1.055*linear**(1/2.4)-.055)
    clean=Image.fromarray(np.clip(np.rint(s*255),0,255).astype('uint8'))
    clean.paste(Image.open(base.ORIGINAL).convert('RGB'),BOX[:2])
    clean.save(IMG / f'concepts/EN-02-attempt-{(n-1)//2}-clean.png')
    metrics=seam(clean);write(PKG/f'_tools/en02-fix1-attempt-{(n-1)//2}.json',metrics)
    print(json.dumps({k:{j:v[j] for j in ('G0','median','ratio','passed')} for k,v in metrics['sides'].items()}))


def artifact_metrics(clean):
    y=base.linear_luma(clean)*255; x0,y0,x1,y1=BOX
    mirror={}; streak={}; darkness={}
    for side,width in [('left',334),('right',334),('top',188),('bottom',188)]:
        values=[]
        for w in sorted(set([32,64,width])):
            if side=='left': ext=y[y0:y1,x0-w:x0]; orig=y[y0:y1,x0:x0+w][:,::-1]
            elif side=='right': ext=y[y0:y1,x1:x1+w]; orig=y[y0:y1,x1-w:x1][:,::-1]
            elif side=='top': ext=y[y0-w:y0,x0:x1]; orig=y[y0:y0+w,x0:x1][::-1]
            else: ext=y[y1:y1+w,x0:x1]; orig=y[y1-w:y1,x0:x1][::-1]
            aa=ext.ravel()-ext.mean();bb=orig.ravel()-orig.mean(); denom=np.linalg.norm(aa)*np.linalg.norm(bb)
            values.append(dict(width_px=w,ncc=float(aa@bb/denom) if denom else 0))
        mirror[side]=dict(samples=values,max=max(v['ncc'] for v in values),flag=any(v['ncc']>.8 for v in values))
        # ext above is the full-width band. Retain both ratios because card wording
        # says along/across while its edge-clamp example requires across/along.
        gx=float(np.abs(np.diff(ext,axis=1)).mean());gy=float(np.abs(np.diff(ext,axis=0)).mean())
        across,along=(gx,gy) if side in ('left','right') else (gy,gx)
        ratio=across/along if along else None
        streak[side]=dict(mean_abs_dYdx=gx,mean_abs_dYdy=gy,across_over_along=ratio,
            along_over_across=along/across if across else None,flag=ratio is None or ratio<.3)
        if side=='left': edge=y[y0:y1,:32];inner=y[y0:y1,x0:x0+32]
        elif side=='right':edge=y[y0:y1,-32:];inner=y[y0:y1,x1-32:x1]
        elif side=='top':edge=y[:32,x0:x1];inner=y[y0:y0+32,x0:x1]
        else:edge=y[-32:,x0:x1];inner=y[y1-32:y1,x0:x1]
        darkness[side]=dict(edge32_mean_Y=float(edge.mean()),original32_mean_Y=float(inner.mean()),edge_darker=bool(edge.mean()<inner.mean()))
    return mirror,streak,darkness


def sheets(clean,lit,metrics):
    base.save_pair('ext-master',[clean,lit],['clean-ext | 2340x1317','lit-ext | 2340x1317'])
    for size in ((1521,856),(1170,659)):
        base.save_pair(f'ext-working-{size[0]}x{size[1]}',[im.resize(size,Image.Resampling.LANCZOS) for im in (clean,lit)],['clean-ext','lit-ext'])
    frames=[]
    for im in (clean,lit):
        im=im.copy();d=ImageDraw.Draw(im)
        d.rectangle((0,0,2339,1316),outline='#00ffff',width=3)
        d.rectangle((334,188,2005,1128),outline='white',width=2);frames.append(im)
    base.save_pair('ext-framing',frames,['B = entire canvas | white = original','B = entire canvas | white = original'])
    base.save_pair('ext-K1x065',[im.resize((1672,941),Image.Resampling.LANCZOS) for im in frames],['K1 x0.65 framing per EN.6 | clean','K1 x0.65 framing per EN.6 | lit'])
    edges={'left':(0,0,398,1317),'right':(1942,0,2340,1317),'top':(0,0,2340,252),'bottom':(0,1065,2340,1317)}
    for side,box in edges.items():
        pieces=[im.crop(box) for im in (clean,lit)]
        base.save_pair('ext-edge-'+side,[im.resize((im.width*2,im.height*2),Image.Resampling.NEAREST) for im in pieces],['clean | '+side+' | 2x nearest','lit | '+side+' | 2x nearest'])
    y=base.linear_luma(clean)*255;gy,gx=np.gradient(y)
    heat=Image.fromarray(np.clip(np.rint(np.hypot(gx,gy)*4),0,255).astype('uint8')).convert('RGB')
    ImageDraw.Draw(heat).rectangle((334,188,2005,1128),outline='white',width=2)
    plots=Image.new('RGB',SIZE,'#181818');d=ImageDraw.Draw(plots)
    colors=['#f5d78a','#79bfe8','#c3a0dc','#91c797']
    for i,(side,data) in enumerate(metrics['sides'].items()):
        left=75+(i%2)*1170;top=65+(i//2)*640;pw=1010;ph=470
        maximum=max(max(data['profile_G']),data['median']*1.5)*1.12 or 1
        pts=[(left+j/128*pw,top+ph-g/maximum*ph) for j,g in enumerate(data['profile_G'])]
        d.line(pts,fill=colors[i],width=3)
        threshold=top+ph-data['median']*1.5/maximum*ph
        d.line((left,threshold,left+pw,threshold),fill='#888888',width=2)
        d.line((left+pw/2,top,left+pw/2,top+ph),fill='white',width=1)
        d.text((left,top-28),f'{side}: G(0)={data["G0"]:.3f}; median={data["median"]:.3f}; ratio={data["ratio"]:.3f}',fill='white')
        d.text((left,top+ph+12),'offset d: -64 (original) ... 0 ... +64 (extension); gray = 1.5 x median',fill='white')
    base.save_pair('ext-gradient',[heat,plots],['gradient magnitude x4 | old border white','G(d) profiles | EN.7'])
    a=np.asarray(clean);b=np.asarray(lit);changed=np.any(a!=b,axis=2)
    diff=np.rint(a*.3).astype('uint8');diff[changed]=b[changed]
    base.save_pair('ext-lit-diff',[Image.fromarray(diff)],['changed lit pixels over dimmed clean | lantern mask only'])


def finish(n):
    clean=Image.open(IMG/f'concepts/EN-02-attempt-{(n-1)//2}-clean.png').convert('RGB')
    clean.save(IMG/'marmoreal-clean-ext.png')
    a=np.asarray(Image.open(base.ORIGINAL).convert('RGB')).astype(float)
    c0=np.asarray(Image.open(base.C0).convert('RGB')).astype(float)
    mask=np.asarray(Image.open(base.MASK).convert('L'));m=mask/255
    restored=np.rint(a*(1-m[...,None])+c0*m[...,None]).astype('uint8')
    lit=clean.copy();lit.paste(Image.fromarray(restored),BOX[:2]);lit.save(IMG/'marmoreal-lit-ext.png')
    metrics=seam(clean);sheets(clean,lit,metrics)
    print('Final PNGs and 22 sheets written; inspect all before report.')


def report(n):
    clean=Image.open(IMG/'marmoreal-clean-ext.png');lit=Image.open(IMG/'marmoreal-lit-ext.png')
    a=np.asarray(clean);b=np.asarray(lit);crop=a[188:1129,334:2006];litcrop=b[188:1129,334:2006]
    original=np.asarray(Image.open(base.ORIGINAL).convert('RGB'));mask=np.asarray(Image.open(base.MASK).convert('L'))
    c0=np.asarray(Image.open(base.C0).convert('RGB'));field=np.asarray(Image.open(base.FIELD).convert('L'))>0
    expected=np.rint(original*(1-mask[...,None]/255)+c0*(mask[...,None]/255)).astype('uint8')
    shifted=np.zeros(a.shape[:2],dtype='uint8');shifted[188:1129,334:2006]=mask
    changed=np.any(a!=b,axis=2);outside=int(np.count_nonzero(changed&(shifted==0)))
    metrics=seam(clean);mirror,streak,darkness=artifact_metrics(clean)
    baseline=read(base.BASELINE);frozen={p:v for p,v in baseline['package_before'].items()
        if not (str(Path(p).parent.as_posix())==rel(PKG) and Path(p).name in {'README.md','verification.json','source-hashes-before.json','generation-records.json','manifest-sha256.json'})
        and p!=rel(PKG/'_tools/draw_icons_v3_snapshot.py')}
    sources_changed=[p for p,v in baseline['sources'].items() if not (ROOT/p).exists() or sha(ROOT/p)!=v['sha256']]
    frozen_changed=[p for p,v in frozen.items() if not (ROOT/p).exists() or sha(ROOT/p)!=v['sha256']]
    records=read(PKG/'generation-records.json');generations=records['EN-02']['generations'];cache=[];hash_checks=[]
    for e in generations:
        source=Path(e['tool_managed_source']);cache.append(dict(path=str(source),**base.file_info(source)))
        hash_checks.append(dict(prompt_key=e['prompt_key'],passed=all(sha(ROOT/e[p])==e[h] for p,h in [('input','input_sha256'),('raw_file','raw_sha256'),('prompt_file','prompt_sha256')]) and sha(source)==e['raw_sha256']))
    sheets_paths=sorted(p for p in (IMG/'comparison').glob('ext-*.png') if not p.name.startswith('ext-preparation'))
    exports_paths=[IMG/'marmoreal-clean-ext.png',IMG/'marmoreal-lit-ext.png']+sheets_paths
    exports_paths+=sorted(p for p in (IMG/'concepts').glob('EN-02-OUTPAINT-*.png'))
    exports_paths+=sorted(p for p in (IMG/'concepts').glob('EN-02-attempt-*.png'))
    def pixelsha(arr):return hashlib.sha256(arr.tobytes()).hexdigest()
    locality=dict(changed_outside_mask_positive=outside,core_m255_equal_C0=bool(np.array_equal(litcrop[mask==255],c0[mask==255])),lit_formula_exact=bool(np.array_equal(litcrop,expected)))
    fields=dict(clean=bool(np.all(crop[field]==128)),lit=bool(np.all(litcrop[field]==128)),pixels=int(field.sum()))
    review=read(PKG/'_tools/en02-fix1-visual-review.json')
    acceptance=[
        dict(passed=clean.size==lit.size==SIZE and clean.mode==lit.mode=='RGB' and np.array_equal(crop,original),measured=dict(size=list(clean.size),original_crop_sha256=pixelsha(crop)),expected='1) 2340x1317 RGB; clean original byte-identical EN-01',note='Lit crop follows EN.8; pixel-buffer SHA256 avoids PNG encoder differences.'),
        dict(passed=review['perspective_continuous'] and review['no_mirroring'] and review['no_streaks'] and review['edges_darker'] and not any(v['flag'] for v in mirror.values()) and not any(v['flag'] for v in streak.values()),measured=dict(mirror_max={k:v['max'] for k,v in mirror.items()},streak_across_over_along={k:v['across_over_along'] for k,v in streak.items()},darkness=darkness),expected='2) K1 x0.65 whole B per EN.6; no stretched streaks/mirrored architecture; darker edges',note=review['notes']),
        dict(passed=metrics['passed'],measured={k:v['ratio'] for k,v in metrics['sides'].items()},expected='3) Each side G(0) <= 1.5 x median G(d), 1<=abs(d)<=64, EN.7',note='64px segment flags are inspection only.'),
        dict(passed=outside==0 and locality['core_m255_equal_C0'] and locality['lit_formula_exact'],measured=locality,expected='4) Lit differs only within lantern mask; no second feather, EN.8',note='Round nearest uint8; original EN-01 mask used exactly.'),
        dict(passed=review['no_water'] and fields['clean'] and fields['lit'],measured=dict(no_water=review['no_water'],field=fields),expected='5) No water; field #808080',note='Haze is air/clouds; field mask checked every pixel.')]
    result=dict(task='EN-02',run='CX-17 fix1',status='предложено',created_utc=base.stamp(),
        source_unchanged=dict(checked=len(baseline['sources']),changed=sources_changed,passed=not sources_changed),
        en01_files_frozen=dict(checked=len(frozen),changed=frozen_changed,passed=not frozen_changed),
        outside_folder=[],tool_cache_outside_repo=cache,git_commands=0,MCP_calls=0,unreal_open_edit_build=0,persistent_processes_started=0,
        exports=[dict(path=rel(p),size=list(Image.open(p).size),mode=Image.open(p).mode) for p in exports_paths],
        palette='not applicable: plate colours come from the painting',gray=dict(method='sRGB decode -> linear Rec.709 Y -> sRGB encode',sheets=[rel(p) for p in sheets_paths if p.name.endswith('-gray.png')]),
        sizes=dict(canvas=list(SIZE),original_rect_xywh=[334,188,1672,941],working=[[1521,856],[1170,659]],K1x065=[1672,941]),
        generations_used=len(generations),generation_budget=6,generation_hash_checks=hash_checks,
        generation_records_append_only={k:v for k,v in records.items() if k!='EN-02'}==baseline['previous_generation_records'],
        original_crop_sha256=dict(algorithm='SHA256 raw decoded RGB bytes',EN01=pixelsha(original),clean_ext=pixelsha(crop),lit_ext=pixelsha(litcrop),lit_formula=pixelsha(expected),EN01_png=sha(base.ORIGINAL)),
        field_all_808080=fields,lit_locality=locality,seam=metrics,mirror_check=mirror,streak_check=streak,
        streak_ratio_note='Literal along/across also reported; across/along is used for edge-clamp flag <0.3 because edge clamp has zero normal derivative.',
        dark_edges=darkness,visual_review=review,acceptance=acceptance,
        acceptance_pass=all(row['passed'] for row in acceptance) and not sources_changed and not frozen_changed,
        method=dict(tiles=[list(TILES[i]) for i in range(n-1,n+1)],overlap_px=732,blend='linear feather outside original only; paste original after each pass',
                    colour_correction=dict(inside_band_px=32,sigma_px=24,outward_fade_px=96,extension_only=True),darkening=dict(linear_light=True,border_factor=1,outer_factor=.85,smoothstep=True)),
        limits=['Real game K1 camera is checked later in EN-03..EN-07, per EN.6; no Unreal read here.','Rect B C0 rounding gap: 0.4593 horizontal / 0.2295 vertical px, note only.'])
    write(PKG/'verification.json',result)
    immutables=read(PKG/'_tools/en02-fix1-input-hashes.json')
    result['run1_helpers_unchanged']={p:sha(PKG/p)==h for p,h in immutables.items()}
    result['run1_snapshots']={name:base.file_info(PKG/'history'/name) for name in ['verification-en02-run1.json','manifest-sha256-en02-run1.json']}
    result['source_unchanged']['pass']=result['source_unchanged']['passed']
    result['en01_files_frozen']['pass']=result['en01_files_frozen']['passed']
    result['outcome']='passed' if result['acceptance_pass'] else 'failed'
    result['failed_criteria']=[row['expected'] for row in acceptance if not row['passed']]
    result['complete_attempts']=2
    result['attempts']=[dict(attempt=i,seam_file=rel(PKG/f'_tools/en02-fix1-attempt-{i}.json'),
        seam_ratios={k:v['ratio'] for k,v in read(PKG/f'_tools/en02-fix1-attempt-{i}.json')['sides'].items()},passed=False) for i in (1,2)]
    result['stop_reason']='Two complete attempts failed seam/perspective criteria. No further generation per task; Claude owns T-SYNTX-IMG-BANANA fallback.'
    result['recommended_default_variant']='clean-ext after a successful replacement outpaint; current candidates not recommended for game'
    result['acceptance_pass']=result['acceptance_pass'] and all(result['run1_helpers_unchanged'].values()) and all(e['passed'] for e in hash_checks)
    write(PKG/'verification.json',result)
    records['EN-02']['status']='proposed' if result['acceptance_pass'] else 'failed_after_two_complete_attempts'
    records['EN-02']['selected_attempt']=(n-1)//2
    records['EN-02']['fix1_authorization']='ВР-VS2-EN.5: built-in tool cache copies allowed, read-only; MCP 0'
    records['EN-02']['complete_attempts']=result['attempts']
    records['EN-02']['stop_reason']=result['stop_reason']
    records['EN-02']['run1_fields_note']='provider_checks and built_in_excluded_reason retain run1 history; overridden by fix1 authorization.'
    write(PKG/'generation-records.json',records)
    print(json.dumps({'acceptance_pass':result['acceptance_pass'],'rows':[r['passed'] for r in acceptance],'sources_changed':sources_changed,'frozen_changed':frozen_changed}))


def readme():
    r=read(PKG/'verification.json'); old=(PKG/'history/en02-before-README.md').read_bytes()
    lines=['\n\n## EN-02 — расширение плиты (2026-10-06)\n',
        '**Статус: предложено. Итог CX-17 fix1: неуспех, приёмка не пройдена.** '
        'Две полные попытки не выдержали порог швов; после них генерации остановлены по заданию. '
        'Сохранён полный пакет результатов и измерений для ревью Claude и перехода к T-SYNTX-IMG-BANANA. '
        'Ни один текущий расширенный кандидат не рекомендуется для внедрения.\n',
        'Первый запуск был заблокирован до генерации: 0 из 6. Он подготовил холст и маску outpaint, '
        'промпт, baseline, историю, геометрию 334+1672+334 × 188+941+188 и paste-back. '
        'Его отчёты сохранены побайтно в [verification-en02-run1.json](history/verification-en02-run1.json) '
        'и [manifest-sha256-en02-run1.json](history/manifest-sha256-en02-run1.json). Старые материалы не удалялись.\n',
        '**Метод.** Встроенный image_gen, две попытки по два последовательных тайла 1536×1317: '
        '[0,0,1536,1317] и [804,0,2340,1317], перекрытие 732 px. Второй тайл каждой попытки получает '
        'неизменённый оригинал и уже созданный контекст первого. C0, карту и кадры игры генератор не получал. '
        'Сырые PNG — 1354×1161, возврат в тайл Lanczos ×1,13442 по X и ×1,13437 по Y. '
        'Сдвиг или геометрический warp не применялся; оригинал возвращён побайтно после каждого прохода. '
        'Перекрытие смешано линейной растушёвкой 732 px только снаружи оригинала.\n',
        'Разрешённая низкочастотная коррекция: средняя разность RGB «оригинал − генерация» '
        'в полосе 32 px внутри границы, Gaussian σ=24 px вдоль стороны, перенос наружу с линейным '
        'затуханием за 96 px. В углах вклады нормированы. Оригинал не меняется. '
        'Только достройка затемнена в линейном свете smoothstep: 1,0 у старой границы → 0,85 у внешнего края. '
        'Это не устранило скачки деталей и яркости; нижний край остаётся светлее исходной нижней полосы.\n',
        '**Применённые решения.** ВР-VS2-EN.5: служебные файлы CODEX_HOME перечислены в '
        '`tool_cache_outside_repo`, побайтно скопированы в concepts и не изменялись, не перемещались и не удалялись; '
        '`outside_folder=[]`. ВР-VS2-EN.6: B — весь холст, K1 ×0,65 — весь холст, уменьшенный Lanczos до '
        '1672×941 с обводкой оригинала; рамки 1/0,65 и ошибки «нехватки покрытия» нет. '
        'Разница округления C0 0,4593/0,2295 px — только примечание. '
        'ВР-VS2-EN.7: G(d) — средний перепад линейной Rec.709 Y (0–255) по стороне, '
        'порог G(0) ≤ 1,5 × median G(d), 1 ≤ |d| ≤ 64. '
        'ВР-VS2-EN.8: lit = clean_ext×(1−m)+C0×m, m=исходная маска/255, '
        'округление к ближайшему uint8; второй растушёвки нет.\n',
        '| Генерация | Тайловый контекст | MAE RGB в 32 px до paste-back |\n|---|---|---|']
    gens=read(PKG/'generation-records.json')['EN-02']['generations']
    for e in gens:
        lines.append(f'| {e["prompt_key"]} | {e["tile_box"]} | {e["registration_before_pasteback"]["mean_absolute_RGB_32px_inside_border"]:.5f} |')
    lines+=['\n| Сторона | G(0), попытка 1 | Медиана | Отношение | Попытка 2, отношение | Порог |\n|---|---:|---:|---:|---:|---:|']
    other=read(PKG/'_tools/en02-fix1-attempt-2.json')['sides']
    for side,v in r['seam']['sides'].items():
        lines.append(f'| {side} | {v["G0"]:.5f} | {v["median"]:.5f} | {v["ratio"]:.5f} | {other[side]["ratio"]:.5f} | ≤1,5 — не пройдено |')
    lines+=['\nДля итоговых имён и листов сохранена **попытка 1**: в попытке 2 дополнительно появились '
        'высокие вертикальные архитектурные детали над колоннадой. Это выбор диагностического кандидата, '
        'не художественная приёмка. Все профили G(-64…64), отношения 64-px сегментов и список сегментов '
        'выше 1,5 находятся в [verification.json](verification.json); сегменты служат только осмотру.\n',
        '| Сторона | Mirror NCC, максимум | Streak across/along |\n|---|---:|---:|']
    for side in ('left','right','top','bottom'):
        lines.append(f'| {side} | {r["mirror_check"][side]["max"]:.5f} | {r["streak_check"][side]["across_over_along"]:.5f} |')
    lines+=['\nMirror проверен для полос 32, 64 и полной ширины расширения с отражённой соседней '
        'полосой оригинала: максимум <0,8 на каждой стороне. Streak: обе производные и оба отношения '
        'есть в JSON. В формулировке задания «along/across» противоречит примеру edge-clamp: '
        'при edge-clamp поперечная производная равна нулю, поэтому для флага <0,3 использовано '
        'across/along; буквальное along/across тоже приведено. Все четыре отношения >0,3.\n',
        f'**Скриптовые инварианты пройдены.** RGB 2340×1317; SHA-256 RGB-байтов оригинала и clean-кропа '
        f'совпадает: `{r["original_crop_sha256"]["EN01"]}`. Lit-кроп точно равен формуле EN.8; '
        f'изменений вне m>0 — {r["lit_locality"]["changed_outside_mask_positive"]}; '
        f'в ядрах m=255 lit=C0 точно. Все {r["field_all_808080"]["pixels"]} пикселей поля '
        'в обоих финалах — #808080. SHA-256 lit-кропа и ожидаемой формулы приведены в verification.\n',
        '**Просмотр PNG.** Открыты все 22 листа ниже — цвет и Rec.709 gray, мастер, обе рабочие '
        'величины, B/K1, четыре края 2× nearest, градиент и lit-diff. Ночной рисунок, вишнёвые '
        'ветви и скала продолжаются; воды, диска луны, текста, фигур, зеркальной архитектуры '
        'и растянутых полос не видно. Но на всех размерах читается прямоугольная граница '
        'оригинала: разрыв неба справа сверху, несогласованные листья/ветви слева, скачок '
        'дымки и контура скалы снизу. Верхние детали колоннады не состыкованы достаточно '
        'точно, хотя общая перспектива и балюстрады внутри оригинала сохранены. '
        'Слева достроена отдельная скальная площадка — незапрошенное новое образование; '
        'утверждение «без новых ориентиров» не выполнено. Верх/лево/право темнее к краю, '
        'низ — нет. Lit-diff находится только внутри маски, фонари восстановлены без второй '
        'растушёвки. Эти наблюдения записаны в [_tools/en02-fix1-visual-review.json](_tools/en02-fix1-visual-review.json).\n',
        '| Лист | Цвет | Rec.709 gray |\n|---|---|---|']
    names=[('Мастер','ext-master'),('1521×856','ext-working-1521x856'),('1170×659','ext-working-1170x659'),('B и оригинал','ext-framing'),('K1 ×0,65','ext-K1x065')]+[(f'Край {side}, 2× nearest',f'ext-edge-{side}') for side in ('left','right','top','bottom')]+[('Градиент и G(d)','ext-gradient'),('Lit-diff','ext-lit-diff')]
    for label,name in names:
        prefix='../../../scraped-data/derived/env-u16-marmoreal-codex/comparison/'+name
        lines.append(f'| {label} | [цвет]({prefix}-colour.png) | [серый]({prefix}-gray.png) |')
    lines+=['\n**Рекомендация.** Для будущего игрового default — clean-ext после успешной замены outpaint: '
        'он сохраняет принятую чистую плиту EN-01 и оставляет фонари под управлением игровых накладок. '
        'Lit-ext нужен для сравнения с восстановленной живописной засветкой. Текущие '
        '[clean-ext](../../../scraped-data/derived/env-u16-marmoreal-codex/marmoreal-clean-ext.png) и '
        '[lit-ext](../../../scraped-data/derived/env-u16-marmoreal-codex/marmoreal-lit-ext.png) '
        'сохранены как не прошедшие приёмку кандидаты, не как готовый default.\n',
        '**Сохранность и бюджет.** 4 из 6 встроенных генераций (ключи 02…05; ключ 01 первого '
        'запуска не изменялся); две полные попытки. MCP, SYNTX, платные API/CLI — 0. Git — 0, '
        'чтение/изменение/сборка unreal/ — 0. Постоянных процессов не запускалось. '
        f'Baseline подтверждает неизменность {r["source_unchanged"]["checked"]} источников и '
        f'{r["en01_files_frozen"]["checked"]} замороженных файлов EN-01. '
        'Старые скрипты, en02-spec, baseline, маски, clean и история не правились. README '
        'начинается побайтно с EN-01 из history/en02-before-README.md. Сырые файлы равны '
        'служебным оригиналам инструмента; точные prompts/inputs/raw и хеши записаны в '
        '[generation-records.json](generation-records.json). '
        '[manifest-sha256.json](manifest-sha256.json) покрывает оба корня, исключая себя.\n',
        '**Что не выполнено.** Порог шва на всех четырёх сторонах обеих попыток, '
        'непрерывная перспектива через верхнюю границу, отсутствие новых образований и '
        'затемнение нижнего края. Условие двух неудач выполнено: дальше генератор не вызывается, '
        'Claude продолжает своим T-SYNTX-IMG-BANANA. Реальная камера K1 проверяется в EN-03…EN-07.\n',
        'Воспроизведение скриптовой сборки без новых генераций:\n\n```powershell\n'
        'python -B art/imagegen/env-u16-marmoreal-codex/_tools/en02_fix1.py compose 2\n'
        'python -B art/imagegen/env-u16-marmoreal-codex/_tools/en02_fix1.py compose 3\n'
        'python -B art/imagegen/env-u16-marmoreal-codex/_tools/en02_fix1.py correct 3\n'
        'python -B art/imagegen/env-u16-marmoreal-codex/_tools/en02_fix1.py finish 3\n'
        'python -B art/imagegen/env-u16-marmoreal-codex/_tools/en02_fix1.py report 3\n'
        'python -B art/imagegen/env-u16-marmoreal-codex/_tools/en02_fix1.py readme 3\n'
        'python -B art/imagegen/env-u16-marmoreal-codex/_tools/en02_fix1.py manifest 3\n```\n']
    (PKG/'README.md').write_bytes(old+'\n'.join(lines).encode('utf-8'))
    assert (PKG/'README.md').read_bytes().startswith(old)
    print('EN-01 README prefix preserved byte-for-byte; one EN-02 section appended.')


if __name__=='__main__':
    p=argparse.ArgumentParser(); p.add_argument('command',choices=['input','archive','compose','correct','finish','report','readme','manifest']);p.add_argument('n',type=int);p.add_argument('--source'); args=p.parse_args()
    if args.command=='input':make_input(args.n)
    elif args.command=='archive':archive(args.n,args.source)
    elif args.command=='compose':compose(args.n)
    elif args.command=='correct':correct(args.n)
    elif args.command=='finish':finish(args.n)
    elif args.command=='report':report(args.n)
    elif args.command=='readme':readme()
    elif args.command=='manifest':base.manifest()
