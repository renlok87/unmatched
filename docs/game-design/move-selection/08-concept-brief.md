# 08. Бриф на концепты подбора хода (ImageGen)

Дата: 2026-10-03. Статус: ПРЕДЛОЖЕНИЕ, v2 (после адверсариального ревью — [09](09-review-log.md)). Исполнитель — задача MS-T-00 ([05](05-implementation-plan.md)). Генерация — во
встроенном ImageGen приложения Codex «ChatGPT» (отдельно открыто у пользователя, доступ через computer use). Концепты —
**визуальные предложения**, а не игровые ассеты и не кадры UE: они не доказывают читаемость и не заменяют замеры
MS-AT-30. Решение по цвету и форме принимает пользователь на арт-приёмке (MS-Q-04).

> **Итог MS-T-00 (2026-10-03).** Концепты ImageGen по этому брифу (v1) пользователь отклонил: модель выдумала
> доски, фигурки и пути. Действующие макеты v2 собраны скриптом на реальных данных: арт и топология карт
> Marmoreal/Sarpedon, герои и сайдкики из БД бэкенда (как в админке), реальные RU-карты, алгоритм 04 §3.1. Значки
> перерисованы в языке карт (итерация 2). Описание, источники и наблюдения —
> [`art/imagegen/move-selection-v2/README.md`](../../../art/imagegen/move-selection-v2/README.md). Ниже — исходный
> бриф v1, оставлен для истории. Состояния, цвета и критерии из него действуют, промпты — нет.

## 1. Что должны показать концепты

Главное — **подложки** (plates) под пространствами в состояниях из [03](03-ux-spec.md) §4.2: достижимо (база),
только с бустом, путь, цель, цель «нужен буст», союзник, враг-блок, отказ, конфликт, отправлено, pending MOVE/PLACE,
последний ход соперника, угроза. Плюс превью пути с призраком фигурки, момент выбора буста, черновик нескольких бойцов, обратная связь об
ошибке, взгляд соперника и панель манёвра.

## 2. Ограничения арт-дирекшна

| Правило | Значение | Источник |
|---|---|---|
| Стиль | «мрачноватая атмосферная диорама», язык B · Painted Miniature: крупные окрашенные формы, матовые материалы, холодные тени, тёплые фонари | `docs/game-design/03-art-direction.md` §1 (D-02), `docs/game-design/evidence/ART-002/README.md` |
| Игровой слой | ярче и насыщеннее декора на 0,3–0,7 EV; подсветки — unlit, читаются поверх арта карты | 03 С-9; решение W5b-R D-2 |
| Подложка не перекрашивает зону | кольцо по краю круга пространства, заливка ≤ 20 %, цвет зоны остаётся виден | 03 §4.1 пакета; R3 P-16 |
| Цвет подложки (предложение, задаётся на доску) | сетка Cobble — тёплый белый `#F2E9D8`; карты Marmoreal и Sarpedon — два варианта для сравнения: A — тёплое золото `#FFC857` (нынешний цвет карт), B — бирюзовый `#4CD2DC`; тёплый белый на картах **не** используется (сливается с пастельными зонами, ΔE76 < 20); кромка `#111317` | MS-D-12; 03 §4.2b пакета |
| Линия пути | на Cobble — слоновая кость `#FFF4DC`, на картах — цвет подложки доски; тёмная кромка; точки шагов; наконечник у цели | 03 §4.2 V-03, §4.2b пакета |
| Команды | P1 — золото `#E8C06A`, сплошная окружность; P2 — серебристо-синий `#5A7F9F`, шестигранник с разрывами на углах; белый ободок `#FFFFFF` | `decisions/2026-09-29-board-readability-decisions.md` D-2, D-3 |
| Ошибка и конфликт | красный `#D9483F` только вместе с глифом: крест и значок «стоп» (отказ, V-08) или «!» (конфликт хода, V-09); больше нигде | `docs/unreal/contracts/hud/hud-style-tokens.json` `state.error`; 03 §4.2 пакета |
| Pending | вертикальный фиолетовый маркер `#8A56C6` над фигуркой; подложка — длинный пунктир цвета подложки доски | 03 §6; 03 §4.2 V-11 пакета |
| Не только цвет | каждое состояние отличается формой и значком; концепт должен читаться в градациях серого | XAG 103, UI-ACC-004 |
| Текст | без читаемого текста, кроме цифр (1, 2, 3, +2, +4, 3/7) и коротких латинских меток пространств (M13); блоки текста панели — серые полосы-плейсхолдеры | генерация искажает буквы; тексты дают StringTable |
| Без логотипов и чужих IP | никаких логотипов Unmatched, Restoration Games, Dire Wolf; фигурки — наши (Medusa, Harpies, King Arthur, Merlin) по нашим кадрам | — |
| Референсы | только собственные кадры проекта и собственные imagegen-ассеты; без NoAI-материалов Fab | `docs/art-pipeline/CREDITS-fab.md`; 07 §1 |

