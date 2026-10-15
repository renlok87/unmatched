# HUD «Стол»: образцы материалов

Созданы 12 пустых материальных подложек встроенным инструментом `image_gen`: по четыре для R3, M2 и M3. Это только материалы; игровые данные, иллюстрации героев и интерфейсная компоновка не добавлялись. Выполнено 13 вызовов инструмента: 12 исходных генераций и одна корректирующая правка.

- `R3/` — матовый тёмный картон, кремовый обрез, тональный меандр и зерно печати.
- `M2/` — тёмный картон, более заметная фактура бумаги, тонкая линия охристой краски.
- `M3/` — тёмный зелёно-серый мрамор и патинированная бронза на карточке героя. Фраза «only for hero cards» применена буквально: сопутствующие компоненты — картон и бумага в зелёно-серой гамме с бронзовым цветом кромки.
- Все `pile-slip.png` — кремовая бумага с небольшим загибом.
- `swatch-sheet.png` — 1600×1200, тёмный фон, слева направо R3 → M2 → M3, без подписей.
- `review/alpha-on-light.png` — дополнительный просмотр прозрачности на светлом фоне.
- `raw/` — 13 неизменённых результатов ImageGen, включая отклонённый вариант полосы.
- `prompts.json` — точные промпты, пути исходников и история правки.
- `validation.json` — размеры, обрезка, SHA-256 и результаты технической проверки.

## Нормализация

`normalize.py` использует Python/Pillow и NumPy. Материал взят из генераций, без подмены одноцветными заливками. Удалены внешние поля и остатки теней; заданы точные размеры и сглаженные маски. У карточек радиус внешнего контура 20 px. Кремовый обрез R3-карточки расширен до 20 px (2,38% ширины) из сгенерированного образца бумаги; тёмная часть также взята из исходной генерации.

Окна дисков отцентрованы радиальным пересэмплированием до диаметра около 118 px (46% от 256). Кремовый центр непрозрачен. Средние 80% каждой полосы: `x ∈ [120,1080)`, период 240 px, четыре повторения. Период собран из сгенерированной фактуры и её зеркального продолжения. Граничные столбцы средней области совпадают точно; внешние торцы не предназначены для повторения.

| Подложка | Raw, px | Итог, px | Осмотр: текст / цифры / логотипы |
|---|---:|---:|---|
| `R3/hero-card-plate.png` | 1894×830 | 840×368 | отсутствуют |
| `R3/hp-dial.png` | 1254×1254 | 256×256 | отсутствуют |
| `R3/pile-slip.png` | 2048×768 | 240×64 | отсутствуют |
| `R3/question-strip.png` | 1464×1074 | 1200×88 | отсутствуют |
| `M2/hero-card-plate.png` | 1894×830 | 840×368 | отсутствуют |
| `M2/hp-dial.png` | 1254×1254 | 256×256 | отсутствуют |
| `M2/pile-slip.png` | 1983×793 | 240×64 | отсутствуют |
| `M2/question-strip.png` | 1464×1074 | 1200×88 | отсутствуют |
| `M3/hero-card-plate.png` | 1894×830 | 840×368 | отсутствуют |
| `M3/hp-dial.png` | 1254×1254 | 256×256 | отсутствуют |
| `M3/pile-slip.png` | 1983×793 | 240×64 | отсутствуют |
| `M3/question-strip.png` | 1464×1075 | 1200×88 | отсутствуют |

## Самопроверка и исправления

Каждый из 12 итоговых PNG открыт и осмотрен отдельно. Обе сборные таблицы также открыты и осмотрены. Текста, букв, цифр, логотипов, иконок, персонажей и игровых данных не обнаружено. Узор — геометрический меандр. Кремовые окна дисков и бумажные ярлыки пустые. Вне контура — прозрачность, внешних теней нет. Обводка M2 читается как охристая краска, а не металлическая фольга.

