# SC-08 — LOBBY: список игр и его загрузка (`UUmScreenLobby`, `UUmLobbyGameRow`)

VS-7, шаг S2, 2026-10-08, ветка `feat/visual-vs7` (worktree `C:/tmp/wt-visual`). Карточка — `screens.csv` SC-08; 04 §1.3, §3.3;
принятый макет CX-29 `art/imagegen/sc08-lobby-list-codex/` (ВР-VS4-SC08-01…17). Тот же экран несёт [SC-09](../SC-09/README.md)…
[SC-13](../SC-13/README.md); здесь — общие сборки, тесты, гейты и решения шага.

**Статус:** UE-часть готова, живая проверка одним клиентом editor-build на основном бэкенде `:3000`, по делегированию. Набор G
packaged с `RENDER`, листы цвет / серый / дейтеранопия, G-READ / G-GRAY / G-LOOK, статус в реестре 03 — шаг «Кадры».
**Откат:** `-S08SlateHud=lobby` — прежние Slate-панели GD-036 / GD-029 (проверено: `HUD-SCREENS lobby=slate`, маршрут `game`).

## Что сделано (`do`)

| Пункт | Где и как |
|---|---|
| Экран | `UUmScreenLobby : UUmScreenBase` (`S08/UI/UmScreenLobby.h/.cpp`), WBP `/Game/S08/UI/Screens/WBP_UI_SCR_LOBBY` (`UUmHudAuthoring`, `ue_author_um_hud.py`), в `Screens` корня над фоном SC-02; полный экран, рамка базы не рисуется. |
| Раскладка | класс L — прямоугольники 04 §1.3 (1080p и 720p); класс S — ВР-VS4-SC08-09 (поля 16, правая колонка 456 su). Шапка `panel` 0,92, список и колонки — `modal` (panel.bg 1,0). |
| Шапка | `NicknameText` (username входа), `MenuButton` «≡» (`ui-menu` 24 su), `LangRu` / `LangEn` (язык UI, как LOGIN). |
| Список | `ListTitle`, `RefreshButton` «Обновить» (текстом: глифа ⟳ нет в v3, ВР-VS4-SC08-05), `Skeleton` (HB-47, 3 строки, пульс 900 мс, после 300 мс ожидания), `RowsScroll > Rows` — пул `UUmLobbyGameRow` (опрос строк не пересоздаёт). |
| Строка | 56 su на `panel.inset`, наведение `panel.bg.hover`; Code (`type.heading`), «1×1», имя доски из `boardList`, «n/2», диски 32 su героев игроков (CP-07 B, без кольца), «Войти» (40 su). Колонки — по самому широкому тексту, пять равных промежутков (ВР-VS4-SC08-04). Недоступная — текст `text.secondary`, без мест и кнопки, причина `why.room.full` / `why.room.started` справа и подсказкой (ВР-VS4-SC08-02 / -03). |
| Данные | `FS08FlowController::FetchAvailableGames` — `availableGames(mode: ONE_V_ONE, limit: 20)` (новый `S08FlowControllerLobby.cpp`); опрос 15 с, «Обновить», возврат фокуса окна (ВР-H20, `FUmLobbyPoll`); 10 с без ответа — ошибка (SC-13); поздний ответ применяется. `JoinRoomById` — `joinGame(gameId)` из строки → ROOM. |
| Звук | `UI-BTN-CLICK` (вход, обновить), `UI-REJECT` (отказ строки, ошибка списка); `UI-ROOM-JOIN` и `MUS-MENU` звучат сами. |
| Трасса | `SHOT widget id=UI-SCR-LOBBY impl=umg state=<loading|list|empty|error|create|code|code-error> … list= rows= unavailable= mode= board= busy= code=<число знаков> codeError= recover= primary=` — при каждой смене (кода комнаты и имён нет); `LOBBY list state=… rows=`, `LOBBY join source=row|code`, `HUD-SCREENS lobby=<WBP> lobbyParts=1`. |
| Строки | `common.btn.refresh` (новая); остальные `screens.lobby.*` уже были. |
| Корень | Slate-панель GD-036 стадии `Lobby` не строится, пока UMG LOBBY открыт (`RefreshHud`, 1 строка в `S08FlowGameMode.cpp`). |

## Решения по делегированию (шаг S2)

