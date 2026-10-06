# HB-08 — скины HUD 9-slice, CX-02r

Статус: **предложено**. Рекомендую **flat-token-v1 / fix1**: сохранён принятый плоский стиль, все состояния теперь имеют замкнутую кромку; её цвет и цвет тела заменяют прежние разрывы. Всё нарисовано скриптом, без ImageGen и ретуши.

Доработка выполнена; полная приёмка остаётся **не пройдена** из-за одного буквального противоречия карточки: navy-кромка normal primary совпадает с navy-панелью (1:1), хотя к жёлтому телу даёт 10,91:1. Назначенная таблица цветов сохранена; критерий не подменён и зафиксирован в [verification.json](verification.json).

## Состав

- [vector/x1/](vector/x1/) и [vector/x2/](vector/x2/): 29 точных имён в каждом масштабе, всего 58 RGBA PNG; поле — 1 физический прозрачный пиксель.
- [masters/](masters/): 29 прямых векторных рендеров при 4 px/su, без уменьшения мастера для рабочих экспортов.
- [layers/](layers/): отдельный X ошибки 16 su и разделитель 1 su в ×1/×2; разделитель запечён поверх panel.bg.
- [slice-margins.json](slice-margins.json): границы left/top/right/bottom и режим stretch каждого скина, включая мастера.
- [manifest.json](manifest.json): токены, параметры, размеры, хэши и позиции на листах; [runtime-style.json](runtime-style.json): отдельные слои текста и значков.
- [verification.json](verification.json): каждый PNG, палитра и формулы, все серые пары, контрасты, UTF-8, входные хэши и отдельные условия приёмки.
- [generation-records.json](generation-records.json): только финальная сборка; точные процедурные ключи, параметры и SHA-256. [concepts/](concepts/): её неизменённые копии только vector/ и masters/, без листов.
- [source-hashes-before.json](source-hashes-before.json), [fix1-provenance.json](fix1-provenance.json) и [manifest-sha256.json](manifest-sha256.json): происхождение и полные хэши всех файлов обеих разрешённых папок.
- [DESIGN.md](DESIGN.md), [visual-review.json](visual-review.json), [каталог в цвете](comparison/catalog-color.png), [каталог в сером](comparison/catalog-gray.png).

Курсоры перенесены в отдельные задачи IC-58…IC-61; в этом пакете их экспортов и каталогов нет. Исторический раздел ревью Claude в конце оставлен дословно по заданию.

## Состояния и решения по делегированию

ВР-VS2-HB08-01…05 — **по делегированию, решение Claude**. Они исполняются в этом пакете со статусом «предложено».

| Скин | Тело | Кромка, 1 su если не указано иное |
|---|---|---|
| Btn_Normal | #061623, α 0,92 | #F9EBDB, α 0,45 |
| Btn_Hover | #1E2B35, α 0,92 | #F9EBDB, α 1 |
| Btn_Pressed | #040E17, α 0,92 | #F9EBDB, α 1 |
| Btn_Disabled | #061623, α 0,92 | #F9EBDB, α 0,16 |
| Btn_Selected | #0D7A89, α 1 | #FAF8F2, α 1 |
| BtnPrimary_Normal | #F2C14E, α 1 | #061623, α 1 |
| BtnPrimary_Hover | #F3C55B, α 1 | #F9EBDB, α 1 |
| BtnPrimary_Pressed | #D5AA45, α 1 | #F9EBDB, α 1 |
| BtnPrimary_Disabled | #4E5457, α 1 | #061623, α 1 |
| *_Focus | только отдельное кольцо | #FAF8F2, 2 su, зазор 2 su |

ВР-VS2-HB08-01: текст disabled primary — `text.primary` **#F2EDE4**, контраст **6,5976:1** на #4E5457. У остальных primary текст #061623: normal/focus 10,9118:1, hover 11,2912:1, pressed 8,4280:1. Все пять состояний проходят 4,5:1. Текст — отдельный runtime-слой, в PNG его нет.

