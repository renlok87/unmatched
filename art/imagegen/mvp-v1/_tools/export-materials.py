"""Deterministic D/N/ORM proposals derived from original imagegen basecolors.

No generative redraw. N and AO are luminance heuristics, not geometry bakes.
Run with Python 3.13, Pillow 12.1, numpy 2.4, scipy 1.17.
"""
from pathlib import Path
import hashlib
import json
import importlib.util
import numpy as np
from scipy.ndimage import gaussian_filter
from PIL import Image

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('normalization',Path(__file__).with_name('normalize-views.py'))
helper=importlib.util.module_from_spec(spec)
spec.loader.exec_module(helper)
PARAMS={'cobblestone':(4,.82,0),'rock':(3,.90,0),'old-wood':(1.5,.80,0),'charcoal-cloth':(.5,.88,0),'dull-bronze':(.8,.65,1),'aged-iron':(1,.75,1)}

def metadata(p,**extra):
    im=Image.open(p)
    return {'path':p.relative_to(ROOT).as_posix(),'width':im.width,'height':im.height,'alpha':False,'bytes':p.stat().st_size,'sha256':hashlib.sha256(p.read_bytes()).hexdigest(),**extra}

def seams(a):
    a=np.asarray(a,dtype=float)
    wrapx=np.abs(a[:,0]-a[:,-1]).mean()
    wrapy=np.abs(a[0]-a[-1]).mean()
    innerx=np.abs(np.diff(a,axis=1)).mean()
    innery=np.abs(np.diff(a,axis=0)).mean()
    return {'edgeMeanDifferenceXY':[float(wrapx),float(wrapy)],'interiorNeighborMeanDifferenceXY':[float(innerx),float(innery)],'edgeToInteriorRatioXY':[float(wrapx/max(innerx,.001)),float(wrapy/max(innery,.001))]}

rows=[]
previews=[]
checks=[]
for name,(strength,roughness,metallic) in PARAMS.items():
    source=ROOT/f'materials/tex-{name}.png'
    original=Image.open(source).convert('RGB')
    for size in (2048,1024):
        diffuse=original.resize((size,size),Image.Resampling.LANCZOS)
        rgb=np.asarray(diffuse,dtype=np.float32)/255
        luma=rgb@np.array([.2126,.7152,.0722],dtype=np.float32)
        height=gaussian_filter(luma,1.5*size/1024,mode='wrap')
        lo,hi=np.percentile(height,[5,95])
        height=np.clip((height-lo)/max(hi-lo,.02),0,1)
        dx=(np.roll(height,-1,axis=1)-np.roll(height,1,axis=1))*.5*strength*size/1024
        dy=(np.roll(height,-1,axis=0)-np.roll(height,1,axis=0))*.5*strength*size/1024
        # OpenGL convention here is (-dx,-dy,1); invert green for DirectX.
        normal=np.stack([-dx,dy,np.ones_like(dx)],axis=2)
        normal/=np.linalg.norm(normal,axis=2,keepdims=True)
        normal8=np.clip(np.rint((normal*.5+.5)*255),0,255).astype(np.uint8)
        ao=1-.35*np.clip((gaussian_filter(height,12*size/1024,mode='wrap')-height)*1.5,0,1)
        rough=np.clip(roughness+.08*(.5-height),0,1)
        orm=np.clip(np.rint(np.stack([ao,rough,np.full_like(ao,metallic)],axis=2)*255),0,255).astype(np.uint8)
        maps={'D':diffuse,'N':Image.fromarray(normal8),'ORM':Image.fromarray(orm)}
        for kind,im in maps.items():
            path=ROOT/f'materials/export/T_{name.replace("-","_")}_{kind}_{size}.png'
            helper.save_new(im,path)
            rows.append(metadata(path,assetId='TEX-'+name.upper(),kind=kind,source=source.relative_to(ROOT).as_posix(),sourceSha256=helper.digest(source),parameters={'heightPercentiles':[5,95],'heightBlurSigmaAt1024':1.5,'normalStrength':strength,'normalOrientation':'DirectX: G inverted relative to OpenGL','roughnessBase':roughness,'roughnessAmplitude':.08,'metallic':metallic,'aoStrength':.35,'aoSigmaAt1024':12,'periodicFilters':True}))
            if size==1024:
                tile=im.resize((512,512),Image.Resampling.LANCZOS) if kind=='D' else im.resize((512,512),Image.Resampling.NEAREST)
                preview=Image.new('RGB',(1024,1024))
                for x in (0,512):
                    for y in (0,512): preview.paste(tile,(x,y))
                pp=ROOT/f'materials/export/previews/T_{name.replace("-","_")}_{kind}_tile2x2.png'
                helper.save_new(preview,pp)
                previews.append(metadata(pp,kind=kind,assetId='TEX-'+name.upper()))
        decoded=normal8.astype(float)/255*2-1
        error=np.abs(np.linalg.norm(decoded,axis=2)-1)
        checks.append({'name':name,'size':size,'normalMaxLengthError':float(error.max()),'normalNormalizedWithinQuantization':bool(error.max()<.015),'metallicExact':bool(np.all(orm[:,:,2]==255*metallic)),'seams':{k:seams(im) for k,im in maps.items()}})
(ROOT/'material-exports.json').write_text(json.dumps({'method':'Luminance-derived height/normal/AO proposals. D is Lanczos only. No real geometry bake; seams must be visually reviewed.','outputs':rows,'previews':previews,'checks':checks},indent=2)+'\n',encoding='utf8')
print(json.dumps({'exports':len(rows),'previews':len(previews),'normalAndMetallicPass':all(r['normalNormalizedWithinQuantization'] and r['metallicExact'] for r in checks)}))
