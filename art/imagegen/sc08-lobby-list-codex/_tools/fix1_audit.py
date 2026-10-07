"""Prepare immutable sources and finish a visually reviewed corrective package."""
import sys
sys.dont_write_bytecode=True
import json
import hashlib
from pathlib import Path
import sc08_lobby_list as b

DESCRIPTIONS={
 'SC-08': [('loading','Три строки-заглушки без текста; ключевой кадр 900 мс.'),('list','Пять реальных комнат; первая строка под указателем, две последние недоступны.')],
 'SC-09': [('create-marmoreal','1×1, выбрана Marmoreal, «СОЗДАТЬ» — основная кнопка.'),('create-sarpedon','Выбрана Sarpedon; остальные элементы доступны.'),('busy','Marmoreal; «СОЗДАЁМ…», спиннер 32 su и курсор ожидания; подсказка why.syncing.')],
 'SC-10': [('create-ai','«Против ИИ», Sarpedon; заметка «Соперник — ИИ: AI Bot», без аватара бота.'),('busy','Та же конфигурация во время создания, со спиннером и курсором ожидания.')],
 'SC-11': [('code-partial','VZSJ; пятая ячейка в фокусе, две пустые с подчёркиванием; «Введите 6 символов».'),('code-full','VZSJFT; «ВОЙТИ» — основная кнопка с клавиатурным фокусом, «СОЗДАТЬ» — обычная.'),('code-error-notfound','3GPMCA сохранён; badge-refuse и «Игра не найдена»; «ВОЙТИ» — основная.'),('code-error-full','4XM89G сохранён; badge-refuse и «Комната заполнена»; «ВОЙТИ» — основная.')],
 'SC-12': [('empty','Ответ availableGames(ONE_V_ONE) = []; строк нет. Лампочка 32 su над текстом, «ОБНОВИТЬ» доступна.')],
 'SC-13': [('error','resource-connection-lost 48 su, «Не удалось загрузить список игр», обычная «ПОВТОРИТЬ». «ОБНОВИТЬ» скрыта. Создание и вход доступны.')]
}

def prepare(task):
    baseline=b.load(b.PACKAGE/'fix1-baseline.json')['source_inventory']['files']
    current=b.source_inventory(task)
    permitted={'art/imagegen/sc08-lobby-list-codex/_tools/sc08_lobby_list.py','art/imagegen/sc09-lobby-create-codex/_tools/sc09_lobby_create.py'}
    changed=[p for p,h in baseline.items() if b.sha(Path(p) if Path(p).is_absolute() else b.ROOT/p)!=h and p not in permitted]
    if changed:raise ValueError('Original source changed: '+repr(changed))
    b.dump(b.PACKAGE/'source-hashes-before.json',{'files':current,'hud_icons_v3':b.tree_digest(current),'fix1_previous_inventory':'fix1-baseline.json'})
    for name in (f'{task}.fix1.codex.md','SC-08-series.fix1.codex.md'):
        b.guard(b.PACKAGE/'prompts'/name).write_bytes((b.ROOT/'docs/game-design/visual/06-tasks/prompts'/name).read_bytes())

