# SEL — выбор героя, выбор поля и VS

> **Валидация Opus xhigh (2026-10-16, `docs/game-design/select-screens/04-REVIEW-OPUS.md`):** PASS-WITH-FIXES, цель
> реализации — вариант A. Живописные фигуры на референсах — только композиция: в игре в нишах стоят SkeletalMesh v2
> (`S08HeroesV2`), ImageGen-арт в нишу не ставится никогда (AGENTS.md «Heroes»).

Дата: 2026-10-16. Восемь референсов: четыре состояния × два варианта. Все финальные изображения — **1920×1080 RGB PNG**. Генерация выполнена встроенным ImageGen; надписи и реальные карты добавлены отдельным проходом Python/Pillow.

[Контактный лист](refs/contact-sheet.png): 960×1080, 2 колонки × 4 строки, каждый кадр 480×270. Слева A «studio», справа B «table»; сверху вниз R1, R2, R3, R4.

## Исходники и правила сборки

- Спецификация: `docs/game-design/select-screens/02-DESIGN.md`, §3–§5. Просмотрены также принятый HUD `docs/game-design/hud-redesign/blind-s20/A.jpg` и старый экран `docs/game-design/hud-redesign/frames/live-s3-room.jpg`.
- Материал: `art/imagegen/hud-table-materials-codex/M3/hero-card-plate.png`. Использован и как материал-референс ImageGen, и как реальная текстура при композитинге плашек.
- Лики: `art/imagegen/hero-quality-v1/king-arthur/king-arthur-front.png` и `art/imagegen/hero-quality-v1/medusa/medusa-front.png`. Оба front переданы в каждую генерацию. Из этих же fronts вырезаны портреты ростера. Fronts Мерлина и гарпии просмотрены; помощники обозначены текстом, в витринах стоят только герои (§6 спецификации).
- Карты: `docs/game-design/evidence/VISUAL/AN-23/sheet-01-marmoreal-K1-plain.png` и `docs/game-design/evidence/VISUAL/AN-23/sheet-03-sarpedon-K1-plain.png`. Это трёхколоночные диагностические листы: вырезана только первая, цветная колонка, без шапки, серой версии и симуляции цветового зрения. Получены реальные кадры 960×540. На рабочих копиях локально приглушены мелкие отладочные имена и HP, не входящие в список текста задания. Размеры и координаты этих участков записаны в `_tools/composition.json`. Поле, зоны, связи, фигуры и окружение взяты из реального кадра; ImageGen карту не рисовал. Файлы источников не изменялись.
- Georgia — заголовки; Roboto BoldCondensed — кнопки, параметры и статусы; Roboto Regular — способности, помощники и ники. Пути шрифтов: `C:/Windows/Fonts/georgia.ttf`, `art/imagegen/anim-move-sheet-codex/_tools/fonts/Roboto-BoldCondensed.ttf`, `art/imagegen/anim-move-sheet-codex/_tools/fonts/Roboto-Regular.ttf`.
- P1: `#E8C06A`, P2: `#5A7F9F`. Бронза: `#8C6B3F`; кремовый: `#ECE3CF`; акценты: `#C9A45C`; основа: `#14161C`…`#1B2433`. Маленькая корона у Veteran обозначает хоста без добавления нового слова в интерфейс.

## Раскладка

В R1/R2 витрины занимают x=48 и 1312, y=120, 560×800; плашки имени — нижние 100 px. Фигуры масштабируются с сохранением пропорций, без растяжения силуэтов. Карточка занимает x=640…1280, y=500…788, ростер — три плитки 128×168 с y=800. В §3 одновременно заданы карточка до y=800 и ростер с y=800; оставлен зазор 12 px. Медальон R2: 140 px, центр (960,420). В R1 медальона нет, поскольку состояние ещё hover.

В R3 витрины уменьшены до 400×600 по краям, реальное превью Marmoreal — ровно 960×540, миниатюры — 200×120. В R4 сохранены диагональные срезы и фигуры в полный рост, медальон приведён к 220 px; имена и ники над общей нижней строкой поля/загрузки. В A используется тёмная студия с цветными световыми конусами и мягким отражением пьедесталов; в B — более светлый мрамор витрин на настоящем размытом и затемнённом Marmoreal K1.

## Референсы

### R1-hero-hover-A

[Готовый PNG](refs/R1-hero-hover-A.png) · [Исходный арт-слой](raw/R1-hero-hover-A.png)

**Спецификация:** §3 — hover, пустой P2, карточка и ростер. Вариант A — studio.

**Raw:** 1672×941; **финал:** 1920×1080.

**Композитинг:** ImageGen: Артур в полный рост и пустой пьедестал соперника. Pillow: точные границы витрин, материал M3, все надписи, вопросительный знак, портреты из fronts и золотая рамка наведения. Карточка показывает реальные данные Артура.

**Промпт, отправленный в ImageGen:**

