"""CP-07: procedural circles; original avatars are used only in the review folder.

Run from any cwd: python -B <this-file>. No generator CLI, Git, or Unreal calls.
The unmodified v3 snapshot provides hex decoding and the two engine font paths.
Its Rec.601 grey() is deliberately replaced with the required Rec.709 luma.
"""
from __future__ import annotations

import sys
sys.dont_write_bytecode = True
import hashlib
import importlib.util
import io
import json
import math
from pathlib import Path

import cairo
import numpy as np
from PIL import Image, ImageDraw, ImageFont

PACKAGE = Path(__file__).resolve().parents[1]
ROOT = PACKAGE.parents[2]
REVIEW = ROOT / 'scraped-data/derived/portrait-crop-v1-codex'
spec = importlib.util.spec_from_file_location('icons_snapshot', PACKAGE / '_tools/draw_icons_v3_snapshot.py')
icons = importlib.util.module_from_spec(spec)
spec.loader.exec_module(icons)
TOKENS = {'card.navy': '#061623', 'card.cream': '#F9EBDB',
          'mark.keyline': '#111317', 'text.primary': '#F2EDE4'}
SIZES = (32, 40, 64, 80, 120, 160)
SCALES = (('x1', 1), ('x1.5', 1.5), ('x2', 2))
MASTER = 320
CHARACTERS = {
    'king-arthur': {'source': 'avatars/king-arthur.png', 'start': (.49, .43, .60),
                    'shift': .04, 'eyes': [(404, 373), (464, 402)], 'monogram': 'KA'},
    'medusa': {'source': 'avatars/medusa.png', 'start': (.44, .33, .56),
               'shift': .04, 'eyes': [(146, 120), (181, 119)], 'monogram': 'M'},
    'king-arthur-merlin': {'source': 'sidekicks/king-arthur-merlin.png', 'start': (.5, .5, .75),
                          'shift': .02, 'eyes': [(53, 49), (71, 49)], 'monogram': 'M'},
    'medusa-harpies': {'source': 'sidekicks/medusa-harpies.png', 'start': (.5, .5, .75),
                       'shift': .02, 'eyes': [(52, 59), (65, 58)], 'monogram': None},
}
KEYS = {'king-arthur': 'king-arthur', 'medusa': 'medusa',
        'king-arthur-merlin': 'king-arthur/merlin', 'medusa-harpies': 'medusa/harpies'}
WRITES: set[str] = set()