ВР-VS2-HB08-02: кромка во всех состояниях непрерывна и одинаковой ширины, без вырезов, открытых дуг и пропавших углов. Disabled обычной кнопки приглушён намеренно: неактивный элемент освобождён от порога 3:1 (WCAG 1.4.11, как указано в задании). Runtime: значок α 0,4, текст #B9B2A6, без снижения альфы текста. Минимальная ширина кнопки 120 su, высоты 32/40/48 su; шрифт отдельного текста Roboto Bold Condensed 20 su.

ВР-VS2-HB08-03: тело заполняет весь скруглённый силуэт; полупрозрачная кромка и разделитель накладываются Porter-Duff OVER на собственное тело внутри PNG. Они не лежат поверх прозрачности. Итоговый полупрозрачный скин естественно смешивается с задником, но соотношение кромки с телом больше не зависит от пустого слоя под ней. Формулы, квантование альфы и разрешённые композиты перечислены в `palette.derived`.

Primary hover = 92 % #F2C14E + 8 % #FAF8F2 = #F3C55B; pressed = #F2C14E × 0,88 = #D5AA45; disabled = 40 % #B9B2A6 поверх #061623 = #4E5457, непрозрачная запечённая смесь.

ВР-VS2-HB08-04: Check_Off и Check_On — **24 su**, плюс поле 1 px: 26×26 px при ×1, 50×50 px при ×2. `stretch: none`, каждый slice margin покрывает полный соответствующий размер изображения. На листе каждый checkbox показан один раз в родном размере каждого масштаба; галочка заново растеризована из вектора, не растянута.

ВР-VS2-HB08-05: пакет ограничен скинами HB-08.

## Срезы и сохранённый дизайн

Угол = radius × scale + edge × scale + 1 px. Обычная кнопка: 6/11 px при ×1/×2, панель: 8/15 px, модаль: 10/19 px, warning-тост: 9/17 px. Углы сохраняются побайтно; боковые полосы растягиваются только вдоль края, поперечный профиль и толщина неизменны. Checkbox — фиксированное исключение, срез к нему не применяется.

Focus PNG содержит только кольцо: сначала normal, поверх кольцо с выносом 4 su по каждой стороне, 2 su ширины и 2 su пустого зазора. На листах показана собранная пара normal + ring. Отдельное физическое поле 1 px сохранено.

Радиусы: кнопки, капсулы, теги, чипы — 4 su; панели и тосты — 6 su; модаль — 8 su; тонкие дорожки — 2 su. Warning-тост: оранжевая кромка #E8812C 2 su; предупреждающий значок добавляется отдельно. Input_Error сохраняет малый красный X поверх normal, без красного тела; отдельно поставляется runtime-X 16 su. Тени, буквы, цифры и декоративные текстуры отсутствуют.

## Проверки и ограничения

- **0** непрозрачных пикселей вне ΔE76 ≤ 3 разрешённой палитры, производных цветов и edge-композитов; исключены только переходные пиксели сглаживания рядом с разрешёнными цветами.
- **450/450** серых пар прошли: 15 пар обычной кнопки + 10 пар primary, три размера, три фона, ×1/×2. В каждой записи приведены медианы разницы Rec.709 luma по всему телу и по всей замкнутой кромке; у focus также по полному кольцу. Выбор отдельных контрастных пикселей, разрывы и вырезы не используются.
- Все прямые кромки, углы и кольца проверены при трёх размерах и ×1/×2/×4; topology-check подтверждает один замкнутый контур. Input_Error проверен как нормальная непрерывная кромка с прежним X поверх неё.
- Контраст обычной normal-кромки к panel.bg — 3,9960:1, disabled — 1,5387:1 (допустимое исключение). У активных cream/glyph-кромок к panel.bg — 15,6388/17,2430:1. Не выполнен буквальный порог normal primary к panel.bg: **1:1**; к собственному жёлтому телу **10,9118:1**. Цвет из обязательной таблицы не изменён.
- Все 108 листов растяжения (54 цветных и 54 серых) пересобраны; серый побайтно соответствует Rec.709 luma по кодированным sRGB каналам: 0,2126 R + 0,7152 G + 0,0722 B. PNG сохранены с optimize=True, режим RGBA.
- Все входы и дерево hud-icons-v3 повторно проверены SHA-256; исходники неизменны. Снимок текущего движка побайтно совпадает с оригиналом. `rect_sil`, `Poly`, `poly`, `hx` не изменились; общий AST словаря TOKENS расширен, но все токены, потребляемые скинами, совпадают с предыдущим манифестом.
- Указанный исторический кадр Marmoreal содержит объёмные дворец/деревья и постоянные подписи фигур. Использован именно заданный источник; это сравнение скинов, не приёмка текущего задника. Кропы обеих карт: (300,80)–(1540,680); вписывание в ячейки с сохранением пропорций и центральной обрезкой bicubic.
- Запись ограничена двумя папками задания, `outside_folder: []`. Git-команд нет; файлы unreal/ не открывались, движок и сборки не запускались. Runtime-импорт, шрифты, hitbox и DPI-фильтрация не проверялись в рамках этого пакета.

