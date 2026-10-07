# Задник вокруг поля карты: правило для новых карт (EN-18)

Карточка EN-18 (`docs/game-design/visual/06-tasks/env.csv`), решение по делегированию ВР-58: «вклейка по умолчанию;
lit3d — если вклейка не держит читаемость на K2». Образец — Marmoreal, ENV-U16 (EN-01…EN-17, VS-4…VS-5). Документ
не меняет действующие карты: Marmoreal — нарисованный задник (вклейка), Sarpedon — `lit3d`, путь 1 (AGENTS.md «Board
scenes and heroes»; Sarpedon переводится в другой режим только словом пользователя).

## 1. Правило

1. Поле — всегда настоящая иллюстрация карты (импорт скриптом, вне git, ENV-U3). Синтетические доски не используются.
2. Задник новой карты — **вклейка концепта** (`conceptPaste.mode = "paste"`, `default = "on"`): плоская нарисованная
   плита вокруг поля, без освещённого рельефа и без de-lit (ВР-53).
3. Плита оживляется полустатичными элементами: мерцание огней, ветер, туман, частицы вне поля (ВР-55). Мелкие детали
   концепта могут быть 3D с анимацией, но их нарисованный двойник с плиты убирается (02 §10.3).
4. После сборки вклейки — **K2-тест** (§2). PASS — карта остаётся на вклейке. FAIL — карта переходит на `lit3d`
   (3D-остров под de-lit альбедо, путь `docs/art-pipeline/ENV-P8-3D-UNDER-PAINT-TASK.md`), а решение записывается в журнал
   решений (`docs/game-design/decisions/`) с числами теста.
5. Старый 3D-вид карты (если был) остаётся только флагом отката и строкой AGENTS.md «Rollback flags»; по умолчанию
   поверх нарисованного задника 3D-окружение не включается.

```
paste (по умолчанию) ──► K2-тест ──PASS──► paste остаётся
                              └──FAIL──► lit3d (de-lit альбедо + 3D-остров) + строка в журнале решений
```

## 2. K2-тест (числа — решение по делегированию ВР-EN.16)

Кадры — свежий упакованный `-Bench` (`python tools/art/render/live_tune.py bench --packaged --map <map>`), виды K1,
K2 ×1,6 и K2 ×2,5, отпечаток `RENDER reference=1`, шесть фигур v2. Тест проходит, только если выполнены все строки на
**обоих** видах K2:

| № | Замер | Порог | Чем мерить |
|---|---|---|---|
| T1 | ΔE76 смежных зон поля | ≥ 23,2 | `env_gates.py gates` (G5, зоны), H2 |
| T2 | кольцо выбора: ΔL* к полю под ним | ≥ 30 | `env_gates.py gates` (G5, кольцо) |
| T3 | кромка фигуры к заднику (D4 edge) | ≥ 1,15 | `tools/art/render/hero_light_metrics.py` (D4) |
| T4 | плотность плиты в полосе 300 px от рамы поля | ≥ 0,8 текселя на экранный пиксель | `cp_bake.py` manifest (плотности текселей) + камера вида |
| T5 | сдвиг высоких нарисованных объектов относительно поля между K1 и K2 ×1,6 | ≤ 6 px | `paste_proto.py` (метрика совмещения деталей, `detail_positions`) |

- Т1–Т3 — читаемость игры: поле и фигуры не теряются на приближении. Т4–Т5 — качество самой вклейки: рисунок не
  мылится и не «съезжает» с поля.
- Если не проходит только T4 — сначала поднимается детализация плиты (×2 своей плиты, §3 п. 5), тест повторяется один
  раз; повторный FAIL — `lit3d`.
- Marmoreal (VS-5, packaged `-Bench`): T1 26,6 / 27,8, T2 43,1 / 53,9, T3 1,188 (K1) — PASS, поле и фигуры на K2
  читаются глазами; карта остаётся на вклейке (ВР-58). T4 и T5 для Marmoreal отдельно не мерились (плита ×2 и
  совмещение приняты в EN-03 / EN-07). Числа — `docs/game-design/evidence/VISUAL/ENV-U16/README.md`.

