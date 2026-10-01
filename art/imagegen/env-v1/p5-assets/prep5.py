import sys, glob, os, json, hashlib
import numpy as np
from PIL import Image
from scipy import ndimage
SRC='C:/tmp/envmaps-research/refs5'; OUT='C:/tmp/envmaps-research/tripo-inputs5'
HOLES='--holes' in sys.argv
args=[a for a in sys.argv[1:] if a!='--holes']
ids=args or [os.path.basename(d) for d in sorted(glob.glob(f'{SRC}/ENV-*'))]
rp=f'{OUT}/prep-report.json'; rep=json.load(open(rp)) if os.path.exists(rp) else {}
sheet=[]
for aid in ids:
    os.makedirs(f'{OUT}/{aid}',exist_ok=True); row=[]
    for v in ('front','left','back','right'):
        p=f'{SRC}/{aid}/{v}.png'
        a=np.asarray(Image.open(p).convert('RGB')).astype(int)
        bgc=np.median(np.concatenate([a[0],a[-1],a[:,0],a[:,-1]]),axis=0)
        near=(np.abs(a-bgc).max(axis=2)<=6)
        lab,n=ndimage.label(near)
        edge=set(np.unique(np.concatenate([lab[0],lab[-1],lab[:,0],lab[:,-1]])))-{0}
        keep=set(edge)
        if HOLES:
            sizes=ndimage.sum(near,lab,range(1,n+1))
            keep|={i+1 for i,sz in enumerate(sizes) if sz>=400}
        bg=ndimage.binary_opening(np.isin(lab,list(keep)),iterations=1)
        o=a.copy(); o[bg]=255
        o[:6,:]=255; o[-6:,:]=255; o[:,:6]=255; o[:,-6:]=255  # imagegen 1-3 px frame line
        q=f'{OUT}/{aid}/{v}.png'; Image.fromarray(o.astype(np.uint8)).save(q)
        rep.setdefault(aid,{})[v]={'src':p,'size':list(a.shape[:2]),'bgColor':bgc.tolist(),'bgFrac':round(float(bg.mean()),3),'sha256':hashlib.sha256(open(q,'rb').read()).hexdigest()}
        row.append(Image.open(q).convert('RGB').resize((256,256)))
    sheet.append(row)
json.dump(rep,open(rp,'w'),indent=1)
W=Image.new('RGB',(1024,256*len(sheet)),'white')
for i,r in enumerate(sheet):
    for j,im in enumerate(r): W.paste(im,(256*j,256*i))
W.save(f'{OUT}/sheet-{"_".join(x[6:] for x in ids)[:60]}.jpg',quality=85)
for k in ids: print(k,{s:(x['bgFrac'],x['size']) for s,x in rep[k].items()})
