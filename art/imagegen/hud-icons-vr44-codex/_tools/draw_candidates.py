"""IC-36: local extension of the byte-identical v3 snapshot. No v3 build()."""
import sys
sys.dont_write_bytecode = True
import math
import cairo
import numpy as np
from PIL import Image
import draw_icons_v3_snapshot as v3

PALETTE = ['#061623','#F9EBDB','#FAF8F2','#111317']
SIZES = [1024,16,21,24,32,48,64,96]
HOTSPOT_U = (11,2)

def polygon(ctx, sp, pts, col=None):
    v3.poly(ctx, [(sp.sx(x),sp.sy(y)) for x,y in pts])
    v3.fill(ctx,col or v3.C['glyph'])

def rect(ctx, sp, x,y,w,h,col=None):
    ctx.rectangle(sp.sx(x),sp.sy(y),sp.pxu(w),sp.pxu(h))
    v3.fill(ctx,col or v3.C['glyph'])

def g_end_turn(ctx,sp):
    top=sp.sy(-sp.W/2); bot=top+sp.W
    # Union as one filled path: shaft and head never introduce a seam.
    polygon(ctx,sp,[(-8,top),(-1.25,top),(-1.25,-3.5),(3.25,0),
                     (-1.25,3.5),(-1.25,bot),(-8,bot)])
    rect(ctx,sp,4.75,-6,2.25,12)

def draw_end_turn(ctx,sp):
    v3.token(ctx,v3.disc_sil(sp),sp)
    v3.glyph(ctx,sp,16,16,lambda:g_end_turn(ctx,sp))

def g_card_drop(ctx,sp):
    left=sp.sx(-sp.W/2); right=left+sp.W
    polygon(ctx,sp,[(left,-9.5),(right,-9.5),(right,-4.5),(3.5,-4.5),
                    (0,-.5),(-3.5,-4.5),(left,-4.5)])
    h=sp.pxu(3) if sp.detail else 1/sp.k
    gap=sp.pxu(1)
    top=sp.sy(1.5)
    for i in range(2):
        y=top+i*(h+gap)
        polygon(ctx,sp,[(-4,y),(7.5,y),(4,y+h),(-7.5,y+h)])

def draw_card_drop(ctx,sp):
    v3.token(ctx,v3.sq_sil(sp),sp)
    v3.glyph(ctx,sp,16,16,lambda:g_card_drop(ctx,sp))