`moderation_blocked`: нет. Ошибок вызовов ImageGen: нет.

Замечания, исправленные в этой работе:

- Исходный R3-ярлык содержал полупрозрачную внешнюю тень; она удалена обрезкой и маской.
- Первая полоса M3 получила мраморные прожилки вопреки ограничению «only for hero cards». Через ImageGen выполнена правка материала на матовый печатный картон. Отклонённый исходник сохранён как `raw/M3/question-strip-rejected-marble.png` (1464×1074).
- Первая попытка нормализации R3-диска ошибочно включила светлый внешний обрез в измерение окна, что визуально исказило кольцо. После просмотра PNG алгоритм исправлен: измеряется только непрерывная светлая область центра. Все итоговые диски пересобраны и повторно осмотрены; добавлена проверка диаметра.

Коммиты не выполнялись. Все результаты и вспомогательные файлы находятся в каталоге задания; исходный `PROMPT.codex.md` не изменялся.

## Точные промпты

Каждый вызов использовал `transparent_background=true`. Генерации выполнялись по одной подложке на вызов. Для правки полосы M3 исходный PNG передан как `referenced_image_paths`; остальные вызовы не имели референсных изображений.

### R3/hero-card-plate.png

```text
Use case: product-mockup. Asset type: blank material-only raster plate for a board-game HUD. One isolated component, perfectly face-on orthographic top view, no perspective, no table or background, actual transparent alpha outside its silhouette. Fill the canvas with the single shape leaving a small clear margin. Gentle illumination from top-left, no cast shadow or contact shadow outside the shape. Entire surface blank for later code composition; absolutely NO text, letters, numbers, icons, logos, watermarks, game data, characters, art panels, laurels or ornamental emblems. Material detail must be visible, refined, restrained. Never copy an existing game asset.
Family R3: printed component canon. Near-black navy matte card stock (#14161C / #061623), tiny irregular screen-print/riso grain, cream die-cut paper edge (#ECE3CF / #F9EBDB) 2–3 percent of full width. Interior Greek meander repeated pattern at ONLY six percent tonal contrast, dark and subdued. Flat printed ink, no bevel, no metallic shine, no glow.
Generate ONE hero-card plate, an EMPTY landscape rounded rectangle, width:height exactly 840:368, corner radius proportional to 20 px at 840 width. Continuous same material across whole card including the left area. Thin cream edge smoothly follows rounded corners, substantial dark interior. No divisions or inset panels. No shadow.
```

### R3/hp-dial.png

```text
Use case: product-mockup. Asset type: blank material-only raster plate for a board-game HUD. One isolated component, perfectly face-on orthographic top view, no perspective, no table or background, actual transparent alpha outside its silhouette. Fill the canvas with the single shape leaving a small clear margin. Gentle illumination from top-left, no cast shadow or contact shadow outside the shape. Entire surface blank for later code composition; absolutely NO text, letters, numbers, icons, logos, watermarks, game data, characters, art panels, laurels or ornamental emblems. Material detail must be visible, refined, restrained. Never copy an existing game asset.
Family R3, printed component canon: near-black navy matte card stock (#14161C / #061623), tiny screen-print/riso grain, a cream die-cut paper edge (#ECE3CF / #F9EBDB) 2–3 percent of the full width. Very subdued dark-on-dark Greek meander at only SIX percent tonal contrast. Flat printed inks. NO bevel, metallic shine, glow or faux 3D trim.
Generate ONE circular health dial, width:height 1:1 for final 256x256. Two stacked die-cut CARDBOARD discs, only a slight offset and visible paper thickness, with outer ring in the family material. Perfectly centred PLAIN CREAM PAPER circular window, diameter exactly 46 percent of the complete disc diameter, opaque warm cream, absolutely blank. Tiny understated fastener/rivet hint within the outer ring near twelve o'clock, NOT in the central blank window. Entire disc unmarked; no ticks, scale, numerals, icons or arrows. Perfect top view, no perspective, no external shadow.
```

