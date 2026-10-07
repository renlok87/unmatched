# EN-06 — каналы анимации вклейки и reduced motion окружения

**Статус: технически готово, по делегированию (2026-10-07, VS-5 шаг E1, ветка `feat/visual-vs5`).** Вклейка Marmoreal
ещё за флагом `-ConceptPaste` (по умолчанию её включает EN-13). Кадры ниже — живые кадры editor `-game` с пометкой
`-ConceptPaste`. Приёмочные кадры VS-5 — packaged `-Bench` в EN-15.

## Что сделано

- **Профиль.** Необязательный блок `conceptPaste.anim`:
  - `mask` — путь `/Game/EnvMaps/…`;
  - `lanterns` ≤ 8 слотов: `{id, c0Px, radiusPx, light | flicker}`;
  - `wind`: `{ampPx, hz, gustHz, gustAmp, wavePx}`;
  - `mist`: `{opacity, panPxPerS, noisePx, colorSrgb}`.

  Разбор — `S08ConceptPasteAnim.cpp`. Неизвестное поле, 9 слотов, слот без света или со светом и своим мерцанием сразу,
  смещение ветра больше 4 C0 px — ошибки разбора.
- **Материал** `M_ConceptPaste`, граф 4 (`tools/art/concept_paste/ue_concept_material.py`).
  - Ноды Time больше нет: время задаёт параметр `AnimTime` из C++. По нему же идут потоки воды Sarpedon в режиме paste.
  - Статический переключатель `UseAnim` (по умолчанию выкл.) включает три канала: огни (R × мерцание слота), ветер
    (сдвиг UV по G) и туман (B × непрозрачность × шум).
  - `MI_ConceptPaste_Anim` — дочерний MI с `UseAnim` = вкл. `T_ConceptPaste_Noise` — шум 256², сид 20261007, wrap, G8.
    Оба собирает тот же скрипт.
  - Формулы — колонка keyframes карточки (`S08ConceptPasteAnim.h`).
- **C++.** `Apply` ставит листу `MI_ConceptPaste_Anim`, если есть маска и MI; иначе остаётся статичная вклейка и
  `use=0 status=mask-missing|material-missing`.
  - В живом прогоне `US08ConceptPasteAnimComponent` каждый тик пишет `AnimTime` и `LanternFlicker_i`.
  - Слот со ссылкой на свет берёт `FlickerScale` этого света с тем же T, что у точечного света: одно значение на кадр.
  - В `-Bench`, с `-EnvFxFreeze` и при reduced motion: AnimTime 0, мерцание 1, амплитуда ветра 0. Туман остаётся, но
    стоит.
- **Reduced motion окружения** (ВР-EN.4): `FS08EnvFxOptions::FromCommandLine` берёт `S08IconMotion::IsReducedMotion()`
  и ставит `bFreeze`. Поэтому:
  - вклейка стоит, `MPC_EnvScene Live` = 0 (вода и ветер Sarpedon стоят);
  - fx с `reducedMotion: "freeze"` (по умолчанию) замирают после прогрева;
  - fx с `"off"` не спавнятся.
  - В базовой раскладке Marmoreal (откат P5c) у лепестков и светлячков стоит `"off"` (02 §10.1).
- **Трассы.**
  - `ARTPREVIEW concept-paste anim profile=… mask=… lanterns=N synced=K wind=<amp>@<hz> mist=<op> frozen=0|1
    reason=live|bench|flag|reduced use=0|1 status=…`.
  - `ARTPREVIEW envlayout fx …`: в каждой строке fx и в сводке в конце `reason=`. Пропущенный fx пишется как
    `… mode=off reason=reduced`, в сводке есть `reducedOff=N`.

## Приёмка карточки

