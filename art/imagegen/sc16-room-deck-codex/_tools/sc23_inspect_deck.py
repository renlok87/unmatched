#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Catalogue mode extends the unchanged FINAL SC-21 module.

Three columns, two whole rows per scroll stop. Static scroll proof covers every
unique catalogue entry exactly once across the two required viewport variants.
"""
import sys
sys.dont_write_bytecode = True
import csv
import itertools
from PIL import Image
from sc21_inspect_own import (ROOT, VIEWER, config, build, load, card_data, rects,
    strings, hero_name, draw_card, write_json, refresh_manifest, relative,
    theme, contrast, close_controls, sha)


def deck_strings():
    with (ROOT/'docs/game-design/visual/06-tasks/screens.csv').open(encoding='utf-8-sig',newline='') as f:
        text=next(r['do'] for r in csv.DictReader(f) if r['id']=='SC-23')
    out={}
    for key in ('hud.inspect.deck.title','hud.inspect.copies.short','hud.inspect.back'):
        out[key]=text.split('Строки:',1)[1].split(key,1)[1].split('«',1)[1].split('»',1)[0]
    return out


def catalogue(cfg):
    d=next(d for d in load(cfg['derived']/'inputs/deck-lists.json')['gameDeckLists'] if d['playerId']==VIEWER)
    assert len(d['cards'])==11 and sum(c['count'] for c in d['cards'])==d['total']==30
    # This is the catalogue capture order, with no drawPile or instance order.
    return [card_data(cfg,c['nameEn']) for c in d['cards']]


def deck_renderer(c,cfg,state,overlay=False):
    if state=='deck-card':
        return draw_card(c,cfg,state,'Hiss and Slither',overlay,back=True)
    r=rects(c.viewport)
    c.veil();c.panel(r['modal'],kind='modal')
    x,y,w,h=r['modal'];ds=deck_strings()
    c.text((x+24,y+24),ds['hud.inspect.deck.title'].format(hero=hero_name()),'type.title',
           source='screens.csv:SC-23:do:hud.inspect.deck.title + 05-content-matrix.csv:medusa')
    close_controls(c,r)
    # A fixed viewport keeps both entire rows readable at class S 720p / 150%.
    rows,cols,step_y,step_x,view_h=2,3,232,230,440
    title_bottom=y+76
    bottom_line=y+h-24
    view_y=title_bottom+(bottom_line-title_bottom-view_h)/2
    view=(x+24,view_y,w-48,view_h)
    c.skin(view,'PanelInset')
    # 150 su card + 8 su gap + 40 su copy chip; row and chip never overlap.
    grid_w=658
    start_x=x+24+(w-48-24-grid_w)/2
    first=6 if state=='deck-scroll' else 0
    cards=catalogue(cfg)
    visible=[]
    for index in range(first,min(first+6,len(cards))):
        local=index-first;col,row=local%cols,local//cols
        fx,fy=start_x+col*step_x,view_y+row*step_y
        frame=(fx,fy,150,208)
        c.card_frame(frame)
        data=cards[index]
        c.scan(ROOT/data['art']['ru']['path'],frame,overlay=overlay)
        chip=(fx+158,fy+88,40,32)
        label=ds['hud.inspect.copies.short'].format(n=data['capture']['count'])
        c.chip(chip,label,source='screens.csv:SC-23:do:hud.inspect.copies.short + inputs/deck-lists.json:count')
        if overlay:
            c.text((fx+8,fy+16),'150 × 208 su','type.caption',
                   source='04 §1.7: deck tile size in su')
            c.text((fx,fy+208+4),f'({fx-x:g}, {fy-y:g})','type.caption',
                   source='07: documentation anchors in su')
        visible.append({'title':data['localized']['titleRu'],'copies':data['capture']['count'],
                        'frame_su':frame,'chip_su':chip,'scan':data['art']['ru']['path']})
    # Use HB-08 existing slider skins for the read-only scrollbar.
    sx,sy=x+w-36,view_y
    c.skin((sx,sy,8,view_h),'SliderTrack')
    thumb_h=view_h*view_h/(4*208+3*24)
    thumb_y=sy+(view_h-thumb_h if first else 0)
    c.skin((sx-2,thumb_y,12,thumb_h),'SliderThumb')
    c.notes.append({'grid':{'columns':3,'visible_rows':rows,'tile_su':[150,208],
        'viewport_su':view,'scroll_su':464 if first else 0,'content_height_su':904,
        'snap_to_whole_rows':True,'catalogue_count':11,'total_copies':30,
        'title_band_bottom_su':title_bottom,'bottom_padding_line_su':bottom_line,
        'vertical_gap_su':(bottom_line-title_bottom-view_h)/2,
        'entries':visible,'semantics':'Catalogue composition, not draw order; chips beside scans'}})
    # Return all modal regions; no persistent panel is present.
    return {'modal':r['modal'],'grid_viewport':view,'card_size_su':[150,208],
            'copy_chip_size_su':[40,32],'anchor':'centre','scroll_stop':state}


def facts(cfg):
    cards=catalogue(cfg)
    font=theme().font('type.caption',4)
    advances={n:font.getlength(n)/4 for n in '0123456789'}
    assert max(advances.values())-min(advances.values())<=.001
    return {'deck':{'unique':len(cards),'total':sum(c['capture']['count'] for c in cards),
                    'source':'inputs/deck-lists.json:gameDeckLists[Medusa].cards, count',
                    'catalogue_order':[c['capture']['nameEn'] for c in cards],
                    'order_policy':'CX-23 ВР-VS3-SC21-05 / F-05: capture catalogue order, never drawPile'},
            'cards':cards,'opened_card':next(c for c in cards if c['capture']['nameEn']=='Hiss and Slither'),
            'strings':deck_strings(),'hero':{'value':hero_name(),'source':'05-content-matrix.csv:medusa:nazvanie'},
            'sc21_final_sha256':sha(ROOT/'art/imagegen/sc21-inspect-own-codex/_tools/sc21_inspect_own.py'),
            'room_copies':{'value':'×3','count':3,'skin':'Chip','position':'text column after BOOST',
                'source':'screens.csv:SC-23:do:hud.inspect.copies.short + gameDeckLists.count',
                'decision':'ВР-VS3-SC21-08','hand_discard_available':False,
                'hud.inspect.copies_displayed':False},
            'runtime_copy_digits':{'font':'Roboto Regular / type.caption','advances_su':advances,'tabular':True},
            'timing':{'value':'После боя:','source':'CX-23 ВР-VS3-SC21-02 / Hiss and Slither RU scan'},
            'background':'Specified Sarpedon original historical K1, lit3d and six v2 figures; historical labels retained',
            'lang_toggle':'Tab + Язык карты, RU shown; EN/RU titles/effects/scans exist',
            'scroll_proof':'deck displays first 6 unique entries; supplemental deck-scroll displays last 5; each once across the two stops',
            'card_values':'gameDeckLists cardType, attackValue/defenseValue and boostValue cross-checked against S01',
            'scheme_catalogue_caveat':'S01 value incorrectly carries BOOST for SCHEME; no scheme value is drawn. Types, boosts and copies cross-check.'}


def refine_audit(cfg):
    d=load(cfg['package']/'verification.json')
    # Independent copy/scroll rectangles and real underlying flat skin colors.
    for name,a in d['layout'].items():
        note=next((n['grid'] for n in a['notes'] if 'grid' in n),None)
        pix=Image.open(ROOT/(relative(cfg['package']/'comparison'/name) if 'overlay' in name else relative(cfg['derived']/name))).convert('RGB')
        f=a['viewport']['factor'];checks=[]
        if not note:
            chip=next(n['room_copies_chip'] for n in a['notes'] if 'room_copies_chip' in n)
            x,y,w,h=chip['rect_su']
            body=pix.getpixel((round((x+6)*f),round((y+h/2)*f)))
            ratio=contrast(theme().color('text.primary'),body)
            assert ratio>=4.5
            a['room_copy_chip']={**chip,'body_rgb':body,'text_contrast':ratio}
            continue
        for item in note['entries']:
            x,y,w,h=item['chip_su']
            body=pix.getpixel((round((x+6)*f),round((y+h/2)*f)))
            ratio=contrast(theme().color('text.primary'),body)
            assert ratio>=4.5
            ax,ay,aw,ah=item['frame_su']
            area=max(0,min(x+w,ax+aw)-max(x,ax))*max(0,min(y+h,ay+ah)-max(y,ay))
            assert area==0
            checks.append({'copies':item['copies'],'chip_body_rgb':body,'text_contrast':ratio,
                           'chip_scan_frame_overlap_su2':area,'chip_rect_su':item['chip_su']})
        a['grid_copy_chips']=checks
        a['scrollbar']={'skins':['SliderTrack','SliderThumb'],'viewport_height_su':440,
                        'content_height_su':904,'whole_rows_per_stop':2}
    d['sizes']['additional_states']=['deck-scroll (scroll proof; all 11 unique cards)']
    write_json(cfg,cfg['package']/'layout-geometry.json',d['layout'])
    write_json(cfg,cfg['package']/'verification.json',d)
    refresh_manifest(cfg,load(cfg['package']/'manifest-sha256.json')['facts'])


def main():
    cfg=config('SC-23','sc23-inspect-deck')
    build(cfg,('deck','deck-card','deck-scroll'),deck_renderer,facts(cfg),
      '# SC-23 · Режим колоды\n\nСтатус: **предложено**.\n\n'
      'Рекомендую сетку в три колонки: целые карты 150×208 su, чип копий 40×32 su справа с зазором 8 su. Два полных ряда видны и в S при 720p/150%; скролл показывает оставшиеся пять карт. Обе позиции дают все 11 уникальных RU-сканов ровно по одному разу, сумма count = 30. Порядок — gameDeckLists, состав каталога, а не порядок колоды.\n\n'
      'Кадры deck / deck-card — обязательные; deck-scroll — дополнительное доказательство прокрутки. Все три состояния существуют в 1080p/720p, UI 100/150, цвете и точном Rec.709. В deck-card открыта «Шипеть и извиваться»: Защита, Значение 4, BOOST 3, «После боя: Ваш противник сбрасывает 1 карту.»; «Назад» возвращает к сетке. Tab и «Язык карты» показаны. Это статический макет, runtime-обработчиков нет.\n\n'
      '## Происхождение\n\nЧисла взяты из [захвата](../../../scraped-data/derived/sc23-inspect-deck-codex/inputs/deck-lists.json) и сверены с S01; RU — подготовленный i18n; все 11 ссылок RU/EN проверены по reused-cardart.json. Открытая карта не показывает счётчики текущей руки, которых нет в ROOM-захвате. В ROOM ещё нет руки и сброса, поэтому hud.inspect.copies не показан. ВР-VS3-SC21-08: прежняя отдельная строка ×3 заменена чипом ×3 из состава сразу после BOOST; это тот же HB-08 Chip 40×32 su, что в сетке. S01 ошибочно хранит BOOST в value схем: эта несовместимость явно указана в facts, значение схем не выводится.\n\n'
      'Финальный SC-21, библиотека SC-01 и снимок v3 скопированы без изменения. [sc23_inspect_deck.py](_tools/sc23_inspect_deck.py) расширяет их отдельно. Хэши входов/всех файлов: [manifest-sha256.json](manifest-sha256.json), [source-hashes-before.json](source-hashes-before.json); измерения: [verification.json](verification.json), [layout-geometry.json](layout-geometry.json). Копии цифр имеют равные advance ширины 0–9 в Roboto Regular; строки отрисованы runtime-слоем. Ни один чип не пересекает скан.\n\n'
      '## Геометрия\n\nМодали L 852×688 и S 784×600 su, центр холста. Fix1, ВР-VS3-SC21-06: жёлтая «Закрыть» удалена из deck, deck-scroll и deck-card во всех пресетах. primary_count = 0 проходит правило «не более одной». × — v3 32 su; «Закрыть» — только accessible name и tooltip в facts. В deck-card остаётся одна обычная кнопка «Назад». Tab и «Язык карты» у нижнего поля 24 su. Viewport центрирован между концом title band y=76 и нижним полем 24 su: y=150 у L и y=106 у S, равные промежутки 74 и 30 su; viewport 440 su, шаг ряда 232, полное содержимое 904 su; прокрутка по целым рядам на 464 su. Частично обрезанных карт нет. Заголовок и × остаются сверху, scrollbar сохранён. ВР-VS3-SC21-07: открытая карта повторяет финальный SC-21 fix1, включая рамку capped-скана с backing 4 su по каждой стороне и прежним слотом. Slot, frame, scan и scale записаны для каждого пресета. Финальный sc21_inspect_own.py скопирован побайтно после fix1; новый sha256 в facts. [fix1-before.json](fix1-before.json) хранит исходные хеши и прямоугольники; в S колонка 312 su сохраняет поля по 24 su. Скан ограничен физическим 1,6×. Готовые HB-08 используются для модали, inset, кнопок, чипов, трека и ползунка.\n\n'
      '## Листы\n\n[Оверлей 1080p 100](comparison/SC-23-overlay-1080p-100.png), [1080p 150](comparison/SC-23-overlay-1080p-150.png), [720p 100](comparison/SC-23-overlay-720p-100.png), [720p 150](comparison/SC-23-overlay-720p-150.png), рядом серые пары. Оверлеи содержат рамки, размеры, координаты относительно модали и чипы, без арта поля/сканов.\n\n'
      '[Полные кадры](../../../scraped-data/derived/sc23-inspect-deck-codex/) — **только внутренняя LAN-сборка** (ВР-48).\n\n'
      '## Ограничения\n\nИсторический заданный K1 сохраняет старые подписи фигур, это не новая приёмка искусства. Модали могут перекрывать поле; постоянных панелей нет, пересечения с консервативными масками посчитаны отдельно. Нет генераций, Git, MCP, Unreal, instance ids на экране и порядка drawPile.\n\n'
      'Воспроизведение: `python -B art/imagegen/sc23-inspect-deck-codex/_tools/sc23_inspect_deck.py`; аудит: `python -B art/imagegen/sc23-inspect-deck-codex/_tools/verify_package.py --id SC-23 --slug sc23-inspect-deck`.\n')
    refine_audit(cfg)


if __name__=='__main__':
    main()