## 3. Порядок работ (как собран Marmoreal)

| Шаг | Что | Результат / инструмент | Карточка-образец |
|---|---|---|---|
| 1 | Концепт C0 по кадру игры: камера K1 (HFOV 35, pitch −55, yaw −90, 1920 × 1080), поле карты в кадре | `<map>-v1.png` (вне git) | ENV-MAPS P5 |
| 2 | Совмещение (registration): гомография концепта к кадру игры (у Marmoreal — тождественная, остаток ≤ 1,3 px) | `registration.json`, `register.py` | ENV-U15 |
| 3 | Чистая плита: убрать нарисованные фигуры и всё, что станет живым (огни, частицы), края поля | `<plate>-clean.png` | EN-01 |
| 4 | Достройка 20 % по краям (outpaint) — это rect B (C0 −384…2304 × −216…1296) | `<plate>-extended.png` | EN-02 |
| 5 | ×2 своей плиты (Lanczos-3 или генерация по своей плите; не ИИ-апскейл оригинала карты) | `<plate>-extended-2x.png` | EN-03 |
| 6 | Маски Anim: R мерцание, G ветер, B туман, A область частиц (офлайн); слой нарисованных огней | `<plate>-anim-2x.png`, `<plate>-lanterns-2x.png` | EN-04 |
| 7 | Спецификация `tools/art/concept_paste/<map>.paste.json` по шаблону `_template.paste.json` (§5) | `cp_bake.py check <map>` | EN-07 |
| 8 | Запекание и импорт: PlateA / PlateB / Anim, материал `M_ConceptPaste` (дочерний `MI_ConceptPaste_Anim`) | `cp_bake.py`, `ue_import_concept_paste.py`, `ue_concept_material.py` | EN-06, EN-07 |
| 9 | Профиль доски `conceptPaste`: `default "on"`, `mode "paste"`, `offVariant` (старый вид), `hide` (поднос, земля, 3D-окружение, базовые пропсы и fx), свет ≤ 6 точечных вместе со светом профиля | `S08ArtBoardProfiles.json`, `cp_layout.py` | EN-07, EN-13 |
| 10 | Анимации: мерцание огней синхронно с точечным светом; ветер (UV-искажение крон); туман (сдвиг UV у обрыва); частицы только вне поля; reduced motion — статично / без частиц | профиль `conceptPaste.anim`, раскладка `layout.fx` | EN-08…EN-12 |
| 11 | Флаг отката (`-NoConceptPaste` / `offVariant`) и строка AGENTS.md «Rollback flags»; трасса `ARTLOOK board=<profile> backdrop=paste` | C++ не нужен: `ResolveMode` общий | EN-13 |
| 12 | Свет героев под новый задник (не ярче прежнего, D1–D6) | `hero_light_metrics.py` | AN-36 / EN-14 |
| 13 | Бенч цены: `render_bench.py` paste / откат / без fx; пороги — §4 | `render_bench.py` | EN-15 |
| 14 | Лист приёмки: цвет, серый, дейтеранопия, полосы анимаций, reduced motion, G-READ панелей HUD, K2-тест §2 | `env_gates.py sheet / gates` | EN-16 |
| 15 | Пересъёмка эталона GD-058 обеих карт (лёгкий режим), дополнение к акту | `live_tune.py bench`, `compare --noise` | EN-17 |

Итерации параметров (свет, раскладка, fx) — одним клиентом `live_tune.py` (AGENTS.md «Iteration speed», ≤ 3 итерации в
лёгком режиме); перезапуск — только после C++, мешей, текстур и материалов; приёмочные кадры — свежий `-Bench`.

## 4. Пороги цены (как в EN-15)

