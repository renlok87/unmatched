"""IC-37 isolated extension of the byte-identical v3 snapshot. No source writes."""
from __future__ import annotations
import io
import math
from pathlib import Path
import cairo
import numpy as np
from PIL import Image, ImageFilter
import draw_icons_v3_snapshot as v3

PACKAGE = Path(__file__).resolve().parents[1]
SIZES = (1024, 16, 21, 24, 32, 48, 64, 96)
KEYS = ('gray', 'green', 'blue', 'violet', 'purple', 'red', 'brown', 'yellow')
COLORS = {'navy': '#061623', 'cream': '#F9EBDB', 'glyph': '#FAF8F2', 'keyline': '#111317', 'neutral': '#808080', 'white': '#FFFFFF'}
BOARDS = {
    'marmoreal': dict(zip(KEYS, ('#DEDEE0','#5EA66F','#4E84A1','#9187A9','#904A80','#D39BA5','#9A6D5D','#D5BD8A'))),
    'sarpedon': {'green':'#2F8564','blue':'#90AABB','yellow':'#DCC88E','red':'#A43839','purple':'#B182A2','brown':'#8C6034'},
}

def rgba(h):
    return tuple(int(h[i:i+2],16) for i in (1,3,5)) + (255,)

def luminance(h):
    c = np.array(rgba(h)[:3], dtype=float)/255
    c = np.where(c <= .04045, c/12.92, ((c+.055)/1.055)**2.4)
    return float(c @ [.2126,.7152,.0722])

def contrast(a,b):
    x,y = sorted((luminance(a),luminance(b)))
    return (y+.05)/(x+.05)

def ink(disc):
    return max((COLORS['navy'],COLORS['glyph']),key=lambda c:contrast(c,disc))

def gray(im):
    a = np.asarray(im.convert('RGBA')).copy()
    y = np.floor(a[:,:,:3] @ np.array([.2126,.7152,.0722]) + .5).astype(np.uint8)
    a[:,:,:3] = y[:,:,None]
    return Image.fromarray(a)

def surface(size):
    s = cairo.ImageSurface(cairo.FORMAT_ARGB32,size,size)
    ctx = cairo.Context(s)
    ctx.scale(size/32,size/32)
    # Exact flat print palette, with native pixel snapping and no downscaling.
    ctx.set_antialias(cairo.ANTIALIAS_NONE)
    return s,ctx,v3.Spec(size)

def pil(s):
    b = io.BytesIO()
    s.write_to_png(b)
    return Image.open(io.BytesIO(b.getvalue())).convert('RGBA')

def white(ctx):
    ctx.set_source_rgba(1,1,1,1)
    ctx.fill()

def rect(ctx,sp,x,y,w,h):
    x0,y0,x1,y1=map(sp.snap,(x,y,x+w,y+h))
    ctx.rectangle(x0,y0,x1-x0,y1-y0)

def path(ctx,sp,commands):
    for cmd,pts in commands:
        pts=[sp.snap(n) for n in pts]
        {'M':ctx.move_to,'L':ctx.line_to,'C':ctx.curve_to}[cmd](*pts)
    ctx.close_path()

def gray_glyph(ctx,sp):
    rect(ctx,sp,11.75,11.75,8.5,8.5)
    white(ctx)

def green_glyph(ctx,sp):
    # Pointed almond tilted -45 degrees, no stem (avoids a diamond silhouette).
    path(ctx,sp,[('M',[11.5,20.5]),('C',[11.5,14.5,14.5,11.5,20.5,11.5]),('C',[20.5,17.5,17.5,20.5,11.5,20.5])])
    white(ctx)
    if sp.detail>1:
        # One negative midrib, removed rather than thinned at 16/21/24/32.
        w=sp.pxu(1.5)
        ctx.move_to(sp.snap(13),sp.snap(19))
        ctx.line_to(sp.snap(19),sp.snap(13))
        ctx.set_line_width(w)
        ctx.set_line_cap(cairo.LINE_CAP_BUTT)
        ctx.set_operator(cairo.OPERATOR_CLEAR)
        ctx.stroke()
        ctx.set_operator(cairo.OPERATOR_OVER)

def blue_glyph(ctx,sp):
    # Two filled ribbons, no stroke-on-fill seam. W is pixel-snapped 2.25 u.
    w=sp.W
    for cy in (12,20):
        path(ctx,sp,[('M',[10.5,cy-w/2]),('C',[12.3,cy-w/2-.75,14.2,cy-w/2-.75,16,cy-w/2]),('C',[17.8,cy-w/2+.75,19.7,cy-w/2+.75,21.5,cy-w/2]),('L',[21.5,cy+w/2]),('C',[19.7,cy+w/2+.75,17.8,cy+w/2+.75,16,cy+w/2]),('C',[14.2,cy+w/2-.75,12.3,cy+w/2-.75,10.5,cy+w/2])])
        white(ctx)