## 3. Общие параметры генерации

- Размер: 1536×1024 (альбом), если ImageGen предлагает размеры; иначе — максимальный альбомный.
- Две попытки на концепт; лучшая сохраняется как `<id>.png`, вторая — `<id>-alt.png`.
- Выход: `art/imagegen/move-selection-v1/<id>.png`; промпт — `art/imagegen/move-selection-v1/prompts/<id>.txt`;
  реестр — `art/imagegen/move-selection-v1/manifest.json` (поля как в `art/imagegen/mvp-v1/manifest.json`: id, файл,
  sha256, промпт, референсы, дата, статус `proposal`).
- Лист сравнения: `art/imagegen/move-selection-v1/contact-sheet.png` (все восемь + серые версии, собирается скриптом
  после генерации).
- Общий префикс промпта (добавляется к каждому):

```
Game UI concept for a digital adaptation of a miniatures board game, viewed from a fixed three-quarter top-down
camera over a tabletop diorama. Painted-miniature style: large matte painted forms, cool blue-grey shadows, warm
lantern accents. The board is a painted map with circular spaces connected by drawn lines; spaces are tinted by
zone colours. All selection highlights are clean, flat, unlit overlays that sit on the board surface, crisp and
readable, never repainting the zone colour underneath. Team colours: player 1 gold with a solid circle ring under the
figure, player 2 steel blue with a hexagon ring with small gaps at the corners, both with a thin white rim. No logos,
no readable words; only numerals and short labels like "M13". Keep the composition faithful to the attached
reference screenshot (camera angle, board layout, figure scale).
```

## 4. Концепты

### MS-C-01. Лист состояний подложек

- **Назначение:** дизайн-система подложек V-01..V-16 и V-04b на одном листе; база для материала `M_UM_MovePlate`.
- **Референсы:** `art/imagegen/mvp-v1/markers/marker-move.png`, `art/imagegen/mvp-v1/markers/marker-pending.png`,
  `art/imagegen/mvp-v1/markers/marker-selection-p1.png`, `art/imagegen/mvp-v1/markers/marker-selection-p2.png`,
  `art/imagegen/mvp-v1/ui/actions/ui-action-refusal.png`, `art/imagegen/mvp-v1/ui/actions/ui-action-maneuver-normal.png`,
  `art/imagegen/mvp-v1/ui/team/team-shape-circle-12.png`, `art/imagegen/mvp-v1/ui/team/team-shape-hex-12.png`.
- **Промпт:**

```
A clean design sheet, 4 columns by 5 rows, each cell shows one round board space (a painted cobblestone disc, mid
grey) seen from above at a slight angle, with a different selection overlay:
1 reachable: solid warm-white ring (#F2E9D8) with a thin dark keyline on both sides and a very faint warm-white fill;
2 reachable only with boost: dashed warm-white ring, no fill, a tiny dark chip with "+2" at the top of the ring;
3 path step: a small warm-ivory dot with a dark keyline and a thick ivory line passing through the centre;
4 destination: double warm-white ring, a translucent ghost of a small bronze snake-haired figure, a round dark badge
  with the numeral "1";
5 selected start: the existing gold solid circle team ring under a figure base plus a thin selection ring;
6 ally pass-through: no ring, a faint dashed inner circle and a small chevron arrow icon;
7 enemy blocked: dark diagonal hatching over the space and a small padlock icon;
8 invalid click: a red X (#D9483F) with a small round stop icon;
9 conflict: dashed red double ring and an exclamation mark icon;
10 sent: the destination look at 70% brightness with a small hourglass icon;
11 pending move: long-dash warm-white ring, a small wand icon, a violet (#8A56C6) vertical marker above;
12 pending place: long-dash warm-white ring with a small map-pin icon, no line;
13 last move origin: thin steel-blue hexagon outline with gaps at the corners;
14 last move destination: solid steel-blue hexagon ring with small blue dots trailing toward it;
15 same as 1 on a saturated red zone space; 16 same as 1 on a saturated blue zone space;
17 destination that still needs a boost: like 4 but the outer ring is dashed, a tiny dark chip "+3" at the top;
18 same as 1 but the ring is warm gold (#FFC857) on a pale pastel marble space;
19 same as 1 but the ring is turquoise (#4CD2DC) on the same pale pastel marble space;
20 threat: four small steel-blue corner brackets just outside the ring and a small eye icon with the numeral "2".
Neutral dark slate background, even soft light, every state distinguishable by shape and icon alone.
```

