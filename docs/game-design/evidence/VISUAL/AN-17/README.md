# AN-17 — лист приёмки

Лист собран `tools/art/visual/sheet.py` 2026-10-07 по 02-visual-design.md §13.2. Поля ниже заполняет Claude после
ревью (один проход, 07 §5).

**Решение:** технически импортировано (стенд поз `-BenchClipPose` — инструмент проверки, не художественное решение;
позы берутся из принятых клипов H2LD/H3LD)
**Дата решения:** 2026-10-06
**Ревью:** ZCode (Z-1), один проход, арт и рамки задачи вместе (02 §13.3)
**Флаг отката:** — (инструмент: `-BenchClipPose`, `-BenchClipPoseFighter`; на игру не влияет)

## Что сделано (карта AN-17)

Стенд поз в packaged `-Bench`: `-BenchClipPose=<Hero>/<Clip>@<frames>` ставит каждую фигуру в точный кадр клипа
(`S08HeroesV2::ParseBenchClipPoses`), новая ступень 7 стенда (`AS08FlowGameMode::RunRenderBench`) проигрывает
список кадров, снимок `bench-<view>-<clip>-f<NN>-1920x1080.png`, трассы `ARTPREVIEW clippose fighter=.. clip=..
frame=.. t=.. len=.. rootDeltaUU=..` и `ARTPREVIEW figrect fighter=.. view=.. x= y= w= h=`. Список через запятую
читается с `bShouldStopOnSeparator=false` (первый прогон терял всё после первой запятой — исправлено, коммит
`0f712a5e`-серії, см. Z-1 README).

## Состав листа (02 §13.2)

| № | Пункт | Файлы | Есть |
|---|---|---|---|
| 1 | Мастер и рабочие размеры | — (кадры движка 1080p вместо значков: позы фигур, не UI) | — |
| 2 | Цвет, серый Rec.709, дейтеранопия | `sheet-01..06-*.png` (по три ряда в каждом листе) | да |
| 3 | Кадр на обеих настоящих досках, K1/K2, packaged `-Bench` c `RENDER` | листы 1–4 — Marmoreal original, 5–6 — Sarpedon original; `RENDER reference=1` в трассе (144 строки, marmoreal) | да |
| 4 | Контекст | — (кадры непрозрачные, доска и есть контекст) | — |
| 5 | Движение: лист кадров по времени | `bench-*-f00..f21` — полная серия кадров в `C:/tmp/visual/AN-18/` (70 PNG на карту); в лист вошли ключевые | частично |
| 6 | Трассы | `ARTLOOK`, `ARTPREVIEW clippose` (210/карта), `figrect` (420/432), `BENCH done views=2 poses=35` | да |
| 7 | README | этот файл | да |

## Прогоны (финальный пакет, stamp `f8903fb9`)

- Marmoreal original `c121b47f8d6eb28daccb76d05` + `-ConceptPaste` (окраска задника EN-13 ещё не принята — задник
  включён флагом, см. Z-1 README), K1+K2x1.6: 35 поз × 2 вида, 70 PNG, 19:01–19:58.
- Sarpedon original `c7fa64a26c29a0835f2383e63` (lit3d), K1+K2x1.6: 35 поз × 2 вида, 70 PNG.
- Позы: Idle q0..q75 (24 fps), LungeAttack f00..f13, HitReact f00..f10, DeathSettle f00..f21, Place — у всех
  шести фигур сразу (кадр один на всех).
- `rootDeltaUU=0.00` во всех 210 позах (клипы world-free, стенд не смещает корень — 0 нарушений).
- Кадровая сетка: frames advance верно (f00→f07→f13…), t = frame/24, len клипов 2.333/2.0/0.583/… с.

## Входы

| файл | размер | sha256 |
|---|---|---|
| `C:/tmp/visual/AN-18/marmoreal/bench-K1-LungeAttack-f00-1920x1080.png` | 1920×1080 | d26d600971c7eeef7ee6ac4479bf84310526f915946f4f06c2edec608742fc3b |
| `C:/tmp/visual/AN-18/marmoreal/bench-K1-LungeAttack-f07-1920x1080.png` | 1920×1080 | a7f59f2ca07509ac311c2448702871a1161a3ca07c5bb7bed5090542cb05bf17 |
| `C:/tmp/visual/AN-18/marmoreal/bench-K2x1.6-Idle-q50-1920x1080.png` | 1920×1080 | 7be7e60db00c85facfe5c8451717429ce1ac0bd0f1d880281e18038b3c5dfa0c |
| `C:/tmp/visual/AN-18/marmoreal/bench-K1-DeathSettle-f21-1920x1080.png` | 1920×1080 | d75f68e8ac389dfc5e34d19ab78ddc2d9684a425318a3b87ee1a8060e4377a4a |
| `C:/tmp/visual/AN-18/sarpedon/bench-K1-LungeAttack-f07-1920x1080.png` | 1920×1080 | 58c5518c1ec3ba93db44ee48a08b1e2b1c99b70dfd8aa47de670ae899c1805f5 |
| `C:/tmp/visual/AN-18/sarpedon/bench-K1-HitReact-f05-1920x1080.png` | 1920×1080 | 0b8f4a5f0ffcda14ddffac780e01be7b109ff8fa60cb359c5e1dd34fba267a35 |

## Замеры

- Контраст: не применяется (позы фигур, не текст/кромки).
- ΔE76: не применяется.
- ΔGPU: стенд поз не добавляет контента в кадр (те же шесть фигур) — замер `render_bench.py` не проводился,
  изменений рендера нет.

## Проверка глазами (G-LOOK, AGENTS.md «Look before you report»)

- Каждый PNG листа открыт (Read + анализ кропов 4×): да.
- Сверка с референсом: Arthur LungeAttack к.7 — меч вынесен вперёд-вниз, рука выпрямлена, наклон вперёд —
  совпадает с `art/pipeline-candidates/ASSET-KING-ARTHUR-001/20260929-h2anim/preview/ue/KingArthur-LungeAttack-f07-q34-ue-editor.jpg`
  (проверено парой кропов f00/f07: f00 — замах, меч поднят вверх-назад; f07 — укол вперёд-вниз; одиночный кроп f07
  сверху-вниз читался ошибочно — камера K1 65°).
- Доска — настоящая: Marmoreal original / Sarpedon original (обе, трассы `board=`): да.
- Задник верный: Marmoreal — окраска (concept paste, через `-ConceptPaste`); Sarpedon — lit3d-остров с водопадом
  и огнём: да.
- Все шесть фигур v2 (без серых болванок, раскрашенные миниатюры; figrect 6/6): да.
- Различимо в сером и при дейтеранопии: силуэты поз различимы (G-GRAY): да.

## Что не прошло

- Ничего по критериям карты. Ограничение: одиночные кропы сверху-вниз искажают чтение направления меча —
  вывод делается по паре кадров (f00 против f07), не по одному.
