"""EN-04 procedural masks. Writes only the two task-authorised package roots.

Run from any directory with python -B: build_masks.py build|sheets|verify.
No provider, subprocess, Git, Unreal or icon-generator imports.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import time
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont
from scipy import ndimage as ndi

ROOT = Path(__file__).resolve().parents[4]
PKG = ROOT / 'art/imagegen/env-u16-marmoreal-codex'
IMG = ROOT / 'scraped-data/derived/env-u16-marmoreal-codex'
SIZE = (4680, 2634)
OFFSET = np.array([668., 376.])
SCALE = 1672 / 1920
NAMES = ('lantern-alpha', 'lantern-glow', 'sakura', 'mist', 'petals')
COLOURS = ((255, 176, 64), (255, 240, 96), (248, 96, 212), (80, 208, 255), (192, 128, 255))
FRAME_CONCEPT = [(387, 208), (1278, 208), (1366, 765), (305, 765)]
DOOR_CONCEPT = [(803, -30), (867, -30), (867, 99), (803, 99)]
# Tight regions of the painted glass, measured in the original EN-01 pixel space.
# These are not the centres of the much larger pools on foliage/paving.
GLASS = {
    'lantern-nw': [(407, 77), (444, 74), (441, 111), (410, 110)],
    'lantern-ne': [(1226, 79), (1267, 78), (1264, 113), (1227, 112)],
    'lantern-w': [(132, 486), (179, 485), (176, 528), (136, 525)],
    'lantern-e': [(1507, 489), (1553, 490), (1548, 530), (1508, 528)],
    'sconce-door-w': [(782, 13), (794, 13), (794, 39), (782, 39)],
    'sconce-door-e': [(871, 13), (881, 13), (881, 41), (869, 41)],
}
PORTAL = [(818, -18), (851, -18), (851, 22), (818, 22)]
# Concept-pixel paths of visible woody cores. Pigment-only HSV selection can
# select magenta reflected highlights on bark; these paths remove that leakage.
# Widths are concept pixels, drawn at x2 without modifying the source painting.
WOODY_PATHS = [
    ([(-1,507),(-22,477),(-34,449),(-29,421),(-17,392),(-8,370),(-18,330),(-17,290),(-11,254),(-10,218)],38),
    ([(-32,422),(-9,398),(11,379),(39,368),(75,357),(108,357)],16),
    ([(-29,421),(-51,405),(-72,382),(-90,361)],7),
    ([(-16,294),(10,271),(38,261),(63,260),(91,253)],7),
    ([(-17,269),(-43,246),(-61,218),(-82,192)],7),
    ([(-14,341),(-43,338),(-67,332),(-83,324)],6),
    ([(1660,582),(1654,552),(1644,526),(1651,488),(1665,455),(1685,428),(1708,403),(1730,387)],32),
    ([(1646,527),(1622,522),(1600,509),(1575,488),(1556,466)],16),
    ([(1668,452),(1656,420),(1642,399),(1622,388),(1600,374),(1574,354)],14),
    ([(1642,399),(1653,370),(1653,337),(1644,313)],8),
    ([(1665,455),(1696,446),(1728,425),(1758,415)],6),
]
SHARED_MUTATIONS = {'README.md', 'source-hashes-before.json', 'verification.json',
                    'generation-records.json', 'manifest-sha256.json'}


def rel(p):
    return p.resolve().relative_to(ROOT).as_posix()


def sha(p):
    h = hashlib.sha256()
    with p.open('rb') as f:
        for b in iter(lambda: f.read(1024 * 1024), b''):
            h.update(b)
    return h.hexdigest()


def load(p):
    return json.loads(p.read_text(encoding='utf-8'))


def write_json(p, obj):
    assert p.resolve().is_relative_to(PKG)
    p.write_text(json.dumps(obj, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


def save_image(p, a):
    assert p.resolve().is_relative_to(IMG)
    p.parent.mkdir(parents=True, exist_ok=True)
    (a if isinstance(a, Image.Image) else Image.fromarray(a)).save(p, compress_level=6)


def plate_points(points, space='concept'):
    return np.asarray(points, np.float64) * (2 * SCALE if space == 'C0' else 2) + OFFSET


def polygon(points, space='concept'):
    a = Image.new('L', SIZE)
    ImageDraw.Draw(a).polygon([tuple(p) for p in plate_points(points, space)], fill=255)
    return np.asarray(a) > 0


def embed(a):
    out = np.zeros(SIZE[::-1], a.dtype)
    out[376:2258, 668:4012] = np.repeat(np.repeat(a, 2, axis=0), 2, axis=1)
    return out


def u8(a):
    return np.clip(np.rint(a), 0, 255).astype('uint8')


def linear_y(a):
    v = a.astype(np.float32) / 255
    v = np.where(v <= .04045, v / 12.92, ((v + .055) / 1.055) ** 2.4)
    return v @ np.array([.2126, .7152, .0722], np.float32)


def gray(a):
    # Display grayscale: Rec.709 luma of encoded sRGB, not Pillow's BT.601 L.
    g = u8(np.asarray(a)[..., :3].astype(np.float32) @ np.array([.2126, .7152, .0722], np.float32))
    return Image.fromarray(np.repeat(g[..., None], 3, axis=2))


def protection():
    field = embed(np.asarray(Image.open(IMG / 'marmoreal-field-mask.png')) > 0)
    frame = polygon(FRAME_CONCEPT)
    # Conservative: protect the complete painted frame and 40 px outside it.
    frame40 = ndi.distance_transform_edt(~frame) <= 40
    edge = np.zeros(SIZE[::-1], bool)
    edge[:40] = edge[-40:] = True
    edge[:, :40] = edge[:, -40:] = True
    return field, frame, frame40, edge, field | frame40 | edge


def regions():
    geom = load(ROOT / 'tools/art/concept_paste/marmoreal.paste.json')['geometry']
    crown = np.zeros(SIZE[::-1], bool)
    for z in geom['heightZones']:
        if z['id'] not in ('cherry-w', 'cherry-e'):
            continue
        crown |= polygon(z['poly'], 'C0')
        # Continue only the side of the polygon touching the original frame.
        # The continuation cannot consume central colonnade flowers or conifers.
        if z['id'] == 'cherry-w':
            extension = [(-384, 60), (0, 60), (0, 600), (-384, 600)]
        else:
            extension = [(1920, 120), (2304, 120), (2304, 640), (1920, 640)]
        crown |= polygon(extension, 'C0')
    cliff = next(z for z in geom['planeZones'] if z['id'] == 'front-cliff')
    # Extend the two sloping side edges of front-cliff down through the outpaint.
    pts = np.array(cliff['poly'], np.float64)
    left0, left1 = pts[0], pts[3]
    right0, right1 = pts[1], pts[2]
    bottom_c0_y = (SIZE[1] - 41 - OFFSET[1]) / (2 * SCALE)
    extrapolate = lambda a, b: a + (b - a) * ((bottom_c0_y - a[1]) / (b[1] - a[1]))
    cliff_cont = polygon([pts[0], pts[1], extrapolate(right0, right1), extrapolate(left0, left1)], 'C0')
    foot_y = float(plate_points([left1], 'C0')[0, 1])
    return crown, cliff_cont, foot_y


def chroma_support(clean, crown):
    v = clean.astype(np.float32) / 255
    hi, lo = v.max(axis=2), v.min(axis=2)
    delta = hi - lo
    safe = np.maximum(delta, 1e-8)
    r, g, b = v[..., 0], v[..., 1], v[..., 2]
    h = np.zeros(delta.shape, np.float32)
    take = (hi == r) & (delta > 0)
    h[take] = ((g[take] - b[take]) / safe[take]) % 6
    take = (hi == g) & (hi != r) & (delta > 0)
    h[take] = (b[take] - r[take]) / safe[take] + 2
    take = (hi == b) & (hi != r) & (hi != g) & (delta > 0)
    h[take] = (r[take] - g[take]) / safe[take] + 4
    h *= 60
    s = delta / np.maximum(hi, 1e-8)
    woody = woody_support()
    return crown & (h >= 300) & (h <= 350) & (s >= .25) & ~woody, h, s


def woody_support():
    im = Image.new('L', SIZE)
    draw = ImageDraw.Draw(im)
    for points, width in WOODY_PATHS:
        draw.line([tuple(p) for p in plate_points(points)], fill=255, width=round(width*2), joint='curve')
    return np.asarray(im)>0


def bases():
    t = time.perf_counter()
    clean = np.asarray(Image.open(IMG / 'marmoreal-extended-2x.png'))
    lit = np.asarray(Image.open(IMG / 'marmoreal-lit-extended-2x.png'))
    assert clean.shape == lit.shape == (*SIZE[::-1], 3)
    field, frame, frame40, edge, protected = protection()
    crown, cliff, foot_y = regions()
    return clean, lit, protected, crown, cliff, foot_y, time.perf_counter() - t


def centre(weights, domain):
    ys, xs = np.nonzero(domain)
    w = weights[ys, xs].astype(np.float64)
    total = w.sum()
    if total <= 0:
        raise ValueError('No luminance in the measured emitter domain')
    return np.array([(xs * w).sum() / total, (ys * w).sum() / total]), float(total)


def build():
    clean, lit, protected, crown, cliff, foot_y, shared = bases()
    masks, timings = {}, {}

    def finish(name, a, started):
        a = u8(a)
        a[protected] = 0
        masks[name] = a
        save_image(IMG / f'marmoreal-mask-{name}.png', a)
        timings[name] = {'mask_and_png_seconds': round(time.perf_counter() - started, 4),
                         'with_shared_setup_seconds': round(time.perf_counter() - started + shared, 4)}
        print(name, timings[name], flush=True)

    t = time.perf_counter()
    src = np.asarray(Image.open(IMG / 'marmoreal-lantern-mask.png').resize((3344, 1882), Image.Resampling.BILINEAR))
    base = np.zeros(SIZE[::-1], np.float32)
    base[376:2258, 668:4012] = src
    # Additional plate-space 8 px finite feather; tails cannot enter the door.
    alpha = ndi.gaussian_filter(base, 8 / 3, truncate=3)
    door = polygon(DOOR_CONCEPT)
    alpha[door] = 0
    finish('lantern-alpha', alpha, t)

    t = time.perf_counter()
    delta_y = np.maximum(linear_y(lit) - linear_y(clean), 0)
    # All support is attributable to the six EN-01 emitters. Clip Lanczos ringing.
    supported = base > 0
    glow = delta_y * (masks['lantern-alpha'].astype(np.float32) / 255)
    glow[~supported | door] = 0
    peak = float(glow.max())
    if peak <= 0:
        raise ValueError('The EN-03 lit/clean pair contains no positive lantern difference')
    finish('lantern-glow', glow * (255 / peak), t)

    t = time.perf_counter()
    seed, _, _ = chroma_support(clean, crown)
    seed[protected] = False
    # Smooth only inside the pigment selection: feather cannot paint a dark branch.
    sakura = ndi.gaussian_filter(seed.astype(np.float32), 12 / 3, truncate=3) * 255
    sakura[~seed] = 0
    finish('sakura', sakura, t)

    t = time.perf_counter()
    y = np.arange(SIZE[1], dtype=np.float32)
    start, peak_y, stop = foot_y - 96, foot_y + 96, SIZE[1] - 41
    ramp = np.clip(np.minimum((y - start) / (peak_y - start),
                              (stop - y) / (stop - peak_y)), 0, 1)
    # Side feather is inward 32 px and respects the continued cliff trapezoid.
    side = np.clip(ndi.distance_transform_edt(cliff) / 32, 0, 1)
    finish('mist', ramp[:, None] * side * 255, t)

    t = time.perf_counter()
    # Exact grayscale disk dilation, separable into 49 horizontal segments.
    # This avoids an expensive 49x49 arbitrary-footprint filter at master size.
    src = masks['sakura']
    petals = np.zeros_like(src)
    for dy in range(-24, 25):
        dx = int(np.floor(np.sqrt(24 * 24 - dy * dy)))
        row = ndi.maximum_filter1d(src, size=2 * dx + 1, axis=1, mode='constant', cval=0)
        if dy < 0:
            np.maximum(petals[:dy], row[-dy:], out=petals[:dy])
        elif dy > 0:
            np.maximum(petals[dy:], row[:-dy], out=petals[dy:])
        else:
            np.maximum(petals, row, out=petals)
    finish('petals', petals, t)

    save_image(IMG / 'marmoreal-lanterns-2x.png', np.dstack([lit, masks['lantern-alpha']]))
    save_image(IMG / 'marmoreal-anim-2x.png', np.dstack([masks[n] for n in NAMES[1:]]))
    entries = []
    # Measure each glow centroid on glass, as requested; full-pool centroid is
    # also recorded so this restriction is explicit and reproducible.
    specs = load(PKG / '_tools/mask-spec.json')
    spot_names = {'nw': 'lantern-nw', 'ne': 'lantern-ne', 'sw': 'lantern-w',
                  'se': 'lantern-e', 'door-w': 'sconce-door-w', 'door-e': 'sconce-door-e'}
    spots = [(spot_names[n], np.array([x, y])) for n, x, y in specs['spots']]
    yy, xx = np.ogrid[:SIZE[1], :SIZE[0]]
    # Nearest emitter divides overlapping pools without attributing one to two lights.
    best = np.full(SIZE[::-1], np.inf, np.float32)
    owner = np.zeros(SIZE[::-1], np.uint8)
    for i, (_, xy) in enumerate(spots):
        p = plate_points([xy])[0]
        d = (xx - p[0]) ** 2 + (yy - p[1]) ** 2
        take = d < best
        best[take], owner[take] = d[take], i
    for i, (name, _) in enumerate(spots):
        glass = polygon(GLASS[name])
        p, weight = centre(masks['lantern-glow'], glass)
        pool = (masks['lantern-glow'] > 0) & (owner == i)
        full, _ = centre(masks['lantern-glow'], pool)
        ys, xs = np.nonzero(pool)
        radius = float(np.sqrt((xs - p[0]) ** 2 + (ys - p[1]) ** 2).max() / (2 * SCALE))
        concept = (p - OFFSET) / 2
        glass_ys, glass_xs = np.nonzero(glass)
        entries.append({'id': name, 'centre_plate_px': p.tolist(), 'centre_concept_px': concept.tolist(),
                        'centre_C0_px': (concept / SCALE).tolist(), 'radius_C0_px': radius,
                        'centroid_method': 'linear Rec.709 positive lit-clean difference, alpha-weighted, restricted to glass ROI',
                        'centroid_weight_u8': weight, 'glass_polygon_concept_px': GLASS[name],
                        'full_pool_centroid_plate_px': full.tolist(),
                        'glass_reference_concept_px': [float((glass_xs.min()+glass_xs.max()-2*OFFSET[0])/4),
                                                       float((glass_ys.min()+glass_ys.max()-2*OFFSET[1])/4)],
                        'animated': True})
    portal_roi = polygon(PORTAL)
    portal_y = linear_y(lit)
    # Fixed portal has no glow difference. Warm chroma rejects cool stone in ROI.
    warm = (lit[..., 0].astype(int) > lit[..., 2].astype(int) + 24) & portal_roi
    threshold = float(np.quantile(portal_y[warm], .80))
    core = warm & (portal_y >= threshold)
    p, weight = centre(portal_y, core)
    concept = (p - OFFSET) / 2
    entries.append({'id': 'portal', 'centre_plate_px': p.tolist(), 'centre_concept_px': concept.tolist(),
                    'centre_C0_px': (concept / SCALE).tolist(), 'radius_C0_px': 26 / SCALE,
                    'centroid_method': 'fallback: lit plate linear Rec.709 luminance, brightest warm 20% of portal ROI',
                    'glow_weight': float(masks['lantern-glow'][portal_roi].sum()),
                    'luminance_weight': weight, 'glass_polygon_concept_px': PORTAL,
                    'animated': False, 'limitation': 'The retained portal has no lit-clean difference and no lantern glass; a glow-mask centroid is undefined.'})
    medians = {}
    for n in ('sakura', 'mist'):
        rgb = np.median(clean[masks[n] > 0], axis=0)
        medians[n] = {'sRGB_u8': rgb.tolist(), 'sRGB_0_1': (rgb / 255).tolist(),
                      'hex': '#' + ''.join(f'{int(round(c)):02X}' for c in rgb),
                      'sample_pixels': int(np.count_nonzero(masks[n]))}
    write_json(PKG / 'lanterns.json', {'schema': 'unmatched.marmoreal.lantern-anchors/1', 'task': 'EN-04',
               'status': 'предложено', 'plate_size_px': list(SIZE), 'conceptRectPx': [668, 376, 3344, 1882],
               'coordinates': {'concept_per_C0': SCALE, 'plate_per_concept': 2, 'plate_offset_px': OFFSET.tolist()},
               'entries': entries, 'median_plate_sRGB': medians})
    write_json(PKG / '_tools/en04-build.json', {'shared_setup_seconds': shared, 'timings': timings,
               'glow_normalisation_peak_linear_Y': peak, 'mist_ramp_plate_y': [start, peak_y, stop],
               'algorithms': {'alpha': 'bilinear x2 + Gaussian sigma 8/3 truncate 3; protected regions and portal zero',
                              'glow': 'max(linear709(lit)-linear709(clean),0)*alpha; within EN-01 light support; peak normalised',
                              'sakura': 'clean HSV hue 300..350 saturation>=.25 in continued cherry zones; explicit woody cores removed; Gaussian sigma4 truncate3, reclip to pigment',
                              'mist': 'continued front-cliff; triangular vertical ramp; inward side feather32',
                              'petals': 'exact uint8 grayscale disk dilation radius24, protected regions reapplied'},
               'generations': 0})


def masks_from_disk():
    return {n: np.asarray(Image.open(IMG / f'marmoreal-mask-{n}.png')) for n in NAMES}


def font(size=20):
    return ImageFont.truetype('C:/Windows/Fonts/consola.ttf', size)


def overlay(plate, mask, colour):
    amount = mask.astype(np.float32)[..., None] / 510
    return Image.fromarray(u8(plate * (1 - amount) + np.array(colour, np.float32) * amount))


def sheets():
    lit = np.asarray(Image.open(IMG / 'marmoreal-lit-extended-2x.png'))
    masks = masks_from_disk()
    paths = []

    def put(name, im):
        p = IMG / 'comparison' / f'masks-{name}.png'
        save_image(p, im)
        paths.append({'path': rel(p), 'size': list(im.size)})

    # Independent master sheets keep each view at 1:1 (no giant 5-wide canvas).
    for n, colour in zip(NAMES, COLOURS):
        im = overlay(lit, masks[n], colour)
        put(f'{n}-master-colour', im)
        put(f'{n}-master-gray', gray(im))
    for size in ((1521, 856), (1170, 659)):
        panels = [Image.fromarray(lit).resize(size, Image.Resampling.LANCZOS)]
        panels += [overlay(lit, masks[n], c).resize(size, Image.Resampling.LANCZOS) for n, c in zip(NAMES, COLOURS)]
        for mono in (False, True):
            atlas = Image.new('RGB', (size[0] * 3, (size[1] + 32) * 2), (16, 20, 28))
            d = ImageDraw.Draw(atlas)
            for i, (im, label) in enumerate(zip(panels, ['lit reference'] + list(NAMES))):
                x, y = i % 3 * size[0], i // 3 * (size[1] + 32)
                atlas.paste(gray(im) if mono else im, (x, y + 32))
                d.text((x + 8, y + 5), label + ' | 50% mask overlay', fill='white', font=font())
            put(f'working-{size[0]}x{size[1]}-{"gray" if mono else "colour"}', gray(atlas) if mono else atlas)
    # Image-plane K1 framing, not an Unreal camera capture. Full B covers K1x.65.
    size = (1672, 941)
    frame = Image.fromarray(lit).resize(size, Image.Resampling.LANCZOS)
    d = ImageDraw.Draw(frame)
    box = (668*size[0]/SIZE[0], 376*size[1]/SIZE[1], 4012*size[0]/SIZE[0], 2258*size[1]/SIZE[1])
    d.rectangle(box, outline=(255, 224, 128), width=2)
    d.text((12, 12), 'K1 x0.65 | image-plane full B; rectangle = original concept', fill='white', font=font())
    put('K1x065-colour', frame)
    put('K1x065-gray', gray(frame))
    entries = load(PKG / 'lanterns.json')['entries']
    atlas = Image.new('RGB', (4*720, 2*540), (16, 20, 28))
    for i, e in enumerate(entries):
        x, y = e['centre_plate_px']
        half = 96 if e['id'].startswith('lantern') else 68
        box = tuple(int(round(v)) for v in (x-half, y-half, x+half, y+half))
        crop = Image.fromarray(lit).crop(box)
        draw = ImageDraw.Draw(crop)
        # Glass ROI in yellow; centre white; 4 C0 px tolerance circle in cyan.
        pts = plate_points(e['glass_polygon_concept_px']) - np.array(box[:2])
        draw.line([tuple(p) for p in pts] + [tuple(pts[0])], fill=(255, 208, 64), width=1)
        cx, cy = x-box[0], y-box[1]
        r = 4*2*SCALE
        draw.ellipse((cx-r, cy-r, cx+r, cy+r), outline=(80, 224, 255), width=1)
        draw.line((cx-4, cy, cx+4, cy), fill='white', width=1)
        draw.line((cx, cy-4, cx, cy+4), fill='white', width=1)
        factor = 2.5
        crop = crop.resize((round(crop.width*factor), round(crop.height*factor)), Image.Resampling.LANCZOS)
        heat = Image.fromarray(masks['lantern-glow']).crop(box).convert('RGB').resize(crop.size, Image.Resampling.NEAREST)
        sheet = Image.new('RGB', (crop.width*2, crop.height+56), (16, 20, 28))
        sheet.paste(crop, (0,56)); sheet.paste(heat, (crop.width,56))
        sd = ImageDraw.Draw(sheet)
        sd.text((8,6), e['id'] + ' | K2 x2.5 | glass / R glow', fill='white', font=font(16))
        sd.text((8,29), 'cyan = +/-4 C0 px; portal static, R=0' if not e['animated'] else 'white = measured centre; cyan = +/-4 C0 px', fill='white', font=font(14))
        put(f'K2-{e["id"]}-colour', sheet)
        put(f'K2-{e["id"]}-gray', gray(sheet))
        panel = sheet.resize((720, min(508, round(sheet.height*720/sheet.width))), Image.Resampling.LANCZOS)
        atlas.paste(panel, ((i%4)*720, (i//4)*540))
    put('K2-all-colour', atlas)
    put('K2-all-gray', gray(atlas))
    # Crown/cliff detail diagnostics at 100% help catch branches and wrong mist.
    for name, box in [('sakura-w', (320,600,1120,1450)), ('sakura-e', (3700,620,4500,1470)),
                      ('mist-foot', (1500,2070,3100,2634))]:
        n = 'mist' if name.startswith('mist') else 'sakura'
        base = Image.fromarray(lit).crop(box)
        over = overlay(lit, masks[n], COLOURS[NAMES.index(n)]).crop(box)
        raw = Image.fromarray(masks[n]).convert('RGB').crop(box)
        row = Image.new('RGB', (base.width*3,base.height+32),(16,20,28))
        for i, (im, label) in enumerate(zip([base,over,raw], ['lit plate','50% overlay',n+' raw'])):
            row.paste(im,(i*base.width,32))
            ImageDraw.Draw(row).text((i*base.width+8,6),label,fill='white',font=font())
        put(f'detail-{name}-colour',row);put(f'detail-{name}-gray',gray(row))
    woody=woody_support()
    im=overlay(lit,woody.astype('uint8')*255,(96,255,128)).resize((1560,878))
    put('woody-exclusions-colour',im);put('woody-exclusions-gray',gray(im))
    field, frame, frame40, edge, protected = protection()
    cov = overlay(lit, protected.astype('uint8')*255, (32,224,160)).resize((1560,878))
    put('protected-colour',cov);put('protected-gray',gray(cov))
    write_json(PKG / '_tools/en04-sheets.json', {'overlay_opacity': .5, 'gray': 'Rec.709 encoded sRGB luma .2126/.7152/.0722',
               'K1': 'full B image-plane, not a live Unreal capture', 'K2_zoom': 2.5, 'sheets': paths})
    print('sheets:', len(paths), flush=True)


def verify():
    started = time.perf_counter()
    clean = np.asarray(Image.open(IMG / 'marmoreal-extended-2x.png'))
    lit = np.asarray(Image.open(IMG / 'marmoreal-lit-extended-2x.png'))
    masks = masks_from_disk()
    field, frame, frame40, edge, protected = protection()
    crown, cliff, foot_y = regions()
    seed, _, _ = chroma_support(clean, crown)
    door = polygon(DOOR_CONCEPT)
    checks, outputs = {}, {}
    en03=load(PKG/'_tools/sx02-planb-check.json')['outputs']
    checks['EN03_pair_matches_verified_hashes']=all(
        sha(ROOT/name)==info['sha256'] and info['ssim_passed'] and info['field_flat_passed']
        for name,info in en03.items())
    expanded=polygon(load(PKG/'_tools/mask-spec.json')['field_expanded'])
    # The EN-01 raster is doubled by exact pixel replication; polygon drawing
    # may differ by <=1 px along sloping edges, so count both forbidden regions.
    checks['all_masks_zero_on_declared_expanded_field_polygon']=all(not np.any(m[expanded]) for m in masks.values())
    for n in NAMES:
        p = IMG / f'marmoreal-mask-{n}.png'
        im = Image.open(p); a = np.asarray(im)
        ihdr = p.read_bytes()[:26]
        outputs[rel(p)] = {'size': list(im.size), 'mode': im.mode, 'png_bit_depth': ihdr[24],
                           'png_colour_type': ihdr[25], 'sha256': sha(p), 'nonzero_pixels': int(np.count_nonzero(a)),
                           'min_max': [int(a.min()),int(a.max())],
                           'field_plus_2percent_nonzero': int(np.count_nonzero(a[field])),
                           'frame_foot_40px_nonzero': int(np.count_nonzero(a[frame40])),
                           'outer_frame_40px_nonzero': int(np.count_nonzero(a[edge]))}
        checks[f'{n}_format_and_protection'] = (im.size == SIZE and im.mode == 'L' and ihdr[24] == 8
                                               and not np.any(a[protected]) and np.any(a))
    anim_p = IMG / 'marmoreal-anim-2x.png'; lantern_p = IMG / 'marmoreal-lanterns-2x.png'
    anim = np.asarray(Image.open(anim_p)); lantern = np.asarray(Image.open(lantern_p))
    for p, a in [(anim_p, anim), (lantern_p, lantern)]:
        im = Image.open(p)
        outputs[rel(p)] = {'size': list(im.size), 'mode': im.mode, 'png_bit_depth': p.read_bytes()[24],
                           'sha256': sha(p)}
        channels=a if p==anim_p else a[...,3:4]
        outputs[rel(p)]['protected_counter_channels']='RGBA' if p==anim_p else 'alpha only; RGB equals the lit plate by contract'
        outputs[rel(p)]['field_plus_2percent_nonzero_by_channel']=[int(np.count_nonzero(channels[...,i][field])) for i in range(channels.shape[2])]
        outputs[rel(p)]['frame_foot_40px_nonzero_by_channel']=[int(np.count_nonzero(channels[...,i][frame40])) for i in range(channels.shape[2])]
        outputs[rel(p)]['outer_frame_40px_nonzero_by_channel']=[int(np.count_nonzero(channels[...,i][edge])) for i in range(channels.shape[2])]
        checks[p.stem+'_format'] = im.size == SIZE and im.mode == 'RGBA' and p.read_bytes()[24] == 8
    checks['anim_channels_exact'] = all(np.array_equal(anim[..., i], masks[n]) for i, n in enumerate(NAMES[1:]))
    checks['anim_protection_all_channels'] = not np.any(anim[protected])
    checks['lantern_layer_RGB_exact_lit'] = np.array_equal(lantern[..., :3],lit)
    checks['lantern_layer_alpha_exact'] = np.array_equal(lantern[..., 3],masks['lantern-alpha'])
    checks['lantern_layer_protected_alpha_zero'] = not np.any(lantern[..., 3][protected])
    # RGBA lantern RGB is intentionally preserved even where alpha=0 (contract).
    checks['door_glow_zero'] = not np.any(masks['lantern-glow'][door])
    ydiff = np.maximum(linear_y(lit)-linear_y(clean),0)
    checks['R_only_positive_lit_clean_luminance_difference'] = not np.any(masks['lantern-glow'][ydiff<=0])
    src_support = embed(np.asarray(Image.open(IMG/'marmoreal-lantern-mask.png')) > 0)
    checks['R_only_EN01_six_emitter_support'] = not np.any(masks['lantern-glow'][~src_support])
    checks['G_only_HSV_crown_selection'] = not np.any(masks['sakura'][~seed])
    checks['G_zero_on_explicit_trunks_and_branches'] = not np.any(masks['sakura'][woody_support()])
    checks['B_only_cliff_and_lower_continuation'] = not np.any(masks['mist'][~cliff])
    d = ndi.distance_transform_edt(masks['sakura']==0)
    checks['petals_support_within_24px_of_sakura'] = not np.any(masks['petals'][d>24])
    checks['petals_contains_sakura_outside_protection'] = bool(np.all(masks['petals']>=masks['sakura']))
    entries = load(PKG/'lanterns.json')['entries']
    centre_checks = []
    for e in entries:
        p = np.array(e['centre_plate_px']);cp = np.array(e['centre_concept_px']);c0=np.array(e['centre_C0_px'])
        domain = polygon(e['glass_polygon_concept_px'])
        on_domain = bool(domain[int(round(p[1])),int(round(p[0]))])
        rec = {'id':e['id'],'within_emitter_ROI':on_domain,
               'coordinate_round_trip_max_error_px':float(np.max(np.abs(c0*SCALE*2+OFFSET-p))),
               'positive_glow_pixels_in_glass':int(np.count_nonzero(masks['lantern-glow'][domain]))}
        if e['animated']:
            measured,_=centre(masks['lantern-glow'],domain)
            err=float(np.linalg.norm(measured-p)/(2*SCALE))
            ref=plate_points([e['glass_reference_concept_px']])[0]
            ix,iy=int(round(p[0])),int(round(p[1]))
            clearance=float(ndi.distance_transform_edt(domain)[iy,ix]/(2*SCALE))
            rec.update({'centroid_recompute_error_C0_px':err,
                        'offset_from_glass_bbox_centre_C0_px':float(np.linalg.norm(ref-p)/(2*SCALE)),
                        'clearance_to_glass_ROI_edge_C0_px':clearance,
                        '4_C0_px_tolerance_disk_inside_glass':clearance>=4})
            checks[e['id']+'_glass_centre'] = on_domain and err < 1e-6 and clearance>=4
        centre_checks.append(rec)
    checks['seven_named_entries'] = {e['id'] for e in entries} == set(GLASS)|{'portal'} and len(entries)==7
    checks['portal_static_zero_glow'] = not entries[-1]['animated'] and entries[-1]['glow_weight']==0
    baseline=load(PKG/'en04-baseline.json')
    unchanged={}
    for label in ('inputs','hud_icons_v3','existing_package_files'):
        changed=[]; exempt=[]; intentional=[]
        for name,before in baseline[label].items():
            p=ROOT/name
            if label=='existing_package_files' and p.parent==PKG and p.name in SHARED_MUTATIONS:
                exempt.append(name);continue
            if label=='existing_package_files' and p==PKG/'_tools/draw_icons_v3_snapshot.py':
                backup=PKG/'history/en04-before-draw_icons_v3_snapshot.py'
                if backup.exists() and sha(backup)==before['sha256'] and sha(p)==sha(ROOT/'art/imagegen/hud-icons-v3/_tools/draw_icons.py'):
                    intentional.append({'path':name,'reason':'Task requires exact current HUD generator snapshot; old snapshot retained byte-identically.',
                                        'old_snapshot_backup':rel(backup),'before_sha256':before['sha256'],'after_sha256':sha(p)})
                    continue
            if not p.is_file() or sha(p)!=before['sha256']: changed.append(name)
        current=set(rel(p) for p in (ROOT/'art/imagegen/hud-icons-v3').rglob('*') if p.is_file()) if label=='hud_icons_v3' else set(baseline[label])
        added=sorted(current-set(baseline[label]))
        unchanged[label]={'checked':len(baseline[label])-len(exempt),'changed':changed,'added':added,'allowed_report_updates':exempt,
                          'task_required_preserved_snapshot_replacement':intentional,'unchanged_except_documented_task_updates':not changed and not added}
        checks[label+'_unchanged']=not changed and not added
    checks['icon_snapshot_byte_identical']=sha(PKG/'_tools/draw_icons_v3_snapshot.py')==sha(ROOT/'art/imagegen/hud-icons-v3/_tools/draw_icons.py')
    build_record=load(PKG/'_tools/en04-build.json')
    checks['all_masks_under_60_seconds']=all(t['with_shared_setup_seconds']<=60 for t in build_record['timings'].values())
    sheet_data=load(PKG/'_tools/en04-sheets.json')
    sheet_checks=[]
    for s in sheet_data['sheets']:
        p=ROOT/s['path']
        a=np.asarray(Image.open(p))
        ok=a.shape[1::-1]==tuple(s['size']) and a.shape[2]==3
        rec={'path':s['path'],'sha256':sha(p),'size':list(a.shape[1::-1]),'format_pass':bool(ok)}
        if p.stem.endswith('-gray'):
            colour_path=p.with_name(p.name.replace('-gray.png','-colour.png'))
            encoded=np.asarray(Image.open(colour_path))
            expected=u8(encoded.astype(np.float32)@np.array([.2126,.7152,.0722],np.float32))
            rec['gray_RGB_equal']=bool(np.all(a[...,0]==a[...,1]) and np.all(a[...,0]==a[...,2]))
            rec['Rec709_max_error_levels']=int(np.max(np.abs(a[...,0].astype(int)-expected.astype(int))))
            ok=ok and rec['gray_RGB_equal'] and rec['Rec709_max_error_levels']<=1
        checks['sheet_'+p.stem]=bool(ok)
        sheet_checks.append(rec)
    limitations=[
        'Portal has zero lit-clean difference; its glow-mask centroid is undefined. A static lit-luminance emitter centroid is provided instead; portal is not lantern glass.',
        'The glass centroid is measured inside each glass ROI. The unrestricted pool centroid is also recorded and can lie off the glass.',
        'K1/K2 sheets are registered image-plane framing/crops, not live game camera captures; Unreal access was prohibited.',
        'HSV plus cherry geometry is a pigment selection, not a semantic proof about every branch. Direct PNG review is recorded separately.',
        'All seven PNG colour/alpha buffers cannot be zero in the protected field: lanterns RGB must equal lit RGB. All five masks, all anim channels and lantern alpha are zero there.'
    ]
    visual_path=PKG/'_tools/en04-visual-review.json'
    visual=load(visual_path) if visual_path.exists() else {'status':'pending'}
    record={'task':'EN-04','status':'предложено','verified_utc':datetime.now(timezone.utc).isoformat(),
            'depends_on':'EN-03 SX-02 plan B; hashes equal accepted source check',
            'outputs':outputs,'checks':{k:bool(v) for k,v in checks.items()},
            'script_checks_pass':all(checks.values()),'failed_checks':[k for k,v in checks.items() if not v],
            'strict_literal_acceptance_pass':False,'literal_unmet':['Portal centroid from glow mask / portal glass, because source difference is zero and portal is a doorway.'],
            'protection_pixels':{'field_plus_2percent':int(field.sum()),'painted_frame_40px':int(frame40.sum()),'outer_40px':int(edge.sum())},
            'door_glow_nonzero_pixels':int(np.count_nonzero(masks['lantern-glow'][door])),
            'sakura_nonzero_outside_HSV_or_cherry':int(np.count_nonzero(masks['sakura'][~seed])),
            'sakura_nonzero_on_explicit_woody_cores':int(np.count_nonzero(masks['sakura'][woody_support()])),
            'mist_nonzero_outside_cliff':int(np.count_nonzero(masks['mist'][~cliff])),
            'centres':centre_checks,'source_integrity':unchanged,'build':build_record,'sheets':sheet_checks,'visual_review':visual,
            'limitations':limitations,'generations':0,'MCP_calls':0,'git_commands':0,'unreal_access':False,
            'write_scope':[rel(PKG),rel(IMG)],'persistent_processes_started':0,
            'verification_seconds':round(time.perf_counter()-started,4)}
    v=load(PKG/'verification.json');v['EN-04']=record;write_json(PKG/'verification.json',v)
    write_json(PKG/'_tools/en04-verification.json',record)
    print(json.dumps({'script_checks_pass':record['script_checks_pass'],'failed':record['failed_checks'],
                      'strict_literal_acceptance_pass':False,'seconds':record['verification_seconds']},ensure_ascii=False),flush=True)
    if not all(checks.values()):
        raise SystemExit(1)


if __name__ == '__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command',choices=('build','sheets','verify'))
    command=parser.parse_args().command
    {'build':build,'sheets':sheets,'verify':verify}[command]()
