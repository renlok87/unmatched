"""Record the completed human-visible inspection; append README without rewriting history.

Run only after opening every listed PNG. This does not perform visual inspection.
"""
import argparse, hashlib, json
import rework_fix2 as f

def review():
    paths=set(f.COMP.glob('r3-*.png'))|{f.COMP/'08-diff-outside-remove-mask.png',f.IMG/'marmoreal-clean.png',f.IMG/'marmoreal-lantern-mask.png',f.COMP/'fix2-inspection-boost-colour.png'}
    for spot in ['nw','ne']:
        paths.update([f.IMG/f'concepts/EN-01-R3-{spot}-1-input.png',f.IMG/f'concepts/EN-01-R3-{spot}-1-raw.png',f.COMP/f'fix2-{spot}-polygon-inspection.png',f.COMP/f'fix2-{spot}-fix-mask.png'])
    report={'performed':True,'date':'2026-10-06','run':'CX-07r fix2','method':'Opened each of the 47 current r3 PNGs with view_image, including colour and Rec.709 gray; opened boosted K2 at brightness x2.5, normal 4x Lanczos, 2x nearest, all seven seam-cell pairs, source-core diagnostics, masks, lit sheets and black outside diff. Also opened both edit inputs, both unretouched raws, final deliverables and final polygon diagnostics. This file records the inspection, it does not automate it.','inspected_images':{f.rel(p):f.digest(p) for p in sorted(paths)},'r3_images_count':len(list(f.COMP.glob('r3-*.png'))),'silhouettes_removed':True,'boosted_silhouettes_removed':True,'pedestals_intact':True,'no_new_objects_water_figures_text':True,'K2_no_visible_boundary':True,'gray_readable':True,'gray_notes':'Плоские светлые крышки и тела четырёх тумб, ритм балюстрады и мраморных колонн читаются на полном, рабочих и K2 серых листах. Ниши остаются тёмными; новая заделка не выглядит светлой кляксой.','lit_no_double_edges':True,'notes':'На NW/NE вместо коробки, крыши с завитыми углами и парных стоек видны тёмная ниша и тонкие ветви с розовыми цветками. Повышенная яркость показывает фон без узнаваемого фонаря; видимого шва вставки нет. SW принятую заделку сохраняет. В SE видны широкие листья и диагональные ветви, без крыши, стоек или крюка; генерация не нужна. У бра показана тёмная дверная ниша без пламени. Крышки и колонны взяты из fix1. В lit фонари и бра восстановлены с единственным контуром; мягкий свет затухает без ступенчатой кромки. Тёплые ступени у двери и блики вне support сохранены по ВР-VS2-EN.2. Вода, фигуры, текст и новые предметы не добавлены.'}
    f.save_json(f.PKG/'_tools/visual-review-fix2.json',report)
    print({'reviewed_r3':report['r3_images_count'],'reviewed_total':len(paths)})

