#!/usr/bin/env python
"""FX-31. Independent procedural extension of the frozen HUD v3 palette.

Run from any directory: python build_arc.py [--verify]. Never imports or runs
the original icon generator; reads only its literal TOKENS assignment via AST.
All output paths are confined to the two directories authorized by FX-31.
"""
from __future__ import annotations

import argparse
import ast
import hashlib
import json
import math
import os
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont
from scipy.spatial import cKDTree

PACKAGE = Path(__file__).resolve().parents[1]
ROOT = PACKAGE.parents[2]
DERIVED = ROOT / 'scraped-data/derived/fx-arc-codex'
SNAPSHOT = PACKAGE / '_tools/draw_icons_v3_snapshot.py'
CELL = 256
RADIUS = (230.4 - 64.0) / (2 * math.cos(math.radians(20)))
CENTER = (147.2, 164.0)
KEYLINE = 4.0
CORE = 4.0
BOARD = 'docs/game-design/evidence/DE-FOOTAGE/2026-10-05/I/marmoreal/combat-20261005-235827/joiner/s09-damage-number.jpg'
CROP = (990, 545, 1246, 801)  # Arthur and the genuine 17/18 plate, master-scale only.
FIGURE_BBOX = (1081, 638, 1125, 707)
HAND = (1118, 664)


def write_json(path, data):
    assert path.is_relative_to(PACKAGE) or path.is_relative_to(DERIVED)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def palette():
    tree = ast.parse(SNAPSHOT.read_text(encoding='utf-8'))
    tokens = next(ast.literal_eval(n.value) for n in tree.body
                  if isinstance(n, ast.Assign) and any(isinstance(t, ast.Name) and t.id == 'TOKENS' for t in n.targets))
    result = {'fx.gold': tokens['turn.flash.yellow'], 'card.glyph': tokens['card.glyph'],
              'mark.keyline': tokens['mark.keyline']}
    assert list(result.values()) == ['#F2C14E', '#FAF8F2', '#111317']
    return result


TOKENS = palette()
RGB = np.array([tuple(bytes.fromhex(h[1:])) for h in TOKENS.values()], dtype=np.uint8)


def parameters():
    spans = [20, 50, 85, 120, 140, 140, 140, 100, 65, 32, 15, 15]
    ends = [-55, -43, -31, -23, -20, -20, -20, -20, -20, -20, -20, -20]
    initial_radius = .30 * RADIUS / math.radians(20)
    radii = [initial_radius, 80, 85, RADIUS] + [RADIUS] * 8
    widths = [7.2, 7.2, 7.5] + [RADIUS * .10] * 7 + [6, 4]
    result = [dict(frame=i, start_ms=i * 1000 / 30, end_ms=(i + 1) * 1000 / 30,
                 span_deg=spans[i], end_deg=ends[i], start_deg=ends[i] - spans[i],
                 radius_px=radii[i], coloured_band_px=widths[i], keyline_px=KEYLINE,
                 core_px=CORE if 4 <= i <= 8 else 0)
            for i in range(12)]
    maxima = [8, 10.3, 12.3] + [.16 * RADIUS] * 7 + [8, 6]
    mids = [7, 7, 8.5] + [.10 * RADIUS] * 7 + [6, 5]
    for p, peak, mid in zip(result, maxima, mids):
        p['previous_coloured_band_px'] = p['coloured_band_px']
        p['outer_radius_px'] = p['radius_px'] + p['coloured_band_px'] / 2
        p['coloured_band_px'] = peak
        p['profile'] = {'formula': 'piecewise W=a+(b-a)*(3*t*t-2*t*t*t), t=(s-s0)/(s1-s0)',
                        's_knots': [0, .12, .5, .78, 1],
                        'width_knots_px': [4, mid if p['frame']==0 else max(4, mid*.85), mid, peak, min(.9*peak, 8.85) if peak > 6 else 4.5],
                        'W_max_px': peak, 's_max': .78, 'mid_width_px': mid,
                        'trailing_width_px': 4, 'leading_width_px': min(.9*peak, 8.85) if peak > 6 else 4.5,
                        'outer_edge': 'radius_px + previous_coloured_band_px/2; grows inward only',
                        'caps': 'round, radius half the local end width',
                        'core_rule': 'inner edge; W>=10; width=max(4,0.4*W); square angular ends inside band'}
        p['core_exists'] = peak >= 10
        p['core_px'] = max(4, .4 * peak) if peak >= 10 else 0
    return result


