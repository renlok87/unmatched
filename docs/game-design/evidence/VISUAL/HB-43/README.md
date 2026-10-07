# HB-43 — ACTIONS: `UUmHudActions` (шаг H6)

VS-4, шаг V3 (H6), 2026-10-07, ветка `feat/visual-vs4` (worktree `C:/tmp/wt-visual`), код — `21166207`, правка теста
(язык EN под замер подсказки) — `1ece7893`. Карточка — `hud.csv` HB-43; 04 §2.11, §2.14 (дельты VS-4), §3.1, §7.1;
принятый макет HB-42 (`art/imagegen/hud-actions-v1-codex/`, ВР-VS2-HB42-03…-19). Носитель значков IC-46 (конец хода),
IC-55 («Журнал» в TOP класса S), IC-59 / IC-60 (курсоры над ячейкой) — их листы K1 галереи в своих папках.

**Статус:** блок, WBP, клавиши, тесты и лист галереи готовы, по делегированию. Кадры K1 packaged `-Bench` (набор A) —
шаг «Кадры». **Откат:** `-S08SlateHud=actions` — прежняя пара Slate «BEGIN MANEUVER (M)» / «END TURN (E)» (она же под
гейтом `-S09Markers`).

## Что сделано (`do`)

| Пункт | Где и как |
|---|---|
| 1. Блок | `UUmHudActions` (`S08/UI/UmHudActions.h/.cpp`) — 4 × `UUmButton` вариант «диск» (`action-maneuver`, `action-attack`, `action-scheme`, `action-end-turn`), `/Game/S08/UI/Hud/WBP_UI_HUD_ACTIONS` (библиотека `UUmHudAuthoring`, `ue_author_um_hud.py`). |
| 2. Числа HB-42 | класс L: ячейки 78 / 78 / 78 / 86 × 72 su, зазоры 8 su, ряд 344 × 72 в (1552, 984); диск 48 su на y + 4; подписи `type.tag` капсом на одной базовой линии y + 67 su; чип клавиши 20 × 20 su в 2 su от правого верхнего угла. Класс S: 4 × 48 su, диск 40, подписи — в подсказке. Скины HB-08 по состоянию (`Btn_*`, главная — `BtnPrimary_*` только доступной). |
| 3. Состояния | `UmHudActions::Decide` (без мира): ход соперника — все `why.not.your.turn`; запрос в пути — все `why.syncing`; черновик манёвра — МАНЁВР выбрана, остальные `why.draft.open`; сброс по лимиту — `why.no.actions` / `why.discard.count`; бой — `why.wait.defender`; 0 действий — `why.no.actions`; черновики атаки и схемы — своя кнопка выбрана, две другие доступны; нет карты схемы — `why.scheme.none`; КОНЕЦ ХОДА главная только при пустом `EndTurnReason` (SD-44); двух главных не бывает. |
| 4. Подсказка | плашка HB-22 8 su над рядом внутри поля 16 su: L — только у недоступной ячейки, `why.*`; S — подпись, под ней `why.*`, чип справа; задержка 300 мс, шире 360 / 300 su — перенос, не обрезка. |
| 5. Ввод | клик = команда клавиши (`PressUmActionKey`): M, A, G, E; арбитр `FS09HudPressArbiter` (те же id нажатий); шаг флага `hudendturn` жмёт ячейку UMG. Ответ в кадр отпускания. |
| 6. Клавиши UI-ACC-017 | `US08UserSettings::KeyHintsMode` `auto|on|off` (+ `-S08KeyHints=`, `s08.Settings keyHints=`), «Авто» — до первой доигранной партии (`CompletedMatches`, +1 на экране результата, `-Bench` не считает); чипы строки статуса — тот же режим. Трасса `HUD-KEYHINTS mode= shown= completedMatches=`. |
| 7. Slate | пара «BEGIN MANEUVER» / «END TURN» — только с `-S08SlateHud=actions` или `-S09Markers`. |
| 8. SHOT | `SHOT widget id=UI-HUD-ACTIONS impl=umg state=own|opp|mode=maneuver|attack|scheme … class=L|S actions=<n> primary=0|1 keys=0|1 cells=… buttons=… tip=…`. |
| 9. Тесты | `Unmatched.S08.Hud.Actions.Tree`, `.States` (матрица HB-42, ячейки, скины, подсказка, SHOT, бюджет), `.KeyHints`, `Unmatched.S09.HudPress.UmgActions` (синтетические клики по 24 на ячейку, удержание 0 и 50 мс, повторное применение модели — 0 потерь; недоступная — Refused со своим `why.*`). |

Хуки в `S08FlowGameMode.cpp` — 6 строк (обновление, Slate-пара, клавиша G, шаг флага), `S08FlowGameModeResult.cpp` —
счётчик партий; остальное — `S08FlowGameModeUmHud.cpp`.

## Решения по делегированию (шаг V3)

| № | Решение | Почему |
|---|---|---|
| ВР-VS4-40 | Запрос в пути — весь ряд недоступен с `why.syncing`; надписи «Отправлено…» на дисках нет | причина видна в подсказке и в строке статуса; диск не меняет форму |
| ВР-VS4-41 | G / СХЕМА при открытом черновике атаки закрывает его и открывает выбор схемы (дельта ВР-VS2-HB42-05) | черновик атаки локальный — ничего не отправлено, переключение режима не теряет хода |
| ВР-VS4-42 | В ход соперника — состояние «недоступна» (диск 0,4, подпись `text.secondary`) у всех четырёх, без второго множителя 0,4 на ряд | двойное приглушение давало 0,16 и нечитаемые подписи |
| ВР-VS4-43 | Нет карты схемы в руке — СХЕМА недоступна с `why.scheme.none` | ключ есть в `why-reasons.json`; иначе нажатие давало бы пустой выбор |
| ВР-VS4-44 | Подсказка (L — `why.*`, S — подпись) после 300 мс наведения; при фокусе с клавиатуры — сразу | одно правило для мыши; клавиатуре задержка не нужна |
| ВР-VS4-45 | «Авто» UI-ACC-017 = чипы видны, пока `CompletedMatches` = 0 (экран результата, кроме `-Bench`) | «только первая партия профиля» (ВР-H09) без отдельного флага профиля |

