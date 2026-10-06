"""Refresh EN reference chips and technical overlays, independently audit, seal.

Run after build_mockups.py. The manifest is the LAST write. --check is read-only.
"""
from pathlib import Path
import hashlib, json, re, sys
import numpy as np
from PIL import Image
import build_mockups as b
import fix1_audit

def independent(v):
    expected=[];errors=[];gray_bad=[];mode_bad=[];outside_bad=[];state_bad=[]
    for board in b.BG:
        for w,h,ui,s in b.CONFIGS:
            for state in b.STATES:
                expected += [b.OUT/f'HB-42-{board}-{state}-{w}x{h}-{ui}.png',b.OUT/f'HB-42-{board}-{state}-{w}x{h}-{ui}-gray.png']
            for name,folder in [('strip',b.OUT),('contact',b.OUT),('overlay',b.PKG/'comparison')]:
                expected += [folder/f'HB-42-{board}-{name}-{w}x{h}-{ui}.png',folder/f'HB-42-{board}-{name}-{w}x{h}-{ui}-gray.png']
    for state in ['own-0','own-2-why']:
        expected += [b.OUT/f'HB-42-sarpedon-{state}-en-1920x1080-100.png',b.OUT/f'HB-42-sarpedon-{state}-en-1920x1080-100-gray.png']
    for p in expected:
        if not p.is_file():errors.append('Missing '+b.rel(p))
    if errors:return {'passed':False,'errors':errors}
    for i,p in enumerate(expected):
        with Image.open(p) as im:
            if im.mode!='RGBA':mode_bad.append(b.rel(p))
            im.verify()
        if not p.stem.endswith('-gray'):
            gp=p.with_name(p.stem+'-gray.png')
            with Image.open(p) as color,Image.open(gp) as gray:
                if color.size!=gray.size:gray_bad.append(b.rel(p));continue
                for y in range(0,color.height,128):
                    box=(0,y,color.width,min(color.height,y+128));a=np.asarray(color.crop(box).convert('RGB'),float);g=np.asarray(gray.crop(box).convert('RGB'))
                    want=np.rint(a @ np.array([.2126,.7152,.0722])).astype('uint8')
                    if np.any(g!=want[:,:,None]):gray_bad.append(b.rel(p));break
        if i%50==0:print(f'Independent PNG/gray audit {i}/{len(expected)}',flush=True)
    for g in v['geometry']:
        ident=g['id'];w,h=g['resolution'];s=g['su_to_px'];board=g['board'];im=Image.open(b.OUT/(ident+'.png')).convert('RGB');bg=b.base(board,w,h).convert('RGB')
        allowed=np.zeros((h,w),bool)
        for r in [g['ACTIONS']]+g['DECKS']+([g['tooltip']] if g['tooltip'] else []):allowed |= b.rectmask(r,(w,h),s)
        for cell in g['cells']:
            if cell['focus_outer_su']:allowed |= b.rectmask(cell['focus_outer_su'],(w,h),s)
            if cell['caption_su']:
                # Explicitly include measured glyph overflow to distinguish the
                # honest A13 text-fit failure from retouching the board.
                text=next(t for t in v['contrast']['text'] if t['id']==ident and t['string_key']=='hud.action.'+cell['action'])
                x,y,x1,y1=text['ink_bbox_px'];allowed[y:y1,x:x1]=True
        changed=np.any(np.asarray(im)!=np.asarray(bg),axis=2)&~allowed
        n=int(np.count_nonzero(changed))
        if n:outside_bad.append({'id':ident,'outside_documented_HUD_pixels':n})
        # Probe an interior body pixel to confirm the rendered state, separately
        # from the state's JSON declaration and glyph colours.
        for cell in g['cells']:
            a=cell['action'];r=cell['cell_su'];x=round((r[0]+2)*s);y=round((r[1]+r[3]/2)*s)
            look=v['states'][next(st for st in b.STATES if ident.startswith(f'HB-42-{board}-{st}-') and not any(ident.startswith(f'HB-42-{board}-{long}-') for long in b.STATES if long.startswith(st+'-')) )]['buttons'][a]['look']
            token={'available':'navy','disabled':'navy','hover':'hover','selected':'pending','primary':'yellow'}[look]
            alpha=1 if look in ('primary','selected') else .92
            plate=Image.new('RGBA',(1,1),b.rgba(token,alpha));under=bg.crop((x,y,x+1,y+1)).convert('RGBA');want=Image.alpha_composite(under,plate).convert('RGB').getpixel((0,0));got=im.getpixel((x,y))
            if got!=want:state_bad.append({'id':ident,'action':a,'pixel':[x,y],'expected':want,'actual':got})
    before=b.load(b.PKG/'source-hashes-before.json')['files'];before.update(b.load(b.PKG/'_tools/additional-inputs-before.json')['files'])
    input_bad=[name for name in v['input_scope'] if not (b.ROOT/name).is_file() or b.sha(b.ROOT/name)!=before[name]['sha256']]
    snapshot_bad=[]
    for source,name in [('art/imagegen/hud-icons-v3/_tools/draw_icons.py','draw_icons_v3_snapshot.py'),('art/imagegen/hud-composition-v1-codex/_tools/build_mockups.py','hb07_build_mockups_snapshot.py'),('art/imagegen/hud-composition-v1-codex/_tools/layout_reference.py','layout_reference_snapshot.py'),('art/imagegen/hud-hand-v1-codex/_tools/build_mockups.py','hb22_build_mockups_snapshot.py'),('art/imagegen/hud-decks-v1-codex/_tools/build_mockups.py','hb26_build_mockups_snapshot.py')]:
        if b.sha(b.ROOT/source)!=b.sha(b.PKG/'_tools'/name):snapshot_bad.append(name)
    return {'passed':not any([errors,gray_bad,mode_bad,outside_bad,state_bad,input_bad,snapshot_bad]),'required_pngs':len(expected),'all_png_decodes':not errors,'gray_checked_pixelwise':True,'gray_bad':gray_bad,'mode_bad':mode_bad,'outside_documented_HUD':outside_bad,'state_body_pixel_failures':state_bad,'source_sha256_checked':len(v['input_scope']),'source_failures':input_bad,'unchanged_snapshot_failures':snapshot_bad,'errors':errors,'processes_started':0}

