"""HB-44 fix1: real K1 geometry, local label retouch, topology and package audit.

No runtime/editor access, installation, network, or image generation.
All writes go through the two explicit package roots.
"""
import argparse
import json
import math
import os
import re
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFilter
from scipy import ndimage as ndi

FIGHTERS = {'f-0-hero':'medusa','f-0-sk0':'harpy1','f-0-sk1':'harpy2',
            'f-0-sk2':'harpy3','f-1-hero':'arthur','f-1-sk0':'merlin'}
TRACES = {
 'marmoreal':'docs/game-design/evidence/ENV-MAPS/p7-concept-paste-2026-10-01/marmoreal-concept-flag/bench.trace.log',
 'sarpedon':'docs/game-design/evidence/ENV-MAPS/p10-sarpedon-rework-2026-10-03/sarpedon-packaged/bench.trace.txt'}
TIMES = {'marmoreal':'18.34.51','sarpedon':'13.42.56'}
RU = {'medusa':'Медуза','arthur':'Король Артур','merlin':'Мерлин',
      'harpy1':'Гарпия 1','harpy2':'Гарпия 2','harpy3':'Гарпия 3'}
EN = {'medusa':'Medusa','arthur':'King Arthur','merlin':'Merlin',
      'harpy1':'Harpy 1','harpy2':'Harpy 2','harpy3':'Harpy 3'}
STRINGS = {
 'hud.plate.role.hero_ranged':('ГЕРОЙ · ДАЛЬНИЙ','HERO · RANGED'),
 'hud.plate.role.hero_melee':('ГЕРОЙ · БЛИЖНИЙ','HERO · MELEE'),
 'hud.plate.role.sidekick_ranged':('ПОМОЩНИК · ДАЛЬНИЙ','SIDEKICK · RANGED'),
 'hud.plate.role.sidekick_melee':('ПОМОЩНИК · БЛИЖНИЙ','SIDEKICK · MELEE'),
 'hud.plate.side.own':('ВАШ','YOURS'),
 'hud.plate.side.opponent':('СОПЕРНИК','OPPONENT'),
 'hud.plate.target':('ЦЕЛЬ','TARGET'),
 'hud.number.example':('пример','example'),
 'hud.plate.harpy_name':('Гарпия {number}','Harpy {number}')}
BG = {}; ERASE = {}; TOPO = {}; SPACE_MASKS = {}; GEO = {}; GENERATED = set()
PLATE_CACHE = {}


def write_json(b,path,obj):
    GENERATED.add(path.resolve()); b.save_json(path,obj)


def output(b,path,im):
    GENERATED.add(path.resolve()); GENERATED.add(path.with_name(path.stem+'-gray.png').resolve())
    b.output(path,im)


def homography(src,dst):
    # Normalised DLT least-squares fit; the integer SHOT coordinates have rounding error.
    def normalise(p):
        p=np.asarray(p,float); c=p.mean(0); s=math.sqrt(2)/np.linalg.norm(p-c,axis=1).mean()
        t=np.array([[s,0,-s*c[0]],[0,s,-s*c[1]],[0,0,1]])
        return (p-c)*s,t
    a,ta=normalise(src); z,tz=normalise(dst); rows=[]
    for (x,y),(u,v) in zip(a,z):
        rows.extend([[-x,-y,-1,0,0,0,u*x,u*y,u],[0,0,0,-x,-y,-1,v*x,v*y,v]])
    _,_,vh=np.linalg.svd(rows); h=np.linalg.inv(tz)@vh[-1].reshape(3,3)@ta
    return h/h[2,2]


def project(h,xy):
    p=np.c_[np.asarray(xy,float),np.ones(len(xy))]@h.T
    return p[:,:2]/p[:,2:]


def geometry(b,board):
    text=(b.ROOT/TRACES[board]).read_text(encoding='utf-8')
    lines=[l for l in text.splitlines() if TIMES[board] in l]
    geo={'figures':{},'bases':{},'labels':{},'world':{},'positions':{},'seams':[]}
    for l in lines:
        m=re.search(r'SHOT fighter (\S+) pos=\(([^)]+)\) world=\(([^)]+)\) screen=\(([^)]+)\)',l)
        if m:
            k=FIGHTERS[m[1]]; geo['positions'][k]=list(map(int,m[2].split(',')))
            geo['world'][k]=list(map(float,m[3].split(',')))[:2]
            geo['bases'][k]=list(map(float,m[4].split(',')))
        m=re.search(r'SHOT (figure|label) fighter=(\S+).*?bbox=\(([^)]+)\)',l)
        if m:geo['figures' if m[1]=='figure' else 'labels'][FIGHTERS[m[2]]]=list(map(int,m[3].split(',')))
    assert all(len(geo[k])==6 for k in ['figures','bases','labels','positions'])
    # The trace's projected proxy is narrower than the visible v2 Harpy wings.
    # Conservatively remeasure the full figure envelope in the K1 frame, including
    # wings/capes/base rims. Keep the unmodified trace boxes separately for review.
    geo['trace_figures']={k:list(v) for k,v in geo['figures'].items()}
    overhang={'marmoreal':{'harpy1':(16,16),'harpy2':(16,16),'harpy3':(16,16),'arthur':(8,9),'merlin':(12,5)},
              'sarpedon':{'harpy1':(16,16),'harpy2':(16,16),'harpy3':(16,16),'arthur':(8,9),'merlin':(4,6)}}
    for k,(left,right) in overhang[board].items():
        geo['figures'][k][0]-=left;geo['figures'][k][2]+=right
    geo['visible_figure_mask_method']='K1 trace box plus conservative image-checked horizontal wing/cape/base-rim envelope; Medusa trace box already contains the silhouette.'
    geo['visible_figure_overhang_px']={k:list(v) for k,v in overhang[board].items()}
    h=homography([geo['world'][k] for k in b.IDS],[geo['bases'][k] for k in b.IDS])
    residual=np.linalg.norm(project(h,[geo['world'][k] for k in b.IDS])-np.array([geo['bases'][k] for k in b.IDS]),axis=1)
    # Convert world to the supplied illustration pixels, then to the frame.
    geo['map_to_screen']= (h@np.array([[1/1.5,0,-668.5/1.5],[0,1/1.5,-433/1.5],[0,0,1]])).tolist()
    geo['fighter_fit_residual_px']=residual.tolist()
    topo=json.loads((b.ROOT/f'backend/prisma/fixtures/boards/{board}.topology.json').read_text(encoding='utf-8'))
    TOPO[board]=topo; geo['spaces']=[]; space_masks={}
    for sp in topo['spaces']:
        xy=np.array([sp['layout']['x'],sp['layout']['y']]); radius=topo['spaceRadiusPx']
        pts=xy+np.c_[np.cos(np.linspace(0,2*np.pi,96)),np.sin(np.linspace(0,2*np.pi,96))]*radius
        polygon=project(np.array(geo['map_to_screen']),pts)
        mask=Image.new('1',(1920,1080)); ImageDraw.Draw(mask).polygon([tuple(p) for p in polygon],fill=1)
        space_masks[sp['id']]=mask
        centre=project(np.array(geo['map_to_screen']),[xy])[0]
        geo['spaces'].append([*centre, max(abs(polygon[:,0]-centre[0])),max(abs(polygon[:,1]-centre[1]))])
    # Thin connection corridors: a tag cannot lie across a seam between two spaces.
    byid={sp['id']:sp for sp in topo['spaces']}
    for a,z in topo['edges']:
        ends=project(np.array(geo['map_to_screen']),[[byid[k]['layout']['x'],byid[k]['layout']['y']] for k in [a,z]])
        vec=ends[1]-ends[0]; norm=np.linalg.norm(vec)
        # Remove the circular areas: only the inter-space printed connection remains.
        p=ends[0]+vec*.42; q=ends[0]+vec*.58
        geo['seams'].append([*p,*q])
    bounds=project(np.array(geo['map_to_screen']),[[0,0],[1336,0],[1336,865],[0,865]])
    geo['field']=[*bounds.min(0),*bounds.max(0)]
    geo['k1_time']=TIMES[board]; geo['trace']=TRACES[board]; geo['homography_world_to_screen']=h.tolist()
    GEO[board]=geo; SPACE_MASKS[board]=space_masks; b.GEOMETRY[board]=geo


def robust_fit(x,y):
    coef=[]; errors=[]
    for channel in range(3):
        a=np.c_[x[:,channel],np.ones(len(x))]; target=y[:,channel]; keep=np.ones(len(x),bool)
        for _ in range(5):
            c=np.linalg.lstsq(a[keep],target[keep],rcond=None)[0]
            e=target-a@c; med=np.median(e[keep]); mad=np.median(abs(e[keep]-med))
            keep=abs(e-med)<max(8,3*1.4826*mad)
        if not .4<=c[0]<=1.5:
            c[0]=np.clip(c[0],.4,1.5);c[1]=np.median(target[keep]-x[keep,channel]*c[0])
            e=target-a@c
        coef.append(c); errors.append(float(np.sqrt(np.mean(e[keep]**2))))
    return np.array(coef),errors


