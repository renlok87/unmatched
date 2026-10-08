# SC-38 — ABORTED: партия прервана (`UUmScreenAborted`)

VS-7, шаг S5, 2026-10-08, ветка `feat/visual-vs7`. Карточка — `screens.csv` SC-38; 04 §1.11 (новый ID UI-SCR-ABORTED), GD-040;
макет CX-34 `art/imagegen/sc38-aborted-codex/` (ВР-VS5-SC38-01…04). Сборки, строки, WBP — [SC-31](../SC-31/README.md).

**Статус:** UE-часть готова, живая проверка editor-build (`s5c`, 1×1 на Sarpedon original, хост вышел из живой партии), по
делегированию. Набор F packaged, листы, G-READ / G-GRAY / G-LOOK, packaged-прогон `run-vs-ai-abort-demo.ps1` и реестр 03 — шаг
«Кадры». **Откат:** `-S08SlateHud=aborted` — текст прерывания в командной панели (маркер `#FF6414` только с `-S09Markers`).

## Что сделано (`do`)

| Пункт | Где и как |
|---|---|
| Экран | `UUmScreenAborted : UUmModalBase` (`S08/UI/UmScreenAborted.h/.cpp`), WBP `/Game/S08/UI/Screens/WBP_UI_SCR_ABORTED`, в `Modals`; BindWidget `Icon`, `TitleText`, `WhoText`, `TurnText`, `LobbyButton`. |
| Вход | строка комнаты ABORTED в живой партии (`IsRoomAborted`: `game(id)` / ответ мутации, не снапшот и не CUE). Slate-блок прерывания скрыт хуком `UmAbortedOnUmg` в `RefreshHud`. |
| Раскладка | ВР-VS5-SC38-02: модаль 640×360, колонка по центру: `resource-connection-lost` 48 su; «Партия прервана» `type.title`; «Соперник покинул партию» `type.body`; «Ход 1» `type.caption` `text.secondary`; «В ЛОББИ» (+ Enter, если чипы включены) — единственная главная. Ни слов, ни цветов победы / поражения, без грейда CUE-016; красный — только X значка. |
| Выход | «В лобби», L, Enter → `ReturnToLobbyCommand` (`leaveGame`) → LOBBY (ВР-VS7-67). `STG-ABORTED` звучит сам. |
| Трасса | `SHOT widget id=UI-SCR-ABORTED impl=umg state=shown … who=<named|unknown> turn=<n> primary=lobby`, `ABORTED shown who=… turn=…`. |
| Строки | `screens.aborted.who.unknown` «Соперник покинул партию» / "The opponent left the game" — новая (дельта CX-34); остальные `screens.aborted.*` были. |
| Гейт S10 | `tools/s10/run-vs-ai-abort-demo.ps1`: по умолчанию `Test-AbortedWidget` — нарисованная видимая строка `SHOT widget id=UI-SCR-ABORTED state=shown` раньше снимка доказательства и ни одной строки UI-SCR-GAMEOVER (04 §5.3); `-S09Markers` — откат к пикселям `#FF6414` / `#40C8FF`; самотест PASS (4 новых проверки). Прогон доказательства `-S10AbortProof` не менялся. |

## Решения по делегированию

| № | Решение | Почему |
|---|---|---|
| ВР-VS7-66 | Имя вышедшего сервер клиенту не отдаёт (только `GameAction GAME_ABORTED.userId`) — всегда «Соперник покинул партию» (ВР-SC13); «Игрок {player} покинул партию» — только когда имя придёт в данных | ничего не выдумывать; в 1×1 игрок видит экран только когда вышел другой. Исключение — харнесс S10: там прерывает внешний `abortGame` той же учётной записи, текст условен |
| ВР-VS7-67 | «В лобби» — прежний `ReturnToLobbyCommand` (один `leaveGame`, общий с L / Enter и доказательством S10) | один путь выхода, гейт `-S10AbortProof` не меняется |

## Проверка

- `Unmatched.S08.Hud.Screens.Aborted.Tree` (код и WBP): «Партия прервана», «Соперник покинул партию», «Игрок Veteran покинул
  партию» с именем, «Ход 1», «В лобби» единственная главная, нет «ПОБЕДА» / «ПОРАЖЕНИЕ», нажатие, модаль внутри трёх холстов.
- Живой `s5c` (720p): хост (`room_actor.cjs --stay-ms 100000`) вышел → `game -> … status=ABORTED` → `ABORTED shown who=unknown
  turn=1`, `SHOT … state=shown … primary=lobby` → «В лобби» (`-S08EndDrive lobby`) → `RESULT lobby-return sent (leaveGame)`,
  `LEFT room=…`, `HUD-SCREEN route=lobby`; по API у гостя `myGames` IN_PROGRESS и LOBBY пусты. `check-trace` PASS.
- Кадр открыт (Read, `s5c`); `s5b` — до правки (оверлей RECONNECT restoring закрывал ABORTED: поток прерванной партии
  закрывается и `FS08NetWatch` считает это обрывом; теперь оверлей над ABORTED / GAMEOVER не показывается, ВР-VS7-61).

## Кадры

Полный кадр — `scraped-data/derived/visual-evidence/SC-38/`; в git — непрозрачная модаль `aborted-shown-720p-100.jpg`.

## Не сделано в этом шаге

- Packaged-прогон `tools/s10/run-vs-ai-abort-demo.ps1` с новым гейтом, набор F (Marmoreal и Sarpedon, 1080p / 720p), листы,
  реестр 03 — шаг «Кадры».
- Десатурация CUE-017 горит под ABORTED (VS-6 `FS08NetWatch` принимает закрытие потока прерванной партии за обрыв) — сторона
  VS-6, открытый пункт.
- Кадр без имени и кадр с именем — второй только тестом (сервер имени не отдаёт).
