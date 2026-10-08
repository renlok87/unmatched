# AN-31 — лист приёмки

Лист собран `tools/art/visual/sheet.py` 2026-10-07 по 02-visual-design.md §13.2 (переснят после ревью Z-1).

**Решение:** художественно принято, по делегированию (2026-10-07, ВР-07, ВР-72, ВР-Z1R-03; пометка ZCode от
2026-10-06 снята ВР-Z1R-06 — цифры на её кадрах не было)
**Дата решения:** 2026-10-07
**Ревью:** визуальный чат, ревью Z-1 + один проход по кадрам (02 §13.3)
**Флаг отката:** `-S08BaseDigitLegacy` (S08ArtLook.h, трасса ARTLOOK `baseDigit=on|legacy(-S08BaseDigitLegacy)`)

## Что было не так (ревью 2026-10-07)

На кадрах ZCode — чёрный диск ≈ 14 px без цифры. Причины: (1) `UTextRenderComponent` не рисует runtime-шрифты
вовсе (`FTextRenderSceneProxy::CreateRenderThreadResources` выходит сразу), а ZCode собрал transient runtime UFont;
(2) поворот `MakeFromZY(-Dir, Up)` ставил текст ребром; (3) геометрия ВР-AN08 свешивалась за кромку и лежала под
когтями, цифра выходила ≈ 6 px; (4) Place-перенос не прятал цифру; (5) камера бралась из устаревшего POV.
Строки «диск 61–102 px, цифра 36–61 px» и «скрытие покрыто юнит-тестом» были неверны.

## Что сделано

- Шрифт: офлайн distance-field `F_UM_RobotoBoldCondensed_Offline` (Roboto Bold Condensed, цифры 0–9, em 32 px ×16
  supersample, страница 256×42). `UTrueTypeFontFactory` в UE 5.8 есть; его опции (`FFontImportOptionsData`) не
  видны питону, поэтому их заполняет editor-only `US08BaseDigitAuthoringLibrary` (`S08BaseDigitAuthoring.*`),
  а TTF виден GDI только внутри процесса редактора (`AddFontResourceExW FR_PRIVATE`, ничего не установлено).
  Скрипт: `python tools/art/hero/base_digit_import.py`.
- Материалы: диск `M_UM_BaseDigit` — unlit, EyeAdaptationInverse(Color) (правило игрового слоя); цифра
  `M_UM_BaseDigitText` — unlit masked (clip 0,5 по distance field), EyeAdaptationInverse(Color = card.cream).
- Геометрия ВР-Z1R-03: диск ⌀ 0,5 диаметра верхней грани (11 uu), центр на 0,48 R, цифра em 0,9 диска (cap 7,1 uu),
  по центру, плашмя (нормаль +Z), верх цифры от камеры, не зеркально. Сторона: по правилу крыла ВР-Z1R-03 —
  зеркальная (поворот −60°, к смещению покоя): при +60° ближнее крыло закрывало > 25 % диска (A/B кадры
  `C:/tmp/visual/Z-1/ab-turn{60,0,-60,90}`), при −60° все шесть цифр читаются; ревью-параметр
  `-S08BaseDigitTurn=<deg>` для A/B.
- Скрыта на весь Place-перенос (D3) и с начала растворения; место пересчитывается при apply, повороте покоя и
  конце хода; камера — `AS08BoardActor::ViewCameraLocation` (D4).

## Что проверено — packaged `-Bench`, stamp `45a3c4e9`, обе карты

- Трассы: `ARTPREVIEW basedigit fighter=f-0-sk0 n=1 / f-0-sk1 n=2 / f-0-sk2 n=3 … discUU=11.0 capUU=7.1
  topRadiusUU=11.0 turn=-60 drawable=1 font=F_UM_RobotoBoldCondensed_Offline` на обеих картах; номера совпадают
  с тегом (`HarpyNumber` = последняя цифра Label) и с бейджем портрета VS-2 (`UmHudPanel::SidekickNumber`, тест).
- K2×1,6 в фокусе каждой гарпии (`-BenchClipPose=Idle@12 -BenchClipPoseFighter=f-0-sk0|1|2`, 6 прогонов):
  цифры 1, 2, 3 читаются в цвете, сером и при дейтеранопии (лист 2); высота цифры ≈ 11 px, диск ≈ 19–20 px
  (замер по сетке 5 px, лист 1) — критерий ≥ 9 px выполнен. Коготь касается края диска у «1», цифра не закрыта.
- K1 (обе карты, лист 3): диск ≈ 12 px, виден (критерий ≥ 8 px); цифра на K1 даже различима, но по карточке её
  несёт тег HUD.
- K2×2,5 (лист 4): цифра крупная, без ступенек (distance field).
- Диск у кромки к камере, внутри верхней грани, не на кольце команды; при `-S08BaseDigitLegacy` компонентов нет.
- Живой бой: см. README AN-24/AN-25 (те же прогоны) — диски с цифрами 1–3 на результатных кадрах.

### Тесты

`Unmatched.S08.HeroesV2.HarpyNumber` (+ сверка с бейджем HUD), `.BaseDigitPlacement` (нормаль·Z > 0,99, диск
внутри грани, верх глифа от камеры, не зеркально, сторона, подъём над диском ≥ 0,3 uu), `.BaseDigitStates`
(офлайн-шрифт, цифра видна у живой гарпии, скрыта весь Place-перенос и с начала растворения) — PASS.