```text
Use case: ui-mockup. Create ONE premium 16:9 landscape ART LAYER for a 1920x1080 game screen, edge-to-edge, no mockup device. This is the digital board game Unmatched, with fighting-game selection drama and museum-plaque elegance. Reference images: King Arthur and Medusa front images are strict CHARACTER LIKENESS references, the green marble plate is the MATERIAL reference, the in-game HUD is PALETTE/FRAME reference only. Keep Arthur's dark engraved steel/gold armour, red cape, crown, beard, upright sword and dark round miniature pedestal. Keep Medusa's pale face, living snake crown, charcoal draped Greek dress, gold greaves and ornaments, golden bow, quiver and dark round pedestal. Turn Arthur three-quarter toward the RIGHT, Medusa three-quarter toward the LEFT, faces visible, never backs to camera. Photoreal polished collectible game figures; only these heroes, NO sidekicks in niches. Palette navy #14161C to #1B2433, cream #ECE3CF, restrained aged bronze #8C6B3F and gold #C9A45C. Player left team GOLD #E8C06A; player right team muted SILVER-BLUE #5A7F9F, never red/blue teams. Thin bronze/cream frames with tiny Greek-meander corners; green-grey polished marble plates. All UI panels and tiles are EMPTY surfaces reserved for later compositing. ABSOLUTELY NO TEXT, NO LETTERS, NO NUMBERS, NO TYPOGRAPHY, NO QUESTION MARKS, NO VS GLYPHS, NO LOGOS, NO WATERMARKS, NO PSEUDO-WRITING. A medallion, if present, has a completely smooth blank bronze centre. Do not draw any board/map; real map photographs will be composited later. No neon, sci-fi, blood, lightning or giant laurel wreaths. Do not draw HUD from input reference or extra menus.

Variant A STUDIO: almost black navy gallery, dramatic soft cones of light from above, warm gold on left, muted silver-blue on right, near-black vignette, polished dark marble floor with subtle pedestal reflections. Two tall dark display niches framed in thin aged bronze. Museum materials, MK11-like staging without any MK motifs.

Hero HOVER screen. Exact 1920x1080 coordinate layout: a blank top header from y=0 to 96. LEFT niche rectangle x=48..608 y=120..920: Arthur FULL BODY with crown near y=185, boots at y=735 and pedestal at y=790; figure fills the niche, no crop. Blank nameplate at y=820..920. RIGHT niche x=1312..1872 y=120..920: EMPTY pedestal at y=765, no figure, empty space above it; blank nameplate y=820..920. Centre x=640..1280 is clear: a blank framed hero information plaque x=640..1280 y=500..790. Leave centre above plaque atmospheric and empty, NO medallion in hover state. Exactly THREE blank compact roster tiles x=752..880, x=896..1024, x=1040..1168 at y=800..968, first tile has thin gold hover frame. No portraits or marks needed in blank roster tiles. Blank full-width bottom control bar y=980..1060. Emphasize the full-body Arthur and the empty opponent pedestal.
```

**Все видимые строки и числа** (повторы опущены; переносы способности и названий карт объединены):

- «Король Артур»
- «Veteran»
- «Выбирает…»
- «P1»
- «?»
- «Соперник выбирает…»
- «ProGamer»
- «P2»
- «ВЫБОР ГЕРОЯ»
- «шаг 1 из 2»
- «Выйти»
- «SNYMNZ»
- «HP 18 · ход 2 · ближний бой»
- «+ Мерлин · HP 7 · дальний бой»
- «Когда Король Артур атакует, вы можете УСИЛИТЬ эту атаку: сыграйте карту УСИЛЕНИЯ…»
- «Колода · 30»
- «Медуза»
- «Случайный»
- «Готов»
- «Начать партию»

**Самопроверка:** PNG открыт и просмотрен. Все читаемые надписи наложены реальными шрифтами из списка задания; псевдотекста ImageGen не обнаружено. Артур узнаваем по короне, бороде, красному плащу, тёмной броне с золотой отделкой и прямому мечу; P2 намеренно пуст.

**Результат генерации:** success; `moderation_blocked=false`.

### R1-hero-hover-B

[Готовый PNG](refs/R1-hero-hover-B.png) · [Исходный арт-слой](raw/R1-hero-hover-B.png)

**Спецификация:** §3 — hover, пустой P2, карточка и ростер. Вариант B — table.

**Raw:** 1672×941; **финал:** 1920×1080.

**Композитинг:** ImageGen: Артур в полный рост и пустой пьедестал соперника. Pillow: точные границы витрин, материал M3, все надписи, вопросительный знак, портреты из fronts и золотая рамка наведения. Карточка показывает реальные данные Артура. Фон снаружи витрин — реальный размытый Marmoreal K1.

**Промпт, отправленный в ImageGen:**

```text
Use case: ui-mockup. Create ONE premium 16:9 landscape ART LAYER for a 1920x1080 game screen, edge-to-edge, no mockup device. This is the digital board game Unmatched, with fighting-game selection drama and museum-plaque elegance. Reference images: King Arthur and Medusa front images are strict CHARACTER LIKENESS references, the green marble plate is the MATERIAL reference, the in-game HUD is PALETTE/FRAME reference only. Keep Arthur's dark engraved steel/gold armour, red cape, crown, beard, upright sword and dark round miniature pedestal. Keep Medusa's pale face, living snake crown, charcoal draped Greek dress, gold greaves and ornaments, golden bow, quiver and dark round pedestal. Turn Arthur three-quarter toward the RIGHT, Medusa three-quarter toward the LEFT, faces visible, never backs to camera. Photoreal polished collectible game figures; only these heroes, NO sidekicks in niches. Palette navy #14161C to #1B2433, cream #ECE3CF, restrained aged bronze #8C6B3F and gold #C9A45C. Player left team GOLD #E8C06A; player right team muted SILVER-BLUE #5A7F9F, never red/blue teams. Thin bronze/cream frames with tiny Greek-meander corners; green-grey polished marble plates. All UI panels and tiles are EMPTY surfaces reserved for later compositing. ABSOLUTELY NO TEXT, NO LETTERS, NO NUMBERS, NO TYPOGRAPHY, NO QUESTION MARKS, NO VS GLYPHS, NO LOGOS, NO WATERMARKS, NO PSEUDO-WRITING. A medallion, if present, has a completely smooth blank bronze centre. Do not draw any board/map; real map photographs will be composited later. No neon, sci-fi, blood, lightning or giant laurel wreaths. Do not draw HUD from input reference or extra menus.

Variant B TABLE: lighter green-grey marble and bronze display plaques, soft museum lighting, navy translucent panel inserts. Around plaques leave a very dark smooth low-detail navy backdrop: the REAL blurred Marmoreal game scene will replace this backdrop later. More tactile marble, warmer cream edges, gentler shadows than studio, same exact layout. Do not invent a board.

Hero HOVER screen. Exact 1920x1080 coordinate layout: a blank top header from y=0 to 96. LEFT niche rectangle x=48..608 y=120..920: Arthur FULL BODY with crown near y=185, boots at y=735 and pedestal at y=790; figure fills the niche, no crop. Blank nameplate at y=820..920. RIGHT niche x=1312..1872 y=120..920: EMPTY pedestal at y=765, no figure, empty space above it; blank nameplate y=820..920. Centre x=640..1280 is clear: a blank framed hero information plaque x=640..1280 y=500..790. Leave centre above plaque atmospheric and empty, NO medallion in hover state. Exactly THREE blank compact roster tiles x=752..880, x=896..1024, x=1040..1168 at y=800..968, first tile has thin gold hover frame. No portraits or marks needed in blank roster tiles. Blank full-width bottom control bar y=980..1060. Emphasize the full-body Arthur and the empty opponent pedestal.
No pillars, braziers, banners, temples or extra architecture. Light marble plaques should be restrained, not ornate. Keep the 560x800 side panels right at specified screen edges.
```

