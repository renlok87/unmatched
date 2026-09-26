"""Authorized layout/resize/background normalization; no source overwritten."""
from pathlib import Path
import importlib.util
import json
from PIL import Image

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('n',Path(__file__).with_name('normalize-views.py'))
n=importlib.util.module_from_spec(spec)
spec.loader.exec_module(n)
rows=[]

def output(asset,role,source,destination,target_width=None,aspect=1):
    image,box,bw,cx,bg=n.extract(ROOT/source)
    crop=image.crop(box)
    if aspect!=1:
        crop=crop.resize((round(crop.width*aspect),crop.height),Image.Resampling.LANCZOS)
    scale=min(810/crop.width,810/crop.height)
    if target_width is not None: scale=min(target_width/crop.width,810/crop.height)
    size=(round(crop.width*scale),round(crop.height*scale))
    crop=crop.resize(size,Image.Resampling.LANCZOS)
    out=Image.new('RGBA',(1024,1024),(128,128,128,255))
    xy=((1024-size[0])//2,918-size[1])
    if role in ('top','three-quarter'): xy=((1024-size[0])//2,(1024-size[1])//2)
    out.alpha_composite(crop,xy)
    n.save_new(out.convert('RGB'),ROOT/destination)
    rows.append({'assetId':asset,'role':role,'path':destination,'source':source,'sourceSha256':n.digest(ROOT/source),'sha256':n.digest(ROOT/destination),'width':1024,'height':1024,'alpha':False,'bytes':(ROOT/destination).stat().st_size,'method':'boundary gray removal, Lanczos scale, #808080 canvas','parameters':{'sourceBounds':box,'sourceBackgroundRgb':bg.tolist(),'horizontalAspectFactor':aspect,'scale':scale,'pasteXY':xy,'pasteSize':size}})

# Reviewed playable bounds in raw v3: x148..995,y139..1210.
# Technical aspect correction gives field5:6; no cells or paint are redrawn.
factor=(5/6)/((995-148)/(1210-139))
output('REF-BOARD-COBBLE','top','environment/ref-board-cobble-v3.png','environment/ref-board-cobble-v4.png',aspect=factor)
output('REF-BOARD-COBBLE','side','environment/ref-board-cobble-v2-side.png','environment/ref-board-cobble-v3-side.png')
for role in ('front','side','top','three-quarter'):
    output('REF-BARREL',role,f'environment/ref-barrel-v2-{role}.png',f'environment/ref-barrel-v3-{role}.png',target_width=658 if role=='top' else None)
for role in ('front','left','back','right'):
    output('REF-LANTERN',role,f'environment/ref-lantern-v2-{role}.png',f'environment/ref-lantern-v3-{role}.png')
for role in ('three-quarter','front','side'):
    output('REF-TABLE-BASE',role,f'environment/ref-table-base-v2-{role}.png',f'environment/ref-table-base-v3-{role}.png',target_width=675 if role=='front' else 810 if role=='side' else None)
(ROOT/'normalized-environment.json').write_text(json.dumps({'authorization':'Technical normalization approved by user; original imagegen files preserved.','outputs':rows},indent=2)+'\n',encoding='utf8')
print(json.dumps({'normalized':len(rows),'boardHorizontalCorrection':factor}))