## Контрольные листы

Три колонки: малый/средний/большой размер. Checkbox показан только в первой колонке, один раз при родном 24 su. ×1/×2 — рабочие масштабы, ×4 — мастер. Все PNG без надписей.

| Страница | Строки сверху вниз |
|---|---|
| 01 | Panel, PanelInset, Modal |
| 02 | Btn Normal, Hover, Pressed, Disabled, Focus, Selected |
| 03 | BtnPrimary Normal, Hover, Pressed, Disabled, Focus |
| 04 | Toast, ToastWarning, Capsule, Tag, Chip, KeyChip |
| 05 | ProgressTrack, ProgressFill, SliderTrack, SliderThumb, Check Off, On |
| 06 | Input Normal, Focus, Error |

### Фон card.navy

| Страница | ×1 | ×2 | Мастер ×4 |
|---|---|---|---|
| 01 | [цвет](comparison/navy-x1-p01-color.png), [серый](comparison/navy-x1-p01-gray.png) | [цвет](comparison/navy-x2-p01-color.png), [серый](comparison/navy-x2-p01-gray.png) | [цвет](comparison/navy-x4-p01-color.png), [серый](comparison/navy-x4-p01-gray.png) |
| 02 | [цвет](comparison/navy-x1-p02-color.png), [серый](comparison/navy-x1-p02-gray.png) | [цвет](comparison/navy-x2-p02-color.png), [серый](comparison/navy-x2-p02-gray.png) | [цвет](comparison/navy-x4-p02-color.png), [серый](comparison/navy-x4-p02-gray.png) |
| 03 | [цвет](comparison/navy-x1-p03-color.png), [серый](comparison/navy-x1-p03-gray.png) | [цвет](comparison/navy-x2-p03-color.png), [серый](comparison/navy-x2-p03-gray.png) | [цвет](comparison/navy-x4-p03-color.png), [серый](comparison/navy-x4-p03-gray.png) |
| 04 | [цвет](comparison/navy-x1-p04-color.png), [серый](comparison/navy-x1-p04-gray.png) | [цвет](comparison/navy-x2-p04-color.png), [серый](comparison/navy-x2-p04-gray.png) | [цвет](comparison/navy-x4-p04-color.png), [серый](comparison/navy-x4-p04-gray.png) |
| 05 | [цвет](comparison/navy-x1-p05-color.png), [серый](comparison/navy-x1-p05-gray.png) | [цвет](comparison/navy-x2-p05-color.png), [серый](comparison/navy-x2-p05-gray.png) | [цвет](comparison/navy-x4-p05-color.png), [серый](comparison/navy-x4-p05-gray.png) |
| 06 | [цвет](comparison/navy-x1-p06-color.png), [серый](comparison/navy-x1-p06-gray.png) | [цвет](comparison/navy-x2-p06-color.png), [серый](comparison/navy-x2-p06-gray.png) | [цвет](comparison/navy-x4-p06-color.png), [серый](comparison/navy-x4-p06-gray.png) |

### Кроп Marmoreal

