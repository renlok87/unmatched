#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""SC-01 reusable procedural layout library. No writes, engine or network calls.

Copy this file unchanged for other SC packages. Pass source paths explicitly.
All rectangles use slate units; DPI and application scale are independent.
The icon generator snapshot is archival only; its main() is never invoked.
"""
from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
import json

import numpy as np
from PIL import Image, ImageDraw, ImageFont

STATES = ('normal', 'hover', 'pressed', 'disabled', 'focus', 'selected')


@dataclass(frozen=True)
class Viewport:
    width: int
    height: int
    dpi: float
    ui: float

    @property
    def factor(self):
        return self.dpi * self.ui

    @property
    def canvas(self):
        return (self.width / self.factor, self.height / self.factor)

    @property
    def layout_class(self):
        return 'L' if self.canvas[0] >= 1500 else 'S'

    @property
    def margin(self):
        return 24 if self.layout_class == 'L' else 16

    @classmethod
    def preset(cls, resolution='1080p', scale=100):
        if resolution not in ('1080p', '720p') or scale not in (100, 150):
            raise ValueError('Supported viewport presets: 1080p/720p, 100/150')
        return cls(1920 if resolution == '1080p' else 1280,
                   1080 if resolution == '1080p' else 720,
                   1.0 if resolution == '1080p' else 0.75, scale / 100)


class Theme:
    def __init__(self, tokens_path, bold_font, regular_font, spinner_path, skins_folder):
        self.tokens = json.loads(Path(tokens_path).read_text(encoding='utf-8-sig'))
        self.bold_font = str(bold_font)
        self.regular_font = str(regular_font)
        self.spinner = Image.open(spinner_path).convert('RGBA')
        self.skins_folder = Path(skins_folder)
        self.margins = json.loads((self.skins_folder / 'slice-margins.json').read_text(encoding='utf-8'))['files']
        self.runtime = json.loads((self.skins_folder / 'runtime-style.json').read_text(encoding='utf-8'))

    @lru_cache(maxsize=128)
    def skin(self, name, scale):
        return Image.open(self.skins_folder / f'vector/x{scale}/T_Skin_{name}.png').convert('RGBA')

    def color(self, name):
        value = self.tokens['colors'][name]['hex'].lstrip('#')
        return tuple(int(value[i:i+2], 16) for i in (0, 2, 4))

    def alpha(self, name):
        return self.tokens['colors'][name].get('alpha', 1.0)

    def size(self, name):
        return self.tokens['typography'][name]['su']

    def radius(self, name):
        return self.tokens['radii'][name]['px']

    @lru_cache(maxsize=128)
    def font(self, role, factor):
        item = self.tokens['typography'][role]
        path = self.bold_font if item['face'] == 'BoldCondensed' else self.regular_font
        return ImageFont.truetype(path, max(1, round(item['su'] * factor)))


def mix(fg, bg, alpha):
    return tuple(round(a * alpha + b * (1 - alpha)) for a, b in zip(fg, bg))


def luma709(image):
    """Encoded RGB Rec.709 luma, not Pillow's default Rec.601 conversion."""
    rgb = np.asarray(image.convert('RGB'), dtype=np.float64)
    gray = np.rint(rgb @ np.array([0.2126, 0.7152, 0.0722])).astype(np.uint8)
    return Image.fromarray(gray).convert('RGB')


def wcag_luminance(rgb):
    value = np.asarray(rgb, dtype=np.float64) / 255
    linear = np.where(value <= 0.04045, value / 12.92, ((value + 0.055) / 1.055) ** 2.4)
    return linear @ np.array([0.2126, 0.7152, 0.0722])


def contrast(a, b):
    x, y = wcag_luminance(a), wcag_luminance(b)
    return float((max(x, y) + 0.05) / (min(x, y) + 0.05))


