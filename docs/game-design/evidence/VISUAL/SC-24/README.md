# SC-24 — PAUSE: меню паузы и выход из партии (`UUmScreenPause`, `UUmSettingRow`)

VS-7, шаг S4, 2026-10-08, ветка `feat/visual-vs7` (worktree `C:/tmp/wt-visual`), коммит `28ec24d2`. Карточка — `screens.csv`
SC-24; 04 §1.8 (H16); принятый макет CX-32 `art/imagegen/sc24-pause-codex/` (ВР-VS5-SC24-01…12). Вкладки модали —
[SC-25](../SC-25/README.md) звук, [SC-26](../SC-26/README.md) язык, [SC-27](../SC-27/README.md) масштаб,
[SC-28](../SC-28/README.md) игра, [SC-29](../SC-29/README.md) подсказки, [SC-30](../SC-30/README.md) графика; здесь — общие
сборки, тесты, гейты, прогоны и решения шага.

**Статус:** UE-часть готова, живая проверка одним клиентом editor-build на основном бэкенде `:3000`, по делегированию. Набор G
packaged с `RENDER`, листы цвет / серый / дейтеранопия, G-READ / G-GRAY / G-LOOK и статус в реестре 03 — шаг «Кадры».
**Откат:** `-S08SlateHud=pause` — паузы нет: Esc пишет `INPUT esc pause.unavailable`, «≡» только пишут трассу.

## Что сделано (`do`)

| Пункт | Где и как |
|---|---|
| Экран | `UUmScreenPause : UUmModalBase` (`S08/UI/UmScreenPause.h/.cpp`), WBP `/Game/S08/UI/Screens/WBP_UI_SCR_PAUSE` (`UUmHudAuthoring`, `ue_author_um_hud.py`), в `Modals` корня. BindWidget `TitleText`, `RunningText`, `DefenseText`, `HeaderDivider`, `Tabs` (`TabSound`, `TabInterface`, `TabGame`, `TabGraphics`), `Rows` (пул `UUmSettingRow`), `ScrollTrack`, `ScrollThumb`, `FooterDivider`, `LeaveButton`, `LeaveWhy`, `ContinueButton`. |
| Раскладка | ВР-VS5-SC24-01…03: модаль 720 su (рамка базы, скин `modal`), отступ 16, высота по содержимому, не выше 800 su (720p — 864) и холста без полей; вкладки 160×48 через 8, ряды 520 su с `panel.divider`; при нехватке высоты ряды прокручиваются колесом (полоса 4 su, 4 su от края), шапка и низ на месте. |
| Шапка | «Пауза»; в GAME «Партия продолжается» и, пока открыто окно защиты, «До конца окна защиты {n} с» (`combatInfo.timeoutAt`, `SecondsUntilDeadline`). |
| Низ | «ПОКИНУТЬ ПАРТИЮ» (обычная: X `badge-refuse` 24 su + `text.primary`) слева, «ПРОДОЛЖИТЬ» — единственная главная — справа; пока команда в полёте — «Покинуть» недоступна, под ней «Синхронизация…» (`why.syncing`), нажатие отказывает с `UI-REJECT`. LOBBY — без «Покинуть»; ROOM — «ВЫЙТИ ИЗ КОМНАТЫ» → собственный диалог комнаты (SC-17). |
| Выход | «Покинуть партию» → `UUmConfirmDialog` «Покинуть партию» / «Партия прервётся для обоих игроков» → `UI-PAUSE-EXIT` + `leaveGame` (`FS08FlowController::LeaveRoom`) → LOBBY. |
| Вход | Esc без выбора в GAME (ответ ввода хода вместо `pause.unavailable`), «≡» в TOP (`HandleUmTopPress`), «≡» шапок LOBBY / ROOM и Esc на них (если не открыта другая модаль). Esc в паузе = «Продолжить» (сначала закрывает диалог выхода). |
| Звук | открыта: `SetAudioPaused(true)` + `UI-PANEL-OPEN`; закрыта: `SetAudioPaused(false)` + `UI-PANEL-CLOSE` (трасса `MUSIC pause=1/0` — звуковая сторона приглушает музыку −10 дБ); выход — `UI-PAUSE-EXIT`. |
| Трасса | `SHOT widget id=UI-SCR-PAUSE impl=umg state=<sound|interface|game|graphics> … context=<game|lobby|room> rows= scroll= visible= total= modalH= leave=<enabled|disabled|none> why= defense=<n|-> primary=continue lang=<ru|en|pseudo>`; диалог выхода — `state=confirm` (ВР-SC11); `PAUSE open|close|tab|leave …`, `SETTINGS set <k>=<v> source=pause`. |
| Ввод | открытая пауза владеет клавиатурой и полем (`UmPauseOwnsInput` в тике рядом с INSPECT); партия на сервере идёт. |
| Инструменты | `-S08PauseDrive=<plan>` (open, close, inlobby / inroom / ingame, tab-*, scroll, top, `<key>.<value>`, leave, leaveno, leaveyes, exit) и кадры подсостояний `UI-SCR-PAUSE-<context>-<tab|confirm>[-defense][-syncing][-scrolled][-<lang>][-ui<n>][-gfx<n>].png` при `-S08ScreenShots`; `tools/s08/screens/room_actor.cjs --play-after-ms` — хост ходит по API, пока у гостя открыта пауза. |

