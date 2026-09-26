"""v3 authorized normalization. Reproduce without overwriting any prior PNG.

Side edits: original physical base width and baseline; isotropic resize.
Harpy: preserve horizontal/base scale, normalize total silhouette height to480px.
The independent vertical fit is recorded; it does not prove matching 3D anatomy.
"""
from pathlib import Path
import importlib.util
import json
import numpy as np
from PIL import Image,ImageDraw

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('n',Path(__file__).with_name('normalize-views.py'))
n=importlib.util.module_from_spec(spec)
spec.loader.exec_module(n)
old=json.loads((ROOT/'normalized-views.json').read_text(encoding='utf8'))['outputs']
rows=[]

def bounds(im):
    a=np.asarray(im.convert('RGB'),dtype=float)
    ys,xs=np.nonzero(np.max(np.abs(a-128),axis=2)>15)
    return [int(xs.min()),int(ys.min()),int(xs.max()),int(ys.max())]

def normalize(name,role,source,destination,target_height=None):
    previous=next(r for r in old if r['assetId']=='REF-'+name.upper() and r['role']==role)
    image,box,bw,cx,bg=n.extract(ROOT/source)
    scale=previous['parameters']['targetBaseWidthPx']/bw
    if target_height is None: scale=min(scale,810/(box[3]-box[1]))
    crop=image.crop(box)
    size=(round(crop.width*scale),target_height or round(crop.height*scale))
    crop=crop.resize(size,Image.Resampling.LANCZOS)
    x=round(512-(cx-box[0])*size[0]/(box[2]-box[0])); y=918-size[1]
    out=Image.new('RGBA',(1024,1024),(128,128,128,255)); out.alpha_composite(crop,(x,y)); out=out.convert('RGB')
    n.save_new(out,ROOT/destination)
    before=bounds(Image.open(ROOT/previous['path'])); after=bounds(out)
    rows.append({'assetId':'REF-'+name.upper(),'role':role,'path':destination,'source':source,'sourceSha256':n.digest(ROOT/source),'replaces':previous['path'],'sha256':n.digest(ROOT/destination),'width':1024,'height':1024,'alpha':False,'bytes':(ROOT/destination).stat().st_size,'method':'boundary background segmentation, Lanczos fit, solid#808080 canvas','parameters':{'sourceBounds':box,'detectedSourceBaseWidth':bw,'targetBaseWidth':previous['parameters']['targetBaseWidthPx'],'scaleXY':[size[0]/(box[2]-box[0]),size[1]/(box[3]-box[1])],'pasteXY':[x,y],'targetSilhouetteHeight':target_height,'baseline':918},'measurement':{'threshold':'max RGB distance from128 >15, inclusive bounds','previousBounds':before,'previousHeightPx':before[3]-before[1]+1,'outputBounds':after,'outputHeightPx':after[3]-after[1]+1}})

normalize('king-arthur','right','characters/ref-king-arthur-v6-right-raw.png','characters/ref-king-arthur-v6-right.png')
normalize('merlin','left','characters/ref-merlin-v4-left-raw.png','characters/ref-merlin-v4-left.png')
normalize('medusa','right','characters/ref-medusa-v6-right-raw.png','characters/ref-medusa-v6-right.png')
for role in ('front','left','back','right'):
    source=f'characters/ref-harpy-v5-{role}-raw.png' if role=='right' else f'characters/ref-harpy-v4-{role}.png'
    normalize('harpy',role,source,f'characters/ref-harpy-v5-{role}.png',target_height=480)
(ROOT/'normalized-v3.json').write_text(json.dumps({'authorization':'User requested four side redraws and Harpy height alignment; technical normalization authorized.','outputs':rows},indent=2)+'\n',encoding='utf8')

# New preview only; preserve the previous review sheet.
selected={(r['assetId'],r['role']):r['path'] for r in old}
selected.update({(r['assetId'],r['role']):r['path'] for r in rows})
sheet=Image.new('RGB',(1536,1632),(30,34,39)); draw=ImageDraw.Draw(sheet)
for y,name in enumerate(('king-arthur','medusa','merlin','harpy')):
    for x,role in enumerate(('front','left','back','right')):
        p=selected[('REF-'+name.upper(),role)]
        sheet.paste(Image.open(ROOT/p).resize((384,384),Image.Resampling.LANCZOS),(384*x,408*y+24))
        draw.text((384*x+8,408*y+6),name+' / '+role,fill='white')
n.save_new(sheet,ROOT/'normalized-views-v3-preview.png')
print(json.dumps({'outputs':len(rows),'harpyHeights':[r['measurement'] for r in rows if r['assetId']=='REF-HARPY']}))
