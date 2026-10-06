#!/usr/bin/env python
"""CP-13 procedural extension of the unchanged v3 snapshot. No ImageGen.

Run from any directory: python -B .../_tools/build_card_frames.py
Writes only the two CP-13 output roots. Never invokes the snapshot's CLI.
"""
from __future__ import annotations

import hashlib
import json
import math
import os
from pathlib import Path
import sys
import time

sys.dont_write_bytecode = True
import numpy as np
from PIL import Image, ImageDraw, ImageFont
import draw_icons_v3_snapshot as v3

PACKAGE = Path(__file__).resolve().parents[1]
ROOT = PACKAGE.parents[2]
DERIVED = ROOT / 'scraped-data/derived/card-frame-v1-codex'
WRITES = set()


def audit(event, args):
    if event == 'open' and isinstance(args[0], (str, bytes, os.PathLike)):
        mode, flags = args[1:3]
        writing = (isinstance(mode, str) and any(c in mode for c in 'wax+')) or (
            isinstance(flags, int) and flags & (os.O_WRONLY | os.O_RDWR | os.O_CREAT | os.O_TRUNC))
        if writing:
            target = Path(os.fsdecode(args[0])).resolve()
            if not any(target.is_relative_to(p) for p in (PACKAGE, DERIVED)):
                raise PermissionError(f'CP-13 forbidden write: {target}')
            WRITES.add(target.relative_to(ROOT).as_posix())
    elif event in ('os.mkdir', 'os.remove', 'os.rmdir', 'os.rename'):
        for arg in args[:2] if event == 'os.rename' else args[:1]:
            if isinstance(arg, (str, bytes, os.PathLike)):
                target = Path(os.fsdecode(arg)).resolve()
                if not any(target.is_relative_to(p) for p in (PACKAGE, DERIVED)):
                    raise PermissionError(f'CP-13 forbidden mutation: {target}')
    elif event in ('subprocess.Popen', 'os.system'):
        raise PermissionError('CP-13 build does not start subprocesses')


sys.addaudithook(audit)
TOKENS = {k: v3.TOKENS[k] for k in ('card.navy', 'card.cream', 'state.pending',
                                  'turn.flash.orange', 'card.glyph', 'mark.keyline')}
RGB = {k: tuple(round(c * 255) for c in v3.hx(v)) for k, v in TOKENS.items()}
STATES = ('idle', 'hover', 'selected', 'warning', 'flash', 'focus',
          'mini-idle', 'playable', 'not-playable', 'new')
DISPLAYS = {
    'hand': (150, 208, 4, 8), 'hover': (225, 312, 4, 8),
    'combat': (230, 319, 4, 8), 'source-slot': (190, 264, 4, 8),
    'inspector-ru': (460, 640, 4, 8), 'inspector-en': (408, 566, 4, 8),
    'class-s-hand': (120, 166, 4, 8),
    'opponent-back': (48, 67, 2, 4), 'deck-chip': (32, 45, 2, 4),
    'discard-chip': (32, 45, 2, 4),
}
KEYS = ('medusa:gaze-of-stone', 'medusa:hiss-and-slither', 'medusa:snipe',
        'medusa:winged-frenzy', 'king-arthur:excalibur',
        'king-arthur:the-holy-grail', 'king-arthur:skirmish', 'king-arthur:prophecy')
TYPES = {'gaze-of-stone': 'attack', 'hiss-and-slither': 'defense', 'snipe': 'versatile',
         'winged-frenzy': 'scheme', 'excalibur': 'attack',
         'the-holy-grail': 'defense', 'skirmish': 'versatile', 'prophecy': 'scheme'}
EDGE = {'idle': ('card.cream', 1, .45), 'hover': ('card.cream', 1, 1),
        'selected': ('state.pending', 3, 1), 'warning': ('turn.flash.orange', 2, 1),
        'flash': ('card.glyph', 2, 1)}
PADDING = 6  # focus extends 4 su; new marker extends 6 su above the frame
ASSETS, FITS, SHEETS = {}, {}, {}
FONT = ImageFont.load_default(size=13)


