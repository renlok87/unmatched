"""Measure registered views against immutable spec and cross-view contracts.

Run: python tools/scratch-model/check_views.py path/to/package
For a single generation attempt: add --view front --variant shaded.
Inputs: spec.json, template.json, views-registration.json and selected views PNGs.
Outputs: views-check.json (or --output), masks PNGs, diagnostic overlays.
Reports missing views as FAIL; never claims full package passed on a partial run.
"""
import argparse
from pathlib import Path
import numpy as np
from PIL import Image
from common import read, report, check, silhouette, weapon_region, row_width, lab, rgb, GRID

def measure(package, only_view=None, only_variant=None):
    s=read(package/'spec.json');t=read(package/'template.json');scale=t['px_per_cm'];b=t['baseline_px'];key=s['key'].lower()
    reg=read(package/'views-registration.json');c={};masks={};body={};extents={}
    for view in ([only_view] if only_view else ['front','side','back']):
        for variant in ([only_variant] if only_variant else ['shaded','albedo']):
            prefix=f'{view}.{variant}';selected=reg['selected'].get(f'{view}-{variant}');path=package/'views'/f'{key}-{view}-{variant}.png'
            available=bool(selected and path.exists())
            c[prefix+'.registered']=check(available,selected,'selected registered raw attempt')
            if not available:continue
            meta=reg['attempts'][selected];c[prefix+'.registration']=check(meta['checks_passed'],meta['checks'],'scale <=3%; each residual <=1.5 px')
            mask,components,pixels=silhouette(path,t);masks[(view,variant)]=mask
            (package/'masks').mkdir(exist_ok=True);Image.fromarray((mask*255).astype('uint8')).save(package/'masks'/f'{key}-{view}-{variant}.png')
            if variant=='shaded':Image.fromarray((mask*255).astype('uint8')).save(package/'masks'/f'{key}-{view}.png')
            ys,xs=np.nonzero(mask)
            if not xs.size:
                c[prefix+'.figure']=check(False,0,'nonempty figure');continue
            c[prefix+'.single_connected_figure']=check(len(components)==1,components,'one substantial component (>=0.1% largest, >=100 px)')
            edge=bool(mask[0].any() or mask[-1].any() or mask[:,0].any() or mask[:,-1].any())
            c[prefix+'.frame_margin']=check(not edge,edge,'no edge contact')
            bottom=int(ys.max());c[prefix+'.baseline']=check(abs(bottom-b)<=2,bottom,dict(baseline_px=b,tolerance_px=2))
            wr=weapon_region(s,view,t);body_mask=mask & ~wr;body[(view,variant)]=body_mask
            ybody=np.nonzero(body_mask)[0];top=int(ybody.min());height=(b-top)/scale
            c[prefix+'.figure_height']=check(abs(height/s['height_cm']-1)<=.01,height,dict(height_cm=s['height_cm'],tolerance_rel=.01))
            extents[(view,variant)]=(top,bottom)
            base_top=b-s['base']['height_cm']*scale
            widths=[row_width(mask,y) for y in range(round(base_top)+2,bottom-1)]
            base=float(max(widths,default=0)/scale)
            c[prefix+'.base_diameter']=check(abs(base/s['base']['diameter_cm']-1)<=.02,base,dict(diameter_cm=s['base']['diameter_cm'],tolerance_rel=.02))
            errors=[]
            for landmark,expected in s['widths_cm']['side' if view=='side' else 'front'].items():
                z=s['landmarks_z_cm'][landmark];row=b-z*scale;actual=row_width(body_mask,row)/scale;rel=abs(actual/expected-1);errors.append(rel)
                c[prefix+'.width.'+landmark]=check(rel<=.08,actual,dict(width_cm=expected,tolerance_rel=.08),'Staff excluded using pre-generation projection bounds from spec; all other silhouette retained.')
            med=float(np.median(errors));c[prefix+'.width_median']=check(med<=.04,med,'relative median <=0.04')
            grid=np.linalg.norm(lab(pixels)-lab(rgb(GRID)),axis=-1)<=12
            fraction=float(np.sum(grid&mask)/mask.sum());c[prefix+'.grid_inside']=check(fraction<=.002,fraction,'<=0.002')
            if variant=='albedo':
                values=lab(pixels[mask]);palette=lab(np.array([rgb(z['hex']) for z in s['palette']]))
                assignments=np.argmin(np.sum((values[:,None]-palette[None])**2,axis=-1),axis=1)
                for i,zone in enumerate(s['palette']):
                    brightness=values[assignments==i,0]/100
                    if len(brightness)>=100:
                        spread=float(brightness.max()-brightness.min());c[prefix+'.flat.'+zone['zone']]=check(spread<=.12,spread,'L* range /100 <=0.12')
            # Separate diagnostic only; never feeds registration or measurements.
            overlay=np.asarray(Image.open(path).convert('RGB')).copy()
            from scipy import ndimage
            border=mask & ~ndimage.binary_erosion(mask);overlay[border]=[255,0,100]
            (package/'diagnostics').mkdir(exist_ok=True);Image.fromarray(overlay).save(package/'diagnostics'/f'{key}-{view}-{variant}-mask-overlay.png')
    if not only_variant:
        for view in ([only_view] if only_view else ['front','side','back']):
            a=masks.get((view,'shaded'));d=masks.get((view,'albedo'))
            if a is not None and d is not None:
                iou=float(np.sum(a&d)/np.sum(a|d));c[view+'.shaded_albedo_iou']=check(iou>=.98,iou,'>=0.98')
    if not only_view:
        a=body.get(('front','shaded'));d=body.get(('back','shaded'))
        if a is not None and d is not None:
            errors=[];lo,hi=s['weapon']['rows_excluded_from_symmetry_z_cm']
            for y in range(round(b-s['height_cm']*scale),round(b-s['base']['height_cm']*scale)):
                z=(b-y)/scale
                if lo<=z<=hi:continue
                errors.append(abs(row_width(a,y)-row_width(d[:,::-1],y))/(s['height_cm']*scale))
            med=float(np.median(errors)) if errors else 1;p95=float(np.percentile(errors,95)) if errors else 1
            c['front_back.profile_median']=check(med<=.02,med,'<=0.02 of full figure height')
            c['front_back.profile_p95']=check(p95<=.05,p95,'<=0.05 of full figure height')
        if ('front','shaded') in extents and ('side','shaded') in extents:
            delta=[abs(a-bb)/(s['height_cm']*scale) for a,bb in zip(extents[('front','shaded')],extents[('side','shaded')])]
            c['front_side.extents']=check(max(delta)<=.01,delta,'top and bottom <=0.01 of full height')
    return c

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('package',type=Path);p.add_argument('--view',choices=['front','side','back']);p.add_argument('--variant',choices=['shaded','albedo']);p.add_argument('--output',type=Path)
    a=p.parse_args();c=measure(a.package,a.view,a.variant);r=report(a.output or a.package/'views-check.json',c,scope='attempt' if a.view or a.variant else 'package')
    print('checks_passed:',r['checks_passed'])
    for name,value in c.items():
        if not value['passed']:print(name,value['measured'],value['expected'])
    raise SystemExit(0 if r['checks_passed'] else 1)

if __name__=='__main__':main()