def readme(v):
    lines=['# HB-42 — кнопки действий','', '**Статус: предложено.** Корректирующий прогон fix1 выполнен. '+('Все условия пройдены.' if not v['failed_acceptance'] else 'Реальные оставшиеся непройденные измерения приведены ниже и в verification.json.'),'',
    'Сканы карт, аватары, рубашки и иллюстрация доски — только для внутренней LAN-сборки (ВР-48, GAP-019); в git не входят, лежат в scraped-data/derived/hud-actions-v1-codex/.','',
    'Собраны 16 состояний × 2 доски × 4 canvas: **128 цветных и 128 серых макетов**, два EN-кадра с серыми парами, 8 нативных полос состояний и 8 контактных листов с серыми парами, 8 технических overlay с серыми парами. Всего 308 PNG. Ни один законченный HUD, crop полосы или кадр контактного листа не уменьшался. Контактные листы содержат все 16 полноразмерных кадров в сетке 4×4; их размер намеренно велик.','',
    'Рекомендуемый вариант — **accepted-flat / native**: геометрия HB-07, состояния и закрытые кромки HB-08, why-панель HB-22, точные DECKS-чипы HB-26, неизменённые v3 и IC-36 диски. Основание рекомендации: сохранены принятые компоненты, все пересечения с защищёнными областями равны нулю, клавиши не закрывают глифы, серые пары различаются. Дополнительных стилистических вариантов не придумано.','',
    'Marmoreal — только aeafe8f25aea665f с рисованным задником и шестью v2 фигурами. Sarpedon — только bf36d5d6574c7312, lit3d, шесть v2 фигур. Старые подписи клиентского bench («Medusa 16/16», «King Arthur 18/18», Merlin, Harpies 1–3) сохранены как артефакты фона. Они не показывают числа действий и не выдаются за данные состояния кнопок. В 720p только исходный фон пересчитан один раз из 1080p Lanczos.','',
    '## Листы сравнения','']
    for board in b.BG:
        for w,h,ui,s in b.CONFIGS:
            prefix=f'../../../scraped-data/derived/hud-actions-v1-codex/HB-42-{board}'
            suffix=f'{w}x{h}-{ui}'
            lines.append(f'- {board} · {w}×{h}, UI {ui}%: [полоса]({prefix}-strip-{suffix}.png), [серая полоса]({prefix}-strip-{suffix}-gray.png); [все кадры]({prefix}-contact-{suffix}.png), [серые кадры]({prefix}-contact-{suffix}-gray.png); [геометрия](comparison/HB-42-{board}-overlay-{suffix}.png), [серая геометрия](comparison/HB-42-{board}-overlay-{suffix}-gray.png).')
    lines += ['','EN: [own-0](../../../scraped-data/derived/hud-actions-v1-codex/HB-42-sarpedon-own-0-en-1920x1080-100.png), [own-2-why](../../../scraped-data/derived/hud-actions-v1-codex/HB-42-sarpedon-own-2-why-en-1920x1080-100.png); рядом соответствующие `-gray.png`. На EN-проверке также английские чипы Deck 25 / Discard 2: взяты их нативные прямоугольники из принятого HB-26 `opp-en`. Остальная боковая панель этого файла не переносилась. Их дополнительный SHA зафиксирован до первого использования в [_tools/additional-inputs-before.json](_tools/additional-inputs-before.json).','',
    '## Состояния','', '| Файл состояния | Манёвр | Атака | Схема | Конец хода |', '|---|---|---|---|---|']
    labels={'available':'доступна','disabled':'недоступна','selected':'выбрана','hover':'наведение','primary':'главная'}
    for state in b.STATES:lines.append('| '+state+' | '+' | '.join(labels[v['look']] for v in b.state_rules(state)['buttons'].values())+' |')
    lines += ['','В `focus` у манёвра отдельное кольцо; состояние тела остаётся доступным. `own-1` без наведения не экспортируется: ряд совпадает с `own-2`. В `keys` / `keys-own-0` режим подсказок включён, Auto означает только первый матч профиля; это компонентный макет, не реализация сохранения настроек. Class S не имеет подписей под дисками и не имеет чипов поверх дисков. Название и чип появляются в tooltip.','',
    '## Геометрия и источники данных','',
    'Прямоугольники ACTIONS/HAND/HAND-CAPTION/DECKS взяты из принятого HB-07 `own-turn` соответствующей доски и canvas. L: ширины 78/78/78/86 su при высоте 72 su; зазоры 8 su, диск 48 su в (+15,+4) у первых трёх и (+19,+4) у последней ячейки. Ряд по-прежнему 344×72 su. Подпись центрируется по видимому ink-box; общая базовая линия y + 67 su, floor до целого px: 1051 px при 1080p и 698 px при 720p. S: 4 ячейки 48×48 su, зазор 8 su, диск 40 su в (+4,+4); пиксели не изменены. Чипы L 20×20 su с отступами 2 su сверху/справа, кольцо 2 su с внешним зазором 2 su. Общего фона ряда нет. Все прямоугольники, реальные alpha>0 ink-box, базовые линии и font em сохранены в geometry / caption_fit / contrast / key_chips.','',
    '**Дельта 04:** §2.14 «4 кнопки 80×72» → «78/78/78/86 × 72 в классе L»; бюджет подписи диска для «КОНЕЦ ХОДА» → 86 su. Сам файл 04 не менялся. Основание — ВР-VS2-HB42-12…13.','',
    'n=2 и n=1 — примеры правила `ACTIONS_PER_TURN = 2`, model.ts:462,469–471. Сброс: наименьший пример 8−7=1, выбрано 0; executor.ts:285–293 сохраняет ход, actionsRemaining=0 и pendingHandDiscard. Это не счётчики из трасс прогона I. Колода 23/25 и сброс 2 — постоянные принятые компонентные данные HB-26. Реальные источники этих чисел, Feint / Swift Strike и рубашек сохранены в [facts.json](facts.json).','',
    'why-reasons.json: исходная карточка использовала префикс 3c601114097308ff; HB-05 (f0e3080c) добавил экранные причины, текущий файл 9378fa10264bfe50. Пять ключей why.not.your.turn, why.no.actions, why.actions.remaining, why.draft.open, why.discard.count совпадают с текстом задания; аргументы и EN взяты из этого файла. Полные SHA всех входов приведены в [source-hashes-before.json](source-hashes-before.json). Расхождения ожидаемых индивидуальных SHA: '+str(len(v['expected_hash_mismatches']))+'.','',
    'Диски 48/36/60/45 px; hover — округлённые 1,06× размеры 51/38/64/48 px. Существующий размер использован без пересчёта; отсутствующий создан один раз из мастера Lanczos и хранится только в памяти текущего запуска. Никакого пересчёта из рабочего размера или перекраски. Полный список источников — verification.icons. IC-36 end-turn всегда оставляет собственную navy-пластину, даже на жёлтой ячейке.','',
    'Tooltip: radius 4 su, edge 1 su, 16 su по сторонам, 44+24×(число строк−1) su, Regular 16 su, перенос по словам. Низ у ACTIONS.top−8; правый край у наведённой ячейки с учётом поля. Возможное пересечение с DECKS сохранено в transient_overlap и decks_match. Маски — зарегистрированные полигоны HB-07 с запасами 6/15 px при 1080p, масштабируются только с canvas, не UI scale. Ноль пересечений относится именно к этим консервативным маскам; ручной замер не выдаётся за проекцию движка.','',
    '## Проверки A1–A15','', '| Условие | Итог | Как проверено |','|---|---|---|']
    notes={
     'A1':'Верные SHA фонов; ноль изменений вне слоя HUD; старые подписи сохранены.',
     'A2':'Все ячейки, диски, подписи, чипы, кольца и tooltip в geometry/key_chips.',
     'A3':'Точные hex/opacity/radius/edge из HB-08; disabled текст не полупрозрачный.',
     'A4':'Матрица состояний выше и verification.states; локальные attack/scheme переключаемы.',
     'A5':'Правила с файлами и строками в facts.rule_examples; цифры не названы моментом матча.',
     'A6':'As-is или ровно один Lanczos из мастера; источники и SHA в icons.',
     'A7':'Ширина/перенос/высота/якоря и временное перекрытие; figures/spaces=0.',
     'A8':'Чипы 20 su, зазор 8 su у S caption; glyph overlap=0, rim overlap измерен.',
     'A9':'В S только tooltip caption; покой без tooltip.',
     'A10':'Исходные chip ROI совпадают пиксельно; разрешённые tooltip-перекрытия записаны отдельно.',
     'A11':'Никаких видимых заглушек; строки из входов, открытые данные ниже.',
     'A12':'Четыре ячейки, кольцо, чипы и DECKS: FIELD/маски/HAND/HAND-CAPTION=0.',
     'A13':'Нативный 14 su; поля слева/справа ≥2 su и снизу ≥1 su прошли; rest gap ≥3,5 su. Два hover-замера 720p имеют 1,33 su вместо ≥2 su при включении слабого Lanczos-ореола.',
     'A14':'Все 56 пар прошли; измерения отдельно по cell/disc/caption; ring и hover меняют форму.',
     'A15':'Требуемая строка о LAN выше воспроизведена дословно.'}
    for k,n in notes.items():lines.append(f'| {k} | '+('прошло' if v['acceptance'][k]['passed'] else '**не прошло**')+' | '+n+' |')
    f=v['fix1'];ba=f['before_after'];ss=f['class_s_unchanged'];co=v['acceptance']['edges_and_icons']['measured']
    lines += ['','## Исправления fix1','',
    '1. Ячейки L: 80/80/80/80 → 78/78/78/86 su; диски и чипы переставлены по центрам и отступам новых ячеек. Минимальное боковое поле подписи: '+str(round(ba['caption_min_side_free_su']['before'],3))+' → '+str(round(ba['caption_min_side_free_su']['after'],3))+' su; не прошедших боковых полей: '+str(ba['caption_side_failures']['before'])+' → '+str(ba['caption_side_failures']['after'])+'.',
    '2. Общая базовая линия floor((y+67)×px/su). Разброс базовых линий в ряду: '+str(ba['caption_baseline_span_px']['before'])+' → '+str(ba['caption_baseline_span_px']['after'])+' px. Нижнее поле с учётом Ц/Д: минимум '+str(round(ba['caption_bottom_min_su'],3))+' su. Шрифт, кегль, трекинг и строки неизменны. Ink подписей измерен по alpha>0; боковые поля относительно точных su-границ ячейки, нижнее поле от полного нижнего края ink до внутренней стороны кромки. Диск измерен консервативно по всем alpha>0 пикселям, включая слабый Lanczos-ореол: зазоры hover 2 su при 1080p и 1,333 su при 720p (две реальные записи fail).',
    '3. Измерения приведены к ВР-VS2-HB42-14…18: disabled-кромка .16 и диск .4 сохраняют сырые отношения и exempt_inactive=true; rim/plate — только info, rim/cell проверяется. Subpixel edge использует номинальную пару. Не прошедших кромок: 370 → '+str(co['failed_edges'])+'; значков: 244 → '+str(co['failed_icons'])+'. Смесь кромки чипа над inset внесена в palette.derived с формулой: off-token 0,103567 → '+str(v['acceptance']['palette']['measured'])+'. Primary разрешён в own-0 / own-0-why / keys-own-0. Видимые DECKS-пиксели: 0 отличий; покрытые — только transient_overlap. Отсутствие растра курсора сохранено в uncertain_values и не считается провалом.',
    'Класс S: '+str(ss['files'])+' финалов/серых пар/полос/контактных листов; различающихся пикселей **'+str(ss['different_pixels'])+'**, проверены исходные и новые pixel SHA-256. Все 16 технических overlay пересобраны. Дополнительно 32 нативных EN-замера rest/hover на обеих досках при 1080p и 720p выполнены в памяти, без дополнительных финальных PNG; записи находятся в caption_fit (measurement_only) и facts.EN_caption_measurement_probes. Исходные значения — [fix1-before.json](fix1-before.json); доказательства — verification.fix1. prepare.py и повторная фиксация source-hashes-before.json не выполнялись.','',
    '## Непройденные ограничения','']
    for k in v['failed_acceptance']:
        a=v['acceptance'][k];measured={kk:vv for kk,vv in a['measured'].items() if kk!='failures'} if isinstance(a['measured'],dict) else a['measured'];lines.append(f'- **{k}**: измерено `{json.dumps(measured,ensure_ascii=False)}`; ожидается `{a["expected"]}`. {a["note"]}')
    if not v['failed_acceptance']:lines.append('Нет.')
    if co['failed_icons']:lines += ['', 'Сохранённый cream-rim диска КОНЕЦ ХОДА на primary-жёлтой ячейке имеет rim/cell '+str(round(co['enabled_icon_rim_cell_min'],3))+':1 вместо 3:1. Глиф к собственной navy-пластине проходит. Перекраска диска или ячейки не разрешена fix1; все '+str(co['failed_icons'])+' экземпляров с числами перечислены в contrast.icons и acceptance.edges_and_icons.measured.failures.']
    lines += ['',
    '## Открытые данные','',
    'Курсор не рисуется в HB-42: это область IC-58…IC-61 (ВР-46, ВР-VS2-HB08-05; ВР-VS2-HB42-18). Мышь в состояниях — логическая наведённая ячейка (states.pointer_button), tooltip и hover-облик; `focus` не имеет pointer. Отсутствие растра сохранено в uncertain_values, но не является failed acceptance. Не добавлялся условный заменитель и не добавлялись новые игровые данные.','',
    '## Изоляция и воспроизведение','',
    'Все пять generator/reference snapshots скопированы побайтно; они не исполняются. ImageGen не вызван, generation-records.json содержит пустой журнал; concepts/ пуст. Рендер использует Pillow для текстов/PNG и pycairo для нативного покрытия геометрии с точными дробными su. Внутренний Python audit hook запрещает запись вне двух разрешённых корней и запуск дочерних процессов. Git, файлы unreal/, Editor, UBT и упаковка не использовались. Фоновый сервис не запускался.','',
    'Начальный SHA-инвентарь консервативно захватил также весь упомянутый общий art/imagegen/. Это включает пакеты других параллельных задач, которые не являются входами HB-42. Все настоящие входы HB-42 и полные деревья шести принятых пакетов проверены отдельно: source_unchanged='+str(v['source_unchanged']).lower()+'. Изменения посторонних пакетов перечислены с исходными/текущими SHA в observed_non_input_changes; они не скрыты и не приписаны этому запуску. Посторонние файлы не исправлялись и не откатывались.','',
    'Команды воспроизведения fix1 из корня проекта. prepare.py повторно запускать запрещено; fix1-before.json не перезаписывать:','',
    '```powershell','python -B -X utf8 art/imagegen/hud-actions-v1-codex/_tools/build_mockups.py','python -B -X utf8 art/imagegen/hud-actions-v1-codex/_tools/finalize.py','python -B -X utf8 art/imagegen/hud-actions-v1-codex/_tools/finalize.py --check','```','',
    'build_mockups.py создаёт все состояния и листы; finalize.py обновляет EN-чипы/контуры, независимо читает PNG и проверяет серые пиксели, входы и state-body pixels, пишет отчёт и README, затем **последней операцией записи** manifest-sha256.json. `--check` ничего не пишет. [verification.json](verification.json) содержит все непрошедшие условия; [manifest-sha256.json](manifest-sha256.json) охватывает обе разрешённые папки, исключая себя.','',
    '## Язык листов','',
    'Печатный жетон задаёт форму: четыре самостоятельные высечки образуют ряд, а свободные промежутки оставляют сцену видимой. Геометрическая точность и аккуратное нативное покрытие служат главным средством качества.','',
    'Цвет использует уже принятые роли: navy удерживает основу, бирюза отмечает выбор, жёлтая ячейка ведёт к завершению хода. Диск сохраняет собственную печать; состояние читается также по яркости и контуру.','',
    'Масштаб меняет плотность информации: подпись остаётся под диском в L и переходит в отдельную подсказку в S. Ритм восьми su и точная работа с полями соединяют ряд с окружением.','',
    'Контактные листы показывают повторение одной системы, без новых украшений. Подпись каждого состояния и технические контуры дают проверяемую структуру; качество выражено сохранением принятых решений и явным учётом ограничений.','']
    if v['source_changed_paths'] or v['expected_hash_mismatches']:
        lines += ['## Изменившиеся входы','',json.dumps({'source_changed_paths':v['source_changed_paths'],'expected_hash_mismatches':v['expected_hash_mismatches']},ensure_ascii=False,indent=2),'']
    b.guard(b.PKG/'README.md').write_text('\n'.join(lines),encoding='utf-8')

