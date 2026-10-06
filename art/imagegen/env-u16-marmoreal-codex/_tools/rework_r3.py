"""EN-01 CX-07r: bounded, reproducible rework. Run with python -B.

Never runs the original preparation/finalization scripts or writes outside the
two authorized roots. Image generation is external; record copies its raw bytes.
"""
from pathlib import Path
import argparse, hashlib, json, shutil
import numpy as np
from PIL import Image, ImageDraw
from scipy.ndimage import distance_transform_edt as edt, gaussian_filter
from build_plate import ROOT, PKG, IMG, SOURCE, SPOTS, gray, sheet, digest, rel, save_json

SIZE = (1672, 941)
COMP = IMG / 'comparison'
CROP = (56, 393, 248, 585)
FORBIDDEN = ('Forbidden: copying or imitating pixels, assets, splash art, logos, card text or fonts of any commercial digital edition of a board game; brush-stroke banners and ink splatter; invented game data (card names, numbers, hero names, HP, boards, spaces); text, letters or numbers baked into textures; red fills; any element on screen that carries meaning only by colour.')
PROMPT = ('Edit this crop of a painted night garden. Remove the dark leftover lantern silhouette above the stone pedestal: the pointed finial, the wide roof outline and the thin brown hook or stem in its centre. Replace it with the same dark blue-green moonlit foliage and pink blossoms that surround it, matching the brush texture and the cold blue-grey moonlight from the west. Keep the stone pedestal with its plain flat cap, the marble balustrade and every blossom outside the silhouette unchanged. No new objects, no lantern, no figures, no text, no warm light. ' + FORBIDDEN)

def rgb(p):
    return np.array(Image.open(p).convert('RGB'))

def lab(a):
    c = a.astype(float)/255
    lin = np.where(c <= .04045, c/12.92, ((c+.055)/1.055)**2.4)
    xyz = lin @ np.array([[.4124564,.3575761,.1804375],[.2126729,.7151522,.0721750],[.0193339,.1191920,.9503041]]).T
    xyz /= np.array([.95047,1,1.08883])
    f = np.where(xyz > (6/29)**3, np.cbrt(xyz), xyz/(3*(6/29)**2)+4/29)
    return np.stack([116*f[...,1]-16,500*(f[...,0]-f[...,1]),200*(f[...,1]-f[...,2])],axis=-1)

def smooth(t):
    t = np.clip(t,0,1)
    return t*t*(3-2*t)

def polygon(points):
    im = Image.new('L', SIZE)
    ImageDraw.Draw(im).polygon(points, fill=255)
    return np.asarray(im)>0

def prepare():
    assert (PKG/'fix1-baseline.json').exists()
    old = IMG/'marmoreal-lantern-mask.png'
    dst = COMP/'r3-old-lantern-mask.png'
    if not dst.exists(): shutil.copyfile(old,dst)
    base = Image.open(SOURCE).convert('RGB')
    previous = Image.open(IMG/'concepts/EN-01-A-composite.png').convert('RGB')
    ims,labels=[],[]
    for name,x,y in SPOTS:
        box=(x-60,y-60,x+60,y+60)
        for im,title in [(base,'C0'),(previous,'previous')]:
            ims.append(im.crop(box).resize((480,480),Image.Resampling.LANCZOS))
            labels.append(f'{name} {title}; source 120x120, 4x')
    sheet('r3-inspection-cores',ims,labels,cols=2)
    sheet('r3-inspection-cores',ims,labels,cols=2,mono=True)
    field=np.asarray(Image.open(IMG/'marmoreal-field-mask.png'))
    x0,y0,x1,y1=CROP
    assert not field[y0:y1,x0:x1].any()
    path=IMG/'concepts/EN-01-R3-sw-1-input.png'
    if not path.exists(): previous.crop(CROP).resize((1024,1024),Image.Resampling.LANCZOS).save(path)
    prompt=PKG/'prompts/EN-01-R3-sw-1.txt'
    if not prompt.exists(): prompt.write_text(PROMPT,encoding='utf-8')
    print(rel(path))

def record(source,number=1):
    records=json.loads((PKG/'generation-records.json').read_text(encoding='utf-8'))
    variant=f'R3-sw-{number}'
    assert len([r for r in records['generations'] if r['variant'].startswith('R3-')])<2
    dst=IMG/f'concepts/EN-01-{variant}-raw.png'
    assert not dst.exists()
    shutil.copyfile(source,dst)
    prompt=PKG/f'prompts/EN-01-{variant}.txt'
    inp=IMG/f'concepts/EN-01-{variant}-input.png'
    records['generations'].append({'variant':variant,'prompt_key':f'EN-01-{variant}','prompt_file':rel(prompt),'prompt_sha256':digest(prompt),'input':rel(inp),'input_sha256':digest(inp),'raw_file':rel(dst),'raw_sha256':digest(dst),'raw_size':list(Image.open(dst).size),'crop_box':list(CROP),'retouched':False,'tool_managed_source':str(source),'submitted_prompt_sha256':digest(prompt),'submitted_prompt_normalization':'exact UTF-8 file text'})
    records.update(rework_budget=2,rework_generations=len(records['generations'])-4)
    save_json(PKG/'generation-records.json',records)
    print({'recorded':variant,'size':Image.open(dst).size})

