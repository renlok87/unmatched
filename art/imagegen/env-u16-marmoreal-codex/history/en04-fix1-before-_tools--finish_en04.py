"""Finalize EN-04 package prose/log/manifest without altering earlier records.

Run python -B finish_en04.py docs, then build_masks.py verify, then
finish_en04.py manifest. All paths are confined to the task package roots.
"""
from pathlib import Path
import argparse
import hashlib
import json

ROOT=Path(__file__).resolve().parents[4]
PKG=ROOT/'art/imagegen/env-u16-marmoreal-codex'
IMG=ROOT/'scraped-data/derived/env-u16-marmoreal-codex'


def dump(p,obj):
    assert p.resolve().is_relative_to(PKG)
    p.write_text(json.dumps(obj,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')


def docs():
    v=json.loads((PKG/'_tools/en04-verification.json').read_text(encoding='utf-8'))
    log=json.loads((PKG/'generation-records.json').read_text(encoding='utf-8'))
    log['EN-04']={'task':'EN-04','status':'предложено','budget':0,'generation_count':0,'generations':[],
                  'prompt_keys':[],'reason':'No image generation is permitted or used; all outputs are procedural.',
                  'procedural_recipe_key':'EN-04-MASKS-03',
                  'script':'_tools/build_masks.py','build_record':'_tools/en04-build.json',
                  'attempts':[{'key':'EN-04-MASKS-01','generations':0,'result':'HSV selected some reflected pink bark highlights; add woody-core exclusion.'},
                              {'key':'EN-04-MASKS-02','generations':0,'result':'Explicit woody cores excluded; crop review required wider trunk contours.'},
                              {'key':'EN-04-MASKS-03','generations':0,'result':'Trunk and primary-branch exclusion widened; final script checks and PNG review.'}]}
    dump(PKG/'generation-records.json',log)
    link='../../../scraped-data/derived/env-u16-marmoreal-codex/'
    lines=['\n\n## EN-04 — маски анимации и слой фонарей ×2 (2026-10-07)',
           '', '**Статус: предложено.** Пять 8-битных масок L и два RGBA PNG 4680×2634 построены скриптом из проверенных плит EN-03 (SX-02, план Б). Генераций 0, бюджет 0. Исходная живопись не изменена. '+
           'Скриптовые проверки пройдены; буквальное требование центроида портала из glow невыполнимо на этих входах и явно отмечено ниже.',
           '', '**Рекомендация.** Единственный итоговый вариант EN-04-MASKS-03: чистая плита + слой фонарей с управлением через R glow; '+
           'G — движение цветков, B — огибающая дымки, A — область появления лепестков. Первый процедурный проход отклонён из-за небольших розовых бликов на коре в HSV-выборке; '+
           'во втором добавлены явные исключения стволов и основных ветвей, в третьем их контуры расширены после осмотра крупных кропов. Листы — диагностические наложения, яркость дымки на них не является рекомендуемой игровой интенсивностью.',
           '', '| Файл в derived-папке | Назначение |','|---|---|']
    purpose={'lantern-alpha':'головы, бра и тёплые пятна; исходная маска ×2, feather 8 plate px',
             'lantern-glow':'положительная линейная Rec.709 разность lit−clean × alpha, нормирована по максимуму; дверь 0',
             'sakura':'HSV 300…350°, saturation ≥0,25, cherry-w/e и боковое продолжение; древесина исключена; feather 12 px',
             'mist':'треугольная вертикальная полоса у подножия front-cliff и в нижнем outpaint',
             'petals':'точная grayscale dilation сакуры диском 24 px, защита повторена'}
    for n,s in purpose.items():
        name='marmoreal-mask-'+n+'.png';lines.append(f'| [{name}]({link+name}) | {s} |')
    lines += [f'| [marmoreal-lanterns-2x.png]({link}marmoreal-lanterns-2x.png) | lit RGB, alpha = lantern-alpha; RGB сохранён даже при alpha 0 |',
              f'| [marmoreal-anim-2x.png]({link}marmoreal-anim-2x.png) | RGBA = lantern-glow / sakura / mist / petals |',
              '', '**Малые решения и координаты.** C0→concept: ×1672/1920; concept→plate: ×2 +(668,376). '+
              'EN-01 field-mask уже содержит расширение поля на 2%; второй раз 2% не добавлял. Для 40 px у подножия рамки консервативно защищена вся деревянная рамка EN-01 '+
              '[(387,208),(1278,208),(1366,765),(305,765)] concept px плюс евклидово расширение 40 plate px. Отдельно защищены 40 px по всем четырём краям плиты. '+
              'Размытие/дилатация выполняются до повторного обнуления защиты. Cherry-полигоны продолжаются горизонтально в боковой outpaint; '+
              'границы остаются из paste.json. Feather сакуры — Gaussian σ=4, обрезанный 12 px, с повторным ограничением цветовым пигментом и woody-исключениями: края не закрашивают тёмные ветви. '+
              'B: ramp y=2161→2353→2593, боковой feather внутрь 32 px, только продолженный трапецоид front-cliff. Это огибающая, не готовая текстура дымки.',
              '', '**Якоря.** [lanterns.json](lanterns.json) содержит все семь требуемых ID, plate/concept/C0 центры и радиусы C0. '+
              'Шесть центров — центроиды glow внутри вручную ограниченного стекла; радиус покрывает весь принадлежащий прибору ненулевой glow. '+
              'Для прозрачности записаны также центроиды полных световых пятен. Окружность ±4 C0 px вокруг каждого из шести центров целиком лежит внутри измеренной области стекла. '+
              'Число offset_from_glass_bbox_centre — справочное: яркостный центроид не обязан совпадать с геометрическим центром bbox. '+
              'Медианы чистой плиты под ненулевой сакурой и дымкой записаны как sRGB_u8, sRGB_0_1 и hex; цвета взяты из живописи, правило фиксированных токенов для плит не применяется.',
              '', '**Ограничение портала.** В EN-01 дверь намеренно оставлена светящейся и в clean, и в lit. Её glow-маска равна нулю; '+
              'центроид нулевой разности не определён, а портал не имеет фонарного стекла. Для седьмой записи дан неподвижный якорь — центроид ярчайших 20% тёплых пикселей lit в области светильника портала; '+
              '`animated=false`, `glow_weight=0`, дверь не включена в R. Поэтому `strict_literal_acceptance_pass=false`; никакой ложной полной приёмки нет. '+
              'Требование «все семь PNG нулевые на поле» применяется к маскам/каналам anim/alpha фонарного слоя: его RGB обязан оставаться точным lit RGB.',
              '', '**Проверка.** [verification.json](verification.json), секция EN-04; отдельная копия [_tools/en04-verification.json](_tools/en04-verification.json). '+
              f"Скриптовых условий: {len(v['checks'])}, не пройдено: {len(v['failed_checks'])}. Все семь PNG проверены после сохранения, включая IHDR bit depth, режимы и точные каналы. "+
              'Пиксельные счётчики на поле+2%, у рамки+40 px и внешней границы+40 px равны 0; дверь/R, древесные cores/G и выход за cliff/B — 0. '+
              'Маска не является математическим семантическим доказательством для каждого мазка ветви; поэтому дополнительно открыты крупные PNG крон и записан непосредственный визуальный осмотр. '+
              'K1 — плоский full-B framing по контракту пакета, K2 — кропы ×2,5; игровых снимков/камеры Unreal эта задача не создаёт.',
              '', '| Маска | Этап + PNG, с общей подготовкой |','|---|---:|']
    for n,t in v['build']['timings'].items():lines.append(f"| {n} | {t['with_shared_setup_seconds']:.3f} с (лимит 60 с) |")
    lines += ['', '**Листы.** Цвет и серый Rec.709 `.2126 R + .7152 G + .0722 B` в кодированном sRGB. '+
              'В полноразмерных листах каждое изображение имеет мастер 4680×2634; рабочие листы содержат по шесть панелей указанного размера. Маски накладываются как opacity = mask/255 ×0,5.',
              '', '| Лист | Цвет | Серый |','|---|---|---|']
    sheets=[('Рабочий 1521×856','working-1521x856'),('Рабочий 1170×659','working-1170x659'),('K1 ×0,65, full B','K1x065'),('Все семь K2','K2-all'),
            ('Сакура слева, 100%','detail-sakura-w'),('Сакура справа, 100%','detail-sakura-e'),('Подножие скалы, 100%','detail-mist-foot'),
            ('Исключения древесины','woody-exclusions'),('Защищённые области','protected')]
    sheets += [(n+' master',n+'-master') for n in purpose]
    sheets += [(e['id']+' K2','K2-'+e['id']) for e in json.loads((PKG/'lanterns.json').read_text(encoding='utf-8'))['entries']]
    for label,stem in sheets:
        lines.append(f'| {label} | [PNG]({link}comparison/masks-{stem}-colour.png) | [PNG]({link}comparison/masks-{stem}-gray.png) |')
    lines += ['', '**Сохранность.** [source-hashes-before.json](source-hashes-before.json) и неизменяемый [en04-baseline.json](en04-baseline.json) '+
              'фиксируют входы и все 1499 файлов HUD до работы. После работы входы и дерево HUD неизменны. '+
              'Требуемый снимок HUD-генератора заменён точной копией текущего draw_icons.py; прежний снимок сохранён побайтно в history/en04-before-draw_icons_v3_snapshot.py. '+
              'Другие прежние скрипты, изображения, prompts и история не менялись. Старые README/отчёты/журнал/manifest сохранены в history/en04-before-*; '+
              'README дописан, JSON-отчёты расширены EN-04, прежние секции не переписаны. Git/MCP/Unreal — 0. Записи только в двух разрешённых папках. Постоянных процессов нет.',
              '', 'Воспроизведение без генераций:', '', '```powershell',
              'python -X utf8 -B art/imagegen/env-u16-marmoreal-codex/_tools/build_masks.py build',
              'python -X utf8 -B art/imagegen/env-u16-marmoreal-codex/_tools/build_masks.py sheets',
              'python -X utf8 -B art/imagegen/env-u16-marmoreal-codex/_tools/build_masks.py verify',
              'python -X utf8 -B art/imagegen/env-u16-marmoreal-codex/_tools/finish_en04.py docs',
              'python -X utf8 -B art/imagegen/env-u16-marmoreal-codex/_tools/build_masks.py verify',
              'python -X utf8 -B art/imagegen/env-u16-marmoreal-codex/_tools/finish_en04.py manifest','```','']
    # Prefix stays byte-identical to the start-of-task README (no newline rewrite).
    before=(PKG/'history/en04-before-README.md').read_bytes()
    (PKG/'README.md').write_bytes(before+'\n'.join(lines).encode('utf-8'))
    plan=PKG/'EN-04-plan.md'
    plan.write_text(plan.read_text(encoding='utf-8').replace('- [ ]','- [x]'),encoding='utf-8')


def manifest():
    paths=sorted(p for base in (PKG,IMG) for p in base.rglob('*') if p.is_file() and p!=PKG/'manifest-sha256.json')
    files={p.relative_to(ROOT).as_posix():{'sha256':hashlib.sha256(p.read_bytes()).hexdigest(),'bytes':p.stat().st_size} for p in paths}
    dump(PKG/'manifest-sha256.json',{'task':'EN-04 procedural masks; earlier records preserved in history/en04-before-*',
                                   'files':files,'self_excluded':True})
    print('manifest:',len(files),'files')


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('command',choices=('docs','manifest'))
    {'docs':docs,'manifest':manifest}[p.parse_args().command]()
