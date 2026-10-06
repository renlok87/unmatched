#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Generate the Russian review document from final measured facts; package-only write."""
import json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[4]
PKG=ROOT/'art/imagegen/hud-decks-v1-codex'
def load(n):return json.loads((PKG/n).read_text('utf8'))
def fmt(r):return '['+', '.join(f'{x:.3f}'.rstrip('0').rstrip('.') for x in r)+']'

def main():
    facts=load('facts.json');v=load('verification.json')
    links=[];delta=[];headers=[];transient=[]
    for board in ['marmoreal','sarpedon']:
        for w,h,ui in [(1920,1080,100),(1920,1080,150),(1280,720,100),(1280,720,150)]:
            stem=f'HB-26-{board}';suffix=f'{w}x{h}-{ui}'
            links.append(f'| {board} · {w}×{h} · {ui}% | [Цвет](../../../scraped-data/derived/hud-decks-v1-codex/{stem}-contact-{suffix}.png) · [Серый](../../../scraped-data/derived/hud-decks-v1-codex/{stem}-contact-{suffix}-gray.png) | [Геометрия](comparison/{stem}-overlay-{suffix}.png) · [Серый](comparison/{stem}-overlay-{suffix}-gray.png) |')
            o=next(o for o in facts['rendered_outputs'] if o['board']==board and o['resolution']==[w,h] and o['ui_scale_percent']==ui and o['state']=='own' and o['language']=='ru')
            p=o['panel_geometry'];cl=o['class'];label=f'{board} · {w}×{h}/{ui}% · {cl}'
            delta.append(f'| DECK PANEL | {label} | {fmt(p["rectangle_su"])} | D5: правый край −{16 if cl=="S" else 24} su, низ DECKS −8 su; верх по принятому HB-07. |')
            for chip in ['CHIP-0','CHIP-1']:delta.append(f'| {chip} | {label} | {fmt(o["rectangles_su"][chip])} | Внутри принятого DECKS; зазор 8 su; геометрия fix1. |')
            for chip in o['chip_geometry']:
                delta.append(f'| MINI-{chip["chip"]} / TEXT-{chip["chip"]} | {label} | {fmt(chip["mini_box_su"])} / {fmt(chip["text_box_su"])} | Отступы слева/справа {chip["left_padding_su"]:g}/{chip["right_padding_su"]:g} su, зазор мини → текст {chip["mini_to_text_gap_su"]:g} su. |')
            for side in ['own','opp']:
                z=next(z for z in v['panel_geometry'] if z['id']==f'HB-26-{board}-{side}-{w}x{h}-{ui}')
                headers.append(f'| {label} | {side} | {z["header_height_su"]:.1f} | {z["viewport_height_su"]} | {z["rows_visible"]}/{z["total_rows"]} | {z["title_size_su"]} · {len(z["title_lines"])} |')
            z=next((z for z in v['transient_overlap'] if z['id']==o['id']),None)
            if z:
                e=z['elements']['DECKPANEL'];transient.append(f'| {label} | {e["figure_overlap_px2"]} | {e["space_overlap_px2"]} | {e["blocks_overlap_px2"].get("OPP-HAND",0)} | 0 |')
    checks=[]
    descriptions={
     'D1':'Два разрешённых bench-фона; пиксели вне HUD равны исходному фону. Старые подписи оставлены.',
     'D2':'Моменты seq 12/13, свежие и stale-счётчики, пометки и два явно описанных вывода; суммы полной модели.',
     'D3':'27 уникальных карт сверены с API и БД; строки 48 su, диски v3 24 su, copies/value/boost без подмены.',
     'D4':'Для каждой карты каждой панели измерен весь бюджет имени: 20 → 16 → …; иной текст не сокращён.',
     'D5':'Прямоугольники fix1: L720 ширина 336 su, остальные сохранены; перенос только после ·, имя героя целиком; viewport кратен 48.',
     'D6':'L RU: 156/124×56, EN: 144/136×56; S: 64×48; отступы/зазоры 8 su в L, 4 su в S; реальные числа 20 su.',
     'D7':'Вкладка соперника: только публичный сброс; рука — рубашки, нет приватных пометок и порядка добора.',
     'D8':'Все постоянные панели/фишки: 0 px² с фигурами, клетками с запасом и видимыми блоками; временные S-пересечения записаны.',
     'D9':'Открытых неизвестных значений нет; запрещённого placeholder на финалах нет.',
     'D10':'Текст и геометрия растеризованы нативно на всех четырёх холстах, HUD не масштабировался.',
     'D11':'У каждого финала есть Rec.709 gray; выбранные состояния и ≈ различаются в сером.',
     'D12':'Правовая строка ниже воспроизведена дословно; все изображения с заимствованной графикой в derived.',
     'D13':'Хеши входов, прозрачный слой/палитра, PNG-инвентарь, write-guard, acceptance и финальный манифест.',
     'D14':'Два EN-финала opp/opp-end для Sarpedon 1080p100 и их серые версии.'}
    for k,d in descriptions.items():checks.append(f'| {k} | {"Пройдено" if v["acceptance"][k]["passed"] else "НЕ пройдено"} | {d} |')
    for o in facts['rendered_outputs']:
        if o['language']!='en' or o['state']!='opp':continue
        label='sarpedon · 1920×1080/100% · L · EN'
        for chip in o['chip_geometry']:
            delta.append(f'| CHIP-{chip["chip"]} | {label} | {fmt(chip["rectangle_su"])} | Внутри DECKS; EN-ширина; зазор 8 su. |')
            delta.append(f'| MINI-{chip["chip"]} / TEXT-{chip["chip"]} | {label} | {fmt(chip["mini_box_su"])} / {fmt(chip["text_box_su"])} | Отступы 8/8 su, зазор мини → текст 8 su. |')
    ellipses=[n for n in v['name_fit'] if n['ellipsis']]
    unique=sorted({(n['displayed_name'],n['shown'],n['size_su'],n['id'].split('-')[-2],n['id'].split('-')[-1]) for n in ellipses})
    etable='\n'.join(f'| {full} | {shown} | {size} | {res}/{ui}% |' for full,shown,size,res,ui in unique)
    text=f'''# HB-26 · колода и сброс

Статус: **предложено**. Пакет подготовлен для ревью, художественная или интеграционная приёмка этим статусом не заявляется. Git и `unreal/` не использовались. Запись ограничена этим пакетом и `scraped-data/derived/hud-decks-v1-codex/`.

Полный набор: **56 RU-финалов + 56 gray**, **2 EN-финала + 2 gray**, 8 цветных и 8 серых contact sheets, 8 цветных и 8 серых overlay sheets без сканов. Финалы и contact sheets лежат в derived, в пакете — скрипты, неизменённые снимки исходных генераторов, JSON-аудит и геометрические листы. ImageGen не вызывался; [generation-records.json](generation-records.json) содержит пустой журнал, `concepts/` пустая.

## Рекомендация и результат D8

Рекомендую вариант с пятью исправлениями fix1 и стилем принятого HB-08. Он сохраняет реальные данные, разделение своей/чужой колоды и единый ритм строки на всех холстах.

**D8 пройден на всех холстах класса L**: на 1280×720 UI 100% обе панели имеют прямоугольник `{fmt(next(z["rectangle_su"] for z in v["panel_geometry"] if z["id"]=="HB-26-sarpedon-own-1280x720-100"))}`. Пересечение Sarpedon с запасами S15/S27 уменьшилось с **61 до 0 px²**. Все постоянные панели и фишки дают **0 px²** с фигурами, клетками с зарегистрированными запасами и видимыми блоками HB-07.

Ширина **336 su**, названная в задании fix1, применена к финалам на обеих досках. Точная дополнительная проверка выявила неточность исходного утверждения о максимуме: **337–339 su также дают 0 px²** при округлении прямоугольника в пиксели, а исходные **340 su дают 61 px²** на Sarpedon. Сохранён прямо указанный в fix1 вариант 336 su; он не объявляется абсолютным максимумом. `panel_width_probe` содержит все пять ширин для обеих досок. Панели класса S и 1080p, маски, фон и правые якоря сохранены; временные пересечения S по-прежнему записаны в `transient_overlap`.

## Исправления fix1

Исходные значения и измерения до правки сохранены в [fix1-before.json](fix1-before.json), первоначальный `source-hashes-before.json` не заменён.

1. L720: `[1342.667, 268, 340, 524]` → `[1346.667, 268, 336, 524]` на обеих досках; правое поле 24 su и низ DECKS −8 su сохранены, D8 **61 → 0 px²**.
2. Заголовки: «… · King» / «Arthur» → «… ·» / «King Arthur». Сначала одна строка 28 su, иначе перенос только после разделителя; при необходимости 28 → 24 su. Правило одинаково для RU/EN; шапка и целый viewport пересчитаны по числу строк.
3. Фишки L: **140/140 → 156/124 su (RU), 144/136 su (EN)** при общей ширине 288 su с зазором 8 su; отступы слева/справа **3/3 → 8/8 su**, зазор после мини **2 → 8 su**, мини 32×45 su. S: 64×48 su сохранены; мини **22×32 → 18×25.3125 su**, отступы **3/3 → 4/4 su**, зазор **2 → 4 su**, число 20 su. Внешняя кромка мини включена в отступы. Для EN нужны иные ширины: RU «Колода ≈24» требует 98 su текста, EN «Discard 2» — до 76 su; одна общая пара с полными отступами потребовала бы 286 su вместо доступных 280. Адаптация ширин по языку сохраняет весь DECKS и текст без уменьшения. EN-прямоугольники и внутренние боксы также записаны ниже.
4. Вкладки: зазор L **4 → 8 su**, S **4 → 4 su**; закрытие остаётся у правого края.
5. Названия 16 su: прежний верх +3 su → общая базовая линия первой строки с ×N и значениями. Использован baseline-anchor `ls`; измерения каждой видимой строки есть в `fix1_name_baselines`, бюджет всех имён заново измерен в `name_fit`.

## Листы для просмотра

Contact sheets содержат семь полных кадров в ряд: chips, chips-stale, own, own-end, own-discard, opp, opp-end. Размер 13440×1116 для 1080p и 8960×756 для 720p; при проверке мелкого текста открывать в 100%, а не полагаться на уменьшенный preview.

| Доска и холст | Финалы, 7 состояний | Без сканов: HUD, блоки HB-07, маски, якоря |
|---|---|---|
{chr(10).join(links)}

EN: [opp](../../../scraped-data/derived/hud-decks-v1-codex/HB-26-sarpedon-opp-en-1920x1080-100.png), [opp-end](../../../scraped-data/derived/hud-decks-v1-codex/HB-26-sarpedon-opp-end-en-1920x1080-100.png), [opp gray](../../../scraped-data/derived/hud-decks-v1-codex/HB-26-sarpedon-opp-en-1920x1080-100-gray.png), [opp-end gray](../../../scraped-data/derived/hud-decks-v1-codex/HB-26-sarpedon-opp-end-en-1920x1080-100-gray.png).

Дополнительно: [нативные кропы fix1](../../../scraped-data/derived/hud-decks-v1-codex/fix1-review/) — все семь состояний на каждом холсте в цвете и сером, отдельно обе EN-панели. Кропы собраны без масштабирования и просмотрены после исправлений.

## Визуальные принципы и небольшие решения

Плоская печать держится на спокойном navy, постоянной тонкой кромке и ясной типографике. Ни тени, ни текстуры, ни блики не отвлекают от состава колоды; геометрия выверена в su и проверена в пикселях.

Ритм 48 su отделяет карты, а две строки разделяют название и состояние экземпляров. Внимательная расстановка оставляет место диску типа, числу копий и значениям; полное название сохраняется в данных для инспектора.

Форма и текст несут смысл раньше цвета: типы используют существующие v3-глифы, stale обозначается знаком ≈. Выбранные вкладки и фильтр отличаются светлой сплошной кромкой и яркостью тела; серые пары проверены численно.

Чёткая нативная растеризация важнее декоративных добавлений. На 720p учитываются ceil-размер шрифта, ширина каждого слова и высота глифа; окончательная проверка включает просмотр самих PNG.

- Кнопки используют радиус 4 su и состояния HB-08: Normal navy α0,92 / cream α0,45; Selected pending α1 / glyph α1. Панель — радиус 6 su, внутренний отступ 12 su, без blur/shadow/gradient. Геометрия снимков HB-08 в файлах x1/x2 используется как норматив процедурных элементов, готовые 9-slice PNG не масштабируются в HUD.
- Вкладки имеют горизонтальный внутренний отступ 6 su, промежуток **8 su в L / 4 su в S**; закрытие закреплено справа. Все строки остаются 20 su.
- В L внешняя кромка мини начинается через 8 su, само изображение через 9 su, текст через 50 su. В S внешняя кромка начинается через 4 su, мини 18×25.3125 su, текст через 28 su; число 20 su и префикс ≈ помещаются целиком.
- Кромка мини-карты рисуется **снаружи** контейнера скана на собственной navy-подложке 1 su. Скан целиком вписан в 32×45 su (L), ресемплинг — один Lanczos из оригинала, без обрезки.
- Строка: общая базовая линия copies/name/values вычисляется из верхнего отступа +3 su для 20 su; уменьшенное имя 16 su стоит на ней же. Пометки +29 su используют прежние navy-тело и cream-кромку.
- Viewport содержит целое число строк 48 su; оставшаяся высота — свободный отступ снизу. Ползунок: трек 4 su cream α0,16, thumb cream α0,45, radius 2 su. В own-discard две непустые строки, scrollbar не нужен.
- Ни один полный список не помещается целиком в своём viewport: все own-end/opp-end отличаются от top и заканчиваются последней строкой. При фильтре и прокрутке суммы видимых строк не равны сводке полной колоды; `sums` проверяет **полную модель до фильтра/viewport**, отдельно для каждого момента. На чужой стороне приватные суммы по картам намеренно не вычисляются.
- Числа Roboto Bold Condensed табличные: проверены одинаковые advance 0–9. Текст строк и счётчиков остаётся runtime-текстом в описании реализации; PNG — статический макет, не импортируемая текстура с надписями.
- 24, 36 и 18 px type discs берутся из готовых sizes v3 без изменения; 27 px для 720p/150% — один Lanczos из v3 master с кэшем. Новый глиф не рисуется; snapshot `draw_icons_v3_snapshot.py` не исполняется.
- K / Shift+K, клик по фишке или портрету открывают предусмотренную панель; закрытие при требовании игрового ввода относится к будущей реализации по 04 §2.9. Этот пакет содержит статические макеты.

## Данные и приватность

Сведения о каждой карте, строке и написанном тексте — [facts.json](facts.json). Полные хеши до работы — [source-hashes-before.json](source-hashes-before.json); проверка неизменности всех входов и `hud-icons-v3/**` — [verification.json](verification.json); итоговая инвентаризация двух папок — [manifest-sha256.json](manifest-sha256.json).

| Доска | Момент | Своя колода / сброс / рука | Соперник | Stale | Верх своего сброса |
|---|---|---|---|---|---|
| Marmoreal | host seq 12, строки 1400/1409 | Medusa: 23 / 2 / 5 | King Arthur: 24 / 1 / 5 | host строка 1297, ≈24 / 2 | Feint |
| Sarpedon | joiner seq 13, строки 1186/1196/1288 | King Arthur: 25 / 2 / 3 | Medusa: **22** / 2 / 6 | joiner строка 1364, ≈25 / 2 | Swift Strike |

Своя Medusa: в руке Gaze of Stone×2, Snipe×1, Clutching Claws×1, Dash×1; сброс A Momentary Glance×1 и Feint×1. Свой King Arthur: Noble Sacrifice×1, Swift Strike×1, The Holy Grail×1; сброс Swift Strike×1, Momentous Shift×1. Публичный чужой сброс: Swift Strike×1 на Marmoreal; Dash×1, Regroup×1 на Sarpedon. Свой остаток: copies − hand − discard, включая нули.

Feint в сбросе — заданный вывод по host строке 1286, d=2; это единственная **пригодная для защиты** карта Medusa с value=2. Gaze of Stone тоже имеет value=2, но attack-only и не подходит к этой защите. Кадр host s09-turn-banner прямо подтверждает Feint. Regroup — заданный вывод по joiner строке 1172: Swift Strike A3 без усиления, damage=2 ⇒ защита 1, у Medusa единственный пригодный вариант Regroup. Все основания и тип `inference` записаны явно.

Сортировка: attack → defense → versatile → scheme, затем Unicode-order casefold отображаемого имени. RU Medusa — i18n.ru.title; RU King Arthur — i18n.ru.title для Feint/Regroup, иначе фактическое Card.nameRu из БД, равное EN. Заголовки используют фактические Hero.nameRu **Medusa** и **King Arthur**. Список не показывает порядок добора; чужая рука — только n рубашек нужного героя высотой 24 su, чужие строки — только публичное «В сбросе n». Общие copies оригинальной колоды не выдаются за текущий остаток чужой колоды.

## Дельта 04

Прямоугольники ниже в su, формат `[x,y,w,h]`. Это требуемая адаптация 04 к **принятому HB-07 own-turn**, а не произвольное перемещение иных блоков. DECKS сохранён без изменения; top L = max(248, OPP-HAND.bottom+8)=268; top S=PANEL-OPP.bottom+8=120. Таблица содержит каждую панель и обе фишки на обоих фонах/четырёх холстах.

| Блок | Доска, холст, UI | Итоговый прямоугольник | Основание |
|---|---|---|---|
{chr(10).join(delta)}

| Холст | Вкладка | Шапка, su | Viewport, su | Видно / уникальных | Заголовок: su · строк |
|---|---|---|---|---|---|
{chr(10).join(headers)}

own-end/opp-end используют ту же шапку и viewport, начальный индекс `total−visible`; own-discard — та же геометрия own, две строки с discard>0. EN-шапка/viewport отдельно записаны в `panel_geometry`.

## Пересечения S, временная панель

Числа ниже — одинаковые для own, own-end, own-discard, opp, opp-end. Измерение прямоугольника консервативное, включает запас клеток 15 px и фигур 6 px при 1080p (масштабируется device scale, не UI scale). Панель S временно перекрывает OPP-HAND и край поля по исключению 04 §1.6. Защищённые PANEL-OPP, DECKS, ACTIONS, HAND остаются свободными. Фишки на всех холстах: **0 px²** со всеми масками и блоками.

| Холст | Фигуры, px² | Клетки с запасом, px² | OPP-HAND, px² | Защищённые блоки, px² |
|---|---|---|---|---|
{chr(10).join(transient)}

## Бюджет имён

`name_fit` содержит {len(v['name_fit'])} измерений **всех строк модели**, включая строки за прокруткой и скрытые фильтром. Ширина берётся по реальному растровому размеру Roboto, а не по числу символов. Полное имя сохранено для инспектора; никаких иных сокращений нет. The Hounds of Mighty Zeus упражняет английский бюджет в обеих EN-проверках.

| Полное имя | Показано | su | Холст/UI |
|---|---|---|---|
{etable}

## Самопроверка D1–D14

| Требование | Результат | Проверка |
|---|---|---|
{chr(10).join(checks)}

Минимальный контраст текста: **{v['contrast']['text_min']:.4f}:1** (≥4,5); минимальная кромка к собственному телу: **{v['contrast']['edge_vs_body_min']:.4f}:1** (≥3). Глифы v3 к собственной type plate проверены отдельно; пиксели чужого скана не используются как фон этой нормативной пары. Минимальный номинальный текст 720p: **{v['min_text_px_720p']['nominal_px']} px**, растровый em округлён вверх. `palette.fraction={v['palette']['fraction']}` на HUD-only RGBA с исключением исходной графики, кромок/разделителей и частичного покрытия антиалиасинга. Пиксели непрозрачной печати проверяются по **точному** hex, строже допуска ΔE≤3.

## Фоновые артефакты и открытые данные

Оба фоновых кадра просмотрены: реальная Marmoreal original с рисованной вклейкой и Sarpedon original lit3d, шесть готовых v2 фигур на каждом. Старые мелкие подписи **Medusa 16/16, King Arthur 18/18, Merlin, Harpies 1–3** оставлены в кадре неизменёнными по D1; это артефакты bench-фона, а не актуальные HP или HUD из момента run I. Позиции bench-фигур тоже не выдаются за позиции run I. На некоторых краях видны старые технические уголки; они не ретушируются. Запрещённый P5c фон не использован.

Неизвестных значений, требующих пустого элемента, нет: `uncertain_values=[]`. Имена King Arthur на английском в RU-макетах — проверенные данные БД, а не отсутствующий перевод. Два вывода по сбросу описаны выше; фон не является источником match-счётчиков. Хеши именованных входов сопоставляются с карточкой, любые отклонения перечисляются в `expected_hash_mismatches`, а не принимаются молча.

Сканы карт, аватары, рубашки и иллюстрация доски — только для внутренней LAN-сборки (ВР-48, GAP-019); в git не входят, лежат в scraped-data/derived/hud-decks-v1-codex/.

## Воспроизведение и порядок завершения

```powershell
python -B -X utf8 art/imagegen/hud-decks-v1-codex/_tools/build_mockups.py
python -B -X utf8 art/imagegen/hud-decks-v1-codex/_tools/review_crops.py
python -B -X utf8 art/imagegen/hud-decks-v1-codex/_tools/write_readme.py
python -B -X utf8 art/imagegen/hud-decks-v1-codex/_tools/verify_package.py --finalize
python -B -X utf8 art/imagegen/hud-decks-v1-codex/_tools/verify_package.py --check
```

Первоначальный `source-hashes-before.json` сохраняется: повторный build его не перезаписывает. Снимки генератора v3, HB-07 build и layout_reference скопированы byte-for-byte. Из snapshot layout_reference вызывается только декодер и функции font/contrast/gray; старые capture/build/render/masks никогда не исполняются. Никакая команда не запускает Unreal, git или сетевую генерацию.

`verify_package.py` независимо от renderer перечитывает исходные API и трассы, проверяет 27 записей, сортировку, суммы, приватность, якоря fix1, пять исправлений, фон вне HUD, каждый экспорт и каждый gray-пиксель. `--finalize` сначала дополняет verification, затем пишет **manifest-sha256.json последним**. После этого `--check` только читает и проверяет полный инвентарь и все хеши; непройденные требования, если появятся, остаются явно записанными.
'''
    p=PKG/'README.md';assert p.resolve().is_relative_to(PKG)
    p.write_text(text,encoding='utf8')
    print('README.md written from final facts and verification')

if __name__=='__main__':main()