def violet_glyph(ctx,sp):
    v3.circle(ctx,sp.snap(17.25),sp.snap(16),sp.snap(5.25))
    white(ctx)
    v3.circle(ctx,sp.snap(19.75),sp.snap(16),sp.snap(4.5))
    v3.clear(ctx)

def purple_glyph(ctx,sp):
    # Gate, curved outside and deliberately square-cut inside (task A wins).
    path(ctx,sp,[('M',[11,21]),('L',[11,16]),('C',[11,9.333333,21,9.333333,21,16]),('L',[21,21])])
    white(ctx)
    rect(ctx,sp,13.75,15.25,4.5,7)
    v3.clear(ctx)

def red_glyph(ctx,sp):
    path(ctx,sp,[('M',[16.8,9.5]),('C',[16.4,12.15,14.1,12.55,13.3,14.45]),('C',[10.9,17.85,13.2,20,16,20]),('C',[19.5,20,21.1,17.45,18.7,14.15]),('C',[18.9,16.05,17.1,16.35,17.2,14.35]),('C',[17.3,12.65,16.7,10.95,16.8,9.5])])
    white(ctx)
    if sp.detail>1:
        path(ctx,sp,[('M',[16.2,15.35]),('C',[16.1,16.35,14.8,16.85,14.8,17.75]),('C',[14.8,19.55,17.5,19.55,17.5,17.75]),('C',[17.5,17.05,16.8,16.15,16.2,15.35])])
        v3.clear(ctx)

def brown_glyph(ctx,sp):
    # Wide flat top and base; no triangular apex.
    p=[(10,19.5),(13.25,12.5),(18.75,12.5),(22,19.5)]
    v3.Poly([(sp.snap(x),sp.snap(y)) for x,y in p],[0,sp.pxu(1),sp.pxu(1),0]).path(ctx)
    white(ctx)

def yellow_glyph(ctx,sp):
    # Composite of three discs, never a single circle or triangular fill.
    for x,y in [(16,12.5),(12.5,18.562178),(19.5,18.562178)]:
        v3.circle(ctx,sp.snap(x),sp.snap(y),sp.pxu(1.5))
    white(ctx)

CANDIDATES = {
    'zone-'+key: {'variant':'A','draw':fun,'box_u':13}
    for key,fun in zip(KEYS,(gray_glyph,green_glyph,blue_glyph,violet_glyph,purple_glyph,red_glyph,brown_glyph,yellow_glyph))
}

def glyph_mask(key,size):
    s,ctx,sp=surface(size)
    CANDIDATES['zone-'+key]['draw'](ctx,sp)
    return pil(s).getchannel('A')

def colored(mask,color):
    im=Image.new('RGBA',mask.size,rgba(color))
    im.putalpha(mask)
    return im

def layers(key,size):
    s,ctx,sp=surface(size)
    sil=v3.rect_sil(sp.M,sp.M,32-2*sp.M,32-2*sp.M,sp.pxu(1.5))
    v3.token(ctx,sil,sp)
    v3.circle(ctx,16,16,sp.snap(11)+sp.rim)
    v3.fill(ctx,v3.hx(COLORS['cream']))
    # Transparent center allows tinting the isolated disc below this layer.
    v3.circle(ctx,16,16,sp.snap(11))
    v3.clear(ctx)
    body=pil(s)
    s,ctx,sp=surface(size)
    v3.circle(ctx,16,16,sp.snap(11))
    white(ctx)
    disc=pil(s)
    mask=glyph_mask(key,size)
    outline=mask.filter(ImageFilter.MaxFilter(3))
    glyph=colored(outline,COLORS['keyline'])
    glyph.alpha_composite(colored(mask,COLORS['white']))
    return body,disc,glyph

def render(key,size,disc_color=None):
    dc=disc_color or BOARDS['marmoreal'][key]
    body,disc,glyph=layers(key,size)
    out=colored(disc.getchannel('A'),dc)
    out.alpha_composite(body)
    mask=glyph_mask(key,size)
    out.alpha_composite(colored(mask.filter(ImageFilter.MaxFilter(3)),COLORS['keyline']))
    out.alpha_composite(colored(mask,ink(dc)))
    return out

def save(im,path):
    path=PACKAGE/path
    path.parent.mkdir(parents=True,exist_ok=True)
    im.save(path)

def build():
    for size in SIZES:
        for key in KEYS:
            stem=f'vector/{size}/zone-{key}'
            body,disc,glyph=layers(key,size)
            for suffix,im in [('',render(key,size)),('_body',body),('_disc',disc),('_glyph',glyph)]:
                save(im,Path(stem+suffix+'.png'))
                save(gray(im),Path(stem+suffix+'-gray.png'))
            if key in BOARDS['sarpedon']:
                im=render(key,size,BOARDS['sarpedon'][key])
                save(im,Path(stem+'-sarpedon.png'))
                save(gray(im),Path(stem+'-sarpedon-gray.png'))

if __name__=='__main__':
    build()