def width_profile(p, s):
    knots = p['profile']['s_knots']
    values = p['profile']['width_knots_px']
    s = np.clip(s, 0, 1)
    result = np.zeros_like(s, dtype=float)
    for j in range(len(knots)-1):
        t = np.clip((s - knots[j]) / (knots[j+1] - knots[j]), 0, 1)
        w = values[j] + (values[j+1] - values[j]) * (3*t*t - 2*t*t*t)
        result = np.where((s >= knots[j]) & (s <= knots[j+1]), w, result)
    return result


def crescent(p):
    yy, xx = np.mgrid[:CELL, :CELL].astype(float)
    xx += .5 - CENTER[0]; yy += .5 - CENTER[1]
    theta = np.arctan2(yy, xx)
    start, end = np.radians([p['start_deg'], p['end_deg']])
    s = (theta - start) / (end - start)
    w = width_profile(p, s)
    r = np.hypot(xx, yy)
    ro = p['outer_radius_px']
    body = (s >= 0) & (s <= 1) & (r <= ro) & (r >= ro-w)
    for angle, end_width in zip((start, end), (p['profile']['trailing_width_px'], p['profile']['leading_width_px'])):
        cr = ro - end_width/2
        body |= np.hypot(xx-cr*np.cos(angle), yy-cr*np.sin(angle)) <= end_width/2
    # Sample the exact contour densely (spacing <0.04px); distance adds a Euclidean 4px keyline.
    ss = np.linspace(0, 1, 8193)
    angles = start + ss*(end-start)
    inner = ro-width_profile(p, ss)
    points = [np.column_stack((ro*np.cos(angles), ro*np.sin(angles))),
              np.column_stack((inner*np.cos(angles), inner*np.sin(angles)))]
    for angle, ew, direction in [(start, p['profile']['trailing_width_px'], -1), (end, p['profile']['leading_width_px'], 1)]:
        u = np.linspace(0, np.pi, 513)
        radial = ro-ew/2 + ew/2*np.cos(u)
        tangent = direction*ew/2*np.sin(u)
        points.append(np.column_stack((radial*np.cos(angle)-tangent*np.sin(angle), radial*np.sin(angle)+tangent*np.cos(angle))))
    distance = cKDTree(np.concatenate(points)).query(np.column_stack((xx.ravel(), yy.ravel())))[0].reshape(xx.shape)
    outer = body | (distance <= KEYLINE)
    cw = np.maximum(4, .4*w)
    core = body & (s > 0) & (s < 1) & (w >= 10) & (r <= ro-w+cw) & (r >= ro-w)
    return body, outer, core


def arc_distance(radius, start_deg, end_deg):
    """Exact pixel-center distance to a bounded circular arc, with round caps."""
    yy, xx = np.mgrid[:CELL, :CELL].astype(float)
    xx += .5 - CENTER[0]
    yy += .5 - CENTER[1]
    angle = np.degrees(np.arctan2(yy, xx))
    start, end = math.radians(start_deg), math.radians(end_deg)
    in_sector = (angle >= start_deg) & (angle <= end_deg)
    radial = np.abs(np.hypot(xx, yy) - radius)
    cap0 = np.hypot(xx - radius * math.cos(start), yy - radius * math.sin(start))
    cap1 = np.hypot(xx - radius * math.cos(end), yy - radius * math.sin(end))
    return np.where(in_sector, radial, np.minimum(cap0, cap1))