**Все видимые строки и числа** (повторы опущены; переносы способности и названий карт объединены):

- «Король Артур»
- «Veteran»
- «Выбирает…»
- «P1»
- «?»
- «Соперник выбирает…»
- «ProGamer»
- «P2»
- «ВЫБОР ГЕРОЯ»
- «шаг 1 из 2»
- «Выйти»
- «SNYMNZ»
- «HP 18 · ход 2 · ближний бой»
- «+ Мерлин · HP 7 · дальний бой»
- «Когда Король Артур атакует, вы можете УСИЛИТЬ эту атаку: сыграйте карту УСИЛЕНИЯ…»
- «Колода · 30»
- «Медуза»
- «Случайный»
- «Готов»
- «Начать партию»

**Самопроверка:** PNG открыт и просмотрен. Все читаемые надписи наложены реальными шрифтами из списка задания; псевдотекста ImageGen не обнаружено. Артур узнаваем по короне, бороде, красному плащу, тёмной броне с золотой отделкой и прямому мечу; P2 намеренно пуст.

**Результат генерации:** success; `moderation_blocked=false`.

### R2-hero-locked-A

[Готовый PNG](refs/R2-hero-locked-A.png) · [Исходный арт-слой](raw/R2-hero-locked-A.png)

**Спецификация:** §3 — locked / ready, VS и бейджи ростера. Вариант A — studio.

**Raw:** 1672×941; **финал:** 1920×1080.

**Композитинг:** ImageGen: обе узнаваемые фигуры и пустой бронзовый медальон. Pillow: геометрия витрин, медальон 140 px, надпись VS, реальные портреты, бейджи P1/P2, затемнение занятой соперником плитки, статусы «Выбран» / «Готов». Центральная карточка показывает данные Медузы; так в наборе представлены обе способности.

**Промпт, отправленный в ImageGen:**

```text
Use case: ui-mockup. Create ONE premium 16:9 landscape ART LAYER for a 1920x1080 game screen, edge-to-edge, no mockup device. This is the digital board game Unmatched, with fighting-game selection drama and museum-plaque elegance. Reference images: King Arthur and Medusa front images are strict CHARACTER LIKENESS references, the green marble plate is the MATERIAL reference, the in-game HUD is PALETTE/FRAME reference only. Keep Arthur's dark engraved steel/gold armour, red cape, crown, beard, upright sword and dark round miniature pedestal. Keep Medusa's pale face, living snake crown, charcoal draped Greek dress, gold greaves and ornaments, golden bow, quiver and dark round pedestal. Turn Arthur three-quarter toward the RIGHT, Medusa three-quarter toward the LEFT, faces visible, never backs to camera. Photoreal polished collectible game figures; only these heroes, NO sidekicks in niches. Palette navy #14161C to #1B2433, cream #ECE3CF, restrained aged bronze #8C6B3F and gold #C9A45C. Player left team GOLD #E8C06A; player right team muted SILVER-BLUE #5A7F9F, never red/blue teams. Thin bronze/cream frames with tiny Greek-meander corners; green-grey polished marble plates. All UI panels and tiles are EMPTY surfaces reserved for later compositing. ABSOLUTELY NO TEXT, NO LETTERS, NO NUMBERS, NO TYPOGRAPHY, NO QUESTION MARKS, NO VS GLYPHS, NO LOGOS, NO WATERMARKS, NO PSEUDO-WRITING. A medallion, if present, has a completely smooth blank bronze centre. Do not draw any board/map; real map photographs will be composited later. No neon, sci-fi, blood, lightning or giant laurel wreaths. Do not draw HUD from input reference or extra menus.

Variant A STUDIO: almost black navy gallery, dramatic soft cones of light from above, warm gold on left, muted silver-blue on right, near-black vignette, polished dark marble floor with subtle pedestal reflections. Two tall dark display niches framed in thin aged bronze. Museum materials, MK11-like staging without any MK motifs.

Both heroes LOCKED screen, same grid as hero hover: blank top header y=0..96, LEFT niche x=48..608 y=120..920 with FULL BODY Arthur facing right, RIGHT niche x=1312..1872 y=120..920 with FULL BODY Medusa facing left. Heads at y=180, boots at y=730, dark round pedestals near y=790. Blank lower nameplates y=820..920. Bronze round medallion exactly centred at x=960 y=420, diameter 140, completely BLANK smooth centre, subtle bronze rays only. Blank framed hero information plaque x=640..1280 y=510..790 below medallion. Exactly THREE blank roster tiles x=752..880, x=896..1024, x=1040..1168 y=800..968, first outlined gold, second outlined silver-blue; no badges/glyphs, we add them later. Blank bottom control bar y=980..1060. A confident lock-in pose, no lunging, no flying effects.
No pillars, braziers, banners or ornate temple architecture, just dark framed museum niches, cones of light and reflective floor.
```