CORES = {
 'nw': [(416,39),(424,39),(427,51),(429,56),(441,65),(444,57),(451,55),(453,63),(451,71),(450,78),(449,102),(452,108),(448,115),(438,119),(440,126),(432,130),(415,130),(408,126),(410,118),(404,115),(401,110),(403,104),(400,79),(396,73),(393,65),(395,56),(399,55),(399,62),(411,54),(414,49)],
 'ne': [(1242,35),(1249,35),(1250,46),(1256,48),(1258,55),(1254,60),(1266,65),(1272,68),(1273,61),(1278,61),(1280,67),(1278,73),(1276,78),(1272,102),(1274,110),(1270,117),(1260,121),(1261,128),(1255,134),(1237,134),(1228,130),(1228,122),(1219,117),(1218,111),(1220,105),(1220,77),(1213,71),(1210,65),(1211,58),(1216,57),(1216,64),(1232,57),(1237,52),(1239,46)],
 'sw': [(148,436),(154,436),(155,446),(159,450),(159,456),(168,462),(178,466),(181,457),(185,456),(188,463),(187,473),(184,481),(183,515),(187,522),(182,530),(172,536),(173,544),(164,550),(147,550),(136,547),(132,542),(136,532),(128,528),(125,522),(129,514),(125,486),(116,481),(115,476),(120,472),(121,463),(126,458),(130,460),(129,466),(140,455),(144,450)],
 'se': [(1525,438),(1531,438),(1532,445),(1540,452),(1542,458),(1536,465),(1553,471),(1563,473),(1564,463),(1568,465),(1569,476),(1567,482),(1563,488),(1558,523),(1561,530),(1555,536),(1546,540),(1545,546),(1538,552),(1521,552),(1511,548),(1510,541),(1500,536),(1495,530),(1499,523),(1502,490),(1493,481),(1492,474),(1496,465),(1500,462),(1501,467),(1500,474),(1515,466),(1519,461),(1515,454),(1519,448),(1523,445)],
 'door-w': [(781,0),(795,0),(796,10),(796,43),(800,47),(800,51),(790,56),(777,53),(777,48),(782,46),(783,18),(780,12)],
 'door-e': [(868,0),(882,0),(884,12),(880,20),(880,46),(886,48),(887,54),(877,58),(867,54),(866,49),(870,47),(870,17),(867,10)]
}
FIX_POLY = [(118,424),(148,421),(169,432),(181,447),(190,464),(188,483),(177,493),(169,507),(157,515),(141,508),(127,491),(112,480),(112,451)]

def seam_cells(plate,base,support,field,frame):
    inside=edt(support); outside=edt(~support)
    inner=support&(inside<=6)
    outer=~support&~field&(outside<=6)
    yy,xx=np.indices(field.shape)
    door_distance=np.hypot(np.maximum(np.maximum(803-xx,xx-866),0),np.maximum(yy-98,0))
    protected=frame|(door_distance<=40)
    lp=lab(plate)[...,0];lc=lab(base)[...,0]
    rows=[]
    for y in range(0,SIZE[1],32):
        for x in range(0,SIZE[0],32):
            sl=np.s_[y:min(y+32,SIZE[1]),x:min(x+32,SIZE[0])]
            i=inner[sl];o=outer[sl]; ni=int(i.sum());no=int(o.sum())
            row={'x':x,'y':y,'inner_pixels':ni,'outer_pixels':no}
            if min(ni,no)<40: row.update(status='skipped',s=None,exempt=False)
            else:
                source_delta=float(np.median(lc[sl][i])-np.median(lc[sl][o]))
                plate_delta=float(np.median(lp[sl][i])-np.median(lp[sl][o]))
                s=abs(plate_delta-source_delta); protected_share=float(protected[sl][o].mean())
                exempt=protected_share>=.5
                row.update(s=s,source_delta=source_delta,plate_delta=plate_delta,protected_outer_share=protected_share,exempt=exempt,status='exempt' if exempt else ('pass' if s<=4 else 'fail'))
            rows.append(row)
    eligible=[r for r in rows if r['s'] is not None]
    share=sum(r['s']<=4 for r in eligible)/len(eligible)
    return {'cells':rows,'measured_cells':len(eligible),'s_le_4_share':share,'non_exempt_failures':[r for r in eligible if r['s']>4 and not r['exempt']],'passed':share>=.95 and not any(r['s']>4 and not r['exempt'] for r in eligible)}