def refresh():
    v=b.load(b.PKG/'verification.json');facts=b.load(b.PKG/'facts.json');old_en={g['id'] for g in v['geometry'] if '-en-' in g['id']};new=[]
    for state in ['own-0','own-2-why']:
        _,r,_=b.render('sarpedon',state,1920,1080,100,1.,'en');new.append(r)
    mapping={'geometry':'geometry','overlap':'overlap','decks_match':'decks_match','caption_fit':'caption_fit','key_chips':'key_chips','transient_overlap':'tooltip','background_checks':'background'}
    for key in mapping:
        v[key]=[x for x in v[key] if x['id'] not in old_en and not x.get('measurement_only')]
        for r in new:
            if key=='geometry':v[key].append(r['geometry'])
            elif key=='transient_overlap':
                if r['tooltip']:v[key].append(r['tooltip'])
            elif key=='background_checks':v[key].append({'id':r['geometry']['id'],'outside_hud_different_pixels':r['outside_hud_different_pixels']})
            else:v[key].extend(r[key])
    for key,rr in [('text','texts'),('edges','edges'),('icons','icon_contrast')]:
        v['contrast'][key]=[x for x in v['contrast'][key] if x['id'] not in old_en]
        for r in new:v['contrast'][key].extend(dict(t,id=r['geometry']['id']) for t in r[rr])
    v['palette']['per_mockup']=[x for x in v['palette']['per_mockup'] if x['id'] not in old_en]+[r['palette'] for r in new]
    v['palette']['derived']=list({d['hex']:d for p in v['palette']['per_mockup'] for d in p['derived']}.values())
    v['palette']['method']='Opaque HUD pixels checked against exact tokens plus derived translucent edge / own token body mixtures (ВР-VS2-HB42-15); all other off-token pixels counted. Background, scans, card backs, icons and antialias coverage excluded.'
    for r in new:facts['rendered_text'][r['geometry']['id']]=r['texts']
    en_fit,en_texts=fix1_audit.english_probes()
    v['caption_fit'].extend(en_fit);facts['EN_caption_measurement_probes']=en_texts
    facts['decks']['EN_reference']='scraped-data/derived/hud-decks-v1-codex/HB-26-sarpedon-opp-en-1920x1080-100.png; only two DECKS rectangles, same owner counts; accepted EN labels / card scan'
    facts['decks']['EN_hash_before']='_tools/additional-inputs-before.json'
    for board in b.BG:
        for w,h,ui,s in b.CONFIGS:
            group=[]
            for g in v['geometry']:
                if g['board']==board and g['resolution']==[w,h] and g['ui_scale_percent']==ui and '-en-' not in g['id']:
                    group.append({'geometry':g,'tooltip':next((t for t in v['transient_overlap'] if t['id']==g['id']),None),'key_chips':[k for k in v['key_chips'] if k['id']==g['id']]})
            b.overlay(board,w,h,ui,s,group)
    changed,mismatches,observed=b.provenance();v['source_unchanged']=not changed;v['source_changed_paths']=changed;v['observed_non_input_changes']=observed;v['expected_hash_mismatches']=mismatches
    before=b.load(b.PKG/'source-hashes-before.json')['files'];before.update(b.load(b.PKG/'_tools/additional-inputs-before.json')['files'])
    named=set(re.findall(r'`([^`]+)`',(b.ROOT/'docs/game-design/visual/06-tasks/prompts/HB-42.codex.md').read_text('utf-8').split('## Warnings')[0]));dirs=[p.rstrip('/')+'/' for p in named if '/' in p and p!='art/imagegen/' and (b.ROOT/p).is_dir()]
    dirs+=['art/imagegen/'+n+'/' for n in ['hud-icons-v3','hud-icons-vr44-codex','hud-composition-v1-codex','hud-skins-v1-codex','hud-hand-v1-codex','hud-decks-v1-codex']]
    v['input_scope']=sorted(n for n in before if n in named or any(n.startswith(p) for p in dirs) or n.startswith(('scraped-data/','C:/Program Files/')) or n=='docs/game-design/visual/06-tasks/prompts/HB-42.codex.md')
    v['source_files_checked']=len(v['input_scope']);v['inventory_files_recorded']=len(before)
    v['exports']=b.export_audit();v['independent_verification']=independent(v)
    v['uncertain_values']=[{'what':'Raster of the mouse cursor','where':'The pointer target in hover / -why / key states','why_missing':'No cursor asset in allowed inputs; no new icons permitted. Logical pointed cell, tooltip and hover state are present; a new cursor was not invented.'}]
    v['visual_review']={'method':'Opened original two backgrounds and actual PNGs, then native strips/gray/overlay at the end','checked':'painted Marmoreal, lit3d Sarpedon, six v2 figures, correctly selected/disabled/primary/key states, captions and tooltip geometry','note':'Small bench labels preserved. No new placeholder art, no new cursor.'}
    facts['fix1']={'prompt':'docs/game-design/visual/06-tasks/prompts/HB-42.fix1.codex.md','cell_widths_L_su':[78,78,78,86],'caption_baseline_su':'cell.y + 67','caption_baseline_px':'floor((cell.y + 67) * su_to_px)','caption_alignment':'center alpha>0 ink horizontally in exact su cell; never alter font, string or tracking','delta_04':'§2.14 78/78/78/86 x 72 in class L; disc caption end-turn budget 86 su','decisions':['ВР-VS2-HB42-'+str(i) for i in range(12,19)]}
    facts['geometry_sources']['L_cells_and_caption_baseline']='HB-42.fix1.codex.md; ВР-VS2-HB42-12…13 supersede original four 80x72 cells / individual ink centering.'
    b.save(b.PKG/'facts.json',facts)
    v['acceptance']=b.acceptance(v)
    v['acceptance']['independent_verification']={'passed':v['independent_verification']['passed'],'measured':v['independent_verification'],'expected':'All exports readable, exact grayscale, inputs immutable, actual skin state pixels correct','note':'Separate audit reads saved images; it does not trust the renderer claims.'}
    v['acceptance']['pointer_cursor_raster']={'passed':True,'measured':'Logical pointer target, no cursor raster','expected':'No cursor in HB-42; pointed button represented by state / tooltip','note':'ВР-VS2-HB42-18: cursors belong to IC-58…IC-61; uncertain_values retained.'}
    v['fix1']=fix1_audit.audit(v)
    for name,result in [('class_s_unchanged',v['fix1']['class_s_unchanged']),('caption_pixel_audit',v['fix1']['caption_pixel_audit'])]:
        v['acceptance'][name]={'passed':result['passed'],'measured':{k:val for k,val in result.items() if k!='per_file'},'expected':'No changed S pixels' if name=='class_s_unchanged' else 'Common baseline and rendered caption ink agree with measurements','note':'Read-only independent fix1 audit; original snapshot preserved.'}
    v['acceptance']['source_inventory_preserved']={'passed':v['fix1']['source_inventory_preserved'],'measured':v['fix1']['source_inventory_preserved'],'expected':True,'note':'Original source-hashes-before.json digest matches fix1-before.json.'}
    v['fix1']['before_after']['acceptance_failed_after']=[k for k,a in v['acceptance'].items() if not a['passed']]
    v['failed_acceptance']=[k for k,a in v['acceptance'].items() if not a['passed']]
    readme(v)
    v['write_audit']['paths']=sorted(set(v['write_audit']['paths'])|b.WRITES|{b.rel(b.PKG/'verification.json'),b.rel(b.PKG/'manifest-sha256.json')})
    # Account for README, verification and manifest size before sealing. The
    # measured package byte count excludes only the manifest not yet written.
    b.save(b.PKG/'verification.json',v)
    v['sizes']['package_bytes']=sum(p.stat().st_size for p in b.PKG.rglob('*') if p.is_file() and p.name!='manifest-sha256.json')
    v['acceptance']['package_size']['measured']=v['sizes']['package_bytes'];b.save(b.PKG/'verification.json',v)
    files={b.rel(p):{'sha256':b.sha(p),'bytes':p.stat().st_size} for root in [b.PKG,b.OUT] for p in sorted(root.rglob('*')) if p.is_file() and p!=b.PKG/'manifest-sha256.json'}
    # This is the final write. The subsequent check is read-only.
    b.save(b.PKG/'manifest-sha256.json',{'schema':'HB-42.manifest/1','algorithm':'sha256','self_excluded':True,'roots':[b.rel(b.PKG),b.rel(b.OUT)],'files':files})
    print('Sealed manifest: '+str(len(files))+' files; failed acceptance: '+', '.join(v['failed_acceptance']),flush=True)