**Все видимые строки и числа** (повторы опущены; переносы способности и названий карт объединены):

- «Король Артур»
- «Veteran»
- «Выбран»
- «P1»
- «Медуза»
- «ProGamer»
- «Готов»
- «P2»
- «ВЫБОР ГЕРОЯ»
- «шаг 1 из 2»
- «Выйти»
- «SNYMNZ»
- «HP 16 · ход 3 · дальний бой»
- «+ Гарпии ×3 · HP 1 · ближний бой»
- «В начале своего хода вы можете нанести 1 урон бойцу противника в зоне Медузы.»
- «?»
- «Случайный»
- «VS»
- «Начать партию»

**Самопроверка:** PNG открыт и просмотрен. Все читаемые надписи наложены реальными шрифтами из списка задания; псевдотекста ImageGen не обнаружено. Артур узнаваем по короне, бороде, красному плащу, доспеху и мечу; Медуза — по змеиным волосам, бледному лицу, тёмному греческому платью, золотым поножам и луку. Оба обращены к центру, лица видны, стопы и пьедесталы сохранены.

**Результат генерации:** success; `moderation_blocked=false`.

### R2-hero-locked-B

[Готовый PNG](refs/R2-hero-locked-B.png) · [Исходный арт-слой](raw/R2-hero-locked-B.png)

**Спецификация:** §3 — locked / ready, VS и бейджи ростера. Вариант B — table.

**Raw:** 1672×941; **финал:** 1920×1080.

**Композитинг:** ImageGen: обе узнаваемые фигуры и пустой бронзовый медальон. Pillow: геометрия витрин, медальон 140 px, надпись VS, реальные портреты, бейджи P1/P2, затемнение занятой соперником плитки, статусы «Выбран» / «Готов». Центральная карточка показывает данные Медузы; так в наборе представлены обе способности. Фон снаружи витрин — реальный размытый Marmoreal K1.

**Промпт, отправленный в ImageGen:**

```text
Use case: ui-mockup. Create ONE premium 16:9 landscape ART LAYER for a 1920x1080 game screen, edge-to-edge, no mockup device. This is the digital board game Unmatched, with fighting-game selection drama and museum-plaque elegance. Reference images: King Arthur and Medusa front images are strict CHARACTER LIKENESS references, the green marble plate is the MATERIAL reference, the in-game HUD is PALETTE/FRAME reference only. Keep Arthur's dark engraved steel/gold armour, red cape, crown, beard, upright sword and dark round miniature pedestal. Keep Medusa's pale face, living snake crown, charcoal draped Greek dress, gold greaves and ornaments, golden bow, quiver and dark round pedestal. Turn Arthur three-quarter toward the RIGHT, Medusa three-quarter toward the LEFT, faces visible, never backs to camera. Photoreal polished collectible game figures; only these heroes, NO sidekicks in niches. Palette navy #14161C to #1B2433, cream #ECE3CF, restrained aged bronze #8C6B3F and gold #C9A45C. Player left team GOLD #E8C06A; player right team muted SILVER-BLUE #5A7F9F, never red/blue teams. Thin bronze/cream frames with tiny Greek-meander corners; green-grey polished marble plates. All UI panels and tiles are EMPTY surfaces reserved for later compositing. ABSOLUTELY NO TEXT, NO LETTERS, NO NUMBERS, NO TYPOGRAPHY, NO QUESTION MARKS, NO VS GLYPHS, NO LOGOS, NO WATERMARKS, NO PSEUDO-WRITING. A medallion, if present, has a completely smooth blank bronze centre. Do not draw any board/map; real map photographs will be composited later. No neon, sci-fi, blood, lightning or giant laurel wreaths. Do not draw HUD from input reference or extra menus.

Variant B TABLE: lighter green-grey marble and bronze display plaques, soft museum lighting, navy translucent panel inserts. Around plaques leave a very dark smooth low-detail navy backdrop: the REAL blurred Marmoreal game scene will replace this backdrop later. More tactile marble, warmer cream edges, gentler shadows than studio, same exact layout. Do not invent a board.

Both heroes LOCKED screen, same grid as hero hover: blank top header y=0..96, LEFT niche x=48..608 y=120..920 with FULL BODY Arthur facing right, RIGHT niche x=1312..1872 y=120..920 with FULL BODY Medusa facing left. Heads at y=180, boots at y=730, dark round pedestals near y=790. Blank lower nameplates y=820..920. Bronze round medallion exactly centred at x=960 y=420, diameter 140, completely BLANK smooth centre, subtle bronze rays only. Blank framed hero information plaque x=640..1280 y=510..790 below medallion. Exactly THREE blank roster tiles x=752..880, x=896..1024, x=1040..1168 y=800..968, first outlined gold, second outlined silver-blue; no badges/glyphs, we add them later. Blank bottom control bar y=980..1060. A confident lock-in pose, no lunging, no flying effects.
No pillars, braziers, banners, temples or extra architecture. Restrained marble plaques, no extra large decorations.
```