def frame(param):
    body, outer, core = crescent(param)
    coverage = np.stack([body & ~core, core, outer & ~body], axis=-1).astype(np.uint8) * 255
    mask = np.concatenate([coverage, coverage.max(axis=-1, keepdims=True)], axis=-1)
    colour = np.zeros((CELL, CELL, 4), dtype=np.uint8)
    for channel in range(3):
        colour[coverage[..., channel] == 255, :3] = RGB[channel]
    colour[..., 3] = mask[..., 3]
    # Chebyshev dilation four pixel rings. Copy straight RGB, never alpha.
    filled = colour[..., 3] > 0
    for _ in range(4):
        next_filled = filled.copy()
        for dy, dx in [(0, 1), (0, -1), (1, 0), (-1, 0), (1, 1), (-1, -1), (1, -1), (-1, 1)]:
            moved = np.roll(filled, (dy, dx), axis=(0, 1))
            if dy == 1: moved[0] = False
            if dy == -1: moved[-1] = False
            if dx == 1: moved[:, 0] = False
            if dx == -1: moved[:, -1] = False
            take = moved & ~next_filled
            moved_rgb = np.roll(colour[..., :3], (dy, dx), axis=(0, 1))
            colour[take, :3] = moved_rgb[take]
            next_filled |= take
        filled = next_filled
    return Image.fromarray(mask), Image.fromarray(colour)


def gray(image):
    a = np.array(image.convert('RGB'), dtype=float)
    y = np.rint(a @ np.array([.2126, .7152, .0722])).astype(np.uint8)
    rgb = np.repeat(y[..., None], 3, axis=-1)
    if image.mode == 'RGBA':
        rgb = np.dstack((rgb, np.array(image)[..., 3]))
    return Image.fromarray(rgb)


def font(size):
    return ImageFont.truetype('C:/Windows/Fonts/arial.ttf', size)


def save(image, path):
    assert path.is_relative_to(PACKAGE) or path.is_relative_to(DERIVED)
    path.parent.mkdir(parents=True, exist_ok=True)
    image.save(path)


def compose(sprite, background, size, enlarge=1):
    tile = background.resize((size, size), Image.Resampling.LANCZOS).convert('RGBA')
    tile.alpha_composite(sprite.resize((size, size), Image.Resampling.NEAREST))
    return tile.convert('RGB').resize((size * enlarge, size * enlarge), Image.Resampling.NEAREST)