| Страница | ×1 | ×2 | Мастер ×4 |
|---|---|---|---|
| 01 | [цвет](../../../scraped-data/derived/hud-skins-v1-codex/comparison/marmoreal-x1-p01-color.png), [серый](../../../scraped-data/derived/hud-skins-v1-codex/comparison/marmoreal-x1-p01-gray.png) | [цвет](../../../scraped-data/derived/hud-skins-v1-codex/comparison/marmoreal-x2-p01-color.png), [серый](../../../scraped-data/derived/hud-skins-v1-codex/comparison/marmoreal-x2-p01-gray.png) | [цвет](../../../scraped-data/derived/hud-skins-v1-codex/comparison/marmoreal-x4-p01-color.png), [серый](../../../scraped-data/derived/hud-skins-v1-codex/comparison/marmoreal-x4-p01-gray.png) |
| 02 | [цвет](../../../scraped-data/derived/hud-skins-v1-codex/comparison/marmoreal-x1-p02-color.png), [серый](../../../scraped-data/derived/hud-skins-v1-codex/comparison/marmoreal-x1-p02-gray.png) | [цвет](../../../scraped-data/derived/hud-skins-v1-codex/comparison/marmoreal-x2-p02-color.png), [серый](../../../scraped-data/derived/hud-skins-v1-codex/comparison/marmoreal-x2-p02-gray.png) | [цвет](../../../scraped-data/derived/hud-skins-v1-codex/comparison/marmoreal-x4-p02-color.png), [серый](../../../scraped-data/derived/hud-skins-v1-codex/comparison/marmoreal-x4-p02-gray.png) |
| 03 | [цвет](../../../scraped-data/derived/hud-skins-v1-codex/comparison/marmoreal-x1-p03-color.png), [серый](../../../scraped-data/derived/hud-skins-v1-codex/comparison/marmoreal-x1-p03-gray.png) | [цвет](../../../scraped-data/derived/hud-skins-v1-codex/comparison/marmoreal-x2-p03-color.png), [серый](../../../scraped-data/derived/hud-skins-v1-codex/comparison/marmoreal-x2-p03-gray.png) | [цвет](../../../scraped-data/derived/hud-skins-v1-codex/comparison/marmoreal-x4-p03-color.png), [серый](../../../scraped-data/derived/hud-skins-v1-codex/comparison/marmoreal-x4-p03-gray.png) |
| 04 | [цвет](../../../scraped-data/derived/hud-skins-v1-codex/comparison/marmoreal-x1-p04-color.png), [серый](../../../scraped-data/derived/hud-skins-v1-codex/comparison/marmoreal-x1-p04-gray.png) | [цвет](../../../scraped-data/derived/hud-skins-v1-codex/comparison/marmoreal-x2-p04-color.png), [серый](../../../scraped-data/derived/hud-skins-v1-codex/comparison/marmoreal-x2-p04-gray.png) | [цвет](../../../scraped-data/derived/hud-skins-v1-codex/comparison/marmoreal-x4-p04-color.png), [серый](../../../scraped-data/derived/hud-skins-v1-codex/comparison/marmoreal-x4-p04-gray.png) |
| 05 | [цвет](../../../scraped-data/derived/hud-skins-v1-codex/comparison/marmoreal-x1-p05-color.png), [серый](../../../scraped-data/derived/hud-skins-v1-codex/comparison/marmoreal-x1-p05-gray.png) | [цвет](../../../scraped-data/derived/hud-skins-v1-codex/comparison/marmoreal-x2-p05-color.png), [серый](../../../scraped-data/derived/hud-skins-v1-codex/comparison/marmoreal-x2-p05-gray.png) | [цвет](../../../scraped-data/derived/hud-skins-v1-codex/comparison/marmoreal-x4-p05-color.png), [серый](../../../scraped-data/derived/hud-skins-v1-codex/comparison/marmoreal-x4-p05-gray.png) |
| 06 | [цвет](../../../scraped-data/derived/hud-skins-v1-codex/comparison/marmoreal-x1-p06-color.png), [серый](../../../scraped-data/derived/hud-skins-v1-codex/comparison/marmoreal-x1-p06-gray.png) | [цвет](../../../scraped-data/derived/hud-skins-v1-codex/comparison/marmoreal-x2-p06-color.png), [серый](../../../scraped-data/derived/hud-skins-v1-codex/comparison/marmoreal-x2-p06-gray.png) | [цвет](../../../scraped-data/derived/hud-skins-v1-codex/comparison/marmoreal-x4-p06-color.png), [серый](../../../scraped-data/derived/hud-skins-v1-codex/comparison/marmoreal-x4-p06-gray.png) |