**Все видимые строки и числа** (повторы опущены; переносы способности и названий карт объединены):

- «Король Артур»
- «Veteran»
- «Выбран»
- «P1»
- «Медуза»
- «ProGamer»
- «Готов»
- «P2»
- «ВЫБОР ГЕРОЯ»
- «шаг 1 из 2»
- «Выйти»
- «SNYMNZ»
- «HP 16 · ход 3 · дальний бой»
- «+ Гарпии ×3 · HP 1 · ближний бой»
- «В начале своего хода вы можете нанести 1 урон бойцу противника в зоне Медузы.»
- «?»
- «Случайный»
- «VS»
- «Начать партию»

**Самопроверка:** PNG открыт и просмотрен. Все читаемые надписи наложены реальными шрифтами из списка задания; псевдотекста ImageGen не обнаружено. Артур узнаваем по короне, бороде, красному плащу, доспеху и мечу; Медуза — по змеиным волосам, бледному лицу, тёмному греческому платью, золотым поножам и луку. Оба обращены к центру, лица видны, стопы и пьедесталы сохранены.

**Результат генерации:** success; `moderation_blocked=false`.

### R3-board-select-A

[Готовый PNG](refs/R3-board-select-A.png) · [Исходный арт-слой](raw/R3-board-select-A.png)

**Спецификация:** §4 — выбор поля после героев. Вариант A — studio.

**Raw:** 1672×941; **финал:** 1920×1080.

**Композитинг:** ImageGen: уменьшенные боковые витрины и пустые поверхности под карту. Pillow: реальный цветной Marmoreal K1 в большом превью; настоящие Marmoreal и Sarpedon K1 в миниатюрах; выбранная рамка, все надписи, статусы и кнопки. Третья плитка — случайное поле.

**Промпт, отправленный в ImageGen:**

```text
Use case: ui-mockup. Create ONE premium 16:9 landscape ART LAYER for a 1920x1080 game screen, edge-to-edge, no mockup device. This is the digital board game Unmatched, with fighting-game selection drama and museum-plaque elegance. Reference images: King Arthur and Medusa front images are strict CHARACTER LIKENESS references, the green marble plate is the MATERIAL reference, the in-game HUD is PALETTE/FRAME reference only. Keep Arthur's dark engraved steel/gold armour, red cape, crown, beard, upright sword and dark round miniature pedestal. Keep Medusa's pale face, living snake crown, charcoal draped Greek dress, gold greaves and ornaments, golden bow, quiver and dark round pedestal. Turn Arthur three-quarter toward the RIGHT, Medusa three-quarter toward the LEFT, faces visible, never backs to camera. Photoreal polished collectible game figures; only these heroes, NO sidekicks in niches. Palette navy #14161C to #1B2433, cream #ECE3CF, restrained aged bronze #8C6B3F and gold #C9A45C. Player left team GOLD #E8C06A; player right team muted SILVER-BLUE #5A7F9F, never red/blue teams. Thin bronze/cream frames with tiny Greek-meander corners; green-grey polished marble plates. All UI panels and tiles are EMPTY surfaces reserved for later compositing. ABSOLUTELY NO TEXT, NO LETTERS, NO NUMBERS, NO TYPOGRAPHY, NO QUESTION MARKS, NO VS GLYPHS, NO LOGOS, NO WATERMARKS, NO PSEUDO-WRITING. A medallion, if present, has a completely smooth blank bronze centre. Do not draw any board/map; real map photographs will be composited later. No neon, sci-fi, blood, lightning or giant laurel wreaths. Do not draw HUD from input reference or extra menus.

Variant A STUDIO: almost black navy gallery, dramatic soft cones of light from above, warm gold on left, muted silver-blue on right, near-black vignette, polished dark marble floor with subtle pedestal reflections. Two tall dark display niches framed in thin aged bronze. Museum materials, MK11-like staging without any MK motifs.

STAGE/BOARD selection screen. Blank top header y=0..96. Niches SHRINK to x=48..448 y=160..760 and x=1472..1872 y=160..760, 400x600 each: FULL BODY Arthur left, Medusa right, heads near y=205, feet and pedestal near y=660; blank nameplates y=680..760. Large EMPTY landscape preview frame exactly x=480..1440 y=130..670, 960x540; fill it flat near-black navy, absolutely NO imagined board, landscape or diagram within it. Thin cream/bronze rim and small meander corners. Empty board name plaque x=480..1440 y=685..750. Exactly THREE EMPTY thumbnail frames 200x120 at x=644..844, x=860..1060, x=1076..1276, y=788..908, first outlined gold. Blank control strip y=980..1060. Centre preview is the focal point, hero niches are narrower at edges. NO medallion on this screen.
Absolutely keep heroes smaller than the huge central board preview. No pillars/braziers/banners, plain dark studio surround.
```

**Все видимые строки и числа** (повторы опущены; переносы способности и названий карт объединены):

- «Король Артур»
- «Veteran»
- «Готов»
- «P1»
- «Медуза»
- «ProGamer»
- «P2»
- «ВЫБОР ПОЛЯ»
- «шаг 2 из 2»
- «Выйти»
- «SNYMNZ»
- «Marmoreal · оригинальная карта»
- «Sarpedon · оригинальная карта»
- «?»
- «Случайное»
- «‹ Герой»
- «Поле выбирает хост»
- «Начать партию»

**Самопроверка:** PNG открыт и просмотрен. Все читаемые надписи наложены реальными шрифтами из списка задания; псевдотекста ImageGen не обнаружено. Артур узнаваем по короне, бороде, красному плащу, доспеху и мечу; Медуза — по змеиным волосам, бледному лицу, тёмному греческому платью, золотым поножам и луку. Оба обращены к центру, лица видны, стопы и пьедесталы сохранены.

