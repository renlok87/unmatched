"""Layout normalization only: preserve row-major frames, add transparent gutters.

No generated animation is invented or interpolated. Temporal acceptance is separate.
"""
from pathlib import Path
import hashlib
import json
import importlib.util
import numpy as np
from PIL import Image

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('n',Path(__file__).with_name('normalize-views.py'))
n=importlib.util.module_from_spec(spec)
spec.loader.exec_module(n)
names={'impact':'VFX-COMBAT-IMPACT','damage':'VFX-DAMAGE','death-ash':'VFX-DEATH-ASH','petrify':'VFX-MEDUSA-PETRIFY','heal':'VFX-HEAL'}
rows=[]
for name,asset in names.items():
    source=f'vfx/vfx-{name}-flipbook-4x4-raw-v2.png'
    raw=Image.open(ROOT/source).convert('RGBA')
    out=Image.new('RGBA',(2048,2048))
    frames=[]
    previews=[]
    for index in range(16):
        row,col=divmod(index,4)
        box=(round(col*raw.width/4),round(row*raw.height/4),round((col+1)*raw.width/4),round((row+1)*raw.height/4))
        frame=raw.crop(box)
        a=np.asarray(frame)[:,:,3]
        edges=np.concatenate([a[0],a[-1],a[:,0],a[:,-1]])
        # Entire input cell is retained. Transparent padding doesn't repair pre-existing cropping.
        tile=frame.resize((480,480),Image.Resampling.LANCZOS)
        out.alpha_composite(tile,(col*512+16,row*512+16))
        canvas=Image.new('RGBA',(512,512)); canvas.alpha_composite(tile,(16,16))
        finalalpha=np.asarray(canvas)[:,:,3]
        frames.append({'index':index,'sourceBox':box,'rawEdgeMaxAlpha':int(edges.max()),'rawHasVisibleBoundaryContent':bool(edges.max()>8),'outputEdgeMaxAlpha':0,'outputAlphaSum':int(finalalpha.sum()),'outputVisiblePixels':int((finalalpha>8).sum())})
        bg=Image.new('RGBA',(512,512),(28,32,38,255)); bg.alpha_composite(canvas)
        previews.append(bg.convert('RGB'))
    destination=f'vfx/vfx-{name}-flipbook-4x4.png'
    n.save_new(out,ROOT/destination)
    # Contact sheet uses proper compositing; no alteration of the art.
    contact=Image.new('RGB',(1024,1024))
    for i,im in enumerate(previews): contact.paste(im.resize((256,256),Image.Resampling.LANCZOS),((i%4)*256,(i//4)*256))
    n.save_new(contact,ROOT/f'vfx/previews/vfx-{name}-flipbook-contact.png')
    rows.append({'assetId':asset,'role':'flipbook','path':destination,'source':source,'sourceSha256':n.digest(ROOT/source),'sha256':n.digest(ROOT/destination),'width':2048,'height':2048,'alpha':True,'bytes':(ROOT/destination).stat().st_size,'method':'row-major16 full-cell crops; Lanczos480px; transparent16px padding; no interpolation','frames':frames,'grid':[4,4],'technicalEdgesPass':True,'rawCropEdgesPass':all(not f['rawHasVisibleBoundaryContent'] for f in frames),'temporalAcceptance':'pending visual review; Niagara timing and simulation remain outside this package'})
(ROOT/'flipbook-exports.json').write_text(json.dumps({'authorization':'User explicitly approved technical flipbook normalization preserving original outputs.','outputs':rows},indent=2)+'\n',encoding='utf8')
print(json.dumps({'flipbooks':len(rows),'rawBoundaryFailures':{r['assetId']:[f['index'] for f in r['frames'] if f['rawHasVisibleBoundaryContent']] for r in rows}}))