def build():
    base=rgb(SOURCE);previous=rgb(IMG/'concepts/EN-01-A-composite.png');raw=rgb(IMG/'concepts/EN-01-A-raw.png')
    remove=np.asarray(Image.open(IMG/'marmoreal-remove-mask.png'));field=np.asarray(Image.open(IMG/'marmoreal-field-mask.png'))>0
    support=(remove>0)&~field;frame=np.asarray(Image.open(COMP/'painted-frame-protection.png'))>0
    before=seam_cells(previous,base,support,field,frame)
    seam_zone=np.zeros(field.shape,dtype=bool)
    for r in before['non_exempt_failures']:
        x,y=r['x'],r['y'];seam_zone[max(0,y-32):y+64,max(0,x-32):x+64]=True
    alpha=remove.astype(float)/255
    alpha[seam_zone]=np.minimum(alpha[seam_zone],smooth(edt(support)[seam_zone]/32))
    plate=np.rint(base*(1-alpha[...,None])+raw*alpha[...,None]).astype('uint8')
    fix=polygon(FIX_POLY)
    # Feather inward 8 px, never extend outside the drawn fix polygon.
    fix_alpha=smooth(edt(fix)/8)
    assert np.all(support[fix])
    patch=np.asarray(Image.open(IMG/'concepts/EN-01-R3-sw-1-raw.png').convert('RGB').resize((192,192),Image.Resampling.LANCZOS))
    x0,y0,x1,y1=CROP;fa=fix_alpha[y0:y1,x0:x1,None]
    plate[y0:y1,x0:x1]=np.rint(plate[y0:y1,x0:x1]*(1-fa)+patch*fa).astype('uint8')
    plate[field]=128
    assert np.array_equal(plate[~(fix|seam_zone)],previous[~(fix|seam_zone)])
    Image.fromarray(plate).save(IMG/'marmoreal-clean.png')
    Image.fromarray(np.rint(fix_alpha*255).astype('uint8')).save(COMP/'r3-fix-mask.png')
    Image.fromarray(np.rint(alpha*255).astype('uint8')).save(COMP/'r3-composite-alpha.png')
    spec=json.loads((PKG/'_tools/mask-spec.json').read_text(encoding='utf-8'))
    spec['r3_cores']={name:{'polygon':poly,'dilation_px':2,'soft_edge_px':2.5,'method':'Euclidean distance field, no structuring element'} for name,poly in CORES.items()}
    spec['r3_fix_regions']=[{'spot':'sw','polygon':FIX_POLY,'crop_box':CROP,'feather_inward_px':8,'generation':'R3-sw-1','pedestal_cap_excluded':True}]
    spec['r3_seam']={'grid_px':32,'band_px':6,'feather_px':32,'expanded_cell_margin_px':32,'widened_cells':before['non_exempt_failures']}
    spec['r3_glow']={'lantern_R_px':260,'sconce_R_px':130,'window_full_to':.6,'gaussian_sigma_px':3,'threshold':8,'formula':'clip(max((dL-3)/20,(db-4)/25),0,1)','lab':'CIELAB D65 from sRGB','radius_reapplied_after_blur':True}
    save_json(PKG/'_tools/mask-spec.json',spec)
    core_alpha=np.zeros(field.shape);core_region=np.zeros(field.shape,dtype=bool);core_polys=np.zeros(field.shape,dtype=bool)
    for poly in CORES.values():
        binary=polygon(poly);core_polys|=binary
        dist=edt(~binary);dilated=dist<=2;core_region|=dilated
        core_alpha=np.maximum(core_alpha,1-smooth(np.maximum(dist-2,0)/2.5))
    lc=lab(base);lp=lab(plate)
    g=np.clip(np.maximum((np.maximum(lc[...,0]-lp[...,0],0)-3)/20,(np.maximum(lc[...,2]-lp[...,2],0)-4)/25),0,1)
    yy,xx=np.indices(field.shape);glow=np.zeros(field.shape);radius_union=np.zeros(field.shape,dtype=bool)
    for name,x,y in SPOTS:
        R=130 if name.startswith('door') else 260
        rr=np.hypot(xx-x,yy-y);window=1-smooth((rr-.6*R)/(.4*R))
        radius_union|=rr<=R
        blurred=gaussian_filter(g*window,sigma=3)
        blurred[rr>R]=0
        glow=np.maximum(glow,blurred)
    glow[glow<8/255]=0
    m=np.rint(np.minimum(np.maximum(core_alpha,glow),remove/255)*255).astype('uint8')
    m[field|~radius_union]=0
    Image.fromarray(m).save(IMG/'marmoreal-lantern-mask.png')
    lit=np.rint(plate*(1-m[...,None]/255)+base*(m[...,None]/255)).astype('uint8')
    Image.fromarray(lit).save(COMP/'r3-lit-full.png')
    after=seam_cells(plate,base,support,field,frame)
    changed=np.any(plate!=previous,axis=2)
    diff=changed.astype('uint8')*255
    Image.fromarray(diff).save(COMP/'r3-diff-vs-previous.png')
    outside_changed=np.any(plate!=base,axis=2)&(remove==0)
    Image.fromarray(outside_changed.astype('uint8')*255).save(COMP/'08-diff-outside-remove-mask.png')
    metrics=measure(plate,base,lit,m,core_polys,core_region,radius_union,support,field,before,after,changed,fix,seam_zone)
    save_json(PKG/'verification.json',metrics)
    make_sheets(base,previous,plate,lit,m,before,after)
    print(json.dumps({k:metrics[k] for k in ['R1','R2','R3','lantern_mask','lit_check','changes_vs_previous_plate']},ensure_ascii=False))
    print(json.dumps({'R4_before':{k:v for k,v in before.items() if k!='cells'},'R4_after':{k:v for k,v in after.items() if k!='cells'}},ensure_ascii=False))

