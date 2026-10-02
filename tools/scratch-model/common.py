"""Shared deterministic 2D measurements; centimetres, Blender axes, CIE Lab D65.

Imported by check_spec.py, make_template.py, register_views.py and check_views.py.
Requires Python 3, numpy, scipy and Pillow. No network or 3D geometry.
"""
import json
from pathlib import Path
import numpy as np
from PIL import Image
from scipy import ndimage

BACKGROUND = '#B4B4B4'
GRID = '#00C8FF'

def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8-sig'))

def write(path, data):
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text(json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True, allow_nan=False)+'\n', encoding='utf-8')

def rgb(hex_value):
    return np.array([int(hex_value[i:i+2], 16) for i in (1,3,5)])

def lab(values):
    a = np.asarray(values, dtype=float)/255
    linear = np.where(a <= .04045, a/12.92, ((a+.055)/1.055)**2.4)
    xyz = linear @ np.array([[.4124564,.3575761,.1804375],[.2126729,.7151522,.0721750],[.0193339,.1191920,.9503041]]).T
    xyz /= np.array([.95047,1,1.08883])
    f = np.where(xyz > (6/29)**3, np.cbrt(xyz), xyz/(3*(6/29)**2)+4/29)
    return np.stack([116*f[...,1]-16,500*(f[...,0]-f[...,1]),200*(f[...,1]-f[...,2])], axis=-1)

def check(passed, measured, expected, note=''):
    return dict(passed=bool(passed), measured=measured, expected=expected, note=note)

def report(path, checks, **extra):
    passed = all(x['passed'] for x in checks.values())
    data = dict(schema='unmatched.scratch-check/1', checks_passed=passed, checks=checks, **extra)
    write(path, data)
    return data

def image_array(path):
    return np.asarray(Image.open(path).convert('RGB'))

def silhouette(path, template):
    pixels = image_array(path)
    l = lab(pixels)
    selected = (np.linalg.norm(l-lab(rgb(BACKGROUND)),axis=-1)>12) & (np.linalg.norm(l-lab(rgb(GRID)),axis=-1)>12)
    # Exclude only the known registration and label gutters, never figure pixels.
    w,h = template['canvas_px']
    for x,y in template['registration_marks_px']:
        yy,xx = np.ogrid[:h,:w]
        selected[(xx-x)**2+(yy-y)**2<=22**2]=False
    selected[:,template['label_start_px']:]=False
    labels,count = ndimage.label(selected)
    sizes = np.bincount(labels.ravel()); sizes[0]=0
    large = [int(v) for v in sizes[1:] if v>=max(100, int(sizes.max()*.001))]
    mask = ndimage.binary_fill_holes(labels==int(sizes.argmax())) if count else selected
    return mask, large, pixels

def project(point, view, t):
    x,y,z=point
    horizontal={'front':x,'back':-x,'side':y}[view]
    return t['center_px']+horizontal*t['px_per_cm'], t['baseline_px']-z*t['px_per_cm']

def weapon_region(spec, view, t):
    """Explicit pre-generation staff bounds; remove only for body measurements."""
    from PIL import ImageDraw
    im=Image.new('1',tuple(t['canvas_px']))
    d=ImageDraw.Draw(im)
    points=[project(p,view,t) for p in spec['weapon']['centerline_cm']]
    radius=spec['weapon']['shaft_radius_cm']*t['px_per_cm']
    d.line(points, fill=1, width=max(1,round(radius*2)))
    for x,y in points:
        d.ellipse((x-radius,y-radius,x+radius,y+radius), fill=1)
    cx,cy=project(spec['weapon']['crystal_center_cm'],view,t)
    rx=spec['weapon']['crystal_width_cm']/2*t['px_per_cm']
    ry=spec['weapon']['crystal_height_cm']/2*t['px_per_cm']
    d.rectangle((cx-rx,cy-ry,cx+rx,cy+ry),fill=1)
    return np.asarray(im,dtype=bool)

def row_width(mask, row):
    xs=np.flatnonzero(mask[min(mask.shape[0]-1,max(0,int(round(row))))])
    return int(xs[-1]-xs[0]+1) if xs.size else 0