## Решения по делегированию (шаг S4)

| № | Решение | Почему |
|---|---|---|
| ВР-VS7-45 | Псевдолокаль +30 % — в `UmText`: флаг `-S08Lang=pseudo`, каждая строка таблиц = «[» + RU + «~» × ⌈0,3·длина⌉ + «]», имена из данных не трогаются; флаг читается один раз, не сохраняется | ВР-VS4-85 оставил +30 % на VS-7; `-LEET` удлиняет неравномерно; формула = ВР-VS5-SC26-03 |
| ВР-VS7-46 | Длинное значение или подпись «Без звука» (EN, псевдолокаль) укорачивают дорожку ползунка (не меньше 120 su), текст не режется | 04 §6.2: ни один текст не обрезан |
| ВР-VS7-47 | Колонка вкладок 160 su растёт, только если подписи не хватает места (псевдолокаль), модаль растёт вместе с ней | ряды 520 su заданы макетом; обрезать вкладку нельзя |
| ВР-VS7-48 | Слово длиннее колонки 140 su ставит подпись строки над контролом | иначе подпись заходит на ползунок |
| ВР-VS7-49 | Контекст паузы — по маршруту: GAME, LOBBY, ROOM; над BOOT / LOGIN / загрузкой паузы нет; уход с маршрута закрывает паузу | 04 §1.8 называет только эти входы |
| ВР-VS7-50 | «Качество графики» — `SetOverallScalabilityLevel` + `ResolutionQuality` 100 + `Scalability::SetQualityLevels` + `SaveSettings`, без `ApplySettings` | `ApplySettings` заново выставляет лимит кадров и разрешение (AGENTS.md «Unreal GPU load»: не трогать) |
| ВР-VS7-51 | Строка настройки отдаёт имя `s08.Settings` и значение; применение — `ApplySetting` + `Save` (громкости, движение, масштаб применяют их слушатели `OnChanged`) | один путь с консолью DE-025, ничего не дублируется |
| ВР-VS7-52 | Язык при запуске: `-S08Lang` → `-culture=` скриптов набора I → сохранённый; чипы RU / EN на LOGIN тоже сохраняют `Language` | выбор игрока переживает перезапуск, скрипты набора I не ломаются |
| ВР-VS7-53 | Заливка ползунка — `card.cream` своей кистью (скин `progress.fill` набора HB-08 — `state.pending`); «Без звука» в слоте 60 su, может уйти на 2 строки | ВР-VS5-SC24-02 |
| ВР-VS7-54 | В прокручиваемой области видны только целые ряды, частично видимые скрыты | ВР-VS5-SC24-03: половин букв нет |
| ВР-VS7-55 | Довод «партия на сервере не стоит» — гость с открытой паузой, хост ходит по API (`room_actor.cjs --play-after-ms`) | один клиент UE на шаг (правила скорости) |

## Проверка

- Сборки: UnmatchedEditor `s4-build-1…8` (1 — неоднозначный `FCulture` и C4458 / C4459, 7 — C4456; исправлено, последняя
  Succeeded, лог прочитан), игровая цель `s4-build-game-1` Succeeded.
