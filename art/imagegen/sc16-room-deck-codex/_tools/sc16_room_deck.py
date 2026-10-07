#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""SC-16 composes unchanged SC-23 deck rendering over unchanged SC-14 ROOM.

The adapter changes only native icon pasting and exposes SC-21 canvas methods;
deck layout, scans, count chips and catalogue access remain SC-23's code.
"""
import sys
sys.dont_write_bytecode=True
from types import MethodType
from PIL import Image
import sc14_room_hero as b
import sc23_inspect_deck as deck
from sc21_inspect_own import InspectorCanvas

SC23=b.ROOT/'art/imagegen/sc23-inspect-deck-codex'
SC23_DERIVED=b.ROOT/'scraped-data/derived/sc23-inspect-deck-codex'

def states():
    return {'deck-count':b.frame_options('room-state.json','both_picked',deck_hover=True),
            'deck-open':b.frame_options('room-state.json','both_picked',deck_open=True)}

def renderer(c,options):
    room=b.draw_room(c,options)
    if options.get('deck_open'):
        # Native screen icons remain below the second veil; tint their pixels
        # algebraically instead of scaling them or pasting them above the veil.
        navy=c.theme.color('panel.veil');veiled=[]
        for (im,xy),meta in zip(c.icon_layers,c.icons):
            if meta['name'].startswith('cursor-'):continue
            channels=list(im.split())
            for i in range(3):channels[i]=channels[i].point(lambda v,n=navy[i]:round(v*.4+n*.6))
            veiled.append((Image.merge('RGBA',channels),xy))
        c.active_layer='modal';c.icon_layers=veiled;c.wrapped=[]
        for name in ('scan_layout','scan','card_frame'):
            setattr(c,name,MethodType(getattr(InspectorCanvas,name),c))
        original_icon=c.icon
        def compatible_icon(self,first,second,size=32):
            if isinstance(first,(tuple,list)):return original_icon(second,first,size)
            return original_icon(first,second,size)
        c.icon=MethodType(compatible_icon,c)
        cfg=deck.config('SC-23','sc23-inspect-deck')
        r=deck.deck_renderer(c,cfg,'deck',overlay=False)
        c.record('UUmScreenInspect',r['modal'],mode='deck',source='unchanged SC-23 deck_renderer')
        c.record('UUmScreenInspect.DeckGrid',r['grid_viewport'],columns=3,rows=2,card_size_su=[150,208],unique_count=11,copy_total=30)
        for i,entry in enumerate(c.notes[-1]['grid']['entries']):
            c.record(f'UUmScreenInspect.UUmCardWidget[{i}]',entry['frame_su'],title=entry['title'],copies=entry['copies'],whole_scan=True)
            c.record(f'UUmScreenInspect.CopyChip[{i}]',entry['chip_su'],copies=entry['copies'])
        c.icon('cursor-default',(c.viewport.canvas[0]-48,c.viewport.canvas[1]-48),32)
    return room

def extra_inputs():
    files=['art/imagegen/sc14-room-hero-codex/_tools/sc14_room_hero.py',
           'art/imagegen/sc14-room-hero-codex/_tools/finalize_review.py',
           'art/imagegen/sc14-room-hero-codex/manifest-sha256.json',
           'art/imagegen/sc23-inspect-deck-codex/README.md',
           'art/imagegen/sc23-inspect-deck-codex/manifest-sha256.json']
    files.extend(b.rel(p) for p in (SC23/'_tools').glob('*.py'))
    files.extend(b.rel(p) for p in (SC23_DERIVED/'inputs').glob('*.json'))
    # Every source transitively read by the unchanged catalogue renderer.
    files.extend(b.load(SC23/'manifest-sha256.json')['inputs'])
    for px in (24,32,36,48):
        p=b.ICONS/f'sizes/ui-close-{px}.png'
        if p.exists():files.append(b.rel(p))
    return sorted(set(files))

def build():
    manifest=b.load(SC23/'manifest-sha256.json')
    for name in ('sc23_inspect_deck.py','sc21_inspect_own.py'):
        path=SC23/'_tools'/name
        assert b.sha(path)==manifest['files'][b.rel(path)],'Accepted SC-23 script differs from manifest'
    cfg=deck.config('SC-23','sc23-inspect-deck');catalog=deck.catalogue(cfg)
    assert len(catalog)==11 and sum(c['capture']['count'] for c in catalog)==30
    assert sum(c['quantity'] for c in b.load(b.ROOT/'docs/game-design/evidence/S01/catalog-medusa.json')['hero']['cards'])==30
    copies=[('art/imagegen/sc14-room-hero-codex/_tools/sc14_room_hero.py','sc14_room_hero.py'),
            ('art/imagegen/sc14-room-hero-codex/_tools/finalize_review.py','finalize_review.py'),
            ('art/imagegen/sc23-inspect-deck-codex/_tools/sc23_inspect_deck.py','sc23_inspect_deck.py'),
            ('art/imagegen/sc23-inspect-deck-codex/_tools/sc21_inspect_own.py','sc21_inspect_own.py')]
    v=b.build('SC-16',states(),renderer,extra_inputs(),copies)
    manifest=b.load(b.PACKAGE/'manifest-sha256.json');facts=manifest['facts']
    facts['deck_catalogue']=deck.facts(cfg)
    v['deck_composition']={'total':30,'unique':11,'S01_crosscheck':True,'order':'catalogue capture order; no instance/drawPile order',
        'visible_cards':6,'remaining_scroll_cards':5,'renderer':'unchanged SC-23 deck state',
        'read_only_inputs':b.rel(SC23_DERIVED/'inputs')}
    b.dump(b.PACKAGE/'verification.json',v)
    p=b.PACKAGE/'README.md'
    b.text_file(p,p.read_text(encoding='utf-8')+'\n## SC-16: композиция колоды\n\nКадры deck-count и deck-open — host / 6PPWSS / both_picked. В deck-count только кнопка просмотра в hover с native cursor-pointer. Deck-open вызывает исходный SC-23 deck_renderer для Medusa, без изменений скрипта: три колонки, два полных ряда, 150×208 su, копии рядом. Видно шесть карт; оставшиеся пять доступны в принятом скролле SC-23. Состав 11 / 30 сверён по S01 и deck-lists.json; порядок drawPile не показывается. Заголовок «Колода · Медуза» — строка принятого SC-23, остальные имена ROOM остаются значениями БД. Все сканы находятся только в derived.\n')
    b.refresh_manifest(facts)
    return v

if __name__=='__main__':
    sys.stdout.reconfigure(encoding='utf-8');build()
