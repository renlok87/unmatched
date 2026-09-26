"""Normalize the two revised profiles; preserve every previous PNG."""
import importlib.util
import json
from pathlib import Path
from PIL import Image, ImageDraw

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('base',Path(__file__).with_name('normalize-views.py'))
base=importlib.util.module_from_spec(spec); spec.loader.exec_module(base)
old=json.loads((ROOT/'normalized-views.json').read_text(encoding='utf8'))['outputs']
rows=[]
for name,version,role,previous in [('king-arthur',7,'right',6),('merlin',5,'left',4)]:
    source=f'characters/ref-{name}-v{version}-{role}-raw.png'
    image,box,bw,cx,bg=base.extract(ROOT/source)
    ref=next(r for r in old if r['assetId']=='REF-'+name.upper() and r['role']==role)
    scale=min(ref['parameters']['targetBaseWidthPx']/bw,810/(box[3]-box[1]))
    crop=image.crop(box); size=(round(crop.width*scale),round(crop.height*scale))
    crop=crop.resize(size,Image.Resampling.LANCZOS)
    xy=(round(512-(cx-box[0])*size[0]/(box[2]-box[0])),918-size[1])
    out=Image.new('RGBA',(1024,1024),(128,128,128,255)); out.alpha_composite(crop,xy)
    path=f'characters/ref-{name}-v{version}-{role}.png'
    base.save_new(out.convert('RGB'),ROOT/path)
    rows.append({'assetId':ref['assetId'],'role':role,'version':version,'path':path,'source':source,
        'sourceSha256':base.digest(ROOT/source),'replaces':f'characters/ref-{name}-v{previous}-{role}.png',
        'sha256':base.digest(ROOT/path),'width':1024,'height':1024,'alpha':False,'bytes':(ROOT/path).stat().st_size,
        'method':'Boundary-connected background extraction; isotropic Lanczos fit by base width with height limit; #808080 composite',
        'parameters':{'sourceBounds':box,'sourceBaseWidthPx':bw,'sourceBaseCenterX':cx,'sourceBackgroundRgb':bg.tolist(),
            'targetBaseWidthPx':ref['parameters']['targetBaseWidthPx'],'scaleXY':[size[0]/(box[2]-box[0]),size[1]/(box[3]-box[1])],
            'pasteXY':list(xy),'baseline':918,'backgroundTolerance':12,'minimumComponentPixels':24}})
(ROOT/'normalized-v4.json').write_text(json.dumps({'authorization':'Continuation of user-authorized side corrections after review; original-preserving normalization authorized.','outputs':rows},indent=2)+'\n',encoding='utf8')
sheet=Image.new('RGB',(1536,1088),(30,34,39)); draw=ImageDraw.Draw(sheet)
for y,(name,opposite,previous,current) in enumerate([
    ('king-arthur','v5-left','v6-right','v7-right'),('merlin','v3-right','v4-left','v5-left')]):
    for x,(label,suffix) in enumerate([('REFERENCE opposite',opposite),('PREVIOUS rejected',previous),('NEW candidate',current)]):
        im=Image.open(ROOT/f'characters/ref-{name}-{suffix}.png').resize((512,512),Image.Resampling.LANCZOS)
        sheet.paste(im,(512*x,544*y+32)); draw.text((512*x+8,544*y+10),f'{name}: {label} / {suffix}',fill='white')
base.save_new(sheet,ROOT/'side-profiles-v4-preview.png')
print(json.dumps({'normalizedFiles':len(rows),'preview':'side-profiles-v4-preview.png'}))