- WBP: `ue_author_um_hud.py` (`UM_HUD_WBP_OVERWRITE=0`) — `WBP_UI_SCR_PAUSE` created, остальные exists-unchanged,
  `UM_HUD_WBP_PASS assets=34`. Строки: `hud_strings_build.py build` PASS (ST_Screens 142, locres EN / RU).
- Тесты: новые `Unmatched.S08.Hud.Screens.Pause.Tree`, `.Pause.Model` — PASS (обе передачи: код и WBP); `Unmatched.S08.Hud.Screens`
  20 из 20; широкий набор (`S08.Hud`, `IconMotion`, `StaleGuards`, `RoomEntry`, `Leave`, `S10`, `S09.HUD`, `S09.HudPress`,
  `Phase2`, `MoveAnim`, `Audio`) — 240 из 240.
- Гейты: `hud_contract.py check-trace` PASS на `s4b` (551 строк `SHOT widget`), `s4c` (641), `s4d`, `s4e`, `s4f`, `s4g`;
  `validate` PASS; `hud_tokens_codegen.py --check` FRESH; `pytest tools/s08/hud_contract` 75 из 75; `hud_strings_build.py check` PASS.
- Живые прогоны (UnrealEditor `-game` worktree, 30 FPS, offscreen, `C:/tmp/visual/VS7/runs/`, демо-аккаунты):
  - `s4b` / `s4f` 1080p (VS_AI, Marmoreal original, хост): пауза над LOBBY → GAME → все вкладки → «Низкое» / «Высокое» →
    громкость 50 % и mute → выход «Отмена» → EN и обратно → масштаб 150 / 75 / 100 → подсказки клавиш «Выкл» / «Авто» → Esc.
    `s4f` — повтор `s4b` на финальной сборке.
  - `s4c` / `s4g` 720p (1×1, гость; хост `room_actor.cjs` на Sarpedon original): пауза в ROOM → GAME; пауза открыта 47 с, за это
    время хост сделал два манёвра: в трассе гостя `HANDLE_APPLIED seq=2…5`, ход перешёл к гостю (`turn=you`) — партия не стоит;
    масштаб 150 % (холст 1138×640, класс S, прокрутка) → «Покинуть партию» → «Да» → `UI-PAUSE-EXIT`, `LEFT room=…`, LOBBY.
    `s4g` — повтор `s4c` на финальной сборке.
  - `s4d` 720p 150 % с `-S08Lang=pseudo`, `s4e` 1080p с `-S08Lang=en` — пауза над LOBBY, все вкладки.
- Открыты (Read): game-sound, lobby-sound, game-confirm, game-interface, game-game, game-graphics(-gfx0), interface-en, -ui150,
  -ui75 (`s4b`, `s4f`); room-sound, game-sound 720p, game-sound(-scrolled)-ui150, game-confirm 720p (`s4c`, `s4g`); все вкладки
  псевдолокали (`s4d`, дважды) и EN (`s4e`). После `s4b` исправлено: заливка ползунка была `state.pending`, чипы впритык к тексту;
  после `s4c` — «Без звука» под полосой прокрутки, полряда на краю прокрутки; после первого `s4d` — подпись «Масштаб интерфейса»
  на ползунке в псевдолокали.

## Кадры

Пауза лежит над GAME (сканы карт руки, портреты), ROOM (аватары) или LOBBY (миниатюры карт) — полные кадры только в
`scraped-data/derived/visual-evidence/SC-24/` (индекс `visual-evidence-index.json`); в git — JPEG непрозрачной модали:
`pause-game-1080p-100.jpg`, `pause-confirm-1080p-100.jpg`, `pause-room-720p-100.jpg`.

## Не сделано в этом шаге

- Набор G packaged с `RENDER`, листы цвет / серый / дейтеранопия, G-READ / G-GRAY / G-LOOK, реестр 03 и статусы `screens.csv` —
  шаг «Кадры». Бюджет модали ≤ 0,5 мс GT / 0,3 мс GPU не мерился (правило без оптимизаций: мерить один раз в «Кадрах»).
- Состояния game.defense и syncing проверены тестом `Pause.Tree`, вживую не снимались (в прогонах не было боя и команды в
  полёте в момент паузы).
- Навигация Tab / стрелками и кольцо фокуса по модали не сделаны (мышь, Esc).
