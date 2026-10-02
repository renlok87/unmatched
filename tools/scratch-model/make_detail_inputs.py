"""Prepare permitted head crops and a 2D staff detail grid from immutable spec.

Run: python tools/scratch-model/make_detail_inputs.py path/to/package
Inputs: spec.json; front shaded try7 and side shaded try1 originals.
Outputs: detail-inputs/*.png and detail-inputs/detail-template.json.
Only reference crops and a deterministic 2D measuring stencil, no final-image edits.
"""
import argparse
from pathlib import Path
from PIL import Image,ImageDraw
from common import read,write,BACKGROUND,GRID

def build(package):
    s=read(package/'spec.json');dest=package/'detail-inputs';dest.mkdir(exist_ok=True)
    crops={'front':dict(source='raw/merlin-front-shaded-try7.png',box=[350,240,675,660]),
           'side':dict(source='raw/merlin-side-shaded-try1.png',box=[385,235,650,660])}
    for view,item in crops.items():
        with Image.open(package/item['source']) as im:
            im.crop(item['box']).save(dest/f'merlin-face-{view}-crop.png')
    scale=29;baseline=1413;center=512;origin_x=-9.5;origin_z=5.5
    im=Image.new('RGB',(1024,1536),BACKGROUND);d=ImageDraw.Draw(im)
    for cm in range(-18,19):
        x=center+cm*scale;d.line((x,0,x,1535),fill=GRID,width=2 if cm%5==0 else 1)
    for cm in range(-4,50):
        y=baseline-cm*scale;d.line((0,y,1023,y),fill=GRID,width=2 if cm%5==0 else 1)
    def p(point):return center+(point[0]-origin_x)*scale,baseline-(point[2]-origin_z)*scale
    d.line([p(point) for point in s['weapon']['centerline_cm'][:-1]],fill='#35271C',width=round(2*s['weapon']['shaft_radius_cm']*scale))
    x,y=p(s['weapon']['crystal_center_cm']);rx=s['weapon']['crystal_width_cm']*scale/2;ry=s['weapon']['crystal_height_cm']*scale/2
    d.polygon([(x,y-ry),(x+rx,y),(x,y+ry),(x-rx,y)],fill='#2556AD')
    marks=[[40,40],[983,40],[40,1495],[983,1495]]
    for x,y in marks:
        d.ellipse((x-12,y-12,x+12,y+12),fill='black');d.line((x-8,y,x+8,y),fill='white',width=2);d.line((x,y-8,x,y+8),fill='white',width=2)
    im.save(dest/'merlin-weapon-front-template.png')
    write(dest/'detail-template.json',dict(schema='unmatched.scratch-detail-input/1',head_crops=crops,
        weapon=dict(canvas_px=[1024,1536],view='front',px_per_cm=scale,baseline_px=baseline,center_px=center,origin_x_cm=origin_x,origin_z_cm=origin_z,registration_marks_px=marks,purpose='2D generation guide only; not an accepted detail')))

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('package',type=Path);a=p.parse_args();build(a.package)

if __name__=='__main__':main()