**Результат генерации:** success; `moderation_blocked=false`.

### R3-board-select-B

[Готовый PNG](refs/R3-board-select-B.png) · [Исходный арт-слой](raw/R3-board-select-B.png)

**Спецификация:** §4 — выбор поля после героев. Вариант B — table.

**Raw:** 1672×941; **финал:** 1920×1080.

**Композитинг:** ImageGen: уменьшенные боковые витрины и пустые поверхности под карту. Pillow: реальный цветной Marmoreal K1 в большом превью; настоящие Marmoreal и Sarpedon K1 в миниатюрах; выбранная рамка, все надписи, статусы и кнопки. Третья плитка — случайное поле. Фон снаружи витрин — реальный размытый Marmoreal K1.

**Промпт, отправленный в ImageGen:**

```text
Use case: ui-mockup. Create ONE premium 16:9 landscape ART LAYER for a 1920x1080 game screen, edge-to-edge, no mockup device. This is the digital board game Unmatched, with fighting-game selection drama and museum-plaque elegance. Reference images: King Arthur and Medusa front images are strict CHARACTER LIKENESS references, the green marble plate is the MATERIAL reference, the in-game HUD is PALETTE/FRAME reference only. Keep Arthur's dark engraved steel/gold armour, red cape, crown, beard, upright sword and dark round miniature pedestal. Keep Medusa's pale face, living snake crown, charcoal draped Greek dress, gold greaves and ornaments, golden bow, quiver and dark round pedestal. Turn Arthur three-quarter toward the RIGHT, Medusa three-quarter toward the LEFT, faces visible, never backs to camera. Photoreal polished collectible game figures; only these heroes, NO sidekicks in niches. Palette navy #14161C to #1B2433, cream #ECE3CF, restrained aged bronze #8C6B3F and gold #C9A45C. Player left team GOLD #E8C06A; player right team muted SILVER-BLUE #5A7F9F, never red/blue teams. Thin bronze/cream frames with tiny Greek-meander corners; green-grey polished marble plates. All UI panels and tiles are EMPTY surfaces reserved for later compositing. ABSOLUTELY NO TEXT, NO LETTERS, NO NUMBERS, NO TYPOGRAPHY, NO QUESTION MARKS, NO VS GLYPHS, NO LOGOS, NO WATERMARKS, NO PSEUDO-WRITING. A medallion, if present, has a completely smooth blank bronze centre. Do not draw any board/map; real map photographs will be composited later. No neon, sci-fi, blood, lightning or giant laurel wreaths. Do not draw HUD from input reference or extra menus.

Variant B TABLE: lighter green-grey marble and bronze display plaques, soft museum lighting, navy translucent panel inserts. Around plaques leave a very dark smooth low-detail navy backdrop: the REAL blurred Marmoreal game scene will replace this backdrop later. More tactile marble, warmer cream edges, gentler shadows than studio, same exact layout. Do not invent a board.

STAGE/BOARD selection screen. Blank top header y=0..96. Niches SHRINK to x=48..448 y=160..760 and x=1472..1872 y=160..760, 400x600 each: FULL BODY Arthur left, Medusa right, heads near y=205, feet and pedestal near y=660; blank nameplates y=680..760. Large EMPTY landscape preview frame exactly x=480..1440 y=130..670, 960x540; fill it flat near-black navy, absolutely NO imagined board, landscape or diagram within it. Thin cream/bronze rim and small meander corners. Empty board name plaque x=480..1440 y=685..750. Exactly THREE EMPTY thumbnail frames 200x120 at x=644..844, x=860..1060, x=1076..1276, y=788..908, first outlined gold. Blank control strip y=980..1060. Centre preview is the focal point, hero niches are narrower at edges. NO medallion on this screen.
No pillars, braziers, banners, temples or extra architecture. Keep board preview exact 16:9, empty and very large. Restrained museum marble plaques.
```

**Все видимые строки и числа** (повторы опущены; переносы способности и названий карт объединены):

- «Король Артур»
- «Veteran»
- «Готов»
- «P1»
- «Медуза»
- «ProGamer»
- «P2»
- «ВЫБОР ПОЛЯ»
- «шаг 2 из 2»
- «Выйти»
- «SNYMNZ»
- «Marmoreal · оригинальная карта»
- «Sarpedon · оригинальная карта»
- «?»
- «Случайное»
- «‹ Герой»
- «Поле выбирает хост»
- «Начать партию»

**Самопроверка:** PNG открыт и просмотрен. Все читаемые надписи наложены реальными шрифтами из списка задания; псевдотекста ImageGen не обнаружено. Артур узнаваем по короне, бороде, красному плащу, доспеху и мечу; Медуза — по змеиным волосам, бледному лицу, тёмному греческому платью, золотым поножам и луку. Оба обращены к центру, лица видны, стопы и пьедесталы сохранены.

**Результат генерации:** success; `moderation_blocked=false`.

### R4-vs-A

[Готовый PNG](refs/R4-vs-A.png) · [Исходный арт-слой](raw/R4-vs-A.png)

**Спецификация:** §5 — VS / загрузка. Вариант A — studio.

**Raw:** 1672×941; **финал:** 1920×1080.

**Композитинг:** ImageGen: две диагональные витрины, фигуры в полный рост, бронзовый медальон без букв. Pillow: настоящий Marmoreal K1 в центральном просвете, нормализация медальона до 220 px, VS, имена, ники, P1/P2, название поля, статическая дуга спиннера и строка загрузки.

**Промпт, отправленный в ImageGen:**

