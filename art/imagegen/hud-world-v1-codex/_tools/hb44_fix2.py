"""Six bounded HB-44.fix2 corrections. No engine, git, network or installs."""
import json
import math
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw
from scipy import ndimage as ndi

B = F = None
ACTORS = {}
TAG_LAYOUTS = {}
NUMBER_CACHE = {}


def tag_layout(actor, scale):
    maximum = actor['startHealth']
    # Allocate the largest actual glyph bounds at either required native UI size.
    text_width = max(math.ceil(B.font(14*s).getbbox(f'{maximum}/{maximum}')[2]/s)
                     for s in [1, 1.125])
    x = 12
    items = {'chip': [x, 8, x+24, 32]}
    x += 24+6
    if actor.get('digit'):
        items['digit'] = [x, 12, x+16, 28]
        x += 16+6
    items['hp_bar'] = [x, 18, x+40, 22]
    x += 40+8
    items['hp_text_slot'] = [x, 0, x+text_width, 40]
    return {'width_su': x+text_width+12, 'height_su': 40, 'padding_su': 12,
            'elements_su': items,
            'gaps_su': dict(zip(['chip_to_digit', 'digit_to_bar', 'bar_to_text']
                               if actor.get('digit') else ['chip_to_bar', 'bar_to_text'],
                               [6, 6, 8] if actor.get('digit') else [6, 8])),
            'vertical_center_su': 20}


def tag(c, actor, hp, xy, key, maskset=None):
    s = c.scale; x, y = xy; layout = tag_layout(actor, s)
    width = layout['width_su']; box = [x-width*s/2, y, x+width*s/2, y+40*s]
    c.panel(box, 'tag.'+key, 8, True)
    x0 = box[0]; items = layout['elements_su']
    chip = items['chip']; c.chip((x0+(chip[0]+12)*s, y+20*s), actor['team'], 24)
    if actor.get('digit'):
        disc = items['digit']; d = ImageDraw.Draw(c.im)
        d.ellipse([x0+disc[0]*s, y+12*s, x0+disc[2]*s, y+28*s],
                  fill=B.rgb('card.navy')+(255,), outline=B.rgb('card.cream')+(255,),
                  width=max(1, round(s)))
        c.text((x0+(disc[0]+8)*s, y+20*s), str(actor['digit']), 14,
               'card.cream', center=True, cap=10)
    bar = items['hp_bar']; bx = x0+bar[0]*s
    d = ImageDraw.Draw(c.im)
    d.rectangle([bx, y+18*s, bx+40*s, y+22*s], fill=B.rgb('hp.back')+(255,))
    d.rectangle([bx, y+18*s, bx+40*s*hp/actor['startHealth'], y+22*s],
                fill=B.rgb('hp.fill')+(255,))
    value = f"{hp}/{actor['startHealth']}"; textx = x0+items['hp_text_slot'][0]*s
    bounds = B.font(14*s).getbbox(value); ink = bounds[2]-bounds[0]
    c.text((textx+ink/2, y+20*s), value, 14, center=True)
    c.panels[-1]['interior'] = dict(layout,
        elements_px={k:[x0+a[0]*s,y+a[1]*s,x0+a[2]*s,y+a[3]*s] for k,a in items.items()},
        hp_text_ink_width_px=ink, hp_text_right_padding_su=(box[2]-textx-ink)/s)
    return box


def place_tag(board, key, w, h, s, maskset, existing):
    cache = (board, key, w, h, s)
    width = tag_layout(ACTORS[key], s)['width_su']*s
    def mask(x, y):
        m = Image.new('1', (w, h))
        ImageDraw.Draw(m).rounded_rectangle([x-width/2-s, y-s, x+width/2+s, y+41*s],
                                           radius=9*s, fill=1)
        return m
    if cache in B.ANCHOR_CACHE:
        x, y = B.ANCHOR_CACHE[cache]; existing.append(mask(x, y)); return x, y
    bx, _ = F.GEO[board]['bases'][key]; f = F.GEO[board]['figures'][key]
    cx = bx*w/1920; top = (f[3]+7)*h/1080; candidates = []
    for dy in range(0, 181, 6):
        for dx in [0]+[v for a in range(12, 241, 12) for v in [-a, a]]:
            x = cx+dx; y = top+dy
            crop = [math.floor(x-width/2-s), math.floor(y-s),
                    math.ceil(x+width/2+s)+1, math.ceil(y+41*s)+1]
            if crop[0]<12 or crop[2]>w-12 or crop[3]>h-12: continue
            if any(maskset[n].crop(crop).getbbox() for n in ['figures', 'seams']): continue
            if any(m.crop(crop).getbbox() for m in existing): continue
            candidates.append((dy*2+abs(dx), x, y))
        if candidates and (dy+6)*2 >= min(t[0] for t in candidates): break
    if not candidates: raise RuntimeError('No tag '+board+' '+key)
    _, x, y = min(candidates); B.ANCHOR_CACHE[cache] = (x, y)
    existing.append(mask(x, y)); return x, y