### R3/pile-slip.png

```text
Use case: product-mockup. Asset type: blank material-only raster plate for a board-game HUD. One isolated component, perfectly face-on orthographic top view, no perspective, no table or background, actual transparent alpha outside its silhouette. Fill the canvas with the single shape leaving a small clear margin. Gentle illumination from top-left, no cast shadow or contact shadow outside the shape. Entire surface blank for later code composition; absolutely NO text, letters, numbers, icons, logos, watermarks, game data, characters, art panels, laurels or ornamental emblems. Material detail must be visible, refined, restrained. Never copy an existing game asset.
Family R3, printed component canon: near-black navy matte card stock (#14161C / #061623), tiny screen-print/riso grain, a cream die-cut paper edge (#ECE3CF / #F9EBDB) 2–3 percent of the full width. Very subdued dark-on-dark Greek meander at only SIX percent tonal contrast. Flat printed inks. NO bevel, metallic shine, glow or faux 3D trim.
Generate ONE small EMPTY cream-paper count tag/slip, width:height 240:64. Warm cream (#ECE3CF / #F9EBDB) matte paper with subtle natural fibre grain, clean rounded die-cut shape, tiny restrained curl at one end visible only within its silhouette; no cast shadow. Use family-associated very subtle paper character but keep the slip CREAM paper. Entire surface unprinted, blank: no pattern, border decoration, holes, fastener, text, numbers or symbols. Very wide and shallow shape in straight top view.
```

### R3/question-strip.png

```text
Use case: product-mockup. Asset type: blank material-only raster plate for a board-game HUD. One isolated component, perfectly face-on orthographic top view, no perspective, no table or background, actual transparent alpha outside its silhouette. Fill the canvas with the single shape leaving a small clear margin. Gentle illumination from top-left, no cast shadow or contact shadow outside the shape. Entire surface blank for later code composition; absolutely NO text, letters, numbers, icons, logos, watermarks, game data, characters, art panels, laurels or ornamental emblems. Material detail must be visible, refined, restrained. Never copy an existing game asset.
Family R3, printed component canon: near-black navy matte card stock (#14161C / #061623), tiny screen-print/riso grain, a cream die-cut paper edge (#ECE3CF / #F9EBDB) 2–3 percent of the full width. Very subdued dark-on-dark Greek meander at only SIX percent tonal contrast. Flat printed inks. NO bevel, metallic shine, glow or faux 3D trim.
Generate ONE EMPTY long, thin horizontal material strip, width:height 1200:88. Straight parallel horizontal edges, subtly rounded ends, no curled corners. Material and grain from the family. Any edge line only on the top and bottom plus ends. The middle EIGHTY percent is a uniform repeating texture with no central motif, no lighting gradient horizontally, no unique stains or changing border details: it must tile horizontally. No divisions, ornaments or layout. Material texture only, nothing printed as content.
```

### M2/hero-card-plate.png

```text
Use case: product-mockup. Asset type: blank material-only raster plate for a board-game HUD. One isolated component, perfectly face-on orthographic top view, no perspective, no table or background, actual transparent alpha outside its silhouette. Fill the canvas with the single shape leaving a small clear margin. Gentle illumination from top-left, no cast shadow or contact shadow outside the shape. Entire surface blank for later code composition; absolutely NO text, letters, numbers, icons, logos, watermarks, game data, characters, art panels, laurels or ornamental emblems. Material detail must be visible, refined, restrained. Never copy an existing game asset.
Family M2, dark stock plus gold thread: near-black navy matte card stock (#14161C / #061623), slightly heavier natural paper grain, extremely subtle dark-on-dark tonal Greek meander. Edge is exactly ONE thin flat ochre-gold PRINTED INK line (#C9A45C); it is NOT metallic foil or metal. NO bevel, shine, glow, decorative double frames or corner ornaments.
Generate ONE hero-card plate: EMPTY landscape rounded rectangle, width:height 840:368, rounded corner radius equivalent to 20 px at 840 width. Same continuous material across the entire card, including its left side. No panels, divisions, art slot or layout. No external shadow.
```