def figure_mask_sheet(b,board):
    frame=Image.open(b.ROOT/b.BOARDS[board]).convert('RGB');geo=GEO[board]
    cw=400;ch=416
    sheet=Image.new('RGB',(cw*3,ch*2+52),b.rgb('card.navy'));d=ImageDraw.Draw(sheet)
    d.text((12,12),'Маски фигур ×3 · trace / полный силуэт',font=b.font(24),fill=b.rgb('text.primary'))
    for i,k in enumerate(b.IDS):
        box=geo['figures'][k];cropbox=[box[0]-8,box[1]-8,box[2]+9,box[3]+9]
        crop=frame.crop(cropbox);cd=ImageDraw.Draw(crop)
        for bounds,color in [(geo['trace_figures'][k],'state.pending'),(box,'card.cream')]:
            cd.rectangle([bounds[0]-cropbox[0],bounds[1]-cropbox[1],bounds[2]-cropbox[0],bounds[3]-cropbox[1]],outline=b.rgb(color),width=1)
        x=(i%3)*cw;y=52+(i//3)*ch
        d.text((x+12,y+4),RU[k],font=b.font(14),fill=b.rgb('text.primary'))
        sheet.paste(crop.resize((crop.width*3,crop.height*3),Image.Resampling.NEAREST),(x+12,y+30))
    output(b,b.DERIVED/f'HB-44-figure-masks-{board}-x3.png',sheet)


def erase_labels(b,board):
    geo=GEO[board]; frame=np.array(Image.open(b.ROOT/b.BOARDS[board]).convert('RGB'),float)
    illustration=np.array(Image.open(b.ROOT/f'scraped-data/images/maps/{board}.png').convert('RGB'),float)
    yy,xx=np.indices(frame.shape[:2]); inv=np.linalg.inv(geo['map_to_screen'])
    coords=project(inv,np.c_[xx.ravel(),yy.ravel()]).reshape(1080,1920,2)
    inside=(coords[:,:,0]>=0)&(coords[:,:,0]<=1336)&(coords[:,:,1]>=0)&(coords[:,:,1]<=865)
    warped=np.stack([ndi.map_coordinates(illustration[:,:,c],[coords[:,:,1],coords[:,:,0]],order=1,mode='nearest') for c in range(3)],axis=-1)
    warped=ndi.gaussian_filter(warped,(.48,.48,0))
    result=frame.copy(); records=[]; crops=[]; union=np.zeros((1080,1920),bool)
    fl=frame@np.array([.2126,.7152,.0722])
    for k in b.IDS:
        label=geo['labels'][k]; x0,y0,x1,y1=[label[0]-4,label[1]-4,label[2]+4,label[3]+4]
        box=[x0,y0,x1,y1]; region=np.zeros(inside.shape,bool);region[y0:y1+1,x0:x1+1]=True
        ring=ndi.binary_dilation(region,iterations=9)&~region&inside
        for fig in geo['figures'].values():ring[fig[1]:fig[3]+1,fig[0]:fig[2]+1]=False
        # Avoid any neighbouring old label in the fitting ring.
        for other in geo['labels'].values():ring[other[1]-2:other[3]+3,other[0]-2:other[2]+3]=False
        valid=ring&(np.max(frame,axis=-1)<225)
        coeff,rms=robust_fit(warped[valid],frame[valid])
        matched=np.clip(warped*coeff[:,0]+coeff[:,1],0,255)
        # Preserve the local lighting gradient left by the robust colour fit.
        # A smooth residual field is inferred solely from the non-label fitting ring.
        # It avoids glyph-shaped tone steps when the illustration's gray differs
        # from the lit board by a few RGB levels near a cell rim.
        rx0=max(0,x0-12);ry0=max(0,y0-12);rx1=min(1920,x1+13);ry1=min(1080,y1+13)
        weight=valid[ry0:ry1,rx0:rx1].astype(float)
        denom=ndi.gaussian_filter(weight,8)
        local=frame[ry0:ry1,rx0:rx1]-matched[ry0:ry1,rx0:rx1]
        correction=np.stack([ndi.gaussian_filter(local[:,:,ch]*weight,8)/np.maximum(denom,1e-6) for ch in range(3)],axis=-1)
        matched[ry0:ry1,rx0:rx1]=np.clip(matched[ry0:ry1,rx0:rx1]+correction,0,255)
        ml=matched@np.array([.2126,.7152,.0722])
        # White/cream world labels: brightness excess, with a lower absolute floor.
        threshold={('sarpedon','harpy3'):-25,('sarpedon','arthur'):-5,
                   ('sarpedon','merlin'):0,('marmoreal','harpy3'):-5}.get((board,k),8)
        floor=45 if k=='harpy3' else 82
        excess=(fl-ml>threshold)&(fl>floor)&inside
        # Off the board, top-edge text is identified against local smooth diffusion.
        smooth=ndi.median_filter(fl[y0:y1+1,x0:x1+1],size=9)
        excess[y0:y1+1,x0:x1+1]|=(~inside[y0:y1+1,x0:x1+1])&(fl[y0:y1+1,x0:x1+1]>82)
        mask=ndi.binary_closing(excess&region,structure=np.ones((2,2)))
        mask=ndi.binary_dilation(mask,iterations=1)&region
        # Never replace dark heads/wings, including dilation around a glyph touching them.
        protected=np.zeros_like(mask)
        for fig in geo['figures'].values():
            f=np.zeros_like(mask);f[fig[1]:fig[3]+1,fig[0]:fig[2]+1]=True
            protected|=f&(fl<45)
        mask&=~protected
        alpha=np.asarray(Image.fromarray(mask.astype('uint8')*255).filter(ImageFilter.GaussianBlur(.45)),float)/255
        alpha*=region&~protected
        replacement=matched.copy()
        # Harmonic diffusion outside the illustration, fixed at non-label neighbours.
        outside=mask&~inside
        if outside.any():
            _,idx=ndi.distance_transform_edt(mask,return_indices=True)
            diffusion=frame[idx[0],idx[1]].copy()
            for _ in range(120):
                avg=(np.roll(diffusion,1,0)+np.roll(diffusion,-1,0)+np.roll(diffusion,1,1)+np.roll(diffusion,-1,1))/4
                diffusion[outside]=avg[outside]
            replacement[~inside]=diffusion[~inside]
        first=result*(1-alpha[:,:,None])+replacement*alpha[:,:,None]
        # fix2: recover light antialiased stroke tails missed by the first luma
        # threshold. Only compact stroke components in the same padded box may
        # seed the second mask; long printed board lines cannot seed it.
        local_fl=fl[y0:y1+1,x0:x1+1];local_ml=ml[y0:y1+1,x0:x1+1]
        top_hat=local_fl-ndi.grey_opening(local_fl,size=(5,5))
        light=(top_hat>3)&(local_fl>32)&((local_fl-local_ml>-32)|~inside[y0:y1+1,x0:x1+1])
        components,n=ndi.label(light);strokes=np.zeros_like(light)
        for idx,sl in enumerate(ndi.find_objects(components),1):
            if sl is None:continue
            hh=sl[0].stop-sl[0].start;ww=sl[1].stop-sl[1].start
            pixels=components[sl]==idx
            if 2<=pixels.sum()<=260 and ww<=35 and hh<=22 and ww<=max(8,hh*7):
                strokes[sl]|=pixels
        # Full coverage of the first-pass core eliminates feathered glyph ghosts.
        # The small additional stroke mask restores only their lighter tails.
        # Include the faint dark AA fringe around the bright glyph strokes.
        # It is a glyph-shaped expansion, not a rectangle replacement.
        second=ndi.binary_dilation(mask,iterations=2)&region
        second[y0:y1+1,x0:x1+1]|=ndi.binary_dilation(strokes,iterations=1)
        second&=region&~protected
        second_alpha=np.asarray(Image.fromarray(second.astype('uint8')*255).filter(ImageFilter.GaussianBlur(.4)),float)/255
        second_alpha[second]=1;second_alpha*=region&~protected
        outside=second&~inside
        if outside.any():
            # Work locally, with fixed clean neighbours; exclude ALL stroke pixels
            # when seeding so a readable fragment is never diffused back in.
            localmask=second[y0:y1+1,x0:x1+1]
            patch=frame[y0:y1+1,x0:x1+1].copy()
            _,idx=ndi.distance_transform_edt(localmask,return_indices=True)
            diffusion=patch[idx[0],idx[1]].copy()
            for _ in range(180):
                avg=ndi.convolve(diffusion,np.array([[0,.25,0],[.25,0,.25],[0,.25,0]])[:,:,None],mode='nearest')
                diffusion[localmask]=avg[localmask]
            rep=replacement[y0:y1+1,x0:x1+1]
            off=~inside[y0:y1+1,x0:x1+1];rep[off]=diffusion[off]
        result=first*(1-second_alpha[:,:,None])+replacement*second_alpha[:,:,None]
        alpha=1-(1-alpha)*(1-second_alpha)
        union|=alpha>0
        crop_before=Image.fromarray(np.uint8(frame)).crop(box);crop_after=Image.fromarray(np.uint8(result)).crop(box)
        crop_mask=Image.fromarray(np.uint8(alpha*255)).convert('RGB').crop(box)
        crops.append((k,crop_before,crop_after,crop_mask))
        records.append({'fighter':k,'padded_box':box,'label_pixels_replaced':int(mask.sum()),
          'feather_pixels':int((alpha>0).sum()),'fit_residual_px':geo['fighter_fit_residual_px'][b.IDS.index(k)],
          'colour_fit_rms_rgb':rms,'colour_fit_rms':float(np.mean(rms)),'colour_fit_coefficients':coeff.tolist(),
          'threshold_luma_excess':threshold,'dark_figure_pixels_changed':int(np.count_nonzero(alpha[protected])),
          'outside_illustration_pixels':int(outside.sum()),
          'second_pass':{'stroke_luma_excess_min':-32,'top_hat_min':3,'core_opacity':1,
              'additional_mask_pixels':int((second&~mask).sum()),'replaced_pixels':int(second.sum()),
              'dark_figure_pixels_changed':int(np.count_nonzero(second_alpha[protected]))}})
    clean=Image.fromarray(np.uint8(np.rint(result))).convert('RGB');BG[board]=clean
    rowheight=max(im.height for _,im,_,_ in crops)*3+34; colwidth=max(im.width for _,im,_,_ in crops)*3+16
    sheet=Image.new('RGB',(colwidth*3,rowheight*6+44),b.rgb('card.navy')); d=ImageDraw.Draw(sheet)
    d.text((12,8),'До | После | Маска · ×3',font=b.font(24),fill=b.rgb('text.primary'))
    for i,(k,a,z,m) in enumerate(crops):
        y=44+i*rowheight;d.text((12,y),RU[k],font=b.font(14),fill=b.rgb('text.primary'))
        for j,im in enumerate([a,z,m]):sheet.paste(im.resize((im.width*3,im.height*3),Image.Resampling.NEAREST),(j*colwidth+8,y+24))
    output(b,b.DERIVED/f'HB-44-label-erase-{board}-x3.png',sheet)
    actual_changed=np.any(np.uint8(frame)!=np.array(clean),axis=-1)
    ERASE[board]={'boxes':records,'changed_outside_padded_boxes':int((actual_changed&~union).sum()),
      'method':'bilinear homography; 0.48px softening; robust linear RGB ring fit; first brightness mask; second compact light-stroke pass and full-opacity glyph core; feather outside core; harmonic diffusion outside illustration',
      'visual_review':'pending'}


def masks(b,board,w,h,state):
    ms=b.masks(board,w,h)
    # Polygonal space masks projected from topology, rather than screen-space guesses.
    full=Image.new('1',(1920,1080)); choice=Image.new('1',(1920,1080)); selected=[]
    for im in SPACE_MASKS[board].values():full=Image.fromarray(np.array(full)|np.array(im))
    topo=TOPO[board]; byid={sp['id']:sp for sp in topo['spaces']}
    positions={k:next(sp['id'] for sp in topo['spaces'] if [sp['x'],sp['y']]==pos) for k,pos in GEO[board]['positions'].items()}
    if state.get('mode')=='attack':selected=[positions['medusa'],positions['merlin']]
    elif state.get('mode')=='selection' and state.get('plate')=='medusa':
        start=positions['medusa']; seen={start};front={start}
        for _ in range(3):
            front={v for u in front for v in byid[u]['links']}-seen;seen|=front
        # Traversal uses topology edges; occupied endpoints cannot be selected.
        selected=sorted(seen-set(positions.values()))
    for k in selected:choice=Image.fromarray(np.array(choice)|np.array(SPACE_MASKS[board][k]))
    ms['spaces']=full.resize((w,h),Image.Resampling.NEAREST)
    ms['choice']=choice.resize((w,h),Image.Resampling.NEAREST)
    seam=Image.new('1',(w,h));d=ImageDraw.Draw(seam)
    for x0,y0,x1,y1 in GEO[board]['seams']:d.line([(x0*w/1920,y0*h/1080),(x1*w/1920,y1*h/1080)],fill=1,width=max(2,round(4*w/1920)))
    ms['seams']=seam
    return ms,selected


def plate(b,c,actor,hp,key,mode,xy,lang='ru'):
    s=c.scale;x,y=xy;c.panel([x,y,x+268*s,y+144*s],'plate.'+mode,rad=6,onboard=True)
    idx=0 if lang=='ru' else 1
    c.text((x+16*s,y+14*s),(RU if idx==0 else EN)[key],24)
    role='hero' if actor['hero'] else 'sidekick'; attack='ranged' if actor['attack']=='range' else 'melee'
    c.text((x+16*s,y+50*s),STRINGS['hud.plate.role.'+role+'_'+attack][idx],14,'text.secondary')
    c.text((x+16*s,y+82*s),f"{hp}/{actor['startHealth']}",14)
    c.chip((x+85*s,y+91*s),actor['team'])
    c.text((x+105*s,y+83*s),STRINGS['hud.plate.side.'+('own' if actor['team']==1 else 'opponent')][idx])
    if mode=='attack':
        d=ImageDraw.Draw(c.im);d.rounded_rectangle([x+16*s,y+111*s,x+98*s,y+135*s],radius=4*s,fill=b.rgb('state.pending')+(255,))
        c.text((x+57*s,y+123*s),STRINGS['hud.plate.target'][idx],14,'card.glyph',center=True)
    if mode=='selection':
        d=ImageDraw.Draw(c.im)
        for xx,yy,sgx,sgy in [(x,y,1,1),(x+268*s,y,-1,1),(x,y+144*s,1,-1),(x+268*s,y+144*s,-1,-1)]:
            d.line([(xx+sgx*4*s,yy+sgy*12*s),(xx+sgx*4*s,yy+sgy*4*s),(xx+sgx*12*s,yy+sgy*4*s)],fill=b.rgb('card.glyph')+(255,),width=max(1,round(2*s)))


def place_plate(b,board,key,w,h,s,ms,panels):
    cache=(board,key,w,h,s,hash(np.asarray(ms['choice']).tobytes()))
    if cache in PLATE_CACHE:return PLATE_CACHE[cache]
    f=np.array(GEO[board]['figures'][key])*np.array([w/1920,h/1080,w/1920,h/1080]);pw=268*s;ph=144*s
    # Priority above / below / side. Search ALL legal offsets and choose the nearest
    # edge-to-figure distance within the first feasible direction; no screen-top band.
    obstacles=ms['figures'].copy(); oa=np.asarray(obstacles).copy()|np.asarray(ms['choice'])
    for p in panels:oa|=np.asarray(p['mask'])
    oa=ndi.binary_dilation(oa,iterations=math.ceil(s))
    # Summed area table makes exhaustive integer placement fast and deterministic.
    sat=np.pad(oa.astype(np.int32),((1,0),(1,0))).cumsum(0).cumsum(1)
    gx,gy=(f[0]+f[2])/2,(f[1]+f[3])/2
    distant=[]
    for rank,direction in enumerate(['above','below','beside']):
        legal=[]
        for y in range(8,h-math.ceil(ph)-8):
            if direction=='above' and y+ph>f[1]-3:continue
            if direction=='below' and y<f[3]+3:continue
            if direction=='beside' and (y+ph<f[1] or y>f[3]):continue
            xs=np.arange(8,w-math.ceil(pw)-8);x1=xs+math.ceil(pw)+1;y1=y+math.ceil(ph)+1
            collisions=sat[y1,x1]-sat[y,x1]-sat[y1,xs]+sat[y,xs]
            ok=collisions==0
            if direction=='beside':ok&=(xs+pw<=f[0]-3)|(xs>=f[2]+3)
            candidates=xs[ok]
            if not candidates.size:continue
            # Edge distance is primary; alignment to figure centre breaks ties.
            dx=np.maximum(np.maximum(f[0]-(candidates+pw),candidates-f[2]),0)
            dy=max(f[1]-(y+ph),y-f[3],0)
            dist=np.hypot(dx,dy); align=abs(candidates+pw/2-gx)+abs(y+ph/2-gy)
            order=np.lexsort((align,dist));i=order[0]
            legal.append((float(dist[i]),float(align[i]),int(candidates[i]),y))
        if legal:
            distance,_,x,y=min(legal)
            result=([x,y],{'direction':direction,'edge_distance_px':distance,'edge_distance_su':distance/s,'search_step_px':1})
            if distance<=24*s:
                PLATE_CACHE[cache]=result
                return result
            # A remote above-field plate recreates the explicitly forbidden top
            # band. If the local above position is blocked, the fallback is below
            # or genuinely beside the figure, with a leader when needed.
            if direction!='above':distant.append((distance,rank,result))
    if distant:
        result=min(distant,key=lambda entry:entry[:2])[2]
        PLATE_CACHE[cache]=result
        return result
    raise RuntimeError('No legal adjacent plate '+board+' '+key)


def number(b,c,value,xy,heal=False):
    x,y=xy;s=c.scale;c.panel([x-28*s,y-18*s,x+28*s,y+18*s],'heal' if heal else 'damage',8,True)
    c.text((x,y),value,24,'fx.heal' if heal else 'damage.text',True)


def number_anchor(b,board,key,w,h,s,ms,panels):
    x,y=GEO[board]['bases'][key];fy=GEO[board]['figures'][key][1];cx=x*w/1920;cy=fy*h/1080-24*s
    for i in range(100):
        for dx in ([0] if i==0 else [-i*4*s,i*4*s]):
            bx=[cx+dx-29*s,cy-43*s,cx+dx+29*s,cy+19*s]
            crop=[math.floor(bx[0]),math.floor(bx[1]),math.ceil(bx[2])+1,math.ceil(bx[3])+1]
            if min(crop)<0 or crop[2]>=w:continue
            if ms['figures'].crop(crop).getbbox():continue
            if any(p['mask'].crop(crop).getbbox() for p in panels):continue
            return cx+dx,cy
    raise RuntimeError('No number trajectory '+board+' '+key)


def states(b):
    out=[{'id':'tags-start','health':'start'},{'id':'tags-run-I','health':'run'}]
    for k in b.IDS:out.append({'id':'hover-'+k,'plate':k,'mode':'hover','health':'run'})
    for k in ['medusa','arthur']:out.append({'id':'selection-'+k,'plate':k,'mode':'selection','health':'run'})
    out.append({'id':'attack-medusa','plate':'medusa','mode':'attack','target':'medusa','attacker':'merlin','health':'run'})
    for t in [0,300,600,900,960]:out.append({'id':f'damage-{t:03d}ms','damage':t,'health':'run','damage_target':'medusa','attacker':'merlin'})
    for t in [0,300,600,700]:out.append({'id':f'heal-example-{t:03d}ms','heal':t,'health':'example','heal_target':'arthur'})
    for t in [0,300,510]:out.append({'id':f'reduced-damage-{t:03d}ms','damage':t,'reduced':True,'health':'run','damage_target':'medusa','attacker':'merlin'})
    out.extend([{'id':'reduced-heal-example','heal':300,'reduced':True,'health':'example','heal_target':'arthur'},
      {'id':'reduced-target','plate':'medusa','mode':'attack','target':'medusa','attacker':'merlin','reduced':True,'health':'run'}])
    return out


def render(b,board,state,config,actors,run,overlay=False):
    res,ui,w,h,dpi,app=config;s=dpi*app;bg=Image.new('RGB',(w,h),b.rgb('card.navy')) if overlay else BG[board].resize((w,h),Image.Resampling.LANCZOS)
    c=b.Canvas(bg,s);ms,selected=masks(b,board,w,h,state);existing=[];anchors={}
    if overlay:
        d=ImageDraw.Draw(c.im)
        for k,mask in SPACE_MASKS[board].items():
            a=np.array(mask.resize((w,h),Image.Resampling.NEAREST));edge=a&~ndi.binary_erosion(a)
            pixels=np.array(c.im);pixels[edge]=b.rgb('text.secondary')+(255,);c.im=Image.fromarray(pixels)
        pixels=np.array(c.im);pixels[np.array(ms['choice'])]=b.rgb('state.pending')+(255,);c.im=Image.fromarray(pixels)
        d=ImageDraw.Draw(c.im)
        for k,f in GEO[board]['figures'].items():d.rectangle([f[0]*w/1920,f[1]*h/1080,f[2]*w/1920,f[3]*h/1080],outline=b.rgb('card.cream')+(255,))
        lx=w-236*s
        c.text((lx,16),'HB-44',24)
        c.text((lx,50*s),f'{board} · {res} · {ui}%',14,'text.secondary')
        # Space IDs live in geometry/layout JSON; keeping them off the sheet avoids
        # a long diagnostic line under a large adjacent plate.
        c.text((lx,74*s),state['id'],14,'text.secondary')
        c.text((lx,98*s),'Клетки выбора: '+str(len(selected)),14,'text.secondary')
    hp={k:v['startHealth'] for k,v in actors.items()}
    if state['health']!='start':hp.update(run)
    if state['health']=='example':hp['arthur']=4 if state.get('heal')==0 else 8
    for k in b.IDS:
        xy=b.place_tag(board,k,w,h,s,ms,existing);anchors[k]=list(xy)
        f=GEO[board]['figures'][k];bx,by=GEO[board]['bases'][k]
        if abs(xy[0]-bx*w/1920)>24*s or xy[1]-(f[3]+7)*h/1080>12*s:
            width=b.tag_layout(actors[k],s)['width_su']*s
            end=(min(max(bx*w/1920,xy[0]-width/2),xy[0]+width/2),xy[1])
            ImageDraw.Draw(c.im).line([(bx*w/1920,(f[3]+2)*h/1080),end],fill=b.rgb('card.cream')+(255,),width=max(1,round(s)))
            anchors[k+'_leader']=[list(end)]
        b.tag(c,actors[k],hp[k],xy,k)
    plate_position=None
    if state.get('plate'):
        k=state['plate'];xy,plate_position=place_plate(b,board,k,w,h,s,ms,c.panels)
        anchors['plate']=xy
        if plate_position['leader_required']:
            f=np.array(GEO[board]['figures'][k])*[w/1920,h/1080,w/1920,h/1080];centre=((f[0]+f[2])/2,(f[1]+f[3])/2)
            end=(min(max(centre[0],xy[0]),xy[0]+268*s),min(max(centre[1],xy[1]),xy[1]+144*s))
            start=tuple(np.array(GEO[board]['bases'][k])*[w/1920,h/1080])
            # Leader lives below figure/tag UI. Occlusion preserves the HP glyph
            # when a legal distant plate lies beyond the actor's under-base tag.
            plate_position['leader_occluded_pixels']=leader(c,ms,c.panels,start,end)
            plate_position['leader_style']={'cream_su':1,'keyline_su':1,'opacity':1}
            plate_position['leader']=[list(start),list(end)]
        plate(b,c,actors[k],hp[k],k,state['mode'],xy)
    if state.get('target'):
        k=state['target'];x,y=GEO[board]['bases'][k];f=GEO[board]['figures'][k];sz=24
        ix=round((f[2]+5)*w/1920);iy=round((f[1]+f[3])/2*h/1080-sz/2)
        icon=Image.open(b.ICON).convert('RGBA').resize((sz,sz),Image.Resampling.LANCZOS);c.im.alpha_composite(icon,(ix,iy));anchors['target_token']=[ix,iy]
        d=ImageDraw.Draw(c.im);cx=x*w/1920;cy=y*h/1080;rx=32*w/1920;ry=22*h/1080
        for a in [20,110,200,290]:
            d.arc([cx-rx-1,cy-ry-1,cx+rx+1,cy+ry+1],a,a+40,fill=b.rgb('mark.keyline')+(255,),width=3)
            d.arc([cx-rx,cy-ry,cx+rx,cy+ry],a,a+40,fill=b.rgb('card.cream')+(255,),width=1)
    number_attribution=None
    if 'damage' in state:
        t=state['damage']; reduced=state.get('reduced',False)
        visible=60<=t<(510 if reduced else 960)
        x,y=number_anchor(b,board,'medusa',w,h,s,ms,c.panels);rise=0 if reduced else 24*max(0,t-60)/900
        number_attribution=number_check(board,'medusa',(x,y),rise,s,w,h,visible)
        if visible:
            anchors['number_trajectory']=[x,y];number(b,c,'−1',(x,y-rise*s))
    if 'heal' in state:
        t=state['heal'];reduced=state.get('reduced',False)
        visible=t<700
        x,y=number_anchor(b,board,'arthur',w,h,s,ms,c.panels);rise=0 if reduced else 24*t/700
        number_attribution=number_check(board,'arthur',(x,y),rise,s,w,h,visible)
        if visible:
            anchors['number_trajectory']=[x,y];number(b,c,'+4',(x,y-rise*s),True)
            example(c,(x,y-rise*s))
    measurements=[]
    for p in c.panels:
        measurements.append({k:v for k,v in p.items() if k!='mask'}|{'overlap_px2':{n:b.overlap(p['mask'],m) for n,m in ms.items()},
          'other_panel_overlap_px2':max([b.overlap(p['mask'],q['mask']) for q in c.panels if q is not p],default=0),
          'team_chip_su':24 if p['kind'].startswith('tag.') else None,
          'text_contrast':[{'text':t['text'],'ratio':t['background_worst_contrast']} for t in c.texts if t['panel']==p['kind']]})
    record={'file':f'HB-44-{board}-{state["id"]}-{res}-{ui}.png','board':board,'state':state,'resolution':[w,h],
      'device_scale':dpi,'ui_scale':app,'su_to_px':s,'anchors_px':anchors,'panels':measurements,'text':c.texts,
      'choice_space_ids':selected,'plate_position':plate_position,'number_attribution':number_attribution,'language':'ru'}
    return c.im,record


def components(b,config,actors,run,lang):
    res,ui,w,h,dpi,app=config;s=dpi*app;c=b.Canvas(Image.new('RGB',(w,h),b.rgb('card.navy')),s)
    c.text((24,18),'HB-44 · '+('Компоненты · RU' if lang=='ru' else 'Components · EN'),24)
    c.text((24,54),f'{res} · {ui}% · '+('чип команды 24 su' if lang=='ru' else 'team chip 24 su'),14,'text.secondary')
    # Two rows of three plates fit each working canvas without mixing cultures.
    for i,k in enumerate(b.IDS):
        x=24+(i%3)*284*s;y=96+(i//3)*224*s
        b.tag(c,actors[k],run.get(k,actors[k]['startHealth']),(x+134*s,y),k)
        plate(b,c,actors[k],run.get(k,actors[k]['startHealth']),k,'attack' if k=='medusa' else 'hover',(x,y+54*s),lang)
    number(b,c,'−1',(100,600*s));number(b,c,'+4',(220,600*s),True)
    example(c,(220,600*s),lang)
    return c.im


def motion(b,config):
    res,ui,w,h,dpi,app=config;s=dpi*app;c=b.Canvas(Image.new('RGB',(w,h),b.rgb('card.navy')),s)
    c.text((24,20),'HB-44 · Урон и лечение',24)
    c.text((24,62),'Урон Медузе · контакт +60 мс · подъём 24 su за 900 мс',14)
    for i,t in enumerate([0,300,600,900]):
        x=150+i*210*s
        if t>=60:number(b,c,'−1',(x,180*s-24*s*(t-60)/900))
        c.text((x,235*s),str(t)+' мс',14,center=True)
    c.text((24,290*s),'Уменьшенное движение · без подъёма · 450 мс после старта',14)
    for i,t in enumerate([0,300,510]):
        x=150+i*210*s
        if 60<=t<510:number(b,c,'−1',(x,350*s))
        c.text((x,400*s),str(t)+' мс',14,center=True)
    c.text((24,450*s),'Лечение Артура · пример · +4 · 700 мс',14)
    for i,t in enumerate([0,300,600,700]):
        x=150+i*210*s
        if t<700:
            number(b,c,'+4',(x,520*s-24*s*t/700),True)
            example(c,(x,520*s-24*s*t/700))
        c.text((x,580*s),str(t)+' мс',14,center=True)
    return c.im


def native_sheet(b,files,path,title):
    imgs=[Image.open(b.DERIVED/f).convert('RGB') for f in files];w,h=imgs[0].size
    out=Image.new('RGB',(w*2,h*math.ceil(len(imgs)/2)+54),b.rgb('card.navy'));d=ImageDraw.Draw(out)
    d.text((16,12),title,font=b.font(24),fill=b.rgb('text.primary'))
    for i,im in enumerate(imgs):out.paste(im,((i%2)*w,54+(i//2)*h))
    output(b,path,out)


def inventory(b):
    files={};allowed=[b.PKG.relative_to(b.ROOT).as_posix()+'/',b.DERIVED.relative_to(b.ROOT).as_posix()+'/']
    for folder,dirs,names in os.walk(b.ROOT):
        if Path(folder)==b.ROOT:dirs[:]=[d for d in dirs if d not in ['.git','unreal']]
        dirs[:]=[d for d in dirs if d!='.git']
        for n in names:
            p=Path(folder)/n;rel=p.relative_to(b.ROOT).as_posix()
            if any(rel.startswith(a) for a in allowed):continue
            try:st=p.stat();files[rel]=[st.st_size,st.st_mtime_ns]
            except OSError:pass
    return files


def manifests(b):
    baseline=json.loads((b.PKG/'source-hashes-before.json').read_text(encoding='utf-8'))['inputs'];outputs={}
    for folder in [b.PKG,b.DERIVED]:
        for p in sorted(folder.rglob('*')):
            if p.is_file() and p.name not in ['manifest.json','manifest-sha256.json']:
                outputs[p.relative_to(b.ROOT).as_posix()]={'sha256':b.sha(p),'bytes':p.stat().st_size}
    b.save_json(b.PKG/'manifest.json',{'schema':1,'task':'HB-44.fix2','inputs':baseline,'outputs':outputs,
      'excludes':['manifest.json','manifest-sha256.json'],'facts':json.loads((b.PKG/'source-data.json').read_text(encoding='utf-8'))})
    b.save_json(b.PKG/'manifest-sha256.json',{'schema':1,'excludes_self':True,'files':{
      p.relative_to(b.PKG).as_posix():{'sha256':b.sha(p),'bytes':p.stat().st_size}
      for p in sorted(b.PKG.rglob('*')) if p.is_file() and p.name!='manifest-sha256.json'}})


def verify(b,records,provenance):
    baseline=json.loads((b.PKG/'source-hashes-before.json').read_text(encoding='utf-8'))['inputs']
    changed=[p for p,v in baseline.items() if not (b.ROOT/p).is_file() or b.sha(b.ROOT/p)!=v['sha256']]
    review_path=b.PKG/'visual-review.json'
    visual=json.loads(review_path.read_text(encoding='utf-8')) if review_path.exists() else {}
    if visual.get('task')=='HB-44.fix2':
        for board in b.BOARDS:
            proof=visual.get('label_erase',{}).get(board,{})
            sheet=b.DERIVED/f'HB-44-label-erase-{board}-x3.png'
            ERASE[board]['visual_review']={**proof,'passed':bool(proof.get('passed')) and proof.get('sha256')==b.sha(sheet)}
        b.save_json(b.PKG/'label-erase-measurements.json',ERASE)
    iconbefore={p for p in baseline if p.startswith('art/imagegen/hud-icons-v3/')}
    iconafter={p.relative_to(b.ROOT).as_posix() for p in (b.ROOT/'art/imagegen/hud-icons-v3').rglob('*') if p.is_file()}
    audit=b.DERIVED/'audit'
    before=json.loads((audit/'scope-audit-fix2-before.json').read_text(encoding='utf-8'))['files'];after=inventory(b)
    observed_outside=sorted(p for p in before.keys()|after.keys() if before.get(p)!=after.get(p))
    # Concurrent sessions share this checkout. Global diffs are retained verbatim,
    # never reset or overwritten. Attribute our own writes using the scoped output
    # registry and explicit metadata destinations, rather than claiming a quiet repo.
    written=list(GENERATED)
    written += [b.PKG/n for n in ['README.md','verification.json','manifest.json','manifest-sha256.json']]
    written += [audit/'scope-audit-fix2-before.json',audit/'scope-audit-fix2-after.json',audit/'scope-audit-before.json',audit/'scope-audit-after.json']
    outside=sorted(str(p) for p in written if not (p.resolve().is_relative_to(b.PKG.resolve()) or p.resolve().is_relative_to(b.DERIVED.resolve())))
    b.save_json(audit/'scope-audit-fix2-after.json',{'excluded_untouched':['.git/','unreal/'],'files':after})
    audit_records=[{'path':p.relative_to(b.ROOT).as_posix(),'sha256':b.sha(p),'bytes':p.stat().st_size,
                   'file_count':len(json.loads(p.read_text(encoding='utf-8'))['files'])}
                   for p in sorted(audit.glob('scope-audit*.json'))]
    panels=[p for r in records for p in r['panels']];texts=[t for r in records for t in r['text']]
    tag=[p for p in panels if p['kind'].startswith('tag.')];plates=[p for p in panels if p['kind'].startswith('plate.')]
    fonts=min(t['font_px'] for r in records if r['resolution'][1]==720 for t in r['text'])
    digit=min(t['ink_height_px'] for r in records if r['resolution'][1]==720 for t in r['text'] if t['text'] in ['1','2','3'])
    damage=min(t['background_worst_contrast'] for t in texts if t['text']=='−1')
    contrast=min(t['background_worst_contrast'] for t in texts if t['background_worst_contrast'] is not None)
    digitchecks=json.loads((b.PKG/'digit-checks.json').read_text(encoding='utf-8'))
    distinct=all(n>0 for x in digitchecks for n in x['pair_differing_px'].values())
    chipmeasurements=[]
    for r in records:
        im=Image.open(b.DERIVED/r['file']).convert('RGB');s=r['su_to_px']
        for p in r['panels']:
            if not p['kind'].startswith('tag.'):continue
            key=p['kind'].split('.',1)[1];team=provenance['actors'][key]['team']
            x,y=p['box'][:2];cx=x+24*s;cy=y+20*s;rad=12*s
            crop=[math.floor(cx-rad)-1,math.floor(cy-rad)-1,math.ceil(cx+rad)+2,math.ceil(cy+rad)+2]
            ink=np.all(np.asarray(im.crop(crop))==b.rgb(f'team.p{team}.screen'),axis=-1)
            ys,xs=np.nonzero(ink)
            extent=[int(xs.max()-xs.min()+1),int(ys.max()-ys.min()+1)] if len(xs) else [0,0]
            chipmeasurements.append({'file':r['file'],'fighter':key,'team':team,'shape':'circle' if team==1 else 'hexagon',
              'nominal_su':24,'nominal_px':24*s,'opaque_ink_extent_px':extent,'opaque_token_pixels':int(ink.sum()),
              'passed':bool(ink.any()) and max(extent)>=math.floor(24*s)})
    exports=[];grayok=True
    expected_sizes={r['file']:tuple(r['resolution']) for r in records}
    sizeok=True
    for folder in [b.PKG/'comparison',b.DERIVED]:
        for p in sorted(folder.glob('*.png')):
            im=Image.open(p);g=None
            if p.name in expected_sizes:sizeok&=im.size==expected_sizes[p.name]
            if not p.stem.endswith('-gray'):
                gp=p.with_name(p.stem+'-gray.png');g=Image.open(gp)
                grayok&=np.array_equal(np.asarray(b.gray(im)),np.asarray(g.convert('RGB')))
            exports.append({'path':p.relative_to(b.ROOT).as_posix(),'size':list(im.size),'mode':im.mode,
              'margin_px':0,'touches_edge':True,'note':'Full-frame composite or sheet canvas, not an isolated asset','rec709_partner':None if g is None else grayok})
    platechoice=max(p['overlap_px2']['choice'] for p in plates)
    checks={'inputs_unchanged':not changed and iconbefore==iconafter,'snapshot_matches_source':b.sha(b.SNAPSHOT)==b.sha(b.ROOT/'art/imagegen/hud-icons-v3/_tools/draw_icons.py'),
      'tag_figure_clearance':max(p['overlap_px2']['figures'] for p in tag)==0,
      'tag_seam_clearance':max(p['overlap_px2']['seams'] for p in tag)==0,
      'all_panel_figure_clearance':max(p['overlap_px2']['figures'] for p in panels)==0,
      'panels_do_not_overlap':max(p['other_panel_overlap_px2'] for p in panels)==0,
      'plate_choice_clearance':platechoice==0,'plate_tag_clearance':max(p['other_panel_overlap_px2'] for p in plates)==0,
      'tag_text_720_min_10_5':fonts>=10.5,'digit_720_min_10':digit>=10,'damage_contrast_min_4_5':damage>=4.5,
      'all_panel_text_contrast_min_4_5':contrast>=4.5,'gray_partners':bool(grayok),'gray_digits_distinct':distinct,
      'team_chip_24_su':all(p['team_chip_su']==24 for p in tag),'outside_folder_empty':not outside,
      'ru_only':all(not any(v in t['text'] for v in ['TARGET','уточнить','example','Harpies','Medusa','King Arthur','Merlin']) for t in texts),
      'label_erase_scope':all(v['changed_outside_padded_boxes']==0 for v in ERASE.values()),
      'mockup_dimensions':bool(sizeok) and all((b.DERIVED/name).is_file() for name in expected_sizes)}
    checks['team_chip_raster_size']=all(c['passed'] for c in chipmeasurements)
    number_frames=[{'file':r['file'],'phase_ms':r['state'].get('damage',r['state'].get('heal')),
                   'reduced_motion':bool(r['state'].get('reduced')),**r['number_attribution']}
                   for r in records if r.get('number_attribution')]
    plate_frames=[{'file':r['file'],**r['plate_position']} for r in records if r.get('plate_position')]
    example_frames=[]
    for r in records:
        for label in [p for p in r['panels'] if p['kind']=='example.label']:
            capsule=next(p for p in r['panels'] if p['kind']=='heal');s=r['su_to_px']
            text=next(t for t in r['text'] if t['panel']=='example.label')
            tw=b.font(14*s).getbbox(text['text']);tw=tw[2]-tw[0]
            a=label['box'];z=capsule['box']
            example_frames.append({'file':r['file'],'gap_su':(a[0]-z[2])/s,
              'height_su':(a[3]-a[1])/s,'width_su':(a[2]-a[0])/s,'text_width_px':tw,
              'vertical_center_error_px':abs((a[1]+a[3])/2-(text['xy'][1]+text['ink_height_px']/2)),
              'passed':abs(a[0]-z[2]-4*s)<1e-6 and abs(a[1]-z[1])<1e-6 and abs(a[3]-z[3])<1e-6
                       and abs(a[2]-a[0]-tw-24*s)<1e-6})
    checks['number_nearest_own_figure']=bool(number_frames) and all(r['passed'] for r in number_frames)
    checks['plate_attribution']=all(p['nearest_figure']==p['target'] or bool(p.get('leader')) for p in plate_frames)
    checks['example_attached']=bool(example_frames) and all(r['passed'] for r in example_frames)
    checks['tag_interior_gaps']=all(all(g>=6 for g in l['gaps_su'].values()) for geo in GEO.values() for l in geo['tag_interior'].values())
    checks['tag_interior_text_padding']=all(p.get('interior',{}).get('hp_text_right_padding_su',0)>=12-1e-6 for p in tag)
    acceptance={
      'tag >= 10.5 px at 720p':{'passed':fonts>=10.5,'measured':fonts,'expected':'>=10.5 px','note':'Font size at device 0.75, UI 150%'},
      'Harpy digit >= 10 px':{'passed':digit>=10,'measured':digit,'expected':'>=10 px','note':'Measured glyph ink cap'},
      'damage capsule >= 4.5:1':{'passed':damage>=4.5,'measured':damage,'expected':'>=4.5:1','note':'WCAG actual composited panel under glyph core'},
      'the plate crosses no reachable space (0 px^2)':{'passed':platechoice==0,'measured':platechoice,'expected':'0 px²','note':'Hover none; own Medusa topology move3 unoccupied endpoints; Arthur inspect none; attack Medusa/Merlin spaces'},
      'Harpies 1-3 differ in gray':{'passed':distinct,'measured':digitchecks,'expected':'Every pair has different pixels','note':'Rec.709, runtime digit shapes'}}
    prompt=(b.ROOT/'docs/game-design/visual/06-tasks/prompts/HB-44.codex.md').read_text(encoding='utf-8')
    expected=dict(b.EXPECTED)
    for path,digest in re.findall(r'\| `([^`]+)` \| file \| \d+ \| ([0-9a-f]{64}) \|',prompt):expected[path]=digest
    mismatches=[{'path':p,'expected':val,'actual':baseline[p]['sha256']} for p,val in expected.items() if p in baseline and not baseline[p]['sha256'].startswith(val)]
    graypairs=[]
    for board in b.BOARDS:
        for config in b.CONFIGS:
            res,ui,*_=config
            for a,z in [('tags-start','tags-run-I'),('hover-medusa','selection-medusa'),('hover-medusa','attack-medusa'),('damage-000ms','damage-300ms'),('damage-300ms','damage-900ms'),('heal-example-000ms','heal-example-300ms')]:
                aa=np.array(Image.open(b.DERIVED/f'HB-44-{board}-{a}-{res}-{ui}-gray.png').convert('L'),dtype=np.int16)
                zz=np.array(Image.open(b.DERIVED/f'HB-44-{board}-{z}-{res}-{ui}-gray.png').convert('L'),dtype=np.int16)
                count=int(np.count_nonzero(abs(aa-zz)>=20));graypairs.append({'board':board,'resolution':res,'scale':ui,'pair':[a,z],'luma_delta_20_pixels':count,'passed':count>0})
    checks['gray_state_pairs']=all(p['passed'] for p in graypairs)
    v={'task':'HB-44.fix2','status':'предложено','source_unchanged':{'passed':checks['inputs_unchanged'],'checked':len(baseline),'changed':changed,'icon_tree_added':sorted(iconafter-iconbefore),'icon_tree_removed':sorted(iconbefore-iconafter)},
      'exports':exports,'palette':{'passed':True,'literal_tokens':b.TOKENS,'out_of_palette_opaque_core_fraction':0,
        'method':'Procedural fills/text receive exact token RGB; body/edge opacity, AA and board pixels excluded. Accepted target PNG reused as-is; no recolouring. This is construction proof, not a palette test of the painted background.'},
      'gray':{'passed':bool(grayok) and distinct and checks['gray_state_pairs'],'method':'Exact Rec.709 partners of every generated sheet/frame; digit shape pairs; state pixel difference >=20 luma','digit_checks':digitchecks,'state_pairs':graypairs},
      'sizes':{'passed':checks['mockup_dimensions'],'configs':b.CONFIGS,'native_ui_render':True,'master_downscaled':False,'background_resized':True},
      'outside_folder':outside,'audit_files':audit_records,'outside_folder_audit':{'before_count':len(before),'after_count':len(after),
        'observed_changes_other_sessions':observed_outside,'observed_change_count':len(observed_outside),
        'scoped_outputs':[p.relative_to(b.ROOT).as_posix() for p in written],
        'method':'Full path/size/mtime_ns before/after inventory. Concurrent external changes retained here separately; outside_folder lists this build\'s out-of-scope writes (scoped output registry + explicit metadata destinations). Initial manual commands wrote only in PKG. .git/unreal never opened.'},
      'acceptance':acceptance,'label_erase':ERASE,'checks':checks,'expected_hash_mismatches':mismatches,
      'fix2':{'number_nearest_figure_per_frame':number_frames,'plate_placement_per_frame':plate_frames,
              'example_per_frame':example_frames,'tag_interior':{k:v['tag_interior'] for k,v in GEO.items()}},
      'measurements':{'tag_figure_overlap_px2':max(p['overlap_px2']['figures'] for p in tag),'plate_choice_overlap_px2':platechoice,
        'smallest_text_font_px_at_720':fonts,'harpy_digit_min_ink_px_at_720':digit,'damage_min_contrast':damage,'all_text_min_contrast':contrast,
        'all_panels_all_spaces_max_overlap_px2':max(p['overlap_px2']['spaces'] for p in panels),
        'team_chip_measurements':chipmeasurements,
        'mask_method':'Trace anchors/labels; trace figure boxes plus remeasured conservative full wing/cape/base-rim envelope (trace box retained separately); 96-vertex topology space polygons through fitted homography; inter-space edge corridors 4px; panels include keyline. Per-frame details in layout-measurements.json.'},
      'source_data':provenance,'limitations':[{'id':'ALL-PANELS-ALL-SPACES','passed':False,'note':'Under-base tags may cover part of their occupied space; zero-space acceptance applies to the plate choice masks. No runtime/editor validation is claimed.'},
        {'id':'STRICT-UNDER-BASE','passed':False,'note':'Crowded figures / seam clearance require lateral offsets for some tags; 1su leaders preserve attribution.'},
        {'id':'720-100','passed':False,'note':'720p UI100 is not a required output; cap10su at device .75 would be 7.5px.'}],
      'generation':'none','git_commands':'none','unreal_access':'none',
      'network':{'build_and_verification':'none','initial_skill_command':'npx openskills read canvas-design attempted registry resolution, failed EPERM; local SKILL.md used instead; no installation succeeded'}}
    b.save_json(b.PKG/'verification.json',v);manifests(b)
    print(json.dumps({'mockups':len(records),'checks':checks,'min_damage_contrast':damage,'smallest_font_720':fonts,'digit_720':digit},ensure_ascii=False))
    assert all(checks.values()),checks
    return v


def readme(b,v):
    review=json.loads((b.PKG/'review-original.json').read_text(encoding='utf-8'))['section'];m=v['measurements']
    lines=['# HB-44 — слой над фигурами · fix2','', '**Статус: предложено.** Макет для ревью, без изменений клиента. Рекомендуется единственный вариант с чипом команды **24 su** (ВР-78); вариант 16 su удалён.','',
      '## Макеты и листы','',
      '- [Компоненты RU, 1080p](comparison/HB-44-components-ru-1920x1080-100.png) и [RU, 720p/150%](comparison/HB-44-components-ru-1280x720-150.png).',
      '- [Отдельный комплект EN](comparison/HB-44-components-en-1280x720-150.png): шесть имён, все роли, YOURS / OPPONENT, TARGET, example.',
      '- [Фазы урона и лечения](comparison/HB-44-motion-1280x720-150.png), включая уменьшенное движение.',
      '- В `comparison/` схемы каждого hover/selection/attack при двух размерах. Только на них показаны маски клеток выбора; исходной графики досок там нет.',
      '- [Состояния Marmoreal](../../../scraped-data/derived/hud-world-v1-codex/HB-44-marmoreal-states-sheet-1280x720-150.png), [Sarpedon](../../../scraped-data/derived/hud-world-v1-codex/HB-44-sarpedon-states-sheet-1280x720-150.png). Все индивидуальные кадры и серые пары — в той же derived-папке.',
      '- [Удаление подписей Marmoreal ×3](../../../scraped-data/derived/hud-world-v1-codex/HB-44-label-erase-marmoreal-x3.png), [Sarpedon ×3](../../../scraped-data/derived/hud-world-v1-codex/HB-44-label-erase-sarpedon-x3.png): строки — бойцы, колонки — до / после / маска.','',
      '- [Полные маски фигур Marmoreal ×3](../../../scraped-data/derived/hud-world-v1-codex/HB-44-figure-masks-marmoreal-x3.png) и [Sarpedon ×3](../../../scraped-data/derived/hud-world-v1-codex/HB-44-figure-masks-sarpedon-x3.png). Бирюзой показан исходный trace bbox, кремовым — полный консервативный конверт, включая крылья, плащи и края подставок. Листы показывают исходный кадр до ретуши.','',
      '## Данные и решения','',
      'Marmoreal — K1 с `marmoreal-concept-flag` (нарисованный задник), Sarpedon — K1 lit3d. Якоря фигур, подставок и старых подписей взяты из групп трассы 18.34.51 и 13.42.56 соответственно. Маски фигур пересмотрены по самому кадру: крылья гарпий выступают за proxy trace, добавлен консервативный запас 16 px по горизонтали; плащи и подставки Артура/Мерлина тоже включены. Исходные и полные bbox сохранены отдельно в geometry.json. Пространства — из topology.json с проекцией через гомографию. Все шесть фигур v2 остаются исходными.',
      'Номера следуют `sidekicks[]`: f-0-sk0 = 1, sk1 = 2, sk2 = 3. Marmoreal сверху вниз: 3, 1, 2; Sarpedon: 2 слева сверху, 1 справа, 3 слева снизу. Названия героев RU подтверждены строками 05-content-matrix.csv; «Гарпия N» — 02 §6.5 и 04 §6.2.',
      'Плашки 268×144 su: имя 24 su, роль 14 su, HP, команда и ЦЕЛЬ. Позиция — сначала над фигурой, затем под ней, затем сбоку. Исчерпывающий поиск с шагом 1 px требует, чтобы ближайший bbox был собственным бойцом. Если такого законного положения нет, ближайшее законное нижнее/боковое положение получает лидер к подставке. При расстоянии >24 su лидер также обязателен: кремовая линия 1 su, тёмный контур 1 su, полная непрозрачность. Линия скрывается только под фигурами и тегами. Дистанции до всех шести фигур и правило каждого кадра записаны в verification.json и layout-measurements.json. Плашки не перекрывают фигуры, теги или клетки выбора.',
      'Hover не резервирует клеток. Выбор своей Медузы резервирует клетки за 3 ребра топологии, исключая занятые конечные клетки; переход через своих гарпий допустим. Выбор Артура — осмотр. Атака резервирует клетки Медузы и Мерлина. «−1», жетон, дуги и ЦЕЛЬ относятся к Медузе, атакует Мерлин.',
      'Теги 136×40 su у Медузы/Артура, 122×40 у Мерлина, 144×40 у гарпий; радиус 8. Ряд: отступ 12, команда 24, промежуток 6, у гарпий диск 16 и промежуток 6, HP 40×4, промежуток 8, HP-текст 14, отступ не менее 12 su. Все элементы по центру высоты 20 su; точные интервалы и координаты — geometry.json. Лечение +4 — только «пример»: The Holy Grail устанавливает здоровье Артура в 8 из 4, название карты сохранено только в source-data/manifest. Подпись type.tag 14 примыкает справа к +4 через 4 su, высота 36 su, ширина текста +24 su. EN example имеет ту же геометрию на отдельном листе. Смешения языков в плашках нет.','',
      '## Ретушь исходного кадра','',
      'Разрешённая ретушь собственного UE-кадра выполнена только в дополненных на 4 px SHOT label boxes. Bilinear-гомография из шести world/screen пар; смягчение 0,48 px; устойчивый линейный RGB-fit на кольце. После первой маски яркости второй проход выделяет компактные светлые штрихи при пониженном пороге и заполняет ядро без прозрачности; feather остаётся снаружи ядра. Длинные линии доски не создают семена второй маски; за иллюстрацией — диффузия от соседей без текста. Тёмные пиксели фигур защищены. Исходные файлы не изменены. Для каждого бокса записаны координаты, число заменённых пикселей обоих проходов, остаток гомографии и RMS подгонки цвета.','',
      '## Предложенные ключи StringTable','', '| Ключ | RU | EN |','|---|---|---|']
    lines.extend('| '+k+' | '+ru+' | '+en+' |' for k,(ru,en) in STRINGS.items())
    lines += ['', 'Имена героев — данные, а не новые строки ST. Таблица `st-hud.csv` не изменялась.','',
      '## Проверки и ограничения','',
      f'Индивидуальных макетов: **{len(json.loads((b.PKG/"layout-measurements.json").read_text(encoding="utf-8")))}**. Фигуры / панели **0 px²**; клетки выбора / плашки **{m["plate_choice_overlap_px2"]} px²**. В 720p/150% минимальный кегль **{m["smallest_text_font_px_at_720"]} px**, цифра гарпии **{m["harpy_digit_min_ink_px_at_720"]} px**. Контраст урона минимум **{m["damage_min_contrast"]}:1**, всего текста **{m["all_text_min_contrast"]}:1**.',
      'Общее требование «все панели / все клетки = 0» не выполнено: теги под подставками перекрывают части занятых клеток. Это явно записано в verification.json. Проверка клиента/UMG не проводится в этой задаче. 720p/100% не заявлен: cap10 при device0.75 даёт 7,5px. Принятый action-attack-token используется без перекраски; его старые navy/rim — исключение из новой палитры по прямому требованию use as is.',
      'Полупрозрачное тело 0,92 и обод 0,45, антиалиасинг и исходная доска дают смешанные пиксели: palette проверяет исходные процедурные значения, а не цвета живописного фона. Все PNG имеют RGBA; серые партнёры — точный Rec.709. UI на каждом размере рисуется заново, уменьшается только фон. Для отдельных бледных подписей порог разности luma имеет отрицательный допуск к ошибке RGB-fit; значения не скрыты в label_erase. Локальное плавное поле остатка цвета выводится только из кольца вокруг бокса, чтобы не оставлять цветной контур букв.',
      'Хеши всех входов и дерева hud-icons-v3 проверены. Снимок draw_icons_v3_snapshot.py совпадает с оригиналом. Исторические описи scope-audit-before/after.json перенесены в scraped-data/derived/hud-world-v1-codex/audit/; там же отдельные описи fix2 до и после работы. verification.json хранит их пути, SHA256, размеры и число записей. .git и unreal исключены из обхода и не открывались. Записей этой задачи вне разрешённых папок: '+str(len(v['outside_folder']))+'. Другие сессии меняют общий checkout: '+str(v['outside_folder_audit']['observed_change_count'])+' внешних изменений сохранены отдельно в outside_folder_audit, без отката или подмены.',
      'Расхождения ожидаемых хешей: '+json.dumps(v['expected_hash_mismatches'],ensure_ascii=False)+'.',
      '', 'Для воспроизведения нужны уже установленные Python, Pillow, NumPy и SciPy, а также указанные в задании файлы Roboto из каталога шрифтов UE 5.8. Установки зависимостей не выполняются.',
      '', '```powershell','python art/imagegen/hud-world-v1-codex/_tools/build_hb44.py','python art/imagegen/hud-world-v1-codex/_tools/build_hb44.py --verify-only','```','',
      'Генерации нет; generation-records.json пуст, concepts/ пуст. Установок, сетевых запросов, Git-команд и доступа к Unreal при построении не было. Неудачный вызов локального навыка через npx до построения пытался разрешить openskills через registry и завершился EPERM; после него использован локальный SKILL.md.','',
      '## Доработка fix1 (2026-10-06)','',
      'Исправлены все девять пунктов корректирующего задания: фон Marmoreal, локальное удаление подписей, единый RU и отдельный EN, порядок гарпий по ID, урон Медузе, чип 24 su, соседние плашки с масками по состояниям, актуальная опись файлов и SHA256-manifest, переписанный README. Старые результаты, которые новая сборка не выпускает, удалены только в двух разрешённых папках. Историческое ревью ниже сохранено дословно.','',
      '## Доработка fix2 (2026-10-06)','',
      'Шесть исправлений: разнесён ряд тегов (промежутки 6/6/8 su); числа закреплены за Медузой/Артуром с подъёмом 24 su и проверкой ближайшего bbox во всех фазах, включая невидимые конечные; подпись пример/example прикреплена к +4 через 4 su; плашки требуют собственного ближайшего бойца или явного лидера 1+1 su; тяжёлые аудиты вынесены из пакета; второй проход убирает светлые хвосты старых подписей. Все индивидуальные кадры, компоненты, фазы, схемы и серые пары пересобраны.',
      f'Проверено фаз чисел: {len(v["fix2"]["number_nearest_figure_per_frame"])}; плашек: {len(v["fix2"]["plate_placement_per_frame"])}; прикреплённых подписей: {len(v["fix2"]["example_per_frame"])}. Тёмных пикселей фигур изменено: {sum(box["dark_figure_pixels_changed"] for er in v["label_erase"].values() for box in er["boxes"])}. Размер пакета, включая manifest-файлы: **{v.get("package_size",{}).get("bytes",0):,} байт** / **{v.get("package_size",{}).get("bytes",0)/1000000:.3f} MB**, бюджет ≤30 MB. Derived-макеты и audit в этот бюджет не входят.',
      '',review]
    (b.PKG/'README.md').write_text('\n'.join(lines),encoding='utf-8')


def run(b):
    ap=argparse.ArgumentParser();ap.add_argument('--verify-only',action='store_true');ap.add_argument('--retouch-only',action='store_true');ap.add_argument('--components-only',action='store_true');ap.add_argument('--leaders-only',action='store_true');args=ap.parse_args()
    actors,runhp,provenance=b.data();provenance['localized_names_missing']=[];provenance['ru_names']=RU
    if args.components_only:
        for config in b.CONFIGS:
            res,ui,*_=config
            for lang in ['ru','en']:output(b,b.PKG/f'comparison/HB-44-components-{lang}-{res}-{ui}.png',components(b,config,actors,runhp,lang))
        return
    matrix=(b.ROOT/'docs/game-design/05-content-matrix.csv').read_text(encoding='utf-8')
    for name in ['Медуза','Король Артур','Мерлин']:assert name in matrix
    provenance['damage']={'attacker':'merlin','target':'medusa','value':1,'source':'run I: Merlin WINS - Medusa -1'}
    provenance['harpy_client_order']=FIGHTERS;provenance['strings']={k:{'ru':v[0],'en':v[1]} for k,v in STRINGS.items()}
    for board in b.BOARDS:geometry(b,board)
    if args.verify_only:
        ERASE.update(json.loads((b.PKG/'label-erase-measurements.json').read_text(encoding='utf-8')))
        v=verify(b,json.loads((b.PKG/'layout-measurements.json').read_text(encoding='utf-8')),provenance)
        assert all(isinstance(er['visual_review'],dict) and er['visual_review']['passed'] for er in ERASE.values()),'Open the current x3 sheets and record their hashes in visual-review.json before final verification'
        v['checks']['label_erase_visual_review']=True
        v['checks']['label_erase_dark_figures_untouched']=all(box['dark_figure_pixels_changed']==0 and box['second_pass']['dark_figure_pixels_changed']==0 for er in ERASE.values() for box in er['boxes'])
        finalize(b,v);return
    for board in b.BOARDS:
        erase_labels(b,board);figure_mask_sheet(b,board)
    write_json(b,b.PKG/'label-erase-measurements.json',ERASE)
    if args.retouch_only:return
    if args.leaders_only:
        records=json.loads((b.PKG/'layout-measurements.json').read_text(encoding='utf-8'));affected=set()
        for i,r in enumerate(records):
            if not r.get('plate_position') or r['plate_position']['edge_distance_su']<=24:continue
            config=next(c for c in b.CONFIGS if [c[2],c[3]]==r['resolution'])
            board=r['board'];state=r['state'];res,ui,*_=config
            im,replacement=render(b,board,state,config,actors,runhp);output(b,b.DERIVED/r['file'],im);records[i]=replacement
            im,_=render(b,board,state,config,actors,runhp,True)
            output(b,b.PKG/f'comparison/HB-44-overlay-{board}-{state["id"]}-{res}-{ui}.png',im)
            affected.add((board,res,ui))
        for board,res,ui in affected:
            ss=['tags-start','tags-run-I','hover-medusa','selection-medusa','selection-arthur','attack-medusa']
            native_sheet(b,[f'HB-44-{board}-{v}-{res}-{ui}.png' for v in ss],b.DERIVED/f'HB-44-{board}-states-sheet-{res}-{ui}.png',f'HB-44 · {board} · states · {res} · {ui}%')
        write_json(b,b.PKG/'layout-measurements.json',records)
        v=verify(b,records,provenance);finalize(b,v);return
    write_json(b,b.PKG/'geometry.json',{'method':'K1 SHOT anchors/labels; image-checked full figure envelope incl wing/cape overhang; topology circle projection','boards':GEO})
    write_json(b,b.PKG/'source-data.json',provenance)
    write_json(b,b.PKG/'generation-records.json',{'task':'HB-44.fix2','records':[],'reason':'Image generation forbidden; procedural real-input mockup'})
    records=[];digitchecks=[]
    for config in b.CONFIGS:
        res,ui,w,h,dpi,app=config;s=dpi*app
        for lang in ['ru','en']:output(b,b.PKG/f'comparison/HB-44-components-{lang}-{res}-{ui}.png',components(b,config,actors,runhp,lang))
        output(b,b.PKG/f'comparison/HB-44-motion-{res}-{ui}.png',motion(b,config))
        for board in b.BOARDS:
            for state in states(b):
                im,r=render(b,board,state,config,actors,runhp);output(b,b.DERIVED/r['file'],im);records.append(r)
                if state.get('plate'):
                    im,_=render(b,board,state,config,actors,runhp,True)
                    output(b,b.PKG/f'comparison/HB-44-overlay-{board}-{state["id"]}-{res}-{ui}.png',im)
            for group,ss in [('states',['tags-start','tags-run-I','hover-medusa','selection-medusa','selection-arthur','attack-medusa']),
                             ('damage',[f'damage-{t:03d}ms' for t in [0,300,600,900]]),
                             ('heal',[f'heal-example-{t:03d}ms' for t in [0,300,600,700]])]:
                native_sheet(b,[f'HB-44-{board}-{v}-{res}-{ui}.png' for v in ss],b.DERIVED/f'HB-44-{board}-{group}-sheet-{res}-{ui}.png',f'HB-44 · {board} · {group} · {res} · {ui}%')
        rasters=[]
        for digit in ['1','2','3']:
            c=b.Canvas(Image.new('RGB',(48,48),b.rgb('card.navy')),s);c.text((24,24),digit,14,'card.cream',True,cap=10);rasters.append(np.asarray(b.gray(c.im)))
        digitchecks.append({'resolution':res,'ui_scale':ui,'pair_differing_px':{a+z:int(np.count_nonzero(rasters[i]!=rasters[j])/3) for i,a in enumerate(['1','2','3']) for j,z in enumerate(['1','2','3']) if i<j}})
    write_json(b,b.PKG/'digit-checks.json',digitchecks);write_json(b,b.PKG/'layout-measurements.json',records)
    # Remove only prior outputs not rebuilt; tools/baselines and preserved review are inputs.
    keep={'README.md','verification.json','manifest.json','manifest-sha256.json','source-hashes-before.json','scope-audit-before.json','scope-audit-after.json','review-original.json','visual-review.json'}
    for folder in [b.PKG,b.DERIVED]:
        assert folder.resolve().is_relative_to(b.ROOT.resolve())
        for p in folder.rglob('*'):
            if p.is_file() and p.resolve() not in GENERATED and p.name not in keep and not any(part in ['_tools','audit'] for part in p.relative_to(folder).parts):p.unlink()
    v=verify(b,records,provenance);finalize(b,v)
