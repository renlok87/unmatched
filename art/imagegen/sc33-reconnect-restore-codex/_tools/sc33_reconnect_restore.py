#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""SC-33 extension of the byte-identical final SC-31 snapshot.

Exit is the R0+200ms keyframe: FX-36 w=1/3, no card/veil, online chip.
HB-40 toast uses the first collision-free placement in the contracted chain.
"""
import sys
sys.dont_write_bytecode = True
import math
import numpy as np
import sc31_reconnect_auto as shared
from sc31_reconnect_auto import reconnect, main

_place_toast = shared.place_toast
_readme = shared.readme
_overlay = shared.overlay


def measured_toast_placement(canvas, text):
    """Explain the conservative-mask/client difference with actual mask rows."""
    rect, record = _place_toast(canvas, text)
    vp = canvas.viewport
    x0 = math.floor(rect[0] * vp.factor)
    x1 = math.ceil((rect[0] + rect[2]) * vp.factor)
    first_rows = {}
    for name, mask in shared.protected_masks('marmoreal', vp.width, vp.height).items():
        rows = np.where(np.any(mask[:, x0:x1], axis=1))[0]
        first_rows[name] = int(rows[0]) if len(rows) else None
    record['first_protected_row_in_toast_span_px'] = first_rows
    record['chosen_bottom_px'] = math.ceil((rect[1] + rect[3]) * vp.factor)
    previous = record['attempts'][-2]
    record['preceding_pixel_rejected_by'] = {k:v for k,v in previous['overlap'].items() if v}
    record['difference_reason'] = (
        'The bench space polygons are dilated by 15px at 1080p (10px at 720p); '
        'their top row in the toast span binds before FIELD. HB-40 VR-VS4-29 '
        'uses per-cell rectangles projected through the current camera, not these '
        'bench masks. FIELD is also protected here but does not bind this placement. '
        'The explicit CX-33 rest-hand anchor changes the rejected bottom candidate. '
        'Each chosen top is the first permitted upward step; previous pixel overlap is recorded.')
    return rect, record


def restore_readme(card, verification, reviewed=False):
    value = _readme(card, verification, reviewed)
    old = ('Отличие от HB-40: здесь запрещено перекрывать весь консервативный прямоугольник FIELD, '
           'а клиент использует отдельные клеточные диски. Якорь руки отдельно задан серией. '
           'Поэтому его y 209/123/180/104 не копируются механически; сохранён первый допустимый результат цепочки.')
    new = ('Отличие от HB-40: здесь взяты bench-полигоны клеток с консервативной дилатацией '
           '15 px на 1080p / 10 px на 720p. Их верхняя строка в горизонтальном диапазоне тоста '
           'ограничивает подъём раньше прямоугольника FIELD. Клиент по ВР-VS4-29 использует '
           'прямоугольник каждой клетки, центр ± радиус через текущую камеру; это другой способ '
           'защиты. FIELD также включён, но не определяет эти четыре итоговые позиции. '
           'Якорь руки задан серией отдельно. В verification.json записаны первые строки каждой '
           'маски, низ тоста и пересечение предыдущего отвергнутого пикселя; его y '
           '209/123/180/104 не копируются механически. Сохранён первый допустимый результат цепочки.')
    return value.replace(old, new)


shared.place_toast = measured_toast_placement
shared.readme = restore_readme


def restore_overlay(frame, viewport, card, state):
    if state != 'exit-200ms':
        return _overlay(frame, viewport, card, state)
    # TOP's connection square occupies the usual top-left annotation band.
    # Put exit annotations in the empty bottom band so every outline survives.
    from screen_mockup_base import Canvas
    canvas = Canvas(viewport, frame['canvas'].theme)
    width, height = viewport.canvas
    shown = [g for g in frame['geometry'] if g['visible']]
    for item in shown:
        x, y, w, h = item['rect_su']
        canvas.line([(x,y),(x+w,y),(x+w,y+h),(x,y+h),(x,y)], canvas.theme.color('panel.edge'))
    labels = []
    def label(xy, value, role):
        bbox = canvas.text(xy, value, role, source='SC-33 BindWidget layout geometry')
        labels.append([v/canvas.ss for v in bbox])
    label((24,height-208), f'{card} {state} / {viewport.width}x{viewport.height} / UI {round(viewport.ui*100)} / {viewport.layout_class}', 'type.body')
    for i, item in enumerate(shown):
        x, y, w, h = item['rect_su']
        label((24,height-168+i*24), f"{item['name']}  x={x:.2f} y={y:.2f} w={w:.2f} h={h:.2f} su", 'type.caption')
    hidden = ', '.join(g['name'] for g in frame['geometry'] if not g['visible'])
    label((24,height-168+len(shown)*24), 'hidden: '+hidden, 'type.caption')
    overlap = sum(max(0,min(a[2],b[2])-max(a[0],b[0])) * max(0,min(a[3],b[3])-max(a[1],b[1]))
                  for i,a in enumerate(labels) for b in labels[i+1:])
    return canvas.finish().convert('RGBA'), {'labels_px':labels,'label_overlap_px2':overlap,
            'no_source_frame_pixels':True,'background':'card.navy','annotation_band':'bottom; TOP square kept fully visible'}


shared.overlay = restore_overlay


def draw_restoring(viewport):
    return reconnect(viewport, board='marmoreal', desaturation_weight=1,
                     veil_opacity=.8, card_state='restoring')


def draw_exit_200ms(viewport):
    return reconnect(viewport, board='marmoreal', desaturation_weight=1/3,
                     veil_opacity=0, card_state='none',
                     toast='hud.toast.reconnected', connection_chip=True)


if __name__ == '__main__':
    main('SC-33')
