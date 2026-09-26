"""Authorized technical normalization; originals remain byte-for-byte intact.

Reproduce: python art/imagegen/mvp-v1/_tools/normalize-views.py
Pillow 12.1, numpy 2.4, scipy 1.17. No artistic features are added.
"""
from pathlib import Path
import hashlib
import json
import numpy as np
from scipy import ndimage as ndi
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
ROLES = ['front', 'left', 'back', 'right']
SETS = {
    'king-arthur': ([4,4,4,4], 5, 30),
    'medusa': ([3,4,3,4], 5, 30),
    'merlin': ([2,2,2,2], 3, 24),
    'harpy': ([3,3,3,3], 4, 22),
}

def digest(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()

def save_new(image, p):
    import io
    b = io.BytesIO()
    image.save(b, format='PNG', optimize=True)
    data = b.getvalue()
    p.parent.mkdir(parents=True, exist_ok=True)
    if p.exists() and p.read_bytes() != data:
        raise RuntimeError(f'Refusing to overwrite {p}; select another version')
    p.write_bytes(data)

def extract(p):
    a = np.asarray(Image.open(p).convert('RGB'))
    edges = np.concatenate([a[:16].reshape(-1,3),a[-16:].reshape(-1,3),a[:,:16].reshape(-1,3),a[:,-16:].reshape(-1,3)])
    bg = np.median(edges,axis=0)
    eligible = np.max(np.abs(a.astype(float)-bg),axis=2) < 12
    seed = np.zeros(eligible.shape,bool)
    seed[[0,-1],:] = eligible[[0,-1],:]
    seed[:,[0,-1]] = eligible[:,[0,-1]]
    foreground = ~ndi.binary_propagation(seed,mask=eligible)
    labels,count = ndi.label(foreground)
    sizes = np.bincount(labels.ravel())
    keep = sizes >= 24
    keep[0] = False
    foreground = keep[labels]
    ys,xs = np.nonzero(foreground)
    box = [int(xs.min()),int(ys.min()),int(xs.max())+1,int(ys.max())+1]
    base_rows = []
    for y in range(max(box[1],box[3]-40),box[3]):
        xx = np.flatnonzero(foreground[y])
        if len(xx): base_rows.append((int(xx[-1]-xx[0]+1),float((xx[-1]+xx[0])/2)))
    base_width,base_center = max(base_rows)
    rgba = np.dstack([a,foreground.astype(np.uint8)*255])
    return Image.fromarray(rgba),box,base_width,base_center,bg

def main():
    rows=[]
    for name,(versions,output_version,diameter) in SETS.items():
        sources=[]
        for role,version in zip(ROLES,versions):
            relative=f'characters/ref-{name}-v{version}-{role}.png'
            image,box,bw,cx,bg=extract(ROOT/relative)
            sources.append((relative,role,image,box,bw,cx,bg))
        target_width=min(min(812*bw/(box[3]-box[1]),406*bw/max(cx-box[0],1),406*bw/max(box[2]-cx,1)) for _,_,_,box,bw,cx,_ in sources)
        for source,role,image,box,bw,cx,bg in sources:
            scale=target_width/bw
            tx=512-cx*scale
            ty=918-box[3]*scale
            # Supersample the affine mapping for antialiasing, then Lanczos to 1024.
            large=image.transform((2048,2048),Image.Transform.AFFINE,(1/(scale*2),0,-tx/scale,0,1/(scale*2),-ty/scale),resample=Image.Resampling.BICUBIC)
            fg=large.resize((1024,1024),Image.Resampling.LANCZOS)
            out=Image.new('RGBA',(1024,1024),(128,128,128,255))
            out.alpha_composite(fg)
            out=out.convert('RGB')
            relative=f'characters/ref-{name}-v{output_version}-{role}.png'
            save_new(out,ROOT/relative)
            rows.append({'assetId':'REF-'+name.upper(),'role':role,'version':output_version,'path':relative,'source':source,'sourceSha256':digest(ROOT/source),'sha256':digest(ROOT/relative),'width':1024,'height':1024,'alpha':False,'bytes':(ROOT/relative).stat().st_size,'method':'boundary-connected gray removal; isotropic scaling by detected base diameter; 2x bicubic affine + Lanczos; composite #808080','parameters':{'backgroundTolerance':12,'minimumComponentPixels':24,'sourceBackgroundRgb':bg.tolist(),'sourceBounds':box,'sourceBaseWidthPx':bw,'sourceBaseCenterX':cx,'targetBaseWidthPx':target_width,'scale':scale,'translation':[tx,ty],'baseline':918,'baseDiameterUu':diameter}})
    (ROOT/'normalized-views.json').write_text(json.dumps({'authorization':'User approved scripted normalization of views and flipbooks, preserving originals.','outputs':rows},ensure_ascii=False,indent=2)+'\n',encoding='utf8')
    print(json.dumps({'normalized':len(rows),'baseWidths':{n:round(next(r['parameters']['targetBaseWidthPx'] for r in rows if r['assetId']=='REF-'+n.upper()),2) for n in SETS}}))

if __name__=='__main__': main()