### Кроп Sarpedon

| Страница | ×1 | ×2 | Мастер ×4 |
|---|---|---|---|
| 01 | [цвет](../../../scraped-data/derived/hud-skins-v1-codex/comparison/sarpedon-x1-p01-color.png), [серый](../../../scraped-data/derived/hud-skins-v1-codex/comparison/sarpedon-x1-p01-gray.png) | [цвет](../../../scraped-data/derived/hud-skins-v1-codex/comparison/sarpedon-x2-p01-color.png), [серый](../../../scraped-data/derived/hud-skins-v1-codex/comparison/sarpedon-x2-p01-gray.png) | [цвет](../../../scraped-data/derived/hud-skins-v1-codex/comparison/sarpedon-x4-p01-color.png), [серый](../../../scraped-data/derived/hud-skins-v1-codex/comparison/sarpedon-x4-p01-gray.png) |
| 02 | [цвет](../../../scraped-data/derived/hud-skins-v1-codex/comparison/sarpedon-x1-p02-color.png), [серый](../../../scraped-data/derived/hud-skins-v1-codex/comparison/sarpedon-x1-p02-gray.png) | [цвет](../../../scraped-data/derived/hud-skins-v1-codex/comparison/sarpedon-x2-p02-color.png), [серый](../../../scraped-data/derived/hud-skins-v1-codex/comparison/sarpedon-x2-p02-gray.png) | [цвет](../../../scraped-data/derived/hud-skins-v1-codex/comparison/sarpedon-x4-p02-color.png), [серый](../../../scraped-data/derived/hud-skins-v1-codex/comparison/sarpedon-x4-p02-gray.png) |
| 03 | [цвет](../../../scraped-data/derived/hud-skins-v1-codex/comparison/sarpedon-x1-p03-color.png), [серый](../../../scraped-data/derived/hud-skins-v1-codex/comparison/sarpedon-x1-p03-gray.png) | [цвет](../../../scraped-data/derived/hud-skins-v1-codex/comparison/sarpedon-x2-p03-color.png), [серый](../../../scraped-data/derived/hud-skins-v1-codex/comparison/sarpedon-x2-p03-gray.png) | [цвет](../../../scraped-data/derived/hud-skins-v1-codex/comparison/sarpedon-x4-p03-color.png), [серый](../../../scraped-data/derived/hud-skins-v1-codex/comparison/sarpedon-x4-p03-gray.png) |
| 04 | [цвет](../../../scraped-data/derived/hud-skins-v1-codex/comparison/sarpedon-x1-p04-color.png), [серый](../../../scraped-data/derived/hud-skins-v1-codex/comparison/sarpedon-x1-p04-gray.png) | [цвет](../../../scraped-data/derived/hud-skins-v1-codex/comparison/sarpedon-x2-p04-color.png), [серый](../../../scraped-data/derived/hud-skins-v1-codex/comparison/sarpedon-x2-p04-gray.png) | [цвет](../../../scraped-data/derived/hud-skins-v1-codex/comparison/sarpedon-x4-p04-color.png), [серый](../../../scraped-data/derived/hud-skins-v1-codex/comparison/sarpedon-x4-p04-gray.png) |
| 05 | [цвет](../../../scraped-data/derived/hud-skins-v1-codex/comparison/sarpedon-x1-p05-color.png), [серый](../../../scraped-data/derived/hud-skins-v1-codex/comparison/sarpedon-x1-p05-gray.png) | [цвет](../../../scraped-data/derived/hud-skins-v1-codex/comparison/sarpedon-x2-p05-color.png), [серый](../../../scraped-data/derived/hud-skins-v1-codex/comparison/sarpedon-x2-p05-gray.png) | [цвет](../../../scraped-data/derived/hud-skins-v1-codex/comparison/sarpedon-x4-p05-color.png), [серый](../../../scraped-data/derived/hud-skins-v1-codex/comparison/sarpedon-x4-p05-gray.png) |
| 06 | [цвет](../../../scraped-data/derived/hud-skins-v1-codex/comparison/sarpedon-x1-p06-color.png), [серый](../../../scraped-data/derived/hud-skins-v1-codex/comparison/sarpedon-x1-p06-gray.png) | [цвет](../../../scraped-data/derived/hud-skins-v1-codex/comparison/sarpedon-x2-p06-color.png), [серый](../../../scraped-data/derived/hud-skins-v1-codex/comparison/sarpedon-x2-p06-gray.png) | [цвет](../../../scraped-data/derived/hud-skins-v1-codex/comparison/sarpedon-x4-p06-color.png), [серый](../../../scraped-data/derived/hud-skins-v1-codex/comparison/sarpedon-x4-p06-gray.png) |

