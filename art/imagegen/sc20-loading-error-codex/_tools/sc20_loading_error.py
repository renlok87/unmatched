#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""SC-20 extension only; copied SC-19 and inherited libraries remain unchanged."""
import sys
sys.dont_write_bytecode=True
from sc19_loading import build,PACKAGE,load,dump,write_text,refresh_manifest


def main():
    sys.stdout.reconfigure(encoding='utf-8')
    v=build('SC-20',{'error':{
        'stage_key':'screens.loading.error','icon_name':'resource-connection-lost',
        'buttons':(('LobbyButton','common.btn.lobby',False),('RetryButton','common.btn.retry',True))}})
    # The taller panel must remain centred: all unchanged screen content moves
    # up by half the added 72 su. Preserve the icon's slot relative to the panel.
    v['SC19_reuse']={'unchanged_copy':True,'panel_growth_su':72,'content_translation_su':[0,-36],
                    'icon_slot_relative_to_panel_unchanged':True,'icon_shape_changed':True,
                    'literal_absolute_xy_unchanged':False,
                    'note':'The common centred-panel requirement and +72 su growth imply -36 su vertical translation; x/size and internal slot anchors stay identical. Documented resolution of same x,y wording.',
                    'lobby_button_never_aborts_server_match':True,'return_path':['SC-11','SC-05']}
    dump(PACKAGE/'verification.json',v)
    p=PACKAGE/'README.md'
    write_text(p,p.read_text(encoding='utf-8')+'''\n## Уточнение общих координат и кромок\n\nВР-VS5-SC20-01…03: сохранились размеры карточек, их данные, поле и якорь значка относительно LoadingPanel. Панель стала выше на 72 su и осталась строго по центру, поэтому верхняя часть целиком поднялась на 36 su. Буквальные абсолютные y спиннера SC-19 и ErrorIcon SC-20 различаются на −36 su; требование «тот же слот» исполнено во внутренних координатах, конфликт абсолютного y с центрированием отмечен в `SC19_reuse`. Полная подпись ошибки расширяет текстовый слот на 20,25 su вправо, значок по x не прыгает.\n\nCP-07: декоративная кромка поверх рисунка также не достигает 3:1 по всей окружности, цвет и серый измерены в `frames.raster_contrast.portrait_edges`. Исходные рисунки, обод и HB-08 normal primary сохранены; буквальный критерий кромок отмечен непройденным. Палитра проверяет плоские внутренние области UI без арта, закруглённых углов и AA-полосы, а не объявляет весь фон токеновым.\n''')
    refresh_manifest()


if __name__=='__main__':main()