def check():
    manifest=b.load(b.PKG/'manifest-sha256.json');bad=[]
    for name,v in manifest['files'].items():
        p=b.ROOT/name
        if not p.is_file() or b.sha(p)!=v['sha256'] or p.stat().st_size!=v['bytes']:bad.append(name)
    actual={b.rel(p) for root in [b.PKG,b.OUT] for p in root.rglob('*') if p.is_file() and p!=b.PKG/'manifest-sha256.json'}
    extras=sorted(actual^set(manifest['files']));v=b.load(b.PKG/'verification.json');changed,_,observed=b.provenance()
    report={'manifest_files':len(manifest['files']),'manifest_mismatches':bad,'manifest_membership_difference':extras,'input_changes':changed,'source_unchanged':not changed,'independent_verified':v['independent_verification']['passed'],'PNG_count':len(v['exports']),'package_bytes_including_manifest':sum(p.stat().st_size for p in b.PKG.rglob('*') if p.is_file()),'derived_bytes':sum(p.stat().st_size for p in b.OUT.rglob('*') if p.is_file()),'failed_acceptance':v['failed_acceptance'],'writes_after_manifest':0}
    print(json.dumps(report,ensure_ascii=False,indent=2))
    if bad or extras or changed or not v['independent_verification']['passed']:raise SystemExit(1)

if __name__=='__main__':
    if '--check' in sys.argv:check()
    else:refresh()