- `paste` K1 GPU avg ≤ 2,60 мс и ≤ отката + 0,10 мс; K2 ×1,6 ≤ 3,8 мс;
- `paste − paste без fx` ≤ 0,15 мс; VRAM max ≤ откат + 64 МиБ;
- ACC-022: 60,00 FPS, p95 ≤ 16,7 мс на K1, K2 ×1,6, K2 ×2,5 (ПК разработки, не D-07);
- цена — без лимита FPS и не по `gpuMs` с лимитом; `r.DynamicRes` не лимит (AGENTS.md «Unreal GPU load»).

## 5. Шаблон спецификации

`tools/art/concept_paste/_template.paste.json` — копия итоговой `marmoreal.paste.json` (ENV-U16) с плейсхолдерами
`<map>`, `<Map>`, `<plate>`, `<sha256>`; числа совмещения, размеры и координаты — `null` (их дают шаги 2–8). В списках
оставлено по одному образцу каждой формы: деталь на земле и анимированная деталь на стене, зона высоты, зоны `slope` и
`vplane`, свет, fx лепестков и fx светлячков. Ключи шаблона после подстановки совпадают с `marmoreal.paste.json`:

```python
# python -B - < this snippet (из корня checkout); выход 0 = ключи совпадают
import json, sys
def paths(n, p=''):
    out = set()
    if isinstance(n, dict):
        for k, v in n.items():
            out.add(f'{p}/{k}'); out |= paths(v, f'{p}/{k}')
    elif isinstance(n, list):
        for x in n: out |= paths(x, f'{p}[*]')
    return out
d = 'tools/art/concept_paste/'
t = json.loads(open(d + '_template.paste.json', encoding='utf-8').read()
               .replace('<map>', 'marmoreal').replace('<Map>', 'Marmoreal').replace('<plate>', 'marmoreal'))
m = json.load(open(d + 'marmoreal.paste.json', encoding='utf-8'))
a, b = paths(t), paths(m)
print('only template:', sorted(a - b)); print('only marmoreal:', sorted(b - a)); sys.exit(1 if a ^ b else 0)
```

Проверка 2026-10-08: `only template: []`, `only marmoreal: []`; `python -B tools/art/concept_paste/cp_bake.py check
marmoreal` — ok.

Новая карта: скопировать шаблон в `<map>.paste.json`, заменить плейсхолдеры, заполнить `null` по `registration.json` и
контракту `cp_bake.py contract <map>`, удалить ненужные образцы списков или размножить их. Поля, которых нет у карты
(вода, `seaSky`), — `null`, как у Marmoreal; водные слои — по образцу `sarpedon.paste.json` (`bake.water`).

## 6. Хранение

- Концепт, плиты, маски и всё производное от них — вне git (`scraped-data/derived/...`, gitignored), как и сами карты.
- В git — скрипты, спецификация `<map>.paste.json`, `manifest.<map>.json` (sha256 входов и выходов, плотности
  текселей), профиль доски, раскладки и импортированные uassets текстур / материалов по решению карточки
  (ВР-VS5-09).
- Кадры приёмки без сканов карт, рубашек и аватаров можно класть в git; листы со сканами — вне git с индексом
  (ВР-VS4-01).

## 7. Запреты

- Паки с пометкой NoAI (Fab и др.) — не для ИИ-генераций и не в плиту.
- Арт Unmatched Digital Edition (кадры, окружение, камера) не переносится: «Поле и окружение не участвуют»
  (`docs/game-design/de-footage/task/01-decisions.md`).
- ИИ-апскейл оригинала карты (поля) — нельзя; ×2 — только своей плиты (шаг 5).
- Нарисованные двойники живых деталей на плите (огонь, фонарь, частицы) — убрать до запекания (ВР-55); 3D-головы
  фонарей поверх нарисованных — нет.
- Синтетические доски (Cobble 5×6, ART FIXTURE, сетка 20×20) — не образец и не доказательство.
- Режим Sarpedon не меняется этим правилом (AGENTS.md).