## Пересборка и проверка

Из корня проекта, Python с pycairo, NumPy и Pillow:

```powershell
python -B art/imagegen/hud-skins-v1-codex/_tools/draw_skins.py --mode skins
python -B art/imagegen/hud-skins-v1-codex/_tools/verify_skins.py
python -B art/imagegen/hud-skins-v1-codex/_tools/hash_manifest.py
```

Сборка заменяет только финальный прогон в concepts/ этих папок. В derived остаются только backgrounds/ и comparison/ финального прогона; копии концептов туда больше не пишутся. Проверка завершает измерения, а результат приёмки указан в acceptance_pass. Последний шаг обновляет и проверяет хэши всего пакета, включая verification.json.

## Доработка CX-02r (fix1, 2026-10-06)

Исправлены F1–F11: UTF-8 без передачи кириллицы через PowerShell; замкнутые кромки и Porter-Duff OVER; производные primary-цвета и светлый disabled-текст; 450 полных серых пар; native-checkbox; устранён экспорт посторонних ассетов; сохранён только финальный прогон; текущий снимок v3; формат verification.json по 07 §1.2; SHA-256 каждого файла; новая запись прямого визуального осмотра. Прежний раздел Claude ниже сохранён дословно.

Пять прежних прогонов перечислены в pruned_runs с исходным примечанием: moved out of the repo by Claude to C:/tmp/visual/CX-02r/pruned/, not in git. Внешний архив не менялся. concepts/ финальной сборки содержит только vector/ и masters/; у листов нет архивных копий.

Хэш движка изменился после CX-02: `11515374094a2a08b174d0b9b4ef8fb274ec2819168932dc056b5def4ca4c1d7` → `f6d5522d92db0cab030d052037e058c50462c45e1351968951c997801de35354` (additive IC-33/VR44). Новый файл скопирован без изменений; изменение общего TOKENS не затронуло цвета скинов. Финальный run: `20261006T065522441955Z`.

## Ревью Claude (2026-10-06, VS-1, единственный проход, по делегированию)

Итог: **нужна доработка**, не закоммичено. README.md испорчен: кириллица записана как «?» (65 строк), `visual-review.json` тоже содержит «?»; исходный текст есть в журнале Codex `C:/tmp/visual/CX-02/`. На мастерах `T_Skin_BtnPrimary_Pressed` тёмные прямоугольные вырезы в нижних углах, у `T_Skin_Btn_Pressed` кромка разорвана снизу. Текст на disabled primary — 2,39:1 при норме 4,5:1. Курсоры (22 PNG) вне объёма HB-08 (IC-58…IC-61). `scraped-data/derived/hud-skins-v1-codex/` — 614 МБ, оставить только финальный прогон. Остальные 18 проверок из 19 пройдены, запись только в свои папки.

## Ревью Claude CX-02r (2026-10-06, единственный проход, по делегированию)

Итог: **принято по делегированию**. Прогон Codex fix1 (`docs/game-design/visual/06-tasks/prompts/HB-08.fix1.codex.md`,
11:47–11:58, без ImageGen) исправил всё из ревью VS-1: кириллица на месте, кромки замкнуты во всех состояниях,
текст disabled главной кнопки 6,60 : 1, курсоров в пакете нет, `scraped-data/derived/hud-skins-v1-codex/` сокращена
с 614 до 113 МБ (72 листа на задниках и 2 кропа, на которые ссылается README).