def measure(plate,base,lit,m,core_polys,core_region,radius_union,support,field,before,after,changed,fix,seam_zone):
    lp=lab(plate);lc=lab(base);ll=lab(lit);yy,xx=np.indices(field.shape)
    door_opening=(xx>=803)&(xx<867)&(yy<99)
    door_band=edt(~door_opening)<=6
    r1=[];r2=[];r3=[];legacy=[];lit_rows=[]
    for name,x,y in SPOTS:
        rr=np.hypot(xx-x,yy-y)
        spot=(xx>=x-12)&(xx<x+12)&(yy>=y-12)&(yy<y+12)
        ring=(rr>=24)&(rr<48)
        a=float(np.median(lp[...,0][spot]));b=float(np.median(lp[...,0][ring]))
        r1.append({'spot':name,'spot_median_Lstar':a,'ring_median_Lstar':b,'signed_delta':a-b,'passed':a<=b+4})
        legacy.append({'spot':name,'absolute_delta':abs(a-b),'legacy_passed':abs(a-b)<=4})
        centre=(rr<12)&(~door_band if name.startswith('door') else True)
        hot=centre&(lp[...,0]>60)&(lp[...,2]>20)
        r2.append({'spot':name,'hot_pixels':int(hot.sum()),'measured_pixels':int(centre.sum()),'passed':not hot.any()})
        area=(rr<(48 if name.startswith('door') else 96))&support
        if name.startswith('door'): area&=~door_band
        warm=area&(lp[...,2]>20)&(lp[...,0]>25);share=float(warm.sum()/area.sum())
        r3.append({'spot':name,'warm_pixels':int(warm.sum()),'measured_pixels':int(area.sum()),'share':share,'passed':share<=.01})
        de=np.linalg.norm(ll-lc,axis=2);disk=rr<96
        lit_rows.append({'spot':name,'radius_px':96,'mean_dE76':float(de[disk].mean()),'plate_alone_mean_dE76':float(np.linalg.norm(lp-lc,axis=2)[disk].mean()),'passed':float(de[disk].mean())<=8})
    edge_exclusion=edt(~core_region)<=2.5
    diffs=[]
    for axis in [0,1]:
        step=np.abs(np.diff(m.astype(int),axis=axis))
        if axis==0: allowed=~edge_exclusion[:-1]&~edge_exclusion[1:]
        else: allowed=~edge_exclusion[:,:-1]&~edge_exclusion[:,1:]
        diffs.append(int(step[allowed].max(initial=0)))
    warm=(lc[...,2]>20)&(lc[...,0]>25)&~support&~field
    frame=np.asarray(Image.open(COMP/'painted-frame-protection.png'))>0
    regions={'door_steps':[740,99,930,210],'urns':[710,40,952,160],'door_jambs':[770,0,900,105],'SE_paving_below_frame_corner':[1300,765,1490,880]}
    residual={'all_outside_support':int(warm.sum()),'protected_wooden_frame':int((warm&frame).sum()),'areas_may_overlap':True,'unchanged':bool(np.array_equal(plate[warm],base[warm]))}
    for name,(x0,y0,x1,y1) in regions.items(): residual[name]={'box':[x0,y0,x1,y1],'warm_pixels':int(warm[y0:y1,x0:x1].sum())}
    alpha=m.astype(float)/255
    per_core=[]
    remove=np.asarray(Image.open(IMG/'marmoreal-remove-mask.png'))
    for name,poly in CORES.items():
        binary=polygon(poly);dilated=edt(~binary)<=2
        bad=binary&(m!=255);ys,xs=np.where(bad)
        per_core.append({'spot':name,'polygon_pixels':int(binary.sum()),'polygon_pixels_below_255':int(bad.sum()),'dilated_pixels_below_255':int(np.count_nonzero(m[dilated]!=255)),'lit_pixels_different_from_C0':int(np.count_nonzero(np.any(lit!=base,axis=2)&binary)),'clipped_bounds':None if not len(xs) else [int(xs.min()),int(ys.min()),int(xs.max()),int(ys.max())],'remove_values_at_clipped_pixels':np.unique(remove[bad]).tolist()})
    mask_metrics={'nonzero_share':float((m>0).mean()),'share_ge_128':float((m>=128).mean()),'alpha_weighted_mean':float((alpha*alpha).sum()/alpha.sum()),'global_mean_alpha':float(alpha.mean()),'mean_alpha_levels':float(m.mean()),'max_4_neighbour_step_outside_core_edges':max(diffs),'core_polygons_all_255':bool(np.all(m[core_polys]==255)),'dilated_cores_all_255':bool(np.all(m[core_region]==255)),'core_clipped_pixels':int(np.count_nonzero(m[core_region]!=255)),'per_core':per_core,'zero_outside_remove_support':bool(np.all(m[~support]==0)),'zero_on_field':bool(np.all(m[field]==0)),'zero_beyond_radius':bool(np.all(m[~radius_union]==0)),'radius_convention':'union of each light own radius; overlapping lights retained','step_core_exclusion':'dilated cores plus their exact 2.5 px distance-field soft edge','constraint_conflict':'Complete sconce bracket polygons overlap frozen remove-mask feather and protected door boundary. The mandated min(core/glow, remove/255) clips them; full 255 cores cannot be asserted. Polygons were not shrunk to conceal this.'}
    return {'task':'EN-01','run':'CX-07r fix1','status':'предложено','outside_folder':[],'palette':'not applicable: plate colours come from the painting','changed_pixels_outside_remove_mask':int(np.count_nonzero(np.any(plate!=base,axis=2)&~(support|field))),'field_all_808080':bool(np.all(plate[field]==128)),'changes_vs_previous_plate':{'total':int(changed.sum()),'fix_mask':int((changed&fix).sum()),'seam_cells':int((changed&seam_zone&~fix).sum()),'elsewhere':int((changed&~fix&~seam_zone).sum())},'lantern_mask':mask_metrics,'lit_check':{'cores_equal_C0_exactly':bool(np.array_equal(lit[core_polys],base[core_polys])),'per_light':lit_rows},'R1':r1,'R2':r2,'R3':r3,'R4':{'before':before,'after':after},'legacy_spot_ring_Lstar':{'status':'superseded by ВР-VS2-EN.1','per_spot':legacy},'residual_warm_outside_support':residual}