### ΔGPU (render_bench.py, K1, без капа, 3 повторности; `C:/tmp/visual/Z-1/cost-summary.json`)

| карта | ветка (v2.4, цифры, MID) | fix/admin-panel `230b2b0d` (v2.3) | Δ |
|---|---|---|---|
| Marmoreal | 2,500 мс (2,51/2,49/2,50) | 2,510 мс (2,51/2,51/2,51) | −0,010 |
| Sarpedon | 2,620 мс (2,62/2,62/2,62) | 2,637 мс (2,64/2,64/2,63) | −0,017 |

Обе в пределах шума и ≤ 0,05 мс; все SHOT `reference=1`.

## Состав листа

| № | Пункт | Файлы | Есть |
|---|---|---|---|
| 2 | Цвет, серый, дейтеранопия | `sheet-01..04` | да |
| 3 | Обе настоящие доски, packaged | 2 K2×1,6 × 6 гарпий, 3 K1 × 6, 4 K2×2,5 | да |
| 5 | Размер на рабочем виде | 1 сетка 5 px | да |
| 6 | Трассы | `ARTPREVIEW basedigit … drawable=1`, ARTLOOK `baseDigit=on` | да |
| 7 | README | этот файл | да |

## Входы

Прогоны: `C:/tmp/visual/Z-1/shots/{marmoreal,sarpedon}-{plain,digit-f-0-sk0,digit-f-0-sk1,digit-f-0-sk2}/`.
Кропы — `C:/tmp/visual/Z-1/sheets-in/AN-31/` (sha256 в `sheet-manifest.json`).

## Что не прошло

- Ничего по критериям. Без цифры в Label бейдж HUD пуст (0), а диск показывает 1 — расхождение по замыслу
  (в игре метка всегда с номером), записано в Z-1 README как хвост HUD-линии.

## VS-8 A1 — доработка размещения (ВР-Z1R-09 → ВР-VS8-01), 2026-10-08

**Решение:** принято по делегированию (ВР-VS8-01), ветка `feat/visual-vs8`, editor `-game` (live tune / `-Bench`), без упаковки.

Было (Z-1, ВР-Z1R-03): диск ⌀ 0,5 верхней грани, центр 0,48 R, поворот −60°, em 0,9 — диск доходил до центра подставки,
ноги и когти закрывали верх «2» и «3» на K2×1,6, «3» читалась как «5».

Стало (`S08HeroesV2.h`): диск ⌀ **0,40** верхней грани (8,8 uu), центр **0,58 R** (внутренний край 0,38 R от центра,
внешний 0,98 R), поворот **−25°** (передняя кромка, к смещению покоя), em **1,05** диска (cap 6,7 uu). Выбор — A/B трёх
геометрий на Sarpedon K2×1,6 одной сборкой (ревью-параметры `-S08BaseDigitDisc=` / `-S08BaseDigitCentre=` /
`-S08BaseDigitEm=` рядом с `-S08BaseDigitTurn=`): −60° / 0,56 R — «3» всё ещё «5»; −40° — «1» касается когтя; **−25° /
0,58 R — все три чисто** ([vs8-ab-geometry-sarpedon-K2x1p6.jpg](vs8-ab-geometry-sarpedon-K2x1p6.jpg)).
Откат прежний: `-S08BaseDigitLegacy` (компонентов нет). Трасса `ARTPREVIEW basedigit … discUU=8.8 capUU=6.7 … turn=-25
centre=0.58 drawable=1`.

| Проверка | Marmoreal | Sarpedon |
|---|---|---|
| K2×1,6 (все три гарпии в кадре): 1, 2, 3 в цвете и сером, = n трассы | да | да |
| высота цифры K2×1,6 (≥ 9 px) | ≈ 11 px (тот же масштаб, глазом по сетке) | 11–12 px (замер по маске диска), диск 18–20 px |
| K1: диск (≥ 8 px), цифра | ≈ 10 px, цифра различима | 9–10 px, цифра различима |
| K2×2,5 | читается; у «2» коготь касается левого верха цифры | читается, когти вне диска |
| диск на кромке к камере, не на кольце команды | да | да |

Листы: до / после K2×1,6 ([vs8-before-after-K2x1p6-marm-sarp.jpg](vs8-before-after-K2x1p6-marm-sarp.jpg): строки 1–2 —
Z-1, 3–4 — VS-8), [K1](vs8-K1-marm-sarp.jpg), [K2×2,5](vs8-K2x2p5-marm-sarp.jpg); G-LOOK —
[Marmoreal K1](vs8-look-marmoreal-K1.jpg) (вклейка, `backdrop=paste(default)`), [Sarpedon K1](vs8-look-sarpedon-K1.jpg)
(`backdrop=lit3d(default)`), шесть фигур v2. Кадры прогонов: `C:/tmp/visual/VS8/A1/runs/{marmoreal-final,sarpedon-on-base}`,
A/B — `C:/tmp/visual/VS8/A1/ab/`.

Тесты: `Unmatched.S08.HeroesV2.BaseDigitPlacement` (новые размеры, внутренний край ≥ 0,15 R от центра, сторона по знаку
поворота), `.BaseDigitStates`, `.HarpyNumber` — PASS (58/58 в прогоне шага). ΔGPU не перемерялась: те же два примитива
на гарпию, меняются только размеры и место (правило «без оптимизаций», 2026-10-08); последний замер — выше (≤ 0,05 мс).

Остаток: на K2×2,5 Marmoreal коготь гарпии 2 касается левого верха «2» — цифра читается, не правилось (скорость спринта).
