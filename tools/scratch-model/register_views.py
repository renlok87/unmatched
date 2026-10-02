"""Register raw generated PNGs using four corner circles, only scale/translation.

Run: python tools/scratch-model/register_views.py path/to/package --view front --variant shaded --attempt 1
Inputs: template.json; raw/<key>-<view>-<variant>-tryN.png (never modified).
Outputs: views-registration.json, views/<key>-<view>-<variant>.png only on pass.
Lanczos resampling; no rotation, skew, geometry or paint fixes.
"""
import argparse
from pathlib import Path
import numpy as np
from PIL import Image
from scipy import ndimage
from common import read, write, check, BACKGROUND

def detect(im, target):
    a=np.asarray(im.convert('RGB')); h,w=a.shape[:2]; points=[]
    for ex,ey in target:
        # Normalize corner search windows for generator canvas changes.
        left=max(0,int(ex)-85);right=min(w,int(ex)+86);top=max(0,int(ey)-85);bottom=min(h,int(ey)+86)
        black=np.max(a[top:bottom,left:right],axis=-1)<65
        closed=ndimage.binary_closing(black,structure=np.ones((5,5)))
        labels,n=ndimage.label(closed); candidates=[]
        for k in range(1,n+1):
            yy,xx=np.nonzero(labels==k)
            if len(xx)<100 or len(xx)>1800:continue
            width=int(xx.max()-xx.min()+1);height=int(yy.max()-yy.min()+1)
            if not (16<=width<=40 and 16<=height<=40 and .75<=width/height<=1.33):continue
            candidates.append((abs(len(xx)-450),[float(xx.mean()+left),float(yy.mean()+top)]))
        if not candidates:raise ValueError('missing_registration_mark')
        points.append(min(candidates,key=lambda x:x[0])[1])
    return np.array(points)

def fit(source,target):
    source=np.asarray(source,dtype=float);target=np.asarray(target,dtype=float)
    sc=source-source.mean(axis=0);tc=target-target.mean(axis=0)
    scale=float(np.sum(sc*tc)/np.sum(sc*sc));shift=target.mean(axis=0)-scale*source.mean(axis=0)
    residual=np.linalg.norm(scale*source+shift-target,axis=1)
    return scale,shift,residual

def register(im,t):
    target=np.array(t['registration_marks_px']);source=detect(im,target)
    scale,shift,residual=fit(source,target)
    c={'canvas':check(list(im.size)==t['canvas_px'],list(im.size),t['canvas_px']),
       'residual_px':check(bool(np.all(residual<=1.5)),residual.tolist(),'each <=1.5 px'),
       'scale_correction':check(abs(scale-1)<=.03,scale,'1 ±0.03')}
    meta=dict(source_marks_px=source.tolist(),scale=scale,translation_px=shift.tolist(),checks=c,checks_passed=all(v['passed'] for v in c.values()))
    if not meta['checks_passed']:return None,meta
    w,h=t['canvas_px']; pad=100
    padded=Image.new('RGB',(im.width+2*pad,im.height+2*pad),BACKGROUND);padded.paste(im.convert('RGB'),(pad,pad))
    box=(pad-shift[0]/scale,pad-shift[1]/scale,pad+(w-shift[0])/scale,pad+(h-shift[1])/scale)
    output=padded.resize((w,h),Image.Resampling.LANCZOS,box=box)
    return output,meta

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('package',type=Path);p.add_argument('--view',choices=['front','side','back'],required=True);p.add_argument('--variant',choices=['shaded','albedo'],required=True);p.add_argument('--attempt',type=int,required=True)
    a=p.parse_args();s=read(a.package/'spec.json');t=read(a.package/'template.json');key=s['key'].lower();raw=f'{key}-{a.view}-{a.variant}-try{a.attempt}.png';path=a.package/'raw'/raw
    try:out,meta=register(Image.open(path),t)
    except ValueError as e:out=None;meta=dict(checks_passed=False,checks={'registration_marks':check(False,str(e),'four detectable marks')})
    meta['raw']=f'raw/{raw}';rpath=a.package/'views-registration.json';r=read(rpath) if rpath.exists() else dict(schema='unmatched.scratch-registration/1',attempts={},selected={})
    r['attempts'][raw]=meta
    if out is not None:
        (a.package/'views').mkdir(exist_ok=True);out.save(a.package/'views'/f'{key}-{a.view}-{a.variant}.png');r['selected'][f'{a.view}-{a.variant}']=raw
    else:
        # Do not accidentally validate stale registered pixels after a rejected new attempt.
        r['selected'].pop(f'{a.view}-{a.variant}',None)
    write(rpath,r);print(meta);raise SystemExit(0 if out is not None else 1)

if __name__=='__main__':main()