Что проверено:
- Рамки. Журнал Codex: правки только в `_tools/` и `visual-review.json` этого пакета, остальное писала сборка с
  защитой путей в две разрешённые папки. Прочие изменения основной копии за время прогона — от параллельных сессий
  (`hud-icons-vr44`, `env-u16-marmoreal`, `hud-composition`, аудио), не от этого прогона; посторонних файлов нет.
  `unreal/` не тронут, индекс пуст. `verification.json`: `source_unchanged: true`, `outside_folder: []`.
- `manifest-sha256.json`: 309 файлов совпали. После добавления этого раздела пересчитан `_tools/hash_manifest.py`;
  счётчик кириллицы README в `verification.json` относится к версии до раздела.
- Открыты глазами: все 29 скинов ×1 (nearest ×8) и ×2 (nearest ×4), цвет и серый, на `card.navy` и на светлом фоне
  `#E2DACD`; листы navy ×1 p02 и p03 (цвет и серый), ×2 p05 серый, каталог; Marmoreal ×1 p02 (цвет и серый) и p03
  (серый); Sarpedon ×1 p03 цвет, ×1 p02 серый, ×2 p02 цвет. Вырезов, разрывов, открытых дуг нет; галочка флажка
  чёткая на ×1 и ×2; текста, цифр, теней, бликов, кисти нет.
- Серые пары, свой замер (медиана Δluma, ×1 и ×2, фоны navy, `#E2DACD`, `#F5F5F5`): Btn Normal–Pressed по кромке
  110–119, Normal–Disabled по кромке 57–63, Hover–Pressed по телу 26; Primary Normal–Hover по кромке 217,
  Normal–Pressed по телу 23, Hover–Pressed по телу 27. Все ≥ 20.
- Контраст: `panel.edge` к `panel.bg` 4,0 : 1; текст главной кнопки 8,43–11,29 : 1, disabled 6,60 : 1.
- Палитра, своя проверка: вне ΔE76 ≤ 3 только сглаживание дуг углов между кромкой и телом (до 8 пикселей на файл
  ×1), сплошных посторонних цветов нет. Производные цвета — по формулам 02 §4.3, записаны в `palette.derived`.
- Бюджет: пакет 3,3 МБ, ×1 ≤ 672 Б, ×2 ≤ 1,6 КБ, набор 34 КБ.

Решения по делегированию (Claude), записаны в карточке HB-08:
- ВР-VS2-HB08-01 — текст disabled главной кнопки `text.primary` на теле `#4E5457` (`card.navy` там 2,4 : 1).
- ВР-VS2-HB08-02 — кромка всегда замкнута; hover и pressed — кромка `card.cream` 1,0 у обеих кнопок; disabled
  обычной — `panel.divider`; hover и pressed главной — `#F3C55B` и `#D5AA45` по 02 §4.3.
- ВР-VS2-HB08-03 — полупрозрачная кромка запекается поверх своего тела, не поверх прозрачности.
- ВР-VS2-HB08-04 — флажок фиксированного размера 24 su, не растягивается.
- ВР-VS2-HB08-05 — курсоры не входят в HB-08 (IC-58…IC-61); прежние прогоны и курсоры перенесены в
  `C:/tmp/visual/CX-02r/pruned/`, не в git.
- ВР-VS2-HB08-06 — единственный невыполненный пункт `verification.json` (`enabled_edge_contrast_to_panel_bg`,
  BtnPrimary_Normal 1 : 1) — ошибка формулировки карточки в CX-02r. Граница главной кнопки к `panel.bg` — её тело
  `#F2C14E` (10,9 : 1, 02 §3.5 «граница кнопки»); navy-кромка отделяет тело и к `panel.bg` не меряется. Пункт
  засчитан, формулировка карточки исправлена после прогона; `acceptance_pass: false` оставлен как запись Codex.

Не входит в пакет: 02 §4.3 (текст disabled главной) и 07 §1.5 (курсоры в шаблоне T-CODEX-9SLICE) не правились;
кадр Marmoreal во входах — с 3D-окружением P5c (известный разрыв ENV-U16), для листов читаемости допустим; импорт в
UE (HB-10) не проверялся.