```text
Use case: ui-mockup. Create ONE premium 16:9 landscape ART LAYER for a 1920x1080 game screen, edge-to-edge, no mockup device. This is the digital board game Unmatched, with fighting-game selection drama and museum-plaque elegance. Reference images: King Arthur and Medusa front images are strict CHARACTER LIKENESS references, the green marble plate is the MATERIAL reference, the in-game HUD is PALETTE/FRAME reference only. Keep Arthur's dark engraved steel/gold armour, red cape, crown, beard, upright sword and dark round miniature pedestal. Keep Medusa's pale face, living snake crown, charcoal draped Greek dress, gold greaves and ornaments, golden bow, quiver and dark round pedestal. Turn Arthur three-quarter toward the RIGHT, Medusa three-quarter toward the LEFT, faces visible, never backs to camera. Photoreal polished collectible game figures; only these heroes, NO sidekicks in niches. Palette navy #14161C to #1B2433, cream #ECE3CF, restrained aged bronze #8C6B3F and gold #C9A45C. Player left team GOLD #E8C06A; player right team muted SILVER-BLUE #5A7F9F, never red/blue teams. Thin bronze/cream frames with tiny Greek-meander corners; green-grey polished marble plates. All UI panels and tiles are EMPTY surfaces reserved for later compositing. ABSOLUTELY NO TEXT, NO LETTERS, NO NUMBERS, NO TYPOGRAPHY, NO QUESTION MARKS, NO VS GLYPHS, NO LOGOS, NO WATERMARKS, NO PSEUDO-WRITING. A medallion, if present, has a completely smooth blank bronze centre. Do not draw any board/map; real map photographs will be composited later. No neon, sci-fi, blood, lightning or giant laurel wreaths. Do not draw HUD from input reference or extra menus.

Variant A STUDIO: almost black navy gallery, dramatic soft cones of light from above, warm gold on left, muted silver-blue on right, near-black vignette, polished dark marble floor with subtle pedestal reflections. Two tall dark display niches framed in thin aged bronze. Museum materials, MK11-like staging without any MK motifs.

VS MATCH LOADING splash. No header, no roster, no menu buttons or information cards. Two monumental FULL BODY fighters in tall 720x960 display areas: Arthur left x=100..820 y=40..1000 facing inward, Medusa right x=1100..1820 y=40..1000 facing inward; crown/snake crown near y=65, boots at y=865, pedestals near y=920, all fully visible. Their inner panel edges form dramatic diagonal cuts towards the central axis, opening a narrow centre gap. Large round aged bronze medallion at x=960 y=420 diameter 220, blank smooth centre; no lettering. Reserve low dark blank nameplates at x=90..780 y=850..965 and x=1140..1830 y=850..965, do not cover faces. Dark blank board-name/loading strip x=510..1410 y=975..1070. Keep the centre gap clear so we can composite an actual board photo behind the medallion. Dramatic but elegant, no sparks/lightning.
No pillars, torches, banners or extra architecture. Dramatic near-black showcase and floor. Maintain both fighters full length, enormous but complete.
```

**Все видимые строки и числа** (повторы опущены; переносы способности и названий карт объединены):

- «VS»
- «Король Артур»
- «Veteran»
- «P1»
- «Медуза»
- «ProGamer»
- «P2»
- «Marmoreal · оригинальная карта»
- «Подготовка поля…»

**Самопроверка:** PNG открыт и просмотрен. Все читаемые надписи наложены реальными шрифтами из списка задания; псевдотекста ImageGen не обнаружено. Артур узнаваем по короне, бороде, красному плащу, доспеху и мечу; Медуза — по змеиным волосам, бледному лицу, тёмному греческому платью, золотым поножам и луку. Оба обращены к центру, лица видны, стопы и пьедесталы сохранены.

**Результат генерации:** success; `moderation_blocked=false`.

### R4-vs-B

[Готовый PNG](refs/R4-vs-B.png) · [Исходный арт-слой](raw/R4-vs-B.png)

**Спецификация:** §5 — VS / загрузка. Вариант B — table.

**Raw:** 1672×941; **финал:** 1920×1080.

**Композитинг:** ImageGen: две диагональные витрины, фигуры в полный рост, бронзовый медальон без букв. Pillow: настоящий Marmoreal K1 в центральном просвете, нормализация медальона до 220 px, VS, имена, ники, P1/P2, название поля, статическая дуга спиннера и строка загрузки. Фон снаружи витрин — реальный размытый Marmoreal K1.

**Промпт, отправленный в ImageGen:**

