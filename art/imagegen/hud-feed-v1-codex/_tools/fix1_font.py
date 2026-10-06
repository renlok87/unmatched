"""Measured Roboto composite face; fallback runs share the primary baseline.

The accepted snapshot sources stay byte-identical. Install only in this renderer.
"""
import math
from functools import lru_cache
from pathlib import Path
from PIL import ImageDraw, ImageFont
from fontTools.ttLib import TTFont

FONT_DIR = Path('C:/Program Files/Epic Games/UE_5.8/Engine/Content/Slate/Fonts')
FALLBACK = FONT_DIR / 'DroidSansFallback.ttf'
RECORDS = []
CONTEXT = 'initialization'
_text = ImageDraw.ImageDraw.text

@lru_cache(None)
def cmap(path):
    with TTFont(path) as face:
        return frozenset(face.getBestCmap())

class CompositeFont:
    def __init__(self, size, bold=False):
        self.size = size
        self.path = str(FONT_DIR / ('Roboto-BoldCondensed.ttf' if bold else 'Roboto-Regular.ttf'))
        self.primary = ImageFont.truetype(self.path, size)
        self.fallback = ImageFont.truetype(str(FALLBACK), size)
        self.primary_cmap = cmap(self.path)
        self.fallback_cmap = cmap(str(FALLBACK))

    def runs(self, text):
        result = []
        for ch in text:
            face = self.primary if ord(ch) in self.primary_cmap else self.fallback
            if result and result[-1][0] is face:
                result[-1] = (face, result[-1][1] + ch)
            else:
                result.append((face, ch))
        return result

    def getmetrics(self):
        return self.primary.getmetrics()

    def getlength(self, text, *args, **kw):
        return sum(face.getlength(run, *args, **kw) for face, run in self.runs(text))

    def getbbox(self, text, mode='', direction=None, features=None, language=None, stroke_width=0, anchor=None):
        kw=dict(mode=mode,direction=direction,features=features,language=language,stroke_width=stroke_width)
        runs = self.runs(text)
        if not runs or all(face is self.primary for face, _ in runs):
            return self.primary.getbbox(text, anchor=anchor, **kw)
        offset = 0
        boxes = []
        for face, run in runs:
            box = face.getbbox(run, anchor='ls', **kw)
            boxes.append((box[0] + offset, box[1], box[2] + offset, box[3]))
            offset += face.getlength(run)
        box = [min(b[0] for b in boxes), min(b[1] for b in boxes),
               max(b[2] for b in boxes), max(b[3] for b in boxes)]
        if anchor == 'lt':
            box[3] -= box[1]; box[1] = 0
        elif anchor in (None, 'la'):
            ascent = self.primary.getmetrics()[0]
            box[1] += ascent; box[3] += ascent
        elif anchor != 'ls':
            raise ValueError('Unsupported composite anchor: ' + str(anchor))
        return tuple(math.floor(v) if i < 2 else math.ceil(v) for i, v in enumerate(box))

@lru_cache(None)
def font(size, bold=False):
    return CompositeFont(size, bold)

def draw_text(draw, xy, text, fill=None, font=None, anchor=None, **kw):
    if not isinstance(font, CompositeFont):
        return _text(draw, xy, text, fill=fill, font=font, anchor=anchor, **kw)
    fallback = [{'index': i, 'character': ch, 'codepoint': f'U+{ord(ch):04X}',
                 'face': FALLBACK.name} for i, ch in enumerate(text) if ord(ch) not in font.primary_cmap]
    missing = [z for z in fallback if ord(z['character']) not in font.fallback_cmap]
    RECORDS.append({'id': CONTEXT, 'text': text, 'primary_face': Path(font.path).name,
                    'font_px': font.size, 'fallback_characters': fallback,
                    'missing_glyphs': len(missing), 'position_px': list(xy), 'anchor': anchor})
    if not fallback:
        return _text(draw, xy, text, fill=fill, font=font.primary, anchor=anchor, **kw)
    x, y = xy
    if anchor == 'lt':
        baseline = y - font.getbbox(text, anchor='ls')[1]
    elif anchor in (None, 'la'):
        baseline = y + font.primary.getmetrics()[0]
    elif anchor == 'ls':
        baseline = y
    else:
        raise ValueError('Unsupported composite anchor: ' + str(anchor))
    for face, run in font.runs(text):
        _text(draw, (x, baseline), run, fill=fill, font=face, anchor='ls', **kw)
        x += face.getlength(run)

def install(modules):
    ImageDraw.ImageDraw.text = draw_text
    for module in modules:
        factory = getattr(module.font, '__wrapped__', module.font)
        default = factory.__defaults__[0] if factory.__defaults__ else False
        module.font = lambda size, bold=default: font(size, bold)
