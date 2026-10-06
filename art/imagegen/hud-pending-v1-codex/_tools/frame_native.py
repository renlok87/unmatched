"""CP-13 geometry, evaluated directly at native pixel size (no resized frame).

rounded_mask/frame are adapted from the frozen CP-13 build_card_frames.py.
At scale=1 the material masks and alpha are byte-identical to CP-13.
The separately drawn navy underlay is mandatory (CP-07).
"""
import math
import cairo
import numpy as np
from PIL import Image

TOKENS = {'navy': '#061623', 'cream': '#F9EBDB', 'pending': '#0D7A89',
          'warning': '#E8812C', 'glyph': '#FAF8F2', 'keyline': '#111317'}
RGB = {k: tuple(bytes.fromhex(v[1:])) for k, v in TOKENS.items()}
EDGE = {'idle': ('cream', 1, .45), 'hover': ('cream', 1, 1),
        'selected': ('pending', 3, 1), 'warning': ('warning', 2, 1)}


def rounded_mask(w, h, box, radius, scale):
    pw, ph = round(w * scale), round(h * scale)
    surf = cairo.ImageSurface(cairo.FORMAT_A8, pw, ph)
    ctx = cairo.Context(surf)
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
    return np.frombuffer(surf.get_data(), dtype=np.uint8).reshape(ph, surf.get_stride())[:, :pw].copy()


def frame(spec, state, scale=1):
    w, h, band, radius = spec
    token, edge, opacity = EDGE[state]
    outer = rounded_mask(w, h, (0, 0, w, h), radius, scale)
    inside_key = rounded_mask(w, h, (1, 1, w - 2, h - 2), radius - 1, scale)
    inside_edge = rounded_mask(w, h, (1 + edge, 1 + edge,
                               w - 2 * (1 + edge), h - 2 * (1 + edge)),
                               radius - 1 - edge, scale)
    arr = np.zeros((*outer.shape, 4), dtype=np.uint8)
    arr[:, :, :3] = RGB['keyline']
    arr[:, :, 3] = outer
    key = inside_key >= 128
    arr[key, :3] = RGB[token]
    arr[key, 3] = round(255 * opacity)
    navy = inside_edge >= 128
    arr[navy, :3] = RGB['navy']
    arr[navy, 3] = 255
    b = round(band * scale)
    arr[b:round((h-band)*scale), b:round((w-band)*scale)] = 0
    return Image.fromarray(arr)


def underlay(spec, scale):
    w, h, _, radius = spec
    mask = rounded_mask(w, h, (0, 0, w, h), radius, scale)
    out = Image.new('RGBA', (round(w*scale), round(h*scale)), (*RGB['navy'], 255))
    out.putalpha(Image.fromarray(mask))
    return out