### M2/hp-dial.png

```text
Use case: product-mockup. Asset type: blank material-only raster plate for a board-game HUD. One isolated component, perfectly face-on orthographic top view, no perspective, no table or background, actual transparent alpha outside its silhouette. Fill the canvas with the single shape leaving a small clear margin. Gentle illumination from top-left, no cast shadow or contact shadow outside the shape. Entire surface blank for later code composition; absolutely NO text, letters, numbers, icons, logos, watermarks, game data, characters, art panels, laurels or ornamental emblems. Material detail must be visible, refined, restrained. Never copy an existing game asset.
Family M2, dark stock plus gold thread: near-black navy matte card stock (#14161C / #061623), slightly heavier natural paper grain, extremely subtle dark-on-dark tonal Greek meander. Edge is exactly ONE thin flat ochre-gold PRINTED INK line (#C9A45C); it is NOT metallic foil or metal. NO bevel, shine, glow, decorative double frames or corner ornaments.
Generate ONE circular health dial, width:height 1:1 for final 256x256. Two stacked die-cut CARDBOARD discs, only a slight offset and visible paper thickness, with outer ring in the family material. Perfectly centred PLAIN CREAM PAPER circular window, diameter exactly 46 percent of the complete disc diameter, opaque warm cream, absolutely blank. Tiny understated fastener/rivet hint within the outer ring near twelve o'clock, NOT in the central blank window. Entire disc unmarked; no ticks, scale, numerals, icons or arrows. Perfect top view, no perspective, no external shadow.
```

### M2/pile-slip.png

```text
Use case: product-mockup. Asset type: blank material-only raster plate for a board-game HUD. One isolated component, perfectly face-on orthographic top view, no perspective, no table or background, actual transparent alpha outside its silhouette. Fill the canvas with the single shape leaving a small clear margin. Gentle illumination from top-left, no cast shadow or contact shadow outside the shape. Entire surface blank for later code composition; absolutely NO text, letters, numbers, icons, logos, watermarks, game data, characters, art panels, laurels or ornamental emblems. Material detail must be visible, refined, restrained. Never copy an existing game asset.
Family M2, dark stock plus gold thread: near-black navy matte card stock (#14161C / #061623), slightly heavier natural paper grain, extremely subtle dark-on-dark tonal Greek meander. Edge is exactly ONE thin flat ochre-gold PRINTED INK line (#C9A45C); it is NOT metallic foil or metal. NO bevel, shine, glow, decorative double frames or corner ornaments.
Generate ONE small EMPTY cream-paper count tag/slip, width:height 240:64. Warm cream (#ECE3CF / #F9EBDB) matte paper with subtle natural fibre grain, clean rounded die-cut shape, tiny restrained curl at one end visible only within its silhouette; no cast shadow. Use family-associated very subtle paper character but keep the slip CREAM paper. Entire surface unprinted, blank: no pattern, border decoration, holes, fastener, text, numbers or symbols. Very wide and shallow shape in straight top view.
```

### M2/question-strip.png