def dump(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


def save(path, image):
    path.parent.mkdir(parents=True, exist_ok=True)
    image.save(path, compress_level=3)


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def gray(image):
    # Rec.709 luma on the stored sRGB samples, as requested; preserve alpha.
    arr = np.asarray(image.convert('RGBA')).copy()
    luma = np.floor(np.einsum('ijk,k->ij', arr[:, :, :3].astype(np.float32),
                             np.array([.2126, .7152, .0722], np.float32)) + .5).astype('uint8')
    arr[:, :, :3] = luma[:, :, None]
    return Image.fromarray(arr)


def rounded_mask(w, h, box, radius, scale):
    # Cairo coverage is used only for outer alpha. Material boundaries are snapped.
    surf = v3.cairo.ImageSurface(v3.cairo.FORMAT_A8, w * scale, h * scale)
    ctx = v3.cairo.Context(surf)
    ctx.scale(scale, scale)
    x, y, bw, bh = box
    r = max(0, min(radius, bw / 2, bh / 2))
    ctx.new_sub_path()
    for cx, cy, a in ((x + bw - r, y + r, -math.pi / 2),
                      (x + bw - r, y + bh - r, 0),
                      (x + r, y + bh - r, math.pi / 2),
                      (x + r, y + r, math.pi)):
        ctx.arc(cx, cy, r, a, a + math.pi / 2)
    ctx.close_path()
    ctx.set_source_rgba(1, 1, 1, 1)
    ctx.fill()
    surf.flush()
    return np.frombuffer(surf.get_data(), dtype=np.uint8).reshape(h * scale, surf.get_stride())[:, :w * scale].copy()


def frame(spec, state, scale=1):
    w, h, band, radius = spec
    token, requested_edge, opacity = EDGE.get(state, EDGE['idle'])
    edge = min(requested_edge, band - 1)
    # Mini states have only 1 su available after the keyline. Never cover a scan.
    if state == 'mini-idle':
        token, edge, opacity = EDGE['idle']
    outer = rounded_mask(w, h, (0, 0, w, h), radius, scale)
    inside_key = rounded_mask(w, h, (1, 1, w - 2, h - 2), radius - 1, scale)
    inside_edge = rounded_mask(w, h, (1 + edge, 1 + edge,
                                w - 2 * (1 + edge), h - 2 * (1 + edge)),
                               radius - 1 - edge, scale)
    arr = np.zeros((h * scale, w * scale, 4), dtype=np.uint8)
    arr[:, :, :3] = RGB['mark.keyline']
    arr[:, :, 3] = outer
    key = inside_key >= 128
    arr[key, :3] = RGB[token]
    arr[key, 3] = round(255 * opacity)
    navy = inside_edge >= 128
    arr[navy, :3] = RGB['card.navy']
    arr[navy, 3] = 255
    # The exact, invariant rectangular viewport preserves every scan corner.
    arr[band * scale:(h - band) * scale, band * scale:(w - band) * scale] = 0
    return Image.fromarray(arr)


def focus(spec, scale=1):
    w, h, _, radius = spec
    outer = rounded_mask(w + 8, h + 8, (0, 0, w + 8, h + 8), radius + 4, scale)
    inner = rounded_mask(w + 8, h + 8, (2, 2, w + 4, h + 4), radius + 2, scale)
    arr = np.zeros(((h + 8) * scale, (w + 8) * scale, 4), np.uint8)
    arr[:, :, :3] = RGB['card.glyph']
    arr[:, :, 3] = np.maximum(outer.astype(np.int16) - inner, 0).astype('uint8')
    return Image.fromarray(arr)


def new_dot(scale=1):
    # 8 su white diameter + 1 su exterior keyline. Separate from scan and frame.
    arr = np.zeros((10 * scale, 10 * scale, 4), np.uint8)
    outer = rounded_mask(10, 10, (0, 0, 10, 10), 5, scale)
    inner = rounded_mask(10, 10, (1, 1, 8, 8), 4, scale)
    arr[:, :, :3] = RGB['mark.keyline']
    arr[:, :, 3] = outer
    arr[inner >= 128, :3] = RGB['card.glyph']
    return Image.fromarray(arr)


def export_asset(rel, image, spec, state, scale, focus_layer=False):
    path = PACKAGE / rel
    save(path, image)
    w, h, band, radius = spec
    edge = min(EDGE.get(state, EDGE['idle'])[1], band - 1)
    margin = (radius + edge + 1) * scale + 1  # final term is one physical AA px
    if focus_layer:
        margin = (radius + 4) * scale + 1
    ASSETS[rel] = {
        'size_px': list(image.size), 'logical_frame_su': [w, h], 'density': scale,
        'state': state, 'radius_su': radius, 'band_su': band,
        'nine_slice_px': [margin] * 4,
        'nine_slice_uv': [margin / image.width, margin / image.height] * 2,
        'frame_origin_px': [4 * scale, 4 * scale] if focus_layer else [0, 0],
        'window_px': None if focus_layer else [band * scale, band * scale,
                                              (w - 2 * band) * scale, (h - 2 * band) * scale],
        'layer': 'focus-only' if focus_layer else 'frame',
        'edge_su': 2 if focus_layer else edge,
        'edge_alpha': 1 if focus_layer else EDGE.get(state, EDGE['idle'])[2],
    }


def sources():
    manifest = json.loads((ROOT / 'art/imagegen/mvp-v1/reused-cardart.json').read_text(encoding='utf-8'))
    by_key = {c['stableContentKey']: c for c in manifest['cards']}
    result = []
    for lang in ('ru', 'en'):
        for key in KEYS:
            info = by_key[key][lang]
            assert sha(ROOT / info['path']) == info['sha256'], key
            with Image.open(ROOT / info['path']) as image:
                image = image.convert('RGBA')
            result.append({'key': key, 'language': lang, 'path': info['path'],
                           'sha256': info['sha256'], 'type': TYPES[key.split(':')[1]],
                           'image': image, 'kind': 'scan'})
    for hero, name in (('king-arthur', 'WWzu16BEFGsEdu5NsMbMI'), ('medusa', 'ROSMO3sRi6Jh1o7S_riGI')):
        path = f'scraped-data/images/heroes/card-covers/{name}.png'
        with Image.open(ROOT / path) as image:
            image = image.convert('RGBA')
        result.append({'key': hero + ':back', 'language': 'shared', 'path': path,
                       'sha256': sha(ROOT / path), 'type': 'back', 'image': image, 'kind': 'back'})
    return result


def contain(source, spec, scale):
    w, h, band, _ = spec
    image = source['image']
    sw, sh = image.size
    vw, vh = w - 2 * band, h - 2 * band
    crop = 0
    strict_crop = max(0, 1 - vw / (vh * sw / sh)) if source['kind'] == 'back' else 0
    if source['kind'] == 'back':
        # Centre crop <=1.4% total width. Fit remaining image without further crop.
        crop = min(math.floor(sw * .014 / 2), max(0, math.floor(sw * strict_crop / 2)))
        image = image.crop((crop, 0, sw - crop, sh))
    fit = min(vw / image.width, vh / image.height)
    if source['kind'] == 'scan' and w >= 408:
        fit = min(fit, 1.6)
    iw, ih = round(image.width * fit * scale), round(image.height * fit * scale)
    image = image.resize((iw, ih), Image.Resampling.LANCZOS)
    x = round((w * scale - iw) / 2)
    y = round((h * scale - ih) / 2)
    FITS[f"{source['key']}|{source['language']}|{w}x{h}|x{scale}"] = {
        'source_key': source['key'], 'language': source['language'],
        'source_path': source['path'], 'source_sha256': source['sha256'],
        'source_size_px': [sw, sh], 'viewport_su': [vw, vh],
        'draw_rect_px': [x, y, iw, ih], 'logical_scale': max(iw / scale / (sw - 2 * crop), ih / scale / sh),
        'scan_aspect_error_px_at_x1': abs(iw / scale - ih / scale * sw / sh) if source['kind'] == 'scan' else None,
        'scan_crop_px': 0, 'back_side_crop_fraction_total': 2 * crop / sw,
        'strict_cover_required_crop_fraction': strict_crop,
        'back_fit': 'centred-crop-within-budget-then-contain' if crop else 'contain',
        'gap_per_side_su': [(vw - iw / scale) / 2, (vh - ih / scale) / 2],
    }
    return image, (x, y)


def composite(source, spec, state, scale, fitted):
    w, h, band, radius = spec
    padding = 8 if state == 'new' and band == 2 else PADDING
    p = padding * scale
    out = Image.new('RGBA', ((w + 2 * padding) * scale, (h + 2 * padding) * scale))
    # Opaque navy in the viewport, independent from the semi-transparent idle edge.
    ImageDraw.Draw(out).rectangle((p + band * scale, p + band * scale,
                                 p + (w - band) * scale - 1, p + (h - band) * scale - 1), fill=RGB['card.navy'] + (255,))
    image, (x, y) = fitted
    if state == 'not-playable':
        image = image.copy()
        arr = np.asarray(image).copy()
        lum = np.einsum('ijk,k->ij', arr[:, :, :3].astype(np.float32), np.array([.2126, .7152, .0722]))
        arr[:, :, :3] = np.floor(.4 * arr[:, :, :3] + .6 * lum[:, :, None] + .5).astype('uint8')
        arr[:, :, 3] = np.floor(arr[:, :, 3] * .7 + .5).astype('uint8')
        image = Image.fromarray(arr)
    out.alpha_composite(image, (p + x, p + y))
    out.alpha_composite(frame(spec, state, scale), (p, p))
    if state == 'focus':
        out.alpha_composite(focus(spec, scale), (p - 4 * scale, p - 4 * scale))
    if state == 'new':
        # Centre on top-right corner; the marker is exterior and never covers art.
        out.alpha_composite(new_dot(scale), (p + (w - 10) * scale, p + (band - 10) * scale))
    return out


def label(source):
    return f"{source['language'].upper()} {source['key']} / {source['type']}"


def sheet(sources_list, cards, title, scale):
    columns = 6 if len(cards) > 12 else 5
    rows = math.ceil(len(cards) / columns)
    cw = max(max(i.width for i in cards) + 20 * scale, 180 * scale)
    ch = max(i.height for i in cards) + 36 * scale
    sheet = Image.new('RGBA', (columns * cw + 24 * scale, rows * ch + 58 * scale), RGB['card.navy'] + (255,))
    draw = ImageDraw.Draw(sheet)
    font = ImageFont.load_default(size=13 * scale)
    draw.text((12 * scale, 10 * scale), title, fill=RGB['card.glyph'], font=font)
    placements = []
    for i, (source, image) in enumerate(zip(sources_list, cards)):
        x = 12 * scale + i % columns * cw + (cw - image.width) // 2
        y = 40 * scale + i // columns * ch
        sheet.alpha_composite(image, (x, y))
        text = label(source)
        # Wrap long identifiers into two lines on small displays; list index maps to review-index.json.
        if cw < 280 * scale:
            text = f"{i + 1:02d} {source['language'].upper()} {source['key'].split(':')[0]}"
        draw.text((12 * scale + i % columns * cw + 3 * scale, y + image.height + 4 * scale),
                  text, fill=RGB['card.cream'], font=font)
        placements.append({'source_key': source['key'], 'language': source['language'],
                           'source_path': source['path'], 'type': source['type'],
                           'composite_rect_px': [x, y, image.width, image.height]})
    return sheet, placements


def overlay_sheet(display_names, scale):
    # Scan-free comparison; frame apertures show a restrained checker pattern.
    groups = []
    for display in display_names:
        spec = DISPLAYS[display]
        w, h, _, _ = spec
        pad = 8 * scale
        cw, ch = (w + 24) * scale, (h + 54) * scale
        group = Image.new('RGBA', (cw * 7, ch), RGB['card.navy'] + (255,))
        d = ImageDraw.Draw(group)
        d.text((pad, 3 * scale), f'{display} {w}x{h} su / x{scale}', font=ImageFont.load_default(size=14 * scale), fill=RGB['card.glyph'])
        for i, state in enumerate(('idle', 'hover', 'selected', 'warning', 'flash', 'focus', 'mini-idle')):
            x, y = i * cw + 12 * scale, 28 * scale
            # Only token colours; no source imagery.
            d.rectangle((x, y, x + w * scale - 1, y + h * scale - 1), fill=RGB['card.navy'])
            group.alpha_composite(frame(spec, state, scale), (x, y))
            if state == 'focus':
                group.alpha_composite(focus(spec, scale), (x - 4 * scale, y - 4 * scale))
            d.text((x, y + h * scale + 6 * scale), state, font=ImageFont.load_default(size=12 * scale), fill=RGB['card.cream'])
        groups.append(group)
    out = Image.new('RGBA', (max(g.width for g in groups), sum(g.height for g in groups)), RGB['card.navy'] + (255,))
    y = 0
    for group in groups:
        out.alpha_composite(group, (0, y)); y += group.height
    return out


def build():
    start = time.monotonic()
    if not (PACKAGE / 'source-hashes-before.json').is_file():
        raise RuntimeError('Record source hashes before creating output.')
    for directory in ('vector', 'comparison', 'concepts', 'prompts'):
        (PACKAGE / directory).mkdir(exist_ok=True)
    src = sources()
    dump(PACKAGE / 'generation-records.json', {
        'image_generation_used': False, 'generations': [],
        'procedural_prompt_key': 'CP-13-procedural-v1',
        'prompt_file': 'prompts/CP-13-procedural-v1.md',
        'note': 'No ImageGen call; concepts intentionally contains only its explanatory README.'})
    for scale in (1, 2):
        for state in EDGE:
            export_asset(f'vector/card-frame-{state}-x{scale}.png', frame(DISPLAYS['inspector-ru'], state, scale),
                         DISPLAYS['inspector-ru'], state, scale)
        export_asset(f'vector/card-frame-focus-x{scale}.png', focus(DISPLAYS['inspector-ru'], scale),
                     DISPLAYS['inspector-ru'], 'focus', scale, True)
        export_asset(f'vector/card-frame-mini-idle-x{scale}.png', frame(DISPLAYS['opponent-back'], 'mini-idle', scale),
                     DISPLAYS['opponent-back'], 'mini-idle', scale)
        dotpath = f'vector/card-frame-new-dot-x{scale}.png'
        save(PACKAGE / dotpath, new_dot(scale))
        ASSETS[dotpath] = {'size_px': [10 * scale, 10 * scale], 'density': scale,
                          'layer': 'new-marker-only', 'nine_slice_px': [5 * scale] * 4,
                          'nine_slice_uv': [.5] * 4, 'stretch': False}
        for display, spec in DISPLAYS.items():
            for state in EDGE:
                export_asset(f'vector/sizes/{display}/card-frame-{state}-x{scale}.png', frame(spec, state, scale), spec, state, scale)
            export_asset(f'vector/sizes/{display}/card-frame-focus-x{scale}.png', focus(spec, scale), spec, 'focus', scale, True)
    for scale in (1, 2):
        for display, spec in DISPLAYS.items():
            chosen = [s for s in src if s['language'] in (display.split('-')[-1], 'shared')] if display.startswith('inspector-') else src
            fitted = [contain(s, spec, scale) for s in chosen]
            for state in STATES:
                cards = [composite(s, spec, state, scale, f) for s, f in zip(chosen, fitted)]
                image, placements = sheet(chosen, cards, f'CP-13 / {state} / {display} / {spec[0]}x{spec[1]} su / x{scale}', scale)
                name = f'{state}-{display}-x{scale}.png'
                save(DERIVED / name, image)
                save(DERIVED / name.replace('.png', '-gray.png'), gray(image))
                SHEETS[name] = {'state': state, 'display': display, 'density': scale,
                                'size_px': list(image.size), 'entries': placements,
                                'gray': name.replace('.png', '-gray.png')}
            print(f'review {display} x{scale}: {len(chosen)} sources, {len(STATES)} states', flush=True)
        for title, display_names in (('master', ['inspector-ru']),
                                     ('working', [d for d in DISPLAYS if not d.startswith('inspector-')])):
            image = overlay_sheet(display_names, scale)
            save(PACKAGE / f'comparison/overlay-{title}-x{scale}.png', image)
            save(PACKAGE / f'comparison/overlay-{title}-x{scale}-gray.png', gray(image))
    # Presentation-only row demonstrates lift offsets. Frame and scan move together.
    for scale in (1, 2):
        spec = DISPLAYS['hand']; cw = 190 * scale
        image = Image.new('RGBA', (cw * 4, 310 * scale), RGB['card.navy'] + (255,))
        d = ImageDraw.Draw(image)
        for i, (state, shift) in enumerate((('idle', 0), ('hover', -24), ('selected', -32), ('warning', 16))):
            s = src[0]
            card = composite(s, spec, state, scale, contain(s, spec, scale))
            image.alpha_composite(card, (i * cw + 12 * scale, (52 + shift) * scale))
            d.text((i * cw + 12 * scale, 280 * scale), f'{state} {shift:+d} su', font=ImageFont.load_default(size=12 * scale), fill=RGB['card.cream'])
        save(DERIVED / f'lift-comparison-x{scale}.png', image)
        save(DERIVED / f'lift-comparison-x{scale}-gray.png', gray(image))
    dump(PACKAGE / 'asset-contract.json', {'prompt_key': 'CP-13-procedural-v1', 'tokens': TOKENS,
         'assets': ASSETS, 'states': list(STATES), 'displays': {k: list(v) for k, v in DISPLAYS.items()},
         'state_lift_su': {'hover': -24, 'selected': -32, 'warning': 16},
         'flash': {'cue': 'CUE-006', 'duration_ms': 500, 'start': 'flash', 'end': 'idle',
                   'method': 'linear crossfade between independently authored layers', 'reduced_motion': 'one static flash then idle'},
         'not_playable': {'scan_saturation_multiplier': .4, 'scan_opacity': .7, 'preview_only': True},
         'new': {'dot_diameter_su': 8, 'keyline_su': 1, 'position': 'outside top-right, no scan overlap',
                 'expiry': 'first hover or 10 seconds', 'layer_file': 'vector/card-frame-new-dot-x1.png'},
         'nine_slice': {'units': 'physical pixels', 'corner_formula': '(radius_su + edge_su + keyline_su) * density + 1 px',
                        'focus_corner_formula': '(radius_su + gap_su + ring_su) * density + 1 px',
                        'centre': 'transparent', 'stretch_edges': False},
         'density_note': 'x2 is texture density, not 2x logical layout size; su remains unchanged.',
         'mini_edge_policy': 'selected/warning/flash clamp to 1 su inside 2 su band; full edge width impossible without covering scan',
         'class_s_policy': '120x166 frame derived from the explicitly required 112x158 viewport; radius.l kept at 8 su'})
    dump(PACKAGE / 'review-index.json', {'source_assets': [{k: v for k, v in s.items() if k != 'image'} for s in src],
                                       'sheets': SHEETS, 'fitting': FITS})
    dump(PACKAGE / 'write-audit.json', {'guard': 'Python audit hook rejects file writes, filesystem mutations outside the two allowed roots and all subprocesses.',
         'bootstrap_writes': ['art/imagegen/card-frame-v1-codex/source-hashes-before.json',
                              'art/imagegen/card-frame-v1-codex/_tools/draw_icons_v3_snapshot.py'],
         'observed_writes': sorted(WRITES), 'outside_folder': [],
         'scope': 'Writes by this generator only; no claim about independent concurrent sessions.'})
    print(f'Build complete: {len(ASSETS)} vector assets, {len(SHEETS)} colour sheets and grayscale partners; {time.monotonic()-start:.1f}s', flush=True)


def repair_new_mini():
    """Bounded repair of the six new/mini colour sheets and their gray partners."""
    src = sources()
    review = json.loads((PACKAGE / 'review-index.json').read_text(encoding='utf-8'))
    for scale in (1, 2):
        for display in ('opponent-back', 'deck-chip', 'discard-chip'):
            spec = DISPLAYS[display]
            cards = [composite(s, spec, 'new', scale, contain(s, spec, scale)) for s in src]
            image, placements = sheet(src, cards, f'CP-13 / new / {display} / {spec[0]}x{spec[1]} su / x{scale}', scale)
            name = f'new-{display}-x{scale}.png'
            save(DERIVED / name, image)
            save(DERIVED / name.replace('.png', '-gray.png'), gray(image))
            review['sheets'][name] = {'state': 'new', 'display': display, 'density': scale,
                                     'size_px': list(image.size), 'entries': placements,
                                     'gray': name.replace('.png', '-gray.png')}
    dump(PACKAGE / 'review-index.json', review)
    audit_data = json.loads((PACKAGE / 'write-audit.json').read_text(encoding='utf-8'))
    audit_data['observed_writes'] = sorted(set(audit_data['observed_writes']) | WRITES)
    audit_data['repair'] = 'new marker mini-only: y=-8..2 su, outside the 2 su scan inset; 8 su exterior padding'
    dump(PACKAGE / 'write-audit.json', audit_data)
    print('Rebuilt six new/mini colour sheets and six grayscale partners.', flush=True)


if __name__ == '__main__':
    if sys.argv[1:] == ['--repair-new-mini']:
        repair_new_mini()
    elif sys.argv[1:]:
        raise SystemExit('Usage: build_card_frames.py [--repair-new-mini]')
    else:
        build()