## Лист

Галерея `-S08IconGalleryActions=<board>` (инструмент ревью, не матч и не кадр приёмки; `S08/UI/UmActionsGallery.h`):
настоящие `UUmHudActions`, `UUmHudDecks`, `UUmHudTop` в `UUmGameHud` поверх кадра bench K1 доски (Marmoreal original с
нарисованным задником `-ConceptPaste`, Sarpedon original lit3d; шесть фигур v2), 16 состояний матрицы HB-42 по секунде:
own-2, own-2-why, own-1-why, own-0, own-0-why, mode-maneuver, mode-maneuver-why, mode-attack, mode-scheme, discard-why,
opp, opp-why, hover, focus, keys, keys-own-0; у наведённой ячейки — программный курсор её формы (IC-59 / IC-60).
10 холстов: обе доски × 1080p 75 / 100 / 150 % и 720p 100 / 150 %.

- В git (без доски и сканов: `-S08IconGalleryHandPlain -S08CardArtLegacy`): `plain-marm-1080-100-contact-*.png`,
  `plain-marm-720-150-contact-*.png` (16 состояний, цвет и серый), `plain-crops-*.png` (ряд ACTIONS 16 состояний,
  1080p 100 % и 720p 150 % ×2).
- Вне git (кадр доски, ВР-VS4-01): `scraped-data/derived/visual-evidence/HB-43/` — контакты 10 холстов (цвет, серый),
  вырезки ряда 16 состояний × 10 холстов (цвет, серый, дейтеранопия) — [`visual-evidence-index.json`](visual-evidence-index.json).

Что видно (Read: вырезки ряда `actions-crops-colour.png` 16 состояний × 10 холстов, серый — фрагмент 720p 150 % и
Sarpedon 1080p 75 %, plain-листы цвет и серый, кадр Marmoreal 720p 150 % own-2-why целиком): четыре диска на тёмных
ячейках-скинах, подписи «МАНЁВР / АТАКА / СХЕМА / КОНЕЦ ХОДА» на одной линии в классе L, в классе S — только диски;
own-0 — КОНЕЦ ХОДА жёлтая главная, остальные 0,4; режимы — выбранная ячейка с подложкой `state.pending`; ход
соперника — весь ряд 0,4, подсказка «АТАКА / Сейчас не ваш ход» и курсор «недоступно»; hover / focus — рамка и
указатель, в S — плашка с подписью; keys — чипы M A G E в углах (L) или в подсказке (S); подсказки внутри поля, над
рядом, не закрывают DECKS больше, чем макет HB-42. В сером главная ячейка и выбранная отличаются тоном тела, недоступные —
бледностью диска. Доска — Marmoreal с нарисованным задником / Sarpedon lit3d, шесть фигур v2 (кадр bench K1).

## Проверки

- Сборки UnmatchedEditor (build-18) и игровой цели (build-game-2) — Succeeded.
- UE: `Unmatched.S08.Hud.Actions.*` + `S09.HudPress.UmgActions` — 4 из 4; полный прогон `Unmatched.S08+S09+S10` — 498 из
  498 (build-18). Бюджет: обновление ряда (Decide + ApplyModel) p95 0,0134 мс, шаг кадра ≤ 0,03 мс.
- pytest `tools/s08/hud_contract` — 69 из 69; `hud_contract.py validate` PASS; `hud_strings_build.py check` PASS;
  `hud_tokens_codegen.py --check` FRESH; `check-trace` — PASS на трассах галереи (`UI-HUD-ACTIONS` в каждом состоянии).
- WBP `WBP_UI_HUD_ACTIONS` — created (`author-1-report.json`).

## Что не сделано в этом шаге

- Кадры K1 packaged `-Bench` (набор A: свой ход, наведение, выбрана атака) обеих досок — шаг «Кадры»; живой прогон
  партии с нажатиями мышью в этом шаге не снимался (арбитр проверен синтетическими кликами).

## Кадры выхода VS-4 (HB-49, упаковка `5a74a81e`, 2026-10-07)

Живые партии приёмочной упаковки, Marmoreal original (`-ConceptPaste` до EN-13, пометка) и Sarpedon original, шесть фигур v2, слоя отладки нет; прогоны, гейты и листы — [HB-49](../HB-49/README.md) (картинки со сканами и доской — вне git, `scraped-data/derived/visual-evidence/HB-49/`, ВР-VS4-01).

Ячейки ACTIONS во всех кадрах; курсор «нельзя» над недоступной «Конец хода» с подсказкой «Сначала потратьте действия: осталось 2» (`s09-exit-cursor-button`); класс S — диски без подписей, подписи в подсказке. **Вердикт: художественно принято, по делегированию (2026-10-07).** Кнопки черновика атаки «ATTACK (Enter) / CLOSE DRAFT (Esc)» и «RESOLVE COMBAT (R)» остаются Slate (нет UMG-элемента в 04, HB-49 «Вид по умолчанию»).
