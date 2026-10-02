"""Draw centimetre grids and front/left-side/back camera matrices with Pillow.

Run: python tools/scratch-model/make_template.py path/to/spec.json
Input: scratch spec, canvas size verified with image_gen (default 1024x1536).
Output: templates/*.png, template.json. No generated character or 3D geometry.
"""
import argparse
import math
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont
from common import read, write, BACKGROUND, GRID, project

def build(s, size):
    w,h=size; top=max(s['height_cm'],s['weapon']['tip_cm'][2])
    scale=math.floor(.85*h/top); baseline=math.floor(.92*h); center=w//2
    t=dict(schema='unmatched.scratch-template/1',canvas_px=[w,h],px_per_cm=scale,baseline_px=baseline,center_px=center,
           background_hex=BACKGROUND,grid_hex=GRID,registration_marks_px=[[40,40],[w-41,40],[40,h-41],[w-41,h-41]],label_start_px=w-105,views={})
    for view,sign,axis in [('front',1,'x'),('side',1,'y'),('back',-1,'x')]:
        t['views'][view]=dict(horizontal_axis=axis,horizontal_sign=sign,camera_axis={'front':'-Y','side':'+X','back':'+Y'}[view],
            pixel_to_cm=[[sign/scale,0,-sign*center/scale],[0,-1/scale,baseline/scale],[0,0,1]],
            cm_to_pixel=[[sign*scale,0,center],[0,-scale,baseline],[0,0,1]],side_facing='left' if view=='side' else None)
    # Largest projection includes the base; even the label gutter is outside figure margin.
    extent=max(s['base']['diameter_cm']/2,max(v for widths in s['widths_cm'].values() for v in widths.values())/2,
               max(abs(p[i]) for p in s['weapon']['centerline_cm'] for i in (0,1))+s['weapon']['crystal_width_cm']/2)
    assert center-extent*scale>=.08*w and center+extent*scale<=w*.92, 'insufficient horizontal margin'
    assert baseline-top*scale>=.08*h and h-baseline>=.08*h, 'insufficient vertical margin'
    return t

def draw(s,t,view):
    w,h=t['canvas_px']; im=Image.new('RGB',(w,h),BACKGROUND); d=ImageDraw.Draw(im); scale=t['px_per_cm']; cx=t['center_px']; b=t['baseline_px']
    font=ImageFont.load_default(size=12)
    for cm in range(-math.ceil(w/scale),math.ceil(w/scale)+1):
        x=cx+cm*scale
        if 0<=x<w: d.line((x,0,x,h-1), fill=GRID,width=2 if cm%5==0 else 1)
    for cm in range(-math.ceil(h/scale),math.ceil(h/scale)+1):
        y=round(b-cm*scale)
        if 0<=y<h: d.line((0,y,w-1,y),fill=GRID,width=2 if cm%5==0 else 1)
    widths=s['widths_cm']['side' if view=='side' else 'front']
    for name,z in s['landmarks_z_cm'].items():
        y=round(b-z*scale); d.line((0,y,w-1,y),fill=GRID,width=2)
        if name in widths:
            for sign in (-1,1):
                x=round(cx+sign*widths[name]*scale/2); d.line((x,y-6,x,y+6),fill=GRID,width=3)
        d.rectangle((t['label_start_px'],y-7,w-1,y+8),fill=BACKGROUND)
        d.text((t['label_start_px']+2,y-6),name,fill=GRID,font=font)
    # Explicit staff guide is cyan, not geometry; it remains occluded by generated paint.
    points=[project(p,view,t) for p in s['weapon']['centerline_cm']]
    d.line(points,fill=GRID,width=3)
    for x,y in t['registration_marks_px']:
        d.ellipse((x-12,y-12,x+12,y+12),fill='black')
        d.line((x-8,y,x+8,y),fill='white',width=2); d.line((x,y-8,x,y+8),fill='white',width=2)
    return im