| п. | критерий | результат |
|---|---|---|
| 1 | `Unmatched.S08.ConceptPaste.*`, `.EnvLayout.*`, `.LiveTune.*` (+ `.IconMotion.*`), pytest `tools/art/tests` | **51 / 51 Success**: Parser с блоком anim, новый `.Anim`, `.EnvLayout.FxParse` с `reducedMotion`. pytest — 590 passed, 4 skipped; 1 тест сравнивает базовые раскладки с HEAD, проходит после коммита |
| 2 | два свежих `-Bench` Marmoreal с маской: средняя \|Δ\| ≤ 0,5, > 24 ≤ 0,05 % | K1 0,215 / 0 %, K2×1,6 0,257 / 0,0002 % ([metrics.json](metrics.json)) |
| 3 | трасса anim: synced=4; с `-S08ReducedMotion` frozen=1 reason=reduced, лепестки и светлячки mode=off | `lanterns=6 synced=4 … frozen=1 reason=bench use=1 status=ok`; с `-S08ReducedMotion` — `frozen=1 reason=reduced`. Откат P5c с `-S08ReducedMotion`: 4 × `petals-cherry-*` и 2 × `fireflies-garden-*` — `mode=off reason=reduced`, сводка `reducedOff=6 reason=reduced`. Огни P5c — `mode=frozen` |
| 4 | Sarpedon без флагов не изменился (compare в пределах шума) | до (пакет Z-2) / после: K1 0,439 / 0,077 %, K2×1,6 0,487 / 0,26 % — на уровне шума бенч-бенч 0,43 / 0,08 % и 0,47 / 0,25 %. Вне маски шума — 0,0001 % и 0 %, **pass**. Против P10 final-pkg вне маски шума — 0,0012 % / 0 %, pass |

## Живые кадры

Live tune, `shot --live --clock free`, K2×1,6, три кадра:

- стекло фонаря `lantern-w`: яркость 130,0 → 132,6 → 131,4;
- крона: |Δ| 8,4 и 11,0 уровней только в маске G;
- поле, рама, мостовая — шум TSR (обрыв 0,3–0,5).

Файлы:

- [live-K2x1p6-crown-w-a-b.png](live-K2x1p6-crown-w-a-b.png) — крона и фонарь в двух кадрах, крона не рвётся;
- [live-K2x1p6-diff-a-b-x6.png](live-K2x1p6-diff-a-b-x6.png) — разница ×6: ветер только в кроне, огонёк только в
  стекле; фигуры — их idle.

Я открыл оба файла и кадры K1 / K2×1,6 бенчей обеих карт: доски настоящие, задник Marmoreal — плита, Sarpedon — lit3d,
шесть фигур v2.

## Решения по делегированию

- **ВР-VS5-01.** Блок `anim` и 5 точек Marmoreal ставятся в E1 со стартовыми значениями EN-08 (свет), EN-10 (ветер) и
  EN-12 (туман). Без них не проверить п. 3 (`synced=4`). Карточки EN-08, EN-10 и EN-12 их подбирают. `default` остаётся
  off до EN-13.
- **ВР-VS5-02.** Предел `radiusPx` — 4…320 вместо 4…200. Радиусы `lanterns.json` у фонарей — 262–282 C0 px (пятно
  lantern-glow). Кромка диска — 20 %. Пересечения слотов (бра у двери) нормируются на Σw.
- **ВР-VS5-03.** `UseAnim` — статический переключатель на литерал пина `UseAnimS`: компилятор убирает код каналов из
  выключенной перестановки. MID не меняет статический ключ, поэтому лист берёт `MI_ConceptPaste_Anim`. Небо Sarpedon
  остаётся на `M_ConceptPaste` (выкл.).
- **ВР-VS5-04.** `AnimTime` заменяет Time и для потоков воды (лист и море режима paste).
- **ВР-VS5-05.** Reduced motion идёт через `bFreeze` опций fx. Вместе с окружением стоит и «дыхание» света активной
  фигуры: это общее правило замороженных прогонов. Fx Sarpedon оставлены на `freeze` по умолчанию.

## Остатки

- **ALU.** Предел «≤ 30 инструкций ALU» не измерен: в коммандлете статистика материала нулевая. Восемь дисков огней —
  около 40 ALU, но под динамической ветвью `R > 0,002`. R лежит внутри lantern-alpha, а она ненулевая примерно на 11 % плиты
  (README EN-04). ΔGPU мерит EN-15
  (`render_bench.py`).
- **Вырезы древесины в G** (ВР-VS3-EN04-04). На живых кропах K2×1,6 при ampPx 1,2 разрыва нет, сглаживать не нужно.
  Перепроверить в EN-10.
- **Статус в `env.csv`** правится в основной копии после интеграции (ВР-PL09).