```text
Use case: product-mockup. Asset type: blank material-only raster plate for a board-game HUD. One isolated component, perfectly face-on orthographic top view, no perspective, no table or background, actual transparent alpha outside its silhouette. Fill the canvas with the single shape leaving a small clear margin. Gentle illumination from top-left, no cast shadow or contact shadow outside the shape. Entire surface blank for later code composition; absolutely NO text, letters, numbers, icons, logos, watermarks, game data, characters, art panels, laurels or ornamental emblems. Material detail must be visible, refined, restrained. Never copy an existing game asset.
Family M2, dark stock plus gold thread: near-black navy matte card stock (#14161C / #061623), slightly heavier natural paper grain, extremely subtle dark-on-dark tonal Greek meander. Edge is exactly ONE thin flat ochre-gold PRINTED INK line (#C9A45C); it is NOT metallic foil or metal. NO bevel, shine, glow, decorative double frames or corner ornaments.
Generate ONE EMPTY long, thin horizontal material strip, width:height 1200:88. Straight parallel horizontal edges, subtly rounded ends, no curled corners. Material and grain from the family. Any edge line only on the top and bottom plus ends. The middle EIGHTY percent is a uniform repeating texture with no central motif, no lighting gradient horizontally, no unique stains or changing border details: it must tile horizontally. No divisions, ornaments or layout. Material texture only, nothing printed as content.
```

### M3/hero-card-plate.png

```text
Use case: product-mockup. Asset type: blank material-only raster plate for a board-game HUD. One isolated component, perfectly face-on orthographic top view, no perspective, no table or background, actual transparent alpha outside its silhouette. Fill the canvas with the single shape leaving a small clear margin. Gentle illumination from top-left, no cast shadow or contact shadow outside the shape. Entire surface blank for later code composition; absolutely NO text, letters, numbers, icons, logos, watermarks, game data, characters, art panels, laurels or ornamental emblems. Material detail must be visible, refined, restrained. Never copy an existing game asset.
Family M3, marble plus bronze. For HERO CARD ONLY: authentic dark green-grey polished marble with natural delicate branching veins, a thin patinated bronze rim, base #8C6B3F, subdued highlight on upper-left, patina in recesses. Tasteful minimal museum plaque, not souvenir kitsch, no ornate decorations. For accompanying dial and question strip use physically sensible matte dark green-grey printed CARDBOARD and a thin flat bronze-coloured ink edge: marble slabs and metal rims are reserved for the hero card. Pile slip is cream paper.
Generate ONE hero-card plate: EMPTY landscape rounded rectangle, width:height 840:368, rounded corner radius equivalent to 20 px at 840 width. Same continuous material across the entire card, including its left side. No panels, divisions, art slot or layout. No external shadow.
```

### M3/hp-dial.png

```text
Use case: product-mockup. Asset type: blank material-only raster plate for a board-game HUD. One isolated component, perfectly face-on orthographic top view, no perspective, no table or background, actual transparent alpha outside its silhouette. Fill the canvas with the single shape leaving a small clear margin. Gentle illumination from top-left, no cast shadow or contact shadow outside the shape. Entire surface blank for later code composition; absolutely NO text, letters, numbers, icons, logos, watermarks, game data, characters, art panels, laurels or ornamental emblems. Material detail must be visible, refined, restrained. Never copy an existing game asset.
Family M3, marble plus bronze. For HERO CARD ONLY: authentic dark green-grey polished marble with natural delicate branching veins, a thin patinated bronze rim, base #8C6B3F, subdued highlight on upper-left, patina in recesses. Tasteful minimal museum plaque, not souvenir kitsch, no ornate decorations. For accompanying dial and question strip use physically sensible matte dark green-grey printed CARDBOARD and a thin flat bronze-coloured ink edge: marble slabs and metal rims are reserved for the hero card. Pile slip is cream paper.
Generate ONE circular health dial, width:height 1:1 for final 256x256. Two stacked die-cut CARDBOARD discs, only a slight offset and visible paper thickness, with outer ring in the family material. Perfectly centred PLAIN CREAM PAPER circular window, diameter exactly 46 percent of the complete disc diameter, opaque warm cream, absolutely blank. Tiny understated fastener/rivet hint within the outer ring near twelve o'clock, NOT in the central blank window. Entire disc unmarked; no ticks, scale, numerals, icons or arrows. Perfect top view, no perspective, no external shadow.
```

### M3/pile-slip.png

