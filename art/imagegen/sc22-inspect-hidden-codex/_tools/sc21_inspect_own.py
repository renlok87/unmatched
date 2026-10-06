#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""CX-23 procedural INSPECT foundation. Offline, guarded writes, no engine.

SC-22/23 copy this FINAL module byte-for-byte and supply a separate renderer.
Run with python -B to avoid changing archival copies with bytecode caches.
"""
from __future__ import annotations

import sys
sys.dont_write_bytecode = True
from pathlib import Path
import csv
import hashlib
import json
import math
import itertools
import numpy as np
from PIL import Image, ImageDraw
from screen_mockup_base import Canvas, Theme, Viewport, contrast, luma709, mix

ROOT = Path(__file__).resolve().parents[4]
SKINS = ROOT / 'art/imagegen/hud-skins-v1-codex'
FONTS = Path('C:/Program Files/Epic Games/UE_5.8/Engine/Content/Slate/Fonts')
TOKENS = ROOT / 'docs/unreal/contracts/hud/hud-style-tokens.json'
BACKGROUND = ROOT / 'docs/game-design/evidence/ENV-MAPS/p10-sarpedon-rework-2026-10-03/sarpedon-packaged/bench-K1-1920x1080.png'
ICONS = ROOT / 'art/imagegen/hud-icons-v3'
MATRIX = ROOT / 'docs/game-design/05-content-matrix.csv'
I18N_STRINGS = ROOT / 'docs/unreal/contracts/hud/st-hud.csv'
CATALOG = ROOT / 'docs/game-design/evidence/S01/catalog-medusa.json'
CARDART = ROOT / 'art/imagegen/mvp-v1/reused-cardart.json'
VIEWER = 'cmq7d4b3z000ewi205ca0fphl'


def load(path):
    return json.loads(Path(path).read_text(encoding='utf-8-sig'))


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def relative(path):
    p = Path(path).resolve()
    return p.relative_to(ROOT).as_posix() if p.is_relative_to(ROOT) else p.as_posix()


def config(identifier, slug):
    return {'id': identifier, 'slug': slug,
            'package': ROOT / f'art/imagegen/{slug}-codex',
            'derived': ROOT / f'scraped-data/derived/{slug}-codex'}


def safe_path(cfg, path):
    p = Path(path).resolve()
    if not any(p.is_relative_to(cfg[k].resolve()) for k in ('package', 'derived')):
        raise ValueError(f'Write outside task roots: {p}')
    p.parent.mkdir(parents=True, exist_ok=True)
    return p


def write_json(cfg, path, value):
    safe_path(cfg, path).write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


def write_text(cfg, path, value):
    safe_path(cfg, path).write_text(value, encoding='utf-8')


def save_pair(cfg, im, path):
    p = safe_path(cfg, path)
    im.convert('RGBA').save(p, optimize=True)
    gray = p.with_name(p.stem + '-gray.png')
    luma709(im).convert('RGBA').save(safe_path(cfg, gray), optimize=True)
    return [p, gray]


def theme():
    return Theme(TOKENS, FONTS / 'Roboto-BoldCondensed.ttf', FONTS / 'Roboto-Regular.ttf',
                 ICONS / 'sizes/loader-spinner-32.png', SKINS)


def strings():
    with I18N_STRINGS.open(encoding='utf-8-sig', newline='') as f:
        return {r['Key']: r['ru'] for r in csv.DictReader(f)}


def hero_name():
    with MATRIX.open(encoding='utf-8-sig', newline='') as f:
        row = next(r for r in csv.DictReader(f) if r['contentKey'] == 'medusa')
    return row['nazvanie'].split('(', 1)[1].split(')', 1)[0]


def card_data(cfg, title):
    capture = load(cfg['derived'] / 'inputs/deck-lists.json')
    deck = next(d for d in capture['gameDeckLists'] if d['playerId'] == VIEWER)
    card = next(c for c in deck['cards'] if c['nameEn'] == title)
    localized = next(c for c in load(cfg['derived'] / 'inputs/medusa-cards-i18n.json')['cards'] if c['titleEn'] == title)
    cat = next(c for c in load(CATALOG)['hero']['cards'] if c['id'] == card['cardId'])
    assert cat['type'] == card['cardType']
    assert cat['quantity'] == card['count'] == localized['copies']
    assert cat['boost'] == card['boostValue'] == localized['boostValue']
    value = card['attackValue'] if card['cardType'] in ('ATTACK', 'VERSATILE') else card['defenseValue']
    if value is not None:
        assert value == cat['value'] == localized['value']
    art = next(c for c in load(CARDART)['cards'] if c['stableContentKey'].startswith('medusa:') and c['title'] == title)
    for lang in ('ru', 'en'):
        assert sha(ROOT / art[lang]['path']) == art[lang]['sha256']
    counts = None
    state_path = cfg['derived'] / 'inputs/game-state.json'
    if state_path.exists():
        state = json.loads(load(state_path)['gameState']['state'])
        hand = sum(c['cardId'] == card['cardId'] for c in state['handZones'][VIEWER]['cards'])
        discarded = sum(c['cardId'] == card['cardId'] for c in state['discardPiles'][VIEWER])
        counts = {'n': card['count'] - hand - discarded, 'h': hand, 'd': discarded}
        assert counts['n'] >= 0
    return {'capture': card, 'localized': localized, 'art': art, 'value': value, 'counts': counts}


def rects(vp):
    w, h = (852, 688) if vp.layout_class == 'L' else (784, 600)
    x, y = (vp.canvas[0] - w) / 2, (vp.canvas[1] - h) / 2
    scan = (x+24, y+24, 460, 640) if vp.layout_class == 'L' else (x+24, y+24, 400, 555)
    text = (x+508, y+24, 320, 640) if vp.layout_class == 'L' else (x+448, y+24, 312, 552)
    return {'modal': (x, y, w, h), 'slot': scan, 'frame': scan, 'text': text}


class InspectorCanvas(Canvas):
    def __init__(self, viewport, skin_theme, background=None):
        super().__init__(viewport, skin_theme, background)
        self.assets, self.icons, self.notes = [], [], []
        self.wrapped = []

    def paragraph(self, xy, text, width, role='type.body', source=None, color='text.primary'):
        font = self.theme.font(role, self.factor)
        lines, current = [], ''
        for word in text.split():
            trial = (current + ' ' + word).strip()
            if current and font.getlength(trial) > self.px(width):
                lines.append(current)
                current = word
            else:
                current = trial
        if current:
            lines.append(current)
        leading = self.theme.size(role) * 1.45
        x, y = xy
        for i, line in enumerate(lines):
            self.text((x, y+i*leading), line, role, color, source=source)
        self.wrapped.append({'value': text, 'source': source, 'lines': lines, 'width_su': width})
        return y + len(lines)*leading

    def icon(self, xy, name, size=32):
        assert size >= 24
        src = ICONS / f'sizes/{name}-{size}.png'
        im = Image.open(src).convert('RGBA')
        self.image.alpha_composite(im.resize((self.px(size), self.px(size)), Image.Resampling.NEAREST),
                                   (self.px(xy[0]), self.px(xy[1])))
        self.icons.append({'path': relative(src), 'size_su': size, 'rect_su': [*xy, size, size]})

    def card_frame(self, rect):
        x, y, w, h = rect
        # Card silhouette is the inspector's extension; panel/modal/buttons use HB-08.
        self.rounded((x-1, y-1, w+2, h+2), self.theme.color('mark.keyline'), radius=9)
        self.rounded(rect, self.theme.color('panel.bg'), radius=8,
                     edge=mix(self.theme.color('panel.edge'), self.theme.color('panel.bg'), .45))
        self.geometry.append({'kind': 'card_frame', 'rect_su': list(rect), 'layer': 'modal'})

    def scan_layout(self, path, rect, max_scale=1.6):
        x, y, w, h = rect
        with Image.open(path) as source:
            sw, sh = source.size
        # Limit refers to delivered physical pixels, independent of DPI/UI scale.
        fit = min((w-8)*self.viewport.factor/sw, (h-8)*self.viewport.factor/sh)
        scale = min(fit, max_scale)
        out_w, out_h = math.floor(sw*scale), math.floor(sh*scale)
        tw, th = out_w/self.viewport.factor, out_h/self.viewport.factor
        dest = (x+(w-tw)/2, y+(h-th)/2, tw, th)
        frame = (dest[0]-4, dest[1]-4, tw+8, th+8) if fit > max_scale else rect
        return {'slot': rect, 'frame': frame, 'scan': dest,
                'scan_scale': max(out_w/sw, out_h/sh),
                'source_size_px': [sw, sh], 'size_px': [out_w, out_h],
                'capped': fit > max_scale}

    def slot_outline(self, r):
        x, y, w, h = r['slot']
        color = mix(self.theme.color('panel.divider'), self.theme.color('panel.bg'),
                    self.theme.alpha('panel.divider'))
        self.line([(x,y),(x+w,y),(x+w,y+h),(x,y+h),(x,y)], color)
        self.paragraph((x+16,y+16), f'Слот {w:g} × {h:g} su', w-32,
                       source='04 §1.7: layout slot dimensions')
        fw, fh = r['frame'][2:]
        self.paragraph((x+16,y+44), f'Рамка {fw:g} × {fh:g} su', w-32,
                       color='text.secondary', source='SC-21.fix1: ВР-VS3-SC21-07')
        self.geometry.append({'kind':'scan_slot', 'rect_su':list(r['slot']), 'layer':'documentation'})

    def scan(self, path, rect, overlay=False, max_scale=1.6):
        layout = self.scan_layout(path, rect, max_scale)
        dest = layout['scan']; tw, th = dest[2:]
        source = Image.open(path).convert('RGBA')
        if not overlay:
            im = source.resize((self.px(tw), self.px(th)), Image.Resampling.LANCZOS)
            self.image.alpha_composite(im, (self.px(dest[0]), self.px(dest[1])))
        self.assets.append({'source': relative(path), 'source_size_px': list(source.size),
                            'rect_su': list(dest), 'size_px': layout['size_px'],
                            'scale': layout['scan_scale'],
                            'whole_scan': True, 'drawn_over': False, 'omitted_in_overlay': overlay})


def shell(c):
    c.veil()
    r = rects(c.viewport)
    c.panel(r['modal'], kind='modal')
    return r


def close_controls(c, r, back=False):
    x, y, w, h = r['text']
    c.icon((x+w-32, y), 'ui-close', 32)
    c.notes.append({'close': {'accessible_name': strings()['hud.inspect.close'],
        'tooltip': strings()['hud.inspect.close'], 'source': 'st-hud.csv:hud.inspect.close',
        'drawn_label': False, 'icon': 'ui-close-32',
        'dismiss': ['×', 'Esc', 'right click', 'outside click']}})
    if back:
        c.button((x, y+h-100, 120, 40), 'Назад', source='screens.csv:SC-23:do:hud.inspect.back')


def draw_card(c, cfg, state, title='Gaze of Stone', overlay=False, back=False):
    data, s = card_data(cfg, title), strings()
    r = shell(c)
    scan_path = ROOT / data['art']['ru']['path']
    scan_layout = c.scan_layout(scan_path, r['slot'])
    r.update({k: scan_layout[k] for k in ('frame', 'scan', 'scan_scale')})
    c.card_frame(r['frame'])
    if overlay:
        c.slot_outline(r)
    x, y, w, h = r['text']
    name = data['localized']['titleRu']
    end = c.paragraph((x, y+48), name, w, 'type.title',
                      source='inputs/medusa-cards-i18n.json:cards.titleRu')
    typ = data['capture']['cardType'].lower()
    cy = end+16
    c.icon((x, cy), f'action-{typ}', 32)
    c.text((x+44, cy+8), s[f'hud.inspect.type.{typ}'], source=f'st-hud.csv:hud.inspect.type.{typ}')
    cy += 60
    c.text((x, cy), s['hud.inspect.value'].format(n=data['value']), 'type.heading',
           source='st-hud.csv:hud.inspect.value + inputs/deck-lists.json:attackValue/defenseValue')
    c.text((x, cy+36), s['hud.inspect.boost'].format(n=data['capture']['boostValue']), 'type.heading',
           source='st-hud.csv:hud.inspect.boost + inputs/deck-lists.json:boostValue')
    cy += 92
    if back:
        # ROOM knows composition only. Use the same HB-08 chip as the grid.
        chip = (x, cy, 40, 32)
        c.chip(chip, f"×{data['capture']['count']}",
               source='screens.csv:SC-23:do:hud.inspect.copies.short + inputs/deck-lists.json:count')
        c.notes.append({'room_copies_chip': {'rect_su': chip, 'count': data['capture']['count'],
                                             'skin': 'Chip', 'hand_discard_available': False}})
        cy += 56
    effect = data['localized']['effects']['effectAfter']['ru']
    cy = c.paragraph((x, cy), 'После боя: '+effect, w,
                      source='inputs/medusa-cards-i18n.json:effects.effectAfter.ru + CX-23:ВР-VS3-SC21-02')
    if data['counts']:
        cy = c.paragraph((x, cy+24), s['hud.inspect.copies'].format(**data['counts']), w, 'type.caption',
                          source='st-hud.csv:hud.inspect.copies + deck-lists.count - handZones/discardPiles',
                          color='text.secondary')
    # The row ends at the modal's 24 su bottom padding line.
    mx, my, mw, mh = r['modal']
    toggle_y = my+mh-24-28
    reserved_top = y+h-100 if back else toggle_y
    assert cy+16 <= reserved_top, (state, c.viewport, cy, reserved_top)
    c.key_chip((x, toggle_y, 40, 28), 'Tab', source='CX-23:ВР-VS3-SC21-04')
    c.text((x+52, toggle_y+7), s['hud.inspect.lang.toggle'], 'type.caption',
           source='st-hud.csv:hud.inspect.lang.toggle')
    r['language_row_su'] = (x, toggle_y, w, 28)
    if state == 'loading':
        fx, fy, fw, fh = r['frame']
        c.icon((fx+fw/2-16, fy+fh/2-16), 'loader-spinner', 32)
    else:
        c.scan(scan_path, r['slot'], overlay=overlay)
    close_controls(c, r, back)
    return r


def own_renderer(c, cfg, state, overlay=False):
    return draw_card(c, cfg, state, overlay=overlay)


def masks(vp):
    # Conservative envelopes from SC-01 accepted K1 annotation, not segmentation.
    figures = [(390,490,482,557), (505,530,599,603), (384,599,478,665),
               (647,476,710,546), (1138,551,1206,616), (1088,641,1155,719)]
    spaces = [(290,210,1620,925)]
    result = {}
    for name, boxes in [('figures', figures), ('spaces', spaces)]:
        m = Image.new('1', (vp.width, vp.height))
        d = ImageDraw.Draw(m)
        for a,b,e,f in boxes:
            d.rectangle((round(a*vp.width/1920), round(b*vp.height/1080),
                         round(e*vp.width/1920)-1, round(f*vp.height/1080)-1), fill=1)
        result[name] = np.asarray(m, dtype=bool)
    return result


def overlap(c):
    mm = masks(c.viewport)
    result = {'method': 'SC-01 conservative K1 figure bounding boxes + whole field envelope; output pixels; not engine segmentation'}
    for kind in ('persistent', 'modal'):
        im = Image.new('1', (c.viewport.width, c.viewport.height))
        d = ImageDraw.Draw(im)
        items = [g for g in c.geometry if g['kind'] == kind]
        for g in items:
            x,y,w,h = g['rect_su']; f=c.viewport.factor
            d.rectangle((round(x*f),round(y*f),round((x+w)*f)-1,round((y+h)*f)-1), fill=1)
        p = np.asarray(im, dtype=bool)
        result[kind] = {'panel_count':len(items), 'panel_area_px2':int(p.sum()),
                        'overlap_figures_px2':int((p & mm['figures']).sum()),
                        'overlap_spaces_px2':int((p & mm['spaces']).sum()), 'exempt':kind=='modal'}
    return result


def canvas_audit(c, r):
    bg = c.theme.color('panel.bg')
    issues = []
    for t in c.text_runs:
        a,b,e,f = t['bbox_px']
        if a < 0 or b < 0 or e > c.viewport.width or f > c.viewport.height:
            issues.append({'text':t['text'],'problem':'outside viewport'})
        if not t['source']:
            issues.append({'text':t['text'],'problem':'missing provenance'})
    pairs = []
    for a,b in itertools.combinations(c.text_runs,2):
        x1,y1,x2,y2=a['bbox_px']; u1,v1,u2,v2=b['bbox_px']
        area=max(0,min(x2,u2)-max(x1,u1))*max(0,min(y2,v2)-max(y1,v1))
        if area > 0:
            pairs.append({'a':a['text'],'b':b['text'],'px2':area})
    # Runtime text background is the modal or a button skin, never the scan.
    buttons=[g for g in c.geometry if g['kind']=='button']
    text_contrasts=[]
    for t in c.text_runs:
        background=bg
        for g in buttons:
            x,y,w,h=g['rect_su'];f=c.viewport.factor
            a,b,e,j=t['bbox_px']
            if a>=x*f and b>=y*f and e<=(x+w)*f and j<=(y+h)*f:
                background=g['fill']
        text_contrasts.append({'text':t['text'],'source':t['source'],
                               'ink':t['ink'],'background':background,
                               'ratio':contrast(t['ink'],background)})
    edge= mix(c.theme.color('panel.edge'), bg, .45)
    icon_contrasts=[]
    for i in c.icons:
        pix=np.asarray(Image.open(ROOT/i['path']).convert('RGBA'))
        colors=np.unique(pix[pix[:,:,3]==255,:3],axis=0)
        # Main opaque flat areas; hairline/AA and silhouette keyline are secondary.
        if len(colors):
            counts=[int(((pix[:,:,:3]==rgb).all(axis=2)&(pix[:,:,3]==255)).sum()) for rgb in colors]
            body=colors[int(np.argmax(counts))]
            glyph=c.theme.color('card.glyph')
            icon_contrasts.append({'path':i['path'],'dominant_body':body.tolist(),
                'body_to_panel':contrast(body,bg),'glyph_to_body':contrast(glyph,body),
                'cream_edge_to_panel':contrast(c.theme.color('panel.edge'),bg)})
    return {'viewport':{'size_px':[c.viewport.width,c.viewport.height],'dpi':c.viewport.dpi,
            'ui':c.viewport.ui,'factor':c.viewport.factor,'class':c.viewport.layout_class},
            'rects_su':r,'geometry':c.geometry,'assets':c.assets,'icons':c.icons,
            'text_runs':c.text_runs,'wrapped':c.wrapped,'notes':c.notes,
            'text_contrast':text_contrasts,'minimum_text_contrast':min(t['ratio'] for t in text_contrasts),
            'edge_contrast':{'panel_and_card_edge':contrast(edge,bg),
                'buttons':[{'skin':b['skin'],'edge_to_body':contrast(b['edge'],b['fill']),
                            'edge_to_panel':contrast(b['edge'],bg)} for b in buttons]},
            'icon_contrast':icon_contrasts,'smallest_text_px':min(t['size_px'] for t in c.text_runs),
            'overlap':overlap(c),'text_pair_overlaps':pairs,'issues':issues,
            'primary_buttons':sum(b['primary'] for b in buttons),
            'primary_count':sum(b['primary'] for b in buttons)}


def input_audit(cfg):
    before=load(cfg['package']/'source-hashes-before.json')
    changed=[p for p,h in before['inputs'].items() if not (ROOT/p).exists() or sha(ROOT/p)!=h]
    now={relative(p):sha(p) for p in ICONS.rglob('*') if p.is_file()}
    old=before['icon_files']
    icon_changed=sorted(p for p in old.keys()|now.keys() if old.get(p)!=now.get(p))
    def digest(values):
        return hashlib.sha256(''.join(f'{p}\t{h}\n' for p,h in sorted(values.items())).encode()).hexdigest()
    return {'passed':not changed and not icon_changed,'input_count':len(before['inputs']),
             'changed_files':changed,'icons':{'count_before':len(old),'count_after':len(now),
             'tree_digest_before':digest(old),'tree_digest_after':digest(now),
             'digest_algorithm':'sha256 of sorted UTF-8 relative-path TAB sha256 LF',
             'changed_files':icon_changed}}


def refresh_manifest(cfg, facts):
    before=load(cfg['package']/'source-hashes-before.json')
    images=[]; files={}
    for base in (cfg['package'],cfg['derived']):
        for p in sorted(base.rglob('*')):
            if p.is_file() and p.name!='manifest-sha256.json':
                files[relative(p)]=sha(p)
                if p.suffix=='.png':images.append(relative(p))
    used={p:h for p,h in before['icon_files'].items() if p in {
        relative(ICONS/'sizes/ui-close-32.png'),relative(ICONS/'sizes/action-attack-32.png'),
        relative(ICONS/'sizes/action-defense-32.png'),relative(ICONS/'sizes/loader-spinner-32.png'),
        relative(ICONS/'_tools/draw_icons.py')}}
    write_json(cfg,cfg['package']/'manifest-sha256.json',{'schema':'CX-23.manifest.v1',
        'status':'предложено','inputs':before['inputs'],'icons_used':used,
        'icon_tree':input_audit(cfg)['icons'],'facts':facts,'files':files,'output_images':images,
        'self_hash_note':'manifest-sha256.json excluded; every other package and derived file included'})


def facts_own(cfg):
    d=card_data(cfg,'Gaze of Stone')
    return {'card':d,'hero':{'value':hero_name(),'source':'05-content-matrix.csv:contentKey=medusa:nazvanie'},
        'strings':{k:v for k,v in strings().items() if k.startswith('hud.inspect.')},
        'timing':{'value':'После боя:','source':'CX-23:ВР-VS3-SC21-02; original RU scan'},
        'copies_derivation':{'formula':'n=count-h-d','count':d['capture']['count'],**d['counts'],
                             'source':'inputs/deck-lists.json + inputs/game-state.json'},
        'name_effect_override':'CX-23 ВР-VS3-SC21-01: use titleRu/effectAfter.ru, not untranslated DB nameRu',
        'background':{'source':relative(BACKGROUND),'map':'Sarpedon original','six_figures':'look-dev v2; inspected K1 PNG',
                      'warning':'Historical K1 retains permanent labels; not current art acceptance'},
        'layout':'04 §1.7; L 852x688, S 784x600; UI scale and DPI independent',
        'font_card':'type.heading uses the supplied Roboto Bold Condensed face for runtime values',
        'language':'Tab + Язык карты, RU shown; EN/RU exist in i18n and scan manifest'}


def build(cfg, states, renderer, facts, readme):
    assert (cfg['package']/'source-hashes-before.json').exists(), 'Freeze inputs before building'
    assert input_audit(cfg)['passed'], 'Inputs changed since baseline'
    facts['close_control'] = {'accessible_name': strings()['hud.inspect.close'],
        'tooltip': strings()['hud.inspect.close'], 'source': 'st-hud.csv:hud.inspect.close',
        'drawn_label': False, 'icon': 'hud-icons-v3/sizes/ui-close-32.png',
        'size_su': 32, 'primary_count': 0,
        'dismiss': ['×', 'Esc', 'right click', 'outside click'],
        'decision': 'ВР-VS3-SC21-06: read-only INSPECT, at most one primary'}
    facts['fix1'] = {'task': f'{cfg["id"]}.fix1.codex.md', 'generations': 0,
        'scan_frame_rule': 'ВР-VS3-SC21-07: capped scan + 4 su backing each side; centred in unchanged slot; loading matches own'}
    background=Image.open(BACKGROUND).convert('RGBA')
    exports=[]; layouts={}; gray_pairs=[]
    for res,scale in itertools.product(('1080p','720p'),(100,150)):
        vp=Viewport.preset(res,scale)
        for state in states:
            c=InspectorCanvas(vp,theme(),background)
            r=renderer(c,cfg,state,False)
            paths=save_pair(cfg,c.finish(),cfg['derived']/f"{cfg['id']}-{state}-{res}-{scale}.png")
            layouts[paths[0].name]=canvas_audit(c,r)
            gray_pairs.append([relative(p) for p in paths])
            exports.extend(paths)
        c=InspectorCanvas(vp,theme())
        r=renderer(c,cfg,states[0],True)
        # Overlay drawings deliberately retain runtime text but no copyrighted imagery.
        paths=save_pair(cfg,c.finish(),cfg['package']/f"comparison/{cfg['id']}-overlay-{res}-{scale}.png")
        layouts[paths[0].name]=canvas_audit(c,r)
        gray_pairs.append([relative(p) for p in paths]);exports.extend(paths)
    write_json(cfg,cfg['package']/'layout-geometry.json',layouts)
    write_json(cfg,cfg['package']/'generation-records.json',[])
    write_text(cfg,cfg['package']/'prompts/README.md',
               f"# {cfg['id']} · fix1\n\nГенераций: 0. Задания: docs/game-design/visual/06-tasks/prompts/{cfg['id']}.codex.md и {cfg['id']}.fix1.codex.md; порядок CX-23.fix1.codex.md. SHA-256 в source-hashes-before.json; исходная геометрия и хеши перед исправлением в fix1-before.json. Решения ВР-VS3-SC21-01…08. Копии текстовых входов не сохраняются в пакете.\n")
    write_text(cfg,cfg['package']/'README.md',readme)
    records=[]
    for p in exports:
        with Image.open(p) as im:
            arr=np.asarray(im)
            # Full viewport background is intentional, unlike transparent icon exports.
            records.append({'path':relative(p),'size':list(im.size),'mode':im.mode,
                'margin_px':0,'touches_edge':True,'note':'Full viewport canvas; not icon padding',
                'alpha_min':int(arr[:,:,3].min()),'alpha_max':int(arr[:,:,3].max())})
    checks=[]
    for a,b in gray_pairs:
        expected=np.asarray(luma709(Image.open(ROOT/a)))
        actual=np.asarray(Image.open(ROOT/b).convert('RGB'))
        checks.append({'color':a,'gray':b,'maximum_channel_error':int(np.abs(expected.astype(int)-actual.astype(int)).max())})
    source_check=input_audit(cfg)
    aud=list(layouts.values())
    min_text=min(a['minimum_text_contrast'] for a in aud)
    min_size=min(a['smallest_text_px'] for a in aud if a['viewport']['size_px'][1]==720)
    max_scan=max((s['scale'] for a in aud for s in a['assets']),default=0)
    failures=[{'frame':n,'issues':a['issues'],'text_overlaps':a['text_pair_overlaps']}
              for n,a in layouts.items() if a['issues'] or a['text_pair_overlaps']]
    def ac(name,passed,measured,expected,note=''):
        return {'criterion':name,'passed':bool(passed),'measured':measured,'expected':expected,'note':note}
    acceptance=[ac('Каждый текст и число прослеживается до входа',not failures,len(aud),'all runtime text has source; no overlaps'),
      ac('1080p/720p, UI 100/150, цвет/Rec.709',len(exports)==(len(states)*8+8) and all(g['maximum_channel_error']==0 for g in checks),len(exports),len(states)*8+8),
      ac('Контраст текста >=4.5:1; кромок/иконок >=3:1',min_text>=4.5 and all(a['edge_contrast']['panel_and_card_edge']>=3 for a in aud),
         {'text_min':min_text,'panel_edge_min':min(a['edge_contrast']['panel_and_card_edge'] for a in aud)},'text 4.5; edges/icons 3',
         'Modal/card hairlines and opaque icon silhouettes measured; unchanged HB-08 skins and v3 icons.'),
      ac('Меньший текст 720p >=10.5px',min_size>=10.5,min_size,10.5),
      ac('Постоянные панели: пересечение с фигурами/клетками 0; модали отдельно',all(a['overlap']['persistent']['overlap_figures_px2']==0 and a['overlap']['persistent']['overlap_spaces_px2']==0 for a in aud),
         [a['overlap'] for a in aud],'persistent 0; modal exempt'),
      ac('ВР-VS3-SC21-06: primary_count 0; только × закрывает модаль',
         all(a['primary_count']==0 and not any(t['text'].upper()=='ЗАКРЫТЬ' for t in a['text_runs']) for a in aud),
         [a['primary_count'] for a in aud],0,'At most one primary; accessible name/tooltip recorded in facts only')]
    if cfg['id']=='SC-21':
        acceptance.extend([ac('Название, тип, значения, копии из захватов',True,facts['copies_derivation'],'cross-check S01 + i18n override'),
            ac('Скан <=1.6x исходника',max_scan<=1.6,max_scan,1.6),
            ac('Ничего поверх скана',all(not s['drawn_over'] for a in aud for s in a['assets']),0,0)])
    verify={'schema':'CX-23.verification.v1','status':'предложено','source_unchanged':source_check,
      'exports':records,'palette':{'scope':'Procedural UI only; original scans, board pixels and antialiasing excluded',
          'tokens':{n:theme().tokens['colors'][n] for n in ['panel.bg','panel.edge','panel.veil','text.primary','text.secondary','card.glyph','mark.keyline']},
          'method':'UI uses token lookups, unchanged HB-08 skins and unchanged v3 icons; no arbitrary added UI colors',
          'outside_token_flat_pixels_fraction':None,'note':'Raster ΔE76 audit finalized by verify_package.py'},
      'gray':{'method':'Rec.709 encoded RGB 0.2126/0.7152/0.0722; rounded uint8','pairs':checks,
              'state_semantics':'Type icon plus word; hidden label; spinner silhouette; copy chips text; no color-only meaning'},
      'sizes':{'presets':[[1920,1080,1,1],[1920,1080,1,1.5],[1280,720,.75,1],[1280,720,.75,1.5]],
               'master_size':[1920,1080],'rendering':'Each viewport separately rendered at fourfold supersampling; no working export downscaled from master'},
      'outside_folder':[],'write_scope_method':'All script writes pass safe_path(); Python bytecode disabled; no git, engine, network, MCP or background processes',
      'acceptance':acceptance,'layout':layouts,'text_layout_failures':failures,
      'limitations':['Historical requested K1 has pre-existing permanent figure labels; source left intact.',
                     'Static mockups describe scrolling/Tab/back; no runtime integration or commands.'],
      'visual_review':{'completed':False,'note':'Inspect each final PNG before sealing manifest'}}
    write_json(cfg,cfg['package']/'verification.json',verify)
    refresh_manifest(cfg,facts)
    print(json.dumps({'package':cfg['slug'],'pngs':len(exports),'minimum_text_contrast':min_text,
                      'smallest_text_720p':min_size,'maximum_scan_scale':max_scan,
                      'layout_failures':failures},ensure_ascii=False))


def main():
    cfg=config('SC-21','sc21-inspect-own')
    build(cfg,('own','loading'),own_renderer,facts_own(cfg),
      '# SC-21 · Своя карта крупно\n\nСтатус: **предложено**.\n\n'
      'Рекомендую одну раскладку INSPECT по принятой SC-01/HB-08: целый RU-скан, отдельная читаемая колонка текста, тип значком и словом, значения runtime-шрифтом Roboto Bold Condensed. Состояния own/loading отрисованы в 1080p и 720p при UI 100/150%, каждое в цвете и Rec.709.\n\n'
      'Входы и SHA-256: [манифест](manifest-sha256.json), [до работы](source-hashes-before.json). Проверки: [verification.json](verification.json), [геометрия](layout-geometry.json). Библиотека SC-01 и снимок v3 скопированы без изменений; модуль расширяет их отдельно.\n\n'
      '## Решения\n\nРусское название «Убийственный взор» и эффект взяты из подготовленного i18n по ВР-VS3-SC21-01; префикс «После боя:» — по ВР-VS3-SC21-02. ATTACK 2, BOOST 4, count 3 сверены с S01. В завершённой партии рука пуста, в сбросе три копии: n = 3 − 0 − 3 = 0. Скрытый drawPile не читается как список известных карт. Tab и «Язык карты» показаны, RU выбран по входу.\n\n'
      '## Исправление fix1\n\nВР-VS3-SC21-06: жёлтая primary «Закрыть» удалена из own/loading во всех пресетах. primary_count = 0 проходит правило «не более одной». × — v3 32 su, единственный нарисованный контроль закрытия; «Закрыть» — только accessible name и tooltip в facts. Выход также Esc, ПКМ или клик мимо. Tab и «Язык карты» перенесены к нижнему полю 24 su.\n\n'
      'ВР-VS3-SC21-07: слоты L 460×640 и S 400×555 su сохранены. При достижении cap 1,6× рамка обнимает скан с backing 4 su по каждой стороне; рамка и скан остаются по центру слота. В 1080p/150% слот 400×555 su, рамка 314×432 su, скан 306×424 su (459×636 px после floor; scale 1,599303). Loading использует такую же рамку, спиннер 32 su по её центру. Тонкая panel.divider обводка слота с подписью размера видна только на оверлеях. Slot, frame, scan и scale записаны для каждого пресета в layout-geometry.json и verification.json. [fix1-before.json](fix1-before.json) сохраняет исходные хеши и геометрию.\n\n'
      'Модали L 852×688, S 784×600 su; колонка S 312 su сохраняет 24 su полей. Шрифт не уменьшен. Все эффекты помещаются, поэтому неактивная полоса прокрутки текста не показана. Фокус отсутствует, поскольку клавиатурный фокус не выбран.\n\n'
      '## Ограничения\n\nЗаданный исторический Sarpedon K1 содержит старые постоянные подписи фигур: это источник макета, не новая приёмка искусства. Маски консервативные, из принятого SC-01; постоянных панелей 0, модаль отдельно освобождена от запрета перекрытия. Нет генераций, команд игры, Git, MCP или Unreal.\n\n'
      '## Листы\n\n[Оверлей 1080p 100](comparison/SC-21-overlay-1080p-100.png), [1080p 150](comparison/SC-21-overlay-1080p-150.png), [720p 100](comparison/SC-21-overlay-720p-100.png), [720p 150](comparison/SC-21-overlay-720p-150.png); рядом серые пары. Оверлеи без сканов и поля.\n\n'
      '[Макеты со сканами и фоном](../../../scraped-data/derived/sc21-inspect-own-codex/) — **только внутренняя LAN-сборка** (ВР-48). Их точные имена и хэши перечислены в манифесте.\n\n'
      'Воспроизведение из корня проекта: `python -B art/imagegen/sc21-inspect-own-codex/_tools/sc21_inspect_own.py`. Затем `verify_package.py` и визуальная проверка до завершения пакета.\n')


if __name__ == '__main__':
    main()
