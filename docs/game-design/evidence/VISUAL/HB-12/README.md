# HB-12 — курсоры UUmCursor (software cursors, 4 состояния)

VS-2 шаг A3, 2026-10-06, ветка `feat/visual-vs2` (worktree `C:/tmp/wt-visual`). Карточка — `docs/game-design/visual/06-tasks/hud.csv`
HB-12; спецификация — 04 §3.2, §4.2; 02 §4.4 (ВР-46). Курсоры нарисованы движком v3 (IC-58, IC-60, IC-61 — шаг A2;
IC-59 — шаг A3, форма Codex IC-36 fix1).

**Статус:** код, текстуры, WBP и тесты готовы; приёмочные кадры packaged — шаг «Кадры» VS-2 (упаковки в этом шаге нет).
**Решение по арту:** формы приняты по делегированию в IC-58…IC-61 (листы `docs/game-design/evidence/VISUAL/IC-58|59|60|61/`).
**Флаг отката:** `-S08SlateHud=cursor` (или весь `-S08SlateHud`) — ничего не регистрируется, системный курсор как раньше.

## Что сделано

| Пункт карточки | Где |
|---|---|
| 1. UUmCursor, BindWidget Image; ApplyModel | `Source/Unmatched/S08/UI/UmCursor.{h,cpp}` — `UUmCursor` (BindWidget `Box`, `Image`), `ApplyModel(FUmCursorModel)`, `BuildDefaultTree`; `/Game/S08/UI/Common/WBP_UmCursor` (генерируется `tools/s08/hud_contract/ue_author_um_hud.py`) |
| 2. SetSoftwareCursorWidget: Default → Default, Hand → Pointer, SlashedCircle → Denied; Busy перекрывает | `UUmHudRoot::InstallCursors` / `TickCursors` (`S08/UI/UmHudRoot.cpp`): три виджета на вьюпорте; пока `HudBusyReason()` = why.syncing, все три рисуют песочные часы (8 кадров, 1500 мс, reduced — кадр 0) |
| 3. UUmButton и карты ставят Hand / SlashedCircle; поле — Hand над своей фигурой и подсвеченной клеткой | `UUmButton::Restyle` (Hand, у disabled — SlashedCircle); Slate-нажатия `MakeHudPress` (кнопки, карты руки, фишки колоды — до перевода их блоков) — то же правило; поле — `PC->CurrentMouseCursor` = `UmCursor::BoardCursor` в `TickUmHud` (своя фигура: `OwnerId` = зритель; клетка в `ReachableCells` выделения, `AS08BoardActor::IsCellHighlighted`). `UUmCardWidget` ставит курсор, когда появится (CP-15) |
| 4. Текстуры 24/32/48/64, размер по экранному px, кадры занятого, горячие точки | `tools/art/hud_skins_import.py --cursors` → 44 текстуры `/Game/S08/UI/Cursors/T_Cursor_{Default,Pointer,Denied,Busy_00…07}{_24,"",_48,_x2}` (отчёт `art/imagegen/hud-icons-v3/cursor-import-report.json`), горячие точки — `unreal/Unmatched/Config/Cursors/S08CursorHotspots.json` (копия `cursor-hotspots.json`, в pak через `Unmatched.Build.cs`) |
| 5. Трасса HUD-CURSOR | при сборке HUD: `HUD-CURSOR installed=1 impl=software source=…`; на каждом кадре-доказательстве: `HUD-CURSOR state=default|pointer|denied|busy|none base=… busy=0|1 px=… hotspot=(x,y) frame=… game=… painted=0|1 registered=3 impl=software source=…`; откат — `HUD-CURSOR state=system impl=system` |
| 6. `-S08SlateHud=cursor` — системный курсор | `BuildUmHud` не ставит курсоры; `MakeHudPress` не ставит курсор элементу |
| 7. Тест Cursor.Map | `Unmatched.S08.Hud.Cursor.Map` и `Unmatched.S08.Hud.Cursor.Textures` (`S08/UI/UmCursorTests.cpp`) |

Горячая точка: Slate рисует виджет курсора с центром в точке указателя (`FSlateUser::DrawCursor`), поэтому виджет —
2 px × 2 px, картинка стоит на (px − hx, px − hy): пиксель горячей точки покрывает пиксель указателя. Тест Textures
проверяет, что у каждой из 44 текстур пиксель горячей точки непрозрачен (α ≥ 128), у указателя — кончик пальца (11; 2) u.

## Решения по делегированию (ВР-VS2-NN)

- **ВР-VS2-27** (README набора v3, раздел A3): имена текстур — `T_Cursor_*` в `/Game/S08/UI/Cursors`, как в ue_target
  IC-58…IC-61 и 04 §3.2; `T_IV3_cursor_*` из deliverable HB-12 не используется.
- **ВР-VS2-28.** Курсор рисуется 1 : 1 в физических px (Slate не масштабирует виджет курсора); размер — наименьший из
  24 / 32 / 48 / 64 ≥ 32 × DPI × масштаб UI: 720p — 24, 1080p — 32, 150 % и 1440p — 48, 4K — 64 (720p 150 % — 48).
  Фильтр текстур курсоров — nearest (рисуются без ресэмпла).
- **ВР-VS2-29.** Поле: Hand — над своей фигурой и над клеткой, подсвеченной выделением (ReachableCells); выбор цели
  ожидающего выбора (pending) пока не подсвечивает курсором — его клетки дают блоки H10. Пересчёт — при движении
  указателя или раз в 10 кадров (бюджет ≤ 0,01 мс GT: один луч на движение).
- **ВР-VS2-30.** Пока блоки HUD на Slate (до H4…H12), курсор ставит единая точка `MakeHudPress`: Hand у доступного
  элемента, SlashedCircle у заблокированного (с подсказкой why.* по нажатию, как было). Цикл «занято» начинается заново
  с каждой новой команды в полёте.

## Проверки

- UE: `Unmatched.S08.Hud.Cursor.Map`, `.Textures` — зелёные; `Unmatched.S08.Hud.*`, `Unmatched.S09.HudPress.*`,
  `Unmatched.S08.ArtLook.*` — 23/23.
- pytest `tools/art/tests/test_hud_skins_import.py` — 13/13 (план курсоров 44 текстуры, горячие точки указателя и
  «занято», копия `S08CursorHotspots.json` актуальна).

## Отложено (шаг «Кадры» VS-2, packaged)

- Кадры packaged обеих досок (Marmoreal original, Sarpedon original, шесть фигур v2), 1080p 100 % и 720p 150 %:
  наведение на кнопку (указатель), на недоступную «Конец хода» (недоступно + why.actions.remaining), отправленный ход
  (занято); клик-тест HudPress по кнопке 24 su у края. Когда указатель не над окном, Slate курсор не рисует
  (`state=none painted=0`) — кадрам наведения нужен шаг плана ввода с движением указателя.
- `UUmCardWidget` (CP-15) и `UUmHudActions` (HB-43) — носители курсора по своим шагам.

## Кадры VS-2 (2026-10-07, упаковка `230b2b0d`)

- Кадров наведения нет: без движения указателя Slate курсор не рисует (`HUD-CURSOR state=none painted=0` в каждом кадре). Нужен шаг плана ввода с движением указателя (VS-2, «Открыто», п. 5).
- Клик-тест `Unmatched.S09.HudPress.Umg`: n = 24, 0 потерь (UE 418 / 418).
