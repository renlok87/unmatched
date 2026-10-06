#!/usr/bin/env python
"""HB-08: procedural skins extension of the unchanged v3 engine. No UE or git.

python -B art/imagegen/hud-skins-v1-codex/_tools/draw_skins.py --mode skins
All writable paths are confined to PACKAGE and DERIVED. Dependencies: pycairo,
numpy, Pillow; no network, fonts, or image-generation service is used.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path

import cairo
import numpy as np
from PIL import Image, ImageOps

sys.dont_write_bytecode = True
PACKAGE = Path(__file__).resolve().parents[1]
ROOT = PACKAGE.parents[2]
DERIVED = ROOT / 'scraped-data/derived/hud-skins-v1-codex'
spec = importlib.util.spec_from_file_location('hb08_v3', PACKAGE / '_tools/draw_icons_v3_snapshot.py')
v3 = importlib.util.module_from_spec(spec)
spec.loader.exec_module(v3)

TOKENS = {k: v3.TOKENS[k] for k in (
    'card.navy', 'card.cream', 'card.glyph', 'turn.flash.yellow',
    'state.pending', 'state.error', 'text.secondary', 'mark.keyline')}
TOKENS.update({'panel.bg.inset': '#15232E', 'panel.bg.hover': '#1E2B35',
               'panel.bg.pressed': '#040E17', 'state.warning': '#E8812C',
               'text.primary': '#F2EDE4', 'primary.hover': '#F3C55B',
               'primary.pressed': '#D5AA45', 'primary.disabled': '#4E5457'})
BACKGROUNDS = {
    'marmoreal': {'source': 'docs/game-design/evidence/ENV-MAPS/p7-concept-paste-2026-10-01/p7c/packaged-marmoreal/bench-K1-1920x1080.png',
                  'crop': [300, 80, 1540, 680]},
    'sarpedon': {'source': 'docs/game-design/evidence/ENV-MAPS/p10-sarpedon-rework-2026-10-03/sarpedon-packaged/bench-K1-1920x1080.png',
                 'crop': [300, 80, 1540, 680]},
}
NAMES = [
    'Panel', 'PanelInset', 'Modal', 'Btn_Normal', 'Btn_Hover', 'Btn_Pressed',
    'Btn_Disabled', 'Btn_Focus', 'Btn_Selected', 'BtnPrimary_Normal',
    'BtnPrimary_Hover', 'BtnPrimary_Pressed', 'BtnPrimary_Disabled',
    'BtnPrimary_Focus', 'Toast', 'ToastWarning', 'Capsule', 'Tag', 'Chip',
    'KeyChip', 'ProgressTrack', 'ProgressFill', 'SliderTrack', 'SliderThumb',
    'Check_Off', 'Check_On', 'Input_Normal', 'Input_Focus', 'Input_Error',
]
GROUPS = [NAMES[:3], NAMES[3:9], NAMES[9:14], NAMES[14:20], NAMES[20:26], NAMES[26:]]


def dump(path: Path, data):
    guarded(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


def guarded(path: Path):
    q = path.resolve()
    if not (q.is_relative_to(PACKAGE) or q.is_relative_to(DERIVED)):
        raise ValueError(f'Write outside HB-08 roots: {q}')


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def rgb(token):
    return np.array([round(c * 255) for c in v3.hx(TOKENS[token])], dtype=float)


def geometry(name):
    radius, width, height = 4, 32, 24
    if name in ('Panel', 'PanelInset'):
        radius, width, height = 6, 64, 48
    elif name == 'Modal':
        radius, width, height = 8, 64, 48
    elif name in ('Toast', 'ToastWarning'):
        radius, width, height = 6, 48, 24
    elif name in ('ProgressTrack', 'ProgressFill', 'SliderTrack'):
        radius, width, height = 2, 24, 8
    elif name in ('SliderThumb', 'Check_Off', 'Check_On', 'KeyChip'):
        width, height = 24, 24
    return radius, width, height


def style(name):
    body, opacity, edge, edge_opacity, thickness = 'card.navy', .92, 'card.cream', .45, 1
    cue = 'continuous'
    if name == 'PanelInset':
        body = 'panel.bg.inset'
    if name == 'Modal':
        opacity = 1.
    if name == 'Btn_Hover':
        body, edge_opacity = 'panel.bg.hover', 1.
    if name == 'Btn_Pressed':
        body, edge_opacity = 'panel.bg.pressed', 1.
    if name == 'Btn_Disabled':
        edge_opacity = .16
    if name == 'Btn_Selected':
        body, opacity, edge, edge_opacity = 'state.pending', 1., 'card.glyph', 1.
    if name.startswith('BtnPrimary'):
        body, opacity, edge, edge_opacity = 'turn.flash.yellow', 1., 'card.navy', 1.
        if name.endswith('_Hover'):
            body, edge, edge_opacity = 'primary.hover', 'card.cream', 1.
        if name.endswith('_Pressed'):
            body, edge, edge_opacity = 'primary.pressed', 'card.cream', 1.
        if name.endswith('_Disabled'):
            body = 'primary.disabled'
    if name == 'ToastWarning':
        edge, edge_opacity, thickness = 'state.warning', 1., 2
    if name == 'ProgressFill':
        body, opacity, edge, edge_opacity = 'state.pending', 1., 'card.glyph', 1.
    if name in ('ProgressTrack', 'SliderTrack'):
        body = 'panel.bg.inset'
    if name == 'SliderThumb':
        body, opacity, edge, edge_opacity = 'card.glyph', 1., 'card.navy', 1.
    if name == 'KeyChip':
        body = 'panel.bg.inset'
    if name == 'Check_On':
        body, opacity, edge, edge_opacity = 'state.pending', 1., 'card.glyph', 1.
    return dict(body=body, body_opacity=opacity, edge=edge, edge_opacity=edge_opacity,
                edge_su=thickness, shape_cue=cue)


def mask(width, height, callback):
    surface = cairo.ImageSurface(cairo.FORMAT_ARGB32, width, height)
    ctx = cairo.Context(surface)
    ctx.set_source_rgba(1, 1, 1, 1)
    callback(ctx)
    surface.flush()
    raw = np.frombuffer(surface.get_data(), dtype=np.uint8).reshape(height, surface.get_stride())
    return raw[:, :width * 4].reshape(height, width, 4)[:, :, 3].astype(float) / 255.


def rect_mask(width, height, x, y, w, h, radius):
    def draw(ctx):
        v3.rect_sil(x, y, w, h, radius).path(ctx)
        ctx.fill()
    return mask(width, height, draw)


def merge_layers(layers):
    """Adjacent area masks, additive premultiplication: no opaque baked alpha blends.

    Straight borders retain token RGB and their own opacity; fractional path
    coverage is explicitly identified by the independent palette verifier.
    """
    alpha = sum(m * a for m, _, a in layers)
    premul = sum((m * a)[..., None] * rgb(t) for m, t, a in layers)
    color = np.zeros_like(premul)
    np.divide(premul, alpha[..., None], out=color, where=alpha[..., None] > 0)
    rgba = np.dstack((np.rint(color), np.rint(alpha * 255))).clip(0, 255).astype(np.uint8)
    return Image.fromarray(rgba)


def render(name, scale):
    radius, bw, bh = geometry(name)
    st = style(name)
    focus = name.endswith('_Focus')
    extra = 4 * scale if focus else 0
    width, height = bw * scale + 2 + 2 * extra, bh * scale + 2 + 2 * extra
    x, y, w, h = 1, 1, width - 2, height - 2
    rad = (radius + (4 if focus else 0)) * scale
    thickness = (2 if focus else st['edge_su']) * scale
    outer = rect_mask(width, height, x, y, w, h, rad)
    inner = rect_mask(width, height, x + thickness, y + thickness,
                      w - thickness * 2, h - thickness * 2, rad - thickness)
    border = np.clip(outer - inner, 0, 1)
    if focus:
        layers = [(border, 'card.glyph', 1.)]
    else:
        # The body occupies the entire rounded silhouette. Porter-Duff OVER
        # bakes the translucent closed edge over that body, including corners.
        body = merge_layers([(outer, st['body'], st['body_opacity'])])
        edge = merge_layers([(border, st['edge'], st['edge_opacity'])])
        image = Image.alpha_composite(body, edge)
    if focus:
        image = merge_layers(layers)
    if name == 'Check_On':
        def check(ctx):
            pts = [(7, 12), (10, 15), (17, 8), (19, 10), (10, 19), (5, 14)]
            v3.poly(ctx, [(1 + px * scale, 1 + py * scale) for px, py in pts])
            ctx.fill()
        overlay = merge_layers([(mask(width, height, check), 'card.glyph', 1.)])
        image = Image.alpha_composite(image, overlay)
    if name == 'Input_Error':
        # Tiny X in the protected upper-right corner; larger runtime sign is supplied too.
        def cross(ctx):
            ctx.set_line_width(scale)
            cx, cy, half = width - 3 * scale - 1, 1 + 3 * scale, 1.5 * scale
            for sign in (-1, 1):
                ctx.move_to(cx - half, cy - sign * half)
                ctx.line_to(cx + half, cy + sign * half)
            ctx.stroke()
        image = Image.alpha_composite(image, merge_layers([(mask(width, height, cross), 'state.error', 1.)]))
    margin = rad + thickness + 1
    meta = {
        'size_px': [width, height], 'content_su': [bw, bh], 'scale': scale,
        'slice_px': dict(left=margin, top=margin, right=margin, bottom=margin),
        'radius_su': radius + (4 if focus else 0), 'edge_px': thickness,
        'transparent_field_px': 1, 'style': st,
        'focus_overlay': focus, 'focus_outset_su': 4 if focus else 0,
        'focus_gap_su': 2 if focus else None,
        'focus_base': 'BtnPrimary_Normal' if name.startswith('BtnPrimary') else 'Input_Normal' if name.startswith('Input') else 'Btn_Normal',
        'stretch': 'none' if name.startswith('Check_') else 'nine_slice',
        'checkbox_note': 'Fixed native 24 su; never stretched.' if name.startswith('Check_') else None,
    }
    if name.startswith('Check_'):
        meta['slice_px'] = dict(left=width, top=height, right=width, bottom=height)
    return image, meta


def nine_slice(image, margins, size):
    """Corners unscaled, edge thickness unchanged; only tangential span stretches."""
    left, top, right, bottom = (margins[k] for k in ('left', 'top', 'right', 'bottom'))
    dw, dh = size
    sw, sh = image.size
    if dw <= left + right or dh <= top + bottom:
        raise ValueError((image.size, margins, size))
    sx, sy = [0, left, sw - right, sw], [0, top, sh - bottom, sh]
    dx, dy = [0, left, dw - right, dw], [0, top, dh - bottom, dh]
    out = Image.new('RGBA', size)
    for iy in range(3):
        for ix in range(3):
            tile = image.crop((sx[ix], sy[iy], sx[ix + 1], sy[iy + 1]))
            ts = (dx[ix + 1] - dx[ix], dy[iy + 1] - dy[iy])
            if tile.size != ts:
                tile = tile.resize(ts, Image.Resampling.NEAREST)
            out.paste(tile, (dx[ix], dy[iy]))
    return out


def working_sizes(name):
    if name.startswith('Check_'):
        return [(24, 24)]
    if name in ('Panel', 'PanelInset', 'Modal'):
        return [(144, 80), (240, 112), (336, 160)]
    if name.startswith('Btn') or name.startswith('Input'):
        return [(120, 32), (180, 40), (240, 48)]
    if name in ('Toast', 'ToastWarning'):
        return [(144, 32), (240, 40), (336, 48)]
    if name in ('SliderThumb', 'Check_Off', 'Check_On', 'KeyChip'):
        return [(16, 16), (24, 24), (32, 32)]
    if name in ('ProgressTrack', 'ProgressFill', 'SliderTrack'):
        return [(120, 8), (180, 10), (240, 12)]
    return [(64, 24), (96, 32), (144, 40)]


def display(name, scale, target, images, metas):
    if metas[name].get('stretch') == 'none':
        if target != (24, 24):
            raise ValueError('Fixed checkbox must remain 24 su')
        return images[name].copy()
    width, height = target[0] * scale + 2, target[1] * scale + 2
    m = metas[name]
    if m['focus_overlay']:
        base = m['focus_base']
        inset = 4 * scale
        size = width + 2 * inset, height + 2 * inset
        ring = nine_slice(images[name], m['slice_px'], size)
        b = nine_slice(images[base], metas[base]['slice_px'], (width, height))
        under = Image.new('RGBA', size)
        under.paste(b, (inset, inset))
        return Image.alpha_composite(under, ring)
    return nine_slice(images[name], m['slice_px'], (width, height))


def gray(image):
    a = np.array(image.convert('RGB'), dtype=float)
    y = np.rint(a @ np.array([.2126, .7152, .0722])).astype(np.uint8)
    return Image.fromarray(np.repeat(y[:, :, None], 3, axis=2))


class Recorder:
    def __init__(self):
        self.run = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
        self.path = PACKAGE / 'generation-records.json'
        self.data = {
            'image_generation_used': False, 'method': 'deterministic procedural vector rendering',
            'prompt_key_definition': 'Exact procedural instruction; no ImageGen prompts or service calls.',
            'records': [], 'pruned_runs': json.loads((PACKAGE / 'fix1-provenance.json').read_text(encoding='utf-8'))['pruned_runs']}
        for root in (PACKAGE / 'concepts', DERIVED / 'concepts'):
            guarded(root)
            if root.exists():
                shutil.rmtree(root)
        self.generated = []

    def save(self, image, path, key, params):
        guarded(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        image.convert('RGBA').save(path, optimize=True)
        root = DERIVED if path.resolve().is_relative_to(DERIVED) else PACKAGE
        relative = path.relative_to(root)
        snapshot = None
        if root == PACKAGE and relative.parts[0] in ('vector', 'masters'):
            snapshot = PACKAGE / 'concepts' / self.run / relative
            guarded(snapshot)
            snapshot.parent.mkdir(parents=True, exist_ok=True)
            snapshot.write_bytes(path.read_bytes())
        entry = {'run': self.run, 'prompt_key': key,
                 'exact_prompt': json.dumps(params, sort_keys=True, ensure_ascii=False),
                 'method': 'procedural', 'output': path.relative_to(ROOT).as_posix(),
                 'unretouched': (snapshot or path).relative_to(ROOT).as_posix(), 'sha256': sha(path),
                 'archive_copy': snapshot is not None}
        self.data['records'].append(entry)
        self.generated.append(entry)

    def finish(self):
        dump(self.path, self.data)


def build():
    rec = Recorder()
    exports, slice_files, image_sets, meta_sets = {}, {}, {}, {}
    for scale, directory in [(1, 'vector/x1'), (2, 'vector/x2'), (4, 'masters')]:
        images, metas = {}, {}
        for name in NAMES:
            im, m = render(name, scale)
            path = PACKAGE / directory / f'T_Skin_{name}.png'
            rec.save(im, path, f'HB08/skins/v1/{name}/x{scale}',
                     {'mode': 'skins', 'name': name, 'tokens': TOKENS, 'geometry': m})
            key = path.relative_to(PACKAGE).as_posix()
            m['sha256'] = sha(path)
            exports[key] = m
            slice_files[key] = dict(m['slice_px'], stretch=m['stretch'])
            images[name], metas[name] = im, m
        image_sets[scale], meta_sets[scale] = images, metas
    dump(PACKAGE / 'slice-margins.json', {'unit': 'px', 'order': ['left', 'top', 'right', 'bottom'],
                                         'files': slice_files})

    # Supplemental runtime sign: no baked error-colored body or letter text.
    for scale in (1, 2):
        def draw_x(ctx):
            ctx.set_line_width(2 * scale)
            ctx.move_to(4 * scale, 4 * scale); ctx.line_to(12 * scale, 12 * scale)
            ctx.move_to(12 * scale, 4 * scale); ctx.line_to(4 * scale, 12 * scale)
            ctx.stroke()
        sign = merge_layers([(mask(16 * scale, 16 * scale, draw_x), 'state.error', 1.)])
        rec.save(sign, PACKAGE / f'layers/x{scale}/T_Sign_InputError.png',
                 f'HB08/sign/v1/error/x{scale}', {'token': TOKENS['state.error'], 'shape': 'X', 'scale': scale})
        # Divider is baked over the panel body, never left over transparency.
        divider = merge_layers([(np.ones((scale, 16 * scale)), 'card.navy', .92)])
        divider = Image.alpha_composite(divider, merge_layers([(np.ones((scale, 16 * scale)), 'card.cream', .16)]))
        rec.save(divider, PACKAGE / f'layers/x{scale}/T_Line_PanelDivider.png',
                 f'HB08/divider/v1/x{scale}', {'token': TOKENS['card.cream'], 'opacity': .16, 'thickness_su': 1, 'scale': scale})

    sheets = []
    for background in ('navy', 'marmoreal', 'sarpedon'):
        root = PACKAGE if background == 'navy' else DERIVED
        crop = None
        if background != 'navy':
            info = BACKGROUNDS[background]
            crop = Image.open(ROOT / info['source']).convert('RGB').crop(info['crop'])
            rec.save(crop, DERIVED / f'backgrounds/{background}-crop.png',
                     f'HB08/background/v1/{background}', info)
        for scale in (1, 2, 4):
            for page, names in enumerate(GROUPS, 1):
                row_h = (max(max(h for _, h in working_sizes(n)) for n in names) + 32) * scale + 2
                sheet_w = 1120 * scale
                sheet = Image.new('RGB', (sheet_w, row_h * len(names)), TOKENS['card.navy'])
                placements = []
                for row, name in enumerate(names):
                    for col, target in enumerate(working_sizes(name)):
                        # Columns are fixed; largest texture (modal/panel 336 su) fits.
                        cx = (16 + col * 368) * scale
                        top = row * row_h + 16 * scale
                        skin = display(name, scale, target, image_sets[scale], meta_sets[scale])
                        if crop is not None:
                            bg = ImageOps.fit(crop, (352 * scale, row_h - 8 * scale),
                                              method=Image.Resampling.BICUBIC, centering=(.5, .5))
                            sheet.paste(bg, (cx - 4 * scale, row * row_h + 4 * scale))
                        outset = 4 * scale if meta_sets[scale][name]['focus_overlay'] else 0
                        draw_x, draw_y = cx - outset, top - outset
                        sheet.paste(skin, (draw_x, draw_y), skin)
                        placements.append({'name': name, 'row': row + 1, 'column': col + 1,
                                           'target_su': list(target), 'normal_origin_px': [cx, top],
                                           'render_box_px': [draw_x, draw_y, draw_x + skin.width, draw_y + skin.height]})
                for mode, im in [('color', sheet), ('gray', gray(sheet))]:
                    path = root / f'comparison/{background}-x{scale}-p{page:02d}-{mode}.png'
                    rec.save(im, path, f'HB08/sheet/v1/{background}/x{scale}/p{page}/{mode}',
                             {'names': names, 'placements': placements, 'background': background, 'scale': scale,
                              'grayscale': 'Rec.709 encoded-sRGB luma: 0.2126 R + 0.7152 G + 0.0722 B' if mode == 'gray' else None})
                    sheets.append({'path': path.relative_to(ROOT).as_posix(), 'sha256': sha(path),
                                   'background': background, 'scale': scale, 'page': page, 'mode': mode, 'placements': placements})

    # Master contact sheet at native/nearest-neighbor inspection sizes.
    contact = Image.new('RGB', (896, 640), TOKENS['card.navy'])
    for i, name in enumerate(NAMES):
        im = image_sets[4][name].copy()
        if not name.startswith('Check_'):
            im.thumbnail((176, 96), Image.Resampling.NEAREST)
        contact.paste(im, ((i % 5) * 176 + 8, (i // 5) * 104 + 4), im)
    for mode, im in [('color', contact), ('gray', gray(contact))]:
        rec.save(im, PACKAGE / f'comparison/catalog-{mode}.png', f'HB08/catalog/v1/{mode}', {'names': NAMES, 'columns': 5})
    dump(PACKAGE / 'manifest.json', {'task': 'HB-08', 'status': 'предложено', 'tokens': TOKENS,
         'skins': exports, 'names': NAMES, 'working_sizes_su': {n: working_sizes(n) for n in NAMES},
         'sheets': sheets, 'backgrounds': BACKGROUNDS, 'last_run': rec.run})
    dump(PACKAGE / 'runtime-style.json', {
        'status': 'предложено', 'unit': 'su',
        'panel': {'body': 'card.navy', 'opacity': .92, 'modal_opacity': 1.,
                  'edge': 'card.cream', 'edge_opacity': .45, 'divider': 'card.cream', 'divider_opacity': .16},
        'button': {'minimum_width': 120, 'heights': [48, 40, 32], 'text_size': 20,
                   'text_font': 'Roboto Bold Condensed', 'disabled_text': 'text.secondary',
                   'disabled_icon_opacity': .4, 'primary_text': 'card.navy',
                   'primary_disabled_text': 'text.primary', 'primary_disabled_text_hex': '#F2EDE4',
                   'selected_text': 'card.glyph', 'focus_gap': 2, 'focus_thickness': 2},
        'input_error': {'runtime_sign': 'layers/x1/T_Sign_InputError.png', 'sign_su': 16},
        'png_text_content': False,
    })
    rec.finish()
    print(json.dumps({'skins_x1_x2': 58, 'masters': 29,
                      'stretch_sheets': len(sheets), 'run': rec.run}, ensure_ascii=False))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--mode', choices=['skins'], default='skins')
    parser.parse_args()
    build()