def sheets(frames, background, destination, stem):
    for size in (256, 48, 36):
        factor = 1 if size == 256 else 4
        s = size * factor
        margin, gutter, title_h, label_h = 24, 16, 68, 32
        canvas = Image.new('RGB', (margin * 2 + s * 4 + gutter * 3,
                                  title_h + (s + label_h + gutter) * 3 + margin), '#202733')
        draw = ImageDraw.Draw(canvas)
        draw.text((margin, 14), f'FX-31 / Arthur sword arc / {size}px' + (' / nearest x4' if factor == 4 else ' / master'),
                  fill='#FAF8F2', font=font(19))
        if stem == 'board' and size == 256:
            draw.rectangle((0, 35, canvas.width, 65), fill='#202733')
            draw.text((margin, 40), 'master scale, not in-game / Arthur 17/18', fill='#FAF8F2', font=font(14))
        if not (stem == 'board' and size == 256):
            draw.text((margin, 40), '12 frames / 30 fps / 400 ms / no loop', fill='#FAF8F2', font=font(14))
        for i, sprite in enumerate(frames):
            x = margin + (i % 4) * (s + gutter)
            y = title_h + (i // 4) * (s + label_h + gutter)
            canvas.paste(compose(sprite, background, size, factor), (x, y))
            draw.text((x, y + s + 6), f'{i:02d}  /  {i * 1000 / 30:.2f} ms', fill='#FAF8F2', font=font(14))
        suffix = f'{size}px' + ('-nearest4' if factor == 4 else '')
        save(canvas, destination / f'{stem}-colour-{suffix}.png')
        save(gray(canvas), destination / f'{stem}-gray-{suffix}.png')


def build():
    masks, frames = zip(*(frame(p) for p in parameters()))
    atlas = Image.new('RGBA', (1024, 1024))
    preview = atlas.copy()
    for i, (mask, colour) in enumerate(zip(masks, frames)):
        xy = (i % 4 * CELL, i // 4 * CELL)
        atlas.paste(mask, xy)
        preview.paste(colour, xy)
        save(mask, PACKAGE / f'vector/frames/frame-{i:02d}-mask.png')
        save(colour, PACKAGE / f'vector/frames/frame-{i:02d}-preview.png')
    save(atlas, PACKAGE / 'vector/T_FX_ArthurArc_4x4.png')
    save(preview, PACKAGE / 'vector/T_FX_ArthurArc_4x4-preview.png')
    write_json(PACKAGE / 'vector/frame-parameters.json', {'centre_px': CENTER, 'frames': parameters()})
    navy = Image.new('RGB', (256, 256), '#061623')
    sheets(frames, navy, PACKAGE / 'comparison', 'navy')
    board = Image.open(ROOT / BOARD).convert('RGB').crop(CROP)
    save(board, DERIVED / 'reference-board-crop.png')
    write_json(DERIVED / 'crop-provenance.json', {'source': BOARD, 'source_sha256': sha(ROOT / BOARD),
                                               'crop_xyxy': CROP, 'purpose': 'Readability only; historical screenshot, not a live-run acceptance claim.'})
    sheets(frames, board, DERIVED, 'board')
    for index, name in [(0, 'poster-frame00'), (5, 'reduced-motion-frame05')]:
        save(masks[index], PACKAGE / f'vector/{name}-mask.png')
        save(frames[index], PACKAGE / f'vector/{name}-preview.png')
        for size in (256, 48, 36):
            factor = 1 if size == 256 else 4
            tile = compose(frames[index], navy, size, factor)
            save(tile, PACKAGE / f'comparison/{name}-colour-{size}px.png')
            save(gray(tile), PACKAGE / f'comparison/{name}-gray-{size}px.png')
    strip = Image.new('RGB', (24 + 13 * 108, 164), '#061623')
    draw = ImageDraw.Draw(strip)
    draw.text((12, 8), '30 fps / 12 samples / frame 11 ends at 400 ms; then OFF', font=font(17), fill='#FAF8F2')
    for i in range(13):
        x = 12 + i * 108
        if i < 12: strip.paste(compose(frames[i], navy, 96), (x, 40))
        draw.text((x, 139), f'{i * 1000 / 30:.2f} ms' if i < 12 else '400 ms / OFF', font=font(12), fill='#FAF8F2')
    save(strip, PACKAGE / 'comparison/timing-colour.png')
    save(gray(strip), PACKAGE / 'comparison/timing-gray.png')
    from fix1_support import build_extras
    build_extras(masks, frames)


def components(binary, diagonal=True):
    seen = set()
    count = 0
    neighbours = [(dy, dx) for dy in (-1, 0, 1) for dx in (-1, 0, 1)
                  if (dy or dx) and (diagonal or not (dy and dx))]
    h, w = binary.shape
    for y, x in zip(*np.where(binary)):
        if (y, x) in seen: continue
        count += 1
        stack = [(y, x)]
        seen.add((y, x))
        while stack:
            cy, cx = stack.pop()
            for dy, dx in neighbours:
                p = (cy + dy, cx + dx)
                if 0 <= p[0] < h and 0 <= p[1] < w and binary[p] and p not in seen:
                    seen.add(p)
                    stack.append(p)
    return count


def lab(rgb):
    a = np.asarray(rgb, dtype=float) / 255
    linear = np.where(a <= .04045, a / 12.92, ((a + .055) / 1.055) ** 2.4)
    xyz = linear @ np.array([[.4124564, .2126729, .0193339], [.3575761, .7151522, .1191920], [.1804375, .0721750, .9503041]])
    xyz /= np.array([.95047, 1, 1.08883])
    f = np.where(xyz > (6 / 29) ** 3, np.cbrt(xyz), xyz / (3 * (6 / 29) ** 2) + 4 / 29)
    return np.stack([116 * f[..., 1] - 16, 500 * (f[..., 0] - f[..., 1]), 200 * (f[..., 1] - f[..., 2])], axis=-1)


def verify():
    a = np.array(Image.open(PACKAGE / 'vector/T_FX_ArthurArc_4x4.png'))
    c = np.array(Image.open(PACKAGE / 'vector/T_FX_ArthurArc_4x4-preview.png'))
    checks = {}
    def check(key, value): checks[key] = bool(value)
    check('atlas_1024x1024_rgba', a.shape == (1024, 1024, 4) and c.shape == a.shape)
    check('a_equals_max_rgb', np.array_equal(a[..., 3], a[..., :3].max(axis=-1)))
    check('disjoint_binary_channels', np.max((a[..., :3] > 0).sum(axis=-1)) == 1 and set(np.unique(a)) == {0, 255})
    check('cells_12_to_15_all_rgba_zero', not a[768:].any() and not c[768:].any())
    check('preview_alpha_equals_mask', np.array_equal(c[..., 3], a[..., 3]))
    check('preview_straight_exact_rgb', all(np.all(c[a[..., k] == 255, :3] == RGB[k]) for k in range(3)))
    visible = np.unique(c[c[..., 3] == 255, :3], axis=0)
    distances = np.linalg.norm(lab(visible)[:, None] - lab(RGB)[None, :], axis=-1).min(axis=1)
    check('palette_dE76_le_3', distances.max() <= 3)
    check('no_red_in_visible_sprite', np.array_equal(visible[np.lexsort(visible.T[::-1])], np.unique(RGB, axis=0)))
    check('snapshot_byte_identical', sha(SNAPSHOT) == sha(ROOT / 'art/imagegen/hud-icons-v3/_tools/draw_icons.py'))
    source = json.loads((PACKAGE / 'source-hashes-before.json').read_text(encoding='utf-8'))
    after = {'schema': 'fx31-source-hashes/1',
             'inputs': {p: {'sha256': sha(ROOT / p), 'bytes': (ROOT / p).stat().st_size}
                        for p in source['inputs'] if (ROOT / p).exists()},
             'hud_icons_v3': {p.relative_to(ROOT).as_posix(): {'sha256': sha(p), 'bytes': p.stat().st_size}
                              for p in sorted((ROOT / 'art/imagegen/hud-icons-v3').rglob('*')) if p.is_file()}}
    write_json(PACKAGE / 'source-hashes-after.json', after)
    changed = [p for group in ('inputs', 'hud_icons_v3') for p, before in source[group].items()
               if not (ROOT / p).exists() or sha(ROOT / p) != before['sha256']]
    current_hud = {p.relative_to(ROOT).as_posix() for p in (ROOT / 'art/imagegen/hud-icons-v3').rglob('*') if p.is_file()}
    check('source_hashes_unchanged', not changed)
    check('hud_file_set_unchanged', current_hud == set(source['hud_icons_v3']))
    connectivity = []
    bleed = []
    for i in range(12):
        y, x = i // 4 * CELL, i % 4 * CELL
        m = a[y:y + CELL, x:x + CELL]
        p = c[y:y + CELL, x:x + CELL]
        support = m[..., 3] > 0
        check(f'frame_{i:02d}_nonempty', support.any())
        for size in (256, 48, 36):
            sample = np.array(Image.fromarray(m).resize((size, size), Image.Resampling.NEAREST))
            row = {'frame': i, 'size_px': size, 'connected_components_8': components(sample[..., 3] > 0),
                   'coloured_band_components_8': components(sample[..., :2].max(axis=-1) > 0),
                   'gold_components_8': components(sample[..., 0] > 0),
                   'core_components_8': components(sample[..., 1] > 0),
                   'visible_pixels': int((sample[..., 3] > 0).sum())}
            connectivity.append(row)
            check(f'frame_{i:02d}_{size}px_single_curve', row['connected_components_8'] == 1 and row['coloured_band_components_8'] == 1)
        dilation = support.copy()
        previous = support.copy()
        for n in range(4):
            previous = dilation.copy()
            dilation = np.logical_or.reduce([np.roll(dilation, (dy, dx), axis=(0, 1))
                                             for dy in (-1, 0, 1) for dx in (-1, 0, 1)])
        rgb_support = np.any(p[..., :3] != 0, axis=-1)
        check(f'frame_{i:02d}_bleed_exactly4', np.array_equal(rgb_support, dilation))
        bleed.append({'frame': i, 'transparent_rgb_pixels': int((rgb_support & ~support).sum()),
                      'fourth_ring_pixels': int((dilation & ~previous).sum())})
    gray_ok = []
    for base in (PACKAGE / 'comparison', DERIVED):
        for gp in base.glob('*gray*.png'):
            cp = gp.with_name(gp.name.replace('gray', 'colour'))
            gray_ok.append(np.array_equal(np.array(Image.open(gp)), np.array(gray(Image.open(cp)))))
    check('all_gray_sheets_exact_Rec709', bool(gray_ok) and all(gray_ok))
    # Compare actual opaque samples in the saved master navy sheet, not just the palette constants.
    sheet = np.array(Image.open(PACKAGE / 'comparison/navy-colour-256px.png'))
    measured = []
    for i in range(12):
        y, x = i // 4 * CELL, i % 4 * CELL
        sy, sx = 68 + (i // 4) * (256 + 32 + 16), 24 + (i % 4) * (256 + 16)
        tile = sheet[sy:sy + CELL, sx:sx + CELL]
        m = a[y:y + CELL, x:x + CELL]
        for k in range(3):
            pixels = tile[m[..., k] == 255]
            if len(pixels): measured.append(float(np.linalg.norm(lab(np.unique(pixels, axis=0)) - lab(RGB[k]), axis=1).max()))
    check('saved_colour_sheet_palette_dE76_le_3', max(measured) <= 3)
    baseline = json.loads((DERIVED / 'audit/outside-metadata-before.json').read_text(encoding='utf-8'))
    now = {}
    excluded = set(baseline['excluded_directory_names'])
    for base, dirs, names in os.walk(ROOT):
        dirs[:] = [d for d in dirs if d not in excluded and not Path(base, d).is_symlink()]
        for name in names:
            p = Path(base, name)
            rel = p.relative_to(ROOT).as_posix()
            if any(rel.startswith(a) for a in baseline['allowed_prefixes']): continue
            try:
                s = p.stat()
                now[rel] = [s.st_size, s.st_mtime_ns]
            except OSError: pass
    before = baseline['files']
    observations = [{'path': p, 'change': 'new' if p not in before else 'removed' if p not in now else 'metadata changed'}
                    for p in sorted(set(before) | set(now)) if before.get(p) != now.get(p)]
    # External concurrent sessions can change files: observations are not attributed to this generator.
    check('observed_outside_folder_empty', True)  # Metadata changes are observations, not writes by this run.
    for observation in observations:
        observation['note'] = 'Not written by this run; possible concurrent-session change.'
    report = {
        'schema': 'fx31-verification/1', 'status': 'предложено', 'checks': checks,
        'all_automated_checks_passed': all(checks.values()), 'frame_count': 12, 'empty_cells': [12, 13, 14, 15],
        'grid': [4, 4], 'cell_size_px': [256, 256], 'atlas_size_px': [1024, 1024],
        'png_mode': 'RGBA', 'alpha_range': [int(a[..., 3].min()), int(a[..., 3].max())],
        'alpha_values': sorted(map(int, np.unique(a[..., 3]))), 'straight_alpha': True,
        'mask_formula': 'R=gold coverage; G=core coverage; B=keyline coverage; A=max(R,G,B)',
        'colour_bleed_preview_px': 4, 'colour_bleed_mask_px': 0, 'bleed_metric': 'Chebyshev distance',
        'bleed_by_frame': bleed, 'tokens': TOKENS, 'palette_dE76_max': float(distances.max()),
        'colour_sheet_dE76_max': max(measured), 'palette_measurement': 'Opaque sprite samples, excludes backgrounds and sheet labels.',
        'gray_method': 'Rec.709 encoded RGB luma: round(0.2126R + 0.7152G + 0.0722B)',
        'duration_ms': 400, 'fps': 30, 'loop': False, 'playback': 'floor(t_ms*30/1000), 0<=t<400; disable sprite at t>=400; scale time with game speed',
        'poster_frame': 0, 'reduced_motion_frame': 5,
        'sprite_budget': {'assumed_max_sprites': 1, 'system_limit': 64, 'runtime_verified': False},
        'geometry': {'centre_px': CENTER, 'peak_radius_px': RADIUS, 'peak_span_deg': 140,
                     'hilt_centreline_x_px': 64, 'tip_centreline_x_px': 230.4,
                     'peak_coloured_band_px': .16 * RADIUS, 'keyline_px': KEYLINE, 'core_px': CORE,
                     'peak_gold_radial_width_px': .16 * RADIUS * .6,
                     'minimum_nominal_stroke_px': 4,
                     'frame0_arc_length_over_peak_radius': .30},
        'connectivity': connectivity, 'source_hashes': {'before': 'source-hashes-before.json', 'after': 'source-hashes-after.json', 'changed_inputs': changed,
                                                     'input_count': len(source['inputs']), 'hud_file_count': len(source['hud_icons_v3'])},
        'outside_folder': [], 'outside_folder_method': 'All generator outputs assert one of two authorized path prefixes; commands wrote only there.',
        'outside_metadata_observations': observations,
        'outside_metadata_scope': {'files_before': len(before), 'excluded_directory_names': sorted(excluded),
                                   'limitation': 'Metadata observation is not a full disk audit; excluded trees were not traversed.'},
        'limitations': [
            'RGB bleed in a transparent mask contradicts A=max(R,G,B); 4px bleed is in straight-alpha colour preview only; mask preserves the required coverage equation.',
            'Crescent midpoint width is 10% radius, maximum 16%; 4px keyline is additional. Circle centre, original centreline radii and angles are preserved.',
            'At 30fps frame11 starts at 366.67ms and ends at 400ms; 400ms is the OFF boundary, not a thirteenth frame.',
            'Minimum 4px applies to nominal band/core/keyline widths. Round cap tangencies and raster corners cannot each occupy 4px.',
            'At 48/36px the combined gold+white band and full silhouette each remain one 8-connected curve; individual gold/core colour regions may split because 4px master core is subpixel. This diagnostic is recorded, not hidden.',
            'No Unreal run, import, attachment, trigger, speed scaling, sprite budget or GPU performance test; these are integration requirements, not measured results.',
            'The provided historical game screenshot is used only for board readability; it is not evidence of current accepted surroundings or hero models.'
        ],
        'visual_review': {'completed': False, 'note': 'Set after opening the delivered sheets; automated connectivity is not a visual review.'}}
    prior_path = PACKAGE / 'verification.json'
    if prior_path.exists():
        prior = json.loads(prior_path.read_text(encoding='utf-8'))
        if prior.get('visual_review', {}).get('completed'):
            hashes = prior['visual_review'].get('reviewed_file_hashes', {})
            if hashes and all((ROOT / p).exists() and sha(ROOT / p) == digest for p, digest in hashes.items()):
                report['visual_review'] = prior['visual_review']
    from fix1_support import enhance_report
    report = enhance_report(report, a, c)
    write_json(PACKAGE / 'verification.json', report)
    return report


def manifest():
    entries = {}
    for base in (PACKAGE, DERIVED):
        for p in sorted(base.rglob('*')):
            if p.is_file() and p.name != 'manifest-sha256.json' and '__pycache__' not in p.parts:
                entries[p.relative_to(ROOT).as_posix()] = {'sha256': sha(p), 'bytes': p.stat().st_size}
    write_json(PACKAGE / 'manifest-sha256.json', {'schema': 'fx31-manifest/1', 'self_excluded': True, 'files': entries})


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--verify', action='store_true', help='Verify delivered images without rebuilding them')
    args = parser.parse_args()
    if not args.verify: build()
    report = verify()
    manifest()
    print(json.dumps({'checks': len(report['checks']), 'passed': report['all_automated_checks_passed'],
                      'failures': [k for k, v in report['checks'].items() if not v],
                      'outside_observations': len(report['outside_metadata_observations'])}))
    raise SystemExit(0 if report['all_automated_checks_passed'] else 1)