```text
Use case: ui-mockup. Create ONE premium 16:9 landscape ART LAYER for a 1920x1080 game screen, edge-to-edge, no mockup device. This is the digital board game Unmatched, with fighting-game selection drama and museum-plaque elegance. Reference images: King Arthur and Medusa front images are strict CHARACTER LIKENESS references, the green marble plate is the MATERIAL reference, the in-game HUD is PALETTE/FRAME reference only. Keep Arthur's dark engraved steel/gold armour, red cape, crown, beard, upright sword and dark round miniature pedestal. Keep Medusa's pale face, living snake crown, charcoal draped Greek dress, gold greaves and ornaments, golden bow, quiver and dark round pedestal. Turn Arthur three-quarter toward the RIGHT, Medusa three-quarter toward the LEFT, faces visible, never backs to camera. Photoreal polished collectible game figures; only these heroes, NO sidekicks in niches. Palette navy #14161C to #1B2433, cream #ECE3CF, restrained aged bronze #8C6B3F and gold #C9A45C. Player left team GOLD #E8C06A; player right team muted SILVER-BLUE #5A7F9F, never red/blue teams. Thin bronze/cream frames with tiny Greek-meander corners; green-grey polished marble plates. All UI panels and tiles are EMPTY surfaces reserved for later compositing. ABSOLUTELY NO TEXT, NO LETTERS, NO NUMBERS, NO TYPOGRAPHY, NO QUESTION MARKS, NO VS GLYPHS, NO LOGOS, NO WATERMARKS, NO PSEUDO-WRITING. A medallion, if present, has a completely smooth blank bronze centre. Do not draw any board/map; real map photographs will be composited later. No neon, sci-fi, blood, lightning or giant laurel wreaths. Do not draw HUD from input reference or extra menus.

Variant B TABLE: lighter green-grey marble and bronze display plaques, soft museum lighting, navy translucent panel inserts. Around plaques leave a very dark smooth low-detail navy backdrop: the REAL blurred Marmoreal game scene will replace this backdrop later. More tactile marble, warmer cream edges, gentler shadows than studio, same exact layout. Do not invent a board.

VS MATCH LOADING splash. No header, no roster, no menu buttons or information cards. Two monumental FULL BODY fighters in tall 720x960 display areas: Arthur left x=100..820 y=40..1000 facing inward, Medusa right x=1100..1820 y=40..1000 facing inward; crown/snake crown near y=65, boots at y=865, pedestals near y=920, all fully visible. Their inner panel edges form dramatic diagonal cuts towards the central axis, opening a narrow centre gap. Large round aged bronze medallion at x=960 y=420 diameter 220, blank smooth centre; no lettering. Reserve low dark blank nameplates at x=90..780 y=850..965 and x=1140..1830 y=850..965, do not cover faces. Dark blank board-name/loading strip x=510..1410 y=975..1070. Keep the centre gap clear so we can composite an actual board photo behind the medallion. Dramatic but elegant, no sparks/lightning.
No pillars, braziers, banners, temples or extra architecture. Lighter green-grey marble diagonal showcase plaques and bronze rims, softer table-HUD mood. Never crop the feet or snake crown.
```

**Все видимые строки и числа** (повторы опущены; переносы способности и названий карт объединены):

- «VS»
- «Король Артур»
- «Veteran»
- «P1»
- «Медуза»
- «ProGamer»
- «P2»
- «Marmoreal · оригинальная карта»
- «Подготовка поля…»

**Самопроверка:** PNG открыт и просмотрен. Все читаемые надписи наложены реальными шрифтами из списка задания; псевдотекста ImageGen не обнаружено. Артур узнаваем по короне, бороде, красному плащу, доспеху и мечу; Медуза — по змеиным волосам, бледному лицу, тёмному греческому платью, золотым поножам и луку. Оба обращены к центру, лица видны, стопы и пьедесталы сохранены.

**Результат генерации:** success; `moderation_blocked=false`.

## Проверка и исправления

- Восемь отдельных вызовов встроенного ImageGen; восемь успешных raw. Отказов модерации, `moderation_blocked` и незавершённых генераций нет. Системные пути и точные промпты сохранены в `_tools/generation.json`; все исходные raw скопированы в эту папку.
- ImageGen оставил пустые панели без букв. При нормализации R2-B в верхних углах витрин были обнаружены фрагменты пустой шапки; они закрашены участком того же тёмного фона только в рабочей копии. Raw оставлен без изменений. Бейджи отодвинуты от углового меандра; шрифт P1/P2 на цветной плитке очищен от избыточной тени.
- На карте приглушены только мелкие отладочные подписи. Для сравнения сохранены `_tools/*-K1-colour.png` (цветная колонка до обработки) и `_tools/*-K1-clean.png` (используемая рабочая копия). В R3 нет нарисованной ImageGen карты; в R4 фон карты также настоящий.
- При локальной подготовке были исправлены две ошибки синтаксиса проверочной однострочной команды Python и один неверно разобранный путь копирования первого raw. После исправления все raw присутствуют, проверены размеры и доступность. На генерации и итоговые файлы эти ошибки не повлияли.
- Скрипт проверяет whitelist каждой логической строки и границы каждого текстового блока. Список строк, шрифты, прямоугольники текста, размеры и SHA-256 итоговых PNG записаны в `_tools/composition.json`. Это проверка наложенного текста; отсутствие остаточных глифов дополнительно проверено глазами во всех восьми PNG.
- Знаки `?`, `VS`, бейджи `P1`/`P2` прямо заданы в задании. Имя хоста обозначено существующим ником Veteran и рисунком короны; новые слова, таймеры, эпитеты, характеристики или придуманные данные не добавлялись.
- Проверены все восемь финальных изображений отдельно и контактный лист. Пересечений текста с ростером, кнопками или фигурами не обнаружено; R2 содержит выбранного P1 и готового P2, R3 — готовых обоих.

## Повторная сборка

Из корня проекта:

```powershell
python art/imagegen/select-screens-codex/_tools/prepare.py
python art/imagegen/select-screens-codex/_tools/compose.py
python art/imagegen/select-screens-codex/_tools/document.py
```

`prepare.py` подготавливает текст промптов и вырезки карт; повторные генерации автоматически не запускает. `compose.py` воспроизводит готовые PNG из сохранённых raw и исходников проекта. `document.py` формирует этот README через `Path.write_text(..., encoding="utf-8")`. JSON также записывается Python в UTF-8. Автоматическая пересборка оставляет визуальный статус pending до нового ручного просмотра.

Все добавленные этой задачей файлы находятся внутри `art/imagegen/select-screens-codex/`. Изначальный `PROMPT.codex.md` сохранён. Коммитов, изменений игрового кода, запуска клиента, сервисов и фоновых процессов не выполнялось.