def append_readme():
    b=json.loads(f.BASELINE.read_text(encoding='utf-8'));v=json.loads((f.PKG/'verification.json').read_text(encoding='utf-8'))
    assert v['acceptance_pass'] and v['visual_review_current']
    path=f.PKG/'README.md';prefix=path.read_bytes()
    assert len(prefix)==b['readme_before']['bytes'] and hashlib.sha256(prefix).hexdigest()==b['readme_before']['sha256']
    mask=v['lantern_mask'];after=v['R4']['after'];changes=v['changes_vs_previous_plate']
    section='''

## Исправление fix2 (2026-10-06)

Статус: **предложено**. Выполнена единственная корректировка по `EN-01.fix2.codex.md`; все шесть строк обновлённой acceptance проходят в [verification.json](verification.json). Это предложение для ревью, а не новый акт приёмки.

### Что исправлено

NW и NE: по одной локальной генерации image edit, без повторов. Каждый вход — кроп текущей плиты fix1 192×192 px без пикселей поля, увеличенный Lanczos до 1024×1024. Сняты тёмная крыша с завитыми углами, две стойки рамы и центральный стержень; вместо них — тёмная ниша, тонкие ветви и розовые цветки. Запрет `Forbidden` перенесён из базового задания дословно. Результаты 1254×1254 сохранены без ретуши; затем уменьшены Lanczos и вставлены только внутри локальных полигонов с растушёвкой 8 px внутрь. Крышки тумб и колонны исключены. Полигон NW имеет границы x=386…431, y=40…102; NE — x=1230…1271, y=40…102. Поле, SW, SE, расширение растушёвки швов и остальные пиксели плиты fix1 сохранены.

SE осмотрен в K2 4× при обычной яркости и ×2,5: вижу слои сине-зелёных листьев, розовые цветки и неровные диагональные ветви над плоской крышкой. Крыши с завитыми углами, парных стоек, навершия и крюка нет. Генерация SE не выполнялась. SW остаётся принятой заделкой fix1.

Маска собрана по исправленной ВР-VS2-EN.3:

```text
m = max(min(glow, remove/255), core * [remove > 0])
m = 0 вне remove-support, на поле и вне объединения радиусов 260/130 px.
lit = round(clean * (1-m/255) + C0 * (m/255)).
```

Ядра и их расширение 2 px не обрезаются растушёвкой remove-mask. Свечение пересчитано от окончательной плиты по прежней CIELAB D65 формуле, radial smoothstep 0,6R…R, Gaussian σ=3 и порогу 8/255; свечение остаётся ограничено remove-mask. Из 425 пикселей расширенных ядер ниже 255 в fix1 восстановлены 386 внутри support; 39 вне support имеют m=0, а плита там уже равна C0. На всех ядрах, включая эти 39 пикселей, lit побайтно равен C0. Старые полигоны ядер не сужались.

### Измерения окончательной плиты

| Место | L* пятна | L* кольца | R1: пятно − кольцо | R2, px | R3, тёплые | Lit ΔE76 |
|---|---:|---:|---:|---:|---:|---:|
'''
    for i in range(6):
        a=v['R1'][i];c=v['R3'][i];lit=v['lit_check']['per_light'][i]
        section+=f"| {a['spot']} | {a['spot_median_Lstar']:.3f} | {a['ring_median_Lstar']:.3f} | {a['signed_delta']:.3f} | {v['R2'][i]['hot_pixels']} | {c['share']*100:.4f}% ({c['warm_pixels']}/{c['measured_pixels']}) | {lit['mean_dE76']:.3f} |\n"
    section+=f'''
R1–R3 проходят во всех шести точках. Старый абсолютный |ΔL*| сохранён в `legacy_spot_ring_Lstar` как superseded, на приёмку не влияет. R4 до и после fix2: **174/183 = {after['s_le_4_share']*100:.4f}%** ячеек с s≤4; непривилегированных превышений **0**, максимальное непривилегированное s={max(row['s'] for row in after['cells'] if row['s'] is not None and not row['exempt']):.3f}. Список всех pass/fail/exempt/skipped до и после сохранён.

- Изменения относительно fix1: **{changes['total']} px**, NW **{changes['nw']}**, NE **{changes['ne']}**, SE **0**, вне локальных исправлений **0**. SW и принятая растушёвка швов неизменны.
- Вне remove-mask относительно C0 изменено **0 px**; поле целиком **#808080**. Рама и внутренность двери побайтно равны C0.
- Маска: ненулевая доля **{mask['nonzero_share']*100:.4f}%**, доля α≥128 **{mask['share_ge_128']*100:.4f}% ≤10%**, средняя α по кадру **{mask['global_mean_alpha']:.6f}** ({mask['mean_alpha_levels']:.4f}/255), α-взвешенная средняя Σα²/Σα **{mask['alpha_weighted_mean']:.6f}**.
- Внутри support все ядра и их расширение равны **255**, обрезанных пикселей **0**; вне support, на поле и вне радиусов маска **0**. Проверяемый максимальный перепад 4-соседей **{mask['max_4_neighbour_step_outside_core_edges']} ≤48**. Исключены пары, касающиеся расширенного ядра и его 2,5 px мягкой кромки, включая границу support непосредственно рядом с ядром; это исключение явно записано в отчёте.
- Lit совпадает с C0 на всех ядрах внутри и вне support; средний ΔE76 каждой точки **≤8**, двойного контура на просмотренных листах нет.
- Тёплые остатки вне support сохранены: всего **14728 px**, защищённая рама 3148, ступени двери 3484, урны 6483, косяки 4978, мостовая SE под углом рамы 511. Области пересекаются; ВР-VS2-EN.2 разрешает эти остатки, их не суммируем и не закрашиваем.

### Листы и визуальный осмотр

Лично открыты все **47 r3-PNG**, оба новых raw, входы, маски, конечная плита и чёрный diff вне remove-mask. [_tools/visual-review-fix2.json](_tools/visual-review-fix2.json) связывает каждый просмотренный файл с SHA-256. Все листы, зависящие от плиты/маски, пересобраны для fix2 с прежней компоновкой; исходные C0 core-detail, архив `r3-old-lantern-mask.png` и принятая composite-alpha остаются прежними, поскольку их содержание не зависит от fix2.

| Сравнение | Цвет | Rec.709 gray |
|---|---|---|
| K2 4×, C0 / fix1 / fix2 | [цвет](../../../scraped-data/derived/env-u16-marmoreal-codex/comparison/r3-K2-six-4x-colour.png) | [серый](../../../scraped-data/derived/env-u16-marmoreal-codex/comparison/r3-K2-six-4x-gray.png) |
| K2 4×, яркость ×2,5 | [цвет](../../../scraped-data/derived/env-u16-marmoreal-codex/comparison/r3-K2-six-4x-boost-colour.png) | [серый](../../../scraped-data/derived/env-u16-marmoreal-codex/comparison/r3-K2-six-4x-boost-gray.png) |
| K2 2× nearest | [цвет](../../../scraped-data/derived/env-u16-marmoreal-codex/comparison/r3-K2-six-2x-nearest-colour.png) | [серый](../../../scraped-data/derived/env-u16-marmoreal-codex/comparison/r3-K2-six-2x-nearest-gray.png) |
| Полный 1672×941 | [цвет](../../../scraped-data/derived/env-u16-marmoreal-codex/comparison/r3-full-colour.png) | [серый](../../../scraped-data/derived/env-u16-marmoreal-codex/comparison/r3-full-gray.png) |
| Рабочий 1087×612 | [цвет](../../../scraped-data/derived/env-u16-marmoreal-codex/comparison/r3-working-1087x612-colour.png) | [серый](../../../scraped-data/derived/env-u16-marmoreal-codex/comparison/r3-working-1087x612-gray.png) |
| Рабочий 836×471 | [цвет](../../../scraped-data/derived/env-u16-marmoreal-codex/comparison/r3-working-836x471-colour.png) | [серый](../../../scraped-data/derived/env-u16-marmoreal-codex/comparison/r3-working-836x471-gray.png) |
| R4 карта | [цвет](../../../scraped-data/derived/env-u16-marmoreal-codex/comparison/r3-seam-map-colour.png) | [серый](../../../scraped-data/derived/env-u16-marmoreal-codex/comparison/r3-seam-map-gray.png) |
| Маска fix1 / fix2 / поверх C0 | [цвет](../../../scraped-data/derived/env-u16-marmoreal-codex/comparison/r3-lantern-mask-colour.png) | [серый](../../../scraped-data/derived/env-u16-marmoreal-codex/comparison/r3-lantern-mask-gray.png) |
| Lit / C0, шесть точек | [цвет](../../../scraped-data/derived/env-u16-marmoreal-codex/comparison/r3-lit-K2-six-colour.png) | [серый](../../../scraped-data/derived/env-u16-marmoreal-codex/comparison/r3-lit-K2-six-gray.png) |
| Ядра бра и lit | [цвет](../../../scraped-data/derived/env-u16-marmoreal-codex/comparison/r3-sconce-core-clipping-colour.png) | [серый](../../../scraped-data/derived/env-u16-marmoreal-codex/comparison/r3-sconce-core-clipping-gray.png) |

На усиленных листах NW/NE больше не читаются как коробки на тумбах: нет цельной крыши, стоек или стержня, видны ниша и веточки с цветками. У SE сохранённая листва не складывается в форму фонаря. Крышки тумб плоские, мраморные колонны и балюстрады читаются в цвете и сером на всех размерах. Видимой границы новых вставок нет. Семь увеличенных пар seam-cell показывают совпадение fix1/fix2; тёплые блики у рамы остаются как разрешённый остаток. Lit показывает по одному контуру каждого фонаря и бра, без нового ореола или ступенчатого края. Вода, фигуры, текст и новые предметы отсутствуют.

### Бюджет, сохранность и воспроизведение

Использованы **2 из 3** разрешённых генераций fix2: NW 1, NE 1, SE 0, повторов 0; SYNTX **0**. Общая доработка CX-07r — **3 из 4** (SW fix1 + NW/NE fix2), первоначальные A/B/R1/R2 — 4 из 4. Неудачных новых генераций или невыполненных критериев нет. Проверка первого технического расчёта выявила переполнение uint8 в промежуточном lit; оно исправлено приведением α к float до умножения, все окончательные lit-файлы и числа пересобраны. Бюджет генераций это не затронуло.

До изменений [fix2-baseline.json](fix2-baseline.json) зафиксировал SHA-256 и размеры 855 файлов; 849 замороженных файлов, включая прежние concepts/prompts и скрипт rework_r3.py, проверены неизменными. [history/verification-fix1.json](history/verification-fix1.json) и [history/manifest-sha256-fix1.json](history/manifest-sha256-fix1.json) — точные копии fix1. Предыдущая плита и маска сохранены как `comparison/fix2-before-clean.png` и `fix2-before-lantern-mask.png`; их хеши проверяются перед сборкой.

Старые объекты [generation-records.json](generation-records.json) сохранены без изменений и проверены на точное совпадение с baseline; две строки добавлены в конец. Prompt/input/raw проверены SHA-256, `retouched: false`, указан путь исходного файла инструмента. Служебные PNG imagegen под CODEX_HOME перечислены в `tool_cache_outside_repo`, не редактировались и не удалялись; исправляющее задание явно исключает их из `outside_folder`.

Сборка из локальных файлов без новых генераций:

```powershell
python -B art/imagegen/env-u16-marmoreal-codex/_tools/rework_fix2.py build
python -B art/imagegen/env-u16-marmoreal-codex/_tools/rework_fix2.py verify
python -B art/imagegen/env-u16-marmoreal-codex/_tools/rework_fix2.py manifest
```

[_tools/reproducibility-fix2.json](_tools/reproducibility-fix2.json) фиксирует повторную сборку с совпадением SHA-256 плиты, маски, mask-spec и всех PNG листов. [manifest-sha256.json](manifest-sha256.json) покрывает оба разрешённых корня, исключая только себя. Никаких git-команд, чтения/сборки unreal/ или изменений других файлов проекта не было. Все записи агента — внутри папки пакета и разрешённой `scraped-data/derived/env-u16-marmoreal-codex/`; постоянные процессы не запускались.
'''
    path.write_bytes(prefix+section.encode('utf-8'))
    print({'README_appended_bytes':len(section.encode('utf-8')),'original_prefix_preserved':True})

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('command',choices=['review','append-readme']);a=p.parse_args()
    if a.command=='review':review()
    else:append_readme()