```text
Use case: product-mockup. Asset type: blank material-only raster plate for a board-game HUD. One isolated component, perfectly face-on orthographic top view, no perspective, no table or background, actual transparent alpha outside its silhouette. Fill the canvas with the single shape leaving a small clear margin. Gentle illumination from top-left, no cast shadow or contact shadow outside the shape. Entire surface blank for later code composition; absolutely NO text, letters, numbers, icons, logos, watermarks, game data, characters, art panels, laurels or ornamental emblems. Material detail must be visible, refined, restrained. Never copy an existing game asset.
Family M3, marble plus bronze. For HERO CARD ONLY: authentic dark green-grey polished marble with natural delicate branching veins, a thin patinated bronze rim, base #8C6B3F, subdued highlight on upper-left, patina in recesses. Tasteful minimal museum plaque, not souvenir kitsch, no ornate decorations. For accompanying dial and question strip use physically sensible matte dark green-grey printed CARDBOARD and a thin flat bronze-coloured ink edge: marble slabs and metal rims are reserved for the hero card. Pile slip is cream paper.
Generate ONE small EMPTY cream-paper count tag/slip, width:height 240:64. Warm cream (#ECE3CF / #F9EBDB) matte paper with subtle natural fibre grain, clean rounded die-cut shape, tiny restrained curl at one end visible only within its silhouette; no cast shadow. Use family-associated very subtle paper character but keep the slip CREAM paper. Entire surface unprinted, blank: no pattern, border decoration, holes, fastener, text, numbers or symbols. Very wide and shallow shape in straight top view.
```

### M3/question-strip.png

Первоначальный промпт (результат отклонён):

```text
Use case: product-mockup. Asset type: blank material-only raster plate for a board-game HUD. One isolated component, perfectly face-on orthographic top view, no perspective, no table or background, actual transparent alpha outside its silhouette. Fill the canvas with the single shape leaving a small clear margin. Gentle illumination from top-left, no cast shadow or contact shadow outside the shape. Entire surface blank for later code composition; absolutely NO text, letters, numbers, icons, logos, watermarks, game data, characters, art panels, laurels or ornamental emblems. Material detail must be visible, refined, restrained. Never copy an existing game asset.
Family M3, marble plus bronze. For HERO CARD ONLY: authentic dark green-grey polished marble with natural delicate branching veins, a thin patinated bronze rim, base #8C6B3F, subdued highlight on upper-left, patina in recesses. Tasteful minimal museum plaque, not souvenir kitsch, no ornate decorations. For accompanying dial and question strip use physically sensible matte dark green-grey printed CARDBOARD and a thin flat bronze-coloured ink edge: marble slabs and metal rims are reserved for the hero card. Pile slip is cream paper.
Generate ONE EMPTY long, thin horizontal material strip, width:height 1200:88. Straight parallel horizontal edges, subtly rounded ends, no curled corners. Material and grain from the family. Any edge line only on the top and bottom plus ends. The middle EIGHTY percent is a uniform repeating texture with no central motif, no lighting gradient horizontally, no unique stains or changing border details: it must tile horizontally. No divisions, ornaments or layout. Material texture only, nothing printed as content.
```

Корректирующий промпт (итоговый вариант):

```text
Use case: precise-object-edit. Edit target: the supplied isolated blank long thin strip. Keep the long thin shape, blank surface, actual transparent background, top view, no text, no icons and no exterior shadow. Change ONLY its material: remove ALL marble veins and ALL metal or metallic highlight. This companion strip is MATTE DARK GREEN-GREY PAPER CARD STOCK with tiny natural paper grain. It is printed cardboard, near-black muted green-grey, NOT stone. A SINGLE very thin FLAT bronze-coloured INK line (#8C6B3F) follows the edge. This line has zero metallic shine or bevel. Very subtle dark-on-dark meander pattern at 6 percent contrast is allowed. Central 80 percent horizontally uniform and repeatable, no distinctive features. This family reserves actual marble and bronze for its hero-card plate only; this strip must be printed paper.
```