def safe_path(path: Path, avatar=False):
    path = path.resolve()
    assert path.is_relative_to(REVIEW if avatar else PACKAGE), str(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    WRITES.add(path.relative_to(ROOT).as_posix())
    return path


def save(im, path, avatar=False):
    im.save(safe_path(path, avatar))


def write_json(path, data):
    safe_path(path).write_text(json.dumps(data, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')


def variants(c):
    x, y, d = c['start']
    return {'A': (x, y, d), 'B': (x, round(y-c['shift'], 6), round(d-.06, 6)),
            'C': (x, y, round(d+.06, 6))}


def grey(im):
    a = np.asarray(im.convert('RGBA')).copy()
    luma = np.floor(a[..., :3].astype(float) @ np.array([.2126, .7152, .0722]) + .5).astype(np.uint8)
    a[..., :3] = luma[..., None]
    return Image.fromarray(a)


def lab(rgb):
    """sRGB -> CIE Lab D65, for exact-token palette verification."""
    rgb = np.asarray(rgb, dtype=float)/255
    linear = np.where(rgb <= .04045, rgb/12.92, ((rgb+.055)/1.055)**2.4)
    xyz = linear @ np.array([[.4124564, .3575761, .1804375],
                            [.2126729, .7151522, .0721750],
                            [.0193339, .1191920, .9503041]]).T
    xyz /= np.array([.95047, 1, 1.08883])
    f = np.where(xyz > (6/29)**3, np.cbrt(xyz), xyz/(3*(6/29)**2)+4/29)
    return np.stack([116*f[..., 1]-16, 500*(f[..., 0]-f[..., 1]),
                     200*(f[..., 1]-f[..., 2])], axis=-1)


def badge_palette(im):
    """Fix only out-of-tolerance opaque RGB blends; preserve alpha/geometry."""
    a = np.asarray(im).copy()
    tokens = np.array([[6, 22, 35], [17, 19, 23]], dtype=np.uint8)
    opaque = a[..., 3] >= 250
    colors = a[opaque, :3].copy()
    distance = np.linalg.norm(lab(colors)[:, None, :]-lab(tokens), axis=-1)
    nearest = distance.argmin(axis=-1)
    outside = distance.min(axis=-1) > 3
    colors[outside] = tokens[nearest[outside]]
    a[opaque, :3] = colors
    return Image.fromarray(a)


def vector_image(n, su, kind='edge'):
    r = su/2
    layers = [(r, None, 'card.navy', 1)] if kind == 'disc' else [
        (r, r-1, 'mark.keyline', 1), (r-1, r-2, 'card.cream', .45)]
    result = Image.new('RGBA', (n,n))
    for outer, inner, token, opacity in layers:
        surface = cairo.ImageSurface(cairo.FORMAT_ARGB32, n, n)
        ctx = cairo.Context(surface)
        ctx.scale(n/su, n/su)
        ctx.arc(r, r, outer, 0, math.tau)
        if inner is not None:
            ctx.arc_negative(r, r, inner, math.tau, 0)
        ctx.set_fill_rule(cairo.FILL_RULE_EVEN_ODD)
        ctx.set_source_rgba(1,1,1,1)
        ctx.fill()
        buf = io.BytesIO(); surface.write_to_png(buf); buf.seek(0)
        mask=Image.open(buf).convert('RGBA').getchannel('A')
        mask=mask.point(lambda a:round(a*opacity))
        # Straight RGBA keeps exact token RGB even at alpha 0.45.
        layer=Image.new('RGBA',(n,n),TOKENS[token]);layer.putalpha(mask)
        result.alpha_composite(layer)
    return result


def portrait(source, crop, n, su):
    cx, cy, d = crop
    side = source.width
    box = ((cx-d/2)*side, (cy-d/2)*side, (cx+d/2)*side, (cy+d/2)*side)
    # Review rasterization of UV coordinates, no sharpen, retouch or AI upscale.
    im = source.resize((n, n), Image.Resampling.BILINEAR, box=box)
    disc = vector_image(n, su, 'disc')
    alpha = im.getchannel('A')
    im.putalpha(Image.fromarray(np.floor(np.asarray(alpha, dtype=float) *
                    np.asarray(disc.getchannel('A'), dtype=float)/255+.5).astype(np.uint8)))
    disc.alpha_composite(im)
    disc.alpha_composite(vector_image(n, su))
    return disc


def glyph(text, cap_px, color):
    # Fit actual ink height, rather than point size or font ascent.
    font = ImageFont.truetype(icons.FONT_BC, 256)
    box = font.getbbox(text)
    mask = Image.new('L', (box[2]-box[0], box[3]-box[1]))
    ImageDraw.Draw(mask).text((-box[0], -box[1]), text, font=font, fill=255)
    mask = mask.resize((max(1, round(mask.width * cap_px/mask.height)), round(cap_px)), Image.Resampling.LANCZOS)
    im = Image.new('RGBA', mask.size, color)
    im.putalpha(mask)
    return im


def badge(n, su, digit=None, exact_palette=True):
    scale = n/su
    size = round(14*scale)
    im = vector_image(size, 14, 'disc')
    # Badge uses only navy + outer keyline; it has no cream hairline.
    sf = cairo.ImageSurface(cairo.FORMAT_ARGB32, size, size)
    ctx = cairo.Context(sf)
    ctx.scale(scale, scale)
    ctx.arc(7, 7, 6.5, 0, math.tau)
    ctx.set_line_width(1)
    ctx.set_source_rgb(*icons.hx(TOKENS['mark.keyline']))
    ctx.stroke()
    buf = io.BytesIO(); sf.write_to_png(buf); buf.seek(0)
    im.alpha_composite(Image.open(buf).convert('RGBA'))
    if exact_palette:
        im = badge_palette(im)
    if digit is not None:
        text = glyph(str(digit), 10*scale, TOKENS['card.cream'])
        im.alpha_composite(text, ((size-text.width)//2, (size-text.height)//2))
    return im


def add_badge(im, su, digit):
    out = im.copy(); b = badge(im.width, su, digit)
    out.alpha_composite(b, (im.width-b.width, im.height-b.height))
    return out


def fallback(n, su, text):
    im = vector_image(n, su, 'disc')
    cap = min(24, su*.38)*n/su
    g = glyph(text, cap, TOKENS['text.primary'])
    im.alpha_composite(g, ((n-g.width)//2, (n-g.height)//2))
    im.alpha_composite(vector_image(n, su))
    return im


def sheet(w, h, title, subtitle):
    im = Image.new('RGBA', (w, h), TOKENS['card.navy'])
    draw = ImageDraw.Draw(im)
    draw.text((28, 22), title, font=ImageFont.truetype(icons.FONT_BC, 27), fill=TOKENS['card.cream'])
    draw.text((28, 58), subtitle, font=ImageFont.truetype(icons.FONT_RG, 14), fill=TOKENS['text.primary'])
    draw.line((28, 88, w-28, 88), fill=(249,235,219,100))
    return im


def label(im, xy, text, size=14):
    ImageDraw.Draw(im).text(xy, text, font=ImageFont.truetype(icons.FONT_RG, size), fill=TOKENS['text.primary'])


def pair(im, dest, avatar=False):
    save(im, dest, avatar)
    save(grey(im), dest.with_stem(dest.stem+'-gray'), avatar)


def over_limit(n, side, crop):
    return n > 1.6*side*crop[2]+1e-9


def working_status(name, variant, su, tag, side, crop):
    sidekick = 'sidekicks' in CHARACTERS[name]['source']
    bleed = sidekick and variant == 'A' and su in (32, 40) and tag in ('x1', 'x1.5')
    ring = 'REJECT ring' if sidekick and variant == 'C' else ('! ring filter' if bleed else 'ring ok')
    scale = dict(SCALES)[tag]
    magnification = '! >1.6x' if over_limit(round(su*scale), side, crop) else 'ok'
    return f'{ring} / {magnification}'


def magnification_row(name, variant, su, tag, scale, side, crop):
    n = round(su*scale)
    return {'character': name, 'variant': variant, 'su': su, 'scale': tag, 'display_px': n,
            'source_crop_px': round(side*crop[2], 6), 'magnification': round(n/(side*crop[2]), 6),
            'recommended': variant == 'B', 'allowed': not over_limit(n, side, crop)}


def build():
    baseline = json.loads((PACKAGE/'source-hashes-before.json').read_text(encoding='utf-8'))
    for path, record in baseline['files'].items():
        assert hashlib.sha256((ROOT/path).read_bytes()).hexdigest() == record['sha256'], path
    source = {name: Image.open(ROOT/'scraped-data/derived/ue-media-v1'/c['source']).convert('RGBA')
              for name,c in CHARACTERS.items()}
    recommendations = {KEYS[name]: dict(zip(('cx','cy','d'), variants(c)['B'])) for name,c in CHARACTERS.items()}
    write_json(PACKAGE/'portrait-crops.json', recommendations)
    write_json(PACKAGE/'generation-records.json', {'image_generation_used': False, 'generations': [],
                 'prompt_key': 'CP-07 / T-CODEX-CARDFRAME / portrait-circle', 'method': 'procedural Cairo + Pillow'})
    write_json(PACKAGE/'prompts/render-contract.json', {
        'prompt_key': 'CP-07 / T-CODEX-CARDFRAME / portrait-circle', 'tokens': TOKENS,
        'sizes_su': SIZES, 'scales': dict(SCALES), 'master_px': MASTER,
        'master_is_review_only': True, 'hairline_opacity': .45, 'keyline_su': 1, 'hairline_su': 1,
        'badge': {'diameter_su':14, 'cap_su':10, 'position_su':[18,18], 'font': icons.FONT_BC,
                  'digits_are_live_text': True},
        'gray': 'round(0.2126 R + 0.7152 G + 0.0722 B), encoded sRGB Rec.709 luma; alpha unchanged',
        'characters': CHARACTERS, 'variants': {n:variants(c) for n,c in CHARACTERS.items()}})
    for su in SIZES:
        for tag,k in (SCALES[0], SCALES[2]):
            save(vector_image(round(su*k), su), PACKAGE/f'vector/portrait-edge-{su}-{tag}.png')
            save(vector_image(round(su*k), su, 'disc'), PACKAGE/f'vector/portrait-underlay-{su}-{tag}.png')
        r=su/2
        svg=(f'<svg xmlns="http://www.w3.org/2000/svg" width="{su}" height="{su}" viewBox="0 0 {su} {su}">'
             f'<circle cx="{r}" cy="{r}" r="{r-.5}" fill="none" stroke="#111317" stroke-width="1"/>'
             f'<circle cx="{r}" cy="{r}" r="{r-1.5}" fill="none" stroke="#F9EBDB" stroke-opacity="0.45" stroke-width="1"/></svg>')
        safe_path(PACKAGE/f'vector/portrait-edge-{su}.svg').write_text(svg,encoding='utf-8')
    for tag,k in SCALES:
        save(badge(round(32*k),32), PACKAGE/f'vector/harpy-badge-14-{tag}.png')
        for digit in (1,2,3):
            b=add_badge(vector_image(round(32*k),32,'disc'),32,digit)
            pair(b, PACKAGE/f'comparison/harpy-badge-{digit}-32-{tag}.png')
    exceeds=[]; master_exceeds=[]
    for name,c in CHARACTERS.items():
        side=source[name].width
        for variant,crop in variants(c).items():
            for su in SIZES:
                for tag,k in SCALES:
                    n=round(su*k)
                    pair(portrait(source[name],crop,n,su), REVIEW/f'{name}-{variant}-{su}-{tag}.png',True)
                    if over_limit(n,side,crop):
                        exceeds.append({'character':name,'variant':variant,'su':su,'scale':tag,'display_px':n,
                                        'source_crop_px':round(side*crop[2],6),'magnification':round(n/(side*crop[2]),6),
                                        'recommended':variant=='B','allowed':False})
            if over_limit(MASTER,side,crop):
                master_exceeds.append({'character':name,'variant':variant,'display_px':MASTER,
                                       'magnification':round(MASTER/(side*crop[2]),6),'review_only':True})
        for tag,k in SCALES:
            for digit in ((1,2,3) if name=='medusa-harpies' else (None,)):
                if digit is not None:
                    im=portrait(source[name],variants(c)['B'],round(32*k),32)
                    pair(add_badge(im,32,digit),REVIEW/f'harpy-{digit}-B-32-{tag}.png',True)
            winner=portrait(source[name],variants(c)['B'],round(120*k),120)
            loser=grey(winner)
            loser.putalpha(loser.getchannel('A').point(lambda a:round(a*.6)))
            pair(winner, REVIEW/f'{name}-winner-120-{tag}.png',True)
            pair(loser, REVIEW/f'{name}-loser-120-{tag}.png',True)
        for su in SIZES:
            for tag,k in SCALES:
                for text in ((c['monogram'],) if c['monogram'] else ('1','2','3')):
                    pair(fallback(round(su*k),su,text), PACKAGE/f'comparison/fallback-{name}-{text}-{su}-{tag}.png')
    # 2160p / 150% is computed only: never render x3 review composites.
    recommended = json.loads((PACKAGE/'portrait-crops.json').read_text(encoding='utf-8'))
    x3_rows = []
    for name in CHARACTERS:
        crop = tuple(recommended[KEYS[name]][key] for key in ('cx', 'cy', 'd'))
        for su in SIZES:
            row = magnification_row(name, 'B', su, 'x3', 3, source[name].width, crop)
            row.update({'display_case': '2160p / 150%', 'computed_only': True,
                        'exceeds_limit': not row['allowed']})
            x3_rows.append(row)
            if row['exceeds_limit']:
                exceeds.append(row)
    write_json(PACKAGE/'magnification-limits.json', {'limit':1.6,'production_exceeds':exceeds,
                   'recommended_x3_rows':x3_rows,
                   'review_master_exceeds':master_exceeds, 'review_resampling_is_not_source_enhancement':True})
    # A/B/C at master size. Every actual bitmap is explicitly tagged for its source limit.
    im=sheet(1200,1730,'CP-07 / PORTRAIT CROPS','A start   /   B tighter, recommended   /   C wider   ·   320 px REVIEW master')
    for row,(name,c) in enumerate(CHARACTERS.items()):
        y=108+row*399
        label(im,(28,y),name,18)
        for col,(variant,crop) in enumerate(variants(c).items()):
            x=36+col*390
            im.alpha_composite(portrait(source[name],crop,MASTER,160),(x,y+30))
            limit=' ! >1.6x REVIEW ONLY' if over_limit(MASTER,source[name].width,crop) else ''
            ring=' / REJECT ring' if col==2 and 'sidekicks' in c['source'] else ''
            label(im,(x,y+357),f'{variant} {crop[0]:.2f}/{crop[1]:.2f}/{crop[2]:.2f}'+limit,13)
            label(im,(x,y+377),('RECOMMENDED' if variant=='B' else '')+ring,12)
    pair(im,REVIEW/'comparison-master.png',True)
    # Native-size matrices, no thumbnail reduction or display-size enlargement.
    for tag,k in SCALES:
        col_w=round(160*k)+34
        width=205+len(SIZES)*col_w
        # Generous row spacing prevents 320 px circles from overlapping.
        row_h=round(160*k)+43
        im=sheet(width,132+12*row_h+30,f'CP-07 / WORKING SIZES / {tag}',
                 'Native px · A/B/C · ! exceeds 1.6x · B recommended · C sidekick may reveal baked ring')
        for col,su in enumerate(SIZES): label(im,(205+col*col_w,104),f'{su} su / {round(su*k)} px')
        for row,(name,c) in enumerate(CHARACTERS.items()):
            for vi,(variant,crop) in enumerate(variants(c).items()):
                y=132+(row*3+vi)*row_h
                label(im,(28,y+8),name,13);label(im,(28,y+29),variant+(' / chosen' if variant=='B' else ''))
                for col,su in enumerate(SIZES):
                    n=round(su*k);x=205+col*col_w
                    im.alpha_composite(portrait(source[name],crop,n,su),(x,y))
                    note=working_status(name,variant,su,tag,source[name].width,crop)
                    label(im,(x,y+n+8),note,12)
        pair(im,REVIEW/f'comparison-working-{tag}.png',True)
    im=sheet(1200,510,'CP-07 / 32 su / GRAYSCALE CHECK','Top: actual 32 px · Bottom: same pixels at x4 nearest, inspection only · badges 1 / 2 / 3')
    cases=[(n,portrait(source[n],variants(c)['B'],32,32)) for n,c in CHARACTERS.items()]
    cases += [(f'Harpy {digit}',add_badge(cases[3][1],32,digit)) for digit in (1,2,3)]
    for col,(name,disc) in enumerate(cases):
        x=28+col*165; label(im,(x,111),name,12)
        im.alpha_composite(disc,(x,145))
        im.alpha_composite(disc.resize((128,128),Image.Resampling.NEAREST),(x,216))
    pair(im,REVIEW/'readability-32.png',True)
    # Procedural package sheets never include originals.
    for tag,k in SCALES:
        im=sheet(1380,650,f'CP-07 / OVERLAY / {tag}','No avatars · navy underlay · 1 su keyline · 1 su cream 45% · badge 14 su / cap 10 su')
        x=28
        for su in SIZES:
            n=round(su*k)
            label(im,(x,108),f'{su} su / {n} px')
            disc=vector_image(n,su,'disc');disc.alpha_composite(vector_image(n,su))
            im.alpha_composite(disc,(x,144));x+=max(150,n)+28
        for digit in (1,2,3):
            n=round(32*k);x=28+(digit-1)*180
            base=vector_image(n,32,'disc');base.alpha_composite(vector_image(n,32))
            tile=Image.new('RGBA',(n+16,n+16),TOKENS['card.cream'])
            tile.alpha_composite(add_badge(base,32,digit),(8,8))
            im.alpha_composite(tile,(x,490))
            # Caption starts 6 px below the cream tile, including its 16 px padding.
            label(im,(x,490+tile.height+6),f'Harpy {digit} / 32 su',12)
        pair(im,PACKAGE/f'comparison/overlay-working-{tag}.png')
    im=sheet(1280,580,'CP-07 / OVERLAY MASTER','320 px procedural edge · no avatars · badge is separate · digits remain live text')
    disc=vector_image(320,160,'disc');disc.alpha_composite(vector_image(320,160))
    im.alpha_composite(disc,(28,135))
    im.alpha_composite(vector_image(320,160),(405,135))
    for digit in (1,2,3):
        b=add_badge(vector_image(160,32,'disc'),32,digit)
        im.alpha_composite(b,(780+(digit-1)*164,150))
    label(im,(28,478),'Underlay + edge');label(im,(405,478),'Edge / transparent centre')
    pair(im,PACKAGE/'comparison/overlay-master.png')
    # Winners and losers at native scale, both on navy and cream, opacity is observable.
    for tag,k in SCALES:
        n=round(120*k);cw=2*n+60;rw=n+78
        im=sheet(2*cw+70,130+4*rw,f'CP-07 / RESULT / {tag}','B crop · winner / loser · loser: Rec.709 saturation 0, whole-widget alpha 0.6')
        for row,name in enumerate(CHARACTERS):
            y=120+row*rw;label(im,(28,y),name,15)
            for bi,bg in enumerate(['card.navy','card.cream']):
                x=28+bi*cw;tile=Image.new('RGBA',(cw-20,n+22),TOKENS[bg])
                winner=Image.open(REVIEW/f'{name}-winner-120-{tag}.png').convert('RGBA')
                loser=Image.open(REVIEW/f'{name}-loser-120-{tag}.png').convert('RGBA')
                tile.alpha_composite(winner,(10,10));tile.alpha_composite(loser,(n+30,10))
                im.alpha_composite(tile,(x,y+28))
        pair(im,REVIEW/f'result-working-{tag}.png',True)
    for tag,k in SCALES:
        cw=round(160*k)+34;rh=round(160*k)+42
        im=sheet(210+len(SIZES)*cw,132+6*rh+24,f'CP-07 / FALLBACK / {tag}',
                 'No source artwork · live heading text · KA / M / M · Harpies use only 1 / 2 / 3')
        cases=[('King Arthur','KA'),('Medusa','M'),('Merlin','M'),('Harpy 1','1'),('Harpy 2','2'),('Harpy 3','3')]
        for col,su in enumerate(SIZES):label(im,(210+col*cw,104),f'{su} su / {round(su*k)} px')
        for row,(name,text) in enumerate(cases):
            y=132+row*rh;label(im,(28,y+8),name)
            for col,su in enumerate(SIZES):im.alpha_composite(fallback(round(su*k),su,text),(210+col*cw,y))
        pair(im,PACKAGE/f'comparison/fallback-working-{tag}.png')
    # Crop landmark evidence: original source coordinates, circle + central 60% radius.
    im=sheet(1120,700,'CP-07 / EYE LANDMARKS','Manual landmarks in original pixels · white crop boundary · central 60% circle · B')
    for col,(name,c) in enumerate(CHARACTERS.items()):
        src=source[name];tile=src.resize((256,256),Image.Resampling.NEAREST)
        draw=ImageDraw.Draw(tile);cx,cy,d=variants(c)['B']
        for diameter,width in [(d,2),(d*.6,1)]:
            draw.ellipse(((cx-diameter/2)*256,(cy-diameter/2)*256,(cx+diameter/2)*256,(cy+diameter/2)*256),outline='#F9EBDB',width=width)
        for ex,ey in c['eyes']:
            x=ex/src.width*256;y=ey/src.height*256
            draw.line((x-4,y,x+4,y),fill='#F2EDE4');draw.line((x,y-4,x,y+4),fill='#F2EDE4')
        x=28+col*274;label(im,(x,110),name,13);im.alpha_composite(tile,(x,146))
        label(im,(x,426),'B / centre + diameter',12)
        label(im,(x,450),f'{cx:.2f} / {cy:.2f} / {d:.2f}',14)
    pair(im,REVIEW/'eye-landmarks.png',True)
    # Retain the existing source-inspection PNGs byte-for-byte; supply their
    # missing Rec.709 partners so every colour review image has a gray partner.
    for path in sorted(REVIEW.glob('source-inspection-*.png')):
        if not path.stem.endswith('-gray'):
            with Image.open(path) as inspection:
                save(grey(inspection),path.with_stem(path.stem+'-gray'),True)
    write_json(PACKAGE/'build-data.json',{'output_roots':[PACKAGE.relative_to(ROOT).as_posix(), REVIEW.relative_to(ROOT).as_posix()],
               'written_paths':sorted(WRITES), 'composite_pairs':4*3*6*3,'recommended_variant':'B',
               'renderer':'Cairo exact token paths + Pillow bilinear UV review',
               'source_sampling':'original source pixels; no enhancement', 'python':sys.version.split()[0]})
    print(f'CP-07 built: {len(WRITES)} files; {len(exceeds)} production size/variant limit violations.')


if __name__ == '__main__':
    build()