def figures(board, w, h):
    return {k: np.array(v)*[w/1920, h/1080, w/1920, h/1080]
            for k, v in F.GEO[board]['figures'].items()}


def distances(box, fs):
    return {k: float(math.hypot(max(f[0]-box[2], box[0]-f[2], 0),
                               max(f[1]-box[3], box[1]-f[3], 0))) for k, f in fs.items()}


def example(c, xy, lang='ru'):
    x, y = xy; s = c.scale
    value = F.STRINGS['hud.number.example'][0 if lang=='ru' else 1]
    bounds = B.font(14*s).getbbox(value); tw = bounds[2]-bounds[0]
    left = x+32*s; width = tw+24*s
    c.panel([left, y-18*s, left+width, y+18*s], 'example.label', 4, True)
    c.text((left+12*s+tw/2, y), value, 14, center=True)
    return width/s


def number_anchor(b, board, key, w, h, s, ms, panels):
    cache = (board, key, w, h, s)
    if cache in NUMBER_CACHE: return NUMBER_CACHE[cache]
    fs = figures(board, w, h); f = fs[key]
    preferred = np.array([(f[0]+f[2])/2, f[1]-24*s])
    ew = 0
    if key=='arthur':
        bounds = b.font(14*s).getbbox('пример'); ew = 4*s+bounds[2]-bounds[0]+24*s
    oa = np.array(ms['figures']).copy()
    for p in panels: oa |= np.array(p['mask'])
    sat = np.pad(oa.astype(np.int32), ((1, 0), (1, 0))).cumsum(0).cumsum(1)
    # Reserve the entire moving row and keyline, not just the start capsule.
    xs = np.arange(math.ceil(30*s), math.floor(w-30*s-ew), dtype=float)
    best = None
    for y in range(math.ceil(43*s), math.floor(h-20*s)):
        x0 = np.floor(xs-29*s).astype(int); x1 = np.ceil(xs+29*s+ew).astype(int)+1
        y0 = math.floor(y-43*s); y1 = math.ceil(y+19*s)+1
        legal = (sat[y1, x1]-sat[y0, x1]-sat[y1, x0]+sat[y0, x0])==0
        for rise in [0, 24*240/900, 24*540/900, 24*840/900, 24,
                     24*300/700, 24*600/700]:
            ds = {}
            for k, q in fs.items():
                dx = np.maximum(np.maximum(q[0]-(xs+28*s), xs-28*s-q[2]), 0)
                dy = max(q[1]-(y-rise*s+18*s), y-rise*s-18*s-q[3], 0)
                ds[k] = np.hypot(dx, dy)
            legal &= ds[key] < np.minimum.reduce([d for k, d in ds.items() if k!=key])-1e-6
        good = np.flatnonzero(legal)
        if not len(good): continue
        score = np.hypot(xs[good]-preferred[0], y-preferred[1])
        i = good[np.argmin(score)]; candidate = (float(score.min()), float(xs[i]), float(y))
        if best is None or candidate < best: best = candidate
    if best is None: raise RuntimeError('No attributed number trajectory '+board+' '+key)
    NUMBER_CACHE[cache] = best[1:]; return best[1:]