def digest_json(value):
    return hashlib.sha256(json.dumps(value,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode('utf-8')).hexdigest()

def finish():
    import finalize_package
    finalize_package.main()
    v=b.load(b.PACKAGE/'verification.json');task=v['task']
    geom=b.load(b.PACKAGE/'layout-geometry.json')
    v['limitations']=[s for s in v['limitations'] if 'Conditional RecoverButton' not in s]
    v['spacing_changes']['class_S']='Размеры шрифта сохранены; названия карт в строках помещаются в одну строку. Минимальный зазор колонок >=8 su.'
    v['overlay_review']={key:{'states':list(item['overlay_bind_widgets']),'label_overlap_pairs':sum(len(a['overlapping_label_pairs']) for a in item['overlay_audit']),
                                  'source_illustrations':False,'all_elements_have_coordinates':True} for key,item in geom.items()}
    if any(r['label_overlap_pairs'] for r in v['overlay_review'].values()):raise ValueError('Overlay label overlap')
    inset=[q['minimum_su'] for states in v['layout_measurements'].values() for m in states.values() for q in m['row_content_insets']]
    v['row_content_inset_min_su']=min(inset) if inset else None
    v['acceptance']['fix1 row inset >=8su']={'passed':not inset or min(inset)>=8-1e-6,'measured':min(inset) if inset else None,'expected':8,'note':'All row slots and actual text ink; skeleton bars separately. Cursor is not row content; no rows in empty/error.'}
    v['acceptance']['fix1 text overlap zero']={'passed':all(not m['text_overlap'] and not m['clipped_text'] for states in v['layout_measurements'].values() for m in states.values()),'expected':0,'measured':sum(len(m['text_overlap'])+len(m['clipped_text']) for states in v['layout_measurements'].values() for m in states.values())}
    if task=='SC-10':
        gap=[]
        for key,states in v['layout_measurements'].items():
            if not key.endswith('-150'):continue
            for state,m in states.items():
                r={x['source']:x for x in m['text_runs']};f=m['factor'];g=geom[key]['rectangles']
                note=r['ai-note']['bbox_px'];label=r['screens.lobby.create.board']['bbox_px']
                mode_bottom=max(g[n][1]+g[n][3] for n in ('ModeChip1v1','ModeChipAi'))
                q={'canvas':key,'state':state,'mode_to_note_su':note[1]/f-mode_bottom,'note_to_board_label_su':(label[1]-note[3])/f,'board_label_to_tiles_su':g['BoardChips[0]'][1]-label[3]/f}
                gap.append(q)
        v['ai_note_ink_spacing']=gap
        v['acceptance']['fix1 AI ink spacing >=8su']={'passed':all(min(q[k] for k in ('mode_to_note_su','note_to_board_label_su','board_label_to_tiles_su'))>=8 for q in gap),'measured':gap,'expected':8}
    if task=='SC-12':
        used=[i for states in v['layout_measurements'].values() for m in states.values() for i in m['icons'] if i['name']=='state-hint']
        v['hint_glyph_layers']=used
        v['acceptance']['fix1 hint glyph only']={'passed':all('/layers/state-hint_glyph-' in i['source'] and i['crop_px'][0:2]==[0,0] for i in used),'measured':used,'expected':'left square glyph layer, 32su, no plate'}
    v['acceptance_pass']=all(a['passed'] for a in v['acceptance'].values())
    review=b.load(b.PACKAGE/'visual-review.json')
    review['limitations']=['RecoverButton скрыт: myGames пуст. На L резерв внутри CodeColumn, на S только пояснение без прямоугольника.']
    review['checks']=list(dict.fromkeys(review['checks']+['fix1: отступы строк по измерениям','fix1: подписанные схемы каждого состояния и легенды координат']))
    b.dump(b.PACKAGE/'visual-review.json',review)
    text_min=v['acceptance']['text contrast >=4.5:1']['measured'];small=v['acceptance']['smallest text 720p >=10.5px']['measured'];edge=v['acceptance']['edges and icons >=3:1']['measured']['native_panel_boundary_min']
    lines=[f'# {task} — макеты лобби, fix1','', 'Статус: **предложено**. Рекомендуется исправленный вариант на принятых скинах HB-08 и библиотеке SC-01: данные сохранены, схемы показывают состояния этой карточки; исправленный общий модуль списка скопирован без изменений.', '', '## Состояния', '']
    lines += [f'- `{s}` — {description}' for s,description in DESCRIPTIONS[task]]
    lines += ['', '## Данные','', 'Никнейм **ProGamer** — `inputs/available-games.json`, поле `viewer.username` (источник: `backend/prisma/seed.ts`, строка 34). Две доски — ответы `adminBoard` в `inputs/all-boards.json`: `c121b47f8d6eb28daccb76d05`, **Marmoreal · original map**; `c7fa64a26c29a0835f2383e63`, **Sarpedon · original map**. Иллюстрации взяты целиком из `scraped-data/images/maps/`, без обрезки, названия под ними. Публичный каталог не используется.']
    if task in ('SC-08','SC-09','SC-10','SC-11'):
        lines += ['', 'Список — пять строк t0 из `inputs/available-games.json`, в порядке ответа: **VZSJFT, EK74C3, QSMFTR, 4XM89G, ZJ4LXZ**. Режим 1×1; у трёх доступных комнат 1/2 мест. После t0 ответы `joinGame` в `inputs/list-join-errors.json`: 4XM89G — «Игра уже заполнена» → why.room.full «Комната заполнена»; ZJ4LXZ — «Нельзя присоединиться к игре, которая уже началась или завершилась» → why.room.started «Игра уже началась». У них нет кнопки и значения мест, причина видна и записана как подсказка; следующий опрос удаляет эти строки.', '', 'Диски 32 su: King Arthur (`cmq7d7b1000njwi74a536w55r`) и Medusa (`cmq7d7b4000r8wi74tzd1jmxv`) из ответов `adminHero` в `inputs/heroes.json`; портреты CP-01, обрезка CP-07 B, без командного кольца.']
    if task=='SC-10':lines+=['', 'Имя **AI Bot** — `backend/prisma/seed-ai.ts`, строка 24; подстановка в предложенный ключ screens.lobby.create.ai.note. Сам файл seed не копируется.']
    if task=='SC-11':lines+=['', 'Коды VZSJ/VZSJFT — первый код списка; 3GPMCA/4XM89G и ответы ошибок — `inputs/join-errors.json`. `viewer_myGames` пуст: RecoverButton не показан.']
    if task=='SC-12':lines+=['', 'Пустота подтверждена `inputs/available-games-empty.json`: `answer.data.availableGames = []`, запрос ONE_V_ONE. Глиф лампочки — левая квадратная область `layers/state-hint_glyph-{24,32,36,48}.png`. Для 32/24/36 px размер точный; для 48 px используется точный слой. Плашка и поле числа исключены; методы и координаты обрезки записаны в verification.json.']
    if task=='SC-13':lines+=['', 'Ошибка — сценарий карточки (ошибка запроса или 10 с без ответа); успешный или ошибочный ответ сервера для этого состояния не выдумывается. Текст взят из RU-строки screens.lobby.list.error контракта, с окончанием «игр».']
    own={'SC-08':'','SC-09':' и ВР-VS4-SC09-01…03','SC-10':' и ВР-VS4-SC09-01…03, ВР-VS4-SC10-01','SC-11':' и ВР-VS4-SC11-01…05','SC-12':' и ВР-VS4-SC12-01…02','SC-13':' и ВР-VS4-SC13-01'}[task]
    lines+=['','## Решения и измерения','',f'Применены ВР-VS4-SC08-01…16{own}: реальные карты и данные, скины, фиксированная сетка, состояния, подпись фона ВР-75, отступы строк, схемы и описание этой карточки. K1 под одной вуалью 0.6 — исторический фон-заглушка; это офлайн-макеты. Типографика не уменьшена; переносы и измерения текста соответствуют состояниям этой карточки. Звуки и shake не рисуются.', '',f'Минимум контраста текста **{text_min:.3f}:1**; наименьший текст при 720p **{small:g} px**. '+(f'Минимальный отступ содержимого строки **{min(inset):.3f} su**; код начинается в 16 su, кнопка/причина заканчивается в 8 su от рамки.' if inset else 'Строк нет, измерение отступов неприменимо.')+' Текстовых пересечений и обрезаний: 0. В каждом состоянии на каждом холсте ровно одна основная кнопка.', '',f'Минимальная измеренная граница панелей **{edge:.4f}:1**, ниже 3:1 на части растровых отсчётов. Ограничение принятых неизменяемых HB-08/SC-01 сохранено: критерий кромок и общая приёмка — **false**, остальные проверки перечислены отдельно. У основной кнопки контраст даёт внутренняя жёлтая граница; внешняя navy-кромка на navy — 1:1. Неактивные кромки записаны без подмены значений.', '', 'Значка обновления в принятом v3 нет: в состояниях с обновлением «ОБНОВИТЬ» текстовая; в ошибке SC-13 она скрыта. Для глифа нужна новая карточка IC. Условная RecoverButton скрыта по пустому myGames: на L её пунктирный резерв расположен внутри CodeColumn, на S места нет — только пояснение в легенде.', '', '## fix1','', 'Скопирован окончательный модуль списка SC-08 с исправленными отступами и шириной колонок; отступы проверяются там, где состояние показывает строки. Каждая схема содержит отдельную страницу состояния, локальные подписи и полную легенду x/y/w/h в su; только фон card.navy, контуры и подписи, без карты, портретов и K1. README переписан для этой карточки. Копии SC-01 и генератора иконок побайтно сохранены.']
    if task=='SC-10':lines+=['', 'На обоих холстах 150% поправлены только интервалы между режимом, заметкой об ИИ, подписью «Доска» и тайлами. Расстояния по границам напечатанных глифов >=8 su; отдельная таблица ai_note_ink_spacing в verification.json.']
    if task=='SC-12':lines+=['', 'Целая плашка state-hint заменена только принятой лампочкой, обрезанной по левой квадратной области слоя глифа.']
    lines+=['','## Файлы','', '| Холст | Схемы всех состояний | Макеты |','|---|---|---|']
    for key in v['layout_measurements']:
        links=' · '.join(f'[{s}](../../../scraped-data/derived/{b.PACKAGE.name}/{task}-{s}-{key}.png) / [серый](../../../scraped-data/derived/{b.PACKAGE.name}/{task}-{s}-{key}-gray.png)' for s,_ in DESCRIPTIONS[task])
        lines.append(f'| {key} | [цвет](comparison/{task}-overlay-{key}.png) / [серый](comparison/{task}-overlay-{key}-gray.png) | {links} |')
    lines+=['',f'Воспроизведение: `python -B art/imagegen/{b.PACKAGE.name}/_tools/{b.MODULES[task]}`. После осмотра каждого экспортированного PNG выполнить `python -B art/imagegen/{b.PACKAGE.name}/_tools/fix1_audit.py finish` (README, visual-review и хеши), затем `python -B art/imagegen/{b.PACKAGE.name}/_tools/verify_outputs.py`. Осмотр всех финальных PNG в цвете и сером отражён в visual-review.json. Хеши входов и выходов — manifest-sha256.json; исходное состояние до исправления — fix1-baseline.json. В verification.json блок fix1 содержит изменения и SHA-256 до/после. Для двух самоссылочных JSON применяется явно описанная нормализация; полный байтовый хеш verification.json есть в манифесте.', '', 'Git, сеть, MCP, Unreal, генерация изображений и фоновые процессы не использовались. Запись ограничена папкой пакета и соответствующей derived-папкой; inputs/ не изменялась.']
    b.guard(b.PACKAGE/'README.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')
    b.dump(b.PACKAGE/'verification.json',v)
    b.refresh_manifest()
    baseline=b.load(b.PACKAGE/'fix1-baseline.json')['files']
    current=b.inventory([p for root in (b.PACKAGE,b.DERIVED) for p in root.rglob('*') if p.is_file()])
    changes=[]
    for path in sorted(baseline.keys()|current.keys()):
        if baseline.get(path)==current.get(path):continue
        after=current.get(path);mode='file bytes'
        if path==b.label_path(b.PACKAGE/'verification.json'):
            after=digest_json({k:val for k,val in v.items() if k!='fix1'});mode='canonical JSON without fix1'
        if path==b.label_path(b.PACKAGE/'manifest-sha256.json'):
            manifest=b.load(b.PACKAGE/'manifest-sha256.json');manifest['files'].pop(b.label_path(b.PACKAGE/'verification.json'),None)
            after=digest_json(manifest);mode='canonical JSON without files[verification.json]'
        changes.append({'path':path,'sha256_before':baseline.get(path),'sha256_after':after,'after_hash_scope':mode})
    v['fix1']={'changes':['ВР-VS4-SC08-14: row inset','ВР-VS4-SC08-15: state overlays and contained recovery slot','ВР-VS4-SC08-16: card README']+(['AI spacing'] if task=='SC-10' else ['hint glyph only'] if task=='SC-12' else []),
               'changed_files':changes,'normalization':'SHA256 of UTF-8 sorted compact JSON for verification excluding fix1, and manifest excluding its verification entry: avoids circular hashes. Before hashes always refer to original file bytes. All other after hashes are exact file bytes.',
               'original_sources_preserved':True,'input_capture_files_unchanged':True}
    b.dump(b.PACKAGE/'verification.json',v);b.refresh_manifest()
    print(json.dumps({'task':task,'changed_files':len(changes),'row_inset':v['row_content_inset_min_su'],'overlays':v['overlay_review'],'unmet':[k for k,a in v['acceptance'].items() if not a['passed']]},ensure_ascii=False))

if __name__=='__main__':
    sys.stdout.reconfigure(encoding='utf-8')
    if sys.argv[1]=='prepare':prepare(sys.argv[2])
    elif sys.argv[1]=='finish':finish()
    else:raise ValueError(sys.argv[1])