def log_rects(sp):
    xpx=sp.px(8.375); bwpx=sp.px(2.75); gap=sp.px(1.5)
    center=sp.px(16); pitch=sp.px(4.5)
    centers=([sp.px(13),sp.px(19)] if sp.detail == 0 else [center-pitch,center,center+pitch])
    # Integer pixel arithmetic avoids half-pixel float ties collapsing the last
    # bullet gap at 21 px. Same snapped pitch for both bullets and lines.
    for cy in centers:
        yield (xpx/sp.k,(cy-bwpx//2)/sp.k,bwpx/sp.k,bwpx/sp.k)
        yield ((xpx+bwpx+gap)/sp.k,(cy-sp.px(2.25)//2)/sp.k,sp.pxu(11),sp.W)

def g_log(ctx,sp):
    # Absolute snapping, translated by glyph(); no per-line keyline or seam.
    for x,y,w,h in log_rects(sp): ctx.rectangle(x-16,y-16,w,h)
    v3.fill(ctx,v3.C['glyph'])

def draw_log(ctx,sp):
    v3.token(ctx,v3.disc_sil(sp),sp)
    v3.glyph(ctx,sp,16,16,lambda:g_log(ctx,sp))

# Prototype upper hand retained. Long/oblique wrist edges become short 45-degree
# chamfers (3*sqrt(2) u each); all other edges are horizontal or vertical.
HAND = [(7,2),(15,2),(15,11),(20,11),(20,13),(24,13),(24,15),
        (28,15),(28,27),(25,30),(11,30),(8,27),(8,25),(5,22),
        (3,22),(3,17),(7,17)]

def draw_pointer(ctx,sp):
    # Offset of one silhouette; cursor keyline is the explicit 2-u exception.
    pts=[(sp.snap(x),sp.snap(y)) for x,y in HAND]
    sil=v3.Poly(pts,[0]*len(pts))
    sil.path(ctx); v3.fill(ctx,v3.C['keyline'])
    sil.path(ctx,sp.pxu(2)); v3.fill(ctx,v3.C['glyph'])
    # Folded fingers are carried by the outer knuckles. No decorative creases:
    # an isolated black slot looked like a hole at 48/64, so it was removed.

def draw_menu(ctx,sp):
    for cy in [11.5,16,20.5]:
        x,y,w,h=sp.snap(8),sp.snap(cy-sp.W/2),sp.pxu(16),sp.W
        ctx.rectangle(x-sp.K,y-sp.K,w+2*sp.K,h+2*sp.K)
        v3.fill(ctx,v3.C['keyline'])
        ctx.rectangle(x,y,w,h); v3.fill(ctx,v3.C['glyph'])

def draw_arrow(ctx,sp):
    pts=[(5,3),(5,26),(11,21),(15,29),(19,27),(15,19),(23,19)]
    sil=v3.Poly([(sp.snap(x),sp.snap(y)) for x,y in pts],[0]*7)
    sil.path(ctx);v3.fill(ctx,v3.C['keyline'])
    sil.path(ctx,sp.pxu(2));v3.fill(ctx,v3.C['glyph'])

CANDIDATES={
 'end-turn':(draw_end_turn,{},False),
 'card-drop':(draw_card_drop,{},False),
 'log':(draw_log,{},False),
 'pointer':(draw_pointer,{},False),
}
v3.CANDIDATES.update(CANDIDATES)

def exact_palette(im):
    """Palette-rendering stage: coverage alpha kept; RGB assigned to token roles.
    Cairo blends internal opaque boundaries. Assign nearest token to those edge
    samples as well, so every opaque RGB is exact. Generated concepts untouched.
    """
    a=np.array(im)
    colours=np.array([tuple(round(c*255) for c in v3.hx(h)) for h in PALETTE],dtype=np.int32)
    flat=a[...,:3].reshape(-1,3).astype(np.int32)
    indices=((flat[:,None,:]-colours[None,:,:])**2).sum(2).argmin(1)
    a[...,:3]=colours[indices].reshape(a.shape[0],a.shape[1],3)
    return Image.fromarray(a,'RGBA')

def render(name,size):
    sp=v3.Spec(size)
    surf,ctx=v3.surface(size,size)
    ctx.scale(sp.k,sp.k)
    if name in CANDIDATES: CANDIDATES[name][0](ctx,sp)
    elif name=='menu': draw_menu(ctx,sp)
    elif name=='plain-arrow': draw_arrow(ctx,sp)
    else: return v3.render(name,size)
    im=v3.to_pil(surf)
    if name=='pointer':
        # The cursor has two roles only. Quantize Cairo's inner AA samples
        # against those roles before the unchanged shared palette stage.
        a=np.array(im)
        tones=np.array([[17,19,23],[250,248,242]],dtype=np.int32)
        rgb=a[...,:3].astype(np.int32)
        ix=((rgb[:,:,None,:]-tones[None,None,:,:])**2).sum(3).argmin(2)
        a[...,:3]=tones[ix]
        im=Image.fromarray(a,'RGBA')
    return exact_palette(im)

def gray(im):
    a=np.array(im.convert('RGBA'))
    l=np.floor(a[...,:3].astype(float)@np.array([.2126,.7152,.0722])+.5).astype(np.uint8)
    a[...,:3]=l[...,None]
    return Image.fromarray(a,'RGBA')

def features(size):
    sp=v3.Spec(size)
    boxes=list(log_rects(sp))
    return {'W_px':sp.px(2.25),'keyline_px':sp.px(1),
            'edge_px':sp.px(1.25),'cursor_keyline_px':sp.px(2),
            'log_bullet_px':sp.px(2.75),'log_bullet_line_gap_px':sp.px(1.5),
            'log_line_vertical_gap_px':min(round((boxes[i+2][1]-(boxes[i][1]+boxes[i][3]))*sp.k) for i in range(1,len(boxes)-2,2)),
            'log_bullet_vertical_gap_px':min(round((boxes[i+2][1]-(boxes[i][1]+boxes[i][3]))*sp.k) for i in range(0,len(boxes)-2,2)),
            'log_rows':len(boxes)//2,
            'end_turn_tip_bar_gap_px':round((sp.snap(20.75)-sp.snap(19.25))*sp.k),
            'card_stack_gap_px':sp.px(1),'card_stack_plate_px':sp.px(3) if sp.detail else 1,
            'optional_pointer_crease':False}