def place_plate(b, board, key, w, h, s, ms, panels):
    cache = (board, key, w, h, s, hash(np.asarray(ms['choice']).tobytes()))
    if cache in F.PLATE_CACHE: return F.PLATE_CACHE[cache]
    fs = figures(board, w, h); f = fs[key]; pw = 268*s; ph = 144*s
    oa = np.asarray(ms['figures']).copy() | np.asarray(ms['choice'])
    for p in panels: oa |= np.asarray(p['mask'])
    oa = ndi.binary_dilation(oa, iterations=math.ceil(s))
    sat = np.pad(oa.astype(np.int32), ((1, 0), (1, 0))).cumsum(0).cumsum(1)
    fallback = []; gx = (f[0]+f[2])/2; gy = (f[1]+f[3])/2
    for rank, direction in enumerate(['above', 'below', 'beside']):
        owned = []; alllegal = []
        for y in range(8, h-math.ceil(ph)-8):
            if direction=='above' and y+ph>f[1]-3: continue
            if direction=='below' and y<f[3]+3: continue
            if direction=='beside' and (y+ph<f[1] or y>f[3]): continue
            xs = np.arange(8, w-math.ceil(pw)-8); x1 = xs+math.ceil(pw)+1; y1 = y+math.ceil(ph)+1
            ok = (sat[y1,x1]-sat[y,x1]-sat[y1,xs]+sat[y,xs])==0
            if direction=='beside': ok &= (xs+pw<=f[0]-3) | (xs>=f[2]+3)
            cs = xs[ok]
            if not cs.size: continue
            ds = {}
            for k, q in fs.items():
                dx = np.maximum(np.maximum(q[0]-(cs+pw), cs-q[2]), 0)
                dy = max(q[1]-(y+ph), y-q[3], 0); ds[k] = np.hypot(dx, dy)
            align = abs(cs+pw/2-gx)+abs(y+ph/2-gy)
            good = ds[key] < np.minimum.reduce([d for k,d in ds.items() if k!=key])-1e-6
            for target, indices in [(alllegal,np.arange(len(cs))), (owned,np.flatnonzero(good))]:
                if len(indices):
                    i = indices[np.lexsort((align[indices],ds[key][indices]))[0]]
                    target.append((float(ds[key][i]), float(align[i]), int(cs[i]), y))
        if owned:
            distance, _, x, y = min(owned)
            ds = distances([x,y,x+pw,y+ph],fs)
            result = ([x,y], {'direction':direction, 'rule':'nearest-own-figure',
                      'target':key, 'nearest_figure':min(ds,key=ds.get), 'distances_px':ds,
                      'edge_distance_px':distance, 'edge_distance_su':distance/s,
                      'search_step_px':1, 'leader_required':distance>24*s})
            F.PLATE_CACHE[cache] = result; return result
        if alllegal and direction!='above':
            distance, align, x, y = min(alllegal)
            fallback.append((distance,rank,align,x,y,direction))
    if not fallback: raise RuntimeError('No legal plate '+board+' '+key)
    distance, _, _, x, y, direction = min(fallback)
    ds = distances([x,y,x+pw,y+ph],fs)
    result = ([x,y], {'direction':direction, 'rule':'leader-no-owned-legal-position',
              'target':key, 'nearest_figure':min(ds,key=ds.get), 'distances_px':ds,
              'edge_distance_px':distance, 'edge_distance_su':distance/s,
              'search_step_px':1, 'leader_required':True})
    F.PLATE_CACHE[cache] = result; return result


def leader(c, ms, panels, start, end):
    layer = Image.new('RGBA', c.im.size); d = ImageDraw.Draw(layer); s = c.scale
    d.line([start,end], fill=B.rgb('mark.keyline')+(255,), width=max(3,round(3*s)))
    d.line([start,end], fill=B.rgb('card.cream')+(255,), width=max(1,round(s)))
    pixels = np.array(layer); blocked = np.array(ms['figures']).copy()
    for p in panels: blocked |= np.array(p['mask'])
    count = int(np.count_nonzero((pixels[:,:,3]>0)&blocked))
    pixels[blocked,3] = 0; c.im = Image.alpha_composite(c.im,Image.fromarray(pixels))
    return count


def number_check(board, key, xy, rise, s, w, h, visible):
    x,y = xy; y -= rise*s; box = [x-28*s,y-18*s,x+28*s,y+18*s]
    ds = distances(box, figures(board,w,h)); nearest = min(ds,key=ds.get)
    return {'target':key, 'visible':visible, 'box_px':box, 'rise_su':rise,
            'distances_px':ds, 'nearest_figure':nearest, 'passed':nearest==key}


def install(b, f):
    global B, F, ACTORS
    B, F = b, f; ACTORS = b.data()[0]
    b.tag = tag; b.place_tag = place_tag
    b.tag_layout = tag_layout
    f.number_anchor = number_anchor; f.place_plate = place_plate
    f.example = example; f.leader = leader; f.number_check = number_check
    f.finalize = finalize
    audit = b.DERIVED/'audit'; audit.mkdir(exist_ok=True)
    for name in ['scope-audit-before.json', 'scope-audit-after.json']:
        old = b.PKG/name
        if old.exists():
            dest = audit/name
            if dest.exists():
                if b.sha(old)!=b.sha(dest): raise RuntimeError('Audit move destination differs: '+name)
                old.unlink()
            else: old.rename(dest)
    original_geometry = f.geometry
    def geometry(b, board):
        original_geometry(b,board)
        f.GEO[board]['tag_interior'] = {k:tag_layout(v,1) for k,v in ACTORS.items()}
        f.GEO[board]['tag_interior_configs'] = {res+'-'+ui:{k:dict(tag_layout(v,dpi*app),su_to_px=dpi*app)
                                                      for k,v in ACTORS.items()}
                                              for res,ui,w,h,dpi,app in b.CONFIGS}
    f.geometry = geometry


def finalize(b, v):
    # Iterate only small metadata until its own reported byte count is exact.
    for _ in range(8):
        size = sum(p.stat().st_size for p in b.PKG.rglob('*') if p.is_file())
        v['package_size'] = {'bytes':size,'budget_bytes':30000000,'passed':size<=30000000}
        v['checks']['package_size_max_30_mb'] = size<=30000000
        b.save_json(b.PKG/'verification.json',v)
        F.readme(b,v); F.manifests(b)
        if sum(p.stat().st_size for p in b.PKG.rglob('*') if p.is_file())==size: break
    else: raise RuntimeError('Package size metadata did not converge')
    assert v['package_size']['passed'],v['package_size']