- **Критерии приёмки:** 20 ячеек; в ячейках 1–17 цвет подложки тёплый белый (вариант сетки), в 18–19 — два варианта
  для карт; в градациях серого все состояния различимы (проверка сменой режима просмотра), в том числе 4 и 17, 9 и 20;
  красный — только в ячейках 8 и 9; кольцо не закрывает зону в ячейках 15–16 и 18–19; нет букв, кроме цифр.

### MS-C-02. Marmoreal: база и ярус буста

- **Назначение:** как подложки выглядят на светлой карте с многозонными пространствами (главный риск RK-01).
- **Референсы:** `docs/game-design/evidence/ENV-MAPS/p5a-verify-2026-10-01/live/marmoreal/k1/run-20261001-114548/phase2-board-host-1920x1080.png`
  (текущие золотые кольца `#FFC857` — вариант A сохраняет их цвет, вариант B меняет на бирюзовый),
  `docs/game-design/evidence/ART-002/option-B-painted-miniature.png` (стиль).
- **Два варианта:** промпт ниже генерируется дважды — `{COLOUR}` = «warm gold (#FFC857)» → `MS-C-02a`, «turquoise
  (#4CD2DC)» → `MS-C-02b`. Это вход для выбора цвета карт в MS-T-13 и для арт-приёмки (MS-Q-04).
- **Промпт:**

```
Same board, camera and figures as the attached Marmoreal screenshot (white marble garden courtyard map with round
spaces split into pale pastel zone colours: green, blue, pink, brown, yellow, grey). Replace the existing rings
around spaces with the new selection overlays in {COLOUR}: the snake-haired gold-team hero on the left is selected;
the spaces she can reach in up to 3 steps along the drawn lines show a solid {COLOUR} ring with a dark keyline and a
faint fill; spaces reachable only with a boost (4 to 7 steps) show a dashed {COLOUR} ring with a tiny "+2" or "+4"
chip. Spaces that are neighbours on the grid but not connected by a line stay unmarked. The cursor hovers a reachable
space: a {COLOUR} path line with dark keyline follows the drawn lines from the hero to that space, small dots on
intermediate spaces, an arrowhead at the end and a small dark badge "3/3" near the cursor. Enemy figures with
steel-blue hexagon rings have dark diagonal hatching on their spaces; the small team-colour diamond in front of each
hero base stays visible and is not covered by any ring.
```

- **Критерии приёмки:** композиция совпадает с референсом (≥ 80 % расположения пространств узнаваемо); в обоих
  вариантах кольца видны и на белом мраморе (тёмная кромка), и на зелёных/синих/жёлтых пространствах; линия идёт по
  нарисованным связям, а не по прямой через пустоту; ярус буста отличается формой (пунктир), а не только яркостью;
  ромб лидера не перекрыт.

### MS-C-03. Sarpedon и Cobble: адаптация к насыщенным зонам и к сетке

- **Назначение:** проверить подложки на насыщенных зонах (красная, жёлтая, розовая) и на квадратной сетке Cobble с
  метками зон.
- **Референсы:** `docs/game-design/evidence/ENV-MAPS/p5a-verify-2026-10-01/live/sarpedon/k1/run-20261001-114858/phase2-board-host-1920x1080.png`,
  `docs/game-design/evidence/ART-005/art3-live-3boards-r2-2026-09-29/k1/cobble-5x6/run-20260929-192438/phase2-board-host-1920x1080.png`.
- **Промпт:**

```
Two panels side by side. Left panel: the attached Sarpedon map (beach, river and ship deck with saturated green,
yellow, pink, purple and red round spaces) from the same camera; the gold-team hero is selected and her reachable
spaces show the warm gold (#FFC857) keylined ring overlay, boost-only spaces the dashed ring with "+N" chip; the ring
stays readable on the red, yellow and pale blue spaces. Right panel: the attached Cobble City square grid (grey cobblestone tiles with
blue diamond and red bar zone marks); the same overlay adapted to squares: a rounded-square warm-white keylined ring
inset inside each reachable tile, dashed for boost-only, an ivory path line with right-angle turns along tile
centres, the existing zone marks still visible under the overlay.
```

- **Критерии приёмки:** на красных и жёлтых пространствах кольцо отделено тёмной кромкой; на сетке подложка не закрывает
  метки зон; линия на сетке — ортогональными шагами.

### MS-C-04. Превью пути и призрак (крупный план)

- **Назначение:** ближний вид K2: линия по связям, точки шагов, наконечник, призрак на цели, бейдж шагов, значки зон
  цели и «отсюда можно атаковать».
- **Референсы:** `docs/game-design/evidence/ENV-MAPS/p9b-hero-light-detail-2026-10-02/closeup-k2x2p5-marmoreal.jpg`,
  `art/imagegen/hero-quality-v1/medusa/medusa-front.png`.
- **Промпт:**

```
Close-up of the attached Marmoreal board at the attached zoom. The bronze snake-haired hero stands on her space with
her gold circle team ring. A warm gold (#FFC857) path line with a dark keyline runs from her along two drawn connection
lines to a destination space three steps away: small gold dots on the two intermediate spaces, an arrowhead at the
end. On the destination: a double warm gold ring with a dark keyline and a 45% translucent ghost copy of the hero in
her idle pose, dithered, no shadow. Beside the destination: a compact dark badge "3/3", two small zone tokens (a green leaf glyph and a blue wave
glyph) because the space belongs to two zones, and a small crossed-swords icon with the numeral "1" (one enemy in
attack range from there).
```

- **Критерии приёмки:** призрак читается как «план», а не как вторая фигурка (прозрачность, без тени); линия не
  заслоняет фигурки; значки у цели не перекрывают соседние пространства.

### MS-C-05. Момент выбора буста

- **Назначение:** связь «карта руки → расширение подложек»; строка буста в панели.
- **Референсы:** `docs/game-design/evidence/ENV-MAPS/p5a-verify-2026-10-01/live/marmoreal/k1/run-20261001-114548/phase2-board-host-1920x1080.png`
  (полоса руки внизу), `art/imagegen/mvp-v1/ui/actions/ui-action-boost-normal.png`,
  `art/imagegen/mvp-v1/ui/cards/ui-card-frame-attack-selected.png`, `art/imagegen/mvp-v1/ui/panels/ui-hand-tray.png`.
- **Промпт:**

```
The attached Marmoreal view during a maneuver draft. At the bottom, the hand tray shows five cards; each card has a
small boost badge with a numeral (+1, +4, +4, +2, +3); the second card is raised and outlined as selected, with the
boost action icon glowing. On the board, the selected hero's reachable spaces expand: the inner group keeps the solid
warm gold (#FFC857) keylined rings (base), and a further ring of spaces that were dashed now turns solid, showing the
boost took effect; a faint soft ripple travels outward from the hero along the drawn lines. Top-left, a compact dark panel
with grey placeholder text bars and one highlighted line with the boost icon and "+4".
```

- **Критерии приёмки:** понятно, какая карта даёт буст и что он изменил на доске; цифры BOOST на картах читаются; рябь
  не мешает читать состояния (она опциональна и отключается в reduced motion).

### MS-C-06. Черновик нескольких бойцов и панель манёвра

- **Назначение:** порядок ходов, одновременный показ нескольких планов, конфликт, строки панели.
- **Референсы:** `docs/game-design/evidence/ENV-MAPS/p5a-verify-2026-10-01/live/sarpedon/k1/run-20261001-114858/phase2-board-host-1920x1080.png`,
  `art/imagegen/mvp-v1/ui/panels/ui-panel-active-turn.png`, `art/imagegen/mvp-v1/ui/portraits/ui-portrait-medusa.png`,
  `art/imagegen/mvp-v1/ui/portraits/ui-portrait-harpy-v2.png`.
- **Промпт:**

```
The attached Sarpedon view during a maneuver draft with three planned moves at once: the hero and two winged harpy
sidekicks of the gold team each have a warm gold (#FFC857) path line to a destination with a translucent ghost and a
round dark order badge "1", "2", "3". The second plan still needs a boost: its outer destination ring and its path are
dashed gold with a tiny dark "+2" chip. The third plan is in conflict: its destination ring and path are dashed red
(#D9483F) with a small exclamation icon. Top-left, a dark maneuver panel: a title bar, then three rows each with an order numeral,
a small portrait (hero, harpy, harpy), a short grey placeholder bar, the space labels like "S20 → S27" and a step
counter like "3/7"; the third row has a red exclamation icon; small up/down arrow buttons and an x button at the end
of each row; below, a boost row with the boost icon and "+4", two small grey buttons, and a wide confirm button that is
dimmed because of the conflict.
```

- **Критерии приёмки:** порядок читается без подсказки; план «нужен буст» (пунктир + чип) и конфликтный план
  (пунктир + «!») отличимы друг от друга и в сером; панель не перекрывает доску; кнопка подтверждения явно неактивна.

### MS-C-07. Ошибки и блокировки

- **Назначение:** обратная связь при отказе: враг-блок, нехватка шагов, обездвиженный боец.
- **Референсы:** `docs/game-design/evidence/ART-005/art3-live-3boards-r2-2026-09-29/k1/cobble-5x6/run-20260929-192438/phase2-board-host-1920x1080.png`,
  `art/imagegen/mvp-v1/ui/actions/ui-action-refusal.png`, `art/imagegen/mvp-v1/ui/cursors/ui-cursor-unavailable.png`.
- **Промпт:**

```
The attached Cobble City grid during a maneuver draft. Three feedback moments in one frame: (1) a tile occupied by an
enemy steel-blue hexagon-ring figure has dark diagonal hatching and a small padlock icon; (2) the player has just
clicked a tile beyond any reach, even with the biggest boost: a red X with a round stop icon sits on that tile, the
cursor shows the unavailable cursor, and a small dark tooltip with a placeholder text bar and the numerals "9/3"
floats next to it; (3) one
gold-team sidekick figure is greyed out with a small chain icon above its base, meaning it cannot move this turn.
Reachable tiles keep the warm-white keylined rounded-square rings.
```

- **Критерии приёмки:** каждая из трёх причин различима значком и формой; красный используется только у креста; клетка
  с отказом лежит за пределами яруса буста (в ярусе буста клик ставит цель «нужен буст», а не отказ — 03 §3.1); серая
  фигурка не путается с побеждённой (у побеждённой фишка скрыта).

### MS-C-08. Взгляд соперника

- **Назначение:** что видит игрок, пока соперник планирует и после его коммита.
- **Референсы:** `docs/game-design/evidence/ENV-MAPS/p5a-verify-2026-10-01/live/sarpedon/k1/run-20261001-114858/phase2-board-joiner-1920x1080.png`,
  `art/imagegen/mvp-v1/markers/marker-selection-p2.png`, `art/imagegen/mvp-v1/ui/portraits/ui-portrait-king-arthur-v2.png`.
- **Промпт:**

```
The attached Sarpedon view from the gold player's side right after the opponent's maneuver. The steel-blue team
knight has just moved four spaces: his origin space shows a thin steel-blue hexagon outline with gaps at the
corners, a trail of small steel-blue dots marks each space he passed along the drawn lines, and his destination
shows a solid steel-blue hexagon ring under him. Near the top-right opponent portrait, a small pulsing "planning"
indicator (three dots) is fading out. Above the hand tray, a thin dark event strip with two placeholder text bars
and a boost icon with "+2". The camera does not move; at the right screen edge, a small arrow points toward a second
moved figure that is outside the view.
```

- **Критерии приёмки:** ход соперника читается без анимации (откуда, где прошёл, куда); цвет и форма — команды P2;
  след не сливается с синей зоной (форма шестигранника и точки); индикатор планирования не выдаёт содержимое черновика.

## 5. После генерации

1. Сохранить файлы и `manifest.json`; посчитать sha256.
2. Собрать `contact-sheet.png` (цвет + серый) — скрипт в `art/imagegen/move-selection-v1/_tools/` (по образцу
   `tools/art-imagegen/`).
3. Записать в `art/imagegen/move-selection-v1/README.md`: какие концепты выбраны как стартовые значения для MS-T-08 и
   MS-T-13, какие отвергнуты и почему (по критериям §4).
4. Пометить, что это предложения; финальную арт-приёмку делает пользователь на кадрах MS-AT-30.