| № | Решение | Почему |
|---|---|---|
| ВР-VS7-14 | LOBBY открывается после второго прохода BOOT (стадия `Login`) и в стадии `Lobby`; прогоны `-S08Auto` его не видят | отдельного шага «войти в лобби» у потока нет; драйвер гейтов S09 / S10 не меняется |
| ВР-VS7-15 | `createGame` на бэкенде сбрасывает кеш `availableGames` (`backend/src/games/game.service.ts`, +1 вызов) | кеш Redis 30 с не сбрасывался при создании: на живом бэкенде без правки новая комната появилась через 25 с и 38 с, а карточка требует ≤ 15 с |
| ВР-VS7-16 | Отказ `joinGame` строки: «заполнена» → `why.room.full`, иначе (началась, завершилась, исчезла) → `why.room.started`; по коду: «заполнена» → «Комната заполнена», иначе (NOT_FOUND поиска) → «Игра не найдена» | `gameByCode` не различает неизвестный, полный и начатый код (GD-029) |
| ВР-VS7-17 | Своя комната игрока в списке не показывается | `joinGame` отказывает хосту («Вы уже являетесь хостом») |
| ВР-VS7-19 | «≡» в шапке нажимается (звук, трасса `LOBBY menu`), меню открывает шаг PAUSE (SC-24…) | экрана PAUSE на UMG ещё нет |
| ВР-VS7-20 | Ошибка списка в доказательствах — `tools/s10/delay-graphql-query-proxy.cjs` держит `availableGames` 12 с (новое поле), задержка `createGame` — для кадра busy | 10 с без ответа — собственный триггер SC-13; `drop-graphql-reply-proxy.cjs` рвёт только мутации |
| ВР-VS7-23 | Скелет — компонент HB-47 как есть (три сплошные строки 56 su с разделителем), без полос-заглушек макета | принятый компонент; правка — не цель шага |
| ВР-VS7-24 | Чипы режима и языка — `UUmButton` с `type.button` (прописные), как принятый HB-11; в макете чипы строчные | стиль кнопки не меняется под один экран |
| ВР-VS7-25 | Кадры LOBBY в git не кладутся: на каждом видны миниатюры карт (board art, ВР-VS4-01); в git — индекс и JPEG-вырезки панелей без миниатюр и аватаров | правило доказательств |
| ВР-VS7-26 | Строка `SHOT widget id=UI-SCR-LOBBY` пишется при каждой смене состояния / полей экрана | живые прогоны S1 строк `SHOT widget` экранов BOOT / LOGIN не пишут (пишутся только кадры `SCREENSHOT`) |

## Проверка

- Сборки: UnmatchedEditor `s2-build-1…5` (последняя Succeeded, лог прочитан), игровая цель `s2-build-game-1` Succeeded.
- WBP: `ue_author_um_hud.py` (`UM_HUD_WBP_OVERWRITE=0`) — `WBP_UI_SCR_LOBBY` created, 30 прежних exists-unchanged, `UM_HUD_WBP_PASS`.
- Тесты: `Unmatched.S08.Hud.Screens.Lobby.Tree` и `.Lobby.Poll` (новые) — PASS; `Unmatched.S08.Hud.Screens.*` 15 из 15;
  `Unmatched.S08.Hud` 115 из 115; поток `RoomEntryGuard + StaleResponse + LeaveRoom + S10 + S09.Hud` — PASS (EXIT 0).
  Бэкенд: `jest src/games/default-board.spec.ts` 12 из 12 (createGame с кешем).
- Гейты: `hud_contract.py check-trace` — `s2a` 108, `s2b` 90, `s2c` 84, `s2d2` 90, `s2f` 107 строк `SHOT widget`, PASS (в `s2f` —
  5 строк `UI-SCR-LOBBY`: empty, list, code, code busy, code-error); `validate` PASS; `hud_tokens_codegen.py --check` FRESH;
  `hud_strings_build.py build` PASS (ST_Screens 132, locres EN / RU).
- Живые прогоны (UnrealEditor `-game` worktree, 30 FPS, offscreen, `C:/tmp/visual/VS7/runs/`; второй «клиент» — сид-аккаунт
  Veteran через `createGame` API на настоящих досках, комнаты убраны `leaveGame` после прогонов):
  `s2a` 1080p — пусто → создание (выборы) → неверный код; `s2b` 720p 150 % (класс S, `canvas=1138x640`) — скелет, ошибка через
  10 с, поздний ответ → список, вход строкой → ROOM; `s2c` 720p 100 % — список, код 4 / 6 знаков, вход по коду → ROOM; `s2d2`
  1080p — VS_AI на Sarpedon, busy; `s2g` 1080p — «Создать» при ошибке списка → ROOM на Marmoreal; `s2e` — откат `-S08SlateHud=lobby`; `s2f` 1080p — комната второго клиента появилась в списке
  через 25 с (бэкенд без ВР-VS7-15).
- Открыты (Read): empty 1080p, create-ai 1080p, code-error-notfound 1080p, list / error / loading 720p 150 %, code-full /
  code-partial 720p 100 %, busy 1080p (`s2d` — плитки теряли выбор → исправлено, `s2d2`), list 1080p, вырезки.

## Кадры

В git (`list-panel-1080p-100.jpg`): панель списка без миниатюр. Полные кадры — `visual-evidence-index.json`
(`scraped-data/derived/visual-evidence/SC-08/`: loading 720p 150 %, list 1080p / 720p 100 % / 720p 150 %).

## Не сделано в этом шаге

- «Список обновляется ≤ 15 с после создания комнаты вторым клиентом» на живом бэкенде — после интеграции и сборки бэкенда с
  ВР-VS7-15 (сейчас 25–38 с из-за кеша сервера); модель опроса (15 с) покрыта `Lobby.Poll`. Прогон двух клиентов UE — шаг «Кадры».
- Недоступная строка и диски героев живьём не сняты (на стенде нет комнат с выбранным героем и гонки входа) — покрыты `Lobby.Tree`.
- Набор G packaged, листы, G-READ / G-GRAY / G-LOOK, статус в реестре 03 и `screens.csv` — шаг «Кадры». Бюджет экрана ≤ 0,5 мс
  GT / 0,3 мс GPU не мерился.
- Глиф «обновить» (⟳) — нужна карточка IC. Навигация Tab по экрану LOBBY не сделана (кольцо фокуса — только у «Войти» по коду
  при вводе с клавиатуры).