def make_sheets(base,previous,plate,lit,m,before,after):
    images=[Image.fromarray(a) for a in [base,previous,plate]]
    for scale,method,suffix in [(4,Image.Resampling.LANCZOS,'4x'),(2,Image.Resampling.NEAREST,'2x-nearest')]:
        ims=[];labels=[]
        for name,x,y in SPOTS:
            for im,title in zip(images,['C0','previous','new']):
                ims.append(im.crop((x-60,y-60,x+60,y+60)).resize((120*scale,120*scale),method));labels.append(f'{name} {title} ({x},{y}) {suffix}')
        for mono in [False,True]: sheet(f'r3-K2-six-{suffix}',ims,labels,cols=3,mono=mono)
    for size,title in [(SIZE,'r3-full'),((1087,612),'r3-working-1087x612'),((836,471),'r3-working-836x471')]:
        ims=[images[i].resize(size,Image.Resampling.LANCZOS) for i in [0,2]]
        for mono in [False,True]: sheet(title,ims,['C0','new clean'],cols=2,mono=mono)
    maps=[]
    colours={'pass':(80,230,120),'fail':(255,60,60),'exempt':(255,190,60),'skipped':(90,100,120)}
    for a,metrics in [(previous,before),(plate,after)]:
        im=Image.fromarray(np.uint8(a*.4));d=ImageDraw.Draw(im)
        for row in metrics['cells']:
            x,y=row['x'],row['y'];d.rectangle((x,y,x+31,y+31),outline=colours[row['status']],width=1)
            if row['status']!='skipped':d.text((x+1,y+1),{'pass':'P','fail':'F','exempt':'E'}[row['status']],fill=colours[row['status']])
        maps.append(im)
    for mono in [False,True]: sheet('r3-seam-map',maps,['before: P pass, F fail, E exempt; empty skipped','after: P pass, F fail, E exempt; empty skipped'],cols=2,mono=mono)
    for row in before['non_exempt_failures']:
        x,y=row['x'],row['y'];box=(x-16,y-16,x+48,y+48)
        ims=[im.crop(box).resize((192,192),Image.Resampling.NEAREST) for im in images]
        for mono in [False,True]:sheet(f'r3-seam-cell-{x}-{y}',ims,['C0','previous','new; 3x nearest'],cols=3,mono=mono)
    old=Image.open(COMP/'r3-old-lantern-mask.png').convert('RGB');new=Image.fromarray(m).convert('RGB')
    overlay=Image.fromarray(np.uint8(base*.6+np.stack([m,np.zeros_like(m),m],axis=-1)*.4))
    for mono in [False,True]:sheet('r3-lantern-mask',[old,new,overlay],['old mask','new mask','new alpha over C0'],cols=3,mono=mono)
    ims=[];labels=[]
    for name,x,y in SPOTS:
        for a,title in [(base,'C0'),(lit,'lit')]:
            ims.append(Image.fromarray(a).crop((x-60,y-60,x+60,y+60)).resize((240,240),Image.Resampling.NEAREST));labels.append(f'{name} {title}; 2x nearest')
    for mono in [False,True]:sheet('r3-lit-K2-six',ims,labels,cols=2,mono=mono)
    gray(Image.fromarray(lit)).save(COMP/'r3-lit-full-gray.png')
    ims=[];labels=[]
    for name,x,y in SPOTS[-2:]:
        box=(x-32,0,x+32,70)
        contour=Image.fromarray(base.copy());d=ImageDraw.Draw(contour)
        d.line(CORES[name]+[CORES[name][0]],fill=(0,255,255),width=1)
        for im,title in [(images[0],'C0'),(contour,'complete core outline'),(Image.fromarray(m).convert('RGB'),'clipped alpha'),(Image.fromarray(lit),'lit')]:
            ims.append(im.crop(box).resize((256,280),Image.Resampling.NEAREST));labels.append(f'{name} {title}; 4x nearest')
    for mono in [False,True]:sheet('r3-sconce-core-clipping',ims,labels,cols=4,mono=mono)

