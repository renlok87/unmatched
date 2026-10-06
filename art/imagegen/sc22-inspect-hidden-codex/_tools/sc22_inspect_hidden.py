#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""SC-22 extends the unchanged FINAL SC-21 foundation. No card values loaded."""
import sys
sys.dont_write_bytecode = True
from sc21_inspect_own import (ROOT, config, build, shell, close_controls, strings,
                             hero_name, relative, sha)

BACK = ROOT / 'scraped-data/images/heroes/card-covers/ROSMO3sRi6Jh1o7S_riGI.png'


def hidden_renderer(c, cfg, state, overlay=False):
    r=shell(c)
    scan_layout=c.scan_layout(BACK,r['slot'],max_scale=1)
    r.update({k:scan_layout[k] for k in ('frame','scan','scan_scale')})
    c.card_frame(r['frame'])
    if overlay:c.slot_outline(r)
    x,y,w,h=r['text']
    end=c.paragraph((x,y+48),strings()['hud.inspect.hidden'],w,'type.title',
                    source='st-hud.csv:hud.inspect.hidden')
    c.text((x,end+24),hero_name(),source='05-content-matrix.csv:medusa:nazvanie')
    c.scan(BACK,r['slot'],overlay=overlay,max_scale=1)
    close_controls(c,r)
    return r


def main():
    cfg=config('SC-22','sc22-inspect-hidden')
    facts={'hero':{'value':hero_name(),'source':'05-content-matrix.csv:medusa:nazvanie'},
           'hidden':{'value':strings()['hud.inspect.hidden'],'source':'st-hud.csv:hud.inspect.hidden'},
           'close':{'accessible_name':strings()['hud.inspect.close'],'tooltip':strings()['hud.inspect.close'],
                    'drawn_label':False,'source':'st-hud.csv:hud.inspect.close'},
           'sc21_final_sha256':sha(ROOT/'art/imagegen/sc21-inspect-own-codex/_tools/sc21_inspect_own.py'),
           'card_back':{'source':relative(BACK),'sha256':sha(BACK),'identity':'Medusa Hero.imageUrl; SC-22 input'},
           'viewer':{'value':'Veteran / King Arthur','source':'SC-22 task:do','displayed':False},
           'data_minimization':'Renderer reads hero matrix, localized hidden/close strings and Hero card back; no card/deck capture read',
           'layout':'SC-21 FINAL: L 852x688 + 460x640; S 784x600 + 400x555, text width 312 to preserve 24 su padding',
           'background':'Specified historical Sarpedon original K1, lit3d and six v2 figures; inherited source-label caveat'}
    build(cfg,('hidden',),hidden_renderer,facts,
          '# SC-22 · Скрытая карта соперника\n\nСтатус: **предложено**.\n\n'
          'Рекомендую ту же модаль SC-21: рубашка Медузы целиком, заголовок «Скрытая информация», владелец «Медуза». Ни тип, ни значение, BOOST, эффект, копии или язык карты не показаны. Рендер не загружает захваты карт: скрытые поля нельзя случайно вывести. Зритель — Veteran (Король Артур), как задано карточкой.\n\n'
          'Финальный [sc21_inspect_own.py](_tools/sc21_inspect_own.py) и библиотека SC-01 скопированы побайтно; SHA-256 и проверка копий в [манифесте](manifest-sha256.json) и [verification.json](verification.json). Расширение — [sc22_inspect_hidden.py](_tools/sc22_inspect_hidden.py). Снимок генератора v3 неизменён. Метаданные HB-08 читаются из корня его пакета, рисунки — из vector/x1 и vector/x2.\n\n'
          '## Исправление fix1\n\nВР-VS3-SC21-06: жёлтая «Закрыть» удалена во всех пресетах. primary_count = 0 проходит правило «не более одной». × — v3 32 su, единственный нарисованный контроль закрытия; «Закрыть» — только accessible name и tooltip в facts. Выход также Esc, ПКМ и клик мимо. Заголовок «Скрытая информация» и владелец «Медуза» сохранены; типа, значения, BOOST, эффекта, копий и Tab нет.\n\n'
          'Финальный SC-21 после fix1 скопирован побайтно, новый sha256 записан в facts и проверке копий. [fix1-before.json](fix1-before.json) хранит входные хеши и прямоугольники до исправления, включая разрешённое обновление зависимости SC-21. Рубашка 768×1051 только уменьшается, поэтому cap не достигается и рамка остаётся размером слота: L 460×640, S 400×555 su. Модали 852×688 и 784×600 su, колонка S 312 su сохраняет поля по 24 su. Слоты и рамки обозначены на оверлеях; скан, frame и scale есть в геометрии. У модали нет команды игры.\n\n'
          '## Листы\n\n[1080p 100](comparison/SC-22-overlay-1080p-100.png), [1080p 150](comparison/SC-22-overlay-1080p-150.png), [720p 100](comparison/SC-22-overlay-720p-100.png), [720p 150](comparison/SC-22-overlay-720p-150.png), рядом серые пары. Только геометрия и runtime-строки, без рубашки/поля.\n\n'
          '[Полные макеты](../../../scraped-data/derived/sc22-inspect-hidden-codex/) — **только внутренняя LAN-сборка** (ВР-48). Все файлы обеих папок включены в SHA-256 манифест.\n\n'
          '## Ограничения\n\nИсторический заданный K1 содержит старые подписи фигур; сам источник не изменялся. Пересечения модали посчитаны отдельно и освобождены от запрета; постоянных панелей нет. Все четыре пресета отрисованы независимо, grayscale точно Rec.709. Без генераций, Git, MCP, Unreal и фона-заглушки.\n\n'
          'Воспроизведение: `python -B art/imagegen/sc22-inspect-hidden-codex/_tools/sc22_inspect_hidden.py`; аудит: `python -B art/imagegen/sc22-inspect-hidden-codex/_tools/verify_package.py --id SC-22 --slug sc22-inspect-hidden`.\n')


if __name__=='__main__':
    main()
