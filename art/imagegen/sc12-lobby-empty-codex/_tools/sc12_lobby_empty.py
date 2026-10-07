#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""SC-12: captured empty list and the accepted bulb glyph, without its plate."""
import sys
sys.dont_write_bytecode = True
import sc08_lobby_list as base
from PIL import Image

original_icon = base.LobbyCanvas.icon


def native_hint(self, name, xy, size_su):
    if name != 'state-hint':
        return original_icon(self, name, xy, size_su)
    assert size_su == 32
    px = round(size_su * self.viewport.factor)
    candidates = sorted((int(p.stem.rsplit('-', 1)[1]), p)
                        for p in (base.ICONS / 'layers').glob('state-hint_glyph-*.png'))
    native_px, source = next((size, p) for size, p in candidates if size >= px)
    with Image.open(source) as layer:
        assert layer.size == (2 * native_px, native_px)
        crop = (0, 0, native_px, native_px)
        glyph = layer.convert('RGBA').crop(crop)
    method = 'exact accepted glyph layer; left square crop'
    fallback = None
    if native_px != px:
        glyph = glyph.resize((px, px), Image.Resampling.LANCZOS)
        method = 'next larger accepted glyph layer; left square crop; LANCZOS'
        fallback = {'from_px': native_px, 'to_px': px, 'filter': 'LANCZOS'}
    position = tuple(round(value * self.viewport.factor) for value in xy)
    self.icon_layers.append((glyph, position))
    self.icons.append({'name': name, 'size_su': size_su, 'size_px': px,
                       'native_size_px': [2 * native_px, native_px],
                       'rendered_size_px': list(glyph.size), 'position_px': position,
                       'source': base.label_path(source), 'source_sha256': base.sha(source),
                       'crop_px': list(crop), 'method': method, 'fallback': fallback})


base.LobbyCanvas.icon = native_hint


def empty_states():
    answer = base.capture('available-games-empty.json')
    assert answer['request']['variables']['mode'] == 'ONE_V_ONE'
    assert answer['answer']['data']['availableGames'] == []
    return {'empty': {'list': 'empty'}}


if __name__ == '__main__':
    sys.stdout.reconfigure(encoding='utf-8')
    base.build('SC-12', empty_states())
    report = base.load(base.PACKAGE / 'verification.json')
    report['acceptance']['captured ONE_V_ONE answer is empty'] = {
        'passed': True, 'measured': [], 'expected': [],
        'note': 'available-games-empty.json answer.data.availableGames; VS_AI is excluded'}
    layers = {icon['source']: icon['source_sha256']
              for states in report['layout_measurements'].values()
              for frame in states.values() for icon in frame['icons']
              if icon['name'] == 'state-hint'}
    report['native_hint'] = {'aspect': '1:1', 'size_su': [32, 32],
                             'plate': False, 'source_unchanged': True,
                             'input_layers': layers}
    base.dump(base.PACKAGE / 'verification.json', report)
    base.refresh_manifest()