class Canvas:
    """Fourfold supersampling preserves fractional 10.5 px type and hairlines."""
    def __init__(self, viewport, theme, background=None, supersample=4):
        self.viewport, self.theme, self.ss = viewport, theme, supersample
        self.factor = viewport.factor * supersample
        size = (viewport.width * supersample, viewport.height * supersample)
        if background is None:
            self.image = Image.new('RGBA', size, theme.color('panel.bg') + (255,))
        else:
            self.image = background.convert('RGBA').resize(size, Image.Resampling.LANCZOS)
        self.geometry, self.text_runs = [], []

    def px(self, value):
        return round(value * self.factor)

    def box(self, rect):
        x, y, w, h = rect
        return (self.px(x), self.px(y), self.px(x + w)-1, self.px(y + h)-1)

    def rounded(self, rect, fill, radius=4, edge=None, edge_su=1):
        ImageDraw.Draw(self.image).rounded_rectangle(self.box(rect), self.px(radius),
            fill=fill, outline=edge, width=max(1, self.px(edge_su)))

    def line(self, points, color, width=1):
        ImageDraw.Draw(self.image).line([(self.px(x), self.px(y)) for x, y in points],
                                     fill=color, width=max(1, self.px(width)))

    def text(self, xy, value, role='type.body', color='text.primary', anchor='lt', source=None):
        font = self.theme.font(role, self.factor)
        ink = self.theme.color(color) if isinstance(color, str) else color
        xy_px = tuple(self.px(v) for v in xy)
        draw = ImageDraw.Draw(self.image)
        bbox = draw.textbbox(xy_px, value, font=font, anchor=anchor)
        draw.text(xy_px, value, font=font, fill=ink, anchor=anchor)
        self.text_runs.append({'text': value, 'type': role,
            'size_su': self.theme.size(role), 'size_px': self.theme.size(role) * self.viewport.factor,
            'font_render_px': font.size / self.ss, 'ink': ink,
            'bbox_px': [v / self.ss for v in bbox], 'source': source})
        return bbox

    def veil(self, shown=True):
        if shown:
            overlay = Image.new('RGBA', self.image.size,
                self.theme.color('panel.veil') + (round(255 * self.theme.alpha('panel.veil')),))
            self.image = Image.alpha_composite(self.image, overlay)

    def skin(self, rect, name):
        """HB-08 content rect in su. Native one-pixel transparent guard is outside it.

        Select x1/x2 by final pixels/su (not supersampling), Lanczos-scale the
        source, then stretch only the centre and tangential edge spans. Focus
        skins are overlays: compose the normal base and the supplied 4 su ring.
        Checkboxes are fixed 24 su, uniformly scaled, never nine-slice stretched.
        """
        x, y, w, h = rect
        scale = 1 if self.viewport.factor <= 1 else 2
        if name.endswith('_Focus'):
            self.skin(rect, name.replace('_Focus', '_Normal'))
            x, y, w, h = x-4, y-4, w+8, h+8
        source = self.theme.skin(name, scale)
        ratio = self.factor / scale
        sw, sh = (round(v * ratio) for v in source.size)
        source = source.resize((sw, sh), Image.Resampling.LANCZOS)
        pad = max(1, round(ratio))
        target = (self.px(w)+2*pad, self.px(h)+2*pad)
        meta = self.theme.margins[f'vector/x{scale}/T_Skin_{name}.png']
        if meta['stretch'] == 'none':
            if (w, h) != (24, 24):
                raise ValueError('HB-08 checkbox is fixed at 24x24 su')
            out = source
        else:
            left, top, right, bottom = (round(meta[k]*ratio) for k in ('left','top','right','bottom'))
            dw, dh = target
            if dw < left+right or dh < top+bottom:
                raise ValueError('Skin target smaller than protected corners')
            sx, sy = (0,left,sw-right,sw), (0,top,sh-bottom,sh)
            dx, dy = (0,left,dw-right,dw), (0,top,dh-bottom,dh)
            out = Image.new('RGBA', target)
            for row in range(3):
                for col in range(3):
                    tile = source.crop((sx[col],sy[row],sx[col+1],sy[row+1]))
                    size = (dx[col+1]-dx[col],dy[row+1]-dy[row])
                    if 0 in size:
                        continue
                    if tile.size != size:
                        tile = tile.resize(size, Image.Resampling.LANCZOS)
                    out.paste(tile, (dx[col],dy[row]))
        self.image.alpha_composite(out, (self.px(x)-pad,self.px(y)-pad))

    def panel(self, rect, kind='modal', record=True):
        alpha = 1.0 if kind in ('modal', 'screen', 'documentation') else self.theme.alpha('panel.bg')
        self.skin(rect, 'Modal' if alpha == 1 else 'Panel')
        if record:
            self.geometry.append({'kind': kind, 'rect_su': list(rect), 'alpha': alpha})

    def button(self, rect, label, state='normal', primary=False, why=None, source=None):
        if state not in STATES:
            raise ValueError(state)
        if state == 'disabled' and (not why or not why[0].startswith('why.')):
            raise ValueError('A disabled button requires a why.* code and visible reason')
        if primary and state == 'selected':
            raise ValueError('02 section 4.3: primary selected is not a production state')
        t = self.theme
        key = ('primary_disabled_text' if state == 'disabled' else 'primary_text') if primary else (
            'disabled_text' if state == 'disabled' else 'selected_text' if state == 'selected' else None)
        ink = t.color(t.runtime['button'][key] if key else 'text.primary')
        name = ('BtnPrimary_' if primary else 'Btn_') + state.capitalize()
        x, y, w, h = rect
        self.skin(rect, name)
        body = tuple(self.image.getpixel((self.px(x+12), self.px(y+h/2)))[:3])
        edge = tuple(self.image.getpixel((self.px(x+w/2), self.px(y+.5)))[:3])
        self.text((x+w/2,
                   y+h/2+(1 if state == 'pressed' else 0)), label.upper(),
                  'type.button', ink, 'mm', source)
        if why:
            self.text((x, y+h+6), why[1], 'type.caption', 'text.secondary', source=why[0])
        self.geometry.append({'kind': 'button', 'rect_su': list(rect), 'state': state,
            'primary': primary, 'fill': body, 'edge': edge, 'ink': ink,
            'why': why[0] if why else None, 'skin': name, 'exempt_inactive': state == 'disabled'})

    def chip(self, rect, label, selected=False, source=None):
        ink = self.theme.color('card.glyph' if selected else 'text.primary')
        self.skin(rect, 'Btn_Selected' if selected else 'Chip')
        x, y, w, h = rect
        self.text((x+w/2, y+h/2), label, 'type.caption', ink, 'mm', source)

    def key_chip(self, rect, label, source=None):
        self.skin(rect, 'KeyChip')
        x,y,w,h = rect
        self.text((x+w/2,y+h/2),label,'type.caption',anchor='mm',source=source)

    def checkbox(self, xy, checked=False):
        self.skin((*xy,24,24), 'Check_On' if checked else 'Check_Off')

    def text_field(self, rect, value='', state='normal', source=None):
        if state not in ('normal','focus','error'):
            raise ValueError(state)
        self.skin(rect, 'Input_' + state.capitalize())
        x, y, w, h = rect
        self.text((x+16, y+h/2), value, 'type.body', 'text.primary', 'lm', source)

    def progress(self, xy, phase=0, shown=True):
        if not shown:
            return
        x, y = xy
        self.skin((x,y,480,8), 'ProgressTrack')
        # Indeterminate segment; no invented percentage of gameplay progress.
        start = x+(phase % 8)*50
        self.skin((start,y,120,8), 'ProgressFill')

    def spinner(self, xy, step=0, size=48, shown=True):
        if not shown:
            return
        if size < 24:
            raise ValueError('Icons must be at least 24 su')
        icon = self.theme.spinner.rotate(-45*(step % 8), resample=Image.Resampling.NEAREST)
        icon = icon.resize((self.px(size), self.px(size)), Image.Resampling.NEAREST)
        self.image.alpha_composite(icon, tuple(self.px(v) for v in xy))

    def grid(self, step=48):
        w, h = self.viewport.canvas
        color = mix(self.theme.color('panel.divider'), self.theme.color('panel.bg'), .16)
        for x in np.arange(0,w,step):
            self.line([(x,0),(x,h)], color)
        for y in np.arange(0,h,step):
            self.line([(0,y),(w,y)], color)

    def finish(self):
        return self.image.convert('RGB').resize((self.viewport.width, self.viewport.height), Image.Resampling.LANCZOS)


def modal_rect(viewport):
    w, h = viewport.canvas
    return ((w-640)/2, (h-360)/2, 640, 360)


def draw_base_modal(canvas, strings, open=True):
    """Closed = background only; open = veil + 640x360 modal + one primary."""
    if not open:
        return
    canvas.veil()
    rect = modal_rect(canvas.viewport)
    canvas.panel(rect)
    x, y, w, h = rect
    canvas.text((x+16,y+16), strings['title'], 'type.title', source='screens.pause.leave')
    canvas.text((x+16,y+64), strings['body'], source='screens.pause.leave.confirm')
    canvas.button((x+w-368,y+h-64,168,48), strings['cancel'], source='common.confirm.cancel')
    canvas.button((x+w-184,y+h-64,168,48), strings['confirm'], primary=True, source='common.confirm.yes')


def draw_screen(canvas, shown=True):
    """Route foundation: hidden leaves the live scene, shown adds the veil."""
    canvas.veil(shown)