def draw_contour_guide(s,t,view):
    """2D dimensional underpainting from immutable spec, never generated pixels.

    This is an optional stronger generation input, not a finished/albedo view.
    No 3D geometry is constructed. Body edges interpolate specified widths.
    """
    im=draw(s,t,view);d=ImageDraw.Draw(im)
    widths=s['widths_cm']['side' if view=='side' else 'front']
    z=s['landmarks_z_cm'];scale=t['px_per_cm'];cx=t['center_px'];b=t['baseline_px']
    levels=sorted((z[n],width) for n,width in widths.items())
    levels=[(z['sole'],levels[0][1])]+levels+[(z['head_top'],0)]
    left=[(round(cx-width*scale/2),round(b-height*scale)) for height,width in levels]
    right=[(round(cx+width*scale/2),round(b-height*scale)) for height,width in reversed(levels)]
    d.polygon(left+right,fill='#182A49')
    base=s['base'];half=base['diameter_cm']*scale/2
    d.rectangle((round(cx-half),round(b-base['height_cm']*scale),round(cx+half),b),fill='#30343C')
    points=[project(p,view,t) for p in s['weapon']['centerline_cm']]
    # Centreline ends at the crystal top: shaft ends at crystal bottom.
    shaft=points[:-1]
    d.line(shaft,fill='#35271C',width=round(s['weapon']['shaft_radius_cm']*scale*2))
    x,y=project(s['weapon']['crystal_center_cm'],view,t)
    rx=s['weapon']['crystal_width_cm']*scale/2;ry=s['weapon']['crystal_height_cm']*scale/2
    d.polygon([(x,y-ry),(x+rx,y),(x,y+ry),(x-rx,y)],fill='#2556AD')
    # Simple facial patch, beard and belt help the model read a character instead of a vase.
    head_bottom=b-(z['head_top']-s['heads']['head_height_cm'])*scale
    eye_y=b-z['eye']*scale
    if view=='front':
        d.ellipse((cx-45,eye_y-25,cx+45,eye_y+60),fill='#BE9874')
        d.polygon([(cx-45,eye_y+40),(cx+45,eye_y+40),(cx+15,head_bottom+75),(cx-15,head_bottom+75)],fill='#EEE7D3')
    elif view=='side':
        d.polygon([(cx-85,eye_y-25),(cx-35,eye_y-30),(cx-35,eye_y+60),(cx-100,eye_y+45)],fill='#BE9874')
        d.polygon([(cx-100,eye_y+40),(cx-35,eye_y+40),(cx-35,head_bottom+75)],fill='#EEE7D3')
    waist=b-z['waist']*scale;waist_width=widths['waist']*scale
    d.rectangle((cx-waist_width/2+3,waist-12,cx+waist_width/2-3,waist+12),fill='#624029')
    return im

def main():
    p=argparse.ArgumentParser(description=__doc__); p.add_argument('spec',type=Path); p.add_argument('--width',type=int,default=1024);p.add_argument('--height',type=int,default=1536)
    p.add_argument('--contour-guide',action='store_true',help='Separate 2D underpainting derived only from spec; preserves original templates.')
    a=p.parse_args();s=read(a.spec);t=build(s,(a.width,a.height)); dest=a.spec.parent/('guides-v2' if a.contour_guide else 'templates');dest.mkdir(exist_ok=True)
    for view in t['views']:
        image=draw_contour_guide(s,t,view) if a.contour_guide else draw(s,t,view)
        image.save(dest/f'{s["key"].lower()}-{view}-template.png')
    if a.contour_guide:write(dest/'guide.json',dict(schema='unmatched.scratch-guide/1',source='spec.json',purpose='generation input only; not approved view',template=t))
    else:write(a.spec.with_name('template.json'),t)
    print('scale',t['px_per_cm'],'baseline',t['baseline_px'])

if __name__=='__main__':main()