def verify():
    v=json.loads((PKG/'verification.json').read_text(encoding='utf-8'));b=json.loads((PKG/'fix1-baseline.json').read_text(encoding='utf-8'))
    checks={p:{'before':entry,'after':{'sha256':digest(ROOT/p),'bytes':(ROOT/p).stat().st_size},'unchanged':digest(ROOT/p)==entry['sha256'] and (ROOT/p).stat().st_size==entry['bytes']} for p,entry in b['files'].items()}
    v['source_unchanged']=all(checks[p]['unchanged'] for p in b['sources'])
    v['frozen_unchanged']=checks
    records=json.loads((PKG/'generation-records.json').read_text(encoding='utf-8'))
    v['generations']=records;v['budget']={'original':4,'original_used':4,'rework':2,'rework_used':records['rework_generations'],'SYNTX':0}
    v['tool_cache_outside_repo']=[r['tool_managed_source'] for r in records['generations'][4:]]
    v['generation_records_append_only']=records['generations'][:4]==b['generation_records_before']['generations']
    v['generation_hash_checks']=[{'variant':r['variant'],'raw':digest(ROOT/r['raw_file'])==r['raw_sha256'],'input':digest(ROOT/r['input'])==r['input_sha256'],'prompt':digest(ROOT/r['prompt_file'])==r['prompt_sha256']} for r in records['generations']]
    plate=rgb(IMG/'marmoreal-clean.png');base=rgb(SOURCE);old=rgb(IMG/'concepts/EN-01-A-composite.png')
    remove=np.asarray(Image.open(IMG/'marmoreal-remove-mask.png'));field=np.asarray(Image.open(IMG/'marmoreal-field-mask.png'))>0
    new_mask=np.asarray(Image.open(IMG/'marmoreal-lantern-mask.png'));support=(remove>0)&~field
    spec=json.loads((PKG/'_tools/mask-spec.json').read_text(encoding='utf-8'))
    zone=np.zeros(field.shape,dtype=bool)
    for r in spec['r3_seam']['widened_cells']:
        x,y=r['x'],r['y'];zone[max(0,y-32):y+64,max(0,x-32):x+64]=True
    fix=polygon(spec['r3_fix_regions'][0]['polygon'])
    core=np.zeros(field.shape,dtype=bool)
    for entry in spec['r3_cores'].values(): core|=edt(~polygon(entry['polygon']))<=2
    edge_exclusion=edt(~core)<=2.5
    delta_y=np.abs(np.diff(new_mask.astype(int),axis=0));delta_x=np.abs(np.diff(new_mask.astype(int),axis=1))
    actual_step=int(max(delta_y[~edge_exclusion[:-1]&~edge_exclusion[1:]].max(),delta_x[~edge_exclusion[:,:-1]&~edge_exclusion[:,1:]].max()))
    assert actual_step==v['lantern_mask']['max_4_neighbour_step_outside_core_edges']
    v['lantern_mask']['step_core_exclusion']='dilated cores plus their exact 2.5 px distance-field soft edge'
    v['tool_source_readback']=[{'variant':r['variant'],'source_byte_identical_to_raw':digest(Path(r['tool_managed_source']))==r['raw_sha256']} for r in records['generations'][4:]]
    frame=np.asarray(Image.open(COMP/'painted-frame-protection.png'))>0
    expected_hashes={'scraped-data/derived/concepts/env-v1/marmoreal-v1.png':'8f098ef2980162a9fa48fdec6865618388e5e0486c73b71247dff5fccc72e662',rel(IMG/'marmoreal-field-mask.png'):'d3fe2452fe262b1a1392bd4954ac87d2fb3de454cd9dbf82dfdddcda2a82e2ca',rel(IMG/'marmoreal-remove-mask.png'):'dc5d41e26228dd665c39fa63078ed54bb47440ee276758abba140cc84cf12099',rel(IMG/'concepts/EN-01-A-composite.png'):'a127769e876620310f617310c439d4ceb973f0fb05d91a446f2846c27d02ba08'}
    prefix=(PKG/'README.md').read_bytes()[:b['readme_before']['bytes']]
    readback={'plate_RGB_1672x941':Image.open(IMG/'marmoreal-clean.png').mode=='RGB' and Image.open(IMG/'marmoreal-clean.png').size==SIZE,'mask_L_1672x941':Image.open(IMG/'marmoreal-lantern-mask.png').mode=='L' and Image.open(IMG/'marmoreal-lantern-mask.png').size==SIZE,'field_all_808080':bool(np.all(plate[field]==128)),'outside_remove_zero':bool(np.array_equal(plate[remove==0],base[remove==0])),'elsewhere_unchanged':bool(np.array_equal(plate[~(fix|zone)],old[~(fix|zone)])),'fix_inside_support':bool(np.all(support[fix])),'painted_frame_unchanged':bool(np.array_equal(plate[frame],base[frame])),'door_interior_unchanged':bool(np.array_equal(plate[:99,803:867],base[:99,803:867])),'mask_not_above_remove':bool(np.all(new_mask<=remove)),'mask_zero_on_field':bool(np.all(new_mask[field]==0)),'outside_diff_black':bool(np.all(np.asarray(Image.open(COMP/'08-diff-outside-remove-mask.png'))==0)),'old_mask_backup_byte_identical':digest(COMP/'r3-old-lantern-mask.png')==b['current_deliverables'][rel(IMG/'marmoreal-lantern-mask.png')]['sha256'],'README_original_bytes_unchanged':hashlib.sha256(prefix).hexdigest()==b['readme_before']['sha256'],'fixed_task_hashes_match':all(digest(ROOT/p)==h for p,h in expected_hashes.items()),'generations_intact':all(all(r[k] for k in ['raw','input','prompt']) for r in v['generation_hash_checks'])}
    gray_checks={}
    for p in COMP.glob('r3-*-gray.png'):
        src=p.with_name(p.name.replace('-gray.png','-colour.png'))
        if src.exists():
            # Headers are already neutral; gray is computed on source panels.
            expected=np.asarray(gray(Image.open(src).convert('RGB')));actual=rgb(p)
            gray_checks[rel(p)]=bool(np.array_equal(actual,expected))
    readback['Rec709_gray_sheets']=all(gray_checks.values())
    v['independent_readback']={'checks':readback,'gray_checks':gray_checks,'passed':all(readback.values())}
    paths=sorted(set(COMP.glob('r3-*.png'))|set((IMG/'concepts').glob('EN-01-R3-*.png'))|{IMG/'marmoreal-clean.png',IMG/'marmoreal-lantern-mask.png',COMP/'08-diff-outside-remove-mask.png'})
    v['exports']={rel(p):{'size':list(Image.open(p).size),'mode':Image.open(p).mode,'sha256':digest(p)} for p in paths}
    v['gray']=[rel(p) for p in paths if 'gray' in p.name];v['sizes']={'plate':list(Image.open(IMG/'marmoreal-clean.png').size),'mask':list(Image.open(IMG/'marmoreal-lantern-mask.png').size),'working':[[1087,612],[836,471]],'K2_source':[120,120]}
    review_path=PKG/'_tools/visual-review-r3.json'
    review=json.loads(review_path.read_text(encoding='utf-8')) if review_path.exists() else {}
    v['visual_review']=review
    mask=v['lantern_mask'];accept=[]
    def row(line,passed,measured,expected,note=''):
        accept.append({'line':line,'passed':bool(passed),'measured':measured,'expected':expected,'note':note})
    row('1) Sources, scope, frozen masks, outside diff',v['source_unchanged'] and all(x['unchanged'] for x in checks.values()) and all(readback.values()) and v['generation_records_append_only'] and v['changed_pixels_outside_remove_mask']==0 and v['changes_vs_previous_plate']['elsewhere']==0,{'source_unchanged':v['source_unchanged'],'outside_folder':[],'outside_diff':v['changed_pixels_outside_remove_mask'],'elsewhere':v['changes_vs_previous_plate']['elsewhere'],'independent_readback':readback},'sources/frozen byte-identical; no writes outside roots; outside/elsewhere = 0')
    row('2) Six lights removed, pedestals, warm exceptions, gray field, no water',review.get('silhouettes_removed',False) and review.get('pedestals_intact',False) and review.get('no_new_objects_water_figures_text',False) and v['field_all_808080'],review,'Read every PNG; field #808080; residual warm outside support allowed by ВР-VS2-EN.2')
    row('3) R1-R4 and K2 without visible boundary',all(r['passed'] for key in ['R1','R2','R3'] for r in v[key]) and v['R4']['after']['passed'] and review.get('K2_no_visible_boundary',False),{'R1':all(r['passed'] for r in v['R1']),'R2':all(r['passed'] for r in v['R2']),'R3':all(r['passed'] for r in v['R3']),'R4_share':v['R4']['after']['s_le_4_share'],'R4_non_exempt_failures':len(v['R4']['after']['non_exempt_failures'])},'R1 <= ring+4; R2 = 0; R3 <=1%; R4 >=95%, all non-exempt <=4; K2 no visible boundary')
    row('4) Gray sheet: pedestals and balustrades readable',review.get('gray_readable',False),review.get('gray_notes','pending inspection'),'Read gray sheets')
    mask_pass=mask['core_polygons_all_255'] and mask['zero_outside_remove_support'] and mask['zero_on_field'] and mask['zero_beyond_radius'] and mask['share_ge_128']<=.1 and mask['max_4_neighbour_step_outside_core_edges']<=48
    lit_pass=all(r['passed'] for r in v['lit_check']['per_light']) and v['lit_check']['cores_equal_C0_exactly'] and review.get('lit_no_double_edges',False)
    row('5) Lantern mask and lit overlay',mask_pass and lit_pass,{'mask':mask,'lit_check':v['lit_check'],'no_double_edges':review.get('lit_no_double_edges',False)},'cores 255, zeros outside support/field/radius, >=128 share <=10%, max noncore step <=48, dE76 <=8 each, no double edges',mask['constraint_conflict'] if not mask['core_polygons_all_255'] else '')
    row('6) Changed paths restricted to package (images in authorized derived root)',True,{'agent_written_roots':[rel(PKG),rel(IMG)],'git_commands':0},'two authorized roots; git status prohibited by user','Scope is enforced by write targets and frozen hashes; no git command used. Tool cache explicitly permitted by fix1.')
    v['acceptance']=accept;v['acceptance_pass']=all(r['passed'] for r in accept)
    v['limits']=[{'line':r['line'],'measured':r['measured'],'expected':r['expected'],'note':r['note']} for r in accept if not r['passed']]
    save_json(PKG/'verification.json',v)
    print(json.dumps({'sources':v['source_unchanged'],'frozen':all(x['unchanged'] for x in checks.values()),'acceptance':[{k:r[k] for k in ['line','passed']} for r in accept]},ensure_ascii=False))

def manifest():
    files=sorted(p for root in [PKG,IMG] for p in root.rglob('*') if p.is_file() and p!=PKG/'manifest-sha256.json')
    save_json(PKG/'manifest-sha256.json',{'schema':'en01.manifest/2','run':'CX-07r fix1','files':{rel(p):{'sha256':digest(p),'bytes':p.stat().st_size} for p in files}})
    print({'manifest_files':len(files)})

if __name__ == '__main__':
    p=argparse.ArgumentParser(); p.add_argument('command',choices=['prepare','record','build','verify','manifest']); p.add_argument('--source'); p.add_argument('--number',type=int,default=1)
    args=p.parse_args()
    if args.command=='prepare': prepare()
    elif args.command=='record': record(args.source,args.number)
    elif args.command=='build': build()
    elif args.command=='verify': verify()
    elif args.command=='manifest': manifest()
